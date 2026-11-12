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
    assert r.min_radius() >= p.mbr
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
             "side B rise", "side B", "side B bend", "quadrant gutter", "side A bend", "side A", "horn A"]
    it = iter(names)
    assert all(any(n == want for n in it) for want in order), names
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
    assert pos["tensioners"][0] + rt.TENSIONER_HALF < pos["cps_join_x"] < pos["s_bend_x"] < pos["quadrant_x"]
    assert pos["quadrant_apex_x"] < pos["qh_winch_x"] - rt.WINCH_HALF
    assert pos["qh_winch_x"] + rt.WINCH_HALF < pos["carousel_x"] - pos["well_r"]
    # the D passes between the side lanes' tensioners on its way aft
    assert p.quadrant_r + p.cable_r + 160.0 < p.lane_y - rt.TENSIONER_WIDTH
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
    assert count("ROLLER CRADLE") >= 25 and count("ROLLER TRESTLE") >= 25 and count("GRATING WALKWAY") >= 3
    assert count("CABLE ENGINE WHEEL") == 8
    assert count("QUADRANT GUTTER") == 1 and count("RAIL BOGIE") == 4 and count("QUADRANT RAIL") >= 4
    assert count("HANDLER FRAME") == 1 and count("CHUTE") == 2                     # horns A and B
    assert count("HINGE SHEAVE") == 0 and count("SHEAVE CHEEK") == 0 and count("CRADLE LIFT FRAME") >= 4
    assert count("A&R PAD EYE") == 1 and count("PAD EYE") == 2 and count("FOOT SHEAVE") == 2
    assert count("PULL HEAD") == 5 and count("CPS RACK") == 1 and count("CPS RAMP") == 1 and count("CPS SLIDE") == 1
    assert count("CABLE") == 1 and count("CABLE END") == 1 and count("CABLE COIL") == 1
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
    assert len(S.stations["lower path"]) >= 15 and len(S.stations["highway"]) >= 25 and total >= 45


def test_cable_solid_follows_the_route(made):
    """The static CABLE (oval), the CABLE END at the core and the quay's CABLE lie on their routes within 1 mm."""
    S = made["S"]
    p = Params()
    for key, routes in (("assembly", {"CABLE": S.routes["main"], "CABLE END": S.routes["core_end"]}),
                        ("quay_loading", {"CABLE": S.routes["quay_loading"]})):
        info, arrays = made["trees"][key]
        routes = dict(routes)
        for i, n in enumerate(info["nodes"]):
            if n["kind"] != "part" or n["name"] not in routes:
                continue
            pts = arrays[f"p{n['mesh']}"].astype(float)
            W = _world(info, i)
            world = (pts @ W[:3, :3].T + W[:3, 3]) * 1000.0             # m -> mm
            d = routes[n["name"]].distance(world[:: max(1, len(world) // 20000)])
            assert np.max(np.abs(d - p.cable_r)) < 1.0, (key, n["name"])
            routes.pop(n["name"])
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
    p = Params()
    joints = {j["name"]: j for j in made["joints"]["joints"]}
    for k, hinge_dir in ((1, 1.0), (2, -1.0)):
        lift = joints[f"TENSIONER {k}: Top track lift"]
        tilt = joints[f"TENSIONER {k}: Top track tilt"]
        assert lift["type"] == "slide" and tilt["type"] == "rotate"
        assert np.allclose(lift["axis"]["direction"], [0, 0, 1], atol=1e-6)
        lo, hi = lift["limits"]
        assert lo <= -(p.squeeze_h() - p.squeeze_h(50.0)) + 1e-6
        assert hi >= p.squeeze_h(500.0) - p.squeeze_h() + 500.0
        assert tilt["rides_on"] == f"TENSIONER {k}: Top track lift"
        assert tilt["limits"][0] == 0.0 and tilt["limits"][1] >= 20.0
        # the hinge lies at the tensioner's aft end (smaller x) in both lanes
        centre = [t for t in made["route"]["tensioners"] if t["name"] == f"TENSIONER {k}"][0]["centre"]
        assert tilt["axis"]["point"][0] < centre[0] - 1500.0
        # a positive tilt lifts the forward end: the axis is -y (forward end x>0: x -> z)
        assert np.allclose(tilt["axis"]["direction"], [0, -1, 0], atol=1e-6)
        assert set(tilt["parts"]) < set(lift["parts"]) or tilt["parts"][0].startswith(lift["parts"][0])


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
            "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn on tilt",
            "QUADRANT SYSTEM: Swivel sheave port foot sheave turn",
            "QUADRANT SYSTEM: QUADRANT: Quadrant gutter roller 1 turn", "QUADRANT SYSTEM: QUADRANT: Rail wheel 1 turn",
            "HANDLING WINCH 1: Drum turn", "HANDLING WINCH 2: Fairlead sheave turn", "HORN A: Chute roller 1 turn",
            "CABLE ENGINE: Bottom wheel 1 turn", "CABLE ENGINE: Cable engine squeeze",
            "STERN RADIUS CONTROLLER: Stern turn roller 1 turn", "CRADLE 1: Roller port turn",
            "Lower path roller 1 turn"]
    for w in want:
        assert w in names, w
    by = {j["name"]: j for j in joints}
    assert by["QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"]["limits"] == [0.0, 100.0]
    assert by["QUADRANT SYSTEM: QUADRANT: Rail wheel 1 turn"]["drive"]["follows"] == "QUADRANT SYSTEM: Quadrant travel"
    assert by["QUADRANT SYSTEM: Quadrant tip"]["rides_on"] == "QUADRANT SYSTEM: Quadrant travel"
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
    """Task 0091: the D-quadrant's way aft is free. The S-bend's cradles in its lane drop out of the way (one joint, the
    others follow it), every other cradle stands outside the lane; the travel rides on the handler's tilt (the tip on
    the travel); the handling wire runs low under the D to a sheave on the hinge axis and along the handler's frame
    (that part tilts with it); nothing of the handler's forward end stands in the D's way."""
    from fresing_render.demo_model import deck as dk
    from fresing_render.demo_model import geom as g
    S, layout = made["S"], made["layout"]
    p = S.p
    lane = layout.d_lane(p)
    joints = made["joints"]["joints"]
    by = {j["name"]: j for j in joints}
    drops = [j for j in joints if j["name"].endswith(" drop")]
    assert len(drops) == len(S.stations["lifting"]) >= 4
    lead = [j for j in drops if j["drive"]["by"] == "operator"]
    assert len(lead) == 1
    for j in drops:
        assert j["type"] == "slide" and j["axis"]["direction"] == [0.0, 0.0, -1.0]
        assert j is lead[0] or (j["drive"]["follows"] == lead[0]["name"] and j["drive"]["ratio"] == 1.0)
        # dropped, the cradle's top is below the D's underside
        assert j["axis"]["point"][2] + dk.LIFT_TOP - j["limits"][1] < lane["low_z"] - 50.0
        assert abs(j["axis"]["point"][1]) < lane["half_width"] + 700.0
    # the other highway cradles stand clear of the lane
    for node, _uid, W, label, _path in g.walk(S.root):
        if label.startswith("CRADLE ") and node.name == "ROLLER CRADLE":
            corners = np.array([[x, y, z, 1.0] for x in (-310.0, 310.0) for y in (-640.0, 640.0)
                                for z in (-460.0, dk.LIFT_TOP)]) @ W.T
            assert np.abs(corners[:, 1]).min() >= lane["half_width"], label
    assert by["QUADRANT SYSTEM: Quadrant travel"]["rides_on"] == "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"
    assert by["QUADRANT SYSTEM: Quadrant tip"]["rides_on"] == "QUADRANT SYSTEM: Quadrant travel"
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


def test_ar_drum_pays_out_with_the_travel_and_the_tilt(made):
    """Task 0095: the A&R drum's 'Drum turn' follows the D's travel (mm of wire per mm of travel) and rides on 'Drum turn
    on tilt', which the demo turns with one SMOOTH step over the tilt: the step follows the wire's real payout within
    2 % of the payout over the tilt (a coupling to the tilt angle would be 16 % off: the wire bears on the pulley only
    from ~10°)."""
    S, layout = made["S"], made["layout"]
    p = S.p
    by = {j["name"]: j for j in made["joints"]["joints"]}
    drum = by["QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn"]
    on_tilt = by["QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn on tilt"]
    W = made["route"]["wires"]["ar"]
    assert drum["drive"]["follows"] == "QUADRANT SYSTEM: Quadrant travel"
    assert drum["drive"]["ratio"] == pytest.approx(360.0 / (2 * math.pi * W["drum_r"]), rel=1e-6)
    assert drum["rides_on"] == on_tilt["name"] and on_tilt["drive"]["by"] == "winch"
    assert np.allclose(drum["axis"]["direction"], on_tilt["axis"]["direction"])
    # travel: the wire's length (from the drum's top) grows about mm for mm (the eye moves aft level)
    D = np.array(W["drum_centre"])[[0, 2]]

    def length(e):
        q = rt.tangent_to_point(D, W["drum_r"], +1, e)
        return W["drum_r"] * (math.atan2(q[1] - D[1], q[0] - D[0]) - math.pi / 2) + np.linalg.norm(e - q)
    paid = length(np.array(W["eye_end"])[[0, 2]]) - length(np.array(W["eye"])[[0, 2]])
    assert paid == pytest.approx(W["travel"], rel=0.01)
    # tilt: the step against the real payout
    L = lambda t: layout.ar_wire_length(p, S.pos, D, W["drum_r"], t)[0]  # noqa: E731
    total = L(rt.TILT_END) - L(0.0)
    assert on_tilt["drive"]["payout_mm"] == pytest.approx(total, abs=1.0)
    k = on_tilt["drive"]["step_from"]
    ss = np.linspace(0.0, 1.0, 41)
    smooth = lambda q: (1 - np.cos(np.pi * q)) / 2  # noqa: E731
    for s in ss:
        th = rt.TILT_END * smooth(s)
        step = total * smooth(min(1.0, max(0.0, (s - k) / (1 - k))))
        assert abs(step - (L(th) - L(0.0))) < 0.02 * total, (s, th)


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
        assert sy * e[1] > 0 and bar_y - 200.0 < abs(e[1]) < bar_y and -600.0 < e[0] < 0.0        # the bar's end
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
    # the fixed part: one WIRE ROPE per side under the quadrant system (the moving parts are the demo's)
    qs = S.handles["quadrant_system"][-1].node
    assert len([c for c in qs.children if c.node.name == "WIRE ROPE"]) == 2
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
