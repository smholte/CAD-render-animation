"""Write a small gantry router with a tool carousel as a STEP assembly for the G-code tests (task 0026).

All sizes in mm. The gantry moves along Y, the carriage along X on the gantry's beam, the head along Z
on the carriage, so every axis moves the tool and the workpiece stays on the bed:

TEST.GANTRY
  BED                       box 800 x 600 x 40 (top at z = 0)
  STOCK 300x200x30          the workpiece: x -150..150, y -100..100, z 0..30
  Y.ASM                     the gantry: moves along Y
    GANTRY SIDE L / R       boxes at x = -390 and x = 370 (20 mm thick)
    BEAM                    box across, z 200..260, y 40..100
    X.ASM                   moves along X on the beam
      CARRIAGE              plate x -50..50, y 26..40, z 150..260 (behind the spindle, clear of it and the tool)
      Z.ASM                 moves along Z
        SPINDLE             cylinder Ø50, z 110..230 (nose at z = 110)
        TOOL T1 FLAT D6     flat end mill Ø6 x 30, tip at x = 0, y = 0, z = 80 (50 mm above the stock)
  CAROUSEL.ASM              tool carousel beside the bed, turns about the vertical axis x = 500, y = 0
    CAROUSEL DISC           cylinder Ø170 x 10, z 130..140 (its top is the pockets' height)
    TOOL T2 BALL D4         ball end mill Ø4 x 30 standing in the disc, tip at (560, 0, 110), top at z 140
    TOOL T3 DRILL D5        drill Ø5 x 40 with a 118° point, tip at (500, 60, 100), top at z 140

usage: python make_test_gantry.py out.step
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
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

STOCK = (-150.0, -100.0, 0.0, 300.0, 200.0, 30.0)       # x, y, z, dx, dy, dz
T1_TIP = (0.0, 0.0, 80.0)
T2_TIP = (560.0, 0.0, 110.0)
T3_TIP = (500.0, 60.0, 100.0)
CAROUSEL_AXIS = (500.0, 0.0)
# the carousel (task 0067): the disc's top is the pockets' height (z 140), the tools stand in it hanging down, so the
# spindle comes down onto a tool without going into the disc; the disc stays inside x > 410 (the gantry's right side)
DISC_Z, DISC_R = 130.0, 85.0


def flat_mill(radius: float, length: float):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), radius, length).Shape()


def ball_mill(radius: float, length: float):
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, radius), gp_Dir(0, 0, 1)), radius, length - radius).Shape()
    ball = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, radius), radius).Shape()
    return BRepAlgoAPI_Fuse(cyl, ball).Shape()


def drill(radius: float, length: float, angle: float = 118.0):
    h = radius / math.tan(math.radians(angle) / 2)
    cone = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0.0, radius, h).Shape()
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, h), gp_Dir(0, 0, 1)), radius, length - h).Shape()
    return BRepAlgoAPI_Fuse(cone, cyl).Shape()


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb=None):
        lab = st.AddShape(shape, False)
        name(lab, text)
        if rgb:
            ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB),
                        XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(assy, lab, TopLoc_Location(t))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    def box(x, y, z, dx, dy, dz):
        return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()

    grey, blue, steel = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.8, 0.8, 0.82)
    sx, sy, sz, sdx, sdy, sdz = STOCK
    bed = part(box(-400, -300, -40, 800, 600, 40), "BED", blue)
    stock = part(box(sx, sy, sz, sdx, sdy, sdz), "STOCK 300x200x30", (0.75, 0.76, 0.78))
    side_l = part(box(-410, 40, 0, 20, 60, 260), "GANTRY SIDE L", blue)
    side_r = part(box(390, 40, 0, 20, 60, 260), "GANTRY SIDE R", blue)
    beam = part(box(-410, 40, 200, 820, 60, 60), "BEAM", blue)
    carriage = part(box(-50, 26, 150, 100, 14, 110), "CARRIAGE", grey)
    spindle = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 110), gp_Dir(0, 0, 1)), 25.0, 120.0).Shape(),
                   "SPINDLE", grey)
    t1 = part(flat_mill(3.0, 30.0), "TOOL T1 FLAT D6", steel)
    t2 = part(ball_mill(2.0, 30.0), "TOOL T2 BALL D4", steel)
    t3 = part(drill(2.5, 40.0), "TOOL T3 DRILL D5", steel)
    cx, cy = CAROUSEL_AXIS
    disc = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cx, cy, DISC_Z), gp_Dir(0, 0, 1)), DISC_R, 10.0).Shape(),
                "CAROUSEL DISC", grey)

    z_asm = asm("Z.ASM")
    place(z_asm, spindle)
    place(z_asm, t1, *T1_TIP)
    x_asm = asm("X.ASM")
    place(x_asm, carriage)
    place(x_asm, z_asm)
    y_asm = asm("Y.ASM")
    place(y_asm, side_l)
    place(y_asm, side_r)
    place(y_asm, beam)
    place(y_asm, x_asm)
    car = asm("CAROUSEL.ASM")
    place(car, disc)
    place(car, t2, *T2_TIP)
    place(car, t3, *T3_TIP)
    root = asm("TEST.GANTRY")
    place(root, bed)
    place(root, stock)
    place(root, y_asm)
    place(root, car)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_gantry.step")
    print("written")
