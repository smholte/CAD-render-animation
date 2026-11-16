"""The demo's vessel (tasks 0076, 0153): hull, superstructure, propulsion and deck outfitting. Invented; generic
features every offshore construction / cable-lay vessel has, nothing of a real vessel or company.

Model coordinates as everywhere in the demo: mm, x to the bow (transom at 0), y to port, z up (waterline 0).

Hull (task 0153): ruled between stations (a smooth loft meshes ~5 x heavier, task 0074), a raked stem with flare,
a bulbous bow, a flat transom with a centre skeg, bilge keels, a sheer forward of the superstructure (the deck aft of it
stays flat at ``deck_z``: everything of the cable-lay spread stands on it). Its paint is split in height: HULL BOTTOM
(antifouling, keel up to ``BOOT_LO``), BOOT TOP (the black band round the waterline), HULL (above it); MAIN DECK is the
top ``DECK_T`` of the hull, so it follows the sheer.

Propulsion: two azimuth thrusters under the stern (a steer joint each, the propeller's turn riding on it) and two bow
tunnel thrusters (openings through the hull, a propeller inside each). The joints are driven by the operator (the
demo's animation turns the propellers; task 0154's water effects read them).

Outfitting: accommodation block with window rows, bridge with wings, funnels, mast with radars, antennas and lights,
lifeboats in davits, railings, a deck crane (slew + luff joints, parked), bollards, fairleads, hatches, windlasses,
hawse pipes and anchors, a rubbing strake (where fenders touch the side), freeing ports in the bulwark, name and
draft-mark boards (the app puts the decals on them).
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from .geom import Asm, Part, Rot, T

# ---- colours (sRGB; the demo's looks replace most of them) --------------------------------------------------
HULL_BLUE = (0.09, 0.17, 0.32)
HULL_RED = (0.55, 0.12, 0.10)
BLACK = (0.05, 0.05, 0.05)
DECK_GREY = (0.42, 0.44, 0.45)
WHITE = (0.93, 0.93, 0.91)
GLASS = (0.10, 0.14, 0.18)
GALV = (0.60, 0.61, 0.62)
ORANGE = (0.95, 0.42, 0.05)
YELLOW = (0.976, 0.659, 0.0)
BRONZE = (0.80, 0.55, 0.35)
LAMP = (1.0, 0.95, 0.8)

DECK_T = 40.0                 # the main deck plate
BOOT_LO, BOOT_HI = -900.0, 700.0     # the boot-top band round the waterline (z)
SHEER = 2000.0                # the deck rises this much at the stem ...
SHEER_LEN = 14000.0           # ... over this length from the bow (the superstructure stands aft of it)
BULWARK_H = 1100.0

# Stations: x (from the stern for the aft ones, from the bow for the forward ones), deck half-breadth, flat-bottom
# half-breadth, keel z, bilge radius. Task 0153: fuller deck forward (flare), a raked stem (the forward stations' keel
# rises above the waterline), the waterline stem a little aft of the deck's.
AFT = [(0, 12600, 7000, -1500, 2600), (4000, 13100, 8800, -3200, 2500), (9000, 13400, 10200, -4800, 2300),
       (15000, 13500, 11000, -5700, 2200), (22000, 13500, 11300, -6000, 2200)]
FORE = [(36000, 13500, 11300, -6000, 2200), (30000, 13450, 10800, -6000, 2400), (24000, 13200, 9200, -6000, 3100),
        (19000, 12800, 7200, -6000, 3800), (15000, 12200, 5200, -5900, 4300), (11500, 11300, 3300, -5700, 4500),
        (8500, 10000, 1800, -5400, 4300), (6000, 8500, 900, -5000, 3900), (4000, 7000, 400, -4600, 3300),
        (2500, 5400, 150, -3900, 2600), (1300, 3700, 60, -2400, 1800), (500, 2200, 40, -700, 1000),
        (0, 900, 20, 1200, 400)]

# propulsion (mm)
AZ_X = 5500.0                 # the azimuth thrusters' steering axes ...
AZ_Y = 6500.0                 # ... this far either side of the centre line (scaled with the beam)
AZ_PROP_R = 1580.0            # their propellers (the nozzle's inside: + 60)
AZ_POD_DROP = 2030.0          # the pod's axis under the housing's underside
BOW_TUNNELS = (9500.0, 12500.0)    # the bow tunnel thrusters: distance of their axes from the bow
BOW_Z = -3200.0
BOW_TUNNEL_R = 1000.0
BOW_PROP_R = 880.0

# superstructure (from the bow)
HOUSE_AFT = 29000.0           # the accommodation's aft face this far from the bow
HOUSE_FWD = 14000.0           # its front (the sheer starts here)
TIER_H = 2800.0

# deck crane (port side, forward of the carousel well), parked with its boom up and forward
CRANE_X_FROM_BOW = 40000.0
CRANE_Y = 10300.0
CRANE_BOOM = 22000.0
CRANE_LUFF = 70.0             # the boom's angle above the horizontal as modelled (joint value 0)

RADAR_Y = 2600.0              # the two radars this far either side of the mast (scanners 3.8 m and 2.6 m long)
NAME = "DEMO LAYER"           # the invented name on the name boards (the app writes it as decals)


def sheer(x: float, L: float) -> float:
    """How far the deck lies above ``deck_z`` at x (0 aft of the sheer, ``SHEER`` at the stem)."""
    s = (x - (L - SHEER_LEN)) / SHEER_LEN
    return SHEER * s * s if s > 0 else 0.0


def stations(p, L: float) -> list:
    """(x, deck half-breadth, bottom half-breadth, keel z, bilge r, deck z) of every station; half-breadths scaled
    when the beam grows (a thick cable needs wider lanes)."""
    f = p.beam / 27000.0
    out = [(s[0], s[1] * f, s[2] * f, s[3], s[4]) for s in AFT]
    out += [(L - s[0], s[1] * f, s[2] * f, s[3], s[4]) for s in FORE]
    return [s + (p.deck_z + sheer(s[0], L),) for s in out]


def _tangent_point(c, r, d):
    dx, dz = d[0] - c[0], d[1] - c[1]
    L = math.hypot(dx, dz)
    a = math.atan2(dz, dx)
    b = math.acos(r / L)
    ang = a - b
    return (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)), ang


def _section(x, bd, bb, k, r, deck):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle
    c = (bb, k + r)
    (ty, tz), ang = _tangent_point(c, r, (bd, deck))
    mid = -math.pi / 2 + 0.5 * (ang + math.pi / 2)
    pt = lambda y, z: g.gp_Pnt(x, y, z)  # noqa: E731
    e = [BRepBuilderAPI_MakeEdge(pt(-bd, deck), pt(bd, deck)).Edge(),
         BRepBuilderAPI_MakeEdge(pt(bd, deck), pt(ty, tz)).Edge(),
         BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(pt(ty, tz), pt(bb + r * math.cos(mid), k + r + r * math.sin(mid)),
                                                    pt(bb, k)).Value()).Edge(),
         BRepBuilderAPI_MakeEdge(pt(bb, k), pt(-bb, k)).Edge(),
         BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(pt(-bb, k), pt(-(bb + r * math.cos(mid)),
                                                                     k + r + r * math.sin(mid)),
                                                    pt(-ty, tz)).Value()).Edge(),
         BRepBuilderAPI_MakeEdge(pt(-ty, tz), pt(-bd, deck)).Edge()]
    w = BRepBuilderAPI_MakeWire()
    for ed in e:
        w.Add(ed)
    return w.Wire()


def offset_polygon(pts, d):
    """Inward miter offset of a convex polygon given anticlockwise."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = np.asarray(pts[i], float), np.asarray(pts[(i + 1) % n], float)
        t = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-t[1], t[0]])                 # inward for anticlockwise
        lines.append((a + d * nrm, t))
    out = []
    for i in range(n):
        (p1, t1), (p2, t2) = lines[i - 1], lines[i]
        A = np.array([t1, -t2]).T
        if abs(np.linalg.det(A)) < 1e-9:              # straight on: the offset point itself
            out.append(tuple(p2))
            continue
        s = np.linalg.solve(A, p2 - p1)
        out.append(tuple(p1 + s[0] * t1))
    return out


def hull_solid(p, L: float):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    loft = BRepOffsetAPI_ThruSections(True, True, 1e-6)
    for s in stations(p, L):
        loft.AddWire(_section(*s))
    loft.CheckCompatibility(False)
    loft.Build()
    return loft.Shape()


def side_hit(shape, x: float, z: float, side: int = -1) -> float:
    """y where a line along y at (x, z) first meets ``shape`` from outside on that side (−1 starboard, +1 port)."""
    from OCP.gp import gp_Lin
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    si = IntCurvesFace_ShapeIntersector()
    si.Load(shape, 1e-3)
    si.Perform(gp_Lin(g.P((x, side * 1e6, z)), g.D((0.0, -side, 0.0))), 0.0, 2e6)
    if si.NbPnt() < 1:
        raise ValueError(f"nothing of the hull at x={x:.0f}, z={z:.0f}")
    return min((si.Pnt(i + 1).Y() for i in range(si.NbPnt())), key=lambda y: -side * y)


def side_point(hull, x: float, z: float, side: int, dx: float = 300.0, dz: float = 300.0):
    """The hull's side at (x, z): (point, outward normal, along (forward), up the side), all unit but the point."""
    y = side_hit(hull, x, z, side)
    t = np.array([2 * dx, side_hit(hull, x + dx, z, side) - side_hit(hull, x - dx, z, side), 0.0])
    u = np.array([0.0, side_hit(hull, x, z + dz, side) - side_hit(hull, x, z - dz, side), 2 * dz])
    n = np.cross(t, u)
    n /= np.linalg.norm(n)
    if n[1] * side < 0:
        n = -n
    t /= np.linalg.norm(t)
    u = np.cross(n, t) * (1.0 if side > 0 else -1.0)
    u = u if u[2] > 0 else -u
    return np.array([x, y, z]), n, t, u


def side_frame(hull, x: float, z: float, side: int, out: float = 0.0) -> np.ndarray:
    """A frame on the hull's side at (x, z): local z = outward normal, local x = forward along the side; its origin
    ``out`` mm outside the surface."""
    q, n, t, _u = side_point(hull, x, z, side)
    return g.Frame(q + out * n, t, n)


# ---------------------------------------------------------------------------------------------------------
# propellers and thrusters
# ---------------------------------------------------------------------------------------------------------


def _ellipse_wire(centre, normal, major_dir, a: float, b: float):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.gp import gp_Ax2, gp_Elips
    ax = gp_Ax2(g.P(centre), g.D(normal), g.D(major_dir))
    e = BRepBuilderAPI_MakeEdge(gp_Elips(ax, float(a), float(b))).Edge()
    return BRepBuilderAPI_MakeWire(e).Wire()


def propeller_shape(R: float, hub_r: float, hub_len: float, blades: int = 4, pitch: float = 2.4):
    """A propeller about local +z (its hub from z = 0 to hub_len): twisted blades (elliptic sections, lofted) with a
    pitch of ``pitch`` x R, wide at 0.6 R, rounded at the tip."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    zc = 0.5 * hub_len
    P = pitch * R
    hub = g.fuse(g.cyl(hub_r, hub_len), g.cone(hub_r, 0.35 * hub_r, 0.6 * hub_r, (0, 0, hub_len)))
    pieces = [hub]
    for k in range(blades):
        th = 2 * math.pi * k / blades
        radial = np.array([math.cos(th), math.sin(th), 0.0])
        tang = np.array([-math.sin(th), math.cos(th), 0.0])
        ts = BRepOffsetAPI_ThruSections(True, False, 1e-6)
        for s in (0.0, 0.3, 0.6, 0.85, 1.0):
            r = hub_r * 0.8 + s * (R - hub_r * 0.8)
            chord = (0.55 + 1.1 * s - 1.3 * s * s) * R * 0.55 if s < 1.0 else 0.18 * R
            thick = (0.10 - 0.075 * s) * R * 0.6
            phi = math.atan2(P, 2 * math.pi * max(r, 1.0))           # blade angle from the plane of the disc
            major = math.cos(phi) * tang + math.sin(phi) * np.array([0.0, 0.0, 1.0])
            ts.AddWire(_ellipse_wire(radial * r + [0, 0, zc], radial, major, 0.5 * chord, max(thick, 6.0)))
        ts.CheckCompatibility(False)
        ts.Build()
        pieces.append(ts.Shape())
    return g.fuse(*pieces)


def _stadium(length: float, width: float, h: float, m=None):
    """A prism of a stadium outline (round ends) along local x, extruded along z."""
    a, w = length / 2 - width / 2, width / 2
    prof = [(-a, -w), (a, -w), ("arc", (a + w, 0.0), (a, w)), (-a, w), ("arc", (-a - w, 0.0), (-a, -w))]
    return g.prism(prof, h, m)


def azimuth_thruster(kit) -> Asm:
    """An azimuth thruster under the hull; local origin on its steering axis at the housing's underside, local x
    forward (the propeller pushes aft), z up. Joints: Steer (about z) and Propeller turn (rides on Steer)."""
    a = Asm("AZIMUTH THRUSTER")
    R = AZ_PROP_R
    zp = -AZ_POD_DROP
    housing = g.fuse(g.cyl(1400.0, 1500.0, (0, 0, 0)), g.cyl(1550.0, 120.0, (0, 0, 0)))
    a.add(Part("THRUSTER HOUSING", housing, HULL_RED))
    steer = Asm("STEERING UNIT")
    strut = _stadium(1700.0, 640.0, AZ_POD_DROP - 30.0, T(-150.0, 0.0, zp))
    steer.add(Part("THRUSTER STRUT", g.fuse(strut, g.cyl(1150.0, 120.0, (0, 0, -150.0))), HULL_RED))
    pod = g.revolve([(0.0, 0.0), (420.0, 0.0), (700.0, 500.0), (700.0, 2400.0), (560.0, 3000.0), (0.0, 3000.0)],
                    (1600.0, 0.0, zp), (-1.0, 0.0, 0.0))                 # nose forward at x = 1600, tail at -1400
    steer.add(Part("THRUSTER POD", pod, HULL_RED))
    ri = R + 60.0
    noz_prof = [(ri, 0.0), (ri + 330.0, 0.0), (ri + 200.0, 1500.0), (ri, 1500.0)]
    nozzle = g.revolve(noz_prof, (-1000.0, 0.0, zp), (-1.0, 0.0, 0.0))     # x = -1000 … -2500
    stators = [g.xform(g.box(-1350.0, -40.0, 650.0, 300.0, 80.0, ri - 650.0 + 40.0),
                       T(0, 0, zp) @ Rot((1, 0, 0), 120.0 * k)) for k in range(3)]
    steer.add(Part("THRUSTER NOZZLE", g.fuse(nozzle, *stators), HULL_RED))
    prop = kit.get(("propeller", R), lambda: Part("PROPELLER", propeller_shape(R, 450.0, 650.0), BRONZE))
    cp = steer.add(prop, g.Frame((-1450.0, 0.0, zp), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0)))
    cs = a.add(steer)
    a.joint("Steer", "rotate", [cs], (0, 0, 0), (0, 0, 1), None,
            {"by": "operator", "note": "turns the thruster about its vertical axis (0 = pushing aft, the vessel ahead)"},
            motor=True)
    a.joint("Propeller turn", "rotate", [[cs, cp]], (0, 0, zp), (-1, 0, 0), None,
            {"by": "operator", "note": "the propeller's turn (positive: pushing aft)"}, rides_on="Steer", motor=True)
    a.info.update(prop_r=R, pod_z=zp, prop_x=-1450.0, nozzle_r=ri + 330.0)
    return a


def tunnel_thruster(kit, half: float) -> Asm:
    """A bow tunnel thruster: local origin on the tunnel's axis (local y = across the vessel). The tunnel itself is cut
    into the hull; this is its lining, the gearbox on a strut from the tunnel's top and the propeller."""
    a = Asm("BOW THRUSTER")
    Rt = BOW_TUNNEL_R
    a.add(Part("THRUSTER TUNNEL", g.tube(Rt, Rt - 30.0, 2 * half, (0, -half, 0), (0, 1, 0)), HULL_RED))
    box_ = g.revolve([(0.0, 0.0), (300.0, 0.0), (380.0, 250.0), (380.0, 1150.0), (300.0, 1400.0), (0.0, 1400.0)],
                     (0, -800.0, 0), (0, 1, 0))                          # y = -800 … 600
    strut = _stadium(700.0, 220.0, Rt - 300.0, T(0, -100.0, 300.0))
    a.add(Part("TUNNEL GEARBOX", g.fuse(box_, strut), HULL_RED))
    prop = kit.get(("propeller", BOW_PROP_R), lambda: Part("PROPELLER", propeller_shape(BOW_PROP_R, 280.0, 420.0),
                                                           BRONZE))
    cp = a.add(prop, g.Frame((0, 650.0, 0), (1.0, 0.0, 0.0), (0, 1, 0)))
    a.joint("Propeller turn", "rotate", [cp], (0, 0, 0), (0, 1, 0), None,
            {"by": "operator", "note": "the bow thruster's propeller (positive pushes water to port: the bow to stb)"},
            motor=True)
    return a


# ---------------------------------------------------------------------------------------------------------
# superstructure and outfitting
# ---------------------------------------------------------------------------------------------------------


def railing(points, h: float = 1000.0, post_step: float = 1500.0):
    """A railing along a polyline at its own height: square posts, a top rail and a knee rail (one solid; boxes only:
    round bars made the booleans ten times slower)."""
    pts = [np.asarray(q, float) for q in points]
    parts = []
    for a, b in zip(pts[:-1], pts[1:]):
        L = float(np.linalg.norm(b - a))
        n = max(1, int(math.ceil(L / post_step)))
        for k in range(n + 1):
            q = a + (b - a) * k / n
            parts.append(g.box(q[0] - 25.0, q[1] - 25.0, q[2], 50.0, 50.0, h))
        d = (b - a) / L
        parts.append(g.beam(a - 25.0 * d + [0, 0, h - 25.0], b + 25.0 * d + [0, 0, h - 25.0], 60.0, 50.0))
        parts.append(g.beam(a + [0, 0, 0.5 * h], b + [0, 0, 0.5 * h], 40.0, 40.0))
    return g.fuse(*parts)


def _window_cuts(x0, x1, y_face, side, z0, w=900.0, h=1000.0, step=1800.0, depth=150.0, sill=1000.0):
    """Boxes that cut a row of windows into a wall at y = y_face (its outside towards ``side``)."""
    n = int((x1 - x0 - 600.0) // step)
    xs = [x0 + 0.5 * (x1 - x0) + (k - (n - 1) / 2) * step for k in range(n)]
    yb = y_face - depth if side > 0 else y_face - 10.0
    return [g.box(x - w / 2, yb, z0 + sill, w, depth + 10.0, h) for x in xs], xs


def _front_cuts(y0, y1, x_face, z0, w=900.0, h=1000.0, step=1800.0, depth=150.0, sill=1000.0):
    n = int((y1 - y0 - 600.0) // step)
    ys = [y0 + 0.5 * (y1 - y0) + (k - (n - 1) / 2) * step for k in range(n)]
    return [g.box(x_face - depth, y - w / 2, z0 + sill, depth + 10.0, w, h) for y in ys]


def superstructure(p, L: float) -> tuple[Asm, dict]:
    """Accommodation block (three tiers with window rows), bridge with wings, funnels, mast; railings."""
    a = Asm("SUPERSTRUCTURE")
    xa, xf = L - HOUSE_AFT, L - HOUSE_FWD
    z = p.deck_z
    tiers = [(xa, xf, 9000.0), (xa + 500.0, xf - 500.0, 7800.0), (xa + 1500.0, xf - 1000.0, 7800.0)]
    blocks, cuts, glass = [], [], []
    for k, (x0, x1, hw) in enumerate(tiers):
        z0 = z + k * TIER_H
        blocks.append(g.box(x0, -hw, z0, x1 - x0, 2 * hw, TIER_H))
        for side in (-1, 1):
            c, _xs = _window_cuts(x0, x1, side * hw, side, z0)
            cuts += c
            yg = side * (hw - 120.0) - (20.0 if side > 0 else 0.0)
            glass.append(g.box(x0 + 300.0, yg, z0 + 1000.0, x1 - x0 - 600.0, 20.0, 1000.0))
        cuts += _front_cuts(-hw, hw, x1, z0)
        glass.append(g.box(x1 - 140.0, -hw + 300.0, z0 + 1000.0, 20.0, 2 * hw - 600.0, 1000.0))
    # the bridge on top, its front over the tiers, wings out to the sides
    zb = z + 3 * TIER_H
    bx0, bx1 = xf - 6500.0, xf + 500.0
    f = p.beam / 27000.0
    wing = 12000.0 * f
    bridge = g.fuse(g.box(bx0, -7500.0, zb, bx1 - bx0, 15000.0, TIER_H),
                    g.box(bx1 - 3000.0, -wing, zb, 3000.0, 2 * wing, TIER_H))
    bcuts = [g.box(bx1 - 150.0, y - 650.0, zb + 900.0, 160.0, 1300.0, 1400.0)
             for y in np.arange(-wing + 1000.0, wing - 999.0, 1500.0)]
    for side in (-1, 1):
        bcuts += [g.box(x - 650.0, side * wing - (150.0 if side > 0 else 10.0), zb + 900.0, 1300.0, 160.0, 1400.0)
                  for x in (bx1 - 2250.0, bx1 - 750.0)]
    bridge = g.cut(bridge, *bcuts)
    a.add(Part("BRIDGE", bridge, WHITE))
    bglass = [g.box(bx1 - 130.0, -wing + 200.0, zb + 900.0, 20.0, 2 * wing - 400.0, 1400.0)]
    bglass += [g.box(bx1 - 2950.0, side * (wing - 130.0) - (20.0 if side > 0 else 0.0), zb + 900.0, 2900.0, 20.0,
                     1400.0) for side in (-1, 1)]
    for gl in bglass:
        a.add(Part("BRIDGE WINDOW", gl, GLASS))
    house = g.cut(g.fuse(*blocks), *cuts)
    a.add(Part("ACCOMMODATION", house, WHITE))
    for gl in glass:
        a.add(Part("WINDOW", gl, GLASS))
    # funnels on the top tier, aft
    zt = z + 3 * TIER_H
    for side in (-1, 1):
        fx, fy = xa + 3500.0, side * 4500.0
        body = _stadium(3000.0, 1600.0, 4300.0, T(fx, fy, zt))
        a.add(Part("FUNNEL", body, WHITE))
        a.add(Part("FUNNEL TOP", g.fuse(_stadium(3080.0, 1680.0, 900.0, T(fx, fy, zt + 4300.0)),
                                        g.rod((fx + 600.0, fy, zt + 5000.0), (fx + 600.0, fy, zt + 5600.0), 280.0),
                                        g.rod((fx - 600.0, fy, zt + 5000.0), (fx - 600.0, fy, zt + 5600.0), 280.0)),
                   BLACK))
    # mast on the bridge roof, radars on its platform, antennas and lights on top
    zr = zb + TIER_H
    mx = bx0 + 3500.0
    mast = g.fuse(g.rod((mx, 0, zr), (mx, 0, zr + 9500.0), 260.0),
                  g.rod((mx - 1600.0, -1800.0, zr), (mx, 0, zr + 4200.0), 120.0),
                  g.rod((mx - 1600.0, 1800.0, zr), (mx, 0, zr + 4200.0), 120.0),
                  g.box(mx - 900.0, -3000.0, zr + 4200.0, 1800.0, 6000.0, 120.0),
                  g.rod((mx, -3200.0, zr + 7000.0), (mx, 3200.0, zr + 7000.0), 90.0))
    a.add(Part("MAST", mast, WHITE))
    radars = []
    for k, ry in enumerate((-RADAR_Y, RADAR_Y)):       # their sweep clear of the mast's pole (r 260)
        a.add(Part("RADAR PEDESTAL", g.cyl(220.0, 450.0, (mx, ry, zr + 4320.0)), WHITE))
        sc = a.add(Part("RADAR SCANNER", g.fuse(g.box(-1900.0 + 600.0 * k, -110.0, 0.0, 3800.0 - 1200.0 * k, 220.0,
                                                      260.0),
                                                g.cyl(160.0, 120.0, (0.0, 0.0, -120.0))), WHITE),
                   T(mx, ry, zr + 4900.0))
        radars.append((sc, (mx, ry, zr + 4900.0)))
    ant = [g.rod((mx + 300.0 * s, s * 2800.0, zr + 7000.0), (mx + 300.0 * s, s * 2800.0, zr + 9300.0), 25.0)
           for s in (-1, 1)]
    ant += [g.rod((mx, 0, zr + 9500.0), (mx, 0, zr + 11500.0), 30.0)]
    for an in ant:
        a.add(Part("ANTENNA", an, GALV))
    lights = [g.cyl(120.0, 260.0, (mx, 0, zr + 9300.0))]
    lights += [g.cyl(100.0, 220.0, (bx1 - 1500.0, s * (wing - 300.0), zb + TIER_H)) for s in (-1, 1)]
    for li in lights:
        a.add(Part("MAST LIGHT", li, LAMP))
    for k, (sc, c) in enumerate(radars):
        a.joint(f"Radar {k + 1} turn", "rotate", [sc], c, (0, 0, -1), None,
                {"by": "operator", "note": "the radar scanner turns clockwise seen from above"}, motor=True)
    # railings: round the first tier's roof (walkways beside the second tier), the top tier's roof, the bridge roof
    rails = []
    hw1 = 9000.0 - 60.0
    rails.append([(xa + 60.0, -hw1, z + TIER_H), (xf - 60.0, -hw1, z + TIER_H)])
    rails.append([(xa + 60.0, hw1, z + TIER_H), (xf - 60.0, hw1, z + TIER_H)])
    rails.append([(xa + 60.0, -hw1, z + TIER_H), (xa + 60.0, hw1, z + TIER_H)])
    t3 = tiers[2]
    rails.append([(bx0 - 60.0, -t3[2] + 60.0, zt), (t3[0] + 60.0, -t3[2] + 60.0, zt), (t3[0] + 60.0, t3[2] - 60.0, zt),
                  (bx0 - 60.0, t3[2] - 60.0, zt)])
    rails.append([(bx0 + 60.0, -7440.0, zr), (bx1 - 3000.0, -7440.0, zr), (bx1 - 3000.0, -wing + 60.0, zr),
                  (bx1 - 60.0, -wing + 60.0, zr), (bx1 - 60.0, wing - 60.0, zr), (bx1 - 3000.0, wing - 60.0, zr),
                  (bx1 - 3000.0, 7440.0, zr), (bx0 + 60.0, 7440.0, zr), (bx0 + 60.0, -7440.0, zr)])
    for r in rails:
        a.add(Part("RAILING", railing(r), GALV))
    info = {"aft": xa, "front": xf, "bridge": [bx0, bx1], "wing": wing, "roof_z": zr, "top_z": zr + 11500.0}
    return a, info


def lifeboat_shape(length: float = 7500.0, beam: float = 2600.0, height: float = 2900.0):
    """An enclosed lifeboat about local x (centred), its keel at z = 0."""
    secs = []
    for s, wf, hf in ((-0.5, 0.25, 0.75), (-0.42, 0.75, 0.95), (-0.2, 1.0, 1.0), (0.2, 1.0, 1.0), (0.4, 0.75, 0.95),
                      (0.5, 0.15, 0.7)):
        x = s * length
        w, h = 0.5 * beam * wf, height * hf
        secs.append([(x, -0.35 * w, 0.0), (x, -w, 0.45 * h), (x, -0.85 * w, 0.8 * h), (x, -0.45 * w, h),
                     (x, 0.45 * w, h), (x, 0.85 * w, 0.8 * h), (x, w, 0.45 * h), (x, 0.35 * w, 0.0)])
    return g.loft(secs, ruled=True)


def davit(y_post: float, y_arm: float, z0: float, z_top: float) -> object:
    """A davit: a post from the deck at y_post up to z_top, an arm out to y_arm, its fall down 800 (one solid)."""
    s = 1.0 if y_arm > y_post else -1.0
    return g.fuse(g.box(-150.0, y_post - 150.0, z0, 300.0, 300.0, z_top - z0),
                  g.beam((0.0, y_post, z_top - 150.0), (0.0, y_arm + s * 150.0, z_top - 150.0), 260.0, 300.0),
                  g.rod((0.0, y_arm, z_top - 300.0), (0.0, y_arm, z_top - 1100.0), 25.0))


def deck_crane() -> Asm:
    """Knuckle-free offshore deck crane: pedestal, slewing house with cab, box boom with its hook block stowed at the
    tip. Local origin on the slewing axis at the deck; the boom points along +x at ``CRANE_LUFF`` degrees."""
    a = Asm("DECK CRANE")
    a.add(Part("CRANE PEDESTAL", g.fuse(g.cyl(1300.0, 3200.0), g.cyl(1550.0, 150.0, (0, 0, 3050.0))), YELLOW))
    slew = Asm("CRANE SLEWING HOUSE")
    zs = 3230.0
    slew.add(Part("CRANE HOUSE", g.fuse(g.cyl(1500.0, 300.0, (0, 0, zs)), g.box(-2600.0, -1300.0, zs + 300.0, 3600.0,
                                                                                 2600.0, 2400.0),
                                        g.box(-200.0, -1200.0, zs + 2700.0, 1400.0, 300.0, 800.0),
                                        g.box(-200.0, 900.0, zs + 2700.0, 1400.0, 300.0, 800.0)), YELLOW))
    slew.add(Part("CRANE CAB", g.box(-600.0, -2600.0, zs + 300.0, 2000.0, 1250.0, 2200.0), WHITE))
    slew.add(Part("CAB WINDOW", g.box(1390.0, -2500.0, zs + 1200.0, 30.0, 1050.0, 1100.0), GLASS))
    pin = np.array([700.0, 0.0, zs + 3200.0])
    boom = Asm("CRANE BOOM")
    L = CRANE_BOOM
    tip = np.array([L, 0.0, 0.0])
    bshape = g.fuse(g.beam((0.0, -800.0, 0.0), tip + [0, -250.0, 0], 350.0, 500.0),
                    g.beam((0.0, 800.0, 0.0), tip + [0, 250.0, 0], 350.0, 500.0),
                    g.rod((0.0, -1000.0, 0.0), (0.0, 1000.0, 0.0), 200.0),
                    *[g.beam((x, -800.0 + 550.0 * x / L, 0.0), (x, 800.0 - 550.0 * x / L, 0.0), 160.0, 300.0)
                      for x in np.linspace(1500.0, L - 800.0, 8)],
                    g.box(L - 700.0, -450.0, -400.0, 1000.0, 900.0, 800.0))
    boom.add(Part("CRANE BOOM", bshape, YELLOW))
    boom.add(Part("HOOK BLOCK", g.fuse(g.box(-350.0, -250.0, -1500.0, 700.0, 500.0, 900.0),
                                       g.rod((0, 0, -1500.0), (0, 0, -2100.0), 120.0)), ORANGE),
             T(*(tip + [0.0, 0.0, -400.0])) @ Rot((0, 1, 0), CRANE_LUFF))
    cb = slew.add(boom, T(*pin) @ Rot((0, 1, 0), -CRANE_LUFF))
    cs = a.add(slew)
    a.joint("Slew", "rotate", [cs], (0, 0, 0), (0, 0, 1), None,
            {"by": "operator", "note": "slews the crane (parked: the boom forward)"}, motor=True)
    a.joint("Luff", "rotate", [[cs, cb]], pin, (0, -1, 0), [-55.0, 10.0],
            {"by": "operator", "note": f"luffs the boom (0 = parked at {CRANE_LUFF:.0f}° up; negative lowers it)"},
            rides_on="Slew")
    a.info["tip_z"] = float(pin[2] + L * math.sin(math.radians(CRANE_LUFF)))
    return a


def bollard() -> Part:
    return Part("BOLLARD", g.fuse(g.box(-900.0, -400.0, 0.0, 1800.0, 800.0, 60.0),
                                  *[g.fuse(g.cyl(210.0, 650.0, (x, 0, 60.0)), g.cyl(280.0, 60.0, (x, 0, 710.0)))
                                    for x in (-450.0, 450.0)]), BLACK)


def fairlead_shape():
    """A closed (Panama) fairlead set in the bulwark: an oval ring along local y (through the bulwark)."""
    outer = _stadium(1000.0, 650.0, 400.0, g.Frame((0, -200.0, 0), (1, 0, 0), (0, 1, 0)))
    inner = _stadium(700.0, 350.0, 420.0, g.Frame((0, -210.0, 0), (1, 0, 0), (0, 1, 0)))
    return g.cut(outer, inner)


def anchor_shape():
    """A stockless anchor hanging shank up along local z (its crown at z = 0), flukes along local x."""
    shank = g.box(-110.0, -90.0, 0.0, 220.0, 180.0, 2200.0)
    crown = g.box(-500.0, -160.0, -100.0, 1000.0, 320.0, 450.0)
    flukes = [g.loft([[(sx * 400.0, -120.0, 300.0), (sx * 650.0, -120.0, 300.0), (sx * 650.0, 120.0, 300.0),
                       (sx * 400.0, 120.0, 300.0)],
                      [(sx * 420.0, -60.0, 1300.0), (sx * 480.0, -60.0, 1300.0), (sx * 480.0, 60.0, 1300.0),
                       (sx * 420.0, 60.0, 1300.0)]]) for sx in (-1, 1)]
    ring = g.tube(200.0, 110.0, 120.0, (0, -60.0, 2350.0), (0, 1, 0))
    return g.fuse(shank, crown, *flukes, ring)


def windlass() -> Part:
    """An anchor windlass: base, gypsy wheel about local y, brake drum, motor."""
    return Part("WINDLASS", g.fuse(g.box(-900.0, -700.0, 0.0, 1800.0, 1400.0, 300.0),
                                   g.box(-700.0, -600.0, 300.0, 300.0, 1200.0, 900.0),
                                   g.box(400.0, -600.0, 300.0, 300.0, 1200.0, 900.0),
                                   g.cyl(650.0, 400.0, (0, -200.0, 1100.0), (0, 1, 0)),
                                   g.cyl(450.0, 900.0, (0, -1300.0, 1100.0), (0, 1, 0)),
                                   g.cyl(350.0, 900.0, (0, 0, 1100.0), (0, 1, 0))), BLACK)


# ---------------------------------------------------------------------------------------------------------
# the vessel
# ---------------------------------------------------------------------------------------------------------


def vessel(p, pos, kit=None) -> Asm:
    """The whole vessel as one assembly (its own file ``demo_vessel.step`` too). ``info``: the deck outline, the hull's
    stations, the outfitting's boxes (the tests check they keep clear of the cable-lay spread)."""
    from .machines import Kit
    kit = kit or Kit(p)
    L = pos["length"]
    st = stations(p, L)
    f = p.beam / 27000.0
    hull = hull_solid(p, L)
    big = 4 * L
    well_r = p.carousel_d / 2 + 900.0
    well_floor = -700.0
    well = g.cyl(well_r, p.deck_z - well_floor + 4000, (pos["carousel_x"], 0, well_floor))
    zone = lambda z0, z1: g.box(-L, -big / 2, z0, 3 * L, big, z1 - z0)  # noqa: E731
    # the hull's top is plane between stations (two level lines): bands that follow it, sampled at the stations
    xs_st = [-L] + [s[0] for s in st] + [2 * L]
    top_at = [p.deck_z + sheer(max(0.0, min(x, L)), L) for x in xs_st]

    def band(lo: float, hi: float, lo_abs: float | None = None):
        """Everything between (deck − lo) and (deck + hi) along the sheer; ``lo_abs``: a level bottom instead."""
        prof = [(x, lo_abs if lo_abs is not None else z - lo) for x, z in zip(xs_st, top_at)]
        prof += [(x, z + hi) for x, z in reversed(list(zip(xs_st, top_at)))]
        return g.polygon_prism(prof, 2 * big, g.Frame((0, big, 0), (1, 0, 0), (0, -1, 0)))
    # bulbous bow: a round nose under the stem, its aft end inside the hull
    bz, br = -3300.0, 1500.0 * min(1.0, f)
    bx0, bx1 = L - 10000.0, L - 400.0
    nose = 2500.0
    prof = [(0.0, 0.0), (br, 0.0), (br, bx1 - bx0 - nose)]
    prof += [(br * math.cos(t), bx1 - bx0 - nose + nose * math.sin(t)) for t in np.linspace(0.25, 1.3, 5)]
    prof += [(0.0, bx1 - bx0)]
    bulb = g.revolve(prof, (bx0, 0.0, bz), (1.0, 0.0, 0.0))
    tunnels = [g.cyl(BOW_TUNNEL_R, 4 * p.beam, (L - xb, -2 * p.beam, BOW_Z), (0, 1, 0)) for xb in BOW_TUNNELS]
    a = Asm("VESSEL")
    bottom = g.cut(g.fuse(g.common(hull, zone(-big, BOOT_LO)), g.cut(bulb, zone(BOOT_LO, big))), well, *tunnels)
    boot = g.cut(g.common(hull, zone(BOOT_LO, BOOT_HI)), well)
    top = g.cut(g.common(hull, band(DECK_T, -DECK_T, lo_abs=BOOT_HI)), well)
    deck = g.cut(g.common(hull, band(DECK_T, 500.0)), well)
    inner = g.common(hull, band(0.0, -DECK_T, lo_abs=-big))        # the hull without its deck plate
    a.add(Part("HULL BOTTOM", bottom, HULL_RED))
    a.add(Part("BOOT TOP", boot, BLACK))
    a.add(Part("HULL", top, HULL_BLUE))
    a.add(Part("MAIN DECK", deck, DECK_GREY))
    # well lining (grey) so the well does not show the hull's colours
    lining = g.fuse(g.tube(well_r + 1.0, well_r - 30.0, p.deck_z - well_floor, (pos["carousel_x"], 0, well_floor)),
                    g.cyl(well_r - 30.0, 30.0, (pos["carousel_x"], 0, well_floor)))
    a.add(Part("CAROUSEL WELL", lining, DECK_GREY))
    # skeg on the centre line aft, bilge keels along the bilges amidships
    skeg_prof = [(800.0, -1600.0), (14000.0, -5700.0), (14000.0, -6100.0), (9000.0, -6100.0), (2500.0, -4200.0),
                 (800.0, -2600.0)]
    skeg = g.polygon_prism(skeg_prof, 600.0, g.Frame((0, 300.0, 0), (1, 0, 0), (0, -1, 0)))
    a.add(Part("SKEG", g.cut(skeg, g.xform(hull, T(0, 0, 300.0))), HULL_RED))      # 300 into the hull
    s45 = 1 / math.sqrt(2)
    for side in (-1, 1):
        n = np.array([0.0, side * s45, -s45])
        c0 = np.array([0.0, side * 11300.0 * f, -6000.0 + 2200.0]) + 2200.0 * n       # the bilge's 45° point
        a.add(Part("BILGE KEEL", g.beam(c0 + [24000.0, 0, 0], c0 + [L - 38000.0, 0, 0], 30.0, 1600.0, up=n),
                   HULL_RED))
    # bulwark on the deck edge (the stations' deck edges, following the sheer), open at the stern and where the quay's
    # cable comes aboard; freeing ports along its foot
    outline = [(s[0], -s[1]) for s in st] + [(s[0], s[1]) for s in reversed(st)]
    inner_o = offset_polygon(outline, 160.0)
    top_z = p.deck_z + SHEER + BULWARK_H + 500.0
    bw = g.cut(g.polygon_prism(outline, top_z - p.deck_z + 100.0, T(0, 0, p.deck_z - 50.0)),
               g.polygon_prism(inner_o, top_z - p.deck_z + 300.0, T(0, 0, p.deck_z - 100.0)))
    xs = sorted({s[0] for s in st} | set(np.linspace(L - SHEER_LEN, L, 15).tolist()))
    band_prof = [(x, p.deck_z + sheer(x, L) - 1.0) for x in [-L] + xs + [2 * L]]
    band_prof += [(x, p.deck_z + sheer(x, L) + BULWARK_H) for x in reversed([-L] + xs + [2 * L])]
    band = g.polygon_prism(band_prof, 2 * big, g.Frame((0, big, 0), (1, 0, 0), (0, -1, 0)))
    bw = g.common(bw, band)
    ports = [g.box(x - 400.0, -big / 2, p.deck_z - 10.0, 800.0, big, 260.0)
             for x in np.arange(12000.0, L - SHEER_LEN - 3000.0, 6000.0)]
    fair = [(L - HOUSE_AFT - 1500.0, side) for side in (-1, 1)] + [(L - 6000.0, side) for side in (-1, 1)]
    fair_cut = []
    for x, side in fair:
        zf = p.deck_z + sheer(x, L) + 650.0
        fair_cut.append(g.box(x - 400.0, -big / 2, zf - 220.0, 800.0, big, 440.0))
    bw = g.cut(bw, g.box(-2000, -p.beam, p.deck_z - 100, 5200, 2 * p.beam, 1500),
               g.box(3000, -p.beam, p.deck_z - 100, pos["board_x"] + 1500 - 3000, p.beam, 1500), *ports, *fair_cut)
    a.add(Part("BULWARK", bw, HULL_BLUE))
    outfit = {}                                     # name -> list of boxes (model mm) the tests check
    fl = Part("FAIRLEAD", fairlead_shape(), BLACK)
    for x, side in fair:
        zf = p.deck_z + sheer(x, L) + 650.0
        yo = side_hit(g.polygon_prism(outline, 20.0, T(0, 0, zf - 10.0)), x, zf, side)
        a.add(fl, T(x, yo - side * 80.0, zf) @ Rot((0, 0, 1), 0.0 if side > 0 else 180.0))
    # rubbing strake: a half-round bar along each side, under the deck edge, over the parallel middle body
    zr = p.deck_z - 1500.0
    xs_r = [6000.0, 12000.0, 20000.0, 40000.0, 60000.0, 80000.0, L - 30000.0, L - 26500.0]
    for side in (-1, 1):
        q = [np.array([x, side_hit(hull, x, zr, side), zr]) for x in xs_r]
        bars = [g.rod(q0, q1, 160.0) for q0, q1 in zip(q[:-1], q[1:])] + [g.sphere(160.0, qq) for qq in q]
        a.add(Part("RUBBING STRAKE", g.cut(g.fuse(*bars), inner), BLACK))
    # name boards on both bows, draft-mark boards fore and aft (the app puts the decals on them)
    boards = []
    for side in (-1, 1):
        for name, x, zc, w, h in (("NAME BOARD", L - 22000.0, p.deck_z - 600.0, 6000.0, 900.0),
                                  ("DRAFT MARK BOARD", L - 7000.0, 0.0, 600.0, 2600.0),
                                  ("DRAFT MARK BOARD", 6000.0, 0.0, 600.0, 2600.0)):
            q, n, t, u = side_point(hull, x, zc, side)
            Mf = g.Frame(q, t, n)
            a.add(Part(name, g.xform(g.box(-w / 2, -h / 2, -60.0, w, h, 75.0), Mf), HULL_BLUE if name == "NAME BOARD"
                       else BLACK))
            boards.append({"name": name, "side": side, "centre": (q + 15.0 * n).tolist(), "normal": n.tolist(),
                           "up": u.tolist(), "size": [w, h]})
    # propulsion
    az = azimuth_thruster(kit)
    thr = []
    for side, label in ((1, "PS"), (-1, "SB")):
        y = side * AZ_Y * f
        # its housing's underside at the lowest point of the hull the thruster sweeps when it steers round (the bottom
        # slopes down forward): the nozzle's top stays under the hull at every steering angle
        zb = min(_bottom_z(hull, AZ_X + r * math.cos(t), y + r * math.sin(t)) for r in (0.0, 1500.0, 2700.0)
                 for t in np.linspace(0.0, 2 * math.pi, 12, endpoint=False))
        c = a.add(az, T(AZ_X, y, zb - 30.0), f"AZIMUTH THRUSTER {label}")
        thr.append({"name": f"AZIMUTH THRUSTER {label}", "axis": [AZ_X, y, zb - 30.0], "path": [c]})
    for k, xb in enumerate(BOW_TUNNELS):
        half = min(abs(side_hit(hull, L - xb + dx, BOW_Z + dz, s)) for dx in (-BOW_TUNNEL_R, BOW_TUNNEL_R)
                   for dz in (-BOW_TUNNEL_R, BOW_TUNNEL_R) for s in (-1, 1)) - 20.0
        c = a.add(tunnel_thruster(kit, half), T(L - xb, 0.0, BOW_Z), f"BOW THRUSTER {k + 1}")
        thr.append({"name": f"BOW THRUSTER {k + 1}", "axis": [L - xb, 0.0, BOW_Z], "path": [c]})
    # superstructure, lifeboats in davits
    sup, si = superstructure(p, L)
    a.add(sup, T(0, 0, 0), "SUPERSTRUCTURE")
    outfit["SUPERSTRUCTURE"] = [[si["aft"], si["bridge"][1], -si["wing"], si["wing"], p.deck_z, si["top_z"]]]
    boat = Part("LIFEBOAT", lifeboat_shape(), ORANGE)
    dv_y0, dv_y1 = 8650.0, 10600.0
    zd = p.deck_z + TIER_H
    for side in (-1, 1):
        xb = L - HOUSE_AFT + 6500.0
        a.add(boat, T(xb, side * dv_y1, p.deck_z + TIER_H + 200.0))
        for dx in (-2900.0, 2900.0):
            a.add(Part("DAVIT", g.xform(davit(side * dv_y0, side * dv_y1, zd, zd + 4600.0), T(xb + dx, 0, 0)), GALV))
        outfit.setdefault("LIFEBOAT", []).append([xb - 3750.0, xb + 3750.0, side * dv_y1 - 1300.0,
                                                  side * dv_y1 + 1300.0, zd, zd + 4600.0])
    # deck crane on port, forward of the carousel well
    crane = deck_crane()
    xk = L - CRANE_X_FROM_BOW
    c = a.add(crane, T(xk, CRANE_Y * f, p.deck_z), "DECK CRANE")
    yk = CRANE_Y * f
    pin_z = p.deck_z + 3230.0 + 3200.0
    outfit["DECK CRANE"] = [[xk - 2700.0, xk + 1600.0, yk - 2700.0, yk + 1600.0, p.deck_z, pin_z + 600.0],
                            [xk + 1700.0, xk + 700.0 + CRANE_BOOM * math.cos(math.radians(CRANE_LUFF)) + 800.0,
                             yk - 1100.0, yk + 1100.0, pin_z - 600.0, p.deck_z + crane.info["tip_z"]]]
    # bollards, hatches, windlasses, hawse pipes and anchors
    bl = bollard()
    for x, side in [(L - 44500.0, s) for s in (-1, 1)] + [(L - HOUSE_AFT - 1500.0, s) for s in (-1, 1)] + \
            [(L - 7000.0, s) for s in (-1, 1)]:
        zz = p.deck_z + sheer(x, L)
        y = side * (side_hit(g.polygon_prism(outline, 20.0, T(0, 0, zz - 10.0)), x, zz, side) * side - 1300.0)
        a.add(bl, T(x, y, zz))
        outfit.setdefault("BOLLARD", []).append([x - 900.0, x + 900.0, y - 400.0, y + 400.0, zz, zz + 770.0])
    hatch = Part("HATCH COVER", g.fuse(g.box(-1300.0, -1300.0, 0.0, 2600.0, 2600.0, 450.0),
                                       g.box(-1200.0, -1200.0, 450.0, 2400.0, 2400.0, 120.0),
                                       *[g.box(-1100.0 + 2000.0 * k, -150.0, 570.0, 200.0, 300.0, 120.0)
                                         for k in (0, 1)]), DECK_GREY)
    for x, y in ((L - 36000.0, -5500.0), (L - 36000.0, 0.0), (L - HOUSE_AFT - 3000.0, 0.0)):
        a.add(hatch, T(x, y, p.deck_z))
        outfit.setdefault("HATCH COVER", []).append([x - 1300.0, x + 1300.0, y - 1300.0, y + 1300.0, p.deck_z,
                                                     p.deck_z + 690.0])
    wl = windlass()
    an = Part("ANCHOR", anchor_shape(), BLACK)
    for side in (-1, 1):
        xw = L - 4800.0
        zz = p.deck_z + sheer(xw, L)
        a.add(wl, T(xw, side * 2600.0, zz))
        # the hawse pipe from the deck beside the windlass down and out through the bow's side
        xh, zh = L - 3600.0, p.deck_z - 300.0
        yo = side_hit(hull, xh, zh, side)
        top = np.array([L - 3900.0, side * 2600.0 * 1.35, p.deck_z + sheer(L - 3900.0, L) - 50.0])
        out_ = np.array([xh, yo + side * 150.0, zh])
        d = out_ - top
        a.add(Part("HAWSE PIPE", g.fuse(g.tube(300.0, 230.0, float(np.linalg.norm(d)) + 200.0, top - 100.0 * d /
                                               np.linalg.norm(d), d),
                                        g.tube(420.0, 230.0, 120.0, out_ - 60.0 * d / np.linalg.norm(d), d)), BLACK))
        q, n, t, u = side_point(hull, xh, zh - 1300.0, side)
        a.add(an, g.Frame(q + 330.0 * n - 1250.0 * u, t, u))
        outfit.setdefault("WINDLASS", []).append([xw - 900.0, xw + 900.0, side * 2600.0 - 1500.0,
                                                  side * 2600.0 + 1500.0, zz, zz + 1800.0])
    a.info["length"] = L
    a.info["deck_outline"] = [[round(x, 1), round(y, 1)] for x, y in outline]
    a.info["stations"] = [[round(float(v), 1) for v in s] for s in st]
    a.info["thrusters"] = thr
    a.info["boards"] = boards
    a.info["outfit"] = outfit
    a.info["sheer_from"] = L - SHEER_LEN
    return a


def _bottom_z(hull, x: float, y: float) -> float:
    """z of the hull's underside at (x, y)."""
    from OCP.gp import gp_Lin
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    si = IntCurvesFace_ShapeIntersector()
    si.Load(hull, 1e-3)
    si.Perform(gp_Lin(g.P((x, y, -1e5)), g.D((0.0, 0.0, 1.0))), 0.0, 2e5)
    if si.NbPnt() < 1:
        raise ValueError(f"no hull under ({x:.0f}, {y:.0f})")
    return min(si.Pnt(i + 1).Z() for i in range(si.NbPnt()))
