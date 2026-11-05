"""Task 0027, the part without Blender: bit shapes, straight segments, cuts on a block.

Sizes are checked against hand-calculated ones: a 200 x 200 x 40 mm block (z 0..40), a flat
Ø10 mm end mill, a ball Ø6 mm, a 118° drill Ø8 mm.
"""

import math

import numpy as np
import pytest

mf = pytest.importorskip("manifold3d")

from fresing_render.core import machining as M  # noqa: E402

MM = 0.001
TOP = 40 * MM
DOWN = np.array([0.0, 0.0, 1.0])          # the bit's axis from tip to shank (it points down)


def block():
    return mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.0))


def path(points_mm, step_mm=1.3, frame0=1.0):
    """A path through ``points_mm`` at ``step_mm`` per frame (like an animation at constant feed)."""
    pts = [np.array(points_mm[0], float)]
    for a, b in zip(points_mm[:-1], points_mm[1:]):
        a, b = np.array(a, float), np.array(b, float)
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step_mm)))
        pts += [a + (b - a) * k / n for k in range(1, n + 1)]
    o = np.array(pts) * MM
    t = frame0 + np.arange(len(o), dtype=float)
    return M.Path(t, o, np.tile(DOWN, (len(o), 1)))


def timeline(tool, p, finished=None, detail="NORMAL"):
    wp = M.Workpiece(block(), finished, detail)
    return M.Timeline(wp, [M.Cutter(tool, detail)], [p], detail)


def removed(tiles):
    rest = mf.Manifold.batch_boolean([t.solid for t in tiles if t.ntri], mf.OpType.Add)
    return block() - rest


def bbox_mm(m):
    return np.round(np.array(m.bounding_box()) / MM, 3)


FLAT10 = M.Tool("FLAT", radius=5 * MM, length=40 * MM)
BALL6 = M.Tool("BALL", radius=3 * MM, length=30 * MM)
DRILL8 = M.Tool("DRILL", radius=4 * MM, length=40 * MM, angle=118.0)


# ---------------------------------------------------------------------------
# bit shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool", [
    FLAT10, BALL6, DRILL8,
    M.Tool("BULL", radius=5 * MM, length=30 * MM, corner=1 * MM),
    M.Tool("VEE", radius=6 * MM, length=20 * MM, angle=90.0),
])
def test_shapes_are_recognised_from_their_outline(tool):
    got = M.classify(M.tool_profile(tool, 64))
    assert got.kind == tool.kind
    assert got.radius == pytest.approx(tool.radius, rel=0.01)
    assert got.length == pytest.approx(tool.length, rel=0.001)
    if tool.kind == "BULL":
        assert got.corner == pytest.approx(tool.corner, rel=0.05)
    if tool.kind in ("VEE", "DRILL"):
        assert got.angle == pytest.approx(tool.angle, abs=1.0)


@pytest.mark.parametrize("tool", [FLAT10, BALL6, DRILL8])
def test_shapes_are_recognised_from_a_tessellated_part(tool):
    """As the importer gives it: points on rings of a coarse mesh, tilted in space."""
    pts = M.piece_points(M.tool_profile(tool, 24), 18)
    rot = np.array([[1, 0, 0], [0, math.cos(0.4), -math.sin(0.4)], [0, math.sin(0.4), math.cos(0.4)]])
    pts = pts @ rot.T + np.array([0.3, -0.1, 0.5])
    origin, d = M.axis_from_points(pts)
    prof, zmin, zmax = M.profile_from_points(pts, origin, d if d @ (rot @ DOWN) > 0 else -d)
    got = M.classify(prof)
    assert got.kind == tool.kind and got.radius == pytest.approx(tool.radius, rel=0.03)


def test_wide_shank_is_two_convex_pieces():
    prof = [(0.0, 1.5 * MM), (10 * MM, 1.5 * MM), (10 * MM, 3 * MM), (40 * MM, 3 * MM)]
    assert len(M.convex_pieces(prof)) == 2
    for tool in (FLAT10, BALL6, DRILL8):
        assert len(M.convex_pieces(M.tool_profile(tool, 40))) == 1


def test_describe():
    assert M.describe(FLAT10) == "Flat end mill Ø10.0 mm, 40 mm long"
    assert M.describe(DRILL8) == "Drill Ø8.0 mm 118°, 40 mm long"


# ---------------------------------------------------------------------------
# segments
# ---------------------------------------------------------------------------

def test_straight_moves_are_one_segment_each():
    p = path([(0, 0, 50), (0, 0, 35), (50, 0, 35), (50, 30, 35), (50, 30, 50)])
    segs = M.find_segments(p.o, p.d, 0.005 * MM)
    assert len(segs) == 4
    assert segs[0][0] == 0 and segs[-1][1] == len(p.o) - 1


def test_back_and_forth_on_one_line_is_two_segments():
    p = path([(0, 0, 35), (40, 0, 35), (10, 0, 35)])
    assert len(M.find_segments(p.o, p.d, 0.005 * MM)) == 2


# ---------------------------------------------------------------------------
# cuts
# ---------------------------------------------------------------------------

def test_straight_slot_has_the_right_width_and_depth():
    # plunge 5 mm at x = -50, mill to x = +50, back up
    p = path([(-50, 0, 50), (-50, 0, 35), (50, 0, 35), (50, 0, 50)])
    tl = timeline(FLAT10, p)
    gone = removed(tl.at(p.t[-1]))
    lo_hi = bbox_mm(gone)
    assert lo_hi == pytest.approx([-55, -5, 35, 55, 5, 40], abs=0.02)
    stadium = (100 * 10 + math.pi * 25) * 5          # mm³
    assert gone.volume() / MM ** 3 == pytest.approx(stadium, rel=0.005)
    assert tl.stats.segments == 3 and tl.stats.ops <= 3     # one boolean per straight move, not per frame


def test_pocket_and_ball_floor():
    # zig-zag pocket 60 x 40, 4 mm deep with the ball mill: floor at 36 mm (the ball's lowest point)
    pts = [(-30, -20, 50), (-30, -20, 36)]
    y = -20.0
    flip = False
    while y <= 20.0 + 1e-9:
        xs = (30.0, -30.0) if flip else (-30.0, 30.0)
        pts += [(xs[0], y, 36), (xs[1], y, 36)]
        y += 2.0
        flip = not flip
    pts.append((pts[-1][0], pts[-1][1], 50))
    p = path(pts, step_mm=2.0)
    gone = removed(timeline(BALL6, p).at(p.t[-1]))
    assert bbox_mm(gone) == pytest.approx([-33, -23, 36, 33, 23, 40], abs=0.05)


def test_drilled_hole_has_the_drill_point():
    p = path([(40, 40, 50), (40, 40, 25), (40, 40, 50)], step_mm=0.8)
    gone = removed(timeline(DRILL8, p).at(p.t[-1]))
    assert bbox_mm(gone) == pytest.approx([36, 36, 25, 44, 44, 40], abs=0.05)
    h = 4 / math.tan(math.radians(59))                # height of the 118° point
    expected = math.pi * 16 * (15 - h) + math.pi * 16 * h / 3
    assert gone.volume() / MM ** 3 == pytest.approx(expected, rel=0.01)


def test_cut_follows_the_time_and_scrubbing_gives_the_same_mesh():
    p = path([(-50, 0, 50), (-50, 0, 35), (50, 0, 35), (50, 30, 35), (-20, 30, 30), (-20, 30, 50)])
    tl = timeline(FLAT10, p)
    times = [p.t[5], p.t[40], p.t[20], p.t[-1], p.t[0], p.t[60] + 0.5, p.t[40]]
    first = {}
    for T in times:
        v, t, s = tl.mesh_at(T)
        key = float(T)
        if key in first:
            a = first[key]
            assert np.array_equal(a[0], v) and np.array_equal(a[1], t) and np.array_equal(a[2], s)
        first[key] = (v.copy(), t.copy(), s.copy())
    fresh = timeline(FLAT10, p)                  # straight to the frame, nothing before it computed
    for T in (p.t[40], p.t[60] + 0.5):
        v, t, s = fresh.mesh_at(T)
        a = first[float(T)]
        assert np.array_equal(a[0], v) and np.array_equal(a[1], t)
    # more material is gone later on
    vols = [M.volume(tl.at(T)) for T in (p.t[0], p.t[20], p.t[40], p.t[-1])]
    assert vols == sorted(vols, reverse=True) and vols[-1] < vols[1] < block().volume()


def test_half_way_through_a_move_only_half_is_cut():
    p = path([(-50, 0, 35), (50, 0, 35)], step_mm=1.0)
    tl = timeline(FLAT10, p)
    mid = p.t[0] + 50.0                         # tip at x = 0
    assert bbox_mm(removed(tl.at(mid)))[3] == pytest.approx(5.0, abs=0.02)
    assert bbox_mm(removed(tl.at(mid + 0.5)))[3] == pytest.approx(5.5, abs=0.02)   # between frames


def test_finish_at_cad_part_never_cuts_below_it():
    # the finished part: the block with a pocket 60 x 40 x 5 mm; the bit goes 3 mm too deep and wider
    pocket = mf.Manifold.cube((0.06, 0.04, 0.01)).translate((-0.03, -0.02, 0.035))
    finished = block() - pocket
    pts = [(-40, -30, 50), (-40, -30, 32)]
    y = -30.0
    flip = False
    while y <= 30.0 + 1e-9:
        xs = (40.0, -40.0) if flip else (-40.0, 40.0)
        pts += [(xs[0], y, 32), (xs[1], y, 32)]
        y += 5.0
        flip = not flip
    pts.append((pts[-1][0], pts[-1][1], 50))
    p = path(pts, step_mm=2.5)
    tiles = timeline(FLAT10, p, finished=finished).at(p.t[-1])
    rest = mf.Manifold.batch_boolean([t.solid for t in tiles if t.ntri], mf.OpType.Add)
    assert (finished - rest).volume() / MM ** 3 < 1e-3      # nothing of the finished part is gone
    assert rest.volume() == pytest.approx(finished.volume(), rel=1e-6)   # and all the rest is


def test_big_pieces_are_split_into_tiles_with_the_same_result():
    # rings of a round pocket: every frame is its own little segment, so the mesh grows fast
    o = [np.array((0, 0, 50.0))]
    for r in (6.0, 12.0, 18.0, 24.0):
        n = int(2 * math.pi * r / 1.3)
        o += [np.array((r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), 37.0))
              for k in range(n + 1)]
    o = np.array(o) * MM
    p = M.Path(np.arange(len(o), dtype=float), o, np.tile(DOWN, (len(o), 1)))
    one = timeline(FLAT10, p, detail="FAST")
    one.wp.tile_max = 10 ** 9
    split = timeline(FLAT10, p, detail="FAST")
    split.wp.tile_max = 600
    a, b = one.at(p.t[-1]), split.at(p.t[-1])
    assert sum(1 for t in b if t.ntri) > 1
    assert M.volume(b) == pytest.approx(M.volume(a), rel=1e-9)


def test_rapid_moves_above_the_block_cost_nothing():
    p = path([(-90, -90, 80), (90, 90, 80), (90, -90, 80)])
    tl = timeline(FLAT10, p)
    tl.at(p.t[-1])
    assert tl.stats.ops == 0 and tl.stats.cutting_segments == 0
