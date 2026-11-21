"""Prototype 0251: render the comparison scene S with one method's bake.

    ~/venv/bin/python tools/proto_0251/render_s.py hf /tmp/p251/s_hf.npz /tmp/p251/out_s_hf [frames] [engine]

Method hf: the height field (liquid grids on the plate and the tray + drops). pbf: particles (meshed by Geometry
Nodes). flip: Blender's liquid simulation (its own bake; see flip_s.py). ``frames``: "all", or a list "40,80,120".
"""

from __future__ import annotations

import json
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl  # noqa: E402
import scene_s as S  # noqa: E402

MM = 1e-3


def build_static():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = S.FPS
    sc.frame_start, sc.frame_end = 0, S.FRAMES - 1
    alu = bl.metal("Aluminium", (0.62, 0.64, 0.66), 0.32)
    iron = bl.metal("Cast iron", (0.08, 0.085, 0.09), 0.5, 0.5)
    steel = bl.metal("Tray steel", (0.25, 0.26, 0.27), 0.45, 0.8)
    carrier = bpy.data.objects.new("Table", None)
    sc.collection.objects.link(carrier)
    cell = 0.75 * MM
    bed, x0, y0 = S.plate_bed(cell)
    blk = bed.copy()
    plate_only = np.where(bed > 1 * MM, 0.0, bed)
    bl.solid_from_bed("Plate", plate_only, cell, x0, y0, -S.PLATE[2], iron, carrier)
    # the block on its own (so it gets its own colour): its cells only
    m = bed > 1 * MM
    js, is_ = np.nonzero(m)
    sub = blk[js.min():js.max() + 1, is_.min():is_.max() + 1]
    bl.solid_from_bed("Block", sub, cell, x0 + is_.min() * cell, y0 + js.min() * cell, 0.0, alu, carrier)
    # the tray: its sloped floor + walls
    tb, tx0, ty0, drain = S.tray_bed(2 * MM)
    tray_floor = np.where(drain > 0, np.nan, tb)
    bl.solid_from_bed("Tray floor", tray_floor, 2 * MM, tx0, ty0, -0.01, steel)
    x0t, x1t, y0t, y1t, _, wall = S.TRAY
    for nm, (cx, cy, sx, sy) in {"Wall -x": (x0t - 0.002, 0, 0.004, y1t - y0t + 0.008),
                                 "Wall +x": (x1t + 0.002, 0, 0.004, y1t - y0t + 0.008),
                                 "Wall -y": (0, y0t - 0.002, x1t - x0t, 0.004),
                                 "Wall +y": (0, y1t + 0.002, x1t - x0t, 0.004)}.items():
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, wall / 2 - 0.005))
        o = bpy.context.object
        o.name = nm
        o.scale = (sx, sy, wall + 0.01)
        o.data.materials.append(steel)
    # the drain pipe under the hole
    bpy.ops.mesh.primitive_cylinder_add(radius=S.DRAIN[2], depth=0.06, location=(S.DRAIN[0], S.DRAIN[1], -0.03))
    pipe = bpy.context.object
    pipe.data.materials.append(bl.metal("Pipe", (0.02, 0.02, 0.02), 0.5, 0.0))
    # the jet's nozzle (a stand-in)
    p = S.JET[0]
    bpy.ops.mesh.primitive_cylinder_add(radius=3 * MM, depth=0.03, location=(p[0], p[1], p[2] + 0.015))
    bpy.context.object.data.materials.append(bl.metal("Nozzle", (0.9, 0.5, 0.1), 0.4, 0.0))
    mats = S.plate_mats()

    def place(f):
        carrier.matrix_world = __import__("mathutils").Matrix(mats[min(f, len(mats) - 1)].tolist())
    bl.studio((0.0, 0.0, 0.07), dist=0.55, elev=36, azim=-58, lens=40)
    return sc, carrier, place


def jet_drops(f):
    """The jet drawn as a stream of drops from the nozzle down to the liquid (deterministic: from the frame)."""
    p, q, a, b = S.JET
    t = f / S.FPS
    if not (a <= t < b):
        return np.zeros((0, 3)), np.zeros(0)
    z = np.arange(p[2], S.PLATE_Z + 0.02, -2.2 * MM)
    ph = (f * 0.37) % 1.0
    z = z - ph * 2.2 * MM
    P = np.stack([np.full_like(z, p[0]), np.full_like(z, p[1]), z], 1)
    P[:, :2] += 0.25 * MM * np.stack([np.sin(z * 900 + f), np.cos(z * 700 + f)], 1)
    return P, np.full(len(z), 1.3 * MM)


def setup_hf(npz, sc, carrier, place):
    D = dict(np.load(npz))          # into memory once (an npz decompresses a whole array at every access)
    liq = bl.liquid_material()
    dm = bl.drop_material()
    x0, y0, cell = D["plate_x0"]
    plate = bl.liquid_grid("Liquid plate", D["plate_bed"], cell, x0, y0, liq, carrier)
    tx0, ty0, tcell = D["tray_x0"]
    tray = bl.liquid_grid("Liquid tray", D["tray_bed"], tcell, tx0, ty0, liq)
    drops = bl.drops_object("Drops", dm)
    off = np.concatenate([[0], np.cumsum(D["counts"])])

    def update(f):
        f = min(f, len(D["plate"]) - 1)
        place(f)
        bl.set_liquid(plate, D["plate"][f].astype(np.float32))
        bl.set_liquid(tray, D["tray"][f].astype(np.float32))
        P = D["drops"][off[f]:off[f + 1]]
        V = D["vols"][off[f]:off[f + 1]]
        keep = V > 2e-10
        Pd, Rd = bl.split_drops(P[keep], V[keep])
        Pj, Rj = jet_drops(f)
        bl.set_drops(drops, np.vstack([Pd, Pj]), np.concatenate([Rd, Rj]))
    return update


def main():
    method, npz, out = sys.argv[1:4]
    frames = sys.argv[4] if len(sys.argv) > 4 else "all"
    eng = sys.argv[5] if len(sys.argv) > 5 else "CYCLES"
    sc, carrier, place = build_static()
    if method == "hf":
        update = setup_hf(npz, sc, carrier, place)
    elif method == "pbf":
        import render_pbf
        update = render_pbf.setup(npz, sc, carrier, place)
    else:
        import flip_s
        update = flip_s.setup_render(npz, sc, carrier, place)
    bl.engine(eng, 24 if eng == "CYCLES" else 32)
    fr = list(range(S.FRAMES)) if frames == "all" else [int(x) for x in frames.split(",")]
    t0 = time.perf_counter()
    # time the per-frame update alone (what the 3D view pays while playing)
    ups = []
    for f in fr[:40]:
        a = time.perf_counter()
        update(f)
        bpy.context.view_layer.update()
        ups.append(time.perf_counter() - a)
    times = bl.render_frames(fr, out, update)
    res = dict(method=method, engine=eng, frames=len(fr), render_s_per_frame=float(np.median(times)),
               first_frame_s=times[0], update_ms=1000 * float(np.median(ups)), total_s=time.perf_counter() - t0)
    if len(fr) > 30:
        res["mp4_bytes"] = bl.mp4(out, os.path.join(out, f"s_{method}_{eng.lower()}.mp4"))
    json.dump(res, open(os.path.join(out, "times.json"), "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
