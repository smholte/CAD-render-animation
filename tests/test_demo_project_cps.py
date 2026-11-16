"""Task 0145 (split from ``test_demo_project.py``): the demo's shots 8b and 9 – a CPS set run from the rack, the
second end hauled in while the D travels, the second end carried over the stern.

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


def test_shot_8b_runs_a_cps_set_from_the_rack(made):
    """Task 0126, the owner's CPS steps 1–5: the set on the ramp's shelf lies where CAD has it until shot 8b; it slides
    tail first down the ramp and the slide, along side B, round the D, down side A to forward of tensioner 2, and back
    until its pull head is at the D's lane-B bar end; shot 9 then shows the second end and its CPS in its place.
    Measured at every frame of the shot (``tests/demo_cps_check.py``): every piece within 2 cm of the CPS's middle line
    (its axis' ends and three points between), and nothing in anything – no corner of a piece inside a roller, cradle,
    rail, rack, trough or the D, nor theirs inside a piece (the clash check leaves riders out: this is its check)."""
    import demo_cps_check as chk

    from fresing_render.blender import animation, build, joints, paths
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    m = demo.cps_run_marks(d)
    item = paths.find(sc, demo.CPS_RUN_ITEM)
    assert item.still and item.part.hide_render and len(item.riders) == 1
    r = item.riders[0]
    pieces = [p.part for p in r.parts]
    cs = d.sheet("route")["cps_store"]
    assert {o.get(build.PROP_UID) for o in pieces} == {o.get(build.PROP_UID) for o in
                                                      paths_riders_parts(d.uid(cs["run_set"]))}
    f0, f9 = _cps_shot(sc, a)
    steps = sorted((b for b in a.blocks if b.kind == "JOINT" and b.joint == m["joint"]), key=lambda b: b.start)
    assert [round(b.to_dist, 3) for b in steps] == [round(m["out"], 3), round(m["home"], 3)]
    assert f0 < animation.frame_of(a, steps[0].start) and animation.frame_of(a, steps[-1].start + steps[-1].duration) < f9
    j = joints.find(sc, m["joint"])
    # before the shot: on the rack, where CAD has it (nothing moved)
    sc.frame_set(f0)
    assert joints.get_value(j) == pytest.approx(0.0, abs=1e-6)
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in pieces:
        assert np.abs(chk._mesh(ob, dg)[0] - chk._mesh(ob)[0]).max() < 1e-3, ob.name
    # its way, every frame (the clash part every second frame, see measure)
    res = chk.measure(sc, d, list(range(f0, f9 + 1)), pieces, chk.near_parts(sc, d), clash_every=2)
    assert res["frames"] == f9 - f0 + 1
    assert res["line"] <= 20.0, res
    assert res["depth"] <= 0.5, res                                # (the clash check's own depth, core.clash.DEPTH)
    # at the end: its pull head at the D's lane-B bar end (where the gutter starts), the second end shown in its place
    sc.frame_set(f9 - 1)
    head = next(o for o in pieces if o.get(build.PROP_NAME) == "PULL HEAD")
    v, _t = chk._mesh(head, bpy.context.evaluated_depsgraph_get())
    R = np.linalg.inv(np.array(d.root().matrix_world)) @ np.array(head.matrix_world)
    v = (v @ R[:3, :3].T + R[:3, 3]) * 1000.0
    nose = v[np.argmin(v[:, 0])]                                  # (it lies on the gutter's start, heading +x)
    assert nose[0] == pytest.approx(float(d.sheet("route")["positions"]["quadrant_x"]), abs=20.0), nose
    shown = {b.target_uid for b in a.blocks if b.kind == "SHOW" and abs(b.start - _t9(a)) < 1e-6}
    hidden = {b.target_uid for b in a.blocks if b.kind == "HIDE" and abs(b.start - _t9(a)) < 1e-6}
    assert cs["run_set"] in hidden and d.sheet("route")["second_end"]["cps"] in shown
    sc.frame_set(1)


def test_the_second_end_is_hauled_in_while_the_d_travels(made):
    """Task 0126 (0125's open point 1): while the D carries the bight aft in shot 9 the second end is hauled in by the
    D's travel, so nothing of it piles up on the seabed then (36 m by the end of the travel before); it first piles up
    while the D is lowered towards the seabed (shot 10)."""
    import re

    from fresing_render.blender import animation, joints, paths
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    said = animation.bake(sc, a)["warnings"]
    se = paths.find(sc, demo.SECOND_ITEM)
    assert not joints.find(sc, se.joint).follows
    steps = sorted((b for b in a.blocks if b.kind == "JOINT" and b.joint == se.joint), key=lambda b: b.start)
    travel = next(b for b in a.blocks if b.kind == "JOINT" and b.joint == demo.TRAVEL and b.to_dist > 0)
    assert len(steps) == 2 and steps[0].start + steps[0].duration < _t9(a)
    assert steps[1].start == travel.start and steps[1].duration == travel.duration
    assert steps[0].to_dist - steps[1].to_dist == pytest.approx(travel.to_dist, abs=1e-4)
    lower = min(b.start for b in a.blocks if b.kind == "JOINT" and b.joint == demo.LOWER)
    piles = [int(m.group(1)) for w in said if "Second end" in w and "piles up" in w
             for m in [re.search(r"at frame (\d+)", w)] if m]
    assert all(f >= animation.frame_of(a, lower) for f in piles), said
    sc.frame_set(1)


def test_shot_9_carries_the_second_end_over_the_stern(made):
    """Tasks 0091, 0095, 0082: shot 9 (shot 7 until 0082) cuts from the lay cable to the second end, drops the lanes'
    cradles in the D's way, opens both tensioners, runs the D-quadrant's whole travel onto the handler, tilts the
    handler to 100° carrying the D (the travel rides on the tilt) and holds there: the D vertical, curve up, hanging
    from the A&R wire over the top pulley – not tipped yet. The clash check over the whole animation
    (test_demo_clash.py) covers this shot too."""
    from mathutils import Vector

    from fresing_render.blender import animation, build, joints
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    s = sc.fresing
    leads = demo.cradle_drops(demo.Demo(sc, made["folder"], VERSION, small=True))
    assert len(leads) == 2                                         # one per lane (task 0102)
    followers = {lead: [j for j in s.joints if j.follows == lead] for lead, _drop in leads}
    assert all(len(f) >= 3 for f in followers.values())
    blocks = _first_steps(a)
    travel = made["sheet"]["joints"]
    t_max = next(j for j in travel if j["name"] == demo.TRAVEL)["limits"][1] / 1000.0
    assert blocks[demo.TRAVEL].to_dist == pytest.approx(t_max)
    assert any("x 60" in b.name for b in a.blocks)

    def part(name):
        return next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == name)
    hf, qf = part("HANDLER FRAME"), part("QUADRANT FRAME")
    fps = int(a.fps)

    def at(seconds):
        sc.frame_set(int(round(seconds * fps)) + 1)
        return hf.matrix_world.inverted() @ qf.matrix_world
    tilt = blocks[demo.TILT]
    assert math.degrees(tilt.to_angle) == pytest.approx(100.0)
    on_handler = at(tilt.start)
    assert math.degrees(joints.get_value(s.joints[demo.TILT])) == pytest.approx(0.0, abs=1e-3)
    assert joints.get_value(s.joints[demo.TRAVEL]) == pytest.approx(t_max, abs=1e-4)
    for lead, drop in leads:
        assert joints.get_value(s.joints[lead]) == pytest.approx(drop, abs=1e-4)
        assert all(joints.get_value(j) == pytest.approx(drop, abs=1e-4) for j in followers[lead])
        assert blocks[lead].start + blocks[lead].duration <= blocks[demo.TRAVEL].start + 1e-6
    # both tensioners open – lifted, tilted out to their own side – before the D travels, and stay open
    for name in demo.TENSIONERS:
        for jn in (f"{name}: Top track lift", f"{name}: Top track tilt"):
            assert blocks[jn].start + blocks[jn].duration <= blocks[demo.TRAVEL].start + 1e-6, jn
        assert math.degrees(joints.get_value(s.joints[f"{name}: Top track tilt"])) == pytest.approx(70.0, abs=1e-3)
        assert joints.get_value(s.joints[f"{name}: Top track lift"]) > 0.85
    end = min(b.start for b in a.blocks if b.kind == "JOINT" and b.joint == demo.TILT and b.start > tilt.start)
    assert end >= tilt.start + tilt.duration + 2.0                 # a hold on the end picture
    tilted = at(end - 0.1)
    assert math.degrees(joints.get_value(s.joints[demo.TILT])) == pytest.approx(100.0, abs=1e-3)
    assert math.degrees(joints.get_value(s.joints[demo.TIP])) == pytest.approx(0.0, abs=1e-6)
    assert np.allclose(np.array(tilted), np.array(on_handler), atol=1e-4)      # the D tilts with the handler
    # vertical, curve up: the D's curve points along its local +x (model mm); in the vessel's frame that is up
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_cable_lay.step"))
    up = root.matrix_world.to_3x3().inverted() @ (qf.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0)))
    assert up.normalized().z > 0.98
    # the D sits on the handler's rails: its bar where the sheet's travel puts it (handler mm: hinge at 0)
    assert on_handler.translation.z * 1000 == pytest.approx(400.0, abs=0.5)
    sc.frame_set(1)
