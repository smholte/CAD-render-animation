"""Write a small STEP assembly with faces painted in CAD, for automated tests (task 0010).

TEST.FACES (revision "a")
  HOUSING      grey box; top face red, front face blue with the appearance name
               "Aluminum - Anodized Glossy (Blue)" (as Fusion writes a face appearance)
  BRACKET  x2  steel-grey plate; one end face orange (two copies of one part)
  COVER        light grey plate, no painted faces (for painting by hand)
  BLOCK        white box, no painted faces (painted by hand, then changed in revision "b")
  EVERY FACE   green box whose six faces all carry the part colour (some exporters do this):
               no extra face sets
Revision "b": the same, but BLOCK is a cylinder now (its faces changed).

usage: python make_test_faces.py out.step [a|b]
"""

import re
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
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

GREY = (0.6, 0.6, 0.6)
RED = (0.8, 0.1, 0.1)
BLUE = (0.2, 0.333, 0.8)
STEEL = (0.45, 0.45, 0.47)
ORANGE = (1.0, 0.5, 0.0)
LIGHT = (0.9, 0.9, 0.9)
WHITE = (0.95, 0.95, 0.95)
GREEN = (0.3, 0.6, 0.3)

# colour (sRGB, as written) -> appearance name given to it afterwards
APPEARANCES = {BLUE: "Aluminum - Anodized Glossy (Blue)"}

# face numbers (OpenCascade's order) that get their own colour
HOUSING_TOP, HOUSING_FRONT = 5, 2      # box faces: 0 -X, 1 +X, 2 -Y, 3 +Y, 4 -Z, 5 +Z
BRACKET_END = 1


def build(path: str, rev: str = "a") -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def colour(label, rgb):
        ct.SetColor(label, Quantity_Color(*rgb, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)

    def part(shape, text, rgb, faces=None):
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        colour(lab, rgb)
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        k = 0
        while exp.More():
            face_rgb = (faces or {}).get(k)
            if face_rgb:
                colour(st.AddSubShape(lab, exp.Current()), face_rgb)
            exp.Next()
            k += 1
        return lab

    housing = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 300.0, 200.0, 100.0).Shape(), "HOUSING", GREY,
                   {HOUSING_TOP: RED, HOUSING_FRONT: BLUE})
    bracket = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 80.0, 40.0, 10.0).Shape(), "BRACKET", STEEL,
                   {BRACKET_END: ORANGE})
    cover = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 400.0, 300.0, 5.0).Shape(), "COVER", LIGHT)
    if rev == "b":
        block = part(BRepPrimAPI_MakeCylinder(50.0, 100.0).Shape(), "BLOCK", WHITE)
    else:
        block = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 100.0, 100.0, 100.0).Shape(), "BLOCK", WHITE)
    every = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 60.0, 60.0, 60.0).Shape(), "EVERY FACE", GREEN,
                 {k: GREEN for k in range(6)})

    root = st.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.FACES"))
    for lab, x, y in ((housing, 0, 0), (bracket, 400, 0), (bracket, 400, 100), (cover, 0, 300),
                      (block, 600, 0), (every, 800, 0)):
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

    # the appearance name of the blue face, as Fusion and Inventor write it
    with open(path, encoding="latin-1") as fh:
        text = fh.read()

    def named(m):
        rgb = tuple(round(float(v), 3) for v in re.split(r"\s*,\s*", m.group(1).strip()))
        return f"COLOUR_RGB('{APPEARANCES.get(rgb, '')}',{m.group(1)})"

    text = re.sub(r"COLOUR_RGB\(''\s*,\s*([^)]*)\)", named, text, flags=re.S)
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(text)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_faces.step", sys.argv[2] if len(sys.argv) > 2 else "a")
    print("written")
