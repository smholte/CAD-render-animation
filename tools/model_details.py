"""Details for the invented test models (task 0122): chamfers, chamfered and rounded outlines, hex heads, bolts,
screws, nuts and washers – plain OpenCascade shapes in mm, each one solid, made with
``fresing_render/demo_model/geom.py``.

A test-model part stays ONE solid (fuse its pieces): a part of several solids loses its colour in the importer.
Fastener names follow the standard's notation so the part library sorts them ("ISO 4017 M12 x 40 - 8.8",
"ISO 4762 M10 x 20 - 12.9", "ISO 4032 M12 - 8", "ISO 7089 12 - 200 HV").
"""

from __future__ import annotations

import math
import os
import sys

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.GeomAbs import GeomAbs_Line
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fresing_render.demo_model import geom as g  # noqa: E402


def edges(shape):
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        yield TopoDS.Edge(ex.Current())
        ex.Next()


def edge_ends(edge) -> list:
    pts = []
    ex = TopExp_Explorer(edge, TopAbs_VERTEX)
    while ex.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(ex.Current()))
        pts.append((p.X(), p.Y(), p.Z()))
        ex.Next()
    return pts


def _pick(shape, keep):
    seen = set()
    for e in edges(shape):
        if BRepAdaptor_Curve(e).GetType() != GeomAbs_Line:
            continue
        ends = edge_ends(e)
        key = tuple(sorted(tuple(round(c, 3) for c in p) for p in ends))
        if key in seen or len(ends) < 2 or not all(keep(p) for p in ends):
            continue
        seen.add(key)
        yield e


def chamfer(shape, d: float, keep):
    """Chamfer (d mm) every straight edge whose two ends both pass ``keep((x, y, z))``. Flat: cheap in triangles."""
    mk = BRepFilletAPI_MakeChamfer(shape)
    n = 0
    for e in _pick(shape, keep):
        mk.Add(float(d), e)
        n += 1
    if not n:
        return shape
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("chamfer failed")
    return mk.Shape()


def fillet(shape, r: float, keep):
    """Round (r mm) every straight edge whose two ends pass ``keep``. Costs triangles: prefer ``chamfer``."""
    mk = BRepFilletAPI_MakeFillet(shape)
    n = 0
    for e in _pick(shape, keep):
        mk.Add(float(r), e)
        n += 1
    if not n:
        return shape
    mk.Build()
    if not mk.IsDone():
        raise RuntimeError("fillet failed")
    return mk.Shape()


def chamfered_rect(x0, y0, w, h, c) -> list:
    """(x, y) corners of a w x h rectangle with its corners cut by c (for ``g.polygon_prism``)."""
    return [(x0 + c, y0), (x0 + w - c, y0), (x0 + w, y0 + c), (x0 + w, y0 + h - c), (x0 + w - c, y0 + h),
            (x0 + c, y0 + h), (x0, y0 + h - c), (x0, y0 + c)]


def rounded_rect(x0, y0, w, h, r) -> list:
    """A w x h rectangle with round corners r, as a profile for ``g.prism``."""
    s = r * (1 - math.sqrt(0.5))
    x1, y1 = x0 + w, y0 + h
    return [(x0 + r, y0), (x1 - r, y0), ("arc", (x1 - s, y0 + s), (x1, y0 + r)),
            (x1, y1 - r), ("arc", (x1 - s, y1 - s), (x1 - r, y1)),
            (x0 + r, y1), ("arc", (x0 + s, y1 - s), (x0, y1 - r)),
            (x0, y0 + r), ("arc", (x0 + s, y0 + s), (x0 + r, y0))]


def hex_prism(af: float, h: float, z0: float = 0.0):
    """A hexagon ``af`` across flats, z0 .. z0 + h, on the z axis."""
    r = af / math.sqrt(3.0)
    pts = [(r * math.cos(math.radians(30 + 60 * k)), r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return g.polygon_prism(pts, h, g.T(0, 0, z0))


# ISO metric: thread d -> (hex across flats, hex head height, socket head Ø, socket head height, socket af, nut height)
METRIC = {6: (10, 4.0, 10, 6, 5, 5.2), 8: (13, 5.3, 13, 8, 6, 6.8), 10: (16, 6.4, 16, 10, 8, 8.4),
          12: (18, 7.5, 18, 12, 10, 10.8), 16: (24, 10.0, 24, 16, 14, 14.8), 20: (30, 12.5, 30, 20, 17, 18.0),
          24: (36, 15.0, 36, 24, 19, 21.5), 30: (46, 18.7, 45, 30, 22, 25.6)}


def hex_bolt(d: int, length: float):
    """ISO 4017 hex head bolt: the head on z 0 .. k (with a thin washer face), the shank down to z = -length."""
    af, k = METRIC[d][:2]
    return g.fuse(hex_prism(af, k), g.cyl(af * 0.48, 0.6), g.cyl(d / 2, length, (0, 0, -length)))


def socket_screw(d: int, length: float):
    """ISO 4762 socket head cap screw: the head on z 0 .. d with its hex socket, the shank down to z = -length."""
    _af, _k, dk, k, s, _m = METRIC[d]
    head = g.cut(g.cyl(dk / 2, k), hex_prism(s, k * 0.6, k * 0.41))
    return g.fuse(head, g.cyl(d / 2, length, (0, 0, -length)))


def nut(d: int):
    """ISO 4032 hex nut on z 0 .. m with its bore (a separate part on a bolt's shank: the bore is 0.5 mm wider)."""
    af, _k, _dk, _hk, _s, m = METRIC[d]
    return g.cut(hex_prism(af, m), g.cyl(d / 2 + 0.25, m + 2, (0, 0, -1)))


def washer(d: int):
    """ISO 7089 washer on z 0 .. t."""
    od, t = {6: (12, 1.6), 8: (16, 1.6), 10: (20, 2.0), 12: (24, 2.5), 16: (30, 3.0), 20: (37, 3.0),
             24: (44, 4.0), 30: (56, 4.0)}[d]
    return g.cut(g.cyl(od / 2, t), g.cyl(d / 2 + 0.2, t + 2, (0, 0, -1)))
