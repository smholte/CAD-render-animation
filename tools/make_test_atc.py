"""Write a small generic vertical mill with a double-arm tool changer as a STEP assembly (task 0064).

Nothing of a real machine: all sizes in mm, Z up. The table moves along X and Y, the head along Z; the arm and the
disc magazine hang from the column. The CAD pose is the change position: the spindle's gauge line (its nose) at
z = 300 on the axis x = 0, y = 0.

TEST.ATC
  BED, COLUMN               fixed
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE
    X.ASM                   moves along X
      TABLE
      STOCK 160x120x30      x -80..80, y -60..60, z 60..90
  Z.ASM                     moves along Z
    HEAD, SPINDLE           spindle Ø90, its nose (the gauge line) at z = 300
    TOOL T1 BT30 FLAT D10   BT30 holder + flat end mill Ø10, stick-out 40: tip at (0, 0, 215), gauge length 85
  ATC HOUSING, MAGAZINE POST   fixed, above the arm's hub and in the magazine's middle
  ARM.ASM
    CHANGER ARM             hub (round, Ø60) on the axis x = -130, y = 0, vertical; a bar (z 281..299, 1 mm under
                            the spindle's nose) with a U-shaped claw at each end (round inside, Ø47, around a BT30
                            flange Ø46); the claw's open side is cut along the ring round the hub the flange sweeps
                            when the arm turns in. In the CAD it is at rest, along Y; turned +90° about +Z its claws
                            are round x = 0 (the spindle) and x = -260 (the station)
  MAGAZINE.ASM              turns about the vertical axis x = -460, y = 0
    MAGAZINE DISC           Ø280, z 330..350 (inside the pots' hinges: a tipped pot clears it)
    POT                     12 of the same part, one every 30° counter-clockwise from +X (pot 1 at the station):
                            a sleeve lying radially (the tool points outward), its mouth (the gauge line) at radius
                            200, z = 400; it tips down 90° about a hinge pin (round, along the tangent) at radius 150,
                            z = 350: tipped, the station pot's mouth is at (-260, 0, 300), the tool hanging down
    TOOL T2 BT30 BALL D8    in pot 2 (BT30 + ball end mill Ø8, stick-out 35, gauge length 80)

usage: python make_test_atc.py out.step
"""

import math
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakeSphere)
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

GAUGE_Z = 300.0                     # the spindle's nose (gauge line) in the CAD pose
HUB = (-130.0, 0.0)                 # the arm's axis
GRIP_R = 130.0
MAG = (-460.0, 0.0)                 # the magazine's axis
POTS = 12
POT_R = 200.0                       # the pot's mouth (gauge line), from the magazine's axis
POT_Z = 400.0
HINGE_R, HINGE_Z = 150.0, 350.0
DISC_R = 140.0                      # inside the hinges: a tipping pot's block swings down past the disc's rim
T1_STICK, T2_STICK = 40.0, 35.0
BT30_GAUGE = 45.0                   # from the holder's nose to its gauge line (core/tools.py HOLDER_SIZES)


def _fuse(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return out


def _cyl(x, y, z, r, h, d=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*d)), r, h).Shape()


def _cone(z, r1, r2, h):
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r1, r2, h).Shape()


def _box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def _moved(shape, trsf):
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def bt30_tool(stick: float, radius: float, ball: bool = False):
    """A BT30 holder with an end mill, the tip at the origin, along +Z: nose at ``stick``, gauge line 45 above it."""
    if ball:
        mill = _fuse(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, radius), radius).Shape(),
                     _cyl(0, 0, radius, radius, stick - radius))
    else:
        mill = _cyl(0, 0, 0, radius, stick)
    g = stick + BT30_GAUGE
    nose = _cone(stick, 16.0, 18.0, 25.0)
    flange = _cyl(0, 0, g - 20.0, 23.0, 20.0)
    taper = _cone(g, 15.875, 15.875 - 48.4 * 7 / 48, 48.4)
    stud = _cyl(0, 0, g + 48.4, 5.0, 23.0)
    return _fuse(mill, nose, flange, taper, stud)


def changer_arm():
    """The arm in its grip pose (claws round x = 0 and x = -260), then turned back -90° about its hub to rest."""
    hx, hy = HUB
    z0, h = GAUGE_Z - 19.0, 18.0              # 1 mm clear of the spindle's nose, round the flange (z 280 … 300)
    bar = _box(-GRIP_R * 2, -15.0, z0, GRIP_R * 2, 30.0, h)
    hub = _cyl(hx, hy, z0, 30.0, 60.0)
    shapes = [bar, hub]
    for cx, opening in ((0.0, 1.0), (-2 * GRIP_R, -1.0)):
        ring = BRepAlgoAPI_Cut(_cyl(cx, 0, z0, 33.0, h), _cyl(cx, 0, z0 - 1, 23.5, h + 2)).Shape()
        # open towards the way the claw moves when the arm turns +Z into the tools (U-shaped claw)
        y0 = 0.0 if opening > 0 else -40.0
        ring = BRepAlgoAPI_Cut(ring, _box(cx - 23.5, y0, z0 - 1, 47.0, 40.0, h + 2)).Shape()
        shapes.append(ring)
    arm = _fuse(*shapes)
    arm = BRepAlgoAPI_Cut(arm, _cyl(0, 0, z0 - 1, 23.5, h + 2)).Shape()
    arm = BRepAlgoAPI_Cut(arm, _cyl(-2 * GRIP_R, 0, z0 - 1, 23.5, h + 2)).Shape()
    # the way in: the arm turns about its hub, so the flange sweeps a ring round the hub (radius 130 ± 23); nothing of
    # the claw or the bar may stand in that ring on the open side (task 0067: the bar narrowed the opening)
    ring = BRepAlgoAPI_Cut(_cyl(hx, hy, z0 - 1, GRIP_R + 23.5, h + 2), _cyl(hx, hy, z0 - 2, GRIP_R - 23.5, h + 4)).Shape()
    for cx, opening in ((0.0, 1.0), (-2 * GRIP_R, -1.0)):
        y0 = 0.0 if opening > 0 else -45.0
        way = BRepAlgoAPI_Common(ring, _box(cx - 40.0, y0, z0 - 1, 80.0, 45.0, h + 2)).Shape()
        arm = BRepAlgoAPI_Cut(arm, way).Shape()
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(hx, hy, 0), gp_Dir(0, 0, 1)), -math.pi / 2)
    return _moved(arm, t)


def pot():
    """Pot 1 at the station (towards +X from the magazine's axis), not tipped: a sleeve lying along X, its mouth at
    the gauge point, a block down to the hinge pin."""
    mx, my = MAG
    mouth = mx + POT_R
    sleeve = BRepAlgoAPI_Cut(_cyl(mouth - 80.0, my, POT_Z, 28.0, 80.0, (1, 0, 0)),
                             _cyl(mouth - 76.0, my, POT_Z, 18.0, 80.0, (1, 0, 0))).Shape()
    hx = mx + HINGE_R
    block = _box(hx - 15.0, my - 15.0, HINGE_Z, 30.0, 30.0, POT_Z - 28.0 - HINGE_Z + 2.0)
    pin = _cyl(hx, my - 20.0, HINGE_Z, 6.0, 40.0, (0, 1, 0))
    return _fuse(sleeve, block, pin)


def build(path: str) -> None:
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

    def place(assy, lab, trsf=None, x=0.0, y=0.0, z=0.0):
        if trsf is None:
            trsf = gp_Trsf()
            trsf.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(assy, lab, TopLoc_Location(trsf))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, steel, dark = (0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.8, 0.8, 0.82), (0.25, 0.27, 0.3)
    bed = part(_box(-250, -250, -80, 500, 500, 80), "BED", blue)
    column = part(_box(-150, 250, -80, 300, 120, 640), "COLUMN", blue)
    saddle = part(_box(-200, -150, 0, 400, 300, 30), "SADDLE", grey)
    table = part(_box(-220, -120, 30, 440, 240, 30), "TABLE", grey)
    stock = part(_box(-80, -60, 60, 160, 120, 30), "STOCK 160x120x30", (0.75, 0.76, 0.78))
    head = part(_box(-70, 40, 320, 140, 210, 200), "HEAD", blue)
    spindle = part(_cyl(0, 0, GAUGE_Z, 45.0, 180.0), "SPINDLE", grey)
    t1 = part(bt30_tool(T1_STICK, 5.0), "TOOL T1 BT30 FLAT D10", steel)
    hx, hy = HUB
    housing = part(_fuse(_box(hx - 40, hy - 40, GAUGE_Z + 45, 80, 290, 60)), "ATC HOUSING", blue)
    mx, my = MAG
    post = part(_fuse(_cyl(mx, my, 350, 25.0, 170.0), _box(mx - 20, my, 480, 40, 250, 40),
                      _box(mx - 20, 230, 380, 40, 20, 140)), "MAGAZINE POST", blue)
    arm = part(changer_arm(), "CHANGER ARM", dark)
    disc = part(_cyl(mx, my, 330, DISC_R, 20.0), "MAGAZINE DISC", grey)
    pot_lab = part(pot(), "POT", dark)
    t2 = part(bt30_tool(T2_STICK, 4.0, ball=True), "TOOL T2 BT30 BALL D8", steel)

    x_asm = asm("X.ASM")
    place(x_asm, table)
    place(x_asm, stock)
    y_asm = asm("Y.ASM")
    place(y_asm, saddle)
    place(y_asm, x_asm)
    z_asm = asm("Z.ASM")
    place(z_asm, head)
    place(z_asm, spindle)
    place(z_asm, t1, z=GAUGE_Z - T1_STICK - BT30_GAUGE)
    arm_asm = asm("ARM.ASM")
    place(arm_asm, arm)
    mag = asm("MAGAZINE.ASM")
    place(mag, disc)
    for k in range(POTS):
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(mx, my, 0), gp_Dir(0, 0, 1)), 2 * math.pi * k / POTS)
        place(mag, pot_lab, t)
    # T2 in pot 2: lying radially, tip outwards, its gauge line at the pot's mouth
    a2 = 2 * math.pi / POTS
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), -math.pi / 2)       # +Z (into the holder) -> -X
    tz = gp_Trsf()
    tz.SetTranslation(gp_Vec(mx + POT_R + T2_STICK + BT30_GAUGE, my, POT_Z))
    tr = gp_Trsf()
    tr.SetRotation(gp_Ax1(gp_Pnt(mx, my, 0), gp_Dir(0, 0, 1)), a2)
    place(mag, t2, tr.Multiplied(tz.Multiplied(t)))
    root = asm("TEST.ATC")
    place(root, bed)
    place(root, column)
    place(root, y_asm)
    place(root, z_asm)
    place(root, housing)
    place(root, post)
    place(root, arm_asm)
    place(root, mag)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_atc.step")
    print("written")
