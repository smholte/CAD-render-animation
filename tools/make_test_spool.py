"""Write the test model for spooling as a STEP assembly (task 0080; generic, invented).

    python tools/make_test_spool.py out.step      TEST.SPOOL   (tests/data/test_spool.step, a copy in
                                                  fresing_render/data/)
    python tools/make_test_spool.py numbers       prints the numbers below, worked out

Two small machines side by side: a winch whose wire rope comes off a spiral-grooved drum over a fairlead sheave on a
level-wind carriage down to a weight, and a carousel whose power cable comes off the top layer of a stored coil, round
a guide sheave on a slewing arm, up to a clamp. All sizes in mm, angles in degrees, Z up. Every part is one solid.
The same numbers are in the code for tests and the app's set-up: ``NUMBERS`` (a dict), ``centreline(which, step)``
(a CAD rope's middle as points), ``Route(which)`` (its arcs and straight runs), ``wound_estimate(which)``, ``PARTS``,
``ASSEMBLIES``, ``UID``.

======================================================================================================================
TEST.SPOOL                                                    22 parts, 21 different shapes, 4 sub-assemblies
======================================================================================================================
1. The winch (drum axis along +Y through (0, 0, 450); the rope runs in the plane y = 0)
  BASE FRAME               x -400..1100, y -420..420, z 0..60, with two bearing pedestals (x -90..90,
                           y ±265..±315, z 60..300): one solid
  BEARING BLOCK (2 x)      x -80..80, y ±270..±310 (centred on y = ±290), z 300..540, a bore Ø61 on the drum axis
  DRUM.ASM                 origin on the drum axis at (0, 0, 450); its own z = the drum axis (= +Y), its own x = +Z
                           (an angle about the drum axis below, beta, runs from +Z towards +X: the turn about +Y)
    WINCH DRUM             barrel with a SPIRAL GROOVE (a true helix, right-handed about +Y): groove radius 10.5, its
                           bottom at r = 150 (so a Ø20 rope's middle lies at r1 = 160 on the first layer), pitch 21.2,
                           lands at r 157; the groove's middle runs from y = -190 to y = +190 (17.925 turns) and is at
                           y = -190 at beta = GROOVE START (below); two flanges Ø600, 20 thick, inner faces at
                           y = -200 / +200; a shaft Ø60 through to y = ±320: one solid
    WIRE ON DRUM           the wound wire as one revolved solid (about the drum axis): inner radius 150 (the groove's
                           bottom: it fills the groove and so lies 7 into the barrel's lands r 150..157, as the
                           wound rope does), layers of Ø20 at rope-middle radii 160, 177.321, 194.641
                           (160 + k * 20 * cos 30°); layers 1 and 2 full width (y -200..200, outer r 187.321),
                           layer 3 (outer r 204.641) from y = -200 to y = -10: the wraps before the one the WIRE ROPE
                           starts with (its middle at y = 0, it covers y -10..10)
  WIRE ROPE                Ø20, one solid (a round bar swept along arcs and lines in the plane y = 0):
                           arc on the drum, 90° about +Y at radius 194.641 (layer 3) from the back
                           (-194.641, 0, 450) over the top to the LEAVE POINT (0, 0, 644.641), heading +X;
                           straight 800 to the top of the fairlead sheave (800, 0, 644.641);
                           arc 90° round it (about +Y) to (900, 0, 544.641), heading -Z;
                           straight 344.641 down to the weight's top (900, 0, 200).   Length 1607.462.
                           Its first quarter turn lies on layer 2 (r 187.321 under it) like a real rope in the
                           valley of the layer below: 2.68 into WIRE ON DRUM's outer face. Paying out turns the drum
                           about +Y (the top moves towards +X).
  LEVEL WIND RAIL          fixed on the base: x 780..820, y -300..300, z 60..100 (along Y at x = 800)
  LEVEL WIND.ASM           origin (800, 0, 0); slides along Y (as drawn at y = 0, travel ±240 on the rail)
    LEVEL WIND CARRIAGE    a block x 750..850, y -60..60, z 100.5..150 with two skirts down beside the rail
                           (0.5 clear of it) and two cheeks (y ±25..±40, x 770..830, z 150..580) with a bore Ø30
                           on the SHEAVE PIN's axis: one solid
    SHEAVE PIN             Ø30 along Y, y -50..50, through both cheeks at (800, y, 544.641)
    FAIRLEAD SHEAVE        on SHEAVE PIN (bore Ø31): rope-middle radius 100 (a round groove of radius 10.5, its
                           bottom at r 90, straight walls out to the rim r 125), 40 wide (y -20..20), hub r 35;
                           centre (800, 0, 544.641), axis Y: its top is at the rope's height z = 644.641
  WEIGHT                   a block on the base: x 870..930, y -80..80, z 60..200; the rope ends on its top

2. The carousel (axis vertical through (3000, 0))
  CAROUSEL BASE            a fixed plinth: cylinder r 900 about the carousel axis, z 0..100
  CAROUSEL.ASM             origin (3000, 0, 0); turns about +Z through it (paying out: clockwise seen from above)
    TURNTABLE              disc r 1000, z 100..140
    INNER CORE             tube r 270..300, z 140..520
    RIM FENCE              tube r 970..1000, z 140..420
    CABLE COIL             the stored cable (Ø40) as one revolved solid: rope-middle radii 340..840 (12.5 turns a
                           layer, 40 apart); layers 1-3 full: r 320..860, z 140..260 (layer 1 laid from the core out,
                           2 back in, 3 out again); layer 4 (z 260..300), laid from the rim inwards, still covers
                           rope-middle radii 600..840: r 580..860 – except the quarter turn the POWER CABLE draws
                           (r 575..620, from +X to +Y) and a notch under the guide sheave (carousel x 570..632,
                           y -115..115, z 260..305), so the CAD cable and the guide sheave are not drawn through it
  SLEW POST                fixed column: cylinder r 100 about the vertical through (4300, 0), z 0..1000
  ARM.ASM                  origin (4300, 0, 0); slews about +Z through it (the ARM PIVOT)
    ARM                    a boss r 100 (z 1000.5..1140) on the post, a beam (x 3540..4400, y -200..50,
                           z 1060..1140) reaching over x = 3600 and a hanger of two cheeks (x 3540..3560 and
                           3640..3660, y -40..40, z 390..1060) with a bore Ø30 on the GUIDE PIN's axis: one solid
    GUIDE PIN              Ø30 along X, x 3530..3670, at (y 0, z 430)
    GUIDE SHEAVE           on GUIDE PIN (bore Ø31): rope-middle radius 150 (round groove of radius 20.5, its bottom
                           at r 130, walls flaring from its widest out to 48 wide at the rim r 170), 50 wide
                           (x 3575..3625), hub r 40; centre (3600, 0, 430), axis X. Its rim reaches down to z 260,
                           the top of layer 3. The cable comes onto it straight off the coil (no free span), so where
                           it still curves round the carousel axis (5..12° before the leave point) it lies up to
                           2.2 mm into the rim's inner lip: a guide 50 wide cannot hold a Ø40 cable bending sideways.
    CABLE CLAMP            a block x 3560..3640, y -190..-110, z 1000..1060 under the arm's beam
  POWER CABLE              Ø40, one solid: a quarter turn on the coil (radius 600, z 280, about the carousel axis,
                           clockwise seen from above) from (3000, 600, 280) to the LEAVE POINT (3600, 0, 280), there
                           heading -Y; 90° up round the guide sheave (about -X) to (3600, -150, 430), heading +Z;
                           straight 570 up to the clamp's underside (3600, -150, 1000).   Length 1748.097.
                           Paying out turns the carousel about -Z (clockwise seen from above).

Colours: BASE FRAME, BEARING BLOCK, LEVEL WIND RAIL, LEVEL WIND CARRIAGE, CAROUSEL BASE, SLEW POST, CABLE CLAMP grey
(0.3, 0.3, 0.3); WINCH DRUM, TURNTABLE, INNER CORE, RIM FENCE, ARM yellow (0.976, 0.659, 0); the sheaves and pins steel
(0.55, 0.57, 0.6); WIRE ROPE and WIRE ON DRUM dark grey (0.13, 0.13, 0.14); POWER CABLE and CABLE COIL black
(0.05, 0.05, 0.05); WEIGHT orange (0.9, 0.35, 0.05).

GROOVE START: the drum's groove (its middle at r 160.5, the rope's at 160) is the first layer of a wound path that
ends at the leave point, laid back from there: layer 3 from y = 0 back to -190 (8.962 turns), a climb of 90° of turn,
layer 2 (17.925 turns, -190 -> +190 going back), a climb of 90°, layer 1 (17.925 turns, +190 -> -190 going back). So
layer 1 starts (y = -190) at beta = GROOVE START = 247.925° (from +Z towards +X about +Y); along the groove
y = -190 + 21.2 * (beta - GROOVE START) / 360°. (A wound path with other climbs sits off the groove by
pitch x the difference / 360°.)

Wound at the start (``wound_estimate``; an ESTIMATE: helix or spiral turns only – the app's own model adds the
climbs between layers):
  drum       layer 1, 2: 17.925 turns x sqrt((2 pi r)^2 + 21.2^2) at r 160 / 177.321; layer 3: 8.962 turns at
             194.641 (y -190 -> 0, ends at the leave point): 18023.708 + 19974.006 + 10962.187 = 48959.901 mm
  carousel   layers 1-3: 12.5 turns of an Archimedean spiral r 340 <-> 840 (its true length 46341.370 each);
             layer 4: 6 turns, r 840 -> 600 (27144.432, ends at the leave point): 166168.543 mm

Checked before the file is written (``check``): every part is one valid solid; no part lies in another except
WIRE ON DRUM in WINCH DRUM (7 mm: the groove's lands), WIRE ROPE in WIRE ON DRUM (2.68: the valley of layer 2) and
POWER CABLE in GUIDE SHEAVE (2.2: the rim's lip, above); the two ropes touch what they lie on (WIRE ROPE: WIRE ON
DRUM, FAIRLEAD SHEAVE, WEIGHT; POWER CABLE: CABLE COIL, GUIDE SHEAVE, CABLE CLAMP) and are 10 mm and more from every
other part (WIRE ROPE: 27.7 from the drum's lands; POWER CABLE: 60 from the arm); parts that move against each other
are 0.5 mm apart (bores, the carriage over its rail, the arm over its post) except the turntable on its plinth and
the guide sheave's rim on the coil's layer 3 (they touch).

Writing the file takes about 10 s (the spiral groove 2-3 s, the check 6 s); 731 KB; the importer reads it in 1.6 s
(Normal: 36,742 triangles, 13,600 of them the drum).

Needs OpenCascade (OCP) and fresing_render/demo_model/geom.py (shapes, the scene tree, the STEP writer; no Blender).
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402
from OCP.BRepCheck import BRepCheck_Analyzer  # noqa: E402
from OCP.BRepExtrema import BRepExtrema_DistShapeShape  # noqa: E402
from OCP.Interface import Interface_Static  # noqa: E402
from OCP.STEPControl import STEPControl_Writer  # noqa: E402

from fresing_render.demo_model import geom as G  # noqa: E402

GREY, YELLOW, STEEL = (0.3, 0.3, 0.3), (0.976, 0.659, 0.0), (0.55, 0.57, 0.6)
ROPE_GREY, BLACK, ORANGE = (0.13, 0.13, 0.14), (0.05, 0.05, 0.05), (0.9, 0.35, 0.05)
COS30 = math.cos(math.radians(30.0))
BORE = 0.5                          # a bore something turns or slides in is this much wider (radius)

# =====================================================================================================================
# the numbers (mm, degrees)
# =====================================================================================================================

# --- the winch -------------------------------------------------------------------------------------------------------
DRUM_C = np.array([0.0, 0.0, 450.0])            # on the drum axis; the axis is +Y
WIRE_D = 20.0
R1 = 160.0                                      # rope middle, first layer
PITCH = 21.2
GROOVE_R = 10.5                                 # the groove's round section
GROOVE_BOTTOM = 150.0                           # = R1 - WIRE_D / 2
LAND_R = 157.0                                  # the barrel's lands between the grooves
FLANGE_IN = (-200.0, 200.0)                     # flanges' inner faces (y)
FLANGE_R, FLANGE_T = 300.0, 20.0
SHAFT_R, SHAFT_END = 30.0, 320.0
DRUM_LAYERS = 3                                 # layers wound, the third partly
LAYER3_TO = 0.0                                 # the third layer's rope middle has reached y = 0
CLIMB = 90.0                                    # degrees of turn between layers (GROOVE START assumes it)
LAYER_R = [R1 + k * WIRE_D * COS30 for k in range(DRUM_LAYERS)]
TURNS = (FLANGE_IN[1] - FLANGE_IN[0] - WIRE_D) / PITCH          # turns in a full layer (17.925)
TURNS3 = (LAYER3_TO - (FLANGE_IN[0] + WIRE_D / 2)) / PITCH       # in the third layer, to the leave point (8.962)
LEAVE = DRUM_C + np.array([0.0, 0.0, LAYER_R[2]])                # top of layer 3, in the plane y = 0
SHEAVE_C = np.array([800.0, 0.0, LEAVE[2] - 100.0])             # the fairlead sheave; axis +Y
SHEAVE_SEAT, SHEAVE_BOTTOM, SHEAVE_RIM, SHEAVE_HALF = 100.0, 90.0, 125.0, 20.0
SHEAVE_GROOVE = 10.5
WEIGHT_TOP = 200.0
WEIGHT_BOX = (870.0, -80.0, 60.0, 930.0, 80.0, WEIGHT_TOP)
RAIL_BOX = (780.0, -300.0, 60.0, 820.0, 300.0, 100.0)
CARRIAGE_HALF_Y = 60.0                          # the carriage's block: y -60..60, so it travels ±240 on the rail
BASE_BOX = (-400.0, -420.0, 0.0, 1100.0, 420.0, 60.0)
BLOCK_Y, BLOCK_HALF = 290.0, 20.0               # bearing blocks: centred on y = ±290, 40 wide
BLOCK_Z = (300.0, 540.0)


def _groove_start():
    """beta (degrees, about +Y from +Z towards +X) where the groove's (layer 1's) middle is at y = -190: the wound path
    laid back from the leave point (beta 0) – layer 3, a climb, layer 2, a climb, layer 1."""
    back = 360.0 * (TURNS3 + 2.0 * TURNS) + 2.0 * CLIMB
    return (-back) % 360.0


GROOVE_START = _groove_start()

# --- the carousel ----------------------------------------------------------------------------------------------------
CAR_C = np.array([3000.0, 0.0, 0.0])            # on the carousel axis; the axis is +Z
CABLE_D = 40.0
R_IN, R_OUT = 340.0, 840.0                      # rope-middle radii of a layer
A_BOT = 140.0                                   # the turntable's top: the coil's underside
COIL_FULL = 3                                   # full layers
COIL_TURNS = (R_OUT - R_IN) / CABLE_D           # 12.5 turns a layer
TOP_FROM = 600.0                                # the top layer still covers rope-middle radii TOP_FROM..R_OUT
LEAVE_R = TOP_FROM
COIL_TOP_Z = A_BOT + (COIL_FULL + 0.5) * CABLE_D                # 280: the top layer's rope middles
C_LEAVE = CAR_C + np.array([LEAVE_R, 0.0, COIL_TOP_Z])          # (3600, 0, 280)
C_START = CAR_C + np.array([0.0, LEAVE_R, COIL_TOP_Z])          # (3000, 600, 280)
GUIDE_C = np.array([3600.0, 0.0, 430.0])        # the guide sheave; axis X
GUIDE_SEAT, GUIDE_BOTTOM, GUIDE_RIM, GUIDE_HALF = 150.0, 130.0, 170.0, 25.0
GUIDE_GROOVE = 20.5
GUIDE_LIP = 24.0                                # the guide's groove flares to 48 wide at its rim (cable Ø40)
CLAMP_BOX = (3560.0, -190.0, 1000.0, 3640.0, -110.0, 1060.0)
CABLE_END = np.array([3600.0, -150.0, 1000.0])
PIVOT = np.array([4300.0, 0.0, 0.0])            # the arm slews about +Z through it
POST_R, POST_TOP = 100.0, 1000.0
PLINTH_R = 900.0
TURNTABLE = (1000.0, 100.0, 140.0)              # radius, z from, z to
CORE = (270.0, 300.0, 140.0, 520.0)             # r in, r out, z from, z to
RIM = (970.0, 1000.0, 140.0, 420.0)
SHEAVE_NOTCH = (570.0, -115.0, 260.0, 632.0, 115.0, 305.0)     # the coil's notch under the guide sheave (carousel x, y)


# =====================================================================================================================
# the ropes' middles: arcs and straight runs in 3D
# =====================================================================================================================

def _rot(v, axis, angle):
    """v turned ``angle`` radians about the unit vector ``axis`` (right hand)."""
    v, k = np.asarray(v, float), np.asarray(axis, float)
    return v * math.cos(angle) + np.cross(k, v) * math.sin(angle) + k * (k @ v) * (1.0 - math.cos(angle))


class Line:
    kind = "line"

    def __init__(self, start, end):
        self.start, self.end = np.asarray(start, float), np.asarray(end, float)
        self.length = float(np.linalg.norm(self.end - self.start))
        self.start_tangent = self.end_tangent = (self.end - self.start) / self.length

    def point(self, s):
        return self.start + self.start_tangent * s

    def tangent(self, s):
        return self.start_tangent


class Arc:
    """On a circle about ``axis`` (unit) through ``centre`` from ``start``, turning ``angle`` degrees about the axis
    (right hand): the rope goes the way the turn carries the start point."""
    kind = "arc"

    def __init__(self, name, centre, axis, start, angle):
        self.name, self.centre, self.axis = name, np.asarray(centre, float), np.asarray(axis, float)
        self.radius = float(np.linalg.norm(np.asarray(start, float) - self.centre))
        self.angle = float(angle)
        self.length = self.radius * math.radians(angle)
        self._r0 = np.asarray(start, float) - self.centre
        self.start, self.end = self.point(0.0), self.point(self.length)
        self.start_tangent, self.end_tangent = self.tangent(0.0), self.tangent(self.length)

    def point(self, s):
        return self.centre + _rot(self._r0, self.axis, s / self.radius)

    def tangent(self, s):
        r = _rot(self._r0, self.axis, s / self.radius)
        return np.cross(self.axis, r) / self.radius


class Route:
    """A CAD rope's middle: ``which`` = "wire" (the winch's WIRE ROPE) or "cable" (the carousel's POWER CABLE)."""

    def __init__(self, which):
        if which == "wire":
            back = DRUM_C + np.array([-LAYER_R[2], 0.0, 0.0])
            a1 = Arc("WIRE ON DRUM", DRUM_C, (0.0, 1.0, 0.0), back, 90.0)
            top = SHEAVE_C + np.array([0.0, 0.0, SHEAVE_SEAT])
            a2 = Arc("FAIRLEAD SHEAVE", SHEAVE_C, (0.0, 1.0, 0.0), top, 90.0)
            self.segments = [a1, Line(a1.end, top), a2, Line(a2.end, (a2.end[0], 0.0, WEIGHT_TOP))]
            self.radius = WIRE_D / 2.0
        elif which == "cable":
            a1 = Arc("CABLE COIL", CAR_C + np.array([0.0, 0.0, COIL_TOP_Z]), (0.0, 0.0, -1.0), C_START, 90.0)
            a2 = Arc("GUIDE SHEAVE", GUIDE_C, (-1.0, 0.0, 0.0), a1.end, 90.0)
            self.segments = [a1, a2, Line(a2.end, CABLE_END)]
            self.radius = CABLE_D / 2.0
        else:
            raise ValueError(which)
        for a, b in zip(self.segments[:-1], self.segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-9 and np.linalg.norm(a.end_tangent - b.start_tangent) < 1e-9
        self.start, self.end = self.segments[0].start, self.segments[-1].end
        self.length = sum(s.length for s in self.segments)
        self.leave_point, self.leave_direction = self.segments[0].end, self.segments[0].end_tangent

    def points(self, step=1.0):
        out = [self.start]
        for seg in self.segments:
            k = max(int(math.ceil(seg.length / step)), 1)
            out += [seg.point(seg.length * i / k) for i in range(1, k + 1)]
        return np.array(out)


def centreline(which, step=1.0):
    """A CAD rope's middle as points (n, 3) in the model's coordinates (mm), ``step`` mm apart or less, from its start
    on the spool to its end: ``which`` = "wire" or "cable"."""
    return Route(which).points(step)


def spiral_length(r0, r1, turns, n=20001):
    """The length of an Archimedean spiral from radius r0 to r1 over ``turns`` turns (mm)."""
    phi = np.linspace(0.0, 2.0 * math.pi * turns, n)
    r = r0 + (r1 - r0) * phi / phi[-1]
    dr = (r1 - r0) / phi[-1]
    f = np.sqrt(r * r + dr * dr)
    return float(np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(phi)))


def wound_estimate(which):
    """How much rope is on the spool at the start, ending at the leave point (mm): an ESTIMATE from the turns only
    (helix turns per drum layer, spiral turns per carousel layer); the app's own model adds the climbs between layers.
    Returns {"layers": [mm per layer], "total": mm}."""
    if which in ("wire", "drum"):
        def helix(r, turns):
            return turns * math.hypot(2.0 * math.pi * r, PITCH)
        layers = [helix(LAYER_R[0], TURNS), helix(LAYER_R[1], TURNS), helix(LAYER_R[2], TURNS3)]
    elif which in ("cable", "carousel"):
        full = spiral_length(R_IN, R_OUT, COIL_TURNS)
        layers = [full] * COIL_FULL + [spiral_length(R_OUT, TOP_FROM, (R_OUT - TOP_FROM) / CABLE_D)]
    else:
        raise ValueError(which)
    return {"layers": [round(v, 3) for v in layers], "total": round(sum(layers), 3)}


def _t(p):
    return tuple(round(float(v), 4) for v in p)


def _numbers():
    wire, cable = Route("wire"), Route("cable")

    def segments(route):
        return [{"kind": s.kind, "on": getattr(s, "name", ""), "start": _t(s.start), "end": _t(s.end),
                 "length": round(s.length, 4)} for s in route.segments]
    fair, guide = wire.segments[2], cable.segments[1]
    return {
        "units": "mm, degrees",
        "winch": {
            "drum": {"uid": UID["WINCH DRUM"], "assembly": UID["DRUM.ASM"], "wire_uid": UID["WIRE ON DRUM"],
                     "axis_point": _t(DRUM_C), "axis_direction": (0.0, 1.0, 0.0), "d": WIRE_D, "r1": R1,
                     "groove_bottom": GROOVE_BOTTOM, "groove_radius": GROOVE_R, "land_radius": LAND_R,
                     "pitch": PITCH, "flange_inner": FLANGE_IN, "flange_radius": FLANGE_R, "shaft_end": SHAFT_END,
                     "layer_radii": [round(r, 4) for r in LAYER_R], "layers": DRUM_LAYERS, "layer3_reached": LAYER3_TO,
                     "turns_per_layer": round(TURNS, 6), "turns_layer3": round(TURNS3, 6), "climb": CLIMB,
                     "groove_start": round(GROOVE_START, 4), "hand": "right-handed about +Y (layer 1)",
                     "pays_out": "turns about +Y (the top moves towards +X)",
                     "wire_inner_radius": GROOVE_BOTTOM, "wire_outer_radii": (round(LAYER_R[1] + WIRE_D / 2, 4),
                                                                              round(LAYER_R[2] + WIRE_D / 2, 4)),
                     "wire_layer3_to": LAYER3_TO - WIRE_D / 2},
            "rope": {"uid": UID["WIRE ROPE"], "d": WIRE_D, "start": _t(wire.start), "end": _t(wire.end),
                     "leave_point": _t(wire.leave_point), "leave_direction": _t(wire.leave_direction),
                     "length": round(wire.length, 4), "segments": segments(wire)},
            "fairlead": {"uid": UID["FAIRLEAD SHEAVE"], "pin_uid": UID["SHEAVE PIN"], "axis_point": _t(SHEAVE_C),
                         "axis_direction": (0.0, 1.0, 0.0), "seat_radius": SHEAVE_SEAT,
                         "surface_radius": SHEAVE_BOTTOM, "rim_radius": SHEAVE_RIM, "width": 2 * SHEAVE_HALF,
                         "side": 1, "wrap": 90.0, "tangent_in": _t(fair.start), "tangent_out": _t(fair.end)},
            "level_wind": {"uid": UID["LEVEL WIND.ASM"], "carriage_uid": UID["LEVEL WIND CARRIAGE"],
                           "rail_uid": UID["LEVEL WIND RAIL"], "direction": (0.0, 1.0, 0.0), "at": 0.0,
                           "travel": (RAIL_BOX[1] + CARRIAGE_HALF_Y, RAIL_BOX[4] - CARRIAGE_HALF_Y)},
            "weight": {"uid": UID["WEIGHT"], "top": WEIGHT_TOP},
            "wound_estimate": wound_estimate("wire"),
        },
        "carousel": {
            "spool": {"assembly": UID["CAROUSEL.ASM"], "turntable_uid": UID["TURNTABLE"], "core_uid": UID["INNER CORE"],
                      "rim_uid": UID["RIM FENCE"], "coil_uid": UID["CABLE COIL"], "axis_point": _t(CAR_C),
                      "axis_direction": (0.0, 0.0, 1.0), "d": CABLE_D, "r_in": R_IN, "r_out": R_OUT,
                      "a_bot": A_BOT, "full_layers": COIL_FULL, "turns_per_layer": COIL_TURNS,
                      "top_layer_from": TOP_FROM, "top_layer_z": COIL_TOP_Z, "leave_radius": LEAVE_R,
                      "pays_out": "turns about -Z (clockwise seen from above)",
                      "coil_radii": (R_IN - CABLE_D / 2, R_OUT + CABLE_D / 2),
                      "coil_z": (A_BOT, A_BOT + (COIL_FULL + 1) * CABLE_D)},
            "cable": {"uid": UID["POWER CABLE"], "d": CABLE_D, "start": _t(cable.start), "end": _t(cable.end),
                      "leave_point": _t(cable.leave_point), "leave_direction": _t(cable.leave_direction),
                      "length": round(cable.length, 4), "segments": segments(cable)},
            "guide": {"uid": UID["GUIDE SHEAVE"], "pin_uid": UID["GUIDE PIN"], "axis_point": _t(GUIDE_C),
                      "axis_direction": (1.0, 0.0, 0.0), "seat_radius": GUIDE_SEAT, "surface_radius": GUIDE_BOTTOM,
                      "rim_radius": GUIDE_RIM, "width": 2 * GUIDE_HALF, "wrap": 90.0,
                      "tangent_in": _t(guide.start), "tangent_out": _t(guide.end)},
            "arm": {"uid": UID["ARM.ASM"], "arm_uid": UID["ARM"], "post_uid": UID["SLEW POST"],
                    "pivot": _t(PIVOT), "axis_direction": (0.0, 0.0, 1.0), "clamp_uid": UID["CABLE CLAMP"],
                    "reach": round(float(np.linalg.norm(GUIDE_C[:2] - PIVOT[:2])), 4)},
            "wound_estimate": wound_estimate("cable"),
        },
    }


# =====================================================================================================================
# the scene: parts, assemblies, IDs
# =====================================================================================================================

PARTS = ["BASE FRAME", "BEARING BLOCK", "BEARING BLOCK", "WINCH DRUM", "WIRE ON DRUM", "LEVEL WIND RAIL",
         "LEVEL WIND CARRIAGE", "SHEAVE PIN", "FAIRLEAD SHEAVE", "WEIGHT", "WIRE ROPE", "CAROUSEL BASE", "TURNTABLE",
         "INNER CORE", "RIM FENCE", "CABLE COIL", "SLEW POST", "ARM", "GUIDE PIN", "GUIDE SHEAVE", "CABLE CLAMP",
         "POWER CABLE"]
ASSEMBLIES = ["TEST.SPOOL", "DRUM.ASM", "LEVEL WIND.ASM", "CAROUSEL.ASM", "ARM.ASM"]
_IN = {"WINCH DRUM": "DRUM.ASM", "WIRE ON DRUM": "DRUM.ASM", "LEVEL WIND CARRIAGE": "LEVEL WIND.ASM",
       "SHEAVE PIN": "LEVEL WIND.ASM", "FAIRLEAD SHEAVE": "LEVEL WIND.ASM", "TURNTABLE": "CAROUSEL.ASM",
       "INNER CORE": "CAROUSEL.ASM", "RIM FENCE": "CAROUSEL.ASM", "CABLE COIL": "CAROUSEL.ASM", "ARM": "ARM.ASM",
       "GUIDE PIN": "ARM.ASM", "GUIDE SHEAVE": "ARM.ASM", "CABLE CLAMP": "ARM.ASM"}
UID = {name: f"TEST.SPOOL#1/{_IN[name] + '#1/' if name in _IN else ''}{name}#1" for name in PARTS}
UID.update({name: f"TEST.SPOOL#1/{name}#1" for name in ASSEMBLIES[1:]})
UID["BEARING BLOCK 2"] = "TEST.SPOOL#1/BEARING BLOCK#2"
NUMBERS = _numbers()

# =====================================================================================================================
# shapes (OpenCascade, through demo_model/geom.py)
# =====================================================================================================================


def box(x0, y0, z0, x1, y1, z1):
    """A box from corner to corner."""
    return G.box(min(x0, x1), min(y0, y1), min(z0, z1), abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))


def ring(r_in, r_out, z0, z1):
    """A tube about +Z through the origin."""
    return G.revolve([(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)])


def sheave(bottom, groove_r, rim, half, lip, bore, hub_r, web_half):
    """A sheave about its local z through the origin: a round groove (radius ``groove_r``, its bottom at r ``bottom``)
    up to its widest, then straight walls out to the rim where the groove is ``2 lip`` wide (``lip`` = ``groove_r``:
    parallel walls); the rim ``2 half`` wide; a web and a hub with a bore."""
    c = bottom + groove_r
    ri = bottom - 15.0
    return G.revolve([(bore, -half), (hub_r, -half), (hub_r, -web_half), (ri, -web_half), (ri, -half), (rim, -half),
                      (rim, -lip), (c, -groove_r), ("arc", (bottom, 0.0), (c, groove_r)), (rim, lip),
                      (rim, half), (ri, half), (ri, web_half), (hub_r, web_half), (hub_r, half), (bore, half)])


# local z -> the drum axis (+Y), local x -> +Z: beta (from +Z towards +X) is the local angle from x towards y
DRUM_FRAME = G.Frame(DRUM_C, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))


def winch_drum():
    """In DRUM.ASM's coordinates (z = the drum axis): barrel with the spiral groove, flanges, shaft."""
    lo, hi = FLANGE_IN
    start = lo + WIRE_D / 2.0
    helix = G._helix_edge(GROOVE_BOTTOM + GROOVE_R, start, PITCH, TURNS)
    groove = G.xform(G.sweep_round(helix, GROOVE_R), G.Rot((0.0, 0.0, 1.0), GROOVE_START))
    barrel = G.cut(G.cyl(LAND_R, hi - lo, (0.0, 0.0, lo)), groove)
    return G.fuse(barrel, G.cyl(FLANGE_R, FLANGE_T, (0.0, 0.0, hi)),
                  G.cyl(FLANGE_R, FLANGE_T, (0.0, 0.0, lo - FLANGE_T)),
                  G.cyl(SHAFT_R, 2.0 * SHAFT_END, (0.0, 0.0, -SHAFT_END)))


def wire_on_drum():
    """In DRUM.ASM's coordinates: the wound layers as one revolved solid."""
    lo, hi = FLANGE_IN
    o2, o3 = LAYER_R[1] + WIRE_D / 2.0, LAYER_R[2] + WIRE_D / 2.0
    to = LAYER3_TO - WIRE_D / 2.0
    return G.revolve([(GROOVE_BOTTOM, lo), (GROOVE_BOTTOM, hi), (o2, hi), (o2, to), (o3, to), (o3, lo)])


def base_frame():
    parts = [box(*BASE_BOX)]
    for s in (1, -1):
        parts.append(box(-90.0, s * (BLOCK_Y - 25.0), BASE_BOX[5], 90.0, s * (BLOCK_Y + 25.0), BLOCK_Z[0]))
    return G.fuse(*parts)


def bearing_block():
    """Centred on its own origin on the drum axis (placed at y = ±290)."""
    z0, z1 = BLOCK_Z[0] - DRUM_C[2], BLOCK_Z[1] - DRUM_C[2]
    return G.cut(box(-80.0, -BLOCK_HALF, z0, 80.0, BLOCK_HALF, z1),
                 G.rod((0.0, -BLOCK_HALF - 10.0, 0.0), (0.0, BLOCK_HALF + 10.0, 0.0), SHAFT_R + BORE))


def carriage():
    """In LEVEL WIND.ASM's coordinates (origin (800, 0, 0)): block, skirts beside the rail, cheeks with the pin bore."""
    h = CARRIAGE_HALF_Y
    rail_half = 0.5 * (RAIL_BOX[3] - RAIL_BOX[0])
    top = RAIL_BOX[5]
    parts = [box(-50.0, -h, top + BORE, 50.0, h, 150.0),
             box(-50.0, -h, top - 20.0, -rail_half - BORE, h, top + BORE),
             box(rail_half + BORE, -h, top - 20.0, 50.0, h, top + BORE)]
    for s in (1, -1):
        parts.append(box(-30.0, s * 25.0, 150.0, 30.0, s * 40.0, 580.0))
    pin = G.rod((0.0, -60.0, SHEAVE_C[2]), (0.0, 60.0, SHEAVE_C[2]), 15.0)
    return G.cut(G.fuse(*parts), pin)


def arm():
    """In ARM.ASM's coordinates (origin on the pivot): boss, beam, hanger cheeks with the guide pin's bore."""
    gx = GUIDE_C[0] - PIVOT[0]
    parts = [G.cyl(POST_R, 1140.0 - (POST_TOP + BORE), (0.0, 0.0, POST_TOP + BORE)),
             box(gx - 60.0, -200.0, 1060.0, 100.0, 50.0, 1140.0)]
    for x0 in (gx - 60.0, gx + 40.0):
        parts.append(box(x0, -40.0, GUIDE_C[2] - 40.0, x0 + 20.0, 40.0, 1060.0))
    pin = G.rod((gx - 80.0, 0.0, GUIDE_C[2]), (gx + 80.0, 0.0, GUIDE_C[2]), 15.0)
    return G.cut(G.fuse(*parts), pin)


def cable_coil():
    """In CAROUSEL.ASM's coordinates (z = the carousel axis): layers 1-3 full and the top layer from r 580, less the
    quarter turn the POWER CABLE draws and a notch under the guide sheave."""
    lo, hi = R_IN - CABLE_D / 2.0, R_OUT + CABLE_D / 2.0
    z3, z4 = A_BOT + COIL_FULL * CABLE_D, A_BOT + (COIL_FULL + 1) * CABLE_D
    top_in = TOP_FROM - CABLE_D / 2.0
    coil = G.revolve([(lo, A_BOT), (hi, A_BOT), (hi, z4), (top_in, z4), (top_in, z3), (lo, z3)])
    quarter = G.revolve([(top_in - 5.0, z3), (TOP_FROM + CABLE_D / 2.0, z3), (TOP_FROM + CABLE_D / 2.0, z4 + 5.0),
                         (top_in - 5.0, z4 + 5.0)], angle=90.0)          # from +X towards +Y: where the cable lies
    x0, y0, za, x1, y1, zb = SHEAVE_NOTCH
    return G.cut(coil, quarter, box(x0, y0, za, x1, y1, zb))


def rope_part(which):
    route = Route(which)
    return G.route_solid(route, route.radius)


def model():
    root = G.Asm("TEST.SPOOL")
    # the winch
    root.add(G.Part("BASE FRAME", base_frame(), GREY))
    block = G.Part("BEARING BLOCK", bearing_block(), GREY)
    root.add(block, G.T(DRUM_C[0], BLOCK_Y, DRUM_C[2]))
    root.add(block, G.T(DRUM_C[0], -BLOCK_Y, DRUM_C[2]))
    drum = G.Asm("DRUM.ASM")
    drum.add(G.Part("WINCH DRUM", winch_drum(), YELLOW))
    drum.add(G.Part("WIRE ON DRUM", wire_on_drum(), ROPE_GREY))
    root.add(drum, DRUM_FRAME)
    root.add(G.Part("LEVEL WIND RAIL", box(*RAIL_BOX), GREY))
    lw = G.Asm("LEVEL WIND.ASM")
    lw.add(G.Part("LEVEL WIND CARRIAGE", carriage(), GREY))
    on_pin = G.Frame((0.0, 0.0, SHEAVE_C[2]), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))       # local z along +Y
    lw.add(G.Part("SHEAVE PIN", G.cyl(15.0, 100.0, (0.0, 0.0, -50.0)), STEEL), on_pin)
    lw.add(G.Part("FAIRLEAD SHEAVE", sheave(SHEAVE_BOTTOM, SHEAVE_GROOVE, SHEAVE_RIM, SHEAVE_HALF, SHEAVE_GROOVE,
                                            15.0 + BORE, 35.0, 8.0), STEEL), on_pin)
    root.add(lw, G.T(SHEAVE_C[0], 0.0, 0.0))
    root.add(G.Part("WEIGHT", box(*WEIGHT_BOX), ORANGE))
    root.add(G.Part("WIRE ROPE", rope_part("wire"), ROPE_GREY))
    # the carousel
    root.add(G.Part("CAROUSEL BASE", G.cyl(PLINTH_R, TURNTABLE[1], tuple(CAR_C)), GREY))
    car = G.Asm("CAROUSEL.ASM")
    car.add(G.Part("TURNTABLE", G.cyl(TURNTABLE[0], TURNTABLE[2] - TURNTABLE[1], (0.0, 0.0, TURNTABLE[1])), YELLOW))
    car.add(G.Part("INNER CORE", ring(*CORE), YELLOW))
    car.add(G.Part("RIM FENCE", ring(*RIM), YELLOW))
    car.add(G.Part("CABLE COIL", cable_coil(), BLACK))
    root.add(car, G.T(*CAR_C))
    root.add(G.Part("SLEW POST", G.cyl(POST_R, POST_TOP, tuple(PIVOT)), GREY))
    am = G.Asm("ARM.ASM")
    am.add(G.Part("ARM", arm(), YELLOW))
    gx = GUIDE_C[0] - PIVOT[0]
    on_guide = G.Frame((gx, 0.0, GUIDE_C[2]), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))       # local z along +X
    am.add(G.Part("GUIDE PIN", G.cyl(15.0, 140.0, (0.0, 0.0, -70.0)), STEEL), on_guide)
    guide = sheave(GUIDE_BOTTOM, GUIDE_GROOVE, GUIDE_RIM, GUIDE_HALF, GUIDE_LIP, 15.0 + BORE, 40.0, 10.0)
    am.add(G.Part("GUIDE SHEAVE", guide, STEEL), on_guide)
    x0, y0, z0, x1, y1, z1 = CLAMP_BOX
    am.add(G.Part("CABLE CLAMP", box(x0 - PIVOT[0], y0, z0, x1 - PIVOT[0], y1, z1), GREY))
    root.add(am, G.T(*PIVOT))
    root.add(G.Part("POWER CABLE", rope_part("cable"), BLACK))
    return root


def placed(root):
    """Every part once per place: (name, uid, shape in the model's coordinates)."""
    return [(node.name, uid, G.xform(node.shape, W)) for node, uid, W, _label, _path in G.walk(root)
            if isinstance(node, G.Part)]


def bounds(shape):
    """The exact box (lo, hi) of a shape (mm)."""
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def write_step(root, path):
    STEPControl_Writer()                                # (makes the setting below known)
    if not Interface_Static.SetIVal_s("write.surfacecurve.mode", 0):   # no curves-on-surface: a smaller file
        raise RuntimeError("the STEP writer does not know write.surfacecurve.mode")
    G.write_step(root, path)


# ---------------------------------------------------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------------------------------------------------

OVERLAPS = {frozenset(("WINCH DRUM", "WIRE ON DRUM")): 7.0, frozenset(("WIRE ON DRUM", "WIRE ROPE")): 2.68,
            frozenset(("GUIDE SHEAVE", "POWER CABLE")): 2.2}     # the pairs drawn into each other, how deep (mm)
TOUCHES = {"WIRE ROPE": ("WIRE ON DRUM", "FAIRLEAD SHEAVE", "WEIGHT"),
           "POWER CABLE": ("CABLE COIL", "GUIDE SHEAVE", "CABLE CLAMP")}


def check(root, say=print):
    parts = placed(root)
    assert [p[0] for p in parts] == PARTS
    boxes = []
    for name, _uid, shape in parts:
        assert G.solids(shape) == 1 and BRepCheck_Analyzer(shape).IsValid() and G.volume(shape) > 0, name
        boxes.append(bounds(shape))
    near = {k: (math.inf, "") for k in TOUCHES}
    for i, (na, _ua, sa) in enumerate(parts):
        for j in range(i + 1, len(parts)):
            nb, _ub, sb = parts[j]
            apart = np.maximum(np.maximum(boxes[i][0] - boxes[j][1], boxes[j][0] - boxes[i][1]), 0.0)
            if np.linalg.norm(apart) > 20.0:
                continue
            d = float(BRepExtrema_DistShapeShape(sa, sb).Value())
            if d < 1e-6:
                v = G.volume(BRepAlgoAPI_Common(sa, sb).Shape())
                if frozenset((na, nb)) in OVERLAPS:
                    assert v > 1.0, (na, nb, "should overlap", v)
                else:
                    assert v < 1e-3, (na, "lies inside", nb, v)
            for rope, touched in TOUCHES.items():
                if rope in (na, nb) and na != nb:
                    other = nb if na == rope else na
                    if other in touched:
                        assert d < 1e-4, (rope, "does not touch", other, d)
                    else:
                        near[rope] = min(near[rope], (d, other))
    for rope, (d, other) in near.items():
        assert d >= 10.0, (rope, "too near", other, d)
        route = Route("wire" if rope == "WIRE ROPE" else "cable")
        shape = next(s for n, _u, s in parts if n == rope)
        assert abs(G.volume(shape) / (math.pi * route.radius ** 2 * route.length) - 1.0) < 1e-6, rope
        say(f"  {rope}: touches {', '.join(TOUCHES[rope])}; nearest other part {d:.1f} ({other})")


def numbers(say=print):
    for which in ("wire", "cable"):
        r = Route(which)
        say(f"{which}: length {r.length:.3f}, start {np.round(r.start, 3)}, leave {np.round(r.leave_point, 3)} "
            f"heading {np.round(r.leave_direction, 6)}, end {np.round(r.end, 3)}")
        for seg in r.segments:
            say(f"  {seg.kind:4s} {getattr(seg, 'name', ''):16s} {np.round(seg.start, 3)} -> {np.round(seg.end, 3)} "
                f"length {seg.length:.3f}")
        w = wound_estimate(which)
        say(f"  wound (estimate): layers {w['layers']}, total {w['total']}")
    say(f"drum layer radii {np.round(LAYER_R, 4)}, turns a layer {TURNS:.4f}, layer 3 {TURNS3:.4f}, "
        f"groove start {GROOVE_START:.4f}°")


def main(argv):
    if len(argv) < 2 or argv[1] == "numbers":
        numbers()
        return 0
    root = model()
    check(root)
    write_step(root, argv[1])
    print(f"written: {G.count_parts(root)} parts, {os.path.getsize(argv[1]) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
