"""Write the two test models for hoses, cables and drag chains as STEP assemblies (task 0058; generic, invented).

    python tools/make_test_flex.py hoses  out.step [A|B]    TEST.FLEX.HOSES   (tests/data/test_flex_hoses_a / _b.step)
    python tools/make_test_flex.py chains out.step          TEST.FLEX.GANTRY  (tests/data/test_flex_chains_a.step)
    python tools/make_test_flex.py avoid  out.step [A|B]    TEST.FLEX.AVOID   (tests/data/test_flex_avoid_a / _b.step)
    python tools/make_test_flex.py numbers                  prints the numbers below from the geometry

All sizes in mm, Z up. Every part is one solid. Each maker checks its own model before it writes it (``check_…``):
no part lies inside another; parts that move against each other do not touch (0.2 mm in the pin bores, 1 mm and
more elsewhere) as drawn and at the ends of the travel; a hose touches its two fittings and nothing else (3 mm and
more); the hoses are long enough for the whole motion; the chains never run out of links. The numbers are also in
the code (``hose_routes``, ``hose_ends``, ``hose_motion``, ``cylinder``, ``CHAINS``, ``chain_pins``, ``chain_runs``)
for tests to use.

======================================================================================================================
TEST.FLEX.HOSES – a luffing arm with hydraulics                       29 parts (revision B: 30), each its own shape
======================================================================================================================
Task 0261 (study 0258): real size. The LAYOUT is three times the first model's (``K``: places, lengths, the slide's
travel); the structure (base, post, brackets, arm, valve block, rail, carriage) is drawn at the first numbers and
scaled x 3. What has a real size is drawn at it: the hoses (Ø16 / Ø20), the cable (Ø10), the fittings and glands,
the pins (Ø60, bores Ø60.4), the cylinder (bore Ø125, barrel Ø150, rod Ø70, eyes Ø100 x 90). The hoses only get longer.

  BASE                         box 3600 x 1800 x 300: x 0..3600, y -450..1350, z 0..300
  POST                         carries the arm's pivot (300, *, 1800), axis along Y: a block up to z 1500 and a fork
                               (cheeks y 345..435 and 765..855, bore Ø60.4) the arm turns in
  BASE.BRACKET                 two lugs (y 360..435 and 765..840) on a foot, bore Ø60: carries the barrel pin
  BASE.PIN                     Ø60 along Y through the barrel pin (900, *, 510) (pick target)
  VALVE BLOCK                  box x 840..1380, y -330..-90, z 300..600; three ports on top
  FITTING VALVE A / B / C      hex stubs on the block's top at (930 / 1110 / 1290, -210), z 600..620 (A and B 24
                               across flats, C 30); end face up
  RAIL                         box x 300..1680, y 960..1140, z 300..390: the slide's rail, along X
  ARM.ASM                      turns about the pivot; drawn level, the middle of its range -20° .. +20°
    ARM                        box 3750 x 300 x 300 along X, from 150 behind the pivot to 3600 in front of it
    ARM.PIN                    Ø60 along Y at the pivot (pick target for the arm's joint)
    ARM.BRACKET                under the arm: a plate with two lugs, carries the rod pin
    ARM.ROD.PIN                Ø60 along Y through the rod pin, (2400, *, -450) from the pivot = (2700, *, 1350) (pick)
    FITTING ARM                hex stub (30 across flats) on the arm's side 2700 from the pivot, y 450 -> 420; end
                               face (3000, 420, 1800), looking along -Y
    CABLE GLAND ARM            block 30 x 24 x 24 on the arm's other side, 3255..3285 from the pivot; the cable
                               leaves its face (3555, 762, 1800) along -X
    ARM.LAMP                   revision B only: a ball Ø180 on top of the arm, 3300 from the pivot
  CYL.ASM                      one cylinder at y = 600 in the pattern of tools/make_test_cylinder.py: barrel pin
                               (900, 510), rod pin (2700, 1350); pin to pin 1986.35, 25.02° up from level
    CYL.BARREL                 BARREL.CAP (end cap + eye, bore Ø60.4), BARREL.TUBE (Ø150/125, 120..1252 from the
                               pin), BARREL.GLAND (1252..1342, bore Ø72), FITTING BARREL A and B (hex stubs 24 across
                               flats on the tube's side, 270 and 1150 from the pin, y 525 -> 500; end faces
                               (1144.67, 500, 624.18) and (1942.11, 500, 996.32), looking along -Y)
    CYL.ROD                    PISTON (Ø123, 641..731 from the pin), ROD (Ø70), ROD.EYE (bore Ø60.4)
  SLIDE.ASM                    slides along X on the rail (3 mm above it); drawn at mid travel, -450 .. +450
    SLIDE CARRIAGE             block x 810..1170, y 930..1170, z 393..513 with a post 120 x 120 up to z 1923
    SLIDE GLAND                round stub Ø22 on the post, x 1050 -> 1075; the cable leaves its face (1075, 1050,
                               1860) along +X
  HYDRAULIC HOSE ARM, HYDRAULIC HOSE CYL A, HYDRAULIC HOSE CYL B, CABLE
                               directly under the root (as bought-in hoses usually are), each one solid: a round
                               bar swept along straight pieces and arcs that meet smoothly (in 3D). Every end is
                               straight for 2 diameters and lies flat on its fitting's face (touching, not inside).

The motion.  Arm: about Y through (300, *, 1800); +20° is tip up (a joint about +Y turns it down: there -20°). The
cylinder then goes from 1502.07 to 2474.35 pin to pin (drawn 1986.35): its piston can go 521 in and 521 out (closed
length 1465.35, full stroke 1042), which lets the arm go from -21.6° to +21.4°. Slide: along X, -450 .. +450.

Hoses. End 0 is the first fitting named; "out" is the direction the hose leaves that fitting; lengths are exact.

  HYDRAULIC HOSE ARM      Ø20   length 3000.81   tightest bend (centreline) 494.6
      end 0  (1290, -210, 620)      out (0, 0, 1)    touches FITTING VALVE C  (on the VALVE BLOCK)
      end 1  (3000, 420, 1800)      out (0, -1, 0)   touches FITTING ARM      (in ARM.ASM: across the arm's pivot)
      revision B: the same ends on a wider path, length 3150.56 (5.0 % longer), tightest bend 465.4
  HYDRAULIC HOSE CYL A    Ø16   length 1413.55   tightest bend 184.8
      end 0  (930, -210, 620)       out (0, 0, 1)    touches FITTING VALVE A
      end 1  (1144.67, 500, 624.18) out (0, -1, 0)   touches FITTING BARREL A (in CYL.BARREL: turns with the barrel)
  HYDRAULIC HOSE CYL B    Ø16   length 1756.04   tightest bend 402.7
      end 0  (1110, -210, 620)      out (0, 0, 1)    touches FITTING VALVE B
      end 1  (1942.11, 500, 996.32) out (0, -1, 0)   touches FITTING BARREL B
  CABLE                   Ø10   length 3286.14   tightest bend 610.0; 1.32 x the distance between its ends
      end 0  (1075, 1050, 1860)     out (1, 0, 0)    touches SLIDE GLAND      (in SLIDE.ASM)
      end 1  (3555, 762, 1800)      out (-1, 0, 0)   touches CABLE GLAND ARM  (in ARM.ASM, near the tip); it hangs
                                                     between them, lowest about (2370, 918, 940)

Checked over the arm's -20° .. +20° and the slide's -450 .. +450: the two ends are never further apart than the
hose is long. "Spare" = length - the two straight ends - the distance between the ends of those straight pieces:

  HYDRAULIC HOSE ARM      ends 2171.0 apart as drawn, 1690.1 .. 2686.1 over the motion; spare 275.1 (arm +20°)
  HYDRAULIC HOSE CYL A    ends  741.8 apart as drawn,  733.2 ..  756.3;                 spare 618.0 (arm -20°)
  HYDRAULIC HOSE CYL B    ends 1156.8 apart as drawn, 1156.7 .. 1179.9;                 spare 528.6 (arm -20°)
  CABLE                   ends 2497.4 apart as drawn, 2050.3 .. 2988.8;                 spare 293.9 (arm -20°,
                                                                                        slide -450)
With the arm down 20° and the slide at +450 the cable's ends are 2196 apart: 1090 mm of slack, it then hangs down to
about the base. The app does not lay hoses on parts (not in task 0058): a tour looks best with the arm at -10° or up.

Revision B: ARM.LAMP in ARM.ASM, the four hoses placed in the other order, HYDRAULIC HOSE ARM on a wider path.

======================================================================================================================
TEST.FLEX.GANTRY – a gantry router with a drag chain on every axis                    78 parts, 17 different shapes
======================================================================================================================
The machine is the one of tools/make_test_gantry.py without the carousel (same names and sizes, but about 2.5 mm of
air between parts that slide on each other), so the CNC machine set-up and a G-code program can drive it. Task 0262:
the router x 2.5 on the same stand (the bed's top at 0.9 m, the floor at z -900); the drag-chain links keep their
size (pitch 40, bend R80): the chains are only longer.

  BED                          box 2000 x 1500 x 100 (top at z = 0)
  MACHINE STAND                the stand of tools/make_test_gantry.py, down to the floor at z -900
  STOCK 300x200x30             the workpiece: x -150..150, y -100..100, z 0..30
  CHAIN TRAY Y                 shelf beside the bed for the Y chain: x 1000..1260, z -125..-100
  CHAIN BRACKET Y FIXED        block on the tray behind the Y chain's first link
  CHAIN Y.ASM                  21 x CHAIN LINK (the bed is this chain's fixed side)
  Y.ASM                        the gantry: moves along Y
    GANTRY SIDE L / R          boxes x -1025..-975 and 975..1025, y 100..250, z 2.5..650
    BEAM                       box between them, y 100..250, z 500..650
    CHAIN BRACKET X FIXED      block on the beam behind the X chain's first link
    CHAIN BRACKET Y MOVING     an angle on GANTRY SIDE R over the Y chain's last link
    CHAIN X.ASM                24 x CHAIN LINK (the beam is this chain's fixed side)
    X.ASM                      moves along X on the beam
      CARRIAGE                 plate x -125..125, y 65..97.5, z 375..650
      CHAIN BRACKET X MOVING   post on the carriage with a tab over the X chain's last link
      CHAIN BRACKET Z FIXED    bar from the carriage with a tab under the Z chain's first link
      CHAIN Z.ASM              17 x CHAIN LINK (the carriage is this chain's fixed side)
      Z.ASM                    moves along Z
        SPINDLE                cylinder Ø125, z 275..575
        TOOL T1 FLAT D6        flat end mill Ø6 x 30, tip at (0, 0, 245), 215 above the stock
        CHAIN BRACKET Z MOVING shelf on the spindle under the Z chain's last link

Travel checked (nothing but the tool touches anything): X -375 .. +375, Y -250 .. +250, Z -214 .. +150 (at -215 the
tool's tip is on the stock's top; the Z chain is laid out for -220 .. +150).

CHAIN LINK (one shape, placed 62 times): a frame of two side plates (4 thick) joined by a bar at the top and one at
the bottom; 32 long, 60 wide, 20 high. The solid's own origin is a lower corner: the body is x 0..32, y 0..60,
z 0..20, and the two pins (a notion: where the link hinges on its neighbours) are at (-4, 30, 10) and (36, 30, 10),
40 apart: **pitch 40**. The link from pin i to pin i + 1 has its own x along that line, its z across the run (on the
fixed run: towards the moving run) and its y along the bend's axis. On a straight run neighbours are 8 mm apart; in
the bend each link is turned 28.955° (2 asin(40 / 160)) against the one before and the corners are 2.75 mm apart.

Each chain, in its own plane: pins 0 .. k on the fixed run's line, 40 apart; pin k is where a circle of **radius
80** touches that line; the next six pins lie on that circle, 28.955° apart; the next lies on the line 160 from the
first (40 from the last pin on the circle) and the rest follow on it, back towards the fixed end, to the last pin.
The brackets leave 2 mm to the link they hold. Pin 0 is worked out from where the last pin is drawn (``CHAIN_END``).

  CHAIN X   plane X-Z, 24 links; lies on the beam (2 mm above it), the moving run 160 above the fixed run
      fixed end   pin 0 (-58.74, 175, 662); the fixed run goes along +X (pins 0..9); CHAIN BRACKET X FIXED on the BEAM
      bend        centre (301.26, 175, 742)
      moving end  pin 24 (-50, 175, 822), 8 links on its run; CHAIN BRACKET X MOVING on the CARRIAGE (X.ASM)
  CHAIN Y   plane X-Y, 21 links; lies on its side on the tray beside the bed (runs side by side, the bend's axis up)
      fixed end   pin 0 (1225, 168.74, -68); the fixed run goes along -Y (pins 0..7); CHAIN BRACKET Y FIXED on the tray
      bend        centre (1145, -111.26, -68)
      moving end  pin 21 (1065, 200, -68), 7 links on its run; CHAIN BRACKET Y MOVING on GANTRY SIDE R (Y.ASM)
  CHAIN Z   plane X-Z, 17 links; stands beside the spindle (both runs upright, the bend on top)
      fixed end   pin 0 (-260, 15, 511.26); the fixed run goes along +Z (pins 0..5); CHAIN BRACKET Z FIXED (X.ASM)
      bend        centre (-180, 15, 711.26)
      moving end  pin 17 (-100, 15, 480), 5 links on its run; CHAIN BRACKET Z MOVING on the SPINDLE (Z.ASM)

Over X -375 .. +375, Y -250 .. +250, Z -220 .. +150 the bend's centre moves half as far as the moving end (±187.5,
±125, -110 .. +75) and the runs keep at least: CHAIN X 4 whole links (fixed run) and 4 (moving run), CHAIN Y 3 and 4,
CHAIN Z 2 and 3. +X and +Z move their chain's far end the way its fixed run goes; +Y moves it against
(``CHAIN_SIGN``).

The files are small because equal parts are one shape placed again and the curves on the surfaces are left out
(hoses a: 274 KB, chains: 237 KB). Needs OpenCascade (OCP), as the other tools/make_test_*.py.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

K = 3.0                             # task 0261: the layout x 3 of the first model; real-size parts stay real
PIVOT = (300.0, 1800.0)             # (x, z) of the arm's pivot; everything hydraulic lies at y = ARM_Y
ARM_Y = 600.0
BARREL_PIN = (900.0, 510.0)
ROD_PIN_ARM = (2400.0, -450.0)      # the rod pin from the pivot, in the arm
ARM_RANGE = 20.0                    # degrees either way the hoses are made for
SLIDE_RANGE = 450.0
SLIDE_AT = (990.0, 1050.0, 393.0)   # where SLIDE.ASM is placed (its origin: the carriage's middle, underside)
FIT_ARM, FIT_BARREL_A = 2700.0, 270.0
GLAND_ARM = 3255.0
PIN_R = 30.0                        # pins Ø60, the bores of what turns on them Ø60.4
BORE_R, TUBE_R, ROD_R, PISTON_R = 62.5, 75.0, 35.0, 61.5      # cylinder: bore Ø125, barrel Ø150, rod Ø70
EYE_R, EYE_W = 50.0, 90.0
CAP_IN = 120.0                      # the end cap's inside face from the barrel pin


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
_IN = math.ceil(CYL_L - cylinder(-ARM_RANGE)[0]) + 36          # what the piston can go in and out: the arm's range
_OUT = math.ceil(cylinder(ARM_RANGE)[0] - CYL_L) + 33          # and a little more
PISTON = CAP_IN + _IN               # the piston's back face from the barrel pin
TUBE_END = PISTON + 90.0 + _OUT     # where the gland begins
FIT_BARREL_B = TUBE_END - 102.0


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
        "HYDRAULIC HOSE ARM": (np.array([1290.0, -210.0, 620.0]), _at(arm, (FIT_ARM, -180.0, 0.0))),
        "HYDRAULIC HOSE CYL A": (np.array([930.0, -210.0, 620.0]), _at(barrel, (FIT_BARREL_A, -TUBE_R - 25.0, 0.0))),
        "HYDRAULIC HOSE CYL B": (np.array([1110.0, -210.0, 620.0]), _at(barrel, (FIT_BARREL_B, -TUBE_R - 25.0, 0.0))),
        "CABLE": (np.array([1075.0 + slide, 1050.0, 1860.0]), _at(arm, (GLAND_ARM, 162.0, 0.0))),
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
        "HYDRAULIC HOSE ARM": [((1980.0, -690.0, 1380), (1.0, 0.0, 0.45))] if revision == "A" else
                              [((1800.0, -780.0, 1342.0), (1.0, 0.0, 0.45))],
        # up, over in a hump and down into the port on the barrel's side
        "HYDRAULIC HOSE CYL A": [((1038.0, -30.0, 1110.0), (0.5, 1.0, 0.0))],
        "HYDRAULIC HOSE CYL B": [((1500.0, -180.0, 1260.0), (1.0, 0.45, 0.25))],
        # hangs between the two glands: its lowest point about half-way
        "CABLE": [((2370.0, 918.0, 940.0), (1.0, -0.11, 0.0))],
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


def _big(shape):
    """A shape drawn at the first model's numbers, K times as big (about the origin)."""
    return G.xform(shape, np.diag([K, K, K, 1.0]))


def hoses_model(revision="A"):
    px, pz = PIVOT
    bx, bz = BARREL_PIN
    ax, az = ROD_PIN_ARM
    root = Asm("TEST.FLEX.HOSES")

    # the structure: drawn at the first model's numbers, x K, then the real-size bores
    root.add(Part("BASE", _big(G.box(0, -150, 0, 1200, 600, 100)), YELLOW))
    opx, opz, obx, obz = px / K, pz / K, bx / K, bz / K
    post = _big(G.fuse(G.box(opx - 60, 115, 100, 120, 170, 400), G.box(opx - 40, 115, opz - 120, 80, 30, 160),
                       G.box(opx - 40, 255, opz - 120, 80, 30, 160)))
    root.add(Part("POST", G.cut(post, G.cyl(PIN_R + 0.2, 600, (px, 300, pz), Y)), YELLOW))
    bracket = _big(G.fuse(G.box(obx - 40, 120, 100, 80, 160, 8), G.box(obx - 40, 120, 100, 80, 25, 110),
                          G.box(obx - 40, 255, 100, 80, 25, 110)))
    root.add(Part("BASE.BRACKET", G.cut(bracket, G.cyl(PIN_R, 600, (bx, 300, bz), Y)), YELLOW))
    root.add(Part("BASE.PIN", G.cyl(PIN_R, 510, (bx, 345, bz), Y), CHROME))
    root.add(Part("VALVE BLOCK", _big(G.box(280, -110, 100, 180, 80, 100)), GREY))
    for name, x, flats in (("A", 930.0, 24.0), ("B", 1110.0, 24.0), ("C", 1290.0, 30.0)):
        root.add(Part(f"FITTING VALVE {name}", _hex((x, -210.0, 600.0), Z, flats, 20.0), BRASS))
    root.add(Part("RAIL", _big(G.box(100, 320, 100, 460, 60, 30)), STEEL))

    # the arm, built round its pivot
    arm = Asm("ARM.ASM")
    arm.add(Part("ARM", G.cut(_big(G.box(-50, -50, -50, 1250, 100, 100)), G.cyl(PIN_R + 0.2, 360, (0, -180, 0), Y)),
                 YELLOW))
    arm.add(Part("ARM.PIN", G.cyl(PIN_R, 540, (0, -270, 0), Y), CHROME))
    oax, oaz = ax / K, az / K
    lugs = _big(G.fuse(G.box(oax - 40, -75, -60, 80, 150, 10), G.box(oax - 40, -75, oaz - 40, 80, 20, -60 - (oaz - 40)),
                       G.box(oax - 40, 55, oaz - 40, 80, 20, -60 - (oaz - 40))))
    arm.add(Part("ARM.BRACKET", G.cut(lugs, G.cyl(PIN_R, 600, (ax, -300, az), Y)), YELLOW))
    arm.add(Part("ARM.ROD.PIN", G.cyl(PIN_R, 480, (ax, -240, az), Y), CHROME))
    arm.add(Part("FITTING ARM", _hex((FIT_ARM, -150.0, 0.0), -Y, 30.0, 30.0), BRASS))
    arm.add(Part("CABLE GLAND ARM", G.box(GLAND_ARM, 150, -12, 30, 24, 24), GREY))
    if revision == "B":
        arm.add(Part("ARM.LAMP", G.sphere(90.0), ORANGE), T(3300, 0, 240))
    root.add(arm, arm_matrix())

    # the cylinder, built along X from its barrel pin (x = 0) to its rod pin (x = CYL_L)
    barrel = Asm("CYL.BARREL")
    barrel.add(Part("BARREL.CAP", G.fuse(_x(45, CAP_IN, TUBE_R), _eye(0, EYE_R, PIN_R + 0.2, EYE_W)), GREY))
    barrel.add(Part("BARREL.TUBE", _tube_x(CAP_IN, TUBE_END, BORE_R, TUBE_R), GREY))
    barrel.add(Part("BARREL.GLAND", _tube_x(TUBE_END, TUBE_END + 90, ROD_R + 1.0, TUBE_R), GREY))
    barrel.add(Part("FITTING BARREL A", _hex((FIT_BARREL_A, -TUBE_R, 0.0), -Y, 24.0, 25.0), BRASS))
    barrel.add(Part("FITTING BARREL B", _hex((FIT_BARREL_B, -TUBE_R, 0.0), -Y, 24.0, 25.0), BRASS))
    rod = Asm("CYL.ROD")
    rod.add(Part("PISTON", _x(PISTON, PISTON + 90, PISTON_R), STEEL))
    rod.add(Part("ROD", _x(PISTON + 90, CYL_L - 45, ROD_R), CHROME))
    rod.add(Part("ROD.EYE", _eye(CYL_L, EYE_R, PIN_R + 0.2, EYE_W), STEEL))
    cyl = Asm("CYL.ASM")
    cyl.add(barrel)
    cyl.add(rod)
    root.add(cyl, barrel_matrix())

    # the slide, built round the middle of its carriage's underside
    slide = Asm("SLIDE.ASM")
    slide.add(Part("SLIDE CARRIAGE", _big(G.fuse(G.box(-60, -40, 0, 120, 80, 40), G.box(-20, -20, 40, 40, 40, 470))),
                   BLUE))
    slide.add(Part("SLIDE GLAND", G.cyl(11.0, 25.0, (60, 0, 1467), X), GREY))
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
        assert PISTON - (CYL_L - length) > CAP_IN + 15 and PISTON + 90 + (length - CYL_L) < TUBE_END - 15
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
T1_TIP = (0.0, 0.0, 245.0)          # task 0262: the router x 2.5 as tools/make_test_gantry.py (nose at z 275)
STOCK = (-150.0, -100.0, 0.0, 300.0, 200.0, 30.0)
TRAVEL = {"X": (-375.0, 375.0), "Y": (-250.0, 250.0), "Z": (-220.0, 150.0)}
# where each chain's last pin (its moving end) is drawn, in the model's coordinates (the links keep their size: the
# chains are only longer)
CHAIN_END = {"CHAIN X": (-50.0, 175.0, 822.0), "CHAIN Y": (1065.0, 200.0, -68.0), "CHAIN Z": (-100.0, 15.0, 480.0)}


def _origin(name, on_fixed, on_moving, u, v):
    """Pin 0 of a chain whose last pin is CHAIN_END[name]."""
    lu, lv = chain_pins_2d(on_fixed, on_moving)[-1]
    return tuple(float(c) for c in np.round(np.array(CHAIN_END[name]) - lu * u - lv * v, 6))


# name -> (links on the fixed run, links on the moving run, pin 0, the fixed run's direction, from the fixed run
#          towards the moving run, the assembly it sits in (its fixed side), the axis that moves its far end)
CHAINS = {}


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


for _name, (_f, _m, _u, _v, _a, _ax) in {"CHAIN X": (9, 8, X, Z, "Y.ASM", "X"), "CHAIN Y": (7, 7, -Y, -X, "", "Y"),
                                         "CHAIN Z": (5, 5, Z, X, "X.ASM", "Z")}.items():
    CHAINS[_name] = (_f, _m, _origin(_name, _f, _m, _u, _v), _u, _v, _a, _ax)


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
    from make_test_gantry import stand
    root = Asm("TEST.FLEX.GANTRY")
    link = Part("CHAIN LINK", link_shape(), (0.12, 0.12, 0.13))
    px, py, pz = chain_pins("CHAIN X"), chain_pins("CHAIN Y"), chain_pins("CHAIN Z")

    root.add(Part("BED", G.box(-1000, -750, -100, 2000, 1500, 100), BLUE))
    root.add(Part("MACHINE STAND", stand(), (0.25, 0.27, 0.3)))
    root.add(Part("STOCK 300x200x30", G.box(*STOCK), (0.75, 0.76, 0.78)))
    ys = [p[1] for p in py]
    tray_y0, tray_y1 = min(ys) - 0.5 * (TRAVEL["Y"][1] - TRAVEL["Y"][0]) - 100.0, max(ys) + 60.0
    root.add(Part("CHAIN TRAY Y", G.box(1000, tray_y0, -125, 260, tray_y1 - tray_y0, 25), GREY))
    root.add(Part("CHAIN BRACKET Y FIXED", G.box(py[0][0] - 15, py[0][1] - 2, -100, 30, 30, 62), STEEL))
    root.add(*chain_asm("CHAIN Y", link))

    y_asm = Asm("Y.ASM")
    y_asm.add(Part("GANTRY SIDE L", G.box(-1025, 100, 2.5, 50, 150, 647.5), BLUE))
    y_asm.add(Part("GANTRY SIDE R", G.box(975, 100, 2.5, 50, 150, 647.5), BLUE))
    y_asm.add(Part("BEAM", G.box(-975, 100, 500, 1950, 150, 150), BLUE))
    y_asm.add(Part("CHAIN BRACKET X FIXED", G.box(px[0][0] - 28, px[0][1] - 30, 650, 30, 60, 22), STEEL))
    yl = py[-1][1]
    y_asm.add(Part("CHAIN BRACKET Y MOVING", G.fuse(G.box(1025, yl - 30, -36, 52, 36, 10),
                                                    G.box(1025, yl - 30, -36, 10, 36, 50)), STEEL))
    y_asm.add(*chain_asm("CHAIN X", link))

    x_asm = Asm("X.ASM")
    x_asm.add(Part("CARRIAGE", G.box(-125, 65, 375, 250, 32.5, 275), GREY))
    top = px[-1][2] + 12.0
    x_asm.add(Part("CHAIN BRACKET X MOVING", G.fuse(G.box(-37.5, 65, 650, 75, 25, top + 8 - 650),
                                                    G.box(px[-1][0] - 16, 65, top, 52, px[-1][1] + 40 - 65, 8)), STEEL))
    z0 = pz[0][2]
    x_asm.add(Part("CHAIN BRACKET Z FIXED", G.fuse(G.box(-280, 65, z0 - 8, 160, 32.5, 20),
                                                   G.box(pz[0][0] - 15, pz[0][1] - 30, z0 - 8, 30, 95 - pz[0][1], 10)),
                   STEEL))
    x_asm.add(*chain_asm("CHAIN Z", link))

    z_asm = Asm("Z.ASM")
    z_asm.add(Part("SPINDLE", G.cyl(62.5, 300.0, (0, 0, 275)), GREY))
    z_asm.add(Part("TOOL T1 FLAT D6", G.cyl(3.0, 30.0), (0.8, 0.8, 0.82)), T(*T1_TIP))
    z_asm.add(Part("CHAIN BRACKET Z MOVING", G.box(-125, pz[-1][1] - 30, pz[-1][2] - 8, 62.5, 60, 10), STEEL))
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
            for z in (STOCK[5] - T1_TIP[2] + 1.0, 0.0, TRAVEL["Z"][1]):
                move = {"bed": np.eye(4), "Y.ASM": T(0, y, 0), "X.ASM": T(x, y, 0), "Z.ASM": T(x, y, z)}
                now = {k: G.xform(v, move[k]) for k, v in at_rest.items()}
                keys = sorted(now)
                for i, ka in enumerate(keys):
                    for kb in keys[i + 1:]:
                        d = gap(now[ka], now[kb])
                        assert d > 0.9, ("bodies touch", ka, kb, d, x, y, z)
                        least = min(least, d)
    say(f"  bodies over X, Y, Z (Z from {STOCK[5] - T1_TIP[2] + 1:.0f}: 1 mm lower the tool is on the stock): least gap "
        f"{least:.2f} mm")


# +1: the axis' positive direction moves the chain's far end along its fixed run's direction (away from pin 0)
CHAIN_SIGN = {"CHAIN X": 1.0, "CHAIN Y": -1.0, "CHAIN Z": 1.0}


# =====================================================================================================================
# TEST.FLEX.AVOID (task 0298): a block in a hose's way
# =====================================================================================================================
#
#   BASE            box x 0..1600, y -300..300, z 0..60
#   BLOCK           box x 520..920, y -180..180, z 60..400: stands on the base in the hose's way
#   FITTING BASE    hex stub (24 across flats) on the base at (260, 0), z 60..85; the hose leaves its face upwards
#   TOWER           box x 1300..1400, y -100..100, z 60..1000
#   LIFT.ASM        slides along Z beside the tower (3 mm off it), drawn at its middle; travel -400 .. +100
#     LIFT CARRIAGE box x 1180..1297, y -120..120, z 560..680
#     FITTING LIFT  hex stub on the carriage's side at (1180, 0, 620), x 1180 -> 1155; the hose arrives along +X
#   HOSE            Ø20, from FITTING BASE up, over the block (its middle 100 above the block's top) and down into
#                   FITTING LIFT; one solid (a round bar swept along straight pieces and arcs)
#   LAMP            revision B only: a ball Ø120 on top of the tower
#
# Lowered (Lift -400) the lift's fitting is 180 below the block's top: the hose has room to spare and, solved as if
# nothing were there, sags deep into the block; with "Avoid other parts" it lies on it.

AVOID_BLOCK = ((520.0, -180.0, 60.0), (920.0, 180.0, 400.0))
AVOID_HOSE_D = 20.0
AVOID_TRAVEL = (-400.0, 100.0)


def avoid_route():
    return Route((260.0, 0.0, 85.0), Z, (1155.0, 0.0, 620.0), -X, 2.0 * AVOID_HOSE_D,
                 [((720.0, 0.0, 500.0), (1.0, 0.0, 0.0))])


def avoid_model(revision="A"):
    root = Asm("TEST.FLEX.AVOID")
    root.add(Part("BASE", G.box(0, -300, 0, 1600, 600, 60), YELLOW))
    (x0, y0, z0), (x1, y1, z1) = AVOID_BLOCK
    root.add(Part("BLOCK", G.box(x0, y0, z0, x1 - x0, y1 - y0, z1 - z0), GREY))
    root.add(Part("FITTING BASE", _hex((260.0, 0.0, 60.0), Z, 24.0, 25.0), BRASS))
    root.add(Part("TOWER", G.box(1300, -100, 60, 100, 200, 940), STEEL))
    lift = Asm("LIFT.ASM")
    lift.add(Part("LIFT CARRIAGE", G.box(1180, -120, 560, 117, 240, 120), BLUE))
    lift.add(Part("FITTING LIFT", _hex((1180.0, 0.0, 620.0), -X, 24.0, 25.0), BRASS))
    root.add(lift)
    if revision == "B":
        root.add(Part("LAMP", G.sphere(60.0, (1350.0, 0.0, 1060.0)), ORANGE))
    root.add(Part("HOSE", G.route_solid(avoid_route(), AVOID_HOSE_D / 2.0), (0.03, 0.03, 0.03)))
    return root


def check_avoid(root, say=print):
    """The hose as drawn keeps 30 mm and more off the block, and it is long enough for the lift's whole travel."""
    route = avoid_route()
    pts = route.points(2.0)
    lo, hi = map(np.asarray, AVOID_BLOCK)
    gap = np.linalg.norm(np.maximum(np.maximum(lo - pts, pts - hi), 0.0), axis=1).min() - AVOID_HOSE_D / 2.0
    assert gap >= 30.0, f"the hose comes {gap:.1f} mm near the block"
    for dz in AVOID_TRAVEL:
        inner = np.linalg.norm(route.end1 + (0.0, 0.0, dz) + route.straight * route.out1
                               - route.end0 - route.straight * route.out0)
        spare = route.length - 2.0 * route.straight - inner
        assert spare >= 30.0, f"the hose is too short at lift {dz:+.0f} ({spare:.1f} to spare)"
    say(f"avoid: hose {route.length:.1f} long, {gap:.1f} off the block as drawn")


def numbers(say=print):
    say(f"cylinder: pin to pin {CYL_L:.2f} at {CYL_ANGLE:.2f}°; {cylinder(-ARM_RANGE)[0]:.2f} .. "
        f"{cylinder(ARM_RANGE)[0]:.2f} over the arm's range; piston back face {PISTON:.0f}, tube to {TUBE_END:.0f}: "
        f"{PISTON - CAP_IN:.0f} in, {TUBE_END - PISTON - 90:.0f} out, closed {CYL_L - (PISTON - CAP_IN):.2f}, "
        f"full stroke {TUBE_END - CAP_IN - 90:.0f}")
    lo = hi = 0.0
    for a in np.linspace(-30, 30, 6001):
        if CYL_L - (PISTON - CAP_IN) <= cylinder(a)[0] <= CYL_L + TUBE_END - PISTON - 90:
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
    elif what == "avoid":
        root = avoid_model(argv[3] if len(argv) > 3 else "A")
        check_avoid(root)
    else:
        raise SystemExit("usage: make_test_flex.py hoses|chains|avoid out.step [A|B]   or   make_test_flex.py numbers")
    STEPControl_Writer()                                # (makes the setting below known)
    if not Interface_Static.SetIVal_s("write.surfacecurve.mode", 0):   # no curves-on-surface: a smaller file
        raise RuntimeError("the STEP writer does not know write.surfacecurve.mode")
    G.write_step(root, path)
    print(f"written: {G.count_parts(root)} parts, {os.path.getsize(path) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
