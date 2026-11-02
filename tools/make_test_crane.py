"""Write a small crane-like STEP assembly for the motion tests (two revisions).

TEST.CRANE
  BASE                          box 1000 x 600 x 100
  PEDESTAL                      box, carries the boom pin
  BOOM.ASM
    BOOM                        box 1500 x 100 x 100, starts at the pivot
    BOOM.PIN                    cylinder Ø40 along Y at the pivot (pick target for the joint axis)
  TROLLEY.ASM                   rides on the boom (a sibling of BOOM.ASM in the CAD tree)
    TROLLEY                     box 150 x 150 x 60
    WHEEL                       x2, cylinders
  COVER                         box
  ISO 4017 M12 x 40 - 8.8 HDG  x4

Revision B: one bolt removed, the bolts listed in another order, a new BOOM.LAMP in BOOM.ASM,
and the cover moved 10 mm.

usage: python make_test_crane.py out.step [A|B]
"""

import sys

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

PIVOT = (100.0, 300.0, 400.0)       # mm: boom pin centre


def build(path: str, revision: str = "A") -> None:
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
        lab = st.AddShape(shape, False)
        name(lab, text)
        if rgb:
            color(lab, rgb)
        return lab

    def place(assy, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(assy, lab, TopLoc_Location(t))

    px, py, pz = PIVOT
    base = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1000.0, 600.0, 100.0).Shape(), "BASE", (0.976, 0.659, 0.0))
    pedestal = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 120.0, 160.0, 280.0).Shape(), "PEDESTAL",
                    (0.976, 0.659, 0.0))
    boom = part(BRepPrimAPI_MakeBox(gp_Pnt(0, -50, -50), 1500.0, 100.0, 100.0).Shape(), "BOOM",
                (0.976, 0.659, 0.0))
    pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -90, 0), gp_Dir(0, 1, 0)), 20.0, 180.0).Shape(),
               "BOOM.PIN")
    trolley = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 150.0, 150.0, 60.0).Shape(), "TROLLEY",
                   (0.2, 0.2, 0.2))
    wheel = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), 25.0, 20.0).Shape(), "WHEEL")
    cover = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 300.0, 200.0, 10.0).Shape(), "COVER", (0.075, 0.267, 0.486))
    bolt = part(BRepPrimAPI_MakeCylinder(6.0, 40.0).Shape(), "ISO 4017 M12 x 40 - 8.8 HDG")
    lamp = part(BRepPrimAPI_MakeSphere(30.0).Shape(), "BOOM.LAMP") if revision == "B" else None

    boom_asm = st.NewShape()
    name(boom_asm, "BOOM.ASM")
    place(boom_asm, boom)
    place(boom_asm, pin)
    if lamp is not None:
        place(boom_asm, lamp, 1450, 0, 80)

    trolley_asm = st.NewShape()
    name(trolley_asm, "TROLLEY.ASM")
    place(trolley_asm, trolley)
    place(trolley_asm, wheel, 30, -20, 10)
    place(trolley_asm, wheel, 120, -20, 10)

    root = st.NewShape()
    name(root, "TEST.CRANE")
    place(root, base)
    place(root, pedestal, px - 60, py - 80, 100)
    place(root, boom_asm, px, py, pz)
    place(root, trolley_asm, px + 600, py - 75, pz + 50)
    place(root, cover, 600, 50, 100 if revision == "A" else 110)
    holes = [(50, 50), (950, 50), (50, 550), (950, 550)]
    if revision == "B":
        holes = [(950, 550), (50, 550), (950, 50)]          # one bolt less, other order
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
    build(sys.argv[1] if len(sys.argv) > 1 else "test_crane.step", sys.argv[2] if len(sys.argv) > 2 else "A")
    print("written")
