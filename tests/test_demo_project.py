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

    from fresing_render.blender import build, joints
    sc = _scene()
    sc.frame_set(1)
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_cable_lay.step"))
    M = root.matrix_world.copy()
    sheet = made["sheet"]["joints"]
    assert len(sheet) == 310                           # task 0102: no S-bend cradles; the cradles that drop
    by = {j.name: j for j in sc.fresing.joints}
    # + Cable travel and handling winch 1's wire speed (task 0080; no quay in the small form)
    assert len(by) == len(sheet) + 2 and demo.CABLE in by and demo.WINCH_TRAVEL in by
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
            assert j.couple_table in (f"spool:{demo.SPOOL_ITEM}", f"spool:{demo.WINCH_SPOOL}"), row["name"]
            spooled += 1
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
    assert spooled == 5                                 # carousel, arch, guide cage; handling winch 1's drum (0080) + level wind (0081)


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
    assert 60.0 <= body + cards <= 95.0, body + cards          # (0081: shot 8, 10 s more)
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


def test_shot_7_moves_the_whole_quadrant_system(made):
    """Tasks 0091, 0095: shot 7 drops the S-bend's cradles in the D's lane, runs the D-quadrant's whole travel onto the
    handler, tilts the handler its whole range carrying the D (the travel rides on the tilt), and ends there: the D
    vertical, curve up, hanging from the A&R wire over the top pulley – not tipped (task 0082 tips it near the sea
    bottom). The A&R drum pays out with the travel (a coupling) and over the tilt (a step). The clash check over the
    whole animation (above) covers this shot too."""
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
    blocks = {b.joint: b for b in a.blocks if b.kind == "JOINT"}
    travel = made["sheet"]["joints"]
    t_max = next(j for j in travel if j["name"] == demo.TRAVEL)["limits"][1] / 1000.0
    assert blocks[demo.TRAVEL].to_dist == pytest.approx(t_max)
    assert any("x 60" in b.name for b in a.blocks)
    assert demo.TIP not in blocks                                  # not tipped any more

    def part(name):
        return next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == name)
    hf, qf = part("HANDLER FRAME"), part("QUADRANT FRAME")
    fps = int(a.fps)

    def at(seconds):
        sc.frame_set(int(round(seconds * fps)) + 1)
        return hf.matrix_world.inverted() @ qf.matrix_world
    tilt, drum = blocks[demo.TILT], blocks[demo.DRUM_TILT]
    on_handler = at(tilt.start)
    assert math.degrees(joints.get_value(s.joints[demo.TILT])) == pytest.approx(0.0, abs=1e-3)
    assert joints.get_value(s.joints[demo.TRAVEL]) == pytest.approx(t_max, abs=1e-4)
    for lead, drop in leads:
        assert joints.get_value(s.joints[lead]) == pytest.approx(drop, abs=1e-4)
        assert all(joints.get_value(j) == pytest.approx(drop, abs=1e-4) for j in followers[lead])
        assert blocks[lead].start + blocks[lead].duration <= blocks[demo.TRAVEL].start + 1e-6
    # both tensioners open – lifted, tilted out to their own side – before the D travels, and stay open
    for name in demo.TENSIONERS:
        for jn, want in ((f"{name}: Top track lift", None), (f"{name}: Top track tilt", 70.0)):
            b = [x for x in a.blocks if x.kind == "JOINT" and x.joint == jn and x.start >= blocks[demo.TRAVEL].start - 6.0]
            assert b and b[-1].start + b[-1].duration <= blocks[demo.TRAVEL].start + 1e-6, jn
        assert math.degrees(joints.get_value(s.joints[f"{name}: Top track tilt"])) == pytest.approx(70.0, abs=1e-3)
        assert joints.get_value(s.joints[f"{name}: Top track lift"]) > 0.85
    last = max(b.start + b.duration for b in a.blocks)
    assert last >= tilt.start + tilt.duration + 2.0                 # a hold on the end picture
    tilted = at(last)
    assert math.degrees(joints.get_value(s.joints[demo.TILT])) == pytest.approx(100.0, abs=1e-3)
    assert math.degrees(joints.get_value(s.joints[demo.TIP])) == pytest.approx(0.0, abs=1e-6)
    assert np.allclose(np.array(tilted), np.array(on_handler), atol=1e-4)      # the D tilts with the handler
    # vertical, curve up: the D's curve points along its local +x (model mm); in the vessel's frame that is up
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_cable_lay.step"))
    up = root.matrix_world.to_3x3().inverted() @ (qf.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0)))
    assert up.normalized().z > 0.98
    # the drum's step lies inside the tilt and ends with it; its turn is the payout over the tilt
    assert tilt.start < drum.start and drum.start + drum.duration == pytest.approx(tilt.start + tilt.duration)
    row = next(j for j in made["sheet"]["joints"] if j["name"] == demo.DRUM_TILT)
    assert math.degrees(drum.to_angle) == pytest.approx(row["drive"]["payout_mm"] * row["drive"]["deg_per_mm"], rel=1e-5)
    # the D sits on the handler's rails: its bar where the sheet's travel puts it (handler mm: hinge at 0)
    assert on_handler.translation.z * 1000 == pytest.approx(400.0, abs=0.5)
    sc.frame_set(1)


def _ends(ob):
    """Start and end (world) of a straight wire piece (a 1 m cylinder along y, stretched) and its thickness scale."""
    from mathutils import Vector
    M = ob.matrix_world
    return M @ Vector((0, 0, 0)), M @ Vector((0, 1, 0)), M.to_3x3().col[0].length


def test_wires_follow_their_ends(made):
    """Task 0095: the A&R wire is on the D's eye at the top of its curve at the start, at the end of the travel and all
    through the tilt (over the top pulley from ~10°), its other end on the drum; the tipping wires hang parked until the
    D is on the handler and then end on the bar's ends. Checked against the eyes' places worked out from the D's own
    part (not the wires' empties), within 3 mm, also after a Build at another frame rate; every driver of the wires is
    a simple expression (scripts off); a wire's straight piece never runs through steel."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from fresing_render.blender import animation, build, joints
    sc = _scene()
    s = sc.fresing
    a = s.animations[demo.ANIM]
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    W = d.sheet("route")["wires"]
    animation.clear_keys(sc)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    eye_car = d.uid(W["ar"]["eye_carrier"])
    eye_l = eye_car.matrix_world.inverted() @ d.mm(W["ar"]["eye"])
    drum_car = d.uid(W["ar"]["drum_carrier"])
    drum_l = drum_car.matrix_world.inverted() @ d.mm(W["ar"]["drum_centre"])
    tips = {}
    for k in ("port", "stb"):
        c = d.uid(W[f"tipping_{k}"]["eye_carrier"])
        h = d.uid(W[f"tipping_{k}"]["head_carrier"])
        tips[k] = (c, c.matrix_world.inverted() @ d.mm(W[f"tipping_{k}"]["eye"]),
                   h, h.matrix_world.inverted() @ d.mm(W[f"tipping_{k}"]["park"]))
    O = {o.name: o for o in sc.objects if o.get(demo.WIRE_TAG)}
    assert len(O) >= 20 and all(o.users_collection[0].name == demo.WIRES for o in O.values())
    assert not any(o.get(build.PROP_KIND) for o in O.values())               # no part: the clash check leaves them
    for o in O.values():                                                     # scripts off
        for ad in (o.animation_data, getattr(o.data, "animation_data", None)):
            for fc in (ad.drivers if ad else []):
                assert fc.driver.is_simple_expression, (o.name, fc.driver.expression)
    deck, w2 = O["A&R wire (deck)"], O["A&R wire (pulley to eye)"]
    steel = [o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) not in ("WIRE ROPE", "CABLE")]
    near = []

    def through_steel(ob, r):
        p0, p1, sx = _ends(ob)
        L = (p1 - p0).length
        pts = [p0 + (p1 - p0) * (i / 200) for i in range(201) if 0.3 < L * i / 200 < L - 0.3]
        lo = Vector([min(q[i] for q in pts) for i in range(3)]) - Vector((0.1,) * 3)
        hi = Vector([max(q[i] for q in pts) for i in range(3)]) + Vector((0.1,) * 3)
        dg = bpy.context.evaluated_depsgraph_get()
        for o in steel:
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            if any(max(c[i] for c in bb) < lo[i] or min(c[i] for c in bb) > hi[i] for i in range(3)):
                continue
            tree, Mi = BVHTree.FromObject(o, dg), o.matrix_world.inverted()
            for q in pts:
                hit = tree.find_nearest(Mi @ q)
                if hit[0] is not None and (o.matrix_world @ hit[0] - q).length < r - 0.002:
                    near.append((ob.name, o.get(build.PROP_NAME), sc.frame_current))
                    break

    def check(fps_note):
        tmax = s.joints[demo.TRAVEL].slide_max
        conn = joints.get_value(s.joints[demo.TRAVEL]) > tmax - 0.001
        E = eye_car.matrix_world @ eye_l
        s0, s1, _ = _ends(deck)
        a0, a1, ax = _ends(w2)
        assert ((a1 if ax > 0.5 else s1) - E).length < 0.003, (fps_note, sc.frame_current)
        if ax > 0.5:                                                    # over the pulley: the deck piece ends on it
            assert math.degrees(joints.get_value(s.joints[demo.TILT])) > 5.0
        assert abs((s0 - drum_car.matrix_world @ drum_l).length - W["ar"]["drum_r"] / 1000.0) < 0.003
        through_steel(deck, W["ar"]["rope_d"] / 2000.0)
        if ax > 0.5:
            through_steel(w2, W["ar"]["rope_d"] / 2000.0)
        for k, (c, el, h, pl) in tips.items():
            t0, t1, _ = _ends(O[f"Tipping wire {k}"])
            want = c.matrix_world @ el if conn else h.matrix_world @ pl
            assert (t1 - want).length < 0.003, (fps_note, k, sc.frame_current, conn)
            through_steel(O[f"Tipping wire {k}"], W[f"tipping_{k}"]["rope_d"] / 2000.0)
    try:
        for fps in ("25", "50"):
            a.fps = fps
            animation.bake(sc, a)
            f = int(a.fps)
            blocks = {b.joint: b for b in a.blocks if b.kind == "JOINT"}
            tr, ti = blocks[demo.TRAVEL], blocks[demo.TILT]
            seen_contact = False
            for sec in [tr.start, tr.start + tr.duration * 0.5, ti.start] + \
                    [ti.start + ti.duration * q for q in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0)]:
                sc.frame_set(int(round(sec * f)) + 1)
                check(fps)
                seen_contact = seen_contact or _ends(w2)[2] > 0.5
            assert seen_contact
    finally:
        a.fps = "25"
        animation.bake(sc, a)
    assert not near, near[:5]
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
    assert ids[:3] == ["model", "looks", "joints"] and ids[-1] == "finish"
    assert [i for i in ids if i.startswith("shot_")] == ["shot_fly", "shot_deck", "shot_carousel", "shot_rollers",
                                                       "shot_tensioner", "shot_drum", "shot_quadrant", "shot_sea"]
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
