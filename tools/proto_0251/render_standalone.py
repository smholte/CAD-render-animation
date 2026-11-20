"""Prototype 0251: short videos of the stand-alone tests (standalone.npz from standalone.py), EEVEE by default.

    ~/venv/bin/python tools/proto_0251/render_standalone.py /tmp/p251/standalone.npz <out dir> [engine] [tests]
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl  # noqa: E402

MM = 1e-3
WALLS = {"t4": 30 * MM, "t5": 25 * MM, "t6": 25 * MM}
VIEW = {"t1": dict(elev=40, azim=-60), "t2": dict(elev=40, azim=-50), "t3": dict(elev=22, azim=-80),
        "t4": dict(elev=45, azim=-60), "t5": dict(elev=30, azim=-70), "t6": dict(elev=35, azim=-65)}
MAXF = 96


def padded(bed, wall):
    b = np.pad(bed, 2, constant_values=np.nan)
    b[:2, :] = b[-2:, :] = wall
    b[:, :2] = b[:, -2:] = wall
    b[2:-2, 2:-2] = bed
    return b


def one(D, t, out, eng):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bed = D[f"{t}_bed"]
    cell = float(D[f"{t}_cell"])
    store = D[f"{t}_store"]
    ny, nx = bed.shape
    x0, y0 = -nx * cell / 2 + cell / 2, -ny * cell / 2 + cell / 2
    carrier = bpy.data.objects.new("Carrier", None)
    sc.collection.objects.link(carrier)
    alu = bl.metal("Aluminium", (0.62, 0.64, 0.66), 0.32)
    if t in WALLS:
        sb = padded(np.nan_to_num(bed, nan=-0.005), WALLS[t])
        if t == "t4":
            # the drain hole: the cells with the lowest bed near x = 0
            pass
        bl.solid_from_bed("Part", sb, cell, x0 - 2 * cell, y0 - 2 * cell, float(np.nanmin(bed)) - 0.012, alu, carrier)
    else:
        bl.solid_from_bed("Part", bed, cell, x0, y0, float(np.nanmin(bed)) - 0.012, alu, carrier)
    liq = bl.liquid_material()
    g = bl.liquid_grid("Liquid", bed, cell, x0, y0, liq, carrier)
    if t == "t4":
        bpy.ops.mesh.primitive_cylinder_add(radius=10 * MM, depth=0.004, location=(x0 + 2 * MM, 0.0, -0.0005))
        bpy.context.object.data.materials.append(bl.metal("Hole", (0.01, 0.01, 0.01), 0.6, 0.0))
    size = max(nx, ny) * cell
    v = VIEW[t]
    bl.studio((0, 0, 0), dist=size * 1.55, lens=40, res=(480, 270), **v)
    bl.engine(eng, 24 if eng == "CYCLES" else 32)
    n = len(store)
    pick = np.unique(np.linspace(0, n - 1, min(n, MAXF)).round().astype(int))
    ang = D.get(f"{t}_angles") if f"{t}_angles" in D.files else None
    xs = D[f"{t}_x"] if f"{t}_x" in D.files else None

    def update(k):
        i = pick[k]
        M = np.eye(4)
        if ang is not None:
            a = math.radians(float(ang[i]))
            M[:3, :3] = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
        if xs is not None:
            M[0, 3] = float(xs[i]) - 0.04
        carrier.matrix_world = Matrix(M.tolist())
        bl.set_liquid(g, store[i].astype(np.float32))
    sc.frame_start, sc.frame_end = 0, len(pick) - 1
    folder = os.path.join(out, t)
    ups = []
    for k in range(min(10, len(pick))):
        a = time.perf_counter()
        update(k)
        ups.append(time.perf_counter() - a)
    times = bl.render_frames(range(len(pick)), folder, update)
    fps = max(6, round(len(pick) / (n * 2 / 24)))
    size = bl.mp4(folder, os.path.join(out, f"{t}_{eng.lower()}.mp4"), fps=fps)
    return dict(test=t, frames=len(pick), render_s=float(np.median(times)), first_s=times[0],
                update_ms=1000 * float(np.median(ups)), mp4=size, fps=fps)


def main():
    npz, out = sys.argv[1:3]
    eng = sys.argv[3] if len(sys.argv) > 3 else "EEVEE"
    tests = sys.argv[4].split(",") if len(sys.argv) > 4 else ["t1", "t2", "t3", "t4", "t5", "t6"]
    D = np.load(npz)
    res = [one(D, t, out, eng) for t in tests]
    json.dump(res, open(os.path.join(out, f"times_{eng.lower()}.json"), "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
