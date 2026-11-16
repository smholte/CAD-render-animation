"""Write the test mill on a cabinet, inside an enclosure with a sliding door, as a STEP assembly (task 0156: a person
changes the tool by hand). All sizes in mm. Nothing of a real machine.

TEST.MILL.CABINET
  CABINET STAND             steel cabinet 800 x 720 x 850 (z 0..850), a toe recess at its front foot, two doors
                            drawn as shallow grooves; its bottom (z 0) is the floor
  ENCLOSURE                 panels round the mill on the stand: back, sides, roof and a front panel with an opening
                            x -260..260, z 900..1850 (one solid); its roof at z 2000
  DOOR RAIL                 the sliding door's rail above the opening, x -430..870 (the door runs out to the right)
  SLIDING DOOR              a frame 540 x 970 in front of the opening (its middle open, like a clear window) with a
                            vertical handle bar on its left edge; slides along +x (a slide joint in the tests, open at
                            +530 mm)
  TEST.MILL                 the test mill of make_test_mill.py, raised by 910 (its bed's bottom on the stand's top);
                            on its head (Z.ASM) a RELEASE BUTTON: a bracket on the left with a green push button
                            (the drawbar's release) facing the operator at x -130, z 240 (mill coordinates)

The spindle's axis is at x = 0, y = 0; the door's front face at y = -290, its handle bar's front at y = -330.

usage: python make_test_mill_cabinet.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_mill as mill  # noqa: E402
from machine_parts import DARK, LIGHT_GREY, RAIL_STEEL, asm, chamfered_rect, g, part, write  # noqa: E402

RAISE = 910.0                     # the mill's bed bottom (-60) on the stand's top (850)
STAND_TOP = 850.0
ENC = (-440.0, 440.0, -270.0, 450.0)       # enclosure x0, x1, y0 (front panel's front), y1 (back panel's back)
ROOF = 2000.0
OPEN = (-260.0, 260.0, 900.0, 1850.0)       # the front panel's opening: x0, x1, z0, z1
DOOR = (-270.0, 270.0, 890.0, 1860.0)       # the door's frame: x0, x1, z0, z1
DOOR_Y = (-290.0, -276.0)                  # the door's back and front faces (y): 6 mm in front of the panel
DOOR_OPEN = 530.0                          # mm the door slides to the right to open
CABINET_BLUE = (0.16, 0.2, 0.26)


def stand():
    x0, x1, y0, y1 = -400.0, 400.0, -300.0, 420.0
    body = g.polygon_prism(chamfered_rect(x0, y0, x1 - x0, y1 - y0, 6.0), STAND_TOP)
    toe = g.box(x0 - 1, y0 - 1, -1.0, x1 - x0 + 2, 61.0, 81.0)            # toe recess 60 deep, 80 high
    grooves = [g.box(x - 2.0, y0 - 1.0, 120.0, 4.0, 4.0, 680.0) for x in (-1.0, -380.0, 378.0)]
    grooves.append(g.box(x0 + 20, y0 - 1.0, 798.0, x1 - x0 - 40, 4.0, 4.0))
    return g.cut(body, toe, *grooves)


def enclosure():
    x0, x1, y0, y1 = ENC
    t = 10.0
    back = g.box(x0, y1 - t, STAND_TOP, x1 - x0, t, ROOF - STAND_TOP)
    left = g.box(x0, y0, STAND_TOP, t, y1 - y0, ROOF - STAND_TOP)
    right = g.box(x1 - t, y0, STAND_TOP, t, y1 - y0, ROOF - STAND_TOP)
    roof = g.box(x0, y0, ROOF - t, x1 - x0, y1 - y0, t)
    front = g.box(x0, y0, STAND_TOP, x1 - x0, t, ROOF - STAND_TOP)
    hole = g.box(OPEN[0], y0 - 1.0, OPEN[2], OPEN[1] - OPEN[0], t + 2.0, OPEN[3] - OPEN[2])
    return g.cut(g.fuse(back, left, right, roof, front), hole)


def door_rail():
    return g.box(-430.0, DOOR_Y[0] - 4.0, DOOR[3] + 4.0, 1300.0, 30.0, 16.0)


def door():
    x0, x1, z0, z1 = DOOR
    yb, yf = DOOR_Y
    frame = g.box(x0, yb, z0, x1 - x0, yf - yb, z1 - z0)
    window = g.box(x0 + 40.0, yb - 1.0, z0 + 40.0, x1 - x0 - 80.0, yf - yb + 2.0, z1 - z0 - 80.0)
    frame = g.cut(frame, window)
    bar = g.cyl(11.0, 360.0, (x0 + 24.0, -318.0, 1000.0))                 # the handle bar, Ø22
    feet = [g.box(x0 + 16.0, -318.0, z, 16.0, 44.0, 16.0) for z in (1000.0, 1344.0)]
    return g.fuse(frame, bar, *feet)


def release_button():
    """The drawbar release button on the head's left side (task 0156): a bracket from the collar with a box and a
    round green push button facing the operator (-y); in Z.ASM's coordinates (mm, as make_test_mill.py)."""
    bracket = g.box(-150.0, -32.0, 222.0, 108.0, 32.0, 36.0)
    cap = g.cyl(8.0, 8.0, (-130.0, -32.0, 240.0), (0.0, -1.0, 0.0))
    return g.fuse(bracket, cap)


def model():
    sx, sy, sz, sdx, sdy, sdz = mill.STOCK
    stock = part("STOCK 200x200x40", g.box(sx, sy, sz, sdx, sdy, sdz), mill.ALU)
    finished = part("FINISHED PART", mill.finished_part(), mill.ALU)
    end_mill = part("END MILL D10", g.cyl(5.0, 40.0))
    ball = part("BALL MILL D6", mill.ball_mill(3.0, 30.0))
    button = part("RELEASE BUTTON", release_button(), (0.1, 0.55, 0.2))
    m = mill.machine("TEST.MILL", stock, finished, mill.STOCK, [(end_mill, mill.FLAT_TIP), (ball, mill.BALL_TIP),
                                                                (button, (0.0, 0.0, 0.0))], ball_bracket=True)
    return asm("TEST.MILL.CABINET", part("CABINET STAND", stand(), CABINET_BLUE),
               part("ENCLOSURE", enclosure(), LIGHT_GREY), part("DOOR RAIL", door_rail(), RAIL_STEEL),
               part("SLIDING DOOR", door(), DARK), (m, (0.0, 0.0, RAISE)))


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_mill_cabinet.step")
    print("written")
