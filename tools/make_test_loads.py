"""Write the test model of real-size lifting loads as a STEP assembly (task 0231; generic, invented).

    python tools/make_test_loads.py out.step    TEST.LOADS  (tests/data/test_loads.step, a copy in fresing_render/data/)
    python tools/make_test_loads.py numbers     prints the numbers below

Three loads on a yard, each sized for the crane that lifts it in the Lifting learning set. All sizes in mm, Z up, the
ground at z = 0. Every part is one solid. No real make, no logo. The masses are NOT in the STEP: the app's Load panel
gets them ("estimate": invented) from ``NUMBERS`` – the tour and the tests read them from there.

======================================================================================================================
IBC ON PALLET.ASM        1200 x 1000 x 1150 mm, about 1.1 t full; centre of its footprint (-6000, 0)
  PALLET                 1200 x 1000 x 150: top boards, three bearers, a bottom ledge
  IBC TANK               a plastic tank 1000 x 800 x 900 in the cage (z 175..1075)
  IBC CAGE               the steel grid round it: corner posts, three rails round, a bottom frame (one solid)
  IBC CAP                the filler cap on the tank's top
  LIFTING EYE (4 x)      small eyes on the cage's top corners (z 1100 .. 1150, a Ø20 hole): L5 will rig them
PUMP SKID.ASM            4000 x 2000 x 200 frame, pump and motor off-centre, about 6 t; centre (0, 0)
  SKID FRAME             two long channels (y -1000..-850 and 850..1000), five cross members, z 0..200
  MOTOR                  Ø600 x 1100 on two feet, axis along x at y = +350 (x -1700..-600), centre z 560
  PUMP                   volute Ø500 x 800 + suction and delivery pipes, axis along x at y = +350 (x 300..1800)
  COUPLING GUARD         a box between motor and pump
  PADEYE (4 x)           plates 80 x 12 x 120 with a Ø36 hole at the four corners (x ±1800, y ±900), top z 320
20 FT CONTAINER.ASM      6058 x 2438 x 2591 mm, about 18 t gross; centre of its footprint (8500, 0)
  CONTAINER SHELL        hollow box (wall 25) with 30 corrugation ribs on both long sides
  DOOR LEAF L / R        two door leaves on the end at +x
  CORNER CASTING TOP (4 x)    178 x 162 x 118 with the 124 x 63 slot in the top face: the lift points
  CORNER CASTING BOTTOM (4 x) the same without the slot
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from fresing_render.demo_model import geom as g  # noqa: E402
from machine_parts import asm, part, write  # noqa: E402

WOOD, TANK_WHITE, CAGE_STEEL = (0.62, 0.47, 0.3), (0.86, 0.88, 0.9), (0.62, 0.64, 0.67)
SKID_BLUE, MOTOR_BLUE, PUMP_RED, EYE_YELLOW = (0.1, 0.27, 0.45), (0.1, 0.35, 0.6), (0.75, 0.2, 0.12), (0.95, 0.75, 0.1)
BOX_ORANGE, CASTING = (0.8, 0.32, 0.1), (0.45, 0.46, 0.48)

IBC_AT, SKID_AT, BOX_AT = (-6000.0, 0.0), (0.0, 0.0), (8500.0, 0.0)

# size (x, y, z mm), gross mass (t), source of the mass in the app: all invented
NUMBERS = {
    "ibc_size": (1200.0, 1000.0, 1150.0), "ibc_mass_t": 1.1,
    "skid_size": (4000.0, 2000.0, 1060.0), "skid_mass_t": 6.0,
    "container_size": (6058.0, 2438.0, 2591.0), "container_mass_t": 18.0,
    "ibc_at": IBC_AT, "skid_at": SKID_AT, "container_at": BOX_AT,
    "padeyes": 4, "ibc_eyes": 4, "top_castings": 4,
}
ASSEMBLIES = ["TEST.LOADS", "IBC ON PALLET.ASM", "PUMP SKID.ASM", "20 FT CONTAINER.ASM"]
PARTS = (["PALLET", "IBC TANK", "IBC CAGE", "IBC CAP"] + ["LIFTING EYE"] * 4
         + ["SKID FRAME", "MOTOR", "PUMP", "COUPLING GUARD"] + ["PADEYE"] * 4
         + ["CONTAINER SHELL", "DOOR LEAF L", "DOOR LEAF R"] + ["CORNER CASTING TOP"] * 4
         + ["CORNER CASTING BOTTOM"] * 4)
COLOURS = {"PALLET": WOOD, "IBC TANK": TANK_WHITE, "IBC CAGE": CAGE_STEEL, "IBC CAP": BOX_ORANGE,
           "LIFTING EYE": EYE_YELLOW, "SKID FRAME": SKID_BLUE, "MOTOR": MOTOR_BLUE, "PUMP": PUMP_RED,
           "COUPLING GUARD": EYE_YELLOW, "PADEYE": EYE_YELLOW, "CONTAINER SHELL": BOX_ORANGE,
           "DOOR LEAF L": BOX_ORANGE, "DOOR LEAF R": BOX_ORANGE, "CORNER CASTING TOP": CASTING,
           "CORNER CASTING BOTTOM": CASTING}


def _eye(width: float, thick: float, height: float, hole_r: float, hole_z: float):
    """An eye plate standing in the x-z plane: x -w/2..w/2, y -t/2..t/2, z 0..h, a round hole along y."""
    plate = g.box(-width / 2, -thick / 2, 0.0, width, thick, height)
    return g.cut(plate, g.cyl(hole_r, thick + 20.0, (0.0, -thick / 2 - 10.0, hole_z), (0.0, 1.0, 0.0)))


# ---- the IBC ----------------------------------------------------------------------------------------------------

def pallet():
    boards = [g.box(-600, -500 + k * 238, 125, 1200, 120, 25) for k in range(5)]
    bearers = [g.box(-600 + k * 540, -500, 25, 120, 1000, 100) for k in range(3)]
    ledge = [g.box(-600, -500, 0, 1200, 120, 25), g.box(-600, 380, 0, 1200, 120, 25)]
    return g.fuse(*boards, *bearers, *ledge)


def ibc_tank():
    body = g.box(-500, -400, 175, 1000, 800, 900)
    return g.fuse(body, g.cyl(60.0, 40.0, (0.0, 0.0, 1075.0)))


def ibc_cage():
    posts = [g.box(sx * 590 - 10 if sx > 0 else -600, sy * 490 - 10 if sy > 0 else -500, 150, 10, 10, 1000)
             for sx in (-1, 1) for sy in (-1, 1)]
    parts = list(posts)
    for z in (150.0, 600.0, 1130.0):                     # three rails round
        parts += [g.box(-600, -500, z, 1200, 10, 20), g.box(-600, 490, z, 1200, 10, 20),
                  g.box(-600, -500, z, 10, 1000, 20), g.box(590, -500, z, 10, 1000, 20)]
    for k in range(1, 5):                                # upright bars on the long sides
        x = -600 + k * 240
        parts += [g.box(x - 4, -500, 150, 8, 8, 1000), g.box(x - 4, 492, 150, 8, 8, 1000)]
    return g.fuse(*parts)


def ibc_assembly():
    pal = part("PALLET", pallet(), WOOD)
    tank = part("IBC TANK", ibc_tank(), TANK_WHITE)
    cage = part("IBC CAGE", ibc_cage(), CAGE_STEEL)
    cap = part("IBC CAP", g.fuse(g.cyl(70.0, 25.0, (0.0, 0.0, 1115.0))), BOX_ORANGE)
    eye = part("LIFTING EYE", _eye(60.0, 10.0, 50.0, 10.0, 30.0), EYE_YELLOW)
    eyes = [(eye, (sx * 570.0, sy * 480.0, 1100.0)) for sx in (-1, 1) for sy in (-1, 1)]
    return asm("IBC ON PALLET.ASM", pal, tank, cage, cap, *eyes)


# ---- the pump skid ----------------------------------------------------------------------------------------------

def skid_frame():
    chan = [g.box(-2000, -1000, 0, 4000, 150, 200), g.box(-2000, 850, 0, 4000, 150, 200)]
    cross = [g.box(x - 60, -850, 60, 120, 1700, 140) for x in (-1800, -900, 0, 900, 1800)]
    return g.fuse(*chan, *cross)


def motor():
    body = g.cyl(300.0, 1100.0, (-1700.0, 350.0, 560.0), (1.0, 0.0, 0.0))
    # the feet reach up into the body (its lowest line is z 260)
    feet = [g.box(x, 350 - 220, 200, 200, 440, 150) for x in (-1600.0, -900.0)]
    terminal = g.box(-1300, 350 - 130, 840, 260, 260, 150)
    return g.fuse(body, *feet, terminal)


def pump():
    volute = g.cyl(250.0, 500.0, (900.0, 350.0, 560.0), (1.0, 0.0, 0.0))
    shaft_end = g.cyl(120.0, 700.0, (300.0, 350.0, 560.0), (1.0, 0.0, 0.0))
    foot = g.box(700, 350 - 250, 200, 400, 500, 110)
    suction = g.cyl(110.0, 500.0, (1400.0, 350.0, 560.0), (1.0, 0.0, 0.0))
    delivery = g.cyl(90.0, 500.0, (1100.0, 350.0, 560.0), (0.0, 0.0, 1.0))
    return g.fuse(volute, shaft_end, foot, suction, delivery)


def skid_assembly():
    frame = part("SKID FRAME", skid_frame(), SKID_BLUE)
    mot = part("MOTOR", motor(), MOTOR_BLUE)
    pmp = part("PUMP", pump(), PUMP_RED)
    guard = part("COUPLING GUARD", g.box(-600, 350 - 150, 410, 900, 300, 300), EYE_YELLOW)
    eye = part("PADEYE", _eye(80.0, 12.0, 120.0, 18.0, 70.0), EYE_YELLOW)
    eyes = [(eye, (sx * 1800.0, sy * 900.0, 200.0)) for sx in (-1, 1) for sy in (-1, 1)]
    return asm("PUMP SKID.ASM", frame, mot, pmp, guard, *eyes)


# ---- the 20 ft container ----------------------------------------------------------------------------------------

L, W, H = 6058.0, 2438.0, 2591.0


def shell():
    outer = g.box(-L / 2, -W / 2, 0, L, W, H)
    inner = g.box(-L / 2 + 25, -W / 2 + 25, 25, L - 50, W - 50, H - 50)
    parts = [g.cut(outer, inner)]
    for sy in (-1, 1):                                   # corrugation: 15 ribs on each long side
        for k in range(15):
            x = -L / 2 + 370 + k * 350
            y0 = sy * (W / 2) - (0 if sy > 0 else 0)
            parts.append(g.box(x - 40, y0 - 5 if sy > 0 else y0 - 25, 150, 80, 30, H - 300))
    return g.fuse(*parts)


def door_leaf(side: int):
    y0 = 5.0 if side > 0 else -1200.0
    leaf = g.box(L / 2, y0, 140, 22, 1195, H - 280)
    bars = [g.cyl(14.0, H - 200, (L / 2 + 28, y0 + 200 + k * 400, 100)) for k in range(3)]
    return g.fuse(leaf, *bars)


def casting(top: bool):
    c = g.box(-89, -81, 0, 178, 162, 118)
    if top:
        c = g.cut(c, g.box(-62, -31.5, 118 - 30, 124, 63, 40))
    return c


def container_assembly():
    sh = part("CONTAINER SHELL", shell(), BOX_ORANGE)
    dl, dr = part("DOOR LEAF L", door_leaf(1), BOX_ORANGE), part("DOOR LEAF R", door_leaf(-1), BOX_ORANGE)
    top = part("CORNER CASTING TOP", casting(True), CASTING)
    bot = part("CORNER CASTING BOTTOM", casting(False), CASTING)
    xs, ys = L / 2 - 89, W / 2 - 81
    tops = [(top, (sx * xs, sy * ys, H - 118)) for sx in (-1, 1) for sy in (-1, 1)]
    bots = [(bot, (sx * xs, sy * ys, 0.0)) for sx in (-1, 1) for sy in (-1, 1)]
    return asm("20 FT CONTAINER.ASM", sh, dl, dr, *tops, *bots)


def model():
    return asm("TEST.LOADS", (ibc_assembly(), (*IBC_AT, 0.0)), (skid_assembly(), (*SKID_AT, 0.0)),
               (container_assembly(), (*BOX_AT, 0.0)))


def placed(root):
    """(name, path, world shape) of every part, in the order PARTS lists them."""
    out = []
    for node, _uid, W_, _label, path in g.walk(root):
        if isinstance(node, g.Part):
            out.append((node.name, [c.parent.name for c in path], g.xform(node.shape, W_)))
    return out


def check(root, say=print):
    """Raises AssertionError with a plain reason when the model is not as described."""
    items = placed(root)
    assert [n for n, _p, _s in items] == PARTS, [n for n, _p, _s in items]
    for name, _p, shape in items:
        assert g.solids(shape) == 1 and g.volume(shape) > 1.0, name
    boxes = {}
    for name, _p, shape in items:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        b = Bnd_Box()
        BRepBndLib.Add_s(shape, b)
        lo, hi = b.CornerMin(), b.CornerMax()
        boxes.setdefault(name, []).append((lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()))

    def span(names):
        bb = [x for n in names for x in boxes[n]]
        return (max(b[3] for b in bb) - min(b[0] for b in bb), max(b[4] for b in bb) - min(b[1] for b in bb),
                max(b[5] for b in bb) - min(b[2] for b in bb))
    ibc = span(["PALLET", "IBC CAGE", "LIFTING EYE"])
    skid = span(["SKID FRAME", "MOTOR", "PUMP", "PADEYE"])
    box = span(["CONTAINER SHELL", "CORNER CASTING TOP", "CORNER CASTING BOTTOM"])
    for got, want, what in ((ibc, NUMBERS["ibc_size"], "IBC"), (skid, NUMBERS["skid_size"], "skid"),
                            (box, NUMBERS["container_size"], "container")):
        assert all(abs(a - b) < 80.0 for a, b in zip(got[:2], want[:2])) and abs(got[2] - want[2]) < 80.0, \
            (what, got, want)
    say(f"  sizes: IBC {ibc}, skid {skid}, container {box}")


def numbers(say=print):
    for k, v in NUMBERS.items():
        say(f"{k}: {v}")


def main(argv):
    if len(argv) < 2 or argv[1] == "numbers":
        numbers()
        return 0
    root = model()
    check(root)
    write(root, argv[1])
    print(f"written: {g.count_parts(root)} parts, {os.path.getsize(argv[1]) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
