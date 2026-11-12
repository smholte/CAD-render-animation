"""Task 0065: the clash check's parts without Blender (core/clash.py): rigid bodies, boxes, the motion between frames,
points on triangles, tool zones, rows and the texts."""

import math

import numpy as np
import pytest

from fresing_render.core import clash as C

MM = 1e-3


def rot_z(deg, about=(0.0, 0.0, 0.0)):
    a = math.radians(deg)
    m = np.eye(4)
    m[:3, :3] = [[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]
    c = np.array(about)
    m[:3, 3] = c - m[:3, :3] @ c
    return m


def move(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


# ---------------------------------------------------------------------------
# rigid bodies
# ---------------------------------------------------------------------------

def test_parts_that_move_alike_are_one_body_and_still_parts_are_group_0():
    rng = np.random.default_rng(1)
    T = 30
    place = [move(*rng.uniform(-2, 2, 3)) for _ in range(9)]
    # parts 0-2 never move, 3-5 turn about one axis together, 6-8 slide together (with float32-like noise)
    turn = [rot_z(3.0 * k, about=(0.4, 0.1, 0.0)) for k in range(T)]
    slide = [move(0.01 * k, 0.0, 0.0) for k in range(T)]
    mats = np.empty((T, 9, 4, 4))
    for k in range(T):
        for p in range(9):
            m = place[p] if p < 3 else (turn[k] @ place[p] if p < 6 else slide[k] @ place[p])
            mats[k, p] = m + rng.normal(0, 2e-7, (4, 4)) * (np.arange(4) < 3)[:, None]
    g = C.rigid_groups(C.deltas(mats))
    assert list(g[:3]) == [0, 0, 0]
    assert len(set(g[3:6])) == 1 and len(set(g[6:9])) == 1
    assert len({g[0], g[3], g[6]}) == 3


def test_parts_that_part_ways_once_are_two_bodies():
    T = 10
    mats = np.tile(np.eye(4), (T, 2, 1, 1))
    mats[7:, 1] = move(0.0, 0.0, 1e-3)             # one part moves 1 mm late in the animation
    g = C.rigid_groups(C.deltas(mats))
    assert g[0] != g[1]


# ---------------------------------------------------------------------------
# boxes and motion
# ---------------------------------------------------------------------------

def test_world_boxes_and_box_pairs():
    lo = np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0]], float)
    hi = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]], float)
    mats = np.stack([np.eye(4), move(0.5, 0, 0), move(3, 0, 0)])
    wlo, whi = C.world_boxes(mats, lo, hi)
    assert np.allclose(wlo[1], (0.5, 0, 0)) and np.allclose(whi[2], (4, 1, 1))
    turned_lo, turned_hi = C.world_boxes(rot_z(45)[None], lo[:1], hi[:1])
    assert np.isclose(turned_hi[0, 1], math.sqrt(2)) and np.isclose(turned_lo[0, 0], -math.sqrt(0.5))
    pairs = {tuple(p) for p in C.box_pairs(wlo, whi, wlo, whi)}
    assert (0, 1) in pairs and (0, 2) not in pairs and (1, 2) not in pairs
    assert (1, 2) in {tuple(p) for p in C.box_pairs(wlo, whi, wlo, whi, margin=1.6)}


def test_screw_motion_between_two_frames_is_exact_for_a_turn_and_a_slide():
    m0 = move(0.3, 0.2, 0.1)
    for deg in (10.0, 90.0, 170.0):
        m1 = rot_z(deg, about=(1.0, -0.5, 0.0)) @ m0
        half = C.screw_between(m0, m1, 0.5)
        assert np.allclose(half, rot_z(deg / 2, about=(1.0, -0.5, 0.0)) @ m0, atol=1e-12)
    m1 = move(0.0, 0.0, 0.25) @ rot_z(40.0) @ m0                 # a turn about Z and a slide along it: a screw
    assert np.allclose(C.screw_between(m0, m1, 0.25), move(0, 0, 0.0625) @ rot_z(10.0) @ m0, atol=1e-12)
    assert np.allclose(C.screw_between(m0, m0, 0.3), m0)


def test_motion_bounds_every_point_of_the_box():
    lo, hi = np.array([-0.1, -0.2, 0.0]), np.array([0.3, 0.1, 0.05])
    m1 = rot_z(7.0, about=(0.5, 0.5, 0.0))
    bound = C.motion(np.eye(4), m1, lo, hi)
    pts = np.random.default_rng(3).uniform(lo, hi, (2000, 3))
    moved = np.linalg.norm(C.transform(m1, pts) - pts, axis=1)
    assert moved.max() <= bound + 1e-12
    many = C.motion_many(np.stack([np.eye(4)] * 2), np.stack([m1, np.eye(4)]), np.stack([lo] * 2), np.stack([hi] * 2))
    assert np.isclose(many[0], bound) and many[1] == 0.0


# ---------------------------------------------------------------------------
# points on triangles, long faces, nearest points
# ---------------------------------------------------------------------------

def test_points_spread_over_long_triangles():
    tri = np.array([[[0, 0, 0], [0.1, 0, 0], [0, 0.01, 0]]], float)
    pts, which = C.triangle_points(tri, 0.01)
    assert len(pts) > 10 and np.all(which == 0)
    assert np.all(pts[:, 0] >= -1e-12) and np.all(pts[:, 1] >= -1e-12)
    assert np.all(pts[:, 0] / 0.1 + pts[:, 1] / 0.01 <= 1 + 1e-9)          # all inside the triangle
    assert len(C.thin_out(pts, 5)) == 5


def test_split_long_faces_keeps_the_surface():
    v = np.array([[0, 0, 0], [1.0, 0, 0], [0, 0.0025, 0]])            # a 1 m sliver, 2.5 mm wide
    t = np.array([[0, 1, 2]])
    sv, st = C.split_long(v, t, longest=0.025)
    tri = sv[st]
    assert np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2)) <= 0.025 + 1e-12
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    assert np.isclose(area.sum(), 0.5 * 1.0 * 0.0025)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    assert np.all(n[:, 2] > 0)                                             # faces keep their side


def test_split_long_stays_small_on_a_vessel_sized_mesh():
    """Task 0077: a 60 m sliver became 3^10 pieces when halved at its longest edge, a vessel's deck and hull billions
    (the check ran out of memory). Cut into a strip: about 2 x length / 25 mm pieces, the same surface and sides; a
    wide face stays whole; a mesh past the budget is cut coarser."""
    v = np.array([[0, 0, 0], [60.0, 0, 0], [20.0, 0.004, 0]])            # 60 m long, 4 mm wide
    t = np.array([[0, 1, 2]])
    sv, st = C.split_long(v, t, longest=0.025)
    tri = sv[st]
    assert len(st) <= 2 * 60 / 0.025 + 2
    assert np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2)) <= 0.025 * 1.1
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    assert np.isclose(area.sum(), 0.5 * 60.0 * 0.004)
    assert np.all(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])[:, 2] > 0)
    wide = np.array([[0, 0, 0], [120.0, 0, 0], [60.0, 40.0, 0]])         # a deck plate: not thin
    assert len(C.split_long(wide, t)[1]) == 1
    many = np.concatenate([v + [0, 0, k * 0.01] for k in range(200)])     # 200 slivers: past the budget
    mt = np.arange(len(many)).reshape(-1, 3)
    sv, st = C.split_long(many, mt)
    assert len(st) <= 1.05 * C.MESH_BUDGET
    tri = sv[st]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    assert np.isclose(area.sum(), 200 * 0.5 * 60.0 * 0.004)


def test_closest_points_on_triangles_match_a_dense_search():
    rng = np.random.default_rng(5)
    tri = rng.uniform(-1, 1, (40, 3, 3))
    p = rng.uniform(-1.5, 1.5, 3)
    got = C.closest_on_triangles(p, tri)
    uv = np.array([(i / 60, j / 60) for i in range(61) for j in range(61 - i)])
    for k in range(len(tri)):
        a, b, c = tri[k]
        dense = a + uv[:, :1] * (b - a) + uv[:, 1:] * (c - a)
        best = np.min(np.linalg.norm(dense - p, axis=1))
        assert np.linalg.norm(got[k] - p) <= best + 1e-9
        assert np.linalg.norm(C.clamp_to_triangle(p, tri[k]) - got[k]) < 1e-9


def test_signed_volume_of_a_box():
    v = np.array([[x, y, z] for x in (0, 2) for y in (0, 3) for z in (0, 4)], float)
    # the 12 triangles of a box, facing out
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    t = np.array([tri for a, b, c, d in q for tri in ((a, b, c), (a, c, d))])
    assert np.isclose(C.signed_volume(v, t), 24.0)
    assert np.isclose(C.signed_volume(v, t[:, ::-1]), -24.0)


# ---------------------------------------------------------------------------
# tools, depths, rows, texts
# ---------------------------------------------------------------------------

def test_tool_zones():
    cut = C.zone((0, 0, 0), (0, 0, 2), 3 * MM, -math.inf, 20 * MM)      # Ø6, 20 mm of flutes along +Z
    above = C.zone((0, 0, 0), (0, 0, 1), math.inf, 40 * MM, math.inf)  # above the gauge line, any width
    pts = np.array([[0, 0, 0.01], [0.0029, 0, 0.019], [0.004, 0, 0.01], [0, 0, 0.025], [0.5, 0.2, 0.05]])
    assert list(C.in_zone(pts, [cut])) == [True, True, False, False, False]
    assert list(C.in_zone(pts, [cut, above])) == [True, True, False, False, True]
    assert not np.any(C.in_zone(pts, []))


def test_clash_depth_and_start_overlap():
    assert not C.is_clash(0.4 * MM, 0.0) and C.is_clash(0.6 * MM, 0.0)
    assert C.is_clash(0.6 * MM, -1.0)                                      # not touching at the start
    # a pin in its bore (0.05 mm at the start): half a millimetre more counts
    assert not C.is_clash(0.5 * MM, 0.05 * MM) and C.is_clash(0.6 * MM, 0.05 * MM)
    # parts that overlap 10 mm in CAD: 10 + 0.5 + half of 10
    assert C.allowed_depth(10 * MM) == 10 * MM + C.DEPTH + 5 * MM
    assert not C.is_clash(15 * MM, 10 * MM) and C.is_clash(15.6 * MM, 10 * MM)
    assert C.is_near(2 * MM, 50 * MM, 5 * MM) and not C.is_near(2 * MM, 3 * MM, 5 * MM)
    assert not C.is_near(0.0, 50 * MM, 5 * MM)


def test_moments_in_a_row_make_one_row():
    hits = [C.Hit(t, d * MM, d * MM)
            for t, d in ((12, 1), (13, 3), (13.5, 4), (14, 2), (30, 1), (30.5, 2), (31, 1), (33, 1))]
    rows = C.merge(hits, "CLASH", "A", "B")
    assert [(r.frame_from, r.frame_to) for r in rows] == [(12, 14), (30, 31), (33, 33)]      # 31 -> 33: apart
    assert rows[0].t_deep == 13.5 and np.isclose(rows[0].depth, 4 * MM)
    near = C.merge([C.Hit(5, 3 * MM, 0), C.Hit(6, 1 * MM, 0)], "NEAR", "A", "C")
    assert near[0].depth == 1 * MM and near[0].t_deep == 6
    ordered = C.sort_rows(near + rows)
    assert [r.kind for r in ordered] == ["CLASH"] * 3 + ["NEAR"] and ordered[0].depth == 4 * MM
    assert C.row_text(rows[0]) == "A × B: frames 12–14, 4.0 mm deep"
    assert C.row_text(near[0]) == "A × C: frames 5–6, 1.0 mm apart"


def test_texts():
    assert C.header(False, False, 0) == "Not checked since the last Build"
    assert C.header(True, True, 3) == "Not checked since the last Build"
    assert C.header(True, False, 3) == "3 clashes"
    assert C.header(True, False, 1) == "1 clash"
    assert C.header(True, False, 0) == "No clashes"
    assert C.header(True, False, 0, near=2) == "2 near misses"
    assert C.queue_note("Lift", False, 0) == "'Lift' was not checked for clashes (6 Animation > Clash check)"
    assert C.queue_note("Lift", True, 0) == ""
    assert C.queue_note("Lift", True, 2).startswith("'Lift' has 2 clashes")
    assert C.mm(0.00612) == "6.1 mm" and C.mm(0.4) == "400 mm"


# ---------------------------------------------------------------------------
# parts that turn in place (task 0092)
# ---------------------------------------------------------------------------

def _turn(deg, c, u):
    return C.rotation_about(np.array(c, float), np.array(u, float), math.radians(deg))


def _cylinder(r=50 * MM, h=0.2, n=48, flat=None, teeth=0, depth=0.0, off=(0.0, 0.0)):
    """A faceted cylinder along Z (caps as fans): ``flat`` cuts it at x = flat, ``teeth`` makes a gear-like rim."""
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rr = np.where(np.cos(teeth * ang) < 0, r - depth, r) if teeth else np.full(n, r)
    xy = np.stack([rr * np.cos(ang) + off[0], rr * np.sin(ang) + off[1]], axis=1)
    if flat is not None:
        xy[:, 0] = np.minimum(xy[:, 0], flat)
    v = [(x, y, 0.0) for x, y in xy] + [(x, y, h) for x, y in xy] + [(off[0], off[1], 0.0), (off[0], off[1], h)]
    t = []
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return np.array(v), np.array(t)


def test_a_turn_about_a_fixed_axis_is_one_stretch():
    lo, hi = np.array([0.9, 1.5, -0.1]), np.array([1.1, 2.5, 0.1])
    e = np.stack([_turn(7 * k, (1, 2, 0), (0, 1, 0)) for k in range(50)])           # 350°: past half a turn too
    (s, end, c, u), = C.spin_stretches(e, lo, hi)
    assert (s, end) == (0, 50)
    assert np.allclose(abs(u @ [0, 1, 0]), 1.0) and np.allclose(c, [1, 0, 0], atol=1e-9)
    # still at first, then turning: one stretch
    e2 = np.concatenate([np.repeat(np.eye(4)[None], 10, axis=0), e[:30]])
    assert [(a, b) for a, b, _c, _u in C.spin_stretches(e2, lo, hi)] == [(0, 40)]


def test_a_turn_then_a_slide_and_a_screw_are_not_in_place():
    lo, hi = np.array([0.9, 1.5, -0.1]), np.array([1.1, 2.5, 0.1])
    e = [_turn(7 * k, (1, 2, 0), (0, 1, 0)) for k in range(20)]
    e += [move(0.01 * k, 0, 0) @ e[-1] for k in range(1, 30)]
    assert [(a, b) for a, b, _c, _u in C.spin_stretches(np.stack(e), lo, hi)] == [(0, 20)]
    screw = np.stack([move(0, 0.002 * k, 0) @ _turn(7 * k, (1, 2, 0), (0, 1, 0)) for k in range(30)])
    assert C.spin_stretches(screw, lo, hi) == []
    # a slide and a turn about a moving axis (a roller on a carriage, seen from the world): no long stretch
    ride = np.stack([move(0, 0.0125 * k, 0) @ _turn(27 * k, (0, 0, 0), (1, 0, 0)) for k in range(40)])
    assert C.spin_stretches(ride, np.array([-0.1, -0.05, -0.05]), np.array([0.1, 0.05, 0.05])) == []
    # nothing turns: nothing to hold
    assert C.spin_stretches(np.stack([move(0.01 * k, 0, 0) for k in range(10)]), lo, hi) == []


def test_round_about_its_axis_and_not():
    v, t = _cylinder()
    assert C.round_about(v, t, (0, 0, 0), (0, 0, 1))
    assert C.round_about(v, t, (0, 0, 0.3), (0, 0, -1))                             # any point on the axis, any sense
    assert not C.round_about(v, t, (1 * MM, 0, 0), (0, 0, 1))                       # 1 mm off its centre
    assert not C.round_about(v, t, (0, 0, 0), (0, 1, 0))                            # across it
    assert not C.round_about(*_cylinder(flat=46 * MM), (0, 0, 0), (0, 0, 1))        # a flat 4 mm deep
    assert not C.round_about(*_cylinder(n=240, teeth=20, depth=8 * MM), (0, 0, 0), (0, 0, 1))  # teeth
    assert not C.round_about(*_cylinder(n=6), (0, 0, 0), (0, 0, 1))                 # a hexagon is no circle
    # a coarse faceted cylinder turned by half a facet lies its sag off itself: still round
    assert C.round_about(*_cylinder(n=24), (0, 0, 0), (0, 0, 1))
    assert C._ring_sag(v - 0.0, np.array([0.0, 0.0, 1.0])) == pytest.approx(0.05 * (1 - math.cos(math.pi / 48)))


def test_box_tree_holds_every_piece_and_bounds_the_distance():
    # a ring of 400 triangles (24 m across) and a small block: the bound is never more than the true gap, and close
    ang = np.linspace(0, 2 * math.pi, 401)
    pts = np.stack([12 * np.cos(ang), 12 * np.sin(ang), np.zeros_like(ang)], axis=1)
    v = np.concatenate([pts[:-1], pts[:-1] + [0, 0, 1.0]])
    n = len(pts) - 1
    t = np.array([(i, (i + 1) % n, n + i) for i in range(n)]
                 + [((i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)])
    plo, phi = C.piece_boxes(v, t)
    assert len(plo) >= len(t)
    nlo, nhi, kids = C.box_tree(plo, phi)
    assert np.allclose(nlo[0], v.min(axis=0)) and np.allclose(nhi[0], v.max(axis=0))
    leaves = kids[:, 0] < 0
    assert np.all(nhi[leaves] - nlo[leaves] < 0.6)                    # small boxes along the ring (1 m faces cut)
    bv = np.array([(x, y, z) for x in (0, 0.2) for y in (0, 0.2) for z in (0.2, 0.4)], dtype=float)
    bt = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6),
                   (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    tb = C.box_tree(*C.piece_boxes(bv, bt))
    ta = (nlo, nhi, kids)
    for x in (0.0, 11.0, 11.5, 11.9):
        true = max(0.0, 12 * math.cos(math.pi / 400) - math.hypot(x + 0.2, 0.2))    # to the ring's nearest facet
        sep = C.tree_separation(ta, tb, move(x, 0.0, 0.0))
        assert sep <= true + 1e-9 and sep >= 0.8 * true - 0.03, (x, sep, true)
    # turned: still a lower bound; ``need`` stops sooner and says at least that much
    rel = rot_z(30) @ move(5.0, 0.0, 0.0)
    assert C.tree_separation(ta, tb, rel) > 5.0
    assert 1.0 <= C.tree_separation(ta, tb, rel, need=1.0) <= C.tree_separation(ta, tb, rel)


def test_line_box_distance():
    lo = np.array([[1.0, -0.5, -0.5], [-0.2, -0.2, 3.0], [2.0, 2.0, 0.0]])
    hi = np.array([[2.0, 0.5, 0.5], [0.2, 0.2, 4.0], [3.0, 3.0, 1.0]])
    d = C.line_box_distance(np.zeros(3), np.array([0.0, 0.0, 1.0]), lo, hi)
    assert np.allclose(d, [1.0, 0.0, math.hypot(2.0, 2.0)])
    # a long thin box passing by at a slant: dense samples of the box are never nearer
    lo, hi = np.array([[0.4, -1.0, -0.1]]), np.array([[0.5, 1.0, 0.1]])
    u = np.array([0.0, 0.3, 1.0]) / math.hypot(0.3, 1.0)
    d = C.line_box_distance(np.zeros(3), u, lo, hi)[0]
    g = np.stack(np.meshgrid(*[np.linspace(lo[0, i], hi[0, i], 21) for i in range(3)]), axis=-1).reshape(-1, 3)
    r = np.linalg.norm(g - (g @ u)[:, None] * u, axis=1)
    assert d <= r.min() + 1e-9 and d >= r.min() - 0.01


def test_connected_pieces():
    t = np.array([(0, 1, 2), (2, 3, 0), (4, 5, 6), (7, 8, 9), (9, 10, 7), (10, 11, 8)])
    lab = C.connected(13, t)
    assert len({lab[0], lab[1], lab[2], lab[3]}) == 1 and lab[4] == lab[5] == lab[6]
    assert len({lab[i] for i in (7, 8, 9, 10, 11)}) == 1 and lab[12] == 12
    assert len({lab[0], lab[4], lab[7], lab[12]}) == 4
    # a long strip (a path 2,000 faces long) ends as one piece
    m = 2000
    t = np.array([(i, i + 1, i + 2) for i in range(m)])
    assert len(set(C.connected(m + 2, t))) == 1


def test_a_slow_turn_with_a_long_move_stays_on_its_path_between_frames():
    """Task 0091's open point: bodies up to 60 m from the origin that slide up to metres while they turn by 0 … 1 rad
    about some axis, their places read as float32 (as Blender gives them): the place half-way is on the exact screw
    path within a hundredth of a millimetre. The least-squares axis point before task 0092 put tiny turns metres off."""
    rng = np.random.default_rng(3)

    def turn(axis, ang, about=(0.0, 0.0, 0.0)):
        return C.rotation_about(np.array(about, float), np.asarray(axis, float) / np.linalg.norm(axis), ang)
    pts = np.array([[0.5, 0.2, 0.1], [-0.5, 0.0, 0.3]])
    for th in (0.0, 1e-7, 1e-6, 1e-5, 1e-4, 0.01, 1.0):
        for _k in range(40):
            base = turn(rng.normal(size=3), rng.uniform(0, 3))
            base[:3, 3] = rng.uniform(-60, 60, 3)
            ax = rng.normal(size=3)
            ax /= np.linalg.norm(ax)
            c, along = rng.uniform(-5, 5, 3), rng.normal() * 2.0

            def screw(f):
                m = turn(ax, th * f, c)
                m[:3, 3] += ax * along * f
                return m
            m0 = base.astype(np.float32).astype(np.float64)
            m1 = (screw(1.0) @ base).astype(np.float32).astype(np.float64)
            mid = C.screw_between(m0, m1, 0.5)
            err = np.max(np.abs(C.transform(mid, pts) - C.transform(screw(0.5) @ base, pts)))
            assert err < 0.01 * MM, (th, err)
    assert abs(float(C.turn_angles(turn((0, 0, 1), 1e-5).astype(np.float32).astype(np.float64))) - 1e-5) < 1e-6
