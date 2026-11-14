"""Write a small generic mill with a 5-axis trunnion (A tilts, C turns) as a STEP assembly (task 0066; more detail:
task 0122).

Nothing of a real machine: all sizes in mm, Z up. The bed and the trunnion's supports stand still; a moving column
carries the tool in X, Y and Z (the same head as make_test_4axis.py). The cradle tilts about the X axis line
y = 0, z = 140 (the rotary table's top); the rotary table turns about the vertical line x = 0, y = 0 and holds a
block.

TEST.5AXIS
  BED, LINEAR RAIL X        as in make_test_4axis.py
  SUPPORT L, SUPPORT R      fixed: the trunnion's bearings, x -170 .. -130 and 130 .. 170, round tops (r 40 about the
                            A axis, top z 180), on feet screwed into the bed's T-slots
  BEARING CAP               x2, on the supports' outsides
  SERVO MOTOR A             beside the right support's bearing cap
  A.ASM                     tilts about the line y = 0, z = 140 along X (a rotate joint in the tests)
    CRADLE                  x -130 .. 130, a plate z 90 .. 120 with a cheek at each end
    C DRIVE HOUSING         under the plate (inside the cradle's own sweep)
    C.ASM                   turns about the vertical line x = 0, y = 0 (rides on A)
      ROTARY TABLE          Ø140, z 120 .. 140, four radial T-slots
      BLOCK 60x60x40        the workpiece: x, y -30 .. 30, z 140 .. 180
  X.ASM … TOOL T1 FLAT D6   as in make_test_4axis.py; the tool's tip at (0, 0, 230), 50 above the block

usage: python make_test_5axis.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLUE, DARK, GREY, SCREW_BLACK, bearing_cap, chamfered_rect, g, servo_motor,  # noqa: E402
                           socket_screw, write)
from make_test_4axis import Doc, bed, head, x_rails  # noqa: E402

A_Z = 140.0
TIP_Z = 230.0


def support():
    """The right support (x 130..170) on its foot; the left one is the same turned half round."""
    prof = [(-60.0, 15.0), (60.0, 15.0), (60.0, 100.0), (40.0, A_Z), (-40.0, A_Z), (-60.0, 100.0)]
    body = g.xform(g.polygon_prism(prof, 40.0), g.Frame((130.0, 0, 0), (0, 1, 0), (1, 0, 0)))
    top = g.cyl(40.0, 40.0, (130.0, 0, A_Z), (1, 0, 0))
    foot = g.polygon_prism(chamfered_rect(120, -80, 70, 160, 8), 15.0)
    return g.fuse(body, top, foot)


def cradle():
    return g.fuse(g.box(-130, -90, 90, 260, 180, 30), g.box(-130, -90, 90, 20, 180, 70), g.box(110, -90, 90, 20, 180, 70))


def rotary_table():
    t = g.cyl(70.0, 20.0, (0, 0, 120))
    slots = [g.xform(g.box(18.0, -5.0, 132.0, 60.0, 10.0, 10.0), g.Rot((0, 0, 1), a)) for a in (45.0, 135.0, 225.0, 315.0)]
    return g.cut(t, *slots)


def c_housing():
    return g.revolve([(0.0, 62.0), (40.0, 62.0), (45.0, 67.0), (45.0, 90.0), (0.0, 90.0)])


def model():
    d = Doc()
    bed_p = d.part("BED", bed(), BLUE)
    sup = support()
    right = d.part("SUPPORT R", sup, BLUE)
    left = d.part("SUPPORT L", g.xform(sup, g.Rot((0, 0, 1), 180.0)), BLUE)
    cap = d.part("BEARING CAP", bearing_cap(36.0, 28.0, 8.0), GREY)
    motor = d.part("SERVO MOTOR A", servo_motor(70.0, 110.0), DARK)
    screw = d.part("ISO 4762 M10 x 25 - 12.9", socket_screw(10, 25.0), SCREW_BLACK)
    cradle_p = d.part("CRADLE", cradle(), GREY)
    housing = d.part("C DRIVE HOUSING", c_housing(), DARK)
    table = d.part("ROTARY TABLE", rotary_table(), DARK)
    block = d.part("BLOCK 60x60x40", g.box(-30, -30, A_Z, 60, 60, 40), ALU)
    c_asm = d.asm("C.ASM", table, block)
    a_asm = d.asm("A.ASM", cradle_p, housing, c_asm)
    caps = [(cap, g.Frame((x, 0, A_Z), (0, 1, 0), (s, 0, 0))) for x, s in ((170.0, 1.0), (-170.0, -1.0))]
    screws = [(screw, (s * x, y, 15.0)) for s in (-1.0, 1.0) for x in (140.0, 175.0) for y in (-70.0, 70.0)]
    return d.asm("TEST.5AXIS", bed_p, *x_rails(d), left, right, *caps, (motor, g.Frame((186.0, 0, A_Z), (0, 1, 0), (1, 0, 0))),
                 *screws, a_asm, head(d, TIP_Z))


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_5axis.step")
    print("written")
