"""Small OpenCascade helpers shared by the wind-turbine converter and its invented parts (task 0116).

Everything is in millimetres. Matrices are 4 x 4 NumPy arrays (rotation + translation, row-major, as ``a4.trsf``
takes them). No Blender.
"""

from __future__ import annotations

import math

import numpy as np


def trsf(M: np.ndarray):
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(*(float(M[i, j]) for i in range(3) for j in range(4)))
    return t


def matrix_of(loc) -> np.ndarray:
    """A TopLoc_Location as a 4 x 4 matrix."""
    T = loc.Transformation()
    M = np.eye(4)
    for i in range(3):
        for j in range(4):
            M[i, j] = T.Value(i + 1, j + 1)
    return M


def moved(shape, M: np.ndarray):
    """``shape`` placed by M (a copy of the geometry with M applied: the result has no location of its own)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    return BRepBuilderAPI_Transform(shape, trsf(M), True).Shape()


def rot_z(deg: float) -> np.ndarray:
    a = math.radians(deg)
    M = np.eye(4)
    M[:2, :2] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return M


def translate(v) -> np.ndarray:
    M = np.eye(4)
    M[:3, 3] = v
    return M


def frame(origin, z, x=None) -> np.ndarray:
    """A right-handed frame with its z axis along ``z`` (x along ``x`` made square to z, or any)."""
    z = np.asarray(z, float)
    z = z / np.linalg.norm(z)
    if x is None:
        x = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = np.asarray(x, float) - np.dot(x, z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, origin
    return M


def bbox(shape) -> tuple[np.ndarray, np.ndarray]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    return np.array([lo.X(), lo.Y(), lo.Z()]), np.array([hi.X(), hi.Y(), hi.Z()])


def volume(shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return float(g.Mass())


def count(shape, kind: str) -> int:
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    e = TopExp_Explorer(shape, {"solid": TopAbs_SOLID, "shell": TopAbs_SHELL, "face": TopAbs_FACE}[kind])
    n = 0
    while e.More():
        n += 1
        e.Next()
    return n


def solids(shape) -> list:
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out, e = [], TopExp_Explorer(shape, TopAbs_SOLID)
    while e.More():
        out.append(TopoDS.Solid_s(e.Current()) if hasattr(TopoDS, "Solid_s") else TopoDS.Solid(e.Current()))
        e.Next()
    return out


def faces(shape) -> list:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out, e = [], TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        out.append(TopoDS.Face_s(e.Current()) if hasattr(TopoDS, "Face_s") else TopoDS.Face(e.Current()))
        e.Next()
    return out


def surface(face) -> dict:
    """What a face is: {"kind": "cylinder"/"plane"/"cone"/"sphere"/"other", "point", "dir", "r", "area", "centre"}."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
    from OCP.GProp import GProp_GProps
    s = BRepAdaptor_Surface(face)
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    c = g.CentreOfMass()
    out = {"kind": "other", "area": float(g.Mass()), "centre": np.array([c.X(), c.Y(), c.Z()])}
    t = s.GetType()

    def ax(a):
        p, d = a.Location(), a.Direction()
        return np.array([p.X(), p.Y(), p.Z()]), np.array([d.X(), d.Y(), d.Z()])
    if t == GeomAbs_Cylinder:
        cy = s.Cylinder()
        out["point"], out["dir"] = ax(cy.Axis())
        out.update(kind="cylinder", r=float(cy.Radius()))
    elif t == GeomAbs_Plane:
        out["point"], out["dir"] = ax(s.Plane().Axis())
        out["kind"] = "plane"
    elif t == GeomAbs_Cone:
        co = s.Cone()
        out["point"], out["dir"] = ax(co.Axis())
        out.update(kind="cone", r=float(co.RefRadius()), angle=math.degrees(co.SemiAngle()))
    elif t == GeomAbs_Sphere:
        sp = s.Sphere()
        p = sp.Location()
        out.update(kind="sphere", point=np.array([p.X(), p.Y(), p.Z()]), r=float(sp.Radius()))
    return out


def common(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    op = BRepAlgoAPI_Common(a, b)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("boolean common failed")
    return op.Shape()


def cut(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    op = BRepAlgoAPI_Cut(a, b)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("boolean cut failed")
    return op.Shape()


def fuse(*shapes):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    out = shapes[0]
    for s in shapes[1:]:
        op = BRepAlgoAPI_Fuse(out, s)
        op.Build()
        if not op.IsDone():
            raise RuntimeError("boolean fuse failed")
        out = op.Shape()
    return out


def box(lo, hi):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeBox(gp_Pnt(*map(float, lo)), gp_Pnt(*map(float, hi))).Shape()


def one_solid(shape, what: str = "part"):
    """The one solid of ``shape`` (the importer drops the colour of a part made of several, CLAUDE.md section 8)."""
    ss = solids(shape)
    if len(ss) != 1:
        raise ValueError(f"{what}: {len(ss)} solids, need one")
    return ss[0]


def is_valid(shape) -> bool:
    from OCP.BRepCheck import BRepCheck_Analyzer
    return bool(BRepCheck_Analyzer(shape).IsValid())


def edge_points(edge, n: int = 64) -> np.ndarray:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    c = BRepAdaptor_Curve(edge)
    t0, t1 = c.FirstParameter(), c.LastParameter()
    out = []
    for k in range(n + 1):
        p = c.Value(t0 + (t1 - t0) * k / n)
        out.append((p.X(), p.Y(), p.Z()))
    return np.array(out)


def edges(shape) -> list:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out, e = [], TopExp_Explorer(shape, TopAbs_EDGE)
    while e.More():
        out.append(TopoDS.Edge_s(e.Current()) if hasattr(TopoDS, "Edge_s") else TopoDS.Edge(e.Current()))
        e.Next()
    return out


def fit_circle(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """(centre, normal, radius, worst distance off the circle) of points that lie on a circle in 3-D."""
    c0 = pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(pts - c0)
    n = vt[2]
    e1, e2 = vt[0], vt[1]
    x, y = (pts - c0) @ e1, (pts - c0) @ e2
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    sol, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
    cx, cy = sol[0], sol[1]
    r = math.sqrt(sol[2] + cx * cx + cy * cy)
    c = c0 + cx * e1 + cy * e2
    d = np.hypot(x - cx, y - cy) - r
    off = np.abs((pts - c) @ n)
    return c, n, r, float(max(np.abs(d).max(), off.max()))


def tri_count(shape, linear: float, angular_deg: float) -> int:
    """Triangles of ``shape`` meshed with these deflections (mm, DEGREES – the importer's QUALITY gives radians)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    BRepMesh_IncrementalMesh(shape, linear, False, math.radians(angular_deg), True)
    n = 0
    for f in faces(shape):
        tri = BRep_Tool.Triangulation_s(f, TopLoc_Location())
        if tri is not None:
            n += tri.NbTriangles()
    return n


def surface_points(face, n: int = 200) -> np.ndarray:
    """An n x n grid of points on a face's surface (its parameter range), as (n*n, 3)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    s = BRepAdaptor_Surface(face)
    u0, u1, v0, v1 = s.FirstUParameter(), s.LastUParameter(), s.FirstVParameter(), s.LastVParameter()
    out = np.empty((n * n, 3))
    k = 0
    for i in range(n):
        u = u0 + (u1 - u0) * i / (n - 1)
        for j in range(n):
            p = s.Value(u, v0 + (v1 - v0) * j / (n - 1))
            out[k] = (p.X(), p.Y(), p.Z())
            k += 1
    return out
