"""Write a small crane-like STEP assembly for the motion tests (two revisions).

TEST.CRANE                      mm; the boom turns about Y at PIVOT
  BASE                          base plate 1000 x 600 x 100, corners and top edges chamfered, four bolt holes Ø13
  PEDESTAL                      a foot flange with gussets, a block with chamfered corners and a fork on top (two
                                cheeks with chamfered tops, bore Ø40.4) that carries the boom pin; the boom
                                turns between the cheeks, 20 mm above the block (task 0072: no part starts inside
                                another, so the clash check never sits on its threshold)
  ISO 4762 M10 x 20 - 12.9      x4, socket head screws holding the pedestal's foot down
  BOOM.ASM
    BOOM                        box girder 1500 x 100 x 100 from the pivot: round end round the pin, chamfered edges,
                                side ribs, the tip tapered underneath, an end stop on top
    BOOM.PIN                    cylinder Ø40 along Y at the pivot (pick target for the joint axis)
    BOOM.LUFF.PIN                Ø20 through the fork under the boom: the luffing cylinder's rod pin
  TROLLEY.ASM                   rides on the boom (a sibling of BOOM.ASM in the CAD tree)
    TROLLEY                     body 150 x 150 x 60 with chamfers and a hoist motor on top
    WHEEL                       x2, flanged wheels
  HYDRAULIC CYLINDER.ASM             luffing cylinder (task 0122): barrel pin in a fork on the pedestal's front, rod pin in a
                                fork under the boom; the piston can go 6 mm in and 140 mm out (boom up to ~37°)
    HYDRAULIC CYLINDER.BARREL        eye, end cap, tube (bore Ø52), gland, two ports
    HYDRAULIC CYLINDER.ROD           piston Ø50, rod Ø22, eye
  PEDESTAL.LUFF.PIN              Ø20 through the pedestal's fork: the barrel pin
  COVER                         plate 300 x 200 x 10 with round corners, four screw heads and a handle
  ISO 4017 M12 x 40 - 8.8 HDG  x4, hex head bolts, the shank down in the base's holes

Revision B: one bolt removed, the bolts listed in another order, a new BOOM.LAMP in BOOM.ASM,
and the cover moved 10 mm.

usage: python make_test_crane.py out.step [A|B] [--inventor-names] [--plain]

``--plain`` writes the plain crane of tasks 0011–0072 (boxes and cylinders; the old-project models
test_crane_inv_*.step were made with it).
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
from model_details import chamfer, chamfered_rect, hex_prism  # noqa: E402

PIVOT = (100.0, 300.0, 400.0)       # mm: boom pin centre
YELLOW = (0.976, 0.659, 0.0)        # RAL 1003-ish: the crane's paint (the groups' "Colour #F9A800")
GREY = (0.2, 0.2, 0.2)
BLUE = (0.075, 0.267, 0.486)
STEEL = (0.62, 0.64, 0.66)
BOLT_HOLES = [(50, 50), (950, 50), (50, 550), (950, 550)]
PED = (PIVOT[0] - 60, PIVOT[1] - 80, 100.0)          # the pedestal's place (its own x 0..120, y 0..160)
FOOT = (-20.0, 140.0)                               # the foot flange's screw places along x and y (pedestal space)
FOOT_Y = (-25.0, 185.0)


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def base_shape():
    plate = g.polygon_prism(chamfered_rect(0, 0, 1000, 600, 20), 100.0)
    plate = chamfer(plate, 8.0, lambda p: abs(p[2] - 100.0) < 1e-6)
    holes = [g.cyl(6.5, 102.0, (x, y, -1.0)) for x, y in BOLT_HOLES]
    return g.cut(plate, *holes)


def pedestal_shape(lug: bool = False):
    """In its own space: block x 0..120, y 0..160, z 20..230 on a foot flange z 0..20; the pivot at (60, *, 300)."""
    foot = g.polygon_prism(chamfered_rect(-35, -45, 190, 250, 15), 20.0)
    foot = chamfer(foot, 3.0, lambda p: abs(p[2] - 20.0) < 1e-6)
    block = g.polygon_prism(chamfered_rect(0, 0, 120, 160, 12), 210.0, g.T(0, 0, 20))
    parts = [foot, block]
    # the cheeks, tops chamfered (not round: a round top on the bore's axis would make the importer call the bore
    # "Ø80", since faces on one axis line share one axis with the largest radius)
    cheek = [(20.0, 200.0), (100.0, 200.0), (100.0, 318.0), (82.0, 340.0), (38.0, 340.0), (20.0, 318.0)]
    for y0 in (0.0, 135.0):
        parts.append(g.xform(g.polygon_prism(cheek, 25.0), g.Frame((0, y0 + 25.0, 0), (1, 0, 0), (0, -1, 0))))
    # gussets between the foot and the block: a triangle 25 out and 70 up, 12 thick
    tri = [(0.0, 0.0), (25.0, 0.0), (0.0, 70.0)]
    for side in ("-y", "+y", "-x") + (() if lug else ("+x",)):
        sgn = -1.0 if side[0] == "-" else 1.0
        if side[1] == "y":                       # local x outwards, local y up, extruded 12 along x
            out, at = (0, sgn, 0), (54.0 if sgn > 0 else 66.0, 0.0 if sgn < 0 else 160.0, 20.0)
            along = (sgn, 0, 0)
        else:
            out, at = (sgn, 0, 0), (0.0 if sgn < 0 else 120.0, 74.0 if sgn < 0 else 86.0, 20.0)
            along = (0, -sgn, 0)
        parts.append(g.xform(g.polygon_prism(tri, 12.0), g.Frame(at, out, along)))
    if lug:                                                      # the luffing cylinder's lug on the front
        parts += [g.box(120, 60, 60, 48, 8, 70), g.box(120, 92, 60, 48, 8, 70)]        # a fork round the eye
        parts += [g.cyl(24.0, 8.0, (LUFF_BASE_LOCAL[0], y0, LUFF_BASE_LOCAL[2]), (0, 1, 0)) for y0 in (60.0, 92.0)]
    shape = g.fuse(*parts)
    cuts = [g.cyl(20.2, 200.0, (60, -20, 300), (0, 1, 0))]
    cuts += [g.cyl(5.5, 22.0, (x, y, -1.0)) for x in FOOT for y in FOOT_Y]
    if lug:
        cuts.append(g.cyl(LUFF_PIN_R, 40.0, LUFF_BASE_LOCAL, (0, 1, 0)))
    return g.cut(shape, *cuts)


def boom_shape(lug: bool = False):
    """From the pivot along +x: 1500 long, 100 x 100."""
    section = chamfered_rect(-50, -50, 100, 100, 8)              # (y, z)
    girder = g.xform(g.polygon_prism(section, 1500.0), g.Frame((0, 0, 0), (0, 1, 0), (1, 0, 0)))
    parts = [girder, g.cyl(50.0, 100.0, (0, -50, 0), (0, 1, 0))]
    for x in (250.0, 500.0, 750.0, 1000.0, 1250.0):              # side ribs, 10 short of top and bottom
        for y0 in (-56.0, 50.0):
            parts.append(g.box(x - 4, y0, -40, 8, 6, 80))
    parts.append(g.polygon_prism(chamfered_rect(1360, -40, 24, 80, 4), 28.0, g.T(0, 0, 50)))     # end stop
    if lug:
        parts += [g.box(LUFF_ROD_LOCAL[0] - 22, y0, -75, 44, 8, 26) for y0 in (-19.0, 11.0)]
        parts += [g.cyl(22.0, 8.0, (LUFF_ROD_LOCAL[0], y0, LUFF_ROD_LOCAL[2]), (0, 1, 0)) for y0 in (-19.0, 11.0)]
    shape = g.fuse(*parts)
    # the tip tapers underneath: from z -50 at x 1250 to z -18 at the end (local y = world z, extruded along -y)
    taper = g.xform(g.polygon_prism([(1250.0, -50.0), (1510.0, -18.0), (1510.0, -60.0), (1250.0, -60.0)], 140.0),
                    g.Frame((0, 70, 0), (1, 0, 0), (0, -1, 0)))
    cuts = [g.cyl(20.2, 120.0, (0, -60, 0), (0, 1, 0)), taper]
    if lug:
        cuts.append(g.cyl(LUFF_PIN_R, 40.0, (LUFF_ROD_LOCAL[0], -20, LUFF_ROD_LOCAL[2]), (0, 1, 0)))
    return g.cut(shape, *cuts)


def trolley_shape():
    """Body 150 x 150 x 60; on its back half (y > 80) a hoist: motor, rope drum with flanges, two stands. The front
    half of the top stays a clear flat face (tests click it 30 mm in from the corner)."""
    body = g.polygon_prism(chamfered_rect(0, 0, 150, 150, 8), 60.0)
    body = chamfer(body, 5.0, lambda p: abs(p[2] - 60.0) < 1e-6)
    y, z = 112.0, 86.0
    motor = g.cyl(22.0, 45.0, (12, y, z), (1, 0, 0))
    fan = g.cyl(18.0, 6.0, (6, y, z), (1, 0, 0))
    feet = g.box(14, y - 16, 60, 40, 32, 10)
    drum = g.cyl(16.0, 66.0, (66, y, z), (1, 0, 0))
    flanges = [g.cyl(24.0, 5.0, (x, y, z), (1, 0, 0)) for x in (61.0, 132.0)]
    stands = [g.box(x, y - 10, 60, 6, 20, 26) for x in (57.0, 137.0)]
    return g.fuse(body, motor, fan, feet, drum, *flanges, *stands)


def wheel_shape():
    """A flanged wheel along +y (0 .. 20), flange on the boom's side, hub outside."""
    prof = [(0.0, -6.0), (12.0, -6.0), (12.0, 0.0), (25.0, 0.0), (25.0, 15.0), (30.0, 16.5), (30.0, 20.0),
            (0.0, 20.0)]
    return g.revolve(prof, (0, 0, 0), (0, 1, 0))


def cover_shape():
    r = 20.0
    prof = [(r, 0.0), (300 - r, 0.0), ("arc", (300 - r + r * math.sin(math.pi / 4), r - r * math.cos(math.pi / 4)),
                                            (300.0, r)),
            (300.0, 200 - r), ("arc", (300 - r + r * math.sin(math.pi / 4), 200 - r + r * math.cos(math.pi / 4)),
                               (300 - r, 200.0)),
            (r, 200.0), ("arc", (r - r * math.sin(math.pi / 4), 200 - r + r * math.cos(math.pi / 4)), (0.0, 200 - r)),
            (0.0, r), ("arc", (r - r * math.sin(math.pi / 4), r - r * math.cos(math.pi / 4)), (r, 0.0))]
    plate = g.prism(prof, 10.0)
    heads = [g.cyl(7.0, 3.0, (x, y, 10.0)) for x in (20.0, 280.0) for y in (20.0, 180.0)]
    handle = [g.box(130, 92, 10, 6, 16, 18), g.box(164, 92, 10, 6, 16, 18), g.box(130, 92, 24, 40, 16, 6)]
    return g.fuse(plate, *heads, *handle)


def hex_bolt(length: float = 40.0):
    """ISO 4017 M12: head 18 across flats, 7.5 high, on z = 0; the shank goes down."""
    return g.fuse(hex_prism(18.0, 7.5), g.cyl(9.0, 1.0, (0, 0, 0)), g.cyl(6.0, length, (0, 0, -length)))


def socket_screw():
    """ISO 4762 M10 x 20: head Ø16 x 10 on z = 0 with a hex socket, the shank down through the foot."""
    head = g.cut(g.cyl(8.0, 10.0), hex_prism(8.0, 6.0, 4.1))
    return g.fuse(head, g.cyl(5.0, 20.0, (0, 0, -20.0)))


# the luffing cylinder (task 0122, the owner's pick B): its barrel pin in a fork on the pedestal's front, its rod pin
# in a fork under the boom. Barrel = eye, end cap, tube (bore Ø52), gland (bore Ø24); rod = piston Ø50, rod Ø22, eye.
LUFF_BASE_LOCAL = (150.0, 60.0, 95.0)            # pedestal space: the pin's axis (along +y from y 60, 40 long)
LUFF_ROD_LOCAL = (420.0, 0.0, -75.0)             # boom space: the rod pin's centre
LUFF_PIN_R = 10.0                                # pins Ø20; the eyes' bores are the pins' size (as the test luffer)
LUFF_CAP, LUFF_GLAND = 34.0, 200.0               # the barrel's inner ends (mm from the barrel pin)
LUFF_PISTON = (40.0, 60.0)                       # the piston in the CAD pose: 6 mm can go in, 140 mm out


def luff_pins():
    """(barrel pin, rod pin) in world mm (x, z); both pins along Y through y = PIVOT y."""
    return ((PED[0] + LUFF_BASE_LOCAL[0], PED[2] + LUFF_BASE_LOCAL[2]),
            (PIVOT[0] + LUFF_ROD_LOCAL[0], PIVOT[2] + LUFF_ROD_LOCAL[2]))


def _eye(z: float):
    """An eye round a pin along y at (0, 0, z): Ø36 x 18, bore the pin's size."""
    return g.cut(g.cyl(18.0, 18.0, (0, -9, z), (0, 1, 0)), g.cyl(LUFF_PIN_R, 30.0, (0, -15, z), (0, 1, 0)))


def luff_parts():
    """Barrel and rod, placed: their own z runs from the barrel pin to the rod pin (L apart)."""
    (bx, bz), (rx, rz) = luff_pins()
    L = math.hypot(rx - bx, rz - bz)
    bore = g.cyl(26.0, LUFF_GLAND - LUFF_CAP, (0, 0, LUFF_CAP))
    gland_bore = g.cyl(12.0, 20.0, (0, 0, LUFF_GLAND - 4.0))
    barrel = g.fuse(g.cyl(16.0, 26.0, (0, 0, 0)), g.cyl(35.0, 12.0, (0, 0, 22.0)),       # neck, end cap
                    g.cyl(32.0, 190.0, (0, 0, 22.0)), g.cyl(35.0, 12.0, (0, 0, 200.0)),  # tube, gland
                    g.cyl(8.0, 18.0, (20, 0, 46.0), (1, 0, 0)), g.cyl(8.0, 18.0, (20, 0, 186.0), (1, 0, 0)))
    barrel = g.fuse(g.cut(barrel, bore, gland_bore, g.cyl(LUFF_PIN_R, 40.0, (0, -20, 0), (0, 1, 0))), _eye(0.0))
    rod = g.fuse(g.cyl(25.0, LUFF_PISTON[1] - LUFF_PISTON[0], (0, 0, LUFF_PISTON[0])),
                 g.cyl(11.0, L - 16.0 - LUFF_PISTON[1], (0, 0, LUFF_PISTON[1])),
                 g.cyl(14.0, 20.0, (0, 0, L - 30.0)), _eye(L))
    ang = math.degrees(math.atan2(rx - bx, rz - bz))             # tilt from +z towards +x
    m = g.T(bx, PIVOT[1], bz) @ g.Rot((0, 1, 0), ang)
    return g.xform(barrel, m), g.xform(rod, m)


def luff_pin(length: float = 44.0):
    """A pin Ø20 along +y from y 0, with a head Ø28 x 4 before its start."""
    return g.fuse(g.cyl(LUFF_PIN_R, length, (0, 0, 0), (0, 1, 0)), g.cyl(14.0, 4.0, (0, -4.0, 0), (0, 1, 0)))


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
        base = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1000.0, 600.0, 100.0).Shape(), "BASE", YELLOW)
        ped = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 120.0, 160.0, 230.0).Shape()
        for y0 in (0.0, 135.0):
            ped = BRepAlgoAPI_Fuse(ped, BRepPrimAPI_MakeBox(gp_Pnt(20, y0, 200), 80.0, 25.0, 140.0).Shape()).Shape()
        ped = BRepAlgoAPI_Cut(ped, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(60, -10, 300), gp_Dir(0, 1, 0)), 20.2,
                                                            180.0).Shape()).Shape()
        pedestal = part(ped, "PEDESTAL", YELLOW)
        boom = part(BRepPrimAPI_MakeBox(gp_Pnt(0, -50, -50), 1500.0, 100.0, 100.0).Shape(), "BOOM", YELLOW)
        trolley = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 150.0, 150.0, 60.0).Shape(), "TROLLEY", GREY)
        wheel = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), 25.0, 20.0).Shape(),
                     "WHEEL")
        cover = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 300.0, 200.0, 10.0).Shape(), "COVER", BLUE)
        bolt = part(BRepPrimAPI_MakeCylinder(6.0, 40.0).Shape(), "ISO 4017 M12 x 40 - 8.8 HDG")
        screw = None
    else:
        base = part(base_shape(), "BASE", GREY)
        pedestal = part(pedestal_shape(lug=luff), "PEDESTAL", YELLOW)
        boom = part(boom_shape(lug=luff), "BOOM", YELLOW)
        trolley = part(trolley_shape(), "TROLLEY", GREY)
        wheel = part(wheel_shape(), "WHEEL", STEEL)
        cover = part(cover_shape(), "COVER", BLUE)
        bolt = part(hex_bolt(), "ISO 4017 M12 x 40 - 8.8 HDG")
        screw = part(socket_screw(), "ISO 4762 M10 x 20 - 12.9", (0.12, 0.12, 0.13))
    pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -90, 0), gp_Dir(0, 1, 0)), 20.0, 180.0).Shape(),
               "BOOM.PIN")
    lamp = part(BRepPrimAPI_MakeSphere(30.0).Shape(), "BOOM.LAMP") if revision in ("B", "C") else None

    boom_asm = st.NewShape()
    name(boom_asm, "BOOM.ASM")
    place(boom_asm, boom)
    place(boom_asm, pin)
    if lamp is not None:
        place(boom_asm, lamp, 1450, 0, 80)
    if luff:
        place(boom_asm, part(luff_pin(), "BOOM.LUFF.PIN", STEEL), LUFF_ROD_LOCAL[0], -22.0, LUFF_ROD_LOCAL[2])

    trolley_asm = st.NewShape()
    name(trolley_asm, "TROLLEY.ASM")
    place(trolley_asm, trolley)
    place(trolley_asm, wheel, 30, -20, 10)
    place(trolley_asm, wheel, 120, -20, 10)

    root = st.NewShape()
    name(root, "TEST.CRANE")
    place(root, base)
    place(root, pedestal, *PED)
    if screw is not None:
        for x in FOOT:
            for y in FOOT_Y:
                place(root, screw, PED[0] + x, PED[1] + y, PED[2] + 20.0)
    place(root, boom_asm, px, py, pz)
    place(root, trolley_asm, px + 600, py - 75, pz + 50)
    place(root, cover, 600, 50, 100 if revision == "A" else 110)
    if luff:
        barrel_s, rod_s = luff_parts()
        cyl_asm = st.NewShape()
        name(cyl_asm, "HYDRAULIC CYLINDER.ASM")
        place(cyl_asm, part(barrel_s, "HYDRAULIC CYLINDER.BARREL", (0.1, 0.1, 0.1)))
        place(cyl_asm, part(rod_s, "HYDRAULIC CYLINDER.ROD", (0.85, 0.86, 0.88)))
        place(root, cyl_asm)
        (bx, bz), _r = luff_pins()
        place(root, part(luff_pin(), "PEDESTAL.LUFF.PIN", STEEL), bx, PIVOT[1] - 22.0, bz)
    holes = list(BOLT_HOLES)
    if revision == "B":
        holes = [(950, 550), (50, 550), (950, 50)]          # one bolt less, other order
    if revision == "C":                                    # Inventor keeps occurrence names: bolt 1 deleted,
        for n, (x, y) in ((2, (950, 50)), (3, (930, 540)), (4, (50, 560))):   # bolts 3 and 4 swap places
            place(root, bolt, x, y, 100, occurrence=f"ISO 4017 M12 x 40 - 8.8 HDG:{n}")
        holes = []
    for x, y in holes:
        place(root, bolt, x, y, 100)
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
