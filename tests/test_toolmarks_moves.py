"""Task 0061: every cut triangle knows the move that made it last, and what the cut-face material is told.

The part without Blender first (a 200 x 200 x 40 mm block, z 0..40, as in test_machining_core.py), then the milled
mesh's attributes in Blender: the test mill (a slot from a joint animation, no program) and the test gantry
(programs with feeds and speeds, four tools).
"""

import math
import os

import numpy as np
import pytest

mf = pytest.importorskip("manifold3d")

from fresing_render.core import machining as M  # noqa: E402
from fresing_render.core import toolmarks as TM  # noqa: E402

MM = 0.001
UP = np.array([0.0, 0.0, 1.0])            # the bit's axis, from the tip up into the tool

FLAT10 = M.Tool("FLAT", radius=5 * MM, length=40 * MM)
BALL6 = M.Tool("BALL", radius=3 * MM, length=30 * MM)
BULL10 = M.Tool("BULL", radius=5 * MM, length=30 * MM, corner=1 * MM)
DRILL8 = M.Tool("DRILL", radius=4 * MM, length=40 * MM, angle=118.0)
VEE12 = M.Tool("VEE", radius=6 * MM, length=20 * MM, angle=90.0)


def block():
    return mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.0))


def path(points_mm, step_mm=1.3):
    """A path through ``points_mm`` at ``step_mm`` per frame; frame 1 is the first point."""
    pts = [np.array(points_mm[0], float)]
    for a, b in zip(points_mm[:-1], points_mm[1:]):
        a, b = np.array(a, float), np.array(b, float)
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step_mm)))
        pts += [a + (b - a) * k / n for k in range(1, n + 1)]
    o = np.array(pts) * MM
    return M.Path(1.0 + np.arange(len(o), dtype=float), o, np.tile(UP, (len(o), 1)))


def timeline(tool, p, finished=None, tile=None):
    wp = M.Workpiece(block(), finished, "NORMAL")
    if tile:
        wp.tile_max = tile
    return M.Timeline(wp, [M.Cutter(tool, "NORMAL")], [p], "NORMAL")


def row_of(tl, a_mm, b_mm) -> int:
    """The row in ``tl.moves`` of the move from ``a_mm`` to ``b_mm``."""
    mk = tl.moves
    hit = [k for k in range(len(mk)) if np.allclose(mk.o0[k] / MM, a_mm, atol=1e-6)
           and np.allclose(mk.o1[k] / MM, b_mm, atol=1e-6)]
    assert len(hit) == 1, (a_mm, b_mm, hit)
    return hit[0]


class Faces:
    """The mesh at a time, with what each triangle is told; lookups by place (mm)."""

    def __init__(self, tl, T=None):
        self.tl = tl
        T = float(tl.paths[0].t[-1]) if T is None else float(T)
        self.v, self.t, self.src, self.move, (self.o, self.d, self.a, self.p) = tl.mesh_at(T, marks=True)
        P = self.v[self.t].astype(float)
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        self.area = np.linalg.norm(n, axis=1) / 2
        self.n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
        self.P = P / MM
        self.c = self.P.mean(axis=1)
        self.kind = self.p[:, 0].astype(int)

    def top(self, x, y) -> int:
        """The triangle seen from straight above at (x, y)."""
        A, B, C = self.P[:, 0, :2], self.P[:, 1, :2], self.P[:, 2, :2]
        q = np.array([x, y], float)

        def side(a, b):
            return (b[:, 0] - a[:, 0]) * (q[1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (q[0] - a[:, 0])

        s0, s1, s2 = side(A, B), side(B, C), side(C, A)
        inside = (self.n[:, 2] > 1e-3) & (s0 >= -1e-9) & (s1 >= -1e-9) & (s2 >= -1e-9)
        cand = np.flatnonzero(inside)
        assert len(cand), (x, y)
        # the height of each candidate's plane at (x, y)
        z = self.P[cand, 0, 2] - ((q[0] - self.P[cand, 0, 0]) * self.n[cand, 0]
                                  + (q[1] - self.P[cand, 0, 1]) * self.n[cand, 1]) / self.n[cand, 2]
        return int(cand[np.argmax(z)])

    def top_z(self, x, y) -> float:
        k = self.top(x, y)
        q = np.array([x, y], float)
        return float(self.P[k, 0, 2] - ((q[0] - self.P[k, 0, 0]) * self.n[k, 0]
                                        + (q[1] - self.P[k, 0, 1]) * self.n[k, 1]) / self.n[k, 2])

    def floor(self, z_mm, tol=1e-3):
        """Cut triangles lying flat at this height, facing up."""
        return (self.src < 0) & (self.n[:, 2] > 0.999) & (np.abs(self.c[:, 2] - z_mm) < tol)

    def walls(self):
        return (self.src < 0) & (np.abs(self.n[:, 2]) < 0.01)


# pass 1 along X 3 mm deep (floor at z 37), lift, pass 2 along Y 6 mm deep (floor at z 34): a cross
CROSS = [(-40, 0, 50), (-40, 0, 37), (40, 0, 37), (40, 0, 50), (0, -40, 50), (0, -40, 34), (0, 40, 34), (0, 40, 50)]
SPOTS_X = [(-30, 0), (-20, 3), (20, -3), (30, 1), (-8, 2), (9, -4)]       # on pass 1's floor, outside the crossing
SPOTS_Y = [(0, -30), (2, -15), (-3, 20), (1, 33), (0, 0), (3, 3), (-4, -4)]   # on pass 2's floor (incl. the crossing)


# ---------------------------------------------------------------------------
# which move made a face
# ---------------------------------------------------------------------------

def test_results_keep_their_shape():
    tl = timeline(FLAT10, path(CROSS))
    T = float(tl.paths[0].t[-1])
    assert len(tl.mesh_at(T)) == 3
    v, t, src, move = tl.mesh_at(T, moves=True)
    assert move.dtype == np.int32 and len(move) == len(t) == len(src)
    out = tl.mesh_at(T, marks=True)
    assert len(out) == 5 and all(a.dtype == np.float32 and a.shape == (len(t), 3) for a in out[4])
    tiles = tl.at(T)
    assert len(tl.wp.mesh(tiles)) == 3 and len(tl.wp._tile_mesh(tiles[0].solid)) == 3
    assert np.array_equal(tl.wp.mesh(tiles, moves=True, ids=tl.cut_ids)[3], move)
    # stock faces: no move; every face a bit made: a move
    assert np.all(move[src >= 0] == -1) and np.all(move[src < 0] >= 0)
    assert set(np.unique(move[src < 0])) <= set(range(len(tl.moves)))


def test_two_passes_across_each_other():
    tl = timeline(FLAT10, path(CROSS))
    one, two = row_of(tl, (-40, 0, 37), (40, 0, 37)), row_of(tl, (0, -40, 34), (0, 40, 34))
    # before the second pass: the crossing still shows the first pass
    T1 = float(tl.moves.t1[one])
    f = Faces(tl, T1)
    for x, y in SPOTS_X + [(0, 0), (3, 3), (-4, -4)]:
        k = f.top(x, y)
        assert f.move[k] == one and f.top_z(x, y) == pytest.approx(37.0, abs=1e-3), (x, y)
    # after it: the re-cut area shows the new pass, the untouched area the old one
    f = Faces(tl)
    for x, y in SPOTS_X:
        k = f.top(x, y)
        assert f.move[k] == one and f.top_z(x, y) == pytest.approx(37.0, abs=1e-3), (x, y)
    for x, y in SPOTS_Y:
        k = f.top(x, y)
        assert f.move[k] == two and f.top_z(x, y) == pytest.approx(34.0, abs=1e-3), (x, y)
    # whole floors: every flat cut face at 37 mm is the first pass's, at 34 mm the second's
    assert set(f.move[f.floor(37.0)]) == {one} and set(f.move[f.floor(34.0)]) == {two}
    assert f.area[f.floor(34.0)].sum() / MM ** 2 == pytest.approx(80 * 10 + math.pi * 25, rel=0.01)
    assert f.area[f.floor(37.0)].sum() / MM ** 2 == pytest.approx(70 * 10 + math.pi * 25, rel=0.01)
    assert set(f.move[f.src < 0]) == {one, two}          # the plunges and the moves back out: their pass
    for z, pass_dir in ((37.0, (1, 0, 0)), (34.0, (0, 1, 0))):
        fl = f.floor(z)
        assert set(f.kind[fl]) == {TM.ARCS} and np.allclose(f.d[fl], pass_dir, atol=1e-6)
    # the second pass's walls in the crossing are its own, the first pass's walls outside it are the first's
    w = f.walls()
    near = w & (np.abs(f.c[:, 0]) < 5.01) & (np.abs(f.c[:, 1]) < 4.9) & (f.c[:, 2] < 36.9)
    assert near.any() and set(f.move[near]) == {two}
    far = w & (np.abs(f.c[:, 0]) > 8) & (np.abs(f.c[:, 0]) < 38)
    assert far.any() and set(f.move[far]) == {one}


def test_a_shallower_second_pass_leaves_the_deeper_floor_alone():
    pts = [(-40, 0, 50), (-40, 0, 34), (40, 0, 34), (40, 0, 50), (0, -40, 50), (0, -40, 37), (0, 40, 37), (0, 40, 50)]
    tl = timeline(FLAT10, path(pts))
    deep, shallow = row_of(tl, (-40, 0, 34), (40, 0, 34)), row_of(tl, (0, -40, 37), (0, 40, 37))
    f = Faces(tl)
    for x, y in [(0, 0), (3, 3), (-30, 0), (25, -2)]:           # the deep floor, also where the second pass crossed
        assert f.move[f.top(x, y)] == deep and f.top_z(x, y) == pytest.approx(34.0, abs=1e-3)
    for x, y in [(0, -30), (2, 25), (-3, 12)]:
        assert f.move[f.top(x, y)] == shallow and f.top_z(x, y) == pytest.approx(37.0, abs=1e-3)


def test_scrubbing_and_tiles_give_the_same_moves():
    p = path(CROSS)
    tl = timeline(FLAT10, p)
    seen = {}
    times = [float(x) for x in (p.t[40], p.t[-1], p.t[90], p.t[20], p.t[40] + 0.4, p.t[90], p.t[-1], 1.0, p.t[40])]
    for T in times:
        out = tl.mesh_at(T, marks=True)
        flat = list(out[:4]) + list(out[4])
        if T in seen:
            assert all(np.array_equal(a, b) for a, b in zip(seen[T], flat)), T
        seen[T] = [np.array(a) for a in flat]
    # cut into small tiles: other triangles, the same answer at every spot
    small = timeline(FLAT10, p, tile=60)
    assert small.mesh_at(float(p.t[-1])) and small.stats.tiles > 3
    for T in (float(p.t[90]), float(p.t[-1])):
        a, b = Faces(tl, T), Faces(small, T)
        for x, y in SPOTS_X + SPOTS_Y + [(-43, 2), (2, 43), (60, 60)]:
            ka, kb = a.top(x, y), b.top(x, y)
            assert a.move[ka] == b.move[kb], (T, x, y)
            assert a.kind[ka] == b.kind[kb] and np.allclose(a.o[ka], b.o[kb]) and np.allclose(a.p[ka], b.p[kb])
    # the faces where a tile was cut in two belong to nobody: not stock, no move
    b = Faces(small)
    caps = (b.src < 0) & (b.move < 0)
    assert caps.any() and np.all(b.kind[caps] == TM.NONE) and np.all(np.abs(b.n[caps, 2]) < 1e-6)


def test_with_the_finished_part_the_faces_still_name_the_move():
    """Finish at the CAD part: the cut stops at the part's surface (z 36); those faces are the move's too."""
    keep = mf.Manifold.cube((0.2, 0.2, 0.036)).translate((-0.1, -0.1, 0.0))
    p = path(CROSS)
    for tile in (None, 60):
        tl = timeline(FLAT10, p, finished=keep, tile=tile)
        one, two = row_of(tl, (-40, 0, 37), (40, 0, 37)), row_of(tl, (0, -40, 34), (0, 40, 34))
        f = Faces(tl)
        for x, y in SPOTS_Y:                    # the second pass wanted 34 mm: it ends on the part at 36
            k = f.top(x, y)
            assert f.top_z(x, y) == pytest.approx(36.0, abs=1e-3) and f.move[k] == two, (tile, x, y)
            assert f.kind[k] == TM.ARCS
        for x, y in SPOTS_X:
            assert f.move[f.top(x, y)] == one and f.top_z(x, y) == pytest.approx(37.0, abs=1e-3)
        assert np.all(f.move[f.src < 0][f.kind[f.src < 0] == TM.NONE] == -1)


def test_the_ids_kept_stay_bounded(monkeypatch):
    p = path(CROSS)
    ref = timeline(FLAT10, p)
    want = {T: [np.array(a) for a in ref.mesh_at(T, moves=True)] for T in (float(p.t[90]), float(p.t[-1]))}
    monkeypatch.setattr(M.Timeline, "IDS_MAX", 25)
    tl = timeline(FLAT10, p)
    most = 0
    for rnd in range(4):
        for T in p.t[::3]:
            tl.mesh_at(float(T), moves=True)
            most = max(most, len(tl.cut_ids))
    assert most <= 25 + len(tl.segs) + 1               # (one check per frame; a frame adds at most every move)
    for T, arrays in want.items():                     # forgetting changes nothing
        got = tl.mesh_at(T, moves=True)
        assert all(np.array_equal(a, b) for a, b in zip(arrays, got)), T


# ---------------------------------------------------------------------------
# the kind of marks
# ---------------------------------------------------------------------------

SLOT = [(-40, 0, 50), (-40, 0, 35), (40, 0, 35), (40, 0, 50)]          # plunge, 80 mm along X 5 mm deep, out


def test_a_slot_has_arcs_on_its_floor_and_lines_on_its_walls():
    tl = timeline(FLAT10, path(SLOT))
    down, along = row_of(tl, (-40, 0, 50), (-40, 0, 35)), row_of(tl, (-40, 0, 35), (40, 0, 35))
    f = Faces(tl)
    fl = f.floor(35.0)
    # the whole floor shows the pass's arcs: also under the plunge and where the bit left straight up
    assert f.area[fl].sum() / MM ** 2 == pytest.approx(80 * 10 + math.pi * 25, rel=0.01)
    assert set(f.kind[fl]) == {TM.ARCS}
    assert np.allclose(f.d[fl], (1, 0, 0), atol=1e-6) and np.allclose(f.a[fl], (0, 0, 1), atol=1e-6)
    assert np.allclose(f.p[fl, 1], 5 * MM) and np.allclose(f.p[fl, 2], tl.moves.per_tooth[along])
    assert np.allclose(f.o[fl], np.array((-40, 0, 35)) * MM, atol=1e-7)        # nothing cut before: the start
    # the plunge before and the move straight back out lie on the pass's own faces: one move, one kind of marks
    assert list(tl.moves.owner) == [along, along, along] and down == along - 1
    assert set(f.move[f.src < 0]) == {along}
    # the walls: lines along the axis, counted along the feed; also the round ends
    w = f.walls()
    assert w.any() and set(f.kind[w]) == {TM.FLANK} and np.allclose(f.d[w], (1, 0, 0), atol=1e-6)
    assert np.allclose(f.p[w, 2], tl.moves.per_tooth[along])
    # while the bit is still on its way down the hole already shows the same move
    early = Faces(tl, float(tl.moves.t0[along]) - 3.0)
    assert (early.src < 0).any() and set(early.move[early.src < 0]) == {along}
    # the stock's own faces: nothing
    assert np.all(f.kind[f.src >= 0] == TM.NONE) and np.all(f.o[f.src >= 0] == 0) and np.all(f.a[f.src >= 0] == 0)


def test_a_wall_cut_in_two_depths_knows_its_step_down():
    """Two depths along the same line: the wall is one flat face of the deeper pass, so nothing in the mesh shows
    where the depths met. The deeper pass's wall faces carry the step-down (3 mm) for the line the marks draw; a
    slot somewhere else on the block, at yet another depth, has none."""
    pts = [(-40, 0, 50), (-40, 0, 37), (40, 0, 37), (40, 0, 50), (-40, 0, 50), (-40, 0, 34), (40, 0, 34),
           (40, 0, 50), (-40, 30, 50), (-40, 30, 36), (40, 30, 36), (40, 30, 50)]
    tl = timeline(FLAT10, path(pts))
    first, deep = row_of(tl, (-40, 0, 37), (40, 0, 37)), row_of(tl, (-40, 0, 34), (40, 0, 34))
    other = row_of(tl, (-40, 30, 36), (40, 30, 36))
    assert tl.moves.step[deep] == pytest.approx(3 * MM, abs=1e-6)
    assert tl.moves.step[first] == 0.0 and tl.moves.step[other] == 0.0
    f = Faces(tl)
    w = f.walls()
    mine = w & (f.move == deep)
    assert mine.any() and set(f.kind[mine]) == {TM.FLANK}
    assert np.allclose(f.p[mine, 1], 3 * MM, atol=1e-6)
    there = w & (f.move == other)
    assert there.any() and np.allclose(f.p[there, 1], 0.0)
    # the floor's arcs still carry the tool's flat radius
    fl = f.floor(34.0)
    assert np.allclose(f.p[fl, 1], 5 * MM)


def test_a_plunge_has_rings():
    tl = timeline(FLAT10, path([(0, 0, 50), (0, 0, 33), (0, 0, 50)]))
    f = Faces(tl)
    cut = f.src < 0
    assert set(f.move[cut]) == {row_of(tl, (0, 0, 50), (0, 0, 33))} and list(tl.moves.owner) == [0, 0]
    assert set(f.kind[f.floor(33.0)]) == {TM.RINGS} and set(f.kind[f.walls()]) == {TM.RINGS_WALL}
    assert set(f.kind[cut]) == {TM.RINGS, TM.RINGS_WALL}
    assert np.allclose(f.d[cut], 0) and np.allclose(f.a[cut], (0, 0, 1))
    assert np.allclose(f.p[f.floor(33.0), 2], tl.moves.per_rev[0]) and np.allclose(f.p[f.floor(33.0), 1], 5 * MM)
    assert np.allclose(f.p[f.walls(), 2], tl.moves.per_rev[0])                  # the wall: one ring per turn
    assert np.allclose(f.o[cut], np.array((0, 0, 50)) * MM, atol=1e-7)          # on the axis: the move's start


def test_a_ball_pass_has_lines_across_it():
    tl = timeline(BALL6, path([(-40, 0, 50), (-40, 0, 38), (40, 0, 38), (40, 0, 50)]))
    along = row_of(tl, (-40, 0, 38), (40, 0, 38))
    f = Faces(tl)
    mid = (f.src < 0) & (np.abs(f.c[:, 0]) < 36)
    assert mid.any() and set(f.move[mid]) == {along} and set(f.kind[mid]) == {TM.ACROSS}
    assert np.allclose(f.p[mid, 1], 0.0) and np.allclose(f.p[mid, 2], tl.moves.per_tooth[along])
    assert np.allclose(f.d[mid], (1, 0, 0), atol=1e-6)


def test_a_drill_has_rings():
    tl = timeline(DRILL8, path([(10, 10, 50), (10, 10, 25), (10, 10, 50)]))
    f = Faces(tl)
    cut = f.src < 0
    cone = cut & (f.n[:, 2] > 0.1)
    assert cone.any() and set(f.kind[cone]) == {TM.RINGS}
    assert f.walls().any() and set(f.kind[f.walls()]) == {TM.RINGS_WALL}
    assert np.allclose(f.p[cut, 1], 0.0)                                       # a point: no flat bottom


def test_drill_point_rings_are_spaced_by_the_feed_per_turn():
    """Task 0096: the rings on a drill's point (and a plunge's bottom) are one per turn of the spindle - F / S, as
    the hole's wall - no longer a fixed 0.08 mm; still kept between the limits."""
    tl = timeline(DRILL8, path([(10, 10, 50), (10, 10, 25), (10, 10, 50)]))
    for per_rev in (0.05 * MM, 0.2 * MM):
        tl.set_feeds(np.full(len(tl.moves), per_rev / 2), np.full(len(tl.moves), per_rev))
        f = Faces(tl)
        cone = (f.src < 0) & (f.n[:, 2] > 0.1)
        assert cone.any() and set(f.kind[cone]) == {TM.RINGS}
        assert np.allclose(f.p[cone, 2], per_rev), (per_rev, np.unique(f.p[cone, 2]))
        assert np.allclose(f.p[f.walls(), 2], per_rev)
    tl.set_feeds(np.full(len(tl.moves), 1e-9), np.full(len(tl.moves), 1e-9))
    f = Faces(tl)
    assert np.allclose(f.p[(f.src < 0) & (f.n[:, 2] > 0.1), 2], TM.SPACING_MIN)


def test_a_drill_moved_sideways_still_has_rings_on_its_point():
    tl = timeline(DRILL8, path([(-20, 0, 38), (20, 0, 38)]))
    f = Faces(tl)
    slanted = (f.src < 0) & (f.n[:, 2] > 0.1) & (f.n[:, 2] < 0.99)
    assert slanted.any() and set(f.kind[slanted]) == {TM.RINGS}


def test_a_v_bit_has_lines_along_the_path():
    tl = timeline(VEE12, path([(-40, 0, 50), (-40, 0, 37), (40, 0, 37), (40, 0, 50)]))
    along = row_of(tl, (-40, 0, 37), (40, 0, 37))
    f = Faces(tl)
    mid = (f.src < 0) & (np.abs(f.c[:, 0]) < 36)
    assert mid.any() and set(f.move[mid]) == {along} and set(f.kind[mid]) == {TM.ALONG}
    assert np.allclose(f.p[mid, 2], TM.SPACING_ALONG) and np.allclose(f.d[mid], (1, 0, 0), atol=1e-6)


def test_who_shows_whose_marks():
    """Standing still and straight back out: the move before. A plunge: the sideways move from its bottom –
    but not when the bit comes out again first (pecking), or when the next move starts somewhere else."""
    pts = [(-40, 0, 50), (-40, 0, 37), (40, 0, 37), (40, 0, 50),            # 0 plunge, 1 pass, 2 out
           (60, 0, 50), (60, 0, 30), (60, 0, 45), (60, 0, 25), (60, 0, 50),  # 3 over, 4 peck, 5 out, 6 peck, 7 out
           (60, 30, 50)]                                                     # 8 over
    tl = timeline(FLAT10, path(pts))
    assert list(tl.moves.owner) == [1, 1, 1, 3, 4, 4, 6, 6, 8]
    f = Faces(tl)
    hole = (f.src < 0) & (np.hypot(f.c[:, 0] - 60, f.c[:, 1]) < 5.01)
    assert set(f.move[hole]) <= {4, 6} and set(f.kind[hole]) == {TM.RINGS, TM.RINGS_WALL}
    assert set(f.kind[f.floor(25.0)]) == {TM.RINGS}
    # a bit that waits at the bottom of its plunge before it goes sideways (the wait is part of the plunge)
    o = np.array([(0, 0, 50), (0, 0, 44), (0, 0, 37), (0, 0, 37), (0, 0, 37), (10, 0, 37), (20, 0, 37)], float) * MM
    p = M.Path(1.0 + np.arange(len(o)), o, np.tile(UP, (len(o), 1)))
    tl = timeline(FLAT10, p)
    assert len(tl.moves) == 2 and list(tl.moves.owner) == [1, 1]
    # a bit that never moves, in the block: one move, its own
    o = np.tile(np.array([(0.0, 0.0, 37.0)]) * MM, (4, 1))
    tl = timeline(FLAT10, M.Path(1.0 + np.arange(4), o, np.tile(UP, (4, 1))))
    f = Faces(tl)
    assert list(tl.moves.owner) == [0] and set(f.kind[f.src < 0]) == {TM.RINGS, TM.RINGS_WALL}


def test_a_bull_nose_has_arcs_of_its_flat_and_lines_on_its_corner():
    tl = timeline(BULL10, path([(-40, 0, 36), (40, 0, 36)]))
    f = Faces(tl)
    fl = f.floor(36.0)
    assert set(f.kind[fl]) == {TM.ARCS} and np.allclose(f.p[fl, 1], 4 * MM)     # R - corner radius
    corner = (f.src < 0) & (f.n[:, 2] > 0.1) & (f.n[:, 2] < 0.99) & (np.abs(f.c[:, 0]) < 36)
    assert corner.any() and set(f.kind[corner]) == {TM.ACROSS}
    w = f.walls() & (np.abs(f.c[:, 0]) < 36)
    assert w.any() and set(f.kind[w]) == {TM.FLANK}


def test_a_tilted_tool_is_judged_against_its_own_axis():
    """The same slot with everything turned 30° about X: the kinds follow the tool's axis, not Z."""
    ang = math.radians(30)
    rot = np.array([[1, 0, 0], [0, math.cos(ang), -math.sin(ang)], [0, math.sin(ang), math.cos(ang)]])
    p0 = path([(-40, 0, 60), (-40, 0, 37), (40, 0, 37), (40, 0, 60)])
    centre = np.array([0.0, 0.0, 0.04])
    o = (p0.o - centre) @ rot.T + centre
    p = M.Path(p0.t, o, np.tile(rot @ UP, (len(o), 1)))
    tl = timeline(FLAT10, p)
    f = Faces(tl)
    axis = rot @ UP
    cut = f.src < 0
    c = f.n[cut] @ axis
    assert np.all(f.kind[cut][c > 0.999] == TM.ARCS) and np.any(c > 0.999)
    assert set(f.kind[cut][np.abs(c) < 0.01]) <= {TM.FLANK, TM.RINGS_WALL}
    assert np.allclose(f.a[cut], axis, atol=1e-6)


# ---------------------------------------------------------------------------
# spacing, and marks that carry on
# ---------------------------------------------------------------------------

def test_marks_carry_on_from_one_move_into_the_next():
    """Two moves on one line with a hop between them: counted from either move's attributes, a point's place in
    the marks differs by a whole number of marks."""
    pts = [(-40, 0, 37), (-3.3, 0, 37), (-3.3, 0, 39), (-3.3, 0, 37), (40, 0, 37)]
    tl = timeline(FLAT10, path(pts))
    a, b = row_of(tl, (-40, 0, 37), (-3.3, 0, 37)), row_of(tl, (-3.3, 0, 37), (40, 0, 37))
    assert tl.moves.dist[a] == 0.0 and tl.moves.dist[b] == pytest.approx(36.7 * MM, abs=1e-9)
    tl.set_feeds(np.full(len(tl.moves), 0.0437 * MM), np.full(len(tl.moves), 0.131 * MM))
    f = Faces(tl)
    ka, kb = f.top(-30, 0), f.top(30, 0)
    assert (f.move[ka], f.move[kb]) == (a, b) and f.kind[ka] == f.kind[kb] == TM.ARCS
    sp = float(f.p[ka, 2])
    assert sp == pytest.approx(0.0437 * MM, rel=1e-6) and f.p[kb, 2] == f.p[ka, 2]
    P = np.array([0.012, 0.001, 0.037])
    ua, ub = (P - f.o[ka].astype(float)) @ f.d[ka], (P - f.o[kb].astype(float)) @ f.d[kb]
    turns = (ua - ub) / sp
    assert abs(turns - round(turns)) < 2e-3, turns
    # the walls count the same way
    wa = np.flatnonzero(f.walls() & (f.move == a))[0]
    wb = np.flatnonzero(f.walls() & (f.move == b) & (f.kind == TM.FLANK))[0]
    turns = ((P - f.o[wa].astype(float)) @ f.d[wa] - (P - f.o[wb].astype(float)) @ f.d[wb]) / float(f.p[wa, 2])
    assert abs(turns - round(turns)) < 2e-3, turns
    # the start is moved back by less than one mark, along the feed
    back = (tl.moves.o0[b] - f.o[kb].astype(float)) @ f.d[kb]
    assert -1e-8 <= back < sp + 1e-8 and back == pytest.approx(math.fmod(36.7 * MM, sp), abs=2e-8)


def test_distance_cut_before_counts_sideways_moves_only():
    pts = [(-40, 0, 50), (-40, 0, 37), (0, 0, 37), (0, 30, 37), (0, 30, 50), (90, 30, 50), (90, 30, 37), (90, 60, 37)]
    tl = timeline(FLAT10, path(pts))
    mk = tl.moves
    assert mk.dist[row_of(tl, (-40, 0, 37), (0, 0, 37))] == 0.0
    assert mk.dist[row_of(tl, (0, 0, 37), (0, 30, 37))] == pytest.approx(40 * MM)
    assert mk.dist[row_of(tl, (0, 30, 37), (0, 30, 50))] == pytest.approx(70 * MM)
    # the move 13 mm above the block does not count
    assert mk.dist[row_of(tl, (90, 30, 37), (90, 60, 37))] == pytest.approx(70 * MM)
    assert list(mk.t0) == sorted(mk.t0) and np.all(mk.t1 >= mk.t0) and len(mk) == len(tl.segs)
    assert np.allclose(np.linalg.norm(mk.d, axis=1), 1.0) and set(mk.bit) == {0}


def test_set_feeds_sets_the_spacing():
    tl = timeline(FLAT10, path(SLOT))
    n = len(tl.moves)
    typical = M.typical_feed("")[0]
    assert np.allclose(tl.moves.per_tooth, typical) and np.allclose(tl.moves.per_rev, 3 * typical)
    f = Faces(tl)
    assert np.allclose(f.p[f.floor(35.0), 2], typical)
    tl.set_feeds(np.full(n, 0.1 * MM), np.full(n, 0.3 * MM))
    assert not tl.mesh_cache                                    # the marks worked out before are forgotten
    f = Faces(tl)
    assert np.allclose(f.p[f.floor(35.0), 2], 0.1 * MM)
    assert np.allclose(f.p[f.walls(), 2], 0.1 * MM)
    tl.set_feeds(np.full(n, 5 * MM), np.full(n, 1e-9))          # never further apart or closer than the limits
    f = Faces(tl)
    assert np.allclose(f.p[f.floor(35.0), 2], TM.SPACING_MAX)
    hole = timeline(FLAT10, path([(0, 0, 50), (0, 0, 33), (0, 0, 50)]))
    hole.set_feeds(np.full(2, 0.1 * MM), np.full(2, 0.3 * MM))
    f = Faces(hole)
    assert np.allclose(f.p[f.walls(), 2], 0.3 * MM)             # a plunged hole's wall: one ring per turn
    hole.set_feeds(np.full(2, 5 * MM), np.full(2, 1e-9))
    assert np.allclose(Faces(hole).p[f.walls(), 2], TM.SPACING_MIN)
    with pytest.raises(ValueError):
        tl.set_feeds(np.zeros(n + 1), np.zeros(n + 1))


def test_typical_feeds_by_material():
    assert M.typical_feed("aluminium_machined") == (pytest.approx(0.05 * MM), "aluminium")
    assert M.typical_feed("steel_raw") == (pytest.approx(0.03 * MM), "steel")
    assert M.typical_feed("stainless_brushed") == (pytest.approx(0.025 * MM), "stainless steel")
    assert M.typical_feed("cast_iron") == (pytest.approx(0.04 * MM), "cast iron")
    assert M.typical_feed("brass") == (pytest.approx(0.04 * MM), "brass")
    assert M.typical_feed("copper")[1] == "copper" and M.typical_feed("bronze")[1] == "bronze"
    assert M.typical_feed("pom_white") == (pytest.approx(0.08 * MM), "plastic")
    assert M.typical_feed("paint") == (pytest.approx(0.04 * MM), "") == M.typical_feed("")
    assert [M.default_flutes(k) for k in ("FLAT", "BALL", "VEE", "DRILL", "BULL", "CUSTOM")] == [3, 2, 2, 2, 4, 3]


def test_flat_bottoms():
    def r(tool):
        return M.flat_radius(M.Cutter(tool, "NORMAL"))
    assert r(FLAT10) == pytest.approx(5 * MM) and r(BULL10) == pytest.approx(4 * MM)
    assert r(BALL6) == 0.0 and r(DRILL8) == 0.0 and r(VEE12) == 0.0
    face = M.Tool("CUSTOM", radius=25 * MM, length=6 * MM, profile=((0.0, 25 * MM), (6 * MM, 31 * MM)))
    assert r(face) == pytest.approx(25 * MM)
    assert r(M.Tool("BULL", radius=5 * MM, length=30 * MM, corner=4.9 * MM)) == 0.0     # nearly a ball


# ---------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
GANTRY = os.path.join(HERE, "data", "test_gantry.step")


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def _scene(bpy, tmp_path, model, axes):
    import addon_utils
    from mathutils import Vector
    from fresing_render.blender import gcode, joints, machining
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    for name, asm, d in axes:
        o = _ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    return sc


def _ob(sc, name):
    from fresing_render.blender import build
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _click(bpy, o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


class Milled:
    """The milled mesh as Blender has it: per face its place, normal, material slot and the four attributes."""

    def __init__(self, sc, name):
        from fresing_render.blender import machining
        self.ob = _ob(sc, name)
        me = self.ob.data
        n = len(me.polygons)
        self.n_faces = n
        self.names = [a.name for a in me.attributes]

        def read(get, key, width=3):
            a = np.empty(n * width, np.float32)
            get(key, a)
            return a.reshape(n, width) if width > 1 else a

        self.c = read(me.polygons.foreach_get, "center")
        self.nrm = read(me.polygons.foreach_get, "normal")
        mi = np.empty(n, np.int32)
        me.polygons.foreach_get("material_index", mi)
        self.all_cut = mi == me[machining.CUT_SLOT]
        # (the mesh has a few triangles without area, two corners on one spot: they have no direction)
        self.cut = self.all_cut & (read(me.polygons.foreach_get, "area", 1) > 1e-12)
        self.attr = {}
        for name_ in TM.ATTRS:
            a = me.attributes.get(name_)
            if a is not None:
                assert a.domain == "FACE" and a.data_type == "FLOAT_VECTOR" and len(a.data) == n
                self.attr[name_] = read(a.data.foreach_get, "vector")
        if len(self.attr) == 4:
            self.o, self.d, self.a, self.p = (self.attr[k] for k in TM.ATTRS)
            self.kind = self.p[:, 0].astype(int)
        self.world = np.array(self.ob.matrix_world)

    def flat(self, z, y=None, tol=1.0):
        """Cut faces lying flat at height ``z`` in the world (mm), facing up; with ``y``: centre within ``tol``
        mm of that y."""
        w = (self.c @ self.world[:3, :3].T + self.world[:3, 3]) / MM
        up = self.nrm @ self.world[:3, :3].T
        sel = self.cut & (up[:, 2] > 0.999) & (np.abs(w[:, 2] - z) < 0.02)
        if y is not None:
            sel &= np.abs(w[:, 1] - y) < tol
        return sel


def test_the_milled_mesh_has_the_attributes(blender, tmp_path):
    """Test mill, a slot from a joint animation (no program): 5 mm deep, 50 mm along X, flat end mill Ø10."""
    bpy = blender
    from fresing_render.blender import animation, machining
    sc = _scene(bpy, tmp_path, MILL, (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)),
                                      ("Z", "Z.ASM", (0, 0, 1))))
    a = sc.fresing.animations.add()
    a.name, a.tail = "Mill", 0.0
    for j, start, dur, to in (("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    frames = animation.bake(sc, a)["frames"]
    _click(bpy, _ob(sc, "END MILL D10"))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    _click(bpy, _ob(sc, "STOCK 200x200x40"))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    machining.sample(sc)
    sc.frame_set(frames)
    m = Milled(sc, "STOCK 200x200x40")
    assert len(m.attr) == 4 and m.n_faces > 100
    assert np.all(m.kind[~m.all_cut] == TM.NONE) and np.all(m.kind[m.all_cut] != TM.NONE)
    # the slot's floor (world z 65 mm): arcs of the Ø10 bit, fed along X, a typical feed for the block
    fl = m.cut & (m.nrm[:, 2] > 0.999)
    assert fl.any() and set(m.kind[fl]) == {TM.ARCS}
    typical, _words = core_typical(sc)
    assert np.allclose(m.p[fl, 1], 5 * MM, atol=1e-6) and np.allclose(m.p[fl, 2], typical, rtol=1e-5)
    assert np.allclose(np.abs(m.d[fl] @ np.array([1.0, 0, 0], np.float32)), 1.0, atol=1e-4)
    # the path and the mesh are in the same space (the workpiece's own): the floor lies in the plane of the
    # bit's tip, square to its axis, and the walls are FLANK along the same feed
    q = m.c[fl] - m.o[fl]
    assert np.max(np.abs(np.einsum("ij,ij->i", q, m.a[fl]))) < 2e-6
    assert np.allclose(np.einsum("ij,ij->i", m.nrm[fl], m.a[fl]), 1.0, atol=1e-4)
    side = np.abs(np.einsum("ij,ij->i", q, np.cross(m.a[fl], m.d[fl])))
    assert side.max() < 5 * MM + 1e-6                          # every floor face within the bit's radius of its line
    walls = m.cut & (np.abs(m.nrm[:, 2]) < 0.01)
    assert set(m.kind[walls]) <= {TM.FLANK, TM.RINGS_WALL} and np.any(m.kind[walls] == TM.FLANK)
    text = machining.marks_source(sc)
    assert text.startswith("No program: ") and "mm per tooth)" in text
    # half way: the attributes are written for that frame's triangles too, and going back gives the same ones
    sc.frame_set(51)
    half = Milled(sc, "STOCK 200x200x40")
    assert len(half.attr) == 4 and half.n_faces != m.n_faces
    sc.frame_set(frames)
    again = Milled(sc, "STOCK 200x200x40")
    assert again.n_faces == m.n_faces and all(np.array_equal(again.attr[k], m.attr[k]) for k in TM.ATTRS)
    # the block's material sets the typical feed: aluminium 0.05 mm per tooth
    wp = m.ob
    from fresing_render.blender import build
    g = sc.fresing.groups.get(wp.get(build.PROP_GROUP, ""))
    if g is not None:
        g.material = "aluminium_machined"
        assert machining.refresh(sc, force=True)
        alu = Milled(sc, "STOCK 200x200x40")
        fl = alu.cut & (alu.nrm[:, 2] > 0.999)
        assert np.allclose(alu.p[fl, 2], 0.05 * MM, rtol=1e-5)
        assert machining.marks_source(sc) == "No program: typical feed for aluminium (0.05 mm per tooth)"


def core_typical(sc):
    from fresing_render.blender import machining
    return M.typical_feed(machining.block_look(sc, machining.workpiece(sc))[0])


def test_write_mesh_marks_and_normals(blender):
    bpy = blender
    from fresing_render.blender import machining
    me = bpy.data.meshes.new("t")
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 0, -1]], np.float32)
    t = np.array([[0, 1, 2], [1, 3, 2]], np.int32)
    mat = np.zeros(2, np.int32)
    machining._write_mesh(me, v, t, mat)                                     # as before: no attributes
    assert not [a.name for a in me.attributes if a.name.startswith("fr_mk") or a.name == "custom_normal"]
    marks = tuple(np.arange(6, dtype=np.float32).reshape(2, 3) + 10 * k for k in range(4))
    normals = np.tile(np.array([[0.0, 0.6, 0.8]], np.float32), (6, 1))
    normals[3:] = (0.6, 0.0, 0.8)
    for _again in range(2):                                                  # (written over the last frame's)
        machining._write_mesh(me, v, t, mat, marks=marks, normals=normals)
        for name, want in zip(TM.ATTRS, marks):
            a = me.attributes[name]
            got = np.empty(6, np.float32)
            a.data.foreach_get("vector", got)
            assert a.domain == "FACE" and np.array_equal(got.reshape(2, 3), want)
        got = np.empty(18, np.float32)
        me.corner_normals.foreach_get("vector", got)
        assert np.allclose(got.reshape(6, 3), normals, atol=1e-6)            # used as they are
    machining._write_mesh(me, v, t, mat, marks=marks)                        # marks only: smooth by angle again
    assert "custom_normal" not in me.attributes and TM.ATTR_P in me.attributes
    got = np.empty(18, np.float32)
    me.corner_normals.foreach_get("vector", got)
    assert np.allclose(got.reshape(6, 3)[:3], (0, 0, 1), atol=1e-6)          # a 90° edge stays sharp


ONE_FEED = """%
G21 G90 G17 G54
S12000 M3
G0 X-50 Y0 Z5
G1 Z-2 F800
G1 X50
G0 Z10
M5
M30
%
"""

FOUR_TOOLS = """%
(FOUR TOOLS)
G21 G90 G17 G54
T1 M6
S3000 M3
G0 X-180 Y-60 Z5
G1 Z-1 F3000
G1 X180
G0 Z10
T2 M6
S8000 M3
G0 X-50 Y20 Z5
G1 Z-3 F600
G1 X50
G0 Z10
T3 M6
G0 X60 Y60 Z5
G1 Z-10 F200
G0 Z10
T4 M6
G0 X-60 Y60 Z5
G1 Z-2 F200
G0 Z10
M5
M30
%
"""
G_STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"


def _gantry(bpy, tmp_path):
    from fresing_render.blender import gcode
    sc = _scene(bpy, tmp_path, GANTRY, (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)),
                                        ("Z", "Z.ASM", (0, 0, 1))))
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    _click(bpy, _ob(sc, T1))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    _click(bpy, _ob(sc, G_STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    assert gcode.problem(sc) == ""
    _click(bpy, _ob(sc, T1))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    _click(bpy, _ob(sc, G_STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    return sc


def _step(sc, path, **kw):
    a = sc.fresing.animations.get("Program") or sc.fresing.animations.add()
    a.name, a.tail = "Program", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    for k, v in kw.items():
        setattr(b, k, v)
    b.gcode_file = path
    return a, b


def test_feed_and_speed_come_from_the_program(blender, tmp_path):
    bpy = blender
    from fresing_render.blender import animation, gcode, machining
    sc = _gantry(bpy, tmp_path)
    assert gcode.feeds(sc) == [] and machining.marks_source(sc).startswith("No program: ")
    p = tmp_path / "one.ngc"
    p.write_text(ONE_FEED)
    a, _b = _step(sc, str(p))
    assert machining.marks_source(sc).startswith("Build the animation to use the program's feed. Until then: ")
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    rows = gcode.feeds(sc)
    assert [(f, s) for _fr, f, s in rows] == [(800.0, 12000.0), (0.0, 0.0)]
    assert 1.0 < rows[0][0] < rows[1][0] <= sc.frame_end + 1
    machining.sample(sc)
    sc.frame_set(sc.frame_end)
    assert machining.refresh(sc, force=True)
    assert machining.marks_source(sc) == "Marks from the program: F800 S12000, 3 flutes"
    m = Milled(sc, G_STOCK)
    fl = m.flat(28.0)
    assert fl.any() and set(m.kind[fl]) == {TM.ARCS}
    assert np.allclose(m.p[fl, 2], 800 / 12000 / 3 * MM, rtol=1e-5)          # feed per tooth, 3 flutes
    assert np.allclose(m.p[fl, 1], 3 * MM, atol=1e-6)
    # the frame the cutting starts on: the plunge's
    tl = machining.runtime(sc)["timeline"]
    first_cut = float(tl.moves.t0[tl.moves.cuts][0])
    assert rows[0][0] <= first_cut + 1.0
    # scrubbing does not pile up ids without end, and a move's feed is its own
    for f in list(range(1, sc.frame_end + 1, 2)) * 2:
        sc.frame_set(f)
    assert len(tl.cut_ids) <= M.Timeline.IDS_MAX + len(tl.segs) + 1
    assert len(tl.cut_ids) < 4 * sc.frame_end
    # 'Clear keys' forgets the feeds
    gcode.after_clear(sc)
    assert gcode.feeds(sc) == []


def test_four_tools_each_leave_their_own_marks(blender, tmp_path):
    bpy = blender
    from fresing_render.blender import animation, gcode, machining, tools
    sc = _gantry(bpy, tmp_path)
    sc.fresing.milling.detail = "FINE"
    for n, kind, sizes in ((1, "FACE", dict(diameter=50 * MM, lead_angle=math.radians(90), insert_size=12 * MM,
                                            inserts=5)),
                           (2, "FLAT", dict(diameter=8 * MM, flutes=2)), (3, "DRILL", dict(diameter=6 * MM)),
                           (4, "VEE", dict(diameter=10 * MM, angle=math.radians(90)))):
        row = tools.add_row(sc, kind, n)
        for k, v in sizes.items():
            setattr(row, k, v)
    p = tmp_path / "four.ngc"
    p.write_text(FOUR_TOOLS)
    a, _b = _step(sc, str(p), gcode_tc_time=1.0, gcode_speed="FASTER", gcode_factor=4.0)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    assert [(f, s) for _fr, f, s in gcode.feeds(sc)] == [(3000.0, 3000.0), (600.0, 8000.0), (200.0, 8000.0),
                                                         (0.0, 0.0)]
    machining.sample(sc)
    items = machining.cut_items(sc)
    assert [(c.flutes, c.face, c.program) for c in items[1:]] == [(5, True, True), (2, False, True),
                                                                  (2, False, True), (2, False, True)]
    sc.frame_set(sc.frame_end)
    assert machining.refresh(sc, force=True)
    assert machining.marks_source(sc) == "Marks from the program's feeds and speeds"
    m = Milled(sc, G_STOCK)
    top = 30.0
    # face mill Ø50 along X at y -60, 1 deep: arcs of its radius, one per turn (3000 mm/min at 3000 rpm = 1 mm)
    fl = m.flat(top - 1, y=-60, tol=25)
    assert fl.any() and set(m.kind[fl]) == {TM.ARCS}
    assert np.allclose(m.p[fl, 1], 25 * MM, atol=1e-6) and np.allclose(m.p[fl, 2], 1.0 * MM, rtol=1e-5)
    # end mill Ø8, 2 flutes, at y 20, 3 deep: 600 / 8000 / 2 = 0.0375 mm per tooth
    fl = m.flat(top - 3, y=20, tol=4)
    assert fl.any() and set(m.kind[fl]) == {TM.ARCS}
    assert np.allclose(m.p[fl, 1], 4 * MM, atol=1e-6) and np.allclose(m.p[fl, 2], 0.0375 * MM, rtol=1e-5)
    # drill Ø6 at (60, 60): rings on the point, rings on the wall one per turn (200 / 8000 = 0.025 mm)
    w = m.c @ m.world[:3, :3].T + m.world[:3, 3]
    hole = m.cut & (np.hypot(w[:, 0] / MM - 60, w[:, 1] / MM - 60) < 3.2)
    assert set(m.kind[hole]) == {TM.RINGS, TM.RINGS_WALL}
    wall = hole & (np.abs(m.nrm @ m.world[2, :3]) < 0.01)
    assert wall.any() and np.allclose(m.p[wall, 2], 0.025 * MM, rtol=1e-5)
    assert np.allclose(m.d[hole], 0.0)
    # chamfer mill at (-60, 60), straight down: rings
    vee = m.cut & (np.hypot(w[:, 0] / MM + 60, w[:, 1] / MM - 60) < 2.2)
    assert vee.any() and set(m.kind[vee]) == {TM.RINGS}
    # before T2 cut: the faced strip has its marks, the slot is not there
    f_t2 = next(f for f, n in gcode.schedule(sc) if n == 2)
    sc.frame_set(int(f_t2))
    early = Milled(sc, G_STOCK)
    assert early.flat(top - 1, y=-60, tol=25).any() and not early.flat(top - 3).any()
