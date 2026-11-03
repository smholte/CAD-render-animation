"""Phase 2 inside Blender: joints, chains, poses, explode, visibility sets, scenes,
animation, model update (re-import), render queue, project lock, UI."""

import math
import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")
PIVOT = Vector((0.1, 0.3, 0.4))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, logic, project_lock, queue, states  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name, n=0):
    hits = [o for o in sc.objects if o.get(build.PROP_NAME) == name]
    hits.sort(key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def boom_joint(sc):
    pin = ob(sc, "BOOM.PIN")
    hit = PIVOT + Vector((0, 0, 0.02))
    origin, direction, desc = joints.axis_from_hit(pin, 0, hit, Vector((0, 0, 1)))
    assert "Ø40.0" in desc
    return joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], origin, direction, ref=pin)


def update(sc):
    bpy.context.view_layer.update()


def tip(sc):
    return ob(sc, "BOOM").matrix_world @ Vector((1.5, 0, 0))


def close(a, b, tol=1e-4):
    return (Vector(a) - Vector(b)).length < tol


# ---------------------------------------------------------------------------


def test_axes_stored_and_picked(scene):
    pin = ob(scene, "BOOM.PIN")
    assert len(pin.data["fr_axes"]) == 7
    origin, direction, _desc = joints.axis_from_hit(pin, 0, PIVOT + Vector((0.05, 0, 0.02)), Vector((0, 0, 1)))
    assert close(origin, PIVOT + Vector((0, 0, 0))), origin
    assert abs(abs(direction.y) - 1) < 1e-6
    # a flat face gives the face normal through the click
    base = ob(scene, "BASE")
    o2, d2, desc2 = joints.axis_from_hit(base, 0, Vector((0.5, 0.3, 0.1)), Vector((0, 0, 1)))
    assert "flat" in desc2 and close(d2, (0, 0, 1)) and close(o2, (0.5, 0.3, 0.1))


def test_rotate_joint_moves_boom_and_keeps_structure(scene):
    j = boom_joint(scene)
    boom_asm = ob(scene, "BOOM.ASM")
    assert boom_asm.parent is j.motion and build.logical_parent(boom_asm) is build.model_roots(scene)[0]
    assert j.base is build.model_roots(scene)[0]
    start = tip(scene).copy()
    assert close(start, (1.6, 0.3, 0.4))
    sign = 1 if joints.axis_world(j)[1].y > 0 else -1
    joints.set_value(j, math.radians(30))
    update(scene)
    expected = PIVOT + Matrix.Rotation(sign * math.radians(30), 3, "Y") @ Vector((1.5, 0, 0))
    assert close(tip(scene), expected), (tip(scene), expected)
    # the structure list and click-selection still follow the CAD tree
    logic.rebuild_tree(scene)
    names = [it.obj.get(build.PROP_NAME) for it in scene.fresing.tree]
    assert names == ["TEST.CRANE", "BOOM.ASM", "TROLLEY.ASM"]
    assert logic.subassembly_for_pick(ob(scene, "BOOM")) is boom_asm
    assert logic.part_count(build.model_roots(scene)[0]) == 12
    joints.set_value(j, 0.0)
    update(scene)
    assert close(tip(scene), start)
    # removing the joint puts the boom back in the CAD tree
    joints.set_value(j, math.radians(10))
    joints.remove(scene, j)
    update(scene)
    assert boom_asm.parent is build.model_roots(scene)[0] and close(tip(scene), start)
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.JOINT_KINDS]


def test_limits_clamp(scene):
    j = boom_joint(scene)
    j.use_limits = True
    j.rot_min, j.rot_max = math.radians(-10), math.radians(45)
    assert abs(joints.set_value(j, math.radians(60)) - math.radians(45)) < 1e-6
    ui = j.motion.id_properties_ui(joints.VALUE).as_dict()
    assert abs(ui["max"] - math.radians(45)) < 1e-6


def test_chain_trolley_rides_on_boom(scene):
    jb = boom_joint(scene)
    trolley = ob(scene, "TROLLEY.ASM")
    cad = trolley.matrix_world.translation.copy()
    jt = joints.create(scene, "SLIDE", [trolley], cad, Vector((1, 0, 0)), base=ob(scene, "BOOM.ASM"))
    assert jt.frame.parent is ob(scene, "BOOM.ASM")
    sign = 1 if joints.axis_world(jb)[1].y > 0 else -1
    joints.set_value(jb, math.radians(30))
    joints.set_value(jt, 0.2)
    update(scene)
    expected = PIVOT + Matrix.Rotation(sign * math.radians(30), 3, "Y") @ (cad - PIVOT + Vector((0.2, 0, 0)))
    assert close(trolley.matrix_world.translation, expected), (trolley.matrix_world.translation, expected)
    # a joint cannot sit on what it moves
    with pytest.raises(RuntimeError):
        joints.set_base(scene, jb, ob(scene, "BOOM"))
    # changing the axis keeps the parts where they are
    before = ob(scene, "TROLLEY").matrix_world.copy()
    joints.flip(scene, jt)
    update(scene)
    assert abs(joints.get_value(jt) - 0.2) < 1e-9
    after_flip = ob(scene, "TROLLEY").matrix_world.translation
    expected_flip = PIVOT + Matrix.Rotation(sign * math.radians(30), 3, "Y") @ (cad - PIVOT + Vector((-0.2, 0, 0)))
    assert close(after_flip, expected_flip), (after_flip, expected_flip)
    _ = before


def test_pose_roundtrip_and_reset(scene):
    j = boom_joint(scene)
    cover = ob(scene, "COVER")
    joints.set_value(j, math.radians(20))
    cover.matrix_basis = Matrix.Translation((0, 0, 0.3)) @ cover.matrix_basis
    update(scene)
    want_tip, want_cover = tip(scene).copy(), cover.matrix_world.translation.copy()
    states.save_pose(scene, "Up")
    states.reset_pose(scene)
    update(scene)
    assert close(tip(scene), (1.6, 0.3, 0.4)) and cover.matrix_world.translation.z < want_cover.z - 0.25
    assert states.apply_pose(scene, "Up")
    update(scene)
    assert close(tip(scene), want_tip) and close(cover.matrix_world.translation, want_cover)
    # a free move survives adding a joint (stored relative to the rest position)
    joints.create(scene, "ROTATE", [cover], cover.matrix_world.translation, Vector((0, 0, 1)))
    update(scene)
    assert close(cover.matrix_world.translation, want_cover)


def test_explode(scene):
    root = build.model_roots(scene)[0]
    before = {o.name: o.matrix_world.translation.copy() for o in scene.objects
              if o.get(build.PROP_KIND) in build.MODEL_KINDS}
    n = states.explode(scene, root, 0.5)
    update(scene)
    assert n >= 5
    moved = sum(1 for o in scene.objects if o.name in before and
                (o.matrix_world.translation - before[o.name]).length > 1e-3)
    assert moved >= 5
    states.save_pose(scene, "Exploded")
    states.reset_pose(scene)
    update(scene)
    assert all(close(o.matrix_world.translation, before[o.name]) for o in scene.objects if o.name in before)


def test_visibility_sets(scene):
    cover = ob(scene, "COVER")
    logic.set_hidden(cover, True)
    states.save_visibility(scene, "No cover")
    states.show_all(scene)
    assert not cover.hide_render
    assert states.apply_visibility(scene, "No cover")
    assert cover.hide_render and logic.is_hidden(cover)


def test_saved_scene_switches_everything(scene):
    from fresing_render.blender import cameras
    s = scene.fresing
    j = boom_joint(scene)
    cam_a = scene.camera
    joints.set_value(j, math.radians(25))
    logic.set_hidden(ob(scene, "COVER"), True)
    s.background = "TRANSPARENT"
    s.out_format = "square"
    states.save_shot(scene, "Hero")
    # change everything
    cam_b = cameras.add_camera(scene, "FRONT")
    joints.set_value(j, 0.0)
    states.show_all(scene)
    s.background = "COLOR"
    s.out_format = "presentation"
    g = s.groups[0]
    old_mat = g.material
    g.material = "steel_machined" if old_mat != "steel_machined" else "paint_gloss"
    assert scene.camera is cam_b
    warnings = states.apply_shot(scene, "Hero")
    assert not warnings, warnings
    assert scene.camera is cam_a
    assert abs(math.degrees(joints.get_value(j)) - 25) < 1e-6
    assert ob(scene, "COVER").hide_render
    assert s.background == "TRANSPARENT" and scene.render.film_transparent
    assert s.out_format == "square" and scene.render.resolution_x == scene.render.resolution_y
    assert s.groups[0].material == old_mat


def _anim(scene, j):
    s = scene.fresing
    a = s.animations.add()
    a.name = "Luff"
    a.fps = "25"
    a.tail = 0.0
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration = "JOINT", j.name, 0.0, 2.0
    b.use_from, b.from_angle, b.to_angle = False, 0.0, math.radians(60)
    h = a.blocks.add()
    cover = ob(scene, "COVER")
    h.kind, h.start, h.target_uid, h.target_name = "HIDE", 1.0, cover[build.PROP_UID], "COVER"
    c = a.blocks.add()
    c.kind, c.camera_mode, c.orbit_angle, c.start, c.duration = "CAMERA", "ORBIT", math.radians(90), 0.0, 2.0
    return a


def test_animation_bake_and_clear(scene):
    j = boom_joint(scene)
    a = _anim(scene, j)
    cam0 = scene.camera
    cam_loc0 = cam0.matrix_world.translation.copy()
    info = animation.bake(scene, a)
    assert info["frames"] == 51 and not info["warnings"], info
    assert scene.frame_end == 51 and scene.camera.get("fr_anim_camera")
    scene.frame_set(26)
    assert abs(math.degrees(joints.get_value(j)) - 30) < 0.5
    cover = ob(scene, "COVER")
    assert cover.hide_render
    scene.frame_set(25)
    assert not cover.hide_render
    scene.frame_set(51)
    assert abs(math.degrees(joints.get_value(j)) - 60) < 1e-3
    centre = Vector(((Vector(scene.fresing.bounds_min) + Vector(scene.fresing.bounds_max)) / 2))
    expect = Matrix.Translation(centre) @ Matrix.Rotation(math.radians(90), 4, "Z") @ Matrix.Translation(-centre)
    assert close(scene.camera.matrix_world.translation, expect @ cam_loc0, 1e-3)
    assert [m.name for m in scene.timeline_markers]
    # editing the joint structure clears the keys and restores the model
    animation.clear_keys(scene)
    update(scene)
    assert scene.fresing.anim_baked == "" and scene.camera is cam0
    assert abs(joints.get_value(j)) < 1e-9 and not cover.hide_render and not cover.hide_viewport
    assert not [act for act in bpy.data.actions if act.get(animation.TAG) and act.users]


def test_saved_file_keeps_working(scene, tmp_path):
    j = boom_joint(scene)
    name = j.name
    path = str(tmp_path / "crane.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    j = sc.fresing.joints[name]
    joints.set_value(j, math.radians(30))
    update(sc)
    assert not close(tip(sc), (1.6, 0.3, 0.4))


def test_update_model_keeps_work(scene):
    s = scene.fresing
    jb = boom_joint(scene)
    trolley = ob(scene, "TROLLEY.ASM")
    jt = joints.create(scene, "SLIDE", [trolley], trolley.matrix_world.translation, Vector((1, 0, 0)),
                       base=ob(scene, "BOOM.ASM"))
    jb.use_limits = True
    jb.rot_max = math.radians(70)
    joints.set_value(jb, math.radians(20))
    joints.set_value(jt, 0.1)
    cover = ob(scene, "COVER")
    cover["fr_group_manual"] = "Covers"
    bolts = sorted((o for o in build.iter_parts(scene) if o[build.PROP_NAME].startswith("ISO 4017")),
                   key=lambda o: (round(o.matrix_world.translation.x, 3), round(o.matrix_world.translation.y, 3)))
    far = bolts[-1]                                   # the bolt at (950, 550)
    assert close(far.matrix_world.translation, (0.95, 0.55, 0.1))
    logic.set_hidden(far, True)
    logic.exclude([ob(scene, "WHEEL", 0)])
    states.save_pose(scene, "Work")
    states.save_visibility(scene, "Bolt off")
    update(scene)
    tip_before = tip(scene).copy()
    root = build.model_roots(scene)[0]

    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update(scene)
    assert len(build.model_roots(scene)) == 1
    assert len(s.joints) == 2 and all(joints.is_valid(x) for x in s.joints)
    jb, jt = s.joints[jb.name], s.joints[jt.name]
    assert abs(math.degrees(joints.get_value(jb)) - 20) < 1e-6 and abs(joints.get_value(jt) - 0.1) < 1e-9
    assert jb.use_limits and abs(math.degrees(jb.rot_max) - 70) < 1e-6
    assert jt.frame.parent is ob(scene, "BOOM.ASM")
    assert close(tip(scene), tip_before)
    assert ob(scene, "COVER").get("fr_group_manual") == "Covers"
    assert ob(scene, "COVER")[build.PROP_GROUP] == "Covers"
    new_bolts = [o for o in build.iter_parts(scene) if o[build.PROP_NAME].startswith("ISO 4017")]
    assert len(new_bolts) == 3
    hidden = [o for o in new_bolts if logic.is_hidden(o)]
    assert len(hidden) == 1 and close(hidden[0].matrix_world.translation, (0.95, 0.55, 0.1))
    assert sum(1 for o in scene.objects if o.get(build.PROP_NAME) == "WHEEL" and o.get(build.PROP_EXCLUDED)) == 1
    assert [x.text for x in s.report_new] == ["BOOM.LAMP"]
    assert [x.text for x in s.report_missing] == ["ISO 4017 M12 x 40 - 8.8 HDG"]
    # saved states point at the new parts
    states.reset_pose(scene)
    states.show_all(scene)
    assert states.apply_pose(scene, "Work") and states.apply_visibility(scene, "Bolt off")
    update(scene)
    assert close(tip(scene), tip_before)
    assert len([o for o in new_bolts if logic.is_hidden(o)]) == 1
    # nothing of the old model is left
    assert len(list(build.iter_parts(scene))) == 12


def test_render_queue_still_and_video(scene, tmp_path):
    s = scene.fresing
    j = boom_joint(scene)
    s.out_resolution = "preview"
    s.quality = "draft"
    s.use_gpu = False
    states.save_shot(scene, "Side")
    a = s.animations.add()
    a.name = "Short"
    a.tail = 0.0
    a.out_resolution = "preview"
    a.quality = "draft"
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.to_angle = "JOINT", j.name, 0.08, math.radians(20)
    queue.add_job(scene, "STILL", shot="Side")
    queue.add_job(scene, "ANIMATION", animation="Short")
    queue.add_job(scene, "TEST", animation="Short")
    for job in s.queue:
        job.quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "q.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 600:
        time.sleep(1.0)
    queue.sync(scene)
    st = [(x.label, x.status, x.message) for x in s.queue]
    assert all(x.status == "DONE" for x in s.queue), (st, queue.log_tail(qdir, 30))
    still, video = s.queue[0].output, s.queue[1].output
    assert os.path.isfile(still) and still.endswith(".png")
    assert os.path.isfile(video) and video.endswith(".mp4") and os.path.getsize(video) > 1000
    frames = os.path.splitext(video)[0]
    assert sorted(os.listdir(frames)) == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    test = s.queue[2]                                   # time test: the middle frame and an estimate
    assert test.label == "Time test: Short" and queue.last_time_test(scene, "Short") == test
    assert os.path.isfile(test.output) and test.output.endswith("_frame_0002.png"), test.output
    assert "_time_tests" in test.output
    assert "s per frame on CPU" in test.message and "for 3 frames at" in test.message, test.message
    assert os.listdir(os.path.dirname(test.output)) == [os.path.basename(test.output)]   # first frame removed


def test_project_lock(tmp_path):
    import json
    blend = str(tmp_path / "p.blend")
    open(blend, "w").close()
    assert project_lock.other_user(blend) is None
    project_lock.write(blend)
    assert project_lock.read(blend) is not None and project_lock.other_user(blend) is None
    with open(project_lock.lock_path(blend), "w") as fh:
        json.dump({"user": "anna", "computer": "WS-07", "since": time.time(), "heartbeat": time.time()}, fh)
    other = project_lock.other_user(blend)
    assert other and "anna on WS-07" in project_lock.describe(other)
    with open(project_lock.lock_path(blend), "w") as fh:
        json.dump({"user": "anna", "computer": "WS-07", "since": 0, "heartbeat": time.time() - 3600}, fh)
    assert project_lock.other_user(blend) is None, "stale locks are ignored"


def test_ui_motion_panels_draw(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui, ui_motion
    s = scene.fresing
    j = boom_joint(scene)
    states.save_pose(scene, "P")
    states.save_visibility(scene, "V")
    states.save_shot(scene, "S")
    _anim(scene, j)
    for kind in ("JOINT", "POSE", "CAMERA", "SHOW"):
        b = s.animations[0].blocks.add()
        b.kind = kind
    queue.add_job(scene, "STILL", shot="S")
    t = queue.add_job(scene, "TEST", animation=s.animations[0].name)
    t.status, t.message, t.output = "DONE", "15.2 s per frame on GPU: about 1.0 h for 236 frames", __file__
    errors = []

    class FL(FakeLayout):
        def prop(self, data, name, *a, **k):
            if name.startswith('["'):
                if name[2:-2] not in data:
                    self.errors.append(f"missing custom property {name}")
                return
            super().prop(data, name, *a, **k)

        def prop_search(self, data, name, search_data, search_prop, *a, **k):
            self.prop(data, name)
            if search_prop not in search_data.bl_rna.properties:
                self.errors.append(f"missing search list {search_prop}")

        def progress(self, *a, **k):
            pass

        def _child(self, *a, **k):
            return FL(self.errors)

        row = column = box = split = _child

    for blk in range(len(s.animations[0].blocks)):
        s.animations[0].blocks_index = blk
        for cls in ui_motion.CLASSES + ui.CLASSES:
            if issubclass(cls, bpy.types.Panel):
                fake = type("P", (), {"layout": FL(errors)})()
                cls.draw(fake, bpy.context)
                for extra in ("draw_header", "draw_header_preset"):
                    if hasattr(cls, extra):
                        getattr(cls, extra)(fake, bpy.context)
    for cls, data, prop in ((ui_motion.FRESING_UL_joints, s, "joints"), (ui_motion.FRESING_UL_poses, s, "poses"),
                            (ui_motion.FRESING_UL_shots, s, "shots"), (ui_motion.FRESING_UL_anims, s, "animations"),
                            (ui_motion.FRESING_UL_blocks, s.animations[0], "blocks"),
                            (ui_motion.FRESING_UL_queue, s, "queue"), (ui.FRESING_UL_visibility, s, "visibility_sets")):
        for item in getattr(data, prop):
            cls.draw_item(None, bpy.context, FL(errors), data, item, 0, data, "", 0)
    assert not errors, errors


def test_operators_smoke(scene):
    """Every phase 2 button that works without a mouse click runs without errors."""
    s = scene.fresing
    boom = ob(scene, "BOOM.ASM")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    boom.select_set(True)
    bpy.context.view_layer.objects.active = boom
    assert bpy.ops.fresing.joint_add(kind="ROTATE", axis="Y", origin="CENTER") == {"FINISHED"}
    assert len(s.joints) == 1
    for op, kw in (("joint_flip", {}), ("joint_axis_preset", {"axis": "Z"}), ("joint_kind", {"kind": "SLIDE"}),
                   ("joint_kind", {"kind": "ROTATE"}), ("joint_value", {"target": "ZERO"}),
                   ("joint_members", {"action": "SELECT"}), ("pose_save", {"name": "A"}),
                   ("pose_apply", {"name": "A"}), ("pose_update", {}), ("explode", {}), ("pose_reset", {}),
                   ("vis_save", {"name": "V"}), ("vis_apply", {"name": "V"}), ("vis_update", {}),
                   ("shot_save", {"name": "S", "scheme": "__current__", "pose": "__keep__",
                                  "visibility": "__current__"}),
                   ("shot_apply", {"name": "S"}), ("shot_update", {}),
                   ("anim_add", {}), ("block_add", {"kind": "JOINT"}), ("block_add", {"kind": "POSE"}),
                   ("block_add", {"kind": "CAMERA"}), ("block_add", {"kind": "HIDE"}), ("block_duplicate", {}),
                   ("block_move", {"direction": "UP"}), ("block_target", {}), ("anim_build", {}), ("anim_fit_camera", {}),
                   ("anim_clear", {}), ("queue_add", {"kind": "STILL"}), ("queue_add", {"kind": "SHOT", "name": "S"}),
                   ("queue_add", {"kind": "ANIMATION"}), ("queue_add", {"kind": "TEST"}),
                   ("queue_remove", {}), ("block_remove", {}),
                   ("report_clear", {}), ("joint_remove", {}), ("pose_remove", {}), ("vis_remove", {}),
                   ("shot_remove", {}), ("anim_remove", {})):
        res = getattr(bpy.ops.fresing, op)(**kw)
        assert res == {"FINISHED"}, (op, res)
    assert s.shots.get("S") is None and len(s.joints) == 0
    assert len(s.queue) == 3


# ---- review fixes ----------------------------------------------------------


def test_scene_wins_over_built_animation(scene):
    j = boom_joint(scene)
    states.save_shot(scene, "Flat")                        # joint at 0
    a = _anim(scene, j)
    animation.bake(scene, a)
    scene.frame_set(40)
    assert joints.get_value(j) > 0.5
    states.apply_shot(scene, "Flat")
    scene.frame_set(40)                                   # keys are gone, the scene's pose stays
    assert abs(joints.get_value(j)) < 1e-9 and not scene.fresing.anim_baked


def test_update_keeps_joints_of_other_models(scene):
    machine = os.path.join(HERE, "data", "test_machine.step")
    assert bpy.ops.fresing.import_step(filepath=machine, quality="draft") == {"FINISHED"}
    cover = ob(scene, "COVER.ASM")
    jm = joints.create(scene, "ROTATE", [cover], cover.matrix_world.translation, Vector((0, 0, 1)))
    boom_joint(scene)
    crane = next(r for r in build.model_roots(scene) if r.get(build.PROP_NAME) == "TEST.CRANE")
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=crane.name) == {"FINISHED"}
    names = {j.name for j in scene.fresing.joints}
    assert jm.name in names and len(names) == 2 and not len(scene.fresing.report_notes)


def test_gone_part_does_not_hit_a_new_one(scene):
    bolts = sorted((o for o in build.iter_parts(scene) if o[build.PROP_NAME].startswith("ISO 4017")),
                   key=lambda o: (round(o.matrix_world.translation.x, 3), round(o.matrix_world.translation.y, 3)))
    gone = bolts[0]                                      # (50, 50): not in revision B
    assert close(gone.matrix_world.translation, (0.05, 0.05, 0.1))
    logic.set_hidden(gone, True)
    states.save_visibility(scene, "V")
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    assert not [o for o in build.iter_parts(scene) if logic.is_hidden(o)]
    states.apply_visibility(scene, "V")
    assert not [o for o in build.iter_parts(scene) if logic.is_hidden(o)]


def test_project_from_before_phase2(scene):
    for o in scene.objects:                             # what a 0.1 project looks like
        for key in (build.PROP_CAD_BASIS, build.PROP_REST_BASIS):
            if key in o:
                del o[key]
    j = boom_joint(scene)
    joints.set_value(j, math.radians(30))
    joints.remove(scene, j)
    update(scene)
    assert close(tip(scene), (1.6, 0.3, 0.4))


def test_renames_follow(scene):
    s = scene.fresing
    states.save_pose(scene, "Up")
    states.save_visibility(scene, "V")
    states.save_shot(scene, "Hero", pose="Up", visibility="V")
    a = s.animations.add()
    a.name = "A"
    a.start_shot = "Hero"
    queue.add_job(scene, "ANIMATION", animation="A")
    s.poses["Up"].name = "Raised"
    s.visibility_sets["V"].name = "No cover"
    s.shots["Hero"].name = "Hero shot"
    a.name = "Luffing"
    shot = s.shots["Hero shot"]
    assert shot.pose == "Raised" and shot.visibility == "No cover"
    assert a.start_shot == "Hero shot" and s.queue[0].animation == "Luffing"
    assert not states.apply_shot(scene, "Hero shot")


def test_big_groups_match_fast():
    from fresing_render.blender import reimport
    import random
    random.seed(1)
    pts = [Vector((random.random() * 10, random.random() * 10, 0)) for _ in range(1500)]
    olds = [{"kind": "part", "key_a": None, "key_b": ("bolt",), "leaf": "bolt", "pos": p} for p in pts]
    news = [{"kind": "part", "key_a": None, "key_b": ("bolt",), "leaf": "bolt", "pos": p + Vector((0.0001, 0, 0))}
            for p in reversed(pts[:1400])]
    t0 = time.time()
    pairs = reimport.match(olds, news)
    assert time.time() - t0 < 3.0
    assert len(pairs) == 1400
    assert all((o["pos"] - n["pos"]).length < 0.001 for o, n in pairs)


def test_update_matches_inventor_occurrence_names(tmp_path):
    """Inventor names every placed part ("BOLT:3"). Those names win over positions: here bolts 3
    and 4 swapped places and bolt 1 was deleted (positions alone would mix them up)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    inv_a = os.path.join(HERE, "data", "test_crane_inv_a.step")
    inv_c = os.path.join(HERE, "data", "test_crane_inv_c.step")
    assert bpy.ops.fresing.import_step(filepath=inv_a, quality="draft") == {"FINISHED"}

    def bolt(occ):
        return next(o for o in build.iter_parts(sc) if o.get(build.PROP_INSTANCE) == f"ISO 4017 M12 x 40 - 8.8 HDG:{occ}")

    assert close(bolt(3).matrix_world.translation, (0.05, 0.55, 0.1))
    logic.set_hidden(bolt(3), True)
    bolt(4)["fr_group_manual"] = "Bolt four"
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=inv_c, quality="draft", update_root=root.name) == {"FINISHED"}
    s = sc.fresing
    assert close(bolt(3).matrix_world.translation, (0.93, 0.54, 0.1)), "bolt 3 moved in revision C"
    assert close(bolt(4).matrix_world.translation, (0.05, 0.56, 0.1)), "bolt 4 moved where bolt 3 was"
    assert logic.is_hidden(bolt(3)) and not logic.is_hidden(bolt(4)) and not logic.is_hidden(bolt(2))
    assert bolt(4).get("fr_group_manual") == "Bolt four" and bolt(3).get("fr_group_manual") is None
    assert [x.text for x in s.report_new] == ["BOOM.LAMP"]
    assert [x.text for x in s.report_missing] == ["ISO 4017 M12 x 40 - 8.8 HDG"]
