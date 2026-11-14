"""Task 0077: the demo project "Cable-lay vessel" (Help > Make demo project, ``fresing_render/blender/demo.py``).

Blender as a Python module. The project is made once in its scaled-down form (the PC check's on GitHub: Draft meshes,
no quay model; the same joints, cylinders, cameras and animation), then checked: every joint of the sheet with its
type, limits, stack and coupling; a coupling's ratio; drivers that work with scripts off; the animation; save,
reopen and Build again; Cancel; the stage list later tasks extend.
"""

import json
import math
import os
import shutil
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from fresing_render.blender import demo  # noqa: E402

VERSION = "9.9.9"


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("demo") / "Demo é")
    seen = []
    out = demo.build_project(folder, VERSION, small=True,
                             progress=lambda st, text, done, total: seen.append((st, text)))
    models = str(tmp_path_factory.mktemp("models"))
    for f in os.listdir(demo.model_dir(folder, VERSION)):
        shutil.copy(os.path.join(demo.model_dir(folder, VERSION), f), models)
    with open(os.path.join(models, "demo_joints.json"), encoding="utf-8") as fh:
        sheet = json.load(fh)
    bpy.ops.wm.open_mainfile(filepath=out["path"])
    yield {"folder": folder, "out": out, "seen": seen, "models": models, "sheet": sheet}
    fresing_render.unregister()


def _scene():
    return bpy.context.scene


def test_the_project_is_made_and_saved(made):
    folder, out = made["folder"], made["out"]
    assert out["path"] == demo.project_path(folder, VERSION) and os.path.isfile(out["path"])
    assert demo.exists(folder, VERSION)
    assert not os.path.exists(demo.progress_path(folder, VERSION))        # only while it is made
    sc = _scene()
    assert sc.get(demo.TAG) == VERSION and demo.is_demo(sc)
    info = demo.read_summary(folder, VERSION)
    assert info["joints"] == len(sc.fresing.joints) and info["animation"] == demo.ANIM
    # the status line went through the stages with counts
    texts = [t for _s, t in made["seen"]]
    assert any(t.startswith("Writing the model") for t in texts)
    assert "Importing" in texts and any(t.startswith("Joints ") for t in texts) and "Animation" in texts


def test_every_joint_of_the_sheet(made):
    from mathutils import Vector

    from fresing_render.blender import build, joints, paths
    sc = _scene()
    sc.frame_set(1)
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_cable_lay.step"))
    M = root.matrix_world.copy()
    sheet = made["sheet"]["joints"]
    assert len(sheet) == 310                           # task 0102: no S-bend cradles; the cradles that drop
    by = {j.name: j for j in sc.fresing.joints}
    # + Cable travel and handling winch 1's wire speed (task 0080; no quay in the small form)
    # task 0082: the speed joints of the A&R wire, the two tipping wires and the second end
    wires = [paths.find(sc, n).joint for n in (demo.AR_ITEM, demo.SECOND_ITEM) + tuple(n for _k, n in demo.TIP_ITEMS)]
    assert len(by) == len(sheet) + 2 + 4 and demo.CABLE in by and demo.WINCH_TRAVEL in by and all(w in by for w in wires)
    cable_turned = spooled = 0
    for row in sheet:
        j = by.get(row["name"])
        assert j is not None, row["name"]
        assert j.kind == ("ROTATE" if row["type"] == "rotate" else "SLIDE"), row["name"]
        moved = {o.get(build.PROP_UID) for o in joints.moved_objects(sc, j)}   # a rider may carry the same part
        assert set(row["parts"]) <= moved, row["name"]
        lim = row["limits"]
        if lim is None:
            assert not j.use_limits, row["name"]
        elif j.kind == "ROTATE":
            assert j.use_limits and math.isclose(math.degrees(j.rot_min), lim[0], abs_tol=1e-3) \
                and math.isclose(math.degrees(j.rot_max), lim[1], abs_tol=1e-3), row["name"]
        else:
            assert j.use_limits and math.isclose(j.slide_min * 1000, lim[0], abs_tol=1e-2) \
                and math.isclose(j.slide_max * 1000, lim[1], abs_tol=1e-2), row["name"]
        below = joints.rides_on(sc, j)
        assert (below.name if below else None) == row.get("rides_on"), row["name"]
        drive = row["drive"]
        if j.couple_table:                                          # follows its spool's layer by table (task 0080)
            assert j.couple_table in (f"spool:{demo.SPOOL_ITEM}", f"spool:{demo.WINCH_SPOOL}",
                                      f"spool:{demo.AR_SPOOL}"), row["name"]
            spooled += 1
        elif j.follows in wires:                                    # turned by a tipping wire (task 0082)
            assert "TIPPING" in row["name"] or "Swivel sheave" in row["name"], row["name"]
        elif row["name"] == demo.PULLEY_TURN:                       # turned by the lowering's steps (task 0082)
            assert not j.follows
        elif j.follows == demo.WINCH_TRAVEL:                        # turned by handling winch 1's wire
            assert "Fairlead" in row["name"], row["name"]
        elif drive.get("by") == "follows":
            assert j.follows == drive["follows"] and math.isclose(j.couple_ratio, drive["ratio"], rel_tol=1e-5)
        elif drive.get("by") in ("cable", "carousel"):
            assert j.follows == demo.CABLE and math.isclose(j.couple_ratio, drive["deg_per_mm"], rel_tol=1e-5)
            cable_turned += 1
        else:
            assert not j.follows, row["name"]
        # the axis where the sheet puts it (model mm, in the model's frame: the vessel moves with the sea)
        o, d = joints.axis_world(j)
        p = np.array(M @ Vector(np.array(row["axis"]["point"]) / 1000.0))
        dv = np.array((M.to_3x3() @ Vector(row["axis"]["direction"])).normalized())
        assert np.linalg.norm(np.cross(np.array(o) - p, dv)) < 1e-4, row["name"]
        assert abs(abs(float(np.dot(np.array(d), dv))) - 1.0) < 1e-6, row["name"]
    assert cable_turned >= 204                          # 0102: fewer highway cradles (no S-bends; none where the
    #                                                     D's bar stands at rest or on the rise's top); 0080: the carousel by table
    assert spooled == 6       # carousel, arch, guide cage; handling winch 1's drum (0080) + level wind (0081); A&R drum (0082)


def test_a_coupling_turns_at_its_ratio(made):
    from fresing_render.blender import joints
    sc = _scene()
    s = sc.fresing
    from fresing_render.blender import animation
    animation.clear_keys(sc)
    cable = s.joints[demo.CABLE]
    row = next(r for r in made["sheet"]["joints"] if r["drive"].get("by") == "cable")
    roller = s.joints[row["name"]]
    member = joints.members(roller)[0]
    bpy.context.view_layer.update()
    before = member.matrix_world.copy()
    joints.set_value(cable, 0.25)                                   # 250 mm of cable
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    want = math.radians(row["drive"]["deg_per_mm"] * 250.0)
    assert math.isclose(joints.get_value(roller), want, rel_tol=1e-4)
    turned = (before.inverted() @ member.matrix_world).to_quaternion().angle
    assert math.isclose(turned, abs(want) % (2 * math.pi), abs_tol=1e-3)
    # the carousel's support rollers follow the carousel, which follows the cable
    car = s.joints["CAROUSEL: Carousel turn"]
    sup = s.joints["CAROUSEL: Support roller 11100-1 turn"]
    assert math.isclose(joints.get_value(sup), joints.get_value(car) * sup.couple_ratio, rel_tol=1e-4)
    joints.set_value(cable, 0.0)


def test_cylinders_follow_the_handler(made):
    """The handler's two cylinders follow its tilt; the tensioners' four tilt cylinders (task 0102), pinned on the lift
    frame and on the tilting carriage, follow the lift and the tilt: at 70° each is longer by about half a metre."""
    from mathutils import Vector

    from fresing_render.blender import cylinders, joints
    sc = _scene()
    s = sc.fresing
    assert len(s.cylinders) == 2 + 4
    tilt = s.joints["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]
    c = s.cylinders[0]
    length0 = cylinders.length_now(c)
    joints.set_value(tilt, math.radians(60))
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    assert abs(cylinders.length_now(c) - length0) > 0.2          # the rod slides as the handler tilts
    joints.set_value(tilt, 0.0)
    bpy.context.view_layer.update()
    for k in (1, 2):
        lift, top = s.joints[f"TENSIONER {k}: Top track lift"], s.joints[f"TENSIONER {k}: Top track tilt"]
        mine = [c for c in s.cylinders if c.name.startswith(f"Tensioner {k} tilt cylinder")]
        assert len(mine) == 2
        before = [cylinders.length_now(c) for c in mine]
        joints.set_value(lift, 0.9)
        joints.set_value(top, math.radians(70.0))
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()
        after = [cylinders.length_now(c) for c in mine]
        assert all(0.4 < b - a < 0.7 for a, b in zip(before, after)), (before, after)
        joints.set_value(top, 0.0)
        joints.set_value(lift, 0.0)
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()
        assert [cylinders.length_now(c) for c in mine] == pytest.approx(before, abs=1e-4)
    del Vector


def test_drivers_work_with_scripts_off(made):
    n = 0
    for ob in _scene().objects:
        ad = ob.animation_data
        if ad is None:
            continue
        for fc in ad.drivers:
            drv = fc.driver
            assert drv.type != "SCRIPTED" or drv.is_simple_expression, (ob.name, drv.expression)
            n += 1
    assert n >= 300


def test_scenes_cameras_brand_and_the_animation(made):
    sc = _scene()
    s = sc.fresing
    assert s.shots.get(demo.SEA_SHOT) is not None
    for name in demo.VIEWS:
        assert s.shots.get(name) is not None and sc.objects.get(name) is not None, name
    assert s.brand_name == "Demo" and os.path.isfile(bpy.path.abspath(s.brand_logo))
    a = s.animations[demo.ANIM]
    body = max(b.start + b.duration for b in a.blocks)
    cards = (a.fin_title_seconds if a.fin_title_on else 0) + (a.fin_end_seconds if a.fin_end_on else 0)
    assert 60.0 <= body + cards <= 150.0, body + cards         # (0081: shot 8, 10 s more; 0082: shots 9–12, ~55 s)
    kinds = {(b.kind, b.camera_mode if b.kind == "CAMERA" else "") for b in a.blocks}
    assert {("CAMERA", "PATH"), ("CAMERA", "ORBIT"), ("CAMERA", "RIDE"), ("JOINT", ""), ("FADE_OUT", ""),
            ("FADE_IN", "")} <= kinds
    assert any(f"x {demo.LAPSE}" in b.name for b in a.blocks) and a.fin_captions   # the time-lapse in a caption
    assert len(s.callouts) >= 3 and all(c.step == demo.XRAY_STEP for c in s.callouts)
    assert s.background == "SEA"


def _keys(sc):
    """Every key the Build wrote (layered actions: the channel bag of each object's slot)."""
    from bpy_extras import anim_utils
    out = {}
    for ob in sc.objects:
        ad = ob.animation_data
        if ad is None or ad.action is None or ad.action_slot is None:
            continue
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves if cb is not None else []:
            pts = np.array([tuple(k.co) for k in fc.keyframe_points])
            out[(ob.name, fc.data_path, fc.array_index)] = pts
    return out


def test_save_reopen_and_build_again_gives_the_same_keys(made, tmp_path):
    from fresing_render.blender import animation
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    animation.bake(sc, a)
    first = _keys(sc)
    assert len(first) > 15                  # the moved joints, the camera, the fades (followers are drivers)
    path = str(tmp_path / "again.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = _scene()
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    again = _keys(sc)
    assert set(again) == set(first)
    for k, v in first.items():
        assert v.shape == again[k].shape and np.allclose(v, again[k], atol=1e-5), k
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


# test_no_clash_in_the_animation: in tests/test_demo_clash.py since task 0108 (four processes at once)


def test_the_cable_is_on_its_path_and_runs_at_10_m_per_min(made):
    """Task 0078: the CAD cable is a cable on its path (bends as drawn, the rollers it rests on found, none of their
    joints changed), it has the power-cable look, and in shot 4 a Run motor step moves "Cable travel" at 10 m/min:
    the stripes (the look's driver) and a roller's rim go exactly as far."""
    import numpy as np

    from fresing_render.blender import animation, build, cable_looks, joints, paths, paths_sea
    sc = _scene()
    sc.frame_set(sc.frame_start)
    it = paths.find(sc, demo.CABLE_ITEM)
    assert it is not None and it.joint == demo.CABLE and not it.made_joint and it.still and it.look == "POWER"
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
    assert it.part.get("fr_group_manual") == paths.GROUPS["POWER"]
    assert it.part.material_slots[0].material.get("fr_material") == "cable_power"
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


def _first_steps(a) -> dict:
    """The first Move step of each joint in shot 9 and later (the quadrant operation)."""
    t9 = next(b.start for b in a.blocks if b.kind == "HIDE" and b.target_name == "CABLE")
    out = {}
    for b in sorted((b for b in a.blocks if b.kind == "JOINT" and b.start >= t9 - 1e-6), key=lambda b: b.start):
        out.setdefault(b.joint, b)
    return out


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


def _solved(sc, item):
    """The cable solved over the built frames as Build solved it: (result, first frame)."""
    from fresing_render.blender import paths
    _w, slots, *_ = paths._inputs_of(item)
    rel, first = paths._stored_places(sc, item, slots)[:2]
    return paths._solve_item(sc, item, rel, first=first), first


def _dense(P, step=0.25):
    out = [P[:1]]
    for a_, b_ in zip(P[:-1], P[1:]):
        n = max(1, int(math.ceil(np.linalg.norm(b_ - a_) / step)))
        out.append(a_ + (b_ - a_) * (np.arange(1, n + 1) / n)[:, None])
    return np.concatenate(out)


def test_the_quadrant_operation_shots_10_to_12(made):
    """Task 0082, the owner's steps 8–15: the handler tilts on to LOWER_TILT and the D hangs plumb (the sheet's hang
    tip); the A&R winch lowers it to 1.5 m over the seabed with the vessel creeping on; it tips towards flat and is
    lowered until the cable round its gutter lies on the seabed, where the second end is let go (its start and the
    gutter's turn); it comes back up, tilts back, travels back, the tensioners close and the cradles rise.
    Every frame from shot 9 on: the second end is exactly as long as it is (its sea end keeps it: nothing is paid out
    from shot 9 on; exactly in the solver's own measure, within 1 m – 0.5 % – along the drawn points' chords), with a path everywhere but a few frames where the D lifts its turn off horn
    A (kept as before: at most 6 frames); the bend round the D's gutter never tighter than its MBR; the second end's
    CPS rides at its start, the pull head at the D's bar end."""
    from mathutils import Vector

    from fresing_render.blender import animation, build, joints, paths, paths_sea
    sc = _scene()
    s = sc.fresing
    a = s.animations[demo.ANIM]
    animation.bake(sc, a)
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    q = d.sheet("route")["quadrant"]
    ids = [x.id for x in demo.STAGES]
    assert ids.index("shot_sea") < ids.index("quadrant_ops") < ids.index("shot_quadrant") < ids.index("shot_lower") \
        < ids.index("shot_tip") < ids.index("shot_back") < ids.index("finish")
    steps = [b for b in a.blocks if b.kind == "JOINT"]
    t9 = next(b.start for b in a.blocks if b.kind == "HIDE" and b.target_name == "CABLE")
    tilts = [math.degrees(b.to_angle) for b in steps if b.joint == demo.TILT]
    assert tilts == pytest.approx([100.0, q["lower_tilt"], 0.0])
    lowers = [b.to_dist for b in sorted((b for b in steps if b.joint == demo.LOWER), key=lambda b: b.start)]
    assert lowers[0] > 25.0 and lowers[1] > lowers[0] and lowers[-1] == 0.0
    tips = [math.degrees(b.to_angle) for b in sorted((b for b in steps if b.joint == demo.TIP), key=lambda b: b.start)]
    assert tips[0] == pytest.approx(q["hang_tip"]) and tips[1] == pytest.approx(-q["lower_tilt"]) and tips[-1] == 0.0
    # from shot 9 on 'Cable travel' stands still: the second end follows it, nothing of it is paid out
    assert not [b for b in a.blocks if b.joint == demo.CABLE and b.start + b.duration > t9]
    assert sum(1 for b in a.blocks if "(x " in b.name) >= 4                 # the time-lapse captions
    se = paths.find(sc, demo.SECOND_ITEM)
    assert se.b_kind == "SEA" and paths.let_go_frame(se, "a") > 0
    let_go = paths.let_go_frame(se, "a")
    gutter = [i for i, c in enumerate(se.contacts) if c.part is not None and c.part.get(build.PROP_NAME) == "QUADRANT GUTTER"
              and c.kind != "ROLLER"]
    assert gutter and all(paths.let_go_frame(se, str(i)) == let_go for i in gutter)
    # the length, the path, the MBR round the gutter: every second frame from shot 9 on
    f9 = animation.frame_of(a, t9) + 1
    res, first = _solved(sc, se)
    bad = sorted(k + first for k in res["problems"] if k + first >= f9)
    assert len(bad) <= 6, bad
    # the solver's own length (its arc length along the drawn points) is the cable's: its sea end's mark + paid out
    want = se.sea_mark + paths_sea.payout(sc, se)
    good = [k for k in range(f9 - first, len(res["ok"])) if res["ok"][k]]
    assert np.abs(np.asarray(res["length"])[good] - want).max() < 0.001
    quad = d.uid(q["uid"])
    arc = d.sheet("route")["second_end"]["route"]["segments"][0]
    sc.frame_set(1)                                              # the D in its CAD place: model -> its own frame
    to_quad = np.linalg.inv(np.array(quad.matrix_world)) @ np.array(d.root().matrix_world)
    worst_len, worst_r = 0.0, 1e9
    bed = paths_sea.bottom_z(sc, se)
    for f in range(f9, int(sc.frame_end) + 1, 2):
        sc.frame_set(f)
        P = paths.shape_now(sc, se)
        assert np.isfinite(P).all()
        L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
        worst_len = max(worst_len, abs(L - (se.sea_mark + paths_sea.payout(sc, se))))
        if f < let_go:                                           # round the gutter: its circle, carried by the D
            W = np.array(quad.matrix_world) @ to_quad
            c = W @ np.r_[np.array(arc["centre"]) / 1000.0, 1.0]
            n = W[:3, :3] @ np.array(arc["normal"])
            rel = P - c[:3]
            h = rel @ n
            on = (np.abs(np.linalg.norm(rel - np.outer(h, n), axis=1) - arc["radius"] / 1000.0) < 0.05) & \
                (np.abs(h) < 0.05)
            if len(P) >= 3:                                      # three points in a row along the cable, all on it
                A_, B_, C_ = P[:-2], P[1:-1], P[2:]
                area = 0.5 * np.linalg.norm(np.cross(B_ - A_, C_ - A_), axis=1)
                ab, bc, ca = (np.linalg.norm(x, axis=1) for x in (B_ - A_, C_ - B_, A_ - C_))
                # the turn round the gutter, less its last 0.6 m towards the sea: where the cable leaves the gutter for
                # the sea the catenary may leave out of the gutter's plane at the start of the lowering (the hang-off's
                # own kink – an open point of the sea end, not the bend round the gutter)
                inner = on.copy()
                ends = np.flatnonzero(on & ~np.r_[on[1:], False])                 # the last point of each run
                s_on = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
                for e in ends:
                    inner &= ~((s_on > s_on[e] - 0.6) & (s_on <= s_on[e]))
                keep = inner[:-2] & inner[1:-1] & inner[2:] & (area > 1e-9) & (np.minimum(ab, bc) > 0.05)
                if keep.any():
                    worst_r = min(worst_r, float((ab * bc * ca / (4 * area))[keep].min()))
        if f == let_go:                                          # the cable round the gutter lies on the seabed
            root_z = (d.root().matrix_world.inverted() @ Vector(P[0])).z
            assert abs(root_z - bed) < 0.8, (root_z, bed)
    assert worst_len < 1.0, worst_len                        # (the drawn points' chords: within 0.5 %)
    assert worst_r >= 0.98 * se.mbr, (worst_r, se.mbr)
    # the CPS rides at its start: the pull head at the D's bar end, where the second end starts, at shot 9's start
    sc.frame_set(f9)
    head = next(p.part for r in se.riders for p in r.parts
                if p.part is not None and p.part.get(build.PROP_NAME) == "PULL HEAD")
    P = paths.shape_now(sc, se)
    mid = sum((head.matrix_world @ Vector(v) for v in head.bound_box), Vector()) / 8.0
    assert (mid - Vector(P[0])).length < 1.5
    # the D comes back to its stationary place, the tensioners close, the cradles rise, the wires are taken off
    sc.frame_set(int(sc.frame_end))
    for jn in (demo.TRAVEL, demo.TILT, demo.LOWER, demo.TIP):
        assert joints.get_value(s.joints[jn]) == pytest.approx(0.0, abs=1e-4), jn
    for name in demo.TENSIONERS:
        assert joints.get_value(s.joints[f"{name}: Top track lift"]) == pytest.approx(0.0, abs=1e-4)
    assert all(paths.find(sc, n).part.hide_render for _k, n in demo.TIP_ITEMS)
    sc.frame_set(1)


def test_the_wires_of_the_quadrant_operation(made):
    """Task 0082: the A&R wire and the tipping wires are cables of 4 Motion > Cables and paths, each kept tight by its
    winch (none skipped). The A&R wire is spooled on its drum (the drum follows it by table) and runs straight to the
    D's eye while the D travels; from ~10° of tilt it bears on the handler's top pulley, and over the lowering it
    runs over it. The tipping wires' winch drums and foot sheaves follow their wires' speed joints, the head sheaves
    turn with the wires; while connected (shots 9–12) the wires never run through the handler, the stern or the horns.
    Every frame after shot 8 has a path for each wire."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from fresing_render.blender import animation, build, joints, paths
    sc = _scene()
    s = sc.fresing
    a = s.animations[demo.ANIM]
    animation.bake(sc, a)
    ar = paths.find(sc, demo.AR_ITEM)
    assert ar.keep_tight and paths.tight_skipped(sc, ar) == "" and ar.a_kind == "SPOOL"
    assert s.joints[demo.AR_DRUM].couple_table == f"spool:{demo.AR_SPOOL}"
    for key, name in demo.TIP_ITEMS:
        it = paths.find(sc, name)
        assert it.keep_tight and paths.tight_skipped(sc, it) == "", name
        for jn in (f"QUADRANT SYSTEM: Swivel sheave {key} foot sheave turn",
                   f"QUADRANT SYSTEM: TIPPING WINCH {key.upper()}: Drum turn", f"QUADRANT SYSTEM: Swivel sheave {key} turn"):
            assert s.joints[jn].follows == it.joint, jn
    t9 = next(b.start for b in a.blocks if b.kind == "HIDE" and b.target_name == "CABLE")
    f9 = animation.frame_of(a, t9)
    for it in [ar] + [paths.find(sc, n) for _k, n in demo.TIP_ITEMS]:
        res, first = _solved(sc, it)
        assert not [k for k in res["problems"] if k + first >= f9], it.name
    # the A&R wire: off the pulley while the D travels, over it from ~10° of tilt to the end of the lowering
    res, first = _solved(sc, ar)
    k = [i for i, c in enumerate(paths._wheels(ar)) if c.part is not None
         and c.part.get(build.PROP_NAME) == "HANDLER TOP PULLEY"][0]
    tilt = s.joints[demo.TILT]
    theta0 = demo.ar_contact_tilt(demo.Demo(sc, made["folder"], VERSION, small=True))
    seen = 0
    for f in range(f9, int(sc.frame_end) + 1, 5):
        sc.frame_set(f)
        th = math.degrees(joints.get_value(tilt))
        w = float(res["wrap"][f - first, k])
        if th < theta0 - 3.0:
            assert w == 0.0, (f, th, w)
        elif th > theta0 + 3.0:
            assert w > 0.05, (f, th, w)
            seen += 1
    assert seen > 20
    # the tipping wires never through steel while they are shown
    names = {"HANDLER FRAME", "QUADRANT RAIL", "HINGE BRACKET", "HINGE PIN", "CHUTE", "HULL", "HULL BOTTOM",
             "MAIN DECK", "BULWARK", "HANDLER TOP PULLEY", "PISTON ROD", "CYLINDER BRACKET"}
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [(o, BVHTree.FromObject(o, dg)) for o in build.iter_parts(sc) if o.get(build.PROP_NAME) in names]
    assert len(trees) >= 10
    near, shown = [], 0
    for f in range(f9, int(sc.frame_end) + 1, 10):
        sc.frame_set(f)
        for _key, name in demo.TIP_ITEMS:
            it = paths.find(sc, name)
            if it.part.hide_render:
                continue
            shown += 1
            r = 0.5 * it.diameter
            P = _dense(paths.shape_now(sc, it))
            for o, t in trees:
                Mi = o.matrix_world.inverted()
                for q in P:
                    hit = t.find_nearest(Mi @ Vector(q))
                    if hit[0] is not None and (o.matrix_world @ hit[0] - Vector(q)).length < r - 0.002:
                        near.append((f, name, o.get(build.PROP_NAME)))
                        break
    assert shown > 20 and not near, near[:5]
    sc.frame_set(1)


def test_the_quadrant_operations_parts_are_hidden_until_shot_9(made):
    """Task 0082: the model's A&R wire, tipping wires, the cable's second end and its CPS set are hidden where the
    animation starts (Show steps bring them in from shot 9) and were kept out (excluded) while the lay cable was read,
    so none of them is a contact of it; they are cables (the CPS a rider) now, so the clash check leaves them out.
    0095's constraint and driver wires are gone; the joints of the quadrant: 'Quadrant lower' rides on the travel and
    the tip on it, the handler tilts to LOWER_TILT, and the A&R winch's drum follows its wire by table."""
    from fresing_render.blender import animation, build, joints, logic, paths, paths_riders
    sc = _scene()
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    sc.frame_set(1)
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    objs = demo.quadrant_ops_parts(d)
    names = sorted(o.get(build.PROP_NAME) for o in objs)
    assert names == ["A&R WIRE", "CABLE END", "CPS SET", "TIPPING WIRE", "TIPPING WIRE"], names
    parts = [t for o in objs for t in [o] + list(logic.descendants(o)) if t.get(build.PROP_KIND) == "part"]
    assert all(t.hide_render and not t.get(build.PROP_EXCLUDED) for t in parts)
    cables = {o.name for o in paths.cable_parts(sc)} | {o.name for o in paths_riders.rider_parts(sc)}
    assert all(t.name in cables for t in parts)
    assert not bpy.data.collections.get("FR demo wires")
    assert not [o for o in sc.objects if o.get("fr_demo_wire")]
    # the lay cable's contacts: nothing of the quadrant operation's own parts
    it = paths.find(sc, demo.CABLE_ITEM)
    held = {t.name for t in parts}
    assert not [c.part.name for c in it.contacts if c.part is not None and c.part.name in held]
    s = sc.fresing
    low = s.joints["QUADRANT SYSTEM: Quadrant lower"]
    assert joints.rides_on(sc, low).name == demo.TRAVEL
    assert joints.rides_on(sc, s.joints[demo.TIP]).name == low.name
    assert math.degrees(s.joints[demo.TILT].rot_max) == pytest.approx(110.0, abs=1e-3)
    assert s.joints[demo.AR_DRUM].couple_table == f"spool:{demo.AR_SPOOL}"
    assert "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn on tilt" not in s.joints


def test_the_d_lowered_on_its_wire_runs_into_nothing(made):
    """Task 0082: the D's whole way on the new joint – tensioners open, cradles down, the travel onto the handler, the
    tilt to LOWER_TILT, the turn to hang plumb (the sheet's hang tip) and the lowering on 'Quadrant lower' to near the
    seabed – gives 0 clash rows (the sea at rest, as the demo's check): the D, the handler, the rails, the tensioners,
    the horns and the stern stay apart. Its own short animation, the demo's is built again afterwards."""
    from fresing_render.blender import animation, clash, tour, vessel_motion
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
        t0 = time.time()
        with vessel_motion.at_rest(sc):
            res = clash.check(sc, store=False)
        print(f"\nlowering check: {time.time() - t0:.0f} s, {len(res.rows)} rows")
        rows = [r for r in res.rows if r.kind == "CLASH"]
        assert not rows, [(r.a, r.b, r.frame_from, round(r.depth * 1000, 1)) for r in rows[:5]]
    finally:
        animation.clear_keys(sc)
        s.animations.remove(len(s.animations) - 1)
        s.animations_index = keep
        animation.bake(sc, s.animations[demo.ANIM])
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


def test_cancel_leaves_nothing(made, tmp_path, monkeypatch):
    folder = str(tmp_path / "cancel")

    def copy_model(d):
        os.makedirs(d.model_dir, exist_ok=True)
        for f in os.listdir(made["models"]):
            shutil.copy(os.path.join(made["models"], f), d.model_dir)
    monkeypatch.setattr(demo, "_run_maker", copy_model)

    def press_cancel(stage, text, done, total):
        if text.startswith("Joints") and done >= 50:
            with open(demo.cancel_path(folder, VERSION), "w", encoding="utf-8") as fh:
                fh.write("cancel\n")
    with pytest.raises(demo.Cancelled):
        demo.build_project(folder, VERSION, small=True, progress=press_cancel)
    assert not os.path.exists(demo.project_dir(folder, VERSION))
    assert not demo.exists(folder, VERSION)
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


def test_a_failure_leaves_nothing(made, tmp_path, monkeypatch):
    folder = str(tmp_path / "fails")

    def broken(d):
        os.makedirs(d.model_dir, exist_ok=True)
        raise RuntimeError("the demo model could not be written: no OpenCascade")
    monkeypatch.setattr(demo, "_run_maker", broken)
    with pytest.raises(RuntimeError, match="could not be written"):
        demo.build_project(folder, VERSION, small=True)
    assert not os.path.exists(demo.project_dir(folder, VERSION))
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


def test_stages_can_be_added_and_replaced():
    ids = [s.id for s in demo.STAGES]
    assert ids[:4] == ["model", "looks", "hold", "joints"] and ids[-1] == "finish"      # hold: task 0082
    assert [i for i in ids if i.startswith("shot_")] == ["shot_fly", "shot_deck", "shot_carousel", "shot_rollers",
                                                       "shot_tensioner", "shot_drum", "shot_sea", "shot_quadrant", "shot_lower",
                                                       "shot_tip", "shot_back"]
    saved = list(demo.STAGES)
    try:
        @demo.stage("cable", "Cable on its path", after="joints")
        def cable(d):
            pass

        @demo.stage("shot_rollers", "Shot 4 again")
        def rollers(d):
            pass
        ids = [s.id for s in demo.STAGES]
        assert ids[ids.index("joints") + 1] == "cable"
        assert ids.count("shot_rollers") == 1 and demo.STAGES[ids.index("shot_rollers")].fn is rollers
    finally:
        demo.STAGES[:] = saved


def test_the_maker_ships_with_the_extension():
    pkg = os.path.join(ROOT, "fresing_render", "demo_model")
    assert os.path.isfile(os.path.join(pkg, "make.py")) and os.path.isfile(os.path.join(pkg, "layout.py"))
    assert not os.path.exists(os.path.join(ROOT, "tools", "demo_cable_lay"))
    import subprocess
    r = subprocess.run([sys.executable, "-I", os.path.join(pkg, "make.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "--only" in r.stdout, r.stderr


def test_help_menu_buttons_have_tooltips(made):
    from fresing_render.blender import ops_demo
    for op in (bpy.ops.fresing.demo_make, bpy.ops.fresing.demo_cancel, bpy.ops.fresing.demo_open):
        desc = op.get_rna_type().description
        assert len(desc) > 40 and "\n" not in desc
    assert not ops_demo.running() and ops_demo.progress_text() == ""
    assert bpy.ops.fresing.demo_cancel.poll() is False                 # nothing to cancel
    assert ops_demo.kill_tree(0) is None                                # no program: nothing happens


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
    assert 20000.0 < car.wound < 40000.0                            # 15 full layers of 24 m and the top one
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
