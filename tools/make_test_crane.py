"""Write the test crane – a service crane at real size (task 0259: x5 of the first one) – for the motion tests (two
revisions).

TEST.CRANE                      mm; the boom turns about Y at PIVOT (2.4 m up: the boom's underside 2.15 m, a 1.85 m
                                person walks under it)
  BASE                          base 5000 x 3000 x 500, corners and top edges chamfered, four bolt holes Ø33
  PEDESTAL                      a foot flange (60 thick) with gussets, a block 600 x 800 with chamfered corners and a fork
                                on top (two cheeks 80 thick with chamfered tops, bore Ø100.4) that carries the boom pin;
                                the boom turns between the cheeks, 100 mm above the block (task 0072: no part starts
                                inside another, so the clash check never sits on its threshold)
  ISO 4762 M24 x 60 - 12.9      x4, socket head screws holding the pedestal's foot down
  BOOM.ASM
    BOOM                        box girder 7500 x 500 x 500 from the pivot: round end round the pin, chamfered edges,
                                side ribs, the tip tapered underneath, an end stop on top
    BOOM.PIN                    cylinder Ø100 along Y at the pivot (pick target for the joint axis)
    BOOM.LUFF.PIN               Ø70 through the fork under the boom: the luffing cylinder's rod pin
  TROLLEY.ASM                   rides on the boom (a sibling of BOOM.ASM in the CAD tree)
    TROLLEY                     body 750 x 750 x 300 with chamfers and a hoist motor on top
    WHEEL                       x2, flanged wheels Ø300
  HYDRAULIC CYLINDER.ASM        luffing cylinder (task 0122): barrel pin in a fork on the pedestal's front, rod pin in a
                                fork under the boom; the piston can go 30 mm in and 700 mm out (boom up to ~37°)
    HYDRAULIC CYLINDER.BARREL   eye, end cap, tube (bore Ø200), gland, two ports
    HYDRAULIC CYLINDER.ROD      piston Ø198, rod Ø110, eye
  PEDESTAL.LUFF.PIN             Ø70 through the pedestal's fork: the barrel pin
  COVER                         plate 1500 x 1000 x 12 with chamfered corners, four screw heads and a handle
  ISO 4017 M30 x 120 - 8.8 HDG  x4, hex head bolts, the shank down in the base's holes

The layout (every place, length and travel) is the first crane's (tasks 0011–0122) x 5, the pedestal 400 mm taller
(head room under the boom); plates, pins, bolts, screws and the cylinder have real sizes for a crane of this size.

Revision B: one bolt removed, the bolts listed in another order, a new BOOM.LAMP in BOOM.ASM,
and the cover moved 50 mm.

usage: python make_test_crane.py out.step [A|B] [--inventor-names] [--plain]

``--plain`` writes the crane as plain boxes and cylinders (as tasks 0011–0072 had it). The old-project models
test_crane_inv_*.step and test_crane_plain.step in tests/data were made with the first (1/5 size) maker and stay as
they are: they stand for projects saved by older versions.
"""

import math
import os
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fresing_render.demo_model import geom as g  # noqa: E402
from model_details import chamfer, chamfered_rect, hex_bolt, hex_prism, socket_screw  # noqa: E402

S = 5.0                             # the layout: the first crane x S
DZ = 400.0                          # mm the pedestal is taller than S x the first one (head room under the boom)
PIVOT = (500.0, 1500.0, 2400.0)     # mm: boom pin centre
YELLOW = (0.976, 0.659, 0.0)        # RAL 1003-ish: the crane's paint (the groups' "Colour #F9A800")
GREY = (0.2, 0.2, 0.2)
BLUE = (0.075, 0.267, 0.486)
STEEL = (0.62, 0.64, 0.66)
BASE_H = 500.0                      # the base's top
BOLT_HOLES = [(250, 250), (4750, 250), (250, 2750), (4750, 2750)]
BOLT = "ISO 4017 M30 x 120 - 8.8 HDG"           # anchor bolts: M30, holes Ø33
SCREW = "ISO 4762 M24 x 60 - 12.9"              # the pedestal's foot screws: M24, holes Ø26
PED = (PIVOT[0] - 300, PIVOT[1] - 400, BASE_H)  # the pedestal's place (its own x 0..600, y 0..800)
PED_TOP = 1550.0                    # the block's top (pedestal space); the pivot 350 above it
PIVOT_LOCAL = (300.0, 1900.0)       # (x, z) of the pivot in pedestal space
FOOT_T = 60.0                       # the foot flange's thickness
FOOT = (-100.0, 700.0)              # the foot flange's screw places along x and y (pedestal space)
FOOT_Y = (-125.0, 925.0)
PIN_R, BORE_R = 50.0, 50.2          # the boom pin Ø100 and its bores
CHEEK_T = 80.0                      # the fork's cheeks; their inner faces 25 mm from the boom
COVER_T = 12.0
COVER_AT = (3000.0, 250.0)          # the cover's corner on the base; revision B lifts it by 50


def _z(z: float) -> float:
    """A height on the pedestal or above it, from the first crane's (pedestal space): x S, raised by DZ."""
    return z * S + DZ


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def base_shape():
    plate = g.polygon_prism(chamfered_rect(0, 0, 5000, 3000, 100), BASE_H)
    plate = chamfer(plate, 40.0, lambda p: abs(p[2] - BASE_H) < 1e-6)
    holes = [g.cyl(16.5, BASE_H + 2.0, (x, y, -1.0)) for x, y in BOLT_HOLES]
    return g.cut(plate, *holes)


def pedestal_shape(lug: bool = False):
    """In its own space: block x 0..600, y 0..800, z FOOT_T..PED_TOP on a foot flange z 0..FOOT_T; the pivot at
    (300, *, 1900)."""
    foot = g.polygon_prism(chamfered_rect(-175, -225, 950, 1250, 75), FOOT_T)
    foot = chamfer(foot, 10.0, lambda p: abs(p[2] - FOOT_T) < 1e-6)
    block = g.polygon_prism(chamfered_rect(0, 0, 600, 800, 60), PED_TOP - FOOT_T, g.T(0, 0, FOOT_T))
    parts = [foot, block]
    # the cheeks, tops chamfered (not round: a round top on the bore's axis would make the importer call the bore
    # "Ø500", since faces on one axis line share one axis with the largest radius)
    cheek = [(100.0, _z(200.0)), (500.0, _z(200.0)), (500.0, _z(318.0)), (410.0, _z(340.0)), (190.0, _z(340.0)),
             (100.0, _z(318.0))]
    for y_out in (125.0, 755.0):                # extruded towards -y from y_out: cheeks y 45..125 and 675..755
        parts.append(g.xform(g.polygon_prism(cheek, CHEEK_T), g.Frame((0, y_out, 0), (1, 0, 0), (0, -1, 0))))
    # gussets between the foot and the block: a triangle 125 out and 350 up, 25 thick
    tri = [(0.0, 0.0), (125.0, 0.0), (0.0, 350.0)]
    for side in ("-y", "+y", "-x") + (() if lug else ("+x",)):
        sgn = -1.0 if side[0] == "-" else 1.0
        if side[1] == "y":                       # local x outwards, local y up, extruded 25 along x
            out, at = (0, sgn, 0), (287.5 if sgn > 0 else 312.5, 0.0 if sgn < 0 else 800.0, FOOT_T)
            along = (sgn, 0, 0)
        else:
            out, at = (sgn, 0, 0), (0.0 if sgn < 0 else 600.0, 387.5 if sgn < 0 else 412.5, FOOT_T)
            along = (0, -sgn, 0)
        parts.append(g.xform(g.polygon_prism(tri, 25.0), g.Frame(at, out, along)))
    if lug:                                                      # the luffing cylinder's lug on the front
        # a fork round the eye: two plates 40 thick with chamfered ends (not round: see the cheeks)
        lug = [(550.0, _z(60.0)), (800.0, _z(60.0)), (870.0, _z(74.0)), (870.0, _z(116.0)), (800.0, _z(130.0)),
               (550.0, _z(130.0))]
        parts += [g.xform(g.polygon_prism(lug, 40.0), g.Frame((0, y0 + 40.0, 0), (1, 0, 0), (0, -1, 0)))
                  for y0 in (300.0, 460.0)]
    shape = g.fuse(*parts)
    cuts = [g.cyl(BORE_R, 1000.0, (PIVOT_LOCAL[0], -100, PIVOT_LOCAL[1]), (0, 1, 0))]
    cuts += [g.cyl(13.0, FOOT_T + 2.0, (x, y, -1.0)) for x in FOOT for y in FOOT_Y]
    if lug:
        cuts.append(g.cyl(LUFF_PIN_R, 200.0, LUFF_BASE_LOCAL, (0, 1, 0)))
    return g.cut(shape, *cuts)


def boom_shape(lug: bool = False):
    """From the pivot along +x: 7500 long, 500 x 500."""
    section = chamfered_rect(-250, -250, 500, 500, 40)           # (y, z)
    girder = g.xform(g.polygon_prism(section, 7500.0), g.Frame((0, 0, 0), (0, 1, 0), (1, 0, 0)))
    parts = [girder, g.cyl(250.0, 500.0, (0, -250, 0), (0, 1, 0))]
    for x in (1250.0, 2500.0, 3750.0, 5000.0, 6250.0):           # side ribs 20 thick, 50 short of top and bottom
        for y0 in (-280.0, 250.0):
            parts.append(g.box(x - 10, y0, -200, 20, 30, 400))
    parts.append(g.polygon_prism(chamfered_rect(6800, -200, 120, 400, 20), 140.0, g.T(0, 0, 250)))  # end stop
    if lug:
        x = LUFF_ROD_LOCAL[0]                                    # a fork round the rod eye, chamfered ends
        lug = [(x - 110, -200.0), (x + 110, -200.0), (x + 110, -420.0), (x + 50, -485.0), (x - 50, -485.0),
               (x - 110, -420.0)]
        parts += [g.xform(g.polygon_prism(lug, 40.0), g.Frame((0, y0 + 40.0, 0), (1, 0, 0), (0, -1, 0)))
                  for y0 in (-100.0, 60.0)]
    shape = g.fuse(*parts)
    # the tip tapers underneath: from z -250 at x 6250 to z -90 at the end (local y = world z, extruded along -y)
    taper = g.xform(g.polygon_prism([(6250.0, -250.0), (7550.0, -90.0), (7550.0, -300.0), (6250.0, -300.0)], 700.0),
                    g.Frame((0, 350, 0), (1, 0, 0), (0, -1, 0)))
    cuts = [g.cyl(BORE_R, 600.0, (0, -300, 0), (0, 1, 0)), taper]
    if lug:
        cuts.append(g.cyl(LUFF_PIN_R, 200.0, (LUFF_ROD_LOCAL[0], -100, LUFF_ROD_LOCAL[2]), (0, 1, 0)))
    return g.cut(shape, *cuts)


def trolley_shape():
    """Body 750 x 750 x 300; a hoist on its top at x > 275, y > 425: motor, rope drum with flanges, two stands. The
    rest of the top stays a clear flat face (the real-app test clicks it 150 mm in from the corner, from the +y side)."""
    body = g.polygon_prism(chamfered_rect(0, 0, 750, 750, 40), 300.0)
    body = chamfer(body, 25.0, lambda p: abs(p[2] - 300.0) < 1e-6)
    y, z = 560.0, 420.0
    fan = g.cyl(80.0, 25.0, (280, y, z), (1, 0, 0))
    motor = g.cyl(100.0, 160.0, (305, y, z), (1, 0, 0))
    feet = g.box(310, y - 80, 300, 140, 160, 40)
    drum = g.cyl(75.0, 180.0, (500, y, z), (1, 0, 0))
    flanges = [g.cyl(110.0, 20.0, (x, y, z), (1, 0, 0)) for x in (480.0, 680.0)]
    stands = [g.box(x, y - 45, 300, 25, 90, 120) for x in (460.0, 700.0)]
    return g.fuse(body, fan, motor, feet, drum, *flanges, *stands)


def wheel_shape():
    """A flanged wheel Ø300 along +y (0 .. 100), flange on the boom's side, hub outside."""
    prof = [(0.0, -30.0), (60.0, -30.0), (60.0, 0.0), (125.0, 0.0), (125.0, 75.0), (150.0, 82.5), (150.0, 100.0),
            (0.0, 100.0)]
    return g.revolve(prof, (0, 0, 0), (0, 1, 0))


def cover_shape():
    """Plate 1500 x 1000 x 12 with chamfered corners, four M12 screw heads and a handle."""
    plate = g.polygon_prism(chamfered_rect(0, 0, 1500, 1000, 75), COVER_T)
    heads = [hex_prism(18.0, 8.0, COVER_T).Moved(_loc(x, y)) for x in (100.0, 1400.0) for y in (100.0, 900.0)]
    handle = [g.box(640, 480, COVER_T, 25, 40, 90), g.box(835, 480, COVER_T, 25, 40, 90),
              g.box(640, 480, COVER_T + 90, 220, 40, 25)]
    return g.fuse(plate, *heads, *handle)


def _loc(x, y, z=0.0):
    from OCP.TopLoc import TopLoc_Location as _L
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(x, y, z))
    return _L(t)


def lamp_shape():
    """Revision B's BOOM.LAMP: a work lamp Ø200 on a foot (its centre at the origin, the foot on z -150)."""
    foot = g.polygon_prism(chamfered_rect(-125, -100, 250, 200, 25), 30.0, g.T(0, 0, -150.0))
    post = g.box(-25, -25, -120, 50, 50, 70)
    housing = g.cyl(100.0, 200.0, (-100, 0, 0), (1, 0, 0))
    rim = g.cyl(115.0, 25.0, (100, 0, 0), (1, 0, 0))
    return g.fuse(foot, post, housing, rim)


# the luffing cylinder (task 0122, the owner's pick B): its barrel pin in a fork on the pedestal's front, its rod pin
# in a fork under the boom (plates 120 apart). Barrel = eye, neck, end cap, tube (bore Ø200), gland (bore Ø120); rod =
# piston Ø198, rod Ø110, eye. Pins Ø70; the eyes' bores are the pins' size (as the test luffer).
LUFF_BASE_LOCAL = (750.0, 300.0, _z(95.0))       # pedestal space: the pin's axis (along +y from y 300, 200 long)
LUFF_ROD_LOCAL = (2100.0, 0.0, -375.0)           # boom space: the rod pin's centre
LUFF_PIN_R = 35.0
LUFF_CAP, LUFF_GLAND = 270.0, 1100.0             # the barrel's inner ends (mm from the barrel pin)
LUFF_PISTON = (300.0, 400.0)                     # the piston in the CAD pose: 30 mm can go in, 700 mm out
LUFF_BORE_R, LUFF_ROD_R = 100.0, 55.0


def luff_pins():
    """(barrel pin, rod pin) in world mm (x, z); both pins along Y through y = PIVOT y."""
    return ((PED[0] + LUFF_BASE_LOCAL[0], PED[2] + LUFF_BASE_LOCAL[2]),
            (PIVOT[0] + LUFF_ROD_LOCAL[0], PIVOT[2] + LUFF_ROD_LOCAL[2]))


def _eye(z: float):
    """An eye round a pin along y at (0, 0, z): Ø150 x 90, bore the pin's size."""
    return g.cut(g.cyl(75.0, 90.0, (0, -45, z), (0, 1, 0)), g.cyl(LUFF_PIN_R, 150.0, (0, -75, z), (0, 1, 0)))


def luff_parts():
    """Barrel and rod, placed: their own z runs from the barrel pin to the rod pin (L apart)."""
    (bx, bz), (rx, rz) = luff_pins()
    L = math.hypot(rx - bx, rz - bz)
    bore = g.cyl(LUFF_BORE_R, LUFF_GLAND - LUFF_CAP, (0, 0, LUFF_CAP))
    gland_bore = g.cyl(LUFF_ROD_R + 5.0, 100.0, (0, 0, LUFF_GLAND - 20.0))
    # the neck is thinner than the gap between the fork's plates and the end cap starts beyond them: no part of the
    # cylinder lies inside the forks (the first crane's did)
    barrel = g.fuse(g.cyl(55.0, 260.0, (0, 0, 0)), g.cyl(140.0, 60.0, (0, 0, 240.0)),     # neck, end cap
                    g.cyl(125.0, 860.0, (0, 0, 240.0)), g.cyl(140.0, 60.0, (0, 0, 1100.0)),  # tube, gland
                    g.cyl(35.0, 90.0, (100, 0, 330.0), (1, 0, 0)), g.cyl(35.0, 90.0, (100, 0, 1030.0), (1, 0, 0)))
    barrel = g.fuse(g.cut(barrel, bore, gland_bore, g.cyl(LUFF_PIN_R, 200.0, (0, -100, 0), (0, 1, 0))), _eye(0.0))
    rod = g.fuse(g.cyl(LUFF_BORE_R - 1.0, LUFF_PISTON[1] - LUFF_PISTON[0], (0, 0, LUFF_PISTON[0])),
                 g.cyl(LUFF_ROD_R, L - LUFF_PIN_R - LUFF_PISTON[1], (0, 0, LUFF_PISTON[1])), _eye(L))
    ang = math.degrees(math.atan2(rx - bx, rz - bz))             # tilt from +z towards +x
    m = g.T(bx, PIVOT[1], bz) @ g.Rot((0, 1, 0), ang)
    return g.xform(barrel, m), g.xform(rod, m)


def luff_pin(length: float = 220.0):
    """A pin Ø70 along +y from y 0, with a head Ø100 x 20 before its start."""
    return g.fuse(g.cyl(LUFF_PIN_R, length, (0, 0, 0), (0, 1, 0)), g.cyl(50.0, 20.0, (0, -20.0, 0), (0, 1, 0)))


# ---------------------------------------------------------------------------
# the assembly
# ---------------------------------------------------------------------------

def build(path: str, revision: str = "A", inventor_names: bool = False, plain: bool = False) -> None:
    """``inventor_names``: every placed part gets an occurrence name like Inventor writes ("BOLT:3").

    Revision "C" (with inventor_names) is revision A with bolt 1 removed and bolts 3 and 4 swapped:
    only the occurrence names tell them apart."""
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def color(label, rgb):
        ct.SetColor(label, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB),
                    XCAFDoc_ColorType.XCAFDoc_ColorSurf)

    def part(shape, text, rgb=None):
        if not plain and g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
        lab = st.AddShape(shape, False)
        name(lab, text)
        if rgb:
            color(lab, rgb)
        return lab

    counters: dict = {}

    def place(assy, lab, x=0.0, y=0.0, z=0.0, occurrence: str = ""):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        comp = st.AddComponent(assy, lab, TopLoc_Location(t))
        if inventor_names:
            if not occurrence:
                from OCP.TDataStd import TDataStd_Name as _N
                attr = _N()
                base_name = attr.Get().ToExtString() if lab.FindAttribute(_N.GetID_s(), attr) else "Part"
                key = (assy.Tag(), base_name)
                counters[key] = counters.get(key, 0) + 1
                occurrence = f"{base_name}:{counters[key]}"
            name(comp, occurrence)

    px, py, pz = PIVOT
    luff = not plain
    if plain:
        base = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 5000.0, 3000.0, BASE_H).Shape(), "BASE", YELLOW)
        ped = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 600.0, 800.0, PED_TOP).Shape()
        for y0 in (45.0, 675.0):
            ped = BRepAlgoAPI_Fuse(ped, BRepPrimAPI_MakeBox(gp_Pnt(100, y0, _z(200.0)), 400.0, CHEEK_T,
                                                            700.0).Shape()).Shape()
        ped = BRepAlgoAPI_Cut(ped, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(PIVOT_LOCAL[0], -50, PIVOT_LOCAL[1]),
                                                                   gp_Dir(0, 1, 0)), BORE_R, 900.0).Shape()).Shape()
        pedestal = part(ped, "PEDESTAL", YELLOW)
        boom = part(BRepPrimAPI_MakeBox(gp_Pnt(0, -250, -250), 7500.0, 500.0, 500.0).Shape(), "BOOM", YELLOW)
        trolley = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 750.0, 750.0, 300.0).Shape(), "TROLLEY", GREY)
        wheel = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), 125.0, 100.0).Shape(),
                     "WHEEL")
        cover = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1500.0, 1000.0, COVER_T).Shape(), "COVER", BLUE)
        bolt = part(BRepPrimAPI_MakeCylinder(15.0, 120.0).Shape(), BOLT)
        screw = None
    else:
        base = part(base_shape(), "BASE", GREY)
        pedestal = part(pedestal_shape(lug=luff), "PEDESTAL", YELLOW)
        boom = part(boom_shape(lug=luff), "BOOM", YELLOW)
        trolley = part(trolley_shape(), "TROLLEY", GREY)
        wheel = part(wheel_shape(), "WHEEL", STEEL)
        cover = part(cover_shape(), "COVER", BLUE)
        bolt = part(hex_bolt(30, 120.0), BOLT)
        screw = part(socket_screw(24, FOOT_T), SCREW, (0.12, 0.12, 0.13))
    pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -450, 0), gp_Dir(0, 1, 0)), PIN_R, 900.0).Shape(),
               "BOOM.PIN")
    lamp = None
    if revision in ("B", "C"):
        lamp = part(BRepPrimAPI_MakeSphere(150.0).Shape() if plain else lamp_shape(), "BOOM.LAMP")

    boom_asm = st.NewShape()
    name(boom_asm, "BOOM.ASM")
    place(boom_asm, boom)
    place(boom_asm, pin)
    if lamp is not None:
        place(boom_asm, lamp, 7250, 0, 400)
    if luff:
        place(boom_asm, part(luff_pin(), "BOOM.LUFF.PIN", STEEL), LUFF_ROD_LOCAL[0], -110.0, LUFF_ROD_LOCAL[2])

    trolley_asm = st.NewShape()
    name(trolley_asm, "TROLLEY.ASM")
    place(trolley_asm, trolley)
    place(trolley_asm, wheel, 150, -100, 50)
    place(trolley_asm, wheel, 600, -100, 50)

    root = st.NewShape()
    name(root, "TEST.CRANE")
    place(root, base)
    place(root, pedestal, *PED)
    if screw is not None:
        for x in FOOT:
            for y in FOOT_Y:
                place(root, screw, PED[0] + x, PED[1] + y, PED[2] + FOOT_T)
    place(root, boom_asm, px, py, pz)
    place(root, trolley_asm, px + 3000, py - 375, pz + 250)
    place(root, cover, COVER_AT[0], COVER_AT[1], BASE_H if revision == "A" else BASE_H + 50.0)
    if luff:
        barrel_s, rod_s = luff_parts()
        cyl_asm = st.NewShape()
        name(cyl_asm, "HYDRAULIC CYLINDER.ASM")
        place(cyl_asm, part(barrel_s, "HYDRAULIC CYLINDER.BARREL", (0.1, 0.1, 0.1)))
        place(cyl_asm, part(rod_s, "HYDRAULIC CYLINDER.ROD", (0.85, 0.86, 0.88)))
        place(root, cyl_asm)
        (bx, bz), _r = luff_pins()
        place(root, part(luff_pin(), "PEDESTAL.LUFF.PIN", STEEL), bx, PIVOT[1] - 110.0, bz)
    holes = list(BOLT_HOLES)
    if revision == "B":
        holes = [(4750, 2750), (250, 2750), (4750, 250)]    # one bolt less, other order
    if revision == "C":                                    # Inventor keeps occurrence names: bolt 1 deleted,
        for n, (x, y) in ((2, (4750, 250)), (3, (4650, 2700)), (4, (250, 2800))):   # bolts 3 and 4 swap places
            place(root, bolt, x, y, BASE_H, occurrence=f"{BOLT}:{n}")
        holes = []
    for x, y in holes:
        place(root, bolt, x, y, BASE_H)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(args[0] if args else "test_crane.step", args[1] if len(args) > 1 else "A",
          inventor_names="--inventor-names" in sys.argv, plain="--plain" in sys.argv)
    print("written")
