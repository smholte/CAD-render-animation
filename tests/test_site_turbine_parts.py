"""The parts Fresing adds to the IEA 15 MW turbine (task 0116, ``tools/site_projects/turbine_parts.py``).

Both variants are built from the measured numbers (``fit``). On the owner's machine the real ones are read from
``~/iea/work`` (with every part of his model in the turbine frame, ``src_T/*.brep``: the clearance checks against the
drivetrain, the generator, the tower and the yaw bearing run then); elsewhere – GitHub – from the copy below
(``SYNTHETIC``, the same numbers; a test keeps the two in step) and against a tower made from its profile.

What is checked: every part ONE valid solid (CLAUDE.md section 8), names unique with a known prefix, bodies known,
joints / decal anchors / cameras well formed, the triangles at the importer's Normal facets (under 150 000 per
variant, printed per part), and that nothing comes into what moves: the turning generator, hub and blades at any
pitch (nothing of ours as far upwind as they reach), the nacelle yawing +-10° over the tower, the door leaf over its
whole swing, the davit's jib and hook over their slewing range.
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

pytest.importorskip("OCP")

from site_projects import occ, turbine_parts as tp  # noqa: E402

from fresing_render.importer import step_reader  # noqa: E402

WORK = os.path.expanduser(os.environ.get("FRESING_IEA_WORK", "~/iea/work"))
HAVE_SRC = os.path.isdir(os.path.join(WORK, "src_T")) and all(
    os.path.isfile(os.path.join(WORK, f"fit_{v}.json")) for v in tp.VARIANTS)

BUDGET = 150_000
# Measured on the owner's model (13 Nov 2026): the most downwind point of what turns with the rotor (the generator
# rotor's back face; hub, shaft), as a distance along the rotor axis from the hub centre (+ = upwind), and the
# farthest a blade's skin lies from its pitch axis (pitching, a blade point can come that far downwind).
ROTOR_S_MIN = -6264.4
BLADE_RHO = 4081.0
NACELLE_GAP = 100.0                  # to the turning generator (task brief)
MOVE_GAP = 8.0                       # to anything a moving part (door, davit, yawing nacelle) passes

# The measured numbers the parts rely on (offshore, the turbine frame, mm); onshore = 14 m lower, the tower from
# the pedestal's top (iea15_source.fit).
SYNTHETIC = {
    "tower_top_z": 144582.0,
    "yaw_bearing_z": [144582.0, 144962.0],
    "rotor": {"point": [0.0, -11210.318, 150488.063], "direction": [0.0, -0.9945219, 0.1045285]},
    "msl_z": 0.0, "seabed_z": -30000.0, "tower_base_z": 15000.0, "z_shift": 0.0,
    "tower_profile": [[-75000.0, 5000.0], [28000.0, 5000.0], [41000.0, 4963.0], [54000.0, 4721.5],
                      [67000.0, 4416.5], [80000.0, 4075.5], [93000.0, 3695.0], [106000.0, 3454.5],
                      [119000.0, 3374.0], [132000.0, 3286.0], [144582.0, 3250.0]],
}


def _synthetic(variant: str) -> dict:
    f = json.loads(json.dumps(SYNTHETIC))
    f["variant"] = variant
    if variant == "onshore":
        dz = -14000.0
        f["tower_top_z"] += dz
        f["yaw_bearing_z"] = [z + dz for z in f["yaw_bearing_z"]]
        f["rotor"]["point"][2] += dz
        f.update(msl_z=dz, seabed_z=-30000.0 + dz, tower_base_z=15000.0 + dz, z_shift=dz, ground_z=0.0)
        prof = [[z + dz, r] for z, r in f["tower_profile"]]
        zb = f["tower_base_z"]
        f["tower_profile"] = [[zb, tp.tower_radius({"tower_profile": prof}, zb)]] + [p for p in prof if p[0] > zb]
    return f


def _fit(variant: str) -> dict:
    if HAVE_SRC:
        with open(os.path.join(WORK, f"fit_{variant}.json"), encoding="utf-8") as fh:
            return json.load(fh)
    return _synthetic(variant)


_BUILT: dict = {}


def _build(v: str):
    if v not in _BUILT:
        fit = _fit(v)
        _BUILT[v] = (v, fit, tp.make(fit, v))
    return _BUILT[v]


@pytest.fixture(scope="module", params=tp.VARIANTS)
def built(request):
    return _build(request.param)


@pytest.fixture(scope="module")
def offshore():
    return _build("offshore")


@pytest.fixture(scope="module")
def src():
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    out = {}
    for n in ("tower", "newyaw_bearing", "bedplate", "stator", "newNosePiece", "flange_2", "flange_2_2",
              "misc_equipment", "newRotor", "Hub", "shaft"):
        s = TopoDS_Shape()
        BRepTools.Read_s(s, os.path.join(WORK, "src_T", f"{n}.brep"), BRep_Builder())
        out[n] = s
    return out


def _src_in(src, variant, name):
    """A source part in the variant's frame (onshore: 14 m lower)."""
    s = src[name]
    dz = _fit(variant)["z_shift"]
    return s if dz == 0 else occ.moved(s, occ.translate((0.0, 0.0, dz)))


def _tower_shape(fit, variant, src=None):
    """The tower as the converter leaves it: the source tower (or one made from the profile) without the door."""
    if src is not None:
        t = _src_in(src, variant, "tower")
    else:
        zs = [p[0] for p in fit["tower_profile"]]
        t = tp._tower(fit, zs[0], zs[-1])
    cuts = [tp.door_cut(fit, variant)]
    if variant == "onshore":                 # the monopile below the tower base is not there onshore
        zb = fit["tower_base_z"]
        cuts.append(occ.box((-20000.0, -20000.0, zb - 200000.0), (20000.0, 20000.0, zb)))
    return occ.cut(t, cuts[0]) if len(cuts) == 1 else occ.cut(occ.cut(t, cuts[0]), cuts[1])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _dist(a, b) -> float:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.Extrema import Extrema_ExtFlag_MIN
    d = BRepExtrema_DistShapeShape()
    d.SetFlag(Extrema_ExtFlag_MIN)
    d.SetMultiThread(True)
    d.LoadS1(a)
    d.LoadS2(b)
    d.Perform()
    assert d.IsDone()
    return float(d.Value())


def _box_gap(a, b) -> float:
    la, ha = occ.bbox(a)
    lb, hb = occ.bbox(b)
    return _gap(la, ha, lb, hb)


def _gap(la, ha, lb, hb) -> float:
    return float(np.linalg.norm(np.maximum(0.0, np.maximum(la - hb, lb - ha))))


_FACES: dict = {}


def _faces_boxed(shape) -> list:
    """The faces of a shape with their (quick, a little loose) boxes, kept for the shape."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    key = id(shape)
    if key not in _FACES:
        out = []
        for f in occ.faces(shape):
            b = Bnd_Box()
            BRepBndLib.Add_s(f, b, False)
            lo, hi = b.CornerMin(), b.CornerMax()
            out.append((f, np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])))
        _FACES[key] = (shape, out)                      # keeps the shape alive: ids stay unique
    return _FACES[key][1]


def _compound(faces):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for f in faces:
        b.Add(c, f)
    return c


def _near_dist(moving, fixed, margin=60.0) -> float:
    """Distance between two parts, measured only between faces whose boxes come within ``margin`` of the other
    part's nearby faces (a railing has thousands of faces; a whole-solid distance took seconds). inf when no face
    comes that near. Two solids that overlap have faces that cross: still 0."""
    def near(shape, lo, hi):
        return [(f, a, b) for f, a, b in _faces_boxed(shape) if _gap(lo, hi, a, b) <= margin]

    def box(faces):
        return np.min([a for _f, a, _b in faces], axis=0), np.max([b for _f, _a, b in faces], axis=0)
    fb = near(fixed, *occ.bbox(moving))
    if not fb:
        return math.inf
    mb = near(moving, *box(fb))
    if not mb:
        return math.inf
    fb = near(fixed, *box(mb))
    if not fb:
        return math.inf
    return _dist(_compound([f for f, _a, _b in mb]), _compound([f for f, _a, _b in fb]))


def _radial_gap(lo, hi) -> float:
    """How far a box stays from the z axis (its nearest point in x-y)."""
    return float(np.hypot(*np.clip(0.0, lo[:2], hi[:2])))


def _rot(axis_p, axis_d, deg) -> np.ndarray:
    d = np.asarray(axis_d, float)
    d /= np.linalg.norm(d)
    t = math.radians(deg)
    K = np.array([[0, -d[2], d[1]], [d[2], 0, -d[0]], [-d[1], d[0], 0]])
    R = np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(axis_p, float) - R @ np.asarray(axis_p, float)
    return M


def _corners(shape) -> np.ndarray:
    lo, hi = occ.bbox(shape)
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def _triangles(shape) -> int:
    """Triangles as the importer meshes the part at Normal (step_reader.mesh_params, FACETS)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRep import BRep_Tool
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    lin, ang = step_reader.QUALITY["normal"]
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    size = max(hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z())
    defl, rel, a = step_reader.mesh_params(lin, ang, size, step_reader.FACETS["normal"], False)
    BRepMesh_IncrementalMesh(shape, defl, rel, a, True)
    n = 0
    for f in occ.faces(shape):
        t = BRep_Tool.Triangulation_s(f, TopLoc_Location())
        if t is not None:
            n += t.NbTriangles()
    return n


def _inside(shape, p) -> bool:
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN
    c = BRepClass3d_SolidClassifier(shape, gp_Pnt(*map(float, p)), 1e-3)
    return c.State() == TopAbs_IN


def _vertex(p):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt
    return BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, p))).Vertex()


# ---------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------

def test_synthetic_numbers_match_the_measured(src):
    """The copy the repository's test machines use is the owner's measured fit (kept in step)."""
    for v in tp.VARIANTS:
        real, syn = _fit(v), _synthetic(v)
        for k in ("tower_top_z", "msl_z", "seabed_z", "tower_base_z", "z_shift"):
            assert real[k] == pytest.approx(syn[k], abs=0.5), (v, k)
        assert np.allclose(real["yaw_bearing_z"], syn["yaw_bearing_z"], atol=0.5)
        assert np.allclose(real["rotor"]["point"], syn["rotor"]["point"], atol=0.5)
        assert np.allclose(real["rotor"]["direction"], syn["rotor"]["direction"], atol=1e-6)
        assert np.allclose(np.array(real["tower_profile"], float), np.array(syn["tower_profile"], float), atol=0.5)


def test_every_part_is_one_valid_solid_with_a_known_name_and_body(built):
    v, fit, parts = built
    names = [p.name for p in parts]
    assert len(names) == len(set(names))
    for p in parts:
        assert p.name == p.name.upper() and p.name.strip() == p.name, p.name
        assert any(p.name.startswith(pre) for pre in tp.PREFIXES), p.name
        assert p.body in tp.BODIES, (p.name, p.body)
        assert occ.count(p.shape, "solid") == 1, p.name
        assert occ.is_valid(p.shape), p.name
        assert occ.volume(p.shape) > 0.0, p.name
    bodies = {p.body for p in parts}
    assert bodies == ({"TOWER", "NACELLE", "DOOR", "DAVIT"} if v == "offshore" else {"TOWER", "NACELLE", "DOOR"})
    must = {"NACELLE COVER", "NACELLE HATCH", "HELI DECK", "RAIL HELI", "LIGHT 1", "LIGHT 2", "SENSOR MAST",
            "YAW SEAL", "TOWER FLANGE 1", "TOWER FLANGE 3", "DOOR FRAME", "DOOR LEAF", "HANDLE DOOR"}
    must |= ({"TP SLEEVE", "GRATING DECK", "RAIL GATE", "DAVIT PEDESTAL", "DAVIT", "HOOK BLOCK", "CABINET",
              "LADDER", "RAIL CAGE 1", "GRATING REST PLATFORM", "BOAT LANDING 1", "FENDER 1", "J-TUBE 3"}
             if v == "offshore" else {"CONCRETE PEDESTAL", "CONCRETE SLAB", "GRAVEL APRON", "STEP STAIR"})
    assert must <= set(names), must - set(names)
    by = {p.name: p.body for p in parts}
    assert by["DOOR FRAME"] == "TOWER" and by["DOOR LEAF"] == "DOOR" and by["HANDLE DOOR"] == "DOOR"
    if v == "offshore":
        assert by["DAVIT PEDESTAL"] == "TOWER" and by["DAVIT"] == "DAVIT" and by["HOOK BLOCK"] == "DAVIT"


def test_triangles_under_budget(built):
    v, _fit_, parts = built
    total = 0
    print(f"\n{v}: triangles at the importer's Normal facets")
    for p in parts:
        n = _triangles(p.shape)
        total += n
        print(f"  {p.name:26s} {p.body:8s} {n:7d}")
    print(f"  {'total':26s} {'':8s} {total:7d}")
    assert total < BUDGET


def test_heights_and_layout(built):
    v, fit, parts = built
    by = {p.name: p.shape for p in parts}
    lo, hi = occ.bbox(by["NACELLE COVER"])
    assert lo[2] > fit["tower_top_z"] - 300.0 and lo[1] > -4400.0
    # the platform at the tower base, the J-tubes' bell-mouths just above the seabed (offshore)
    if v == "offshore":
        assert occ.bbox(by["GRATING DECK"])[1][2] == pytest.approx(fit["tower_base_z"], abs=0.5)
        for i in (1, 2, 3):
            jl, _jh = occ.bbox(by[f"J-TUBE {i}"])
            assert fit["seabed_z"] < jl[2] < fit["seabed_z"] + 600.0
        bl = occ.bbox(by["BOAT LANDING 1"])
        c = (bl[0] + bl[1]) / 2
        az = math.degrees(math.atan2(c[0], c[1])) % 360.0
        assert 120.0 < az < 150.0                                # front right (towards -y and +x)
        tl, th = occ.bbox(by["TP SLEEVE"])
        assert tl[2] == pytest.approx(tp.TP_BOTTOM, abs=1) and th[2] == pytest.approx(fit["tower_base_z"], abs=1)
    else:
        pl, ph = occ.bbox(by["CONCRETE PEDESTAL"])
        assert ph[2] == pytest.approx(fit["tower_base_z"], abs=0.5)
        sl, sh = occ.bbox(by["CONCRETE SLAB"])
        assert fit["ground_z"] < sh[2] < fit["ground_z"] + 200.0
        st_lo, _ = occ.bbox(by["STEP STAIR"])
        assert st_lo[2] == pytest.approx(sh[2], abs=1.0)        # the stair stands on the slab
    # tower flanges at three of the tower's section joints, round the tower
    zs = [p[0] for p in fit["tower_profile"]]
    for i in (1, 2, 3):
        fl, fh = occ.bbox(by[f"TOWER FLANGE {i}"])
        zc = (fl[2] + fh[2]) / 2
        assert min(abs(zc - z) for z in zs) < 1.0
        r = tp.tower_radius(fit, zc)
        assert r < fh[0] < r + 60.0


def test_joints_are_well_formed(built):
    v, fit, _parts = built
    js = tp.joints(fit, v)
    assert [j["name"] for j in js] == (["Door", "Davit"] if v == "offshore" else ["Door"])
    for j in js:
        assert j["kind"] == "ROTATE" and j["body"] in ("DOOR", "DAVIT")
        assert len(j["point"]) == 3 and np.isfinite(j["point"]).all()
        assert np.linalg.norm(j["direction"]) == pytest.approx(1.0)
        lo, hi = j["limits"]
        assert lo < hi
    door = js[0]
    assert door["limits"] == [0.0, tp.DOOR_OPEN]
    assert door["point"][2] == pytest.approx(tp.threshold_z(fit, v))
    # the hinge stands just outside the tower's skin
    assert tp.tower_radius(fit, door["point"][2]) < np.hypot(*door["point"][:2]) < tp.tower_radius(fit, 0) + 300


def test_the_door_opens_outwards(built):
    v, fit, parts = built
    j = tp.joints(fit, v)[0]
    leaf = next(p.shape for p in parts if p.name == "DOOR LEAF")
    r0 = np.hypot(*((occ.bbox(leaf)[0] + occ.bbox(leaf)[1]) / 2)[:2])
    opened = occ.moved(leaf, _rot(j["point"], j["direction"], 90.0))
    r1 = np.hypot(*((occ.bbox(opened)[0] + occ.bbox(opened)[1]) / 2)[:2])
    assert r1 > r0 + 300.0


def _door_neighbours(parts, fit, variant, src=None):
    fixed = [p.shape for p in parts if p.body == "TOWER"]
    fixed.append(_tower_shape(fit, variant, src))
    return fixed


def _sweep_gap(moving, fixed, axis_p, axis_d, angles) -> float:
    best = math.inf
    for a in angles:
        M = _rot(axis_p, axis_d, a)
        for m in moving:
            mm = occ.moved(m, M)
            for f in fixed:
                best = min(best, _near_dist(mm, f))
    return best


def _check_door(parts, fit, v, src=None):
    j = tp.joints(fit, v)[0]
    moving = [p.shape for p in parts if p.body == "DOOR"]
    gap = _sweep_gap(moving, _door_neighbours(parts, fit, v, src), j["point"], j["direction"],
                     np.linspace(j["limits"][0], j["limits"][1], 11))
    print(f"\n{v}: door leaf + handle, smallest gap over the swing: {gap:.1f} mm")
    assert gap > MOVE_GAP


def test_door_swing_is_clear(built):
    v, fit, parts = built
    _check_door(parts, fit, v)


def test_davit_slew_is_clear(offshore):
    v, fit, parts = offshore
    j = tp.joints(fit, v)[1]
    moving = [p.shape for p in parts if p.body == "DAVIT"]
    fixed = [p.shape for p in parts if p.body == "TOWER"] + [_tower_shape(fit, v)]
    gap = _sweep_gap(moving, fixed, j["point"], j["direction"], np.linspace(j["limits"][0], j["limits"][1], 13))
    print(f"\ndavit + hook over its slew: smallest gap {gap:.1f} mm")
    assert gap > MOVE_GAP
    # its jib never reaches the tower: the hook's farthest swing stays metres off
    hook = next(p.shape for p in parts if p.name == "HOOK BLOCK")
    for a in j["limits"]:
        h = occ.moved(hook, _rot(j["point"], j["direction"], a))
        c = (occ.bbox(h)[0] + occ.bbox(h)[1]) / 2
        assert np.hypot(c[0], c[1]) > tp.tower_radius(fit, c[2]) + 2000.0


def _s_max(shape, hub, d) -> float:
    """How far upwind (along the rotor axis from the hub centre) the part reaches (its box's corners)."""
    return float(((_corners(shape) - hub) @ d).max())


def test_nothing_reaches_the_turning_rotor_or_the_blades(built):
    """What turns with the rotor stays within ROTOR_S_MIN downwind of the hub; a blade point, pitching, within
    BLADE_RHO. Every part of ours stays farther downwind (the nacelle's by 100 mm from the generator), also with
    the nacelle yawed +-10° (tower parts against the yawed rotor)."""
    v, fit, parts = built
    hub0 = np.asarray(fit["rotor"]["point"], float)
    d0 = np.asarray(fit["rotor"]["direction"], float)
    limit = min(ROTOR_S_MIN, -BLADE_RHO)
    worst = {}
    for p in parts:
        yaws = (0.0,) if p.body == "NACELLE" else (-10.0, 0.0, 10.0)
        for yaw in yaws:
            M = _rot((0, 0, 0), (0, 0, 1), yaw)
            hub, d = M[:3, :3] @ hub0 + M[:3, 3], M[:3, :3] @ d0
            s = _s_max(p.shape, hub, d)
            worst[p.body] = max(worst.get(p.body, -math.inf), s)
            assert s < limit - NACELLE_GAP, (p.name, yaw, s)
    print(f"\n{v}: most upwind point of ours: " + ", ".join(f"{b} {s:.0f}" for b, s in worst.items())
          + f" mm (the rotor reaches {limit:.0f})")


def test_anchors_lie_on_their_parts(built):
    v, fit, parts = built
    by = {p.name: p.shape for p in parts}
    by[tp.TOWER_PART] = _tower_shape(fit, v)
    an = tp.anchors(fit, v)
    texts = [a.get("text") for a in an]
    assert texts.count(tp.TURBINE_ID) == (2 if v == "offshore" else 1)
    stickers = [a.get("sticker") for a in an]
    assert "WARN_GENERAL" in stickers and "NO UNAUTHORISED ACCESS" in texts
    if v == "offshore":
        assert {"N 0°", "E 90°", "S 180°", "W 270°", "SWL 1 t"} <= set(texts) and "WARN_LOAD" in stickers
    for a in an:
        assert a["kind"] in ("TEXT", "STICKER")
        assert (a["kind"] == "TEXT") == ("text" in a) and (a["kind"] == "STICKER") == ("sticker" in a)
        assert a["width_mm"] > 0
        n, up = np.asarray(a["normal"], float), np.asarray(a["up"], float)
        assert np.linalg.norm(n) == pytest.approx(1.0) and np.linalg.norm(up) == pytest.approx(1.0)
        assert abs(n @ up) < 1e-6
        shape = by[a["part"]]
        p = np.asarray(a["point"], float)
        assert _dist(_vertex(p), shape) < 1.0, a
        assert not _inside(shape, p + 5.0 * n) and _inside(shape, p - 5.0 * n), a       # outward normal
    if v == "offshore":                                         # the heading marks at their compass directions
        for a in an:
            if a.get("text", "").startswith(("N ", "E ", "S ", "W ")):
                az = math.degrees(math.atan2(a["point"][0], a["point"][1])) % 360.0
                want = float(a["text"].split()[1].rstrip("°"))
                assert abs((az - want + 180.0) % 360.0 - 180.0) < 0.01


def test_cameras(built):
    v, fit, _parts = built
    cams = {c["name"]: c for c in tp.cameras(fit, v)}
    assert set(cams) == ({"Work boat", "Whole turbine"} if v == "offshore" else {"From the field"})
    for c in cams.values():
        assert 10.0 < c["lens"] < 200.0
        assert np.linalg.norm(np.subtract(c["target"], c["eye"])) > 10000.0
    if v == "offshore":
        e = np.asarray(cams["Work boat"]["eye"])
        assert fit["msl_z"] + 1000 < e[2] < fit["msl_z"] + 6000 and 20000 < np.hypot(e[0], e[1]) < 30000
        assert 18.0 <= cams["Work boat"]["lens"] <= 30.0
        assert cams["Work boat"]["target"][2] > e[2] + 10000      # looking up
    else:
        e = np.asarray(cams["From the field"]["eye"])
        assert e[2] == pytest.approx(fit["ground_z"] + 1700.0) and 60000 < np.hypot(e[0], e[1]) < 80000


# ---------------------------------------------------------------------------
# against the owner's model (not collected where it is not)
# ---------------------------------------------------------------------------

def test_rotor_reach_measured(src):
    """ROTOR_S_MIN is what the generator rotor, hub and shaft reach downwind (as measured)."""
    from site_projects.iea15_source import _mesh_points
    fit = _fit("offshore")
    hub, d = np.asarray(fit["rotor"]["point"]), np.asarray(fit["rotor"]["direction"])
    s = math.inf
    for n in ("newRotor", "Hub", "shaft"):
        occ.tri_count(src[n], 5.0, 10.0)
        s = min(s, float(((_mesh_points(src[n]) - hub) @ d).min()))
    assert s == pytest.approx(ROTOR_S_MIN, abs=5.0)


def test_nacelle_parts_clear_the_drivetrain_and_the_tower(built, src):
    v, fit, parts = built
    nac = [p for p in parts if p.body == "NACELLE"]
    fixed_nacelle = [_src_in(src, v, n) for n in ("bedplate", "stator", "newNosePiece", "flange_2", "flange_2_2",
                                                  "misc_equipment")]
    turning = [_src_in(src, v, n) for n in ("newRotor", "Hub", "shaft")]
    tower = [_src_in(src, v, "tower"), _src_in(src, v, "newyaw_bearing")]
    gaps = {"drivetrain": math.inf, "generator": math.inf, "tower (yaw +-10°)": math.inf}
    for p in nac:
        for f in fixed_nacelle:
            if _box_gap(p.shape, f) < 500.0:
                gaps["drivetrain"] = min(gaps["drivetrain"], _near_dist(p.shape, f, 1000.0))
        for f in turning:
            if _box_gap(p.shape, f) < 500.0:
                gaps["generator"] = min(gaps["generator"], _near_dist(p.shape, f, 1000.0))
        for yaw in (-10.0, 0.0, 10.0):
            m = occ.moved(p.shape, _rot((0, 0, 0), (0, 0, 1), yaw))
            for f in tower:
                if _box_gap(m, f) < 500.0:
                    gaps["tower (yaw +-10°)"] = min(gaps["tower (yaw +-10°)"], _near_dist(m, f, 1000.0))
    print(f"\n{v}: smallest gaps of the nacelle parts: " + ", ".join(f"{k} {g:.0f} mm" for k, g in gaps.items()))
    assert gaps["drivetrain"] > 10.0
    assert gaps["generator"] >= NACELLE_GAP
    assert gaps["tower (yaw +-10°)"] > 20.0


def test_tower_parts_do_not_run_into_the_tower(built, src):
    """Nothing of ours inside the source tower (with its door cut out) or the yaw bearing."""
    v, fit, parts = built
    tower = _tower_shape(fit, v, src)
    bearing = _src_in(src, v, "newyaw_bearing")
    r_max = max(r for _z, r in fit["tower_profile"]) + 50.0
    worst, touching = math.inf, []
    for p in parts:
        if p.body == "NACELLE":
            continue
        near = [f for f, lo, hi in _faces_boxed(p.shape) if _radial_gap(lo, hi) <= r_max]
        if not near:
            continue
        near = _compound(near)
        for f in (tower, bearing):
            if _box_gap(near, f) > 50.0:
                continue
            g = _dist(near, f)
            if g < 1e-3:                                      # touching is fine, overlapping is not
                vol = occ.volume(occ.common(p.shape, f))
                assert vol < 1e3, (p.name, vol)
                touching.append(p.name)
            else:
                worst = min(worst, g)
    print(f"\n{v}: our tower parts against the source tower: touching {sorted(set(touching))}, "
          f"else at least {worst:.1f} mm")


def test_door_swing_is_clear_of_the_real_tower(built, src):
    v, fit, parts = built
    _check_door(parts, fit, v, src)


if not HAVE_SRC:
    # GitHub's test groups allow one skipped test each (tools/ci_pytest_summary.py): without the owner's model
    # these are not collected at all, rather than skipped.
    del (test_synthetic_numbers_match_the_measured, test_rotor_reach_measured,
         test_nacelle_parts_clear_the_drivetrain_and_the_tower, test_tower_parts_do_not_run_into_the_tower,
         test_door_swing_is_clear_of_the_real_tower)
