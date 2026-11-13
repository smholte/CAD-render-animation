"""Task 0078: independent tests of ``core/paths.py`` (cable paths), written from the brief by an agent that wrote
none of the code (subagent E).

Every expected value here comes from geometry worked out in this file (a tangent formula of its own, routes built by
walking straight runs and arcs, meshes revolved from an outline, tubes with facets as a CAD mesh has them) or from
the test model's maker (``tools/make_test_paths.py``: ``NUMBERS``, ``Route``) - never from the function under test,
and nothing is taken from the author's tests. Metres and radians unless a name says otherwise.

What the code does *not* do right today is in the task's report (the review), not here: this file holds what holds
today and should keep holding. Bounds marked "measured" are a little above what the web machine gave.
"""

import math
import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_paths as maker  # noqa: E402  (the test model's own numbers: an independent source)
from fresing_render.core import flex_fit  # noqa: E402
from fresing_render.core import paths as P  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])
MM = 1e-3
HELD = (None, True, False)


# =====================================================================================================================
# my own geometry
# =====================================================================================================================

def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def angle_deg(a, b) -> float:
    a, b = unit(a), unit(b)
    return math.degrees(math.atan2(float(np.linalg.norm(np.cross(a, b))), float(a @ b)))


def rot(axis, a):
    """The matrix that turns by ``a`` about ``axis`` (right hand)."""
    k = unit(axis)
    m = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(a) * m + (1.0 - math.cos(a)) * (m @ m)


def frame(axis):
    a = unit(axis)
    u = unit(np.cross(a, X if abs(a[0]) < 0.9 else Y))
    return u, np.cross(a, u), a


def radial(p, wheel):
    """From the wheel's axis square out to the point."""
    a = unit(wheel.axis)
    rel = np.asarray(p, dtype=float) - np.asarray(wheel.centre, dtype=float)
    return rel - (rel @ a) * a


def tangent2d(c1, r1, s1, c2, r2, s2):
    """The straight run from circle 1 to circle 2 in a plane, side +1 = going round counter-clockwise: (point on
    1, point on 2, direction). Going round c counter-clockwise the centre lies to the left of the direction t, so
    the point is c - s r n with n the left normal of t; the step between the two points is along t when
    d . n = s2 r2 - s1 r1."""
    d = np.asarray(c2, dtype=float) - np.asarray(c1, dtype=float)
    dist = math.hypot(d[0], d[1])
    phi = math.atan2(d[1], d[0]) + math.asin((s1 * r1 - s2 * r2) / dist)
    t = np.array([math.cos(phi), math.sin(phi)])
    n = np.array([-t[1], t[0]])
    return np.asarray(c1) - s1 * r1 * n, np.asarray(c2) - s2 * r2 * n, t


def point_tangent(q, c, r, s, coming: bool):
    """Where the straight from the point q meets the circle (``coming``), or the straight to q leaves it."""
    d = np.asarray(c, dtype=float) - np.asarray(q, dtype=float)
    dist = math.hypot(d[0], d[1])
    turn = math.asin(r / dist)
    phi = math.atan2(d[1], d[0]) + (-s * turn if coming else s * turn)
    t = np.array([math.cos(phi), math.sin(phi)]) * (1.0 if coming else -1.0)     # the cable's direction there
    return np.asarray(c) - s * r * np.array([-t[1], t[0]])


def chain2d(start, circles, end):
    """A cable in a plane from start over circles [(centre, radius, side)] to end: (tangent-in points, tangent-out
    points, wraps, length), or None when a straight has no tangent."""
    count = len(circles)
    p_in, p_out = [None] * count, [None] * count
    if math.hypot(*(circles[0][0] - start)) <= circles[0][1] or math.hypot(*(circles[-1][0] - end)) <= circles[-1][1]:
        return None
    p_in[0] = point_tangent(start, *circles[0], True)
    p_out[-1] = point_tangent(end, *circles[-1], False)
    for i in range(count - 1):
        (c1, r1, s1), (c2, r2, s2) = circles[i], circles[i + 1]
        if abs(s1 * r1 - s2 * r2) >= math.hypot(*(c2 - c1)):
            return None
        p_out[i], p_in[i + 1], _ = tangent2d(c1, r1, s1, c2, r2, s2)
    wraps = []
    length = math.hypot(*(p_in[0] - start)) + math.hypot(*(end - p_out[-1]))
    for i, (c, r, s) in enumerate(circles):
        a0 = math.atan2(p_in[i][1] - c[1], p_in[i][0] - c[0])
        a1 = math.atan2(p_out[i][1] - c[1], p_out[i][0] - c[0])
        wraps.append((s * (a1 - a0)) % (2.0 * math.pi))
        length += r * wraps[-1]
        if i:
            length += math.hypot(*(p_in[i] - p_out[i - 1]))
    return p_in, p_out, wraps, length


def measure(path, wheels, start, end, on0=False, on1=False) -> dict:
    """A solved path measured against the brief, with nothing of the solver's: the worst over all wheels of
    ``radius`` (arc points' distance from the axis - the radius), ``plane`` (how far arc points are from the plane
    through the wheel's centre), ``tangent`` (the straights' direction . the radius at the touching point: 0 when
    the straight touches the cylinder), ``kink`` (degrees between a straight and the arc where they meet),
    ``turn`` (the angle the arc points really go round - ``wrap``), ``length`` (my sum of straights and arcs -
    ``length``), and ``side`` / ``forward`` / ``layout`` True when the sides, the way round and the layout of
    ``points`` are as the brief says."""
    out = {"radius": 0.0, "plane": 0.0, "tangent": 0.0, "kink": 0.0, "turn": 0.0, "side": True, "forward": True,
           "layout": True}
    pts = path.points
    total = 0.0
    prev = None if on0 else np.asarray(start, dtype=float)
    at = 0 if on0 else 1
    for i, w in enumerate(wheels):
        a = unit(w.axis)
        side = 1.0 if w.side >= 0 else -1.0
        k0, n = int(path.first[i]), int(path.counts[i])
        out["layout"] &= k0 == at
        at += n
        arc = pts[k0:k0 + n]
        rad = np.array([radial(p, w) for p in arc])
        rho = np.linalg.norm(rad, axis=1)
        out["radius"] = max(out["radius"], float(np.abs(rho - w.radius).max()))
        h = (arc - np.asarray(w.centre, dtype=float)) @ a
        out["plane"] = max(out["plane"], float(np.abs(h).max()))
        u = rad[0] / rho[0]
        v = np.cross(a, u)
        theta = np.unwrap(np.arctan2(rad @ v, rad @ u))
        out["turn"] = max(out["turn"], abs(side * (theta[-1] - theta[0]) - float(path.wrap[i])))
        if path.wrap[i] > 1e-9:
            out["forward"] &= bool((side * np.diff(theta) > -1e-12).all())
        rise = float(h[-1] - h[0])

        def along(k):                                       # the arc's own direction at its point k (a helix)
            t = side * np.cross(a, rad[k] / rho[k]) * (w.radius * float(path.wrap[i])) + a * rise
            if np.linalg.norm(t) < 1e-15:
                t = side * np.cross(a, rad[k] / rho[k])
            return unit(t)

        for k, other in ((0, prev), (n - 1, pts[k0 + n] if k0 + n < len(pts) else None)):
            if other is None:
                continue
            d = (arc[0] - other) if k == 0 else (other - arc[-1])
            long = float(np.linalg.norm(d))
            if k == 0:
                total += long
            if long > 1e-6:
                d = d / long
                out["tangent"] = max(out["tangent"], abs(float(d @ (rad[k] / rho[k]))))
                out["kink"] = max(out["kink"], angle_deg(d, along(k)))
                out["side"] &= float(np.cross(rad[k], d) @ a) * side > 0.0
        total += math.hypot(w.radius * float(path.wrap[i]), rise)
        prev = arc[-1]
    if not (on1 and wheels):
        total += float(np.linalg.norm(np.asarray(end, dtype=float) - (prev if prev is not None else start)))
        at += 1
    out["layout"] &= at == len(pts) and len(path.s) == len(pts)
    out["length"] = abs(total - path.length)
    return out


def fine(path) -> None:
    assert path.ok, path.problem
    assert path.problem == "" and path.bad == -1
    assert np.isfinite(path.points).all() and np.isfinite(path.s).all() and np.isfinite(path.wrap).all()
    assert path.s[0] == 0.0 and (np.diff(path.s) >= -1e-12).all() and path.length == pytest.approx(path.s[-1], abs=1e-12)
    assert (path.wrap >= 0.0).all()


def refused(path, number=None, bad=None) -> None:
    """A plain refusal: a sentence, no shape, nothing that is not a number."""
    assert not path.ok
    assert isinstance(path.problem, str) and len(path.problem) > 15 and path.problem.strip().endswith(".")
    assert path.points.shape == (0, 3) and len(path.s) == 0 and path.length == 0.0
    assert np.isfinite(path.wrap).all()
    if number is not None:
        assert f"contact {number}" in path.problem.lower(), path.problem
    if bad is not None:
        assert path.bad == bad


class Course:
    """A route of straight runs and arcs in space, made by walking it: where a cable drawn in CAD really is."""

    def __init__(self, start, heading):
        self.p, self.t = np.asarray(start, dtype=float), unit(heading)
        self.start = self.p.copy()
        self.segs = []
        self.length = 0.0

    def line(self, long):
        self.segs.append(dict(kind="line", s0=self.length, length=long, p0=self.p.copy(), t0=self.t.copy()))
        self.p = self.p + long * self.t
        self.length += long
        return self

    def arc(self, n, r, deg, name=None):
        """Turn ``deg`` about the direction n (right hand; made square to the heading) with bend radius r."""
        n = np.asarray(n, dtype=float)
        n = unit(n - (n @ self.t) * self.t)
        turn = math.radians(deg)
        c = self.p + r * np.cross(n, self.t)
        self.segs.append(dict(kind="arc", s0=self.length, length=r * turn, p0=self.p.copy(), t0=self.t.copy(), c=c, n=n,
                              r=r, angle=turn, name=name))
        m = rot(n, turn)
        self.p, self.t = c + m @ (self.p - c), m @ self.t
        self.length += r * turn
        return self

    def at(self, s):
        for seg in self.segs:
            if s <= seg["s0"] + seg["length"] + 1e-12 or seg is self.segs[-1]:
                x = s - seg["s0"]
                if seg["kind"] == "line":
                    return seg["p0"] + x * seg["t0"], seg["t0"]
                m = rot(seg["n"], x / seg["r"])
                return seg["c"] + m @ (seg["p0"] - seg["c"]), m @ seg["t0"]

    def points(self, step):
        return np.array([self.at(s)[0] for s in np.linspace(0.0, self.length, max(int(round(self.length / step)), 1) + 1)])

    def arcs(self):
        return [s for s in self.segs if s["kind"] == "arc"]

    def wheels(self):
        return [P.Wheel(a["c"], a["n"], a["r"], 1) for a in self.arcs()]

    def off(self, pts):
        """How far points are from the route (exact: every straight and arc for itself)."""
        pts = np.asarray(pts, dtype=float)
        best = np.full(len(pts), np.inf)
        for seg in self.segs:
            if seg["kind"] == "line":
                f = np.clip((pts - seg["p0"]) @ seg["t0"], 0.0, seg["length"])
                d = np.linalg.norm(seg["p0"] + f[:, None] * seg["t0"] - pts, axis=1)
            else:
                rel = pts - seg["c"]
                u = unit(seg["p0"] - seg["c"])
                v = np.cross(seg["n"], u)
                th = np.mod(np.arctan2(rel @ v, rel @ u), 2.0 * math.pi)
                th = np.where(th > seg["angle"], np.where(th - seg["angle"] < 2.0 * math.pi - th, seg["angle"], 0.0), th)
                on = seg["c"] + seg["r"] * (np.cos(th)[:, None] * u + np.sin(th)[:, None] * v)
                d = np.linalg.norm(on - pts, axis=1)
            best = np.minimum(best, d)
        return best

    def tube(self, radius, sides=24, chord=1e-4):
        """A closed tube round the route with facets as a CAD mesher makes them: rings only at the ends of each
        straight (long facets), arcs cut so that no facet is more than ``chord`` from the true surface."""
        stations = [0.0]
        for seg in self.segs:
            k = 1
            if seg["kind"] == "arc":
                step = min(2.0 * math.acos(max(1.0 - chord / seg["r"], -1.0)), math.radians(10.0))
                k = max(int(math.ceil(seg["angle"] / step)), 1)
            stations += [seg["s0"] + seg["length"] * i / k for i in range(1, k + 1)]
        p0, t0 = self.at(0.0)
        u = unit(np.cross(t0, X if abs(t0[0]) < 0.9 else Y))
        verts, was = [], t0
        for s in stations:
            p, t = self.at(s)
            ax = np.cross(was, t)
            sin = float(np.linalg.norm(ax))
            if sin > 1e-12:
                u = rot(ax / sin, math.atan2(sin, float(was @ t))) @ u
            u = unit(u - (u @ t) * t)
            v, was = np.cross(t, u), t
            for i in range(sides):
                a = 2.0 * math.pi * i / sides
                verts.append(p + radius * (math.cos(a) * u + math.sin(a) * v))
        tris = []
        for k in range(len(stations) - 1):
            for i in range(sides):
                a, b = k * sides + i, k * sides + (i + 1) % sides
                tris += [(a, b, a + sides), (b, b + sides, a + sides)]
        n0, last = len(verts), (len(stations) - 1) * sides
        verts += [self.at(0.0)[0], self.at(self.length)[0]]
        for i in range(sides):
            tris += [(n0, (i + 1) % sides, i), (n0 + 1, last + i, last + (i + 1) % sides)]
        return np.array(verts), np.array(tris, dtype=np.int64)


def revolve(profile, sides=48, centre=(0, 0, 0), axis=Z, sweep=2.0 * math.pi, rng=None):
    """The surface an outline [(place along the axis, radius)] makes when it is turned about the axis: corners
    and triangles. Less than a whole turn: a sector with open ends. ``rng``: the quads are cut either way."""
    prof = np.asarray(profile, dtype=float)
    whole = sweep >= 2.0 * math.pi - 1e-9
    n = sides if whole else sides + 1
    theta = np.linspace(0.0, sweep, sides + 1)[:n]
    u, v, a = frame(axis)
    c = np.asarray(centre, dtype=float)
    verts = np.array([c + z * a + r * (math.cos(t) * u + math.sin(t) * v) for z, r in prof for t in theta])
    tris = []
    for j in range(len(prof) - 1):
        for i in range(sides):
            i2 = (i + 1) % n if whole else i + 1
            p00, p01, p10, p11 = j * n + i, j * n + i2, (j + 1) * n + i, (j + 1) * n + i2
            if rng is not None and rng.random() < 0.5:
                tris += [(p00, p01, p11), (p00, p11, p10)]
            else:
                tris += [(p00, p01, p10), (p01, p11, p10)]
    return verts, np.array(tris, dtype=np.int64)


def groove_outline(bottom, groove_r, flange, width, steps=24, z0=0.0, half_deg=70.0):
    """A sheave's rim: a round groove (radius ``groove_r``, its bottom at radius ``bottom``) reaching half_deg up
    either side, straight flanks on from there up to radius ``flange``, flat out to half ``width``."""
    h = math.radians(half_deg)
    arc = [(z0 + groove_r * math.sin(t), bottom + groove_r - groove_r * math.cos(t)) for t in np.linspace(-h, h, steps + 1)]
    tip = arc[-1][0] - z0 + (flange - arc[-1][1]) / math.tan(h)
    edge = max(0.5 * width, tip + 1e-4)
    return ([(z0 - edge, 0.6 * bottom), (z0 - edge, flange), (z0 - tip, flange)] + arc
            + [(z0 + tip, flange), (z0 + edge, flange), (z0 + edge, 0.6 * bottom)])


def roller_outline(radius, long):
    return [(-0.5 * long, 0.3 * radius), (-0.5 * long, radius), (0.5 * long, radius), (0.5 * long, 0.3 * radius)]


def sheave_for(arc, rope, key, flip=False, sink=0.0, shift=0.0, rng=None, sides=48, steps=24, full=None):
    """A grooved sheave the route's arc lies in: its axis the arc's (or the other way round), the groove's bottom
    at arc radius - rope (+ ``sink``: the cable is drawn that deep into it), ``shift`` along the axis."""
    n = arc["n"] * (-1.0 if flip else 1.0)
    bottom = arc["r"] - rope + sink
    centre = arc["c"] + shift * n
    v, t = revolve(groove_outline(bottom, 1.08 * rope, bottom + 2.3 * rope, 5.0 * rope, steps), sides, centre, n, rng=rng)
    return P.Round(key, centre + 0.37 * n, n, v, t, full)       # (any point on the axis)


def roller_at(centre, axis, key, radius=0.06, long=0.4, sides=24, rng=None):
    v, t = revolve(roller_outline(radius, long), sides, centre, axis, rng=rng)
    return P.Round(key, np.asarray(centre, dtype=float) + 0.11 * unit(axis), axis, v, t)


def centreline_of(course, rope, **kw):
    """The centreline read from a faceted tube round the route, a point every cable radius. Up to 200 radii long
    with ``paths.centreline`` (which then reads the tube in one go); a longer one with ``flex_fit.tube_centreline``
    in one go: ``paths.centreline`` reads those in pieces and today loses part of a cable that turns more than a
    quarter turn after a seam between two pieces (in the review)."""
    v, t = course.tube(rope, **kw)
    if course.length <= 200.0 * rope:
        tube = P.centreline(v, t)
    else:
        tube = flex_fit.tube_centreline(v, t, int(round(course.length / rope)) + 1)
    assert tube.ok, tube.problem
    return tube


def read(course, rope, rounds, **kw):
    tube = centreline_of(course, rope)
    return P.read_cable(tube.points, tube.radius, rounds, **kw), tube


def kinds(reading):
    return [(c.kind, c.key) for c in reading.contacts]


def deg(x):
    return math.degrees(float(x))


# =====================================================================================================================
# solve: a tight string over wheels
# =====================================================================================================================

@pytest.mark.parametrize("s1", [1, -1])
@pytest.mark.parametrize("s2", [1, -1])
def test_two_wheels_every_combination_of_sides(s1, s2):
    """Open and crossed belts, radii from 5 mm to 10 m, the plane anywhere in space up to 200 m from the origin:
    the straight between the wheels is my own tangent, in every ``held`` mode."""
    rng = np.random.default_rng(100 + 3 * s1 + s2)
    for _ in range(40):
        r1, r2 = (float(np.clip(10 ** rng.uniform(-2.3, 1.0), 0.005, 10.0)) for _ in range(2))
        c1 = rng.uniform(-2, 2, 2)
        c2 = c1 + unit(rng.normal(size=2)) * (r1 + r2 + 10 ** rng.uniform(-2, 0.7))
        p1, p2, t = tangent2d(c1, r1, s1, c2, r2, s2)
        # a start on the tangent of circle 1 some way before p1, an end on a tangent of circle 2 after p2
        a0 = math.atan2(p1[1] - c1[1], p1[0] - c1[0]) - s1 * math.radians(rng.uniform(5, 170))
        start = c1 + r1 * np.array([math.cos(a0), math.sin(a0)]) - s1 * np.array([-math.sin(a0), math.cos(a0)]) * rng.uniform(0.1, 3)
        a1 = math.atan2(p2[1] - c2[1], p2[0] - c2[0]) + s2 * math.radians(rng.uniform(5, 170))
        end = c2 + r2 * np.array([math.cos(a1), math.sin(a1)]) + s2 * np.array([-math.sin(a1), math.cos(a1)]) * rng.uniform(0.1, 3)
        turn, move = rot(rng.normal(size=3), rng.uniform(0, math.pi)), rng.uniform(-200, 200, 3)

        def space(p):
            return turn @ np.array([p[0], p[1], 0.0]) + move

        wheels = [P.Wheel(space(c1), turn @ Z, r1, s1), P.Wheel(space(c2), turn @ Z, r2, s2)]
        for held in HELD:
            path = P.solve(space(start), wheels, space(end), held=held)
            fine(path)
            out = path.points[path.first[0] + path.counts[0] - 1]
            into = path.points[path.first[1]]
            assert np.linalg.norm(out - space(p1)) < 1e-9 and np.linalg.norm(into - space(p2)) < 1e-9
            m = measure(path, wheels, space(start), space(end))
            assert m["side"] and m["forward"] and m["layout"]
            assert m["radius"] < 1e-9 and m["tangent"] < 1e-9 and m["kink"] < 1e-5 and m["length"] < 1e-9


def test_chains_of_1_to_8_wheels_in_a_plane_against_my_own():
    """Random chains (wraps from next to nothing to nearly a whole turn, axes given either way round, anywhere in
    space): what my own chain says can be drawn is drawn exactly so; what goes more than 350° round is refused."""
    rng = np.random.default_rng(5)
    drawn = turned_down = 0
    for _ in range(700):
        count = int(rng.integers(1, 9))
        scale = 10 ** rng.uniform(-1.5, 1.2)
        circles, x = [], 0.0
        for _i in range(count):
            r = float(np.clip(scale * 10 ** rng.uniform(-0.8, 0.5), 0.005, 10.0))
            x += r + (circles[-1][1] if circles else 0.0) + scale * rng.uniform(0.05, 4)
            circles.append((np.array([x, scale * rng.uniform(-3, 3)]), r, int(rng.choice([1, -1]))))
        start = np.array([-scale * rng.uniform(1, 5) - circles[0][1], scale * rng.uniform(-4, 4)])
        end = np.array([x + circles[-1][1] + scale * rng.uniform(1, 5), scale * rng.uniform(-4, 4)])
        ref = chain2d(start, circles, end)
        turn, move = rot(rng.normal(size=3), rng.uniform(0, math.pi)), rng.uniform(-200, 200, 3)

        def space(p):
            return turn @ np.array([p[0], p[1], 0.0]) + move

        flips = [int(rng.choice([1, -1])) for _c in circles]            # the axis the other way: the other side
        wheels = [P.Wheel(space(c), turn @ Z * f, r, s * f) for (c, r, s), f in zip(circles, flips)]
        can = ref is not None and all(math.radians(0.01) < w < math.radians(349.5) for w in ref[2])
        cannot = ref is None or any(w > math.radians(350.5) for w in ref[2])
        for held in HELD:
            path = P.solve(space(start), wheels, space(end), held=held)
            if cannot:
                refused(path)
                turned_down += 1
            if not can:
                continue
            fine(path)
            drawn += 1
            assert np.abs(path.wrap - np.array(ref[2])).max() < 1e-9
            assert abs(path.length - ref[3]) < 1e-9 * scale + 1e-10
            for i in range(count):
                assert np.linalg.norm(path.points[path.first[i]] - space(ref[0][i])) < 1e-8 * scale + 1e-10
                assert np.linalg.norm(path.points[path.first[i] + path.counts[i] - 1] - space(ref[1][i])) < 1e-8 * scale + 1e-10
            m = measure(path, wheels, space(start), space(end))
            assert m["side"] and m["forward"] and m["layout"]
            assert m["radius"] < 1e-9 * scale + 1e-11 and m["tangent"] < 1e-9 and m["kink"] < 1e-4
            assert m["turn"] < 1e-9 and m["length"] < 1e-9 * scale + 1e-10
    assert drawn > 1500 and turned_down > 100


def walked(rng, count, wraps=(5.0, 300.0), runs=(0.3, 5.0), far=200.0):
    co = Course(rng.uniform(-far, far, 3), rng.normal(size=3))
    co.line(rng.uniform(*runs))
    for _ in range(count):
        co.arc(np.cross(co.t, rng.normal(size=3)), 10 ** rng.uniform(-1, 0.5), float(rng.uniform(*wraps)))
        co.line(rng.uniform(*runs))
    return co


@pytest.mark.parametrize("held", HELD)
def test_wheels_whose_axes_point_anywhere_give_the_walked_route(held):
    """A route walked through space, every bend about another axis (no fleet angle: each straight lies in both
    its bends' planes), 200 m from the origin: the solver finds exactly that route again, in every mode."""
    rng = np.random.default_rng(18)
    for _ in range(120):
        co = walked(rng, int(rng.integers(1, 7)))
        wheels = co.wheels()
        path = P.solve(co.start, wheels, co.p, held=held)
        fine(path)
        for i, a in enumerate(co.arcs()):
            assert np.linalg.norm(path.points[path.first[i]] - a["p0"]) < 1e-7
            assert abs(path.wrap[i] - a["angle"]) < 1e-8
        assert abs(path.length - co.length) < 1e-7
        m = measure(path, wheels, co.start, co.p)
        assert m["side"] and m["forward"] and m["layout"] and m["kink"] < 1e-4 and m["tangent"] < 1e-8


def askew(rng, skew_deg):
    """Two wheels a cable goes over and under, the second's axis turned by ``skew_deg`` about a random direction,
    start and end out of the first wheel's plane."""
    r1, r2 = rng.uniform(0.05, 1.0, 2)
    c2 = np.array([r1 + r2 + rng.uniform(0.5, 4), rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)])
    a2 = rot(rng.normal(size=3), math.radians(skew_deg)) @ Y
    wheels = [P.Wheel(np.zeros(3), Y, float(r1), 1), P.Wheel(c2, a2, float(r2), -1)]
    start = np.array([-rng.uniform(1.5, 4), rng.uniform(-0.2, 0.2), -rng.uniform(0.5, 2)])
    end = c2 + np.array([rng.uniform(1.5, 4), rng.uniform(-0.2, 0.2), rng.uniform(0.5, 2)])
    return wheels, start, end


def line_to_axis(p, d, wheel) -> float:
    n = np.cross(d, unit(wheel.axis))
    return abs(float((p - wheel.centre) @ n)) / float(np.linalg.norm(n))


def test_free_is_a_tight_string_on_cylinders_with_axes_askew():
    """``held=False``, axes 1° to 30° askew: every straight touches both cylinders (my own line-to-axis distance
    is the radius) and meets its arcs without a kink - the arcs are helices, so they leave their wheels' planes."""
    rng = np.random.default_rng(2)
    slid = 0.0
    for _ in range(150):
        wheels, start, end = askew(rng, rng.uniform(1, 30))
        path = P.solve(start, wheels, end, held=False)
        fine(path)
        m = measure(path, wheels, start, end)
        assert m["side"] and m["forward"] and m["layout"]
        assert m["radius"] < 1e-9 and m["tangent"] < 1e-9 and m["turn"] < 1e-9 and m["length"] < 1e-9
        assert m["kink"] < 1e-4                                         # the brief: under 0.1°
        out, into = path.points[path.first[0] + path.counts[0] - 1], path.points[path.first[1]]
        d = unit(into - out)
        for w in wheels:
            assert abs(line_to_axis(out, d, w) - w.radius) < 1e-9
        slid = max(slid, m["plane"])
    assert slid > 0.01                                                  # (it really is another shape than held)


def test_held_keeps_arcs_in_their_planes_and_kinks_by_the_fleet_angle():
    """``held=True``, axes askew: every arc lies in the plane through its wheel's centre (the groove) and each
    straight still touches both circles; where it leaves a wheel's plane it meets the arc with a kink of exactly
    that fleet angle - so with a fleet angle over 0.1° the brief's "no kink over 0.1°" cannot hold in this mode
    (it holds in the other, where the cable leaves the groove instead)."""
    rng = np.random.default_rng(3)
    widest = 0.0
    for _ in range(150):
        wheels, start, end = askew(rng, rng.uniform(1, 30))
        path = P.solve(start, wheels, end, held=True)
        fine(path)
        m = measure(path, wheels, start, end)
        assert m["side"] and m["forward"] and m["layout"]
        assert m["plane"] < 1e-9 and m["radius"] < 1e-9 and m["tangent"] < 1e-9 and m["length"] < 1e-9
        # the kink at each end of each straight is the angle between the straight and that wheel's plane
        ends = [start] + [path.points[path.first[i] + k] for i in range(2) for k in (0, path.counts[i] - 1)] + [end]
        fleet = 0.0
        for k, i in ((0, 0), (2, 0), (2, 1), (4, 1)):
            d = unit(ends[k + 1] - ends[k])
            fleet = max(fleet, math.degrees(math.asin(abs(float(d @ unit(wheels[i].axis))))))
        assert m["kink"] == pytest.approx(fleet, abs=1e-6)
        widest = max(widest, fleet)
    assert widest > 5.0


def test_by_itself_switches_from_held_to_free_at_a_tenth_of_a_degree():
    """``held=None``: two sheaves 10 m apart, the second slid along its axis (the end rides with it). Up to a
    fleet angle of 0.1° the frames are the held ones, beyond it the free ones. At the switch the cable jumps: the
    arcs leave their grooves by millimetres from one frame to the next (measured 2.83 mm here) - a cable whose
    contacts move must be solved with ``held=True``."""
    frames = 401
    slide = np.linspace(0.0, 0.040, frames)
    centres = np.zeros((frames, 2, 3))
    centres[:, 0] = [0.0, 0.0, 2.0]
    centres[:, 1] = [10.0, 0.0, 2.0]
    centres[:, 1, 1] = slide
    axes = np.tile(Y, (frames, 2, 1))
    starts = np.tile([-0.25, 0.0, 0.0], (frames, 1))
    ends = np.tile([10.25, 0.0, 0.0], (frames, 1))
    ends[:, 1] = slide
    got = {held: P.solve_frames(starts, centres, axes, [0.25, 0.25], [1, 1], ends, counts=[24, 24], held=held)
           for held in HELD}
    for out in got.values():
        assert out["ok"].all() and np.isfinite(out["points"]).all()
    assert got[True]["held"].all() and not got[False]["held"].any()
    first_free = int(np.flatnonzero(~got[None]["held"])[0])
    assert got[None]["held"][:first_free].all() and not got[None]["held"][first_free:].any()
    assert math.degrees(math.atan(slide[first_free] / 10.0)) == pytest.approx(0.1, abs=0.002)
    assert np.allclose(got[None]["points"][:first_free], got[True]["points"][:first_free], atol=1e-12)
    assert np.allclose(got[None]["points"][first_free:], got[False]["points"][first_free:], atol=1e-9)
    # held: the arcs stay in the grooves and nothing jumps (the sheave moves 0.1 mm a frame)
    assert np.abs(got[True]["points"][:, 25:49, 1] - slide[:, None]).max() < 1e-12
    assert np.linalg.norm(np.diff(got[True]["points"], axis=0), axis=2).max() < 0.11 * MM
    # by itself: the jump at the switch
    jump = np.linalg.norm(got[None]["points"][first_free] - got[None]["points"][first_free - 1], axis=1).max()
    assert 1.0 * MM < jump < 4.0 * MM


@pytest.mark.parametrize("wrap_deg", [0.01, 0.5, 90.0, 179.99, 180.0, 180.01, 270.0, 349.9])
def test_one_wheel_any_wrap_up_to_350_degrees(wrap_deg):
    """A wheel barely touched, half round, nearly all the way round: start and end are put on the two tangents
    of a known arc, on both sides and with the axis either way."""
    r, lead, tail = 0.4, 1.7, 0.9
    for side in (1, -1):
        for flip in (1, -1):
            centre = np.array([120.0, -80.0, 30.0])
            axis = unit([0.2, 1.0, -0.3]) * flip
            u, v, a = frame(axis)
            a0 = 0.7
            a1 = a0 + side * math.radians(wrap_deg)
            p_in = centre + r * (math.cos(a0) * u + math.sin(a0) * v)
            p_out = centre + r * (math.cos(a1) * u + math.sin(a1) * v)
            t_in = side * (-math.sin(a0) * u + math.cos(a0) * v)
            t_out = side * (-math.sin(a1) * u + math.cos(a1) * v)
            start, end = p_in - lead * t_in, p_out + tail * t_out
            wheel = P.Wheel(centre, axis, r, side)
            for held in HELD:
                path = P.solve(start, [wheel], end, held=held)
                fine(path)
                assert deg(path.wrap[0]) == pytest.approx(wrap_deg, abs=1e-7)
                assert np.linalg.norm(path.points[1] - p_in) < 1e-9 and np.linalg.norm(path.points[-2] - p_out) < 1e-9
                assert path.length == pytest.approx(lead + tail + r * math.radians(wrap_deg), abs=1e-9)
                assert path.counts[0] == max(2, math.ceil(wrap_deg / 4.0 - 1e-9) + 1)          # a point every 4°
                m = measure(path, [wheel], start, end)
                assert m["side"] and m["forward"] and m["layout"] and m["kink"] < 1e-5 and m["turn"] < 1e-9


def test_more_than_350_degrees_round_a_wheel_is_refused():
    r = 0.4
    for wrap_deg in (350.5, 355.0, 359.0):
        a1 = math.radians(wrap_deg)
        start = np.array([r, 0.0, 0.0]) - 1.5 * np.array([0.0, 0.0, 1.0])
        end = r * np.array([math.cos(a1), 0.0, math.sin(a1)]) + 0.3 * np.array([-math.sin(a1), 0.0, math.cos(a1)])
        for held in HELD:                                   # about -Y the angle from +X to +Z counts up
            path = P.solve(start, [P.Wheel(np.zeros(3), -Y, r, 1)], end, held=held)
            refused(path, number=1, bad=0)
            assert "350" in path.problem


@pytest.mark.parametrize("luff", [-15.0, -7.0, 0.0, 9.0, 15.0])
def test_the_test_models_rope_at_every_luff_is_the_makers_route(luff):
    """The winch model's rope, laid by its maker's own maths (``Route``: an independent source), with the A-frame
    luffed: it starts on the drum and ends on the chute's circle (both ends on a wheel)."""
    n = maker.numbers_at(luff)
    order = ["WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "CHUTE"]
    wheels = [P.Wheel(np.array(n["contacts"][k]["axis_point"]) * MM, np.array(n["contacts"][k]["axis_direction"]),
                      n["contacts"][k]["seat_radius"] * MM, n["contacts"][k]["side"]) for k in order]
    start = np.array(n["contacts"]["WINCH DRUM"]["tangent_in"]) * MM
    end = np.array(n["contacts"]["CHUTE"]["tangent_out"]) * MM
    for held in HELD:
        path = P.solve(start, wheels, end, start_on_wheel=True, end_on_wheel=True, held=held)
        fine(path)
        assert path.first[0] == 0 and int(path.counts.sum()) == len(path.points)        # no extra end points
        assert np.linalg.norm(path.points[0] - start) < 1e-6 and np.linalg.norm(path.points[-1] - end) < 1e-6
        for i, k in enumerate(order):
            c = n["contacts"][k]
            assert deg(path.wrap[i]) == pytest.approx(c["wrap"], abs=2e-4)               # (the maker rounds to 4 places)
            assert np.linalg.norm(path.points[path.first[i]] - np.array(c["tangent_in"]) * MM) < 2e-6
            assert np.linalg.norm(path.points[path.first[i] + path.counts[i] - 1] - np.array(c["tangent_out"]) * MM) < 2e-6
        assert path.length == pytest.approx((n["rope"]["length"] - n["rope"]["free"]) * MM, abs=2e-6)
        m = measure(path, wheels, start, end, True, True)
        assert m["side"] and m["forward"] and m["layout"] and m["kink"] < 1e-5 and m["plane"] < 1e-12
        assert m["radius"] < 1e-12                                                       # the brief: within 0.5 mm


def test_an_end_on_a_wheel_is_put_on_its_circle():
    """``start_on_wheel``: a point beside the circle (further out, and off the wheel's plane) is put on the circle
    where it is seen from the axis; the arc starts there."""
    wheel = P.Wheel(np.array([1.0, 2.0, 3.0]), Z, 0.5, 1)
    start = np.array([1.0 + 0.9, 2.0, 3.0])                     # 0.4 outside the circle, at angle 0
    end = np.array([1.0 - 0.5, 2.0 - 3.0, 3.0])                 # leaves at angle 180° going -Y
    for held in (None, True):
        path = P.solve(start, [wheel], end, start_on_wheel=True, held=held)
        fine(path)
        assert np.linalg.norm(path.points[0] - np.array([1.5, 2.0, 3.0])) < 1e-12
        assert deg(path.wrap[0]) == pytest.approx(180.0, abs=1e-9)
        assert path.length == pytest.approx(0.5 * math.pi + 3.0, abs=1e-12)
        assert len(path.points) == path.counts[0] + 1 and path.first[0] == 0
    both = P.solve(start, [wheel], np.array([1.0, 2.9, 3.0]), start_on_wheel=True, end_on_wheel=True)
    fine(both)
    assert deg(both.wrap[0]) == pytest.approx(90.0, abs=1e-9) and len(both.points) == both.counts[0]
    assert np.linalg.norm(both.points[-1] - np.array([1.0, 2.5, 3.0])) < 1e-12


def test_counts_are_kept_whatever_the_wrap_and_s_is_the_true_length():
    """The same number of points whether the wrap is nothing or wide; ``s`` counts the arc's true length (the
    chords between its points are shorter)."""
    r = 0.3
    for top in (0.0, 0.001, 0.2, 1.5):                          # how far the wheel pushes the cable up
        wheel = P.Wheel(np.array([0.0, 0.0, top - r]), Y, r, 1)
        start, end = np.array([-2.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0])
        for counts in ([2], [7], [40]):
            path = P.solve(start, [wheel], end, counts=counts)
            fine(path)
            assert list(path.counts) == counts and len(path.points) == counts[0] + 2 and path.first[0] == 1
            # my own: the tangent from a point 2 m away; the wrap is twice the angle the straight rises by
            lean = math.atan2(top - r, 2.0) + math.asin(r / math.hypot(2.0, top - r))
            assert path.wrap[0] == pytest.approx(2.0 * lean, abs=1e-9)
            run = math.sqrt(4.0 + (top - r) ** 2 - r * r)
            assert path.length == pytest.approx(2.0 * run + r * 2.0 * lean, abs=1e-9)
            chords = float(np.linalg.norm(np.diff(path.points, axis=0), axis=1).sum())
            pieces = counts[0] - 1                                  # my own: the arc as that many equal chords
            short = r * 2.0 * lean - pieces * 2.0 * r * math.sin(lean / pieces)
            assert path.length - chords == pytest.approx(short, abs=1e-12) and chords <= path.length + 1e-12
            arc_s = path.s[1:1 + counts[0]]
            assert np.allclose(np.diff(arc_s), r * path.wrap[0] / (counts[0] - 1), atol=1e-12)


def test_a_wheel_the_cable_lifts_off_is_no_broken_shape():
    """A sheave sinks away under a straight cable. While it still pushes the cable up, the wrap shrinks smoothly
    to nothing. Just below the line there is nothing to wrap: the answer is either a straight cable that does
    not touch it, or a plain refusal about that contact. (Further below - from where the cable would have to
    bend back by more than 10° - the solver today draws a loop nearly all the way round the wheel: in the
    review, not here.)"""
    start, end = np.array([-2.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0])
    r = 0.25
    last = None
    for top in np.linspace(0.3, 0.0, 61):
        path = P.solve(start, [P.Wheel(np.array([0.0, 0.0, top - r]), Y, r, 1)], end, counts=[21], held=True)
        fine(path)
        assert last is None or path.wrap[0] < last + 1e-12
        last = float(path.wrap[0])
        assert path.points[:, 2].max() == pytest.approx(top, abs=1e-9)
    assert last == pytest.approx(0.0, abs=1e-9)
    for top in (-0.001, -0.02, -0.05):
        for held in HELD:
            path = P.solve(start, [P.Wheel(np.array([0.0, 0.0, top - r]), Y, r, 1)], end, counts=[20], held=held)
            if path.ok:
                assert path.wrap[0] == pytest.approx(0.0, abs=1e-9) and np.abs(path.points[:, 2]).max() < 1e-9
            else:
                refused(path, number=1, bad=0)


def frames_of(wheel_frames, radii, sides, start, end, **kw):
    count = len(wheel_frames)
    centres = np.array([[c for c, _a in f] for f in wheel_frames])
    axes = np.array([[a for _c, a in f] for f in wheel_frames])
    return P.solve_frames(np.tile(start, (count, 1)), centres, axes, radii, sides, np.tile(end, (count, 1)), **kw), centres, axes


def test_a_luffing_frame_moves_the_rope_smoothly():
    """500 small steps of the test model's luff (-15° … +15°): no point of the rope moves further in a step than
    the sheaves do (times 1.5: an arc's end slides a little along its sheave too); measured 1.16 times."""
    count = 500
    frames = []
    for luff in np.linspace(-15.0, 15.0, count):
        ws = maker.wheels(float(luff))
        frames.append([(np.array([c[0], 0.0, c[1]]) * MM, Y) for _n, c, _r, _s in ws[:3]])
    radii = [w[2] * MM for w in maker.wheels(0.0)[:3]]
    start = np.array([maker.NUMBERS["rope"]["start"]]) .reshape(3) * MM
    end = np.array([2.7, 0.0, 0.65])
    out, centres, _ = frames_of(frames, radii, [-1, 1, -1], start, end, start_on_wheel=True, counts=[40, 50, 40], held=True)
    assert out["ok"].all() and out["held"].all() and not out["problems"]
    moved = np.linalg.norm(np.diff(out["points"], axis=0), axis=2).max(axis=1)
    wheel_step = np.linalg.norm(np.diff(centres, axis=0), axis=2).max(axis=1)
    assert (moved <= 1.5 * wheel_step + 1e-9).all()
    assert np.abs(np.diff(moved)).max() < 0.02 * moved.max()            # … and evenly: no step unlike its neighbours
    assert (np.abs(np.diff(out["wrap"], axis=0)) < math.radians(0.2)).all()
    assert np.abs(np.diff(out["length"])).max() < 1.5 * wheel_step.max()
    # the ends of the range are the maker's own numbers
    for f, luff in ((0, -15.0), (count - 1, 15.0)):
        n = maker.numbers_at(luff)["contacts"]
        assert np.degrees(out["wrap"][f, :2]) == pytest.approx([n["WINCH DRUM"]["wrap"], n["SHEAVE 1"]["wrap"]], abs=2e-4)


def test_a_wheel_tilting_through_parallel_moves_the_cable_smoothly():
    """The second wheel's axis tilts from -15° through parallel to +15° in 501 steps (exactly parallel in the
    middle frame): with the arcs held in their planes nothing jumps where the two ways of working a straight out
    (parallel axes: a formula; not parallel: Newton) change over, and the frames are ``solve`` frame by frame."""
    count = 501
    tilt = np.radians(np.linspace(-15.0, 15.0, count))
    frames = [[(np.zeros(3), Y), (np.array([2.0, 0.0, 0.3]), rot(X, t) @ Y)] for t in tilt]
    start, end = np.array([-2.0, 0.0, 0.0]), np.array([5.0, 0.0, -0.5])
    out, _, axes = frames_of(frames, [0.3, 0.25], [1, 1], start, end, counts=[12, 20], held=True)
    assert out["ok"].all()
    moved = np.linalg.norm(np.diff(out["points"], axis=0), axis=2).max(axis=1)
    assert moved.max() < 0.5 * (tilt[1] - tilt[0])              # under 0.5 m per radian of tilt (measured 0.25)
    assert moved[248:252].max() < 1.2 * np.median(moved)        # nothing special where the axes are parallel
    for f in (0, 100, 249, 250, 251, 400, 500):
        one = P.solve(start, [P.Wheel(c, a, r, 1) for (c, a), r in zip(frames[f], (0.3, 0.25))], end, counts=[12, 20], held=True)
        fine(one)
        assert np.abs(one.points - out["points"][f]).max() < 1e-9 and np.abs(one.s - out["s"][f]).max() < 1e-9


def test_frames_are_solve_frame_by_frame_with_bad_frames_in_the_middle():
    """A sheave passes so close to another that for a while no straight fits between them (they go round the
    cable on opposite sides and overlap). Those frames are refused with the two contacts named and keep the last
    good shape; every other frame is exactly what ``solve`` gives; afterwards the cable is right again."""
    count = 120
    xs = np.linspace(1.6, -0.2, count)                           # wheel 2 comes in from the right, over wheel 1
    frames = [[(np.zeros(3), Y), (np.array([x, 0.0, 0.45]), Y)] for x in xs]
    radii, sides = [0.3, 0.25], [1, -1]
    start, end = np.array([-3.0, 0.0, -0.5]), np.array([4.0, 0.0, 2.0])
    for held in (True, None):
        out, _, _ = frames_of(frames, radii, sides, start, end, counts=[30, 30], held=held)
        assert np.isfinite(out["points"]).all() and np.isfinite(out["s"]).all() and np.isfinite(out["wrap"]).all()
        bad = np.flatnonzero(~out["ok"])
        assert 5 < len(bad) < count - 20 and bad[0] > 5
        assert sorted(out["problems"]) == list(bad)
        last_good = None
        for f in range(count):
            wheels = [P.Wheel(c, a, r, s) for (c, a), r, s in zip(frames[f], radii, sides)]
            one = P.solve(start, wheels, end, counts=[30, 30], held=held)
            assert one.ok == bool(out["ok"][f])
            if one.ok:
                assert np.abs(one.points - out["points"][f]).max() < 1e-9
                assert abs(one.length - out["length"][f]) < 1e-9 and np.abs(one.wrap - out["wrap"][f]).max() < 1e-9
                assert out["bad"][f] == -1
                last_good = f
            else:
                assert out["problems"][f] == one.problem and out["bad"][f] == one.bad
                assert "contact 1" in one.problem.lower() and "contact 2" in one.problem
                assert np.array_equal(out["points"][f], out["points"][last_good])       # the last good shape
        # my own: the crossing straight exists while the centres are further apart than the two radii together
        apart = np.hypot(xs, 0.45)
        assert (out["ok"][apart > 0.55 + 1e-3]).all() or held is None
        assert not out["ok"][apart < 0.55 - 1e-3].any()


JUNK = [
    # name, start, wheels (centre, axis, radius, side), end, extra, expected: None = a path, else (number, bad)
    ("coincident wheels", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((0, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (2, 1)),
    ("the same place, other side", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((0, 0, 0), Y, 0.3, -1)], (4, 0, 0.3), {}, (2, 1)),
    ("a wheel inside a wheel", (-2, 0, 0.3), [((0, 0, 0), Y, 1.0, 1), ((0.2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (2, 1)),
    ("overlapping, opposite sides", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((0.5, 0, 0), Y, 0.3, -1)], (4, 0, 0.3), {}, (2, 1)),
    ("start inside the first wheel", (0.1, 0, 0), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (1, 0)),
    ("start on the wheel's axis", (0, -3, 0), [((0, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (1, 0)),
    ("end inside the last wheel", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (2.1, 0, 0), {}, (2, 1)),
    ("radius 0", (-2, 0, 0.3), [((0, 0, 0), Y, 0.0, 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (1, 0)),
    ("radius below 0", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, -0.3, 1)], (4, 0, 0.3), {}, (2, 1)),
    ("radius not a number", (-2, 0, 0.3), [((0, 0, 0), Y, float("nan"), 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (1, 0)),
    ("axis of no length", (-2, 0, 0.3), [((0, 0, 0), (0, 0, 0), 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (1, 0)),
    ("centre not a number", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((float("nan"), 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (2, 1)),
    ("axis not a number", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), (0, float("inf"), 0), 0.3, 1)], (4, 0, 0.3), {}, (2, 1)),
    ("start not a number", (float("inf"), 0, 0), [((0, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, (None, -1)),
    ("end not a number", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1)], (4, float("nan"), 0.3), {}, (None, -1)),
    ("start exactly on the circle", (0, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0.3), {}, None),
    ("end exactly on the circle", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (2, 0, 0.3), {}, None),
    ("end on the circle's far side", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (2, 0, -0.3), {}, None),
    ("circles that just touch, an S", (-2, 0, 0.3), [((0, 0, 0), Y, 0.3, 1), ((0.6, 0, 0), Y, 0.3, -1)], (3, 0, -0.3), {}, None),
    ("axis not of length 1", (-2, 0, 0), [((0, 0, 0), (0, 100, 0), 0.3, 1), ((2, 0, 0), (0, 1e-3, 0), 0.3, 1)], (4, 0, 0), {}, None),
    ("lists and whole numbers", [-2, 0, 1], [([0, 0, 0], [0, 1, 0], 1, 1)], [4, 0, 1], {}, None),
    ("start and end the same, no wheels", (1, 2, 3), [], (1, 2, 3), {}, None),
    ("ends on wheels, but no wheels", (1, 2, 3), [], (2, 2, 3), {"start_on_wheel": True, "end_on_wheel": True}, None),
    ("both ends at one place of one wheel", (-0.3, 0, 0), [((0, 0, 0), Y, 0.3, 1)], (-0.3, 0, 0),
     {"start_on_wheel": True, "end_on_wheel": True}, None),
    ("the axis along the cable", (-2, 0, 0.3), [((0, 0, 0), X, 0.3, 1)], (4, 0, 0.3), {}, None),
    ("fewer than 2 points asked for", (-2, 0, 0), [((0, 0, 0), Y, 0.3, 1), ((2, 0, 0), Y, 0.3, 1)], (4, 0, 0),
     {"counts": [0, 1]}, None),
]


@pytest.mark.parametrize("case", JUNK, ids=[c[0] for c in JUNK])
def test_what_cannot_be_is_refused_in_plain_words_and_nothing_is_ever_broken(case):
    """Coincident wheels, an end inside a circle, radii and axes that are none, numbers that are not numbers: a
    sentence that names the contact (counted from 1) and no shape; odd but possible input: a whole path. Never an
    exception, never NaN (NumPy's warnings are errors here: no quiet NaN arithmetic either)."""
    _name, start, wheel_list, end, extra, expected = case
    wheels = [P.Wheel(np.array(c, dtype=float), np.array(a, dtype=float), r, s) for c, a, r, s in wheel_list]
    for held in HELD:
        with np.errstate(all="raise"):
            path = P.solve(np.array(start, dtype=float), wheels, np.array(end, dtype=float), held=held, **extra)
        if expected is None:
            fine(path)
            assert len(path.points) >= 2 and len(path.first) == len(wheels) and (path.counts >= 2).all()
        else:
            refused(path, number=expected[0], bad=expected[1])
            assert len(path.wrap) == len(wheels) and len(path.first) == len(wheels)


def test_the_same_in_32_bit_numbers():
    """Places as Blender hands them out (float32), 150 m from the origin: the same cable within what such numbers
    can say (their step is 0.015 mm there)."""
    rng = np.random.default_rng(32)
    for _ in range(20):
        co = walked(rng, 3, far=150.0)
        wheels = co.wheels()
        low = [P.Wheel(w.centre.astype(np.float32), w.axis.astype(np.float32), np.float32(w.radius), np.int8(1)) for w in wheels]
        exact = P.solve(co.start, wheels, co.p, held=True)
        path = P.solve(co.start.astype(np.float32), low, co.p.astype(np.float32), held=True, counts=list(exact.counts))
        fine(exact)
        fine(path)
        assert path.points.dtype == np.float64
        assert np.abs(path.points - exact.points).max() < 0.2 * MM and abs(path.length - exact.length) < 0.2 * MM


def test_wheels_in_the_wrong_order_or_on_the_other_side_are_still_whole_paths():
    """Not what the user meant, but a cable that can be: no refusal is promised here, only that what comes out
    is a real tight string (touching, without kinks, the sides as asked)."""
    start, end = np.array([-2.0, 0.0, 0.5]), np.array([4.0, 0.0, 0.5])
    w1, w2 = P.Wheel(np.zeros(3), Y, 0.3, 1), P.Wheel(np.array([2.0, 0.0, 0.0]), Y, 0.3, 1)
    for wheels in ([w2, w1], [P.Wheel(w1.centre, Y, 0.3, -1), P.Wheel(w2.centre, Y, 0.3, -1)],
                   [P.Wheel(w1.centre, -Y, 0.3, 1), w2]):
        for held in HELD:
            path = P.solve(start, wheels, end, held=held)
            if not path.ok:
                refused(path)
                continue
            m = measure(path, wheels, start, end)
            assert m["side"] and m["forward"] and m["layout"] and m["kink"] < 1e-5 and m["tangent"] < 1e-9
            assert m["radius"] < 1e-12 and m["length"] < 1e-9


def test_250_frames_of_12_wheels_take_no_time():
    rng = np.random.default_rng(7)
    co = Course(np.zeros(3), X).line(2.0)
    for i in range(12):
        co.arc(Y if i % 2 == 0 else -Y, rng.uniform(0.2, 0.6), rng.uniform(40, 120)).line(rng.uniform(1.0, 3.0))
    wheels = co.wheels()
    frames = 250
    sway = 0.05 * np.sin(np.linspace(0.0, 6.0, frames))
    centres = np.array([[w.centre + [0.0, 0.0, sway[f] * (i % 3)] for i, w in enumerate(wheels)] for f in range(frames)])
    axes = np.array([[w.axis for w in wheels]] * frames)
    args = (np.tile(co.start, (frames, 1)), centres, axes, [w.radius for w in wheels], [1] * 12, np.tile(co.p, (frames, 1)))
    P.solve_frames(*args, held=True)
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        out = P.solve_frames(*args, held=True)
        best = min(best, time.perf_counter() - t0)
    assert out["ok"].all() and out["points"].shape[0] == frames
    assert best < 1.0                                           # the brief: well under 0.1 s (measured 0.02 s)


# =====================================================================================================================
# the small ones: what turns how fast, stripes, point counts, the tightest bend
# =====================================================================================================================

def test_wheel_ratio_is_degrees_per_millimetre_with_the_right_sign():
    # 1 mm of cable on a rim of radius 250 mm turns it by 1/250 rad
    assert P.wheel_ratio(0.25, 1, Y, Y) == pytest.approx(math.degrees(1.0 / 250.0), rel=1e-12)
    assert P.wheel_ratio(0.25, -1, Y, Y) == pytest.approx(-math.degrees(1.0 / 250.0), rel=1e-12)
    assert P.wheel_ratio(0.25, 1, Y, -Y) == pytest.approx(-math.degrees(1.0 / 250.0), rel=1e-12)
    assert P.wheel_ratio(0.25, -1, Y, -Y) == pytest.approx(math.degrees(1.0 / 250.0), rel=1e-12)
    assert P.wheel_ratio(0.25, 1, Y, Y, reverse=True) == pytest.approx(-math.degrees(1.0 / 250.0), rel=1e-12)
    assert P.wheel_ratio(0.25, 1, Y, unit([0.1, 0.9, 0.0])) > 0 > P.wheel_ratio(0.25, 1, Y, unit([0.1, -0.9, 0.0]))
    # a 100 m Motor step: the rim runs 100 m (the brief: within 0.1 %), radii from 5 mm to 10 m
    for r in (0.005, 0.06, 0.18, 2.5, 10.0):
        turned = math.radians(P.wheel_ratio(r, 1, Z, Z) * 100_000.0)
        assert turned * r == pytest.approx(100.0, rel=1e-12)
    # the side is the brief's: sign(((p - c) x t) . axis); over the top of a wheel about +Y going +X it is +1,
    # and that wheel then turns about +Y (its top runs +X): w x r = (+Y) x (+Z) = +X
    assert float(np.cross(0.25 * Z, X) @ Y) > 0.0
    assert np.allclose(np.cross(Y * math.radians(P.wheel_ratio(0.25, 1, Y, Y)), 0.25 * Z), X * 1e-3)


def test_stripes_and_the_angle_they_stand_at():
    d = 0.1
    # round(pi d / (pitch tan(angle)))
    assert P.stripes(d, 0.2, math.radians(45)) == round(math.pi * d / 0.2)
    assert P.stripes(d, 0.05, math.radians(45)) == 6
    assert P.stripes(d, 0.05, math.radians(30)) == round(math.pi * d / (0.05 * math.tan(math.radians(30))))
    assert P.stripes(d, 0.05, math.radians(-30)) == -P.stripes(d, 0.05, math.radians(30))
    assert P.stripes(d, 0.2, math.radians(90)) == 0 and P.stripes(d, 0.2, math.radians(89.99)) == 0
    assert P.stripes(d, 0.0, math.radians(45)) == 0
    for pitch in (0.02, 0.05, 0.3):
        for starts in (-6, -1, 1, 2, 6, 12):
            angle = P.stripe_angle(d, pitch, starts)
            assert math.tan(angle) == pytest.approx(math.pi * d / (starts * pitch), rel=1e-12)
            assert P.stripes(d, pitch, angle) == starts
    assert P.stripe_angle(d, 0.2, 0) == pytest.approx(0.5 * math.pi)
    # a 6-strand wire rope of 24 mm with a lay of 150 mm between strands … the strands stand at 4.8° to the rope
    assert deg(P.stripe_angle(0.024, 0.15, 6)) == pytest.approx(math.degrees(math.atan(math.pi * 0.024 / 0.9)), abs=1e-9)


def test_point_counts():
    step = math.radians(4.0)
    assert P.point_counts([0.0, 1e-12, step, 1.0001 * step, 2.0 * step, math.radians(350.0)]) == [2, 2, 2, 3, 3, 89]
    assert P.point_counts(math.radians(90.0)) == [24]
    assert P.point_counts([0.0, 3.0], least=5) == [5, math.ceil(3.0 / step) + 1]
    assert P.point_counts([math.pi], step=math.radians(10.0)) == [19]
    assert P.point_counts([-1.0, float("nan"), float("inf")]) == [2, 2, 2]             # never fewer, never an error
    for wrap in np.radians([0.01, 3.99, 4.01, 77.0, 180.0, 349.0]):                    # no piece wider than a step
        (n,) = P.point_counts([wrap])
        assert wrap / (n - 1) <= step + 1e-12 and (n == 2 or wrap / (n - 2) > step - 1e-9)


def test_tightest_bend():
    wheels = [P.Wheel(np.zeros(3), Y, r, 1) for r in (0.5, 0.1, 0.3, 0.2)]
    assert P.tightest(wheels, [1.0, 1.0, 1.0, 1.0]) == (1, 0.1)
    assert P.tightest(wheels, [1.0, 0.0, 1.0, 1.0]) == (3, 0.2)                       # no wrap: no bend
    assert P.tightest(wheels, np.radians([90.0, 0.99, 90.0, 0.99])) == (2, 0.3)       # under 1°: not counted
    assert P.tightest(wheels, np.radians([90.0, 1.0, 90.0, 0.99])) == (1, 0.1)
    assert P.tightest(wheels, [0.0, 0.0, 0.0, 0.0]) == (-1, math.inf) and P.tightest([], []) == (-1, math.inf)
    assert P.tightest(wheels, [1.0] * 4, least_wrap=2.0) == (-1, math.inf)


# =====================================================================================================================
# seat, surface_radius, is_round: meshes of my own, anywhere in space
# =====================================================================================================================

POSE = (rot(unit([0.3, -0.5, 0.8]), 0.7), np.array([180.0, -150.0, 90.0]))        # turned, 250 m from the origin


def posed(outline, sides=48, rng=None, sweep=2.0 * math.pi, f32=False):
    """A part revolved from an outline, turned in space far from its mesh origin: (verts, tris, centre, axis)."""
    turn, move = POSE
    v, t = revolve(outline, sides, rng=rng, sweep=sweep)
    v = v @ turn.T + move
    return (v.astype(np.float32) if f32 else v), t, move.copy(), turn @ Z


@pytest.mark.parametrize("rope", [0.010, 0.025, 0.1, 0.25])
def test_seat_in_a_round_groove_wider_than_the_rope(rope):
    """Cable Ø 20 to 500 mm in a groove 8 % wider: the cable's middle is at groove bottom + cable radius. The
    facets of the groove's section stand off its true bottom by their sagitta, and nothing more is lost - also
    with the corners in 32-bit numbers 250 m from the origin (their step there: 0.015 mm)."""
    rng = np.random.default_rng(8)
    bottom, groove = 12.0 * rope, 1.08 * rope
    for sides, steps in ((24, 8), (48, 24), (96, 64)):
        outline = groove_outline(bottom, groove, bottom + 2.2 * rope, 5.0 * rope, steps)
        sagitta = groove * (1.0 - math.cos(math.radians(140.0) / steps / 2.0))
        for f32 in (False, True):
            v, t, c, a = posed(outline, sides, rng, f32=f32)
            place, radius = P.seat(v, t, c, a, 0.0, rope)
            assert abs(place) < 1e-6
            # (+ 0.05 % of the cable's radius: the steps the outline is read in)
            coarse = 0.03 * MM if f32 else 1e-6
            assert -coarse <= radius - (bottom + rope) <= sagitta + 5e-4 * rope + coarse
    # with the facets a real mesh has (the importer keeps them within 0.5 mm, small parts far finer) …
    v, t, c, a = posed(groove_outline(bottom, groove, bottom + 2.2 * rope, 5.0 * rope, 64), 96, rng)
    assert abs(P.seat(v, t, c, a, 0.0, rope)[1] - (bottom + rope)) < max(0.1 * MM, 0.0005 * rope)    # the brief: 0.1 mm


def test_seat_in_grooves_narrower_than_the_rope():
    """A round groove or a square slot too narrow for the rope: it rides on the two edges."""
    top = 0.3
    for rope, groove in ((0.02, 0.012), (0.02, 0.019), (0.05, 0.01)):
        half = [(groove * math.sin(t), top - groove * math.cos(t)) for t in np.linspace(-math.pi / 2, math.pi / 2, 33)]
        v, t, c, a = posed([(-0.1, 0.2), (-0.1, top)] + half + [(0.1, top), (0.1, 0.2)])
        place, radius = P.seat(v, t, c, a, 0.0, rope)
        assert abs(place) < 1e-6 and radius == pytest.approx(top + math.sqrt(rope ** 2 - groove ** 2), abs=1e-6)
    for rope, wide in ((0.02, 0.03), (0.02, 0.01)):
        slot = [(-0.1, 0.2), (-0.1, top), (-wide / 2, top), (-wide / 2, top - 0.05), (wide / 2, top - 0.05),
                (wide / 2, top), (0.1, top), (0.1, 0.2)]
        v, t, c, a = posed(slot)
        want = top + math.sqrt(rope ** 2 - (wide / 2) ** 2)
        for at in (0.0, 0.6 * rope, -0.9 * rope):                      # … also when the cable is drawn beside it
            place, radius = P.seat(v, t, c, a, at, rope)
            assert abs(place) < 0.02 * rope and radius == pytest.approx(want, abs=1e-6)


@pytest.mark.parametrize("beta", [20.0, 35.0, 45.0, 60.0])
def test_seat_in_a_v_groove(beta):
    """Flanks ``beta`` from the sheave's plane: the rope touches both, its middle r / sin(beta) above the V's
    point - found also from 0.7 radii beside the middle."""
    b = math.radians(beta)
    for rope in (0.012, 0.1):
        apex = 8.0 * rope
        top = apex + 3.0 * rope / math.sin(b)
        reach = (top - apex) * math.tan(b)
        v, t, c, a = posed([(-reach - 0.01, 0.5 * apex), (-reach - 0.01, top), (-reach, top), (0.0, apex), (reach, top),
                            (reach + 0.01, top), (reach + 0.01, 0.5 * apex)])
        for at in (0.0, 0.7 * rope, -0.7 * rope):
            place, radius = P.seat(v, t, c, a, at, rope)
            assert abs(place) < 0.01 * rope
            assert radius == pytest.approx(apex + rope / math.sin(b), abs=max(1e-6, 1e-5 * rope))


def test_seat_finds_a_groove_beside_where_the_cable_is_drawn_but_not_far_off():
    """The groove up to one cable radius beside ``at``: the cable sinks into it. Further off: it stays where it
    is (on the flange). Two grooves side by side: the nearer one."""
    rope, bottom = 0.012, 0.238
    for beside in (0.3, 0.8, 0.99, -0.6):
        v, t, c, a = posed(groove_outline(bottom, 0.013, bottom + 0.028, 0.2, 24, z0=beside * rope))
        place, radius = P.seat(v, t, c, a, 0.0, rope)
        assert place == pytest.approx(beside * rope, abs=0.02 * rope) and abs(radius - (bottom + rope)) < 0.05 * MM
    for beside in (1.5, 2.5):
        v, t, c, a = posed(groove_outline(bottom, 0.013, bottom + 0.028, 0.2, 24, z0=beside * rope))
        place, radius = P.seat(v, t, c, a, 0.0, rope)
        assert place == pytest.approx(0.0, abs=1e-9) and radius > bottom + rope + 0.02
    v, t, c, a = posed(groove_outline(bottom, 0.013, bottom + 0.028, 0.2, 24, z0=0.8 * rope))
    assert P.seat(v, t, c, a, 0.0, rope, search=0.5 * rope)[0] == pytest.approx(0.0, abs=1e-9)      # search: how far
    assert P.seat(v, t, c, a, -1.0 * rope, rope, search=2.0 * rope)[0] == pytest.approx(0.8 * rope, abs=0.02 * rope)
    pitch = 2.6 * rope
    one = groove_outline(bottom, 0.013, bottom + 0.02, 0.0, 16, z0=-pitch / 2)
    two = groove_outline(bottom, 0.013, bottom + 0.02, 0.0, 16, z0=pitch / 2)
    v, t, c, a = posed([(-0.05, 0.15), (-0.05, bottom + 0.02)] + one[2:-2] + two[2:-2] + [(0.05, bottom + 0.02), (0.05, 0.15)])
    for at, want in ((-pitch / 2, -pitch / 2), (-0.4 * rope, -pitch / 2), (0.4 * rope, pitch / 2),
                     (pitch / 2 + 0.5 * rope, pitch / 2)):
        place, radius = P.seat(v, t, c, a, at, rope)
        assert place == pytest.approx(want, abs=0.02 * rope) and abs(radius - (bottom + rope)) < 0.06 * MM


def test_seat_on_a_flanged_drum_a_cone_and_a_hollow_roller():
    rope = 0.012
    rng = np.random.default_rng(81)
    # a plain barrel of radius 200 between flanges of radius 300 (their inner faces at +-0.2)
    drum = [(-0.22, 0.04), (-0.22, 0.3), (-0.2, 0.3), (-0.2, 0.2), (0.2, 0.2), (0.2, 0.3), (0.22, 0.3), (0.22, 0.04)]
    v, t, c, a = posed(drum, 48, rng)
    for at in (0.0, 0.15, -0.18, 0.2 - 1.01 * rope):
        place, radius = P.seat(v, t, c, a, at, rope)
        assert place == pytest.approx(at, abs=1e-9) and radius == pytest.approx(0.212, abs=1e-6)
    place, radius = P.seat(v, t, c, a, 0.2 - 0.5 * rope, rope)          # drawn half into the flange: beside it
    assert place == pytest.approx(0.2 - rope, abs=0.02 * rope) and radius == pytest.approx(0.212, abs=1e-5)
    assert P.seat(v, t, c, a, 0.21, rope)[1] == pytest.approx(0.312, abs=1e-6)          # on the flange's rim
    assert P.seat(v, t, c, a, 0.3, rope) == (0.3, 0.0)                                  # beside the drum: nothing
    assert P.surface_radius(v, t, c, a, 0.0, 2.0 * rope) == pytest.approx(0.2, abs=1e-9)
    assert P.surface_radius(v, t, c, a, 0.21, 0.01) == pytest.approx(0.3, abs=1e-9)
    assert P.surface_radius(v, t, c, a, 0.2 - rope, 4.0 * rope) == pytest.approx(0.3, abs=1e-9)   # the widest in reach
    assert P.surface_radius(v, t, c, a, 0.4, 0.05) == 0.0
    # a cone, radius 0.2 + k z: the cable does not slide down; its middle is square out from where it touches
    for k in (0.05, 0.3, 1.0, 3.0):
        low = max(-0.3, (0.01 - 0.2) / k + 1e-3)
        v, t, c, a = posed([(low, 0.2 + low * k), (0.3, 0.2 + 0.3 * k)], 64, rng)
        place, radius = P.seat(v, t, c, a, 0.1, rope)
        assert place == pytest.approx(0.1, abs=1e-9)
        assert radius == pytest.approx(0.2 + 0.1 * k + rope * math.sqrt(1.0 + k * k), abs=2e-6)
        assert P.surface_radius(v, t, c, a, 0.1, 1e-4) == pytest.approx(0.2 + 0.1 * k, abs=1e-4 * k + 1e-6)
    # a tube: the bore (radius 50) never wins over the outside (60)
    turn, move = POSE
    outer, inner = revolve([(-0.25, 0.06), (0.25, 0.06)], 24, rng=rng), revolve([(-0.25, 0.05), (0.25, 0.05)], 24, rng=rng)
    v = np.concatenate([outer[0], inner[0]]) @ turn.T + move
    t = np.concatenate([outer[1], inner[1][:, ::-1] + len(outer[0])])
    assert P.seat(v, t, move, turn @ Z, 0.1, rope) == pytest.approx((0.1, 0.072), abs=1e-9)
    assert P.surface_radius(v, t, move, turn @ Z, 0.0, 0.02) == pytest.approx(0.06, abs=1e-9)
    assert P.is_round(v, move, turn @ Z)
    # nothing to rest on, a cable of no thickness, a place that is no number: no radius, no error
    assert P.seat(v, t, move, turn @ Z, 0.1, 0.0)[1] == 0.0
    assert P.seat(v, t, move, turn @ Z, float("nan"), rope)[1] == 0.0
    assert P.seat(np.zeros((0, 3)), np.zeros((0, 3), dtype=int), np.zeros(3), Z, 0.0, rope) == (0.0, 0.0)
    assert not P.is_round(np.zeros((0, 3)), np.zeros(3), Z)


@pytest.mark.parametrize("sweep_deg", [60.0, 90.0, 180.0, 290.0, 360.0])
def test_a_part_of_a_turn_is_not_round_but_carries_the_cable_all_the_same(sweep_deg):
    """A chute or quadrant (60° … 290° of a turn) does not turn; a whole revolve does. The seat is the same on
    every one of them, with coarse and with fine facets."""
    rope, bottom = 0.012, 0.238
    for sides in (6, 12, 48):
        v, t, c, a = posed(groove_outline(bottom, 0.013, bottom + 0.028, 0.06, 12), sides, sweep=math.radians(sweep_deg))
        assert P.is_round(v, c, a) == (sweep_deg == 360.0)
        assert abs(P.seat(v, t, c, a, 0.0, rope)[1] - (bottom + rope)) < 0.08 * MM


def test_is_round_on_plain_shapes():
    """Rollers, sheaves and drums (with holes in the web: holes inside do not matter), a hexagon bar as coarse as
    a mesh gets; not round: square and five-sided bars, a roller in one piece with its bracket, an axis that is
    not the part's own."""
    plain = revolve(roller_outline(0.06, 0.6), 32)[0]
    assert P.is_round(plain, np.zeros(3), Z) and P.is_round(plain, np.zeros(3), -Z * 5.0)
    assert P.is_round(plain + [3.0, 4.0, 5.0], np.array([3.0, 4.0, 77.0]), Z)           # any point on the axis
    sheave = revolve(groove_outline(0.238, 0.013, 0.266, 0.056, 12), 48)[0]
    holes = np.array([[0.12 * math.cos(b) + 0.04 * math.cos(q), 0.12 * math.sin(b) + 0.04 * math.sin(q), z]
                      for b in np.linspace(0, 2 * math.pi, 5, endpoint=False)
                      for q in np.linspace(0, 2 * math.pi, 16, endpoint=False) for z in (-0.01, 0.01)])
    assert P.is_round(sheave, np.zeros(3), Z) and P.is_round(np.concatenate([sheave, holes]), np.zeros(3), Z)
    drum = revolve([(-0.22, 0.04), (-0.22, 0.3), (-0.2, 0.3), (-0.2, 0.2), (0.2, 0.2), (0.2, 0.3), (0.22, 0.3), (0.22, 0.04)], 48)[0]
    assert P.is_round(drum, np.zeros(3), Z)
    for sides, round_ in ((4, False), (5, False), (6, True), (8, True), (12, True)):
        assert P.is_round(revolve([(-0.1, 0.05), (0.1, 0.05)], sides)[0], np.zeros(3), Z) == round_
    bracket = np.array([[x, y, z] for x in (-0.1, 0.1) for y in (-0.15, -0.1) for z in (-0.3, 0.3)])
    assert not P.is_round(np.concatenate([plain, bracket]), np.zeros(3), Z)
    assert not P.is_round(plain, np.array([0.005, 0.0, 0.0]), Z)                        # 5 mm beside the roller's axis
    assert not P.is_round(plain, np.zeros(3), X)                                        # across it
    assert not P.is_round(np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), np.zeros(3), Z)
    assert not P.is_round(plain * float("nan"), np.zeros(3), Z)


# =====================================================================================================================
# read_cable: a cable drawn in CAD, read from a tube with facets
# =====================================================================================================================

def shaped(reading):
    return [c for c in reading.contacts if c.kind != "TOUCH"]


def off_path(reading, pts):
    """My own distance from points to the read path: its straights between the arcs' ends, and each arc on its
    contact's circle (centre, axis, radius as the contact says)."""
    path = reading.path
    pts = np.asarray(pts, dtype=float)
    best = np.full(len(pts), np.inf)
    corners = [] if reading.start_on_wheel else [path.points[0]]
    for i, c in enumerate(shaped(reading)):
        arc = path.points[path.first[i]:path.first[i] + path.counts[i]]
        corners += [arc[0], arc[-1]]
        a = unit(c.axis)
        rel = pts - c.centre
        u = unit(arc[0] - c.centre - ((arc[0] - c.centre) @ a) * a)
        v = np.cross(a, u) * c.side
        th = np.mod(np.arctan2(rel @ v, rel @ u), 2.0 * math.pi)
        wrap = float(path.wrap[i])
        th = np.where(th > wrap, np.where(th - wrap < 2.0 * math.pi - th, wrap, 0.0), th)
        on = c.centre + c.radius * (np.cos(th)[:, None] * u + np.sin(th)[:, None] * v)
        best = np.minimum(best, np.linalg.norm(on - pts, axis=1))
    if not reading.end_on_wheel:
        corners.append(path.points[-1])
    for p, q in zip(corners[0::2], corners[1::2]):
        d = q - p
        f = np.clip(((pts - p) @ d) / max(float(d @ d), 1e-30), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(p + f[:, None] * d - pts, axis=1))
    return best


@pytest.mark.parametrize("rope", [0.010, 0.05, 0.25])
def test_read_a_faceted_cable_over_two_sheaves_and_a_bend(rope):
    """Cable Ø 20, 100 and 500 mm drawn as a tube with facets, over a sheave, under a second one (its axis the
    other way round), through a bend in the air: WRAP, WRAP, BEND in that order, the sheaves' centres, axes and
    seats from the parts, the sides right, the wraps within 0.05°, the path within 1.2 % of the cable's radius
    (or 0.2 mm) of the true route, and ``deviation`` is what I measure myself."""
    rng = np.random.default_rng(9)
    co = (Course([3.0, -2.0, 1.0], [1.0, 0.0, 0.2]).line(165 * rope).arc(Y, 20 * rope, 120.0).line(125 * rope)
          .arc(-Y, 30 * rope, 75.0).line(85 * rope).arc([0.0, 1.0, 0.3], 50 * rope, 40.0).line(65 * rope))
    a1, a2, a3 = co.arcs()
    rounds = [sheave_for(a2, rope, "under", flip=True, rng=rng), sheave_for(a1, rope, "over", rng=rng)]
    rd, tube = read(co, rope, rounds)
    assert rd.ok and rd.problem == "", rd.problem
    assert tube.radius == pytest.approx(rope, rel=0.01) and abs(tube.length - co.length) < 0.5 * rope
    assert co.off(tube.points).max() < 0.015 * rope                    # what the facets leave of the centreline
    assert kinds(rd) == [("WRAP", "over"), ("WRAP", "under"), ("BEND", None)]
    over, under, bend = rd.contacts
    assert not rd.start_on_wheel and not rd.end_on_wheel
    assert np.linalg.norm(rd.start - co.start) < 0.02 * rope and np.linalg.norm(rd.end - co.p) < 0.02 * rope
    for c, a, side in ((over, a1, 1), (under, a2, -1)):
        assert c.side == side and c.full and c.key in ("over", "under")
        assert angle_deg(c.axis, a["n"] * side) < 1e-6                  # the part's own axis, as it was given
        rel = c.centre - a["c"]                                         # on the axis, in the cable's plane
        assert np.linalg.norm(rel - (rel @ a["n"]) * a["n"]) < 1e-8 and abs(float(rel @ a["n"])) < 0.01 * rope
        assert 0.0 <= c.radius - a["r"] < 0.002 * rope + 0.02 * MM      # the seat from the mesh (facets: a hair up)
        assert c.surface == pytest.approx(c.radius - rope, abs=0.002 * rope)
        assert abs(c.gap) < 0.02 * rope
        assert deg(c.wrap) == pytest.approx(math.degrees(a["angle"]), abs=0.05)
    assert bend.key is None and bend.surface == 0.0 and not bend.full and bend.gap == 0.0
    assert bend.radius == pytest.approx(a3["r"], rel=0.004) and deg(bend.wrap) == pytest.approx(40.0, abs=0.1)
    assert angle_deg(bend.axis * bend.side, a3["n"]) < 0.1
    assert [c.s for c in rd.contacts] == sorted(c.s for c in rd.contacts)
    for c, a in zip(rd.contacts, co.arcs()):
        assert c.s == pytest.approx(a["s0"] + 0.5 * a["length"], abs=0.5 * rope)
    assert co.off(rd.path.points).max() < max(0.012 * rope, 0.2 * MM)
    assert abs(rd.path.length - co.length) < 0.1 * rope
    mine = float(off_path(rd, tube.points).max())
    assert rd.deviation == pytest.approx(mine, abs=1e-7) and rd.deviation < max(0.012 * rope, 0.2 * MM)
    wheels = [P.Wheel(c.centre, c.axis, c.radius, c.side) for c in rd.contacts]
    m = measure(rd.path, wheels, rd.start, rd.end)
    assert m["side"] and m["forward"] and m["layout"] and m["kink"] < 0.1 and m["plane"] < 1e-9


def test_read_only_the_part_the_cable_rests_on_of_those_that_share_an_axis():
    """A sheave, its pin and the bores of its bracket's cheeks all have the one axis: the sheave is the contact,
    whatever the order the parts are given in; without the sheave the arc is a bend in the air."""
    rope = 0.012
    rng = np.random.default_rng(12)
    co = Course([0.0, 0.0, 0.0], [1.0, 0.0, 0.3]).line(0.6).arc(Y, 0.2, 110.0).line(0.7)
    a = co.arcs()[0]
    sheave = sheave_for(a, rope, "SHEAVE", rng=rng)
    pin = P.Round("PIN", a["c"], Y, *revolve([(-0.08, 1e-4), (-0.08, 0.02), (0.08, 0.02), (0.08, 1e-4)], 24, a["c"], Y))
    verts, tris = [], []
    for y0, y1 in ((0.04, 0.06), (-0.06, -0.04)):                       # two square cheeks, each with its bore
        base = sum(len(v) for v in verts)
        verts.append(np.array([a["c"] + [0.25 * sx, y, 0.25 * sz] for y in (y0, y1)
                               for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]))
        tris.append(np.array([(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
                              (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]) + base)
        bore = revolve([(y0, 0.0205), (y1, 0.0205)], 16, a["c"], Y)
        base = sum(len(v) for v in verts)
        verts.append(bore[0])
        tris.append(bore[1] + base)
    bracket = P.Round("BRACKET", a["c"], Y, np.concatenate(verts), np.concatenate(tris))
    tube = centreline_of(co, rope)
    for rounds in ([sheave, pin, bracket], [bracket, pin, sheave], [pin, sheave, bracket]):
        rd = P.read_cable(tube.points, tube.radius, rounds)
        assert rd.ok and kinds(rd) == [("WRAP", "SHEAVE")]
        assert rd.contacts[0].side == 1 and deg(rd.contacts[0].wrap) == pytest.approx(110.0, abs=0.05)
    rd = P.read_cable(tube.points, tube.radius, [pin, bracket])
    assert rd.ok and kinds(rd) == [("BEND", None)] and rd.contacts[0].radius == pytest.approx(0.2, abs=0.5 * MM)
    # a double block: two sheaves side by side on one axis, the cable in the second
    beside = sheave_for(a, rope, "BESIDE", shift=-0.06, rng=rng)
    rd = P.read_cable(tube.points, tube.radius, [beside, sheave])
    assert rd.ok and kinds(rd) == [("WRAP", "SHEAVE")]
    assert kinds(P.read_cable(tube.points, tube.radius, [beside])) == [("BEND", None)]


def test_read_rollers_that_touch_almost_touch_or_stand_clear():
    """Rollers under a straight Ø 24 cable (it may be 3 mm from where it would rest: a quarter of its radius):
    touching, 1 and 2.9 mm clear and 2 mm drawn into the cable are TOUCH contacts with that gap; 3.1 and 5 mm
    clear, and 3.1 mm into the cable, are none. A roller above the cable turns the other way than one below; the
    roller's axis given the other way round: the other side. 15° askew still turns, 30° does not."""
    rope = 0.012
    co = Course([0.0, 0.0, 1.0], X).line(2.3)
    tube = centreline_of(co, rope)
    rounds, want = [], []
    for k, gap in enumerate((0.0, 0.001, 0.0029, 0.0031, 0.005, -0.002, -0.0031)):
        x = 0.2 + 0.3 * k
        rounds.append(roller_at([x, 0.0, 1.0 - (0.06 + rope + gap)], Y, f"gap {gap}"))
        if -0.003 <= gap <= 0.003:
            want.append((f"gap {gap}", x, gap))
    rd = P.read_cable(tube.points, tube.radius, rounds)
    assert rd.ok and rd.deviation < 1e-6 and not shaped(rd)
    assert [c.key for c in rd.contacts] == [w[0] for w in want]
    for c, (_key, x, gap) in zip(rd.contacts, want):
        assert c.kind == "TOUCH" and c.side == 1 and c.full and c.wrap == 0.0
        assert c.gap == pytest.approx(gap, abs=0.02 * MM) and c.surface == pytest.approx(0.06, abs=1e-6)
        assert c.radius == pytest.approx(0.06 + rope + gap, abs=0.02 * MM)          # axis -> the cable's middle
        assert c.s == pytest.approx(x, abs=1e-3)
        assert np.linalg.norm(c.centre - [x, 0.0, 1.0 - (0.06 + rope + gap)]) < 1e-6
    # above / below, the axis either way, a guide at the side (its axis upright), askew
    def one(centre, axis, key="R"):
        return P.read_cable(tube.points, tube.radius, [roller_at(centre, axis, key)]).contacts

    below, above = one([1.0, 0.0, 1.0 - 0.072], Y), one([1.0, 0.0, 1.0 + 0.072], Y)
    assert [c.side for c in below] == [1] and [c.side for c in above] == [-1]
    assert [c.side for c in one([1.0, 0.0, 1.0 - 0.072], -Y)] == [-1]
    side_guide = one([1.0, 0.072, 1.0], Z)
    # the brief's side: sign(((p - c) x t) . axis) = ((0, -1, 0) x (1, 0, 0)) . (0, 0, 1) = +1
    assert [(c.kind, c.side) for c in side_guide] == [("TOUCH", 1)]
    assert [c.kind for c in one([1.0, 0.0, 1.0 - 0.072], rot(Z, math.radians(15.0)) @ Y)] == ["TOUCH"]
    assert one([1.0, 0.0, 1.0 - 0.072], rot(Z, math.radians(30.0)) @ Y) == []
    assert one([1.0, 0.0, 1.0 - 0.072], X) == []                        # a tube the cable runs along
    # the tolerance grows with the cable: Ø 200 may be 25 mm away
    co = Course([0.0, 0.0, 1.0], X).line(9.0)
    pts = co.points(0.1)
    rounds = [roller_at([1.0 + 2.0 * k, 0.0, 1.0 - (0.15 + 0.1 + gap)], Y, gap, radius=0.15, long=0.8)
              for k, gap in enumerate((0.0, 0.010, 0.024, 0.026))]
    assert [c.key for c in P.read_cable(pts, 0.1, rounds).contacts] == [0.0, 0.010, 0.024]
    assert [c.key for c in P.read_cable(pts, 0.1, rounds, touch_tol=0.002).contacts] == [0.0]


def test_read_a_cable_drawn_into_its_groove_or_off_it():
    """Drawn 2 mm into the groove or 2 mm off it (Ø 24: up to 3 mm counts): still a WRAP on the sheave, the path
    on the sheave's true seat, ``gap`` says how the cable was drawn and ``deviation`` honestly that the path is
    2 mm from the CAD cable. 4 mm off: not on the part any more - a bend in the air."""
    rope = 0.012
    rng = np.random.default_rng(31)
    co = Course([0.0, 0.0, 0.0], [1.0, 0.0, 0.3]).line(0.6).arc(Y, 0.2, 110.0).line(0.7)
    a = co.arcs()[0]
    tube = centreline_of(co, rope)
    for sink in (0.002, -0.002, 0.0029):
        rd = P.read_cable(tube.points, tube.radius, [sheave_for(a, rope, "S", sink=sink, rng=rng)])
        assert rd.ok and kinds(rd) == [("WRAP", "S")]
        c = rd.contacts[0]
        assert c.radius == pytest.approx(0.2 + sink, abs=0.05 * MM) and c.gap == pytest.approx(-sink, abs=0.15 * MM)
        assert rd.deviation == pytest.approx(abs(sink), abs=0.15 * MM)
        assert rd.deviation == pytest.approx(float(off_path(rd, tube.points).max()), abs=1e-7)
    for sink in (0.004, -0.004):
        rd = P.read_cable(tube.points, tube.radius, [sheave_for(a, rope, "S", sink=sink, rng=rng)])
        assert rd.ok and kinds(rd) == [("BEND", None)] and rd.deviation < 0.2 * MM
        assert rd.contacts[0].radius == pytest.approx(0.2, abs=0.3 * MM)


def test_read_backwards_the_same_part_twice_and_another_rope_beside():
    rope = 0.012
    rng = np.random.default_rng(4)
    co = Course([3.0, -2.0, 1.0], [1.0, 0.0, 0.2]).line(0.5).arc(Y, 0.25, 120.0).line(0.4).arc(-Y, 0.3, 75.0).line(0.3)
    a1, a2 = co.arcs()
    rounds = [sheave_for(a1, rope, "S1", rng=rng), sheave_for(a2, rope, "S2", flip=True, rng=rng)]   # both about +Y
    tube = centreline_of(co, rope)
    there = P.read_cable(tube.points, tube.radius, rounds)
    back = P.read_cable(tube.points[::-1], tube.radius, rounds)
    assert there.ok and back.ok
    assert [(c.key, c.side) for c in there.contacts] == [("S1", 1), ("S2", -1)]
    assert [(c.key, c.side) for c in back.contacts] == [("S2", 1), ("S1", -1)]          # other order, other sides
    for c, d in zip(there.contacts, back.contacts[::-1]):
        assert c.wrap == pytest.approx(d.wrap, abs=1e-4) and c.radius == pytest.approx(d.radius, abs=1e-6)
        assert c.s + d.s == pytest.approx(there.path.length, abs=2e-3)
    assert back.path.length == pytest.approx(there.path.length, abs=1e-5)
    assert np.linalg.norm(back.start - there.end) < 1e-9 and back.deviation == pytest.approx(there.deviation, abs=1e-5)

    # over a double sheave, round a return bend 40 mm to the side, back over its second groove
    co = Course([0.0, 0.02, 0.0], [1.0, 0.0, 0.5]).line(0.4).arc(Y, 0.2, 100.0).line(0.35)
    co.arc(np.cross(co.t, Y), 0.02, 180.0).line(0.35).arc(-Y, 0.2, 100.0).line(0.4)
    first, _, second = co.arcs()
    middle = 0.5 * (first["c"] + second["c"])
    pitch = float(np.linalg.norm(first["c"] - second["c"]))
    bottom = 0.2 - rope
    one = groove_outline(bottom, 1.08 * rope, bottom + 0.02, 0.0, 16, z0=-pitch / 2)
    two = groove_outline(bottom, 1.08 * rope, bottom + 0.02, 0.0, 16, z0=pitch / 2)
    outline = [(-0.05, 0.1), (-0.05, bottom + 0.02)] + one[2:-2] + two[2:-2] + [(0.05, bottom + 0.02), (0.05, 0.1)]
    double = P.Round("DOUBLE", middle, Y, *revolve(outline, 48, middle, Y, rng=rng))
    rd, _ = read(co, rope, [double])
    assert rd.ok and kinds(rd) == [("WRAP", "DOUBLE"), ("BEND", None), ("WRAP", "DOUBLE")]
    assert [c.side for c in rd.contacts] == [1, 1, -1]                  # the way back turns it the other way
    assert np.linalg.norm(rd.contacts[0].centre - first["c"]) < 1e-6 and np.linalg.norm(rd.contacts[2].centre - second["c"]) < 1e-6
    assert rd.contacts[1].radius == pytest.approx(0.02, abs=0.1 * MM) and deg(rd.contacts[1].wrap) == pytest.approx(180.0, abs=0.2)

    # two ropes side by side on a plain drum, touching each other: the drum carries the rope, not its neighbour
    def lay(y):
        return Course([0.0, y, 0.0], [1.0, 0.0, 0.4]).line(0.5).arc(Y, 0.2 + rope, 150.0).line(0.6)

    mine, other = lay(0.0), lay(2.0 * rope)
    centre = mine.arcs()[0]["c"]
    drum = P.Round("DRUM", centre, Y, *revolve(roller_outline(0.2, 0.3), 48, centre, Y, rng=rng))
    neighbour = P.Round("OTHER ROPE", other.arcs()[0]["c"], Y, *other.tube(rope))
    tube = centreline_of(mine, rope)
    for rounds in ([drum, neighbour], [neighbour, drum]):
        rd = P.read_cable(tube.points, tube.radius, rounds)
        assert rd.ok and kinds(rd) == [("WRAP", "DRUM")] and rd.contacts[0].surface == pytest.approx(0.2, abs=1e-6)


def test_read_a_bend_over_small_rollers_and_a_level_run():
    """A Ø 100 power cable through a 3 m bend that seven small rollers carry from inside, then level over three
    rollers (one 15°, one 30° askew): the bend shapes the path (a BEND, no part), the rollers only turn (TOUCH),
    all in the order the cable meets them."""
    rope = 0.05
    rng = np.random.default_rng(13)
    co = Course([0.0, 0.0, 2.0], X).line(1.5).arc(Y, 3.0, 60.0).line(4.0)
    a = co.arcs()[0]
    rounds, places = [], []
    for k in range(7):
        s = a["s0"] + 3.0 * math.radians(5.0 + 50.0 * k / 6.0)
        p, _t = co.at(s)
        rounds.append(roller_at(p + unit(a["c"] - p) * (rope + 0.08), Y, f"B{k}", radius=0.08, long=0.6, rng=rng))
        places.append(s)
    for k, tilt in enumerate((0.0, 15.0, 30.0)):
        s = a["s0"] + a["length"] + 1.0 + k
        p, t = co.at(s)
        down = unit(np.cross(t, Y))
        down = -down if down[2] > 0 else down
        rounds.append(roller_at(p + down * (rope + 0.08), rot(down, math.radians(tilt)) @ Y, f"L{k}", radius=0.08, long=0.6, rng=rng))
        places.append(s)
    order = list(rng.permutation(len(rounds)))
    rd, tube = read(co, rope, [rounds[i] for i in order])
    assert rd.ok
    assert [c.key for c in rd.contacts if c.kind == "TOUCH"] == ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "L0", "L1"]
    assert [c.kind for c in rd.contacts].count("BEND") == 1 and len(rd.contacts) == 10
    bend = shaped(rd)[0]
    assert bend.radius == pytest.approx(3.0, abs=2 * MM) and deg(bend.wrap) == pytest.approx(60.0, abs=0.05)
    assert [c.s for c in rd.contacts] == sorted(c.s for c in rd.contacts)
    for c in rd.contacts:
        if c.kind == "TOUCH":
            assert c.side == 1 and c.full and abs(c.gap) < 0.2 * MM and c.surface == pytest.approx(0.08, abs=1e-6)
            assert c.s == pytest.approx(places[int(c.key[1]) + (7 if c.key[0] == "L" else 0)], abs=0.02)
    assert co.off(rd.path.points).max() < 0.3 * MM and rd.deviation < 0.3 * MM


@pytest.mark.parametrize("between", [0.0, 0.5, 1.0, 2.0, 4.0, 8.0])
def test_read_an_s_curve_with_a_short_straight_between_its_sheaves(between):
    """Over one sheave and straight under the next, with 0 to 8 cable radii of straight between them (less than
    the points can show): two WRAPs in order on the right sides; without the parts two bends of the right size."""
    rope = 0.012
    rng = np.random.default_rng(14)
    co = Course([0.0, 0.0, 0.0], X).line(0.4).arc(Y, 0.25, 70.0)
    if between:
        co.line(between * rope)
    co.arc(-Y, 0.3, 80.0).line(0.4)
    a1, a2 = co.arcs()
    rd, tube = read(co, rope, [sheave_for(a2, rope, "S2", flip=True, rng=rng), sheave_for(a1, rope, "S1", rng=rng)])
    assert rd.ok and [(c.kind, c.key, c.side) for c in rd.contacts] == [("WRAP", "S1", 1), ("WRAP", "S2", -1)]
    # (nearly touching circles: a hair in a radius turns the straight between them by most of a degree)
    assert deg(rd.contacts[0].wrap) == pytest.approx(70.0, abs=0.8) and deg(rd.contacts[1].wrap) == pytest.approx(80.0, abs=0.8)
    assert co.off(rd.path.points).max() < 0.15 * MM and abs(rd.path.length - co.length) < 0.2 * MM
    bare = P.read_cable(tube.points, tube.radius, [])
    assert bare.ok and [c.kind for c in bare.contacts] == ["BEND", "BEND"]
    assert [c.radius for c in bare.contacts] == pytest.approx([0.25, 0.3], abs=1.5 * MM)
    assert co.off(bare.path.points).max() < 0.3 * MM and bare.deviation < 0.35 * MM


@pytest.mark.parametrize("turn", [0.5, 1.0, 3.0, 10.0, 30.0])
def test_read_a_roller_that_turns_the_cable_by_a_little(turn):
    """A Ø 120 roller the cable bends over by 0.5° to 30° (the arc is 0.6 to 38 mm long: mostly between two
    points of the centreline): a WRAP on the roller with that wrap."""
    rope = 0.012
    co = Course([0.0, 0.0, 0.0], X).line(1.0).arc(Y, 0.06 + rope, turn).line(1.0)
    a = co.arcs()[0]
    rd, _ = read(co, rope, [roller_at(a["c"], Y, "ROLLER")])
    assert rd.ok and kinds(rd) == [("WRAP", "ROLLER")]
    c = rd.contacts[0]
    assert c.side == 1 and c.radius == pytest.approx(0.072, abs=1e-6) and deg(c.wrap) == pytest.approx(turn, abs=0.02)
    assert co.off(rd.path.points).max() < 0.1 * MM and rd.deviation < 0.15 * MM


def test_read_a_cable_that_starts_on_a_drum_or_ends_on_a_sheave():
    rope = 0.012
    rng = np.random.default_rng(15)
    for wrap in (40.0, 300.0, 340.0):
        co = Course([0.0, 0.0, 0.0], X).arc(Y, 0.2 + rope, wrap).line(0.8)
        a = co.arcs()[0]
        drum = P.Round("DRUM", a["c"], Y, *revolve(roller_outline(0.2, 0.3), 48, a["c"], Y, rng=rng))
        rd = P.read_cable(co.points(rope), rope, [drum])
        assert rd.ok and rd.start_on_wheel and not rd.end_on_wheel and kinds(rd) == [("WRAP", "DRUM")]
        assert deg(rd.contacts[0].wrap) == pytest.approx(wrap, abs=0.02) and rd.contacts[0].full
        assert np.linalg.norm(rd.path.points[0] - co.start) < 0.05 * MM and rd.path.first[0] == 0
        assert rd.path.length == pytest.approx(co.length, abs=0.1 * MM)
    co = Course([0.0, 0.0, 0.0], X).arc(Y, 0.2 + rope, 355.0).line(0.8)     # nearly a whole turn: said plainly
    a = co.arcs()[0]
    drum = P.Round("DRUM", a["c"], Y, *revolve(roller_outline(0.2, 0.3), 48, a["c"], Y, rng=rng))
    rd = P.read_cable(co.points(rope), rope, [drum])
    assert not rd.ok and "contact 1" in rd.problem and "350" in rd.problem and kinds(rd) == [("WRAP", "DRUM")]
    assert rd.path.points.shape == (0, 3) and not rd.path.ok
    co = Course([0.0, 0.0, 0.0], X).line(1.0).arc(-Y, 0.3, 90.0)
    rd, _ = read(co, rope, [sheave_for(co.arcs()[0], rope, "END", rng=rng)])
    assert rd.ok and rd.end_on_wheel and not rd.start_on_wheel and kinds(rd) == [("WRAP", "END")]
    assert deg(rd.contacts[0].wrap) == pytest.approx(90.0, abs=0.3)
    assert len(rd.path.points) == 1 + int(rd.path.counts[0]) and np.linalg.norm(rd.path.points[-1] - co.p) < 0.5 * MM


def test_read_refuses_what_is_no_line_or_arc_and_what_is_no_cable():
    """A coil with a pitch, a wave, a bend that tightens bit by bit: refused in a sentence that says where; no
    points, numbers that are none, a cable of no thickness: refused too. Never an exception."""
    rope = 0.012
    th = np.linspace(0.0, 4.0 * math.pi, 600)
    s = np.linspace(0.0, 3.0, 500)
    heading = np.cumsum(0.3 * s) * (s[1] - s[0])
    odd = {
        "coil": np.c_[0.5 * np.cos(th), 0.5 * np.sin(th), 0.3 * th / (2.0 * math.pi)],
        "rope wound on a drum": np.c_[0.5 * np.cos(th), 0.5 * np.sin(th), 0.03 * th / (2.0 * math.pi)],
        "wave": np.c_[np.linspace(0, 6, 600), np.zeros(600), 0.4 * np.sin(np.linspace(0, 6, 600))],
        "tightening bend": np.c_[np.cumsum(np.cos(heading)) * (s[1] - s[0]), np.zeros(500),
                                 np.cumsum(np.sin(heading)) * (s[1] - s[0])],
    }
    for pts in odd.values():
        rd = P.read_cable(pts, rope, [])
        assert not rd.ok and "neither" in rd.problem and "straight" in rd.problem and " m " in rd.problem
        assert rd.contacts == [] and rd.path.points.shape == (0, 3) and rd.deviation == 0.0
    line = Course([0.0, 0.0, 0.0], X).line(1.0).points(rope)
    bad = line.copy()
    bad[7, 1] = float("nan")
    for pts, radius in (([], rope), (np.zeros((1, 3)), rope), (bad, rope), (line, 0.0), (line, -1.0), (line, float("nan")),
                        (np.zeros((5, 3)), rope), ("no points", rope)):
        rd = P.read_cable(pts, radius, [])
        assert not rd.ok and len(rd.problem) > 15 and rd.contacts == [] and not rd.path.ok
    straight = P.read_cable(line, rope, None)                           # (no parts at all: a plain straight cable)
    assert straight.ok and straight.contacts == [] and straight.path.length == pytest.approx(1.0, abs=1e-9)
    assert len(straight.path.points) == 2 and straight.deviation < 1e-9


def test_reading_5000_points_past_700_rollers_is_not_slow():
    """A 190 m roller highway: 5,000 centreline points, 700 round parts, 6 bends. Nothing in it grows with
    points x parts so that it hurts (measured 2.3 s on the web machine; the bound is loose)."""
    co = Course([0.0, 0.0, 2.0], X).line(20.0)
    for k in range(6):
        co.arc(Y if k % 2 == 0 else -Y, 3.0, 40.0).line(30.0)
    step = co.length / 5000.0
    pts = co.points(step)
    rope = step
    rounds = []
    for k, s in enumerate(np.linspace(1.0, co.length - 1.0, 700)):
        p, t = co.at(s)
        down = unit(np.cross(t, Y))
        down = -down if down[2] > 0 else down
        rounds.append(roller_at(p + down * (rope + 0.08), Y, k, radius=0.08, long=0.6))
    t0 = time.perf_counter()
    rd = P.read_cable(pts, rope, rounds)
    took = time.perf_counter() - t0
    assert rd.ok and len(pts) == 5001
    found = [c.kind for c in rd.contacts]
    assert found.count("BEND") == 6 and found.count("TOUCH") == 700 and found.count("WRAP") == 0
    assert [c.key for c in rd.contacts if c.kind == "TOUCH"] == list(range(700))
    assert rd.deviation < 0.1 * MM and rd.path.length == pytest.approx(co.length, abs=1 * MM)
    assert took < 30.0


# =====================================================================================================================
# the test model, read as the app reads it (the importer's meshes and round axes)
# =====================================================================================================================

class Model:
    """tests/data/test_paths_a.step through the importer: every part's mesh where it stands, in metres, and the
    round faces' axes the importer found."""

    def __init__(self, folder, quality="normal"):
        path = os.path.join(HERE, "data", "test_paths_a.step")
        self.info = step_reader.read_step(path, str(folder), quality)
        self.arrays = np.load(os.path.join(str(folder), "meshes.npz"))
        self.nodes = self.info["nodes"]
        self.world = []
        for node in self.nodes:
            m = np.eye(4) if node["matrix"] is None else np.array(node["matrix"], dtype=float)
            self.world.append(m if node["parent"] < 0 else self.world[node["parent"]] @ m)
        self.parts = [i for i, node in enumerate(self.nodes) if node["kind"] == "part"]

    def mesh(self, i):
        mid = self.nodes[i]["mesh"]
        m = self.world[i]
        return (self.arrays[f"p{mid}"].astype(np.float64) @ m[:3, :3].T + m[:3, 3],
                self.arrays[f"t{mid}"].reshape(-1, 3).astype(np.int64))

    def part(self, uid):
        (i,) = [k for k in self.parts if self.nodes[k]["uid"] == uid]
        return i

    def rounds(self, leave_out):
        out = []
        for i in self.parts:
            if self.nodes[i]["uid"] == leave_out:
                continue
            verts, tris = self.mesh(i)
            m = self.world[i]
            for ox, oy, oz, dx, dy, dz, _r in self.info["meshes"][self.nodes[i]["mesh"]]["axes"]:
                out.append(P.Round(self.nodes[i]["uid"], m[:3, :3] @ (ox, oy, oz) + m[:3, 3], m[:3, :3] @ (dx, dy, dz), verts, tris))
        return out


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    return Model(tmp_path_factory.mktemp("paths_independent"))


def test_the_test_models_round_parts(model):
    """Drum, sheaves and V rollers are round all the way (they may turn); the chute is not; and each one's seat
    for the Ø 24 rope, read from its mesh, is the maker's number within 0.1 mm."""
    n = maker.NUMBERS
    rope = n["rope_radius"] * MM
    for name, c in n["contacts"].items():
        verts, tris = model.mesh(model.part(c["uid"]))
        centre, axis = np.array(c["axis_point"]) * MM, np.array(c["axis_direction"])
        assert P.is_round(verts, centre, axis) == c["turns"], name
        place, radius = P.seat(verts, tris, centre, axis, 0.0, rope)
        assert abs(place) < 0.1 * MM and radius == pytest.approx(c["seat_radius"] * MM, abs=0.1 * MM), name
        assert P.surface_radius(verts, tris, centre, axis, 0.0, 1 * MM) == pytest.approx(c["surface_radius"] * MM, abs=0.15 * MM)
    for r in n["rollers"]:
        verts, tris = model.mesh(model.part(r["uid"]))
        centre, axis = np.array(r["axis_point"]) * MM, np.array(r["axis_direction"])
        assert P.is_round(verts, centre, axis)
        place, radius = P.seat(verts, tris, centre, axis, 0.0, rope)
        assert radius == pytest.approx(r["seat_radius"] * MM, abs=0.02 * MM)
        assert abs(place) <= rope + 1e-9            # (a plain roller: anywhere in reach is as low as anywhere else)


def test_the_test_models_wire_rope_read_from_cad(model):
    """Its WIRE ROPE read against every round axis of every other part (pins, bores, bearing blocks and all):
    drum, sheave 1, sheave 2 - wraps on the parts, with the maker's radii, wraps and sides -, the two V rollers
    it only rests on, the chute (a wrap on a part that is not round: it does not turn); it starts on the drum.

    The rope's middle is read here with ``flex_fit.tube_centreline`` in one go: ``paths.centreline`` reads a
    cable this long (585 radii) in pieces and today loses part of it where the rope turns more than a quarter
    turn after a seam (the review has the numbers)."""
    n = maker.NUMBERS
    uid = n["rope"]["uid"]
    verts, tris = model.mesh(model.part(uid))
    tube = flex_fit.tube_centreline(verts, tris, int(round(n["rope"]["length"] / n["rope_radius"])) + 1)
    assert tube.ok and tube.radius == pytest.approx(0.012, abs=0.05 * MM)
    rounds = model.rounds(leave_out=uid)
    assert len(rounds) >= 16
    rd = P.read_cable(tube.points, tube.radius, rounds)
    assert rd.ok, rd.problem
    names = ["WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "V ROLLER 1", "V ROLLER 2", "CHUTE"]
    want = [n["contacts"][k]["uid"] if k in n["contacts"] else maker.UID[k] for k in names]
    assert [c.key for c in rd.contacts] == want
    assert [c.kind for c in rd.contacts] == ["WRAP", "WRAP", "WRAP", "TOUCH", "TOUCH", "WRAP"]
    assert rd.start_on_wheel and not rd.end_on_wheel
    for c, name in zip(rd.contacts, names):
        if name in n["contacts"]:
            m = n["contacts"][name]
            assert c.radius == pytest.approx(m["seat_radius"] * MM, abs=0.1 * MM), name
            assert c.surface == pytest.approx(m["surface_radius"] * MM, abs=0.1 * MM), name
            assert c.side * float(c.axis @ np.array(m["axis_direction"])) == pytest.approx(m["side"], abs=1e-6), name
            assert deg(c.wrap) == pytest.approx(m["wrap"], abs=0.25), name      # (the drum's start: a point's width)
            assert np.linalg.norm(c.centre - np.array(m["axis_point"]) * MM) < 0.05 * MM, name
            assert c.full == m["turns"], name
            assert abs(c.gap) < 0.5 * MM, name
        else:
            m = n["rollers"][int(name[-1]) - 1]
            assert c.radius == pytest.approx(m["seat_radius"] * MM, abs=0.1 * MM) and c.full and c.wrap == 0.0
            assert c.surface == pytest.approx(m["surface_radius"] * MM, abs=0.02 * MM) and abs(c.gap) < 0.1 * MM
            # the brief's side with the maker's own points: the rope's middle, the roller's axis, the rope going +X
            mid, foot, axis = np.array(m["rope_middle"]) * MM, np.array(m["axis_point"]) * MM, np.array(m["axis_direction"])
            assert c.side * float(c.axis @ axis) == pytest.approx(np.sign(np.cross(mid - foot, X) @ axis), abs=1e-6)
    # sheave 1 and 2 turn opposite ways, both about +Y in the model
    assert rd.contacts[1].side * rd.contacts[1].axis[1] > 0 > rd.contacts[2].side * rd.contacts[2].axis[1]
    assert rd.deviation < 0.5 * MM                                              # the brief: within 0.5 mm
    assert rd.path.length == pytest.approx(n["rope"]["length"] * MM, abs=1.5 * MM)
    route = maker.centreline(0.0, 0.5) * MM                                     # the maker's own points, 0.5 mm apart
    far = max(float(np.linalg.norm(route - p, axis=1).min()) for p in rd.path.points)
    assert far < 1.0 * MM                           # (0.7 mm at the rope's start on the drum: the tube's end)
    wheels = [P.Wheel(c.centre, c.axis, c.radius, c.side) for c in shaped(rd)]
    m = measure(rd.path, wheels, rd.start, rd.end, on0=True)
    assert m["kink"] < 0.1 and m["side"] and m["forward"] and m["layout"] and m["radius"] < 1e-9
    best, radius = P.tightest(wheels, rd.path.wrap)
    assert best == 2 and radius == pytest.approx(0.18, abs=0.1 * MM)            # sheave 2 bends the rope tightest


def test_a_short_cables_centreline_is_the_middle_of_its_tube():
    """``centreline`` on a tube up to 200 radii long (read in one go): a point every cable radius from end to
    end, on the true route within 1.5 % of the radius whatever the facets."""
    for rope, sides in ((0.012, 12), (0.05, 24), (0.25, 48)):
        co = (Course([5.0, 6.0, 7.0], [0.3, 1.0, 0.2]).line(30 * rope).arc(Z, 20 * rope, 200.0).line(20 * rope)
              .arc([1.0, 0.0, 0.0], 25 * rope, 60.0).line(30 * rope))
        v, t = co.tube(rope, sides=sides)
        tube = P.centreline(v, t)
        assert tube.ok and tube.radius == pytest.approx(rope, rel=0.02)
        assert tube.length == pytest.approx(co.length, abs=0.3 * rope)
        assert len(tube.points) == int(round(tube.length / tube.radius)) + 1
        ends = sorted([co.start, co.p], key=lambda p: tuple(p))                 # end 0: the smaller x
        assert np.linalg.norm(tube.points[0] - ends[0]) < 0.05 * rope and np.linalg.norm(tube.points[-1] - ends[1]) < 0.05 * rope
        assert co.off(tube.points).max() < 0.015 * rope
        spacing = np.linalg.norm(np.diff(tube.points, axis=0), axis=1)
        assert spacing.max() < 1.1 * rope and spacing.min() > 0.9 * rope
