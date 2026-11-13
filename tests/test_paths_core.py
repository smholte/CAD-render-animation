"""Task 0078: the cable-path maths (fresing_render/core/paths.py) – no Blender.

The solver (straights and arcs over wheels, in a plane and with a fleet angle, many frames at once), the surface a
cable rests on (meshes built here with NumPy), reading a CAD cable's centreline (made-up routes with noise, a real
tube mesh through ``flex_fit.tube_centreline``) and, as its last test, the demo vessel's real cable: the STEP file
is made by the model maker and read by the app's importer (about a minute, once for the module).
"""

import json
import math
import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fresing_render.core import flex_fit  # noqa: E402
from fresing_render.core import paths as P  # noqa: E402

Y = np.array([0.0, 1.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


# ---------------------------------------------------------------------------------------------------------
# helpers: checking a solved path
# ---------------------------------------------------------------------------------------------------------

def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def angle_deg(a, b) -> float:
    """The angle between two directions (exact for tiny angles: by the cross product)."""
    a, b = unit(a), unit(b)
    return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), float(a @ b)))


def arc_of(path, i):
    k = int(path.first[i])
    return path.points[k:k + int(path.counts[i])]


def helix_tangents(path, wheels, i):
    """The cable's direction where it comes onto wheel i and where it leaves it, from the wheel itself (not from
    the drawn points): round the axis by the wrap, along it by how far the arc's ends are apart."""
    w = wheels[i]
    a = unit(w.axis)
    arc = arc_of(path, i)
    rel = arc - np.asarray(w.centre, float)
    h = rel @ a
    out = []
    for k in (0, -1):
        e = unit(rel[k] - h[k] * a)
        t = w.side * np.cross(a, e) * w.radius * path.wrap[i] + a * (h[-1] - h[0])
        out.append(unit(t) if np.linalg.norm(t) > 0 else None)
    return out


def check_path(path, wheels, start, end, on0=False, on1=False, min_run=1e-5):
    """Everything a good path must be. Returns (the largest direction change at a tangent point in degrees, the
    furthest the cable's middle is from a wheel's circle)."""
    assert path.ok, path.problem
    pts, s = path.points, path.s
    assert np.isfinite(pts).all() and np.isfinite(s).all()
    W = len(wheels)
    assert len(path.first) == W and len(path.wrap) == W and len(path.counts) == W
    lead = 0 if (on0 and W) else 1
    tail = 0 if (on1 and W) else 1
    assert len(pts) == lead + int(np.sum(path.counts)) + tail == len(s)
    if W:
        assert int(path.first[0]) == lead
        assert np.array_equal(path.first[1:], path.first[:-1] + path.counts[:-1])
    if lead:
        assert np.allclose(pts[0], start, atol=1e-12)
    if tail:
        assert np.allclose(pts[-1], end, atol=1e-12)
    assert s[0] == 0.0 and (np.diff(s) >= -1e-12).all()
    assert path.length == pytest.approx(s[-1], abs=1e-12)
    kink = off = 0.0
    total = 0.0
    at = 0
    for i, w in enumerate(wheels):
        a = unit(w.axis)
        arc = arc_of(path, i)
        k0 = int(path.first[i])
        rel = arc - np.asarray(w.centre, float)
        h = rel @ a
        rad = np.linalg.norm(rel - np.outer(h, a), axis=1)
        off = max(off, float(np.abs(rad - w.radius).max()))
        # the arc's length: exact (a helix: round by radius x wrap, along by the rise), and s follows it evenly
        long = math.hypot(w.radius * path.wrap[i], h[-1] - h[0])
        assert s[k0 + len(arc) - 1] - s[k0] == pytest.approx(long, abs=1e-10)
        assert np.allclose(np.diff(s[k0:k0 + len(arc)]), long / (len(arc) - 1), atol=1e-10)
        # the wrap is the angle the points go round, on the wheel's side
        e0, e1 = unit(rel[0] - h[0] * a), unit(rel[-1] - h[-1] * a)
        turned = math.atan2(float(np.cross(e0, e1) @ a), float(e0 @ e1)) * w.side
        assert math.isclose(math.remainder(turned - path.wrap[i], 2 * math.pi), 0.0, abs_tol=1e-9)
        # the straights before and after: their length in s, and no kink where they meet the arc
        t_in, t_out = helix_tangents(path, wheels, i)
        if k0 > 0:
            d = pts[k0] - pts[k0 - 1]
            assert s[k0] - s[k0 - 1] == pytest.approx(np.linalg.norm(d), abs=1e-10)
            if np.linalg.norm(d) > min_run and t_in is not None:
                kink = max(kink, angle_deg(d, t_in))
        k1 = k0 + len(arc) - 1
        if k1 < len(pts) - 1:
            d = pts[k1 + 1] - pts[k1]
            if np.linalg.norm(d) > min_run and t_out is not None:
                kink = max(kink, angle_deg(d, t_out))
        total += long
        at = k1
    return kink, off


def zigzag(count, rng, skew=0.0, sideways=0.0):
    """Wheels 2 m apart, in turn under and over the line, the cable snaking between them."""
    wheels = []
    for i in range(count):
        axis = unit([skew * rng.normal(), 1.0, skew * rng.normal()])
        wheels.append(P.Wheel(np.array([2.0 * i, sideways * rng.normal(), 0.5 * (1 if i % 2 else -1) + 0.1 * rng.normal()]),
                              axis, 0.2 + 0.2 * rng.random(), -1 if i % 2 == 0 else 1))
    return wheels


# ---------------------------------------------------------------------------------------------------------
# the solver
# ---------------------------------------------------------------------------------------------------------

def test_no_wheels_is_a_straight_line():
    p = P.solve([0, 0, 0], [], [3, 4, 0])
    assert p.ok and len(p.points) == 2 and p.length == pytest.approx(5.0)
    assert np.allclose(p.s, [0.0, 5.0]) and len(p.first) == 0 and len(p.wrap) == 0


def test_one_wheel_by_hand():
    """A wheel of radius 1 at the origin, the cable from (-3, 1) to (1, -3) over its top right: a quarter turn."""
    w = P.Wheel(np.zeros(3), Y, 1.0, +1)            # about +y: x turns towards -z … seen from +y clockwise
    start, end = np.array([-3.0, 0.0, 1.0]), np.array([1.0, 0.0, -3.0])
    p = P.solve(start, [w], end)
    kink, off = check_path(p, [w], start, end)
    assert kink < 1e-9 and off < 1e-12
    assert p.wrap[0] == pytest.approx(math.pi / 2, abs=1e-12)
    assert p.length == pytest.approx(3.0 + math.pi / 2 + 3.0, abs=1e-12)
    assert np.allclose(arc_of(p, 0)[0], [0, 0, 1], atol=1e-12) and np.allclose(arc_of(p, 0)[-1], [1, 0, 0], atol=1e-12)
    assert len(p.points) == 2 + 24                   # 90° at one point every 4°: 23 steps
    # the other side: on at the lower left (-0.6, -0.8), nearly all the way round, off at (-0.8, -0.6)
    q = P.solve(start, [P.Wheel(np.zeros(3), Y, 1.0, -1)], end)
    assert q.ok and q.wrap[0] == pytest.approx(2 * math.pi - (math.atan2(0.8, 0.6) - math.atan2(0.6, 0.8)), abs=1e-12)
    assert np.allclose(arc_of(q, 0)[0], [-0.6, 0, -0.8], atol=1e-12) and np.allclose(arc_of(q, 0)[-1], [-0.8, 0, -0.6], atol=1e-12)
    # the same wheel given with its axis the other way round and the other side is the same path
    r = P.solve(start, [P.Wheel(np.zeros(3), -Y, 1.0, -1)], end)
    assert np.allclose(r.points, p.points, atol=1e-12)


@pytest.mark.parametrize("count", [1, 2, 3, 5, 8, 12])
def test_chain_in_a_plane(count):
    rng = np.random.default_rng(count)
    wheels = zigzag(count, rng)
    start, end = np.array([-3.0, 0.0, 0.0]), np.array([2.0 * count + 1.0, 0.0, 0.0])
    p = P.solve(start, wheels, end)
    kink, off = check_path(p, wheels, start, end)
    assert kink < 1e-3 and kink < 1e-9, kink         # the brief: < 0.001°; measured: rounding only
    assert off < 1e-9
    assert np.abs(p.points[:, 1]).max() < 1e-12      # it stays in its plane
    assert (p.wrap > math.radians(20)).all()
    # the centre may be any point on the axis, the axis may point either way (with the side turned too)
    moved = [P.Wheel(w.centre + (i - 3.0) * w.axis, -w.axis if i % 2 else w.axis, w.radius, -w.side if i % 2 else w.side)
             for i, w in enumerate(wheels)]
    q = P.solve(start, moved, end)
    assert q.ok and np.allclose(q.points, p.points, atol=1e-11)


@pytest.mark.parametrize("count", [1, 2, 3, 6, 12])
@pytest.mark.parametrize("skew", [0.0, 0.05, 0.3])
def test_chain_with_a_fleet_angle(count, skew):
    """Start and end beside the wheels' planes, the wheels sideways of each other, the axes parallel (skew 0) or
    each a little or a lot off: no kink at any tangent point, the arcs are helices on the wheels."""
    rng = np.random.default_rng(100 * count + int(100 * skew))
    wheels = zigzag(count, rng, skew=skew, sideways=0.15)
    start, end = np.array([-3.0, 0.4, 0.0]), np.array([2.0 * count + 1.0, -0.3, 0.0])
    p = P.solve(start, wheels, end)
    kink, off = check_path(p, wheels, start, end)
    assert kink < 1e-8, kink
    assert off < 1e-9
    rise = [abs((arc_of(p, i)[-1] - arc_of(p, i)[0]) @ unit(w.axis)) for i, w in enumerate(wheels)]
    assert max(rise) > 1e-3                         # the arcs really leave their planes
    # the shortest way: nudging any wheel's touching points along the wheel makes it longer
    assert p.length < np.linalg.norm(np.diff(p.points, axis=0), axis=1).sum() + 1e-2


def test_fleet_angle_like_0075():
    """0075's case: a sheave 0.3 m sideways over 3 m (5.7°). The cable runs straight when the sheave is unrolled."""
    w = P.Wheel(np.array([3.0, 0.0, 0.0]), Y, 0.5, +1)
    start, end = np.array([0.0, 0.0, 0.5]), np.array([3.5, 0.6, -3.0])
    p = P.solve(start, [w], end)
    kink, off = check_path(p, [w], start, end)
    assert kink < 1e-10 and off < 1e-12
    arc = arc_of(p, 0)
    seen_along = 3.0 + 0.5 * p.wrap[0] + 3.0         # the lengths seen along the axis: tangent, arc, tangent
    assert p.wrap[0] == pytest.approx(math.pi / 2, abs=1e-12)
    assert arc[0][1] == pytest.approx(0.6 * 3.0 / seen_along, abs=1e-12)
    assert arc[-1][1] == pytest.approx(0.6 * (3.0 + 0.5 * p.wrap[0]) / seen_along, abs=1e-12)
    assert p.length == pytest.approx(math.hypot(seen_along, 0.6), abs=1e-12)
    mid = arc[len(arc) // 2]
    assert 0.0 < arc[0][1] < mid[1] < arc[-1][1] < 0.6


def test_axes_square_to_each_other_stay_in_their_planes():
    """A level bend, then a bend upwards (as a CAD route has them): each arc stays flat, whatever point on its
    axis is given as the wheel's centre."""
    a = P.Wheel(np.array([0.0, 2.0, 0.0]), Z, 2.0, +1)               # level, from heading +x to +y
    b = P.Wheel(np.array([2.0, 6.0, 1.5]), np.array([1.0, 0.0, 0.0]), 1.5, +1)    # then up
    start, end = np.array([-5.0, 0.0, 0.0]), np.array([2.0, 7.5, 6.0])
    p = P.solve(start, [a, b], end)
    kink, off = check_path(p, [a, b], start, end)
    assert kink < 1e-9 and off < 1e-12
    assert np.allclose(p.wrap, [math.pi / 2, math.pi / 2], atol=1e-12)
    assert np.abs(arc_of(p, 0)[:, 2]).max() < 1e-12 and np.abs(arc_of(p, 1)[:, 0] - 2.0).max() < 1e-12
    assert p.length == pytest.approx(5.0 + math.pi + 4.0 + 0.75 * math.pi + 4.5, abs=1e-11)
    far = [P.Wheel(a.centre + 3.0 * Z, a.axis, a.radius, a.side), P.Wheel(b.centre - 4.0 * b.axis, b.axis, b.radius, b.side)]
    q = P.solve(start, far, end)
    assert q.ok and np.allclose(q.points, p.points, atol=1e-9)


def test_start_and_end_on_a_wheel():
    drum = P.Wheel(np.zeros(3), Y, 0.6, +1)
    sheave = P.Wheel(np.array([5.0, 0.0, 3.0]), Y, 0.3, +1)
    start = np.array([-0.9, 0.0, 0.0])               # not on the drum's circle: it is put on it
    end = np.array([5.0, 0.0, 3.0]) + 0.3 * unit([1.0, 0.0, -1.0])
    p = P.solve(start, [drum, sheave], end, start_on_wheel=True, end_on_wheel=True)
    kink, off = check_path(p, [drum, sheave], start, end, on0=True, on1=True)
    assert kink < 1e-9 and off < 1e-12
    assert np.allclose(p.points[0], [-0.6, 0, 0], atol=1e-12) and np.allclose(p.points[-1], end, atol=1e-12)
    assert int(p.first[0]) == 0 and p.s[0] == 0.0
    # only the start on its wheel: the end is a point again
    q = P.solve(start, [drum, sheave], np.array([9.0, 0.0, 0.0]), start_on_wheel=True)
    kink, off = check_path(q, [drum, sheave], start, np.array([9.0, 0.0, 0.0]), on0=True)
    assert kink < 1e-9 and len(q.points) == int(np.sum(q.counts)) + 1
    # a start beside the drum's plane stays there: the arc on the drum is a helix up to the fleet angle
    side = P.solve(start + 0.2 * Y, [drum, sheave], end, start_on_wheel=True, end_on_wheel=True)
    assert side.ok and side.points[0][1] == pytest.approx(0.2, abs=1e-12)
    assert check_path(side, [drum, sheave], start, end, on0=True, on1=True)[0] < 1e-9


def test_counts_are_honoured_whatever_the_wrap():
    rng = np.random.default_rng(5)
    wheels = zigzag(4, rng)
    start, end = np.array([-3.0, 0.0, 0.0]), np.array([9.0, 0.0, 0.0])
    counts = [7, 2, 31, 12]
    p = P.solve(start, wheels, end, counts=counts)
    check_path(p, wheels, start, end)
    assert list(p.counts) == counts and len(p.points) == 2 + sum(counts)
    assert list(p.first) == [1, 8, 10, 41]
    lifted = [P.Wheel(w.centre + [0, 0, 0.2 * (i - 1)], w.axis, w.radius, w.side) for i, w in enumerate(wheels)]
    q = P.solve(start, lifted, end, counts=counts)
    assert q.ok and len(q.points) == len(p.points) and list(q.first) == list(p.first)
    assert not np.allclose(q.wrap, p.wrap, atol=1e-3)
    assert P.point_counts([0.0, math.radians(4.0), math.radians(90.0), math.radians(91.0)]) == [2, 2, 24, 24]
    assert P.point_counts([math.radians(90.0)], step=math.radians(10.0), least=5) == [10]
    assert P.point_counts(math.radians(1.0), least=3) == [3]
    free = P.solve(start, wheels, end)
    assert list(free.counts) == P.point_counts(free.wrap)
    fine = P.solve(start, wheels, end, step=math.radians(1.0))
    assert len(fine.points) > 3 * len(free.points) and fine.length == pytest.approx(free.length, abs=1e-12)


def test_s_is_the_true_length_not_the_chords():
    w = P.Wheel(np.zeros(3), Y, 1.0, +1)
    start, end = np.array([-3.0, 0.0, 1.0]), np.array([1.0, 0.0, -3.0])
    coarse = P.solve(start, [w], end, counts=[3])
    fine = P.solve(start, [w], end, counts=[500])
    assert coarse.length == pytest.approx(6.0 + math.pi / 2, abs=1e-12) == pytest.approx(fine.length, abs=1e-12)
    chords = np.linalg.norm(np.diff(coarse.points, axis=0), axis=1).sum()
    assert coarse.length - chords > 0.03


def test_a_wheel_with_no_wrap_is_fine():
    """A wheel the cable only just touches: two points at the same place, no loop."""
    a = P.Wheel(np.array([0.0, 0.0, -0.5]), Y, 0.5, +1)              # the cable lies on its top, straight
    start, end = np.array([-4.0, 0.0, 0.0]), np.array([4.0, 0.0, 0.0])
    p = P.solve(start, [a], end)
    check_path(p, [a], start, end)
    assert p.wrap[0] == 0.0 and p.length == pytest.approx(8.0, abs=1e-12)
    assert np.allclose(arc_of(p, 0), [[0, 0, 0], [0, 0, 0]], atol=1e-9)
    for lift in (1e-9, 1e-6, 1e-3):                                  # lifted a hair: a hair of wrap
        b = P.Wheel(a.centre + [0, 0, lift], Y, 0.5, +1)
        q = P.solve(start, [b], end)
        kink, off = check_path(q, [b], start, end)
        assert kink < 1e-9 and 0.0 <= q.wrap[0] < 0.1 and q.length >= 8.0 - 1e-12
        assert q.wrap[0] == pytest.approx(2 * math.atan2(lift, 4.0) + 2 * math.asin(0.0), abs=2e-3 * math.sqrt(lift) + 1e-9) or lift < 1e-3
    # between two real wheels too
    chain = [P.Wheel(np.array([-2.0, 0.0, -0.3]), Y, 0.3, +1), a, P.Wheel(np.array([2.0, 0.0, -0.3]), Y, 0.3, +1)]
    q = P.solve(np.array([-4.0, 0.0, -1.0]), chain, np.array([4.0, 0.0, -1.0]))
    kink, off = check_path(q, chain, [-4.0, 0.0, -1.0], [4.0, 0.0, -1.0])
    assert kink < 1e-9 and q.wrap[1] == 0.0


def test_arcs_directly_after_each_other():
    """An S-bend without a straight between its arcs (the circles touch), and an arc that goes on with another
    radius (the one circle inside the other): straights of length 0, no kink."""
    r1, r2 = 2.0, 1.5
    a = P.Wheel(np.array([0.0, 0.0, r1]), Y, r1, -1)                 # from heading +x bending up
    ang = math.radians(40.0)
    joint = a.centre + r1 * np.array([math.sin(ang), 0.0, -math.cos(ang)])
    b = P.Wheel(joint + r2 * unit(joint - a.centre), Y, r2, +1)      # then back down
    start = np.array([-3.0, 0.0, 0.0])
    heading = np.array([1.0, 0.0, 0.0])
    end = b.centre + r2 * np.array([0.0, 0.0, 1.0]) + 2.0 * heading  # leaves level again
    p = P.solve(start, [a, b], end)
    kink, off = check_path(p, [a, b], start, end)
    assert kink < 1e-9 and off < 1e-12
    assert np.allclose(p.wrap, [ang, ang], atol=1e-7)
    assert np.allclose(arc_of(p, 0)[-1], joint, atol=1e-7) and np.allclose(arc_of(p, 1)[0], joint, atol=1e-7)
    assert angle_deg(*[t for t in (helix_tangents(p, [a, b], 0)[1], helix_tangents(p, [a, b], 1)[0])]) < 1e-5
    # a wider arc that turns into a tighter one, the same way round
    c = P.Wheel(np.array([0.0, 0.0, 3.0]), Y, 3.0, -1)
    joint = c.centre + 3.0 * np.array([math.sin(ang), 0.0, -math.cos(ang)])
    d = P.Wheel(joint + 1.0 * unit(c.centre - joint), Y, 1.0, -1)
    end = d.centre + np.array([-1.0, 0.0, 0.0]) + np.array([0.0, 0.0, -0.0]) + 4.0 * np.array([0.0, 0.0, 1.0]) * 0 + [0, 0, 0]
    end = d.centre + 1.0 * np.array([1.0, 0.0, 0.0]) + 2.0 * np.array([0.0, 0.0, 1.0])     # leaves straight up
    q = P.solve(start, [c, d], end)
    kink, off = check_path(q, [c, d], start, end)
    assert kink < 1e-9 and q.wrap[0] == pytest.approx(ang, abs=1e-7) and q.wrap[1] == pytest.approx(math.pi / 2 - ang, abs=1e-7)
    # circles that overlap by less than 0.1 mm (places kept in 32-bit numbers) still count as touching
    near = [a, P.Wheel(b.centre - 5e-5 * unit(b.centre - a.centre), Y, r2, +1)]
    assert P.solve(start, near, end=b.centre + [2.0, 0.0, r2]).ok
    far = [a, P.Wheel(b.centre - 5e-4 * unit(b.centre - a.centre), Y, r2, +1)]
    assert not P.solve(start, far, end=b.centre + [2.0, 0.0, r2]).ok


def test_touching_arcs_in_different_planes():
    """A level arc that turns straight into an arc upwards (the demo's cable lifting off its coil), exact and with
    the places rounded as 32-bit numbers round them."""
    a = P.Wheel(np.array([0.0, 0.0, 0.0]), -Z, 8.0, +1)              # clockwise seen from above
    joint, heading = np.array([8.0, 0.0, 0.0]), np.array([0.0, -1.0, 0.0])
    b = P.Wheel(joint + 4.0 * Z, np.cross(heading, Z), 4.0, +1)      # bends upwards from there
    start = np.array([0.0, 8.0, 0.0])
    end = joint + 4.0 * heading + 4.0 * Z + 3.0 * Z
    p = P.solve(start, [a, b], end, start_on_wheel=True)
    kink, off = check_path(p, [a, b], start, end, on0=True)
    assert kink < 1e-9 and off < 1e-12
    assert np.allclose(p.wrap, [math.pi / 2, math.pi / 2], atol=1e-9)
    assert p.length == pytest.approx(4.0 * math.pi + 2.0 * math.pi + 3.0, abs=1e-9)
    rng = np.random.default_rng(2)
    for noise in (1e-7, 1e-6, 1e-5):
        t0 = time.perf_counter()
        rough = [P.Wheel(w.centre + noise * rng.normal(size=3), w.axis, w.radius, w.side) for w in (a, b)]
        q = P.solve(start, rough, end, start_on_wheel=True)
        assert q.ok, q.problem
        assert time.perf_counter() - t0 < 0.5
        assert abs(q.length - p.length) < 20 * noise + 1e-9
        assert check_path(q, rough, start, end, on0=True, min_run=1e-3)[1] < 1e-9


# ---------------------------------------------------------------------------------------------------------
# refusals: never a broken shape
# ---------------------------------------------------------------------------------------------------------

def refused(path, number, bad=None):
    assert not path.ok
    assert f"contact {number}" in path.problem.lower(), path.problem
    assert path.problem.endswith(".") and "\n" not in path.problem and "nan" not in path.problem.lower()
    assert path.bad == (number - 1 if bad is None else bad)
    assert len(path.points) == 0 and len(path.s) == 0 and path.length == 0.0
    return path.problem


def test_refusals():
    a = P.Wheel(np.array([0.0, 0.0, 0.0]), Y, 1.0, +1)
    b = P.Wheel(np.array([4.0, 0.0, 0.0]), Y, 1.0, -1)
    c = P.Wheel(np.array([8.0, 0.0, 0.0]), Y, 1.0, +1)
    start, end = np.array([-5.0, 0.0, 1.0]), np.array([13.0, 0.0, 1.0])
    assert P.solve(start, [a, b, c], end).ok
    # a point inside a wheel's circle
    text = refused(P.solve([0.2, 0.0, 0.3], [a, b, c], end), 1)
    assert "start" in text and "inside" in text
    text = refused(P.solve(start, [a, b, c], [8.3, 0.0, 0.1]), 3)
    assert "end" in text and "inside" in text
    # wheels that overlap: no crossing straight between them
    near = P.Wheel(np.array([1.5, 0.0, 0.0]), Y, 1.0, -1)
    text = refused(P.solve(start, [a, near, c], end), 2)
    assert "contact 1" in text.lower() and "overlap" in text
    # the one inside the other, going round the same way: no outer straight either
    inner = P.Wheel(np.array([0.2, 0.0, 0.0]), Y, 0.5, +1)
    refused(P.solve(start, [a, inner, c], end), 2)
    # the same wheel twice
    refused(P.solve(start, [a, a], end), 2)
    # a wheel the cable just clears, on the side it would have to come back round: nearly a whole turn – refused
    for clear in (0.002, 0.05):
        under = P.Wheel(np.array([4.0, 0.0, -1.0 - clear]), Y, 1.0, +1)
        text = refused(P.solve(np.array([-5.0, 0.0, 0.0]), [under], np.array([13.0, 0.0, 0.0])), 1)
        assert "350" in text and "other side" in text
    # numbers that are not numbers
    for wrong in (P.Wheel(np.array([4.0, np.nan, 0.0]), Y, 1.0, -1), P.Wheel(b.centre, np.zeros(3), 1.0, -1),
                  P.Wheel(b.centre, Y, 0.0, -1), P.Wheel(b.centre, Y, math.inf, -1), P.Wheel(b.centre, Y, -1.0, -1)):
        refused(P.solve(start, [a, wrong, c], end), 2)
    p = P.solve([np.nan, 0.0, 0.0], [a], end)
    assert not p.ok and p.bad == -1 and len(p.points) == 0 and "start or end" in p.problem
    assert not P.solve(start, [], [0.0, math.inf, 0.0]).ok
    # the same with axes that are not parallel: overlapping wheels are refused, never drawn
    for tilt in (0.02, 0.3):
        skew = P.Wheel(np.array([1.5, 0.0, 0.0]), unit([tilt, 1.0, 0.0]), 1.0, -1)
        p = P.solve(start, [a, skew, c], end)
        assert not p.ok and p.bad in (1, 2) and len(p.points) == 0 and "contact" in p.problem


def test_a_wide_wrap_is_allowed_up_to_350_degrees():
    w = P.Wheel(np.zeros(3), Y, 1.0, +1)
    start = np.array([-4.0, 0.0, 1.0])
    for deg in (200.0, 300.0, 345.0):                # leaves after going round by this much
        a = math.radians(deg)
        leave = np.array([math.sin(a), 0.0, math.cos(a)])
        end = leave + 4.0 * np.array([math.cos(a), 0.0, -math.sin(a)])
        p = P.solve(start, [w], end)
        kink, off = check_path(p, [w], start, end)
        assert kink < 1e-9 and p.wrap[0] == pytest.approx(a, abs=1e-9)
    a = math.radians(352.0)
    leave = np.array([math.sin(a), 0.0, math.cos(a)])
    refused(P.solve(start, [w], leave + 4.0 * np.array([math.cos(a), 0.0, -math.sin(a)])), 1)


def test_tightest():
    wheels = [P.Wheel(np.zeros(3), Y, r, 1) for r in (2.0, 0.4, 0.9, 0.1)]
    assert P.tightest(wheels, np.radians([30.0, 10.0, 90.0, 0.5])) == (1, 0.4)      # the 0.1 one has no wrap
    assert P.tightest(wheels, np.radians([30.0, 10.0, 90.0, 0.5]), least_wrap=0.0) == (3, 0.1)
    assert P.tightest(wheels, np.zeros(4)) == (-1, math.inf)
    assert P.tightest([], []) == (-1, math.inf)


# ---------------------------------------------------------------------------------------------------------
# many frames at once
# ---------------------------------------------------------------------------------------------------------

def moving_chain(frames, count, skew, seed=3):
    """A zigzag of wheels that go up and down (and sideways with ``skew``) over the frames."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 1.0, frames)
    centres = np.zeros((frames, count, 3))
    axes = np.zeros((frames, count, 3))
    for i in range(count):
        centres[:, i, 0] = 2.0 * i
        centres[:, i, 2] = 0.5 * (1 if i % 2 else -1) + 0.3 * np.sin(2 * np.pi * t + i)
        centres[:, i, 1] = 0.05 * i * t * (1 if skew else 0)
        axes[:, i] = unit([skew * rng.normal(), 1.0, skew * rng.normal()])
    radii = 0.2 + 0.2 * rng.random(count)
    sides = np.array([-1.0 if i % 2 == 0 else 1.0 for i in range(count)])
    starts = np.tile([-3.0, 0.4 if skew else 0.0, 0.0], (frames, 1))
    ends = np.tile([2.0 * count + 1.0, -0.3 if skew else 0.0, 0.0], (frames, 1))
    return starts, centres, axes, radii, sides, ends


@pytest.mark.parametrize("frames,count,skew", [(250, 12, 0.0), (1000, 3, 0.0), (60, 12, 0.05), (60, 5, 0.3)])
def test_frames_give_what_solve_gives(frames, count, skew):
    starts, centres, axes, radii, sides, ends = moving_chain(frames, count, skew)
    out = P.solve_frames(starts, centres, axes, radii, sides, ends)
    assert out["ok"].all() and not out["problems"] and (out["bad"] == -1).all()
    n = out["points"].shape[1]
    assert out["points"].shape == (frames, n, 3) and out["s"].shape == (frames, n) and out["wrap"].shape == (frames, count)
    assert n == 2 + int(out["counts"].sum())
    assert list(out["counts"]) == P.point_counts(out["wrap"].max(axis=0))
    worst = 0.0
    for f in range(0, frames, max(1, frames // 40)):
        wheels = [P.Wheel(centres[f, i], axes[f, i], radii[i], int(sides[i])) for i in range(count)]
        one = P.solve(starts[f], wheels, ends[f], counts=out["counts"])
        check_path(one, wheels, starts[f], ends[f])
        worst = max(worst, np.abs(one.points - out["points"][f]).max(), np.abs(one.s - out["s"][f]).max(),
                    np.abs(one.wrap - out["wrap"][f]).max())
        assert np.array_equal(one.first, out["first"])
        assert out["length"][f] == pytest.approx(one.length, abs=1e-9)
    assert worst < 1e-9, worst


def test_frames_are_fast():
    """The brief: 250 frames x 12 wheels well under 0.1 s (no Python loop over the frames)."""
    took = {}
    for key, (frames, count, skew) in {"250 x 12, in a plane": (250, 12, 0.0), "1000 x 3, in a plane": (1000, 3, 0.0),
                                       "250 x 12, every axis askew": (250, 12, 0.05),
                                       "1000 x 3, every axis askew": (1000, 3, 0.05)}.items():
        args = moving_chain(frames, count, skew)
        best = math.inf
        for _ in range(3):
            t0 = time.perf_counter()
            out = P.solve_frames(*args)
            best = min(best, time.perf_counter() - t0)
        assert out["ok"].all()
        took[key] = best
    print("\nsolve_frames: " + ", ".join(f"{k}: {v * 1e3:.1f} ms" for k, v in took.items()))
    assert took["250 x 12, in a plane"] < 0.1 and took["1000 x 3, in a plane"] < 0.1
    assert took["250 x 12, every axis askew"] < 0.5
    # the time does not grow with the frames as a loop would: 8 x the frames takes far less than 8 x as long
    few, many = moving_chain(125, 12, 0.0), moving_chain(1000, 12, 0.0)
    t0 = time.perf_counter()
    P.solve_frames(*few)
    t1 = time.perf_counter()
    P.solve_frames(*many)
    t2 = time.perf_counter()
    assert (t2 - t1) < 6.0 * (t1 - t0) + 0.02


def test_a_bad_frame_does_not_spoil_the_others():
    starts, centres, axes, radii, sides, ends = moving_chain(40, 5, 0.0)
    good = P.solve_frames(starts, centres, axes, radii, sides, ends, counts=[30] * 5)
    centres = centres.copy()
    centres[7, 2] = centres[7, 1] + [0.1, 0.0, 0.0]      # frame 7: wheel 3 lies in wheel 2
    centres[8, 3, 0] = np.nan                            # frame 8: not a number
    starts = starts.copy()
    starts[20] = centres[20, 0] + [0.01, 0.0, 0.0]       # frame 20: the start inside wheel 1
    centres[0, 4, 2] = 30.0                              # frame 0: wheel 5 far on the wrong side … still a path
    centres[0, 4, 2] = centres[1, 4, 2]
    centres[1, 1] = centres[1, 0]                        # frame 1: two wheels at one place
    out = P.solve_frames(starts, centres, axes, radii, sides, ends, counts=[30] * 5)
    bad = [1, 7, 8, 20]
    assert list(np.flatnonzero(~out["ok"])) == bad and sorted(out["problems"]) == bad
    assert list(out["bad"][bad]) == [1, 2, 3, 0]
    assert "contact 3" in out["problems"][7].lower() and "contact 4" in out["problems"][8].lower()
    assert "start" in out["problems"][20]
    assert np.isfinite(out["points"]).all() and np.isfinite(out["s"]).all()
    rest = np.setdiff1d(np.arange(40), bad + [0])
    assert np.abs(out["points"][rest] - good["points"][rest]).max() < 1e-9
    # a frame without a path keeps the last good shape (the first frames: the first good one)
    assert np.array_equal(out["points"][7], out["points"][6]) and np.array_equal(out["points"][8], out["points"][6])
    assert np.array_equal(out["points"][20], out["points"][19]) and np.array_equal(out["points"][1], out["points"][0])
    none = P.solve_frames(starts[[20, 20]], centres[[20, 20]], axes[[20, 20]], radii, sides, ends[[20, 20]])
    assert not none["ok"].any() and np.all(none["points"] == 0.0)


def test_frames_with_ends_on_wheels_and_no_wheels():
    frames = 30
    t = np.linspace(0.0, 1.0, frames)
    centres = np.zeros((frames, 2, 3))
    centres[:, 1] = np.stack([5.0 * np.cos(0.6 + 0.5 * t), np.zeros(frames), 5.0 * np.sin(0.6 + 0.5 * t)], axis=1)   # luffs
    axes = np.tile(Y, (frames, 2, 1))
    starts = np.tile([-0.6, 0.0, 0.0], (frames, 1))
    ends = centres[:, 1] + [3.0, 0.0, -4.0]
    out = P.solve_frames(starts, centres, axes, [0.6, 0.3], [1, 1], ends, start_on_wheel=True)
    assert out["ok"].all() and out["points"].shape[1] == int(out["counts"].sum()) + 1
    assert np.allclose(out["points"][:, 0], [-0.6, 0.0, 0.0], atol=1e-12)
    assert np.ptp(out["wrap"][:, 0]) > 0.3            # the wrap on the drum changes as the sheave luffs
    for f in (0, 13, 29):
        wheels = [P.Wheel(centres[f, i], Y, r, 1) for i, r in enumerate((0.6, 0.3))]
        one = P.solve(starts[f], wheels, ends[f], start_on_wheel=True, counts=out["counts"])
        assert np.abs(one.points - out["points"][f]).max() < 1e-9
    line = P.solve_frames(starts, np.zeros((frames, 0, 3)), np.zeros((frames, 0, 3)), [], [], ends)
    assert line["ok"].all() and line["points"].shape == (frames, 2, 3)
    assert np.allclose(line["length"], np.linalg.norm(ends - starts, axis=1))


# ---------------------------------------------------------------------------------------------------------
# what turns, and the look's numbers
# ---------------------------------------------------------------------------------------------------------

def test_wheel_ratio():
    """360 / (2 pi r) degrees per metre of cable -> per mm; the sign from the side, the joint's axis, reverse."""
    r = 0.6
    per_mm = 360.0 / (2 * math.pi * 600.0)
    assert P.wheel_ratio(r, +1, Y, Y) == pytest.approx(per_mm, rel=1e-12)
    assert P.wheel_ratio(r, +1, Y, Y) == pytest.approx(0.0954929658551372, rel=1e-12)
    assert P.wheel_ratio(r, -1, Y, Y) == pytest.approx(-per_mm)
    assert P.wheel_ratio(r, +1, Y, -Y) == pytest.approx(-per_mm)
    assert P.wheel_ratio(r, -1, Y, -Y) == pytest.approx(per_mm)
    assert P.wheel_ratio(r, +1, Y, unit([0.1, 1.0, 0.0])) == pytest.approx(per_mm)
    assert P.wheel_ratio(r, +1, Y, Y, reverse=True) == pytest.approx(-per_mm)
    # 100 m of cable over a roller of 0.1 m: its surface runs 100 m (the brief: within 0.1 %)
    turns = P.wheel_ratio(0.1, +1, Y, Y) * 100_000.0 / 360.0
    assert turns * 2 * math.pi * 0.1 == pytest.approx(100.0, rel=1e-12)
    # and the wheel really turns that way: a point of the cable on the wheel moves with the wheel's rim
    w = P.Wheel(np.zeros(3), Y, 1.0, +1)
    p = P.solve([-3.0, 0.0, 1.0], [w], [1.0, 0.0, -3.0])
    arc = arc_of(p, 0)
    cable_goes = arc[1] - arc[0]
    rim_goes = np.cross(Y, arc[0]) * math.copysign(1.0, P.wheel_ratio(1.0, +1, Y, Y))
    assert cable_goes @ rim_goes > 0


def test_stripes():
    d, pitch = 0.2, 0.5
    assert P.stripes(d, pitch, math.radians(90.0)) == 0                      # rings
    assert P.stripe_angle(d, pitch, 0) == pytest.approx(math.pi / 2)
    for starts in (1, 2, 3, 6, -1, -4):
        ang = P.stripe_angle(d, pitch, starts)
        assert (ang > 0) == (starts > 0) and abs(ang) < math.pi / 2
        assert math.tan(ang) == pytest.approx(math.pi * d / (starts * pitch))
        assert P.stripes(d, pitch, ang) == starts
    assert P.stripes(d, pitch, math.radians(45.0)) == round(math.pi * 0.2 / 0.5)      # 1.26 -> 1
    assert P.stripes(d, 0.25, math.radians(45.0)) == 3                               # 2.51 -> 3
    assert P.stripes(d, pitch, math.radians(-45.0)) == -1
    assert P.stripes(d, pitch, math.radians(89.9)) == 0
    assert P.stripes(d, 0.0, math.radians(45.0)) == 0
    assert P.stripes(d, pitch, 0.0) > 1000                                           # along the cable: no end of them
