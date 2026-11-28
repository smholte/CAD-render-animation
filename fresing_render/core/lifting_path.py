"""The lift path and its checks (task 0348, Lifting lane L6a) – plain Python with NumPy, no Blender.

* **Checks at one moment** (``Checks.at``): the joint values of a crane (degrees / mm by its file's names) -> one
  :class:`Row` per check that applies: C1 crane use (``lifting_reach.readout``), C10 the hoist line pull, C2–C4 the
  rigging from the hang (constant while the load hangs rigidly on the hook), C5 outriggers and mats or C6 crawler
  tracks from the crane's masses and centres of gravity (``Supports``), "Set up" (beams out to the spread the chart is
  for, jacks down) and the backward stability when the plan carries more counterweight than the chart picked.
* **The worst moment** (``search``): every check is worked out at the path's keys, at a few points in each gap, then a
  golden-section search round each check's highest peaks – not at every frame blindly (``every`` is that reference).
* **Proposed steps** (``propose``): from where the hook is to a set-down point – hoist clear, slew, luff / telescope,
  travel (a crawler, only when the point is out of reach from where it stands), lower – as joint values per step.

Units: the crane's file frame in mm and degrees (as ``lifting_reach``); masses in kg; the words in t, m and kPa. The
plan's words only (study 0180 section 8): within / near / over the entered limits (lifting.FORBIDDEN_WORDS never).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import lifting
from . import lifting_reach as LR

GREY, GREEN = "grey", "green"
COLOUR = {lifting.OK: GREEN, lifting.AMBER: "amber", lifting.RED: "red", lifting.NOT_CHECKED: GREY}
RANK = {lifting.OK: 0, lifting.NOT_CHECKED: 1, lifting.AMBER: 2, lifting.RED: 3}
BACK_RESERVE = 0.15        # share of the base the unloaded crane's CoG keeps inside it (lifting_model.charts, the makers)
JACK_TOL = 0.02            # share of a jack's run: a jack this close to its down end counts as down
BEAM_TOL = 0.001           # m: beams this close to the chart's spread count as out to it
ORDER = ("C1", "C10", "SETUP", "C5", "C6", "BACK", "CLR", "C2", "C3", "C4")
TITLES = {"C1": "Crane use", "C10": "Line pull", "SETUP": "Set-up", "C5": "Outriggers", "C6": "Tracks",
          "BACK": "Back stability", "CLR": "Clearance", "C2": "Sling legs", "C3": "Sling legs",
          "C4": "Shackles, gear"}


def _pct(u) -> str:
    return f"{u * 100:.0f} %"


def _t(kg: float) -> str:
    t = lifting.tonnes(kg)
    return f"{t:.2f} t" if abs(t) < 100 else f"{t:.1f} t"


def _kpa(pa: float) -> str:
    return f"{lifting.kPa(pa):.0f} kPa"


@dataclass
class Row:
    """One check at one moment: what the table and the data box show."""

    id: str
    title: str
    status: str = lifting.NOT_CHECKED
    use: float | None = None
    value: str = ""             # the worst value in words ("27.9 t", "121 kPa")
    limit: str = ""             # the limit in words ("24.0 t", "200 kPa entered")
    words: str = ""             # one plain sentence (the status line)
    amber_at: float | None = None
    t: float | None = None      # the moment (frame) – set by the search
    measure: float | None = None  # what grows towards the worst when there is no use (a reaction, a pressure)

    @property
    def key(self) -> tuple:
        return (RANK.get(self.status, 1), self.use if self.use is not None else -1.0,
                self.measure if self.measure is not None else -1.0)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status, "use": self.use, "value": self.value,
                "limit": self.limit, "words": self.words, "amber_at": self.amber_at, "t": self.t,
                "measure": self.measure}

    @staticmethod
    def from_dict(d: dict) -> "Row":
        return Row(**{k: d.get(k) for k in ("id", "title", "status", "use", "value", "limit", "words", "amber_at",
                                            "t", "measure")})


def grey(cid: str, why: str) -> Row:
    """A check that is not worked out, with the reason in words."""
    return Row(cid, TITLES.get(cid, cid), lifting.NOT_CHECKED, words=f"{TITLES.get(cid, cid)}: not checked – {why}")


def _limit_words(status: str, amber_at: float | None) -> str:
    c = COLOUR[status]
    if amber_at is None or status == lifting.NOT_CHECKED:
        return c
    return f"{c}, your limit is {_pct(amber_at)}"


def status_line(row: Row) -> str:
    return row.words


# ---------------------------------------------------------------------------------------------------------------------
# masses and supports (C5, C6, set-up, backward stability)

def _flat(up: str, p) -> np.ndarray:
    p = np.asarray(p, float)
    return np.stack([p[..., 0], p[..., 2]], axis=-1) if up == "Y" else p[..., :2]


class Supports:
    """The crane's masses and centres of gravity from its file, moved by its joints.

    ``data["mass"]`` / ``data["cog"]`` by group (the file's units), each group's ``rig.groups[g].moves_with`` joint;
    the counterweight group takes the plan's counterweight; the boom the telescope runs out of moves its CoG out by
    half the head's run (an estimate: the sections' masses are not in the file). The carrier's frame: the crawler's
    travel taken out (everything rides on it)."""

    def __init__(self, rig: LR.Rig, data: dict):
        self.rig, self.data = rig, data
        units = data.get("units") or {}
        self.fm = lifting.MASS_UNITS.get(str(units.get("mass", "t")), 1000.0)
        fl = lifting.LENGTH_UNITS.get(str(units.get("length", "m")), 1.0)
        ru = lifting.LENGTH_UNITS.get(str((data.get("rig") or {}).get("units") or "mm"), 0.001)
        self.to_rig = fl / ru                                       # the file's length unit -> the rig's (mm)
        self.rig_m = ru                                             # the rig's length unit -> m
        self.f_m = fl                                               # the file's length unit -> m
        self.problem = ""
        self.groups = []                                            # (name, kg, cog mm, moves_with)
        m, cog = data.get("mass"), data.get("cog")
        grp = (data.get("rig") or {}).get("groups") or {}
        if not isinstance(m, dict) or not isinstance(cog, dict):
            self.problem = "the crane's file has no masses and centres of gravity by group"
            return
        for g, mg in m.items():
            c = LR._vec3(cog.get(g))
            if c is None or not LR._number(mg) or float(mg) <= 0:
                continue
            mw = grp.get(g, {}).get("moves_with") if isinstance(grp.get(g), dict) else None
            self.groups.append((g, float(mg) * self.fm, c * self.to_rig, mw if mw in rig.by else None))
        if not self.groups:
            self.problem = "the crane's file has no masses with a centre of gravity"
        role = rig.role
        self.tele = role.get("tele")
        self.tele_boom = rig.by[self.tele].get("rides_on") if self.tele else None
        self.travel = None
        tr = data.get("tracks")
        if isinstance(tr, dict) and tr.get("joint") in rig.by:
            self.travel = tr["joint"]
        self.up = rig.up_axis
        self.outr = data.get("outriggers") if isinstance(data.get("outriggers"), dict) else None
        self.trk = tr if isinstance(tr, dict) else None

    def carrier_values(self, values: dict) -> dict:
        v = dict(values)
        if self.travel:
            v[self.travel] = 0.0
        return v

    def items(self, values: dict, counterweight_kg: float | None, hanging_kg: float) -> list:
        """[(kg, x m, y m)] in the carrier's level frame: every group, and ``hanging_kg`` (load + rigging) plumb under
        the hook."""
        v = self.carrier_values(values)
        rig = self.rig
        out = []
        shift = None
        if self.tele_boom:
            v0 = dict(v)
            lead, _r = rig.leader_of(self.tele)
            v0[lead] = 0.0
            shift = 0.5 * (rig.hook(v) - rig.hook(v0))
        for g, kg, c, mw in self.groups:
            if g == "counterweight" and counterweight_kg is not None:
                kg = float(counterweight_kg)
                if kg <= 0:
                    continue
            p = rig.moved(mw, c, v) if mw else c
            if shift is not None and mw == self.tele_boom:
                p = p + shift
            xy = _flat(self.up, p) * self.rig_m
            out.append((kg, float(xy[0]), float(xy[1])))
        if hanging_kg > 0:
            xy = _flat(self.up, rig.hook(v)) * self.rig_m
            out.append((float(hanging_kg), float(xy[0]), float(xy[1])))
        return out

    # -- the set-up ----------------------------------------------------------------------------------------------
    def jack(self):
        """(the jacks' leader joint, its down end) or None."""
        o = self.outr or {}
        j = o.get("jack_joint")
        if not j or j not in self.rig.by:
            return None
        lim = self.rig.by[j].get("limits")
        if not lim:
            return None
        lo, hi = float(lim[0]), float(lim[1])
        return j, lo, hi


def outrigger_row(items, a: float, b: float, centre, mat, allowable_pa, limits: lifting.Limits,
                  mat_words: str) -> Row:
    """C5 at one moment, in the plan's words."""
    try:
        r = lifting.outriggers(items, a, b, mat=mat, allowable=allowable_pa, centre=centre, limits=limits)
    except ValueError as exc:
        return grey("C5", str(exc).rstrip(".").lower())
    d = r.details
    row = Row("C5", TITLES["C5"], r.status, r.use, amber_at=limits.ground)
    if d.get("reactions") is None:
        row.value = "outside the base"
        row.words = (f"The crane's centre of gravity ({d['x']:.2f}, {d['y']:.2f}) m lies outside its outriggers – "
                     f"red: over entered limit.")
        return row
    names = ("front left", "front right", "rear left", "rear right")
    i = max(range(4), key=lambda k: d["reactions"][k])
    rmax = d["r_max"]
    row.measure = lifting.force_t(rmax)
    row.value = f"{lifting.force_t(rmax):.1f} t"
    lifted = f" One outrigger is unloaded ({names[d['lifted']]} lifts)." if d.get("lifted") is not None else ""
    if d.get("pressure") is None:
        row.limit = "no allowable entered"
        row.words = (f"Outrigger {names[i]} carries {lifting.force_t(rmax):.1f} t – the ground pressure is not "
                     f"checked: enter the allowable ground pressure.")
        if d.get("lifted") is not None:
            row.words += f"{lifted[:-1]} – amber."
        return row
    p = d["pressure"]
    row.value = f"{_kpa(p)} ({lifting.force_t(rmax):.1f} t)"
    row.limit = f"{_kpa(allowable_pa)} entered"
    row.words = (f"Outrigger {names[i]} carries {lifting.force_t(rmax):.1f} t: {_kpa(p)} on {mat_words}, "
                 f"{_pct(r.use)} of the {_kpa(allowable_pa)} entered – {_limit_words(r.status, limits.ground)}."
                 f"{lifted}")
    return row


def tracks_row(items, gauge: float, length: float, width: float, centre, allowable_pa,
               limits: lifting.Limits) -> Row:
    """C6 at one moment."""
    try:
        p, x, y = lifting.resultant(items)
        r = lifting.tracks(p, x - float(centre[0]), y - float(centre[1]), gauge, length, width,
                           allowable=allowable_pa, limits=limits)
    except ValueError as exc:
        return grey("C6", str(exc).rstrip(".").lower())
    row = Row("C6", TITLES["C6"], r.status, r.use, amber_at=limits.ground)
    if not r.details:
        row.value = "outside the tracks"
        row.words = (f"The crane's centre of gravity ({x:.2f}, {y:.2f}) m lies outside its tracks – red: over "
                     "entered limit.")
        return row
    top = max(r.details["p_max"])
    row.measure = lifting.kPa(top)
    row.value = f"{_kpa(top)} ({r.details['shape']})"
    if allowable_pa is None:
        row.limit = "no allowable entered"
        row.words = (f"Largest track pressure {_kpa(top)} – the ground pressure is not checked: enter the allowable "
                     "ground pressure.")
        return row
    row.limit = f"{_kpa(allowable_pa)} entered"
    row.words = (f"Track pressure {_kpa(top)} ({r.details['shape']}), {_pct(r.use)} of the {_kpa(allowable_pa)} "
                 f"entered – {_limit_words(r.status, limits.ground)}.")
    return row


def base_margin(x: float, y: float, a: float, b: float) -> float:
    """The share of the base left between a CoG at (x, y) (from the base's centre) and the nearest edge: 1 in the
    middle, 0 on the edge, below 0 outside."""
    return min(1.0 - abs(x) / a, 1.0 - abs(y) / b)


def backward_row(items, a: float, b: float, centre, cw_kg: float, chart_cw_kg: float,
                 limits: lifting.Limits) -> Row:
    """The unloaded crane (the load set down or lost) with more counterweight than its chart: its CoG must keep
    ``BACK_RESERVE`` of the base inside (the makers' rule for the built-in charts)."""
    row = Row("BACK", TITLES["BACK"], amber_at=limits.crane)
    try:
        _p, x, y = lifting.resultant(items)
    except ValueError as exc:
        return grey("BACK", str(exc).rstrip(".").lower())
    m = base_margin(x - float(centre[0]), y - float(centre[1]), a, b)
    use = (1.0 - m) / (1.0 - BACK_RESERVE)
    row.use = use
    row.measure = 1.0 - m
    row.status = lifting.status_of(use, limits.crane)
    row.value = f"{max(m, 0.0) * 100:.0f} % of the base inside" if m > 0 else "outside the base"
    row.limit = f"at least {BACK_RESERVE * 100:.0f} %"
    row.words = (f"Counterweight {_t(cw_kg)} is more than the chart's {_t(chart_cw_kg)}: without the load the crane's "
                 f"centre of gravity keeps {max(m, 0.0) * 100:.0f} % of its base inside ({BACK_RESERVE * 100:.0f} % "
                 f"needed) – {_limit_words(row.status, limits.crane)}.")
    return row


# ---------------------------------------------------------------------------------------------------------------------
# every check at one moment

@dataclass
class Plan:
    """The plan's numbers the checks need (SI: kg, m, Pa)."""

    load_kg: float = 0.0                 # the load's mass (× contingency below)
    contingency: float = 1.0
    hook_block_kg: float = 0.0
    rigging_kg: float = 0.0
    counterweight_kg: float | None = None
    spread: float | None = None          # the outrigger spread the chart is picked for (m); None = from the pose
    hung: bool = False                   # the load hangs on this crane's hook
    rig_checks: list = field(default_factory=list)   # the hang's checks (lifting_rig.results "checks")
    rig_stale: bool = False
    allowable_pa: float | None = None    # the ground's allowable pressure (entered)
    mat: tuple | None = None             # (w, l) m of a mat under each outrigger pad; None = the pad
    line_pull: object = None             # gross kg -> lifting.Result (C10), or None
    clearance: object = None             # joint values -> Row (task 0349, lifting_zones.Clearance.row), or None
    limits: lifting.Limits = field(default_factory=lambda: lifting.DEFAULT_LIMITS)


class Checks:
    """The checks of one crane and its load at any moment of the path."""

    def __init__(self, data: dict, charts, plan: Plan):
        self.data = data
        self.charts = list(charts or ())
        self.plan = plan
        self.rig = LR.Rig(data)
        self.sup = Supports(self.rig, data)
        # the counterweight the crane carries: the plan's, else the file's own (charts and masses agree)
        self.cw = plan.counterweight_kg
        if self.cw is None:
            g = next((kg for name, kg, _c, _m in self.sup.groups if name == "counterweight"), None)
            self.cw = g

    def setup(self, values: dict) -> dict:
        out = {}
        if self.cw is not None:
            out["counterweight"] = float(self.cw)
        sp = self.plan.spread if self.plan.spread is not None else LR.outrigger_spread(self.data, values)
        if sp is not None:
            out["outriggers"] = float(sp)
        return out

    def hanging_kg(self) -> float:
        p = self.plan
        return max(p.load_kg, 0.0) * max(p.contingency, 0.0) + max(p.rigging_kg, 0.0)

    def at(self, values: dict) -> list:
        p = self.plan
        lim = p.limits
        rows = []
        st = self.setup(values)
        ro = LR.readout(self.rig, values, self.charts, st, load_kg=p.load_kg, contingency=p.contingency,
                        hook_block_kg=p.hook_block_kg, rigging_kg=p.rigging_kg, limits=lim)
        rows.append(self._c1(ro))
        rows.append(self._c10(ro.gross))
        rows += self._supports(values, ro)
        if p.clearance is not None:
            try:
                rows.append(p.clearance(values))
            except Exception as exc:  # noqa: BLE001 - a broken mesh: grey with the reason
                rows.append(grey("CLR", str(exc).rstrip(".").lower()))
        rows += self._rigging()
        return rows

    # -- C1, C10 ---------------------------------------------------------------------------------------------------
    def _c1(self, ro) -> Row:
        lim = self.plan.limits
        row = Row("C1", TITLES["C1"], ro.status, ro.use, amber_at=lim.crane, measure=ro.radius)
        row.value = _t(ro.gross)
        if ro.capacity is not None:
            row.limit = f"{_t(ro.capacity)} at {ro.row:g} m"
            row.words = (f"Crane at {_pct(ro.use)} of its chart at {ro.radius:.1f} m – "
                         f"{_limit_words(ro.status, lim.crane)}.")
        elif ro.status == lifting.NOT_CHECKED:
            row.words = f"Crane use not checked – {ro.reason or ro.words}".rstrip(".") + "."
        else:
            row.limit = "no capacity"
            row.words = f"Crane at {ro.radius:.1f} m: {ro.reason or ro.chart_note}".rstrip(".") + " – red."
        if self.cw is not None and ro.chart is not None:
            cw = ro.chart.config.get("counterweight")
            if LR._number(cw) and float(self.cw) > float(cw) + 1e-6:
                row.words += (f" The crane carries {_t(self.cw)} of counterweight, the chart is for "
                              f"{_t(cw)}: see Backward stability.")
        return row

    def _c10(self, gross: float) -> Row:
        if self.plan.line_pull is None:
            return grey("C10", "the crane's file has no hoist reeving")
        try:
            r = self.plan.line_pull(gross)
        except Exception as exc:  # noqa: BLE001 - a broken file entry: grey with the reason
            return grey("C10", str(exc).rstrip(".").lower())
        lim = self.plan.limits
        row = Row("C10", TITLES["C10"], r.status, r.use, amber_at=lim.crane)
        row.value = _t(r.value)
        falls = int(r.inputs.get("falls", 1))
        if r.limit is None:
            row.limit = "no maximum entered"
            row.words = f"Line pull {_t(r.value)} on {falls} falls – not checked: the winch's maximum is not entered."
        else:
            row.limit = _t(r.limit)
            row.words = (f"Line pull {_t(r.value)} on {falls} falls, {_pct(r.use)} of the winch's {_t(r.limit)} – "
                         f"{_limit_words(r.status, lim.crane)}.")
        return row

    # -- C5 / C6, set-up, backward stability --------------------------------------------------------------------
    def _supports(self, values: dict, ro) -> list:
        sup, p, lim = self.sup, self.plan, self.plan.limits
        out = []
        o, trk = sup.outr, sup.trk
        if o is None and trk is None:
            return [grey("C5", "the crane's file has no outriggers or tracks")]
        cw = self.cw
        if o is not None:
            out.append(self._setup_row(values, ro))
        if sup.problem:
            out.append(grey("C5" if o is not None else "C6", sup.problem))
            out.append(grey("BACK", sup.problem))
            return out
        items = sup.items(values, cw, self.hanging_kg())
        empty = sup.items(values, cw, 0.0)
        if o is not None:
            a = o.get("a")
            sp = LR.outrigger_spread(self.data, values)
            if not LR._number(a) or sp is None:
                out.append(grey("C5", "the crane's file does not give its outrigger base"))
                base = None
            else:
                a, b = float(a) * sup.f_m, sp / 2.0
                centre = tuple(float(x) * sup.f_m for x in (o.get("centre") or (0.0, 0.0)))
                mat = p.mat
                words = f"its {mat[0]:g} × {mat[1]:g} m mat" if mat else None
                if mat is None:
                    pad = o.get("pad")
                    if isinstance(pad, (list, tuple)) and len(pad) == 2 and all(LR._number(x) for x in pad):
                        mat = (float(pad[0]) * sup.f_m, float(pad[1]) * sup.f_m)
                        words = f"its {mat[0]:g} × {mat[1]:g} m pad (no mat entered)"
                out.append(outrigger_row(items, a, b, centre, mat, p.allowable_pa, lim, words or "its pad"))
                base = (a, b, centre)
        else:
            g, L, w = (trk.get(k) for k in ("gauge", "length", "width"))
            if not all(LR._number(x) and float(x) > 0 for x in (g, L, w)):
                out.append(grey("C6", "the crane's file does not give its tracks' gauge, length and width"))
                base = None
            else:
                centre = tuple(float(x) * sup.f_m for x in (trk.get("centre") or (0.0, 0.0)))
                g, L, w = (float(x) * sup.f_m for x in (g, L, w))
                out.append(tracks_row(items, g, L, w, centre, p.allowable_pa, lim))
                base = (L / 2.0, g / 2.0, centre)
        out.append(self._back_row(empty, base, ro))
        return out

    def _setup_row(self, values: dict, ro) -> Row:
        sup, lim = self.sup, self.plan.limits
        row = Row("SETUP", TITLES["SETUP"], lifting.OK)
        problems = []
        sp = LR.outrigger_spread(self.data, values)
        need = ro.chart.config.get("outriggers") if ro.chart is not None else None
        if self.plan.spread is not None and LR._number(self.plan.spread):
            need = max(float(need), float(self.plan.spread)) if LR._number(need) else float(self.plan.spread)
        if sp is not None and LR._number(need) and sp < float(need) - BEAM_TOL:
            problems.append(f"the beams are out to {sp:.2f} m, the chart is for {float(need):g} m")
        jk = sup.jack()
        jack_words = ""
        if jk is not None:
            j, lo, hi = jk
            v = float(self.rig.value_of(j, values))
            down = hi if abs(hi) >= abs(lo) else lo
            if abs(v - down) > JACK_TOL * max(abs(hi - lo), 1e-9):
                problems.append("the jacks are up – the crane stands on its wheels, the chart is for the jacks down")
            else:
                jack_words = ", jacks down"
        else:
            jack_words = " (the file names no jacks)"
        if problems:
            row.status = lifting.RED
            row.value = "not set up"
            row.limit = "as the chart"
            row.words = "Not set up as the chart needs: " + "; ".join(problems) + " – red."
        else:
            row.value = f"{sp:.2f} m" if sp is not None else "–"
            row.limit = f"{float(need):g} m" if LR._number(need) else "–"
            row.words = (f"Set up: beams out to {sp:.2f} m" if sp is not None else "Set up") + jack_words + \
                " – as the chart needs."
        return row

    def _back_row(self, empty, base, ro) -> Row:
        p = self.plan
        cw = self.cw
        chart_cw = ro.chart.config.get("counterweight") if ro.chart is not None else None
        if cw is None or not LR._number(chart_cw) or cw <= float(chart_cw) + 1e-6:
            return grey("BACK", "the crane carries the chart's counterweight: the chart covers its backward "
                                "stability")
        if base is None:
            return grey("BACK", "the crane's base is not in its file")
        a, b, centre = base
        return backward_row(empty, a, b, centre, cw, float(chart_cw), p.limits)

    # -- C2–C4 from the hang ------------------------------------------------------------------------------------
    def _rigging(self) -> list:
        p = self.plan
        if not p.hung:
            return [grey("C2", "the load is not hung on this crane's hook (8 Lifting plan > Rigging > Hang on the "
                               "hook)")]
        out = []
        by: dict = {}                                   # one row per check: the worst of its items (each shackle …)
        for chk in p.rig_checks or []:
            cid = str(chk.get("check", ""))
            for x in chk.get("parts") or [chk]:
                by.setdefault(cid, []).append(dict(x, title=x.get("title") or chk.get("title", cid)))
        for cid, parts in by.items():
            chk = {"title": parts[0]["title"]}
            worst = max(parts, key=lambda x: (RANK.get(x.get("status"), 1),
                                              x.get("use") if x.get("use") is not None else -1.0))
            row = Row(cid, TITLES.get(cid, chk.get("title", cid)), worst.get("status") or lifting.NOT_CHECKED,
                      worst.get("use"), amber_at=p.limits.rigging)
            row.value = _pct(worst["use"]) if worst.get("use") is not None else ""
            row.limit = "WLL"
            what = worst.get("title") or chk.get("title", cid)
            if worst.get("use") is not None:
                row.words = (f"{what}: {_pct(worst['use'])} of its WLL – "
                             f"{_limit_words(row.status, p.limits.rigging)}.")
            else:
                row.words = f"{what}: {(worst.get('message') or worst.get('words') or '').rstrip('.')}."
            if p.rig_stale:
                row.words += " The load or its gear changed since it was hung: Hang on the hook again."
            out.append(row)
        if not out:
            out.append(grey("C2", "the hang has no checks"))
        return out


# ---------------------------------------------------------------------------------------------------------------------
# the worst moment

def worst_of(rows) -> str:
    """The worst status of a moment's rows."""
    return lifting.worst_status(r.status for r in rows) if rows else lifting.NOT_CHECKED


@dataclass
class Found:
    """The search's answer: per check id its worst Row (``t`` set), every moment evaluated (sorted), the count."""

    worst: dict
    moments: list            # [(t, worst status at t)]
    evaluations: int


GOLD = (math.sqrt(5.0) - 1.0) / 2.0


def _golden(f, lo: float, hi: float, rounds: int):
    """Maximise ``f`` (returns a comparable key) on [lo, hi]: the best (key, t) of every point tried."""
    best = None
    a, b = lo, hi
    c = b - GOLD * (b - a)
    d = a + GOLD * (b - a)
    fc, fd = f(c), f(d)
    for kv, tv in ((fc, c), (fd, d)):
        if best is None or kv > best[0]:
            best = (kv, tv)
    for _ in range(rounds):
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - GOLD * (b - a)
            fc = f(c)
            if fc > best[0]:
                best = (fc, c)
        else:
            a, c, fc = c, d, fd
            d = a + GOLD * (b - a)
            fd = f(d)
            if fd > best[0]:
                best = (fd, d)
    return best


def search(at, t0: float, t1: float, keys=(), inner: int = 3, rounds: int = 14, peaks: int = 2,
           step: float | None = None, spacing: float | None = None) -> Found:
    """The worst moment of every check between ``t0`` and ``t1``: ``at(t)`` -> [Row] (one per check id). Evaluated at
    ``keys`` (and the ends), ``inner`` points evenly in each gap, then a golden-section search of ``rounds`` round each
    check's ``peaks`` highest local peaks (between the neighbouring grid points). ``step``: round the moments to it
    (frames: 1/100). ``spacing``: the grid's points at most this far apart (a narrow peak shorter than that can still
    be missed – the reference ``every`` cannot miss one longer than a frame)."""
    if t1 < t0:
        t0, t1 = t1, t0
    cache: dict = {}

    def ev(t):
        t = float(t)
        if step:
            t = round(t / step) * step
        t = min(max(t, t0), t1)
        got = cache.get(t)
        if got is None:
            got = {r.id: r for r in at(t)}
            cache[t] = got
        return t, got

    T = sorted({float(t0), float(t1)} | {float(k) for k in keys if t0 <= k <= t1})
    grid = []
    for a, b in zip(T, T[1:]):
        n = inner + 1
        if spacing:
            n = max(n, int(math.ceil((b - a) / spacing - 1e-9)))
        grid += [a + (b - a) * i / n for i in range(n)]
    grid.append(T[-1])
    grid = sorted({ev(t)[0] for t in grid})
    ids = []
    for t in grid:
        for k in cache[t]:
            if k not in ids:
                ids.append(k)
    worst = {}
    for cid in ids:
        def key(t, cid=cid):
            r = ev(t)[1].get(cid)
            return r.key if r is not None else (-1, -1.0)
        vals = [key(t) for t in grid]
        n = len(grid)
        best_i = max(range(n), key=lambda i: vals[i])
        if all(v == vals[0] for v in vals):
            cands = []                                  # the same all along (rigging, line pull): no search
        else:
            peaks_i = [i for i in range(n) if (i == 0 or vals[i] >= vals[i - 1]) and (i == n - 1 or vals[i] >= vals[i + 1])]
            peaks_i.sort(key=lambda i: vals[i], reverse=True)
            cands = peaks_i[:peaks]
            if best_i not in cands:
                cands.append(best_i)
        best = (vals[best_i], grid[best_i])
        for i in cands:
            lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, n - 1)]
            if hi - lo <= (step or 0.0):
                continue
            got = _golden(lambda t: key(t), lo, hi, rounds)
            if got[0] > best[0]:
                best = got
        t = ev(best[1])[0]
        r = ev(t)[1][cid]
        row = Row(**{k: getattr(r, k) for k in ("id", "title", "status", "use", "value", "limit", "words",
                                                 "amber_at", "measure")})
        row.t = t
        worst[cid] = row
    moments = sorted((t, worst_of(list(rows.values()))) for t, rows in cache.items())
    return Found(worst, moments, len(cache))


def every(at, times) -> Found:
    """The reference: every moment in ``times`` (frames), each check's worst of them."""
    worst: dict = {}
    moments = []
    for t in times:
        rows = at(float(t))
        moments.append((float(t), worst_of(rows)))
        for r in rows:
            w = worst.get(r.id)
            if w is None or r.key > w.key:
                c = Row(**{k: getattr(r, k) for k in ("id", "title", "status", "use", "value", "limit", "words",
                                                       "amber_at", "measure")})
                c.t = float(t)
                worst[r.id] = c
    return Found(worst, moments, len(moments))


def ordered(worst: dict) -> list:
    """The rows in the table's order."""
    return sorted(worst.values(), key=lambda r: (ORDER.index(r.id) if r.id in ORDER else len(ORDER), r.id))


def worst_so_far(moments, t: float) -> str:
    """The worst status of the moments up to ``t`` (the data box)."""
    s = [st for tt, st in moments if tt <= t + 1e-9]
    return lifting.worst_status(s) if s else lifting.NOT_CHECKED


# ---------------------------------------------------------------------------------------------------------------------
# proposed steps

SPEEDS = {"hoist": 300.0, "slew": 4.0, "luff": 2.0, "second": 2.0, "tele": 250.0, "travel": 300.0}   # mm/s, °/s
MIN_S, MAX_S = 2.0, 20.0


@dataclass
class Step:
    kind: str                      # hoist / slew / luff / travel / lower
    label: str
    values: dict                   # joint (file name) -> value at the step's end (deg / mm)
    seconds: float
    easing: str = "SMOOTH"         # the animation step's motion (SMOOTH, LINEAR, EASE_IN, EASE_OUT)


@dataclass
class Proposal:
    ok: bool
    steps: list = field(default_factory=list)
    reason: str = ""
    notes: list = field(default_factory=list)
    end: dict = field(default_factory=dict)       # the joints' values at the end


SUB = 6                            # a luff / telescope move in this many pieces: the hook keeps its height (± a few cm)
STRAIGHT_MM = 10.0                 # a set-down point this close (level) to the hook: only the hoist moves


def _seconds(rig: LR.Rig, before: dict, after: dict) -> float:
    s = MIN_S
    roles = {v: k for k, v in rig.role.items()}
    for n, v in after.items():
        role = roles.get(n, "travel")
        sp = SPEEDS.get(role, SPEEDS["hoist"])
        s = max(s, abs(float(v) - float(before.get(n, 0.0))) / sp)
    return round(min(s, MAX_S), 1)


def _hoist_for(rig: LR.Rig, values: dict, z: float) -> float:
    """The hoist value that puts the hook at height ``z`` (mm along the up axis) with the other joints as given."""
    hoist = rig.role["hoist"]
    v0 = dict(values)
    v0[hoist] = 0.0
    up = rig.up
    dz = -float(rig.hook_dir(v0) @ up)
    return (float(rig.hook(v0) @ up) - z) / max(dz, 0.5)


def _travel_for(rig: LR.Rig, data: dict, values: dict, target, radius_mm: float):
    """A crawler's travel that brings the slew axis within ``radius_mm`` (level) of the target, as little as it can:
    None when the crane has no travel joint."""
    tr = data.get("tracks")
    j = tr.get("joint") if isinstance(tr, dict) else None
    if not j or j not in rig.by or rig.by[j]["kind"] != "SLIDE" or rig.by[j].get("follows"):
        return None
    d = rig.axis(j, values)
    d = d - (d @ rig.up) * rig.up
    if np.linalg.norm(d) < 1e-9:
        return None
    d = d / np.linalg.norm(d)
    c = rig.slew_centre(values)
    v = np.asarray(target, float) - c
    v = v - (v @ rig.up) * rig.up
    along = float(v @ d)
    side2 = float(v @ v) - along * along
    now = float(values.get(j, 0.0))
    if side2 > radius_mm * radius_mm:
        t = along                                       # the closest it gets: straight beside the target
    else:
        h = math.sqrt(radius_mm * radius_mm - side2)
        t = min((along - h, along + h), key=abs)
    lo, hi = rig.limits(j)
    return j, min(max(now + t, lo), hi)


def propose(rig: LR.Rig, data: dict, values: dict, target, clearance_mm: float = 2000.0, charts=(),
            setup: dict | None = None, load_kg: float = 0.0, hook_block_kg: float = 0.0) -> Proposal:
    """Steps from the hook where it is (the pick) to ``target`` (model frame, mm: where the hook ends). The hook goes
    up ``clearance_mm`` above the higher of the two first (the boom helps when the hoist is at its top) and keeps that
    height while the crane slews, luffs and telescopes (in ``SUB`` pieces) and travels, then lowers. A target straight
    below or above the hook: the hoist only."""
    cur = {k: float(v) for k, v in values.items()}
    T = np.asarray(target, float)
    up = rig.up
    hoist = rig.role["hoist"]
    lo, hi = rig.solve_range(hoist)
    pick = rig.hook(cur)
    h0 = float(pick @ up)
    zt = float(T @ up)
    notes = []
    if -float(rig.hook_dir(cur) @ up) < 0.5:
        return Proposal(False, reason="The hoist does not lower the hook (its direction does not point down).")
    level = (T - pick) - float((T - pick) @ up) * up
    if float(np.linalg.norm(level)) < STRAIGHT_MM:          # straight down (or up): the hoist only
        v = _hoist_for(rig, cur, zt)
        if not lo - 1e-6 <= v <= hi + 1e-6:
            return Proposal(False, reason="The hoist cannot reach the set-down point straight "
                                          + ("above" if v < lo else "below") + " the hook.")
        nxt = {hoist: v}
        st = Step("lower" if zt < h0 else "hoist", "Lower" if zt < h0 else "Hoist", nxt, _seconds(rig, cur, nxt))
        now = dict(cur, **nxt)
        return Proposal(True, [st] if abs(v - cur.get(hoist, 0.0)) > 1.0 else [], "", notes, now)
    z_clear = max(h0, zt) + max(float(clearance_mm), 0.0)
    steps = []
    now = dict(cur)
    # 1. hoist clear (the boom raises the rest when the hoist is at its top)
    v_up = _hoist_for(rig, now, z_clear)
    if v_up >= lo - 1e-6:
        if abs(v_up - now.get(hoist, 0.0)) > 1.0:
            nxt = {hoist: v_up}
            steps.append(Step("hoist", "Hoist clear", nxt, _seconds(rig, now, nxt)))
            now.update(nxt)
    else:
        a0 = LR.hook_to(rig, pick + (z_clear - h0) * up, now, charts, setup, load_kg=load_kg,
                        hook_block_kg=hook_block_kg)
        if a0.ok:
            nxt = {n: v for n, v in a0.values.items() if abs(v - now.get(n, 0.0)) > 1e-3}
            notes.append("The hoist is near its top: the boom raises the load clear.")
        else:
            z_clear = h0 + (now.get(hoist, 0.0) - lo) * -float(rig.hook_dir(now) @ up)
            notes.append(f"The hook goes up only {(z_clear - h0) / 1000.0:.2f} m: the hoist is at its top.")
            nxt = {hoist: lo}
        if nxt:
            steps.append(Step("hoist", "Hoist clear", nxt, _seconds(rig, now, nxt)))
            now.update(nxt)
    # 2. where the hook goes, at the clearance height
    T_clear = T + (z_clear - zt) * up
    a = LR.hook_to(rig, T_clear, now, charts, setup, load_kg=load_kg, hook_block_kg=hook_block_kg)
    travel = None
    if not a.ok:
        r_pick, _z = rig.radius_height(now)
        got = _travel_for(rig, data, now, T_clear, r_pick * 1000.0)
        if got is not None and abs(got[1] - now.get(got[0], 0.0)) > 1.0:
            q = dict(now)
            q[got[0]] = got[1]
            a2 = LR.hook_to(rig, T_clear, q, charts, setup, load_kg=load_kg, hook_block_kg=hook_block_kg)
            if a2.ok:
                a, travel = a2, got
                notes.append(f"The crane travels {(got[1] - now.get(got[0], 0.0)) / 1000.0:+.2f} m on its tracks to "
                             "reach the set-down point.")
        if not a.ok:
            return Proposal(False, reason=a.reason, notes=notes)
    role = rig.role
    slew = role["slew"]
    vals = a.values
    if abs(vals.get(slew, now.get(slew, 0.0)) - now.get(slew, 0.0)) > 0.05:
        nxt = {slew: vals[slew]}
        steps.append(Step("slew", "Slew", nxt, _seconds(rig, now, nxt)))
        now.update(nxt)
    # 3. luff / telescope in pieces, the hoist keeping the hook at the clearance height
    boom = {}
    for r in ("luff", "second", "tele"):
        n = role.get(r)
        if n and n in vals and abs(vals[n] - now.get(n, 0.0)) > 1e-3:
            boom[n] = vals[n]
    words = "Luff / telescope" if "tele" in role else ("Luff / fold" if "second" in role else "Luff")
    if boom:
        total = _seconds(rig, now, dict(boom, **({hoist: vals[hoist]} if hoist in vals else {})))
        start = dict(now)
        for k in range(1, SUB + 1):
            f = k / SUB
            nxt = {n: start.get(n, 0.0) + f * (v - start.get(n, 0.0)) for n, v in boom.items()}
            q = dict(now, **nxt)
            hv = vals[hoist] if k == SUB and hoist in vals else _hoist_for(rig, q, z_clear)
            nxt[hoist] = min(max(hv, lo), hi)
            ease = "EASE_IN" if k == 1 else ("EASE_OUT" if k == SUB else "LINEAR")
            steps.append(Step("luff", words, nxt, round(max(total / SUB, 0.3), 2), ease))
            now.update(nxt)
    elif hoist in vals and abs(vals[hoist] - now.get(hoist, 0.0)) > 1.0:
        nxt = {hoist: vals[hoist]}
        steps.append(Step("luff", words, nxt, _seconds(rig, now, nxt)))
        now.update(nxt)
    if travel is not None:
        nxt = {travel[0]: travel[1]}
        steps.append(Step("travel", "Travel", nxt, _seconds(rig, now, nxt)))
        now.update(nxt)
    # 4. lower onto the set-down point
    v_down = _hoist_for(rig, now, zt)
    if v_down > hi + 1e-6:
        dz2 = -float(rig.hook_dir(now) @ up)
        return Proposal(False, reason=f"The hook cannot go down to the set-down point: the hoist runs out "
                                      f"{(v_down - hi) * dz2 / 1000.0:.2f} m above it.", notes=notes)
    if abs(v_down - now.get(hoist, 0.0)) > 1.0:
        nxt = {hoist: v_down}
        steps.append(Step("lower", "Lower", nxt, _seconds(rig, now, nxt)))
        now.update(nxt)
    err = float(np.linalg.norm(rig.hook(now) - T))
    if err > 50.0:
        notes.append(f"The hook ends {err:.0f} mm from the set-down point (the hoist hangs a little off plumb).")
    return Proposal(True, steps, a.reason, notes, now)
