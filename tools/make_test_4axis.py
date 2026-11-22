"""Write the test mill with a 4th axis – an A-axis rotary table and a tailstock on its table – as a STEP assembly
(task 0066; more detail: task 0122; task 0250: the vertical machining centre of make_test_mill.py, travels X 1000 x
Y 500 x Z 500, BT40, with a rotary table of faceplate Ø220 – nothing of a real make).

All sizes in mm, Z up, the coordinates of make_test_mill.py (the floor at z -900, the table's top at z 30). The table
moves along X on the saddle, the saddle along Y, the head along Z on the fixed column; the rotary table and the
tailstock stand on the table and hold a round bar between the chuck and the tailstock's centre, turning about the X
axis line y = 0, z = AXIS_Z.

TEST.4AXIS
  BED, COLUMN, CHIP TRAY …  the VMC of make_test_mill.py (fixed)
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE, WAY COVER …
    X.ASM                   moves along X
      TABLE                 1200 x 500, T-slots at y 0 and +/-118
      HEADSTOCK             the rotary table's housing, x -340..-197 on a foot screwed into the outer T-slots
      BEARING CAP           at the headstock's back (-x)
      SERVO MOTOR A         on the headstock's front (-y)
      TAILSTOCK             x 150..300: its centre (a cone) touching the bar's end at x = 120
      HANDWHEEL             at the tailstock's end
      ISO 4762 M16 x 40 - 12.9   x8, the feet's screws in the outer T-slots
      A.ASM                 turns about the line y = 0, z = 210 along X (a rotate joint in the tests)
        CHUCK               a faceplate Ø220 (x -195..-180), a chuck Ø160 (x -180..-120) and three jaws on the bar
                            (x -120..-100: the slot starts at x -93)
        BAR D50x240         the workpiece: Ø50, x -120..120, its top at z = 235
  Z.ASM                     moves along Z (in the CAD pose HEAD_UP = 220 above the test mill's)
    SPINDLE, SPINDLE HOUSING, SPINDLE MOTOR
    TOOL HOLDER BT40        a collet holder, its gauge line at the spindle's nose (z 350)
    TOOL T1 FLAT D6         flat end mill Ø6, 40 out of the holder: tip at (0, 0, 250), 15 above the bar

Nothing touches in the CAD pose, with A turned, the table at every corner of X and Y and the head anywhere in Z
above the tool reaching the table (checked with OpenCascade when the model was made).

usage: python make_test_4axis.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_mill as mill  # noqa: E402
from machine_parts import (ALU, BLUE, DARK, GREY, SCREW_BLACK, STEEL, asm, bearing_cap, bt40_collet_holder,  # noqa: E402
                           chamfer, chamfered_rect, g, part, servo_motor, socket_screw, write)

TOP = mill.TABLE_TOP                # 30: the table's top
AXIS_Z = TOP + 180.0                # the A axis: y = 0, z = 210 (the rotary table's centre height 180)
BAR_R = 25.0
TIP_Z = AXIS_Z + BAR_R + 15.0       # 250: the tool's tip, 15 above the bar
STICK, BT40_GAUGE = 40.0, 60.0      # the end mill out of its holder; the holder's nose to its gauge line
NOSE_Z = TIP_Z + STICK + BT40_GAUGE  # 350: the spindle's nose in the CAD pose
HEAD_UP = NOSE_Z - mill.NOSE        # 220
SLOT_Y = 118.0                      # the table's outer T-slots (make_test_mill.table for the mill's stock)
SCREW = "ISO 4762 M16 x 40 - 12.9"


class Doc:
    """Parts and sub-assemblies of a test model (shared by make_test_5axis.py); ``write`` checks each part is one
    solid."""

    def part(self, text, shape, rgb=None):
        return part(text, shape, rgb)

    def asm(self, text, *children):
        return asm(text, *children)

    def write(self, root, path: str):
        write(root, path)


def head_parts(d, tip_z: float):
    """The tool T1 (flat Ø6, 40 out of its holder, tip at (0, 0, tip_z)) and its BT40 collet holder, in Z.ASM's own
    coordinates (the nose at mill.NOSE; Z.ASM is raised by ``tip_z + 100 - mill.NOSE``)."""
    dz = mill.NOSE - (tip_z + STICK + BT40_GAUGE)
    tool = d.part("TOOL T1 FLAT D6", g.cyl(3.0, STICK, (0, 0, tip_z + dz)), STEEL)
    holder = d.part("TOOL HOLDER BT40", bt40_collet_holder(STICK, STICK + BT40_GAUGE), (0.62, 0.63, 0.66))
    return [tool, (holder, (0.0, 0.0, tip_z + dz))]


def screws(d, xs):
    s = d.part(SCREW, socket_screw(16, 40.0), SCREW_BLACK)
    return [(s, (x, y, TOP + 20.0)) for x in xs for y in (-SLOT_Y, SLOT_Y)]


def headstock():
    """The rotary table's housing: a body x -340..-197, y +/-125, up to z 340 (its top rounded off by chamfers), on
    a foot x -370..-168 over the outer T-slots."""
    foot = g.polygon_prism(chamfered_rect(-370, -150, 202, 300, 12), 20.0, g.T(0, 0, TOP))
    body = g.polygon_prism(chamfered_rect(-340, -125, 143, 250, 16), AXIS_Z + 130.0 - TOP, g.T(0, 0, TOP))
    body = chamfer(body, 30.0, lambda p: abs(p[2] - (AXIS_Z + 130.0)) < 1e-6 and abs(abs(p[1]) - 125.0) < 1e-6)
    ring = g.cyl(118.0, 10.0, (-207.0, 0, AXIS_Z), (1, 0, 0))     # the bearing's ring round the faceplate's back
    ring = g.cut(ring, g.cyl(60.0, 12.0, (-208.0, 0, AXIS_Z), (1, 0, 0)))
    return g.fuse(foot, body, ring)


def chuck():
    """The faceplate Ø220 (x -195..-180) with its chuck Ø160 (x -180..-120) and three jaws on the bar (x -120..-100,
    r 25..45)."""
    plate = g.cyl(110.0, 15.0, (-195.0, 0, AXIS_Z), (1, 0, 0))
    body = g.cyl(80.0, 60.0, (-180.0, 0, AXIS_Z), (1, 0, 0))
    body = chamfer(body, 4.0, lambda p: abs(p[0] + 120.0) < 1e-6)
    jaws = [g.xform(g.box(-120.0, -8.0, BAR_R, 20.0, 16.0, 20.0), g.Rot((1, 0, 0), a)) for a in (0.0, 120.0, 240.0)]
    jaws = [g.xform(j, g.T(0, 0, AXIS_Z)) for j in jaws]
    return g.fuse(plate, body, *jaws)


def tailstock():
    """The centre (a cone, its tip on the bar's end at x 120), the quill Ø60 (x 150..190), the body x 190..290 and its
    foot over the outer T-slots."""
    centre = g.cone(20.0, 0.0, 30.0, (150.0, 0, AXIS_Z), (-1, 0, 0))
    quill = g.cyl(30.0, 40.0, (150.0, 0, AXIS_Z), (1, 0, 0))
    foot = g.polygon_prism(chamfered_rect(170, -150, 140, 300, 12), 20.0, g.T(0, 0, TOP))
    body = g.polygon_prism(chamfered_rect(190, -80, 100, 160, 12), AXIS_Z + 50.0 - TOP, g.T(0, 0, TOP))
    body = chamfer(body, 6.0, lambda p: abs(p[2] - (AXIS_Z + 50.0)) < 1e-6)
    return g.fuse(foot, body, quill, centre)


def handwheel():
    hub = g.cyl(14.0, 20.0, (290.0, 0, AXIS_Z), (1, 0, 0))
    rim = g.cut(g.cyl(55.0, 10.0, (305.0, 0, AXIS_Z), (1, 0, 0)), g.cyl(47.0, 12.0, (304.0, 0, AXIS_Z), (1, 0, 0)))
    spokes = [g.xform(g.box(305.0, -4.0, 0.0, 8.0, 8.0, 50.0), g.Rot((1, 0, 0), a)) for a in (0.0, 120.0, 240.0)]
    spokes = [g.xform(s, g.T(0, 0, AXIS_Z)) for s in spokes]
    knob = g.cyl(7.0, 30.0, (315.0, 0, AXIS_Z + 51.0), (1, 0, 0))
    return g.fuse(hub, rim, *spokes, knob)


def model():
    d = Doc()
    hs = d.part("HEADSTOCK", headstock(), BLUE)
    cap = d.part("BEARING CAP", bearing_cap(60.0, 48.0, 10.0), GREY)
    motor = d.part("SERVO MOTOR A", servo_motor(80.0, 130.0), DARK)
    ts = d.part("TAILSTOCK", tailstock(), BLUE)
    wheel = d.part("HANDWHEEL", handwheel(), DARK)
    chuck_p = d.part("CHUCK", chuck(), DARK)
    bar = d.part("BAR D50x240", g.cyl(BAR_R, 240.0, (-120, 0, AXIS_Z), (1, 0, 0)), ALU)
    a_asm = d.asm("A.ASM", chuck_p, bar)
    table = [hs, (cap, g.Frame((-340.0, 0, AXIS_Z), (0, 1, 0), (-1, 0, 0))),
             (motor, g.Frame((-270.0, -125.0, TOP + 110.0), (1, 0, 0), (0, -1, 0))), ts, wheel,
             *screws(d, (-355.0, -182.0, 185.0, 295.0)), a_asm]
    return mill.machine("TEST.4AXIS", None, None, mill.STOCK, head_parts(d, TIP_Z), clamps=False,
                        extra_table=table, head_up=HEAD_UP)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_4axis.step")
    print("written")
