"""The demo's wind park as the maker writes it (task 0166, ``fresing_render/demo_model/park.py``, ``turbine.py``,
``substation.py``): one solid per part, the joints, the blades turning clockwise seen from the front, every rotor facing
one wind, the first end's cable piece clear of the monopile, the scour rock and the seabed and meeting the app's laid
cable at the park's origin, turbine B beside the lay line with its J-tube towards it. No Blender."""

import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pytest.importorskip("OCP")

from fresing_render.demo_model import geom as g  # noqa: E402
from fresing_render.demo_model import park as pk  # noqa: E402
from fresing_render.demo_model import turbine as tb  # noqa: E402
from fresing_render.demo_model import turbine_parts as tp  # noqa: E402
from fresing_render.demo_model.params import ParkParams, Params  # noqa: E402


@pytest.fixture(scope="module")
def built():
    root, info = pk.build(Params(), ParkParams())
    return root, info, g.resolve_joints(root)


def test_every_part_is_one_solid(built):
    root, _info, _js = built
    seen = {}
    for node, *_ in g.walk(root):
        if isinstance(node, g.Part):
            seen[id(node)] = node
    bad = [p.name for p in seen.values() if g.solids(p.shape) != 1]
    assert not bad, bad
    assert not [p.name for p in seen.values() if not p.color]          # (a part without a colour reads uncoloured)
    names = [p.name for p in seen.values()]
    # nine turbines share their parts: one mesh each in the app
    assert len(seen) < 160 and g.count_parts(root) > 700, (len(seen), g.count_parts(root))
    for n in ("TOWER", "MONOPILE", "BLADE", "SPINNER", "NACELLE COVER", "TP SLEEVE", "SCOUR PROTECTION", "J-TUBE 1",
              "MARINE LIGHT", "AVIATION LIGHT", "JACKET LEG", "HELIDECK", "CLADDING", "DECK LIGHT", pk.CABLE_PIECE):
        assert n in names, n


def test_layout(built):
    _root, info, _js = built
    pp = ParkParams()
    ts = info["turbines"]
    assert len(ts) == pp.rows * pp.cols == 9 and len({t["name"] for t in ts}) == 9
    a = next(t for t in ts if t["role"] == "A")
    b = next(t for t in ts if t["role"] == "B")
    # A on the lay line behind the origin, B the next one along its row, b_off beside the lay line
    assert abs(a["xy"][1]) < 1.0 and -60000.0 < a["xy"][0] < -30000.0
    assert b["xy"][1] == pytest.approx(pp.b_off, abs=1.0)
    assert math.dist(a["xy"], b["xy"]) == pytest.approx(pp.along, abs=1.0)
    # the turbines 1.2 km / 1.5 km apart; none within 1 km of another; the substation between the rows
    xy = np.array([t["xy"] for t in ts])
    d = np.linalg.norm(xy[:, None] - xy[None], axis=2) + np.eye(9) * 1e9
    assert d.min() > 1.0e6
    s = np.array(info["substation"]["xy"])
    assert np.linalg.norm(xy - s, axis=1).min() > 6.0e5
    # A's J-tube points along the lay line (+x) towards the vessel, B's towards the lay line (+y: it is to starboard)
    assert np.allclose(a["bell_axis"][:2] / np.linalg.norm(a["bell_axis"][:2]), [1.0, 0.0], atol=1e-6)
    assert np.allclose(b["bell_axis"][:2] / np.linalg.norm(b["bell_axis"][:2]), [0.0, 1.0], atol=1e-6)
    # B's bell-mouth: the planned distance from the lay line is what b_end allows (the second end lies on it)
    assert abs(b["bell"][1]) < pp.b_end


def test_joints(built):
    _root, info, js = built
    by = {j["name"]: j for j in js}
    assert list(by)[0] == pk.SHIFT and by[pk.SHIFT]["type"] == "slide"
    assert np.allclose(by[pk.SHIFT]["axis"]["direction"], [1.0, 0.0, 0.0])
    assert len(js) == 1 + 2 * 9
    wind = ParkParams().wind_from
    up = np.array([math.sin(math.radians(wind)), math.cos(math.radians(wind))])         # towards the wind
    for t in info["turbines"]:
        yaw, rot = by[f"{t['name']}: Yaw"], by[f"{t['name']}: Rotor"]
        assert yaw["rides_on"] == pk.SHIFT and rot["rides_on"] == yaw["name"] and rot.get("motor") is True
        assert np.allclose(yaw["axis"]["direction"], [0, 0, 1]) and np.allclose(yaw["axis"]["point"][:2], t["xy"])
        dn = np.array(rot["axis"]["direction"])
        # the rotor's axis points downwind along the tilted shaft: every rotor faces the same wind
        assert dn[:2] / np.linalg.norm(dn[:2]) @ up == pytest.approx(-1.0, abs=1e-9)
        assert math.degrees(math.asin(-dn[2])) == pytest.approx(tb.TILT_DEG, abs=1e-3)
        # the hub sits upwind of the tower, at hub height
        hub = np.array(rot["axis"]["point"])
        assert (hub[:2] - t["xy"]) @ up == pytest.approx(abs(tb.HUB[1]), abs=1.0)
        assert hub[2] == pytest.approx(tb.HUB[2], abs=1.0)
    phases = [t["phase"] for t in info["turbines"]]
    assert len(set(round(p) for p in phases)) == 9                      # each rotor at its own phase


def test_blades_lead_a_clockwise_turn():
    """Seen from the front (upwind) the rotor turns clockwise = a positive turn about DOWN; each blade's leading edge
    (the round, thick end of the section, near the pitch axis) must face the way its blade then moves."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    blade = tb.blade()
    BRepMesh_IncrementalMesh(blade, 50.0, False, 0.3, True)
    from fresing_render.demo_model import occ
    pts = occ.mesh_points(blade) if hasattr(occ, "mesh_points") else None
    if pts is None:
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS
        out = []
        e = TopExp_Explorer(blade, TopAbs_FACE)
        while e.More():
            f = TopoDS.Face(e.Current()) if not hasattr(TopoDS, "Face_s") else TopoDS.Face_s(e.Current())
            tri = BRep_Tool.Triangulation_s(f, TopLoc_Location())
            if tri is not None:
                out += [[tri.Node(i).X(), tri.Node(i).Y(), tri.Node(i).Z()] for i in range(1, tri.NbNodes() + 1)]
            e.Next()
        pts = np.array(out)
    mid = pts[np.abs(pts[:, 2] - 60000.0) < 3000.0]
    # the chord lies along the blade frame's y: the leading edge 0.3 chord from the pitch axis, the trailing edge 0.7
    le_side = -1.0 if abs(mid[:, 1].min()) < abs(mid[:, 1].max()) else 1.0
    assert le_side == tb.LE_SIGN == -1.0
    for k in range(3):
        F = tb.blade_frame(120.0 * k)
        le = F[:3, :3] @ np.array([0.0, le_side, 0.0])
        r = F[:3, 2]
        moves = np.cross(tb.DOWN, r)                     # a positive turn about DOWN
        assert le @ moves > 0.99
    # the root is round (no wobble): its first section's radius
    root = pts[np.abs(pts[:, 2]) < 1.0]
    rr = np.hypot(root[:, 0], root[:, 1])
    assert rr.max() - rr.min() < 30.0 and abs(rr.mean() - tb.ROOT_R) < 30.0


def test_first_end_clear_of_pile_rock_and_seabed(built):
    """The CAD piece from A's J-tube bell-mouth over the scour rock to the seabed: its surface stays over the rock's
    ridge and the seabed, clear of the monopile, round (no bend under the cable's bend radius), and its end lies on
    the park's origin along +x at the height of the app's laid cable."""
    _root, info, _js = built
    p = Params()
    piece = info["cable_piece"]
    r = piece["radius"]
    a = next(t for t in info["turbines"] if t["role"] == "A")
    segs = piece["route"]["segments"]
    route = pk.rt.Route("x", p.cable_d)
    for sg in segs:                                        # (the sheet rounds to 0.1 µm: each piece starts at the last end)
        start = route.end if route.segments else np.array(sg["start"])
        if sg["type"] == "line":
            route.add(pk.rt.Line(start, sg["end"]))
        else:
            c, n = np.array(sg["centre"]), pk.rt.unit(sg["normal"])
            c = c + n * float((start - c) @ n)              # (the start in the arc's plane)
            route.add(pk.rt.Arc(c, n, start, math.radians(sg["angle_deg"])))
    assert route.min_radius() >= p.bend_r - 0.01
    assert all(gap < 1e-6 and ang < 0.01 for gap, ang in route.joins())
    pts = route.sample(25.0)
    rho = np.hypot(pts[:, 0] - a["xy"][0], pts[:, 1] - a["xy"][1])
    sb = info["seabed_z"]
    # from where it leaves the bell-mouth: over the rock (its ridge along J-tube 1's azimuth) and the seabed
    out = (rho > np.hypot(*np.subtract(a["bell"][:2], a["xy"])) + 50.0) & (rho < tb.scour_radius() + r)
    rock = np.array([tb.rock_top(min(x, tb.scour_radius())) for x in rho[out]])
    gap = pts[out, 2] - r - rock
    assert gap.min() > 0.0, gap.min()
    assert out.sum() > 500
    assert (pts[:, 2] - r > sb - 0.3 * p.cable_d - 0.01).all()          # sinks at most 30 % of its Ø (as the app's)
    assert rho.min() > info["pile_r"] + r
    # it starts inside the bell-mouth (the J-tube carries it up) and ends at the origin along +x
    assert np.linalg.norm(pts[0] - np.array(a["bell"])) < 600.0
    assert np.allclose(pts[-1], piece["end"], atol=0.01) and np.allclose(piece["end"][:2], [0.0, 0.0])
    assert piece["end"][2] == pytest.approx(sb + (0.5 - 0.3) * p.cable_d)
    assert np.allclose(route.end_tangent, [1.0, 0.0, 0.0], atol=1e-6)
    # from there the app's laid cable runs straight along +x to the touch-down: away from A, clear of its rock
    assert np.hypot(*np.subtract([0.0, 0.0], a["xy"])) > info["scour_r"] + r + 1000.0


def test_demo_options_leave_the_site_parts_alone():
    """The two demo options of the shared turbine parts change nothing when they are not given (the site's)."""
    b0, a0 = tp.jtube_bell(tb.FIT)
    assert b0[2] == pytest.approx(tb.SEABED_Z + 1800.0 - tp.JTUBE_BEND)
    b1, _ = tp.jtube_bell(tb.FIT, tb.JTUBE_BELL_Z)
    assert b1[2] == pytest.approx(tb.SEABED_Z + tb.JTUBE_BELL_Z)
    assert not tp._in_corridor(None, 1000.0, 0.0, 500.0)
    n = tp._radial(tb.CORRIDOR[0])
    assert tp._in_corridor(tb.CORRIDOR, *(n[:2] * 9000.0), 500.0)
    assert not tp._in_corridor(tb.CORRIDOR, *(-n[:2] * 9000.0), 500.0)
