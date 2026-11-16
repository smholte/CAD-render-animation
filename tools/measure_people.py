"""Task 0157: what people cost – Build and frame time with 1, 5 and 20 people walking on the Vessel deck round the
test crane (vessel motion on, a calm beam sea). Run with the venv's bpy:

    ~/venv/bin/python tools/measure_people.py [counts…]

Each person walks a loop of four points beside the crane at its own gait, stops, looks at the crane and waves.
Prints one line per count: Build seconds, frame time (frame_set + evaluation, mean of 100 frames) with the people and
the same frames with the people hidden."""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,I001  (bpy first: it puts Blender's own modules on the path)
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402

CRANE = os.path.join(HERE, "tests", "data", "test_crane_a.step")
GAITS = ("STROLL", "WALK", "BRISK", "CARRY", "WALK")


def frame_time(sc, n=100):
    t = time.perf_counter()
    for f in range(1, n + 1):
        sc.frame_set(f)
    return (time.perf_counter() - t) / n * 1000.0


def run(count):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    s.background = "DECK"
    s.sea_state = "CALM"
    s.vessel.heading = "BEAM"
    s.vessel.enabled = True
    bpy.context.view_layer.update()
    from fresing_render.blender import animation, logic, people, surroundings
    mn, mx = logic.cached_bounds(sc)
    z = surroundings.floor_height(sc)
    cx, cy = float(mx[0]) + 2.0, (float(mn[1]) + float(mx[1])) / 2
    t0 = time.perf_counter()
    for i in range(count):
        x = cx + (i % 5) * 1.2
        y = cy - 4.0 + (i // 5) * 1.5
        ob = people.add_person(sc, (x, y, z), f"P{i + 1}", heading=0.0)
        ob.fresing_person.look = i % 4
        people.set_path(sc, ob, [(x, y - 3.0, z), (x + 0.6, y - 4.5, z), (x + 0.6, y - 1.0, z), (x, y, z)])
        ps = ob.fresing_person
        for kind, kw in (("WALK", dict(place="END", gait=GAITS[i % len(GAITS)])), ("STOP", {}),
                         ("WAVE", {})):
            a = ps.actions.add()
            a.kind = kind
            for k, v in kw.items():
                setattr(a, k, v)
    t_add = time.perf_counter() - t0
    bpy.ops.fresing.anim_add()
    an = animation.active(sc)
    t0 = time.perf_counter()
    res = animation.bake(sc, an)
    t_build = time.perf_counter() - t0
    with_people = frame_time(sc)
    for ob in people.people(sc):
        ob.hide_viewport = True
    without = frame_time(sc)
    print(f"{count:3d} people: add {t_add:5.1f} s, Build {t_build:5.1f} s ({res['frames']} frames, "
          f"{len(res['warnings'])} warnings), frame {with_people:6.1f} ms with them, {without:6.1f} ms hidden",
          flush=True)
    fresing_render.unregister()


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or [1, 5, 20]:
        run(n)
