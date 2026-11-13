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
