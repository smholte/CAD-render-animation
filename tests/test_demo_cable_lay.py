"""Tasks 0076 + 0084: the invented cable-lay vessel spread (tools/make_demo_cable_lay.py, fresing_render/demo_model/).

Task 0084 re-laid the deck the way the owner works: side lanes A (starboard) and B (port) with V roller highways, the
quadrant's middle lane with rails, a lower path beside and below side A; the cable's oval runs through both
tensioners and round the D-quadrant. The STEP files are big, so they are not in the repository: the module fixture
writes them once into a temporary folder (about 60 s) and the app's importer reads them. Pure-geometry checks (route,
MBR, tangents, the layout's order) run for several cable sizes without OpenCascade.
"""

import json
import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fresing_render.demo_model import route as rt  # noqa: E402
from fresing_render.demo_model.params import Params  # noqa: E402

TRIANGLE_BUDGET = 3_000_000           # placed triangles of the whole assembly at Normal detail
SIZES = [50.0, 120.0, 200.0, 350.0, 500.0]


# ---------------------------------------------------------------------------------------------------------
# Without OpenCascade
# ---------------------------------------------------------------------------------------------------------

def _smooth(r):
    for gap, ang in r.joins():
        assert gap < 1e-6 and ang < 1e-5, r.name


@pytest.mark.parametrize("d", SIZES)
def test_oval_route_respects_mbr_and_is_smooth(d):
    p = Params(cable_d=d)
    pos = rt.positions(p)
    r = rt.main_route(p, pos)
    assert p.mbr == pytest.approx(17.5 * d)
    assert r.min_radius() >= p.mbr * 1.15 - 1e-6              # every bend 1.15 x the MBR (the route sheet's bends)
    _smooth(r)
    assert all(s.length > 100.0 for s in r.segments)
    # the carousel core, the horn and the quadrant are no tighter than the MBR
    assert p.core_r >= p.mbr and p.chute_r >= p.mbr and p.quadrant_r >= p.mbr
    # from the carousel to under the water behind the stern
    assert r.segments[0].start[0] > pos["tower_x"] and r.end[2] < 0 and r.end[0] < 0
    # the other routes too: the quay's loading route, the CPS slide, the cable's end at the core
    others = [rt.quay_route(p, pos, __import__("fresing_render.demo_model.layout", fromlist=["x"]).quay_positions(p, pos)),
              rt.cps_slide_route(p, pos), rt.core_end_route(p, pos["coil_in"], p.turntable_t + p.cable_r)]
    for o in others:
        _smooth(o)
        assert o.min_radius() >= p.mbr, o.name


def _arcs(r, radius=None, angle=None):
    out = []
    for seg, info in zip(r.segments, r.info):
        if seg.kind != "arc":
            continue
        if radius is not None and abs(seg.radius - radius) > 1e-6:
            continue
        if angle is not None and abs(math.degrees(seg.angle) - angle) > 1e-6:
            continue
        out.append((seg, info))
    return out


@pytest.mark.parametrize("d", SIZES)
def test_oval_goes_through_both_tensioners_and_round_the_quadrant(d):
    """The owner's oval (0083): lower path aft on side A, the stern turn to side B, forward through tensioner 1,
    round the quadrant (180°), aft on side A through tensioner 2, down horn A."""
    p = Params(cable_d=d)
    pos = rt.positions(p)
    r = rt.main_route(p, pos)
    names = [i.get("rollers") or i.get("support") for i in r.info]
    order = ["coil", "guide cage", "guide frame", "arch", "tower foot", "lower path", "stern turn", "side B",
             "side B rise", "side B", "quadrant gutter", "side A", "horn A"]
    it = iter(names)
    assert all(any(n == want for n in it) for want in order), names
    # task 0102: the lanes lie on the D's curve – straight from side B round the gutter straight into side A (one U, no
    # S-bends): the gutter's arc has a straight on each side, along x, at y = +-the D's radius
    k = names.index("quadrant gutter")
    assert names[k - 1] == "side B" and names[k + 1] == "side A"
    for seg in (r.segments[k - 1], r.segments[k + 1]):
        assert seg.kind == "line" and abs(seg.tangent()[0]) == pytest.approx(1.0)
        assert abs(seg.start[1]) == pytest.approx(p.quadrant_r) and abs(seg.end[1]) == pytest.approx(p.quadrant_r)
    assert p.lane_y == p.quadrant_r
    assert not [a for a in _arcs(r) if a[1].get("rollers") in ("side A", "side B")]
    # both 180° turns: the stern turn (lower path -> side B) and round the quadrant (side B -> side A)
    (st, _), = [a for a in _arcs(r, angle=180.0) if a[1].get("rollers") == "stern turn"]
    (qd, _), = [a for a in _arcs(r, angle=180.0) if a[1].get("rollers") == "quadrant gutter"]
    assert st.radius >= p.bend_r and qd.radius == p.quadrant_r
    assert np.allclose(qd.centre, [pos["quadrant_x"], 0.0, p.line_z])
    # the gripping runs: tensioner 1 on side B, tensioner 2 on side A, on the cable's line
    a = p.links_per_run * p.pad_pitch / 2
    for y in (p.lane_y, -p.lane_y):
        for x in (pos["tensioners"][0] - a, pos["tensioners"][0], pos["tensioners"][0] + a):
            assert r.distance([x, y, p.line_z])[0] < 1e-6
    # the lower path: beside side A (outboard, clear of tensioner 2), 1–1.5 m below its highway (Ø up to 350)
    assert pos["lower_y"] < -p.lane_y - rt.TENSIONER_WIDTH - 500.0
    if d <= 350:
        assert 1000.0 <= p.line_z - p.low_z <= 1500.0
    # the stern turn crosses the middle lane under the quadrant's rails
    assert p.low_z + p.cable_r + 55.0 < p.rail_z - 400.0           # radius controller's top < girder's underside
    # order from the stern: handler (its top pulley clear of the stern turn's web), stern turn, tensioners, quadrant,
    # its winch, the carousel's well
    assert pos["handler_reach_x"] + 450.0 + 500.0 < pos["stern_turn_x"] - pos["stern_turn_r"]
    assert pos["stern_turn_x"] + 400.0 + 2 * p.bend_r * math.sin(math.radians(pos["rise_deg"])) + 1000.0 \
        < pos["tensioners"][0] - rt.TENSIONER_HALF
    # the cable engine (task 0095) on the lower path, forward of tensioner 2, on its straight (aft of the tower's foot)
    assert pos["engine_y"] == pos["lower_y"]
    assert pos["tensioners"][0] + rt.TENSIONER_HALF < pos["engine_x"] - rt.ENGINE_FRAME
    assert pos["engine_x"] + rt.ENGINE_FRAME + 500.0 < pos["tower_x"] - p.bend_r
    assert r.distance([[pos["engine_x"] + dx, pos["lower_y"], p.low_z] for dx in (-1700.0, 0.0, 1700.0)]).max() < 1e-6
    assert pos["tensioners"][0] + rt.TENSIONER_HALF < pos["cps_join_x"] < pos["quadrant_x"] - 600.0
    assert pos["quadrant_apex_x"] < pos["qh_winch_x"] - rt.WINCH_HALF
    assert pos["qh_winch_x"] + rt.WINCH_HALF < pos["carousel_x"] - pos["well_r"]
    # the D passes through the side lanes' tensioners on its way aft (task 0102): its sides on their cable lines; the
    # tensioners' bases reach only so far inboard (their bottom tracks), the D's frame lower down stays inside that
    from fresing_render.demo_model import deck as dk
    ds = dk.d_shape(p)
    assert ds["half_width"] > p.lane_y and ds["inner"] <= p.lane_y - rt.TENSIONER_INBOARD
    # everything fits the beam
    assert p.carousel_d / 2 + 900 < p.beam / 2
    assert abs(pos["lower_y"]) + 1000.0 < p.beam / 2


@pytest.mark.parametrize("d", SIZES)
def test_arch_only_slews_over_the_coil(d):
    """The loading tower's arch reaches the coil from near the core to near the rim by slewing alone: the guide's
    distance from the carousel's centre follows from the angle; at rest it lies over the rest coil radius."""
    p = Params(cable_d=d)
    pos = rt.positions(p)
    ar = pos["arch"]
    T = np.array([pos["tower_x"], pos["tower_y"]])
    C = np.array([pos["carousel_x"], 0.0])
    G = np.array(ar["guide"])
    assert np.linalg.norm(G - T) == pytest.approx(ar["span"])
    assert np.linalg.norm(G - C) == pytest.approx(math.hypot(p.coil_r, p.bend_r))
    lo, hi = ar["slew_limits"]
    assert lo < 0 < hi
    rads = []
    base = math.radians(ar["slew_rest_deg"])
    for a in np.linspace(lo, hi, 21):
        g2 = T + ar["span"] * np.array([math.cos(base + math.radians(a)), math.sin(base + math.radians(a))])
        dist = np.linalg.norm(g2 - C)
        rads.append(math.sqrt(max(dist ** 2 - p.bend_r ** 2, 0.0)))
    assert min(rads) <= p.core_r + rt.GUIDE_IN + 1.0
    assert max(rads) >= ar["coil_radii"][1] - 1.0
    # the tower stands outside the carousel's well
    assert np.linalg.norm(T - C) >= pos["well_r"] + 1700.0


def test_route_length_and_sampling():
    p = Params()
    r = rt.main_route(p, rt.positions(p))
    pts = r.sample(25.0)
    assert np.max(r.distance(pts)) < 1e-6
    assert r.length == pytest.approx(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)), abs=0.5)


def test_rope_round_a_sheave_is_tangent():
    r = rt.rope_route("test", 40.0, 0.0, [("sheave", (0.0, 1000.0), 600.0, +1, {"name": "drum"}),
                                           ("sheave", (-9000.0, 6000.0), 300.0, +1, {"name": "sheave"}),
                                           ("point", (-2000.0, 2500.0))])
    _smooth(r)
    first = r.segments[0]
    v = first.start - np.array([0.0, 0.0, 1000.0])
    assert abs(v @ first.tangent()) < 1e-6
    assert np.linalg.norm(v) == pytest.approx(600.0)
    # the same rope in a vertical plane along another direction: the same shape, turned
    u = np.array([0.6, -0.8])
    r2 = rt.rope_route("test2", 40.0, 0.0, [("sheave", (0.0, 1000.0), 600.0, +1, {"name": "drum"}),
                                            ("sheave", (-9000.0, 6000.0), 300.0, +1, {"name": "sheave"}),
                                            ("point", (-2000.0, 2500.0))], origin=(100.0, 200.0), udir=u)
    _smooth(r2)
    assert r2.length == pytest.approx(r.length)
    for a, b in zip(r.segments, r2.segments):
        q = a.end
        want = np.array([100.0 + q[0] * u[0], 200.0 + q[0] * u[1], q[2]])
        assert np.allclose(b.end, want, atol=1e-6)


def test_lebus_crossover_and_pads_from_the_parameters():
    p = Params()
    assert 30.0 <= p.lebus_crossover_deg <= 40.0
    assert 150.0 <= p.pad_v_deg <= 160.0
    assert p.links_per_run == 14 and p.links_per_run * p.pad_pitch == 4200.0
    assert p.pads_per_track == 36


# ---------------------------------------------------------------------------------------------------------
# With OpenCascade: the files, read by the app's importer
# ---------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def made(tmp_path_factory):
    pytest.importorskip("OCP")
    from fresing_render.demo_model import layout
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


def _shapes(S):
    from fresing_render.demo_model import geom as g
    by_name = {}
    for key in ("assembly", "quay_loading"):
        for node, *_ in g.walk(S.files[key]):
            if hasattr(node, "shape"):
                by_name.setdefault(node.name, node.shape)
    return by_name


def test_every_file_is_read_with_names_and_colours(made):
    assert set(made["trees"]) >= {"assembly", "quay_loading", "tensioner", "quadrant", "carousel"}
    for key, (info, arrays) in made["trees"].items():
        parts = _parts(info)
        assert parts, key
        assert all(n["name"] and n["name"] != "Unnamed" for n in info["nodes"]), key
        assert all(n.get("color") for n in parts), f"{key}: parts without a colour"
        for mid in range(info["stats"]["unique_parts"]):
            assert len(arrays[f"t{mid}"]) > 0, f"{key}: mesh {mid} is empty"
    stats = made["trees"]["assembly"][0]["stats"]
    assert stats["placed_parts"] > 1000 and stats["unique_parts"] > 120


def test_part_counts(made):
    info = made["trees"]["assembly"][0]
    parts = _parts(info)
    count = lambda name: sum(1 for n in parts if n["name"] == name)  # noqa: E731
    n = Params().pads_per_track
    assert count("TRACK PAD") == 4 * n and count("PAD BACK PLATE") == 4 * n and count("TRACK CHAIN LINK") == 4 * n
    assert count("DRIVE SPROCKET") == 4 and count("IDLER SPROCKET") == 4
    assert count("FAIRLEAD SHEAVE") == 2 and count("TIPPING SHEAVE") == 2 and count("HANDLER TOP PULLEY") == 1
    assert count("WINCH DRUM") == 5                       # 2 handling, quadrant handling, 2 tipping
    assert count("CABLE ROLLER") >= 60 and count("SUPPORT ROLLER") >= 24 and count("GUIDE ROLLER") >= 40
    assert count("ROLLER CRADLE") >= 20 and count("ROLLER TRESTLE") >= 20 and count("GRATING WALKWAY") >= 3
    assert count("CABLE ENGINE WHEEL") == 8
    assert count("QUADRANT GUTTER") == 1 and count("RAIL BOGIE") == 4 and count("QUADRANT RAIL") >= 4
    assert count("HANDLER FRAME") == 1 and count("CHUTE") == 2                     # horns A and B
    assert count("HINGE SHEAVE") == 0 and count("SHEAVE CHEEK") == 0 and count("CRADLE LIFT FRAME") >= 15
    assert count("HINGE PIN") == 2 + 1 and count("PISTON ROD") == 2 * 2 + 2 * 2 + 2   # tensioners (0102), handler
    assert count("A&R PAD EYE") == 1 and count("PAD EYE") == 2 and count("FOOT SHEAVE") == 2
    # five sets in the rack + the second end's (task 0082)
    assert count("PULL HEAD") == 6 and count("CPS RACK") == 1 and count("CPS RAMP") == 1 and count("CPS SLIDE") == 1
    # the core's end and the second end (task 0082); the quadrant operation's wires (task 0082)
    assert count("CABLE") == 1 and count("CABLE END") == 2 and count("CABLE COIL") == 1
    assert count("A&R WIRE") == 1 and count("TIPPING WIRE") == 2
    assert count("CABLE END CLAMP") == 1 and count("ARCH FRAME") == 1 and count("GUIDE FRAME") == 1
    # each track's pads sit under their own track assembly; the top track in its tilting carriage on the lift frame
    for k in (1, 2):
        for t in ("BOTTOM TRACK#1", "TOP TRACK LIFT FRAME#1/TOP TRACK CARRIAGE#1/TOP TRACK#1"):
            prefix = f"DEMO CABLE LAY#1/TENSIONER#{k}/{t}/TRACK PAD#"
            assert sum(1 for n in parts if n["uid"].startswith(prefix)) == n


def test_part_names_are_sorted_by_the_library(made):
    from fresing_render.core import part_types
    want = {"WINCH DRUM": "Winch drums & sheaves", "TIPPING SHEAVE": "Winch drums & sheaves",
            "CABLE ROLLER": "Conveyor rollers", "GUIDE ROLLER": "Conveyor rollers", "DRIVE SPROCKET": "Gears & sprockets",
            "HYDRAULIC MOTOR": "Hydraulic components", "PLANETARY GEARBOX": "Motors & gearboxes",
            "PISTON ROD": "Chrome rods & linear shafts", "TENSIONER CYLINDER": "Hydraulic cylinders",
            "HANDLER HYDRAULIC CYLINDER": "Hydraulic cylinders", "WIRE ROPE": "Lifting gear & wire ropes",
            "CABLE": "Cables", "TRACK CHAIN LINK": "Chains", "PILLOW BLOCK": "Bearing housings & units",
            "SHACKLE": "Lifting gear & wire ropes", "GRATING WALKWAY": "Gratings, stairs & railings",
            "SLEWING RING": "Bearings", "HANDLER TOP PULLEY": "Pulleys"}
    names = {n["name"] for n in made["trees"]["assembly"][0]["nodes"]}
    for name, group in want.items():
        assert name in names, name
        assert part_types.classify(name) == group, name
    assert any(n.startswith("ISO 4017 M") for n in names)


def test_sheave_grooves_are_tori_on_the_rope_centre(made):
    """Every sheave's groove is a torus whose major radius is the pitch (rope centre) radius."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    by_name = _shapes(made["S"])
    sheet = made["route"]["sheaves"]
    assert len(sheet) == 7          # 2 fairleads, the handler's top pulley, 2 swivel heads, 2 swivel feet
    uids = {n["uid"] for n in made["trees"]["assembly"][0]["nodes"]}
    for sh in sheet:
        assert sh["uid"] in uids, sh["uid"]
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


def test_route_sheet_mbr_ends_and_supports(made):
    sheet = made["route"]
    p = Params()
    assert sheet["cable"]["mbr"] == p.mbr and sheet["cable"]["diameter"] == p.cable_d
    names = [r["name"] for r in sheet["routes"]]
    assert names == ["main", "core_end", "cps_slide", "quay_loading"]
    for r in sheet["routes"]:
        segs = r["segments"]
        for a, b in zip(segs, segs[1:]):
            assert np.allclose(a["end"], b["start"], atol=1e-3)
        for s in segs:
            if s["type"] == "arc" and r["name"] != "cps_slide":
                assert s["radius"] >= p.mbr, (r["name"], s)
    assert sheet["quadrant"]["radius"] >= p.mbr
    # what the main route lies on is named by uids of the assembly
    uids = {n["uid"] for n in made["trees"]["assembly"][0]["nodes"]}
    ons = [s["on"] for s in sheet["routes"][0]["segments"] if "on" in s]
    assert len(ons) >= 8 and all(u in uids for u in ons)
    for key in ("solid", "cable_end_solid"):
        assert sheet["cable"][key] in uids
    for c in sheet["quadrant"]["handler"]["cylinders"]:
        assert c["barrel"] in uids and c["rod"] in uids
    # the quay's loading route meets the oval on side A's highway, heading forward
    quay = sheet["routes"][3]
    end = np.array(quay["segments"][-1]["end"])
    assert made["S"].routes["main"].distance(end)[0] < 1e-3
    assert np.allclose(quay["segments"][-1]["end_tangent"], [1, 0, 0], atol=1e-6)
    assert end[1] == pytest.approx(-p.lane_y)


def test_the_route_runs_through_both_tensioners_and_round_the_quadrant(made):
    sheet = made["route"]
    main = made["S"].routes["main"]
    assert [t["name"] for t in sheet["tensioners"]] == ["TENSIONER 1", "TENSIONER 2"]
    ys = []
    for t in sheet["tensioners"]:
        a, b = np.array(t["grip_line"])
        assert np.linalg.norm(b - a) == pytest.approx(Params().links_per_run * Params().pad_pitch)
        for q in (a, 0.5 * (a + b), b):
            assert main.distance(q)[0] < 1e-3, t["name"]
        ys.append(a[1])
    assert ys[0] > 0 > ys[1]                              # tensioner 1 on side B (port), 2 on side A
    q = sheet["quadrant"]
    arcs = [s for s in sheet["routes"][0]["segments"] if s["type"] == "arc" and s.get("rollers") == "quadrant gutter"]
    assert len(arcs) == 1
    assert np.allclose(arcs[0]["centre"], q["curve_centre"], atol=1e-3)
    assert arcs[0]["angle_deg"] == pytest.approx(180.0) and arcs[0]["radius"] == pytest.approx(q["radius"])


def test_rollers_about_1500_apart_on_the_straights(made):
    """Cradles (highways) and rollers (lower path) stand about 1.5 m apart; a longer gap only where a machine holds
    the cable (tensioner, cable engine) or where another stretch of cable passes under or over."""
    S = made["S"]
    pos = S.pos
    main = S.routes["main"]
    from fresing_render.demo_model.layout import _samples, _where
    pts, ss = _samples(main, 100.0)
    quay_pts, _ = _samples(S.routes["quay_loading"], 100.0)
    machines = [(pos["tensioners"][0], rt.TENSIONER_HALF + 300.0), (pos["engine_x"], rt.ENGINE_FRAME + 500.0)]
    total = 0
    for kind, stations in S.stations.items():
        st = sorted(stations)
        total += len(st)
        for a, b in zip(st, st[1:]):
            ia, qa, _ = _where(main, a)
            ib, qb, _ = _where(main, b)
            if ia != ib or b - a <= 1600.0:
                continue
            mid = [_where(main, s)[1] for s in np.linspace(a, b, 9)]
            explained = any(abs(m[0] - x) < h for m in mid for x, h in machines)
            others = np.vstack([pts[np.abs(ss - 0.5 * (a + b)) > 4000.0], quay_pts])
            for m in mid:
                d = np.hypot(others[:, 0] - m[0], others[:, 1] - m[1])
                explained = explained or bool((d < 1500.0).any())
            assert explained, (kind, a, b, qa, qb)
    assert len(S.stations["lower path"]) >= 15 and len(S.stations["highway"]) >= 20 and total >= 40


def test_cable_solid_follows_the_route(made):
    """The static CABLE (oval), the CABLE END at the core, the second end (task 0082) and the quay's CABLE lie on their
    routes within 1 mm."""
    S = made["S"]
    p = Params()
    sheet = made["route"]
    for key, routes in (("assembly", {sheet["cable"]["solid"]: S.routes["main"],
                                      sheet["cable"]["cable_end_solid"]: S.routes["core_end"],
                                      sheet["second_end"]["solid"]: S.routes["second_end"]}),
                        ("quay_loading", {"CABLE": S.routes["quay_loading"]})):
        info, arrays = made["trees"][key]
        routes = dict(routes)
        for i, n in enumerate(info["nodes"]):
            if n["kind"] != "part" or (n["uid"] not in routes and n["name"] not in routes):
                continue
            k = n["uid"] if n["uid"] in routes else n["name"]
            pts = arrays[f"p{n['mesh']}"].astype(float)
            W = _world(info, i)
            world = (pts @ W[:3, :3].T + W[:3, 3]) * 1000.0             # m -> mm
            d = routes[k].distance(world[:: max(1, len(world) // 20000)])
            assert np.max(np.abs(d - p.cable_r)) < 1.0, (key, k)
            routes.pop(k)
        assert not routes, key


def test_tensioner_pads_rubber_v_on_steel_plates(made):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from fresing_render.demo_model import geom as g
    from fresing_render.demo_model import machines as mm
    p = Params()
    tens = made["route"]["tensioners"]
    for t in tens:
        assert len(t["tracks"]) == 2 and t["pad_v_deg"] == p.pad_v_deg
        for tr in t["tracks"]:
            pins = np.array(tr["pins"])
            assert len(pins) == p.pads_per_track == len(tr["pads"]) == len(tr["back_plates"])
            steps = np.linalg.norm(np.roll(pins, -1, axis=0) - pins, axis=1)
            assert np.allclose(steps, tr["pitch"], atol=1e-6)
            # the contact run: links_per_run pitches in a straight line along the cable
            run = pins[: p.links_per_run]
            assert np.allclose(run[:, 1:], run[0, 1:], atol=1e-6)
    # the rubber pad's V: two flanks whose normals lean 10° (160° V) – dark rubber; the back plate steel
    S = made["S"]
    ten = S.files["tensioner"]
    tr = ten.info["tracks"][0]
    pad, plate = tr["pads"][0].node, tr["plates"][0].node
    assert pad.color == mm.RUBBER and plate.color == mm.STEEL
    flank = []
    ex = TopExp_Explorer(pad.shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        a = BRepAdaptor_Surface(f)
        if a.GetType() == GeomAbs_SurfaceType.GeomAbs_Plane:
            d = a.Plane().Axis().Direction()
            n = np.array([d.X(), d.Y(), d.Z()]) * (-1 if f.Orientation() == TopAbs_REVERSED else 1)
            if 0.5 < n[2] < 0.999:
                flank.append(n)
        ex.Next()
    assert len(flank) == 2
    lean = [math.degrees(math.acos(n[2])) for n in flank]
    assert lean == pytest.approx([90 - p.pad_v_deg / 2] * 2, abs=1e-6)
    # neighbouring pads, plates and links never overlap, on the wraps too
    W = g.path_matrix(np.eye(4), tr["chain"])
    placed = [g.xform(c.node.shape, W @ c.M) for c in tr["pads"]]
    plates = [g.xform(c.node.shape, W @ c.M) for c in tr["plates"]]
    links = [g.xform(c.node.shape, W @ c.M) for c in tr["links"]]
    for k in range(len(placed)):
        nxt = (k + 1) % len(placed)
        for a, b in ((placed[k], placed[nxt]), (plates[k], plates[nxt]), (plates[k], links[nxt]),
                     (links[k], links[nxt]), (placed[k], plates[k])):
            assert g.volume(BRepAlgoAPI_Common(a, b).Shape()) < 1.0, k


def test_tensioner_lifts_and_tilts(made):
    """Task 0102, as the owner works: the top track first lifts (slide up), then tilts sideways about a hinge along the
    cable on the tensioner's outboard side – tensioner 1 (port) out to port, tensioner 2 (starboard) out to starboard:
    a positive tilt moves the top track's middle away from the middle line (y = 0). Two lift and two tilt cylinders;
    the tilt cylinders are pinned on the lift frame and on the carriage (the app's cylinders)."""
    from fresing_render.demo_model import geom as g
    p = Params()
    joints = {j["name"]: j for j in made["joints"]["joints"]}
    sheet = {t["name"]: t for t in made["route"]["tensioners"]}
    uids = {n["uid"] for n in made["trees"]["assembly"][0]["nodes"]}
    for k in (1, 2):
        lift = joints[f"TENSIONER {k}: Top track lift"]
        tilt = joints[f"TENSIONER {k}: Top track tilt"]
        t = sheet[f"TENSIONER {k}"]
        side = 1.0 if k == 1 else -1.0                       # port, starboard
        assert lift["type"] == "slide" and tilt["type"] == "rotate"
        assert np.allclose(lift["axis"]["direction"], [0, 0, 1], atol=1e-6)
        lo, hi = lift["limits"]
        assert lo <= -(p.squeeze_h() - p.squeeze_h(50.0)) + 1e-6
        assert hi >= p.squeeze_h(500.0) - p.squeeze_h() + 500.0
        assert tilt["rides_on"] == f"TENSIONER {k}: Top track lift"
        assert tilt["limits"] == [0.0, 70.0]
        # the hinge runs along the cable (fore–aft) on the outboard side, over the cable's height
        d = np.array(tilt["axis"]["direction"])
        assert abs(d[0]) == pytest.approx(1.0)
        hp = np.array(tilt["axis"]["point"])
        assert side * hp[1] > p.lane_y + 500.0 and abs(hp[2] - p.line_z) < 100.0
        # a positive tilt takes the top track's middle (over the cable) out to its own side
        mid = np.array([t["centre"][0], side * p.lane_y, p.line_z + 700.0, 1.0])
        moved = g.Rot(d, 30.0, hp) @ mid
        assert side * moved[1] > side * mid[1] + 300.0 and moved[2] > mid[2]
        assert set(tilt["parts"]) < set(lift["parts"]) or tilt["parts"][0].startswith(lift["parts"][0])
        # inboard is towards the middle line
        assert np.allclose(t["inboard"], [0.0, -side, 0.0], atol=1e-6)
        # two lift cylinders (their rods ride on the lift), two tilt cylinders pinned on both sides
        assert sum(1 for u in lift["parts"] if u.endswith("/PISTON ROD#1")) == 2
        assert len(t["tilt_cylinders"]) == 2
        for c in t["tilt_cylinders"]:
            assert c["barrel"] in uids and c["rod"] in uids
            assert np.allclose(np.abs(c["axis"]), [1.0, 0.0, 0.0], atol=1e-6)
            assert c["barrel_on"] == "TOP TRACK LIFT FRAME" and c["rod_on"] == "TOP TRACK FRAME"
            assert side * c["barrel_pin"][1] > side * c["rod_pin"][1] > p.lane_y      # outboard of the cable line


def _mesh_points(shape, cache: dict, deflection: float = 10.0) -> np.ndarray:
    """The corners of a part's triangles (its own coordinates, mm)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    if id(shape) in cache:
        return cache[id(shape)]
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.5, True)
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(TopoDS.Face(ex.Current()), loc)
        if tri is not None:
            tr = loc.Transformation()
            out += [(q.X(), q.Y(), q.Z()) for q in (tri.Node(i).Transformed(tr) for i in range(1, tri.NbNodes() + 1))]
        ex.Next()
    cache[id(shape)] = np.array(out) if out else np.zeros((0, 3))
    return cache[id(shape)]


def _tensioner_pose(info, lift: float, tilt: float, path, loc):
    """A tensioner part's matrix (tensioner coordinates) with the top track lifted by ``lift`` mm and tilted ``tilt``°."""
    from fresing_render.demo_model import geom as g
    hinge = np.array(info["hinge"])
    ML = g.T(0, 0, lift)
    MC = ML @ g.Rot(info["hinge_axis"], tilt, hinge)
    cl, cc = info["parts"]["carriage"]
    if path[0] is cl:
        return (MC if len(path) > 1 and path[1] is cc else ML) @ loc
    if path[0].node.name == "TENSIONER CYLINDER" and path[-1].node.name == "PISTON ROD":
        return ML @ loc
    for t in info["tilt_cylinders"]:
        if path[0] is t["assembly"][0]:
            B0, P0 = np.array(t["barrel_pin"]), np.array(t["rod_pin"])
            B, P = (ML @ np.r_[B0, 1.0])[:3], (MC @ np.r_[P0, 1.0])[:3]
            d0, d1 = (P0 - B0) / np.linalg.norm(P0 - B0), (P - B) / np.linalg.norm(P - B)
            ang = math.degrees(math.atan2(np.cross(d0, d1) @ info["hinge_axis"], d0 @ d1))
            if path[-1] is t["barrel"][-1]:
                return g.T(*(B - B0)) @ g.Rot(info["hinge_axis"], ang, B0) @ loc
            return g.T(*(P - P0)) @ g.Rot(info["hinge_axis"], ang, P0) @ loc
    return loc


def _in_the_ds_way(S, open_tensioners: bool = True, drop_cradles: bool = True) -> list:
    """Every part (model mm, triangle corners) inside the room the D-quadrant sweeps over its whole travel – its curve, its
    gutter's upper channel, its bar – with the tensioners open (lifted, tilted out) and the lanes' cradles dropped."""
    from fresing_render.demo_model import deck as dk
    from fresing_render.demo_model import geom as g
    p, pos, layout = S.p, S.pos, __import__("fresing_render.demo_model.layout", fromlist=["x"])
    lane, ds = layout.d_lane(p), dk.d_shape(p)
    x0 = pos["quadrant_x"] - 600.0 - pos["quadrant_travel"]
    x1 = pos["quadrant_x"] + ds["half_width"]
    tens = {}
    for k in (1, 2):
        c = S.handles[f"tensioner{k}"][0]
        tens[id(c)] = c
    quad = S.quadrant_info["quadrant"]
    cps2 = S.handles["second_end_cps"][-1]
    # the cables and wires move with the D or are kept out until it moves (task 0082: the A&R and tipping wires, the
    # second end and its CPS ride on it)
    flex = {"CABLE", "CABLE END", "A&R WIRE", "TIPPING WIRE"}
    cache, out = {}, []
    for node, uid, W, _label, path in g.walk(S.root):
        if not isinstance(node, g.Part) or node.name in flex or any(c is quad or c is cps2 for c in path):
            continue
        M = W
        if path and id(path[0]) in tens:
            info = path[0].node.info
            lift, tilt = (info["lift_limits"][1], info["tilt_open"]) if open_tensioners else (0.0, 0.0)
            M = path[0].M @ _tensioner_pose(info, lift, tilt, path[1:], np.linalg.inv(path[0].M) @ W)
        lc = [c for c in path if c.node.name == "LIFTING CRADLE"]
        if lc and drop_cradles and any(c.node.name == "CRADLE LIFT" for c in path):
            M = g.T(0, 0, -lc[0].node.info["drop"]) @ M
        v = _mesh_points(node.shape, cache) @ M[:3, :3].T + M[:3, 3]
        ay, z = np.abs(v[:, 1]), v[:, 2]
        inx = (v[:, 0] > x0) & (v[:, 0] < x1) & (z < np.where(ay < lane["eyes_y"], lane["top_z"], lane["edge_top_z"]))
        bad = inx & (((ay < ds["inner"]) & (z > lane["low_z"])) | ((ay < ds["half_width"]) & (z > lane["band_z"])))
        if bad.any():
            out.append(uid)
    return out


def test_the_d_quadrants_way_is_clear(made):
    """Task 0102: over its whole travel the D-quadrant – exactly as wide as the cable's path, its sides passing through
    the tensioners' lines – sweeps a room in which nothing stands once both tensioners are open (lifted, tilted out) and
    the lanes' cradles have dropped: its frame under the cable's height inside the bottom tracks, the gutter's ends over
    them; tensioner bases, columns, horns, rails, the handler, the stern turn all outside or below. Closed, the
    tensioners stand in its way (the check sees them). Open, nothing of a tensioner stands between the two cable lines
    at any height from the cable's up (the band the owner drew)."""
    S = made["S"]
    p = S.p
    assert _in_the_ds_way(S) == []
    closed = _in_the_ds_way(S, open_tensioners=False)
    assert any("/TOP TRACK" in u for u in closed) and not any("TENSIONER BASE FRAME" in u for u in closed)
    assert any("/CRADLE " in u or "CRADLE LIFT" in u for u in _in_the_ds_way(S, drop_cradles=False))
    from fresing_render.demo_model import geom as g
    cache = {}
    for k, side in ((1, 1.0), (2, -1.0)):
        c = S.handles[f"tensioner{k}"][0]
        info = c.node.info
        for node, _uid, W, _label, path in g.walk(c.node):
            if not isinstance(node, g.Part) or path[0] not in info["parts"]["carriage"][:1] + \
                    [t["assembly"][0] for t in info["tilt_cylinders"]]:
                continue
            M = c.M @ _tensioner_pose(info, info["lift_limits"][1], info["tilt_open"], path, W)
            v = _mesh_points(node.shape, cache) @ M[:3, :3].T + M[:3, 3]
            up = v[:, 2] > p.line_z
            assert (side * v[up, 1] > p.lane_y).all(), node.name           # outboard of its own cable line


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
        if "rides_on" in j:
            assert j["rides_on"] in names, j["name"]
    want = ["CAROUSEL: Carousel turn", "LOADING TOWER: Arch slew", "LOADING TOWER: LOADING ARCH: Guide cage swivel",
            "TENSIONER 1: Top track lift", "TENSIONER 2: Top track tilt", "TENSIONER 2: Bottom track drive sprocket turn",
            "QUADRANT SYSTEM: Quadrant travel", "QUADRANT SYSTEM: Quadrant tip",
            "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt", "QUADRANT SYSTEM: QUADRANT HANDLER: Top pulley turn",
            "QUADRANT SYSTEM: Swivel sheave port swivel", "QUADRANT SYSTEM: Swivel sheave stb turn",
            "QUADRANT SYSTEM: TIPPING WINCH STB: Drum turn", "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn",
            "QUADRANT SYSTEM: Quadrant lower",
            "QUADRANT SYSTEM: Swivel sheave port foot sheave turn",
            "QUADRANT SYSTEM: QUADRANT: Quadrant gutter roller 1 turn", "QUADRANT SYSTEM: QUADRANT: Rail wheel 1 turn",
            "HANDLING WINCH 1: Drum turn", "HANDLING WINCH 2: Fairlead sheave turn", "HORN A: Chute roller 1 turn",
            "CABLE ENGINE: Bottom wheel 1 turn", "CABLE ENGINE: Cable engine squeeze",
            "STERN RADIUS CONTROLLER: Stern turn roller 1 turn", "CRADLE 1: Roller port turn",
            "Lower path roller 1 turn"]
    for w in want:
        assert w in names, w
    by = {j["name"]: j for j in joints}
    assert by["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]["limits"] == [0.0, rt.LOWER_TILT]
    assert by["QUADRANT SYSTEM: QUADRANT: Rail wheel 1 turn"]["drive"]["follows"] == "QUADRANT SYSTEM: Quadrant travel"
    assert by["QUADRANT SYSTEM: Quadrant tip"]["rides_on"] == "QUADRANT SYSTEM: Quadrant lower"
    assert by["QUADRANT SYSTEM: Quadrant lower"]["rides_on"] == "QUADRANT SYSTEM: Quadrant travel"
    assert np.allclose(by["QUADRANT SYSTEM: Quadrant travel"]["axis"]["direction"], [-1, 0, 0])
    # the arch only slews: no slide joint on the loading tower
    assert not [j for j in joints if j["name"].startswith("LOADING TOWER") and j["type"] == "slide"]
    # every turning part on the cable's way has a joint: rollers, sprockets, wheels
    assert len([j for j in joints if j["drive"].get("by") == "cable"]) >= 200
    # the separate machine files carry their own joints
    assert set(sheet["machine_files"]) >= {"demo_tensioner.step", "demo_carousel.step", "demo_quadrant.step",
                                           "demo_quay_loading.step"}
    for fname, js in sheet["machine_files"].items():
        key = [k for k, v in made["layout"].FILES.items() if v == fname][0]
        file_uids = {n["uid"] for n in made["trees"][key][0]["nodes"]}
        file_names = {j["name"] for j in js}
        assert js and all(u in file_uids for j in js for u in j["parts"]), fname
        assert all(j["drive"]["follows"] in file_names for j in js if j["drive"].get("by") == "follows"), fname


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
    assert checked >= 150


def test_triangles_under_budget(made):
    info, arrays = made["trees"]["assembly"]
    placed = sum(len(arrays[f"t{n['mesh']}"]) for n in _parts(info))
    assert placed < TRIANGLE_BUDGET, placed


def test_lebus_drum_crossovers_and_risers(made):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    lebus = made["S"].files["drum_lebus"]
    drum = [c.node for c in lebus.children if c.node.name == "WINCH DRUM"][0]
    info = lebus.info
    assert info["crossovers_per_turn"] == 2 and info["crossover_deg"] == pytest.approx(35.0)
    ex = TopExp_Explorer(drum.shape, TopAbs_FACE)
    tori, spans = 0, []
    while ex.More():
        a = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
        if a.GetType() == GeomAbs_SurfaceType.GeomAbs_Torus:
            assert abs(a.Torus().MajorRadius() - info["first_layer_rc"]) < 0.1
            tori += 1
            spans.append(math.degrees(abs(a.LastUParameter() - a.FirstUParameter())))
        ex.Next()
    # two level pieces per turn, each 180° less one crossover (some split where they meet a neighbour)
    assert tori >= 2 * info["turns"]
    assert max(spans) == pytest.approx(180.0 - 35.0, abs=0.5)
    risers = [c.node for c in lebus.children if c.node.name == "LEBUS RISER"]
    assert len(risers) == 2


def test_handling_winches_have_the_lebus_drum(made):
    """Task 0091: the deck's handling winches carry the Lebus drum (the demo's drum close-up shows it)."""
    hw = made["S"].files["handling_winch"]
    unit = [c.node for c in hw.children if c.node.name == "WINCH DRUM UNIT"][0]
    assert len([c for c in unit.children if c.node.name == "LEBUS RISER"]) == 2
    info = made["trees"]["assembly"][0]
    assert sum(1 for n in _parts(info) if n["name"] == "LEBUS RISER") == 4


def test_quadrant_system_can_move(made):
    """Tasks 0091, 0102: the D-quadrant's way aft is free. The lanes' cradles in its way drop out of it (one lead joint per
    lane, the others of that lane follow it), every other cradle stands outside its room; the travel rides on the
    handler's tilt (the tip on the travel); nothing of the handler's forward end stands in the D's way."""
    from fresing_render.demo_model import deck as dk
    from fresing_render.demo_model import geom as g
    S, layout = made["S"], made["layout"]
    p = S.p
    lane = layout.d_lane(p)
    joints = made["joints"]["joints"]
    by = {j["name"]: j for j in joints}
    drops = [j for j in joints if j["name"].endswith(" drop")]
    assert len(drops) == len(S.stations["lifting"]) >= 15
    lead = [j for j in drops if j["drive"]["by"] == "operator"]
    assert sorted(j["drive"]["lane"] for j in lead) == ["A", "B"]
    for j in drops:
        assert j["type"] == "slide" and j["axis"]["direction"] == [0.0, 0.0, -1.0]
        mine = [ld for ld in lead if np.sign(ld["axis"]["point"][1]) == np.sign(j["axis"]["point"][1])]
        assert len(mine) == 1
        assert j is mine[0] or (j["drive"]["follows"] == mine[0]["name"] and j["drive"]["ratio"] == 1.0)
        # dropped, the cradle's top is below the D's underside
        assert j["axis"]["point"][2] + dk.LIFT_TOP - j["limits"][1] < lane["low_z"] - 50.0
        assert abs(j["axis"]["point"][1]) < lane["half_width"] + 700.0
    # the other highway cradles stand clear of the D's room: outside it, or under its underside (side B's low run)
    for node, _uid, W, label, _path in g.walk(S.root):
        if label.startswith("CRADLE ") and node.name == "ROLLER CRADLE":
            corners = np.array([[x, y, z, 1.0] for x in (-310.0, 310.0) for y in (-640.0, 640.0)
                                for z in (-460.0, dk.LIFT_TOP)]) @ W.T
            assert np.abs(corners[:, 1]).min() >= lane["half_width"] or corners[:, 2].max() < lane["low_z"] - 50.0, \
                label
    assert by["QUADRANT SYSTEM: Quadrant travel"]["rides_on"] == "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"
    assert by["QUADRANT SYSTEM: Quadrant lower"]["rides_on"] == "QUADRANT SYSTEM: Quadrant travel"
    assert by["QUADRANT SYSTEM: Quadrant tip"]["rides_on"] == "QUADRANT SYSTEM: Quadrant lower"
    # nothing of the handler's forward end stands in the D's way: the top pulley and its brackets stay under the D's
    # underside (and its A&R eye) while it rolls on
    hd = S.quadrant_info["handler_asm"]
    hinge_z = p.rail_z - rt.HANDLER_RAIL_TOP
    pc = np.array(hd.info["pulley_centre"])
    assert pc[2] + hd.info["pulley_r"] + 1.25 * p.quadrant_rope_d / 2 < lane["low_z"] - hinge_z - 50.0
    assert pc[0] - hd.info["pulley_r"] > S.pos["handler_len"]


def test_ar_wire_hinge_sheave_gone_and_top_pulley(made):
    """Task 0095: the A&R wire is always on the D's eye at the top of its curve – the middle of the curve's outer edge,
    just outside the gutter's lip, under the gutter and above the D's underside. No sheave at the hinge, no slot in the
    stern turn. At the end of the tilt the wire comes from forward over the top pulley and hangs straight down from it
    to the eye (the D vertical, curve up); flat, the wire runs over the pulley without touching it."""
    from fresing_render.demo_model import deck as dk
    from fresing_render.demo_model import geom as g
    S, layout = made["S"], made["layout"]
    p = S.p
    names = {n.name for n, *_ in g.walk(S.root)}
    assert not names & {"HINGE SHEAVE", "SHEAVE CHEEK", "HANG-OFF PAD EYE"}
    quad = S.quadrant_info["quad_asm"]
    eye = np.array(quad.info["hang_off"])
    lip = p.quadrant_r + p.cable_r + 160.0
    assert eye[1] == 0.0 and lip < eye[0] < lip + 150.0                      # outside the lip, on the middle line
    assert dk.BOGIE_H + 100.0 < eye[2] < p.line_z - p.rail_z - p.cable_r - 10.0 - 40.0
    sheet = made["route"]
    W = sheet["wires"]["ar"]
    assert np.allclose(sheet["quadrant"]["hang_off"], W["eye"])
    # the tip turns about that point
    tip = next(j for j in made["joints"]["joints"] if j["name"] == "QUADRANT SYSTEM: Quadrant tip")
    assert np.linalg.norm(np.cross(np.array(tip["axis"]["point"]) - W["eye"], tip["axis"]["direction"])) < 1e-3
    # at the end of the tilt: straight down from the pulley's aft side to the eye
    th = math.radians(rt.TILT_END)
    tp = rt.top_pulley(p)
    z_h = p.rail_z - rt.HANDLER_RAIL_TOP
    P = layout._hinge_world(S.pos, z_h, tp["centre"], rt.TILT_END)
    E = layout._hinge_world(S.pos, z_h, tp["eye"], rt.TILT_END)
    X = layout._hinge_world(S.pos, z_h, tp["exit"], rt.TILT_END)
    assert np.linalg.norm(X - (P + [-tp["r"], 0.0, 0.0])) < 1e-6
    assert abs(E[0] - X[0]) < 1e-6 and E[2] < X[2] - 500.0
    # ... the D stands vertical there (its curve's axis along the handler's: up), the eye just below the pulley
    assert math.cos(th) < 0 and P[2] - E[2] < 2500.0
    # flat (D at the end of its travel) the line from the eye forward clears the pulley; it bears on it once tilted
    _L, on0 = layout.ar_wire_length(p, S.pos, np.array(W["drum_centre"])[[0, 2]], W["drum_r"], 0.0)
    _L, on20 = layout.ar_wire_length(p, S.pos, np.array(W["drum_centre"])[[0, 2]], W["drum_r"], 20.0)
    assert not on0 and on20
    # the stern turn has no slot in its web any more (a solid sector of revolution)
    st = S.handles["stern_turn"][-1].node
    rc = [c.node for c in st.children if c.node.name == "RADIUS CONTROLLER"][0]
    assert g.solids(rc.shape) == 1


def _points(made, prefix: str = "", names=None) -> np.ndarray:
    """Every mesh point (model mm) of the assembly's parts whose uid starts with ``prefix`` (and named one of
    ``names``)."""
    info, arrays = made["trees"]["assembly"]
    out = []
    for i, n in enumerate(info["nodes"]):
        if n["kind"] != "part" or not n["uid"].startswith(prefix) or (names and n["name"] not in names):
            continue
        W = _world(info, i)
        out.append((arrays[f"p{n['mesh']}"].astype(float) @ W[:3, :3].T + W[:3, 3]) * 1000.0)
    assert out, prefix
    return np.concatenate(out)


def _rot(point, direction, deg: float) -> np.ndarray:
    """A turn of ``deg`` about the axis (point, direction), right hand, as a 4x4 matrix (model mm)."""
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    a = math.radians(deg)
    K = np.array([[0, -d[2], d[1]], [d[2], 0, -d[0]], [-d[1], d[0], 0]])
    R = np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(point, float) - R @ np.asarray(point, float)
    return M


def _quadrant_pose(made, travel: float, tilt: float, lower: float, tip: float) -> np.ndarray:
    """Where the D's parts go (model mm) with the quadrant's joints at these values: the tip rides on the lowering,
    which rides on the travel, which rides on the handler's tilt (as the demo makes them)."""
    by = {j["name"]: j for j in made["joints"]["joints"]}
    tl, tv = by["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"], by["QUADRANT SYSTEM: Quadrant travel"]
    lw, tp = by["QUADRANT SYSTEM: Quadrant lower"], by["QUADRANT SYSTEM: Quadrant tip"]

    def slide(j, mm):
        M = np.eye(4)
        M[:3, 3] = np.array(j["axis"]["direction"]) * mm
        return M
    return (_rot(tl["axis"]["point"], tl["axis"]["direction"], tilt) @ slide(tv, travel) @ slide(lw, lower)
            @ _rot(tp["axis"]["point"], tp["axis"]["direction"], tip))


def test_quadrant_lower_points_straight_down_and_the_ar_winch_has_one_drum_turn(made):
    """Task 0082: 'Quadrant lower' lowers the D on its A&R wire straight down in the world once the handler has tilted
    it over the stern (to LOWER_TILT); it rides on the travel and the tip rides on it, so the D tips about its eye wherever
    it hangs. The A&R winch has one plain 'Drum turn' (its wire, a cable of the demo, turns it): 0095's step over the
    tilt and its coupling to the travel are gone. The sheet's hang tip puts the D's centre of mass under its eye."""
    from fresing_render.demo_model import geom as g
    S = made["S"]
    js = made["joints"]["joints"]
    by = {j["name"]: j for j in js}
    q = made["route"]["quadrant"]
    low = by["QUADRANT SYSTEM: Quadrant lower"]
    assert low["type"] == "slide" and low["limits"] == [0.0, made["layout"].LOWER_MAX]
    assert low["drive"]["by"] == "operator"
    assert low["parts"] == by["QUADRANT SYSTEM: Quadrant travel"]["parts"]
    assert low["parts"] == by["QUADRANT SYSTEM: Quadrant tip"]["parts"]
    assert np.allclose(low["axis"]["point"], q["hang_off"], atol=1e-3)
    tl = by["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]
    down = _rot([0, 0, 0], tl["axis"]["direction"], rt.LOWER_TILT)[:3, :3] @ np.array(low["axis"]["direction"])
    assert np.allclose(down, [0.0, 0.0, -1.0], atol=1e-6)
    assert q["lower_tilt"] == rt.LOWER_TILT and q["tilt_end"] == rt.TILT_END < rt.LOWER_TILT <= tl["limits"][1]
    # the A&R winch: one drum joint, driven on its own
    drums = [j for j in js if j["name"].startswith("QUADRANT SYSTEM: QUADRANT HANDLING WINCH:")]
    assert [j["name"] for j in drums] == ["QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn"]
    assert drums[0]["drive"]["by"] == "winch" and "rides_on" not in drums[0] and "follows" not in drums[0]["drive"]
    # hanging plumb: the centre of mass straight under the eye (and under it, not over it)
    quad = S.quadrant_info["quad_asm"]
    _v, c = g.mass_centre(quad)
    QD = g.path_matrix(np.eye(4), S.handles["quadrant_system"] + [S.quadrant_info["quadrant"]])
    P = _quadrant_pose(made, q["travel"][1], rt.LOWER_TILT, 10000.0, q["hang_tip"])
    com = (P @ QD @ np.r_[c, 1.0])[:3]
    eye = (P @ np.r_[q["hang_off"], 1.0])[:3]
    assert abs(com[0] - eye[0]) < 1.0 and abs(com[1] - eye[1]) < 1.0 and com[2] < eye[2] - 1000.0
    assert -30.0 < q["hang_tip"] < 0.0                    # its bar swings aft, away from the transom


def test_the_lowered_d_hangs_clear_of_the_stern(made):
    """Task 0082: the D, tilted over the stern to LOWER_TILT and hanging plumb from its eye (the sheet's hang tip), goes
    straight down past the transom, the horns' lower ends and the handler with room to spare (lowering moves it only
    down, so its place across is checked once; the handler's side: over its whole lowering)."""
    from fresing_render.demo_model import geom as g
    S = made["S"]
    q = made["route"]["quadrant"]
    D = _points(made, q["uid"] + "/")
    root = f"{made['layout'].ROOT}#1"
    hull = _points(made, g.path_uid(root, S.handles["vessel"]) + "/")
    by = {j["name"]: j for j in made["joints"]["joints"]}
    tl = by["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]
    Hi = np.linalg.inv(_rot(tl["axis"]["point"], tl["axis"]["direction"], rt.LOWER_TILT))
    hinge = np.array(tl["axis"]["point"])
    for lower in (0.0, 300.0, 1000.0, 5000.0, made["layout"].LOWER_MAX):
        P = _quadrant_pose(made, q["travel"][1], rt.LOWER_TILT, lower, q["hang_tip"])
        w = D @ P[:3, :3].T + P[:3, 3]
        # aft of the transom (the hull's aft end) by more than 0.4 m
        assert w[:, 0].max() < hull[:, 0].min() - 400.0, (lower, w[:, 0].max())
        # off the handler's rails: in the handler's own frame every point over its frame lies above the rail top
        h = w @ Hi[:3, :3].T + Hi[:3, 3] - hinge
        over = h[:, 0] < S.pos["handler_len"]
        assert h[over, 2].min() > rt.HANDLER_RAIL_TOP + 50.0, (lower, h[over, 2].min())
    # aft of the horns' lower ends (they reach 1.4 m aft of the transom) where the D's sides pass them
    P = _quadrant_pose(made, q["travel"][1], rt.LOWER_TILT, 0.0, q["hang_tip"])
    w = D @ P[:3, :3].T + P[:3, 3]
    for key in ("horn_A", "horn_B"):
        H = _points(made, g.path_uid(root, S.handles[key]) + "/")
        band = (w[:, 1] > H[:, 1].min() - 100.0) & (w[:, 1] < H[:, 1].max() + 100.0)
        assert band.any() and w[band, 0].max() < H[:, 0].min() - 100.0, (key, w[band, 0].max(), H[:, 0].min())


def test_the_quadrant_operations_wires_in_the_cad_pose(made):
    """Task 0082: the A&R wire (A&R WIRE) from where it leaves its drum's top to the D's eye; the tipping wires
    (TIPPING WIRE) from the swivel post's top up its axis, over the head sheave's groove and on to the D's pad eye at
    the bar's end – the D at its stationary place. Smooth (a bend for the fleet angle off the head sheave), and the
    solids lie on them."""
    S = made["S"]
    p = S.p
    sheet = made["route"]
    W = sheet["wires"]
    ropes = S.quadrant_info["ropes"]
    ar = ropes["A&R wire"]
    c = np.array(W["ar"]["drum_centre"])
    st = ar.segments[0].start
    assert abs(math.hypot(st[0] - c[0], st[2] - c[2]) - W["ar"]["drum_r"]) < 1e-3
    assert np.linalg.norm(ar.end - W["ar"]["eye"]) < 1e-3
    for key in ("port", "stb"):
        r = ropes[f"tipping wire {key} (to the D)"]
        w = W[f"tipping_{key}"]
        assert np.linalg.norm(r.segments[0].start - w["lead_start"]) < 1e-3
        assert np.allclose(r.segments[0].tangent(), [0.0, 0.0, 1.0])                  # up the post's axis
        arc = r.segments[1]
        assert arc.kind == "arc" and np.linalg.norm(arc.centre - w["head_centre"]) < 1e-3
        assert abs(arc.radius - w["head_r"]) < 1e-3 and 0.0 < math.degrees(arc.angle) < 180.0
        assert np.linalg.norm(r.end - w["eye"]) < 1e-3
        assert all(gap < 1e-6 and ang < 1e-4 for gap, ang in r.joins()), r.joins()
    info, arrays = made["trees"]["assembly"]
    want = {"A&R WIRE": [ar], "TIPPING WIRE": [ropes["tipping wire port (to the D)"],
                                               ropes["tipping wire stb (to the D)"]]}
    seen = {k: 0 for k in want}
    for i, n in enumerate(info["nodes"]):
        if n["kind"] != "part" or n["name"] not in want:
            continue
        W_ = _world(info, i)
        pts = (arrays[f"p{n['mesh']}"].astype(float) @ W_[:3, :3].T + W_[:3, 3]) * 1000.0
        d = min((r.distance(pts) for r in want[n["name"]]), key=lambda x: float(np.max(np.abs(x - x.mean()))))
        rr = p.quadrant_rope_d / 2 if n["name"] == "A&R WIRE" else p.tipping_rope_d / 2
        assert np.max(np.abs(d - rr)) < 1.0, n["uid"]
        seen[n["name"]] += 1
    assert seen == {"A&R WIRE": 1, "TIPPING WIRE": 2}


def test_the_second_end_and_its_cps(made):
    """Task 0082: the cable's second end (CABLE END) from the D's lane-B bar end round the whole gutter, aft along side
    A, over horn A into the sea – the main route's segments from the gutter on; its CPS set lies straight along side B aft
    of the bar end with its pull head's nose at the bar end."""
    S = made["S"]
    p = S.p
    se = made["route"]["second_end"]
    main, r = S.routes["main"], S.routes["second_end"]
    nose = np.array(se["pull_head_nose"])
    assert np.allclose(r.segments[0].start, nose) and np.allclose(nose, [S.pos["quadrant_x"], p.lane_y, p.line_z])
    assert r.segments[0].kind == "arc" and math.degrees(r.segments[0].angle) == pytest.approx(180.0)
    assert r.segments[0].radius == pytest.approx(p.quadrant_r)
    assert np.allclose(r.end, main.end) and r.length < main.length
    assert se["route"]["length"] == pytest.approx(r.length, abs=1e-3)
    uids = {n["uid"]: n for n in made["trees"]["assembly"][0]["nodes"]}
    assert uids[se["solid"]]["name"] == "CABLE END" and se["cps"] in uids
    cps = _points(made, se["cps"] + "/")
    R0 = se["cps_outer_radius"]
    assert np.abs(cps[:, 1] - nose[1]).max() < 1.05 * R0 and np.abs(cps[:, 2] - nose[2]).max() < 1.05 * R0
    assert nose[0] <= cps[:, 0].max() < nose[0] + 0.5 * R0               # (the pull head's eye ring before its nose)
    assert cps[:, 0].min() == pytest.approx(nose[0] - se["cps_length"], abs=R0)
    head = _points(made, se["cps"] + "/", {"PULL HEAD"})
    assert nose[0] <= head[:, 0].max() < nose[0] + 0.5 * R0 and head[:, 0].min() > nose[0] - 1500.0


def test_the_rails_clear_the_lay_cable(made):
    """Tasks 0084, 0082: the quadrant's rails (girders, trestles, the handler's rails) stay at least 10 cm from the lay
    cable; the D's bogies and rail wheels too, all along its travel."""
    S = made["S"]
    p = S.p
    C = S.routes["main"].sample(50.0)
    info, arrays = made["trees"]["assembly"]
    q = made["route"]["quadrant"]

    def boxes(names, prefix=""):
        out = []
        for i, n in enumerate(info["nodes"]):
            if n["kind"] == "part" and n["name"] in names and n["uid"].startswith(prefix):
                W = _world(info, i)
                pts = (arrays[f"p{n['mesh']}"].astype(float) @ W[:3, :3].T + W[:3, 3]) * 1000.0
                out.append((n["uid"], pts.min(axis=0), pts.max(axis=0)))
        return out

    def gap(lo, hi):
        return float(np.linalg.norm(np.maximum(np.maximum(lo - C, 0.0), C - hi), axis=1).min()) - p.cable_r
    fixed = boxes({"QUADRANT RAIL", "RAIL TRESTLE"})
    assert len(fixed) >= 10
    worst = min((gap(lo, hi), u) for u, lo, hi in fixed)
    assert worst[0] >= 100.0 - 0.01, worst
    moving = boxes({"RAIL BOGIE", "RAIL WHEEL"}, q["uid"] + "/")
    assert len(moving) >= 8
    worst = min((gap(lo - [s, 0, 0], hi - [s, 0, 0]), u, s) for s in np.arange(0.0, q["travel"][1] + 1.0, 250.0)
                for u, lo, hi in moving)
    assert worst[0] >= 100.0, worst


def test_tipping_wires_up_the_swivel_posts_to_the_bar_ends(made):
    """Task 0095: each tipping wire comes from its winch under a foot sheave and up the swivel post's axis (fixed part),
    so the head can swivel to any side; the head points at the D's tipping eye when the D comes onto the handler and
    follows the tilt. The tipping eyes sit at the ends of the straight bar: the D's bottom corners when it stands
    vertical at the end of the tilt."""
    S = made["S"]
    p = S.p
    quad = S.quadrant_info["quad_asm"]
    bar_y = quad.info["bar_y"]
    sheet = made["route"]["wires"]
    by = {j["name"]: j for j in made["joints"]["joints"]}
    for key, sy in (("port", 1.0), ("stb", -1.0)):
        e = np.array(quad.info["eyes"][f"tipping_{key}"])
        assert sy * e[1] > 0 and bar_y < abs(e[1]) < bar_y + 500.0 and -600.0 < e[0] < 0.0       # the bar's end
        w = sheet[f"tipping_{key}"]
        # vertical at the end of the tilt: the eye is the lowest corner of the D (the bar's end), aft of the transom
        assert w["eye_tilted"][0] < 0.0 and w["eye_tilted"][2] < p.deck_z + 1500.0
        # the fixed wire ends on the post's axis, inside the swivel bearing; the head sheave's wire meets the axis
        axis = np.array(w["post_axis"])
        assert np.allclose(np.array(w["lead_start"])[:2], axis[:2])
        hc = np.array(w["head_centre"])
        assert np.linalg.norm((hc - w["head_r"] * np.array(w["head_x"]))[:2] - axis[:2]) < 0.05
        # the head points at the eye when the D comes on, and at the end of the tilt (the swivel follows the tilt)
        sw = by[f"QUADRANT SYSTEM: Swivel sheave {key} swivel"]
        assert sw["drive"]["follows"] == "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"
        az = lambda v: math.degrees(math.atan2(v[1], v[0]))  # noqa: E731
        assert az(w["head_x"]) == pytest.approx(az(np.array(w["eye_on_handler"]) - axis), abs=0.02)
        turned = az(w["head_x"]) + sw["drive"]["ratio"] * rt.TILT_END
        assert turned == pytest.approx(az(np.array(w["eye_tilted"]) - axis), abs=0.02)
    # the fixed part: one WIRE ROPE per side under the quadrant system; the wire on to the D: one TIPPING WIRE per side
    # (task 0082, the demo makes it an app cable)
    qs = S.handles["quadrant_system"][-1].node
    assert len([c for c in qs.children if c.node.name == "WIRE ROPE"]) == 2
    assert len([c for c in qs.children if c.node.name == "TIPPING WIRE"]) == 2
    for key in ("port", "stb"):
        r = S.quadrant_info["ropes"][f"tipping wire {key}"]
        names = [i.get("name") for i in r.info if i.get("support") == "sheave"]
        assert names == ["foot sheave"]
        assert r.segments[-1].end_tangent[2] == pytest.approx(1.0)                  # up the post's axis


def test_engine_on_the_lower_path_and_handling_winches_on_the_tensioner_lines(made):
    """Task 0095: the cable engine on the lower path just forward of tensioner 2, its wheels on the cable (rollers fill
    its old place on side B); the two handling winches forward, one each side of the A&R winch, each drum's middle on
    a tensioner's line, the wire leading aft along that lane at the cable's height, 80 % of the old drum."""
    from fresing_render.demo_model import geom as g
    S = made["S"]
    p, pos = S.p, S.pos
    W = g.path_matrix(np.eye(4), S.handles["cable_engine"])
    assert np.allclose(W[:3, 3], [pos["engine_x"], pos["lower_y"], p.low_z])
    ce = S.handles["cable_engine"][-1].node
    assert ce.info["wheel_r"] + p.cable_r + 180.0 <= p.low_z - p.deck_z + 1e-6
    # side B's highway has cradles where the engine stood (between the rise and tensioner 1)
    main = S.routes["main"]
    from fresing_render.demo_model.layout import _where
    xs = [_where(main, s)[1] for s in S.stations["highway"]]
    x_rise = pos["rise_x"] + 2 * p.bend_r * math.sin(math.radians(pos["rise_deg"]))
    on_b = [q for q in xs if abs(q[1] - p.lane_y) < 1 and x_rise < q[0] < pos["tensioners"][0] - rt.TENSIONER_HALF]
    assert len(on_b) >= 2
    for k, sy in ((1, -1.0), (2, 1.0)):
        Wk = g.path_matrix(np.eye(4), S.handles[f"handling_winch_{k}"])
        hw = S.handles[f"handling_winch_{k}"][-1].node
        mid = Wk @ np.r_[hw.info["drum_centre"], 1.0]
        assert mid[1] == pytest.approx(sy * p.lane_y)                             # on the tensioner's line
        assert abs(mid[0] - pos["qh_winch_x"]) < 600.0                            # beside the A&R winch
        assert hw.info["first_layer_rc"] == pytest.approx(480.0) and hw.info["groove"] == "lebus"
        fl = Wk @ np.r_[hw.info["fairlead"]["centre"], 1.0]
        assert fl[0] < mid[0] - 1000.0 and fl[1] == pytest.approx(mid[1])         # the wire leads aft
        top = Wk @ np.r_[hw.info["rope_top"], 1.0]
        assert top[2] == pytest.approx(p.line_z)                                  # at the cable's height
        assert pos["quadrant_apex_x"] < Wk[0, 3] - 2500.0 < Wk[0, 3] + 1500.0 < pos["carousel_x"] - pos["well_r"]


def test_carousel_coil_layers_and_cable_end_through_the_core(made):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    p = Params()
    S = made["S"]
    car = S.handles["carousel"][-1].node
    coil = car.info["coil"]
    assert coil["layers"] == p.coil_layers and coil["top_z"] == pytest.approx(p.turntable_t + p.coil_layers * p.cable_d)
    # the cable's end: along the core, through the hole at its foot, into the clamp inside the core
    end = S.routes["core_end"]
    c = np.array([S.pos["carousel_x"], 0.0])
    rho_end = np.hypot(*(end.end[:2] - c))
    assert rho_end < p.core_r - 300.0
    assert end.segments[0].start[2] == pytest.approx(p.turntable_t + p.cable_r)
    shapes = _shapes(S)
    holes = []
    ex = TopExp_Explorer(shapes["INNER CORE"], TopAbs_FACE)
    while ex.More():
        a = BRepAdaptor_Surface(TopoDS.Face(ex.Current()))
        if a.GetType() == GeomAbs_SurfaceType.GeomAbs_Cylinder and abs(a.Cylinder().Radius() - 0.7 * p.cable_d) < 0.1:
            holes.append(a)
        ex.Next()
    assert holes, "no hole at the foot of the core"
    # the coil shows its layers: notches on the outer face between layers
    n_faces = 0
    ex = TopExp_Explorer(shapes["CABLE COIL"], TopAbs_FACE)
    while ex.More():
        n_faces += 1
        ex.Next()
    assert n_faces >= 4 * p.coil_layers


def test_quay_file(made):
    """demo_quay_loading.step: the quay, the storage carousel, the quay tower with its arch, the cable from the
    storage carousel onto side A's highway; placed for the vessel moored starboard side to (model coordinates)."""
    info, arrays = made["trees"]["quay_loading"]
    names = {n["name"] for n in info["nodes"]}
    for want in ("QUAY SLAB", "QUAY FENDER", "BOLLARD", "STORAGE CAROUSEL", "QUAY LOADING TOWER", "LOADING ARCH",
                 "CABLE", "BOARDING RADIUS CONTROLLER", "ROLLER CRADLE"):
        assert want in names, want
    q = made["route"]["quay"]
    p = Params()
    assert q["edge_y"] < -p.beam / 2
    assert q["storage_carousel_centre"][1] < q["edge_y"] and q["tower"][1] < q["edge_y"]
    js = made["joints"]["machine_files"]["demo_quay_loading.step"]
    jn = {j["name"] for j in js}
    assert "QUAY LOADING TOWER: Arch slew" in jn and "STORAGE CAROUSEL: Carousel turn" in jn


def test_big_files_are_not_in_the_repository():
    for name in ("demo_cable_lay.step", "demo_vessel.step", "demo_drum_lebus.step", "demo_quay_loading.step"):
        for folder in ("tests/data", "fresing_render/data"):
            assert not os.path.exists(os.path.join(ROOT, folder, name))


def test_every_turning_roller_turns_about_its_own_axis():
    """Task 0097: every roller joint of the demo (the two side rollers of every highway cradle included) turns about
    the roller's long direction (< 0.5°). The cradles' joints once took the cable's contact point along the axle for
    the lever arm, which tilted the axis 63° and made them wobble through the cable."""
    from fresing_render.demo_model import geom as g, layout
    S = layout.build()
    places = {uid: M for _node, uid, M, _label, _path in g.walk(S.root)}
    n = 0
    for j in g.resolve_joints(S.root):
        if j["type"] != "rotate" or "oller" not in j["name"] or len(j["parts"]) != 1:
            continue
        long_dir = places[j["parts"][0]][:3, :3] @ np.array([0.0, 1.0, 0.0])
        long_dir /= np.linalg.norm(long_dir)
        d = np.asarray(j["axis"]["direction"], float)
        d /= np.linalg.norm(d)
        assert math.degrees(math.acos(min(1.0, abs(long_dir @ d)))) < 0.5, j["name"]
        n += 1
    assert n >= 230 and sum(1 for j in g.resolve_joints(S.root) if j["name"].startswith("CRADLE")
                            and "Roller" in j["name"]) == 2 * len(S.stations["highway"]) >= 40


# ---------------------------------------------------------------------------------------------------------
# Task 0081: handling winch fleet angle (level wind), the D's gutter rollers over the cable sizes
# ---------------------------------------------------------------------------------------------------------

FLEET_LIMIT = 1.5                     # degrees: the app's warning limit (spiral groove / Lebus practice)


def _fleet(hw: dict, shift: float = 0.0):
    """The fleet angles (deg, at the a_lo and a_hi flange) of a handling winch from the route sheet, with the formula
    the app uses (``core.spool.fleet_angles``): the rope from the top layer's middle at each flange to where it meets
    the fairlead sheave's groove – moved ``shift`` mm along the drum's axis (the level wind's travel). Also gives where
    that point lies along the axis (mm from the drum's middle)."""
    from fresing_render.core import spool as SP
    d = hw["rope_d"]
    lo, hi = hw["flange_faces"]
    sp = SP.Spool(kind=SP.DRUM, d=d / 1000.0, r1=hw["first_layer_rc"] / 1000.0, a_lo=lo / 1000.0, a_hi=hi / 1000.0,
                  pitch=hw["pitch"] / 1000.0, r_max=(hw["flange_r"] - d / 2.0) / 1000.0,
                  groove=SP.LEBUS if hw["groove"] == "lebus" else SP.SPIRAL)
    path = SP.wind(sp)
    ax = np.array(hw["drum_axis"])
    rel = np.array(hw["fairlead_groove_top"]) - np.array(hw["drum_centre"])
    along = float(rel @ ax)
    across = float(np.linalg.norm(rel - along * ax))
    q = np.array([across, 0.0, along + shift]) / 1000.0           # the spool frame: z along the drum's axis
    return [math.degrees(a) for a in SP.fleet_angles(path, q)], along


def test_handling_winch_fleet_angle_with_its_level_wind(made):
    """Task 0081 (0080's follow-up): the app warned of a 20.9° fleet angle on handling winch 1 – its fairlead sheave
    stood 0.9 m from the flange. For 1.5° the sheave would have to stand ~23 m from the 1.28 m drum; aft of the winch
    the D-quadrant rests ~2.6 m away (its curve over the lane) and forward lies the carousel's well, so the sheave rides
    on a level wind instead: a carriage across the drum ("Level wind", a slide joint along the drum's axis) carries the
    sheave (its turn rides on it) and the hanging end's shackle. With the carriage over the wrap being paid out, the
    fleet angle at both flanges is ~0° (the app makes the joint follow the layer, ACROSS)."""
    by = {j["name"]: j for j in made["joints"]["joints"]}
    winches = made["route"]["handling_winches"]
    assert [w["name"] for w in winches] == ["HANDLING WINCH 1", "HANDLING WINCH 2"]
    for hw in winches:
        before, along = _fleet(hw)
        assert min(before) > 20.0 and max(before) < 22.0, before          # with the sheave standing still: ~20.9°
        lw = by[hw["level_wind"]["joint"]]
        assert lw["type"] == "slide" and lw["drive"]["by"] == "winch"
        assert abs(abs(float(np.dot(lw["axis"]["direction"], hw["drum_axis"]))) - 1.0) < 1e-6    # across the drum
        assert by[hw["name"] + ": Fairlead sheave turn"]["rides_on"] == lw["name"]
        sheave = next(s for s in made["route"]["sheaves"] if s["name"].endswith(f"(handling winch {hw['name'][-1]})"))
        assert sheave["uid"].startswith(lw["parts"][0] + "/")                # the sheave is on the carriage
        assert abs(float(np.dot(np.array(sheave["centre"]) - np.array(hw["drum_centre"]), hw["drum_axis"]))) < 1e-6
        lo, hi = hw["flange_faces"]
        d = hw["rope_d"]
        sign = float(np.dot(lw["axis"]["direction"], hw["drum_axis"]))
        for k, a_end in enumerate((lo + d / 2.0, hi - d / 2.0)):
            travel = (a_end - along) * sign                                 # the carriage over that flange's wrap
            assert lw["limits"][0] - 1e-6 <= travel <= lw["limits"][1] + 1e-6, (hw["name"], travel)
            after, _ = _fleet(hw, a_end - along)
            assert after[k] <= FLEET_LIMIT and after[k] < 0.01, (hw["name"], k, after)


def _roller_gaps(p, quad, cache) -> np.ndarray:
    """Each gutter roller's gap to the cable round the D's curve (mm; 0 = touching): the roller's outer face (a vertical
    cylinder from its bottom to its flange) against the cable's circle (radius ``quadrant_r`` at the cable's height), in
    the vertical plane through the roller's axis."""
    from fresing_render.demo_model import deck as dk
    zc = dk.d_shape(p)["zc"]
    gaps = []
    for c in quad.children:
        if c.node.name != "GUIDE ROLLER":
            continue
        v = _mesh_points(c.node.shape, cache, 0.5) @ c.M[:3, :3].T + c.M[:3, 3]
        ctr = c.M[:2, 3]
        lo, hi = v[:, 2].min(), v[:, 2].max()
        rr = np.hypot(*(v[:, :2] - ctr).T)[v[:, 2] < lo + 20.0].max()
        dz = 0.0 if lo <= zc <= hi else min(abs(lo - zc), abs(hi - zc))
        gaps.append(math.hypot(p.quadrant_r - (np.hypot(*ctr) + rr), dz) - p.cable_r)
    return np.array(gaps)


@pytest.mark.parametrize("d", [50.0, 60.0, 80.0, 120.0, 140.0, 170.0, 200.0, 500.0])
def test_the_ds_gutter_rollers_reach_the_cable(d):
    """Task 0081 (0102's open point): the D's gutter rollers hang from its top plate and end at ``band_z`` – 30 mm over
    the tensioners' bottom pads, which the D's ends pass over. For a small cable the pads' V edges stood higher than the
    cable's centre (a 40 mm deep V), so the rollers ended up to 45 mm above it and could not reach it. The pads' V now
    follows the cable Ø (a tensioner's pads are made for its cable): the rollers touch the cable from Ø 80 up and clear
    a Ø 50–60 cable by under 2 mm; no roller stands in the cable. Nothing of the D outside ``inner`` is lower than
    ``band_z`` (its outer lip used to reach the cable's centre for every cable: into the pads' V at Ø 50)."""
    pytest.importorskip("OCP")
    from fresing_render.demo_model import deck as dk
    from fresing_render.demo_model import geom as g
    from fresing_render.demo_model import machines as m
    p = Params(cable_d=d)
    ds = dk.d_shape(p)
    assert ds["band_z"] - ds["zc"] >= m.pad_top(p) + 30.0 - 1e-9                 # 30 mm over the pads (0102)
    wide = m.PAD_V_WIDE * p.cable_r / math.tan(p.pad_v_half_angle)
    assert m.pad_v_depth(p) >= min(m.PAD["v_depth"], wide) - 1e-9                # still cradles the cable
    if d >= 170.0:
        assert m.pad_v_depth(p) == m.PAD["v_depth"]                             # big cables: the 0084 pads
    quad = dk.quadrant_d(p, m.Kit(p))
    cache: dict = {}
    gaps = _roller_gaps(p, quad, cache)
    assert len(gaps) == 25 and (gaps >= -0.05).all(), gaps
    assert (gaps < (0.05 if d >= 80.0 else 2.0)).all(), gaps                    # touching / just clear
    for node, _uid, W, _label, _path in g.walk(quad):
        if not isinstance(node, g.Part) or node.name not in ("QUADRANT GUTTER", "GUIDE ROLLER"):
            continue                                    # (a small D's bogies stand outside ``inner``: on the rails)
        v = _mesh_points(node.shape, cache) @ W[:3, :3].T + W[:3, 3]
        out = np.abs(v[:, 1]) > ds["inner"] + 1.0
        assert (v[out, 2] >= ds["band_z"] - 0.5).all(), (d, node.name, float(v[out, 2].min() - ds["band_z"]))


@pytest.fixture(scope="module")
def small_and_big():
    """The whole model (not written) for the owner's smallest and biggest cable: ~40 s each."""
    pytest.importorskip("OCP")
    from fresing_render.demo_model import layout
    return {d: layout.build(Params(cable_d=d), with_lebus=False) for d in (50.0, 500.0)}


@pytest.mark.parametrize("d", [50.0, 500.0])
def test_the_d_quadrants_way_is_clear_for_the_smallest_and_biggest_cable(small_and_big, d):
    """Task 0081: the D's sweep (0102's check, made at Ø 200) at the ends of the owner's range: with the tensioners open
    and the lanes' cradles dropped nothing stands in the room the D sweeps (at Ø 500 the CPS slide's end reached into
    it: the slide now ends where its trough clears the room), and the gutter rollers reach the cable."""
    S = small_and_big[d]
    assert _in_the_ds_way(S) == []
    gaps = _roller_gaps(S.p, S.quadrant_info["quadrant"].node, {})
    assert (gaps >= -0.05).all() and (gaps < (0.05 if d >= 80.0 else 2.0)).all(), gaps
