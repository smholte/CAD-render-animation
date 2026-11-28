"""Invented SAMPLE load charts for the crane classes (task 0191) – plain Python.

Not one maker's chart: each capacity is worked out from the class's own invented numbers (``classes``) by a simple
model with the shape real charts have, then rounded down:

- **strength**: the boom and its luffing gear carry ``rated`` at the class's shortest radius; further out the moment
  about the luff pin limits it (capacity x (radius - pin) = constant), a longer boom carries less (a power of
  shortest / this boom);
- **tipping**: the 75 % rule over the outrigger / track edge on the weakest side (360° slew). A mobile and a
  knuckle-boom crane (task 0349): the load whose resultant with the crane's own masses – the carrier / truck where its
  centre of gravity is, the superstructure / column, counterweight and boom turned with the slew – reaches the edge of
  the real outrigger base (its centre need not be the slew axis), the smallest over every slew angle; the masses'
  centres from the made solids (``cogs``, what the equipment file says) or, while the numbers are typed, estimated
  from the layout. A crawler: stabilising moment of lower and upper works and counterweight against the load and the
  boom's own moment over the nearer track edge;
- the smaller of the two, never more than the class number, never more than a shorter boom (or fewer extensions) at
  the same radius; rows where less than ``MIN_ROW`` t is left are not in the chart.

Every chart is ``sample`` and passes ``core.lifting.validate_charts`` with no errors. Units: t and m (the equipment
file's units).
"""

from __future__ import annotations

import math

import numpy as np

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


SLEW_STEPS = 72        # slew angles tried for the weakest direction (every 5°; the corners' angles are added)


def _turned(fixed, turning, th):
    """(mass, x, y) arrays of the crane's masses at slew angles ``th`` (radians, (K,)): ``fixed`` [(t, x, y)] stay,
    ``turning`` [(t, u, v)] – in the upper's frame, u along the boom from the slew axis – turn with the slew."""
    c, s = np.cos(th)[:, None], np.sin(th)[:, None]
    mf = np.array([m for m, _x, _y in fixed] + [m for m, _u, _v in turning], float)
    xs = [np.full(len(th), x) for _m, x, _y in fixed] + [u * c[:, 0] - v * s[:, 0] for _m, u, v in turning]
    ys = [np.full(len(th), y) for _m, _x, y in fixed] + [u * s[:, 0] + v * c[:, 0] for _m, u, v in turning]
    return mf, np.stack(xs, axis=1), np.stack(ys, axis=1)


def _angles(base) -> np.ndarray:
    cx, a, b = base
    th = np.radians(np.arange(SLEW_STEPS) * 360.0 / SLEW_STEPS)
    corners = [math.atan2(sy * b, cx + sx * a) for sx in (-1, 1) for sy in (-1, 1)]
    return np.concatenate([th, np.array(corners) % (2 * math.pi)])


def base_margins(fixed, turning, base) -> np.ndarray:
    """The share of the base (``base_margin`` of core.lifting_path: 1 in the middle, 0 on the edge) the crane's own
    centre of gravity keeps at every slew angle tried."""
    cx, a, b = base
    th = _angles(base)
    m, x, y = _turned(fixed, turning, th)
    gx, gy = (x * m).sum(axis=1) / m.sum(), (y * m).sum(axis=1) / m.sum()
    return np.minimum(1.0 - np.abs(gx - cx) / a, 1.0 - np.abs(gy) / b)


def tip_load(fixed, turning, r: float, base) -> float:
    """The smallest load (t) at radius ``r`` (m, from the slew axis at x = y = 0, in the boom's direction) whose
    resultant with the crane's masses reaches the edge of the base ``(cx, a, b)`` (the rectangle |x − cx| ≤ a,
    |y| ≤ b), over every slew angle tried: 0 when the crane alone already stands outside it."""
    cx, a, b = base
    th = _angles(base)
    m, x, y = _turned(fixed, turning, th)
    M0 = float(m.sum())
    gx, gy = (x * m).sum(axis=1) / M0, (y * m).sum(axis=1) / M0
    if np.any(np.abs(gx - cx) >= a) or np.any(np.abs(gy) >= b):
        return 0.0
    dx, dy = r * np.cos(th) - gx, r * np.sin(th) - gy
    big = 1e9
    with np.errstate(divide="ignore", invalid="ignore"):
        sx = np.where(dx > 1e-12, (cx + a - gx) / dx, np.where(dx < -1e-12, (cx - a - gx) / dx, big))
        sy = np.where(dy > 1e-12, (b - gy) / dy, np.where(dy < -1e-12, (-b - gy) / dy, big))
    sh = np.minimum(sx, sy)                    # the share of the way from the crane's CoG to the load: the edge
    if np.any(sh >= 1.0 - 1e-12):              # the load itself stands inside the base that way: no tipping there
        sh = np.where(sh >= 1.0 - 1e-12, np.inf, sh)
    s_min = float(np.min(sh))
    if not math.isfinite(s_min):
        return math.inf
    return M0 * s_min / (1.0 - s_min)


def _back_ok(masses_at: list, e: float) -> bool:
    """(mass t, x m from the slew axis, + = towards the boom) of the unloaded crane, boom over the tipping line at e
    behind it: True when its centre of gravity lies at least BACK_RESERVE x e in front of that line."""
    m = sum(mi for mi, _ in masses_at)
    x = sum(mi * xi for mi, xi in masses_at) / m
    return x + e >= BACK_RESERVE * e


# ---------------------------------------------------------------------------------------------------------------------
# Mobile telescopic

def _xy(cogs, key, default):
    v = (cogs or {}).get(key)
    return (float(v[0]), float(v[1])) if v is not None else default


def mobile_masses(c: C.Mobile, cogs: dict | None = None, L=None):
    """(fixed, turning without the boom, the outrigger boxes' x (front, rear) m) of a mobile crane: the carrier where
    its centre of gravity is (``cogs``: the made solids'; else the middle of the carrier, an estimate), the
    superstructure and the counterweight turning with the slew."""
    L = L or C.layout(c)
    p = L.pts
    est = ((p["front"] + p["rear"]) / 2000.0, 0.0)
    fixed = [(c.mass_carrier, *_xy(cogs, "carrier", est))]
    turning = [(c.mass_upper, *_xy(cogs, "superstructure", (0.0, 0.0))),
               (None, *_xy(cogs, "counterweight", (-c.cw_x / 1000.0, 0.0)))]
    return fixed, turning, tuple(x / 1000.0 for x in p["out_x"])


def _base(out_x, spread_m: float):
    xf, xr = out_x
    return ((xf + xr) / 2.0, abs(xf - xr) / 2.0, spread_m / 2.0)


def mobile(c: C.Mobile, cogs: dict | None = None) -> list:
    L = C.layout(c)
    xp = L.pts["xp"] / 1000.0                      # luff pin (negative: behind the slew axis)
    L0 = c.L0 / 1000.0
    Lmax = c.Lmax / 1000.0
    booms = [math.ceil((L0 + k * (Lmax - L0) / 5.0) * 100 - 1e-6) / 100 for k in range(6)]
    r_rated = 3.0
    fixed, turn0, out_x = mobile_masses(c, cogs, L)
    charts = []
    for spread in c.spread:
        base = _base(out_x, spread / 1000.0)
        for cw in c.counterweights:
            turning = [(m if m is not None else cw, u, v) for m, u, v in turn0]
            turning = [t for t in turning if t[0] > 0]
            for Lb in booms:
                steep = [(c.mass_boom, xp + 0.42 * Lb * math.cos(math.radians(c.luff_max)), 0.0)]
                if float(np.min(base_margins(fixed, turning + steep, base))) < BACK_RESERVE:
                    continue
                r_min = max(r_rated, xp + Lb * math.cos(math.radians(c.luff_max)))
                r_max = xp + Lb * math.cos(math.radians(10.0))
                rows = []
                for r in _radii(math.ceil(r_min * 2) / 2, r_max):
                    strength = c.rated * (r_rated - xp) / (r - xp) * (L0 / Lb) ** 0.8
                    strength -= 0.15 * c.mass_boom * (Lb / Lmax) * (r - r_rated) / Lb    # the boom's own weight
                    bx = xp + 0.42 * (r - xp)                  # the boom's centre of gravity, from the slew axis
                    tip = STAB_MOBILE * tip_load(fixed, turning + [(c.mass_boom, bx, 0.0)], r, base)
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

KB_TRUCK_EST = 0.40       # the truck's centre of gravity while the numbers are typed: this share from its front to its rear


def knuckle_masses(c: C.Knuckle, cogs: dict | None = None, L=None):
    """(fixed, turning without the booms, the stabiliser boxes' x) of a knuckle-boom crane (``mobile_masses``)."""
    L = L or C.layout(c)
    p = L.pts
    est = ((p["front"] + KB_TRUCK_EST * (p["rear"] - p["front"])) / 1000.0, 0.0)
    fixed = [(c.mass_truck, *_xy(cogs, "truck", est))]
    turning = [(c.mass_column, *_xy(cogs, "column", (0.0, 0.0)))]
    return fixed, turning, tuple(x / 1000.0 for x in p["out_x"])


def knuckle(c: C.Knuckle, cogs: dict | None = None) -> list:
    """By outreach: ``boom`` in the configuration is the outreach with that many extensions out (so ``pick_chart``
    takes the next longer one); the chart's name says so."""
    charts = []
    base_reach = (c.main_len + c.outer_len) / 1000.0
    fixed, turning, out_x = knuckle_masses(c, cogs)
    for spread in c.spread:
        base = _base(out_x, spread / 1000.0)
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
                tip = STAB_KNUCKLE * tip_load(fixed, turning + [(m_booms, 0.40 * r, 0.0)], r, base)
                rows.append((r, min(c.max_cap, strength, tip)))
            label = (f"SAMPLE – 360°, outreach {reach:g} m ({k} of {c.extensions} extensions out), "
                     f"stabilisers {spread / 1000.0:g} m")
            ch = _chart({"boom": reach, "outriggers": round(spread / 1000.0, 2)}, rows, c, label=label)
            if ch:
                charts.append(ch)
    _cap_shorter(charts, key=("outriggers",))
    return charts


def charts_of(name_or_cls, cogs: dict | None = None) -> list:
    """The class's SAMPLE charts; ``cogs`` (group -> [x, y, z] m, the made solids') for a mobile or knuckle-boom crane's
    tipping (task 0349), else estimated from the layout."""
    c = C.CLASSES[name_or_cls] if isinstance(name_or_cls, str) else name_or_cls
    if c.kind == "CC":
        return crawler(c)
    return {"AT": mobile, "KB": knuckle}[c.kind](c, cogs)


def as_charts(chart_dicts: list) -> list:
    """The charts as ``core.lifting.Chart`` (kg, m)."""
    return [lifting.chart_from_dict(d, "t", "m") for d in chart_dicts]
