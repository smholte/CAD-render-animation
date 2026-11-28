"""Writes the invented welded frame the PC check "Heavy" times the weld finding with (task 0379).

Runs as its own small program (Blender's Python with the bundled OpenCascade), like ``heavy_scene.py``:
``python heavy_welds.py out.step [cells] [--revision B]``. No Blender, no relative imports; the shape library is
``demo_model/geom.py`` (loaded by its path, as ``stress_scene.py`` does). Nothing of it is a real design.

The frame is ``tools/make_test_weldment.py --heavy N --beads`` (task 0368's 300-weld frame): N cells in a grid, 250 mm
apart, each a base plate 200 x 200 x 10 with a hole Ø42.4, a fin 150 x 8 x 80 on it and a post tube Ø42.4 through the
hole. The welds are solid beads in ONE part "Welds" (as Inventor exports them): per cell two fillets a3 along the fin
and a ring a3 round the post – 3 x N welds. Revision B (the model update): every 10th cell's fin is 10 mm taller (its
own shape; the welds stay where they are, so the finder must find the same welds again on the new file).
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GEOM = os.path.join(os.path.dirname(HERE), "demo_model", "geom.py")
STEEL = (0.42, 0.43, 0.45)
BLUE = (0.10, 0.25, 0.55)
LEG = 3 * math.sqrt(2.0)                    # a fillet a3: legs of 3 sqrt(2) cut by a 45° face
CHANGED_EVERY = 10                          # revision B: every 10th cell's fin


def _geom():
    name = "fresing_heavy_welds_geom"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, GEOM)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fillet_x(g, y0, z0, legs, x0, x1, side):
    """A straight fillet bead along x in the corner of a face y = y0 (its air on the ``side`` of it) and the top z = z0."""
    ly, lz = legs
    pts = [(y0, z0), (y0 + side * ly, z0), (y0, z0 + lz)]
    if side < 0:
        pts = pts[::-1]
    return g.polygon_prism(pts, x1 - x0, g.Frame((x0, 0, 0), (0, 1, 0), (1, 0, 0)))


def _ring(g, cx, cy, r, z0, leg):
    return g.revolve([(r, z0), (r + leg, z0), (r, z0 + leg)], (cx, cy, 0.0))


def frame(cells: int, revision: str = "A"):
    """(assembly, {part name: CAD material}, welds): the frame with its welds as beads in one "Welds" part."""
    g = _geom()
    Asm, Part, T = g.Asm, g.Part, g.T
    plate = Part("CELL PLATE", g.cut(g.box(0, 0, 0, 200, 200, 10), g.cyl(21.2, 12, (100, 160, -1))), BLUE)
    fin = Part("CELL FIN", g.box(25, 96, 10, 150, 8, 80), STEEL)
    fin_b = Part("CELL FIN TALL", g.box(25, 96, 10, 150, 8, 90), STEEL)
    post = Part("CELL POST", g.tube(21.2, 18.0, 80, (100, 160, -10)), STEEL)
    root = Asm("HEAVY.WELDED.FRAME")
    cols = max(1, math.ceil(math.sqrt(cells)))
    solids, changed = [], 0
    for k in range(cells):
        m = T((k % cols) * 250.0, (k // cols) * 250.0, 0.0)
        tall = revision == "B" and k % CHANGED_EVERY == 0
        changed += 1 if tall else 0
        root.add(plate, m, f"CELL {k} PLATE")
        root.add(fin_b if tall else fin, m, f"CELL {k} FIN")
        root.add(post, m, f"CELL {k} POST")
        for s in (_fillet_x(g, 96.0, 10.0, (LEG, LEG), 25.0, 175.0, -1),
                  _fillet_x(g, 104.0, 10.0, (LEG, LEG), 25.0, 175.0, +1),
                  _ring(g, 100.0, 160.0, 21.2, 10.0, LEG)):
            solids.append(g.xform(s, m))
    root.add(Part("Welds", g.compound(*solids), STEEL))
    return root, {"Welds": "Welded Steel Mild"}, {"welds": 3 * cells, "changed_placed": changed}


def write_step(root, path: str, materials: dict) -> None:
    """The STEP file with each part's CAD material name, as Inventor writes it (the painted plates' colour gets its
    appearance name, else "Steel, Mild" decides)."""
    g = _geom()
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
    labels = {}                                        # one label per shape: a part placed 100 times stays one mesh
    for c in root.children:
        p = c.node
        lab = labels.get(id(p))
        if lab is None:
            lab = labels[id(p)] = st.AddShape(p.shape, False)
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString(p.name))
            if p.color:
                ct.SetColor(lab, Quantity_Color(*p.color, Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
            if materials.get(p.name):
                mt.SetMaterial(lab, H(materials[p.name]), H(""), 7850.0, H("density"), H("POSITIVE_RATIO_MEASURE"))
        comp = st.AddComponent(top, lab, TopLoc_Location(g.trsf(c.M)))
        if c.instance:
            TDataStd_Name.Set_s(comp, TCollection_ExtendedString(c.instance))
    st.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.SetMaterialMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"writing {path} failed")
    with open(path, encoding="latin-1") as fh:
        text = fh.read()

    def named(m):
        rgb = tuple(round(float(v), 3) for v in re.split(r"\s*,\s*", m.group(1).strip()))
        name = "Paint - Enamel Glossy (Blue)" if rgb == tuple(round(c, 3) for c in BLUE) else ""
        return f"COLOUR_RGB('{name}',{m.group(1)})"
    text = re.sub(r"COLOUR_RGB\(''\s*,\s*([^)]*)\)", named, text, flags=re.S)
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(text)


def build(path: str, cells: int = 100, revision: str = "A") -> dict:
    t0 = time.time()
    root, mats, info = frame(cells, revision)
    write_step(root, path, mats)
    info.update(cells=cells, parts=len(root.children), kb=round(os.path.getsize(path) / 1024), seconds=time.time() - t0)
    return info


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    rev = "A"
    if "--revision" in args:
        i = args.index("--revision")
        rev = args[i + 1]
        del args[i:i + 2]
    out = args[0] if args else "heavy_welds.step"
    n = int(args[1]) if len(args) > 1 else 100
    print(json.dumps(build(out, n, rev)))
