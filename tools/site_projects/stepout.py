"""Write placed shapes as one STEP assembly whose sub-assemblies are the model's moving bodies (task 0112).

``write(out, top, bodies, parts)``: ``bodies`` maps a sub-assembly name to its parent's name (``top`` for the first
level); ``parts`` is a list of (part name, key, shape, 4x4 world matrix in mm, body name). Every sub-assembly sits at
the identity, so a part's place is its world matrix; a shape used by several parts (the same key) is stored once.
Each part must be one solid or one shell: the importer drops the colour of a part made of several solids
(CLAUDE.md section 8).
"""

from __future__ import annotations


def write(out: str, top: str, bodies: dict, parts: list) -> dict:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    from .a4 import trsf

    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    children: dict = {}
    for b, parent in bodies.items():
        children.setdefault(parent, []).append(b)
    by_body: dict = {}
    for p in parts:
        by_body.setdefault(p[4], []).append(p)
    unknown = set(by_body) - set(bodies) - {top}
    if unknown:
        raise ValueError(f"parts in bodies that are not in the tree: {sorted(unknown)}")
    shapes: dict = {}
    counts = {"parts": 0, "unique": 0, "bodies": 0}

    def fill(asm, body):
        for pname, key, shape, M, _b in by_body.get(body, []):
            if key not in shapes:
                shapes[key] = st.AddShape(shape, False)
                name(shapes[key], pname)
                counts["unique"] += 1
            st.AddComponent(asm, shapes[key], TopLoc_Location(trsf(M)))
            counts["parts"] += 1
        for sub in children.get(body, []):
            sa = st.NewShape()
            name(sa, sub)
            fill(sa, sub)
            counts["bodies"] += 1
            st.AddComponent(asm, sa, TopLoc_Location())

    root = st.NewShape()
    name(root, top)
    fill(root, top)
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(out) != IFSelect_RetDone:
        raise RuntimeError(f"could not write {out}")
    return counts
