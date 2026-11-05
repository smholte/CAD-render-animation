"""Milling speed (task 0027): time per frame on a 200 x 200 x 40 mm block, for the report and later tasks.

    ~/venv/bin/python tools/bench_milling.py                # all detail levels, both paths, the comparison
    ~/venv/bin/python tools/bench_milling.py --quick        # Normal only
    ~/venv/bin/python tools/bench_milling.py --blender      # also: mesh into Blender per frame, reading
                                                            # the path on a scene with 2,800 parts

Paths (25 frames per second):
    pocket   zig-zag pocket 150 x 150 mm, stepover 5 mm, two layers of 2 mm, feed 4000 mm/min
             (2.67 mm per frame): long straight moves
    rings    round pocket Ø110 mm in rings 5 mm apart, two layers, same feed: every frame is a new
             little straight piece (like arcs from a CAM program)
Methods compared (only for the report, the app uses "segments"):
    segments  the app: one boolean per straight move, the open move cut on the fly, tiles
    perframe  one boolean per frame for the bit's move in that frame (the lead's first idea)
    heightmap a grid of heights seen from above (0.25 mm), stamped along the path; the top surface
              a mesh of 800 x 800 points that moves every frame
"""

from __future__ import annotations

import argparse
import math
import os
import random
import resource
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fresing_render.core import machining as M  # noqa: E402

MM = 0.001
FEED = 2.67                        # mm per frame


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _resample(pts):
    out = [np.array(pts[0], float)]
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = np.array(a, float), np.array(b, float)
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / FEED)))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.array(out) * MM


def pocket_path():
    pts = [(-75, -75, 45), (-75, -75, 40)]
    z = 40.0
    for _ in range(2):
        z -= 2.0
        pts.append((-75, -75, z))
        y, flip = -75.0, False
        while y <= 75.0 + 1e-9:
            xs = (75.0, -75.0) if flip else (-75.0, 75.0)
            pts += [(xs[0], y, z), (xs[1], y, z)]
            y += 5.0
            flip = not flip
        pts += [(pts[-1][0], pts[-1][1], 45.0), (-75, -75, 45)]
    return _resample(pts)


def rings_path():
    out = [np.array((0, 0, 45.0)) * MM]
    z = 40.0
    for _ in range(2):
        z -= 2.0
        for rr in np.arange(5.0, 55.1, 5.0):
            n = max(8, int(2 * math.pi * rr / FEED))
            for k in range(n + 1):
                a = 2 * math.pi * k / n
                out.append(np.array((rr * math.cos(a), rr * math.sin(a), z)) * MM)
        out.append(np.array((55.0, 0, 45.0)) * MM)
    return np.array(out)


def block():
    import manifold3d as mf
    return mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.0))


def as_path(o):
    return M.Path(np.arange(len(o), dtype=float), o, np.tile([0.0, 0.0, 1.0], (len(o), 1)))


def bench_segments(name, o, tool, detail):
    p = as_path(o)
    tl = M.Timeline(M.Workpiece(block(), None, detail), [M.Cutter(tool, detail)], [p], detail)
    times = []
    t_all = time.perf_counter()
    for f in range(len(o)):
        t0 = time.perf_counter()
        v, t, _s = tl.mesh_at(float(f))
        times.append(time.perf_counter() - t0)
    total = time.perf_counter() - t_all
    tri_end = len(t)
    tiles = tl.stats.tiles
    # scrubbing back: random frames once everything was computed once
    rnd = random.Random(1)
    back = []
    for _ in range(40):
        f = rnd.randrange(len(o))
        t0 = time.perf_counter()
        tl.mesh_at(float(f))
        back.append(time.perf_counter() - t0)
    # straight to the last frame, nothing computed before (opening a project at the end)
    fresh = M.Timeline(M.Workpiece(block(), None, detail), [M.Cutter(tool, detail)], [p], detail)
    t0 = time.perf_counter()
    fresh.mesh_at(float(len(o) - 1))
    jump = time.perf_counter() - t0
    ms = np.array(times) * 1000
    q = max(1, len(ms) // 10)
    return {"name": name, "detail": detail, "tool": tool.kind, "frames": len(o), "segments": tl.stats.segments,
            "mean": ms.mean(), "last10": ms[-q:].mean(), "max": ms.max(), "total": total,
            "back": np.mean(back) * 1000, "jump": jump, "tris": tri_end, "tiles": tiles, "rss": rss_mb()}


def bench_perframe(o, tool, detail):
    cut = M.Cutter(tool, detail)
    state = block()
    times, n = [], 0
    for i in range(1, len(o)):
        t0 = time.perf_counter()
        h, (lo, hi) = cut.sweep(o[i - 1], o[i], np.array([0.0, 0.0, 1.0]))
        if lo[2] < 0.04:
            state = state - h
            n = state.num_tri()
        times.append(time.perf_counter() - t0)
    ms = np.array(times) * 1000
    q = max(1, len(ms) // 10)
    return {"mean": ms.mean(), "last10": ms[-q:].mean(), "tris": n, "total": ms.sum() / 1000}


def bench_heightmap(o, radius, cell=0.25 * MM):
    n = int(round(0.2 / cell))
    xs = (np.arange(n) + 0.5) * cell - 0.1
    H = np.full((n, n), 0.04, dtype=np.float32)
    times = []
    for i in range(1, len(o)):
        a, b = o[i - 1], o[i]
        t0 = time.perf_counter()
        if min(a[2], b[2]) < 0.04:
            lo, hi = np.minimum(a, b) - radius, np.maximum(a, b) + radius
            i0, i1 = max(0, int((lo[0] + 0.1) / cell)), min(n, int((hi[0] + 0.1) / cell) + 2)
            j0, j1 = max(0, int((lo[1] + 0.1) / cell)), min(n, int((hi[1] + 0.1) / cell) + 2)
            X, Y = np.meshgrid(xs[i0:i1], xs[j0:j1], indexing="ij")
            d = b[:2] - a[:2]
            L2 = float(d @ d)
            s = np.clip(((X - a[0]) * d[0] + (Y - a[1]) * d[1]) / L2, 0, 1) if L2 > 0 else np.zeros_like(X)
            z = (a[2] + s * (b[2] - a[2])).astype(np.float32)
            dist2 = (X - (a[0] + s * d[0])) ** 2 + (Y - (a[1] + s * d[1])) ** 2
            np.minimum(H[i0:i1, j0:j1], np.where(dist2 <= radius * radius, z, np.inf).astype(np.float32),
                       out=H[i0:i1, j0:j1])
        times.append(time.perf_counter() - t0)
    return {"stamp": np.mean(times) * 1000, "cells": n * n, "H": H}


def bench_blender(o, tool):
    """Mesh into Blender per frame (end state of the pocket), and reading the path on a big scene."""
    import bpy

    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from fresing_render.blender import machining as BM
    p = as_path(o)
    tl = M.Timeline(M.Workpiece(block(), None, "NORMAL"), [M.Cutter(tool, "NORMAL")], [p], "NORMAL")
    v, t, s = tl.mesh_at(float(len(o) - 1))
    me = bpy.data.meshes.new("bench")
    t0 = time.perf_counter()
    for _ in range(10):
        BM._write_mesh(me, v, t, np.zeros(len(t), np.int32))
    upload = (time.perf_counter() - t0) / 10 * 1000
    # heightmap mesh for comparison: 800 x 800 points, only z changes per frame
    n = 800
    hm = bpy.data.meshes.new("hm")
    xs = (np.arange(n) + 0.5) * 0.00025 - 0.1
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    co = np.stack([X.ravel(), Y.ravel(), np.full(n * n, 0.04)], 1).astype(np.float32)
    idx = np.arange(n * n).reshape(n, n)
    quads = np.stack([idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()], 1)
    hm.vertices.add(len(co))
    hm.vertices.foreach_set("co", co.ravel())
    hm.loops.add(quads.size)
    hm.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    hm.polygons.add(len(quads))
    hm.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    hm.update()
    t0 = time.perf_counter()
    for _ in range(3):
        co[:, 2] = 0.039
        hm.vertices.foreach_set("co", co.ravel())
        hm.update()
    hm_upload = (time.perf_counter() - t0) / 3 * 1000
    return {"upload": upload, "tris": len(t), "hm_upload": hm_upload, "rss": rss_mb()}


def bench_sampling():
    """Reading the path: one frame_set per frame on the test mill, and with 2,800 extra parts that move."""
    import addon_utils
    import bpy
    from mathutils import Vector

    import fresing_render
    from fresing_render.blender import animation, build, joints, machining
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    bpy.ops.fresing.import_step(filepath=os.path.join(ROOT, "tests", "data", "test_mill.step"), quality="draft")
    obs = {o.get(build.PROP_NAME): o for o in sc.objects if o.get(build.PROP_KIND)}
    out = {}
    for extra in (0, 2800):
        if extra:                 # 2,800 small parts riding on the head (like a big machine's moving parts)
            src = obs["SPINDLE"]
            col = src.users_collection[0]
            for k in range(extra):
                c = src.copy()
                c.parent = obs["Z.ASM"]
                c.matrix_parent_inverse = src.matrix_parent_inverse
                c.location = (src.location.x + (k % 70) * 0.002, src.location.y + (k // 70) * 0.002, src.location.z)
                col.objects.link(c)
        if not sc.fresing.joints:
            for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
                o = obs[asm]
                joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
        a = sc.fresing.animations.get("B") or sc.fresing.animations.add()
        a.name, a.tail = "B", 0.0
        a.blocks.clear()
        for j, start, dur, to in (("Z", 0.0, 4.0, -0.025), ("X", 4.0, 16.0, 0.05)):
            b = a.blocks.add()
            b.kind, b.joint, b.start, b.duration, b.easing, b.use_from, b.to_dist = "JOINT", j, start, dur, "LINEAR", True, to
        frames = animation.bake(sc, a)["frames"]
        m = sc.fresing.milling
        if not m.bits:
            machining.add_bit(sc, obs["END MILL D10"])
            machining.set_workpiece(sc, obs["STOCK 200x200x40"])
        t0 = time.perf_counter()
        machining.sample(sc)
        dt = time.perf_counter() - t0
        out[extra] = (frames, dt * 1000 / frames, len(sc.objects))
    fresing_render.unregister()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--blender", action="store_true")
    args = ap.parse_args(argv)
    flat = M.Tool("FLAT", radius=5 * MM, length=30 * MM)
    ball = M.Tool("BALL", radius=5 * MM, length=30 * MM)
    paths = {"pocket": pocket_path(), "rings": rings_path()}
    details = ["NORMAL"] if args.quick else ["FINE", "NORMAL", "FAST"]
    print(f"machine: {os.cpu_count()} cores; block 200 x 200 x 40 mm; feed {FEED} mm per frame\n")
    print("| Path | Bit | Detail | Frames | Moves | ms/frame mean | last 10 % | max | scrub back | open at end "
          "| triangles | tiles | memory |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for pname, o in paths.items():
        for tool in (flat, ball):
            for d in details:
                r = bench_segments(pname, o, tool, d)
                print(f"| {pname} | {tool.kind.lower()} Ø10 | {d.lower()} | {r['frames']} | {r['segments']} | "
                      f"{r['mean']:.1f} | {r['last10']:.1f} | {r['max']:.0f} | {r['back']:.0f} ms | "
                      f"{r['jump']:.1f} s | {r['tris']:,} | {r['tiles']} | {r['rss']:.0f} MB |", flush=True)
    print("\nComparison (flat Ø10, normal):")
    for pname, o in paths.items():
        pf = bench_perframe(o, flat, "NORMAL")
        hm = bench_heightmap(o, 5 * MM)
        print(f"- {pname}: one boolean per frame: {pf['mean']:.1f} ms mean, {pf['last10']:.1f} ms at the end, "
              f"{pf['tris']:,} triangles; height map 0.25 mm: stamping {hm['stamp']:.2f} ms per frame "
              f"({hm['cells']:,} cells)", flush=True)
    if args.blender:
        r = bench_blender(paths["pocket"], flat)
        print(f"\nInto Blender per frame: segments mesh ({r['tris']:,} triangles) {r['upload']:.1f} ms; "
              f"height-map mesh 800 x 800 {r['hm_upload']:.0f} ms (z only)")
        for extra, (frames, ms, nobj) in bench_sampling().items():
            print(f"Reading the path: {ms:.2f} ms per frame ({frames} frames, {nobj} objects in the scene)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
