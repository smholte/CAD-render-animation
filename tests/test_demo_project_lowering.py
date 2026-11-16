"""Task 0145 (split from ``test_demo_project.py``): the D lowered on its wire runs into nothing – its own short
animation, clash-checked as windows of frames in four processes at once (as ``test_demo_clash.py`` checks the demo).

The demo project is made once per run and shared by these files (``tests/demo_made.py``, task 0145: the single file
had grown to ~35 min on GitHub); each file opens the saved project itself.
"""

import json  # noqa: F401
import math  # noqa: F401
import os  # noqa: F401
import shutil  # noqa: F401
import sys
import time  # noqa: F401

import numpy as np  # noqa: F401
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)                          # (demo_made: the made demo project, task 0145; demo_cps_check, 0126)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import (VERSION, _cps_shot, _dense, _first_steps, _keys, _scene, _solved, _t9,  # noqa: E402,F401
                       animation_frame, made, paths_riders_parts)
from fresing_render.blender import demo  # noqa: E402


WINDOWS = 12                      # windows of frames for the 4 worker processes (the animation: ~370 frames)


def test_the_d_lowered_on_its_wire_runs_into_nothing(made, tmp_path):
    """Task 0082: the D's whole way on the new joint – tensioners open, cradles down, the travel onto the handler, the
    tilt to LOWER_TILT, the turn to hang plumb (the sheet's hang tip) and the lowering on 'Quadrant lower' to near the
    seabed – gives 0 clash rows (the sea at rest, as the demo's check): the D, the handler, the rails, the tensioners,
    the horns and the stern stay apart. Its own short animation, the demo's is built again afterwards.

    Task 0145: the clash check of this animation (8.5–13 min on one core, the slowest test of the demo) runs as windows
    of frames in four processes (``demo_clash_child.check_in_windows``, as the demo's whole check since task 0108, and as
    strict: every moment and every step between two, start overlaps from the animation's first frame, the parts held
    still decided over the whole animation)."""
    import demo_clash_child as child

    from fresing_render.blender import animation, tour
    sc = _scene()
    s = sc.fresing
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    q = d.sheet("route")["quadrant"]
    keep = s.animations_index
    a = s.animations.add()
    a.name, a.tail, a.fps = "Lowering check", 0.2, "24"
    t = 0.0
    for name in demo.TENSIONERS:
        up, out = demo.tensioner_open(d, name)
        tour._joint_step(a, f"{name}: Top track lift", t, 1.0, up, slide=True)
        tour._joint_step(a, f"{name}: Top track tilt", t + 1.0, 1.0, math.radians(out))
    for lead, drop in demo.cradle_drops(d):
        tour._joint_step(a, lead, t + 1.0, 1.0, drop, slide=True)
    t += 2.0
    tour._joint_step(a, demo.TRAVEL, t, 4.0, q["travel"][1] / 1000.0, slide=True)
    t += 4.0
    tour._joint_step(a, demo.TILT, t, 3.0, math.radians(q["lower_tilt"]))
    t += 3.0
    tour._joint_step(a, demo.TIP, t, 1.0, math.radians(q["hang_tip"]))
    t += 1.0
    depth = demo.SEA_DEPTH - 4.0                       # its lowest point a few metres over the seabed
    tour._joint_step(a, "QUADRANT SYSTEM: Quadrant lower", t, 4.0, depth, slide=True)
    try:
        s.animations_index = len(s.animations) - 1
        animation.bake(sc, a)
        blend = str(tmp_path / "lowering.blend")             # the workers open this build
        bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
        t0 = time.time()
        done = child.check_in_windows(sc, blend, str(tmp_path / "check"), WINDOWS)
        every = [r for x in done for r in x["rows"]]
        print(f"\nlowering check: {time.time() - t0:.0f} s in {len(done)} windows "
              f"({sum(x['seconds'] for x in done):.0f} s of work), {len(every)} rows")
        rows = [r for x in done for r, k in zip(x["rows"], x["kinds"]) if k == "CLASH"]
        assert not rows, rows[:5]
    finally:
        animation.clear_keys(sc)
        s.animations.remove(len(s.animations) - 1)
        s.animations_index = keep
        animation.bake(sc, s.animations[demo.ANIM])
        sc.frame_set(1)
