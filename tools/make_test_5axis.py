"""Write the test mill with a 5-axis trunnion (A tilts, C turns) on its table as a STEP assembly (task 0066; more
detail: task 0122; task 0250: the vertical machining centre of make_test_mill.py, travels X 1000 x Y 500 x Z 500,
BT40, with a trunnion whose rotary table is Ø250 – nothing of a real make).

All sizes in mm, Z up, the coordinates of make_test_mill.py (the floor at z -900, the table's top at z 30). The table
moves along X on the saddle, the saddle along Y, the head along Z on the fixed column (the same head and tool as
make_test_4axis.py). The trunnion's supports stand on the table; its cradle tilts about the X axis line y = 0,
z = A_Z (the rotary table's top); the rotary table turns about the vertical line x = 0, y = 0 and holds a block.

TEST.5AXIS
  BED, COLUMN, CHIP TRAY …  the VMC of make_test_mill.py (fixed)
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE, WAY COVER …
    X.ASM                   moves along X
      TABLE                 1200 x 500, T-slots at y 0 and +/-118
      SUPPORT L, SUPPORT R  the trunnion's bearings, x -285..-232 and 232..285, round tops (r 70 about the A axis,
                            top z 330), on feet screwed into the outer T-slots
      BEARING CAP           x2, on the supports' outsides
      SERVO MOTOR A         beside the right support's bearing cap
      ISO 4762 M16 x 40 - 12.9   x4, the feet's screws (outside the supports)
      A.ASM                 tilts about the line y = 0, z = 260 along X (a rotate joint in the tests)
        CRADLE              a plate x -210..210, y -170..170, z 140..180, a cheek at each end (x +/-210..230, up to
                            z 310) and a trunnion shaft Ø90 into each support's bearing; it swings within r 210 of the
                            A axis: 20 mm over the table at any tilt
        C DRIVE HOUSING     on the plate, under the rotary table
        C.ASM               turns about the vertical line x = 0, y = 0 (rides on A)
          ROTARY TABLE      Ø250, z 230..260, four radial T-slots
          BLOCK 60x60x40    the workpiece: x, y -30..30, z 260..300
  Z.ASM                     moves along Z (in the CAD pose HEAD_UP = 330 above the test mill's)
    TOOL HOLDER BT40, TOOL T1 FLAT D6   as in make_test_4axis.py but 50 out of the holder; the tool's tip at
                            (0, 0, 350), 50 above the block

Nothing touches in the CAD pose, with A tilted -60..60° (to -120..120° with the head at the top of Z), C turned, the
table at every corner of X and Y and the head anywhere in Z above the tool reaching the table or the A motor (checked
with OpenCascade when the model was made).

usage: python make_test_5axis.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_mill as mill  # noqa: E402
from machine_parts import (ALU, BLUE, DARK, GREY, bearing_cap, chamfer, chamfered_rect, g,  # noqa: E402
                           servo_motor, write)
from make_test_4axis import BT40_GAUGE, TOP, Doc, head_parts, screws  # noqa: E402

A_Z = TOP + 230.0                   # 260: the A axis (the rotary table's top)
TIP_Z = A_Z + 40.0 + 50.0           # 350: the tool's tip, 50 above the block
STICK_5 = 50.0                      # the end mill 50 out of its holder (10 more than on the 4th-axis mill: room over the
                                    # tilted block, and the two test tools' tips differ - tests/test_rotary.py)
HEAD_UP = TIP_Z + STICK_5 + BT40_GAUGE - mill.NOSE   # 330
TABLE_R = 125.0
SUP = (232.0, 285.0, 70.0)          # a support's inner and outer face (x), its round top's radius
SHAFT_R = 45.0


def support():
    """The right support (x 232..285) on its foot, a bore round the cradle's shaft; the left one is the same turned
    half round."""
    x0, x1, r = SUP
    prof = [(-140.0, TOP + 20.0), (140.0, TOP + 20.0), (140.0, A_Z - 120.0), (r, A_Z), (-r, A_Z), (-140.0, A_Z - 120.0)]
    body = g.xform(g.polygon_prism(prof, x1 - x0), g.Frame((x0, 0, 0), (0, 1, 0), (1, 0, 0)))
    top = g.cyl(r, x1 - x0, (x0, 0, A_Z), (1, 0, 0))
    foot = g.polygon_prism(chamfered_rect(x0, -150, x1 - x0 + 35.0, 300, 10), 20.0, g.T(0, 0, TOP))
    shape = g.fuse(body, top, foot)
    return g.cut(shape, g.cyl(SHAFT_R + 1.0, x1 - x0 + 2.0, (x0 - 1.0, 0, A_Z), (1, 0, 0)))


def cradle():
    plate = g.polygon_prism(chamfered_rect(-210, -170, 420, 340, 20), 40.0, g.T(0, 0, A_Z - 120.0))
    cheeks = [chamfer(g.box(x, -170, A_Z - 120.0, 20, 340, 170), 6.0, lambda p: abs(p[2] - (A_Z + 50.0)) < 1e-6)
              for x in (-230.0, 210.0)]
    shafts = [g.cyl(SHAFT_R, SUP[1] - 2.0 - 230.0, (230.0, 0, A_Z), (1, 0, 0)),
              g.cyl(SHAFT_R, SUP[1] - 2.0 - 230.0, (-230.0, 0, A_Z), (-1, 0, 0))]
    return g.fuse(plate, *cheeks, *shafts)


def rotary_table():
    t = g.cyl(TABLE_R, 30.0, (0, 0, A_Z - 30.0))
    t = chamfer(t, 2.0, lambda p: abs(p[2] - A_Z) < 1e-6)
    slots = [g.xform(g.box(40.0, -7.0, A_Z - 12.0, 90.0, 14.0, 14.0), g.Rot((0, 0, 1), a))
             for a in (45.0, 135.0, 225.0, 315.0)]
    return g.cut(t, *slots)


def c_housing():
    return g.revolve([(0.0, A_Z - 80.0), (100.0, A_Z - 80.0), (100.0, A_Z - 40.0), (90.0, A_Z - 32.0),
                      (0.0, A_Z - 32.0)])


def model():
    d = Doc()
    sup = support()
    right = d.part("SUPPORT R", sup, BLUE)
    left = d.part("SUPPORT L", g.xform(sup, g.Rot((0, 0, 1), 180.0)), BLUE)
    cap = d.part("BEARING CAP", bearing_cap(60.0, 48.0, 10.0), GREY)
    motor = d.part("SERVO MOTOR A", servo_motor(90.0, 140.0), DARK)
    cradle_p = d.part("CRADLE", cradle(), GREY)
    housing = d.part("C DRIVE HOUSING", c_housing(), DARK)
    table = d.part("ROTARY TABLE", rotary_table(), DARK)
    block = d.part("BLOCK 60x60x40", g.box(-30, -30, A_Z, 60, 60, 40), ALU)
    c_asm = d.asm("C.ASM", table, block)
    a_asm = d.asm("A.ASM", cradle_p, housing, c_asm)
    x1 = SUP[1]
    caps = [(cap, g.Frame((x, 0, A_Z), (0, 1, 0), (s, 0, 0))) for x, s in ((x1, 1.0), (-x1, -1.0))]
    on_table = [left, right, *caps, (motor, g.Frame((x1 + 30.0, 0, A_Z), (0, 1, 0), (1, 0, 0))),
                *screws(d, (-303.0, 303.0)), a_asm]
    return mill.machine("TEST.5AXIS", None, None, mill.STOCK, head_parts(d, TIP_Z, STICK_5), clamps=False,
                        extra_table=on_table, head_up=HEAD_UP)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_5axis.step")
    print("written")
