"""A block with a chamfer and a filleted hole, for the web page's edge picks (task 0219). No Blender.

TEST.EDGES: a block 100 x 60 x 30 mm from the origin; the top edge along X at Y 0 chamfered 5 x 5 mm; a hole
Ø20 through it at (70, 30), its top rim rounded R3 (so the hole meets the rounding in a circle Ø20 and the rounding
meets the top in a circle Ø26). Known edges: the block's straight edges, the chamfer's two edges (100 mm long, at
Y 5 / Z 30 and Y 0 / Z 25), the hole's bottom rim Ø20 at Z 0, the rounding's two circles.

``shape()`` gives the OpenCascade solid (tests mesh it with the importer's own mesher); ``python make_test_edges.py
out.step`` writes it as a STEP part.
"""

import sys

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

SIZE = (100.0, 60.0, 30.0)
HOLE = (70.0, 30.0, 10.0)          # centre x, y, radius
ROUND = 3.0
CHAMFER = 5.0


def _edges(shape):
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        yield TopoDS.Edge(ex.Current())
        ex.Next()


def shape():
    x, y, z = SIZE
    block = BRepPrimAPI_MakeBox(x, y, z).Shape()
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(HOLE[0], HOLE[1], -1.0), gp_Dir(0, 0, 1)), HOLE[2], z + 2).Shape()
    s = BRepAlgoAPI_Cut(block, cyl).Shape()
    fil = BRepFilletAPI_MakeFillet(s)
    for e in _edges(s):
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Circle and abs(c.Value(c.FirstParameter()).Z() - z) < 1e-6:
            fil.Add(ROUND, e)
    s = fil.Shape()
    ch = BRepFilletAPI_MakeChamfer(s)
    for e in _edges(s):
        c = BRepAdaptor_Curve(e)
        if c.GetType() != GeomAbs_Line:
            continue
        a, b = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(a.Y()) < 1e-6 and abs(b.Y()) < 1e-6 and abs(a.Z() - z) < 1e-6 and abs(b.Z() - z) < 1e-6:
            ch.Add(CHAMFER, e)
    return ch.Shape()


def main(path: str) -> None:
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    w = STEPControl_Writer()
    w.Transfer(shape(), STEPControl_AsIs)
    w.Write(path)


if __name__ == "__main__":
    main(sys.argv[1])
