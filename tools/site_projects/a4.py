"""FreeCAD Assembly4 files without FreeCAD (task 0047, reworked in task 0112 for the Thor project).

Assembly4 keeps every part in its own file and places it with App::Link objects (also links to sub-assembly files).
``Reader`` follows the links from the "Model" part of the top file through all files in the same folder and
multiplies the stored placements. Hidden links are left out. Each placed part keeps the chain of link names it was
reached through (``Part.path``), so a caller can tell which sub-assembly a part belongs to; ``Reader.lcs_world``
gives the world frame of a coordinate system (LCS) of a linked file, which is how Assembly4 says where two
sub-assemblies meet – the joints of the Thor arm are read from these.

Placements are 4x4 NumPy matrices in mm; the OpenCascade shapes are read only when asked (``shapes=True``).
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field

import numpy as np


def quat_matrix(q0: float, q1: float, q2: float, q3: float) -> np.ndarray:
    """FreeCAD's quaternion (x, y, z, w) as a 3x3 rotation."""
    x, y, z, w = q0, q1, q2, q3
    n = (x * x + y * y + z * z + w * w) ** 0.5 or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def placement(body: str, prop: str = "Placement") -> np.ndarray:
    """A placement property of an object's XML as a 4x4 matrix (identity when it has none)."""
    m = re.search(rf'name="{prop}" type="App::PropertyPlacement".*?<PropertyPlacement ([^/]*)/>', body, re.S)
    M = np.eye(4)
    if not m:
        return M
    p = {k: float(v) for k, v in re.findall(r'(\w+)="([^"]*)"', m.group(1))}
    M[:3, :3] = quat_matrix(p["Q0"], p["Q1"], p["Q2"], p["Q3"])
    M[:3, 3] = (p["Px"], p["Py"], p["Pz"])
    return M


def visible(body: str) -> bool:
    m = re.search(r'name="Visibility" type="App::PropertyBool".*?<Bool value="([^"]*)"', body, re.S)
    return not m or m.group(1) == "true"


@dataclass
class Part:
    label: str                 # the name the STEP gets: the file's name for a whole-file body, else the object's
    key: tuple                 # (file, object): one shape, maybe placed several times
    matrix: np.ndarray         # world placement (mm)
    path: tuple                # link names from the top: ("AssemblyArt1", "AssemblyArt2", "Art2BodyA_Art2BodyA")
    brep: bytes = field(default=b"", repr=False)


class Reader:
    def __init__(self, top: str):
        self.top = os.path.abspath(top)
        self.folder = os.path.dirname(self.top)
        self._docs: dict = {}
        self._files = {f.lower(): f for f in os.listdir(self.folder)}

    def find(self, name: str) -> str:
        f = self._files.get(name.lower())
        if f is None:
            raise FileNotFoundError(f"{name} is not in {self.folder}")
        return os.path.join(self.folder, f)

    def doc(self, path: str):
        """(zip, {object: type}, {object: XML})"""
        if path not in self._docs:
            z = zipfile.ZipFile(path)
            d = z.read("Document.xml").decode("utf-8")
            types = dict((n, t) for t, n in re.findall(r'<Object type="([^"]+)" name="([^"]+)"', d))
            objs = {}
            i = d.index("<ObjectData")
            for m in re.finditer(r'<Object name="([^"]+)"[^>]*>(.*?)\n        </Object>', d[i:], re.S):
                objs[m.group(1)] = m.group(2)
            self._docs[path] = (z, types, objs)
        return self._docs[path]

    def link_target(self, path: str, body: str) -> tuple[str, str]:
        lo = re.search(r'name="LinkedObject".*?(?:<XLink file="([^"]*)"[^>]*name="([^"]*)"|<Link value="([^"]*)")',
                       body, re.S)
        return (self.find(lo.group(1)) if lo.group(1) else path), (lo.group(2) or lo.group(3))

    def link_matrix(self, link: str, path: str | None = None) -> np.ndarray:
        """The placement of a link of the top file (or of ``path``)."""
        _z, _t, objs = self.doc(path or self.top)
        return placement(objs[link])

    def lcs_world(self, chain: tuple, lcs: str) -> np.ndarray:
        """World frame of coordinate system ``lcs`` of the file reached through the links ``chain`` (from the top
        file; each link's placement multiplied, as ``parts`` does)."""
        M = np.eye(4)
        path = self.top
        for link in chain:
            _z, _types, objs = self.doc(path)
            M = M @ placement(objs[link])
            path, _name = self.link_target(path, objs[link])
        _z, _types, objs = self.doc(path)
        return M @ placement(objs[lcs])

    def parts(self, shapes: bool = False) -> list[Part]:
        out: list[Part] = []
        self._resolve(self.top, "Model", np.eye(4), (), True, out, shapes)
        return out

    def _resolve(self, path, name, M, chain, via_link, out, shapes):
        """via_link: reached through a link, whose placement replaces the object's own. Reached as a child of an
        App::Part (a library part such as a bearing or a board, or a sub-part of one), the object keeps its own
        placement inside that part (the Thor board and bearings went astray without this)."""
        z, types, objs = self.doc(path)
        body = objs[name]
        t = types.get(name)
        if t == "App::Link":
            tgt_path, tgt = self.link_target(path, body)
            self._resolve(tgt_path, tgt, M @ placement(body), chain + (name,), True, out, shapes)
            return
        if t == "App::Part":
            if not via_link:
                M = M @ placement(body)
            grp = re.search(r'name="Group" type="App::PropertyLinkList".*?<LinkList[^>]*>(.*?)</LinkList>', body, re.S)
            for child in re.findall(r'<Link value="([^"]*)"', grp.group(1) if grp else ""):
                ct = types.get(child, "")
                if ct in ("App::Link", "App::Part") or (ct.startswith(("Part", "PartDesign::Body"))
                                                        and 'type="Part::PropertyPartShape"' in objs.get(child, "")):
                    if visible(objs[child]):
                        self._resolve(path, child, M, chain, False, out, shapes)
            return
        f = re.search(r'name="Shape" type="Part::PropertyPartShape"[^>]*>\s*<Part file="([^"]+)"', body)
        if not f:
            return
        data = z.read(f.group(1))
        if not via_link:                       # keep its own place inside the part it belongs to
            M = M @ _brep_location(data)
        stem = os.path.splitext(os.path.basename(path))[0]
        label = stem if name in ("Body", "Body001", "Body002", "Model") else name
        out.append(Part(label, (path, name), M, chain, data if shapes else b""))


def _brep_location(data: bytes) -> np.ndarray:
    """The location stored on a shape in a .brp file (needs OpenCascade)."""
    s = read_brep(data)
    t = s.Location().Transformation()
    M = np.eye(4)
    for i in range(3):
        for j in range(4):
            M[i, j] = t.Value(i + 1, j + 1)
    return M


def read_brep(data: bytes):
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape
    fd, tmp = tempfile.mkstemp(suffix=".brp")
    os.close(fd)
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        s = TopoDS_Shape()
        BRepTools.Read_s(s, tmp, BRep_Builder())
    finally:
        os.remove(tmp)
    return s


def trsf(M: np.ndarray):
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(*(float(M[i, j]) for i in range(3) for j in range(4)))
    return t


def placement_expression(body: str) -> list[str]:
    """The terms of an Assembly4 placement expression: ['Parent.Placement', 'File#LCS.Placement',
    'AttachmentOffset', 'Own#LCS.Placement ^ -1'] ([] when the object is not attached)."""
    m = re.search(r'<Expression path="Placement" expression="([^"]*)"', body)
    return [t.strip() for t in m.group(1).split("*")] if m else []


def _term_object(term: str) -> str:
    return term.split(".Placement")[0].strip()


class Attachments:
    """Who is attached to whom inside one Assembly4 file, and where (the coordinate systems)."""

    def __init__(self, reader: Reader, chain: tuple):
        """``chain``: the links from the top file to this file (one link: a sub-assembly of the top file)."""
        self.r = reader
        self.chain = chain
        path = reader.top
        M = np.eye(4)
        for link in chain:
            _z, _t, objs = reader.doc(path)
            M = M @ placement(objs[link])
            path, _name = reader.link_target(path, objs[link])
        self.path, self.world = path, M
        _z, self.types, self.objs = reader.doc(path)
        self.parent = {}
        for n, b in self.objs.items():
            terms = placement_expression(b)
            if terms:
                self.parent[n] = _term_object(terms[0])

    def anchor(self, obj: str, anchors) -> str:
        """The first object of ``anchors`` on the way up from ``obj`` (``obj`` itself first), '' when none."""
        seen = set()
        while obj and obj not in seen:
            if obj in anchors:
                return obj
            seen.add(obj)
            obj = self.parent.get(obj, "")
        return ""

    def _lcs(self, term: str, owner: str) -> np.ndarray:
        """A coordinate system named in an expression term: 'File#LCS' (in that file) or 'LCS' (in this file)."""
        ref = _term_object(term).split("^")[0].strip()
        if "#" in ref:
            f, lcs = ref.split("#", 1)
            _z, _t, objs = self.r.doc(self.r.find(f + ".FCStd"))
            return placement(objs[lcs])
        return placement(self.objs[ref])

    def frames(self, obj: str) -> tuple[np.ndarray, np.ndarray]:
        """World frames where ``obj`` is attached: (the parent's coordinate system x the attachment offset, the
        object's own coordinate system). Assembly4 makes them the same frame; both are returned so a caller can
        check that."""
        body = self.objs[obj]
        terms = placement_expression(body)
        if len(terms) < 4:
            raise ValueError(f"{obj} is not attached to a coordinate system")
        parent = _term_object(terms[0])
        P = self.world if parent.startswith("LCS_") else self.world @ placement(self.objs[parent])
        if parent.startswith("LCS_"):
            P = P @ placement(self.objs[parent])
            on_parent = P @ placement(body, "AttachmentOffset")
        else:
            on_parent = P @ self._lcs(terms[1], parent) @ placement(body, "AttachmentOffset")
        own = self.world @ placement(body) @ self._lcs(terms[-1], obj)
        return on_parent, own

    def lcs(self, ref: str) -> np.ndarray:
        """World frame of a coordinate system 'File#LCS' of a part placed by link ``File_File`` in this file, or of
        'LCS' of this file."""
        if "#" in ref:
            f, lcs = ref.split("#", 1)
            link = next(n for n, b in self.objs.items() if self.types.get(n) == "App::Link"
                        and self.r.link_target(self.path, b)[0] == self.r.find(f + ".FCStd"))
            _z, _t, objs = self.r.doc(self.r.find(f + ".FCStd"))
            return self.world @ placement(self.objs[link]) @ placement(objs[lcs])
        return self.world @ placement(self.objs[ref])
