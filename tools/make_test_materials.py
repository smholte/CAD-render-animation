"""Write a small STEP assembly with CAD material and appearance names, for automated tests.

OpenCascade writes the material names (XCAF materials) the same way Fusion 360 and Inventor do
(PROPERTY_DEFINITION 'material property' / 'material name'). Appearance names are added
afterwards, the way Autodesk writes them: as the name of the part's colour.

TEST.MATERIALS
  PLATE        material "Aluminium 6082", appearance "Aluminum - Satin"   (grey)
  SEAL RING    material "EPDM",           appearance "Rubber - Soft"      (black)
  BODY1        material "Steel",          appearance "Paint - Enamel Glossy (Red)"  (red)
  BODY2        material "Generic",        no appearance                   (blue)
  BODY3        nothing
  TWIN  x2     two different parts with the same name: "Steel" and "Brass" (must be left out)

usage: python make_test_materials.py out.step
"""

import re
import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

# colour (sRGB) -> appearance name written into the file
APPEARANCES = {
    (0.627, 0.627, 0.627): "Aluminum - Satin",
    (0.153, 0.153, 0.153): "Rubber - Soft",
    (0.753, 0.0, 0.0): "Paint - Enamel Glossy (Red)",
}


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    mt = XCAFDoc_DocumentTool.MaterialTool_s(doc.Main())
    H = TCollection_HAsciiString

    def part(shape, text, rgb=None, material=None):
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        if rgb:
            ct.SetColor(lab, Quantity_Color(*rgb, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        if material:
            mt.SetMaterial(lab, H(material), H(""), 7850.0, H("density"), H("POSITIVE_RATIO_MEASURE"))
        return lab

    labels = [
        part(BRepPrimAPI_MakeBox(200.0, 100.0, 10.0).Shape(), "PLATE", (0.627, 0.627, 0.627), "Aluminium 6082"),
        part(BRepPrimAPI_MakeCylinder(20.0, 3.0).Shape(), "SEAL RING", (0.153, 0.153, 0.153), "EPDM"),
        part(BRepPrimAPI_MakeBox(50.0, 50.0, 50.0).Shape(), "BODY1", (0.753, 0.0, 0.0), "Steel"),
        part(BRepPrimAPI_MakeSphere(25.0).Shape(), "BODY2", (0.1, 0.2, 0.7), "Generic"),
        part(BRepPrimAPI_MakeCylinder(10.0, 80.0).Shape(), "BODY3"),
        part(BRepPrimAPI_MakeBox(30.0, 30.0, 5.0).Shape(), "TWIN", None, "Steel"),
        part(BRepPrimAPI_MakeCylinder(8.0, 30.0).Shape(), "TWIN", None, "Brass"),
    ]
    root = st.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.MATERIALS"))
    for i, lab in enumerate(labels):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(300.0 * i, 0.0, 0.0))
        st.AddComponent(root, lab, TopLoc_Location(t))
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.SetMaterialMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")

    # give the colours their appearance names, as Fusion and Inventor do
    with open(path, encoding="latin-1") as fh:
        text = fh.read()

    def named(m):
        rgb = tuple(round(float(v), 3) for v in re.split(r"\s*,\s*", m.group(1).strip()))
        name = APPEARANCES.get(rgb, "")
        return f"COLOUR_RGB('{name}',{m.group(1)})"

    text = re.sub(r"COLOUR_RGB\(''\s*,\s*([^)]*)\)", named, text, flags=re.S)
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(text)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_materials.step")
    print("written")
