"""Coolant: flood and mist while milling (task 0042). No Blender here.

How it works
------------
* **When**: a Run G-code program step plays its program's coolant codes (``gcode.Schedule.m_times``): the flood
  code (M8) switches flood on, the mist code (M7) mist, the off code (M9; M9 always stops both, as on LinuxCNC).
  Or the step says "always flood" / "always mist" while the spindle turns, or "off". ``spans`` turns that into
  (start, end, kind) in video seconds; the build stores them as frames.
* **Wet surfaces**: the block, the table and the vise get wet while coolant flows and dry a few seconds after it
  stops. ``wetness`` gives the wet level (0 … 1) at any frame straight from the spans – no history – and
  ``wet_keys`` the keys of that curve for the build.
* **The look at every frame** comes from the frame number alone (deterministic: the render queue renders frames out
  of order). Every drop has a fixed seed; its life repeats with a period of its own, and each repeat ("cycle") draws
  new numbers from a hash of (drop, cycle). So frame 50 is the same whether frame 10 or 90 was shown before it.
  - **jets**: a liquid stream from each nozzle to the tool – a tube that sags a little under gravity, ripples along
    its length and spreads, breaking up into drops near the tool;
  - **splash** (task 0257): drops thrown off the turning tool where the jets meet it, more while it cuts than in the
    air. They leave in a flat band at the jets' height, tangentially at about the tool's rim speed v = ω·r (capped at
    ``SPLASH_CAP``), with drops that get finer the faster it turns (``drop_diameter``: a spinning-disc rule) and slow
    down in the air by their size (``drag_time``); below ``FILM_V`` the liquid wears the tool as a turning film that
    runs down the flutes and sheds in a few streams from the flute edges (``film_share``); above ``AIR_V`` the air
    layer turning with the tool bends the end of each jet and atomises part of it (``deflect_share``), so less
    splashes off the tool and a fine mist swirls round it. ``regime`` names the look for a speed;
  - **mist** (M7): no solid stream, a fine cone of tiny drops from each nozzle.
* **Nozzles**: "Automatic" makes 2-4 flexible hoses (Loc-Line look) on a ring round the spindle nose, each bent so
  its nozzle points at the tool; after a tool change they bend again to the new tool's length (``auto_nozzles``,
  ``hose_mesh``). Picked nozzles are parts of the model (a tip and a direction each).

Coordinates: the *coolant space* of the build - origin at the tip of the tool that was in the spindle in the CAD
model, +Z up the tool into the spindle, fixed to the head (it does not turn with the spindle). Metres, seconds;
time in frames where it says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MM = 0.001
G = 9.81

OFF, FLOOD, MIST = 0, 1, 2
KIND_NAMES = {FLOOD: "flood", MIST: "mist"}

RISE = 0.6                  # s: the surfaces are wet this quickly after the coolant starts (63 %)
MIST_WET = 0.55             # mist wets the surfaces less than flood
AIR_SPLASH = 0.3            # share of the splash while the tool is not cutting (moving in the air, coolant on)
CUT_MARGIN = 0.5 * MM       # a feed move this close above the stock's top still counts as cutting
STANDOFF = 60 * MM          # an automatic nozzle's tip is this far from the point it aims at
ELEVATION = math.radians(32)    # … and comes in at this angle above the horizontal
AIM_UP = 4 * MM             # the jets aim this far above the tool's tip (at the cutting edges)
HOSE_R = 4.2 * MM           # Loc-Line 1/4": a segment's ball is about Ø 8.4 mm
HOSE_SEG = 9.5 * MM         # … and a segment this long
RING_GAP = 8 * MM           # the nozzle ring sits this far outside the spindle nose

# The tool's speed (task 0257). Rim speed v = |rpm| * 2 pi / 60 * tool radius, m/s.
FILM_V = 1.0                # below this the liquid wears the tool as a turning film (half film, half splash here)
STREAM_V = 2.0              # below this the splash leaves as big drops / streams
SPRAY_V = 5.0               # a fine spray from here
MIST_V = 15.0               # mist-like above this
AIR_V = 5.0                 # the air layer turning with the tool deflects part of each jet above this rim speed
DEFLECT_MAX = 0.85          # never more than this share of a jet deflected
SPLASH_CAP = 25.0           # m/s: the fastest splash drawn (a D50 at 10,000 rpm: 26 m/s; faster reads as nothing)
LEGACY_V = 3.0              # rim speed when the build stored no spindle speed (projects built before 0.2.200)
SIGMA = 0.04                # N/m: surface tension of a coolant emulsion (water 0.072, cutting oil ~0.03)
RHO = 1000.0                # kg/m3: the liquid
RHO_AIR, MU_AIR = 1.2, 1.8e-5
DROP_MIN, DROP_MAX = 0.08 * MM, 2.4 * MM    # drop diameters drawn (mist … a stream's beads)
FLUTES = 3                  # streams a slow tool sheds (one per flute edge)
HELIX = math.radians(30)    # the flutes' helix angle: a film running down a flute turns with it
FAR = 0.35                  # m: drops further than this from the tool are out of the picture
DRAWN_MIN = 0.09 * MM       # the smallest drop radius drawn (finer ones vanish below a pixel in a close-up)

# The liquid's look: colour (linear), how see-through, IOR, roughness, how milky (sub-surface weight)
@dataclass(frozen=True)
class Liquid:
    label: str
    colour: tuple
    transmission: float
    ior: float
    roughness: float
    milky: float


LIQUIDS = {
    "EMULSION": Liquid("Emulsion (milky)", (0.86, 0.88, 0.84), 0.55, 1.34, 0.08, 0.6),
    "OIL": Liquid("Cutting oil (clear)", (0.95, 0.80, 0.42), 0.95, 1.47, 0.04, 0.0),
}
SHEEN_TINT = {"EMULSION": (0.94, 0.95, 0.92), "OIL": (0.98, 0.93, 0.78)}


# ---------------------------------------------------------------------------
# when coolant flows
# ---------------------------------------------------------------------------

def merge(spans) -> list:
    """Overlapping or touching (start, end) spans joined, sorted."""
    out = []
    for a, b in sorted((float(a), float(b)) for a, b in spans if b > a):
        if out and a <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def spans(m_times, program_end: float, spindle_keys=(), mode: str = "PROGRAM", flood_code: int = 8,
          mist_code: int = 7, off_code: int = 9) -> list:
    """[(start, end, kind)] video seconds while coolant flows, kind FLOOD or MIST, sorted by start.

    ``m_times``: [(video time, M number)] of the program (``Schedule.m_times``). ``mode``: 'PROGRAM' (the codes),
    'FLOOD' / 'MIST' (always, while the spindle turns: ``spindle_keys`` [(t, rpm)]), 'OFF'. A code of 0 is not used.
    M9 always stops both, as on LinuxCNC; flood and mist can be on together."""
    out = []
    if mode == "OFF":
        return out
    if mode in ("FLOOD", "MIST"):
        kind = FLOOD if mode == "FLOOD" else MIST
        keys = list(spindle_keys) + [(program_end, 0.0)]
        on = [(t0, min(t1, program_end)) for (t0, rpm), (t1, _r) in zip(keys, keys[1:])
              if abs(rpm) > 1e-9 and t1 > t0]
        return [(a, b, kind) for a, b in merge(on)]
    start = {FLOOD: None, MIST: None}
    raw = {FLOOD: [], MIST: []}
    for t, m in m_times:
        m = int(m)
        if flood_code and m == flood_code and start[FLOOD] is None:
            start[FLOOD] = t
        if mist_code and m == mist_code and start[MIST] is None:
            start[MIST] = t
        if m == 9 or (off_code and m == off_code):
            for k in (FLOOD, MIST):
                if start[k] is not None:
                    raw[k].append((start[k], t))
                    start[k] = None
    for k in (FLOOD, MIST):
        if start[k] is not None:
            raw[k].append((start[k], program_end))
    for k in (FLOOD, MIST):
        out += [(a, b, k) for a, b in merge(raw[k])]
    out.sort(key=lambda r: (r[0], r[2]))
    return out


def cutting_spans(pieces, top_z: float | None, end: float | None = None) -> list:
    """[(start, end)] seconds while the tool cuts: feed moves (straight or arcs) that reach down to the stock's top
    (``top_z``, mm, program coordinates; None: every feed move cuts). ``pieces``: ``Schedule.pieces``."""
    out = []
    for p in pieces:
        m = p.move
        if p.vd <= 0 or m.kind not in ("FEED", "ARC") or getattr(m, "cycle", "") == "CLEAN":
            continue
        if top_z is not None and min(m.a[2], m.b[2]) > top_z + CUT_MARGIN / MM:
            continue
        out.append((p.v0, p.v0 + p.vd))
    return merge(out)


def describe(sp, fps: float = 1.0) -> str:
    """'flood 2 times, 12.4 s in all; mist 1 time, 3.0 s' for the panel (``sp`` in frames with ``fps``)."""
    sp = np.asarray(sp, float).reshape(-1, 3)
    if not len(sp):
        return "no coolant"
    parts = []
    for k in (FLOOD, MIST):
        rows = sp[np.round(sp[:, 2]) == k]
        if len(rows):
            n = len(rows)
            sec = float((rows[:, 1] - rows[:, 0]).sum()) / fps
            parts.append(f"{KIND_NAMES[k]} {n} time{'s' if n != 1 else ''}, {sec:.1f} s")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# levels at a moment (frames)
# ---------------------------------------------------------------------------

def _rows(sp) -> np.ndarray:
    return np.asarray(sp, float).reshape(-1, 3)


def flow_at(T, sp) -> np.ndarray:
    """Per time in ``T`` (frames): 0 off, 1 flood, 2 mist (flood wins when both are on)."""
    T = np.atleast_1d(np.asarray(T, float))
    out = np.zeros(T.shape, np.int8)
    for a, b, k in _rows(sp):
        on = (T >= a - 1e-9) & (T < b - 1e-9)
        k = int(round(k))
        if k == FLOOD:
            out[on] = FLOOD
        else:
            out[on & (out == OFF)] = MIST
    return out


def in_spans(T, sp2) -> np.ndarray:
    """True per time in ``T`` inside one of the (start, end) spans ``sp2`` (frames)."""
    T = np.atleast_1d(np.asarray(T, float))
    sp2 = np.asarray(sp2, float).reshape(-1, 2)
    out = np.zeros(T.shape, bool)
    for a, b in sp2:
        out |= (T >= a - 1e-9) & (T < b - 1e-9)
    return out


def splash_level(T, sp, cut) -> np.ndarray:
    """How much splashes at the tool at ``T`` (frames): 1 while flood flows and the tool cuts, AIR_SPLASH while it
    moves in the air, mist a third of that; 0 without coolant."""
    f = flow_at(T, sp)
    c = in_spans(T, cut)
    lvl = np.where(c, 1.0, AIR_SPLASH)
    return np.where(f == FLOOD, lvl, np.where(f == MIST, lvl / 3.0, 0.0))


def _dry(t, dry: float):
    """Share of the wet level left ``t`` s after the coolant stopped (smooth, 0 after ``dry`` s)."""
    if dry <= 0:
        return np.zeros_like(t)
    x = np.clip(t / dry, 0.0, 1.0)
    return (1.0 - x) ** 2 * (1.0 + 2.0 * x)          # smoothstep down: drying starts slowly and ends softly


def _piece(level: float, target: float, dt, fps: float, rise: float, dry: float):
    """The wet level ``dt`` frames into a stretch that starts at ``level`` and heads for ``target``: it rises with
    time constant ``rise`` s, and dries (down to ``target``) within ``dry`` s."""
    dt = np.asarray(dt, float)
    if target >= level and target > 0:
        return target - (target - level) * np.exp(-dt / (max(rise, 1e-6) * fps))
    return target + (level - target) * _dry(dt / fps, dry)


def wetness(T, sp, fps: float, rise: float = RISE, dry: float = 4.0) -> np.ndarray:
    """Wet level 0 … 1 of the surfaces at ``T`` (frames), from the spans alone: while coolant flows it rises
    towards 1 (flood) or MIST_WET (mist) with time constant ``rise`` s; after it stops it dries within ``dry`` s."""
    T = np.atleast_1d(np.asarray(T, float))
    rows = _rows(sp)
    w = np.zeros(T.shape)
    if not len(rows):
        return w
    edges = sorted({float(x) for x in rows[:, :2].reshape(-1)})
    level = 0.0
    for k, t0 in enumerate(edges):
        t1 = edges[k + 1] if k + 1 < len(edges) else math.inf
        kind = flow_at([t0 + 1e-6], rows)[0]
        target = 1.0 if kind == FLOOD else (MIST_WET if kind == MIST else 0.0)
        m = (T >= t0) & (T < t1)
        if m.any():
            w[m] = _piece(level, target, T[m] - t0, fps, rise, dry)
        if t1 < math.inf:
            level = float(_piece(level, target, t1 - t0, fps, rise, dry))
    return np.clip(w, 0.0, 1.0)


def wet_keys(sp, fps: float, f_start: float = 1.0, f_end: float | None = None, rise: float = RISE,
             dry: float = 4.0, step: float = 0.2) -> list:
    """[(frame, level)] keys (linear between them) that follow ``wetness``: at every change and every ``step`` s
    while the level moves; the level between keys is off by at most a few per cent."""
    rows = _rows(sp)
    if not len(rows):
        return [(float(f_start), 0.0)]
    end = float(f_end) if f_end is not None else float(rows[:, 1].max()) + (dry + 1.0) * fps
    ts = {float(f_start), end}
    st = max(1.0, step * fps)
    for a, b, _k in rows:
        ts |= {float(a), float(b)}
        ts |= set(np.arange(a, min(b, a + 5 * rise * fps), st).tolist())     # rising
        ts |= set(np.arange(b, b + dry * fps + st, st).tolist())             # drying
    t = np.array(sorted(x for x in ts if f_start <= x <= end))
    v = wetness(t, rows, fps, rise, dry)
    keys = [(float(a), float(b)) for a, b in zip(t, v)]
    # drop keys in the middle of flat stretches
    out = [keys[0]]
    for i in range(1, len(keys) - 1):
        if abs(keys[i][1] - out[-1][1]) < 1e-4 and abs(keys[i + 1][1] - keys[i][1]) < 1e-4:
            continue
        out.append(keys[i])
    if len(keys) > 1:
        out.append(keys[-1])
    return out


# ---------------------------------------------------------------------------
# deterministic random numbers: a hash of (drop, cycle, channel)
# ---------------------------------------------------------------------------

def hash01(a, b, c: int = 0) -> np.ndarray:
    """Uniform numbers in [0, 1) from integer arrays (the same inputs always give the same numbers)."""
    a = np.asarray(a, np.uint64)
    b = np.asarray(b, np.int64).astype(np.uint64)
    with np.errstate(over="ignore"):
        x = a * np.uint64(0x9E3779B97F4A7C15) ^ (b + np.uint64(0x632BE59BD9B4E019)) * np.uint64(0xBF58476D1CE4E5B9)
        x ^= np.uint64((c * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF)
        x ^= x >> np.uint64(30)
        x *= np.uint64(0xBF58476D1CE4E5B9)
        x ^= x >> np.uint64(27)
        x *= np.uint64(0x94D049BB133111EB)
        x ^= x >> np.uint64(31)
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def _cycle(t: float, period: np.ndarray, phase: np.ndarray) -> tuple:
    """(cycle number, age in s) of drops that repeat every ``period`` s, shifted by ``phase`` (0 … 1)."""
    x = t / period + phase
    k = np.floor(x)
    return k.astype(np.int64), (x - k) * period


# ---------------------------------------------------------------------------
# nozzles and hoses (coolant space)
# ---------------------------------------------------------------------------

@dataclass
class Nozzle:
    """A nozzle at a moment: tip ``o`` and the way it points ``d`` (unit), coolant space; ``mount``: where its hose
    starts (automatic nozzles), or None (a part of the model)."""
    o: np.ndarray
    d: np.ndarray
    mount: np.ndarray | None = None
    mount_dir: np.ndarray | None = None


def ring_angles(n: int, turn: float = 0.0) -> np.ndarray:
    """Where ``n`` automatic nozzles sit round the spindle (radians from +X): behind the tool seen from the front
    (+Y side) for 2-3, all round for 4; ``turn`` turns them all."""
    n = max(1, int(n))
    if n == 1:
        a = [90.0]
    elif n == 2:
        a = [55.0, 125.0]
    elif n == 3:
        a = [30.0, 90.0, 150.0]
    else:
        a = [45.0 + 360.0 * k / n for k in range(n)]
    return np.radians(np.array(a)) + turn


def auto_nozzles(n: int, ring: float, mount_z: float, aim: np.ndarray, turn: float = 0.0,
                 standoff: float = STANDOFF, elevation: float = ELEVATION) -> list:
    """The automatic nozzles for a tool whose cutting edges are at ``aim``: a hose from the ring (radius ``ring`` at
    height ``mount_z``) to a tip ``standoff`` from the aim point, coming in at ``elevation`` above the horizontal."""
    aim = np.asarray(aim, float)
    out = []
    for a in ring_angles(n, turn):
        u = np.array([math.cos(a), math.sin(a), 0.0])
        mount = np.array([ring * u[0], ring * u[1], mount_z])
        way = u * math.cos(elevation) + np.array([0.0, 0.0, math.sin(elevation)])
        tip = aim + standoff * way
        d = -way
        mdir = np.array([0.9 * u[0], 0.9 * u[1], -0.45])          # out of the ring, then down to the tool
        out.append(Nozzle(tip, d / np.linalg.norm(d), mount, mdir / np.linalg.norm(mdir)))
    return out


def _bezier(p0, p1, p2, p3, n: int) -> np.ndarray:
    s = np.linspace(0.0, 1.0, n)[:, None]
    return ((1 - s) ** 3) * p0 + 3 * ((1 - s) ** 2) * s * p1 + 3 * (1 - s) * s * s * p2 + s ** 3 * p3


def _frames(pts: np.ndarray) -> tuple:
    """Tangents and two normals along a polyline (rotation-minimising: the rings do not twist)."""
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    n = np.zeros_like(t)
    ref = np.array([0.0, 0.0, 1.0]) if abs(t[0, 2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    v = np.cross(t[0], ref)
    n[0] = v / np.linalg.norm(v)
    for i in range(1, len(t)):
        v = n[i - 1] - t[i] * (n[i - 1] @ t[i])
        ln = np.linalg.norm(v)
        n[i] = v / ln if ln > 1e-9 else n[i - 1]
    b = np.cross(t, n)
    return t, n, b


def _tube(pts, radii, sides: int, cap0: bool = True, cap1: bool = True) -> tuple:
    """Vertices and quads/triangles of a tube through ``pts`` with a radius per point (closed at the ends)."""
    pts = np.asarray(pts, float)
    radii = np.asarray(radii, float)
    _t, n, b = _frames(pts)
    a = np.linspace(0.0, 2 * math.pi, sides, endpoint=False)
    ring = np.cos(a)[None, :, None] * n[:, None, :] + np.sin(a)[None, :, None] * b[:, None, :]
    verts = (pts[:, None, :] + radii[:, None, None] * ring).reshape(-1, 3)
    m = len(pts)
    i = np.arange(m - 1)[:, None] * sides
    j = np.arange(sides)[None, :]
    jn = (j + 1) % sides
    quads = np.stack([i + j, i + jn, i + sides + jn, i + sides + j], axis=-1).reshape(-1, 4)
    faces = [tuple(q) for q in quads.tolist()]
    extra = []
    if cap0:
        c = len(verts) + len(extra)
        extra.append(pts[0])
        faces += [(c, (k + 1) % sides, k) for k in range(sides)]
    if cap1:
        c = len(verts) + len(extra)
        extra.append(pts[-1])
        base = (m - 1) * sides
        faces += [(c, base + k, base + (k + 1) % sides) for k in range(sides)]
    if extra:
        verts = np.concatenate([verts, np.array(extra)])
    return verts, faces


def loc_line_profile(s: np.ndarray, seg: float = HOSE_SEG) -> np.ndarray:
    """Radius share (0 … 1) along a Loc-Line hose: a ball, a neck and the socket of the next segment, repeated."""
    u = np.mod(s / seg, 1.0)
    ball = np.sqrt(np.clip(1.0 - ((u - 0.35) / 0.36) ** 2, 0.0, 1.0))          # the round ball
    socket = 0.92 + 0.08 * np.clip((u - 0.72) / 0.28, 0.0, 1.0)                 # the socket's flared rim
    return np.where(u < 0.68, 0.62 + 0.38 * ball, np.where(u < 0.76, 0.66, socket))


def hose_mesh(nz: Nozzle, radius: float = HOSE_R, seg: float = HOSE_SEG, sides: int = 12) -> tuple:
    """A flexible coolant hose (Loc-Line look) from ``nz.mount`` to the nozzle's tip, ending in a round nozzle
    pointing along ``nz.d``. Returns (vertices, faces) in coolant space."""
    p0 = np.asarray(nz.mount, float)
    p3 = np.asarray(nz.o, float)
    d1 = np.asarray(nz.d, float)
    noz = 14 * MM                                   # the straight round nozzle at the end
    p3h = p3 - d1 * noz
    L = float(np.linalg.norm(p3h - p0))
    p1 = p0 + np.asarray(nz.mount_dir, float) * max(0.6 * L, 45 * MM)
    p2 = p3h - d1 * max(0.5 * L, 40 * MM)
    curve = _bezier(p0, p1, p2, p3h, 80)
    seglen = np.linalg.norm(np.diff(curve, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seglen)])
    n = max(8, int(s[-1] / seg * 8))
    ss = np.linspace(0.0, s[-1], n)
    pts = np.stack([np.interp(ss, s, curve[:, k]) for k in range(3)], axis=1)
    rad = radius * loc_line_profile(ss, seg)
    v0, f0 = _tube(pts, rad, sides, cap0=True, cap1=False)
    # the nozzle: a short cone from the hose's last socket to a small round opening
    k = 6
    t = np.linspace(0.0, 1.0, k)
    npts = p3h[None, :] + (t * noz)[:, None] * d1[None, :]
    nrad = radius * (0.95 - 0.55 * t)
    v1, f1 = _tube(npts, nrad, sides, cap0=False, cap1=True)
    off = len(v0)
    faces = f0 + [tuple(x + off for x in f) for f in f1]
    return np.concatenate([v0, v1]), faces


def ring_mesh(radius: float, z: float, sides: int = 40) -> tuple:
    """The coolant ring on the spindle nose that holds the automatic hoses: a flat round block."""
    h = 7 * MM
    w = 3.5 * MM
    a = np.linspace(0.0, 2 * math.pi, sides, endpoint=False)
    c, s = np.cos(a), np.sin(a)
    verts = []
    for r, zz in ((radius - w, z - h / 2), (radius + w, z - h / 2), (radius + w, z + h / 2), (radius - w, z + h / 2)):
        verts.append(np.stack([r * c, r * s, np.full(sides, zz)], axis=1))
    verts = np.concatenate(verts)
    faces = []
    for q in range(4):
        q1 = (q + 1) % 4
        for k in range(sides):
            k1 = (k + 1) % sides
            faces.append((q * sides + k, q * sides + k1, q1 * sides + k1, q1 * sides + k))
    return verts, faces


# ---------------------------------------------------------------------------
# the liquid at a moment
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """What to draw at one moment: the jets as a mesh, the drops as points with a radius each."""
    verts: np.ndarray
    faces: list
    drops: np.ndarray
    sizes: np.ndarray


def jet_speed(flow: float) -> float:
    """m/s at the nozzle: a gentle flood stream is slow, full flood faster."""
    return 1.4 + 2.6 * float(flow)


def jet_radius(flow: float) -> float:
    return (0.7 + 1.5 * float(flow)) * MM


def _jet_path(o, d, target, g, speed: float, n: int) -> tuple:
    """Points of the stream from ``o`` (pointing ``d``) towards ``target`` and the distance along it (sag under
    gravity ``g``); it ends at the target's distance along ``d``."""
    o = np.asarray(o, float)
    d = np.asarray(d, float)
    L = float(np.dot(np.asarray(target, float) - o, d))
    L = min(max(L, 5 * MM), 0.4)
    s = np.linspace(0.0, L, n)
    tt = s / max(speed, 0.1)
    pts = o[None, :] + s[:, None] * d[None, :] + 0.5 * np.asarray(g, float)[None, :] * (tt ** 2)[:, None]
    return pts, s, L


# ---------------------------------------------------------------------------
# the tool's speed (task 0257)
# ---------------------------------------------------------------------------

def rim_speed(rpm: float, radius: float) -> float:
    """m/s at the tool's rim: |rpm| * 2 pi / 60 * radius."""
    return abs(float(rpm)) * 2.0 * math.pi / 60.0 * float(radius)


def regime(v: float) -> str:
    """The look at rim speed ``v`` (m/s): 'film' (wears the tool, sheds streams), 'streams' (big drops), 'spray',
    'mist' (mist-like spray)."""
    if v < FILM_V:
        return "film"
    if v < STREAM_V:
        return "streams"
    if v < MIST_V:
        return "spray"
    return "mist"


def drop_diameter(v, radius: float, sigma: float = SIGMA):
    """Typical drop diameter (m) thrown off a tool of ``radius`` at rim speed ``v``: the spinning-disc rule
    d = 3.8 * sqrt(sigma * r / rho) / v (Walton & Prewett), between DROP_MIN and DROP_MAX. A D10: 2.4 mm (capped) at
    1,000 rpm, 0.55 mm at 6,000, 0.22 mm at 15,000."""
    v = np.maximum(np.asarray(v, float), 1e-3)
    d = 3.8 * math.sqrt(sigma * max(float(radius), 1e-4) / RHO) / v
    return np.clip(d, DROP_MIN, DROP_MAX)


def drag_time(d, v):
    """s: how quickly a drop of diameter ``d`` flying at ``v`` is slowed by the air (its velocity relaxes towards
    falling with e^(-t/tau)): Stokes with the Schiller-Naumann correction at its start speed. Fine mist stops within
    centimetres, big drops fly on."""
    d = np.asarray(d, float)
    re = RHO_AIR * np.asarray(v, float) * d / MU_AIR
    return RHO * d * d / (18.0 * MU_AIR * (1.0 + 0.15 * re ** 0.687))


def film_share(v: float) -> float:
    """Share of the liquid that wears the tool as a turning film: 1 below 0.5 m/s, 0 above 1.5 m/s (half at
    FILM_V)."""
    return float(np.clip((FILM_V + 0.5 - v) / 1.0, 0.0, 1.0))


def deflect_share(v: float, flow: float) -> float:
    """Share of each jet the air layer turning with the tool deflects and atomises before it reaches the tool:
    (v - AIR_V) / (v - AIR_V + 2 * jet speed), 0 below AIR_V, at most DEFLECT_MAX. A faster jet (more flow) gets
    through better. A D10 with full flood: 0 at 9,000 rpm, 26 % at 15,000, 67 % at 40,000."""
    x = float(v) - AIR_V
    if x <= 0:
        return 0.0
    return float(min(DEFLECT_MAX, x / (x + 2.0 * jet_speed(flow))))


def _fly(p0, v0, age, g, tau):
    """Where a drop is ``age`` s after it left ``p0`` at ``v0``, slowed by the air (relaxation time ``tau``) and
    pulled by ``g``: v(t) = g tau + (v0 - g tau) e^(-t/tau)."""
    g = np.asarray(g, float)[None, :]
    tau = np.asarray(tau, float)[:, None]
    a = np.asarray(age, float)[:, None]
    e = 1.0 - np.exp(-a / tau)
    return p0 + g * tau * a + (v0 - g * tau) * tau * e


def _tangent(radial: np.ndarray, spin: float) -> np.ndarray:
    """The turning direction at a point ``radial`` (unit, horizontal) from the axis: M3 (spin +1) is clockwise seen
    from above."""
    return np.stack([radial[..., 1], -radial[..., 0], np.zeros(radial.shape[:-1])], axis=-1) * spin


def _bend(s, s_hit: float, share: float, tool_r: float) -> np.ndarray:
    """How far (m) the jet is pushed along the turning direction at distance ``s`` along it: nothing before the bend
    zone (3 + 6 * share mm before the tool), growing as a square to share * (2 + 3 * r/5 mm) at the tool."""
    if share <= 0:
        return np.zeros_like(np.asarray(s, float))
    lb = (3.0 + 6.0 * share) * MM
    u = np.clip((np.asarray(s, float) - (s_hit - lb)) / lb, 0.0, 1.2)      # (it stops at the tool)
    return share * (2.0 * MM + 0.6 * tool_r) * u * u


def jet(nz: Nozzle, target, T: float, fps: float, flow: float, g, seed: int = 0, draft: bool = False,
        sides: int = 10, deflect: float = 0.0, spin: float = 1.0, tool_r: float = 5 * MM, rim_v: float = 0.0) -> Frame:
    """One flood stream at frame ``T``: a rippling tube from the nozzle to the tool, drops where it breaks up.
    ``deflect`` (task 0257, ``deflect_share``): the share the air layer turning with the tool bends away – the jet's
    end swings in the turning direction (``spin``) and thins, and a fine mist of that share swirls round the tool
    (radius ``tool_r``, rim speed ``rim_v``, its axis through ``target``, vertical)."""
    speed = jet_speed(flow)
    r0 = jet_radius(flow)
    pts, s, L = _jet_path(nz.o, nz.d, target, g, speed, 24 if draft else 48)
    target = np.asarray(target, float)
    rin = np.asarray(nz.o, float) - target
    rin[2] = 0.0
    rl = float(np.linalg.norm(rin))
    rin = rin / rl if rl > 1e-9 else np.array([1.0, 0.0, 0.0])
    tang = _tangent(rin, spin)
    hz = math.hypot(float(nz.d[0]), float(nz.d[1]))
    s_hit = max(L - tool_r / max(hz, 0.2), 0.5 * L)        # where the stream meets the tool's rim
    t = T / fps
    u = s / L
    if draft:
        rad = r0 * (1.0 + 0.35 * u)
    else:
        lam = 6.5 * MM                                   # ripples on the stream travel with the liquid
        ph = 2 * math.pi * (s / lam - t * speed / lam) + seed * 1.7
        rad = r0 * (1.0 + 0.35 * u) * (1.0 + 0.12 * np.sin(ph) + 0.05 * np.sin(2.3 * ph + 1.1))
        # the stream thins where it starts to break up, just before the tool
        rad *= 1.0 - 0.35 * np.clip((u - 0.8) / 0.2, 0.0, 1.0)
    if deflect > 0:
        bend = _bend(s, s_hit, deflect, tool_r)
        pts = pts + bend[:, None] * tang[None, :]
        lb = (3.0 + 6.0 * deflect) * MM
        rad = rad * (1.0 - 0.6 * deflect * np.clip((s - (s_hit - lb)) / lb, 0.0, 1.0))
    verts, faces = _tube(pts, rad, sides)
    if draft:
        return Frame(verts, faces, np.zeros((0, 3)), np.zeros(0))
    # break-up drops: they ride along the last part of the stream with the liquid and scatter a little
    n = int(10 + 30 * flow)
    i = np.arange(n) + 1000 * (seed + 1)
    per = (0.35 * L) / speed
    phase = hash01(i, 0, 1)
    k, age = _cycle(t, per, phase)
    frac = age / per
    sd = 0.65 * L + frac * 0.4 * L
    sd = np.minimum(sd, L * 1.02)
    p = np.stack([np.interp(sd, s, pts[:, q]) for q in range(3)], axis=1)
    side = np.stack([hash01(i, k, 2 + q) - 0.5 for q in range(3)], axis=1)
    side -= (side @ nz.d)[:, None] * nz.d[None, :]
    p += side * (r0 * 3.0 * frac)[:, None]
    size = r0 * (0.35 + 0.45 * hash01(i, k, 5)) * (1.0 - 0.3 * frac)
    if deflect > 0:
        a, b = _atomised(target, rin, tool_r, T, fps, flow, deflect, spin, seed, rim_v)
        p, size = np.concatenate([p, a]), np.concatenate([size, b])
    return Frame(verts, faces, p, size)


def _atomised(target, rin, tool_r: float, T: float, fps: float, flow: float, share: float, spin: float,
              seed: int, rim_v: float) -> tuple:
    """The fine mist a deflected jet leaves (task 0257): drops born where the jet meets the air layer, carried round
    the tool by it at half the rim speed of the layer, drifting outwards and up or down a little. Returns (points,
    sizes)."""
    n = int(400 * share * (0.5 + 0.5 * flow))
    if n <= 0:
        return np.zeros((0, 3)), np.zeros(0)
    i = np.arange(n) + 9000 * (seed + 1)
    life = 0.05 + 0.12 * hash01(i, 0, 11)
    k, age = _cycle(T / fps, life, hash01(i, 0, 12))
    a0 = math.atan2(float(rin[1]), float(rin[0])) + 0.25 * (hash01(i, k, 13) - 0.5)
    r = tool_r + (1.0 + 2.5 * hash01(i, k, 14)) * MM + (0.03 + 0.12 * hash01(i, k, 15)) * age
    omega = 0.5 * max(float(rim_v), AIR_V) / r                      # the layer turns at about half the rim speed
    a = a0 - spin * omega * age                                       # M3: clockwise from above
    z = (hash01(i, k, 16) - 0.5) * 3.0 * MM + (hash01(i, k, 17) - 0.5) * 0.05 * age
    p = np.asarray(target, float)[None, :] + np.stack([r * np.cos(a), r * np.sin(a), z], axis=1)
    size = DRAWN_MIN * (0.8 + 0.4 * hash01(i, k, 18))
    return p, size


def mist(nz: Nozzle, target, T: float, fps: float, flow: float, seed: int = 0, draft: bool = False) -> Frame:
    """Mist from one nozzle at frame ``T``: a cone of tiny drops flying to the tool (no solid stream)."""
    n = 0 if draft else int(120 + 280 * flow)
    if n == 0:
        return Frame(np.zeros((0, 3)), [], np.zeros((0, 3)), np.zeros(0))
    o = np.asarray(nz.o, float)
    d = np.asarray(nz.d, float)
    L = float(np.dot(np.asarray(target, float) - o, d))
    L = min(max(L, 5 * MM), 0.4) * 1.1
    speed = 6.0
    i = np.arange(n) + 5000 * (seed + 1)
    per = L / speed
    k, age = _cycle(T / fps, per * (0.8 + 0.4 * hash01(i, 0, 1)), hash01(i, 0, 2))
    s = age * speed
    e1 = np.cross(d, [0.0, 0.0, 1.0] if abs(d[2]) < 0.9 else [1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    a = 2 * math.pi * hash01(i, k, 3)
    r = math.tan(math.radians(9)) * s * np.sqrt(hash01(i, k, 4))
    p = o[None, :] + s[:, None] * d[None, :] + (r * np.cos(a))[:, None] * e1 + (r * np.sin(a))[:, None] * e2
    size = (0.06 + 0.1 * hash01(i, k, 5)) * MM
    return Frame(np.zeros((0, 3)), [], p, size)


def splash(tip, radius: float, reach: float, T: float, fps: float, level_at, flow: float, g, spin: float = 1.0,
           floor: float | None = None, n_max: int = 700, draft: bool = False, rpm: float | None = None,
           band: float = AIM_UP, deflect: float = 0.0) -> Frame:
    """Drops thrown off the turning tool at frame ``T`` (task 0257). ``tip``: the tool's tip (coolant space),
    ``radius``: its radius, ``reach``: how far up the flutes the liquid wets it, ``rpm``: the spindle's speed (signed,
    + = M3; None: a rim speed of LEGACY_V), ``band``: the height above the tip where the jets meet the tool,
    ``deflect``: the share of the jets the air layer took away (less reaches the tool). ``level_at(times in frames)``
    -> 0 … 1 splash at those moments (a drop is only there if it was thrown while coolant flowed). Drops end where
    they fall below ``floor`` (the part's top; default: a little below the tip) or fly out of the picture.

    The drops leave in a flat band at ``band`` at about the rim speed (``rim_speed``, at most SPLASH_CAP), mostly in
    the turning direction with an outward share, as big as ``drop_diameter`` says, slowed by the air
    (``drag_time``). Below FILM_V a share (``film_share``) wears the tool as a film turning with it and running down
    the flutes, and sheds from FLUTES points on the flute edges that turn with the tool: streams."""
    empty = Frame(np.zeros((0, 3)), [], np.zeros((0, 3)), np.zeros(0))
    if draft or n_max <= 0 or flow <= 0:
        return empty
    if rpm is None:
        v = LEGACY_V
        omega = v / max(radius, 1e-4)
    else:
        v = rim_speed(rpm, radius)
        omega = abs(float(rpm)) * 2.0 * math.pi / 60.0
        if abs(rpm) > 1e-9:
            spin = 1.0 if rpm > 0 else -1.0
    fs = film_share(v)
    tip = np.asarray(tip, float)
    t = T / fps
    reach = max(float(reach), band)
    out = [_film(tip, radius, reach, band, T, fps, level_at, flow, spin, omega, fs)] if fs > 0 else []
    # thrown drops: a fast tool throws more, finer ones
    n = int(n_max * (0.35 + 0.65 * flow) * (1.0 + float(np.clip((v - STREAM_V) / 6.0, 0.0, 1.0))))
    i = np.arange(n)
    # s each drop flies (then a new one from the tool); fast drops are out of the picture sooner, so the tool throws
    # them more often: as many show near the tool at any speed
    life = (0.06 + 0.2 * hash01(i, 0, 1)) / (1.0 + v / 2.0)
    k, age = _cycle(t, life, hash01(i, 0, 2))
    born = (t - age) * fps
    keep = hash01(i, k, 3) < np.asarray(level_at(born), float) * (1.0 - deflect)
    if keep.any():
        i, k, age = i[keep], k[keep], age[keep]
        shed = hash01(i, k, 9) < fs
        a = 2 * math.pi * hash01(i, k, 4)
        if shed.any():                                   # a slow tool sheds from its flute edges, turning with it
            q = np.floor(hash01(i, k, 10) * FLUTES)
            a_shed = 2 * math.pi * q / FLUTES - spin * omega * (t - age) + 0.12 * (hash01(i, k, 11) - 0.5)
            a = np.where(shed, a_shed, a)
        radial = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], axis=1)
        tang = _tangent(radial, spin)
        bw = 2.0 * jet_radius(flow) + 1.0 * MM            # the band's height: about the jets' width
        h = np.where(shed, reach * hash01(i, k, 5), band + (hash01(i, k, 5) - 0.5) * bw)
        p0 = tip[None, :] + radial * (radius * 1.02) + np.array([0.0, 0.0, 1.0])[None, :] * h[:, None]
        sp = np.minimum(v * (0.85 + 0.3 * hash01(i, k, 6)), SPLASH_CAP)
        sp = np.where(shed, v * (1.0 + 0.15 * hash01(i, k, 6)) + 0.05, sp)
        out_share = 0.15 + 0.2 * hash01(i, k, 7)
        vz = 0.12 * (hash01(i, k, 12) - 0.45)            # flat: a little up or down, not a cloud
        d = (tang + out_share[:, None] * radial + vz[:, None] * np.array([0.0, 0.0, 1.0])[None, :])
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        vel = d * sp[:, None]
        dia = drop_diameter(v, radius) * (0.6 + 0.8 * hash01(i, k, 8) ** 2)
        dia = np.where(shed, DROP_MAX * (0.35 + 0.25 * hash01(i, k, 8)), dia)
        p = _fly(p0, vel, age, g, drag_time(dia, sp))
        fl = tip[2] - 0.5 * MM if floor is None else floor
        ok = (p[:, 2] > fl) & (np.linalg.norm(p - tip[None, :], axis=1) < FAR)
        out.append(Frame(np.zeros((0, 3)), [], p[ok], np.maximum(0.5 * dia, DRAWN_MIN)[ok]))
    return combine(out) if out else empty


def _film(tip, radius: float, reach: float, band: float, T: float, fps: float, level_at, flow: float, spin: float,
          omega: float, share: float) -> Frame:
    """The film on a slow tool (task 0257): beads on the tool's surface that turn with it and run down the flutes
    from the jets' height to the tip (turning with the flutes' helix as they go), a few rings of them."""
    n = int(160 * share * (0.5 + 0.5 * flow))
    if n <= 0:
        return Frame(np.zeros((0, 3)), [], np.zeros((0, 3)), np.zeros(0))
    i = np.arange(n) + 20000
    t = T / fps
    top = min(reach, band + 1.5 * MM)
    vdown = 0.012 + 0.02 * hash01(i, 0, 21)               # m/s down the flute
    per = top / vdown
    k, age = _cycle(t, per, hash01(i, 0, 22))
    keep = hash01(i, k, 23) < np.asarray(level_at((t - age) * fps), float)
    i, k, age, vdown = i[keep], k[keep], age[keep], vdown[keep]
    z = top - vdown * age
    q = np.floor(hash01(i, k, 24) * FLUTES)
    a = (2 * math.pi * q / FLUTES + 0.9 * hash01(i, k, 25) - spin * omega * t
         - spin * (top - z) * math.tan(HELIX) / max(radius, 1e-4))
    size = (0.2 + 0.15 * hash01(i, k, 26)) * MM * (0.7 + 0.3 * flow)
    r = radius * 1.01 + 0.5 * size
    p = np.asarray(tip, float)[None, :] + np.stack([r * np.cos(a), r * np.sin(a), z], axis=1)
    return Frame(np.zeros((0, 3)), [], p, size)


def combine(frames) -> Frame:
    verts, faces, drops, sizes = [], [], [], []
    off = 0
    for f in frames:
        if len(f.verts):
            verts.append(np.asarray(f.verts, float))
            faces += [tuple(x + off for x in face) for face in f.faces]
            off += len(f.verts)
        if len(f.drops):
            drops.append(np.asarray(f.drops, float))
            sizes.append(np.asarray(f.sizes, float))
    return Frame(np.concatenate(verts) if verts else np.zeros((0, 3)), faces,
                 np.concatenate(drops) if drops else np.zeros((0, 3)),
                 np.concatenate(sizes) if sizes else np.zeros(0))


def liquid_at(T: float, fps: float, sp, cut, nozzles: list, target, tip, radius: float, flow: float, g,
              spin: float = 1.0, draft: bool = False, reach: float = 8 * MM, rpm: float | None = None) -> Frame:
    """Everything liquid at frame ``T``: the jets (flood) or mist from every nozzle, and the splash at the tool.
    ``rpm``: the spindle's speed at ``T`` (signed, + = M3; task 0257) – it sets the splash, the film and how much of
    the jets the air layer turns away (None: as at a rim speed of LEGACY_V)."""
    kind = int(flow_at([T], sp)[0])
    v = LEGACY_V if rpm is None else rim_speed(rpm, radius)
    if rpm is not None and abs(rpm) > 1e-9:
        spin = 1.0 if rpm > 0 else -1.0
    deflect = deflect_share(v, flow) if kind == FLOOD else 0.0
    band = float(np.asarray(target, float)[2] - np.asarray(tip, float)[2])
    parts = []
    if kind == FLOOD:
        parts += [jet(nz, target, T, fps, flow, g, seed=k, draft=draft, deflect=deflect, spin=spin, tool_r=radius,
                      rim_v=v) for k, nz in enumerate(nozzles)]
    elif kind == MIST:
        parts += [mist(nz, target, T, fps, flow, seed=k, draft=draft) for k, nz in enumerate(nozzles)]
    parts.append(splash(tip, radius, reach, T, fps, lambda tt: splash_level(tt, sp, cut), flow, g, spin,
                        draft=draft, rpm=rpm, band=band, deflect=deflect))
    return combine(parts)
