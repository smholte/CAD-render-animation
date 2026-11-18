"""Hook to here and the crane's readout (task 0201, Lifting lane L4) – plain Python, no Blender.

A placed crane is rigged from its equipment file (``rig``: joints in the model frame, mm and degrees, as the render-kit
sheet writes them; ``limits``; ``charts``). This module

* works out where the hook is for joint values (``Rig.hook``: the app's joint rules – a joint that ``rides_on``
  another moves with it, a follower takes ``ratio`` x its leader – the same as ``lifting_model/classes.hook_point``),
* finds joint values that put the hook on a point (``hook_to``): slew, then the boom in its plane – luff and telescope
  (mobile), luff (crawler) and the luffing jib, main boom + knuckle + extensions (knuckle-boom) – and the hoist, so
  the hook hangs plumb on the point, inside every joint's limits. Among several answers the one with the lowest crane
  use on the chart that applies, then the shortest boom. Out of reach: by how much (radius or height),
* picks the chart for the crane's set-up (``chart_for``): only combinations the file has; an in-between counterweight
  or outrigger spread takes the next safer chart (less counterweight, narrower spread) and says why,
* gives the live readout (``readout``): radius, hook height, boom length and angle, the chart row (next longer
  radius), capacity, gross load, crane use with the status word (``lifting.crane_use``).

The joints are found by their names in the built-in cranes (``ROLES``): "Slew", "Luff", "Telescope", "Jib", "Main
boom", "Knuckle", "Extension", "Hoist". The boom moves in one vertical plane through the slew axis; the hook hangs
plumb (the hook-swing joints follow the boom's turns with ratio -1). Units inside: mm and degrees (the rig's), kg for
masses; the readout gives metres and kg.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import lifting

ROLES = {
    "mobile_crane": {"slew": "Slew", "luff": "Luff", "tele": "Telescope", "hoist": "Hoist"},
    "crawler_crane": {"slew": "Slew", "luff": "Luff", "second": "Jib", "hoist": "Hoist"},
    "knuckle_boom_crane": {"slew": "Slew", "luff": "Main boom", "second": "Knuckle", "tele": "Extension",
                           "hoist": "Hoist"},
}
NEEDED = ("slew", "luff", "hoist")
TOL = 1e-6           # degrees / mm: limits are met within this
CHECK_MM = 1.0       # the 3-D kinematics must put the hook this close to the target, else the answer is refused


class ReachError(ValueError):
    """The crane's file cannot be used by Hook to here (the message says why, in plain words)."""


# ---------------------------------------------------------------------------------------------------------------------
# kinematics (mm, degrees)

def _rot(axis, deg: float) -> np.ndarray:
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def _about(point, axis, deg: float) -> np.ndarray:
    p = np.asarray(point, float)
    R = _rot(axis, deg)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = p - R @ p
    return M


def _along(axis, dist: float) -> np.ndarray:
    a = np.asarray(axis, float)
    M = np.eye(4)
    M[:3, 3] = a / np.linalg.norm(a) * dist
    return M


def _r2(v, psi: float):
    c, s = math.cos(psi), math.sin(psi)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def _wrap_into(deg: float, lim, near: float | None = None) -> float | None:
    """``deg`` + k x 360 inside ``lim`` (the one nearest ``near``), or None."""
    lo, hi = lim
    best = None
    for k in range(-3, 4):
        v = deg + 360.0 * k
        if lo - TOL <= v <= hi + TOL:
            if best is None or abs(v - (near if near is not None else 0.0)) < abs(best - (near or 0.0)):
                best = v
    return None if best is None else min(max(best, lo), hi)


class Rig:
    """A crane's joints from its equipment file (``data``: the whole file as read, ``rig`` inside)."""

    def __init__(self, data: dict):
        self.data = data
        rig = data.get("rig") or {}
        self.kind = str(data.get("kind", ""))
        self.joints = list(rig.get("joints") or [])
        self.by = {j["name"]: j for j in self.joints}
        self.role = {}
        for role, name in ROLES.get(self.kind, {}).items():
            if name in self.by:
                self.role[role] = name
        missing = [ROLES.get(self.kind, {}).get(r, r) for r in NEEDED if r not in self.role]
        if self.kind not in ROLES:
            raise ReachError(f"Hook to here knows mobile, crawler and knuckle-boom cranes, not '{self.kind}'.")
        if missing:
            raise ReachError("The crane's file has no joint named " + ", ".join(f"'{m}'" for m in missing)
                             + ": Hook to here needs them.")
        hook = rig.get("hook") or {}
        if "point" not in hook:
            raise ReachError("The crane's file does not say where the hook is (rig > hook > point).")
        self.hook_cad = np.asarray(hook["point"], float)
        lim = data.get("limits") or {}
        self.limits_data = lim
        luff = self.by[self.role["luff"]]
        ang = lim.get("boom_angle") or lim.get("main_boom_angle")
        self.th0 = float(ang[0]) - float(luff["limits"][0]) if ang and luff.get("limits") else 0.0
        self.second_cad = 0.0
        if "second" in self.role:
            sj = self.by[self.role["second"]]
            rel = lim.get("jib_angle_to_boom") or lim.get("knuckle_angle")
            self.second_cad = float(rel[0]) - float(sj["limits"][0]) if rel and sj.get("limits") else 0.0
        self.model_boom = lim.get("model_boom")
        self.model_jib = lim.get("model_jib")
        self.jib_boom_angle = lim.get("jib_charts_boom_angle")
        self._planar = None

    # -- joint values ---------------------------------------------------------------------------------------------
    def name(self, role: str) -> str | None:
        return self.role.get(role)

    def driven(self) -> list:
        """The joints a user drives (not followers)."""
        return [j for j in self.joints if not j.get("follows")]

    def value_of(self, name: str, given: dict) -> float:
        j = self.by[name]
        if j.get("follows"):
            return float(j["ratio"]) * self.value_of(j["follows"], given)
        return float(given.get(name, 0.0))

    def chain(self, name: str) -> list:
        """The joint and those it rides on, from the bottom up."""
        out = []
        while name:
            out.append(name)
            name = self.by[name].get("rides_on")
        return out[::-1]

    def motion(self, name: str, given: dict) -> np.ndarray:
        """4 x 4 world motion (mm, model frame) of what the joint moves, relative to the CAD pose."""
        M = np.eye(4)
        for n in self.chain(name):
            j = self.by[n]
            v = self.value_of(n, given)
            M = M @ (_about(j["point"], j["direction"], v) if j["kind"] == "ROTATE" else _along(j["direction"], v))
        return M

    def hook(self, given: dict) -> np.ndarray:
        """The hook's point in the model frame (mm)."""
        return (self.motion(self.role["hoist"], given) @ np.r_[self.hook_cad, 1.0])[:3]

    def point(self, name: str, given: dict) -> np.ndarray:
        """A joint's axis point now (moved by what it rides on)."""
        j = self.by[name]
        base = self.motion(j["rides_on"], given) if j.get("rides_on") else np.eye(4)
        return (base @ np.r_[np.asarray(j["point"], float), 1.0])[:3]

    def slew_centre(self, given: dict) -> np.ndarray:
        return self.point(self.role["slew"], given)

    def radius_height(self, given: dict) -> tuple[float, float]:
        """(radius from the slew axis, hook height above the model's ground) in m."""
        p = self.hook(given)
        c = self.slew_centre(given)
        return float(math.hypot(p[0] - c[0], p[1] - c[1]) / 1000.0), float(p[2] / 1000.0)

    def boom_length(self, given: dict) -> float:
        """The boom length the charts mean (m): a crawler's model boom; else pivot -> (knuckle ->) head sheave."""
        if self.model_boom:
            return float(self.model_boom)
        pl = self.planar()
        e = self.value_of(self.role["tele"], given) if "tele" in self.role else 0.0
        v = pl.V0 + e * pl.w
        return round(float((np.linalg.norm(pl.P2 - pl.P1) + np.linalg.norm(v)) / 1000.0), 4)   # 0.1 mm: no float
        # noise past a chart's boom length (15.350000016 m would take the next longer chart)

    def boom_angle(self, given: dict) -> float:
        """The (main) boom's angle above horizontal, degrees."""
        return self.th0 + self.value_of(self.role["luff"], given)

    def second_angle(self, given: dict) -> float | None:
        """The jib's / outer boom's angle to the main boom's line, degrees (None: the crane has none)."""
        if "second" not in self.role:
            return None
        return self.second_cad + self.value_of(self.role["second"], given)

    def jib_length(self) -> float | None:
        return float(self.model_jib) if self.model_jib else None

    def limits(self, name: str):
        lim = self.by[name].get("limits")
        return (float(lim[0]), float(lim[1])) if lim else (-1e9, 1e9)

    # -- the boom in its plane ------------------------------------------------------------------------------------
    def planar(self) -> "Planar":
        if self._planar is None:
            self._planar = Planar(self)
        return self._planar


@dataclass
class Planar:
    """The boom in its vertical plane (x, z of the model frame at slew 0, below-slew joints at 0):

        sheave = P1 + R(s1 a1) [ (P2 - P1) + R(s2 a2) [ V0 + e w ] ],   hook (hoist 0) = sheave + h

    a1 = the luff / main boom value, a2 = the jib / knuckle value (P2 = P1 when there is none), e = the telescope /
    extension value (w = how far the sheave moves per mm of it, followers included)."""

    rig: Rig
    P1: np.ndarray = None
    P2: np.ndarray = None
    V0: np.ndarray = None
    w: np.ndarray = None
    h: np.ndarray = None
    s1: float = 1.0
    s2: float = 1.0
    cx: float = 0.0

    def __post_init__(self):
        r = self.rig
        zero: dict = {}
        luff = r.by[r.role["luff"]]
        slew = r.by[r.role["slew"]]
        hoist = r.by[r.role["hoist"]]
        d = np.asarray(slew["direction"], float)
        if abs(abs(d[2]) / np.linalg.norm(d) - 1.0) > 1e-6:
            raise ReachError("The slew joint does not turn about a vertical axis: Hook to here cannot work it out.")
        sp = np.asarray(slew["point"], float)
        self.cx, cy = float(sp[0]), float(sp[1])

        def xz(p):
            if abs(p[1] - cy) > 1.0:
                raise ReachError("The boom does not move in a plane through the slew axis: Hook to here cannot work "
                                 "it out.")
            return np.array([p[0], p[2]], float)

        def sign(j):
            dd = np.asarray(j["direction"], float)
            dd = dd / np.linalg.norm(dd)
            if j["kind"] != "ROTATE" or abs(abs(dd[1]) - 1.0) > 1e-6:
                raise ReachError(f"The joint '{j['name']}' does not turn about a level axis across the boom.")
            return -float(np.sign(dd[1]))

        self.s1 = sign(luff)
        self.P1 = xz(np.asarray(luff["point"], float))
        if "second" in r.role:
            sj = r.by[r.role["second"]]
            self.s2 = sign(sj)
            self.P2 = xz(np.asarray(sj["point"], float))
        else:
            self.P2 = self.P1.copy()
        S0 = xz(r.point(r.role["hoist"], zero))
        self.V0 = S0 - self.P2
        self.h = xz(r.hook_cad) - xz(np.asarray(hoist["point"], float))
        self.w = np.zeros(2)
        if "tele" in r.role:
            lo, hi = r.limits(r.role["tele"])
            span = hi if hi > 0 else 1000.0
            S1 = xz(r.point(r.role["hoist"], {r.role["tele"]: span}))
            self.w = (S1 - S0) / span
            Sm = xz(r.point(r.role["hoist"], {r.role["tele"]: span / 2}))
            if np.linalg.norm(Sm - (S0 + self.w * span / 2)) > 0.01:
                raise ReachError("The telescope does not move the boom head in a straight line.")

    def sheave(self, a1: float, a2: float = 0.0, e: float = 0.0) -> np.ndarray:
        inner = _r2(self.V0 + e * self.w, math.radians(self.s2 * a2))
        v = _r2((self.P2[0] - self.P1[0] + inner[0], self.P2[1] - self.P1[1] + inner[1]), math.radians(self.s1 * a1))
        return np.array([self.P1[0] + v[0], self.P1[1] + v[1]])

    def hook0(self, a1: float, a2: float = 0.0, e: float = 0.0) -> np.ndarray:
        return self.sheave(a1, a2, e) + self.h

    def boom_m(self, e: float) -> float:
        if self.rig.model_boom:
            return float(self.rig.model_boom)
        return round(float((np.linalg.norm(self.P2 - self.P1) + np.linalg.norm(self.V0 + e * self.w)) / 1000.0), 4)


# ---------------------------------------------------------------------------------------------------------------------
# charts for a set-up

SETUP_KEYS = ("counterweight", "outriggers")          # chosen by the user; the boom (and a crawler's jib) by the pose
SETUP_WORDS = {"counterweight": "counterweight", "outriggers": "outrigger spread"}


def setup_values(charts) -> dict:
    """{config key: sorted values the charts have} for the keys a user sets (counterweight in kg, spread in m)."""
    out: dict = {}
    for c in charts:
        for k in SETUP_KEYS:
            v = c.config.get(k)
            if isinstance(v, (int, float)) and math.isfinite(v):
                out.setdefault(k, set()).add(float(v))
    return {k: sorted(v) for k, v in out.items()}


def _shown(key: str, v: float) -> str:
    return f"{lifting.tonnes(v):g} t" if key == "counterweight" else f"{v:g} m"


def _close(a, b) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def chart_for(charts, boom: float | None, setup: dict | None = None, jib: float | None = None):
    """(chart or None, sentence) for a boom length (m), the user's set-up ({"counterweight": kg, "outriggers": m};
    a key left out or None = the smallest the charts have) and a crawler's jib (m, None = main boom charts).

    Only combinations the file has. An in-between counterweight or spread takes the next lower one (the next safer
    chart); a combination the file does not have steps the counterweight down, then the spread, and says so."""
    charts = list(charts)
    if not charts:
        return None, "The crane's file has no load chart."
    setup = dict(setup or {})
    vals = setup_values(charts)
    notes = []
    config = {}
    for k in SETUP_KEYS:
        if k not in vals:
            continue
        have = vals[k]
        v = setup.get(k)
        if v is None:
            config[k] = have[0]
            continue
        v = float(v)
        hit = next((x for x in have if _close(x, v)), None)
        if hit is None:
            lower = [x for x in have if x < v]
            if not lower:
                return None, (f"No chart for a {SETUP_WORDS[k]} of {_shown(k, v)} or less (the charts start at "
                              f"{_shown(k, have[0])}).")
            hit = lower[-1]
            notes.append(f"the {SETUP_WORDS[k]} {_shown(k, v)} lies between the charts' values: the "
                         f"{_shown(k, hit)} chart is the next safer one")
        config[k] = hit
    has_jib = any(c.config.get("jib") is not None for c in charts)
    jib_cfg = {}
    if has_jib:
        jib_cfg = {"jib": None}
    if jib is not None:
        jibs = sorted({c.config["jib"] for c in charts if isinstance(c.config.get("jib"), (int, float))})
        longer = [x for x in jibs if x >= jib - 1e-6]
        if not longer:
            return None, f"No chart for a jib of {jib:g} m or longer."
        jib_cfg = {"jib": longer[0]}
        if not _close(longer[0], jib):
            notes.append(f"the next longer jib {longer[0]:g} m")
    tries = [dict(config)]
    # a combination the file does not have: step the counterweight down, then the spread
    for k in ("counterweight", "outriggers"):
        if k in config:
            for x in reversed([x for x in vals[k] if x < config[k]]):
                t = dict(tries[-1])
                t[k] = x
                tries.append(t)
    for i, cfg in enumerate(tries):
        chart, why = lifting.pick_chart(charts, boom=boom, **cfg, **jib_cfg)
        if chart is not None:
            if i:
                changed = [f"{SETUP_WORDS[k]} {_shown(k, cfg[k])}" for k in cfg if not _close(cfg[k], config[k])]
                notes.append("the file has no chart for the set-up as chosen: using " + ", ".join(changed)
                             + " (the next safer one)")
            if why != "Chart found.":
                notes.append(why.rstrip(".").replace("Using ", "", 1))
            text = "Chart: " + (chart.name or "unnamed")
            if notes:
                text += ". " + "; ".join(notes)[0].upper() + "; ".join(notes)[1:] + "."
            return chart, text
    _c, why = lifting.pick_chart(charts, boom=boom, **config, **jib_cfg)
    return None, why


def outrigger_spread(data: dict, values: dict) -> float | None:
    """The outrigger / stabiliser spread across (m) the pose gives, from the file's ``outriggers`` block
    (b = b_in + stages x value; spread = 2 b), or None."""
    o = data.get("outriggers") or {}
    j = o.get("joint")
    if not j or "b_in" not in o:
        return None
    v = float(values.get(j, 0.0)) / 1000.0
    return 2.0 * (float(o["b_in"]) + float(o.get("stages", 1)) * v)


# ---------------------------------------------------------------------------------------------------------------------
# Hook to here

@dataclass
class Answer:
    ok: bool
    values: dict = field(default_factory=dict)   # joint name -> value (deg / mm) to set; empty when not ok
    reason: str = ""                             # out of reach: by how much; else what was chosen
    radius: float = 0.0                          # m
    height: float = 0.0                          # m (hook)
    boom: float = 0.0                            # m
    chart: object = None
    chart_note: str = ""
    use: float | None = None
    error_mm: float = 0.0                        # the 3-D kinematics' hook against the target
    candidates: int = 0


def _single(P, V, s, lim, X):
    """Turn V (from P) about P by a in ``lim`` so the end's x is X: [(a, end)] and, when none, (kind, by mm)."""
    rho = math.hypot(V[0], V[1])
    if rho < 1e-9:
        return [], ("far", 0.0)
    gam = math.atan2(V[1], V[0])
    out = []
    c = (X - P[0]) / rho
    if -1.0 <= c <= 1.0:
        a = math.acos(c)
        for psi in (a - gam, -a - gam):
            deg = _wrap_into(math.degrees(psi) / s, lim)
            if deg is not None:
                end = (P[0] + rho * math.cos(gam + math.radians(s * deg)), P[1] + rho * math.sin(gam + math.radians(s * deg)))
                if abs(end[0] - X) < 1e-3:
                    out.append((deg, np.array(end)))
    if out:
        return out, None
    xs = [P[0] + rho * math.cos(gam + math.radians(s * a)) for a in np.linspace(lim[0], lim[1], 721)]
    if X > max(xs):
        return [], ("far", X - max(xs))
    if X < min(xs):
        return [], ("close", min(xs) - X)
    return [], ("limits", 0.0)


class _Search:
    def __init__(self, rig: Rig, X: float, Z: float):
        self.rig, self.pl, self.X, self.Z = rig, rig.planar(), X, Z
        self.hoist_lim = rig.limits(rig.role["hoist"])
        self.fails: list = []

    def hoist_ok(self, hook0_z: float):
        hv = hook0_z - self.Z
        lo, hi = self.hoist_lim
        if hv < lo - TOL:
            self.fails.append(("high", lo - hv))
            return None
        if hv > hi + TOL:
            self.fails.append(("low", hv - hi))
            return None
        return min(max(hv, lo), hi)

    # one rotation (luff; the jib with the boom at a fixed angle)
    def at(self, e: float = 0.0, a1: float | None = None):
        pl, r = self.pl, self.rig
        lim1 = r.limits(r.role["luff"])
        Xs = self.X - pl.h[0]
        if a1 is None:                                         # the boom alone turns
            V = (pl.P2 - pl.P1) + (pl.V0 + e * pl.w)
            sols, fail = _single(pl.P1, V, pl.s1, lim1, Xs)
            if fail:
                self.fails.append(fail)
            out = []
            for a, end in sols:
                hv = self.hoist_ok(end[1] + pl.h[1])
                if hv is not None:
                    out.append({"a1": a, "a2": 0.0, "e": e, "hoist": hv})
            return out
        P2 = pl.P1 + np.array(_r2(pl.P2 - pl.P1, math.radians(pl.s1 * a1)))
        V = np.array(_r2(pl.V0 + e * pl.w, math.radians(pl.s1 * a1)))
        lim2 = r.limits(r.role["second"])
        sols, fail = _single(P2, V, pl.s2, lim2, Xs)
        if fail:
            self.fails.append(fail)
        out = []
        for a, end in sols:
            hv = self.hoist_ok(end[1] + pl.h[1])
            if hv is not None:
                out.append({"a1": a1, "a2": a, "e": e, "hoist": hv})
        return out

    # two rotations + free height (knuckle-boom): the lowest hook rope that reaches
    def two(self, e: float):
        pl, r = self.pl, self.rig
        lim1, lim2 = r.limits(r.role["luff"]), r.limits(r.role["second"])
        lo, hi = self.hoist_lim
        Xs = self.X - pl.h[0]
        l1v = pl.P2 - pl.P1
        l2v = pl.V0 + e * pl.w
        l1, l2 = float(np.linalg.norm(l1v)), float(np.linalg.norm(l2v))
        al1, al2 = math.atan2(l1v[1], l1v[0]), math.atan2(l2v[1], l2v[0])

        def ik(hv):
            Zs = self.Z + hv - pl.h[1]
            dx, dz = Xs - pl.P1[0], Zs - pl.P1[1]
            D2 = dx * dx + dz * dz
            cb = (D2 - l1 * l1 - l2 * l2) / (2 * l1 * l2)
            if cb > 1.0 or cb < -1.0:
                return None, ("far" if cb > 1.0 else "close")
            res = []
            for b in (math.acos(cb), -math.acos(cb)):
                base = math.atan2(dz, dx) - math.atan2(l2 * math.sin(b), l1 + l2 * math.cos(b))
                psi1 = base - al1
                psi2 = b - (al2 - al1)
                a1 = _wrap_into(math.degrees(psi1) / pl.s1, lim1)
                a2 = _wrap_into(math.degrees(psi2) / pl.s2, lim2)
                if a1 is not None and a2 is not None:
                    S = pl.sheave(a1, a2, e)
                    if abs(S[0] - Xs) < 0.01 and abs(S[1] - (self.Z + hv - pl.h[1])) < 0.01:
                        res.append({"a1": a1, "a2": a2, "e": e, "hoist": hv})
            return (res or None), ("limits" if not res else None)

        grid = np.linspace(lo, hi, 401)
        prev = None
        for hv in grid:
            sol, _why = ik(float(hv))
            if sol:
                if prev is None:
                    return sol[:1]
                a, b = prev, float(hv)                         # the lowest rope that reaches: between a and b
                for _ in range(40):
                    m = 0.5 * (a + b)
                    s2, _w = ik(m)
                    if s2:
                        b, sol = m, s2
                    else:
                        a = m
                return sol[:1]
            prev = float(hv)
        return []


def _candidates_e(rig: Rig, charts) -> list:
    """Telescope / extension values worth trying: a fine grid and every chart's boom length."""
    if "tele" not in rig.role:
        return [0.0]
    lo, hi = rig.limits(rig.role["tele"])
    es = [float(x) for x in np.linspace(lo, hi, 61)]
    pl = rig.planar()
    L0, L1 = pl.boom_m(lo), pl.boom_m(hi)
    for c in charts or ():
        b = c.config.get("boom")
        if isinstance(b, (int, float)) and L0 - 1e-6 <= b <= L1 + 1e-6 and L1 > L0:
            es.append(lo + (hi - lo) * (b - L0) / (L1 - L0))
    return sorted(set(round(e, 6) for e in es))


def _words_fail(fails, rig: Rig) -> str:
    if not fails:
        return "Out of reach within the joints' limits."
    by = {}
    for kind, d in fails:
        by[kind] = min(by.get(kind, 1e18), d)
    if "far" in by and not any(k in by for k in ("high", "low")):
        return f"Out of reach: {by['far'] / 1000:.2f} m further out than the hook reaches."
    if "close" in by and not any(k in by for k in ("high", "low", "far")):
        return f"Out of reach: {by['close'] / 1000:.2f} m closer to the slew axis than the hook reaches."
    if "high" in by:
        return f"Out of reach: {by['high'] / 1000:.2f} m higher than the hook reaches at this radius."
    if "low" in by:
        return f"Out of reach: {by['low'] / 1000:.2f} m lower than the hoist rope reaches."
    if "far" in by:
        return f"Out of reach: {by['far'] / 1000:.2f} m further out than the hook reaches."
    return "Out of reach within the joints' limits."


def _diagnose(rig: Rig, X: float, Z: float) -> str:
    """Why a point is out of reach, from the hook's places over a grid of the boom's joints (two turning joints:
    no closed form for the whole reach)."""
    pl = rig.planar()
    lim1 = rig.limits(rig.role["luff"])
    lim2 = rig.limits(rig.role["second"]) if "second" in rig.role else (0.0, 0.0)
    lime = rig.limits(rig.role["tele"]) if "tele" in rig.role else (0.0, 0.0)
    a1 = np.radians(pl.s1 * np.linspace(*lim1, 121))[:, None, None]
    a2 = np.radians(pl.s2 * np.linspace(*lim2, 121 if "second" in rig.role else 1))[None, :, None]
    e = np.linspace(*lime, 9 if "tele" in rig.role else 1)[None, None, :]
    vx, vz = pl.V0[0] + e * pl.w[0], pl.V0[1] + e * pl.w[1]
    ix, iz = vx * np.cos(a2) - vz * np.sin(a2), vx * np.sin(a2) + vz * np.cos(a2)
    ux, uz = pl.P2[0] - pl.P1[0] + ix, pl.P2[1] - pl.P1[1] + iz
    hx = pl.P1[0] + ux * np.cos(a1) - uz * np.sin(a1) + pl.h[0]
    hz = pl.P1[1] + ux * np.sin(a1) + uz * np.cos(a1) + pl.h[1]
    r = (hx - pl.cx).ravel()
    z = hz.ravel()
    rt = X - pl.cx
    if rt > r.max():
        return f"Out of reach: about {(rt - r.max()) / 1000:.2f} m further out than the hook reaches."
    if rt < r.min():
        return f"Out of reach: about {(r.min() - rt) / 1000:.2f} m closer to the slew axis than the hook reaches."
    band = np.abs(r - rt) < max(100.0, 0.01 * (r.max() - r.min()))
    lo, hi = rig.limits(rig.role["hoist"])
    if band.any():
        zmax, zmin = z[band].max() - lo, z[band].min() - hi
        if Z > zmax:
            return f"Out of reach: about {(Z - zmax) / 1000:.2f} m higher than the hook reaches at this radius."
        if Z < zmin:
            return f"Out of reach: about {(zmin - Z) / 1000:.2f} m lower than the hoist rope reaches."
    return "Out of reach within the joints' limits."


def hook_to(rig: Rig, target, current: dict | None = None, charts=(), setup: dict | None = None,
            load_kg: float = 0.0, hook_block_kg: float = 0.0) -> Answer:
    """Joint values that put the hook (hanging plumb) on ``target`` (model frame, mm). ``current``: the joints' values
    now (deg / mm; a crawler's travel stays). Among several answers the lowest crane use on the chart that applies
    (``chart_for`` with ``setup``; gross = load + hook block unless the chart includes it), then the shortest boom.
    Out of reach: ``ok`` False and the reason (by how much)."""
    current = dict(current or {})
    T = np.asarray(target, float)
    slew = rig.by[rig.role["slew"]]
    keep = {k: v for k, v in current.items() if k not in rig.role.values()}
    base = rig.motion(slew["rides_on"], keep) if slew.get("rides_on") else np.eye(4)
    Tb = (np.linalg.inv(base) @ np.r_[T, 1.0])[:3]
    sp = np.asarray(slew["point"], float)
    dx, dy = Tb[0] - sp[0], Tb[1] - sp[1]
    R = math.hypot(dx, dy)
    sz = float(np.sign(slew["direction"][2]))
    cur_slew = float(current.get(rig.role["slew"], 0.0))
    if R < 1.0:
        slew_v = cur_slew
    else:
        slew_v = _wrap_into(math.degrees(math.atan2(dy, dx)) * sz, rig.limits(rig.role["slew"]), near=cur_slew)
        if slew_v is None:
            return Answer(False, reason="Out of reach: the point lies outside the slew range.")
    pl = rig.planar()
    X, Z = pl.cx + R, float(Tb[2])
    search = _Search(rig, X, Z)
    sols = []
    es = _candidates_e(rig, charts)
    if "second" in rig.role and "tele" not in rig.role:          # crawler with a luffing jib
        lim1 = rig.limits(rig.role["luff"])
        pref = (rig.jib_boom_angle - rig.th0) if rig.jib_boom_angle is not None else 0.5 * (lim1[0] + lim1[1])
        pref = min(max(pref, lim1[0]), lim1[1])
        order = sorted(np.arange(lim1[0], lim1[1] + 1e-9, 0.5).tolist() + [pref], key=lambda a: abs(a - pref))
        for a1 in order:
            sols = search.at(0.0, a1=float(a1))
            if sols:
                break
    elif "second" in rig.role:                                   # knuckle-boom
        for e in es:
            sols += search.two(e)
    else:
        for e in es:
            sols += search.at(e)
    if not sols:
        why = _diagnose(rig, X, Z) if "second" in rig.role else _words_fail(search.fails, rig)
        return Answer(False, reason=why, radius=R / 1000.0, height=Z / 1000.0)
    # the shortest boom of each chart bracket: refine the shortest telescope that reaches
    if "tele" in rig.role and len(es) > 1:
        e_ok = sorted({s["e"] for s in sols})
        first = e_ok[0]
        below = [e for e in es if e < first]
        if below:
            a, b = below[-1], first
            for _ in range(40):
                m = 0.5 * (a + b)
                got = search.two(m) if "second" in rig.role else search.at(m)
                if got:
                    b = m
                    sols += got
                else:
                    a = m
    best, best_key = None, None
    for s in sols:
        boom = pl.boom_m(s["e"])
        chart, note = chart_for(charts, boom, setup, rig.jib_length()) if charts else (None, "")
        use, cap = None, None
        if chart is not None:
            r = lifting.crane_use(load_kg, R / 1000.0, chart, hook_block=hook_block_kg)
            use, cap = r.use, r.limit
        # no chart / no capacity last; then the lowest use (with no load: the largest capacity); the shortest boom
        key = (0 if cap else 1, use if use is not None else math.inf, -(cap or 0.0), round(boom, 6), s["hoist"])
        if best_key is None or key < best_key:
            best, best_key = (s, boom, chart, note, use), key
    s, boom, chart, note, use = best
    vals = {rig.role["slew"]: slew_v, rig.role["luff"]: s["a1"], rig.role["hoist"]: s["hoist"]}
    if "second" in rig.role:
        vals[rig.role["second"]] = s["a2"]
    if "tele" in rig.role:
        vals[rig.role["tele"]] = s["e"]
    full = dict(keep)
    full.update(vals)
    err = float(np.linalg.norm(rig.hook(full) - T))
    bad = [n for n in rig.chain(rig.role["hoist"]) if rig.by[n].get("limits")
           and not (rig.limits(n)[0] - 1e-3 <= rig.value_of(n, full) <= rig.limits(n)[1] + 1e-3)]
    if err > CHECK_MM or bad:
        return Answer(False, reason="Hook to here found no answer inside the joints' limits"
                      + (f" ({', '.join(bad)})" if bad else f" (the hook would be {err:.1f} mm off)") + ".",
                      radius=R / 1000.0, height=Z / 1000.0)
    return Answer(True, values=vals, reason="", radius=R / 1000.0, height=Z / 1000.0, boom=boom, chart=chart,
                  chart_note=note, use=use, error_mm=err, candidates=len(sols))


# ---------------------------------------------------------------------------------------------------------------------
# the live readout

@dataclass
class Readout:
    radius: float = 0.0          # m, slew axis -> hook, horizontal
    height: float = 0.0          # m, hook above the crane's ground
    boom: float = 0.0            # m
    boom_angle: float = 0.0      # deg
    second_angle: float | None = None
    jib: float | None = None     # m (crawler's luffing jib)
    chart: object = None
    chart_note: str = ""
    row: float | None = None     # m, the chart row used (next longer radius)
    capacity: float | None = None  # kg
    load: float = 0.0            # kg, load x contingency
    hook_block: float = 0.0      # kg, added (0 when the chart includes it)
    rigging: float = 0.0         # kg (0 until rigging comes, L5)
    gross: float = 0.0           # kg
    use: float | None = None
    status: str = lifting.NOT_CHECKED
    words: str = lifting.STATUS_WORDS[lifting.NOT_CHECKED]
    reason: str = ""
    sample: bool = False
    result: object = None


def readout(rig: Rig, values: dict, charts=(), setup: dict | None = None, load_kg: float = 0.0,
            contingency: float = 1.0, hook_block_kg: float = 0.0, rigging_kg: float = 0.0,
            limits: lifting.Limits = lifting.DEFAULT_LIMITS) -> Readout:
    """What the panel shows for the crane's pose: geometry, chart, capacity, gross load and crane use."""
    r, z = rig.radius_height(values)
    out = Readout(radius=r, height=z, boom=rig.boom_length(values), boom_angle=rig.boom_angle(values),
                  second_angle=rig.second_angle(values), jib=rig.jib_length())
    out.load = max(0.0, load_kg) * max(contingency, 0.0)
    out.rigging = rigging_kg
    chart, note = chart_for(charts, out.boom, setup, out.jib)
    out.chart, out.chart_note = chart, note
    if chart is None:
        out.status, out.words = lifting.RED, lifting.STATUS_WORDS[lifting.RED]
        out.reason = note
        out.hook_block = hook_block_kg
        out.gross = out.load + rigging_kg + hook_block_kg
        return out
    out.sample = bool(chart.sample)
    res = lifting.crane_use(out.load, r, chart, rigging=rigging_kg, hook_block=hook_block_kg, limits=limits)
    out.result = res
    out.hook_block = 0.0 if chart.includes_hook_block else hook_block_kg
    out.gross = float(res.value or 0.0)
    out.capacity = res.details.get("capacity")
    out.row = res.details.get("row_radius")
    out.use = res.use
    out.status, out.words = res.status, res.words
    if out.capacity is None:
        out.reason = f"No capacity here: {res.details.get('reason', '')}."
    return out
