"""Write a small 3-axis mill with a stock block and a finished part as a STEP assembly (task 0029: the app makes the
toolpath). Nothing of a real machine or part: all sizes in mm, Z up.

TEST.TOOLPATH
  BED, COLUMN               fixed (the machine of the milling test model)
  TABLE.ASM                 moves along Y (a slide joint in the tests)
    TABLE                   box 400 x 300 x 30 (top at z = 30)
    STOCK 120x80x40         the raw block: x -60..60, y -40..40, z 30..70
    FINISHED PART           same place as the stock, inside it:
                              base 120 x 80, top at z = 55
                              boss 24 x 24 up to z = 65 at x -52..-28, y -32..-8, its top edges rounded R3
                              pocket 36 x 22, 8 deep (floor z = 47), corners R5, at x 12..48, y -32..-10
                              dome: a sphere R25 round (-22, 18, 40): top at z = 65, Ø40 on the base
                              mushroom (the undercut): post 10 x 10 (z 55..60) under a cap 22 x 16 (z 60..64) at
                              (28, 22): the cap hangs over by 6 / 3 mm - the stock under it cannot be cut from the top
                              through hole Ø10 at (52, 30)
  X.ASM                     moves along X
    CARRIAGE
    Z.ASM                   moves along Z
      SPINDLE               cylinder Ø60
      END MILL D10          flat end mill Ø10 x 40, tip at x = 0, y = 0, z = 90 (20 mm above the stock)

usage: python make_test_toolpath.py out.step
"""

import sys

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
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

STOCK = (-60.0, -40.0, 30.0, 120.0, 80.0, 40.0)        # x, y, z, dx, dy, dz
BASE_TOP = 55.0
BOSS = (-52.0, -32.0, 24.0, 24.0, 65.0, 3.0)            # x, y, dx, dy, top, fillet radius of the top edges
POCKET = (12.0, -32.0, 36.0, 22.0, 8.0, 5.0)            # x, y, dx, dy, depth, corner radius
DOME = (-22.0, 18.0, 40.0, 25.0)                        # centre x, y, z, radius
POST = (23.0, 17.0, 10.0, 10.0, 60.0)                   # x, y, dx, dy, top
CAP = (17.0, 14.0, 22.0, 16.0, 64.0)                    # x, y, dx, dy, top (from the post's top)
HOLE = (52.0, 30.0, 5.0)                                # x, y, radius
FLAT_TIP = (0.0, 0.0, 90.0)


def _edges(shape, test):
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    out = []
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if test(p0, p1):
            out.append(e)
        exp.Next()
    return out


def _round(shape, radius, test):
    fil = BRepFilletAPI_MakeFillet(shape)
    for e in _edges(shape, test):
        fil.Add(radius, e)
    return fil.Shape()


def finished_part():
    x, y, z, dx, dy, _dz = STOCK
    base = BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, BASE_TOP - z).Shape()
    bx, by, bdx, bdy, btop, br = BOSS
    boss = BRepPrimAPI_MakeBox(gp_Pnt(bx, by, BASE_TOP - 1.0), bdx, bdy, btop - BASE_TOP + 1.0).Shape()
    boss = _round(boss, br, lambda p0, p1: abs(p0.Z() - btop) < 1e-6 and abs(p1.Z() - btop) < 1e-6)
    shape = BRepAlgoAPI_Fuse(base, boss).Shape()
    cx, cy, cz, cr = DOME
    sphere = BRepPrimAPI_MakeSphere(gp_Pnt(cx, cy, cz), cr).Shape()
    above = BRepPrimAPI_MakeBox(gp_Pnt(cx - cr, cy - cr, BASE_TOP - 1.0), 2 * cr, 2 * cr, cr).Shape()
    shape = BRepAlgoAPI_Fuse(shape, BRepAlgoAPI_Common(sphere, above).Shape()).Shape()
    px, py, pdx, pdy, ptop = POST
    post = BRepPrimAPI_MakeBox(gp_Pnt(px, py, BASE_TOP - 1.0), pdx, pdy, ptop - BASE_TOP + 1.0).Shape()
    kx, ky, kdx, kdy, ktop = CAP
    cap = BRepPrimAPI_MakeBox(gp_Pnt(kx, ky, ptop), kdx, kdy, ktop - ptop).Shape()
    shape = BRepAlgoAPI_Fuse(shape, BRepAlgoAPI_Fuse(post, cap).Shape()).Shape()
    qx, qy, qdx, qdy, depth, qr = POCKET
    pocket = BRepPrimAPI_MakeBox(gp_Pnt(qx, qy, BASE_TOP - depth), qdx, qdy, depth + 20.0).Shape()
    pocket = _round(pocket, qr, lambda p0, p1: abs(p0.X() - p1.X()) < 1e-6 and abs(p0.Y() - p1.Y()) < 1e-6)
    shape = BRepAlgoAPI_Cut(shape, pocket).Shape()
    hx, hy, hr = HOLE
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(hx, hy, z - 5.0), gp_Dir(0, 0, 1)), hr, 100.0).Shape()
    return BRepAlgoAPI_Cut(shape, hole).Shape()


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
    stock = part(BRepPrimAPI_MakeBox(gp_Pnt(sx, sy, sz), sdx, sdy, sdz).Shape(), "STOCK 120x80x40",
                 (0.75, 0.76, 0.78))
    finished = part(finished_part(), "FINISHED PART", (0.75, 0.76, 0.78))
    carriage = part(BRepPrimAPI_MakeBox(gp_Pnt(-60, 180, 120), 120.0, 80.0, 160.0).Shape(), "CARRIAGE", blue)
    spindle = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 130), gp_Dir(0, 0, 1)), 30.0, 120.0).Shape(),
                   "SPINDLE", grey)
    end_mill = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 5.0, 40.0).Shape(),
                    "END MILL D10")

    table_asm = asm("TABLE.ASM")
    place(table_asm, table)
    place(table_asm, stock)
    place(table_asm, finished)
    z_asm = asm("Z.ASM")
    place(z_asm, spindle)
    place(z_asm, end_mill, *FLAT_TIP)
    x_asm = asm("X.ASM")
    place(x_asm, carriage)
    place(x_asm, z_asm)
    root = asm("TEST.TOOLPATH")
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
    build(sys.argv[1] if len(sys.argv) > 1 else "test_toolpath.step")
    print("written")
