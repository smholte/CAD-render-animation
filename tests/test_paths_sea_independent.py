"""Task 0081, independent tests (written by a tester who did not write the code, from the brief): try to break the
catenary (fresing_render/core/catenary.py), the sea end (blender/paths_sea.py) and the things riding on the cable
(blender/paths_riders.py).

Faults found are kept as ``xfail(strict=True)`` tests: they pass while the fault is there and fail once it is fixed
(then drop the mark). Model: tests/data/test_sea.step set up by ``paths_sea.set_up_test_model`` (15 m of water,
layback 20 m, 40 m on the seabed, the CPS set passing the horn at 1 m paid out, 60 m/min for 8 s).
"""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import catenary as C

U = np.array([-1.0, 0.0, 0.0])          # laid aft (−x)
ZB = -30.0


def poly_length(p):
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def one(res, k):
    return {key: (v[k:k + 1] if isinstance(v, np.ndarray) and v.shape[:1] == res["kind"].shape else v)
            for key, v in res.items()}


def dense(res, k=0, n=200001):
    lam = np.linspace(0.0, float(res["L"][k]), n)
    return C.points(one(res, k), lam[None])[0]


def hang1(T, S, L, zb=ZB, u=U):
    return C.hang(np.array([T], dtype=float), np.array(S, dtype=float), np.asarray(u, dtype=float), zb,
                  np.array([L], dtype=float))


def check_exact(res, zb, k=0, tol_per_100m=1e-4):
    """The drawn line through the solved shape: its length, its ends, nothing under the seabed, no NaN."""
    p = dense(res, k)
    L = float(res["L"][k])
    assert np.isfinite(p).all()
    assert abs(poly_length(p) - L) <= tol_per_100m * max(L, 1.0) / 100.0 + 2e-6, (poly_length(p), L)
    assert np.linalg.norm(p[0] - res["T"][k]) < 1e-5
    assert np.linalg.norm(p[-1] - res["S"][k]) < 1e-5
    assert p[:, 2].min() >= zb - 1e-6
    assert abs(res["laid"][k] + res["suspended"][k] - L) < 1e-6
    return p


# =============================================================================
# core/catenary.py: lengths at extreme numbers
# =============================================================================

@pytest.mark.parametrize("T, S, zb, L, kind", [
    ((0, 0, 0.2), (-30, 0, -0.3), -0.3, 30.2, C.NORMAL),            # 0.5 m of water
    ((0, 0, 0.2), (-30, 0, -0.3), -0.3, 31.0, C.PILED),             # … a little too much cable
    ((0, 0, 3), (-300, 0, -500), -500, 700.0, C.NORMAL),            # 500 m deep
    ((0, 0, 3), (-300, 0, -500), -500, 600.0, C.LIFTED),            # … tight
    ((0, 0, 3), (-20000, 0, -30), -30, 20010.0, C.NORMAL),          # 20 km on the seabed, slack
    ((0, 0, 3), (-20000, 0, -30), -30, 20000.04, C.NORMAL),         # … very tight (a ≈ 5e6 m)
    ((0, 0, 3), (-100, 80, -30), -30, 140.0, C.NORMAL),             # the hang-off far to the side of the lay line
    ((0, 0, 3), (-100, 80, -30), -30, 135.0, C.NORMAL),
    ((0, 0, 3), (-10, 60, -30), -30, 200.0, C.PILED),               # to the side and far too much
    ((5, -3, 40), (-2, 1, -100), -100, 140.5, C.LIFTED),
    ((5, -3, 40), (-2, 1, -100), -100, 144.0, C.NORMAL),            # high hang-off, short layback
])
def test_length_exact_at_extreme_numbers(T, S, zb, L, kind):
    res = hang1(T, S, L, zb)
    assert int(res["kind"][0]) == kind
    # (a piled cable's snake on the seabed is itself a polyline of 2,049 points: sampled densely it reads a
    # little short at its corners – a warned case)
    check_exact(res, zb, tol_per_100m=1e-3 if kind == C.PILED else 1e-4)
    for key in ("a", "suspended", "laid", "layback", "angle", "direction", "tdp", "excess"):
        assert np.isfinite(res[key]).all(), key


def test_lifted_near_the_straight_line_keeps_its_length():
    h, X0 = 33.0, 80.0
    line = math.hypot(X0, h)
    for eps in (1e-3, 1e-5, 1e-7):
        res = hang1((0, 0, 3), (-80, 0, ZB), line + eps)
        assert int(res["kind"][0]) == C.LIFTED
        check_exact(res, ZB)


def test_stretched_is_warned_by_its_excess():
    """Shorter than the straight line: drawn straight, the missing length is in ``excess`` (negative)."""
    res = hang1((0, 0, 3), (-300, 0, -500), 583.4, -500)
    assert int(res["kind"][0]) == C.STRETCHED
    p = dense(res)
    assert float(res["excess"][0]) == pytest.approx(583.4 - float(res["line"][0]), abs=1e-9)
    assert np.isfinite(p).all() and p[:, 2].min() >= -500 - 1e-9


def test_points_returns_exactly_the_ends_for_every_kind():
    cases = [((0, 0, 3), (-80, 0, ZB), L) for L in (86.6, 87.5, 88.5, 100.0, 113.5, 150.0)]
    cases.append(((0, 0, 3), (-80, 0, ZB), 80.0))                   # stretched
    for T, S, L in cases:
        res = hang1(T, S, L)
        p = C.points(res, np.array([[0.0, L]]))[0]
        assert np.linalg.norm(p[0] - np.array(T)) < 1e-6, (L, C.KINDS[int(res["kind"][0])])
        assert np.linalg.norm(p[1] - res["S"][0]) < 1e-6, (L, C.KINDS[int(res["kind"][0])])


def test_no_nan_over_a_wide_grid():
    rng = np.random.default_rng(81)
    F = 400
    T = np.zeros((F, 3))
    T[:, 0] = rng.uniform(-50, 50, F)
    T[:, 1] = rng.uniform(-50, 50, F)
    T[:, 2] = rng.uniform(-29.9, 60, F)                    # some hang-offs just above the seabed
    S = np.array([-60.0, 10.0, ZB])
    L = rng.uniform(0.0, 400.0, F)
    res = C.hang(T, S, U, ZB, L)
    for key in ("a", "suspended", "laid", "layback", "angle", "direction", "tdp", "excess"):
        assert np.isfinite(res[key]).all(), key
    lam = L[:, None] * np.linspace(0.0, 1.0, 33)[None]
    pts = C.points(res, lam)
    assert np.isfinite(pts).all()
    assert np.linalg.norm(pts[:, 0] - T, axis=1).max() < 1e-5
    assert np.linalg.norm(pts[:, -1] - res["S"], axis=1).max() < 1e-5


def test_hang_off_under_the_seabed_does_not_blow_up():
    res = hang1((0, 0, -40), (-60, 0, ZB), 80.0)
    p = C.points(res, np.linspace(0, 80.0, 50)[None])
    assert np.isfinite(p).all()


# =============================================================================
# continuity across the boundaries, monotonic payout
# =============================================================================

def scan(T, S, L):
    F = len(L)
    return C.hang(np.tile(np.asarray(T, dtype=float), (F, 1)), np.asarray(S, dtype=float), U, ZB, L)


@pytest.mark.parametrize("S", [(-80.0, 0.0, ZB), (-60.0, 25.0, ZB)])
def test_continuous_across_normal_lifted_piled(S):
    """Paying out with the vessel standing still: lifted → touching down → piled. The departure angle, the
    touch-down and points along the cable move by small steps (no jump at a boundary); the laid part never
    shrinks. (The stretched boundary is a square-root corner by nature and is left out.)"""
    T = (0.0, 0.0, 3.0)
    S = np.array(S)
    h = 3.0 - ZB
    line = math.hypot(np.linalg.norm(S[:2]), h)
    L = np.linspace(line + 0.5, line + 60.0, 6001)
    dL = L[1] - L[0]
    res = scan(T, S, L)
    kinds = set(int(k) for k in res["kind"])
    assert {C.NORMAL, C.LIFTED, C.PILED} <= kinds
    assert np.degrees(np.abs(np.diff(res["angle"]))).max() < 0.5
    assert np.linalg.norm(np.diff(res["tdp"], axis=0), axis=1).max() < 200 * dL
    assert np.abs(np.diff(res["layback"])).max() < 200 * dL
    assert (np.diff(res["laid"]) >= -1e-9).all()
    lam = L[:, None] * np.array([0.25, 0.5, 0.75])[None]
    sub = slice(None, None, 3)
    pts = C.points({k: (v[sub] if isinstance(v, np.ndarray) and v.shape[:1] == (len(L),) else v)
                    for k, v in res.items()}, lam[sub])
    step = np.linalg.norm(np.diff(pts, axis=0), axis=2).max()
    assert step < 0.2, step


def test_more_payout_with_the_vessel_moving_aft_keeps_the_end_still():
    """The seabed's end S never moves (it is the input) and laid = advance + what was there when the vessel
    advances exactly as much as is paid out."""
    F = 50
    adv = np.linspace(0.0, 30.0, F)
    T = np.zeros((F, 3))
    T[:, 0] = -adv * U[0]                                   # the hang-off moves forward over the seabed
    T[:, 2] = 3.0
    S = np.array([-100.0, 0.0, ZB])
    L0 = 120.0
    res = C.hang(T, S, U, ZB, L0 + adv)
    assert (res["kind"] == C.NORMAL).all()
    assert np.allclose(res["laid"] - res["laid"][0], adv, atol=1e-6)
    assert np.allclose(res["layback"], res["layback"][0], atol=1e-6)


# =============================================================================
# leaving the wheel (hang_off) and setting the touch-down (anchor)
# =============================================================================

def wheel(axis, side, *, u=(-1.0, 0.0, 0.0), r=1.5, wmax=math.radians(100.0), L0=95.0, S=None, arrive=None,
          centre=(0.0, 0.0, 2.0)):
    c = np.array([centre], dtype=float)
    ar = np.array([arrive if arrive is not None else (centre[0], centre[1], centre[2] + r)], dtype=float)
    u = np.array(u, dtype=float)
    S = np.array(centre) + 80.0 * u if S is None else np.array(S, dtype=float)
    return C.hang_off(c, np.array([axis], dtype=float), r, side, ar, wmax, S, u, ZB, np.array([L0]))


def _lay_ways():
    """(lay direction, wheel axis whose positive turn carries the cable that way from the top)."""
    out = []
    for ang in (0.0, 37.0, 90.0, 180.0, 251.0):
        a = math.radians(ang)
        u = np.array([math.cos(a), math.sin(a), 0.0])
        axis = np.cross(np.array([0.0, 0.0, 1.0]), u)       # k x rho(top) = u  ⇔  k = z × u
        out.append((u, axis))
    return out


@pytest.mark.parametrize("flip", [False, True])
@pytest.mark.parametrize("k", range(5))
def test_wheel_tangent_any_lay_direction_and_axis_sign(k, flip):
    """The same wheel given as (axis, +1) or (−axis, −1): the same leave point; no kink; T on the wheel's rim;
    the bookkeeping r ψ + L = L0."""
    u, axis = _lay_ways()[k]
    ax, side = (-axis, -1) if flip else (axis, 1)
    h = wheel(ax, side, u=u)
    assert not h["steep"][0] and not h["short"][0]
    assert float(h["kink"][0]) < 1e-6
    T = h["T"][0]
    assert np.linalg.norm(T - np.array([0.0, 0.0, 2.0])) == pytest.approx(1.5, abs=1e-9)
    assert float((T[:2]) @ u[:2]) > 0.0                     # leaves on the aft side of the wheel
    assert 1.5 * float(h["psi"][0]) + float(h["L"][0]) == pytest.approx(95.0, abs=1e-9)
    check_exact(h, ZB)


def test_sheave_half_turn_and_steep_chute():
    u, axis = _lay_ways()[0]
    sheave = wheel(axis, 1, u=u, wmax=math.pi)
    assert not sheave["steep"][0] and float(sheave["kink"][0]) < 1e-6
    chute = wheel(axis, 1, u=u, wmax=math.radians(25.0))
    assert chute["steep"][0] and float(chute["psi"][0]) == pytest.approx(math.radians(25.0))
    assert float(chute["kink"][0]) > math.radians(20.0)
    check_exact(chute, ZB)


def test_arrival_not_exactly_on_the_rim():
    """The arrival point 1 % outside the rim: T is still on the rim and the tangent is kept."""
    u, axis = _lay_ways()[0]
    h = wheel(axis, 1, u=u, arrive=(0.0, 0.0, 2.0 + 1.5 * 1.01))
    assert np.linalg.norm(h["T"][0] - np.array([0.0, 0.0, 2.0])) == pytest.approx(1.5, abs=1e-9)
    assert float(h["kink"][0]) < 1e-6


def test_anchor_tension_and_layback_agree_and_hang_off_finds_them_again():
    u, axis = _lay_ways()[1]
    c = np.array([[0.0, 0.0, 2.0]])
    ar = c + np.array([0.0, 0.0, 1.5])
    lay = C.anchor(c, axis[None], 1.5, 1, ar, math.radians(100.0), u, ZB, layback=30.0, laid=40.0)
    ten = C.anchor(c, axis[None], 1.5, 1, ar, math.radians(100.0), u, ZB, a=float(lay["a"][0]), laid=40.0)
    assert np.allclose(lay["start"], ten["start"], atol=1e-9)
    assert np.allclose(lay["length0"], ten["length0"], atol=1e-9)
    h = C.hang_off(c, axis[None], 1.5, 1, ar, math.radians(100.0), lay["start"][0], u, ZB, lay["length0"])
    assert float(h["layback"][0]) == pytest.approx(30.0, abs=1e-6)
    assert float(h["laid"][0]) == pytest.approx(40.0, abs=1e-6)
    assert float(h["kink"][0]) < 1e-6
    # paying out 25 m with the vessel 25 m further on: the same shape, 25 m more on the seabed
    c2 = c - 25.0 * u
    h2 = C.hang_off(c2, axis[None], 1.5, 1, ar - 25.0 * u, math.radians(100.0), lay["start"][0], u, ZB,
                    lay["length0"] + 25.0)
    assert float(h2["layback"][0]) == pytest.approx(30.0, abs=1e-6)
    assert float(h2["laid"][0]) == pytest.approx(65.0, abs=1e-6)


@pytest.mark.xfail(strict=True, reason="core.catenary.hang: when the hang-off is level with or aft of the cable's "
                   "end on the seabed (xi <= 0) any length is called LIFTED and drawn as a two-point catenary; with "
                   "slack cable that catenary sags many metres under the seabed (23.5 m in 33 m of water) instead of "
                   "piling up")
def test_hang_off_over_the_end_never_goes_under_the_seabed():
    for S in ((0.0, 0.0, ZB), (10.0, 0.0, ZB)):
        res = hang1((0, 0, 3), S, 80.0)
        p = dense(res, n=20001)
        assert p[:, 2].min() >= ZB - 1e-6, (S, p[:, 2].min() - ZB)


# =============================================================================
# in Blender (as a Python module)
# =============================================================================

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_sea.step")


def _bpy():
    return pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def addon():
    bpy = _bpy()
    import addon_utils
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("sea independent"))


@pytest.fixture()
def sea(addon, folder):
    bpy = _bpy()
    import addon_utils
    from fresing_render.blender import paths, paths_sea
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths_sea.set_up_test_model(sc)
    return sc


def update(times=2):
    bpy = _bpy()
    for _ in range(times):
        bpy.context.view_layer.update()


def cable(sc):
    from fresing_render.blender import paths, paths_sea
    return paths.find(sc, paths_sea.TEST_CABLE)


def named(sc, name, k=0):
    from fresing_render.blender import build
    return [o for o in sc.objects if o.get(build.PROP_NAME) == name][k]


def set_pay(sc, metres):
    """Pay out ``metres`` with the cable joint (live, no animation built)."""
    from fresing_render.blender import joints, paths
    it = cable(sc)
    joints.set_value(joints.find(sc, it.joint), metres * (-1.0 if it.reverse else 1.0), use_limits=False)
    update()
    paths.refresh(sc, force=True)
    update()


def bed_world(sc):
    from fresing_render.blender import paths_sea
    return np.array(paths_sea.bed(sc).matrix_world)


def end_world(sc, it):
    """Where the cable's end on the seabed must be (world): the seabed's place x sea_start."""
    m = bed_world(sc)
    return m[:3, :3] @ np.array(it.sea_start) + m[:3, 3]


def drawn_ok(sc, it):
    from fresing_render.blender import paths
    line = paths.shape_now(sc, it)
    s = paths.lengths_now(sc, it)
    assert len(line) > 10 and np.isfinite(line).all() and np.isfinite(s).all()
    return line, s


def test_tension_mode_gives_the_layback_mode_shape(sea):
    from fresing_render.blender import paths_sea
    sc = sea
    it = cable(sc)
    before, _s = drawn_ok(sc, it)
    n = paths_sea.numbers(sc, it)
    start, mark = np.array(it.sea_start), it.sea_mark
    it.sea_tension = n["bottom"]                            # (a TENSION setting while in LAYBACK: re-anchors the same)
    it.sea_mode = "TENSION"
    it = cable(sc)
    after, _s = drawn_ok(sc, it)
    n2 = paths_sea.numbers(sc, it)
    assert n2["layback"] == pytest.approx(20.0, abs=1e-3)
    assert np.allclose(np.array(it.sea_start), start, atol=1e-3) and it.sea_mark == pytest.approx(mark, abs=1e-3)
    assert len(after) == len(before) and np.abs(after - before).max() < 1e-3


@pytest.mark.parametrize("what, value", [("sea_depth", 25.0), ("sea_layback", 32.0), ("sea_laid", 5.0)])
def test_changing_a_setting_anchors_again(sea, what, value):
    from fresing_render.blender import paths_sea
    sc = sea
    it = cable(sc)
    setattr(it, what, value)
    it = cable(sc)
    n = paths_sea.numbers(sc, it)
    line, s = drawn_ok(sc, it)
    want = {"sea_depth": (25.0, 20.0, 40.0), "sea_layback": (15.0, 32.0, 40.0), "sea_laid": (15.0, 20.0, 5.0)}[what]
    assert n["depth"] == pytest.approx(want[0])
    assert n["layback"] == pytest.approx(want[1], abs=1e-3) and n["laid"] == pytest.approx(want[2], abs=1e-3)
    assert line[-1][2] == pytest.approx(-want[0] + (0.5 - paths_sea.SINK) * it.diameter, abs=1e-3)
    assert np.linalg.norm(line[-1] - end_world(sc, it)) < 1e-3
    assert abs(float(np.linalg.norm(np.diff(line, axis=0), axis=1).sum()) - (s[-1] - s[0])) < 0.01


def test_lay_mode_keeps_the_layback_and_the_end_still(sea):
    """Paying out with the lay: the seabed moves aft as much as is paid out, the laid end moves with the seabed,
    the layback stays, the laid part grows by the payout."""
    from fresing_render.blender import paths_sea
    sc = sea
    it = cable(sc)
    e0, b0 = end_world(sc, it), bed_world(sc)[:3, 3]
    for pay in (2.5, 7.0, -1.0):
        set_pay(sc, pay)
        it = cable(sc)
        n = paths_sea.numbers(sc, it)
        assert n["layback"] == pytest.approx(20.0, abs=1e-3), pay
        assert n["laid"] == pytest.approx(40.0 + pay, abs=1e-3), pay
        moved = bed_world(sc)[:3, 3] - b0
        assert np.linalg.norm(moved) == pytest.approx(abs(pay), abs=1e-4)
        line, _s = drawn_ok(sc, it)
        assert np.linalg.norm(line[-1] - (e0 + moved)) < 1e-3


def _reversed_pays_out(sc, sync_first):
    from fresing_render.blender import joints, paths_sea
    it = cable(sc)
    it.reverse = True
    if sync_first:
        paths_sea.sync_bed(sc)                              # (what Build does)
    it = cable(sc)
    set_pay(sc, 4.0)
    it = cable(sc)
    assert joints.get_value(joints.find(sc, it.joint)) == pytest.approx(-4.0)
    assert paths_sea.payout(sc, it) == pytest.approx(4.0)
    moved = bed_world(sc)[:3, 3] - np.array([0.0, 0.0, paths_sea.waterline(sc)])
    assert np.allclose(moved, 4.0 * np.array(it.sea_dir), atol=1e-4), moved          # aft, not forward
    n = paths_sea.numbers(sc, it)
    assert n["layback"] == pytest.approx(20.0, abs=1e-3) and n["laid"] == pytest.approx(44.0, abs=1e-3)


def test_reversed_cable_joint_pays_out_the_same_once_the_seabed_is_synced(sea):
    _reversed_pays_out(sea, sync_first=True)


@pytest.mark.xfail(strict=True, reason="paths_sea: ticking 'Runs the other way' on a cable into the sea does not "
                   "set the seabed's driver again (its sign stays): paying out then moves the seabed FORWARD, and the "
                   "catenary collapses (layback 1.6 m instead of 20 m after 4 m) until Build or a sea setting changes")
def test_reversed_cable_joint_pays_out_the_same(sea):
    _reversed_pays_out(sea, sync_first=False)


def test_forget_then_redraw_draws_the_same(sea):
    from fresing_render.blender import paths, paths_sea
    sc = sea
    set_pay(sc, 3.0)
    it = cable(sc)
    before, _s = drawn_ok(sc, it)
    n0 = paths_sea.numbers(sc, it)
    paths.forget()
    assert paths_sea.numbers(sc, it) != {}                  # (from the stored sea_info)
    paths.refresh(sc, force=True)
    paths.changed(sc, cable(sc))
    it = cable(sc)
    after, _s = drawn_ok(sc, it)
    assert np.abs(after - before).max() < 1e-4
    assert paths_sea.numbers(sc, it)["layback"] == pytest.approx(n0["layback"], abs=1e-4)


def test_from_cad_cable_again_keeps_the_sea_end(sea):
    from fresing_render.blender import paths, paths_riders, paths_sea
    sc = sea
    it = cable(sc)
    it.sea_layback = 24.0
    it = cable(sc)
    before, _s = drawn_ok(sc, it)
    paths.read_cad(sc, it, named(sc, "CABLE"))
    it = cable(sc)
    assert it.b_kind == "SEA" and it.problem == ""
    assert paths_sea.numbers(sc, it)["layback"] == pytest.approx(24.0, abs=1e-3)
    after, _s = drawn_ok(sc, it)
    assert np.linalg.norm(after[-1] - before[-1]) < 1e-3
    assert len(it.riders) == 1 and all(p.part.modifiers.get(paths_riders.MOD) for p in it.riders[0].parts)


def test_removing_the_cable_cleans_up(sea):
    from fresing_render.blender import paths, paths_riders, paths_sea
    sc = sea
    set_pay(sc, 3.0)
    it = cable(sc)
    parts = [p.part for p in it.riders[0].parts]
    paths.remove(sc, paths.index_of(sc, it))
    update()
    assert paths.find(sc, paths_sea.TEST_CABLE) is None
    assert all(p.modifiers.get(paths_riders.MOD) is None for p in parts)
    assert not any(o.name.startswith(paths_riders.RUN) for o in sc.objects)
    ob = paths_sea.bed(sc)
    if ob is not None:                                      # the seabed motion: back home, no drivers
        assert np.linalg.norm(np.array(ob.matrix_world)[:2, 3]) < 1e-9
        assert ob.animation_data is None or not len(ob.animation_data.drivers)


def test_removing_the_hang_off_contact_says_so(sea):
    """The horn taken off a cable into the sea: no crash, the cable says what is missing (or the app refuses)."""
    from fresing_render.blender import paths
    sc = sea
    it = cable(sc)
    k = [c.name for c in it.contacts].index("HORN")
    try:
        paths.remove_contact(sc, it, k)
    except paths.PathError:
        return
    it = cable(sc)
    paths.refresh(sc, force=True)
    it = cable(sc)
    line = paths.shape_now(sc, it)
    assert np.isfinite(line).all()
    if not [c for c in it.contacts if c.kind in ("SHEAVE", "CHUTE", "BEND")]:
        assert it.problem != ""


def test_built_animation_then_a_setting_changed_redraws_every_frame(sea):
    """With the animation built, a new layback: every frame is drawn again from the places read at Build (the
    solver at that frame, <= 1 mm), with the new layback."""
    from fresing_render.blender import animation, paths, paths_sea
    sc = sea
    animation.bake(sc, sc.fresing.animations[paths_sea.TEST_ANIMATION])
    sc.frame_set(sc.frame_start)
    it = cable(sc)
    it.sea_layback = 26.0
    it = cable(sc)
    stored = paths._stored_places(sc, it, paths._inputs_of(it)[1])
    assert stored is not None
    rel, first = stored
    for f in (sc.frame_start, sc.frame_end):
        sc.frame_set(f)
        it = cable(sc)
        res = paths._solve_item(sc, it, rel[f - first:f - first + 1])
        want = paths._at(paths._world(it.part), res["points"][0])
        got = paths.shape_now(sc, it)
        assert np.abs(got - want).max() < 1e-3, f
        assert paths_sea.numbers(sc, it)["layback"] == pytest.approx(26.0, abs=1e-3), f


def test_too_much_cable_piles_and_is_warned(sea):
    """Paying out 16 m while the vessel sails 0.4 m (Weather & time 0.1 kn): it piles up under the horn, the
    panel says so, nothing under the seabed."""
    from fresing_render.blender import animation, paths_sea
    sc = sea
    it = cable(sc)
    it.sea_laid = 0.0
    it.sea_layback = 3.0
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 0.1
    it = cable(sc)
    it.sea_speed = "WEATHER"
    a = s.animations[paths_sea.TEST_ANIMATION]
    a.blocks[0].speed_mmin = 120.0
    r = animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    it = cable(sc)
    n = paths_sea.numbers(sc, it)
    assert n["kind"] == C.PILED
    assert "piles up" in it.problem or any("piles up" in w for w in r["warnings"])
    line, _sl = drawn_ok(sc, it)
    assert line[:, 2].min() >= -15.0 - 1e-3


@pytest.mark.xfail(strict=True, reason="paths_sea: cable piled on the seabed is drawn with only N_PILED = 64 points "
                   "while its snake has a wave every 4 m: the drawn line is metres shorter than the cable it stands "
                   "for (19 m short for 167 m piled over 40 m), so the stripes stretch and the tube cuts corners")
def test_piled_cable_drawn_with_its_length(addon):
    from fresing_render.blender import paths_sea
    r = C.hang(np.array([[0.0, 0.0, 3.0]]), np.array([-40.0, 0.0, ZB]), U, ZB, np.array([200.0]))
    assert int(r["kind"][0]) == C.PILED
    s = float(r["suspended"][0])
    lam = s + (200.0 - s) * np.arange(0, paths_sea.N_PILED + 1) / paths_sea.N_PILED
    p = C.points(r, lam[None])[0]
    assert poly_length(p) == pytest.approx(200.0 - s, rel=0.01)


@pytest.mark.xfail(strict=True, reason="paths_sea: the seabed's motion takes Weather & time's vessel speed only "
                   "when a sea setting changes or at Build: changing the vessel speed (the wake follows at once) "
                   "leaves the seabed moving at the old speed in the view")
def test_weather_vessel_speed_change_moves_the_seabed_at_the_new_speed(sea):
    sc = sea
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 1.0
    it = cable(sc)
    it.sea_speed = "WEATHER"
    s.weather.vessel_speed = 4.0
    update()
    sc.frame_set(sc.frame_start + 50)
    update()
    adv = np.linalg.norm(bed_world(sc)[:2, 3])
    assert adv == pytest.approx(4.0 * 0.514444 * 50 / sc.render.fps, rel=1e-3)


@pytest.mark.xfail(strict=True, reason="paths_sea: with Weather & time switched off the seabed of a 'Vessel speed of "
                   "Weather & time' cable keeps moving with the clock (its driver is not set back to the lay) until "
                   "a sea setting changes or Build")
def test_weather_off_falls_back_to_the_lay(sea):
    sc = sea
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 2.0
    it = cable(sc)
    it.sea_speed = "WEATHER"
    s.weather.enabled = False
    update()
    sc.frame_set(sc.frame_start + 50)
    update()
    assert np.linalg.norm(bed_world(sc)[:2, 3]) < 1e-6       # nothing paid out: the seabed stays


def test_vessel_motion_moves_the_hang_off_not_the_seabed(sea):
    """Vessel motion on (Sea, Rough): the horn heaves and rolls, the cable's end on the seabed stays where the
    seabed has it, at every frame, and the touch-down lies on the seabed."""
    from fresing_render.blender import animation, paths_sea, vessel_motion, world
    sc = sea
    s = sc.fresing
    s.background, s.sea_state, s.env_detail = "SEA", "ROUGH", "SIMPLE"
    s.vessel.enabled = True
    world.apply(sc, s)
    vessel_motion.sync(sc)
    update()
    animation.bake(sc, s.animations[paths_sea.TEST_ANIMATION])
    it = cable(sc)
    assert it.moving
    tops = []
    for f in range(sc.frame_start, sc.frame_end + 1, 40):
        sc.frame_set(f)
        it = cable(sc)
        line, _s = drawn_ok(sc, it)
        assert np.linalg.norm(line[-1] - end_world(sc, it)) < 2e-3, f
        bz = paths_sea.waterline(sc) - paths_sea.depth(sc, it) + (0.5 - paths_sea.SINK) * it.diameter
        assert abs(line[-1][2] - bz) < 2e-3, f
        top, tdp = paths_sea.tdp_world(sc, it)
        assert abs(tdp[2] - bz) < 2e-3, f
        tops.append(top)
    assert np.ptp(np.array(tops), axis=0).max() > 0.02      # the hang-off moves with the vessel


def _rider(sc):
    it = cable(sc)
    return it, it.riders[0]


def _part_mid_world(sc, it, p):
    """Where the part's own middle (its CAD middle) is drawn now (world)."""
    from fresing_render.blender import paths_riders
    M = paths_riders.matrix_now(sc, it, p.part)
    r0 = np.array(p["fr_r0"]).reshape(4, 4)
    local = np.linalg.inv(r0) @ np.append(np.array(p["fr_mid"]), 1.0)
    return (M @ local)[:3], M


def _at_s(line, s, want):
    k = int(np.clip(np.searchsorted(s, want) - 1, 0, len(s) - 2))
    t = (want - s[k]) / max(s[k + 1] - s[k], 1e-12)
    return line[k] + np.clip(t, 0.0, 1.0) * (line[k + 1] - line[k])


def _check_rider_on_chords(sc, front, tol=2e-3):
    """Each part's middle on the middle of its chord, at s = front − at − length … front − at (+ paid out), with
    ``front`` the mark of the rider's front (metres along the cable, nothing paid out)."""
    from fresing_render.blender import paths, paths_sea
    update()
    it, r = _rider(sc)
    line = paths.shape_now(sc, it)
    s = paths.lengths_now(sc, it)
    pay = paths_sea.payout(sc, it)
    mids = []
    for p in r.parts:
        sa = front - p.at - p.length + pay
        a, b = _at_s(line, s, sa), _at_s(line, s, sa + p.length)
        got, _M = _part_mid_world(sc, it, p)
        assert np.isfinite(got).all()
        assert np.linalg.norm(got - 0.5 * (a + b)) < tol, (p.part.name, float(np.linalg.norm(got - 0.5 * (a + b))))
        mids.append(got)
    return np.array(mids)


def _front(sc):
    from fresing_render.blender import paths_riders
    it, r = _rider(sc)
    return paths_riders.mark_of(sc, it, r)


def _horn_distance(sc, front):
    """How far the rider's front point on the cable is from the horn's axis (m)."""
    from fresing_render.blender import paths, paths_sea
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import make_test_sea as maker
    it = cable(sc)
    line, s = paths.shape_now(sc, it), paths.lengths_now(sc, it)
    q = _at_s(line, s, front + paths_sea.payout(sc, it))
    c = np.array(maker.NUMBERS["horn_centre"]) / 1000.0
    return float(np.hypot(q[0] - c[0], q[2] - c[2]))


def test_rider_by_mark_passes_the_horn_when_paid_out(sea):
    """'At a payout mark' 1 m: its front reaches the horn when 1 m is paid out (on the horn's bend), and every
    part lies on its chord before, then and after (down the catenary)."""
    sc = sea
    front = _front(sc)
    R = 2.0                                                 # the cable's bend radius round the horn
    for pay in (0.0, 1.0, 6.0):
        set_pay(sc, pay)
        _check_rider_on_chords(sc, front)
        if pay == 1.0:
            assert abs(_horn_distance(sc, front) - R) < 0.02


@pytest.mark.xfail(strict=True, reason="paths_riders.mark_of subtracts the payout of the moment (_hang_mark, "
                   "_cable_end_mark): a rider edited, added or read again (model update) while cable is paid out "
                   "gets a front mark shifted by that payout – at 3 m paid out the CPS set jumps 3 m along the cable")
def test_rider_mark_does_not_depend_on_the_payout_when_it_is_set(sea):
    from fresing_render.blender import paths_riders
    sc = sea
    front = _front(sc)
    set_pay(sc, 3.0)
    it, r = _rider(sc)
    paths_riders.changed(sc, r)                             # (any rider setting edited at this pose)
    assert _front(sc) == pytest.approx(front, abs=1e-3)
    _check_rider_on_chords(sc, front)


def test_rider_from_the_end_lies_on_the_catenary_and_the_seabed(sea):
    sc = sea
    it, r = _rider(sc)
    r.where, r.at = "END", 45.0                             # 5 m before the touch-down: on the catenary
    front = _front(sc)
    it = cable(sc)
    assert front == pytest.approx(it.sea_mark - 45.0, abs=1e-6)
    mids = _check_rider_on_chords(sc, front)
    assert mids[:, 2].max() < 0.0 and np.ptp(mids[:, 2]) > 0.3          # hanging, not lying
    it, r = _rider(sc)
    r.at = 20.0                                             # on the seabed
    front = _front(sc)
    mids = _check_rider_on_chords(sc, front)
    on_vertebrae = [k for k, p in enumerate(r.parts) if p.part.get("fr_name", p.part.name).startswith("VERTEBRA")
                    or p.part.name.startswith("VERTEBRA")]
    assert np.allclose(mids[on_vertebrae, 2], mids[on_vertebrae[0], 2], atol=0.01)
    set_pay(sc, 5.0)                                        # it lies still on the seabed while the seabed moves
    mids2 = _check_rider_on_chords(sc, front)
    moved = mids2 - mids
    assert np.allclose(moved, moved[0], atol=2e-3) and np.linalg.norm(moved[0]) == pytest.approx(5.0, abs=2e-3)


def test_rider_turned_round_points_the_other_way(sea):
    from fresing_render.blender import paths_riders
    sc = sea
    it, r = _rider(sc)
    r.where, r.at = "END", 45.0
    it, r = _rider(sc)
    tube = named(sc, "CPS TUBE")
    p = [q for q in r.parts if q.part == tube][0]
    update()
    _m, M0 = _part_mid_world(sc, it, p)
    r.flip = True
    it, r = _rider(sc)
    _check_rider_on_chords(sc, _front(sc))
    p = [q for q in r.parts if q.part == tube][0]
    _m, M1 = _part_mid_world(sc, it, p)
    # the tube's long axis (in its own coordinates) points the other way along the cable now
    r0 = np.array(p["fr_r0"]).reshape(4, 4)
    own = np.linalg.inv(r0[:3, :3]) @ np.array([1.0, 0.0, 0.0])      # (the CPS axis is CAD x: maker NUMBERS)
    a0, a1 = M0[:3, :3] @ own, M1[:3, :3] @ own
    assert float(a0 @ a1) / (np.linalg.norm(a0) * np.linalg.norm(a1)) < -0.99
    assert paths_riders.describe(sc, it, r)


def test_single_part_rider_and_a_rider_past_the_end(sea):
    from fresing_render.blender import paths, paths_riders
    sc = sea
    it = cable(sc)
    paths_riders.remove(sc, it, 0)
    it = cable(sc)
    ring = named(sc, "VERTEBRA", 2)
    r = paths_riders.add(sc, it, [ring], where="END", at=45.0, name="One ring")
    assert len(r.parts) == 1
    _check_rider_on_chords(sc, _front(sc))
    it, r = _rider(sc)
    r.at = -10.0                                            # 10 m past the cable's end: waits at the end
    update()
    it, r = _rider(sc)
    got, _M = _part_mid_world(sc, it, r.parts[0])
    assert np.isfinite(got).all()
    line = paths.shape_now(sc, it)
    assert np.linalg.norm(got - line[-1]) < 1.0
    with pytest.raises(paths_riders.RiderError):            # a part already riding cannot ride twice
        paths_riders.add(sc, it, [ring], where="END", at=10.0)


def _rider_without_sea_end(sc, sync):
    from fresing_render.blender import paths_riders, paths_sea
    paths_sea.remove_sea_end(sc, cable(sc))
    it, r = _rider(sc)
    assert it.b_kind == "FIXED"
    if sync:
        paths_riders.sync(sc, it)
    front = _front(sc)
    for pay in (0.0, 1.0):
        set_pay(sc, pay)
        _check_rider_on_chords(sc, front)


def test_rider_on_a_cable_without_a_sea_end(sea):
    sc = sea
    _rider_without_sea_end(sc, sync=True)
    set_pay(sc, 0.0)
    it, r = _rider(sc)
    r.where, r.at = "END", 3.0
    _check_rider_on_chords(sc, _front(sc))


@pytest.mark.xfail(strict=True, reason="paths_riders: a rider 'at a payout mark' keeps the front mark it had when "
                   "it was last synced; removing the sea end changes where the cable leaves the horn (the mark "
                   "_hang_mark gives now) but the riders are not placed again: the CPS set sits 0.93 m off its place")
def test_rider_follows_when_the_sea_end_is_removed(sea):
    _rider_without_sea_end(sea, sync=False)


def test_weather_speed_equal_to_the_lay_keeps_the_touch_down(sea):
    """Weather & time's vessel speed = the lay speed (60 m/min = 1.944 kn): built, the layback stays, the laid part
    grows by the advance, the seabed moves by speed x time."""
    from fresing_render.blender import animation, paths_sea
    sc = sea
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 1.0 / 0.514444
    it = cable(sc)
    it.sea_speed = "WEATHER"
    r = animation.bake(sc, s.animations[paths_sea.TEST_ANIMATION])
    assert not [w for w in r["warnings"] if "sea" in w.lower()]
    for f in (sc.frame_start, 100, sc.frame_end):
        sc.frame_set(f)
        it = cable(sc)
        n = paths_sea.numbers(sc, it)
        adv = float(np.linalg.norm(bed_world(sc)[:2, 3]))
        assert adv == pytest.approx((f - sc.frame_start) / 25.0, abs=2e-3), f
        assert n["layback"] == pytest.approx(20.0, abs=0.05), f
        assert n["laid"] == pytest.approx(40.0 + adv, abs=0.05), f


def test_tension_mode_numbers(sea):
    """Bottom tension 6 kN, 30 kg/m: a = H / (w g); the top tension is H + w g h; a heavier cable at the same
    layback only changes the tensions, not the shape."""
    from fresing_render.blender import paths_sea
    sc = sea
    it = cable(sc)
    before, _s = drawn_ok(sc, it)
    it.sea_weight = 30.0                                    # (LAYBACK mode: same shape, other tensions)
    it = cable(sc)
    after, _s = drawn_ok(sc, it)
    assert np.abs(after - before).max() < 1e-3
    it.sea_mode = "TENSION"
    it.sea_tension = 6.0
    it = cable(sc)
    n = paths_sea.numbers(sc, it)
    assert n["bottom"] == pytest.approx(6.0, rel=1e-6)
    assert n["a"] == pytest.approx(6000.0 / (30.0 * C.G), rel=1e-6)
    assert n["top"] - n["bottom"] == pytest.approx(30.0 * C.G * n["height"] / 1000.0, rel=1e-6)
    assert n["layback"] == pytest.approx(float(C.span(n["a"], n["height"])), abs=1e-3)
    drawn_ok(sc, it)


@pytest.mark.parametrize("tension", [0.01, 400.0])
def test_extreme_bottom_tension_draws(sea, tension):
    from fresing_render.blender import paths_sea
    sc = sea
    it = cable(sc)
    it.sea_mode = "TENSION"
    it.sea_tension = tension
    it = cable(sc)
    line, s = drawn_ok(sc, it)
    n = paths_sea.numbers(sc, it)
    assert n["laid"] == pytest.approx(40.0, abs=0.01)       # (4 mm off at 400 kN: a = 2.2 km, the touch-down far out)
    assert line[:, 2].min() >= -15.0 - 1e-3
    assert abs(float(np.linalg.norm(np.diff(line, axis=0), axis=1).sum()) - (s[-1] - s[0])) < 0.02


def test_cut_box_holds_the_touch_down(sea):
    from fresing_render.blender import paths_sea
    sc = sea
    box = paths_sea.cut_box(sc)
    assert box is not None
    top, tdp = paths_sea.tdp_world(sc, cable(sc))
    o, d = np.array(box["origin"]), np.array(box["dir"])
    for q in (top, tdp):
        rel = q[:2] - o
        along, across = float(rel @ d), float(rel @ np.array([-d[1], d[0]]))
        assert 0.0 < along < box["length"] and abs(across) < 0.5 * box["width"]


@pytest.mark.xfail(strict=True, reason="paths_riders: a rider placed 'from the cable's end' is not placed again when "
                   "the sea end is anchored again (layback, laid, depth, mode): its front mark keeps the old sea_mark, "
                   "so the CPS set lands metres away from where it was put (7.8 m after layback 20 -> 30 m, 27.6 m – "
                   "back on the deck – after 'already on the seabed' 40 -> 10 m)")
@pytest.mark.parametrize("what, value", [("sea_layback", 30.0), ("sea_laid", 10.0)])
def test_rider_from_the_end_follows_a_new_touch_down(sea, what, value):
    """A CPS set 45 m from the cable's end, then the touch-down set again: it must stay 45 m from the end."""
    sc = sea
    it, r = _rider(sc)
    r.where, r.at = "END", 45.0
    setattr(cable(sc), what, value)
    it = cable(sc)
    assert _front(sc) == pytest.approx(it.sea_mark - 45.0, abs=1e-6)
    _check_rider_on_chords(sc, _front(sc))


def test_scene_water_depth_is_the_cables_when_its_own_is_0(sea):
    """The cable's own depth 0: the scene's (Sea surroundings) water depth is used, set when the touch-down is."""
    from fresing_render.blender import paths_sea
    sc = sea
    sc.fresing.sea_depth = 22.0
    it = cable(sc)
    it.sea_depth = 0.0
    it = cable(sc)
    n = paths_sea.numbers(sc, it)
    assert n["depth"] == pytest.approx(22.0) and n["layback"] == pytest.approx(20.0, abs=1e-3)
    line, _s = drawn_ok(sc, it)
    assert line[-1][2] == pytest.approx(-22.0 + (0.5 - paths_sea.SINK) * it.diameter, abs=1e-3)


@pytest.mark.xfail(strict=True, reason="paths_sea: a cable that takes its water depth from the Sea surroundings "
                   "(its own depth 0) is not drawn again when the scene's water depth changes: its end stays on the "
                   "old seabed (22 m -> 28 m: the cable ends 6 m above the new seabed)")
def test_scene_water_depth_change_moves_the_cable_to_the_new_seabed(sea):
    from fresing_render.blender import paths, paths_sea
    sc = sea
    sc.fresing.sea_depth = 22.0
    it = cable(sc)
    it.sea_depth = 0.0
    sc.fresing.sea_depth = 28.0
    update()
    paths.refresh(sc)
    update()
    it = cable(sc)
    line, _s = drawn_ok(sc, it)
    assert line[-1][2] == pytest.approx(-28.0 + (0.5 - paths_sea.SINK) * it.diameter, abs=1e-3)
    assert paths_sea.numbers(sc, it)["layback"] == pytest.approx(20.0, abs=1e-3)


def test_rider_switched_off_goes_back_to_its_cad_place(sea):
    from fresing_render.blender import paths_riders
    sc = sea
    set_pay(sc, 4.0)
    it, r = _rider(sc)
    parts = [p.part for p in r.parts]
    r.enabled = False
    update()
    assert all(p.modifiers.get(paths_riders.MOD) is None for p in parts)
    assert paths_riders.rider_parts(sc) == []
    it, r = _rider(sc)
    r.enabled = True
    update()
    assert all(p.modifiers.get(paths_riders.MOD) is not None for p in parts)


def test_removing_the_sea_end_stops_the_seabed(sea):
    from fresing_render.blender import paths_sea
    sc = sea
    paths_sea.remove_sea_end(sc, cable(sc))
    set_pay(sc, 3.0)
    ob = paths_sea.bed(sc)
    assert ob is None or np.linalg.norm(np.array(ob.matrix_world)[:2, 3]) < 1e-9
    assert paths_sea.cut_box(sc) is None


def test_vessel_faster_than_the_lay_lifts_then_stretches_and_says_so(sea):
    """Nothing on the seabed and the vessel sailing twice as fast as the cable is paid out: the cable lifts its end
    off the seabed, then is too short – both are said, nothing is NaN, the end stays on the seabed."""
    from fresing_render.blender import animation, paths_sea
    from fresing_render.core import catenary as C_
    sc = sea
    it = cable(sc)
    it.sea_laid = 0.0
    s = sc.fresing
    s.weather.enabled = True
    s.weather.vessel_speed = 4.0
    it = cable(sc)
    it.sea_speed = "WEATHER"
    r = animation.bake(sc, s.animations[paths_sea.TEST_ANIMATION])
    kinds = set()
    for f in range(sc.frame_start, sc.frame_end + 1, 10):
        sc.frame_set(f)
        it = cable(sc)
        line, _s = drawn_ok(sc, it)
        kinds.add(paths_sea.numbers(sc, it)["kind"])
        assert np.linalg.norm(line[-1] - end_world(sc, it)) < 1e-3, f
    assert {C_.LIFTED, C_.STRETCHED} <= kinds
    said = " ".join(r["warnings"]) + " " + cable(sc).problem
    assert "lifts its end" in said or "too short" in said, said
