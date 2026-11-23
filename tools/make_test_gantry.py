"""Write a small gantry router with a tool carousel as a STEP assembly for the G-code tests (task 0026; more detail:
task 0122).

All sizes in mm. Task 0262: the layout x 2.5 of the first model (``K``: a sheet-size router, bed 2.0 x 1.5 m) on a
stand that puts the bed's top (z = 0) at 0.9 m above the floor (z = -900). The parts with a real size keep it: the
tools, the stock, its clamps and screws, the T-slots, the profile rails (20 wide) and their guide blocks; the servo
motors are real sizes (110 / 90 mm flanges). The gantry moves along Y, the carriage along X on the gantry's beam, the
head along Z on the carriage, so every axis moves the tool and the workpiece stays on the bed:

TEST.GANTRY
  BED                       2000 x 1500 x 100 (top at z = 0), corners chamfered, eight T-slots along Y
  MACHINE STAND             the bed's stand: legs, a ring of 120 mm tubes under the bed, stretchers, pads on the floor
  LINEAR RAIL Y             x2, profile rails on the bed's edges (x +/-950), y -725..725
  STOCK 300x200x30          the workpiece: x -150..150, y -100..100, z 0..30
  EDGE CLAMP                x4, low toe clamps (top z 18) on the stock's left and right faces at y +/-60
  ISO 4762 M12 x 30 - 12.9  x4, the clamps' screws, down into the T-slots at x +/-168
  CAROUSEL STAND            the carousel's post beside the bed (foot on the floor, top z 323)
  Y.ASM                     the gantry: moves along Y
    GANTRY SIDE L / R       uprights x -1000..-900 and 900..1000, y 155..305, z 80..500, each on a foot with two guide
                            blocks round the Y rail
    BEAM                    x -1050..1550, y 155..305, z 500..650 (it reaches over the carousel)
    LINEAR RAIL X           x2, on the beam's front (z 530 and 620)
    SERVO MOTOR Y           x2, on the uprights' backs; SERVO MOTOR X on the beam's left end
    X.ASM                   moves along X on the beam
      CARRIAGE              plate x -150..150, y 98..133, z 375..800 (behind the spindle, clear of it and the tool),
                            four guide blocks round the X rails, a bracket on top for the Z motor
      LINEAR RAIL Z         x2, on the carriage's front (x +/-105, z 400..800: clear of the carousel's hub)
      SERVO MOTOR Z         on the carriage's top
      Z.ASM                 moves along Z
        SPINDLE             Ø125, z 275..620 (nose at z = 275, a collet nut Ø100 below z 300)
        Z SLIDE             the spindle's mount: a plate on four guide blocks round the Z rails and a collar
        TOOL T1 FLAT D6     flat end mill Ø6 x 30, tip at x = 0, y = 0, z = 245 (215 mm above the stock)
  CAROUSEL.ASM              tool carousel beside the bed, turns about the vertical axis x = 1250, y = 0
    CAROUSEL DISC           Ø425 x 12, z 338..350 (its top is the pockets' height), a hub on top and below
    TOOL T2 BALL D4         ball end mill Ø4 x 30 standing in the disc, tip at (1400, 0, 320), top at z 350
    TOOL T3 DRILL D5        drill Ø5 x 40 with a 118° point, tip at (1250, 150, 310), top at z 350

usage: python make_test_gantry.py out.step
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLOCK_BACK, BLUE, DARK, GREY, RAIL_STEEL, SCREW_BLACK, STEEL, asm,  # noqa: E402
                           chamfer, chamfered_rect, g, guide_block, on, part, rail, servo_motor, socket_screw,
                           toe_clamp, tslot, write)

STOCK = (-150.0, -100.0, 0.0, 300.0, 200.0, 30.0)       # x, y, z, dx, dy, dz (a real block: not scaled)
K = 2.5                            # task 0262: the layout's scale against the first model (task 0026)
FLOOR = -900.0                     # the stand puts the bed's top (z 0) at a working height of 0.9 m
T1_TIP = (0.0, 0.0, 245.0)         # the spindle's nose at z 275, the tool 30 out of it
T2_TIP = (1400.0, 0.0, 320.0)
T3_TIP = (1250.0, 150.0, 310.0)
CAROUSEL_AXIS = (1250.0, 0.0)
# the carousel (task 0067): the disc's top is the pockets' height (z 350), the tools stand in it hanging down, so the
# spindle comes down onto a tool without going into the disc; the disc stays inside x > 1012 (the gantry's right side)
DISC_Z, DISC_R, DISC_T = 338.0, 212.5, 12.0      # a 12 mm plate: the tools show 18 mm below it
SIDE_X = 950.0                     # the Y rails' and the uprights' middles (x +/-)
SIDE_Y = (155.0, 305.0)            # the uprights and the beam (y)
BEAM_X = (-1050.0, 1550.0)
BEAM_Z = (500.0, 650.0)
RAILS_X = (530.0, 620.0)           # z of the X rails on the beam's front
CAR_FRONT = SIDE_Y[0] - BLOCK_BACK - 35.0   # the carriage plate (35 thick) sits on the X rails' guide blocks
RAILS_Z = 105.0                    # x +/- of the Z rails
SLIDE_BACK = CAR_FRONT - BLOCK_BACK         # the Z slide's back on the Z rails' guide blocks
CLAMP_TOP = 18.0
CLAMP_SCREW_X = 168.0              # 18 mm outside the stock's ends
NOSE_Z = 275.0


def flat_mill(radius: float, length: float):
    return g.cyl(radius, length)


def ball_mill(radius: float, length: float):
    return g.fuse(g.cyl(radius, length - radius, (0, 0, radius)), g.sphere(radius, (0, 0, radius)))


def drill(radius: float, length: float, angle: float = 118.0):
    h = radius / math.tan(math.radians(angle) / 2)
    return g.fuse(g.cone(0.0, radius, h), g.cyl(radius, length - h, (0, 0, h)))


def bed():
    b = g.polygon_prism(chamfered_rect(-1000, -750, 2000, 1500, 50), 100.0, g.T(0, 0, -100))
    b = chamfer(b, 3.0, lambda p: abs(p[2]) < 1e-6)
    slots = [tslot(1502.0, (x, 0, 0), (0, 1, 0), top=0.0)
             for x in (-700.0, -420.0, -CLAMP_SCREW_X, -56.0, 56.0, CLAMP_SCREW_X, 420.0, 700.0)]
    return g.cut(b, *slots)


def stand():
    """The bed's stand (task 0262): a welded frame of 120 mm tubes from the floor (z -900) up to the bed (z -100):
    four legs on pads, a ring under the bed, stretchers near the floor."""
    x, y, t = 940.0, 690.0, 120.0
    ring = [g.box(-x, -y, -220, 2 * x, t, t), g.box(-x, y - t, -220, 2 * x, t, t),
            g.box(-x, -y, -220, t, 2 * y, t), g.box(x - t, -y, -220, t, 2 * y, t)]
    legs = [g.box(sx * x - (t if sx > 0 else 0), sy * y - (t if sy > 0 else 0), FLOOR + 15, t, t, -215 - FLOOR - 15)
            for sx in (-1, 1) for sy in (-1, 1)]
    pads = [g.cyl(55.0, 15.0, (sx * (x - t / 2), sy * (y - t / 2), FLOOR)) for sx in (-1, 1) for sy in (-1, 1)]
    low = [g.box(-x, sy * y - (80 if sy > 0 else 0), FLOOR + 150, 2 * x, 80, 80) for sy in (-1, 1)]
    return g.fuse(*ring, *legs, *pads, *low)


def gantry_side():
    """The left upright (x -1000..-900) on its foot with two guide blocks round the Y rail (rail foot on z = 0)."""
    x0 = -SIDE_X
    blocks = [on(guide_block(80.0), (x0, yc, 0.0), (-1, 0, 0), (0, 1, 0)) for yc in (180.0, 280.0)]
    foot = g.polygon_prism(chamfered_rect(x0 - 62, 92, 124, 276, 15), 58.0, g.T(0, 0, BLOCK_BACK))
    z_up = BLOCK_BACK + 58.0
    upright = g.polygon_prism(chamfered_rect(x0 - 50, SIDE_Y[0], 100, SIDE_Y[1] - SIDE_Y[0], 12), BEAM_Z[0] - z_up,
                              g.T(0, 0, z_up))
    gussets = []
    for tri in ([(SIDE_Y[1], z_up), (368.0, z_up), (SIDE_Y[1], 300.0)],     # (y, z) triangles at the upright's
                [(92.0, z_up), (SIDE_Y[0], z_up), (SIDE_Y[0], 300.0)]):    # back and front
        gussets.append(g.xform(g.polygon_prism(tri, 30.0), g.Frame((x0 - 15.0, 0, 0), (0, 1, 0), (1, 0, 0))))
    return g.fuse(foot, upright, *blocks, *gussets)


def beam():
    h = BEAM_Z[1] - BEAM_Z[0]
    b = g.polygon_prism(chamfered_rect(BEAM_X[0], SIDE_Y[0], BEAM_X[1] - BEAM_X[0], SIDE_Y[1] - SIDE_Y[0], 12), h,
                        g.T(0, 0, BEAM_Z[0]))
    b = chamfer(b, 10.0, lambda p: abs(p[2] - BEAM_Z[1]) < 1e-6 and abs(p[1] - SIDE_Y[1]) < 1e-6)
    caps = [g.box(x, SIDE_Y[0] - 5, BEAM_Z[0] - 5, 20, SIDE_Y[1] - SIDE_Y[0] + 10, h + 10)
            for x in (BEAM_X[0] - 20, BEAM_X[1])]
    return g.fuse(b, *caps)


def carriage():
    plate = g.polygon_prism(chamfered_rect(-150, CAR_FRONT, 300, 35, 10), 425.0, g.T(0, 0, 375))
    blocks = [on(guide_block(80.0), (xc, SIDE_Y[0], zc), (0, 0, 1), (1, 0, 0))
              for zc in RAILS_X for xc in (-75.0, 75.0)]
    bracket = g.polygon_prism(chamfered_rect(-100, CAR_FRONT, 200, 160, 15), 25.0, g.T(0, 0, 800))   # behind the
    return g.fuse(plate, *blocks, bracket)                                                         # spindle


def z_slide():
    plate = g.polygon_prism(chamfered_rect(-155, SLIDE_BACK - 45, 310, 45, 12), 225.0, g.T(0, 0, 375))
    blocks = [on(guide_block(80.0), (x, CAR_FRONT, zc), (-1, 0, 0), (0, 0, 1))
              for zc in (437.5, 537.5) for x in (-RAILS_Z, RAILS_Z)]
    collar = g.cyl(82.5, 162.5, (0, 0, 400))
    # the collar and the plate keep clear of the carriage and its Z rails (the spindle itself is far before them)
    return g.cut(g.fuse(plate, collar, *blocks), g.cyl(62.5, 250.0, (0, 0, 350)),
                 g.box(-100, SLIDE_BACK, 350, 200, 100, 250))


def spindle():
    prof = [(0.0, 275.0), (47.5, 275.0), (50.0, 277.5), (50.0, 292.5), (62.5, 300.0), (62.5, 590.0), (52.5, 595.0),
            (52.5, 620.0), (0.0, 620.0)]
    return g.revolve(prof)


def carousel_disc():
    cx, cy = CAROUSEL_AXIS
    top = DISC_Z + DISC_T
    disc = g.cyl(DISC_R, DISC_T, (cx, cy, DISC_Z))
    hub = g.revolve([(0.0, top), (50.0, top), (50.0, top + 25.0), (40.0, top + 35.0), (0.0, top + 35.0)], (cx, cy, 0))
    under = g.cyl(87.5, 12.5, (cx, cy, DISC_Z - 12.5))
    return g.fuse(disc, hub, under)


def carousel_stand():
    """The carousel's post from the floor up to just under the disc."""
    cx, cy = CAROUSEL_AXIS
    z0 = FLOOR + 37.5
    foot = g.polygon_prism(chamfered_rect(cx - 175, cy - 175, 350, 350, 37), 37.5, g.T(0, 0, FLOOR))
    post = g.cyl(75.0, DISC_Z - 27.5 - z0, (cx, cy, z0))
    top = g.cyl(100.0, 12.5, (cx, cy, DISC_Z - 27.5))        # 2.5 mm under the turning disc's hub
    ribs = [g.xform(g.polygon_prism([(75.0, z0), (162.0, z0), (75.0, z0 + 162.0)], 25.0),
                    g.Rot((0, 0, 1), a) @ g.Frame((0, 12.5, 0), (1, 0, 0), (0, -1, 0)))
            for a in (45.0, 135.0, 225.0, 315.0)]
    ribs = [g.xform(r, g.T(cx, cy, 0)) for r in ribs]
    return g.fuse(foot, post, top, *ribs)


def model():
    sx, sy, sz, sdx, sdy, sdz = STOCK
    bed_p = part("BED", bed(), BLUE)
    rail_y = part("LINEAR RAIL Y", rail(1450.0), RAIL_STEEL)
    stock = part("STOCK 300x200x30", g.box(sx, sy, sz, sdx, sdy, sdz), ALU)
    clamp = part("EDGE CLAMP", toe_clamp(sx + sdx, 0.0, CLAMP_TOP, hole_at=CLAMP_SCREW_X - (sx + sdx)), DARK)
    screw = part("ISO 4762 M12 x 30 - 12.9", socket_screw(12, 30.0), SCREW_BLACK)
    post = part("CAROUSEL STAND", carousel_stand(), BLUE)
    frame = part("MACHINE STAND", stand(), DARK)
    side_l = part("GANTRY SIDE L", gantry_side(), BLUE)
    side_r = part("GANTRY SIDE R", g.xform(gantry_side(), g.T(2 * SIDE_X, 0, 0)), BLUE)   # (symmetric in x)
    beam_p = part("BEAM", beam(), BLUE)
    rail_x = part("LINEAR RAIL X", rail(2500.0), RAIL_STEEL)
    motor_y = part("SERVO MOTOR Y", servo_motor(110.0, 200.0), DARK)
    motor_x = part("SERVO MOTOR X", servo_motor(110.0, 200.0), DARK)
    car_p = part("CARRIAGE", carriage(), GREY)
    rail_z = part("LINEAR RAIL Z", rail(400.0), RAIL_STEEL)   # z 400..800: above the carousel's hub
    motor_z = part("SERVO MOTOR Z", servo_motor(90.0, 160.0), DARK)
    spindle_p = part("SPINDLE", spindle(), GREY)
    slide = part("Z SLIDE", z_slide(), GREY)
    t1 = part("TOOL T1 FLAT D6", flat_mill(3.0, 30.0), STEEL)
    t2 = part("TOOL T2 BALL D4", ball_mill(2.0, 30.0), STEEL)
    t3 = part("TOOL T3 DRILL D5", drill(2.5, 40.0), STEEL)
    disc = part("CAROUSEL DISC", carousel_disc(), GREY)

    z_asm = asm("Z.ASM", spindle_p, slide, (t1, T1_TIP))
    rz = [(rail_z, g.Frame((x, CAR_FRONT, 400.0), (-1, 0, 0), (0, 0, 1))) for x in (-RAILS_Z, RAILS_Z)]
    x_asm = asm("X.ASM", car_p, *rz, (motor_z, (0.0, CAR_FRONT + 80.0, 829.0)), z_asm)
    rx = [(rail_x, g.Frame((-1000.0, SIDE_Y[0], z), (0, 0, 1), (1, 0, 0))) for z in RAILS_X]
    my = [(motor_y, g.Frame((x, SIDE_Y[1], 412.0), (1, 0, 0), (0, 1, 0))) for x in (-SIDE_X, SIDE_X)]
    mx = (motor_x, g.Frame((BEAM_X[0] - 20.0, sum(SIDE_Y) / 2, sum(BEAM_Z) / 2), (0, 1, 0), (-1, 0, 0)))
    y_asm = asm("Y.ASM", side_l, side_r, beam_p, *rx, *my, mx, x_asm)
    car = asm("CAROUSEL.ASM", disc, (t2, T2_TIP), (t3, T3_TIP))
    ry = [(rail_y, g.Frame((x, -725.0, 0.0), (-1, 0, 0), (0, 1, 0))) for x in (-SIDE_X, SIDE_X)]
    flip = g.Rot((0, 0, 1), 90.0)                  # the clamp is made for a face at +y: turned to the +x end
    clamps, screws = [], []
    for y in (-60.0, 60.0):
        clamps += [(clamp, g.T(0, y, 0) @ g.Rot((0, 0, 1), -90.0)), (clamp, g.T(0, y, 0) @ flip)]
        screws += [(screw, (x, y, CLAMP_TOP)) for x in (-CLAMP_SCREW_X, CLAMP_SCREW_X)]
    return asm("TEST.GANTRY", bed_p, frame, *ry, stock, *clamps, *screws, post, y_asm, car)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_gantry.step")
    print("written")
