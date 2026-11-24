"""Task 0298, independent tests (written from the brief and the docstrings by a tester who did not write the code):
hoses that avoid other parts (core/flex_avoid.py, core/flex.py ``avoid``), via points (blender/flex_route.py) and the
blender side of Avoid other parts. Its six findings were fixed by the worker; their tests are plain tests now.
"""

import os
import sys

import numpy as np
import pytest

from fresing_render.core import flex as HS
from fresing_render.core import flex_avoid as FA

HERE = os.path.dirname(__file__)
MM = 0.001
TOL = 2.5 * MM                  # the known corner cut between two samples (task file / test_flex_avoid.py)
I4 = np.eye(4)

P0, P1 = np.array([0.0, 0.0, 0.5]), np.array([1.0, 0.0, 0.5])
T0 = T1 = np.array([1.0, 0.0, 0.0])
D = 0.02
R = D / 2
STIFF = HS.stiff_length(D, 0.5)
BLOCK = FA.Box((0.3, -0.2, -1.0), (0.7, 0.2, 0.35))


def turn(axis, angle, move=(0.0, 0.0, 0.0)):
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    m = np.eye(4)
    m[:3, :3] = np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k
    m[:3, 3] = move
    return m


def gap(pts, placed, radius=R, n=3000):
    """Smallest gap between the hose's surface and bodies [(body, world matrix)], along its polyline."""
    q = HS.resample(pts, n)
    best = np.inf
    for body, m in placed:
        inv = np.linalg.inv(m)
        best = min(best, float(body.distance(q @ inv[:3, :3].T + inv[:3, 3])[0].min()))
    return best - radius


def one(length=1.3, field=None, clear=R, **kw):
    return HS.solve_hoses(P0, T0, P1, T1, length, STIFF, avoid=field, clear=clear, **kw)


def field_of(*placed):
    return FA.Field([b for b, _m in placed], [0] * len(placed), list(range(len(placed))), [m for _b, m in placed])


# ---------------------------------------------------------------------------
# the field: exact shapes against brute force
# ---------------------------------------------------------------------------

def test_box_and_ball_distance_against_brute_force():
    rng = np.random.default_rng(1)
    box = FA.Box((-0.2, -0.1, 0.0), (0.3, 0.4, 0.05))
    # surface samples of the box, dense
    g = np.linspace(0, 1, 41)
    u, v = np.meshgrid(g, g)
    faces = []
    lo, hi = box.lo, box.hi
    for ax in range(3):
        o = [k for k in range(3) if k != ax]
        for side in (lo[ax], hi[ax]):
            f = np.zeros((u.size, 3))
            f[:, ax] = side
            f[:, o[0]] = lo[o[0]] + u.ravel() * (hi[o[0]] - lo[o[0]])
            f[:, o[1]] = lo[o[1]] + v.ravel() * (hi[o[1]] - lo[o[1]])
            faces.append(f)
    surf = np.concatenate(faces)
    pts = rng.uniform(-0.5, 0.6, (300, 3))
    d, n = box.distance(pts)
    brute = np.linalg.norm(pts[:, None] - surf[None], axis=2).min(axis=1)
    inside = ((pts > lo) & (pts < hi)).all(axis=1)
    assert np.allclose(np.abs(d), brute, atol=0.02)                    # (grid of 1/40 of a side)
    assert np.array_equal(d < 0, inside)
    assert np.allclose(np.linalg.norm(n, axis=1), 1.0)
    # the way out really leads out: a small step along it grows the distance
    d2, _ = box.distance(pts + 1e-4 * n)
    assert (d2 > d - 1e-12).all()
    ball = FA.Ball((0.1, 0.2, -0.3), 0.25)
    d, n = ball.distance(pts)
    assert np.allclose(d, np.linalg.norm(pts - (0.1, 0.2, -0.3), axis=1) - 0.25)
    d2, _ = ball.distance(pts + 1e-4 * n)
    assert (d2 > d).all()


def test_exit_leaves_the_body_exactly():
    rng = np.random.default_rng(2)
    for body in (FA.Box((-0.2, -0.1, 0.0), (0.3, 0.4, 0.05)), FA.Ball((0.1, 0.2, -0.3), 0.25)):
        lo, hi = body.lo, body.hi
        pts = rng.uniform(lo, hi, (2000, 3))
        pts = pts[body.distance(pts)[0] < 0][:200]
        dirs = rng.normal(size=(len(pts), 3))
        dirs /= np.linalg.norm(dirs, axis=1)[:, None]
        t = body.exit(pts, dirs)
        assert np.isfinite(t).all() and (t >= 0).all()
        out = body.distance(pts + dirs * t[:, None])[0]
        assert np.abs(out).max() < 1e-9                                 # it lands on the surface


def test_field_with_turned_bodies_matches_each_body_in_its_own_frame():
    rng = np.random.default_rng(3)
    box = FA.Box((-0.1, -0.05, -0.2), (0.1, 0.05, 0.2))
    ball = FA.Ball((0.0, 0.0, 0.0), 0.08)
    ma = turn((1, 2, 3), 0.7, (0.5, 0.1, 0.2))
    mb = turn((0, 1, 0), 2.0, (0.6, 0.0, 0.25))
    f = FA.Field([box, ball], [0, 0, 1], [0, 1, 0], [ma, mb, mb])
    pts = rng.uniform(0.3, 0.8, (2, 400, 3))
    d, w = f([0, 1], pts, clear=0.5)

    def own(body, m, p):
        inv = np.linalg.inv(m)
        dd, nn = body.distance(p @ inv[:3, :3].T + inv[:3, 3])
        return dd, nn @ m[:3, :3].T

    da, na = own(box, ma, pts[0])
    db, nb = own(ball, mb, pts[0])
    want = np.minimum(da, db)
    near = want < 0.5                                                    # (beyond clear + margin: may be FAR)
    assert np.allclose(d[0, near], want[near], atol=1e-12)
    pick = np.where((da <= db)[:, None], na, nb)
    assert np.allclose(w[0, near], pick[near], atol=1e-9)
    dr, nr = own(box, mb, pts[1])
    near = dr < 0.5
    assert np.allclose(d[1, near], dr[near], atol=1e-12) and np.allclose(w[1, near], nr[near], atol=1e-9)


def test_field_odd_calls():
    f = field_of((BLOCK, I4))
    pts = np.array([[[0.5, 0.0, 0.3], [0.5, 0.0, 5.0]]])
    d, w = f([7], pts, 0.01)                                            # a row with no bodies
    assert np.isinf(d).all() and not w.any()
    d, w = f(np.zeros(0, int), np.zeros((0, 2, 3)), 0.01)               # no rows
    assert d.shape == (0, 2) and w.shape == (0, 2, 3)
    empty = FA.Field([], [], [], np.zeros((0, 4, 4)))
    d, w = empty([0], pts, 0.01)
    assert np.isinf(d).all() and len(empty) == 0
    d, _w = f([0], pts, 0.01)
    assert d[0, 0] == pytest.approx(-0.05) and np.isinf(d[0, 1])         # far beyond clear + margin: FAR


def test_field_ids_are_rows_not_positions():
    f = field_of((BLOCK, I4))
    p = np.array([[[0.5, 0.0, 0.3]]])
    assert np.isinf(f([-1], p, 0.01)[0]).all()
    d, _w = f([0, 0], np.concatenate([p, p]), 0.01)
    assert d[0, 0] == pytest.approx(-0.05) and d[1, 0] == pytest.approx(-0.05)


# ---------------------------------------------------------------------------
# the solver with parts to avoid: absurd inputs
# ---------------------------------------------------------------------------

def test_a_callable_as_the_docstring_says():
    f = field_of((BLOCK, I4))
    res = one(field=lambda ids, pts, clear, toward: f(ids, pts, clear, toward))
    assert gap(res.points[0], [(BLOCK, I4)]) > -TOL


def test_absurd_inputs_give_an_answer_not_a_crash():
    f = field_of((BLOCK, I4))
    bad = HS.solve_hoses(np.array([np.nan, 0, 0.5]), T0, P1, T1, 1.3, STIFF, avoid=f, clear=R)
    assert bad.short[0] and np.isfinite(bad.points).all()
    zero = one(0.0, f)
    assert zero.short[0] and np.isfinite(zero.points).all()
    none = HS.solve_hoses(np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), STIFF,
                          avoid=f, clear=R)
    assert none.points.shape == (0, 33, 3)
    taut = one(1.0 + 1e-9, f)                                             # cannot avoid anything: as without
    assert np.array_equal(taut.points, one(1.0 + 1e-9).points)
    for clear in (np.nan, np.inf, -1.0, 0.0):                            # no clearance: as without
        assert np.array_equal(one(1.3, f, clear).points, one(1.3).points), clear
    huge = one(1.3, f, 10.0)                                              # larger than the gap between the ends
    pts = huge.points[0]
    assert np.isfinite(pts).all() and HS.polyline_length(pts) == pytest.approx(1.3, rel=1e-6)
    assert np.allclose(pts[0], P0) and np.allclose(pts[-1], P1)


def test_a_fitting_inside_a_part_still_gives_a_hose():
    inside = FA.Box((-0.1, -0.1, 0.4), (0.1, 0.1, 0.6))                 # the fitting at P0 sits in it
    res = one(1.3, field_of((inside, I4), (BLOCK, I4)))
    pts = res.points[0]
    assert np.isfinite(pts).all() and not res.short[0]
    assert HS.polyline_length(pts) == pytest.approx(1.3, rel=1e-6)
    assert np.allclose(pts[0], P0) and np.allclose(pts[-1], P1)
    assert gap(pts, [(BLOCK, I4)]) > -TOL                                # the block further on is still avoided


def test_seed_of_the_wrong_shape_or_nan_is_ignored():
    f = field_of((BLOCK, I4))
    plain = one(1.3, f).points
    for seed in (np.zeros((5, 3)), np.full((1, 33, 3), np.nan), np.zeros((1, 33, 3)), np.ones((2, 33, 3))):
        assert np.array_equal(one(1.3, f, seed=seed).points, plain)


def test_same_inputs_same_answer_and_batch_independence():
    ball = FA.Ball((0.5, 0.0, 0.2), 0.2)
    a = one(1.3, field_of((BLOCK, I4))).points[0]
    b = one(1.6, field_of((ball, I4))).points[0]
    assert np.array_equal(a, one(1.3, field_of((BLOCK, I4))).points[0])
    f = FA.Field([BLOCK, ball], [2, 0], [0, 1], [I4, I4])
    both = HS.solve_hoses(np.stack([P0, P0, P0]), np.stack([T0] * 3), np.stack([P1] * 3), np.stack([T1] * 3),
                          [1.6, 1.4, 1.3], STIFF, avoid=f, clear=[R, R, R]).points
    assert np.allclose(both[2], a, atol=1e-9) and np.allclose(both[0], b, atol=1e-9)
    assert np.array_equal(both[1], one(1.4).points[0])                   # row 1: nothing to avoid


def test_culling_by_reach_changes_no_answer():
    ball = FA.Ball((0.5, 0.0, 0.2), 0.2)
    far = FA.Box((3.0, 3.0, 3.0), (4.0, 4.0, 4.0))
    lengths = np.array([1.3, 1.6])
    p0, p1 = np.stack([P0, P0]), np.stack([P1, P1])
    args = (p0, np.stack([T0, T0]), p1, np.stack([T1, T1]), lengths, STIFF)
    rows, which = [0, 0, 1, 1], [0, 2, 1, 2]
    bodies = [BLOCK, ball, far]
    plain = FA.Field(bodies, rows, which, np.tile(I4, (4, 1, 1)))
    culled = FA.Field(bodies, rows, which, np.tile(I4, (4, 1, 1)), reach=FA.reach_box(p0, p1, lengths, R))
    assert len(culled) == 2 and len(plain) == 4
    a = HS.solve_hoses(*args, avoid=plain, clear=R).points
    b = HS.solve_hoses(*args, avoid=culled, clear=R).points
    assert np.array_equal(a, b)


def test_a_motion_with_broken_frames_in_it():
    f = 10
    p1 = np.tile(P1, (f, 1))
    p1[3] = np.nan                                                       # a frame without an end
    p1[6] = (3.0, 0.0, 0.5)                                              # a frame where it is far too short
    field = FA.Field([BLOCK], np.arange(f), np.zeros(f, int), np.tile(I4, (f, 1, 1)))
    res = HS.solve_motion(np.tile(P0, (f, 1)), np.tile(T0, (f, 1)), p1, np.tile(T1, (f, 1)), 1.3, STIFF, avoid=field,
                          clear=R)
    assert res.short[3] and res.short[6] and np.isfinite(res.points).all()
    for k in (0, 1, 2, 4, 5, 7, 8, 9):
        assert not res.short[k] and gap(res.points[k], [(BLOCK, I4)], n=1200) > -TOL, k


# ---------------------------------------------------------------------------
# shapes in the way
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("placed", [
    [(FA.Ball((0.5, 0.0, 0.2), 0.2), I4)],
    [(FA.Box((0.3, -0.2, -1.0), (0.5, 0.2, 0.35)), I4), (FA.Box((0.5, -0.2, -1.0), (0.7, 0.2, 0.35)), I4)],
    [(FA.Box((-0.15, -0.15, -1.0), (0.15, 0.15, 0.35)), turn((0, 0, 1), np.pi / 4, (0.5, 0, 0)))],
    [(FA.Box((-0.15, -0.15, -1.0), (0.15, 0.15, 0.35)), turn((1, 0, 0), 0.3, (0.5, 0, 0)))],
], ids=["ball", "two touching boxes", "box turned 45 deg", "box tilted"])
@pytest.mark.parametrize("length", [1.3, 1.6])
def test_a_hose_stays_out_of_shapes(placed, length):
    res = one(length, field_of(*placed))
    pts = res.points[0]
    assert gap(pts, placed) > -TOL
    assert HS.polyline_length(pts) == pytest.approx(length, rel=1e-6)


@pytest.mark.parametrize("thick", [0.015, pytest.param(0.02, marks=pytest.mark.xfail(
    strict=True, reason="known limit (core/flex.py solve_hoses): a wall about as thin as the hose's diameter can "
                        "still be crossed – the samples on its two sides are pushed apart")), 0.03])
def test_a_wall_thicker_than_a_quarter_segment_is_not_crossed(thick):
    wall = FA.Box((0.5 - thick / 2, -0.3, -1.0), (0.5 + thick / 2, 0.3, 0.4))
    worst = min(gap(one(length, field_of((wall, I4))).points[0], [(wall, I4)]) for length in (1.3, 1.6))
    assert worst > -TOL


def test_a_moving_ball_along_a_motion():
    f = 30
    cs = np.stack([np.linspace(0.2, 0.8, f), np.zeros(f), np.full(f, 0.15)], axis=1)
    places = np.tile(I4, (f, 1, 1))
    places[:, :3, 3] = cs
    ball = FA.Ball((0.0, 0.0, 0.0), 0.15)
    field = FA.Field([ball], np.arange(f), np.zeros(f, int), places)
    res = HS.solve_motion(np.tile(P0, (f, 1)), np.tile(T0, (f, 1)), np.tile(P1, (f, 1)), np.tile(T1, (f, 1)), 1.3,
                          STIFF, avoid=field, clear=R)
    for k in range(f):
        assert gap(res.points[k], [(ball, places[k])], n=1200) > -TOL, k


@pytest.mark.parametrize("length", [1.3, 1.6])
def test_a_still_motion_does_not_jitter(length):
    f = 12
    field = FA.Field([BLOCK], np.arange(f), np.zeros(f, int), np.tile(I4, (f, 1, 1)))
    res = HS.solve_motion(np.tile(P0, (f, 1)), np.tile(T0, (f, 1)), np.tile(P1, (f, 1)), np.tile(T1, (f, 1)), length,
                          HS.stiff_length(D, 0.2), avoid=field, clear=R)
    assert HS.largest_move(res.points) < 1 * MM


def test_seeded_with_its_own_answer_it_stays():
    f = field_of((BLOCK, I4))
    worst = 0.0
    for length, s in ((1.3, 0.2), (1.6, 0.2), (1.3, 0.5)):
        st = HS.stiff_length(D, s)
        cur = HS.solve_hoses(P0, T0, P1, T1, length, st, avoid=f, clear=R).points
        for _k in range(3):
            nxt = HS.solve_hoses(P0, T0, P1, T1, length, st, avoid=f, clear=R, seed=cur).points
            worst = max(worst, float(np.abs(nxt - cur).max()))
            cur = nxt
    assert worst < 1 * MM


# ---------------------------------------------------------------------------
# Blender: the avoid test model
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fresing_render  # noqa: E402
from fresing_render.blender import build, flex, flex_avoid, flex_route, joints  # noqa: E402

AVOID_A = os.path.join(HERE, "data", "test_flex_avoid_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("avoid_ind"))


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def lift(sc, value):
    joints.set_value(joints.find(sc, "Lift"), value)
    bpy.context.view_layer.update()
    flex.refresh(sc)


def block_gap(sc, item, part="BLOCK"):
    ob = named(sc, part)
    body = flex_avoid.body_of(ob)
    inv = np.linalg.inv(flex_avoid._rigid(np.array(ob.matrix_world)))
    pts = HS.resample(flex.shape_now(sc, item), 800)
    return float(body.distance(pts @ inv[:3, :3].T + inv[:3, 3])[0].min()) - 0.5 * item.diameter


def through(sc, item, p):
    return float(np.linalg.norm(flex.shape_now(sc, item) - p, axis=1).min())


@pytest.fixture()
def model(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=AVOID_A, quality="draft") == {"FINISHED"}
    made = flex.set_up_test_avoid(sc, avoid=False)
    return sc, flex.find(sc, made["items"][0])


def test_a_part_hidden_after_avoid_is_not_avoided(model):
    sc, it = model
    it.avoid = True
    lift(sc, -0.4)
    assert block_gap(sc, it) > -TOL
    named(sc, "BLOCK").hide_set(True)                                    # hidden by the user: not avoided
    lift(sc, -0.39)
    assert block_gap(sc, it) < -0.05


def test_an_excluded_part_is_not_avoided(model):
    sc, it = model
    named(sc, "BLOCK")[build.PROP_EXCLUDED] = True
    it.avoid = True
    lift(sc, -0.4)
    assert "BLOCK" not in {o.get(build.PROP_NAME) for o in flex_avoid.parts_for(sc, it)}
    assert block_gap(sc, it) < -0.05


def test_a_hose_switched_off_with_avoid_on(model):
    sc, it = model
    it.avoid = True
    lift(sc, -0.4)
    before = flex.shape_now(sc, it).copy()
    it.enabled = False
    it = sc.fresing.flex[0]
    for v in (-0.2, 0.0):
        lift(sc, v)
    flex.refresh(sc, force=True)
    it.enabled = True
    it = sc.fresing.flex[0]
    lift(sc, -0.4)
    assert np.isfinite(flex.shape_now(sc, it)).all()
    assert block_gap(sc, it) > -TOL
    assert np.abs(flex.shape_now(sc, it) - before).max() < 0.05


def test_via_points_added_and_removed_in_any_order(model):
    sc, it = model
    plain = flex.shape_now(sc, it).copy()
    ps = [np.array([0.5, 0.1, 0.6]), np.array([0.72, 0.15, 0.55]), np.array([0.95, -0.1, 0.7])]
    for k, p in enumerate(ps):
        flex_route.add(sc, sc.fresing.flex[0], p, k, (k + 1) / 4)
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 3
    for p in ps:
        assert through(sc, it, p) < 0.1 * MM
    flex_route.remove(sc, it, 1)                                         # the middle one
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 2
    assert through(sc, it, ps[0]) < 0.1 * MM and through(sc, it, ps[2]) < 0.1 * MM
    assert through(sc, it, ps[1]) > 5 * MM
    flex_route.remove(sc, it, 0)
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 1 and through(sc, it, ps[2]) < 0.1 * MM
    flex_route.remove(sc, it, 5)                                         # no such: nothing happens
    flex_route.remove(sc, it, 0)
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 0 and len(it.clips) == 0
    assert np.allclose(flex.shape_now(sc, it), plain, atol=1e-6)        # as before any via point


def test_odd_via_points_give_a_hose(model):
    sc, it = model
    a = flex_route.stops_now(it)[0][0]
    flex_route.add(sc, it, a, 0, 0.0)                                    # on end A itself
    p = np.array([0.72, 0.15, 0.55])
    flex_route.add(sc, sc.fresing.flex[0], p, 1, 0.5)                    # two in a row at one place
    flex_route.add(sc, sc.fresing.flex[0], p, 2, 0.5)
    it = sc.fresing.flex[0]
    line = flex.shape_now(sc, it)
    assert np.isfinite(line).all() and len(line) >= 2
    for _p, d in flex_route.stops_now(it):
        assert np.isfinite(d).all() and np.linalg.norm(d) == pytest.approx(1.0)


def test_esc_puts_the_route_back(model):
    sc, it = model
    flex_route.add(sc, it, np.array([0.72, 0.15, 0.55]), 0, 0.5)
    it = sc.fresing.flex[0]
    before = flex.shape_now(sc, it).copy()
    snap = flex_route.snapshot(it)
    flex_route.add(sc, it, np.array([0.5, -0.1, 0.8]), 0, 0.3)
    flex_route.move(sc, sc.fresing.flex[0], 1, np.array([0.8, 0.2, 0.9]))
    flex_route.remove(sc, sc.fresing.flex[0], 0)
    flex_route.restore(sc, sc.fresing.flex[0], snap)
    it = sc.fresing.flex[0]
    assert flex_route.count(it) == 1
    assert np.allclose(flex.shape_now(sc, it), before, atol=1e-6)


def test_a_via_point_with_avoid_on(model):
    sc, it = model
    it.avoid = True
    it.length_auto = True                                                # (fixed: a stretch is too short for the via)
    p = np.array([0.72, 0.3, 0.55])                                     # beside the block: never in it
    flex_route.add(sc, it, p, 0, 0.5)
    it = sc.fresing.flex[0]
    for v in (0.0, -0.2, -0.4):
        lift(sc, v)
        via = flex_route.stops_now(it)[1][0]
        assert through(sc, it, via) < 0.1 * MM, v
        assert block_gap(sc, it) > -TOL, v


def test_avoid_is_kept_over_save_and_reopen(model, tmp_path):
    sc, it = model
    it.avoid = True
    lift(sc, -0.4)
    assert block_gap(sc, it) > -TOL
    path = str(tmp_path / "avoid.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    it = sc.fresing.flex[0]
    assert it.avoid
    lift(sc, -0.39)
    assert block_gap(sc, it) > -TOL


def test_the_clash_option_lists_only_hoses_with_avoid_on(model):
    from fresing_render.blender import animation, clash
    sc, it = model
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Move", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Lift", 0.0, 1.0, "LINEAR"
    b.use_from, b.to_dist = True, -0.4
    assert not animation.bake(sc, a)["warnings"]
    sc.frame_set(sc.frame_end)
    assert block_gap(sc, it) < -0.05                                     # Avoid off: through the block
    sc.fresing.clash.hoses = True
    rows = [r for r in clash.check(sc, store=False).rows if it.part.name in r.names]
    assert not rows                                                      # it bends through on purpose: not listed
