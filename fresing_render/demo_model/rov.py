"""An invented work-class ROV for the demo's into-the-sea shot (task 0173): it watches the cable's touch-down. Its
own file ``demo_rov.step`` (``layout.FILES["rov"]``), imported as its own model by the demo (``blender/demo.py``).
A generic look – an open box frame under a yellow buoyancy block, seven ducted thrusters, two lights and a camera
at the front, two folded manipulator arms, the tether's bend restrictor on top – nothing of a real make.

**ROV coordinates** (mm): the origin is the middle of the skids' underside, +x forward (where the camera and the
lights look), +y port, z up. About 3.0 m long, 1.8 m wide, 1.9 m high.

Parts (each one solid with a colour): "ROV FRAME" (the box frame of rectangular beams, one solid), "ROV BUOYANCY",
"ROV SKID" (one runner, placed twice), 7 x "ROV THRUSTER DUCT" + "ROV PROPELLER" (each pair in its own "ROV
THRUSTER" assembly: 4 horizontal ones at the corners at ±45° in plan, 3 vertical ones through the buoyancy),
2 x "ROV LIGHT" + "ROV LIGHT LENS" (the lenses are what glows), "ROV CAMERA" + "ROV CAMERA LENS",
2 x "ROV MANIPULATOR", "ROV TETHER TERMINATION".

Joints (in the root, no prefix): "ROV: Thruster k turn" (k = 1 … 7; 1–4 horizontal: front port, front starboard, aft
port, aft starboard; 5–7 vertical: front port, front starboard, aft), each turns its propeller about its duct's axis
(a motor, driven by the operator).
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from .geom import Asm, Part, T
from .params import Params

ROOT = "DEMO ROV"
FILE = "demo_rov.step"

# ---- colours (sRGB) ----------------------------------------------------------------------------------------------
ALU = (0.66, 0.68, 0.70)              # the frame: bare aluminium
FOAM_YELLOW = (0.98, 0.70, 0.05)      # syntactic foam
SKID_GREY = (0.30, 0.32, 0.34)
DUCT_BLACK = (0.08, 0.08, 0.09)
BRONZE = (0.80, 0.55, 0.35)           # as the vessel's propellers
STEEL = (0.58, 0.59, 0.60)
LENS_WHITE = (0.95, 0.96, 0.97)       # the light lenses (they glow in the demo)
CAMERA_DARK = (0.20, 0.22, 0.24)
GLASS = (0.10, 0.14, 0.18)
ARM_GREY = (0.40, 0.42, 0.44)
RESTRICTOR_ORANGE = (0.95, 0.42, 0.05)

# ---- sizes (mm) ----------------------------------------------------------------------------------------------------
FX, FY = 1350.0, 800.0                # the frame's beam centre lines: x = ±FX, y = ±FY
BW = 80.0                             # beam section (square)
Z_SKID = 120.0                        # the skids' top = the frame's underside
Z_BOT = Z_SKID + BW / 2               # the frame's bottom beams' centre line
Z_TOP = 1210.0                        # its top beams' centre line
Z_FOAM = Z_TOP + BW / 2               # the buoyancy's underside (1250)
FOAM_H = 500.0
FOAM_X, FOAM_Y = 1400.0, 860.0        # half length / width of the buoyancy block
FOAM_CHAMFER = 120.0                  # its corners in plan
FOAM_EDGE = 60.0                      # its top edges
SKID_X = 1350.0                       # the runners' flat underside: x = ±SKID_X
SKID_W = 100.0

DUCT_RI = 160.0                       # the duct's inner radius (the propeller turns inside it)
DUCT_RO = 205.0
DUCT_LEN = 260.0
PROP_R = 145.0                        # the propeller's blade tips (corners included: see propeller())
PROP_HUB_R = 50.0
HOLE_R = 220.0                        # the vertical thrusters' holes through the buoyancy
H_THRUSTERS = ((1050.0, 500.0), (1050.0, -500.0), (-1050.0, 500.0), (-1050.0, -500.0))
Z_H = 700.0                           # the horizontal thrusters' axes
V_THRUSTERS = ((480.0, 420.0), (480.0, -420.0), (-560.0, 0.0))

LIGHT_R, LIGHT_LEN = 70.0, 200.0
LIGHT_Y, LIGHT_Z = 600.0, Z_TOP - BW / 2 - LIGHT_R          # just under the top front beam
LIGHT_X0 = FX - 20.0                                        # the housing's back
LENS_R, LENS_T = 55.0, 8.0
CAM_TILT = 20.0                        # deg down
TETHER_TILT = 30.0                     # deg aft from vertical
TETHER_AT = (-1150.0, 0.0)
TETHER_LEN = 190.0


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _bar(p0, p1, w=BW):
    """A beam w x w from p0 to p1, half a section longer at each end (corners overlap: one solid when fused)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = _unit(p1 - p0)
    return g.beam(p0 - d * w / 2, p1 + d * w / 2, w)


# ---------------------------------------------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------------------------------------------

def frame():
    """The open box frame: two rectangles (bottom, top), six posts, cross members, side diagonals."""
    bars = []
    for z in (Z_BOT, Z_TOP):
        for y in (-FY, FY):
            bars.append(_bar((-FX, y, z), (FX, y, z)))
        for x in (-FX, 0.0, FX):
            bars.append(_bar((x, -FY, z), (x, FY, z)))
    for x in (-FX, 0.0, FX):
        for y in (-FY, FY):
            bars.append(_bar((x, y, Z_BOT), (x, y, Z_TOP)))
    for y in (-FY, FY):                                   # side diagonals, one per bay
        bars.append(_bar((-FX, y, Z_BOT), (0.0, y, Z_TOP), 60.0))
        bars.append(_bar((FX, y, Z_BOT), (0.0, y, Z_TOP), 60.0))
    # a bottom cross member under the manipulators and a tool skid plate's rails
    bars.append(_bar((FX - 300.0, -FY, Z_BOT), (FX - 300.0, FY, Z_BOT), 60.0))
    return g.fuse(*bars)


def buoyancy():
    """The foam block on top: corners chamfered in plan, top edges chamfered, through-holes for the vertical
    thrusters."""
    def plan(inset):
        a, b, c = FOAM_X - inset, FOAM_Y - inset, FOAM_CHAMFER
        return [(a, -b + c), (a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b), (a - c, -b)]
    z0, z1 = Z_FOAM, Z_FOAM + FOAM_H
    secs = [[(x, y, z0) for x, y in plan(0.0)], [(x, y, z1 - FOAM_EDGE) for x, y in plan(0.0)],
            [(x, y, z1) for x, y in plan(FOAM_EDGE)]]
    block = g.loft(secs)
    holes = [g.cyl(HOLE_R, FOAM_H + 20.0, (x, y, z0 - 10.0)) for x, y in V_THRUSTERS]
    return g.cut(block, *holes)


def skid():
    """One runner (centred on y = 0): a flat bar under the frame's side beam, turned up at the front."""
    flat = g.box(-SKID_X, -SKID_W / 2, 0.0, 2 * SKID_X, SKID_W, Z_SKID)
    nose = g.beam((SKID_X - 100.0, 0.0, Z_SKID / 2), (SKID_X + 90.0, 0.0, Z_SKID + 40.0), SKID_W, Z_SKID)
    return g.fuse(flat, nose)


def duct():
    """A short nozzle about local +z (z 0 … DUCT_LEN): a straight bore DUCT_RI, a flared outside; the motor pod in
    the middle on three struts at the intake end."""
    ri, ro = DUCT_RI, DUCT_RO
    prof = [(ri, 0.0), (ro - 15.0, 0.0), (ro, 40.0), (ro, DUCT_LEN - 60.0), (ri + 15.0, DUCT_LEN), (ri, DUCT_LEN)]
    ring = g.revolve(prof)
    pod = g.fuse(g.cyl(PROP_HUB_R + 5.0, 75.0, (0, 0, 30.0)),
                 g.cone(PROP_HUB_R + 5.0, 20.0, 25.0, (0, 0, 30.0), (0, 0, -1)))       # its nose stays in the duct
    struts = [g.xform(g.box(PROP_HUB_R, -8.0, 20.0, ri - PROP_HUB_R + 10.0, 16.0, 40.0), g.Rot((0, 0, 1), 120.0 * k))
              for k in range(3)]
    return g.fuse(ring, pod, *struts)


PROP_Z = (110.0, 190.0)                 # the propeller's hub (local z) in its duct


def propeller():
    """Hub + four flat blades at 30° pitch, about local +z (in the duct's frame): one solid."""
    z0, z1 = PROP_Z
    zc = 0.5 * (z0 + z1)
    hub = g.fuse(g.cyl(PROP_HUB_R, z1 - z0, (0, 0, z0)), g.cone(PROP_HUB_R, 18.0, 40.0, (0, 0, z1)))
    chord, thick = 80.0, 10.0
    half = 0.5 * (chord * math.cos(math.radians(30.0)) + thick * math.sin(math.radians(30.0)))   # across, seen along z
    tip = math.sqrt(PROP_R ** 2 - half ** 2)                # the tip corners lie on PROP_R
    blades = []
    for k in range(4):
        b = g.box(PROP_HUB_R - 10.0, -chord / 2, -thick / 2, tip - PROP_HUB_R + 10.0, chord, thick)
        b = g.xform(b, g.Rot((0, 0, 1), 90.0 * k + 45.0) @ T(0, 0, zc) @ g.Rot((1, 0, 0), 30.0))
        blades.append(b)
    return g.fuse(hub, *blades)


def light():
    """A lamp housing about local +z (z 0 … LIGHT_LEN): a cylinder with a front bezel and cooling rings."""
    body = g.cyl(LIGHT_R, LIGHT_LEN)
    bezel = g.tube(LIGHT_R + 8.0, LENS_R, 25.0, (0, 0, LIGHT_LEN - 25.0))
    rings = [g.cyl(LIGHT_R + 6.0, 12.0, (0, 0, z)) for z in (40.0, 90.0)]
    return g.fuse(body, bezel, *rings)


def lens(r: float, t: float):
    return g.cyl(r, t)


def camera():
    """The pan-tilt camera hanging from the top front beam: a pan base, a yoke and a housing along local +x
    tilted down by CAM_TILT. In ROV coordinates; returns (shape, lens frame)."""
    base_c = np.array([FX, 0.0, Z_TOP - BW / 2])
    pan = g.cyl(60.0, 70.0, base_c - [0, 0, 70.0])
    yoke = g.box(FX - 40.0, -110.0, Z_TOP - BW / 2 - 200.0, 80.0, 220.0, 135.0)
    pivot = np.array([FX + 40.0, 0.0, Z_TOP - BW / 2 - 160.0])
    d = np.array([math.cos(math.radians(CAM_TILT)), 0.0, -math.sin(math.radians(CAM_TILT))])
    housing = g.cyl(75.0, 260.0, pivot - d * 80.0, d)
    trunnion = g.rod(pivot - [0, 120.0, 0], pivot + [0, 120.0, 0], 30.0)
    front = pivot + d * 180.0
    return g.fuse(pan, yoke, housing, trunnion), g.on_axis(front, d)


def manipulator(side: float):
    """A folded arm at the lower front (one solid): shoulder on the bottom front beam, upper arm forward, forearm
    folded back up, a wrist and a two-finger jaw pointing forward-down."""
    y = side * 400.0
    sh = np.array([FX + 30.0, y, Z_BOT + 90.0])
    el = np.array([FX + 160.0, y, Z_BOT + 260.0])
    wr = np.array([FX + 60.0, y, Z_BOT + 470.0])
    jaw = wr + np.array([120.0, 0.0, -40.0])
    pieces = [g.box(FX - 40.0, y - 70.0, Z_BOT - BW / 2, 130.0, 140.0, 140.0),          # the base on the beam
              g.rod(sh - [0, 60.0, 0], sh + [0, 60.0, 0], 45.0),                       # shoulder
              g.beam(sh, el, 90.0), g.rod(el - [0, 55.0, 0], el + [0, 55.0, 0], 40.0),  # upper arm, elbow
              g.beam(el, wr, 70.0), g.rod(wr - [0, 45.0, 0], wr + [0, 45.0, 0], 42.0),   # forearm, wrist
              g.rod(wr, jaw, 30.0)]
    for s in (-1.0, 1.0):
        f0 = jaw + [0, s * 22.0, 0]
        pieces.append(g.beam(f0 - [20.0, 0, 0], f0 + [70.0, 0, -50.0], 18.0, 30.0))
    return g.fuse(*pieces)


def termination():
    """The tether's bend restrictor on top, aft, leaning aft by TETHER_TILT: a flange on the foam, a bullet-shaped
    body. In ROV coordinates; returns (shape, the tether's point, its direction)."""
    base = np.array([TETHER_AT[0], TETHER_AT[1], Z_FOAM + FOAM_H])
    d = np.array([-math.sin(math.radians(TETHER_TILT)), 0.0, math.cos(math.radians(TETHER_TILT))])
    flange = g.cyl(120.0, 40.0, base)                         # flat on the foam's top
    prof = [(0.0, 0.0), (85.0, 0.0), (85.0, 90.0), (65.0, 110.0), (60.0, 140.0), (40.0, TETHER_LEN),
            (0.0, TETHER_LEN)]
    start = base + [0, 0, 50.0]                              # the leaning body's foot stays in the flange
    body = g.revolve(prof, start, d)
    tip = start + d * TETHER_LEN
    return g.fuse(flange, body), tip, d


# ---------------------------------------------------------------------------------------------------------------
# the ROV
# ---------------------------------------------------------------------------------------------------------------

def _thruster_frames():
    """(centre, axis direction) of the 7 thrusters: 4 horizontal (pointing out to their corner), 3 vertical (up)."""
    out = []
    for x, y in H_THRUSTERS:
        out.append((np.array([x, y, Z_H]), _unit((math.copysign(1.0, x), math.copysign(1.0, y), 0.0))))
    zc = Z_FOAM + FOAM_H / 2
    for x, y in V_THRUSTERS:
        out.append((np.array([x, y, zc]), np.array([0.0, 0.0, 1.0])))
    return out


def build(p: Params | None = None) -> tuple[Asm, dict]:
    """(root Asm, info for the route sheet; ROV coordinates, mm)."""
    del p                                              # (the ROV does not depend on the cable)
    root = Asm(ROOT)
    root.add(Part("ROV FRAME", frame(), ALU))
    root.add(Part("ROV BUOYANCY", buoyancy(), FOAM_YELLOW))
    sk = Part("ROV SKID", skid(), SKID_GREY)
    for y in (FY, -FY):
        root.add(sk, T(0.0, y, 0.0))
    # thrusters: one assembly shape, placed 7 times; each its own copy so its propeller turns alone
    duct_p = Part("ROV THRUSTER DUCT", duct(), DUCT_BLACK)
    prop_p = Part("ROV PROPELLER", propeller(), BRONZE)
    thrusters = []
    for k, (c, d) in enumerate(_thruster_frames()):
        a = Asm("ROV THRUSTER")
        a.add(duct_p)
        cp = a.add(prop_p)
        M = g.on_axis(c - d * DUCT_LEN / 2, d)
        ct = root.add(a, M, f"ROV THRUSTER {k + 1}")
        root.joint(f"ROV: Thruster {k + 1} turn", "rotate", [[ct, cp]], c, d, None,
                   {"by": "operator", "note": "the propeller's turn (positive: right-handed about the duct's axis, "
                                              "which points out of the ROV for the horizontal thrusters, up for the "
                                              "vertical ones)"}, motor=True)
        thrusters.append({"centre": c.tolist(), "axis": d.tolist(), "kind": "horizontal" if k < 4 else "vertical"})
    # lights and camera
    lp = Part("ROV LIGHT", light(), STEEL)
    llp = Part("ROV LIGHT LENS", lens(LENS_R, LENS_T), LENS_WHITE)
    lights = []
    for y in (LIGHT_Y, -LIGHT_Y):
        M = g.on_axis((LIGHT_X0, y, LIGHT_Z), (1.0, 0.0, 0.0))
        root.add(lp, M)
        root.add(llp, M @ T(0.0, 0.0, LIGHT_LEN))
        lights.append([LIGHT_X0 + LIGHT_LEN + LENS_T / 2, y, LIGHT_Z])
    cam, Mlens = camera()
    root.add(Part("ROV CAMERA", cam, CAMERA_DARK))
    root.add(Part("ROV CAMERA LENS", lens(50.0, 8.0), GLASS), Mlens)
    cam_pt = (Mlens @ np.r_[0.0, 0.0, 4.0, 1.0])[:3]
    # manipulators (a mirrored pair: two parts of one name)
    for s in (1.0, -1.0):
        root.add(Part("ROV MANIPULATOR", manipulator(s), ARM_GREY))
    term, tip, td = termination()
    root.add(Part("ROV TETHER TERMINATION", term, RESTRICTOR_ORANGE))
    lo, hi = _box(root)
    info = {
        "about": "task 0173: ROV coordinates (mm): origin = the middle of the skids' underside, +x forward (camera and "
                 "lights look along it), +y port, z up. tether: where the tether leaves the bend restrictor and its "
                 "direction (up and aft); camera: the lens centre and its view direction; lights: the lens centres "
                 "(the 'ROV LIGHT LENS' parts glow); box: the ROV's bounding box; size: [L, W, H].",
        "file": FILE, "root": ROOT,
        "tether": {"point": [float(v) for v in tip], "direction": [float(v) for v in td]},
        "camera": {"point": [float(v) for v in cam_pt], "direction": [float(v) for v in Mlens[:3, 2]]},
        "lights": lights,
        "light_direction": [1.0, 0.0, 0.0],
        "thrusters": thrusters,
        "box": [[float(v) for v in lo], [float(v) for v in hi]],
        "size": [float(v) for v in hi - lo],
        "glow": ["ROV LIGHT LENS"],
        "triangles_hint": 0,
    }
    return root, info


def _box(root: Asm) -> tuple[np.ndarray, np.ndarray]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for node, _uid, W, _label, _path in g.walk(root):
        if not isinstance(node, Part):
            continue
        b = Bnd_Box()
        BRepBndLib.AddOptimal_s(g.xform(node.shape, W), b, False, False)
        a, c = b.CornerMin(), b.CornerMax()
        lo, hi = np.minimum(lo, (a.X(), a.Y(), a.Z())), np.maximum(hi, (c.X(), c.Y(), c.Z()))
    return lo, hi
