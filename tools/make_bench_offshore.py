"""Write an invented offshore-style assembly to measure meshing (task 0074): big round parts next to many fasteners.

BENCH.OFFSHORE
  SLEWING RING D10000          Ø10 m ring, 72 bolt holes
  DRUM D2000                   Ø2 m cable drum with two flanges
  FRAME PLATE                  4 m x 2 m plate, 40 holes
  BRACKET                      small bracket with holes          x8
  PIN D60                      hinge pin                         x8
  ISO 4017 M36/M24/M16/M10, ISO 4032 nuts, ISO 7089 washers      ~450 placed

Nothing of it is a real machine. Not used by the app; tests build their shapes in memory.

usage: python make_bench_offshore.py out.step
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool


def cyl(r, h, x=0.0, y=0.0, z=0.0):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()


def cut(a, *tools):
    for t in tools:
        a = BRepAlgoAPI_Cut(a, t).Shape()
    return a


def fuse(a, *tools):
    for t in tools:
        a = BRepAlgoAPI_Fuse(a, t).Shape()
    return a


def hexagon(s, h, z=0.0):
    r = s / math.sqrt(3.0)
    poly = BRepBuilderAPI_MakePolygon()
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        poly.Add(gp_Pnt(r * math.cos(a), r * math.sin(a), z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, h)).Shape()


def fillet_all(shape, r):
    mk = BRepFilletAPI_MakeFillet(shape)
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        mk.Add(r, TopoDS.Edge(ex.Current()))
        ex.Next()
    try:
        return mk.Shape()
    except Exception:
        return shape


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def part(shape, text):
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        return lab

    def place(assy, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(assy, lab, TopLoc_Location(t))

    ring_r = 5000.0
    holes = [cyl(22.5, 400, (ring_r - 150) * math.cos(a), (ring_r - 150) * math.sin(a), -50)
             for a in (2 * math.pi * k / 72 for k in range(72))]
    ring = part(cut(cyl(ring_r, 300), cyl(ring_r - 300, 400, z=-50), *holes), "SLEWING RING D10000")
    drum = part(fuse(cyl(1000, 3000), cyl(1300, 60), cyl(1300, 60, z=2940)), "DRUM D2000")
    plate = cut(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 4000.0, 2000.0, 40.0).Shape(),
                *[cyl(13, 100, 200 + 400 * i, 200 + 400 * j, -10) for i in range(10) for j in range(4)])
    plate = part(plate, "FRAME PLATE")
    bracket = cut(fillet_all(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 160.0, 80.0, 20.0).Shape(), 4.0),
                  cyl(9, 40, 30, 40, -10), cyl(9, 40, 130, 40, -10), cyl(20, 40, 80, 40, -10))
    bracket = part(bracket, "BRACKET")
    pin = part(cyl(30, 250), "PIN D60")
    sizes = {36: (55, 160, 31, 20), 24: (36, 100, 21, 60), 16: (24, 60, 14, 120), 10: (16, 30, 8, 250)}
    fasteners = []
    for d, (s, length, k, n) in sizes.items():
        bolt = part(fuse(hexagon(s, k), cyl(d / 2, length, z=k)), f"ISO 4017 M{d}x{length} - 8.8")
        nut = part(cut(hexagon(s, 0.8 * d), cyl(d / 2, d * 2, z=-d / 2)), f"ISO 4032 M{d} - 8")
        washer = part(cut(cyl(1.1 * s / 2, d / 6), cyl(d / 2 + 0.5, d, z=-d / 4)), f"ISO 7089 {d} - 200 HV")
        fasteners.append((bolt, nut, washer, n))

    root = st.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("BENCH.OFFSHORE"))
    place(root, ring)
    place(root, drum, 0, 0, 1000)
    place(root, plate, 6000, 0, 0)
    for k in range(8):
        place(root, bracket, 6000 + 400 * k, 2500, 0)
        place(root, pin, 6000 + 400 * k, 3000, 0)
    x = 0.0
    for bolt, nut, washer, n in fasteners:
        for k in range(n):
            px, py = 12000 + (k % 25) * 120.0, x + (k // 25) * 120.0
            place(root, bolt, px, py, 0)
            place(root, nut, px, py, 200)
            place(root, washer, px, py, 260)
        x += 2000.0
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise SystemExit("writing failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "bench_offshore.step")
