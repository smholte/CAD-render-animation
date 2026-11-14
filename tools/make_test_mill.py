"""Write a small 3-axis milling machine as a STEP assembly for the milling tests (task 0027; more detail: task 0122).

All sizes in mm. The table moves along Y, the carriage along X, the head along Z:

TEST.MILL
  BED                       cast bed 700 x 500 x 60 (top at z = 0, flat: the chips that fall off the table land on
                            it; its bottom, -60, is the machine's lowest point = the floor), corners chamfered, a
                            recessed band round its sides
  COLUMN                    behind the table, x -300..300, y 250..370, z -60..340: chamfered, three ribs at the back
  LINEAR RAIL X             x2, profile rails on the column's front (z 160 and 260)
  SERVO MOTOR X             on the column's right side
  TABLE.ASM                 moves along Y (a slide joint in the tests)
    TABLE                   400 x 300 x 30 (top at z = 30), three T-slots along X (y 0 and +/-118), corners chamfered
    EDGE CLAMP              x4, low toe clamps (top z 48) pushing on the stock's front and back faces at x +/-60
    ISO 4762 M12 x 30 - 12.9   x4, the clamps' screws, down into the outer T-slots
    STOCK 200x200x40        the workpiece: box 200 x 200 x 40, x/y -100..100, z 30..70
    FINISHED PART           the stock with a pocket 100 x 60 x 10 (corners R5) and a hole Ø20 x 15
                            in the middle (for "finish at the CAD part"); same place as the stock
  X.ASM                     moves along X
    CARRIAGE                plate y 200..228, z 100..340 with four guide blocks round the X rails
    LINEAR RAIL Z           x2, on the carriage's front (x +/-50)
    SERVO MOTOR Z           on the carriage's top
    Z.ASM                   moves along Z (sits on X.ASM)
      SPINDLE               Ø60, z 130..250 (its nose at z 130)
      SPINDLE HOUSING       the head: a slide plate with four guide blocks round the Z rails, an arm and a collar
                            round the spindle, and a bracket holding the ball mill (its lowest point z 112)
      SPINDLE MOTOR         on the collar, z 260..360
      END MILL D10          flat end mill Ø10 x 40, tip at x = 0, y = 0, z = 90 (20 mm above the stock)
      BALL MILL D6          ball end mill Ø6 x 30 (cylinder + half sphere), tip at x = 120, z = 90

Nothing new lies below the table's top within reach of the chips but the bed's flat top (the chip tests' landing
heights), and nothing of the head comes below z 112 in the CAD pose.

usage: python make_test_mill.py out.step
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLUE, DARK, GREY, RAIL_STEEL, SCREW_BLACK, BLOCK_BACK, RAIL_H, asm,  # noqa: E402
                           chamfer, chamfered_rect, g, guide_block, on, part, rail, servo_motor, socket_screw, toe_clamp,
                           tslot, write)

STOCK = (-100.0, -100.0, 30.0, 200.0, 200.0, 40.0)      # x, y, z, dx, dy, dz
FLAT_TIP = (0.0, 0.0, 90.0)
BALL_TIP = (120.0, 0.0, 90.0)
POCKET = (-50.0, -30.0, 100.0, 60.0, 10.0, 5.0)          # x, y, dx, dy, depth, corner radius (from the top)
HOLE = (70.0, 50.0, 10.0, 15.0)                          # x, y, radius, depth
TABLE_TOP = 30.0
COL_FRONT = 250.0                                        # the column's front face (y)
RAILS_X = (160.0, 260.0)                                 # z of the X rails' middles
CAR_FRONT = 200.0                                        # the carriage's front face (y)
RAILS_Z = (-50.0, 50.0)                                  # x of the Z rails' middles
CLAMP_TOP = 48.0                                         # the edge clamps' top (z)


def _pocket_tool():
    x, y, dx, dy, depth, r = POCKET
    top = STOCK[2] + STOCK[5]
    return round_vertical(g.box(x, y, top - depth, dx, dy, depth + 5.0), r)


def round_vertical(box, r):
    """Round the vertical edges of a box by r."""
    from model_details import edges, edge_ends
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    fil = BRepFilletAPI_MakeFillet(box)
    for e in edges(box):
        (x0, y0, _z0), (x1, y1, _z1) = edge_ends(e)
        if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
            fil.Add(r, e)
    return fil.Shape()


def finished_part():
    x, y, z, dx, dy, dz = STOCK
    shape = g.cut(g.box(x, y, z, dx, dy, dz), _pocket_tool())
    hx, hy, hr, hd = HOLE
    top = z + dz
    return g.cut(shape, g.cyl(hr, hd + 5.0, (hx, hy, top - hd)))


def ball_mill(radius: float, length: float):
    return g.fuse(g.cyl(radius, length - radius, (0, 0, radius)), g.sphere(radius, (0, 0, radius)))


# ---------------------------------------------------------------------------
# the machine (shared with make_test_toolpath.py)
# ---------------------------------------------------------------------------

def bed():
    b = g.polygon_prism(chamfered_rect(-350, -250, 700, 500, 25), 60.0, g.T(0, 0, -60))
    band = g.cut(g.polygon_prism(chamfered_rect(-360, -260, 720, 520, 30), 32.0, g.T(0, 0, -46)),
                 g.polygon_prism(chamfered_rect(-346, -246, 692, 492, 23.3), 34.0, g.T(0, 0, -47)))
    return g.cut(b, band)


def column():
    body = g.polygon_prism(chamfered_rect(-300, COL_FRONT, 600, 120, 20), 400.0, g.T(0, 0, -60))
    body = chamfer(body, 6.0, lambda p: abs(p[2] - 340.0) < 1e-6)
    ribs = []
    for x in (-210.0, -10.0, 190.0):           # tapered ribs at the back: local (u, v) = (y, z), extruded along x
        rib = g.polygon_prism([(368.0, -60.0), (430.0, -60.0), (430.0, -20.0), (368.0, 290.0)], 20.0)
        ribs.append(g.xform(rib, g.Frame((x, 0, 0), (0, 1, 0), (1, 0, 0))))
    top = g.polygon_prism(chamfered_rect(-290, COL_FRONT + 10, 580, 100, 15), 8.0, g.T(0, 0, 338))
    return g.fuse(body, top, *ribs)


def rail_x():
    """Along X on the column's front: local x = z, local z = x, height towards -y."""
    return on(rail(580.0), (-290.0, COL_FRONT, 0.0), (0, 0, 1), (1, 0, 0))


def carriage():
    plate = g.polygon_prism(chamfered_rect(-80, CAR_FRONT, 160, 28, 6), 240.0, g.T(0, 0, 100))
    plate = chamfer(plate, 3.0, lambda p: abs(p[1] - CAR_FRONT) < 1e-6 and p[2] > 339.0)
    blocks = []
    for zc in RAILS_X:
        for xc in (-45.0, 45.0):
            blocks.append(on(guide_block(50.0), (xc, COL_FRONT, zc), (0, 0, 1), (1, 0, 0)))
    return g.fuse(plate, *blocks)


def rail_z():
    """Along Z on the carriage's front: local x = -x, height towards -y."""
    return rail(240.0)


def housing(ball_bracket: bool):
    """The head (Z.ASM): slide plate on four guide blocks, the arm, the collar round the spindle (bore Ø60, z 185..260),
    and the ball mill's bracket (its sleeve down to z 112)."""
    back = CAR_FRONT - RAIL_H - (BLOCK_BACK - RAIL_H)   # the blocks' backs (y), 6 mm before the rails' tops
    plate = g.polygon_prism(chamfered_rect(-80, 160, 160, back - 160, 6), 170.0, g.T(0, 0, 160))
    blocks = []
    for zc in (205.0, 285.0):
        for xc in RAILS_Z:
            blocks.append(on(guide_block(50.0), (xc, CAR_FRONT, zc), (-1, 0, 0), (0, 0, 1)))
    arm = g.polygon_prism(chamfered_rect(-40, 20, 80, 142, 6), 60.0, g.T(0, 0, 195))
    arm = chamfer(arm, 4.0, lambda p: abs(p[2] - 255.0) < 1e-6)
    collar = g.cyl(46.0, 75.0, (0, 0, 185))
    rib = g.xform(g.polygon_prism([(44.0, 195.0), (161.0, 162.0), (161.0, 195.0)], 16.0),
                  g.Frame((-8.0, 0.0, 0.0), (0, 1, 0), (1, 0, 0)))
    parts = [plate, *blocks, arm, collar, rib]
    if ball_bracket:
        bx = BALL_TIP[0]
        parts += [g.polygon_prism(chamfered_rect(40, -12, bx - 40 + 12, 24, 5), 16.0, g.T(0, 0, 176)),
                  g.cyl(8.0, 192.0 - 112.0, (bx, 0, 112.0))]
    shape = g.fuse(*parts)
    cuts = [g.cyl(30.0, 90.0, (0, 0, 180))]
    if ball_bracket:
        cuts.append(g.cyl(3.0, 40.0, (BALL_TIP[0], 0, 100.0)))
    return g.cut(shape, *cuts)


def spindle():
    prof = [(0.0, 130.0), (29.0, 130.0), (30.0, 131.0), (30.0, 166.0), (32.5, 168.0), (32.5, 176.0), (30.0, 178.0),
            (30.0, 250.0), (0.0, 250.0)]
    return g.revolve(prof)


def spindle_motor():
    prof = [(0.0, 260.0), (46.0, 260.0), (46.0, 270.0), (40.0, 270.0), (40.0, 300.0), (43.0, 300.0), (43.0, 306.0),
            (40.0, 306.0), (40.0, 330.0), (43.0, 330.0), (43.0, 336.0), (40.0, 336.0), (40.0, 352.0),
            (34.0, 360.0), (0.0, 360.0)]
    body = g.revolve(prof)
    box = g.box(-18, -58, 290, 36, 22, 34)
    return g.fuse(body, box)


def table(stock):
    """400 x 300 x 30, three T-slots along X: one under the stock's middle, two beside it for the clamps' screws."""
    t = g.polygon_prism(chamfered_rect(-200, -150, 400, 300, 10), TABLE_TOP)
    t = chamfer(t, 2.0, lambda p: abs(p[2] - TABLE_TOP) < 1e-6 and (abs(abs(p[0]) - 200) < 1e-6 or
                                                                      abs(abs(p[1]) - 150) < 1e-6))
    ys = (0.0, -clamp_screw_y(stock), clamp_screw_y(stock))
    return g.cut(t, *[tslot(402.0, (0, y, 0), (1, 0, 0), top=TABLE_TOP) for y in ys])


def clamp_screw_y(stock) -> float:
    return stock[1] + stock[4] + 18.0                   # 18 mm outside the stock's back face


def edge_clamp(stock):
    """A toe clamp for the stock's back face (+y), at x = 0; its nose on the face, its screw 18 mm out."""
    return toe_clamp(stock[1] + stock[4], TABLE_TOP, CLAMP_TOP)


def machine(name: str, stock_part, finished, stock, tools, ball_bracket: bool = False):
    """The test mill round a stock (x, y, z, dx, dy, dz) and its finished part; ``tools``: [(Part, (x, y, z))] on the
    head."""
    bed_p = part("BED", bed(), BLUE)
    col_p = part("COLUMN", column(), BLUE)
    rail_xp = part("LINEAR RAIL X", rail_x(), RAIL_STEEL)
    motor_x = part("SERVO MOTOR X", servo_motor(70.0, 130.0), DARK)
    table_p = part("TABLE", table(stock), GREY)
    clamp = part("EDGE CLAMP", edge_clamp(stock), DARK)
    screw = part("ISO 4762 M12 x 30 - 12.9", socket_screw(12, 30.0), SCREW_BLACK)
    car_p = part("CARRIAGE", carriage(), BLUE)
    rail_zp = part("LINEAR RAIL Z", rail_z(), RAIL_STEEL)
    motor_z = part("SERVO MOTOR Z", servo_motor(60.0, 110.0), DARK)
    spindle_p = part("SPINDLE", spindle(), GREY)
    housing_p = part("SPINDLE HOUSING", housing(ball_bracket), BLUE)
    smotor = part("SPINDLE MOTOR", spindle_motor(), DARK)

    sy = clamp_screw_y(stock)
    flip = g.Rot((0, 0, 1), 180.0)
    clamps = []
    for x in (-60.0, 60.0):
        clamps += [(clamp, g.T(x, 0, 0)), (clamp, g.T(x, 0, 0) @ flip)]
    screws = [(screw, (x, y, CLAMP_TOP)) for x in (-60.0, 60.0) for y in (-sy, sy)]
    table_asm = asm("TABLE.ASM", table_p, stock_part, finished, *clamps, *screws)
    z_asm = asm("Z.ASM", spindle_p, housing_p, smotor, *tools)
    rz = [(rail_zp, g.Frame((x, CAR_FRONT, 100.0), (-1, 0, 0), (0, 0, 1))) for x in RAILS_Z]
    x_asm = asm("X.ASM", car_p, *rz, (motor_z, (0.0, 213.0, 344.0)), z_asm)
    mx = g.Frame((304.0, 310.0, 210.0), (0, 1, 0), (1, 0, 0))
    return asm(name, bed_p, col_p, *[(rail_xp, (0.0, 0.0, z)) for z in RAILS_X], (motor_x, mx), table_asm, x_asm)


def model():
    sx, sy, sz, sdx, sdy, sdz = STOCK
    stock = part("STOCK 200x200x40", g.box(sx, sy, sz, sdx, sdy, sdz), ALU)
    finished = part("FINISHED PART", finished_part(), ALU)
    end_mill = part("END MILL D10", g.cyl(5.0, 40.0))         # (no colour, as before: the tools' own look)
    ball = part("BALL MILL D6", ball_mill(3.0, 30.0))
    return machine("TEST.MILL", stock, finished, STOCK, [(end_mill, FLAT_TIP), (ball, BALL_TIP)], ball_bracket=True)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_mill.step")
    print("written")
