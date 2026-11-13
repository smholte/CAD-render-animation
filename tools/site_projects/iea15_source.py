"""The owner's STEP of the IEA 15 MW reference turbine, read and measured (task 0116).

The owner opened the IEA's SolidWorks assembly (``CAD/deprecated/IEA-15-240-RWT_Solidworks.zip``, top ``15MW.SLDASM``)
in Fusion and exported ``15MW.step``; it lies on the draft release ``site-kit``. What is in it (read 13 Nov 2026):

    tower:1                 ONE solid: the monopile (pile tip -75 m) and the tower (to its top at +144.58 m above
                            the sea), 10 m across up to +28 m, then cones to 6.5 m
    assem_rotor:1           the nacelle and rotor: bedplate (3 solids), yaw bearing, misc_equipment (a drum on the yaw
                            axis), nose (the fixed turret), stator, flange_2 x 2, newRotor (the generator's rotor),
                            shaft, Hub (2 solids), SRB_mock_bearing and TDO_mock_bearing (plain rings that stand in
                            for the main bearings)
    IEA-15-240-RWT_TipShape_V1_high_resolution x 3
                            a blade each: an open SHELL (the blade's skin, 117 m along its own z) + a disc 2 m across
                            and 10 mm thick at its root (a modelling aid: no part of a real turbine)

``read(path)`` gives every leaf as (instance name, prototype name, shape in its own coordinates, 4 x 4 placement in
the STEP's world, mm). ``TFrame`` turns the STEP's world into the turbine's own: tower axis on z, sea level (MSL) at
z 0, the rotor upwind towards -y (the app's front views look at it), in mm. ``measure`` works the axes out from the
round faces (nothing is taken from the source's names alone) and compares them with the IEA's numbers (``IEA``).
"""

from __future__ import annotations

import json
import math

import numpy as np

from . import occ

# The IEA 15 MW reference turbine, version 1.0 (github.com/IEAWindSystems/IEA-15-240-RWT, tag v1.0 = commit
# 630f7cbc6a7092caf5b9c3d4401c8102a60728a4, Apache-2.0): the version the SolidWorks model is drawn from (its hub
# puts the blade roots 3 m from the centre, as v1.0 says; later versions changed the rotor). value, source.
IEA_COMMIT = "630f7cbc6a7092caf5b9c3d4401c8102a60728a4"
_TAB = "Documentation/IEA-15-240-RWT_tabular.xlsx, sheet Overview (IEA-15-240-RWT v1.0)"
_ED = "OpenFAST/IEA-15-240-RWT-Monopile/IEA-15-240-RWT-Monopile_ElastoDyn.dat (v1.0)"
_HD = "OpenFAST/IEA-15-240-RWT-Monopile/IEA-15-240-RWT-Monopile_HydroDyn.dat (v1.0)"
IEA = {
    "rotor_diameter_m": (240.0, _TAB + ": Rotor diameter [m]"),
    "hub_height_m": (150.0, _TAB + ": Hub height [m]"),
    "hub_diameter_m": (7.94, _TAB + ": Hub diameter [m]"),
    "hub_to_blade_m": (3.0, _TAB + ": Hub distance from center to blades [m]"),
    "overhang_m": (11.014, _TAB + ": Hub Overhang [m] (-11.014, upwind)"),
    "shaft_tilt_deg": (6.0, _TAB + ": Shaft tilt angle [deg]"),
    "precone_deg": (4.0, _TAB + ": Rotor pre-cone angle [deg] (-4, towards the wind)"),
    "prebend_m": (4.0, _TAB + ": Blade pre-bend [m]"),
    "blade_length_m": (117.0, "TipRad 120.0 - HubRad 3.0, " + _ED),
    "rated_rpm": (7.56, _TAB + ": Maximum rotor speed [rpm]"),
    "min_rpm": (5.0, _TAB + ": Minimum rotor speed [rpm]"),
    "tower_top_m": (144.495, "TowerHt, " + _ED),
    "tower_base_m": (15.0, "TowerBsHt, " + _ED + "; = " + _TAB + ": Transition piece height [m]"),
    "yaw_bearing_m": (0.38, _TAB + ": Tower top to nacelle (yaw bearing height) [m]"),
    "tower_base_diameter_m": (10.0, _TAB + ": Tower base diameter [m]"),
    "monopile_diameter_m": (10.0, _TAB + ": Monopile base diameter [m]"),
    "embedment_m": (45.0, _TAB + ": Monopile embedment depth [m]"),
    "water_depth_m": (30.0, "WtrDpth, " + _HD),
}


def value(key: str) -> float:
    return IEA[key][0]


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

class Leaf:
    """One placed shape of the source: ``shape`` in its own coordinates, ``M`` its placement (STEP world, mm)."""

    def __init__(self, inst: str, proto: str, path: tuple, shape, M: np.ndarray):
        self.inst, self.proto, self.path, self.shape, self.M = inst, proto, path, shape, M

    def __repr__(self):
        return f"Leaf({'/'.join(self.path + (self.inst,))})"


def read(path: str) -> list[Leaf]:
    """Every leaf shape of the STEP with its world placement (assembly placements multiplied out)."""
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
    if r.ReadFile(path) != 1:
        raise RuntimeError(f"could not read {path}")
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(lab):
        a = TDataStd_Name()
        return a.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), a) else ""

    out: list[Leaf] = []

    def walk(lab, M, path):
        ref = lab
        if st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            M = M @ occ.matrix_of(st.GetLocation_s(lab))
        inst = name(lab)
        if st.IsAssembly_s(ref):
            seq = Sequence_TDF_Label()
            st.GetComponents_s(ref, seq)
            for i in range(1, seq.Length() + 1):
                walk(seq.Value(i), M, path + (inst,))
        else:
            shape = st.GetShape_s(ref).Located(TopLoc_Location())
            out.append(Leaf(inst, name(ref), path, shape, M))

    seq = Sequence_TDF_Label()
    st.GetFreeShapes(seq)
    for i in range(1, seq.Length() + 1):
        walk(seq.Value(i), np.eye(4), ())
    return out


def by_proto(leaves: list[Leaf], proto: str) -> list[Leaf]:
    return [lf for lf in leaves if lf.proto == proto]


def one(leaves: list[Leaf], proto: str) -> Leaf:
    hits = by_proto(leaves, proto)
    if len(hits) != 1:
        raise RuntimeError(f"the STEP has {len(hits)} '{proto}' (need 1): is it the IEA 15 MW model?")
    return hits[0]


BLADE_PROTO = "IEA-15-240-RWT_TipShape_V1_high_resolution"


def blades(leaves: list[Leaf]) -> list[tuple[Leaf, Leaf]]:
    """(skin, root disc) of each blade, in the STEP's order."""
    out = []
    groups: dict = {}
    for lf in leaves:
        if lf.path and lf.path[-1].startswith(BLADE_PROTO):
            groups.setdefault(lf.path[-1], []).append(lf)
    for key in sorted(groups):
        g = groups[key]
        skin = [lf for lf in g if occ.count(lf.shape, "solid") == 0]
        disc = [lf for lf in g if occ.count(lf.shape, "solid") == 1]
        if len(skin) != 1 or len(disc) != 1:
            raise RuntimeError(f"blade {key}: {len(skin)} skins and {len(disc)} root discs (need 1 and 1)")
        out.append((skin[0], disc[0]))
    if len(out) != 3:
        raise RuntimeError(f"{len(out)} blades in the STEP (need 3)")
    return out


# ---------------------------------------------------------------------------
# the turbine's own frame
# ---------------------------------------------------------------------------

def _world_faces(lf: Leaf, M=None) -> list[dict]:
    """The faces of a leaf as ``occ.surface`` records in the world (M @ leaf placement)."""
    W = (np.eye(4) if M is None else M) @ lf.M
    R, t = W[:3, :3], W[:3, 3]
    out = []
    for f in occ.faces(lf.shape):
        s = occ.surface(f)
        s["centre"] = R @ s["centre"] + t
        if "point" in s:
            s["point"] = R @ s["point"] + t
        if "dir" in s:
            s["dir"] = R @ s["dir"]
        out.append(s)
    return out


def _axis_of(recs: list[dict], kinds=("cylinder",)) -> tuple[np.ndarray, np.ndarray, list[float]]:
    """The common axis of a part's round faces: (point, unit direction, radii). Raises when they disagree."""
    round_ = [s for s in recs if s["kind"] in kinds]
    if not round_:
        raise RuntimeError("no round faces")
    d0 = round_[0]["dir"] / np.linalg.norm(round_[0]["dir"])
    p0 = round_[0]["point"]
    for s in round_[1:]:
        d = s["dir"] / np.linalg.norm(s["dir"])
        if abs(abs(float(d @ d0)) - 1.0) > 1e-6:
            raise RuntimeError("round faces on different axes")
        off = (s["point"] - p0) - ((s["point"] - p0) @ d0) * d0
        if np.linalg.norm(off) > 0.5:
            raise RuntimeError(f"round faces {np.linalg.norm(off):.1f} mm off one axis")
    return p0, d0, sorted({round(s["r"], 1) for s in round_})


class TFrame:
    """STEP world -> the turbine's frame: tower axis = z (x = y = 0), sea level z = 0, rotor upwind along -y."""

    def __init__(self, leaves: list[Leaf]):
        tower = one(leaves, "tower")
        p, d, _r = _axis_of(_world_faces(tower), ("cylinder", "cone"))
        if abs(abs(d[2]) - 1.0) > 1e-9:
            raise RuntimeError("the tower does not stand along the STEP's z")
        lo, hi = occ.bbox(occ.moved(tower.shape, tower.M))
        tip = lo[2]                                        # the monopile's tip, 45 m below a 30 m deep seabed
        msl = tip + 1000.0 * (value("embedment_m") + value("water_depth_m"))
        shaft = one(leaves, "shaft")
        _sp, sd, _ = _axis_of(_world_faces(shaft))
        hub = one(leaves, "Hub")
        hub_c = [s for s in _world_faces(hub) if s["kind"] == "sphere"]
        towards_hub = hub_c[0]["point"][:2] - p[:2]
        if float(sd[:2] @ towards_hub) < 0:
            sd = -sd
        h = sd[:2] / np.linalg.norm(sd[:2])               # upwind, horizontal
        turn = math.degrees(math.atan2(-1.0, 0.0) - math.atan2(h[1], h[0]))   # h -> (0, -1)
        self.M = occ.rot_z(turn) @ occ.translate((-p[0], -p[1], -msl))
        self.turn_deg = turn
        self.tower_top_raw = float(hi[2] - msl)

    def apply(self, lf: Leaf) -> np.ndarray:
        return self.M @ lf.M


# ---------------------------------------------------------------------------
# measuring
# ---------------------------------------------------------------------------

def _line_closest(p1, d1, p2, d2) -> tuple[np.ndarray, float]:
    """The point midway between two lines where they come closest, and that distance."""
    w = p1 - p2
    a, b, c, d, e = d1 @ d1, d1 @ d2, d2 @ d2, d1 @ w, d2 @ w
    den = a * c - b * b
    s = (b * e - c * d) / den
    t = (a * e - b * d) / den
    q1, q2 = p1 + s * d1, p2 + t * d2
    return (q1 + q2) / 2, float(np.linalg.norm(q1 - q2))


def root_circle(skin: Leaf, W: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """The blade root's edge (all its points near the skin's z 0) fitted as a circle, in the frame W @ placement."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve  # noqa: F401
    best = None
    for e in occ.edges(skin.shape):
        pts = occ.edge_points(e, 96)
        if np.abs(pts[:, 2]).max() < 1.0 and np.ptp(pts[:, 0]) > 1000.0:
            best = pts if best is None else np.vstack([best, pts])
    if best is None:
        raise RuntimeError("the blade's root edge was not found")
    G = W @ skin.M
    pts = best @ G[:3, :3].T + G[:3, 3]
    return occ.fit_circle(pts)


def measure(leaves: list[Leaf], T: TFrame | None = None) -> dict:
    """The turbine's axes and sizes in the turbine frame (mm), each from round faces, and how they compare with
    the IEA's numbers. Every joint axis is checked from both sides: the part that turns and the part it turns in."""
    T = T or TFrame(leaves)
    M = T.M
    out: dict = {"turn_deg": round(T.turn_deg, 4)}

    def faces_of(proto):
        return _world_faces(one(leaves, proto), M)

    # yaw: the tower's top cone and the yaw bearing (tower side), the drum on the bedplate (nacelle side)
    tp, td, tr = _axis_of(faces_of("tower"), ("cylinder", "cone"))
    yp, yd, yr = _axis_of(faces_of("newyaw_bearing"))
    mp, md, mr = _axis_of(faces_of("misc_equipment"))
    out["yaw"] = {"point": [0.0, 0.0, 0.0], "direction": [0.0, 0.0, 1.0],
                  "tower_off_mm": float(np.hypot(*tp[:2])), "bearing_off_mm": float(np.hypot(*yp[:2])),
                  "nacelle_off_mm": float(np.hypot(*mp[:2])), "bearing_radii": yr, "nacelle_radii": mr}
    top = [s for s in faces_of("tower") if s["kind"] == "plane" and s["dir"][2] > 0.99]
    out["tower_top_z"] = float(max(s["centre"][2] for s in top))
    yb = [s for s in faces_of("newyaw_bearing") if s["kind"] == "plane"]
    out["yaw_bearing_z"] = sorted(float(s["centre"][2]) for s in yb)

    # rotor: the shaft (turns) and the nose (fixed) on one axis
    sp, sd, sr = _axis_of(faces_of("shaft"))
    np_, nd, nr = _axis_of(faces_of("newNosePiece"))
    hub = faces_of("Hub")
    centre = [s for s in hub if s["kind"] == "sphere"]
    hc = centre[0]["point"]
    if sd[1] > 0:                                          # point upwind (-y)
        sd = -sd
    off_nose = np.linalg.norm((np_ - sp) - ((np_ - sp) @ sd) * sd)
    out["rotor"] = {"point": [float(v) for v in hc], "direction": [float(v) for v in sd],
                    "shaft_radii": sr, "nose_radii": nr, "nose_off_mm": float(off_nose),
                    "nose_angle_deg": math.degrees(math.acos(min(1.0, abs(float(nd @ sd))))),
                    "hub_off_mm": float(np.linalg.norm((hc - sp) - ((hc - sp) @ sd) * sd))}
    out["shaft_tilt_deg"] = math.degrees(math.asin(abs(sd[2])))
    out["hub_height_m"] = hc[2] / 1000.0
    out["overhang_m"] = float(np.hypot(hc[0], hc[1])) / 1000.0

    # the hub's three blade openings (planar rings) and the blades' root circles
    rings = sorted((s for s in hub if s["kind"] == "plane" and abs(float(s["dir"] @ sd)) < 0.2),
                   key=lambda s: math.atan2(float((s["centre"] - hc) @ np.cross(sd, [0, 0, 1])),
                                            float((s["centre"] - hc)[2])))
    out["hub_rings"] = [{"centre": [float(v) for v in s["centre"]], "normal": [float(v) for v in s["dir"]],
                         "from_hub_mm": float(np.linalg.norm(s["centre"] - hc))} for s in rings]
    bl = []
    for i, (skin, disc) in enumerate(blades(leaves)):
        G = M @ skin.M
        axis_p, axis_d = G[:3, 3], G[:3, 2]
        c, n, r, worst = root_circle(skin, M)
        if float(n @ axis_d) < 0:
            n = -n
        ring = min(rings, key=lambda s: np.linalg.norm(s["centre"] - c))
        apex, miss = _line_closest(axis_p, axis_d, hc, sd)
        cone = 90.0 - math.degrees(math.acos(min(1.0, abs(float(axis_d @ sd)))))
        bl.append({"index": i + 1, "point": [float(v) for v in axis_p], "direction": [float(v) for v in axis_d],
                   "root_centre": [float(v) for v in c], "root_radius": r, "root_fit_mm": worst,
                   "root_off_axis_mm": float(np.linalg.norm((c - axis_p) - ((c - axis_p) @ axis_d) * axis_d)),
                   "root_normal_deg": math.degrees(math.acos(min(1.0, abs(float(n @ axis_d))))),
                   "ring_off_mm": float(np.linalg.norm((ring["centre"] - axis_p)
                                                       - ((ring["centre"] - axis_p) @ axis_d) * axis_d)),
                   "ring_normal_deg": math.degrees(math.acos(min(1.0, abs(float(ring["dir"] @ axis_d))))),
                   "apex": [float(v) for v in apex], "axis_miss_mm": miss, "cone_deg": cone,
                   "x_axis": [float(v) for v in G[:3, 0]]})
    out["blades"] = bl
    out["precone_deg"] = float(np.mean([b["cone_deg"] for b in bl]))

    # rotor diameter: the farthest blade point from the rotor axis, twice (the swept circle)
    skin = blades(leaves)[0][0]
    occ.tri_count(skin.shape, 20.0, 5.0)
    pts = _mesh_points(skin.shape)
    G = M @ skin.M
    P = pts @ G[:3, :3].T + G[:3, 3]
    rel = P - hc
    radial = rel - np.outer(rel @ sd, sd)
    out["rotor_diameter_m"] = 2.0 * float(np.linalg.norm(radial, axis=1).max()) / 1000.0
    loc = pts[:, 2]
    out["blade_length_m"] = float(loc.max() - loc.min()) / 1000.0
    out["prebend_m"] = float(np.abs(pts[np.argmax(loc), 0])) / 1000.0
    return out


def _mesh_points(shape) -> np.ndarray:
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    out = []
    for f in occ.faces(shape):
        tri = BRep_Tool.Triangulation_s(f, TopLoc_Location())
        if tri is None:
            continue
        for i in range(1, tri.NbNodes() + 1):
            p = tri.Node(i)
            out.append((p.X(), p.Y(), p.Z()))
    return np.array(out)


# ---------------------------------------------------------------------------
# what the invented parts are fitted to
# ---------------------------------------------------------------------------

VARIANTS = ("offshore", "onshore")
ONSHORE_SHIFT = -14000.0          # onshore: ground z 0, the tower base on a 1.0 m pedestal (T frame z +15 m -> +1 m)
SPLIT_Z = 15000.0                 # tower | monopile, T frame (IEA: tower base / transition piece height 15 m)


def tower_profile(leaves: list[Leaf], T: TFrame) -> list[tuple[float, float]]:
    """[(z, outer radius)] of the tower in the T frame, bottom to top: the round outer faces' ends (linear between)."""
    tower = one(leaves, "tower")
    W = T.M @ tower.M
    pts = {}
    for f in occ.faces(tower.shape):
        s = occ.surface(f)
        if s["kind"] not in ("cylinder", "cone") or not _faces_out(f):
            continue
        for e in occ.edges(f):
            p = occ.edge_points(e, 8) @ W[:3, :3].T + W[:3, 3]
            r = np.hypot(p[:, 0], p[:, 1])
            if np.ptp(p[:, 2]) < 1.0 and np.ptp(r) < 1.0:          # a ring edge
                z = round(float(p[0, 2]), 1)
                pts[z] = max(pts.get(z, 0.0), round(float(r.mean()), 1))
    out = sorted(pts.items())
    lo, _hi = occ.bbox(occ.moved(tower.shape, W))
    if out and lo[2] < out[0][0] - 1.0:                  # the straight 10 m tube runs on down to the pile tip
        out.insert(0, (round(float(lo[2]), 1), out[0][1]))
    return out


def _faces_out(face) -> bool:
    """A round face of the tower whose material normal points away from the axis (the outer skin, not the wall's
    inside)."""
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.gp import gp_Pnt, gp_Vec
    g = BRepGProp_Face(face)
    u0, u1, v0, v1 = g.Bounds()
    p, n = gp_Pnt(), gp_Vec()
    g.Normal((u0 + u1) / 2, (v0 + v1) / 2, p, n)
    return p.X() * n.X() + p.Y() * n.Y() > 0.0


def radius_at(profile: list[tuple[float, float]], z: float) -> float:
    zs = [p[0] for p in profile]
    return float(np.interp(z, zs, [p[1] for p in profile]))


def fit(leaves: list[Leaf], variant: str, T: TFrame | None = None, measured: dict | None = None) -> dict:
    """The numbers the invented parts are fitted to, in the variant's frame (mm)."""
    if variant not in VARIANTS:
        raise ValueError(variant)
    T = T or TFrame(leaves)
    m = json.loads(json.dumps(measured or measure(leaves, T), default=float))
    dz = ONSHORE_SHIFT if variant == "onshore" else 0.0

    def shift(p):
        return [p[0], p[1], p[2] + dz]
    m["rotor"]["point"] = shift(m["rotor"]["point"])
    for b in m["blades"]:
        for k in ("point", "root_centre", "apex"):
            b[k] = shift(b[k])
    for r in m["hub_rings"]:
        r["centre"] = shift(r["centre"])
    m["tower_top_z"] += dz
    m["yaw_bearing_z"] = [z + dz for z in m["yaw_bearing_z"]]
    m.update(variant=variant, z_shift=dz, msl_z=0.0 + dz, tower_base_z=SPLIT_Z + dz,
             seabed_z=-1000.0 * value("water_depth_m") + dz,
             tower_profile=[(z + dz, r) for z, r in tower_profile(leaves, T)])
    if variant == "onshore":
        zb = m["tower_base_z"]
        m["tower_profile"] = [(zb, radius_at(m["tower_profile"], zb))] + [
            p for p in m["tower_profile"] if p[0] > zb + 1e-6]
        m["ground_z"] = 0.0
    return m
