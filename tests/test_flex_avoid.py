"""Task 0298: hoses that avoid other parts (core/flex_avoid.py, the contact in core/flex.py, blender/flex_avoid.py),
a route shaped by via points (blender/flex_route.py, ops_route.py) and hoses in the clash check.

The Blender part runs on the avoid test model (tools/make_test_flex.py ``avoid``: a block in the way of a Ø20 hose
from a fitting on the base to a fitting on a lift that slides down 400 mm; its numbers are in the maker).
"""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import flex as HS
from fresing_render.core import flex_avoid as FA

HERE = os.path.dirname(__file__)
MM = 0.001
TOL = 2.5 * MM                  # the hose's surface may go this far into a part between two of its points: where it
#                                 bends round a sharp edge, the straight piece between two samples (a quarter of a
#                                 segment apart) cuts the corner (1.4 mm for a soft Ø20 hose 1.3 m long, 2.2 mm 1.6 m)


# ---------------------------------------------------------------------------
# core: no Blender
# ---------------------------------------------------------------------------

def test_box_and_ball_distance_and_exit():
    box = FA.Box((0, 0, 0), (1, 2, 3))
    d, n = box.distance(np.array([[0.5, 1, 1.5], [2, 1, 1.5], [0.5, 1, 3.5], [2, 3, 3.5], [0.1, 1, 1.5]]))
    assert d == pytest.approx([-0.5, 1.0, 0.5, 1.5, -0.1])
    assert np.allclose(n[1], (1, 0, 0)) and np.allclose(n[2], (0, 0, 1)) and np.allclose(n[4], (-1, 0, 0))
    assert np.allclose(n[3], np.array([1, 1, 0.5]) / 1.5)
    assert box.exit(np.array([[0.5, 1, 1.5]]), np.array([[0, 0, 1.0]]))[0] == pytest.approx(1.5)
    ball = FA.Ball((0, 0, 0), 1.0)
    d, n = ball.distance(np.array([[2.0, 0, 0], [0, 0.5, 0]]))
    assert d == pytest.approx([1.0, -0.5]) and np.allclose(n[1], (0, 1, 0))
    assert ball.exit(np.array([[0, 0.5, 0]]), np.array([[0, 1.0, 0]]))[0] == pytest.approx(0.5)


def test_field_moves_bodies_culls_by_reach_and_keeps_rows_apart():
    box = FA.Box((-0.1, -0.1, -0.1), (0.1, 0.1, 0.1))
    m = np.eye(4)
    m[:3, 3] = (1.0, 0.0, 0.0)
    turn = np.eye(4)
    turn[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    f = FA.Field([box], [0, 1], [0, 0], np.stack([m, turn]))
    pts = np.array([[[1.0, 0.0, 0.3]], [[1.0, 0.0, 0.3]]])
    d, n = f([0, 1], pts, clear=0.5)
    assert d[0, 0] == pytest.approx(0.2) and np.allclose(n[0, 0], (0, 0, 1))
    assert d[1, 0] == FA.FAR                     # row 1's box sits at the origin: far from that point
    # reach: an entry whose box is far from its row's room is dropped at once
    far = FA.Field([box], [0], [0], [m], reach=(np.array([[5.0, 5, 5]]), np.array([[6.0, 6, 6]])))
    assert len(far) == 0
    # the nearest of two bodies wins, also when they are one body at two places
    m2 = np.eye(4)
    m2[:3, 3] = (1.0, 0.0, 0.55)
    f2 = FA.Field([box], [0, 0], [0, 0], np.stack([m, m2]))
    d, n = f2([0], np.array([[[1.0, 0.0, 0.3]]]), clear=0.5)
    assert d[0, 0] == pytest.approx(0.15) and np.allclose(n[0, 0], (0, 0, -1))


P0, P1 = np.array([0.0, 0.0, 0.5]), np.array([1.0, 0.0, 0.5])
T0 = T1 = np.array([1.0, 0.0, 0.0])
BLOCK = FA.Box((0.3, -0.2, -1.0), (0.7, 0.2, 0.35))      # stands on the "floor": the hose cannot go under it


def gap_to(body, pts, radius):
    """The smallest gap between a hose's surface and the body, measured along its polyline (600 points)."""
    return float(body.distance(HS.resample(pts, 600))[0].min()) - radius


@pytest.mark.parametrize("length", [1.1, 1.3, 1.6])
@pytest.mark.parametrize("stiffness", [0.2, 0.5, 0.9])
def test_a_sagging_hose_lies_on_the_block(length, stiffness):
    d = 0.02
    free = HS.solve_hose(P0, T0, P1, T1, length, HS.stiff_length(d, stiffness))
    assert gap_to(BLOCK, free.points[0], d / 2) < -0.05                  # without: deep in it
    field = FA.Field([BLOCK], [0], [0], [np.eye(4)])
    res = HS.solve_hose(P0, T0, P1, T1, length, HS.stiff_length(d, stiffness))
    res = HS.solve_hoses(P0, T0, P1, T1, length, HS.stiff_length(d, stiffness), avoid=field, clear=d / 2)
    pts = res.points[0]
    assert gap_to(BLOCK, pts, d / 2) > -TOL
    assert np.allclose(pts[0], P0) and np.allclose(pts[-1], P1)
    assert HS.polyline_length(pts) == pytest.approx(length, rel=1e-6)      # its length is kept
    over = (pts[:, 0] > 0.3) & (pts[:, 0] < 0.7)
    assert pts[over, 2].min() > 0.35                       # on top of it (a soft one droops beside it on each side)


def test_a_hose_clear_of_the_parts_is_not_touched():
    d = 0.02
    stiff = HS.stiff_length(d, 0.5)
    free = HS.solve_hose(P0, T0, P1, T1, 1.01, stiff)
    assert free.points[0, :, 2].min() > 0.4
    field = FA.Field([BLOCK], [0], [0], [np.eye(4)])
    res = HS.solve_hoses(P0, T0, P1, T1, 1.01, stiff, avoid=field, clear=d / 2)
    assert np.array_equal(res.points, free.points)


def test_a_batch_gives_each_hose_what_it_gets_alone():
    d = 0.02
    stiff = HS.stiff_length(d, 0.5)
    field = FA.Field([BLOCK], [0], [0], [np.eye(4)])
    alone = HS.solve_hoses(P0, T0, P1, T1, 1.3, stiff, avoid=field, clear=d / 2).points[0]
    # the same hose as row 1 of a batch whose row 0 has no parts to avoid
    field2 = FA.Field([BLOCK], [1], [0], [np.eye(4)])
    both = HS.solve_hoses(np.stack([P0, P0]), np.stack([T0, T0]), np.stack([P1, P1]), np.stack([T1, T1]), [1.3, 1.3],
                          stiff, avoid=field2, clear=[d / 2, d / 2]).points
    assert np.allclose(both[1], alone, atol=1e-9)
    assert gap_to(BLOCK, both[0], d / 2) < -0.05                            # row 0 had nothing to avoid


def test_a_motion_stays_out_at_every_frame_and_does_not_jump():
    d = 0.02
    f = 60
    s = np.sin(np.linspace(0.0, 1.2, f))
    p1 = np.stack([1.0 - 0.3 * s, 0.2 * s, 0.5 + 0.3 * s], axis=1)
    field = FA.Field([BLOCK], np.arange(f), np.zeros(f, int), np.tile(np.eye(4), (f, 1, 1)))
    res = HS.solve_motion(np.tile(P0, (f, 1)), np.tile(T0, (f, 1)), p1, np.tile(T1, (f, 1)), 1.3,
                          HS.stiff_length(d, 0.6), 0.5, avoid=field, clear=d / 2)
    for k in range(f):
        assert gap_to(BLOCK, res.points[k], d / 2) > -TOL, k
    assert HS.largest_move(res.points) < 0.05                               # ends move ~0.6 cm a frame


def test_a_seed_keeps_the_side_and_is_quick():
    d = 0.02
    stiff = HS.stiff_length(d, 0.5)
    field = FA.Field([BLOCK], [0], [0], [np.eye(4)])
    first = HS.solve_hoses(P0, T0, P1, T1, 1.3, stiff, avoid=field, clear=d / 2)
    p1 = P1 + (0.0, 0.0, -0.02)
    again = HS.solve_hoses(P0, T0, p1, T1, 1.3, stiff, avoid=field, clear=d / 2, seed=first.points)
    assert gap_to(BLOCK, again.points[0], d / 2) > -TOL
    assert np.abs(again.points[0] - first.points[0]).max() < 0.05


# ---------------------------------------------------------------------------
# the route editor's picking (pure)
# ---------------------------------------------------------------------------

def test_hot_takes_the_nearest_dot_then_the_line():
    from fresing_render.blender.ops_route import hot
    dots = np.array([[100.0, 100.0], [200.0, 100.0]])
    line = np.array([[0.0, 50.0], [300.0, 50.0]])
    assert hot((105, 98), dots, line) == ("dot", 0)
    kind, i, t = hot((150, 55), dots, line)
    assert kind == "line" and i == 0 and t == pytest.approx(0.5)
    assert hot((150, 80), dots, line) == (None,)
    assert hot((150, 80), np.zeros((0, 2)), np.array([[np.nan, np.nan], [1.0, 1.0]])) == (None,)


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, flex, flex_avoid, flex_route, joints  # noqa: E402

AVOID_A = os.path.join(HERE, "data", "test_flex_avoid_a.step")
AVOID_B = os.path.join(HERE, "data", "test_flex_avoid_b.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("avoid"))


def load(folder, path=AVOID_A):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def lift(sc, value):
    joints.set_value(joints.find(sc, "Lift"), value)
    bpy.context.view_layer.update()
    flex.refresh(sc)


def hose_gap(sc, item, part="BLOCK"):
    """The smallest gap (m) between the hose's surface and the part now (negative: in it)."""
    ob = named(sc, part)
    body = flex_avoid.body_of(ob)
    inv = np.linalg.inv(flex_avoid._rigid(np.array(ob.matrix_world)))
    pts = HS.resample(flex.shape_now(sc, item), 800)
    d, _w = body.distance(pts @ inv[:3, :3].T + inv[:3, 3])
    return float(d.min()) - 0.5 * item.diameter


@pytest.fixture()
def model(folder):
    sc = load(folder)
    made = flex.set_up_test_avoid(sc, avoid=False)
    return sc, flex.find(sc, made["items"][0])


def test_avoid_live_and_off_as_before(model):
    sc, it = model
    assert it.diameter == pytest.approx(0.02, abs=0.0002) and not it.avoid
    lift(sc, -0.4)
    off = flex.shape_now(sc, it).copy()
    assert hose_gap(sc, it) < -0.05                                  # through the block
    it.avoid = True
    names = {o.get(build.PROP_NAME) for o in flex_avoid.parts_for(sc, it)}
    assert "BLOCK" in names and "BASE" in names
    assert not names & {"FITTING BASE", "FITTING LIFT", "HOSE"}       # its fittings and itself are not avoided
    assert hose_gap(sc, it) > -TOL
    for v in (-0.3, -0.15, 0.0, 0.1, -0.4):
        lift(sc, v)
        assert hose_gap(sc, it) > -TOL, v
    it.avoid = False                                                 # off: exactly as before
    lift(sc, -0.4)
    assert np.allclose(flex.shape_now(sc, it), off, atol=1e-6)


def test_avoid_at_every_frame_of_a_build(model):
    sc, it = model
    it.avoid = True
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Move", 0.0, "25"
    for start, sec, to in ((0.0, 2.0, -0.4), (2.0, 2.0, 0.1)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Lift", start, sec, "LINEAR"
        b.use_from, b.to_dist = True, to
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    worst = min((sc.frame_set(f), hose_gap(sc, it))[1] for f in range(sc.frame_start, sc.frame_end + 1))
    assert worst > -TOL
    # no clash row for it: it stays out
    sc.fresing.clash.hoses = True
    run = clash.check(sc, store=False)
    assert not [r for r in run.rows if it.part.name in r.names]


def test_a_via_point_shapes_the_route_and_is_kept(model, tmp_path):
    sc, it = model
    before = flex.shape_now(sc, it).copy()
    p = np.array([0.72, 0.15, 0.55])                                  # beside the drawn route, over the block
    k = flex_route.add(sc, it, p, 0, 0.5)
    it = flex.find(sc, it.name)
    assert flex_route.count(it) == 1 and len(it.clips) == 1 and it.clips[k].via
    line = flex.shape_now(sc, it)
    assert np.linalg.norm(line - p, axis=1).min() < 0.1 * MM          # the hose runs through it
    assert np.abs(line[len(line) // 2] - before[len(before) // 2]).max() > 0.05
    # dragged: the route follows
    q = np.array([0.72, -0.15, 0.6])
    flex_route.move(sc, it, k, q)
    line = flex.shape_now(sc, it)
    assert np.linalg.norm(line - q, axis=1).min() < 0.1 * MM
    # the lift moves: the via point goes along, the hose still runs through it
    lift(sc, -0.2)
    via = flex_route.stops_now(it)[1][0]
    assert np.linalg.norm(flex.shape_now(sc, it) - via, axis=1).min() < 0.1 * MM
    assert np.linalg.norm(via - q) < 0.15                              # carried part of the way down
    lift(sc, 0.0)
    assert np.linalg.norm(flex_route.stops_now(it)[1][0] - q) < 1e-6
    # save and open again
    path = str(tmp_path / "route.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 1
    flex.refresh(sc, force=True)
    assert np.linalg.norm(flex.shape_now(sc, it) - q, axis=1).min() < 0.1 * MM
    # a model update to revision B: the via point stays where it was
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=AVOID_B, quality="draft", update_root=root.name) == {"FINISHED"}
    bpy.context.view_layer.update()
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 1 and it.a_part is not None
    flex.refresh(sc, force=True)
    assert np.linalg.norm(flex_route.stops_now(it)[1][0] - q) < 0.1 * MM
    assert np.linalg.norm(flex.shape_now(sc, it) - q, axis=1).min() < 0.1 * MM
    # cleared: straight from end to end again
    assert flex_route.clear(sc, it) == 1 and not len(it.clips)


def test_automatic_length_follows_the_route(model):
    sc, it = model
    cad = it.length
    it.length_auto = True
    auto = it.length
    assert auto != pytest.approx(cad, rel=1e-3)
    flex_route.add(sc, it, np.array([0.72, 0.0, 0.9]), 0, 0.5)         # a detour up: longer
    it = sc.fresing.flex[0]
    assert it.length > auto + 0.2
    it.length_auto = False
    fixed = it.length
    flex_route.move(sc, it, 0, np.array([0.72, 0.0, 1.1]))
    assert sc.fresing.flex[0].length == fixed                          # fixed: stays as it is


def test_a_via_point_in_the_block_is_a_clash_row(model):
    sc, it = model
    it.avoid = True
    flex_route.add(sc, it, np.array([0.72, 0.0, 0.3]), 0, 0.5)          # inside the block: the hose must go in
    it = sc.fresing.flex[0]
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Move", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Lift", 0.0, 1.0, "LINEAR"
    b.use_from, b.to_dist = True, -0.1
    assert not animation.bake(sc, a)["warnings"]
    sc.fresing.clash.hoses = False
    assert not [r for r in clash.check(sc, store=False).rows if it.part.name in r.names]
    sc.fresing.clash.hoses = True
    run = clash.check(sc)
    rows = [r for r in run.rows if it.part.name in r.names]
    assert rows and rows[0].kind == "CLASH" and named(sc, "BLOCK").name in rows[0].names
    assert rows[0].depth > 0.05
