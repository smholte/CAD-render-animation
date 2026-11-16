"""People walk, carry and meet (task 0157) and the person's rig (shared with 0156).

Pure Python: paths (length, smoothed corners, the surface below), gaits (speed = step x steps per second), feet that
stand without sliding and never sink, waits between people, paired greetings, carry grips that the hands reach.
In Blender (bpy module): the rig follows the core's bones, the owner's example builds (order, meeting time, feet, the
box on the floor), Clear keys puts everyone back, a project without people builds as before.
"""

import math
import os

import numpy as np
import pytest

from fresing_render.core import people as PE
from fresing_render.core import person_rig as R


def _world(root, v):
    x, y, z, h = root
    c, s = math.cos(h), math.sin(h)
    return np.array((c * v[0] - s * v[1] + x, s * v[0] + c * v[1] + y, v[2] + z))


def _walker(gait="WALK", path=((0.0, -4.0), (3.0, -6.0), (3.0, -9.0)), ground=None, height=1.75):
    a = PE.PersonSpec("A", height, (0.0, 0.0, 0.0), 0.0, path=path, actions=(PE.Action("WALK", "END", gait=gait),))
    return PE.plan([a], [], ground)


def _contacts(pl, name, fps=50):
    """Per plant: the world positions of its contact point (heel while the heel rolls, ball area while flat, toe tip
    while the toe rolls) over the frames it stands."""
    person = pl.people[name]
    fig = person.fig
    rows = pl.sample(fps)[name]
    out = []
    for side in "lr":
        for p in person.feet[side].plants:
            pts = {"heel": [], "flat": [], "toe": []}
            for f, (root, pose) in enumerate(rows):
                t = f / fps
                if not p.down <= t <= p.up:
                    continue
                sp = fig.sole_points(pose, side)
                if p.roll_in and t < p.down + p.roll_in:
                    pts["heel"].append(_world(root, sp["heel"]))
                elif p.roll_out and t > p.up - p.roll_out:
                    pts["toe"].append(_world(root, sp["toe"]))
                else:
                    pts["flat"].append(_world(root, sp["ball"]))
            out.append(pts)
    return out, rows, fig


# ---------------------------------------------------------------------------
# paths and gaits
# ---------------------------------------------------------------------------


def test_path_length_and_rounded_corners():
    straight = PE.Path([(0, 0), (4, 0)])
    assert abs(straight.length - 4.0) < 1e-9
    corner = PE.Path([(0, 0), (4, 0), (4, 4)])
    assert 7.0 < corner.length < 8.0, "the corner is cut a little"
    assert np.allclose(corner.at(0.0), (0, 0)) and np.allclose(corner.at(corner.length), (4, 4)), "ends kept"
    assert corner.turn_at(corner.length / 2) < 1 / 0.3, "no sharp kink"


@pytest.mark.parametrize("gait", list(PE.GAITS))
def test_gait_speed_and_step_length_go_together(gait):
    pl = _walker(gait, path=((0.0, -12.0),))
    g = PE.GAITS[gait]
    walk = next(s for s in pl.people["A"].segs if s.kind == "WALK")
    m, f = walk.data["m"], walk.data["f"]
    step = 12.0 / m
    assert abs(step * f - g.speed) < 1e-9, "speed = step length x steps per second"
    assert abs(step - g.step * pl.people["A"].fig.k) <= 0.5 * g.step, "the step fits the gait"
    steady = 12.0 / ((walk.t1 - walk.t0) - 1.0 / f)       # the first and last half step speed up / slow down
    assert abs(steady - g.speed) / g.speed < 0.12


@pytest.mark.parametrize("gait", ["STROLL", "WALK", "BRISK", "RUN"])
def test_feet_stand_without_sliding_and_never_sink(gait):
    pl = _walker(gait)
    plants, rows, fig = _contacts(pl, "A")
    for pts in plants:
        for kind, ps in pts.items():
            if len(ps) > 1:
                d = np.linalg.norm(np.asarray(ps) - ps[0], axis=1).max()
                assert d < 0.003, f"{kind} contact slides {d * 1000:.1f} mm"
    low = min(_world(root, p)[2] for root, pose in rows for s in "lr" for p in fig.sole_points(pose, s).values())
    assert low > -0.003, f"a sole sinks {-low * 1000:.1f} mm into the floor"


def test_feet_follow_a_slope():
    ground = lambda x, y, z=None: 0.08 * -y                 # rises 8 % along the walk (-y)
    pl = _walker("WALK", path=((0.0, -6.0),), ground=ground)
    plants, _rows, _fig = _contacts(pl, "A")
    for pts in plants:
        for p in pts["flat"]:
            assert abs(p[2] - ground(p[0], p[1])) < 0.02, "the flat foot stands on the slope"
    assert not pl.warnings


def test_a_jump_in_the_floor_is_warned():
    ground = lambda x, y, z=None: 0.5 if y < -3 else 0.0
    pl = _walker("WALK", path=((0.0, -6.0),), ground=ground)
    assert any("jumps" in w for w in pl.warnings)


# ---------------------------------------------------------------------------
# the schedule: waits and meetings
# ---------------------------------------------------------------------------


def _example():
    anna = PE.PersonSpec("Anna", 1.65, (0.0, 6.0, 0.0), 0.0, path=((0.0, 3.0), (1.4, 1.2)), carry="Box",
                         actions=(PE.Action("WALK", "END"), PE.Action("PUT_DOWN"), PE.Action("GREET", other="Ben"),
                                  PE.Action("TALK", other="Ben", duration=6)))
    ben = PE.PersonSpec("Ben", 1.85, (2.2, 1.2, 0.0), math.radians(90),
                        actions=(PE.Action("IDLE", duration=1.0), PE.Action("GREET", other="Anna"),
                                 PE.Action("TALK", other="Anna", duration=6)))
    return PE.plan([anna, ben], [PE.ItemSpec("Box", "TOOLBOX", (0, 6, 0))])


def test_the_example_lines_up():
    pl = _example()
    assert not pl.warnings
    a, b = pl.people["Anna"], pl.people["Ben"]
    order = [s.kind for s in a.segs if s.kind in ("WALK", "PUT_DOWN", "HANDSHAKE", "TALK")]
    assert order == ["WALK", "PUT_DOWN", "HANDSHAKE", "TALK"]
    ha = next(s for s in a.segs if s.kind == "HANDSHAKE")
    hb = next(s for s in b.segs if s.kind == "HANDSHAKE")
    assert abs(ha.t0 - hb.t0) < 1e-6, "they shake hands together"
    put = next(s for s in a.segs if s.kind == "PUT_DOWN")
    assert ha.t0 >= put.t1, "Ben waits until Anna has put the box down"
    assert any(s.kind == "WAIT" for s in b.segs), "Ben waits for Anna"
    states = pl.item_states["Box"]
    assert [s.state for s in states] == ["PLACED", "HELD", "PLACED"]
    world = states[-1].world
    assert abs(world[2, 3]) < 1e-9, "the box is put on the floor"
    anna_at = a.root(put.t1)
    assert 0.3 < math.hypot(world[0, 3] - anna_at[0], world[1, 3] - anna_at[1]) < 0.9, "in front of her"


def test_handshake_hands_meet():
    pl = _example()
    rows = pl.sample(25)
    ha = next(s for s in pl.people["Anna"].segs if s.kind == "HANDSHAKE")
    f = int((ha.t0 + 1.0) * 25)
    palms = []
    for name in ("Anna", "Ben"):
        root, pose = rows[name][f]
        p, _R = pl.people[name].fig.palm(pose, "r")
        palms.append(_world(root, p))
    assert np.linalg.norm(palms[0] - palms[1]) < 0.06, "the right hands meet"


def test_wait_for_another_persons_step():
    a = PE.PersonSpec("A", actions=(PE.Action("STOP", duration=3.0), PE.Action("WAVE")))
    b = PE.PersonSpec("B", place=(3, 0, 0), actions=(PE.Action("WAVE", wait_person="A", wait_step=1),))
    pl = PE.plan([a, b])
    wave = next(s for s in pl.people["B"].segs if s.kind == "WAVE")
    assert abs(wave.t0 - 3.0) < 1e-6


def test_a_circle_of_waits_is_warned_not_hung():
    a = PE.PersonSpec("A", actions=(PE.Action("WAVE", wait_person="B", wait_step=1),))
    b = PE.PersonSpec("B", place=(3, 0, 0), actions=(PE.Action("WAVE", wait_person="A", wait_step=1),))
    pl = PE.plan([a, b])
    assert any("circle" in w for w in pl.warnings)


def test_greeting_without_answer_is_a_wave():
    a = PE.PersonSpec("A", actions=(PE.Action("GREET", other="B"),))
    b = PE.PersonSpec("B", place=(0.8, 0, 0), actions=(PE.Action("STOP"),))
    pl = PE.plan([a, b])
    assert [s.kind for s in pl.people["A"].segs if s.kind in ("WAVE", "HANDSHAKE")] == ["WAVE"]


# ---------------------------------------------------------------------------
# carry grips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(PE.ITEMS))
def test_every_item_is_carried_with_the_hands_on_it(kind):
    a = PE.PersonSpec("A", path=((0.0, -4.0),), carry="it", actions=(PE.Action("WALK", "END", gait="WALK"),))
    pl = PE.plan([a], [PE.ItemSpec("it", kind, (0.0, 1.0, 0.0))])
    person = pl.people["A"]
    fig = person.fig
    rows = pl.sample(25)["A"]
    root, pose = rows[len(rows) // 2]
    fk = fig.fk(pose)
    held = pl.item_states["it"][-1]
    hand = fk[f"{held.side}_hand"]
    item = PE.m4(hand[1], hand[0]) @ held.grip
    for side in PE.holding_hands(kind):            # every holding hand is where the item's grip wants it
        want = item @ PE.hand_in_item(kind, side, fig.k)
        got = fk[f"{side}_hand"][0]
        assert np.linalg.norm(want[:3, 3] - got) < 0.01, f"{side} hand {np.linalg.norm(want[:3, 3] - got):.3f} m off"
    pts = np.array([p for sh in PE.item_shapes(kind) for p in __import__(
        "fresing_render.core.props_detail", fromlist=["x"])._points(sh)])
    low = (item[:3, :3] @ pts.T).T[:, 2].min() + item[2, 3]
    assert low > 0.03, "the item is carried clear of the floor"


def test_rig_rest_pose_is_the_identity_and_ik_reaches():
    fig = R.Figure(1.85)
    pose = fig.rest()
    for b in R.BONES:
        assert np.allclose(fig.blender_quaternion(pose, b), (1, 0, 0, 0), atol=1e-9)
    w = fig.shoulder(pose, "r") + np.array((-0.1, -0.35, -0.2))
    assert fig.arm_ik(pose, "r", w) < 1e-9
    assert np.linalg.norm(fig.fk(pose)["r_hand"][0] - w) < 1e-9


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def _crane(bpy):
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def test_the_rig_follows_the_core_bones(blender):
    bpy = blender
    from fresing_render.blender import person_rig, surroundings
    sc = _crane(bpy)
    ob = surroundings.add_prop(sc, "PERSON")
    ob.location = (2.0, 3.0, surroundings.floor_height(sc))
    ob.rotation_euler.z = 0.4
    person_rig.ensure(ob)
    fig = person_rig.figure(ob)
    pose = fig.from_angles("WALKING")
    fig.arm_ik(pose, "l", fig.shoulder(pose, "l") + np.array((0.15, -0.3, -0.15)))
    person_rig.set_pose(ob, pose)
    bpy.context.view_layer.update()
    M = np.asarray(ob.matrix_world)
    fk = fig.fk(pose)
    for b in ("pelvis", "l_hand", "r_foot", "head"):
        want = M[:3, :3] @ fk[b][0] + M[:3, 3]
        got = np.asarray(person_rig.bone_world(ob, b).translation)
        assert np.linalg.norm(want - got) < 1e-4, b
    ob.fresing_person.pose = "POINTING"                  # the pose setting goes to the bones, the mesh stays
    me = ob.data
    assert person_rig.rig_of(ob) is not None and ob.data == me


def test_the_example_builds_and_clears(blender):
    bpy = blender
    from fresing_render.blender import animation, clash, people
    sc = _crane(bpy)
    anna, ben, box = people.set_up_example(sc)
    before = {o.name: (tuple(o.location), o.rotation_euler.z) for o in (anna, ben)}
    box_before = tuple(box.location)
    bpy.ops.fresing.anim_add()
    a = animation.active(sc)
    assert animation.length_seconds(a) >= people.length(sc) > 10.0
    res = animation.bake(sc, a)
    assert not res["warnings"], res["warnings"]
    words = people.check_example(sc)
    assert "shake hands" in words
    names = {o.name for o in clash.objects(sc)}
    assert {"Anna", "Ben"} <= names and box.name not in names
    animation.clear_keys(sc)
    for o in (anna, ben):
        assert np.allclose(tuple(o.location), before[o.name][0], atol=1e-6)
        assert abs(o.rotation_euler.z - before[o.name][1]) < 1e-6
        assert o.animation_data is None or o.animation_data.action is None
    assert np.allclose(tuple(box.location), box_before, atol=1e-6)


def test_a_project_without_people_is_unchanged(blender):
    bpy = blender
    from fresing_render.blender import animation, people
    sc = _crane(bpy)
    n = len(bpy.data.objects)
    bpy.ops.fresing.anim_add()
    a = animation.active(sc)
    assert people.length(sc) == 0.0 and animation.length_seconds(a) == 1.0
    animation.bake(sc, a)
    assert len(bpy.data.objects) - n <= 1, "nothing for people is made (only the animation camera may come)"
    assert bpy.data.collections.get(people.COLLECTION) is None
