"""Write the test model for cable paths as a STEP assembly (task 0078; generic, invented).

    python tools/make_test_paths.py out.step [A|B]    TEST.PATHS   (tests/data/test_paths_a.step / _b.step, copies in
                                                      fresing_render/data/)
    python tools/make_test_paths.py numbers           prints the rope's numbers as drawn and luffed -15° / +15°

A small winch spread: a wire rope comes off a drum, goes over a sheave at the top of a luffing A-frame, back down
under a second sheave at its foot, level through a V-roller cradle and over a chute at the end of the base.
All sizes in mm, angles in degrees, Z up. Every part is one solid. Everything the rope does lies in the plane
y = 0 (the model is symmetric about it, the two V rollers apart): below, a point "(x, z)" lies in that plane.
The same numbers are in the code for tests to use: ``NUMBERS`` (a dict, as drawn), ``numbers_at(luff)`` (the same
with the A-frame luffed and the rope laid anew), ``centreline(luff, step)`` (the rope's middle as points),
``Route(luff)`` (its arcs and straight runs), ``PARTS``, ``ASSEMBLIES``, ``UID``.

======================================================================================================================
TEST.PATHS                                             17 parts (revision B: 18), 14 different shapes (B: 15)
======================================================================================================================
  BASE FRAME               two rails (x 0..3150, y ±280..±380, z 0..100), cross members between them, a deck at
                           x 2300..3150 and the two hinge towers (y ±195..±365, a fork of two lugs on each with a
                           bore Ø51 on the luff axis), all one solid; its top is z = 100
  WINCH DRUM               about Y through (450, 450): plain barrel Ø400 (y -200..200) between two flanges Ø600
                           (20 thick), a shaft stub Ø80 either side out to y = ±340
  BEARING BLOCK (2 x)      pedestals at y = ±290 (80 wide) with a bore Ø81 the drum's shaft turns in
  A-FRAME.ASM              turns about the LUFF AXIS: point (1500, 0, 730), direction +Y. As drawn it leans 20°
                           from the vertical towards +X. Its own coordinates: origin on the luff axis, z along the
                           legs, x square to them (front); placed with a turn of 20° about +Y.
    A-FRAME                two legs (y ±230..±330, 120 thick, from 70 below the luff axis to 1280 above it along
                           the legs), a top cross beam behind the legs (800..900 along the legs), a lower cross
                           beam in front of them (310..410) and two cheek plates (y ±40..±60) from the lower beam
                           back to SHEAVE 2's pin: one solid
    HINGE PIN (2 x)        Ø50 x 190 along Y on the luff axis, one through each leg's foot and its tower's fork
                           (y = ±185..±375): pick one to find the luff axis
    SHEAVE PIN 1           Ø50 along Y through both legs, 1200 from the luff axis along the legs
    SHEAVE 1               on SHEAVE PIN 1 (bore Ø51), groove in the plane y = 0; as drawn about (1910.424, 1857.631)
    SHEAVE PIN 2           Ø40 along Y through the two cheeks
    SHEAVE 2               on SHEAVE PIN 2 (bore Ø41); in A-FRAME.ASM at x = -34.202, z = 93.969: as drawn 100
                           straight above the luff axis, about (1500, 830)
  V CRADLE.ASM
    CRADLE STAND           a plate on the deck and, for each roller, a yoke (two cheeks with a bore Ø31, a bar
                           under the roller) on a web down to the plate: one solid
    V ROLLER (2 x)         plain cylinder Ø120 x 220 with a stub Ø30 x 25 at each end; its own z is its axis, its
                           origin the point of its axis nearest the rope (40 from its low end). The two stand one
                           behind the other along the rope (x = 2400 and x = 2540), 40° from the horizontal,
                           square to the rope: seen along the rope they make a V the rope lies in.
  CHUTE                    a quarter-round trough: a U section (round bottom of radius 20, walls 10 thick) bent
                           round the bend axis, 65° of a circle (from 7.5° before the top to 57.5° past it):
                           clearly not round all the way
  CHUTE STAND              a pedestal on a foot plate; its top is a row of flats whose corners touch the chute's
                           underside (no round face: the chute, not its stand, has the bend axis)
  WIRE ROPE                Ø24, one solid: a round bar swept along the arcs and straight runs below
  GUARD                    revision B only: a plate (x 40..60, y -250..250, z 100..820) on the base behind the drum

Colours: BASE FRAME, BEARING BLOCK, CRADLE STAND, CHUTE STAND grey (0.3, 0.3, 0.3); A-FRAME yellow (0.976, 0.659, 0);
WINCH DRUM, SHEAVE 1, SHEAVE 2, V ROLLER, CHUTE steel grey (0.55, 0.57, 0.6); the pins (0.85, 0.86, 0.88); WIRE ROPE
dark grey (0.13, 0.13, 0.14); GUARD orange (0.9, 0.35, 0.05).

What the rope lies on. "Surface" is the radius from the axis to the surface under the rope, "seat" the radius to
the rope's middle (surface + 12). Side = sign(((p - c) x t) . axis) for a point p of the rope on the wheel, the
wheel's centre c, the rope's direction t (start -> end) and the axis direction listed: +1 = the rope goes round
turning about +Y (from +Z towards +X: over the top towards +X), -1 the other way.

  WINCH DRUM   axis (450, 0, 450), direction +Y     barrel 200, seat 212            side -1   (under the drum)
  SHEAVE 1     axis (1910.424, 0, 1857.631), +Y     groove bottom 238, seat 250     side +1   (over the top)
  SHEAVE 2     axis (1500, 0, 830), +Y              groove bottom 168, seat 180     side -1   (underneath)
  CHUTE        axis (2700, 0, 50), +Y               trough bottom 588, seat 600     side +1   (over the top);
                                                    does not turn
  The sheaves' groove: a round bottom of radius 13 (its middle 1 above the rope's), 70° up either side, straight
  flanks from there (20° from the sheave's plane), flanges 28 above the groove's bottom (SHEAVE 1 Ø532, SHEAVE 2
  Ø392 over the flanges); rims 56 wide, hubs 70. The rope touches a sheave along its groove's bottom only.

  V ROLLER 1   axis through (2400,  46.281, 594.845), direction (0,  0.766044, 0.642788)   surface 60, seat 72
               the rope touches it at (2400,  7.713, 640.807); the rope's middle there (2400, 0, 650)
  V ROLLER 2   axis through (2540, -46.281, 594.845), direction (0, -0.766044, 0.642788)   surface 60, seat 72
               the rope touches it at (2540, -7.713, 640.807); the rope's middle there (2540, 0, 650)
  (the points given on the axes are those nearest the rope; the rope runs straight on over the rollers: no bend)

The rope's middle as drawn, from its start to its free end (length 7022.212):

  start        (238, 450): on the drum, at its -X side (180° round it from +X), going down
  WINCH DRUM   arc of 147.111° (544.326)      (238, 450)           -> (628.022, 334.882)
  straight     1975.049 at +57.111°           (628.022, 334.882)   -> (1700.493, 1993.384)
  SHEAVE 1     arc of 191.749° (836.664)      (1700.493, 1993.384) -> (2088.314, 1681.975)
  straight     1019.595 at -134.638°          (2088.314, 1681.975) -> (1371.919, 956.473)
  SHEAVE 2     arc of 134.638° (422.978)      (1371.919, 956.473)  -> (1500, 650)
  straight     1200 at 0° (level, z = 650)    (1500, 650)          -> (2700, 650)      through the V-cradle
  CHUTE        arc of 50° (523.599)           (2700, 650)          -> (3159.627, 435.673)
  straight     500 at -50° (the free end)     (3159.627, 435.673)  -> end (3481.020, 52.650)
  (directions: degrees from +X towards +Z. Every arc meets its runs without a kink.)

Luffing. A joint about the luff axis, direction +Y: + leans the A-frame further forward (towards +X and down),
- sets it more upright. The model is made for -15° .. +15° (the frame then leans 5° .. 35°). The two sheaves
ride on the frame, so the run between them stays as it is in the frame; the rope's start on the drum and the end
of its arc on the chute stay where they are; the rest is laid anew (``Route(luff)``, ``numbers_at(luff)``):

  luff   length     wrap on DRUM / SHEAVE 1 / SHEAVE 2 / CHUTE     SHEAVE 1 about          SHEAVE 2 about
  -15°   6849.652   156.232 / 185.870 / 119.798 / 50.159           (1604.587, 1925.434)    (1474.118, 826.593)
    0°   7022.212   147.111 / 191.749 / 134.638 / 50.000           (1910.424, 1857.631)    (1500, 830)
  +15°   7162.170   138.417 / 198.055 / 149.805 / 50.166           (2188.292, 1712.982)    (1525.882, 826.593)

  SHEAVE 2 sits straight above the luff axis as drawn, so luffing moves it level at first: the run from it to the
  chute stays within 0.17° of level, and at the V rollers it comes down by at most 0.67 mm (V ROLLER 1) and
  0.36 mm (V ROLLER 2) at ±15° (0.30 / 0.16 at ±10°, 0.07 / 0.04 at ±5°): the rope stays on the rollers.

Checked before the file is written (``check``): every part is one valid solid; as drawn no part lies in another;
the rope touches the drum, both sheaves, both V rollers and the chute (gap 0) and is 10 mm and more from every
other part (10: the chute's stand, through the chute's wall; then the cradle stand 46, the A-frame 114); at seven
angles over the luff range the bodies that move against each other (base with stands, chute and blocks – A-frame
with its pins – each sheave – the drum – each roller) are never nearer than the bores' 0.5 mm (radius; everywhere
else 5 mm and more) and the rope laid anew still touches drum, sheaves and chute and is clear of everything else.
In the app (draft detail, the luff -15° .. +15°, drum, sheaves and rollers turning, the rope left out): the clash
check gives 0 rows.

Revision B: GUARD added, the parts placed in another order (under the root and in A-FRAME.ASM; two of the same
part keep theirs, so every part keeps its ID); the rope and everything it touches are where they were.

The files are small because the curves on the surfaces are left out (A: 292 KB). Needs OpenCascade (OCP), as the
other tools/make_test_*.py; it uses nothing else of the repository.
"""

import math
import os
import sys

import numpy as np
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism,
                             BRepPrimAPI_MakeRevol)
from OCP.GC import GC_MakeArcOfCircle
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType, STEPControl_Writer
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Compound
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

YELLOW, GREY, STEEL, CHROME = (0.976, 0.659, 0.0), (0.3, 0.3, 0.3), (0.55, 0.57, 0.6), (0.85, 0.86, 0.88)
ROPE_GREY, ORANGE = (0.13, 0.13, 0.14), (0.9, 0.35, 0.05)

# =====================================================================================================================
# the numbers (mm, degrees). Everything the rope does lies in the plane y = 0; a point there is (x, z).
# =====================================================================================================================

ROPE_R = 12.0                       # WIRE ROPE Ø 24
GROOVE_R = 13.0                     # the sheaves' groove (a circle arc in the section)
FLANGE = 28.0                       # the sheaves' flanges stand this far above the groove bottom
GROOVE_HALF = 70.0                  # the groove's arc reaches this far up either side of its bottom (degrees)
LEAN = 20.0                         # the A-frame as drawn: from the vertical, towards +X
LUFF = 15.0                         # the luff range either way the model is made for
HINGE = (1500.0, 730.0)             # the luff axis (x, z); along Y
LEG = 1200.0                        # hinge -> SHEAVE 1, along the legs
S2_UP = 100.0                       # SHEAVE 2: straight above the hinge as drawn, this far
DRUM = (450.0, 450.0)
DRUM_BARREL_R, DRUM_FLANGE_R, DRUM_HALF = 200.0, 300.0, 200.0
DRUM_START = 180.0                  # where the rope starts on the drum: this angle round it (from +X towards +Z)
S1_BOTTOM, S2_BOTTOM = 238.0, 168.0  # groove-bottom radius of SHEAVE 1 and SHEAVE 2
ROLLER_R, ROLLER_LEN, ROLLER_LOW = 60.0, 220.0, 40.0   # V ROLLER; its low end is ROLLER_LOW below the rope's touch
ROLLER_X = (2400.0, 2540.0)         # the two rollers stand one behind the other along the rope
V_ANGLE = 40.0                      # their axes from the horizontal
CHUTE_X = 2700.0                    # the chute's bend axis is straight below this point of the level run
CHUTE_BOTTOM = 588.0                # bend axis -> the trough's bottom
CHUTE_TROUGH_R = 20.0               # the trough's section: a round bottom of this radius
CHUTE_SECTOR = (-7.5, 57.5)         # the chute, in degrees from straight up towards +X
CHUTE_WRAP = 50.0                   # the rope leaves it after this much
FREE = 500.0                        # the rope's free end: straight on

DRUM_SEAT = DRUM_BARREL_R + ROPE_R
S1_SEAT, S2_SEAT = S1_BOTTOM + ROPE_R, S2_BOTTOM + ROPE_R
CHUTE_SEAT = CHUTE_BOTTOM + ROPE_R
Z_LINE = HINGE[1] + S2_UP - S2_SEAT                     # the level run through the V-cradle
CHUTE = (CHUTE_X, Z_LINE - CHUTE_SEAT)


def _v(a_deg):
    """(x, z) unit vector at a_deg from +X towards +Z."""
    a = math.radians(a_deg)
    return np.array([math.cos(a), math.sin(a)])


def _perp(u):
    """u turned a quarter turn from +X towards +Z."""
    return np.array([-u[1], u[0]])


def frame_point(v, u, luff=0.0):
    """A point of the A-frame (v: square to the legs towards the front, u: along the legs from the hinge) in the
    model's (x, z), with the frame luffed ``luff`` degrees further forward than drawn."""
    a = math.radians(LEAN + luff)
    return np.array([HINGE[0] + u * math.sin(a) + v * math.cos(a), HINGE[1] + u * math.cos(a) - v * math.sin(a)])


S1_LOCAL = (0.0, LEG)                                                   # (v, u) in the A-frame
S2_LOCAL = (-S2_UP * math.sin(math.radians(LEAN)), S2_UP * math.cos(math.radians(LEAN)))


def wheels(luff=0.0):
    """The four circles the rope bends round: (name, centre (x, z), radius to the rope's middle, side). Side +1:
    the rope goes round turning about +Y (from +Z towards +X: over the top towards +X), -1 about -Y."""
    return [("WINCH DRUM", np.array(DRUM), DRUM_SEAT, -1),
            ("SHEAVE 1", frame_point(*S1_LOCAL, luff), S1_SEAT, 1),
            ("SHEAVE 2", frame_point(*S2_LOCAL, luff), S2_SEAT, -1),
            ("CHUTE", np.array(CHUTE), CHUTE_SEAT, 1)]


def tangent(c1, r1, s1, c2, r2, s2):
    """The straight run from circle 1 to circle 2 that leaves and arrives without a kink: (point on 1, point on 2,
    direction). A rope going round a circle with side s at a point p goes along t with p = c + s r perp(t)."""
    d = np.asarray(c2, float) - np.asarray(c1, float)
    dist = float(np.linalg.norm(d))
    k = s1 * r1 - s2 * r2
    if dist <= abs(k) + 1e-9:
        raise ValueError("the circles lie in each other: no straight run between them")
    run = math.sqrt(dist * dist - k * k)
    t = (run * d - k * _perp(d)) / (dist * dist)
    return c1 + s1 * r1 * _perp(t), c2 + s2 * r2 * _perp(t), t


class Line:
    kind = "line"

    def __init__(self, start, end):
        self.start, self.end = np.asarray(start, float), np.asarray(end, float)
        self.length = float(np.linalg.norm(self.end - self.start))
        self.start_tangent = self.end_tangent = (self.end - self.start) / self.length

    def point(self, s):
        return self.start + self.start_tangent * s


class Arc:
    """On a circle (centre, radius) with side s from the point at angle a0, ``wrap`` degrees on."""
    kind = "arc"

    def __init__(self, name, centre, radius, side, a0, wrap):
        self.name, self.centre, self.radius, self.side = name, np.asarray(centre, float), float(radius), side
        self.a0, self.wrap = a0, wrap
        self.length = self.radius * math.radians(wrap)
        self.start, self.end = self.point(0.0), self.point(self.length)
        self.start_tangent, self.end_tangent = self.tangent(0.0), self.tangent(self.length)

    def angle(self, s):
        return self.a0 - self.side * math.degrees(s / self.radius)

    def point(self, s):
        return self.centre + self.radius * _v(self.angle(s))

    def tangent(self, s):
        return -self.side * _perp(_v(self.angle(s)))


def _angle_of(p, c):
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))


class Route:
    """The rope's middle with the A-frame luffed ``luff`` degrees: arcs on the four circles, straight runs between
    them, the free end. The start on the drum and the end of the chute's arc stay where they are drawn."""

    def __init__(self, luff=0.0):
        ws = wheels(luff)
        runs = [tangent(a[1], a[2], a[3], b[1], b[2], b[3]) for a, b in zip(ws[:-1], ws[1:])]
        self.segments, self.contacts = [], []
        angle_in = DRUM_START
        for i, (name, c, r, side) in enumerate(ws):
            if i < len(runs):
                angle_out = _angle_of(runs[i][0], c)
            else:
                angle_out = 90.0 - CHUTE_WRAP                       # the chute: a fixed point of its circle
            wrap = (side * (angle_in - angle_out)) % 360.0
            arc = Arc(name, c, r, side, angle_in, wrap)
            self.segments.append(arc)
            self.contacts.append(arc)
            if i < len(runs):
                self.segments.append(Line(runs[i][0], runs[i][1]))
                angle_in = _angle_of(runs[i][1], ws[i + 1][1])
        last = self.segments[-1]
        self.segments.append(Line(last.end, last.end + FREE * last.end_tangent))
        for a, b in zip(self.segments[:-1], self.segments[1:]):
            assert np.linalg.norm(a.end - b.start) < 1e-9 and np.linalg.norm(a.end_tangent - b.start_tangent) < 1e-9
        self.start, self.end = self.segments[0].start, self.segments[-1].end
        self.length = sum(s.length for s in self.segments)

    def points(self, step=1.0):
        out = [self.start]
        for seg in self.segments:
            k = max(int(math.ceil(seg.length / step)), 1)
            out += [seg.point(seg.length * i / k) for i in range(1, k + 1)]
        return np.array(out)


def roller_axis(k):
    """V ROLLER k (0, 1): (the point of its axis nearest the rope, the axis' direction, where the rope touches it),
    in the model's (x, y, z). Roller 0 rises towards +Y, roller 1 towards -Y."""
    sign = 1.0 if k == 0 else -1.0
    c, s = math.cos(math.radians(V_ANGLE)), math.sin(math.radians(V_ANGLE))
    reach = ROLLER_R + ROPE_R
    foot = np.array([ROLLER_X[k], sign * reach * s, Z_LINE - reach * c])
    touch = np.array([ROLLER_X[k], sign * ROPE_R * s, Z_LINE - ROPE_R * c])
    return foot, np.array([0.0, sign * c, s]), touch


SURFACE = {"WINCH DRUM": DRUM_BARREL_R, "SHEAVE 1": S1_BOTTOM, "SHEAVE 2": S2_BOTTOM, "CHUTE": CHUTE_BOTTOM}
UID = {"WINCH DRUM": "TEST.PATHS#1/WINCH DRUM#1", "SHEAVE 1": "TEST.PATHS#1/A-FRAME.ASM#1/SHEAVE 1#1",
       "SHEAVE 2": "TEST.PATHS#1/A-FRAME.ASM#1/SHEAVE 2#1", "CHUTE": "TEST.PATHS#1/CHUTE#1",
       "V ROLLER 1": "TEST.PATHS#1/V CRADLE.ASM#1/V ROLLER#1", "V ROLLER 2": "TEST.PATHS#1/V CRADLE.ASM#1/V ROLLER#2",
       "WIRE ROPE": "TEST.PATHS#1/WIRE ROPE#1", "A-FRAME.ASM": "TEST.PATHS#1/A-FRAME.ASM#1"}


def roller_gap(luff=0.0):
    """How far the rope's skin is from each V roller's with the A-frame luffed (0 as drawn; negative: into it)."""
    line = Route(luff).segments[5]                              # the run from SHEAVE 2 to the CHUTE
    p = np.array([line.start[0], 0.0, line.start[1]])
    t = np.array([line.start_tangent[0], 0.0, line.start_tangent[1]])
    out = []
    for k in (0, 1):
        foot, direction, _touch = roller_axis(k)
        n = np.cross(direction, t)
        out.append(abs(float((p - foot) @ n)) / float(np.linalg.norm(n)) - ROLLER_R - ROPE_R)
    return out


def centreline(luff=0.0, step=1.0):
    """The rope's middle as points (n, 3) in the model's coordinates, ``step`` mm apart or less."""
    p = Route(luff).points(step)
    return np.c_[p[:, 0], np.zeros(len(p)), p[:, 1]]


def numbers_at(luff=0.0):
    """Everything the tests need as a dict, in mm and degrees, with the A-frame luffed ``luff`` degrees (the rope
    laid anew over the moved sheaves; its start on the drum and the end of the chute's arc stay)."""
    def p3(p):
        return (round(float(p[0]), 4), 0.0, round(float(p[1]), 4))

    route = Route(luff)
    out = {
        "units": "mm, degrees", "rope_radius": ROPE_R, "rope_plane": "y = 0", "lean": LEAN + luff, "luff": luff,
        "luff_range": (-LUFF, LUFF),
        "luff_axis": {"point": (HINGE[0], 0.0, HINGE[1]), "direction": (0.0, 1.0, 0.0), "moves": UID["A-FRAME.ASM"],
                      "pin": "HINGE PIN"},
        "level_run_z": Z_LINE,
        "rope": {"uid": UID["WIRE ROPE"], "start": p3(route.start), "end": p3(route.end),
                 "length": round(route.length, 4), "free": FREE, "segments": []},
        "contacts": {}, "rollers": [],
    }
    for seg in route.segments:
        out["rope"]["segments"].append({"kind": seg.kind, "on": getattr(seg, "name", ""), "start": p3(seg.start),
                                        "end": p3(seg.end), "length": round(seg.length, 4)})
    in_frame = {"SHEAVE 1": S1_LOCAL, "SHEAVE 2": S2_LOCAL}
    for arc in route.contacts:
        out["contacts"][arc.name] = {
            "uid": UID[arc.name], "axis_point": p3(arc.centre), "axis_direction": (0.0, 1.0, 0.0),
            "surface_radius": SURFACE[arc.name], "seat_radius": arc.radius, "side": arc.side,
            "wrap": round(arc.wrap, 4), "tangent_in": p3(arc.start), "tangent_out": p3(arc.end),
            "turns": arc.name != "CHUTE"}
        if arc.name in in_frame:                # where it sits in A-FRAME.ASM (x: front, z: along the legs)
            out["contacts"][arc.name]["in_frame"] = (round(in_frame[arc.name][0], 4), 0.0,
                                                     round(in_frame[arc.name][1], 4))
    for k in (0, 1):
        foot, direction, touch = roller_axis(k)
        out["rollers"].append({"uid": UID[f"V ROLLER {k + 1}"], "axis_point": tuple(round(float(v), 4) for v in foot),
                               "axis_direction": tuple(round(float(v), 6) for v in direction),
                               "surface_radius": ROLLER_R, "seat_radius": ROLLER_R + ROPE_R,
                               "touch": tuple(round(float(v), 4) for v in touch),
                               "rope_middle": (ROLLER_X[k], 0.0, Z_LINE), "gap": round(roller_gap(luff)[k], 4)})
    return out


NUMBERS = numbers_at(0.0)
PARTS = ["BASE FRAME", "WINCH DRUM", "BEARING BLOCK", "BEARING BLOCK", "A-FRAME", "HINGE PIN", "HINGE PIN",
         "SHEAVE PIN 1", "SHEAVE 1", "SHEAVE PIN 2", "SHEAVE 2", "CRADLE STAND", "V ROLLER", "V ROLLER", "CHUTE",
         "CHUTE STAND", "WIRE ROPE"]                    # revision B: and GUARD
ASSEMBLIES = ["TEST.PATHS", "A-FRAME.ASM", "V CRADLE.ASM"]


# =====================================================================================================================
# shapes (OpenCascade)
# =====================================================================================================================

def T(x=0.0, y=0.0, z=0.0):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def RotY(deg, about=(0.0, 0.0, 0.0)):
    """A turn about +Y (from +Z towards +X) through the point ``about``."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    m = np.eye(4)
    m[:3, :3] = [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
    p = np.asarray(about, float)
    m[:3, 3] = p - m[:3, :3] @ p
    return m


def frame(origin, x, z):
    """Local -> model: local x along ``x``, local z along ``z`` (square to each other), y = z x x."""
    x, z = np.asarray(x, float), np.asarray(z, float)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, np.cross(z, x), z, origin
    return m


def _trsf(m):
    t = gp_Trsf()
    t.SetValues(*[float(m[i, j]) for i in range(3) for j in range(4)])
    return t


def xform(shape, m):
    return BRepBuilderAPI_Transform(shape, _trsf(m), True).Shape()


def _p(v):
    return gp_Pnt(float(v[0]), float(v[1]), float(v[2]))


def box(x0, y0, z0, x1, y1, z1):
    """A box from corner to corner."""
    return BRepPrimAPI_MakeBox(gp_Pnt(float(min(x0, x1)), float(min(y0, y1)), float(min(z0, z1))),
                               gp_Pnt(float(max(x0, x1)), float(max(y0, y1)), float(max(z0, z1)))).Shape()


def cyl(r, p0, p1):
    """A round bar from p0 to p1."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    h = float(np.linalg.norm(d))
    return BRepPrimAPI_MakeCylinder(gp_Ax2(_p(p0), gp_Dir(*[float(v) for v in d / h])), float(r), h).Shape()


def fuse(first, *rest):
    out = first
    for s in rest:
        op = BRepAlgoAPI_Fuse(out, s)
        if not op.IsDone():
            raise RuntimeError("fuse failed")
        op.SimplifyResult()
        out = op.Shape()
    return out


def cut(a, *tools):
    for t in tools:
        op = BRepAlgoAPI_Cut(a, t)
        if not op.IsDone():
            raise RuntimeError("cut failed")
        a = op.Shape()
    return a


def compound(shapes):
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for s in shapes:
        b.Add(c, s)
    return c


def volume(shape):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()


def solids(shape):
    n, ex = 0, TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        n += 1
        ex.Next()
    return n


def gap(a, b):
    return float(BRepExtrema_DistShapeShape(a, b).Value())


def _closed_wire(points):
    """A closed wire through 3D points; an item ("arc", through, end) is a circle arc from the point before."""
    w = BRepBuilderAPI_MakeWire()
    first = cur = np.asarray(points[0], float)
    for it in list(points[1:]) + [first]:
        if isinstance(it, tuple) and len(it) == 3 and isinstance(it[0], str):
            w.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(_p(cur), _p(it[1]), _p(it[2])).Value()).Edge())
            cur = np.asarray(it[2], float)
        else:
            it = np.asarray(it, float)
            if np.linalg.norm(it - cur) > 1e-9:
                w.Add(BRepBuilderAPI_MakeEdge(_p(cur), _p(it)).Edge())
            cur = it
    return w.Wire()


def revolve_y(profile, centre=(0.0, 0.0, 0.0), start=(1.0, 0.0, 0.0), angle=360.0):
    """The solid a closed (r, y) profile sweeps turning about +Y through ``centre``: r is measured along ``start``
    (square to Y) at first, then ``angle`` degrees on (from +Z towards +X). Arcs as in ``_closed_wire``."""
    centre, start = np.asarray(centre, float), np.asarray(start, float)

    def at(q):
        return centre + q[0] * start + np.array([0.0, q[1], 0.0])

    pts = [("arc", at(q[1]), at(q[2])) if isinstance(q[0], str) else at(q) for q in profile]
    face = BRepBuilderAPI_MakeFace(_closed_wire(pts), True).Face()
    return BRepPrimAPI_MakeRevol(face, gp_Ax1(_p(centre), gp_Dir(0, 1, 0)), math.radians(angle)).Shape()


def prism(points, push):
    """A closed flat polygon (3D points) pushed along the vector ``push``."""
    poly = BRepBuilderAPI_MakePolygon()
    for q in points:
        poly.Add(_p(q))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(float(push[0]), float(push[1]), float(push[2]))).Shape()


def rope_solid(route, r=ROPE_R):
    """One round bar along the whole route (a pipe swept along its lines and arcs): one solid."""
    def p(q):
        return gp_Pnt(float(q[0]), 0.0, float(q[1]))

    w = BRepBuilderAPI_MakeWire()
    for seg in route.segments:
        if seg.kind == "line":
            w.Add(BRepBuilderAPI_MakeEdge(p(seg.start), p(seg.end)).Edge())
        else:
            arc = GC_MakeArcOfCircle(p(seg.start), p(seg.point(seg.length / 2)), p(seg.end)).Value()
            w.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    t = route.segments[0].start_tangent
    circle = gp_Circ(gp_Ax2(p(route.start), gp_Dir(float(t[0]), 0.0, float(t[1]))), float(r))
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire(), True).Face()
    return BRepOffsetAPI_MakePipe(w.Wire(), face).Shape()


def sheave(bottom, bore, hub_r, hub_half=35.0, web_half=10.0, rim_half=28.0):
    """A sheave about +Y through its origin, its groove in the plane y = 0: a round groove bottom of radius
    GROOVE_R (reaching GROOVE_HALF degrees up either side), straight flanks on from there, flanges FLANGE above
    the groove's bottom."""
    b = math.radians(GROOVE_HALF)
    rc, rf, ri = bottom + GROOVE_R, bottom + FLANGE, bottom - 20.0
    a = (rc - GROOVE_R * math.cos(b), GROOVE_R * math.sin(b))           # where the round bottom ends
    tip = a[1] + (rf - a[0]) / math.tan(b)                              # the flank goes on along the arc's direction
    assert tip < rim_half - 4.0
    return revolve_y([(bore, -hub_half), (hub_r, -hub_half), (hub_r, -web_half), (ri, -web_half), (ri, -rim_half),
                      (rf, -rim_half), (rf, -tip), (a[0], -a[1]), ("arc", (bottom, 0.0), a), (rf, tip),
                      (rf, rim_half), (ri, rim_half), (ri, web_half), (hub_r, web_half), (hub_r, hub_half),
                      (bore, hub_half)])


# =====================================================================================================================
# the scene tree and the STEP writer
# =====================================================================================================================

class Part:
    def __init__(self, name, shape, color):
        self.name, self.shape, self.color = name, shape, color


class Asm:
    def __init__(self, name):
        self.name, self.children = name, []

    def add(self, node, matrix=None):
        self.children.append((node, np.eye(4) if matrix is None else np.asarray(matrix, float)))
        return node


def placed(root, moves=None):
    """Every part once per place: (name, names of the assemblies it sits in, shape in the model's coordinates).
    ``moves``: assembly name -> a matrix that replaces the place it was given (a pose)."""
    out = []

    def walk(node, world, path):
        if isinstance(node, Part):
            out.append((node.name, path, xform(node.shape, world)))
            return
        for child, m in node.children:
            if moves and child.name in moves:
                m = moves[child.name]
            walk(child, world @ m, path + [node.name])
    walk(root, np.eye(4), [])
    return out


def count_parts(root):
    return len(placed(root))


def write_step(root, path):
    try:                                                # the writer prints statistics for every file
        from OCP.Message import Message, Message_Gravity
        for printer in Message.DefaultMessenger_s().Printers():
            printer.SetTraceLevel(Message_Gravity.Message_Fail)
    except Exception:                                   # an older OCP
        pass
    STEPControl_Writer()                                # (makes the setting below known)
    if not Interface_Static.SetIVal_s("write.surfacecurve.mode", 0):   # no curves-on-surface: a smaller file
        raise RuntimeError("the STEP writer does not know write.surfacecurve.mode")
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    labels = {}

    def label(node):
        if id(node) in labels:
            return labels[id(node)]
        if isinstance(node, Part):
            if solids(node.shape) != 1:                 # several solids: the app's importer reads no colour
                raise ValueError(f"part {node.name} is {solids(node.shape)} solids, not 1")
            lab = st.AddShape(node.shape, False)
            r, g, b = node.color
            ct.SetColor(lab, Quantity_Color(r, g, b, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        else:
            kids = [(label(child), m) for child, m in node.children]
            lab = st.NewShape()
            for kid, m in kids:
                st.AddComponent(lab, kid, TopLoc_Location(_trsf(m)))
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(node.name))
        labels[id(node)] = lab
        return lab

    label(root)
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"writing {path} failed")


# =====================================================================================================================
# TEST.PATHS
# =====================================================================================================================

BASE_END = 3150.0                   # the base frame: x 0 .. BASE_END
RAIL_Y = (280.0, 380.0)             # the two rails: this far either side of the middle
LEG_Y = (230.0, 330.0)              # the A-frame's legs
LEG_HALF = 60.0                     # … their half thickness square to the frame
HINGE_PIN_R, S1_PIN_R, S2_PIN_R, DRUM_SHAFT_R, STUB_R = 25.0, 25.0, 20.0, 40.0, 15.0
BORE = 0.5                          # a bore something turns in is this much wider (radius) than its pin
BEAM_TOP = ((-160.0, -60.0), (800.0, 900.0))       # the top cross beam (v, u): behind the legs
BEAM_LOW = ((60.0, 160.0), (310.0, 410.0))         # the lower cross beam: in front of the legs
CHEEK_Y = (40.0, 60.0)              # the two plates that carry SHEAVE 2 from the lower cross beam
BLOCK_Y = (250.0, 330.0)            # the drum's bearing blocks
TOWER_Y = (195.0, 365.0)            # the hinge towers; their lugs are 30 thick, 5 from the legs
CHUTE_STAND_AT = (-3.0, 3.5, 10.0, 16.5, 23.0, 29.5, 36.0)     # where the stand's top touches the chute
GUARD = (40.0, -250.0, 100.0, 60.0, 250.0, 820.0)              # revision B: a plate behind the drum


def a_frame_matrix(luff=0.0):
    """A-FRAME.ASM's place: its origin on the luff axis, its z along the legs, its x square to them (front)."""
    return T(HINGE[0], 0.0, HINGE[1]) @ RotY(LEAN + luff)


def base_frame():
    hx, hz = HINGE
    dx = DRUM[0]
    parts = [box(0, s * RAIL_Y[0], 0, BASE_END, s * RAIL_Y[1], 100) for s in (1, -1)]
    for x0, x1 in ((0, 100), (dx - 100, dx + 100), (950, 1050), (hx - 100, hx + 100), (2300, BASE_END)):
        parts.append(box(x0, -RAIL_Y[1], 0, x1, RAIL_Y[1], 100))
    bores = []
    for s in (1, -1):                                   # a tower either side, a fork of two lugs on each
        parts.append(box(hx - 80, s * TOWER_Y[0], 100, hx + 80, s * TOWER_Y[1], hz - 110))
        parts.append(box(hx - 60, s * TOWER_Y[0], hz - 110, hx + 60, s * (TOWER_Y[0] + 30), hz + 60))
        parts.append(box(hx - 60, s * (TOWER_Y[1] - 30), hz - 110, hx + 60, s * TOWER_Y[1], hz + 60))
        bores.append(cyl(HINGE_PIN_R + BORE, (hx, s * (TOWER_Y[0] - 10), hz), (hx, s * (TOWER_Y[1] + 10), hz)))
    return cut(fuse(*parts), *bores)


def bearing_block():
    """Built round the drum's axis (its origin on it): a pedestal with a bore."""
    down = DRUM[1] - 100.0
    return cut(box(-80, -40, -down, 80, 40, 90), cyl(DRUM_SHAFT_R + BORE, (0, -50, 0), (0, 50, 0)))


def winch_drum():
    r, f, h = DRUM_BARREL_R, DRUM_FLANGE_R, DRUM_HALF
    return revolve_y([(0, -h - 140), (DRUM_SHAFT_R, -h - 140), (DRUM_SHAFT_R, -h - 20), (f, -h - 20), (f, -h),
                      (r, -h), (r, h), (f, h), (f, h + 20), (DRUM_SHAFT_R, h + 20), (DRUM_SHAFT_R, h + 140),
                      (0, h + 140)])


def a_frame():
    """In A-FRAME.ASM's coordinates: x = v (front), z = u (along the legs), the luff axis is its Y axis."""
    (tv0, tv1), (tu0, tu1) = BEAM_TOP
    (lv0, lv1), (lu0, lu1) = BEAM_LOW
    parts = [box(-LEG_HALF, s * LEG_Y[0], -70, LEG_HALF, s * LEG_Y[1], LEG + 80) for s in (1, -1)]
    parts.append(box(tv0, -LEG_Y[1], tu0, tv1, LEG_Y[1], tu1))
    parts.append(box(lv0, -LEG_Y[1], lu0, lv1, LEG_Y[1], lu1))
    # the cheeks: from the middle of the lower cross beam to 45 past SHEAVE 2's pin
    sv, su = S2_LOCAL
    bv, bu = 0.5 * (lv0 + lv1), 0.5 * (lu0 + lu1)
    along = np.array([sv - bv, su - bu])
    reach = float(np.linalg.norm(along))
    along /= reach
    m = frame((bv, 0.0, bu), (along[0], 0.0, along[1]), np.cross((along[0], 0.0, along[1]), (0.0, 1.0, 0.0)))
    for s in (1, -1):
        parts.append(xform(box(0, s * CHEEK_Y[0], -40, reach + 45, s * CHEEK_Y[1], 40), m))
    bores = [cyl(HINGE_PIN_R, (0, -400, 0), (0, 400, 0)), cyl(S1_PIN_R, (0, -400, LEG), (0, 400, LEG)),
             cyl(S2_PIN_R, (sv, -100, su), (sv, 100, su))]
    return cut(fuse(*parts), *bores)


def v_roller():
    """About its local z; the origin is the point of its axis nearest the rope."""
    lo, hi = -ROLLER_LOW, ROLLER_LEN - ROLLER_LOW
    return fuse(cyl(ROLLER_R, (0, 0, lo), (0, 0, hi)), cyl(STUB_R, (0, 0, lo - 25), (0, 0, lo)),
                cyl(STUB_R, (0, 0, hi), (0, 0, hi + 25)))


def roller_matrix(k):
    foot, direction, _touch = roller_axis(k)
    return frame(foot, (1.0, 0.0, 0.0), direction)


def cradle_stand():
    """A plate on the base and, for each roller, a yoke (two cheeks with a bore, a bar under the roller) on a
    web down to the plate."""
    lo, hi = -ROLLER_LOW, ROLLER_LEN - ROLLER_LOW
    outline = [(lo - 20, 35), (lo - 5, 35), (lo - 5, -75), (hi + 5, -75), (hi + 5, 35), (hi + 20, 35),
               (hi + 20, -100)]                         # (along the roller, square to it towards the rope)
    parts = [box(ROLLER_X[0] - 60, -280, 100, ROLLER_X[1] + 60, 280, 130)]
    bores = []
    for k in (0, 1):
        foot, direction, _touch = roller_axis(k)
        normal = np.array([0.0, -direction[2] * np.sign(direction[1]), abs(direction[1])])
        pts = [foot + t * direction + n * normal for t, n in outline]
        pts.append(np.array([0.0, pts[-1][1], 100.0]))
        low = foot + (lo - 20) * direction - 100 * normal
        pts += [np.array([0.0, low[1], 100.0]), low]
        parts.append(prism([(ROLLER_X[k] - 40, q[1], q[2]) for q in pts], (80.0, 0.0, 0.0)))
        bores.append(cyl(STUB_R + BORE, foot + (lo - 30) * direction, foot + (hi + 30) * direction))
    return cut(fuse(*parts), *bores)


def _chute_start():
    a = math.radians(CHUTE_SECTOR[0])
    return (math.sin(a), 0.0, math.cos(a))


def chute():
    """A U-shaped trough bent round the bend axis: a round bottom (radius CHUTE_TROUGH_R), straight walls, 10 thick."""
    b, t = CHUTE_BOTTOM, CHUTE_TROUGH_R
    c = b + t
    profile = [(c, -t), ("arc", (b, 0.0), (c, t)), (c + 32, t), (c + 32, t + 10), (c, t + 10),
               ("arc", (b - 10, 0.0), (c, -t - 10)), (c + 32, -t - 10), (c + 32, -t)]
    return revolve_y(profile, (CHUTE[0], 0.0, CHUTE[1]), _chute_start(), CHUTE_SECTOR[1] - CHUTE_SECTOR[0])


def chute_stand():
    """A pedestal on a foot plate. Its top is a row of flats under the chute; their corners touch the chute's
    underside in the plane y = 0 (flats, not a round saddle: the stand has no round face on the bend axis)."""
    under = CHUTE_BOTTOM - 10.0
    pts = [(CHUTE[0] + under * math.sin(math.radians(a)), -25.0, CHUTE[1] + under * math.cos(math.radians(a)))
           for a in CHUTE_STAND_AT]
    pts = [(pts[0][0], -25.0, 100.0)] + pts + [(pts[-1][0], -25.0, 100.0)]
    return fuse(prism(pts, (0.0, 50.0, 0.0)), box(pts[0][0] - 20, -120, 100, pts[-1][0] + 20, 120, 120))


def model(revision="A"):
    root = Asm("TEST.PATHS")
    top = []

    top.append((Part("BASE FRAME", base_frame(), GREY), None))
    top.append((Part("WINCH DRUM", winch_drum(), STEEL), T(DRUM[0], 0.0, DRUM[1])))
    block = Part("BEARING BLOCK", bearing_block(), GREY)
    y = 0.5 * (BLOCK_Y[0] + BLOCK_Y[1])
    top.append((block, T(DRUM[0], y, DRUM[1])))
    top.append((block, T(DRUM[0], -y, DRUM[1])))

    pin = Part("HINGE PIN", cyl(HINGE_PIN_R, (0, -95, 0), (0, 95, 0)), CHROME)
    y = 0.5 * (LEG_Y[0] + LEG_Y[1])
    s1, s2 = T(S1_LOCAL[0], 0.0, S1_LOCAL[1]), T(S2_LOCAL[0], 0.0, S2_LOCAL[1])
    inside = [(Part("A-FRAME", a_frame(), YELLOW), None), (pin, T(0.0, y, 0.0)), (pin, T(0.0, -y, 0.0)),
              (Part("SHEAVE PIN 1", cyl(S1_PIN_R, (0, -LEG_Y[1] - 10, 0), (0, LEG_Y[1] + 10, 0)), CHROME), s1),
              (Part("SHEAVE 1", sheave(S1_BOTTOM, S1_PIN_R + BORE, 70.0), STEEL), s1),
              (Part("SHEAVE PIN 2", cyl(S2_PIN_R, (0, -CHEEK_Y[1] - 10, 0), (0, CHEEK_Y[1] + 10, 0)), CHROME), s2),
              (Part("SHEAVE 2", sheave(S2_BOTTOM, S2_PIN_R + BORE, 55.0), STEEL), s2)]
    if revision == "B":
        inside = [inside[i] for i in (6, 5, 4, 3, 1, 2, 0)]
    frame_asm = Asm("A-FRAME.ASM")
    for node, m in inside:
        frame_asm.add(node, m)
    top.append((frame_asm, a_frame_matrix()))

    cradle = Asm("V CRADLE.ASM")
    cradle.add(Part("CRADLE STAND", cradle_stand(), GREY))
    roller = Part("V ROLLER", v_roller(), STEEL)
    cradle.add(roller, roller_matrix(0))
    cradle.add(roller, roller_matrix(1))
    top.append((cradle, None))

    top.append((Part("CHUTE", chute(), STEEL), None))
    top.append((Part("CHUTE STAND", chute_stand(), GREY), None))
    top.append((Part("WIRE ROPE", rope_solid(Route()), ROPE_GREY), None))
    if revision == "B":
        # one more part, and the parts placed in another order (two of the same keep theirs: the same IDs)
        top.append((Part("GUARD", box(*GUARD), ORANGE), None))
        top = [top[i] for i in (9, 8, 6, 5, 0, 7, 2, 3, 4, 1)]
    for node, m in top:
        root.add(node, m)
    return root


# ---------------------------------------------------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------------------------------------------------

ROPE_TOUCHES = ("WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "V ROLLER", "CHUTE")


def body_of(name, path):
    """The rigid body a part belongs to when the A-frame luffs and everything round turns."""
    if name in ("WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "WIRE ROPE"):
        return name
    if name == "V ROLLER":
        return None                                     # each roller is a body of its own (see check)
    return "A-FRAME" if "A-FRAME.ASM" in path else "BASE"


def check(root, say=print):
    parts = placed(root)
    for name, _path, shape in parts:
        assert solids(shape) == 1 and BRepCheck_Analyzer(shape).IsValid() and volume(shape) > 0, name
    # as drawn: no part lies in another; the rope touches what it lies on and is clear of everything else
    rope = next(shape for name, _p, shape in parts if name == "WIRE ROPE")
    near = (math.inf, "")
    for i, (na, _pa, sa) in enumerate(parts):
        for nb, _pb, sb in parts[i + 1:]:
            d = gap(sa, sb)
            if d < 1e-6:
                v = volume(BRepAlgoAPI_Common(sa, sb).Shape())
                assert v < 1e-3, (na, "lies inside", nb, v)
            if "WIRE ROPE" in (na, nb):
                other = nb if na == "WIRE ROPE" else na
                if other in ROPE_TOUCHES:
                    assert d < 1e-4, ("the rope does not touch", other, d)
                else:
                    assert d > 8.0, ("the rope is too near", other, d)
                    near = min(near, (d, other))
    say(f"  rope: touches {', '.join(ROPE_TOUCHES)}; nearest other part {near[0]:.1f} ({near[1]})")
    route = Route()
    assert volume(rope) > 0 and abs(volume(rope) / (math.pi * ROPE_R ** 2 * route.length) - 1.0) < 1e-6

    # the luff range: the bodies never touch (BORE in the bores), the rope's path stays possible and clear
    least = (math.inf, "")
    rope_near = (math.inf, "")
    for luff in np.linspace(-LUFF, LUFF, 7):
        now = placed(root, {"A-FRAME.ASM": a_frame_matrix(luff)})
        bodies, rollers = {}, 0
        for name, path, shape in now:
            key = body_of(name, path)
            if key is None:
                rollers += 1
                key = f"V ROLLER {rollers}"
            bodies.setdefault(key, []).append(shape)
        bodies = {k: compound(v) for k, v in bodies.items()}
        r = Route(luff)
        for arc in r.contacts:
            assert 20.0 < arc.wrap < 300.0, (luff, arc.name, arc.wrap)
        for seg in r.segments:
            assert seg.length > 50.0, (luff, seg.kind, seg.length)
        del bodies["WIRE ROPE"]                         # the rope as drawn; the app lays it anew:
        rope = rope_solid(r)
        for name, _path, shape in now:
            if name in ("WIRE ROPE", "V ROLLER"):       # (the level run moves a little on the rollers: roller_gap)
                continue
            d = gap(rope, shape)
            if name in ROPE_TOUCHES:
                assert d < 1e-4, (luff, "the rope does not touch", name, d)
            else:
                assert d > 8.0, (luff, "the rope is too near", name, d)
                rope_near = min(rope_near, (d, f"{name} at {luff:+.0f}°"))
        assert min(roller_gap(luff)) > -1.0 and max(roller_gap(luff)) < 1e-9, (luff, roller_gap(luff))
        keys = sorted(bodies)
        for i, ka in enumerate(keys):
            for kb in keys[i + 1:]:
                d = gap(bodies[ka], bodies[kb])
                assert d > 0.45, ("bodies touch", ka, kb, d, "luff", luff)
                least = min(least, (d, f"{ka} - {kb} at {luff:+.0f}°"))
    say(f"  luff -{LUFF:.0f}° .. +{LUFF:.0f}°: least gap between bodies {least[0]:.2f} mm ({least[1]}); the rope's "
        f"nearest other part {rope_near[0]:.1f} ({rope_near[1]})")


def numbers(say=print):
    for luff in (0.0, -LUFF, LUFF):
        r = Route(luff)
        say(f"luff {luff:+.0f}°: length {r.length:.3f}, start {np.round(r.start, 3)}, end {np.round(r.end, 3)}")
        for seg in r.segments:
            if seg.kind == "arc":
                say(f"  {seg.name:10s} centre {np.round(seg.centre, 3)} seat {seg.radius:.0f} side {seg.side:+d} "
                    f"in {np.round(seg.start, 3)} out {np.round(seg.end, 3)} wrap {seg.wrap:.3f}° "
                    f"arc {seg.length:.3f}")
            else:
                a = math.degrees(math.atan2(seg.start_tangent[1], seg.start_tangent[0]))
                say(f"  straight   {np.round(seg.start, 3)} -> {np.round(seg.end, 3)} length {seg.length:.3f} "
                    f"direction {a:.3f}°")
        say(f"  rope skin to the V rollers: {roller_gap(luff)[0]:+.3f}, {roller_gap(luff)[1]:+.3f}")
    for k in (0, 1):
        foot, direction, touch = roller_axis(k)
        say(f"V ROLLER {k + 1}: axis point {np.round(foot, 3)} direction {np.round(direction, 6)} touch "
            f"{np.round(touch, 3)}")
    say(f"SHEAVE 2 in the A-frame (v, u): {np.round(S2_LOCAL, 3)}; level run z {Z_LINE}; chute axis {CHUTE}")


def main(argv):
    if len(argv) < 2 or argv[1] == "numbers":
        numbers()
        return 0
    revision = argv[2] if len(argv) > 2 else "A"
    if revision not in ("A", "B"):
        raise SystemExit("usage: make_test_paths.py out.step [A|B]   or   make_test_paths.py numbers")
    root = model(revision)
    check(root)
    write_step(root, argv[1])
    print(f"written: {count_parts(root)} parts, {os.path.getsize(argv[1]) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
