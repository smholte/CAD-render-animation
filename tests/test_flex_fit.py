"""Task 0058: a hose's centreline read from its mesh (core/flex_fit.py) and the two flex test models.

The synthetic tubes are made here in NumPy: a ring of ``sides`` corners swept along a path that is known exactly
(straight pieces and arcs, a helix), so the "true" centreline, length, radius and ends are known. The corners lie on
the true surface, so the radius to compare with is the one through the corners.
"""

import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import flex_fit
from fresing_render.core.flex_fit import tube_centreline

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")
HOSES_B = os.path.join(HERE, "data", "test_flex_hoses_b.step")
CHAINS_A = os.path.join(HERE, "data", "test_flex_chains_a.step")


# ---------------------------------------------------------------------------------------------------------
# paths known exactly: a list of points close together (0.05 of the radius apart or less)
# ---------------------------------------------------------------------------------------------------------

def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


class Path:
    """Straight pieces and arcs joined smoothly; ``points`` is the exact curve sampled every ``fine``."""

    def __init__(self, start=(0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0), fine=0.25):
        self.p = np.asarray(start, dtype=float)
        self.d = _unit(direction)
        self.fine = fine
        self.pts = [self.p.copy()]
        self.length = 0.0

    def straight(self, length):
        k = max(int(math.ceil(length / self.fine)), 1)
        for i in range(1, k + 1):
            self.pts.append(self.p + self.d * (length * i / k))
        self.p = self.p + self.d * length
        self.length += length
        return self

    def arc(self, radius, angle_deg, towards):
        """Turn by ``angle_deg`` on a circle of ``radius``, bending towards the direction ``towards``."""
        side = np.asarray(towards, dtype=float)
        side = _unit(side - self.d * (side @ self.d))
        centre = self.p + side * radius
        ang = math.radians(angle_deg)
        k = max(int(math.ceil(radius * ang / self.fine)), 2)
        for i in range(1, k + 1):
            a = ang * i / k
            self.pts.append(centre - side * radius * math.cos(a) + self.d * radius * math.sin(a))
        self.p = centre - side * radius * math.cos(ang) + self.d * radius * math.sin(ang)
        self.d = _unit(self.d * math.cos(ang) + side * math.sin(ang))
        self.length += radius * ang
        return self

    @property
    def points(self):
        return np.array(self.pts)


def straight_path(length=300.0):
    return Path((5.0, -20.0, 30.0), (1.0, 2.0, 0.5)).straight(length).points


def quarter_arc(radius=100.0):
    return Path((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)).arc(radius, 90.0, (0.0, 0.0, 1.0)).points


def s_curve():
    """Straight 40, a quarter turn R 80 upwards, straight 30, a quarter turn R 60 sideways, straight 40."""
    return (Path((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)).straight(40.0).arc(80.0, 90.0, (0.0, 0.0, 1.0)).straight(30.0)
            .arc(60.0, 90.0, (0.0, 1.0, 0.0)).straight(40.0).points)


def helix(radius=60.0, pitch=80.0, turns=1.5, fine=0.25):
    c = pitch / (2.0 * math.pi)
    k = int(math.ceil(turns * 2.0 * math.pi * math.hypot(radius, c) / fine))
    a = np.linspace(0.0, turns * 2.0 * math.pi, k + 1)
    return np.stack([radius * np.cos(a), radius * np.sin(a), c * a], axis=1)


PATHS = {"straight": straight_path, "arc": quarter_arc, "s-curve": s_curve, "helix": helix}


def path_length(pts):
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def _stations(pts, step):
    """Points on the path about ``step`` apart (ends included) with their tangents and a frame that does not twist."""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    k = max(int(round(s[-1] / step)), 1)
    at = np.linspace(0.0, s[-1], k + 1)
    idx = np.clip(np.searchsorted(s, at), 0, len(pts) - 1)       # stations ON the exact curve
    idx[0], idx[-1] = 0, len(pts) - 1
    idx = np.unique(idx)
    c = pts[idx]
    tan = np.gradient(pts, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    tan = tan[idx]
    u = np.cross(tan[0], [0.3, -0.5, 0.8])
    u /= np.linalg.norm(u)
    us = [u]
    for i in range(1, len(c)):
        u = us[-1] - tan[i] * (us[-1] @ tan[i])
        us.append(u / np.linalg.norm(u))
    us = np.array(us)
    return c, tan, us, np.cross(tan, us)


def _stitch(ring_a, ang_a, ring_b, ang_b):
    """Triangles between two rings of vertex indices whose corners lie at the given angles (ascending from 0)."""
    na, nb = len(ring_a), len(ring_b)
    i = j = 0
    out = []
    while i < na or j < nb:
        ta = (ang_a[i + 1] if i + 1 < na else 2 * math.pi + ang_a[0]) if i < na else math.inf
        tb = (ang_b[j + 1] if j + 1 < nb else 2 * math.pi + ang_b[0]) if j < nb else math.inf
        if ta <= tb:
            out.append((ring_a[i % na], ring_a[(i + 1) % na], ring_b[j % nb]))
            i += 1
        else:
            out.append((ring_b[j % nb], ring_a[i % na], ring_b[(j + 1) % nb]))
            j += 1
    return out


def make_tube(pts, radius, sides, step=None, bore=0.0, caps="fan", seams=False, ferrule=None, twist=0.0,
              facing="out"):
    """A tube mesh along the exact path ``pts``.

    ``bore``: inner radius (0 = solid). ``caps``: "fan" (no vertex in the middle, as OpenCascade meshes a flat
    face), "centre" (a vertex in the middle) – for a solid tube. ``seams``: repeat the vertices along a seam down
    the tube and round the end faces, as the importer does. ``ferrule`` = (length, corner radius): a hexagon
    round end 0 (the path must start straight). ``twist``: the facets turn by this many radians per station.
    ``facing``: "out" = every triangle faces out of the material (as the importer's do), "mixed" = any way."""
    step = step or radius * 0.2
    c, tan, u, w = _stations(pts, step)
    n = len(c)
    ang = np.arange(sides) * 2 * math.pi / sides
    verts, tris, want = [], [], []          # want: per triangle (point it faces away from) or (None, direction)

    def emit(new, away=None, along=None):
        tris.extend(new)
        want.extend([(away, along)] * len(new))

    def ring(i, r, angles, shift=0.0):
        base = len(verts)
        for a in angles:
            verts.append(c[i] + r * (math.cos(a + shift) * u[i] + math.sin(a + shift) * w[i]))
        return list(range(base, base + len(angles)))

    def skin(r, first, inside):
        rings = []
        for i in range(first, n):
            idx = ring(i, r, ang, twist * i)
            if seams:                                   # the seam: the first corner again, as its own vertex
                verts.append(verts[idx[0]].copy())
                rings.append((idx, idx[1:] + [len(verts) - 1]))
            else:
                rings.append((idx, idx[1:] + idx[:1]))
        for i, ((a0, a1), (b0, b1)) in enumerate(zip(rings[:-1], rings[1:])):
            mid = 0.5 * (c[first + i] + c[first + i + 1])
            new = []
            for k in range(sides):
                new += [(a0[k], a1[k], b0[k]), (a1[k], b1[k], b0[k])]
            if inside:                                  # the bore's faces look at the centreline
                emit(new, along=None, away=("towards", mid))
            else:
                emit(new, away=("from", mid))
        return [r[0] for r in rings]

    def face(direction, outer, outer_ang, inner=None, inner_ang=None):
        if seams:                                       # an end face has its own copies of the rim
            base = len(verts)
            verts.extend(verts[i].copy() for i in outer)
            outer = list(range(base, base + len(outer)))
            if inner is not None:
                base = len(verts)
                verts.extend(verts[i].copy() for i in inner)
                inner = list(range(base, base + len(inner)))
        if inner is not None:
            emit(_stitch(outer, outer_ang, inner, inner_ang), along=direction)
        elif caps == "centre":
            verts.append(np.mean([verts[i] for i in outer], axis=0))
            mid = len(verts) - 1
            emit([(outer[k], outer[(k + 1) % len(outer)], mid) for k in range(len(outer))], along=direction)
        else:
            emit([(outer[0], outer[k], outer[k + 1]) for k in range(1, len(outer) - 1)], along=direction)

    first = 0
    hexa = None
    if ferrule:
        length, corner = ferrule
        first = int(np.argmin(np.abs(np.linalg.norm(c - c[0], axis=1) - length)))
        hang = np.arange(6) * math.pi / 3
        h0, h1 = ring(0, corner, hang), ring(first, corner, hang)
        new = []
        for k in range(6):
            new += [(h0[k], h0[(k + 1) % 6], h1[k]), (h0[(k + 1) % 6], h1[(k + 1) % 6], h1[k])]
        emit(new, away=("from", 0.5 * (c[0] + c[first])))
        hexa = (h0, h1, hang)
    out = skin(radius, first, False)
    if hexa:
        face(tan[first], hexa[1], hexa[2], out[0], ang)     # the shoulder between hexagon and hose
    if bore > 0:
        inn = skin(bore, 0, True)
        face(-tan[0], hexa[0] if hexa else out[0], hexa[2] if hexa else ang, inn[0], ang)
        face(tan[-1], out[-1], ang, inn[-1], ang)
    else:
        face(-tan[0], hexa[0] if hexa else out[0], hexa[2] if hexa else ang)
        face(tan[-1], out[-1], ang)
    verts = np.array(verts)
    tris = np.array(tris, dtype=np.int64)
    normal = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
    middle = verts[tris].mean(axis=1)
    for i, (away, along) in enumerate(want):
        if along is not None:
            ref = along
        else:
            ref = (middle[i] - away[1]) * (1.0 if away[0] == "from" else -1.0)
        if float(normal[i] @ ref) < 0:
            tris[i] = tris[i, ::-1]
    if facing == "mixed":
        turn = np.random.default_rng(5).random(len(tris)) < 0.5
        tris[turn] = tris[turn, ::-1]
    return verts, tris




def to_curve(points, curve):
    """The biggest distance from the points to the curve (given as points close together)."""
    best = 0.0
    seg = curve[1:] - curve[:-1]
    l2 = (seg * seg).sum(axis=1)
    for p in points:
        d = p - curve[:-1]
        f = np.clip((d * seg).sum(axis=1) / l2, 0.0, 1.0)
        r = d - f[:, None] * seg
        best = max(best, float(np.sqrt((r * r).sum(axis=1).min())))
    return best


def angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(_unit(a), _unit(b)))))))


def oriented(pts):
    """The exact path with end 0 first by the rule of flex_fit: the end with the smaller x (then y, then z)."""
    a, b = pts[0], pts[-1]
    for i in range(3):
        if abs(a[i] - b[i]) > 1e-9:
            return pts if a[i] < b[i] else pts[::-1]
    return pts


def check(tube, pts, radius, centre_tol, end_tol, dir_tol=1.0, length_tol=0.005, radius_tol=0.02):
    assert tube.ok, tube.problem
    pts = oriented(pts)
    assert tube.points.shape == (65, 3)
    gaps = np.linalg.norm(np.diff(tube.points, axis=0), axis=1)
    assert gaps.max() - gaps.min() < 0.02 * gaps.mean(), "the points are equally spaced"
    assert to_curve(tube.points, pts) < centre_tol * radius
    assert to_curve(pts[::40], tube.points) < centre_tol * radius + 0.05 * gaps.mean() ** 2 / radius
    assert abs(tube.length - path_length(pts)) < length_tol * path_length(pts)
    assert abs(tube.radius - radius) < radius_tol * radius
    assert np.linalg.norm(tube.points[0] - pts[0]) < end_tol
    assert np.linalg.norm(tube.points[-1] - pts[-1]) < end_tol
    assert angle(tube.t0, pts[1] - pts[0]) < dir_tol
    assert angle(tube.t1, pts[-1] - pts[-2]) < dir_tol
    assert abs(np.linalg.norm(tube.t0) - 1) < 1e-9 and abs(np.linalg.norm(tube.t1) - 1) < 1e-9


# ---------------------------------------------------------------------------------------------------------
# accuracy on tubes known exactly (Ø20: radius 10, so 0.1 mm = 1 % of the radius)
# ---------------------------------------------------------------------------------------------------------

R = 10.0
KINDS = {
    "solid": {},
    "solid, seams, centre caps": {"seams": True, "caps": "centre"},
    "bore": {"bore": 6.0},
    "bore, seams": {"bore": 5.0, "seams": True},
}


@pytest.mark.parametrize("path", sorted(PATHS))
@pytest.mark.parametrize("sides", [8, 12, 32])
@pytest.mark.parametrize("kind", sorted(KINDS))
def test_centreline_of_a_swept_tube(path, sides, kind):
    pts = PATHS[path]()
    verts, tris = make_tube(pts, R, sides, **KINDS[kind])
    coarse = sides == 8
    check(tube_centreline(verts, tris), pts, R, centre_tol=0.05 if coarse else 0.02,
          end_tol=0.02 * R if coarse else 0.1)


@pytest.mark.parametrize("path", ["straight", "s-curve"])
@pytest.mark.parametrize("sides", [8, 32])
@pytest.mark.parametrize("bore", [0.0, 6.0])
def test_hex_ferrule_on_an_end(path, sides, bore):
    """A hexagon 25 long and 28 across its corners fused on end 0: the end point is the middle of the hexagon's
    end face, the radius is still the hose's."""
    pts = PATHS[path]()
    verts, tris = make_tube(pts, R, sides, bore=bore, ferrule=(25.0, 14.0), seams=True)
    check(tube_centreline(verts, tris), pts, R, centre_tol=0.05 if sides == 8 else 0.02, end_tol=0.1)


@pytest.mark.parametrize("sides", [8, 12, 32])
def test_facets_that_wind_round_the_tube(sides):
    """The corners turn 21° from ring to ring (a mesh that is not in neat rows): the centre must not follow."""
    pts = s_curve()
    verts, tris = make_tube(pts, R, sides, twist=0.37)
    check(tube_centreline(verts, tris), pts, R, centre_tol=0.05 if sides == 8 else 0.02, end_tol=0.1)


@pytest.mark.parametrize("bore", [6.0, 9.0])
def test_bore_with_triangles_facing_any_way(bore):
    """Without the importer's "every triangle faces out of the material" the bore cannot be told from the
    outside by its facing: the fit then uses both walls. Straight ends stay exact; an end that is bent right up
    to its face (the helix) is then found to 3 % of the radius instead of 1 %."""
    for path, tol in (("s-curve", 0.1), ("helix", 0.03 * R)):
        pts = PATHS[path]()
        verts, tris = make_tube(pts, R, 16, bore=bore, facing="mixed")
        check(tube_centreline(verts, tris), pts, R, centre_tol=0.03, end_tol=tol)


def test_any_unit_and_far_from_the_origin():
    """The importer's meshes are in metres and float32, a hose may lie 20 m from the origin."""
    pts = s_curve() * 0.0005 + np.array([20.0, -7.5, 3.25])                # a Ø10 mm cable, in metres
    verts, tris = make_tube(pts, 0.005, 16)
    tube = tube_centreline(verts.astype(np.float32), tris.astype(np.int32))
    assert tube.ok, tube.problem
    exact = oriented(pts)
    assert abs(tube.length - path_length(pts)) < 0.005 * path_length(pts)
    assert abs(tube.radius - 0.005) < 0.02 * 0.005
    assert to_curve(tube.points, exact) < 0.02 * 0.005
    assert np.linalg.norm(tube.points[0] - exact[0]) < 2e-5 and np.linalg.norm(tube.points[-1] - exact[-1]) < 2e-5
    assert angle(tube.t0, exact[1] - exact[0]) < 1.0 and angle(tube.t1, exact[-1] - exact[-2]) < 1.0


def test_number_of_points():
    verts, tris = make_tube(s_curve(), R, 12)
    for n in (2, 33, 200):
        tube = tube_centreline(verts, tris, n=n)
        assert tube.ok and tube.points.shape == (n, 3)
        assert abs(tube.length - path_length(s_curve())) < 0.005 * path_length(s_curve())


def test_same_answer_whatever_the_order_of_the_mesh():
    """End 0 is the end with the smaller x (then y, then z); vertices and triangles shuffled, triangles started
    at another corner, seam vertices repeated or not: the same tube."""
    pts = s_curve()
    verts, tris = make_tube(pts, R, 12, bore=6.0)
    first = tube_centreline(verts, tris)
    assert first.ok and first.points[0][0] < first.points[-1][0]
    assert np.linalg.norm(first.points[0] - pts[0]) < 0.1
    rng = np.random.default_rng(11)
    for _ in range(3):
        order = rng.permutation(len(verts))
        back = np.empty(len(verts), dtype=np.int64)
        back[order] = np.arange(len(verts))
        t2 = back[tris][rng.permutation(len(tris))]
        t2 = np.roll(t2, int(rng.integers(3)), axis=1)
        again = tube_centreline(verts[order], t2)
        assert again.ok
        assert np.abs(again.points - first.points).max() < 1e-7
        assert abs(again.length - first.length) < 1e-7 and abs(again.radius - first.radius) < 1e-7
        assert np.abs(again.t0 - first.t0).max() < 1e-7 and np.abs(again.t1 - first.t1).max() < 1e-7
    seamed = tube_centreline(*make_tube(pts, R, 12, bore=6.0, seams=True))
    assert np.abs(seamed.points - first.points).max() < 1e-6
    # the same tube turned end for end in space: end 0 is again the one with the smaller x
    mirror = verts * np.array([-1.0, 1.0, 1.0])
    turned = tube_centreline(mirror, tris[:, ::-1])
    assert turned.ok and turned.points[0][0] < turned.points[-1][0]
    assert np.linalg.norm(turned.points[-1] - pts[0] * np.array([-1.0, 1.0, 1.0])) < 0.1


def test_distances_along_the_surface_match_dijkstra():
    import heapq

    verts, tris = make_tube(s_curve(), R, 8, step=6.0)
    p, t, _size = flex_fit._weld(verts, tris)
    _edges, table, closed = flex_fit._edges(p, t)
    assert closed
    start, nbr, w = table
    best = np.full(len(p), np.inf)
    best[3] = 0.0
    heap = [(0.0, 3)]
    while heap:
        d, i = heapq.heappop(heap)
        if d > best[i]:
            continue
        for e in range(start[i], start[i + 1]):
            if d + w[e] < best[nbr[e]]:
                best[nbr[e]] = d + w[e]
                heapq.heappush(heap, (best[nbr[e]], int(nbr[e])))
    assert np.allclose(flex_fit._distances(table, 3, len(p)), best, rtol=0, atol=1e-9)


def test_fast_enough_for_a_fine_hose():
    """A hose of 20,000 triangles within 0.3 s (the best of three; measured 0.10 s in a web session, 4 cores)."""
    pts = Path((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)).straight(60).arc(120, 80, (0, 0, 1)).straight(150).arc(
        90, 100, (0, 1, 0)).straight(60).points
    verts, tris = make_tube(pts, R, 32, step=1.9, seams=True)
    assert 19000 < len(tris) < 22000
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        tube = tube_centreline(verts, tris)
        best = min(best, time.perf_counter() - t0)
    assert tube.ok
    print(f"tube_centreline: {len(tris)} triangles in {best * 1000:.0f} ms")
    assert best < 0.3


# ---------------------------------------------------------------------------------------------------------
# not a hose
# ---------------------------------------------------------------------------------------------------------

def box(dx, dy, dz, cuts=1):
    """A box as triangles; ``cuts`` > 1 divides every face."""
    verts, tris = [], []
    for axis in range(3):
        for side in (0.0, 1.0):
            u, v = [a for a in range(3) if a != axis]
            base = len(verts)
            for i in range(cuts + 1):
                for j in range(cuts + 1):
                    q = [0.0, 0.0, 0.0]
                    q[axis], q[u], q[v] = side, i / cuts, j / cuts
                    verts.append([q[0] * dx, q[1] * dy, q[2] * dz])
            for i in range(cuts):
                for j in range(cuts):
                    a = base + i * (cuts + 1) + j
                    b, c, d = a + 1, a + cuts + 1, a + cuts + 2
                    tris += [(a, c, b), (b, c, d)] if bool(side) != (axis == 1) else [(a, b, c), (b, d, c)]
    return np.array(verts), np.array(tris)


def lathe(zs, rs, sides=24):
    """A turned shape about the z axis: rings of radius rs at the heights zs (radius 0 = a point)."""
    verts, tris, rings = [], [], []
    for z, r in zip(zs, rs):
        base = len(verts)
        if r <= 0:
            verts.append([0.0, 0.0, z])
            rings.append([base] * sides)
        else:
            verts += [[r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides), z]
                      for k in range(sides)]
            rings.append(list(range(base, base + sides)))
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            k1 = (k + 1) % sides
            tris += [(a[k], a[k1], b[k]), (a[k1], b[k1], b[k])]
    tris = [t for t in tris if len(set(t)) == 3]
    return np.array(verts), np.array(tris)


def torus(big=100.0, small=10.0, around=64, sides=16):
    verts, tris = [], []
    for i in range(around):
        a = 2 * math.pi * i / around
        for k in range(sides):
            b = 2 * math.pi * k / sides
            verts.append([(big + small * math.cos(b)) * math.cos(a), (big + small * math.cos(b)) * math.sin(a),
                          small * math.sin(b)])
    for i in range(around):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            c, d = ((i + 1) % around) * sides + k, ((i + 1) % around) * sides + (k + 1) % sides
            tris += [(a, b, c), (b, d, c)]
    return np.array(verts), np.array(tris)


def sphere():
    angles = np.linspace(0.0, math.pi, 17)
    return lathe(-50.0 * np.cos(angles), np.where(np.sin(angles) < 1e-9, 0.0, 50.0 * np.sin(angles)))


NOT_HOSES = {
    "box": lambda: box(120.0, 80.0, 60.0, cuts=4),
    "box of 12 triangles": lambda: box(120.0, 80.0, 60.0),
    "plate": lambda: box(1000.0, 600.0, 20.0, cuts=6),
    "ring": torus,
    "thin ring": lambda: torus(300.0, 6.0, 96, 12),
    "ball": sphere,
    "short tube": lambda: make_tube(straight_path(50.0), R, 16),                 # 2.5 diameters
    "washer": lambda: make_tube(straight_path(4.0), R, 24, bore=5.0, step=2.0),
    "cone": lambda: lathe(np.linspace(0.0, 300.0, 31), np.linspace(4.0, 30.0, 31)),
    "stepped shaft": lambda: lathe([0.0, 150.0, 150.0, 300.0], [10.0, 10.0, 22.0, 22.0]),
    "square beam": lambda: box(1500.0, 100.0, 100.0, cuts=8),
    "flat bar": lambda: box(1000.0, 50.0, 6.0, cuts=10),
}


@pytest.mark.parametrize("name", sorted(NOT_HOSES))
def test_not_a_hose(name):
    verts, tris = NOT_HOSES[name]()
    tube = tube_centreline(verts, tris)
    assert not tube.ok, (name, tube.length, tube.radius)
    assert tube.problem.startswith("The part") and tube.problem.endswith(".") and len(tube.problem) < 120
    assert tube.points.shape == (0, 3) and tube.length == 0.0 and tube.radius == 0.0
    if "ring" in name:
        assert "ring" in tube.problem
    if name in ("box", "box of 12 triangles", "plate", "ball", "short tube", "washer"):
        assert "long and thin" in tube.problem
    if name in ("cone", "stepped shaft"):
        assert "thickness" in tube.problem
    if name in ("square beam", "flat bar"):
        assert "round" in tube.problem


# ---- the independent review's findings (round 2) ----

def prism(profile, length, steps=40):
    """A bar with the cross-section ``profile`` (corners, counter-clockwise seen from +x) along x."""
    prof = np.asarray(profile, dtype=float)
    k = len(prof)
    verts = np.concatenate([np.c_[np.full(k, x), prof] for x in np.linspace(0.0, length, steps + 1)])
    tris = []
    for i in range(steps):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            tris += [(a, b, a + k), (b, b + k, a + k)]
    tris += [(0, j + 1, j) for j in range(1, k - 1)]
    tris += [(steps * k, steps * k + j, steps * k + j + 1) for j in range(1, k - 1)]
    return verts, np.array(tris)


def any_way(tris, seed=3):
    """The same triangles, about half of them turned over (a mesh whose faces look any way)."""
    out = np.array(tris)
    turn = np.random.default_rng(seed).random(len(out)) < 0.5
    out[turn] = out[turn, ::-1]
    return out


def turned(verts, seed):
    """The mesh turned in space (and moved)."""
    q, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return verts @ q.T + np.array([35.0, -120.0, 7.0])


@pytest.mark.parametrize("ratio", [1.0, 1.1, 1.25, 1.6, 2.0, 5.0])
@pytest.mark.parametrize("cuts", [1, 6])
def test_a_bar_is_not_a_hose(ratio, cuts):
    """A bar 1000 long with sides ratio : 1, as a CAD file has it (12 triangles) and meshed finely. The review
    found that 1.6 : 1 … 5 : 1 passed as a hose with half the diagonal as its radius."""
    verts, tris = box(1000.0, 40.0 * ratio, 40.0, cuts=cuts)
    for v, t in ((verts, tris), (turned(verts, 4), tris), (verts, any_way(tris))):
        tube = tube_centreline(v, t)
        assert not tube.ok, (ratio, cuts, tube.radius, tube.length)
        assert tube.problem == "The part is not round like a hose."


PROFILES = {
    "L profile": [(0, 0), (60, 0), (60, 8), (8, 8), (8, 60), (0, 60)],
    "I beam": [(0, 0), (60, 0), (60, 8), (34, 8), (34, 52), (60, 52), (60, 60), (0, 60), (0, 52), (26, 52), (26, 8),
               (0, 8)],
    "channel": [(0, 0), (60, 0), (60, 30), (52, 30), (52, 8), (8, 8), (8, 30), (0, 30)],
    "hollow box section": None,
}


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_a_profile_is_not_a_hose(name):
    if PROFILES[name] is None:
        verts, tris = make_tube(straight_path(600.0), 40.0, 4, bore=34.0)
    else:
        verts, tris = prism(PROFILES[name], 600.0)
    tube = tube_centreline(verts, tris)
    assert not tube.ok and tube.problem == "The part is not round like a hose.", (tube.problem, tube.radius)


def test_which_many_sided_bars_pass():
    """3 and 4 sides are bars; a hexagon passes (a hose's hex ferrule must), so a hexagon bar does too."""
    for sides, ok in ((3, False), (4, False), (6, True), (8, True), (12, True)):
        tube = tube_centreline(*make_tube(s_curve(), R, sides))
        assert tube.ok == ok, (sides, tube.problem)
    oval = lathe(np.linspace(0.0, 300.0, 31), np.full(31, 10.0))
    for wide, ok in ((1.1, True), (1.6, False)):                      # a hose pressed a little flat still reads
        tube = tube_centreline(oval[0] * np.array([wide, 1.0, 1.0]), oval[1])
        assert tube.ok == ok, (wide, tube.problem)


def test_a_cone_is_refused_a_ferrule_is_not():
    """Thicker at one end by more than about a third: "its thickness changes too much" (the review: 2 : 1 passed
    with the middle radius). Ferrules and a flange at the ends are fine."""
    zs = np.linspace(0.0, 300.0, 61)
    for big, ok in ((1.15, True), (1.3, True), (1.5, False), (2.0, False), (3.0, False)):
        tube = tube_centreline(*lathe(zs, np.linspace(6.0, 6.0 * big, 61)))
        assert tube.ok == ok, (big, tube.problem)
        if not ok:
            assert tube.problem == "The part's thickness changes too much along its length for a hose."
    ferrules = tube_centreline(*lathe([0.0, 30.0, 30.0, 270.0, 270.0, 300.0], [13.0, 13.0, 10.0, 10.0, 13.0, 13.0]))
    assert ferrules.ok and abs(ferrules.radius - 10.0) < 0.2 and abs(ferrules.length - 300.0) < 0.5
    flange = tube_centreline(*lathe([0.0, 12.0, 12.0, 300.0], [22.0, 22.0, 10.0, 10.0]))
    assert flange.ok and abs(flange.radius - 10.0) < 0.2 and abs(flange.length - 300.0) < 0.5


def _close_to_itself(name, gap, sides=16):
    """A hose that passes ``gap`` radii from itself: a hairpin, or a coil of 1.5 turns. Returns its exact path."""
    if name == "hairpin":
        return Path((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)).straight(150.0).arc(R + 0.5 * gap * R, 180.0,
                                                                         (0.0, 1.0, 0.0)).straight(150.0).points
    return helix(50.0, (2.0 + gap) * R, 1.5)


@pytest.mark.parametrize("name,gap", [("hairpin", 1.0), ("hairpin", 0.5), ("coil", 1.5), ("coil", 1.0),
                                      ("coil", 0.3)])
def test_hose_with_a_bore_close_to_itself(name, gap):
    """The review's finding: a hairpin with a bore, legs one radius apart, was read as HALF as long; a coil was
    read or refused depending on how it lay in space. The bore's wall is taken out before the ends are looked
    for, so it is now read like the solid one – however it is turned, and inside out as well. (A hairpin tighter
    than legs half a radius apart bends on 1.25 radii: no hose does; its length then reads 1–2 % short.)"""
    pts = _close_to_itself(name, gap)
    exact = path_length(pts)
    verts, tris = make_tube(pts, R, 16, bore=6.0, step=3.0)
    solid = tube_centreline(*make_tube(pts, R, 16, step=3.0))
    assert solid.ok and abs(solid.length - exact) < 0.005 * exact
    for v, t in ((verts, tris), (turned(verts, 1), tris), (turned(verts, 2), tris), (verts, tris[:, ::-1])):
        tube = tube_centreline(v, t)
        assert tube.ok, tube.problem
        assert abs(tube.length - exact) < 0.005 * exact and abs(tube.radius - R) < 0.02 * R
    # faces any way: the bore cannot be told then. Read right or refused – never a wrong hose
    for seed in (1, 2, 3):
        tube = tube_centreline(turned(verts, seed), any_way(tris, seed))
        assert not tube.ok or abs(tube.length - exact) < 0.005 * exact, (tube.length, exact)


def test_the_bore_is_told_from_the_outside():
    pts = s_curve()
    verts, tris = make_tube(pts, R, 12, bore=6.0, ferrule=(25.0, 14.0))
    p, t, _size = flex_fit._weld(verts, tris)
    bore = flex_fit._bore(p, t)
    far = np.linalg.norm(p[t].mean(axis=1)[:, None, :] - pts[None, ::8, :], axis=2).min(axis=1)   # from the centreline
    assert bore.sum() > 1000 and far[bore].max() < 6.01 and far[~bore].min() > 5.0
    wall = bore & True
    assert np.array_equal(flex_fit._bore(p, t[:, ::-1]), wall)                 # every face inside out: the same
    assert flex_fit._bore(p, any_way(t)) is None                               # faces any way: cannot be told
    for v2, t2 in (make_tube(pts, R, 12), torus(), make_tube(pts, R, 12, ferrule=(25.0, 14.0))):
        p2, t2, _size = flex_fit._weld(v2, t2)
        assert not flex_fit._bore(p2, t2).any()                                # solid, a ring: nothing hollow


def test_half_a_hose_is_never_returned(monkeypatch):
    """The old way to find a bored hose's ends (vertices lumped in boxes; still used when the faces look any way)
    takes the two legs of a hairpin for one thick hose half as long. Forced here: the result is refused, because
    its cuts are not round (two rings side by side) and, with the legs apart, the skin is too small for it."""
    pts = _close_to_itself("hairpin", 1.0)
    verts, tris = make_tube(pts, R, 16, bore=6.0, step=3.0)
    monkeypatch.setattr(flex_fit, "_bore", lambda p, t: None)
    tube = tube_centreline(verts, tris)
    assert not tube.ok and tube.problem.startswith("The part")
    monkeypatch.setattr(flex_fit, "ROUND_EVEN", 0.0)                           # without the roundness tests …
    monkeypatch.setattr(flex_fit, "ROUND_SHARE", 0.0)
    solid = make_tube(pts, R, 16, step=3.0)
    monkeypatch.setattr(flex_fit, "_whole", _two_legs_as_one(flex_fit._whole))
    tube = tube_centreline(*solid)
    assert not tube.ok or abs(tube.length - path_length(pts)) < 0.005 * path_length(pts)


def _two_legs_as_one(whole):
    """Spoils the first distances so that the "ends" found are the bend and one end (what the boxes did)."""
    def spoiled(p, t):
        out = whole(p, t)
        if out is None:
            return out
        p2, t2, edges, graph, closed, d = out
        d = np.where(np.isfinite(d), -np.linalg.norm(p2 - p2[np.argmax(p2[:, 0])], axis=1), d)   # start: the bend
        return p2, t2, edges, graph, closed, d
    return spoiled


def test_too_big_a_mesh_says_so_and_memory_errors_are_not_hidden(monkeypatch):
    verts, tris = make_tube(s_curve(), R, 12)
    monkeypatch.setattr(flex_fit, "MAX_POINTS", 500)
    tube = tube_centreline(verts, tris)
    assert not tube.ok and "too big" in tube.problem and tube.problem.startswith("The part")
    monkeypatch.undo()

    def no_memory(*_args):
        raise MemoryError

    monkeypatch.setattr(flex_fit, "_fit", no_memory)
    with pytest.raises(MemoryError):
        tube_centreline(verts, tris)


def test_two_hoses_in_one_mesh_are_refused_and_crumbs_are_ignored():
    pts = s_curve()
    verts, tris = make_tube(pts, R, 12)
    other = verts + np.array([0.0, 200.0, 0.0])
    tube = tube_centreline(np.concatenate([verts, other]), np.concatenate([tris, tris + len(verts)]))
    assert not tube.ok and "separate pieces" in tube.problem
    crumb, ctris = box(1.0, 1.0, 1.0)
    tube = tube_centreline(np.concatenate([verts, crumb + 500.0]), np.concatenate([tris, ctris + len(verts)]))
    check(tube, pts, R, centre_tol=0.02, end_tol=0.1)


def test_bad_input_never_raises():
    verts, tris = make_tube(s_curve(), R, 12)
    bad = [
        (np.zeros((0, 3)), np.zeros((0, 3), dtype=int)),
        ([], []),
        (None, None),
        (verts, np.zeros((0, 3), dtype=int)),
        (verts[:, :2], tris),
        (verts, tris[:, :2]),
        (np.full_like(verts, np.nan), tris),
        (np.zeros_like(verts), tris),                         # every vertex at one point
        (verts, np.zeros_like(tris)),                         # every triangle a point
        (verts, tris + 10 * len(verts)),                      # indices outside the vertices
        (verts * np.array([1.0, 0.0, 0.0]), tris),            # squashed onto a line
        ("hose", "mesh"),
    ]
    for v, t in bad:
        tube = tube_centreline(v, t)
        assert not tube.ok and tube.problem and tube.points.shape == (0, 3)
    # a few broken vertices and triangles in a good mesh do no harm
    v2 = verts.copy()
    t2 = np.concatenate([tris, [[0, 0, 5], [len(verts) + 7, 1, 2], [-4, 1, 2]]])
    v2 = np.concatenate([v2, [[np.nan, 0.0, 0.0]]])
    t2 = np.concatenate([t2, [[len(v2) - 1, 0, 1]]])
    check(tube_centreline(v2, t2), s_curve(), R, centre_tol=0.02, end_tol=0.1)


# ---------------------------------------------------------------------------------------------------------
# the two test models (tools/make_test_flex.py): the numbers of its docstring, read back through the importer
# ---------------------------------------------------------------------------------------------------------

# name: (diameter, length in A, length in B, end 0, out 0, end 1, out 1, fitting at end 0, fitting at end 1) – mm
HOSES = {
    "HYDRAULIC HOSE ARM": (20.0, 1008.54, 1058.99, (430, -70, 220), (0, 0, 1), (1000, 120, 600), (0, -1, 0),
                           "FITTING VALVE C", "FITTING ARM"),
    "HYDRAULIC HOSE CYL A": (16.0, 450.40, 450.40, (310, -70, 220), (0, 0, 1), (381.56, 125, 208.06), (0, -1, 0),
                             "FITTING VALVE A", "FITTING BARREL A"),
    "HYDRAULIC HOSE CYL B": (16.0, 551.52, 551.52, (370, -70, 220), (0, 0, 1), (647.97, 125, 332.39), (0, -1, 0),
                             "FITTING VALVE B", "FITTING BARREL B"),
    "CABLE": (10.0, 1062.59, 1062.59, (375, 350, 620), (1, 0, 0), (1185, 262, 600), (-1, 0, 0),
              "SLIDE GLAND", "CABLE GLAND ARM"),
}
HOSE_PARTS = ["BASE", "POST", "BASE.BRACKET", "BASE.PIN", "VALVE BLOCK", "FITTING VALVE A", "FITTING VALVE B",
              "FITTING VALVE C", "RAIL", "ARM", "ARM.PIN", "ARM.BRACKET", "ARM.ROD.PIN", "FITTING ARM",
              "CABLE GLAND ARM", "BARREL.CAP", "BARREL.TUBE", "BARREL.GLAND", "FITTING BARREL A", "FITTING BARREL B",
              "PISTON", "ROD", "ROD.EYE", "SLIDE CARRIAGE", "SLIDE GLAND"] + sorted(HOSES)
HOSE_ASSEMBLIES = ["TEST.FLEX.HOSES", "ARM.ASM", "CYL.ASM", "CYL.BARREL", "CYL.ROD", "SLIDE.ASM"]
# name: (links, pin 0, last pin, the fixed run's direction, the assembly it sits in) – mm
CHAINS = {
    "CHAIN X": (18, (-28.74, 70, 272), (-20, 70, 432), (1, 0, 0), "Y.ASM"),
    "CHAIN Y": (16, (600, 98.74, -8), (440, 90, -8), (0, -1, 0), "TEST.FLEX.GANTRY"),
    "CHAIN Z": (13, (-222, -8, 221.26), (-62, -8, 190), (0, 0, 1), "X.ASM"),
}
CHAIN_PARTS = ["BED", "STOCK 300x200x30", "CHAIN TRAY Y", "CHAIN BRACKET Y FIXED", "GANTRY SIDE L", "GANTRY SIDE R",
               "BEAM", "CHAIN BRACKET X FIXED", "CHAIN BRACKET Y MOVING", "CARRIAGE", "CHAIN BRACKET X MOVING",
               "CHAIN BRACKET Z FIXED", "SPINDLE", "TOOL T1 FLAT D6", "CHAIN BRACKET Z MOVING"]
CHAIN_ASSEMBLIES = ["TEST.FLEX.GANTRY", "Y.ASM", "X.ASM", "Z.ASM", "CHAIN X.ASM", "CHAIN Y.ASM", "CHAIN Z.ASM"]


def _maker():
    pytest.importorskip("OCP")
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_test_flex", os.path.join(ROOT, "tools", "make_test_flex.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path, tmp_path, quality="draft"):
    pytest.importorskip("OCP")
    from fresing_render.importer import step_reader

    info = step_reader.read_step(path, str(tmp_path), quality)
    return info, np.load(os.path.join(str(tmp_path), "meshes.npz"))


def _world(nodes):
    """Each node's matrix in the model's coordinates (metres), by its index."""
    out = {}
    for i, n in enumerate(nodes):
        m = np.array(n["matrix"], dtype=float)
        parent = n.get("parent", -1)
        out[i] = m if parent is None or parent < 0 else out[parent] @ m
    return out


def test_the_shipped_models_are_the_test_data():
    for name in ("test_flex_hoses_a.step", "test_flex_chains_a.step"):
        with open(os.path.join(ROOT, "fresing_render", "data", name), "rb") as a, \
                open(os.path.join(HERE, "data", name), "rb") as b:
            assert a.read() == b.read(), f"{name}: copy tests/data/{name} to fresing_render/data/"
    for path in (HOSES_A, HOSES_B, CHAINS_A):
        assert os.path.getsize(path) < 400 * 1024


@pytest.mark.parametrize("revision", ["A", "B"])
def test_the_maker_says_what_its_docstring_says(revision):
    """The numbers the Blender-side tests and the tour use: checked against the geometry."""
    maker = _maker()
    routes = maker.hose_routes(revision)
    for name, (dia, len_a, len_b, e0, o0, e1, o1, _f0, _f1) in HOSES.items():
        r = routes[name]
        assert maker.HOSE_DIAMETER[name] == dia
        assert abs(r.length - (len_a if revision == "A" else len_b)) < 0.006
        assert np.abs(r.end0 - e0).max() < 0.006 and np.abs(r.end1 - e1).max() < 0.006
        assert np.allclose(r.out0, o0) and np.allclose(r.out1, o1)
        assert r.min_radius > 3.5 * dia and r.straight >= 1.5 * dia
        pts = r.points(0.5)
        assert abs(path_length(pts) - r.length) < 0.01                     # the sampled line is the route
        drawn, least, most, spare, _pose = maker.hose_motion(revision)[name]
        assert most < r.length and spare > 0.07 * r.length and least <= drawn <= most
    assert abs(routes["CABLE"].length / np.linalg.norm(routes["CABLE"].end1 - routes["CABLE"].end0) - 1.3) < 0.02
    assert abs(maker.CYL_L - 662.12) < 0.01 and abs(maker.CYL_ANGLE - 25.02) < 0.01
    assert abs(maker.cylinder(-20.0)[0] - 500.69) < 0.01 and abs(maker.cylinder(20.0)[0] - 824.78) < 0.01
    assert (maker.PISTON, maker.TUBE_END) == (214.0, 418.0)
    for name, (links, first, last, along, _asm) in CHAINS.items():
        pins = maker.chain_pins(name)
        assert len(pins) == links + 1
        assert np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - 40.0).max() < 1e-9
        assert np.abs(pins[0] - first).max() < 0.006 and np.abs(pins[-1] - last).max() < 0.006
        assert np.allclose((pins[1] - pins[0]) / 40.0, along)
        on_fixed, on_moving = maker.CHAINS[name][:2]
        flat = maker.chain_pins_2d(on_fixed, on_moving)
        bend = flat[on_fixed:on_fixed + 7]                                  # the pin that touches + six more
        assert np.abs(np.hypot(bend[:, 0] - 40.0 * on_fixed, bend[:, 1] - 80.0) - 80.0).max() < 1e-9
        assert np.allclose(flat[:on_fixed + 1, 1], 0.0) and np.allclose(flat[on_fixed + 7:, 1], 160.0)
        lo, hi = maker.TRAVEL[maker.CHAINS[name][6]]
        for shift in np.linspace(lo, hi, 13):
            fixed, moving, centre = maker.chain_runs(on_fixed, on_moving, shift)
            assert fixed >= 2 and moving >= 2
            assert abs(centre - (40.0 * on_fixed + 0.5 * shift)) < 0.05     # the bend moves half as far


@pytest.mark.parametrize("revision", ["A", "B"])
def test_hoses_model_through_the_importer(tmp_path, revision):
    """Every hose of the STEP file read as the app reads it: its centreline's length, diameter, ends and end
    directions are the maker's (length 0.5 %, diameter 2 %, ends 0.1 mm, directions 1°)."""
    info, arrays = _read(HOSES_A if revision == "A" else HOSES_B, tmp_path)
    nodes = info["nodes"]
    names = [n["name"] for n in nodes]
    parts = HOSE_PARTS + (["ARM.LAMP"] if revision == "B" else [])
    assert sorted(names) == sorted(parts + HOSE_ASSEMBLIES)
    assert info["stats"]["placed_parts"] == info["stats"]["unique_parts"] == len(parts)
    world = _world(nodes)
    order = [n["name"] for n in nodes if n["name"] in HOSES]
    assert order == (list(HOSES) if revision == "A" else list(HOSES)[::-1])   # B: placed in the other order
    for i, n in enumerate(nodes):
        if n["name"] in parts:
            assert n.get("color"), (n["name"], "has no colour")
        if n["name"] not in HOSES:
            continue
        dia, len_a, len_b, e0, o0, e1, o1, _f0, _f1 = HOSES[n["name"]]
        verts, tris = arrays[f"p{n['mesh']}"], arrays[f"t{n['mesh']}"].reshape(-1, 3)
        tube = tube_centreline(verts, tris)
        assert tube.ok, tube.problem
        length = len_a if revision == "A" else len_b
        assert abs(tube.length * 1000.0 - length) < 0.005 * length
        assert abs(tube.radius * 2000.0 - dia) < 0.02 * dia
        m = world[i]
        ends = [(m @ np.r_[tube.points[k], 1.0])[:3] * 1000.0 for k in (0, -1)]
        assert np.linalg.norm(ends[0] - e0) < 0.1 and np.linalg.norm(ends[1] - e1) < 0.1
        assert angle(m[:3, :3] @ tube.t0, o0) < 1.0 and angle(m[:3, :3] @ tube.t1, -np.array(o1)) < 1.0


def test_hose_of_the_model_at_every_detail(tmp_path):
    """Finer facets: nearer the exact length (draft: within 0.11 %, fine: 0.03 %)."""
    for quality, tol in (("normal", 0.0006), ("fine", 0.0003)):
        info, arrays = _read(HOSES_A, tmp_path / quality, quality)
        for n in info["nodes"]:
            if n["name"] in HOSES:
                tube = tube_centreline(arrays[f"p{n['mesh']}"], arrays[f"t{n['mesh']}"].reshape(-1, 3))
                assert tube.ok and abs(tube.length * 1000.0 / HOSES[n["name"]][1] - 1.0) < tol
                assert abs(tube.radius * 2000.0 / HOSES[n["name"]][0] - 1.0) < 0.002


def test_chains_model_through_the_importer(tmp_path):
    info, arrays = _read(CHAINS_A, tmp_path)
    nodes = info["nodes"]
    names = [n["name"] for n in nodes]
    assert sorted(names) == sorted(CHAIN_PARTS + CHAIN_ASSEMBLIES + ["CHAIN LINK"] * 47)
    assert info["stats"]["placed_parts"] == 62 and info["stats"]["unique_parts"] == 16
    links = [i for i, n in enumerate(nodes) if n["name"] == "CHAIN LINK"]
    assert len({nodes[i]["mesh"] for i in links}) == 1, "every link is the same mesh"
    for n in nodes:
        if n["name"] in CHAIN_PARTS or n["name"] == "CHAIN LINK":
            assert n.get("color"), (n["name"], "has no colour")
    mesh = arrays[f"p{nodes[links[0]]['mesh']}"]
    assert np.allclose(mesh.min(axis=0), 0.0, atol=1e-6)                    # the link's origin: a corner of its body
    assert np.allclose(mesh.max(axis=0), [0.032, 0.060, 0.020], atol=1e-6)
    world = _world(nodes)
    for name, (count, first, last, _along, asm) in CHAINS.items():
        parent = names.index(f"{name}.ASM")
        assert nodes[nodes[parent]["parent"]]["name"] == asm                # the chain sits with its fixed side
        mine = [i for i in links if nodes[i]["parent"] == parent]
        assert len(mine) == count
        pins0 = np.array([(world[i] @ np.r_[-0.004, 0.030, 0.010, 1.0])[:3] for i in mine]) * 1000.0
        pins1 = np.array([(world[i] @ np.r_[0.036, 0.030, 0.010, 1.0])[:3] for i in mine]) * 1000.0
        assert np.abs(pins0[1:] - pins1[:-1]).max() < 1e-3, "each link's second pin is the next link's first"
        assert np.abs(pins0[0] - first).max() < 0.006 and np.abs(pins1[-1] - last).max() < 0.006
        turn = [angle(world[a][:3, 0], world[b][:3, 0]) for a, b in zip(mine[:-1], mine[1:])]
        bent = [t for t in turn if t > 25.0]
        assert len(bent) == 5 and np.allclose(bent, 28.955, atol=1e-3)      # the links between the pins on the bend
    for bracket in ("X FIXED", "Y MOVING"):
        assert nodes[nodes[names.index(f"CHAIN BRACKET {bracket}")]["parent"]]["name"] == "Y.ASM"
    for bracket in ("X MOVING", "Z FIXED"):
        assert nodes[nodes[names.index(f"CHAIN BRACKET {bracket}")]["parent"]]["name"] == "X.ASM"
    assert nodes[nodes[names.index("CHAIN BRACKET Z MOVING")]["parent"]]["name"] == "Z.ASM"
    assert nodes[nodes[names.index("CHAIN BRACKET Y FIXED")]["parent"]]["name"] == "TEST.FLEX.GANTRY"


def test_models_in_the_app(tmp_path):
    """Imported by the app: every named part is there with its colour, the links share one mesh, the hoses read
    as hoses from the objects' meshes, in the scene's metres."""
    bpy = pytest.importorskip("bpy")
    pytest.importorskip("OCP")
    import addon_utils

    import fresing_render
    from fresing_render.blender import build

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    try:
        scene = bpy.context.scene
        scene.fresing.out_folder = str(tmp_path)
        assert bpy.ops.fresing.import_step(filepath=HOSES_A, quality="draft") == {"FINISHED"}
        bpy.context.view_layer.update()
        parts = {ob[build.PROP_NAME]: ob for ob in build.iter_parts(scene)}
        assert sorted(parts) == sorted(HOSE_PARTS)
        assert all(ob.get(build.PROP_COLOR) for ob in parts.values())
        for name, (dia, length, _b, e0, _o0, e1, _o1, f0, f1) in HOSES.items():
            ob = parts[name]
            assert ob.parent[build.PROP_NAME] == "TEST.FLEX.HOSES"          # hoses hang directly under the root
            verts = np.empty(len(ob.data.vertices) * 3)
            ob.data.vertices.foreach_get("co", verts)
            ob.data.calc_loop_triangles()
            tris = np.empty(len(ob.data.loop_triangles) * 3, dtype=np.int32)
            ob.data.loop_triangles.foreach_get("vertices", tris)
            tube = tube_centreline(verts.reshape(-1, 3), tris.reshape(-1, 3))
            assert tube.ok, tube.problem
            assert abs(tube.length * 1000.0 - length) < 0.005 * length and abs(tube.radius * 2000.0 - dia) < 0.02 * dia
            m = np.array(ob.matrix_world)
            ends = [(m @ np.r_[tube.points[k], 1.0])[:3] * 1000.0 for k in (0, -1)]
            assert np.linalg.norm(ends[0] - e0) < 0.1 and np.linalg.norm(ends[1] - e1) < 0.1
            # each end lies on its fitting: the end point is in the fitting's box (to 0.1 mm)
            for end, fitting in zip(ends, (f0, f1)):
                box = np.array([np.array(parts[fitting].matrix_world) @ np.r_[c, 1.0]
                                for c in parts[fitting].bound_box])[:, :3] * 1000.0
                assert (end > box.min(axis=0) - 0.1).all() and (end < box.max(axis=0) + 0.1).all(), (name, fitting)
        assert parts["FITTING ARM"].parent[build.PROP_NAME] == "ARM.ASM"
        assert parts["FITTING BARREL A"].parent[build.PROP_NAME] == "CYL.BARREL"
        assert parts["SLIDE GLAND"].parent[build.PROP_NAME] == "SLIDE.ASM"

        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.fresing.out_folder = str(tmp_path)
        assert bpy.ops.fresing.import_step(filepath=CHAINS_A, quality="draft") == {"FINISHED"}
        bpy.context.view_layer.update()
        obs = list(build.iter_parts(scene))
        links = [ob for ob in obs if ob[build.PROP_NAME] == "CHAIN LINK"]
        assert len(obs) == 62 and len(links) == 47 and len({ob.data.name for ob in links}) == 1
        assert sorted(ob[build.PROP_NAME] for ob in obs if ob not in links) == sorted(CHAIN_PARTS)
        assert all(ob.get(build.PROP_COLOR) for ob in obs)
        by_chain = {}
        for ob in links:
            by_chain.setdefault(ob.parent[build.PROP_NAME], []).append(ob)
        assert {k: len(v) for k, v in by_chain.items()} == {"CHAIN X.ASM": 18, "CHAIN Y.ASM": 16, "CHAIN Z.ASM": 13}
        for name, (_count, first, last, _along, asm) in CHAINS.items():
            mine = by_chain[f"{name}.ASM"]
            assert mine[0].parent.parent[build.PROP_NAME] == asm
            pins = np.array([(np.array(ob.matrix_world) @ np.r_[p, 1.0])[:3] * 1000.0 for ob in mine
                             for p in ((-0.004, 0.030, 0.010), (0.036, 0.030, 0.010))])
            assert np.linalg.norm(pins - np.array(first), axis=1).min() < 0.01
            assert np.linalg.norm(pins - np.array(last), axis=1).min() < 0.01
    finally:
        fresing_render.unregister()
