"""Independent tests of task 0157 in Blender (as a Python module): the person's rig, Build, Clear keys, the Preview,
saving, the clash check's view of people. Written from the brief by an agent that did not write the code."""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, clash, people, person_rig, props_scale  # noqa: E402
from fresing_render.core import people as CP  # noqa: E402
from fresing_render.core import person_rig as CR  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


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
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    people.forget()
    return bpy.context.scene


@pytest.fixture()
def scene():
    return _fresh()


def _anim(sc, fps="25"):
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "People", fps, 0.0
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return a


def _fcurves(idb):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return []
    act = ad.action
    out = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out += list(cb.fcurves)
    except AttributeError:
        out = list(act.fcurves)
    return out


def _keys(idb) -> dict:
    out = {}
    for fc in _fcurves(idb):
        co = np.zeros(len(fc.keyframe_points) * 2)
        fc.keyframe_points.foreach_get("co", co)
        out[(fc.data_path, fc.array_index)] = co
    return out


def _place(ob):
    return (tuple(round(v, 6) for v in ob.location), tuple(round(v, 6) for v in ob.rotation_euler),
            tuple(round(v, 6) for v in ob.rotation_quaternion), ob.rotation_mode)


def _verts(me) -> np.ndarray:
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def _evaluated_verts(ob) -> np.ndarray:
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        return _verts(me)
    finally:
        ev.to_mesh_clear()


def _world_verts(ob) -> np.ndarray:
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    co = _verts(ev.data)
    M = np.array(ev.matrix_world)
    return (M @ np.c_[co, np.ones(len(co))].T)[:3].T


# ---------------------------------------------------------------------------
# the rig
# ---------------------------------------------------------------------------

def test_rig_has_the_17_bones_of_the_figure(scene):
    ob = people.add_person(scene, (5.0, 5.0, 0.0), "P", heading=0.3)
    arm = person_rig.rig_of(ob)
    assert arm is not None and arm.parent == ob and arm.type == "ARMATURE"
    assert np.allclose(np.array(arm.matrix_basis), np.eye(4))
    assert np.allclose(np.array(arm.matrix_parent_inverse), np.eye(4))
    assert {b.name for b in arm.data.bones} == set(CR.BONES) and len(arm.data.bones) == 17
    fig = person_rig.figure(ob)
    for b in CR.BONES:
        bone = arm.data.bones[b]
        assert np.allclose(np.array(bone.head_local), fig.rest_fk[b][0], atol=1e-5), b
        assert np.allclose(np.array(bone.matrix_local)[:3, :3], fig.rest_fk[b][1] @ CR.C[b], atol=1e-5), b
        par = CR.PARENT[b]
        assert (bone.parent.name if bone.parent else None) == par
    assert ob.modifiers[0].type == "ARMATURE" and ob.modifiers[0].object == arm
    assert ob.modifiers.get(props_scale.MODIFIER) is not None
    assert person_rig.ensure(ob) == arm, "made once"
    assert len([o for o in bpy.data.objects if o.name.startswith("FR rig")]) == 1


def test_rest_pose_leaves_the_mesh_as_it_is_made(scene):
    ob = people.add_person(scene, (5.0, 5.0, 0.0), "P")
    fig = person_rig.figure(ob)
    person_rig.set_pose(ob, fig.rest())
    lod = ob.modifiers[props_scale.MODIFIER]
    lod.show_viewport = False                                  # compare all points (both levels)
    try:
        ev = _evaluated_verts(ob)
    finally:
        lod.show_viewport = True
    co = _verts(ob.data)
    assert ev.shape == co.shape
    assert np.abs(ev - co).max() < 1e-5


def test_a_pose_matches_the_pure_python_skin(scene):
    """Blender's armature + weights move the points as core.person_rig.skin says (fingers left at rest)."""
    ob = people.add_person(scene, (0.0, 0.0, 0.0), "P")
    fig = person_rig.figure(ob)
    pose = fig.rest()
    fig.arm_ik(pose, "r", fig.shoulder(pose, "r") + np.array((-0.1, -0.45, 0.05)))
    fig.leg_ik(pose, "l", fig.hip(pose, "l") + np.array((0.0, -0.3, -0.7)))
    pose.local["chest"] = pose.local["chest"] @ CR.rz(0.3)
    person_rig.set_pose(ob, pose)
    lod = ob.modifiers[props_scale.MODIFIER]
    lod.show_viewport = False
    try:
        ev = _evaluated_verts(ob)
    finally:
        lod.show_viewport = True
    _m, _l, _mats, W, verts, _keys = person_rig._arrays(props_scale.person_settings(ob))
    want = CR.skin(fig, verts, W, pose)
    err = np.linalg.norm(ev - want, axis=1)
    assert err.max() < 0.004, f"Blender's skin differs from the plan by {err.max() * 1000:.1f} mm"
    assert np.linalg.norm(ev - verts, axis=1).max() > 0.2, "the pose did move the arm"


def test_pose_setting_moves_bones_not_the_mesh(scene):
    ob = people.add_person(scene, (0.0, 0.0, 0.0), "P")
    arm = person_rig.rig_of(ob)
    co0 = _verts(ob.data).copy()
    me_name = ob.data.name
    ev0 = _evaluated_verts(ob)
    ob.fresing_person.pose = "POINTING"
    bpy.context.view_layer.update()
    assert ob.data.name == me_name and np.abs(_verts(ob.data) - co0).max() == 0.0, "the mesh data stays the rest mesh"
    q = np.array(arm.pose.bones["r_arm"].rotation_quaternion)
    assert abs(q[0]) < 0.99, "the right arm's bone turned"
    ev1 = _evaluated_verts(ob)
    assert np.linalg.norm(ev1 - ev0, axis=1).max() > 0.3, "and the figure points"
    assert arm["fr_point_r"] == pytest.approx(1.0)
    ob.fresing_person.pose = "STANDING"
    bpy.context.view_layer.update()
    assert np.allclose([tuple(pb.rotation_quaternion) for pb in arm.pose.bones], [(1, 0, 0, 0)] * 17, atol=1e-6)


def test_height_change_rebuilds_the_bones(scene):
    ob = people.add_person(scene, (0.0, 0.0, 0.0), "P")
    arm = person_rig.rig_of(ob)
    head_175 = np.array(arm.data.bones["head"].head_local)
    for h in ("1.85", "1.65"):
        ob.fresing_person.height_choice = h
        bpy.context.view_layer.update()
        assert person_rig.rig_of(ob) == arm, "the same armature"
        fig = person_rig.figure(ob)
        assert fig.height == pytest.approx(float(h))
        for b in CR.BONES:
            assert np.allclose(np.array(arm.data.bones[b].head_local), fig.rest_fk[b][0], atol=1e-5), (h, b)
        assert ob.dimensions.z == pytest.approx(float(h) + 0.03, abs=0.04)
        ev = _world_verts(ob)
        assert ev[:, 2].min() == pytest.approx(0.0, abs=0.003), "still standing on the floor"
    assert np.array(arm.data.bones["head"].head_local)[2] < head_175[2]


# ---------------------------------------------------------------------------
# Build, Clear keys, Preview
# ---------------------------------------------------------------------------

def test_scene_without_people_builds_as_before(scene):
    a = _anim(scene)
    names = {o.name for o in bpy.data.objects}
    assert people.length(scene) == 0.0 and animation.length_seconds(a) == pytest.approx(1.0)
    info = animation.bake(scene, a)
    assert not info.get("warnings")
    assert {o.name for o in bpy.data.objects} == names, "Build made no new objects"
    assert bpy.data.collections.get(people.COLLECTION) is None
    assert scene.frame_end == 26
    # a person standing as a prop without actions changes nothing either
    from fresing_render.blender import surroundings
    surroundings.add_prop(scene, "PERSON")
    animation.clear_keys(scene)
    assert people.length(scene) == 0.0 and not people.acting(scene)
    animation.bake(scene, a)
    assert scene.frame_end == 26


def test_example_builds_keys_that_cover_the_peoples_time(scene):
    a = _anim(scene)
    anna, ben, box = people.set_up_example(scene)
    pl = people.plan(scene, flat=True)
    assert not pl.warnings
    assert animation.length_seconds(a) >= pl.length
    info = animation.bake(scene, a)
    assert not info.get("warnings"), info.get("warnings")
    assert scene.frame_end >= 1 + pl.length * 25 - 1
    for ob in (anna, ben, box, person_rig.rig_of(anna), person_rig.rig_of(ben)):
        assert _keys(ob), f"{ob.name} has keys"
    k = _keys(anna)
    xs = k[("location", 0)]
    assert xs[-2] >= pl.length * 25, "Anna's keys run to the end of her time"
    assert people.check_example(scene)


def test_build_twice_gives_the_same_keys(scene):
    a = _anim(scene)
    anna, ben, box = people.set_up_example(scene)
    obs = (anna, ben, box, person_rig.rig_of(anna), person_rig.rig_of(ben))
    animation.bake(scene, a)
    k1 = [_keys(o) for o in obs]
    end1 = scene.frame_end
    animation.bake(scene, a)
    k2 = [_keys(o) for o in obs]
    assert scene.frame_end == end1
    for o, a1, a2 in zip(obs, k1, k2):
        assert a1.keys() == a2.keys(), o.name
        for key in a1:
            assert a1[key].shape == a2[key].shape and np.allclose(a1[key], a2[key], atol=1e-6), (o.name, key)


def test_clear_keys_puts_people_and_the_toolbox_back(scene):
    a = _anim(scene)
    anna, ben, box = people.set_up_example(scene)
    obs = (anna, ben, box)
    before = {o.name: _place(o) for o in obs}
    bpy.context.view_layer.update()
    box_world = np.array(box.matrix_world)
    rig = person_rig.rig_of(anna)
    bones0 = [tuple(pb.rotation_quaternion) for pb in rig.pose.bones]
    animation.bake(scene, a)
    scene.frame_set(scene.frame_end)
    animation.clear_keys(scene)
    bpy.context.view_layer.update()
    for o in obs:
        assert _place(o) == before[o.name], o.name
        assert not _fcurves(o), f"{o.name} keeps no keys"
    for r in (rig, person_rig.rig_of(ben)):
        assert not _fcurves(r), f"{r.name} keeps no keys"
    assert np.allclose(np.array(box.matrix_world), box_world, atol=1e-5), "the toolbox is in Anna's hand again"
    assert np.allclose([tuple(pb.rotation_quaternion) for pb in rig.pose.bones], bones0, atol=1e-6)
    assert people.HOME not in anna and people.HOME not in ben


def test_toolbox_lies_on_the_floor_after_put_down_to_the_last_frame(scene):
    a = _anim(scene)
    anna, _ben, box = people.set_up_example(scene)
    animation.bake(scene, a)
    pl = people.plan(scene, flat=True)
    put = next(s for s in pl.people["Anna"].segs if s.kind == "PUT_DOWN")
    first = None
    for f in (int(put.t1 * 25) + 2, (int(put.t1 * 25) + scene.frame_end) // 2, scene.frame_end):
        scene.frame_set(f)
        w = _world_verts(box)
        assert w[:, 2].min() == pytest.approx(0.0, abs=0.005), f"frame {f}: the toolbox is on the floor"
        centre = w.mean(axis=0)
        if first is None:
            first = centre
        assert np.allclose(centre, first, atol=1e-4), "and it stays where it was put"
    # in Anna's hand while she walks: off the floor and beside her
    scene.frame_set(40)
    w = _world_verts(box)
    a_xy = np.array(anna.matrix_world.translation)[:2]
    assert w[:, 2].min() > 0.1
    assert np.linalg.norm(w.mean(axis=0)[:2] - a_xy) < 0.5


def test_a_project_saved_with_people_opens_and_builds_again(scene, tmp_path):
    a = _anim(scene)
    people.set_up_example(scene)
    animation.bake(scene, a)
    k1 = _keys(bpy.data.objects["Anna"])
    animation.clear_keys(scene)
    path = str(tmp_path / "people.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    anna = bpy.data.objects["Anna"]
    assert person_rig.rig_of(anna) is not None and len(anna.fresing_person.actions) == 4
    assert anna.fresing_person.carry is not None
    info = animation.bake(sc, sc.fresing.animations[0])
    assert not info.get("warnings")
    k2 = _keys(anna)
    assert k1.keys() == k2.keys()
    for key in k1:
        assert np.allclose(k1[key], k2[key], atol=1e-6), key
    assert people.check_example(sc)


def test_preview_moves_people_and_zero_puts_them_back(scene):
    anna, ben, box = people.set_up_example(scene)
    bpy.context.view_layer.update()
    before = {o.name: _place(o) for o in (anna, ben, box)}
    rig = person_rig.rig_of(anna)
    bones0 = [tuple(pb.rotation_quaternion) for pb in rig.pose.bones]
    pl = people.plan(scene)
    scene.fresing.people_preview = 0.5
    bpy.context.view_layer.update()
    root, _pose = pl.pose_at("Anna", 0.5 * pl.length)
    assert tuple(anna.location)[:2] == pytest.approx(root[:2], abs=1e-5)
    assert anna.rotation_euler.z == pytest.approx(root[3], abs=1e-5)
    assert _place(anna) != before["Anna"]
    scene.fresing.people_preview = 0.0
    bpy.context.view_layer.update()
    for o in (anna, ben, box):
        assert _place(o) == before[o.name], o.name
    assert np.allclose([tuple(pb.rotation_quaternion) for pb in rig.pose.bones], bones0, atol=1e-6)
    assert "fr_people_preview" not in scene


def test_build_after_a_preview_starts_from_home(scene):
    a = _anim(scene)
    anna, _ben, _box = people.set_up_example(scene)
    home = _place(anna)
    scene.fresing.people_preview = 0.7
    animation.bake(scene, a)
    assert scene.fresing.people_preview == 0.0
    scene.frame_set(1)
    bpy.context.view_layer.update()
    assert tuple(anna.matrix_world.translation) == pytest.approx(home[0], abs=1e-4)
    animation.clear_keys(scene)
    assert _place(anna) == home


# ---------------------------------------------------------------------------
# the clash check
# ---------------------------------------------------------------------------

def test_clash_check_knows_acting_people_not_items(scene):
    _anim(scene)
    anna, ben, box = people.set_up_example(scene)
    from fresing_render.blender import surroundings
    idle = surroundings.add_prop(scene, "PERSON")                  # a person who does nothing stays a prop
    names = {o.name for o in clash.objects(scene)}
    assert {"Anna", "Ben"} <= names
    assert box.name not in names and idle.name not in names
    assert not any(n.startswith("FR rig") or n.startswith("FR path") for n in names)


def test_example_has_no_clashes(scene):
    a = _anim(scene)
    people.set_up_example(scene)
    animation.bake(scene, a)
    run = clash.check(scene, store=False)
    rows = [r for r in run.rows if r.kind == "CLASH"]
    assert not rows, [(r.a, r.b, r.depth) for r in rows]


def test_a_path_through_the_machine_is_warned_about(scene):
    a = _anim(scene)
    from fresing_render.blender import logic
    mn, mx = logic.cached_bounds(scene)
    mid = ((float(mn[0]) + float(mx[0])) / 2, (float(mn[1]) + float(mx[1])) / 2)
    p = people.add_person(scene, (mid[0], float(mn[1]) - 3.0, 0.0), "Walker", heading=math.pi)
    people.set_path(scene, p, [(mid[0], float(mx[1]) + 3.0, 0.0)])
    people._act(p.fresing_person, "WALK", place="END")
    info = animation.bake(scene, a)
    assert any("Walker" in w and "runs into" in w for w in info.get("warnings", [])), info.get("warnings")


def test_feet_from_the_built_keys_stand_on_the_floor(scene):
    """Read back from the armature's keys (not the plan): a planted foot's sole stays put and on the floor."""
    a = _anim(scene)
    anna, _ben, _box = people.set_up_example(scene)
    animation.bake(scene, a)
    pl = people.plan(scene, flat=True)
    per = pl.people["Anna"]
    k = per.fig.k
    worst_slide, worst_z = 0.0, 0.0
    for side in ("l", "r"):
        for plant in per.feet[side].plants[1:]:
            a0 = plant.down + plant.roll_in + 0.04
            b0 = min(plant.up - plant.roll_out, pl.length) - 0.04
            if b0 - a0 < 0.1:
                continue
            pts = []
            for t in np.linspace(a0, b0, 4):
                scene.frame_set(int(t * 25) + 1, subframe=(t * 25) % 1.0)
                m = person_rig.bone_world(anna, f"{side}_foot")
                pts.append(np.array(m.translation))
            worst_slide = max(worst_slide, max(np.linalg.norm(p - pts[0]) for p in pts))
            worst_z = max(worst_z, abs(pts[0][2] - CP.P.ANKLE_H * k))
    assert worst_slide < 0.003, f"a standing foot slides {worst_slide * 1000:.1f} mm in the built animation"
    assert worst_z < 0.005, f"an ankle stands {worst_z * 1000:.1f} mm off its height"


def test_renaming_a_person_still_builds(scene):
    a = _anim(scene)
    anna, _ben, box = people.set_up_example(scene)
    anna.name = "Annie"
    info = animation.bake(scene, a)
    assert not info.get("warnings")
    assert [c.name for c in box.constraints if c.name.startswith(people.HELD)] == [f"{people.HELD} Annie r"]
    scene.frame_set(60)
    bpy.context.view_layer.update()
    d = np.array(box.matrix_world.translation) - np.array(anna.matrix_world.translation)
    assert np.linalg.norm(d[:2]) < 0.5, "the box is still in her hand"
