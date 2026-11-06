"""Write three small mechanisms as one STEP assembly (task 0014; generic, no owner data).

mm; every pin turns about Y, so the mechanisms move in the XZ plane. They stand apart along X so no pin of one
lines up with a pin of another.

TEST.LINKAGES
  LIFT.ASM                         scissor lift, 3 stages, arms 1000 mm pin to pin, 15° in the CAD pose
    LIFT.BASE.ASM                  LIFT.BASE (plate), LIFT.BASE.BRACKET (bore Ø30 at the fixed pin), LIFT.BASE.PIN
    LIFT.ARM.IN.1 … 3              inner arms, from (0, z) up to (c, z + s); a centre pin; stage 3 has the
                                   roller under the platform at its top end
    LIFT.ARM.OUT.1 … 3             outer arms, from (c, z) up to (0, z + s); stage 1 has the roller on the
                                   base at its bottom end; stages 2 and 3 carry the pin at their bottom end
    LIFT.PLATFORM.ASM              LIFT.PLATFORM, LIFT.PLATFORM.BRACKET (bore at the platform pin), its pin
    LIFT.CYL.ASM                   lifting cylinder: LIFT.CYL.BARREL pinned to the base at G (450, 100),
                                   LIFT.CYL.ROD pinned to the bottom inner arm's lug at 3/4 of its length
  FOURBAR.ASM                      four-bar (crank-rocker) at x = 2000: ground pins A (2000, 300), D (2400, 300);
    FOURBAR.BASE.ASM               crank 120, coupler 350, rocker 250; the crank at 60° in the CAD pose
    FOURBAR.CRANK, FOURBAR.COUPLER (with a tool block), FOURBAR.ROCKER
  CRANK.ASM                        slider-crank at x = 3200: crank pivot O (3200, 300), crank 100 at 30°,
    CRANK.BASE.ASM                 rod 300, piston pin 20 mm above O's line (offset), guide tube along X
    CRANK.CRANK, CRANK.ROD, CRANK.PISTON

Hand calculation (mm): scissor c = 1000 cos 15° = 965.926, s = 1000 sin 15° = 258.819; fixed pin (0, 100);
platform pin (0, 100 + 3 s) = (0, 876.457), height pin to pin 3 * 1000 * sin(phi). Slider-crank: piston pin
x = 100 cos t + sqrt(300^2 - (100 sin t - 20)^2) from O.

Revision B: a LIFT.PLATFORM.LAMP on the platform, and the four-bar's tool block is longer.

usage: python make_test_linkage.py out.step [A|B]
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

# scissor lift
ARM = 1000.0
PHI0 = math.radians(15.0)
STAGES = 3
C = ARM * math.cos(PHI0)
S = ARM * math.sin(PHI0)
Z0 = 100.0                      # fixed pin height above the base's underside
TOP = Z0 + STAGES * S           # platform pin
PIN_R = 15.0
ROLLER_R = 40.0
CYL_G = (450.0, Z0)              # the lifting cylinder's barrel pin on the base
CYL_AT = 0.75                    # the rod pin on the bottom inner arm, share of its length
# four-bar
FB_X, FB_Z = 2000.0, 300.0
FB_A, FB_B, FB_C, FB_D = 120.0, 350.0, 250.0, 400.0
FB_TH = math.radians(60.0)
# slider-crank
SC_X, SC_Z = 3200.0, 300.0
SC_R, SC_L, SC_E = 100.0, 300.0, 20.0
SC_TH = math.radians(30.0)


def four_bar_points():
    """(A, B, C, D) in mm, (x, z): the open assembly mode (rocker pin above the ground line)."""
    ax, az = FB_X, FB_Z
    dx, dz = FB_X + FB_D, FB_Z
    bx, bz = ax + FB_A * math.cos(FB_TH), az + FB_A * math.sin(FB_TH)
    wx, wz = dx - bx, dz - bz
    d = math.hypot(wx, wz)
    a = (FB_B ** 2 - FB_C ** 2 + d * d) / (2 * d)
    h = math.sqrt(FB_B ** 2 - a * a)
    ux, uz = wx / d, wz / d
    mx, mz = bx + ux * a, bz + uz * a
    cands = [(mx - uz * h, mz + ux * h), (mx + uz * h, mz - ux * h)]
    cx, cz = max(cands, key=lambda p: p[1])
    return (ax, az), (bx, bz), (cx, cz), (dx, dz)


def slider_points():
    ox, oz = SC_X, SC_Z
    bx, bz = ox + SC_R * math.cos(SC_TH), oz + SC_R * math.sin(SC_TH)
    px = bx + math.sqrt(SC_L ** 2 - (bz - (oz + SC_E)) ** 2)
    return (ox, oz), (bx, bz), (px, oz + SC_E)


def _cyl_y(x, z, r, y0, y1):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y0, z), gp_Dir(0, 1, 0)), r, y1 - y0).Shape()


def _cyl_x(x0, x1, y, z, r):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, y, z), gp_Dir(1, 0, 0)), r, x1 - x0).Shape()


def _bar(length, width, y0, y1, holes, hole_r):
    """A bar along X from 0 to ``length`` (rounded ends), width in Z, holes along Y at ``holes`` (x)."""
    body = BRepPrimAPI_MakeBox(gp_Pnt(0, y0, -width / 2), length, y1 - y0, width).Shape()
    body = BRepAlgoAPI_Fuse(body, _cyl_y(0, 0, width / 2, y0, y1)).Shape()
    body = BRepAlgoAPI_Fuse(body, _cyl_y(length, 0, width / 2, y0, y1)).Shape()
    for x in holes:
        body = BRepAlgoAPI_Cut(body, _cyl_y(x, 0, hole_r, y0 - 1, y1 + 1)).Shape()
    return body


def _lug(x):
    """A lug under the inner arm (in front of it, y -100 … 0) with a bore Ø20 at x along the arm."""
    body = BRepPrimAPI_MakeBox(gp_Pnt(x - 30, -100, -30), 60.0, 100.0, 60.0).Shape()
    return BRepAlgoAPI_Cut(body, _cyl_y(x, 0, 10.0, -101, 1)).Shape()


def _tube_x(x0, x1, r_in, r_out, y):
    return BRepAlgoAPI_Cut(_cyl_x(x0, x1, y, 0, r_out), _cyl_x(x0 - 1, x1 + 1, y, 0, r_in)).Shape()


def _eye_y(x, r_out, r_in, y0, y1):
    return BRepAlgoAPI_Cut(_cyl_y(x, 0, r_out, y0, y1), _cyl_y(x, 0, r_in, y0 - 1, y1 + 1)).Shape()


def _bored_block(x0, x1, y0, y1, z0, z1, bores, r):
    body = BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), x1 - x0, y1 - y0, z1 - z0).Shape()
    for x, z in bores:
        body = BRepAlgoAPI_Cut(body, _cyl_y(x, z, r, y0 - 1, y1 + 1)).Shape()
    return body


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

    def place(parent, lab, x=0.0, z=0.0, turn=0.0, y=0.0):
        """Turn the local +X to ``turn`` degrees (counter-clockwise from +X towards +Z), then move."""
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        if turn:
            r = gp_Trsf()
            r.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), -math.radians(turn))
            t = t.Multiplied(r)
        st.AddComponent(parent, lab, TopLoc_Location(t))

    yellow, grey, steel, chrome, blue = ((0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.55, 0.57, 0.6),
                                         (0.85, 0.86, 0.88), (0.1, 0.3, 0.7))
    root = assy("TEST.LINKAGES")

    # ---- scissor lift ---------------------------------------------------------------------------
    lift = assy("LIFT.ASM")
    turn = math.degrees(PHI0)
    base = assy("LIFT.BASE.ASM")
    place(base, part(BRepPrimAPI_MakeBox(gp_Pnt(-150, -60, 0), 1300.0, 180.0, Z0 - ROLLER_R).Shape(),
                     "LIFT.BASE", grey))
    place(base, part(_bored_block(-40, 40, -40, 0, Z0 - ROLLER_R, Z0 + 40, [(0, Z0)], PIN_R),
                     "LIFT.BASE.BRACKET", grey))
    place(base, part(_cyl_y(0, Z0, PIN_R, -40, 30), "LIFT.BASE.PIN", chrome))
    place(lift, base)

    inner_bar = part(_bar(ARM, 60, 0, 30, [0, ARM / 2, ARM], PIN_R), "LIFT.ARM.IN", yellow)
    outer_bar = part(_bar(ARM, 60, 30, 60, [0, ARM / 2, ARM], PIN_R), "LIFT.ARM.OUT", yellow)
    centre_pin = part(_cyl_y(ARM / 2, 0, PIN_R, -5, 65), "LIFT.PIN", chrome)
    end_pin = part(_cyl_y(0, 0, PIN_R, -5, 65), "LIFT.PIN.END", chrome)
    roller_shape = BRepAlgoAPI_Cut(_cyl_y(0, 0, ROLLER_R, 0, 30), _cyl_y(0, 0, PIN_R, -1, 31)).Shape()
    for i in range(STAGES):
        z = Z0 + i * S
        a = assy(f"LIFT.ARM.IN.{i + 1}")
        place(a, inner_bar)
        place(a, centre_pin)
        if i == 0:                               # the lifting cylinder's lug and pin
            place(a, part(_lug(ARM * CYL_AT), "LIFT.ARM.LUG", yellow))
            place(a, part(_cyl_y(ARM * CYL_AT, 0, 10.0, -110, 30), "LIFT.CYL.PIN", chrome))
        if i == STAGES - 1:                      # roller under the platform, at the inner arm's top end
            place(a, part(roller_shape, "LIFT.ROLLER", grey), ARM, 0, 0, y=-30)
        place(lift, a, 0, z, turn)
        b = assy(f"LIFT.ARM.OUT.{i + 1}")
        place(b, outer_bar)
        if i == 0:                               # roller on the base, at the outer arm's bottom end
            place(b, part(roller_shape, "LIFT.ROLLER", grey), 0, 0, 0, y=60)
        else:                                    # its bottom end is pinned to the inner arm below
            place(b, end_pin)
        place(lift, b, C, z, 180.0 - turn)
        if i > 0:                                # the inner arm's bottom end on the outer arm below
            p = assy(f"LIFT.PIN.{i + 1}")
            place(p, end_pin)
            place(a, p)
    plat = assy("LIFT.PLATFORM.ASM")
    place(plat, part(BRepPrimAPI_MakeBox(gp_Pnt(-150, -60, TOP + ROLLER_R), 1300.0, 180.0, 40.0).Shape(),
                     "LIFT.PLATFORM", blue))
    place(plat, part(_bored_block(-40, 40, 60, 100, TOP - 40, TOP + ROLLER_R, [(0, TOP)], PIN_R),
                     "LIFT.PLATFORM.BRACKET", blue))
    place(plat, part(_cyl_y(0, TOP, PIN_R, 30, 100), "LIFT.PLATFORM.PIN", chrome))
    if revision == "B":
        place(plat, part(BRepPrimAPI_MakeSphere(gp_Pnt(500, 30, TOP + 120), 40.0).Shape(), "LIFT.PLATFORM.LAMP"))
    place(lift, plat)
    # the lifting cylinder: barrel pinned to the base at G, rod to the bottom inner arm's lug
    gx, gz = CYL_G
    rx, rz = (ARM * CYL_AT * math.cos(PHI0), Z0 + ARM * CYL_AT * math.sin(PHI0))
    length = math.hypot(rx - gx, rz - gz)
    place(base, part(_bored_block(gx - 30, gx + 30, -100, -60, Z0 - ROLLER_R, Z0 + 30, [(gx, gz)], 10.0),
                     "LIFT.BASE.CYL.BRACKET", grey))
    place(base, part(_cyl_y(gx, gz, 10.0, -110, -50), "LIFT.BASE.CYL.PIN", chrome))
    barrel = assy("LIFT.CYL.BARREL")
    place(barrel, part(BRepAlgoAPI_Fuse(_tube_x(25, 200, 20, 25, -80), _eye_y(0, 18, 10, -95, -65)).Shape(),
                       "LIFT.CYL.TUBE", grey))
    rod = assy("LIFT.CYL.ROD")
    place(rod, part(BRepAlgoAPI_Fuse(_cyl_x(120, length - 15, -80, 0, 8), _eye_y(length, 15, 10, -95, -65)).Shape(),
                    "LIFT.CYL.RODEND", chrome))
    place(rod, part(_cyl_x(100, 120, -80, 0, 19.5), "LIFT.CYL.PISTON", steel))
    cyl = assy("LIFT.CYL.ASM")
    place(cyl, barrel)
    place(cyl, rod)
    place(lift, cyl, gx, gz, math.degrees(math.atan2(rz - gz, rx - gx)))
    place(root, lift)

    # ---- four-bar -------------------------------------------------------------------------------
    pa, pb, pc, pd = four_bar_points()
    fb = assy("FOURBAR.ASM")
    fbase = assy("FOURBAR.BASE.ASM")
    place(fbase, part(BRepPrimAPI_MakeBox(gp_Pnt(FB_X - 100, -40, 0), FB_D + 200, 120.0, 60.0).Shape(),
                      "FOURBAR.BASE", grey))
    place(fbase, part(_bored_block(FB_X - 30, FB_X + 30, -40, -10, 60, FB_Z + 30, [(FB_X, FB_Z)], 10.0),
                      "FOURBAR.POST.A", grey))
    place(fbase, part(_bored_block(FB_X + FB_D - 30, FB_X + FB_D + 30, 50, 80, 60, FB_Z + 30,
                                   [(FB_X + FB_D, FB_Z)], 10.0), "FOURBAR.POST.D", grey))
    place(fb, fbase)

    def link(text, p, q, y0, y1, colour, extra=None):
        ln = math.hypot(q[0] - p[0], q[1] - p[1])
        a = assy(text + ".ASM")
        place(a, part(_bar(ln, 40, y0, y1, [0, ln], 10.0), text, colour))
        place(a, part(_cyl_y(ln, 0, 10.0, y0 - 10, y1 + 10), text + ".PIN", chrome))
        if extra is not None:
            place(a, extra)
        place(fb if text.startswith("FOURBAR") else sc, a, p[0], p[1], math.degrees(math.atan2(q[1] - p[1],
                                                                                               q[0] - p[0])))
        return a

    tool_len = 160.0 if revision == "A" else 220.0
    tool = part(BRepPrimAPI_MakeBox(gp_Pnt(FB_B / 2 - 40, 20, 20), 80.0, 20.0, tool_len).Shape(), "FOURBAR.TOOL",
                blue)
    link("FOURBAR.CRANK", pa, pb, -10, 10, yellow)
    link("FOURBAR.COUPLER", pb, pc, 10, 30, yellow, tool)
    link("FOURBAR.ROCKER", pd, pc, 30, 50, yellow)
    # the crank's own pin at A is in the base post; the rocker's at D too
    place(fbase, part(_cyl_y(FB_X, FB_Z, 10.0, -40, 10), "FOURBAR.PIN.A", chrome))
    place(fbase, part(_cyl_y(FB_X + FB_D, FB_Z, 10.0, 30, 80), "FOURBAR.PIN.D", chrome))
    place(root, fb)

    # ---- slider-crank ---------------------------------------------------------------------------
    po, pbb, pp = slider_points()
    sc = assy("CRANK.ASM")
    sbase = assy("CRANK.BASE.ASM")
    place(sbase, part(BRepPrimAPI_MakeBox(gp_Pnt(SC_X - 150, -40, 0), 800.0, 120.0, 60.0).Shape(),
                      "CRANK.BASE", grey))
    place(sbase, part(_bored_block(SC_X - 30, SC_X + 30, -40, -10, 60, SC_Z + 30, [(SC_X, SC_Z)], 10.0),
                      "CRANK.BEARING", grey))
    place(sbase, part(_cyl_y(SC_X, SC_Z, 10.0, -40, 10), "CRANK.PIN.O", chrome))
    guide = BRepAlgoAPI_Cut(_cyl_x(SC_X + 250, SC_X + 600, 40, SC_Z + SC_E, 34),
                            _cyl_x(SC_X + 249, SC_X + 601, 40, SC_Z + SC_E, 26)).Shape()
    place(sbase, part(guide, "CRANK.GUIDE", grey))
    place(sc, sbase)
    link("CRANK.CRANK", po, pbb, -10, 10, yellow)
    rod = link("CRANK.ROD", pbb, pp, 10, 30, steel)
    del rod
    piston = assy("CRANK.PISTON.ASM")
    body = BRepAlgoAPI_Cut(_cyl_x(pp[0] - 40, pp[0] + 40, 40, pp[1], 25), _cyl_y(pp[0], pp[1], 10.0, 10, 70)).Shape()
    place(piston, part(body, "CRANK.PISTON", blue))
    place(sc, piston)
    place(root, sc)

    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_linkage.step", sys.argv[2] if len(sys.argv) > 2 else "A")
    print("written")
