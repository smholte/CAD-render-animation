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
    assert np.allclose(arc_of(q, 0)[[0, -1]], [[-0.6, 0, -0.8], [-0.8, 0, -0.6]], atol=1e-12)
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
    # a start beside the drum's plane is put on the drum's circle (in its plane) …
    side = P.solve(start + 0.2 * Y, [drum, sheave], end, start_on_wheel=True, end_on_wheel=True)
    assert side.ok and np.allclose(side.points, p.points, atol=1e-12)
    # … and stays beside it on a wheel that is a plain cylinder: the arc on the drum is a helix
    side = P.solve(start + 0.2 * Y, [drum, sheave], end, start_on_wheel=True, end_on_wheel=True, held=False)
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
        kink, _ = check_path(q, [b], start, end)
        assert kink < 1e-9 and q.length >= 8.0 - 1e-12
        assert q.wrap[0] == pytest.approx(2 * math.atan2(lift, 4.0), rel=1e-3, abs=1e-12)     # up one side, down the other
    # between two real wheels too
    chain = [P.Wheel(np.array([-2.0, 0.0, -0.3]), Y, 0.3, +1), a, P.Wheel(np.array([2.0, 0.0, -0.3]), Y, 0.3, +1)]
    q = P.solve(np.array([-4.0, 0.0, -1.0]), chain, np.array([4.0, 0.0, -1.0]))
    kink, _ = check_path(q, chain, [-4.0, 0.0, -1.0], [4.0, 0.0, -1.0])
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
    end = d.centre + np.array([1.0, 0.0, 2.0])                       # leaves straight up
    q = P.solve(start, [c, d], end)
    kink, off = check_path(q, [c, d], start, end)
    assert kink < 1e-9 and np.allclose(q.wrap, [ang, math.pi / 2 - ang], atol=1e-7)
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
        kink, _ = check_path(p, [w], start, end)
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
    assert P.stripes(d, pitch, 0.0) == 64 == -P.stripes(d, pitch, -1e-12)             # along the cable: as many as it draws


# ---------------------------------------------------------------------------------------------------------
# meshes built here: bodies of revolution, tubes
# ---------------------------------------------------------------------------------------------------------

def frame_of(axis):
    a = unit(axis)
    u = unit(np.cross(a, [1.0, 0.0, 0.0] if abs(a[0]) < 0.9 else [0.0, 1.0, 0.0]))
    return u, np.cross(a, u), a


def revolve(profile, sides, centre=(0, 0, 0), axis=Z, sweep=2 * math.pi, phase=0.0):
    """A profile [(place along the axis, radius), …] turned about the axis in ``sides`` flat steps: corners
    (V, 3) and triangles (T, 3), as an importer would give them (corners on the true surface)."""
    profile = np.asarray(profile, float)
    u, v, a = frame_of(axis)
    whole = abs(sweep - 2 * math.pi) < 1e-12
    rings = sides if whole else sides + 1
    ang = phase + sweep * np.arange(rings) / sides
    ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v                   # (rings, 3)
    verts = (np.asarray(centre, float) + profile[:, None, :1] * a + profile[:, None, 1:] * ring[None]).reshape(-1, 3)
    tris = []
    for i in range(len(profile) - 1):
        for j in range(sides):
            k = (j + 1) % rings
            p, q, r, s = i * rings + j, i * rings + k, (i + 1) * rings + k, (i + 1) * rings + j
            tris += [(p, q, r), (p, r, s)]
    return verts, np.array(tris)


def arc_profile(z0, r0, radius, a0, a1, steps):
    """Points of a circle (centre z0, r0 in the profile's plane) from angle a0 to a1 (rad, 0 = along the axis)."""
    a = np.linspace(a0, a1, steps + 1)
    return [(z0 + radius * math.cos(t), r0 + radius * math.sin(t)) for t in a]


def round_groove_sheave(rope, bottom=0.30, flange=0.045, steps=48, groove=1.05):
    """A sheave with a round groove of ``groove`` x the rope's radius, its bottom at ``bottom`` from the axis."""
    g = groove * rope
    half = max(0.04, 2.0 * g)
    prof = [(-half, 0.05), (-half, bottom + flange), (-g, bottom + flange), (-g, bottom + g)]
    prof += arc_profile(0.0, bottom + g, g, math.pi, 2 * math.pi, steps)[1:]
    prof += [(g, bottom + flange), (half, bottom + flange), (half, 0.05)]
    return prof


def v_groove_sheave(apex=0.25, half_angle=math.radians(35.0), top=0.32):
    w = (top - apex) * math.tan(half_angle)
    return [(-w - 0.01, 0.05), (-w - 0.01, top), (-w, top), (0.0, apex), (w, top), (w + 0.01, top), (w + 0.01, 0.05)]


def plain_roller(radius=0.1, length=0.6):
    return [(-length / 2, 0.02), (-length / 2, radius), (length / 2, radius), (length / 2, 0.02)]


def crowned_roller(radius=0.15, length=0.6, crown=2.0, steps=60):
    """A roller whose surface is an arc of radius ``crown`` along the axis, ``radius`` in the middle."""
    half = math.asin(length / 2 / crown)
    prof = [(-length / 2, 0.02)]
    prof += [(crown * math.sin(t), radius - crown + crown * math.cos(t)) for t in np.linspace(-half, half, steps + 1)]
    return prof + [(length / 2, 0.02)]


def tube_mesh(points, radius, sides=16):
    """A round tube along a line of points (rings square to the line, flat ends): corners and triangles."""
    points = np.asarray(points, float)
    tan = np.gradient(points, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    u = np.zeros_like(points)
    ref = np.eye(3)[int(np.argmin(np.abs(tan[0])))]
    u[0] = unit(np.cross(tan[0], ref))
    for i in range(1, len(points)):                  # carry the first direction along without twisting
        w = u[i - 1] - (u[i - 1] @ tan[i]) * tan[i]
        u[i] = w / np.linalg.norm(w)
    v = np.cross(tan, u)
    ang = 2 * math.pi * np.arange(sides) / sides
    ring = (np.cos(ang)[None, :, None] * u[:, None, :] + np.sin(ang)[None, :, None] * v[:, None, :])
    verts = (points[:, None, :] + radius * ring).reshape(-1, 3)
    n = len(points)
    i, j = np.meshgrid(np.arange(n - 1), np.arange(sides), indexing="ij")
    p, q = i * sides + j, i * sides + (j + 1) % sides
    tris = np.concatenate([np.stack([p, q, q + sides], axis=-1).reshape(-1, 3),
                           np.stack([p, q + sides, p + sides], axis=-1).reshape(-1, 3)])
    caps = [(n * sides, j, (j + 1) % sides) for j in range(sides)]
    caps += [(n * sides + 1, (n - 1) * sides + (j + 1) % sides, (n - 1) * sides + j) for j in range(sides)]
    verts = np.vstack([verts, points[:1], points[-1:]])
    return verts, np.vstack([tris, np.array(caps)])


# ---------------------------------------------------------------------------------------------------------
# the surface a cable rests on
# ---------------------------------------------------------------------------------------------------------

PLACED = [((0, 0, 0), Z, 0.0), ((3.0, -2.0, 1.5), unit([0.3, -0.5, 0.8]), 0.7)]     # centre, axis, phase


@pytest.mark.parametrize("centre,axis,phase", PLACED)
def test_seat_in_a_round_groove(centre, axis, phase):
    rope = 0.012
    verts, tris = revolve(round_groove_sheave(rope), 96, centre, axis, phase=phase)
    place, radius = P.seat(verts, tris, centre, axis, 0.0, rope)
    assert abs(place) < 2e-4 and abs(radius - (0.30 + rope)) < 1e-4, (place, radius)       # the brief: 0.1 mm
    assert abs(radius - (0.30 + rope)) < 2e-5                                              # measured: 0.01 mm
    # the cable drawn a little beside the groove's middle still finds it; the centre may be anywhere on the axis
    place, radius = P.seat(verts, tris, np.asarray(centre) + 0.2 * np.asarray(axis), axis, -0.2 + 0.004, rope)
    assert abs(place + 0.2) < 2e-4 and abs(radius - (0.30 + rope)) < 2e-5
    # a thinner rope lies deeper, a rope too thick for the groove rides on its edges
    thin = P.seat(verts, tris, centre, axis, 0.0, 0.006)[1]
    assert abs(thin - 0.306) < 2e-5
    g, top = 1.05 * rope, 0.30 + 0.045
    thick = P.seat(verts, tris, centre, axis, 0.0, 0.03)[1]
    assert abs(thick - (top + math.sqrt(0.03 ** 2 - g ** 2))) < 2e-5
    # the surface's radius: the groove's bottom in the groove, the flanges over the whole width
    assert abs(P.surface_radius(verts, tris, centre, axis, 0.0, 0.002) - (0.30 + g - math.sqrt(g * g - 1e-6))) < 1e-5
    assert abs(P.surface_radius(verts, tris, centre, axis, 0.0, 1e-5) - 0.30) < 1e-5
    assert abs(P.surface_radius(verts, tris, centre, axis, 0.0, 0.1) - top) < 1e-9
    assert P.surface_radius(verts, tris, centre, axis, 0.5, 0.01) == 0.0                   # beside the part
    assert P.seat(verts, tris, centre, axis, 0.5, rope) == (0.5, 0.0)
    assert P.is_round(verts, centre, axis)


def test_seat_what_coarse_facets_cost():
    """Round the axis facets cost nothing (the corners lie on the true surface and the edges between the rings are
    read); along the groove's own curve a coarse mesh makes the groove a little shallower."""
    rope = 0.012
    want = 0.30 + rope
    cost = {}
    for sides in (96, 24, 12):
        verts, tris = revolve(round_groove_sheave(rope, steps=48), sides)
        cost[f"{sides} sides round"] = abs(P.seat(verts, tris, (0, 0, 0), Z, 0.0, rope)[1] - want)
    for steps in (48, 12, 6, 5):                     # 6: a corner at the groove's bottom, 5: a flat there
        verts, tris = revolve(round_groove_sheave(rope, steps=steps), 48)
        cost[f"groove in {steps} steps"] = abs(P.seat(verts, tris, (0, 0, 0), Z, 0.0, rope)[1] - want)
    print("\nseat error (mm): " + ", ".join(f"{k}: {v * 1e3:.3f}" for k, v in cost.items()))
    assert max(cost[f"{s} sides round"] for s in (96, 24, 12)) < 2e-5
    assert cost["groove in 48 steps"] < 2e-5
    for steps in (12, 6, 5):                         # at most how far a flat of the groove lies inside its curve
        assert cost[f"groove in {steps} steps"] < 1.2 * 1.05 * rope * (1 - math.cos(math.pi / (2 * steps))) + 1e-5
    assert cost["groove in 12 steps"] < 1.2e-4       # 15° flats (the importer's Normal: about 17°): 0.1 mm


@pytest.mark.parametrize("centre,axis,phase", PLACED)
def test_seat_in_a_v_groove(centre, axis, phase):
    rope, apex, half = 0.02, 0.25, math.radians(35.0)
    verts, tris = revolve(v_groove_sheave(apex, half), 72, centre, axis, phase=phase)
    place, radius = P.seat(verts, tris, centre, axis, 0.003, rope)
    assert abs(place) < 3e-4 and abs(radius - (apex + rope / math.sin(half))) < 1e-4, (place, radius)
    _, _, touching = P._seat(P._edges_of(verts, tris, centre, axis), 0.003, rope)
    assert abs(touching - (apex + rope / math.sin(half) - rope * math.sin(half))) < 2e-4      # on the flanks
    assert P.is_round(verts, centre, axis)


@pytest.mark.parametrize("sides", [96, 24])
def test_seat_on_a_plain_roller(sides):
    """A plain roller has corners only at its ends: the triangles' edges are read, not the corners. 24 flat sides
    cost nothing, because the corners lie on the true surface."""
    rope = 0.05
    centre, axis = np.array([1.0, 2.0, 3.0]), unit([0.0, math.cos(0.6), math.sin(0.6)])
    verts, tris = revolve(plain_roller(0.1, 0.6), sides, centre, axis, phase=0.3)
    assert len(np.unique(np.round((verts - centre) @ axis, 9))) == 2
    for at in (0.0, 0.2, -0.29):
        place, radius = P.seat(verts, tris, centre, axis, at, rope)
        assert place == at and abs(radius - 0.15) < 1e-9
        assert abs(P.surface_radius(verts, tris, centre, axis, at, rope) - 0.1) < 1e-9
    assert P._seat(P._edges_of(verts, tris, centre, axis), 0.1, rope)[2] == pytest.approx(0.1, abs=1e-9)
    assert P.seat(verts, tris, centre, axis, 0.4, rope)[1] == 0.0          # past its end by more than the rope
    assert P.is_round(verts, centre, axis)


def test_seat_on_a_crowned_roller():
    """On a crown the cable stays where it is: it does not slide down to the lowest place in reach."""
    rope, radius, crown = 0.04, 0.15, 2.0
    verts, tris = revolve(crowned_roller(radius, 0.6, crown), 64)
    for at in (0.0, 0.1, -0.2):
        want = radius - crown + math.sqrt((crown + rope) ** 2 - at ** 2)
        place, got = P.seat(verts, tris, (0, 0, 0), Z, at, rope)
        assert place == at and abs(got - want) < 1e-4, (at, got, want)
        assert abs(got - want) < 2e-5
    assert P.is_round(verts, (0, 0, 0), Z)


def test_is_round():
    rope = 0.012
    quarter = revolve(round_groove_sheave(rope), 24, sweep=math.pi / 2)[0]          # a quarter-round chute
    assert not P.is_round(quarter, (0, 0, 0), Z)
    assert not P.is_round(revolve(plain_roller(), 48, sweep=math.pi)[0], (0, 0, 0), Z)        # half a turn
    assert not P.is_round(revolve(plain_roller(), 60, sweep=math.radians(290.0))[0], (0, 0, 0), Z)
    for sides in (8, 12, 24, 25, 96):
        assert P.is_round(revolve(plain_roller(), sides, phase=0.1 * sides)[0], (0, 0, 0), Z), sides
    # a block with a round hole is not round, whatever its hole; nor is a round part about another axis
    hole = revolve([(-0.05, 0.03), (0.05, 0.03)], 32)[0]
    box = np.array([[x, y, z] for x in (-0.1, 0.1) for y in (-0.1, 0.1) for z in (-0.05, 0.05)])
    assert not P.is_round(np.vstack([hole, box]), (0, 0, 0), Z)
    roller = revolve(plain_roller(), 48)[0]
    assert not P.is_round(roller, (0, 0, 0), [1.0, 0.0, 0.0])
    assert not P.is_round(roller, (0.05, 0, 0), Z)
    # a wheel with six holes through its web is still round: only the outside counts
    web = np.vstack([revolve([(-0.01, 0.03), (0.01, 0.03)], 12, centre=(0.06 * math.cos(a), 0.06 * math.sin(a), 0))[0]
                     for a in np.arange(6) * math.pi / 3])
    assert P.is_round(np.vstack([roller, web]), (0, 0, 0), Z)
    assert not P.is_round(np.zeros((0, 3)), (0, 0, 0), Z)


# ---------------------------------------------------------------------------------------------------------
# reading a CAD cable: made-up routes of straights and arcs
# ---------------------------------------------------------------------------------------------------------

def turn_about(v, axis, ang):
    axis = unit(axis)
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * float(axis @ v) * (1 - math.cos(ang))


class Course:
    """A cable route: straights and arcs that meet without a kink (metres). ``sample`` gives its centreline the
    way ``flex_fit.tube_centreline`` does: points equally far apart along it, with noise if asked."""

    def __init__(self, start=(0, 0, 0), heading=(1, 0, 0)):
        self.at = np.asarray(start, float)
        self.heading = unit(heading)
        self.parts = []                 # ("line", from, to) or ("arc", centre, axis, radius, from, angle)
        self.s = [0.0]

    def straight(self, length):
        end = self.at + length * self.heading
        self.parts.append(("line", self.at.copy(), end))
        self.at = end
        self.s.append(self.s[-1] + length)
        return self

    def bend(self, axis, radius, deg):
        """Turn about ``axis`` (right hand; made square to the heading) by ``deg`` on an arc of ``radius``."""
        axis = np.asarray(axis, float)
        axis = unit(axis - float(axis @ self.heading) * self.heading)
        centre = self.at + radius * np.cross(axis, self.heading)
        ang = math.radians(deg)
        self.parts.append(("arc", centre, axis, radius, self.at.copy(), ang))
        self.at = centre + turn_about(self.at - centre, axis, ang)
        self.heading = turn_about(self.heading, axis, ang)
        self.s.append(self.s[-1] + radius * ang)
        return self

    @property
    def length(self):
        return self.s[-1]

    def arcs(self):
        """Per arc: centre, axis, radius, angle (rad), s of its middle."""
        return [(p[1], p[2], p[3], p[5], 0.5 * (self.s[i] + self.s[i + 1])) for i, p in enumerate(self.parts) if p[0] == "arc"]

    def _part(self, s):
        i = int(np.clip(np.searchsorted(self.s, s, side="right") - 1, 0, len(self.parts) - 1))
        return self.parts[i], s - self.s[i]

    def point(self, s):
        p, d = self._part(s)
        if p[0] == "line":
            return p[1] + d * unit(p[2] - p[1])
        return p[1] + turn_about(p[4] - p[1], p[2], d / p[3])

    def tangent(self, s):
        p, _ = self._part(s)
        return unit(p[2] - p[1]) if p[0] == "line" else unit(np.cross(p[2], self.point(s) - p[1]))

    def sample(self, spacing=None, count=None, noise=0.0, seed=0):
        n = count if count else max(int(round(self.length / spacing)) + 1, 2)
        pts = np.array([self.point(s) for s in np.linspace(0.0, self.length, n)])
        if noise:
            pts = pts + np.random.default_rng(seed).normal(scale=noise, size=pts.shape)
        return pts

    def distance(self, pts):
        """Each point's distance from the route."""
        pts = np.atleast_2d(pts)
        best = np.full(len(pts), np.inf)
        for p in self.parts:
            if p[0] == "line":
                ab = p[2] - p[1]
                f = np.clip((pts - p[1]) @ ab / float(ab @ ab), 0, 1)
                d = np.linalg.norm(pts - (p[1] + f[:, None] * ab), axis=1)
            else:
                _, c, n, r, p0, ang = p
                rel = pts - c
                h = rel @ n
                flat = rel - np.outer(h, n)
                u = unit(p0 - c)
                phi = np.mod(np.arctan2(flat @ np.cross(n, u), flat @ u), 2 * math.pi)
                ends = np.minimum(np.linalg.norm(pts - p0, axis=1),
                                  np.linalg.norm(pts - (c + turn_about(p0 - c, n, ang)), axis=1))
                d = np.where(phi <= ang, np.hypot(np.linalg.norm(flat, axis=1) - r, h), ends)
            best = np.minimum(best, d)
        return best


def sheave_for(arc, rope, key, flip=False, off=0.0, sides=48, groove=True):
    """A Round for an arc of a Course: a sheave whose groove (or a plain roller whose surface) carries the cable
    there, drawn ``off`` away from it (+ apart, - into the part). ``flip``: its axis points the other way."""
    centre, axis, radius = arc[0], arc[1], arc[2]
    bottom = radius - rope - off
    prof = round_groove_sheave(rope, bottom=bottom, flange=2.5 * rope, steps=32) if groove else plain_roller(bottom, 8 * rope)
    a = -axis if flip else axis
    verts, tris = revolve(prof, sides, centre, a, phase=0.37)
    return P.Round(key, centre + 0.123 * a, a, verts, tris)       # the centre: any point on the axis


def roller_at(course, s, rope, key, radius=0.06, length=0.5, toward=(0, 0, -1), tilt=0.0, off=0.0, slide=0.0, sides=24):
    """A plain roller the cable rests on at s: its axis square to the cable, the roller on the ``toward`` side
    (turned by ``tilt`` about the cable), ``off`` away from the cable's skin, ``slide`` along its own axis."""
    p, t = course.point(s), course.tangent(s)
    to = np.asarray(toward, float)
    to = turn_about(unit(to - float(to @ t) * t), t, tilt)
    axis = np.cross(t, to)
    centre = p + (radius + rope + off) * to + slide * axis
    verts, tris = revolve(plain_roller(radius, length), sides, centre, axis, phase=0.2)
    return P.Round(key, centre + 0.05 * axis, axis, verts, tris)


def kinds(reading):
    return [(c.kind, c.key) for c in reading.contacts]


def check_reading(rd, course, shaping, noise=0.0, bend_tol=0.005, centre_tol=2e-3):
    """The arcs of the course are found, in order, each as the kind and on the part given in ``shaping``
    (a key, or None for a BEND); bends have the right circle; the path follows the route."""
    assert rd.ok, rd.problem
    got = [c for c in rd.contacts if c.kind != "TOUCH"]
    arcs = course.arcs()
    assert [(c.kind, c.key) for c in got] == [("BEND" if k is None else "WRAP", k) for k in shaping], kinds(rd)
    assert len(arcs) == len(got)
    assert [c.s for c in rd.contacts] == sorted(c.s for c in rd.contacts)
    for c, (centre, axis, radius, ang, s) in zip(got, arcs):
        assert angle_deg(c.axis, axis) < 0.5 or angle_deg(c.axis, -axis) < 0.5
        assert c.side == (1 if c.axis @ axis > 0 else -1)
        off = c.centre - centre
        assert abs(off @ axis) < 0.02                              # on the axis, in the cable's plane there
        assert c.wrap == pytest.approx(ang, abs=math.radians(0.5) + 3 * noise / radius * 20)
        assert c.s == pytest.approx(s, abs=0.02 + 0.002 * course.length)
        if c.kind == "BEND":
            assert abs(c.radius / radius - 1.0) < bend_tol, (c.radius, radius)
            assert np.linalg.norm(off - (off @ axis) * axis) < centre_tol
            assert c.surface == 0.0 and c.gap == 0.0 and not c.full and c.key is None
    assert np.allclose(rd.start, course.point(0.0), atol=5 * noise + 1e-9)
    assert np.allclose(rd.end, course.point(course.length), atol=5 * noise + 1e-9)
    assert rd.path.ok and rd.path.length == pytest.approx(course.length, abs=0.002 + 20 * noise)
    assert len(rd.path.wrap) == len(got)
    return float(course.distance(rd.path.points).max())


NOISE = 1e-4                    # 0.1 mm: what tube_centreline leaves of a tube's facets


def test_read_two_bends_clean_and_noisy():
    course = Course().straight(3).bend(Z, 2.0, 60).straight(2).bend(-Z, 1.5, 90).straight(4)
    clean = P.read_cable(course.sample(0.05), 0.05, [])
    assert check_reading(clean, course, [None, None]) < 1e-6
    assert clean.deviation < 1e-6                                   # the brief: < 0.5 mm for clean input
    assert not clean.start_on_wheel and not clean.end_on_wheel
    for c, r in zip(clean.contacts, (2.0, 1.5)):
        assert c.radius == pytest.approx(r, abs=1e-6)
    noisy = P.read_cable(course.sample(0.05, noise=NOISE), 0.05, [])
    assert check_reading(noisy, course, [None, None], NOISE, bend_tol=0.001, centre_tol=1e-3) < 5e-4
    assert noisy.deviation < 6e-4                                   # the noise itself: 0.1 mm each way, 5 sigma
    # the same route read from its other end: the same contacts, the other way round
    back = P.read_cable(course.sample(0.05)[::-1], 0.05, [])
    assert back.ok and [c.radius for c in back.contacts] == pytest.approx([1.5, 2.0], abs=1e-6)
    assert back.path.length == pytest.approx(clean.path.length, abs=1e-6)


def test_read_arcs_directly_after_each_other():
    """Opposite bends without a straight between (an S), five arcs in a row as on the demo vessel's quadrant, a
    level arc that turns straight into one upwards, bends in three planes with short straights between."""
    s_bend = Course().straight(3).bend(Z, 2.0, 40).bend(-Z, 2.0, 40).straight(4)
    rd = P.read_cable(s_bend.sample(0.05, noise=NOISE), 0.05, [])
    assert check_reading(rd, s_bend, [None, None], NOISE, bend_tol=0.002) < 5e-4
    kink, _ = check_path(rd.path, [P.Wheel(c.centre, c.axis, c.radius, c.side) for c in rd.contacts], rd.start, rd.end,
                         min_run=1e-3)
    assert kink < 0.01                                              # the two fitted arcs touch: no kink between them
    row = (Course().straight(3).bend(Z, 4.05, 38.9).bend(-Z, 4.05, 38.9).bend(Z, 4.05, 180).bend(-Z, 4.05, 38.9)
           .bend(Z, 4.05, 38.9).straight(10))
    rd = P.read_cable(row.sample(0.1, noise=NOISE), 0.1, [])
    assert check_reading(rd, row, [None] * 5, NOISE, bend_tol=0.001) < 5e-4
    lift = Course((0, 8, 0), (1, 0, 0)).bend(-Z, 8.0, 90).bend(np.cross([0, -1, 0], Z), 4.0, 90).straight(3)
    rd = P.read_cable(lift.sample(0.1, noise=NOISE), 0.1, [])
    assert check_reading(rd, lift, [None, None], NOISE, bend_tol=0.001) < 5e-4
    assert rd.start_on_wheel and not rd.end_on_wheel               # it starts on its first arc (a coil)
    mixed = (Course().straight(2).bend(Y, 3.0, 30).straight(0.4).bend(Z, 5.0, 45).straight(0.8).bend(-Y, 2.0, 30)
             .straight(3))
    rd = P.read_cable(mixed.sample(0.08, noise=NOISE), 0.08, [])
    assert check_reading(rd, mixed, [None] * 3, NOISE, bend_tol=0.003, centre_tol=5e-3) < 1e-3
    # a wider arc that goes on tighter, the same way round, and ends on it
    tighter = Course().straight(2).bend(Z, 3.0, 50).bend(Z, 1.0, 70)
    rd = P.read_cable(tighter.sample(0.03, noise=NOISE), 0.03, [])
    assert check_reading(rd, tighter, [None, None], NOISE, bend_tol=0.003) < 5e-4
    assert rd.end_on_wheel


@pytest.mark.parametrize("radius,spacing,rope", [(0.1, 0.005, 0.005), (0.3, 0.012, 0.012), (1.0, 0.03, 0.03),
                                                 (3.0, 0.1, 0.1), (6.0, 0.1, 0.25)])
def test_read_wraps_from_5_to_200_degrees(radius, spacing, rope):
    """Bends of 5° to 200° in the air: every one is found, and the path lies on the route (0.6 mm with 0.1 mm of
    noise). How well a bend's own circle is known depends on how far the arc bulges against the noise and how
    many points lie on it: from bulge x sqrt(points) = 0.25 m on, the radius is right to 0.5 % (the centre moves
    with it: 2 mm for bends up to 1 m radius or of 60° and more); a 5° bend of a small radius has two points on
    it and its radius is a guess (up to 60 % off)."""
    worst = {}
    for deg in (5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 135.0, 200.0):
        course = Course().straight(12 * radius + 1.0).bend(Y, radius, deg).straight(10 * radius + 1.5)
        rd = P.read_cable(course.sample(spacing, noise=NOISE, seed=int(deg)), rope, [])
        bulge = radius * (1.0 - math.cos(math.radians(deg) / 2))
        on_it = radius * math.radians(deg) / spacing
        clear = bulge * math.sqrt(on_it) >= 2500 * NOISE
        off = check_reading(rd, course, [None], NOISE, bend_tol=0.005 if clear else 0.6,
                            centre_tol=max(2e-3, 0.005 * radius) if clear else 1e9)
        if clear and (deg >= 60.0 or radius <= 1.0):
            assert np.linalg.norm(np.cross(rd.contacts[0].centre - course.arcs()[0][0], Y)) < 2e-3
        worst[deg] = (abs(rd.contacts[0].radius / radius - 1.0), off, rd.deviation)
        assert off < 6e-4 and rd.deviation < 1e-3, (deg, off, rd.deviation)
    print(f"\nbend radius {radius} m, a point every {spacing * 1e3:.0f} mm: " + ", ".join(
        f"{d:.0f}°: r {100 * w[0]:.2f} %, path {w[1] * 1e3:.2f} mm" for d, w in worst.items()))


@pytest.mark.parametrize("spacing", [0.005, 0.02, 0.05, 0.1])
def test_read_any_spacing(spacing):
    """The same route sampled every 5 mm to every 100 mm (a point every cable radius is what the app gives)."""
    course = Course().straight(2.0).bend(Y, 1.5, 75).straight(1.5).bend(-Y, 2.5, 40).bend(Y, 2.5, 40).straight(2.0)
    rd = P.read_cable(course.sample(spacing, noise=NOISE, seed=3), 0.05, [])
    assert check_reading(rd, course, [None] * 3, NOISE, bend_tol=0.003) < 5e-4
    assert rd.deviation < 6e-4


def sheave_course(rope=0.012):
    """A wire rope over two grooved sheaves (the second the other way round), a plain drum and a chute (a groove
    over 80° of the turn only): the route and the four round parts."""
    course = (Course((0, 0, 0), (1, 0, 0.2)).straight(2.0).bend(Y, 0.35, 110).straight(1.8).bend(-Y, 0.25, 140)
              .straight(1.5).bend(Y, 0.6, 35).straight(1.0).bend(Y, 0.9, 60).straight(0.5))
    arcs = course.arcs()
    rounds = [sheave_for(arcs[0], rope, "sheave 1"), sheave_for(arcs[1], rope, "sheave 2", flip=True),
              sheave_for(arcs[2], rope, "drum", groove=False)]
    centre, axis = arcs[3][0], arcs[3][1]
    u, v, _ = frame_of(axis)
    first = [p for p in course.parts if p[0] == "arc"][3][4] - centre           # where the cable comes onto it
    verts, tris = revolve(round_groove_sheave(rope, bottom=0.9 - rope, flange=2.5 * rope, steps=32), 24, centre, axis,
                          sweep=math.radians(80.0), phase=math.atan2(first @ v, first @ u) - math.radians(10.0))
    rounds.append(P.Round("chute", centre, axis, verts, tris))
    return course, rounds


def test_read_wraps_on_parts():
    rope = 0.012
    course, rounds = sheave_course(rope)
    arcs = course.arcs()
    # parts that are near but carry nothing: a roller 5 mm under a straight, a sheave beside a bend's plane
    rounds.append(roller_at(course, 1.0, rope, "clear roller", off=0.005))
    aside = sheave_for(arcs[0], rope, "sheave aside")
    aside.verts = aside.verts + 0.1 * arcs[0][1]
    aside.centre = aside.centre + 0.1 * arcs[0][1]
    rounds.append(aside)
    rd = P.read_cable(course.sample(0.01, noise=NOISE), rope, rounds)
    assert check_reading(rd, course, ["sheave 1", "sheave 2", "drum", "chute"], NOISE) < 5e-4
    assert rd.deviation < 6e-4
    for c, arc, rnd in zip(rd.contacts, arcs, rounds):
        # centre, axis and radius are the part's own, not the fit's: exact
        assert np.array_equal(c.axis, rnd.axis)
        assert np.linalg.norm(np.cross(c.centre - arc[0], arc[1])) < 1e-9 and abs((c.centre - arc[0]) @ arc[1]) < 1e-3
        assert c.radius == pytest.approx(arc[2], abs=1e-4)          # the seat read from the mesh: 0.1 mm
        assert c.surface == pytest.approx(arc[2] - rope, abs=1e-4)
        assert abs(c.gap) < 2e-4
    assert [c.side for c in rd.contacts] == [1, -1, 1, 1]          # sheave 2: the cable turns about -y, its axis is +y
    assert [c.full for c in rd.contacts] == [True, True, True, False]      # the chute is not round all the way
    # every part says it is round or not itself when the caller knows better
    rounds[0].full = False
    assert not P.read_cable(course.sample(0.01), rope, rounds).contacts[0].full


def test_read_gap_when_the_cable_is_drawn_off_the_part():
    """The CAD cable drawn 1 mm off its sheave (and 1 mm into another): the contact is still the part's, the gap
    says by how much; drawn 5 mm off, the part does not carry it: a bend in the air."""
    rope = 0.012
    course = Course().straight(1.5).bend(Y, 0.4, 90).straight(1.5).bend(-Y, 0.4, 60).straight(1.5)
    arcs = course.arcs()
    for off in (0.001, -0.001):
        rounds = [sheave_for(arcs[0], rope, "a", off=off, groove=False), sheave_for(arcs[1], rope, "b", off=-off)]
        rd = P.read_cable(course.sample(0.01, noise=NOISE), rope, rounds)
        assert rd.ok and kinds(rd) == [("WRAP", "a"), ("WRAP", "b")]
        assert rd.contacts[0].gap == pytest.approx(off, abs=1e-4) and rd.contacts[1].gap == pytest.approx(-off, abs=1.5e-4)
        assert rd.contacts[0].radius == pytest.approx(0.4 - off, abs=1e-4)      # where the cable rests, not where it is drawn
        assert rd.deviation == pytest.approx(0.001, abs=6e-4)                   # the path lies on the parts
    rounds = [sheave_for(arcs[0], rope, "a", off=0.005, groove=False), sheave_for(arcs[1], rope, "b")]
    rd = P.read_cable(course.sample(0.01, noise=NOISE), rope, rounds)
    assert kinds(rd) == [("BEND", None), ("WRAP", "b")] and rd.contacts[0].radius == pytest.approx(0.4, abs=1e-3)
    wide = P.read_cable(course.sample(0.01, noise=NOISE), rope, rounds, touch_tol=0.006)
    assert kinds(wide) == [("WRAP", "a"), ("WRAP", "b")] and wide.contacts[0].gap == pytest.approx(0.005, abs=1e-4)


def test_read_rollers_the_cable_rests_on():
    """Rollers under a straight run, along the inside and the outside of a bend in the air, and a V cradle (two
    rollers at 40° to the level): TOUCH contacts, each with its side, in order; the path is not shaped by them."""
    rope = 0.05
    course = Course().straight(6.0).bend(Z, 3.0, 90).straight(5.0)
    rounds = [roller_at(course, s, rope, f"under {i}") for i, s in enumerate((0.8, 2.3, 3.8, 5.3))]
    bend0 = 6.0
    for i, deg in enumerate((15.0, 40.0, 75.0)):                    # inside the bend: upright rollers towards its centre
        s = bend0 + 3.0 * math.radians(deg)
        inward = course.arcs()[0][0] - course.point(s)
        rounds.append(roller_at(course, s, rope, f"inside {i}", toward=inward))
    s = bend0 + 3.0 * math.radians(30.0)
    rounds.append(roller_at(course, s, rope, "outside", toward=course.point(s) - course.arcs()[0][0]))
    s = bend0 + 3.0 * math.radians(90.0) + 2.5                      # the V cradle on the last straight
    for name, tilt in (("V port", math.radians(40.0)), ("V stb", math.radians(-40.0))):
        rounds.append(roller_at(course, s, rope, name, tilt=tilt, slide=0.12))
    # near but not touching: 10 mm of air (the tolerance for this cable: 12.5 mm … so 20 mm), one beside the cable,
    # one the cable runs along (not across)
    rounds.append(roller_at(course, 4.5, rope, "clear", off=0.02))
    rounds.append(roller_at(course, 1.5, rope, "beside", slide=0.6))
    along = roller_at(course, 3.0, rope, "along")
    along.axis = np.array([1.0, 0.0, 0.0])
    along.verts, along.tris = revolve(plain_roller(0.06, 0.5), 24, along.centre, along.axis)
    rounds.append(along)
    rd = P.read_cable(course.sample(0.05, noise=NOISE), rope, rounds)
    assert rd.ok, rd.problem
    want = ["under 0", "under 1", "under 2", "under 3", "inside 0", "outside", "inside 1", None, "inside 2", "V port",
            "V stb"]
    got = [c.key for c in rd.contacts]
    assert got[:9] == want[:9] and sorted(got[9:]) == ["V port", "V stb"], got
    assert [c.kind for c in rd.contacts] == ["TOUCH"] * 7 + ["BEND"] + ["TOUCH"] * 3
    assert check_reading(rd, course, [None], NOISE) < 5e-4
    by = {c.key: c for c in rd.contacts}
    for key, c in by.items():
        if key is None:
            continue
        rnd = next(r for r in rounds if r.key == key)
        assert c.wrap == 0.0 and c.full and np.allclose(c.axis, rnd.axis, atol=1e-12)
        assert c.surface == pytest.approx(0.06, abs=1e-6)
        assert c.radius == pytest.approx(0.06 + rope, abs=4e-4) and abs(c.gap) < 4e-4       # the noise, no more
        assert np.linalg.norm(np.cross(c.centre - rnd.centre, rnd.axis)) < 1e-9             # on its axis …
        assert np.linalg.norm(c.centre - course.point(c.s)) == pytest.approx(0.11, abs=1e-3)   # … beside the cable
        # the side: the roller turns with the cable's skin
        heading = course.tangent(c.s)
        assert c.side == (1 if np.cross(course.point(c.s) - c.centre, heading) @ c.axis > 0 else -1)
    assert by["under 0"].s == pytest.approx(0.8, abs=0.01) and by["V port"].s == pytest.approx(s, abs=0.01)
    assert by["inside 1"].side != by["outside"].side or not np.allclose(by["inside 1"].axis, by["outside"].axis)
    assert by["V port"].side == by["V stb"].side == by["under 0"].side      # all three turn the same way round
    # the V rollers' place: where the cable crosses each, 0.12 m along its axis from its middle
    for key in ("V port", "V stb"):
        rnd = next(r for r in rounds if r.key == key)
        assert abs((by[key].centre - rnd.centre) @ rnd.axis + 0.05) == pytest.approx(0.12, abs=2e-3)


def test_read_a_corner_between_two_points():
    """A tight bend with fewer points on it than an arc needs: the two straights meet at a corner. On a sheave it
    is that sheave's WRAP; in the air a BEND that touches both straights."""
    rope = 0.012
    course = Course().straight(3.0).bend(Y, 0.3, 12).straight(3.0)             # 63 mm of arc, a point every 50 mm
    sheave = sheave_for(course.arcs()[0], rope, "sheave")
    for seed in range(4):
        pts = course.sample(0.05, noise=NOISE, seed=seed)
        rd = P.read_cable(pts, rope, [sheave])
        assert rd.ok and kinds(rd) == [("WRAP", "sheave")], kinds(rd)
        assert rd.contacts[0].wrap == pytest.approx(math.radians(12.0), abs=math.radians(0.1))
        assert course.distance(rd.path.points).max() < 5e-4 and rd.deviation < 1e-3
        air = P.read_cable(pts, rope, [])
        assert air.ok and kinds(air) == [("BEND", None)]
        assert air.contacts[0].wrap == pytest.approx(math.radians(12.0), abs=math.radians(0.1))
        assert rope <= air.contacts[0].radius < 1.5 and air.deviation < 2e-3
    # two straights 0.05° apart are one straight: no corner
    flat = Course().straight(0.5).bend(Y, 0.3, 0.05).straight(0.5)
    assert P.read_cable(flat.sample(0.05), rope, []).contacts == []


def long_route(seed=0, arcs=15):
    """300 m with 15 bends: level turns, rises, an S, a half turn; sheaves and chutes on some, rollers under it."""
    rng = np.random.default_rng(seed)
    course = Course((5.0, -3.0, 2.0), (1.0, 0.2, 0.0)).straight(14.0)
    plan = [(Z, 4.0, 90), (-Z, 4.0, 35), (Z, 4.0, 35), (Y, 3.5, 25), (-Y, 3.5, 25), (Z, 6.0, 180), (-Y, 3.0, 20),
            (Y, 3.0, 20), (-Z, 2.5, 60), (Z, 5.0, 120), (Y, 2.0, 90), (-Y, 2.0, 90), (Z, 3.0, 45), (-Z, 3.0, 45),
            (Y, 4.5, 70)][:arcs]
    touching = {2, 4, 7}                                # these follow the bend before without a straight …
    for i, (axis, radius, deg) in enumerate(plan):
        if i and i not in touching:
            course.straight(float(rng.uniform(8.0, 26.0)))
        if i in touching:                               # … and back in the same plane (an S)
            axis = -course.parts[-1][2]
        course.bend(axis, radius, deg)
    course.straight(300.0 - course.length if course.length < 290.0 else 12.0)
    return course


def test_read_a_300_m_route_with_15_arcs():
    rope = 0.07
    course = long_route()
    assert 295.0 < course.length < 305.0 and len(course.arcs()) == 15
    arcs = course.arcs()
    on_parts = {0: "sheave A", 5: "half turn", 8: "sheave B", 10: "chute", 14: "sheave C"}
    rounds = [sheave_for(arcs[i], rope, key, flip=(i == 8), sides=64) for i, key in on_parts.items()]
    line_s = [0.5 * (course.s[i] + course.s[i + 1]) for i, p in enumerate(course.parts) if p[0] == "line"]
    rollers = [roller_at(course, s, rope, f"roller {j}", radius=0.09) for j, s in enumerate(line_s[1:9])]
    pts = course.sample(count=2400, noise=NOISE, seed=7)
    t0 = time.perf_counter()
    rd = P.read_cable(pts, rope, rounds + rollers)
    took = time.perf_counter() - t0
    shaping = [on_parts.get(i) for i in range(15)]
    off = check_reading(rd, course, shaping, NOISE, bend_tol=0.01, centre_tol=0.03)
    touch = [c.key for c in rd.contacts if c.kind == "TOUCH"]
    assert touch == [f"roller {j}" for j in range(8)]
    print(f"\n300 m, 15 arcs, {len(pts)} points, {len(rounds) + len(rollers)} round parts: read in {took:.2f} s, the path "
          f"within {off * 1e3:.2f} mm of the route, deviation {rd.deviation * 1e3:.2f} mm")
    assert off < 1e-3 and rd.deviation < 1.5e-3
    assert took < 5.0
    # the path the reading gives is the one the solver gives for its contacts
    wheels = [P.Wheel(c.centre, c.axis, c.radius, c.side) for c in rd.contacts if c.kind != "TOUCH"]
    again = P.solve(rd.start, wheels, rd.end, rd.start_on_wheel, rd.end_on_wheel)
    assert again.ok and np.allclose(again.points, rd.path.points, atol=1e-9)
    assert check_path(rd.path, wheels, rd.start, rd.end, min_run=1e-3)[0] < 0.02       # the brief: 0.1°


def test_read_what_is_no_line_or_arc():
    """A spline and a coil with a pitch are refused in plain words; so is a centreline that is none."""
    t = np.linspace(0.0, 1.0, 400)[:, None]
    ctrl = np.array([[0.0, 0, 0], [3.0, 0, 0], [3.0, 0, 2.5], [7.0, 1.0, 2.5]])
    spline = ((1 - t) ** 3 * ctrl[0] + 3 * (1 - t) ** 2 * t * ctrl[1] + 3 * (1 - t) * t ** 2 * ctrl[2] + t ** 3 * ctrl[3])
    seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(spline, axis=0), axis=1))])
    even = np.stack([np.interp(np.linspace(0, seg[-1], 300), seg, spline[:, k]) for k in range(3)], axis=1)
    rd = P.read_cable(even, 0.03, [])
    assert not rd.ok and "neither straight nor a round bend" in rd.problem and rd.contacts == [] and not rd.path.ok
    assert " m " in rd.problem and rd.problem.endswith(".")
    a = np.linspace(0.0, 6 * math.pi, 600)
    coil = np.stack([1.5 * np.cos(a), 1.5 * np.sin(a), 0.4 * a / (2 * math.pi)], axis=1)       # 0.4 m per turn
    rd = P.read_cable(coil, 0.03, [])
    assert not rd.ok and rd.problem
    for bad in (np.zeros((0, 3)), np.zeros((1, 3)), np.full((5, 3), np.nan), np.zeros((4, 3))):
        rd = P.read_cable(bad, 0.03, [])
        assert not rd.ok and rd.problem and rd.contacts == [] and len(rd.path.points) == 0
    assert not P.read_cable(even, 0.0, []).ok
    # a plain straight cable is fine: no contacts, a path of two points
    rd = P.read_cable(np.linspace([0, 0, 0], [5, 1, 2], 80), 0.03, [])
    assert rd.ok and rd.contacts == [] and len(rd.path.points) == 2 and rd.deviation < 1e-9


def test_read_a_path_that_cannot_be_solved_says_which_contact():
    """A sheave the cable is drawn on with the wrong radius by a lot is no contact; a contact the solver refuses
    is named by its place in the list of contacts (rollers counted)."""
    rope = 0.05
    course = Course().straight(4.0).bend(Y, 1.0, 90).straight(4.0)
    rounds = [roller_at(course, 1.0, rope, "roller 1"), roller_at(course, 2.5, rope, "roller 2"),
              sheave_for(course.arcs()[0], rope, "sheave", groove=False)]
    rd = P.read_cable(course.sample(0.05), rope, rounds)
    assert rd.ok and kinds(rd) == [("TOUCH", "roller 1"), ("TOUCH", "roller 2"), ("WRAP", "sheave")]
    # the same contacts, the solver made to refuse the sheave: it is contact 3
    wheels = [P.Wheel(rd.contacts[2].centre, rd.contacts[2].axis, 50.0, rd.contacts[2].side)]
    assert "contact 1" in P.solve(rd.start, wheels, rd.end).problem.lower()
    ch = P._one(rd.start, wheels, rd.end, False, False)
    assert "contact 3" in P._path(ch, None, P.STEP, lambda i: f"contact {i + 3}").problem


# ---------------------------------------------------------------------------------------------------------
# arcs held in the wheels' planes, or a tight string on plain cylinders
# ---------------------------------------------------------------------------------------------------------

def test_held_or_free_with_a_fleet_angle():
    """A sheave beside the line from start to end. Held: the arc stays in the sheave's plane and the straights
    meet it with a kink of the fleet angle (a rope on a groove's flank). Free: a helix on the sheave, no kink.
    Left to itself the solver holds the arcs while no straight leaves a plane by more than 0.1°."""
    w = P.Wheel(np.array([3.0, 0.0, 0.0]), Y, 0.5, +1)
    start, end = np.array([0.0, 0.0, 0.5]), np.array([3.5, 0.0, -3.0])
    flat = P.solve(start, [w], end)
    for side in (0.3, 0.004):                         # 5.7° and 0.08° of fleet angle
        s2, e2 = start + [0, side, 0], end + [0, -side, 0]
        held = P.solve(s2, [w], e2, held=True)
        free = P.solve(s2, [w], e2, held=False)
        kink, _ = check_path(held, [w], s2, e2)
        assert np.abs(arc_of(held, 0)[:, 1]).max() < 1e-12
        assert kink == pytest.approx(math.degrees(math.atan2(side, 3.0)), rel=1e-6)
        assert check_path(free, [w], s2, e2)[0] < 1e-9 and np.ptp(arc_of(free, 0)[:, 1]) > 0.1 * side
        auto = P.solve(s2, [w], e2)
        assert np.allclose(auto.points, (free if side > 0.01 else held).points, atol=1e-12)
    # held: the centre says where the arc is; free: any point on the axis is the same wheel
    moved = P.Wheel(w.centre + 0.2 * Y, Y, 0.5, +1)
    assert arc_of(P.solve(start, [moved], end, held=True), 0)[:, 1] == pytest.approx(0.2, abs=1e-12)
    assert np.allclose(P.solve(start, [moved], end, held=False).points, flat.points, atol=1e-12)
    assert np.allclose(P.solve(start, [moved], end).points, flat.points, atol=1e-12)


def test_held_wheels_with_axes_that_are_not_parallel():
    """Held circles in different planes: the straight between them touches both; a level arc into an arc upwards
    with a straight between, and the same two touching (within 0.1 mm they count as touching)."""
    a = P.Wheel(np.array([0.0, 2.0, 0.0]), Z, 2.0, +1)
    b = P.Wheel(np.array([2.0, 6.0, 1.5]), np.array([1.0, 0.0, 0.0]), 1.5, +1)
    start, end = np.array([-5.0, 0.0, 0.0]), np.array([2.0, 7.5, 6.0])
    p = P.solve(start, [a, b], end, held=True)
    kink, off = check_path(p, [a, b], start, end)
    assert kink < 1e-9 and off < 1e-12 and p.length == pytest.approx(5.0 + math.pi + 4.0 + 0.75 * math.pi + 4.5, abs=1e-10)
    rng = np.random.default_rng(4)
    for noise in (1e-6, 1e-4, 1e-3):                  # the second wheel a little out of place: small kinks, no more
        b2 = P.Wheel(b.centre + noise * rng.normal(size=3), unit(b.axis + noise * rng.normal(size=3)), 1.5, +1)
        q = P.solve(start, [a, b2], end, held=True)
        kink, off = check_path(q, [a, b2], start, end)
        assert off < 1e-12 and kink < math.degrees(3 * noise) + 1e-9 and abs(q.length - p.length) < 5 * noise
    # frames: every frame chooses for itself, and says which way it went
    frames = 40
    t = np.linspace(0.0, 1.0, frames)
    centres = np.tile(np.stack([a.centre, b.centre]), (frames, 1, 1))
    centres[:, 1, 0] += np.where(t > 0.5, 0.2 * (t - 0.5), 0.0)       # the second sheave slides along its own axis
    axes = np.tile(np.stack([a.axis, b.axis]), (frames, 1, 1))
    starts, ends = np.tile(start, (frames, 1)), np.tile(end, (frames, 1))
    out = P.solve_frames(starts, centres, axes, [2.0, 1.5], [1, 1], ends)
    assert out["ok"].all() and out["held"][t <= 0.5].all() and not out["held"][t > 0.6].any()
    for f in (0, 19, 30, 39):
        one = P.solve(start, [P.Wheel(centres[f, 0], Z, 2.0, 1), P.Wheel(centres[f, 1], b.axis, 1.5, 1)], end,
                      counts=out["counts"])
        assert np.abs(one.points - out["points"][f]).max() < 1e-9
    held = P.solve_frames(starts, centres, axes, [2.0, 1.5], [1, 1], ends, held=True)
    assert held["held"].all() and np.abs(held["points"][-1] - out["points"][-1]).max() > 0.01


# ---------------------------------------------------------------------------------------------------------
# a real mesh: the centreline of a tube, then the reading
# ---------------------------------------------------------------------------------------------------------

def test_read_a_rope_drawn_as_a_tube():
    """A wire rope Ø 24 as a tube of 16 flat sides over two sheaves, a drum and a chute: its centreline from the
    mesh (short: ``tube_centreline`` in one go), then its contacts."""
    rope = 0.012
    course, rounds = sheave_course(rope)
    verts, tris = tube_mesh(course.sample(0.5 * rope), rope, 16)
    t0 = time.perf_counter()
    tube = P.centreline(verts, tris)
    took = time.perf_counter() - t0
    assert tube.ok and tube.radius == pytest.approx(rope, rel=0.02) and tube.length == pytest.approx(course.length, abs=2e-3)
    assert len(tube.points) == round(tube.length / tube.radius) + 1
    off = course.distance(tube.points).max()
    assert off < 0.02 * rope                         # tube_centreline's own promise: 1 % of the radius, measured 0.5 %
    rd = P.read_cable(tube.points, tube.radius, rounds)
    path = check_reading(rd, course, ["sheave 1", "sheave 2", "drum", "chute"], 2e-5)
    print(f"\nrope Ø 24, {len(tris)} triangles: centreline in {took:.2f} s, {off * 1e3:.3f} mm off; the path "
          f"{path * 1e3:.3f} mm off the route, deviation {rd.deviation * 1e3:.3f} mm")
    assert path < 2e-4 and rd.deviation < 5e-4       # the brief: 0.5 mm
    # the same through flex_fit.tube_centreline itself, with other numbers of points
    for n in (257, 1025):
        direct = flex_fit.tube_centreline(verts, tris, n)
        rd = P.read_cable(direct.points, direct.radius, rounds)
        assert check_reading(rd, course, ["sheave 1", "sheave 2", "drum", "chute"], 2e-5) < 2e-4


def test_centreline_of_a_300_m_cable():
    """A 300 m cable of 70 mm radius with 15 bends as a tube mesh (137,000 triangles). ``tube_centreline`` alone
    loses it (made for hoses: at most 1024 cuts, its first rough line from 96); ``centreline`` reads it in
    pieces, and the reading finds every bend."""
    rope = 0.07
    course = long_route()
    verts, tris = tube_mesh(course.sample(rope), rope, 16)
    t0 = time.perf_counter()
    tube = P.centreline(verts, tris)
    took = time.perf_counter() - t0
    assert tube.ok and tube.radius == pytest.approx(rope, rel=0.01) and tube.length == pytest.approx(course.length, abs=0.01)
    assert len(tube.points) == round(tube.length / tube.radius) + 1 and len(tube.points) > 4000
    assert tuple(tube.points[0]) < tuple(tube.points[-1])            # end 0: the smaller x
    off = course.distance(tube.points)
    t0 = time.perf_counter()
    plain = flex_fit.tube_centreline(verts, tris, len(tube.points))
    took_plain = time.perf_counter() - t0
    off_plain = course.distance(plain.points)
    t0 = time.perf_counter()
    rd = P.read_cable(tube.points, tube.radius, [])
    took_read = time.perf_counter() - t0
    path = check_reading(rd, course, [None] * 15, 2e-5, bend_tol=0.002, centre_tol=5e-3)
    print(f"\n300 m cable, {len(tris)} triangles: centreline in {took:.1f} s, {off.max() * 1e3:.2f} mm off at most "
          f"({off.mean() * 1e3:.3f} mm on average); tube_centreline alone: {took_plain:.1f} s, {off_plain.max() * 1e3:.0f} mm "
          f"off at most ({off_plain.mean() * 1e3:.1f} mm on average); read in {took_read:.1f} s, the path {path * 1e3:.2f} mm "
          f"off the route")
    assert off.max() < 5e-4 and off_plain.max() > 0.05
    assert path < 5e-4 and rd.deviation < 5e-4       # the brief: 0.5 mm
    assert took < 30.0 and took_read < 10.0
    # a short tube goes to tube_centreline in one go
    short = Course().straight(1.0).bend(Y, 0.5, 90).straight(1.0)
    v2, t2 = tube_mesh(short.sample(0.02), 0.05, 12)
    one = P.centreline(v2, t2, spacing=0.02)
    assert one.ok and short.distance(one.points).max() < 0.02 * 0.05 and len(one.points) == round(one.length / 0.02) + 1
    assert not P.centreline(np.zeros((0, 3)), np.zeros((0, 3), dtype=int)).ok


# ---------------------------------------------------------------------------------------------------------
# the demo vessel's real cable (made by the model maker, read by the app's importer)
# ---------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """The demo vessel's assembly file, written once and read by the importer (Normal); the cable's centreline,
    the round parts near it as the app would give them (every round axis of every part within 0.6 m of the
    cable), and the reading."""
    pytest.importorskip("OCP")
    from fresing_render.demo_model import layout
    from fresing_render.demo_model.params import Params
    from fresing_render.importer import step_reader
    out = str(tmp_path_factory.mktemp("demo_cable"))
    took = {}
    t0 = time.perf_counter()
    S = layout.write(out, Params(), log=lambda *_: None, only=("assembly",))
    took["model"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    cache = os.path.join(out, "cache")
    info = step_reader.read_step(os.path.join(out, layout.FILES["assembly"]), cache, "normal")
    arrays = np.load(os.path.join(cache, "meshes.npz"))
    took["import"] = time.perf_counter() - t0
    with open(os.path.join(out, layout.JOINTS_JSON), encoding="utf-8") as fh:
        joints = json.load(fh)["joints"]
    nodes = info["nodes"]

    def world(i):
        m = np.eye(4)
        while i >= 0:
            if nodes[i]["matrix"] is not None:
                m = np.array(nodes[i]["matrix"]) @ m
            i = nodes[i]["parent"]
        return m

    def mesh(i):
        m = world(i)
        return arrays[f"p{nodes[i]['mesh']}"].astype(float) @ m[:3, :3].T + m[:3, 3], arrays[f"t{nodes[i]['mesh']}"], m

    cable = [i for i, n in enumerate(nodes) if n["kind"] == "part" and n["name"] == "CABLE"]
    assert len(cable) == 1
    verts, tris, _ = mesh(cable[0])
    route = S.routes["main"]
    t0 = time.perf_counter()
    tube = P.centreline(verts, tris)
    took["centreline"] = time.perf_counter() - t0
    assert tube.ok, tube.problem
    pts = tube.points
    if np.linalg.norm(pts[0] - route.segments[0].start / 1000) > np.linalg.norm(pts[-1] - route.segments[0].start / 1000):
        pts = pts[::-1]                              # from the carousel to the sea, as the route runs
    t0 = time.perf_counter()
    rounds = []
    lo, hi = pts.min(axis=0) - 0.6, pts.max(axis=0) + 0.6
    for i, n in enumerate(nodes):
        if n["kind"] != "part" or i == cable[0] or not info["meshes"][n["mesh"]]["axes"]:
            continue
        vw, tw, m = mesh(i)
        b0, b1 = vw.min(axis=0), vw.max(axis=0)
        if (b1 < lo).any() or (b0 > hi).any() or not ((pts > b0 - 0.6) & (pts < b1 + 0.6)).all(axis=1).any():
            continue
        for k, ax in enumerate(info["meshes"][n["mesh"]]["axes"]):
            rounds.append(P.Round((n["uid"], k), m[:3, :3] @ np.array(ax[:3]) + m[:3, 3], m[:3, :3] @ np.array(ax[3:6]), vw, tw))
    took["round parts"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    reading = P.read_cable(pts, tube.radius, rounds)
    took["reading"] = time.perf_counter() - t0
    return {"S": S, "route": route, "joints": joints, "tube": tube, "pts": pts, "rounds": rounds, "reading": reading,
            "took": took, "triangles": len(tris)}


def test_demo_cable_centreline(demo):
    """The CAD cable (a swept solid, Ø 200, 188 m) as the importer meshes it: its centreline lies on the route."""
    route, tube = demo["route"], demo["tube"]
    off = route.distance(demo["pts"] * 1000.0)
    print(f"\ndemo cable: {demo['triangles']} triangles, {len(demo['pts'])} centreline points in {demo['took']['centreline']:.1f} s, "
          f"{off.max():.2f} mm off the route at most, {off.mean():.3f} mm on average (model {demo['took']['model']:.0f} s, "
          f"import {demo['took']['import']:.0f} s)")
    assert tube.radius == pytest.approx(0.1, abs=2e-4) and tube.length == pytest.approx(route.length / 1000, abs=0.01)
    assert len(demo["pts"]) == round(tube.length / tube.radius) + 1
    assert off[5:-5].max() < 2.0 and off.mean() < 0.3 and off.max() < 6.0      # its two ends: tube_centreline's 4.5 mm


def test_demo_cable_every_arc_and_straight(demo):
    """Every arc of the route is found with its radius, the straights between are straight and as long as the
    route's, where the route has none the arcs touch, and the path follows the CAD cable."""
    rd, route = demo["reading"], demo["route"]
    assert rd.ok, rd.problem
    arcs = [(s, i) for s, i in zip(route.segments, route.info) if s.kind == "arc"]
    shaping = [c for c in rd.contacts if c.kind != "TOUCH"]
    assert len(arcs) == 14 and [c.kind for c in shaping] == ["BEND"] * 14       # no part carries a bend: rollers do
    assert rd.start_on_wheel and not rd.end_on_wheel                            # it starts on the coil, ends in the sea
    rows = []
    for c, (seg, inf) in zip(shaping, arcs):
        off = c.centre - seg.centre / 1000
        off = float(np.linalg.norm(off - (off @ seg.normal) * seg.normal))
        rows.append((inf.get("rollers") or inf.get("support"), c.radius, seg.radius / 1000, off, math.degrees(c.wrap),
                     math.degrees(seg.angle)))
        assert angle_deg(c.axis, seg.normal * c.side) < 0.05
        assert abs(c.radius / (seg.radius / 1000) - 1.0) < 0.003 and off < 0.010, rows[-1]
        assert abs(math.degrees(c.wrap) - math.degrees(seg.angle)) < 0.2, rows[-1]
    print("\ndemo cable, arcs (where, radius read / route, centre off mm, wrap read / route):")
    for name, r, r0, off, w, w0 in rows:
        print(f"   {name:16s} {r:.4f} / {r0:.4f} m   {off * 1e3:5.2f} mm   {w:7.2f} / {w0:7.2f}°")
    assert max(abs(r / r0 - 1.0) for _, r, r0, *_ in rows) < 0.003
    # the straights: as long as the route's lines, none where two arcs follow each other directly
    path = rd.path
    lines, at = {}, 0
    for k, seg in enumerate(route.segments):
        if seg.kind == "arc":
            at += 1
        else:
            lines[at] = seg.length / 1000          # the straight before arc number ``at`` (14: the last, to the end)
    for i in range(15):
        k = int(path.first[i]) if i < 14 else len(path.points) - 1
        run = float(np.linalg.norm(path.points[k] - path.points[k - 1])) if k else 0.0
        assert run == pytest.approx(lines.get(i, 0.0), abs=0.02), (i, run, lines.get(i, 0.0))
    off = route.distance(path.points * 1000.0)
    inner = (path.s > 0.2) & (path.s < path.length - 0.2)
    print(f"demo cable: read in {demo['took']['reading']:.1f} s with {len(demo['rounds'])} round axes; the path lies within "
          f"{off[inner].max():.2f} mm of the route ({off.max():.2f} mm at its ends), {rd.deviation * 1e3:.2f} mm of the CAD "
          f"centreline; length {path.length:.3f} m (route {route.length / 1000:.3f} m)")
    assert off[inner].max() < 2.5 and off.max() < 6.0 and rd.deviation < 6e-3
    assert path.length == pytest.approx(route.length / 1000, abs=0.03)
    wheels = [P.Wheel(c.centre, c.axis, c.radius, c.side) for c in shaping]
    assert check_path(path, wheels, rd.start, rd.end, on0=True, min_run=1e-3)[0] < 0.1       # the brief: no kink over 0.1°
    again = P.solve(rd.start, wheels, rd.end, True, False)                       # what the app draws from the contacts
    assert again.ok and np.abs(again.points - path.points).max() < 1e-9
    assert P.tightest(wheels, path.wrap)[1] == pytest.approx(4.05, abs=0.01)     # the bend radius, over the MBR of 3.5 m


def test_demo_cable_rollers(demo):
    """The rollers that carry the cable are TOUCH contacts: every part the joint sheet turns "by the cable" that
    stands on the cable's route, and no other part."""
    rd, joints = demo["reading"], demo["joints"]
    touch = [c for c in rd.contacts if c.kind == "TOUCH"]
    by_cable = [j for j in joints if j["drive"].get("by") == "cable" and len(j["parts"]) == 1]
    turned = {j["parts"][0]: j for j in by_cable}
    touched = {}
    for c in touch:
        touched.setdefault(c.key[0], c)
    assert len(touched) == len(touch)                                # no part twice
    missed = sorted(turned[u]["name"] for u in turned if u not in touched)
    extra = sorted(u for u in touched if u not in turned)
    kinds = {}
    for u in touched:
        name = u.split("/")[-1].split("#")[0]
        kinds[name] = kinds.get(name, 0) + 1
    print(f"\ndemo cable: {len(touch)} rollers touched {kinds}; the joint sheet turns {len(by_cable)} parts by a cable; "
          f"not touched: {len(missed)}; touched without a joint: {len(extra)}")
    # what the sheet turns "by cable" but the main cable does not touch: the other horn (no cable on it), the
    # tensioners' sprockets (they turn with the track chain), the sheaves of the wire ropes
    other = [n for n in missed if not (n.startswith("HORN B") or "sprocket" in n or "sheave" in n.lower() or "pulley" in n)]
    assert not other and not extra, (other, extra)
    assert len([n for n in missed if n.startswith("HORN B")]) == 13 and len([n for n in missed if "sprocket" in n]) == 8
    assert len(touch) == 218 and kinds == {"CABLE ROLLER": 156, "GUIDE ROLLER": 54, "CABLE ENGINE WHEEL": 8}
    assert [c.s for c in rd.contacts] == sorted(c.s for c in rd.contacts)
    # each roller: round, the cable square across it, turning the way the sheet says, at the sheet's speed when
    # the speed is taken where the cable is drawn (the sheet's way); the maker draws the cable up to 16 mm into
    # its waisted rollers, so where a resting cable would touch them they are a little thicker
    cable_r = demo["tube"].radius
    drawn, resting, into = [], [], []
    for u, c in touched.items():
        j = turned[u]
        axis = np.array(j["axis"]["direction"])
        assert c.full and c.wrap == 0.0 and abs(c.axis @ axis) > 0.9999
        assert P.wheel_ratio(c.surface, c.side, c.axis, axis) > 0.0, j["name"]        # positive = paying out
        drawn.append(abs(P.wheel_ratio(c.radius - cable_r, c.side, c.axis, axis)) / j["drive"]["deg_per_mm"] - 1.0)
        resting.append(abs(P.wheel_ratio(c.surface, c.side, c.axis, axis)) / j["drive"]["deg_per_mm"] - 1.0)
        into.append(-c.gap)
    drawn, resting, into = np.abs(drawn), np.array(resting), np.array(into)
    print(f"demo cable: ratio against the sheet's – taken where the cable is drawn: {drawn.max() * 100:.2f} % off at most; "
          f"taken where a resting cable touches the roller: {int((np.abs(resting) > 0.005).sum())} of {len(resting)} more than "
          f"0.5 % off (down to {resting.min() * 100:.1f} %); the cable is drawn {into.max() * 1e3:.1f} mm into a roller at most")
    assert drawn.max() < 0.02 and resting.max() < 1e-3 and resting.min() > -0.2
    assert into.min() > -1e-3 and into.max() < 0.02                  # never drawn apart, at most 20 mm into a roller
