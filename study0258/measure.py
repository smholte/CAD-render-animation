"""Task 0258 (throw-away): every placed part of a STEP file with its world bounding box (mm).

python measure.py <file.step> [...]  -> prints JSON per file: overall box and each leaf part's name + box.
"""
import json
import sys

from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.TopLoc import TopLoc_Location
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib


def name_of(label):
    a = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), a):
        return a.Get().ToExtString()
    return ""


def box(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    if b.IsVoid():
        return None
    m, M = b.CornerMin(), b.CornerMax()
    return [m.X(), m.Y(), m.Z(), M.X(), M.Y(), M.Z()]


def read(path):
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    r.ReadFile(path)
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    parts = []

    def walk(label, loc, path_names):
        if XCAFDoc_ShapeTool.IsAssembly_s(label):
            comps = TDF_LabelSequence()
            XCAFDoc_ShapeTool.GetComponents_s(label, comps, False)
            for i in range(1, comps.Length() + 1):
                c = comps.Value(i)
                ref = TDF_Label()
                XCAFDoc_ShapeTool.GetReferredShape_s(c, ref)
                cloc = XCAFDoc_ShapeTool.GetLocation_s(c)
                walk(ref, loc.Multiplied(cloc), path_names + [name_of(ref) or name_of(c)])
        else:
            shp = XCAFDoc_ShapeTool.GetShape_s(label).Moved(loc)
            bb = box(shp)
            if bb:
                parts.append({"name": path_names[-1] if path_names else name_of(label),
                              "path": "/".join(path_names), "box": bb})

    free = TDF_LabelSequence()
    st.GetFreeShapes(free)
    for i in range(1, free.Length() + 1):
        lab = free.Value(i)
        walk(lab, TopLoc_Location(), [name_of(lab)])
    xs = [p["box"] for p in parts]
    tot = [min(b[0] for b in xs), min(b[1] for b in xs), min(b[2] for b in xs),
           max(b[3] for b in xs), max(b[4] for b in xs), max(b[5] for b in xs)]
    return {"file": path, "box": tot, "parts": parts}


if __name__ == "__main__":
    out = [read(p) for p in sys.argv[1:]]
    json.dump(out, sys.stdout, indent=0)
