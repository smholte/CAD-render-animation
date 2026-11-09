"""Write the test tools of the tool library (task 0040) as STEP files. All sizes in mm.

test_tool_endmill.step     a fluted flat end mill Ø12: three helical flutes (30°) cut 3.4 mm deep over 26 mm, a
                           Ø12 shank up to 72 mm. The tool lies tilted in the file: tip at TIP, axis along AXIS
                           (from the tip into the shank). Made like a manufacturer's model: end teeth with a 10°
                           clearance, a 0.3 mm corner chamfer, the outer diameter only on the lands between the flutes (0037 problem 2: read as Ø10.4 before).
test_tool_facemill.step    an assembly "FACE MILL D50 + SK40": a Ø50 face mill (body + 5 inserts, 45°, 40 mm out of
                           the holder) in a simple SK40 holder; tip at the origin, axis +Z.
test_tool_x_endmill.step   task 0049: a fluted Ø10 end mill alone, laid out like ToolsUnited / Hoffmann models: along
                           +X, the shank's end on the origin, the tip at X = 75.
test_tool_x_bt30.step      task 0049: a BT30 chuck alone in the same layout: the gauge line on the origin, the flange
                           Ø46 and the nose Ø32 along +X (nose end at X = 45), the 7:24 taper and a pull stud along -X
                           (stud end at X = -71.4: further from the origin than the nose).

Downloaded manufacturer models are never committed (licences); these are made here.

usage: python make_test_tools.py <folder>
"""

import math
import os
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool

ENDMILL_D = 12.0
FLUTE_LEN = 26.0
TOTAL_LEN = 72.0
TIP = (10.0, 20.0, 30.0)
AXIS = (0.6, 0.0, 0.8)                    # unit: the end mill leans 36.87° from +Z towards +X

FACE_D = 50.0
FACE_STICK = 40.0                         # from the tip to the holder's nose
FACE_INSERTS = 5


def fluted_mill(radius: float, flute_len: float, total: float, flutes: int = 3, helix: float = 30.0,
                depth: float = 3.4, n: int = 36):
    """Lofted cross-sections: a circle with ``flutes`` notches, turned along the helix; then a round shank."""
    gen = BRepOffsetAPI_ThruSections(True, True, 1e-6)      # ruled: straight between sections
    zs = [k * 2.0 for k in range(int(flute_len / 2.0) + 1)]
    if zs[-1] < flute_len:
        zs.append(flute_len)
    for z in zs:
        phase = z * math.tan(math.radians(helix)) / radius
        poly = BRepBuilderAPI_MakePolygon()
        for k in range(n):
            a = 2 * math.pi * k / n
            u = ((a - phase) * flutes / (2 * math.pi)) % 1.0
            r = radius - (depth * math.sin(math.pi * u / 0.42) if u < 0.42 else 0.0)
            poly.Add(gp_Pnt(r * math.cos(a), r * math.sin(a), z))
        poly.Close()
        gen.AddWire(poly.Wire())
    gen.Build()
    body = gen.Shape()
    shank = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, flute_len), gp_Dir(0, 0, 1)), radius,
                                     total - flute_len).Shape()
    mill = BRepAlgoAPI_Fuse(body, shank).Shape()
    # the end teeth: behind each cutting edge the end face rises at a clearance angle of 10°
    for i in range(flutes):
        wedge = BRepPrimAPI_MakeBox(gp_Pnt(-0.5, 0.0, -6.0), radius + 2.0, 2.2 * radius, 6.0).Shape()
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), math.radians(10.0))
        r = gp_Trsf()
        r.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi * i / flutes + 0.15)
        mill = BRepAlgoAPI_Cut(mill, BRepBuilderAPI_Transform(wedge, r.Multiplied(t), True).Shape()).Shape()
    # a 0.3 mm × 45° chamfer on the outer corners: everything outside a cone goes
    c = 0.3
    keep = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, -0.01), gp_Dir(0, 0, 1)), radius - c - 0.01, radius + 3.0,
                                3.0 + c).Shape()
    ring = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -0.01), gp_Dir(0, 0, 1)), radius + 4.0, 3.0 + c).Shape()
    return BRepAlgoAPI_Cut(mill, BRepAlgoAPI_Cut(ring, keep).Shape()).Shape()


def moved(shape, tip, axis):
    """Turn +Z onto ``axis`` and put the origin on ``tip``."""
    t = gp_Trsf()
    ax = gp_Dir(*axis)
    z = gp_Dir(0, 0, 1)
    if abs(ax.Dot(z) - 1) > 1e-12:
        t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), z.Crossed(ax)), z.Angle(ax))
    m = gp_Trsf()
    m.SetTranslation(gp_Vec(*tip))
    return BRepBuilderAPI_Transform(shape, m.Multiplied(t), True).Shape()


def face_mill():
    r = FACE_D / 2
    body = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0.8), gp_Dir(0, 0, 1)), r - 4.5, 30.0).Shape()
    neck = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 30.8), gp_Dir(0, 0, 1)), 11.0, FACE_STICK - 30.8).Shape()
    shape = BRepAlgoAPI_Fuse(body, neck).Shape()
    for i in range(FACE_INSERTS):
        ins = BRepPrimAPI_MakeBox(gp_Pnt(r - 9.0, -1.75, 0.0), 9.0, 3.5, 6.0).Shape()
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2 * math.pi * i / FACE_INSERTS)
        shape = BRepAlgoAPI_Fuse(shape, BRepBuilderAPI_Transform(ins, t, True).Shape()).Shape()
    return shape


def sk40_holder():
    """Nose Ø40 from the tool up 40 mm, a flange Ø63.5, a 7:24 taper."""
    z0 = FACE_STICK
    nose = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z0), gp_Dir(0, 0, 1)), 20.0, 44.1).Shape()
    flange = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z0 + 44.1), gp_Dir(0, 0, 1)), 31.75, 15.9).Shape()
    taper = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, z0 + 60.0), gp_Dir(0, 0, 1)), 22.225, 12.25, 68.4).Shape()
    return BRepAlgoAPI_Fuse(BRepAlgoAPI_Fuse(nose, flange).Shape(), taper).Shape()


X_MILL_D = 10.0
X_MILL_LEN = 75.0
BT30_A = 45.0                             # nose end to the gauge line


def x_endmill():
    """The tip at +X 75, the shank's end on the origin: a fluted mill along +Z turned onto -X, moved by 75 mm."""
    return moved(fluted_mill(X_MILL_D / 2, 22.0, X_MILL_LEN, depth=2.6, n=24), (X_MILL_LEN, 0.0, 0.0), (-1.0, 0.0, 0.0))


def x_bt30():
    """A BT30 chuck along +Z from its nose (z = 0) to the gauge line (z = 45), taper and stud beyond; then turned
    onto -X with the gauge line on the origin (the nose at +X 45)."""
    a = BT30_A
    nose = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 16.0, a - 20.0).Shape()
    bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)), 6.0, 30.0).Shape()
    flange = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, a - 20.0), gp_Dir(0, 0, 1)), 23.0, 20.0).Shape()
    taper = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, a), gp_Dir(0, 0, 1)), 15.875, 15.875 - 48.4 * 7 / 48,
                                 48.4).Shape()
    stud = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, a + 48.4), gp_Dir(0, 0, 1)), 5.0, 23.0).Shape()
    shape = BRepAlgoAPI_Fuse(BRepAlgoAPI_Fuse(nose, flange).Shape(), taper).Shape()
    shape = BRepAlgoAPI_Cut(BRepAlgoAPI_Fuse(shape, stud).Shape(), bore).Shape()
    return moved(shape, (a, 0.0, 0.0), (-1.0, 0.0, 0.0))


def write(path: str, parts, assembly: str | None = None) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = []
    for shape, name in parts:
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(name))
        labels.append(lab)
    if assembly:
        root = st.NewShape()
        TDataStd_Name.Set_s(root, TCollection_ExtendedString(assembly))
        for lab in labels:
            st.AddComponent(root, lab, TopLoc_Location(gp_Trsf()))
        st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


def build(folder: str) -> None:
    mill = moved(fluted_mill(ENDMILL_D / 2, FLUTE_LEN, TOTAL_LEN), TIP, AXIS)
    write(os.path.join(folder, "test_tool_endmill.step"), [(mill, "END MILL D12 Z3")])
    write(os.path.join(folder, "test_tool_facemill.step"), [(face_mill(), "FACE MILL D50"),
                                                             (sk40_holder(), "SK40 HOLDER")],
          assembly="FACE MILL D50 + SK40")
    write(os.path.join(folder, "test_tool_x_endmill.step"), [(x_endmill(), "END MILL D10 ALONG X")])
    write(os.path.join(folder, "test_tool_x_bt30.step"), [(x_bt30(), "BT30 ER CHUCK ALONG X")])


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("written")
