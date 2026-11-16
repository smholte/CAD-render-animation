"""Task 0167: the tile thinning of the height map (core/heightmesh.py) and what the map does with it.

Strips along the passes, right triangles elsewhere; tiles that meet node for node (a forced node is fanned in, it never
makes a tile keep another); extra vertices on edges (a wall's foot over a rounded strip, a rib's second rim); the map
lying over the finished part. NumPy only (the last tests use Manifold through core/machining.py)."""

import math

import numpy as np
import pytest

from fresing_render.core import heightmesh as HM

MM = 0.001
N = 33                                   # nodes along a tile's side


def grid(z, cell=0.2 * MM):
    """(n, n, 3) nodes of a tile with heights ``z`` (n, n)."""
    i, j = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    return np.stack([j * cell, i * cell, z], axis=-1).astype(float)


def area_xy(P, tri):
    p = P.reshape(-1, 3)[tri]
    return 0.5 * ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))


def covers_tile(P, tri, cell=0.2 * MM):
    """The triangles cover the tile once, all turned up (seen from above)."""
    a = area_xy(P, tri)
    return bool((a > 0).all()) and abs(a.sum() - (32 * cell) ** 2) < 1e-12


def max_error(P, tri, ref):
    """How far the nodes ``ref`` (n, n, 3) lie from the triangulated surface, vertically."""
    p = P.reshape(-1, 3)
    out = 0.0
    q = ref.reshape(-1, 3)
    for t in tri:
        a, b, c = p[t]
        lo, hi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
        sel = np.flatnonzero((q[:, 0] >= lo[0] - 1e-12) & (q[:, 0] <= hi[0] + 1e-12) & (q[:, 1] >= lo[1] - 1e-12) &
                            (q[:, 1] <= hi[1] + 1e-12))
        if not len(sel):
            continue
        d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        l1 = ((q[sel, 0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (q[sel, 1] - a[1])) / d
        l2 = ((b[0] - a[0]) * (q[sel, 1] - a[1]) - (q[sel, 0] - a[0]) * (b[1] - a[1])) / d
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1 + 1e-9)
        z = a[2] + l1 * (b[2] - a[2]) + l2 * (c[2] - a[2])
        if inside.any():
            out = max(out, float(np.abs(z[inside] - q[sel[inside], 2]).max()))
    return out


def test_floor_of_passes_along_x_is_cut_in_strips():
    """A flat floor of 11 passes along x (a mark class each, three rows of nodes apiece): long strips (along x, or
    across the passes from one side of the tile to the other - the same count), far fewer triangles than the right
    triangles keep, and no triangle joins more than two neighbouring passes."""
    z = np.full((N, N), -2 * MM)
    cls = np.repeat(np.arange(N) // 3, N).reshape(N, N)
    P = grid(z)
    me = HM.own(P, P, cls, 5e-6)
    rt = HM.rtin_triangles(HM.rtin(32), HM.rtin_needed(HM.rtin(32), P.reshape(-1, 3), cls.reshape(-1), 5e-6))
    assert me["kind"] in ("x", "y")
    assert len(me["tri"]) <= 2 * 32 + 2 and len(rt) > 3 * len(me["tri"])
    assert covers_tile(P, me["tri"])
    c = cls.reshape(-1)[me["tri"]]
    assert (c.max(axis=1) - c.min(axis=1) <= 1).all()
    # ... and the same turned
    me_t = HM.own(P, P, cls.T.copy(), 5e-6)                     # (passes along y)
    assert me_t["kind"] in ("x", "y") and len(me_t["tri"]) == len(me["tri"])


def test_a_wall_along_x_stays_upright_in_long_strips():
    """A wall 2 mm high along x between two rows (the nodes moved onto it from both sides, as ``_snap`` does):
    the strips run along it, the wall is two long upright triangles, and no node is more than the tolerance off."""
    z = np.where(np.arange(N)[:, None] <= 12, -2 * MM, 0.0) + np.zeros((N, N))
    P = grid(z)
    P[12, :, 1] = P[13, :, 1] = 12.5 * 0.2 * MM                     # both rows on the wall line
    cls = np.where(np.arange(N)[:, None] <= 12, 5, -1) + np.zeros((N, N), int)
    me = HM.own(P, P, cls, 5e-6)
    tri = me["tri"]
    assert len(tri) <= 12
    a = area_xy(P, tri)
    assert (a > -1e-18).all() and abs(a.sum() - (32 * 0.2 * MM) ** 2) < 1e-12
    upright = np.abs(a) < 1e-18
    z = P.reshape(-1, 3)[tri[upright], 2]
    assert upright.sum() == 2 and np.allclose(z.min(axis=1), -2 * MM) and np.allclose(z.max(axis=1), 0.0)


def test_a_smooth_bowl_keeps_the_right_triangles_or_fewer_and_the_tolerance():
    """A smooth bowl (no direction): whatever is chosen has no more triangles than the right triangles and keeps
    every node within the tolerance (the strips are checked against the grid's finest triangles)."""
    i, j = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    r2 = ((i - 16.0) ** 2 + (j - 9.0) ** 2) * (0.2 * MM) ** 2
    z = -1 * MM + r2 / (2 * 20 * MM)
    P = grid(z)
    cls = np.zeros((N, N), int)
    tab = HM.rtin(32)
    rt = HM.rtin_triangles(tab, HM.rtin_needed(tab, P.reshape(-1, 3), cls.reshape(-1), 5e-6))
    for strips in (True, False):
        me = HM.own(P, P, cls, 5e-6, strips=strips)
        assert len(me["tri"]) <= len(rt)
        assert covers_tile(P, me["tri"])
        assert max_error(P, me["tri"], P) <= 1.1 * 5e-6


def test_ridges_and_slopes_in_strips_stay_within_the_tolerance():
    """Ridges along x on a slope along y that bends along x (ball passes on a rounded flank): strips, and every node
    within the tolerance of them (the zip is checked where it crosses the grid's lines)."""
    i, j = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    x, y = j * 0.2, i * 0.2
    z = (-0.4 * y + 0.03 * np.cos(2 * math.pi * y / 0.6) - 0.002 * (x - 3.2) ** 2) * MM
    P = grid(z)
    me = HM.own(P, P, np.zeros((N, N), int), 5e-6)
    assert covers_tile(P, me["tri"])
    assert max_error(P, me["tri"], P) <= 1.1 * 5e-6


def test_forced_border_nodes_are_fanned_in_and_add_no_other_node():
    """A tile thinned to two triangles, its neighbours forcing nodes on two of its sides (and next to a corner):
    the tile uses exactly its own nodes and the forced ones - none more on any side - and still covers itself."""
    P = grid(np.zeros((N, N)))
    me = HM.own(P, P, np.zeros((N, N), int), 5e-6)
    assert len(me["tri"]) == 2
    forced = np.zeros(N * N, bool)
    forced[[3, 5, 17, 31]] = True                                   # the first row (bottom side)
    forced[[N * k + N - 1 for k in (1, 2, 30, 31)]] = True          # the last column (right side), by the corners
    tri, need = HM.triangles(me, forced)
    used = np.zeros(N * N, bool)
    used[tri.reshape(-1)] = True
    corners = np.zeros(N * N, bool)
    corners[[0, N - 1, N * (N - 1), N * N - 1]] = True
    assert np.array_equal(used, forced | corners)
    assert covers_tile(P, tri)


@pytest.mark.parametrize("kind", ["bowl", "passes"])
def test_forced_nodes_on_every_side(kind):
    """The same with a bowl and with passes: forced nodes on every side, the tile covers itself and uses no border
    node that neither it nor its neighbours keep."""
    rng = np.random.default_rng(3)
    if kind == "passes":
        z = np.full((N, N), -2 * MM)
        cls = np.repeat(np.arange(N) // 5, N).reshape(N, N)
    else:
        i, j = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
        z = -((i - 10.0) ** 2 + (j - 20.0) ** 2) * (0.2 * MM) ** 2 / (2 * 8 * MM)
        cls = np.zeros((N, N), int)
    P = grid(z)
    me = HM.own(P, P, cls, 5e-6)
    border = np.zeros((N, N), bool)
    border[0], border[-1], border[:, 0], border[:, -1] = True, True, True, True
    forced = (border & (rng.random((N, N)) < 0.3)).reshape(-1)
    tri, need = HM.triangles(me, forced)
    used = np.zeros(N * N, bool)
    used[tri.reshape(-1)] = True
    assert not (used & border.reshape(-1) & ~(me["need"] | forced)).any()
    assert (used | ~forced).all()
    assert covers_tile(P, tri)


def test_extra_vertices_split_their_edge_or_go_into_their_triangle():
    """An extra vertex on an edge of the triangulation cuts the triangles on both sides; one whose edge is not in
    the triangulation goes into the small triangle (or onto the side of it) that holds it; never into a long one
    (its fan would lean across it)."""
    cell = 0.2 * MM
    P = grid(np.zeros((N, N)))
    tab = HM.rtin(32)
    fine = HM.rtin_triangles(tab, np.ones(N * N, bool))           # the grid's own triangles
    extra = np.array([[16.0, 16.5], [5.25, 20.5], [0.0, 7.5]])    # on an edge, inside a triangle, on the first row
    xyz = np.stack([extra[:, 1] * cell, extra[:, 0] * cell, np.full(3, -1e-6)], axis=1)
    Pall = np.concatenate([P.reshape(-1, 3), xyz])
    edges = np.array([[N * 16 + 16, N * 16 + 17], [0, N * N - 1], [0, N * N - 1]])   # (the last two: no such edge)
    t1, done = HM.split_edges(fine, edges, N * N, Pall)
    assert done.tolist() == [True, False, False] and len(t1) == len(fine) + 2
    t2, done = HM.insert_points(t1, extra, N, done, Pall)
    assert done.all() and len(t2) == len(fine) + 2 + 2 + 1
    assert (area_xy(Pall, t2) > -1e-18).all()
    assert abs(area_xy(Pall, t2).sum() - (32 * cell) ** 2) < 1e-12
    # into a long triangle: no
    two = HM.own(P, P, np.zeros((N, N), int), 5e-6)["tri"]
    t3, done = HM.insert_points(two, extra[1:2], N, np.zeros(1, bool), Pall[:N * N + 2][np.r_[np.arange(N * N), N * N + 1]])
    assert not done.any() and len(t3) == 2


def _flat_map(moves, part=None, tol=5e-6):
    """A map of 2 x 2 tiles over 12.8 mm, flat Ø4 moves (x0, y0, x1, y1, z) in mm."""
    from fresing_render.core import heightmap as H
    shape = H.Shape(H.FLAT, 2 * MM, 40 * MM)
    hm = H.HeightMap(0.0, 0.0, 0.2 * MM, 2, 2, top=0.0, bottom=-6 * MM, tol=tol)
    m = np.array(moves, float) * MM
    hm.set_moves([shape], np.zeros(len(m), int), m[:, 0:2], m[:, 2:4], m[:, 4], m[:, 4], np.arange(len(m)),
                 np.arange(len(m)) + 100, slots=1)
    if part is not None:
        hm.set_part(np.full((hm.ny, hm.nx), part))
    return hm


def test_the_map_lies_over_the_finished_part_where_it_came_down_onto_it():
    """'Finish at the CAD part' (task 0167): a pass that ran on the part (3 um over it) lies ``lift`` (12.5 um) over
    it; one that went 1 mm too deep keeps its own depth (the part shows there); the uncut top is not moved."""
    for z, want in ((-0.997, -1.0 + 0.0125), (-2.0, -2.0)):
        hm = _flat_map([(2, 2, 10, 2, z), (2, 3.5, 10, 3.5, z)], part=-1.0 * MM)
        hm.goto(2)
        hm.cut_tiles()
        P = hm._own[(0, 0)]["P"]
        cut = hm._own[(0, 0)]["owner"] >= 0
        assert np.allclose(P[cut, 2], want * MM, atol=1e-9), (z, np.unique(np.round(P[cut, 2] / MM, 5)))
        assert np.allclose(P[~cut & (P[:, 2] > -1e-9), 2], hm.uncut)


def test_a_tile_the_tool_still_works_on_is_thinned_the_quick_way():
    """Strips are worked out only for tiles no later move can change (scrubbing stays quick); the same time
    gives the same mesh however it is reached."""
    passes = [(1, 1 + 0.1 * k, 11, 1 + 0.1 * k, -1.0) for k in range(60)]
    hm = _flat_map(passes)
    hm.goto(30)
    hm.cut_tiles()
    assert not hm._done[0, 0] or hm.last[0, 0] < 30
    kinds = {key: v["strips"]["kind"] for key, v in hm._own.items() if v.get("strips") is not None}
    assert all(kinds[k] == "rtin" for k in kinds if not hm._done[k])
    hm.goto(60)
    hm.cut_tiles()
    done = {key: v["strips"]["kind"] for key, v in hm._own.items() if v.get("strips") is not None}
    assert any(k != "rtin" for k in done.values())
    first = {k: hm.mesh(*k)[1:] for k in hm._own}
    hm.goto(10)
    hm.cut_tiles()
    hm.goto(60)
    hm.cut_tiles()
    for k, (v, t, m) in first.items():
        v2, t2, m2 = hm.mesh(*k)[1:]
        assert np.array_equal(v, v2) and np.array_equal(t, t2) and np.array_equal(m, m2)
