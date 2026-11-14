"""OpenCascade shapes, the scene tree and the STEP writer of the demo model (task 0076).

Scene tree: ``Part`` (a named, coloured shape; the same Part placed many times shares one mesh in the app) and
``Asm`` (a named assembly of placed children, 4 x 4 matrices in mm). An Asm can carry joint definitions in its own
coordinates; ``walk`` resolves them for every place the Asm is used, with the importer's uids ("NAME#n/…").
"""

from __future__ import annotations

import math

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepGProp import BRepGProp
from OCP.BRepLib import BRepLib
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                             BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol, BRepPrimAPI_MakeSphere)
from OCP.BRep import BRep_Builder
from OCP.collections import Array1_double, List_TopoDS_Shape
from OCP.GC import GC_MakeArcOfCircle
from OCP.Geom import Geom_CylindricalSurface
from OCP.Geom2d import Geom2d_Line
from OCP.Geom2dAPI import Geom2dAPI_PointsToBSpline
from OCP.GeomAbs import GeomAbs_Shape
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax1, gp_Ax2, gp_Ax3, gp_Circ, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d, gp_Trsf, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_StepModelType
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Compound
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

# ---------------------------------------------------------------------------------------------------------
# Matrices (4 x 4, mm)
# ---------------------------------------------------------------------------------------------------------


def T(x=0.0, y=0.0, z=0.0) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def Rot(axis, deg: float, about=(0.0, 0.0, 0.0)) -> np.ndarray:
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    r = np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                  [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                  [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])
    m = np.eye(4)
    m[:3, :3] = r
    p = np.asarray(about, float)
    m[:3, 3] = p - r @ p
    return m


def Frame(origin, xdir, zdir) -> np.ndarray:
    """Local -> model: local x along ``xdir``, local z along ``zdir`` (made square to x), y = z x x."""
    z = np.asarray(zdir, float)
    z = z / np.linalg.norm(z)
    x = np.asarray(xdir, float)
    x = x - z * (x @ z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
    m[:3, 3] = origin
    return m


def on_axis(p, d) -> np.ndarray:
    """A frame whose local z is the axis (p, d): for shapes made along z."""
    d = np.asarray(d, float)
    ref = [1.0, 0.0, 0.0] if abs(d[0]) < 0.9 * np.linalg.norm(d) else [0.0, 1.0, 0.0]
    return Frame(p, ref, d)


def trsf(m) -> gp_Trsf:
    t = gp_Trsf()
    t.SetValues(*[float(m[i, j]) for i in range(3) for j in range(4)])
    return t


def xform(shape, m):
    return BRepBuilderAPI_Transform(shape, trsf(m), True).Shape()


def P(v) -> gp_Pnt:
    return gp_Pnt(float(v[0]), float(v[1]), float(v[2]))


def D(v) -> gp_Dir:
    return gp_Dir(float(v[0]), float(v[1]), float(v[2]))


# ---------------------------------------------------------------------------------------------------------
# Solids
# ---------------------------------------------------------------------------------------------------------


def box(x0, y0, z0, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), float(dx), float(dy), float(dz)).Shape()


def box_c(c, size):
    """Box centred on c."""
    return box(c[0] - size[0] / 2, c[1] - size[1] / 2, c[2] - size[2] / 2, *size)


def beam(p0, p1, w: float, h: float | None = None, up=(0.0, 0.0, 1.0)):
    """A rectangular beam w x h from p0 to p1 (h along ``up`` as far as possible)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    h = w if h is None else h
    d = p1 - p0
    L = float(np.linalg.norm(d))
    up = np.asarray(up, float)
    if abs(up @ d) > 0.99 * L:
        up = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 * L else np.array([0.0, 1.0, 0.0])
    m = Frame(p0, up, d)                         # local z along the beam, local x along "up"
    return xform(box(-h / 2, -w / 2, 0.0, h, w, L), m)


def cyl(r: float, h: float, p=(0.0, 0.0, 0.0), d=(0.0, 0.0, 1.0)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(P(p), D(d)), float(r), float(h)).Shape()


def rod(p0, p1, r: float):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    return cyl(r, float(np.linalg.norm(p1 - p0)), p0, p1 - p0)


def tube(ro: float, ri: float, h: float, p=(0.0, 0.0, 0.0), d=(0.0, 0.0, 1.0)):
    return cut(cyl(ro, h, p, d), cyl(ri, h + 2.0, np.asarray(p, float) - np.asarray(D_(d)), d))


def D_(d):
    d = np.asarray(d, float)
    return d / np.linalg.norm(d)


def cone(r1: float, r2: float, h: float, p=(0.0, 0.0, 0.0), d=(0.0, 0.0, 1.0)):
    return BRepPrimAPI_MakeCone(gp_Ax2(P(p), D(d)), float(r1), float(r2), float(h)).Shape()


def sphere(r: float, p=(0.0, 0.0, 0.0)):
    return BRepPrimAPI_MakeSphere(P(p), float(r)).Shape()


def _list(shapes) -> List_TopoDS_Shape:
    lst = List_TopoDS_Shape()
    for s in shapes:
        lst.Append(s)
    return lst


def fuse(*shapes):
    shapes = [s for s in shapes if s is not None]
    if len(shapes) == 1:
        return shapes[0]
    op = BRepAlgoAPI_Fuse()
    op.SetArguments(_list(shapes[:1]))
    op.SetTools(_list(shapes[1:]))
    op.Build()
    if not op.IsDone():
        raise RuntimeError("fuse failed")
    op.SimplifyResult()
    return op.Shape()


def cut(a, *tools):
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


def common(a, b):
    return BRepAlgoAPI_Common(a, b).Shape()


def compound(*shapes):
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for s in shapes:
        if s is not None:
            b.Add(c, s)
    return c


def volume(shape) -> float:
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()


def mass_centre(root: "Asm") -> tuple[float, np.ndarray]:
    """Volume and centre of volume of every part of an assembly (in its coordinates): one material all through."""
    vol, mom = 0.0, np.zeros(3)
    for node, _uid, W, _label, _path in walk(root):
        if not isinstance(node, Part):
            continue
        gp = GProp_GProps()
        BRepGProp.VolumeProperties_s(node.shape, gp)
        c = gp.CentreOfMass()
        v = gp.Mass()
        vol += v
        mom += v * (W @ np.array([c.X(), c.Y(), c.Z(), 1.0]))[:3]
    return vol, mom / max(vol, 1e-9)


def _wire2d(profile, plane=lambda u, v: gp_Pnt(u, 0.0, v)):
    """Closed wire from a 2D profile: points (u, v) and ("arc", (u, v) through, (u, v) end)."""
    w = BRepBuilderAPI_MakeWire()
    first = profile[0]
    cur = first
    items = list(profile[1:]) + [first]
    for it in items:
        if isinstance(it, tuple) and len(it) == 3 and it[0] == "arc":
            arc = GC_MakeArcOfCircle(plane(*cur), plane(*it[1]), plane(*it[2])).Value()
            w.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
            cur = it[2]
        else:
            if math.hypot(it[0] - cur[0], it[1] - cur[1]) > 1e-9:
                w.Add(BRepBuilderAPI_MakeEdge(plane(*cur), plane(*it)).Edge())
            cur = it
    return w.Wire()


def revolve(profile, p=(0.0, 0.0, 0.0), d=(0.0, 0.0, 1.0), angle: float = 360.0):
    """Solid of revolution of a closed (r, z) profile about the axis (p, d)."""
    face = BRepBuilderAPI_MakeFace(_wire2d(profile), True).Face()
    s = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(angle)).Shape()
    return xform(s, on_axis(p, d))


def prism(profile, h: float, m=None):
    """Closed (x, y) profile extruded along z by h, then placed with matrix m."""
    face = BRepBuilderAPI_MakeFace(_wire2d(profile, lambda u, v: gp_Pnt(u, v, 0.0)), True).Face()
    s = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(h))).Shape()
    return s if m is None else xform(s, m)


def polygon_prism(points, h: float, m=None):
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        poly.Add(gp_Pnt(float(x), float(y), 0.0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    s = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(h))).Shape()
    return s if m is None else xform(s, m)


def torus_piece(centre, normal, start, angle: float, r: float):
    """Round bar of radius r along a circle arc (the cable or a rope round a sheave)."""
    centre, normal, start = np.asarray(centre, float), D_(normal), np.asarray(start, float)
    u = start - centre
    R = float(np.linalg.norm(u))
    u = u / R
    # local frame: z = arc axis, x = towards the start; the bar's section is a circle in the x-z plane at x = R
    m = Frame(centre, u, normal)
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(
        gp_Circ(gp_Ax2(gp_Pnt(R, 0, 0), gp_Dir(0, 1, 0)), float(r))).Edge()).Wire(), True).Face()
    s = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), float(angle)).Shape()
    return xform(s, m)


def route_wire(route):
    """A wire of the route's straights and arcs (G1: they meet with the same direction)."""
    w = BRepBuilderAPI_MakeWire()
    for seg in route.segments:
        if seg.length < 1e-6:
            continue
        if seg.kind == "line":
            w.Add(BRepBuilderAPI_MakeEdge(P(seg.start), P(seg.end)).Edge())
        else:
            arc = GC_MakeArcOfCircle(P(seg.start), P(seg.point(seg.length / 2)), P(seg.end)).Value()
            w.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    return w.Wire()


def route_solid(route, r: float):
    """One round bar of radius r along the whole route (a pipe swept along its wire: one solid)."""
    seg = route.segments[0]
    t = seg.start_tangent
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(P(seg.start), D(t)), float(r))).Edge()).Wire()
    ps = BRepOffsetAPI_MakePipeShell(route_wire(route))
    ps.SetMode(False)                          # corrected Frenet: no twist on the straights
    ps.Add(prof)
    ps.Build()
    ps.MakeSolid()
    return ps.Shape()


def solids(shape) -> int:
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    n = 0
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        n += 1
        ex.Next()
    return n


# ---------------------------------------------------------------------------------------------------------
# Grooved parts: sheaves, helical (spiral-groove) and Lebus drums
# ---------------------------------------------------------------------------------------------------------


def sheave_profile(rp: float, rr: float, hub_r: float, bore_r: float, width: float | None = None,
                   web: float | None = None, flank_deg: float = 60.0):
    """(r, z) profile of a sheave whose groove is a circle of radius rr round the rope-centre radius rp.

    Revolved, the groove is a torus with major radius rp: the rope's centre runs on rp (task 0075 reads it)."""
    width = width or 2.6 * rr
    web = web or max(0.25 * width, 30.0)
    b = math.radians(flank_deg)
    rf = rp + 1.25 * rr                         # flange tip
    rim_in = rp - rr - max(0.4 * rr, 25.0)      # rim's inner radius
    a1 = (rp - rr * math.cos(b), -rr * math.sin(b))
    a2 = (rp - rr * math.cos(b), rr * math.sin(b))
    hub_w = max(width, 2.0 * web)
    prof = [(bore_r, -hub_w / 2), (hub_r, -hub_w / 2), (hub_r, -web / 2), (rim_in, -web / 2),
            (rim_in, -width / 2), (rf, -width / 2), a1, ("arc", (rp - rr, 0.0), a2), (rf, width / 2),
            (rim_in, width / 2), (rim_in, web / 2), (hub_r, web / 2), (hub_r, hub_w / 2), (bore_r, hub_w / 2)]
    return prof


def sheave(rp: float, rr: float, hub_r: float | None = None, bore_r: float | None = None,
           width: float | None = None, holes: int = 0):
    """A grooved sheave about local z through the origin; ``holes`` lightening holes in the web."""
    hub_r = hub_r or max(0.18 * rp, rr * 2.5)
    bore_r = bore_r or 0.45 * hub_r
    s = revolve(sheave_profile(rp, rr, hub_r, bore_r, width))
    if holes:
        rim_in = rp - rr - max(0.4 * rr, 25.0)
        rc = 0.5 * (rim_in + hub_r)
        rh = min(0.28 * (rim_in - hub_r), 0.38 * math.pi * rc / holes)     # the holes never meet
        tools = [cyl(rh, 4 * rr + 400, (rc * math.cos(2 * math.pi * k / holes), rc * math.sin(2 * math.pi * k / holes),
                                         -2 * rr - 200)) for k in range(holes)]
        s = cut(s, *tools)
    return s


def _smooth(t: float) -> float:
    """0 -> 1 with level ends (smoothstep)."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _spine_on_cylinder(radius: float, v_of_u, u_end: float, n: int):
    """Edge on the cylinder x^2 + y^2 = radius^2: height v(u) at angle u (a B-spline through n samples)."""
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), float(radius))
    if v_of_u is None:
        raise ValueError
    ys = Array1_double(1, n)
    du = u_end / (n - 1)
    for i in range(n):
        ys.SetValue(i + 1, float(v_of_u(i * du)))
    fit = Geom2dAPI_PointsToBSpline(ys, 0.0, du, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-3)
    c2d = fit.Curve()
    # the fitted curve is y(x) with x = u: a 2D curve (u, v) on the surface
    e = BRepBuilderAPI_MakeEdge(c2d, surf, c2d.FirstParameter(), c2d.LastParameter()).Edge()
    BRepLib.BuildCurves3d_s(e, 1e-4, GeomAbs_Shape.GeomAbs_C1, 14, 4000)
    return e


def _helix_edge(radius: float, z0: float, pitch: float, turns: float):
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), float(radius))
    line = Geom2d_Line(gp_Pnt2d(0.0, float(z0)), gp_Dir2d(2 * math.pi, float(pitch)))
    length = turns * math.hypot(2 * math.pi, pitch)
    e = BRepBuilderAPI_MakeEdge(line, surf, 0.0, length).Edge()
    BRepLib.BuildCurves3d_s(e, 1e-5, GeomAbs_Shape.GeomAbs_C1, 14, 2000)
    return e


def _edge_curve(edge):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    a = BRepAdaptor_Curve(edge)
    return a, a.FirstParameter(), a.LastParameter()


def sweep_round(edge, r: float):
    a, f, _l = _edge_curve(edge)
    p0, v0 = gp_Pnt(), gp_Vec()
    a.D1(f, p0, v0)
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(p0, gp_Dir(v0)), float(r))).Edge()).Wire()
    ps = BRepOffsetAPI_MakePipeShell(BRepBuilderAPI_MakeWire(edge).Wire())
    ps.SetMode(gp_Dir(0, 0, 1))
    ps.Add(prof)
    ps.Build()
    ps.MakeSolid()
    return ps.Shape()


def grooved_barrel(rc: float, rr: float, z0: float, z1: float, pitch: float, kind: str = "spiral",
                   crossover_deg: float = 18.0):
    """Drum barrel (about local z, from z0 to z1) with a rope groove of radius rr whose centre runs at radius rc.

    ``spiral``: one helical groove (pitch along z per turn). ``lebus``: parallel (level) grooves with two crossover
    zones per turn, 180° apart, each shifting the groove by half a pitch – the rope's centre still at radius rc.
    The barrel's outer radius leaves a groove depth of 0.35 x the rope Ø."""
    ro = rc - rr + 0.7 * rr
    length = z1 - z0
    start = z0 + 0.5 * pitch + rr                  # first groove's centre
    turns = int((z1 - rr - start) // pitch)
    barrel = cyl(ro, length, (0, 0, z0))
    if kind == "spiral":
        e = _helix_edge(rc, start, pitch, turns)
    elif kind == "lebus":
        # level grooves (torus pieces: cheap, exact) joined by short smooth crossovers (each a half pitch over
        # crossover_deg, tangent level at both ends); every turn: level, crossover, level, crossover
        cz = math.radians(crossover_deg)
        cross = _spine_on_cylinder(rc, lambda u: 0.5 * pitch * _smooth(u / cz), cz, 17)
        cross_tool = sweep_round(cross, rr)
        pieces = []
        for k in range(turns):
            for half in (0, 1):
                a0 = half * math.pi
                z = start + k * pitch + half * 0.5 * pitch
                pieces.append(xform(cross_tool, T(0, 0, z) @ Rot((0, 0, 1), math.degrees(a0))))
                p0 = np.array([rc * math.cos(a0 + cz), rc * math.sin(a0 + cz), z + 0.5 * pitch])
                pieces.append(torus_piece((0, 0, z + 0.5 * pitch), (0, 0, 1), p0, math.pi - cz, rr))
        return cut(barrel, *pieces), turns
    groove = sweep_round(e, rr)
    return cut(barrel, groove), turns


def loft(sections, ruled: bool = True):
    """A solid through closed polygon sections (lists of 3D points, the same count each)."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    ts = BRepOffsetAPI_ThruSections(True, ruled, 1e-6)
    for pts in sections:
        poly = BRepBuilderAPI_MakePolygon()
        for q in pts:
            poly.Add(P(q))
        poly.Close()
        ts.AddWire(poly.Wire())
    ts.CheckCompatibility(False)
    ts.Build()
    return ts.Shape()


def riser_wedge(ro: float, h: float, width: float, angle_deg: float, z_flange: float, side: int, n: int = 9):
    """Lebus riser / filler: a ramp on the barrel (radius ro) against a flange at z_flange (side -1: the flange is
    below, +1: above), rising from 10 % to 100 % of h over angle_deg (about local z)."""
    z0, z1 = (z_flange, z_flange + width) if side < 0 else (z_flange - width, z_flange)
    secs = []
    for k in range(n):
        t = k / (n - 1)
        a = math.radians(angle_deg * t)
        hh = h * (0.1 + 0.9 * t)
        rs = (ro - 5.0, ro + hh)
        secs.append([(r * math.cos(a), r * math.sin(a), z) for r, z in
                     ((rs[0], z0), (rs[1], z0), (rs[1], z1), (rs[0], z1))])
    return loft(secs)


def trough(points, frames, profile):
    """A trough (open-topped channel) along sampled ``points`` with a local (side, up) frame at each: ``profile`` is
    a closed polygon of (side, up) offsets. Ruled between the samples."""
    secs = []
    for q, (sd, up) in zip(points, frames):
        q, sd, up = np.asarray(q, float), np.asarray(sd, float), np.asarray(up, float)
        secs.append([q + a * sd + b * up for a, b in profile])
    return loft(secs)


# ---------------------------------------------------------------------------------------------------------
# Scene tree
# ---------------------------------------------------------------------------------------------------------


class Part:
    def __init__(self, name: str, shape, color=None):
        self.name = name
        self.shape = shape
        self.color = color


class Child:
    def __init__(self, parent: "Asm", node, M, instance: str):
        self.parent = parent
        self.node = node
        self.M = np.asarray(M, float)
        self.instance = instance

    def uid_piece(self) -> str:
        n = 0
        for c in self.parent.children:
            if c.node.name == self.node.name:
                n += 1
            if c is self:
                return f"{self.node.name}#{n}"
        raise ValueError("child not in its parent")


class Joint:
    """A joint in its assembly's coordinates. ``parts``: paths of Child objects from that assembly down."""

    def __init__(self, name: str, kind: str, parts: list, point, direction, limits=None, drive=None, **extra):
        self.name = name
        self.kind = kind
        self.parts = [p if isinstance(p, (list, tuple)) else [p] for p in parts]
        self.point = np.asarray(point, float)
        self.direction = D_(direction)
        self.limits = limits
        self.drive = drive or {}
        self.extra = extra


class Asm:
    def __init__(self, name: str):
        self.name = name
        self.children: list[Child] = []
        self.joints: list[Joint] = []
        self.info: dict = {}             # anything else for the JSON sheets, in this assembly's coordinates

    def add(self, node, M=None, instance: str = "") -> Child:
        c = Child(self, node, np.eye(4) if M is None else M, instance)
        self.children.append(c)
        return c

    def joint(self, *a, **k) -> Joint:
        j = Joint(*a, **k)
        self.joints.append(j)
        return j


def walk(root: Asm, M=None):
    """Every node once per place: (node, uid, world matrix, label, path of Child objects)."""
    out = []

    def rec(node, uid, W, label, path):
        out.append((node, uid, W, label, path))
        if isinstance(node, Asm):
            for c in node.children:
                rec(c.node, f"{uid}/{c.uid_piece()}", W @ c.M, c.instance or c.node.name, path + [c])
    rec(root, f"{root.name}#1", np.eye(4) if M is None else M, root.name, [])
    return out


def path_uid(base_uid: str, path) -> str:
    return "/".join([base_uid] + [c.uid_piece() for c in path])


def path_matrix(W, path):
    for c in path:
        W = W @ c.M
    return W


def resolve_joints(root: Asm) -> list[dict]:
    """All joints of the tree in model coordinates, with the parts as importer uids. A joint's name starts with
    the labels (occurrence name, else name) of the assemblies it sits in below the root: "TENSIONER 1: Squeeze"."""
    out = []
    for node, uid, W, _label, path in walk(root):
        if not isinstance(node, Asm):
            continue
        labels = [c.instance or c.node.name for c in path]
        prefix = "".join(f"{lb}: " for lb in labels)

        def ref(name: str) -> str:
            """A joint named relative to this assembly; each leading "../" goes one assembly up."""
            k = 0
            while name.startswith("../"):
                name, k = name[3:], k + 1
            return "".join(f"{lb}: " for lb in labels[:len(labels) - k]) + name
        for j in node.joints:
            parts = [path_uid(uid, p) for p in j.parts]
            d = {"name": prefix + j.name, "type": j.kind, "parts": parts,
                 "axis": {"point": [round(float(v), 4) for v in (W @ np.r_[j.point, 1.0])[:3]],
                          "direction": [round(float(v), 6) for v in W[:3, :3] @ j.direction]},
                 "limits": j.limits, "drive": dict(j.drive), "assembly": uid}
            if "follows" in d["drive"]:
                d["drive"]["follows"] = ref(d["drive"]["follows"])
            for k, v in j.extra.items():
                d[k] = ref(v) if k == "rides_on" else v
            out.append(d)
    return out


def count_parts(root: Asm) -> int:
    return sum(1 for n, *_ in walk(root) if isinstance(n, Part))


# ---------------------------------------------------------------------------------------------------------
# STEP writer
# ---------------------------------------------------------------------------------------------------------


def _quiet() -> None:
    """OpenCascade's STEP writer prints statistics for every file: keep only failures."""
    try:
        from OCP.Message import Message, Message_Gravity
        printers = Message.DefaultMessenger_s().Printers()
        for p in printers:
            p.SetTraceLevel(Message_Gravity.Message_Fail)
    except Exception:          # pragma: no cover - an older OCP
        pass


def write_step(root: Asm, path: str) -> None:
    _quiet()
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    labels: dict = {}

    def name(lab, text):
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(text))

    def label(node):
        key = id(node)
        if key in labels:
            return labels[key]
        if isinstance(node, Part):
            if solids(node.shape) != 1:
                # the importer reads a part's colour only when it is one solid (several solids: no colour)
                raise ValueError(f"part {node.name} is {solids(node.shape)} solids, not 1")
            lab = st.AddShape(node.shape, False)
            name(lab, node.name)
            if node.color:
                r, g, b = node.color
                ct.SetColor(lab, Quantity_Color(r, g, b, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        else:
            kids = [(c, label(c.node)) for c in node.children]
            lab = st.NewShape()
            name(lab, node.name)
            for c, kl in kids:
                comp = st.AddComponent(lab, kl, TopLoc_Location(trsf(c.M)))
                if c.instance:
                    name(comp, c.instance)
        labels[key] = lab
        return lab

    bad = sorted({f"{n.name} ({solids(n.shape)} solids)" for n, *_ in walk(root)
                  if isinstance(n, Part) and solids(n.shape) != 1})
    if bad:
        raise ValueError("parts must be one solid each (the importer reads no colour otherwise): " + ", ".join(bad))
    label(root)
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"writing {path} failed")
