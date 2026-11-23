"""Write a small machine axis with a telescopic way cover as a STEP assembly (task 0034; generic, no owner data).

TEST.WAYCOVER                    mm; the covers lie along X, nested into each other (axis at 0 = closed). Task 0262: the
                                 layout x 2 of the first model (an X axis like the test VMC's, 1000 mm travel); rails,
                                 ball screw, motor, bolts, T-slots and the 3 mm sheet keep their real size
  BASE                           the machine bed 2000 x 600 x 120 (top edges chamfered) with two linear rails on top
                                 (y 160 … 180 and 400 … 420, 18 high) and the cover's end bracket at x = 0 … 40
  CARRIAGE                       200 x 400: a saddle on four guide blocks that wrap the rails, T-slots on top; its
                                 left face at x = 240 (the axis joint moves it)
  COVER.1.PLATE, COVER.1.FLANGE  section 1 (two parts) at x = 40: the plate, an inverted U of folded 3 mm sheet the
                                 rails run through, and the flange, the top sheet with its edges folded down and a wiper
                                 lip
  COVER.2                        section 2 (one part: plate and flange in one), x = 80
  COVER.3.PLATE, COVER.3.FLANGE  section 3 (two parts), x = 120
  COVER.4                        section 4, x = 160
  COVER.5                        section 5, x = 200 (the one at the carriage)

Five sections over a 1000 mm axis: each one slides 200 mm relative to its neighbour, so the sections stand
at x + 200, 400, 600, 800, 1000 mm when the axis is at 1000 mm. Every part of a section lies within its 40 mm along X.

``--sections N`` (task 0035): N sections instead of five (COVER.1 … COVER.N at x = 40, 80 …; sections 1 and 3 of two
parts as above). Five is the default and gives the committed test_waycover_b.step.

``--both-sides`` (task 0035): TEST.WAYCOVER.TWO, a cover each side of the carriage on one 1000 mm X axis
(test_waycover_c.step):
  BASE                           the bed (x -40 … end + 40) with the two rails
  FRAME.LEFT, FRAME.RIGHT        the end plates the covers are fixed to, x -80 … 0 and end … end + 80, each bolted to
                                 the bed's end face with four hex bolts (heads in one part with the plate)
  CARRIAGE                       400 x 400, x = 40 N … 40 N + 400 at axis 0 (left end of its travel)
  COVER.L.1 … COVER.L.N          left cover, nested at x = 0, 40 … (closed at axis 0); COVER.L.N touches the carriage
  COVER.R.1 … COVER.R.N          right cover, fixed end at the right (COVER.R.1), open at axis 0: section k stands at
                                 x = C + (N - k) 40 - 1000 k / N, C = the carriage's right face at axis 1000 mm
Both covers' section k moves k/N of the axis (1000 mm: 200, 400 … 1000 mm), the left one opening, the right one
closing; at 1000 mm the right cover is nested against FRAME.RIGHT's side of the carriage. The sections next to the
carriage (COVER.L.N, COVER.R.N) may be made the carriage section (bolted to it). Section k is 4 (k - 1) mm lower than
section 1 (they nest).

``--drawn-at MM`` (task 0090): the single-cover model drawn with the axis at MM (like a cover drawn at mid-travel):
the carriage stands MM further along and section k MM k / N further than in the closed drawing (test_waycover_d.step:
--drawn-at 500).

usage: python make_test_waycover.py out.step [--sections N] [--both-sides] [--drawn-at MM]
"""

import os
import sys

from OCP.gp import gp_Trsf, gp_Vec
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
from model_details import chamfer, chamfered_rect, hex_prism  # noqa: E402

# Task 0262: the layout x 2 (``S``) against the first model, matched to the test VMC's X travel of 1000 mm
# (tools/make_test_mill.py); the real parts keep their size: the rails (20 wide), the ball screw (Ø24), its bearing
# blocks, the motor, bolt heads, T-slots, guide blocks' height and the 3 mm sheet.
S = 2.0
T = 20.0 * S                    # a section's thickness along X (its pitch when closed)
RAILS = (80.0 * S, 200.0 * S)   # the rails' left sides (y), 20 wide (a real size-20 rail), on the bed's top
SHEET = 3.0                     # the covers' sheet metal
BED_TOP = 60.0 * S
WIDE = 300.0 * S                # the bed's width (y)
SCREW_R, SCREW_Y, SCREW_Z = 12.0, 150.0 * S, BED_TOP + 30.0   # the ball screw along X
SADDLE_TOP = 175.0 * S
TRAVEL = 500.0 * S              # the axis' travel (mm)


def _yz_prism(points, x0, x1):
    """A profile of (y, z) points extruded along X from x0 to x1."""
    return g.polygon_prism(points, x1 - x0, g.Frame((x0, 0, 0), (0, 1, 0), (1, 0, 0)))


def _hex_x(af, h, x0, y, z):
    """A hex head ``af`` across flats from x0 to x0 + h (h < 0: towards -x) at (y, z)."""
    return g.xform(hex_prism(af, abs(h)), g.Frame((x0, y, z), (0, 1, 0), (1 if h > 0 else -1, 0, 0)))


# ---------------------------------------------------------------------------
# the bed, the carriage, the end plates
# ---------------------------------------------------------------------------

def bed(x0, x1, rail_x0, rail_x1, screw_x0, screw_x1, supports=(1,)):
    """The bed x0 … x1 (its long top edges chamfered, cast pockets in its sides) with the two rails from rail_x0 to
    rail_x1 and the ball screw (Ø24 at y 150, z 90) from screw_x0 to screw_x1; ``supports``: bearing blocks at the
    screw's ends (0 = start, 1 = far end), inside the cover sections' opening."""
    c = 6.0
    plate = _yz_prism([(0, 0), (WIDE, 0), (WIDE, BED_TOP - c), (WIDE - c, BED_TOP), (c, BED_TOP), (0, BED_TOP - c)],
                      x0, x1)
    rails = [_yz_prism([(y, BED_TOP), (y + 20, BED_TOP), (y + 20, BED_TOP + 16.5), (y + 18.5, BED_TOP + 18),
                        (y + 1.5, BED_TOP + 18), (y, BED_TOP + 16.5)], rail_x0, rail_x1) for y in RAILS]
    extra = [g.cyl(SCREW_R, screw_x1 - screw_x0, (screw_x0, SCREW_Y, SCREW_Z), (1, 0, 0))]
    for end in supports:
        xs = screw_x1 - 30 if end else screw_x0
        blk = g.polygon_prism(chamfered_rect(xs, SCREW_Y - 28, 30, 56, 4), 52.0, g.T(0, 0, BED_TOP))
        extra.append(chamfer(blk, 2.0, lambda p: abs(p[2] - BED_TOP - 52) < 1e-6))
    pockets = [g.box(x, y, 12 * S, 70 * S, 8, 30 * S) for x in range(int(x0) + int(45 * S), int(x1 - 100 * S), int(100 * S))
               for y in (-1.0, WIDE - 7.0)]
    return g.cut(g.fuse(plate, *rails, *extra), *pockets)


def motor(x_face, out: int):
    """A servo motor on the screw's axis behind an end face at x_face (towards ``out`` along X): flange, body, cap."""
    my = SCREW_Y - 150.0                                           # built about y 150, moved onto the screw
    def along(x_a, length, shape_fn):
        x_lo = x_a if out > 0 else x_a - length
        return shape_fn(x_lo, length)
    flange = along(x_face, 12.0, lambda x, L: _yz_prism(chamfered_rect(my + 114, SCREW_Z - 36, 72, 72, 6), x, x + L))
    body = along(x_face + 12 * out, 110.0, lambda x, L: _yz_prism(chamfered_rect(my + 118, SCREW_Z - 32, 64, 64, 8), x,
                                                                  x + L))
    cap = along(x_face + 122 * out, 14.0, lambda x, L: _yz_prism(chamfered_rect(my + 123, SCREW_Z - 27, 54, 54, 10), x,
                                                                 x + L))
    plug = along(x_face + 40 * out, 26.0, lambda x, L: g.box(x, my + 138, SCREW_Z + 32, L, 24, 14))
    return g.fuse(flange, body, cap, plug)


def carriage(x0, length):
    """The saddle (z BED_TOP + 32 … SADDLE_TOP) on four guide blocks round the rails (z BED_TOP + 10 … + 32),
    x0 … x0 + length."""
    z_lo = BED_TOP + 32.0
    saddle = g.polygon_prism(chamfered_rect(x0, 50 * S, length, 200 * S, 8), SADDLE_TOP - z_lo, g.T(0, 0, z_lo))
    saddle = chamfer(saddle, 3.0, lambda p: abs(p[2] - SADDLE_TOP) < 1e-6)
    blocks = []
    a = 0.05 * length
    w = 0.4 * length
    for xb in (x0 + a, x0 + length - a - w):
        for y in RAILS:
            blk = g.cut(g.box(xb, y - 10, BED_TOP + 10, w, 40, 22), g.box(xb - 1, y - 1, BED_TOP + 9, w + 2, 22, 9.5))
            blocks.append(blk)
    heads = [g.xform(hex_prism(10.0, 6.0), g.T(x, y, SADDLE_TOP)) for x in (x0 + 0.2 * length, x0 + 0.8 * length)
             for y in (65.0 * S, 235.0 * S)]
    nut = g.box(x0 + 0.3 * length, SCREW_Y - 22, SCREW_Z - 18, 0.4 * length, 44, z_lo + 1 - (SCREW_Z - 18))   # the ball
    shape = g.cut(g.fuse(saddle, *blocks, *heads, nut),                                             # nut's housing
                  g.cyl(SCREW_R + 1, length + 2, (x0 - 1, SCREW_Y, SCREW_Z), (1, 0, 0)))
    slots = []
    for y in (100.0 * S, 150.0 * S, 200.0 * S):                      # T-slots along X
        slots.append(g.box(x0 - 1, y - 7, SADDLE_TOP - 9, length + 2, 14, 10))
        slots.append(g.box(x0 - 1, y - 11, SADDLE_TOP - 17, length + 2, 22, 8))
    return g.cut(shape, *slots)


def end_plate(x_in0, x_in1, x_out0, x_out1, out: int):
    """FRAME.LEFT / RIGHT: an end plate on the bed's end (x_in0 … x_in1, z BED_TOP … 220 S) and down its end face
    (x_out0 … x_out1, z 10 S … 220 S), four hex bolts into the bed's end and two higher up, their heads on the outer
    face (towards ``out`` = -1 or +1 along X)."""
    top = 220.0 * S
    shape = g.fuse(g.box(x_in0, 0, BED_TOP, x_in1 - x_in0, WIDE, top - BED_TOP),
                   g.box(x_out0, 0, 10 * S, x_out1 - x_out0, WIDE, top - 10 * S))
    shape = chamfer(shape, 4.0, lambda p: abs(p[2] - top) < 1e-6)
    x_face = x_out0 if out < 0 else x_out1
    heads = [_hex_x(16.0, 7.0 * out, x_face, y, z) for y in (50.0 * S, 250.0 * S) for z in (25.0 * S, 45.0 * S, 190.0 * S)]
    return g.fuse(shape, *heads)


# ---------------------------------------------------------------------------
# the cover sections: folded sheet, 20 mm along X
# ---------------------------------------------------------------------------

def _u(y0, y1, z0, z1, leg, z_open):
    return [(y0, z0), (y1, z0), (y1, z1), (y1 - leg, z1), (y1 - leg, z_open), (y0 + leg, z_open), (y0 + leg, z1),
            (y0, z1)]


def section_plate(x0, top, open_to=1):
    """An inverted U (legs 25 S wide, the rails run through below z 135 S) of 3 mm sheet with its edges folded T - 3
    along X, x0 … x0 + T, from the bed (z BED_TOP) up to ``top``; the folds face +x (``open_to`` 1) or -x (-1)."""
    y0, y1, z_open, leg = 20.0 * S, 280.0 * S, 135.0 * S, 25.0 * S
    outer = [(y0, BED_TOP), (y0, top), (y1, top), (y1, BED_TOP), (y1 - leg, BED_TOP), (y1 - leg, z_open),
             (y0 + leg, z_open), (y0 + leg, BED_TOP)]
    s = SHEET
    pocket = [(y0 + s, BED_TOP - 1), (y0 + s, top - s), (y1 - s, top - s), (y1 - s, BED_TOP - 1),
              (y1 - leg + s, BED_TOP - 1), (y1 - leg + s, z_open + s), (y0 + leg - s, z_open + s),
              (y0 + leg - s, BED_TOP - 1)]
    plate = _yz_prism(outer, x0, x0 + T)
    if open_to > 0:
        hole = _yz_prism(pocket, x0 + s, x0 + T + 1)
    else:
        hole = _yz_prism(pocket, x0 - 1, x0 + T - s)
    return g.cut(plate, hole)


def section_flange(x0, z0, open_to=1):
    """The top sheet on a plate whose top is at ``z0``: 3 mm, 4 S wider each side with its edges folded 12 S down,
    and a wiper lip (4 x 4) on the edge the next section slides under (the open side)."""
    y0, y1, fold = 16.0 * S, 284.0 * S, 12.0 * S
    sheet = g.box(x0, y0, z0, T, y1 - y0, SHEET)
    folds = [g.box(x0, y0, z0 - fold, T, SHEET, fold), g.box(x0, y1 - SHEET, z0 - fold, T, SHEET, fold)]
    xl = x0 + T - 4 if open_to > 0 else x0
    lip = g.box(xl, y0 + 6 * S, z0 + SHEET, 4, y1 - y0 - 12 * S, 4)
    return g.fuse(sheet, *folds, lip)


def section(x0, top, open_to=1):
    """One section in one part: the plate up to top - 10 S and its flange."""
    return g.fuse(section_plate(x0, top - 10.0 * S, open_to), section_flange(x0, top - 10.0 * S, open_to))


# ---------------------------------------------------------------------------
# the assembly
# ---------------------------------------------------------------------------

def build(path: str, sections: int = 5, both_sides: bool = False, drawn_at: float = 0.0) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def part(shape, text, rgb):
        if g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
        lab = st.AddShape(shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(parent, lab, x=0.0, y=0.0, z=0.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(parent, lab, TopLoc_Location(t))

    yellow, grey, steel = (0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.62, 0.64, 0.68)
    root = st.NewShape()
    n = int(sections)
    if both_sides:
        TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.WAYCOVER.TWO"))
        travel = TRAVEL
        c_left = n * T                                   # the carriage's left face at axis 0
        c_right = c_left + 200.0 * S + travel            # its right face at the end of the travel
        end = c_right + n * T                            # the right cover's fixed end
        e = 20.0 * S                                     # the end plates' thickness
        place(root, part(bed(-e, end + e, 0, end, 0, end, supports=(0, 1)), "BASE", grey))
        place(root, part(end_plate(-e, 0, -2 * e, -e, -1), "FRAME.LEFT", grey))
        place(root, part(g.fuse(end_plate(end, end + e, end + e, end + 2 * e, 1), motor(end + 2 * e, 1)), "FRAME.RIGHT",
                         grey))
        place(root, part(carriage(c_left, 200.0 * S), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            top = (170.0 - 2 * (k - 1)) * S
            place(root, part(section((k - 1) * T, top, 1), f"COVER.L.{k}", steel))
            x = c_right + (n - k) * T - travel * k / n
            place(root, part(section(x, top, -1), f"COVER.R.{k}", steel))
    else:
        TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.WAYCOVER"))
        b_top = BED_TOP + 125.0 * S
        bracket = chamfer(g.box(0, 20 * S, BED_TOP, T, 260 * S, b_top - BED_TOP), 3.0, lambda p: abs(p[2] - b_top) < 1e-6)
        length = 1000.0 * S
        base = g.fuse(bed(0, length, T, length - 10 * S, T, length), bracket, motor(length, 1))
        place(root, part(base, "BASE", grey))
        x_c = T + n * T                                   # the carriage's left face, closed
        place(root, part(carriage(x_c + drawn_at, 100.0 * S), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            x = T + (k - 1) * T + drawn_at * k / n
            if k in (1, 3):
                place(root, part(section_plate(x, 160.0 * S), f"COVER.{k}.PLATE", steel))
                place(root, part(section_flange(x, 160.0 * S), f"COVER.{k}.FLANGE", steel))
            else:
                place(root, part(section(x, 170.0 * S), f"COVER.{k}", steel))
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
    drawn = 0.0
    if "--drawn-at" in sys.argv:
        raw = sys.argv[sys.argv.index("--drawn-at") + 1]
        drawn = float(raw)
        args = [a for a in args if a != raw]
    build(args[0] if args else "test_waycover.step", sections=count, both_sides="--both-sides" in sys.argv,
          drawn_at=drawn)
    print("written")
