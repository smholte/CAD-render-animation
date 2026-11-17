"""Milling speed on dense 3-axis finishing programs (task 0146, study 0069 rows M1 and dome).

    ~/venv/bin/python tools/bench_milling_dense.py                  # both programs, all measurements
    ~/venv/bin/python tools/bench_milling_dense.py --only m1 --quick --json out.json
    ~/venv/bin/python tools/bench_milling_dense.py --fast           # the height-map cutter (where available)
    ~/venv/bin/python tools/bench_milling_dense.py --volume         # also the removed volume (mm3)
    ~/venv/bin/python tools/bench_milling_dense.py --only toolpath --toolpath-file tp.npz --fast   # task 0167

Both programs: ball end mill diameter 6 mm, axis +Z, zigzag raster, metres, one sample per ``--per-frame`` points.
    m1    "wavy": block 100 x 60 x 20 mm, 201 passes 0.3 mm apart, 201 points per pass (40,401 points), the tip on a
          smooth wavy surface 1-4.5 mm below the top (study: 13,911 segments at Normal)
    dome  block 60 x 60 x 20 mm, a spherical cap (R 120 mm, apex 1 mm below the top; corners 8.7 mm deep), 0.5 mm step-over
          (study: 3,586 segments)
    toolpath  the app's own toolpath test model (tests/data/test_toolpath.step: flat Ø10 roughing + ball Ø10 finishing,
          7,244 moves), read from a file that ``tools/dump_toolpath_program.py`` writes with Blender as a module
          (task 0167); only with ``--only toolpath``
Measured: the timeline's build, the whole program, the growth over 5 stops (M1), scrubbing forward / backward, peak RSS.
The generators ``m1_program()`` and ``dome_program()`` are importable (tests, Heavy check).
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import resource
import statistics
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fresing_render.core import machining as M  # noqa: E402

MM = 0.001


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _raster(xs, ys, zfun, per_frame):
    """Zigzag raster along X over passes at ys (mm); every pass runs the other way; the step to the next pass is
    the move from one pass's last point to the next pass's first. Returns (t, o, d); o in metres."""
    pts = []
    for k, y in enumerate(ys):
        row = xs if k % 2 == 0 else xs[::-1]
        pts.append(np.stack([row, np.full_like(row, y), zfun(row, y)], axis=1))
    o = np.concatenate(pts) * MM
    d = np.tile((0.0, 0.0, 1.0), (len(o), 1))
    t = np.arange(len(o)) / float(per_frame) + 1.0
    return t, o, d


def m1_program(per_frame: int = 8, a1: float = 1.2, w1: float = 45.0, w2: float = 38.0, a2: float = 0.35,
               w3: float = 25.0):
    """The "wavy" program. Returns ``(stock, tool, t, o, d)``: ``stock = (size_xyz, origin_xyz)`` in metres
    (a Manifold ``cube(size).translate(origin)``), ``tool`` an ``M.Tool``, ``t`` frames (n,), ``o`` the tip in metres
    (n, 3), ``d`` the axis (n, 3) = +Z."""
    xs = np.linspace(0.0, 100.0, 201)
    ys = np.linspace(0.0, 60.0, 201)

    def z(x, y):
        return -(2.5 + a1 * np.sin(2 * math.pi * x / w1) * math.cos(2 * math.pi * y / w2)
                 + a2 * np.sin(2 * math.pi * x / w3))
    t, o, d = _raster(xs, ys, z, per_frame)
    return ((0.1, 0.06, 0.02), (0.0, 0.0, -0.02)), M.Tool("BALL", radius=0.003, length=0.04), t, o, d


def dome_program(per_frame: int = 8):
    """The dome program (same return value as ``m1_program``): block 60 x 60 x 20 mm, top at z = 0."""
    R = 120.0
    xs = np.linspace(0.0, 60.0, 121)
    ys = np.linspace(0.0, 60.0, 121)

    def z(x, y):
        r2 = (x - 30.0) ** 2 + (y - 30.0) ** 2
        return -1.0 - (R - np.sqrt(R * R - r2))
    t, o, d = _raster(xs, ys, z, per_frame)
    return ((0.06, 0.06, 0.02), (0.0, 0.0, -0.02)), M.Tool("BALL", radius=0.003, length=0.04), t, o, d


def toolpath_program(path: str):
    """The toolpath test model's program from ``tools/dump_toolpath_program.py``'s file: ``(stock, tools, paths,
    finished)`` - stock and finished part as Manifold solids, the bits as ``M.Tool``, the paths as ``M.Path``."""
    import manifold3d as mf
    z = np.load(path)

    def solid(v, t):
        return mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(z[v], np.float32),
                                   tri_verts=np.ascontiguousarray(z[t], np.uint32)))
    tools, paths, i = [], [], 0
    while f"tool{i}" in z:
        r, length, corner, angle = (float(x) for x in z[f"tool{i}"])
        tools.append(M.Tool(str(z[f"kind{i}"]), radius=r, length=length, corner=corner, angle=angle))
        paths.append(M.Path(z[f"path{i}_t"], z[f"path{i}_o"], z[f"path{i}_d"]))
        i += 1
    return solid("stock_v", "stock_t"), tools, paths, (solid("keep_v", "keep_t") if "keep_v" in z else None)


def make_stock(stock):
    import manifold3d as mf
    if not isinstance(stock, tuple):
        return stock
    size, origin = stock
    return mf.Manifold.cube(size).translate(origin)


def build(prog, detail, fast):
    if len(prog) == 4:                                  # the toolpath test model: several bits and paths
        st, tools, paths, fin = prog
        cutters = [M.Cutter(t, detail) for t in tools]
    else:
        stock, tool, t, o, d = prog
        st, fin, cutters, paths = make_stock(stock), None, [M.Cutter(tool, detail)], [M.Path(t, o, d)]
    kw = {"fast": True} if fast else {}
    t0 = time.perf_counter()
    tl = M.Timeline(M.Workpiece(st, fin, detail), cutters, paths, detail, **kw)
    return st, tl, time.perf_counter() - t0


def timed(tl, T, **kw):
    t0 = time.perf_counter()
    out = tl.mesh_at(T, **kw)
    return time.perf_counter() - t0, out


def run(name, prog, args):
    res = {"name": name}
    st, tl, dt = build(prog, args.detail, args.fast)
    res.update(points=int(sum(len(p.t) for p in tl.paths)), segments=len(tl.segs), cutting_segments=tl.stats.cutting_segments,
               build_s=dt)
    print(f"\n== {name}: {res['points']} points, {res['segments']} segments ({res['cutting_segments']} cutting), "
          f"timeline built in {dt:.2f} s", flush=True)
    T_end = tl.ends[-1]
    T_mid = tl.ends[len(tl.ends) // 2 - 1]
    s, out = timed(tl, T_end, marks=True, normals=True)
    res.update(whole_s=s, triangles=int(len(out[1])), tiles=tl.stats.tiles)
    s2, _ = timed(tl, T_end, marks=True, normals=True)
    res["whole_again_ms"] = s2 * 1000
    print(f"whole program: {s:.2f} s, {res['triangles']} triangles, {res['tiles']} tiles; again (cached) "
          f"{s2 * 1000:.1f} ms", flush=True)
    if args.volume:
        res["removed_mm3"] = (st.volume() - M.volume(tl.at(T_end))) * 1e9
        print(f"removed volume: {res['removed_mm3']:.2f} mm3", flush=True)
    if name == "m1" and not args.quick:
        _, tl2, _ = build(prog, args.detail, args.fast)
        res["growth"] = []
        t_acc = 0.0
        n = len(tl2.segs)
        for k in [1000, 3000, 6000, 10000, n]:
            k = min(k, n)
            s, o2 = timed(tl2, tl2.ends[k - 1], marks=True, normals=True)
            t_acc += s
            res["growth"].append({"segments": k, "cumulative_s": t_acc, "mesh_s": s, "triangles": int(len(o2[1]))})
            print(f"growth: segment {k:>6}: cumulative {t_acc:7.2f} s (this call {s:.2f} s), {len(o2[1])} triangles",
                  flush=True)
    _, tl3, _ = build(prog, args.detail, args.fast)
    timed(tl3, T_mid, marks=True, normals=True)
    for label, kw in (("marks", dict(marks=True, normals=False)), ("marks+normals", dict(marks=True, normals=True))):
        ms = []
        T = T_mid
        for _i in range(30):
            T += 1.0
            s, _o = timed(tl3, T, **kw)
            ms.append(s * 1000)
        res[f"scrub_fwd_{label}"] = {"median_ms": statistics.median(ms), "max_ms": max(ms)}
        print(f"scrub forward 30 x 1 frame, {label}: median {statistics.median(ms):.1f} ms, max {max(ms):.1f} ms",
              flush=True)
    ms = []
    T = T_mid + 30.0
    for _i in range(10):
        T -= 1.0
        s, _o = timed(tl3, T, marks=True, normals=False)
        ms.append(s * 1000)
    res["scrub_back"] = {"median_ms": statistics.median(ms), "max_ms": max(ms)}
    print(f"scrub backward 10 x 1 frame: median {statistics.median(ms):.1f} ms, max {max(ms):.1f} ms")
    res["peak_rss_mb"] = rss_mb()
    print(f"peak RSS so far: {res['peak_rss_mb']:.0f} MB", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=("m1", "dome", "toolpath"))
    ap.add_argument("--toolpath-file", help="the file of tools/dump_toolpath_program.py (for --only toolpath)")
    ap.add_argument("--detail", default="NORMAL", choices=("FINE", "NORMAL", "FAST"))
    ap.add_argument("--fast", action="store_true", help="the height-map cutter (Timeline(fast=True))")
    ap.add_argument("--quick", action="store_true", help="skip the growth measurement")
    ap.add_argument("--volume", action="store_true")
    ap.add_argument("--per-frame", type=int, default=8)
    ap.add_argument("--json")
    ap.add_argument("--segments-only", action="store_true", help="only print the segment counts")
    args = ap.parse_args()
    if args.fast and "fast" not in inspect.signature(M.Timeline.__init__).parameters:
        print("fast is not available in this version")
        sys.exit(2)
    progs = {"m1": m1_program, "dome": dome_program, "toolpath": None}
    out = []
    for name, fn in progs.items():
        if (args.only and args.only != name) or (fn is None and args.only != name):
            continue
        prog = toolpath_program(args.toolpath_file) if fn is None else fn(args.per_frame)
        if args.segments_only:
            _, tl, dt = build(prog, args.detail, False)
            print(name, "segments", len(tl.segs), f"({dt:.2f} s)")
            continue
        out.append(run(name, prog, args))
    if args.json and out:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
