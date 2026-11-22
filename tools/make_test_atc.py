"""Write the test mill with a double-arm tool changer as a STEP assembly (task 0064; task 0250: the vertical machining
centre of make_test_mill.py – travels X 1000 x Y 500 x Z 500, BT40 – with a double-arm changer and a side-mounted
disc magazine of 24 pots beside its column).

Nothing of a real machine: all sizes in mm, Z up, the coordinates of make_test_mill.py (the floor at z -900, the
table's top at z 30). The table moves along X on the saddle, the saddle along Y, the head along Z on the fixed column.
The CAD pose is the change position: the head HEAD_UP above its place on the test mill, the spindle's gauge line (its
nose) at z = GAUGE_Z on the axis x = 0, y = 0.

TEST.ATC
  BED, COLUMN, CHIP TRAY …  the VMC of make_test_mill.py (fixed)
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE, WAY COVER …
    X.ASM                   moves along X
      TABLE                 1200 x 500, T-slots at y 0 and +/-78 (the clamps' screws)
      STOCK 160x120x30      x -80..80, y -60..60, z 30..60, held by four EDGE CLAMPs
  Z.ASM                     moves along Z (in the CAD pose HEAD_UP = 450 above the test mill's)
    SPINDLE, SPINDLE HOUSING, SPINDLE MOTOR
    TOOL T1 BT40 FLAT D10   BT40 holder + flat end mill Ø10, stick-out 40: gauge length 100, its tip at (0, 0, 480)
  ATC HOUSING               fixed: the arm's gearbox over its hub (x -300..-170) and a beam back to the column's front
  ATC MOTOR                 on the housing
  ARM.ASM
    CHANGER ARM             hub (round, Ø80) on the axis x = -230, y = 0, vertical; a bar (z 555..577, 3 mm under the
                            spindle's nose) with a U-shaped claw at each end (round inside, Ø64.5, round a BT40 flange
                            Ø63.5); the claw's open side is cut along the ring round the hub the flange sweeps when the
                            arm turns in. In the CAD it is at rest, along Y; turned +90° about +Z its claws are round
                            x = 0 (the spindle) and x = -460 (the station)
  MAGAZINE STAND, MAGAZINE BEAM, MAGAZINE POST   fixed: a column on the floor behind the chip tray beside the machine's
                            column, a beam forward over the magazine, the post down into its middle
  MAGAZINE GUARD            fixed: a sheet-metal guard round the back and the left of the magazine
  MAGAZINE MOTOR            on the beam over the post
  MAGAZINE.ASM              turns about the vertical axis x = -880, y = 0
    MAGAZINE DISC           Ø750, z 590..610, a hub ring round the post
    HINGE CLEVIS            24 of the same part on the disc, round each pot's hinge pin
    POT                     24 of the same part, one every 15° counter-clockwise from +X (pot 1 at the station): a
                            sleeve lying radially (the tool points outward), its mouth (the gauge line) at radius 420,
                            z = 700; it tips down 90° about a hinge pin (round, along the tangent) at radius 360, z = 640:
                            tipped, the station pot's mouth is at (-460, 0, 580), the tool hanging down
    TOOL T2 BT40 BALL D8    in pot 2 (BT40 + ball end mill Ø8, stick-out 35, gauge length 95)

Nothing touches in the CAD pose, with the arm at rest and gripping, pulled down and turned, the station pot tipped,
the table at every corner of X and Y and the head anywhere in Z above the tool reaching the table (checked with
OpenCascade when the model was made).

usage: python make_test_atc.py out.step
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_test_mill as mill  # noqa: E402
from machine_parts import (ALU, BLUE, DARK, LIGHT_GREY, asm, bt40_holder_with_end_mill, chamfer,  # noqa: E402
                           chamfered_rect, g, part, servo_motor, write)

HEAD_UP = 450.0                     # the head in the change position, above its place on the test mill (Z travel 480)
GAUGE_Z = mill.NOSE + HEAD_UP       # the spindle's nose (gauge line) in the CAD pose: 580
HUB = (-230.0, 0.0)                 # the arm's axis
GRIP_R = 230.0
STATION_X = HUB[0] - GRIP_R         # -460: the tipped station pot's mouth
POTS = 24
POT_R = 420.0                       # the pot's mouth (gauge line), from the magazine's axis
HINGE_R = 360.0
HINGE_Z = GAUGE_Z + 60.0            # 640: tipped 90°, the mouth comes down to the gauge line at radius 360 + 60
POT_Z = HINGE_Z + (POT_R - HINGE_R)  # 700
MAG = (STATION_X - POT_R, 0.0)      # (-880, 0): the magazine's axis
DISC_R = 375.0                      # inside a tipped pot's sleeve (r 384..456)
DISC_TOP = 610.0
SLEEVE = (100.0, 36.0, 24.0)        # the pot's sleeve: length, outer radius, bore (the BT40 taper and pull stud)
CLAW = (32.25, 46.0, 22.0)          # the arm's claw: inner radius (BT40 flange 31.75), outer radius, thickness
CLAW_Z = GAUGE_Z - 3.0 - CLAW[2]    # the arm's bar z 555..577: round the flange (z 554..580), 3 mm under the nose
HUB_R = 40.0
T1_STICK, T2_STICK = 40.0, 35.0
BT40_GAUGE = 60.0                   # from the holder's nose to its gauge line (core/tools.py HOLDER_SIZES)
STOCK = (-80.0, -60.0, mill.TABLE_TOP, 160.0, 120.0, 30.0)
GUARD_R = 560.0                     # the magazine guard's inside (the longest tool's tip lies at r 530)
POST_R = 50.0
BEAM_Z = (930.0, 990.0)             # the magazine beam
STAND = (-930.0, 780.0, 100.0, 80.0)  # x0, y0, dx, dy: the magazine's stand (behind the chip tray, beside the column)
ATC_BOX = (-300.0, -170.0, -70.0, 70.0, 650.0, 830.0)   # the arm's gearbox: x0, x1, y0, y1, z0, z1
ATC_BEAM = (-330.0, -270.0, 760.0)  # the beam back to the column: x0, x1, z0 (top: ATC_BOX's)


def bt40_tool(stick: float, d: float, ball: bool = False):
    """A BT40 holder and its cutter, the tip at the origin, along +Z: the gauge line ``stick`` + 60 above it."""
    return bt40_holder_with_end_mill(stick, stick + BT40_GAUGE, d, ball=ball)


def changer_arm():
    """The arm in its grip pose (claws round x = 0 and x = STATION_X), then turned back -90° about its hub to rest."""
    hx, hy = HUB
    ri, ro, h = CLAW
    z0 = CLAW_Z
    bar = g.box(STATION_X, -22.0, z0, -STATION_X, 44.0, h)
    hub = g.cyl(HUB_R, GAUGE_Z + 65.0 - z0, (hx, hy, z0))
    shapes = [bar, hub]
    ends = ((0.0, 1.0), (STATION_X, -1.0))
    for cx, opening in ends:
        ring = g.cut(g.cyl(ro, h, (cx, 0, z0)), g.cyl(ri, h + 2, (cx, 0, z0 - 1)))
        # open towards the way the claw moves when the arm turns +Z into the tools (U-shaped claw)
        y0 = 0.0 if opening > 0 else -(ro + 4.0)
        ring = g.cut(ring, g.box(cx - ri, y0, z0 - 1, 2 * ri, ro + 4.0, h + 2))
        shapes.append(ring)
    arm = g.fuse(*shapes)
    arm = g.cut(arm, *[g.cyl(ri, h + 2, (cx, 0, z0 - 1)) for cx, _o in ends])
    # the way in: the arm turns about its hub, so the flange sweeps a ring round the hub (radius GRIP_R +/- ri);
    # nothing of the claw or the bar may stand in that ring on the open side (task 0067)
    ring = g.cut(g.cyl(GRIP_R + ri, h + 2, (hx, hy, z0 - 1)), g.cyl(GRIP_R - ri, h + 4, (hx, hy, z0 - 2)))
    for cx, opening in ends:
        y0 = 0.0 if opening > 0 else -(ro + 10.0)
        way = g.common(ring, g.box(cx - ro - 4.0, y0, z0 - 1, 2 * (ro + 4.0), ro + 10.0, h + 2))
        arm = g.cut(arm, way)
    return g.xform(arm, g.Rot((0, 0, 1), -90.0, (hx, hy, 0)))


def pot():
    """Pot 1 at the station (towards +X from the magazine's axis), not tipped: a sleeve lying along X, its mouth at
    the gauge point, a block down to the hinge pin."""
    mx, my = MAG
    mouth = mx + POT_R
    length, ro, ri = SLEEVE
    sleeve = g.cut(g.cyl(ro, length, (mouth - length, my, POT_Z), (1, 0, 0)),
                   g.cyl(ri, length, (mouth - length + 4.0, my, POT_Z), (1, 0, 0)))
    lip = g.cut(g.cyl(ro + 3.0, 6.0, (mouth - 6.0, my, POT_Z), (1, 0, 0)),
                g.cyl(ri, 8.0, (mouth - 7.0, my, POT_Z), (1, 0, 0)))
    hx = mx + HINGE_R
    block = g.box(hx - 20.0, my - 20.0, HINGE_Z, 40.0, 40.0, POT_Z - ro - HINGE_Z + 2.0)
    pin = g.cyl(8.0, 68.0, (hx, my - 34.0, HINGE_Z), (0, 1, 0))     # its ends 2 mm out of the clevis: clickable
    return g.fuse(sleeve, lip, block, pin)


def magazine_disc():
    """The disc (r 375, z 590..610) with a hub ring round the post (bore r 51) and a bolt circle."""
    from model_details import hex_prism
    mx, my = MAG
    disc = g.cyl(DISC_R, 20.0, (mx, my, DISC_TOP - 20.0))
    hub = g.cyl(90.0, 16.0, (mx, my, DISC_TOP))
    heads = []
    for k in range(8):
        t = 2 * math.pi * (k + 0.5) / 8
        x, y = mx + 72.0 * math.cos(t), my + 72.0 * math.sin(t)
        heads.append(g.cut(g.cyl(6.0, 6.0, (x, y, DISC_TOP + 16.0)), g.xform(hex_prism(5.0, 5.0),
                                                                              g.T(x, y, DISC_TOP + 18.0))))
    return g.cut(g.fuse(disc, hub, *heads), g.cyl(POST_R + 1.0, 60.0, (mx, my, DISC_TOP - 30.0)))


def clevis():
    """The hinge clevis of pot 1 on the disc: a base (z 610..616) and two cheeks beside the pot's block (|y| 22..32,
    up to z 652) with holes round its pin; one part, 24 places."""
    mx, my = MAG
    x0 = mx + HINGE_R - 15.0
    base = g.box(x0, my - 32.0, DISC_TOP, 30.0, 64.0, 6.0)
    cheeks = [g.box(x0, my + y0, DISC_TOP, 30.0, 10.0, HINGE_Z + 12.0 - DISC_TOP) for y0 in (-32.0, 22.0)]
    shape = g.fuse(base, *cheeks)
    return g.cut(shape, g.cyl(8.5, 80.0, (mx + HINGE_R, my - 40.0, HINGE_Z), (0, 1, 0)))


def magazine_post():
    """The post down from the beam into the disc's hub (r 50) with a flange under the beam."""
    mx, my = MAG
    post = g.cyl(POST_R, BEAM_Z[0] - (DISC_TOP - 15.0), (mx, my, DISC_TOP - 15.0))
    flange = g.cyl(80.0, 14.0, (mx, my, BEAM_Z[0] - 14.0))
    return g.fuse(post, flange)


def magazine_stand():
    """A box column from the floor up to the beam behind the chip tray, on a foot, with a rib."""
    x0, y0, dx, dy = STAND
    body = g.polygon_prism(chamfered_rect(x0, y0, dx, dy, 10.0), BEAM_Z[0] - mill.FLOOR, g.T(0, 0, mill.FLOOR))
    foot = g.polygon_prism(chamfered_rect(x0 - 40.0, y0 - 40.0, dx + 80.0, dy + 80.0, 12.0), 20.0,
                           g.T(0, 0, mill.FLOOR))
    rib = g.xform(g.polygon_prism([(y0 + dy - 2.0, mill.FLOOR + 20.0), (y0 + dy + 140.0, mill.FLOOR + 20.0),
                                   (y0 + dy - 2.0, mill.FLOOR + 700.0)], 16.0),
                  g.Frame((x0 + dx / 2 - 8.0, 0, 0), (0, 1, 0), (1, 0, 0)))
    return g.fuse(body, foot, rib)


def magazine_beam():
    """From the stand forward over the magazine's post: x -910..-850, z 930..990, with chamfered edges."""
    mx, my = MAG
    x0, y0, dx, dy = STAND
    beam = g.polygon_prism(chamfered_rect(mx - 30.0, my - 110.0, 60.0, y0 + dy - (my - 110.0), 8.0),
                           BEAM_Z[1] - BEAM_Z[0], g.T(0, 0, BEAM_Z[0]))
    return chamfer(beam, 4.0, lambda p: abs(p[2] - BEAM_Z[1]) < 1e-6)


def magazine_guard():
    """A sheet-metal guard round the magazine (r 560..563, z 650..770) from 60° to 200° (behind it and on its left,
    away from the arm, so the pots stay in sight from the front), a rim on top and a bracket back to the stand."""
    mx, my = MAG
    wall = g.cut(g.cyl(GUARD_R + 3.0, 120.0, (mx, my, 650.0)), g.cyl(GUARD_R, 122.0, (mx, my, 649.0)))
    rim = g.cut(g.cyl(GUARD_R + 3.0, 4.0, (mx, my, 766.0)), g.cyl(GUARD_R - 14.0, 6.0, (mx, my, 765.0)))
    shell = g.fuse(wall, rim)
    far = 2 * GUARD_R
    fan = [(mx, my)] + [(mx + far * math.cos(math.radians(a)), my + far * math.sin(math.radians(a)))
                        for a in (-160.0, -120.0, -80.0, -40.0, 0.0, 30.0, 60.0)]
    shell = g.cut(shell, g.polygon_prism(fan, 200.0, g.T(0, 0, 600.0)))
    bracket = g.box(mx - 10.0, my + GUARD_R + 1.0, 690.0, 20.0, STAND[1] - (my + GUARD_R + 1.0) + 1.0, 70.0)
    return g.fuse(shell, bracket)


def atc_housing():
    """The arm's gearbox over its hub (z 650..830) and a beam back to the column's front (x -330..-270)."""
    x0, x1, y0, y1, z0, z1 = ATC_BOX
    box = g.polygon_prism(chamfered_rect(x0, y0, x1 - x0, y1 - y0, 12.0), z1 - z0, g.T(0, 0, z0))
    box = chamfer(box, 4.0, lambda p: abs(p[2] - z1) < 1e-6)
    bx0, bx1, bz0 = ATC_BEAM
    beam = g.polygon_prism(chamfered_rect(bx0, 0.0, bx1 - bx0, mill.COL_FRONT, 6.0), z1 - bz0, g.T(0, 0, bz0))
    plate = g.box(bx0 - 30.0, mill.COL_FRONT - 20.0, bz0 - 60.0, bx1 - bx0 + 60.0, 20.0, z1 - bz0 + 120.0)
    return g.fuse(box, beam, plate)


def model():
    from machine_parts import STEEL
    mx, my = MAG
    hx, hy = HUB
    sx, sy, sz, sdx, sdy, sdz = STOCK
    stock = part("STOCK 160x120x30", g.box(sx, sy, sz, sdx, sdy, sdz), ALU)
    t1 = part("TOOL T1 BT40 FLAT D10", bt40_tool(T1_STICK, 10.0), STEEL)
    housing = part("ATC HOUSING", atc_housing(), BLUE)
    atc_motor = part("ATC MOTOR", servo_motor(80.0, 120.0), DARK)
    post = part("MAGAZINE POST", magazine_post(), BLUE)
    beam = part("MAGAZINE BEAM", magazine_beam(), BLUE)
    stand = part("MAGAZINE STAND", magazine_stand(), BLUE)
    guard = part("MAGAZINE GUARD", magazine_guard(), LIGHT_GREY)
    mag_motor = part("MAGAZINE MOTOR", servo_motor(80.0, 120.0), DARK)
    arm = part("CHANGER ARM", changer_arm(), DARK)
    disc = part("MAGAZINE DISC", magazine_disc(), (0.6, 0.62, 0.64))
    pot_p = part("POT", pot(), DARK)
    clevis_p = part("HINGE CLEVIS", clevis(), (0.6, 0.62, 0.64))
    t2 = part("TOOL T2 BT40 BALL D8", bt40_tool(T2_STICK, 8.0, ball=True), STEEL)

    # T1 in the spindle: its gauge line at the nose (Z.ASM's own coordinates: the nose at mill.NOSE)
    tools = [(t1, (0.0, 0.0, mill.NOSE - T1_STICK - BT40_GAUGE))]
    arm_asm = asm("ARM.ASM", arm)
    pots = [(pot_p, g.Rot((0, 0, 1), 360.0 * k / POTS, (mx, my, 0))) for k in range(POTS)]
    # T2 in pot 2: lying radially, tip outwards, its gauge line at the pot's mouth
    m2 = (g.Rot((0, 0, 1), 360.0 / POTS, (mx, my, 0)) @ g.T(mx + POT_R + T2_STICK + BT40_GAUGE, my, POT_Z)
          @ g.Rot((0, 1, 0), -90.0))
    clevises = [(clevis_p, g.Rot((0, 0, 1), 360.0 * k / POTS, (mx, my, 0))) for k in range(POTS)]
    mag = asm("MAGAZINE.ASM", disc, *clevises, *pots, (t2, m2))
    extra = [housing, (atc_motor, (hx, hy, ATC_BOX[5])), stand, beam, post, guard,
             (mag_motor, (mx, my, BEAM_Z[1])), arm_asm, mag]
    return mill.machine("TEST.ATC", stock, None, STOCK, tools, head_up=HEAD_UP, extra=extra)


def build(path: str) -> None:
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_atc.step")
    print("written")
