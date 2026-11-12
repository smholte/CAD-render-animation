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
    assert len(sheet) == 307
    by = {j.name: j for j in sc.fresing.joints}
    assert len(by) == len(sheet) + 1 and demo.CABLE in by          # + Cable travel (no quay in the small form)
    cable_turned = 0
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
        if drive.get("by") == "follows":
            assert j.follows == drive["follows"] and math.isclose(j.couple_ratio, drive["ratio"], rel_tol=1e-5)
        elif demo.waits_for_tracks(row["name"]):
            assert not j.follows, row["name"]                      # until task 0079 runs the tracks
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
    assert cable_turned >= 230                          # 244 + the carousel, less the 8 track sprockets


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
    from fresing_render.blender import cylinders, joints
    sc = _scene()
    s = sc.fresing
    assert len(s.cylinders) == 2
    tilt = s.joints["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]
    c = s.cylinders[0]
    length0 = cylinders.length_now(c)
    joints.set_value(tilt, math.radians(60))
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    assert abs(cylinders.length_now(c) - length0) > 0.2          # the rod slides as the handler tilts
    joints.set_value(tilt, 0.0)
    bpy.context.view_layer.update()


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
    assert 60.0 <= body + cards <= 80.0, body + cards
    kinds = {(b.kind, b.camera_mode if b.kind == "CAMERA" else "") for b in a.blocks}
    assert {("CAMERA", "PATH"), ("CAMERA", "ORBIT"), ("CAMERA", "RIDE"), ("JOINT", ""), ("FADE_OUT", ""),
            ("FADE_IN", "")} <= kinds
    assert any("x 10" in b.name for b in a.blocks) and a.fin_captions        # the time-lapse factor in a caption
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


def test_no_clash_in_the_animation(made, monkeypatch):
    """The clash check over the whole animation: 0 rows (a clash is a fault in the model or the set-up). Left out:
    the parts that only turn about their own round axis (rollers, wheels, drums, the carousel with its coil) and the
    static cable – they sweep only their own room; checked frame by frame, they made the check take hours on this
    model (task 0077, an open point for the clash lane). That they really turn about their own axis is checked
    here too."""
    from mathutils import Vector

    from fresing_render.blender import animation, build, clash, joints
    from fresing_render.core import clash as core
    sc = _scene()
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    leave = demo.turning_in_place(sc)
    assert 250 < len(leave) < 600
    for j in sc.fresing.joints:                                    # round about their own axis
        top = joints.driver_of(sc, j)
        if j.kind != "ROTATE" or top is None or top.name != demo.CABLE:
            continue
        o, dvec = joints.axis_world(j)
        for m in joints.members(j):
            if m.get(build.PROP_KIND) != "part":
                continue
            c = sum((m.matrix_world @ Vector(v) for v in m.bound_box), Vector()) / 8.0
            off = c - o
            off -= dvec * off.dot(dvec)
            assert off.length < 0.01, (j.name, off.length)
    monkeypatch.setattr(clash, "HOOKS", clash.HOOKS + [lambda scene: ((), leave)])
    run = clash.check(sc, store=False)
    assert run.stats["parts"] > 700
    assert not run.rows, [core.row_text(r) for r in run.rows[:5]]


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
                                                       "shot_tensioner", "shot_drum", "shot_quadrant"]
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
