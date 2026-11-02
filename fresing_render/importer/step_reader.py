"""Read a STEP file with OpenCascade and write a render cache.

This module never imports bpy. It runs in its own process (Blender's own
Python, started as a subprocess), so a large import never freezes the app
and a crash in OpenCascade cannot take Blender down.

Output (in ``out_dir``):
    tree.json   - assembly tree: one node per assembly / part occurrence
    meshes.npz  - one triangle mesh per *unique* part (repeated bolts are stored once)

Progress is printed to stdout as JSON lines: {"stage": ..., "pct": ..., "msg": ...}

Run directly:
    python step_reader.py model.step out_dir --quality normal
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

# Linear deflection relative to each part's size, angular deflection in radians.
QUALITY = {
    "draft": (0.004, 0.50),
    "normal": (0.0015, 0.30),
    "fine": (0.0006, 0.18),
}

CACHE_VERSION = 3          # 3: axes of round faces (joint picking), instance names
MM_TO_M = 0.001


def emit(stage: str, pct: float, msg: str = "", **extra) -> None:
    data = {"stage": stage, "pct": round(float(pct), 1), "msg": msg}
    data.update(extra)
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------
# OpenCascade helpers
# --------------------------------------------------------------------------

def _occ():
    """Import OpenCascade lazily so the module can be imported without it."""
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool, XCAFDoc_ColorTool, XCAFDoc_ColorType
    from OCP.TDF import TDF_Label, TDF_Tool
    from OCP.TDataStd import TDataStd_Name
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.BRepLib import BRepLib_ToolTriangulatedShape
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.collections import Sequence_TDF_Label
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType
    return locals()


def _label_name(occ, label) -> str:
    attr = occ["TDataStd_Name"]()
    if label.FindAttribute(occ["TDataStd_Name"].GetID_s(), attr):
        try:
            return attr.Get().ToExtString()
        except Exception:  # pragma: no cover - odd encodings
            return ""
    return ""


def _instance_name(occ, inst_label) -> str:
    """Occurrence name ("Frame:1" from Inventor). OpenCascade's own "=>[0:1:1:6]" placeholders are dropped."""
    if inst_label is None:
        return ""
    name = _label_name(occ, inst_label)
    return "" if name.startswith("=>[") else name


def _label_entry(occ, label) -> str:
    s = occ["TCollection_AsciiString"]()
    occ["TDF_Tool"].Entry_s(label, s)
    return s.ToCString()


def _color_of(occ, ctool, label):
    """Colour set on a label (surface colour first, then generic). sRGB 0-1 or None."""
    col = occ["Quantity_Color"]()
    get = getattr(occ["XCAFDoc_ColorTool"], "GetColor_s", None)
    for ctype in (occ["XCAFDoc_ColorType"].XCAFDoc_ColorSurf, occ["XCAFDoc_ColorType"].XCAFDoc_ColorGen):
        try:
            found = get(label, ctype, col) if get else ctool.GetColor(label, ctype, col)
        except Exception:
            found = False
        if found:
            r, g, b = col.Values(occ["Quantity_TOC_sRGB"])
            return (round(r, 4), round(g, 4), round(b, 4))
    return None


def _trsf_to_matrix(trsf) -> list:
    """gp_Trsf -> row-major 4x4 list (translation converted to metres)."""
    m = []
    for r in range(1, 4):
        row = [trsf.Value(r, c) for c in range(1, 4)]
        row.append(trsf.Value(r, 4) * MM_TO_M)
        m.append(row)
    m.append([0.0, 0.0, 0.0, 1.0])
    return m


def _face_colors(occ, stool, ctool, label):
    """Map face (by hash) -> colour for faces coloured individually in the CAD file."""
    result = []
    subs = occ["Sequence_TDF_Label"]()
    try:
        stool.GetSubShapes_s(label, subs)
    except Exception:
        return result
    for i in range(1, subs.Length() + 1):
        sl = subs.Value(i)
        c = _color_of(occ, ctool, sl)
        if c is None:
            continue
        sub_shape = stool.GetShape_s(sl)
        result.append((sub_shape, c))
    return result


MAX_AXES = 400   # per unique part


def _face_axis(occ, face):
    """Axis of a round face (cylinder, cone, torus, revolved surface) as (origin, direction, radius) in mm."""
    try:
        surf = occ["BRepAdaptor_Surface"](face, True)
        st = occ["GeomAbs_SurfaceType"]
        t = surf.GetType()
        if t == st.GeomAbs_Cylinder:
            c = surf.Cylinder()
            ax, r = c.Axis(), c.Radius()
        elif t == st.GeomAbs_Cone:
            c = surf.Cone()
            ax, r = c.Axis(), c.RefRadius()
        elif t == st.GeomAbs_Torus:
            c = surf.Torus()
            ax, r = c.Axis(), c.MajorRadius()
        elif t == st.GeomAbs_SurfaceOfRevolution:
            ax, r = surf.AxeOfRevolution(), 0.0
        else:
            return None
    except Exception:
        return None
    lo, d = ax.Location(), ax.Direction()
    return np.array((lo.X(), lo.Y(), lo.Z())), np.array((d.X(), d.Y(), d.Z())), float(r)


class _Axes:
    """Unique axes of one part; faces on the same line share one axis."""

    def __init__(self):
        self.keys: dict = {}
        self.axes: list[list[float]] = []      # ox, oy, oz, dx, dy, dz, radius (metres)
        self.faces: list[int] = []             # tri_start, tri_count, axis index (flat)

    def add(self, origin, direction, radius, tri_start: int, tri_count: int) -> None:
        d = direction / (np.linalg.norm(direction) or 1.0)
        nz = np.nonzero(np.abs(d) > 1e-9)[0]
        if len(nz) and d[nz[0]] < 0:
            d = -d                              # one sign per line
        foot = origin - d * float(np.dot(origin, d))   # point on the line closest to the part origin
        key = (tuple(np.round(d, 4)), tuple(np.round(foot, 3)))
        idx = self.keys.get(key)
        if idx is None:
            if len(self.axes) >= MAX_AXES:
                return
            idx = len(self.axes)
            self.keys[key] = idx
            o = foot * MM_TO_M
            self.axes.append([float(o[0]), float(o[1]), float(o[2]), float(d[0]), float(d[1]), float(d[2]),
                              radius * MM_TO_M])
        else:
            self.axes[idx][6] = max(self.axes[idx][6], radius * MM_TO_M)
        self.faces.extend((tri_start, tri_count, idx))


def _mesh_shape(occ, shape, lin_rel, ang, face_cols, already_meshed=False, axes: _Axes | None = None):
    """Tessellate one part. Returns (positions, normals, triangles, tri_color_idx, colours)."""
    if not already_meshed:
        occ["BRepMesh_IncrementalMesh"](shape, lin_rel, True, ang, True)
    positions, normals, tris, tri_col = [], [], [], []
    palette = []
    offset = 0
    tri_offset = 0
    exp = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
    BRep_Tool = occ["BRep_Tool"]
    TopLoc_Location = occ["TopLoc_Location"]
    compute_normals = occ["BRepLib_ToolTriangulatedShape"].ComputeNormals_s
    to_face = getattr(occ["TopoDS"], "Face", None) or getattr(occ["TopoDS"], "Face_s")
    while exp.More():
        face = to_face(exp.Current())
        exp.Next()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            continue
        n_nodes = tri.NbNodes()
        n_tris = tri.NbTriangles()
        if n_nodes == 0 or n_tris == 0:
            continue
        if not tri.HasNormals():
            try:
                compute_normals(face, tri)
            except Exception:
                pass
        trsf = loc.Transformation()
        identity = loc.IsIdentity()
        reversed_ = face.Orientation() == occ["TopAbs_REVERSED"]
        pts = np.empty((n_nodes, 3), dtype=np.float64)
        nrm = np.zeros((n_nodes, 3), dtype=np.float64)
        has_n = tri.HasNormals()
        for i in range(1, n_nodes + 1):
            p = tri.Node(i)
            if not identity:
                p = p.Transformed(trsf)
            pts[i - 1] = (p.X(), p.Y(), p.Z())
            if has_n:
                d = tri.Normal(i)
                if not identity:
                    d = d.Transformed(trsf)
                nrm[i - 1] = (d.X(), d.Y(), d.Z())
        if reversed_ and has_n:
            nrm = -nrm
        t = np.empty((n_tris, 3), dtype=np.int64)
        for j in range(1, n_tris + 1):
            a, b, c = tri.Triangle(j).Get()
            if reversed_:
                t[j - 1] = (a - 1, c - 1, b - 1)
            else:
                t[j - 1] = (a - 1, b - 1, c - 1)
        # face colour
        cidx = -1
        if face_cols:
            for sub_shape, colr in face_cols:
                if sub_shape.IsSame(face):
                    if colr not in palette:
                        palette.append(colr)
                    cidx = palette.index(colr)
                    break
        if axes is not None:
            fa = _face_axis(occ, face)
            if fa is not None:
                axes.add(fa[0], fa[1], fa[2], tri_offset, n_tris)
        positions.append(pts)
        normals.append(nrm)
        tris.append(t + offset)
        tri_col.append(np.full(n_tris, cidx, dtype=np.int16))
        offset += n_nodes
        tri_offset += n_tris
    if not positions:
        return None
    pos = np.concatenate(positions) * MM_TO_M
    nrm = np.concatenate(normals)
    # fill missing normals from triangle geometry
    missing = np.linalg.norm(nrm, axis=1) < 0.5
    tri_all = np.concatenate(tris)
    if missing.any():
        v0, v1, v2 = pos[tri_all[:, 0]], pos[tri_all[:, 1]], pos[tri_all[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        acc = np.zeros_like(nrm)
        for k in range(3):
            np.add.at(acc, tri_all[:, k], fn)
        ln = np.linalg.norm(acc, axis=1, keepdims=True)
        ln[ln == 0] = 1
        nrm[missing] = (acc / ln)[missing]
    return (
        pos.astype(np.float32),
        nrm.astype(np.float32),
        tri_all.astype(np.int32),
        np.concatenate(tri_col),
        palette,
    )


# --------------------------------------------------------------------------
# Main reader
# --------------------------------------------------------------------------

def read_step(path: str, out_dir: str, quality: str = "normal") -> dict:
    t0 = time.time()
    occ = _occ()
    lin_rel, ang = QUALITY.get(quality, QUALITY["normal"])
    os.makedirs(out_dir, exist_ok=True)

    emit("read", 2, "Reading STEP file")
    app = occ["XCAFApp_Application"].GetApplication_s()
    doc = occ["TDocStd_Document"](occ["TCollection_ExtendedString"]("XmlXCAF"))
    app.InitDocument(doc)
    reader = occ["STEPCAFControl_Reader"]()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(False)
    reader.SetPropsMode(False)
    status = reader.ReadFile(path)
    if status != occ["IFSelect_RetDone"]:
        raise RuntimeError(f"Could not read STEP file (status {status})")
    emit("transfer", 25, "Building assembly structure")
    if not reader.Transfer(doc):
        raise RuntimeError("STEP transfer failed")
    t_read = time.time() - t0

    stool = occ["XCAFDoc_DocumentTool"].ShapeTool_s(doc.Main())
    ctool = occ["XCAFDoc_DocumentTool"].ColorTool_s(doc.Main())

    nodes: list[dict] = []
    mesh_index: dict[str, int] = {}      # label entry -> mesh id
    mesh_labels: list = []               # mesh id -> referred label
    mesh_names: list[str] = []

    def add_node(label, parent: int, trsf, inst_label, sibling_counts: dict):
        name = _label_name(occ, label) or (_label_name(occ, inst_label) if inst_label is not None else "") or "Unnamed"
        count = sibling_counts.get(name, 0) + 1
        sibling_counts[name] = count
        parent_uid = nodes[parent]["uid"] if parent >= 0 else ""
        uid = f"{parent_uid}/{name}#{count}" if parent_uid else f"{name}#{count}"
        node = {
            "uid": uid,
            "name": name,
            "instance": _instance_name(occ, inst_label),
            "parent": parent,
            "matrix": _trsf_to_matrix(trsf) if trsf is not None else None,
            "kind": "assembly",
            "mesh": -1,
            "color": None,
        }
        idx = len(nodes)
        nodes.append(node)
        col = None
        if inst_label is not None:
            col = _color_of(occ, ctool, inst_label)
        if col is None:
            col = _color_of(occ, ctool, label)
        node["color"] = col
        # colour set on an assembly occurrence applies to everything inside it
        node["inherited_color"] = col or (nodes[parent].get("inherited_color") if parent >= 0 else None)

        if occ["XCAFDoc_ShapeTool"].IsAssembly_s(label):
            comps = occ["Sequence_TDF_Label"]()
            occ["XCAFDoc_ShapeTool"].GetComponents_s(label, comps, False)
            counts: dict = {}
            for i in range(1, comps.Length() + 1):
                comp = comps.Value(i)
                ref = occ["TDF_Label"]()
                if not occ["XCAFDoc_ShapeTool"].GetReferredShape_s(comp, ref):
                    continue
                loc = occ["XCAFDoc_ShapeTool"].GetLocation_s(comp)
                add_node(ref, idx, loc.Transformation(), comp, counts)
        else:
            node["kind"] = "part"
            entry = _label_entry(occ, label)
            if entry not in mesh_index:
                mesh_index[entry] = len(mesh_labels)
                mesh_labels.append(label)
                mesh_names.append(name)
            node["mesh"] = mesh_index[entry]
        return idx

    free = occ["Sequence_TDF_Label"]()
    stool.GetFreeShapes(free)
    root_counts: dict = {}
    for i in range(1, free.Length() + 1):
        lab = free.Value(i)
        loc = occ["XCAFDoc_ShapeTool"].GetLocation_s(lab)
        add_node(lab, -1, loc.Transformation(), None, root_counts)

    n_parts = sum(1 for n in nodes if n["kind"] == "part")
    emit("structure", 30, f"{len(mesh_labels)} unique parts, {n_parts} placed parts")

    # ---- tessellate unique parts -------------------------------------------
    arrays: dict[str, np.ndarray] = {}
    mesh_meta: list[dict] = []
    total = max(1, len(mesh_labels))
    tri_total = 0
    t1 = time.time()
    # Each part is tessellated on its own: the deflection is relative to the part's size,
    # so small parts (bolts) stay smooth next to big frames. OpenCascade still uses all
    # cores within each part.
    shapes = [occ["XCAFDoc_ShapeTool"].GetShape_s(label) for label in mesh_labels]
    premeshed = False
    for mid, label in enumerate(mesh_labels):
        shape = shapes[mid]
        face_cols = _face_colors(occ, stool, ctool, label)
        axes = _Axes()
        try:
            res = _mesh_shape(occ, shape, lin_rel, ang, face_cols, already_meshed=premeshed, axes=axes)
        except Exception as exc:  # keep going, report the part
            emit("warning", 30 + 65 * mid / total, f"Could not mesh {mesh_names[mid]}: {exc}")
            res = None
        meta = {"name": mesh_names[mid], "tris": 0, "palette": [], "bbox": None,
                "axes": axes.axes if res is not None else [], "axis_faces": axes.faces if res is not None else []}
        if res is not None:
            pos, nrm, tri, tcol, palette = res
            arrays[f"p{mid}"] = pos
            arrays[f"n{mid}"] = nrm
            arrays[f"t{mid}"] = tri
            if palette:
                arrays[f"c{mid}"] = tcol
            meta["tris"] = int(len(tri))
            meta["palette"] = palette
            meta["bbox"] = [pos.min(axis=0).tolist(), pos.max(axis=0).tolist()]
            tri_total += len(tri)
        mesh_meta.append(meta)
        if mid % 10 == 0 or mid == total - 1:
            emit("mesh", 30 + 65 * (mid + 1) / total, f"Meshing part {mid + 1} of {total}")
    t_mesh = time.time() - t1

    # part colour: own colour > dominant face colour > colour of an enclosing assembly
    for node in nodes:
        if node["kind"] == "part" and node["color"] is None:
            pal = mesh_meta[node["mesh"]]["palette"]
            key = f"c{node['mesh']}"
            if pal and key in arrays:
                idx = arrays[key]
                idx = idx[idx >= 0]
                if len(idx):
                    node["color"] = pal[int(np.bincount(idx).argmax())]
        if node["kind"] == "part" and node["color"] is None:
            node["color"] = node.get("inherited_color")
    for node in nodes:
        node.pop("inherited_color", None)

    emit("write", 96, "Writing cache")
    np.savez(os.path.join(out_dir, "meshes.npz"), **arrays)
    info = {
        "version": CACHE_VERSION,
        "source": os.path.abspath(path),
        "source_size": os.path.getsize(path),
        "source_mtime": os.path.getmtime(path),
        "quality": quality,
        "units": "m",
        "nodes": nodes,
        "meshes": mesh_meta,
        "stats": {
            "unique_parts": len(mesh_labels),
            "placed_parts": n_parts,
            "triangles_unique": int(tri_total),
            "seconds_read": round(t_read, 1),
            "seconds_mesh": round(t_mesh, 1),
            "seconds_total": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(out_dir, "tree.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    emit("done", 100, "Import finished", stats=info["stats"])
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step")
    ap.add_argument("out_dir")
    ap.add_argument("--quality", default="normal", choices=sorted(QUALITY))
    args = ap.parse_args(argv)
    try:
        read_step(args.step, args.out_dir, args.quality)
    except Exception as exc:
        emit("error", 100, str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
