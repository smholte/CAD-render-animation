"""Write the test model for a vessel at work as a STEP assembly (task 0154; generic, invented).

    python tools/make_test_thrusters.py out.step   TEST.THRUSTERS (tests/data/test_thrusters.step, a copy in
                                                   fresing_render/data/)

A small workboat: a hull with a flat bottom, round bilges and a fine bow (``tools/workboat_hull.py``, task 0234), a
deckhouse with a window band, two azimuth thrusters under the stern, one tunnel thruster through the
bow. mm, Z up, x towards the bow (transom at x = 0), y to port, the waterline at z = 0 (the app's Sea water level is
set by ``blender/vessel_work.set_up_test_model``). Every part is one solid. The places the app's set-up needs are in
``fresing_render/core/vessel_work.TEST`` (this file reads them from there).

  HULL               transom at x 0, the parallel body to x 33500 (y ±6000 at the deck, 150 narrower at the bilges,
                     bilge radius 800, flat bottom at z -2500), the bow narrowing to the stem at x 40000, its forefoot
                     rising to the waterline there; deck z 2500, the bow's (forecastle) z 3700; a tunnel Ø1400 across at the bow thruster (x 32000, z -1300)
  WHEELHOUSE         x 21000 … 27000, y ±3500, z 2500 … 5500, a roof 100 wider all round, a window band cut in
                     (front and sides)
  AZIMUTH PS / SB    steer axes at x 3500, y ±3000 under the hull's bottom (z -2500):
    THRUSTER HOUSING   Ø1800 x 200 under the hull (stays)
    STEERING UNIT      (turns with Steer) THRUSTER POD: strut 1000 x 400 down to the pod Ø800 along x (x -1200 …
                       +1000 from the axis) at z -4100; THRUSTER NOZZLE: ring Ø2100 / Ø1900, x -1900 … -1100, on
                       three stator plates; PROPELLER: hub Ø500 at x -1500, four twisted blades to r 900
  BOW THRUSTER       axis along y at x 32000, z -1300: TUNNEL LINING (r 700 … 660 through the hull's width there),
                     PROPELLER (hub Ø400, four blades to r 600, turning about y)
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from make_test_paths import Asm, Part, T, box, cut, cyl, fuse, solids, write_step  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform  # noqa
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism  # noqa: E402
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec  # noqa: E402

from fresing_render.core.vessel_work import TEST  # noqa: E402
from workboat_hull import Hull, deckhouse  # noqa: E402

HULL_BLUE = (0.09, 0.17, 0.32)
RED = (0.55, 0.12, 0.10)
WHITE = (0.93, 0.93, 0.91)
BRONZE = (0.80, 0.55, 0.35)


def prism_xy(points, z0, z1):
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in points:
        poly.Add(gp_Pnt(float(x), float(y), float(z0)))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, float(z1 - z0))).Shape()


def turned(shape, axis_p, axis_d, deg):
    tr = gp_Trsf()
    tr.SetRotation(gp_Ax1(gp_Pnt(*[float(v) for v in axis_p]), gp_Dir(*[float(v) for v in axis_d])),
                   math.radians(deg))
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def propeller(R, hub_r, hub_len, along):
    """A four-bladed propeller about local x (``along`` = "x") or y, its middle at the origin; blades pitched 30°."""
    hub = cyl(hub_r, (-hub_len / 2, 0, 0), (hub_len / 2, 0, 0))
    blades = []
    for k in range(4):
        b = box(-0.12 * R, -0.05 * R, hub_r * 0.8, 0.12 * R, 0.05 * R, R)
        b = turned(b, (0, 0, 0), (0, 0, 1), 30.0)          # pitched about the blade's own radial line
        blades.append(turned(b, (0, 0, 0), (1, 0, 0), 90.0 * k))
    p = fuse(hub, *blades)
    if along == "y":
        p = turned(p, (0, 0, 0), (0, 0, 1), 90.0)
    return p


FORECASTLE = 1200.0                           # the bow's deck this much higher than the main deck
BOW_START, STEM_X = 33500.0, 40000.0          # task 0234: the bow starts past the bow tunnel (a tunnel cut through the
                                              # curved bow made the file 280 KB bigger), the stem 4 m further forward
STEM_RISE = 0.38                              # the forefoot meets the water at the stem: a fine waterline forward (the
                                              # app reads the bow from it: blender/surroundings.stern_side)


def hull_numbers() -> Hull:
    return Hull(STEM_X, TEST["half_beam"], TEST["bottom"], TEST["deck"], BOW_START, bow_top=TEST["deck"] + FORECASTLE,
                stem_rise=STEM_RISE)


def hull():
    bx, bz, br = TEST["bow_x"], TEST["bow_z"], TEST["tunnel_r"]
    return cut(hull_numbers().solid(), cyl(br, (bx, -2 * TEST["half_beam"], bz), (bx, 2 * TEST["half_beam"], bz)))


def tunnel_half() -> float:
    """Half the bow tunnel's length: to the hull's side where it is narrowest round the tunnel, 120 inside it."""
    h, bx, bz, br = hull_numbers(), TEST["bow_x"], TEST["bow_z"], TEST["tunnel_r"]
    return min(h.half_at(bx + dx, bz + dz) for dx in (-br, 0.0, br) for dz in (-br, 0.0, br)) - 120.0


def azimuth(name):
    a = Asm(name)
    z = TEST["az_drop"]
    a.add(Part("THRUSTER HOUSING", cyl(900.0, (0, 0, -200.0), (0, 0, 0)), RED))
    steer = Asm("STEERING UNIT")
    strut = box(-500.0, -200.0, z, 500.0, 200.0, -200.0)
    pod = fuse(cyl(400.0, (-1200.0, 0, z), (1000.0, 0, z)), strut)
    steer.add(Part("THRUSTER POD", pod, RED))
    ring = cut(cyl(1050.0, (-1900.0, 0, z), (-1100.0, 0, z)), cyl(950.0, (-2000.0, 0, z), (-1000.0, 0, z)))
    stators = [turned(box(-1500.0, -30.0, z + 380.0, -1350.0, 30.0, z + 980.0), (0, 0, z), (1, 0, 0), 120.0 * k)
               for k in range(3)]
    steer.add(Part("THRUSTER NOZZLE", fuse(ring, *stators), RED))
    steer.add(Part("PROPELLER", propeller(900.0, 250.0, 400.0, "x"), BRONZE), T(TEST["az_prop_x"], 0.0, z))
    a.add(steer)
    return a


def bow_thruster(half):
    a = Asm("BOW THRUSTER")
    r = TEST["tunnel_r"]
    lining = cut(cyl(r, (0, -half, 0), (0, half, 0)), cyl(r - 40.0, (0, -half - 1, 0), (0, half + 1, 0)))
    a.add(Part("TUNNEL LINING", lining, RED))
    a.add(Part("PROPELLER", propeller(600.0, 200.0, 300.0, "y"), BRONZE))
    return a


def model():
    root = Asm("TEST.THRUSTERS")
    root.add(Part("HULL", hull(), HULL_BLUE))
    root.add(Part("WHEELHOUSE", deckhouse(21000.0, 27000.0, 3500.0, TEST["deck"], 3000.0), WHITE))
    for name, y in (("AZIMUTH PS", TEST["az_y"]), ("AZIMUTH SB", -TEST["az_y"])):
        root.add(azimuth(name), T(TEST["az_x"], y, TEST["bottom"]))
    root.add(bow_thruster(tunnel_half()), T(TEST["bow_x"], 0.0, TEST["bow_z"]))
    return root


def check(root):
    def walk(node):
        for child, _m in node.children:
            if isinstance(child, Part):
                assert solids(child.shape) == 1, child.name
            else:
                walk(child)
    walk(root)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    root = model()
    check(root)
    write_step(root, argv[1])
    print(f"written {os.path.getsize(argv[1]) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
