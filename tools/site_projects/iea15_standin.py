"""A small stand-in for the owner's STEP of the IEA 15 MW turbine (task 0116, independent tests).

GitHub's test machines cannot see the owner's ``15MW.step`` (it lies on the draft release ``site-kit``), so the
converter (``iea15_source.read / measure / fit``, ``iea15.convert``) is tested on this file instead: the same
assembly structure and names as the owner's file, the same axes and sizes (measured from his file on 13 Nov 2026 in
the turbine frame and copied here), but simple shapes – a few hundred kB, made in a second or two with OpenCascade.

    15MW                                                    (free shape, an assembly)
      tower:1               -> "tower"                      ONE hollow solid, pile tip -75 m to the top +144.582 m
      assem_rotor:1         -> "assem_rotor"                the nacelle and rotor, placed by a matrix of its own
        newNosePiece:1, bedplate:1 (a big solid + a sliver), newRotor:1, stator:1, shaft:1, Hub:1 (a hollow sphere
        cut by three blade rings + a ball at its centre), newyaw_bearing:1, misc_equipment:1, flange_2:1, flange_2:2,
        SRB_mock_bearing:1, TDO_mock_bearing:1
      IEA-15-240-RWT_TipShape_V1_high_resolution:1 .. :3   -> one blade assembly, three times
        =>[0:1:1:16] -> "SHELL"   the blade's open skin, 117 m along its own z, pre-bent 4 m towards its -x
        =>[0:1:1:17] -> "SOLID"   a disc 2 m across, 10 mm thick, at the root

As in the owner's file the blades are drawn for a rotor that turns ANTICLOCKWISE seen from the front: their leading
edge lies on the blade's +y side (the blade's x points downwind along the shaft). The whole turbine stands in a world
placement of its own (``WORLD``: turned about z and moved, not the owner's), so ``TFrame`` has to undo it; every leaf
has a placement of its own too (tower drawn along its y as in the owner's file).

``write(path)`` writes the STEP; ``T_TO_WORLD`` is the turbine frame -> STEP world; the module's numbers (``HUB``,
``UPWIND``, ``BLADE_DIRS``, ``TOWER_PROFILE`` ...) are what a test expects ``measure`` to find. No Blender.
"""

from __future__ import annotations

import math

import numpy as np

from . import occ

# --- the owner's file, measured in the turbine frame (mm; ~/iea/work/measure.json, 13 Nov 2026) -------------------
TILT_DEG = 6.0
HUB = np.array([0.0, -11210.318451936466, 150488.0631820485])          # hub centre: on the shaft axis
UPWIND = np.array([0.0, -math.cos(math.radians(TILT_DEG)), math.sin(math.radians(TILT_DEG))])
DOWN = -UPWIND
BLADE_DIRS = [np.array(d) for d in (
    (0.9737887828691113, 0.023775370720865045, 0.22620817426737796),
    (-0.6838754940020739, 0.0762637684636728, 0.7256019200106479),
    (-0.2899132888670343, -0.10003933634557552, -0.9518100735555578))]
HUB_TO_BLADE = 3000.0
HUB_R_OUT, HUB_R_IN, HUB_BALL_R, HUB_BACK_R = 3970.0, 3880.0, 100.0, 1625.0
BLADE_LENGTH = 117000.0
PREBEND = 4000.0
ROOT_R = 2600.0
TOWER_TOP = 144582.0
TOWER_WALL = 55.0
TOWER_PROFILE = [(-75000.0, 5000.0), (28000.0, 5000.0), (41000.0, 4963.0), (54000.0, 4721.5), (67000.0, 4416.5),
                 (80000.0, 4075.5), (93000.0, 3695.0), (106000.0, 3454.5), (119000.0, 3374.0), (132000.0, 3286.0),
                 (TOWER_TOP, 3250.0)]
YAW_BEARING = (3000.0, 3250.0, TOWER_TOP, TOWER_TOP + 380.0)           # r in, r out, z0, z1
DRUM = (1000.0, TOWER_TOP + 380.0, TOWER_TOP + 1380.0)                  # misc_equipment: r, z0, z1
# drivetrain: (r in, r out, s0, s1) along the shaft, s = mm downwind of the hub's centre (the owner's parts' extents)
SHAFT = (1400.0, 1500.0, 3929.0, 6129.0)
NOSE = (1000.0, 1100.0, 4354.0, 6554.0)
FLANGES = [(800.0, 1200.0, 6554.0, 6654.0), (800.0, 1200.0, 6654.0, 6754.0)]
SRB = (1100.0, 1400.0, 5619.0, 6089.0)
TDO = (1100.0, 1400.0, 4504.0, 4804.0)
# generator: (s, r) outlines revolved about the shaft (a cup turning round the stator, the rotor's back at y -4430)
GEN_ROTOR = [(3988.0, 1500.0), (3988.0, 5263.5), (6264.0, 5263.5), (6264.0, 5136.2), (4088.0, 5136.2),
             (4088.0, 1500.0)]
STATOR = [(4200.0, 4564.5), (4200.0, 4658.0), (6343.0, 4658.0), (6343.0, 1100.0), (6143.0, 1100.0),
          (6143.0, 4564.5)]
BEDPLATE = ((-2500.0, -3000.0, TOWER_TOP + 380.0), (2500.0, 3000.0, 148500.0))
BEDPLATE_SLIVER = ((-2400.0, -3010.0, 147000.0), (2400.0, -3000.0, 147010.0))

ROTOR_DIAMETER_M = 2.0 * (HUB_TO_BLADE + BLADE_LENGTH) / 1000.0         # 240 (no precone)
HUB_HEIGHT_M = HUB[2] / 1000.0
OVERHANG_M = float(np.hypot(HUB[0], HUB[1])) / 1000.0

# --- where the stand-in stands in its STEP's world (NOT the owner's placement) ---------------------------------------
WORLD_TURN_DEG = 131.7                    # the turbine frame turned this much about z ...
WORLD_SHIFT = (-23456.7, 65432.1, 41234.5)  # ... then moved: the tower axis at x, y, sea level (MSL) at z
BLADE_PROTO = "IEA-15-240-RWT_TipShape_V1_high_resolution"


def T_TO_WORLD() -> np.ndarray:
    return occ.translate(WORLD_SHIFT) @ occ.rot_z(WORLD_TURN_DEG)


def blade_frame(i: int) -> np.ndarray:
    """Blade i's own frame in the turbine frame: origin on the hub's ring (3 m from the centre), z along the blade,
    x downwind along the shaft (the owner's file: x_axis ~ +y of the turbine frame)."""
    d = BLADE_DIRS[i]
    return occ.frame(HUB + HUB_TO_BLADE * d, d, DOWN)


def shaft_frame() -> np.ndarray:
    """z downwind along the shaft from the hub's centre."""
    return occ.frame(HUB, DOWN, np.array([0.0, 0.0, 1.0]))


# ---------------------------------------------------------------------------
# shapes in the turbine frame
# ---------------------------------------------------------------------------

def _revolve(outline, frame=None):
    """A solid of revolution: ``outline`` = closed [(axial, radius)] about the z axis of ``frame`` (default T)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt
    p = BRepBuilderAPI_MakePolygon()
    for s, r in outline:
        p.Add(gp_Pnt(float(r), 0.0, float(s)))
    p.Close()
    face = BRepBuilderAPI_MakeFace(p.Wire()).Face()
    solid = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi).Shape()
    solid = occ.one_solid(solid, "revolved")
    return solid if frame is None else occ.moved(solid, frame)


def _ring(r_in, r_out, s0, s1, frame=None):
    return _revolve([(s0, r_in), (s0, r_out), (s1, r_out), (s1, r_in)], frame)


def tower():
    out = [(z, r) for z, r in TOWER_PROFILE]
    inner = [(z, r - TOWER_WALL) for z, r in reversed(TOWER_PROFILE)]
    return _revolve(out + inner)


def _sphere(c, r):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeSphere(gp_Pnt(*map(float, c)), float(r)).Shape()


def _cylinder(frame, r, h):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    return occ.moved(BRepPrimAPI_MakeCylinder(float(r), float(h)).Shape(), frame)


def hub():
    """A hollow sphere cut flat square to each blade 3 m from the centre (the blade rings), open at the back for the
    shaft, + a ball 0.2 m across at the centre (a second solid, as in the owner's file)."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    shell = occ.cut(_sphere(HUB, HUB_R_OUT), _sphere(HUB, HUB_R_IN))
    for i in range(3):
        shell = occ.cut(shell, _cylinder(blade_frame(i), 3500.0, 2000.0))
    shell = occ.cut(shell, _cylinder(shaft_frame(), HUB_BACK_R, HUB_R_OUT + 500.0))
    shell = occ.one_solid(shell, "hub")
    ball = occ.one_solid(_sphere(HUB, HUB_BALL_R), "ball")
    comp = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(comp)
    b.Add(comp, shell)
    b.Add(comp, ball)
    return comp


def bedplate():
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    comp = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(comp)
    b.Add(comp, occ.one_solid(occ.box(*BEDPLATE)))
    b.Add(comp, occ.one_solid(occ.box(*BEDPLATE_SLIVER)))
    return comp


# --- the blade, in its own frame -------------------------------------------------------------------------------------

# span stations: (z mm, chord mm, thickness / chord, share of the airfoil (0 round, 1 airfoil), twist deg)
STATIONS = [(0.0, 0.0, 0.0, 0.0, 0.0), (4000.0, 0.0, 0.0, 0.0, 0.0), (20000.0, 5800.0, 0.40, 0.6, 12.0),
            (35000.0, 5500.0, 0.30, 1.0, 8.0), (60000.0, 4500.0, 0.24, 1.0, 3.0), (90000.0, 3000.0, 0.21, 1.0, 0.5),
            (110000.0, 1600.0, 0.20, 1.0, 0.0)]
N_SECTION = 40
LE_SIGN = +1.0                  # the leading edge on the blade's +y side: it leads an anticlockwise turn (front view)


def prebend_x(z: float) -> float:
    """The blade's centre line off its own z axis (towards -x, upwind): 0 to 30 m, then a parabola to -4 m."""
    return -PREBEND * max(0.0, (z - 30000.0) / (BLADE_LENGTH - 30000.0)) ** 2


def section_points(z, chord, tc, share, twist_deg, le_sign=LE_SIGN, flatback=0.0) -> np.ndarray:
    """N points of a section (blade coordinates), starting at the trailing edge: a circle r ROOT_R blended with a
    NACA-00xx airfoil whose chord lies along y (leading edge at le_sign * 0.3 chord) and thickness along x."""
    th = np.linspace(0.0, 2 * math.pi, N_SECTION, endpoint=False)
    circ = np.c_[ROOT_R * np.sin(th), -ROOT_R * np.cos(th)]
    xi = (1.0 + np.cos(th)) / 2.0                         # 1 at the trailing edge (th 0), 0 at the leading edge
    half = 5.0 * tc * chord * (0.2969 * np.sqrt(xi) - 0.126 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3
                               - 0.1036 * xi ** 4)
    half = half + flatback * chord * xi ** 2               # a thick (flat-back) trailing edge
    air = np.c_[np.sign(np.sin(th)) * half, chord * (0.3 - xi)]
    xy = (1.0 - share) * circ + share * air
    xy[:, 1] *= le_sign
    a = math.radians(twist_deg)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    xy = xy @ R.T
    xy[:, 0] += prebend_x(z)
    return np.c_[xy, np.full(len(xy), z)]


def _periodic_edge(pts: np.ndarray):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.gp import gp_Pnt
    from OCP.collections import HArray1_gp_Pnt
    arr = HArray1_gp_Pnt(1, len(pts))
    for i, p in enumerate(pts, start=1):
        arr.SetValue(i, gp_Pnt(*map(float, p)))
    it = GeomAPI_Interpolate(arr, True, 1e-6)
    it.Perform()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(it.Curve()).Edge()).Wire()


def blade_skin(le_sign=LE_SIGN, stations=None, flatback=0.0):
    """The open skin (a SHELL: one lofted face, open at the root, closed in a point at the tip)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Pnt
    loft = BRepOffsetAPI_ThruSections(False, False, 1e-6)
    for z, c, tc, share, tw in (stations or STATIONS):
        loft.AddWire(_periodic_edge(section_points(z, c, tc, share, tw, le_sign, flatback)))
    loft.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(prebend_x(BLADE_LENGTH), 0.0, BLADE_LENGTH)).Vertex())
    loft.CheckCompatibility(False)
    loft.Build()
    shells = _shells(loft.Shape())
    if len(shells) != 1:
        raise RuntimeError(f"blade skin: {len(shells)} shells")
    return shells[0]


def _shells(shape) -> list:
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out, e = [], TopExp_Explorer(shape, TopAbs_SHELL)
    while e.More():
        out.append(TopoDS.Shell(e.Current()) if not hasattr(TopoDS, "Shell_s") else TopoDS.Shell_s(e.Current()))
        e.Next()
    return out


def blade_disc():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    return occ.one_solid(BRepPrimAPI_MakeCylinder(1000.0, 10.0).Shape(), "disc")


# ---------------------------------------------------------------------------
# the STEP
# ---------------------------------------------------------------------------

def _turn(seed: int) -> np.ndarray:
    """A rigid turn of its own for every leaf (so the reader really has to multiply placements out)."""
    rng = np.random.default_rng(seed)
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R
    return M


Y_UP = np.array([[1.0, 0, 0, 0], [0, 0, -1.0, 0], [0, 1.0, 0, 0], [0, 0, 0, 1.0]])   # own y -> world z (as tower:1)


def rotor_leaves() -> list[tuple[str, object]]:
    """(prototype name, shape in the turbine frame) of the assem_rotor's leaves, in the owner's order."""
    S = shaft_frame()
    return [
        ("newNosePiece", _ring(*NOSE, S)),
        ("bedplate", bedplate()),
        ("newRotor", _revolve(GEN_ROTOR, S)),
        ("stator", _revolve(STATOR, S)),
        ("shaft", _ring(*SHAFT, S)),
        ("Hub", hub()),
        ("newyaw_bearing", _ring(YAW_BEARING[0], YAW_BEARING[1], YAW_BEARING[2], YAW_BEARING[3])),
        ("misc_equipment", _revolve([(DRUM[1], 0.0), (DRUM[1], DRUM[0]), (DRUM[2], DRUM[0]), (DRUM[2], 0.0)])),
        ("flange_2", _ring(*FLANGES[0], S)),
        ("SRB_mock_bearing", _ring(*SRB, S)),
        ("TDO_mock_bearing", _ring(*TDO, S)),
        ("flange_2", _ring(*FLANGES[1], S)),
    ]


def write(path: str, le_sign: float = LE_SIGN) -> dict:
    """The stand-in STEP. Returns {"world": T -> STEP world, "leaves": number of leaves}."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    W = T_TO_WORLD()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def loc(M):
        return TopLoc_Location(occ.trsf(M))

    def proto(text, shape_T, P):
        """A prototype whose own coordinates are P (in the turbine frame): stored as inv(P) @ shape."""
        lab = st.AddShape(occ.moved(shape_T, np.linalg.inv(P)), False)
        name(lab, text)
        return lab

    root = st.NewShape()
    name(root, "15MW")
    n = 0
    # the tower, drawn along its own y
    P = Y_UP
    comp = st.AddComponent(root, proto("tower", tower(), P), loc(W @ P))
    name(comp, "tower:1")
    n += 1
    # the nacelle and rotor: an assembly placed by a matrix of its own, every leaf with a turn of its own
    A = W @ occ.translate((300.0, -200.0, 140000.0)) @ _turn(1)
    asm = st.NewShape()
    name(asm, "assem_rotor")
    comp = st.AddComponent(root, asm, loc(A))
    name(comp, "assem_rotor:1")
    seen: dict = {}
    leaves = rotor_leaves()
    for k, (pname, shape) in enumerate(leaves):
        lo, hi = occ.bbox(shape)
        P = occ.translate((lo + hi) / 2.0) @ _turn(10 + k)
        if pname not in seen:
            seen[pname] = (proto(pname, shape, P), P)
            Pl = P
        else:                                             # a second copy of a prototype (flange_2:2)
            lab, P0 = seen[pname]
            Pl = _same_shape_frame(shape, P0)
        lab = seen[pname][0]
        count = sum(1 for nm, _s in leaves[:k + 1] if nm == pname)
        comp = st.AddComponent(asm, lab, loc(np.linalg.inv(A) @ W @ Pl))
        name(comp, f"{pname}:{count}")
        n += 1
    # the blade: one assembly (skin + root disc), placed three times
    Q = occ.translate((12.5, -7.0, 3.0)) @ _turn(99)
    blade = st.NewShape()
    name(blade, BLADE_PROTO)
    skin = st.AddShape(blade_skin(le_sign), False)
    name(skin, "SHELL")
    disc = st.AddShape(blade_disc(), False)
    name(disc, "SOLID")
    c = st.AddComponent(blade, skin, loc(Q))
    name(c, "=>[0:1:1:16]")
    c = st.AddComponent(blade, disc, loc(Q))
    name(c, "=>[0:1:1:17]")
    for i in range(3):
        comp = st.AddComponent(root, blade, loc(W @ blade_frame(i) @ np.linalg.inv(Q)))
        name(comp, f"{BLADE_PROTO}:{i + 1}")
        n += 2
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"could not write {path}")
    return {"world": W, "leaves": n}


def _same_shape_frame(shape_T, P0) -> np.ndarray:
    """The frame that puts the first copy's prototype (stored in P0's coordinates) onto ``shape_T``: the flanges are
    the same ring moved along the shaft."""
    d = FLANGES[1][2] - FLANGES[0][2]
    return occ.translate(DOWN * d) @ P0
