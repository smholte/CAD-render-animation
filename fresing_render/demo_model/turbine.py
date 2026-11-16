"""The demo's offshore wind turbine (task 0166): an invented turbine on a monopile, sized from the IEA 15 MW reference
turbine's public numbers (IEA Wind TCP Task 37, IEA-15-240-RWT: 240 m rotor, 150 m hub height, 6° shaft tilt,
10 m monopile; the site's turbine of task 0116 is converted from the IEA's own CAD – that file is not used here).

Frame "T" (as ``turbine_parts``): mm, the tower axis = z, sea level (the waterline) z 0, the seabed at
``FIT["seabed_z"]``, the rotor upwind towards -y (compass 180°; compass azimuths: 0 = +y, 90 = +x).

What it is made of:

- ``turbine_parts`` (shared with the site): the transition piece, platform, railings, door, davit, cabinet, ladder,
  boat landing, J-tubes (bell-mouths lifted onto the scour rock, ``JTUBE_BELL_Z``), the scour protection (no boulder
  where J-tube 1's cable comes down, ``CORRIDOR``), the nacelle cover with its cooler, heli-hoist deck, aviation
  lights ("LIGHT 1", "LIGHT 2") and wind sensors, the tower flanges;
- here: the monopile, the tower (its door cut through the wall), the hub with a spinner, the main shaft stub, three
  CLOSED blades with a round root, and four yellow marine lights on the platform's railing ("MARINE LIGHT").

The blades turn CLOCKWISE seen from the front (from upwind): the rotor's joint axis is ``DOWN`` (downwind along the
shaft) and a positive turn about it is clockwise for someone looking downwind; each blade's leading edge leads that
turn (``LE_SIGN`` -1: on the blade frame's -y side, CLAUDE.md section 8). The numbers below are also read by
``tools/site_projects/iea15_standin.py`` (the site converter's test stand-in), so both stay one set.
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from . import occ
from . import turbine_parts as tp
from .geom import Asm, Part, Rot

# ---- the IEA 15 MW public numbers in the T frame (mm); shared with iea15_standin.py ---------------------------------
TILT_DEG = 6.0
HUB = np.array([0.0, -11210.318451936466, 150488.0631820485])          # hub centre: on the shaft axis
UPWIND = np.array([0.0, -math.cos(math.radians(TILT_DEG)), math.sin(math.radians(TILT_DEG))])
DOWN = -UPWIND
HUB_TO_BLADE = 3000.0
BLADE_LENGTH = 117000.0
PREBEND = 4000.0
ROOT_R = 2543.0                   # the blade root's radius
ROOT_WOBBLE, ROOT_OFF = 40.0, (30.0, 50.0)       # the stand-in's not quite round root (the owner's CAD); 0 here
TOWER_TOP = 144582.0
TOWER_WALL = 55.0
TOWER_BASE = 15000.0              # the tower's foot = the transition piece's top = the platform's deck
TOWER_PROFILE = [(-75000.0, 5000.0), (28000.0, 5000.0), (41000.0, 4963.0), (54000.0, 4721.5), (67000.0, 4416.5),
                 (80000.0, 4075.5), (93000.0, 3695.0), (106000.0, 3454.5), (119000.0, 3374.0), (132000.0, 3286.0),
                 (TOWER_TOP, 3250.0)]
RATED_RPM = 7.56                  # IEA-15-240-RWT rated rotor speed

# span stations: (z mm, chord mm, thickness / chord, share of the airfoil (0 round, 1 airfoil), twist deg)
STATIONS = [(0.0, 0.0, 0.0, 0.0, 0.0), (4000.0, 0.0, 0.0, 0.0, 0.0), (20000.0, 5800.0, 0.40, 0.6, 12.0),
            (35000.0, 5500.0, 0.30, 1.0, 8.0), (60000.0, 4500.0, 0.24, 1.0, 3.0), (90000.0, 3000.0, 0.21, 1.0, 0.5),
            (110000.0, 1600.0, 0.20, 1.0, 0.0)]
N_SECTION = 40
LE_SIGN = -1.0                    # the leading edge on the blade frame's -y side: it leads a CLOCKWISE turn (front)


def prebend_x(z: float) -> float:
    """The blade's centre line off its own z axis (towards -x, upwind): 0 to 30 m, then a parabola to -4 m."""
    return -PREBEND * max(0.0, (z - 30000.0) / (BLADE_LENGTH - 30000.0)) ** 2


def section_points(z, chord, tc, share, twist_deg, le_sign=LE_SIGN, flatback=0.0, wobble=ROOT_WOBBLE,
                   off=ROOT_OFF, n=N_SECTION) -> np.ndarray:
    """N points of a section (blade coordinates), starting at the trailing edge: a circle of r ROOT_R (``wobble``
    and ``off``: not quite round, as the stand-in's) blended with a NACA-00xx airfoil whose chord lies along y
    (leading edge at le_sign * 0.3 chord) and thickness along x."""
    th = np.linspace(0.0, 2 * math.pi, n, endpoint=False)
    rr = ROOT_R + wobble * np.cos(2 * th)
    circ = np.c_[rr * np.sin(th) + off[0], -rr * np.cos(th) + off[1]]
    xi = (1.0 + np.cos(th)) / 2.0                         # 1 at the trailing edge (th 0), 0 at the leading edge
    half = 5.0 * tc * chord * (0.2969 * np.sqrt(xi) - 0.126 * xi - 0.3516 * xi ** 2 + 0.2843 * xi ** 3
                               - 0.1036 * xi ** 4)
    half = half + flatback * chord * xi ** 2               # a thick (flat-back) trailing edge
    air = np.c_[np.sign(np.sin(th)) * half, chord * (0.3 - xi)]
    xy = (1.0 - share) * circ + share * air
    xy[:, 1] *= le_sign
    a = math.radians(twist_deg)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    xy = xy @ R.T
    xy[:, 0] += prebend_x(z)
    return np.c_[xy, np.full(len(xy), z)]


# ---- the fit the shared parts are made for (the IEA numbers; iea15_source.fit's keys) ------------------------------
SEABED_Z = -30000.0
FIT = {
    "variant": "offshore",
    "tower_top_z": TOWER_TOP,
    "yaw_bearing_z": [TOWER_TOP, TOWER_TOP + 380.0],
    "rotor": {"point": [float(v) for v in HUB], "direction": [float(v) for v in UPWIND]},
    "msl_z": 0.0, "seabed_z": SEABED_Z, "tower_base_z": TOWER_BASE, "z_shift": 0.0,
    "tower_profile": [[z, r] for z, r in TOWER_PROFILE],
}
PILE_R = 5000.0
PILE_FOOT = 3000.0                # the monopile reaches this far into the seabed (the rest is not drawn)
JTUBE_BELL_Z = 2200.0             # the bell-mouths' open end over the seabed: just over the scour rock
JTUBE_CABLE = 0                   # the J-tube the array cable comes in by (J-TUBE 1)
CORRIDOR = (tp.AZ_JTUBES[JTUBE_CABLE], 2500.0)     # no boulder in this strip of the scour rock (compass az, half width)
SPINNER_R = 3970.0
SHAFT_R, SHAFT_BACK = 1400.0, 9000.0              # the main shaft stub: from the hub back into the nacelle
MARINE_LIGHT_AZ = (45.0, 135.0, 225.0, 315.0)
MARINE_LIGHT_POST = 1500.0        # the lantern's foot over the deck
AVIATION_R = 300.0                # the demo's aviation lights (in place of the site's LIGHT 1, 2): a lantern big enough
#                                   to show as a point of light across the park at night

WHITE = (0.85, 0.86, 0.86)        # RAL 7035-ish: tower, nacelle, blades
YELLOW = (0.93, 0.70, 0.05)       # RAL 1023: the transition piece and what is on it
GREY = (0.45, 0.47, 0.48)
RED = (0.8, 0.05, 0.03)


def tower_radius(z: float) -> float:
    return tp.tower_radius(FIT, z)


def seabed_z() -> float:
    return float(FIT["seabed_z"])


def rock_top(r: float) -> float:
    """The scour rock's surface (T z, mm) at radius r along a vertex of its polygon (J-tube 1's way down)."""
    return tp._bed_height(FIT, r)


def scour_radius() -> float:
    """The scour rock's outer edge (its filter layer, 0.25 m high there)."""
    return float(tp.scour_profile(FIT)[1][0])


def bell(az: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(J-tube's bell-mouth open-end centre, its axis out) in T, for J-tube ``JTUBE_CABLE`` (or the azimuth)."""
    p, d = tp.jtube_bell(FIT, JTUBE_BELL_Z)
    M = tp._az(tp.AZ_JTUBES[JTUBE_CABLE] if az is None else az)
    return (M @ np.r_[p, 1.0])[:3], M[:3, :3] @ d


# ---------------------------------------------------------------------------------------------------------------
# the shapes made here
# ---------------------------------------------------------------------------------------------------------------

def _revolve(outline):
    """A solid of revolution about z: ``outline`` = closed [(z, r)]."""
    return occ.one_solid(g.revolve([(r, z) for z, r in outline]), "revolved")


def monopile():
    return g.cyl(PILE_R, TOWER_BASE - (seabed_z() - PILE_FOOT), (0.0, 0.0, seabed_z() - PILE_FOOT))


def tower():
    """The tower from its foot to the top: flat-faced (``turbine_parts._polygons``, 72 sides: it meshes in two
    triangles per face, a revolved cone of this size in tens of thousands), solid, the door opening cut into it."""
    prof = [(z, r) for z, r in TOWER_PROFILE if z > TOWER_BASE]
    prof = [(TOWER_BASE, tower_radius(TOWER_BASE))] + prof
    solid = tp._polygons([(r, z) for z, r in prof])
    return occ.one_solid(occ.cut(solid, tp.door_cut(FIT, "offshore")), "tower")


SPINNER_NOSE = 5600.0             # the spinner's nose this far upwind of the hub's centre


def spinner():
    """The hub under a spinner: round as the hub at the back, drawn out to a blunt nose upwind (flat-faced rings)."""
    rings = []
    for k in range(1, 12):                                   # the back: a sphere of the hub's size
        a = math.pi * (1.0 - k / 24.0)
        rings.append((SPINNER_R * math.sin(a), SPINNER_R * math.cos(a)))
    for k in range(0, 12):                                   # the front: an ellipse out to the nose
        a = math.pi / 2.0 * (1.0 - k / 12.0)
        rings.append((SPINNER_R * math.sin(a), SPINNER_NOSE * math.cos(a)))
    rings.append((250.0, SPINNER_NOSE))
    return occ.one_solid(occ.moved(tp._polygons(rings), occ.frame(HUB, UPWIND)), "spinner")


def shaft():
    return g.cyl(SHAFT_R, SHAFT_BACK, HUB, DOWN)


TIP = (BLADE_LENGTH - 400.0, 260.0, 0.24, 1.0, 0.0)      # a small last section: the solid's tip (closed flat)
BLADE_STEP = 5000.0               # sections every 5 m along the blade (linear between the stations)
BLADE_POINTS = 48                 # points round a section


def _stations():
    """The stations every BLADE_STEP (and each given one), the numbers linear between them."""
    st = STATIONS + [TIP]
    zs = sorted({z for z, *_ in st} | set(np.arange(0.0, st[-1][0], BLADE_STEP).tolist()))
    cols = np.array(st, float)
    return [tuple([z] + [float(np.interp(z, cols[:, 0], cols[:, k])) for k in range(1, 5)]) for z in zs]


def _sewn(sections):
    """A solid through closed polygons (each (N, 3), the same N, in order): triangles between them (every face a
    true plane: it meshes as it is), the first and last polygons as end caps."""
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeSolid,
                                    BRepBuilderAPI_Sewing)
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    def face(points):
        poly = BRepBuilderAPI_MakePolygon()
        for q in points:
            poly.Add(gp_Pnt(*map(float, q)))
        poly.Close()
        return BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()

    sew = BRepBuilderAPI_Sewing(1e-3)
    n = len(sections[0])
    for a, b in zip(sections[:-1], sections[1:]):
        for k in range(n):
            j = (k + 1) % n
            sew.Add(face([a[k], a[j], b[j]]))
            sew.Add(face([a[k], b[j], b[k]]))
    sew.Add(face(sections[0][::-1]))
    sew.Add(face(sections[-1]))
    sew.Perform()
    ex = TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL)
    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(ex.Current()) if not hasattr(TopoDS, "Shell_s")
                                     else TopoDS.Shell_s(ex.Current())).Solid()
    if occ.volume(solid) < 0:
        solid = solid.Reversed()
    return solid


def blade():
    """One blade in its own frame (z along the blade from the hub's ring, x downwind): a closed, flat-faced solid
    through sections every 5 m (a spline loft meshed in 260 k triangles), a round root (no wobble), the twist
    mirrored with the leading edge (``LE_SIGN``)."""
    secs = [section_points(z, c, tc, share, tw * LE_SIGN, LE_SIGN, 0.0, 0.0, (0.0, 0.0), n=BLADE_POINTS)
            for z, c, tc, share, tw in _stations()]
    return occ.one_solid(_sewn(secs), "blade")


def blade_frame(angle: float) -> np.ndarray:
    """The blade's frame in T for a blade turned ``angle`` degrees (clockwise from the front) from straight up."""
    up = np.array([0.0, 0.0, 1.0])
    up = up - DOWN * (up @ DOWN)
    up /= np.linalg.norm(up)
    R = Rot(DOWN, angle)[:3, :3]
    d = R @ up
    return occ.frame(HUB + HUB_TO_BLADE * d, d, DOWN)


def aviation_light():
    """A red aviation lantern (made at the origin, foot at z 0): a short base and a globe."""
    return occ.one_solid(g.fuse(g.cyl(160.0, 160.0, (0.0, 0.0, 0.0)), g.sphere(AVIATION_R, (0.0, 0.0, 159.0 + AVIATION_R))),
                         "aviation light")


def marine_light():
    """A yellow marine lantern on a short post (made at the origin, foot at z 0)."""
    post = g.cyl(45.0, MARINE_LIGHT_POST, (0.0, 0.0, 0.0))
    body = g.cyl(220.0, 420.0, (0.0, 0.0, MARINE_LIGHT_POST - 1.0))
    cap = g.cone(240.0, 40.0, 140.0, (0.0, 0.0, MARINE_LIGHT_POST + 418.0))
    return occ.one_solid(g.fuse(post, body, cap), "marine light")


# ---------------------------------------------------------------------------------------------------------------
# the parts (made once) and a turbine (an Asm per place; the same Parts, so one mesh each in the app)
# ---------------------------------------------------------------------------------------------------------------

class Kit:
    """Every Part of a turbine, made once: ``fixed`` [(Part, M)], ``nacelle`` [(Part, M)], ``rotor`` [(Part, M)]
    (all M in T at joint values 0)."""

    def __init__(self):
        shared = tp.make(FIT, "offshore", jtube_bell_z=JTUBE_BELL_Z, scour_corridor=CORRIDOR)
        self.fixed, self.nacelle, self.rotor = [], [], []
        eye = np.eye(4)
        aviation = Part("AVIATION LIGHT", aviation_light(), RED)
        for p in shared:
            if p.name.startswith("LIGHT "):                  # the site's small lights: bigger ones in their place
                lo, hi = occ.bbox(p.shape)
                self.nacelle.append((aviation, g.T((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2])))
                continue
            c = _colour(p.name)
            part = Part(p.name, p.shape, c)
            (self.nacelle if p.body == "NACELLE" else self.fixed).append((part, eye))
        self.fixed.append((Part("MONOPILE", monopile(), YELLOW), eye))
        self.fixed.append((Part("TOWER", tower(), WHITE), eye))
        lamp = Part("MARINE LIGHT", marine_light(), YELLOW)
        for az in MARINE_LIGHT_AZ:
            p = tp._radial(az) * (tp.RAIL_R - 260.0) + np.array([0.0, 0.0, tp.deck_z(FIT)])
            self.fixed.append((lamp, g.T(*p)))
        self.rotor.append((Part("SPINNER", spinner(), WHITE), eye))
        self.rotor.append((Part("MAIN SHAFT", shaft(), GREY), eye))
        b = Part("BLADE", blade(), WHITE)
        for k in range(3):
            self.rotor.append((b, blade_frame(120.0 * k)))


def _colour(name: str):
    if name.startswith(("NACELLE", "HELI", "SENSOR", "TOWER FLANGE", "YAW SEAL")):
        return WHITE
    if name.startswith("LIGHT"):
        return RED
    if name.startswith(("SCOUR",)):
        return GREY
    return YELLOW


def turbine(kit: Kit, name: str, turn: float = 0.0, phase: float = 0.0, wind_az: float = 180.0) -> Asm:
    """A turbine named ``name``: its fixed parts turned ``turn`` degrees about the tower axis (counter-clockwise from
    above: J-tube 1 then points to compass az(J-TUBE 1) - turn), the nacelle yawed back so the rotor faces the wind
    from compass ``wind_az`` (180 = from -y, the T frame's own), the rotor turned ``phase`` degrees clockwise (front).
    Joints (in its own coordinates): "Yaw" (the nacelle about the tower axis) and "Rotor" (rides on the yaw; a motor;
    + = clockwise seen from the front)."""
    a = Asm(name)
    R = Rot((0, 0, 1), turn)
    for part, M in kit.fixed:
        a.add(part, R @ M)
    yaw = 180.0 - wind_az                       # compass az grows clockwise; Rot is counter-clockwise from above
    nac = Asm("NACELLE")
    rot = Asm("ROTOR")
    for part, M in kit.nacelle:
        nac.add(part, M)
    for part, M in kit.rotor:
        rot.add(part, M)
    c_rot = nac.add(rot, Rot(DOWN, phase, HUB), "ROTOR")
    c_nac = a.add(nac, Rot((0, 0, 1), yaw), "NACELLE")
    hub = (Rot((0, 0, 1), yaw) @ np.r_[HUB, 1.0])[:3]
    down = Rot((0, 0, 1), yaw)[:3, :3] @ DOWN
    a.joint("Yaw", "rotate", [[c_nac]], (0.0, 0.0, TOWER_TOP), (0.0, 0.0, 1.0))
    a.joint("Rotor", "rotate", [[c_nac, c_rot]], hub, down, rides_on="Yaw", motor=True)
    a.info = {"turn": turn, "phase": phase, "wind_az": wind_az, "hub": hub, "down": down}
    return a
