"""Prototype 0251: the one comparison scene "S" every method runs (invented test model, no machine).

A block 120 x 80 x 30 mm with a closed pocket (40 x 30, 8 deep) and an open slot (10 wide, 6 deep, running out at the
block's +x end) sits on a plate 300 x 160 x 15 mm with a groove along X (a T-slot's opening, 14 wide, 12 deep, open at
both ends). The plate is the moving table: still for 3 s, then +60 mm in X at 0.15 m/s (hard start and stop), back at
4.4 s. A jet pours 2 l/min onto the pocket from 0.2 to 3.0 s. Under the table a fixed tray (500 x 300, 2 deg slope)
runs to a drain hole (diameter 20 mm). 8 s at 24 fps.

World: metres, z up. The plate's frame: origin at the middle of its top, x along the travel.
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import liquid as L  # noqa: E402

MM = 1e-3
FPS = 24
SECONDS = 8
FRAMES = SECONDS * FPS
PLATE = (300 * MM, 160 * MM, 15 * MM)
BLOCK = (120 * MM, 80 * MM, 30 * MM)
POCKET = (-45 * MM, -5 * MM, -15 * MM, 15 * MM, 8 * MM)      # x0, x1, y0, y1, depth
SLOT = (10 * MM, 60 * MM, -5 * MM, 5 * MM, 6 * MM)
GROOVE = (55 * MM, 14 * MM, 12 * MM)                        # y, width, depth
PLATE_Z = 0.10                                              # the plate's top in the world
TRAY = (-0.25, 0.25, -0.15, 0.15, 2.0, 40 * MM)             # x0, x1, y0, y1, slope deg, wall height
DRAIN = (-0.23, 0.0, 10 * MM)                               # x, y, radius
JET = ((-25 * MM, 0.0, PLATE_Z + 0.10), 2.0 / 1000 / 60, 0.2, 3.0)   # world point, m^3/s, from, to (s)


def plate_x(t):
    """The table's X (m) at time t (s): hard starts and stops at 0.15 m/s."""
    v = 0.15
    up = np.clip(t - 3.0, 0, 0.4) * v
    down = np.clip(t - 4.4, 0, 0.4) * v
    return up - down


def plate_mats(frames=FRAMES + 2):
    t = np.arange(frames) / FPS
    m = L.still(frames)
    m[:, 0, 3] = plate_x(t)
    m[:, 2, 3] = PLATE_Z
    return m


def plate_bed(cell):
    """Heights over the plate's top (m) at the cell centres; x from -150 mm, y from -80 mm."""
    nx = int(round(PLATE[0] / cell))
    ny = int(round(PLATE[1] / cell))
    x0 = -PLATE[0] / 2 + cell / 2
    y0 = -PLATE[1] / 2 + cell / 2
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell)
    bed = np.zeros((ny, nx))
    gy, gw, gd = GROOVE
    bed[np.abs(Y - gy) <= gw / 2] = -gd
    blk = (np.abs(X) <= BLOCK[0] / 2) & (np.abs(Y) <= BLOCK[1] / 2)
    bed[blk] = BLOCK[2]
    a, b, c, d, dep = POCKET
    bed[(X >= a) & (X <= b) & (Y >= c) & (Y <= d)] = BLOCK[2] - dep
    a, b, c, d, dep = SLOT
    bed[(X >= a) & (X <= b + cell) & (Y >= c) & (Y <= d) & blk] = BLOCK[2] - dep
    return bed, x0, y0


def tray_bed(cell):
    x0, x1, y0, y1, slope, wall = TRAY
    nx = int(round((x1 - x0) / cell))
    ny = int(round((y1 - y0) / cell))
    cx, cy = x0 + cell / 2, y0 + cell / 2
    X, Y = np.meshgrid(cx + np.arange(nx) * cell, cy + np.arange(ny) * cell)
    t = math.tan(math.radians(slope))
    bed = (X - x0) * t + 0.4 * np.abs(Y - DRAIN[1]) * t
    drain = np.zeros_like(bed)
    dx, dy, r = DRAIN
    hole = (X - dx) ** 2 + (Y - dy) ** 2 <= (r + cell / 2) ** 2
    drain[hole] = math.pi * r * r / hole.sum()
    return bed, cx, cy, drain


def jet_sources(f):
    p, q, a, b = JET
    t = f / FPS
    return [(p, q)] if a <= t < b else []


def bake_hf(cell=1.5 * MM, tray_cell=4 * MM, out=None):
    bed, x0, y0 = plate_bed(cell)
    plate = L.Chart("plate", bed, cell, x0, y0)
    tb, tx0, ty0, drain = tray_bed(tray_cell)
    tray = L.Chart("tray", tb, tray_cell, tx0, ty0, open_edges=False, drain=drain)
    w = L.World([plate, tray], [plate_mats(), L.still(FRAMES + 2)], FPS, floor_z=-0.05, sources=jet_sources)
    D0, D1, P, R, n = [], [], [], [], []
    tot = []
    t0 = time.perf_counter()
    for f in range(FRAMES):
        D0.append(plate.depth.astype(np.float16))
        D1.append(tray.depth.astype(np.float16))
        P.append(w.P.astype(np.float32))
        R.append(w.vol.astype(np.float32))
        n.append(len(w.vol))
        tot.append(w.totals())
        w.run_frame(f)
    secs = time.perf_counter() - t0
    if out:
        np.savez_compressed(out, plate=np.array(D0), tray=np.array(D1), plate_bed=bed, tray_bed=tb,
                            plate_x0=(x0, y0, cell), tray_x0=(tx0, ty0, tray_cell),
                            drops=np.concatenate(P), vols=np.concatenate(R), counts=np.array(n),
                            mats=plate_mats(), seconds=secs)
    return w, secs, tot


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/p251/s_hf.npz"
    w, secs, tot = bake_hf(out=out)
    print("bake s", round(secs, 1), "per frame ms", round(1000 * secs / FRAMES, 1))
    for f in (0, 48, 63, 72, 96, 120, 150, 191):
        print(f, {k: round(v * 1e6, 2) for k, v in tot[f].items()})
