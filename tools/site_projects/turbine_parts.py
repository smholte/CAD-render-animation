"""The parts Fresing adds to the IEA 15 MW turbine for the site (task 0116), made with OpenCascade.

The owner's STEP of the IEA 15 MW reference turbine has the tower, the drivetrain on its bare bedplate, the hub and
the blades – no nacelle cover, no door, no transition piece or platforms. These are invented here, of our own
design, sized from the IEA numbers and fitted to the real geometry (``fit``: ``iea15_source.fit``). Every part is
ONE valid solid (the importer drops the colour of a part made of several, CLAUDE.md section 8).

Frame: the turbine frame "T" of the variant, mm (``iea15_source``): tower axis = z, rotor upwind towards -y,
+y = north. Offshore: sea level (MSL) z 0, seabed -30 m, tower base +15 m. Onshore: everything 14 m lower, the
ground z 0, the tower base on a 1.0 m concrete pedestal (z +1000).

Bodies (sub-assemblies of the written STEP): TOWER (fixed), NACELLE (yaw), DOOR (the "Door" joint, in TOWER),
DAVIT (the "Davit" joint, in TOWER, offshore). Parts are placed at joint values 0.

Directions round the tower are compass azimuths: 0 = +y (north), 90 = +x (east), 180 = -y (south, the rotor's
side). A local frame at azimuth a (``_az``): X = the way the azimuth grows, Y = radially out, Z = up.

What is measured (the owner's model, ``~/iea/work/src_T``, read 13 Nov 2026) and used as numbers below: the
bedplate lies within x +-3250, y -4613 … +3250, z = yaw bearing top … +5958; its front neck (y -4380 … -4320)
within 1340 mm of the rotor axis; the fixed stator ends at y -4415, the turning generator rotor (r 5263) at
y -4430 (its back face tilts with the shaft: farther forward lower down). The tower's outer radius is
``fit["tower_profile"]`` (linear between the points: the tower's cones).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import occ

VARIANTS = ("offshore", "onshore")
BODIES = ("TOWER", "NACELLE", "DOOR", "DAVIT")
# name prefixes -> looks (models.ini "colours"); a part's name starts with one of these (longest match wins)
PREFIXES = ("NACELLE", "HELI", "LIGHT", "SENSOR", "TOWER FLANGE", "YAW SEAL", "DOOR", "HANDLE", "STEP", "RAIL",
            "GRATING", "TP", "PLATFORM BEAM", "DAVIT", "HOOK", "CABINET", "LADDER", "BOAT LANDING", "FENDER",
            "J-TUBE", "CLAMP", "CONCRETE", "GRAVEL")
TOWER_PART = "TOWER"          # the source tower's part name for the decals beside the door (the converter's name)

# layout (compass azimuths, degrees)
AZ_DOOR = 165.0               # door: front right, towards the boat landing
AZ_LADDER = 135.0             # boat landing + access ladder: front right (the app's LOW / ISO views see it)
AZ_DAVIT = 115.0
AZ_CABINET = 215.0
AZ_JTUBES = (210.0, 235.0, 325.0)
AZ_BEAMS = tuple(22.5 + 45.0 * k for k in range(8))
AZ_ID_TP = 155.0              # turbine ID on the transition piece
AZ_ID_TOWER = AZ_DOOR - 15.0  # turbine ID on the tower, beside the door (on the side away from the hinge)
TURBINE_ID = "WTG A07"
HEADINGS = ((0.0, "N 0°"), (90.0, "E 90°"), (180.0, "S 180°"), (270.0, "W 270°"))

# offshore (T frame, mm)
TP_BOTTOM = 3500.0
TP_R = 5250.0                 # sleeve outside (the pile is r 5000; 5 mm gap inside)
TP_FLANGE_R = 5450.0
TP_FLANGE_H = 120.0
DECK_T = 40.0
DECK_RI, DECK_RO = 5460.0, 8500.0
RAIL_R = 8380.0               # the platform railing's posts
RAIL_H = 1100.0
BEAM_H = 300.0
LADDER_Y = 6450.0             # rungs, radially, in the ladder's frame
DAVIT_R = 7700.0
DAVIT_ANGLE = 90.0            # slewing limits +-
DAVIT_C0 = 955.0              # the slewing column's foot above the deck (15 mm over the pedestal's top)
JTUBE_R, JTUBE_Y = 180.0, 5700.0
# door (local frame of the door azimuth; z from the threshold)
DOOR_W, DOOR_H = 900.0, 2100.0
FRAME_W, FRAME_FACE = 1300.0, 5070.0
LEAF_Y0, LEAF_Y1 = 5080.0, 5130.0       # 10 mm in front of the frame
LEAF_HALF = 520.0
HINGE_X, HINGE_Y = 545.0, 5130.0
DOOR_OPEN = 100.0
# nacelle (T frame, offsets from the yaw bearing's top = the bedplate's foot)
COVER_HW = 4000.0
COVER_ZB, COVER_ZT = -512.0, 8400.0
COVER_YF, COVER_YB = -4380.0, 6000.0
COVER_WALL = 60.0
COVER_RT, COVER_RB = 1400.0, 400.0
NECK_R = 1500.0               # the front wall's opening round the rotor axis (bedplate neck, flanges)
FLOOR_HOLE_R = 3400.0         # the cover's floor round the tower top (r 3250)
SEAM_Y = 800.0


@dataclass
class Part:
    name: str
    body: str
    shape: object


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def _p(v):
    from OCP.gp import gp_Pnt
    return gp_Pnt(*(float(c) for c in v))


def _d(v):
    from OCP.gp import gp_Dir
    v = np.asarray(v, float)
    return gp_Dir(*(v / np.linalg.norm(v)))


def _cyl(p0, p1, r):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    return BRepPrimAPI_MakeCylinder(gp_Ax2(_p(p0), _d(p1 - p0)), float(r), L).Shape()


def _cone(p0, p1, r0, r1):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.gp import gp_Ax2
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = float(np.linalg.norm(p1 - p0))
    return BRepPrimAPI_MakeCone(gp_Ax2(_p(p0), _d(p1 - p0)), float(r0), float(r1), L).Shape()


def _zcyl(z0, z1, r, x=0.0, y=0.0):
    return _cyl((x, y, z0), (x, y, z1), r)


def _ring(z0, z1, ri, ro):
    return _cut(_zcyl(z0, z1, ro), _zcyl(z0 - 1.0, z1 + 1.0, ri))


def _box(M, lo, hi):
    s = occ.box(lo, hi)
    return s if M is None else occ.moved(s, M)


def _bar(p0, p1, w, h, up=(0.0, 0.0, 1.0)):
    """A rectangular bar from p0 to p1: w across, h along ``up`` (made square to the bar)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    d /= L
    up = np.asarray(up, float)
    if abs(up @ d) > 0.99:
        up = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    side = np.cross(d, up)
    return occ.moved(occ.box((-w / 2, -h / 2, 0.0), (w / 2, h / 2, L)), occ.frame(p0, d, side))


def _wire(points2d, plane):
    """A closed wire: (u, v) points and ("arc", through, end) items, mapped to 3-D by ``plane(u, v)``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle
    w = BRepBuilderAPI_MakeWire()
    cur = points2d[0]
    for it in list(points2d[1:]) + [points2d[0]]:
        if isinstance(it, tuple) and len(it) == 3 and it[0] == "arc":
            arc = GC_MakeArcOfCircle(_p(plane(*cur)), _p(plane(*it[1])), _p(plane(*it[2]))).Value()
            w.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
            cur = it[2]
        else:
            if math.hypot(it[0] - cur[0], it[1] - cur[1]) > 1e-9:
                w.Add(BRepBuilderAPI_MakeEdge(_p(plane(*cur)), _p(plane(*it))).Edge())
            cur = it
    return w.Wire()


def _prism(points2d, depth, M=None, plane=None):
    """A closed profile in the local XY plane extruded along local Z by ``depth``, placed by M."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    face = BRepBuilderAPI_MakeFace(_wire(points2d, plane or (lambda u, v: (u, v, 0.0))), True).Face()
    s = BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, float(depth))).Shape()
    return s if M is None else occ.moved(s, M)


def _revolve(points_rz):
    """A solid of revolution about z of a closed (r, z) profile."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1
    face = BRepBuilderAPI_MakeFace(_wire(points_rz, lambda r, z: (r, 0.0, z)), True).Face()
    return BRepPrimAPI_MakeRevol(face, gp_Ax1(_p((0, 0, 0)), _d((0, 0, 1))), 2 * math.pi).Shape()


def _list(shapes):
    from OCP.collections import List_TopoDS_Shape
    out = List_TopoDS_Shape()
    for s in shapes:
        out.Append(s)
    return out


def _fuse(shapes):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    shapes = [s for s in shapes if s is not None]
    if len(shapes) == 1:
        return shapes[0]
    op = BRepAlgoAPI_Fuse()
    op.SetArguments(_list(shapes[:1]))
    op.SetTools(_list(shapes[1:]))
    op.SetRunParallel(True)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("fuse failed")
    return op.Shape()


def _cut(a, *tools):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    tools = [t for t in tools if t is not None]
    if not tools:
        return a
    op = BRepAlgoAPI_Cut()
    op.SetArguments(_list([a]))
    op.SetTools(_list(tools))
    op.Build()
    if not op.IsDone():
        raise RuntimeError("cut failed")
    return op.Shape()


def _clean(shape):
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    u = ShapeUpgrade_UnifySameDomain(shape, True, True, False)
    u.Build()
    return u.Shape()


def _solid(shape, what):
    s = occ.one_solid(_clean(shape), what)
    if not occ.is_valid(s):
        raise ValueError(f"{what}: not a valid solid")
    return s


def _az(az_deg: float, z: float = 0.0) -> np.ndarray:
    """Local frame at a compass azimuth: X = the way the azimuth grows, Y = radially out, Z = up (origin on the
    tower axis at height z)."""
    a = math.radians(az_deg)
    M = np.eye(4)
    M[:3, 0] = (math.cos(a), -math.sin(a), 0.0)
    M[:3, 1] = (math.sin(a), math.cos(a), 0.0)
    M[2, 3] = z
    return M


def _at(M, p) -> np.ndarray:
    return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


def _radial(az_deg: float) -> np.ndarray:
    a = math.radians(az_deg)
    return np.array([math.sin(a), math.cos(a), 0.0])


def tower_radius(fit: dict, z: float) -> float:
    prof = fit["tower_profile"]
    return float(np.interp(z, [p[0] for p in prof], [p[1] for p in prof]))


def _tower(fit: dict, z0: float, z1: float, grow: float = 0.0):
    """The tower's outside between z0 and z1 as a full solid (for cutting parts that lie against it)."""
    zs = sorted({z0, z1} | {p[0] for p in fit["tower_profile"] if z0 < p[0] < z1})
    prof = [(0.0, z0)] + [(tower_radius(fit, z) + grow, z) for z in zs] + [(0.0, z1)]
    return _revolve(prof)


def _subdivide(poly, step):
    """Points along a polyline, the corners kept, no gap longer than ``step``."""
    out = [np.asarray(poly[0], float)]
    for a, b in zip(poly, poly[1:]):
        a, b = np.asarray(a, float), np.asarray(b, float)
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return out


def _corners(poly):
    """The polyline without the points that lie on a straight run (rails run corner to corner, in one piece)."""
    pts = [np.asarray(p, float) for p in poly]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        d0 = pts[i] - out[-1]
        d1 = pts[i + 1] - pts[i]
        if np.linalg.norm(np.cross(d0 / np.linalg.norm(d0), d1 / np.linalg.norm(d1))) > 1e-6:
            out.append(pts[i])
    out.append(pts[-1])
    return out


def _railing(poly, step=1300.0, h=RAIL_H, toe=True, r_post=24.0, r_rail=21.0):
    """A railing along a polyline of floor points (3-D): posts, top rail, knee rail, toe board – one solid.

    Rails and toe boards run corner to corner and reach 10 / 4 mm past each corner post's axis (inside the post):
    no two pieces end on the same face (the boolean fuse left a sliver of rail as a solid of its own that way)."""
    corners = _corners(poly)
    posts = _subdivide(corners, step)
    up = np.array([0.0, 0.0, 1.0])
    parts = [_cyl(p, p + up * (h + r_rail), r_post) for p in posts]
    for a, b in zip(corners, corners[1:]):
        e = (b - a) / np.linalg.norm(b - a)
        parts.append(_cyl(a + up * h - e * 10.0, b + up * h + e * 10.0, r_rail))
        parts.append(_cyl(a + up * (h * 0.5) - e * 10.0, b + up * (h * 0.5) + e * 10.0, r_rail * 0.85))
        if toe:
            parts.append(_toe(a - e * 4.0, b + e * 4.0))
    return _fuse(parts)


def _toe(a, b):
    """A toe board (8 mm thick, 120 high, 10 mm above the floor) between two post feet."""
    up = np.array([0.0, 0.0, 1.0])
    return _bar(a + up * 70.0, b + up * 70.0, 8.0, 120.0, up)


def _pipe(points, r):
    """A round pipe along a polyline, mitred at the corners (no torus: few triangles)."""
    pts = [np.asarray(p, float) for p in points]
    ds = [(b - a) / np.linalg.norm(b - a) for a, b in zip(pts, pts[1:])]
    pieces = []
    for i, d in enumerate(ds):
        a, b = pts[i], pts[i + 1]
        ext = 3.0 * r
        piece = _cyl(a - (d * ext if i > 0 else 0), b + (d * ext if i < len(ds) - 1 else 0), r)
        big = 6.0 * r
        if i > 0:                                         # keep the side after the corner at a
            n = ds[i - 1] + d
            piece = _cut(piece, _box(occ.frame(a, n), (-big, -big, -big), (big, big, 0.0)))
        if i < len(ds) - 1:                               # keep the side before the corner at b
            n = d + ds[i + 1]
            piece = _cut(piece, _box(occ.frame(b, n), (-big, -big, 0.0), (big, big, big)))
        pieces.append(piece)
    return _fuse(pieces)


# ---------------------------------------------------------------------------
# heights
# ---------------------------------------------------------------------------

def _check(fit: dict, variant: str):
    if variant not in VARIANTS:
        raise ValueError(variant)
    if fit.get("variant", variant) != variant:
        raise ValueError(f"fit is for {fit.get('variant')}, not {variant}")


def deck_z(fit: dict) -> float:
    """Offshore: the working platform's deck top (= the tower base, the transition piece's top)."""
    return float(fit["tower_base_z"])


def threshold_z(fit: dict, variant: str) -> float:
    """The door opening's bottom."""
    return deck_z(fit) + 530.0 if variant == "offshore" else float(fit["tower_base_z"]) + 2000.0


def _yaw_top(fit: dict) -> float:
    return float(fit["yaw_bearing_z"][-1])


def flange_heights(fit: dict) -> list[float]:
    """Three tower-section joints: the tower profile's breakpoints nearest the quarters of the tower."""
    z0, z1 = float(fit["tower_base_z"]), float(fit["tower_top_z"])
    cand = [p[0] for p in fit["tower_profile"] if z0 + 5000.0 < p[0] < z1 - 5000.0]
    out = []
    for q in (0.25, 0.5, 0.75):
        zq = z0 + q * (z1 - z0)
        best = min((z for z in cand if z not in out), key=lambda z: abs(z - zq))
        out.append(best)
    return sorted(out)


# ---------------------------------------------------------------------------
# both variants
# ---------------------------------------------------------------------------

def _rrect(hw, z0, z1, rt, rb):
    """A rounded rectangle in the x-z plane (u = x, v = z): bottom corners rb, top corners rt."""
    c = math.sqrt(0.5)
    return [(-hw + rb, z0), (hw - rb, z0),
            ("arc", (hw - rb + rb * c, z0 + rb - rb * c), (hw, z0 + rb)), (hw, z1 - rt),
            ("arc", (hw - rt + rt * c, z1 - rt + rt * c), (hw - rt, z1)), (-hw + rt, z1),
            ("arc", (-hw + rt - rt * c, z1 - rt + rt * c), (-hw, z1 - rt)), (-hw, z0 + rb),
            ("arc", (-hw + rb - rb * c, z0 + rb - rb * c), (-hw + rb, z0))]


def _prism_y(points_xz, y0, y1):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    face = BRepBuilderAPI_MakeFace(_wire(points_xz, lambda u, v: (u, y0, v)), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, float(y1 - y0), 0.0)).Shape()


def _nacelle(fit: dict) -> list[Part]:
    yt = _yaw_top(fit)
    zb, zt = yt + COVER_ZB, yt + COVER_ZT
    yf, yb = COVER_YF, COVER_YB
    w = COVER_WALL
    outer = _prism_y(_rrect(COVER_HW, zb, zt, COVER_RT, COVER_RB), yf, yb)
    inner = _prism_y(_rrect(COVER_HW - w, zb + w, zt - w, COVER_RT - w, COVER_RB - w), yf + w, yb - w)
    # the front wall's opening round the rotor axis (the bedplate's neck and the main-shaft flanges pass through)
    p = np.asarray(fit["rotor"]["point"], float)
    d = np.asarray(fit["rotor"]["direction"], float)
    ta, tb = (yf - 200.0 - p[1]) / d[1], (yf + w + 200.0 - p[1]) / d[1]
    neck = _cyl(p + ta * d, p + tb * d, NECK_R)
    floor = _zcyl(zb - 10.0, zb + w + 10.0, FLOOR_HOLE_R)
    g = 15.0                                              # the seam: a groove 15 deep, 30 wide, round the cover
    groove = _cut(_prism_y(_rrect(COVER_HW + 5.0, zb - 5.0, zt + 5.0, COVER_RT + 5.0, COVER_RB + 5.0),
                           SEAM_Y, SEAM_Y + 30.0),
                  _prism_y(_rrect(COVER_HW - g, zb + g, zt - g, COVER_RT - g, COVER_RB - g),
                           SEAM_Y - 1.0, SEAM_Y + 31.0))
    cover = _cut(outer, inner, neck, floor, groove)
    parts = [Part("NACELLE COVER", "NACELLE", _solid(cover, "NACELLE COVER"))]

    hatch = _fuse([occ.box((-600.0, -3000.0, zt), (600.0, -1900.0, zt + 70.0)),
                   occ.box((-560.0, -2960.0, zt + 70.0), (560.0, -1940.0, zt + 90.0))])
    parts.append(Part("NACELLE HATCH", "NACELLE", _solid(hatch, "NACELLE HATCH")))

    # cooler on the back wall, rising above the roof; a grille of slots on its back face
    cz0, cz1 = zb + 1500.0, zt + 1200.0
    cool = occ.box((-3600.0, yb, cz0), (3600.0, yb + 900.0, cz1))
    slots = [occ.box((-3400.0, yb + 860.0, z), (3400.0, yb + 910.0, z + 160.0))
             for z in np.arange(cz0 + 300.0, cz1 - 400.0, 420.0)]
    cool = _cut(cool, *slots)
    parts.append(Part("NACELLE COOLER", "NACELLE", _solid(cool, "NACELLE COOLER")))

    # helicopter-hoist platform on the back half of the roof (inside the flat part: |x| < hw - rt)
    hz = zt + 300.0
    legs = [occ.box((x - 75.0, y - 75.0, zt), (x + 75.0, y + 75.0, hz + 1.0))
            for x in (-2200.0, 2200.0) for y in (1300.0, 3400.0, 5500.0)]
    heli = _fuse([occ.box((-2400.0, 700.0, hz), (2400.0, 5700.0, hz + 60.0))] + legs)
    parts.append(Part("HELI DECK", "NACELLE", _solid(heli, "HELI DECK")))
    rz = hz + 60.0
    rail = _railing([(-2350.0, 760.0, rz), (-2350.0, 5640.0, rz), (2350.0, 5640.0, rz), (2350.0, 760.0, rz)])
    parts.append(Part("RAIL HELI", "NACELLE", _solid(rail, "RAIL HELI")))

    # aviation lights on the cooler's top corners
    ly = yb + 450.0
    for i, x in enumerate((-3300.0, 3300.0)):
        light = _fuse([_zcyl(cz1, cz1 + 100.0, 110.0, x, ly), _zcyl(cz1 + 100.0, cz1 + 260.0, 90.0, x, ly),
                       _cone((x, ly, cz1 + 260.0), (x, ly, cz1 + 320.0), 90.0, 30.0)])
        parts.append(Part(f"LIGHT {i + 1}", "NACELLE", _solid(light, f"LIGHT {i + 1}")))

    # wind sensors: a mast on the cooler with a cross bar, a cup anemometer and a vane
    mz = cz1 + 2600.0
    mast = _fuse([_zcyl(cz1, mz + 60.0, 60.0, 0.0, ly), _cyl((-1000.0, ly, mz), (1000.0, ly, mz), 40.0),
                  occ.box((-150.0, ly - 150.0, cz1), (150.0, ly + 150.0, cz1 + 20.0))])
    parts.append(Part("SENSOR MAST", "NACELLE", _solid(mast, "SENSOR MAST")))
    ax, s0 = 900.0, mz + 42.0
    cups = [_zcyl(s0, s0 + 300.0, 18.0, ax, ly), _zcyl(s0 + 300.0, s0 + 360.0, 40.0, ax, ly)]
    for k in range(3):
        a = math.radians(120.0 * k)
        e = np.array([math.cos(a), math.sin(a), 0.0])
        t = np.array([-math.sin(a), math.cos(a), 0.0])
        c = np.array([ax, ly, s0 + 330.0])
        tip = c + e * 260.0
        cups.append(_cyl(c, tip, 8.0))
        cups.append(_cone(tip - t * 45.0, tip + t * 45.0, 55.0, 15.0))
    parts.append(Part("SENSOR ANEMOMETER", "NACELLE", _solid(_fuse(cups), "SENSOR ANEMOMETER")))
    vx = -900.0
    vz = s0 + 320.0
    vane = _fuse([_zcyl(s0, vz, 18.0, vx, ly), _cyl((vx, ly - 380.0, vz), (vx, ly + 320.0, vz), 28.0),
                  _cone((vx, ly - 380.0, vz), (vx, ly - 470.0, vz), 28.0, 8.0),
                  occ.box((vx - 4.0, ly + 250.0, vz - 120.0), (vx + 4.0, ly + 600.0, vz + 160.0))])
    parts.append(Part("SENSOR VANE", "NACELLE", _solid(vane, "SENSOR VANE")))

    # yaw seal: a dark ring under the cover's floor, round the tower top (turns with the nacelle, symmetric)
    parts.append(Part("YAW SEAL", "NACELLE", _solid(_ring(zb - 100.0, zb, 3300.0, 3600.0), "YAW SEAL")))
    return parts


def _flanges(fit: dict) -> list[Part]:
    out = []
    for i, zf in enumerate(flange_heights(fit)):
        ri = max(tower_radius(fit, zf - 60.0), tower_radius(fit, zf + 60.0)) + 3.0
        out.append(Part(f"TOWER FLANGE {i + 1}", "TOWER",
                        _solid(_ring(zf - 60.0, zf + 60.0, ri, ri + 35.0), f"TOWER FLANGE {i + 1}")))
    return out


def _door_frame_M(fit: dict, variant: str) -> np.ndarray:
    return _az(AZ_DOOR, threshold_z(fit, variant))


def door_cut(fit: dict, variant: str):
    """The solid the converter cuts out of the tower: the door opening (900 x 2100) through the wall."""
    _check(fit, variant)
    M = _door_frame_M(fit, variant)
    return _box(M, (-DOOR_W / 2, 4400.0, 0.0), (DOOR_W / 2, 5300.0, DOOR_H))


def _door(fit: dict, variant: str) -> list[Part]:
    M = _door_frame_M(fit, variant)
    zt = threshold_z(fit, variant)
    fw = FRAME_W / 2
    ring = _cut(occ.box((-fw, 4800.0, -70.0), (fw, FRAME_FACE, DOOR_H + 150.0)),
                occ.box((-DOOR_W / 2, 4700.0, 0.0), (DOOR_W / 2, 5200.0, DOOR_H)))
    plates = [occ.box((585.0, 5040.0, h - 80.0), (640.0, 5095.0, h + 80.0)) for h in (300.0, 1800.0)]
    frame = _cut(occ.moved(_fuse([ring] + plates), M), _tower(fit, zt - 300.0, zt + DOOR_H + 400.0))
    parts = [Part("DOOR FRAME", "TOWER", _solid(frame, "DOOR FRAME"))]
    leaf = [occ.box((-LEAF_HALF, LEAF_Y0, -50.0), (LEAF_HALF, LEAF_Y1, DOOR_H + 60.0))]
    for h in (300.0, 1800.0):
        leaf.append(_cyl((HINGE_X, HINGE_Y, h - 80.0), (HINGE_X, HINGE_Y, h + 80.0), 25.0))
        leaf.append(occ.box((380.0, LEAF_Y1 - 5.0, h - 60.0), (HINGE_X, LEAF_Y1 + 20.0, h + 60.0)))
    parts.append(Part("DOOR LEAF", "DOOR", _solid(occ.moved(_fuse(leaf), M), "DOOR LEAF")))
    hx, hz = -LEAF_HALF + 120.0, 1050.0
    handle = _fuse([occ.box((hx - 30.0, LEAF_Y1, hz - 100.0), (hx + 30.0, LEAF_Y1 + 18.0, hz + 100.0)),
                    _cyl((hx, LEAF_Y1 + 10.0, hz), (hx, LEAF_Y1 + 55.0, hz), 10.0),
                    _cyl((hx - 10.0, LEAF_Y1 + 55.0, hz), (hx + 150.0, LEAF_Y1 + 55.0, hz), 11.0)])
    parts.append(Part("HANDLE DOOR", "DOOR", _solid(occ.moved(handle, M), "HANDLE DOOR")))
    return parts


# ---------------------------------------------------------------------------
# onshore
# ---------------------------------------------------------------------------

def _onshore(fit: dict) -> list[Part]:
    zb = float(fit["tower_base_z"])                          # +1000: the pedestal's top
    g = float(fit.get("ground_z", 0.0))
    slab_top = g + 100.0
    parts = [Part("CONCRETE PEDESTAL", "TOWER",
                  _solid(_cone((0, 0, slab_top), (0, 0, zb), 6500.0, 6000.0), "CONCRETE PEDESTAL")),
             Part("CONCRETE SLAB", "TOWER",
                  _solid(_revolve([(0.0, g - 400.0), (11000.0, g - 400.0), (11000.0, slab_top - 40.0),
                                   (10960.0, slab_top), (0.0, slab_top)]), "CONCRETE SLAB")),
             Part("GRAVEL APRON", "TOWER", _solid(_ring(g - 150.0, g + 40.0, 11000.0, 15000.0), "GRAVEL APRON"))]

    zt = threshold_z(fit, "onshore")
    M = _az(AZ_DOOR)
    top = zt - 80.0                                          # the landing's top, under the door leaf
    y_out = 6400.0
    land = [occ.box((-900.0, 4700.0, top - 50.0), (900.0, y_out, top))]
    land += [occ.box((x - 40.0, y - 40.0, zb), (x + 40.0, y + 40.0, top - 49.0))
             for x in (-800.0, 800.0) for y in (5200.0, 5800.0)]
    landing = _cut(occ.moved(_fuse(land), M), _tower(fit, zb, top + 10.0))
    parts.append(Part("STEP DOOR LANDING", "TOWER", _solid(landing, "STEP DOOR LANDING")))

    n = max(2, int(round((top - slab_top) / 190.0)))         # risers
    rise = (top - slab_top) / n
    run = 260.0
    foot = y_out + (n - 1) * run + 260.0
    stair = []
    for k in range(1, n):                                    # tread k: top at slab + k * rise
        y1 = y_out + (n - k) * run
        stair.append(occ.box((-550.0, y1 - run - 10.0, slab_top + k * rise - 40.0),
                             (550.0, y1 + 10.0, slab_top + k * rise)))
    for x in (-560.0, 545.0):                                # stringers: parallelograms in the Y-Z plane
        pts = [(y_out, top - 20.0), (y_out, top - 320.0), (foot - 300.0, slab_top), (foot, slab_top),
               (foot, slab_top + 300.0)]
        stair.append(_prism(pts, 15.0, M=occ.frame((x, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))))
    parts.append(Part("STEP STAIR", "TOWER", _solid(occ.moved(_fuse(stair), M), "STEP STAIR")))

    # railings: the landing's two sides (the door's hinge is on +X: the open leaf stays 80 mm off) and the stair's
    for i, x in enumerate((-875.0, 875.0)):
        y0 = _surface_y(fit, x + math.copysign(30.0, x), top) + 40.0
        r = _railing([_at(M, (x, y0, top)), _at(M, (x, y_out - 30.0, top))], step=800.0, toe=False)
        parts.append(Part(f"RAIL LANDING {i + 1}", "TOWER", _solid(r, f"RAIL LANDING {i + 1}")))
    for i, x in enumerate((-590.0, 590.0)):
        pts = []
        for k in range(n - 1, 0, -3):
            y = y_out + (n - k) * run - run / 2
            pts.append(_at(M, (x, y, slab_top + k * rise)))
        pts.append(_at(M, (x, y_out + (n - 1) * run, slab_top + rise * 0.5)))   # on the same line (k = 0.5)
        r = _railing(pts, step=2000.0, h=950.0, toe=False)
        parts.append(Part(f"RAIL STAIR {i + 1}", "TOWER", _solid(r, f"RAIL STAIR {i + 1}")))
    return parts


def _surface_y(fit, x, z):
    """In a local frame: the tower surface's Y at local X and height z."""
    r = tower_radius(fit, z)
    return math.sqrt(max(r * r - x * x, 0.0))


# ---------------------------------------------------------------------------
# offshore
# ---------------------------------------------------------------------------

def _minus_round(shape, fit, z0, z1, gap=2.0):
    """``shape`` without what lies inside the transition piece / pile (plus a gap) between z0 and z1."""
    tools = []
    if z1 > TP_BOTTOM:
        tools.append(_zcyl(max(z0, TP_BOTTOM), z1, TP_R + gap))
    if z0 < TP_BOTTOM:
        tools.append(_zcyl(z0, min(z1, TP_BOTTOM) + 0.01, tower_radius(fit, 0.0) + gap))
    return _cut(shape, *tools)


def _offshore(fit: dict) -> list[Part]:
    dz = deck_z(fit)
    rp = tower_radius(fit, TP_BOTTOM)                        # the pile, 5000
    parts = []
    tp = _fuse([_ring(TP_BOTTOM, dz - TP_FLANGE_H, rp + 5.0, TP_R),
                _ring(dz - TP_FLANGE_H - 1.0, dz, rp + 5.0, TP_FLANGE_R),
                _ring(TP_BOTTOM + 200.0, TP_BOTTOM + 320.0, rp + 5.0, TP_R + 60.0)])
    parts.append(Part("TP SLEEVE", "TOWER", _solid(tp, "TP SLEEVE")))

    # working platform: a grating deck with an opening for the ladder, beams under it
    ML = _az(AZ_LADDER)
    hole = _box(ML, (-450.0, 6050.0, dz - 100.0), (450.0, 7150.0, dz + 100.0))
    deck = _cut(_ring(dz - DECK_T, dz, DECK_RI, DECK_RO), hole)
    parts.append(Part("GRATING DECK", "TOWER", _solid(deck, "GRATING DECK")))
    for i, az in enumerate(AZ_BEAMS):
        M = _az(az)
        b = [occ.box((-80.0, TP_FLANGE_R + 5.0, dz - DECK_T - BEAM_H), (80.0, DECK_RO - 50.0, dz - DECK_T)),
             _cyl((0.0, 7000.0, dz - DECK_T - 200.0), (0.0, TP_R + 60.0, dz - 1800.0), 50.0)]
        parts.append(Part(f"PLATFORM BEAM {i + 1}", "TOWER",
                          _solid(occ.moved(_fuse(b), M), f"PLATFORM BEAM {i + 1}")))

    # the platform's railing in 6 sections (a post at each end, 117 mm apart between sections)
    for k in range(6):
        a0, a1 = 60.0 * k + 0.4, 60.0 * (k + 1) - 0.4
        poly = [_radial(a) * RAIL_R + np.array([0.0, 0.0, dz]) for a in np.linspace(a0, a1, 8)]
        parts.append(Part(f"RAIL PLATFORM {k + 1}", "TOWER",
                          _solid(_railing(poly, step=1400.0), f"RAIL PLATFORM {k + 1}")))
    # round the ladder's opening: a U of railing and a gate (closed) on the side towards the tower
    u = [_at(ML, (-520.0, 5990.0, dz)), _at(ML, (-520.0, 7210.0, dz)), _at(ML, (520.0, 7210.0, dz)),
         _at(ML, (520.0, 5990.0, dz))]
    parts.append(Part("RAIL HATCH", "TOWER", _solid(_railing(u, step=700.0), "RAIL HATCH")))
    gate = [_cyl((x, 5990.0, dz + 120.0), (x, 5990.0, dz + 1100.0), 20.0) for x in (-465.0, 465.0)]
    gate += [_cyl((-485.0, 5990.0, z), (485.0, 5990.0, z), 18.0) for z in (dz + 150.0, dz + 600.0, dz + 1070.0)]
    parts.append(Part("RAIL GATE", "TOWER", _solid(occ.moved(_fuse(gate), ML), "RAIL GATE")))

    # door steps: one step and a landing under the door leaf
    MD = _az(AZ_DOOR)
    top = threshold_z(fit, "offshore") - 80.0
    st = [occ.box((-800.0, 4700.0, top - 50.0), (800.0, 6100.0, top)),
          occ.box((-600.0, 6090.0, dz + (top - dz) / 2 - 50.0), (600.0, 6400.0, dz + (top - dz) / 2)),
          occ.box((-600.0, 6080.0, dz + (top - dz) / 2 - 50.0), (600.0, 6100.0, top))]   # riser
    st += [occ.box((x - 40.0, y - 40.0, dz), (x + 40.0, y + 40.0, top - 49.0))
           for x in (-700.0, 700.0) for y in (5300.0, 6000.0)]
    st += [occ.box((x - 40.0, 6300.0, dz), (x + 40.0, 6380.0, dz + (top - dz) / 2 - 49.0)) for x in (-500.0, 500.0)]
    steps = _cut(occ.moved(_fuse(st), MD), _tower(fit, dz, top + 10.0))
    parts.append(Part("STEP DOOR", "TOWER", _solid(steps, "STEP DOOR")))

    # davit: a fixed pedestal; the slewing column + jib and the hook block turn (the "Davit" joint)
    MV = _az(AZ_DAVIT)
    ped = _fuse([_zcyl(dz, dz + 30.0, 400.0, 0.0, DAVIT_R), _zcyl(dz + 29.0, dz + 900.0, 250.0, 0.0, DAVIT_R),
                 _zcyl(dz + 880.0, dz + 940.0, 300.0, 0.0, DAVIT_R)])
    parts.append(Part("DAVIT PEDESTAL", "TOWER", _solid(occ.moved(ped, MV), "DAVIT PEDESTAL")))
    c0, ct = dz + DAVIT_C0, dz + 4400.0
    jib_y = 3000.0
    dav = [_zcyl(c0, c0 + 40.0, 290.0, 0.0, DAVIT_R), _zcyl(c0 + 39.0, ct, 160.0, 0.0, DAVIT_R),
           occ.box((-80.0, DAVIT_R - 250.0, ct - 240.0), (80.0, DAVIT_R + jib_y, ct)),
           _cyl((0.0, DAVIT_R, ct - 1400.0), (0.0, DAVIT_R + 1500.0, ct - 200.0), 45.0),
           _cyl((-60.0, DAVIT_R + jib_y - 120.0, ct - 240.0), (60.0, DAVIT_R + jib_y - 120.0, ct - 240.0), 110.0)]
    parts.append(Part("DAVIT", "DAVIT", _solid(occ.moved(_fuse(dav), MV), "DAVIT")))
    hy = DAVIT_R + jib_y - 120.0
    hb = ct - 240.0 - 112.0
    hook = [_zcyl(hb - 1100.0, hb, 8.0, 0.0, hy),
            occ.box((-70.0, hy - 110.0, hb - 1400.0), (70.0, hy + 110.0, hb - 1080.0)),
            _zcyl(hb - 1560.0, hb - 1395.0, 30.0, 0.0, hy),
            _cone((0.0, hy, hb - 1560.0), (0.0, hy + 90.0, hb - 1700.0), 30.0, 12.0)]
    parts.append(Part("HOOK BLOCK", "DAVIT", _solid(occ.moved(_fuse(hook), MV), "HOOK BLOCK")))

    MC = _az(AZ_CABINET)
    cab = _fuse([occ.box((-600.0, 6300.0, dz), (600.0, 7000.0, dz + 1900.0)),
                 occ.box((-650.0, 6250.0, dz + 1899.0), (650.0, 7050.0, dz + 1960.0)),
                 occ.box((-500.0, 6995.0, dz + 900.0), (-440.0, 7030.0, dz + 1100.0))])
    parts.append(Part("CABINET", "TOWER", _solid(occ.moved(cab, MC), "CABINET")))

    parts += _access(fit)
    parts += _jtubes(fit)
    return parts


def _access(fit: dict) -> list[Part]:
    """Boat landing, access ladder with cage and rest platform (at AZ_LADDER)."""
    dz = deck_z(fit)
    M = _az(AZ_LADDER)
    parts = []
    lz0, lz1 = -3000.0, dz + 1100.0
    lad = [occ.box((s - 6.0, LADDER_Y - 35.0, lz0), (s + 6.0, LADDER_Y + 35.0, lz1)) for s in (-250.0, 250.0)]
    lad += [_cyl((-252.0, LADDER_Y, z), (252.0, LADDER_Y, z), 14.0) for z in np.arange(lz0 + 300.0, dz - 200.0, 300.0)]
    stand = []
    for z in (-2000.0, 1000.0, 4000.0, 7000.0, 10000.0, 13000.0):
        for s in (-250.0, 250.0):
            stand.append(occ.box((s - 30.0, 4800.0, z), (s + 30.0, LADDER_Y - 30.0, z + 60.0)))
    lad += [_minus_round(_fuse(stand), fit, -3000.0, dz)]
    parts.append(Part("LADDER", "TOWER", _solid(occ.moved(_fuse(lad), M), "LADDER")))

    for i, (z0, z1) in enumerate(((6000.0, 9300.0), (10800.0, dz - DECK_T - BEAM_H - 150.0))):
        hoop = [(-350.0, LADDER_Y), (-350.0, 6950.0), (-180.0, 7150.0), (180.0, 7150.0), (350.0, 6950.0),
                (350.0, LADDER_Y)]
        cage = []
        for z in np.linspace(z0, z1 - 60.0, max(2, int((z1 - z0) / 900.0) + 1)):
            for a, b in zip(hoop, hoop[1:]):
                cage.append(_flat((a[0], a[1], z), (b[0], b[1], z)))
        for x, y in hoop[1:-1]:
            cage.append(occ.box((x - 25.0, y - 4.0, z0), (x + 25.0, y + 4.0, z1)) if abs(y - 7150.0) < 1 else
                        occ.box((x - 4.0, y - 25.0, z0), (x + 4.0, y + 25.0, z1)))
        parts.append(Part(f"RAIL CAGE {i + 1}", "TOWER", _solid(occ.moved(_fuse(cage), M), f"RAIL CAGE {i + 1}")))

    rz = 9500.0
    rest = _minus_round(occ.box((-1300.0, 4900.0, rz - 40.0), (-420.0, 6500.0, rz)), fit, rz - 50.0, rz + 10.0)
    parts.append(Part("GRATING REST PLATFORM", "TOWER", _solid(occ.moved(rest, M), "GRATING REST PLATFORM")))
    rb = [_bar((x, 6400.0, rz - 45.0), (x, TP_R + 60.0, rz - 1200.0), 60.0, 60.0, (1, 0, 0)) for x in (-1200.0, -520.0)]
    rb += [occ.box((-1240.0, 5150.0, rz - 140.0), (-480.0, 6450.0, rz - 41.0))]
    rb = _minus_round(_fuse(rb), fit, rz - 1500.0, rz)
    parts.append(Part("PLATFORM BEAM REST", "TOWER", _solid(occ.moved(rb, M), "PLATFORM BEAM REST")))
    y_tp = math.sqrt(TP_R ** 2 - 1300.0 ** 2) + 50.0         # the sleeve's skin beside the rest platform
    rr = _railing([_at(M, (-460.0, 6470.0, rz)), _at(M, (-1270.0, 6470.0, rz)), _at(M, (-1270.0, y_tp, rz))],
                  step=900.0)
    parts.append(Part("RAIL REST PLATFORM", "TOWER", _solid(rr, "RAIL REST PLATFORM")))

    # boat landing: two bumper tubes with brackets to the transition piece and the pile, rubber fenders
    for i, x in enumerate((-800.0, 800.0)):
        y = 6750.0
        bl = [_zcyl(-4000.0, 5500.0, 220.0, x, y), _cone((x, y, 5500.0), (x, y, 5650.0), 220.0, 120.0),
              _cone((x, y, -4000.0), (x, y, -4150.0), 220.0, 120.0)]
        for z in (4500.0, -2500.0):
            bl.append(_minus_round(_cyl((x, y, z), (x, 4800.0, z), 110.0), fit, z - 200.0, z + 200.0))
        parts.append(Part(f"BOAT LANDING {i + 1}", "TOWER", _solid(occ.moved(_fuse(bl), M), f"BOAT LANDING {i + 1}")))
        fz = [(-1500.0, -300.0), (300.0, 2500.0)]
        for j, (z0, z1) in enumerate(fz):
            f = occ.moved(_cut(_zcyl(z0, z1, 300.0, x, y), _zcyl(z0 - 1, z1 + 1, 222.0, x, y)), M)
            parts.append(Part(f"FENDER {2 * i + j + 1}", "TOWER", _solid(f, f"FENDER {2 * i + j + 1}")))
    return parts


def _flat(a, b):
    """A cage hoop's flat bar (8 thick, 60 high) between two points at one height."""
    return _bar(a, b, 8.0, 60.0, (0.0, 0.0, 1.0))


def _jtubes(fit: dict) -> list[Part]:
    """J-tubes: from under the deck down the transition piece and the pile, a mitred bend outwards to a bell-mouth
    just above the seabed; clamps to the transition piece / pile."""
    dz = deck_z(fit)
    sb = float(fit["seabed_z"])
    parts = []
    r, y = JTUBE_R, JTUBE_Y
    top = dz - DECK_T - BEAM_H - 200.0
    z1 = sb + 1800.0
    d1 = np.array([0.0, math.sin(math.radians(30)), -math.cos(math.radians(30))])
    d2 = np.array([0.0, math.sin(math.radians(60)), -math.cos(math.radians(60))])
    p0, p1 = np.array([0.0, y, top]), np.array([0.0, y, z1])
    p2 = p1 + d1 * 800.0
    p3 = p2 + d2 * 700.0
    p4 = p3 + d2 * 500.0
    for i, az in enumerate(AZ_JTUBES):
        M = _az(az)
        tube = [_pipe([p0, p1, p2, p3], r), _cone(p3 - d2 * 1.0, p4, r, 2.1 * r),
                _zcyl(top - 40.0, top, r + 80.0, 0.0, y)]
        parts.append(Part(f"J-TUBE {i + 1}", "TOWER", _solid(occ.moved(_fuse(tube), M), f"J-TUBE {i + 1}")))
        for j, zc in enumerate((12000.0, 6000.0, -6000.0, -18000.0)):
            arm = _minus_round(occ.box((-40.0, 4800.0, zc - 75.0), (40.0, y - r - 10.0, zc + 75.0)), fit,
                               zc - 100.0, zc + 100.0)
            ring = _cut(_zcyl(zc - 75.0, zc + 75.0, r + 40.0, 0.0, y), _zcyl(zc - 76.0, zc + 76.0, r + 2.0, 0.0, y))
            c = occ.moved(_fuse([arm, ring]), M)
            parts.append(Part(f"CLAMP J-TUBE {i + 1}.{j + 1}", "TOWER", _solid(c, f"CLAMP J-TUBE {i + 1}.{j + 1}")))
    return parts


# ---------------------------------------------------------------------------
# the interface
# ---------------------------------------------------------------------------

def make(fit: dict, variant: str) -> list[Part]:
    """Every invented part of the variant, placed in its T frame at joint values 0."""
    _check(fit, variant)
    parts = _nacelle(fit) + _flanges(fit) + _door(fit, variant)
    parts += _offshore(fit) if variant == "offshore" else _onshore(fit)
    names = [p.name for p in parts]
    if len(set(names)) != len(names):
        raise RuntimeError("part names repeat")
    return parts


def joints(fit: dict, variant: str) -> list[dict]:
    """The door's hinge (opens outwards for positive values) and, offshore, the davit's slewing axis."""
    _check(fit, variant)
    M = _door_frame_M(fit, variant)
    out = [{"name": "Door", "kind": "ROTATE", "body": "DOOR",
            "point": [float(v) for v in _at(M, (HINGE_X, HINGE_Y, 0.0))], "direction": [0.0, 0.0, -1.0],
            "limits": [0.0, DOOR_OPEN]}]
    if variant == "offshore":
        MV = _az(AZ_DAVIT, deck_z(fit) + DAVIT_C0)
        out.append({"name": "Davit", "kind": "ROTATE", "body": "DAVIT",
                    "point": [float(v) for v in _at(MV, (0.0, DAVIT_R, 0.0))], "direction": [0.0, 0.0, 1.0],
                    "limits": [-DAVIT_ANGLE, DAVIT_ANGLE]})
    return out


def _on_round(part, r, az, z, kind, width, **what):
    n = _radial(az)
    p = n * r + np.array([0.0, 0.0, z])
    return dict(part=part, point=[float(v) for v in p], normal=[float(v) for v in n], up=[0.0, 0.0, 1.0],
                kind=kind, width_mm=float(width), **what)


def anchors(fit: dict, variant: str) -> list[dict]:
    """Where the decals go: the turbine ID, the heading marks, the door's safety sign, the davit's load sign."""
    _check(fit, variant)
    zt = threshold_z(fit, variant)
    out = []
    if variant == "offshore":
        out.append(_on_round("TP SLEEVE", TP_R, AZ_ID_TP, 7000.0, "TEXT", 2500.0, text=TURBINE_ID))
        for az, txt in HEADINGS:
            out.append(_on_round("TP SLEEVE", TP_R, az, 11500.0, "TEXT", 1500.0, text=txt))
    zi = zt + 1500.0
    out.append(_on_round(TOWER_PART, tower_radius(fit, zi), AZ_ID_TOWER, zi, "TEXT", 1000.0, text=TURBINE_ID))
    M = _door_frame_M(fit, variant)
    n = [float(v) for v in M[:3, 1]]
    for z, kind, width, what in ((1550.0, "STICKER", 300.0, {"sticker": "WARN_GENERAL"}),
                                 (1250.0, "TEXT", 700.0, {"text": "NO UNAUTHORISED ACCESS"})):
        out.append(dict(part="DOOR LEAF", point=[float(v) for v in _at(M, (0.0, LEAF_Y1, z))], normal=n,
                        up=[0.0, 0.0, 1.0], kind=kind, width_mm=width, **what))
    if variant == "offshore":
        MV = _az(AZ_DAVIT, deck_z(fit) + 4400.0 - 120.0)
        side = [float(v) for v in MV[:3, 0]]
        for y, kind, width, what in ((DAVIT_R + 1700.0, "TEXT", 500.0, {"text": "SWL 1 t"}),
                                     (DAVIT_R + 900.0, "STICKER", 180.0, {"sticker": "WARN_LOAD"})):
            out.append(dict(part="DAVIT", point=[float(v) for v in _at(MV, (80.0, y, 0.0))], normal=side,
                            up=[0.0, 0.0, 1.0], kind=kind, width_mm=width, **what))
    return out


def _cam(name, eye, target, lens):
    return {"name": name, "eye": [float(v) for v in eye], "target": [float(v) for v in target], "lens": float(lens)}


def cameras(fit: dict, variant: str) -> list[dict]:
    """Offshore: "Work boat" (low, on the boat landing's side, looking up) and "Whole turbine"; onshore:
    "From the field" (a person in the field 330 m away: all of it) and "At the door" (the door, stair and
    foundation from 26 m)."""
    _check(fit, variant)
    hub = np.asarray(fit["rotor"]["point"], float)
    if variant == "offshore":
        eye = _radial(AZ_LADDER) * 24000.0 + np.array([0.0, 0.0, fit["msl_z"] + 2500.0])
        return [_cam("Work boat", eye, (0.0, -4000.0, fit["msl_z"] + 26000.0), 24.0),
                _cam("Whole turbine", _radial(145.0) * 520000.0 + np.array([0.0, 0.0, fit["msl_z"] + 40000.0]),
                     (0.0, hub[1], fit["msl_z"] + 122000.0), 32.0)]
    g = float(fit.get("ground_z", 0.0))
    door = _radial(AZ_DOOR)
    side = np.cross([0.0, 0.0, 1.0], door)
    return [_cam("From the field", _radial(150.0) * 330000.0 + np.array([0.0, 0.0, g + 1700.0]),
                 (0.0, hub[1], g + 118000.0), 30.0),
            _cam("At the door", door * 26000.0 + side * 9000.0 + np.array([0.0, 0.0, g + 1700.0]),
                 door * 5000.0 + np.array([0.0, 0.0, g + 4500.0]), 30.0)]
