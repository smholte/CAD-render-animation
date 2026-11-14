"""Write a small generic vertical mill with a double-arm tool changer as a STEP assembly (task 0064).

Nothing of a real machine: all sizes in mm, Z up. The table moves along X and Y, the head along Z; the arm and the
disc magazine hang from the column. The CAD pose is the change position: the spindle's gauge line (its nose) at
z = 300 on the axis x = 0, y = 0.

TEST.ATC
  BED, COLUMN               fixed
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE
    X.ASM                   moves along X
      TABLE
      STOCK 160x120x30      x -80..80, y -60..60, z 60..90
  Z.ASM                     moves along Z
    HEAD, SPINDLE           spindle Ø90, its nose (the gauge line) at z = 300
    TOOL T1 BT30 FLAT D10   BT30 holder + flat end mill Ø10, stick-out 40: tip at (0, 0, 215), gauge length 85
  ATC HOUSING, MAGAZINE POST   fixed, above the arm's hub and in the magazine's middle
  ARM.ASM
    CHANGER ARM             hub (round, Ø60) on the axis x = -130, y = 0, vertical; a bar (z 281..299, 1 mm under
                            the spindle's nose) with a U-shaped claw at each end (round inside, Ø47, around a BT30
                            flange Ø46); the claw's open side is cut along the ring round the hub the flange sweeps
                            when the arm turns in. In the CAD it is at rest, along Y; turned +90° about +Z its claws
                            are round x = 0 (the spindle) and x = -260 (the station)
  MAGAZINE.ASM              turns about the vertical axis x = -460, y = 0
    MAGAZINE DISC           Ø280, z 330..350 (inside the pots' hinges: a tipped pot clears it)
    POT                     12 of the same part, one every 30° counter-clockwise from +X (pot 1 at the station):
                            a sleeve lying radially (the tool points outward), its mouth (the gauge line) at radius
                            200, z = 400; it tips down 90° about a hinge pin (round, along the tangent) at radius 150,
                            z = 350: tipped, the station pot's mouth is at (-260, 0, 300), the tool hanging down
    TOOL T2 BT30 BALL D8    in pot 2 (BT30 + ball end mill Ø8, stick-out 35, gauge length 80)

usage: python make_test_atc.py out.step
"""

import math
import os
import sys

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakeSphere)
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GAUGE_Z = 300.0                     # the spindle's nose (gauge line) in the CAD pose
HUB = (-130.0, 0.0)                 # the arm's axis
GRIP_R = 130.0
MAG = (-460.0, 0.0)                 # the magazine's axis
POTS = 12
POT_R = 200.0                       # the pot's mouth (gauge line), from the magazine's axis
POT_Z = 400.0
HINGE_R, HINGE_Z = 150.0, 350.0
DISC_R = 140.0                      # inside the hinges: a tipping pot's block swings down past the disc's rim
T1_STICK, T2_STICK = 40.0, 35.0
BT30_GAUGE = 45.0                   # from the holder's nose to its gauge line (core/tools.py HOLDER_SIZES)


def _fuse(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return out


def _cyl(x, y, z, r, h, d=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*d)), r, h).Shape()


def _cone(z, r1, r2, h):
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r1, r2, h).Shape()


def _box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def _moved(shape, trsf):
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def bt30_tool(stick: float, radius: float, ball: bool = False):
    """A BT30 holder with an end mill, the tip at the origin, along +Z: nose at ``stick``, gauge line 45 above it."""
    if ball:
        mill = _fuse(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, radius), radius).Shape(),
                     _cyl(0, 0, radius, radius, stick - radius))
    else:
        mill = _cyl(0, 0, 0, radius, stick)
    g = stick + BT30_GAUGE
    nose = _cone(stick, 16.0, 18.0, 25.0)
    flange = _cyl(0, 0, g - 20.0, 23.0, 20.0)
    taper = _cone(g, 15.875, 15.875 - 48.4 * 7 / 48, 48.4)
    stud = _cyl(0, 0, g + 48.4, 5.0, 23.0)
    return _fuse(mill, nose, flange, taper, stud)


def changer_arm():
    """The arm in its grip pose (claws round x = 0 and x = -260), then turned back -90° about its hub to rest."""
    hx, hy = HUB
    z0, h = GAUGE_Z - 19.0, 18.0              # 1 mm clear of the spindle's nose, round the flange (z 280 … 300)
    bar = _box(-GRIP_R * 2, -15.0, z0, GRIP_R * 2, 30.0, h)
    hub = _cyl(hx, hy, z0, 30.0, 60.0)
    shapes = [bar, hub]
    for cx, opening in ((0.0, 1.0), (-2 * GRIP_R, -1.0)):
        ring = BRepAlgoAPI_Cut(_cyl(cx, 0, z0, 33.0, h), _cyl(cx, 0, z0 - 1, 23.5, h + 2)).Shape()
        # open towards the way the claw moves when the arm turns +Z into the tools (U-shaped claw)
        y0 = 0.0 if opening > 0 else -40.0
        ring = BRepAlgoAPI_Cut(ring, _box(cx - 23.5, y0, z0 - 1, 47.0, 40.0, h + 2)).Shape()
        shapes.append(ring)
    arm = _fuse(*shapes)
    arm = BRepAlgoAPI_Cut(arm, _cyl(0, 0, z0 - 1, 23.5, h + 2)).Shape()
    arm = BRepAlgoAPI_Cut(arm, _cyl(-2 * GRIP_R, 0, z0 - 1, 23.5, h + 2)).Shape()
    # the way in: the arm turns about its hub, so the flange sweeps a ring round the hub (radius 130 ± 23); nothing of
    # the claw or the bar may stand in that ring on the open side (task 0067: the bar narrowed the opening)
    ring = BRepAlgoAPI_Cut(_cyl(hx, hy, z0 - 1, GRIP_R + 23.5, h + 2), _cyl(hx, hy, z0 - 2, GRIP_R - 23.5, h + 4)).Shape()
    for cx, opening in ((0.0, 1.0), (-2 * GRIP_R, -1.0)):
        y0 = 0.0 if opening > 0 else -45.0
        way = BRepAlgoAPI_Common(ring, _box(cx - 40.0, y0, z0 - 1, 80.0, 45.0, h + 2)).Shape()
        arm = BRepAlgoAPI_Cut(arm, way).Shape()
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(hx, hy, 0), gp_Dir(0, 0, 1)), -math.pi / 2)
    return _moved(arm, t)


def pot():
    """Pot 1 at the station (towards +X from the magazine's axis), not tipped: a sleeve lying along X, its mouth at
    the gauge point, a block down to the hinge pin."""
    mx, my = MAG
    mouth = mx + POT_R
    sleeve = BRepAlgoAPI_Cut(_cyl(mouth - 80.0, my, POT_Z, 28.0, 80.0, (1, 0, 0)),
                             _cyl(mouth - 76.0, my, POT_Z, 18.0, 80.0, (1, 0, 0))).Shape()
    hx = mx + HINGE_R
    block = _box(hx - 15.0, my - 15.0, HINGE_Z, 30.0, 30.0, POT_Z - 28.0 - HINGE_Z + 2.0)
    pin = _cyl(hx, my - 20.0, HINGE_Z, 6.0, 40.0, (0, 1, 0))
    return _fuse(sleeve, block, pin)


# ---------------------------------------------------------------------------
# details (task 0122): nothing new inside a sweep - the arm's ring round the hub (r <= 165), its stroke down, the
# pots and their tools round the magazine (r <= 295 at z 377 .. 423), the head's travel along Z
# ---------------------------------------------------------------------------

COL_FRONT = 250.0
RAILS_Z = (-50.0, 50.0)                 # x of the Z rails on the column's front
GUARD_R = 310.0                         # the magazine guard's inside (the longest tool's tip lies at r 295)


def bed():
    from machine_parts import chamfered_rect, g
    b = g.polygon_prism(chamfered_rect(-250, -250, 500, 500, 25), 80.0, g.T(0, 0, -80))
    band = g.cut(g.polygon_prism(chamfered_rect(-260, -260, 520, 520, 30), 40.0, g.T(0, 0, -64)),
                 g.polygon_prism(chamfered_rect(-246, -246, 492, 492, 23.3), 42.0, g.T(0, 0, -65)))
    return g.cut(b, band)


def column():
    from machine_parts import chamfer, chamfered_rect, g
    body = g.polygon_prism(chamfered_rect(-150, COL_FRONT, 300, 120, 18), 640.0, g.T(0, 0, -80))
    body = chamfer(body, 5.0, lambda p: abs(p[2] - 560.0) < 1e-6)
    ribs = [g.xform(g.polygon_prism([(368.0, -80.0), (420.0, -80.0), (420.0, -40.0), (368.0, 480.0)], 20.0),
                    g.Frame((x, 0, 0), (0, 1, 0), (1, 0, 0))) for x in (-110.0, 90.0)]
    return g.fuse(body, *ribs)


def head():
    """The head: a chamfered housing x -70..70, y 40..228, z 320..520 on four guide blocks round the Z rails."""
    from machine_parts import chamfer, chamfered_rect, g, guide_block, on
    body = g.polygon_prism(chamfered_rect(-70, 40, 140, 188, 10), 200.0, g.T(0, 0, 320))
    body = chamfer(body, 5.0, lambda p: abs(p[2] - 520.0) < 1e-6 and p[1] < 200.0)
    blocks = [on(guide_block(50.0), (x, COL_FRONT, zc), (-1, 0, 0), (0, 0, 1)) for zc in (360.0, 480.0)
              for x in RAILS_Z]
    return g.fuse(body, *blocks)


def spindle_motor():
    from machine_parts import servo_motor
    return servo_motor(80.0, 130.0)


def table():
    """440 x 240 x 30 (z 30..60), four T-slots along X (y -90, -30, 30, 90): the clamps' screws stand in the middle
    two."""
    from machine_parts import chamfer, chamfered_rect, g, tslot
    t = g.polygon_prism(chamfered_rect(-220, -120, 440, 240, 10), 30.0, g.T(0, 0, 30))
    t = chamfer(t, 2.0, lambda p: abs(p[2] - 60.0) < 1e-6 and (abs(abs(p[0]) - 220) < 1e-6 or abs(abs(p[1]) - 120) < 1e-6))
    return g.cut(t, *[tslot(442.0, (0, y, 0), (1, 0, 0), top=60.0) for y in (-90.0, -30.0, 30.0, 90.0)])


def saddle():
    from machine_parts import chamfer, chamfered_rect, g
    s = g.polygon_prism(chamfered_rect(-200, -150, 400, 300, 12), 30.0)
    return chamfer(s, 3.0, lambda p: abs(p[2] - 30.0) < 1e-6 and (abs(abs(p[0]) - 200) < 1e-6 or abs(abs(p[1]) - 150) < 1e-6))


def magazine_stand():
    """From the floor up to the magazine post's arm (x -480..-440, y 230..250, z -80..380), a foot on the floor."""
    from machine_parts import chamfered_rect, g
    mx, _my = MAG
    post = g.box(mx - 20, 230, -80, 40, 20, 460)
    foot = g.polygon_prism(chamfered_rect(mx - 60, 200, 120, 90, 10), 15.0, g.T(0, 0, -80))
    rib = g.xform(g.polygon_prism([(250.0, -65.0), (290.0, -65.0), (250.0, 60.0)], 12.0),
                  g.Frame((mx - 6.0, 0, 0), (0, 1, 0), (1, 0, 0)))
    return g.fuse(post, foot, rib)


def magazine_guard():
    """A sheet-metal guard behind the magazine (r 310..313, z 320..450, from 60° to 200°: towards the column and away
    from the arm, so the pots stay in sight from the front), a rim on top and a bracket down to the stand at its back (z 300..370: below the tools that lie in the
    pots)."""
    from machine_parts import g
    mx, my = MAG
    wall = g.cut(g.cyl(GUARD_R + 3.0, 130.0, (mx, my, 320.0)), g.cyl(GUARD_R, 132.0, (mx, my, 319.0)))
    rim = g.cut(g.cyl(GUARD_R + 3.0, 4.0, (mx, my, 446.0)), g.cyl(GUARD_R - 12.0, 6.0, (mx, my, 445.0)))
    shell = g.fuse(wall, rim)
    far = 2 * GUARD_R
    fan = [(mx, my)] + [(mx + far * math.cos(math.radians(a)), my + far * math.sin(math.radians(a)))
                        for a in (-160.0, -120.0, -80.0, -40.0, 0.0, 30.0, 60.0)]
    shell = g.cut(shell, g.polygon_prism(fan, 200.0, g.T(0, 0, 280.0)))
    bracket = g.box(mx - 10, 250.0, 300.0, 20, GUARD_R - 250.0 + 1.0, 70.0)
    return g.fuse(shell, bracket)


def magazine_disc():
    """The disc (r 140, z 330..350) with a hub ring round the post (bore r 26) and a bolt circle on it."""
    from machine_parts import g
    from model_details import hex_prism
    mx, my = MAG
    disc = g.cyl(DISC_R, 20.0, (mx, my, 330))
    hub = g.cyl(48.0, 12.0, (mx, my, 350.0))
    heads = []
    for k in range(6):
        t = 2 * math.pi * (k + 0.5) / 6
        x, y = mx + 38.0 * math.cos(t), my + 38.0 * math.sin(t)
        heads.append(g.cut(g.cyl(5.0, 5.0, (x, y, 362.0)), g.xform(hex_prism(4.0, 4.0), g.T(x, y, 364.0))))
    return g.cut(g.fuse(disc, hub, *heads), g.cyl(26.0, 30.0, (mx, my, 349.0)))


def edge_clamp():
    """A toe clamp on the stock's +x face (x = 80) at y = 0, top z 78, its screw 18 mm out (x 98)."""
    from machine_parts import g, toe_clamp
    return g.xform(toe_clamp(80.0, 60.0, 78.0), g.Rot((0, 0, 1), -90.0))


def model():
    from machine_parts import (ALU, DARK, GREY, LIGHT_GREY, RAIL_STEEL, SCREW_BLACK, STEEL, asm, g, part, rail,
                               servo_motor, socket_screw)
    blue = (0.075, 0.267, 0.486)
    bed_p = part("BED", bed(), blue)
    column_p = part("COLUMN", column(), blue)
    rail_z = part("LINEAR RAIL Z", rail(400.0), RAIL_STEEL)
    saddle_p = part("SADDLE", saddle(), GREY)
    table_p = part("TABLE", table(), GREY)
    stock = part("STOCK 160x120x30", _box(-80, -60, 60, 160, 120, 30), ALU)
    clamp = part("EDGE CLAMP", edge_clamp(), DARK)
    screw = part("ISO 4762 M12 x 30 - 12.9", socket_screw(12, 30.0), SCREW_BLACK)
    head_p = part("HEAD", head(), blue)
    smotor = part("SPINDLE MOTOR", spindle_motor(), DARK)
    spindle = part("SPINDLE", _cyl(0, 0, GAUGE_Z, 45.0, 180.0), GREY)
    t1 = part("TOOL T1 BT30 FLAT D10", bt30_tool(T1_STICK, 5.0), STEEL)
    hx, hy = HUB
    housing = part("ATC HOUSING", _box(hx - 40, hy - 40, GAUGE_Z + 45, 80, 290, 60), blue)
    atc_motor = part("ATC MOTOR", servo_motor(70.0, 110.0), DARK)
    mx, my = MAG
    post = part("MAGAZINE POST", _fuse(_cyl(mx, my, 350, 25.0, 170.0), _box(mx - 20, my, 480, 40, 250, 40),
                                       _box(mx - 20, 230, 380, 40, 20, 140)), blue)
    stand = part("MAGAZINE STAND", magazine_stand(), blue)
    guard = part("MAGAZINE GUARD", magazine_guard(), LIGHT_GREY)
    mag_motor = part("MAGAZINE MOTOR", servo_motor(60.0, 100.0), DARK)
    arm = part("CHANGER ARM", changer_arm(), DARK)
    disc = part("MAGAZINE DISC", magazine_disc(), GREY)
    pot_p = part("POT", pot(), DARK)
    t2 = part("TOOL T2 BT30 BALL D8", bt30_tool(T2_STICK, 4.0, ball=True), STEEL)

    clamps = [(clamp, g.T(0, y, 0) @ g.Rot((0, 0, 1), a)) for y in (-30.0, 30.0) for a in (0.0, 180.0)]
    screws = [(screw, (x, y, 78.0)) for x in (-98.0, 98.0) for y in (-30.0, 30.0)]
    x_asm = asm("X.ASM", table_p, stock, *clamps, *screws)
    y_asm = asm("Y.ASM", saddle_p, x_asm)
    z_asm = asm("Z.ASM", head_p, (smotor, (0.0, 150.0, 522.0)), spindle, (t1, (0.0, 0.0, GAUGE_Z - T1_STICK - BT30_GAUGE)))
    arm_asm = asm("ARM.ASM", arm)
    pots = [(pot_p, g.Rot((0, 0, 1), 360.0 * k / POTS, (mx, my, 0))) for k in range(POTS)]
    # T2 in pot 2: lying radially, tip outwards, its gauge line at the pot's mouth
    m2 = (g.Rot((0, 0, 1), 360.0 / POTS, (mx, my, 0)) @ g.T(mx + POT_R + T2_STICK + BT30_GAUGE, my, POT_Z)
          @ g.Rot((0, 1, 0), -90.0))
    mag = asm("MAGAZINE.ASM", disc, *pots, (t2, m2))
    rz = [(rail_z, g.Frame((x, COL_FRONT, 150.0), (-1, 0, 0), (0, 0, 1))) for x in RAILS_Z]
    return asm("TEST.ATC", bed_p, column_p, *rz, y_asm, z_asm, housing, (atc_motor, (hx, hy, GAUGE_Z + 105.0)),
               post, stand, guard, (mag_motor, (mx, my, 520.0)), arm_asm, mag)


def build(path: str) -> None:
    from machine_parts import write
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_atc.step")
    print("written")
