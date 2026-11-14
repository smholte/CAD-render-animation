"""Write the test model for a cable on a moving part as a STEP assembly (task 0082; generic, invented).

    python tools/make_test_moving.py out.step   TEST.MOVING  (tests/data/test_moving.step, copy in fresing_render/data/)
    python tools/make_test_moving.py numbers    prints the numbers below

A stern with a horn (as tools/make_test_sea.py) under an overhead gantry. A trolley runs aft along the gantry's
beams; under it a hanger swings about the trolley's pivot; under the hanger a block hangs with a sheave and a clamp
(it can be lowered away from the hanger, as on a wire). A cable is clamped on the block, goes forward round the front
of the sheave, aft and down over the horn into the sea – a cable end carried over the stern and down. A lift wire
comes from a fairlead at the front of the gantry, over a head sheave on the trolley and down to an eye on the block.

mm, Z up, x towards the bow, the stern (transom) at x = 0, the waterline at z = 0 (draft 2 m). The cable lies in the
plane y = 0, the lift wire in the plane y = 300. Every part is one solid.

  STERN DECK       the hull x 0..14000, y -3000..3000, z -2000..2500 with bulwarks, rub rails and plating seams
                   (``make_test_sea.deck_shape``)
  HORN, HORN STAND as tools/make_test_sea.py: the cable's middle on an arc of radius 2000 about (500, *, 1200)
  BULWARK STAY (8 x)  as tools/make_test_sea.py, at x = 1500, 4500, 7500, 10500
  GANTRY           two beams (x -5000..14000, y ±1400..±1600, z 6800..7200), four posts (x 2600..2800 and
                   13600..13800, from the deck up) and a cross beam at the front (x 13600..13800): one solid
  KNEE BRACE (6 x) plates 20 thick under the beams beside the posts, 400 along the beam and 400 down the post
  RAIL END STOP (4 x)  blocks with a buffer on the beams at x -5000..-4850 and 13450..13600 (the trolley's way:
                   x -3400..8600 over the joint's 12 m)
  FAIRLEAD         a post on the front cross beam (x 13600..13700, y 220..380, z 7200..7850) with a head
                   (x 13500..13800, z 7650..7850); the lift wire starts on its front face and runs through it
  CARRIER.ASM      moves along the beams (the joint "Travel")
    TROLLEY        a plate on the beams (x 7400..8600, y ±1650, z 7210..7400, corners chamfered, a slot x 7500..7950,
                   y 250..350 for the lift wire) with side skirts outside the beams (y ±1610..±1650) and
                   two lugs (y ±110..±170, x 7850..8150) with round bottoms (r 150) about the PIVOT axis
                   (8000, *, 6500) along Y, a bore Ø80 for the HANGER PIN
    BRACKET        two cheeks (y 300 ± 50..70) on the plate, bores Ø42 about the HEAD SHEAVE's axis
    HEAD SHEAVE    about Y through (8000, 300, 7600): a round groove (radius 20) for the Ø30 wire, its bottom 0.2 under
                   the wire with its middle at radius 150; rim Ø330, width 80, stubs Ø40 out to y = 300 ± 80
    HANGER PIN     Ø80 along Y through the lugs at the PIVOT, y -185..185 with collars Ø120 outside the lugs
    HYDRAULIC POWER UNIT  a box on the plate (x 7550..8350, y -1350..-750, z 7400..7950), chamfered
    HANGER.ASM     turns about the PIVOT (the joint "Tilt")
      HANGER       an arm (x 7900..8100, y ±100, z 5210..6500) with a round top (r 100) about the PIVOT and a bore
                   Ø84 for the HANGER PIN
      LOWER.ASM    slides down away from the hanger (the joint "Lower")
        BLOCK      two cheeks (y ±140..±200, x 7700..8300, z 4300..5100 and round bottoms r 300 about the SHEAVE's
                   axis, bores Ø102), a cross plate on them (y -200..360, z 5100..5200), an EYE
                   (x 7800..7900, y 270..330, z 5200..5400) with a socket Ø31 for the lift wire's end (its bottom at
                   z 5250) and two arms (y ±115..±160, z 4700..4900) aft to the CLAMP's front face
        SHEAVE     about Y through (8000, 0, 4300): a round groove (radius 80) for the Ø120 cable, its bottom 0.2
                   under the cable with its middle at radius 500; rim Ø1080, width 200, stubs Ø100 out to y = ±230
        CLAMP      a box x 6800..7100, y ±150, z 4650..4950; the cable starts on its aft face and runs through it
  CABLE            Ø120: from (6800, 0, 4800) on the clamp's face forward to the sheave's top, round its front (side +1:
                   turning about +Y), the straight that leaves the sheave and meets the horn without a kink, the arc
                   on the horn to vertical at x = -1500, straight down to z = -1000
  LIFT WIRE        Ø30 in the plane y = 300: from (13800, 7750) on the fairlead's face aft to the head sheave's top,
                   a quarter round its aft side (side -1), straight down into the eye's socket to (7850, 5250)

Colours: deck, stays, knee braces, gantry, fairlead grey (0.3); trolley, hanger, block, rail end stops yellow
(0.976, 0.659, 0); horn, sheaves, bracket, clamp, hanger pin steel grey (0.55, 0.57, 0.6); cable near black
(0.13, 0.13, 0.14); lift wire dark grey (0.25, 0.25, 0.27); power unit blue (0.075, 0.267, 0.486).
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_paths import (Arc, Asm, Line, Part, T, _v, box, cut, cyl, fuse, gap, placed, rope_solid, solids,  # noqa
                             tangent, volume, write_step)
from make_test_sea import (BEND_R, CABLE_R, HORN_C, deck_shape, horn_shape,  # noqa: E402
                           horn_stand_shape, stay_places, stay_shape)
from model_details import chamfered_rect  # noqa: E402

from fresing_render.demo_model import geom as G  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402

CLEAR = 0.2                                   # grooves stand this far off the rope's skin
DECK_TOP = 2500.0
SHEAVE_C = (8000.0, 4300.0)                   # (x, z), y = 0
SHEAVE_R = 500.0                              # to the cable's middle
CLAMP_AT = 6800.0                             # the cable's start (x); z = the sheave's top
PIVOT = (8000.0, 6500.0)                      # the hanger's pivot (x, z), along Y
HEAD_C = (8000.0, 7600.0)                     # the head sheave (x, z), y = 300
HEAD_R = 150.0
WIRE_R = 15.0
WIRE_Y = 300.0
FAIRLEAD_AT = 13800.0                         # the lift wire's start (x): on the fairlead's front face
EYE_AT = 5250.0                               # the lift wire's end (z, the bottom of the eye's bore), x = 7850
CABLE_END_Z = -1000.0

NUMBERS = {
    "sheave_centre": (SHEAVE_C[0], 0.0, SHEAVE_C[1]), "sheave_radius": SHEAVE_R, "cable_diameter": 2 * CABLE_R,
    "horn_centre": HORN_C, "bend_radius": BEND_R, "vertical": (HORN_C[0] - BEND_R, 0.0, HORN_C[2]),
    "cable_start": (CLAMP_AT, 0.0, SHEAVE_C[1] + SHEAVE_R), "cable_end": (HORN_C[0] - BEND_R, 0.0, CABLE_END_Z),
    "pivot": (PIVOT[0], 0.0, PIVOT[1]), "travel_axis": (-1.0, 0.0, 0.0), "lower_axis": (0.0, 0.0, -1.0),
    "head_centre": (HEAD_C[0], WIRE_Y, HEAD_C[1]), "head_radius": HEAD_R, "wire_diameter": 2 * WIRE_R,
    "wire_start": (FAIRLEAD_AT, WIRE_Y, HEAD_C[1] + HEAD_R), "wire_end": (HEAD_C[0] - HEAD_R, WIRE_Y, EYE_AT),
}
STAYS_X = (1500.0, 4500.0, 7500.0, 10500.0)
PARTS = ["STERN DECK"] + ["BULWARK STAY"] * 8 + ["HORN", "HORN STAND", "GANTRY"] + ["KNEE BRACE"] * 6 + [
         "RAIL END STOP"] * 4 + ["FAIRLEAD", "TROLLEY", "BRACKET", "HEAD SHEAVE", "HANGER",
         "BLOCK", "SHEAVE", "CLAMP", "HANGER PIN", "HYDRAULIC POWER UNIT", "CABLE", "LIFT WIRE"]
ASSEMBLIES = ["TEST.MOVING", "CARRIER.ASM", "HANGER.ASM", "LOWER.ASM"]

GREY, YELLOW, STEEL = (0.3, 0.3, 0.3), (0.976, 0.659, 0.0), (0.55, 0.57, 0.6)
BLACK, WIRE_GREY, BLUE = (0.13, 0.13, 0.14), (0.25, 0.25, 0.27), (0.075, 0.267, 0.486)
COLOURS = {"STERN DECK": GREY, "BULWARK STAY": GREY, "KNEE BRACE": GREY, "RAIL END STOP": YELLOW, "GANTRY": GREY,
           "FAIRLEAD": GREY, "TROLLEY": YELLOW, "HANGER": YELLOW, "BLOCK": YELLOW,
           "HORN": STEEL, "HORN STAND": GREY, "SHEAVE": STEEL, "HEAD SHEAVE": STEEL, "BRACKET": STEEL, "CLAMP": STEEL,
           "CABLE": BLACK, "LIFT WIRE": WIRE_GREY, "HANGER PIN": STEEL, "HYDRAULIC POWER UNIT": BLUE}


def _angle(p, c):
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))


class Route:
    """A rope's middle in its plane: ``segments`` (lines and arcs, (x, z)), ``start``, ``end``, ``length``."""

    def __init__(self, segments):
        self.segments = segments
        for a, b in zip(segments[:-1], segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-6 and np.linalg.norm(a.end_tangent - b.start_tangent) < 1e-6
        self.start, self.end = segments[0].start, segments[-1].end
        self.length = sum(s.length for s in segments)


def cable_route() -> Route:
    c1, c2 = np.array(SHEAVE_C), np.array((HORN_C[0], HORN_C[2]))
    p1, p2, _t = tangent(c1, SHEAVE_R, 1, c2, BEND_R, -1)
    top = c1 + np.array([0.0, SHEAVE_R])
    a1 = Arc("SHEAVE", c1, SHEAVE_R, 1, 90.0, (90.0 - _angle(p1, c1)) % 360.0)
    a_in = _angle(p2, c2)
    a2 = Arc("HORN", c2, BEND_R, -1, a_in, 180.0 - a_in)
    down = a2.end
    return Route([Line((CLAMP_AT, top[1]), top), a1, Line(a1.end, a2.start), a2,
                  Line(down, (down[0], CABLE_END_Z))])


def wire_route() -> Route:
    c = np.array(HEAD_C)
    top = c + np.array([0.0, HEAD_R])
    arc = Arc("HEAD SHEAVE", c, HEAD_R, -1, 90.0, 90.0)
    return Route([Line((FAIRLEAD_AT, top[1]), top), arc, Line(arc.end, (arc.end[0], EYE_AT))])


def grooved_sheave(r_mid, rope_r, groove_r, rim, half, stub_r, stub_half):
    """About Y through its origin: a disc of radius ``rim`` and width 2 ``half`` with a round groove of radius
    ``groove_r`` (wider than the rope, so the rope runs in and out without touching its sides) whose bottom lies
    CLEAR under a rope of radius ``rope_r`` with its middle at ``r_mid``; stubs of radius ``stub_r`` out to
    ±``stub_half``."""
    disc = fuse(cyl(rim, (0, -half, 0), (0, half, 0)), cyl(stub_r, (0, -stub_half, 0), (0, stub_half, 0)))
    centre = r_mid - rope_r - CLEAR + groove_r
    torus = BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), float(centre), float(groove_r)).Shape()
    return cut(disc, torus)


def gantry_shape():
    parts = [box(-5000, -1600, 6800, 14000, -1400, 7200), box(-5000, 1400, 6800, 14000, 1600, 7200),
             box(13600, -1400, 6800, 13800, 1400, 7200)]
    parts += [box(x0, y0, DECK_TOP, x0 + 200, y0 + 200, 6800) for x0 in (2600.0, 13600.0) for y0 in (-1600.0, 1400.0)]
    return fuse(*parts)


def knee_shape():
    """A knee brace (a plate 20 thick, 400 along the beam, 400 down the post), placed by ``KNEES``."""
    return G.polygon_prism([(0.0, 0.0), (400.0, 0.0), (0.0, 400.0)], 20.0)


# under the beams, centred on them (y ±1500): local x along the beam away from the post, local y down
KNEES = [G.Frame((x, s * 1500.0 - 10.0 * way, 6800.0), (way, 0.0, 0.0), (0.0, way, 0.0))
         for s in (1.0, -1.0) for x, way in ((2600.0, -1.0), (2800.0, 1.0), (13600.0, -1.0))]
END_STOPS = [(x, s * 1500.0) for s in (1.0, -1.0) for x in (-4925.0, 13525.0)]       # on the beams: (x, y) centres


def end_stop_shape():
    """A rail end stop on a beam: 150 x 200 x 150 with a buffer on its face towards the trolley (local x)."""
    return G.fuse(box(-75, -100, 0, 75, 100, 150), cyl(50.0, (75, 0, 75), (105, 0, 75)))


def trolley_shape():
    plate = G.polygon_prism(chamfered_rect(7400.0, -1650.0, 1200.0, 3300.0, 60.0), 190.0, G.T(0.0, 0.0, 7210.0))
    plate = cut(plate, box(7500, WIRE_Y - 50, 7200, 7950, WIRE_Y + 50, 7410))
    parts = [plate]
    for s in (1.0, -1.0):
        parts.append(box(7450, s * 1610, 7050, 8550, s * 1650, 7210))                  # side skirts
        parts += [box(7850, s * 110, PIVOT[1], 8150, s * 170, 7210),
                  cyl(150.0, (PIVOT[0], s * 110, PIVOT[1]), (PIVOT[0], s * 170, PIVOT[1]))]
    return cut(G.fuse(*parts), cyl(40.0, (PIVOT[0], -200, PIVOT[1]), (PIVOT[0], 200, PIVOT[1])))


def hanger_pin_shape():
    return G.fuse(cyl(40.0, (PIVOT[0], -185, PIVOT[1]), (PIVOT[0], 185, PIVOT[1])),
                  cyl(60.0, (PIVOT[0], 170, PIVOT[1]), (PIVOT[0], 185, PIVOT[1])),
                  cyl(60.0, (PIVOT[0], -185, PIVOT[1]), (PIVOT[0], -170, PIVOT[1])))


def power_unit_shape():
    return G.polygon_prism(chamfered_rect(7550.0, -1350.0, 800.0, 600.0, 40.0), 550.0, G.T(0.0, 0.0, 7400.0))


def hanger_shape():
    arm = G.fuse(box(7900, -100, 5210, 8100, 100, PIVOT[1]),
                 cyl(100.0, (PIVOT[0], -100, PIVOT[1]), (PIVOT[0], 100, PIVOT[1])))
    return cut(arm, cyl(42.0, (PIVOT[0], -200, PIVOT[1]), (PIVOT[0], 200, PIVOT[1])))


def bracket_shape():
    cheeks = [box(7850, WIRE_Y + s0, 7400, 8150, WIRE_Y + s1, 7700) for s0, s1 in ((-70, -50), (50, 70))]
    base = box(7900, WIRE_Y - 70, 7400, 8150, WIRE_Y + 70, 7410)
    bore = cyl(21.0, (HEAD_C[0], WIRE_Y - 100, HEAD_C[1]), (HEAD_C[0], WIRE_Y + 100, HEAD_C[1]))
    return cut(fuse(base, *cheeks), bore)


def block_shape():
    sx, sz = SHEAVE_C
    parts = [box(7700, -200, 5100, 8300, 360, 5200), box(7800, WIRE_Y - 30, 5200, 7900, WIRE_Y + 30, 5400)]
    for s in (1.0, -1.0):
        parts += [box(7700, s * 140, sz, 8300, s * 200, 5100), cyl(300.0, (sx, s * 140, sz), (sx, s * 200, sz)),
                  box(CLAMP_AT + 300, s * 115, 4700, 7720, s * 160, 4900)]          # an arm aft to the clamp
    bore = cyl(51.0, (sx, -300, sz), (sx, 300, sz))
    socket = cyl(WIRE_R + 0.5, (HEAD_C[0] - HEAD_R, WIRE_Y, EYE_AT), (HEAD_C[0] - HEAD_R, WIRE_Y, 5500))
    return cut(G.fuse(*parts), bore, socket)


def clamp_shape():
    return box(CLAMP_AT, -150, 4650, CLAMP_AT + 300, 150, 4950)


def model():
    root = Asm("TEST.MOVING")
    root.add(Part("STERN DECK", deck_shape(14000.0, ()), GREY))              # (no seams: the file stays < 400 KB)
    stay = Part("BULWARK STAY", stay_shape(), GREY)
    for m in stay_places(STAYS_X):
        root.add(stay, m)
    root.add(Part("HORN", horn_shape(), STEEL))
    root.add(Part("HORN STAND", horn_stand_shape(), GREY))
    root.add(Part("GANTRY", gantry_shape(), GREY))
    knee = Part("KNEE BRACE", knee_shape(), GREY)
    for m in KNEES:
        root.add(knee, m)
    stop = Part("RAIL END STOP", end_stop_shape(), YELLOW)
    for x, y in END_STOPS:
        root.add(stop, T(x, y, 7200.0) if x < 0 else T(x, y, 7200.0) @ np.diag([-1.0, -1.0, 1.0, 1.0]))
    root.add(Part("FAIRLEAD", fuse(box(13600, WIRE_Y - 80, 7200, 13700, WIRE_Y + 80, 7850),
                                   box(FAIRLEAD_AT - 300, WIRE_Y - 80, 7650, FAIRLEAD_AT, WIRE_Y + 80, 7850)), GREY))
    carrier = Asm("CARRIER.ASM")
    carrier.add(Part("TROLLEY", trolley_shape(), YELLOW))
    carrier.add(Part("BRACKET", bracket_shape(), STEEL))
    carrier.add(Part("HEAD SHEAVE", grooved_sheave(HEAD_R, WIRE_R, 20.0, 165.0, 40.0, 20.0, 80.0), STEEL),
                T(HEAD_C[0], WIRE_Y, HEAD_C[1]))
    hanger = Asm("HANGER.ASM")
    hanger.add(Part("HANGER", hanger_shape(), YELLOW))
    lower = Asm("LOWER.ASM")
    lower.add(Part("BLOCK", block_shape(), YELLOW))
    lower.add(Part("SHEAVE", grooved_sheave(SHEAVE_R, CABLE_R, 80.0, 540.0, 100.0, 50.0, 230.0), STEEL),
              T(SHEAVE_C[0], 0.0, SHEAVE_C[1]))
    lower.add(Part("CLAMP", clamp_shape(), STEEL))
    hanger.add(lower)
    carrier.add(hanger)
    carrier.add(Part("HANGER PIN", hanger_pin_shape(), STEEL))
    carrier.add(Part("HYDRAULIC POWER UNIT", power_unit_shape(), BLUE))
    root.add(carrier)
    root.add(Part("CABLE", rope_solid(cable_route(), CABLE_R), BLACK))
    root.add(Part("LIFT WIRE", rope_solid(wire_route(), WIRE_R), WIRE_GREY), T(0.0, WIRE_Y, 0.0))
    return root


def count_parts(root):
    return len(placed(root))


def check(root, say=print):
    """Raises AssertionError with a plain reason when the model is not as described."""
    items = placed(root)
    assert [n for n, _p_, _s in items] == PARTS, [n for n, _p_, _s in items]
    for name, _path, shape in items:
        assert solids(shape) == 1 and volume(shape) > 1.0, name
    by = {n: s for n, _p, s in items if n not in ("BULWARK STAY", "KNEE BRACE", "RAIL END STOP")}
    paths = {n: p for n, p, _s in items}
    assert paths["SHEAVE"] == ["TEST.MOVING", "CARRIER.ASM", "HANGER.ASM", "LOWER.ASM"], paths["SHEAVE"]
    for rope, on, tol in (("CABLE", "HORN", 1.0), ("CABLE", "SHEAVE", 1.0), ("LIFT WIRE", "HEAD SHEAVE", 1.0)):
        d = gap(by[rope], by[on])
        assert CLEAR - 1e-3 <= d <= tol, (rope, on, "the rope must rest on it within", tol, d)
    for rope, holder, r, length in (("CABLE", "CLAMP", CABLE_R, 300.0), ("LIFT WIRE", "FAIRLEAD", WIRE_R, 300.0)):
        inside = volume(BRepAlgoAPI_Common(by[rope], by[holder]).Shape())
        assert inside > 0.9 * math.pi * r * r * length, (rope, "starts or ends in", holder, inside)
    assert gap(by["LIFT WIRE"], by["BLOCK"]) < 1e-3, "the lift wire ends on the bottom of the eye's socket"
    meant = {("HORN STAND", "STERN DECK"), ("HORN STAND", "HORN"), ("GANTRY", "STERN DECK"), ("GANTRY", "FAIRLEAD"),
             ("TROLLEY", "BRACKET"), ("CABLE", "CLAMP"), ("LIFT WIRE", "FAIRLEAD"), ("LIFT WIRE", "BLOCK"),
             ("BLOCK", "CLAMP"), ("TROLLEY", "HANGER PIN"), ("TROLLEY", "HYDRAULIC POWER UNIT"),
             ("BULWARK STAY", "STERN DECK"), ("KNEE BRACE", "GANTRY"),
             ("RAIL END STOP", "GANTRY")}
    least = (1e9, "")
    for i, (na, _pa, sa) in enumerate(items):
        for nb, _pb, sb in items[i + 1:]:
            if (na, nb) in meant or (nb, na) in meant:
                continue
            d = gap(sa, sb)
            assert d > 0.05, ("parts touch or overlap where not meant", na, nb, d)
            least = min(least, (d, f"{na} - {nb}"))
    say(f"  least gap between parts that are not meant to touch: {least[0]:.2f} mm ({least[1]})")
    for rope, held in (("CABLE", ("CLAMP", "SHEAVE", "HORN", "HORN STAND")),
                       ("LIFT WIRE", ("FAIRLEAD", "HEAD SHEAVE", "BLOCK", "BRACKET", "TROLLEY"))):  # (as before 0122)
        away = min((gap(by[rope], s), n) for n, _p_, s in items if n not in held + ("CABLE", "LIFT WIRE"))
        assert away[0] >= 50.0, (rope, "a part is too near it", away)
        say(f"  every part {rope} does not rest on or start in is {away[0]:.0f} mm or more from it ({away[1]})")


def numbers(say=print):
    for k, v in NUMBERS.items():
        say(f"{k}: {v}")
    say(f"cable length: {cable_route().length:.3f}, lift wire length: {wire_route().length:.3f}")


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
