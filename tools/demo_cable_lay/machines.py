"""The machines of the demo cable-lay spread (task 0076), each an ``Asm`` in its own coordinates with its joints.

Invented from general engineering knowledge; nothing copied from a company, vessel or product. Part names are
generic English words the app's part-type library sorts (sheaves, rollers, cylinders, motors, gearboxes …).
"""

from __future__ import annotations

import math

import numpy as np

from . import geom as g
from .geom import Asm, Part, Rot, T

# ---- colours (sRGB) ---------------------------------------------------------------------------------------
YELLOW = (0.976, 0.659, 0.0)         # common offshore machine yellow
DARK = (0.13, 0.13, 0.14)            # tracks, pads
STEEL = (0.58, 0.59, 0.60)           # rollers, shafts, pins
CHROME = (0.86, 0.87, 0.88)
MOTOR = (0.20, 0.22, 0.24)
HULL_BLUE = (0.09, 0.17, 0.32)
HULL_RED = (0.55, 0.12, 0.10)
DECK_GREY = (0.42, 0.44, 0.45)
WHITE = (0.93, 0.93, 0.91)
GLASS = (0.10, 0.14, 0.18)
CABLE_BLACK = (0.04, 0.04, 0.04)
ROPE_GREY = (0.45, 0.46, 0.47)
CPS_ORANGE = (0.95, 0.42, 0.05)
FRAME_GREY = (0.30, 0.32, 0.34)


def cable_drive(r_contact: float, **extra) -> dict:
    """A part turned by the cable (or a rope) running over it at ``r_contact``: degrees per mm of payout."""
    d = {"by": "cable", "deg_per_mm": round(360.0 / (2 * math.pi * r_contact), 9), "contact_radius": round(r_contact, 4)}
    d.update(extra)
    return d


def turn_axis(centre, contact, velocity) -> np.ndarray:
    """Axis direction that makes a positive turn move the contact point along ``velocity`` (r x v)."""
    a = np.cross(np.asarray(contact, float) - np.asarray(centre, float), np.asarray(velocity, float))
    return a / np.linalg.norm(a)


# ---------------------------------------------------------------------------------------------------------
# Small parts shared by several machines
# ---------------------------------------------------------------------------------------------------------

class Kit:
    """Builds each shared part once (the app instances one mesh for every place)."""

    def __init__(self, p):
        self.p = p
        self._cache: dict = {}

    def get(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    def roller(self, r: float = 125.0, length: float = 700.0, name: str = "CABLE ROLLER") -> Part:
        """Cable roller about local y (centred), slightly waisted so the cable stays in the middle."""
        def make():
            h = length / 2
            prof = [(30.0, -h - 60), (55.0, -h - 60), (55.0, -h), (r + 15.0, -h), (r + 15.0, -h + 40),
                    (r, -h + 120), (r, h - 120), (r + 15.0, h - 40), (r + 15.0, h), (55.0, h), (55.0, h + 60),
                    (30.0, h + 60)]
            return Part(name, g.revolve(prof, (0, 0, 0), (0, 1, 0)), STEEL)
        return self.get(("roller", name, r, length), make)

    def roller_stand(self, h: float, width: float = 900.0) -> Part:
        """Stand from the deck (z = 0) up to a roller's axle at height h: two posts and a cross beam."""
        def make():
            w = width / 2
            parts = [g.box(-150, -w - 60, 0, 300, 120, h + 80), g.box(-150, w - 60, 0, 300, 120, h + 80),
                     g.box(-200, -w - 100, 0, 400, 2 * w + 200, 30), g.box(-150, -w, 0.45 * h, 300, 2 * w, 120)]
            return Part("ROLLER STAND", g.fuse(*parts), YELLOW)
        return self.get(("stand", round(h), width), make)

    def pillow_block(self, bore: float, h: float = 240.0) -> Part:
        """Bearing block about local y; two bolt holes (Ø26) through its foot at x = +-0.55 h."""
        def make():
            s = g.cut(g.fuse(g.box(-h * 0.7, -h * 0.35, -h / 2, h * 1.4, h * 0.7, h * 0.55),
                             g.cyl(h * 0.45, h * 0.7, (0, -h * 0.35, 0), (0, 1, 0))),
                      g.cyl(bore, h * 2, (0, -h, 0), (0, 1, 0)),
                      *[g.cyl(13.0, h, (x, 0, -h), (0, 0, 1)) for x in (-0.55 * h, 0.55 * h)])
            return Part("PILLOW BLOCK", s, MOTOR)
        return self.get(("pillow", bore, h), make)

    def bolt(self, d: int = 24, length: float = 120.0) -> Part:
        """Hexagon head bolt ISO 4017 (head on top at z = 0 .. k, shank down from z = 0)."""
        s, k = {24: (36.0, 15.0), 16: (24.0, 10.0)}[d]

        def make():
            r = s / math.sqrt(3.0)
            hexa = g.polygon_prism([(r * math.cos(math.pi / 6 + i * math.pi / 3), r * math.sin(math.pi / 6 + i * math.pi / 3))
                                    for i in range(6)], k)
            return Part(f"ISO 4017 M{d} x {length:.0f} - 8.8", g.fuse(hexa, g.cyl(d / 2 - 0.5, length + 1, (0, 0, -length))),
                        STEEL)
        return self.get(("bolt", d, length), make)

    def gearbox(self, r: float, length: float) -> Part:
        def make():
            s = g.fuse(g.cyl(r, length, (0, 0, 0), (0, 1, 0)),
                       g.cyl(r * 1.15, length * 0.12, (0, 0, 0), (0, 1, 0)))
            return Part("PLANETARY GEARBOX", s, MOTOR)
        return self.get(("gearbox", r, length), make)

    def motor(self, r: float, length: float) -> Part:
        def make():
            s = g.fuse(g.cyl(r, length, (0, 0, 0), (0, 1, 0)),
                       g.box(-r * 0.5, length * 0.3, r * 0.8, r, length * 0.4, r * 0.5))
            return Part("HYDRAULIC MOTOR", s, MOTOR)
        return self.get(("motor", r, length), make)

    def shaft(self, r: float, length: float) -> Part:
        return self.get(("shaft", r, length),
                        lambda: Part("SHAFT", g.cyl(r, length, (0, -length / 2, 0), (0, 1, 0)), STEEL))


# ---------------------------------------------------------------------------------------------------------
# Vessel
# ---------------------------------------------------------------------------------------------------------

# Stations of the hull: x (from the stern for the aft ones, from the bow for the forward ones), deck
# half-breadth, flat-bottom half-breadth, keel z, bilge radius. Between stations the hull is ruled (straight):
# light to mesh (a smooth loft gave 1.4 M triangles at Normal), and the deck outline is exactly the polygon.
AFT = [(0, 12600, 7000, -1500, 2600), (4000, 13100, 8800, -3200, 2500), (9000, 13400, 10200, -4800, 2300),
       (15000, 13500, 11000, -5700, 2200), (22000, 13500, 11300, -6000, 2200)]
FORE = [(36000, 13500, 11300, -6000, 2200), (30000, 13400, 10600, -6000, 2500), (24000, 13000, 9000, -6000, 3200),
        (19000, 12300, 7000, -6000, 3900), (15000, 11400, 5000, -5900, 4400), (11500, 10300, 3200, -5700, 4500),
        (8500, 9000, 1800, -5400, 4300), (6000, 7500, 900, -5000, 3900), (4000, 6000, 400, -4600, 3300),
        (2300, 4400, 150, -4100, 2500), (1000, 2800, 60, -3500, 1600), (100, 900, 30, -2800, 500)]


def hull_stations(p, length: float) -> list:
    return [s for s in AFT] + [(length - s[0],) + s[1:] for s in FORE]


def _tangent_point(c, r, d):
    dx, dz = d[0] - c[0], d[1] - c[1]
    L = math.hypot(dx, dz)
    a = math.atan2(dz, dx)
    b = math.acos(r / L)
    ang = a - b
    return (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)), ang


def _hull_section(x, bd, bb, k, r, deck):
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


def _offset_polygon(pts, d):
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


def vessel(p, pos) -> Asm:
    """Generic cable-lay vessel: hull (ruled between stations), deck, bulwark, deckhouse forward, carousel well
    amidships, open stern for the chute and the quadrant. Waterline at z = 0."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    L = pos["length"]
    st = hull_stations(p, L)
    loft = BRepOffsetAPI_ThruSections(True, True, 1e-6)
    for s in st:
        loft.AddWire(_hull_section(*s, p.deck_z))
    loft.CheckCompatibility(False)
    loft.Build()
    hull = loft.Shape()
    well_r = p.carousel_d / 2 + 900.0
    well_floor = -700.0
    well = g.cyl(well_r, p.deck_z - well_floor + 2000, (pos["carousel_x"], 0, well_floor))
    big = 4 * L
    below = g.box(-L, -big / 2, -big, 3 * L, big, big)
    deck_t = 40.0
    a = Asm("VESSEL")
    bottom = g.cut(g.common(hull, below), well)
    top = g.cut(g.common(hull, g.box(-L, -big / 2, 0.0, 3 * L, big, p.deck_z - deck_t)), well)
    deck = g.cut(g.common(hull, g.box(-L, -big / 2, p.deck_z - deck_t, 3 * L, big, 2 * deck_t)), well)
    a.add(Part("HULL BOTTOM", bottom, HULL_RED))
    a.add(Part("HULL", top, HULL_BLUE))
    a.add(Part("MAIN DECK", deck, DECK_GREY))
    # well lining (grey) so the well does not show the hull's colours
    lining = g.fuse(g.tube(well_r + 1.0, well_r - 30.0, p.deck_z - well_floor, (pos["carousel_x"], 0, well_floor)),
                    g.cyl(well_r - 30.0, 30.0, (pos["carousel_x"], 0, well_floor)))
    a.add(Part("CAROUSEL WELL", lining, DECK_GREY))
    # bulwark on the deck edge (the outline is the stations' polygon), open at the stern for the chute/quadrant
    outline = [(s[0], -s[1]) for s in st] + [(s[0], s[1]) for s in reversed(st)]
    inner = _offset_polygon(outline, 160.0)
    bw = g.cut(g.polygon_prism(outline, 1100.0, T(0, 0, p.deck_z)), g.polygon_prism(inner, 1200.0, T(0, 0, p.deck_z - 50)))
    bw = g.cut(bw, g.box(-2000, p.quadrant_y - 3200, p.deck_z - 100, 4500, abs(p.quadrant_y) + 4400, 1500))
    a.add(Part("BULWARK", bw, HULL_BLUE))
    # deckhouse forward: three decks, the bridge with wings and windows, a mast
    x0 = L - 28000.0
    house = g.fuse(g.box(x0, -9000, p.deck_z, 16000, 18000, 3000),
                   g.box(x0 + 2000, -8000, p.deck_z + 3000, 13000, 16000, 3000),
                   g.box(x0 + 6000, -10500, p.deck_z + 6000, 8500, 21000, 3000))
    a.add(Part("DECKHOUSE", house, WHITE))
    a.add(Part("BRIDGE WINDOW", g.box(x0 + 14500, -9800, p.deck_z + 7200, 60, 19600, 1200), GLASS))
    a.add(Part("DECKHOUSE WINDOW", g.box(x0 + 1980, -7700, p.deck_z + 4000, 40, 15400, 1000), GLASS))
    mast = g.fuse(g.rod((x0 + 10000, 0, p.deck_z + 9000), (x0 + 10000, 0, p.deck_z + 17000), 250.0),
                      g.rod((x0 + 10000, -2500, p.deck_z + 15000), (x0 + 10000, 2500, p.deck_z + 15000), 120.0))
    a.add(Part("MAST", mast, WHITE))
    a.info["length"] = L
    a.info["deck_outline"] = [[round(x, 1), round(y, 1)] for x, y in outline]
    return a


# ---------------------------------------------------------------------------------------------------------
# Carousel (+ loading arm and tower)
# ---------------------------------------------------------------------------------------------------------


def carousel(p, kit: Kit, name: str = "CAROUSEL", outer_d: float | None = None, rim_h: float | None = None,
             core_r: float | None = None, coil_h: float | None = None, loading_arm: dict | None = None,
             base_frame: bool = False) -> Asm:
    """Turntable on support rollers, inner core, rim fence, the stored cable coil, four friction drive units.

    Local: turntable axis = z through the origin, the turntable's underside at z = 0. ``loading_arm``: the
    positions for the loading tower + slewing arm + trolley (vessel carousel only)."""
    Ro = (outer_d or p.carousel_d) / 2
    Rc = core_r or p.core_r
    rim_h = rim_h or p.rim_h
    coil_h = coil_h or p.coil_h
    tt = p.turntable_t
    a = Asm(name)
    # -- the turning part
    turn = Asm(name + " TURNTABLE")
    table = g.cut(g.cyl(Ro, tt), g.cyl(900.0, tt + 10, (0, 0, -5)))
    turn.add(Part("TURNTABLE", table, YELLOW))
    turn.add(Part("INNER CORE", g.fuse(g.tube(Rc, Rc - 60, rim_h, (0, 0, tt)),
                                       g.tube(Rc + 150, Rc - 60, 60, (0, 0, tt + rim_h - 60))), YELLOW))
    n_post = max(24, int(2 * math.pi * Ro / 1600))
    posts = [g.xform(g.box(-90, -60, 0, 180, 120, rim_h), Rot((0, 0, 1), 360.0 * k / n_post) @ T(Ro - 90, 0, tt))
             for k in range(n_post)]
    rings = [g.torus_piece((0, 0, z), (0, 0, 1), (Ro - 90, 0, z), 2 * math.pi, 45.0)
             for z in (tt + 0.35 * rim_h, tt + 0.7 * rim_h, tt + rim_h - 45)]
    turn.add(Part("RIM FENCE", g.fuse(*posts, *rings), YELLOW))
    coil_in, coil_out = Rc + 60.0, Ro - 300.0
    coil = g.tube(coil_out, coil_in, coil_h, (0, 0, tt))
    turn.add(Part("CABLE COIL", coil, CABLE_BLACK))
    tc = a.add(turn)
    a.joint("Carousel turn", "rotate", [tc], (0, 0, 0), (0, 0, -1), None,
            {"by": "carousel", "deg_per_mm": round(360.0 / (2 * math.pi * p.coil_r), 9),
             "note": "turns clockwise seen from above while paying out; degrees per mm = 360 / (2 pi x the coil "
                     "radius at the loading arm's guide), here at the rest radius"},
            rest_coil_radius=p.coil_r)
    # -- support rollers (fixed brackets under the turntable): an outer and an inner ring
    rr = 220.0
    roller = kit.roller(rr, 500.0, "SUPPORT ROLLER")
    zf = -(700.0 - rr)                                  # the well floor, from the roller's centre
    bracket = kit.get(("sup_bracket", rr), lambda: Part("ROLLER BRACKET", g.fuse(
        g.box(-300, -400, zf, 600, 800, 60), g.box(-300, -380, zf + 59, 600, 60, -zf - 59 + 80),
        g.box(-300, 320, zf + 59, 600, 60, -zf - 59 + 80)), YELLOW))
    for ring_r, n in ((Ro - 900.0, max(16, int(2 * math.pi * (Ro - 900) / 3000))),
                      (Rc + 1200.0, max(8, int(2 * math.pi * (Rc + 1200) / 3000)))):
        for k in range(n):
            ang = 360.0 * (k + 0.5) / n
            M = Rot((0, 0, 1), ang) @ T(ring_r, 0, -rr) @ Rot((0, 0, 1), 90)
            c = a.add(roller, M)
            a.add(bracket, Rot((0, 0, 1), ang) @ T(ring_r, 0, -rr) @ Rot((0, 0, 1), 90))
            ctr = (M @ np.r_[0, 0, 0, 1.0])[:3]
            axis = M[:3, 1]
            contact = ctr + np.array([0, 0, rr])
            vel = np.cross([0, 0, -1.0], contact)          # the turntable's underside, turning about -z
            ax = turn_axis(ctr, contact, vel)
            a.joint(f"Support roller {ring_r:.0f}-{k + 1} turn", "rotate", [c], ctr, ax, None,
                    {"by": "follows", "follows": "Carousel turn", "ratio": round(ring_r / rr, 6),
                     "note": "rolls under the turntable"})
    # centre slewing ring under the turntable's middle
    a.add(Part("CENTRE SLEWING RING", g.fuse(g.tube(1100, 700, 250, (0, 0, -250)),
                                             g.tube(1300, 600, 450, (0, 0, -700))), MOTOR))
    # -- four friction drive units on the rim
    wr = 300.0
    wheel = kit.get(("drive_wheel", wr), lambda: Part("FRICTION DRIVE WHEEL", g.revolve(
        [(80, -160), (wr, -160), (wr, 160), (80, 160)]), DARK))
    gb = kit.gearbox(240.0, 500.0)
    mo = kit.motor(160.0, 420.0)
    # bracket: a column from the well floor behind the wheel, an arm over the motor
    zfl = -700.0 - tt / 2
    dbr = kit.get(("drive_bracket",), lambda: Part("DRIVE BRACKET", g.fuse(
        g.box(wr + 20, -250, zfl, 250, 500, 1080 + 200 - zfl + 1), g.box(-300, -250, 1280, wr + 570, 500, 120)), YELLOW))
    for k in range(4):
        ang = 45.0 + 90.0 * k
        R0 = Rot((0, 0, 1), ang)
        ctr = (R0 @ np.r_[Ro + wr, 0, tt / 2, 1.0])[:3]
        unit = Asm("DRIVE UNIT")
        cw = unit.add(wheel, T(0, 0, 0))
        unit.add(gb, T(0, 0, 160) @ Rot((1, 0, 0), 90))
        unit.add(mo, T(0, 0, 660) @ Rot((1, 0, 0), 90))
        unit.add(dbr, T(0, 0, 0))
        cu = a.add(unit, T(*ctr) @ R0)
        contact = (R0 @ np.r_[Ro, 0, tt / 2, 1.0])[:3]
        vel = np.cross([0, 0, -1.0], contact)
        ax = turn_axis(ctr, contact, vel)
        a.joint(f"Drive wheel {k + 1} turn", "rotate", [[cu, cw]], ctr, ax, None,
                {"by": "follows", "follows": "Carousel turn", "ratio": round(Ro / wr, 6),
                 "note": "friction wheel on the turntable's edge"})
    if base_frame:                       # standalone (quay / deck) version: on a ring of deck beams
        beams = [g.xform(g.box(-Ro - 600, -200, -1200, 2 * Ro + 1200, 400, 500), Rot((0, 0, 1), 45.0 * k))
                 for k in range(4)]
        a.add(Part("CAROUSEL BASE FRAME", g.fuse(*beams), YELLOW))
    a.info["coil"] = {"inner_r": coil_in, "outer_r": coil_out, "bottom_z": tt, "top_z": tt + coil_h}
    if loading_arm:
        _loading_arm(p, kit, a, loading_arm)
    return a


def _arc_rollers(kit, asm, centre_xz, R_path, a0, a1, cable_r, step_deg, name, y=0.0, chain=None, joint_prefix="",
                 velocity_sign=1.0, plate_name="RADIUS CONTROLLER"):
    """Rollers on the inside of a cable bend (between the cable and the bend's centre), in a vertical x-z plane.

    a0 -> a1: angles (deg, from +x towards +z) of the bend; the cable travels from a0 to a1. Adds a joint per roller
    (turned by the cable) and two side plates holding them. Returns the roller children."""
    rr = 125.0
    roller = kit.roller(rr, 700.0)
    Rr = R_path - cable_r - rr
    cx, cz = centre_xz
    n = max(2, int(abs(a1 - a0) / step_deg) + 1)
    out = []
    sgn = 1.0 if a1 > a0 else -1.0
    for k in range(n):
        ang = math.radians(a0 + (a1 - a0) * (k + 0.5) / n)
        ctr = np.array([cx + Rr * math.cos(ang), y, cz + Rr * math.sin(ang)])
        c = asm.add(roller, T(*ctr))
        contact = np.array([cx + (R_path - cable_r) * math.cos(ang), y, cz + (R_path - cable_r) * math.sin(ang)])
        tang = sgn * np.array([-math.sin(ang), 0.0, math.cos(ang)])  # travel direction at that angle
        ax = turn_axis(ctr, contact, tang * velocity_sign)
        path = [c]
        asm.joint(f"{joint_prefix}{name} {k + 1} turn", "rotate", [path], ctr, ax, None, cable_drive(rr))
        out.append(c)
    # side plates: an annular sector from just inside the rollers out to the cable's centre
    r_in, r_out = Rr - rr - 250.0, R_path - cable_r * 0.3
    lo, hi = sorted((a0, a1))
    pts = []
    for k in range(25):
        t = math.radians(lo + (hi - lo) * k / 24)
        pts.append((cx + r_out * math.cos(t), cz + r_out * math.sin(t)))
    for k in range(25):
        t = math.radians(hi - (hi - lo) * k / 24)
        pts.append((cx + r_in * math.cos(t), cz + r_in * math.sin(t)))
    rb = r_in + 90.0                                     # two tie bars join the plates inside the rollers
    bars = [g.box_c((cx + rb * math.cos(math.radians(t)), 0.0, cz + rb * math.sin(math.radians(t))), (120, 770, 120))
            for t in (lo + 0.25 * (hi - lo), lo + 0.75 * (hi - lo))]
    plate = kit.get(("rc_plate", round(r_in), round(r_out), lo, hi, cx, cz),
                    lambda: Part(plate_name, g.fuse(
                        g.polygon_prism(pts, 30.0, g.Frame((0, 380.0, 0), (1, 0, 0), (0, -1, 0))),
                        g.polygon_prism(pts, 30.0, g.Frame((0, -350.0, 0), (1, 0, 0), (0, -1, 0))), *bars), YELLOW))
    asm.add(plate, T(0, y, 0))
    return out


def _loading_arm(p, kit, a, la):
    """Loading tower (fixed, with the bottom radius controller), slewing arm (tower-top radius controller, arm
    rollers) and the trolley with the guide sheave that moves in/out over the coil."""
    R = p.bend_r
    cr = p.cable_r
    xt = la["tower_x"]                 # local x of the slewing axis
    za, zl, zd = la["arm_z"], la["line_z"], la["deck_z"]
    xg = la["guide_x"]                 # local x of the vertical rise at rest
    # ---- tower (fixed): four legs, ring beam, the slewing ring, bottom radius controller
    z_ring = zl + R + 400.0
    tower = Asm("LOADING TOWER")
    legs = [g.box(xt + sx * 1300 - 200, sy * 1300 - 200, zd, 400, 400, z_ring - zd)
            for sx in (-1, 1) for sy in (-1, 1)]
    braces = [g.beam((xt + sx * 1300, -1300, zd + h0), (xt + sx * 1300, 1300, zd + h0 + 1800), 160.0)
              for sx in (-1, 1) for h0 in (500.0, 3000.0)]
    ring_beam = g.cut(g.box(xt - 1600, -1600, z_ring - 400, 3200, 3200, 400), g.cyl(1150, 600, (xt, 0, z_ring - 500)))
    tower.add(Part("TOWER COLUMN", g.fuse(*legs, *braces, ring_beam), YELLOW))
    tower.add(Part("SLEWING RING", g.tube(1400, 1000, 250, (xt, 0, z_ring)), MOTOR))
    tw = a.add(tower)
    _arc_rollers(kit, tower, (xt - R, zl + R), R, 0.0, -90.0, cr, 9.0, "Tower bottom roller", chain=[tw],
                 joint_prefix="")
    # ---- slewing arm
    arm = Asm("LOADING ARM")
    z_h = z_ring + 250.0
    beam_z0 = za - cr - 1000.0                  # arm beams: their top 400 mm under the cable
    x_far = la["x_far"]
    arm.add(Part("SLEW HOUSING", g.cut(g.cyl(1350, 400, (xt, 0, z_h)), g.cyl(950, 500, (xt, 0, z_h - 50))), YELLOW))
    posts = [g.box(xt + sx * 1000 - 150, sy * 850 - 150, z_h + 399, 300, 300, beam_z0 - z_h - 398)
             for sx in (-1, 1) for sy in (-1, 1)]
    beams = [g.box(xt - 1500, sy * 850 - 150, beam_z0, x_far - xt + 1500, 300, 600) for sy in (-1, 1)]
    ties = [g.box(xt - 1500, -850, beam_z0, 300, 1700, 200)]       # none at the far end: the guide sheave passes
    arm.add(Part("LOADING ARM BEAM", g.fuse(*posts, *beams, *ties), YELLOW))
    ca = a.add(arm)
    a.joint("Loading arm slew", "rotate", [ca], (xt, 0, z_h), (0, 0, 1), [-40.0, 40.0],
            {"by": "operator", "note": "points the guide over the coil; the carousel's turn does the rest"})
    # tower-top radius controller: cable from the arm (heading -x) bends down onto the slewing axis
    _arc_rollers(kit, arm, (xt + R, za - R), R, 90.0, 180.0, cr, 9.0, "Tower top roller", chain=[ca])
    # between the two bends the cable spans freely (a few metres)
    # ---- trolley with the guide sheave (rest pose: the cable rises at xg into the sheave)
    trol = Asm("ARM TROLLEY")
    wc = np.array([xg - R, 0.0, za - R])
    sheave = Part("GUIDE SHEAVE", g.sheave(R, cr, hub_r=600.0, bore_r=200.0, holes=8), YELLOW)
    cs = trol.add(sheave, T(*wc) @ Rot((1, 0, 0), 90))
    side = [g.box(wc[0] - 900, sy * 560 - 60, wc[2] - 400, 1800, 120, beam_z0 + 600 - wc[2] + 401)
            for sy in (-1, 1)]
    axle = g.cyl(200, 1400, wc + [0, -700, 0], (0, 1, 0))          # the sheave turns on it
    top = g.fuse(*[g.box(wc[0] - 900, sy * 800 - 300, beam_z0 + 600, 1800, 600, 150) for sy in (-1, 1)])
    wheels = [g.cyl(140, 120, (wc[0] + sx * 600, sy * 1000 - 60, beam_z0 + 600 - 140 + 150), (0, 1, 0))
              for sx in (-1, 1) for sy in (-1, 1)]
    trol.add(Part("TROLLEY FRAME", g.fuse(*side, top, *wheels, axle), YELLOW))
    ct = arm.add(trol)
    lo = la["guide_x_min"] - xg
    hi = la["guide_x_max"] - xg
    a.joint("Loading arm in/out", "slide", [[ca, ct]], (xt, 0, za), (1, 0, 0), [round(lo, 3), round(hi, 3)],
            {"by": "operator", "note": "moves the guide between the coil's outer turn (min) and the core (max); "
                                       "follows the coil radius the cable comes off"})
    a.joint("Guide sheave turn", "rotate", [[ca, ct, cs]], wc, turn_axis(wc, wc + [0, 0, R], [-1, 0, 0]), None,
            cable_drive(R))
    a.info["guide_sheave"] = {"centre": wc.tolist(), "axis": [0, 1, 0], "pitch_r": R, "groove_r": cr,
                              "path": [ca, ct, cs]}
    a.info["loading_arm"] = {"slew_axis": [xt, 0.0, z_h], "trolley_path": [ca, ct], "arm_path": [ca]}


# ---------------------------------------------------------------------------------------------------------
# Track tensioner
# ---------------------------------------------------------------------------------------------------------


def track_pins(p, zs: float) -> list:
    """Pin centres of one track's chain loop in the x-z plane (local; sprockets at x = -a and +a, height zs).

    Starts at the drive sprocket's top tangent point and runs along the top (contact) run to +x, round the idler,
    back along the bottom run and round the drive sprocket: pads_per_track pins at exactly one pitch apart."""
    pp, nt, Rs = p.pad_pitch, p.sprocket_teeth, p.sprocket_r
    a = p.links_per_run * pp / 2
    pins = [(-a + k * pp, zs + Rs) for k in range(p.links_per_run)]
    step = 2 * math.pi / nt
    for k in range(nt // 2):
        t = math.pi / 2 - k * step
        pins.append((a + Rs * math.cos(t), zs + Rs * math.sin(t)))
    pins += [(a - k * pp, zs - Rs) for k in range(p.links_per_run)]
    for k in range(nt // 2):
        t = -math.pi / 2 - k * step
        pins.append((-a + Rs * math.cos(t), zs + Rs * math.sin(t)))
    return pins


PAD = {"len": 280.0, "width": 500.0, "t": 180.0, "v_depth": 100.0, "base": 80.0}
LINK = {"half_h": 60.0, "pin_r": 35.0}


def _pad_shape(p):
    L, W, t, vd = PAD["len"], PAD["width"], PAD["t"], PAD["v_depth"]
    half_top = vd * math.tan(p.pad_v_half_angle)
    body = g.box(-L / 2, -W / 2, 0, L, W, t)
    vee = g.polygon_prism([(-half_top, t + 1), (0.0, t - vd), (half_top, t + 1)], L + 20,
                          g.Frame((-L / 2 - 10, 0, 0), (0, 1, 0), (1, 0, 0)))
    base = g.box(-L / 2 + 20, -W / 2 + 40, -0.0, L - 40, W - 80, 20)
    return g.fuse(g.cut(body, vee), base)


def _link_shapes(p):
    pp, hh, pr = p.pad_pitch, LINK["half_h"], LINK["pin_r"]

    def plates(y0, y1, holes):
        s = g.fuse(g.box(-pp / 2, y0, -hh, pp, y1 - y0, 2 * hh),
                   g.cyl(hh, y1 - y0, (-pp / 2, y0, 0), (0, 1, 0)), g.cyl(hh, y1 - y0, (pp / 2, y0, 0), (0, 1, 0)))
        if holes:
            s = g.cut(s, g.cyl(pr + 1, 400, (-pp / 2, -200, 0), (0, 1, 0)), g.cyl(pr + 1, 400, (pp / 2, -200, 0), (0, 1, 0)))
        return s
    bush = [g.tube(pr + 15, pr + 1, 260.0, (x, -130, 0), (0, 1, 0)) for x in (-pp / 2, pp / 2)]
    inner = g.fuse(plates(-160, -130, True), plates(130, 160, True), *bush)
    outer = g.fuse(plates(-195, -165, False), plates(165, 195, False),
                   g.cyl(pr, 390, (-pp / 2, -195, 0), (0, 1, 0)), g.cyl(pr, 390, (pp / 2, -195, 0), (0, 1, 0)))
    return inner, outer


def _sprocket_shape(p):
    Rs, nt, pr = p.sprocket_r, p.sprocket_teeth, LINK["pin_r"]
    disc = g.cyl(Rs + 25.0, 120.0, (0, -60, 0), (0, 1, 0))       # stays inside the pads' bases on the wrap
    notches = [g.cyl(pr + 6, 200, (Rs * math.cos(2 * math.pi * k / nt), -100, Rs * math.sin(2 * math.pi * k / nt)),
                     (0, 1, 0)) for k in range(nt)]
    hub = g.cyl(200.0, 300.0, (0, -150, 0), (0, 1, 0))
    return g.cut(g.fuse(disc, hub), *notches, g.cyl(90, 400, (0, -200, 0), (0, 1, 0)))


def track(p, kit: Kit, name: str, zs: float) -> tuple:
    """One track (local: cable centre at the origin, pads facing +z on the contact run). Returns (asm, children):
    pads and links in loop order, the two sprockets."""
    pins = track_pins(p, zs)
    a = p.links_per_run * p.pad_pitch / 2
    inner, outer = kit.get(("links",), lambda: _link_shapes(p))
    pad = kit.get(("pad",), lambda: Part("TRACK PAD", _pad_shape(p), DARK))
    li = kit.get(("link_i",), lambda: Part("TRACK CHAIN LINK", inner, DARK))
    lo = kit.get(("link_o",), lambda: Part("TRACK CHAIN LINK", outer, DARK))
    spr = kit.get(("sprocket",), lambda: Part("DRIVE SPROCKET", _sprocket_shape(p), STEEL))
    idl = kit.get(("idler",), lambda: Part("IDLER SPROCKET", _sprocket_shape(p), STEEL))
    t = Asm(name)
    pads, links, frames = [], [], []
    n = len(pins)
    for k in range(n):
        p0, p1 = np.array(pins[k]), np.array(pins[(k + 1) % n])
        mid = (p0 + p1) / 2
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        o = np.array([-d[1], d[0]])
        # outward: away from the nearer sprocket centre (wraps) or from the loop's middle line (runs)
        ref = np.array([max(-a, min(a, mid[0])), zs])
        if (mid - ref) @ o < 0:
            o = -o
        M = g.Frame((mid[0], 0.0, mid[1]), (d[0], 0.0, d[1]), (o[0], 0.0, o[1]))
        links.append(t.add(li if k % 2 == 0 else lo, M))
        pads.append(t.add(pad, M @ T(0, 0, LINK["half_h"])))
        frames.append(M)
    cd = t.add(spr, T(-a, 0, zs))
    ci = t.add(idl, T(a, 0, zs))
    shaft = kit.shaft(90.0, 1000.0)
    t.add(shaft, T(-a, 0, zs))
    t.add(shaft, T(a, 0, zs))
    pb = kit.pillow_block(90.0)
    bolt = kit.bolt(24, 120.0)
    foot_top = -120.0 + 0.55 * 240.0
    for x in (-a, a):
        for y in (-420.0, 420.0):
            t.add(pb, T(x, y, zs))
            for dx in (-0.55 * 240.0, 0.55 * 240.0):
                t.add(bolt, T(x + dx, y, zs + foot_top))
    t.add(kit.gearbox(220.0, 380.0), T(-a, 520.0, zs))
    t.add(kit.motor(130.0, 340.0), T(-a, 900.0, zs))
    return t, {"pads": pads, "links": links, "drive": cd, "idler": ci, "pins": pins, "frames": frames, "a": a}


def tensioner(p, kit: Kit) -> Asm:
    """Two-track tensioner. Local: the cable along x through the origin (lay direction -x), deck at z = -line_h.

    The bottom track is fixed; the top track hangs in a carriage that the squeeze cylinders lower onto the cable.
    Pads have a 120° V, so every cable Ø 50 … 500 is gripped on the centre line."""
    h = p.squeeze_h()
    zp = -h - PAD["base"] - LINK["half_h"]                # contact run's pin line, bottom track
    zs = zp - p.sprocket_r
    A = Asm("TENSIONER")
    bottom, bi = track(p, kit, "BOTTOM TRACK", zs)
    top, ti = track(p, kit, "TOP TRACK", zs)
    cb = A.add(bottom)
    zdeck = -p.line_h
    # ---- frame
    a = bi["a"]
    zb_top = zs - p.sprocket_r - LINK["half_h"] - PAD["t"] - 60.0           # under the bottom run's pads
    if zb_top < zdeck + 250.0:
        raise ValueError("the cable line is too low for the tensioner's bottom track")
    frame = []
    for y in (-900.0, 900.0):
        frame.append(g.box(-3700, y - 150, zdeck, 7400, 300, zb_top - zdeck))
    for x in (-a, a, -3550.0, 3550.0):
        frame.append(g.box(x - 150, -1050, zdeck, 300, 2100, zb_top - zdeck))
    # pedestals up to the bottom track's pillow blocks
    for x in (-a, a):
        for y in (-420.0, 420.0):
            frame.append(g.box(x - 150, y - 90, zb_top, 300, 180, zs - 120 - zb_top))
    # top: the squeeze cylinders hang from cross beams; the carriage holds the top track
    z_car = -zs + p.sprocket_r + LINK["half_h"] + PAD["t"] + 60.0          # carriage beams over the top run's pads
    car_h = 220.0
    cyl_len = 1100.0
    z_top = z_car + car_h + cyl_len + 150.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(g.box(sx * 3550 - 150, sy * 900 - 150, zb_top, 300, 300, z_top - zb_top))
    for y in (-900.0, 900.0):
        frame.append(g.box(-3700, y - 150, z_top, 7400, 300, 400))
    for x in (-2000.0, 2000.0, -3550.0, 3550.0):
        frame.append(g.box(x - 150, -1050, z_top, 300, 2100, 400))
    for sx in (-1, 1):                                          # side bracing
        for sy in (-1, 1):
            frame.append(g.beam((sx * 3550, sy * 900, zb_top + 200), (sx * 1200, sy * 900, z_top), 180.0))
    A.add(Part("TENSIONER BASE FRAME", g.fuse(*frame), YELLOW))
    # carriage with the top track (mirror of the bottom track about the cable's axis)
    car = Asm("TOP TRACK CARRIAGE")
    ct = car.add(top, Rot((1, 0, 0), 180.0))
    cframe = [g.box(-a - 400, sy * 420 - 90, z_car, 2 * a + 800, 180, car_h) for sy in (-1, 1)]
    cframe += [g.box(x - 200, -560, z_car, 400, 1120, car_h) for x in (-2000.0, 2000.0)]
    cframe += [g.box(x - 150, sy * 420 - 90, -zs + 120, 300, 180, z_car + 1 - (-zs + 120)) for x in (-a, a)
               for sy in (-1, 1)]
    car.add(Part("TOP TRACK FRAME", g.fuse(*cframe), YELLOW))
    cc = A.add(car)
    # squeeze cylinders (x = -2000, +2000): barrel from the top beam down, rod to the carriage
    bar_r, rod_r = 160.0, 90.0
    barrel = kit.get(("sq_barrel", cyl_len), lambda: Part("BARREL", g.fuse(
        g.tube(bar_r, rod_r + 6, cyl_len, (0, 0, -cyl_len)), g.cyl(bar_r, 60.0, (0, 0, -60)),
        g.tube(bar_r + 40, rod_r + 6, 40.0, (0, 0, -cyl_len))), YELLOW))
    rod_len = cyl_len + 150.0 - 80.0
    rodp = kit.get(("sq_rod", rod_len), lambda: Part("PISTON ROD", g.cyl(rod_r, rod_len), CHROME))
    rods = []
    for k, x in enumerate((-2000.0, 2000.0)):
        cyl = Asm("TENSIONER CYLINDER")
        cyl.add(barrel, T(0, 0, 0))
        r = cyl.add(rodp, T(0, 0, -cyl_len - 150.0))
        c = A.add(cyl, T(x, 0, z_top))
        rods.append([c, r])
    # joints
    lo = -(h - p.squeeze_h(50.0))
    hi = p.squeeze_h(500.0) - h + 150.0
    A.joint("Squeeze", "slide", [cc] + rods, (0, 0, -zs), (0, 0, -1), [round(-hi, 3), round(-lo, 3)],
            {"by": "operator", "note": "the cylinders lower the top track onto the cable (positive = squeeze); "
                                       "0 = gripping this cable Ø"})
    Rs = p.sprocket_r
    for label, chain, ci_ in (("Bottom", [cb], bi), ("Top", [cc, ct], ti)):
        for which, key, x in (("drive", "drive", -a), ("idler", "idler", a)):
            if label == "Bottom":
                ctr = np.array([x, 0.0, zs])
                contact, vel = ctr + [0, 0, Rs], [-1.0, 0, 0]
            else:
                ctr = np.array([x, 0.0, -zs])
                contact, vel = ctr - [0, 0, Rs], [-1.0, 0, 0]
            A.joint(f"{label} track {which} sprocket turn", "rotate", [chain + [ci_[key]]], ctr,
                    turn_axis(ctr, contact, vel), None,
                    cable_drive(Rs, note="the chain's pitch line runs at the cable speed"))
    A.info["tracks"] = []
    for label, chain, ci_, flip in (("bottom", [cb], bi, 1.0), ("top", [cc, ct], ti, -1.0)):
        A.info["tracks"].append({
            "name": label, "chain": chain, "pads": ci_["pads"], "links": ci_["links"],
            "pins": [[x, 0.0, flip * z] for x, z in ci_["pins"]],
            "sprockets": {"drive": [-a, 0.0, flip * zs], "idler": [a, 0.0, flip * zs]},
            "pitch": p.pad_pitch, "sprocket_pitch_r": Rs, "contact_run": "pads 1 … %d face the cable" % p.links_per_run,
            "travel": "with the cable on the contact run (towards -x)"})
    A.info["squeeze_h"] = h
    return A


# ---------------------------------------------------------------------------------------------------------
# Winch (handling, quadrant handling, tipping)
# ---------------------------------------------------------------------------------------------------------


def winch(p, kit: Kit, name: str, rope_d: float, rc: float, length: float, layers: int, wound: float,
          fairlead: bool, groove: str = "spiral") -> Asm:
    """Winch: grooved drum (axis local y, centre at x = 0, z = zc) on a base frame, gearbox + hydraulic motor on
    the +y end, spooled wire as a simplified solid. ``fairlead``: a sheave at +x the rope runs over, then down to a
    shackle. ``rc``: rope centre radius on the first layer. Returns the asm with info["rope_top"]."""
    rr = rope_d / 2
    pitch = round(rope_d * 1.06, 2)
    flange_r = rc + rr + (layers + 1.5) * rope_d * 0.9
    zc = flange_r + 350.0
    a = Asm(name)
    drum = Asm("WINCH DRUM UNIT")
    key = ("barrel", rope_d, rc, length, groove)
    barrel = kit.get(key, lambda: Part("WINCH DRUM", g.xform(
        g.grooved_barrel(rc, rr, -length / 2, length / 2, pitch, groove)[0], Rot((1, 0, 0), -90)), YELLOW))
    drum.add(barrel)
    flange = kit.get(("flange", flange_r), lambda: Part("DRUM FLANGE", g.cyl(flange_r, 60.0, (0, -30, 0), (0, 1, 0)),
                                                         YELLOW))
    drum.add(flange, T(0, -length / 2 - 30, 0))
    drum.add(flange, T(0, length / 2 + 30, 0))
    drum.add(kit.shaft(rc * 0.25, length + 900.0))
    # spooled wire: full layers over ``wound`` of the barrel from the -y flange, as one sleeve
    r_out = rc + rr + (layers - 1) * rope_d * 0.866
    wl = wound * length
    spool = g.tube(r_out, rc - rr * 0.3, wl, (0, -length / 2, 0), (0, 1, 0))
    drum.add(Part("WIRE ROPE", spool, ROPE_GREY))
    cd = a.add(drum, T(0, 0, zc))
    rope_rc = r_out - rr                                  # rope centre radius of the outer layer
    # frame, bearings, gearbox and motor
    yb = length / 2 + 300.0
    fr = [g.box(-flange_r - 300, -yb - 500, 0, 2 * flange_r + 600, 300, 300),
          g.box(-flange_r - 300, yb + 200, 0, 2 * flange_r + 600, 300, 300),
          g.box(-flange_r - 300, -yb - 500, 0, 300, 2 * yb + 1000, 300),
          g.box(flange_r, -yb - 500, 0, 300, 2 * yb + 1000, 300)]
    for y in (-yb, yb):
        fr.append(g.box(-flange_r - 300, y - 200, 0, 2 * flange_r + 600, 400, 300))     # cross beam
        fr.append(g.box(-300, y - 150, 299, 600, 300, zc - 300 - 200 + 1))              # bearing pedestal
    a.add(Part("WINCH BASE FRAME", g.fuse(*fr), YELLOW))
    pb = kit.pillow_block(rc * 0.25 + 2, 400.0)
    a.add(pb, T(0, -yb, zc))
    a.add(pb, T(0, yb, zc))
    a.add(kit.gearbox(rc * 0.55, 500.0), T(0, yb + 220, zc))
    a.add(kit.motor(rc * 0.32, 420.0), T(0, yb + 720, zc))
    a.joint("Drum turn", "rotate", [cd], (0, 0, zc), (0, -1, 0), None,
            {"by": "winch", "rope_centre_radius": round(rope_rc, 3),
             "deg_per_mm": round(360.0 / (2 * math.pi * rope_rc), 9),
             "note": "positive pays out (the rope leaves the drum's top towards +x); per layer the radius grows by "
                     f"{rope_d * 0.866:.1f} mm"})
    a.info.update({"rope_d": rope_d, "rope_top": [0.0, 0.0, zc + rope_rc], "drum_centre": [0.0, 0.0, zc],
                   "rope_centre_r": rope_rc, "groove": groove, "pitch": pitch, "first_layer_rc": rc,
                   "flange_r": flange_r})
    if fairlead:
        rp = max(8 * rope_d, 300.0)
        xf = flange_r + 900.0 + rp * 0
        zt = zc + rope_rc                                   # rope leaves the drum level at the top
        ctr = np.array([xf, 0.0, zt - rp])
        sh = Part("FAIRLEAD SHEAVE", g.sheave(rp, rr, holes=5), YELLOW)
        cs = a.add(sh, T(*ctr) @ Rot((1, 0, 0), 90))
        a.add(Part("FAIRLEAD FRAME", g.fuse(
            g.box(xf - 250, -260, 0, 500, 80, ctr[2] + 120), g.box(xf - 250, 180, 0, 500, 80, ctr[2] + 120),
            g.box(xf - 350, -400, 0, 700, 800, 200), g.box(flange_r, -260, 0, xf - flange_r, 520, 200)), YELLOW))
        a.joint("Fairlead sheave turn", "rotate", [cs], ctr, turn_axis(ctr, ctr + [0, 0, rp], [1, 0, 0]), None,
                cable_drive(rp, note="turned by the wire rope"))
        drop = 900.0
        from .route import Route, Line
        rope = Route("fairlead rope", rope_d)
        rope.add(Line((0, 0, zt), (xf, 0, zt)))
        rope.arc((0, 0, -1), rp, 90.0)
        rope.line_to((xf + rp, 0, ctr[2] - drop))
        a.add(Part("WIRE ROPE", g.route_solid(rope, rr), ROPE_GREY))
        sk = Part("SHACKLE", g.fuse(g.torus_piece((0, 0, -2.2 * rope_d), (0, 1, 0), (1.2 * rope_d, 0, -2.2 * rope_d),
                                                  2 * math.pi, rr * 0.9),
                                    g.cyl(rr * 1.2, 1.8 * rope_d, (0, -0.9 * rope_d, -0.9 * rope_d), (0, 1, 0))), STEEL)
        a.add(sk, T(xf + rp, 0, ctr[2] - drop))
        a.info["fairlead"] = {"centre": ctr.tolist(), "pitch_r": rp, "groove_r": rr, "child": cs}
    return a


def lebus_drum(p, rope_d: float = 48.0, rc: float = 600.0, length: float = 1600.0) -> Asm:
    """Spare drum with Lebus-style grooving (parallel grooves, two crossovers per turn), with its flanges."""
    rr = rope_d / 2
    pitch = round(rope_d * 1.06, 2)
    layers = 6
    flange_r = rc + rr + (layers + 1.5) * rope_d * 0.9
    a = Asm("WINCH DRUM LEBUS")
    barrel, turns = g.grooved_barrel(rc, rr, -length / 2, length / 2, pitch, "lebus")
    a.add(Part("WINCH DRUM", g.xform(barrel, Rot((1, 0, 0), -90)), YELLOW))
    fl = Part("DRUM FLANGE", g.cyl(flange_r, 60.0, (0, -30, 0), (0, 1, 0)), YELLOW)
    a.add(fl, T(0, -length / 2 - 30, 0))
    a.add(fl, T(0, length / 2 + 30, 0))
    a.add(Part("SHAFT", g.cyl(rc * 0.25, length + 900, (0, -(length + 900) / 2, 0), (0, 1, 0)), STEEL))
    a.info = {"rope_d": rope_d, "first_layer_rc": rc, "pitch": pitch, "turns": turns, "groove": "lebus",
              "crossovers_per_turn": 2, "crossover_deg": 18.0}
    return a


# ---------------------------------------------------------------------------------------------------------
# Stern: chute, quadrant, cable-end supports, CPS
# ---------------------------------------------------------------------------------------------------------


def chute(p, kit: Kit, R: float, deg: float, deck_local_z: float, transom_local_x: float) -> Asm:
    """Overboarding chute. Local: the bend's centre at the origin, the cable comes in at (0, 0, R) heading -x and
    bends down over ``deg``; rollers inside the bend; side plates; supports to the deck and the transom."""
    a = Asm("CHUTE")
    rollers = _arc_rollers(kit, a, (0.0, 0.0), R, 90.0, 90.0 + deg, p.cable_r, 7.5, "Chute roller",
                           plate_name="CHUTE")
    sup = []
    for y in (-350.0, 350.0):
        # posts from the deck to the chute's forward part, struts from the transom to its lower part
        xp = -0.2 * R
        r_in = R - p.cable_r - 2 * 125.0 - 250.0
        sup.append(g.box(xp - 150, y - 100, deck_local_z, 300, 200,
                         math.sqrt(r_in ** 2 - xp ** 2) - 60.0 - deck_local_z))
        top = np.array([R * math.cos(math.radians(90 + deg * 0.6)) * 0.85, y,
                        R * math.sin(math.radians(90 + deg * 0.6)) * 0.85])
        sup.append(g.beam((transom_local_x - 150.0, y, deck_local_z - 1500.0), top, 220.0))
        sup.append(g.beam((transom_local_x - 150.0, y, deck_local_z - 300.0), top, 220.0))
    sup.append(g.box(transom_local_x - 300, -600, deck_local_z - 1800, 300, 1200, 1800))
    sup.append(g.box(transom_local_x - 300, -600, deck_local_z - 1, -0.2 * R + 450 - transom_local_x, 1200, 41))
    a.add(Part("CHUTE SUPPORT", g.fuse(*sup), YELLOW))
    a.info["rollers"] = len(rollers)
    return a


def quadrant(p, kit: Kit, R: float) -> Asm:
    """Quadrant: a quarter circle (cable gutter of rollers) that tips aft about its hinge to lower a cable end.

    Local: the hinge axis is local y through the origin = the bend's centre; rest pose: the gutter runs from the top
    (0, 0, R) - cable level, heading aft (-x) - round to (-R, 0, 0) heading down."""
    a = Asm("QUADRANT")
    cr = p.cable_r
    _arc_rollers(kit, a, (0.0, 0.0), R, 90.0, 180.0, cr, 7.5, "Quadrant roller", plate_name="QUADRANT GUTTER")
    # two side plates: a quarter disc out to R + 350, with lightening holes, and the hinge tube
    ro = R + 350.0
    pts = [(0.0, 0.0)] + [(ro * math.cos(math.radians(t)), ro * math.sin(math.radians(t)))
                          for t in np.linspace(85.0, 180.0, 30)]
    holes = [g.cyl(0.13 * R, 400, (0.55 * R * math.cos(math.radians(t)), -200, 0.55 * R * math.sin(math.radians(t))),
                   (0, 1, 0)) for t in (105.0, 135.0, 165.0)]
    plates = [g.cut(g.polygon_prism(pts, 40.0, g.Frame((0, y, 0), (1, 0, 0), (0, -1, 0))), *holes)
              for y in (-560.0, 600.0)]
    cross = [g.beam((0.5 * R * math.cos(math.radians(t)), -580, 0.5 * R * math.sin(math.radians(t))),
                    (0.5 * R * math.cos(math.radians(t)), 580, 0.5 * R * math.sin(math.radians(t))), 200.0)
             for t in (100.0, 170.0)]
    hub = g.tube(350.0, 160.0, 1400.0, (0, -700, 0), (0, 1, 0))
    a.add(Part("QUADRANT FRAME", g.fuse(*plates, *cross, hub), YELLOW))
    # hang-off clamp at the top (cable level), around the cable
    clamp = g.cut(g.box(50, -330, R - cr - 120, 500, 660, 2 * cr + 240), g.cyl(cr + 3, 900, (-200, 0, R), (1, 0, 0)))
    a.add(Part("HANG-OFF CLAMP", clamp, MOTOR))
    # pad eyes at 95°, R + 250: handling wire (y -900) and the two tipping wires (y -1300, +1300)
    eyes = {}
    t = math.radians(95.0)
    for key, y in (("handling", -900.0), ("tipping_stb", -1300.0), ("tipping_port", 1300.0)):
        c = np.array([(R + 250.0) * math.cos(t), y, (R + 250.0) * math.sin(t)])
        y0, dy = (y, -600.0 - y) if y < 0 else (600.0, y - 600.0)
        lug = g.cut(g.fuse(g.box(c[0] - 150, y0, c[2] - 150, 300, dy, 300),
                           g.cyl(170.0, 60.0, c - [0, 30, 0], (0, 1, 0))),
                    g.cyl(60.0, 200.0, c - [0, 100, 0], (0, 1, 0)))
        a.add(Part("PAD EYE", lug, YELLOW))
        eyes[key] = c.tolist()
    a.info["pad_eyes"] = eyes
    a.info["radius"] = R
    return a


def cps(p, length_restrictor: int = 14) -> tuple:
    """Cable protection system on a cable end. Local: the cable along +x from its end at the origin.

    Pull head (beyond the end), latch, centraliser, bend restrictor elements (interlocking sleeves). Returns
    (asm, length along the cable, outer radius)."""
    cr = p.cable_r
    bore = cr + 3.0
    a = Asm("CPS")
    ro = cr + 160.0
    head = g.cut(g.fuse(g.cone(cr * 0.6, cr + 20, 700, (-700, 0, 0), (1, 0, 0)),
                        g.cyl(cr + 20, 300, (0, 0, 0), (1, 0, 0))), g.cyl(bore, 400, (0, 0, 0), (1, 0, 0)))
    a.add(Part("PULL HEAD", head, STEEL))
    x = 300.0
    latch = g.cut(g.fuse(g.cyl(ro + 40, 900, (x, 0, 0), (1, 0, 0)), g.cone(ro + 40, ro + 140, 200, (x + 900, 0, 0), (1, 0, 0)),
                         *[g.box(x + 150, -ro - 120, -40, 500, 2 * ro + 240, 80)]),
                  g.cyl(bore, 1300, (x - 10, 0, 0), (1, 0, 0)))
    a.add(Part("CPS LATCH", latch, CPS_ORANGE))
    x += 1100.0
    fins = [g.xform(g.box(x, -30, ro - 20, 700, 60, 260), Rot((1, 0, 0), 120.0 * k)) for k in range(3)]
    cen = g.cut(g.fuse(g.cyl(ro, 700, (x, 0, 0), (1, 0, 0)), *fins), g.cyl(bore, 900, (x - 10, 0, 0), (1, 0, 0)))
    a.add(Part("CENTRALISER", cen, CPS_ORANGE))
    x += 700.0
    el_len = 500.0
    el = g.cut(g.fuse(g.cyl(ro - 30, el_len - 60, (0, 0, 0), (1, 0, 0)),
                      g.cyl(ro, 120, (el_len - 180, 0, 0), (1, 0, 0)),
                      g.cone(ro - 30, ro - 70, 60, (el_len - 60, 0, 0), (1, 0, 0))),
               g.cyl(bore, el_len + 20, (-10, 0, 0), (1, 0, 0)))
    elp = Part("BEND RESTRICTOR ELEMENT", el, CPS_ORANGE)
    for k in range(length_restrictor):
        a.add(elp, T(x + k * el_len, 0, 0))
    x += length_restrictor * el_len
    a.info.update({"length": x, "outer_r": ro, "elements": length_restrictor})
    return a, x, ro
