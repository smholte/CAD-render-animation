"""Task 0129, independent tests (written by a tester who did not write the code, from the brief and the docstrings).

Core first (no Blender), then the frame model (tests/data/test_sequence_frame.step): a portal frame (outside the
subassembly) over SLIDE.UNIT (rail block, cover, 2 bolts, carriage, gripper block, split pin).
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from fresing_render.core import sequence as core

HERE = os.path.dirname(__file__)
FRAME = os.path.join(HERE, "data", "test_sequence_frame.step")
MM = 1e-3
TOL = 0.01 * MM


def box(name, lo, hi, fastener=False, index=0):
    lo, hi = np.array(lo, float), np.array(hi, float)
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    return core.Part(name, c, fastener, index)


def _boxes_overlap(a, b, eps=1e-9):
    return bool(np.all(a.max(axis=0) > b.min(axis=0) + eps) and np.all(b.max(axis=0) > a.min(axis=0) + eps))


# ---------------------------------------------------------------------------
# core, no Blender
# ---------------------------------------------------------------------------

def _ring_round_a_middle_part():
    """A middle part that leaves first (tree order), parts round it on every side at different distances."""
    return [box("mid", (-1, -1, -1), (1, 1, 1), index=0),
            box("px", (2, -1, -1), (4, 1, 1), index=1),
            box("nx", (-8, -1, -1), (-6, 1, 1), index=2),
            box("py", (-1, 2, -1), (1, 4, 1), index=3),
            box("ny", (-1, -8, -1), (1, -6, 1), index=4),
            box("top", (-20, -20, 9), (20, 20, 10), index=5),
            box("bot", (-20, -20, -10), (20, 20, -9), index=6)]


def _enclosure(i, u, dist):
    """A housing round the middle part (outside the subassembly): room for 2 m in every way, none up."""
    if i != 0:
        return False
    return dist > 2.0 + 1e-9 or u[2] > 0.5


def test_last_round_change_keeps_travel_consistent_with_the_way():
    parts = _ring_round_a_middle_part()
    st = core.Settings(direction="CENTRE", by_size=False, distance=2.0, order="TREE",
                       frame=((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    moves = core.plan(parts, st, obstacle=_enclosure)
    by = {m.name: m for m in moves}
    rank = {m.name: m.rank for m in moves}
    ends = {p.name: np.asarray(p.corners) + by[p.name].offset for p in parts}
    starts = {p.name: np.asarray(p.corners) for p in parts}
    # the promise of core/sequence.py: a part ends beyond every part that leaves after it going nearly the same way
    # (no part ever flies through the place where an earlier one waits) - and never ends inside a part still in place
    for a in parts:
        for b in parts:
            if a is b or rank[a.name] > rank[b.name]:
                continue
            assert not _boxes_overlap(ends[a.name], starts[b.name]), (a.name, "ends inside", b.name, "still in place")
            if float(by[a.name].direction @ by[b.name].direction) >= core.NEAR:
                u = by[a.name].direction
                assert (ends[a.name] @ u).min() >= (ends[b.name] @ u).max() - 1e-9, (a.name, b.name)


def test_put_together_reverse_with_obstacle_and_every_setting():
    parts = [box("left", (-6, -2, 0), (-2, 2, 2), index=0), box("mid", (-1, -2, 0), (1, 2, 2), index=1),
             box("right", (2, -2, 0), (6, 2, 2), index=2), box("bolt", (-0.3, -0.3, 2), (0.3, 0.3, 3), True, 3)]

    def beam(i, u, dist):
        c = np.asarray(parts[i].corners)
        way = np.concatenate([c, c + np.asarray(u) * dist])
        lo, hi = way.min(axis=0) + 1e-4, way.max(axis=0) - 1e-4
        return bool(np.all(hi > np.array((-1.5, -10, 5))) and np.all(lo < np.array((1.5, 10, 6))))
    for by_size in (True, False):
        for d in ("UP", "CENTRE", "AXIS"):
            st = core.Settings(direction=d, by_size=by_size, distance=8.0, frame=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                               part_time=0.7, overlap=0.3)
            apart = core.plan(parts, st, obstacle=beam)
            again = core.plan(parts, st, obstacle=beam)
            assert [(m.name, m.rank, tuple(m.offset), m.t0) for m in apart] == \
                   [(m.name, m.rank, tuple(m.offset), m.t0) for m in again]          # deterministic
            st.put_together = True
            tog = {m.name: m for m in core.plan(parts, st, obstacle=beam)}
            total = core.duration(len(parts), 0.7, 0.3)
            for m in apart:
                t = tog[m.name]
                assert np.allclose(m.offset, t.offset) and m.rank == t.rank, (by_size, d, m.name)
                assert t.t0 == pytest.approx(total - m.t1) and t.t1 == pytest.approx(total - m.t0)
                if d != "CENTRE":
                    assert not beam(parts.index(next(p for p in parts if p.name == m.name)), m.direction,
                                    m.distance), (by_size, d, m.name)


def test_every_way_blocked_keeps_the_wanted_way_and_the_stacking():
    parts = _ring_round_a_middle_part()
    st = core.Settings(direction="AXIS", axis=(0, 0, 1), by_size=False, distance=3.0,
                       frame=((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    plain = core.plan(parts, st)
    caged = core.plan(parts, st, obstacle=lambda i, u, d: True)
    assert [(m.name, m.rank, tuple(np.round(m.offset, 9))) for m in plain] == \
           [(m.name, m.rank, tuple(np.round(m.offset, 9))) for m in caged]


def test_order_with_carried_and_blocked_together_nested_riders():
    """A rider of a rider: the block rides on the carriage, which rides on the rail; the rail's floor blocks nothing,
    but a blocked() test says the carriage cannot leave while the cover is in place."""
    parts = [box("rail", (-15, -6, 0), (15, 6, 4), index=0),
             box("cover", (-14, -5, 4), (-6, 5, 5), index=1),
             box("carriage", (-4, -5, 4), (4, 5, 8), index=2),
             box("block", (-2, -3, 8), (2, 3, 12), index=3),
             box("bolt", (-10.4, -0.4, 5), (-9.6, 0.4, 6), True, 4)]
    carried = {0: [2, 3], 2: [3]}
    for order in ("OUTSIDE_IN", "TREE", "REVERSE"):
        st = core.Settings(direction="UP", order=order)
        moves = core.plan(parts, st, blocked=lambda i, j: (i, j) == (2, 1), carried=carried)
        rank = {m.name: m.rank for m in moves}
        assert rank["block"] < rank["carriage"] < rank["rail"], (order, rank)
        assert sorted(rank.values()) == list(range(5))
    # a carrier whose rider is not among the parts (index out of the map) does not wait for it
    moves = core.plan(parts, core.Settings(direction="UP"), carried={0: [7]})
    assert len(moves) == 5


# ---------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, joints, sequence, states  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def fr(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=FRAME, quality="draft") == {"FINISHED"}
    return sc


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def unit(sc):
    return named(sc, "SLIDE.UNIT")


def rig(sc):
    rail, car, blk = named(sc, "RAIL BLOCK"), named(sc, "CARRIAGE"), named(sc, "GRIPPER BLOCK")
    slide = joints.create(sc, "SLIDE", [car], Vector((0, 0, 0.04)), Vector((1, 0, 0)), name="Carriage", base=rail)
    lift = joints.create(sc, "SLIDE", [blk], Vector((0, 0, 0.08)), Vector((0, 0, 1)), name="Lift", base=car)
    return slide, lift


def add_anim(sc, name="Seq"):
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = name, 0.0, "25"
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return a


def add_seq(sc, a, start=0.0, **kw):
    b = a.blocks.add()
    b.kind = "SEQUENCE"
    u = unit(sc)
    b.target_uid, b.target_name = u[build.PROP_UID], u[build.PROP_NAME]
    b.start = start
    b.seq_id = f"i{len(a.blocks)}"
    b.seq_direction = "UP"
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return b


def add_joint_step(a, j, start=0.0, to=0.05, dur=1.0):
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", j.name, start, dur, True
    s.to_dist = to
    return s


def add_cad(a, start, dur=1.0, sub=None):
    c = a.blocks.add()
    c.kind, c.start, c.duration = "CAD", start, dur
    if sub is not None:
        c.cad_whole = False
        c.target_uid, c.target_name = sub[build.PROP_UID], sub[build.PROP_NAME]
    return c


def worlds(sc, parts, frame):
    sc.frame_set(frame)
    return {o.name: o.matrix_world.copy() for o in parts}


def maxdiff(m1, m2):
    return max(abs(x) for r in (m1 - m2) for x in r)


def all_keys(objs):
    out = {}
    for o in objs:
        ad = o.animation_data
        if ad is None or ad.action is None:
            out[o.name] = None
            continue
        cb = animation._channelbag(o, "OBJECT")
        out[o.name] = [(fc.data_path, fc.array_index, tuple((round(k.co[0], 6), round(k.co[1], 9))
                                                             for k in fc.keyframe_points)) for fc in cb.fcurves]
    return out


# --- the blocked-way test against parts outside the subassembly --------------------------------------------------

def test_obstacle_answers_for_the_asked_distance(fr):
    sc = fr
    parts = sequence.movers(sc, unit(sc)).parts
    blk = named(sc, "GRIPPER BLOCK")                      # top at z 120 mm, the beam's underside at z 150 mm
    i = parts.index(blk)
    obs = sequence.Obstacles(sc, unit(sc), parts)
    assert obs(i, (0.0, 0.0, 1.0), 0.040)                 # 10 mm into the beam: blocked
    obs = sequence.Obstacles(sc, unit(sc), parts)
    assert not obs(i, (0.0, 0.0, 1.0), 0.024)             # 6 mm below: clear (0.024 x 1.2 < 0.030)
    obs = sequence.Obstacles(sc, unit(sc), parts)
    assert not obs(i, (0.0, 0.0, 1.0), 0.028)             # ends 2 mm below the beam: clear


def test_obstacle_answers_do_not_depend_on_what_was_asked_before(fr):
    sc = fr
    parts = sequence.movers(sc, unit(sc)).parts
    i = parts.index(named(sc, "GRIPPER BLOCK"))
    up = (0.0, 0.0, 1.0)
    fresh = {d: sequence.Obstacles(sc, unit(sc), parts)(i, up, d) for d in (0.01, 0.02, 0.025, 0.04, 0.2)}
    obs = sequence.Obstacles(sc, unit(sc), parts)
    for d in (0.2, 0.04, 0.025, 0.02, 0.01):
        assert obs(i, up, d) == fresh[d], d
    obs = sequence.Obstacles(sc, unit(sc), parts)
    for d in (0.01, 0.02, 0.025, 0.04, 0.2):
        assert obs(i, up, d) == fresh[d], d


def test_sliding_along_the_base_plate_is_not_blocked(fr):
    """The rail block sits on the base plate (outside the subassembly): sliding along it touches only."""
    sc = fr
    parts = sequence.movers(sc, unit(sc)).parts
    i = parts.index(named(sc, "RAIL BLOCK"))
    obs = sequence.Obstacles(sc, unit(sc), parts)
    assert not obs(i, (0.0, 1.0, 0.0), 0.3)
    assert not obs(i, (0.0, -1.0, 0.0), 0.3)
    assert obs(i, (1.0, 0.0, 0.0), 0.3)                   # into the frame's post at x 170 mm
    assert obs(i, (0.0, 0.0, -1.0), 0.01)                 # down into the base plate


def test_frame_hidden_by_an_earlier_step_does_not_block(fr):
    sc = fr
    frame = named(sc, "PORTAL FRAME")
    a = add_anim(sc)
    h = a.blocks.add()
    h.kind, h.start = "HIDE", 0.0
    h.target_uid, h.target_name = frame[build.PROP_UID], frame[build.PROP_NAME]
    b = add_seq(sc, a, start=0.5)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    parts = sequence.movers(sc, unit(sc)).parts
    w0 = worlds(sc, parts, animation.frame_of(a, 0.5))
    w1 = worlds(sc, parts, sc.frame_end)
    for o in parts:
        d = w1[o.name].translation - w0[o.name].translation
        assert d.length > 0.01 and d.normalized().z > 1 - 1e-6, (o.get(build.PROP_NAME), tuple(d))
    assert b.duration > 0


def test_a_part_inside_a_closed_housing_warns_and_does_not_crash(fr):
    sc = fr
    u = unit(sc)
    parts = sequence.movers(sc, u).parts
    pts = np.concatenate([sequence.corners(o) for o in parts])
    lo, hi = pts.min(axis=0) - 0.02, pts.max(axis=0) + 0.02
    lo[2] = -0.05                                          # round the base plate too: closed on every side
    bpy.ops.mesh.primitive_cube_add()
    cage = bpy.context.active_object
    cage.name = "Housing"
    cage.location = tuple((lo + hi) / 2)
    cage.scale = tuple((hi - lo) / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cage[build.PROP_KIND] = "part"
    cage[build.PROP_NAME] = "HOUSING CAGE"
    bpy.context.view_layer.update()
    a = add_anim(sc)
    add_seq(sc, a, seq_by_size=False, seq_distance=0.5)
    info = animation.bake(sc, a)
    assert info["frames"] > 1
    assert any("HOUSING CAGE" in w and "outside the subassembly" in w for w in info["warnings"]), info["warnings"]


# --- riders -------------------------------------------------------------------------------------------------------

def _rider_anim(sc, **kw):
    slide, lift = rig(sc)
    a = add_anim(sc, "Riders")
    add_joint_step(a, slide, to=0.05)
    add_joint_step(a, lift, to=0.01)
    b = add_seq(sc, a, start=1.0, **kw)
    return a, b, slide, lift


@pytest.mark.parametrize("easing,overlap", [("LINEAR", 0.0), ("EASE_IN", 90.0), ("EASE_OUT", 50.0),
                                            ("SMOOTH", 90.0)])
def test_riders_on_their_straight_line_and_still_once_out(fr, easing, overlap):
    """Rider of a rider (gripper block on the carriage on the rail block): at every frame each part is on its own
    straight line from its carried place, and once out it stays where it flew while its carriers fly out under it."""
    sc = fr
    a, b, _s, _l = _rider_anim(sc, easing=easing, seq_overlap=overlap, seq_part_time=0.6)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    parts = sequence.movers(sc, unit(sc)).parts
    f_start = animation.frame_of(a, 1.0)
    w0 = worlds(sc, parts, f_start)
    w1 = worlds(sc, parts, sc.frame_end)
    track = {o.name: [] for o in parts}
    for f in range(f_start, sc.frame_end + 1):
        sc.frame_set(f)
        for o in parts:
            track[o.name].append(o.matrix_world.copy())
    for o in parts:
        name = o.get(build.PROP_NAME)
        way = w1[o.name].translation - w0[o.name].translation
        assert way.length > 0.02, name
        reached = False
        for k, m in enumerate(track[o.name]):
            d = m.translation - w0[o.name].translation
            assert d.cross(way).length < 1e-5 * way.length, (name, f_start + k)   # on its line
            assert -TOL <= d.dot(way.normalized()) <= way.length + TOL, (name, f_start + k)
            assert maxdiff(m.to_3x3(), w0[o.name].to_3x3()) < 1e-6, name                # it does not turn
            if (m.translation - w1[o.name].translation).length < TOL:
                reached = True
            elif reached:
                pytest.fail(f"{name} left its out place again at frame {f_start + k}")


def test_riders_put_together_after_take_apart_end_home_and_build_twice(fr):
    sc = fr
    a, b, slide, lift = _rider_anim(sc, seq_part_time=0.5, seq_end="HIDE")
    dur = b.duration                                       # (b is stale once another step is added)
    add_seq(sc, a, start=1.0 + dur + 0.4, seq_mode="TOGETHER", seq_part_time=0.5, seq_end="FADE")
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    parts = sequence.movers(sc, unit(sc)).parts
    at = worlds(sc, parts, animation.frame_of(a, 1.0))
    sc.frame_set(animation.frame_of(a, 1.0 + dur + 0.2))
    assert all(o.hide_render for o in parts)
    end = worlds(sc, parts, sc.frame_end)
    for o in parts:
        assert not o.hide_render
        assert maxdiff(end[o.name], at[o.name]) < TOL, o.get(build.PROP_NAME)
    assert joints.get_value(slide) == pytest.approx(0.05, abs=1e-6)
    first = all_keys(parts)
    animation.bake(sc, a)
    again = all_keys(parts)
    assert set(again) == set(first)
    for n in first:                                        # the same keys (float32 noise of 0.1 um allowed)
        assert [(c[0], c[1], [k[0] for k in c[2]]) for c in again[n]] == \
               [(c[0], c[1], [k[0] for k in c[2]]) for c in first[n]], n
        for c1, c2 in zip(first[n], again[n]):
            assert max(abs(x[1] - y[1]) for x, y in zip(c1[2], c2[2])) < 1e-7, (n, c1[0], c1[1])
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


def test_rider_whose_carrier_is_outside_the_subassembly(fr):
    """The gripper block on a joint whose base is the portal frame: its carrier is not a mover, so it flies as any
    part."""
    sc = fr
    blk, frame = named(sc, "GRIPPER BLOCK"), named(sc, "PORTAL FRAME")
    j = joints.create(sc, "SLIDE", [blk], Vector((0, 0, 0.1)), Vector((0, 1, 0)), name="On frame", base=frame)
    a = add_anim(sc)
    add_joint_step(a, j, to=0.0)
    b = add_seq(sc, a, start=0.2)
    m = sequence.movers(sc, unit(sc))
    assert blk.name not in m.carriers
    assert b.seq_riders == 0
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


# --- Back to CAD --------------------------------------------------------------------------------------------------

def test_back_to_cad_between_take_apart_and_put_together(fr):
    """Joints moved, the unit taken apart (riders too), Back to CAD, then put together: every part ends exactly at
    its CAD place, and after Back to CAD (before the put-together) every part is at its CAD place too."""
    sc = fr
    u = unit(sc)
    parts = sequence.movers(sc, u).parts
    cad = {o.name: o.matrix_world.copy() for o in parts}
    a, b, slide, lift = _rider_anim(sc, seq_part_time=0.5)
    c_start = 1.0 + b.duration + 0.2                       # (step items are stale once another is added)
    add_cad(a, c_start, 1.0)
    t_start = c_start + 1.2
    add_seq(sc, a, start=t_start, seq_mode="TOGETHER", seq_part_time=0.5)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    home = worlds(sc, parts, animation.frame_of(a, c_start + 1.0))
    for o in parts:
        assert maxdiff(home[o.name], cad[o.name]) < TOL, ("after Back to CAD", o.get(build.PROP_NAME))
    assert joints.get_value(slide) == pytest.approx(0.0, abs=1e-7)
    assert joints.get_value(lift) == pytest.approx(0.0, abs=1e-7)
    mid = worlds(sc, parts, animation.frame_of(a, t_start + 0.01))
    assert any((mid[o.name].translation - cad[o.name].translation).length > 0.02 for o in parts)   # out again
    end = worlds(sc, parts, sc.frame_end)
    for o in parts:
        assert maxdiff(end[o.name], cad[o.name]) < TOL, ("after Put together", o.get(build.PROP_NAME))
    # task 0132: right after the Take apart, Back to CAD plays it backwards (it flew every part home at once on
    # straight lines before: the bolts passed through the cover and the rail block, 4-7 mm)
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, r.frame_from, round(r.depth * 1000, 2)) for r in run.rows]


def test_back_to_cad_without_joints_brings_a_taken_apart_unit_home(fr):
    sc = fr
    parts = sequence.movers(sc, unit(sc)).parts
    cad = {o.name: o.matrix_world.copy() for o in parts}
    assert not len(sc.fresing.joints)
    a = add_anim(sc)
    b = add_seq(sc, a, seq_part_time=0.4)
    dur = b.duration
    add_cad(a, dur + 0.3, 0.8)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    out = worlds(sc, parts, animation.frame_of(a, dur + 0.1))
    assert all((out[n].translation - cad[n].translation).length > 0.02 for n in cad)
    end = worlds(sc, parts, sc.frame_end)
    for n in cad:
        assert maxdiff(end[n], cad[n]) < TOL, n
    # task 0132: right after a Take apart it is that Take apart backwards (the last part out comes in first), each
    # part on its own way out, and nothing flies through another part
    seq = next(x for x in a.blocks if x.kind == "SEQUENCE")
    rev = animation._Reversed(seq, dur + 0.3, 0.8)
    with sequence._WorldAt(sc, {}, {}):
        moves = sequence.plan_now(rev, unit(sc), parts, scene=sc)
    first_in = min(moves, key=lambda mv: mv.t0).name
    last_out = max(sequence.plan_now(seq, unit(sc), parts, scene=sc), key=lambda mv: mv.t0).name
    assert first_in == last_out
    f_in = animation.frame_of(a, dur + 0.3 + 0.8 * 0.2)
    sc.frame_set(f_in)
    by = {o.name: o for o in parts}
    assert (by[first_in].matrix_world.translation - out[first_in].translation).length > 1e-4    # on its way in
    for n in cad:
        if n != first_in and (out[n].translation - cad[n].translation).length > 0.02:
            way = out[n].translation - cad[n].translation
            for f in range(animation.frame_of(a, dur + 0.3), sc.frame_end + 1, 2):
                sc.frame_set(f)
                d = by[n].matrix_world.translation - cad[n].translation
                assert d.cross(way).length < 1e-5 * way.length, (n, f)              # on its own line
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, r.frame_from, round(r.depth * 1000, 2)) for r in run.rows]


def test_back_to_cad_alone_on_a_model_at_cad_does_nothing(fr):
    sc = fr
    a = add_anim(sc)
    add_cad(a, 0.0, 1.0)
    add_cad(a, 1.0, 1.0)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    assert info["frames"] >= 50
    assert not animation.has_keys(sc) or all(
        o.animation_data is None or o.animation_data.action is None for o in sc.objects
        if o.get(build.PROP_KIND) == "part")


def test_back_to_cad_with_a_follower(fr):
    sc = fr
    slide, lift = rig(sc)
    joints.set_follows(sc, lift, slide.name, ratio=0.5)
    blk = named(sc, "GRIPPER BLOCK")
    cad = blk.matrix_world.copy()
    a = add_anim(sc)
    add_joint_step(a, slide, to=0.06)
    add_cad(a, 1.0, 1.0)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    sc.frame_set(animation.frame_of(a, 1.0))
    assert (blk.matrix_world.translation - cad.translation).length > 0.03
    sc.frame_set(sc.frame_end)
    assert joints.get_value(slide) == pytest.approx(0.0, abs=1e-7)
    assert maxdiff(blk.matrix_world, cad) < TOL


def test_back_to_cad_subassembly_keeps_a_motor_and_a_part_outside(fr):
    sc = fr
    u, frame, pin = unit(sc), named(sc, "PORTAL FRAME"), named(sc, "SPLIT PIN")
    spin = joints.create(sc, "ROTATE", [pin], Vector((0.12, 0, 0.05)), Vector((0, 0, 1)), name="Spin")
    spin.is_motor = True
    travel = joints.create(sc, "SLIDE", [frame], Vector((0, 0, 0)), Vector((0, 1, 0)), name="Frame travel")
    cover = named(sc, "COVER")
    a = add_anim(sc)
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", spin.name, 0.0, 1.0, True
    s.to_angle = math.radians(-(2 * 360 + 100))
    add_joint_step(a, travel, to=0.2)
    add_cad(a, 1.0, 1.0, sub=u)
    # a part moved by hand before Build (a free move) inside the unit
    cover.matrix_basis = build.rest_basis(cover) @ Matrix.Translation((0.0, 0.0, 0.03))
    bpy.context.view_layer.update()
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    sc.frame_set(sc.frame_end)
    assert joints.get_value(spin) == pytest.approx(math.radians(-2 * 360), abs=1e-5)   # nearest whole turn
    assert joints.get_value(travel) == pytest.approx(0.2, abs=1e-6)                     # outside: stays
    assert maxdiff(cover.matrix_basis, build.rest_basis(cover)) < 1e-7                 # moved part: home


def test_back_to_cad_subassembly_not_found_warns(fr):
    sc = fr
    a = add_anim(sc)
    c = add_cad(a, 0.0, 1.0)
    c.cad_whole = False
    info = animation.bake(sc, a)
    assert any("pick a subassembly" in w for w in info["warnings"]), info["warnings"]
    c.target_uid, c.target_name = "nope", "GONE"
    info = animation.bake(sc, a)
    assert any("not found" in w for w in info["warnings"]), info["warnings"]


def test_gcode_walk_follows_back_to_cad(fr):
    from fresing_render.blender import gcode
    sc = fr
    slide, lift = rig(sc)
    a = add_anim(sc)
    c = add_cad(a, 0.0, 1.0)
    js = {slide.name: 0.07, lift.name: 0.02}
    gcode._walk(sc, c, js)
    assert js == {slide.name: 0.0, lift.name: 0.0}
    c2 = add_cad(a, 0.0, 1.0, sub=unit(sc))
    js = {slide.name: 0.07}
    gcode._walk(sc, c2, js)
    assert js[slide.name] == 0.0


# --- product video ------------------------------------------------------------------------------------------------

def test_product_video_without_joints_or_decals_has_no_closeups(fr):
    from fresing_render.blender import product_video as pv
    sc = fr
    assert pv.pick_spots(sc) == []
    info = pv.make(sc)
    assert info["spots"] == []
    assert any("close-ups" in x for x in info["left_out"]), info["left_out"]
    assert not any(b.kind == "CAD" for b in info["animation"].blocks)          # no poses: no Back to CAD


def test_product_video_closeups_frame_the_moving_part_and_make_twice(fr):
    from bpy_extras.object_utils import world_to_camera_view
    from fresing_render.blender import product_video as pv
    sc = fr
    slide, lift = rig(sc)
    for j, lim in ((slide, 0.08), (lift, 0.02)):
        j.use_limits, j.dist_min, j.dist_max = True, 0.0, lim
    joints.set_value(slide, 0.05)
    states.save_pose(sc, "Out")
    joints.set_value(slide, 0.0)
    bpy.context.view_layer.update()
    info = pv.make(sc)
    a = info["animation"]
    ks = [b.kind for b in a.blocks]
    assert ks.count("CAD") == 1 and ks.index("POSE") < ks.index("CAD")
    spots = info["spots"]
    assert spots and spots[0]["label"] == slide.name                    # the longest travel first
    car = named(sc, "CARRIAGE")
    assert car in spots[0]["objects"]
    steps = [b for b in a.blocks if b.kind == "CAMERA" and b.camera is not None and b.camera.get(pv.CAM_TAG)
             and "close-up" in b.camera.name]
    assert len(steps) == len(spots)
    cam = steps[0].camera
    bpy.context.view_layer.update()
    c = Vector(tuple(np.mean(sequence.corners(car), axis=0)))
    v = world_to_camera_view(sc, cam, c)
    assert 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0 and v.z > 0.0
    n_cams = len([o for o in sc.objects if o.type == "CAMERA"])
    pv.make(sc)
    assert len([o for o in sc.objects if o.type == "CAMERA"]) == n_cams          # made again: not duplicated


def test_product_video_with_a_pose_builds_without_warnings(fr):
    from fresing_render.blender import product_video as pv
    sc = fr
    slide, lift = rig(sc)
    for j, lim in ((slide, 0.08), (lift, 0.02)):
        j.use_limits, j.dist_min, j.dist_max = True, 0.0, lim
    joints.set_value(slide, 0.05)
    states.save_pose(sc, "Out")
    joints.set_value(slide, 0.0)
    bpy.context.view_layer.update()
    info = pv.make(sc)
    a = info["animation"]
    pose = next(b for b in a.blocks if b.kind == "POSE")
    cad = next(b for b in a.blocks if b.kind == "CAD")
    assert cad.start == pytest.approx(pose.start + pose.duration, abs=1e-5)   # back to back, as planned
    res = animation.bake(sc, a)
    assert not res["warnings"], res["warnings"]


def test_riders_put_together_alone_end_on_their_carried_places(fr):
    sc = fr
    slide, lift = rig(sc)
    a = add_anim(sc, "In")
    add_joint_step(a, slide, to=0.05)
    add_joint_step(a, lift, to=0.01)
    animation.bake(sc, a)
    parts = sequence.movers(sc, unit(sc)).parts
    carried = worlds(sc, parts, animation.frame_of(a, 1.0))
    animation.clear_keys(sc)
    add_seq(sc, a, start=1.0, seq_mode="TOGETHER", seq_part_time=0.6, seq_overlap=70.0, easing="EASE_OUT")
    # (STAY: a part hidden by its keys is not evaluated and its matrix_world would be stale)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    end = worlds(sc, parts, sc.frame_end)
    for o in parts:
        assert maxdiff(end[o.name], carried[o.name]) < TOL, o.get(build.PROP_NAME)
    start = worlds(sc, parts, animation.frame_of(a, 1.0))
    for o in parts:                              # out at the start, and coming in on a straight line
        way = carried[o.name].translation - start[o.name].translation
        assert way.length > 0.02, o.get(build.PROP_NAME)
        for f in range(animation.frame_of(a, 1.0), sc.frame_end + 1, 3):
            sc.frame_set(f)
            d = o.matrix_world.translation - start[o.name].translation
            assert d.cross(way).length < 1e-5 * way.length, (o.get(build.PROP_NAME), f)
    # task 0132: the jump out at its first frame is a cut, not a motion (it gave rows through the bolts before)
    jumped = animation.jumps(sc)            # (a rider carried out by its carrier's jump has no jump of its own)
    assert set(jumped) == {animation.frame_of(a, 1.0)}
    assert jumped[animation.frame_of(a, 1.0)] <= {o.name for o in parts} and named(sc, "COVER").name in \
        jumped[animation.frame_of(a, 1.0)]
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, r.frame_from, round(r.depth * 1000, 2)) for r in run.rows]


def test_frame_moved_away_by_a_joint_before_the_step_no_longer_blocks(fr):
    """The obstacles are read where the earlier steps have put them: the portal frame travelled 0.5 m along Y."""
    sc = fr
    frame = named(sc, "PORTAL FRAME")
    travel = joints.create(sc, "SLIDE", [frame], Vector((0, 0, 0)), Vector((0, 1, 0)), name="Frame travel")
    a = add_anim(sc)
    add_joint_step(a, travel, to=0.5)
    add_seq(sc, a, start=1.0)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    parts = sequence.movers(sc, unit(sc)).parts
    w0 = worlds(sc, parts, animation.frame_of(a, 1.0))
    w1 = worlds(sc, parts, sc.frame_end)
    for o in parts:
        d = w1[o.name].translation - w0[o.name].translation
        assert d.normalized().z > 1 - 1e-6, (o.get(build.PROP_NAME), tuple(d))
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


def test_riders_on_a_turned_carrier_fly_straight_and_come_home(fr):
    """The rail block (carrier of the carriage, which carries the gripper block) is turned 20 deg about Z by a joint
    first; then take apart and put together."""
    sc = fr
    slide, lift = rig(sc)
    rail = named(sc, "RAIL BLOCK")
    turn = joints.create(sc, "ROTATE", [rail], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Turn rail",
                         base=named(sc, "BASE PLATE"))
    named(sc, "PORTAL FRAME").hide_render = True
    a = add_anim(sc)
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", turn.name, 0.0, 1.0, True
    s.to_angle = math.radians(20)
    add_joint_step(a, slide, to=0.05)
    b = add_seq(sc, a, start=1.0, seq_direction="CENTRE", seq_part_time=0.5)
    dur = b.duration
    add_seq(sc, a, start=1.0 + dur + 0.3, seq_mode="TOGETHER", seq_direction="CENTRE", seq_part_time=0.5)
    info = animation.bake(sc, a)
    parts = sequence.movers(sc, unit(sc)).parts
    w0 = worlds(sc, parts, animation.frame_of(a, 1.0))
    w1 = worlds(sc, parts, animation.frame_of(a, 1.0 + dur))
    for o in parts:
        way = w1[o.name].translation - w0[o.name].translation
        assert way.length > 0.02, o.get(build.PROP_NAME)
        for f in range(animation.frame_of(a, 1.0), animation.frame_of(a, 1.0 + dur) + 1):
            sc.frame_set(f)
            d = o.matrix_world.translation - w0[o.name].translation
            assert d.cross(way).length < 1e-5 * way.length, (o.get(build.PROP_NAME), f)
            assert maxdiff(o.matrix_world.to_3x3(), w0[o.name].to_3x3()) < 1e-5
    end = worlds(sc, parts, sc.frame_end)
    for o in parts:
        assert maxdiff(end[o.name], w0[o.name]) < TOL, o.get(build.PROP_NAME)
    if not info["warnings"]:
        run = clash.check(sc)
        assert not [r for r in run.rows if r.frame_from >= animation.frame_of(a, 1.0)], \
            [(r.a, r.b, r.frame_from, round(r.depth * 1000, 2)) for r in run.rows]


# --- task 0132: a step's own jump is not swept; a real clash still is ------------------------------------------------

def test_put_together_alone_no_rows_but_a_real_clash_is_found(fr):
    """A Put together with nothing taken apart before puts its parts out at once at its first frame: no rows from that.
    Then the portal frame is driven down through the unit: that clash is found (and only from the frame's move)."""
    sc = fr
    frame = named(sc, "PORTAL FRAME")
    drop = joints.create(sc, "SLIDE", [frame], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Frame drop")
    a = add_anim(sc)
    b = add_seq(sc, a, start=0.2, seq_mode="TOGETHER", seq_part_time=0.4)
    t_drop = 0.2 + b.duration + 0.2
    add_joint_step(a, drop, start=t_drop, to=-0.15, dur=1.0)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    f_in = animation.frame_of(a, 0.2)
    assert set(animation.jumps(sc)) == {f_in}
    run = clash.check(sc)
    assert run.rows, "the portal frame driven through the unit must clash"
    assert all(r.frame_to >= animation.frame_of(a, t_drop) for r in run.rows), \
        [(r.a, r.b, r.frame_from, r.frame_to) for r in run.rows]
    assert any(frame.get(build.PROP_NAME) in (r.a, r.b) for r in run.rows)
    # the same project without the drop: no rows at all
    animation.clear_keys(sc)
    next(x for x in a.blocks if x.kind == "JOINT").enabled = False
    animation.bake(sc, a)
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, r.frame_from, round(r.depth * 1000, 2)) for r in run.rows]
    animation.clear_keys(sc)
    assert animation.JUMPS not in sc


def test_a_jump_is_only_skipped_for_the_parts_that_jump(fr):
    """The cut is per part: a part that really moves through another in the same frame gap is still found. A
    recorded jump that names another part does not hide it."""
    sc = fr
    frame = named(sc, "PORTAL FRAME")
    drop = joints.create(sc, "SLIDE", [frame], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Frame drop")
    a = add_anim(sc)
    s = a.blocks.add()                    # a 1-frame move: the frame jumps through the unit between two frames
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", drop.name, 0.4, 0.04, True
    s.to_dist, s.easing = -0.4, "LINEAR"
    animation.bake(sc, a)
    f1 = animation.frame_of(a, 0.44)
    sc[animation.JUMPS] = '{"%d": ["%s"]}' % (f1, named(sc, "COVER").name)
    run = clash.check(sc)
    assert any(frame.get(build.PROP_NAME) in (r.a, r.b) for r in run.rows), "a real fast move must still be swept"
