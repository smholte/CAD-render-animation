"""Task 0077 / 0247: the demo project "Vessel in a wind park" (Help > Make demo project, ``fresing_render/blender/demo.py``).

Blender as a Python module. The project is made once in its scaled-down form (the PC check's on GitHub: Draft meshes,
no quay model; the same joints, cameras and animation; ``tests/demo_made.py``), then checked: every joint of the sheet
with its type, limits and stack; the deck crane's slew and hoist; drivers that work with scripts off; the animation;
save, reopen and Build again; Cancel; a failure; the stage list later tasks extend; the clash check with the park left
out by its stored tag; and **no name of the cable-lay vessel's equipment** anywhere in the public demo (task 0247: the
equipment is private – a demo kit of the owner's).
"""

import math
import os
import re
import shutil
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)                          # (demo_made: the made demo project, task 0145)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import VERSION, _keys, _scene, animation_frame, made  # noqa: E402,F401
from fresing_render.blender import demo  # noqa: E402

# Words of the cable-lay vessel's equipment (task 0247): none may name a file, a part or an object of the public demo.
# The app's generic functions (spools, Lebus drums, tracks, the test models' tensioner) are not the demo.
EQUIPMENT = re.compile(r"\b(CAROUSEL|TENSIONERS?|CHUTES?|QUADRANT|D-QUADRANT|A-?FRAME|LARS|ROV|CPS|CRADLES?|TRESTLES?|"
                       r"LOADING TOWER|HORN [AB]|ROLLER HIGHWAY|CABLE ENGINE|HANDLING WINCH|TIPPING|A&R|LEBUS|"
                       r"QUAY LOADING|STORAGE CAROUSEL|RADIUS CONTROLLER|SPREAD|ARCH)\b", re.I)


def test_the_project_is_made_and_saved(made):
    folder, out = made["folder"], made["out"]
    assert out["path"] == demo.project_path(folder, VERSION) and os.path.isfile(out["path"])
    assert os.path.basename(out["path"]) == f"Vessel in a wind park {VERSION}.blend"
    assert demo.exists(folder, VERSION)
    assert not os.path.exists(demo.progress_path(folder, VERSION))        # only while it is made
    sc = _scene()
    assert sc.get(demo.TAG) == VERSION and demo.is_demo(sc)
    info = demo.read_summary(folder, VERSION)
    assert info["joints"] == len(sc.fresing.joints) >= demo.MIN_JOINTS and info["animation"] == demo.ANIM
    assert info["cylinders"] == 0
    # the status line went through the stages with counts
    texts = [t for _s, t in made["seen"]]
    assert any(t.startswith("Writing the model") for t in texts)
    assert "Importing" in texts and any(t.startswith("Joints ") for t in texts) and "Animation" in texts


def test_no_equipment_in_the_public_demo(made):
    """Task 0247: the files the maker wrote, the parts in them (STEP product names), the project's objects, groups,
    joints, cables, spools, saved scenes and the animation's steps hold no word of the vessel's equipment."""
    from fresing_render.blender import build, paths, spool
    files = sorted(os.listdir(made["models"]))
    assert files == ["demo_joints.json", "demo_park.step", "demo_route.json", "demo_vessel.step"], files
    names = list(files)
    for f in files:
        if f.endswith(".step"):
            with open(os.path.join(made["models"], f), encoding="utf-8", errors="replace") as fh:
                names += re.findall(r"PRODUCT\('([^']*)'", fh.read())
    assert len(names) > 100
    sc = _scene()
    s = sc.fresing
    names += [o.name for o in sc.objects] + [o.get(build.PROP_NAME, "") for o in sc.objects]
    names += [g.name for g in s.groups] + [j.name for j in s.joints] + [sh.name for sh in s.shots]
    names += [it.name for it in paths.items(sc)] + [sp.name for sp in spool.items(sc)]
    names += [b.name for a in s.animations for b in a.blocks] + [a.name for a in s.animations]
    bad = sorted({n for n in names if EQUIPMENT.search(n)})
    assert not bad, bad[:20]
    # the plain deck: no well, no opening; the ship's own crane is there
    parts = {o.get(build.PROP_NAME) for o in build.iter_parts(sc)}
    assert {"DECK CRANE", "CRANE BOOM", "HOOK BLOCK", "HOIST WIRE", "MAIN DECK", "BULWARK"} - parts <= {"DECK CRANE"}
    assert "CAROUSEL WELL" not in parts


def test_every_joint_of_the_sheet(made):
    from mathutils import Vector

    from fresing_render.blender import build, joints
    sc = _scene()
    sc.frame_set(1)
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_vessel.step"))
    M = root.matrix_world.copy()
    sheet = made["sheet"]["joints"]
    # the ship: 2 steers + 4 propellers, 2 radars, the crane's slew, luff, hoist drum, head sheave and hook
    assert len(sheet) == 13
    by = {j.name: j for j in sc.fresing.joints}
    park = made["sheet"]["machine_files"]["demo_park.step"]           # task 0166: the wind park's 19 joints
    assert len(park) == 19 and all(j["name"] in by for j in park)
    assert demo.CRANE_TRAVEL in by and len(by) == len(sheet) + 1 + len(park) == demo.MIN_JOINTS
    for row in sheet:
        j = by.get(row["name"])
        assert j is not None, row["name"]
        assert j.kind == ("ROTATE" if row["type"] == "rotate" else "SLIDE"), row["name"]
        moved = {o.get(build.PROP_UID) for o in joints.moved_objects(sc, j)}
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
        if j.couple_table:                                          # the hoist drum follows its spool by table
            assert j.couple_table == f"spool:{demo.CRANE_SPOOL}", row["name"]
        elif row["name"] == demo.HOOK:                              # the hook on the hoist wire, one to one
            assert j.follows == demo.CRANE_TRAVEL and math.isclose(j.couple_ratio, 1.0, rel_tol=1e-6)
        elif j.follows == demo.CRANE_TRAVEL:                        # the head sheave, turned by the wire (task 0174)
            assert row["name"].endswith("Head sheave turn"), row["name"]
        else:
            assert not j.follows, row["name"]
        o, d = joints.axis_world(j)
        p = np.array(M @ Vector(np.array(row["axis"]["point"]) / 1000.0))
        dv = np.array((M.to_3x3() @ Vector(row["axis"]["direction"])).normalized())
        assert np.linalg.norm(np.cross(np.array(o) - p, dv)) < 1e-4, row["name"]
        assert abs(abs(float(np.dot(np.array(d), dv))) - 1.0) < 1e-6, row["name"]


def test_the_crane_slews_and_lowers_its_hook(made):
    """Shot 3: the boom swings 90° outboard to port, then 20 m of wire comes off the drum and the hook goes down
    plumb beside the ship, clear of the hull; the drum turned by the spool's table."""
    from fresing_render.blender import build, joints, paths
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    slew = next(b for b in a.blocks if b.kind == "JOINT" and b.joint == demo.SLEW)
    hoist = next(b for b in a.blocks if b.kind == "JOINT" and b.joint == demo.CRANE_TRAVEL)
    assert hoist.start == pytest.approx(slew.start + slew.duration)
    hook = next(o for o in build.iter_parts(sc) if o.get(build.PROP_NAME) == "HOOK BLOCK")
    drum = joints.find(sc, next(j.name for j in sc.fresing.joints if j.name.endswith("Hoist drum turn")))
    root = next(r for r in build.model_roots(sc) if r.get(build.PROP_SOURCE, "").endswith("demo_vessel.step"))
    sc.frame_set(animation_frame(a, slew.start - 0.1))
    z0, d0 = hook.matrix_world.translation.z, joints.get_value(drum)
    sc.frame_set(animation_frame(a, hoist.start + hoist.duration + 0.2))
    bpy.context.view_layer.update()
    assert joints.get_value(joints.find(sc, demo.SLEW)) == pytest.approx(math.radians(demo.CRANE_SLEW), abs=1e-3)
    assert joints.get_value(joints.find(sc, demo.HOOK)) == pytest.approx(demo.CRANE_DROP, abs=1e-3)
    local = root.matrix_world.inverted() @ hook.matrix_world.translation
    beam = made["route"]["vessel"]["beam"] / 2000.0
    assert local.y > beam + 1.0                                         # outboard of the port side
    assert z0 - hook.matrix_world.translation.z == pytest.approx(demo.CRANE_DROP, abs=0.3)     # (vessel motion)
    assert abs(math.degrees(joints.get_value(drum) - d0)) > 360.0       # the drum paid the wire out
    it = paths.find(sc, demo.CRANE_WIRE)
    assert it is not None and it.joint == demo.CRANE_TRAVEL and not it.problem


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
    assert n >= 30


def test_scenes_cameras_brand_and_the_animation(made):
    sc = _scene()
    s = sc.fresing
    assert s.shots.get(demo.SEA_SHOT) is not None
    for name in demo.VIEWS:
        assert s.shots.get(name) is not None and sc.objects.get(name) is not None, name
    from fresing_render.blender import demo_park
    for name in (demo_park.BESIDE_A, demo_park.PARK_OVERVIEW, demo_park.PARK_NIGHT):
        assert sc.objects.get(name) is not None, name
    assert s.brand_name == "Demo" and os.path.isfile(bpy.path.abspath(s.brand_logo))
    a = s.animations[demo.ANIM]
    body = max(b.start + b.duration for b in a.blocks)
    cards = (a.fin_title_seconds if a.fin_title_on else 0) + (a.fin_end_seconds if a.fin_end_on else 0)
    assert 50.0 <= body <= 75.0 and 55.0 <= body + cards <= 80.0, (body, cards)       # "about a minute"
    kinds = {(b.kind, b.camera_mode if b.kind == "CAMERA" else "") for b in a.blocks}
    assert {("CAMERA", "PATH"), ("CAMERA", "ORBIT"), ("CAMERA", "RIDE"), ("CAMERA", "CUT"), ("JOINT", ""),
            ("MOTOR", ""), ("VESSEL", ""), ("WEATHER", "")} <= kinds
    assert a.fin_captions and a.fin_title == demo.TITLE
    assert s.background == "SEA" and s.sea_depth == pytest.approx(demo.SEA_DEPTH)
    assert s.sea_cutaway and not s.sea_cut_auto and s.sea_cut_length == pytest.approx(demo.CUT_LENGTH)


def test_save_reopen_and_build_again_gives_the_same_keys(made, tmp_path):
    from fresing_render.blender import animation, paths
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    out = animation.bake(sc, a)
    first = _keys(sc)
    wire = np.array(paths._arrays(sc, paths.find(sc, demo.CRANE_WIRE))[0], dtype=float)
    assert len(first) > 15 and len(wire) > 1    # the moved joints, the camera, the fades (followers are drivers)
    path = str(tmp_path / "again.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = _scene()
    sc.frame_set(sc.frame_end)              # task 0138: Build with the last frame shown gives the same
    again_out = animation.bake(sc, sc.fresing.animations[demo.ANIM])
    again = _keys(sc)
    assert again_out["warnings"] == out["warnings"]
    w2 = np.array(paths._arrays(sc, paths.find(sc, demo.CRANE_WIRE))[0], dtype=float)
    assert w2.shape == wire.shape and float(np.abs(w2 - wire).max()) < 1e-5
    assert set(again) == set(first)
    for k, v in first.items():
        assert v.shape == again[k].shape and np.allclose(v, again[k], atol=1e-5), k
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


def test_no_clash_and_the_park_left_out_by_its_tag(made, tmp_path):
    """The clash check over the whole animation: 0 rows (the crane's boom, hook and wire, the turning propellers and
    radars). The park is left out by the tag stored on its model root (``clash.NO_CLASH``, task 0247) – also after the
    project is saved and opened again, with no code of the demo's registered as a hook."""
    from fresing_render.blender import build, clash, demo_park
    sc = _scene()
    path = str(tmp_path / "tagged.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = _scene()
    r = demo_park.park_root(sc)
    assert r is not None and r.get(clash.NO_CLASH) and not any("demo" in getattr(f, "__module__", "")
                                                               for f in clash.HOOKS)
    objs = clash.objects(sc)
    park = [o for o in build.iter_parts(sc) if clash.left_out(o)]
    assert len(park) > 500 and not set(o.name for o in objs) & set(o.name for o in park)
    assert any(o.get(build.PROP_NAME) == "HOOK BLOCK" for o in objs)
    res = clash.check(sc, store=False)
    rows = [r_ for r_ in res.rows if r_.kind == "CLASH"]
    assert not rows, [(r_.a, r_.b, r_.frame_from, round(r_.depth * 1000, 1)) for r_ in rows[:5]]
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


def test_cancel_leaves_nothing(made, tmp_path, monkeypatch):
    folder = str(tmp_path / "cancel")

    def copy_model(d):
        os.makedirs(d.model_dir, exist_ok=True)
        for f in os.listdir(made["models"]):
            shutil.copy(os.path.join(made["models"], f), d.model_dir)
    monkeypatch.setattr(demo, "_run_maker", copy_model)

    def press_cancel(stage, text, done, total):
        if text.startswith("Joints") and done >= 10:
            with open(demo.cancel_path(folder, VERSION), "w", encoding="utf-8") as fh:
                fh.write("cancel\n")
    with pytest.raises(demo.Cancelled):
        demo.build_project(folder, VERSION, small=True, progress=press_cancel)
    assert not os.path.exists(demo.project_dir(folder, VERSION))
    assert not demo.exists(folder, VERSION)
    bpy.ops.wm.open_mainfile(filepath=made["out"]["path"])


def test_cancel_at_the_import_then_make_it_again(made, tmp_path, monkeypatch):
    """Task 0371: Make it → Cancel while the model is imported → Make it again, twice: each new build is made in the
    same folder, from nothing, and no STEP reader of a cancelled build is left running."""
    folder = str(tmp_path / "again")

    def copy_model(d):
        os.makedirs(d.model_dir, exist_ok=True)
        for f in os.listdir(made["models"]):
            shutil.copy(os.path.join(made["models"], f), d.model_dir)
    monkeypatch.setattr(demo, "_run_maker", copy_model)

    def press_cancel(stage, text, done, total):
        if text == "Importing":
            with open(demo.cancel_path(folder, VERSION), "w", encoding="utf-8") as fh:
                fh.write("cancel\n")

    def readers():
        out = []
        for name in os.listdir("/proc") if os.path.isdir("/proc") else ():
            try:
                with open(f"/proc/{name}/cmdline", "rb") as fh:
                    cmd = fh.read()
                with open(f"/proc/{name}/stat", encoding="ascii", errors="replace") as fh:
                    st = fh.read()
            except OSError:
                continue
            if b"step_reader.py" in cmd and st[st.rfind(")") + 2:].split()[0] not in ("Z", "X") \
                    and folder.encode() in cmd:
                out.append(int(name))
        return out
    for _ in range(2):
        with pytest.raises(demo.Cancelled):
            demo.build_project(folder, VERSION, small=True, progress=press_cancel, only=("model", "looks"))
        assert not os.path.exists(demo.project_dir(folder, VERSION))
        assert readers() == []
        out = demo.build_project(folder, VERSION, small=True, only=("model", "looks"))
        assert os.path.isfile(out["path"]) and demo.exists(folder, VERSION)
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
    assert ids == ["model", "looks", "marks", "joints", "crane", "surroundings", "sea", "park", "cameras",
                   "park_cameras", "brand", "shot_fly", "shot_turbine_a", "shot_crane", "shot_hull", "shot_seabed",
                   "shot_park", "shot_night", "propulsion", "park_rotors", "finish"], ids
    saved = list(demo.STAGES)
    before = [s.id for s in demo.STAGES]
    try:
        @demo.stage("crane", "The crane again", after="joints")
        def crane(d):
            pass

        @demo.stage("shot_hull", "Shot 4 again")
        def hull(d):
            pass
        ids = [s.id for s in demo.STAGES]
        assert ids == before                                     # replaced in its place
        assert ids.count("shot_hull") == 1 and demo.STAGES[ids.index("shot_hull")].fn is hull

        @demo.stage("shot_extra", "A new shot", after="shot_hull")
        def extra(d):
            pass
        ids = [s.id for s in demo.STAGES]
        assert ids[ids.index("shot_hull") + 1] == "shot_extra"
    finally:
        demo.STAGES[:] = saved


def test_the_maker_ships_with_the_extension():
    pkg = os.path.join(ROOT, "fresing_render", "demo_model")
    assert os.path.isfile(os.path.join(pkg, "make.py")) and os.path.isfile(os.path.join(pkg, "layout.py"))
    for gone in ("machines.py", "rov.py"):                              # task 0247: the equipment is private
        assert not os.path.exists(os.path.join(pkg, gone)), gone
    assert not os.path.exists(os.path.join(ROOT, "fresing_render", "blender", "demo_rov.py"))
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
    the cameras, and the propellers and radars turning (motors) through the whole animation."""
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
                                  ("CRANE BOOM", "Demo: yellow structure", "paint_marine"),
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
    # the cameras: one under water at the stern, one along the side, one at the seabed
    wl = marine_looks.waterline(sc)
    cam = sc.objects[demo.STERN_THRUSTERS]
    assert cam.type == "CAMERA" and cam.matrix_world.translation.z < wl - 3.0
    assert sc.objects[demo.AT_THE_SEABED].matrix_world.translation.z < wl - demo.SEA_DEPTH + 10.0
    assert sc.objects[demo.HULL_SIDE].type == "CAMERA"
    # propellers and radars: motors, turning at their speed the whole animation
    a = sc.fresing.animations[demo.ANIM]
    end = max(b.start + b.duration for b in a.blocks)
    names = [n for n, _rpm in demo.turning_joints(demo.Demo(sc, made["folder"], VERSION, small=True))]
    assert len(names) == 6
    # task 0154: the propellers follow Vessel at work (ahead 6 kn, then DP from the crane's shot)
    from fresing_render.blender import vessel_work
    from fresing_render.core import vessel_work as vw_core
    v = sc.fresing.vessel_work
    assert len(v.thrusters) == 4 and sorted(r.kind for r in v.thrusters) == ["AZIMUTH", "AZIMUTH", "TUNNEL", "TUNNEL"]
    steps = [b for b in a.blocks if b.kind == "VESSEL"]
    assert len(steps) == 1 and steps[0].vw_mode == "DP"
    t0 = steps[0].start + steps[0].duration + 0.5
    t1 = t0 + 6.0
    f0, f1 = animation_frame(a, t0), animation_frame(a, t1)
    assert vessel_work.setting(sc).mode == "AHEAD" and vessel_work.setting(sc).speed == demo.TRANSIT_KNOTS
    ths = vessel_work.thrusters(sc)
    cmd = vw_core.command(vessel_work.block_setting(steps[0]), ths)
    fps = sc.render.fps / sc.render.fps_base
    for i, r in enumerate(v.thrusters):
        j = joints.find(sc, r.joint)
        assert joints.is_motor(j) and r.joint in names, r.joint
        sc.frame_set(f0)
        v0 = joints.get_value(j)
        sc.frame_set(f1)
        v1 = joints.get_value(j)
        want = vw_core.rate(ths[i].kind, cmd.loads[i], cmd.jets[i], r.rpm, r.reverse) * (f1 - f0) / fps
        assert abs(want) > 0.5 and v1 - v0 == pytest.approx(want, rel=0.02), r.joint
    for n in names:
        if n.endswith("Propeller turn"):
            continue
        j = joints.find(sc, n)
        assert joints.is_motor(j), n
        blk = [b for b in a.blocks if b.kind == "MOTOR" and b.joint == n]
        assert len(blk) == 1 and blk[0].start == 0.0 and blk[0].start + blk[0].duration == pytest.approx(end, abs=0.6)
        sc.frame_set(f0)
        v0 = joints.get_value(j)
        sc.frame_set(f1)
        v1 = joints.get_value(j)
        want = 2 * math.pi * blk[0].speed_rpm / 60.0 * (f1 - f0) / fps
        assert v1 - v0 == pytest.approx(want, rel=0.02), n
