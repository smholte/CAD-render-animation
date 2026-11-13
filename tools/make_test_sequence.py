"""Write a small test model for the Assembly sequence step as a STEP assembly (task 0100; generic, no owner data).

All sizes in mm. A spindle unit stands on a base plate; every part of the unit is round about the Z axis (except the
bolts, which stand round the cover), so it comes apart straight up, part by part, and goes together the same way.

TEST.SEQUENCE
  BASE PLATE              x -200 … 200, y -200 … 200, z -20 … 0
  SPINDLE.UNIT            (the subassembly the step takes apart: 12 parts, 5 of them fasteners)
    HOUSING               a cup: Ø120, z 0 … 100, inside Ø80 from z 15 up (open at the top); 4 holes Ø8.4 at
                          radius 50 from z 85 up
    BEARING 6205          two rings Ø52 / Ø25, 15 high: z 15 … 30 and z 70 … 85
    SPACER                ring Ø40 / Ø25, z 30 … 70
    SHAFT                 Ø24.8, z 15 … 150
    COVER                 disc Ø120, z 100 … 115, centre hole Ø26, 4 holes Ø8.4 at radius 50
    PULLEY                disc Ø64, z 125 … 145, bore Ø25 (clear of the bolt heads seen from above)
    ISO 4032 M24          hex nut (round here, Ø36), bore Ø25, z 145 … 160
    ISO 4762 M8x30        4 x: head Ø13 z 115 … 123, shank Ø8 z 85 … 115, at radius 50, 45° + k 90°

No two parts overlap: rings fit round the shaft with 0.1 mm play, the bolts in their holes with 0.2 mm.

usage: python make_test_sequence.py out.step
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
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

BOLT_R = 50.0                       # the bolts' circle
BOLT_ANGLES = (45.0, 135.0, 225.0, 315.0)
PARTS = 12                          # in SPINDLE.UNIT
FASTENERS = 5


def _cyl(r, z0, z1, x=0.0, y=0.0):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r, z1 - z0).Shape()


def _ring(r_out, r_in, z0, z1):
    return BRepAlgoAPI_Cut(_cyl(r_out, z0, z1), _cyl(r_in, z0 - 1, z1 + 1)).Shape()


def _bolt_holes(shape, z0, z1):
    for a in BOLT_ANGLES:
        x, y = BOLT_R * math.cos(math.radians(a)), BOLT_R * math.sin(math.radians(a))
        shape = BRepAlgoAPI_Cut(shape, _cyl(4.2, z0, z1, x, y)).Shape()
    return shape


def housing():
    cup = BRepAlgoAPI_Cut(_cyl(60, 0, 100), _cyl(40, 15, 101)).Shape()
    return _bolt_holes(cup, 85, 101)


def cover():
    return _bolt_holes(_ring(60, 13, 100, 115), 99, 116)


def bolt():
    """At the origin of its own placement: the shank's axis is Z, the head's underside at z = 115."""
    return BRepAlgoAPI_Fuse(_cyl(6.5, 115, 123), _cyl(4.0, 85, 115)).Shape()


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
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
    base = part(BRepPrimAPI_MakeBox(gp_Pnt(-200, -200, -20), 400, 400, 20).Shape(), "BASE PLATE", grey)
    unit = asm("SPINDLE.UNIT")
    place(unit, part(housing(), "HOUSING", blue))
    bearing = part(_ring(26, 12.5, 0, 15), "BEARING 6205", steel)
    for z in (15.0, 70.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(0, 0, z))
        place(unit, bearing, t)
    place(unit, part(_ring(20, 12.5, 30, 70), "SPACER", steel))
    place(unit, part(_cyl(12.4, 15, 150), "SHAFT", steel))
    place(unit, part(cover(), "COVER", blue))
    place(unit, part(_ring(32, 12.5, 125, 145), "PULLEY", orange))
    place(unit, part(_ring(18, 12.5, 145, 160), "ISO 4032 M24", dark))
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
