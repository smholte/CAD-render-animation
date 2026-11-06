"""Chips (task 0028): how long it takes to work them out, to show a frame, and to render a frame.

    ~/venv/bin/python tools/bench_chips.py                  # work-out and show times, the long pocket too
    ~/venv/bin/python tools/bench_chips.py --render         # also render one frame: None / Few / Realistic
    ~/venv/bin/python tools/bench_chips.py --render --size 960x540 --quality preview
    ~/venv/bin/python tools/bench_chips.py --render --heavy --no-pocket   # thousands of chips, and the limit

The test mill (tests/data/test_mill.step): a flat Ø10 end mill cuts a slot 5 mm deep and 50 mm long into
the aluminium block; the animation runs on 0.5 s after the cut so the chips land. The render (Cycles on the
processor) looks at the block from the front at the frame where the cut ends: the same picture with no chips,
Few and Realistic. Times are printed; the report names the machine they were measured on.

The long pocket (core only, no Blender scene): a zig-zag pocket 150 x 150 mm, 5 mm deep, 2.67 mm per frame.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
MM = 0.001


def pocket(amount: str) -> dict:
    from fresing_render.core import chips as C
    from fresing_render.core import machining as M
    top = C.grid_for((-0.1, -0.1), (0.1, 0.1), 0.25 * MM)
    top.h[:] = 0.07
    pts = [(-0.075, -0.075, 0.09), (-0.075, -0.075, 0.065)]
    y, d = -0.075, 1
    while y <= 0.075:
        x2 = 0.075 if d > 0 else -0.075
        pts.append((x2, y, 0.065))
        y += 0.008
        if y <= 0.075:
            pts.append((x2, y, 0.065))
        d = -d
    pts.append((pts[-1][0], pts[-1][1], 0.09))
    P = np.array(pts)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    o = [P[0]]
    for i in range(len(seg)):
        n = int(np.ceil(seg[i] / 0.00267))
        for k in range(1, n + 1):
            o.append(P[i] + (P[i + 1] - P[i]) * k / n)
    o = np.array(o)
    t = np.arange(1, len(o) + 1, dtype=float)
    tool = M.Tool("FLAT", radius=5 * MM, length=40 * MM)
    bit = C.BitIn(t, o, np.tile([0, 0, 1.0], (len(t), 1)), 5 * MM, 40 * MM, M.tool_profile(tool),
                  C.presets_for("ALU", "END"))
    work = C.WorkField(top, np.full_like(top.h, 0.03))
    t0 = time.perf_counter()
    C.stamp_paths(work, [bit])
    stamp = time.perf_counter() - t0
    ride = C.grid_for((-0.4, -0.4), (0.4, 0.4), 2 * MM)
    xs, ys = ride.centres()
    X, Y = np.meshgrid(xs, ys)
    ride.h[(abs(X) < 0.2) & (abs(Y) < 0.15)] = 0.03
    st = C.grid_for((-1, -1), (1, 1), 5 * MM)
    xs, ys = st.centres()
    X, Y = np.meshgrid(xs, ys)
    st.h[(abs(X) < 0.35) & (abs(Y) < 0.25)] = 0.0
    inp = C.SimIn(25.0, 1, len(t), [bit], work, ride, st, -0.06, None, amount, False)
    t0 = time.perf_counter()
    b = C.simulate(inp)
    sim = time.perf_counter() - t0
    shows = []
    for f in range(50, len(t), 50):
        t1 = time.perf_counter()
        b.at(f)
        shows.append(time.perf_counter() - t1)
    return {"frames": len(t), "stamp_s": stamp, "sim_s": sim, "chips": b.count, "max_alive": b.stats["max_alive"],
            "at_ms": 1000 * float(np.mean(shows))}


def mill_scene(amount: str, heavy: bool = False, material: str = "AUTO"):
    import addon_utils
    import bpy
    from mathutils import Vector

    import fresing_render
    from fresing_render.blender import animation, build, joints, logic, machining
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    try:
        fresing_render.register()
    except ValueError:
        pass
    sc = bpy.context.scene
    bpy.ops.fresing.import_step(filepath=os.path.join(ROOT, "tests", "data", "test_mill.step"), quality="normal")

    def ob(name):
        return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    for o, nm in ((ob("END MILL D10"), "bit"), (ob("STOCK 200x200x40"), "wp")):
        for x in bpy.context.selected_objects:
            x.select_set(False)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        getattr(bpy.ops.fresing, "mill_add_bit" if nm == "bit" else "mill_set_workpiece")()
    logic.set_hidden(ob("FINISHED PART"), True)
    logic.set_hidden(ob("COLUMN"), True)
    cam = bpy.data.objects.new("Bench cam", bpy.data.cameras.new("Bench cam"))
    sc.collection.objects.link(cam)
    cam.location = (0.30, -0.42, 0.30)
    cam.rotation_euler = (Vector((0.04, 0.0, 0.05)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 60
    sc.camera = cam
    s = sc.fresing
    a = s.animations.add()
    a.name, a.tail = "Mill", 0.5
    moves = ((("Z", 0.0, 1.0, -35.0), ("X", 1.0, 3.0, 90.0), ("Z", 4.0, 0.5, 0.0)) if heavy else
             (("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)))
    for j, start, dur, to in moves:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    frames = animation.bake(sc, a)["frames"]
    machining.sample(sc)
    sc.fresing.milling.chip_material = material
    sc.fresing.milling.chips = amount
    return sc, frames


def blender_times(render: bool, size: str, quality: str, heavy: bool = False) -> list:
    import bpy

    from fresing_render.blender import chips, machining, render as rnd, world
    out = []
    w, h = (int(v) for v in size.split("x"))
    cases = ([("NONE", "AUTO"), ("REALISTIC", "AUTO"), ("REALISTIC", "BRASS")] if heavy else
             [("NONE", "AUTO"), ("FEW", "AUTO"), ("REALISTIC", "AUTO")])
    for amount, material in cases:
        sc, frames = mill_scene(amount, heavy, material)
        t0 = time.perf_counter()
        chips.forget()
        sc.frame_set(1)
        bk = chips.bake(sc) if amount != "NONE" else None
        bake_s = time.perf_counter() - t0
        f = 125 if heavy else 75                         # the cut has just ended: chips in the air and lying
        times = []
        for ff in (f - 2, f - 1, f):
            t1 = time.perf_counter()
            sc.frame_set(ff)
            times.append(time.perf_counter() - t1)
        n = machining.runtime(sc).get("shown") and chips.runtime(sc).get("count", 0)
        row = {"amount": amount + ("" if material == "AUTO" else f" {material}"), "chips": bk.count if bk else 0, "shown": n or 0, "bake_s": bake_s,
               "frame_ms": 1000 * float(np.mean(times)), "inputs_s": bk.stats.get("inputs_s", 0) if bk else 0}
        if render:
            sc.fresing.use_gpu = False
            rnd.apply_quality(sc, quality, False)
            rnd.apply_motion_settings(sc)
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
            world.apply(sc, sc.fresing)
            sc.render.filepath = os.path.join(os.environ.get("BENCH_OUT", "/tmp"),
                                              f"chips_{'heavy_' if heavy else ''}{amount.lower()}_{material.lower()}.png")
            bpy.ops.render.render(write_still=True)        # once to warm up (scene to Cycles)
            t1 = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            row["render_s"] = time.perf_counter() - t1
        out.append(row)
        print(row, flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--size", default="640x360")
    ap.add_argument("--quality", default="preview")
    ap.add_argument("--no-pocket", action="store_true")
    ap.add_argument("--heavy", action="store_true", help="a slot 15 mm deep and 90 mm long: thousands of chips "
                                                       "(aluminium curls), and brass crumbs up to the 25,000 limit")
    a = ap.parse_args()
    print(f"machine: {os.cpu_count()} cores")
    if not a.no_pocket:
        for amount in ("FEW", "REALISTIC"):
            print("pocket", amount, pocket(amount), flush=True)
    rows = blender_times(a.render, a.size, a.quality, a.heavy)
    print("\n| Chips | Chips worked out | Shown at the end of the cut | Working out (s) | Frame change (ms) | Render (s) |")
    print("| --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(f"| {r['amount']} | {r['chips']} | {r['shown']} | {r['bake_s']:.2f} | {r['frame_ms']:.1f} | "
              f"{r.get('render_s', float('nan')):.1f} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
