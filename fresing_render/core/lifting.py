"""Lifting plans (task 0182, Lifting lane L1): the checks C1–C10 (C10: task 0232), the load chart and the words – plain Python.

Study 0180 section 3 has the formulas and the worked cases the tests use; section 8 the words. No Blender, no NumPy:
every later Lifting task (equipment library, cranes, rigging, the lift path, the printed plan) calls these.

Units inside are SI: masses in kg (loads, chart capacities, WLLs, forklift ratings, static and dynamic hook loads),
lengths in m, forces in N, pressures in Pa; angles are degrees at the interface. A WLL or a chart capacity is a *mass*
rating: a force F in N is compared with it as F / (wll · G). Tonnes, kN and kPa only at the edges (``tonnes``,
``kN``, ``kPa``, the messages).

Every check returns a :class:`Result`: its inputs, the formula's name, value, limit, use, a status
(``ok`` / ``amber`` / ``red`` / ``not_checked``), the status words and one plain sentence, so a panel and the printed
plan can show how it was worked out. The app checks the data entered in the plan, never the real crane, ground or
load: the words say "within the entered limits", never that a lift may go ahead (section 8).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, is_dataclass

# ---------------------------------------------------------------------------------------------------------------------
# Units

G = 9.80665  # m/s², standard gravity: kg -> N
MASS_UNITS = {"kg": 1.0, "t": 1000.0, "lb": 0.45359237}
LENGTH_UNITS = {"m": 1.0, "mm": 0.001, "ft": 0.3048}
EPS = 1e-9


def kg(t: float) -> float:
    """Tonnes -> kg."""
    return t * 1000.0


def tonnes(mass_kg: float) -> float:
    """kg -> tonnes."""
    return mass_kg / 1000.0


def newton(mass_kg: float) -> float:
    """The weight of a mass: kg -> N."""
    return mass_kg * G


def force_t(force_n: float) -> float:
    """A force as the tonnes that weigh as much: N -> t."""
    return force_n / G / 1000.0


def kN(force_n: float) -> float:
    return force_n / 1000.0


def kPa(pressure_pa: float) -> float:
    return pressure_pa / 1000.0


def _mass_factor(unit: str) -> float:
    if unit not in MASS_UNITS:
        raise ValueError(f"Unknown mass unit {unit!r}: use one of {', '.join(MASS_UNITS)}.")
    return MASS_UNITS[unit]


def _length_factor(unit: str) -> float:
    if unit not in LENGTH_UNITS:
        raise ValueError(f"Unknown length unit {unit!r}: use one of {', '.join(LENGTH_UNITS)}.")
    return LENGTH_UNITS[unit]


def _t(mass_kg: float) -> str:
    return f"{mass_kg / 1000.0:,.2f} t"


def _ft(force_n: float) -> str:
    return f"{force_t(force_n):,.2f} t ({kN(force_n):,.1f} kN)"


def _pa(pressure: float) -> str:
    return f"{kPa(pressure):,.1f} kPa"


def _pct(use: float | None) -> str:
    return "–" if use is None else f"{use * 100.0:.1f} %"


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ---------------------------------------------------------------------------------------------------------------------
# Status, limits, words

OK, AMBER, RED, NOT_CHECKED = "ok", "amber", "red", "not_checked"
STATUS_WORDS = {
    OK: "Within entered limits",
    AMBER: "Near entered limit",
    RED: "Over entered limit",
    NOT_CHECKED: "Not checked",
}
_RANK = {OK: 0, NOT_CHECKED: 1, AMBER: 2, RED: 3}

PLANNING_AID = (
    "Planning aid only. Fresing Render checks this plan against the data entered in it, not against the real "
    "equipment, ground or load. The plan must be checked and approved by a competent person (for example the "
    "appointed person or lift director) before any lift."
)
SAMPLE_MARK = (
    "SAMPLE – not for real lifts. Invented values to show how the app works. Enter the chart of your real crane."
)
SAMPLE_PAGE_MARK = "SAMPLE DATA – NOT FOR REAL LIFTS"
NOT_CHECKED_BY_APP = "not checked by Fresing Render – competent person"
# Words the app never uses about a plan (section 8). The planning-aid line above is the one place "approved" appears:
# it says a competent person approves the plan, never the app.
FORBIDDEN_WORDS = ("safe", "approved", "certified", "compliant", "OK to lift", "passed")
# What the app does not check: shown grey with NOT_CHECKED_BY_APP (study 0180 section 3).
NOT_DONE = (
    "Soil bearing capacity and slopes",
    "Strength of mats, padeyes, lifting lugs, beams and the load's structure",
    "The crane's own stability, and a reduced wind speed for a large wind area",
    "Load sharing in tandem lifts beyond rigid statics",
    "Splash-zone and subsea loads",
    "Dynamic analysis of vessel motion",
    "Lifting of people",
    "Certificates and inspection dates (the plan can hold the dates, not judge them)",
)
# The study's "Leaves out" column, printed with each check.
LEAVES_OUT = {
    "C1": "Boom deflection (the radius must be the loaded radius), side load, wind above the chart's wind area.",
    "C2": "Sling stretch; hitch reduction (choke 0.8 etc.) comes from the sling's own data.",
    "C3": "Load flexibility; equalisers (switch 'equalised' when they are fitted).",
    "C4": "Side load on shackles is only flagged (leg more than 5° out of the bow plane).",
    "C5": "Soil capacity, mat bending and shear, deflection; the crane maker's software beats this estimate.",
    "C6": "Track and mat stiffness, soil.",
    "C7": "Attachments (their weight and offset need the maker's re-rating).",
    "C8": "The current DNV-ST-N001 edition's values (to be checked), dynamic analysis.",
    "C9": "Hinge and gripper structure, pile ovalisation, dynamics.",
    "C10": "The rope's own weight, acceleration, the drum's layers and fleet angle; the rope's strength and wear.",
}


@dataclass
class Limits:
    """The planner's amber limits (owner, 17 Nov 2026; changeable per plan): green below, amber up to 100 %, red above.

    ``crane``: the equipment's own rating (C1 crane use, C7 forklift, C8, C9); ``rigging``: slings, shackles,
    spreaders (C2–C4); ``ground``: outrigger mats and crawler tracks (C5, C6).
    """

    crane: float = 0.75
    rigging: float = 0.90
    ground: float = 0.90


DEFAULT_LIMITS = Limits()


def status_of(use: float | None, amber_at: float) -> str:
    """The status of a use (a fraction): None -> not checked; above 1 -> red; from ``amber_at`` up to 1 -> amber."""
    if use is None or not _finite(use):
        return NOT_CHECKED
    u = round(use, 9)
    if u > 1.0:
        return RED
    if u >= round(amber_at, 9):
        return AMBER
    return OK


def worst_status(statuses) -> str:
    """The worst of several: red > amber > not checked > ok (none -> ok)."""
    out = OK
    for s in statuses:
        if _RANK[s] > _RANK[out]:
            out = s
    return out


@dataclass
class Result:
    """One check's answer, with everything the panel and the printed plan show of how it was worked out."""

    check: str
    title: str
    formula: str
    inputs: dict = field(default_factory=dict)
    value: float | None = None
    limit: float | None = None
    use: float | None = None
    amber_at: float = 0.0
    status: str = NOT_CHECKED
    words: str = STATUS_WORDS[NOT_CHECKED]
    message: str = ""
    details: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    leaves_out: str = ""

    def to_dict(self) -> dict:
        return _plain(self)


def _plain(x):
    if is_dataclass(x) and not isinstance(x, type):
        return {k: _plain(v) for k, v in asdict(x).items()}
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def _result(check, title, formula, inputs, value=None, limit=None, use=None, amber_at=0.0, parts=(),
            floor=OK, details=None, notes=None, what="") -> Result:
    """Build a Result; its status is the worst of its own use, its parts and ``floor``.

    A Result with parts and no use of its own takes its parts' statuses (and their largest use)."""
    parts = list(parts)
    if use is None and parts:
        uses = [p.use for p in parts if p.use is not None]
        use = max(uses) if uses else None
        statuses = [p.status for p in parts]
    else:
        statuses = [status_of(use, amber_at)] + [p.status for p in parts]
    status = worst_status(statuses + [floor])
    r = Result(check=check, title=title, formula=formula, inputs=dict(inputs), value=value, limit=limit, use=use,
               amber_at=amber_at, status=status, words=STATUS_WORDS[status], details=dict(details or {}),
               notes=list(notes or []), parts=parts, leaves_out=LEAVES_OUT.get(check, ""))
    r.message = f"{what} – {_pct(use)} – {r.words.lower()}." if use is not None else f"{what} – {r.words.lower()}."
    return r


def worst(results) -> int | None:
    """Index of the worst Result in a list (status, then use): the worst moment of a lift path. Empty -> None."""
    best, key = None, None
    for i, r in enumerate(results):
        k = (_RANK[r.status], r.use if r.use is not None else -1.0)
        if key is None or k > key:
            best, key = i, k
    return best


# ---------------------------------------------------------------------------------------------------------------------
# Lift categories (owner 17 Nov 2026: BS 7121 by default, ASME P30.1 selectable)

CATEGORY_SYSTEMS = {
    "BS 7121": ("basic", "intermediate", "complex"),
    "ASME P30.1": ("standard", "critical"),
}
DEFAULT_CATEGORY_SYSTEM = "BS 7121"


def suggest_category(system: str = DEFAULT_CATEGORY_SYSTEM, cranes: int = 1, people: bool = False,
                     crane_use: float | None = None, crane_limit: float = 0.75, offshore: bool = False,
                     pick_and_carry: bool = False) -> tuple[str, list[str]]:
    """A suggested lift category and why; the planner sets the category, this only suggests one.

    BS 7121: several cranes or people carried -> complex; use above the limit, offshore or pick-and-carry ->
    intermediate; else basic. ASME P30.1: several cranes, people, use above the limit or offshore -> critical;
    else standard."""
    if system not in CATEGORY_SYSTEMS:
        raise ValueError(f"Unknown lift category system {system!r}: use one of {', '.join(CATEGORY_SYSTEMS)}.")
    over = crane_use is not None and crane_use > crane_limit
    heavy, middle = [], []
    if cranes > 1:
        heavy.append(f"{cranes} cranes")
    if people:
        heavy.append("people carried")
    if over:
        middle.append(f"crane use {_pct(crane_use)} above the limit {_pct(crane_limit)}")
    if offshore:
        middle.append("offshore")
    if pick_and_carry and system == "BS 7121":
        middle.append("pick and carry")
    if system == "BS 7121":
        if heavy:
            return "complex", heavy + middle
        if middle:
            return "intermediate", middle
        return "basic", ["known load, one crane, no special hazards entered"]
    if heavy or middle:
        return "critical", heavy + middle
    return "standard", ["one crane, crane use within the limit, onshore"]


# ---------------------------------------------------------------------------------------------------------------------
# Load charts

_CONFIG_LENGTHS = ("boom", "jib", "outriggers")
_CONFIG_MASSES = ("counterweight",)


@dataclass
class Chart:
    """One configuration's load chart: radii (m, strictly rising) and capacities (kg; None = a gap, not allowed).

    ``interpolate`` is stored for later and never used: the owner chose the next longer radius (17 Nov 2026)."""

    radius: list
    capacity: list
    config: dict = field(default_factory=dict)
    name: str = ""
    includes_hook_block: bool = False
    interpolate: bool = False
    wind_max: float | None = None
    sample: bool = False


def chart_from_dict(d: dict, mass_unit: str = "t", length_unit: str = "m") -> Chart:
    """A chart from the equipment file's form, converted to kg and m."""
    fm, fl = _mass_factor(mass_unit), _length_factor(length_unit)
    config = {}
    for k, v in dict(d.get("config", {})).items():
        if k in _CONFIG_LENGTHS and _finite(v):
            v = v * fl
        elif k in _CONFIG_MASSES and _finite(v):
            v = v * fm
        config[k] = v
    return Chart(
        radius=[r * fl if _finite(r) else r for r in d.get("radius", [])],
        capacity=[None if c is None else (c * fm if _finite(c) else c) for c in d.get("capacity", [])],
        config=config, name=str(d.get("name", "")), includes_hook_block=bool(d.get("includes_hook_block", False)),
        interpolate=bool(d.get("interpolate", False)), wind_max=d.get("wind_max"), sample=bool(d.get("sample", False)))


def chart_to_dict(chart: Chart, mass_unit: str = "t", length_unit: str = "m") -> dict:
    """The chart in the equipment file's form, in the given units."""
    fm, fl = _mass_factor(mass_unit), _length_factor(length_unit)
    config = {}
    for k, v in chart.config.items():
        if k in _CONFIG_LENGTHS and _finite(v):
            v = v / fl
        elif k in _CONFIG_MASSES and _finite(v):
            v = v / fm
        config[k] = v
    return {
        "name": chart.name, "config": config,
        "radius": [r / fl for r in chart.radius],
        "capacity": [None if c is None else c / fm for c in chart.capacity],
        "includes_hook_block": chart.includes_hook_block, "interpolate": chart.interpolate,
        "wind_max": chart.wind_max, "sample": chart.sample,
    }


def _chart_label(chart: Chart) -> str:
    if chart.name:
        return chart.name
    if chart.config:
        return ", ".join(f"{k} {v}" for k, v in sorted(chart.config.items()))
    return "the chart"


def validate_chart(chart: Chart) -> tuple[list[str], list[str]]:
    """The chart's errors (refused) and warnings, as plain sentences."""
    errors, warnings = [], []
    label = _chart_label(chart)
    radius, capacity = list(chart.radius), list(chart.capacity)
    if not radius:
        errors.append(f"{label}: the chart has no rows.")
        return errors, warnings
    if len(radius) != len(capacity):
        errors.append(f"{label}: {len(radius)} radii but {len(capacity)} capacities.")
        return errors, warnings
    for i, r in enumerate(radius):
        if not _finite(r) or r <= 0:
            errors.append(f"{label}: row {i + 1}: the radius must be a number above 0.")
    if not errors:
        for i in range(1, len(radius)):
            if radius[i] <= radius[i - 1]:
                errors.append(f"{label}: row {i + 1}: radii must rise from row to row "
                              f"({radius[i]:g} m after {radius[i - 1]:g} m).")
    for i, c in enumerate(capacity):
        if c is None:
            continue
        if not _finite(c) or c <= 0:
            errors.append(f"{label}: row {i + 1}: the capacity must be a number above 0 (leave a gap empty).")
    if not errors:
        prev = None
        for i, c in enumerate(capacity):
            if c is None:
                continue
            if prev is not None and c > prev[1]:
                errors.append(f"{label}: row {i + 1}: the capacity rises with the radius "
                              f"({_t(c)} at {radius[i]:g} m after {_t(prev[1])} at {radius[prev[0]]:g} m).")
            prev = (i, c)
    if chart.interpolate:
        warnings.append(f"{label}: interpolation is not offered: the next longer radius is used.")
    return errors, warnings


def _config_key(config: dict, leave_out: str | None = None):
    return tuple(sorted((k, v) for k, v in config.items() if k != leave_out))


def _same_rows(a: Chart, b: Chart):
    """(radius, capacity a, capacity b) at the radii both charts list, gaps left out."""
    out = []
    for i, r in enumerate(a.radius):
        for j, s in enumerate(b.radius):
            if abs(r - s) <= EPS and a.capacity[i] is not None and b.capacity[j] is not None:
                out.append((r, a.capacity[i], b.capacity[j]))
    return out


def validate_charts(charts) -> tuple[list[str], list[str]]:
    """Every chart's own errors and warnings, plus those between configurations (Hs columns, boom lengths)."""
    errors, warnings = [], []
    charts = list(charts)
    for c in charts:
        e, w = validate_chart(c)
        errors += e
        warnings += w
    seen = {}
    for c in charts:
        key = _config_key(c.config)
        if key in seen:
            errors.append(f"Two charts have the same configuration ({_chart_label(c)}).")
        seen[key] = c
    for i, a in enumerate(charts):
        for b in charts[i + 1:]:
            for what in ("hs", "boom"):
                va, vb = a.config.get(what), b.config.get(what)
                if not (_finite(va) and _finite(vb)) or va == vb:
                    continue
                if _config_key(a.config, what) != _config_key(b.config, what):
                    continue
                lo, hi = (a, b) if va < vb else (b, a)
                for r, c_lo, c_hi in _same_rows(lo, hi):
                    if c_hi > c_lo + EPS:
                        if what == "hs":
                            errors.append(f"At {r:g} m the column for Hs {hi.config['hs']:g} m holds more "
                                          f"({_t(c_hi)}) than the calmer Hs {lo.config['hs']:g} m ({_t(c_lo)}).")
                        else:
                            warnings.append(f"At {r:g} m the {hi.config['boom']:g} m boom holds more ({_t(c_hi)}) "
                                            f"than the {lo.config['boom']:g} m boom ({_t(c_lo)}): check the entry.")
                        break
    return errors, warnings


@dataclass
class Lookup:
    capacity: float | None  # kg, None = no capacity here
    row_radius: float | None  # m, the chart row used
    reason: str


def lookup(chart: Chart, radius: float) -> Lookup:
    """The capacity at a radius: the chart's next longer radius, never interpolated (owner, 17 Nov 2026).

    Past the last row, shorter than the first row, or on a gap: no capacity, with the reason."""
    if not _finite(radius) or radius < 0:
        raise ValueError("The radius must be a number of 0 m or more.")
    errors, _ = validate_chart(chart)
    if errors:
        return Lookup(None, None, errors[0])
    if radius < chart.radius[0] - EPS:
        return Lookup(None, None, f"closer than the chart's shortest radius ({chart.radius[0]:g} m)")
    for r, c in zip(chart.radius, chart.capacity):
        if r >= radius - EPS:
            if c is None:
                return Lookup(None, r, f"not allowed here (gap in the chart at {r:g} m)")
            return Lookup(c, r, f"next longer radius {r:g} m" if r > radius + EPS else f"chart row {r:g} m")
    return Lookup(None, None, f"outside the chart (its longest radius is {chart.radius[-1]:g} m)")


def capacity_interpolated(chart: Chart, radius: float) -> float | None:
    """Linear interpolation between the two rows round a radius (kg). Kept for later: no check uses it and the
    app does not offer it (owner, 17 Nov 2026: the next longer radius)."""
    errors, _ = validate_chart(chart)
    if errors or not _finite(radius):
        return None
    rs, cs = chart.radius, chart.capacity
    if radius < rs[0] - EPS or radius > rs[-1] + EPS:
        return None
    for i in range(len(rs)):
        if abs(rs[i] - radius) <= EPS:
            return cs[i]
        if i and rs[i - 1] < radius < rs[i]:
            if cs[i - 1] is None or cs[i] is None:
                return None
            f = (radius - rs[i - 1]) / (rs[i] - rs[i - 1])
            return cs[i - 1] + (cs[i] - cs[i - 1]) * f
    return None


def _same_value(a, b) -> bool:
    if _finite(a) and _finite(b):
        return abs(a - b) <= EPS * max(1.0, abs(a), abs(b))
    return a == b


def pick_chart(charts, boom: float | None = None, hs: float | None = None, **config) -> tuple[Chart | None, str]:
    """The chart to use: every given config key equal; the next longer boom; the next higher Hs column."""
    cands = [c for c in charts if all(_same_value(c.config.get(k), v) for k, v in config.items())]
    if not cands:
        return None, "No chart for this configuration."
    notes = []
    if boom is not None:
        cands = [c for c in cands if _finite(c.config.get("boom")) and c.config["boom"] >= boom - EPS]
        if not cands:
            return None, f"No chart for a boom of {boom:g} m or longer."
        b = min(c.config["boom"] for c in cands)
        cands = [c for c in cands if _same_value(c.config["boom"], b)]
        if b > boom + EPS:
            notes.append(f"the next longer boom {b:g} m")
    if hs is not None:
        cands = [c for c in cands if _finite(c.config.get("hs")) and c.config["hs"] >= hs - EPS]
        if not cands:
            return None, f"No chart for Hs {hs:g} m or higher."
        h = min(c.config["hs"] for c in cands)
        cands = [c for c in cands if _same_value(c.config["hs"], h)]
        if h > hs + EPS:
            notes.append(f"the next higher Hs column {h:g} m")
    if len(cands) > 1:
        return None, "Several charts fit: give the boom, Hs or other configuration."
    return cands[0], ("Using " + " and ".join(notes) + ".") if notes else "Chart found."


# ---------------------------------------------------------------------------------------------------------------------
# C1 – crane use

WIND_AREA_PER_T = 1.2  # m² per t of load: above it the chart's wind speed does not hold (study 0180, [S37])


def crane_use(load: float, radius: float, chart: Chart, rigging: float = 0.0, hook_block: float = 0.0,
              daf: float = 1.0, wind_area: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C1: gross = load + rigging + hook block (unless the chart includes it) × DAF; use = gross / the chart's
    capacity at the next longer radius. An Hs-rated chart (``hs`` in its config) gets no DAF (no double count)."""
    notes = []
    block = 0.0 if chart.includes_hook_block else hook_block
    if chart.includes_hook_block and hook_block:
        notes.append("The chart includes the hook block: its mass is not added.")
    applied = daf
    if _finite(chart.config.get("hs")) and daf != 1.0:
        applied = 1.0
        notes.append("The chart is for a wave height (Hs column): no DAF on the crane use (no double count).")
    gross = (load + rigging + block) * applied
    lk = lookup(chart, radius)
    if wind_area is not None and load > 0 and wind_area / tonnes(load) > WIND_AREA_PER_T:
        notes.append(f"Wind area {wind_area / tonnes(load):.2f} m²/t is above {WIND_AREA_PER_T} m²/t: the chart's wind "
                     f"speed does not hold – {NOT_CHECKED_BY_APP}.")
    inputs = dict(load=load, rigging=rigging, hook_block=hook_block, radius=radius, daf=daf,
                  chart=_chart_label(chart), wind_area=wind_area)
    details = dict(gross=gross, capacity=lk.capacity, row_radius=lk.row_radius, daf_applied=applied, reason=lk.reason)
    formula = "gross load / chart capacity at the next longer radius"
    if lk.capacity is None:
        r = _result("C1", "Crane use", formula, inputs, value=gross, details=details, notes=notes, floor=RED,
                    what=f"Gross load {_t(gross)} at {radius:.2f} m: no capacity – {lk.reason}")
        return r
    use = gross / lk.capacity
    return _result("C1", "Crane use", formula, inputs, value=gross, limit=lk.capacity, use=use,
                   amber_at=limits.crane, details=details, notes=notes,
                   what=f"Gross load {_t(gross)} at {radius:.2f} m: chart {_t(lk.capacity)} ({lk.reason})")


# ---------------------------------------------------------------------------------------------------------------------
# C4 – WLL use of one item

MAX_LEG_ANGLE = 60.0  # degrees to vertical: above it a sling leg is not rated
SIDE_LOAD_ANGLE = 5.0  # degrees out of a shackle's bow plane: flagged


def _cap(item: str) -> str:
    """'sling leg A' -> 'Sling leg A' (str.capitalize would write 'Sling leg a')."""
    return item[:1].upper() + item[1:]


def wll_use(force: float, wll: float | None, item: str = "sling", angle: float | None = None, mode_factor: float = 1.0,
            side_angle: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C4: use = force / (WLL × mode factor · g); a leg more than 60° from vertical is red; a shackle loaded more
    than 5° out of its bow plane gets a note. No WLL entered -> not checked."""
    notes = []
    floor = OK
    if wll is not None and (not _finite(wll) or wll <= 0):
        raise ValueError("The WLL must be a number above 0.")
    if angle is not None and angle > MAX_LEG_ANGLE + EPS:
        floor = RED
        notes.append(f"The leg is {angle:.1f}° from vertical: above {MAX_LEG_ANGLE:g}° it is not rated.")
    if side_angle is not None and side_angle > SIDE_LOAD_ANGLE + EPS:
        notes.append(f"Side load: {side_angle:.1f}° out of the bow plane – use the shackle maker's reduction "
                     f"({NOT_CHECKED_BY_APP}).")
    inputs = dict(force=force, wll=wll, item=item, angle=angle, mode_factor=mode_factor, side_angle=side_angle)
    if wll is None:
        return _result("C4", f"{_cap(item)} WLL", "force / (WLL × mode factor)", inputs, value=force,
                       amber_at=limits.rigging, floor=floor, notes=notes,
                       what=f"{_cap(item)}: {_ft(force)}, no WLL entered")
    rating = wll * mode_factor
    use = force / (rating * G)
    what = f"{_cap(item)}: {_ft(force)} on a WLL of {_t(rating)}"
    if mode_factor != 1.0:
        what += f" ({_t(wll)} × mode factor {mode_factor:g})"
    return _result("C4", f"{_cap(item)} WLL", "force / (WLL × mode factor)", inputs, value=force,
                   limit=rating, use=use, amber_at=limits.rigging, floor=floor, notes=notes, what=what)


# ---------------------------------------------------------------------------------------------------------------------
# C2 / C3 – sling legs

def _vec(p) -> tuple[float, float, float]:
    x, y, z = (float(v) for v in p)
    return x, y, z


def _leg(point, hook):
    px, py, pz = _vec(point)
    hx, hy, hz = _vec(hook)
    dx, dy, dz = hx - px, hy - py, hz - pz
    if dz <= EPS:
        raise ValueError("The hook must be above every lift point.")
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    angle = math.degrees(math.atan2(math.hypot(dx, dy), dz))
    return (dx, dy, dz), length, dz, angle


def two_leg(weight: float, point_a, point_b, hook, leg_wll: float | None = None,
            shackle_wll: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C2: the two legs of a sling to one hook. Statics in the vertical plane through A and B:
    T_A·u_A + T_B·u_B = W·g·z (for a hook straight above the CoG: V_A = W·b/(a+b), T = V·L/h)."""
    (ax, ay, az), (bx, by, bz) = _vec(point_a), _vec(point_b)
    ex, ey = bx - ax, by - ay
    span = math.hypot(ex, ey)
    if span <= EPS:
        raise ValueError("The two lift points must lie apart in plan.")
    ex, ey = ex / span, ey / span
    legs = [_leg(point_a, hook), _leg(point_b, hook)]
    # In-plane parts of the unit leg directions: along A->B and up.
    (va, la, ha, anga), (vb, lb, hb, angb) = legs
    a_d, a_z = (va[0] * ex + va[1] * ey) / la, va[2] / la
    b_d, b_z = (vb[0] * ex + vb[1] * ey) / lb, vb[2] / lb
    w = weight * G
    det = a_d * b_z - b_d * a_z
    if abs(det) <= EPS:
        raise ValueError("The two legs lie on one line: no answer.")
    ta = (0.0 * b_z - b_d * w) / det
    tb = (a_d * w - a_z * 0.0) / det
    hx, hy, _ = _vec(hook)
    offset = abs(-(hx - ax) * ey + (hy - ay) * ex)
    notes = []
    if offset > 1e-3:
        notes.append(f"The hook is {offset * 1000:.0f} mm beside the line between the lift points: the load turns "
                     "until it hangs under it.")
    inputs = dict(weight=weight, point_a=_vec(point_a), point_b=_vec(point_b), hook=_vec(hook), leg_wll=leg_wll,
                  shackle_wll=shackle_wll)
    forces = [ta, tb]
    details = dict(vertical=[ta * a_z, tb * b_z], force=forces, length=[la, lb], angle=[anga, angb],
                   horizontal=[ta * a_d, tb * b_d])
    formula = "V_A = W·b/(a+b), V_B = W·a/(a+b); T = V·L/h"
    if min(forces) < -EPS * max(1.0, w):
        return _result("C2", "Sling legs, 2-leg", formula, inputs, value=max(forces), details=details, notes=notes,
                       floor=RED, what="The hook is not above a point between the lift points: one leg would push")
    parts = []
    for name, t, ang in (("A", ta, anga), ("B", tb, angb)):
        if leg_wll is not None:
            parts.append(wll_use(t, leg_wll, item=f"sling leg {name}", angle=ang, limits=limits))
        if shackle_wll is not None:
            parts.append(wll_use(t, shackle_wll, item=f"shackle {name}", limits=limits))
    what = (f"Leg A {_ft(ta)} at {anga:.1f}°, leg B {_ft(tb)} at {angb:.1f}°"
            + ("" if parts else ": no WLL entered"))
    return _result("C2", "Sling legs, 2-leg", formula, inputs, value=max(forces), parts=parts, details=details,
                   notes=notes, amber_at=limits.rigging, what=what)


SKEW_FACTOR_DNV = 1.25
ASSEMBLY_FACTOR = ((45.0, 2.1), (60.0, 1.5))  # 3- and 4-leg slings: (largest leg angle to vertical, × leg WLL)
LEG_MODES = ("rigid", "equalised", "dnv")


def assembly_factor(angle: float) -> float | None:
    """The marked rating of a 3- or 4-leg sling as a multiple of the leg WLL (uniform load method): 2.1 for legs
    0–45° from vertical, 1.5 for 45–60°, None (not rated) above 60°."""
    for top, factor in ASSEMBLY_FACTOR:
        if angle <= top + EPS:
            return factor
    return None


def multi_leg(weight: float, points, hook, leg_wll: float | None = None, mode: str = "rigid",
              limits: Limits = DEFAULT_LIMITS) -> Result:
    """C3: a 3- or 4-leg sling on a rigid load. 'rigid': two legs carry, T = (W/2)·L/h; 'equalised': equal share
    W/n·L/h; 'dnv': equal share × 1.25. With a leg WLL: the leg force against it, and the assembly against its
    marked rating (2.1 × / 1.5 × the leg WLL, none above 60°)."""
    points = list(points)
    if len(points) not in (3, 4):
        raise ValueError("A multi-leg sling has 3 or 4 legs.")
    if mode not in LEG_MODES:
        raise ValueError(f"Unknown mode {mode!r}: use one of {', '.join(LEG_MODES)}.")
    w = weight * G
    n = len(points)
    legs = [_leg(p, hook) for p in points]
    lengths = [l for _, l, _, _ in legs]
    angles = [a for _, _, _, a in legs]
    rigid = [w / 2.0 * l / h for _, l, h, _ in legs]
    equal = [w / n * l / h for _, l, h, _ in legs]
    dnv = [e * SKEW_FACTOR_DNV for e in equal]
    force = {"rigid": rigid, "equalised": equal, "dnv": dnv}[mode]
    top = max(angles)
    details = dict(force=force, length=lengths, angle=angles, equal_share=equal, dnv_share=dnv, rigid_share=rigid)
    formula = {"rigid": "two legs carry: T = (W/2)·L/h", "equalised": "equal share: T = (W/n)·L/h",
               "dnv": "equal share × skew factor 1.25: T = 1.25·(W/n)·L/h"}[mode]
    inputs = dict(weight=weight, points=[_vec(p) for p in points], hook=_vec(hook), leg_wll=leg_wll, mode=mode)
    parts = []
    floor = OK
    notes = []
    if mode == "equalised":
        notes.append("Equal share: only with equalisers fitted.")
    if leg_wll is not None:
        parts.append(wll_use(max(force), leg_wll, item="sling leg", angle=top, limits=limits))
        factor = assembly_factor(top)
        if factor is None:
            parts.append(_result("C3", "Sling assembly rating", "marked rating = factor × leg WLL",
                                 dict(weight=weight, leg_wll=leg_wll, angle=top), value=weight, floor=RED,
                                 amber_at=limits.rigging,
                                 what=f"A leg is {top:.1f}° from vertical: above {MAX_LEG_ANGLE:g}° not rated"))
        else:
            rating = factor * leg_wll
            parts.append(_result("C3", "Sling assembly rating", f"marked rating = {factor:g} × leg WLL",
                                 dict(weight=weight, leg_wll=leg_wll, angle=top), value=weight, limit=rating,
                                 use=weight / rating, amber_at=limits.rigging,
                                 what=f"Load {_t(weight)} on a {n}-leg assembly rated {_t(rating)} "
                                      f"({factor:g} × {_t(leg_wll)}, legs up to {top:.1f}°)"))
    if top > MAX_LEG_ANGLE + EPS:
        floor = RED
        notes.append(f"A leg is {top:.1f}° from vertical: above {MAX_LEG_ANGLE:g}° it is not rated.")
    what = f"{n} legs, {mode}: largest leg force {_ft(max(force))}, legs up to {top:.1f}° from vertical"
    if not parts:
        what += ": no WLL entered"
    return _result("C3", f"Sling legs, {n}-leg", formula, inputs, value=max(force), parts=parts, floor=floor,
                   details=details, notes=notes, amber_at=limits.rigging, what=what)


# ---------------------------------------------------------------------------------------------------------------------
# C5 – outriggers and mats

@dataclass
class Reactions:
    P: float  # kg, total mass
    x: float  # m, resultant from the outrigger centre
    y: float
    corners: list  # [(x, y)] in the order (+a,+b), (+a,-b), (-a,+b), (-a,-b), in the carrier's frame
    reactions: list | None  # N per corner; None when the crane tips
    lifted: int | str | None  # index of the corner that lifts, "tips", or None


def resultant(items) -> tuple[float, float, float]:
    """Total mass and the plan position of its centre: items = [(mass kg, x m, y m)]."""
    items = list(items)
    p = sum(m for m, _, _ in items)
    if p <= 0:
        raise ValueError("The total mass must be above 0.")
    return p, sum(m * x for m, x, _ in items) / p, sum(m * y for m, _, y in items) / p


def _solve3(m, v):
    """Cramer's rule for a 3 × 3 system."""
    def det(a):
        return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
                - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    d = det(m)
    if abs(d) <= EPS:
        raise ValueError("The three supports lie on one line.")
    out = []
    for k in range(3):
        mk = [[v[i] if j == k else m[i][j] for j in range(3)] for i in range(3)]
        out.append(det(mk) / d)
    return out


def outrigger_reactions(items, a: float, b: float, centre=(0.0, 0.0)) -> Reactions:
    """C5 reactions: rigid carrier, linear share R = P·g/4·(1 ± x̄/a ± ȳ/b); a corner with R < 0 lifts and the other
    three carry (three equations); a resultant outside the base: the crane tips (no reactions)."""
    if a <= 0 or b <= 0:
        raise ValueError("The outrigger half-spreads a and b must be above 0.")
    p, xg, yg = resultant(items)
    cx, cy = centre
    x, y = xg - cx, yg - cy
    signs = ((1, 1), (1, -1), (-1, 1), (-1, -1))
    corners = [(cx + sx * a, cy + sy * b) for sx, sy in signs]
    w = p * G
    if abs(x) > a * (1 + EPS) or abs(y) > b * (1 + EPS):
        return Reactions(p, x, y, corners, None, "tips")
    rs = [w / 4.0 * (1 + sx * x / a + sy * y / b) for sx, sy in signs]
    low = min(range(4), key=lambda i: rs[i])
    if rs[low] >= -EPS * w:
        return Reactions(p, x, y, corners, [max(r, 0.0) for r in rs], None)
    keep = [i for i in range(4) if i != low]
    m = [[1.0, 1.0, 1.0], [signs[i][0] * a for i in keep], [signs[i][1] * b for i in keep]]
    sol = _solve3(m, [w, w * x, w * y])
    if min(sol) < -EPS * w:
        return Reactions(p, x, y, corners, None, "tips")
    out = [0.0] * 4
    for i, r in zip(keep, sol):
        out[i] = max(r, 0.0)
    return Reactions(p, x, y, corners, out, low)


def crane_items(carrier, upper, load_mass: float, load_radius: float, slew: float):
    """Mass items in the carrier's frame for a slew angle (degrees from +x towards +y): carrier = [(m, x, y)] fixed;
    upper = [(m, r, side)] turning with the slew (r along the boom, + towards the load, side to its left); the load at
    ``load_radius`` along the boom (left out when its mass is 0)."""
    s = math.radians(slew)
    c, si = math.cos(s), math.sin(s)
    out = [(m, x, y) for m, x, y in carrier]
    for m, r, side in upper:
        out.append((m, r * c - side * si, r * si + side * c))
    if load_mass:
        out.append((load_mass, load_radius * c, load_radius * si))
    return out


_CORNER_NAMES = ("(+a, +b)", "(+a, −b)", "(−a, +b)", "(−a, −b)")


def outriggers(items, a: float, b: float, mat=None, allowable: float | None = None, centre=(0.0, 0.0),
               limits: Limits = DEFAULT_LIMITS) -> Result:
    """C5: the outrigger reactions and the mat pressure R_max / mat area against the entered allowable pressure."""
    re = outrigger_reactions(items, a, b, centre)
    inputs = dict(items=[tuple(i) for i in items], a=a, b=b, mat=None if mat is None else tuple(mat),
                  allowable=allowable, centre=tuple(centre))
    details = dict(P=re.P, x=re.x, y=re.y, corners=re.corners, reactions=re.reactions, lifted=re.lifted)
    formula = "R = P/4·(1 ± x̄/a ± ȳ/b); pressure = R·g / mat area"
    if re.reactions is None:
        return _result("C5", "Outriggers and mats", formula, inputs, details=details, floor=RED,
                       what=f"The load's resultant ({re.x:.2f}, {re.y:.2f}) m lies outside the outrigger base")
    notes = []
    floor = OK
    if re.lifted is not None:
        floor = AMBER
        notes.append(f"One outrigger unloaded: {_CORNER_NAMES[re.lifted]} lifts, the other three carry.")
    rmax = max(re.reactions)
    details["r_max"] = rmax
    text = f"Largest outrigger load {_ft(rmax)}"
    if mat is None or allowable is None:
        notes.append("Mat size or allowable ground pressure not entered: the ground pressure is not checked.")
        details["pressure"] = None
        return _result("C5", "Outriggers and mats", formula, inputs, details=details, floor=floor, notes=notes,
                       what=text)
    area = float(mat[0]) * float(mat[1])
    if area <= 0:
        raise ValueError("The mat area must be above 0.")
    pressure = rmax / area
    details["pressure"] = pressure
    return _result("C5", "Outriggers and mats", formula, inputs, value=pressure, limit=allowable,
                   use=pressure / allowable, amber_at=limits.ground, floor=floor, details=details, notes=notes,
                   what=f"{text} on a {mat[0]:g} × {mat[1]:g} m mat: {_pa(pressure)} against {_pa(allowable)} entered")


def outriggers_sweep(carrier, upper, load_mass: float, load_radius: float, a: float, b: float, mat=None,
                     allowable: float | None = None, step: float = 1.0, centre=(0.0, 0.0),
                     limits: Limits = DEFAULT_LIMITS) -> Result:
    """C5 at every slew angle (0 … 360° in ``step``), loaded and unloaded: the worst one (details ``slew``,
    ``loaded``)."""
    if step <= 0:
        raise ValueError("The step must be above 0.")
    n = max(1, int(math.ceil(360.0 / step - EPS)))
    best, key = None, None
    for i in range(n):
        slew = i * step
        for loaded in (True, False):
            items = crane_items(carrier, upper, load_mass if loaded else 0.0, load_radius, slew)
            r = outriggers(items, a, b, mat=mat, allowable=allowable, centre=centre, limits=limits)
            r.details["slew"] = slew
            r.details["loaded"] = loaded
            k = (_RANK[r.status], r.details.get("r_max") or (float("inf") if r.status == RED else 0.0))
            if key is None or k > key:
                best, key = r, k
    best.notes.append(f"Worst of every slew angle (step {step:g}°), with and without the load: slew "
                      f"{best.details['slew']:g}°, {'loaded' if best.details['loaded'] else 'unloaded'}.")
    return best


# ---------------------------------------------------------------------------------------------------------------------
# C6 – crawler tracks

def tracks(mass: float, x: float, y: float, gauge: float, length: float, width: float,
           allowable: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C6: shares by lever across the gauge; along a track e = |x|: e ≤ L/6 trapezoid p = R/(bL)·(1 ± 6e/L);
    beyond, triangle p_max = 2R / (3b(L/2 − e)) over 3(L/2 − e)."""
    if gauge <= 0 or length <= 0 or width <= 0:
        raise ValueError("Gauge, track length and width must be above 0.")
    inputs = dict(mass=mass, x=x, y=y, gauge=gauge, length=length, width=width, allowable=allowable)
    w = mass * G
    e = abs(x)
    formula = "share by lever across the gauge; e ≤ L/6: p = R/(bL)·(1 ± 6e/L); else p_max = 2R/(3b(L/2 − e))"
    if abs(y) > gauge / 2 * (1 + EPS) or e >= length / 2 * (1 - EPS):
        return _result("C6", "Crawler tracks", formula, inputs, floor=RED,
                       what=f"The resultant ({x:.2f}, {y:.2f}) m lies outside the tracks")
    shares = [w * (gauge / 2 + y) / gauge, w * (gauge / 2 - y) / gauge]
    pmax, pmin, contact = [], [], []
    for r in shares:
        if e <= length / 6 + EPS:
            pmax.append(r / (width * length) * (1 + 6 * e / length))
            pmin.append(r / (width * length) * (1 - 6 * e / length))
            contact.append(length)
        else:
            c = 3 * (length / 2 - e)
            pmax.append(2 * r / (3 * width * (length / 2 - e)))
            pmin.append(0.0)
            contact.append(c)
    top = max(pmax)
    details = dict(share=shares, p_max=pmax, p_min=pmin, contact=contact,
                   shape="trapezoid" if e <= length / 6 + EPS else "triangle")
    what = f"Largest track pressure {_pa(top)} ({details['shape']}, e = {e:.2f} m)"
    if allowable is None:
        return _result("C6", "Crawler tracks", formula, inputs, value=top, details=details,
                       notes=["Allowable ground pressure not entered: the ground pressure is not checked."],
                       what=what)
    return _result("C6", "Crawler tracks", formula, inputs, value=top, limit=allowable, use=top / allowable,
                   amber_at=limits.ground, details=details, what=f"{what} against {_pa(allowable)} entered")


# ---------------------------------------------------------------------------------------------------------------------
# C7 – forklift at another load centre

def forklift(load: float, rated: float, centre: float, actual_centre: float, axle_to_face: float,
             table=None, lift_height: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C7: the truck's own table first (next larger load centre and lift height); else the fork rule
    rated·c/c2 (never more than rated); the moment rule rated·(c + x)/(c2 + x) for information only."""
    if centre <= 0 or actual_centre <= 0:
        raise ValueError("Load centres must be above 0.")
    moment = rated * (centre + axle_to_face) / (actual_centre + axle_to_face)
    inputs = dict(load=load, rated=rated, centre=centre, actual_centre=actual_centre, axle_to_face=axle_to_face,
                  table=None if table is None else [tuple(r) for r in table], lift_height=lift_height)
    details = dict(moment_rule=moment, moment_use=load / moment if moment > 0 else None)
    notes = [f"Moment rule {_t(moment)} ({_pct(details['moment_use'])}) – for information only."]
    if table:
        rows = [r for r in table if r[0] >= actual_centre - EPS and (lift_height is None or r[1] >= lift_height - EPS)]
        if not rows:
            return _result("C7", "Forklift capacity", "the truck's capacity table", inputs, value=load,
                           details=details, notes=notes, floor=RED,
                           what="No row of the truck's table covers this load centre and lift height")
        c, h, cap = min(rows, key=lambda r: (r[0], r[1]))
        details.update(capacity=cap, table_row=(c, h, cap))
        formula = "the truck's table: next larger load centre and lift height"
        what = f"{_t(load)} at {actual_centre * 1000:.0f} mm: table {_t(cap)} (row {c * 1000:.0f} mm, {h:g} m)"
    else:
        cap = min(rated, rated * centre / actual_centre)
        details["capacity"] = cap
        formula = "fork rule: rated × c / c2"
        what = f"{_t(load)} at {actual_centre * 1000:.0f} mm: fork rule {_t(cap)}"
    return _result("C7", "Forklift capacity", formula, inputs, value=load, limit=cap, use=load / cap,
                   amber_at=limits.crane, details=details, notes=notes, what=what)


# ---------------------------------------------------------------------------------------------------------------------
# C8 – offshore DAF

SITES = ("onshore", "inshore", "offshore")
# DNV-OS-H205 (2014) Table 3-1 (public), an editable preset: rows (upper static hook load in kg, inclusive; None =
# above), DAF onshore, inshore, offshore.
DAF_DNV_OS_H205_2014 = (
    (100_000.0, 1.10, 1.15, 1.30),
    (300_000.0, 1.05, 1.12, 1.25),
    (1_000_000.0, 1.05, 1.10, 1.20),
    (2_500_000.0, 1.03, 1.08, 1.15),
    (None, 1.03, 1.05, 1.10),
)
DAF_NOTE = "Preset from DNV-OS-H205 (2014) – check against the current DNV-ST-N001"


def static_hook_load(load: float, rigging: float = 0.0, tool: float = 0.0, contingency: float = 1.0) -> float:
    """SHL = load × weight contingency + rigging + lifting tool (kg)."""
    return load * contingency + rigging + tool


def daf_for(shl: float, site: str, table=DAF_DNV_OS_H205_2014) -> float:
    """The DAF of the band the static hook load falls in (band tops inclusive)."""
    if site not in SITES:
        raise ValueError(f"Unknown site {site!r}: use one of {', '.join(SITES)}.")
    k = SITES.index(site) + 1
    rows = list(table)
    if not rows:
        raise ValueError("The DAF table has no rows.")
    for row in rows:
        if row[0] is None or shl <= row[0] + EPS:
            return row[k]
    return rows[-1][k]


def dynamic_load(shl: float, site: str, chart_capacity: float | None = None, hs_rated: bool = False,
                 daf: float | None = None, table=DAF_DNV_OS_H205_2014, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C8: DHL = SHL × DAF (band table, editable preset, or ``daf`` typed by the planner); against a static chart value.
    An Hs-rated crane is checked with its Hs column in C1 instead; the DAF stays for the rigging."""
    preset = daf is None
    f = daf_for(shl, site, table) if preset else daf
    dhl = shl * f
    inputs = dict(shl=shl, site=site, chart_capacity=chart_capacity, hs_rated=hs_rated, daf=daf)
    details = dict(shl=shl, daf=f, dhl=dhl)
    notes = [DAF_NOTE] if preset else ["DAF entered by the planner."]
    formula = "DHL = SHL × DAF"
    what = f"Static hook load {_t(shl)} × DAF {f:.2f} ({site}) = dynamic hook load {_t(dhl)}"
    if hs_rated:
        notes.append("Hs-rated crane: the crane is checked with its Hs column (crane use), the DAF is for the rigging.")
        return _result("C8", "Offshore DAF", formula, inputs, value=dhl, details=details, notes=notes, what=what)
    if chart_capacity is None:
        return _result("C8", "Offshore DAF", formula, inputs, value=dhl, details=details, notes=notes, what=what)
    return _result("C8", "Offshore DAF", formula, inputs, value=dhl, limit=chart_capacity, use=dhl / chart_capacity,
                   amber_at=limits.crane, details=details, notes=notes,
                   what=f"{what} against {_t(chart_capacity)} from the static chart")


# ---------------------------------------------------------------------------------------------------------------------
# C9 – upending

def upending(items, hook_s: float, angle: float, rope=(0.0, 1.0), off_hinge: bool = False,
             capacity: float | None = None, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C9: a pile hinged at its foot, lifted at ``hook_s`` along it, ``angle``° above horizontal; moment about the
    hinge: F = Σ m·g·s·cos θ / (hook_s·(cos θ·r_up − sin θ·r_h)). Rope vertical: F = Σ m·g·s / hook_s at every angle.
    At vertical (no lever) or off the hinge the hook takes everything."""
    if not 0.0 <= angle <= 90.0:
        raise ValueError("The angle must lie between 0° (lying) and 90° (upright).")
    if hook_s <= 0:
        raise ValueError("The hook must sit along the pile, above the hinge.")
    rh, ru = (float(v) for v in rope)
    n = math.hypot(rh, ru)
    if n <= EPS or ru <= 0:
        raise ValueError("The rope must pull upwards.")
    rh, ru = rh / n, ru / n
    items = [tuple(i) for i in items]
    total = sum(m for m, _ in items) * G
    th = math.radians(angle)
    c, s = math.cos(th), math.sin(th)
    lever = hook_s * (c * ru - s * rh)
    notes = []
    inputs = dict(items=items, hook_s=hook_s, angle=angle, rope=(rh, ru), off_hinge=off_hinge, capacity=capacity)
    if off_hinge or abs(lever) <= 1e-9 * hook_s:
        f = total / ru
        hinge = (0.0, 0.0)
        notes.append("Off the hinge or upright: the hook is checked for the whole weight.")
        formula = "hook = total weight"
    else:
        moment = sum(m * G * sd * c for m, sd in items)
        f = moment / lever
        hinge = (-f * rh, total - f * ru)
        formula = "F_hook = Σ m·g·d / d_hook (moments about the hinge)"
    if f < -EPS * max(1.0, total):
        raise ValueError("The rope would have to push: check its direction.")
    details = dict(hook=f, hinge=math.hypot(*hinge), hinge_vector=hinge, total=total)
    what = f"Hook {_ft(f)}, hinge {_ft(details['hinge'])} at {angle:g}°"
    if capacity is None:
        return _result("C9", "Upending", formula, inputs, value=f, details=details, notes=notes, what=what)
    return _result("C9", "Upending", formula, inputs, value=f, limit=capacity, use=f / (capacity * G),
                   amber_at=limits.crane, details=details, notes=notes, what=f"{what} against {_t(capacity)}")


# ---------------------------------------------------------------------------------------------------------------------
# C10 – hoist line pull (task 0232)

K_ROLLER = 1.04    # sheave friction factor, roller (anti-friction) bearings – API RP 9B (14th ed., 2015)
K_PLAIN = 1.09     # sheave friction factor, plain (bronze) bushings – the same source
REEVING_SOURCE = ("API RP 9B (14th ed., 2015): reeving efficiency E = (K^N − 1) / (K^S · N · (K − 1)), N parts of line, "
                  "S sheaves, sheave friction factor K = 1.04 roller bearings, 1.09 plain bushings")


def reeving_efficiency(falls: int, sheaves: int | None = None, k: float = K_ROLLER) -> float:
    """E = (K^N − 1) / (K^S · N · (K − 1)): the share of the ideal pull W / N the hoist line gives when the rope runs
    over S sheaves (S = N when the line from the drum comes over the head's lead sheave, as on the app's cranes)."""
    n = int(falls)
    if n < 1:
        raise ValueError("The rope needs at least one fall.")
    s = n if sheaves is None else int(sheaves)
    if k <= 1.0 + EPS:
        return 1.0
    return (k ** n - 1.0) / (k ** s * n * (k - 1.0))


def hoist_line_pull(gross: float, falls: int, max_line_pull: float | None = None, sheaves: int | None = None,
                    k: float = K_ROLLER, limits: Limits = DEFAULT_LIMITS) -> Result:
    """C10: line pull = gross / (falls × E) (kg as a pull; E: ``reeving_efficiency``), against the winch's maximum
    line pull from the crane's file (kg); amber from the crane limit. No maximum entered -> not checked."""
    e = reeving_efficiency(falls, sheaves, k)
    pull = gross / (int(falls) * e)
    inputs = dict(gross=gross, falls=int(falls), sheaves=int(falls) if sheaves is None else int(sheaves), k=k,
                  max_line_pull=max_line_pull)
    details = dict(efficiency=e, pull=pull, ideal=gross / int(falls), source=REEVING_SOURCE)
    formula = "line pull = gross / (falls × E), E = (K^N − 1) / (K^S·N·(K − 1))"
    what = f"Gross {_t(gross)} on {int(falls)} falls (E {e * 100:.1f} %): line pull {_t(pull)}"
    if max_line_pull is None:
        return _result("C10", "Hoist line pull", formula, inputs, value=pull, details=details,
                       amber_at=limits.crane, what=what + ", no maximum line pull entered")
    if not (_finite(max_line_pull) and max_line_pull > 0):
        raise ValueError("The maximum line pull must be a number above 0.")
    return _result("C10", "Hoist line pull", formula, inputs, value=pull, limit=max_line_pull,
                   use=pull / max_line_pull, amber_at=limits.crane, details=details,
                   what=what + f" on a winch of {_t(max_line_pull)}")
