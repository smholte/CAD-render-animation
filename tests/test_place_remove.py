"""Place and Remove (task 0292): move / turn a model, subassembly or parts by numbers, and remove them with what lives
on them. Blender as a module (no window); the keys and clicks in a window: tools/ui_test_place.py."""

import math
import os
import types

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, joints, lesson, lock, logic, ops_place, place,  # noqa: E402
                                    remove, workspaces)
from fresing_render.core import place as core  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)


@pytest.fixture()
def crane():
    """The test crane as the crane lesson makes it: joints Boom and Trolley, the luffing cylinder, an animation."""
    _fresh()
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    workspaces.switch(scene, "All functions")
    lesson.run(scene, "crane")
    yield scene


def ob(scene, name):
    return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)


def ctx(scene, *objs):
    return types.SimpleNamespace(scene=scene, selected_objects=list(objs), active_object=objs[0] if objs else None)


def select(scene, *objs):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0] if objs else None


def _places(scene, names, frames):
    """{(name, frame): world matrix} along the built animation."""
    out = {}
    for f in frames:
        scene.frame_set(f)
        for n in names:
            out[(n, f)] = ob(scene, n).matrix_world.copy()
    return out


def _close(a, b, tol=2e-4):
    return all(abs(a[r][c] - b[r][c]) < tol for r in range(4) for c in range(4))


def test_core_snap_steps_and_words():
    assert core.snap(123.4, 10.0) == 120.0 and core.snap(-0.2, 1.0) == 0.0 and core.snap(7.25, 0.0) == 7.25
    assert core.size_of(core.SNAP_TURN, "45") == 45.0 and core.size_of(core.SNAP_MOVE, "OFF") == 0.0
    assert core.wrap_degrees(270.0) == -90.0 and core.wrap_degrees(-180.0) == -180.0 and core.wrap_degrees(360.0) == 0.0
    assert core.to_floor(-0.25, 0.0) == 0.25
    lines = core.summary({"models": 1, "parts": 20, "joints": 2, "cylinders": 1, "steps": 1, "hoses": 2,
                          "loses": ["Joint 'X' keeps moving 1 other part"]})
    assert lines[0] == ("Goes: 1 model, 20 parts, 2 joints, 1 cylinder, 2 hoses and drag chains, 1 animation step")
    assert lines[1].startswith("Joint 'X'")
    assert core.title({"names": ["BOOM.ASM"]}) == "Remove 'BOOM.ASM'?"
    assert core.title({"names": ["A", "B", "C"]}) == "Remove 'A' and 2 more?"


def test_a_moved_and_turned_crane_builds_the_same_motion_moved(crane):
    """The crane moved 1 m and turned 90°: Build gives the same motion, moved and turned."""
    scene = crane
    s = scene.fresing
    a = s.animations[0]
    names = ("BOOM", "TROLLEY", "HYDRAULIC CYLINDER.ROD", "HYDRAULIC CYLINDER.BARREL")
    info = animation.bake(scene, a)
    frames = (1, max(2, info["frames"] // 2), info["frames"])
    before = _places(scene, names, frames)
    animation.clear_keys(scene)
    root = ob(scene, "TEST.CRANE")
    ops_place.set_lock(root, False)
    select(scene, root)
    D = Matrix.Translation((1.0, 0.0, 0.0)) @ Matrix.Rotation(math.radians(90.0), 4, "Z")
    place.move(scene, [root], D)
    animation.bake(scene, a)
    after = _places(scene, names, frames)
    for k, m in before.items():
        assert _close(D @ m, after[k]), (k, D @ m, after[k])
    # the fields: world position of the root's origin, Model axes = how far from where it was imported
    x, y, z, rx, ry, rz = place.numbers(scene, root, "WORLD")
    assert abs(x - 1000.0) < 0.1 and abs(rz - 90.0) < 0.01
    assert [round(v, 3) for v in place.numbers(scene, root, "MODEL")[:3]] == [1000.0, 0.0, 0.0]
    assert place.is_placed(root) and place.state(scene) in ("placed",)
    place.back_to_cad(scene, [root])
    assert not place.is_placed(root)


def test_the_boom_moved_100_mm_before_animating_takes_its_joint_along(crane):
    scene = crane
    s = scene.fresing
    a = s.animations[0]
    boom = ob(scene, "BOOM.ASM")
    j = joints.find(scene, "Boom")
    o0, d0 = joints.axis_world(j)
    info = animation.bake(scene, a)
    frames = (1, info["frames"])
    before = _places(scene, ("BOOM", "TROLLEY"), frames)
    animation.clear_keys(scene)
    ops_place.set_lock(boom, False)
    select(scene, boom)
    up = Matrix.Translation((0.0, 0.0, 0.1))
    place.move(scene, [boom], up)
    bpy.context.view_layer.update()
    o1, d1 = joints.axis_world(j)
    assert (o1 - o0 - Vector((0, 0, 0.1))).length < 1e-5 and (d1 - d0).length < 1e-6
    assert boom.get(place.FILE) is not None and place.FRAME_FROM in j.motion
    # its CAD place moved: the CAD pose (what Reset pose and every Build start from) keeps it
    with joints.cad_pose(scene):
        bpy.context.view_layer.update()
        cad_z = ob(scene, "BOOM").matrix_world.translation.z
    animation.bake(scene, a)
    after = _places(scene, ("BOOM", "TROLLEY"), frames)
    for k, m in before.items():
        assert _close(up @ m, after[k]), (k, up @ m, after[k])
    animation.clear_keys(scene)
    # the Model-axes numbers read the move, Back to the CAD place puts both back
    assert [round(v, 2) for v in place.numbers(scene, boom, "MODEL")] == [0.0, 0.0, 100.0, 0.0, 0.0, 0.0]
    place.back_to_cad(scene, [boom])
    bpy.context.view_layer.update()
    o2, _d2 = joints.axis_world(j)
    assert (o2 - o0).length < 1e-5 and place.FRAME_FROM not in j.motion and place.FILE not in boom
    with joints.cad_pose(scene):
        bpy.context.view_layer.update()
        assert abs(ob(scene, "BOOM").matrix_world.translation.z - (cad_z - 0.1)) < 1e-5


def test_a_part_moved_alone_keeps_its_place_through_a_pose_and_reset(crane):
    """A part (not a joint's member) placed: Reset pose and Go to pose keep it (a G move would be undone)."""
    from fresing_render.blender import states
    scene = crane
    cover = ob(scene, "COVER")
    ops_place.set_lock(cover, False)
    w0 = cover.matrix_world.copy()
    states.save_pose(scene, "Before")
    place.move(scene, [cover], Matrix.Translation((0.0, 0.25, 0.0)))
    states.reset_pose(scene)
    states.apply_pose(scene, "Before")
    bpy.context.view_layer.update()
    assert abs(cover.matrix_world.translation.y - (w0.translation.y + 0.25)) < 1e-5


def test_fields_steps_snap_and_floor(crane):
    scene = crane
    st = scene.fresing.place
    trolley = ob(scene, "TROLLEY.ASM")
    ops_place.set_lock(trolley, False)
    select(scene, trolley)
    st.space = "WORLD"
    x0 = st.x
    st.snap_move = "10"
    st.x = x0 + 123.4                                   # snapped to 10 mm
    assert abs(st.x - core.snap(x0 + 123.4, 10.0)) < 0.01
    st.step_move = "100"
    assert bpy.ops.fresing.place_step(index=1, sign=-1) == {"FINISHED"}
    st.space = "MODEL"
    assert abs(st.y + 100.0) < 0.01
    st.snap_turn = "OFF"
    st.rz = 30.0
    assert abs(st.rz - 30.0) < 0.01
    st.step_turn = "15"
    assert bpy.ops.fresing.place_step(index=5, sign=1) == {"FINISHED"}
    assert abs(st.rz - 45.0) < 0.01
    # Put on the floor: the whole crane's lowest point on z = 0 (no surroundings in this test)
    root = ob(scene, "TEST.CRANE")
    ops_place.set_lock(root, False)
    select(scene, root)
    place.move(scene, [root], Matrix.Translation((0.0, 0.0, 0.7)))
    assert bpy.ops.fresing.place_floor() == {"FINISHED"}
    assert abs(place.lowest_z(scene, [root]) - place.floor_z(scene)) < 1e-5


def test_locked_and_client_view_refuse(crane):
    scene = crane
    boom = ob(scene, "BOOM.ASM")
    select(scene, boom)
    assert "locked in place" in place.refused(bpy.context)
    assert not bpy.ops.fresing.place_step.poll()
    ops_place.set_lock(boom, False)
    assert place.refused(bpy.context) == "" and bpy.ops.fresing.place_step.poll()
    workspaces.switch(scene, "Client view")
    try:
        assert lock.ON[0] and place.refused(bpy.context) == lock.MESSAGE
        assert not bpy.ops.fresing.place_step.poll() and not bpy.ops.fresing.remove.poll()
        assert not bpy.ops.fresing.place_window.poll()
    finally:
        workspaces.switch(scene, "All functions")


def test_a_built_animation_is_taken_off(crane):
    scene = crane
    animation.bake(scene, scene.fresing.animations[0])
    root = ob(scene, "TEST.CRANE")
    ops_place.set_lock(root, False)
    note = place.move(scene, [root], Matrix.Translation((0.5, 0.0, 0.0)))
    assert "Build again" in note and not animation.has_keys(scene)


def test_remove_the_crane_leaves_nothing_dangling_and_reopens(crane, tmp_path):
    scene = crane
    s = scene.fresing
    root = ob(scene, "TEST.CRANE")
    c = s.callouts.add()
    c.text, c.part = "Boom", ob(scene, "BOOM")
    p = remove.plan(scene, [root])
    assert (p["models"], p["parts"], p["joints"], p["cylinders"], p["labels"], p["steps"]) == (1, 20, 2, 1, 1, 1)
    lines = remove.lines(p)
    assert lines[0].startswith("Goes: 1 model, 20 parts, 2 joints, 1 cylinder") and "Ctrl+Z" in lines[-1]
    names = set(p["gone_names"])
    select(scene, root)
    assert bpy.ops.fresing.remove(names=root.name) == {"FINISHED"}
    _no_dangling(scene, names)
    assert s.model_count == 0 and len(s.tree) == 0
    path = str(tmp_path / "removed.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    _no_dangling(bpy.context.scene, names)


def _no_dangling(scene, names):
    s = scene.fresing
    assert not [n for n in names if n in bpy.data.objects]
    assert not len(s.joints) and not len(s.cylinders) and not len(s.callouts)
    for a in s.animations:
        assert not [b for b in a.blocks if b.kind in ("JOINT", "CYLINDER")]
    kinds = {o.get(build.PROP_KIND) for o in scene.objects}
    assert not kinds & set(build.MODEL_KINDS + build.JOINT_KINDS), kinds
    assert not [c for c in bpy.data.collections if c.name.startswith("FR removing")]


def test_remove_a_subassembly_keeps_the_rest_working(crane):
    """The trolley goes: its joint goes with it, the boom's joint and the cylinder stay and still move."""
    scene = crane
    s = scene.fresing
    trolley = ob(scene, "TROLLEY.ASM")
    p = remove.plan(scene, [trolley])
    assert (p["subassemblies"], p["parts"], p["joints"], p["cylinders"]) == (1, 3, 1, 0)
    remove.remove(scene, [trolley])
    assert [j.name for j in s.joints] == ["Boom"] and [c.name for c in s.cylinders] == ["Luffing cylinder"]
    assert all(joints.is_valid(j) for j in s.joints)
    assert s.model_count == 1 and logic.part_count(ob(scene, "TEST.CRANE")) == 17
    boom = ob(scene, "BOOM")
    w0 = boom.matrix_world.copy()
    joints.set_value(s.joints[0], math.radians(20.0))
    bpy.context.view_layer.update()
    assert not _close(w0, boom.matrix_world)
    info = animation.bake(scene, s.animations[0])
    assert info["frames"] > 1


def test_remove_parts_of_a_joint_says_what_it_keeps(crane):
    scene = crane
    wheel = ob(scene, "WHEEL")
    asm = ob(scene, "BOOM.ASM")
    pin = ob(scene, "BOOM.PIN")
    p = remove.plan(scene, [pin])
    assert p["parts"] == 1 and p["joints"] == 0
    p = remove.plan(scene, [wheel, asm])
    assert p["joints"] == 1 and p["subassemblies"] == 1


def test_remove_a_model_with_hoses(tmp_path):
    """The hoses test model: its hoses and drag chains go with it (no item left pointing at nothing)."""
    from fresing_render.blender import flex
    _fresh()
    assert bpy.ops.fresing.import_step(filepath=HOSES, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    flex.set_up_test_hoses(scene)
    assert len(scene.fresing.flex) >= 1
    root = build.model_roots(scene)[0]
    p = remove.plan(scene, [root])
    assert p["hoses"] == len(scene.fresing.flex)
    remove.remove(scene, [root])
    assert not len(scene.fresing.flex) and not len(scene.fresing.joints)
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    assert not [me for me in bpy.data.meshes if me.users == 0 and me.name.startswith("FR flex")]


def test_delete_outside_full_access_opens_the_remove_window(crane):
    """Delete / X in Object Mode: the app's Remove (its window), not Blender's delete; the Client view refuses."""
    scene = crane
    binds = {(k, sp, key): op for k, sp, key, _m, op, _p in lock.APP_KEYS}
    assert binds[("Object Mode", "EMPTY", "DEL")] == "fresing.remove_key"
    assert binds[("Object Mode", "EMPTY", "X")] == "fresing.remove_key"
    deletes = [x for x in lock.BLENDER_KEYS if x[0] == "Object Mode" and x[2] in ("DEL", "X")]
    assert not deletes
    assert ("fresing.remove", ) and "fresing.remove" in __import__(
        "fresing_render.blender.form_window", fromlist=["WINDOWS"]).WINDOWS


def test_model_update_keeps_a_placed_part(crane):
    """A model update carries the Place of a part over to the new revision (same move on the new file place)."""
    from fresing_render.blender import reimport
    scene = crane
    cover = ob(scene, "COVER")
    ops_place.set_lock(cover, False)
    w0 = cover.matrix_world.copy()
    place.move(scene, [cover], Matrix.Translation((0.0, 0.0, 0.3)))
    root = ob(scene, "TEST.CRANE")
    reimport.update_model(bpy.context, root, root["fr_cache"])
    bpy.context.view_layer.update()
    new = ob(scene, "COVER")
    assert abs(new.matrix_world.translation.z - (w0.translation.z + 0.3)) < 1e-5
    assert place.is_placed(new)
