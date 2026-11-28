"""Task 0349 (Lifting L6b) in the app – Blender as a Python module: the AT-40 with the pump skid hung on its hook.

The clearance row against a wall put next to the boom (a lower bound of the true gap, close to it; the wall named),
what the skid stands on left out, the row along the path; the reach rings, the exclusion zone round the path, the
pads coloured as C5; the plan sheet written and its drawings well formed."""

from __future__ import annotations

import os
import sys
import xml.dom.minidom

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lifting_rigging as T  # noqa: E402

from fresing_render.core import lifting as core  # noqa: E402
from fresing_render.core import lifting_zones as Z  # noqa: E402

registered = T.registered


def _mods():
    from fresing_render.blender import lifting as BL, lifting_path as LP, lifting_rig as RG, lifting_zones as LZ
    return BL, RG, LP, LZ


def _skid_on_at40():
    BL, RG, LP, LZ = _mods()
    sc = T._new()
    c = T._crane(sc)
    ld = T._skid(sc)
    T._above(sc, c, ld, 4.6 - ld.clearance)
    RG.hang(sc, c, ld)
    L = BL.plan(sc)
    L.allowable_kpa, L.mat_size = 250.0, (1.2, 1.2)
    LZ.forget()
    LP.forget()
    return sc, c, ld


def _wall(sc, lo, hi, name="SITE WALL"):
    me = bpy.data.meshes.new(name)
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    bpy.context.view_layer.update()
    return ob


def _box_distance(points, lo, hi) -> float:
    d = np.maximum(0.0, np.maximum(lo - points, points - hi))
    return float(np.min(np.linalg.norm(d, axis=1)))


def _mesh_box_distance(ob, lo, hi, spacing=0.01) -> float:
    """The true gap between a mesh's surface and a box: points spread over its triangles near the box (1 cm apart;
    a long face can pass nearer than any of its corners)."""
    from fresing_render.core import clash
    me = ob.data
    me.calc_loop_triangles()
    M = np.array(ob.matrix_world)
    v = np.array([v.co for v in me.vertices]) @ M[:3, :3].T + M[:3, 3]
    tri = v[np.array([t.vertices for t in me.loop_triangles])]
    near = [t for t in tri if _box_distance(t, lo - 3.0, hi + 3.0) == 0.0]
    if not near:
        return float("inf")
    pts, _w = clash.triangle_points(np.array(near), spacing, max_split=2000)
    return _box_distance(pts, lo, hi)


def _live(sc, LP):
    LP.forget()
    rows = LP.live_rows(sc, force=True)
    assert isinstance(rows, list), rows
    return {r.id: r for r in rows}


def test_clearance_to_a_wall_beside_the_hook_block():
    BL, RG, LP, LZ = _mods()
    sc, c, ld = _skid_on_at40()
    row = _live(sc, LP)["CLR"]
    assert row.status != core.NOT_CHECKED, row.words
    # what the skid stood on when it was hung does not count for it
    cl = LZ.clearance_for(sc, c, ld)
    assert {b.kind for b in cl.bodies} == {"crane", "load", "rigging"}
    hb = next(o for o in c.root.children_recursive if o.type == "MESH" and "HOOK BLOCK" in str(o.get("fr_name", "")))
    pts = np.array([hb.matrix_world @ v.co for v in hb.data.vertices])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    gap = 0.8
    wall = _wall(sc, (hi[0] + gap, lo[1] - 2.0, lo[2] - 1.0), (hi[0] + gap + 0.3, hi[1] + 2.0, hi[2] + 1.0))
    row = _live(sc, LP)["CLR"]
    wlo, whi = np.array([hi[0] + gap, lo[1] - 2.0, lo[2] - 1.0]), np.array([hi[0] + gap + 0.3, hi[1] + 2.0, hi[2] + 1.0])
    # the skid and its slings are near the wall where they are picked: for them it counts once they moved 3.05 m
    truth = min(_mesh_box_distance(o, wlo, whi) for o, k, _j in LZ.moving_objects(sc, c, ld) if k == "crane")
    assert truth <= gap + 1e-6
    got = float(row.value.split()[0])
    assert got <= truth + 0.01 and got > truth - 0.15, (got, truth, row.words)
    assert "SITE WALL" in row.words and row.status == core.RED                     # 0.8 m < 3.05 m needed
    BL.plan(sc).clearance_m = 0.15                    # now the slings (0.25 m away) are not near enough to leave out
    row = _live(sc, LP)["CLR"]
    assert row.status == core.OK and "0.15 m needed" in row.words and "rigging" in row.words, row.words
    bpy.data.objects.remove(wall)
    BL.plan(sc).clearance_m = Z.REQUIRED_DEFAULT


def test_path_rows_zone_rings_footprint_and_the_sheet(tmp_path):
    BL, RG, LP, LZ = _mods()
    sc, c, ld = _skid_on_at40()
    hook = BL.hook_world(sc, c)
    pt = np.array((hook[0] + 3.0, hook[1] - 5.0, 0.0))
    assert LP.propose(sc, point=tuple(pt)).ok
    out = LP.check(sc)
    ids = [r["id"] for r in out["rows"]]
    assert "CLR" in ids and ids.index("CLR") > ids.index("C5")
    clr = next(r for r in out["rows"] if r["id"] == "CLR")
    assert clr["status"] != core.NOT_CHECKED and clr["t"] is not None
    v = out["view"]
    zone = v["zone"]
    assert Z.polygon_area(zone) > 0
    for p in v["path_world"]:                                       # the hook's whole path inside the zone
        assert Z.inside(zone, p[:2])
    assert Z.inside(zone, v["slew"])
    for d in v["patches"]:
        for q in d["corners"]:
            assert Z.inside(zone, q)
    assert len(v["patches"]) == 4 and {d["status"] for d in v["patches"]} <= {core.OK, core.AMBER, core.RED}
    assert v["rings"] and v["rings"][0][1] == core.RED
    full = v["reach"]["full"]
    ro = BL.readout(sc, c, ld)
    assert full is not None and full >= ro.radius - 1e-6 or ro.status == core.RED
    # the pads at the ground check's worst moment carry what C5 says
    c5 = next(r for r in out["rows"] if r["id"] == "C5")
    worst = max(v["patches"], key=lambda d: d["force"])
    assert core.force_t(worst["force"]) == pytest.approx(c5["measure"], rel=1e-6)
    # live: drawn data at the pose shown
    d = LZ.live_view(sc)
    assert d is not None and len(d["zone"]) >= 3 and LZ.tail_radius(sc, c) > 1.0
    # the plan sheet
    path = LZ.plan_sheet(sc, str(tmp_path / "plan.html"))
    page = open(path, encoding="utf-8").read()
    assert "Plan view" in page and "Range diagram" in page and "Clearance" in page and "Exclusion zone" in page
    assert "1926.1408" in page and "SAMPLE" in page
    for svg in page.split("<svg")[1:]:
        xml.dom.minidom.parseString("<svg" + svg.split("</svg>")[0] + "</svg>")
    for w in core.FORBIDDEN_WORDS:
        assert w not in page.lower()
    assert bpy.ops.fresing.lifting_plan_sheet("EXEC_DEFAULT", True, show=False) == {"FINISHED"}
    assert os.path.isfile(LZ.sheet_path(sc))
