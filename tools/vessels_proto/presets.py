"""Vessel presets (study 0312): one row per kind of vessel, applied to a hull and adjusted. No Blender.

A preset holds what a user cannot read from a CAD model – how the vessel drives (speed, how fast it gets there,
how tight it turns, what its thrusters do), how it moves in waves (its roll period, how damped) and what it leaves in
the water (its wake class). What CAN be read from the model is measured (``hydro``): the waterline for a given
weight (or the weight for a given waterline), length and beam on the waterline, the block coefficient, the
metacentric radius and from it the roll period with the preset's centre of gravity.

Every number of a kind is a **typical** value for a generic vessel of that kind (invented, not one real ship) – the
user adjusts them. Sources for the rules of thumb: the roll period ``T = 2 C B / sqrt(GM)``, C = 0.373 + 0.023 B/d
- 0.043 L/100 (IMO 2008 Intact Stability Code, part B 2.3; L in metres), the heave and pitch natural periods
``T = 2 pi sqrt((m + a) / (rho g A_wp))`` with added mass ~ the displaced mass for heave (Faltinsen 1990, "Sea
loads on ships and offshore structures", ch. 2–3: a rough rule).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np

RHO = 1.025          # t/m^3 sea water
G = 9.81
KNOT = 0.514444


@dataclass
class Preset:
    key: str
    name: str
    what: str
    length: float              # m overall
    beam: float                # m
    draught: float             # m
    displacement: float        # t
    speed_max: float           # knots
    speed_cruise: float        # knots
    accel_s: float             # s from still to 90 % of the cruise speed
    stop_lengths: float        # stopping distance from cruise, in vessel lengths (crash stop)
    turn_diameter: float       # tactical diameter at cruise, full helm, in vessel lengths
    spin_deg_s: float          # turn on the spot (deg/s; 0 = cannot)
    side_knots: float          # sideways by thrusters (knots; 0 = cannot)
    roll_period: float         # s: natural roll period (cannot be read from CAD: it needs the centre of gravity)
    roll_damping: float        # share of critical
    propulsion: str            # what pushes it
    thrusters: list = field(default_factory=list)   # (kind, u share of L/2 from the middle, v share of B/2)
    dp: str = "none"           # none / DP1 / DP2 / DP3 (holds position by thrusters)
    wake: str = "displacement"   # displacement / semi-planing / planing / twin-hull / tow
    towed_by: str = ""         # a barge: the kind that tows it
    depth: float = 0.0         # m keel to deck edge (0 = from the hull)
    hull: str = "mono"         # mono / cat / box

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)


# typical values for invented generic vessels (the user adjusts them; tooltips say "typical")
KINDS = [
    Preset("RIB", "RIB / fast rescue boat", "a small fast boat for scale, crew or rescue",
           9.0, 3.2, 0.6, 4.0, 40, 30, 8, 1.2, 3.0, 0, 0, 2.5, 0.10, "2 outboards", [], "none", "planing",
           depth=1.4),
    Preset("CTV", "Crew transfer vessel", "a fast catamaran that brings technicians to wind turbines and pushes "
           "its bow fender onto the boat landing", 26.0, 9.5, 1.6, 120.0, 26, 22, 25, 2.0, 3.5, 12, 0, 3.5, 0.12,
           "2 waterjets", [("JET", -1.0, 0.7), ("JET", -1.0, -0.7)], "none", "twin-hull", depth=3.6, hull="cat"),
    Preset("TUG", "Harbour tug (ASD)", "a short powerful tug with two azimuths at the stern: turns on the spot, "
           "pushes and tows", 32.0, 12.5, 5.0, 800.0, 13, 10, 45, 1.0, 1.6, 15, 3.0, 7.0, 0.06,
           "2 azimuth thrusters", [("AZIMUTH", -0.85, 0.5), ("AZIMUTH", -0.85, -0.5)], "none", "displacement",
           depth=5.5),
    Preset("MULTICAT", "Multicat / workboat", "a flat working boat with a crane and an open deck (anchors, buoys, "
           "survey)", 26.0, 12.0, 2.8, 450.0, 10, 8, 50, 1.2, 2.5, 6, 1.2, 6.0, 0.07, "2 shafts + bow tunnel",
           [("SHAFT", -0.9, 0.4), ("SHAFT", -0.9, -0.4), ("TUNNEL", 0.8, 0.0)], "none", "displacement", depth=3.6),
    Preset("PSV", "Platform supply vessel", "brings cargo, fuel and water to platforms; holds position on DP",
           85.0, 19.0, 6.5, 6500.0, 14, 12, 120, 3.0, 3.5, 4, 1.0, 10.0, 0.05, "2 azimuths + 2 bow tunnels",
           [("AZIMUTH", -0.9, 0.5), ("AZIMUTH", -0.9, -0.5), ("TUNNEL", 0.8, 0.0), ("TUNNEL", 0.7, 0.0)], "DP2",
           "displacement", depth=8.0),
    Preset("CLV", "Cable-lay / construction vessel", "the demo's ship class: a big DP vessel that works slowly",
           124.0, 28.0, 7.0, 15000.0, 12, 10, 180, 4.0, 4.0, 3, 0.8, 11.0, 0.03, "3 azimuths + 3 bow tunnels",
           [("AZIMUTH", -0.9, 0.5), ("AZIMUTH", -0.9, -0.5), ("AZIMUTH", 0.5, 0.0), ("TUNNEL", 0.85, 0.0),
            ("TUNNEL", 0.78, 0.0), ("TUNNEL", 0.71, 0.0)], "DP2", "displacement", depth=10.0),
    Preset("BARGE", "Barge under tow", "a flat deck barge with cargo, towed on a wire by a tug", 90.0, 27.0, 3.0,
           6000.0, 0, 6, 0, 0, 0, 0, 0, 8.0, 0.08, "none (towed)", [], "none", "tow", towed_by="TUG", depth=6.0,
           hull="box"),
    Preset("JACKUP", "Jack-up in transit", "an installation jack-up moving with its legs up: slow and high",
           130.0, 50.0, 5.5, 28000.0, 9, 7, 300, 5.0, 4.0, 2, 0.7, 12.0, 0.04, "4 azimuths",
           [("AZIMUTH", -0.8, 0.6), ("AZIMUTH", -0.8, -0.6), ("AZIMUTH", 0.8, 0.6), ("AZIMUTH", 0.8, -0.6)], "DP2",
           "displacement", depth=10.0, hull="box"),
    Preset("YACHT", "Yacht for scale", "a 12 m motor-sailing yacht: shows how big the rest is", 12.0, 4.0, 2.0, 9.0,
           8, 6, 20, 2.0, 3.0, 0, 0, 3.5, 0.08, "1 shaft", [("SHAFT", -0.7, 0.0)], "none", "displacement",
           depth=2.6),
]
BY_KEY = {p.key: p for p in KINDS}


# ---------------------------------------------------------------------------
# hydrostatics from the hull's mesh
# ---------------------------------------------------------------------------

def ray_hits(verts, faces, step: float | None = None):
    """Vertical rays on a grid ``step`` m apart: for each ray the sorted z where it crosses the surface.
    Returns (xs, ys, list of arrays)."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    if step is None:
        span = verts[:, :2].max(axis=0) - verts[:, :2].min(axis=0)
        step = max(0.05, float(span.max()) / 250.0)
    lo = verts[:, :2].min(axis=0)
    hi = verts[:, :2].max(axis=0)
    xs = np.arange(lo[0] + step / 2, hi[0], step)
    ys = np.arange(lo[1] + step / 2, hi[1], step)
    hits = [[[] for _ in ys] for _ in xs]
    tmin = np.minimum(np.minimum(a, b), c)[:, :2]
    tmax = np.maximum(np.maximum(a, b), c)[:, :2]
    for t in range(len(faces)):
        i0 = int(np.searchsorted(xs, tmin[t, 0]))
        i1 = int(np.searchsorted(xs, tmax[t, 0], side="right"))
        j0 = int(np.searchsorted(ys, tmin[t, 1]))
        j1 = int(np.searchsorted(ys, tmax[t, 1], side="right"))
        if i0 >= i1 or j0 >= j1:
            continue
        px, py = np.meshgrid(xs[i0:i1], ys[j0:j1], indexing="ij")
        A, B, C = a[t], b[t], c[t]
        d = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((B[1] - C[1]) * (px - C[0]) + (C[0] - B[0]) * (py - C[1])) / d
        l2 = ((C[1] - A[1]) * (px - C[0]) + (A[0] - C[0]) * (py - C[1])) / d
        l3 = 1 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        z = l1 * A[2] + l2 * B[2] + l3 * C[2]
        for ii, jj in zip(*np.nonzero(inside)):
            hits[i0 + ii][j0 + jj].append(z[ii, jj])
    return xs, ys, [[np.unique(np.round(np.array(h), 7)) for h in row] for row in hits]


@dataclass
class Hydro:
    waterline: float           # z of the waterline (m)
    volume: float              # m^3 under it
    displacement: float        # t
    lwl: float
    bwl: float
    awp: float                 # waterplane area m^2
    kb: float                  # centre of buoyancy above the keel (m)
    bmt: float                 # transverse metacentric radius I_T / V (m)
    bml: float
    cb: float                  # block coefficient
    keel: float


def hydro(rays, zwl: float) -> Hydro:
    xs, ys, hits = rays
    step = xs[1] - xs[0]
    cell = step * (ys[1] - ys[0])
    vol, mz, awp, ix, iy, xsum, keel = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.inf
    xw, yw = [], []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            h = hits[i][j]
            if len(h) < 2:
                continue
            keel = min(keel, h[0])
            for k in range(0, len(h) - 1, 2):
                z0, z1 = h[k], min(h[k + 1], zwl)
                if z1 > z0:
                    L = z1 - z0
                    vol += L * cell
                    mz += L * cell * (z0 + z1) / 2
                    xsum += L * cell * x
                if h[k] < zwl < h[k + 1]:
                    awp += cell
                    iy += cell * y * y
                    ix += cell * x * x
                    xw.append(x)
                    yw.append(y)
    if vol <= 0 or not xw:
        return Hydro(zwl, 0, 0, 0, 0, 0, 0, 0, 0, 0, keel)
    xc = sum(xw) / len(xw)
    il = ix - awp * xc * xc
    lwl = max(xw) - min(xw) + step
    bwl = max(yw) - min(yw) + step
    T = zwl - keel
    return Hydro(zwl, vol, vol * RHO, lwl, bwl, awp, mz / vol - keel, iy / vol, il / vol,
                 vol / max(lwl * bwl * T, 1e-9), keel)


def waterline_for(rays, displacement_t: float) -> Hydro:
    """The waterline at which the hull displaces ``displacement_t`` tonnes (bisection)."""
    xs, ys, hits = rays
    zs = [h for row in hits for hh in row for h in hh]
    lo, hi = min(zs), max(zs)
    for _ in range(50):
        mid = (lo + hi) / 2
        if hydro(rays, mid).displacement < displacement_t:
            lo = mid
        else:
            hi = mid
    return hydro(rays, (lo + hi) / 2)


def roll_period(beam: float, draught: float, length: float, gm: float) -> float:
    """IMO 2008 IS Code rule of thumb (s)."""
    c = 0.373 + 0.023 * beam / max(draught, 0.1) - 0.043 * length / 100.0
    return 2.0 * c * beam / math.sqrt(max(gm, 0.05))


def gm_for(beam: float, draught: float, length: float, period: float) -> float:
    """The GM that gives ``period`` by the IMO rule (its inverse)."""
    c = 0.373 + 0.023 * beam / max(draught, 0.1) - 0.043 * length / 100.0
    return (2.0 * c * beam / max(period, 0.1)) ** 2


def heave_period(h: Hydro) -> float:
    m = h.volume * RHO * 1000.0
    return 2 * math.pi * math.sqrt(2.0 * m / (RHO * 1000.0 * G * max(h.awp, 1e-6)))


def apply(p: Preset, verts, faces, depth: float | None = None, use: str = "displacement") -> dict:
    """What applying preset ``p`` to this hull gives: the waterline (from the preset's displacement, or the
    displacement from the preset's draught), GM from the preset's KG share, the roll / heave periods."""
    rays = ray_hits(verts, faces)
    if use == "displacement":
        h = waterline_for(rays, p.displacement)
    else:
        keel = min(hh[0] for row in rays[2] for hh in row if len(hh))
        h = hydro(rays, keel + p.draught)
    T = h.waterline - h.keel
    gm = gm_for(h.bwl, T, h.lwl, p.roll_period)           # what the preset's roll period means for this hull
    kg = h.kb + h.bmt - gm
    dep = depth if depth is not None else float(verts[:, 2].max() - h.keel)
    return {"waterline_z": h.waterline, "draught": T, "displacement_t": h.displacement, "lwl": h.lwl,
            "bwl": h.bwl, "cb": h.cb, "awp": h.awp, "kb": h.kb, "bmt": h.bmt, "kg": kg, "gm": gm,
            "kg_share": kg / max(dep, 1e-6), "roll_period": p.roll_period, "heave_period": heave_period(h)}


def save(p: Preset, level: str, folder: str) -> str:
    """Write a user's preset as ``<folder>/<level>/<name>.fresing-vessel.json`` (the app: 0272's Locations kind
    "Vessel presets", levels Company / Department / Mine)."""
    import os
    d = os.path.join(folder, level)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, p.name.replace("/", "-") + ".fresing-vessel.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(p.to_json())
    return path
