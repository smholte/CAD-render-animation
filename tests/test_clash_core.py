"""Task 0065: the clash check's parts without Blender (core/clash.py): rigid bodies, boxes, the motion between frames,
points on triangles, tool zones, rows and the texts."""

import math

import numpy as np

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
