"""Invented test models for the import timing study (task 0301). No Blender; run with the venv's Python.

    python tools/import_timing/make_models.py <out folder> [heavy] [big] [nurbs]

heavy  = the PC check's Heavy machine at full size (600 unique / 3,000 placed parts, pccheck/heavy_scene.py)
big    = the same maker at 4 x (2,400 unique / 12,000 placed): about the EGR line's file size
nurbs  = Heavy with every unique part turned into B-spline faces (BRepBuilderAPI_NurbsConvert): the kind of
         surfaces a CAD export carries for fillets and free forms, much heavier to read than planes and cylinders
Nothing of a real design: the parts are boxes with holes, tubes, tori, cones and spheres with supplier-style names.
"""

from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "fresing_render", "pccheck"))

import heavy_scene  # noqa: E402


def to_nurbs(src: str, dst: str) -> dict:
    """Read ``src``, turn every unique part's shape into B-splines, write ``dst`` (names, colours, tree kept)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_StepModelType
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.SetNameMode(True)
    if r.ReadFile(src) != IFSelect_RetDone or not r.Transfer(doc):
        raise RuntimeError("read failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = TDF_LabelSequence()
    st.GetShapes(labels)
    n = 0
    for i in range(1, labels.Length() + 1):
        lab = labels.Value(i)
        if XCAFDoc_ShapeTool.IsAssembly_s(lab) or not XCAFDoc_ShapeTool.IsSimpleShape_s(lab):
            continue
        shape = XCAFDoc_ShapeTool.GetShape_s(lab)
        st.SetShape(lab, BRepBuilderAPI_NurbsConvert(shape, True).Shape())
        n += 1
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetColorMode(True)
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if w.Write(dst) != IFSelect_RetDone:
        raise RuntimeError("write failed")
    return {"converted": n}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = argv[0]
    which = argv[1:] or ["heavy", "big", "nurbs"]
    os.makedirs(out, exist_ok=True)
    heavy = os.path.join(out, "heavy.step")
    for name in which:
        t = time.time()
        path = os.path.join(out, name + ".step")
        if name == "heavy":
            info = heavy_scene.build(path, 600, 3000)
        elif name == "big":
            info = heavy_scene.build(path, 2400, 12000, seed=11)
        elif name == "nurbs":
            if not os.path.exists(heavy):
                heavy_scene.build(heavy, 600, 3000)
            info = to_nurbs(heavy, path)
        else:
            raise SystemExit(f"unknown model {name}")
        print(name, info, f"{os.path.getsize(path) / 1e6:.1f} MB", f"{time.time() - t:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
