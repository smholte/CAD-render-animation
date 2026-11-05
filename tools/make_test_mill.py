"""Write a small 3-axis milling machine as a STEP assembly for the milling tests (task 0027).

All sizes in mm. The table moves along Y, the carriage along X, the head along Z:

TEST.MILL
  BED                       box 700 x 500 x 60 (top at z = 0)
  COLUMN                    box behind the table, carries the X carriage
  TABLE.ASM                 moves along Y (a slide joint in the tests)
    TABLE                   box 400 x 300 x 30 (top at z = 30)
    STOCK 200x200x40        the workpiece: box 200 x 200 x 40, x/y -100..100, z 30..70
    FINISHED PART           the stock with a pocket 100 x 60 x 10 (corners R5) and a hole Ø20 x 15
                            in the middle (for "finish at the CAD part"); same place as the stock
  X.ASM                     moves along X
    CARRIAGE                box
    Z.ASM                   moves along Z (sits on X.ASM)
      SPINDLE               cylinder Ø60
      END MILL D10          flat end mill Ø10 x 40, tip at x = 0, y = 0, z = 90 (20 mm above the stock)
      BALL MILL D6          ball end mill Ø6 x 30 (cylinder + half sphere), tip at x = 120, z = 90

usage: python make_test_mill.py out.step
"""

import sys

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

STOCK = (-100.0, -100.0, 30.0, 200.0, 200.0, 40.0)      # x, y, z, dx, dy, dz
FLAT_TIP = (0.0, 0.0, 90.0)
BALL_TIP = (120.0, 0.0, 90.0)
POCKET = (-50.0, -30.0, 100.0, 60.0, 10.0, 5.0)          # x, y, dx, dy, depth, corner radius (from the top)
HOLE = (70.0, 50.0, 10.0, 15.0)                          # x, y, radius, depth


def _pocket_tool():
    x, y, dx, dy, depth, r = POCKET
    top = STOCK[2] + STOCK[5]
    box = BRepPrimAPI_MakeBox(gp_Pnt(x, y, top - depth), dx, dy, depth + 5.0).Shape()
    fil = BRepFilletAPI_MakeFillet(box)
    exp = TopExp_Explorer(box, TopAbs_EDGE)
    while exp.More():                                  # round the four vertical edges
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(p0.X() - p1.X()) < 1e-6 and abs(p0.Y() - p1.Y()) < 1e-6:
            fil.Add(r, e)
        exp.Next()
    return fil.Shape()


def finished_part():
    x, y, z, dx, dy, dz = STOCK
    shape = BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()
    shape = BRepAlgoAPI_Cut(shape, _pocket_tool()).Shape()
    hx, hy, hr, hd = HOLE
    top = z + dz
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(hx, hy, top - hd), gp_Dir(0, 0, 1)), hr, hd + 5.0).Shape()
    return BRepAlgoAPI_Cut(shape, hole).Shape()


def ball_mill(radius: float, length: float):
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, radius), gp_Dir(0, 0, 1)), radius, length - radius).Shape()
    ball = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, radius), radius).Shape()
    return BRepAlgoAPI_Fuse(cyl, ball).Shape()


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

    grey, blue = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486)
    sx, sy, sz, sdx, sdy, sdz = STOCK
    bed = part(BRepPrimAPI_MakeBox(gp_Pnt(-350, -250, -60), 700.0, 500.0, 60.0).Shape(), "BED", blue)
    column = part(BRepPrimAPI_MakeBox(gp_Pnt(-350, 250, -60), 700.0, 120.0, 400.0).Shape(), "COLUMN", blue)
    table = part(BRepPrimAPI_MakeBox(gp_Pnt(-200, -150, 0), 400.0, 300.0, 30.0).Shape(), "TABLE", grey)
    stock = part(BRepPrimAPI_MakeBox(gp_Pnt(sx, sy, sz), sdx, sdy, sdz).Shape(), "STOCK 200x200x40",
                 (0.75, 0.76, 0.78))
    finished = part(finished_part(), "FINISHED PART", (0.75, 0.76, 0.78))
    carriage = part(BRepPrimAPI_MakeBox(gp_Pnt(-60, 180, 120), 120.0, 80.0, 160.0).Shape(), "CARRIAGE", blue)
    spindle = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 130), gp_Dir(0, 0, 1)), 30.0, 120.0).Shape(),
                   "SPINDLE", grey)
    end_mill = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 5.0, 40.0).Shape(),
                    "END MILL D10")
    ball = part(ball_mill(3.0, 30.0), "BALL MILL D6")

    table_asm = asm("TABLE.ASM")
    place(table_asm, table)
    place(table_asm, stock)
    place(table_asm, finished)
    z_asm = asm("Z.ASM")
    place(z_asm, spindle)
    place(z_asm, end_mill, *FLAT_TIP)
    place(z_asm, ball, *BALL_TIP)
    x_asm = asm("X.ASM")
    place(x_asm, carriage)
    place(x_asm, z_asm)
    root = asm("TEST.MILL")
    place(root, bed)
    place(root, column)
    place(root, table_asm)
    place(root, x_asm)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_mill.step")
    print("written")
