"""Task 0145 (split from ``test_demo_project.py``): the demo's cable shots – the cable on its path at 10 m/min
(shot 4), the X-ray labels (shot 5), the carousel paying out (shot 3) and the tensioner tracks.

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


def test_the_cable_is_on_its_path_and_runs_at_10_m_per_min(made):
    """Task 0078: the CAD cable is a cable on its path (bends as drawn, the rollers it rests on found, none of their
    joints changed), it has the served-cable look (task 0158), and in shot 4 a Run motor step moves "Cable travel" at 10 m/min:
    the stripes (the look's driver) and a roller's rim go exactly as far."""
    import numpy as np

    from fresing_render.blender import animation, build, cable_looks, joints, paths, paths_sea
    sc = _scene()
    sc.frame_set(sc.frame_start)
    it = paths.find(sc, demo.CABLE_ITEM)
    assert it is not None and it.joint == demo.CABLE and not it.made_joint and it.still and it.look == "SERVED"
    assert it.part.get(build.PROP_NAME) == "CABLE" and paths.status(sc, it)[1] in ("OK", "WARN"), paths.status(sc, it)
    kinds = [c.kind for c in it.contacts]
    assert 8 <= kinds.count("BEND") + kinds.count("CHUTE") <= 14 and 175 <= kinds.count("ROLLER") <= 230, \
        {k: kinds.count(k) for k in set(kinds)}
    assert not any(c.made_joint for c in it.contacts)              # every roller had its joint from the sheet
    rollers = [c for c in it.contacts if c.kind == "ROLLER"]
    assert all(joints.find(sc, c.joint).follows == demo.CABLE for c in rollers)
    # 0102: no S-bends, a shorter oval; 0080: the cable starts where it leaves the coil (the quarter turn is the spool's)
    # 0081: into the sea – the drawn length is the path to horn A + the catenary + 120 m on the seabed
    n = paths_sea.numbers(sc, it)
    on_deck = it.length - n["hanging"] - n["laid"]
    assert it.b_kind == "SEA" and 150.0 < on_deck < 165.0 and abs(it.diameter - 0.2) < 0.002, on_deck
    assert it.part.get("fr_group_manual") == paths.GROUPS["SERVED"]
    assert it.part.material_slots[0].material.get("fr_material") == "cable_served"
    # its yarn and bands on the part, and on the carousel's coil (task 0158)
    assert list(it.part[cable_looks.LOOK])[3] == 3.0 and all(k in it.part for k in cable_looks.PROPS)
    coils = [o for o in bpy.data.objects if o.name.startswith("FR spool") and cable_looks.LOOK in o
             and float(o[cable_looks.LOOK][3]) == 3.0]
    assert coils and all(list(o[cable_looks.YARN]) == list(it.part[cable_looks.YARN]) for o in coils)
    # the drawn tube: the app's, with the attribute the look reads
    dg = bpy.context.evaluated_depsgraph_get()
    me = it.part.evaluated_get(dg).data
    assert cable_looks.ATTR in me.attributes and len(me.vertices) > 5000
    # shot 4: 7 s at 10 m/min
    a = sc.fresing.animations[demo.ANIM]
    step = next(b for b in a.blocks if b.kind == "MOTOR" and b.joint == demo.CABLE)
    assert step.speed_mmin == pytest.approx(10.0, rel=1e-6)
    if not animation.has_keys(sc):
        animation.bake(sc, a)
    f0, f1 = animation.frame_of(a, step.start), animation.frame_of(a, step.start + step.duration)
    cab = joints.find(sc, demo.CABLE)
    c = rollers[len(rollers) // 2]
    j = joints.find(sc, c.joint)
    seen = []
    for f in (f0, f1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        seen.append((joints.get_value(cab), float(it.part[cable_looks.PAY]) - cable_looks.PAY_BIAS, joints.get_value(j)))
    run = seen[1][0] - seen[0][0]
    assert run == pytest.approx(10.0 / 60.0 * step.duration, rel=1e-4)
    assert abs(seen[1][1] - seen[1][0]) < 0.001 and abs(seen[0][1] - seen[0][0]) < 0.001      # stripes: within 1 mm
    rim = abs(seen[1][2] - seen[0][2]) * (paths.radius_of(it, c) - 0.5 * it.diameter)
    assert rim == pytest.approx(run, rel=0.02), (rim, run)        # the roller's rim (Draft meshes: within 2 %)
    assert np.isfinite(paths.shape_now(sc, it)).all()
    sc.frame_set(1)


def test_xray_labels_apart_and_inside_the_picture(made):
    """Task 0091: in shot 5's X-ray step no two label boxes overlap and every box lies inside the picture (with the
    placer's margin), on every frame of the step, at the video's size (HD) and smaller."""
    from fresing_render.blender import animation, callouts
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    fps = int(a.fps)
    w = callouts.window_for(a, sc.fresing.callouts[0])
    boxes = callouts.PartBoxes(sc)
    for size in ((1920, 1080), (960, 540)):
        margin = 0.02 * min(size)
        seen = 0
        for f in range(int(w[0] * fps), int(w[1] * fps) + 1, 3):
            sc.frame_set(f + 1)
            d = callouts.draws_at(sc, size, f / fps, a, "", boxes)
            seen = max(seen, len(d))
            for i, x in enumerate(d):
                assert x.box.inside(size[0], size[1], margin - 1.0), (size, f, x.text)
                for y in d[i + 1:]:
                    assert not x.box.overlaps(y.box), (size, f, x.text, y.text)
        assert seen == len(demo.LABELS), size
    sc.frame_set(1)


def test_shot_3_pays_out_the_carousel_and_the_arch_follows(made):
    """Task 0080: the carousel's coil is a spool of the power cable on "Cable travel" – the carousel turns by table,
    the arch slews and the guide's cage swivels with the layer in shot 3; handling winch 1 spools its wire on its
    Lebus drum; each cable leaves its spool on the circle of its layer."""
    import numpy as np

    from fresing_render.blender import animation, joints, paths, spool
    from fresing_render.core import spool as S
    sc = _scene()
    car = spool.find(sc, demo.SPOOL_ITEM)
    assert car is not None and car.kind == "CAROUSEL" and car.enabled and not car.problem, car and car.problem
    # task 0159: full to the rim – the cable leaves the top layer the carousel holds or the one below it, an even
    # layer (index odd: wound from the rim inwards, as the route and the guide cage expect), with over 40 km on it
    path = spool.path_of(sc, car)
    top = int(S.at(path, car.wound)[3])
    assert top % 2 == 1 and top >= path.layer_count - 2 and 40000.0 < car.wound < path.total, (top, car.wound)
    assert joints.find(sc, car.joint).couple_table == f"spool:{demo.SPOOL_ITEM}"
    assert sorted(f.mode for f in car.followers) == ["ALONG", "ARM"]
    win = spool.find(sc, demo.WINCH_SPOOL)
    assert win is not None and win.groove == "LEBUS" and win.kind == "DRUM"
    a = sc.fresing.animations[demo.ANIM]
    if not animation.has_keys(sc):
        animation.bake(sc, a)
    step = next(b for b in a.blocks if b.kind == "JOINT" and b.joint == demo.CABLE and "top layer" in b.name)
    f0, f1 = animation.frame_of(a, step.start), animation.frame_of(a, step.start + step.duration)
    arch = joints.find(sc, next(f.joint for f in car.followers if f.mode == "ARM"))
    seen = []
    for f in (f0, (f0 + f1) // 2, f1):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        p = spool.payout(sc, car)
        start = np.asarray(paths.shape_now(sc, paths.find(sc, car.cable))[0], dtype=float)
        loc = np.linalg.inv(spool.frame_cad(sc, car, {})) @ np.r_[start, 1.0]
        _phi, _a, r, _k = S.at(spool.path_of(sc, car), np.array([car.wound - p]))
        # (the vessel moves the frame: compare in its own coordinates, Draft meshes)
        assert math.hypot(loc[0], loc[1]) == pytest.approx(float(r[0]), abs=0.005), f
        seen.append((p, joints.get_value(arch), joints.get_value(joints.find(sc, car.joint))))
    assert seen[-1][0] - seen[0][0] == pytest.approx(demo.SPEED / 60.0 * 10.0 * demo.LAPSE, rel=1e-3)
    assert abs(seen[-1][1] - seen[0][1]) > math.radians(0.5)          # the arch slewed with the layer
    assert abs(seen[-1][2] - seen[0][2]) > 2.0 * math.pi * 2.5        # the carousel turned some 3 times
    sc.frame_set(1)


def test_tensioner_tracks_run_with_the_cable(made):
    """Task 0079: the four tracks of the two tensioners run on "Cable travel": the pads on the gripping runs move with
    the cable (shot 5 runs it while the top track squeezes), every link's two hinges on its loop one pitch apart, the
    sprockets one tooth per link; it costs little per frame."""
    import time

    import numpy as np

    from fresing_render.blender import animation, joints, tracks
    sc = _scene()
    its = list(tracks.items(sc))
    assert len(its) == 4 and all(it.joint == demo.CABLE for it in its)
    assert all((it.links, it.parts) == (36, 108) and tracks.status(sc, it)[1] == "OK" for it in its), \
        [tracks.status(sc, it) for it in its]
    assert all(it.length == pytest.approx(36 * 0.3, abs=1e-5) for it in its)
    for it in its:                                    # the sprockets follow the cable at one tooth per link, as made
        for w in it.wheels:
            j = joints.find(sc, w.joint)
            assert j.follows == demo.CABLE and not w.made_joint and not w.note, (it.name, w.name, w.note)
            assert abs(j.couple_ratio) == pytest.approx(math.degrees((2 * math.pi / 8) / 0.3) / 1000.0, rel=1e-6)
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    shot = next(b for b in a.blocks if b.kind == "MOTOR" and b.joint == demo.CABLE and b.start > 30.0)
    f0 = animation.frame_of(a, shot.start + 1.0)
    cab = joints.find(sc, demo.CABLE)
    for it in its:
        sc.frame_set(f0)
        v0, t0 = joints.get_value(cab), tracks.travel_now(sc, it)
        sc.frame_set(f0 + 25)
        v1, t1 = joints.get_value(cab), tracks.travel_now(sc, it)
        assert v1 - v0 == pytest.approx(10.0 / 60.0, rel=1e-3)
        assert abs((t1 - t0) % it.length) == pytest.approx(v1 - v0, rel=1e-3) or \
            abs((t0 - t1) % it.length) == pytest.approx(v1 - v0, rel=1e-3)
        for ob in [o for o in tracks.parts_of(sc, it) if o.get(tracks.ROLE) == "link"][::6]:
            a_, b_ = tracks.hinge_world(sc, it, ob)
            assert abs(np.linalg.norm(b_ - a_) - 0.3) < 5e-5
    # per frame: the shot's frames with the tracks on and off
    frames = list(range(f0, f0 + 40))

    def per_frame():
        t = time.perf_counter()
        for f in frames:
            sc.frame_set(f)
        return (time.perf_counter() - t) / len(frames) * 1000.0
    per_frame()
    on = per_frame()
    for it in its:
        it.enabled = False
    off = per_frame()
    for it in tracks.items(sc):
        it.enabled = True
    secs = made["out"]["seconds"]
    print(f"\nper frame with the 4 tracks running: {on:.1f} ms, off: {off:.1f} ms; stage 'tracks' "
          f"{secs.get('tracks', 0.0):.1f} s of {sum(secs.values()):.0f} s to make the demo")
    animation.clear_keys(sc)
    sc.frame_set(1)
