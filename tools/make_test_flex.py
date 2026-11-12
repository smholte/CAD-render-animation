"""Write the two test models for hoses, cables and drag chains as STEP assemblies (task 0058; generic, invented).

    python tools/make_test_flex.py hoses  out.step [A|B]    TEST.FLEX.HOSES   (tests/data/test_flex_hoses_a / _b.step)
    python tools/make_test_flex.py chains out.step          TEST.FLEX.GANTRY  (tests/data/test_flex_chains_a.step)
    python tools/make_test_flex.py numbers                  prints the numbers below from the geometry

All sizes in mm, Z up. Every part is one solid. Each maker checks its own model before it writes it (``check_…``):
no part lies inside another; parts that move against each other do not touch (0.2 mm in the pin bores, 1 mm and
more elsewhere) as drawn and at the ends of the travel; a hose touches its two fittings and nothing else (3 mm and
more); the hoses are long enough for the whole motion; the chains never run out of links. The numbers are also in
the code (``hose_routes``, ``hose_ends``, ``hose_motion``, ``cylinder``, ``CHAINS``, ``chain_pins``, ``chain_runs``)
for tests to use.

======================================================================================================================
TEST.FLEX.HOSES – a small luffing arm with hydraulics                 29 parts (revision B: 30), each its own shape
======================================================================================================================
  BASE                         box 1200 x 600 x 100: x 0..1200, y -150..450, z 0..100
  POST                         carries the arm's pivot (100, *, 600), axis along Y: a block up to z 500 and a fork
                               (cheeks y 115..145 and 255..285, bore Ø40.4) the arm turns in
  BASE.BRACKET                 two lugs (y 120..145 and 255..280) on a foot, bore Ø40: carries the barrel pin
  BASE.PIN                     Ø40 along Y through the barrel pin (300, *, 170) (pick target)
  VALVE BLOCK                  box x 280..460, y -110..-30, z 100..200; three ports on top
  FITTING VALVE A / B / C      hex stubs on the block's top at (310 / 370 / 430, -70), z 200..220 (A and B 24 across
                               flats, C 30); end face up
  RAIL                         box x 100..560, y 320..380, z 100..130: the slide's rail, along X
  ARM.ASM                      turns about the pivot; drawn level, the middle of its range -20° .. +20°
    ARM                        box 1250 x 100 x 100 along X, from 50 behind the pivot to 1200 in front of it
    ARM.PIN                    Ø40 along Y at the pivot (pick target for the arm's joint)
    ARM.BRACKET                under the arm: a plate with two lugs, carries the rod pin
    ARM.ROD.PIN                Ø40 along Y through the rod pin, (800, *, -150) from the pivot = (900, *, 450) (pick)
    FITTING ARM                hex stub (30 across flats) on the arm's side 900 from the pivot, y 150 -> 120; end
                               face (1000, 120, 600), looking along -Y
    CABLE GLAND ARM            block 30 x 24 x 24 on the arm's other side, 1085..1115 from the pivot; the cable
                               leaves its face (1185, 262, 600) along -X
    ARM.LAMP                   revision B only: a ball Ø60 on top of the arm, 1100 from the pivot
  CYL.ASM                      one cylinder at y = 200 in the pattern of tools/make_test_cylinder.py: barrel pin
                               (300, 170), rod pin (900, 450); pin to pin 662.12, 25.02° up from level
    CYL.BARREL                 BARREL.CAP (end cap + eye, bore Ø40.4), BARREL.TUBE (Ø100/80, 40..418 from the pin),
                               BARREL.GLAND (418..448, bore Ø32), FITTING BARREL A and B (hex stubs 24 across
                               flats on the tube's side, 90 and 384 from the pin, y 150 -> 125; end faces
                               (381.56, 125, 208.06) and (647.97, 125, 332.39), looking along -Y)
    CYL.ROD                    PISTON (Ø78, 214..244 from the pin), ROD (Ø30), ROD.EYE (bore Ø40.4)
  SLIDE.ASM                    slides along X on the rail (1 mm above it); drawn at mid travel, -150 .. +150
    SLIDE CARRIAGE             block x 270..390, y 310..390, z 131..171 with a post 40 x 40 up to z 641
    SLIDE GLAND                round stub Ø22 on the post, x 350 -> 375; the cable leaves its face (375, 350, 620)
                               along +X
  HYDRAULIC HOSE ARM, HYDRAULIC HOSE CYL A, HYDRAULIC HOSE CYL B, CABLE
                               directly under the root (as bought-in hoses usually are), each one solid: a round
                               bar swept along straight pieces and arcs that meet smoothly (in 3D). Every end is
                               straight for 2 diameters and lies flat on its fitting's face (touching, not inside).

The motion.  Arm: about Y through (100, *, 600); +20° is tip up (a joint about +Y turns it down: there -20°). The
cylinder then goes from 500.69 to 824.78 pin to pin (drawn 662.12): its piston can go 174 in and 174 out (closed
length 488.12, full stroke 348), which lets the arm go from -21.7° to +21.4°. Slide: along X, -150 .. +150.

Hoses. End 0 is the first fitting named; "out" is the direction the hose leaves that fitting; lengths are exact.

  HYDRAULIC HOSE ARM      Ø20   length 1008.54   tightest bend (centreline) 164.9
      end 0  (430, -70, 220)        out (0, 0, 1)    touches FITTING VALVE C  (on the VALVE BLOCK)
      end 1  (1000, 120, 600)       out (0, -1, 0)   touches FITTING ARM      (in ARM.ASM: across the arm's pivot)
      revision B: the same ends on a wider path, length 1058.99 (5.0 % longer), tightest bend 152.5
  HYDRAULIC HOSE CYL A    Ø16   length  450.40   tightest bend 59.1
      end 0  (310, -70, 220)        out (0, 0, 1)    touches FITTING VALVE A
      end 1  (381.56, 125, 208.06)  out (0, -1, 0)   touches FITTING BARREL A (in CYL.BARREL: turns with the barrel)
  HYDRAULIC HOSE CYL B    Ø16   length  551.52   tightest bend 105.3
      end 0  (370, -70, 220)        out (0, 0, 1)    touches FITTING VALVE B
      end 1  (647.97, 125, 332.39)  out (0, -1, 0)   touches FITTING BARREL B
  CABLE                   Ø10   length 1062.59   tightest bend 198.0; 1.30 x the distance between its ends
      end 0  (375, 350, 620)        out (1, 0, 0)    touches SLIDE GLAND      (in SLIDE.ASM)
      end 1  (1185, 262, 600)       out (-1, 0, 0)   touches CABLE GLAND ARM  (in ARM.ASM, near the tip); it hangs
                                                     between them, lowest about (790, 306, 330)

Checked over the arm's -20° .. +20° and the slide's -150 .. +150: the two ends are never further apart than the
hose is long. "Spare" = length - the two straight ends - the distance between the ends of those straight pieces:

  HYDRAULIC HOSE ARM      ends 710.9 apart as drawn, 554.3 .. 880.4 over the motion; spare  87.0 (arm +20°)
  HYDRAULIC HOSE CYL A    ends 208.1 apart as drawn, 203.1 .. 216.0;                 spare 188.3 (arm -20°)
  HYDRAULIC HOSE CYL B    ends 357.7 apart as drawn, 356.1 .. 371.4;                 spare 127.0 (arm -20°)
  CABLE                   ends 815.0 apart as drawn, 665.9 .. 980.3;                 spare  78.7 (arm -20°,
                                                                                     slide -150)
With the arm down 20° and the slide at +150 the cable's ends are 717 apart: 346 mm of slack, it then hangs down to
about the base. The app does not lay hoses on parts (not in task 0058): a tour looks best with the arm at -10° or up.

Revision B: ARM.LAMP in ARM.ASM, the four hoses placed in the other order, HYDRAULIC HOSE ARM on a wider path.

======================================================================================================================
TEST.FLEX.GANTRY – a gantry router with a drag chain on every axis                    62 parts, 16 different shapes
======================================================================================================================
The machine is the one of tools/make_test_gantry.py without the carousel (same names and sizes, but 1 mm of air
between parts that slide on each other), so the CNC machine set-up and a G-code program can drive it:

  BED                          box 800 x 600 x 40 (top at z = 0)
  STOCK 300x200x30             the workpiece: x -150..150, y -100..100, z 0..30
  CHAIN TRAY Y                 shelf beside the bed for the Y chain: x 400..640, y -260..210, z -50..-40
  CHAIN BRACKET Y FIXED        block on the tray behind the Y chain's first link
  CHAIN Y.ASM                  16 x CHAIN LINK (the bed is this chain's fixed side)
  Y.ASM                        the gantry: moves along Y
    GANTRY SIDE L / R          boxes x -410..-390 and 390..410, y 40..100, z 1..260
    BEAM                       box between them, y 40..100, z 200..260
    CHAIN BRACKET X FIXED      block on the beam behind the X chain's first link
    CHAIN BRACKET Y MOVING     tab on GANTRY SIDE R over the Y chain's last link
    CHAIN X.ASM                18 x CHAIN LINK (the beam is this chain's fixed side)
    X.ASM                      moves along X on the beam
      CARRIAGE                 plate x -50..50, y 26..39, z 150..260
      CHAIN BRACKET X MOVING   post on the carriage with a tab over the X chain's last link
      CHAIN BRACKET Z FIXED    bar from the carriage with a tab under the Z chain's first link
      CHAIN Z.ASM              13 x CHAIN LINK (the carriage is this chain's fixed side)
      Z.ASM                    moves along Z
        SPINDLE                cylinder Ø50, z 110..230
        TOOL T1 FLAT D6        flat end mill Ø6 x 30, tip at (0, 0, 80), 50 above the stock
        CHAIN BRACKET Z MOVING shelf on the spindle under the Z chain's last link

Travel checked (nothing but the tool touches anything): X -150 .. +150, Y -100 .. +100, Z -50 .. +60 (at -50 the
tool's tip is on the stock's top; the Z chain is laid out for -60 .. +60).

CHAIN LINK (one shape, placed 47 times): a frame of two side plates (4 thick) joined by a bar at the top and one at
the bottom; 32 long, 60 wide, 20 high. The solid's own origin is a lower corner: the body is x 0..32, y 0..60,
z 0..20, and the two pins (a notion: where the link hinges on its neighbours) are at (-4, 30, 10) and (36, 30, 10),
40 apart: **pitch 40**. The link from pin i to pin i + 1 has its own x along that line, its z across the run (on the
fixed run: towards the moving run) and its y along the bend's axis. On a straight run neighbours are 8 mm apart; in
the bend each link is turned 28.955° (2 asin(40 / 160)) against the one before and the corners are 2.75 mm apart.

Each chain, in its own plane: pins 0 .. k on the fixed run's line, 40 apart; pin k is where a circle of **radius
80** touches that line; the next six pins lie on that circle, 28.955° apart; the next lies on the line 160 from the
first (40 from the last pin on the circle) and the rest follow on it, back towards the fixed end, to the last pin.
The brackets leave 2 mm to the link they hold.

  CHAIN X   plane X-Z, 18 links; lies on the beam (2 mm above it), the moving run 160 above the fixed run
      fixed end   pin 0 (-28.74, 70, 272); the fixed run goes along +X (pins 0..6); CHAIN BRACKET X FIXED on the BEAM
      bend        centre (211.26, 70, 352)
      moving end  pin 18 (-20, 70, 432), 5 links on its run; CHAIN BRACKET X MOVING on the CARRIAGE (X.ASM)
  CHAIN Y   plane X-Y, 16 links; lies on its side on the tray beside the bed (runs side by side, the bend's axis up)
      fixed end   pin 0 (600, 98.74, -8); the fixed run goes along -Y (pins 0..5); CHAIN BRACKET Y FIXED on the tray
      bend        centre (520, -101.26, -8)
      moving end  pin 16 (440, 90, -8), 4 links on its run; CHAIN BRACKET Y MOVING on GANTRY SIDE R (Y.ASM)
  CHAIN Z   plane X-Z, 13 links; stands beside the spindle (both runs upright, the bend on top)
      fixed end   pin 0 (-222, -8, 221.26); the fixed run goes along +Z (pins 0..3); CHAIN BRACKET Z FIXED (X.ASM)
      bend        centre (-142, -8, 341.26)
      moving end  pin 13 (-62, -8, 190), 3 links on its run; CHAIN BRACKET Z MOVING on the SPINDLE (Z.ASM)

Over X -150 .. +150, Y -100 .. +100, Z -60 .. +60 the bend's centre moves half as far as the moving end (±75, ±50,
±30) and the runs keep at least: CHAIN X 4 whole links (fixed run) and 3 (moving run), CHAIN Y 3 and 3, CHAIN Z 2
and 3. +X and +Z move their chain's far end the way its fixed run goes; +Y moves it against (``CHAIN_SIGN``).

The files are small because equal parts are one shape placed again and the curves on the surfaces are left out
(hoses a: 272 KB, chains: 178 KB). Needs OpenCascade (OCP), as the other tools/make_test_*.py.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OCP.BRepExtrema import BRepExtrema_DistShapeShape  # noqa: E402
from OCP.Interface import Interface_Static  # noqa: E402
from OCP.STEPControl import STEPControl_Writer  # noqa: E402

from fresing_render.demo_model import geom as G  # noqa: E402
from fresing_render.demo_model.geom import Asm, Part, Rot, T  # noqa: E402

YELLOW, GREY, STEEL, CHROME = (0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.55, 0.57, 0.6), (0.85, 0.86, 0.88)
BLUE, BLACK, BRASS, ORANGE = (0.075, 0.267, 0.486), (0.05, 0.05, 0.055), (0.78, 0.62, 0.25), (0.9, 0.35, 0.05)
X, Y, Z = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


# =====================================================================================================================
# a hose's path: straight pieces and arcs that meet smoothly
# =====================================================================================================================

class Line:
    kind = "line"
    radius = math.inf

    def __init__(self, start, end):
        self.start, self.end = np.asarray(start, float), np.asarray(end, float)
        self.length = float(np.linalg.norm(self.end - self.start))
        self.start_tangent = self.end_tangent = (self.end - self.start) / self.length

    def point(self, s):
        return self.start + self.start_tangent * s


class Arc:
    """The circle that leaves ``start`` along ``tangent`` and passes through ``end``."""
    kind = "arc"

    def __init__(self, start, tangent, end):
        self.start, self.end = np.asarray(start, float), np.asarray(end, float)
        self.start_tangent = unit(tangent)
        chord = self.end - self.start
        along = float(chord @ self.start_tangent)
        side = chord - along * self.start_tangent
        h = float(np.linalg.norm(side))
        self.inward = side / h
        self.radius = float(chord @ chord) / (2.0 * h)
        self.angle = 2.0 * math.atan2(h, along)
        self.length = self.radius * self.angle
        self.centre = self.start + self.radius * self.inward
        a = self.angle
        self.end_tangent = math.sin(a) * self.inward + math.cos(a) * self.start_tangent

    def point(self, s):
        a = s / self.radius
        return self.centre + self.radius * (math.sin(a) * self.start_tangent - math.cos(a) * self.inward)


def biarc(p0, t0, p1, t1):
    """Two arcs from p0 (leaving along t0) to p1 (arriving along t1) that meet smoothly."""
    p0, p1, t0, t1 = np.asarray(p0, float), np.asarray(p1, float), unit(t0), unit(t1)
    v, t = p1 - p0, t0 + t1
    den = 2.0 * (1.0 - float(t0 @ t1))
    if abs(den) < 1e-12:
        d = float(v @ v) / (4.0 * float(v @ t1))
    else:
        d = (-float(v @ t) + math.sqrt(float(v @ t) ** 2 + den * float(v @ v))) / den
    joint = 0.5 * ((p0 + d * t0) + (p1 - d * t1))
    first = Arc(p0, t0, joint)
    second = Arc(joint, first.end_tangent, p1)
    assert np.linalg.norm(second.end_tangent - t1) < 1e-6, "the two arcs do not arrive along t1"
    return [first, second]


class Route:
    """A hose's centreline: a straight piece out of the first fitting, arcs through the knots, a straight piece
    into the second fitting. ``out0`` / ``out1``: the directions the hose leaves its fittings."""

    def __init__(self, end0, out0, end1, out1, straight, knots=()):
        end0, end1, out0, out1 = np.asarray(end0, float), np.asarray(end1, float), unit(out0), unit(out1)
        pts = [(end0 + straight * out0, out0)] + [(np.asarray(p, float), unit(t)) for p, t in knots]
        pts.append((end1 + straight * out1, -out1))
        self.end0, self.end1, self.out0, self.out1, self.straight = end0, end1, out0, out1, straight
        self.segments = [Line(end0, pts[0][0])]
        for (a, ta), (b, tb) in zip(pts[:-1], pts[1:]):
            self.segments += biarc(a, ta, b, tb)
        self.segments.append(Line(pts[-1][0], end1))
        for a, b in zip(self.segments[:-1], self.segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-6 and np.linalg.norm(a.end_tangent - b.start_tangent) < 1e-6
        self.length = sum(s.length for s in self.segments)
        self.min_radius = min(s.radius for s in self.segments)

    def points(self, step=2.0):
        out = [self.end0]
        for seg in self.segments:
            k = max(int(math.ceil(seg.length / step)), 1)
            out += [seg.point(seg.length * i / k) for i in range(1, k + 1)]
        return np.array(out)


# =====================================================================================================================
# TEST.FLEX.HOSES
# =====================================================================================================================

PIVOT = (100.0, 600.0)              # (x, z) of the arm's pivot; everything hydraulic lies at y = ARM_Y
ARM_Y = 200.0
BARREL_PIN = (300.0, 170.0)
ROD_PIN_ARM = (800.0, -150.0)       # the rod pin from the pivot, in the arm
ARM_RANGE = 20.0                    # degrees either way the hoses are made for
SLIDE_RANGE = 150.0
SLIDE_AT = (330.0, 350.0, 131.0)    # where SLIDE.ASM is placed (its origin: the carriage's middle, underside)
FIT_ARM, FIT_BARREL_A = 900.0, 90.0
GLAND_ARM = 1085.0


def rod_pin(a_deg):
    """The rod pin (x, z) with the arm turned a_deg up."""
    a = math.radians(a_deg)
    x, z = ROD_PIN_ARM
    return PIVOT[0] + x * math.cos(a) - z * math.sin(a), PIVOT[1] + x * math.sin(a) + z * math.cos(a)


def cylinder(a_deg=0.0):
    """(pin to pin, angle from level in degrees) of the cylinder with the arm at a_deg."""
    x, z = rod_pin(a_deg)
    return math.hypot(x - BARREL_PIN[0], z - BARREL_PIN[1]), math.degrees(math.atan2(z - BARREL_PIN[1],
                                                                                    x - BARREL_PIN[0]))


CYL_L, CYL_ANGLE = cylinder()
_IN = math.ceil(CYL_L - cylinder(-ARM_RANGE)[0]) + 12          # what the piston can go in and out: the arm's range
_OUT = math.ceil(cylinder(ARM_RANGE)[0] - CYL_L) + 11          # and a little more
PISTON = 40.0 + _IN                 # the piston's back face from the barrel pin (the cap's inside is at 40)
TUBE_END = PISTON + 30.0 + _OUT     # where the gland begins
FIT_BARREL_B = TUBE_END - 34.0


def arm_matrix(a_deg=0.0):
    """ARM.ASM's place with the arm turned a_deg up (about Y through the pivot)."""
    return T(PIVOT[0], ARM_Y, PIVOT[1]) @ Rot(Y, -a_deg)


def barrel_matrix(a_deg=0.0):
    return T(BARREL_PIN[0], ARM_Y, BARREL_PIN[1]) @ Rot(Y, -cylinder(a_deg)[1])


def _at(matrix, p):
    return (matrix @ np.r_[np.asarray(p, float), 1.0])[:3]


def hose_ends(a_deg=0.0, slide=0.0):
    """Every hose's two end points at a pose: name -> (end 0, end 1)."""
    arm, barrel = arm_matrix(a_deg), barrel_matrix(a_deg)
    return {
        "HYDRAULIC HOSE ARM": (np.array([430.0, -70.0, 220.0]), _at(arm, (FIT_ARM, -80.0, 0.0))),
        "HYDRAULIC HOSE CYL A": (np.array([310.0, -70.0, 220.0]), _at(barrel, (FIT_BARREL_A, -75.0, 0.0))),
        "HYDRAULIC HOSE CYL B": (np.array([370.0, -70.0, 220.0]), _at(barrel, (FIT_BARREL_B, -75.0, 0.0))),
        "CABLE": (np.array([375.0 + slide, 350.0, 620.0]), _at(arm, (GLAND_ARM, 62.0, 0.0))),
    }


HOSE_DIAMETER = {"HYDRAULIC HOSE ARM": 20.0, "HYDRAULIC HOSE CYL A": 16.0, "HYDRAULIC HOSE CYL B": 16.0,
                 "CABLE": 10.0}
HOSE_TOUCHES = {"HYDRAULIC HOSE ARM": ("FITTING VALVE C", "FITTING ARM"),
                "HYDRAULIC HOSE CYL A": ("FITTING VALVE A", "FITTING BARREL A"),
                "HYDRAULIC HOSE CYL B": ("FITTING VALVE B", "FITTING BARREL B"),
                "CABLE": ("SLIDE GLAND", "CABLE GLAND ARM")}
HOSE_OUT = {"HYDRAULIC HOSE ARM": (Z, -Y), "HYDRAULIC HOSE CYL A": (Z, -Y), "HYDRAULIC HOSE CYL B": (Z, -Y),
            "CABLE": (X, -X)}


def hose_routes(revision="A"):
    """name -> Route: the centrelines as drawn."""
    ends = hose_ends()
    knots = {
        # up out of the valve block, in a wide arc over to the arm's side
        "HYDRAULIC HOSE ARM": [((660.0, -230.0, 500.0), (1.0, 0.0, 0.45))] if revision == "A" else
                              [((600.0, -260.0, 484.0), (1.0, 0.0, 0.45))],
        # up, over in a hump and down into the port on the barrel's side
        "HYDRAULIC HOSE CYL A": [((346.0, -10.0, 370.0), (0.5, 1.0, 0.0))],
        "HYDRAULIC HOSE CYL B": [((500.0, -60.0, 420.0), (1.0, 0.45, 0.25))],
        # hangs between the two glands: its lowest point about half-way
        "CABLE": [((790.0, 306.0, 330.0), (1.0, -0.11, 0.0))],
    }
    return {name: Route(ends[name][0], HOSE_OUT[name][0], ends[name][1], HOSE_OUT[name][1],
                        2.0 * HOSE_DIAMETER[name], knots[name]) for name in HOSE_DIAMETER}


def hose_motion(revision="A", steps=9):
    """name -> (ends apart as drawn, least, most, spare at the worst pose, that pose): the hose must reach from
    fitting to fitting with its two straight ends, so spare = length - 2 straights - the distance between the
    ends of the straight pieces."""
    routes = hose_routes(revision)
    out = {}
    for name, route in routes.items():
        apart, spare = [], []
        for a in np.linspace(-ARM_RANGE, ARM_RANGE, steps):
            for s in np.linspace(-SLIDE_RANGE, SLIDE_RANGE, steps if name == "CABLE" else 1):
                e0, e1 = hose_ends(a, s)[name]
                if name != "CABLE":
                    e0, e1 = hose_ends(a, 0.0)[name]
                apart.append(float(np.linalg.norm(e1 - e0)))
                inner = float(np.linalg.norm((e1 + route.straight * route.out1) - (e0 + route.straight * route.out0)))
                spare.append((route.length - 2.0 * route.straight - inner, float(a), float(s)))
        drawn = float(np.linalg.norm(route.end1 - route.end0))
        worst = min(spare)
        out[name] = (drawn, min(apart), max(apart), worst[0], (worst[1], worst[2]))
    return out


def _x(x0, x1, r):
    return G.cyl(r, x1 - x0, (x0, 0.0, 0.0), X)


def _tube_x(x0, x1, r_in, r_out):
    return G.cut(_x(x0, x1, r_out), _x(x0 - 1.0, x1 + 1.0, r_in))


def _eye(x, r_out, r_in, width):
    """A ring round a pin along Y at (x, 0, 0)."""
    return G.cut(G.cyl(r_out, width, (x, -width / 2, 0.0), Y), G.cyl(r_in, 2 * width, (x, -width, 0.0), Y))


def _hex(base, direction, flats, length):
    """A hex stub standing on ``base`` along ``direction``."""
    r = flats / math.sqrt(3.0)
    pts = [(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k))) for k in range(6)]
    return G.polygon_prism(pts, length, G.on_axis(base, direction))


def hoses_model(revision="A"):
    px, pz = PIVOT
    bx, bz = BARREL_PIN
    ax, az = ROD_PIN_ARM
    root = Asm("TEST.FLEX.HOSES")

    root.add(Part("BASE", G.box(0, -150, 0, 1200, 600, 100), YELLOW))
    post = G.fuse(G.box(px - 60, 115, 100, 120, 170, 400), G.box(px - 40, 115, pz - 120, 80, 30, 160),
                  G.box(px - 40, 255, pz - 120, 80, 30, 160))
    root.add(Part("POST", G.cut(post, G.cyl(20.2, 200, (px, 100, pz), Y)), YELLOW))
    bracket = G.fuse(G.box(bx - 40, 120, 100, 80, 160, 8), G.box(bx - 40, 120, 100, 80, 25, 110),
                     G.box(bx - 40, 255, 100, 80, 25, 110))
    root.add(Part("BASE.BRACKET", G.cut(bracket, G.cyl(20.0, 200, (bx, 100, bz), Y)), YELLOW))
    root.add(Part("BASE.PIN", G.cyl(20.0, 170, (bx, 115, bz), Y), CHROME))
    root.add(Part("VALVE BLOCK", G.box(280, -110, 100, 180, 80, 100), GREY))
    for name, x, flats in (("A", 310.0, 24.0), ("B", 370.0, 24.0), ("C", 430.0, 30.0)):
        root.add(Part(f"FITTING VALVE {name}", _hex((x, -70.0, 200.0), Z, flats, 20.0), BRASS))
    root.add(Part("RAIL", G.box(100, 320, 100, 460, 60, 30), STEEL))

    # the arm, built round its pivot
    arm = Asm("ARM.ASM")
    arm.add(Part("ARM", G.cut(G.box(-50, -50, -50, 1250, 100, 100), G.cyl(20.0, 120, (0, -60, 0), Y)), YELLOW))
    arm.add(Part("ARM.PIN", G.cyl(20.0, 180, (0, -90, 0), Y), CHROME))
    lugs = G.fuse(G.box(ax - 40, -75, -60, 80, 150, 10), G.box(ax - 40, -75, az - 40, 80, 20, -60 - (az - 40)),
                  G.box(ax - 40, 55, az - 40, 80, 20, -60 - (az - 40)))
    arm.add(Part("ARM.BRACKET", G.cut(lugs, G.cyl(20.0, 200, (ax, -100, az), Y)), YELLOW))
    arm.add(Part("ARM.ROD.PIN", G.cyl(20.0, 160, (ax, -80, az), Y), CHROME))
    arm.add(Part("FITTING ARM", _hex((FIT_ARM, -50.0, 0.0), -Y, 30.0, 30.0), BRASS))
    arm.add(Part("CABLE GLAND ARM", G.box(GLAND_ARM, 50, -12, 30, 24, 24), GREY))
    if revision == "B":
        arm.add(Part("ARM.LAMP", G.sphere(30.0), ORANGE), T(1100, 0, 80))
    root.add(arm, arm_matrix())

    # the cylinder, built along X from its barrel pin (x = 0) to its rod pin (x = CYL_L)
    barrel = Asm("CYL.BARREL")
    barrel.add(Part("BARREL.CAP", G.fuse(_x(22, 40, 50), _eye(0, 30, 20.2, 40)), GREY))
    barrel.add(Part("BARREL.TUBE", _tube_x(40, TUBE_END, 40, 50), GREY))
    barrel.add(Part("BARREL.GLAND", _tube_x(TUBE_END, TUBE_END + 30, 16, 50), GREY))
    barrel.add(Part("FITTING BARREL A", _hex((FIT_BARREL_A, -50.0, 0.0), -Y, 24.0, 25.0), BRASS))
    barrel.add(Part("FITTING BARREL B", _hex((FIT_BARREL_B, -50.0, 0.0), -Y, 24.0, 25.0), BRASS))
    rod = Asm("CYL.ROD")
    rod.add(Part("PISTON", _x(PISTON, PISTON + 30, 39), STEEL))
    rod.add(Part("ROD", _x(PISTON + 30, CYL_L - 25, 15), CHROME))
    rod.add(Part("ROD.EYE", _eye(CYL_L, 30, 20.2, 40), STEEL))
    cyl = Asm("CYL.ASM")
    cyl.add(barrel)
    cyl.add(rod)
    root.add(cyl, barrel_matrix())

    # the slide, built round the middle of its carriage's underside
    slide = Asm("SLIDE.ASM")
    slide.add(Part("SLIDE CARRIAGE", G.fuse(G.box(-60, -40, 0, 120, 80, 40), G.box(-20, -20, 40, 40, 40, 470)),
                   BLUE))
    slide.add(Part("SLIDE GLAND", G.cyl(11.0, 25.0, (20, 0, 489), X), GREY))
    root.add(slide, T(*SLIDE_AT))

    routes = hose_routes(revision)
    names = list(routes)
    for name in (names if revision == "A" else names[::-1]):
        route = routes[name]
        root.add(Part(name, G.route_solid(route, HOSE_DIAMETER[name] / 2.0),
                      (0.03, 0.03, 0.03) if name != "CABLE" else ORANGE))
    return root


# ---------------------------------------------------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------------------------------------------------

def placed(root):
    """Every part once per place: (name, path of assembly names, shape in the model's coordinates)."""
    out = []
    for node, _uid, world, _label, path in G.walk(root):
        if isinstance(node, Part):
            out.append((node.name, [c.node.name for c in path[:-1]], G.xform(node.shape, world)))
    return out


def gap(a, b):
    d = BRepExtrema_DistShapeShape(a, b)
    return float(d.Value())


def _bodies(parts, body_of):
    groups = {}
    for name, path, shape in parts:
        key = body_of(name, path)
        if key is not None:
            groups.setdefault(key, []).append(shape)
    return {k: G.compound(*v) for k, v in groups.items()}


def check_hoses(root, revision="A", say=print):
    parts = placed(root)
    shapes = {name: shape for name, _path, shape in parts}
    routes = hose_routes(revision)
    # a hose lies flat on its two fittings and is clear of everything else
    for name, route in routes.items():
        r = HOSE_DIAMETER[name] / 2.0
        assert route.min_radius >= 3.5 * 2 * r, (name, "bends tighter than 3.5 diameters", route.min_radius)
        near = math.inf
        for other, _path, shape in parts:
            if other == name:
                continue
            d = gap(shapes[name], shape)
            if other in HOSE_TOUCHES[name]:
                assert d < 1e-6, (name, "does not touch", other, d)
                assert G.volume(G.common(shapes[name], shape)) < 1e-3, (name, "lies inside", other)
            else:
                assert d > 3.0, (name, "too near", other, d)
                near = min(near, d)
        say(f"  {name:22s} Ø{2 * r:.0f}  length {route.length:8.2f}  tightest bend {route.min_radius:6.1f}  "
            f"nearest other part {near:5.1f}")
    for name, (drawn, least, most, spare, pose) in hose_motion(revision).items():
        assert spare > 0.07 * routes[name].length, (name, "too short for the motion", spare, pose)
        say(f"  {name:22s} ends apart {drawn:6.1f}, {least:6.1f} .. {most:6.1f}  spare {spare:6.1f} at arm "
            f"{pose[0]:+.0f}°" + (f", slide {pose[1]:+.0f}" if name == "CABLE" else ""))

    # the rigid bodies at the ends of the travel: nothing touches (0.2 mm in the pin bores)
    def body_of(name, path):
        if name in routes:
            return None
        for key in ("CYL.BARREL", "CYL.ROD", "ARM.ASM", "SLIDE.ASM"):
            if key in path:
                return key
        return "base"

    at_rest = _bodies(parts, body_of)
    least = math.inf
    for a in (-ARM_RANGE, 0.0, ARM_RANGE):
        length, angle = cylinder(a)
        turn = T(BARREL_PIN[0], ARM_Y, BARREL_PIN[1]) @ Rot(Y, -(angle - CYL_ANGLE)) @ T(-BARREL_PIN[0], -ARM_Y,
                                                                                         -BARREL_PIN[1])
        along = np.array([math.cos(math.radians(angle)), 0.0, math.sin(math.radians(angle))]) * (length - CYL_L)
        assert PISTON - (CYL_L - length) > 40.0 + 5 and PISTON + 30 + (length - CYL_L) < TUBE_END - 5
        for s in (-SLIDE_RANGE, 0.0, SLIDE_RANGE):
            move = {"base": np.eye(4), "ARM.ASM": arm_matrix(a) @ np.linalg.inv(arm_matrix()), "CYL.BARREL": turn,
                    "CYL.ROD": T(*along) @ turn, "SLIDE.ASM": T(s, 0, 0)}
            now = {k: G.xform(v, move[k]) for k, v in at_rest.items()}
            keys = sorted(now)
            for i, ka in enumerate(keys):
                for kb in keys[i + 1:]:
                    d = gap(now[ka], now[kb])
                    assert d > 0.15, ("bodies touch", ka, kb, d, "arm", a, "slide", s)
                    least = min(least, d)
    say(f"  bodies at arm -{ARM_RANGE:.0f}/0/+{ARM_RANGE:.0f}°, slide -{SLIDE_RANGE:.0f}/0/+{SLIDE_RANGE:.0f}: "
        f"least gap {least:.2f} mm")


# =====================================================================================================================
# TEST.FLEX.GANTRY
# =====================================================================================================================

PITCH, RADIUS = 40.0, 80.0
TURN = 2.0 * math.asin(PITCH / (2.0 * RADIUS))      # a link against the one before, in the bend
LINK_SIZE = (32.0, 60.0, 20.0)                      # the link's body: along the chain, across it, its height
LINK_PIN0, LINK_PIN1 = (-4.0, 30.0, 10.0), (36.0, 30.0, 10.0)     # the two pins in the link's own coordinates
ON_BEND = 6                                         # pins on the circle after the one where it touches the run
T1_TIP = (0.0, 0.0, 80.0)
STOCK = (-150.0, -100.0, 0.0, 300.0, 200.0, 30.0)
TRAVEL = {"X": (-150.0, 150.0), "Y": (-100.0, 100.0), "Z": (-60.0, 60.0)}

# name -> (links on the fixed run, links on the moving run, pin 0, the fixed run's direction, from the fixed run
#          towards the moving run, the assembly it sits in (its fixed side), the axis that moves its far end)
CHAINS = {
    "CHAIN X": (6, 5, (-28.74, 70.0, 272.0), X, Z, "Y.ASM", "X"),
    "CHAIN Y": (5, 4, (600.0, 98.74, -8.0), -Y, -X, "", "Y"),
    "CHAIN Z": (3, 3, (-222.0, -8.0, 221.26), Z, X, "X.ASM", "Z"),
}


def chain_pins_2d(on_fixed, on_moving):
    """The pins as drawn, (u, v): u along the fixed run from pin 0, v towards the moving run."""
    pins = [(PITCH * i, 0.0) for i in range(on_fixed + 1)]
    centre = PITCH * on_fixed
    for j in range(1, ON_BEND + 1):
        pins.append((centre + RADIUS * math.sin(j * TURN), RADIUS * (1.0 - math.cos(j * TURN))))
    u, v = pins[-1]
    u -= math.sqrt(PITCH ** 2 - (2.0 * RADIUS - v) ** 2)
    pins += [(u - PITCH * i, 2.0 * RADIUS) for i in range(on_moving + 1)]
    return np.array(pins)


def chain_frame(name):
    """Chain coordinates (u, v, w) -> the coordinates of the assembly the chain sits in (4 x 4)."""
    _f, _m, origin, u, v, _asm, _axis = CHAINS[name]
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = u, v, np.cross(u, v), origin
    return m


def chain_pins(name):
    """The pins as drawn, in the model's coordinates (all assemblies are placed without a shift)."""
    on_fixed, on_moving = CHAINS[name][:2]
    p = chain_pins_2d(on_fixed, on_moving)
    return (chain_frame(name) @ np.c_[p, np.zeros(len(p)), np.ones(len(p))].T).T[:, :3]


def chain_runs(on_fixed, on_moving, shift):
    """With the moving end ``shift`` further along u: (whole links on the fixed run, on the moving run, the
    bend's centre u). The same rule as the drawn pose: pins on the fixed run's line, on the circle, on the line
    2 radii away; the bend's place is found so that the last pin is the moving end."""
    links = on_fixed + ON_BEND + 1 + on_moving
    target = chain_pins_2d(on_fixed, on_moving)[-1][0] + shift

    def lay(c):
        pins = [(PITCH * i, 0.0) for i in range(int(math.floor(c / PITCH + 1e-9)) + 1)]
        fixed = len(pins) - 1
        e = c - pins[-1][0]                                   # from the last pin on the run to where the circle touches
        lo, hi = 0.0, TURN
        for _ in range(60):                                   # the first pin on the circle, a pitch from that pin
            a = 0.5 * (lo + hi)
            far = math.hypot(e + RADIUS * math.sin(a), RADIUS * (1.0 - math.cos(a)))
            lo, hi = (a, hi) if far < PITCH else (lo, a)
        a = 0.5 * (lo + hi)
        while a <= math.pi + 1e-9 and len(pins) <= links:
            pins.append((c + RADIUS * math.sin(a), RADIUS * (1.0 - math.cos(a))))
            a += TURN
        u, v = pins[-1]
        u -= math.sqrt(PITCH ** 2 - (2.0 * RADIUS - v) ** 2)
        first_up = len(pins)
        while len(pins) <= links:
            pins.append((u, 2.0 * RADIUS))
            u -= PITCH
        return pins, fixed, links + 1 - first_up - 1

    lo, hi = 0.0, PITCH * links
    for _ in range(80):
        c = 0.5 * (lo + hi)
        lo, hi = (c, hi) if lay(c)[0][-1][0] < target else (lo, c)
    c = 0.5 * (lo + hi)
    pins, fixed, moving = lay(c)
    assert abs(pins[-1][0] - target) < 1e-6
    return fixed, moving, c


def link_shape():
    """The link, its own origin at a lower corner of its body."""
    dx, dy, dz = LINK_SIZE
    return G.fuse(G.box(0, 0, 0, dx, 4, dz), G.box(0, dy - 4, 0, dx, 4, dz), G.box(14, 4, 0, 12, dy - 8, 3),
                  G.box(6, 4, dz - 3, 12, dy - 8, 3))


def link_matrices(pins_2d):
    """Each link's place in chain coordinates laid out as an assembly: x = u, z = v, y = -w."""
    out = []
    for a, b in zip(pins_2d[:-1], pins_2d[1:]):
        cu, cv = (b - a) / np.linalg.norm(b - a)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2] = (cu, 0.0, cv), (0.0, 1.0, 0.0), (-cv, 0.0, cu)
        m[:3, 3] = np.array([a[0], 0.0, a[1]]) - m[:3, :3] @ np.array(LINK_PIN0)
        out.append(m)
    return out


def chain_asm(name, link):
    on_fixed, on_moving = CHAINS[name][:2]
    asm = Asm(f"{name}.ASM")
    for m in link_matrices(chain_pins_2d(on_fixed, on_moving)):
        asm.add(link, m)
    f = chain_frame(name)
    place = np.eye(4)                           # the assembly's x = u, y = -w, z = v
    place[:3, 0], place[:3, 1], place[:3, 2], place[:3, 3] = f[:3, 0], -f[:3, 2], f[:3, 1], f[:3, 3]
    return asm, place


def chains_model():
    root = Asm("TEST.FLEX.GANTRY")
    link = Part("CHAIN LINK", link_shape(), (0.12, 0.12, 0.13))
    px, py, pz = chain_pins("CHAIN X"), chain_pins("CHAIN Y"), chain_pins("CHAIN Z")

    root.add(Part("BED", G.box(-400, -300, -40, 800, 600, 40), BLUE))
    root.add(Part("STOCK 300x200x30", G.box(*STOCK), (0.75, 0.76, 0.78)))
    root.add(Part("CHAIN TRAY Y", G.box(400, -260, -50, 240, 470, 10), GREY))
    root.add(Part("CHAIN BRACKET Y FIXED", G.box(585, py[0][1] - 2, -40, 30, 30, 62), STEEL))
    root.add(*chain_asm("CHAIN Y", link))

    y_asm = Asm("Y.ASM")
    y_asm.add(Part("GANTRY SIDE L", G.box(-410, 40, 1, 20, 60, 259), BLUE))
    y_asm.add(Part("GANTRY SIDE R", G.box(390, 40, 1, 20, 60, 259), BLUE))
    y_asm.add(Part("BEAM", G.box(-390, 40, 200, 780, 60, 60), BLUE))
    y_asm.add(Part("CHAIN BRACKET X FIXED", G.box(px[0][0] - 28, 40, 260, 30, 60, 22), STEEL))
    y_asm.add(Part("CHAIN BRACKET Y MOVING", G.box(410, py[-1][1] - 30, 24, 42, 36, 10), STEEL))
    y_asm.add(*chain_asm("CHAIN X", link))

    x_asm = Asm("X.ASM")
    x_asm.add(Part("CARRIAGE", G.box(-50, 26, 150, 100, 13, 110), GREY))
    x_asm.add(Part("CHAIN BRACKET X MOVING", G.fuse(G.box(-15, 26, 260, 30, 10, 192),
                                                    G.box(px[-1][0] - 16, 26, 444, 52, 74, 8)), STEEL))
    z0 = pz[0][2]
    x_asm.add(Part("CHAIN BRACKET Z FIXED", G.fuse(G.box(-240, 26, z0 - 8, 190, 13, 20),
                                                   G.box(pz[0][0] - 15, -38, z0 - 8, 30, 64, 10)), STEEL))
    x_asm.add(*chain_asm("CHAIN Z", link))

    z_asm = Asm("Z.ASM")
    z_asm.add(Part("SPINDLE", G.cyl(25.0, 120.0, (0, 0, 110)), GREY))
    z_asm.add(Part("TOOL T1 FLAT D6", G.cyl(3.0, 30.0), (0.8, 0.8, 0.82)), T(*T1_TIP))
    z_asm.add(Part("CHAIN BRACKET Z MOVING", G.box(-100, -38, pz[-1][2] - 8, 75, 60, 10), STEEL))
    x_asm.add(z_asm)
    y_asm.add(x_asm)
    root.add(y_asm)
    return root


def check_chains(root, say=print):
    parts = placed(root)
    links = [(path, shape) for name, path, shape in parts if name == "CHAIN LINK"]
    others = [(name, path, shape) for name, path, shape in parts if name != "CHAIN LINK"]
    for name, (on_fixed, on_moving, _o, _u, _v, _asm, axis) in CHAINS.items():
        mine = [shape for path, shape in links if path[-1] == f"{name}.ASM"]
        pins = chain_pins(name)
        assert len(mine) == len(pins) - 1 == on_fixed + ON_BEND + 1 + on_moving
        chords = np.linalg.norm(np.diff(pins, axis=0), axis=1)
        assert np.abs(chords - PITCH).max() < 1e-9
        between = [gap(a, b) for a, b in zip(mine[:-1], mine[1:])]
        assert min(between) > 2.0, (name, "links touch", min(between))
        near = min((gap(s, shape), other) for s in mine for other, _path, shape in others)
        assert near[0] > 1.5, (name, "a link is too near", near)
        ends = (min(gap(mine[0], shape) for other, _p, shape in others if other.startswith("CHAIN BRACKET")),
                min(gap(mine[-1], shape) for other, _p, shape in others if other.startswith("CHAIN BRACKET")))
        assert max(ends) < 2.0 + 1e-6, (name, "no bracket at an end", ends)
        runs = [chain_runs(on_fixed, on_moving, s * sign) for s in TRAVEL[axis] for sign in (CHAIN_SIGN[name],)]
        assert min(min(r[0], r[1]) for r in runs) >= 2, (name, "runs out of links", runs)
        say(f"  {name}: {len(mine)} links, pin 0 {np.round(pins[0], 2)}, last pin {np.round(pins[-1], 2)}; links "
            f"{min(between):.2f} mm apart in the bend, {max(between):.2f} on the runs; nearest other part "
            f"{near[0]:.2f} ({near[1]}); over {axis} {TRAVEL[axis][0]:+.0f} .. {TRAVEL[axis][1]:+.0f} the fixed run "
            f"keeps {min(r[0] for r in runs)} links, the moving run {min(r[1] for r in runs)}; the bend's centre "
            f"moves {runs[0][2] - PITCH * on_fixed:+.1f} .. {runs[1][2] - PITCH * on_fixed:+.1f}")

    # the machine's bodies at the ends of the travel (the chains follow in the app: left out here)
    def body_of(name, path):
        if name == "CHAIN LINK":
            return None
        for key in ("Z.ASM", "X.ASM", "Y.ASM"):
            if key in path:
                return key
        return "bed"

    at_rest = _bodies(parts, body_of)
    least = math.inf
    for x in TRAVEL["X"] + (0.0,):
        for y in TRAVEL["Y"] + (0.0,):
            for z in (-49.0, 0.0, TRAVEL["Z"][1]):
                move = {"bed": np.eye(4), "Y.ASM": T(0, y, 0), "X.ASM": T(x, y, 0), "Z.ASM": T(x, y, z)}
                now = {k: G.xform(v, move[k]) for k, v in at_rest.items()}
                keys = sorted(now)
                for i, ka in enumerate(keys):
                    for kb in keys[i + 1:]:
                        d = gap(now[ka], now[kb])
                        assert d > 0.9, ("bodies touch", ka, kb, d, x, y, z)
                        least = min(least, d)
    say(f"  bodies over X, Y, Z (Z from -49: at -50 the tool is on the stock): least gap {least:.2f} mm")


# +1: the axis' positive direction moves the chain's far end along its fixed run's direction (away from pin 0)
CHAIN_SIGN = {"CHAIN X": 1.0, "CHAIN Y": -1.0, "CHAIN Z": 1.0}


# =====================================================================================================================

def numbers(say=print):
    say(f"cylinder: pin to pin {CYL_L:.2f} at {CYL_ANGLE:.2f}°; {cylinder(-ARM_RANGE)[0]:.2f} .. "
        f"{cylinder(ARM_RANGE)[0]:.2f} over the arm's range; piston back face {PISTON:.0f}, tube to {TUBE_END:.0f}: "
        f"{PISTON - 40:.0f} in, {TUBE_END - PISTON - 30:.0f} out, closed {CYL_L - (PISTON - 40):.2f}, full stroke "
        f"{TUBE_END - 70:.0f}")
    lo = hi = 0.0
    for a in np.linspace(-30, 30, 6001):
        if CYL_L - (PISTON - 40) <= cylinder(a)[0] <= CYL_L + TUBE_END - PISTON - 30:
            lo, hi = min(lo, a), max(hi, a)
    say(f"  that lets the arm go from {lo:+.1f}° to {hi:+.1f}°")
    for rev in ("A", "B"):
        say(f"hoses, revision {rev}:")
        for name, r in hose_routes(rev).items():
            say(f"  {name:22s} Ø{HOSE_DIAMETER[name]:.0f} length {r.length:8.2f} end0 {np.round(r.end0, 2)} out "
                f"{r.out0} end1 {np.round(r.end1, 2)} out {r.out1} tightest {r.min_radius:.1f} chord "
                f"{np.linalg.norm(r.end1 - r.end0):.1f}")
        for name, (drawn, least, most, spare, pose) in hose_motion(rev).items():
            say(f"  {name:22s} apart {drawn:6.1f}, {least:6.1f} .. {most:6.1f}, spare {spare:6.1f} at {pose}")
    cable = hose_routes()["CABLE"]
    worst = hose_ends(-ARM_RANGE, SLIDE_RANGE)["CABLE"]
    say(f"  cable at arm -{ARM_RANGE:.0f}°, slide +{SLIDE_RANGE:.0f}: ends {np.linalg.norm(worst[1] - worst[0]):.1f} "
        f"apart, {cable.length - np.linalg.norm(worst[1] - worst[0]):.0f} to spare")
    for name, (on_fixed, on_moving, _o, _u, _v, asm, axis) in CHAINS.items():
        pins = chain_pins(name)
        centre = _at(chain_frame(name), (PITCH * on_fixed, RADIUS, 0.0))
        say(f"{name}: {len(pins) - 1} links in {asm or 'the root'}, pin 0 {np.round(pins[0], 2)}, bend centre "
            f"{np.round(centre, 2)}, last pin {np.round(pins[-1], 2)}")


def main(argv):
    what = argv[1] if len(argv) > 1 else "numbers"
    if what == "numbers":
        numbers()
        return 0
    path = argv[2]
    if what == "hoses":
        revision = argv[3] if len(argv) > 3 else "A"
        root = hoses_model(revision)
        check_hoses(root, revision)
    elif what == "chains":
        root = chains_model()
        check_chains(root)
    else:
        raise SystemExit("usage: make_test_flex.py hoses|chains out.step [A|B]   or   make_test_flex.py numbers")
    STEPControl_Writer()                                # (makes the setting below known)
    if not Interface_Static.SetIVal_s("write.surfacecurve.mode", 0):   # no curves-on-surface: a smaller file
        raise RuntimeError("the STEP writer does not know write.surfacecurve.mode")
    G.write_step(root, path)
    print(f"written: {G.count_parts(root)} parts, {os.path.getsize(path) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
