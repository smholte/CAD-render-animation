"""The demo's work-class ROV as the maker writes it (task 0173, ``fresing_render/demo_model/rov.py``): one solid with a
colour per part, the parts by name, seven propellers each turning about its own duct's axis with room to turn, the
size of a work-class ROV, the lenses in front of their housings, the numbers the demo places it by, its own file
(``layout.FILES["rov"]``), and the triangles the app's importer makes of it. No Blender."""

import json
import os
import sys
from collections import Counter

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pytest.importorskip("OCP")

from fresing_render.demo_model import geom as g  # noqa: E402
from fresing_render.demo_model import rov  # noqa: E402
from fresing_render.demo_model.params import Params  # noqa: E402

TRIANGLE_BUDGET = 40_000            # placed triangles at the importer's Normal detail (task 0173's budget)


@pytest.fixture(scope="module")
def built():
    root, info = rov.build(Params())
    return root, info, g.resolve_joints(root)


def _placed(root):
    """(part, world matrix) of every placed part."""
    return [(n, W) for n, _uid, W, _label, _path in g.walk(root) if isinstance(n, g.Part)]


_CACHE: dict = {}


def _points(shape, tol=2.0):
    """Mesh points of a shape (its own coordinates, mm); each shape meshed once."""
    if id(shape) in _CACHE:
        return _CACHE[id(shape)][1]
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, tol, False, 0.2, True)
    out = []
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        f = TopoDS.Face(e.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is not None:
            tr = loc.Transformation()
            for i in range(1, tri.NbNodes() + 1):
                q = tri.Node(i).Transformed(tr)
                out.append([q.X(), q.Y(), q.Z()])
        e.Next()
    _CACHE[id(shape)] = (shape, np.array(out))          # (the shape kept: its id stays its own)
    return _CACHE[id(shape)][1]


def _world_points(part, W):
    P = _points(part.shape)
    return P @ W[:3, :3].T + W[:3, 3]


def test_every_part_is_one_solid_with_a_colour_and_named(built):
    root, _info, _js = built
    placed = _placed(root)
    assert all(g.solids(p.shape) == 1 for p, _W in placed), [p.name for p, _W in placed if g.solids(p.shape) != 1]
    assert all(p.color for p, _W in placed)
    count = Counter(p.name for p, _W in placed)
    assert count == {"ROV FRAME": 1, "ROV BUOYANCY": 1, "ROV SKID": 2, "ROV THRUSTER DUCT": 7, "ROV PROPELLER": 7,
                     "ROV LIGHT": 2, "ROV LIGHT LENS": 2, "ROV CAMERA": 1, "ROV CAMERA LENS": 1,
                     "ROV MANIPULATOR": 2, "ROV TETHER TERMINATION": 1}, count
    # the buoyancy is yellow, the lenses that glow are light
    by = {p.name: p for p, _W in placed}
    r, gg, b = by["ROV BUOYANCY"].color
    assert r > 0.8 and gg > 0.5 and b < 0.2
    assert min(by["ROV LIGHT LENS"].color) > 0.8


def test_size_and_origin(built):
    _root, info, _js = built
    L, W, H = info["size"]
    assert 2600.0 <= L <= 3400.0 and 1500.0 <= W <= 2100.0 and 1600.0 <= H <= 2200.0, info["size"]
    lo, hi = np.array(info["box"][0]), np.array(info["box"][1])
    assert np.allclose(hi - lo, info["size"])
    # the origin is the middle of the skids' underside: z 0 at the bottom, the ROV about centred on it in y
    assert lo[2] == pytest.approx(0.0, abs=1.0)
    assert abs(lo[1] + hi[1]) < 50.0
    assert lo[0] < -1000.0 < 1000.0 < hi[0]


def test_info_keys(built):
    _root, info, _js = built
    for k in ("tether", "camera", "lights", "box", "size"):
        assert k in info, k
    t = info["tether"]
    d = np.array(t["direction"])
    assert np.linalg.norm(d) == pytest.approx(1.0) and d[2] > 0.7 and d[0] < 0.0          # up and aft
    assert t["point"][0] < 0.0 and t["point"][2] > info["box"][1][2] - 100.0                 # on top, aft
    c = info["camera"]
    dc = np.array(c["direction"])
    assert np.linalg.norm(dc) == pytest.approx(1.0) and dc[0] > 0.8                          # looks forward
    assert c["point"][0] > 1300.0 and abs(c["point"][1]) < 1.0
    assert len(info["lights"]) == 2 and all(q[0] > 1300.0 for q in info["lights"])
    assert info["lights"][0][1] == pytest.approx(-info["lights"][1][1]) and abs(info["lights"][0][1]) > 300.0
    json.dumps(info)                                                                         # plain numbers only


def test_lenses_sit_in_front_of_their_housings(built):
    root, info, _js = built
    placed = _placed(root)
    housings = [_world_points(p, W) for p, W in placed if p.name == "ROV LIGHT"]
    lenses = [_world_points(p, W) for p, W in placed if p.name == "ROV LIGHT LENS"]
    assert len(housings) == len(lenses) == 2
    for q in info["lights"]:
        lens = next(L for L in lenses if np.linalg.norm(L.mean(axis=0)[1:] - q[1:]) < 5.0)
        house = next(Hh for Hh in housings if abs(Hh.mean(axis=0)[1] - q[1]) < 5.0)
        # the lens' front is the frontmost face of its light; the lens lies across the light's axis (+x)
        assert lens[:, 0].max() > house[:, 0].max() - 0.01
        assert lens[:, 0].min() >= house[:, 0].max() - 30.0
        assert lens[:, 0].max() - lens[:, 0].min() < 20.0
        assert np.allclose(0.5 * (lens.min(axis=0) + lens.max(axis=0)), q, atol=1.0)
    cam = next(_world_points(p, W) for p, W in placed if p.name == "ROV CAMERA")
    cl = next(_world_points(p, W) for p, W in placed if p.name == "ROV CAMERA LENS")
    d = np.array(info["camera"]["direction"])
    assert (cl @ d).max() > (cam @ d).max()                       # the lens is the camera's front
    assert np.allclose(0.5 * (cl.min(axis=0) + cl.max(axis=0)), info["camera"]["point"], atol=2.0)


def test_seven_propellers_turn_in_their_ducts(built):
    root, _info, js = built
    assert [j["name"] for j in js] == [f"ROV: Thruster {k} turn" for k in range(1, 8)]
    placed = {}
    for node, uid, W, _label, _path in g.walk(root):
        if isinstance(node, g.Part):
            placed[uid] = (node, W)
    horizontal = vertical = 0
    for j in js:
        assert j["type"] == "rotate" and j["drive"]["by"] == "operator" and j.get("motor") is True
        assert j["limits"] is None
        assert len(j["parts"]) == 1
        prop, Wp = placed[j["parts"][0]]
        assert prop.name == "ROV PROPELLER"
        duct_uid = j["parts"][0].rsplit("/", 1)[0] + "/ROV THRUSTER DUCT#1"
        duct, Wd = placed[duct_uid]
        a = np.array(j["axis"]["point"])
        d = np.array(j["axis"]["direction"])
        # the axis is the duct's own axis: along its local z through its centre
        assert np.allclose(Wd[:3, 2], d, atol=1e-5)          # (the sheet rounds to 1e-6)
        off = Wd[:3, 3] - a
        assert np.linalg.norm(off - d * (off @ d)) < 1e-3
        if abs(d[2]) < 1e-6:
            horizontal += 1
            # in plan at ±45°, pointing out to its corner
            assert abs(abs(d[0]) - abs(d[1])) < 1e-6
            assert np.sign(d[0]) == np.sign(a[0]) and np.sign(d[1]) == np.sign(a[1])
        else:
            assert np.allclose(d, [0, 0, 1])
            vertical += 1
        # the propeller turns inside the duct's bore with room: radius < bore radius - 5 mm, axially inside the duct
        P = _world_points(prop, Wp) - a
        Q = _world_points(duct, Wd) - a
        along, along_d = P @ d, Q @ d
        radial = np.linalg.norm(P - np.outer(along, d), axis=1)
        assert radial.max() < rov.DUCT_RI - 5.0, (j["name"], radial.max())
        assert along.min() > along_d.min() and along.max() < along_d.max()
        # the duct's wall, where the blades are: no duct point within the blades' circle there
        rd = np.linalg.norm(Q - np.outer(along_d, d), axis=1)
        band = (along_d > along.min() - 5.0) & (along_d < along.max() + 5.0) & (rd > rov.PROP_HUB_R + 20.0)
        blades = (radial > rov.PROP_HUB_R + 15.0)
        assert rd[band].min() > radial[blades].max() + 5.0, j["name"]
        # turned about the axis it stays inside the bore
        R = g.Rot(d, 37.0)[:3, :3]
        P2 = P @ R.T
        r2 = np.linalg.norm(P2 - np.outer(P2 @ d, d), axis=1)
        assert r2.max() < rov.DUCT_RI - 5.0
    assert horizontal == 4 and vertical == 3


def test_parts_inside_the_frame_and_the_tether_on_top(built):
    root, info, _js = built
    placed = _placed(root)
    term = next(_world_points(p, W) for p, W in placed if p.name == "ROV TETHER TERMINATION")
    foam = next(_world_points(p, W) for p, W in placed if p.name == "ROV BUOYANCY")
    assert term[:, 2].min() >= foam[:, 2].max() - 1.0                 # it stands on the buoyancy's top
    # the tether's point is the middle of the restrictor's end face, square to its direction
    tip, d = np.array(info["tether"]["point"]), np.array(info["tether"]["direction"])
    end = term[np.abs((term - tip) @ d) < 0.01]
    assert len(end) > 8 and ((term - tip) @ d).max() < 0.01 and np.allclose(end.mean(axis=0), tip, atol=1.0)
    # the skids carry it: nothing lower than their underside
    skids = np.concatenate([_world_points(p, W) for p, W in placed if p.name == "ROV SKID"])
    assert skids[:, 2].min() == pytest.approx(0.0, abs=0.5)
    allp = np.concatenate([_world_points(p, W) for p, W in placed])
    assert allp[:, 2].min() > -0.5


def test_writes_its_own_file_and_triangles_under_budget(built, tmp_path):
    """demo_rov.step is written (one solid per part) and the importer reads it with names and colours, its joints'
    parts among its uids, at Normal detail under the budget. (``layout.write`` writes it with the other files: the
    whole spread's checks in tests/test_demo_cable_lay.py read it too.)"""
    from fresing_render.demo_model import layout
    from fresing_render.importer import step_reader
    assert layout.FILES["rov"] == rov.FILE == "demo_rov.step" and "rov" in layout.MACHINE_FILES
    root, info, js = built
    f = tmp_path / rov.FILE
    g.write_step(root, str(f))
    tree = step_reader.read_step(str(f), str(tmp_path / "cache"), "normal")
    arrays = np.load(tmp_path / "cache" / "meshes.npz")
    parts = [n for n in tree["nodes"] if n["kind"] == "part"]
    assert len(parts) == 27 and all(n.get("color") for n in parts)
    uids = {n["uid"] for n in tree["nodes"]}
    assert all(u in uids for j in js for u in j["parts"])
    placed = sum(len(arrays[f"t{n['mesh']}"]) for n in parts)
    assert 5_000 < placed <= TRIANGLE_BUDGET, placed
    sheet = layout._park_sheet(info)                         # (as the route sheet holds it)
    assert json.loads(json.dumps(sheet))["tether"]["point"] == pytest.approx(info["tether"]["point"], abs=1e-3)


# ---------------------------------------------------------------------------------------------------------------
# where it works and its tether (task 0173)
# ---------------------------------------------------------------------------------------------------------------

HORN = np.array([2550.0, -4050.0, 4050.0 - 4050.0])     # (as layout: horn A's bend centre; only x and y matter here)
R = 4050.0


@pytest.fixture(scope="module")
def placed():
    P = rov.station(HORN, R)
    root, info = rov.build(Params(), place=P, cable_y=HORN[1])
    return root, info, P


def test_the_station_is_beside_the_touch_down_and_looks_at_it(placed):
    _root, info, P = placed
    x_leave = HORN[0] - R * np.sin(np.radians(rov.LEAVE_DEG))
    tdp = np.array([x_leave - rov.LAYBACK, HORN[1], -rov.DEPTH])
    at = P[:3, 3]
    assert at[0] == pytest.approx(tdp[0]) and at[2] == pytest.approx(-rov.DEPTH + rov.ABOVE)
    assert abs(at[1] - HORN[1]) == pytest.approx(rov.SIDE) and (at[1] - HORN[1]) * HORN[1] < 0     # inboard of it
    fwd = P[:3, :3] @ np.array([1.0, 0.0, 0.0])
    to_tdp = (tdp - at)[:2] / np.linalg.norm((tdp - at)[:2])
    assert float(fwd[:2] @ to_tdp) > 0.999 and abs(fwd[2]) < 1e-9                             # level, facing it
    cam = np.array(info["camera"]["point"])
    cd = P[:3, :3] @ np.array(info["camera"]["direction"])
    cw = P[:3, :3] @ cam + at
    miss = np.linalg.norm(np.cross(tdp - cw, cd))                       # the camera's view line passes near it
    assert miss < 2500.0, miss


def test_the_tether_runs_slack_from_the_restrictor_to_the_transom(placed):
    root, info, P = placed
    parts = {n.name: (n, W) for n, W in _placed(root)}
    assert "ROV TETHER" in parts
    n, W = parts["ROV TETHER"]
    assert g.solids(n.shape) == 1 and n.color is not None
    pts = _world_points(n, W)
    tip = np.array(info["tether"]["point"])
    top_l = np.linalg.inv(P) @ np.r_[info["tether_top"], 1.0]
    assert np.linalg.norm(pts - tip, axis=1).min() < rov.TETHER_R + 3.0       # it starts at the restrictor's end
    assert np.linalg.norm(pts - top_l[:3], axis=1).min() < rov.TETHER_R + 3.0  # and ends at its point on the transom
    top = np.array(info["tether_top"])
    assert top[0] < 0.0 and top[2] < 0.0 and (top[1] - HORN[1]) * HORN[1] < 0    # aft of the transom, under water, inboard
    chord = np.linalg.norm((P @ np.r_[tip, 1.0])[:3] - top)
    assert 1.02 * chord < info["tether_length"] < 1.15 * chord
    # it stays inboard of the cable's line (the cable runs at y = HORN[1]), 3 m and more away, and over the seabed
    wp = pts @ P[:3, :3].T + P[:3, 3]
    assert ((wp[:, 1] - HORN[1]) * -np.sign(HORN[1]) > 3000.0).all()
    assert wp[:, 2].min() > -rov.DEPTH + 1000.0                         # a metre and more over the seabed
