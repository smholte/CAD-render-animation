"""The wind-turbine converter (task 0116) on a small stand-in of the owner's STEP – written by an independent tester.

GitHub's test machines cannot see the owner's ``15MW.step`` (a draft release), so ``iea15_source.read / TFrame /
measure / fit`` and ``iea15.convert`` run here on ``tools/site_projects/iea15_standin.py``: the owner's structure and
names, his measured axes and sizes, simple shapes, and a world placement of its own (turned about z and moved), with
blades drawn for an anticlockwise rotor as his are. The tests know the numbers the stand-in was built with and check
that the converter finds them, mirrors the blades the right way, puts the joints on the axes, writes the bodies
nested as the sheet says and the loop as the sheet rules say; one test builds the offshore project with the app
(Blender as a Python module, its own process) and clash-checks it.

The invented parts come from ``site_projects.turbine_parts`` when it is there; else a minimal module of the same
interface stands in (``_mini_parts``), so the converter can be tested on its own.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
import types
from dataclasses import dataclass

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
KIT = os.path.join(ROOT, "site", "render_kit")

pytest.importorskip("OCP")

from site_projects import iea15, iea15_source as S, iea15_standin as SI, occ  # noqa: E402

VARIANTS = ("offshore", "onshore")
SHIFT = {"offshore": 0.0, "onshore": -14000.0}


# ---------------------------------------------------------------------------
# a minimal turbine_parts (the interface of the task's Design) for when the real one is not there
# ---------------------------------------------------------------------------

def _mini_parts() -> types.ModuleType:
    mod = types.ModuleType("site_projects.turbine_parts")

    @dataclass
    class Part:
        name: str
        body: str
        shape: object

    def _zcyl(x, y, z0, z1, r):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        return occ.moved(BRepPrimAPI_MakeCylinder(r, z1 - z0).Shape(), occ.translate((x, y, z0)))

    def door_z(fit):
        return fit["tower_base_z"] + 1500.0

    def door_cut(fit, variant):
        z = door_z(fit)
        return occ.box((-500.0, -5300.0, z), (500.0, -4700.0, z + 2200.0))

    def make(fit, variant):
        z = door_z(fit)
        top = fit["yaw_bearing_z"][1]
        parts = [Part("NACELLE COVER", "NACELLE", occ.one_solid(occ.box((-3500.0, -4300.0, top + 600.0),
                                                                          (3500.0, 9000.0, top + 7000.0)))),
                 Part("DOOR LEAF", "DOOR", occ.one_solid(occ.box((-480.0, -5010.0, z + 20.0),
                                                                   (480.0, -4990.0, z + 2180.0))))]
        if variant == "offshore":
            parts.append(Part("DAVIT POST", "DAVIT", occ.one_solid(_zcyl(7000.0, -3000.0, 15500.0, 18500.0, 150.0))))
        else:
            parts.append(Part("CONCRETE PEDESTAL", "TOWER",
                              occ.one_solid(occ.cut(_zcyl(0.0, 0.0, 0.0, 1000.0, 6500.0),
                                                    _zcyl(0.0, 0.0, -1.0, 1001.0, 4000.0)))))
        return parts

    def joints(fit, variant):
        out = [{"name": "Door", "kind": "ROTATE", "body": "DOOR", "point": [500.0, -5000.0, door_z(fit)],
                "direction": [0.0, 0.0, 1.0], "limits": [0.0, 100.0]}]
        if variant == "offshore":
            out.append({"name": "Davit", "kind": "ROTATE", "body": "DAVIT", "point": [7000.0, -3000.0, 15500.0],
                        "direction": [0.0, 0.0, 1.0], "limits": [-90.0, 90.0]})
        return out

    def anchors(fit, variant):
        z = door_z(fit) + 1500.0
        out = [{"part": "DOOR LEAF", "point": [0.0, -5010.0, z - 500.0], "normal": [0.0, -1.0, 0.0],
                "up": [0.0, 0.0, 1.0], "kind": "STICKER", "sticker": "WARN_GENERAL", "width_mm": 300.0}]
        r = SI.TOWER_PROFILE[0][1]
        a = math.radians(200.0)
        out.append({"part": "TOWER", "point": [r * math.sin(a), r * math.cos(a), z], "normal": [math.sin(a),
                    math.cos(a), 0.0], "up": [0.0, 0.0, 1.0], "kind": "TEXT", "text": "WTG A07", "width_mm": 1000.0})
        return out

    def cameras(fit, variant):
        hub = fit["rotor"]["point"]
        g = fit["msl_z"]
        if variant == "offshore":
            return [{"name": "Work boat", "eye": [17000.0, -17000.0, g + 2500.0], "target": [0.0, -4000.0, g + 26000.0],
                     "lens": 24.0},
                    {"name": "Whole turbine", "eye": [300000.0, -420000.0, g + 40000.0],
                     "target": [0.0, hub[1], g + 135000.0], "lens": 35.0}]
        return [{"name": "From the field", "eye": [35000.0, -60000.0, 1700.0], "target": [0.0, -4000.0, 60000.0],
                 "lens": 20.0}]

    mod.VARIANTS, mod.Part = VARIANTS, Part
    mod.make, mod.door_cut, mod.joints, mod.anchors, mod.cameras = make, door_cut, joints, anchors, cameras
    mod.MINI = True
    return mod


def _real_parts_available() -> bool:
    return importlib.util.find_spec("site_projects.turbine_parts") is not None


@pytest.fixture(scope="module")
def parts_module():
    """The real site_projects.turbine_parts when it is there, else the minimal one (put in sys.modules)."""
    if _real_parts_available():
        from site_projects import turbine_parts
        yield turbine_parts
        return
    mp = pytest.MonkeyPatch()
    mini = _mini_parts()
    mp.setitem(sys.modules, "site_projects.turbine_parts", mini)
    yield mini
    mp.undo()


# ---------------------------------------------------------------------------
# the stand-in, read and measured once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def standin(tmp_path_factory):
    d = tmp_path_factory.mktemp("iea15_standin")
    path = str(d / "15MW.step")
    info = SI.write(path)
    leaves = S.read(path)
    T = S.TFrame(leaves)
    measured = S.measure(leaves, T)
    return {"path": path, "dir": d, "world": info["world"], "leaves": leaves, "T": T, "m": measured}


@pytest.fixture(scope="module")
def converted(standin, parts_module, tmp_path_factory):
    """Both variants converted once: {variant: (sheet, step path)}."""
    out = {}
    for v in VARIANTS:
        d = str(tmp_path_factory.mktemp(f"iea15_{v}"))
        sheet = iea15.convert(standin["path"], d, True, v, leaves=standin["leaves"])
        out[v] = (sheet, os.path.join(d, f"iea15_{v}.step"))
    return out


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _rodrigues(v, axis, deg):
    k = _unit(axis)
    a = math.radians(deg)
    v = np.asarray(v, float)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * float(k @ v) * (1 - math.cos(a))


# ---------------------------------------------------------------------------
# the stand-in itself
# ---------------------------------------------------------------------------

def test_standin_has_the_owners_structure(standin):
    """The leaves the reader finds, with the owner's prototype names and kinds (SHELL / SOLID), small and quick."""
    leaves = standin["leaves"]
    assert os.path.getsize(standin["path"]) < 3_000_000
    protos = sorted(lf.proto for lf in leaves)
    want = sorted(["tower", "newNosePiece", "bedplate", "newRotor", "stator", "shaft", "Hub", "newyaw_bearing",
                   "misc_equipment", "flange_2", "flange_2", "SRB_mock_bearing", "TDO_mock_bearing"]
                  + ["SHELL", "SOLID"] * 3)
    assert protos == want
    assert occ.count(S.one(leaves, "tower").shape, "solid") == 1
    assert occ.count(S.one(leaves, "Hub").shape, "solid") == 2
    assert occ.count(S.one(leaves, "bedplate").shape, "solid") == 2
    bl = S.blades(leaves)
    assert len(bl) == 3
    for skin, disc in bl:
        assert skin.path[-1].startswith(S.BLADE_PROTO)
        assert occ.count(skin.shape, "solid") == 0 and occ.count(skin.shape, "shell") == 1
        assert occ.count(disc.shape, "solid") == 1
    # the reader multiplied the placements out: every leaf has its own turn
    assert not np.allclose(S.one(leaves, "tower").M[:3, :3], np.eye(3))


def test_tframe_undoes_the_world_placement(standin):
    """TFrame finds the tower axis, sea level and the rotor's heading in a placement that is not the owner's."""
    T = standin["T"]
    assert np.allclose(T.M @ standin["world"], np.eye(4), atol=1e-6)
    assert abs(((T.turn_deg + SI.WORLD_TURN_DEG + 180.0) % 360.0) - 180.0) < 1e-6
    assert abs(T.tower_top_raw - SI.TOWER_TOP) < 1e-3


def test_measure_finds_the_numbers_built_in(standin):
    m = standin["m"]
    assert abs(m["hub_height_m"] - SI.HUB_HEIGHT_M) < 1e-6
    assert abs(m["overhang_m"] - SI.OVERHANG_M) < 1e-6
    assert abs(m["shaft_tilt_deg"] - SI.TILT_DEG) < 1e-6
    assert abs(m["rotor_diameter_m"] - SI.ROTOR_DIAMETER_M) < 0.005
    assert abs(m["blade_length_m"] - SI.BLADE_LENGTH / 1000.0) < 1e-3
    assert abs(m["prebend_m"] - SI.PREBEND / 1000.0) < 0.005
    assert m["precone_deg"] < 1e-3
    assert abs(m["tower_top_z"] - SI.TOWER_TOP) < 1e-3
    assert np.allclose(m["yaw_bearing_z"], [SI.YAW_BEARING[2], SI.YAW_BEARING[3]], atol=1e-3)
    # yaw: both sides (tower, bearing | drum on the bedplate) on the z axis
    y = m["yaw"]
    assert max(y["tower_off_mm"], y["bearing_off_mm"], y["nacelle_off_mm"]) < 1e-3
    assert y["bearing_radii"] == [3000.0, 3250.0] and y["nacelle_radii"] == [1000.0]
    # rotor: the shaft (turns) and the nose (fixed) on one line, the hub's centre on it, pointing upwind
    r = m["rotor"]
    assert np.allclose(r["point"], SI.HUB, atol=1e-3)
    assert np.allclose(r["direction"], SI.UPWIND, atol=1e-9)
    assert r["nose_off_mm"] < 1e-3 and r["nose_angle_deg"] < 1e-6 and r["hub_off_mm"] < 1e-3
    assert r["shaft_radii"] == [1400.0, 1500.0] and r["nose_radii"] == [1000.0, 1100.0]
    # pitch: each blade's own z, the hub's ring centred on it, 3 m from the hub's centre
    assert len(m["hub_rings"]) == 3
    assert all(abs(h["from_hub_mm"] - SI.HUB_TO_BLADE) < 1e-3 for h in m["hub_rings"])
    for b, d in zip(m["blades"], SI.BLADE_DIRS):
        assert np.allclose(b["direction"], d, atol=1e-9)
        assert np.allclose(b["point"], SI.HUB + SI.HUB_TO_BLADE * d, atol=1e-3)
        assert b["ring_off_mm"] < 1e-3 and b["ring_normal_deg"] < 1e-4
        assert b["axis_miss_mm"] < 1e-3 and abs(b["cone_deg"]) < 1e-3
        assert abs(b["root_radius"] - SI.ROOT_R) < 50.0 and abs(b["root_off_axis_mm"] - math.hypot(*SI.ROOT_OFF)) < 5.0
        assert np.allclose(b["x_axis"], SI.DOWN, atol=1e-6)            # the blade's x: downwind


def test_tower_profile_and_fit_for_both_variants(standin):
    leaves, T, m = standin["leaves"], standin["T"], standin["m"]
    prof = S.tower_profile(leaves, T)
    assert np.allclose(prof, SI.TOWER_PROFILE, atol=0.2)
    off = S.fit(leaves, "offshore", T, m)
    on = S.fit(leaves, "onshore", T, m)
    assert off["z_shift"] == 0.0 and on["z_shift"] == -14000.0
    assert off["msl_z"] == 0.0 and off["seabed_z"] == -30000.0 and off["tower_base_z"] == 15000.0
    assert on["msl_z"] == -14000.0 and on["tower_base_z"] == 1000.0 and on["ground_z"] == 0.0
    assert np.allclose(off["tower_profile"], SI.TOWER_PROFILE, atol=0.2)
    # onshore the tower starts at its base on the pedestal (+1 m), r 5000 there, then the same cones 14 m lower
    assert on["tower_profile"][0] == (1000.0, 5000.0)
    assert np.allclose(on["tower_profile"][1:], [(z - 14000.0, r) for z, r in SI.TOWER_PROFILE if z - 14000 > 1000],
                       atol=0.2)
    # the measured dict passed in is not changed by fit
    assert np.allclose(m["rotor"]["point"], SI.HUB, atol=1e-3)
    with pytest.raises(ValueError):
        S.fit(leaves, "floating", T, m)


def test_onshore_fit_shifts_every_height(standin):
    """Every height in the onshore fit is 14 m lower than offshore – the points and the numbers alike. FAULT found:
    ``fit`` shifts the rotor's point, the blades, the rings, the tower top and the yaw bearing, but leaves
    ``hub_height_m`` at its offshore value (150.49 while the rotor point says 136.49): a part made from it would
    sit 14 m too high on land."""
    leaves, T, m = standin["leaves"], standin["T"], standin["m"]
    off = S.fit(leaves, "offshore", T, m)
    on = S.fit(leaves, "onshore", T, m)
    dz = -14000.0
    assert abs(on["rotor"]["point"][2] - off["rotor"]["point"][2] - dz) < 1e-6
    assert abs(on["tower_top_z"] - off["tower_top_z"] - dz) < 1e-6
    for a, b in zip(on["yaw_bearing_z"], off["yaw_bearing_z"]):
        assert abs(a - b - dz) < 1e-6
    for bo, bf in zip(on["blades"], off["blades"]):
        for k in ("point", "root_centre", "apex"):
            assert abs(bo[k][2] - bf[k][2] - dz) < 1e-6, k
    for ro, rf in zip(on["hub_rings"], off["hub_rings"]):
        assert abs(ro["centre"][2] - rf["centre"][2] - dz) < 1e-6
    assert abs(on["hub_height_m"] * 1000.0 - on["rotor"]["point"][2]) < 1e-3, (
        "fit()['hub_height_m'] is not shifted onshore: "
        f"{on['hub_height_m']:.3f} m but the rotor point is at {on['rotor']['point'][2] / 1000:.3f} m")


# ---------------------------------------------------------------------------
# blades: leading edge and mirroring
# ---------------------------------------------------------------------------

def test_leading_edge_side_and_mirrored_blade(standin):
    """The stand-in's blades lead on their +y (anticlockwise from the front, as the owner's); mirrored, on -y."""
    skin = S.blades(standin["leaves"])[0][0].shape
    le = iea15.leading_edge_side(skin)
    tw = math.radians(3.0)                                  # the twist at mid-span
    assert le @ np.array([-math.sin(tw), math.cos(tw), 0.0]) > 0.99
    mir = iea15.mirrored_blade(skin)
    le_m = iea15.leading_edge_side(mir)
    assert le_m @ np.array([-math.sin(tw), -math.cos(tw), 0.0]) > 0.99
    # mirrored: the same length, root and pre-bend (towards -x)
    lo, hi = occ.bbox(mir)
    lo0, hi0 = occ.bbox(skin)
    assert np.allclose([lo[0], hi[0], lo[2], hi[2]], [lo0[0], hi0[0], lo0[2], hi0[2]], atol=1.0)
    assert np.allclose([lo[1], hi[1]], [-hi0[1], -lo0[1]], atol=1.0)


@pytest.mark.parametrize("le_sign", [+1.0, -1.0])
def test_leading_edge_on_a_blade_twisted_the_other_way(le_sign):
    """A blade with its leading edge on either side and twisted the other way round: the side is still found."""
    st = [(z, c, tc, sh, -tw) for z, c, tc, sh, tw in SI.STATIONS]
    skin = SI.blade_skin(le_sign, st)
    le = iea15.leading_edge_side(skin)
    assert le[1] * le_sign > 0.99


def test_mirrored_blades_lead_a_clockwise_turn(standin):
    """After mirroring, each blade's leading edge (in the turbine frame) leads a clockwise turn seen from the front
    (looking downwind): the way the IEA's rotor turns; unmirrored it leads the anticlockwise turn."""
    W = standin["T"].M
    for i, (skin, _disc) in enumerate(S.blades(standin["leaves"])):
        G = W @ skin.M
        d = SI.BLADE_DIRS[i]
        clockwise = np.cross(SI.DOWN, d)                     # motion of a point on the blade, clockwise from front
        le_mir = G[:3, :3] @ iea15.leading_edge_side(iea15.mirrored_blade(skin.shape))
        le_src = G[:3, :3] @ iea15.leading_edge_side(skin.shape)
        assert le_mir @ clockwise > 0.9
        assert le_src @ clockwise < -0.9


# ---------------------------------------------------------------------------
# the conversion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", VARIANTS)
def test_sheet_joints_are_on_the_standins_axes(converted, variant):
    sheet, _step = converted[variant]
    dz = SHIFT[variant]
    by = {j["name"]: j for j in sheet["joints"]}
    assert {"Yaw", "Rotor", "Pitch 1", "Pitch 2", "Pitch 3", "Door"} <= set(by)
    assert ("Davit" in by) == (variant == "offshore")
    yaw = by["Yaw"]
    assert yaw["direction"] == [0.0, 0.0, 1.0] and yaw["point"][:2] == [0.0, 0.0]
    assert abs(yaw["point"][2] - (SI.TOWER_TOP + dz)) < 1e-3
    rot = by["Rotor"]
    hub = SI.HUB + np.array([0.0, 0.0, dz])
    assert np.allclose(rot["point"], hub, atol=1e-2)
    assert np.allclose(rot["direction"], SI.DOWN, atol=1e-6)           # +values: clockwise seen from the front
    assert rot["rides_on"] == "Yaw"
    for i in (1, 2, 3):
        p = by[f"Pitch {i}"]
        d = SI.BLADE_DIRS[i - 1]
        assert p["rides_on"] == "Rotor"
        assert np.allclose(p["point"], hub + SI.HUB_TO_BLADE * d, atol=1e-2)
        assert abs(abs(float(np.dot(p["direction"], d))) - 1.0) < 1e-6
        # +90° turns the (mirrored) leading edge from leading the clockwise turn to facing upwind (feather)
        le = np.cross(SI.DOWN, d)                             # the mirrored blade's leading edge leads clockwise
        assert float(_rodrigues(le, p["direction"], 90.0) @ SI.UPWIND) > 0.99
    for j in sheet["joints"]:
        assert j["source"] and j["kind"] in ("ROTATE", "SLIDE")


def _blade_up_after(sheet, value):
    """The largest cosine between a blade (turned by the rotor value about its joint) and straight up in the rotor
    plane."""
    rot = next(j for j in sheet["joints"] if j["name"] == "Rotor")
    up = np.array([0.0, 0.0, 1.0]) - SI.DOWN[2] * SI.DOWN
    up /= np.linalg.norm(up)
    return max(float(_unit(_rodrigues(d, rot["direction"], value)) @ up) for d in SI.BLADE_DIRS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_poses_and_the_loop(converted, variant):
    sheet, _step = converted[variant]
    poses = {p["name"]: p["values"] for p in sheet["poses"]}
    assert {"Running", "Feathered", "Door open"} <= set(poses) and sheet["start_pose"] == "Running"
    r0 = poses["Running"]["Rotor"]
    assert _blade_up_after(sheet, r0) > 1.0 - 1e-6                     # a blade straight up at the start
    assert all(poses["Feathered"][f"Pitch {i}"] == 90.0 for i in (1, 2, 3))
    door = next(j for j in sheet["joints"] if j["name"] == "Door")
    assert poses["Door open"]["Door"] != 0.0
    lo, hi = door["limits"]
    assert lo <= poses["Door open"]["Door"] <= hi
    a = sheet["animation"]
    assert a["loop"] and a["periods"] == {"Rotor": 120.0}
    rotor = [st for st in a["steps"] if st.get("joint") == "Rotor"]
    assert len(rotor) == 1 and rotor[0]["easing"] == "LINEAR"
    turn = rotor[0]["to"] - r0
    assert turn > 0 and abs(turn / 120.0 - round(turn / 120.0)) < 1e-9
    assert abs(turn / 360.0 / (rotor[0]["seconds"] / 60.0) - 7.56) < 1e-3
    assert rotor[0]["start"] == 0.0 and abs(rotor[0]["seconds"] - a["seconds"]) < 1e-9
    yaw = [st for st in a["steps"] if st.get("joint") == "Yaw"]
    assert yaw and yaw[-1]["to"] == 0.0 and abs(yaw[-1]["start"] + yaw[-1]["seconds"] - a["seconds"]) < 1e-6
    assert all(st["easing"] == "SMOOTH" for st in yaw)                 # stands still at both ends of the loop
    assert a["camera"] in {c["name"] for c in sheet["cameras"]}
    # the check animation only uses poses and joints the sheet has
    ca = sheet["check_animation"]
    for st in ca["steps"]:
        if st["kind"] == "POSE":
            assert st["pose"] in poses
        else:
            assert st["joint"] in {j["name"] for j in sheet["joints"]}


@pytest.mark.parametrize("variant", VARIANTS)
def test_check_animation_takes_the_hinged_parts_through_their_range(converted, variant):
    """``check_animation`` is the clash check of "every other joint through its range" (iea15.check_animation's
    docstring): the door and the davit must reach both of their limits, the blades 0° and 90°. FAULT found: the
    davit (limits -a … +a) only goes from 0 to +a (the "Door open" pose), so a davit that hits the railing, the
    ladder's cage or the cabinet when slewed the other way is never clash-checked."""
    sheet, _step = converted[variant]
    poses = {p["name"]: p["values"] for p in sheet["poses"]}
    reached: dict = {}

    def add(values):
        for k, v in values.items():
            reached.setdefault(k, set()).add(float(v))
    add(poses[sheet["start_pose"]])
    for st in sheet["check_animation"]["steps"]:
        if st["kind"] == "POSE":
            add({j["name"]: poses[st["pose"]].get(j["name"], 0.0) for j in sheet["joints"]})
        else:
            add({st["joint"]: st["to"]})
    lims = {j["name"]: j["limits"] for j in sheet["joints"]}
    for i in (1, 2, 3):
        assert min(reached[f"Pitch {i}"]) <= 0.0 and max(reached[f"Pitch {i}"]) >= 90.0
    for name in ("Door", "Davit"):
        if name not in lims:
            continue
        lo, hi = lims[name]
        got = reached.get(name, {0.0})
        assert min(got) <= lo + 1e-6 and max(got) >= hi - 1e-6, (
            f"{name}: the check animation reaches {min(got):g} … {max(got):g}, its limits are {lo:g} … {hi:g}")


# --- the written STEP ----------------------------------------------------------------------------------------------

def _step_tree(path):
    """[(product path (assemblies, top first), part name as the app's Model finds it, instance name, shape)] of every
    leaf of a STEP. The app's Model knows a part by its product name and (task 0116) its occurrence name."""
    from OCP.collections import Sequence_TDF_Label
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    assert r.ReadFile(path) == 1
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(lab):
        a = TDataStd_Name()
        return a.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), a) else ""

    out, asms = [], []

    def walk(lab, path):
        ref, inst = lab, ""
        if st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            inst = name(lab)
            inst = "" if inst.startswith("=>[") else inst
        own = name(ref)
        if st.IsAssembly_s(ref):
            asms.append((path, own, inst))
            seq = Sequence_TDF_Label()
            st.GetComponents_s(ref, seq)
            for i in range(1, seq.Length() + 1):
                walk(seq.Value(i), path + (own,))
        else:
            out.append((path, own, inst, st.GetShape_s(lab) if st.IsReference_s(lab) else
                        st.GetShape_s(ref).Located(TopLoc_Location())))
    seq = Sequence_TDF_Label()
    st.GetFreeShapes(seq)
    for i in range(1, seq.Length() + 1):
        walk(seq.Value(i), ())
    return out, asms


def _model_names(tree):
    """{name: count} as projects.Model counts them (product name, plus the occurrence name when it differs)."""
    leaves, asms = tree
    names: dict = {}
    for _p, own, inst, _s in leaves:
        names[own] = names.get(own, 0) + 1
        if inst and inst != own:
            names[inst] = names.get(inst, 0) + 1
    for _p, own, inst in asms:
        names[own] = names.get(own, 0) + 1
        if inst and inst != own:
            names[inst] = names.get(inst, 0) + 1
    return names


@pytest.fixture(scope="module")
def trees(converted):
    return {v: _step_tree(converted[v][1]) for v in VARIANTS}


def _leaf_name(own, inst):
    return inst or own


@pytest.mark.parametrize("variant", VARIANTS)
def test_written_step_nests_the_bodies(converted, trees, variant):
    """TURBINE FIXED > NACELLE YAW > ROTOR TURNING > BLADE n PITCH (+ DOOR SWING, DAVIT SLEW in the fixed part);
    every part one solid or one shell."""
    sheet, _step = converted[variant]
    leaves, asms = trees[variant]
    top = f"IEA15_{variant.upper()}"
    by = {}
    for path, own, inst, shape in leaves:
        nm = _leaf_name(own, inst)
        by.setdefault(nm, []).append(path)
        ns, nsh = occ.count(shape, "solid"), occ.count(shape, "shell")
        assert ns == 1 or (ns == 0 and nsh == 1), f"{nm}: {ns} solids, {nsh} shells"
    fixed = (top, iea15.FIXED)
    yaw = fixed + (iea15.YAW,)
    rotor = yaw + (iea15.ROTOR,)
    want = {"TOWER": fixed, "YAW BEARING": fixed, "BEDPLATE": yaw, "NOSE": yaw, "STATOR": yaw, "NACELLE DRUM": yaw,
            "HUB": rotor, "SHAFT": rotor, "GENERATOR ROTOR": rotor,
            "HUB CENTRE MARK": rotor}
    for i in (1, 2, 3):
        want[f"BLADE {i}"] = rotor + (iea15.pitch_body(i),)
        want[f"BLADE {i} ROOT DISC"] = rotor + (iea15.pitch_body(i),)
    if variant == "offshore":
        want["MONOPILE"] = fixed
        want["MONOPILE BELOW SEABED"] = fixed
    for nm, path in want.items():
        assert by.get(nm) == [path], f"{nm}: {by.get(nm)}"
    flanges = [p for nm, ps in by.items() if nm.startswith("NOSE FLANGE") for p in ps]
    assert flanges == [yaw, yaw]
    # every invented part sits in the body its maker gave it
    door = [p for p in by.items() if p[1][0][-1] == iea15.DOOR]
    assert door, "no part in DOOR SWING"
    assert all(p[1] == [fixed + (iea15.DOOR,)] for p in door)
    if variant == "offshore":
        assert any(p[1] == [fixed + (iea15.DAVIT,)] for p in by.items())
    assert sorted(sheet["invented"]) == sorted(n for n in by if n in sheet["invented"])
    assert len(leaves) == sheet["parts"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_part_has_its_own_name(trees, variant):
    """Every part of the written STEP has a name of its own, as the app shows it (2 Structure, clash rows).
    FAULT found: the two nose flanges share one shape (key "flange_2" in iea15.source_parts) and stepout names a
    shared shape after its first part, with no occurrence name: the import has "NOSE FLANGE 1" twice and no
    "NOSE FLANGE 2" (the fix the blades got - a sixth item, the shape's own name - is missing for the flanges)."""
    leaves, _asms = trees[variant]
    names = [_leaf_name(own, inst) for _p, own, inst, _s in leaves]
    assert sorted(n for n in set(names) if names.count(n) > 1) == []


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_name_the_sheet_uses_is_one_part(converted, trees, variant):
    """The project maker finds each part the sheet names (hidden parts, joints' bodies, decals) exactly once in the
    written STEP, as the app imports it. FAULT found (before task 0116 named the occurrences): the three blades share
    one shape, stepout named it after the first ("BLADE 1"), so the import had three "BLADE 1 ROOT DISC" and no
    "BLADE 2 ROOT DISC" – the hide list stopped the project."""
    sheet, _step = converted[variant]
    names = _model_names(trees[variant])
    used = [h["part"] for h in sheet["hide"]] + [d["part"] for d in sheet["decals"]]
    used += [p for j in sheet["joints"] for p in j["parts"]]
    for n in used:
        assert names.get(n, 0) == 1, f"'{n}': {names.get(n, 0)} parts of that name"


@pytest.mark.parametrize("variant", VARIANTS)
def test_tower_split_and_door_cut(converted, trees, standin, parts_module, variant):
    """The tower is cut at +15 m (offshore frame), offshore again at the seabed (-30 m); the door opening is cut out
    of the tower and the closed door leaf does not reach into the tower's wall."""
    dz = SHIFT[variant]
    leaves, _asms = trees[variant]
    by = {_leaf_name(own, inst): (path, shape) for path, own, inst, shape in leaves}

    def zrange(nm):
        lo, hi = occ.bbox(by[nm][1])
        return lo[2], hi[2]
    lo, hi = zrange("TOWER")
    assert abs(lo - (15000.0 + dz)) < 1.0 and abs(hi - (SI.TOWER_TOP + dz)) < 1.0
    if variant == "offshore":
        assert np.allclose(zrange("MONOPILE"), (-30000.0, 15000.0), atol=1.0)
        assert np.allclose(zrange("MONOPILE BELOW SEABED"), (-75000.0, -30000.0), atol=1.0)
    else:
        assert "MONOPILE" not in by
    # the uncut tower between the same heights is bigger by the door opening
    full = SI.tower()
    slab = occ.box((-30000, -30000, 15000.0), (30000, 30000, 400000))
    whole = occ.volume(occ.common(full, slab))
    cut = occ.volume(by["TOWER"][1])
    assert whole - cut > 1e6, "no door opening in the tower"
    fit = S.fit(standin["leaves"], variant, standin["T"], standin["m"])
    hole = occ.volume(occ.common(occ.moved(occ.common(full, slab), occ.translate((0, 0, dz))),
                                 parts_module.door_cut(fit, variant)))
    assert abs((whole - cut) - hole) < 0.01 * hole
    for nm, (path, shape) in by.items():
        if path[-1] == iea15.DOOR:
            assert occ.volume(occ.common(shape, by["TOWER"][1])) < 1e3, f"{nm} reaches into the tower"


@pytest.mark.parametrize("variant", VARIANTS)
def test_sheet_numbers_and_notes(converted, variant):
    sheet, _step = converted[variant]
    m = sheet["measured"]
    dz = SHIFT[variant] / 1000.0
    assert abs(m["hub_height_m"]["value"] - (SI.HUB_HEIGHT_M + dz)) < 1e-3
    assert abs(m["rotor_diameter_m"]["value"] - SI.ROTOR_DIAMETER_M) < 0.005
    assert abs(m["shaft_tilt_deg"]["value"] - 6.0) < 1e-3
    assert abs(m["overhang_m"]["value"] - SI.OVERHANG_M) < 1e-3
    assert sheet["frame"]["z_shift_mm"] == SHIFT[variant]
    if variant == "offshore":
        assert sheet["scene"]["water_level_m"] == 30.0
    else:
        assert sheet["scene"] == {"floor_offset_m": 0.0}
    hidden = {h["part"] for h in sheet["hide"]}
    assert {"MAIN BEARING SRB", "MAIN BEARING TDO", "HUB CENTRE MARK"} | {f"BLADE {i} ROOT DISC" for i in (1, 2, 3)} \
        <= hidden
    assert ("MONOPILE BELOW SEABED" in hidden) == (variant == "offshore")
    notes = " ".join(sheet["notes"])
    assert "mirrored" in notes and "+15 m" in notes
    assert "1 extra solids" in notes                         # the bedplate's sliver, left out


@pytest.mark.parametrize("variant", VARIANTS)
def test_scene_level_puts_the_sea_and_ground_at_their_heights(converted, trees, variant):
    """The app puts the floor at the lowest visible point (less the floor gap) and the sea ``water_level`` above it
    (hidden parts do not count): offshore the lowest visible point must be the seabed cut (-30 m), so the sea lands
    at MSL; onshore the ground (z 0) must be the lowest visible point less the sheet's floor gap. FAULT found
    (onshore, with the real turbine_parts): the buried CONCRETE SLAB reaches 400 mm below the ground and the sheet's
    ``floor_offset_m`` is 0, so the app's ground lies 0.4 m too low - the slab and the stair's foot stand 0.4 m out
    of the ground (iea15.convert: ``"scene": {"floor_offset_m": 0.0}``)."""
    sheet, _step = converted[variant]
    leaves, _asms = trees[variant]
    hidden = {h["part"] for h in sheet["hide"]}
    low = min(occ.bbox(shape)[0][2] for _p, own, inst, shape in leaves if _leaf_name(own, inst) not in hidden)
    if variant == "offshore":
        assert abs(low + 1000.0 * sheet["scene"]["water_level_m"] - 0.0) < 50.0, f"lowest visible point {low:.0f} mm"
    else:
        assert abs(low - 1000.0 * sheet["scene"]["floor_offset_m"] - 0.0) < 50.0, f"lowest visible point {low:.0f} mm"


def test_written_step_says_it_is_a_changed_copy(converted):
    for v in VARIANTS:
        head = open(converted[v][1], encoding="latin-1").read(4000)
        assert "Modified copy of the IEA-15-240-RWT" in head and f"({v})" in head


def test_convert_refuses_a_blade_whose_leading_edge_trails(standin, parts_module, tmp_path):
    """Blades drawn for a clockwise rotor already (leading edge on -y): mirrored they would lead the wrong way, and
    the converter says so instead of writing a turbine whose blades fly backwards."""
    path = str(tmp_path / "cw.step")
    SI.write(path, le_sign=-1.0)
    with pytest.raises(RuntimeError, match="leading edge"):
        iea15.convert(path, str(tmp_path / "out"), False, "offshore")


def test_blades_never_enter_the_hub_while_pitching(standin):
    """Every point of the (mirrored) blade skin near the root stays out of the hub's shell at every pitch 0-90°."""
    from site_projects.iea15_source import _mesh_points
    skin = iea15.mirrored_blade(S.blades(standin["leaves"])[0][0].shape)
    occ.tri_count(skin, 20.0, 5.0)
    P = _mesh_points(skin)
    P = P[P[:, 2] < 20000.0]
    for th in range(0, 91, 5):
        a = math.radians(th)
        R = np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])
        for i in range(3):
            F = SI.blade_frame(i)
            rel = (P @ R.T) @ F[:3, :3].T + F[:3, 3] - SI.HUB
            d = np.linalg.norm(rel, axis=1)
            inside = (d > SI.HUB_R_IN) & (d < SI.HUB_R_OUT)
            for dj in SI.BLADE_DIRS:
                inside &= rel @ dj < SI.HUB_TO_BLADE - 1.0
            assert not inside.any(), f"blade {i + 1} at pitch {th}°: {int(inside.sum())} points in the hub"


# ---------------------------------------------------------------------------
# the app project (Blender as a Python module, its own process)
# ---------------------------------------------------------------------------

DRIVER = textwrap.dedent('''
    import json, os, sys
    root, sheets, model, step, out = sys.argv[1:6]
    sys.path.insert(0, os.path.join(root, "tools"))
    sys.path.insert(0, os.path.join(root, "site", "render_kit"))
    import make_site_projects as msp
    import make_site_pictures as kit
    import projects
    projects.SHEETS = sheets                     # the stand-in's sheet instead of the kit's
    kit.KIT_SHEETS = sheets
    res = msp.build_project(model, out, quality="draft", check=True, step=step, log=lambda *a: None)
    import bpy
    s = bpy.context.scene.fresing
    res["animations_left"] = [a.name for a in s.animations]
    res["shots_left"] = [x.name for x in s.shots]
    res["decal_count"] = sum(len(o.fresing_decals) for o in bpy.data.objects if hasattr(o, "fresing_decals"))
    from fresing_render.blender import logic
    import projects as P
    from mathutils import Vector
    scene = bpy.context.scene
    cached = float(logic.cached_bounds(scene)[0][2])
    fresh = float(logic.update_bounds(scene)[0][2])
    m = P.Model(sys.modules["fresing_render"], scene, P.load(model))
    res["lowest_cached_m"], res["lowest_m"] = cached, fresh
    res["msl_world_m"] = float(m.point((0.0, 0.0, 0.0)).z)
    res["water_level_m"], res["floor_offset_m"] = float(s.water_level), float(s.floor_offset)
    print("RESULT " + json.dumps(res, default=str))
''')


def _one_third(sheet: dict) -> dict:
    """The sheet with its loop cut to one third of a turn (same speed, same yaw swing, still a closed loop): the
    clash check of the whole 4/3 turn costs ~3 min here, the third ~1."""
    s = json.loads(json.dumps(sheet))
    a = s["animation"]
    k = 1.0 / iea15.LOOP_THIRDS
    secs = round(a["seconds"] * k, 4)
    for st in a["steps"]:
        if st["joint"] == "Rotor":
            r0 = next(p for p in s["poses"] if p["name"] == s["start_pose"])["values"]["Rotor"]
            st["to"], st["seconds"] = r0 + 120.0, secs
        else:
            st["start"], st["seconds"] = round(st["start"] * k, 4), round(st["seconds"] * k, 4)
    a["seconds"] = secs
    a["steps"][-1]["seconds"] = round(secs - a["steps"][-1]["start"], 4)
    return s


@pytest.mark.parametrize("variant", ["offshore"])
def test_standin_project_builds_with_no_clash(converted, tmp_path, variant):
    """The converted stand-in imported with the app (Draft), joints, poses, decals, cameras, the loop built (cut to
    one third of a turn, ``_one_third``) and clash-checked, and the check animation too: 0 clash rows, joints on the
    sheet's axes, the loop closes, the check animation is taken away again, the sea at sea level."""
    pytest.importorskip("bpy")
    sheet, step = converted[variant]
    sheet = _one_third(sheet)
    model = f"iea15_{variant}"
    sheets = tmp_path / "sheets"
    sheets.mkdir()
    for f in os.listdir(os.path.join(KIT, "projects")):
        shutil.copy(os.path.join(KIT, "projects", f), sheets / f)
    for v in VARIANTS:                                   # models.ini names both projects' cameras
        with open(sheets / f"iea15_{v}.json", "w", encoding="utf-8") as fh:
            json.dump(sheet if v == variant else converted[v][0], fh)
    script = tmp_path / "driver.py"
    script.write_text(DRIVER)
    res = subprocess.run([sys.executable, str(script), ROOT, str(sheets), model, step, str(tmp_path / "proj")],
                         capture_output=True, text=True, timeout=900)
    out = res.stdout
    assert res.returncode == 0 and "RESULT " in out, out[-3000:] + res.stderr[-3000:]
    r = json.loads(out[out.index("RESULT ") + 7:].splitlines()[0])
    assert r["joints"] == len(sheet["joints"]) and r["poses"] == len(sheet["poses"])
    assert r["hidden"] >= len(sheet["hide"])
    assert r["axis_error_deg"] <= 0.1 and r["axis_error_mm"] <= 0.1
    assert r["clash_rows"] == 0, r.get("clashes")
    # The check animation pitches the blades 0 -> 90°. On the stand-in the app's clash check reports "HUB × BLADE"
    # (139-174 mm, frames 13-14 only) although no point of the blade enters the hub at any pitch
    # (test_blades_never_enter_the_hub_while_pitching): the blade is an OPEN shell (as the owner's) whose open root
    # lies on the hub's ring face, and an inside test of an open shell is not defined. Reported to the author; every
    # other pair must be clear.
    other = [c for c in r.get("check_clashes", []) if not c.startswith("HUB × BLADE")]
    assert not other, other
    assert r["loop_gap"] < 1e-5
    assert r["frames"] == 1 + round(sheet["animation"]["seconds"] * 25)
    assert r["decals"] == len(sheet["decals"]) and r["cameras"] == len(sheet["cameras"])
    # the check animation was taken away again: only the sheet's animation and the cameras' and its own shots
    assert r["animations_left"] == [sheet["animation"]["name"]]
    assert sheet["check_animation"]["name"] not in r["shots_left"]
    # the sea where the sheet wants it: the lowest visible point (the floor, as the app caches it) + the water level
    assert abs(r["lowest_cached_m"] - r["lowest_m"]) < 1e-3
    assert abs(r["lowest_m"] + r["water_level_m"] - r["msl_world_m"]) < 0.05
