"""Task 0146: the height map for dense 3-axis programs (core/heightmap.py) and its place in the milling timeline
(core/machining.py, ``Timeline(fast=True)``). The independent tests are in test_heightmap_independent.py; here:
the pieces one by one, with numbers worked out by hand.

Stated tolerance, map against the exact booleans, at detail Normal: surfaces and straight / round walls within
0.03 mm (the booleans' own 40-sided bit is 0.009 mm off on Ø6); sharp outside corners of walls and anything thinner
than a grid cell up to one cell (0.2 mm)."""

import math

import numpy as np
import pytest

mf = pytest.importorskip("manifold3d")

from fresing_render.core import heightmap as H  # noqa: E402
from fresing_render.core import machining as M  # noqa: E402
from fresing_render.core import toolmarks as T  # noqa: E402

MM = 0.001
UP = np.array([0.0, 0.0, 1.0])


def brute(shape, a, b, pts, n=4001):
    """The swept bottom by trying the bit at many places along the move."""
    s = np.linspace(0.0, 1.0, n)[:, None]
    c = a[None, :] + s * (b - a)[None, :]
    out = np.full(len(pts), np.inf)
    for k in range(len(pts)):
        r = np.hypot(pts[k, 0] - c[:, 0], pts[k, 1] - c[:, 1])
        ok = r <= shape.R
        if ok.any():
            out[k] = np.min(c[ok, 2] + shape.f(r[ok]))
    return out


SHAPES = {
    "flat": M.Tool("FLAT", radius=3 * MM, length=0.03),
    "ball": M.Tool("BALL", radius=3 * MM, length=0.03),
    "bull": M.Tool("BULL", radius=4 * MM, length=0.03, corner=1.5 * MM),
    "vee": M.Tool("VEE", radius=4 * MM, length=0.03, angle=90.0),
    "drill": M.Tool("DRILL", radius=3 * MM, length=0.03, angle=118.0),
    "custom": M.Tool("CUSTOM", radius=4 * MM, length=0.02,
                     profile=((0.0, 1 * MM), (1 * MM, 3 * MM), (3 * MM, 4 * MM), (0.02, 4 * MM))),
}


def shape(name):
    tool = SHAPES[name]
    return H.shape_of(tool, M.Cutter(tool, "NORMAL").profile)


@pytest.mark.parametrize("name", sorted(SHAPES))
@pytest.mark.parametrize("move", ["level", "down", "up", "plunge"])
def test_sweep_height_is_the_lowest_place_of_the_bit(name, move):
    sh = shape(name)
    assert sh is not None
    a = np.array([0.0, 0.0, 0.0])
    b = {"level": (0.012, 0.004, 0.0), "down": (0.012, 0.004, -0.003), "up": (0.012, 0.004, 0.005),
         "plunge": (0.0, 0.0, -0.004)}[move]
    b = np.array(b)
    rng = np.random.default_rng(5)
    pts = np.stack([rng.uniform(-0.006, 0.018, 400), rng.uniform(-0.006, 0.010, 400)], axis=1)
    got = H.sweep_height(sh, a[0], a[1], b[0], b[1], a[2], b[2], pts[:, 0], pts[:, 1])
    want = brute(sh, a, b, pts)
    both = np.isfinite(got) & np.isfinite(want)
    # (the brute force steps 3 µm along the move: at the footprint's edge it can miss a point by that much)
    edge = np.isfinite(got) != np.isfinite(want)
    assert edge.sum() <= 6
    assert both.sum() > 20
    assert np.abs(got[both] - want[both]).max() < 3e-6


def test_shapes_the_map_cannot_hold_are_refused():
    tslot = M.Tool("CUSTOM", radius=5 * MM, length=0.02, profile=((0, 5 * MM), (2 * MM, 5 * MM), (2 * MM, 2 * MM),
                                                                  (0.02, 2 * MM)))
    assert H.shape_of(tslot, M.Cutter(tslot, "NORMAL").profile) is None            # narrower higher up: undercut
    shank = M.Tool("CUSTOM", radius=5 * MM, length=0.02, profile=((0, 2 * MM), (5 * MM, 2 * MM), (5 * MM, 5 * MM),
                                                                  (0.02, 5 * MM)))
    assert H.shape_of(shank, M.Cutter(shank, "NORMAL").profile) is None            # a wider shank: two pieces
    assert shape("ball").kind == H.BALL and shape("vee").kind == H.CONE and shape("custom").kind == H.PROFILE


def ring_map(tile=H.TILE):
    """A ring pocket: flat Ø4 round a circle of 9 mm in 72 moves, 5 mm deep."""
    sh = H.shape_of(M.Tool("FLAT", radius=2 * MM, length=0.03))
    ang = np.linspace(0, 2 * np.pi, 73)
    pts = np.stack([0.02 + 0.009 * np.cos(ang), 0.02 + 0.009 * np.sin(ang), np.full(73, -0.005)], axis=1)
    hm = H.HeightMap(0.0, 0.0, 0.2 * MM, 224 // tile, 224 // tile, 0.0, -0.02, 5e-6, tile=tile)
    n = len(pts) - 1
    hm.set_moves([sh], np.zeros(n, int), pts[:-1, :2], pts[1:, :2], pts[:-1, 2], pts[1:, 2], np.arange(n),
                 1000 + np.arange(n))
    return hm, n


def test_walls_stand_where_the_tool_went():
    """Every vertex of a ring pocket's mesh is on the top outside the ring, on the floor inside it, or on one of
    its two walls - within 0.02 mm (the moves are chords of the circle: 0.009 mm). The pass that came by last
    owns a floor node, but the wall is the edge of the pass the node lies deepest in (0.19 mm apart here)."""
    hm, n = ring_map()
    hm.goto(n)
    seen = 0
    for J, I in np.argwhere(hm.cut_tiles()):
        v, t, mv = hm.surface(int(J), int(I))
        v = v[np.unique(t)]
        r = np.hypot(v[:, 0] - 0.02, v[:, 1] - 0.02)
        top = v[:, 2] > -1e-4
        off = np.where(top, np.maximum(0, np.minimum(11 * MM - r, r - 7 * MM)), np.maximum(r - 11 * MM, 7 * MM - r))
        assert off.max() < 0.02 * MM
        assert np.all(top | (np.abs(v[:, 2] + 0.005) < 1e-9))            # nothing half-way up a wall
        seen += len(v)
    assert seen > 2000


def closed(verts, tris) -> bool:
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    fwd = {(int(a), int(b)) for a, b in e}
    return len(fwd) == len(e) and all((b, a) in fwd for a, b in fwd)


def test_tiles_are_closed_solids_that_meet_vertex_for_vertex():
    hm, n = ring_map()
    hm.goto(n)
    border = {}
    for J, I in np.argwhere(hm.cut_tiles()):
        J, I = int(J), int(I)
        _serial, v, t, mv = hm.mesh(J, I)
        assert closed(v, t), (J, I)
        p = v[t]
        vol = np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6.0
        assert vol > 0
        top = t[mv > -2]
        side = np.unique(t[mv == -2])
        on = np.intersect1d(np.unique(top), side)                        # the top's vertices on the tile's border
        border[(J, I)] = {tuple(np.round(q, 12)) for q in v[on]}
    pairs = 0
    for (J, I), mine in border.items():
        for other in ((J, I + 1), (J + 1, I)):
            if other not in border:
                continue
            x0, y0, x1, y1 = hm.box(J, I)
            # the vertices on the shared side (a node moves at most a cell off its line; not the corners' other
            # sides) must be the same set in both tiles
            if other[1] == I + 1:
                near = lambda q: abs(q[0] - x1) < 0.3 * MM and y0 + 0.5 * MM < q[1] < y1 - 0.5 * MM     # noqa: E731
            else:
                near = lambda q: abs(q[1] - y1) < 0.3 * MM and x0 + 0.5 * MM < q[0] < x1 - 0.5 * MM     # noqa: E731
            a = {q for q in mine if near(q)}
            b = {q for q in border[other] if near(q)}
            assert a == b, ((J, I), other, len(a ^ b))
            pairs += 1
    assert pairs > 10


def test_the_map_is_the_same_however_it_is_reached():
    hm, n = ring_map()
    hm.every = 16                                    # (kept states every 16 moves, to go back from)
    hm.goto(40, [(40, (hm.b[40, 0], hm.b[40, 1], hm.z1[40]))])
    first = [a.copy() for a in hm._arrays()]
    meshes = {(int(J), int(I)): hm.mesh(int(J), int(I))[1:] for J, I in np.argwhere(hm.cut_tiles())}
    hm.goto(n)
    hm.goto(7)
    hm.goto(40, [(40, (hm.b[40, 0], hm.b[40, 1], hm.z1[40]))])
    for a, b in zip(first, hm._arrays()):
        assert np.array_equal(a, b)
    again = {(int(J), int(I)): hm.mesh(int(J), int(I))[1:] for J, I in np.argwhere(hm.cut_tiles())}
    assert meshes.keys() == again.keys()
    for key in meshes:
        for a, b in zip(meshes[key], again[key]):
            assert np.array_equal(a, b)
    # a half-done move is the same as the whole move when it has come to its end
    hm.goto(41)
    for a, b in zip(first, hm._arrays()):
        if a.dtype.kind == "f":
            assert np.allclose(a, b, atol=1e-12)


# ---------------------------------------------------------------------------
# in the timeline
# ---------------------------------------------------------------------------

def block(size=(0.06, 0.04, 0.02), origin=(0.0, 0.0, -0.02)):
    return mf.Manifold.cube(size).translate(origin)


def timeline(tool, pts, fast, stock=None, finished=None, detail="NORMAL", axis=UP):
    pts = np.asarray(pts, float)
    stock = block() if stock is None else stock
    path = M.Path(np.arange(len(pts)) + 1.0, pts, np.tile(axis, (len(pts), 1)))
    return M.Timeline(M.Workpiece(stock, finished, detail), [M.Cutter(tool, detail)], [path], detail, fast=fast), stock


def wavy(nx=41, passes=21, step=0.5 * MM):
    """A small finishing raster: a ball follows a wavy surface 1 to 3 mm deep (820 points, about 500 moves)."""
    pts = []
    for k in range(passes):
        xs = np.linspace(0.005, 0.055, nx)
        if k % 2:
            xs = xs[::-1]
        y = 0.01 + k * step
        z = -0.002 + 0.001 * np.sin(xs * 180.0) * math.cos(y * 150.0)
        pts += [(x, y, zz) for x, zz in zip(xs, z)]
    return np.array(pts)


def surface_points(tl, T):
    """Points on the cut surface (centres of the triangles a cutter made) and all triangles of the workpiece."""
    v, t, src, mv = tl.mesh_at(T, moves=True)
    p = v[t].astype(float)
    return p[mv >= 0].mean(axis=1), p                 # (faces a move made: not the seams inside the material)


def distance_to_triangles(q, tri) -> np.ndarray:
    """Distance from each point to the nearest of the triangles (brute force, in chunks; enough for a test)."""
    a, ab, ac = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    n = np.cross(ab, ac)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    d00, d01, d11 = (ab * ab).sum(1), (ab * ac).sum(1), (ac * ac).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-300)
    out = np.full(len(q), np.inf)
    cen = tri.mean(axis=1)
    rad = np.linalg.norm(tri - cen[:, None, :], axis=2).max(axis=1)
    for k in range(len(q)):
        near = np.linalg.norm(cen - q[k], axis=1) < rad + 0.5 * MM
        if not near.any():
            continue
        w = q[k] - a[near]
        d20, d21 = (w * ab[near]).sum(1), (w * ac[near]).sum(1)
        u = (d11[near] * d20 - d01[near] * d21) / den[near]
        v = (d00[near] * d21 - d01[near] * d20) / den[near]
        inside = (u >= 0) & (v >= 0) & (u + v <= 1)
        plane = np.abs((w * n[near]).sum(1))
        # outside the triangle: the nearest of its three corners or edges, by sampling the edges
        best = np.where(inside, plane, np.inf)
        for i, j in ((0, 1), (1, 2), (2, 0)):
            p0, e = tri[near][:, i], tri[near][:, j] - tri[near][:, i]
            s = np.clip(((q[k] - p0) * e).sum(1) / np.maximum((e * e).sum(1), 1e-300), 0, 1)
            best = np.minimum(best, np.linalg.norm(q[k] - (p0 + s[:, None] * e), axis=1))
        out[k] = best.min()
    return out


def test_a_thinly_spread_program_is_cut_exactly():
    """500 moves, but 2 mm long in passes 1.5 mm apart: the map would have more faces than the exact cut."""
    pts = []
    for k in range(17):
        xs = np.linspace(0.005, 0.055, 26)
        pts += [(x, 0.008 + k * 0.0015, -0.002 + 0.0005 * math.sin(x * 300.0)) for x in (xs if k % 2 == 0 else xs[::-1])]
    tl, _s = timeline(SHAPES["ball"], pts, fast=True)
    assert tl.stats.cutting_segments >= M.FAST_MIN_MOVES and tl.map is None
    assert M._MapSide.density(np.array([[0.0, 0.0]]), np.array([[0.004, 0.0]])) == pytest.approx(0.25)


def test_a_short_program_is_cut_exactly_as_before():
    """Fewer than FAST_MIN_MOVES moves: no map, the very same mesh."""
    pts = [(0.01, 0.01, 0.002), (0.01, 0.01, -0.003), (0.05, 0.03, -0.003), (0.05, 0.03, 0.002)]
    a, _s = timeline(SHAPES["flat"], pts, fast=True)
    b, _s = timeline(SHAPES["flat"], pts, fast=False)
    assert a.map is None
    for x, y in zip(a.mesh_at(4.0, marks=True, normals=True)[:4], b.mesh_at(4.0, marks=True, normals=True)[:4]):
        assert np.array_equal(x, y)


def test_a_dense_program_matches_the_exact_cut():
    pts = wavy()
    fast, stock = timeline(SHAPES["ball"], pts, fast=True)
    exact, _s = timeline(SHAPES["ball"], pts, fast=False)
    assert fast.map is not None and fast.stats.extra["map_moves"] >= M.FAST_MIN_MOVES
    T = float(len(pts))
    gone_f = stock.volume() - M.volume(fast.at(T))
    gone_e = stock.volume() - M.volume(exact.at(T))
    assert abs(gone_f - gone_e) < 0.004 * gone_e              # (the exact bit has 40 corners: 0.4 % smaller)
    qf, tf = surface_points(fast, T)
    qe, te = surface_points(exact, T)
    rng = np.random.default_rng(1)
    d1 = distance_to_triangles(qf[rng.choice(len(qf), 400, replace=False)], te)
    d2 = distance_to_triangles(qe[rng.choice(len(qe), 400, replace=False)], tf)
    # 0.03 mm, but for the steep strip under the rim where the ball cuts deeper than about 2/3 of its radius: nodes
    # 0.2 mm apart across a face steeper than 70 degrees are 0.6 to 1 mm apart on the face, and a chord of 1 mm on
    # a Ø6 ball sags 0.05 mm (a quarter of that at Fine)
    assert max(np.percentile(d1, 97), np.percentile(d2, 97)) < 0.03 * MM
    assert max(d1.max(), d2.max()) < 0.09 * MM, (d1.max() / MM, d2.max() / MM)
    # every tile is a closed solid the clash check can read
    for t in fast.at(T):
        assert t.solid.status() == mf.Error.NoError and t.solid.volume() > 0


def test_any_time_gives_the_same_mesh_again():
    pts = wavy()
    fast, stock = timeline(SHAPES["ball"], pts, fast=True)
    times = [200.0, 437.4, 820.0, 437.4, 12.25, 200.0, 437.4]
    seen = {}
    gone = {}
    for T in times:
        out = fast.mesh_at(T, moves=True, normals=True)
        if T in seen:
            for a, b in zip(seen[T], out):
                assert np.array_equal(a, b), T
        seen[T] = [np.array(x) for x in out]
        gone[T] = stock.volume() - M.volume(fast.at(T))
    assert gone[12.25] < gone[200.0] < gone[437.4] < gone[820.0]


def zigzag_pocket(passes=12, per=30, depth=-0.003):
    """A pocket by a flat Ø6: passes 2 mm apart, each cut in ``per`` short moves (the app reads a program so)."""
    pts = [(0.008, 0.008, 0.002)]
    for k in range(passes):
        xs = np.linspace(0.008, 0.050, per + 1)
        # (a little zig in y keeps the moves from being joined into one straight segment)
        ys = 0.008 + k * 0.002 + 0.00004 * (np.arange(per + 1) % 2)
        if k % 2:
            xs = xs[::-1]
        pts += [(x, y, depth) for x, y in zip(xs, ys)]
    pts.append((pts[-1][0], pts[-1][1], 0.002))
    return np.array(pts)


@pytest.fixture()
def any_density(monkeypatch):
    """(the small test programs are spread thinner than a real finishing program)"""
    monkeypatch.setattr(M, "FAST_MIN_DENSITY", 0.0)


def test_faces_know_their_move_and_get_their_marks(any_density):
    pts = zigzag_pocket()
    fast, _s = timeline(SHAPES["flat"], pts, fast=True)
    assert fast.map is not None
    T = float(len(pts))
    v, t, src, mv, marks = fast.mesh_at(T, marks=True)
    p = v[t].astype(float)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1)
    n /= np.maximum(area, 1e-30)[:, None]
    cen = p.mean(axis=1)
    floor = (src < 0) & (n[:, 2] > 0.999) & (np.abs(cen[:, 2] + 0.003) < 1e-6) & (area > 1e-9)
    wall = (src < 0) & (np.abs(n[:, 2]) < 0.02) & (cen[:, 2] > -0.0029) & (cen[:, 2] < -0.0001) & (mv >= 0)
    assert floor.sum() > 20 and wall.sum() > 50
    mk = fast.moves
    # the floor: the move named on a face really passed over it (within the bit's radius), at the floor's depth
    k = mv[floor]
    assert np.all(k >= 0)
    a, b = mk.o0[k], mk.o1[k]
    ab = b - a
    s = np.clip(((cen[floor] - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-30), 0, 1)
    d = np.linalg.norm((cen[floor] - (a + s[:, None] * ab))[:, :2], axis=1)
    # (a triangle at the foot of a wall reaches to the wall: the edge of the pass its corner lies deepest in, which
    # can be a cell outside the last pass that came by)
    assert d.max() < 3 * MM + 0.25 * MM
    assert np.allclose(a[:, 2], -0.003)
    # ... and where two passes overlap (they are 2 mm apart, the bit is 6 mm wide) the later one is named
    y = cen[floor][:, 1]
    row = np.clip(np.round((y - 0.008) / 0.002), 0, 11)
    named = np.round((a[:, 1] - 0.008) / 0.002)
    x = cen[floor][:, 0]
    inner = (y > 0.012) & (y < 0.026) & (x > 0.012) & (x < 0.046)     # (not at the passes' ends)
    assert inner.sum() > 10 and np.all(named[inner] >= row[inner])
    # marks: arcs on the floor of a flat-bottomed tool, lines along the tool on its walls
    kinds = marks[3][:, 0]
    assert np.all(kinds[floor] == T_ARCS)
    assert np.mean(kinds[wall] == T_FLANK) > 0.95


T_ARCS, T_FLANK = float(T.ARCS), float(T.FLANK)


def test_normals_of_the_map_are_flat_on_floors_and_level_on_walls(any_density):
    pts = zigzag_pocket()
    fast, _s = timeline(SHAPES["flat"], pts, fast=True)
    assert fast.map is not None
    v, t, src, mv, nrm = fast.mesh_at(float(len(pts)), moves=True, normals=True)
    assert np.isfinite(nrm).all()
    assert np.allclose(np.linalg.norm(nrm, axis=1), 1.0, atol=1e-4)
    p = v[t].astype(float)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1)
    n /= np.maximum(area, 1e-30)[:, None]
    cen = p.mean(axis=1)
    c = nrm.reshape(-1, 3, 3)
    floor = (src < 0) & (n[:, 2] > 0.999) & (np.abs(cen[:, 2] + 0.003) < 1e-6) & (area > 1e-10)
    assert np.all(c[floor][:, :, 2] > 0.99999)
    wall = (mv >= 0) & (np.abs(n[:, 2]) < 0.02) & (area > 1e-10) & (cen[:, 2] < -0.0002) & (cen[:, 2] > -0.0028)
    assert wall.sum() > 50
    assert np.abs(c[wall][:, :, 2]).max() < math.sin(math.radians(3.0))       # (2° at the cusp between two pass ends)


def test_moves_the_map_cannot_hold_stay_exact():
    """A tilted tool, and a tool whose top stays below the block's top (a tunnel), are not map moves."""
    pts = wavy()
    tilt = np.array([0.0, math.sin(math.radians(5)), math.cos(math.radians(5))])
    a, _s = timeline(SHAPES["ball"], pts, fast=True, axis=tilt)
    assert a.map is None
    short = M.Tool("BALL", radius=3 * MM, length=0.5 * MM)             # shorter than the cut is deep
    b, _s = timeline(short, pts, fast=True)
    assert b.map is None


def test_another_axis_and_a_block_somewhere_else():
    """The tool along -X of the workpiece, the block away from the origin: same answer as the exact cut."""
    base = wavy()
    # x, y, z of the raster become y, z, -x: the tool comes from the -X side
    pts = np.stack([-base[:, 2] + 0.10, base[:, 0] + 0.2, base[:, 1] - 0.3], axis=1)
    stock = mf.Manifold.cube((0.02, 0.06, 0.04)).translate((0.10, 0.2, -0.3))
    axis = np.array([-1.0, 0.0, 0.0])
    fast, _s = timeline(SHAPES["ball"], pts, fast=True, stock=stock, axis=axis)
    exact, _s = timeline(SHAPES["ball"], pts, fast=False, stock=stock, axis=axis)
    assert fast.map is not None
    T = float(len(pts))
    gone_f = stock.volume() - M.volume(fast.at(T))
    gone_e = stock.volume() - M.volume(exact.at(T))
    assert gone_e > 1e-7 and abs(gone_f - gone_e) < 0.004 * gone_e


def test_finished_part_is_never_cut():
    """'Finish at the CAD part': a slab the raster runs 1 to 3 mm into stays whole."""
    pts = wavy()
    slab = mf.Manifold.cube((0.03, 0.02, 0.0195)).translate((0.015, 0.012, -0.02))      # its top 0.5 mm below
    fast, stock = timeline(SHAPES["ball"], pts, fast=True, finished=slab)
    assert fast.map is not None
    T = float(len(pts))
    left = mf.Manifold.compose([t.solid if isinstance(t.solid, mf.Manifold) else t.solid for t in fast.at(T)])
    assert (slab - left).volume() < 1e-12 * 1e3                      # nothing of the slab is gone (< 1e-3 mm³)
    exact, _s = timeline(SHAPES["ball"], pts, fast=False, finished=slab)
    gone_f = stock.volume() - M.volume(fast.at(T))
    gone_e = stock.volume() - M.volume(exact.at(T))
    assert abs(gone_f - gone_e) < 0.006 * gone_e
    # the faces along the finished part are named after a move, as the exact cut names them
    v, t, src, mv = fast.mesh_at(T, moves=True)
    cen = v[t].astype(float).mean(axis=1)
    # (where the raster ran over the slab: y 13 .. 19 mm; further on the block above it is still whole)
    on_slab = (src < 0) & (np.abs(cen[:, 2] + 0.0005) < 1e-6) & (cen[:, 0] > 0.016) & (cen[:, 0] < 0.044) & \
        (cen[:, 1] > 0.013) & (cen[:, 1] < 0.019)
    assert on_slab.sum() > 0 and np.all(mv[on_slab] >= 0)


def test_side_cut_next_to_the_map():
    """A T-slot cutter (it undercuts: booleans) after a dense raster (the map): both show, at every time."""
    pts = wavy()
    tslot = M.Tool("CUSTOM", radius=5 * MM, length=0.02,
                   profile=((0, 5 * MM), (2 * MM, 5 * MM), (2 * MM, 2 * MM), (0.02, 2 * MM)))
    side = np.array([(-0.01, 0.03, -0.012), (0.03, 0.03, -0.012), (-0.01, 0.03, -0.012)])
    n = len(pts)
    stock = block()

    def make(fast):
        paths = [M.Path(np.arange(n) + 1.0, pts, np.tile(UP, (n, 1))),
                 M.Path(n + 1.0 + np.arange(3) * 5.0, side, np.tile(UP, (3, 1)))]
        return M.Timeline(M.Workpiece(stock, None, "NORMAL"), [M.Cutter(SHAPES["ball"], "NORMAL"),
                                                               M.Cutter(tslot, "NORMAL")], paths, "NORMAL", fast=fast)
    fast, exact = make(True), make(False)
    assert fast.map is not None and fast.stats.extra["map_moves"] < len(fast.segs)
    for T in (n + 3.5, float(n + 11), n * 0.5):
        gone_f = stock.volume() - M.volume(fast.at(T))
        gone_e = stock.volume() - M.volume(exact.at(T))
        assert abs(gone_f - gone_e) < 0.005 * gone_e, T
    # the undercut is there: a point under the slot's roof, inside the T's wide part, is air
    left = fast.at(float(n + 11))
    probe = mf.Manifold.cube((0.002, 0.0015, 0.001)).translate((0.02, 0.033, -0.0115))
    assert sum((t.solid ^ probe).volume() for t in left) < 1e-13


# ---------------------------------------------------------------------------
# task 0186: a map tile that is no closed solid never drops a column of the block
# ---------------------------------------------------------------------------

def test_ring_follows_the_top_where_two_border_vertices_stand_at_one_place():
    """A wall on the tile's border: E (its top) and F (its foot) at one place of the side B-C. Sorted by place alone
    the ring read A B E F C D; the top's border runs A B F E C D, and the side must follow it."""
    P = np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [1, 0.5, 1.0], [1, 0.5, 0.2]], float)
    A, B, C, D, E, F = range(6)
    tri = np.array([[A, B, F], [A, F, E], [A, E, C], [A, C, D]])
    assert H.HeightMap._ring_walk(np.array([A, B, E, F, C, D]), tri, P).tolist() == [A, B, F, E, C, D]
    right = np.array([A, B, F, E, C, D])
    assert H.HeightMap._ring_walk(right, tri, P).tolist() == right.tolist()
    # no two at one place: the ring as it was (the same array)
    ring = np.array([A, B, C, D])
    tri2 = np.array([[A, B, C], [A, C, D]])
    assert H.HeightMap._ring_walk(ring, tri2, P) is ring
    # a top whose border is not one loop through the ring: left alone
    odd = np.array([A, B, E, F, C, D])
    assert H.HeightMap._ring_walk(odd, tri[:2], P) is odd


def _broken(hm, which, plain_too=False):
    """``hm.mesh`` with the first top triangle of tile ``which`` left out (no closed solid any more); with
    ``plain_too`` its plain mesh too."""
    real = hm.mesh

    def mesh(J, I, plain=False):         # noqa: E741
        s, v, t, mv = real(J, I, plain=plain)
        if (J, I) == which and (plain_too or not plain):
            t, mv = t[1:], mv[1:]
        return s, v, t, mv
    return mesh


@pytest.mark.parametrize("plain_too", [False, True])
def test_a_tile_that_is_no_closed_solid_keeps_its_column(any_density, monkeypatch, plain_too):
    pts = zigzag_pocket()
    T = float(len(pts))
    good, stock = timeline(SHAPES["flat"], pts, fast=True)
    fast, _s = timeline(SHAPES["flat"], pts, fast=True)
    assert fast.map is not None
    hm = fast.map.hm
    good.at(T)
    which = tuple(int(x) for x in np.argwhere(good.map.hm.cut_tiles())[0])
    lo, hi = good.map._span(*which)
    # (proof the made tile is broken: a solid from it is empty)
    _s0, v, t, mv = hm.mesh(*which)
    assert fast.map._solid(v, t[1:], mv[1:]) is None
    monkeypatch.setattr(hm, "mesh", _broken(hm, which, plain_too))
    tiles = fast.at(T)
    for tile in tiles:
        assert tile.solid.status() == mf.Error.NoError and not tile.solid.is_empty()
    box = M._box(lo, hi)
    inside_good = sum((t.solid ^ box).volume() for t in good.at(T))
    inside_fast = sum((t.solid ^ box).volume() for t in tiles)
    extra = fast.stats.extra
    if plain_too:                                   # the tile's box: the block uncut there, never a hole
        assert extra.get("map_tiles_box") == 1 and not extra.get("map_tiles_plain")
        assert inside_fast == pytest.approx((stock ^ box).volume(), rel=1e-3)     # (pieces overlap a hair)
        assert inside_fast > inside_good
    else:                                           # its plain right triangles: the same cut, near enough
        assert extra.get("map_tiles_plain") == 1 and not extra.get("map_tiles_box")
        assert inside_fast == pytest.approx(inside_good, rel=2e-3)
    assert not good.stats.extra.get("map_tiles_plain") and not good.stats.extra.get("map_tiles_box")


def test_the_density_does_not_hang_on_rounding_noise():
    """Task 0249: a raster on whole millimetres, read once exactly and once a few nanometres off (a table that carries
    the block): the same density – the squares are not on the round numbers."""
    xs, ys = np.arange(-30, 31) * M.MM, np.arange(21) * 0.6 * M.MM
    a = np.array([(x, y) for y in ys for x in xs[:-1]])
    b = a + np.array((M.MM, 0.0))
    for noise in (1e-9, -1e-9, 7e-9):
        assert M._MapSide.density(a + noise, b + noise) == M._MapSide.density(a, b)
