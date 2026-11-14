"""Write the test model for a cable over a stern horn at sea as a STEP assembly (task 0081; generic, invented).

    python tools/make_test_sea.py out.step   TEST.SEA   (tests/data/test_sea.step, copy in fresing_render/data/)
    python tools/make_test_sea.py numbers    prints the numbers below

mm, Z up, x towards the bow, the stern (transom) at x = 0, the waterline at z = 0 (draft 2 m: the app's Sea
"water level" 2.0 m). Everything the cable does lies in the plane y = 0. Every part is one solid.

  STERN DECK       the hull x 0..12000, y -3000..3000, z -2000..2500, its bilges chamfered 400; a rub rail along
                   both sides; plating seams (8 wide, 3 deep) across the deck at x = 2000, 6000, 10000; a bulwark
                   1000 high and 150 thick along both sides (a capping rail on top) and the transom (an opening
                   |y| < 900 for the cable and the horn) (task 0122)
  BULWARK STAY (14 x)  plates 15 thick, 350 x 800, inside the side bulwarks at x = 1500, 3000 … 10500
  CABLE            Ø120, one solid: from (9300, 0, 3200) straight aft to x = 500, an arc of radius 2000 (to its
                   middle) about the axis through (500, *, 1200) along Y, 90° down to vertical at x = -1500, then
                   straight down to z = -1000 (under water). (Its start end lies 300 inside CABLE BLOCK.)
  CABLE BLOCK      a cable stopper: body x 9000..9600, y -300..300, z 2500..3560 with chamfered corners, a top cap
                   (z 3560..3600), a base flange (x 8900..9700, y ±420, 40 thick) with a gusset each side, held down by
                   four ISO 4017 M24 x 40 bolts
  HORN             a U trough bent round that arc, 95° (from 2.5° before the top to 92.5°): round bottom of radius
                   80 under the cable (0.2 mm clear of it), walls 15 thick, up to 40 above the cable's middle; under
                   it from 10° to 85° a web (|y| <= 10, three lightening holes Ø140) down to a flange r 1650..1680,
                   |y| <= 60
  HORN STAND       a block on the deck up under the horn's start (touches the horn's underside along a line), on a
                   base flange
  ROLLER (3 x)     Ø200 x 400 along Y with stubs Ø60 out to y = ±300, at x = 7000, 5000, 3000, 0.2 mm under the cable
  ROLLER STAND (3) a yoke on the deck: a base plate 400 x 760 x 40 (chamfered corners), two uprights with round tops,
                   a bore Ø62 (1 mm clear of the stub) and a bearing boss outside; four ISO 4017 M24 x 40 bolts
  CPS SET          lies on the deck beside the cable, axis along x at y = 1500, z = 2650:
    VERTEBRA (6 x) rings OD 280, ID 150, length 400, gaps of 10, from x = 4000
    CPS TUBE       OD 300, ID 150, length 1500, from x = 6460 (10 after the last ring)
    CPS CHOCK (2)  cradles on the deck under the first and last ring
  BOLLARD (4 x)    double bitts on a base plate at x = 1200 and 10800, y = ±2200
  ISO 4017 M24 x 40 - 8.8 HDG (16 x)   the roller stands' and the cable block's hold-down bolts (head on the plate,
                   the shank through a hole 1 mm wider down to the deck)

Colours: deck, stays, block and stands grey (0.3); horn and rollers steel grey (0.55, 0.57, 0.6); cable near black
(0.13, 0.13, 0.14); CPS orange (0.9, 0.35, 0.05); bollards yellow (0.976, 0.659, 0); bolts galvanised
(0.68, 0.69, 0.7).
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from make_test_paths import (Asm, Part, T, box, cut, cyl, fuse, gap, placed, revolve_y, solids,  # noqa: E402
                             volume, write_step)
from model_details import chamfer, chamfered_rect, hex_bolt  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire  # noqa: E402
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe  # noqa: E402
from OCP.GC import GC_MakeArcOfCircle  # noqa: E402
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt  # noqa: E402

from fresing_render.demo_model import geom as G  # noqa: E402

CABLE_R = 60.0
CLEAR = 0.2                                   # the horn and the rollers stand this far off the cable's skin
HORN_C = (500.0, 0.0, 1200.0)
BEND_R = 2000.0
CABLE_START = (9300.0, 0.0, 3200.0)
CABLE_END_Z = -1000.0
ROLLER_X = (7000.0, 5000.0, 3000.0)
ROLLER_Z = 3200.0 - CABLE_R - 100.0 - CLEAR   # centre of a roller
DECK_TOP = 2500.0
CPS_AXIS = (1500.0, 2650.0)                   # (y, z)
VERT_X0, VERT_LEN, VERT_GAP = 4000.0, 400.0, 10.0
VERT_X = tuple(VERT_X0 + i * (VERT_LEN + VERT_GAP) for i in range(6))
TUBE_X = VERT_X[-1] + VERT_LEN + VERT_GAP
TUBE_LEN = 1500.0
CHOCK_X = (VERT_X[0] + 50.0, VERT_X[-1] + 50.0)
CHOCK_LEN = 300.0
HORN_SECTOR = (-2.5, 92.5)                    # degrees from straight up towards -x
TROUGH_R, WALL = 80.0, 15.0
BOLLARDS = [(1200.0, 2200.0), (1200.0, -2200.0), (10800.0, 2200.0), (10800.0, -2200.0)]
BOLT = "ISO 4017 M24 x 40 - 8.8 HDG"
STAYS_X = (1500.0, 3000.0, 4500.0, 6000.0, 7500.0, 9000.0, 10500.0)
STAND_PLATE = 40.0                            # the roller stands' and the cable block's base plates: 40 thick
STAND_BOLTS = [(sx * 160.0, sy * 345.0) for sx in (1, -1) for sy in (1, -1)]           # roller-local (x, y)
BLOCK_BOLTS = [(x, y) for x in (8950.0, 9650.0) for y in (370.0, -370.0)]

NUMBERS = {
    "horn_centre": HORN_C, "horn_axis": (0.0, 1.0, 0.0), "bend_radius": BEND_R, "cable_radius": CABLE_R,
    "cable_diameter": 2 * CABLE_R,
    "cable_start": CABLE_START, "arrival": (HORN_C[0], 0.0, 3200.0),
    "vertical": (HORN_C[0] - BEND_R, 0.0, HORN_C[2]), "cable_end": (HORN_C[0] - BEND_R, 0.0, CABLE_END_Z),
    "horn_sector": HORN_SECTOR,
    "rollers": [(x, 0.0, ROLLER_Z) for x in ROLLER_X], "roller_axis": (0.0, 1.0, 0.0), "roller_radius": 100.0,
    "cps_axis_point": (0.0, CPS_AXIS[0], CPS_AXIS[1]), "cps_axis": (1.0, 0.0, 0.0),
    "vertebrae": [(x, VERT_LEN) for x in VERT_X], "cps_tube": (TUBE_X, TUBE_LEN),
}
PARTS = (["STERN DECK"] + ["BULWARK STAY"] * 14 + ["CABLE", "CABLE BLOCK", "HORN", "HORN STAND"]
         + ["ROLLER", "ROLLER STAND"] * 3 + ["VERTEBRA"] * 6 + ["CPS TUBE"] + ["CPS CHOCK"] * 2 + ["BOLLARD"] * 4
         + [BOLT] * 16)
ASSEMBLIES = ["TEST.SEA", "CPS SET"]

GREY, STEEL, BLACK, ORANGE = (0.3, 0.3, 0.3), (0.55, 0.57, 0.6), (0.13, 0.13, 0.14), (0.9, 0.35, 0.05)
YELLOW, ZINC = (0.976, 0.659, 0.0), (0.68, 0.69, 0.7)
COLOURS = {"STERN DECK": GREY, "BULWARK STAY": GREY, "CABLE BLOCK": GREY, "ROLLER STAND": GREY, "HORN STAND": GREY,
           "HORN": STEEL, "ROLLER": STEEL, "CABLE": BLACK, "VERTEBRA": ORANGE, "CPS TUBE": ORANGE, "CPS CHOCK": ORANGE,
           "BOLLARD": YELLOW, BOLT: ZINC}

TROUGH_RC = BEND_R + TROUGH_R - CABLE_R - CLEAR     # the trough circle's centre, measured from the horn's axis


def _p(x, z):
    return gp_Pnt(float(x), 0.0, float(z))


# ---------------------------------------------------------------------------------------------------------------------
# details shared with tools/make_test_moving.py (task 0122)
# ---------------------------------------------------------------------------------------------------------------------

BULWARK_T, BULWARK_H = 150.0, 1000.0           # the bulwark: thickness, height above the deck


def deck_shape(x1, seams_x, half=3000.0, bottom=-2000.0, top=DECK_TOP, opening=900.0):
    """The hull x 0..x1, y ±half, z bottom..top as one solid: chamfered bilges, a rub rail, plating seams (8 wide, 3
    deep) across the deck at ``seams_x``, a bulwark (BULWARK_H high, BULWARK_T thick) along both sides and the
    transom (an opening |y| < ``opening``) with a capping rail on the sides. Its stays are parts of their own
    (``stay_places``): one shape placed many times keeps the file small."""
    c = 400.0
    section = [(-half + c, bottom), (half - c, bottom), (half, bottom + c), (half, top), (-half, top),
               (-half, bottom + c)]
    along_x = G.Frame((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))      # local (x, y) = world (y, z)
    parts = [G.polygon_prism(section, x1, along_x)]
    t, h = BULWARK_T, BULWARK_H
    for s in (1.0, -1.0):
        parts.append(box(0.0, s * (half - t), top, x1, s * half, top + h))                          # side bulwark
        parts.append(box(0.0, s * (half - t - 50.0), top + h, x1, s * half, top + h + 40.0))        # capping rail
        parts.append(box(0.0, s * half, top - 260.0, x1, s * (half + 80.0), top - 160.0))          # rub rail
        parts.append(box(0.0, s * opening, top, t, s * (half - t), top + h))                        # transom bulwark
    hull = G.fuse(*parts)
    seams = [box(x - 4.0, -(half - BULWARK_T), top - 3.0, x + 4.0, half - BULWARK_T, top + 1.0) for x in seams_x]
    return G.cut(hull, *seams)


def stay_shape():
    """A bulwark stay: a plate 15 thick, 350 in from the bulwark, 800 up (placed by ``stay_places``)."""
    return G.polygon_prism([(0.0, 0.0), (350.0, 0.0), (0.0, 800.0)], 15.0)


def stay_places(xs, half=3000.0, top=DECK_TOP):
    """Where the stays stand: on the deck against both side bulwarks at each x (local x inwards, y up)."""
    out = []
    for x in xs:
        for s in (1.0, -1.0):
            out.append(G.Frame((x + 7.5 * s, s * (half - BULWARK_T), top), (0.0, -s, 0.0), (-s, 0.0, 0.0)))
    return out


def bollard_shape():
    """Double bitts on a base plate, local origin on the deck under the middle: posts Ø300 600 high, 500 apart."""
    plate = G.polygon_prism(chamfered_rect(-450.0, -200.0, 900.0, 400.0, 40.0), 30.0)
    parts = [plate]
    for x in (-250.0, 250.0):
        parts += [G.cyl(150.0, 600.0, (x, 0.0, 30.0)), G.cyl(190.0, 40.0, (x, 0.0, 630.0))]
    return G.fuse(*parts)


def bolt_shape():
    """ISO 4017 M24 x 40: the head on z 0..15, the shank down to z = -40."""
    return hex_bolt(24, STAND_PLATE)


def bolt_holes(points, z0, depth):
    return [G.cyl(12.5, depth + 2.0, (x, y, z0 - 1.0)) for x, y in points]


# ---------------------------------------------------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------------------------------------------------

def cable_shape():
    cx, _, cz = HORN_C
    w = BRepBuilderAPI_MakeWire()
    w.Add(BRepBuilderAPI_MakeEdge(_p(CABLE_START[0], CABLE_START[2]), _p(cx, cz + BEND_R)).Edge())
    mid = math.radians(45.0)
    arc = GC_MakeArcOfCircle(_p(cx, cz + BEND_R), _p(cx - BEND_R * math.sin(mid), cz + BEND_R * math.cos(mid)),
                             _p(cx - BEND_R, cz)).Value()
    w.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    w.Add(BRepBuilderAPI_MakeEdge(_p(cx - BEND_R, cz), _p(cx - BEND_R, CABLE_END_Z)).Edge())
    circle = gp_Circ(gp_Ax2(_p(CABLE_START[0], CABLE_START[2]), gp_Dir(-1.0, 0.0, 0.0)), CABLE_R)
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire(), True).Face()
    return BRepOffsetAPI_MakePipe(w.Wire(), face).Shape()


def horn_shape():
    rc, ro, top = TROUGH_RC, TROUGH_R + WALL, BEND_R + 40.0
    profile = [(top, -ro), (rc, -ro), ("arc", (rc - ro, 0.0), (rc, ro)), (top, ro),
               (top, TROUGH_R), (rc, TROUGH_R), ("arc", (rc - TROUGH_R, 0.0), (rc, -TROUGH_R)), (top, -TROUGH_R)]
    a0 = math.radians(HORN_SECTOR[1])             # sweep from 92.5° back to -2.5° (a turn about +Y goes z -> x)
    start = np.array([-math.sin(a0), 0.0, math.cos(a0)])
    trough = revolve_y(profile, centre=HORN_C, start=start, angle=HORN_SECTOR[1] - HORN_SECTOR[0])
    # under it (task 0122), from 10° to 85°: a web (|y| <= 10) down to a flange (r 1650..1680, |y| <= 60), all of
    # it turned about the horn's axis (planes square to the axis meet the trough in circles: a small file), with three
    # lightening holes in the web
    r10 = rc - math.sqrt(ro * ro - 100.0) + 6.0                  # 6 up into the trough's wall
    web = [(r10, -10.0), (1680.0, -10.0), (1680.0, -60.0), (1650.0, -60.0), (1650.0, 60.0), (1680.0, 60.0),
           (1680.0, 10.0), (r10, 10.0)]
    a1 = math.radians(85.0)
    web = revolve_y(web, centre=HORN_C, start=np.array([-math.sin(a1), 0.0, math.cos(a1)]), angle=75.0)
    holes = []
    for deg in (30.0, 50.0, 70.0):
        a = math.radians(deg)
        c = np.array(HORN_C) + 1800.0 * np.array([-math.sin(a), 0.0, math.cos(a)])
        holes.append(cyl(70.0, c - (0.0, 30.0, 0.0), c + (0.0, 30.0, 0.0)))
    return cut(G.fuse(trough, web), *holes)


def horn_stand_shape():
    r_under = TROUGH_RC - (TROUGH_R + WALL)       # the horn's underside at y = 0
    block = box(560.0, -110.0, DECK_TOP, 760.0, 110.0, 3300.0)
    under = cyl(r_under, (HORN_C[0], -200.0, HORN_C[2]), (HORN_C[0], 200.0, HORN_C[2]))
    stand = BRepAlgoAPI_Common(block, under).Shape()
    flange = G.polygon_prism(chamfered_rect(520.0, -160.0, 280.0, 320.0, 20.0), 30.0, G.T(0.0, 0.0, DECK_TOP))
    return G.fuse(stand, flange)


def roller_shape():
    """About Y through its origin (the centre)."""
    return fuse(cyl(100.0, (0, -200, 0), (0, 200, 0)), cyl(30.0, (0, -300, 0), (0, 300, 0)))


def roller_stand_shape():
    """In the roller's own coordinates (origin on its axis); its base plate stands on z = DECK_TOP - ROLLER_Z."""
    zb = DECK_TOP - ROLLER_Z
    plate = G.polygon_prism(chamfered_rect(-200.0, -380.0, 400.0, 760.0, 30.0), STAND_PLATE, G.T(0.0, 0.0, zb))
    parts = [plate]
    for s in (1.0, -1.0):
        parts += [box(-100, s * 210, zb + STAND_PLATE, 100, s * 330, 0), cyl(100.0, (0, s * 210, 0), (0, s * 330, 0)),
                  cyl(70.0, (0, s * 330, 0), (0, s * 348, 0))]
    shape = G.fuse(*parts)
    return G.cut(shape, cyl(31.0, (0, -400, 0), (0, 400, 0)), *bolt_holes(STAND_BOLTS, zb, STAND_PLATE))


def cable_block_shape():
    """A cable stopper; the cable runs into its aft face (x = 9000) at (y 0, z 3200)."""
    body = G.polygon_prism(chamfered_rect(9000.0, -300.0, 600.0, 600.0, 60.0), 1060.0, G.T(0.0, 0.0, DECK_TOP))
    cap = G.polygon_prism(chamfered_rect(8980.0, -320.0, 640.0, 640.0, 70.0), 40.0, G.T(0.0, 0.0, DECK_TOP + 1060.0))
    flange = G.polygon_prism(chamfered_rect(8900.0, -420.0, 800.0, 840.0, 40.0), STAND_PLATE, G.T(0.0, 0.0, DECK_TOP))
    tri = [(0.0, 0.0), (120.0, 0.0), (0.0, 500.0)]
    gussets = []
    for s in (1.0, -1.0):
        for x in (9300.0,):
            gussets.append(G.polygon_prism(tri, 20.0, G.Frame((x - 10.0 * s, s * 300.0, DECK_TOP + STAND_PLATE),
                                                              (0.0, s, 0.0), (s, 0.0, 0.0))))
    shape = G.fuse(body, cap, flange, *gussets)
    return G.cut(shape, *bolt_holes(BLOCK_BOLTS, DECK_TOP, STAND_PLATE))


def ring(od, idia, length):
    return cut(cyl(od / 2, (0, 0, 0), (length, 0, 0)), cyl(idia / 2, (-1, 0, 0), (length + 1, 0, 0)))


def chock_shape():
    """Local: the CPS axis is the x axis (origin on it); a cradle for the ring (r 140) on the deck."""
    zd = DECK_TOP - CPS_AXIS[1]
    return cut(box(0, -100, zd, CHOCK_LEN, 100, zd + 80), cyl(140.0, (-1, 0, 0), (CHOCK_LEN + 1, 0, 0)))


def model():
    root = Asm("TEST.SEA")
    root.add(Part("STERN DECK", deck_shape(12000.0, (2000.0, 6000.0, 10000.0)), GREY))
    stay = Part("BULWARK STAY", stay_shape(), GREY)
    for m in stay_places(STAYS_X):
        root.add(stay, m)
    root.add(Part("CABLE", cable_shape(), BLACK))
    root.add(Part("CABLE BLOCK", cable_block_shape(), GREY))
    root.add(Part("HORN", horn_shape(), STEEL))
    root.add(Part("HORN STAND", horn_stand_shape(), GREY))
    roller, stand = Part("ROLLER", roller_shape(), STEEL), Part("ROLLER STAND", roller_stand_shape(), GREY)
    for x in ROLLER_X:
        root.add(roller, T(x, 0, ROLLER_Z))
        root.add(stand, T(x, 0, ROLLER_Z))
    cps = Asm("CPS SET")
    vert = Part("VERTEBRA", ring(280.0, 150.0, VERT_LEN), ORANGE)
    for x in VERT_X:
        cps.add(vert, T(x))
    cps.add(Part("CPS TUBE", ring(300.0, 150.0, TUBE_LEN), ORANGE), T(TUBE_X))
    chock = Part("CPS CHOCK", chock_shape(), ORANGE)
    for x in CHOCK_X:
        cps.add(chock, T(x))
    root.add(cps, T(0, CPS_AXIS[0], CPS_AXIS[1]))
    bollard = Part("BOLLARD", bollard_shape(), YELLOW)
    for x, y in BOLLARDS:
        root.add(bollard, T(x, y, DECK_TOP))
    bolt = Part(BOLT, bolt_shape(), ZINC)
    for x in ROLLER_X:
        for bx, by in STAND_BOLTS:
            root.add(bolt, T(x + bx, by, DECK_TOP + STAND_PLATE))
    for bx, by in BLOCK_BOLTS:
        root.add(bolt, T(bx, by, DECK_TOP + STAND_PLATE))
    return root


def count_parts(root):
    return len(placed(root))


def check(root, say=print):
    """Raises AssertionError with a plain reason when the model is not as described."""
    items = placed(root)
    assert [n for n, _p_, _s in items] == PARTS, [n for n, _p_, _s in items]
    for name, _path, shape in items:
        assert solids(shape) == 1 and volume(shape) > 1.0, name
    assert [p for n, p, _s in items if n == "VERTEBRA"] == [["TEST.SEA", "CPS SET"]] * 6
    by = {}
    for name, _path, shape in items:
        by.setdefault(name, []).append(shape)
    cable = by["CABLE"][0]
    for name, tol in (("HORN", 1.0), ("ROLLER", 0.5)):
        for s in by[name]:
            d = gap(cable, s)
            assert CLEAR - 1e-3 <= d <= tol, (name, "the cable must rest on it within", tol, d)
    block = by["CABLE BLOCK"][0]
    inside = volume(BRepAlgoAPI_Common(cable, block).Shape())
    assert inside > 0.9 * math.pi * CABLE_R ** 2 * 300.0, ("the cable starts in its block", inside)
    for st, ro in zip(by["ROLLER STAND"], by["ROLLER"]):
        assert 0.5 < gap(st, ro) < 1.5, ("stand and roller: bore gap", gap(st, ro))
    assert gap(by["HORN STAND"][0], cable) > 10.0, "the horn stand must not touch the cable"
    assert gap(by["HORN STAND"][0], by["HORN"][0]) < 1.0, "the horn stand carries the horn"
    deck = by["STERN DECK"][0]
    for name in ("CABLE BLOCK", "HORN STAND", "ROLLER STAND", "CPS CHOCK", "CPS TUBE", "BOLLARD", BOLT, "BULWARK STAY"):
        for s in by[name]:
            assert gap(s, deck) < 1e-6, (name, "must stand on the deck")
    for b in by[BOLT]:                            # a bolt's shank in its hole, not in the plate
        holder = [s for s in by["ROLLER STAND"] + by["CABLE BLOCK"] if gap(s, b) < 1e-6]
        assert len(holder) == 1 and volume(BRepAlgoAPI_Common(b, holder[0]).Shape()) < 1e-3, "a bolt sits wrong"
        assert volume(BRepAlgoAPI_Common(b, deck).Shape()) < 1e-3, "a bolt goes into the deck"
    meant = {("CABLE BLOCK", "STERN DECK"), ("HORN STAND", "STERN DECK"), ("ROLLER STAND", "STERN DECK"),
             ("HORN STAND", "HORN"), ("CABLE", "CABLE BLOCK"), ("CPS CHOCK", "STERN DECK"),
             ("CPS CHOCK", "VERTEBRA"), ("CPS TUBE", "STERN DECK"), ("BOLLARD", "STERN DECK"), (BOLT, "STERN DECK"),
             (BOLT, "ROLLER STAND"), (BOLT, "CABLE BLOCK"), ("BULWARK STAY", "STERN DECK")}
    least = (1e9, "")
    for i, (na, _pa, sa) in enumerate(items):
        for nb, _pb, sb in items[i + 1:]:
            if (na, nb) in meant or (nb, na) in meant:
                continue
            d = gap(sa, sb)
            assert d > 0.05, ("parts touch or overlap where not meant", na, nb, d)
            if "STERN DECK" not in (na, nb):
                least = min(least, (d, f"{na} - {nb}"))
    say(f"  least gap between parts that are not meant to touch: {least[0]:.2f} mm ({least[1]})")
    away = min((gap(cable, s), n) for n, _p_, s in items
               if n not in ("CABLE", "CABLE BLOCK", "HORN", "ROLLER", "HORN STAND"))
    assert away[0] >= 50.0, ("a part is too near the cable", away)
    say(f"  every other part (but the horn stand) is {away[0]:.0f} mm or more from the cable ({away[1]})")


def numbers(say=print):
    for k, v in NUMBERS.items():
        say(f"{k}: {v}")


def main(argv):
    if len(argv) < 2 or argv[1] == "numbers":
        numbers()
        return 0
    root = model()
    check(root)
    write_step(root, argv[1])
    print(f"written: {count_parts(root)} parts, {os.path.getsize(argv[1]) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
