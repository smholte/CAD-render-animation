"""Task 0076: the invented cable-lay vessel spread (tools/make_demo_cable_lay.py, tools/demo_cable_lay/).

The STEP files are big (the assembly ~13 MB), so they are not in the repository: the module fixture writes them once
into a temporary folder (about 45 s) and the app's importer reads them. Pure-geometry checks (route, MBR, tangents)
run for several cable sizes without OpenCascade.
"""

import json
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from demo_cable_lay import route as rt  # noqa: E402
from demo_cable_lay.params import Params  # noqa: E402

TRIANGLE_BUDGET = 3_000_000           # placed triangles of the whole assembly at Normal detail


# ---------------------------------------------------------------------------------------------------------
# Without OpenCascade
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("d", [50.0, 120.0, 200.0, 350.0, 500.0])
def test_route_respects_mbr_and_is_smooth(d):
    p = Params(cable_d=d)
    pos = rt.positions(p)
    r = rt.main_route(p, pos)
    assert p.mbr == pytest.approx(17.5 * d)
    assert r.min_radius() >= p.mbr
    for gap, ang in r.joins():
        assert gap < 1e-6 and ang < 1e-5
    assert all(s.length > 100.0 for s in r.segments)
    # the carousel core, the chute and the quadrant are no tighter than the MBR
    assert p.core_r >= p.mbr and p.chute_r >= p.mbr and p.quadrant_r >= p.mbr
    # the route goes the right way: from the carousel to under the water behind the stern
    assert r.segments[0].start[0] > pos["tower_x"] and r.end[2] < 0 and r.end[0] < 0
    # the machines along the deck line do not overlap: chute, tensioner 2, tensioner 1, handling winches, tower
    t1, t2 = pos["tensioners"]
    half = rt.TENSIONER_HALF
    assert pos["chute_x"] + 2000 < t2 - half
    assert t2 + half + 2000 < t1 - half
    assert t1 + half + 2500 < pos["tower_x"] - p.bend_r
    # the carousel fits the vessel's beam with its well
    assert p.carousel_d / 2 + 900 < p.beam / 2


def test_route_length_and_sampling():
    p = Params()
    r = rt.main_route(p, rt.positions(p))
    pts = r.sample(25.0)
    assert np.max(r.distance(pts)) < 1e-6
    # an arc's chord sag at 25 mm steps on a 4 m bend is far below a micrometre: the length is the sum of segments
    assert r.length == pytest.approx(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)), abs=0.5)


def test_rope_round_a_sheave_is_tangent():
    r = rt.rope_route("test", 40.0, 0.0, [("sheave", (0.0, 1000.0), 600.0, +1, {"name": "drum"}),
                                           ("sheave", (-9000.0, 6000.0), 300.0, +1, {"name": "sheave"}),
                                           ("point", (-2000.0, 2500.0))])
    for gap, ang in r.joins():
        assert gap < 1e-6 and ang < 1e-5
    first = r.segments[0]
    # the first straight leaves the drum on its tangent: square to the radius at the leaving point
    v = first.start - np.array([0.0, 0.0, 1000.0])
    assert abs(v @ first.tangent()) < 1e-6
    assert np.linalg.norm(v) == pytest.approx(600.0)


# ---------------------------------------------------------------------------------------------------------
# With OpenCascade: the files, read by the app's importer
# ---------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def made(tmp_path_factory):
    pytest.importorskip("OCP")
    from demo_cable_lay import layout
    from fresing_render.importer import step_reader
    out = str(tmp_path_factory.mktemp("demo"))
    S = layout.write(out, Params(), log=lambda *_: None)
    trees = {}
    for key, fname in layout.FILES.items():
        cache = os.path.join(out, "cache_" + key)
        quality = "normal" if key == "assembly" else "draft"
        info = step_reader.read_step(os.path.join(out, fname), cache, quality)
        arrays = np.load(os.path.join(cache, "meshes.npz"))
        trees[key] = (info, arrays)
    with open(os.path.join(out, layout.ROUTE_JSON), encoding="utf-8") as fh:
        route_sheet = json.load(fh)
    with open(os.path.join(out, layout.JOINTS_JSON), encoding="utf-8") as fh:
        joints = json.load(fh)
    return {"out": out, "S": S, "trees": trees, "route": route_sheet, "joints": joints, "layout": layout}


def _parts(info):
    return [n for n in info["nodes"] if n["kind"] == "part"]


def _world(info, i):
    """World matrix (m) of node i from the chain of local matrices."""
    nodes = info["nodes"]
    M = np.eye(4)
    while i >= 0:
        n = nodes[i]
        if n["matrix"] is not None:
            M = np.array(n["matrix"]) @ M
        i = n["parent"]
    return M


def test_every_file_is_read_with_names_and_colours(made):
    for key, (info, arrays) in made["trees"].items():
        parts = _parts(info)
        assert parts, key
        assert all(n["name"] and n["name"] != "Unnamed" for n in info["nodes"]), key
        assert all(n.get("color") for n in parts), f"{key}: parts without a colour"
        for mid in range(info["stats"]["unique_parts"]):
            assert len(arrays[f"t{mid}"]) > 0, f"{key}: mesh {mid} is empty"
    stats = made["trees"]["assembly"][0]["stats"]
    assert stats["placed_parts"] > 600 and stats["unique_parts"] > 80


def test_part_counts(made):
    info = made["trees"]["assembly"][0]
    parts = _parts(info)
    count = lambda name: sum(1 for n in parts if n["name"] == name)  # noqa: E731
    p = Params()
    assert p.pads_per_track == 48
    assert count("TRACK PAD") == 4 * 48 and count("TRACK CHAIN LINK") == 4 * 48
    assert count("DRIVE SPROCKET") == 4 and count("IDLER SPROCKET") == 4
    for name in ("GUIDE SHEAVE", "LEAD SHEAVE"):
        assert count(name) == 1, name
    assert count("FAIRLEAD SHEAVE") == 2 and count("TIPPING SHEAVE") == 2
    assert count("WINCH DRUM") == 5                       # 2 handling, quadrant handling, 2 tipping
    assert count("CABLE ROLLER") >= 30 and count("SUPPORT ROLLER") >= 24
    assert count("BEND RESTRICTOR ELEMENT") >= 10 and count("CPS LATCH") == 1 and count("CENTRALISER") == 1
    assert count("CABLE") == 1 and count("CABLE END") == 1 and count("CABLE COIL") == 1
    # each track's pads sit under their own track assembly
    for k in (1, 2):
        for t in ("BOTTOM TRACK#1", "TOP TRACK CARRIAGE#1/TOP TRACK#1"):
            prefix = f"DEMO CABLE LAY#1/TENSIONER#{k}/{t}/TRACK PAD#"
            assert sum(1 for n in parts if n["uid"].startswith(prefix)) == 48


def test_part_names_are_sorted_by_the_library(made):
    from fresing_render.core import part_types
    want = {"GUIDE SHEAVE": "Winch drums & sheaves", "WINCH DRUM": "Winch drums & sheaves",
            "CABLE ROLLER": "Conveyor rollers", "DRIVE SPROCKET": "Gears & sprockets",
            "HYDRAULIC MOTOR": "Hydraulic components", "PLANETARY GEARBOX": "Motors & gearboxes",
            "PISTON ROD": "Chrome rods & linear shafts", "TENSIONER CYLINDER": "Hydraulic cylinders",
            "WIRE ROPE": "Lifting gear & wire ropes", "CABLE": "Cables", "TRACK CHAIN LINK": "Chains",
            "PILLOW BLOCK": "Bearing housings & units", "SHACKLE": "Lifting gear & wire ropes"}
    names = {n["name"] for n in made["trees"]["assembly"][0]["nodes"]}
    for name, group in want.items():
        assert name in names, name
        assert part_types.classify(name) == group, name
    # a few bolts in ISO notation, so the standard-part lighter facets are used
    assert any(n.startswith("ISO 4017 M") for n in names)


def test_sheave_grooves_are_tori_on_the_rope_centre(made):
    """Every sheave's groove is a torus whose major radius is the pitch (rope / cable centre) radius."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    by_name = {}
    for node, *_ in __import__("demo_cable_lay.geom", fromlist=["walk"]).walk(made["S"].root):
        if hasattr(node, "shape"):
            by_name.setdefault(node.name, node.shape)
    sheet = made["route"]["sheaves"]
    assert len(sheet) == 6
    for sh in sheet:
        name = sh["uid"].split("/")[-1].split("#")[0]
        ex = TopExp_Explorer(by_name[name], TopAbs_FACE)
        tori = []
        while ex.More():
            a = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
            if a.GetType() == GeomAbs_SurfaceType.GeomAbs_Torus:
                tori.append((a.Torus().MajorRadius(), a.Torus().MinorRadius()))
            ex.Next()
        assert tori, name
        for major, minor in tori:
            assert abs(major - sh["pitch_radius"]) < 0.1, name
            assert abs(minor - sh["groove_radius"]) < 0.1, name
    # the guide sheave carries the cable on the route's bend radius
    p = Params()
    assert sheet[0]["pitch_radius"] == p.bend_r and sheet[0]["groove_radius"] == p.cable_r


def test_route_sheet_mbr_and_ends(made):
    sheet = made["route"]
    p = Params()
    assert sheet["cable"]["mbr"] == p.mbr and sheet["cable"]["diameter"] == p.cable_d
    for r in sheet["routes"]:
        segs = r["segments"]
        for a, b in zip(segs, segs[1:]):
            assert np.allclose(a["end"], b["start"], atol=1e-3)
        for s in segs:
            if s["type"] == "arc":
                assert s["radius"] >= p.mbr, (r["name"], s)
    assert sheet["quadrant"]["radius"] >= p.mbr
    # what each part of the main route lies on is named by a uid of the assembly
    uids = {n["uid"] for n in made["trees"]["assembly"][0]["nodes"]}
    ons = [s["on"] for s in sheet["routes"][0]["segments"] if "on" in s]
    assert len(ons) >= 4 and all(u in uids for u in ons)


def test_cable_solid_follows_the_route(made):
    """The static CABLE (and the CABLE END on the quadrant) lie on their route's centreline within 1 mm."""
    info, arrays = made["trees"]["assembly"]
    S = made["S"]
    p = Params()
    routes = {"CABLE": S.routes["main"],
              "CABLE END": made["layout"]._shift(S.quadrant_info["cable_end_route"],
                                                 __import__("demo_cable_lay.geom", fromlist=["path_matrix"])
                                                 .path_matrix(np.eye(4), S.handles["quadrant_system"]))}
    for i, n in enumerate(info["nodes"]):
        if n["kind"] != "part" or n["name"] not in routes:
            continue
        pts = arrays[f"p{n['mesh']}"].astype(float)
        W = _world(info, i)
        world = (pts @ W[:3, :3].T + W[:3, 3]) * 1000.0             # m -> mm
        d = routes[n["name"]].distance(world[:: max(1, len(world) // 20000)])
        assert np.max(np.abs(d - p.cable_r)) < 1.0, n["name"]
        routes.pop(n["name"])
    assert not routes


def test_tensioner_pads_equal_pitch_without_overlaps(made):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from demo_cable_lay import geom as g
    tens = made["route"]["tensioners"]
    assert len(tens) == 2
    for t in tens:
        assert len(t["tracks"]) == 2
        for tr in t["tracks"]:
            pins = np.array(tr["pins"])
            assert len(pins) == 48 == len(tr["pads"])
            steps = np.linalg.norm(np.roll(pins, -1, axis=0) - pins, axis=1)
            assert np.allclose(steps, tr["pitch"], atol=1e-6)
    # neighbouring pads (and each pad with its neighbour's link) never overlap, on the wraps too
    S = made["S"]
    ten = S.files["tensioner"]
    tr = ten.info["tracks"][0]
    W = g.path_matrix(np.eye(4), tr["chain"])
    pad_shape = tr["pads"][0].node.shape
    placed = [g.xform(pad_shape, W @ c.M) for c in tr["pads"]]
    links = [g.xform(c.node.shape, W @ c.M) for c in tr["links"]]
    for k in range(len(placed)):
        nxt = (k + 1) % len(placed)
        assert g.volume(BRepAlgoAPI_Common(placed[k], placed[nxt]).Shape()) < 1.0, k
        assert g.volume(BRepAlgoAPI_Common(placed[k], links[nxt]).Shape()) < 1.0, k
        assert g.volume(BRepAlgoAPI_Common(links[k], links[nxt]).Shape()) < 1.0, k


def test_joint_sheet_names_parts_that_exist(made):
    sheet = made["joints"]
    joints = sheet["joints"]
    info = made["trees"]["assembly"][0]
    uids = {n["uid"] for n in info["nodes"]}
    names = [j["name"] for j in joints]
    assert len(names) == len(set(names)), "joint names repeat"
    for j in joints:
        assert j["type"] in ("rotate", "slide")
        assert j["parts"] and all(u in uids for u in j["parts"]), j["name"]
        assert abs(np.linalg.norm(j["axis"]["direction"]) - 1.0) < 1e-5
        if j["limits"] is not None:
            assert j["limits"][0] < j["limits"][1], j["name"]
        if j["drive"].get("by") == "follows":
            assert j["drive"]["follows"] in names, j["name"]
    want = ["CAROUSEL: Carousel turn", "CAROUSEL: Loading arm slew", "CAROUSEL: Loading arm in/out",
            "CAROUSEL: Guide sheave turn", "TENSIONER 1: Squeeze", "TENSIONER 2: Bottom track drive sprocket turn",
            "QUADRANT SYSTEM: Quadrant tip", "QUADRANT SYSTEM: TIPPING WINCH STB: Drum turn",
            "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn", "HANDLING WINCH PORT: Drum turn",
            "HANDLING WINCH STARBOARD: Fairlead sheave turn", "CHUTE: Chute roller 1 turn",
            "CABLE ROUTE: Cable roller 1 turn", "QUADRANT SYSTEM: QUADRANT: Quadrant roller 1 turn"]
    for w in want:
        assert w in names, w
    # every turning part on the cable's way has a joint: rollers, sprockets, the guide sheave
    by_cable = [j for j in joints if j["drive"].get("by") == "cable"]
    assert len(by_cable) >= 60
    # the separate machine files carry their own joints
    assert set(sheet["machine_files"]) >= {"demo_tensioner.step", "demo_carousel.step", "demo_quadrant.step"}
    for fname, js in sheet["machine_files"].items():
        key = [k for k, v in made["layout"].FILES.items() if v == fname][0]
        file_uids = {n["uid"] for n in made["trees"][key][0]["nodes"]}
        assert js and all(u in file_uids for j in js for u in j["parts"]), fname


def test_joint_axes_sit_on_their_parts(made):
    """A rotate joint driven by the cable turns its part about the part's own round axis: the axis point is the
    centre of the part's bounding box in the axis' square plane."""
    info, arrays = made["trees"]["assembly"]
    idx = {n["uid"]: i for i, n in enumerate(info["nodes"])}
    checked = 0
    for j in made["joints"]["joints"]:
        if j["type"] != "rotate" or j["drive"].get("by") != "cable" or len(j["parts"]) != 1:
            continue
        i = idx[j["parts"][0]]
        n = info["nodes"][i]
        if n["kind"] != "part":
            continue
        W = _world(info, i)
        pts = (arrays[f"p{n['mesh']}"].astype(float) @ W[:3, :3].T + W[:3, 3]) * 1000.0
        d = np.array(j["axis"]["direction"])
        c = 0.5 * (pts.min(axis=0) + pts.max(axis=0))
        off = c - np.array(j["axis"]["point"])
        off -= d * (off @ d)
        assert np.linalg.norm(off) < 2.0, j["name"]
        checked += 1
    assert checked >= 40


def test_triangles_under_budget(made):
    info, arrays = made["trees"]["assembly"]
    placed = sum(len(arrays[f"t{n['mesh']}"]) for n in _parts(info))
    assert placed < TRIANGLE_BUDGET, placed


def test_lebus_drum_has_level_grooves_and_crossovers(made):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    lebus = made["S"].files["drum_lebus"]
    drum = [c.node for c in lebus.children if c.node.name == "WINCH DRUM"][0]
    info = lebus.info
    ex = TopExp_Explorer(drum.shape, TopAbs_FACE)
    tori = 0
    while ex.More():
        a = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
        if a.GetType() == GeomAbs_SurfaceType.GeomAbs_Torus:
            assert abs(a.Torus().MajorRadius() - info["first_layer_rc"]) < 0.1
            tori += 1
        ex.Next()
    # two level pieces per turn (each may be split where it meets a neighbour's crossover)
    assert tori >= 2 * info["turns"]
    assert info["crossovers_per_turn"] == 2


def test_big_files_are_not_in_the_repository():
    for name in ("demo_cable_lay.step", "demo_vessel.step", "demo_drum_lebus.step"):
        for folder in ("tests/data", "fresing_render/data"):
            assert not os.path.exists(os.path.join(ROOT, folder, name))
