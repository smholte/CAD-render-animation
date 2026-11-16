"""Measure what cables, paths, spools and tracks cost on the demo project (task 0159).

    ~/venv/bin/python tools/measure_cables.py <made folder> [--out result.json] [--render] [--frames N]

``<made folder>`` is what ``tests/demo_made.py <folder>`` made (``made.json`` + the project). Blender as a Python module,
no graphics card: "playback" is the scene's evaluation per frame (``frame_set``: drivers, Geometry Nodes, constraints –
what the live view waits for before it draws), not EEVEE's drawing. Prints one table and writes the numbers as JSON:

- make: the demo's make time and its stages (from made.json)
- build: ``animation.bake`` of the demo animation, split by the module the time was spent in (cProfile, own time per
  file; the flex parts' modules by name, the rest "other")
- playback: ms per frame over evenly spaced frames, and again with the app-made cable / spool / track drawings
  switched off – the difference is what drawing them costs per frame
- memory: the process's resident memory after opening, after Build
- triangles: the evaluated carousel rope, its full layers (task 0174; before: its solid), every cable tube, the CAD coil
- project size: the saved .blend (MB)
- live: ms per step of the cable's speed joint after "Clear keys" (the live handlers' cost while posing)
- render (``--render``): one Cycles frame of the carousel shot, 480 x 270, 16 samples, on the processor
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import pstats
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GROUPS = ("paths", "spool", "flex", "tracks", "clash", "cable_looks", "joints", "animation")


def rss_mb() -> float:
    with open("/proc/self/status", encoding="ascii") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def group_of(filename: str) -> str:
    base = os.path.basename(filename)
    if "fresing_render" not in filename:
        return "blender/other"
    for g in GROUPS:
        if base.startswith(g):                          # paths.py, paths_rollers.py … ; spool.py; flex*.py …
            return ("core." if os.sep + "core" + os.sep in filename else "") + g
    return "other app"


def by_module(prof: cProfile.Profile) -> dict:
    st = pstats.Stats(prof)
    out: dict[str, float] = {}
    for (fn, _line, _name), (_cc, _nc, tt, _ct, _callers) in st.stats.items():
        g = group_of(fn)
        out[g] = out.get(g, 0.0) + tt
    return {k: round(v, 2) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def top_functions(prof: cProfile.Profile, n: int = 25) -> list:
    """The n functions with the most time of their own (file:function, own s, with callees s, calls)."""
    st = pstats.Stats(prof)
    rows = [(f"{os.path.basename(fn)}:{name}", round(tt, 2), round(ct, 2), nc)
            for (fn, _line, name), (_cc, nc, tt, ct, _callers) in st.stats.items()]
    return sorted(rows, key=lambda r: -r[1])[:n]


def made_objects(sc):
    """The app-made drawings: (spool rope / solid, cable parts with "FR cable", track parts with "FR track")."""
    from fresing_render.blender import paths, spool, tracks
    mods = []
    for ob in sc.objects:
        for m in ob.modifiers:
            if m.type == "NODES" and m.name in (spool.MOD, getattr(spool, "LAYER_MOD", spool.MOD), paths.MOD,
                                                tracks.MOD):
                mods.append(m)
    return mods


def triangles(sc) -> dict:
    import bpy
    from fresing_render.blender import paths, spool
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}

    def tris(ob):
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            return len(me.loop_triangles), len(me.vertices)
        finally:
            ev.to_mesh_clear()
    for sp in sc.fresing.spools:
        for what in ("rope", "solid"):
            ob = spool._made(sc, sp, what)
            if ob is not None:
                out[f"spool {sp.name} {what}"] = tris(ob)
        layers = spool.layer_objects(sc, sp) if hasattr(spool, "layer_objects") else []
        if layers:                                  # task 0174: every full layer (shown now or not)
            got = [tris(ob) for ob in layers]
            out[f"spool {sp.name} layers ({len(layers)})"] = (sum(t for t, _v in got), sum(v for _t, v in got))
        if sp.coil is not None:
            out[f"spool {sp.name} CAD coil (hidden)"] = (sum(len(p.vertices) - 2 for p in sp.coil.data.polygons),
                                                        len(sp.coil.data.vertices))
    tot_t = tot_v = 0
    for it in sc.fresing.cables:
        if it.part is not None and it.part.modifiers.get(paths.MOD) is not None:
            t, v = tris(it.part)
            out[f"cable {it.name}"] = (t, v)
            tot_t += t
            tot_v += v
    out["cables total"] = (tot_t, tot_v)
    return out


def playback(sc, frames: list[int]) -> float:
    t0 = time.perf_counter()
    for f in frames:
        sc.frame_set(f)
    return 1000.0 * (time.perf_counter() - t0) / len(frames)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("made")
    ap.add_argument("--out", default="")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--frames", type=int, default=120)
    args = ap.parse_args()
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import bpy  # noqa: I001
    import addon_utils

    import fresing_render
    from fresing_render.blender import animation, demo, joints

    with open(os.path.join(args.made, "made.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    res = {"machine": f"{os.cpu_count()} cores", "make_seconds": info.get("make_seconds"),
           "make_stages": info["out"].get("seconds"), "make_timings": info["out"].get("timings")}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    t0 = time.perf_counter()
    bpy.ops.wm.open_mainfile(filepath=info["out"]["path"])
    res["open_seconds"] = round(time.perf_counter() - t0, 1)
    res["project_mb"] = round(os.path.getsize(info["out"]["path"]) / 1e6, 1)
    sc = bpy.context.scene
    res["rss_open_mb"] = round(rss_mb())
    a = sc.fresing.animations[demo.ANIM]
    sc.frame_set(1)
    res["triangles"] = triangles(sc)
    n = max(2, args.frames)
    f0, f1 = int(sc.frame_start), int(sc.frame_end)
    frames = sorted({int(round(f0 + (f1 - f0) * k / (n - 1))) for k in range(n)})
    res["frames"] = [f0, f1, len(frames)]
    playback(sc, frames[:5])                                          # warm up
    res["playback_ms"] = round(playback(sc, frames), 1)
    mods = made_objects(sc)
    was = [(m, m.show_viewport) for m in mods]
    for m in mods:
        m.show_viewport = False
    res["playback_ms_without_drawings"] = round(playback(sc, frames), 1)
    for m, v in was:
        m.show_viewport = v
    res["drawings"] = len(mods)
    # Build, split by module
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    prof.enable()
    animation.bake(sc, a)
    prof.disable()
    res["build_seconds"] = round(time.perf_counter() - t0, 1)
    res["build_by_module"] = by_module(prof)
    res["build_top"] = top_functions(prof)
    res["rss_build_mb"] = round(rss_mb())
    playback(sc, frames[:5])
    res["playback_ms_after_build"] = round(playback(sc, frames), 1)
    # the carousel shot's frame for render and the live test
    shot = next((b for b in a.blocks if b.kind == "CAMERA" and b.camera is not None and "arousel" in b.camera.name),
                None)
    f_shot = animation.frame_of(a, shot.start + 1.0) if shot is not None else f0
    res["shot_frame"] = int(f_shot)
    if args.render:
        sc.frame_set(f_shot)
        r = sc.render
        r.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 16
        r.resolution_x, r.resolution_y, r.resolution_percentage = 480, 270, 100
        r.filepath = os.path.join(args.made, "measure_render.png")
        if shot is not None:
            sc.camera = shot.camera
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        res["render_seconds"] = round(time.perf_counter() - t0, 1)
        res["render_file"] = r.filepath
    # live: the cable's speed joint stepped by hand after Clear keys
    animation.clear_keys(sc)
    j = joints.find(sc, "Cable travel")
    if j is not None:
        dg = bpy.context.evaluated_depsgraph_get()
        v0 = joints.get_value(j)
        steps = [v0 + 0.5 * k for k in range(1, 11)]
        joints.set_value(j, steps[0])
        dg.update()
        t0 = time.perf_counter()
        for v in steps[1:]:
            joints.set_value(j, v)
            dg.update()
        res["live_ms_per_step"] = round(1000.0 * (time.perf_counter() - t0) / (len(steps) - 1), 1)
    fresing_render.unregister()
    text = json.dumps(res, indent=1)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
