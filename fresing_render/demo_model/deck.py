"""The deck machines of the owner's layout (task 0084), each an ``Asm`` in its own coordinates with its joints.

Loading tower with the overhead arch, V roller highways and walkways, the horizontal radius controllers (stern turn,
quadrant gutter), the D-quadrant on rail bogies, the quadrant handler, the linear cable engine, swivel sheaves, the
CPS sets, rack, ramp and slide, the quay. Invented from general engineering knowledge and the owner's description of
how he works (0083); nothing copied from a company, vessel or product.
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from .geom import Asm, Part, Rot, T
from .machines import (CHROME, DARK, MOTOR, RUBBER, STEEL, YELLOW, Kit, _arc_rollers, cable_drive,
                       turn_axis)
from .route import LOWER_TILT, ar_eye_local, top_pulley

GREY = (0.55, 0.56, 0.57)
CPS_YELLOW = (0.98, 0.78, 0.05)
CPS_GREY = (0.40, 0.42, 0.44)
CPS_BROWN = (0.36, 0.22, 0.12)
ORANGE = (0.95, 0.42, 0.05)
CONCRETE = (0.62, 0.61, 0.58)
FENDER_BLACK = (0.06, 0.06, 0.06)
GRATING = (0.38, 0.40, 0.41)


def roller_about(kit: Kit, centre, axis, r: float, length: float, name: str = "CABLE ROLLER"):
    """(part, matrix) of a kit roller (made about its local y) with its axis along ``axis``."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    ref = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    x = ref - a * (ref @ a)
    x /= np.linalg.norm(x)
    z = np.cross(x, a)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, a, z, centre
    return kit.roller(r, length, name), M


# ---------------------------------------------------------------------------------------------------------
# Highways: V roller cradles on trestles, walkways
# ---------------------------------------------------------------------------------------------------------

V_HALF = math.radians(30.0)            # each cradle roller rises 30° from level: a 120° V
CRADLE_RR = 100.0
CRADLE_LEN = 600.0
CRADLE_OFF = 200.0                      # each roller sits this much outwards along its axis
CRADLE_BASE = 420.0                     # the cradle's base plate: this far under the cable's centre


def cradle(p, kit: Kit) -> Asm:
    """A V roller cradle. Local: the cable's centre at the origin, travelling towards -x. Two rollers in a 120° V
    (each with its joint, turned by the cable) on a bracket whose base plate lies CRADLE_BASE under the cable."""
    def make():
        cr, rr = p.cable_r, CRADLE_RR
        a = Asm("ROLLER CRADLE")
        ends = []
        for sy in (-1, 1):
            ax = np.array([0.0, sy * math.cos(V_HALF), math.sin(V_HALF)])
            n = np.array([0.0, -sy * math.sin(V_HALF), math.cos(V_HALF)])      # from the roller to the cable
            ctr = -(cr + rr) * n + CRADLE_OFF * ax
            part, M = roller_about(kit, ctr, ax, rr, CRADLE_LEN - 120.0)
            c = a.add(part, M)
            contact = ctr + rr * n               # the surface point straight towards the cable (not along the axle)
            a.joint(f"Roller {'port' if sy > 0 else 'stb'} turn", "rotate", [c], ctr,
                    turn_axis(ctr, contact, [-1.0, 0.0, 0.0]), None, cable_drive(rr))
            for t in (-CRADLE_LEN / 2, CRADLE_LEN / 2):
                ends.append(ctr + t * ax)
        zb = -CRADLE_BASE
        parts = [g.box(-180, -620, zb - 40, 360, 1240, 40)]
        for e in ends:                          # a post under each axle end
            parts.append(g.box(-60, e[1] - 50, zb - 1, 120, 100, e[2] - 30 - zb + 1))
            parts.append(g.cyl(35.0, 160.0, (-80, e[1], e[2]), (1, 0, 0)))
        a.add(Part("ROLLER CRADLE", g.fuse(*parts), YELLOW))
        return a
    return kit.get(("cradle",), make)


def trestle(kit: Kit, h: float) -> Part:
    """A portal trestle from the deck (z = 0) up to height h (the cradle's base plate)."""
    def make():
        legs = [g.box(-120, y - 120, 0, 240, 240, h) for y in (-480.0, 480.0)]
        feet = [g.box(-250, y - 250, 0, 500, 500, 30) for y in (-480.0, 480.0)]
        top = g.box(-150, -600, h - 200, 300, 1200, 200)
        brace = g.box(-100, -480, 0.35 * h, 200, 960, 120)
        return Part("ROLLER TRESTLE", g.fuse(*legs, *feet, top, brace), YELLOW)
    return kit.get(("trestle", round(h)), make)


LIFT_TOP = 160.0                        # a cradle's highest point above the cable's centre (roller ends + radius)


def lifting_cradle(p, kit: Kit, h: float, drop: float) -> Asm:
    """A V roller cradle that can drop out of the D-quadrant's way (task 0091; since task 0102 every
    lane cradle the D passes over).
    Local: as ``cradle`` (the cable's centre at the origin, travelling towards -x). The fixed part is a trestle of
    height h whose legs are guide tubes; the cradle sits on a lift frame (top beam + two posts sliding in the tubes)
    that a slide joint lowers by up to ``drop`` (the joint is made by the caller, on ``info["lift"]``)."""
    def make():
        z0 = -(CRADLE_BASE + 40.0) - h         # the deck, in the cradle's frame
        tube_top = h - 200.0 - drop - 10.0       # the top beam stops 10 mm above the tubes
        post = h - 240.0 - drop                  # dropped, the posts end 40 mm above the deck
        if post - drop - 10.0 < 80.0:
            raise ValueError(f"a lifting cradle {h:.0f} mm high cannot drop {drop:.0f} mm")
        legs, posts = [], []
        for y in (-480.0, 480.0):
            legs.append(g.cut(g.box(-120, y - 120, z0, 240, 240, tube_top),
                              g.box(-90, y - 90, z0 + 30.0, 180, 180, tube_top)))
            legs.append(g.box(-250, y - 250, z0, 500, 500, 30))
            posts.append(g.box(-80, y - 80, z0 + h - 200.0 - post, 160, 160, post + 1.0))
        brace = g.box(-100, -375, z0 + 0.35 * h, 200, 750, 120)          # into the tubes' walls, not their bores
        base = Part("ROLLER TRESTLE", g.fuse(*legs, brace), YELLOW)
        frame = Part("CRADLE LIFT FRAME", g.fuse(g.box(-150, -600, z0 + h - 200.0, 300, 1200, 200), *posts), YELLOW)
        lift = Asm("CRADLE LIFT")
        lift.add(cradle(p, kit))
        lift.add(frame)
        a = Asm("LIFTING CRADLE")
        a.add(base)
        a.info.update({"lift": a.add(lift), "drop": drop, "h": h})
        return a
    return kit.get(("lifting_cradle", round(h), round(drop)), make)


def walkway(x0: float, x1: float, y_in: float, y_out: float, z: float) -> Part:
    """A grating walkway from x0 to x1 between y_in and y_out (model), its top at z, on posts from the deck at
    deck_z = z - h (posts every 3 m), with a handrail on the outer side. Built in model coordinates (placed at I)."""
    lo, hi = min(y_in, y_out), max(y_in, y_out)
    w = hi - lo
    parts = [g.box(x0, lo, z - 40, x1 - x0, w, 40)]
    n = max(2, int((x1 - x0) / 3000.0) + 1)
    yr = y_out - math.copysign(40.0, y_out - y_in)
    for k in range(n):
        x = x0 + 100 + (x1 - x0 - 200) * k / (n - 1)
        parts.append(g.box(x - 40, (lo + hi) / 2 - 40, z - 1150, 80, 80, 1111))
        parts.append(g.box(x - 25, yr - 25, z - 1, 50, 50, 1101))
    parts.append(g.box(x0, yr - 30, z + 1060, x1 - x0, 60, 40))
    parts.append(g.box(x0, yr - 20, z + 520, x1 - x0, 40, 30))
    return Part("GRATING WALKWAY", g.fuse(*parts), GRATING)


# ---------------------------------------------------------------------------------------------------------
# Horizontal radius controllers (stern turn, quadrant gutter)
# ---------------------------------------------------------------------------------------------------------

def flat_bend_rollers(p, kit: Kit, asm: Asm, R: float, z: float, a0: float, a1: float, step_deg: float, name: str,
                      rr: float = 90.0) -> list:
    """Vertical rollers inside a horizontal bend (centre at the local origin, radius R, cable centre height z).
    a0 -> a1: angles (deg) from +x; the cable travels from a0 to a1. Each roller has a joint (turned by the cable)."""
    cr = p.cable_r
    Rr = R - cr - rr
    n = max(2, int(abs(a1 - a0) / step_deg) + 1)
    out = []
    for k in range(n):
        ang = math.radians(a0 + (a1 - a0) * (k + 0.5) / n)
        u = np.array([math.cos(ang), math.sin(ang), 0.0])
        ctr = Rr * u + [0, 0, z]
        part, M = roller_about(kit, ctr, (0, 0, 1), rr, 2 * cr + 40.0, "GUIDE ROLLER")
        c = asm.add(part, M)
        sgn = 1.0 if a1 > a0 else -1.0
        vel = sgn * np.array([-math.sin(ang), math.cos(ang), 0.0])
        contact = (R - cr) * u + [0, 0, z]
        asm.joint(f"{name} {k + 1} turn", "rotate", [c], ctr, turn_axis(ctr, contact, vel), None, cable_drive(rr))
        out.append(c)
    return out


def sector(profile, a0: float, a1: float):
    """Revolve an (r, z) profile about local z from angle a0 to a1 (deg)."""
    lo, hi = sorted((a0, a1))
    return g.xform(g.revolve(profile, angle=hi - lo), Rot((0, 0, 1), lo))


def flat_bend(p, kit: Kit, R: float, z: float, z_deck: float, a0: float = 270.0, a1: float = 90.0,
              name: str = "STERN RADIUS CONTROLLER", label: str = "Stern turn", slots=()) -> Asm:
    """A horizontal radius controller: vertical rollers inside the bend, rollers under the cable. Local: the bend's
    centre at the origin (model z); the cable travels clockwise (seen from above) from angle a0 to a1 (a0 > a1).
    The stern turn: 270° -> 90° (from the lower path round the aft side to side B, under the quadrant's rails)."""
    a = Asm(name)
    cr = p.cable_r
    rr = 90.0
    flat_bend_rollers(p, kit, a, R, z, a0, a1, 7.5, f"{label} roller", rr)
    web_in = R - cr - 2 * rr - 70.0
    top = z + cr + 25.0
    prof = [(web_in, z_deck), (R + 450.0, z_deck), (R + 450.0, z_deck + 30.0), (web_in + 40.0, z_deck + 30.0),
            (web_in + 40.0, top), (R - cr + 15.0, top), (R - cr + 15.0, top + 30.0), (web_in, top + 30.0)]
    rc = sector(prof, a1, a0)
    if slots:                                   # holes in the web (a wire passing through: ``slots`` are local boxes)
        rc = g.cut(rc, *[g.box(*s) for s in slots])
    a.add(Part("RADIUS CONTROLLER", rc, YELLOW))
    # bottom rollers under the cable (axis radial), on blocks
    n = max(3, int(round((a0 - a1) / 14.0)))
    for k in range(n):
        ang = math.radians(a1 + (a0 - a1) * (k + 0.5) / n)
        u = np.array([math.cos(ang), math.sin(ang), 0.0])
        ctr = R * u + [0, 0, z - cr - 80.0]
        part, M = roller_about(kit, ctr, u, 80.0, 420.0)
        c = a.add(part, M)
        vel = np.array([math.sin(ang), -math.cos(ang), 0.0])
        a.joint(f"{label} bottom roller {k + 1} turn", "rotate", [c], ctr,
                turn_axis(ctr, ctr + [0, 0, 80.0], vel), None, cable_drive(80.0))
        blk = kit.get(("st_block", round(z - z_deck)), lambda: Part("ROLLER STAND", g.fuse(
            g.box(-60, -260, 0, 120, 40, z - cr - 80.0 - z_deck + 30), g.box(-60, 220, 0, 120, 40, z - cr - 80.0 - z_deck + 30),
            g.box(-200, -300, 0, 400, 600, 30)), YELLOW))
        Mb = np.eye(4)
        Mb[:3, 0], Mb[:3, 1], Mb[:3, 2] = np.cross([0, 0, 1.0], u), u, [0, 0, 1.0]
        Mb[:3, 3] = R * u + [0, 0, z_deck]
        a.add(blk, Mb)
    return a


# ---------------------------------------------------------------------------------------------------------
# Loading tower with the overhead arch (vessel and quay)
# ---------------------------------------------------------------------------------------------------------

def loading_tower(p, kit: Kit, name: str, span: float, z_arch: float, z_foot: float, z_deck: float,
                  foot_deg: float, arch_deg: float, cage_deg: float, z_coil: float, slew_limits) -> Asm:
    """Loading tower (fixed, with the foot bend) carrying the overhead arch that only slews about the tower's
    axis: two 90° radius controllers and the straight between (rollers inside), the hanging guide frame with a
    platform, and the guide's roller cage (bellmouth) where the cable lifts off the coil, on a swivel.

    Local: the tower's axis is the z axis (model z), the axes parallel to the model's. ``foot_deg``: model
    direction the cable leaves the foot bend; ``arch_deg``: direction from the tower to the guide (rest);
    ``cage_deg``: direction from the guide to the lift-off point (rest)."""
    R, cr = p.bend_r, p.cable_r
    A = Asm(name)
    z_ring = z_arch - R - 1400.0
    # ---- tower
    legs = [g.box(sx * 1300 - 200, sy * 1300 - 200, z_deck, 400, 400, z_ring - z_deck) for sx in (-1, 1)
            for sy in (-1, 1)]
    braces = []
    for k, h0 in enumerate(np.arange(z_deck + 800.0, z_ring - 1500.0, 2600.0)):
        for sx in (-1, 1):
            braces.append(g.beam((sx * 1300, -1300, h0), (sx * 1300, 1300, h0 + 1800), 160.0))
            braces.append(g.beam((-1300, sx * 1300, h0 + 1300), (1300, sx * 1300, h0 + 1300 + 1800), 160.0))
    ring_beam = g.cut(g.box(-1600, -1600, z_ring - 400, 3200, 3200, 400), g.cyl(1150, 600, (0, 0, z_ring - 500)))
    A.add(Part("TOWER COLUMN", g.fuse(*legs, *braces, ring_beam), YELLOW))
    A.add(Part("SLEWING RING", g.tube(1400, 1000, 250, (0, 0, z_ring)), MOTOR))
    foot = Asm("TOWER FOOT")
    _arc_rollers(kit, foot, (-R, z_foot + R), R, 0.0, -90.0, cr, 9.0, "Tower foot roller")
    zp = z_foot + 450.0
    foot.add(Part("FOOT FRAME", g.fuse(
        *[g.box(-R * 0.55 - 150, y - 100, z_deck, 300, 200, zp - z_deck) for y in (-480.0, 480.0)],
        *[g.box(-R * 0.55 - 150, min(y, 0.6 * y) - 0.0, zp - 100, 300, 0.4 * abs(y), 100) for y in (-480.0, 480.0)],
        g.box(-R * 0.55 - 400, -600, z_deck, 800, 1200, 40)), YELLOW))
    A.add(foot, Rot((0, 0, 1), foot_deg - 180.0))
    # ---- the arch (slews)
    arch = Asm("LOADING ARCH")
    z_h = z_ring + 250.0
    arch.add(Part("SLEW HOUSING", g.cut(g.cyl(1350, 400, (0, 0, z_h)), g.cyl(950, 500, (0, 0, z_h - 50))), YELLOW))
    _arc_rollers(kit, arch, (span - R, z_arch - R), R, 0.0, 90.0, cr, 9.0, "Arch roller (guide side)",
                 plate_name="ARCH")
    _arc_rollers(kit, arch, (R, z_arch - R), R, 90.0, 180.0, cr, 9.0, "Arch roller (tower side)", plate_name="ARCH")
    rr = 125.0
    Rr = R - cr - rr
    r_in, r_out = Rr - rr - 250.0, R - cr * 0.3
    frame = []
    straight = span - 2 * R
    if straight > 1.0:
        xs = np.arange(R + 0.5 * min(1500.0, straight), span - R, 1500.0)
        for k, x in enumerate(xs):
            ctr = np.array([x, 0.0, z_arch - cr - rr])
            part = kit.roller(rr, 700.0)
            c = arch.add(part, T(*ctr))
            arch.joint(f"Arch roller (top) {k + 1} turn", "rotate", [c], ctr,
                       turn_axis(ctr, ctr + [0, 0, rr], [-1.0, 0, 0]), None, cable_drive(rr))
        sp = [g.box(R, y - 30, z_arch - (R - r_in), straight, 30, r_out - r_in) for y in (-350.0, 380.0)]
        sp += [g.box(x - 60, -380, z_arch - (R - r_in) + 30, 120, 760, 120) for x in (R + 0.3 * straight,
                                                                                     R + 0.7 * straight)]
        arch.add(Part("ARCH", g.fuse(*sp), YELLOW))
    # top chord over the cable (over the guide leg too), posts from the housing to a platform, up to the chord
    zt = z_arch + cr + 300.0
    frame.append(g.box(-300, -500, zt, span + 1100, 1000, 350))
    zpl = z_arch - R * 0.5
    for y in (-470.0, 470.0):
        frame.append(g.box(-200, y - 30, zpl, 200, 60, zt - zpl + 1))
    for sx in (-1, 1):
        for y in (-700.0, 700.0):
            x = sx * 900.0
            frame.append(g.box(x - 150, y - 150, z_h + 399, 300, 300, z_arch - R * 0.5 - z_h - 398))
    frame.append(g.box(-1050, -850, z_arch - R * 0.5, 2100 + R * 0.3, 1700, 250))
    arch.add(Part("ARCH FRAME", g.fuse(*frame), YELLOW))
    # hanging guide frame along the vertical leg (x = span), a platform at its end
    z_bot = z_coil + R + 350.0
    z_top = z_arch - R
    gf = [g.box(span + sx * 700 - 100, sy * 650 - 100, z_bot, 200, 200, zt - z_bot + 1) for sx in (-1, 1)
          for sy in (-1, 1)]
    for zz in np.arange(z_bot + 1500.0, z_top, 2000.0):
        gf.append(g.cut(g.box(span - 800, -750, zz, 1600, 1500, 120), g.box(span - 400, -400, zz - 10, 800, 800, 140)))
    gf.append(g.cut(g.box(span - 1300, -1100, z_bot - 60, 2600, 2200, 60), g.cyl(cr + 250, 200, (span, 0, z_bot - 100))))
    gf.append(g.box(span - 1300, -1100, z_bot, 40, 2200, 1100))
    arch.add(Part("GUIDE FRAME", g.fuse(*gf), YELLOW))
    for k, zz in enumerate((z_bot + 800.0, z_top - 600.0)):
        for sx in (-1, 1):
            ctr = np.array([span + sx * (cr + 90.0), 0.0, zz])
            c = arch.add(kit.roller(90.0, 500.0, "GUIDE ROLLER"), T(*ctr))
            arch.joint(f"Guide roller {2 * k + (sx + 1) // 2 + 1} turn", "rotate", [c], ctr,
                       turn_axis(ctr, ctr - [sx * 90.0, 0, 0], [0, 0, 1.0]), None, cable_drive(90.0))
    # the guide's roller cage (bellmouth) on a swivel under the platform
    cage = Asm("GUIDE CAGE")
    _arc_rollers(kit, cage, (R, z_coil + R), R, -90.0, -180.0, cr, 9.0, "Guide cage roller", plate_name="GUIDE CAGE")
    cage.add(Part("CAGE SWIVEL", g.fuse(g.tube(cr + 450, cr + 250, 200, (0, 0, z_bot - 260)),
                                        g.box(150, -400, z_coil + R - 150, 0.45 * R, 800, z_bot - 260 - (z_coil + R - 150)),
                                        g.box(150, -400, z_bot - 260, 0.45 * R, 800, 60)), YELLOW))
    cc = arch.add(cage, T(span, 0, 0) @ Rot((0, 0, 1), cage_deg - arch_deg))
    arch.joint("Guide cage swivel", "rotate", [cc], (span, 0, 0), (0, 0, 1), None,
               {"by": "follows coil", "note": "turns the roller cage so its bend lies along the coil's turn where the "
                                              "cable lifts off (rest: lined up)"})
    ca = A.add(arch, Rot((0, 0, 1), arch_deg))
    A.joint("Arch slew", "rotate", [ca], (0, 0, 0), (0, 0, 1), [round(v, 3) for v in slew_limits],
            {"by": "operator", "note": "the arch only slews: positive (anticlockwise seen from above) brings the guide "
                                       "towards the core, negative towards the rim; the coil radius under the guide "
                                       "follows from the angle"})
    A.info.update({"arch_path": [ca], "cage_path": [ca, cc], "span": span, "z_ring": z_ring})
    return A


# ---------------------------------------------------------------------------------------------------------
# Linear cable engine
# ---------------------------------------------------------------------------------------------------------

def cable_engine(p, kit: Kit, h: float | None = None) -> Asm:
    """Linear cable engine: four pairs of rubber-tyred wheels (bottom fixed, top on a carriage pressed down by two
    cylinders), each with a hydraulic motor. Local: the cable along x through the origin, travelling towards -x;
    the deck at z = -h (the cable's height above the deck: the highway's ``line_h`` or, since task 0095, the lower
    path's). A low cable gets smaller wheels so the frame still stands on the deck."""
    cr = p.cable_r
    h = p.line_h if h is None else h
    rw, ww = min(300.0, (h - cr - 180.0) / 2.0), 260.0
    zdeck = -h
    A = Asm("CABLE ENGINE")
    wheel = kit.get(("ce_wheel", rw), lambda: Part("CABLE ENGINE WHEEL", g.fuse(
        g.revolve([(60, -ww / 2), (rw - 60, -ww / 2), (rw, -ww / 2 + 50), (rw, ww / 2 - 50), (rw - 60, ww / 2),
                   (60, ww / 2)], (0, 0, 0), (0, 1, 0))), RUBBER))
    hub = kit.get(("ce_hub", rw), lambda: Part("WHEEL HUB", g.cyl(rw - 70, ww + 40, (0, -ww / 2 - 20, 0), (0, 1, 0)),
                                                STEEL))
    mo = kit.motor(110.0, 280.0)
    xs = (-1350.0, -450.0, 450.0, 1350.0)
    zb = -(cr + rw)
    top = Asm("TOP WHEEL CARRIAGE")
    for which, asm, z in (("Bottom", A, zb), ("Top", top, -zb)):
        for k, x in enumerate(xs):
            ctr = np.array([x, 0.0, z])
            c = asm.add(wheel, T(*ctr))
            asm.add(hub, T(*ctr))
            asm.add(mo, T(x, 380.0, z))
            contact = ctr + ([0, 0, rw] if which == "Bottom" else [0, 0, -rw])
            asm.joint(f"{which} wheel {k + 1} turn", "rotate", [c], ctr, turn_axis(ctr, contact, [-1.0, 0, 0]), None,
                      cable_drive(rw, note="rubber tyre on the cable"))
    side = [g.box(-1900, sy * 330 - 30, zb - rw - 120, 3800, 60, rw + 120 + 90) for sy in (-1, 1)]
    side += [g.box(x - 90, -330, zb - rw - 120, 180, 660, 120) for x in xs]
    frame = [g.box(-2000, sy * 900 - 150, zdeck, 4000, 300, zb - rw - 120 - zdeck) for sy in (-1, 1)]
    frame += [g.box(x - 150, -1050, zdeck, 300, 2100, zb - rw - 120 - zdeck) for x in (-1900.0, 0.0, 1900.0)]
    frame += [g.box(x - 150, -900 - 150, zb - rw - 121, 300, 1800 + 300, 120) for x in (-1350.0, 1350.0)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(g.box(sx * 1900 - 150, sy * 900 - 150, zb - rw - 121, 300, 300, -zb + rw + 700 - (zb - rw - 121)))
    frame += side
    A.add(Part("CABLE ENGINE FRAME", g.fuse(*frame), YELLOW))
    tf = [g.box(-1900, sy * 330 - 30, -zb - 90, 3800, 60, 180) for sy in (-1, 1)]
    tf += [g.box(-1700, -1050, -zb + rw + 100, 3400, 2100, 160)]
    tf += [g.box(x - 90, -330, -zb, 180, 60, rw + 101) for x in xs] + [g.box(x - 90, 270, -zb, 180, 60, rw + 101) for x in xs]
    top.add(Part("TOP WHEEL FRAME", g.fuse(*tf), YELLOW))
    ct = A.add(top)
    A.joint("Cable engine squeeze", "slide", [ct], (0, 0, -zb), (0, 0, 1), [-(cr - 25.0), 250.0 - cr + 300.0],
            {"by": "operator", "note": "positive lifts the top wheels off the cable; 0 = pressing this cable Ø"})
    A.info.update({"wheel_r": rw, "half_length": 2000.0, "top_path": [ct]})
    return A


# ---------------------------------------------------------------------------------------------------------
# The D-quadrant on rail bogies, the quadrant handler, rails
# ---------------------------------------------------------------------------------------------------------

RAIL_Y = 2000.0                         # the quadrant's rails at y = +-RAIL_Y
BOGIE_H = 350.0                         # rail top -> the D's underside
WHEEL_R = 120.0                         # rail wheel tread radius (its flange 30 more)


D_INNER = 450.0                         # the D's frame under the cable's height stays this far inside its curve (0102)


def d_shape(p) -> dict:
    """The D-quadrant's sizes (local mm: origin on the bar's line at the curve's centre, rail top z = 0), task 0102.

    The D is exactly as wide as the cable's path, so its sides pass through the tensioners' lines (over their bottom
    tracks, the horns' upper ends and the lane cradles): nothing of it farther out than ``inner`` from the middle is lower
    than ``band_z`` – 30 mm under the cable's centre, at least 30 mm over the bottom track's pads. Its frame lower down
    (bar, spokes, ring, bogies) stays within |y| <= ``inner``. Task 0081: the pads' V follows the cable Ø
    (``machines.pad_v_depth``), so ``band_z`` – where the gutter rollers end – lies under the cable's centre from Ø 80
    up and just above it for smaller cables (the rollers touch, or clear the cable by ~2 mm); the outer lip ends at the
    cable's centre or at ``band_z`` if that is higher (``lip_z``)."""
    from .machines import pad_top as pad_top_of
    Rq, cr = p.quadrant_r, p.cable_r
    zc = p.line_z - p.rail_z
    rr = 90.0
    pad_top = pad_top_of(p)                              # the bottom pads' highest edge, from the cable's centre (their
    #                                                      V follows the cable Ø, task 0081: the rollers reach the cable)
    z_up = zc + max(-30.0, pad_top + 30.0)
    zt = max(z_up + 300.0, zc + cr + 60.0)               # the guide rollers' top, the gutter's top plate under it
    lip = Rq + cr + 120.0
    web_in = Rq - cr - 2 * rr - 70.0
    inner = Rq - D_INNER
    bar_end = web_in + 40.0                              # the upper bar's ends: at the gutter's inner web, well inside the
    #                                                      cable (a part's edge close to it reads as a seat, task 0078)
    eye_y = Rq + 150.0                                   # the tipping eyes: on brackets over the cable's line,
    eye_z = zt + 580.0                                   # high enough that their wires clear the gutter when vertical
    return {"zc": zc, "rr": rr, "band_z": z_up, "zt": zt, "lip": lip, "lip_z": max(zc, z_up), "web_in": web_in,
            "inner": inner, "half_width": lip + 40.0, "floor": zc - cr - 10.0, "bar_end": bar_end, "eye_y": eye_y, "eye_z": eye_z,
            "top_z": max(zt + 30.0, eye_z + 190.0), "edge_top_z": zt + 30.0, "floor_deg": math.degrees(math.asin(min(1.0, inner / (lip + 40.0)))),
            "ring_deg": math.degrees(math.asin(min(1.0, inner / (web_in + 120.0))))}


def quadrant_d(p, kit: Kit) -> Asm:
    """The D-shaped quadrant. Local: origin on the straight bar's line at the curve's centre, at rail-top height;
    the curve (cable centre radius Rq) in front (+x), the bar along y at x = 0, the cable round the gutter at local
    z = line_z - rail_z, travelling from +y round the front to -y. Rail bogies at the rails, the A&R pad eye at the
    top of the curve (task 0095: the A&R wire hangs the D from it), tipping pad eyes at the bar's ends.

    Task 0102: the D is exactly as wide as the cable's path (``d_shape``): its gutter's ends carry the cable in line with
    the side lanes and pass over the tensioners' bottom tracks, so towards its ends the gutter is an upper channel only –
    a top plate, the guide rollers hanging from it inside the cable, the outer lip down to the cable's centre – and its
    floor, ring and bar under the cable's height stay inside the curve (``inner``); an upper bar above the cable's height
    joins the channel's ends."""
    Rq, cr = p.quadrant_r, p.cable_r
    ds = d_shape(p)
    zc, rr, z_up, zt, lip, web_in, inner = (ds[k] for k in ("zc", "rr", "band_z", "zt", "lip", "web_in", "inner"))
    A = Asm("QUADRANT")
    # guide rollers inside the curve, hanging from the top plate (no stub under them: they stay above band_z)
    H = zt - 10.0 - z_up
    roller = kit.get(("d_guide_roller", rr, round(H)), lambda: Part("GUIDE ROLLER", g.revolve(      # about local y,
        [(25.0, 0.0), (rr, 0.0), (rr, H - 30.0), (rr + 15.0, H - 30.0), (rr + 15.0, H), (55.0, H), (55.0, H + 9.0),
         (25.0, H + 9.0)], (0, 0, 0), (0, 1, 0)), STEEL))                                  # as every roller of the kit
    up = np.eye(4)
    up[:3, :3] = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])   # local y -> model z
    Rr = Rq - cr - rr
    n = max(2, int(180.0 / 7.5) + 1)
    for k in range(n):
        ang = math.radians(90.0 - 180.0 * (k + 0.5) / n)
        u = np.array([math.cos(ang), math.sin(ang), 0.0])
        ctr = Rr * u + [0, 0, z_up]
        c = A.add(roller, T(*ctr) @ up)
        vel = -np.array([-math.sin(ang), math.cos(ang), 0.0])          # the cable runs from +y round the front to -y
        contact = (Rq - cr) * u + [0, 0, zc]
        A.joint(f"Quadrant gutter roller {k + 1} turn", "rotate", [c], ctr + [0, 0, zc - z_up],
                turn_axis(ctr + [0, 0, zc - z_up], contact, vel), None, cable_drive(rr))
    floor = ds["floor"]
    lz = ds["lip_z"]                                     # the outer lip down to the cable's centre (or the rollers'
    upper = [(web_in, z_up), (web_in + 40.0, z_up), (web_in + 40.0, zt), (lip, zt), (lip, lz), (lip + 40.0, lz),
             (lip + 40.0, zt + 30.0), (web_in, zt + 30.0)]                     # reach over the pads, if higher)
    lower = [(web_in, floor - 40.0), (lip + 40.0, floor - 40.0), (lip + 40.0, lz), (lip, lz), (lip, floor),
             (web_in + 40.0, floor), (web_in + 40.0, z_up + 1.0), (web_in, z_up + 1.0)]
    fd = ds["floor_deg"]
    A.add(Part("QUADRANT GUTTER", g.fuse(sector(upper, -90.0, 90.0), sector(lower, -fd, fd)), YELLOW))
    # frame: the straight bar, spokes from the bar's middle to the gutter, a ring under the gutter – all inside |y| <=
    # inner; the upper bar over the cable's height from end to end of the curve, posts down to the bar
    zb0, zb1 = BOGIE_H, floor - 40.0
    fr = [g.box(-600, -inner, zb0, 600, 2 * inner, zb1 - zb0 + 1)]
    for ang in (-60.0, -30.0, 0.0, 30.0, 60.0):
        u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
        fr.append(g.beam(np.array([0, 0, (zb0 + zb1) / 2]), np.array([0, 0, (zb0 + zb1) / 2]) + (web_in + 30) * u,
                         260.0, zb1 - zb0))
    rd = ds["ring_deg"]
    fr.append(sector([(web_in - 250, zb0), (web_in + 120, zb0), (web_in + 120, zb1 + 1), (web_in - 250, zb1 + 1)],
                     -rd, rd))
    ye = ds["bar_end"]
    fr.append(g.box(-600, -ye, z_up, 600, 2 * ye, zt + 30.0 - z_up))
    for sy in (-1, 1):
        fr.append(g.box(-450, sy * (inner - 200.0) - 150.0, zb1, 300, 300, z_up - zb1 + 1.0))
    A.add(Part("QUADRANT FRAME", g.fuse(*fr), YELLOW))
    # pad eyes (task 0095): the A&R eye at the top of the curve – the middle of its outer edge, just outside the
    # gutter's lip, under the gutter and above the D's underside; a bracket from the frame's ring carries a plate
    # square to x whose hole the A&R wire ends in (the wire stays in the plane y = 0, so it never runs through the
    # plate). The tipping eyes on the upper bar's ends: the D's bottom corners when it stands vertical on the handler.
    eye = ar_eye_local(p)
    ar = eye[0]
    eyes = {"handling": eye}
    plate = g.cut(g.box(ar - 30.0, -180.0, zb0 + 10.0, 60.0, 360.0, zb1 - zb0 + 10.0),
                  g.cyl(75.0, 200.0, eye + [-100.0, 0, 0], (1, 0, 0)))
    A.add(Part("A&R PAD EYE", g.fuse(plate, g.box(web_in + 80.0, -50.0, zb0 + 30.0, ar - 30.0 - web_in - 80.0 + 1.0,
                                                  100.0, 170.0)), YELLOW))      # under the gutter's floor
    zb = zc + cr + 30.0                                  # over the cable's top where it leaves the gutter at rest
    for key, sy in (("tipping_port", 1.0), ("tipping_stb", -1.0)):
        c = np.array([-300.0, sy * ds["eye_y"], ds["eye_z"]])
        # a thin lug with a big hole (the tipping wire comes in at up to ~60° to the hole's axis) on a bracket from the
        # upper bar's end over the cable's line
        lo, hi = sorted((sy * ye, sy * (ds["eye_y"] - 20.0)))
        y0 = sy * ds["eye_y"] - 20.0
        lug = g.cut(g.fuse(g.box(-450, y0, zb, 300, 40, c[2] - zb), g.box(-450, lo, zb, 300, hi - lo + 1.0, zt + 30.0 - zb),
                           g.cyl(190.0, 40.0, c + [0, -20, 0], (0, 1, 0))), g.cyl(90.0, 200.0, c + [0, -100, 0], (0, 1, 0)))
        A.add(Part("PAD EYE", lug, YELLOW))
        eyes[key] = c
    # rail bogies: two on each rail, each with two wheels (they turn with the travel)
    wr = WHEEL_R
    # the tread covers the rail head (140 wide), the flange runs beside it, inboard; the bogie's top plate clears
    # the flange (task 0091: the flange used to cut into the rail head, the tread into the top plate)
    wheel = kit.get(("rail_wheel", wr), lambda: Part("RAIL WHEEL", g.fuse(
        g.cyl(wr, 150.0, (0, -75, 0), (0, 1, 0)), g.cyl(wr + 30, 20.0, (0, 75, 0), (0, 1, 0))), STEEL))
    bogie = kit.get(("bogie",), lambda: Part("RAIL BOGIE", g.fuse(
        g.box(-650, -170, wr, 1300, 40, BOGIE_H - wr), g.box(-650, 130, wr, 1300, 40, BOGIE_H - wr),
        g.box(-650, -170, BOGIE_H - 60, 1300, 340, 61)), YELLOW))
    k = 0
    for xb in (550.0, Rq - 800.0):
        for sy in (-1, 1):
            A.add(bogie, T(xb, sy * RAIL_Y, 0))
            for dx in (-400.0, 400.0):
                k += 1
                ctr = np.array([xb + dx, sy * RAIL_Y, wr])
                c = A.add(wheel, T(*ctr) if sy < 0 else T(*ctr) @ Rot((0, 0, 1), 180.0))     # flange inboard
                A.joint(f"Rail wheel {k} turn", "rotate", [c], ctr, (0, 1, 0), None,
                        {"by": "follows", "follows": "../Quadrant travel", "ratio": round(360.0 / (2 * math.pi * wr), 9),
                         "note": "rolls on the rail (degrees per mm of travel; travel is aft, -x)"})
    A.info.update({"eyes": {k2: v.tolist() for k2, v in eyes.items()}, "radius": Rq, "cable_z": zc,
                   "hang_off": eye.tolist(), "bar_y": ye, "front_x": lip + 40.0, "back_x": -600.0, "shape": ds})
    return A


def rail_girder(x0: float, x1: float) -> Part:
    """A rail on a box girder from x0 to x1 (local y = 0), the rail's top at z = 0."""
    s = g.fuse(g.box(x0, -200, -400, x1 - x0, 400, 300), g.box(x0, -40, -100, x1 - x0, 80, 60),
               g.box(x0, -70, -40, x1 - x0, 140, 40))
    return Part("QUADRANT RAIL", s, STEEL)


def quadrant_handler(p, kit: Kit, length: float, z_hinge: float, deck_z: float) -> Asm:
    """The quadrant handler: a frame lying flat in the middle lane, hinged at the transom, tilted 0 -> ~100° over
    the stern by two cylinders; rails on top (the quadrant rolls on), the A&R wire's top pulley beyond its far end.

    Task 0095: no sheave at the hinge any more. The A&R wire runs from its winch straight to the D's eye at the top of
    the curve; the top pulley (``route.top_pulley``) stays under the D while it rolls on, and the wire bears on it once
    the handler tilts: at 100° it comes from forward over the pulley and hangs straight down to the eye.

    Local: the hinge axis along y through the origin (model z = z_hinge); the frame lies along +x."""
    A = Asm("QUADRANT HANDLER")
    rail_top = p.rail_z - z_hinge
    zd = deck_z - z_hinge
    frame = Asm("HANDLER FRAME")
    fr = []
    for sy in (-1, 1):
        fr.append(g.box(0, sy * RAIL_Y - 250, -350, length, 500, rail_top - 100 + 350))
        fr.append(g.cyl(300.0, 580.0, (0, sy * RAIL_Y - 290, 0), (0, 1, 0)))      # 10 mm from the brackets' cheeks
    # cross beams: the first one far enough from the hinge to swing over the brackets
    for x in np.linspace(1100.0, length - 1000.0, 4):
        fr.append(g.box(x - 200, -RAIL_Y, -250, 400, 2 * RAIL_Y, 400))
    # the top pulley beyond the forward (top) end, on two brackets from the end beam
    tp = top_pulley(p)
    rp = tp["r"]
    pc = np.array([tp["centre"][0], 0.0, tp["centre"][1]])
    fr.append(g.box(length - 400, -RAIL_Y, -250, 400, 2 * RAIL_Y, rail_top - 100 + 250))
    for sy in (-1, 1):
        fr.append(g.box(length - 350, sy * 260 - 40, -250, pc[0] + 300.0 - (length - 350), 80, pc[2] + 250 + 150))
    frame.add(Part("HANDLER FRAME", g.fuse(*fr), YELLOW))
    for sy in (-1, 1):
        frame.add(Part("QUADRANT RAIL", g.fuse(
            g.box(0, sy * RAIL_Y - 40, rail_top - 100, length - 50, 80, 60),
            g.box(0, sy * RAIL_Y - 70, rail_top - 40, length - 50, 140, 40)), STEEL))
    pulley = Part("HANDLER TOP PULLEY", g.sheave(rp, p.quadrant_rope_d / 2, holes=6), YELLOW)
    cp = frame.add(pulley, T(*pc) @ Rot((1, 0, 0), 90))
    frame.add(Part("PULLEY PIN", g.cyl(70.0, 600.0, pc + [0, -300, 0], (0, 1, 0)), STEEL))
    cf = A.add(frame)
    A.joint("Handler tilt", "rotate", [cf], (0, 0, 0), (0, -1, 0), [0.0, LOWER_TILT],
            {"by": "operator", "note": "tilts the handler up and over the stern (positive); the quadrant rides on it"})
    A.joint("Top pulley turn", "rotate", [[cf, cp]], pc, (0, -1, 0), None,
            cable_drive(rp, note="turned by the A&R wire once the handler tilts (positive = paying out)"))
    # hinge brackets on the transom (fixed)
    for sy in (-1, 1):
        br = [g.box(-500, sy * RAIL_Y + o, zd, 800, 120, -zd + 450) for o in (-420.0, 300.0)]
        br += [g.box(-650, sy * RAIL_Y - 450, zd, 1000, 900, 40)]
        A.add(Part("HINGE BRACKET", g.fuse(*br), YELLOW))
    A.add(Part("HINGE PIN", g.cyl(120.0, 2 * RAIL_Y + 1000, (0, -RAIL_Y - 500, 0), (0, 1, 0)), STEEL))
    # tilt cylinders: base pins on deck brackets just forward of the transom, outboard of the hinge brackets; rod pins
    # on the frame's sides. The base pin is nearer the hinge than the rod pin (806 < 1507 mm), so the cylinder's angle
    # changes the same way over the whole tilt and never stands still (task 0091: with the base pins forward of the
    # frame's end it stood still near 75°, where the clash check's step between frames lost the rod in its barrel)
    cyls = []
    yc = RAIL_Y + 700.0
    base = np.array([-400.0, 0.0, -700.0])
    rodpin = np.array([1500.0, 0.0, -150.0])
    L0 = float(np.linalg.norm(base - rodpin))
    Lb = L0 - 450.0
    barrel = kit.get(("handler_barrel", round(Lb)), lambda: Part("BARREL", g.fuse(
        g.tube(180.0, 115.0, Lb, (0, 0, 0)), g.cyl(180.0, 60.0, (0, 0, 0))), YELLOW))      # bore 15 mm round the rod
    rod = kit.get(("handler_rod", round(L0)), lambda: Part("PISTON ROD", g.cyl(100.0, L0 - 200.0, (0, 0, 0)), CHROME))
    for sy in (-1, 1):
        b = base + [0, sy * yc, 0]
        r = rodpin + [0, sy * yc, 0]
        d = (r - b) / np.linalg.norm(r - b)
        A.add(Part("CYLINDER BRACKET", g.fuse(g.box(b[0] - 300, b[1] - 250, zd, 600, 500, 40),
                                              g.box(b[0] - 150, b[1] - 250, zd, 300, 60, 450),
                                              g.box(b[0] - 150, b[1] + 190, zd, 300, 60, 450)), YELLOW))
        cyl = Asm("HANDLER HYDRAULIC CYLINDER")
        cyl.add(barrel, g.on_axis(b, d))
        cr_ = cyl.add(rod, g.on_axis(r, -d))
        cc = A.add(cyl)
        cyls.append({"barrel": [cc], "rod": [cc, cr_], "barrel_pin": b.tolist(), "rod_pin": r.tolist(),
                     "rod_pin_on": "HANDLER FRAME"})
        y0, y1 = sorted((sy * (RAIL_Y + 200.0), sy * (yc + 150.0)))
        frame.add(Part("CYLINDER LUG", g.box(rodpin[0] - 200, y0, -350, 400, y1 - y0, 400), YELLOW))
    A.info.update({"pulley_centre": pc.tolist(), "pulley_r": rp, "frame_path": [cf], "pulley_path": [cf, cp],
                   "cylinders": cyls, "rail_top": rail_top, "frame": frame, "frame_part_path": [cf, frame.children[0]],
                   "pulley_exit": [tp["exit"][0], 0.0, tp["exit"][1]], "eye_end": [tp["eye"][0], 0.0, tp["eye"][1]]})
    return A


# ---------------------------------------------------------------------------------------------------------
# Swivel sheave (tipping wires)
# ---------------------------------------------------------------------------------------------------------

def swivel_sheave(p, kit: Kit, rope_d: float, rp: float, height: float, rope_z: float, head_deg: float = 0.0) -> Asm:
    """A hollow post from the deck with a sheave head that swivels about the post's axis (task 0095: the tipping wire
    comes in along that axis, so the head can turn to any side and the wire still meets its sheave). Local: the post's
    foot at the origin; the wire comes from its winch along -x at height ``rope_z``, goes under the foot sheave (its
    centre at (-rf, 0, rope_z + rf), fixed, in a window of the post) and up the post's axis to the head; the head
    sheave's centre is ``rp`` out from the axis along the head's x at ``height`` (the wire meets it on the axis), the
    head turned ``head_deg`` about z. The wire over the head sheave and on to the D is made by the demo project (it
    moves); the parts it meets: ``info``."""
    A = Asm("SWIVEL SHEAVE")
    rr = rope_d / 2
    rf = rp
    zb = height - rp - 700.0                  # the swivel bearing's foot
    zf = rope_z + rf                          # the foot sheave's centre
    post = g.tube(260.0, 120.0, zb, (0, 0, 0))
    post = g.cut(post, g.box(-400.0, -70.0, rope_z - 2 * rr - 60.0, 400.0, 140.0, 2 * rf + 4 * rr + 120.0))  # window
    A.add(Part("SHEAVE POST", g.fuse(post, g.cut(g.cyl(480.0, 40.0, (0, 0, 0)), g.cyl(120.0, 100.0, (0, 0, -10))),
                                     *[g.box(-2 * rf - 120.0, sy * 70.0 + (0 if sy > 0 else -40.0), zf - rf - 160.0,
                                             2 * rf + 240.0, 40.0, 2 * rf + 320.0) for sy in (-1, 1)]), YELLOW))
    cf = A.add(Part("FOOT SHEAVE", g.sheave(rf, rr, holes=5), YELLOW), T(-rf, 0, zf) @ Rot((1, 0, 0), 90))
    A.add(Part("SHEAVE PIN", g.cyl(50.0, 220.0, (-rf, -110.0, zf), (0, 1, 0)), STEEL))
    head = Asm("SWIVEL HEAD")
    # the turning bearing is a sleeve round the post's top, 15 mm clear of it all round and 20 mm above its top face:
    # they never touch while the head swivels (with the sea moving, the clash check's step between frames is a few mm
    # off for a slowly turning part, task 0091)
    head.add(Part("SWIVEL BEARING", g.fuse(g.tube(340.0, 275.0, 470.0, (0, 0, zb - 220.0)),
                                           g.tube(340.0, 80.0, 30.0, (0, 0, zb + 220.0))), MOTOR))
    zp = zb + 250.0                           # the head's base plate (a hole for the wire on the axis)
    xs0, xs1 = -330.0, 2.0 * rp - rr - 40.0      # the parked wire hangs from the sheave's far side, past the plates
    base = g.cut(g.box(xs0, -170, zp, xs1 - xs0, 340, 60), g.cyl(80.0, 200.0, (0, 0, zp - 50)))
    fork = [g.box(xs0 + 280.0, sy * 120 + (0 if sy > 0 else -50), zp, xs1 - xs0 - 280.0, 50, height + 150.0 - zp)
            for sy in (-1, 1)]
    head.add(Part("SHEAVE HEAD", g.fuse(base, *fork), YELLOW))
    cs = head.add(Part("TIPPING SHEAVE", g.sheave(rp, rr, holes=5), YELLOW), T(rp, 0, height) @ Rot((1, 0, 0), 90))
    head.add(Part("SHEAVE PIN", g.cyl(50.0, 340.0, (rp, -170, height), (0, 1, 0)), STEEL))
    ch = A.add(head, Rot((0, 0, 1), head_deg))
    A.info.update({"head": ch, "sheave": cs, "foot": cf, "foot_centre": [-rf, 0.0, zf], "foot_r": rf,
                   "head_centre": [rp, 0.0, height], "bearing_z": zb})
    return A


# ---------------------------------------------------------------------------------------------------------
# CPS: sets, rack, ramp and slide
# ---------------------------------------------------------------------------------------------------------

def cps_set(p, kit: Kit, length: float = 16000.0) -> Asm:
    """A cable protection system lying along +x from its nose (pull head) at the origin: pull head, grey tube,
    yellow segments, brown vertebrae, grey, yellow bend restrictors next to the cable. Outer Ø ~2 x the cable Ø."""
    def make():
        R0 = max(1.0 * p.cable_d, 120.0)                 # outer radius
        a = Asm("CPS SET")
        head = g.fuse(g.cone(0.25 * R0, R0 * 0.85, 700.0, (0, 0, 0), (1, 0, 0)), g.cyl(R0 * 0.85, 300.0, (700, 0, 0), (1, 0, 0)),
                      g.torus_piece((-0.2 * R0, 0, 0), (0, 1, 0), (-0.4 * R0, 0, 0), 2 * math.pi, 0.06 * R0))
        a.add(Part("PULL HEAD", head, STEEL))
        x = 1000.0
        tube_l = 0.28 * length
        a.add(Part("CPS TUBE", g.fuse(g.cyl(R0 * 0.9, tube_l, (x, 0, 0), (1, 0, 0)),
                                      g.cyl(R0, 120.0, (x, 0, 0), (1, 0, 0))), CPS_GREY))
        x += tube_l
        seg_l = 500.0
        seg = kit.get(("cps_seg", R0), lambda: Part("CPS SEGMENT", g.fuse(
            g.cyl(R0, seg_l - 60, (0, 0, 0), (1, 0, 0)), g.cyl(R0 * 0.8, 60.0, (seg_l - 60, 0, 0), (1, 0, 0))), CPS_YELLOW))
        for k in range(int(0.18 * length / seg_l)):
            a.add(seg, T(x, 0, 0))
            x += seg_l
        vl = 380.0
        vert = kit.get(("cps_vert", R0), lambda: Part("CPS VERTEBRA", g.fuse(
            g.cyl(R0 * 0.82, vl, (0, 0, 0), (1, 0, 0)), g.cyl(R0 * 1.02, vl * 0.45, (vl * 0.25, 0, 0), (1, 0, 0))),
            CPS_BROWN))
        for k in range(int(0.26 * length / vl)):
            a.add(vert, T(x, 0, 0))
            x += vl
        gl = 0.08 * length
        a.add(Part("CPS SLEEVE", g.cyl(R0 * 0.85, gl, (x, 0, 0), (1, 0, 0)), CPS_GREY))
        x += gl
        bl = 450.0
        br = kit.get(("cps_br", R0), lambda: Part("BEND RESTRICTOR ELEMENT", g.fuse(
            g.cone(R0 * 0.95, R0 * 0.75, bl - 60, (0, 0, 0), (1, 0, 0)), g.cyl(R0 * 0.95, 60.0, (bl - 60, 0, 0), (1, 0, 0))),
            CPS_YELLOW))
        while x + bl <= length:
            a.add(br, T(x, 0, 0))
            x += bl
        a.info.update({"length": x, "outer_r": R0})
        return a
    return kit.get(("cps_set", length), make)


def cps_rack(x0: float, x1: float, rows_y: list, levels_z: list, deck_z: float, R0: float) -> Part:
    """The CPS rack along the deck (model coordinates): posts every ~3 m outside the rows, cross beams under each
    level, a cradle rail under each row. Placed at I."""
    y_lo, y_hi = min(rows_y) - R0 - 400.0, max(rows_y) + R0 + 400.0
    xs = np.linspace(x0, x1, max(2, int((x1 - x0) / 3000.0) + 1))
    parts = []
    for x in xs:
        for y in (y_lo, y_hi):
            parts.append(g.box(x - 100, y - 100, deck_z, 200, 200, max(levels_z) + R0 + 300 - deck_z))
        for z in levels_z:
            parts.append(g.box(x - 100, y_lo - 100, z - R0 - 220, 200, y_hi - y_lo + 200, 160))
            for y in rows_y:
                parts.append(g.box(x - 60, y - R0 - 40, z - R0 - 61, 120, 80, 61 + 0.4 * R0))
                parts.append(g.box(x - 60, y + R0 - 40, z - R0 - 61, 120, 80, 61 + 0.4 * R0))
    for z in levels_z:
        for y in rows_y:
            parts.append(g.box(x0 - 100, y - 0.35 * R0 - 30, z - R0 - 70, x1 - x0 + 200, 60, 20))
            parts.append(g.box(x0 - 100, y + 0.35 * R0 - 30, z - R0 - 70, x1 - x0 + 200, 60, 20))
    parts.append(g.box(x0 - 100, y_lo - 100, max(levels_z) + R0 + 300 - 160, x1 - x0 + 200, 200, 160))
    parts.append(g.box(x0 - 100, y_hi - 100, max(levels_z) + R0 + 300 - 160, x1 - x0 + 200, 200, 160))
    return Part("CPS RACK", g.fuse(*parts), YELLOW)


def trough_along(route, start: float, end: float, R0: float, twist_deg: float = 0.0, step: float = 600.0):
    """A shallow U trough (inner radius R0 + 60) under a path (route from s = start to end); twisting by
    ``twist_deg`` about the path from start to end (the orange ramp)."""
    pts, frames = [], []
    total = route.length
    s_vals = np.linspace(start, min(end, total), max(2, int((min(end, total) - start) / step) + 1))
    for s in s_vals:
        acc = 0.0
        for seg in route.segments:
            if s <= acc + seg.length + 1e-9:
                q = seg.point(s - acc)
                t = seg.tangent(s - acc) if seg.kind == "arc" else seg.tangent()
                break
            acc += seg.length
        side = np.cross([0, 0, 1.0], t)
        side /= np.linalg.norm(side)
        up = np.cross(t, side)
        tw = math.radians(twist_deg * (s - start) / max(end - start, 1.0))
        side2 = side * math.cos(tw) + up * math.sin(tw)
        up2 = np.cross(t, side2)
        pts.append(q)
        frames.append((side2, up2))
    ri, ro = R0 + 60.0, R0 + 120.0
    prof = []
    for k in range(9):                                   # outer arc of the U, then the inner arc back
        a = math.radians(-180.0 + 180.0 * k / 8)
        prof.append((ro * math.cos(a), ro * math.sin(a) * 0.75))
    for k in range(8, -1, -1):
        a = math.radians(-180.0 + 180.0 * k / 8)
        prof.append((ri * math.cos(a), ri * math.sin(a) * 0.75))
    return g.trough(pts, frames, prof), pts


# ---------------------------------------------------------------------------------------------------------
# Quay
# ---------------------------------------------------------------------------------------------------------

def quay(x0: float, x1: float, y_edge: float, depth: float, z_top: float) -> Asm:
    """A quay along x (model coordinates): concrete slab from y_edge outwards (-y) by ``depth``, top at z_top,
    fenders on its face, bollards near the edge."""
    a = Asm("QUAY")
    a.add(Part("QUAY SLAB", g.fuse(g.box(x0, y_edge - depth, -6000.0, x1 - x0, depth, z_top + 6000.0),
                                   g.box(x0, y_edge - 400.0, z_top, x1 - x0, 400.0, 250.0)), CONCRETE))
    fender = Part("QUAY FENDER", g.fuse(g.cyl(700.0, 2400.0, (0, 0, 0), (0, 0, 1)),
                                        g.box(-300, -900, 400, 600, 300, 1600)), FENDER_BLACK)
    bollard = Part("BOLLARD", g.fuse(g.cyl(220.0, 600.0, (0, 0, 0)), g.cyl(320.0, 120.0, (0, 0, 600)),
                                     g.box(-400, -400, 0, 800, 800, 40)), DARK)
    for x in np.arange(x0 + 6000.0, x1 - 3000.0, 16000.0):
        a.add(fender, T(x, y_edge + 700.0, z_top - 3200.0))
        a.add(bollard, T(x + 4000.0, y_edge - 1200.0, z_top))
    return a
