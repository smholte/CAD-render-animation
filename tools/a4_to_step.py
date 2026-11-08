"""FreeCAD Assembly4 file -> one STEP assembly, without FreeCAD (task 0047: the Thor arm for the landing page).

    ~/venv/bin/python tools/a4_to_step.py <folder>/Assembly.FCStd <out.step> [name]

Assembly4 keeps every part in its own file and places it with App::Link objects (also links to sub-assembly files).
This follows the links from the "Model" part of the given file through all files in the same folder, multiplies the
stored placements, and writes each stored body once with all its placed copies. Hidden links are left out.
"""

import os, re, sys, tempfile, zipfile
from OCP.BRep import BRep_Builder
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Trsf, gp_Quaternion, gp_Vec
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDataStd import TDataStd_Name
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone

FOLDER = os.path.dirname(os.path.abspath(sys.argv[1])) if len(sys.argv) > 1 else "."
_docs = {}

def find(name):
    for f in os.listdir(FOLDER):
        if f.lower() == name.lower():
            return os.path.join(FOLDER, f)
    raise FileNotFoundError(name)

def doc(path):
    if path not in _docs:
        z = zipfile.ZipFile(path)
        d = z.read("Document.xml").decode()
        types = dict((n, t) for t, n in re.findall(r'<Object type="([^"]+)" name="([^"]+)"', d))
        objs = {}
        i = d.index("<ObjectData")
        for m in re.finditer(r'<Object name="([^"]+)"[^>]*>(.*?)\n        </Object>', d[i:], re.S):
            objs[m.group(1)] = m.group(2)
        _docs[path] = (z, types, objs)
    return _docs[path]

def placement(body, prop="Placement"):
    m = re.search(rf'name="{prop}" type="App::PropertyPlacement".*?<PropertyPlacement ([^/]*)/>', body, re.S)
    t = gp_Trsf()
    if not m:
        return t
    p = {k: float(v) for k, v in re.findall(r'(\w+)="([^"]*)"', m.group(1))}
    t.SetRotation(gp_Quaternion(p["Q0"], p["Q1"], p["Q2"], p["Q3"]))
    t.SetTranslationPart(gp_Vec(p["Px"], p["Py"], p["Pz"]))
    return t

def visible(body):
    m = re.search(r'name="Visibility" type="App::PropertyBool".*?<Bool value="([^"]*)"', body, re.S)
    return not m or m.group(1) == "true"

parts = []   # (name, shape, trsf)

def resolve(path, name, trsf, depth=0):
    z, types, objs = doc(path)
    body = objs[name]
    t = types.get(name)
    if t == "App::Link":
        lo = re.search(r'name="LinkedObject".*?(?:<XLink file="([^"]*)"[^>]*name="([^"]*)"|<Link value="([^"]*)")', body, re.S)
        tgt_path = find(lo.group(1)) if lo.group(1) else path
        tgt = lo.group(2) or lo.group(3)
        resolve(tgt_path, tgt, trsf.Multiplied(placement(body)), depth + 1)
        return
    if t == "App::Part":
        grp = re.search(r'name="Group" type="App::PropertyLinkList".*?<LinkList[^>]*>(.*?)</LinkList>', body, re.S)
        for child in re.findall(r'<Link value="([^"]*)"', grp.group(1) if grp else ""):
            if types.get(child) in ("App::Link", "App::Part") or (types.get(child, "").startswith(("Part", "PartDesign::Body")) and 'type="Part::PropertyPartShape"' in objs.get(child, "")):
                if visible(objs[child]):
                    resolve(path, child, trsf, depth + 1)
        return
    f = re.search(r'name="Shape" type="Part::PropertyPartShape"[^>]*>\s*<Part file="([^"]+)"', body)
    if not f:
        print("no shape:", os.path.basename(path), name, t); return
    tmp = tempfile.mktemp(suffix=".brp"); open(tmp, "wb").write(z.read(f.group(1)))
    s = TopoDS_Shape(); BRepTools.Read_s(s, tmp, BRep_Builder()); os.remove(tmp)
    if s.IsNull():
        return
    s = s.Located(TopLoc_Location())   # the link's placement replaces the object's own
    stem = os.path.splitext(os.path.basename(path))[0]
    parts.append((stem if name in ("Body", "Body001", "Model") else name, s, trsf))

if len(sys.argv) < 3:
    sys.exit(__doc__)
src, out = sys.argv[1], sys.argv[2]
_, types, objs = doc(src)
resolve(src, "Model", gp_Trsf())
xdoc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
st = XCAFDoc_DocumentTool.ShapeTool_s(xdoc.Main())
asm = st.NewShape(); TDataStd_Name.Set_s(asm, TCollection_ExtendedString(sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(os.path.basename(src))[0]))
labels = {}
for name, s, t in parts:
    key = (name,)
    if key not in labels:
        labels[key] = st.AddShape(s, False); TDataStd_Name.Set_s(labels[key], TCollection_ExtendedString(name))
    st.AddComponent(asm, labels[key], TopLoc_Location(t))
st.UpdateAssemblies()
w = STEPCAFControl_Writer(); w.SetNameMode(True); w.Transfer(xdoc, STEPControl_AsIs)
assert w.Write(out) == IFSelect_RetDone
print(len(parts), "parts,", len(labels), "unique ->", out)
