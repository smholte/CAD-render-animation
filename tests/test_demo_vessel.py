"""Task 0153 / 0247: the demo's ship in detail (fresing_render/demo_model/vessel.py) – hull, superstructure, propulsion,
outfitting, her own deck crane with its hoist, a plain deck (no well, the bulwark closed all round). OpenCascade only
(the ship is built alone, ~10 s); the app's side (looks, marks, cameras, the propellers turning, the crane's shot, the
clash check) is in tests/test_demo_project*.py.
"""

import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

pytest.importorskip("OCP")

from fresing_render.demo_model import geom as g  # noqa: E402
from fresing_render.demo_model import vessel as vs  # noqa: E402
from fresing_render.demo_model.params import ShipParams  # noqa: E402


@pytest.fixture(scope="module")
def ves():
    p = ShipParams()
    a = vs.vessel(p)
    parts = [(node, uid, W) for node, uid, W, _l, _p in g.walk(a) if isinstance(node, g.Part)]
    return {"p": p, "a": a, "parts": parts, "joints": {j["name"]: j for j in g.resolve_joints(a)}}


def _named(ves, name):
    return [(n, u, W) for n, u, W in ves["parts"] if n.name == name]


def _placed(node, W):
    return g.xform(node.shape, W)


def _bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def test_every_part_is_one_solid_and_the_file_is_written(ves, tmp_path):
    bad = [u for n, u, _W in ves["parts"] if g.solids(n.shape) != 1]
    assert not bad
    g.write_step(ves["a"], str(tmp_path / "v.step"))           # refuses parts of several solids (no colour)
    assert os.path.getsize(tmp_path / "v.step") > 100_000


def test_part_counts(ves):
    count = lambda name: len(_named(ves, name))  # noqa: E731
    for name, n in (("HULL", 1), ("HULL BOTTOM", 1), ("BOOT TOP", 1), ("MAIN DECK", 1), ("BULWARK", 1), ("SKEG", 1),
                    ("BILGE KEEL", 2), ("RUBBING STRAKE", 2), ("NAME BOARD", 2), ("DRAFT MARK BOARD", 4),
                    ("PROPELLER", 4), ("THRUSTER NOZZLE", 2), ("THRUSTER TUNNEL", 2), ("ACCOMMODATION", 1),
                    ("BRIDGE", 1), ("FUNNEL", 2), ("FUNNEL TOP", 2), ("MAST", 1), ("RADAR SCANNER", 2),
                    ("LIFEBOAT", 2), ("DAVIT", 4), ("CRANE BOOM", 1), ("HOOK BLOCK", 1), ("BOLLARD", 6),
                    ("FAIRLEAD", 4), ("HATCH COVER", 3), ("WINDLASS", 2), ("HAWSE PIPE", 2), ("ANCHOR", 2),
                    ("HOIST WIRE", 1), ("BOOM HEAD SHEAVE", 1), ("WINCH DRUM", 1), ("DRUM FLANGE", 2)):
        assert count(name) == n, name
    assert count("RAILING") >= 5 and count("WINDOW") >= 6 and count("BRIDGE WINDOW") == 3


def test_joints_of_the_propulsion_radars_and_crane(ves):
    js = ves["joints"]
    assert len(js) == 13                         # (task 0174: the crane's hoist drum and head sheave; 0247: its hook)
    for side in ("PS", "SB"):
        steer, prop = js[f"AZIMUTH THRUSTER {side}: Steer"], js[f"AZIMUTH THRUSTER {side}: Propeller turn"]
        assert np.allclose(steer["axis"]["direction"], [0, 0, 1])
        assert prop["rides_on"] == f"AZIMUTH THRUSTER {side}: Steer"
        assert all(any(q.startswith(s) for s in steer["parts"]) for q in prop["parts"])   # it rides on the steer
        assert np.allclose(prop["axis"]["direction"], [-1, 0, 0])
        assert prop["drive"]["by"] == "operator" and steer["limits"] is None
    for k in (1, 2):
        j = js[f"BOW THRUSTER {k}: Propeller turn"]
        assert np.allclose(np.abs(j["axis"]["direction"]), [0, 1, 0]) and j["axis"]["point"][2] < -2000.0
    for k in (1, 2):
        assert np.allclose(js[f"SUPERSTRUCTURE: Radar {k} turn"]["axis"]["direction"], [0, 0, -1])
    turning = {n for n, j in js.items() if j.get("motor")}           # turn without end (the app's Motor)
    assert turning == set(js) - {"DECK CRANE: Luff", "DECK CRANE: Hoist drum turn", "DECK CRANE: Head sheave turn",
                                 "DECK CRANE: Hook lower"}
    for name in ("DECK CRANE: Hoist drum turn", "DECK CRANE: Head sheave turn", "DECK CRANE: Hook lower"):
        assert js[name]["rides_on"] == "DECK CRANE: Luff" and js[name]["drive"]["by"] == "winch"
    assert js["DECK CRANE: Luff"]["rides_on"] == "DECK CRANE: Slew" and js["DECK CRANE: Luff"]["limits"] == [-55.0, 10.0]
    hook = js["DECK CRANE: Hook lower"]                              # task 0247: plumb down, on the boom
    assert hook["type"] == "slide" and np.allclose(hook["axis"]["direction"], [0, 0, -1])
    assert hook["limits"] == [0.0, vs.HOOK_DROP]


def test_a_plain_deck(ves):
    """Task 0247: no carousel well (the deck plate is whole: its area is the outline's) and the bulwark closed all
    round – at the transom and along the starboard quarter, where the old spread's openings were."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    names = {n.name for n, _u, _W in ves["parts"]}
    assert "CAROUSEL WELL" not in names
    bw = next(_placed(n, W) for n, u, W in ves["parts"] if n.name == "BULWARK")
    outline = np.array(ves["a"].info["deck_outline"])
    p = ves["p"]
    for x in (1500.0, 9000.0, 20000.0):
        for side in (-1, 1):
            half = outline[outline[:, 1] * side > 0]
            order = np.argsort(half[:, 0])
            edge = float(np.interp(x, half[order, 0], np.abs(half[order, 1])))
            y = side * (edge - 80.0)                                   # in the bulwark plate, just inside the edge
            st = BRepClass3d_SolidClassifier(bw, g.P((x, y, p.deck_z + 500.0)), 1e-3)
            assert st.State() == TopAbs_IN, (x, side)
    lo, _hi = _bbox(bw)
    assert lo[0] < 200.0                                                # round the transom too


def test_the_propellers_turn_free_of_their_nozzles_pods_and_tunnels(ves):
    """Each propeller turned about its own joint never meets the parts round it: the nozzle's inside and the tunnel
    lie outside its swept disc, the pod and gearbox outside its hub's end."""
    js = ves["joints"]
    by_uid = {u: (n, W) for n, u, W in ves["parts"]}
    for name, j in js.items():
        if not name.endswith("Propeller turn"):
            continue
        uid = j["parts"][0] if j["parts"][0] in by_uid else next(u for u in by_uid if u.startswith(j["parts"][0]) and
                                                                    by_uid[u][0].name == "PROPELLER")
        node, W = by_uid[uid]
        prop = _placed(node, W)
        group = uid.rsplit("/", 2)[0] if "AZIMUTH" in uid else uid.rsplit("/", 1)[0]
        others = [_placed(n, Wo) for u, (n, Wo) in by_uid.items() if (u.startswith(group) and u != uid)
                  or n.name == "HULL BOTTOM"]
        assert len(others) >= 3, name
        c, d = np.array(j["axis"]["point"]), np.array(j["axis"]["direction"])
        for ang in (0.0, 17.0, 45.0, 71.0):
            turned = g.xform(prop, g.Rot(d, ang, c))
            for o in others:
                assert g.volume(g.common(turned, o)) < 1.0, (name, ang)
        # the swept disc stays inside the nozzle / tunnel: every corner of the propeller within the inside radius
        lo, hi = _bbox(prop)
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        r = corners - c
        r -= np.outer(r @ d, d)
        R = vs.AZ_PROP_R if "AZIMUTH" in name else vs.BOW_PROP_R
        assert np.linalg.norm(r, axis=1).max() < math.sqrt(2) * R + 50.0


def test_every_turning_part_turns_free(ves):
    """Every joint that turns without end (propellers, steers, radars, the crane's slew; found by the demo's clash
    check: a radar scanner swept through the mast) turned at several angles never meets a part that stays."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    by_uid = {u: (n, W) for n, u, W in ves["parts"]}
    for name, j in ves["joints"].items():
        if not j.get("motor"):
            continue
        moving = {u for u in by_uid if any(u == q or u.startswith(q + "/") for q in j["parts"])}
        assert moving, name
        shapes = [_placed(*by_uid[u]) for u in moving]
        c, d = np.array(j["axis"]["point"]), np.array(j["axis"]["direction"])
        reach = 0.0
        for sh in shapes:
            lo, hi = _bbox(sh)
            corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            reach = max(reach, float(np.linalg.norm(corners - c, axis=1).max()))
        others = []
        for u, (n, W) in by_uid.items():
            if u in moving:
                continue
            sh = _placed(n, W)
            lo, hi = _bbox(sh)
            near = np.clip(c, lo, hi)
            if np.linalg.norm(near - c) < reach + 10.0:
                others.append((u, sh))
        for ang in (0.0, 31.0, 77.0, 133.0, 190.0, 260.0, 318.0):
            for sh in shapes:
                turned = g.xform(sh, g.Rot(d, ang, c))
                for u, o in others:
                    assert g.volume(g.common(turned, o)) < 1.0, (name, ang, u)
    del Bnd_Box, BRepBndLib


def test_the_thrusters_are_under_water_and_under_the_hull(ves):
    for node, uid, W in ves["parts"]:
        if node.name in ("PROPELLER", "THRUSTER NOZZLE", "THRUSTER POD", "THRUSTER STRUT", "TUNNEL GEARBOX"):
            lo, hi = _bbox(_placed(node, W))
            assert hi[2] < -1500.0, uid
    hull = [_placed(n, W) for n, u, W in ves["parts"] if n.name == "HULL BOTTOM"][0]
    for node, uid, W in _named(ves, "THRUSTER NOZZLE") + _named(ves, "THRUSTER STRUT"):
        assert g.volume(g.common(_placed(node, W), hull)) < 1.0, uid


def test_the_bow_tunnels_go_through_the_hull(ves):
    L = ves["p"].length
    bottom = [_placed(n, W) for n, u, W in ves["parts"] if n.name == "HULL BOTTOM"][0]
    for xb in vs.BOW_TUNNELS:
        hole = g.cyl(vs.BOW_TUNNEL_R - 5.0, 40000.0, (L - xb, -20000.0, vs.BOW_Z), (0, 1, 0))
        assert g.volume(g.common(hole, bottom)) < 1.0
        # and there is hull round it (the tunnel runs through the bow, not under it)
        ring = g.tube(vs.BOW_TUNNEL_R + 600.0, vs.BOW_TUNNEL_R + 100.0, 2000.0, (L - xb, -1000.0, vs.BOW_Z), (0, 1, 0))
        assert g.volume(g.common(ring, bottom)) > 0.9 * g.volume(ring)


def test_hull_shape_sheer_stem_bulb_and_paint_bands(ves):
    p, L = ves["p"], ves["p"].length
    st = vs.stations(p, L)
    flat = [s for s in st if s[0] <= L - vs.SHEER_LEN]
    assert all(s[5] == p.deck_z for s in flat)                     # the spread's deck stays level
    assert st[-1][5] == pytest.approx(p.deck_z + vs.SHEER)          # the sheer at the stem
    assert all(b[5] >= a[5] for a, b in zip(st, st[1:]))
    assert st[-1][3] > 0.0 > st[-2][3]                              # raked stem: its foot above the waterline
    parts = {n.name: _placed(n, W) for n, u, W in ves["parts"] if n.name in ("HULL", "BOOT TOP", "HULL BOTTOM",
                                                                             "MAIN DECK")}
    lo, hi = _bbox(parts["BOOT TOP"])
    assert lo[2] < -500.0 and hi[2] > 500.0                         # the band spans the waterline
    lo, hi = _bbox(parts["HULL BOTTOM"])
    assert hi[2] <= vs.BOOT_LO + 1.0 and hi[0] > L - 1500.0          # the bulb's nose forward of the forefoot
    lo, hi = _bbox(parts["HULL"])
    assert lo[2] >= vs.BOOT_HI - 1.0
    # the deck plate follows the sheer: DECK_T thick at the stem's top
    lo, hi = _bbox(parts["MAIN DECK"])
    assert hi[2] == pytest.approx(p.deck_z + vs.SHEER, abs=5.0)
    assert g.volume(parts["MAIN DECK"]) == pytest.approx(vs.DECK_T * _deck_area(ves), rel=0.08)


def _deck_area(ves):
    """The deck outline's area (mm²): a plain deck, no well (task 0247)."""
    pts = np.array(ves["a"].info["deck_outline"])
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def test_superstructure_and_outfitting_stand_on_the_deck_inside_the_hull(ves):
    """Everything on deck stands inside the deck outline (lifeboats and the bridge's wings may reach out over it by
    their own width only)."""
    from matplotlib.path import Path
    outline = Path(np.array(ves["a"].info["deck_outline"]))
    p = ves["p"]
    for node, uid, W in ves["parts"]:
        if node.name in ("ACCOMMODATION", "FUNNEL", "LIFEBOAT", "BOLLARD", "HATCH COVER", "WINDLASS", "CRANE PEDESTAL",
                         "DAVIT"):
            lo, hi = _bbox(_placed(node, W))
            for x in (lo[0], hi[0]):
                for y in (lo[1], hi[1]):
                    assert outline.contains_point((x, y)), uid
            assert lo[2] >= p.deck_z - 1.0, uid


def test_boards_lie_on_the_hull_side(ves):
    hull = {n.name: _placed(n, W) for n, u, W in ves["parts"] if n.name in ("HULL", "BOOT TOP")}
    boards = ves["a"].info["boards"]
    assert len(boards) == 6
    for b in boards:
        c, n = np.array(b["centre"]), np.array(b["normal"])
        assert n[1] * b["side"] > 0.6                              # facing outboard (the bow flares)
        # a point just outside the board's face is outside the hull, one 100 mm in is inside it
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.TopAbs import TopAbs_IN
        key = "HULL" if c[2] > vs.BOOT_HI + 100.0 else "BOOT TOP"
        out = BRepClass3d_SolidClassifier(hull[key], g.P(c + 20.0 * n), 1e-3)
        inn = BRepClass3d_SolidClassifier(hull[key], g.P(c - 100.0 * n), 1e-3)
        assert out.State() != TopAbs_IN and inn.State() == TopAbs_IN, b["name"]
