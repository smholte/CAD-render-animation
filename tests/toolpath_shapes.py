"""Triangles of the toolpath test model's stock and finished part, meshed with OpenCascade (no Blender), for
tests/test_toolpath_core.py. Program coordinates: the work zero on the top centre of the stock."""

from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))


def mesh(shape, lin=0.15, ang=0.3) -> np.ndarray:
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, lin, False, ang, True)
    out = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        f = TopoDS.Face(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is not None:
            tr = loc.Transformation()
            pts = np.array([[*tri.Node(i + 1).Transformed(tr).Coord()] for i in range(tri.NbNodes())])
            rev = f.Orientation() == TopAbs_REVERSED
            for k in range(tri.NbTriangles()):
                a, b, c = tri.Triangle(k + 1).Get()
                out.append(pts[[a - 1, c - 1, b - 1]] if rev else pts[[a - 1, b - 1, c - 1]])
        exp.Next()
    return np.array(out)


def model(lin=0.15):
    """(part triangles, stock triangles) in program coordinates (mm)."""
    import make_test_toolpath as m
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    x, y, z, dx, dy, dz = m.STOCK
    part = mesh(m.finished_part(), lin)
    stock = mesh(BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape(), lin)
    zero = np.array([x + dx / 2, y + dy / 2, z + dz])
    return part - zero, stock - zero
