"""Independent tests of the hang solver, the reeving and check C10 (task 0232), written from the brief and study 0180
section 3 by a tester that did not write the code. Expectations come from statics and the hand cases, never from the
implementation."""

import math

import numpy as np
import pytest

from fresing_render.core import lifting
from fresing_render.core import lifting_hang as H
from fresing_render.core import lifting_reeve as R

G = lifting.G
Z = np.array([0.0, 0.0, 1.0])


# ------------------------------------------------------------------------------------------------ helpers (own statics)

def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _forces_on(lg):
    """The pull of a leg on its bottom point (towards its top), N."""
    return lg.force * _unit(np.asarray(lg.top) - np.asarray(lg.bottom))


def _check_single_equilibrium(h, mass, rest_points, rest_cog, lengths, tol=1e-4):
    """A rigid load on legs to one hook: forces sum to the weight, no moment about the CoG, CoG under the hook,
    taut legs at their length, slack legs shorter and carrying nothing, the pose rigid."""
    W = mass * G
    assert h.weight == pytest.approx(W, rel=1e-9)
    total = sum((_forces_on(lg) for lg in h.legs), np.zeros(3))
    assert np.allclose(total, W * Z, atol=tol * W), total
    cog = np.asarray(h.cogs[0])
    moment = sum((np.cross(np.asarray(lg.bottom) - cog, _forces_on(lg)) for lg in h.legs), np.zeros(3))
    size = max(np.linalg.norm(np.asarray(p) - np.asarray(rest_cog)) for p in rest_points) + 1.0
    assert np.linalg.norm(moment) < tol * W * size, moment
    assert np.allclose(cog[:2], np.asarray(h.hook)[:2], atol=1e-3)
    assert cog[2] < h.hook[2]
    pose = np.asarray(h.poses[0])
    rot = pose[:3, :3]
    assert np.allclose(rot @ rot.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(rot) == pytest.approx(1.0, abs=1e-9)
    assert np.allclose(pose[:3, :3] @ np.asarray(rest_cog) + pose[:3, 3], cog, atol=1e-6)
    for lg, p, L in zip(h.legs, rest_points, lengths):
        assert np.allclose(pose[:3, :3] @ np.asarray(p, float) + pose[:3, 3], lg.bottom, atol=1e-6)
        d = np.linalg.norm(np.asarray(lg.top) - np.asarray(lg.bottom))
        assert lg.force >= 0.0
        if lg.taut:
            assert d == pytest.approx(L, abs=2e-3)
        else:
            assert lg.force <= 1e-6 * W
            assert d <= L + 1e-6


def _predict(rest_points, rest_cog, hook_b, mass, active=None):
    """Forces and leg angles for a load whose legs all meet at ``hook_b`` (rest frame) – equally stiff legs, the
    slack ones dropped one by one (an active set). Returns (forces N, angles °, up direction in the rest frame)."""
    W = mass * G
    pts = [np.asarray(p, float) for p in rest_points]
    hook_b = np.asarray(hook_b, float)
    up = _unit(hook_b - np.asarray(rest_cog, float))
    u = [_unit(hook_b - p) for p in pts]
    act = list(range(len(pts))) if active is None else list(active)
    while True:
        U = np.array([u[i] for i in act]).T
        # equally stiff legs: T_i = u_i . delta, sum T_i u_i = W up  (least squares = exact when up is in the span)
        delta = np.linalg.pinv(U @ U.T) @ (W * up)
        t = U.T @ delta
        if (t >= -1e-9 * W).all():
            break
        act.pop(int(np.argmin(t)))
    forces = np.zeros(len(pts))
    forces[act] = t
    assert np.allclose(sum(forces[i] * u[i] for i in range(len(pts))), W * up, atol=1e-6 * W)
    angles = [math.degrees(math.acos(np.clip(np.dot(ui, up), -1, 1))) for ui in u]
    return forces, angles, up


# ------------------------------------------------------------------------------------------------ study 0180 C2 and C3

C2_PTS = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)]
C2_COG = (1.5, 0.0, -0.5)
C2_LEN = [math.hypot(1.5, 3.0), math.hypot(2.5, 3.0)]   # 3.3541, 3.9051


def _c2():
    return H.single(10000.0, C2_COG, C2_PTS, C2_LEN, (1.5, 0.0, 3.0), names=["A", "B"])


def test_c2_hand_case_forces_angles_and_horizontals():
    h = _c2()
    assert h.ok and h.stable and not h.rolled and not h.neutral
    a, b = h.leg("A"), h.leg("B")
    assert a.taut and b.taut
    assert a.force / G == pytest.approx(6988.0, rel=0.005)
    assert b.force / G == pytest.approx(4881.0, rel=0.005)
    assert a.angle == pytest.approx(26.57, abs=0.05)
    assert b.angle == pytest.approx(39.81, abs=0.05)
    # both horizontal parts 3.125 t, vertical shares 6.25 / 3.75 t
    fa, fb = _forces_on(a) / G, _forces_on(b) / G
    assert abs(fa[0]) == pytest.approx(3125.0, rel=0.005)
    assert abs(fb[0]) == pytest.approx(3125.0, rel=0.005)
    assert fa[2] == pytest.approx(6250.0, rel=0.005)
    assert fb[2] == pytest.approx(3750.0, rel=0.005)
    assert h.tilts[0] == pytest.approx(0.0, abs=0.05)
    _check_single_equilibrium(h, 10000.0, C2_PTS, C2_COG, C2_LEN)


def test_c2_checks_rows():
    h = _c2()
    rows = H.checks(h, 10000.0, leg_wll=8000.0, shackle_wll=8500.0)
    c2 = [r for r in rows if r.check == "C2"]
    assert len(c2) == 1
    assert c2[0].use == pytest.approx(0.873, abs=0.002)
    assert c2[0].status == lifting.OK          # below the default rigging limit 90 %
    shackles = [r for r in rows if r.check == "C4" and "shackle" in r.title.lower()]
    assert len(shackles) == 2
    assert max(r.use for r in shackles) == pytest.approx(0.822, abs=0.002)
    # with the study's 75 % limit the legs are amber
    rows = H.checks(h, 10000.0, leg_wll=8000.0, limits=lifting.Limits(rigging=0.75))
    assert [r for r in rows if r.check == "C2"][0].status == lifting.AMBER
    # a WLL below the force: red
    rows = H.checks(h, 10000.0, leg_wll=6000.0)
    assert [r for r in rows if r.check == "C2"][0].status == lifting.RED
    # no WLL: not checked, but still a row
    rows = H.checks(h, 10000.0)
    assert [r for r in rows if r.check == "C2"][0].status == lifting.NOT_CHECKED


def test_c2_equal_legs_tilt_against_own_statics():
    """The brief's form of C2: legs of equal length, CoG 1.5 m from A -> the load tilts until the CoG is under the
    hook."""
    L = 3.6
    d = math.sqrt(L * L - 4.0)
    hook_b = (2.0, 0.0, d)                     # rest frame: on the perpendicular bisector, above the line
    h = H.single(10000.0, C2_COG, C2_PTS, [L, L], (0.0, 0.0, 10.0), names=["A", "B"])
    forces, angles, up = _predict(C2_PTS, C2_COG, hook_b, 10000.0)
    assert h.leg("A").force == pytest.approx(forces[0], rel=0.002)
    assert h.leg("B").force == pytest.approx(forces[1], rel=0.002)
    assert h.leg("A").force > h.leg("B").force          # the leg nearer the CoG carries more
    assert h.leg("A").angle == pytest.approx(angles[0], abs=0.05)
    assert h.leg("B").angle == pytest.approx(angles[1], abs=0.05)
    tilt = math.degrees(math.acos(np.dot(up, Z)))
    assert h.tilts[0] == pytest.approx(tilt, abs=0.05)
    assert tilt > 5.0
    _check_single_equilibrium(h, 10000.0, C2_PTS, C2_COG, [L, L])


C3_PTS = [(2.0, 1.5, 0.0), (-2.0, 1.5, 0.0), (-2.0, -1.5, 0.0), (2.0, -1.5, 0.0)]


def test_c3_hand_case_symmetric_four_legs():
    L = math.hypot(2.5, 3.5)                    # 4.3012
    h = H.single(20000.0, (0.0, 0.0, -0.3), C3_PTS, [L] * 4, (0.0, 0.0, 3.5))
    assert h.ok and h.stable
    assert h.tilts[0] == pytest.approx(0.0, abs=0.05)
    for lg in h.legs:
        assert lg.taut
        assert lg.force / G == pytest.approx(6145.0, rel=0.005)     # equal share
        assert lg.angle == pytest.approx(35.54, abs=0.05)
        assert H.design_force(h, lg, 20000.0) / G == pytest.approx(12289.0, rel=0.005)
        assert H.design_force(h, lg, 20000.0, "equalised") / G == pytest.approx(6145.0, rel=0.005)
        assert H.design_force(h, lg, 20000.0, "dnv") / G == pytest.approx(7681.0, rel=0.005)
    rows = H.checks(h, 20000.0, leg_wll=12500.0)
    c3 = [r for r in rows if r.check == "C3"]
    assert len(c3) == 1
    assert c3[0].use == pytest.approx(0.983, abs=0.002)
    assert c3[0].status == lifting.AMBER


def test_c3_seventy_degree_legs_red():
    # legs 70° from vertical: hook height = half diagonal / tan 70°
    hz = 2.5 / math.tan(math.radians(70.0))
    L = 2.5 / math.sin(math.radians(70.0))
    h = H.single(2000.0, (0.0, 0.0, -0.3), C3_PTS, [L] * 4, (0.0, 0.0, hz))
    assert h.legs[0].angle == pytest.approx(70.0, abs=0.1)
    rows = H.checks(h, 2000.0, leg_wll=50000.0)
    assert [r for r in rows if r.check == "C3"][0].status == lifting.RED


def test_three_leg_rigid_rule_two_legs_carry():
    pts = [(2.0, 0.0, 0.0), (-1.0, 1.7320508, 0.0), (-1.0, -1.7320508, 0.0)]
    L = math.hypot(2.0, 3.0)
    h = H.single(9000.0, (0.0, 0.0, -0.4), pts, [L] * 3, (0.0, 0.0, 3.0))
    for lg in h.legs:
        assert lg.force / G == pytest.approx(3000.0 * L / 3.0, rel=0.005)     # equal share, statics
        assert H.design_force(h, lg, 9000.0) / G == pytest.approx(4500.0 * L / 3.0, rel=0.005)
    rows = H.checks(h, 9000.0, leg_wll=10000.0)
    assert len([r for r in rows if r.check == "C3"]) == 1


def test_single_leg_hangs_straight_under_the_hook():
    h = H.single(3000.0, (1.0, 0.5, -0.8), [(0.2, 0.1, 0.0)], [2.0], (5.0, 5.0, 10.0))
    lg = h.legs[0]
    assert lg.force / G == pytest.approx(3000.0, rel=1e-4)
    assert lg.angle == pytest.approx(0.0, abs=0.01)
    assert np.allclose(lg.bottom[:2], (5.0, 5.0), atol=1e-3)
    assert lg.bottom[2] == pytest.approx(8.0, abs=1e-3)
    rows = H.checks(h, 3000.0, leg_wll=2500.0)
    assert any(r.check == "C4" and r.status == lifting.RED for r in rows)


# ------------------------------------------------------------------------------------------------ off-centre 4 legs

def test_off_centre_four_legs_level_pose_elastic_share():
    """Leg lengths cut so the load hangs level with the hook over an off-centre CoG: the shares of four equally stiff
    legs; the legs nearest the CoG carry most."""
    cog = (0.8, 0.4, -0.3)
    hook_b = np.array([0.8, 0.4, 3.0])
    lengths = [float(np.linalg.norm(hook_b - p)) for p in np.array(C3_PTS)]
    h = H.single(20000.0, cog, C3_PTS, lengths, (0.8, 0.4, 3.0))
    forces, angles, _ = _predict(C3_PTS, cog, hook_b, 20000.0)
    got = np.array([lg.force for lg in h.legs])
    assert np.allclose(got, forces, rtol=0.01, atol=0.002 * 20000 * G), (got / G, forces / G)
    assert np.argmax(got) == 0
    assert h.tilts[0] == pytest.approx(0.0, abs=0.05)
    _check_single_equilibrium(h, 20000.0, C3_PTS, cog, lengths)


def test_off_centre_four_equal_legs_tilts():
    cog = (1.0, 0.0, -0.3)
    L = 4.3012
    h = H.single(20000.0, cog, C3_PTS, [L] * 4, (3.0, -2.0, 6.0))
    hook_b = (0.0, 0.0, math.sqrt(L * L - 6.25))
    forces, angles, up = _predict(C3_PTS, cog, hook_b, 20000.0)
    got = np.array([lg.force for lg in h.legs])
    assert np.allclose(got, forces, rtol=0.01, atol=0.002 * 20000 * G), (got / G, forces / G)
    assert h.tilts[0] == pytest.approx(math.degrees(math.acos(up @ Z)), abs=0.1)
    _check_single_equilibrium(h, 20000.0, C3_PTS, cog, [L] * 4)


# ------------------------------------------------------------------------------------------------ random geometries

def _random_case(rng, n):
    if n == 2:
        a = rng.uniform(-3, 3, 3) * (1, 1, 0.1)
        b = a + _unit(rng.uniform(-1, 1, 3) * (1, 1, 0.2)) * rng.uniform(1.5, 5.0)
        pts = np.array([a, b])
        t = rng.uniform(0.2, 0.8)
        side = _unit(np.cross(b - a, np.cross(Z, b - a)))     # in the vertical plane through AB, roughly up
        if side[2] < 0:
            side = -side
        cog = a + t * (b - a) - side * rng.uniform(0.2, 1.0)
        hook_b = a + rng.uniform(0.2, 0.8) * (b - a) + side * rng.uniform(1.5, 4.0)
    else:
        ang = np.sort(rng.uniform(0, 2 * np.pi, n)) if n > 3 else np.array([0, 2.1, 4.2]) + rng.uniform(-0.3, 0.3, 3)
        rad = rng.uniform(1.0, 3.0, n)
        pts = np.stack([rad * np.cos(ang), rad * np.sin(ang), rng.uniform(-0.2, 0.2, n)], axis=1)
        w = rng.uniform(0.5, 1.0, n)
        c = (pts * w[:, None]).sum(0) / w.sum()
        cog = np.array([c[0], c[1], pts[:, 2].min() - rng.uniform(0.1, 1.0)])
        hook_b = np.array([c[0], c[1], 0.0]) + rng.uniform(-0.3, 0.3, 3) * (1, 1, 0) + (0, 0, rng.uniform(2.0, 5.0))
    lengths = [float(np.linalg.norm(hook_b - p)) for p in pts]
    return pts, cog, hook_b, lengths


@pytest.mark.parametrize("n", [2, 3, 4])
def test_random_geometries_match_own_statics(n):
    rng = np.random.default_rng(1000 + n)
    for _ in range(6):
        pts, cog, hook_b, lengths = _random_case(rng, n)
        mass = float(rng.uniform(500.0, 50000.0))
        hook = rng.uniform(-20, 20, 3)
        h = H.single(mass, cog, [tuple(p) for p in pts], lengths, tuple(hook))
        assert h.stable and not h.rolled
        _check_single_equilibrium(h, mass, pts, cog, lengths)
        forces, angles, up = _predict(pts, cog, hook_b, mass)
        got = np.array([lg.force for lg in h.legs])
        assert np.allclose(got, forces, rtol=0.01, atol=0.003 * mass * G), (n, got / G, forces / G)
        for lg, f, a in zip(h.legs, forces, angles):
            if f > 0.01 * mass * G:
                assert lg.angle == pytest.approx(a, abs=0.1)
        assert h.tilts[0] == pytest.approx(math.degrees(math.acos(np.clip(up @ Z, -1, 1))), abs=0.1)


def test_random_slack_extra_lengths_still_in_equilibrium():
    rng = np.random.default_rng(77)
    for n in (3, 4, 4, 3, 4):
        pts, cog, hook_b, lengths = _random_case(rng, n)
        lengths = [L + float(rng.uniform(0, 0.4)) for L in lengths]
        mass = float(rng.uniform(1000.0, 20000.0))
        h = H.single(mass, cog, [tuple(p) for p in pts], lengths, (1.0, 2.0, 8.0))
        _check_single_equilibrium(h, mass, pts, cog, lengths)
        assert sum(lg.taut for lg in h.legs) >= 1


# ------------------------------------------------------------------------------------------------ invariance and scale

def _rot_z(phi):
    c, s = math.cos(phi), math.sin(phi)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


@pytest.mark.parametrize("n", [2, 3])
def test_moving_and_turning_the_whole_set_up(n):
    rng = np.random.default_rng(5 + n)
    pts, cog, hook_b, lengths = _random_case(rng, n)
    hook = np.array([0.5, -0.3, 4.0])
    base = H.single(8000.0, cog, [tuple(p) for p in pts], lengths, tuple(hook))
    v = np.array([123.4, -56.7, 8.9])
    for rot, shift in ((np.eye(3), v), (_rot_z(0.7), np.zeros(3)), (_rot_z(-2.3), v)):
        P = [tuple(rot @ p + shift) for p in pts]
        h = H.single(8000.0, tuple(rot @ cog + shift), P, lengths, tuple(rot @ hook + shift))
        for l0, l1 in zip(base.legs, h.legs):
            assert l1.force == pytest.approx(l0.force, rel=1e-4, abs=1e-3)
            assert l1.angle == pytest.approx(l0.angle, abs=1e-3)
            assert np.allclose(l1.bottom, rot @ l0.bottom + shift, atol=1e-3)
        assert h.tilts[0] == pytest.approx(base.tilts[0], abs=1e-3)


def test_forces_scale_with_the_mass():
    ref = _c2()
    for m in (50.0, 1.0e6):
        h = H.single(m, C2_COG, C2_PTS, C2_LEN, (1.5, 0.0, 3.0), names=["A", "B"])
        for l0, l1 in zip(ref.legs, h.legs):
            assert l1.force / m == pytest.approx(l0.force / 10000.0, rel=1e-4)
            assert np.allclose(l1.bottom, l0.bottom, atol=1e-3)


# ------------------------------------------------------------------------------------------------ odd cases

def _said(h, *words):
    text = " ".join(h.notes + h.problems).lower()
    return any(w in text for w in words)


def test_slack_leg_reported():
    """Four legs of a rectangle, D 0.3 m longer: A, B, C hold the load as a tripod (the hook on the centre normal),
    D's corner stays at the old length from the hook, so D is slack; CoG on B's side of the diagonal A-C."""
    L = math.hypot(2.5, 3.5)
    lengths = [L, L, L, L + 0.3]
    cog = (-0.5, 0.5, -0.3)
    h = H.single(5000.0, cog, C3_PTS, lengths, (0.0, 0.0, 5.0), names=["a", "b", "c", "d"])
    d = h.leg("d")
    assert not d.taut
    assert d.force == pytest.approx(0.0, abs=1e-6 * 5000 * G)
    assert np.linalg.norm(d.top - d.bottom) == pytest.approx(L, abs=2e-3)
    assert len(h.taut) == 3
    assert _said(h, "slack")
    forces, _, _ = _predict(C3_PTS, cog, (0.0, 0.0, 3.5), 5000.0, active=[0, 1, 2])
    got = np.array([lg.force for lg in h.legs])
    assert np.allclose(got, forces, rtol=0.005, atol=1e-3 * 5000 * G), (got / G, forces / G)
    _check_single_equilibrium(h, 5000.0, C3_PTS, cog, lengths)


def test_legs_too_short_to_reach_reported():
    h = H.single(5000.0, (2.0, 0.0, -0.5), C2_PTS, [1.0, 1.0], (0.0, 0.0, 5.0), names=["A", "B"])
    assert not h.ok
    assert _said(h, "short", "reach")


def test_cog_above_the_line_rolls_over():
    """Two legs, CoG above the line through the lift points: the load rolls over until the CoG is below."""
    cog = (1.5, 0.0, 0.5)
    h = H.single(4000.0, cog, C2_PTS, C2_LEN, (1.5, 0.0, 3.0), names=["A", "B"])
    assert h.rolled or not h.stable
    assert h.problems
    assert _said(h, "roll", "unstable", "over")


def test_cog_on_the_line_is_neutral():
    cog = (1.5, 0.0, 0.0)
    h = H.single(4000.0, cog, C2_PTS, C2_LEN, (1.5, 0.0, 3.0), names=["A", "B"])
    assert h.neutral
    assert h.notes or h.problems
    # statics still hold: the C2 split of a 4 t load
    assert h.leg("A").force / G == pytest.approx(4000 * 0.625 * C2_LEN[0] / 3.0, rel=0.005)
    assert h.leg("B").force / G == pytest.approx(4000 * 0.375 * C2_LEN[1] / 3.0, rel=0.005)


def test_top_heavy_load_on_four_legs_to_one_hook_is_stable():
    """Four taut legs to one point make the load and legs one rigid pendulum about the hook: a CoG a little above the
    lift points, still far below the hook, hangs stable and level (statics, equal shares)."""
    L = math.hypot(2.5, 3.5)
    h = H.single(20000.0, (0.0, 0.0, 0.3), C3_PTS, [L] * 4, (0.0, 0.0, 3.5))
    assert h.stable and not h.rolled
    assert h.tilts[0] == pytest.approx(0.0, abs=0.1)
    for lg in h.legs:
        assert lg.force / G == pytest.approx(6145.0, rel=0.01)


def test_bad_input_raises():
    with pytest.raises(ValueError):
        H.single(0.0, C2_COG, C2_PTS, C2_LEN, (1.5, 0.0, 3.0))
    with pytest.raises(ValueError):
        H.single(1000.0, C2_COG, C2_PTS, [0.0, C2_LEN[1]], (1.5, 0.0, 3.0))


# ------------------------------------------------------------------------------------------------ spreader (two stages)

def _spreader(load_cog=(0.0, 0.0, -0.5), sp_top=((-1.0, 0.0, 3.3), (1.0, 0.0, 3.3)), top_len=2.5):
    pts = [(-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    sp_bottom = [(-2.0, 0.0, 3.0), (2.0, 0.0, 3.0)]
    return H.with_spreader(10000.0, load_cog, pts, [3.0, 3.0], 1000.0, (0.0, 0.0, 3.15), list(sp_top), sp_bottom,
                           [top_len, top_len], (0.0, 0.0, 10.0)), pts


def test_spreader_forces_add_up_through_both_stages():
    h, _ = _spreader()
    assert h.ok
    W, Ws = 10000.0 * G, 1000.0 * G
    hook_legs = [lg for lg in h.legs if lg.at_hook]
    low_legs = [lg for lg in h.legs if not lg.at_hook]
    assert len(hook_legs) == 2 and len(low_legs) == 2
    up = sum((_forces_on(lg) for lg in hook_legs), np.zeros(3))
    down = sum((_forces_on(lg) for lg in low_legs), np.zeros(3))
    assert np.allclose(up, (W + Ws) * Z, atol=1e-4 * W)
    assert np.allclose(down, W * Z, atol=1e-4 * W)
    for lg in low_legs:          # symmetric: vertical legs, half each
        assert lg.force == pytest.approx(W / 2, rel=0.002)
        assert lg.angle == pytest.approx(0.0, abs=0.05)
    for lg in hook_legs:
        h_vert = math.sqrt(2.5 ** 2 - 1.0)
        assert lg.force == pytest.approx((W + Ws) / 2 * 2.5 / h_vert, rel=0.002)
    # combined CoG under the hook
    cogs = np.array(h.cogs)
    combined = (cogs[np.argmin(cogs[:, 2])] * 10000.0 + cogs[np.argmax(cogs[:, 2])] * 1000.0) / 11000.0
    assert np.allclose(combined[:2], h.hook[:2], atol=1e-3)


def test_spreader_off_centre_load_each_body_in_equilibrium():
    h, pts = _spreader(load_cog=(0.6, 0.0, -0.5))
    W, Ws = 10000.0 * G, 1000.0 * G
    hook_legs = [lg for lg in h.legs if lg.at_hook]
    low_legs = [lg for lg in h.legs if not lg.at_hook]
    cogs = np.array(h.cogs)
    load_cog = cogs[np.argmin(cogs[:, 2])]
    sp_cog = cogs[np.argmax(cogs[:, 2])]
    # the load: its two legs carry its weight, no moment about its CoG
    f_low = [_forces_on(lg) for lg in low_legs]
    assert np.allclose(sum(f_low), W * Z, atol=1e-4 * W)
    m = sum(np.cross(lg.bottom - load_cog, f) for lg, f in zip(low_legs, f_low))
    assert np.linalg.norm(m) < 1e-4 * W * 3
    # the spreader: pulled up by the hook legs, down by the load legs, its own weight
    f_up = [_forces_on(lg) for lg in hook_legs]
    net = sum(f_up) - sum(f_low) - Ws * Z
    assert np.linalg.norm(net) < 1e-4 * W
    m = sum(np.cross(lg.bottom - sp_cog, f) for lg, f in zip(hook_legs, f_up)) \
        - sum(np.cross(lg.top - sp_cog, f) for lg, f in zip(low_legs, f_low))
    assert np.linalg.norm(m) < 1e-4 * W * 3
    # the leg nearer the load's CoG carries more
    near = min(low_legs, key=lambda lg: abs(lg.bottom[0] - load_cog[0]))
    assert near.force == max(lg.force for lg in low_legs)
    combined = (load_cog * 10000.0 + sp_cog * 1000.0) / 11000.0
    assert np.allclose(combined[:2], h.hook[:2], atol=1e-3)


def test_spreader_checks_rows():
    h, _ = _spreader()
    rows = H.checks(h, 10000.0, leg_wll=8000.0, spreader_wll=12500.0, spreader_mass=1000.0)
    sp = [r for r in rows if "spreader" in r.title.lower()]
    assert sp, [r.title for r in rows]
    assert sp[0].use == pytest.approx(10000.0 / 12500.0, rel=0.01)
    assert any(r.check == "C2" for r in rows)
    c2 = [r for r in rows if r.check == "C2"][0]
    hook_max = max(lg.force for lg in h.legs if lg.at_hook)
    assert c2.value == pytest.approx(hook_max, rel=0.005)
    rows = H.checks(h, 10000.0, spreader_wll=9000.0, spreader_mass=1000.0)
    assert [r for r in rows if "spreader" in r.title.lower()][0].status == lifting.RED


def test_spreader_with_cog_above_vertical_legs_rolls():
    """Vertical parallel legs from a spreader: a CoG above the lift points is unstable (the classic roll-over)."""
    h, _ = _spreader(load_cog=(0.0, 0.0, 0.5))
    assert h.rolled or not h.stable
    assert h.problems


# ------------------------------------------------------------------------------------------------ C10 and the reeving

def _api_e(n, s=None, k=1.04):
    s = n if s is None else s
    return (k ** n - 1) / (k ** s * n * (k - 1))


def test_c10_efficiency_hand_values():
    assert lifting.reeving_efficiency(1) == pytest.approx(1 / 1.04, rel=1e-9)
    assert lifting.reeving_efficiency(4) == pytest.approx(0.90747, abs=1e-5)       # hand: 0.169859 / 0.187177
    assert lifting.reeving_efficiency(8) == pytest.approx(0.84159, abs=1e-5)       # hand: 0.368569 / 0.437942
    for n in range(1, 21):
        assert lifting.reeving_efficiency(n) == pytest.approx(_api_e(n), rel=1e-12)
        assert R.efficiency(n) == pytest.approx(_api_e(n), rel=1e-12)
        assert lifting.reeving_efficiency(n, sheaves=n + 1) == pytest.approx(_api_e(n, n + 1), rel=1e-12)
        assert lifting.reeving_efficiency(n, k=1.09) == pytest.approx(_api_e(n, k=1.09), rel=1e-12)
    es = [lifting.reeving_efficiency(n) for n in range(1, 21)]
    assert all(a > b for a, b in zip(es, es[1:]))      # more sheaves, more friction
    assert lifting.reeving_efficiency(6, k=1.0) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        lifting.reeving_efficiency(0)


def test_c10_line_pull_check():
    # 40 t on 8 falls: 40000 / (8 x 0.841595) = 5941.0 kg
    assert R.line_pull(40000.0, 8) == pytest.approx(5941.0, rel=1e-3)
    r = lifting.hoist_line_pull(40000.0, 8, max_line_pull=8000.0)
    assert r.check == "C10"
    assert r.value == pytest.approx(5941.0, rel=1e-3)
    assert r.use == pytest.approx(5941.0 / 8000.0, rel=1e-3)
    assert r.status == lifting.OK                       # 74.3 % < 75 % crane limit
    assert lifting.hoist_line_pull(40000.0, 8, max_line_pull=7500.0).status == lifting.AMBER
    assert lifting.hoist_line_pull(40000.0, 8, max_line_pull=5900.0).status == lifting.RED
    assert lifting.hoist_line_pull(40000.0, 8).status == lifting.NOT_CHECKED
    for n in (1, 3, 5, 12):
        assert R.line_pull(1000.0, n) == pytest.approx(1000.0 / (n * _api_e(n)), rel=1e-12)


def test_sheaves_and_payout_for_many_falls():
    for n in range(1, 17):
        head, block, dead = R.sheaves_for(n)
        assert head == 1 + (n - 1) // 2
        assert block == n // 2
        assert dead == ("head" if n % 2 == 0 else "block")
        assert R.payout(n, 2.5) == pytest.approx(n * 2.5)
    assert R.sheaves_for(8) == (4, 4, "head")
    assert R.sheaves_for(7) == (4, 3, "block")


def _world_path(rv, d, drum=np.array([-6.0, 0.0, -15.0])):
    pts = R.path(rv, tuple(drum), tuple(-drum))
    origin = {"head": np.zeros(3), "block": np.array([0.0, 0.0, -d]), "drum": drum}
    return pts, np.array([origin[f] + np.asarray(p) for f, p in pts])


@pytest.mark.parametrize("n", list(range(1, 11)))
def test_reeved_path_falls_dead_end_and_payout(n):
    rv = R.Reeving(falls=n, head_r=0.35, block_r=0.3, head_pitch=0.09, block_pitch=0.09, rope_d=0.024)
    pts, w1 = _world_path(rv, 10.0)
    assert R.falls_of(pts) == n
    assert pts[0][0] == "drum"
    assert pts[-1][0] == ("head" if n % 2 == 0 else "block")
    frames = [f for f, _ in pts]
    pieces = sum(1 for a, b in zip(frames, frames[1:]) if {a, b} == {"head", "block"})
    assert pieces == n
    head, block, _ = R.sheaves_for(n)
    sl = R.sheave_list(rv)
    assert sum(1 for s in sl if s[0] == "head") == head
    assert sum(1 for s in sl if s[0] == "block") == block
    # the rope wraps every sheave at its radius
    for f, y, r in sl:
        on = [np.asarray(p) for g, p in pts if g == f and abs(p[1] - y) < 1e-9]
        assert on, (f, y)
        assert any(abs(math.hypot(p[0], p[2]) - r) < 1e-6 for p in on)
    # no jumps: consecutive points of the world line are close except along the falls and the lead
    seg = np.linalg.norm(np.diff(w1, axis=0), axis=1)
    long = seg > 0.5
    assert long.sum() == n + 1                          # the lead from the drum + the falls
    # lowering the block 5 m pays out falls x 5 m (the falls lean a little: 0.2 %)
    _, w2 = _world_path(rv, 15.0)
    l1 = np.linalg.norm(np.diff(w1, axis=0), axis=1).sum()
    l2 = np.linalg.norm(np.diff(w2, axis=0), axis=1).sum()
    assert l2 - l1 == pytest.approx(R.payout(n, 5.0), rel=0.002)


def test_drum_table_winds_falls_times_hoist():
    """The table's hoist value runs one way, the rope on the drum the other (here: hoist 0 = most rope on the drum).
    Either way: falls x the hoist's change goes on or off, layer by layer, and at the end with the least rope only
    the dead turns stay on the first layer."""
    rv = R.Reeving(falls=6, head_r=0.35, block_r=0.3, head_pitch=0.09, block_pitch=0.09, rope_d=0.024,
                   drum_r=0.3, drum_w=0.5)
    t = R.drum_table(rv, 40.0)
    assert t.hoist[0] == pytest.approx(0.0) and t.hoist[-1] == pytest.approx(40.0)
    assert np.all(np.diff(t.hoist) > 0)
    da = np.diff(t.angle)
    assert np.all(da >= -1e-9) or np.all(da <= 1e-9)            # the drum turns one way only
    do = np.diff(t.outside)
    assert np.all(do >= -1e-9) or np.all(do <= 1e-9)            # layers only grow or only shrink
    first = rv.drum_r + rv.rope_d
    assert min(t.outside[0], t.outside[-1]) == pytest.approx(first, abs=1e-6)
    dead = 3.0 * 2 * math.pi * (rv.drum_r + rv.rope_d / 2)
    assert t.wound0 == pytest.approx(6 * 40.0 + dead, rel=0.01) or t.wound0 == pytest.approx(dead, rel=0.01)
    wound = 6 * 40.0
    turn = abs(t.angle[-1] - t.angle[0])
    assert turn * (rv.drum_r + rv.rope_d / 2) >= wound * (rv.drum_r + rv.rope_d / 2) / t.outside.max() * 0.999
    assert turn * (rv.drum_r + rv.rope_d / 2) <= wound * 1.001
    # step by step: the rope moved (falls x hoist step) lies between the turn x the lower layer's middle radius and
    # the turn x the middle radius one layer up (a climb between layers)
    step = rv.rope_d * math.sqrt(3) / 2
    for i in range(len(t.hoist) - 1):
        moved = 6 * (t.hoist[i + 1] - t.hoist[i])
        turned = abs(t.angle[i + 1] - t.angle[i])
        lo = min(t.outside[i], t.outside[i + 1]) - rv.rope_d / 2
        hi = max(t.outside[i], t.outside[i + 1]) - rv.rope_d / 2 + step
        assert turned * lo <= moved * 1.001 + 1e-9
        assert turned * hi >= moved * 0.999 - 1e-9
    assert t.layers >= 2                                # 240 m does not fit one layer of a 0.5 m drum


def _two_stage_equilibrium(h, m_load, m_sp):
    W, Ws = m_load * G, m_sp * G
    hook_legs = [lg for lg in h.legs if lg.at_hook]
    low_legs = [lg for lg in h.legs if not lg.at_hook]
    cogs = np.array(h.cogs)
    load_cog, sp_cog = cogs[np.argmin(cogs[:, 2])], cogs[np.argmax(cogs[:, 2])]
    f_up = [_forces_on(lg) for lg in hook_legs]
    f_low = [_forces_on(lg) for lg in low_legs]
    assert np.allclose(sum(f_up), (W + Ws) * Z, atol=1e-4 * W)
    assert np.allclose(sum(f_low), W * Z, atol=1e-4 * W)
    m = sum(np.cross(lg.bottom - load_cog, f) for lg, f in zip(low_legs, f_low))
    assert np.linalg.norm(m) < 1e-4 * W * 5
    m = sum(np.cross(lg.bottom - sp_cog, f) for lg, f in zip(hook_legs, f_up)) \
        - sum(np.cross(lg.top - sp_cog, f) for lg, f in zip(low_legs, f_low))
    assert np.linalg.norm(m) < 1e-4 * W * 5
    combined = (load_cog * m_load + sp_cog * m_sp) / (m_load + m_sp)
    assert np.allclose(combined[:2], h.hook[:2], atol=1e-3)
    for lg in h.legs:
        assert lg.force >= 0.0
        d = np.linalg.norm(lg.top - lg.bottom)
        assert d == pytest.approx(lg.length, abs=2e-3) if lg.taut else d <= lg.length + 1e-6


def test_spreader_frame_four_and_four_off_centre():
    pts = [(2.0, 1.5, 0.0), (-2.0, 1.5, 0.0), (-2.0, -1.5, 0.0), (2.0, -1.5, 0.0)]
    sp_bottom = [(x, y, 3.0) for x, y, _ in pts]
    sp_top = [(1.0, 1.0, 3.2), (-1.0, 1.0, 3.2), (-1.0, -1.0, 3.2), (1.0, -1.0, 3.2)]
    h = H.with_spreader(12000.0, (0.5, 0.3, -0.4), pts, [3.0] * 4, 1500.0, (0.0, 0.0, 3.1), sp_top, sp_bottom,
                        [3.0] * 4, (5.0, 5.0, 20.0))
    assert h.ok and h.stable
    _two_stage_equilibrium(h, 12000.0, 1500.0)


def test_spreader_on_one_top_padeye_tilts_until_the_cogs_are_under_it():
    h = H.with_spreader(10000.0, (0.6, 0.0, -0.5), [(-2.0, 0.0, 0.0), (2.0, 0.0, 0.0)], [3.0, 3.0], 1000.0,
                        (0.0, 0.0, 3.15), [(0.0, 0.0, 3.4)], [(-2.0, 0.0, 3.0), (2.0, 0.0, 3.0)], [1.0],
                        (0.0, 0.0, 10.0))
    assert h.stable
    top = [lg for lg in h.legs if lg.at_hook]
    assert len(top) == 1 and top[0].force / G == pytest.approx(11000.0, rel=1e-4)
    assert top[0].angle == pytest.approx(0.0, abs=0.05)
    _two_stage_equilibrium(h, 10000.0, 1000.0)
