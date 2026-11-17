"""Invented SAMPLE load charts for the crane classes (task 0191) – plain Python.

Not one maker's chart: each capacity is worked out from the class's own invented numbers (``classes``) by a simple
model with the shape real charts have, then rounded down:

- **strength**: the boom and its luffing gear carry ``rated`` at the class's shortest radius; further out the moment
  about the luff pin limits it (capacity x (radius - pin) = constant), a longer boom carries less (a power of
  shortest / this boom);
- **tipping**: the 75 % rule over the outrigger / track edge on the weakest side (360° slew): stabilising moment of
  carrier, superstructure and counterweight against the load and the boom's own moment;
- the smaller of the two, never more than the class number, never more than a shorter boom (or fewer extensions) at
  the same radius; rows where less than ``MIN_ROW`` t is left are not in the chart.

Every chart is ``sample`` and passes ``core.lifting.validate_charts`` with no errors. Units: t and m (the equipment
file's units).
"""

from __future__ import annotations

import math

from ..core import lifting
from . import classes as C

MIN_ROW = 0.3          # t: a row with less left is not charted
STAB_MOBILE = 0.75     # EN 13000 style: rated <= 75 % of the tipping load on outriggers
STAB_CRAWLER = 0.75
STAB_KNUCKLE = 0.85    # loader cranes: a stability factor nearer 1 (invented, plausible)

GRID = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0,
        26.0, 28.0, 30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 44.0, 48.0, 52.0, 56.0, 60.0, 64.0, 68.0, 72.0, 76.0, 80.0,
        86.0, 92.0, 98.0, 104.0, 110.0, 116.0, 122.0, 128.0, 134.0, 140.0)


def _floor(t: float) -> float:
    """Rounded down: 0.1 t from 10 t up, else 0.01 t (a chart never shows more than worked out)."""
    step = 0.1 if t >= 10.0 else 0.01
    return math.floor(t / step + 1e-9) * step


def _radii(r0: float, r1: float, grid=GRID) -> list:
    return [r for r in grid if r0 - 1e-9 <= r <= r1 + 1e-9]


def _chart(config: dict, rows: list, c, includes_block: bool = False, label: str = "") -> dict | None:
    """The chart dict (equipment file form, t and m) from (radius, capacity) rows; rows under MIN_ROW dropped."""
    radius, capacity = [], []
    for r, cap in rows:
        cap = _floor(cap)
        if cap < MIN_ROW:
            break
        radius.append(round(r, 2))
        capacity.append(round(cap, 2))
    if len(radius) < 2:
        return None
    cfg = {k: (lifting.kg(v) if k in ("counterweight",) else v) for k, v in config.items()}
    ch = lifting.Chart(radius=radius, capacity=[lifting.kg(x) for x in capacity], config=cfg,
                       name=label or _name(config), includes_hook_block=includes_block, wind_max=c.wind_max,
                       sample=True)
    d = lifting.chart_to_dict(ch, "t", "m")
    d["capacity"] = [round(x, 2) for x in d["capacity"]]
    d["config"] = {k: round(v, 3) for k, v in d["config"].items()}
    return d


def _name(config: dict) -> str:
    parts = []
    if "boom" in config:
        parts.append(f"boom {config['boom']:g} m")
    if "jib" in config:
        parts.append(f"jib {config['jib']:g} m")
    if "counterweight" in config:
        parts.append(f"counterweight {config['counterweight']:g} t")
    if "outriggers" in config:
        parts.append(f"outriggers {config['outriggers']:g} m")
    return "SAMPLE – 360°, " + ", ".join(parts)


def _cap_by(chart: dict, other: dict) -> None:
    """``chart`` never holds more than ``other`` at a radius ``other`` covers (its next longer row between rows)."""
    if other is None:
        return
    rs, cs = other["radius"], other["capacity"]
    for i, r in enumerate(chart["radius"]):
        nxt = [k for k, x in enumerate(rs) if x >= r - 1e-9]
        if nxt and (r >= rs[0] - 1e-9):
            chart["capacity"][i] = min(chart["capacity"][i], cs[nxt[0]])
    for i in range(1, len(chart["capacity"])):
        chart["capacity"][i] = min(chart["capacity"][i], chart["capacity"][i - 1])


def _cap_shorter(charts: list, key=("counterweight", "outriggers", "jib")) -> None:
    """A longer boom never holds more than a shorter one at the same radius (same other settings): taken down."""
    def other(ch):
        return tuple((k, ch["config"].get(k)) for k in key)
    by = {}
    for ch in sorted(charts, key=lambda ch: ch["config"]["boom"]):
        _cap_by(ch, by.get(other(ch)))
        by[other(ch)] = ch


BACK_RESERVE = 0.15    # unloaded, boom steepest and shortest: the crane's centre of gravity stays this share of the
                       # tipping distance inside the supports, or the configuration is not charted (backward stability)


def _back_ok(masses_at: list, e: float) -> bool:
    """(mass t, x m from the slew axis, + = towards the boom) of the unloaded crane, boom over the tipping line at e
    behind it: True when its centre of gravity lies at least BACK_RESERVE x e in front of that line."""
    m = sum(mi for mi, _ in masses_at)
    x = sum(mi * xi for mi, xi in masses_at) / m
    return x + e >= BACK_RESERVE * e


# ---------------------------------------------------------------------------------------------------------------------
# Mobile telescopic

def mobile(c: C.Mobile) -> list:
    L = C.layout(c)
    xp = L.pts["xp"] / 1000.0                      # luff pin (negative: behind the slew axis)
    a = c.span_x / 2000.0
    L0 = c.L0 / 1000.0
    Lmax = c.Lmax / 1000.0
    booms = [math.ceil((L0 + k * (Lmax - L0) / 5.0) * 100 - 1e-6) / 100 for k in range(6)]
    r_rated = 3.0
    charts = []
    for spread in c.spread:
        e = min(spread / 2000.0, a)                # the weakest tipping line (360°)
        for cw in c.counterweights:
            stab = (c.mass_carrier + c.mass_upper) * e + cw * (e + c.cw_x / 1000.0)
            for Lb in booms:
                boom_x = xp + 0.42 * Lb * math.cos(math.radians(c.luff_max))
                if not _back_ok([(c.mass_carrier + c.mass_upper, 0.0), (cw, -c.cw_x / 1000.0),
                                 (c.mass_boom, boom_x)], e):
                    continue
                r_min = max(r_rated, xp + Lb * math.cos(math.radians(c.luff_max)))
                r_max = xp + Lb * math.cos(math.radians(10.0))
                rows = []
                for r in _radii(math.ceil(r_min * 2) / 2, r_max):
                    strength = c.rated * (r_rated - xp) / (r - xp) * (L0 / Lb) ** 0.8
                    strength -= 0.15 * c.mass_boom * (Lb / Lmax) * (r - r_rated) / Lb    # the boom's own weight
                    bx = xp + 0.42 * (r - xp)                  # the boom's centre of gravity, from the slew axis
                    over = c.mass_boom * max(0.0, bx - e)
                    tip = STAB_MOBILE * (stab - over) / (r - e) if r > e else math.inf
                    rows.append((r, min(c.rated, strength, tip)))
                ch = _chart({"boom": Lb, "counterweight": cw, "outriggers": round(spread / 1000.0, 2)}, rows, c)
                if ch:
                    charts.append(ch)
    _cap_shorter(charts)
    return charts


# ---------------------------------------------------------------------------------------------------------------------
# Crawler lattice boom

def crawler(c: C.Crawler) -> list:
    L = C.layout(c)
    tr = L.pts["track"]
    xp = L.pts["xp"] / 1000.0
    e = min(c.gauge / 2000.0, tr["contact"] / 2000.0)
    base = c.mass_lower + c.mass_upper
    L_cad = c.boom_cad / 1000.0
    L_short = min(c.boom_lengths)
    r_rated = max(round(xp + L_short * math.cos(math.radians(c.luff_max)) + 0.5), round(3.0 + c.rated / 300.0))
    charts = []
    for cw in c.counterweights:
        stab = base * e + cw * (e + c.cw_x / 1000.0)
        for Lb in c.boom_lengths:
            mb = c.mass_boom * Lb / L_cad
            if not _back_ok([(base, 0.0), (cw, -c.cw_x / 1000.0),
                             (mb, xp + 0.5 * Lb * math.cos(math.radians(c.luff_max)))], e):
                continue
            r_min = max(r_rated, xp + Lb * math.cos(math.radians(c.luff_max)))
            r_max = xp + Lb * math.cos(math.radians(c.luff_min))
            rows = []
            for r in _radii(math.ceil(r_min), r_max):
                strength = c.rated * ((r_rated - xp) / (r - xp)) ** 0.7 * (L_short / Lb) ** 0.7
                over = mb * max(0.0, xp + 0.5 * (r - xp) - e)
                tip = STAB_CRAWLER * (stab - over) / (r - e) if r > e else math.inf
                rows.append((r, min(c.rated, strength, tip)))
            ch = _chart({"boom": float(Lb), "counterweight": cw}, rows, c)
            if ch:
                charts.append(ch)
    _cap_shorter(charts, key=("counterweight",))
    jib_charts = []
    if c.jib_lengths:
        Lb = c.jib_boom
        mb = c.mass_boom * Lb / L_cad
        boom_angle = 80.0
        bx = xp + Lb * math.cos(math.radians(boom_angle))
        rated_j = 0.3 * c.rated
        Lj0 = min(c.jib_lengths)
        r0 = bx + Lj0 * math.cos(math.radians(80.0))
        for cw in c.counterweights:
            stab = base * e + cw * (e + c.cw_x / 1000.0)
            main = next((ch for ch in charts if ch["config"]["boom"] == float(Lb)
                         and ch["config"]["counterweight"] == cw), None)
            for Lj in c.jib_lengths:
                mj = c.mass_jib * Lj / (c.jib_cad / 1000.0)
                r_min = bx + Lj * math.cos(math.radians(80.0))
                r_max = bx + Lj * math.cos(math.radians(15.0))
                rows = []
                for r in _radii(math.ceil(r_min), r_max):
                    strength = rated_j * ((r0 - bx + 2.0) / (r - bx + 2.0)) ** 0.8 * (Lj0 / Lj) ** 0.7
                    over = mb * max(0.0, xp + 0.5 * Lb * math.cos(math.radians(boom_angle)) - e) \
                        + mj * max(0.0, (bx + r) / 2 - e)
                    tip = STAB_CRAWLER * (stab - over) / (r - e) if r > e else math.inf
                    rows.append((r, min(rated_j, strength, tip)))
                ch = _chart({"boom": float(Lb), "jib": float(Lj), "counterweight": cw}, rows, c)
                if ch:
                    _cap_by(ch, main)              # a jib on the boom never holds more than the boom alone
                    jib_charts.append(ch)
        _cap_shorter_jib(jib_charts)
    return charts + jib_charts


def _cap_shorter_jib(jib_charts: list) -> None:
    """A longer jib never holds more than a shorter one (same counterweight)."""
    by = {}
    for ch in sorted(jib_charts, key=lambda ch: ch["config"]["jib"]):
        _cap_by(ch, by.get(ch["config"]["counterweight"]))
        by[ch["config"]["counterweight"]] = ch


# ---------------------------------------------------------------------------------------------------------------------
# Knuckle boom

def knuckle(c: C.Knuckle) -> list:
    """By outreach: ``boom`` in the configuration is the outreach with that many extensions out (so ``pick_chart``
    takes the next longer one); the chart's name says so."""
    charts = []
    base_reach = (c.main_len + c.outer_len) / 1000.0
    for spread in c.spread:
        e = spread / 2000.0
        stab = (c.mass_truck + c.mass_column) * e
        for k in range(c.extensions + 1):
            reach = math.floor((base_reach + k * c.ext_stroke / 1000.0) * 100 + 1e-6) / 100
            m_booms = c.mass_main + c.mass_outer
            moment = c.moment * (1.0 - 0.035 * k)              # the extensions' own weight costs lifting moment
            rows = []
            radii = _radii(2.0, reach)
            if radii and reach - radii[-1] > 0.2:
                radii.append(reach)
            for r in radii:
                strength = moment / r
                over = m_booms * max(0.0, 0.40 * r - e)
                tip = STAB_KNUCKLE * (stab - over) / (r - e) if r > e else math.inf
                rows.append((r, min(c.max_cap, strength, tip)))
            label = (f"SAMPLE – 360°, outreach {reach:g} m ({k} of {c.extensions} extensions out), "
                     f"stabilisers {spread / 1000.0:g} m")
            ch = _chart({"boom": reach, "outriggers": round(spread / 1000.0, 2)}, rows, c, label=label)
            if ch:
                charts.append(ch)
    _cap_shorter(charts, key=("outriggers",))
    return charts


def charts_of(name_or_cls) -> list:
    c = C.CLASSES[name_or_cls] if isinstance(name_or_cls, str) else name_or_cls
    return {"AT": mobile, "CC": crawler, "KB": knuckle}[c.kind](c)


def as_charts(chart_dicts: list) -> list:
    """The charts as ``core.lifting.Chart`` (kg, m)."""
    return [lifting.chart_from_dict(d, "t", "m") for d in chart_dicts]
