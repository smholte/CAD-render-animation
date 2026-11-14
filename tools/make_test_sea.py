"""Write the test model for a cable over a stern horn at sea as a STEP assembly (task 0081; generic, invented).

    python tools/make_test_sea.py out.step   TEST.SEA   (tests/data/test_sea.step, copy in fresing_render/data/)
    python tools/make_test_sea.py numbers    prints the numbers below

mm, Z up, x towards the bow, the stern (transom) at x = 0, the waterline at z = 0 (draft 2 m: the app's Sea
"water level" 2.0 m). Everything the cable does lies in the plane y = 0. Every part is one solid.

  STERN DECK       box hull x 0..12000, y -3000..3000, z -2000..2500
  CABLE            Ø120, one solid: from (9300, 0, 3200) straight aft to x = 500, an arc of radius 2000 (to its
                   middle) about the axis through (500, *, 1200) along Y, 90° down to vertical at x = -1500, then
                   straight down to z = -1000 (under water). (Its start end lies 300 inside CABLE BLOCK.)
  CABLE BLOCK      box x 9000..9600, y -300..300, z 2500..3600
  HORN             a U trough bent round that arc, 95° (from 2.5° before the top to 92.5°): round bottom of radius
                   80 under the cable (0.2 mm clear of it), walls 15 thick, up to 40 above the cable's middle
  HORN STAND       a block on the deck up under the horn's start (touches the horn's underside along a line)
  ROLLER (3 x)     Ø200 x 400 along Y with stubs Ø60 out to y = ±300, at x = 7000, 5000, 3000, 0.2 mm under the cable
  ROLLER STAND (3) a yoke on the deck: two uprights with a bore Ø62 (1 mm clear of the stub) on a base plate
  CPS SET          lies on the deck beside the cable, axis along x at y = 1500, z = 2650:
    VERTEBRA (6 x) rings OD 280, ID 150, length 400, gaps of 10, from x = 4000
    CPS TUBE       OD 300, ID 150, length 1500, from x = 6460 (10 after the last ring)
    CPS CHOCK (2)  cradles on the deck under the first and last ring

Colours: deck, block and stands grey (0.3); horn and rollers steel grey (0.55, 0.57, 0.6); cable near black
(0.13, 0.13, 0.14); CPS orange (0.9, 0.35, 0.05).
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_paths import (Asm, Part, T, box, cut, cyl, fuse, gap, placed, revolve_y, solids,  # noqa: E402
                             volume, write_step)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire  # noqa: E402
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe  # noqa: E402
from OCP.GC import GC_MakeArcOfCircle  # noqa: E402
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt  # noqa: E402

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
PARTS = (["STERN DECK", "CABLE", "CABLE BLOCK", "HORN", "HORN STAND"] + ["ROLLER", "ROLLER STAND"] * 3
         + ["VERTEBRA"] * 6 + ["CPS TUBE"] + ["CPS CHOCK"] * 2)
ASSEMBLIES = ["TEST.SEA", "CPS SET"]

GREY, STEEL, BLACK, ORANGE = (0.3, 0.3, 0.3), (0.55, 0.57, 0.6), (0.13, 0.13, 0.14), (0.9, 0.35, 0.05)
COLOURS = {"STERN DECK": GREY, "CABLE BLOCK": GREY, "ROLLER STAND": GREY, "HORN STAND": GREY, "HORN": STEEL,
           "ROLLER": STEEL, "CABLE": BLACK, "VERTEBRA": ORANGE, "CPS TUBE": ORANGE, "CPS CHOCK": ORANGE}

TROUGH_RC = BEND_R + TROUGH_R - CABLE_R - CLEAR     # the trough circle's centre, measured from the horn's axis


def _p(x, z):
    return gp_Pnt(float(x), 0.0, float(z))


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
    return revolve_y(profile, centre=HORN_C, start=start, angle=HORN_SECTOR[1] - HORN_SECTOR[0])


def horn_stand_shape():
    r_under = TROUGH_RC - (TROUGH_R + WALL)       # the horn's underside at y = 0
    block = box(560.0, -110.0, DECK_TOP, 760.0, 110.0, 3300.0)
    under = cyl(r_under, (HORN_C[0], -200.0, HORN_C[2]), (HORN_C[0], 200.0, HORN_C[2]))
    return BRepAlgoAPI_Common(block, under).Shape()


def roller_shape():
    """About Y through its origin (the centre)."""
    return fuse(cyl(100.0, (0, -200, 0), (0, 200, 0)), cyl(30.0, (0, -300, 0), (0, 300, 0)))


def roller_stand_shape():
    """In the roller's own coordinates (origin on its axis); its base plate stands on z = DECK_TOP - ROLLER_Z."""
    zb = DECK_TOP - ROLLER_Z
    parts = [box(-120, -330, zb, 120, 330, zb + 60), box(-100, 210, zb, 100, 330, 60),
             box(-100, -330, zb, 100, -210, 60)]
    return cut(fuse(*parts), cyl(31.0, (0, -400, 0), (0, 400, 0)))


def ring(od, idia, length):
    return cut(cyl(od / 2, (0, 0, 0), (length, 0, 0)), cyl(idia / 2, (-1, 0, 0), (length + 1, 0, 0)))


def chock_shape():
    """Local: the CPS axis is the x axis (origin on it); a cradle for the ring (r 140) on the deck."""
    zd = DECK_TOP - CPS_AXIS[1]
    return cut(box(0, -100, zd, CHOCK_LEN, 100, zd + 80), cyl(140.0, (-1, 0, 0), (CHOCK_LEN + 1, 0, 0)))


def model():
    root = Asm("TEST.SEA")
    root.add(Part("STERN DECK", box(0, -3000, -2000, 12000, 3000, DECK_TOP), GREY))
    root.add(Part("CABLE", cable_shape(), BLACK))
    root.add(Part("CABLE BLOCK", box(9000, -300, DECK_TOP, 9600, 300, 3600), GREY))
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
    for name in ("CABLE BLOCK", "HORN STAND", "ROLLER STAND", "CPS CHOCK", "CPS TUBE"):
        for s in by[name]:
            assert gap(s, deck) < 1e-6, (name, "must stand on the deck")
    meant = {("CABLE BLOCK", "STERN DECK"), ("HORN STAND", "STERN DECK"), ("ROLLER STAND", "STERN DECK"),
             ("HORN STAND", "HORN"), ("CABLE", "CABLE BLOCK"), ("CPS CHOCK", "STERN DECK"),
             ("CPS CHOCK", "VERTEBRA"), ("CPS TUBE", "STERN DECK")}
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
