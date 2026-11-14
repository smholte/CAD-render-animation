"""Write a small generic mill with a 4th axis (an A-axis rotary table and a tailstock) as a STEP assembly (task 0066;
more detail: task 0122).

Nothing of a real machine: all sizes in mm, Z up. The bed stands still; a moving column carries the tool in X, Y and
Z; the rotary table turns about the X axis line y = 0, z = 150 and holds a round bar between its chuck and the
tailstock's centre.

TEST.4AXIS
  BED                       fixed, top at z = 0, x -250..250, y -150..230: chamfered, three T-slots along X
                            (y 0, +/-70); the headstock's and the tailstock's feet are screwed down into the outer two
  ISO 4762 M10 x 25 - 12.9  x8
  LINEAR RAIL X             x2, on the bed behind the rotary table (y 165 and 195): the column runs on them
  HEADSTOCK                 fixed: the rotary table's housing, x -230 .. -160, on a foot, a bearing cap at its back
  SERVO MOTOR A             on the headstock's front (-y)
  TAILSTOCK                 fixed: body x 140 .. 200 and its centre (a cone) touching the bar's end at x = 120
  HANDWHEEL                 at the tailstock's end
  A.ASM                     turns about the line y = 0, z = 150 along X (a rotate joint in the tests)
    CHUCK                   Ø90, x -160 .. -120, three jaws on the bar (x -120 .. -108: the slot starts at x -93)
    BAR D50x240             the workpiece: Ø50, x -120 .. 120, its top at z = 175
  X.ASM                     moves along X
    COLUMN                  on four guide blocks round the X rails, x -50..50, y 150..210, up to z tip + 128
    LINEAR RAIL Y           x2, on the column's top
    Y.ASM                   moves along Y
      RAM                   a beam on two guide blocks round the Y rails, z tip + 150 .. tip + 210, and a plate
                            down its front (y 45..60) carrying the Z rails
      LINEAR RAIL Z         x2, on the ram's front (x +/-22)
      Z.ASM                 moves along Z
        HEAD                x -35..35, y -35..23, z tip + 70 .. tip + 190, on four guide blocks round the Z rails
        SPINDLE MOTOR       on the head
        SPINDLE             Ø50, z tip + 40 .. tip + 70
        TOOL T1 FLAT D6     flat end mill Ø6, 40 long: tip at (0, 0, 190), 15 above the bar

usage: python make_test_4axis.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLUE, DARK, GREY, RAIL_STEEL, SCREW_BLACK, STEEL, asm, bearing_cap,  # noqa: E402
                           chamfer, chamfered_rect, g, guide_block, on, part, rail, servo_motor, socket_screw, tslot,
                           write)

AXIS_Z = 150.0                      # the A axis: y = 0, z = 150
BAR_R = 25.0
TIP_Z = 190.0
RAILS_X = (165.0, 195.0)            # y of the X rails on the bed (the column's foot: y 145..215)


def bed(slots=(-70.0, 0.0, 70.0)):
    b = g.polygon_prism(chamfered_rect(-250, -150, 500, 380, 20), 60.0, g.T(0, 0, -60))
    b = chamfer(b, 3.0, lambda p: abs(p[2]) < 1e-6)
    return g.cut(b, *[tslot(502.0, (0, y, 0), (1, 0, 0), top=0.0) for y in slots])


def x_rails(d):
    r = d.part("LINEAR RAIL X", rail(480.0), RAIL_STEEL)
    return [(r, g.Frame((-240.0, y, 0.0), (0, 1, 0), (1, 0, 0))) for y in RAILS_X]


def column(tip_z: float):
    top = tip_z + 128.0
    blocks = [on(guide_block(50.0), (x, y, 0.0), (0, 1, 0), (1, 0, 0)) for y in RAILS_X for x in (-30.0, 30.0)]
    foot = g.polygon_prism(chamfered_rect(-60, 145, 120, 70, 8), 18.0, g.T(0, 0, 22))
    body = g.polygon_prism(chamfered_rect(-50, 150, 100, 60, 8), top - 40.0, g.T(0, 0, 40))
    body = chamfer(body, 3.0, lambda p: abs(p[2] - top) < 1e-6)
    return g.fuse(foot, body, *blocks)


def ram(tip_z: float):
    t = tip_z
    beam = g.polygon_prism(chamfered_rect(-40, 45, 80, 165, 6), 60.0, g.T(0, 0, t + 150))
    beam = chamfer(beam, 3.0, lambda p: abs(p[2] - (t + 210)) < 1e-6)
    plate = g.polygon_prism(chamfered_rect(-45, 45, 90, 15, 4), 140.0, g.T(0, 0, t + 70))
    blocks = [on(guide_block(50.0), (x, 180.0, t + 128.0), (-1, 0, 0), (0, 1, 0)) for x in (-25.0, 25.0)]
    return g.fuse(beam, plate, *blocks)


def head_shape(tip_z: float):
    t = tip_z
    body = g.polygon_prism(chamfered_rect(-35, -35, 70, 58, 8), 120.0, g.T(0, 0, t + 70))
    body = chamfer(body, 4.0, lambda p: abs(p[2] - (t + 70)) < 1e-6)
    blocks = [on(guide_block(50.0), (x, 45.0, zc), (-1, 0, 0), (0, 0, 1)) for zc in (t + 100.0, t + 160.0)
              for x in (-22.0, 22.0)]
    return g.fuse(body, *blocks)


def head(d, tip_z: float):
    """The moving column, ram, head, spindle and tool T1 (flat Ø6, 40 long), its tip at (0, 0, tip_z)."""
    col = d.part("COLUMN", column(tip_z), BLUE)
    ry = d.part("LINEAR RAIL Y", rail(60.0), RAIL_STEEL)
    ram_p = d.part("RAM", ram(tip_z), GREY)
    rz = d.part("LINEAR RAIL Z", rail(140.0), RAIL_STEEL)
    hd = d.part("HEAD", head_shape(tip_z), BLUE)
    motor = d.part("SPINDLE MOTOR", servo_motor(60.0, 100.0), DARK)
    spindle = d.part("SPINDLE", g.cyl(25.0, 30.0, (0, 0, tip_z + 40)), GREY)
    tool = d.part("TOOL T1 FLAT D6", g.cyl(3.0, 40.0, (0, 0, tip_z)), STEEL)
    z_asm = d.asm("Z.ASM", hd, (motor, (0.0, -6.0, tip_z + 190.0)), spindle, tool)
    rails_z = [(rz, g.Frame((x, 45.0, tip_z + 70.0), (-1, 0, 0), (0, 0, 1))) for x in (-22.0, 22.0)]
    y_asm = d.asm("Y.ASM", ram_p, *rails_z, z_asm)
    rails_y = [(ry, g.Frame((x, 150.0, tip_z + 128.0), (-1, 0, 0), (0, 1, 0))) for x in (-25.0, 25.0)]
    return d.asm("X.ASM", col, *rails_y, y_asm)


class Doc:
    """Parts and sub-assemblies of a test model (shared by make_test_5axis.py); ``write`` checks each part is one
    solid."""

    def part(self, text, shape, rgb=None):
        return part(text, shape, rgb)

    def asm(self, text, *children):
        return asm(text, *children)

    def write(self, root, path: str):
        write(root, path)


def headstock():
    foot = g.polygon_prism(chamfered_rect(-240, -80, 80, 160, 10), 15.0)
    body = g.polygon_prism(chamfered_rect(-230, -60, 70, 120, 12), AXIS_Z + 50.0)
    body = chamfer(body, 4.0, lambda p: abs(p[2] - (AXIS_Z + 50.0)) < 1e-6)
    return g.fuse(foot, body)


def tailstock():
    centre = g.cone(15.0, 0.0, 20.0, (140, 0, AXIS_Z), (-1, 0, 0))
    foot = g.polygon_prism(chamfered_rect(130, -80, 80, 160, 8), 15.0)
    body = g.polygon_prism(chamfered_rect(140, -40, 60, 80, 8), AXIS_Z + 25.0)
    body = chamfer(body, 3.0, lambda p: abs(p[2] - (AXIS_Z + 25.0)) < 1e-6)
    quill = g.cyl(20.0, 8.0, (132, 0, AXIS_Z), (1, 0, 0))
    return g.fuse(foot, body, quill, centre)


def handwheel():
    hub = g.cyl(10.0, 16.0, (200, 0, AXIS_Z), (1, 0, 0))
    rim = g.cut(g.cyl(36.0, 8.0, (210, 0, AXIS_Z), (1, 0, 0)), g.cyl(30.0, 10.0, (209, 0, AXIS_Z), (1, 0, 0)))
    spokes = [g.xform(g.box(210, -3, 0, 6, 6, 32), g.Rot((1, 0, 0), a, (0, 0, 0)) @ g.T(0, 0, 0))
              for a in (0.0, 120.0, 240.0)]
    spokes = [g.xform(s, g.T(0, 0, AXIS_Z)) for s in spokes]
    knob = g.cyl(5.0, 22.0, (218, 0, AXIS_Z + 33.0), (1, 0, 0))
    return g.fuse(hub, rim, *spokes, knob)


def chuck():
    body = g.fuse(g.cyl(45.0, 32.0, (-160, 0, AXIS_Z), (1, 0, 0)), g.cyl(40.0, 8.0, (-128, 0, AXIS_Z), (1, 0, 0)))
    jaws = [g.xform(g.box(-120, -6, BAR_R, 12, 12, 14), g.Rot((1, 0, 0), a)) for a in (0.0, 120.0, 240.0)]
    jaws = [g.xform(j, g.T(0, 0, AXIS_Z)) for j in jaws]
    return g.fuse(body, *jaws)


def model():
    d = Doc()
    bed_p = d.part("BED", bed(), BLUE)
    hs = d.part("HEADSTOCK", headstock(), BLUE)
    cap = d.part("BEARING CAP", bearing_cap(42.0, 33.0, 8.0), GREY)
    motor = d.part("SERVO MOTOR A", servo_motor(60.0, 100.0), DARK)
    ts = d.part("TAILSTOCK", tailstock(), BLUE)
    wheel = d.part("HANDWHEEL", handwheel(), DARK)
    screw = d.part("ISO 4762 M10 x 25 - 12.9", socket_screw(10, 25.0), SCREW_BLACK)
    chuck_p = d.part("CHUCK", chuck(), DARK)
    bar = d.part("BAR D50x240", g.cyl(BAR_R, 240.0, (-120, 0, AXIS_Z), (1, 0, 0)), ALU)
    a_asm = d.asm("A.ASM", chuck_p, bar)
    screws = [(screw, (x, y, 15.0)) for x in (-215.0, -175.0, 150.0, 190.0) for y in (-70.0, 70.0)]   # in the T-slots
    root = d.asm("TEST.4AXIS", bed_p, *x_rails(d), hs, (cap, g.Frame((-230.0, 0, AXIS_Z), (0, 1, 0), (-1, 0, 0))),
                 (motor, g.Frame((-195.0, -60.0, 100.0), (1, 0, 0), (0, -1, 0))), ts, wheel, *screws, a_asm,
                 head(d, TIP_Z))
    return root


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_4axis.step")
    print("written")
