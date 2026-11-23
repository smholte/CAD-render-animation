"""Write a luffing arm with hydraulic cylinders as a STEP assembly (task 0013; generic, no owner data).

Task 0261 (study 0258): real size. The LAYOUT is three times the first model's (places, lengths, travels: the arm
4.5 m from its pivot, the pivot 1.8 m up); the parts that have a real size are drawn at it, not x 3: pins Ø60, the
cylinders' bore Ø125 / rod Ø70 (an ISO 6020/6022 size), M24 anchor bolts, fittings and screws. The structure (base,
post, brackets, arm) is built at the first model's numbers, scaled x 3 (``K``) and then given real-size bores.

TEST.LUFFER                      mm; every pin turns about Y
  BASE                           plate 3600 x 1200 x 300, corners and top edges chamfered, four anchor-bolt holes Ø26
  ISO 4017 M24 x 120 - 8.8 HDG   x4, hex head anchor bolts in the base's holes (task 0122; real size since 0261)
  POST                           a foot flange, a block with chamfered corners and gussets up to 90 mm under the arm,
                                 and a fork (two cheeks with round tops and bosses, bore Ø60.4) the arm turns in, the
                                 pivot at (300, *, 1800)
  BASE.BRACKET                   a plate with five lugs (round tops) that carry the barrel pins (1500, *, 450), bore
                                 Ø60; a slot for each cylinder between the lugs (task 0072: no part starts inside
                                 another, so the clash check never sits on its threshold)
  BASE.PIN                       Ø60 along Y through the barrel pins (pick target)
  ARM.ASM                        turns about the pivot
    ARM                          box girder 4500 x 300 x 300 from the pivot: chamfered, round end round the pin, side
                                 ribs, the tip tapered underneath with a clevis for a hook
    ARM.PIN                      Ø60 along Y at the pivot (pick target for the arm joint)
    ARM.BRACKET                  under the arm: a plate with gussets and lugs (round bottoms) that carry the rod pins
                                 (2400, *, 1350), bore Ø60; a slot per cylinder
    ARM.ROD.PIN                  Ø60 along Y through the rod pins (pick target)
  CYL.ASM  (twice: y = 240 and y = 960, side by side)
    CYL.BARREL                   BARREL.CAP (end cap + eye, cap screws), BARREL.TUBE (Ø150/125, two oil ports and the
                                 pipe from the rod-side port back to a block at the cap end), BARREL.GLAND (bore Ø72,
                                 flange with cap screws)
    CYL.ROD                      PISTON (Ø123), ROD (Ø70), ROD.EYE (with a threaded neck)
  TELE.ASM (y = 600, telescopic: barrel with one oil port, one stage, rod Ø80)
    TELE.BARREL, TELE.STAGE, TELE.ROD

The cylinders lie at 45°: barrel pin (1500, 450), rod pin (2400, 1350), pin to pin 1272.79 mm. Their rod can
go 180 mm in (piston back face 300 mm from the barrel pin, end cap inside at 120) and 390 mm out (piston
front 390, gland at 780): closed length 1092.79 mm, full stroke 570 mm. Everything the stroke is read from
(the cap's inside face, the bore, the piston, the gland's inside face) lies inside radius 62.5 (the ports, screws and
the pipe lie outside it). The pins are the plain cylinders of task 0013 (their round face is the first axis).

Revision B: a new ARM.LAMP in ARM.ASM and the two CYL.ASM placed in the other order.

usage: python make_test_cylinder.py out.step [A|B]
"""

import math
import os
import sys

import numpy as np

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fresing_render.demo_model import geom as g  # noqa: E402
from model_details import chamfer, chamfered_rect, hex_bolt, hex_prism  # noqa: E402

K = 3.0                         # the layout's scale against the first model (task 0261)
PIVOT = (300.0, 1800.0)         # (x, z) of the arm pivot
BARREL_PIN = (1500.0, 450.0)
ROD_PIN = (2400.0, 1350.0)
LENGTH = math.hypot(ROD_PIN[0] - BARREL_PIN[0], ROD_PIN[1] - BARREL_PIN[1])     # 1272.79
CYL_Y = (240.0, 960.0)
TELE_Y = 600.0
ANCHORS = [(180.0, 150.0), (180.0, 1050.0), (3420.0, 150.0), (3420.0, 1050.0)]
PIN_R = 30.0                    # every pin Ø60; the post's and the arm's pivot bores Ø60.4
BORE_R, TUBE_R = 62.5, 75.0     # cylinder bore Ø125, barrel Ø150
ROD_R, PISTON_R = 35.0, 61.5    # rod Ø70, piston Ø123
EYE_R, EYE_W = 50.0, 90.0       # the eyes round the pins: Ø100, 90 wide
ANCHOR = (24, 120.0)            # M24 x 120


# ---------------------------------------------------------------------------
# small shape helpers (mm)
# ---------------------------------------------------------------------------

def _big(shape):
    """The first model's shape, K times as big (about the origin)."""
    return g.xform(shape, np.diag([K, K, K, 1.0]))


def _along_x(x0, x1, r):
    return g.cyl(r, x1 - x0, (x0, 0, 0), (1, 0, 0))


def _hollow_x(x0, x1, r_in, r_out):
    return g.cut(_along_x(x0, x1, r_out), _along_x(x0 - 1, x1 + 1, r_in))


def _along_y(x, z, y0, y1, r):
    return g.cyl(r, y1 - y0, (x, y0, z), (0, 1, 0))


def _xz_prism(points, y0, y1):
    """A profile of (x, z) points extruded along Y from y0 to y1."""
    return g.polygon_prism(points, y1 - y0, g.Frame((0, y1, 0), (1, 0, 0), (0, -1, 0)))


def _yz_prism(points, x0, x1):
    """A profile of (y, z) points extruded along X from x0 to x1."""
    return g.polygon_prism(points, x1 - x0, g.Frame((x0, 0, 0), (0, 1, 0), (1, 0, 0)))


def _eye(x, r_out, r_in, width):
    """A ring around a pin along Y at (x, 0, 0)."""
    return g.cut(_along_y(x, 0, -width / 2, width / 2, r_out), _along_y(x, 0, -width, width, r_in))


def _lug(cx, cz, r, y0, y1, down: bool, depth: float):
    """A plate along Y (y0 .. y1): a half disc of radius r round (cx, cz) and a block ``depth`` towards its base."""
    if down:                                         # base above the pin (the arm's bracket)
        block = g.box(cx - r, y0, cz, 2 * r, y1 - y0, depth)
    else:                                            # base below the pin (the base's bracket)
        block = g.box(cx - r, y0, cz - depth, 2 * r, y1 - y0, depth)
    return g.fuse(block, _along_y(cx, cz, y0, y1, r))


# ---------------------------------------------------------------------------
# the fixed parts (world coordinates)
# ---------------------------------------------------------------------------

def base_shape():
    plate = g.polygon_prism(chamfered_rect(0, 0, 1200, 400, 25), 100.0)
    plate = _big(chamfer(plate, 8.0, lambda p: abs(p[2] - 100.0) < 1e-6))
    return g.cut(plate, *[g.cyl(ANCHOR[0] / 2 + 1.0, 302.0, (x, y, -1.0)) for x, y in ANCHORS])


def post_shape():
    px, pz = PIVOT[0] / K, PIVOT[1] / K                              # built at the first model's size, then x K
    foot = g.polygon_prism(chamfered_rect(px - 85, 90, 170, 220, 14), 18.0, g.T(0, 0, 100))
    foot = chamfer(foot, 3.0, lambda p: abs(p[2] - 118.0) < 1e-6)
    block = g.polygon_prism(chamfered_rect(px - 60, 115, 120, 170, 12), pz - 50 - 30 - 118, g.T(0, 0, 118))
    parts = [foot, block]
    for y0 in (115.0, 255.0):                                        # the cheeks: round tops round the pin
        parts.append(g.box(px - 40, y0, pz - 120, 80, 30, 120))
        parts.append(_along_y(px, pz, y0, y0 + 30, 40.0))
    parts.append(_along_y(px, pz, 111.0, 115.0, 30.0))              # bosses round the bore
    parts.append(_along_y(px, pz, 285.0, 289.0, 30.0))
    # gussets between the foot and the block: triangles 25 out and 110 up, 12 thick
    tri_x = [(0.0, 0.0), (25.0, 0.0), (0.0, 110.0)]
    for sgn, x in ((-1.0, px - 60), (1.0, px + 60)):                 # on the -x and +x faces, in the middle
        pts = [(x + sgn * u, 118.0 + v) for u, v in tri_x]
        parts.append(_xz_prism(pts, 194.0, 206.0))
    for sgn, y in ((-1.0, 115.0), (1.0, 285.0)):                     # on the -y and +y faces, two each
        for xc in (px - 35, px + 35):
            pts = [(y + sgn * u, 118.0 + v) for u, v in [(0.0, 0.0), (22.0, 0.0), (0.0, 90.0)]]
            parts.append(g.xform(g.polygon_prism(pts, 12.0), g.Frame((xc - 6, 0, 0), (0, 1, 0), (1, 0, 0))))
    shape = _big(g.fuse(*parts))
    return g.cut(shape, _along_y(PIVOT[0], PIVOT[1], 300.0, 900.0, PIN_R + 0.2))


def base_bracket_shape():
    bx, bz = BARREL_PIN[0] / K, BARREL_PIN[1] / K
    plate = g.polygon_prism(chamfered_rect(bx - 40, 10, 80, 380, 6), 15.0, g.T(0, 0, 100))
    plate = chamfer(plate, 2.0, lambda p: abs(p[2] - 115.0) < 1e-6)
    lugs = [(10.0, 25.0), (135.0, 145.0), (255.0, 265.0), (375.0, 390.0)]
    parts = [plate] + [_lug(bx, bz, 40.0, y0, y1, False, bz - 115.0 + 0.0) for y0, y1 in lugs]
    parts.append(_along_y(bx, bz, 4.0, 10.0, 28.0))                 # bosses on the outer lugs
    parts.append(_along_y(bx, bz, 390.0, 396.0, 28.0))
    shape = _big(g.fuse(*parts))
    return g.cut(shape, _along_y(BARREL_PIN[0], BARREL_PIN[1], -30.0, 1230.0, PIN_R))


# ---------------------------------------------------------------------------
# the arm (its own coordinates: the pivot at the origin, along +x)
# ---------------------------------------------------------------------------

def arm_shape():
    section = chamfered_rect(-50, -50, 100, 100, 8)                  # (y, z)
    girder = _yz_prism(section, 0.0, 1500.0)
    parts = [girder, _along_y(0, 0, -50, 50, 50.0)]
    for x in (300.0, 500.0, 950.0, 1200.0):                          # side ribs, 10 short of top and bottom
        for y0 in (-56.0, 50.0):
            parts.append(g.box(x - 4, y0, -40, 8, 6, 80))
    shape = g.fuse(*parts)
    # the tip tapers underneath: from z -50 at x 1250 to z -25 at the end
    taper = _xz_prism([(1250.0, -50.0), (1510.0, -25.0), (1510.0, -60.0), (1250.0, -60.0)], -70.0, 70.0)
    shape = g.cut(shape, taper)
    clevis = []
    for y0 in (-42.0, 30.0):                                         # a clevis at the tip for a hook
        clevis.append(g.box(1490, y0, -25, 50, 12, 50))
        clevis.append(_along_y(1540, 0, y0, y0 + 12, 25.0))
    shape = _big(g.cut(g.fuse(shape, *clevis), _along_y(1540, 0, -50, 50, 10.0)))
    return g.cut(shape, _along_y(0, 0, -180, 180, PIN_R + 0.2))


def arm_bracket_shape(ax, az):
    """Under the arm round the rod pins at (ax, *, az) (arm coordinates; the arm's underside at z = -150)."""
    pin_x, pin_z = ax, az
    ax, az = ax / K, az / K                                          # built at the first model's size, then x K
    plate = _yz_prism(chamfered_rect(-190, az + 60, 380, -50 - (az + 60), 6), ax - 40, ax + 40)
    lugs = [(-190.0, -175.0), (-65.0, -55.0), (55.0, 65.0), (175.0, 190.0)]
    parts = [plate] + [_lug(ax, az, 40.0, y0, y1, True, 60.0) for y0, y1 in lugs]
    parts.append(_along_y(ax, az, -196.0, -190.0, 28.0))            # bosses on the outer lugs
    parts.append(_along_y(ax, az, 190.0, 196.0, 28.0))
    for sgn in (-1.0, 1.0):                                         # gussets up the arm's sides
        y = sgn * 50.0
        pts = [(y, -50.0), (y + sgn * 100.0, -50.0), (y, 10.0)]
        parts.append(g.xform(g.polygon_prism(pts, 10.0), g.Frame((ax - 5, 0, 0), (0, 1, 0), (1, 0, 0))))
    shape = _big(g.fuse(*parts))
    return g.cut(shape, _along_y(pin_x, pin_z, -630.0, 630.0, PIN_R))


# ---------------------------------------------------------------------------
# a cylinder, built along X from its barrel pin (x = 0) to its rod pin (x = L); "up" (+z) is away from the base
# ---------------------------------------------------------------------------

def _hex_x(af, h, x0, radius, deg):
    """A hex head (``af`` across flats) on x0 .. x0 + h at ``radius`` and angle ``deg`` round the X axis."""
    a = math.radians(deg)
    return g.xform(hex_prism(af, h), g.Frame((x0, radius * math.cos(a), radius * math.sin(a)), (0, 1, 0), (1, 0, 0)))


def _port(x, top=88.0, fitting=100.0, length=40.0, width=40.0):
    """An oil port on the barrel's top: a welded block and a fitting (from radius 70: the bore stays clear)."""
    return g.fuse(g.box(x - length / 2, -width / 2, 70.0, length, width, top - 70.0),
                  g.cyl(9.0, fitting - top, (x, 0, top)), g.cyl(11.0, 5.0, (x, 0, top)))


def cap_shape():
    disc = _along_x(45, 120, TUBE_R)
    heads = [_hex_x(18.0, 10.0, 35.0, 62.0, a) for a in (45.0, 135.0, 225.0, 315.0)]
    return g.fuse(_eye(0, EYE_R, PIN_R, EYE_W), disc, *heads)


def tube_shape(x1=780.0, ports=(195.0, 714.0), pipe=True):
    shape = [_hollow_x(120, x1, BORE_R, TUBE_R), _hollow_x(120, 144, 70, 79)]   # a weld collar at the cap end
    if pipe:                                                        # the cap-end port's block is a manifold
        shape.append(g.box(165, -20, 70, 150, 40, 18))
        shape.append(g.cyl(9.0, 14.0, (276, 0, 88)))
    for x in ports:
        shape.append(_port(x))
    if pipe:                                                        # the pipe from the rod-side port to the block
        shape.append(g.rod((276, 0, 95), (714, 0, 95), 8.0))
    return g.fuse(*shape)


def gland_shape():
    flange = _hollow_x(780, 810, ROD_R + 1, TUBE_R)
    nose = _hollow_x(810, 870, ROD_R + 1, 62.0)
    heads = [_hex_x(10.0, 8.0, 810.0, 68.0, a) for a in range(30, 360, 60)]
    shape = g.fuse(flange, nose, *heads)
    return g.cut(shape, _along_x(858, 871, ROD_R + 5))               # the wiper's seat at the front


def rod_eye_shape(L):
    return g.fuse(_eye(L, EYE_R, PIN_R, EYE_W), g.cut(_along_x(L - 110, L - 45, 45), _along_x(L - 120, L - 44,
                                                                                               ROD_R + 0.5)))


def tele_barrel_shape():
    return g.fuse(_eye(0, EYE_R, PIN_R, EYE_W), _along_x(45, 120, TUBE_R), _along_x(54, 66, 52),
                  _hollow_x(120, 600, BORE_R, TUBE_R), _hollow_x(570, 600, BORE_R, 78), _port(195.0))


def tele_stage_shape():
    return g.fuse(_hollow_x(450, 900, 45, 58), _hollow_x(450, 495, 45, 60), _hollow_x(864, 900, 45, 62))


def tele_rod_shape(L):
    return g.fuse(_along_x(660, L - 45, 40), _eye(L, EYE_R, PIN_R, EYE_W))


# ---------------------------------------------------------------------------
# the assembly
# ---------------------------------------------------------------------------

def build(path: str, revision: str = "A") -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb=None):
        if g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
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

    base = part(base_shape(), "BASE", yellow)
    anchor = part(hex_bolt(*ANCHOR), f"ISO 4017 M{ANCHOR[0]} x {ANCHOR[1]:.0f} - 8.8 HDG", (0.12, 0.12, 0.13))
    post = part(post_shape(), "POST", yellow)
    base_bracket = part(base_bracket_shape(), "BASE.BRACKET", yellow)
    # the pins: plain cylinders (their round face is the part's first axis, the pick target)
    base_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(bx, -60, bz), gp_Dir(0, 1, 0)), PIN_R, 1320.0).Shape(),
                    "BASE.PIN", chrome)

    # the arm, built at the pivot
    arm = part(arm_shape(), "ARM", yellow)
    arm_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -270, 0), gp_Dir(0, 1, 0)), PIN_R, 540.0).Shape(),
                   "ARM.PIN", chrome)
    ax, az = rx - px, rz - pz                                      # rod pin relative to the pivot
    arm_bracket = part(arm_bracket_shape(ax, az), "ARM.BRACKET", yellow)
    arm_rod_pin = part(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(ax, -660, az), gp_Dir(0, 1, 0)), PIN_R,
                                                1320.0).Shape(), "ARM.ROD.PIN", chrome)
    lamp = part(BRepPrimAPI_MakeSphere(90.0).Shape(), "ARM.LAMP") if revision == "B" else None

    # a cylinder, built along X from its barrel pin (x = 0) to its rod pin (x = L)
    cap = part(cap_shape(), "BARREL.CAP", grey)
    tube = part(tube_shape(), "BARREL.TUBE", grey)
    gland = part(gland_shape(), "BARREL.GLAND", grey)
    piston = part(_along_x(300, 390, PISTON_R), "PISTON", steel)
    rod = part(_along_x(390, L - 60, ROD_R), "ROD", chrome)
    rod_eye = part(rod_eye_shape(L), "ROD.EYE", steel)

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
    t_barrel = part(tele_barrel_shape(), "TELE.BARREL", grey)
    t_stage = part(tele_stage_shape(), "TELE.STAGE", steel)
    t_rod = part(tele_rod_shape(L), "TELE.ROD", chrome)
    tele = assy("TELE.ASM")
    for lab in (t_barrel, t_stage, t_rod):
        place(tele, lab)

    arm_asm = assy("ARM.ASM")
    place(arm_asm, arm)
    place(arm_asm, arm_pin)
    place(arm_asm, arm_bracket)
    place(arm_asm, arm_rod_pin)
    if lamp is not None:
        place(arm_asm, lamp, 4350, 0, 240)

    root = assy("TEST.LUFFER")
    place(root, base)
    for x, y in ANCHORS:
        place(root, anchor, x, y, 300.0)
    place(root, post)
    place(root, base_bracket)
    place(root, base_pin)
    place(root, arm_asm, px, TELE_Y, pz)
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
