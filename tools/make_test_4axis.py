"""Write a small generic mill with a 4th axis (an A-axis rotary table and a tailstock) as a STEP assembly (task 0066).

Nothing of a real machine: all sizes in mm, Z up. The bed stands still; a moving column carries the tool in X, Y and
Z; the rotary table turns about the X axis line y = 0, z = 150 and holds a round bar between its chuck and the
tailstock's centre.

TEST.4AXIS
  BED                       fixed, top at z = 0
  HEADSTOCK                 fixed: the rotary table's housing, x -230 .. -160
  TAILSTOCK                 fixed: block x 140 .. 200 and its centre (a cone) touching the bar's end at x = 120
  A.ASM                     turns about the line y = 0, z = 150 along X (a rotate joint in the tests)
    CHUCK                   Ø90, x -160 .. -120
    BAR D50x240             the workpiece: Ø50, x -120 .. 120, its top at z = 175
  X.ASM                     moves along X
    COLUMN
    Y.ASM                   moves along Y
      RAM
      Z.ASM                 moves along Z
        HEAD, SPINDLE
        TOOL T1 FLAT D6     flat end mill Ø6, 40 long: tip at (0, 0, 190), 15 above the bar

usage: python make_test_4axis.py out.step
"""

import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
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

from make_test_atc import _box, _cyl, _fuse

AXIS_Z = 150.0                      # the A axis: y = 0, z = 150
BAR_R = 25.0
TIP_Z = 190.0
GREY, BLUE, STEEL, DARK = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.8, 0.8, 0.82), (0.25, 0.27, 0.3)
ALU = (0.75, 0.76, 0.78)


class Doc:
    """A STEP assembly document: parts, sub-assemblies, placements (shared by make_test_5axis.py)."""

    def __init__(self):
        app = XCAFApp_Application.GetApplication_s()
        self.doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
        app.InitDocument(self.doc)
        self.st = XCAFDoc_DocumentTool.ShapeTool_s(self.doc.Main())
        self.ct = XCAFDoc_DocumentTool.ColorTool_s(self.doc.Main())

    def _name(self, label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(self, shape, text, rgb=None):
        lab = self.st.AddShape(shape, False)
        self._name(lab, text)
        if rgb:
            self.ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB),
                             XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def asm(self, text, *children):
        lab = self.st.NewShape()
        self._name(lab, text)
        for ch in children:
            self.place(lab, ch)
        return lab

    def place(self, assy, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        self.st.AddComponent(assy, lab, TopLoc_Location(t))

    def write(self, path: str):
        self.st.UpdateAssemblies()
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        writer.Transfer(self.doc, STEPControl_StepModelType.STEPControl_AsIs)
        if writer.Write(path) != IFSelect_RetDone:
            raise RuntimeError("STEP write failed")


def head(d: Doc, tip_z: float):
    """The moving column, ram, head, spindle and tool T1 (flat Ø6, 40 long), its tip at (0, 0, tip_z)."""
    column = d.part(_box(-50, 150, 0, 100, 60, tip_z + 210), "COLUMN", BLUE)
    ram = d.part(_box(-40, 0, tip_z + 150, 80, 210, 60), "RAM", GREY)
    hd = d.part(_box(-35, -35, tip_z + 70, 70, 70, 120), "HEAD", BLUE)
    spindle = d.part(_cyl(0, 0, tip_z + 40, 25.0, 30.0), "SPINDLE", GREY)
    tool = d.part(_cyl(0, 0, tip_z, 3.0, 40.0), "TOOL T1 FLAT D6", STEEL)
    z_asm = d.asm("Z.ASM", hd, spindle, tool)
    y_asm = d.asm("Y.ASM", ram, z_asm)
    return d.asm("X.ASM", column, y_asm)


def build(path: str) -> None:
    d = Doc()
    bed = d.part(_box(-250, -150, -60, 500, 300, 60), "BED", BLUE)
    headstock = d.part(_box(-230, -60, 0, 70, 120, AXIS_Z + 50), "HEADSTOCK", BLUE)
    centre = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(140, 0, AXIS_Z), gp_Dir(-1, 0, 0)), 15.0, 0.0, 20.0).Shape()
    tailstock = d.part(_fuse(_box(140, -40, 0, 60, 80, AXIS_Z + 25), centre), "TAILSTOCK", BLUE)
    chuck = d.part(_cyl(-160, 0, AXIS_Z, 45.0, 40.0, (1, 0, 0)), "CHUCK", DARK)
    bar = d.part(_cyl(-120, 0, AXIS_Z, BAR_R, 240.0, (1, 0, 0)), "BAR D50x240", ALU)
    a_asm = d.asm("A.ASM", chuck, bar)
    root = d.asm("TEST.4AXIS", bed, headstock, tailstock, a_asm, head(d, TIP_Z))
    d.write(path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_4axis.step")
    print("written")
