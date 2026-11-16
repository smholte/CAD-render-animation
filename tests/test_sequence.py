"""Assembly sequence step (task 0100): take a subassembly apart part by part, or put it together.

Test model: tools/make_test_sequence.py (SPINDLE.UNIT: 12 parts round the Z axis, 5 of them fasteners, on a base
plate). The core part (order, directions, distances, times) is tested without Blender first.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from fresing_render.core import sequence as core

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_sequence.step")
MM = 1e-3
TOL = 0.01 * MM                      # every part within 0.01 mm of its target


# ---------------------------------------------------------------------------
# no Blender
# ---------------------------------------------------------------------------

def box(name, lo, hi, fastener=False, index=0):
    lo, hi = np.array(lo, float), np.array(hi, float)
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    return core.Part(name, c, fastener, index)


def stack():
    """A cup with two rings in it, a lid, a bolt (tree order: cup, ring1, ring2, lid, bolt)."""
    return [box("cup", (-6, -6, 0), (6, 6, 10), index=0),
            box("ring1", (-2, -2, 1), (2, 2, 3), index=1),
            box("ring2", (-2, -2, 3), (2, 2, 5), index=2),
            box("lid", (-6, -6, 10), (6, 6, 11), index=3),
            box("bolt", (4, 4, 8), (5, 5, 12), fastener=True, index=4)]


def test_duration_and_stagger():
    assert core.duration(0, 1.0, 0.5) == 0.0
    assert core.duration(1, 1.0, 0.5) == 1.0
    assert core.duration(5, 1.0, 0.5) == pytest.approx(3.0)
    assert core.duration(5, 2.0, 0.0) == pytest.approx(10.0)
    assert core.duration(3, 1.0, 5.0) == pytest.approx(1.0 + 2 * 0.1)        # overlap capped at 90 %
    moves = core.plan(stack(), core.Settings(direction="UP", part_time=1.0, overlap=0.25))
    starts = sorted(m.t0 for m in moves)
    assert np.allclose(np.diff(starts), 0.75)
    assert all(m.t1 - m.t0 == pytest.approx(1.0) for m in moves)


def test_outside_in_fasteners_first_then_the_near_end_furthest_out():
    parts = stack()
    moves = core.plan(parts, core.Settings(direction="UP"))
    order = [m.name for m in sorted(moves, key=lambda m: m.rank)]
    assert order == ["bolt", "lid", "ring2", "ring1", "cup"]
    assert core.fasteners_first(moves, parts)
    tree = core.plan(parts, core.Settings(direction="UP", order="TREE"))
    assert [m.name for m in sorted(tree, key=lambda m: m.rank)] == ["cup", "ring1", "ring2", "lid", "bolt"]
    rev = core.plan(parts, core.Settings(direction="UP", order="REVERSE"))
    assert [m.name for m in sorted(rev, key=lambda m: m.rank)] == ["bolt", "lid", "ring2", "ring1", "cup"]
    assert not core.fasteners_first(tree, parts)


def test_stacked_parts_end_clear_of_each_other():
    parts = stack()
    st = core.Settings(direction="AXIS", axis=(0, 0, 1), by_size=False, distance=5.0)
    moves = {m.name: m for m in core.plan(parts, st)}
    ends = {}
    for p in parts:
        z = p.corners[:, 2] + moves[p.name].offset[2]
        ends[p.name] = (z.min(), z.max())
        assert np.allclose(moves[p.name].offset[:2], 0.0)
        assert moves[p.name].distance >= 5.0 - 1e-9
    # the first out goes furthest: the lid ends beyond the rings, the rings beyond the cup (which leaves last and
    # goes the set distance): the column keeps its order, nothing flies through a part waiting outside
    for a, b in (("lid", "ring2"), ("ring2", "ring1"), ("ring1", "cup")):
        assert ends[a][0] > ends[b][1]
    assert moves["cup"].distance == pytest.approx(5.0)
    assert moves["bolt"].distance > moves["lid"].distance                # the bolt lies across the lid


def test_by_size_clears_the_subassembly_and_minus_axis():
    parts = stack()
    up = core.plan(parts, core.Settings(direction="AXIS", axis=(0, 0, 1), by_size=True))
    assert min(m.distance for m in up) == pytest.approx(12.0)          # the whole height 0 … 12
    down = core.plan(parts, core.Settings(direction="AXIS", axis=(0, 0, -1), by_size=True))
    assert all(m.offset[2] < 0 for m in down)
    assert [m.name for m in sorted(down, key=lambda m: m.rank)][0] == "bolt"
    # the floor of the cup is in the rings' way down (a test as Blender's rays answer it): the cup goes first
    floor = core.plan(parts, core.Settings(direction="AXIS", axis=(0, 0, -1)), blocked=lambda i, j: j == 0 and i in (1, 2))
    assert [m.name for m in sorted(floor, key=lambda m: m.rank)][:2] == ["bolt", "cup"]


def test_away_from_the_centre():
    parts = [box("a", (1, -1, -1), (3, 1, 1), index=0), box("b", (-3, -1, -1), (-1, 1, 1), index=1),
             box("mid", (-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), index=2)]
    moves = {m.name: m for m in core.plan(parts, core.Settings(direction="CENTRE", by_size=False, distance=2.0))}
    assert np.allclose(moves["a"].offset, (2, 0, 0)) and np.allclose(moves["b"].offset, (-2, 0, 0))
    assert np.allclose(moves["mid"].offset, (0, 0, 2))                  # right in the middle: up
    assert moves["mid"].rank == 2


def test_put_together_is_the_exact_reverse():
    parts = stack()
    st = core.Settings(direction="UP", part_time=0.8, overlap=0.4)
    apart = {m.name: m for m in core.plan(parts, st)}
    st.put_together = True
    together = {m.name: m for m in core.plan(parts, st)}
    total = core.duration(len(parts), 0.8, 0.4)
    for n, a in apart.items():
        t = together[n]
        assert np.allclose(a.offset, t.offset) and a.rank == t.rank
        assert t.t0 == pytest.approx(total - a.t1) and t.t1 == pytest.approx(total - a.t0)
    first_in = min(together.values(), key=lambda m: m.t0)
    assert first_in.name == "cup"


def _ends(parts, moves):
    by = {m.name: m for m in moves}
    return {p.name: np.asarray(p.corners) + by[p.name].offset for p in parts}


def test_away_from_the_centre_stacks_nested_parts():
    """Task 0129: parts nested in each other near the centre went the same way the same distance and ended nested
    again. Now each ends beyond the parts that leave after it going nearly the same way (GAP apart)."""
    parts = [box("cup", (0.0, -3, -3), (6, 3, 3), index=0),
             box("ring", (0.5, -1, -1), (4.5, 1, 1), index=1),
             box("pin", (1.0, -0.3, -0.3), (4.0, 0.3, 0.3), index=2),
             box("far", (-9, -1, -1), (-7, 1, 1), index=3)]
    st = core.Settings(direction="CENTRE", by_size=False, distance=2.0)
    moves = core.plan(parts, st)
    by = {m.name: m for m in moves}
    ends = _ends(parts, moves)
    rank = {m.name: m.rank for m in moves}
    gap = max(core.MIN_GAP, core.GAP * 2.0)
    for a in parts:
        for b in parts:
            if a is b or rank[a.name] > rank[b.name]:
                continue
            u = by[a.name].direction
            if float(u @ by[b.name].direction) < core.NEAR:
                continue
            # a leaves first: it ends beyond b's end, at least the gap
            assert (ends[a.name] @ u).min() >= (ends[b.name] @ u).max() + gap - 1e-9, (a.name, b.name)
    assert by["far"].distance == pytest.approx(2.0)                 # alone on its side: the set distance


def test_riders_leave_before_their_carrier_in_every_order():
    parts = stack()
    carried = {0: [1, 2], 3: [4]}            # the cup carries the rings, the lid the bolt
    for order in ("OUTSIDE_IN", "TREE", "REVERSE"):
        moves = core.plan(parts, core.Settings(direction="UP", order=order), carried=carried)
        rank = {m.name: m.rank for m in moves}
        assert rank["ring1"] < rank["cup"] and rank["ring2"] < rank["cup"] and rank["bolt"] < rank["lid"], order
    tree = core.plan(parts, core.Settings(direction="UP", order="TREE"), carried=carried)
    assert [m.name for m in sorted(tree, key=lambda m: m.rank)] == ["ring1", "ring2", "cup", "bolt", "lid"]


class _Beam:
    """A beam outside the subassembly, as Blender's swept test answers it: a part runs into it when its way (box
    moved along u by dist) overlaps the beam's box."""

    def __init__(self, parts, lo, hi):
        self.parts, self.lo, self.hi = parts, np.array(lo, float), np.array(hi, float)
        self.asked = 0

    def __call__(self, i, u, dist):
        self.asked += 1
        c = np.asarray(self.parts[i].corners)
        way = np.concatenate([c, c + np.asarray(u) * dist])
        lo, hi = way.min(axis=0) + 1e-4, way.max(axis=0) - 1e-4
        return bool(np.all(hi > self.lo) and np.all(lo < self.hi))


def test_a_part_outside_the_subassembly_sends_a_part_another_way():
    parts = [box("left", (-6, -2, 0), (-2, 2, 2), index=0), box("mid", (-1, -2, 0), (1, 2, 2), index=1),
             box("right", (2, -2, 0), (6, 2, 2), index=2)]
    beam = _Beam(parts, (-1.5, -10, 5), (1.5, 10, 6))                # over the middle part only, along Y
    st = core.Settings(direction="UP", by_size=False, distance=8.0)
    moves = {m.name: m for m in core.plan(parts, st, obstacle=beam)}
    assert np.allclose(moves["left"].direction, (0, 0, 1)) and np.allclose(moves["right"].direction, (0, 0, 1))
    mid = moves["mid"]
    assert abs(mid.direction[2]) < 1e-9                               # sideways: clear of the beam
    assert not beam(1, mid.direction, mid.distance)
    # without the beam: everything up, as before
    plain = core.plan(parts, st)
    assert all(np.allclose(m.direction, (0, 0, 1)) for m in plain)
    # a way that is blocked everywhere keeps the wanted way (Blender reports it)
    cage = _Beam(parts, (-100, -100, -100), (100, 100, 100))
    stuck = {m.name: m for m in core.plan(parts, st, obstacle=cage)}
    assert all(np.allclose(m.direction, (0, 0, 1)) for m in stuck.values())


def test_another_way_is_clear_of_the_parts_still_in_place():
    """The middle part cannot go up (beam); ±X would run into the parts left and right of it while they are still in
    place."""
    parts = [box("left", (-6, -2, 0), (-2, 2, 2), index=0), box("mid", (-1, -2, 0), (1, 2, 2), index=1),
             box("right", (2, -2, 0), (6, 2, 2), index=2)]
    beam = _Beam(parts, (-1.5, -10, 5), (1.5, 10, 6))
    st = core.Settings(direction="UP", by_size=False, distance=8.0, order="TREE",
                       frame=((1, 0, 0), (0, 1, 0), (0, 0, 1)))

    class Hit:
        dirs = None

        def __call__(self, i, j):
            return False

        def hit(self, i, j, u, dist):
            return bool(core._in_way(np.asarray(parts[i].corners), np.asarray(parts[j].corners), np.asarray(u))
                        and (np.asarray(parts[j].corners) @ np.asarray(u)).min()
                        < (np.asarray(parts[i].corners) @ np.asarray(u)).max() + dist)
    moves = {m.name: m for m in core.plan(parts, st, blocked=Hit(), obstacle=beam)}
    assert np.allclose(moves["mid"].direction, (-1, 0, 0))          # tree order: the left part has left already
    parts[1].index, parts[0].index = 0, 1                            # the middle part first: both still there
    moves = {m.name: m for m in core.plan(parts, st, blocked=Hit(), obstacle=beam)}
    u = moves["mid"].direction
    assert abs(u[0]) < 1e-9 and abs(u[2]) < 1e-9, u                 # not ±X, not up: along Y


def test_other_ways_most_like_the_wanted_first():
    st = core.Settings(frame=((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    ways = core.other_ways((0, 0, 1), st)
    assert len(ways) == 5
    assert np.allclose(ways[-1], (0, 0, -1))
    assert all(abs(w[2]) < 1e-9 for w in ways[:4])


def test_flush_parts_keep_their_order_whatever_the_float32_noise():
    """Task 0140 (0131 row 9): two parts whose near ends are flush rank by the model tree, not by 1e-9 m of noise."""
    def two(za, zb):
        return [box("cover", (-1, 0, za), (1, 1, 1), index=0), box("carriage", (2, 0, zb), (4, 1, 1), index=1)]
    st = core.Settings(direction="AXIS", axis=(0, 0, 1), by_size=False, distance=1.0)
    orders = set()
    for za, zb in ((0.0500000007, 0.0500000045), (0.0500000045, 0.0500000007)):
        moves = core.plan(two(za, zb), st)
        orders.add(tuple(m.name for m in sorted(moves, key=lambda m: m.rank)))
    assert orders == {("cover", "carriage")}, orders


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


def load(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    return sc


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def unit(sc):
    return named(sc, "SPINDLE.UNIT")


def add_anim(sc, name="Sequence"):
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
    b.seq_id = f"t{len(a.blocks)}"
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return b


@pytest.fixture()
def sc(tmp_path):
    return load(tmp_path)


def worlds(sc, parts, frame):
    sc.frame_set(frame)
    return {o.name: o.matrix_world.copy() for o in parts}


def key_frames(ob):
    ad = ob.animation_data
    cb = animation._channelbag(ob, "OBJECT")
    fc = cb.fcurves.find("location", index=2)
    assert ad is not None and fc is not None
    return [k.co[0] for k in fc.keyframe_points]


def test_take_apart_targets_order_stagger(sc):
    a = add_anim(sc)
    b = add_seq(sc, a, seq_part_time=1.0, seq_overlap=50.0)
    parts = sequence.movers(sc, unit(sc)).parts
    assert len(parts) == 12 and b.seq_count == 12 and b.seq_fasteners == 5
    assert b.duration == pytest.approx(6.5)
    w0 = worlds(sc, parts, 1)
    plan = {m.name: m for m in sequence.plan_now(b, unit(sc), parts)}
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    assert info["seconds"] == pytest.approx(6.5)
    w1 = worlds(sc, parts, sc.frame_end)
    for o in parts:
        want = Matrix.Translation(Vector(tuple(plan[o.name].offset))) @ w0[o.name]
        got = w1[o.name]
        assert (got.translation - want.translation).length < TOL, o.name
        assert max(abs(x) for r in (got - want) for x in r) < 1e-6
        assert plan[o.name].offset[2] > 0.15 and abs(plan[o.name].offset[0]) < 1e-9
    # order and stagger read from the keys: starts 0.5 s (12.5 frames) apart, rounded to frames, fasteners first
    starts = sorted(((key_frames(o)[-2], o) for o in parts), key=lambda x: x[0])
    gaps = np.diff([f for f, _ in starts])
    assert all(12 <= g <= 13 for g in gaps), gaps
    first5 = {o.get(build.PROP_NAME) for _f, o in starts[:5]}
    assert first5 == {"ISO 4762 M8x30", "ISO 4032 M24"}
    assert starts[0][1].get(build.PROP_NAME) == "ISO 4032 M24"           # the nut on top first
    assert starts[-1][1].get(build.PROP_NAME) == "HOUSING"               # the cup last
    # each part takes 1 s (25 frames)
    for o in parts:
        k = key_frames(o)
        assert k[-1] - k[-2] == pytest.approx(25, abs=1)


def test_put_together_ends_exactly_home_and_starts_out(sc):
    a = add_anim(sc)
    parts = sequence.movers(sc, unit(sc)).parts
    home = worlds(sc, parts, 1)
    add_seq(sc, a, seq_mode="TOGETHER")
    animation.bake(sc, a)
    w_start = worlds(sc, parts, 1)
    assert all((w_start[n].translation - home[n].translation).length > 0.1 for n in home)   # out at the start
    w_end = worlds(sc, parts, sc.frame_end)
    for n in home:
        assert max(abs(x) for r in (w_end[n] - home[n]) for x in r) < TOL, n
    # the first in is the housing (it left last), the last in is the nut
    first = min(parts, key=lambda o: key_frames(o)[-2])
    last = max(parts, key=lambda o: key_frames(o)[-2])
    assert first.get(build.PROP_NAME) == "HOUSING" and last.get(build.PROP_NAME) == "ISO 4032 M24"


def test_apart_then_together_and_build_twice_same_keys(sc):
    a = add_anim(sc)
    parts = sequence.movers(sc, unit(sc)).parts
    home = worlds(sc, parts, 1)
    b1 = add_seq(sc, a, seq_end="HIDE")
    add_seq(sc, a, start=b1.duration + 0.5, seq_mode="TOGETHER", seq_end="FADE")
    animation.bake(sc, a)
    mid = animation.frame_of(a, b1.duration + 0.25)
    sc.frame_set(mid)
    assert all(o.hide_render for o in parts)                             # all out and hidden in between
    end = worlds(sc, parts, sc.frame_end)
    assert all(not o.hide_render for o in parts)
    for n in home:
        assert max(abs(x) for r in (end[n] - home[n]) for x in r) < TOL, n
    from fresing_render.blender import fade
    sc.frame_set(sc.frame_end)
    assert all(float(o.get(fade.FADE, 0.0)) == pytest.approx(0.0) for o in parts)

    def keys():
        out = {}
        for o in parts:
            cb = animation._channelbag(o, "OBJECT")
            out[o.name] = [(fc.data_path, fc.array_index, tuple(tuple(k.co) for k in fc.keyframe_points))
                           for fc in cb.fcurves]
        return out
    first = keys()
    animation.bake(sc, a)
    assert keys() == first


def test_after_a_joint_moved_the_subassembly(sc):
    """A joint turns the unit 30° about Z and lifts nothing else; the parts then fly along the unit's turned +X."""
    u = unit(sc)
    parts = sequence.movers(sc, u).parts
    home0 = worlds(sc, parts, 1)
    j = joints.create(sc, "ROTATE", [u], Vector((0.3, 0.0, 0.0)), Vector((0, 0, 1)), name="Turn unit")
    a = add_anim(sc)
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", j.name, 0.0, 1.0, True
    s.to_angle = math.radians(30)
    b = add_seq(sc, a, start=1.0, seq_direction="AXIS", seq_axis="X", seq_by_size=False, seq_distance=0.25)
    t = add_seq(sc, a, start=1.0 + b.duration, seq_mode="TOGETHER", seq_direction="AXIS", seq_axis="X",
                seq_by_size=False, seq_distance=0.25)
    animation.bake(sc, a)            # (sideways the parts run into each other: reported, that is all)
    f_turned = animation.frame_of(a, 1.0)
    at = worlds(sc, parts, f_turned)
    turned_x = (u.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    assert abs(turned_x.angle(Vector((1, 0, 0))) - math.radians(30)) < 1e-4
    out = worlds(sc, parts, animation.frame_of(a, 1.0 + b.duration))
    for n in at:
        d = out[n].translation - at[n].translation
        assert d.length >= 0.25 - 1e-6 and d.normalized().dot(turned_x) > 1 - 1e-6, n
    end = worlds(sc, parts, sc.frame_end)
    for n in at:                                         # back where the joint had put them
        assert (end[n].translation - at[n].translation).length < TOL, n
    assert any((at[n].translation - home0[n].translation).length > 0.01 for n in at)
    assert t.duration == b.duration


def test_no_clash_along_the_chosen_direction(sc):
    a = add_anim(sc)
    b = add_seq(sc, a, seq_direction="AXIS", seq_axis="Z")
    add_seq(sc, a, start=b.duration, seq_mode="TOGETHER", seq_direction="UP")
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    run = clash.check(sc)
    assert not run.rows, [r.a + " x " + r.b for r in run.rows]


def test_a_blocked_way_is_reported(sc):
    a = add_anim(sc)
    add_seq(sc, a, seq_direction="AXIS", seq_axis="-Z", seq_order="TREE")
    info = animation.bake(sc, a)
    assert any("runs into" in w for w in info["warnings"]), info["warnings"]


def test_trail_lines_one_per_part_and_removed_with_the_tick(sc):
    a = add_anim(sc)
    b = add_seq(sc, a, seq_trails=True)
    animation.bake(sc, a)
    t = [x for x in sc.fresing.trails if x.seq_owner == b.seq_id]
    assert len(t) == 12 and all(x.obj is not None for x in t)
    animation.bake(sc, a)
    assert len([x for x in sc.fresing.trails if x.seq_owner == b.seq_id]) == 12       # not made twice
    b.seq_trails = False
    animation.bake(sc, a)
    assert not [x for x in sc.fresing.trails if x.seq_owner]


def test_preview_moves_the_parts_and_puts_them_back(sc):
    a = add_anim(sc)
    b = add_seq(sc, a)
    parts = sequence.movers(sc, unit(sc)).parts
    before = {o.name: o.matrix_basis.copy() for o in parts}
    b.seq_preview = 100.0
    bpy.context.view_layer.update()
    moved = [o for o in parts if (o.matrix_basis.translation - before[o.name].translation).length > 0.1]
    assert len(moved) == 12
    b.seq_preview = 0.0
    for o in parts:
        assert max(abs(x) for r in (o.matrix_basis - before[o.name]) for x in r) < 1e-9
        assert sequence.PREVIEW not in o
    b.seq_preview = 50.0
    animation.bake(sc, a)                                 # Build puts the preview back first
    assert b.seq_preview == 0.0 and not [o for o in parts if sequence.PREVIEW in o]
    assert not joints.free_moves(sc)


def test_add_step_operator_and_label(sc):
    u = unit(sc)
    sc.fresing.tree_index = next(i for i, t in enumerate(sc.fresing.tree) if t.obj == u)
    assert bpy.ops.fresing.anim_add() == {"FINISHED"}
    assert bpy.ops.fresing.block_add(kind="SEQUENCE") == {"FINISHED"}
    a = animation.active(sc)
    b = a.blocks[-1]
    assert b.seq_id and b.target_name == "SPINDLE.UNIT" and b.seq_count == 12
    assert animation.block_label(b) == "Take apart SPINDLE.UNIT"
    b.seq_part_time = 0.5
    assert b.duration == pytest.approx(0.5 + 11 * 0.25)
    assert bpy.ops.fresing.block_duplicate() == {"FINISHED"}
    assert a.blocks[-1].seq_id != b.seq_id
    states.by_uid(sc)


# ---------------------------------------------------------------------------
# task 0129: a frame round the subassembly, riders
# ---------------------------------------------------------------------------

FRAME = os.path.join(HERE, "data", "test_sequence_frame.step")
UNDER_BEAM = ("RAIL BLOCK", "COVER", "CARRIAGE", "GRIPPER BLOCK", "SPLIT PIN")


@pytest.fixture()
def fr(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=FRAME, quality="draft") == {"FINISHED"}
    return sc


def rig(sc):
    """The carriage slides along X on the rail block; the gripper block lifts on the carriage: both ride."""
    rail, car, blk = named(sc, "RAIL BLOCK"), named(sc, "CARRIAGE"), named(sc, "GRIPPER BLOCK")
    slide = joints.create(sc, "SLIDE", [car], Vector((0, 0, 0.04)), Vector((1, 0, 0)), name="Carriage", base=rail)
    lift = joints.create(sc, "SLIDE", [blk], Vector((0, 0, 0.08)), Vector((0, 0, 1)), name="Lift", base=car)
    return slide, lift


def add_frame_seq(sc, a, start=0.0, **kw):
    b = a.blocks.add()
    b.kind = "SEQUENCE"
    u = named(sc, "SLIDE.UNIT")
    b.target_uid, b.target_name = u[build.PROP_UID], u[build.PROP_NAME]
    b.start = start
    b.seq_id = f"f{len(a.blocks)}"
    b.seq_direction = "UP"
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return b


def carriage_step(a, j, start=0.0, to=0.05):
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", j.name, start, 1.0, True
    s.to_dist = to
    return s


def test_parts_under_a_frame_go_another_way_and_nothing_clashes(fr):
    sc = fr
    slide, _lift = rig(sc)
    a = add_anim(sc, "Frame")
    carriage_step(a, slide)
    apart = add_frame_seq(sc, a, start=1.0, seq_part_time=0.6)
    hold = 1.0 + apart.duration + 0.4
    add_frame_seq(sc, a, start=hold, seq_mode="TOGETHER", seq_part_time=0.6)
    unit = named(sc, "SLIDE.UNIT")
    parts = sequence.movers(sc, unit).parts
    assert apart.seq_count == len(parts) == 7 and apart.seq_riders == 2
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    at = worlds(sc, parts, animation.frame_of(a, 1.0))                  # the carriage has slid 50 mm
    out = worlds(sc, parts, animation.frame_of(a, 1.0 + apart.duration))
    for o in parts:
        name = o.get(build.PROP_NAME)
        d = out[o.name].translation - at[o.name].translation
        assert d.length > 0.05, name
        if name in UNDER_BEAM:
            assert abs(d.z) < 1e-6, (name, tuple(d))                    # not up through the beam: sideways
        else:
            assert d.normalized().z > 1 - 1e-6, (name, tuple(d))        # the bolts go up past the beam
    end = worlds(sc, parts, sc.frame_end)
    for n in at:                                                         # back where the joint had put them
        assert max(abs(x) for r in (end[n] - at[n]) for x in r) < TOL, n
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


def test_without_the_frame_the_same_parts_go_up(fr):
    sc = fr
    frame = named(sc, "PORTAL FRAME")
    frame.hide_render = True                                            # hidden: no longer in anybody's way
    a = add_anim(sc)
    b = add_frame_seq(sc, a)
    parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    moves = sequence.plan_now(b, named(sc, "SLIDE.UNIT"), parts, scene=sc)
    assert all(np.allclose(m.direction, (0, 0, 1)) for m in moves)
    frame.hide_render = False
    moves = {m.name: m for m in sequence.plan_now(b, named(sc, "SLIDE.UNIT"), parts, scene=sc)}
    turned = {o.get(build.PROP_NAME) for o in parts if not np.allclose(moves[o.name].direction, (0, 0, 1))}
    assert turned == set(UNDER_BEAM)


def test_riders_fly_on_their_own_from_their_carried_place(fr):
    sc = fr
    slide, lift = rig(sc)
    a = add_anim(sc, "Riders")
    carriage_step(a, slide)
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from, s.to_dist = "JOINT", lift.name, 0.0, 1.0, True, 0.01
    b = add_frame_seq(sc, a, start=1.0, seq_part_time=0.8, seq_overlap=50.0)
    car, blk, rail = named(sc, "CARRIAGE"), named(sc, "GRIPPER BLOCK"), named(sc, "RAIL BLOCK")
    cad = blk.matrix_world.translation.copy()
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    f_start = animation.frame_of(a, 1.0)
    w0 = worlds(sc, parts, f_start)
    # carried: 50 mm along X with the carriage, 10 mm up on its own joint
    assert (w0[blk.name].translation - cad - Vector((0.05, 0.0, 0.01))).length < TOL
    assert b.seq_riders == 2
    # the block leaves first of the three, the rail block last
    starts = {o.name: key_frames(o)[0] for o in (blk, car, rail)}
    f_blk = [k for k in key_frames(blk) if k >= f_start]
    f_car = [k for k in key_frames(car) if k >= f_start]
    f_rail = [k for k in key_frames(rail) if k >= f_start]
    assert min(f_blk) < min(f_car) < min(f_rail), starts
    # every frame from the block's start to the end: the block is at its start place + its own flight only;
    # once out, it stays put while the carriage and the rail block fly out under it
    end_f = sc.frame_end
    out = worlds(sc, parts, end_f)
    blk_out = out[blk.name].translation
    for f in range(int(max(f_blk)), end_f + 1):
        sc.frame_set(f)
        assert (blk.matrix_world.translation - blk_out).length < TOL, f
    for f in range(int(min(f_blk)), int(max(f_blk)) + 1):
        sc.frame_set(f)
        d = blk.matrix_world.translation - w0[blk.name].translation
        way = blk_out - w0[blk.name].translation
        assert d.cross(way).length < 1e-6 * max(1.0, way.length), f        # on its straight line all the time
    assert (blk_out - w0[blk.name].translation).length > 0.05


# ---------------------------------------------------------------------------
# task 0129: the Back to CAD step
# ---------------------------------------------------------------------------

def test_back_to_cad_after_a_pose_whole_model_and_one_subassembly(fr):
    sc = fr
    slide, lift = rig(sc)
    unit = named(sc, "SLIDE.UNIT")
    frame = named(sc, "PORTAL FRAME")
    cad_frame = frame.matrix_world.copy()
    cad = {o.name: o.matrix_world.copy() for o in sequence.movers(sc, unit).parts}
    joints.set_value(slide, 0.06)
    joints.set_value(lift, 0.02)
    frame.matrix_basis = build.rest_basis(frame) @ Matrix.Translation((0.0, 0.3, 0.0))   # a moved part
    bpy.context.view_layer.update()
    pose = states.save_pose(sc, "Out").name
    states.reset_pose(sc)
    joints.apply_free_moves(sc, {}, reset_others=True)
    bpy.context.view_layer.update()
    a = add_anim(sc, "Back")
    p = a.blocks.add()
    p.kind, p.pose, p.start, p.duration = "POSE", pose, 0.0, 1.0
    c = a.blocks.add()
    c.kind, c.start, c.duration = "CAD", 1.5, 1.0
    assert animation.block_label(c) == "Back to CAD"
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    sc.frame_set(animation.frame_of(a, 1.0))
    assert joints.get_value(slide) == pytest.approx(0.06, abs=1e-6)
    sc.frame_set(animation.frame_of(a, 2.0))                               # half way back, eased
    assert 0.0 < joints.get_value(slide) < 0.06
    sc.frame_set(sc.frame_end)
    assert joints.get_value(slide) == pytest.approx(0.0, abs=1e-7)
    assert joints.get_value(lift) == pytest.approx(0.0, abs=1e-7)
    for n, w in cad.items():
        o = sc.objects[n]
        assert max(abs(x) for r in (o.matrix_world - w) for x in r) < 1e-6, n
    assert max(abs(x) for r in (frame.matrix_world - cad_frame) for x in r) < 1e-6
    sc.frame_set(animation.frame_of(a, 1.0))
    assert (frame.matrix_world.translation - cad_frame.translation).y == pytest.approx(0.3, abs=1e-6)

    # only the subassembly: the joints that move its parts go back, a joint elsewhere stays
    other = joints.create(sc, "SLIDE", [frame], Vector((0, 0, 0)), Vector((0, 1, 0)), name="Frame travel")
    animation.clear_keys(sc)
    a.blocks.clear()
    for j, v in ((slide, 0.06), (other, 0.1)):
        s = a.blocks.add()
        s.kind, s.joint, s.start, s.duration, s.use_from, s.to_dist = "JOINT", j.name, 0.0, 1.0, True, v
    c = a.blocks.add()
    c.kind, c.start, c.duration, c.cad_whole = "CAD", 1.0, 1.0, False
    c.target_uid, c.target_name = unit[build.PROP_UID], unit[build.PROP_NAME]
    assert animation.block_label(c) == "Back to CAD: SLIDE.UNIT"
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    sc.frame_set(sc.frame_end)
    assert joints.get_value(slide) == pytest.approx(0.0, abs=1e-7)
    assert joints.get_value(other) == pytest.approx(0.1, abs=1e-6)


def test_back_to_cad_turns_a_motor_to_its_nearest_whole_turn(fr):
    sc = fr
    pin = named(sc, "SPLIT PIN")
    m = joints.create(sc, "ROTATE", [pin], Vector((0.12, 0, 0.05)), Vector((0, 0, 1)), name="Spin")
    m.is_motor = True
    a = add_anim(sc)
    s = a.blocks.add()
    s.kind, s.joint, s.start, s.duration, s.use_from = "JOINT", m.name, 0.0, 1.0, True
    s.to_angle = math.radians(3 * 360 + 200)
    c = a.blocks.add()
    c.kind, c.start, c.duration = "CAD", 1.0, 1.0
    animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    assert joints.get_value(m) == pytest.approx(math.radians(4 * 360), abs=1e-5)


def test_back_to_cad_step_operator(fr):
    sc = fr
    assert bpy.ops.fresing.anim_add() == {"FINISHED"}
    assert bpy.ops.fresing.block_add(kind="CAD") == {"FINISHED"}
    b = animation.active(sc).blocks[-1]
    assert b.kind == "CAD" and b.cad_whole and b.duration == pytest.approx(2.0)
    desc = bpy.ops.fresing.block_add.get_rna_type().properties["kind"].enum_items["CAD"].description
    assert "CAD" in desc


def test_back_to_cad_in_the_queue_copy_and_with_scripts_off(fr, tmp_path):
    """The render queue opens the saved project in a background copy and builds the animation there; Back to CAD
    only keys the joints' values, so every driver stays one Blender runs with scripts off."""
    sc = fr
    slide, lift = rig(sc)
    a = add_anim(sc, "Back")
    carriage_step(a, slide, to=0.06)
    c = a.blocks.add()
    c.kind, c.start, c.duration = "CAD", 1.5, 1.0
    path = str(tmp_path / "back é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    from fresing_render.blender import queue
    setup = queue._setup_animation(sc, {"kind": "ANIMATION", "animation": "Back", "quality": "draft", "id": "t",
                                        "out_dir": str(tmp_path)}, lambda *x: None)
    assert setup
    j = sc.fresing.joints["Carriage"]
    sc.frame_set(animation.frame_of(sc.fresing.animations["Back"], 1.2))
    assert joints.get_value(j) == pytest.approx(0.06, abs=1e-6)
    sc.frame_set(sc.frame_end)
    assert joints.get_value(j) == pytest.approx(0.0, abs=1e-7)
    for ob in sc.objects:
        ad = ob.animation_data
        for d in (ad.drivers if ad else []):
            drv = d.driver
            assert drv.type != "SCRIPTED" or drv.is_simple_expression, (ob.name, d.data_path, drv.expression)


def test_preview_keeps_a_rider_where_it_flew(fr):
    sc = fr
    rig(sc)
    a = add_anim(sc)
    b = add_frame_seq(sc, a)
    unit = named(sc, "SLIDE.UNIT")
    parts = sequence.movers(sc, unit).parts
    w0 = {o.name: o.matrix_world.copy() for o in parts}
    plan = {m.name: m for m in sequence.plan_now(b, unit, parts, scene=sc)}
    b.seq_preview = 100.0
    bpy.context.view_layer.update()
    for o in parts:                                    # every part (riders too) exactly at its own out place
        want = w0[o.name].translation + Vector(tuple(plan[o.name].offset))
        assert (o.matrix_world.translation - want).length < TOL, o.get(build.PROP_NAME)
    b.seq_preview = 0.0
    for o in parts:
        assert (o.matrix_world.translation - w0[o.name].translation).length < 1e-7


# ---------------------------------------------------------------------------
# task 0140: the rows of bug hunt 0131
# ---------------------------------------------------------------------------

def _whole_seq(sc, a, start=0.0, **kw):
    b = a.blocks.add()
    b.kind = "SEQUENCE"
    root = named(sc, "TEST.SEQUENCE.FRAME")
    b.target_uid, b.target_name = root[build.PROP_UID], root[build.PROP_NAME]
    b.start = start
    b.seq_id = f"w{len(a.blocks)}"
    b.seq_direction = "UP"
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return b


def _jumps(sc, parts, f_from, f_to, limit=0.015):
    out = []
    sc.frame_set(f_from)
    last = {o.name: o.matrix_world.translation.copy() for o in parts}
    for f in range(f_from + 1, f_to + 1):
        sc.frame_set(f)
        for o in parts:
            p = o.matrix_world.translation.copy()
            if (p - last[o.name]).length > limit:
                out.append((f, o.get(build.PROP_NAME), round((p - last[o.name]).length * 1000, 1)))
            last[o.name] = p
    return out


def test_nested_sequences_do_not_jump(fr):
    """0131 row 8: Take apart the slide unit, Take apart the whole model, Put together the whole model, Put together
    the slide unit: no part jumps, the slide unit's parts wait where its own Take apart left them, nothing clashes."""
    sc = fr
    a = add_anim(sc, "Nested")
    s1 = add_frame_seq(sc, a, start=0.0, seq_part_time=1.5)
    t = s1.duration + 0.2
    s2 = _whole_seq(sc, a, start=t, seq_part_time=1.5)
    t += s2.duration + 0.2
    s3 = _whole_seq(sc, a, start=t, seq_mode="TOGETHER", seq_part_time=1.5)
    t += s3.duration + 0.2
    s4 = add_frame_seq(sc, a, start=t, seq_mode="TOGETHER", seq_part_time=1.5)
    unit_parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    every = sequence.movers(sc, named(sc, "TEST.SEQUENCE.FRAME")).parts
    home = worlds(sc, every, 1)
    animation.bake(sc, a)
    out1 = worlds(sc, unit_parts, animation.frame_of(a, s1.duration + 0.1))
    assert all((out1[n].translation - home[n].translation).length > 0.05 for n in out1)
    assert _jumps(sc, every, 1, sc.frame_end) == []
    before4 = worlds(sc, unit_parts, animation.frame_of(a, s4.start) - 1)
    for n in out1:                                     # back where the slide unit's own Take apart left them
        assert (before4[n].translation - out1[n].translation).length < TOL, n
    end = worlds(sc, every, sc.frame_end)
    for n in home:
        assert (end[n].translation - home[n].translation).length < TOL, n
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


def test_preview_is_not_stored_in_a_pose_a_scene_or_the_product_video(fr):
    """0131 row 10: Save pose, Save scene and Make a product video while a Preview is above 0 % end the preview
    first: what they store is the model where it stands, not the preview's places."""
    from fresing_render.blender import product_video
    sc = fr
    a = add_anim(sc)
    b = add_frame_seq(sc, a)
    parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    home = {o.name: o.matrix_world.translation.copy() for o in parts}
    b.seq_preview = 60.0
    bpy.context.view_layer.update()
    assert any((o.matrix_world.translation - home[o.name]).length > 0.04 for o in parts)
    states.save_pose(sc, "P")
    assert b.seq_preview == 0.0 and not [o for o in parts if sequence.PREVIEW in o]
    assert not joints.free_moves(sc)
    b.seq_preview = 60.0
    bpy.context.view_layer.update()
    states.save_shot(sc, "S")
    assert b.seq_preview == 0.0 and not joints.free_moves(sc)
    b.seq_preview = 60.0
    bpy.context.view_layer.update()
    info = product_video.make(sc)
    animation.bake(sc, info["animation"])
    sc.frame_set(1)
    for o in parts:
        assert (o.matrix_world.translation - home[o.name]).length < TOL, o.get(build.PROP_NAME)


def test_parts_hidden_in_structure_take_no_part(sc):
    """0131 row 11: a part hidden with the eye in 2 Structure is not counted, gets no time and stays hidden, also with
    Put together + Hide / Fade."""
    from fresing_render.blender import logic
    cover = named(sc, "COVER")
    logic.set_hidden(cover, True)
    a = add_anim(sc)
    b = add_seq(sc, a, seq_mode="TOGETHER", seq_end="FADE")
    assert b.seq_count == 11
    assert b.seq_hidden == 1
    parts = sequence.movers(sc, unit(sc)).parts
    assert cover not in parts
    animation.bake(sc, a)
    for f in range(1, sc.frame_end + 1, 5):
        sc.frame_set(f)
        assert cover.hide_render, f
    b.seq_end = "HIDE"
    animation.bake(sc, a)
    for f in range(1, sc.frame_end + 1, 5):
        sc.frame_set(f)
        assert cover.hide_render, f


def test_trail_of_a_removed_part_is_dropped_silently(sc):
    """0131 row 16f: a sequence step's trail line whose part is gone (a model update removed it) is removed by the
    next Build, with no warning."""
    a = add_anim(sc)
    b = add_seq(sc, a, seq_trails=True)
    animation.bake(sc, a)
    animation.clear_keys(sc)
    gone = named(sc, "COVER")
    assert any(t.part == gone for t in sc.fresing.trails if t.seq_owner == b.seq_id)
    bpy.data.objects.remove(gone, do_unlink=True)
    sequence.count(sc, b)
    info = animation.bake(sc, a)
    assert not [w for w in info["warnings"] if "gone" in w], info["warnings"]
    mine = [t for t in sc.fresing.trails if t.seq_owner == b.seq_id]
    assert len(mine) == 11 and all(t.part is not None for t in mine)


def test_preview_plans_again_when_a_part_outside_changes(fr):
    """0131 row 16g: hiding the portal frame while the preview shows a step plans again (the parts under the beam
    then go up), so the preview shows what Build will build."""
    sc = fr
    a = add_anim(sc)
    b = add_frame_seq(sc, a)
    unit = named(sc, "SLIDE.UNIT")
    parts = sequence.movers(sc, unit).parts
    cover = named(sc, "COVER")
    w0 = cover.matrix_world.translation.copy()
    b.seq_preview = 100.0
    bpy.context.view_layer.update()
    d = cover.matrix_world.translation - w0
    assert abs(d.z) < 1e-6                                # sideways under the beam
    named(sc, "PORTAL FRAME").hide_render = True
    b.seq_preview = 99.0
    b.seq_preview = 100.0
    bpy.context.view_layer.update()
    d = cover.matrix_world.translation - w0
    assert d.normalized().z > 1 - 1e-6, tuple(d)          # the frame is gone: straight up
    k1 = sequence._plan_key(sc, b, unit, parts)
    assert sequence._same_plan(k1, sequence._plan_key(sc, b, unit, parts))
    named(sc, "PORTAL FRAME").location.z += 0.01
    bpy.context.view_layer.update()
    assert not sequence._same_plan(k1, sequence._plan_key(sc, b, unit, parts))


# ---------------------------------------------------------------------------
# task 0162: the sequence rows of bug hunt 0147
# ---------------------------------------------------------------------------

def test_home_stack_any_order():
    """0147 row 7: a Put together undoes the newest Take apart of its own subassembly (or one inside it), whatever
    came between; Take aparts of subassemblies round it, made later, then find the part where it ends now."""
    A, B, C = "A", "B", "C"                             # A holds B, B holds C
    inside = {A: {A, B, C}, B: {B, C}, C: {C}}
    owns = {s: (lambda uid, s=s: uid in inside[s]) for s in inside}
    h: dict = {}
    for sub, d in ((C, "cad"), (B, "c_out"), (A, "b_out")):          # take apart C, then B, then A
        sequence._home_push(h, "p", d, sub)
    assert sequence.home_top(h, "p", None, owns[B]) == "c_out"
    assert sequence._home_pop(h, "p", owns[B]) == "c_out"           # B first: C stays apart, A finds it at c_out
    assert h["p"] == [(C, "cad"), (A, "c_out")]
    assert sequence._home_pop(h, "p", owns[C]) == "cad"             # then C: home, A finds it home
    assert h["p"] == [(A, "cad")]
    assert sequence._home_pop(h, "p", owns[A]) == "cad" and "p" not in h
    for sub, d in ((C, "cad"), (A, "c_out")):
        sequence._home_push(h, "p", d, sub)
    assert sequence._home_pop(h, "p", owns[B]) == "cad"             # B holds C: undoes C's take apart
    assert h["p"] == [(A, "cad")]
    assert sequence.home_top(h, "p", "x") == "cad" and sequence.home_top({}, "p", "x") == "x"
    h = {"p": [(C, "cad")]}
    assert sequence._home_pop(h, "p", owns[A]) == "cad"             # none of its own: the newest


def _end_of(a, b):
    return animation.frame_of(a, b.start + b.duration) + 1


def test_nested_steps_in_any_order(fr):
    """0147 row 7: Take apart the slide unit, Take apart the whole model, Put together the slide unit, Put together
    the whole model: the 3rd step puts the slide unit together (its parts at home, not left at its take-apart
    place), the 4th finds them home and leaves them there; nothing jumps or clashes. (The portal frame and the base
    plate are hidden: in this order the slide unit would come home through the base plate that the whole model's
    Take apart has lifted over it – the clash check shows that; it is not a fault of the steps.)"""
    from fresing_render.blender import logic
    sc = fr
    logic.set_hidden(named(sc, "PORTAL FRAME"), True)
    logic.set_hidden(named(sc, "BASE PLATE"), True)
    a = add_anim(sc, "Any order")
    s1 = add_frame_seq(sc, a, start=0.0, seq_part_time=1.5)
    t = s1.duration + 0.2
    s2 = _whole_seq(sc, a, start=t, seq_part_time=1.5)
    t += s2.duration + 0.2
    s3 = add_frame_seq(sc, a, start=t, seq_mode="TOGETHER", seq_part_time=1.5)
    t += s3.duration + 0.2
    s4 = _whole_seq(sc, a, start=t, seq_mode="TOGETHER", seq_part_time=1.5)
    unit_parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    every = sequence.movers(sc, named(sc, "TEST.SEQUENCE.FRAME")).parts
    home = worlds(sc, every, 1)
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]
    car = named(sc, "CARRIAGE")
    z = []
    for s in (s1, s2, s3, s4):
        sc.frame_set(_end_of(a, s))
        z.append(round((car.matrix_world.translation - home[car.name].translation).length * 1000, 1))
    assert z[0] > 50 and z[1] > z[0] and z[2] < 0.01 and z[3] < 0.01, z
    assert not [n for n, kf in [(o.name, key_frames(o)) for o in unit_parts]
                if any(f > _end_of(a, s3) for f in kf)], "the last step moved parts that were home"
    w3 = worlds(sc, unit_parts, _end_of(a, s3))
    for o in unit_parts:                                  # the slide unit is together after its own Put together
        assert (w3[o.name].translation - home[o.name].translation).length < TOL, o.get(build.PROP_NAME)
    end = worlds(sc, every, sc.frame_end)
    for n in home:
        assert (end[n].translation - home[n].translation).length < TOL, n
    assert _jumps(sc, every, 1, sc.frame_end) == []
    run = clash.check(sc)
    assert not run.rows, [(r.a, r.b, round(r.depth * 1000, 2)) for r in run.rows]


@pytest.mark.parametrize("end", ["HIDE", "FADE"])
def test_put_together_stay_shows_what_take_apart_hid(sc, end):
    """0147 row 9: Take apart with Hide or Fade, then Put together with Stay: every part shows again from its come-in
    on (12 of 12 render at the last frame, none before its own come-in)."""
    from fresing_render.blender import fade
    a = add_anim(sc)
    b1 = add_seq(sc, a, seq_end=end)
    b2 = add_seq(sc, a, start=b1.duration + 0.5, seq_mode="TOGETHER", seq_end="STAY")
    parts = sequence.movers(sc, unit(sc)).parts
    assert len(parts) == 12
    info = animation.bake(sc, a)
    assert not info["warnings"], info["warnings"]

    def shows(o):
        return not o.hide_render and float(o.get(fade.FADE, 0.0)) < 1e-6
    sc.frame_set(animation.frame_of(a, b2.start) - 1)
    assert not any(shows(o) for o in parts)             # still hidden / faded while they wait out there
    sc.frame_set(sc.frame_end)
    assert sum(shows(o) for o in parts) == 12


def test_a_rider_comes_in_from_where_it_is(fr):
    """0147 row 13: a rider in a Put together whose settings differ from its Take apart starts where it is and blends
    to its line, as the other parts do: no jump in one frame (before: 137.9 mm)."""
    sc = fr
    rig(sc)
    a = add_anim(sc, "Riders differ")
    b1 = add_frame_seq(sc, a, seq_distance=0.1)
    add_frame_seq(sc, a, start=b1.duration + 0.3, seq_mode="TOGETHER", seq_direction="CENTRE")
    info = animation.bake(sc, a)
    parts = sequence.movers(sc, named(sc, "SLIDE.UNIT")).parts
    riders = {named(sc, "CARRIAGE").name, named(sc, "GRIPPER BLOCK").name}
    step = {}
    sc.frame_set(1)
    last = {o.name: o.matrix_world.translation.copy() for o in parts}
    for f in range(2, sc.frame_end + 1):
        sc.frame_set(f)
        for o in parts:
            p = o.matrix_world.translation.copy()
            step[o.name] = max(step.get(o.name, 0.0), (p - last[o.name]).length)
            last[o.name] = p
    others = max(v for n, v in step.items() if n not in riders)
    assert all(step[n] <= others * 1.05 + 1e-4 for n in riders), (
        {named_n: round(v * 1000, 1) for named_n, v in step.items()}, info["warnings"])


def test_hiding_a_part_after_build_takes_the_build_off(sc):
    """0147 row 21c: a part hidden with the eye in 2 Structure after Build: the built animation is taken off (Build
    again), and built again the part stays hidden at every frame."""
    a = add_anim(sc)
    add_seq(sc, a)
    animation.bake(sc, a)
    assert animation.has_keys(sc)
    cover = named(sc, "COVER")
    bpy.ops.fresing.tree_refresh()
    i = next(k for k, it in enumerate(sc.fresing.tree) if it.obj == cover)
    assert bpy.ops.fresing.tree_row(index=i, action="HIDE") == {"FINISHED"}
    assert not animation.has_keys(sc) and "Build again" in sc.fresing.last_message
    assert cover.hide_render
    animation.bake(sc, a)
    for f in range(1, sc.frame_end + 1, 3):
        sc.frame_set(f)
        assert cover.hide_render, f
    assert bpy.ops.fresing.show_all() == {"FINISHED"}             # Show all after Build: off again, then shown
    assert not animation.has_keys(sc) and not cover.hide_render
