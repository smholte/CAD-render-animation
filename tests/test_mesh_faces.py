"""Faces of a plain triangle mesh (core/mesh_faces.py, task 0117): cylinders found with their axes, flat faces,
free shapes, broken meshes, the same answer for welded and unwelded meshes, and the speed."""

import os
import time

import numpy as np
import pytest

from fresing_render.core import mesh_faces as mf


# ---------------------------------------------------------------------------------------------------------------
# mesh makers (every one checks its own winding: each inner edge is run once each way)
# ---------------------------------------------------------------------------------------------------------------

class Builder:
    def __init__(self):
        self.p: list = []
        self.t: list = []

    def points(self, arr) -> np.ndarray:
        arr = np.atleast_2d(np.asarray(arr, dtype=float))
        start = len(self.p)
        self.p.extend(arr.tolist())
        return np.arange(start, start + len(arr))

    def tri(self, a, b, c) -> int:
        self.t.append((int(a), int(b), int(c)))
        return len(self.t) - 1

    def quad(self, a, b, c, d) -> list:
        return [self.tri(a, b, c), self.tri(a, c, d)]

    def ring(self, n, r, z, phase=0.0, centre=(0.0, 0.0)):
        a = phase + 2 * np.pi * np.arange(n) / n
        return self.points(np.column_stack((centre[0] + r * np.cos(a), centre[1] + r * np.sin(a), np.full(n, z))))

    def square(self, n, half, z, phase):
        """``n`` points on a square's outline along the same rays as a ring (corners on rays when phase = 45 deg)."""
        a = phase + 2 * np.pi * np.arange(n) / n
        s = half / np.maximum(np.abs(np.cos(a)), np.abs(np.sin(a)))
        return self.points(np.column_stack((s * np.cos(a), s * np.sin(a), np.full(n, z))))

    def wall(self, lower, upper, outward=True) -> list:
        out = []
        n = len(lower)
        for k in range(n):
            a, b, c, d = lower[k], lower[(k + 1) % n], upper[(k + 1) % n], upper[k]
            out += self.quad(a, b, c, d) if outward else self.quad(a, d, c, b)
        return out

    def band(self, inner, outer, up=True) -> list:
        """The flat ring between two loops of the same length (normal +z when ``up``)."""
        out = []
        n = len(inner)
        for k in range(n):
            a, b, c, d = inner[k], outer[k], outer[(k + 1) % n], inner[(k + 1) % n]
            out += self.quad(a, b, c, d) if up else self.quad(a, d, c, b)
        return out

    def fan(self, loop, z, up=True) -> list:
        c = self.points([[0.0, 0.0, z]])[0]
        n = len(loop)
        return [self.tri(c, loop[k], loop[(k + 1) % n]) if up else self.tri(c, loop[(k + 1) % n], loop[k])
                for k in range(n)]

    def mesh(self):
        return np.asarray(self.p, dtype=float), np.asarray(self.t, dtype=np.int64).reshape(-1, 3)


def check_winding(tri, closed=True):
    e = np.concatenate((tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]))
    fwd = {tuple(x) for x in e.tolist()}
    assert len(fwd) == len(e), "an edge is run twice the same way"
    if closed:
        assert all((b, a) in fwd for a, b in fwd), "an edge is used by one triangle only"


def open_tube(n, r=0.05, h=0.3):
    b = Builder()
    ph = 0.3
    rings = [b.ring(n, r, z, ph) for z in (0.0, h / 2, h)]
    wall = b.wall(rings[0], rings[1]) + b.wall(rings[1], rings[2])
    p, t = b.mesh()
    check_winding(t, closed=False)
    return p, t, [(wall, r)]


def capped(n, r=0.05, h=0.12):
    b = Builder()
    lo, hi = b.ring(n, r, 0.0, 0.1), b.ring(n, r, h, 0.1)
    wall = b.wall(lo, hi)
    b.fan(hi, h, True)
    b.fan(lo, 0.0, False)
    p, t = b.mesh()
    check_winding(t)
    return p, t, [(wall, r)]


def shaft(n):
    return capped(n, r=0.005, h=2.0)


def plate_with_hole(n, half=0.1, r=0.03, th=0.01):
    b = Builder()
    ph = np.pi / 4
    i0, i1 = b.ring(n, r, 0.0, ph), b.ring(n, r, th, ph)
    s0, s1 = b.square(n, half, 0.0, ph), b.square(n, half, th, ph)
    top = b.band(i1, s1, True)
    bottom = b.band(i0, s0, False)
    b.wall(s0, s1, True)
    hole = b.wall(i0, i1, False)
    p, t = b.mesh()
    check_winding(t)
    return p, t, [(hole, r)], top, bottom


def boss_on_box(n, half=0.1, r=0.03, h=0.05, depth=0.04):
    b = Builder()
    ph = np.pi / 4
    i0 = b.ring(n, r, 0.0, ph)
    i1 = b.ring(n, r, h, ph)
    s0 = b.square(n, half, 0.0, ph)
    sb = b.square(n, half, -depth, ph)
    b.band(i0, s0, True)
    wall = b.wall(i0, i1, True)
    b.fan(i1, h, True)
    b.wall(sb, s0, True)
    b.fan(sb, -depth, False)
    p, t = b.mesh()
    check_winding(t)
    return p, t, [(wall, r)]


def slewing_ring(n, ro=1.0, ri=0.85, h=0.2):
    b = Builder()
    o0, o1 = b.ring(n, ro, 0.0), b.ring(n, ro, h)
    i0, i1 = b.ring(n, ri, 0.0), b.ring(n, ri, h)
    outer = b.wall(o0, o1, True)
    inner = b.wall(i0, i1, False)
    b.band(i1, o1, True)
    b.band(i0, o0, False)
    p, t = b.mesh()
    check_winding(t)
    return p, t, [(outer, ro), (inner, ri)]


def fillet(n, R=0.02, L=0.1, H=0.15):
    """Two flats joined by a quarter-round (n sides on the full circle; the quarter has n / 4 facets)."""
    k = n // 4
    tt = np.linspace(0, np.pi / 2, k + 1)
    prof = [(-L, 0.0)] + [(R * np.sin(a), R - R * np.cos(a)) for a in tt] + [(R, R + L)]
    b = Builder()
    lo = b.points([[x, y, 0.0] for x, y in prof])
    hi = b.points([[x, y, H] for x, y in prof])
    tris = []
    for i in range(len(prof) - 1):
        tris.append(b.quad(lo[i], lo[i + 1], hi[i + 1], hi[i]))
    p, t = b.mesh()
    check_winding(t, closed=False)
    arc = [x for q in tris[1:-1] for x in q]
    # the true axis runs along z through (0, R)
    return p, t, [(arc, R)], np.array([0.0, R, 0.0])


def box(lo=(0, 0, 0), hi=(1, 2, 3)):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    b = Builder()
    v = b.points([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        b.quad(*[v[i] for i in q])
    p, t = b.mesh()
    check_winding(t)
    return p, t


def uv_sphere(nu=32, nv=16, r=0.5):
    b = Builder()
    top = b.points([[0, 0, r]])[0]
    bot = b.points([[0, 0, -r]])[0]
    rings = []
    for i in range(1, nv):
        phi = np.pi * i / nv
        rings.append(b.ring(nu, r * np.sin(phi), r * np.cos(phi)))
    for k in range(nu):
        b.tri(top, rings[0][k], rings[0][(k + 1) % nu])
        b.tri(bot, rings[-1][(k + 1) % nu], rings[-1][k])
    for i in range(len(rings) - 1):
        b.wall(rings[i + 1], rings[i], True)
    p, t = b.mesh()
    check_winding(t)
    return p, t


def torus(nu=48, nv=24, R=1.0, r=0.3):
    u = 2 * np.pi * np.arange(nu) / nu
    v = 2 * np.pi * np.arange(nv) / nv
    U, V = np.meshgrid(u, v, indexing="ij")
    p = np.stack(((R + r * np.cos(V)) * np.cos(U), (R + r * np.cos(V)) * np.sin(U), r * np.sin(V)), -1).reshape(-1, 3)
    idx = np.arange(nu * nv).reshape(nu, nv)
    a = idx
    b_ = np.roll(idx, -1, 0)
    c = np.roll(np.roll(idx, -1, 0), -1, 1)
    d = np.roll(idx, -1, 1)
    t = np.concatenate((np.stack((a, b_, c), -1).reshape(-1, 3), np.stack((a, c, d), -1).reshape(-1, 3)))
    check_winding(t)
    return p, t


def rotate(p, seed, *extra):
    """A random turn and shift (also applied to the extra points/directions: (array, is_direction))."""
    rng = np.random.default_rng(seed)
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    shift = rng.uniform(-5, 5, 3)
    out = [p @ q.T + shift]
    for v, is_dir in extra:
        out.append(v @ q.T + (0 if is_dir else shift))
    return out


def unweld(p, t):
    return p[t].reshape(-1, 3), np.arange(3 * len(t)).reshape(-1, 3)


# ---------------------------------------------------------------------------------------------------------------
# checks of every result
# ---------------------------------------------------------------------------------------------------------------

def check_output(f: mf.Faces, m: int):
    assert f.order.dtype == np.int64 and f.starts.dtype == np.int32 and f.kinds.dtype == np.uint8
    assert np.array_equal(np.sort(f.order), np.arange(m))
    assert f.starts[0] == 0 and f.starts[-1] == m
    assert len(f.kinds) == len(f.starts) - 1
    if m:
        assert np.all(np.diff(f.starts) > 0)
    assert set(np.unique(f.kinds)).issubset({0, 1, 2, 3})
    assert len(f.axes) <= mf.MAX_AXES
    for a in f.axes:
        assert len(a) == 7
        d = np.asarray(a[3:6])
        assert abs(np.linalg.norm(d) - 1) < 1e-9
        nz = np.flatnonzero(np.abs(d) > 1e-9)
        assert d[nz[0]] > 0
        assert abs(np.dot(a[0:3], d)) < 1e-6 * max(1.0, np.linalg.norm(a[0:3]))  # foot nearest the origin
    af = f.axis_faces
    assert len(af) % 3 == 0
    for k in range(0, len(af), 3):
        s, c, i = af[k:k + 3]
        face = int(np.searchsorted(f.starts, s, side="right") - 1)
        assert f.starts[face] == s and f.starts[face + 1] == s + c
        assert f.kinds[face] in (2, 3)
        assert 0 <= i < len(f.axes)


def face_sets(f: mf.Faces):
    return [set(f.order[f.starts[k]:f.starts[k + 1]].tolist()) for k in range(len(f.kinds))]


def round_faces(f: mf.Faces):
    """{face index: axis} for every face with an axis."""
    out = {}
    for k in range(0, len(f.axis_faces), 3):
        s, c, i = f.axis_faces[k:k + 3]
        out[int(np.searchsorted(f.starts, s, side="right") - 1)] = f.axes[i]
    return out


def assert_axis(axis, true_dir, true_point, R):
    d = np.asarray(axis[3:6])
    ang = np.degrees(np.arccos(min(1.0, abs(float(np.dot(d, true_dir))))))
    assert ang < 0.5, f"axis {ang:.3f} deg off"
    o = np.asarray(axis[0:3])
    off = (o - true_point) - np.dot(o - true_point, true_dir) * true_dir
    assert np.linalg.norm(off) < 0.005 * R, f"axis {np.linalg.norm(off) / R:.4%} of r beside the true one"
    return ang


SIDES = (16, 24, 32, 48, 64)
SHAPES = {
    "open tube": lambda n: open_tube(n)[:3],
    "capped": lambda n: capped(n)[:3],
    "boss on box": lambda n: boss_on_box(n)[:3],
    "hole in plate": lambda n: plate_with_hole(n)[:3],
    "long shaft": lambda n: shaft(n)[:3],
    "slewing ring": lambda n: slewing_ring(n)[:3],
}


@pytest.mark.parametrize("n", SIDES)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_cylinder_wall_is_one_round_face(shape, n):
    p, t, walls = SHAPES[shape](n)
    seed = 31 * n + list(SHAPES).index(shape)
    p2, d, o = rotate(p, seed, (np.array([0.0, 0.0, 1.0]), True), (np.zeros(3), False))
    f = mf.split(p2, t)
    check_output(f, len(t))
    sets = face_sets(f)
    rf = round_faces(f)
    assert sum(f.kinds == 2) == len(walls)
    rmax = max(r for _, r in walls)
    for tris, r in walls:
        k = sets.index(set(tris))
        assert f.kinds[k] == 2 and k in rf
        assert_axis(rf[k], d, o, r)
        assert abs(rf[k][6] - rmax) < 0.005 * rmax
    assert len(f.axes) == 1                             # walls on one line share one axis


@pytest.mark.parametrize("n", SIDES)
def test_fillet_between_two_flats(n):
    p, t, walls, centre = fillet(n)
    p2, d, o = rotate(p, n, (np.array([0.0, 0.0, 1.0]), True), (centre, False))
    f = mf.split(p2, t)
    check_output(f, len(t))
    sets = face_sets(f)
    (tris, r), = walls
    k = sets.index(set(tris))
    assert f.kinds[k] == 2
    axis = round_faces(f)[k]
    assert_axis(axis, d, o, r)
    assert abs(axis[6] - r) < 0.005 * r
    assert len(f.kinds) == 3 and sorted(f.kinds.tolist()) == [1, 1, 2]   # the two flats stay flat faces


def test_box_has_six_flat_faces():
    p, t = box()
    f = mf.split(*rotate(p, 3), t)
    check_output(f, len(t))
    assert len(f.kinds) == 6 and np.all(f.kinds == 1)
    assert f.axes == [] and f.axis_faces == []


@pytest.mark.parametrize("n", (16, 32, 64))
def test_plate_with_hole_flat_sides_are_one_face_each(n):
    p, t, walls, top, bottom = plate_with_hole(n)
    f = mf.split(rotate(p, 7)[0], t)
    check_output(f, len(t))
    sets = face_sets(f)
    assert set(top) in sets and set(bottom) in sets
    assert f.kinds[sets.index(set(top))] == 1
    assert sorted(f.kinds.tolist()) == [1] * 6 + [2]     # top, bottom, four sides, the hole


@pytest.mark.parametrize("maker", [lambda: capped(32)[:2], lambda: plate_with_hole(48)[:2], lambda: uv_sphere(),
                                   lambda: slewing_ring(64)[:2], lambda: fillet(32)[:2], lambda: box()])
def test_unwelded_mesh_gives_the_same_faces(maker):
    p, t = maker()
    p = rotate(p, 11)[0]
    a = mf.split(p, t)
    pu, tu = unweld(p, t)
    rng = np.random.default_rng(0)
    b = mf.split(pu, tu, normals=rng.normal(size=pu.shape))      # garbage normals are ignored
    c = mf.split(pu, tu)
    check_output(b, len(t))
    for x in (b, c):
        assert np.array_equal(a.order, x.order)
        assert np.array_equal(a.starts, x.starts)
        assert np.array_equal(a.kinds, x.kinds)
        assert a.axis_faces == x.axis_faces
        assert np.allclose(np.asarray(a.axes).reshape(-1, 7), np.asarray(x.axes).reshape(-1, 7), atol=1e-9)


# ---------------------------------------------------------------------------------------------------------------
# free shapes and broken meshes
# ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("nu,nv", [(16, 8), (32, 16), (64, 32), (128, 64)])
def test_sphere_is_few_faces(nu, nv):
    p, t = uv_sphere(nu, nv)
    f = mf.split(rotate(p, nu)[0], t)
    check_output(f, len(t))
    assert len(f.kinds) <= 4, f"{len(f.kinds)} faces"
    assert not np.any(f.kinds == 2)


@pytest.mark.parametrize("nu,nv", [(24, 12), (48, 24), (96, 48)])
def test_torus_is_few_faces(nu, nv):
    p, t = torus(nu, nv)
    f = mf.split(rotate(p, 5)[0], t)
    check_output(f, len(t))
    assert len(f.kinds) <= 4, f"{len(f.kinds)} faces"


def test_noise_and_broken_triangles_do_not_crash():
    rng = np.random.default_rng(1)
    p = rng.normal(size=(3000, 3))
    t = rng.integers(0, 3000, size=(5000, 3))
    f = mf.split(p, t)
    check_output(f, len(t))
    # triangles with a repeated corner, three corners on a line, all corners in one point
    p2, t2 = capped(32)[:2]
    n = len(p2)
    extra_p = np.array([[0, 0, 5.0], [1, 0, 5.0], [2, 0, 5.0]])
    p3 = np.concatenate((p2, extra_p))
    t3 = np.concatenate((t2, [[0, 0, 1], [n, n + 1, n + 2], [5, 5, 5], [t2[0, 0], t2[0, 1], t2[0, 1]]]))
    f = mf.split(p3, t3)
    check_output(f, len(t3))
    assert sum(f.kinds == 2) == 1


def test_zero_area_slivers_join_a_neighbour():
    p, t, walls = capped(32)
    a, b = t[0, 0], t[0, 1]
    mid = len(p)
    p = np.concatenate((p, [(p[a] + p[b]) / 2]))
    t = np.concatenate((t, [[a, mid, b]]))              # a needle on the wall's first edge
    f = mf.split(p, t)
    check_output(f, len(t))
    assert sum(f.kinds == 2) == 1
    assert len(f.kinds) == 3


def test_duplicated_and_flipped_triangles():
    p, t = box()
    t2 = np.concatenate((t, t, t[:, ::-1]))
    f = mf.split(p, t2)
    check_output(f, len(t2))
    p, t, _ = capped(32)
    t2 = np.concatenate((t, t))
    f = mf.split(p, t2)
    check_output(f, len(t2))


def test_non_manifold_edges():
    # a fin standing on a plate: three or four triangles on one edge
    b = Builder()
    v = b.points([[-1, -1, 0], [0, -1, 0], [1, -1, 0], [-1, 1, 0], [0, 1, 0], [1, 1, 0], [0, -1, 1], [0, 1, 1]])
    b.quad(v[0], v[1], v[4], v[3])
    b.quad(v[1], v[2], v[5], v[4])
    b.quad(v[1], v[4], v[7], v[6])
    b.quad(v[1], v[6], v[7], v[4])
    p, t = b.mesh()
    f = mf.split(p, t)
    check_output(f, len(t))


@pytest.mark.parametrize("p,t", [
    (np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)),
    (np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0.0]]), np.array([[0, 1, 2]])),
    (np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0.0]]), np.array([[0, 1, 2], [0, 1, 2]])),
    (np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0.0]]), np.array([[0, 1, 2]])),
    (np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [5, 5, 5], [6, 5, 5], [5, 6, 5.0]]), np.array([[0, 1, 2], [3, 4, 5]])),
    (np.array([[0, 0, 0], [1, 0, 0], [np.nan, 1, 0.0]]), np.array([[0, 1, 2]])),
])
def test_tiny_meshes(p, t):
    f = mf.split(p, t)
    check_output(f, len(t))
    if len(t) == 0:
        assert len(f.order) == 0 and list(f.starts) == [0] and len(f.kinds) == 0


def test_deterministic():
    p, t = torus(48, 24)
    p2, t2, _ = slewing_ring(48)
    p3, t3 = uv_sphere()
    pp = np.concatenate((p, p2 + 5, p3 - 5))
    tt = np.concatenate((t, t2 + len(p), t3 + len(p) + len(p2)))
    a, b = mf.split(pp, tt), mf.split(pp.copy(), tt.copy())
    assert np.array_equal(a.order, b.order) and np.array_equal(a.starts, b.starts)
    assert np.array_equal(a.kinds, b.kinds) and a.axes == b.axes and a.axis_faces == b.axis_faces


def test_max_axes():
    parts = []
    off = 0
    pp, tt = [], []
    for k in range(mf.MAX_AXES + 10):
        p, t, _ = open_tube(16, r=0.01, h=0.05)
        pp.append(p + [0.05 * (k % 30), 0.05 * (k // 30), 0])
        tt.append(t + off)
        off += len(p)
    f = mf.split(np.concatenate(pp), np.concatenate(tt))
    check_output(f, sum(len(t) for t in tt))
    assert sum(f.kinds == 2) == mf.MAX_AXES + 10
    assert len(f.axes) == mf.MAX_AXES and len(f.axis_faces) == 3 * mf.MAX_AXES


# ---------------------------------------------------------------------------------------------------------------
# weld and loose parts
# ---------------------------------------------------------------------------------------------------------------

def test_weld_joins_points_across_a_grid_boundary():
    tol = 1e-3
    p = np.array([[0.0, 0, 0], [10.0, 0, 0],
                  [5 * tol - 1e-7, 3 * tol + 1e-7, 0], [5 * tol + 1e-7, 3 * tol - 1e-7, 0],
                  [1.0, 1.0, 1.0], [1.0 + 0.4 * tol, 1.0, 1.0 - 0.4 * tol], [1.0 + 5 * tol, 1.0, 1.0]])
    w = mf.weld(p, tol)
    assert w.dtype == np.int64
    assert w[2] == w[3] and w[4] == w[5]
    assert len({w[0], w[1], w[2], w[4], w[6]}) == 5
    assert list(w[:3]) == [0, 1, 2]                    # numbered by first appearance
    assert len(mf.weld(np.zeros((0, 3)))) == 0


def test_loose_parts_through_welded_corners():
    p1, t1 = box()
    p2, t2 = box((5, 5, 5), (6, 6, 6))
    p = np.concatenate((p2, p1))
    t = np.concatenate((t2, t1 + len(p2)))
    pu, tu = unweld(p, t)
    lab = mf.loose_parts(pu, tu)
    assert lab.dtype == np.int64 and len(lab) == len(t)
    assert list(np.unique(lab)) == [0, 1]
    assert np.all(lab[:12] == 0) and np.all(lab[12:] == 1)
    assert len(mf.loose_parts(np.zeros((0, 3)), np.zeros((0, 3), dtype=int))) == 0


# ---------------------------------------------------------------------------------------------------------------
# speed
# ---------------------------------------------------------------------------------------------------------------

def many_parts(n_tri: int, seed=0):
    """Capped cylinders (64 sides) and boxes in a grid, unwelded like a glTF export, about ``n_tri`` triangles."""
    pc, tc, _ = capped(64, r=0.02, h=0.05)
    pb, tb = box((0.03, 0, 0), (0.06, 0.03, 0.04))
    p1 = np.concatenate((pc, pb))
    t1 = np.concatenate((tc, tb + len(pc)))
    p1, t1 = unweld(p1, t1)
    copies = max(1, n_tri // len(t1))
    side = int(np.ceil(np.sqrt(copies)))
    k = np.arange(copies)
    shift = np.column_stack((0.1 * (k % side), 0.1 * (k // side), np.zeros(copies)))
    p = (p1[None, :, :] + shift[:, None, :]).reshape(-1, 3)
    t = (t1[None, :, :] + (len(p1) * k)[:, None, None]).reshape(-1, 3)
    return p, t, copies


def test_speed_100k():
    p, t, copies = many_parts(100_000)
    t0 = time.perf_counter()
    f = mf.split(p, t)
    dt = time.perf_counter() - t0
    print(f"\n{len(t)} triangles: {dt:.2f} s, {len(f.kinds)} faces")
    check_output(f, len(t))
    assert sum(f.kinds == 2) == copies
    assert dt < 2.0


def test_speed_isolated_triangles():
    rng = np.random.default_rng(2)
    p = rng.uniform(0, 100, size=(600_000, 3))
    t = np.arange(600_000).reshape(-1, 3)
    t0 = time.perf_counter()
    f = mf.split(p, t)
    dt = time.perf_counter() - t0
    print(f"\n200k isolated triangles: {dt:.2f} s")
    assert len(f.kinds) == 200_000
    assert dt < 4.0


@pytest.mark.skipif(not os.environ.get("FR_SLOW"), reason="set FR_SLOW=1 for the 1 M triangle timing")
def test_speed_1m():
    p, t, copies = many_parts(1_000_000)
    t0 = time.perf_counter()
    f = mf.split(p, t)
    dt = time.perf_counter() - t0
    print(f"\n{len(t)} triangles: {dt:.2f} s, {len(f.kinds)} faces")
    check_output(f, len(t))
    assert sum(f.kinds == 2) == copies
    assert dt < 10.0


# ---------------------------------------------------------------------------------------------------------------
# more shapes: 32-bit positions, bends, fillet rings, short arcs, slots, height fields
# ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", list(SHAPES))
def test_float32_positions(shape):
    """glTF stores 32-bit positions: the walls are still found (positions a few metres from the origin)."""
    p, t, walls = SHAPES[shape](32)
    p2, d, o = rotate(p, 17, (np.array([0.0, 0.0, 1.0]), True), (np.zeros(3), False))
    f = mf.split(p2.astype(np.float32), t)
    check_output(f, len(t))
    sets = face_sets(f)
    rf = round_faces(f)
    rmax = max(r for _, r in walls)
    for tris, r in walls:
        k = sets.index(set(tris))
        assert_axis(rf[k], d, o, r)
        assert abs(rf[k][6] - rmax) < 0.005 * rmax


def pipe_with_bend(n, nb, r=0.02, Rb=0.1, L=0.3):
    """A straight pipe along +x, a 90 degree bend (nb pieces) round (0, Rb), a straight pipe along +y."""
    cl = [np.array([-L, 0, 0]), np.array([0.0, 0, 0])]
    tang = [np.array([1.0, 0, 0])] * 2
    for a in np.linspace(0, np.pi / 2, nb + 1)[1:]:
        cl.append(np.array([Rb * np.sin(a), Rb - Rb * np.cos(a), 0]))
        tang.append(np.array([np.cos(a), np.sin(a), 0]))
    cl.append(np.array([Rb, Rb + L, 0]))
    tang.append(np.array([0, 1.0, 0]))
    b = Builder()
    rings = []
    ang = 2 * np.pi * np.arange(n) / n
    for c, tg in zip(cl, tang):
        u = np.array([0, 0, 1.0])
        v = np.cross(tg, u)
        rings.append(b.points(c + r * np.outer(np.cos(ang), u) + r * np.outer(np.sin(ang), v)))
    parts = [b.wall(rings[i], rings[i + 1], True) for i in range(len(rings) - 1)]
    p, t = b.mesh()
    check_winding(t, closed=False)
    return p, t, parts[0], parts[-1]


@pytest.mark.parametrize("n,nb", [(16, 8), (32, 12), (32, 24), (64, 24)])
def test_pipe_bend_straight_pipes_are_cylinders(n, nb):
    p, t, first, last = pipe_with_bend(n, nb)
    p2, dx, dy = rotate(p, n + nb, (np.array([1.0, 0, 0]), True), (np.array([0, 1.0, 0]), True))
    f = mf.split(p2, t)
    check_output(f, len(t))
    rf = round_faces(f)
    assert sum(f.kinds == 2) == 2 and len(f.axes) == 2
    sets = face_sets(f)
    for tris, d in ((first, dx), (last, dy)):
        k = next(i for i, s in enumerate(sets) if set(tris) <= s)   # the pipe's face (it may reach into the bend)
        assert f.kinds[k] == 2
        assert abs(rf[k][6] - 0.02) < 1e-4
        assert np.degrees(np.arccos(min(1.0, abs(np.dot(rf[k][3:6], d))))) < 0.5
        assert len(sets[k]) <= 1.1 * len(tris)


@pytest.mark.parametrize("n", (16, 32, 64))
def test_boss_with_a_fillet_ring_at_its_foot(n):
    """The boss wall is a cylinder; the fillet ring (a torus) round its foot is not."""
    rf_, r, h = 0.01, 0.03, 0.06
    prof = [(0.1, 0.0)] + [(r + rf_ - rf_ * np.sin(a), rf_ - rf_ * np.cos(a)) for a in np.linspace(0, np.pi / 2, 5)]
    prof += [(r, h)]
    b = Builder()
    rings = [b.ring(n, rr, z) for rr, z in prof]
    walls = [b.wall(rings[i], rings[i + 1], True) for i in range(len(rings) - 1)]
    p, t = b.mesh()
    f = mf.split(rotate(p, n)[0], t)
    check_output(f, len(t))
    sets = face_sets(f)
    k = sets.index(set(walls[-1]))
    assert f.kinds[k] == 2 and abs(round_faces(f)[k][6] - r) < 0.005 * r
    assert sum(f.kinds == 2) == 1
    assert sorted(f.kinds.tolist()) == [0, 1, 2]


def test_two_facets_are_not_a_cylinder():
    """Flat - two facets - flat (an arc of 2 steps): no round face (as in a CAD chamfer pair)."""
    R = 0.02
    prof = [(-0.1, 0.0)] + [(R * np.sin(a), R - R * np.cos(a)) for a in np.radians([0, 22.5, 45])]
    prof += [(R * np.sin(np.radians(45)) + 0.1, R - R * np.cos(np.radians(45)) + 0.1)]
    b = Builder()
    lo = b.points([[x, y, 0.0] for x, y in prof])
    hi = b.points([[x, y, 0.2] for x, y in prof])
    for i in range(len(prof) - 1):
        b.quad(lo[i], lo[i + 1], hi[i + 1], hi[i])
    p, t = b.mesh()
    f = mf.split(p, t)
    check_output(f, len(t))
    assert not np.any(f.kinds == 2)


@pytest.mark.parametrize("n", (16, 32, 64))
def test_slot_with_round_ends(n):
    """A slot (two flats, two half rounds, extruded): two round faces with their own axes, two flats."""
    r, half = 0.01, 0.03
    k = n // 2
    a1 = np.linspace(-np.pi / 2, np.pi / 2, k + 1)
    a2 = np.linspace(np.pi / 2, 3 * np.pi / 2, k + 1)
    loop = [(half + r * np.cos(a), r * np.sin(a)) for a in a1] + [(-half + r * np.cos(a), r * np.sin(a)) for a in a2]
    b = Builder()
    lo = b.points([[x, y, 0.0] for x, y in loop])
    hi = b.points([[x, y, 0.05] for x, y in loop])
    b.wall(lo, hi, True)
    p, t = b.mesh()
    p2, d, c1, c2 = rotate(p, n, (np.array([0, 0, 1.0]), True), (np.array([half, 0, 0]), False),
                           (np.array([-half, 0, 0]), False))
    f = mf.split(p2, t)
    check_output(f, len(t))
    assert sorted(f.kinds.tolist()) == [1, 1, 2, 2]
    assert len(f.axes) == 2
    for ax in f.axes:
        assert abs(ax[6] - r) < 0.005 * r
        near = min(np.linalg.norm(np.cross(np.asarray(ax[:3]) - c, d)) for c in (c1, c2))
        assert near < 0.005 * r


def test_smooth_height_field_is_one_face():
    n = 200
    x, y = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")
    z = 0.05 * np.sin(6 * x) * np.cos(5 * y)
    p = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    idx = np.arange(n * n).reshape(n, n)
    a, b_, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    t = np.concatenate((np.stack((a, b_, c), -1).reshape(-1, 3), np.stack((a, c, d), -1).reshape(-1, 3)))
    f = mf.split(p, t)
    check_output(f, len(t))
    assert len(f.kinds) <= 3
    assert not np.any(f.kinds == 2)


@pytest.mark.parametrize("n,nv", [(16, 8), (32, 16), (64, 64)])
def test_capsule_wall_is_a_cylinder(n, nv):
    """A cylinder with half spheres on both ends (smooth joins): the wall is round, the ends are not."""
    r, h = 0.02, 0.08
    b = Builder()
    rings = []
    for i in range(nv // 2, -1, -1):                   # lower half sphere, from the pole up to the equator
        a = np.pi / 2 * i / (nv // 2)
        rings.append(b.ring(n, r * np.cos(a), -r * np.sin(a)) if i else b.ring(n, r, 0.0))
    for i in range(0, nv // 2 + 1):                    # upper half sphere, from the equator up
        a = np.pi / 2 * i / (nv // 2)
        rings.append(b.ring(n, r * np.cos(a), h + r * np.sin(a)) if i else b.ring(n, r, h))
    rings = [rr for rr in rings]
    parts = []
    for i in range(len(rings) - 1):
        lo_, hi_ = rings[i], rings[i + 1]
        if np.allclose(np.asarray(b.p)[lo_], np.asarray(b.p)[hi_]):
            continue
        parts.append(b.wall(lo_, hi_, True))
    p, t = b.mesh()
    keep = np.array([len(set(x)) == 3 and np.linalg.norm(np.cross(p[x[1]] - p[x[0]], p[x[2]] - p[x[0]])) > 1e-12
                     for x in t])                      # drop the triangles that fold into the poles
    t = t[keep]
    f = mf.split(rotate(p, n)[0], t)
    check_output(f, len(t))
    assert sum(f.kinds == 2) == 1
    assert abs(f.axes[0][6] - r) < 0.005 * r


def test_jittered_cylinder():
    """Corners a millionth of the size off the true circle (rounding in a file) still make one round face."""
    p, t, walls = capped(48, r=0.05, h=0.1)
    rng = np.random.default_rng(4)
    p = p + rng.normal(scale=1e-7, size=p.shape)
    f = mf.split(p, t)
    check_output(f, len(t))
    assert sorted(f.kinds.tolist()) == [1, 1, 2]


@pytest.mark.parametrize("maker", [lambda: capped(32)[:2], lambda: plate_with_hole(48)[:2], lambda: fillet(32)[:2],
                                   lambda: box()])
def test_triangles_wound_the_wrong_way(maker):
    """Some exporters turn triangles round at random: the faces stay the same."""
    p, t = maker()
    a = mf.split(p, t)
    flip = np.random.default_rng(3).random(len(t)) < 0.3
    t2 = np.where(flip[:, None], t[:, ::-1], t)
    b = mf.split(p, t2)
    check_output(b, len(t))
    assert np.array_equal(a.order, b.order) and np.array_equal(a.starts, b.starts)
    assert np.array_equal(a.kinds, b.kinds) and a.axis_faces == b.axis_faces
    assert np.allclose(np.asarray(a.axes).reshape(-1, 7), np.asarray(b.axes).reshape(-1, 7), atol=1e-9)


def height_field(n, noise=0.0, seed=0):
    x, y = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")
    z = 0.05 * np.sin(8 * x) * np.cos(7 * y) + noise * np.random.default_rng(seed).random((n, n))
    p = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    idx = np.arange(n * n).reshape(n, n)
    a, b_, c, d = idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]
    return p, np.concatenate((np.stack((a, b_, c), -1).reshape(-1, 3), np.stack((a, c, d), -1).reshape(-1, 3)))


@pytest.mark.skipif(not os.environ.get("FR_SLOW"), reason="set FR_SLOW=1 for the 1 M triangle timing")
@pytest.mark.parametrize("noise", (0.0, 0.002, 0.05))
def test_speed_1m_height_field(noise):
    """A fine height field: smooth (one face), a little rough (many small faces), very rough (a face per
    triangle almost)."""
    p, t = height_field(708, noise)
    t0 = time.perf_counter()
    f = mf.split(p, t)
    dt = time.perf_counter() - t0
    print(f"\n{len(t)} triangles, noise {noise}: {dt:.2f} s, {len(f.kinds)} faces")
    check_output(f, len(t))
    assert dt < 10.0
