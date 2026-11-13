"""Write the test model for tensioner tracks as a STEP assembly (task 0079; generic, invented).

    python tools/make_test_tracks.py out.step     TEST.TRACKS   (tests/data/test_tracks.step, a copy in
                                                  fresing_render/data/)
    python tools/make_test_tracks.py numbers      prints the numbers below, worked out

Two small machines side by side: a cable tensioner (two caterpillar tracks of links and rubber pads that squeeze a
cable between them) and a belt of separate links round three wheels of different size. All sizes in mm, angles in
degrees, Z up. Every part is one solid. The same numbers are in the code for tests and the app's set-up: ``NUMBERS``
(a dict), ``track_pins(which)``, ``belt_pins()``, ``PARTS``, ``ASSEMBLIES``, ``UID``.

======================================================================================================================
TEST.TRACKS                      171 parts (belt N = 58), 17 different shapes, 4 sub-assemblies
======================================================================================================================
1. The tensioner. The CABLE runs along +X through (0, 0, 1000). All chain and wheel axes are along +Y; each track's
   loop lies in the planes y = const, symmetric about y = 0. Below, a point "(x, z)" lies in the plane y = 0.
  Chain: pitch p = 100; sprockets 10 teeth, pitch-line radius R = p / (2 sin 18°) = 161.8034; sprocket centres at
  x = -300 (DRIVE SPROCKET) and x = +300 (IDLER SPROCKET); the gripping run (next to the cable) is 6 links long.
  Pins of a track (22, all exactly p apart, as ``demo_model.machines.track_pins``): from the drive sprocket's tangent
  point on the gripping run 6 pins along the gripping run (x -300, -200, … 200), 5 round the idler at tooth steps of
  36° (from the gripping run's side), 6 back along the other run (x 300, 200, … -200), 5 round the drive sprocket.
  Link k hinges on pins k and k+1 (k = 0..21, pin 22 = pin 0); in the CAD pose every sprocket has its pins in its
  notches (at 18° + k 36° from +X in the x-z plane).
  BASE FRAME               deck plate x -820..820, y -200..200, z 0..40; two side plates (y ±90..±110, x -350..350,
                           z 40..880) with holes for the bottom track's shafts; for each CABLE ROLLER two posts
                           (x ±700 ±25, y ±55..±75, z 40..945) joined by a pin Ø24 (y -75..75) through its bore:
                           one solid
  CABLE                    a round bar Ø60 from (-800, 0, 1000) to (800, 0, 1000)
  CABLE ROLLER (2 x)       under the cable at x = -700 and +700: cylinder r 50, y -50..50, axis +Y, centre z 920
                           (its top touches the cable), bore Ø24 (on the BASE FRAME's pin)
  BOTTOM TRACK.ASM         fixed. Gripping run = its TOP run: pin line z = 910, sprocket centres z = 748.1966
    DRIVE SPROCKET         at (-300, 748.1966); a disc r R + 10 = 171.8034, y -10..10, a round notch r 16 (along Y)
                           at each of the 10 pin places on the pitch circle; hub r 40, y -40..40; bore r 20
    IDLER SPROCKET         at (300, 748.1966); the same shape (made twice: the STEP writer gives one shape one name)
    SPROCKET SHAFT (2 x)   r 20, y -110..110, through each sprocket (into the BASE FRAME's side plates)
    SUPPORT ROLLER (2 x)   inside the loop under the gripping run at x = -100 and +100, centre z 850: cylinder r 40,
                           y -45..45, bore r 12. Its top (z 890) touches the links' inner edge (910 - 20)
    ROLLER SHAFT (2 x)     r 12, y -110..110, through each support roller
    TRACK CHAIN LINK (22 x) two shapes, one name: inner links (even k) and outer links (odd k). In a link's own
                           frame: origin the middle of its two pins, x along pin k -> pin k+1 (hinges at x = ±50),
                           y across the chain (= the loop normal: +Y for the bottom track, -Y for the top one),
                           z outward (away from the loop's inside).
                           inner: two side plates (y 25..33 and -33..-25), each a stadium (x -50..50, z -20..20 with
                             round ends r 20 about the hinges) with holes r 8.5 at the hinges, and two bushes
                             (tubes r 14 / 8.5, y -25..25) at the hinges
                           outer: two side plates (y 35..43 and -43..-35, stadium, no holes) and two pins (r 8,
                             y -43..43) at the hinges.  Round axes of a link: its two hinges, 100 apart, along Y.
    TRACK PAD (22 x)       a rubber block on a link's outer side, in the link's frame: x -45..45, y -60..60,
                           z 20..60 (10 mm gaps between pads on the runs); pads on the gripping run have their outer
                           faces at z = 970: they touch the cable. Pad k sits on link k.
  TOP CARRIAGE.ASM         (tests make a +Z slide joint "lift" on it)
    TOP TRACK FRAME        two side plates (y ±90..±110, x -350..350, z 1110..1530) with holes for the top track's
                           shafts, joined by a top beam (x -350..350, y -110..110, z 1490..1530) above the track
    TOP TRACK.ASM          the bottom track mirrored about the plane z = 1000 (placed by proper turns, no mirror
                           transform): gripping run = its BOTTOM run, pin line z = 1090, sprocket centres
                           z = 1251.8034, support rollers centre z = 1150 at x = ±100. The same part names; its pins
                           start at the drive sprocket's tangent point on the gripping run (-300, 1090) and run +X
                           along it, like the bottom track's; its pads on the gripping run have their outer faces at
                           z = 1030 (touch the cable)

  Sweeps: a chain sweeps 20 in from its pin line (link plates) and 60 out (pads), |y| <= 60 (pads; links 43):
  bottom x -521.8..521.8, z 526.4..970; top z 1030..1473.6. The BASE FRAME is 30 from the bottom sweep (across Y,
  from its side plates), 153 from the top sweep and from the TOP CARRIAGE.ASM; the TOP TRACK FRAME 16.4 from its
  sweep (the top beam). Inside a sweep only what the chain runs on: sprockets, support rollers, shafts. Measured in
  the CAD pose: links 2.0 from the sprockets (the bushes in the notches), pads 2.1; a pad 0.6 from its neighbour
  links' round ends, 10 from the next pad; neighbour links 0.5 apart (pin in bush, plates 2 apart across Y); pads
  off the gripping run 4.5 from the cable at least. Belt links 2.0 from pulleys A and B, 1.8 from C.
  When the cable moves +X, the pads on each gripping run move with it: +X.

2. The belt drive (a plain belt of separate links round three wheels of different size; wheel axes along +X; the
   loop lies in the plane x = 1500; below, a point "(y, z)" lies in that plane)
  BELT DRIVE.ASM
    BELT FRAME             a plate behind the pulleys (x 1430..1450, y -200..850, z 0..900) with a stub shaft r 10
                           from it into each pulley's bore (to x 1525): one solid
    BELT PULLEY A          centre (0, 400), pitch-line radius (where the hinges lie) 120: cylinder r 114,
                           x 1475..1525, bore r 10
    BELT PULLEY B          centre (700, 400), pitch radius 80: cylinder r 74
    BELT PULLEY C          centre (350, zC), pitch radius 50: cylinder r 44; zC = 808.8326 so the belt closes
    BELT LINK (N x)        pitch pb = 40; N = 58. In its frame (origin the middle of its two hinges, x along the
                           chord, y = the wheel axis +X, z outward): a plate x -16..16, y -30..30, z 2..8; a neck
                           x -20..20, y -30..30, z 0..2 (joins the plate to the knuckles); two knuckles r 4 along y
                           (-30..30) at x = ±20: its round axes are its two hinges, 40 apart. Neighbour links' knuckles
                           lie in each other (the shared hinge).
  The loop: outer tangents A -> B -> C -> A with the arcs (all wheels inside; anticlockwise about +X: along the bottom
  towards +Y). Hinge pins by a CHORD WALK: pin 0 is where the belt leaves A towards B (the tangent point); each next
  pin is the point further along the loop exactly pb away in a straight line. zC is solved (bisection to 1e-9 mm)
  so that after N steps the walk is back on pin 0 (closure 3e-11 mm); N = round(loop length at zC = 800 / pb).
  Loop length 2324.9513 (tangents 698.856, 537.349, 533.614; arcs on A 295.972, B 182.193, C 76.967); pin 0 at
  (6.8571, 280.1961); pins on the wheels' pitch circles: A 8, B 4, C 2 (the others on the tangents).

Colours: BASE FRAME, TOP TRACK FRAME, BELT FRAME grey (0.3, 0.3, 0.3); sprockets, rollers, shafts, pulleys steel
(0.55, 0.57, 0.6); chain links (0.35, 0.36, 0.38); TRACK PAD dark rubber (0.07, 0.07, 0.075); CABLE black
(0.05, 0.05, 0.05); CABLE ROLLER yellow (0.976, 0.659, 0); BELT LINK orange (0.9, 0.35, 0.05).

Checked before the file is written (``check``): every part is one valid solid; no two parts overlap except
neighbour BELT LINKs at their shared hinge (the knuckles); these pairs touch (distance 0, no volume in common): the
gripping-run pads and the CABLE, the CABLE ROLLERs and the CABLE, each support roller and the two links over it,
every shaft and its wheel(s) and frame, every pad and its own link, each pulley and the BELT FRAME's stub; the
BASE FRAME is 5 mm and more from both chains' sweeps and from every part of the TOP CARRIAGE.ASM, the TOP TRACK FRAME
5 mm and more from its chain's sweep, the BELT FRAME from the belt's.

Writing the file takes about 6 s (the check 5 s); 371 KB; the importer reads it in 1.8 s (Normal: 12,796
triangles in the 17 meshes).

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
CHAIN, RUBBER, BLACK, ORANGE = (0.35, 0.36, 0.38), (0.07, 0.07, 0.075), (0.05, 0.05, 0.05), (0.9, 0.35, 0.05)

# =====================================================================================================================
# the numbers (mm)
# =====================================================================================================================

# --- the tensioner ---------------------------------------------------------------------------------------------------
PITCH = 100.0
TEETH = 10
R = PITCH / (2.0 * math.sin(math.pi / TEETH))       # 161.8034: the sprockets' pitch-line radius
RUN_LINKS = 6                                       # links on the gripping run
A_HALF = RUN_LINKS * PITCH / 2.0                    # sprocket centres at x = -300 and +300
CABLE_Z, CABLE_R, CABLE_X = 1000.0, 30.0, (-800.0, 800.0)
LINK_HALF_H = 20.0                                  # link plates reach 20 in and out from the pin line
PAD_Z = (20.0, 60.0)                                # a pad in its link's frame: z 20..60
PAD_HALF_X, PAD_HALF_Y = 45.0, 60.0
GRIP_Z = {"bottom": CABLE_Z - CABLE_R - PAD_Z[1] + 0.0, "top": CABLE_Z + CABLE_R + PAD_Z[1]}   # pin lines 910 / 1090
SPROCKET_Z = {"bottom": GRIP_Z["bottom"] - R, "top": GRIP_Z["top"] + R}
ROLLER_X, ROLLER_R, ROLLER_HALF, ROLLER_BORE = (-100.0, 100.0), 40.0, 45.0, 12.0
ROLLER_Z = {"bottom": GRIP_Z["bottom"] - LINK_HALF_H - ROLLER_R, "top": GRIP_Z["top"] + LINK_HALF_H + ROLLER_R}
SPROCKET_RIM = R + 10.0
NOTCH_R, HUB_R, HUB_HALF, SPROCKET_HALF, SPROCKET_BORE = 16.0, 40.0, 40.0, 10.0, 20.0
SHAFT_HALF = 110.0                                  # shafts y -110..110: into the frames' side plates
PLATE_Y = (90.0, 110.0)                             # frames' side plates |y| 90..110
CABLE_ROLLER_X, CABLE_ROLLER_R, CABLE_ROLLER_HALF, CABLE_ROLLER_BORE = (-700.0, 700.0), 50.0, 50.0, 12.0
CABLE_ROLLER_Z = CABLE_Z - CABLE_R - CABLE_ROLLER_R          # 920
NORMAL = {"bottom": np.array([0.0, 1.0, 0.0]), "top": np.array([0.0, -1.0, 0.0])}   # loop normals (links' y)
SWEEP_OUT, SWEEP_IN, SWEEP_HALF_Y = PAD_Z[1], LINK_HALF_H, PAD_HALF_Y

# --- the belt drive --------------------------------------------------------------------------------------------------
BELT_X = 1500.0
BELT_PITCH = 40.0
PULLEY_HALF, PULLEY_GAP, PULLEY_BORE = 25.0, 6.0, 10.0     # pulley radius = pitch radius - 6
BELT_A = (np.array([0.0, 400.0]), 120.0)                   # (y, z) centre, pitch-line radius
BELT_B = (np.array([700.0, 400.0]), 80.0)
BELT_C_Y, BELT_C_R, BELT_C_Z0 = 350.0, 50.0, 800.0         # C's z is solved (near 800)
BELT_FRAME_BOX = (BELT_X - 70.0, -200.0, 0.0, BELT_X - 50.0, 850.0, 900.0)


def track_pins(which: str) -> np.ndarray:
    """The 22 pin centres of a track (world, mm), in loop order: from the drive sprocket's tangent point on the
    gripping run along it (+X), round the idler, back along the other run, round the drive sprocket.
    ``which`` = "bottom" or "top" (the bottom track mirrored about z = 1000)."""
    zs = SPROCKET_Z["bottom"]
    a, nt = A_HALF, TEETH
    pins = [(-a + k * PITCH, zs + R) for k in range(RUN_LINKS)]
    step = 2.0 * math.pi / nt
    for k in range(nt // 2):
        t = math.pi / 2.0 - k * step
        pins.append((a + R * math.cos(t), zs + R * math.sin(t)))
    pins += [(a - k * PITCH, zs - R) for k in range(RUN_LINKS)]
    for k in range(nt // 2):
        t = -math.pi / 2.0 - k * step
        pins.append((-a + R * math.cos(t), zs + R * math.sin(t)))
    out = np.array([(x, 0.0, z) for x, z in pins])
    if which == "top":
        out[:, 2] = 2.0 * CABLE_Z - out[:, 2]
    elif which != "bottom":
        raise ValueError(which)
    return out


def link_frame(a, b, normal) -> np.ndarray:
    """A link's frame (local -> world) between hinge points a -> b: x along the chord, y = the loop normal,
    z = x × y (outward)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    x = (b - a) / np.linalg.norm(b - a)
    z = np.cross(x, normal)
    return G.Frame((a + b) / 2.0, x, z)


# --- the belt's loop -------------------------------------------------------------------------------------------------

class Loop2D:
    """The belt's loop in the (y, z) plane: outer tangents between the wheels (in order, anticlockwise about +X) and
    the arcs on them. s = arc length from pin 0 (the tangent point where the belt leaves the first wheel)."""

    def __init__(self, wheels):
        self.wheels = [(np.asarray(c, float), float(r)) for c, r in wheels]
        n = len(self.wheels)
        tans = []                                         # (point on i, point on i+1, outward normal)
        for i in range(n):
            (ci, ri), (cj, rj) = self.wheels[i], self.wheels[(i + 1) % n]
            d = cj - ci
            L = float(np.linalg.norm(d))
            u = d / L
            w = np.array([u[1], -u[0]])                   # right of the travel: outward on an anticlockwise loop
            s = (ri - rj) / L
            m = w * math.sqrt(1.0 - s * s) + u * s
            tans.append((ci + ri * m, cj + rj * m, m))
        self.segments = []                                # ("line", p0, p1, length) / ("arc", c, r, a0, da, length)
        for i in range(n):
            p0, p1, m = tans[i]
            self.segments.append(("line", p0, p1, float(np.linalg.norm(p1 - p0))))
            j = (i + 1) % n
            cj, rj = self.wheels[j]
            m_out = tans[j][2]
            a0 = math.atan2(m[1], m[0])
            da = (math.atan2(m_out[1], m_out[0]) - a0) % (2.0 * math.pi)
            self.segments.append(("arc", cj, rj, a0, da, rj * da))
        self.length = sum(s[-1] for s in self.segments)

    def point(self, s: float) -> np.ndarray:
        s = s % self.length
        for seg in self.segments:
            if s <= seg[-1] or seg is self.segments[-1]:
                if seg[0] == "line":
                    _k, p0, p1, L = seg
                    return p0 + (p1 - p0) * (s / L)
                _k, c, r, a0, _da, _L = seg
                a = a0 + s / r
                return c + r * np.array([math.cos(a), math.sin(a)])
            s -= seg[-1]
        raise AssertionError

    def next_pin(self, s: float, pitch: float) -> float:
        """The s further along whose point is exactly ``pitch`` away (straight line) from point(s)."""
        p = self.point(s)
        lo, hi = s + pitch * (1.0 - 1e-12), s + pitch * 1.6
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if np.linalg.norm(self.point(mid) - p) < pitch:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-13 * max(1.0, abs(s)):
                break
        return 0.5 * (lo + hi)

    def walk(self, n: int, pitch: float) -> list:
        s = [0.0]
        for _ in range(n):
            s.append(self.next_pin(s[-1], pitch))
        return s


def _belt_loop(zc: float) -> Loop2D:
    return Loop2D([BELT_A, BELT_B, (np.array([BELT_C_Y, zc]), BELT_C_R)])


def _solve_belt():
    """N = round(loop length / pb) at zC = 800, then zC so that N chord steps close the loop."""
    n = int(round(_belt_loop(BELT_C_Z0).length / BELT_PITCH))

    def f(zc):
        loop = _belt_loop(zc)
        return loop.walk(n, BELT_PITCH)[-1] - loop.length
    lo, hi = BELT_C_Z0 - 100.0, BELT_C_Z0 + 100.0
    flo, fhi = f(lo), f(hi)
    assert flo * fhi < 0.0, (flo, fhi)
    while hi - lo > 1e-9:
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm < 0.0) == (flo < 0.0):
            lo, flo = mid, fm
        else:
            hi = mid
    zc = 0.5 * (lo + hi)
    loop = _belt_loop(zc)
    s = loop.walk(n, BELT_PITCH)
    closure = float(np.linalg.norm(loop.point(s[-1]) - loop.point(0.0)))
    return n, zc, loop, s, closure


BELT_N, BELT_C_Z, BELT_LOOP, _BELT_S, BELT_CLOSURE = _solve_belt()
BELT_C = (np.array([BELT_C_Y, BELT_C_Z]), BELT_C_R)
BELT_WHEELS = {"BELT PULLEY A": BELT_A, "BELT PULLEY B": BELT_B, "BELT PULLEY C": BELT_C}


def belt_pins() -> np.ndarray:
    """The belt's N hinge pins (world, mm) in loop order, pin 0 where the belt leaves A towards B."""
    return np.array([(BELT_X, *BELT_LOOP.point(s)) for s in _BELT_S[:-1]])


# =====================================================================================================================
# the scene: parts, assemblies, IDs
# =====================================================================================================================

ROOT = "TEST.TRACKS"
TRACK_ASM = {"bottom": "BOTTOM TRACK.ASM", "top": "TOP TRACK.ASM"}
_TRACK_PARTS = (["DRIVE SPROCKET", "IDLER SPROCKET"] + ["SPROCKET SHAFT"] * 2 + ["SUPPORT ROLLER"] * 2
                + ["ROLLER SHAFT"] * 2 + ["TRACK CHAIN LINK"] * 22 + ["TRACK PAD"] * 22)
PARTS = (["BASE FRAME", "CABLE", "CABLE ROLLER", "CABLE ROLLER"] + _TRACK_PARTS + ["TOP TRACK FRAME"] + _TRACK_PARTS
         + ["BELT FRAME", "BELT PULLEY A", "BELT PULLEY B", "BELT PULLEY C"] + ["BELT LINK"] * BELT_N)
ASSEMBLIES = [ROOT, "BOTTOM TRACK.ASM", "TOP CARRIAGE.ASM", "TOP TRACK.ASM", "BELT DRIVE.ASM"]
_ASM_PATH = {"bottom": f"{ROOT}#1/BOTTOM TRACK.ASM#1", "top": f"{ROOT}#1/TOP CARRIAGE.ASM#1/TOP TRACK.ASM#1"}


def _uids():
    """The importer's part IDs: ``UID[name]`` for a part or assembly that is there once; "CABLE ROLLER 1" / "2";
    for the tracks "<bottom|top> <NAME> <k>" (k from 1, as the #k of the ID; links and pads in loop order: link k of
    the loop is "… TRACK CHAIN LINK k+1") and "<bottom|top> <NAME>" for the first; "BELT LINK <k>" (k from 1)."""
    u = {ROOT: f"{ROOT}#1", "BASE FRAME": f"{ROOT}#1/BASE FRAME#1", "CABLE": f"{ROOT}#1/CABLE#1",
         "CABLE ROLLER 1": f"{ROOT}#1/CABLE ROLLER#1", "CABLE ROLLER 2": f"{ROOT}#1/CABLE ROLLER#2",
         "BOTTOM TRACK.ASM": _ASM_PATH["bottom"], "TOP CARRIAGE.ASM": f"{ROOT}#1/TOP CARRIAGE.ASM#1",
         "TOP TRACK.ASM": _ASM_PATH["top"], "TOP TRACK FRAME": f"{ROOT}#1/TOP CARRIAGE.ASM#1/TOP TRACK FRAME#1",
         "BELT DRIVE.ASM": f"{ROOT}#1/BELT DRIVE.ASM#1"}
    for which, base in _ASM_PATH.items():
        for name, count in (("DRIVE SPROCKET", 1), ("IDLER SPROCKET", 1), ("SPROCKET SHAFT", 2),
                            ("SUPPORT ROLLER", 2), ("ROLLER SHAFT", 2), ("TRACK CHAIN LINK", 22), ("TRACK PAD", 22)):
            for k in range(1, count + 1):
                u[f"{which} {name} {k}"] = f"{base}/{name}#{k}"
            u[f"{which} {name}"] = f"{base}/{name}#1"
    for name in ("BELT FRAME", "BELT PULLEY A", "BELT PULLEY B", "BELT PULLEY C"):
        u[name] = f"{ROOT}#1/BELT DRIVE.ASM#1/{name}#1"
    for k in range(1, BELT_N + 1):
        u[f"BELT LINK {k}"] = f"{ROOT}#1/BELT DRIVE.ASM#1/BELT LINK#{k}"
    return u


UID = _uids()


def _t(p):
    return tuple(round(float(v), 4) for v in p)


def _numbers():
    def track(which):
        zs, sign = SPROCKET_Z[which], (1.0 if which == "bottom" else -1.0)
        pins = track_pins(which)
        return {
            "assembly": UID[TRACK_ASM[which]],
            "pins": [_t(p) for p in pins],
            "links": len(pins),
            "normal": _t(NORMAL[which]),
            "sprockets": {"drive": {"uid": UID[f"{which} DRIVE SPROCKET"], "centre": (-A_HALF, 0.0, round(zs, 4)),
                                    "shaft_uid": UID[f"{which} SPROCKET SHAFT 1"]},
                          "idler": {"uid": UID[f"{which} IDLER SPROCKET"], "centre": (A_HALF, 0.0, round(zs, 4)),
                                    "shaft_uid": UID[f"{which} SPROCKET SHAFT 2"]}},
            "sprocket_axis": (0.0, 1.0, 0.0), "sprocket_rim": round(SPROCKET_RIM, 4), "notch_radius": NOTCH_R,
            "notch_angles": [18.0 + 36.0 * k for k in range(TEETH)],
            "support_rollers": [{"uid": UID[f"{which} SUPPORT ROLLER {k + 1}"],
                                 "shaft_uid": UID[f"{which} ROLLER SHAFT {k + 1}"],
                                 "centre": (x, 0.0, ROLLER_Z[which])} for k, x in enumerate(ROLLER_X)],
            "support_roller_radius": ROLLER_R,
            "support_roller_seat": ROLLER_R + LINK_HALF_H,       # its centre to the pin line
            "grip_pin_z": GRIP_Z[which],
            "grip_pad_face_z": GRIP_Z[which] + sign * PAD_Z[1],
            "grip_links": list(range(RUN_LINKS)),
            "pad_moves_with_cable_plus_x": (1.0, 0.0, 0.0),
            "link_uids": [UID[f"{which} TRACK CHAIN LINK {k + 1}"] for k in range(len(pins))],
            "pad_uids": [UID[f"{which} TRACK PAD {k + 1}"] for k in range(len(pins))],
            "inner_links": list(range(0, len(pins), 2)), "outer_links": list(range(1, len(pins), 2)),
            "sweep": {"x": (-A_HALF - R - SWEEP_OUT, A_HALF + R + SWEEP_OUT),
                      "z": tuple(sorted((round(zs - sign * (R + SWEEP_OUT), 4),
                                         round(zs + sign * (R + SWEEP_OUT), 4)))),
                      "half_y": SWEEP_HALF_Y},
        }
    pins = belt_pins()
    counts = {}
    for name in PARTS:
        counts[name] = counts.get(name, 0) + 1
    return {
        "units": "mm",
        "pitch": PITCH, "teeth": TEETH, "R": round(R, 6), "tooth_angle": 360.0 / TEETH,
        "grip_links": RUN_LINKS,
        "link": {"hinges": (-PITCH / 2, PITCH / 2), "half_height": LINK_HALF_H,
                 "inner_y": ((25.0, 33.0), 14.0, 8.5), "outer_y": ((35.0, 43.0), 8.0), "half_y": 43.0},
        "pad": {"x": (-PAD_HALF_X, PAD_HALF_X), "y": (-PAD_HALF_Y, PAD_HALF_Y), "z": PAD_Z},
        "bottom": track("bottom"),
        "top": track("top"),
        "cable": {"uid": UID["CABLE"], "start": (CABLE_X[0], 0.0, CABLE_Z), "end": (CABLE_X[1], 0.0, CABLE_Z),
                  "radius": CABLE_R, "direction": (1.0, 0.0, 0.0)},
        "cable_rollers": [{"uid": UID[f"CABLE ROLLER {k + 1}"], "centre": (x, 0.0, CABLE_ROLLER_Z),
                           "radius": CABLE_ROLLER_R, "axis": (0.0, 1.0, 0.0)} for k, x in enumerate(CABLE_ROLLER_X)],
        "lift": {"assembly": UID["TOP CARRIAGE.ASM"], "frame_uid": UID["TOP TRACK FRAME"], "axis": (0.0, 0.0, 1.0)},
        "base_uid": UID["BASE FRAME"],
        "belt": {
            "assembly": UID["BELT DRIVE.ASM"], "frame_uid": UID["BELT FRAME"],
            "pb": BELT_PITCH, "N": BELT_N, "zC": round(BELT_C_Z, 9), "loop_length": round(BELT_LOOP.length, 6),
            "closure": BELT_CLOSURE, "axis": (1.0, 0.0, 0.0), "plane_x": BELT_X, "normal": (1.0, 0.0, 0.0),
            "wheels": [{"name": name, "uid": UID[name],
                        "centre": (BELT_X, round(float(c[0]), 9), round(float(c[1]), 9)),
                        "pitch_radius": r, "radius": r - PULLEY_GAP} for name, (c, r) in BELT_WHEELS.items()],
            "pins": [_t(p) for p in pins],
            "link_uids": [UID[f"BELT LINK {k + 1}"] for k in range(BELT_N)],
            "link": {"hinges": (-BELT_PITCH / 2, BELT_PITCH / 2), "knuckle_r": 4.0, "half_y": 30.0, "z": (0.0, 8.0)},
        },
        "counts": counts,
        "parts": len(PARTS),
    }


NUMBERS = _numbers()

# =====================================================================================================================
# shapes (OpenCascade, through demo_model/geom.py)
# =====================================================================================================================

Y = (0.0, 1.0, 0.0)


def box(x0, y0, z0, x1, y1, z1):
    """A box from corner to corner."""
    return G.box(min(x0, x1), min(y0, y1), min(z0, z1), abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))


def ycyl(r, x, z, y0, y1):
    """A cylinder along +Y through (x, z) from y0 to y1."""
    return G.cyl(r, y1 - y0, (x, y0, z), Y)


def xcyl(r, y, z, x0, x1):
    """A cylinder along +X through (y, z) from x0 to x1."""
    return G.cyl(r, x1 - x0, (x0, y, z), (1.0, 0.0, 0.0))


def sprocket():
    """About its own origin, axis +Y: disc with the 10 pin notches, hub, bore."""
    disc = ycyl(SPROCKET_RIM, 0.0, 0.0, -SPROCKET_HALF, SPROCKET_HALF)
    notches = [ycyl(NOTCH_R, R * math.cos(math.radians(a)), R * math.sin(math.radians(a)),
                    -SPROCKET_HALF - 5.0, SPROCKET_HALF + 5.0) for a in NUMBERS["bottom"]["notch_angles"]]
    body = G.fuse(G.cut(disc, *notches), ycyl(HUB_R, 0.0, 0.0, -HUB_HALF, HUB_HALF))
    return G.cut(body, ycyl(SPROCKET_BORE, 0.0, 0.0, -HUB_HALF - 5.0, HUB_HALF + 5.0))


def wheel(r, half, bore):
    """A plain cylinder about its own origin, axis +Y, with a bore."""
    return G.cut(ycyl(r, 0.0, 0.0, -half, half), ycyl(bore, 0.0, 0.0, -half - 5.0, half + 5.0))


def _stadium(y0, y1):
    h, e = LINK_HALF_H, PITCH / 2.0
    return G.fuse(box(-e, y0, -h, e, y1, h), ycyl(h, -e, 0.0, y0, y1), ycyl(h, e, 0.0, y0, y1))


def inner_link():
    e = PITCH / 2.0
    parts = []
    for y0, y1 in ((25.0, 33.0), (-33.0, -25.0)):
        holes = [ycyl(8.5, x, 0.0, y0 - 1.0, y1 + 1.0) for x in (-e, e)]
        parts.append(G.cut(_stadium(y0, y1), *holes))
    for x in (-e, e):
        parts.append(G.cut(ycyl(14.0, x, 0.0, -25.0, 25.0), ycyl(8.5, x, 0.0, -26.0, 26.0)))
    return G.fuse(*parts)


def outer_link():
    e = PITCH / 2.0
    return G.fuse(_stadium(35.0, 43.0), _stadium(-43.0, -35.0), ycyl(8.0, -e, 0.0, -43.0, 43.0),
                  ycyl(8.0, e, 0.0, -43.0, 43.0))


def pad():
    return box(-PAD_HALF_X, -PAD_HALF_Y, PAD_Z[0], PAD_HALF_X, PAD_HALF_Y, PAD_Z[1])


def shaft(r):
    return ycyl(r, 0.0, 0.0, -SHAFT_HALF, SHAFT_HALF)


def base_frame():
    zs, zr = SPROCKET_Z["bottom"], ROLLER_Z["bottom"]
    parts = [box(-820.0, -200.0, 0.0, 820.0, 200.0, 40.0)]
    holes = []
    for s in (1, -1):
        parts.append(box(-350.0, s * PLATE_Y[0], 40.0, 350.0, s * PLATE_Y[1], 880.0))
    for x in (-A_HALF, A_HALF):
        holes.append(ycyl(SPROCKET_BORE, x, zs, -PLATE_Y[1] - 5.0, PLATE_Y[1] + 5.0))
    for x in ROLLER_X:
        holes.append(ycyl(ROLLER_BORE, x, zr, -PLATE_Y[1] - 5.0, PLATE_Y[1] + 5.0))
    for x in CABLE_ROLLER_X:
        for s in (1, -1):
            parts.append(box(x - 25.0, s * 55.0, 40.0, x + 25.0, s * 75.0, 945.0))
        parts.append(ycyl(CABLE_ROLLER_BORE, x, CABLE_ROLLER_Z, -75.0, 75.0))
    return G.cut(G.fuse(*parts), *holes)


def top_frame():
    zs, zr = SPROCKET_Z["top"], ROLLER_Z["top"]
    parts = [box(-350.0, -PLATE_Y[1], 1490.0, 350.0, PLATE_Y[1], 1530.0)]
    for s in (1, -1):
        parts.append(box(-350.0, s * PLATE_Y[0], 1110.0, 350.0, s * PLATE_Y[1], 1530.0))
    holes = [ycyl(SPROCKET_BORE, x, zs, -PLATE_Y[1] - 5.0, PLATE_Y[1] + 5.0) for x in (-A_HALF, A_HALF)]
    holes += [ycyl(ROLLER_BORE, x, zr, -PLATE_Y[1] - 5.0, PLATE_Y[1] + 5.0) for x in ROLLER_X]
    return G.cut(G.fuse(*parts), *holes)


def belt_link():
    e = BELT_PITCH / 2.0
    return G.fuse(box(-16.0, -30.0, 2.0, 16.0, 30.0, 8.0), box(-e, -30.0, 0.0, e, 30.0, 2.0),
                  ycyl(4.0, -e, 0.0, -30.0, 30.0), ycyl(4.0, e, 0.0, -30.0, 30.0))


def belt_frame():
    x0, y0, z0, x1, y1, z1 = BELT_FRAME_BOX
    parts = [box(x0, y0, z0, x1, y1, z1)]
    for c, _r in BELT_WHEELS.values():
        parts.append(xcyl(PULLEY_BORE, c[0], c[1], x1, BELT_X + PULLEY_HALF))
    return G.fuse(*parts)


def pulley(r):
    return G.cut(xcyl(r - PULLEY_GAP, 0.0, 0.0, -PULLEY_HALF, PULLEY_HALF),
                 xcyl(PULLEY_BORE, 0.0, 0.0, -PULLEY_HALF - 5.0, PULLEY_HALF + 5.0))


def model():
    root = G.Asm(ROOT)
    root.add(G.Part("BASE FRAME", base_frame(), GREY))
    root.add(G.Part("CABLE", xcyl(CABLE_R, 0.0, CABLE_Z, *CABLE_X), BLACK))
    croller = G.Part("CABLE ROLLER", wheel(CABLE_ROLLER_R, CABLE_ROLLER_HALF, CABLE_ROLLER_BORE), YELLOW)
    for x in CABLE_ROLLER_X:
        root.add(croller, G.T(x, 0.0, CABLE_ROLLER_Z))
    # the same shape, made twice: the STEP writer gives one shape one name (the second would rename the first)
    drive, idler = G.Part("DRIVE SPROCKET", sprocket(), STEEL), G.Part("IDLER SPROCKET", sprocket(), STEEL)
    sshaft = G.Part("SPROCKET SHAFT", shaft(SPROCKET_BORE), STEEL)
    rshaft = G.Part("ROLLER SHAFT", shaft(ROLLER_BORE), STEEL)
    sroller = G.Part("SUPPORT ROLLER", wheel(ROLLER_R, ROLLER_HALF, ROLLER_BORE), STEEL)
    inner, outer = G.Part("TRACK CHAIN LINK", inner_link(), CHAIN), G.Part("TRACK CHAIN LINK", outer_link(), CHAIN)
    tpad = G.Part("TRACK PAD", pad(), RUBBER)

    def track(which):
        asm = G.Asm(TRACK_ASM[which])
        zs, zr = SPROCKET_Z[which], ROLLER_Z[which]
        asm.add(drive, G.T(-A_HALF, 0.0, zs))
        asm.add(idler, G.T(A_HALF, 0.0, zs))
        for x in (-A_HALF, A_HALF):
            asm.add(sshaft, G.T(x, 0.0, zs))
        for x in ROLLER_X:
            asm.add(sroller, G.T(x, 0.0, zr))
        for x in ROLLER_X:
            asm.add(rshaft, G.T(x, 0.0, zr))
        pins = track_pins(which)
        frames = [link_frame(pins[k], pins[(k + 1) % len(pins)], NORMAL[which]) for k in range(len(pins))]
        for k, F in enumerate(frames):
            asm.add(inner if k % 2 == 0 else outer, F)
        for F in frames:
            asm.add(tpad, F)
        return asm

    root.add(track("bottom"))
    carriage = G.Asm("TOP CARRIAGE.ASM")
    carriage.add(G.Part("TOP TRACK FRAME", top_frame(), GREY))
    carriage.add(track("top"))
    root.add(carriage)
    belt = G.Asm("BELT DRIVE.ASM")
    belt.add(G.Part("BELT FRAME", belt_frame(), GREY))
    for name, (c, r) in BELT_WHEELS.items():
        belt.add(G.Part(name, pulley(r), STEEL), G.T(BELT_X, c[0], c[1]))
    bl = G.Part("BELT LINK", belt_link(), ORANGE)
    pins = belt_pins()
    for k in range(BELT_N):
        belt.add(bl, link_frame(pins[k], pins[(k + 1) % BELT_N], np.array([1.0, 0.0, 0.0])))
    root.add(belt)
    return root


def placed(root):
    """Every part once per place: (name, uid, shape in the model's coordinates)."""
    return [(node.name, uid, G.xform(node.shape, W)) for node, uid, W, _label, _path in G.walk(root)
            if isinstance(node, G.Part)]


def bounds(shape):
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

def track_sweep(which):
    """The room a track's chain (links and pads) sweeps as it runs: a stadium round both sprockets, R + 60 out,
    |y| <= 60 (filled: it holds the sprockets too)."""
    zs, r = SPROCKET_Z[which], R + SWEEP_OUT
    h = SWEEP_HALF_Y
    return G.fuse(box(-A_HALF, -h, zs - r, A_HALF, h, zs + r), ycyl(r, -A_HALF, zs, -h, h), ycyl(r, A_HALF, zs, -h, h))


def _cross2(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def belt_sweep():
    """The room the belt sweeps: the hull of the wheels' circles grown by the link's height (8) + 1, x 1470..1530
    (filled; the check takes the pulleys out of it, their stubs sit in them)."""
    pts = []
    for c, r in BELT_WHEELS.values():
        for a in np.linspace(0.0, 2.0 * math.pi, 73)[:-1]:
            pts.append(c + (r + 9.0) * np.array([math.cos(a), math.sin(a)]))
    pts = np.array(pts)
    # convex hull (monotone chain)
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and _cross2(h[-1] - h[-2], p - h[-2]) <= 0:
                h.pop()
            h.append(p)
        return h
    hull = half(pts)[:-1] + half(pts[::-1])[:-1]
    return G.polygon_prism([(float(y), float(z)) for y, z in hull], 60.0,
                           G.Frame((BELT_X - 30.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))


def _dist(a, b):
    return float(BRepExtrema_DistShapeShape(a, b).Value())


def check(root, say=print):
    parts = placed(root)
    assert [p[0] for p in parts] == PARTS, [p[0] for p in parts]
    assert {u for _n, u, _s in parts} >= {v for k, v in UID.items() if not k.endswith(".ASM") and k != ROOT}
    boxes = []
    for name, uid, shape in parts:
        assert G.solids(shape) == 1 and BRepCheck_Analyzer(shape).IsValid() and G.volume(shape) > 0, uid
        boxes.append(bounds(shape))
    idx = {u: i for i, (_n, u, _s) in enumerate(parts)}
    # pairs that must touch (distance 0, nothing in common) and pairs that may overlap
    touch = set()
    for which in ("bottom", "top"):
        tn = NUMBERS[which]
        for k in range(RUN_LINKS):
            touch.add(frozenset((tn["pad_uids"][k], UID["CABLE"])))
        for k in range(22):
            touch.add(frozenset((tn["pad_uids"][k], tn["link_uids"][k])))
        frame = UID["BASE FRAME"] if which == "bottom" else UID["TOP TRACK FRAME"]
        for k, wheel_key in ((1, "DRIVE SPROCKET"), (2, "IDLER SPROCKET")):
            s = UID[f"{which} SPROCKET SHAFT {k}"]
            touch |= {frozenset((s, UID[f"{which} {wheel_key}"])), frozenset((s, frame))}
        pins = track_pins(which)
        for k in range(2):
            s, r = UID[f"{which} ROLLER SHAFT {k + 1}"], UID[f"{which} SUPPORT ROLLER {k + 1}"]
            touch |= {frozenset((s, r)), frozenset((s, frame))}
            j = int(np.argmin(np.abs(pins[:RUN_LINKS + 1, 0] - ROLLER_X[k])))     # the pin over the roller
            touch |= {frozenset((r, tn["link_uids"][j - 1])), frozenset((r, tn["link_uids"][j]))}
    for k in (1, 2):
        touch.add(frozenset((UID[f"CABLE ROLLER {k}"], UID["CABLE"])))
        touch.add(frozenset((UID[f"CABLE ROLLER {k}"], UID["BASE FRAME"])))
    for name in BELT_WHEELS:
        touch.add(frozenset((UID[name], UID["BELT FRAME"])))
    overlap = {frozenset((UID[f"BELT LINK {k + 1}"], UID[f"BELT LINK {(k + 1) % BELT_N + 1}"])) for k in range(BELT_N)}
    found = set()
    for i, (na, ua, sa) in enumerate(parts):
        for j in range(i + 1, len(parts)):
            nb, ub, sb = parts[j]
            apart = np.maximum(np.maximum(boxes[i][0] - boxes[j][1], boxes[j][0] - boxes[i][1]), 0.0)
            if np.linalg.norm(apart) > 1.0:
                continue
            d = _dist(sa, sb)
            if d > 1e-6:
                continue
            pair = frozenset((ua, ub))
            v = G.volume(BRepAlgoAPI_Common(sa, sb).Shape())
            if pair in overlap:
                assert v > 1.0, (ua, ub, "should overlap", v)
            else:
                assert v < 1e-3, (ua, "lies inside", ub, v)
                assert pair in touch, (ua, "touches", ub, "(not expected)")
            found.add(pair)
    missing = (touch | overlap) - found
    assert not missing, sorted(tuple(sorted(p)) for p in missing)[:5]
    say(f"  {len(parts)} parts, each one solid; {len(touch)} pairs touch, {len(overlap)} belt hinges overlap, "
        "nothing else meets")
    # clearances to the rooms the chains sweep
    shape = {u: s for _n, u, s in parts}
    carriage = [s for _n, u, s in parts if u.startswith(UID["TOP CARRIAGE.ASM"] + "/")]
    gaps = {"BASE FRAME - bottom sweep": _dist(shape[UID["BASE FRAME"]], track_sweep("bottom")),
            "BASE FRAME - top sweep": _dist(shape[UID["BASE FRAME"]], track_sweep("top")),
            "BASE FRAME - TOP CARRIAGE.ASM": min(_dist(shape[UID["BASE FRAME"]], s) for s in carriage),
            "TOP TRACK FRAME - top sweep": _dist(shape[UID["TOP TRACK FRAME"]], track_sweep("top")),
            "BELT FRAME - belt sweep": _dist(shape[UID["BELT FRAME"]], G.cut(belt_sweep(), *[
                xcyl(r - PULLEY_GAP, c[0], c[1], BELT_X - 40.0, BELT_X + 40.0) for c, r in BELT_WHEELS.values()]))}
    for k, v in gaps.items():
        assert v >= 5.0, (k, v)
    say("  clearances: " + ", ".join(f"{k} {v:.1f}" for k, v in gaps.items()))
    # the chains: pins one pitch apart, the links' hinges on them
    for which in ("bottom", "top"):
        p = track_pins(which)
        assert np.allclose(np.linalg.norm(np.roll(p, -1, 0) - p, axis=1), PITCH, atol=1e-9), which
    p = belt_pins()
    assert np.allclose(np.linalg.norm(np.roll(p, -1, 0) - p, axis=1), BELT_PITCH, atol=1e-4)
    assert BELT_CLOSURE < 1e-4, BELT_CLOSURE


def numbers(say=print):
    say(f"tensioner: pitch {PITCH}, {TEETH} teeth, R {R:.4f}, grip run {RUN_LINKS} links, 22 pins a track")
    for which in ("bottom", "top"):
        n = NUMBERS[which]
        say(f"  {which}: sprockets z {SPROCKET_Z[which]:.4f}, grip pin line z {n['grip_pin_z']}, pad faces z "
            f"{n['grip_pad_face_z']}, support rollers z {ROLLER_Z[which]}, normal {n['normal']}")
        for k, pin in enumerate(n["pins"]):
            say(f"    pin {k:2d} {pin}")
    b = NUMBERS["belt"]
    say(f"belt: pb {b['pb']}, N {b['N']}, zC {b['zC']:.9f}, loop length {b['loop_length']:.6f}, "
        f"closure {b['closure']:.2e}")
    say(f"parts {NUMBERS['parts']}: {NUMBERS['counts']}")


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
