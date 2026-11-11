"""Write a small machine axis with a telescopic way cover as a STEP assembly (task 0034; generic, no owner data).

TEST.WAYCOVER                    mm; the covers lie along X, nested into each other (axis at 0 = closed)
  BASE                           box 1000 x 300 x 60: the machine bed
  CARRIAGE                       box 100 x 200 x 120 on the bed at x = 60 (the axis joint moves it)
  COVER.1.PLATE, COVER.1.FLANGE  section 1 (two parts): plate 20 x 260 x 100 at x = 0 and a flange on it
  COVER.2                        section 2 (one part), x = 20
  COVER.3.PLATE, COVER.3.FLANGE  section 3 (two parts), x = 40
  COVER.4                        section 4, x = 60
  COVER.5                        section 5, x = 80 (the one at the carriage)

Five sections over a 500 mm axis: each one slides 100 mm relative to its neighbour, so the sections stand
at x + 100, 200, 300, 400, 500 mm when the axis is at 500 mm.

``--sections N`` (task 0035): N sections instead of five (COVER.1 … COVER.N at x = 0, 20 …; sections 1 and 3 of two
parts as above). Five is the default and gives the committed test_waycover_b.step.

``--both-sides`` (task 0035): TEST.WAYCOVER.TWO, a cover on each side of the carriage on one 500 mm X axis:
  BASE, FRAME.LEFT, FRAME.RIGHT  the bed and the two ends the covers are fixed to
  CARRIAGE                       box 200 x 200 x 120, x = 20 N … 20 N + 200 at axis 0 (left end of its travel)
  COVER.L.1 … COVER.L.N          left cover, nested at x = 0, 20 … (closed at axis 0); COVER.L.N touches the carriage
  COVER.R.1 … COVER.R.N          right cover, fixed end at the right (COVER.R.1), open at axis 0: section k stands at
                                 x = C + (N - k) 20 - 500 k / N, C = the carriage's right face at axis 500 mm
Both covers' section k moves k/N of the axis (500 mm: 100, 200 … 500 mm), the left one opening, the right one
closing; at 500 mm the right cover is nested against FRAME.RIGHT's side of the carriage. The sections next to the
carriage (COVER.L.N, COVER.R.N) may be made the carriage section (bolted to it).

usage: python make_test_waycover.py out.step [--sections N] [--both-sides]
"""

import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
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


def build(path: str, sections: int = 5, both_sides: bool = False) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def part(shape, text, rgb):
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(parent, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(parent, lab, TopLoc_Location(t))

    def box(x, y, z, dx, dy, dz):
        return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()

    yellow, grey, steel = (0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.62, 0.64, 0.68)
    root = st.NewShape()
    n = int(sections)
    if both_sides:
        TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.WAYCOVER.TWO"))
        t, travel = 20.0, 500.0
        c_left = n * t                                   # the carriage's left face at axis 0
        c_right = c_left + 200.0 + travel                # its right face at axis 500 mm
        end = c_right + n * t                            # the right cover's fixed end
        place(root, part(box(-40, 0, 0, end + 80, 300, 60), "BASE", grey))
        place(root, part(box(-40, 0, 60, 40, 300, 160), "FRAME.LEFT", grey))
        place(root, part(box(end, 0, 60, 40, 300, 160), "FRAME.RIGHT", grey))
        place(root, part(box(c_left, 50, 60, 200, 200, 120), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            place(root, part(box((k - 1) * t, 20, 60, t, 260, 110 - 2 * (k - 1)), f"COVER.L.{k}", steel))
            x = c_right + (n - k) * t - travel * k / n
            place(root, part(box(x, 20, 60, t, 260, 110 - 2 * (k - 1)), f"COVER.R.{k}", steel))
    else:
        TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.WAYCOVER"))
        place(root, part(box(0, 0, 0, 1000, 300, 60), "BASE", grey))
        place(root, part(box(60, 50, 60, 100, 200, 120), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            x = (k - 1) * 20.0
            if k in (1, 3):
                place(root, part(box(x, 20, 60, 20, 260, 100), f"COVER.{k}.PLATE", steel))
                place(root, part(box(x, 20, 160, 20, 260, 10), f"COVER.{k}.FLANGE", steel))
            else:
                place(root, part(box(x, 20, 60, 20, 260, 110), f"COVER.{k}", steel))
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    count = 5
    if "--sections" in sys.argv:
        count = int(sys.argv[sys.argv.index("--sections") + 1])
        args = [a for a in args if a != str(count)]
    build(args[0] if args else "test_waycover.step", sections=count, both_sides="--both-sides" in sys.argv)
    print("written")
