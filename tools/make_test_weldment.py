"""Write the invented test weldment as a STEP assembly (task 0319, welds; generic, invented).

    python tools/make_test_weldment.py out.step               TEST.WELDMENT (tests/data/test_weldment.step, copy in
                                                              fresing_render/data/)
    python tools/make_test_weldment.py out.step B             revision B (tests/data/test_weldment_b.step): the fin
                                                              20 mm taller, no branch – for the model update
    python tools/make_test_weldment.py --heavy N out.step     a big invented frame for timing: N cells, ~3 x N weld pairs

All sizes in mm, Z up. Every part is one solid, placed by its own coordinates (identity matrices); all parts are
direct children of the root assembly "TEST.WELDMENT". Steel parts grey (0.42, 0.43, 0.45), the two plates painted blue
(0.10, 0.25, 0.55).

  BASE PLATE        box x 0..400, y 0..300, z 0..12, a through hole Ø60.3 (r 30.15) centred at (300, 200)
  FIN               box x 50..250, y 145..155, z 12..112, stands on the base plate (a T-joint)
  GUSSET            triangular plate 8 thick (x 146..154) in the corner between the fin's +y face (y = 155) and the
                    base top (z = 12): legs 60 along +y (y 155..215) and 60 along +z (z 12..72), the right-angle
                    corner cut off by a 10 x 10 snipe: it touches the fin on y = 155 for z 22..72 and the base on
                    z = 12 for y 165..215 (a polygon prism, one solid)
  POST              tube Ø60.3 x 5 (r 30.15 / 25.15), vertical through (300, 200), z -20..150; passes through the base
                    plate's hole, its outer face exactly on the hole's face
  BRANCH            tube Ø48.3 x 4 (r 24.15 / 20.15), vertical through (200, 60), z 12..160 before coping, its top end
                    cut by a solid cylinder r 44.45 along X through (y 60, z 150): it fits the main tube's outer face
  MAIN TUBE         tube Ø88.9 x 5 (r 44.45 / 39.45), axis along X through y = 60, z = 150, x 100..300
  EXTENSION PLATE   box x 400..550, y 0..300, z 0..12, edge to edge with the base plate at x = 400 (a butt joint)

Welds a weld finder should find (pair: seam):
  BASE PLATE / FIN          two fillets, one on each side of the fin, 200 long (y = 145 and y = 155, z = 12)
  BASE PLATE / GUSSET       the gusset's foot on z = 12: a line 50 long (y 165..215) at x 146 .. 154 (8 wide)
  FIN / GUSSET              the gusset's edge on the fin's +y face: 50 long (z 22..72)
  BASE PLATE / POST         two all-round circles Ø60.3 (r 30.15) round the hole: top at z = 12 and bottom at z = 0
  BASE PLATE / BRANCH       the branch's circle Ø48.3 on the base top (outer, z = 12); its bore makes a second, inner
                            circle Ø40.3 at z = 12
  BRANCH / MAIN TUBE        the saddle where the coped end meets the main tube's outer face (outer), plus the bore's
                            inner saddle
  BASE PLATE / EXTENSION    the butt joint at x = 400: top (z = 12) and bottom (z = 0) seams, each 300 long, and the
                            two 12 mm ends (y = 0 and y = 300)
No other pairs touch (``PAIRS``). ``small()`` gives the assembly.

``--heavy N`` / ``heavy(n)``: N cells in a grid of about sqrt(N) x sqrt(N), 250 apart. Each cell: a base plate
200 x 200 x 10 with a hole Ø42.4 at (100, 160), a fin 150 x 8 x 80 on it (x 25..175, y 96..104, z 10..90) and a post tube
Ø42.4 x 3.2 through the hole (z -10..70). Parts "CELL k PLATE", "CELL k FIN", "CELL k POST" (the instance names; one
Part object per shape is shared by every cell, so the file stays small): 3 weld pairs a cell (plate/fin, plate/post
twice counted as one pair).
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fresing_render.demo_model import geom as g  # noqa: E402
from fresing_render.demo_model.geom import Asm, Part, T  # noqa: E402

STEEL = (0.42, 0.43, 0.45)
BLUE = (0.10, 0.25, 0.55)

PAIRS = {
    ("BASE PLATE", "FIN"), ("BASE PLATE", "GUSSET"), ("FIN", "GUSSET"), ("BASE PLATE", "POST"),
    ("BASE PLATE", "BRANCH"), ("BRANCH", "MAIN TUBE"), ("BASE PLATE", "EXTENSION PLATE"),
}


def small(revision: str = "A") -> Asm:
    """Revision "B" (the model-update test, tests/data/test_weldment_b.step): the FIN 20 mm taller (z 12..132: its side
    faces changed) and no BRANCH; everything else as A."""
    base = g.cut(g.box(0, 0, 0, 400, 300, 12), g.cyl(30.15, 14, (300, 200, -1)))
    fin = g.box(50, 145, 12, 200, 10, 120 if revision == "B" else 100)
    gusset = g.polygon_prism([(155, 22), (165, 12), (215, 12), (155, 72)], 8,
                             g.Frame((146, 0, 0), (0, 1, 0), (1, 0, 0)))
    post = g.tube(30.15, 25.15, 170, (300, 200, -20))
    branch = g.cut(g.tube(24.15, 20.15, 148, (200, 60, 12)), g.cyl(44.45, 200, (100, 60, 150), (1, 0, 0)))
    main = g.tube(44.45, 39.45, 200, (100, 60, 150), (1, 0, 0))
    ext = g.box(400, 0, 0, 150, 300, 12)
    root = Asm("TEST.WELDMENT")
    for name, shape, col in (("BASE PLATE", base, BLUE), ("FIN", fin, STEEL), ("GUSSET", gusset, STEEL),
                             ("POST", post, STEEL), ("BRANCH", branch, STEEL), ("MAIN TUBE", main, STEEL),
                             ("EXTENSION PLATE", ext, BLUE)):
        if revision == "B" and name == "BRANCH":
            continue
        root.add(Part(name, shape, col))
    return root


def heavy(n: int) -> Asm:
    plate = Part("CELL PLATE", g.cut(g.box(0, 0, 0, 200, 200, 10), g.cyl(21.2, 12, (100, 160, -1))), BLUE)
    fin = Part("CELL FIN", g.box(25, 96, 10, 150, 8, 80), STEEL)
    post = Part("CELL POST", g.tube(21.2, 18.0, 80, (100, 160, -10)), STEEL)
    root = Asm("TEST.WELDMENT.HEAVY")
    cols = max(1, math.ceil(math.sqrt(n)))
    for k in range(n):
        m = T((k % cols) * 250.0, (k // cols) * 250.0, 0.0)
        root.add(plate, m, f"CELL {k} PLATE")
        root.add(fin, m, f"CELL {k} FIN")
        root.add(post, m, f"CELL {k} POST")
    return root


def main(argv) -> int:
    args = argv[1:]
    n = None
    if args and args[0] == "--heavy":
        n, args = int(args[1]), args[2:]
    revision = "A"
    if len(args) == 2 and args[1] in ("A", "B"):
        revision, args = args[1], args[:1]
    if len(args) != 1:
        raise SystemExit("usage: make_test_weldment.py [--heavy N] out.step [A|B]")
    t0 = time.time()
    root = small(revision) if n is None else heavy(n)
    g.write_step(root, args[0])
    print(f"written: {g.count_parts(root)} parts, {os.path.getsize(args[0]) / 1024:.0f} KB, {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
