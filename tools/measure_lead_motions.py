"""Task 0309: how long one slider change of a lead motion takes – the joints set and the scene worked out again
(``view_layer.update()``, what Blender does before it draws) – on the test crane, the test mill and the PC check's
Heavy machine (about 3,000 placed parts, made at run time). Blender as a Python module, so no drawing is counted.

    ~/venv/bin/python tools/measure_lead_motions.py [--small]      (--small: the Heavy machine scaled down)
"""

from __future__ import annotations

import math
import os
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402  (bpy first: it puts addon_utils on the path)
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import joints, lead_motions  # noqa: E402
from fresing_render.core import lead_motions as core  # noqa: E402

DATA = os.path.join(ROOT, "tests", "data")


def fresh(step, out, quality="draft"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = out
    t0 = time.time()
    assert bpy.ops.fresing.import_step(filepath=step, quality=quality) == {"FINISHED"}
    print(f"  imported {os.path.basename(step)} in {time.time() - t0:.1f} s, {len(sc.objects)} objects")
    return sc


def measure(sc, lm, n=40):
    """(median ms, slowest ms, joints, median ms of the same joint values set straight in the joint box's way)."""
    times, base = [], []
    ps = [100.0 * (0.5 - 0.5 * math.cos(math.pi * i / (n - 1))) for i in range(n)]
    for p in ps:                                   # as the app runs a drag: the slider's own update, no refresh of
        t0 = time.perf_counter()                   # mechanisms / hoses / cables here (their live handlers do that)
        lm["position"] = p
        lead_motions.apply(sc, lm, p, refresh=False)
        bpy.context.view_layer.update()
        times.append((time.perf_counter() - t0) * 1000.0)
    lm.position = 0.0
    bpy.context.view_layer.update()
    rows = lead_motions.usable(sc, lm)
    for p in ps:                                   # the baseline: the joints set one by one, as the joint box does
        vals = lead_motions.values_at(lm, p)
        t0 = time.perf_counter()
        for r, j in rows:
            joints.set_value(j, vals[r.joint])
        bpy.context.view_layer.update()
        base.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(times), max(times), len(rows), statistics.median(base)


def crane(out):
    from fresing_render.blender import tour
    from fresing_render.blender.lessons import crane as lesson
    sc = fresh(os.path.join(DATA, "test_crane_a.step"), out)
    tour._boom_joint(sc)
    lesson._trolley(sc)
    lm = lead_motions.add(sc, "Boom up and out", [core.Row("Boom", 0, math.radians(35), 0, 60),
                                                  core.Row("Trolley", 0, 1.75, 40, 100)])
    return measure(sc, lm)


def mill(out):
    from fresing_render.blender.lessons import mill as lesson
    sc = fresh(os.path.join(DATA, "test_mill.step"), out)
    lesson._axes(sc)
    lm = lead_motions.add(sc, "Table X and Y", [core.Row("X", 0, 0.3, 0, 60), core.Row("Y", 0, 0.2, 40, 100)])
    return measure(sc, lm)


def heavy(out, small):
    from fresing_render.pccheck import heavy as H
    from fresing_render.importer import runner
    if small:
        os.environ["FRESING_PCCHECK_HEAVY_SMALL"] = "1"
    z = H.sizes()
    step = os.path.join(out, "heavy_machine.step")
    script = os.path.join(ROOT, "fresing_render", "pccheck", "heavy_scene.py")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p and os.path.isdir(p)))
    t0 = time.time()
    subprocess.run([runner.python_executable(), script, step, str(z["unique"]), str(z["placed"])], check=True,
                   env=env, capture_output=True)
    print(f"  heavy machine written in {time.time() - t0:.0f} s ({z['placed']} placed parts)")
    sc = fresh(step, out, quality="normal")
    mods = [o for o in sc.objects if o.get("fr_name", "").startswith("MODULE ")][:3]
    mods = sorted({o.get("fr_name"): o for o in mods}.values(), key=lambda o: o.get("fr_name"))
    j1 = joints.create(sc, "ROTATE", [mods[0]], mods[0].matrix_world.translation.copy(), Vector((0, 0, 1)),
                       name="Turn")
    j2 = joints.create(sc, "SLIDE", [mods[1]], mods[1].matrix_world.translation.copy(), Vector((1, 0, 0)),
                       name="Slide")
    lm = lead_motions.add(sc, "Turn and slide", [core.Row(j1.name, 0, math.radians(90), 0, 60),
                                                 core.Row(j2.name, 0, 0.5, 40, 100)])
    return measure(sc, lm)


def main():
    small = "--small" in sys.argv
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    rows = []
    with tempfile.TemporaryDirectory() as out:
        for name, fn in (("test crane", crane), ("test mill", mill),
                         ("Heavy machine" + (" (small)" if small else ""), lambda o: heavy(o, small))):
            print(name)
            med, mx, n, base = fn(out)
            rows.append((name, med, mx, n, base))
    print(f"\n{os.cpu_count()} cores")
    print("| Model | joints in the lead motion | ms per slider change (median) | slowest | the same joints set "
          "directly (median) |")
    for name, med, mx, n, base in rows:
        print(f"| {name} | {n} | {med:.2f} | {mx:.2f} | {base:.2f} |")


if __name__ == "__main__":
    main()
