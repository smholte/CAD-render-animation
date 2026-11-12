"""Task 0061: the normals of the milled workpiece (fresing_render/core/cut_normals.py).

Flat faces flat, round walls smooth by angle, nothing shaded across a sharp edge, needle triangles neither pull
their neighbours nor show themselves. Pure NumPy, plus a milled block from the core (Manifold) and one test in
Blender on the test mill (tools/make_test_mill.py: the block's top is at z = 70 mm, the slot's floor at 65 mm).
"""

from __future__ import annotations

import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import cut_normals as CN

MM = 0.001
HERE = os.path.dirname(__file__)


def face_normals(v, t) -> np.ndarray:
    p = np.asarray(v, np.float64)[np.asarray(t)]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-300)[:, None]


def angle(a, b) -> np.ndarray:
    """Degrees between unit vectors (row by row)."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return np.degrees(2.0 * np.arctan2(np.linalg.norm(a - b, axis=-1), np.linalg.norm(a + b, axis=-1)))   # exact near 0


def corners(v, t, **kw) -> np.ndarray:
    """corner_normals as (triangles, 3 corners, 3); checks the shape, the type and the length on the way."""
    n = CN.corner_normals(v, t, **kw)
    assert n.shape == (len(t) * 3, 3) and n.dtype == np.float32
    assert np.isfinite(n).all()
    assert np.abs(np.linalg.norm(n.astype(np.float64), axis=1) - 1.0).max() < 1e-5
    return n.reshape(-1, 3, 3)


def cube():
    v = np.array([(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)], float)
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]      # outward
    t = np.array([(a, b, c) for a, b, c, d in q] + [(a, c, d) for a, b, c, d in q])
    return v, t


def cylinder(n=40, r=1.0, h=2.0, caps="centre"):
    """A closed cylinder about Z: (verts, tris, number of side triangles). The side's 2 n triangles come first."""
    a = np.arange(n) * 2 * math.pi / n
    ring = np.stack([r * np.cos(a), r * np.sin(a)], axis=1)
    v = np.vstack([np.c_[ring, np.zeros(n)], np.c_[ring, np.full(n, h)], [(0, 0, 0), (0, 0, h)]])
    i = np.arange(n)
    j = (i + 1) % n
    side = np.vstack([np.c_[i, j, j + n], np.c_[i, j + n, i + n]])
    if caps == "centre":                                 # a fan round a point in the middle (n triangles round it)
        cap = np.vstack([np.c_[np.full(n, 2 * n), j, i], np.c_[np.full(n, 2 * n + 1), i + n, j + n]])
    else:                                                # a fan from a corner, as a boolean leaves it: needles
        k = np.arange(1, n - 1)
        cap = np.vstack([np.c_[np.zeros(n - 2, int), k + 1, k], np.c_[np.full(n - 2, n), k + n, k + 1 + n]])
    return v, np.vstack([side, cap]), 2 * n


def turned(v, shift=(0.0613, -0.0271, 0.0432)):
    """The mesh turned to no round direction, moved and rounded to 32 bits - as a milled mesh comes."""
    ax = np.array([0.3, -0.5, 0.81])
    ax /= np.linalg.norm(ax)
    k = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    rot = np.eye(3) + math.sin(0.7) * k + (1 - math.cos(0.7)) * k @ k
    return (np.asarray(v, float) @ rot.T + np.array(shift)).astype(np.float32), rot


# ---------------------------------------------------------------------------
# flat and sharp
# ---------------------------------------------------------------------------

def test_a_cube_is_flat_everywhere():
    v, t = cube()
    n = corners(v, t)
    assert angle(n, face_normals(v, t)[:, None, :]).max() < 1e-3
    assert CN.corner_normals(v, t).tolist() == np.repeat(face_normals(v, t), 3, axis=0).tolist()   # exactly


def test_nothing_in_nothing_out():
    out = CN.corner_normals(np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    assert out.shape == (0, 3) and out.dtype == np.float32
    assert CN.corner_normals(np.zeros((5, 3)), np.zeros((0, 3), np.int64)).shape == (0, 3)


@pytest.mark.parametrize("caps", ["centre", "corner"])
def test_cylinder_side_smooth_caps_flat_rim_sharp(caps):
    v, t, ns = cylinder(40, caps=caps)
    n = corners(v, t)
    radial = v[t][:, :, :2] / np.linalg.norm(v[t][:, :, :2], axis=2, keepdims=True).clip(1e-9)
    # the side: at every corner the normal points straight out of the axis (the two strips there count the same)
    side = n[:ns]
    assert np.abs(side[:, :, 2]).max() < 1e-6, "the caps do not pull the side's normals: the rim is sharp"
    assert angle(side[:, :, :2] / np.linalg.norm(side[:, :, :2], axis=2, keepdims=True), radial[:ns]).max() < 0.01
    # the caps: flat, also the 40 triangles round the middle point and the needles of the corner fan
    cap = n[ns:]
    fz = np.sign(face_normals(v, t)[ns:, 2])
    assert np.abs(cap[:, :, :2]).max() < 1e-6 and (cap[:, :, 2] == fz[:, None]).all()


def test_the_angle_decides_what_is_smooth():
    v, t, ns = cylinder(40)                              # strips 9 degrees apart
    fn = face_normals(v, t)
    assert angle(corners(v, t, angle=math.radians(5.0)), fn[:, None, :]).max() < 1e-3      # every strip flat
    assert angle(corners(v, t)[:ns], fn[:ns, None, :]).max() == pytest.approx(4.5, abs=0.01)
    v10, t10, _ns = cylinder(10)                         # strips 36 degrees apart: sharp
    assert angle(corners(v10, t10), face_normals(v10, t10)[:, None, :]).max() < 1e-3
    assert CN.SHARP_ANGLE == pytest.approx(math.radians(30.0))


# ---------------------------------------------------------------------------
# needles
# ---------------------------------------------------------------------------

def plate():
    """A 10 x 1 x 1 plate whose top is a fan from one corner over points on its edges: long thin triangles, and
    two triangles without area along the front edge (three points on one line), next to the front wall."""
    top = [(0, 0), (3, 0), (6, 0), (10, 0), (10, 1), (5, 1), (2, 1), (1, 1), (0.5, 1), (0, 1)]
    v = [(x, y, 0.0) for x, y in top] + [(0, 0, -1), (10, 0, -1), (10, 1, -1), (0, 1, -1)]
    t = [(0, i, i + 1) for i in range(1, len(top) - 1)]                      # the top (+Z); the first two: no area
    a, b, c, d = 10, 11, 12, 13
    t += [(a, b, 3), (a, 3, 2), (a, 2, 1), (a, 1, 0)]                        # the front wall (-Y)
    t += [(b, c, 4), (b, 4, 3)]                                              # right (+X)
    t += [(c, d, 9), (c, 9, 8), (c, 8, 7), (c, 7, 6), (c, 6, 5), (c, 5, 4)]  # back (+Y)
    t += [(d, a, 0), (d, 0, 9)]                                              # left (-X)
    t += [(a, d, c), (a, c, b)]                                              # bottom (-Z)
    return np.array(v, float), np.array(t), 8                                # 8 top triangles


@pytest.mark.parametrize("as_milled", [False, True])
def test_long_thin_triangles_and_needles_stay_flat(as_milled):
    v, t, ntop = plate()
    rot = np.eye(3)
    if as_milled:                                        # rounding gives the needles a (wrong) direction and area
        v, rot = turned(v * 0.01)
    fn = face_normals(v, t)
    n = corners(v, t)
    up, front = rot @ (0, 0, 1.0), rot @ (0, -1.0, 0)
    real = np.ones(len(t), bool)
    real[:2] = False
    assert angle(fn[2:ntop], up).max() < 0.01 and angle(fn[ntop:ntop + 4], front).max() < 0.01
    # every corner of every real triangle is its face normal: the top (thin triangles 10 long) and all walls
    assert angle(n[real], fn[real][:, None, :]).max() < 0.01
    # the needles show as a piece of the top or of the front wall they lie between, nothing else
    off = np.minimum(angle(n[:2], up), angle(n[:2], front))
    assert off.max() < 0.01


def test_a_triangle_without_direction_never_gives_nan():
    v, t = cube()
    v = np.vstack([v, [(5, 5, 5), (5, 5, 5), (6, 5, 5), (np.nan, 0, 0)]])
    extra = [(8, 9, 10),                                 # two corners at one place
             (8, 8, 8),                                  # one vertex three times
             (0, 0, 1),                                  # a vertex twice, on the cube
             (0, 1, 11),                                 # a corner that is not a number
             (1, 3, 7)]                                  # a real triangle again (the cube's side, doubled)
    t2 = np.vstack([t, extra])
    with np.errstate(all="ignore"):
        n = CN.corner_normals(v, t2)
    assert n.shape == (len(t2) * 3, 3) and np.isfinite(n).all()
    assert np.abs(np.linalg.norm(n.astype(np.float64), axis=1) - 1.0).max() < 1e-5
    n = n.reshape(-1, 3, 3)
    assert n[len(t)].tolist() == [[0, 0, 1]] * 3, "alone and without a direction: +Z"
    # only needles, nothing real anywhere
    only = CN.corner_normals(np.array([(0, 0, 0), (1, 0, 0), (2, 0, 0)], float), np.array([(0, 1, 2), (2, 1, 0)]))
    assert only.tolist() == [[0, 0, 1]] * 6


def test_a_needle_does_not_join_floor_and_wall():
    """A step: floor, wall, upper floor. Needles lie along both edges of the wall (points in line). The floors
    stay flat and the wall keeps its own direction - Blender's smooth-by-angle leaned them here."""
    xs = [0.0, 0.3, 0.55, 1.0]                           # points along the edges (y = 0 and y = 1 sides)
    lo = [(x, 0, 0) for x in xs]                         # the lower edge of the wall, z = 0, at y = 0
    hi = [(x, 0, 1) for x in xs]                         # its upper edge
    v = np.array(lo + hi + [(0, -1, 0), (1, -1, 0), (0, 1, 1), (1, 1, 1)], float)
    f0, f1, u0, u1 = 8, 9, 10, 11
    t = [(f0, f1, 3), (f0, 3, 0),                        # lower floor (+Z), two big triangles ...
         (0, 3, 2), (0, 2, 1),                           # ... and two needles along its edge to the wall
         (0, 3, 7), (0, 7, 4),                           # the wall (-Y), two big triangles ...
         (4, 7, 6), (4, 6, 5),                           # ... and two needles along its upper edge
         (4, 7, u1), (4, u1, u0)]                        # the upper floor (+Z)
    t = np.array(t)
    for vv, rot in ((v, np.eye(3)), turned(v * 0.02)):
        fn = face_normals(vv, t)
        n = corners(vv, t)
        real = [0, 1, 4, 5, 8, 9]
        assert angle(n[real], fn[real][:, None, :]).max() < 0.01
        up, wall = rot @ (0, 0, 1.0), rot @ (0, -1.0, 0)
        assert np.minimum(angle(n[[2, 3, 6, 7]], up), angle(n[[2, 3, 6, 7]], wall)).max() < 0.01


# ---------------------------------------------------------------------------
# smooth by angle: what is right at a shallow edge
# ---------------------------------------------------------------------------

def _floor_and_chamfer(width: float):
    """A 10 x 10 floor, a chamfer ``width`` wide rising 20 degrees along one edge (below the angle), then a face
    40 degrees steeper (above it)."""
    c20, s20 = width * math.cos(math.radians(20)), width * math.sin(math.radians(20))
    c60, s60 = math.cos(math.radians(60)), math.sin(math.radians(60))
    v = np.array([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),                    # floor
                  (10 + c20, 0, s20), (10 + c20, 10, s20),                           # top of the chamfer
                  (10 + c20 + c60, 0, s20 + s60), (10 + c20 + c60, 10, s20 + s60)])  # top of the steep face
    t = np.array([(0, 1, 2), (0, 2, 3), (1, 4, 5), (1, 5, 2), (4, 6, 7), (4, 7, 5)])
    fn = face_normals(v, t)
    assert angle(fn[2], fn[0]) == pytest.approx(20.0) and angle(fn[4], fn[2]) == pytest.approx(40.0)
    n = corners(v, t)
    by_vertex = {}
    for f in range(len(t)):
        for k in range(3):
            by_vertex.setdefault((int(t[f, k]), f // 2), []).append(n[f, k])
    return fn, by_vertex


def test_floor_meeting_a_wide_shallow_chamfer_blends_at_that_edge():
    """Floor and chamfer about as big as each other (the chamfer 4 wide): smooth by angle – at the edge between
    them both get the middle direction (10 degrees from each: every plane counts once, though the floor has two
    triangles at one end of the edge and one at the other). The floor's far corners touch nothing else and stay
    exactly flat. Across the 40 degree edge nothing is blended."""
    fn, by_vertex = _floor_and_chamfer(4.0)
    mid = (fn[0] + fn[2]) / np.linalg.norm(fn[0] + fn[2])
    for vert in (1, 2):                                   # the shared edge: floor (0) and chamfer (1) agree
        for face in (0, 1):
            assert angle(by_vertex[(vert, face)], mid).max() < 0.01
    for vert in (0, 3):                                   # the far corners of the floor
        assert angle(by_vertex[(vert, 0)], fn[0]).max() < 1e-3
    for vert in (4, 5):                                   # the 40 degree edge: each side keeps its own
        assert angle(by_vertex[(vert, 1)], fn[2]).max() < 1e-3
        assert angle(by_vertex[(vert, 2)], fn[4]).max() < 1e-3
    for vert in (6, 7):
        assert angle(by_vertex[(vert, 2)], fn[4]).max() < 1e-3


def test_big_floor_next_to_a_small_shallow_face_stays_flat():
    """The same with a chamfer 1 wide – a tenth of the floor, like the fan at the end of a V-groove next to its
    flank: the big face keeps exactly its own normal at every corner. The small face is 20 degrees steeper, more
    than a rounding's first strip (``RUN_IN``): it keeps its say at the edge they share (the middle direction),
    so the edge shows as the shallow crease it is."""
    fn, by_vertex = _floor_and_chamfer(1.0)
    mid = (fn[0] + fn[2]) / np.linalg.norm(fn[0] + fn[2])
    for vert in (0, 1, 2, 3):
        assert angle(by_vertex[(vert, 0)], fn[0]).max() < 1e-3
    for vert in (1, 2):
        assert angle(by_vertex[(vert, 1)], mid).max() < 0.01
    for vert in (4, 5):
        assert angle(by_vertex[(vert, 1)], fn[2]).max() < 1e-3
        assert angle(by_vertex[(vert, 2)], fn[4]).max() < 1e-3


def zipper(lower, upper, x):
    """Triangles of the strip between two rows of points (numbers ``lower`` and ``upper``, positions ``x`` along
    the strip), walking along both and always taking the point further back next. Normal: lower -> upper turns left."""
    t, i, j = [], 0, 0
    while i < len(lower) - 1 or j < len(upper) - 1:
        if j == len(upper) - 1 or (i < len(lower) - 1 and x[lower[i + 1]] <= x[upper[j + 1]]):
            t.append((lower[i], lower[i + 1], upper[j]))
            i += 1
        else:
            t.append((lower[i], upper[j + 1], upper[j]))
            j += 1
    return t


def roof(xa, xr, xb, tilt=10.0):
    """Two flat strips meeting along a ridge (the X axis), ``tilt`` degrees apart, cut into uneven triangles:
    points at ``xa`` on the outer edge of strip A (y = -1), ``xr`` on the ridge, ``xb`` on B's outer edge."""
    c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    v = [(x, -1.0, 0.0) for x in xa] + [(x, 0.0, 0.0) for x in xr] + [(x, c, -s) for x in xb]
    ia = list(range(len(xa)))
    ir = list(range(len(xa), len(xa) + len(xr)))
    ib = list(range(len(xa) + len(xr), len(v)))
    x = [p[0] for p in v]
    ta, tb = zipper(ia, ir, x), zipper(ir, ib, x)
    return np.array(v, float), np.array(ta + tb), len(ta), ir


def test_every_vertex_along_an_edge_gets_the_same_normal():
    """The edge between two strips of a round wall, the strips cut into odd triangles (as later cuts leave them):
    1 to 4 triangles of a strip at a ridge vertex, corner angles from 6 to 170 degrees. Every plane counts once,
    so all along the ridge the normal is the middle of the two - weights by area or corner angle would differ
    from vertex to vertex and show as ripples on the wall."""
    v, t, na, ridge = roof([0, 0.2, 9.7, 10], [0, 1, 2.5, 3, 7, 7.1, 10], [0, 5, 5.5, 6, 10])
    fn = face_normals(v, t)
    assert angle(fn[0], fn[na]) == pytest.approx(10.0)
    mid = (fn[0] + fn[na]) / np.linalg.norm(fn[0] + fn[na])
    n = corners(v, t)
    on_ridge = np.isin(t, ridge)
    assert on_ridge.sum() > 20
    assert angle(n[on_ridge], mid).max() < 0.01
    assert angle(n[~on_ridge], np.repeat(fn, 3, axis=0).reshape(-1, 3, 3)[~on_ridge]).max() < 1e-3   # outer edges


def test_a_seam_between_two_tiles_does_not_show():
    """The same two strips as two tiles with their own vertices, the seam running slanted across them: on both
    sides of the seam the ridge vertex gets the same normal (per tile, without welding)."""
    v1, t1, na1, r1 = roof([0, 1, 3], [0, 2, 5], [0, 4, 7])                   # ends at the seam x = 5 + 2 y
    v2, t2, na2, r2 = roof([3, 8, 10], [5, 6, 10], [7, 9, 10])                # starts there
    n1, n2 = corners(v1, t1), corners(v2, t2)
    fn = face_normals(v1, t1)
    mid = (fn[0] + fn[na1]) / np.linalg.norm(fn[0] + fn[na1])
    at1, at2 = n1[t1 == r1[-1]], n2[t2 == r2[0]]
    assert len(at1) >= 2 and len(at2) >= 2
    assert angle(at1, mid).max() < 0.01 and angle(at2, mid).max() < 0.01
    # welded into one mesh it is the same
    v, t = np.vstack([v1, v2]), np.vstack([t1, t2 + len(v1)])
    both = corners(v, t, weld=True)
    assert angle(both, np.vstack([n1, n2])).max() < 0.01


def test_weld_joins_vertices_at_the_same_place():
    v, t, ns = cylinder(40)
    shared = corners(v, t)
    soup_v, soup_t = v[t].reshape(-1, 3), np.arange(len(t) * 3).reshape(-1, 3)     # every triangle its own points
    fn = face_normals(v, t)
    assert angle(corners(soup_v, soup_t), fn[:, None, :]).max() < 1e-3             # not welded: all flat
    assert angle(corners(soup_v, soup_t, weld=True), shared).max() < 1e-3
    far = soup_v * 400.0 + 7000.0                        # too big for one whole number per place: the slow way
    assert angle(corners(far, soup_t, weld=True), shared).max() < 1e-3


# ---------------------------------------------------------------------------
# big fans, speed
# ---------------------------------------------------------------------------

def cone(n, r=1.0, h=1.0):
    a = np.arange(n) * 2 * math.pi / n
    v = np.vstack([np.c_[r * np.cos(a), r * np.sin(a), np.zeros(n)], [(0, 0, h), (0, 0, 0)]])
    i = np.arange(n)
    j = (i + 1) % n
    return v, np.vstack([np.c_[i, j, np.full(n, n)], np.c_[np.full(n, n + 1), j, i]]), n


@pytest.mark.parametrize("n", [20, 1500])
def test_the_tip_of_a_cone(n):
    """Many triangles round one vertex (1,500: more than fit in one go). Each keeps to its own side of the cone at
    the tip - it blends with its neighbours within the angle only, not with the far side."""
    v, t, ns = cone(n)
    assert n * n > CN.PAIRS or n == 20
    nn = corners(v, t)
    fn = face_normals(v, t)
    tip = nn[:ns, 2]
    assert angle(tip, fn[:ns]).max() < 15.0
    flat = np.hypot(tip[:, 0], tip[:, 1])
    assert angle(tip[:, :2] / flat[:, None], fn[:ns, :2] / np.linalg.norm(fn[:ns, :2], axis=1)[:, None]).max() < 0.05
    assert np.ptp(tip[:, 2]) < 1e-5, "the same all round"
    assert (nn[ns:] == (0, 0, -1)).all(), "the base is flat, also round its middle point"


def test_small_and_big_goes_give_the_same(monkeypatch):
    v, t, _ns = cylinder(40)
    v2, t2, _n2 = cone(30)
    vp, tp, _np = plate()
    vp, _rot = turned(vp * 0.01)
    meshes = ((v, t), (v2, t2), (vp, tp))
    whole = [CN.corner_normals(a, b) for a, b in meshes]
    for pairs in (10, 2000):                             # every fan of 4 or more one at a time; several goes per size
        monkeypatch.setattr(CN, "PAIRS", pairs)
        assert all(np.abs(CN.corner_normals(a, b) - w).max() < 1e-6 for (a, b), w in zip(meshes, whole))


def test_twenty_thousand_triangles_are_quick():
    """No loop over triangles or vertices: a 20,000-triangle surface takes about 12 ms on the web machine
    (measured, task 0061); the limit here only catches a loop."""
    g = 101
    x, y = np.meshgrid(np.linspace(0, 0.1, g), np.linspace(0, 0.1, g))
    v = np.c_[x.ravel(), y.ravel(), 0.004 * np.sin(x.ravel() * 80) * np.cos(y.ravel() * 60)].astype(np.float32)
    i = (np.arange(g - 1)[:, None] * g + np.arange(g - 1)[None, :]).ravel()
    t = np.vstack([np.c_[i, i + 1, i + g + 1], np.c_[i, i + g + 1, i + g]]).astype(np.int32)
    assert len(t) == 20000
    best = 1e9
    for _ in range(3):
        t0 = time.perf_counter()
        n = CN.corner_normals(v, t)
        best = min(best, time.perf_counter() - t0)
    assert best < 0.25, f"{best * 1000:.0f} ms"
    assert angle(n, np.repeat(face_normals(v, t), 3, axis=0)).max() < 15.0        # a smooth surface


# ---------------------------------------------------------------------------
# a milled block (the core's own booleans)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def milled():
    """A 200 x 200 x 40 mm block: ball-mill passes 3 mm deep slanting across it, flat slots 5 mm deep across
    those, cut in tiles of at most 4,000 triangles: [(verts, tris, source, the tile's box lo, hi)] per tile."""
    mf = pytest.importorskip("manifold3d")
    from fresing_render.core import machining as M
    stock = mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.03))
    wp = M.Workpiece(stock, None, "NORMAL")
    wp.tile_max = 4000
    ball, flat = [], []
    for i, y in enumerate(np.arange(-0.06, 0.0601, 0.012)):
        x0, x1 = (-0.08, 0.08) if i % 2 == 0 else (0.08, -0.08)
        ball += [(x0, y, 0.08), (x0, y, 0.067), (x1, y + 0.02, 0.067), (x1, y + 0.02, 0.08)]
    for x in (-0.05, 0.0, 0.05):
        flat += [(x, -0.07, 0.08), (x, -0.07, 0.065), (x + 0.01, 0.07, 0.065), (x + 0.01, 0.07, 0.08)]
    paths, cutters = [], []
    for tool, o, t0 in ((M.Tool("BALL", 3 * MM, 30 * MM), ball, 0.0), (M.Tool("FLAT", 5 * MM, 40 * MM), flat, 1e3)):
        o = np.array(o)
        paths.append(M.Path(t0 + np.arange(len(o), dtype=float), o, np.tile([0.0, 0.0, 1.0], (len(o), 1))))
        cutters.append(M.Cutter(tool, "NORMAL"))
    tl = M.Timeline(wp, cutters, paths, "NORMAL")
    return [wp._tile_mesh(t.solid)[:3] + (t.lo, t.hi) for t in tl.at(1e9) if t.ntri]


def test_milled_block_level_faces_are_flat(milled):
    assert len(milled) >= 3, "several tiles"
    thin_seen = 0
    for v, t, src, lo, hi in milled:
        n = corners(v, t, skip=CN.seam_faces(v, t, lo, hi))
        fn, _trust, _fuzz, thin, _e = CN._faces(v.astype(np.float64), t.astype(np.intp))
        thin_seen += int(thin.sum())
        level = (np.abs(fn[:, 2]) > 1 - 1e-9) & ~thin    # the top, the bottom, the slots' floors
        assert level.sum() > 20
        assert angle(n[level], fn[level][:, None, :]).max() < 0.01
        uncut = (src >= 0) & ~thin                       # the block's own six faces
        assert angle(n[uncut], fn[uncut][:, None, :]).max() < 0.01
        # nothing is shaded across a sharp edge: no corner further from its face than the angle
        assert angle(n[~thin], fn[~thin][:, None, :]).max() < 30.0
        # a needle takes a direction that is there: one of the real triangles' at one of its three vertices
        real_at = {}
        for f in np.flatnonzero(~thin):
            for vert in t[f]:
                real_at.setdefault(int(vert), []).append(f)
        for f in np.flatnonzero(thin):
            near = [g for vert in t[f] for g in real_at.get(int(vert), [])]
            if near:
                assert angle(n[f][:, None, :], fn[near][None, :, :]).min(axis=1).max() < 30.0
    assert thin_seen > 0, "the booleans left needles (if not, this test checks nothing about them)"


def seam_differences(milled, skip: bool) -> np.ndarray:
    """At every place where two tiles meet: the largest angle between the normals the two tiles give the same
    face there (degrees). Per tile, nothing welded."""
    v = np.concatenate([m[0] for m in milled])
    off = np.cumsum([0] + [len(m[0]) for m in milled])
    t = np.concatenate([m[1] + o for m, o in zip(milled, off)])
    caps = [CN.seam_faces(m[0], m[1], m[3], m[4]) for m in milled]
    n = np.concatenate([CN.corner_normals(m[0], m[1], skip=c if skip else None)
                        for m, c in zip(milled, caps)]).astype(np.float64)
    tile = np.concatenate([np.full(len(m[1]) * 3, i) for i, m in enumerate(milled)])
    fn, _trust, _fuzz, thin, _e = CN._faces(v.astype(np.float64), t.astype(np.intp))
    seen = ~thin & ~np.concatenate(caps)
    place = CN._weld(v.astype(np.float64))[t].reshape(-1)
    order = np.argsort(place, kind="stable")
    cuts = np.flatnonzero(np.r_[True, place[order][1:] != place[order][:-1], True])
    worst = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        c = order[a:b]
        c = c[seen[c // 3]]
        if len(set(tile[c].tolist())) < 2:
            continue
        same = (fn[c // 3] @ fn[c // 3].T > math.cos(math.radians(0.5))) & (tile[c][:, None] != tile[c][None, :])
        if same.any():
            worst.append(float(angle(n[c][:, None, :], n[c][None, :, :])[same].max()))
    return np.array(worst)


def test_milled_block_seams_between_tiles(milled):
    """Vertices are not shared between tiles. Where a seam cuts a round wall, the same face on both sides must get
    the same normal - without welding, as long as the faces that close a tile inside the material are skipped.
    With them a wall that crosses the seam within 30 degrees leans towards the seam, another way on each side."""
    caps = [CN.seam_faces(v, t, lo, hi) for v, t, _s, lo, hi in milled]
    assert all(c.any() for c in caps), "every tile has a seam"
    for (v, t, src, lo, hi), c in zip(milled, caps):
        fn = face_normals(v, t)
        real = c & (np.linalg.norm(np.cross(v[t][:, 1] - v[t][:, 0], v[t][:, 2] - v[t][:, 0]), axis=1) > 1e-12)
        assert (np.abs(fn[real]).max(axis=1) > 1 - 1e-6).all(), "seam faces lie in a side of the box"
        assert not c[src >= 0].any(), "the block's own faces are never seam faces"
    worst = seam_differences(milled, skip=True)
    assert len(worst) > 100, "the seams cross the cuts"
    # (a seam can cut the one triangle that showed how far a strip reaches from its edge: a single vertex may then
    # be judged another way on the two sides - a faint kink at one point, not a line along the seam)
    differ = int((worst >= 0.1).sum())
    assert differ <= 0.02 * len(worst) and worst.max() < 5.0, \
        f"{differ} of {len(worst)} seam vertices differ, most {worst.max():.2f}"
    without = seam_differences(milled, skip=False)
    assert without.max() > 2.0, "the reason for seam_faces (if this fails the skip may no longer be needed)"


def test_skipped_faces_pull_nothing_and_stay_flat():
    """A wall leaning 20 degrees against a flat face that is marked as not seen: each keeps its own direction;
    unmarked they blend. A needle between them takes the wall's direction, not the hidden face's."""
    c, s_ = math.cos(math.radians(20)), math.sin(math.radians(20))
    v = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (1 + c, 0, s_), (1 + c, 1, s_), (1, 0.5, 0)], float)
    t = np.array([(0, 1, 2), (0, 2, 3),                  # the hidden face (+Z)
                  (1, 4, 5), (1, 5, 2),                  # the wall, 20 degrees from it
                  (1, 6, 2)])                            # a needle on the edge between them (no area)
    fn = face_normals(v, t)
    blended = corners(v, t)
    assert angle(blended[2, 0], fn[2]) == pytest.approx(10.0, abs=0.01)
    hidden = np.array([True, True, False, False, False])
    n = corners(v, t, skip=hidden)
    assert angle(n[:4], fn[:4, None, :]).max() < 1e-3
    assert angle(n[4], fn[2]).max() < 1e-3
    # seam_faces: the triangles in a side of the box, here z = 0
    assert CN.seam_faces(v, t, (-5, -5, 0), (5, 5, 5)).tolist() == [True, True, False, False, True]
    assert not CN.seam_faces(v, t, (-5, -5, -1), (5, 5, 5)).any()


# ---------------------------------------------------------------------------
# in Blender, on the test mill
# ---------------------------------------------------------------------------

def test_milled_slot_in_blender_floor_and_top_are_flat(tmp_path):
    """Mill the slot of tests/test_machining.py plus a shallower pass across it, write the normals as the mesh's
    custom normals (one per face corner) and read back what Blender shades with."""
    bpy = pytest.importorskip("bpy")
    pytest.importorskip("manifold3d")
    import addon_utils
    from mathutils import Vector

    import fresing_render
    from fresing_render.blender import animation, build, joints, machining

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    try:
        machining._RUNTIME.clear()
        sc = bpy.context.scene
        sc.fresing.out_folder = str(tmp_path)
        assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_mill.step"),
                                           quality="draft") == {"FINISHED"}

        def ob(name):
            return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)

        def click(o):
            for x in bpy.context.selected_objects:
                x.select_set(False)
            o.select_set(True)
            bpy.context.view_layer.objects.active = o

        for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
            o = ob(asm)
            joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
        a = sc.fresing.animations.add()
        a.name, a.tail = "Mill", 0.0
        for j, start, dur, to in (("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0),     # the slot
                                  ("X", 3.5, 0.5, 25.0), ("Y", 4.0, 0.5, -30.0), ("Z", 4.5, 0.5, -22.0),
                                  ("Y", 5.0, 2.0, 30.0), ("Z", 7.0, 0.5, 0.0)):                            # across
            b = a.blocks.add()
            b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
            b.use_from, b.to_dist = True, to * MM
        frames = animation.bake(sc, a)["frames"]
        click(ob("END MILL D10"))
        assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
        wp = ob("STOCK 200x200x40")
        click(wp)
        assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
        machining.sample(sc)
        sc.frame_set(frames)
        assert machining.refresh(sc, force=True)

        me = wp.data
        v = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", v)
        t = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", t)
        v, t = v.reshape(-1, 3), t.reshape(-1, 3)
        assert len(t) == len(me.polygons) > 200, "the milled mesh is triangles"
        n = CN.corner_normals(v, t)
        old = me.attributes.get("custom_normal")
        if old is not None:
            me.attributes.remove(old)
        attr = me.attributes.new("custom_normal", "FLOAT_VECTOR", "CORNER")
        attr.data.foreach_set("vector", n.reshape(-1))
        me.update()
        got = np.empty(len(me.loops) * 3, np.float32)
        me.corner_normals.foreach_get("vector", got)
        got = got.reshape(-1, 3)
        assert np.abs(got - n).max() < 1e-6, "Blender shades with the corner normals that were written"

        fn = face_normals(v, t)
        z = v[t][:, :, 2]
        thin = CN._faces(v.astype(np.float64), t.astype(np.intp))[3]
        got = got.reshape(-1, 3, 3)
        seen = 0
        for height, least in ((0.070, 20), (0.065, 4), (0.068, 4)):       # the top, the slot's floor, the pass across
            sel = (fn[:, 2] > 1 - 1e-6) & (np.abs(z - height).max(axis=1) < 1e-6) & ~thin
            assert sel.sum() >= least, f"faces at z = {height * 1000:.0f} mm"
            assert angle(got[sel], fn[sel][:, None, :]).max() < 0.5
            seen += int(sel.sum())
        assert seen > 40
        # the slot's round ends are smooth: their strips' corners lean towards each other, never past the angle
        wall = (np.abs(fn[:, 2]) < 1e-6) & ~thin
        lean = angle(got[wall], fn[wall][:, None, :])
        assert 4.0 < lean.max() < 30.0
    finally:
        fresing_render.unregister()


def test_straight_wall_runs_into_its_rounded_corner():
    """A wall 30 long, then a rounding of 9 degree strips 0.8 wide (the corner a round tool leaves): the wall is the
    flat face - exactly its own normal at every corner - and the rounding's first strip starts with the wall's
    direction at the edge they share, as on the CAD part. Between the strips of the rounding: the middle."""
    h = 5.0
    pts, x, y, a = [(0.0, 0.0), (30.0, 0.0)], 30.0, 0.0, 0.0
    for _k in range(4):
        a += math.radians(9.0)
        x, y = x + 0.8 * math.cos(a), y + 0.8 * math.sin(a)
        pts.append((x, y))
    v = np.array([(px, py, z) for px, py in pts for z in (0.0, h)])
    t = np.array([q for k in range(len(pts) - 1) for q in ((2 * k, 2 * k + 2, 2 * k + 3), (2 * k, 2 * k + 3, 2 * k + 1))])
    fn = face_normals(v, t)
    n = corners(v, t)
    assert angle(n[:2].reshape(-1, 3), fn[0]).max() < 1e-3                 # the wall: flat
    first = n[2:4].reshape(-1, 3)[[i for i, vert in enumerate(t[2:4].reshape(-1)) if vert in (2, 3)]]
    assert angle(first, fn[0]).max() < 1e-3                                # the rounding starts with the wall's
    between = n[2:4].reshape(-1, 3)[[i for i, vert in enumerate(t[2:4].reshape(-1)) if vert in (4, 5)]]
    mid = (fn[2] + fn[4]) / np.linalg.norm(fn[2] + fn[4])
    assert angle(between, mid).max() < 0.01                                # strip to strip: the middle, as before
