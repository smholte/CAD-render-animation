"""Write the test mill – an invented vertical machining centre (VMC) – as a STEP assembly for the milling tests (task
0027; more detail: task 0122; task 0249: the small mill became a larger VMC, travels X 1000 x Y 500 x Z 500, table
1200 x 500, BT40 – nothing of a real make). All sizes in mm, Z up; the spindle's axis is x = 0, y = 0.

The common VMC layout: a fixed column behind the table, the saddle moves along Y on the bed, the table along X on the
saddle, the head along Z on the column. The stock, the finished part, the tools and the clamps lie where they lay on
the small mill (the stock x/y -100..100, z 30..70; the table's top at z 30): programs, work zero and cut checks keep
their numbers. The floor is z -900 (the bed's and the coolant tank's bottoms): the table's top is 930 above it.

TEST.MILL
  BED                       cast bed x -480..480, y -330..1230, z -900..-322 (top), chamfers, a recessed band, feet
  COLUMN                    on the bed's back: x -450..450, y 680..1180 (its front 680 behind the spindle), up to
                            z 1300, hollow from the top, ribs at its back and sides
  LINEAR RAIL Y             x2, on the bed's top at x +/-330, y -300..580
  LINEAR RAIL Z             x2, on the column's front at x +/-220, z -200..1300
  SERVO MOTOR Y             on the bed's back face; SERVO MOTOR Z on the column's top
  CHIP TRAY                 one sheet-steel solid round the bed (task 0251's drain list): x -1200..1200,
                            y -388..675, open round the bed (a U: two wings and a front channel), its floor falls 2°
                            to the front and 1.5° to a valley at x 1160 (z -520 at the drain), walls up to z -250, an
                            upstand round the bed up to z -340 (18 below the bed's top: coolant on the bed runs off)
  COOLANT DRAIN             under the Ø50 hole at the tray's lowest point (1160, -355): a flange under the floor and a
                            pipe down into the tank (nothing stands above the floor)
  COOLANT TANK              a box on the floor under the drain
  WAY COVER Y FRONT 0..5    telescopic way cover in front of the saddle: section 0 fixed over the bed's front, 1..5
                            laid out for the app's way covers (section k follows k/6 of Y), 6 on the saddle;
  WAY COVER Y BACK 0..4     behind it the same with section 0 against the column (k/5; 5 on the saddle). Gable roofs
                            (2°) shed coolant to the bed's sides
  Y.ASM                     moves along Y (a slide joint in the tests)
    SADDLE                  x -450..450, y -150..150, z -300..-82 with its guide blocks (Y below, X above)
    WAY COVER Y FRONT 6, WAY COVER Y BACK 5   the covers' sections fixed to the saddle
    X.ASM                   moves along X (the tests' joint points to -x: a positive value moves the tool to +x on
                            the work, as the machine's X+)
      TABLE                 1200 x 500, z -60..30, three T-slots (opening 18, open at both ends) along X at y 0 and
                            +/-118, chamfered edges
      LINEAR RAIL X         x2, under the table at y +/-125 (they ride with it; the blocks sit on the saddle)
      SERVO MOTOR X         at the table's right end
      EDGE CLAMP            x4, low toe clamps (top z 48) pushing on the stock's front and back faces at x +/-60
      ISO 4762 M12 x 30 - 12.9   x4, the clamps' screws, down into the outer T-slots
      STOCK 200x200x40      the workpiece: box 200 x 200 x 40, x/y -100..100, z 30..70
      FINISHED PART         the stock with a pocket 100 x 60 x 10 (corners R5) and a hole Ø20 x 15
                            in the middle (for "finish at the CAD part"); same place as the stock
  Z.ASM                     moves along Z
    SPINDLE                 BT40 spindle: a shaft Ø80, its nose at z 130 (the gauge line, its lowest point)
    SPINDLE HOUSING         the head: the cartridge Ø150 round the spindle with its nose collar Ø116 (z 152..162), the head casting up to z 720, its back
                            plate on four guide blocks round the Z rails, and a bracket holding the ball mill (its
                            lowest point z 112)
    SPINDLE MOTOR           on the head, z 720..920
    END MILL D10            flat end mill Ø10 x 40, tip at x = 0, y = 0, z = 90 (20 mm above the stock)
    BALL MILL D6            ball end mill Ø6 x 30 (cylinder + half sphere), tip at x = 120, z = 90

Nothing of the head comes below z 112 in the CAD pose. The travels (``TRAVEL``): X -500..500, Y -110..390 (500 mm;
the spindle reaches 140 mm past the table's front edge, so the doors of the enclosure stand 380 mm in front of it),
Z -20..480; nothing touches anywhere in them (checked with every axis at both ends, doors open and shut). The
enclosure with its sliding doors: make_test_mill_cabinet.py.

usage: python make_test_mill.py out.step
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_parts import (ALU, BLUE, COVER_GREY, DARK, GREY, RAIL_STEEL, SCREW_BLACK, TRAY_GREY,  # noqa: E402
                           asm, block_on, chamfer, chamfered_rect, g, part, rail_along, servo_motor, socket_screw,
                           toe_clamp, tslot, way_cover_section, write)

STOCK = (-100.0, -100.0, 30.0, 200.0, 200.0, 40.0)      # x, y, z, dx, dy, dz
FLAT_TIP = (0.0, 0.0, 90.0)
BALL_TIP = (120.0, 0.0, 90.0)
POCKET = (-50.0, -30.0, 100.0, 60.0, 10.0, 5.0)          # x, y, dx, dy, depth, corner radius (from the top)
HOLE = (70.0, 50.0, 10.0, 15.0)                          # x, y, radius, depth
TABLE_TOP = 30.0
TABLE = (-600.0, -250.0, 1200.0, 500.0, -60.0)           # x0, y0, dx, dy, bottom z (top: TABLE_TOP)
FLOOR = -900.0                                           # the bed's bottom: the floor
BED_TOP = -322.0                                         # the Y rails' feet
BED = (-480.0, -330.0, 960.0, 1560.0)                    # x0, y0, dx, dy
COL_FRONT = 680.0                                        # the column's front face (y): the Z rails' feet
COLUMN = (-450.0, 500.0, 1300.0)                         # x0, depth, top z
SADDLE = (-450.0, -150.0, 900.0, 300.0, -300.0, -82.0)   # x0, y0, dx, dy, bottom z, top z
RAILS_Y = (-330.0, 330.0)                                # x of the Y rails
RAILS_X = (-125.0, 125.0)                                # y of the X rails (under the table)
RAILS_Z = (-220.0, 220.0)                                # x of the Z rails
BLOCKS_X = (-60.0, 60.0)                                 # x of the X blocks on the saddle (the rails ride on them)
BLOCKS_Y = (-100.0, 100.0)                               # y of the Y blocks under the saddle
HEAD_BACK = COL_FRONT - 22.0                             # the head's back plate on its blocks (machine_parts BLOCK_BACK)
NOSE = 130.0                                             # the spindle's nose (BT40 gauge line)
CLAMP_TOP = 48.0                                         # the edge clamps' top (z)
# Y: 500 mm, the spindle reaching 140 mm past the table's front edge (the travel is longer than the table is deep on
# many VMCs) and 110 mm in front of the stock's middle: the doors' panel stands 380 mm in front of the spindle, so a
# person standing at the doors reaches it (blender/tc_person.py)
TRAVEL = {"X": (-500.0, 500.0), "Y": (-110.0, 390.0), "Z": (-20.0, 480.0)}
# the chip tray (task 0251's drain list): floor falls 2° to the front, 1.5° to the valley at the drain's x
TRAY = (-1200.0, 1200.0, -388.0, 675.0, -250.0, 5.0)     # x0, x1, y0, y1, walls' top z, sheet
TRAY_HOLE = (-490.0, 490.0, -340.0)                      # the bed's opening: x0, x1, its front y (open to the back)
DRAIN = (1160.0, -355.0, -520.0, 25.0)                   # x, y, the floor's top z there, radius (Ø50)
SLOPE_Y, SLOPE_X = 2.0, 1.5                              # degrees
UPSTAND_TOP = -340.0
TANK = (700.0, -380.0, 1180.0, 120.0, -580.0)             # x0, y0, x1, y1, top z (on the floor)
# way covers: a fixed section + moving ones on each side; section k of N follows k/N of Y, the last one is on the
# saddle (N counts it)
COVER_FRONT = (-375.0, 110.0, 6)                         # the fixed end (y), each section's length, N
COVER_BACK = (COL_FRONT, 135.0, 5)
COVER_W, COVER_TOP, COVER_STEP = 400.0, -264.0, 6.0      # outer section's half width, roof edge z; each next one in

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
# the machine (shared with make_test_toolpath.py and make_test_mill_cabinet.py)
# ---------------------------------------------------------------------------

def bed():
    x0, y0, dx, dy = BED
    h = BED_TOP - FLOOR
    b = g.polygon_prism(chamfered_rect(x0, y0, dx, dy, 30), h, g.T(0, 0, FLOOR))
    b = chamfer(b, 8.0, lambda p: abs(p[2] - BED_TOP) < 1e-6)
    band = g.cut(g.polygon_prism(chamfered_rect(x0 - 10, y0 - 10, dx + 20, dy + 20, 35), 60.0, g.T(0, 0, FLOOR + 90)),
                 g.polygon_prism(chamfered_rect(x0 + 6, y0 + 6, dx - 12, dy - 12, 27), 62.0, g.T(0, 0, FLOOR + 89)))
    feet = [g.box(x - 60.0, y - 60.0, FLOOR, 120.0, 120.0, 20.0) for x in (x0 - 40.0, x0 + dx + 40.0)
            for y in (y0 + 150.0, y0 + dy - 150.0)]
    pads = [g.box(x - (20.0 if x > 0 else 40.0), y - 40.0, FLOOR + 20.0, 60.0, 80.0, 120.0)
            for x in (x0 - 40.0, x0 + dx + 40.0) for y in (y0 + 150.0, y0 + dy - 150.0)]
    return g.fuse(g.cut(b, band), *feet, *pads)


def column():
    x0, depth, top = COLUMN
    body = g.polygon_prism(chamfered_rect(x0, COL_FRONT, -2 * x0, depth, 40), top - BED_TOP, g.T(0, 0, BED_TOP))
    body = chamfer(body, 10.0, lambda p: abs(p[2] - top) < 1e-6)
    pocket = g.box(-300.0, COL_FRONT + 120.0, 0.0, 600.0, 260.0, top + 1.0)          # hollow casting from the top
    body = g.cut(body, pocket)
    ribs = []
    yb = COL_FRONT + depth
    for x in (-330.0, -10.0, 310.0):                  # tapered ribs at the back: local (u, v) = (y, z), along x
        rib = g.polygon_prism([(yb - 2.0, BED_TOP), (yb + 160.0, BED_TOP), (yb + 160.0, BED_TOP + 80.0),
                               (yb - 2.0, top - 220.0)], 20.0)
        ribs.append(g.xform(rib, g.Frame((x, 0, 0), (0, 1, 0), (1, 0, 0))))
    for x in (x0 - 18.0, -x0 - 2.0):                  # side ribs, along y
        rib = g.polygon_prism([(BED_TOP, -(COL_FRONT + 60.0)), (BED_TOP + 500.0, -(yb - 40.0)), (BED_TOP, -(yb - 40.0))],
                               20.0)              # local (u, v) = (z, -y)
        ribs.append(g.xform(rib, g.Frame((x, 0, 0), (0, 0, 1), (1, 0, 0))))
    cap = g.polygon_prism(chamfered_rect(-300.0, COL_FRONT + 120.0, 600.0, 260.0, 10.0), 12.0, g.T(0, 0, top - 12.0))
    return g.fuse(body, cap, *ribs)


def saddle():
    x0, y0, dx, dy, zb, zt = SADDLE
    s = g.polygon_prism(chamfered_rect(x0, y0, dx, dy, 25), zt - zb, g.T(0, 0, zb))
    s = chamfer(s, 6.0, lambda p: abs(p[2] - zt) < 1e-6)
    s = g.cut(s, *[g.box(x, y0 - 1.0, zb + 40.0, 220.0, 40.0, 110.0) for x in (-370.0, 150.0)],    # cored sides
              *[g.box(x, -y0 - 39.0, zb + 40.0, 220.0, 40.0, 110.0) for x in (-370.0, 150.0)])
    blocks = [block_on(60.0, (x, y, BED_TOP), (0, 1, 0), (0, 0, 1)) for x in RAILS_Y for y in BLOCKS_Y]
    blocks += [block_on(50.0, (x, y, TABLE[4]), (1, 0, 0), (0, 0, -1)) for x in BLOCKS_X for y in RAILS_X]
    nut = g.box(-50.0, -60.0, zt - 1.0, 100.0, 120.0, 1.0)   # (flat: the X screw's nut seat)
    return g.fuse(s, nut, *blocks)


def table(stock):
    """1200 x 500, three T-slots along X (opening 18, open at both ends): one under the stock's middle, two beside it
    for the clamps' screws."""
    x0, y0, dx, dy, zb = TABLE
    t = g.polygon_prism(chamfered_rect(x0, y0, dx, dy, 12), TABLE_TOP - zb, g.T(0, 0, zb))
    t = chamfer(t, 2.0, lambda p: abs(p[2] - TABLE_TOP) < 1e-6 and (abs(abs(p[0]) - dx / 2) < 1e-6 or
                                                                      abs(abs(p[1]) - dy / 2) < 1e-6))
    ys = (0.0, -clamp_screw_y(stock), clamp_screw_y(stock))
    slots = [tslot(dx + 30.0, (0, y, 0), (1, 0, 0), top=TABLE_TOP, open_w=18.0, wide=30.0, depth=32.0) for y in ys]
    return g.cut(t, *slots)

def clamp_screw_y(stock) -> float:
    return stock[1] + stock[4] + 18.0                   # 18 mm outside the stock's back face


def edge_clamp(stock):
    """A toe clamp for the stock's back face (+y), at x = 0; its nose on the face, its screw 18 mm out."""
    return toe_clamp(stock[1] + stock[4], TABLE_TOP, CLAMP_TOP)


def housing(ball_bracket: bool):
    """The head (Z.ASM): the cartridge Ø150 round the spindle (bore Ø100, z 160..380), the head casting above it, its
    back plate on four guide blocks round the Z rails, and the ball mill's bracket (its sleeve down to z 112)."""
    plate = g.polygon_prism(chamfered_rect(-260.0, HEAD_BACK - 40.0, 520.0, 40.0, 8.0), 520.0, g.T(0, 0, 280.0))
    blocks = [block_on(70.0, (x, COL_FRONT, z), (0, 0, 1), (0, -1, 0)) for x in RAILS_Z for z in (330.0, 730.0)]
    body = g.polygon_prism(chamfered_rect(-150.0, -100.0, 300.0, HEAD_BACK - 40.0 + 100.0 + 1.0, 30.0), 400.0,
                           g.T(0, 0, 320.0))
    body = chamfer(body, 12.0, lambda p: abs(p[2] - 720.0) < 1e-6)
    nose_rib = g.xform(g.polygon_prism([(-60.0, 320.0), (-60.0, 380.0), (HEAD_BACK - 40.0, 380.0),
                                        (HEAD_BACK - 40.0, 280.0)], 40.0), g.Frame((-20.0, 0, 0), (0, 1, 0), (1, 0, 0)))
    cartridge = g.revolve([(0.0, 160.0), (68.0, 160.0), (75.0, 167.0), (75.0, 380.0), (0.0, 380.0)])
    collar = g.revolve([(43.0, NOSE + 22.0), (55.0, NOSE + 22.0), (58.0, NOSE + 25.0), (58.0, 162.0), (43.0, 162.0)])
    parts = [plate, *blocks, body, nose_rib, cartridge, collar]
    if ball_bracket:
        bx = BALL_TIP[0]
        parts += [g.polygon_prism(chamfered_rect(60, -12, bx - 60 + 12, 24, 5), 16.0, g.T(0, 0, 176)),
                  g.cyl(8.0, 192.0 - 112.0, (bx, 0, 112.0))]
    shape = g.fuse(*parts)
    cuts = [g.cyl(50.0, 230.0, (0, 0, 162))]
    if ball_bracket:
        cuts.append(g.cyl(3.0, 40.0, (BALL_TIP[0], 0, 100.0)))
    return g.cut(shape, *cuts)


def spindle():
    """The BT40 spindle: a shaft Ø80, its nose at z 130 (the gauge line, its lowest point: the air nozzle read from
    its shape blows from there; the coolant ring of the automatic hoses sits round it), up into the cartridge."""
    return g.revolve([(0.0, NOSE), (38.0, NOSE), (40.0, NOSE + 2.0), (40.0, 375.0), (0.0, 375.0)])


def spindle_motor():
    prof = [(0.0, 720.0), (95.0, 720.0), (95.0, 735.0), (85.0, 735.0), (85.0, 780.0), (89.0, 780.0), (89.0, 788.0),
            (85.0, 788.0), (85.0, 840.0), (89.0, 840.0), (89.0, 848.0), (85.0, 848.0), (85.0, 900.0),
            (76.0, 920.0), (0.0, 920.0)]
    return g.fuse(g.revolve(prof), g.box(-30, -118, 770, 60, 36, 60))


def tray():
    """The chip tray (task 0251): one solid round the bed. Its floor's top is the plane through the drain falling
    ``SLOPE_Y`` to the front and ``SLOPE_X`` towards the valley x = drain's x (two planes: a V to the drain); 5 mm
    sheet; outer walls up to ``TRAY[4]``, an upstand round the bed's opening up to ``UPSTAND_TOP``; the drain's hole."""
    import math
    x0, x1, y0, y1, wtop, t = TRAY
    hx0, hx1, hy0 = TRAY_HOLE
    xd, yd, zd, rd = DRAIN
    sy, sx = math.tan(math.radians(SLOPE_Y)), math.tan(math.radians(SLOPE_X))
    low = zd - 40.0                                     # below every point of the floor's underside

    def under(dirx):                                    # everything below the floor's plane on one side of the valley
        n = (dirx * sx, -sy, 1.0)                       # z = zd + sy (y - yd) + sx |x - xd|  ->  n . (p - d) <= 0
        big = g.box(-4000.0, -4000.0, -4000.0, 8000.0, 8000.0, 4000.0)
        return g.xform(big, g.Frame((xd, yd, zd), np.cross((0.0, 1.0, 0.0), n), n))

    def half(dirx, lift):                               # the half space below the floor (lift: its underside)
        u = under(dirx)
        side = g.box(xd if dirx > 0 else -4000.0, -4000.0, -4000.0, 4000.0 + (0.0 if dirx > 0 else xd), 8000.0, 8000.0)
        return g.xform(g.common(u, side), g.T(0, 0, lift))

    below_top = g.fuse(half(1.0, 0.0), half(-1.0, 0.0))
    below_bottom = g.fuse(half(1.0, -t), half(-1.0, -t))
    outline = g.box(x0, y0, low, x1 - x0, y1 - y0, wtop - low)
    hole = g.box(hx0, hy0, low - 1.0, hx1 - hx0, y1 - hy0 + 10.0, wtop - low + 2.0)
    floor = g.cut(g.common(g.cut(outline, hole), below_top), below_bottom)
    inner = g.box(x0 + t, y0 + t, low - 1.0, x1 - x0 - 2 * t, y1 - y0 - 2 * t, wtop - low + 2.0)
    walls = g.cut(outline, inner, below_bottom)
    up = g.cut(g.box(hx0 - t, hy0 - t, low, hx1 - hx0 + 2 * t, y1 - hy0 + t, UPSTAND_TOP - low), hole, below_bottom)
    shape = g.fuse(floor, walls, up)
    shape = g.cut(shape, g.box(hx0, y1 - t - 1.0, low - 1.0, hx1 - hx0, t + 2.0, wtop - low + 2.0))   # open at the back
    return g.cut(shape, g.cyl(rd, 100.0, (xd, yd, zd - 60.0)))


def drain():
    """The drain (task 0251): the Ø50 hole in the tray's floor is open; under it this part – a flange bolted under
    the floor and a pipe down into the tank (nothing stands above the floor: the coolant runs straight in)."""
    xd, yd, zd, rd = DRAIN
    top = zd - TRAY[5] - 2.0                          # just under the floor's underside all round the flange
    flange = g.cut(g.cyl(rd + 22.0, 6.0, (xd, yd, top - 6.0)), g.cyl(rd, 10.0, (xd, yd, top - 8.0)))
    pipe = g.cut(g.cyl(rd + 4.0, top - TANK[4] + 30.0, (xd, yd, TANK[4] - 30.0)),
                 g.cyl(rd, top - TANK[4] + 40.0, (xd, yd, TANK[4] - 35.0)))
    return g.fuse(flange, pipe)

def tank():
    x0, y0, x1, y1, top = TANK
    body = g.polygon_prism(chamfered_rect(x0, y0, x1 - x0, y1 - y0, 10.0), top - FLOOR, g.T(0, 0, FLOOR))
    lid = g.box(x0 + 40.0, y0 + 40.0, top, x1 - x0 - 80.0, y1 - y0 - 80.0, 6.0)
    return g.fuse(body, lid)


def cover_section(side: str, k: int):
    """Section k (0 fixed .. N on the saddle) of the front or back Y way cover, in the CAD pose (Y = 0)."""
    fixed, length, n = COVER_FRONT if side == "FRONT" else COVER_BACK
    face = SADDLE[1] if side == "FRONT" else SADDLE[1] + SADDLE[3]      # the saddle's face the cover meets
    e = (abs(face - fixed) - length) / n              # how far apart the sections' ends lie
    w = COVER_W - COVER_STEP * k
    top = COVER_TOP - COVER_STEP * k
    if side == "FRONT":                               # runs from the fixed end towards +y
        return way_cover_section(length, w, BED_TOP + 1.0, top, fixed + k * e, towards=1.0)
    return way_cover_section(length, w, BED_TOP + 1.0, top, fixed - k * e, towards=-1.0)


def travel_check():
    """The covers' sections at both ends of Y, worked out as the app's way covers move them (k/N): every section
    overlaps the next by at least 20 mm and the saddle never runs into section 0."""
    out = []
    for side, (fixed, length, n) in (("FRONT", COVER_FRONT), ("BACK", COVER_BACK)):
        face0 = SADDLE[1] if side == "FRONT" else SADDLE[1] + SADDLE[3]
        for y in TRAVEL["Y"]:
            span = abs(face0 + y - fixed)
            e = (span - length) / n
            if e < 0:
                out.append(f"{side} at Y {y}: the sections do not fit (span {span:.0f} < {length:.0f})")
            if length - e < 20.0:
                out.append(f"{side} at Y {y}: overlap {length - e:.0f} mm")
    return out

def machine(name: str, stock_part, finished, stock, tools, ball_bracket: bool = False, extra_head=()):
    """The VMC round a stock (x, y, z, dx, dy, dz) and its finished part; ``tools``: [(Part, (x, y, z))] on the head;
    ``extra_head``: more children of Z.ASM."""
    bed_p = part("BED", bed(), BLUE)
    col_p = part("COLUMN", column(), BLUE)
    rail_yp = part("LINEAR RAIL Y", rail_along(880.0, (0.0, -300.0, BED_TOP), (0, 1, 0), (0, 0, 1)), RAIL_STEEL)
    rail_zp = part("LINEAR RAIL Z", rail_along(1500.0, (0.0, COL_FRONT, -200.0), (0, 0, 1), (0, -1, 0)), RAIL_STEEL)
    rail_xp = part("LINEAR RAIL X", rail_along(1200.0, (-600.0, 0.0, TABLE[4]), (1, 0, 0), (0, 0, -1)), RAIL_STEEL)
    motor_y = part("SERVO MOTOR Y", servo_motor(80.0, 140.0), DARK)
    motor_z = part("SERVO MOTOR Z", servo_motor(80.0, 140.0), DARK)
    motor_x = part("SERVO MOTOR X", servo_motor(60.0, 95.0), DARK)
    table_p = part("TABLE", table(stock), GREY)
    clamp = part("EDGE CLAMP", edge_clamp(stock), DARK)
    screw = part("ISO 4762 M12 x 30 - 12.9", socket_screw(12, 30.0), SCREW_BLACK)
    saddle_p = part("SADDLE", saddle(), BLUE)
    spindle_p = part("SPINDLE", spindle(), GREY)
    housing_p = part("SPINDLE HOUSING", housing(ball_bracket), BLUE)
    smotor = part("SPINDLE MOTOR", spindle_motor(), DARK)
    tray_p = part("CHIP TRAY", tray(), TRAY_GREY)
    drain_p = part("COOLANT DRAIN", drain(), RAIL_STEEL)
    tank_p = part("COOLANT TANK", tank(), DARK)
    nf, nb = COVER_FRONT[2], COVER_BACK[2]
    covers = {(side, k): part(f"WAY COVER Y {side} {k}", cover_section(side, k), COVER_GREY)
              for side, n in (("FRONT", nf), ("BACK", nb)) for k in range(n + 1)}

    sy = clamp_screw_y(stock)
    flip = g.Rot((0, 0, 1), 180.0)
    clamps = []
    for x in (-60.0, 60.0):
        clamps += [(clamp, g.T(x, 0, 0)), (clamp, g.T(x, 0, 0) @ flip)]
    screws = [(screw, (x, y, CLAMP_TOP)) for x in (-60.0, 60.0) for y in (-sy, sy)]
    mx = g.Frame((TABLE[0] + TABLE[2], 0.0, -15.0), (0, 1, 0), (1, 0, 0))
    x_asm = asm("X.ASM", table_p, *[(rail_xp, (0.0, y, 0.0)) for y in RAILS_X], (motor_x, mx),
                stock_part, finished, *clamps, *screws)
    y_asm = asm("Y.ASM", saddle_p, covers[("FRONT", nf)], covers[("BACK", nb)], x_asm)
    z_asm = asm("Z.ASM", spindle_p, housing_p, smotor, *tools, *extra_head)
    my = g.Frame((0.0, BED[1] + BED[3], -620.0), (1, 0, 0), (0, 1, 0))
    mz = g.Frame((0.0, COL_FRONT + 250.0, COLUMN[2]), (1, 0, 0), (0, 0, 1))
    fixed_covers = [covers[(s_, k)] for s_, n in (("FRONT", nf), ("BACK", nb)) for k in range(n)]
    return asm(name, bed_p, col_p, *[(rail_yp, (x, 0.0, 0.0)) for x in RAILS_Y],
               *[(rail_zp, (x, 0.0, 0.0)) for x in RAILS_Z], (motor_y, my), (motor_z, mz), tray_p, drain_p, tank_p,
               *fixed_covers, y_asm, z_asm)

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
