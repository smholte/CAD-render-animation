"""Facets by size (task 0074): big round parts capped in mm, small standard parts lighter, the rest as before."""

import math
import os

import numpy as np
import pytest

pytest.importorskip("OCP")

from fresing_render.importer import runner, step_reader  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")


def _cyl(r, h, x=0.0, y=0.0, z=0.0):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()


def _cut(a, *tools):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    for t in tools:
        a = BRepAlgoAPI_Cut(a, t).Shape()
    return a


def _mesh(shape, quality, standard=False, facets=True):
    from OCP.BRepTools import BRepTools
    BRepTools.Clean_s(shape)                              # OpenCascade keeps a mesh that is fine enough
    occ = step_reader._occ()
    lin, ang = step_reader.QUALITY[quality]
    pos, _n, tri, _c, _p = step_reader._mesh_shape(occ, shape, lin, ang, standard=standard,
                                                   facets=step_reader.FACETS[quality] if facets else None)
    return np.asarray(pos).reshape(-1, 3) * 1000.0, np.asarray(tri).reshape(-1, 3)


def _circle(pos, cx, cy, r):
    """(segments, biggest gap between facet and circle in mm) of the mesh points on that circle."""
    on = np.abs(np.hypot(pos[:, 0] - cx, pos[:, 1] - cy) - r) < 0.01
    a = np.unique(np.round(np.arctan2(pos[on, 1] - cy, pos[on, 0] - cx), 7))
    a.sort()
    steps = np.diff(np.concatenate([a, [a[0] + 2 * math.pi]]))
    return len(a), r * (1 - math.cos(steps.max() / 2))


@pytest.mark.parametrize("quality", ["draft", "normal", "fine"])
def test_big_ring_and_drum_stay_under_the_cap(quality):
    cap = step_reader.FACETS[quality]["cap_mm"]
    ring = _cut(_cyl(5000, 300), _cyl(4700, 400, z=-50), _cyl(22.5, 400, 4850, 0, -50))
    drum = _cut(_cyl(1000, 3000), _cyl(950, 3100, z=-50))
    pos, _t = _mesh(ring, quality)
    segs, gap = _circle(pos, 0, 0, 5000)
    assert gap <= cap, (quality, segs, gap)
    hole_segs, hole_gap = _circle(pos, 4850, 0, 22.5)
    assert hole_segs >= 20 and hole_gap <= cap            # its bolt holes keep their segments
    pos, _t = _mesh(drum, quality)
    assert _circle(pos, 0, 0, 1000)[1] <= cap
    # before task 0074 the Ø10 m ring had 3.7 mm flat spots at Normal
    old, _t = _mesh(ring, quality, facets=False)
    assert _circle(old, 0, 0, 5000)[1] > cap


def test_small_standard_parts_get_fewer_segments():
    bolt = _cyl(5.0, 30.0)                                # an M10 x 30 shank
    for quality, lo, hi in (("draft", 10, 16), ("normal", 16, 24), ("fine", 28, 40)):
        pos, tri = _mesh(bolt, quality, standard=True)
        segs, _gap = _circle(pos, 0, 0, 5.0)
        assert lo <= segs <= hi, (quality, segs)
        old_pos, old_tri = _mesh(bolt, quality, standard=True, facets=False)
        assert len(tri) < len(old_tri)
    pos, _t = _mesh(_cyl(10.0, 60.0), "normal", standard=True)   # M20: still at least 16
    assert _circle(pos, 0, 0, 10.0)[0] >= 16


def test_other_small_parts_and_middle_parts_are_meshed_as_before():
    for shape, standard in ((_cyl(5.0, 30.0), False), (_cyl(30.0, 250.0), True), (_cyl(100.0, 300.0), False)):
        new = _mesh(shape, "normal", standard=standard)[1]
        old = _mesh(shape, "normal", standard=standard, facets=False)[1]
        assert len(new) == len(old)


def test_mesh_params_rules():
    f = step_reader.FACETS["normal"]
    lin, ang = step_reader.QUALITY["normal"]
    assert step_reader.mesh_params(lin, ang, 500.0, f) == (lin, True, ang)
    assert step_reader.mesh_params(lin, ang, 10000.0, f) == (f["cap_mm"], False, ang)
    assert step_reader.mesh_params(lin, ang, 40.0, f) == (lin, True, ang)              # not a standard part
    assert step_reader.mesh_params(lin, ang, 40.0, f, standard=True) == (f["small_gap"], False, f["small_ang"])
    assert step_reader.mesh_params(lin, ang, 400.0, f, standard=True) == (lin, True, ang)   # a long anchor bolt
    assert step_reader.mesh_params(lin, ang, 10000.0, None) == (lin, True, ang)
    assert step_reader.is_standard_part("ISO 4017 M12 x 40 - 8.8 HDG")
    assert step_reader.is_standard_part("DIN 912 M10x30 - 12.9")
    assert not step_reader.is_standard_part("END MILL D10 ALONG")
    assert not step_reader.is_standard_part("SIGNAL.LAMP")


def test_import_uses_facets_and_old_caches_are_not_reused(tmp_path):
    info = step_reader.read_step(os.path.join(DATA, "test_machine.step"), str(tmp_path / "new"), "normal")
    tris = {m["name"]: m["tris"] for m in info["meshes"]}
    assert tris["ISO 4017 M12 x 40 - 8.8 HDG"] < 120                  # was 176 (20 instead of 42 segments)
    assert tris["SIGNAL.LAMP"] > 5000                                   # not a standard part: as before
    assert step_reader.CACHE_VERSION == 6
    assert runner.cache_is_valid(str(tmp_path / "new"))
    head = tmp_path / "new" / "tree.json"                              # a cache meshed before task 0074
    head.write_text(head.read_text(encoding="utf-8").replace('"version": 6', '"version": 5', 1), encoding="utf-8")
    assert not runner.cache_is_valid(str(tmp_path / "new"))            # is meshed again, never reused


def test_painted_faces_survive_a_model_update_meshed_finer(tmp_path):
    """A part meshed with other settings (another Detail, or after task 0074) keeps its painted faces: the model
    update compares the CAD faces' areas and centres, not their triangle counts. A changed part still loses them."""
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    from fresing_render.blender import build, faces, logic
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    try:
        sc = bpy.context.scene
        sc.fresing.out_folder = str(tmp_path)
        faces_b = os.path.join(DATA, "test_faces_b.step")
        assert bpy.ops.fresing.import_step(filepath=faces_b, quality="draft") == {"FINISHED"}

        def block():
            return next(o for o in build.iter_parts(sc) if o[build.PROP_NAME] == "BLOCK")

        draft_tris = len(block().data.polygons)
        logic.ensure_group(sc.fresing, "Red paint")
        faces.paint(block(), [1], "Red paint")
        root = build.model_roots(sc)[0]
        assert bpy.ops.fresing.import_step(filepath=faces_b, quality="fine", update_root=root.name) == {"FINISHED"}
        assert len(block().data.polygons) > draft_tris          # meshed finer: other triangle counts
        assert "Red paint" in faces.groups_on(block())
        assert not any(n.text.startswith("BLOCK:") for n in sc.fresing.report_notes)
        # the same number of faces, but one moved: not the same part
        draft, fine = _ring_mesh(build, 1385.0, "draft"), _ring_mesh(build, 1385.0, "fine")
        assert faces.layout(draft) != faces.layout(fine) and faces.same_faces(draft, fine)
        assert not faces.same_faces(draft, _ring_mesh(build, 1250.0, "fine"))       # its hole moved 135 mm
    finally:
        fresing_render.unregister()


def _ring_mesh(build, hole_x, quality):
    ring = _cut(_cyl(1500, 300), _cyl(1200, 400, z=-50), _cyl(22.5, 400, hole_x, 0, -50))
    occ = step_reader._occ()
    starts: list = []
    from OCP.BRepTools import BRepTools
    BRepTools.Clean_s(ring)
    pos, nrm, tri, _c, _p = step_reader._mesh_shape(occ, ring, *step_reader.QUALITY[quality], face_starts=starts)
    me = build._new_mesh("ring", pos, nrm, tri)
    from fresing_render.blender import faces
    me[faces.PROP_STARTS] = starts
    return me
