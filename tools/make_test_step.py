"""Write a small STEP assembly for automated tests.

TEST.MACHINE
  FRAME                         (yellow, RAL 1003-ish)
  COVER.ASM
    COVER.PLATE                 (blue)
    ISO 7380 M6x12              x2
  ISO 4017 M12 x 40 - 8.8 HDG  x4  (repeated: stored once)
  DIN 912 M10x30 - 12.9        x2
  SIGNAL.LAMP                   (no colour)

usage: python make_test_step.py out.step
"""

import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
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


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def color(label, rgb):
        ct.SetColor(label, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)

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

    frame = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1000.0, 600.0, 50.0).Shape(), "FRAME", (0.976, 0.659, 0.0))
    plate = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 400.0, 300.0, 5.0).Shape(), "COVER.PLATE", (0.075, 0.267, 0.486))
    button = part(BRepPrimAPI_MakeCylinder(5.0, 12.0).Shape(), "ISO 7380 M6x12")
    bolt = part(BRepPrimAPI_MakeCylinder(6.0, 40.0).Shape(), "ISO 4017 M12 x 40 - 8.8 HDG")
    cap = part(BRepPrimAPI_MakeCylinder(5.0, 30.0).Shape(), "DIN 912 M10x30 - 12.9")
    lamp = part(BRepPrimAPI_MakeSphere(40.0).Shape(), "SIGNAL.LAMP")

    cover = st.NewShape()
    name(cover, "COVER.ASM")
    place(cover, plate)
    place(cover, button, 20, 20, 5)
    place(cover, button, 380, 20, 5)

    root = st.NewShape()
    name(root, "TEST.MACHINE")
    place(root, frame)
    place(root, cover, 300, 150, 50)
    for x, y in ((50, 50), (950, 50), (50, 550), (950, 550)):
        place(root, bolt, x, y, 50)
    place(root, cap, 200, 100, 50)
    place(root, cap, 800, 100, 50)
    place(root, lamp, 900, 500, 140)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_machine.step")
    print("written")
