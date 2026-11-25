"""Long cables and hoses meshed by their own rule (task 0325, ``importer/tube_mesh.py``).

The Stress model's cables (circles swept along long B-splines, flat caps) came to 30,000–190,000 triangles each at
Normal; now segments round by the diameter and rings only where the cable bends. The mesh stays closed, faces out and
lies on the CAD surface; everything that is not such a cable meshes exactly as before."""

import math
import os

import numpy as np
import pytest

pytest.importorskip("OCP")

from fresing_render.importer import step_reader, tube_mesh  # noqa: E402
from fresing_render.pccheck import stress_scene  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")


def _clean(shape):
    from OCP.BRepTools import BRepTools
    BRepTools.Clean_s(shape)                              # OpenCascade keeps a mesh that is fine enough
    return shape


def _mesh(shape, quality="normal", facets=True):
    occ = step_reader._occ()
    lin, ang = step_reader.QUALITY[quality]
    f = dict(step_reader.FACETS[quality])
    if not facets:
        f.pop("tube_gap")
    starts: list = []
    pos, nrm, tri, _c, _p = step_reader._mesh_shape(occ, _clean(shape), lin, ang, facets=f, face_starts=starts)
    return np.asarray(pos, np.float64) * 1000.0, np.asarray(nrm, np.float64), np.asarray(tri), starts


def _cable(length=30000.0, c=0, r=14.0):
    return stress_scene.Maker(stress_scene.FULL).cable(length, 600.0, c, r, False)


def _closed(pos, tri) -> bool:
    """Every edge shared by exactly two triangles (points welded by place): no crack, no hole."""
    key, inv = np.unique(np.round(pos, 6), axis=0, return_inverse=True)
    t = inv.ravel()[tri]
    e = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _u, cnt = np.unique(e, axis=0, return_counts=True)
    return bool((cnt == 2).all())


def _volume(pos, tri) -> float:
    v0, v1, v2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def _cad_volume(shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def _normals_agree(pos, nrm, tri) -> float:
    v0, v1, v2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    return float((np.einsum("ij,ij->i", fn, nrm[tri].mean(axis=1)) > 0).mean())


def _surface_gap(shape, pts) -> float:
    """Largest distance of the points from the shape's faces (not its inside), mm."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    shell = TopExp_Explorer(shape, TopAbs_SHELL).Current()
    worst = 0.0
    for p in pts:
        d = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, p))).Vertex(), shell)
        worst = max(worst, d.Value())
    return worst


# --- the numbers ---------------------------------------------------------------------------------------------------

def test_segments_by_the_diameter():
    gaps = [step_reader.FACETS[q]["tube_gap"] for q in ("draft", "normal", "fine")]
    assert [tube_mesh.segments(10.0, g) for g in gaps] == [10, 16, 25]        # Ø20 mm: about 12–16 at Normal
    assert tube_mesh.segments(1.0, 0.2) == tube_mesh.MIN_SEG                   # a thin wire: still round
    assert tube_mesh.segments(500.0, 0.08) == tube_mesh.MAX_SEG
    for r in (3.0, 14.0, 32.0, 80.0):                                         # the sag stays under the gap
        n = tube_mesh.segments(r, 0.2)
        if tube_mesh.MIN_SEG < n < tube_mesh.MAX_SEG:
            assert r * (1 - math.cos(math.pi / n)) <= 0.2


def test_rings_only_where_it_bends():
    t = np.linspace(0, 1, 401)
    round_ = np.stack([np.cos(a) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)])
    straight = np.zeros((401, 8, 3))
    straight[:, :, 0] = t[:, None] * 10000.0
    straight[:, :, 1] = 10 * round_[None, :]
    assert tube_mesh.rings(straight, 0.2) == [0, 400]
    # a quarter bend of radius 500 mm: the sag between kept rows stays within the gap, and it needs a few dozen
    a = t * math.pi / 2
    bent = np.zeros((401, 8, 3))
    rr = 500.0 + 10 * round_[None, :]
    bent[:, :, 0] = rr * np.cos(a)[:, None]
    bent[:, :, 1] = rr * np.sin(a)[:, None]
    keep = tube_mesh.rings(bent, 0.2)
    assert 15 <= len(keep) <= 60, len(keep)
    step = max(np.diff(a[keep]))
    assert 510.0 * (1 - math.cos(step / 2)) <= 0.2 + 1e-9


# --- the Stress cable ------------------------------------------------------------------------------------------------

def test_a_30_m_stress_cable_is_light_closed_and_on_its_surface():
    shape = _cable()
    plan = tube_mesh.plan(shape, step_reader.FACETS["normal"]["tube_gap"])
    assert plan is not None and len(plan) == 3                               # the tube and its two caps
    pos, nrm, tri, starts = _mesh(shape)
    assert len(tri) <= 15000, len(tri)                                        # was about 54,000 (Ø28, 15 m + drop)
    assert len(starts) == 4 and starts[-1] == len(tri)                        # every CAD face still picks as one
    assert _closed(pos, tri)
    assert _normals_agree(pos, nrm, tri) == 1.0
    assert 0.97 < _volume(pos, tri) / _cad_volume(shape) < 1.0               # inside the true round, close to it
    # every point lies on the CAD surface, and the middles of the long edges stay within the gap round plus the gap
    # along (the sag of a segment round and of a run between rings can add up)
    rng = np.random.default_rng(1)
    assert _surface_gap(shape, pos[rng.choice(len(pos), 60, replace=False)]) < 0.01
    v0, v1 = pos[tri[:, 0]], pos[tri[:, 1]]
    long_ = np.argsort(-np.linalg.norm(v1 - v0, axis=1))[:40]
    gap = step_reader.FACETS["normal"]["tube_gap"]
    assert _surface_gap(shape, (v0[long_] + v1[long_]) / 2.0) <= 2 * gap + 0.02


def test_a_cable_stored_inside_out_stays_as_the_cad_has_it():
    """Normals and triangles follow the faces' own orientation, as OpenCascade's mesh does: the same cable reversed
    comes out reversed (the reader never turns a face round itself)."""
    shape = _cable(length=6000.0)
    pos, nrm, tri, _s = _mesh(shape)
    rpos, rnrm, rtri, _s = _mesh(shape.Reversed())
    assert _volume(pos, tri) > 0 > _volume(rpos, rtri)
    assert _normals_agree(rpos, rnrm, rtri) == 1.0
    np.testing.assert_allclose(rnrm, -nrm, atol=1e-6)


@pytest.mark.parametrize("c, r", [(0, 14.0), (1, 20.0), (2, 26.0), (3, 32.0)])
def test_every_stress_cable_kind_is_much_lighter_and_details_keep_their_order(c, r):
    shape = _cable(c=c, r=r)
    counts = [len(_mesh(shape, q)[2]) for q in ("draft", "normal", "fine")]
    old = len(_mesh(shape, "normal", facets=False)[2])                      # OpenCascade's mesh, as before 0325
    assert counts[0] < counts[1] < counts[2], counts
    assert counts[1] <= 15000 and counts[1] * 3 < old, (counts, old)          # 31,000–186,000 before


def test_a_cable_of_two_faces_in_a_row_shares_its_ring():
    """A sweep along two B-spline pieces: two tube faces meeting at a ring. The second face's end row takes the
    first face's very points (their seams need not line up): the mesh stays closed."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.collections import Array1_gp_Pnt
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    def spline(pts):
        arr = Array1_gp_Pnt(1, len(pts))
        for i, p in enumerate(pts):
            arr.SetValue(i + 1, gp_Pnt(*p))
        return GeomAPI_PointsToBSpline(arr, 3, 3).Curve()
    a = spline([(0, 0, 0), (1000, 40, 0), (2000, 0, 0), (3000, 0, 0)])
    b = spline([(3000, 0, 0), (3600, 0, -300), (3900, 0, -900), (4000, 0, -1600)])
    wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(a).Edge(), BRepBuilderAPI_MakeEdge(b).Edge()).Wire()
    t0 = a.DN(a.FirstParameter(), 1)
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(t0)), 12.0)).Edge()
                                   ).Wire()
    ps = BRepOffsetAPI_MakePipeShell(wire)
    ps.SetMode(False)
    ps.Add(prof)
    ps.Build()
    ps.MakeSolid()
    shape = ps.Shape()
    plan = tube_mesh.plan(shape, 0.2)
    assert plan is not None and len(plan) == 4, None if plan is None else len(plan)   # two tubes, two caps
    pos, nrm, tri, _s = _mesh(shape)
    assert _closed(pos, tri)
    assert _normals_agree(pos, nrm, tri) == 1.0
    assert len(tri) < len(_mesh(shape, facets=False)[2])


# --- what stays as it was ----------------------------------------------------------------------------------------------

def _not_a_cable(shape):
    assert tube_mesh.plan(shape, 0.2) is None
    with_rule, without = _mesh(shape), _mesh(shape, facets=False)
    assert len(with_rule[2]) == len(without[2])


def test_round_bars_boxes_and_short_tubes_mesh_as_before():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    _not_a_cable(BRepPrimAPI_MakeBox(100.0, 20.0, 30.0).Shape())
    _not_a_cable(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 10.0, 3000.0).Shape())  # a rod
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.collections import Array1_gp_Pnt
    from OCP.gp import gp_Circ
    arr = Array1_gp_Pnt(1, 4)
    for i, p in enumerate([(0, 0, 0), (100, 10, 0), (200, 0, 0), (300, 0, 20)]):
        arr.SetValue(i + 1, gp_Pnt(*p))
    curve = GeomAPI_PointsToBSpline(arr, 3, 3).Curve()
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(
        curve.DN(curve.FirstParameter(), 1))), 10.0)).Edge()).Wire()
    ps = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire())
    ps.Add(prof)
    ps.Build()
    ps.MakeSolid()
    _not_a_cable(ps.Shape())                     # 300 mm long, Ø20: 15 diameters – meshed as before


def test_a_hollow_hose_and_a_square_duct_mesh_as_before():
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.collections import Array1_gp_Pnt
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    pts = [(0, 0, 0), (1500, 50, 0), (3000, 0, 0), (3500, 0, -500)]
    arr = Array1_gp_Pnt(1, len(pts))
    for i, p in enumerate(pts):
        arr.SetValue(i + 1, gp_Pnt(*p))
    curve = GeomAPI_PointsToBSpline(arr, 3, 3).Curve()
    t0 = gp_Dir(curve.DN(curve.FirstParameter(), 1))

    def sweep(profile):
        ps = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire())
        ps.SetMode(False)
        ps.Add(profile)
        ps.Build()
        ps.MakeSolid()
        return ps.Shape()

    def circle(r):
        return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), t0), r)).Edge()).Wire()
    assert tube_mesh.plan(sweep(circle(15.0)), 0.2) is not None             # the solid hose is one …
    _not_a_cable(BRepAlgoAPI_Cut(sweep(circle(15.0)), sweep(circle(11.0))).Shape())   # … the hollow one is not
    ax = gp_Ax2(gp_Pnt(0, 0, 0), t0)
    x, y = ax.XDirection(), ax.YDirection()
    sq = BRepBuilderAPI_MakePolygon()
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        sq.Add(gp_Pnt(15 * (sx * x.X() + sy * y.X()), 15 * (sx * x.Y() + sy * y.Y()), 15 * (sx * x.Z() + sy * y.Z())))
    sq.Close()
    _not_a_cable(sweep(sq.Wire()))                                            # a square duct: flat faces


@pytest.mark.parametrize("name", ["test_flex_hoses_a", "test_paths_a", "test_spool", "test_flex_avoid_a", "test_sea",
                                  "test_crane_a"])
def test_the_test_models_hoses_cables_and_ropes_are_not_touched(name):
    """Their hoses and ropes are swept along lines and arcs (cylinders and tori: light already); no part of these
    models is meshed by the new rule, so their triangle counts stay as they were."""
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    rd = STEPControl_Reader()
    rd.ReadFile(os.path.join(DATA, name + ".step"))
    rd.TransferRoots()
    exp = TopExp_Explorer(rd.OneShape(), TopAbs_SOLID)
    n = 0
    while exp.More():
        assert tube_mesh.plan(exp.Current(), 0.2) is None
        exp.Next()
        n += 1
    assert n


def test_a_cable_cut_off_at_a_slant_meshes_as_before():
    """Its end is no ring straight across the tube (the cap's edge is not one row of the grid): OpenCascade meshes it."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    cable = _cable(length=3000.0)
    assert tube_mesh.plan(cable, 0.2) is not None
    knife = BRepPrimAPI_MakeBox(gp_Pnt(-500, -500, -500), 500.0, 1500.0, 1000.0).Shape()
    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(30))
    knife = BRepBuilderAPI_Transform(knife, turn, True).Shape()
    move = gp_Trsf()
    from OCP.gp import gp_Vec
    move.SetTranslation(gp_Vec(100.0, 0.0, 0.0))
    knife = BRepBuilderAPI_Transform(knife, move, True).Shape()
    _not_a_cable(BRepAlgoAPI_Cut(cable, knife).Shape())
