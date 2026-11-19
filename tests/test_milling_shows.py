"""Task 0223: the milled block shows what the program does – every cut face carries tool marks (both routes: the
booleans and the height map of Fast 3-axis), every move through the block takes material away, and a program that
runs through a workpiece Milling does not cut is found. The tour's machining stops check all of it
(``tour.check_milling``); here the pieces, each with a broken copy that the check must catch.

Stated tolerance: cut faces without marks at most 1 % of the cut area (``machining.BARE_SHARE``, slivers); a tool tip
0.3 mm up its axis must lie outside the material after the move (the height map is at most 0.2 mm off at sharp
outside corners, the probe cube is 0.1 mm)."""

import os

import numpy as np
import pytest

mf = pytest.importorskip("manifold3d")

from fresing_render.core import machining as M  # noqa: E402

MM = 0.001
UP = np.array([0.0, 0.0, 1.0])
FLAT6 = M.Tool("FLAT", radius=3 * MM, length=0.03)


def block():
    return mf.Manifold.cube((0.06, 0.04, 0.02)).translate((0.0, 0.0, -0.02))


def zigzag_pocket(passes=12, per=30, depth=-0.003):
    """A pocket by a flat Ø6: in from above, passes 2 mm apart, each in ``per`` short moves, out again."""
    pts = [(0.008, 0.008, 0.002)]
    for k in range(passes):
        xs = np.linspace(0.008, 0.050, per + 1)
        ys = 0.008 + k * 0.002 + 0.00004 * (np.arange(per + 1) % 2)
        if k % 2:
            xs = xs[::-1]
        pts += [(x, y, depth) for x, y in zip(xs, ys)]
    pts.append((pts[-1][0], pts[-1][1], 0.002))
    return np.array(pts)


def timeline(pts, fast=False):
    path = M.Path(np.arange(len(pts)) + 1.0, np.asarray(pts, float), np.tile(UP, (len(pts), 1)))
    return M.Timeline(M.Workpiece(block(), None, "NORMAL"), [M.Cutter(FLAT6, "NORMAL")], [path], "NORMAL", fast=fast)


@pytest.fixture()
def any_density(monkeypatch):
    """(the small test program is spread thinner than a real finishing program)"""
    monkeypatch.setattr(M, "FAST_MIN_DENSITY", 0.0)


# ---------------------------------------------------------------------------
# marks on every cut face
# ---------------------------------------------------------------------------

def test_every_cut_face_has_marks_on_both_routes(any_density):
    pts = zigzag_pocket()
    T = float(len(pts))
    got = {}
    for fast in (False, True):
        tl = timeline(pts, fast)
        assert (tl.map is not None) == fast
        cut, bare = tl.cut_cover(T)
        assert cut > 0.0
        assert bare <= 0.01 * cut, (fast, cut, bare)
        got[fast] = cut
    # the same pocket either way: floor 42+6 x 22+6 mm and its walls 3 mm high (within the map's corners)
    assert abs(got[True] - got[False]) < 0.03 * got[False]


def test_seams_inside_the_material_do_not_count():
    """A cut through a block big enough to be split into tiles: the faces that close a tile inside the material have
    no maker and no marks; nobody sees them, so they are not "cut faces without marks"."""
    pts = zigzag_pocket()
    tl = timeline(pts)
    tl.wp.tile_max = 300                             # split often
    cut, bare = tl.cut_cover(float(len(pts)))
    assert tl.stats.tiles > 1
    assert cut > 0.0 and bare <= 0.01 * cut


def test_a_cut_face_that_lost_its_maker_is_found():
    """The broken copy: the faces still show the cut, but which move made them is forgotten (the marks read zeros):
    the check must name them."""
    pts = zigzag_pocket()
    T = float(len(pts))
    tl = timeline(pts)
    cut, bare = tl.cut_cover(T)
    assert bare <= 0.01 * cut
    tl.cut_ids.clear()                                # every cut face's maker forgotten
    tl.mesh_cache = {}
    cut2, bare2 = tl.cut_cover(T)
    assert abs(cut2 - cut) < 1e-12 and bare2 > 0.9 * cut2


# ---------------------------------------------------------------------------
# every move through the block cuts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fast", [False, True])
def test_every_move_through_the_block_cut(any_density, fast):
    pts = zigzag_pocket()
    tl = timeline(pts, fast)
    left, n, when = tl.left_in_stock()
    assert n > 500 and left == [] and when == []


def test_a_move_that_did_not_cut_is_found():
    """The broken copy: four passes of the pocket are not cut (as moves the timeline took for ones that miss the
    block, or a frame range the cut stops at). The passes beside them take away up to 3 mm on either side, so the
    tips of the middle two (y 18 and 20 mm) stay in the material, and their frames are named."""
    pts = zigzag_pocket()
    tl = timeline(pts)
    skipped = [s for s in tl.segs if 126 <= s.t0 < 249]          # passes 5 to 8 (31 points each)
    assert skipped
    for s in skipped:
        s.cuts = False
    left, n, when = tl.left_in_stock()
    assert left, "passes that were not cut went unnoticed"
    assert all(126.0 <= w <= 250.0 for w in when), when
    y = np.array([p[1] for p in left])
    z = np.array([p[2] for p in left])
    assert np.all((y > 0.0168) & (y < 0.0212)), y         # (and the step-overs between them)
    assert np.allclose(z, -0.0027, atol=1e-4)


def test_the_finished_part_stops_the_cut_on_purpose():
    """Finish at the CAD part: the bit goes into it, the cut stops at it – not a missed cut."""
    pts = zigzag_pocket(depth=-0.004)
    part = mf.Manifold.cube((0.06, 0.04, 0.018)).translate((0.0, 0.0, -0.02))     # its top 2 mm under the block's
    path = M.Path(np.arange(len(pts)) + 1.0, pts, np.tile(UP, (len(pts), 1)))
    tl = M.Timeline(M.Workpiece(block(), part, "NORMAL"), [M.Cutter(FLAT6, "NORMAL")], [path], "NORMAL")
    left, n, _when = tl.left_in_stock()
    assert n > 500 and left == []


def test_points_inside():
    box = mf.Manifold.cube((0.01, 0.01, 0.01))
    got = M.points_inside(box, np.array([[0.005, 0.005, 0.005], [0.02, 0.0, 0.0], [0.005, 0.005, 0.0099]]))
    assert len(got) == 2
    assert M.points_inside(box, np.zeros((0, 3))) == []


# ---------------------------------------------------------------------------
# in Blender: the audit, Use the CNC tool and workpiece, a painted block, the tour's check
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gantry(tmp_path_factory):
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    from fresing_render.blender import tour
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("tour") / "Test tour")
    out = tour.build_all(folder, "9.9.9", only=("gantry", "marks"))
    assert out["errors"] == {}
    yield bpy, folder
    fresing_render.unregister()


def test_a_program_through_an_uncut_block_is_found(gantry):
    """The cause found in the tour (task 0223): the gantry, double-arm and operator sets ran their programs through
    a block that Milling did not cut - the path went through uncut material and no check said so."""
    bpy, folder = gantry
    from fresing_render.blender import animation, machining, tour
    tour.open_set(folder, "9.9.9", "gantry")
    sc = bpy.context.scene
    a = sc.fresing.animations["G-code"]
    assert tour.check_milling(sc)                      # as built: cut, with marks
    machining.stop(sc)                                 # the broken copy: Milling not set up
    assert machining.cnc_unused(sc)                    # the CNC and Milling panels offer the button
    animation.bake(sc, a)
    au = machining.audit(sc)
    assert not au["set_up"] and au["through"] > 100
    with pytest.raises(RuntimeError, match="Milling is not set up"):
        tour.check_milling(sc)
    # one click: the CNC machine's tool and workpiece
    assert bpy.ops.fresing.mill_from_cnc() == {"FINISHED"}
    assert not machining.cnc_unused(sc)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    au = machining.audit(sc)
    assert machining.audit_problems(au) == [], au
    assert au["cut_mm2"] > 500 and au["bare_mm2"] <= 0.01 * au["cut_mm2"] and au["left"] == 0
    # Cut material off: set up on purpose not to cut - nothing to report
    machining.settings(sc).enabled = False
    assert not machining.cnc_unused(sc)


def test_a_painted_block_cuts_to_bare_metal(gantry):
    """The other cause (task 0223): ten of the twelve machining sets have a block as imported - grey satin paint -
    and a cut in paint stayed paint with faint marks: plain grey, soft-looking dents. The metal under it shows now."""
    bpy, folder = gantry
    from fresing_render.blender import machining, toolmarks, tour
    from fresing_render.core import machining as mcore
    tour.open_set(folder, "9.9.9", "gantry")
    sc = bpy.context.scene
    wp = machining.workpiece(sc)
    assert machining.block_look(sc, wp)[0] == "paint_satin"
    mat = machining.cut_material(sc, wp)
    assert mat is not None and mat["fr_material"] == "aluminium_machined"
    assert toolmarks.group_node(mat) is not None
    for block in ("", "paint_gloss", "paint_matte", "powder_coat", "paint_marine"):
        assert mcore.cut_look(block)[0] == "aluminium_machined", block
    for block in ("glass_clear", "wood", "rubber_black", "concrete", "emission_light"):
        assert mcore.cut_look(block) is None, block


def test_the_tour_check_catches_lost_marks_and_a_missed_cut(gantry):
    bpy, folder = gantry
    from fresing_render.blender import machining, tour
    tour.open_set(folder, "9.9.9", "marks")
    sc = bpy.context.scene
    st = tour.find("marks")
    assert tour.apply(st, sc) == []
    note = st.check(sc)                                # the stop's own check + check_milling
    assert "all with tool marks" in note and "every move through the block cut" in note
    tl = machining._timeline(sc)
    # a lost look: the cut faces' makers forgotten
    keep = dict(tl.cut_ids)
    tl.cut_ids.clear()
    tl.mesh_cache = {}
    with pytest.raises(RuntimeError, match="have no tool marks"):
        tour.check_milling(sc)
    tl.cut_ids.update(keep)
    tl.mesh_cache = {}
    # a missed cut: the end mill's passes not cut
    late = [s for s in tl.segs if s.cuts and s.bit == 2]
    assert late
    for s in late:
        s.cuts = False
    tl.states = {0: tl.wp.first}
    tl.last = (0, tl.wp.first)
    with pytest.raises(RuntimeError, match="the bit went through material that stays"):
        tour.check_milling(sc)
    for s in late:
        s.cuts = True
    tl.states = {0: tl.wp.first}
    tl.last = (0, tl.wp.first)
    assert tour.check_milling(sc)


def test_every_milling_set_is_named():
    from fresing_render.blender import tour
    sets = {s.set for s in tour.STOPS if s.group == tour.MACH}
    assert sets <= set(tour.MILLING_SETS), sets - set(tour.MILLING_SETS)
    for st in tour.STOPS:
        assert getattr(st.check, "milling", False) == (st.set in tour.MILLING_SETS), st.id
    assert os.path.isfile(tour.SETS["operator"].models[0])
