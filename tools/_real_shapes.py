"""Shared helpers of the real-size faces / decals test models (task 0235): fillets, holes, face picking by plane.

Plain OpenCascade (OCP); every part comes out as ONE solid. Lengths in mm."""

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Line


def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cylinder(x, y, z, r, h, axis=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*axis)), r, h).Shape()


def fuse(a, b):
    return BRepAlgoAPI_Fuse(a, b).Shape()


def cut(a, b):
    return BRepAlgoAPI_Cut(a, b).Shape()


def _edges(shape):
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    seen = []
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        if not any(e.IsSame(s) for s in seen):
            seen.append(e)
        exp.Next()
    return seen


def _direction(edge):
    c = BRepAdaptor_Curve(edge)
    if c.GetType() != GeomAbs_Line:
        return None
    d = c.Line().Direction()
    return d.X(), d.Y(), d.Z()


def round_edges(shape, r, along=None, chamfer=False, circles=False):
    """Fillet (or chamfer) the straight edges parallel to ``along`` (an axis index 0/1/2; None: all straight edges)."""
    mk = BRepFilletAPI_MakeChamfer(shape) if chamfer else BRepFilletAPI_MakeFillet(shape)
    n = 0
    for e in _edges(shape):
        d = _direction(e)
        if circles and d is None:
            mk.Add(r, e)
            n += 1
            continue
        if d is None or (along is not None and abs(d[along]) < 0.999):
            continue
        mk.Add(r, e)
        n += 1
    if n:
        mk.Build()
        return mk.Shape()
    return shape


def holes(shape, centres, r, z0, z1):
    """Vertical holes of radius r through z0..z1 at the (x, y) centres."""
    for x, y in centres:
        shape = cut(shape, cylinder(x, y, z0, r, z1 - z0))
    return shape


def find_face(shape, normal, at):
    """Index (explorer order) of the planar face with this outward normal lying on the plane through coordinate
    ``at`` along the normal's axis, the biggest such face (-1: none)."""
    axis = max(range(3), key=lambda i: abs(normal[i]))
    best, best_area = -1, 0.0
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    k = 0
    while exp.More():
        f = TopoDS.Face(exp.Current())
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Plane:
            pl = s.Plane()
            d = pl.Axis().Direction()
            n = [d.X(), d.Y(), d.Z()]
            if f.Orientation() == TopAbs_REVERSED:
                n = [-v for v in n]
            loc = (pl.Location().X(), pl.Location().Y(), pl.Location().Z())
            if sum(a * b for a, b in zip(n, normal)) > 0.999 and abs(loc[axis] - at) < 1e-6:
                g = GProp_GProps()
                BRepGProp.SurfaceProperties_s(f, g)
                if g.Mass() > best_area:
                    best, best_area = k, g.Mass()
        exp.Next()
        k += 1
    return best
