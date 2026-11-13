"""Task 0058: the hose solver without Blender (core/flex.py), checked against its guarantees.

Lengths in metres, Z up. The "generic" hoses are made from a fixed seed: ends 0.3 … 2 m apart in any direction,
fittings pointing roughly along the hose (a quarter also sideways or backwards), 2 … 200 % of slack, bending
lengths from a rope to a stiff hydraulic hose. The measured worst values are printed (pytest -s shows them).
"""

import math
import time

import numpy as np
import pytest

from fresing_render.core import flex as F

N = 33


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def generic(count, seed=7, slack=(1.02, 3.0)):
    """A spread of hoses that reach: p0, t0, p1, t1, length, stiff."""
    rng = np.random.default_rng(seed)
    p0 = rng.uniform(-1.0, 1.0, (count, 3))
    dist = rng.uniform(0.3, 2.0, count)
    chord = unit(rng.normal(size=(count, 3)))
    p1 = p0 + chord * dist[:, None]
    wild = rng.random(count) < 0.25
    spread = np.where(wild, 3.0, 0.7)[:, None]
    t0 = unit(chord + spread * rng.normal(size=(count, 3)))
    t1 = unit(chord + spread * rng.normal(size=(count, 3)))
    length = dist * rng.uniform(slack[0], slack[1], count) + 0.15
    stiff = length * 10.0 ** rng.uniform(-1.7, 0.3, count)
    return p0, t0, p1, t1, length, stiff


def rotation(axis, angle):
    x, y, z = unit(axis)
    c, s = math.cos(angle), math.sin(angle)
    k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + s * k + (1.0 - c) * (k @ k)


def segments(points):
    seg = np.diff(points, axis=-2)
    ln = np.linalg.norm(seg, axis=-1)
    return seg / ln[..., None], ln


def angle(a, b):
    return np.arctan2(np.linalg.norm(np.cross(a, b), axis=-1), np.sum(a * b, axis=-1))


def energy(points, length, ell, sag, gravity=(0.0, 0.0, -1.0)):
    """The model's energy per unit weight, worked out from the points alone, as the module's docstring says it:
    (ℓ³/2)·Σ κ²·Δs + sag·Σ height·h, with κ = |Δd| / Δs at every joint, Δs = h between two free segments and
    1.5 h at the two end joints (the end segment stands for the fitting's clamp at the very end), and the trace
    of weight every hose keeps."""
    n = points.shape[-2]
    h = length / (n - 1)
    d, _ln = segments(points)
    turn = np.sum(np.diff(d, axis=-2) ** 2, axis=-1)
    ds = np.full(n - 2, 1.0)
    ds[0] = ds[-1] = 1.5
    bend = np.sum(turn / ds, axis=-1) / h
    height = -points @ unit(np.asarray(gravity, dtype=float))
    w = np.full(n, 1.0)
    w[0] = w[-1] = 0.5
    ell = np.maximum(ell, F._FLOOR * length)
    weight = sag + F._GHOST * (ell / length) ** 3
    return 0.5 * ell ** 3 * bend + weight * h * np.sum(height * w, axis=-1)


def catenary(dist, length, count):
    """A rope of this length hanging between two points at the same height, dist apart: points at equal steps
    along the rope ((count, 2): x, z with the ends at z = 0), and the slope angle at the ends."""
    lo, hi = 1e-6, 1e6                                    # a·sinh(dist / 2a) = length / 2
    for _ in range(200):
        a = math.sqrt(lo * hi)
        if 2.0 * a * math.sinh(min(dist / (2.0 * a), 700.0)) > length:
            lo = a
        else:
            hi = a
    s = np.linspace(-0.5 * length, 0.5 * length, count)
    x = a * np.arcsinh(s / a)
    z = np.sqrt(a * a + s * s) - math.sqrt(a * a + 0.25 * length * length)
    return np.stack([x + 0.5 * dist, z], axis=1), math.atan(0.5 * length / a)


# ---------------------------------------------------------------------------
# 1 + 2: the ends, the segments, the end directions
# ---------------------------------------------------------------------------

def test_ends_segments_and_directions_are_exact():
    p0, t0, p1, t1, length, stiff = generic(300)
    h = F.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert h.points.shape == (300, N, 3)
    assert not h.short.any() and np.isfinite(h.points).all()
    d, ln = segments(h.points)
    end = max(np.abs(h.points[:, 0] - p0).max(), np.abs(h.points[:, -1] - p1).max())
    seg = np.abs(ln / (length / (N - 1))[:, None] - 1.0).max()
    turn = max(angle(d[:, 0], t0).max(), angle(d[:, -1], t1).max())
    print("\nends off %.1e m, segment length off %.1e (relative), end direction off %.1e rad" % (end, seg, turn))
    assert end <= 1e-9
    assert seg <= 1e-9
    assert turn <= 1e-7
    assert np.abs(F.polyline_length(h.points) / length - 1.0).max() <= 1e-9
    assert (h.need < length).all() and (h.need >= np.linalg.norm(p1 - p0, axis=1) - 1e-12).all()


@pytest.mark.parametrize("n", [5, 6, 7, 12, 20, 33, 65])
def test_any_number_of_points(n):
    p0, t0, p1, t1, length, stiff = generic(12, seed=3)
    h = F.solve_hoses(p0, t0, p1, t1, length, stiff, n=n)
    ok = ~h.short                                         # few points: the two end segments take more of the reach
    assert ok.sum() >= 8 and np.isfinite(h.points).all()
    d, ln = segments(h.points[ok])
    assert np.abs(ln / (length[ok] / (n - 1))[:, None] - 1.0).max() <= 1e-9
    assert max(angle(d[:, 0], t0[ok]).max(), angle(d[:, -1], t1[ok]).max()) <= 1e-7
    assert np.abs(h.points[:, -1] - p1).max() <= 1e-9
    with pytest.raises(ValueError):
        F.solve_hoses(p0, t0, p1, t1, length, stiff, n=4)


def test_shapes_and_units_of_the_inputs():
    one = F.solve_hose((0, 0, 0), (0, 0, -3.0), (0.5, 0, 0), (0, 0, 0.2), 1.0, 0.2)       # directions of any length
    assert one.points.shape == (1, N, 3) and one.short.shape == (1,)
    same = F.solve_hoses([[0, 0, 0]], [0, 0, -1], [0.5, 0, 0], [[0, 0, 1]], [1.0], 0.2)
    assert np.array_equal(one.points, same.points)
    many = F.solve_hoses((0, 0, 0), (0, 0, -1), [(0.5, 0, 0), (0.6, 0, 0), (0.7, 0, 0)], (0, 0, 1), 1.0,
                         [0.2, 0.2, 0.3], sag=[1.0, 0.5, 1.0])
    assert many.points.shape == (3, N, 3)
    assert np.abs(many.points[0] - one.points[0]).max() <= 1e-9
    with pytest.raises(ValueError):
        F.solve_hoses(np.zeros((2, 3)), (0, 0, 1), np.ones((3, 3)), (0, 0, 1), 1.0, 0.2)
    with pytest.raises(ValueError):
        F.solve_hoses((0, 0), (0, 0, 1), (1, 0, 0), (0, 0, 1), 1.0, 0.2)


# ---------------------------------------------------------------------------
# 3: a pure function
# ---------------------------------------------------------------------------

def test_same_inputs_same_answer_whatever_came_before():
    a = generic(40, seed=11)
    b = generic(25, seed=12, slack=(1.5, 4.0))
    first = F.solve_hoses(*a).points.copy()
    F.solve_hoses(*b)
    F.solve_hoses(*b, n=17)
    F.solve_hose(*[x[3] for x in b], min_radius=0.2)
    again = F.solve_hoses(*a).points
    assert np.array_equal(first, again)                   # bit for bit


def test_a_batch_equals_each_hose_alone_and_order_does_not_matter():
    a = generic(60, seed=21)
    rmin = np.where(np.arange(60) % 3 == 0, 0.08, 0.0)
    whole = F.solve_hoses(*a, min_radius=rmin)
    worst = 0.0
    for i in range(60):
        alone = F.solve_hose(*[x[i] for x in a], min_radius=rmin[i])
        worst = max(worst, np.abs(alone.points[0] - whole.points[i]).max())
        assert alone.short[0] == whole.short[i] and alone.tight[0] == whole.tight[i]
        assert alone.min_radius[0] == pytest.approx(whole.min_radius[i], rel=1e-6)
    order = np.random.default_rng(5).permutation(60)
    mixed = F.solve_hoses(*[x[order] for x in a], min_radius=rmin[order])
    mix = np.abs(mixed.points - whole.points[order]).max()
    big = [np.concatenate([x] * 9) for x in a]            # more than one chunk
    many = F.solve_hoses(*big, min_radius=np.concatenate([rmin] * 9))
    rep = np.abs(many.points.reshape(9, 60, N, 3) - whole.points).max()
    print("\nbatch against alone %.1e m, shuffled %.1e m, 540 in chunks %.1e m" % (worst, mix, rep))
    assert worst <= 1e-9 and mix <= 1e-9 and rep <= 1e-9


# ---------------------------------------------------------------------------
# 4: smooth in the inputs
# ---------------------------------------------------------------------------

def test_a_tiny_move_of_an_end_moves_the_hose_a_little():
    p0, t0, p1, t1, length, stiff = generic(200, seed=31)
    base = F.solve_hoses(p0, t0, p1, t1, length, stiff).points
    rng = np.random.default_rng(32)
    step = 1e-6
    worst = 0.0
    for _ in range(3):
        moved = F.solve_hoses(p0, t0, p1 + step * unit(rng.normal(size=p1.shape)), t1, length, stiff).points
        worst = max(worst, (np.linalg.norm(moved - base, axis=2).max(axis=1) / length).max())
    turned = F.solve_hoses(p0, unit(t0 + step * rng.normal(size=t0.shape)), p1, t1, length, stiff).points
    worst_turn = (np.linalg.norm(turned - base, axis=2).max(axis=1) / length).max()
    print("\nan end moved 1e-6 m: the hose moves up to %.1e × its length; a fitting turned 1e-6 rad: %.1e"
          % (worst, worst_turn))
    assert worst <= 1e-3
    assert worst_turn <= 1e-3


def _paths():
    """Six motions of 201 frames: (name, p0, t0, p1, t1, length, stiff, sag)."""
    u = np.linspace(0.0, 1.0, 201)
    zero, one = np.zeros_like(u), np.ones_like(u)
    out = []
    # a hydraulic hose in a U-loop, one fitting travelling 0.6 m sideways and 0.3 m up
    out.append(("U-loop, end travels", (0, 0, 0), (0, 0, -1),
                np.stack([0.25 + 0.6 * u, zero, 0.3 * u], axis=1), (0, 0, 1), 1.4, 0.45, 1.0))
    # a hose across a joint that turns 110°: the far fitting swings round the hinge and turns with the arm
    a = np.radians(110.0) * u
    arm = np.stack([np.cos(a), zero, np.sin(a)], axis=1)
    out.append(("across a joint turning 110°", (-0.25, 0, 0.08), (1, 0, 0),
                0.35 * arm + 0.08 * np.stack([-np.sin(a), zero, np.cos(a)], axis=1), arm, 0.75, 0.5, 1.0))
    # a soft cable between two parts, one going round a circle in space
    b = 2.0 * np.pi * u
    out.append(("soft cable, end on a circle", (0, 0, 0), (1, 0, 0),
                np.stack([0.9 + 0.3 * np.cos(b), 0.3 * np.sin(b), 0.2 * np.sin(2 * b)], axis=1), (1, 0, 0),
                1.6, 0.06, 1.0))
    # a cylinder stroking out: both fittings in line, the slack goes from a lot (ends at half the length) to
    # nearly none
    out.append(("in line, slack taken up", (0, 0, 0), (1, 0, 0),
                np.stack([0.6 + 0.59 * u, zero, zero], axis=1), (1, 0, 0), 1.2, 0.3, 1.0))
    # a fitting that turns on the spot through 180° about a level axis
    c = np.pi * u
    out.append(("fitting turns 180°", (0, 0, 0), (1, 0, 0), (0.7, 0.1, 0.1),
                np.stack([np.cos(c), np.sin(c), zero], axis=1), 1.1, 0.25, 1.0))
    # no weight at all (sag 0): an S between two parallel fittings, one sliding past the other
    out.append(("no weight, S-bend", (0, 0, 0), (0, 1, 0),
                np.stack([0.4 * one, 0.3 + 0.3 * u, 0.4 * u - 0.1], axis=1), (0, 1, 0), 1.0, 0.3, 0.0))
    return out


def test_no_pops_along_a_motion():
    """201 frames of six motions: the largest move of any point between two frames stays in proportion to how
    far the end moved in that frame. (Each motion is also one batch: frames are solved alone or together.)"""
    print()
    for name, p0, t0, p1, t1, length, stiff, sag in _paths():
        h = F.solve_hoses(p0, t0, p1, t1, length, stiff, sag=sag)
        assert not h.short.any(), name
        frames = h.points
        jump = np.linalg.norm(np.diff(frames, axis=0), axis=2).max(axis=1)        # per frame step
        p1b = np.broadcast_to(np.asarray(p1, dtype=float), (201, 3))
        t1b = np.broadcast_to(np.asarray(t1, dtype=float), (201, 3))
        drive = np.linalg.norm(np.diff(p1b, axis=0), axis=1) + length * angle(t1b[1:], t1b[:-1])
        ratio = jump / drive
        print("%-30s largest move per frame %.4f m = %.1f × the end's own move (median %.1f ×)"
              % (name, jump.max(), ratio.max(), np.median(ratio)))
        assert ratio.max() <= 12.0, name
        assert jump.max() <= 0.05 * length, name
        back = F.solve_hoses(p0, t0, p1b[::-1], t1b[::-1], length, stiff, sag=sag).points[::-1]
        assert np.array_equal(back, frames), name         # the same frame, whatever order the frames are solved in


# ---------------------------------------------------------------------------
# 5: moving and turning everything
# ---------------------------------------------------------------------------

def test_turning_and_moving_the_scene_turns_and_moves_the_shape():
    p0, t0, p1, t1, length, stiff = generic(120, seed=41)
    g = np.array([0.0, 0.0, -1.0])
    base = F.solve_hoses(p0, t0, p1, t1, length, stiff, gravity=g).points
    worst = 0.0
    for axis, ang, shift in (((1, 2, 3), 0.7, (5.0, -3.0, 2.0)), ((0, 0, 1), 2.5, (0.0, 0.0, 0.0)),
                             ((-2, 1, 0.5), 3.1, (100.0, 250.0, -40.0))):
        r = rotation(axis, ang)
        shift = np.asarray(shift)
        moved = F.solve_hoses(p0 @ r.T + shift, t0 @ r.T, p1 @ r.T + shift, t1 @ r.T, length, stiff,
                              gravity=r @ g).points
        worst = max(worst, (np.abs(moved - (base @ r.T + shift)).max(axis=(1, 2)) / length).max())
    print("\nturned and moved: off by %.1e × the length" % worst)
    assert worst <= 1e-7


# ---------------------------------------------------------------------------
# 6: physics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stiff", [0.0, 0.01, 0.3, 5.0])
def test_in_line_and_just_long_enough_is_a_straight_line(stiff):
    for direction in ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.3, -0.5, 0.8)):
        t = unit(direction)
        p0 = np.array([0.2, -0.1, 0.4])
        h = F.solve_hose(p0, t, p0 + 1.3 * t, t, 1.3, stiff)
        want = p0 + np.linspace(0.0, 1.3, N)[:, None] * t
        assert np.abs(h.points[0] - want).max() <= 1e-9
        assert not h.short[0] and h.need[0] == pytest.approx(1.3, rel=1e-9)
        assert np.isinf(h.min_radius[0]) and not h.tight[0]


@pytest.mark.parametrize("dist, length", [(1.0, 1.2), (1.0, 2.0), (0.4, 1.5)])
def test_a_soft_hose_hangs_like_a_rope(dist, length):
    """Ends at the same height, leaving at the rope's own angle: within 1 % of the length of the catenary."""
    want, slope = catenary(dist, length, N)
    t0 = (math.cos(slope), 0.0, -math.sin(slope))
    t1 = (math.cos(slope), 0.0, math.sin(slope))
    worst = 0.0
    for stiff in (0.0, 0.002 * length, 0.02 * length):
        h = F.solve_hose((0, 0, 0), t0, (dist, 0, 0), t1, length, stiff)
        off = np.linalg.norm(h.points[0][:, [0, 2]] - want, axis=1).max()
        assert np.abs(h.points[0][:, 1]).max() <= 1e-9
        worst = max(worst, off / length)
    print("\nrope %.1f m between ends %.1f m apart: off the catenary by %.2f %% of the length"
          % (length, dist, 100.0 * worst))
    assert worst <= 0.01


def test_without_weight_the_stiffness_does_not_matter_and_a_u_loop_is_symmetric():
    p0, t0, p1, t1 = (0, 0, 0), (0, 0, -1), (0.3, 0, 0), (0, 0, 1)
    shapes = [F.solve_hose(p0, t0, p1, t1, 1.0, stiff, sag=0.0).points[0] for stiff in (0.03, 0.2, 1.0, 7.0)]
    for other in shapes[1:]:
        assert np.abs(other - shapes[0]).max() <= 1e-9
    u = shapes[0]
    assert np.abs(u[:, 1]).max() <= 1e-9                                   # in the plane of the two fittings
    mirror = u[::-1] * np.array([-1.0, 1.0, 1.0]) + np.array([0.3, 0.0, 0.0])
    assert np.abs(mirror - u).max() <= 1e-9
    assert u[:, 2].min() < -0.3 and u[:, 2].max() <= 1e-12                 # it hangs below, as the fittings point
    # … and generic hoses too: 30 × stiffer, the same shape
    a = generic(40, seed=51)
    one = F.solve_hoses(*a, sag=0.0).points
    two = F.solve_hoses(*a[:5], a[5] * 30.0, sag=0.0).points
    assert (np.abs(one - two).max(axis=(1, 2)) / a[4]).max() <= 1e-7


def test_more_sag_hangs_lower_and_stiffer_bends_wider():
    args = ((0, 0, 0), (1, 0, -0.2), (1.0, 0.2, 0.1), (1, 0, 0.3), 1.5)
    low = [F.solve_hose(*args, 0.35, sag=s).points[0][:, 2].min() for s in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)]
    assert all(b < a - 1e-4 for a, b in zip(low, low[1:])), low
    radius = [F.solve_hose(*args, s).min_radius[0] for s in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8)]
    assert all(b > a * 1.001 for a, b in zip(radius, radius[1:])), radius
    print("\nlowest point for sag 0 … 1: %s m; tightest bend for stiffer hoses: %s m"
          % (np.round(low, 3), np.round(radius, 3)))
    # generic hoses: on the whole the same (a hose may also get a tighter bend at one fitting when it is stiffer)
    a = generic(100, seed=52)
    soft = F.solve_hoses(*a[:5], a[4] * 0.03).min_radius
    hard = F.solve_hoses(*a[:5], a[4] * 0.6).min_radius
    assert np.mean(hard > soft) > 0.9


def test_the_shape_is_a_minimum_of_the_energy():
    """No nearby hose of the same length between the same fittings has less energy: solved again from a start
    pushed off the answer it comes back, and every other shape tried has more energy."""
    p0, t0, p1, t1, length, stiff = generic(60, seed=61, slack=(1.1, 2.5))
    best = F.solve_hoses(p0, t0, p1, t1, length, stiff)
    e0 = energy(best.points, length, stiff, 1.0)
    rng = np.random.default_rng(62)
    for k in range(4):
        # other shapes with the same ends, directions and length: the answer for another stiffness / sag
        other = F.solve_hoses(p0, t0, p1, t1, length, stiff * rng.uniform(0.5, 2.0, 60),
                              sag=rng.uniform(0.3, 1.0, 60))
        e1 = energy(other.points, length, stiff, 1.0)
        assert (e1 >= e0 - 1e-9 * np.abs(e0) - 1e-12).all()


def test_the_curve_does_not_depend_on_the_number_of_points():
    """33, 65 and 129 points give the same curve: the answer is the rod's, not the grid's. (For hoses whose
    bending length is at least 0.15 × their length; a rope kinks at its fittings, within one segment, and where
    exactly then depends on the segment. A hose that has two shapes may get the other one: under 1 in 100.)"""
    p0, t0, p1, t1, length, stiff = generic(120, seed=63, slack=(1.1, 2.5))
    stiff = np.maximum(stiff, 0.15 * length)
    a = F.solve_hoses(p0, t0, p1, t1, length, stiff)
    b = F.solve_hoses(p0, t0, p1, t1, length, stiff, n=2 * N - 1)
    few = slice(0, 40)                                    # (129 points: large systems, slow on a busy machine)
    c = F.solve_hoses(p0[few], t0[few], p1[few], t1[few], length[few], stiff[few], n=4 * N - 3)
    ab = np.linalg.norm(b.points[:, ::2] - a.points, axis=2).max(axis=1) / length
    bc = np.linalg.norm(c.points[:, ::2] - b.points[few], axis=2).max(axis=1) / length[few]
    print("\n33 against 65 points: median %.2f %% of the length apart, 90 %% of the hoses within %.2f %%, the worst "
          "%.2f %%; 65 against 129: median %.2f %%, worst %.2f %%" % (100 * np.median(ab), 100 * np.percentile(ab, 90),
                                                                 100 * ab.max(), 100 * np.median(bc), 100 * bc.max()))
    assert np.median(ab) <= 0.005 and np.percentile(ab, 90) <= 0.01
    assert np.mean(ab > 0.05) <= 0.02                     # (another shape altogether)
    assert np.median(bc) <= 0.4 * np.median(ab[few])      # … and it closes in as the square of the segment


def test_a_mirrored_set_up_gives_the_mirrored_shape():
    """Two hoses on the two halves of a symmetric machine look like each other in a mirror."""
    p0, t0, p1, t1, length, stiff = generic(150, seed=64)
    m = np.array([-1.0, 1.0, 1.0])                        # the mirror: the plane x = 0 (gravity lies in it)
    one = F.solve_hoses(p0, t0, p1, t1, length, stiff).points
    two = F.solve_hoses(p0 * m, t0 * m, p1 * m, t1 * m, length, stiff).points
    off = np.abs(two - one * m).max(axis=(1, 2)) / length
    print("\nmirrored: off by %.1e × the length" % off.max())
    assert off.max() <= 1e-7


def test_fittings_in_line_bow_in_the_plane_of_gravity():
    """Nothing says where a hose pushed together between two fittings in line should go, except its weight (and
    with sag 0 the trace of weight it keeps): it bows downwards, in a plane, the same on both halves."""
    for stiff in (0.05, 0.3, 1.0):
        for sag in (1.0, 0.0):
            dist = np.linspace(0.6, 1.19, 60)             # ends at half the length … nearly taut
            p1 = np.stack([dist, 0 * dist, 0 * dist], axis=1)
            h = F.solve_hoses((0, 0, 0), (1, 0, 0), p1, (1, 0, 0), 1.2, stiff, sag=sag)
            assert not h.short.any()
            assert np.abs(h.points[:, :, 1]).max() <= 1e-6, (stiff, sag)
            assert (h.points[:, :, 2].max(axis=1) <= 1e-9).all() and (h.points[:, N // 2, 2] < -0.02).all()
            mirror = h.points[:, ::-1] * np.array([-1.0, 1.0, 1.0]) + p1[:, None, :]
            assert np.abs(mirror - h.points).max() <= 1e-6, (stiff, sag)
            assert (np.diff(h.points[:, N // 2, 2]) > 0.0).all()          # the middle rises as the slack goes
    # in line with gravity itself: still one answer, the same alone and in a batch, and the same every time
    args = ((0, 0, 0.5), (0, 0, -1), (0, 0, 0), (0, 0, -1), 0.8, 0.2)
    one = F.solve_hose(*args).points[0]
    assert np.isfinite(one).all() and np.abs(one[:, :2]).max() > 0.05     # it bows out somewhere
    many = F.solve_hoses(*[np.array([x] * 5, dtype=float) for x in args]).points
    assert np.abs(many - one).max() <= 1e-9


def test_a_hose_with_two_shapes_changes_over_once():
    """Slack between fittings that point out of one plane: the hose can wind like a right-handed or a left-handed
    screw. Along a motion from where the one is the relaxed shape to where the other is, the choice changes: one
    jump, to less energy, no flicker before or after."""
    u = np.linspace(0.0, 1.0, 81)
    a = np.radians(35.0) * (2.0 * u - 1.0)                # the far fitting swings from 35° to one side to the other
    t1 = np.stack([np.cos(a), np.sin(a), 0.0 * u], axis=1)
    args = ((0, 0, 0), (0.6, 0.05, 0.8), (1.0, 0.0, 0.0), t1, 1.4, 0.4)
    h = F.solve_hoses(*args)
    jump = np.linalg.norm(np.diff(h.points, axis=0), axis=2).max(axis=1)
    big = np.flatnonzero(jump > 0.05)
    quiet = np.delete(jump, big)
    e = energy(h.points, 1.4, 0.4, 1.0)
    print("\nswinging the far fitting: %d jump (%.2f m, after frame %s of 80), else at most %.4f m per frame"
          % (len(big), jump.max(), big, quiet.max()))
    assert len(big) == 1 and quiet.max() <= 0.015
    assert e[big[0] + 1] < e[big[0]]                      # it jumps to the shape with less energy
    # the same frames one by one, and in the other order: the same shapes
    k = int(big[0])
    for i in (k - 1, k, k + 1, k + 2):
        alone = F.solve_hose(args[0], args[1], args[2], t1[i], 1.4, 0.4).points[0]
        assert np.abs(alone - h.points[i]).max() <= 1e-9


def _swing(frames=81, to=28.0):
    """The motion of the test above, the fitting swinging from −35° to ``to``: (p0, t0, p1, t1 per frame,
    length, stiff). Up to about 31° the hose can stay in the shape it starts in; at 35° that shape is gone."""
    u = np.linspace(0.0, 1.0, frames)
    a = np.radians(-35.0 + (to + 35.0) * u)
    return (0, 0, 0), (0.6, 0.05, 0.8), (1.0, 0.0, 0.0), np.stack([np.cos(a), np.sin(a), 0.0 * u], axis=1), 1.4, 0.4


def test_a_motion_solved_as_a_whole_keeps_its_shape():
    """``solve_motion``: the same swing, all frames in one call: the hose is followed from frame to frame and
    does not jump; ends, segments and end directions are as exact as ever."""
    args = _swing()
    plain = F.solve_hoses(*args)
    whole = F.solve_motion(*args)
    t1 = args[3]
    drive = 1.4 * angle(t1[1:], t1[:-1])                  # what the fitting's turn moves, as a length
    was = np.linalg.norm(np.diff(plain.points, axis=0), axis=2).max(axis=1) / drive
    now = np.linalg.norm(np.diff(whole.points, axis=0), axis=2).max(axis=1) / drive
    print("\nswing: largest move per frame %.1f × the fitting's own with solve_hoses, %.1f × with solve_motion"
          % (was.max(), now.max()))
    assert was.max() > 20.0 and now.max() <= 3.0
    assert (whole.start == plain.start[0]).all()
    # what it cannot do: swung on to 35° the shape it kept is lost near the end, and the hose jumps there, once
    far = _swing(81, to=35.0)
    lost = np.linalg.norm(np.diff(F.solve_motion(*far).points, axis=0), axis=2).max(axis=1)
    assert (lost > 0.05).sum() == 1 and lost.argmax() > 70
    assert F.largest_move(whole.points) == pytest.approx(np.linalg.norm(np.diff(whole.points, axis=0), axis=2).max())
    assert np.array_equal(whole.points[0], plain.points[0])                # it starts as the first frame is solved
    d, ln = segments(whole.points)
    assert np.abs(ln / (1.4 / (N - 1)) - 1.0).max() <= 1e-9
    assert angle(d[:, 0], unit(np.array(args[1]))).max() <= 1e-7 and angle(d[:, -1], t1).max() <= 1e-7
    assert np.abs(whole.points[:, 0]).max() == 0.0 and np.abs(whole.points[:, -1] - (1.0, 0.0, 0.0)).max() == 0.0
    assert not whole.short.any() and np.allclose(whole.min_radius, F.bend_radius(whole.points, hose=True), rtol=1e-6)
    # a pure function of the whole motion
    F.solve_hoses(*generic(10, seed=3))
    assert np.array_equal(F.solve_motion(*args).points, whole.points)
    # every frame is a shape the hose can be in: the solver, started from it, stays (same energy as its own
    # answer or the other of the two shapes)
    e_whole = energy(whole.points, 1.4, 0.4, 1.0)
    e_plain = energy(plain.points, 1.4, 0.4, 1.0)
    assert (e_whole >= e_plain - 1e-9 * np.abs(e_plain)).sum() >= 70      # (the plain one takes the lower)
    # a motion without a jump is exactly what solve_hoses gives, frame for frame
    for name, *calm, sag in _paths()[:3]:
        one = F.solve_motion(*calm, sag=sag)
        assert np.array_equal(one.points, F.solve_hoses(*calm, sag=sag).points), name
    # one frame, short frames, a limit: nothing special
    assert F.solve_motion(args[0], args[1], args[2], t1[:1], 1.4, 0.4).points.shape == (1, N, 3)
    length = np.where(np.arange(81) % 20 == 7, 0.9, 1.4)                   # four frames too short
    mixed = F.solve_motion(args[0], args[1], args[2], t1, length, 0.4, min_radius=0.05)
    assert np.array_equal(mixed.short, np.arange(81) % 20 == 7) and np.isfinite(mixed.points).all()
    _d, ln = segments(mixed.points[~mixed.short])
    assert np.abs(ln / (1.4 / (N - 1)) - 1.0).max() <= 1e-9


def test_a_given_start():
    """``start``: one of the three starts by name. Every guarantee holds as for the best of the three."""
    a = generic(60, seed=21)
    best = F.solve_hoses(*a)
    assert best.start.shape == (60,) and set(np.unique(best.start)) <= {0, 1, 2}
    assert np.array_equal(F.solve_hoses(*a, start=-1).points, best.points)
    assert np.array_equal(F.solve_hoses(*a, start=np.full(60, -1)).points, best.points)
    shapes = []
    for k in (0, 1, 2):
        h = F.solve_hoses(*a, start=k)
        assert (h.start == k).all() and np.isfinite(h.points).all() and not h.short.any()
        d, ln = segments(h.points)
        assert np.abs(ln / (a[4] / (N - 1))[:, None] - 1.0).max() <= 1e-9
        assert max(angle(d[:, 0], a[1]).max(), angle(d[:, -1], a[3]).max()) <= 1e-7
        assert np.array_equal(h.points[:, 0], a[0]) and np.array_equal(h.points[:, -1], a[2])
        assert np.array_equal(F.solve_hoses(*a, start=k).points, h.points)          # bit for bit again
        shapes.append(h.points)
    # the best of the three is one of the three
    for i in range(60):
        assert np.abs(shapes[best.start[i]][i] - best.points[i]).max() <= 1e-9
    # a mixed batch: each hose as it is alone, whatever the others were asked
    want = np.arange(60) % 4 - 1                                           # −1, 0, 1, 2, −1 …
    mixed = F.solve_hoses(*a, start=want)
    worst = 0.0
    for i in range(60):
        alone = F.solve_hose(*[x[i] for x in a], start=want[i])
        worst = max(worst, np.abs(alone.points[0] - mixed.points[i]).max())
        assert alone.start[0] == mixed.start[i] and (want[i] < 0 or mixed.start[i] == want[i])
    order = np.random.default_rng(5).permutation(60)
    again = F.solve_hoses(*[x[order] for x in a], start=want[order])
    print("\ngiven starts, mixed batch against alone %.1e m; %d of 60 hoses take a wound start by themselves"
          % (worst, (best.start > 0).sum()))
    assert worst <= 1e-9 and np.abs(again.points - mixed.points[order]).max() <= 1e-9
    # nothing to choose: short, taut, too few points for the wound starts
    dist = np.linalg.norm(a[2] - a[0], axis=1)
    assert (F.solve_hoses(*a[:4], 0.5 * dist, a[5], start=2).start == 0).all()
    assert (F.solve_hoses(*a, n=6, start=1).start == 0).all()
    line = F.solve_hose((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), 1.0, 0.2, start=1)
    assert line.start[0] == 0 and np.isfinite(line.points).all()
    for bad in (3, -2, 0.5, [0, 7]):
        with pytest.raises(ValueError):
            F.solve_hoses(*a[:4], a[4], a[5], start=bad)


def test_nearly_taut_and_very_slack_hoses():
    rng = np.random.default_rng(71)
    count = 40
    p0 = rng.uniform(-1, 1, (count, 3))
    chord = unit(rng.normal(size=(count, 3)))
    dist = rng.uniform(0.4, 2.0, count)
    p1 = p0 + chord * dist[:, None]
    stiff = dist * 10.0 ** rng.uniform(-1.5, 0.0, count)
    for name, length, t0, t1 in (
            ("taut, in line", dist * 1.001, chord, chord),
            ("taut, fittings 20° off", None, unit(chord + 0.35 * unit(rng.normal(size=(count, 3)))),
             unit(chord + 0.35 * unit(rng.normal(size=(count, 3))))),
            ("4 × too long", dist * 4.0, unit(chord + 0.7 * rng.normal(size=(count, 3))),
             unit(chord + 0.7 * rng.normal(size=(count, 3)))),
            ("12 × too long", dist * 12.0, unit(rng.normal(size=(count, 3))), unit(rng.normal(size=(count, 3))))):
        if length is None:                                # 0.1 % more than just reaches
            length = F.solve_hoses(p0, t0, p1, t1, dist, stiff).need * 1.001
        h = F.solve_hoses(p0, t0, p1, t1, length, stiff)
        assert np.isfinite(h.points).all(), name
        assert not h.short.any(), name
        d, ln = segments(h.points)
        assert np.abs(ln / (length / (N - 1))[:, None] - 1.0).max() <= 1e-9, name
        assert max(angle(d[:, 0], t0).max(), angle(d[:, -1], t1).max()) <= 1e-7, name
        assert np.abs(h.points[:, -1] - p1).max() <= 1e-9, name
        again = F.solve_hoses(p0, t0, p1 + 1e-7 * chord, t1, length, stiff).points
        moved = (np.linalg.norm(again - h.points, axis=2).max(axis=1) / length).max()
        assert moved <= 1e-3, (name, moved)
    # taut and in line: nearly the straight line (0.1 % of slack lets the middle sag about 2 % of the length)
    h = F.solve_hoses(p0, chord, p1, chord, dist * 1.001, stiff)
    line = p0[:, None, :] + np.linspace(0.0, 1.0, N)[None, :, None] * (p1 - p0)[:, None, :]
    assert (np.linalg.norm(h.points - line, axis=2).max(axis=1) / dist).max() <= 0.025


# ---------------------------------------------------------------------------
# 7: too short, and inputs that make no sense
# ---------------------------------------------------------------------------

def test_too_short_is_a_straight_line_and_says_how_much_is_needed():
    p0, t0, p1, t1, length, stiff = generic(50, seed=81)
    dist = np.linalg.norm(p1 - p0, axis=1)
    h = F.solve_hoses(p0, t0, p1, t1, 0.8 * dist, stiff)
    assert h.short.all() and np.isfinite(h.points).all() and not h.tight.any()
    line = p0[:, None, :] + np.linspace(0.0, 1.0, N)[None, :, None] * (p1 - p0)[:, None, :]
    assert np.abs(h.points - line).max() <= 1e-12
    assert np.array_equal(h.points[:, 0], p0) and np.array_equal(h.points[:, -1], p1)
    assert (h.need >= dist).all() and (h.need > 0.8 * dist).all() and np.isinf(h.min_radius).all()
    # ``need`` is the length that just reaches: a hair more is solved, a hair less is short
    more = F.solve_hoses(p0, t0, p1, t1, h.need * (1.0 + 1e-6), stiff)
    less = F.solve_hoses(p0, t0, p1, t1, h.need * (1.0 - 1e-6), stiff)
    assert not more.short.any() and less.short.all()
    assert np.allclose(more.need, h.need, rtol=1e-12) and np.isfinite(more.points).all()
    d, ln = segments(more.points)
    assert np.abs(ln / (more.need * (1.0 + 1e-6) / (N - 1))[:, None] - 1.0).max() <= 1e-6
    # fittings that point across the line need more than the distance
    side = F.solve_hose((0, 0, 0), (0, 0, 1), (1, 0, 0), (0, 0, -1), 1.0, 0.2)
    assert side.short[0] and side.need[0] > 1.0
    # in a mixed batch the others are not disturbed
    mixed_len = np.where(np.arange(50) % 2 == 0, length, 0.5 * dist)
    mixed = F.solve_hoses(p0, t0, p1, t1, mixed_len, stiff)
    good = F.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert np.array_equal(mixed.short, np.arange(50) % 2 == 1)
    assert np.abs(mixed.points[::2] - good.points[::2]).max() <= 1e-9


def test_inputs_that_make_no_sense_give_no_nan():
    up = (0.0, 0.0, 1.0)
    cases = {
        "both ends in one place": ((0, 0, 0), up, (0, 0, 0), up, 1.0, 0.2),
        "both ends in one place, directions opposite": ((1, 2, 3), up, (1, 2, 3), (0, 0, -1), 1.0, 0.2),
        "directions opposite": ((0, 0, 0), (1, 0, 0), (0.5, 0, 0), (-1, 0, 0), 1.0, 0.2),
        "direction without length": ((0, 0, 0), (0, 0, 0), (0.5, 0.1, 0), (0, 0, 0), 1.0, 0.2),
        "nothing has a length": ((0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), 1.0, 0.2),
        "length 0": ((0, 0, 0), up, (0.5, 0, 0), up, 0.0, 0.2),
        "length below 0": ((0, 0, 0), up, (0.5, 0, 0), up, -1.0, 0.2),
        "length 0, ends in one place": ((0, 0, 0), up, (0, 0, 0), up, 0.0, 0.2),
        "stiffness below 0": ((0, 0, 0), up, (0.5, 0, 0), up, 1.0, -3.0),
        "enormous stiffness": ((0, 0, 0), up, (0.5, 0, 0), up, 1.0, 1e6),
        "no gravity direction": ((0, 0, 0), up, (0.5, 0, 0), up, 1.0, 0.2, 1.0, 0.0, (0, 0, 0)),
        "weight along the line, ends in line": ((0, 0, 0), (0, 0, -1), (0, 0, -0.5), (0, 0, -1), 1.0, 0.2),
        "in line with slack, no weight": ((0, 0, 0), (1, 0, 0), (0.5, 0, 0), (1, 0, 0), 1.0, 0.2, 0.0),
        "sag below 0": ((0, 0, 0), up, (0.5, 0, 0), up, 1.0, 0.2, -2.0),
        "huge limit": ((0, 0, 0), up, (0.5, 0, 0), (0, 0, -1), 1.0, 0.2, 1.0, 50.0),
    }
    for name, args in cases.items():
        h = F.solve_hose(*args)
        assert np.isfinite(h.points).all(), name
        assert not np.isnan(h.need).any() and not np.isnan(h.min_radius).any(), name
        assert np.array_equal(h.points[0, 0], np.asarray(args[0], dtype=float)), name
        assert np.array_equal(h.points[0, -1], np.asarray(args[2], dtype=float)), name
        if not h.short[0]:
            _d, ln = segments(h.points)
            assert np.abs(ln / (args[4] / (N - 1)) - 1.0).max() <= 1e-9, name
    assert F.solve_hose(*cases["length 0"]).short[0]
    assert F.solve_hose(*cases["length below 0"]).short[0]
    assert not F.solve_hose(*cases["both ends in one place"]).short[0]
    # a direction without length takes the line between the ends
    a = F.solve_hose(*cases["direction without length"]).points
    b = F.solve_hose((0, 0, 0), (0.5, 0.1, 0), (0.5, 0.1, 0), (5, 1, 0), 1.0, 0.2).points
    assert np.abs(a - b).max() <= 1e-12
    # all of them as one batch: the same, nobody spoils the others
    rows = [c for c in cases.values() if len(c) == 6]
    batch = F.solve_hoses(*[np.array([r[k] for r in rows], dtype=float) for k in range(6)])
    for i, r in enumerate(rows):
        assert np.abs(batch.points[i] - F.solve_hose(*r).points[0]).max() <= 1e-9


# ---------------------------------------------------------------------------
# 8: the tightest bend
# ---------------------------------------------------------------------------

def test_the_reported_radius_is_the_circle_through_three_points():
    a = generic(80, seed=91)
    h = F.solve_hoses(*a)
    measured = F.bend_radius(h.points, hose=True)
    assert np.allclose(h.min_radius, measured, rtol=1e-6)
    # … and by hand for one: segment length / the turn between two segments (as a chord of the unit circle);
    # the joints next to the fittings turn over 1.5 segments of hose
    d, ln = segments(h.points[:1])
    turn = 2.0 * np.sin(0.5 * angle(d[0, 1:], d[0, :-1]))
    turn[0] /= 1.5
    turn[-1] /= 1.5
    assert h.min_radius[0] == pytest.approx(ln[0, 0] / turn.max(), rel=1e-6)
    assert F.bend_radius(h.points[0], hose=True) >= F.bend_radius(h.points[0])
    # a hose that IS half a circle (no weight, fittings 0.4 m apart, pointing down) reports the circle's radius
    half = F.solve_hose((0, 0, 0), (0, 0, -1), (0.4, 0, 0), (0, 0, 1), math.pi * 0.2, 0.3, sag=0.0)
    print("\nhalf circle of radius 0.2 m: tightest bend reported %.4f m" % half.min_radius[0])
    assert half.min_radius[0] == pytest.approx(0.2, rel=0.02)
    assert half.points[0][:, 2].min() == pytest.approx(-0.2, rel=0.01)
    # … and a limit it keeps (0.19 m) is not called tight and does not pull it out of round
    kept = F.solve_hose((0, 0, 0), (0, 0, -1), (0.4, 0, 0), (0, 0, 1), math.pi * 0.2, 0.3, sag=0.0, min_radius=0.19)
    assert not kept.tight[0] and np.abs(kept.points - half.points).max() <= 1e-6
    # a quarter circle of radius 0.5 drawn as points
    t = np.linspace(0.0, 0.5 * math.pi, 40)
    arc = np.stack([0.5 * np.cos(t), 0.5 * np.sin(t), 0.0 * t], axis=1)
    assert F.bend_radius(arc) == pytest.approx(0.5, rel=1e-9)
    assert np.isinf(F.bend_radius(np.linspace((0, 0, 0), (1, 2, 3), 9)))


def test_a_minimum_radius_is_kept_where_the_ends_allow():
    # a soft cable in a U between two fittings 0.4 m apart: without a limit it folds tightly at the fittings
    args = ((0, 0, 0), (0, 0, -1), (0.4, 0, 0), (0, 0, 1), 1.6, 0.03)
    free = F.solve_hose(*args)
    assert free.min_radius[0] < 0.1 and not free.tight[0]
    print()
    for limit in (0.12, 0.15, 0.19):
        h = F.solve_hose(*args, min_radius=limit)
        print("limit %.2f m: tightest bend %.4f m (without a limit %.4f m)"
              % (limit, h.min_radius[0], free.min_radius[0]))
        assert h.min_radius[0] >= 0.99 * limit and not h.tight[0]
        assert h.min_radius[0] == pytest.approx(F.bend_radius(h.points[0], hose=True), rel=1e-6)
        d, ln = segments(h.points)
        assert np.abs(ln / (1.6 / (N - 1)) - 1.0).max() <= 1e-9 and np.abs(h.points[0, -1] - (0.4, 0, 0)).max() <= 1e-9
    # a limit the hose keeps anyway changes nothing
    wide = F.solve_hose(*args[:5], 0.5)
    same = F.solve_hose(*args[:5], 0.5, min_radius=0.5 * wide.min_radius[0])
    assert np.abs(same.points - wide.points).max() <= 1e-9 and not same.tight[0]
    # the ends do not allow it: a U-turn between fittings 0.4 m apart cannot be wider than 0.2 m …
    h = F.solve_hose(*args, min_radius=0.3)
    assert h.tight[0] and h.min_radius[0] < 0.99 * 0.3 and np.isfinite(h.points).all()
    # … and a hose that is nearly taut between fittings that point 60° off has to turn right at them
    h = F.solve_hose((0, 0, 0), unit((1, 0, 1.7)), (1, 0, 0), unit((1, 0, -1.7)), 1.06, 0.2, min_radius=0.25)
    assert h.tight[0] and not h.short[0]
    # generic hoses with a moderate limit: where it is not flagged, it is kept; most can keep it
    a = generic(150, seed=92, slack=(1.3, 3.0))
    limit = 0.06 * a[4]
    h = F.solve_hoses(*a, min_radius=limit)
    free = F.solve_hoses(*a)
    assert np.isfinite(h.points).all()
    assert (h.min_radius[~h.tight] >= 0.99 * limit[~h.tight]).all()
    assert (h.min_radius[h.tight] < 0.99 * limit[h.tight]).all()
    under = free.min_radius < limit
    print("generic hoses: %d of 150 bend tighter than 6 %% of their length without a limit, %d still do with it"
          % (under.sum(), h.tight.sum()))
    assert under.sum() >= 30 and h.tight.sum() <= 0.25 * under.sum()
    assert (h.min_radius >= np.minimum(free.min_radius, limit) * 0.9).all()       # never worse than without


# ---------------------------------------------------------------------------
# 8b: numbers that are not numbers, absurd numbers, no hoses
# ---------------------------------------------------------------------------

def test_one_absurd_number_does_not_take_the_batch_down():
    base = dict(p0=np.zeros((2, 3)), t0=(1, 0, 0), p1=np.array([(1.0, 0, 0), (1.0, 0, 0)]), t1=(1, 0, 0),
                length=np.array([1.5, 1.5]), stiff=np.array([0.2, 0.2]), sag=np.array([1.0, 1.0]),
                min_radius=np.array([0.0, 0.0]))
    good = F.solve_hoses(**base)
    with np.errstate(all="raise"):                        # no warnings either
        for what, values in (("stiff", (1e60, 1e110, 1e300, np.inf, -np.inf, np.nan)),
                             ("sag", (1e300, np.inf, -np.inf, np.nan)),
                             ("min_radius", (1e200, np.inf, np.nan)),
                             ("length", (np.inf, -np.inf, np.nan, 1e300))):
            for value in values:
                args = dict(base)
                args[what] = np.array([value, base[what][1]])
                h = F.solve_hoses(**args)
                assert np.isfinite(h.points).all(), (what, value)
                assert not np.isnan(h.need).any() and not np.isnan(h.min_radius).any(), (what, value)
                assert np.abs(h.points[1] - good.points[1]).max() <= 1e-9, (what, value)
                if what == "length" and not np.isfinite(value):
                    assert h.short[0]
                elif what != "length":
                    _d, ln = segments(h.points[:1])
                    assert not h.short[0] and np.abs(ln / (1.5 / (N - 1)) - 1.0).max() <= 1e-9, (what, value)
        # an end, a direction, gravity that is not a number
        for bad in (np.nan, np.inf):
            h = F.solve_hoses((bad, 0, 0), (1, 0, 0), np.array([(1.0, 0, 0), (1.0, 0, 0)]), (1, 0, 0), 1.5, 0.2)
            assert h.short.all() and np.isfinite(h.points).all() and not np.isnan(h.need).any()
            h = F.solve_hoses(np.zeros((2, 3)), np.array([(bad, 0, 0), (1.0, 0, 0)]), (1.0, 0, 0), (1, 0, 0), 1.5, 0.2)
            assert np.isfinite(h.points).all() and not h.short.any()
            assert np.abs(h.points[1] - good.points[1]).max() <= 1e-9
            h = F.solve_hose((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), 1.5, 0.2, gravity=(0, bad, -1))
            assert np.isfinite(h.points).all() and not h.short[0]
        # the same through solve_motion
        h = F.solve_motion(np.zeros((3, 3)), (1, 0, 0), np.array([(1.0, 0, 0), (np.nan, 0, 0), (1.0, 0, 0.1)]),
                           (1, 0, 0), 1.5, np.array([0.2, 1e80, 0.2]))
        assert np.isfinite(h.points).all() and list(h.short) == [False, True, False]
    # no hoses at all: an empty result
    none = np.zeros((0, 3))
    h = F.solve_hoses(none, none, none, none, 1.5, 0.2)
    assert h.points.shape == (0, N, 3) and h.short.shape == (0,) and h.start.shape == (0,)
    assert F.solve_hoses(none, (1, 0, 0), none, (1, 0, 0), np.zeros(0), 0.2, n=9).points.shape == (0, 9, 3)
    assert F.solve_motion(none, none, none, none, 1.5, 0.2).points.shape == (0, N, 3)


# ---------------------------------------------------------------------------
# 8c: a guide
# ---------------------------------------------------------------------------

def _hinge(angle_deg):
    """A stiff hose across a hinge at the origin, the arm at these angles (F,): the two fittings are in line
    when the arm is at 0. Returns p0, t0, p1, t1 (F, 3), length, bending length."""
    a = np.radians(np.asarray(angle_deg, dtype=float))
    c, s, z = np.cos(a), np.sin(a), 0.0 * a
    return (np.stack([z - 0.2, z, z + 0.05], axis=1), np.stack([z + 1.0, z, z], axis=1),
            np.stack([0.25 * c + 0.05 * s, z, -0.25 * s + 0.05 * c], axis=1), np.stack([c, z, -s], axis=1),
            0.6, F.stiff_length(0.02, 1.0))


def _bowed(p0, p1, to, depth=0.15, m=17):
    """A guide per frame: an arc from p0 to p1 with its belly towards ``to``."""
    u = np.linspace(0.0, 1.0, m)[None, :, None]
    return p0[:, None, :] + u * (p1 - p0)[:, None, :] + depth * np.sin(np.pi * u) * np.asarray(to, dtype=float)


def _carried(shape, p1, m=17):
    """A guide per frame as the caller makes it, for an end 1 that only slides: the shape of frame 0, each point
    carried along with end 0 (which stays) and with end 1, blended along the hose with a smooth step."""
    c = F.resample(shape, m)
    u = np.linspace(0.0, 1.0, m)
    w = (3.0 * u * u - 2.0 * u ** 3)[None, :, None]
    return c[None, :, :] + w * (p1 - p1[0])[:, None, :]


def _moves(points, p1, t1, length):
    """Per frame step: the largest move of a point / what end 1 moved and its fitting turned (as a length)."""
    move = np.linalg.norm(np.diff(points, axis=0), axis=2).max(axis=1)
    return move / (np.linalg.norm(np.diff(p1, axis=0), axis=1) + length * angle(t1[1:], t1[:-1]) + 1e-12)


def test_a_guide_keeps_the_hose_on_its_side():
    """The hose across a hinge: solved frame by frame it lies on the side the arm's fitting pushes it to, and
    flips where the fittings come in line. With a guide that bows to one side it stays on that side through the
    whole swing of ±40°."""
    p0, t0, p1, t1, length, ell = _hinge(np.linspace(-40.0, 40.0, 161))
    plain = F.solve_hoses(p0, t0, p1, t1, length, ell)
    mid = plain.points[:, N // 2, 2] - 0.05
    assert mid[79] < -0.1 and mid[81] > 0.1 and _moves(plain.points, p1, t1, length).max() > 20.0
    print()
    for side in (1.0, -1.0):
        guide = _bowed(p0, p1, (0, 0, side))
        h = F.solve_hoses(p0, t0, p1, t1, length, ell, guide=guide)
        ratio = _moves(h.points, p1, t1, length)
        mid = (h.points[:, N // 2, 2] - 0.05) * side
        print("guide bowed to %+.0f z: the middle stays %.3f … %.3f m on that side, largest move per frame %.2f × "
              "the fitting's own" % (side, mid.min(), mid.max(), ratio.max()))
        assert (h.start == 3).all() and not h.short.any()
        assert mid.min() > 0.05 and ratio.max() <= 1.0
        assert np.abs(h.points[:, :, 1]).max() <= 1e-9                     # and in the plane of the motion
        d, ln = segments(h.points)
        assert np.abs(ln / (length / (N - 1)) - 1.0).max() <= 1e-9
        assert max(angle(d[:, 0], t0).max(), angle(d[:, -1], t1).max()) <= 1e-7
        assert np.array_equal(h.points[:, 0], p0) and np.array_equal(h.points[:, -1], p1)
        # a pure function of its inputs, the guide among them; a frame alone as in the batch; solve_motion the same
        assert np.array_equal(F.solve_hoses(p0, t0, p1, t1, length, ell, guide=guide).points, h.points)
        for i in (0, 80, 133):
            alone = F.solve_hose(p0[i], t0[i], p1[i], t1[i], length, ell, guide=guide[i])
            assert np.abs(alone.points[0] - h.points[i]).max() <= 1e-9 and alone.start[0] == 3
        assert np.array_equal(F.solve_motion(p0, t0, p1, t1, length, ell, guide=guide).points, h.points)
    # rows without a guide (NaN) are solved as without one, whatever the others have
    some = _bowed(p0, p1, (0, 0, 1.0))
    some[::2] = np.nan
    mixed = F.solve_hoses(p0, t0, p1, t1, length, ell, guide=some)
    assert (mixed.start[1::2] == 3).all() and (mixed.start[::2] < 3).all()
    assert np.abs(mixed.points[::2] - plain.points[::2]).max() <= 1e-9
    assert np.abs(mixed.points[1::2] - F.solve_hoses(p0, t0, p1, t1, length, ell,
                                                    guide=_bowed(p0, p1, (0, 0, 1.0))).points[1::2]).max() <= 1e-9
    # the same with the fittings 30 mm out of the plane of the swing, and a guide bowed sideways: it holds too
    p0b, p1b = p0 + (0, 0.03, 0), p1 - (0, 0.03, 0)
    for to in ((0, 0, 1.0), (0, 0, -1.0), (0, 1.0, 0)):
        h = F.solve_hoses(p0b, t0, p1b, t1, length, ell, guide=_bowed(p0b, p1b, to))
        belly = (h.points[:, N // 2] - 0.5 * (p0b + p1b)) @ np.asarray(to)
        assert (h.start == 3).all() and belly.min() > 0.05 and _moves(h.points, p1b, t1, length).max() <= 2.0, to


def test_a_guide_stops_the_flicker_between_two_mirror_shapes():
    """A stiff hose between two fittings that both point up, one sliding across: an S, and its mirror image is
    as good. Frame by frame the two are taken by turns; with the first frame's shape carried along as a guide the
    hose keeps the one it has."""
    frames = 300
    s = 0.15 * (1.0 - np.cos(np.linspace(0.0, 2.0 * np.pi, frames)))
    p1 = np.stack([s, 0.0 * s, 0.3 + 0.0 * s], axis=1)
    t1 = np.broadcast_to((0.0, 0.0, 1.0), (frames, 3))
    args = ((0, 0, 0), (0, 0, 1), p1, (0, 0, 1), 0.45, F.stiff_length(0.016, 1.0))
    plain = F.solve_hoses(*args)
    guide = _carried(plain.points[0], p1)
    held = F.solve_hoses(*args, guide=guide)
    was = (_moves(plain.points, p1, t1, 0.45) > 6.0).sum()
    now = _moves(held.points, p1, t1, 0.45)
    print("\nS between two fittings pointing up: %d jumps frame by frame, with a guide the largest move per frame "
          "is %.1f × the end's own" % (was, now.max()))
    assert was >= 6 and now.max() <= 6.0 and (held.start == 3).all()


def test_a_guide_that_is_the_answer_gives_the_answer():
    a = generic(80, seed=94, slack=(1.05, 1.8))
    plain = F.solve_hoses(*a)
    again = F.solve_hoses(*a, guide=plain.points)
    off = np.abs(again.points - plain.points).max(axis=(1, 2)) / a[4]
    print("\nits own shape as the guide: %d of 80 hoses come back within 1e-6 of their length (worst of those %.1e)"
          % ((off <= 1e-6).sum(), off[off <= 1e-6].max()))
    assert (again.start == 3).all()
    assert (off <= 1e-6).sum() >= 76                      # (the others have a second shape next to theirs)
    # resampled to another number of points it is the same guide
    coarse = np.stack([F.resample(p, 17) for p in plain.points])
    assert (np.abs(F.solve_hoses(*a, guide=coarse).points - plain.points).max(axis=(1, 2)) / a[4] <= 1e-2).sum() >= 76


def test_a_silly_guide_still_gives_a_hose():
    p0, t0, p1, t1, length, stiff = generic(40, seed=95)
    u = np.linspace(0.0, 1.0, 9)[None, :, None]
    line = p0[:, None, :] + u * (p1 - p0)[:, None, :]
    zig = line + 0.3 * np.where(np.arange(9) % 2 == 0, 1.0, -1.0)[None, :, None] * np.array([0.3, -0.5, 0.8])
    silly = {
        "a straight line": line,
        "three times too long and somewhere else": 3.0 * _bowed(p0, p1, (0, 0, 1.0)) + 7.0,
        "a zig-zag": zig,
        "backwards": _bowed(p0, p1, (0, 1.0, 0))[:, ::-1],
        "one point, repeated": np.repeat(p0[:, None, :], 5, axis=1),
        "not numbers": np.full((40, 6, 3), np.nan),
        "an infinite one": np.where(np.arange(9)[None, :, None] == 4, np.inf, line),
        "two points": line[:, [0, -1]],
    }
    plain = F.solve_hoses(p0, t0, p1, t1, length, stiff)
    with np.errstate(all="raise"):
        for name, guide in silly.items():
            h = F.solve_hoses(p0, t0, p1, t1, length, stiff, guide=guide)
            assert np.isfinite(h.points).all() and not h.short.any(), name
            d, ln = segments(h.points)
            assert np.abs(ln / (length / (N - 1))[:, None] - 1.0).max() <= 1e-9, name
            assert max(angle(d[:, 0], t0).max(), angle(d[:, -1], t1).max()) <= 1e-7, name
            assert np.array_equal(h.points[:, 0], p0) and np.array_equal(h.points[:, -1], p1), name
            if name in ("one point, repeated", "not numbers", "an infinite one"):    # no guide at all
                assert (h.start < 3).all() and np.abs(h.points - plain.points).max() <= 1e-9, name
    for bad in (np.zeros(3), np.zeros((40, 1, 3)), np.zeros((40, 5, 2)), np.zeros((7, 5, 3))):
        with pytest.raises(ValueError):
            F.solve_hoses(p0, t0, p1, t1, length, stiff, guide=bad)
    # short and taut hoses take no notice of a guide
    dist = np.linalg.norm(p1 - p0, axis=1)
    h = F.solve_hoses(p0, t0, p1, t1, 0.5 * dist, stiff, guide=line)
    assert h.short.all() and (h.start == 0).all()


def test_a_followed_hose_is_in_a_shape_it_would_stay_in():
    """``solve_motion`` without a guide: where the shape the hose is followed in stops being one it would stay
    in, it takes the frame's own answer (it snaps, as a hose does) – it does not ride on a balance point. The two
    cases an independent review found: the hose across the hinge at full swing, and fittings in line pushed
    together and pulled apart."""
    swing = 40.0 * np.sin(np.linspace(0.0, 2.0 * np.pi, 300))
    p0, t0, p1, t1, length, ell = _hinge(swing)
    plain = F.solve_hoses(p0, t0, p1, t1, length, ell)
    whole = F.solve_motion(p0, t0, p1, t1, length, ell)
    ratio = energy(whole.points, length, ell, 1.0) / energy(plain.points, length, ell, 1.0)
    jumps = (_moves(whole.points, p1, t1, length) > 6.0).sum()
    print("\nhinge, followed without a guide: energy at most %.2f × the frame's own answer; %d jumps (frame by "
          "frame: %d)" % (ratio.max(), jumps, (_moves(plain.points, p1, t1, length) > 6.0).sum()))
    assert ratio.max() <= 1.05 and ratio[75] <= 1.001      # (it was 2.4 × at full swing)
    assert jumps <= (_moves(plain.points, p1, t1, length) > 6.0).sum()
    # fittings in line, the ends going from 0.25 m to 0.55 m apart and back, hose 0.7 m
    s = 0.15 * (1.0 - np.cos(np.linspace(0.0, 2.0 * np.pi, 300)))
    q1 = np.stack([0.25 + s, 0.0 * s, 0.0 * s], axis=1)
    args = ((0, 0, 0), (1, 0, 0), q1, (1, 0, 0), 0.7, F.stiff_length(0.016, 1.0))
    plain = F.solve_hoses(*args)
    whole = F.solve_motion(*args)
    ratio = energy(whole.points, 0.7, args[5], 1.0) / energy(plain.points, 0.7, args[5], 1.0)
    print("in line, pushed together and pulled apart: energy at most %.2f × the frame's own answer" % ratio.max())
    assert ratio[150] <= 1.001 and ratio.max() <= 1.6     # (it was 7.7 × with the ends furthest apart)
    # with a guide the hinge hose keeps its side over the whole cycle, and that is what solve_motion returns
    guide = _bowed(p0, p1, (0, 0, 1.0))
    held = F.solve_motion(p0, t0, p1, t1, length, ell, guide=guide)
    assert (held.start == 3).all() and _moves(held.points, p1, t1, length).max() <= 1.0
    assert ((held.points[:, N // 2, 2] - 0.05) > 0.05).all()


# ---------------------------------------------------------------------------
# 9: speed
# ---------------------------------------------------------------------------

def _best(fn, repeats):
    best = math.inf
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def test_speed():
    """Measured where the tests run and printed (web session, 4 cores, 12 Nov 2026: one hose 4.5 ms, 20 generic
    hoses 17 ms, 20 poses of a U-loop 10 ms, 5,000 hoses 2.7 s); the limits leave room for a slow test runner.
    Best of 15 for the short ones, so another program on the machine does not count."""
    print()
    a = generic(20, seed=101)
    F.solve_hoses(*a)                                     # (the first call fills small caches)
    t20 = _best(lambda: F.solve_hoses(*a), 15)
    one = [x[4] for x in a]
    t1 = _best(lambda: F.solve_hose(*one), 15)
    # what a machine has: U-loops and gentle bends, moderately stiff, at 20 different poses
    u = np.linspace(0.0, 1.0, 20)
    typ = ((0, 0, 0), (0, 0, -1), np.stack([0.3 + 0.4 * u, 0.1 * u, 0.2 * u - 0.1], axis=1), (0.2, 0, 1), 1.3, 0.4)
    ttyp = _best(lambda: F.solve_hoses(*typ), 15)
    big = generic(5000, seed=102)
    t = time.perf_counter()
    h = F.solve_hoses(*big)
    t5000 = time.perf_counter() - t
    assert not h.short.any()
    frames = (0, 0, 0), (0, 0, -1), np.stack([0.3 + 0.5 * np.linspace(0, 1, 5000)] + [np.zeros(5000)] * 2, axis=1), \
        (0, 0, 1), 1.4, 0.45
    t = time.perf_counter()
    F.solve_hoses(*frames)
    tframes = time.perf_counter() - t
    held = _best(lambda: F.solve_hoses(*a, min_radius=0.06 * a[4]), 5)     # a limit about half of them must be held to
    print("one hose %.2f ms; 20 generic hoses %.2f ms (%.2f ms each), with a minimum radius %.2f ms; 20 poses of a "
          "U-loop %.2f ms;" % (1e3 * t1, 1e3 * t20, 50.0 * t20, 1e3 * held, 1e3 * ttyp))
    print("5,000 generic hoses %.2f s (%.2f ms each); 5,000 frames of one U-loop %.2f s"
          % (t5000, 0.2 * t5000, tframes))
    # a whole motion of 250 frames: without a jump (as solve_hoses), and with one (followed frame by frame)
    calm = _paths()[0]
    u = np.linspace(0.0, 1.0, 250)
    calm_p1 = np.stack([0.25 + 0.6 * u, 0.0 * u, 0.3 * u], axis=1)
    t_calm = _best(lambda: F.solve_motion(calm[1], calm[2], calm_p1, calm[4], calm[5], calm[6]), 3)
    t_same = _best(lambda: F.solve_hoses(calm[1], calm[2], calm_p1, calm[4], calm[5], calm[6]), 3)
    swing = _swing(250)
    t_jump = _best(lambda: F.solve_motion(*swing), 3)
    print("a motion of 250 frames: %.0f ms (solve_hoses: %.0f ms); one with a jump, followed: %.0f ms"
          % (1e3 * t_calm, 1e3 * t_same, 1e3 * t_jump))
    assert t_calm <= 2.0 and t_jump <= 5.0
    assert t1 <= 0.040
    assert t20 <= 0.060
    assert held <= 0.300
    assert ttyp <= 0.040
    assert t5000 <= 15.0
    assert tframes <= 15.0


# ---------------------------------------------------------------------------
# the small helpers
# ---------------------------------------------------------------------------

def test_stiff_length():
    assert F.stiff_length(0.025, 0.0) == pytest.approx(0.1)               # 4 diameters
    assert F.stiff_length(0.025, 1.0) == pytest.approx(1.6)               # 64 diameters
    assert F.stiff_length(0.025, 0.5) == pytest.approx(0.4)               # 16
    assert isinstance(F.stiff_length(0.025, 0.5), float)
    assert np.allclose(F.stiff_length([0.01, 0.02], 1.0), [0.64, 1.28])


def test_polyline_length_and_resample():
    square = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 2.0)])
    assert F.polyline_length(square) == pytest.approx(4.0)
    assert isinstance(F.polyline_length(square), float)
    assert np.allclose(F.polyline_length(np.stack([square, 2.0 * square])), [4.0, 8.0])
    assert F.polyline_length(square[:1]) == 0.0
    r = F.resample(square, 9)
    assert r.shape == (9, 3)
    assert np.array_equal(r[0], square[0]) and np.array_equal(r[-1], square[-1])
    assert np.allclose(r[2], (1, 0, 0)) and np.allclose(r[4], (1, 1, 0)) and np.allclose(r[6], (1, 1, 1))
    assert F.polyline_length(r) == pytest.approx(4.0)
    # a solved hose resampled keeps its shape
    h = F.solve_hose((0, 0, 0), (0, 0, -1), (0.5, 0, 0), (0, 0, 1), 1.2, 0.3)
    again = F.resample(h.points[0], N)
    assert np.abs(again - h.points[0]).max() <= 2e-3
    assert F.resample(square[:1], 4).shape == (4, 3) and F.resample(square, 1).shape == (1, 3)
    assert np.allclose(F.resample(np.array([(1.0, 2, 3)] * 5), 3), (1, 2, 3))


# ---------------------------------------------------------------------------
# the guide carried by two parts (after the independent review: blended point by point its middle fell onto a
# hinge's axis from about a quarter turn on)
# ---------------------------------------------------------------------------

def _turn(axis, angle):
    axis = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def test_carried_guide_goes_over_from_one_part_to_the_other_by_a_share_of_the_turn():
    s = np.linspace(0.0, 1.0, 17)
    line = np.stack([0.3 + s, 0.1 + 0.2 * np.sin(s * math.pi), 0.05 * s * s], axis=1)
    rng = np.random.default_rng(5)
    for _ in range(200):                                  # any two rigid copies: the ends are the copies' ends
        a = line @ _turn(rng.normal(size=3), rng.uniform(-3, 3)).T + rng.normal(size=3)
        b = line @ _turn(rng.normal(size=3), rng.uniform(-3, 3)).T + rng.normal(size=3)
        g = F.carried(a, b)
        assert np.isfinite(g).all()
        assert np.abs(g[0] - a[0]).max() < 1e-9 and np.abs(g[-1] - b[-1]).max() < 1e-9
    # a hinge about Z through the origin, the second part turned 120 degrees: every point keeps its distance from
    # the hinge's axis (blended point by point the middle would be at half of it)
    b = line @ _turn((0, 0, 1), math.radians(120)).T
    g = F.carried(line, b)
    assert np.abs(np.linalg.norm(g[:, :2], axis=1) - np.linalg.norm(line[:, :2], axis=1)).max() < 1e-9
    assert np.abs(g[:, 2] - line[:, 2]).max() < 1e-9
    plain = 0.5 * (line[8] + b[8])
    assert np.linalg.norm(plain[:2]) < 0.55 * np.linalg.norm(line[8, :2])
    # the same copy twice is that copy; a pure slide is a share of the slide; a batch works row by row
    assert np.abs(F.carried(line, line) - line).max() < 1e-12
    slid = F.carried(line, line + np.array([0.2, 0.0, 0.1]))
    assert np.abs(np.cross(slid - line, np.array([0.2, 0.0, 0.1]))).max() < 1e-9
    both = F.carried(np.stack([line, line]), np.stack([b, line]))
    assert np.abs(both[0] - g).max() < 1e-12 and np.abs(both[1] - line).max() < 1e-12
    # a straight line (no turn can be read from it) and half a turn give a finite line with the right ends
    straight = np.stack([s, 0 * s, 0 * s], axis=1)
    for a, b in ((straight, straight @ _turn((0, 0, 1), 1.0).T), (line, line @ _turn((0, 0, 1), math.pi).T)):
        g = F.carried(a, b)
        # (at half a turn the turn's axis is read from a matrix that barely holds it: the far end is right to about
        # the square root of the rounding, 2e-8 m on GitHub's processor and under 1e-9 on others – task 0078)
        assert np.isfinite(g).all() and np.abs(g[0] - a[0]).max() < 1e-9 and np.abs(g[-1] - b[-1]).max() < 1e-6
