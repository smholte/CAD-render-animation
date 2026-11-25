"""Write the invented test weldment as a STEP assembly (task 0319, welds; generic, invented).

    python tools/make_test_weldment.py out.step               TEST.WELDMENT (tests/data/test_weldment.step, copy in
                                                              fresing_render/data/)
    python tools/make_test_weldment.py out.step B             revision B (tests/data/test_weldment_b.step): the fin
                                                              20 mm taller, no branch – for the model update
    python tools/make_test_weldment.py --heavy N out.step     a big invented frame for timing: N cells, ~3 x N weld pairs
    python tools/make_test_weldment.py --cad KIND out.step [B]
                                                              task 0323: the CAD-weld frame with solid weld beads in
                                                              the file, as KIND exports it (inventor / creo / unnamed;
                                                              tests/data/test_weldment_cad_<kind>.step, the inventor
                                                              one also in fresing_render/data/); B: revision B
    python tools/make_test_weldment.py --heavy N --beads out.step
                                                              the heavy frame with its 3 x N welds as beads in one
                                                              "Welds" part (Inventor-like): import timing of 0323

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

**The CAD-weld frame** (task 0323, ``cad(kind, revision)``): the welds are solid beads in the file, as a CAD program
exports solid welds. Parts (steel grey, the two plates painted blue; named apart from the 0319 weldment's, so both can be in
one project – the test tour's welds set):

  BOTTOM PLATE      box x 0..400, y 0..300, z 0..12, hole Ø60.3 at (300, 200); its +x edge bevelled for a single-V
                    groove: 30° from z = 2 (a 2 mm root face) to the top at x = 394.23
  END PLATE         box x 400..550, the same bevel mirrored (60° included, root faces touching at x = 400)
  RIB               box x 50..250, y 145..155, z 12..112
  TUBE              tube Ø60.3 x 5 through the hole, z -20..150
  BOX POST          box x 100..160, y 220..280, z 12..112
  STIFFENER         box x 300..380, y 40..48, z 12..92
  look-alikes that are NOT welds: WALL (x 40..360, y 10..18, z 12..60), KEY BAR 10 x 10 lying in the corner of the
  plate and the wall (x 60..200, y 18..28, z 12..22: a square section, faces on both), ROUND BAR Ø10 in that corner
  (x 220..340: touches both along a line only), FOOT (x 20..80, y 220..280, z -40..-3) under the plate with a PAD 3 mm
  thick between them (a gasket: faces on both sides, no corner)

  The welds (``CAD_WELDS``: what a finder must give):
  1 BOTTOM PLATE / RIB        fillet a5 (legs 7.07) on the rib's -y side, x 50..250: 200 long
  2 BOTTOM PLATE / RIB        intermittent fillet a4 on the +y side: 4 pieces 30 long, pitch 50 (x 60..240)
  3 BOTTOM PLATE / TUBE       fillet a4 all round the tube on the top: 189.4 long (r 30.15)
  4 BOTTOM PLATE / BOX POST   fillet a4 all round the box post (one bead round its four corners): 240 long
  5 BOTTOM PLATE / STIFFENER  fillet with unequal legs, 10 on the plate and 6 on the stiffener (a4, rounded down from
                              4.24) on the stiffener's -y side, 80 long
  6 BOTTOM PLATE / END PLATE  single-V groove (butt) weld with a cap 15.5 wide and 1.5 high, y 0..300: 300 long

  ``kind``: "inventor" – every bead in ONE part "Welds" (one body of several solids), CAD material "Welded Steel Mild",
  the parts "Steel, Mild", the two blue plates' appearance "Paint - Enamel Glossy (Blue)" (Autodesk: an Inventor weldment's solid welds are an assembly feature and come out of a
  STEP export as one part / one body; the beads' material is the weldment's bead material); "creo" – one part per
  weld "WELD_1" … "WELD_6" (Creo 8+ exports each solid weld as a body of its own; the intermittent weld's four pieces
  are the solids of one part), no materials; "unnamed" – one part per bead with names that say nothing ("BODY 1" …),
  found only by their shape. Revision B (inventor): weld 1 150 long (x 50..200), weld 4 gone (the box post is
  bolted now), a new fillet a3 on the stiffener's +y side (80 long).

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


# ---------------------------------------------------------------------------------------------------------
# task 0323: the CAD-weld frame (solid weld beads in the file)
# ---------------------------------------------------------------------------------------------------------

ROOT2 = math.sqrt(2.0)
BEVEL = 10.0 * math.tan(math.radians(30.0))          # 5.7735: how far the 30° bevel reaches over the 10 mm above
#                                                      the root face
CAD_WELDS = (    # (number, part a, part b, kind, a or cap width (mm), length (mm), closed, intermittent (n, l, e))
    (1, "BOTTOM PLATE", "RIB", "FILLET", 5.0, 200.0, False, None),
    (2, "BOTTOM PLATE", "RIB", "FILLET", 4.0, 180.0, False, (4, 30.0, 50.0)),
    (3, "BOTTOM PLATE", "TUBE", "FILLET", 4.0, 2 * math.pi * 30.15, True, None),
    (4, "BOTTOM PLATE", "BOX POST", "FILLET", 4.0, 240.0, True, None),
    (5, "BOTTOM PLATE", "STIFFENER", "FILLET", 4.0, 80.0, False, None),
    (6, "BOTTOM PLATE", "END PLATE", "BUTT", 15.5, 300.0, False, None),
)
CAD_WELDS_B = (
    (1, "BOTTOM PLATE", "RIB", "FILLET", 5.0, 150.0, False, None),
    (2, "BOTTOM PLATE", "RIB", "FILLET", 4.0, 180.0, False, (4, 30.0, 50.0)),
    (3, "BOTTOM PLATE", "TUBE", "FILLET", 4.0, 2 * math.pi * 30.15, True, None),
    (5, "BOTTOM PLATE", "STIFFENER", "FILLET", 4.0, 80.0, False, None),
    (6, "BOTTOM PLATE", "END PLATE", "BUTT", 15.5, 300.0, False, None),
    (7, "BOTTOM PLATE", "STIFFENER", "FILLET", 3.0, 80.0, False, None),
)
LOOK_ALIKES = ("WALL", "KEY BAR", "ROUND BAR", "FOOT", "PAD")


def _fillet_x(y0: float, z0: float, legs: tuple, x0: float, x1: float, side: int):
    """A straight fillet bead along x in the corner of a face y = y0 (its air on the ``side`` of it) and the top
    z = z0: legs (on the top, on the face)."""
    ly, lz = legs
    pts = [(y0, z0), (y0 + side * ly, z0), (y0, z0 + lz)]
    if side < 0:
        pts = pts[::-1]
    return g.polygon_prism(pts, x1 - x0, g.Frame((x0, 0, 0), (0, 1, 0), (1, 0, 0)))


def _ring(cx: float, cy: float, r: float, z0: float, leg: float):
    return g.revolve([(r, z0), (r + leg, z0), (r, z0 + leg)], (cx, cy, 0.0))


def _square_ring(x0, y0, x1, y1, z0, leg):
    """A fillet bead all round a square post standing on z = z0: one solid round the four corners."""
    lo = [(x0 - leg, y0 - leg, z0), (x1 + leg, y0 - leg, z0), (x1 + leg, y1 + leg, z0), (x0 - leg, y1 + leg, z0)]
    hi = [(x0, y0, z0 + leg), (x1, y0, z0 + leg), (x1, y1, z0 + leg), (x0, y1, z0 + leg)]
    return g.cut(g.loft([lo, hi]), g.box(x0, y0, z0 - 1, x1 - x0, y1 - y0, leg + 2))


def _groove(y0: float, y1: float):
    """The single-V groove weld between the two plates at x = 400 with its cap (1.5 high, 2 over each plate)."""
    pts = [(400.0, 2.0), (400 + BEVEL, 12.0), (400 + BEVEL + 2, 12.0), (404.0, 13.2), (400.0, 13.5), (396.0, 13.2),
           (400 - BEVEL - 2, 12.0), (400 - BEVEL, 12.0)]
    # (x, z) profile along y: local x -> model x, local z -> model y, local y -> -z: give it in (x, -z)
    return g.polygon_prism([(x, -z) for x, z in pts][::-1], y1 - y0, g.Frame((0, y0, 0), (1, 0, 0), (0, 1, 0)))


def cad_beads(revision: str = "A") -> list:
    """[(weld number, [solids])] of the CAD-weld frame."""
    a5, a4, a3 = 5 * ROOT2, 4 * ROOT2, 3 * ROOT2
    out = []
    out.append((1, [_fillet_x(145.0, 12.0, (a5, a5), 50.0, 200.0 if revision == "B" else 250.0, -1)]))
    out.append((2, [_fillet_x(155.0, 12.0, (a4, a4), x, x + 30.0, +1) for x in (60.0, 110.0, 160.0, 210.0)]))
    out.append((3, [_ring(300.0, 200.0, 30.15, 12.0, a4)]))
    if revision != "B":
        out.append((4, [_square_ring(100.0, 220.0, 160.0, 280.0, 12.0, a4)]))
    out.append((5, [_fillet_x(40.0, 12.0, (10.0, 6.0), 300.0, 380.0, -1)]))
    out.append((6, [_groove(0.0, 300.0)]))
    if revision == "B":
        out.append((7, [_fillet_x(48.0, 12.0, (a3, a3), 300.0, 380.0, +1)]))
    return out


def cad(kind: str = "inventor", revision: str = "A") -> tuple:
    """(assembly, {part name: CAD material}) of the CAD-weld frame as ``kind`` exports it."""
    if kind not in ("inventor", "creo", "unnamed"):
        raise ValueError(kind)
    wedge_a = g.polygon_prism([(400 - BEVEL, -12.0), (400.0, -12.0), (400.0, -2.0)][::-1], 300.0,
                              g.Frame((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    wedge_b = g.polygon_prism([(400.0, -2.0), (400.0, -12.0), (400 + BEVEL, -12.0)][::-1], 300.0,
                              g.Frame((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    base = g.cut(g.box(0, 0, 0, 400, 300, 12), g.cyl(30.15, 14, (300, 200, -1)), wedge_a)
    ext = g.cut(g.box(400, 0, 0, 150, 300, 12), wedge_b)
    parts = [("BOTTOM PLATE", base, BLUE), ("END PLATE", ext, BLUE),
             ("RIB", g.box(50, 145, 12, 200, 10, 100), STEEL),
             ("TUBE", g.tube(30.15, 25.15, 170, (300, 200, -20)), STEEL),
             ("BOX POST", g.box(100, 220, 12, 60, 60, 100), STEEL),
             ("STIFFENER", g.box(300, 40, 12, 80, 8, 80), STEEL),
             ("WALL", g.box(40, 10, 12, 320, 8, 48), STEEL),
             ("KEY BAR", g.box(60, 18, 12, 140, 10, 10), STEEL),
             ("ROUND BAR", g.cyl(5.0, 120.0, (220, 23, 17), (1, 0, 0)), STEEL),
             ("FOOT", g.box(20, 220, -40, 60, 60, 37), STEEL),
             ("PAD", g.box(20, 220, -3, 60, 60, 3), (0.1, 0.1, 0.1))]
    root = Asm("TEST.WELDMENT.CAD")
    mats = {}
    for name, shape, col in parts:
        root.add(Part(name, shape, col))
        if kind == "inventor":
            mats[name] = "Rubber" if name == "PAD" else "Steel, Mild"
    beads = cad_beads(revision)
    if kind == "inventor":
        root.add(Part("Welds", g.compound(*[s for _n, ss in beads for s in ss]), STEEL))
        mats["Welds"] = "Welded Steel Mild"
    else:
        k = 0
        for n, ss in beads:
            if kind == "creo":
                root.add(Part(f"WELD_{n}", ss[0] if len(ss) == 1 else g.compound(*ss), STEEL))
            else:
                for s in ss:
                    k += 1
                    root.add(Part(f"BODY {k}", s, STEEL))
    return root, mats


def write_cad_step(root: Asm, path: str, materials: dict) -> None:
    """``geom.write_step`` for the CAD-weld frame: a part may be several solids (the welds body of an Inventor
    export) and parts carry CAD material names (as Inventor writes them)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_StepModelType
    from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool
    g._quiet()
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    mt = XCAFDoc_DocumentTool.MaterialTool_s(doc.Main())
    H = TCollection_HAsciiString
    top = st.NewShape()
    TDataStd_Name.Set_s(top, TCollection_ExtendedString(root.name))
    for c in root.children:
        p = c.node
        lab = st.AddShape(p.shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(p.name))
        if p.color:
            ct.SetColor(lab, Quantity_Color(*p.color, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        if materials.get(p.name):
            mt.SetMaterial(lab, H(materials[p.name]), H(""), 7850.0, H("density"), H("POSITIVE_RATIO_MEASURE"))
        st.AddComponent(top, lab, TopLoc_Location(g.trsf(c.M)))
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.SetMaterialMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"writing {path} failed")
    if materials:
        # the painted plates' colour gets its appearance name, as Inventor writes it (else "Steel, Mild" decides)
        import re
        with open(path, encoding="latin-1") as fh:
            text = fh.read()

        def named(m):
            rgb = tuple(round(float(v), 3) for v in re.split(r"\s*,\s*", m.group(1).strip()))
            name = "Paint - Enamel Glossy (Blue)" if rgb == tuple(round(c, 3) for c in BLUE) else ""
            return f"COLOUR_RGB('{name}',{m.group(1)})"
        text = re.sub(r"COLOUR_RGB\(''\s*,\s*([^)]*)\)", named, text, flags=re.S)
        with open(path, "w", encoding="latin-1", newline="") as fh:
            fh.write(text)


def heavy_beads(n: int) -> tuple:
    """The heavy frame (``heavy``) with its welds as beads in one "Welds" part: per cell two fillets a3 along the
    fin (150 long) and a ring a3 round the post on the plate's top – 3 x n beads."""
    root = heavy(n)
    leg = 3 * ROOT2
    cols = max(1, math.ceil(math.sqrt(n)))
    solids = []
    for k in range(n):
        m = T((k % cols) * 250.0, (k // cols) * 250.0, 0.0)
        for s in (_fillet_x(96.0, 10.0, (leg, leg), 25.0, 175.0, -1), _fillet_x(104.0, 10.0, (leg, leg), 25.0, 175.0, +1),
                  _ring(100.0, 160.0, 21.2, 10.0, leg)):
            solids.append(g.xform(s, m))
    root.add(Part("Welds", g.compound(*solids), STEEL))
    return root, {"Welds": "Welded Steel Mild"}


def main(argv) -> int:
    args = argv[1:]
    n = None
    kind = None
    beads = False
    if args and args[0] == "--heavy":
        n, args = int(args[1]), args[2:]
        if args and args[0] == "--beads":
            beads, args = True, args[1:]
    if args and args[0] == "--cad":
        kind, args = args[1], args[2:]
    revision = "A"
    if len(args) == 2 and args[1] in ("A", "B"):
        revision, args = args[1], args[:1]
    if len(args) != 1:
        raise SystemExit("usage: make_test_weldment.py [--heavy N [--beads]] [--cad KIND] out.step [A|B]")
    t0 = time.time()
    if kind is not None or beads:
        root, mats = cad(kind, revision) if kind is not None else heavy_beads(n)
        write_cad_step(root, args[0], mats)
        print(f"written: {len(root.children)} parts, {os.path.getsize(args[0]) / 1024:.0f} KB, "
              f"{time.time() - t0:.1f} s")
        return 0
    root = small(revision) if n is None else heavy(n)
    g.write_step(root, args[0])
    print(f"written: {g.count_parts(root)} parts, {os.path.getsize(args[0]) / 1024:.0f} KB, {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
