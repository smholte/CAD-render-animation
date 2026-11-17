"""Write the test model for a sheave on a swivel head as a STEP assembly (task 0172; generic, invented).

    python tools/make_test_swivel.py out.step   TEST.SWIVEL  (tests/data/test_swivel.step, copy in fresing_render/data/)
    python tools/make_test_swivel.py numbers    prints the numbers below and the swivel's angle along the slew

A deck davit. Its post turns on a pedestal (the joint "Slew", about the vertical axis through the origin); at the
end of its arm a swivel head hangs, free to turn about a vertical axis through the arm's tip (the joint "Swivel").
The head carries a sheave whose groove passes over the swivel's axis: the wire comes from a fairlead on the deck,
off the slew axis, up to the sheave, over its top and straight down ALONG the swivel's axis into a hook block. As
the davit slews, the fairlead is seen from the arm's tip in another direction, and the swivel must turn so the wire
comes in in the sheave's plane (``swivel_angle(slew)``: -22.5° … +22.5° over a slew of +45° … -45°, half the slew
the other way, since the fairlead is as far from the slew axis as the tip).

mm, Z up. The slew axis is the Z axis, the swivel axis the vertical line through (3000, 0). Every part is one solid.

  DECK             a plate x -1500..4500, y -3800..2000, z -200..0
  PEDESTAL         Ø700, z 0..500, on a foot plate 900 x 900 x 30 (chamfered)
  FAIRLEAD         a post Ø200 on a foot plate 400 x 400 x 30 at (0, -3000), its top (chamfered) at z 800; the wire
                   starts on the middle of its top face, (0, -3000, 800)
  DAVIT.ASM        turns about the Z axis (the joint "Slew")
    DAVIT          the post Ø400 from z 502 (2 above the pedestal) up to z 3600, the arm (y ±150, z 3300..3600)
                   from the post out to a round end Ø300 about the swivel axis with a bore Ø124 for the head's
                   shaft, and a knee (40 thick, 1000 x 1000) under the arm beside the post: one solid
    HOOK BLOCK     a block x 2850..3150, y ±100, z 1000..1400 (chamfered) on the swivel axis with a socket Ø21 for the
                   wire's end (its bottom at z 1350), a shank Ø80 below and an eye (ring of radius 80, bar Ø50)
    SWIVEL HEAD.ASM  turns about the swivel axis (the joint "Swivel"); drawn turned by BETA = -135° about it (local x
                     towards the fairlead, local y along the sheave's axis):
      SWIVEL HEAD  a bearing disc Ø500 (z 3200..3298, 2 under the arm), a shaft Ø120 up through the arm's bore
                   (2 all round) to a collar Ø200 (z 3602..3640, 2 above the arm), and two cheeks (local x 200..400,
                   local y ±45..±65, z 2780..3200) with a bore Ø50 for the SHEAVE PIN
      SHEAVE PIN   Ø50 along local y through the cheeks at (local x 300, z 2850), y ±85, collars Ø80 at ±65..±75
      SHEAVE       about local y through (local x 300, z 2850): a round groove (radius 20) for the Ø20 wire, its
                   bottom 0.2 under the wire with its middle at radius 300 (SHEAVE_R); rim Ø640, width 80, hub
                   Ø90 out to ±44 (1 from the cheeks), a bore Ø52 on the pin (1 all round)
  WIRE             Ø20 in the sheave's plane (local y = 0): from the fairlead's top up to the sheave (a straight that
                   meets it without a kink), over its top (side -1: towards the swivel axis), straight down the
                   swivel axis into the hook block's socket to (3000, 0, 1350)

Colours: deck, pedestal, fairlead grey (0.3); davit, swivel head yellow (0.976, 0.659, 0); sheave, pin steel grey
(0.55, 0.57, 0.6); wire dark grey (0.25, 0.25, 0.27); hook block orange (0.9, 0.35, 0.05).

The wire's length between the fairlead and the hook block changes as the davit slews (4.2 m to the sheave as drawn,
2.3 m at -45°, 5.5 m at +45°): in the app its winch keeps it tight. Checked before the file is written (``check``):
every part one solid; the wire rests on the sheave (0.2), starts on the fairlead and ends on the socket's bottom;
nothing else touches where not meant; with the swivel turned to -60, -30, +30, +60° (relative to as drawn) the head
and the sheave stay 1 mm and more from the davit; with the davit slewed to ±45° it stays 1 mm and more from the
pedestal, the deck and the fairlead.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_test_moving import Route, grooved_sheave  # noqa: E402
from make_test_paths import (Arc, Asm, Line, Part, T, box, cut, cyl, fuse, gap, placed, prism,  # noqa: E402
                             rope_solid, solids, tangent, volume, write_step)
from model_details import chamfered_rect  # noqa: E402

from fresing_render.demo_model import geom as G  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402

CLEAR = 0.2                                   # the groove's bottom stands this far off the wire's skin
TIP = (3000.0, 0.0)                           # the swivel axis (x, y), vertical
FAIRLEAD_AT = (0.0, -3000.0)                  # the fairlead post's axis (x, y)
FAIRLEAD_TOP = 800.0                          # the wire starts here, on the middle of the post's top face
SHEAVE_R = 300.0                              # the sheave's centre is this far off the swivel axis = radius to the
SHEAVE_Z = 2850.0                             # … wire's middle; its centre's height
WIRE_R = 10.0
WIRE_END = 1350.0                             # the wire's end (z, the bottom of the hook block's socket), on the axis
ARM = (3300.0, 3600.0)                        # the arm's underside and top
POST_FOOT = 502.0                             # the davit's post starts here, 2 above the pedestal
DISC = (3200.0, 3298.0)                       # the swivel head's bearing disc (z)
SLEW_RANGE = 45.0                             # the model is made for the davit slewed ±45°


def _beta() -> float:
    """Degrees: the direction from the arm's tip to the fairlead as drawn (from +X towards +Y)."""
    return math.degrees(math.atan2(FAIRLEAD_AT[1] - TIP[1], FAIRLEAD_AT[0] - TIP[0]))


BETA = _beta()                                # -135°: the swivel head is drawn turned by this about its axis
HEAD_M = T(TIP[0], TIP[1], 0.0) @ G.Rot((0.0, 0.0, 1.0), BETA)     # SWIVEL HEAD.ASM's place in DAVIT.ASM

NUMBERS = {
    "slew_axis": ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)), "swivel_axis": ((TIP[0], TIP[1], 0.0), (0.0, 0.0, 1.0)),
    "swivel_drawn": BETA, "sheave_radius": SHEAVE_R, "wire_diameter": 2 * WIRE_R,
    "sheave_centre": (TIP[0] + SHEAVE_R * math.cos(math.radians(BETA)),
                      TIP[1] + SHEAVE_R * math.sin(math.radians(BETA)), SHEAVE_Z),
    "wire_start": (FAIRLEAD_AT[0], FAIRLEAD_AT[1], FAIRLEAD_TOP), "wire_end": (TIP[0], TIP[1], WIRE_END),
    "arm_top": ARM[1], "slew_range": SLEW_RANGE,
}
PARTS = ["DECK", "PEDESTAL", "FAIRLEAD", "DAVIT", "HOOK BLOCK", "SWIVEL HEAD", "SHEAVE PIN", "SHEAVE", "WIRE"]
ASSEMBLIES = ["TEST.SWIVEL", "DAVIT.ASM", "SWIVEL HEAD.ASM"]

GREY, YELLOW, STEEL = (0.3, 0.3, 0.3), (0.976, 0.659, 0.0), (0.55, 0.57, 0.6)
WIRE_GREY, ORANGE = (0.25, 0.25, 0.27), (0.9, 0.35, 0.05)
COLOURS = {"DECK": GREY, "PEDESTAL": GREY, "FAIRLEAD": GREY, "DAVIT": YELLOW, "SWIVEL HEAD": YELLOW,
           "SHEAVE": STEEL, "SHEAVE PIN": STEEL, "WIRE": WIRE_GREY, "HOOK BLOCK": ORANGE}


# ---------------------------------------------------------------------------------------------------------
# the numbers the app should find
# ---------------------------------------------------------------------------------------------------------

def tip_at(slew: float) -> np.ndarray:
    """(x, y) of the swivel axis with the davit slewed ``slew`` degrees (about +Z)."""
    a = math.radians(slew)
    return np.array([TIP[0] * math.cos(a) - TIP[1] * math.sin(a), TIP[0] * math.sin(a) + TIP[1] * math.cos(a)])


def swivel_angle(slew: float) -> float:
    """Degrees the swivel turns (about +Z, from as drawn) so the sheave's plane holds the fairlead again, with the
    davit slewed ``slew`` degrees: the fairlead's direction from the tip minus the slew minus as drawn."""
    d = np.asarray(FAIRLEAD_AT) - tip_at(slew)
    v = math.degrees(math.atan2(d[1], d[0])) - slew - BETA
    return (v + 180.0) % 360.0 - 180.0


def free_run(slew: float) -> float:
    """mm from the fairlead's top to the sheave's centre with the davit slewed (the straight run's length changes
    with it: the winch keeps the wire tight)."""
    d = float(np.linalg.norm(np.asarray(FAIRLEAD_AT) - tip_at(slew))) - SHEAVE_R
    return math.hypot(d, SHEAVE_Z - FAIRLEAD_TOP)


def wire_route() -> Route:
    """The wire's middle in the sheave's plane: (u, z), u = along the head's local x (from the swivel axis towards
    the fairlead as drawn)."""
    u_f = float(np.linalg.norm(np.asarray(FAIRLEAD_AT) - np.asarray(TIP)))
    c = np.array([SHEAVE_R, SHEAVE_Z])
    p1, p2, _t = tangent(np.array([u_f, FAIRLEAD_TOP]), 0.0, 1, c, SHEAVE_R, -1)
    a_in = math.degrees(math.atan2(p2[1] - c[1], p2[0] - c[0]))
    arc = Arc("SHEAVE", c, SHEAVE_R, -1, a_in, (180.0 - a_in) % 360.0)
    return Route([Line(p1, p2), arc, Line(arc.end, (0.0, WIRE_END))])


# ---------------------------------------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------------------------------------

def pedestal_shape():
    foot = G.polygon_prism(chamfered_rect(-450.0, -450.0, 900.0, 900.0, 80.0), 30.0)
    return fuse(foot, cyl(350.0, (0, 0, 0), (0, 0, 500.0)))


def fairlead_shape():
    x, y = FAIRLEAD_AT
    foot = G.polygon_prism(chamfered_rect(x - 200.0, y - 200.0, 400.0, 400.0, 40.0), 30.0)
    post = cyl(100.0, (x, y, 0.0), (x, y, FAIRLEAD_TOP - 20.0))
    return fuse(foot, post, G.cone(100.0, 70.0, 20.0, (x, y, FAIRLEAD_TOP - 20.0)))


def davit_shape():
    tx, ty = TIP
    post = cyl(200.0, (0, 0, POST_FOOT), (0, 0, ARM[1]))
    arm = fuse(box(0.0, -150.0, ARM[0], tx, 150.0, ARM[1]), cyl(150.0, (tx, ty, ARM[0]), (tx, ty, ARM[1])))
    knee = prism([(150.0, -20.0, ARM[0]), (1150.0, -20.0, ARM[0]), (150.0, -20.0, ARM[0] - 1000.0)],
                  (0.0, 40.0, 0.0))
    return cut(fuse(post, arm, knee), cyl(62.0, (tx, ty, ARM[0] - 10.0), (tx, ty, ARM[1] + 10.0)))


def hook_block_shape():
    tx, ty = TIP
    block = G.polygon_prism(chamfered_rect(tx - 150.0, ty - 100.0, 300.0, 200.0, 30.0), 400.0, T(0.0, 0.0, 1000.0))
    shank = cyl(40.0, (tx, ty, 780.0), (tx, ty, 1001.0))
    eye = BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(tx, ty, 700.0), gp_Dir(0, 1, 0)), 80.0, 25.0).Shape()
    socket = cyl(WIRE_R + 0.5, (tx, ty, WIRE_END), (tx, ty, 1500.0))
    return cut(fuse(block, shank, eye), socket)


def swivel_head_shape():
    """In the head's own coordinates: the swivel axis is local z through the origin, the sheave's centre at
    (SHEAVE_R, 0, SHEAVE_Z), its axis along local y."""
    disc = cyl(250.0, (0, 0, DISC[0]), (0, 0, DISC[1]))
    shaft = cyl(60.0, (0, 0, DISC[1] - 1.0), (0, 0, ARM[1] + 2.0))
    collar = cyl(100.0, (0, 0, ARM[1] + 2.0), (0, 0, ARM[1] + 40.0))
    cheeks = [box(SHEAVE_R - 100.0, s * 45.0, SHEAVE_Z - 70.0, SHEAVE_R + 100.0, s * 65.0, DISC[0] + 1.0)
              for s in (1.0, -1.0)]
    bore = cyl(25.0, (SHEAVE_R, -100.0, SHEAVE_Z), (SHEAVE_R, 100.0, SHEAVE_Z))
    return cut(fuse(disc, shaft, collar, *cheeks), bore)


def pin_shape():
    x, z = SHEAVE_R, SHEAVE_Z
    return fuse(cyl(25.0, (x, -85.0, z), (x, 85.0, z)), cyl(40.0, (x, 65.0, z), (x, 75.0, z)),
                cyl(40.0, (x, -75.0, z), (x, -65.0, z)))


def sheave_shape():
    """About local y through the origin (placed at (SHEAVE_R, 0, SHEAVE_Z))."""
    s = grooved_sheave(SHEAVE_R, WIRE_R, 20.0, SHEAVE_R + 20.0, 40.0, 45.0, 44.0)
    return cut(s, cyl(26.0, (0, -60.0, 0), (0, 60.0, 0)))


def model():
    root = Asm("TEST.SWIVEL")
    root.add(Part("DECK", box(-1500, -3800, -200, 4500, 2000, 0), GREY))
    root.add(Part("PEDESTAL", pedestal_shape(), GREY))
    root.add(Part("FAIRLEAD", fairlead_shape(), GREY))
    davit = Asm("DAVIT.ASM")
    davit.add(Part("DAVIT", davit_shape(), YELLOW))
    davit.add(Part("HOOK BLOCK", hook_block_shape(), ORANGE))
    head = Asm("SWIVEL HEAD.ASM")
    head.add(Part("SWIVEL HEAD", swivel_head_shape(), YELLOW))
    head.add(Part("SHEAVE PIN", pin_shape(), STEEL))
    head.add(Part("SHEAVE", sheave_shape(), STEEL), T(SHEAVE_R, 0.0, SHEAVE_Z))
    davit.add(head, HEAD_M)
    root.add(davit)
    root.add(Part("WIRE", rope_solid(wire_route(), WIRE_R), WIRE_GREY), HEAD_M)
    return root


def count_parts(root):
    return len(placed(root))


def check(root, say=print):
    """Raises AssertionError with a plain reason when the model is not as described."""
    items = placed(root)
    assert [n for n, _p, _s in items] == PARTS, [n for n, _p, _s in items]
    for name, _path, shape in items:
        assert solids(shape) == 1 and volume(shape) > 1.0, name
    by = {n: s for n, _p, s in items}
    paths = {n: p for n, p, _s in items}
    assert paths["SHEAVE"] == ["TEST.SWIVEL", "DAVIT.ASM", "SWIVEL HEAD.ASM"], paths["SHEAVE"]
    d = gap(by["WIRE"], by["SHEAVE"])
    assert CLEAR - 1e-3 <= d <= 1.0, ("the wire must rest on the sheave", d)
    assert gap(by["WIRE"], by["FAIRLEAD"]) < 1e-3, "the wire starts on the fairlead's top"
    assert gap(by["WIRE"], by["HOOK BLOCK"]) < 1e-3, "the wire ends on the bottom of the hook block's socket"
    meant = {("DECK", "PEDESTAL"), ("DECK", "FAIRLEAD"), ("WIRE", "FAIRLEAD"), ("WIRE", "HOOK BLOCK"),
             ("SWIVEL HEAD", "SHEAVE PIN")}
    least = (1e9, "")
    for i, (na, _pa, sa) in enumerate(items):
        for nb, _pb, sb in items[i + 1:]:
            if (na, nb) in meant or (nb, na) in meant or "WIRE" in (na, nb) and "SHEAVE" in (na, nb):
                continue
            g = gap(sa, sb)
            assert g >= 0.99, ("parts touch or overlap where not meant", na, nb, g)
            least = min(least, (g, f"{na} - {nb}"))
    say(f"  least gap between parts that are not meant to touch: {least[0]:.2f} mm ({least[1]})")
    away = min((gap(by["WIRE"], s), n) for n, _p, s in items
               if n not in ("WIRE", "FAIRLEAD", "SHEAVE", "HOOK BLOCK"))
    assert away[0] >= 30.0, ("a part is too near the wire", away)
    say(f"  every part the wire does not rest on or end in is {away[0]:.0f} mm or more from it ({away[1]})")
    # the moving bodies at other angles: the head against the davit, the davit against what stands on the deck
    head_parts, davit_parts = ("SWIVEL HEAD", "SHEAVE PIN", "SHEAVE"), ("DAVIT", "HOOK BLOCK")
    for turn in (-60.0, -30.0, 30.0, 60.0):
        moved = {n: s for n, _p, s in placed(root, {"SWIVEL HEAD.ASM": HEAD_M @ G.Rot((0, 0, 1), turn)})}
        g = min(gap(moved[a], moved[b]) for a in head_parts for b in davit_parts)
        assert g >= 0.99, ("the swivel head comes near the davit", turn, g)
    for slew in (-SLEW_RANGE, SLEW_RANGE):
        moved = {n: s for n, _p, s in placed(root, {"DAVIT.ASM": G.Rot((0, 0, 1), slew)})}
        g = min(gap(moved[a], moved[b]) for a in davit_parts + head_parts for b in ("DECK", "PEDESTAL", "FAIRLEAD"))
        assert g >= 0.99, ("the davit comes near the deck, the pedestal or the fairlead", slew, g)
    say("  the head turned ±30°, ±60° and the davit slewed ±45°: 1 mm and more from what they move against")


def numbers(say=print):
    for k, v in NUMBERS.items():
        say(f"{k}: {v}")
    r = wire_route()
    say(f"wire length: {r.length:.3f} (wrap on the sheave {r.segments[1].wrap:.3f}°)")
    for slew in (-45.0, -22.5, 0.0, 22.5, 45.0):
        say(f"slew {slew:+6.1f}°: swivel {swivel_angle(slew):+8.3f}°, fairlead -> sheave {free_run(slew):9.3f}")


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
