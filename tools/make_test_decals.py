"""Write a small STEP assembly for the decal tests (task 0024).

TEST.DECALS (revision "a")
  PANEL        grey plate 400 x 300 x 10 mm (big flat faces)
  BARREL  x2   cylinder Ø120 x 300 mm, standing (a round face; two copies of one part)
  BOX          cube 100 mm
Revision "b": BOX is 120 mm long in X now (its +X face moved, its top face grew); BARREL is 350 mm
long (its round face changed, the spots near its foot are still on it); PANEL the same.

usage: python make_test_decals.py out.step [a|b]
"""

import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
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


def build(path: str, rev: str = "a") -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def part(shape, text, rgb):
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        ct.SetColor(lab, Quantity_Color(*rgb, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    panel = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 400.0, 300.0, 10.0).Shape(), "PANEL", (0.7, 0.7, 0.7))
    barrel = part(BRepPrimAPI_MakeCylinder(60.0, 350.0 if rev == "b" else 300.0).Shape(), "BARREL", (0.5, 0.5, 0.55))
    box = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 120.0 if rev == "b" else 100.0, 100.0, 100.0).Shape(), "BOX",
               (0.8, 0.8, 0.8))

    root = st.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.DECALS"))
    for lab, x, y in ((panel, 0, 0), (barrel, 600, 100), (barrel, 800, 100), (box, 1000, 0)):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(float(x), float(y), 0.0))
        st.AddComponent(root, lab, TopLoc_Location(t))
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_decals.step", sys.argv[2] if len(sys.argv) > 2 else "a")
    print("written")
