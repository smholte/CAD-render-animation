"""Task 0349 (Lifting L6b) – independent tests, written by an agent that did not write the code, to break it.

Plain Python first (``core/lifting_zones``, ``lifting_model/charts``), then one test with Blender as a Python module.
Tests marked ``FOUND:`` in their docstring fail on the branch as it was handed over: each says the input, what came
out and what should have come out. As handed over, these 10 fail on purpose (findings for the author):

- test_what_the_load_stands_on_does_not_hide_a_wall_beside_it, test_two_obstacles_with_the_same_name,
  test_a_part_inside_an_obstacle_is_not_clear, test_the_cached_clearance_follows_an_obstacle_turned_in_place
  (a clearance reported as clear / larger than it is),
- test_a_long_boom_keeps_the_points_5_cm_apart, test_a_nan_corner_does_not_hide_the_whole_part,
- test_distances_gives_every_body_within_the_search (docstring), test_the_sheet_says_which_way_the_distance_errs
  (words),
- test_zone_holds_the_tail_swing_even_without_a_margin, test_zone_margin_within_a_centimetre (small).
"""

from __future__ import annotations

import html.parser
import json
import math
import os
import xml.dom.minidom

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_path as P, lifting_reach as LR
from fresing_render.core import lifting_zones as Z
from fresing_render.lifting_model import charts as K, classes as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "fresing_render", "data", "lifting")


# ---------------------------------------------------------------------------------------------------------------------
# helpers: exact distances by hand

_BOX_T = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
          (1, 5, 7), (1, 7, 3)]
_BOX_E = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def _box(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    return v, np.array(_BOX_T)


def _identity(_j, _v):
    return np.eye(4)


def _turn_slide(j, v):
    """A joint that turns about z by v[j] degrees and slides 1 cm per degree along x, and lifts 1 mm per degree."""
    a = math.radians(v.get(j, 0.0))
    M = np.eye(4)
    M[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    M[0, 3] = 0.01 * v.get(j, 0.0)
    M[2, 3] = 0.001 * v.get(j, 0.0)
    return M


def _seg_seg(p1, q1, p2, q2) -> float:
    """Exact distance between two segments (Ericson, Real-Time Collision Detection 5.1.9)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a <= 1e-15 and e <= 1e-15:
        return float(np.linalg.norm(p1 - p2))
    if a <= 1e-15:
        s, t = 0.0, min(max(f / e, 0.0), 1.0)
    else:
        c = d1 @ r
        if e <= 1e-15:
            t, s = 0.0, min(max(-c / a, 0.0), 1.0)
        else:
            b = d1 @ d2
            den = a * e - b * b
            s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > 1e-15 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(max(-c / a, 0.0), 1.0)
            elif t > 1.0:
                t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    return float(np.linalg.norm((p1 + d1 * s) - (p2 + d2 * t)))


def _pt_tri(p, a, b, c) -> float:
    from fresing_render.core import clash
    q = clash.closest_on_triangles(np.asarray(p, float), np.array([[a, b, c]], float))[0]
    return float(np.linalg.norm(q - p))


def _convex_distance(va, ta, ea, vb, tb, eb) -> float:
    """The exact distance between two separated convex polyhedra: the smallest of vertex–face (both ways) and
    edge–edge distances."""
    best = math.inf
    for p in va:
        for t in tb:
            best = min(best, _pt_tri(p, *vb[t]))
    for p in vb:
        for t in ta:
            best = min(best, _pt_tri(p, *va[t]))
    for i, j in ea:
        for k, m in eb:
            best = min(best, _seg_seg(va[i], va[j], vb[k], vb[m]))
    return best


def _overlap(M, alo, ahi, blo, bhi) -> bool:
    """Separating-axis test of a box (``alo``–``ahi`` moved by ``M``) and an axis-aligned box."""
    A = M[:3, :3]
    ca = M[:3, :3] @ ((alo + ahi) / 2) + M[:3, 3]
    ea = (ahi - alo) / 2
    cb, eb = (blo + bhi) / 2, (bhi - blo) / 2
    axes = [A[:, i] for i in range(3)] + [np.eye(3)[i] for i in range(3)]
    axes += [np.cross(A[:, i], np.eye(3)[j]) for i in range(3) for j in range(3)]
    for ax in axes:
        n = np.linalg.norm(ax)
        if n < 1e-9:
            continue
        ax = ax / n
        ra = sum(ea[i] * abs(A[:, i] @ ax) for i in range(3))
        rb = sum(eb[i] * abs(ax[i]) for i in range(3))
        if abs((ca - cb) @ ax) > ra + rb:
            return False
    return True


def _moved(M, v):
    return v @ M[:3, :3].T + M[:3, 3]


# ---------------------------------------------------------------------------------------------------------------------
# clearance

def test_clearance_is_between_the_true_gap_and_the_gap_plus_the_spacing():
    """Random boxes (edges under 3 m), moved and turned by a joint: the true gap ≤ the reported one ≤ the true gap +
    3.5 cm (points 5 cm apart on the moving part's surface, measured to exact triangles)."""
    rng = np.random.default_rng(11)
    tried = 0
    for k in range(25):
        lo = rng.uniform(-1, 1, 3)
        size = rng.uniform(0.2, 2.5, 3)
        b = Z.body("PART", "crane", "J", *_box(lo, lo + size))
        olo = rng.uniform(-4, 4, 3)
        osz = rng.uniform(0.2, 2.5, 3)
        ov, ot = _box(olo, olo + osz)
        ob = Z.Triangles([("OBST", ov, ot)])
        c = Z.Clearance([b], ob, _turn_slide, required=2.0)
        for ang in (0.0, 17.0, 63.0, 140.0, 255.0):
            vals = {"J": ang}
            M = _turn_slide("J", vals)
            va = _moved(M, _box(lo, lo + size)[0])
            truth = _convex_distance(va, np.array(_BOX_T), _BOX_E, ov, np.array(_BOX_T), _BOX_E)
            got = c.nearest(vals).distance
            if got >= Z.FAR / 2:                 # nothing within the search: the true gap is near or past it
                assert truth >= c.need - 0.035, (k, ang, got, truth)
                continue
            if _overlap(M, lo, lo + size, olo, olo + osz):   # boxes overlapping: not this test's case
                continue
            tried += 1
            assert truth - 1e-5 <= got <= truth + 0.035, (k, ang, got, truth)       # points rounded to 1 µm
    assert tried >= 10


def test_a_long_boom_keeps_the_points_5_cm_apart():
    """FOUND: a 30 m boom (a box, its faces two 30 m triangles each) and a thin bar (a power line) crossing 10 cm above
    it between the boom's surface points: 0.246 m reported against 0.100 m true. ``surface_points`` splits a triangle
    at most 64 times (``max_split=64``), so on a face longer than 3.2 m the points lie further apart than SPACING
    (30 m / 64 = 0.47 m here) and the documented bound ("the true gap, or up to ~3 cm more") does not hold."""
    boom = Z.body("BOOM", "crane", "J", *_box((0, 0, 0), (30, 1, 1)))
    line = Z.Triangles([("LINE", *_box((15.225, -5, 1.1), (15.235, 5, 1.11)))])
    c = Z.Clearance([boom], line, _identity, required=1.0)
    got = c.nearest({}).distance
    assert 0.1 - 1e-9 <= got <= 0.1 + 0.035, got


def test_exactly_touching_is_red_with_a_finite_use():
    b = Z.body("HOOK BLOCK", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    ob = Z.Triangles([("WALL", *_box((1, 0, 0), (2, 1, 1)))])
    c = Z.Clearance([b], ob, _identity, required=1.0)
    n = c.nearest({})
    assert n.distance == pytest.approx(0.0, abs=1e-9) and n.obstacle == "WALL"
    r = c.row({})
    assert r.status == lifting.RED and math.isfinite(r.use) and r.use > 1.0
    assert "nan" not in r.value.lower() and "inf" not in r.value.lower()


def test_a_part_inside_an_obstacle_is_not_clear():
    """FOUND: a hook block (0.5 m cube) wholly inside a hall modelled as a closed box 20 m across: nothing within the
    search (the nearest wall is 9.5 m away) – row "more than 1.47 m", status ok. A part inside a closed obstacle is a
    clash (distance 0, red)."""
    b = Z.body("HOOK BLOCK", "crane", "J", *_box((0, 0, 0), (0.5, 0.5, 0.5)))
    ob = Z.Triangles([("HALL", *_box((-10, -10, -10), (10, 10, 10)))])
    c = Z.Clearance([b], ob, _identity, required=1.0)
    assert c.row({}).status == lifting.RED, c.row({}).words


def test_no_obstacles_at_all():
    b = Z.body("BOOM", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    for ob in (Z.Triangles([]), None):
        c = Z.Clearance([b], ob, _identity, required=1.0)
        assert c.distances({}) == [] and c.nearest({}).distance >= Z.FAR / 2
        r = c.row({})
        assert r.status == lifting.OK and "more than" in r.value
        c.leave_out_touching([{}])
        assert c.ignore == {}


def test_no_bodies():
    c = Z.Clearance([], Z.Triangles([("WALL", *_box((1, 0, 0), (2, 1, 1)))]), _identity, required=1.0)
    assert c.row({}).status == lifting.OK


def test_a_body_without_triangles_or_points():
    with pytest.raises(ValueError):
        Z.body("EMPTY", "crane", "J", np.zeros((0, 3)), np.zeros((0, 3), int))
    # points but no triangles: the corners themselves
    b = Z.body("CLOUD", "crane", "J", np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]), np.zeros((0, 3), int))
    c = Z.Clearance([b], Z.Triangles([("WALL", *_box((1.5, -1, -1), (2, 1, 1)))]), _identity, required=1.0)
    assert c.nearest({}).distance == pytest.approx(0.5, abs=1e-9)


def test_degenerate_obstacle_triangles():
    """A triangle with three points on one line (a rod drawn as a sliver) and one with all three points the same: no
    NaN, the distance to the line."""
    b = Z.body("A", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    v = np.array([[1.5, 0.5, -1.0], [1.5, 0.5, 0.5], [1.5, 0.5, 2.0], [1.3, 0.5, 0.5]])
    ob = Z.Triangles([("ROD", v, np.array([[0, 1, 2], [3, 3, 3]]))])
    c = Z.Clearance([b], ob, _identity, required=1.0)
    n = c.nearest({})
    assert 0.3 - 1e-6 <= n.distance <= 0.3 + 0.035 and n.obstacle == "ROD"


def test_a_nan_corner_does_not_hide_the_whole_part():
    """FOUND: a part with one NaN corner (a broken mesh) next to a wall 0.5 m away: the part's box becomes NaN and the
    whole part is skipped – "more than 1.47 m", ok. Either refuse the part (ValueError) or measure the rest of it."""
    v, t = _box((0, 0, 0), (1, 1, 1))
    v = v.copy()
    v[0, 0] = np.nan
    wall = Z.Triangles([("WALL", *_box((1.5, 0, 0), (2, 1, 1)))])
    try:
        b = Z.body("BROKEN", "crane", "J", v, t)
    except ValueError:
        return
    c = Z.Clearance([b], wall, _identity, required=1.0)
    r = c.row({})
    assert "nan" not in r.value.lower()
    assert c.nearest({}).distance == pytest.approx(0.5, abs=0.04), r.words


def test_what_the_load_stands_on_does_not_hide_a_wall_beside_it():
    """FOUND: a low skid (1 x 1 x 0.2 m) stands on a pallet (left out for it, right), a wall 0.5 m beside it. Every
    point of the skid is nearer the pallet than the wall; ``_lookup`` takes each point's single nearest obstacle and,
    when that one is left out, drops the point – so the wall is never seen: "more than 1.47 m" instead of 0.50 m.
    (Blender's BVH ``find_nearest`` in the app has the same one-answer shape.)"""
    load = Z.body("SKID", "load", "H", *_box((0, 0, 0), (1, 1, 0.2)))
    ob = Z.Triangles([("PALLET", *_box((-0.2, -0.2, -0.15), (1.2, 1.2, 0))), ("WALL", *_box((1.5, -1, 0), (2, 2, 1)))])
    c = Z.Clearance([load], ob, _identity, required=1.0)
    c.leave_out_touching([{}])
    assert c.ignore == {"SKID": {"PALLET"}}
    n = c.nearest({})
    assert n.distance == pytest.approx(0.5, abs=1e-6) and n.obstacle == "WALL", n


def test_two_obstacles_with_the_same_name():
    """FOUND: what the load stands on is left out by NAME. Two pallets both named "PALLET" (copies of one part – part
    names repeat), the skid stands on one, the other 1.0 m beside it: the second is left out too – "more than 1.47 m"
    instead of 1.00 m."""
    load = Z.body("SKID", "load", "H", *_box((0, 0, 0), (1, 1, 1)))
    ob = Z.Triangles([("PALLET", *_box((-0.5, -0.5, -0.2), (1.5, 1.5, 0))),
                      ("PALLET", *_box((2.0, 0, 0), (3, 1, 1)))])
    c = Z.Clearance([load], ob, _identity, required=1.0)
    c.leave_out_touching([{}])
    assert c.nearest({}).distance == pytest.approx(1.0, abs=1e-6)


def test_leave_out_touching_is_only_for_the_load_and_its_rigging_and_counts_the_end_too():
    floor = ("SLAB", *_box((-5, -5, -1), (5, 5, 0)))
    target = ("PLINTH", *_box((10, -1, -1), (12, 1, 0.5)))
    load = Z.body("SKID", "load", "H", *_box((0, 0, 0), (1, 1, 1)))
    sling = Z.body("SLING", "rigging", "H", *_box((0.4, 0.4, 1.0), (0.6, 0.6, 3.0)))
    boom = Z.body("BOOM", "crane", "S", *_box((0, 0, 0.001), (1, 1, 1)))          # 1 mm over the slab: not "load"

    def mot(j, v):
        M = np.eye(4)
        if j == "H":
            M[0, 3], M[2, 3] = v.get("x", 0.0), v.get("z", 0.0)
        return M
    c = Z.Clearance([load, sling, boom], Z.Triangles([floor, target]), mot, required=1.0)
    c.leave_out_touching([{"x": 0.0, "z": 0.0}, {"x": 10.5, "z": 0.5}])
    assert c.ignore.get("SKID") == {"SLAB", "PLINTH"}
    assert "BOOM" not in c.ignore
    # the boom still sees the slab
    n = c.nearest({"x": 5.0, "z": 5.0})
    assert n.body == "BOOM" and n.obstacle == "SLAB" and n.distance == pytest.approx(0.001, abs=1e-6)


def test_distances_gives_every_body_within_the_search():
    """FOUND (docstring): ``distances`` says "each body's nearest obstacle when it comes within ``need``", but a second
    body 1.0 m from a wall (inside the 1.47 m search) is missing when another body is 0.5 m away – only the overall
    nearest body is returned. (``nearest`` is right; the list is not what the docstring says.)"""
    a = Z.body("A", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    b = Z.body("B", "crane", "J", *_box((0, 5, 0), (1, 6, 1)))
    ob = Z.Triangles([("W1", *_box((1.5, 0, 0), (2, 1, 1))), ("W2", *_box((2.0, 5, 0), (3, 6, 1)))])
    c = Z.Clearance([a, b], ob, _identity, required=1.0)
    got = {bb.name: d for d, bb, _k, _p in c.distances({})}
    assert got == pytest.approx({"A": 0.5, "B": 1.0}, abs=1e-6)


def test_the_row_grows_as_the_gap_shrinks_and_its_numbers_agree():
    b = Z.body("BOOM", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    ob = Z.Triangles([("WALL", *_box((3, 0, 0), (4, 1, 1)))])

    def slide(j, v):
        M = np.eye(4)
        M[0, 3] = v.get(j, 0.0)
        return M
    c = Z.Clearance([b], ob, slide, required=1.0)
    last = -1.0
    rank = {lifting.OK: 0, lifting.AMBER: 1, lifting.RED: 2}
    last_rank = 0
    for x in np.linspace(0.0, 2.0, 41):
        r = c.row({"J": float(x)})
        assert r.use >= last - 1e-12
        assert rank[r.status] >= last_rank
        last, last_rank = r.use, rank[r.status]
        d = 2.0 - x
        if d < c.need - 1e-6:
            assert r.value == f"{d:.2f} m" and r.measure == pytest.approx(-d, abs=1e-9)
            assert r.use == pytest.approx(1.0 / max(d, 1e-6), rel=1e-9)
    assert last_rank == 2


def test_a_zero_clearance_needed_does_not_divide_by_zero():
    b = Z.body("BOOM", "crane", "J", *_box((0, 0, 0), (1, 1, 1)))
    c = Z.Clearance([b], Z.Triangles([("WALL", *_box((1.0005, 0, 0), (2, 1, 1)))]), _identity, required=0.0)
    r = c.row({})
    assert math.isfinite(r.use) and r.status in (lifting.OK, lifting.AMBER, lifting.RED)


def test_a_standing_body_and_the_amber_border():
    """A body with no joint (None) stands; amber exactly from the crane limit: use = needed / distance ≥ 0.75."""
    b = Z.body("COUNTERWEIGHT", "crane", None, *_box((0, 0, 0), (1, 1, 1)))
    for gap, st in ((1.0 / 0.74, lifting.OK), (1.0 / 0.76, lifting.AMBER), (1.0, lifting.AMBER), (0.99, lifting.RED)):
        ob = Z.Triangles([("WALL", *_box((1.0 + gap, 0, 0), (3 + gap, 1, 1)))])
        r = Z.Clearance([b], ob, lambda j, v: (_ for _ in ()).throw(AssertionError("asked a joint")),
                        required=1.0).row({})
        assert r.status == st, (gap, r.status, r.words)


# ---------------------------------------------------------------------------------------------------------------------
# reach

def _chart(radius, capacity):
    return lifting.Chart(radius=list(radius), capacity=list(capacity), config={})


def test_reach_stops_at_a_gap_in_the_chart():
    ch = _chart([3.0, 5.0, 8.0, 12.0], [20000.0, None, 9000.0, 4000.0])
    r = Z.reach(ch, 6000.0)
    assert r.full == 3.0 and r.longest == 12.0


def test_reach_with_a_gross_load_exactly_on_a_row_and_on_the_amber_line():
    ch = _chart([3.0, 5.0, 8.0], [20000.0, 12000.0, 8000.0])
    assert Z.reach(ch, 12000.0).full == 5.0
    assert Z.reach(ch, 8000.0).full == 8.0
    assert Z.reach(ch, 8000.000001).full == 5.0
    assert Z.reach(ch, 6000.0).amber == 8.0                     # 8 t × 0.75 = 6 t exactly
    assert Z.reach(ch, 6000.01).amber == 5.0
    assert Z.reach(ch, 0.0).full == 8.0 and Z.reach(ch, 0.0).amber == 8.0


def test_reach_with_capacities_rising_outwards():
    """A chart whose first rows hold less (a boom limited near the crane): the shortest row does not carry 6 t, a longer
    one does. No ring from the axis out is right (the next-longer-row rule needs every row in between), and the words
    must not claim more than that."""
    ch = _chart([3.0, 5.0, 8.0], [5000.0, 8000.0, 6000.0])
    r = Z.reach(ch, 6000.0)
    assert r.full is None and r.amber is None
    assert "6.00 t" in r.words


def test_reach_of_an_empty_chart_and_custom_limits():
    r = Z.reach(_chart([], []), 1000.0)
    assert r.full is None and r.longest is None and r.words
    ch = _chart([3.0, 5.0], [10000.0, 8000.0])
    r = Z.reach(ch, 7000.0, lifting.Limits(crane=0.9))
    assert r.full == 5.0 and r.amber == 5.0                      # 8 × 0.9 = 7.2 t ≥ 7 t
    assert "amber" in r.words and "5 m" in r.words


def test_reach_words_name_the_tonnes():
    ch = _chart([3.0, 5.0, 8.0], [20000.0, 12000.0, 8000.0])
    r = Z.reach(ch, 10000.0)
    assert r.full == 5.0 and r.amber == 3.0
    assert "10.00 t" in r.words and "5 m" in r.words and "3 m" in r.words
    assert "13.33 t" in r.words                                  # 10 / 0.75 worth of chart


# ---------------------------------------------------------------------------------------------------------------------
# hull, zone, inside

def test_hull_odd_inputs():
    assert Z.hull([]) == []
    assert Z.hull([(1.0, 2.0)]) == [(1.0, 2.0)]
    assert Z.hull([(1.0, 2.0), (1.0, 2.0), (1.0, 2.0)]) == [(1.0, 2.0)]
    h = Z.hull([(0, 0), (1, 1), (2, 2), (3, 3), (1.5, 1.5)])     # all on one line
    assert sorted(h) == [(0.0, 0.0), (3.0, 3.0)] and Z.polygon_area(h) == 0.0
    h = Z.hull([(0, 0), (4, 0), (4, 0), (2, 0), (4, 3), (0, 3), (2, 3), (0, 1.5)])   # points on the edges
    assert len(h) == 4 and Z.polygon_area(h) == pytest.approx(12.0)
    assert Z.hull(np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]))                      # a NumPy array


def test_hull_holds_every_point_and_is_counter_clockwise():
    rng = np.random.default_rng(5)
    for _k in range(30):
        pts = rng.normal(0, rng.uniform(0.1, 50), (rng.integers(3, 60), 2))
        h = Z.hull(pts)
        if len(h) < 3:
            continue
        assert Z.polygon_area(h) > 0
        for p in pts:
            assert Z.inside(h, p) or min(math.dist(p, q) for q in h) < 1e-5


def test_inside_against_a_brute_force_test():
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]
    assert Z.inside(sq, (1.0, 0.5)) and Z.inside(sq, (2.0, 0.5)) and Z.inside(sq, (0.0, 0.0))
    assert not Z.inside(sq, (2.01, 0.5)) and not Z.inside(sq, (1.0, -0.01))


def test_zone_holds_the_tail_swing_even_without_a_margin():
    """FOUND (small): with margin 0 the tail swing circle (OSHA 1926.1424(a): the swing radius to be marked) is drawn
    as an inscribed 32-gon: 712 of 721 points of the true 10 m circle lie outside the zone (up to 4.8 cm, 10 m ×
    (1 − cos(π/32))). The load's circles (12-gons) lose up to 3.4 % of their radius the same way."""
    z = Z.exclusion_zone((0.0, 0.0), 10.0, [], [], 0.0, margin=0.0)
    for a in np.linspace(0, 2 * math.pi, 361):
        assert Z.inside(z, (10.0 * math.cos(a), 10.0 * math.sin(a))), math.degrees(a)


def test_zone_margin_within_a_centimetre():
    """FOUND (small): a 10 m tail and a 1 m margin: points 10.99 m from the slew axis are outside the zone in most
    directions (the two inscribed polygons lose ~5 cm together) – the margin is not the margin the user typed."""
    z = Z.exclusion_zone((0.0, 0.0), 10.0, [], [], 0.0, margin=1.0)
    for a in np.linspace(0, 2 * math.pi, 361):
        assert Z.inside(z, (10.99 * math.cos(a), 10.99 * math.sin(a))), math.degrees(a)


def test_zone_holds_supports_and_path_with_margin_and_stays_convex():
    sup = [(-3.0, -2.0), (5.0, -2.0), (5.0, 2.0), (-3.0, 2.0)]
    path = [(8.0, 0.0), (6.0, 6.0), (0.0, 9.0), (0.0, 9.0)]
    z = Z.exclusion_zone((1.0, 0.0), 4.0, sup, path, load_r=1.5, margin=1.0)
    assert Z.polygon_area(z) > 0
    for p in sup + path + [(1.0, 0.0)]:
        assert Z.inside(z, p)
    for p in path:                                                # load radius + most of the margin
        for a in np.linspace(0, 2 * math.pi, 37):
            assert Z.inside(z, (p[0] + 2.4 * math.cos(a), p[1] + 2.4 * math.sin(a)))
    assert not Z.inside(z, (0.0, 9.0 + 1.5 + 1.0 + 0.05))
    # convex: every corner turns left
    for i in range(len(z)):
        o, a, b = z[i - 2], z[i - 1], z[i]
        assert (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]) > -1e-9


def test_zone_odd_inputs():
    z = Z.exclusion_zone((2.0, 3.0), 0.0, [], [], 0.0, margin=0.0)
    assert z == [(2.0, 3.0)]
    z = Z.exclusion_zone((2.0, 3.0), -1.0, [], [], -1.0, margin=0.5)
    assert len(z) >= 3 and Z.inside(z, (2.0, 3.0)) and Z.polygon_area(z) == pytest.approx(math.pi * 0.25, rel=0.02)
    z = Z.exclusion_zone((0.0, 0.0), 2.0, [], [np.array([5.0, 0.0])], 0.0, margin=0.0)
    assert Z.inside(z, (5.0, 0.0))


# ---------------------------------------------------------------------------------------------------------------------
# ground footprint

def _crane(name):
    it = LL.read_item(os.path.join(LIB, name))
    poses = {p["name"]: dict(p["values"]) for p in it.data["rig"]["poses"]}
    return it.data, LL.charts_of(it), poses


@pytest.mark.parametrize("name", ["AT-40", "AT-250", "KB-50"])
def test_pads_sum_to_the_weight_and_balance_the_moments(name):
    """Σ R = W and Σ R · (pad − centre) = W · (resultant − centre), in x and y, at many slew angles and loads; with all
    four pads down each R = W/4 · (1 ± x/a ± y/b)."""
    data, charts, poses = _crane(name)
    rig = LR.Rig(data)
    slew = rig.role["slew"]
    o = data["outriggers"]
    seen4 = seen3 = 0
    for load in (0.0, 1000.0, 3000.0, 8000.0):
        for s in range(0, 360, 40):
            v = dict(poses["Working"], **{slew: float(s)})
            ck = P.Checks(data, charts, P.Plan(load_kg=load, allowable_pa=250e3, mat=(1.0, 1.0)))
            pads = Z.footprint(ck, v)
            items = ck.sup.items(v, ck.cw, ck.hanging_kg())
            pm, x, y = lifting.resultant(items)
            W = pm * lifting.G
            if any(p.status == lifting.RED and p.force == 0.0 for p in pads) and sum(p.force for p in pads) == 0:
                continue                                             # tips: no reactions
            assert len(pads) == 4
            cx, cy = o["centre"][0], o["centre"][1]
            a = o["a"]
            b = LR.outrigger_spread(data, v) / 2.0
            ctr = [(np.mean([q[0] for q in p.corners]), np.mean([q[1] for q in p.corners])) for p in pads]
            for (px, py), (sx, sy) in zip(ctr, ((1, 1), (1, -1), (-1, 1), (-1, -1))):
                assert px == pytest.approx(cx + sx * a, abs=1e-9) and py == pytest.approx(cy + sy * b, abs=1e-9)
            F = np.array([p.force for p in pads])
            assert F.min() >= 0.0
            assert F.sum() == pytest.approx(W, rel=1e-9)
            assert float(F @ (np.array(ctr)[:, 0] - cx)) == pytest.approx(W * (x - cx), abs=1e-6 * W)
            assert float(F @ (np.array(ctr)[:, 1] - cy)) == pytest.approx(W * (y - cy), abs=1e-6 * W)
            if F.min() > 1e-6 * W:
                seen4 += 1
                for f, (sx, sy) in zip(F, ((1, 1), (1, -1), (-1, 1), (-1, -1))):
                    assert f == pytest.approx(W / 4 * (1 + sx * (x - cx) / a + sy * (y - cy) / b), rel=1e-9)
            else:
                seen3 += 1
                assert sum(p.lifted for p in pads) >= 1
            for p in pads:
                assert p.pressure == pytest.approx(p.force / 1.0, rel=1e-12)
                assert p.use == pytest.approx(p.pressure / 250e3, rel=1e-12)
    assert seen4 >= 5


def test_a_tipping_crane_paints_every_pad_red():
    data, charts, poses = _crane("AT-40")
    rig = LR.Rig(data)
    v = dict(poses["Working"], **{rig.role["slew"]: 90.0})
    pads = Z.footprint(P.Checks(data, charts, P.Plan(load_kg=200000.0, allowable_pa=250e3)), v)
    assert len(pads) == 4 and all(p.status == lifting.RED and p.lifted for p in pads)


@pytest.mark.parametrize("name", ["CC-100", "CC-750"])
def test_track_pieces_carry_the_track_shares(name):
    """Each track's pieces add up to its share of the weight (lever across the gauge) within 1 %; the piece nearest the
    load is the most loaded, the far end of a triangle carries nothing."""
    data, charts, poses = _crane(name)
    rig = LR.Rig(data)
    slew = rig.role["slew"]
    t = data["tracks"]
    g, L = t["gauge"], t["length"]
    shapes = set()
    for load in (0.0, 5000.0, 15000.0):
        for s in (0.0, 30.0, 90.0, 180.0, 270.0):
            v = dict(poses["Working"], **{slew: s})
            ck = P.Checks(data, charts, P.Plan(load_kg=load, allowable_pa=300e3))
            tr = Z.footprint(ck, v, pieces=10)
            items = ck.sup.items(v, ck.cw, ck.hanging_kg())
            pm, x, y = lifting.resultant(items)
            W = pm * lifting.G
            res = lifting.tracks(pm, x, y, g, L, t["width"])
            if not res.details:
                assert all(p.status == lifting.RED for p in tr)
                continue
            shapes.add(res.details["shape"])
            left = [p for p in tr if p.name.startswith("left")]
            right = [p for p in tr if p.name.startswith("right")]
            assert len(left) == len(right) == 10
            assert all(np.mean([q[1] for q in p.corners]) > 0 for p in left)
            sl = W * (g / 2 + y) / g
            assert sum(p.force for p in left) == pytest.approx(sl, rel=0.01)
            assert sum(p.force for p in right) == pytest.approx(W - sl, rel=0.01)
            heavy = max(left, key=lambda p: p.pressure)
            hx = np.mean([q[0] for q in heavy.corners])
            assert hx * x >= 0                                       # on the resultant's side
            if res.details["shape"] == "triangle":
                far = min(left, key=lambda p: np.mean([q[0] for q in p.corners]) * np.sign(x))
                assert far.pressure == 0.0 and far.lifted
    assert shapes == {"trapezoid", "triangle"}


def test_footprint_of_a_crane_without_masses_or_outriggers():
    data, charts, poses = _crane("AT-40")
    broken = json.loads(json.dumps(data))
    broken.pop("mass")
    assert Z.footprint(P.Checks(broken, charts, P.Plan(load_kg=1000.0)), poses["Working"]) == []
    noout = json.loads(json.dumps(data))
    noout["outriggers"]["a"] = None
    assert Z.footprint(P.Checks(noout, charts, P.Plan(load_kg=1000.0)), poses["Working"]) == []


# ---------------------------------------------------------------------------------------------------------------------
# drawings and the sheet

def _parse(svg):
    xml.dom.minidom.parseString(svg)


def test_plan_svg_with_odd_inputs():
    _parse(Z.plan_svg({"slew": (0.0, 0.0)}))
    _parse(Z.plan_svg({"slew": (5.0, 5.0), "zone": [(5.0, 5.0)], "rings": [], "patches": [], "path": [(1.0, 1.0)],
                       "obstacles": [("A <&> \"B\"", [(0, 0), (1, 1)]), ("<x>", [(0, 0), (1, 0), (1, 1)])],
                       "nearest": None}))
    _parse(Z.plan_svg({"slew": (0.0, 0.0), "rings": [(0.0, lifting.RED), (12.5, "weird")],
                       "patches": [{"corners": [(0, 0), (1, 0), (1, 1), (0, 1)], "status": "unknown"}],
                       "path": [(0.0, 0.0), (0.0, 0.0)], "nearest": [(0.0, 0.0), (0.0, 0.0)]}))
    # far from the origin, large and tiny at once
    _parse(Z.plan_svg({"slew": (1e6, -1e6), "zone": Z.exclusion_zone((1e6, -1e6), 30.0, [], [], 0.0),
                       "path": [(1e6 + 0.001, -1e6)]}))


def test_range_svg_with_odd_inputs():
    _parse(Z.range_svg([], [], None, None))
    _parse(Z.range_svg([(3.0, 10.0)], [(3.0, None), (5.0, 1000.0)], 3.0, None, hook=(3.0, 10.0), path=[(3.0, 10.0)]))
    _parse(Z.range_svg([(0.0, -5.0), (2.0, -1.0)], [(2.0, 500.0)], 2.0, 2.0, hook=(1.0, -3.0)))


def test_the_plan_svg_draws_to_scale():
    """The scale bar's length in pixels matches the drawing's scale: two path points 10 m apart are as far apart in the
    drawing as 10 m of the bar says."""
    import re
    svg = Z.plan_svg({"slew": (0.0, 0.0), "path": [(0.0, 0.0), (10.0, 0.0)], "zone": [(-5, -5), (15, -5), (15, 5),
                                                                                     (-5, 5)]})
    bar = re.search(r'<line x1="20" y1="[\d.]+" x2="([\d.]+)" y2="[\d.]+" stroke="#000" stroke-width="2"/><text '
                    r'x="20" y="[\d.]+">([\d.e+-]+) m</text>', svg)
    pts = re.search(r'<polyline points="([\d., -]+)" fill="none" stroke="#1565c0"', svg).group(1).split()
    (x0, _y0), (x1, _y1) = [tuple(map(float, p.split(","))) for p in pts]
    px_per_m = (x1 - x0) / 10.0
    assert (float(bar.group(1)) - 20.0) / float(bar.group(2)) == pytest.approx(px_per_m, rel=0.02)


class _Tags(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def test_sheet_escapes_everything_typed():
    evil = '<script>alert("x")</script> & "q"'
    row = P.Row("CLR", evil, lifting.AMBER, 0.8, value=evil, limit=evil, words=evil, amber_at=0.75)
    row.t = 12.25
    page = Z.sheet_html(evil, [(evil, evil)], "<svg></svg>", "<svg></svg>", [row, P.grey("C5", evil)], [evil])
    p = _Tags()
    p.feed(page)
    assert "script" not in p.tags
    assert "&lt;script&gt;" in page and "80 %" in page and "12.2" in page


# ---------------------------------------------------------------------------------------------------------------------
# the makers

NAMES = [n for n, c in C.CLASSES.items() if c.kind in ("AT", "KB")]


def test_tip_load_by_hand_with_a_turning_counterweight():
    """10 t carrier on the slew axis, 5 t counterweight 3 m behind the slew (turning), base 4 × 4 m round the axis,
    load 5 m out. Along an axis the crane's CoG is 1 m behind the slew: (15 + P) · 2 = P · 5 + 15 · 1... i.e. the
    resultant reaches the edge 2 m out when P = 15 · 3 / 3 = 15 t; on a diagonal it is further. The rigid 4-pad model
    agrees: 14.99 t stands, 15.02 t tips."""
    fixed, turning = [(10.0, 0.0, 0.0)], [(5.0, -3.0, 0.0)]
    tl = K.tip_load(fixed, turning, 5.0, (0.0, 2.0, 2.0))
    assert tl == pytest.approx(15.0, rel=1e-9)
    for s in range(0, 360, 5):
        th = math.radians(s)
        items = [(10.0, 0.0, 0.0), (5.0, -3.0 * math.cos(th), -3.0 * math.sin(th))]
        ok = lifting.outrigger_reactions(items + [(14.99, 5 * math.cos(th), 5 * math.sin(th))], 2.0, 2.0)
        assert ok.lifted != "tips", s
    th = 0.0
    bad = lifting.outrigger_reactions([(10.0, 0, 0), (5.0, -3.0, 0.0), (15.02, 5.0, 0.0)], 2.0, 2.0)
    assert bad.lifted == "tips"


def test_tip_load_against_a_fine_slew_search():
    """Random asymmetric cranes (CoG off the middle line, base centre off the slew axis): ``tip_load`` (72 slew angles
    + the corners) is never more than the smallest tipping load over 0.1° steps, found with
    ``lifting.outrigger_reactions``, by more than 0.5 %."""
    rng = np.random.default_rng(2)
    for _k in range(6):
        cx, a, b = rng.uniform(-1, 1), rng.uniform(2, 4), rng.uniform(1.5, 3)
        fixed = [(rng.uniform(5, 30), cx + rng.uniform(-0.5, 0.5) * a, rng.uniform(-0.2, 0.2) * b)]
        turning = [(rng.uniform(2, 8), rng.uniform(-3, 1), rng.uniform(-0.3, 0.3))]
        r = rng.uniform(4, 12)
        tl = K.tip_load(fixed, turning, r, (cx, a, b))
        if tl == 0.0 or not math.isfinite(tl):
            continue
        best = math.inf
        for s in np.arange(0.0, 360.0, 0.1):
            th = math.radians(s)
            c, si = math.cos(th), math.sin(th)
            items = fixed + [(m, u * c - w * si, u * si + w * c) for m, u, w in turning]
            M0 = sum(m for m, _x, _y in items)
            gx = sum(m * x for m, x, _y in items) / M0
            gy = sum(m * y for m, _x, y in items) / M0
            lx, ly = r * c, r * si
            # the share of the way from the CoG to the load where the rectangle's edge is crossed
            sh = math.inf
            for d, g0, lo, hi in ((lx - gx, gx, cx - a, cx + a), (ly - gy, gy, -b, b)):
                if d > 1e-12:
                    sh = min(sh, (hi - g0) / d)
                elif d < -1e-12:
                    sh = min(sh, (lo - g0) / d)
            if sh < 1.0:
                best = min(best, M0 * sh / (1 - sh))
        assert tl <= best * 1.005, (tl, best)


@pytest.mark.parametrize("name", NAMES)
def test_the_charts_base_is_the_files_outriggers(name):
    """The charts' tipping rectangle (front / rear outrigger boxes, the spread) is the file's own outrigger block, and
    the file's masses are the class's."""
    d = json.load(open(os.path.join(LIB, name, f"{name}.json"), encoding="utf-8"))
    c = C.CLASSES[name]
    if c.kind == "AT":
        fixed, turning, out_x = K.mobile_masses(c, d["cog"])
        assert d["mass"]["carrier"] == pytest.approx(c.mass_carrier)
    else:
        fixed, turning, out_x = K.knuckle_masses(c, d["cog"])
        assert d["mass"]["truck"] == pytest.approx(c.mass_truck)
    o = d["outriggers"]
    cx, a, _b = K._base(out_x, 1.0)
    assert cx == pytest.approx(o["centre"][0], abs=1e-3) and a == pytest.approx(o["a"], abs=1e-3)
    spreads = sorted(round(2 * s, 2) for s in o["spreads"].values())
    assert spreads == sorted(round(s / 1000.0, 2) for s in c.spread)
    charted = sorted({ch["config"]["outriggers"] for ch in d["charts"]})
    assert set(charted) <= set(spreads)


@pytest.mark.parametrize("name", NAMES)
def test_every_charted_row_is_under_the_tipping_share(name):
    """Each row of each chart in the file ≤ STAB × the tipping load: the row's capacity / STAB does not tip the crane
    (``outrigger_reactions``, every 2° of slew) with the file's own centres of gravity, its outrigger base, the counterweight of the chart, and
    the boom's mass where the maker puts it (``0.42 (r − pin)``; a knuckle boom ``0.40 r``)."""
    d = json.load(open(os.path.join(LIB, name, f"{name}.json"), encoding="utf-8"))
    c = C.CLASSES[name]
    L = C.layout(c)
    o = d["outriggers"]
    cx, a = o["centre"][0], o["a"]
    cog = d["cog"]
    tried = 0
    for ch in d["charts"]:
        b = ch["config"]["outriggers"] / 2.0
        if c.kind == "AT":
            stab = K.STAB_MOBILE
            xp = L.pts["xp"] / 1000.0
            fixed = [(d["mass"]["carrier"], cog["carrier"][0], cog["carrier"][1])]
            turn = [(d["mass"]["superstructure"], cog["superstructure"][0], cog["superstructure"][1])]
            cw = ch["config"].get("counterweight", 0.0)
            if cw > 0:
                turn.append((cw, cog["counterweight"][0], cog["counterweight"][1]))
            mb = c.mass_boom
        else:
            stab = K.STAB_KNUCKLE
            xp = None
            fixed = [(d["mass"]["truck"], cog["truck"][0], cog["truck"][1])]
            turn = [(d["mass"]["column"], cog["column"][0], cog["column"][1])]
            mb = c.mass_main + c.mass_outer
        for r, cap in zip(ch["radius"], ch["capacity"]):
            bx = xp + 0.42 * (r - xp) if xp is not None else 0.40 * r
            t = turn + [(mb, bx, 0.0)]
            # the load the chart allows, divided by the stability share, must not tip the crane at any slew angle
            m = 0.999 * cap / stab          # the file rounds the base to 1 mm; the charts use the layout unrounded
            for deg in range(0, 360, 2):
                th = math.radians(deg)
                co, si = math.cos(th), math.sin(th)
                items = fixed + [(mm, u * co - w * si, u * si + w * co) for mm, u, w in t]
                items.append((m, r * co, r * si))
                re = lifting.outrigger_reactions(items, a, b, (cx, 0.0))
                assert re.lifted != "tips", (name, ch["name"], r, cap, deg, re.x, re.y)
            tried += 1
    assert tried > 0


# ---------------------------------------------------------------------------------------------------------------------
# the app's sheet note

def test_the_sheet_says_which_way_the_distance_errs():
    """FOUND (words): the plan sheet's note says "Distances are a lower bound", but the clearance is measured from
    points on the moving part's surface to the obstacles' triangles – it can only be the true gap or MORE (an upper
    bound; ``core.lifting_zones`` says so itself: "the true gap, or up to ~3 cm more"). A reader takes "lower bound"
    as "at least this much room", the unsafe way round."""
    src = open(os.path.join(ROOT, "fresing_render", "blender", "lifting_zones.py"), encoding="utf-8").read()
    assert "Distances are a lower bound" not in src


# ---------------------------------------------------------------------------------------------------------------------
# Blender as a Python module

@pytest.fixture
def app():
    bpy = pytest.importorskip("bpy")
    import fresing_render
    os.environ["FRESING_LIFTING_UNDERSTOOD"] = "1"
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield bpy
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def test_the_cached_clearance_follows_an_obstacle_turned_in_place(app):
    """FOUND: ``fingerprint`` keys every object on its location only (``matrix_basis.translation``): a wall turned about
    its own origin (location unchanged) keeps the old cached clearance until something else changes; the same for a
    scale. Compared with the clearance worked out afresh after ``forget()``."""
    bpy = app
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_lifting_zones_app as A
    from fresing_render.blender import lifting as BL, lifting_zones as LZ
    sc, c, ld = A._skid_on_at40()
    hb = next(o for o in c.root.children_recursive if o.type == "MESH" and "HOOK BLOCK" in str(o.get("fr_name", "")))
    pts = np.array([hb.matrix_world @ v.co for v in hb.data.vertices])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    wall = A._wall(sc, (hi[0] + 0.8, lo[1] - 2.0, lo[2] - 1.0), (hi[0] + 1.1, hi[1] + 2.0, hi[2] + 1.0))
    vals = BL.values(sc, c)
    before = LZ.clearance_for(sc, c, ld).row(vals)
    assert before.status == lifting.RED and "SITE WALL" in before.words, before.words
    wall.rotation_euler = (0.0, 0.0, math.pi)          # about the world origin: the wall goes elsewhere
    bpy.context.view_layer.update()
    after = LZ.clearance_for(sc, c, ld).row(BL.values(sc, c))
    LZ.forget()
    fresh = LZ.clearance_for(sc, c, ld).row(BL.values(sc, c))
    assert fresh.words != before.words                 # the turn did change the clearance
    assert after.words == fresh.words, (before.words, after.words, fresh.words)
