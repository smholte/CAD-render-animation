"""Task 0077: the demo project "Cable-lay vessel" (Help > Make demo project, ``fresing_render/blender/demo.py``).

Blender as a Python module. The project is made once in its scaled-down form (the PC check's on GitHub: Draft meshes,
no quay model; the same joints, cylinders, cameras and animation), then checked: every joint of the sheet with its
type, limits, stack and coupling; a coupling's ratio; drivers that work with scripts off; the animation; save,
reopen and Build again; Cancel; the stage list later tasks extend.

Task 0145 split the shots' checks into ``test_demo_project_cable.py`` (shots 3–5), ``_cps.py`` (shots 8b, 9),
``_quadrant.py`` (shots 10–12) and ``_lowering.py`` (the D's way, clash-checked). The demo project is made once per run and shared by these files (``tests/demo_made.py``, task 0145: the single file
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
    assert len(sheet) == 317                           # task 0102: no S-bend cradles; the cradles that drop; task 0126:
    #                                                    none under the CPS slide's last bend onto side B; task 0153: the
    #                                                    vessel's 4 propellers, 2 steers, 2 radars, the crane's slew + luff
    by = {j.name: j for j in sc.fresing.joints}
    # + Cable travel and handling winch 1's wire speed (task 0080; no quay in the small form)
    # task 0082: the speed joints of the A&R wire, the two tipping wires and the second end; task 0126: the CPS run's
    wires = [paths.find(sc, n).joint for n in (demo.AR_ITEM, demo.SECOND_ITEM, demo.CPS_RUN_ITEM)
             + tuple(n for _k, n in demo.TIP_ITEMS)]
    assert len(by) == len(sheet) + 2 + 5 and demo.CABLE in by and demo.WINCH_TRAVEL in by and all(w in by for w in wires)
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
        elif "Swivel sheave" in row["name"] and row["name"].endswith(" swivel"):
            assert not j.follows, row["name"]                       # turned to its wire (Swivel, task 0125)
        elif j.follows == demo.WINCH_TRAVEL:                        # turned by handling winch 1's wire
            assert "Fairlead" in row["name"], row["name"]
        elif drive.get("by") == "follows":
            assert j.follows == drive["follows"] and math.isclose(j.couple_ratio, drive["ratio"], rel_tol=1e-5)
        elif drive.get("by") in ("cable", "carousel"):
            assert j.follows == demo.CABLE and math.isclose(j.couple_ratio, drive["deg_per_mm"], rel_tol=1e-5)
            cable_turned += 1
        else:
            assert not j.follows, row["name"]
        # the axis where the sheet puts it (model mm, in the model's frame: the vessel moves with the sea) – but a
        # swivel head's sheave turns about the post to its wire from the first frame on (task 0125)
        if "Swivel sheave" in row["name"] and row["name"].endswith(" turn") and "foot" not in row["name"]:
            continue
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
    assert 60.0 <= body + cards <= 210.0, body + cards         # (0081: shot 8, 10 s more; 0082: shots 9–12, ~55 s;
    #                                                            0126: shot 8b, ~24 s; 0166: the park's 2b, 8a, 13, 26 s)
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
    from fresing_render.blender import animation, paths_sea
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    out = animation.bake(sc, a)
    first = _keys(sc)
    marks = {it.name: float(it.sea_mark) for it in paths_sea.sea_cables(sc)}
    assert len(first) > 15                  # the moved joints, the camera, the fades (followers are drivers)
    path = str(tmp_path / "again.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = _scene()
    sc.frame_set(sc.frame_end)              # task 0138: Build with the last frame shown gives the same (was +114 m)
    again_out = animation.bake(sc, sc.fresing.animations[demo.ANIM])
    again = _keys(sc)
    assert {it.name: float(it.sea_mark) for it in paths_sea.sea_cables(sc)} == pytest.approx(marks, abs=1e-6)
    assert again_out["warnings"] == out["warnings"]
    assert set(again) == set(first)
    for k, v in first.items():
        assert v.shape == again[k].shape and np.allclose(v, again[k], atol=1e-5), k
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


# test_no_clash_in_the_animation: in tests/test_demo_clash.py since task 0108 (four processes at once)


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
    assert ids[:5] == ["model", "looks", "hold", "marks", "joints"] and ids[-1] == "finish"   # hold: 0082, marks: 0153
    assert ids[-3:-1] == ["propulsion", "park_rotors"]   # tasks 0153, 0166: propellers and rotors turn all the time
    assert [i for i in ids if i.startswith("shot_")] == ["shot_fly", "shot_deck", "shot_turbine_a", "shot_carousel",
                                                       "shot_rollers", "shot_tensioner", "shot_drum", "shot_sea",
                                                       "shot_park", "shot_cps", "shot_quadrant", "shot_lower",
                                                       "shot_tip", "shot_back", "shot_night"]
    assert ids.index("park") == ids.index("sea") + 1 and ids.index("park_shift") == ids.index("shot_quadrant") - 1
    saved = list(demo.STAGES)
    before = [s.id for s in demo.STAGES]
    try:
        @demo.stage("cable", "Cable on its path", after="joints")
        def cable(d):
            pass

        @demo.stage("shot_rollers", "Shot 4 again")
        def rollers(d):
            pass
        ids = [s.id for s in demo.STAGES]
        assert ids == before                                     # replaced in its place
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


def test_the_vessel_in_detail(made):
    """Task 0153: the vessel's looks (antifouling with growth, boot top, glass …), its name and draft marks as decals,
    the two new cameras, and the propellers and radars turning (motors) through the whole animation."""
    from fresing_render.blender import build, decals, joints, marine_looks
    sc = _scene()
    by_name = {}
    for o in build.iter_parts(sc):
        by_name.setdefault(o.get(build.PROP_NAME), []).append(o)
    groups = {g.name: g for g in sc.fresing.groups}
    for name, group, material in (("HULL BOTTOM", "Demo: antifouling", "paint_marine_growth"),
                                  ("BOOT TOP", "Demo: boot top", "paint_marine_growth"),
                                  ("HULL", "Demo: hull", "paint_marine_streaks"),
                                  ("PROPELLER", "Demo: propellers", "bronze"),
                                  ("WINDOW", "Demo: glass", "glass_tinted"),
                                  ("MAIN DECK", "Demo: non-slip deck", "powder_coat")):
        assert groups[group].material == material, group
        for o in by_name[name]:
            assert o.get("fr_group_manual") == group, (name, o.name)
    assert marine_looks.nodes_of(by_name["HULL BOTTOM"][0].active_material)       # the growth's nodes are there
    assert groups["Demo: deck fittings"].wear > 0.5
    # the name on both bows, three draft marks on each of the four boards
    texts = {}
    for o in by_name["NAME BOARD"] + by_name["DRAFT MARK BOARD"]:
        texts[o.name] = sorted(it.text for it in decals.items_of(o))
    assert sorted(t for t in texts.values() if t == [demo.VESSEL_NAME]) == [[demo.VESSEL_NAME]] * 2
    assert sum(1 for t in texts.values() if t == ["5M", "6M", "7M"]) == 4
    # the new cameras: one under water at the stern, one along the side
    wl = marine_looks.waterline(sc)
    cam = sc.objects[demo.STERN_THRUSTERS]
    assert cam.type == "CAMERA" and cam.matrix_world.translation.z < wl - 3.0
    assert sc.objects[demo.HULL_SIDE].type == "CAMERA"
    # propellers and radars: motors, turning at their speed the whole animation
    a = sc.fresing.animations[demo.ANIM]
    end = max(b.start + b.duration for b in a.blocks)
    names = [n for n, _rpm in demo.turning_joints(demo.Demo(sc, made["folder"], VERSION, small=True))]
    assert len(names) == 6
    t0, t1 = 20.0, 26.0
    f0, f1 = animation_frame(a, t0), animation_frame(a, t1)
    for n in names:
        j = joints.find(sc, n)
        assert joints.is_motor(j), n
        blk = [b for b in a.blocks if b.kind == "MOTOR" and b.joint == n]
        assert len(blk) == 1 and blk[0].start == 0.0 and blk[0].start + blk[0].duration == pytest.approx(end, abs=0.6)
        sc.frame_set(f0)
        v0 = joints.get_value(j)
        sc.frame_set(f1)
        v1 = joints.get_value(j)
        fps = sc.render.fps / sc.render.fps_base
        want = 2 * math.pi * blk[0].speed_rpm / 60.0 * (f1 - f0) / fps
        assert v1 - v0 == pytest.approx(want, rel=0.02), n
