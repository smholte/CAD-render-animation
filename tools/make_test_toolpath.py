"""Write the test mill (task 0249: a vertical machining centre) with a stock block and a finished part as a STEP assembly (task 0029: the app makes the
toolpath). Nothing of a real machine or part: all sizes in mm, Z up.

TEST.TOOLPATH
  BED, COLUMN, CHIP TRAY …  fixed (the vertical machining centre of the milling test model, tools/make_test_mill.py,
                            task 0249)
  Y.ASM                     moves along Y (a slide joint in the tests): the SADDLE
    X.ASM                   moves along X (the tests' joint points to -x)
      TABLE                 1200 x 500 (top at z = 30)
      STOCK 120x80x40       the raw block: x -60..60, y -40..40, z 30..70
      FINISHED PART         same place as the stock, inside it:
                              base 120 x 80, top at z = 55
                              boss 24 x 24 up to z = 65 at x -52..-28, y -32..-8, its top edges rounded R3
                              pocket 36 x 22, 8 deep (floor z = 47), corners R5, at x 12..48, y -32..-10
                              dome: a sphere R25 round (-22, 18, 40): top at z = 65, Ø40 on the base
                              mushroom (the undercut): post 10 x 10 (z 55..60) under a cap 22 x 16 (z 60..64) at
                              (28, 22): the cap hangs over by 6 / 3 mm - the stock under it cannot be cut from the top
                              through hole Ø10 at (52, 30)
      EDGE CLAMP …          18 mm low beside the stock's back and front faces, their screws 18 mm out
  Z.ASM                     moves along Z
    SPINDLE                 BT40, its nose at z 130
    END MILL D10            flat end mill Ø10 x 40, tip at x = 0, y = 0, z = 90 (20 mm above the stock)

usage: python make_test_toolpath.py out.step
"""

import os
import sys

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STOCK = (-60.0, -40.0, 30.0, 120.0, 80.0, 40.0)        # x, y, z, dx, dy, dz
BASE_TOP = 55.0
BOSS = (-52.0, -32.0, 24.0, 24.0, 65.0, 3.0)            # x, y, dx, dy, top, fillet radius of the top edges
POCKET = (12.0, -32.0, 36.0, 22.0, 8.0, 5.0)            # x, y, dx, dy, depth, corner radius
DOME = (-22.0, 18.0, 40.0, 25.0)                        # centre x, y, z, radius
POST = (23.0, 17.0, 10.0, 10.0, 60.0)                   # x, y, dx, dy, top
CAP = (17.0, 14.0, 22.0, 16.0, 64.0)                    # x, y, dx, dy, top (from the post's top)
HOLE = (52.0, 30.0, 5.0)                                # x, y, radius
FLAT_TIP = (0.0, 0.0, 90.0)


def _edges(shape, test):
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    out = []
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if test(p0, p1):
            out.append(e)
        exp.Next()
    return out


def _round(shape, radius, test):
    fil = BRepFilletAPI_MakeFillet(shape)
    for e in _edges(shape, test):
        fil.Add(radius, e)
    return fil.Shape()


def finished_part():
    x, y, z, dx, dy, _dz = STOCK
    base = BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, BASE_TOP - z).Shape()
    bx, by, bdx, bdy, btop, br = BOSS
    boss = BRepPrimAPI_MakeBox(gp_Pnt(bx, by, BASE_TOP - 1.0), bdx, bdy, btop - BASE_TOP + 1.0).Shape()
    boss = _round(boss, br, lambda p0, p1: abs(p0.Z() - btop) < 1e-6 and abs(p1.Z() - btop) < 1e-6)
    shape = BRepAlgoAPI_Fuse(base, boss).Shape()
    cx, cy, cz, cr = DOME
    sphere = BRepPrimAPI_MakeSphere(gp_Pnt(cx, cy, cz), cr).Shape()
    above = BRepPrimAPI_MakeBox(gp_Pnt(cx - cr, cy - cr, BASE_TOP - 1.0), 2 * cr, 2 * cr, cr).Shape()
    shape = BRepAlgoAPI_Fuse(shape, BRepAlgoAPI_Common(sphere, above).Shape()).Shape()
    px, py, pdx, pdy, ptop = POST
    post = BRepPrimAPI_MakeBox(gp_Pnt(px, py, BASE_TOP - 1.0), pdx, pdy, ptop - BASE_TOP + 1.0).Shape()
    kx, ky, kdx, kdy, ktop = CAP
    cap = BRepPrimAPI_MakeBox(gp_Pnt(kx, ky, ptop), kdx, kdy, ktop - ptop).Shape()
    shape = BRepAlgoAPI_Fuse(shape, BRepAlgoAPI_Fuse(post, cap).Shape()).Shape()
    qx, qy, qdx, qdy, depth, qr = POCKET
    pocket = BRepPrimAPI_MakeBox(gp_Pnt(qx, qy, BASE_TOP - depth), qdx, qdy, depth + 20.0).Shape()
    pocket = _round(pocket, qr, lambda p0, p1: abs(p0.X() - p1.X()) < 1e-6 and abs(p0.Y() - p1.Y()) < 1e-6)
    shape = BRepAlgoAPI_Cut(shape, pocket).Shape()
    hx, hy, hr = HOLE
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(hx, hy, z - 5.0), gp_Dir(0, 0, 1)), hr, 100.0).Shape()
    return BRepAlgoAPI_Cut(shape, hole).Shape()


def model():
    """The machine of the milling test model (make_test_mill.py) round this stock and finished part."""
    from make_test_mill import ALU, g, machine, part
    sx, sy, sz, sdx, sdy, sdz = STOCK
    stock = part("STOCK 120x80x40", g.box(sx, sy, sz, sdx, sdy, sdz), ALU)
    finished = part("FINISHED PART", finished_part(), ALU)
    end_mill = part("END MILL D10", g.cyl(5.0, 40.0))
    return machine("TEST.TOOLPATH", stock, finished, STOCK, [(end_mill, FLAT_TIP)])


def build(path: str) -> None:
    from make_test_mill import write
    write(model(), path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_toolpath.step")
    print("written")
