"""FreeCAD file (.fcstd) -> STEP assembly, without FreeCAD (task 0047: the CEB press for the landing page).

    ~/venv/bin/python tools/fcstd_to_step.py <file.fcstd> <out.step>

A .fcstd is a zip: Document.xml names the objects, and each object's shape is stored as an OpenCascade .brp file.
Every object with a stored shape becomes a sub-assembly named after it; its solids (or shells, when the file has no
solids) become its parts "<OBJECT> PART n", placed where they were. Old Assembly2 files work this way too.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import zipfile

# the Shape of the same object: never search on past its </Object> (that took a constraint's name for the next shape)
SHAPE_RE = re.compile(r'<Object name="([^"]+)"[^>]*>(?:(?!</Object>).)*?<Property name="Shape" '
                      r'type="Part::PropertyPartShape"[^>]*>\s*<Part file="([^"]+\.brp)"', re.S)


def convert(src: str, out: str) -> int:
    """Write ``out``; returns the number of parts."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS_Shape
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    z = zipfile.ZipFile(src)
    pairs = SHAPE_RE.findall(z.read("Document.xml").decode("utf-8"))
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in pairs:
            path = os.path.join(tmp, "shape.brp")
            with open(path, "wb") as fh:
                fh.write(z.read(fn))
            shape = TopoDS_Shape()
            BRepTools.Read_s(shape, path, BRep_Builder())
            kind = TopAbs_SOLID if TopExp_Explorer(shape, TopAbs_SOLID).More() else TopAbs_SHELL
            ex = TopExp_Explorer(shape, kind)
            if not ex.More():
                continue
            asm = st.NewShape()
            TDataStd_Name.Set_s(asm, TCollection_ExtendedString(re.sub(r"_0\d$", "", name).replace("_", " ")))
            prefix = name.split("_")[0].upper()
            n = 0
            while ex.More():
                n += 1
                sh = ex.Current()
                part = st.AddShape(sh.Located(TopLoc_Location()), False)
                TDataStd_Name.Set_s(part, TCollection_ExtendedString(f"{prefix} PART {n}"))
                st.AddComponent(asm, part, sh.Location())
                ex.Next()
            st.UpdateAssemblies()
            print(f"{name}: {n} parts")
            total += n
    if not total:
        raise SystemExit(f"{src}: no stored shapes found")
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(out) != IFSelect_RetDone:
        raise SystemExit(f"could not write {out}")
    print(f"{total} parts -> {out}")
    return total


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
