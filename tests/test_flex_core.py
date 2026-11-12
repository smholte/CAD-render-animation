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
    radius = [F.solve_hose(*args, s).min_radius[0] for s in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6)]
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
    c = F.solve_hoses(p0, t0, p1, t1, length, stiff, n=4 * N - 3)
    ab = np.linalg.norm(b.points[:, ::2] - a.points, axis=2).max(axis=1) / length
    bc = np.linalg.norm(c.points[:, ::2] - b.points, axis=2).max(axis=1) / length
    print("\n33 against 65 points: median %.2f %% of the length apart, 90 %% of the hoses within %.2f %%, the worst "
          "%.2f %%; 65 against 129: median %.2f %%, worst %.2f %%" % (100 * np.median(ab), 100 * np.percentile(ab, 90),
                                                                 100 * ab.max(), 100 * np.median(bc), 100 * bc.max()))
    assert np.median(ab) <= 0.005 and np.percentile(ab, 90) <= 0.01
    assert np.mean(ab > 0.05) <= 0.02                     # (another shape altogether)
    assert np.median(bc) <= 0.4 * np.median(ab)           # … and it closes in as the square of the segment


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
    measured = F.bend_radius(h.points)
    assert np.allclose(h.min_radius, measured, rtol=1e-6)
    # … and by hand for one: segment length / the turn between two segments (as a chord of the unit circle)
    d, ln = segments(h.points[:1])
    turn = angle(d[0, 1:], d[0, :-1]).max()
    assert h.min_radius[0] == pytest.approx(ln[0, 0] / (2.0 * math.sin(0.5 * turn)), rel=1e-6)
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
        assert h.min_radius[0] == pytest.approx(F.bend_radius(h.points[0]), rel=1e-6)
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
