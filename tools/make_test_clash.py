"""Write a small test model for the clash check as a STEP assembly (task 0065; generic, no owner data).

All sizes in mm. Two arms stand on vertical pins on a base plate and point along +Y in the CAD pose. Arm B turns
first (+90° about its pin) and then lies along -X; then arm A turns down (-90° about its pin) and lies along +X just
above arm B: arm A's flat underside goes exactly 6.0 mm into arm B's flat side.

TEST.CLASH
  BASE.ASM
    BASE                    plate x -400 … 1100, y -100 … 800, z -20 … 0 (top at z = 0)
    PIN.A                   pin Ø20 at (0, 44), z 0 … 80
    PIN.B                   pin Ø20 at (1000, 0), z 0 … 80
    BLOCK                   low block under arm A's path: 80 x 80 turned 45°, round (212, 256), z 0 … 13; arm A's
                            underside is at z = 15, so it passes 2.0 mm above the block (a near miss)
    POST                    thin plate 4 mm thick, 100 long (radial), z 0 … 100, at 135° from +X, 250 … 350 mm from
                            pin A: arm A turning the other way (+90°) goes through it
  ARM.A.ASM
    ARM.A                   x -20 … 20, y 14 … 744 (700 mm from its pin), z 15 … 55, bore Ø20 at (0, 44)
  ARM.B.ASM
    ARM.B                   x 970 … 1030, y -30 … 503, z 5 … 65, bore Ø20 at (1000, 0)

Turned, arm B covers x 497 … 1030, y -30 … 30; arm A covers x -30 … 700, y 24 … 64. Over x 497 … 700 arm A's
underside (y = 24) is 6.0 mm inside arm B (its side at y = 30), far from B's other faces (B is 10 mm taller at the top
and the bottom): the clash is 6.0 mm deep, between flat faces (the same in every mesh quality). Arm A comes down onto
B, so every point of it is deepest at the end: the clash is deepest at the last frame.

usage: python make_test_clash.py out.step
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
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

PIN_R = 10.0
PIVOT_A = (0.0, 44.0)
PIVOT_B = (1000.0, 0.0)
LEN_A, HALF_A, Z_A = 700.0, 20.0, (15.0, 55.0)
LEN_B, HALF_B, Z_B = 503.0, 30.0, (5.0, 65.0)
DEPTH = HALF_B - (PIVOT_A[1] - HALF_A)                     # 30 - 24 = 6.0 mm
GAP = 2.0                                                 # arm A over the block
POST_ANGLE = 135.0


def _box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def _cyl(x, y, z0, z1, r):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z0), gp_Dir(0, 0, 1)), r, z1 - z0).Shape()


def arm(px, py, length, half_w, z0, z1):
    """An arm along +Y from its pin at (px, py), with a bore for the pin."""
    body = _box(px - half_w, py - 30.0, z0, 2 * half_w, length + 30.0, z1 - z0)
    return BRepAlgoAPI_Cut(body, _cyl(px, py, z0 - 1, z1 + 1, PIN_R)).Shape()


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
        lab = st.AddShape(shape, False)
        name(lab, text)
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, trsf=None):
        st.AddComponent(assy, lab, TopLoc_Location(trsf if trsf is not None else gp_Trsf()))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, orange, steel = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.95, 0.45, 0.05), (0.8, 0.8, 0.82)
    base = part(_box(-400, -100, -20, 1500, 900, 20), "BASE", grey)
    pin_a = part(_cyl(PIVOT_A[0], PIVOT_A[1], 0, 80, PIN_R), "PIN.A", steel)
    pin_b = part(_cyl(PIVOT_B[0], PIVOT_B[1], 0, 80, PIN_R), "PIN.B", steel)
    # the block: a square 80 x 80 round (200, 200), turned 45° about its centre, top 2 mm below arm A
    blk = _box(-40, -40, 0, 80, 80, 15.0 - GAP)
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(45))
    t2 = gp_Trsf()
    t2.SetTranslation(gp_Vec(PIVOT_A[0] + 300 * math.cos(math.radians(45)),
                             PIVOT_A[1] + 300 * math.sin(math.radians(45)), 0))
    block = part(blk, "BLOCK", blue)
    # the post: 100 long along the radius at 135°, 4 thick
    post = part(_box(250, -2, 0, 100, 4, 100), "POST", blue)
    tp = gp_Trsf()
    tp.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(POST_ANGLE))
    tp2 = gp_Trsf()
    tp2.SetTranslation(gp_Vec(PIVOT_A[0], PIVOT_A[1], 0))
    tp = tp2.Multiplied(tp)
    arm_a = part(arm(PIVOT_A[0], PIVOT_A[1], LEN_A, HALF_A, *Z_A), "ARM.A", orange)
    arm_b = part(arm(PIVOT_B[0], PIVOT_B[1], LEN_B, HALF_B, *Z_B), "ARM.B", orange)

    base_asm = asm("BASE.ASM")
    place(base_asm, base)
    place(base_asm, pin_a)
    place(base_asm, pin_b)
    place(base_asm, block, t2.Multiplied(t))
    place(base_asm, post, tp)
    a_asm = asm("ARM.A.ASM")
    place(a_asm, arm_a)
    b_asm = asm("ARM.B.ASM")
    place(b_asm, arm_b)
    root = asm("TEST.CLASH")
    place(root, base_asm)
    place(root, a_asm)
    place(root, b_asm)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_clash.step")
    print("written")
