"""Write a small gantry router with a tool carousel as a STEP assembly for the G-code tests (task 0026; more detail:
task 0122).

All sizes in mm. The gantry moves along Y, the carriage along X on the gantry's beam, the head along Z
on the carriage, so every axis moves the tool and the workpiece stays on the bed:

TEST.GANTRY
  BED                       800 x 600 x 40 (top at z = 0), corners chamfered, six T-slots along Y
  LINEAR RAIL Y             x2, profile rails on the bed's edges (x +/-380)
  STOCK 300x200x30          the workpiece: x -150..150, y -100..100, z 0..30
  EDGE CLAMP                x4, low toe clamps (top z 18) on the stock's left and right faces at y +/-60
  ISO 4762 M12 x 30 - 12.9  x4, the clamps' screws, down into the T-slots at x +/-168
  CAROUSEL STAND            the carousel's post beside the bed (foot on the floor, top z 124)
  Y.ASM                     the gantry: moves along Y
    GANTRY SIDE L / R       uprights x -400..-360 and 360..400, y 62..122, z 40..200, each on a foot with two guide
                            blocks round the Y rail
    BEAM                    x -420..620, y 62..122, z 200..260 (it reaches over the carousel)
    LINEAR RAIL X           x2, on the beam's front (z 212 and 248)
    SERVO MOTOR Y           x2, on the uprights' backs; SERVO MOTOR X on the beam's left end
    X.ASM                   moves along X on the beam
      CARRIAGE              plate x -60..60, y 26..40, z 150..320 (behind the spindle, clear of it and the tool),
                            four guide blocks round the X rails, a bracket on top for the Z motor
      LINEAR RAIL Z         x2, on the carriage's front (x +/-42, z 160..320: clear of the carousel's hub)
      SERVO MOTOR Z         on the carriage's top
      Z.ASM                 moves along Z
        SPINDLE             Ø50, z 110..248 (nose at z = 110, a collet nut Ø40 below z 120)
        Z SLIDE             the spindle's mount: a plate on four guide blocks round the Z rails and a collar
        TOOL T1 FLAT D6     flat end mill Ø6 x 30, tip at x = 0, y = 0, z = 80 (50 mm above the stock)
  CAROUSEL.ASM              tool carousel beside the bed, turns about the vertical axis x = 500, y = 0
    CAROUSEL DISC           Ø170 x 10, z 130..140 (its top is the pockets' height), a hub on top and below
    TOOL T2 BALL D4         ball end mill Ø4 x 30 standing in the disc, tip at (560, 0, 110), top at z 140
    TOOL T3 DRILL D5        drill Ø5 x 40 with a 118° point, tip at (500, 60, 100), top at z 140

usage: python make_test_gantry.py out.step
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLUE, DARK, GREY, RAIL_STEEL, SCREW_BLACK, STEEL, asm, chamfer,  # noqa: E402
                           chamfered_rect, g, guide_block, on, part, rail, servo_motor, socket_screw, toe_clamp,
                           tslot, write)

STOCK = (-150.0, -100.0, 0.0, 300.0, 200.0, 30.0)       # x, y, z, dx, dy, dz
T1_TIP = (0.0, 0.0, 80.0)
T2_TIP = (560.0, 0.0, 110.0)
T3_TIP = (500.0, 60.0, 100.0)
CAROUSEL_AXIS = (500.0, 0.0)
# the carousel (task 0067): the disc's top is the pockets' height (z 140), the tools stand in it hanging down, so the
# spindle comes down onto a tool without going into the disc; the disc stays inside x > 410 (the gantry's right side)
DISC_Z, DISC_R = 130.0, 85.0
SIDE_X = 380.0                     # the Y rails' and the uprights' middles (x +/-)
SIDE_Y = (62.0, 122.0)             # the uprights and the beam (y)
BEAM_X = (-420.0, 620.0)
RAILS_X = (212.0, 248.0)           # z of the X rails on the beam's front
CAR_FRONT = 26.0                   # the carriage's front face (y)
RAILS_Z = 42.0                     # x +/- of the Z rails
CLAMP_TOP = 18.0
CLAMP_SCREW_X = 168.0              # 18 mm outside the stock's ends


def flat_mill(radius: float, length: float):
    return g.cyl(radius, length)


def ball_mill(radius: float, length: float):
    return g.fuse(g.cyl(radius, length - radius, (0, 0, radius)), g.sphere(radius, (0, 0, radius)))


def drill(radius: float, length: float, angle: float = 118.0):
    h = radius / math.tan(math.radians(angle) / 2)
    return g.fuse(g.cone(0.0, radius, h), g.cyl(radius, length - h, (0, 0, h)))


def bed():
    b = g.polygon_prism(chamfered_rect(-400, -300, 800, 600, 20), 40.0, g.T(0, 0, -40))
    b = chamfer(b, 3.0, lambda p: abs(p[2]) < 1e-6)
    slots = [tslot(602.0, (x, 0, 0), (0, 1, 0), top=0.0)
             for x in (-280.0, -CLAMP_SCREW_X, -56.0, 56.0, CLAMP_SCREW_X, 280.0)]
    return g.cut(b, *slots)


def gantry_side():
    """The left upright (x -400..-360) on its foot with two guide blocks round the Y rail (rail foot on z = 0)."""
    x0 = -SIDE_X
    blocks = [on(guide_block(50.0), (x0, yc, 0.0), (-1, 0, 0), (0, 1, 0)) for yc in (66.0, 118.0)]
    foot = g.polygon_prism(chamfered_rect(x0 - 25, 37, 50, 110, 8), 18.0, g.T(0, 0, 22))
    upright = g.polygon_prism(chamfered_rect(x0 - 20, SIDE_Y[0], 40, SIDE_Y[1] - SIDE_Y[0], 6), 160.0, g.T(0, 0, 40))
    gussets = []
    for tri in ([(SIDE_Y[1], 40.0), (147.0, 40.0), (SIDE_Y[1], 120.0)],     # (y, z) triangles at the upright's
                [(37.0, 40.0), (SIDE_Y[0], 40.0), (SIDE_Y[0], 120.0)]):    # back and front
        gussets.append(g.xform(g.polygon_prism(tri, 12.0), g.Frame((x0 - 6.0, 0, 0), (0, 1, 0), (1, 0, 0))))
    return g.fuse(foot, upright, *blocks, *gussets)


def beam():
    b = g.polygon_prism(chamfered_rect(BEAM_X[0], SIDE_Y[0], BEAM_X[1] - BEAM_X[0], SIDE_Y[1] - SIDE_Y[0], 6), 60.0,
                        g.T(0, 0, 200))
    b = chamfer(b, 4.0, lambda p: abs(p[2] - 260.0) < 1e-6 and abs(p[1] - SIDE_Y[1]) < 1e-6)
    caps = [g.box(x, SIDE_Y[0] - 2, 198, 8, SIDE_Y[1] - SIDE_Y[0] + 4, 64) for x in (BEAM_X[0] - 8, BEAM_X[1])]
    return g.fuse(b, *caps)


def carriage():
    plate = g.polygon_prism(chamfered_rect(-60, CAR_FRONT, 120, 14, 4), 170.0, g.T(0, 0, 150))
    blocks = [on(guide_block(50.0), (xc, SIDE_Y[0], zc), (0, 0, 1), (1, 0, 0))
              for zc in RAILS_X for xc in (-30.0, 30.0)]
    bracket = g.polygon_prism(chamfered_rect(-40, CAR_FRONT, 80, 64, 6), 10.0, g.T(0, 0, 320))   # behind the spindle
    return g.fuse(plate, *blocks, bracket)


def z_slide():
    plate = g.polygon_prism(chamfered_rect(-62, -14, 124, 18, 5), 90.0, g.T(0, 0, 150))
    blocks = [on(guide_block(40.0), (x, CAR_FRONT, zc), (-1, 0, 0), (0, 0, 1))
              for zc in (175.0, 215.0) for x in (-RAILS_Z, RAILS_Z)]
    collar = g.cyl(33.0, 65.0, (0, 0, 160))
    # the collar is flat at its back, 2 mm before the carriage (the spindle itself is 1 mm before it)
    return g.cut(g.fuse(plate, collar, *blocks), g.cyl(25.0, 100.0, (0, 0, 140)), g.box(-40, CAR_FRONT - 2, 140, 80, 40, 100))


def spindle():
    prof = [(0.0, 110.0), (19.0, 110.0), (20.0, 111.0), (20.0, 117.0), (25.0, 120.0), (25.0, 236.0), (21.0, 238.0),
            (21.0, 248.0), (0.0, 248.0)]
    return g.revolve(prof)


def carousel_disc():
    cx, cy = CAROUSEL_AXIS
    disc = g.cyl(DISC_R, 10.0, (cx, cy, DISC_Z))
    hub = g.revolve([(0.0, 140.0), (20.0, 140.0), (20.0, 150.0), (16.0, 154.0), (0.0, 154.0)], (cx, cy, 0))
    under = g.cyl(35.0, 5.0, (cx, cy, DISC_Z - 5.0))
    return g.fuse(disc, hub, under)


def carousel_stand():
    cx, cy = CAROUSEL_AXIS
    foot = g.polygon_prism(chamfered_rect(cx - 70, cy - 70, 140, 140, 15), 15.0, g.T(0, 0, -40))
    post = g.cyl(30.0, 143.0, (cx, cy, -25.0))
    top = g.cyl(40.0, 6.0, (cx, cy, 118.0))
    ribs = [g.xform(g.polygon_prism([(30.0, -25.0), (65.0, -25.0), (30.0, 40.0)], 10.0),
                    g.Rot((0, 0, 1), a) @ g.Frame((0, 5.0, 0), (1, 0, 0), (0, -1, 0)))
            for a in (45.0, 135.0, 225.0, 315.0)]
    ribs = [g.xform(r, g.T(cx, cy, 0)) for r in ribs]
    return g.fuse(foot, post, top, *ribs)


def model():
    sx, sy, sz, sdx, sdy, sdz = STOCK
    bed_p = part("BED", bed(), BLUE)
    rail_y = part("LINEAR RAIL Y", rail(580.0), RAIL_STEEL)
    stock = part("STOCK 300x200x30", g.box(sx, sy, sz, sdx, sdy, sdz), ALU)
    clamp = part("EDGE CLAMP", toe_clamp(sx + sdx, 0.0, CLAMP_TOP, hole_at=CLAMP_SCREW_X - (sx + sdx)), DARK)
    screw = part("ISO 4762 M12 x 30 - 12.9", socket_screw(12, 30.0), SCREW_BLACK)
    stand = part("CAROUSEL STAND", carousel_stand(), BLUE)
    side_l = part("GANTRY SIDE L", gantry_side(), BLUE)
    side_r = part("GANTRY SIDE R", g.xform(gantry_side(), g.T(2 * SIDE_X, 0, 0)), BLUE)   # (symmetric in x)
    beam_p = part("BEAM", beam(), BLUE)
    rail_x = part("LINEAR RAIL X", rail(1000.0), RAIL_STEEL)
    motor_y = part("SERVO MOTOR Y", servo_motor(60.0, 110.0), DARK)
    motor_x = part("SERVO MOTOR X", servo_motor(60.0, 110.0), DARK)
    car_p = part("CARRIAGE", carriage(), GREY)
    rail_z = part("LINEAR RAIL Z", rail(160.0), RAIL_STEEL)   # z 160..320: above the carousel's hub
    motor_z = part("SERVO MOTOR Z", servo_motor(50.0, 100.0), DARK)
    spindle_p = part("SPINDLE", spindle(), GREY)
    slide = part("Z SLIDE", z_slide(), GREY)
    t1 = part("TOOL T1 FLAT D6", flat_mill(3.0, 30.0), STEEL)
    t2 = part("TOOL T2 BALL D4", ball_mill(2.0, 30.0), STEEL)
    t3 = part("TOOL T3 DRILL D5", drill(2.5, 40.0), STEEL)
    disc = part("CAROUSEL DISC", carousel_disc(), GREY)

    z_asm = asm("Z.ASM", spindle_p, slide, (t1, T1_TIP))
    rz = [(rail_z, g.Frame((x, CAR_FRONT, 160.0), (-1, 0, 0), (0, 0, 1))) for x in (-RAILS_Z, RAILS_Z)]
    x_asm = asm("X.ASM", car_p, *rz, (motor_z, (0.0, 58.0, 334.0)), z_asm)
    rx = [(rail_x, g.Frame((-400.0, SIDE_Y[0], z), (0, 0, 1), (1, 0, 0))) for z in RAILS_X]
    my = [(motor_y, g.Frame((x, SIDE_Y[1], 165.0), (1, 0, 0), (0, 1, 0))) for x in (-SIDE_X, SIDE_X)]
    mx = (motor_x, g.Frame((BEAM_X[0] - 8.0, 92.0, 230.0), (0, 1, 0), (-1, 0, 0)))
    y_asm = asm("Y.ASM", side_l, side_r, beam_p, *rx, *my, mx, x_asm)
    car = asm("CAROUSEL.ASM", disc, (t2, T2_TIP), (t3, T3_TIP))
    ry = [(rail_y, g.Frame((x, -290.0, 0.0), (-1, 0, 0), (0, 1, 0))) for x in (-SIDE_X, SIDE_X)]
    flip = g.Rot((0, 0, 1), 90.0)                  # the clamp is made for a face at +y: turned to the +x end
    clamps, screws = [], []
    for y in (-60.0, 60.0):
        clamps += [(clamp, g.T(0, y, 0) @ g.Rot((0, 0, 1), -90.0)), (clamp, g.T(0, y, 0) @ flip)]
        screws += [(screw, (x, y, CLAMP_TOP)) for x in (-CLAMP_SCREW_X, CLAMP_SCREW_X)]
    return asm("TEST.GANTRY", bed_p, *ry, stock, *clamps, *screws, stand, y_asm, car)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_gantry.step")
    print("written")
