"""Write a small machine axis with a telescopic way cover as a STEP assembly (task 0034; generic, no owner data).

TEST.WAYCOVER                    mm; the covers lie along X, nested into each other (axis at 0 = closed)
  BASE                           the machine bed 1000 x 300 x 60 (top edges chamfered) with two linear rails on top
                                 (y 80 … 100 and 200 … 220, 18 high) and the cover's end bracket at x = 0 … 20
  CARRIAGE                       100 x 200: a saddle on four guide blocks that wrap the rails, T-slots on top; its
                                 left face at x = 120 (the axis joint moves it)
  COVER.1.PLATE, COVER.1.FLANGE  section 1 (two parts) at x = 20: the plate, an inverted U of folded 3 mm sheet the
                                 rails run through, and the flange, the top sheet with its edges folded down and a wiper
                                 lip
  COVER.2                        section 2 (one part: plate and flange in one), x = 40
  COVER.3.PLATE, COVER.3.FLANGE  section 3 (two parts), x = 60
  COVER.4                        section 4, x = 80
  COVER.5                        section 5, x = 100 (the one at the carriage)

Five sections over a 500 mm axis: each one slides 100 mm relative to its neighbour, so the sections stand
at x + 100, 200, 300, 400, 500 mm when the axis is at 500 mm. Every part of a section lies within its 20 mm along X.

``--sections N`` (task 0035): N sections instead of five (COVER.1 … COVER.N at x = 20, 40 …; sections 1 and 3 of two
parts as above). Five is the default and gives the committed test_waycover_b.step.

``--both-sides`` (task 0035): TEST.WAYCOVER.TWO, a cover each side of the carriage on one 500 mm X axis:
  BASE                           the bed (x -20 … end + 20) with the two rails
  FRAME.LEFT, FRAME.RIGHT        the end plates the covers are fixed to, x -40 … 0 and end … end + 40, each bolted to
                                 the bed's end face with four hex bolts (heads in one part with the plate)
  CARRIAGE                       200 x 200, x = 20 N … 20 N + 200 at axis 0 (left end of its travel)
  COVER.L.1 … COVER.L.N          left cover, nested at x = 0, 20 … (closed at axis 0); COVER.L.N touches the carriage
  COVER.R.1 … COVER.R.N          right cover, fixed end at the right (COVER.R.1), open at axis 0: section k stands at
                                 x = C + (N - k) 20 - 500 k / N, C = the carriage's right face at axis 500 mm
Both covers' section k moves k/N of the axis (500 mm: 100, 200 … 500 mm), the left one opening, the right one
closing; at 500 mm the right cover is nested against FRAME.RIGHT's side of the carriage. The sections next to the
carriage (COVER.L.N, COVER.R.N) may be made the carriage section (bolted to it). Section k is 2 (k - 1) mm lower than
section 1 (they nest).

``--drawn-at MM`` (task 0090): the single-cover model drawn with the axis at MM (like a cover drawn at mid-travel):
the carriage stands MM further along and section k MM k / N further than in the closed drawing.

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

T = 20.0                        # a section's thickness along X (its pitch when closed)
RAILS = (80.0, 200.0)           # the rails' left sides (y), 20 wide, z 60 … 78
SHEET = 3.0                     # the covers' sheet metal
BED_TOP = 60.0
SCREW_R, SCREW_Z = 12.0, 90.0   # the ball screw along X at y 150


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
    plate = _yz_prism([(0, 0), (300, 0), (300, BED_TOP - c), (300 - c, BED_TOP), (c, BED_TOP), (0, BED_TOP - c)],
                      x0, x1)
    rails = [_yz_prism([(y, BED_TOP), (y + 20, BED_TOP), (y + 20, BED_TOP + 16.5), (y + 18.5, BED_TOP + 18),
                        (y + 1.5, BED_TOP + 18), (y, BED_TOP + 16.5)], rail_x0, rail_x1) for y in RAILS]
    extra = [g.cyl(SCREW_R, screw_x1 - screw_x0, (screw_x0, 150, SCREW_Z), (1, 0, 0))]
    for end in supports:
        xs = screw_x1 - 30 if end else screw_x0
        blk = g.polygon_prism(chamfered_rect(xs, 122, 30, 56, 4), 52.0, g.T(0, 0, BED_TOP))
        extra.append(chamfer(blk, 2.0, lambda p: abs(p[2] - BED_TOP - 52) < 1e-6))
    pockets = [g.box(x, y, 12, 70, 8, 30) for x in range(int(x0) + 45, int(x1) - 100, 100) for y in (-1.0, 293.0)]
    return g.cut(g.fuse(plate, *rails, *extra), *pockets)


def motor(x_face, out: int):
    """A servo motor on the screw's axis behind an end face at x_face (towards ``out`` along X): flange, body, cap."""
    def along(x_a, length, shape_fn):
        x_lo = x_a if out > 0 else x_a - length
        return shape_fn(x_lo, length)
    flange = along(x_face, 12.0, lambda x, L: _yz_prism(chamfered_rect(114, SCREW_Z - 36, 72, 72, 6), x, x + L))
    body = along(x_face + 12 * out, 110.0, lambda x, L: _yz_prism(chamfered_rect(118, SCREW_Z - 32, 64, 64, 8), x,
                                                                  x + L))
    cap = along(x_face + 122 * out, 14.0, lambda x, L: _yz_prism(chamfered_rect(123, SCREW_Z - 27, 54, 54, 10), x,
                                                                 x + L))
    plug = along(x_face + 40 * out, 26.0, lambda x, L: g.box(x, 138, SCREW_Z + 32, L, 24, 14))
    return g.fuse(flange, body, cap, plug)


def carriage(x0, length):
    """The saddle (z 92 … 175) on four guide blocks round the rails (z 70 … 92), x0 … x0 + length."""
    saddle = g.polygon_prism(chamfered_rect(x0, 50, length, 200, 8), 175.0 - 92.0, g.T(0, 0, 92))
    saddle = chamfer(saddle, 3.0, lambda p: abs(p[2] - 175.0) < 1e-6)
    blocks = []
    a = 0.05 * length
    w = 0.4 * length
    for xb in (x0 + a, x0 + length - a - w):
        for y in RAILS:
            blk = g.cut(g.box(xb, y - 10, 70, w, 40, 22), g.box(xb - 1, y - 1, 69, w + 2, 22, 9.5))
            blocks.append(blk)
    heads = [g.xform(hex_prism(10.0, 6.0), g.T(x, y, 175.0)) for x in (x0 + 0.2 * length, x0 + 0.8 * length)
             for y in (65.0, 235.0)]
    nut = g.box(x0 + 0.3 * length, 128, 72, 0.4 * length, 44, 21)       # the ball nut's housing round the screw
    shape = g.cut(g.fuse(saddle, *blocks, *heads, nut),
                  g.cyl(SCREW_R + 1, length + 2, (x0 - 1, 150, SCREW_Z), (1, 0, 0)))
    slots = []
    for y in (100.0, 150.0, 200.0):                                  # T-slots along X
        slots.append(g.box(x0 - 1, y - 7, 166, length + 2, 14, 10))
        slots.append(g.box(x0 - 1, y - 11, 158, length + 2, 22, 8))
    return g.cut(shape, *slots)


def end_plate(x_in0, x_in1, x_out0, x_out1, out: int):
    """FRAME.LEFT / RIGHT: an end plate on the bed's end (x_in0 … x_in1, z 60 … 220) and down its end face
    (x_out0 … x_out1, z 10 … 220), four hex bolts into the bed's end and two higher up, their heads on the outer face
    (towards ``out`` = -1 or +1 along X)."""
    shape = g.fuse(g.box(x_in0, 0, BED_TOP, x_in1 - x_in0, 300, 220 - BED_TOP),
                   g.box(x_out0, 0, 10, x_out1 - x_out0, 300, 210))
    shape = chamfer(shape, 4.0, lambda p: abs(p[2] - 220.0) < 1e-6)
    x_face = x_out0 if out < 0 else x_out1
    heads = [_hex_x(16.0, 7.0 * out, x_face, y, z) for y in (50.0, 250.0) for z in (25.0, 45.0, 190.0)]
    return g.fuse(shape, *heads)


# ---------------------------------------------------------------------------
# the cover sections: folded sheet, 20 mm along X
# ---------------------------------------------------------------------------

def _u(y0, y1, z0, z1, leg, z_open):
    return [(y0, z0), (y1, z0), (y1, z1), (y1 - leg, z1), (y1 - leg, z_open), (y0 + leg, z_open), (y0 + leg, z1),
            (y0, z1)]


def section_plate(x0, top, open_to=1):
    """An inverted U (legs 25 wide, the rails run through below z 135) of 3 mm sheet with its edges folded 17 mm
    along X, x0 … x0 + 20, from the bed (z 60) up to ``top``; the folds face +x (``open_to`` 1) or -x (-1)."""
    y0, y1, z_open, leg = 20.0, 280.0, 135.0, 25.0
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
    """The top sheet on a plate whose top is at ``z0``: 3 mm, 4 mm wider each side with its edges folded 12 mm down,
    and a wiper lip on the edge the next section slides under (the open side)."""
    sheet = g.box(x0, 16, z0, T, 268, SHEET)
    folds = [g.box(x0, 16, z0 - 12, T, SHEET, 12), g.box(x0, 281, z0 - 12, T, SHEET, 12)]
    xl = x0 + T - 4 if open_to > 0 else x0
    lip = g.box(xl, 22, z0 + SHEET, 4, 256, 4)
    return g.fuse(sheet, *folds, lip)


def section(x0, top, open_to=1):
    """One section in one part: the plate up to top - 10 and its flange."""
    return g.fuse(section_plate(x0, top - 10.0, open_to), section_flange(x0, top - 10.0, open_to))


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
        travel = 500.0
        c_left = n * T                                   # the carriage's left face at axis 0
        c_right = c_left + 200.0 + travel                # its right face at axis 500 mm
        end = c_right + n * T                            # the right cover's fixed end
        place(root, part(bed(-20, end + 20, 0, end, 0, end, supports=(0, 1)), "BASE", grey))
        place(root, part(end_plate(-20, 0, -40, -20, -1), "FRAME.LEFT", grey))
        place(root, part(g.fuse(end_plate(end, end + 20, end + 20, end + 40, 1), motor(end + 40, 1)), "FRAME.RIGHT",
                         grey))
        place(root, part(carriage(c_left, 200.0), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            top = 170.0 - 2 * (k - 1)
            place(root, part(section((k - 1) * T, top, 1), f"COVER.L.{k}", steel))
            x = c_right + (n - k) * T - travel * k / n
            place(root, part(section(x, top, -1), f"COVER.R.{k}", steel))
    else:
        TDataStd_Name.Set_s(root, TCollection_ExtendedString("TEST.WAYCOVER"))
        bracket = chamfer(g.box(0, 20, BED_TOP, T, 260, 125.0), 3.0, lambda p: abs(p[2] - 185.0) < 1e-6)
        base = g.fuse(bed(0, 1000, T, 990, T, 1000), bracket, motor(1000, 1))
        place(root, part(base, "BASE", grey))
        x_c = T + n * T                                   # the carriage's left face, closed
        place(root, part(carriage(x_c + drawn_at, 100.0), "CARRIAGE", yellow))
        for k in range(1, n + 1):
            x = T + (k - 1) * T + drawn_at * k / n
            if k in (1, 3):
                place(root, part(section_plate(x, 160.0), f"COVER.{k}.PLATE", steel))
                place(root, part(section_flange(x, 160.0), f"COVER.{k}.FLANGE", steel))
            else:
                place(root, part(section(x, 170.0), f"COVER.{k}", steel))
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
