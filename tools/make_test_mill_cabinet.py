"""Write the test mill (the vertical machining centre of make_test_mill.py) inside its own sheet-metal enclosure with
two front sliding doors as a STEP assembly (task 0156: a person changes the tool by hand; task 0249: the larger VMC
standing on the floor in its own enclosure – no cabinet stand). All sizes in mm; the floor is z 0. Nothing of a real
machine. (The file keeps its old name: every caller knows it.)

TEST.MILL.ENCLOSED
  ENCLOSURE                 one sheet-metal solid round the machine (x -1250..1250, back face y 1390): back, sides,
                            roof (z 2500), the upper front panel (y -380..-372) with the door opening x -600..600,
                            z 840..1960, and below it a lower front (front face y -398, up to z 750; a toe recess 60 deep, 100 high under
                            the doors) with a shelf
  DOOR RAIL                 the doors' rail above the opening, x -1250..1250
  SLIDING DOOR              the left door: a frame x -615..0 (its window drawn open; 210 wide at the meeting edge),
                            y -396..-382, z 820..1980, a vertical handle bar Ø16 at x -170 (its front y -451);
                            slides along -x (a slide joint in the tests, open at +350 mm): the door the person opens,
                            away from the tool trolley on its right
  SLIDING DOOR RIGHT        the right door, x 0..615, its handle at x 170; slides along +x (it follows the left
                            door's joint with ratio -1 in the tests)
  CONTROL PANEL             a plain box with a screen on an arm at the right front corner (no maker's look)
  WORK LIGHT                a light bar under the roof inside, over the table
  TEST.MILL                 the VMC of make_test_mill.py, raised by 900 (the bed's bottom on the floor), its head
                            (Z.ASM) 80 higher; in the spindle END MILL D10 BT40: a Ø10 end mill in a BT40-like holder,
                            gauge line at the spindle's nose (z 210 + 900), tip 120 below it; on its head (Z.ASM) a
                            RELEASE BUTTON: a bracket on the cartridge's left with a green push button (the drawbar's
                            release) facing the operator at x -130, z 240 (mill coordinates)

The spindle's axis is at x = 0, y = 0, 380 mm behind the doors' panel: a person standing at the doors leans in and
reaches the holder and the button (blender/tc_person.py).

usage: python make_test_mill_cabinet.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_mill as mill  # noqa: E402
from machine_parts import (DARK, ENCLOSURE_GREY, RAIL_STEEL, SCREEN, asm, bt40_holder_with_end_mill,  # noqa: E402
                           chamfer, chamfered_rect, g, part, sliding_door, write)

RAISE = -mill.FLOOR                       # the mill's floor (z -900) on the floor (0)
X0, X1, BACK = -1250.0, 1250.0, 1390.0    # the enclosure's sides and its back wall's back face
PANEL = -380.0                            # the upper front panel's front face (y); it is T thick
APRON = (-398.0, 750.0)                   # the lower front: its front face (y), its top (z)
ROOF = 2500.0
T = 8.0                                   # sheet
OPEN = (-600.0, 600.0, 840.0, 1960.0)      # the front panel's opening: x0, x1, z0, z1
DOOR_Y = PANEL - 2.0                       # the doors' back face (y): 2 mm in front of the panel
DOOR_T = 14.0
DOOR_Z = (820.0, 1980.0)
DOOR_W = 615.0
DOOR_OPEN = 350.0                          # mm the left door slides to the left to open (the right one as far right):
                                           # its handle stays inside the opening, where the hand comes from
HANDLE_X = -170.0                          # the left door's handle (the person's: away from the trolley on its right),
HANDLE_X_RIGHT = 170.0                     # far enough out that the person stands as close as the doors allow
HANDLE_OUT = 55.0                          # its bar's front this far before the door: room for the fist behind it
TOE = (60.0, 100.0)                        # the toe recess under the lower front: depth, height (in front of the doors)


def enclosure():
    yf, ztop = APRON
    back = g.box(X0, BACK - T, 0.0, X1 - X0, T, ROOF)
    sides = [g.box(x, yf, 0.0, T, BACK - yf, ztop) for x in (X0, X1 - T)]
    sides += [g.box(x, PANEL, ztop, T, BACK - PANEL, ROOF - ztop) for x in (X0, X1 - T)]
    roof = g.box(X0, PANEL, ROOF - T, X1 - X0, BACK - PANEL, T)
    apron = g.box(X0, yf, 0.0, X1 - X0, T, ztop)
    shelf = g.box(X0, yf, ztop - T, X1 - X0, PANEL + T - yf, T)
    front = g.box(X0, PANEL, ztop - T, X1 - X0, T, ROOF - ztop + T)
    hole = g.box(OPEN[0], PANEL - 1.0, OPEN[2], OPEN[1] - OPEN[0], T + 2.0, OPEN[3] - OPEN[2])
    toe = g.box(OPEN[0], yf - 1.0, -1.0, OPEN[1] - OPEN[0], TOE[0] + 1.0, TOE[1] + 1.0)        # room for the toes
    toe_back = g.box(OPEN[0], yf + TOE[0], 0.0, OPEN[1] - OPEN[0], T, TOE[1] + T)
    toe_top = g.box(OPEN[0], yf, TOE[1], OPEN[1] - OPEN[0], TOE[0] + T, T)
    return g.fuse(g.cut(g.fuse(back, *sides, roof, apron, shelf, front), hole, toe), toe_back, toe_top)


def door_rail():
    return g.box(X0, DOOR_Y - DOOR_T - 8.0, DOOR_Z[1] + 4.0, X1 - X0, PANEL - (DOOR_Y - DOOR_T - 8.0), 20.0)


def doors():
    z0, z1 = DOOR_Z
    kw = dict(handle_z=(1180.0, 1580.0), handle_r=8.0, handle_out=HANDLE_OUT)
    right = sliding_door(0.0, DOOR_W, z0, z1, DOOR_Y, DOOR_T, handle_x=HANDLE_X_RIGHT, sides=(210.0, 60.0), **kw)
    left = sliding_door(-DOOR_W, 0.0, z0, z1, DOOR_Y, DOOR_T, handle_x=HANDLE_X, sides=(60.0, 210.0), **kw)
    return right, left


def control_panel():
    """A plain operator panel: a box with a screen and a key field, on an arm from the enclosure's right side."""
    x0 = X1 + 60.0
    box = g.polygon_prism(chamfered_rect(x0, -600.0, 420.0, 90.0, 12.0), 600.0, g.T(0, 0, 1150.0))
    screen = g.box(x0 + 40.0, -602.0, 1430.0, 340.0, 4.0, 270.0)
    keys = g.box(x0 + 40.0, -602.0, 1190.0, 340.0, 4.0, 200.0)
    arm = g.box(X1, -470.0, 1600.0, 140.0, 60.0, 60.0)
    hinge = g.cyl(40.0, 80.0, (X1 + 50.0, -510.0, 1590.0))
    link = g.box(X1 + 20.0, -560.0, 1600.0, 60.0, 100.0, 60.0)
    return g.fuse(g.cut(box, screen, keys), arm, hinge, link)


def work_light():
    bar = g.polygon_prism(chamfered_rect(-450.0, -380.0, 900.0, 70.0, 10.0), 40.0, g.T(0, 0, ROOF - T - 70.0))
    lens = g.box(-430.0, -370.0, ROOF - T - 74.0, 860.0, 50.0, 4.0)
    brackets = [g.box(x, -360.0, ROOF - T - 30.0, 30.0, 30.0, 30.0) for x in (-400.0, 370.0)]
    return g.fuse(bar, lens, *brackets)


def release_button():
    """The drawbar release button on the head's left (task 0156): a bracket from the cartridge with a box and a round
    green push button facing the operator (-y); in Z.ASM's coordinates (mm, as make_test_mill.py)."""
    bracket = g.box(-160.0, -40.0, 222.0, 87.0, 40.0, 36.0)
    cap = g.cyl(8.0, 8.0, (-130.0, -40.0, 240.0), (0.0, -1.0, 0.0))
    return chamfer(g.fuse(bracket, cap), 2.0, lambda p: abs(p[0] + 160.0) < 1e-6)


HEAD_UP = 80.0                    # the head sits this much higher than on the plain test mill: room for a holder
TOOL_TIP = 10.0                   # the tool's tip in the head's coordinates (before HEAD_UP): 20 above the stock


def model():
    sx, sy, sz, sdx, sdy, sdz = mill.STOCK
    stock = part("STOCK 200x200x40", g.box(sx, sy, sz, sdx, sdy, sdz), mill.ALU)
    finished = part("FINISHED PART", mill.finished_part(), mill.ALU)
    end_mill = part("END MILL D10 BT40", bt40_holder_with_end_mill(), (0.62, 0.63, 0.66))
    ball = part("BALL MILL D6", mill.ball_mill(3.0, 30.0))
    button = part("RELEASE BUTTON", release_button(), (0.1, 0.55, 0.2))
    m = mill.machine("TEST.MILL", stock, finished, mill.STOCK, [(end_mill, (0.0, 0.0, TOOL_TIP)),
                                                                (ball, mill.BALL_TIP),
                                                                (button, (0.0, 0.0, 0.0))], ball_bracket=True)
    if not _raise_head(m):
        raise RuntimeError("no Z.ASM in the test mill")
    right, left = doors()
    return asm("TEST.MILL.ENCLOSED", part("ENCLOSURE", enclosure(), ENCLOSURE_GREY),
               part("DOOR RAIL", door_rail(), RAIL_STEEL), part("SLIDING DOOR", left, DARK),
               part("SLIDING DOOR RIGHT", right, DARK), part("CONTROL PANEL", control_panel(), SCREEN),
               part("WORK LIGHT", work_light(), (0.9, 0.9, 0.85)), (m, (0.0, 0.0, RAISE)))


def _raise_head(node) -> bool:
    """Z.ASM HEAD_UP higher on its column (the CAD pose: the tool in its holder clears the stock)."""
    for c in getattr(node, "children", []):
        if getattr(c.node, "name", "") == "Z.ASM":
            c.M = c.M @ g.T(0.0, 0.0, HEAD_UP)
            return True
        if _raise_head(c.node):
            return True
    return False


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_mill_cabinet.step")
    print("written")
