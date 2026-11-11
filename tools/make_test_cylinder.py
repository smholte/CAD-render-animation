"""Write a small luffing arm with hydraulic cylinders as a STEP assembly (task 0013; generic, no owner data).

TEST.LUFFER                      mm; every pin turns about Y
  BASE                           box 1200 x 400 x 100
  POST                           carries the arm pivot (100, *, 600): a block up to 30 mm under the arm and a fork
                                 (two cheeks, bore Ø40.4) the arm turns in
  BASE.BRACKET                   carries the barrel pins (500, *, 150), bore Ø40; a slot for each cylinder (task 0072:
                                 no part starts inside another, so the clash check never sits on its threshold)
  BASE.PIN                       Ø40 along Y through the barrel pins (pick target)
  ARM.ASM                        turns about the pivot
    ARM                          box 1500 x 100 x 100 from the pivot along X
    ARM.PIN                      Ø40 along Y at the pivot (pick target for the arm joint)
    ARM.BRACKET                  under the arm, carries the rod pins (800, *, 450), bore Ø40; a slot per cylinder
    ARM.ROD.PIN                  Ø40 along Y through the rod pins (pick target)
  CYL.ASM  (twice: y = 80 and y = 320, side by side)
    CYL.BARREL                   BARREL.CAP (end cap + eye), BARREL.TUBE (Ø100/80), BARREL.GLAND (bore Ø32)
    CYL.ROD                      PISTON (Ø78), ROD (Ø30), ROD.EYE
  TELE.ASM (y = 200, telescopic: barrel, one stage, rod)
    TELE.BARREL, TELE.STAGE, TELE.ROD

The cylinders lie at 45°: barrel pin (500, 150), rod pin (800, 450), pin to pin 424.26 mm. Their rod can
go 60 mm in (piston back face 100 mm from the barrel pin, end cap inside at 40) and 130 mm out (piston
front 130, gland at 260): closed length 364.26 mm, full stroke 190 mm.

Revision B: a new ARM.LAMP in ARM.ASM and the two CYL.ASM placed in the other order.

usage: python make_test_cylinder.py out.step [A|B]
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
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

PIVOT = (100.0, 600.0)          # (x, z) of the arm pivot
BARREL_PIN = (500.0, 150.0)
ROD_PIN = (800.0, 450.0)
LENGTH = math.hypot(ROD_PIN[0] - BARREL_PIN[0], ROD_PIN[1] - BARREL_PIN[1])     # 424.26
CYL_Y = (80.0, 320.0)
TELE_Y = 200.0
SLOT = 55.0                     # half the width of a bracket's slot round a cylinder (Ø100 barrel, gland)


def _along_x(x0, x1, r):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, 0, 0), gp_Dir(1, 0, 0)), r, x1 - x0).Shape()


def _hollow_x(x0, x1, r_in, r_out):
    return BRepAlgoAPI_Cut(_along_x(x0, x1, r_out), _along_x(x0 - 1, x1 + 1, r_in)).Shape()


def _eye(x, r_out, r_in, width):
    """A ring around a pin along Y at (x, 0, 0)."""
    outer = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, -width / 2, 0), gp_Dir(0, 1, 0)), r_out, width).Shape()
    bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, -width, 0), gp_Dir(0, 1, 0)), r_in, 2 * width).Shape()
    return BRepAlgoAPI_Cut(outer, bore).Shape()


def _fuse(a, b):
    return BRepAlgoAPI_Fuse(a, b).Shape()


def build(path: str, revision: str = "A") -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb=None):
        lab = st.AddShape(shape, False)
        name(lab, text)
        if rgb:
            ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB),
                        XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def assy(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    def place(parent, lab, x=0.0, y=0.0, z=0.0, turn_y=0.0):
        """Turn about Y (degrees) first, then move."""
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        if turn_y:
            r = gp_Trsf()
            r.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), math.radians(turn_y))
            t = t.Multiplied(r)
        st.AddComponent(parent, lab, TopLoc_Location(t))

    yellow, grey, steel, chrome = (0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.55, 0.57, 0.6), (0.85, 0.86, 0.88)
    px, pz = PIVOT
    bx, bz = BARREL_PIN
    rx, rz = ROD_PIN
    L = LENGTH

    base = part(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1200.0, 400.0, 100.0).Shape(), "BASE", yellow)
    # the post: a block up to 30 mm under the arm (which is 100 wide at y 150..250), cheeks either side of it
    post = BRepPrimAPI_MakeBox(gp_Pnt(px - 60, 115, 100), 120.0, 170.0, pz - 50 - 30 - 100).Shape()
    for y0 in (115.0, 255.0):
        post = _fuse(post, BRepPrimAPI_MakeBox(gp_Pnt(px - 40, y0, pz - 120), 80.0, 30.0, 160.0).Shape())
    post = BRepAlgoAPI_Cut(post, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(px, 100, pz), gp_Dir(0, 1, 0)), 20.2,
                                                          200.0).Shape()).Shape()
    post = part(post, "POST", yellow)
    bracket = BRepPrimAPI_MakeBox(gp_Pnt(bx - 40, 10, 100), 80.0, 380.0, 90.0).Shape()
    bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(bx, 0, bz), gp_Dir(0, 1, 0)), 20.0, 400.0).Shape()
    bracket = BRepAlgoAPI_Cut(bracket, bore).Shape()
    for y in CYL_Y + (TELE_Y,):                                    # a slot for each cylinder's barrel (Ø100)
        bracket = BRepAlgoAPI_Cut(bracket, BRepPrimAPI_MakeBox(gp_Pnt(bx - 50, y - SLOT, bz - 35), 100.0, 2 * SLOT,
                                                               100.0).Shape()).Shape()
    base_bracket = part(bracket, "BASE.BRACKET", yellow)
    base_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(bx, -20, bz), gp_Dir(0, 1, 0)), 20.0, 440.0).Shape(),
                    "BASE.PIN", chrome)

    # the arm, built at the pivot
    arm = part(BRepPrimAPI_MakeBox(gp_Pnt(0, -50, -50), 1500.0, 100.0, 100.0).Shape(), "ARM", yellow)
    arm_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -90, 0), gp_Dir(0, 1, 0)), 20.0, 180.0).Shape(),
                   "ARM.PIN", chrome)
    ax, az = rx - px, rz - pz                                      # rod pin relative to the pivot
    abox = BRepPrimAPI_MakeBox(gp_Pnt(ax - 40, -190, az - 40), 80.0, 380.0, -50 - (az - 40)).Shape()
    abore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(ax, -200, az), gp_Dir(0, 1, 0)), 20.0, 400.0).Shape()
    abox = BRepAlgoAPI_Cut(abox, abore).Shape()
    for y in CYL_Y + (TELE_Y,):                                    # a slot for each rod end and gland (Ø100)
        abox = BRepAlgoAPI_Cut(abox, BRepPrimAPI_MakeBox(gp_Pnt(ax - 50, y - 200 - SLOT, az - 50), 100.0, 2 * SLOT,
                                                         110.0).Shape()).Shape()
    arm_bracket = part(abox, "ARM.BRACKET", yellow)
    arm_rod_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(ax, -220, az), gp_Dir(0, 1, 0)), 20.0,
                                                440.0).Shape(), "ARM.ROD.PIN", chrome)
    lamp = part(BRepPrimAPI_MakeSphere(30.0).Shape(), "ARM.LAMP") if revision == "B" else None

    # a cylinder, built along X from its barrel pin (x = 0) to its rod pin (x = L)
    cap = part(_fuse(_along_x(20, 40, 50), _eye(0, 30, 20, 40)), "BARREL.CAP", grey)
    tube = part(_hollow_x(40, 260, 40, 50), "BARREL.TUBE", grey)
    gland = part(_hollow_x(260, 290, 16, 50), "BARREL.GLAND", grey)
    piston = part(_along_x(100, 130, 39), "PISTON", steel)
    rod = part(_along_x(130, L - 25, 15), "ROD", chrome)
    rod_eye = part(_eye(L, 30, 20, 40), "ROD.EYE", steel)

    barrel_asm = assy("CYL.BARREL")
    for lab in (cap, tube, gland):
        place(barrel_asm, lab)
    rod_asm = assy("CYL.ROD")
    for lab in (piston, rod, rod_eye):
        place(rod_asm, lab)
    cyl = assy("CYL.ASM")
    place(cyl, barrel_asm)
    place(cyl, rod_asm)

    # telescopic: barrel, one stage, rod (each section slides 1/2 of the rod's travel)
    t_barrel = part(_fuse(_fuse(_along_x(20, 40, 50), _eye(0, 30, 20, 40)), _hollow_x(40, 200, 40, 50)),
                    "TELE.BARREL", grey)
    t_stage = part(_fuse(_hollow_x(150, 300, 28, 38), _hollow_x(150, 165, 28, 39)), "TELE.STAGE", steel)
    t_rod = part(_fuse(_along_x(220, L - 25, 20), _eye(L, 30, 20, 40)), "TELE.ROD", chrome)
    tele = assy("TELE.ASM")
    for lab in (t_barrel, t_stage, t_rod):
        place(tele, lab)

    arm_asm = assy("ARM.ASM")
    place(arm_asm, arm)
    place(arm_asm, arm_pin)
    place(arm_asm, arm_bracket)
    place(arm_asm, arm_rod_pin)
    if lamp is not None:
        place(arm_asm, lamp, 1450, 0, 80)

    root = assy("TEST.LUFFER")
    place(root, base)
    place(root, post)
    place(root, base_bracket)
    place(root, base_pin)
    place(root, arm_asm, px, 200, pz)
    turn = -math.degrees(math.atan2(rz - bz, rx - bx))      # local +X onto the line barrel pin -> rod pin
    for y in (CYL_Y if revision == "A" else tuple(reversed(CYL_Y))):
        place(root, cyl, bx, y, bz, turn_y=turn)
    place(root, tele, bx, TELE_Y, bz, turn_y=turn)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_cylinder.step", sys.argv[2] if len(sys.argv) > 2 else "A")
    print("written")
