"""Task 0012: couplings (one joint follows another) and motors ("run at 12 rpm").

Every value is checked against a hand-calculated one on the test crane (tests/data):
* WHEEL: Ø50 mm cylinders along Y inside TROLLEY.ASM (a wheel rolling 100 mm turns 4 rad = 229.18°);
* the four ISO 4017 bolts are used as gripper jaws, COVER and TROLLEY.ASM as telescope sections.
Joint values are internal units: radians and metres.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
TOL = 1e-5                  # 0.01 mm / 0.0006°: matrices and driver results are single precision
WHEEL_R = 0.025             # m
TURN = 2 * math.pi

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, states  # noqa: E402


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
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def update():
    bpy.context.view_layer.update()


def J(sc, name):
    return joints.find(sc, name)


def V(sc, name):
    return joints.get_value(J(sc, name))


def pos(o):
    return o.matrix_world.translation.copy()


def close(a, b, tol=TOL):
    return (Vector(a) - Vector(b)).length < tol


def close_m(a, b, tol=TOL):
    return all(abs(a[r][c] - b[r][c]) < tol for r in range(3) for c in range(3))


def move(sc, name, value):
    joints.set_value(J(sc, name), value)
    update()


# ---------------------------------------------------------------------------
# set-ups used by several tests
# ---------------------------------------------------------------------------


def trolley_and_wheels(sc):
    """Trolley slides along X; each wheel turns about its own axle (Y)."""
    tr = ob(sc, "TROLLEY.ASM")
    joints.create(sc, "SLIDE", [tr], pos(tr), X, name="Trolley")
    for n in (0, 1):
        w = ob(sc, "WHEEL", n)
        joints.create(sc, "ROTATE", [w], pos(w), Y, name=f"Wheel {n + 1}")


def jaws(sc):
    """Two bolts as gripper jaws on one line (X): jaw B follows jaw A the other way (-1)."""
    a, b = ob(sc, "ISO 4017 M12 x 40 - 8.8 HDG", 0), ob(sc, "ISO 4017 M12 x 40 - 8.8 HDG", 1)
    joints.create(sc, "SLIDE", [a], pos(a), X, name="Jaw A")
    joints.create(sc, "SLIDE", [b], pos(b), X, name="Jaw B")
    joints.set_follows(sc, J(sc, "Jaw B"), "Jaw A", ratio=-1.0)


# ---------------------------------------------------------------------------
# each coupling type against hand-calculated values
# ---------------------------------------------------------------------------


def test_rotate_follows_rotate_gear(scene):
    """Gear pair: wheel 2 turns half as fast the other way (-0.5 turns per turn of wheel 1)."""
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1", ratio=-0.5)
    w2 = ob(scene, "WHEEL", 1)
    p0 = pos(w2)
    move(scene, "Wheel 1", math.radians(90))
    assert abs(V(scene, "Wheel 2") - math.radians(-45)) < TOL
    assert close(pos(w2), p0), "a wheel turning on its axle stays where it is"
    assert close_m(w2.matrix_world.to_3x3(), Matrix.Rotation(math.radians(-45), 3, Y))
    move(scene, "Wheel 1", math.radians(-720))                        # two turns back: 1 turn forward
    assert abs(V(scene, "Wheel 2") - math.radians(360)) < TOL


def test_slide_follows_slide_jaws(scene):
    """Gripper jaws: ratio -1, they close towards each other."""
    jaws(scene)
    a, b = ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG", 0), ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG", 1)
    pa, pb = pos(a), pos(b)
    move(scene, "Jaw A", 0.03)
    assert abs(V(scene, "Jaw B") + 0.03) < TOL
    assert close(pos(a) - pa, (0.03, 0, 0)) and close(pos(b) - pb, (-0.03, 0, 0))


def test_slide_follows_slide_telescope(scene):
    """Telescope: section 2 rides on section 1 (a stack) and follows it 1:1, so it goes twice as far."""
    cover, tr = ob(scene, "COVER"), ob(scene, "TROLLEY.ASM")
    pc, pt = pos(cover), pos(tr)
    joints.create(scene, "SLIDE", [cover, tr], pc, X, name="Section 1")
    joints.create(scene, "SLIDE", [tr], pt, X, name="Section 2")
    assert joints.rides_on(scene, J(scene, "Section 2")).name == "Section 1"
    assert bpy.context.scene.fresing.joints.find("Section 2") == 1
    scene.fresing.joints_index = 1
    assert bpy.ops.fresing.joint_follow(mode="FOLLOW") == {"FINISHED"}   # proposes the joint it rides on
    j2 = J(scene, "Section 2")
    assert j2.follows == "Section 1" and j2.couple_ratio == 1.0
    move(scene, "Section 1", 0.2)
    assert close(pos(cover) - pc, (0.2, 0, 0)) and close(pos(tr) - pt, (0.4, 0, 0))


def test_rotate_drives_slide_spindle(scene):
    """Spindle: the cover turns as the screw (about X); the trolley nut travels 5 mm per turn."""
    cover, tr = ob(scene, "COVER"), ob(scene, "TROLLEY.ASM")
    joints.create(scene, "ROTATE", [cover], pos(cover), X, name="Screw")
    joints.create(scene, "SLIDE", [tr], pos(tr), X, name="Nut")
    joints.set_follows(scene, J(scene, "Nut"), "Screw")
    assert J(scene, "Nut").couple_ratio == 5.0                         # the usual ball-screw pitch
    pt = pos(tr)
    move(scene, "Screw", 3 * TURN)
    assert abs(V(scene, "Nut") - 0.015) < TOL and close(pos(tr) - pt, (0.015, 0, 0))
    # rack and pinion: a pinion of Ø40 mm on a rack: π·40 mm per turn
    J(scene, "Nut").couple_ratio = math.pi * 40
    update()
    assert abs(V(scene, "Nut") - 3 * math.pi * 0.040) < TOL


def test_slide_drives_rotate_rolling_wheel(scene):
    """A wheel of Ø50 mm rolls along: 360/(π·50) degrees per mm; 100 mm of travel = 4 rad."""
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=360.0 / (math.pi * 50))
    w = ob(scene, "WHEEL", 0)
    p0 = pos(w)
    move(scene, "Trolley", 0.1)
    assert abs(V(scene, "Wheel 1") - 0.1 / WHEEL_R) < 1e-4            # ratio is kept in single precision
    assert close(pos(w) - p0, (0.1, 0, 0))
    assert close_m(w.matrix_world.to_3x3(), Matrix.Rotation(0.1 / WHEEL_R, 3, Y), 1e-4)


def test_offset(scene):
    jaws(scene)
    J(scene, "Jaw B").couple_offset_dist = 0.01
    move(scene, "Jaw A", 0.0)
    assert abs(V(scene, "Jaw B") - 0.01) < TOL
    move(scene, "Jaw A", 0.02)
    assert abs(V(scene, "Jaw B") + 0.01) < TOL


def test_chain_of_three(scene):
    """Motor -> spindle nut -> rolling wheel: 2 turns × 50 mm = 100 mm -> 4 rad."""
    trolley_and_wheels(scene)
    cover = ob(scene, "COVER")
    joints.create(scene, "ROTATE", [cover], pos(cover), X, name="Motor")
    joints.set_motor(scene, J(scene, "Motor"), True)
    joints.set_follows(scene, J(scene, "Trolley"), "Motor", ratio=50.0)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=360.0 / (math.pi * 50))
    move(scene, "Motor", 2 * TURN)
    assert abs(V(scene, "Trolley") - 0.1) < TOL
    assert abs(V(scene, "Wheel 1") - 4.0) < 1e-4
    assert joints.driver_of(scene, J(scene, "Wheel 1")).name == "Motor"
    assert [x.name for x in joints.all_followers(scene, J(scene, "Motor"))] == ["Trolley", "Wheel 1"]
    # the same values worked out without Blender (used for limit warnings in animations)
    assert abs(joints.driven_value(scene, J(scene, "Wheel 1"), {"Motor": TURN}) - 2.0) < 1e-4


def test_loops_and_itself_refused(scene):
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley")
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1")
    with pytest.raises(RuntimeError, match="follow itself"):
        joints.set_follows(scene, J(scene, "Trolley"), "Trolley")
    with pytest.raises(RuntimeError, match="cannot follow each other") as exc:
        joints.set_follows(scene, J(scene, "Trolley"), "Wheel 2")
    assert "through 'Wheel 1'" in str(exc.value)
    with pytest.raises(RuntimeError, match="cannot follow each other"):
        joints.set_follows(scene, J(scene, "Wheel 1"), "Wheel 2")
    assert J(scene, "Trolley").follows == ""
    # through the panel's field: refused, the field goes back, the reason is shown under it
    t = J(scene, "Trolley")
    t.follows = "Wheel 2"
    assert t.follows == "" and "cannot follow each other" in t["_follow_error"]
    assert joints.couplings_simple(scene)


def test_follower_cannot_be_moved_by_hand_poses_or_steps(scene):
    jaws(scene)
    s = scene.fresing
    move(scene, "Jaw A", 0.02)
    joints.set_value(J(scene, "Jaw B"), 0.5)                       # the driver wins
    update()
    assert abs(V(scene, "Jaw B") + 0.02) < TOL
    s.joints_index = 1
    assert not bpy.ops.fresing.joint_value.poll()                  # CAD / Min / Max greyed out
    # poses keep only joints that move by themselves
    states.save_pose(scene, "Open")
    assert [v.joint for v in s.poses["Open"].joints] == ["Jaw A"]
    move(scene, "Jaw A", 0.0)
    states.apply_pose(scene, "Open")
    update()
    assert abs(V(scene, "Jaw A") - 0.02) < TOL and abs(V(scene, "Jaw B") + 0.02) < TOL
    # an old pose that still has the follower's value: ignored
    v = s.poses["Open"].joints.add()
    v.joint, v.value = "Jaw B", 0.3
    states.apply_pose(scene, "Open")
    update()
    assert abs(V(scene, "Jaw B") + 0.02) < TOL
    # animation steps on it: a warning, no keys
    a = s.animations.add()
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.use_from, b.to_dist = "JOINT", "Jaw B", 1.0, False, 0.05
    info = animation.bake(scene, a)
    assert any("move 'Jaw A' instead" in w for w in info["warnings"]), info
    assert J(scene, "Jaw B").motion.animation_data.action is None


def test_follower_limits_warn_but_do_not_stop_it(scene):
    jaws(scene)
    jb = J(scene, "Jaw B")
    jb.use_limits = True
    jb.slide_min, jb.slide_max = -0.01, 0.01
    move(scene, "Jaw A", 0.03)
    assert abs(V(scene, "Jaw B") + 0.03) < TOL, "a follower is never stopped by its limits"
    assert joints.outside_limits(jb, V(scene, "Jaw B"))
    move(scene, "Jaw A", 0.0)
    a = scene.fresing.animations.add()
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.use_from, b.to_dist = "JOINT", "Jaw A", 1.0, False, 0.03
    info = animation.bake(scene, a)
    assert any("'Jaw B' follows 'Jaw A' and goes beyond its own limits" in w for w in info["warnings"]), info
    animation.clear_keys(scene)
    b.to_dist = 0.005
    assert not animation.bake(scene, a)["warnings"]


def test_animation_moves_followers_with_their_leader(scene):
    """A Move joint step on the leader: the follower follows at every frame (drivers read the keys)."""
    jaws(scene)
    a = scene.fresing.animations.add()
    a.fps = "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from, b.to_dist, b.easing = "JOINT", "Jaw A", 0, 2, False, 0.04, "LINEAR"
    animation.bake(scene, a)
    for f, expect in ((1, 0.0), (26, 0.02), (51, 0.04)):
        scene.frame_set(f)
        assert abs(V(scene, "Jaw A") - expect) < TOL and abs(V(scene, "Jaw B") + expect) < TOL, f


def test_structure_changes_in_the_cad_pose_with_an_offset(scene):
    """A follower with an offset is not at 0 when its leader is: joint changes still happen in the
    CAD pose (the coupling is muted meanwhile), so nothing jumps."""
    jaws(scene)
    J(scene, "Jaw B").couple_offset_dist = 0.01
    move(scene, "Jaw A", 0.02)
    b = ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG", 1)
    before = pos(b)
    with joints.cad_pose(scene):
        assert abs(V(scene, "Jaw B")) < 1e-9
        assert close(pos(b), before - Vector((-0.01, 0, 0)))          # the CAD place
    update()
    assert close(pos(b), before)
    # a structure change on the follower (new axis) keeps it where it is
    o, d = joints.axis_world(J(scene, "Jaw B"))
    joints.set_axis(scene, J(scene, "Jaw B"), o + Vector((0, 0, 0.05)), d)
    update()
    assert close(pos(b), before)
    assert joints.couplings_simple(scene)


def test_remove_rename_and_type_change(scene):
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley")
    joints.set_follows(scene, J(scene, "Wheel 2"), "Trolley", ratio=10.0)
    move(scene, "Trolley", 0.01)
    # rename the leader: the followers keep following it
    J(scene, "Trolley").name = "Carriage"
    assert J(scene, "Wheel 1").follows == "Carriage" and J(scene, "Wheel 2").follows == "Carriage"
    # the follower's type changes: its ratio starts again from the usual one of the new pair
    joints.set_kind(scene, J(scene, "Wheel 2"), "SLIDE")
    assert J(scene, "Wheel 2").couple_ratio == 1.0 and J(scene, "Wheel 2").follows == "Carriage"
    update()
    assert abs(V(scene, "Wheel 2") - 0.01) < TOL
    # remove the leader: followers move by themselves from now on, where they are
    w1 = V(scene, "Wheel 1")
    scene.fresing.joints_index = 0
    assert bpy.ops.fresing.joint_remove() == {"FINISHED"}
    assert "move by themselves" in scene.fresing.last_message
    j1 = J(scene, "Wheel 1")
    assert j1.follows == "" and joints._coupling_fcurve(j1) is None
    assert abs(V(scene, "Wheel 1") - w1) < TOL
    move(scene, "Wheel 1", 0.5)
    assert abs(V(scene, "Wheel 1") - 0.5) < TOL


def test_by_itself_again(scene):
    jaws(scene)
    move(scene, "Jaw A", 0.02)
    scene.fresing.joints_index = 1
    assert bpy.ops.fresing.joint_follow(mode="FREE") == {"FINISHED"}
    jb = J(scene, "Jaw B")
    assert jb.follows == "" and abs(V(scene, "Jaw B") + 0.02) < TOL   # it stays where it was
    move(scene, "Jaw A", 0.0)
    assert abs(V(scene, "Jaw B") + 0.02) < TOL
    assert bpy.ops.fresing.joint_value.poll()


# ---------------------------------------------------------------------------
# saved files, scripts disabled, model updates
# ---------------------------------------------------------------------------


def test_save_and_reopen(scene, tmp_path):
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=360.0 / (math.pi * 50))
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1", ratio=-1.0)
    path = str(tmp_path / "coupled.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    j1, j2 = J(sc, "Wheel 1"), J(sc, "Wheel 2")
    assert j1.follows == "Trolley" and j2.follows == "Wheel 1" and abs(j2.couple_ratio + 1) < 1e-9
    move(sc, "Trolley", 0.05)
    assert abs(V(sc, "Wheel 1") - 2.0) < 1e-4 and abs(V(sc, "Wheel 2") + 2.0) < 1e-4


def test_drivers_are_simple_expressions(scene):
    """Blender evaluates simple expressions without Python: the file still moves with
    'Auto Run Python Scripts' off. (tools/coupling_check_noscripts.py checks it in the real program.)"""
    jaws(scene)
    trolley_and_wheels(scene)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=2.2918311805232927)
    J(scene, "Wheel 1").couple_offset_angle = -0.25
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1", ratio=1e-7)
    for j in scene.fresing.joints:
        fc = joints._coupling_fcurve(j)
        if j.follows:
            assert fc is not None and fc.driver.is_simple_expression, (j.name, fc.driver.expression)
            assert not fc.driver.use_self and fc.driver.type == "SCRIPTED"
        else:
            assert fc is None
    # the motion drivers of every joint stay plain AVERAGE (no expression at all)
    for j in scene.fresing.joints:
        drivers = [d for d in j.motion.animation_data.drivers if d.data_path != joints.COUPLING_PATH]
        assert drivers and all(d.driver.type == "AVERAGE" for d in drivers)
    assert joints.couplings_simple(scene)
    assert joints.expression(2.0, -0.1) == "a * 2.0 - 0.1" and joints.expression(-1.0, 0.0) == "a * -1.0"


def test_model_update_keeps_couplings_and_motor(scene):
    """Crane A -> B: couplings, the motor flag and the free joints' values come back."""
    trolley_and_wheels(scene)
    cover = ob(scene, "COVER")
    joints.create(scene, "ROTATE", [cover], pos(cover), X, name="Motor")
    joints.set_motor(scene, J(scene, "Motor"), True)
    joints.set_follows(scene, J(scene, "Trolley"), "Motor", ratio=50.0)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=360.0 / (math.pi * 50))
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1", ratio=-2.0)
    J(scene, "Wheel 2").couple_offset_angle = 0.5
    move(scene, "Motor", TURN)
    before = {j.name: joints.get_value(j) for j in scene.fresing.joints}
    names = [j.name for j in scene.fresing.joints]
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    s = scene.fresing
    assert [j.name for j in s.joints] == names and not len(s.report_notes), [n.text for n in s.report_notes]
    assert joints.is_motor(J(scene, "Motor"))
    assert [J(scene, n).follows for n in ("Trolley", "Wheel 1", "Wheel 2")] == ["Motor", "Trolley", "Wheel 1"]
    assert abs(J(scene, "Wheel 2").couple_offset_angle - 0.5) < 1e-6
    for n, v in before.items():
        assert abs(V(scene, n) - v) < 1e-4, n
    move(scene, "Motor", 2 * TURN)
    assert abs(V(scene, "Trolley") - 0.1) < TOL and abs(V(scene, "Wheel 2") - (-8.0 + 0.5)) < 1e-3
    assert joints.couplings_simple(scene)


def test_model_update_when_the_leader_is_gone(scene):
    """The leader's parts are not in the new revision: the follower moves by itself, with a note."""
    jaws(scene)
    specs = joints.dissolve_all(scene)
    assert specs[1]["follows"] == "Jaw A" and specs[1]["ratio"] == -1.0
    by_uid = {o.get(build.PROP_UID): o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS}
    del by_uid[ob(scene, "ISO 4017 M12 x 40 - 8.8 HDG", 0).get(build.PROP_UID)]
    notes = joints.rebuild_from_specs(scene, specs, by_uid)
    assert [j.name for j in scene.fresing.joints] == ["Jaw B"]
    assert J(scene, "Jaw B").follows == "" and any("moves by itself now" in n for n in notes), notes


def test_specs_from_an_older_version(scene):
    """Specs written before couplings (no 'follows', 'motor'...) rebuild as before."""
    jaws(scene)
    specs = joints.dissolve_all(scene)
    for sp in specs:
        for k in ("follows", "ratio", "offset_angle", "offset_dist", "motor"):
            del sp[k]
    by_uid = {o.get(build.PROP_UID): o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS}
    assert joints.rebuild_from_specs(scene, specs, by_uid) == []
    assert all(not j.follows and not j.is_motor for j in scene.fresing.joints)


# ---------------------------------------------------------------------------
# motors and Run motor
# ---------------------------------------------------------------------------


def motor_setup(sc):
    pin = ob(sc, "BOOM.PIN")
    joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], pos(pin), Y, name="Drum")
    joints.set_motor(sc, J(sc, "Drum"), True)
    a = sc.fresing.animations.add()
    a.name, a.fps = "Run", "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.speed_rpm = "MOTOR", "Drum", 0.0, 5.0, 12.0
    return a, b


def test_motor_turns_without_end(scene):
    pin = ob(scene, "BOOM.PIN")
    joints.create(scene, "ROTATE", [ob(scene, "BOOM.ASM")], pos(pin), Y, name="Drum")
    j = J(scene, "Drum")
    j.use_limits = True
    joints.set_motor(scene, j, True)
    assert not j.use_limits and joints.limits(j)[1] >= 1000 * TURN
    move(scene, "Drum", 25 * TURN)                       # far past the ±10 turns of a plain rotate joint
    assert abs(V(scene, "Drum") - 25 * TURN) < 1e-4
    joints.create(scene, "SLIDE", [ob(scene, "COVER")], (0, 0, 0), X, name="S")
    with pytest.raises(RuntimeError, match="Only a rotate joint"):
        joints.set_motor(scene, J(scene, "S"), True)
    joints.set_kind(scene, J(scene, "Drum"), "SLIDE")      # a slide is never a motor
    assert not J(scene, "Drum").is_motor


def test_run_motor_12_rpm_for_5_s_is_one_turn(scene):
    a, b = motor_setup(scene)
    b.easing = "LINEAR"                                   # constant speed, no ramps
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    assert abs(animation.motor_total(J(scene, "Drum"), b) - TURN) < 1e-9
    for f, turns in ((1, 0.0), (26, 0.2), (63, 0.496), (126, 1.0)):
        scene.frame_set(f)
        assert abs(V(scene, "Drum") / TURN - turns) < 1e-5, f
    scene.frame_set(140)                                  # it stays after the step
    assert abs(V(scene, "Drum") / TURN - 1.0) < 1e-5


def test_run_motor_with_ramps(scene):
    """1 s ramps: the speed rises evenly, stays, falls. Total = 12 rpm × (5 - 1) s = 0.8 turn;
    after 0.48 s of the ramp: 0.2 turn/s × 0.48² / (2 × 1) = 0.02304 turn."""
    a, b = motor_setup(scene)
    b.easing, b.ramp = "SMOOTH", 1.0
    animation.bake(scene, a)
    expect = {1: 0.0, 13: 0.02304, 26: 0.1, 76: 0.5, 114: 0.8 - 0.2 * 0.48 ** 2 / 2, 126: 0.8}
    for f, turns in expect.items():
        scene.frame_set(f)
        assert abs(V(scene, "Drum") / TURN - turns) < 1e-5, (f, V(scene, "Drum") / TURN, turns)
    # only a slow start: (5 - 0.5) × 0.2 = 0.9 turn; only a slow stop: the same
    for easing in ("EASE_IN", "EASE_OUT"):
        b.easing = easing
        assert abs(animation.motor_total(J(scene, "Drum"), b) / TURN - 0.9) < 1e-9
    # ramps longer than the step: shrunk to fit, the motor just speeds up and slows down
    b.easing, b.ramp, b.duration = "SMOOTH", 4.0, 2.0
    assert animation.motor_ramps(b) == (1.0, 1.0)
    assert abs(animation.motor_total(J(scene, "Drum"), b) / TURN - 0.2) < 1e-9


def test_run_motor_moves_its_followers_and_backwards(scene):
    """Winch: the drum turns 1 turn at -12 rpm... the rope (slide) pays out 300 mm per turn."""
    a, b = motor_setup(scene)
    b.easing, b.speed_rpm = "LINEAR", -12.0
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], pos(tr), X, name="Rope")
    joints.set_follows(scene, J(scene, "Rope"), "Drum", ratio=300.0)
    animation.bake(scene, a)
    scene.frame_set(126)
    assert abs(V(scene, "Drum") + TURN) < 1e-5 and abs(V(scene, "Rope") + 0.3) < 1e-5


def test_run_motor_slide_and_limits(scene):
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], pos(tr), X, name="Conveyor")
    j = J(scene, "Conveyor")
    j.use_limits, j.slide_min, j.slide_max = True, 0.0, 0.2
    a = scene.fresing.animations.add()
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.speed_mms, b.easing = "MOTOR", "Conveyor", 2.0, 50.0, "LINEAR"
    assert abs(animation.motor_total(j, b) - 0.1) < 1e-9
    assert not animation.bake(scene, a)["warnings"]
    scene.frame_set(1 + 50)
    assert abs(V(scene, "Conveyor") - 0.1) < 1e-5
    animation.clear_keys(scene)
    b.duration = 6.0                                       # 300 mm: stops at its 200 mm limit
    info = animation.bake(scene, a)
    assert any("reaches its limit" in w for w in info["warnings"]), info
    scene.frame_set(1 + 75)                                # 3 s: 150 mm, still on its way
    assert abs(V(scene, "Conveyor") - 0.15) < 1e-5
    scene.frame_set(1 + 110)                               # 4.4 s: stopped at 200 mm since 4 s
    assert abs(V(scene, "Conveyor") - 0.2) < 1e-5
    scene.frame_set(1 + 150)
    assert abs(V(scene, "Conveyor") - 0.2) < 1e-5
    # a plain rotate joint says how to let it turn without end
    animation.clear_keys(scene)
    pin = ob(scene, "BOOM.PIN")
    joints.create(scene, "ROTATE", [ob(scene, "BOOM.ASM")], pos(pin), Y, name="Arm")
    b.joint, b.speed_rpm, b.duration = "Arm", 600.0, 2.0      # 20 turns: more than the ±10 turns of a plain joint
    info = animation.bake(scene, a)
    assert any("tick 'Motor'" in w for w in info["warnings"]), info


def test_run_motor_step_added_from_the_menu(scene):
    pin = ob(scene, "BOOM.PIN")
    joints.create(scene, "ROTATE", [ob(scene, "BOOM.ASM")], pos(pin), Y, name="Drum")
    joints.create(scene, "SLIDE", [ob(scene, "COVER")], (0, 0, 0), X, name="Plain")
    joints.set_motor(scene, J(scene, "Drum"), True)
    scene.fresing.joints_index = 1                          # the selected joint is not a motor: the motor is used
    assert bpy.ops.fresing.block_add(kind="MOTOR") == {"FINISHED"}
    a = animation.active(scene)
    b = a.blocks[-1]
    assert b.kind == "MOTOR" and b.joint == "Drum" and b.duration == 5.0 and b.speed_rpm == 12.0
    assert animation.block_label(b) == "Run Drum"


def test_run_motor_survives_save_and_queue_style_reopen(scene, tmp_path):
    """The background render opens the saved project and plays the keys: the drum and its follower
    are where they should be at the last frame."""
    a, b = motor_setup(scene)
    b.easing = "LINEAR"
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], pos(tr), X, name="Rope")
    joints.set_follows(scene, J(scene, "Rope"), "Drum", ratio=300.0)
    animation.bake(scene, a)
    path = str(tmp_path / "motor.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    sc.frame_set(126)
    assert abs(V(sc, "Drum") - TURN) < 1e-5 and abs(V(sc, "Rope") - 0.3) < 1e-5


# ---------------------------------------------------------------------------
# panels
# ---------------------------------------------------------------------------


def _texts(draw_fn, *args):
    from test_blender import FakeLayout
    icons = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys()
    texts, errors = [], []

    class FL(FakeLayout):
        def label(self, *a, text="", icon="NONE", **k):
            texts.append(text)
            if icon not in icons:
                errors.append(f"unknown icon {icon}")

        def operator(self, idname, *a, text="", icon="NONE", **k):
            texts.append(text)
            if icon not in icons:
                errors.append(f"unknown icon {icon}")
            return super().operator(idname, *a, **k)

        def prop(self, data, name, *a, text=None, icon="NONE", **k):
            if text:
                texts.append(text)
            if icon not in icons:
                errors.append(f"unknown icon {icon}")
            if name.startswith('["'):
                return
            super().prop(data, name, *a, **k)

        def prop_search(self, data, name, *a, text=None, icon="NONE", **k):
            if text:
                texts.append(text)
            if icon not in icons:
                errors.append(f"unknown icon {icon}")
            assert hasattr(data, name), name

        def _child(self, *a, **k):
            return FL(self.errors)

        row = column = box = split = _child

        def panel(self, idname, default_closed=False):
            return FL(self.errors), FL(self.errors)

    fake = type("P", (), {"layout": FL(errors)})()
    draw_fn(fake, *args)
    assert not errors, errors
    return " ".join(texts)


def test_motion_panel_shows_couplings_and_motors(scene):
    from fresing_render.blender import ui_motion
    trolley_and_wheels(scene)
    cover = ob(scene, "COVER")
    joints.create(scene, "ROTATE", [cover], pos(cover), X, name="Motor")
    joints.set_motor(scene, J(scene, "Motor"), True)
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley")
    s = scene.fresing
    s.joints_index = 1                                          # Wheel 1: follows the trolley
    text = _texts(ui_motion.FRESING_PT_motion.draw, bpy.context)
    assert "Follows a joint" in text and "By itself" in text and "Ratio" in text
    assert "° per mm of 'Trolley'" in text and "a wheel of Ø100.0 mm" in text, text
    assert "CAD (0)" not in text, "a follower has no CAD/Min/Max buttons"
    s.joints_index = 0                                          # the trolley drives it
    assert "Drives 'Wheel 1'" in _texts(ui_motion.FRESING_PT_motion.draw, bpy.context)
    s.joints_index = 3                                          # the motor: turns, no limits
    joints.set_value(J(scene, "Motor"), 2.5 * TURN)
    text = _texts(ui_motion.FRESING_PT_motion.draw, bpy.context)
    assert "= 2.50 turns" in text and "Limits" not in text, text
    # a refused choice shows why, under the field
    s.joints_index = 0
    J(scene, "Trolley").follows = "Wheel 1"
    assert "cannot follow each other" in _texts(ui_motion.FRESING_PT_motion.draw, bpy.context)
    for item in s.joints:
        _texts(lambda p, it: ui_motion.FRESING_UL_joints.draw_item(None, bpy.context, p.layout, s, it, 0, s, "", 0),
               item)


def test_animation_panel_shows_the_motor_step(scene):
    from fresing_render.blender import ui_motion
    a, b = motor_setup(scene)
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], pos(tr), X, name="Rope")
    joints.set_follows(scene, J(scene, "Rope"), "Drum", ratio=300.0)
    s = scene.fresing
    s.animations_index = 0
    b.easing, b.ramp = "LINEAR", 0.5
    text = _texts(ui_motion.FRESING_PT_animation.draw, bpy.context)
    assert "Speed (rpm)" in text and "1.00 turns in this step" in text and "1 joint follows it" in text, text
    assert "Ramp (s)" not in text
    b.easing = "SMOOTH"
    assert "Ramp (s)" in _texts(ui_motion.FRESING_PT_animation.draw, bpy.context)
    b.joint = "Rope"                                              # a follower: say which joint to run instead
    assert "pick 'Drum' here instead" in _texts(ui_motion.FRESING_PT_animation.draw, bpy.context)
