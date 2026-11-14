"""Write a small test model for the Assembly sequence step as a STEP assembly (task 0100; generic, no owner data).

All sizes in mm. A spindle unit stands on a base plate; every part of the unit is round about the Z axis (except the
bolts, which stand round the cover), so it comes apart straight up, part by part, and goes together the same way.

TEST.SEQUENCE
  BASE PLATE              x -200 … 200, y -200 … 200, z -20 … 0, corners and top edges chamfered, four holes Ø18
  SPINDLE.UNIT            (the subassembly the step takes apart: 12 parts, 5 of them fasteners)
    HOUSING               a cup: Ø120, z 0 … 100, inside Ø80 from z 15 up (open at the top); a foot flange Ø150
                          (z 0 … 12) and three cooling fins Ø140 (z 30 … 66); 4 holes Ø8.4 at radius 50 from z 85 up
    BEARING 6205          two rings Ø52 / Ø25, 15 high (outer corners chamfered): z 15 … 30 and z 70 … 85
    SPACER                ring Ø40 / Ø25, z 30 … 70
    SHAFT                 Ø24.8, z 15 … 150, ends chamfered, a keyway 8 wide at the top (z 126 … 150, open upwards)
    COVER                 disc Ø120, z 100 … 115 with a spigot into the housing (Ø79, z 94 … 100) and a seal boss
                          (Ø56, up to z 119); centre hole Ø26, 4 holes Ø8.4 at radius 50
    PULLEY                two-groove V-belt pulley Ø64, z 125 … 145, bore Ø25 with its key in the shaft's keyway (clear
                          of the bolt heads seen from above)
    ISO 4032 M24          hex nut 36 across flats, bore Ø25, z 145 … 160
    ISO 4762 M8x30        4 x: socket head Ø13 z 115 … 123 with its hex socket, shank Ø8 z 85 … 115, at radius 50,
                          45° + k 90°

No two parts overlap: rings fit round the shaft with 0.1 mm play, the bolts in their holes with 0.2 mm, the key in its
keyway with 0.2 … 1 mm. The details of task 0122 (fins, keyway, grooves, spigot) block no part's way up that was
free before: the order (fasteners, pulley, cover, bearing, spacer, bearing, shaft, housing) is the one of task 0100.

usage: python make_test_sequence.py out.step
"""

import math
import os
import sys

from OCP.gp import gp_Trsf, gp_Vec
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
from model_details import chamfer, chamfered_rect, hex_prism, socket_screw  # noqa: E402

BOLT_R = 50.0                       # the bolts' circle
BOLT_ANGLES = (45.0, 135.0, 225.0, 315.0)
PARTS = 12                          # in SPINDLE.UNIT
FASTENERS = 5


def _bolt_holes(shape, z0, z1):
    holes = [g.cyl(4.2, z1 - z0, (BOLT_R * math.cos(math.radians(a)), BOLT_R * math.sin(math.radians(a)), z0))
             for a in BOLT_ANGLES]
    return g.cut(shape, *holes)


def base_plate():
    plate = g.polygon_prism(chamfered_rect(-200, -200, 400, 400, 20), 20.0, g.T(0, 0, -20))
    plate = chamfer(plate, 3.0, lambda p: abs(p[2]) < 1e-6)
    holes = []
    for x in (-170.0, 170.0):
        for y in (-170.0, 170.0):
            holes.append(g.cyl(9.0, 22.0, (x, y, -21)))                                 # for M16 anchor bolts
    return g.cut(plate, *holes)


def housing():
    prof = [(0.0, 0.0), (75.0, 0.0), (75.0, 12.0), (60.0, 12.0)]
    for z in (30.0, 46.0, 62.0):                                     # cooling fins
        prof += [(60.0, z), (70.0, z), (70.0, z + 4), (60.0, z + 4)]
    prof += [(60.0, 100.0), (40.0, 100.0), (40.0, 15.0), (0.0, 15.0)]
    return _bolt_holes(g.revolve(prof), 85, 101)


def bearing():
    """6205: Ø52 / Ø25 x 15 on z 0 … 15, the outer ring's corners rounded off (chamfered)."""
    return g.revolve([(12.5, 0.0), (25.0, 0.0), (26.0, 1.0), (26.0, 14.0), (25.0, 15.0), (12.5, 15.0)])


def spacer():
    return g.revolve([(12.5, 30.0), (20.0, 30.0), (20.0, 70.0), (12.5, 70.0)])


def shaft():
    s = g.revolve([(0.0, 15.0), (11.4, 15.0), (12.4, 16.0), (12.4, 149.0), (11.4, 150.0), (0.0, 150.0)])
    return g.cut(s, g.box(8.4, -4.0, 126.0, 5.0, 8.0, 25.0))        # the keyway, open at the top


def cover():
    prof = [(13.0, 94.0), (39.5, 94.0), (39.5, 100.0), (60.0, 100.0), (60.0, 115.0), (28.0, 115.0), (28.0, 119.0),
            (13.0, 119.0)]
    return _bolt_holes(g.revolve(prof), 99, 116)


def pulley():
    prof = [(12.5, 125.0), (32.0, 125.0), (32.0, 128.0), (26.0, 131.0), (32.0, 134.0), (32.0, 136.0), (26.0, 139.0),
            (32.0, 142.0), (32.0, 145.0), (12.5, 145.0)]
    key = g.box(8.9, -3.8, 127.0, 4.0, 7.6, 16.0)                   # in the shaft's keyway (x 8.4 …, y ±4, z 126 …)
    return g.fuse(g.revolve(prof), key)


def nut():
    """ISO 4032 M24: 36 across flats, 15 high (z 145 … 160), the top edges chamfered."""
    hexa = chamfer(hex_prism(36.0, 15.0, 145.0), 1.5, lambda p: abs(p[2] - 160.0) < 1e-6)
    return g.cut(hexa, g.cyl(12.5, 17.0, (0, 0, 144.0)))


def bolt():
    """At the origin of its own placement: the shank's axis is Z, the head's underside at z = 115."""
    return g.xform(socket_screw(8, 30.0), g.T(0, 0, 115.0))


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
        if g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
        lab = st.AddShape(shape, False)
        name(lab, text)
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, trsf=None):
        st.AddComponent(assy, lab, TopLoc_Location(trsf if trsf is not None else gp_Trsf()))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, orange, steel, dark = ((0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.95, 0.45, 0.05),
                                       (0.8, 0.8, 0.82), (0.15, 0.15, 0.17))
    base = part(base_plate(), "BASE PLATE", grey)
    unit = asm("SPINDLE.UNIT")
    place(unit, part(housing(), "HOUSING", blue))
    brg = part(bearing(), "BEARING 6205", steel)
    for z in (15.0, 70.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(0, 0, z))
        place(unit, brg, t)
    place(unit, part(spacer(), "SPACER", steel))
    place(unit, part(shaft(), "SHAFT", steel))
    place(unit, part(cover(), "COVER", blue))
    place(unit, part(pulley(), "PULLEY", orange))
    place(unit, part(nut(), "ISO 4032 M24", dark))
    b = part(bolt(), "ISO 4762 M8x30", dark)
    for a in BOLT_ANGLES:
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(BOLT_R * math.cos(math.radians(a)), BOLT_R * math.sin(math.radians(a)), 0))
        place(unit, b, t)
    root = asm("TEST.SEQUENCE")
    place(root, base)
    place(root, unit)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_sequence.step")
    print("written")
