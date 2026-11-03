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
import io
import json
import os
import pickle
import queue
import struct
import subprocess
import sys
import threading
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
    from OCP.BinTools import BinTools, BinTools_FormatVersion, BinTools_ShapeSet
    from OCP.TopoDS import TopoDS_Shape, TopoDS_Face
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


def _faces(occ, shape):
    """The faces of a shape in OpenCascade's own order (the same order after a binary copy)."""
    exp = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
    to_face = getattr(occ["TopoDS"], "Face", None) or getattr(occ["TopoDS"], "Face_s")
    while exp.More():
        yield to_face(exp.Current())
        exp.Next()


def _face_colour_list(occ, shape, face_cols):
    """Colour per face (by position in _faces order), None for faces without their own colour.

    Returns None when the part has no individually coloured faces (the usual case)."""
    if not face_cols:
        return None
    out = []
    for face in _faces(occ, shape):
        colr = None
        for sub_shape, c in face_cols:
            if sub_shape.IsSame(face):
                colr = c
                break
        out.append(colr)
    return out if any(c is not None for c in out) else None


def _trsf_arrays(trsf):
    """gp_Trsf -> (3x4 matrix incl. scale, 3x3 rotation, scale factor) for numpy."""
    m = np.array([[trsf.Value(r, c) for c in range(1, 5)] for r in range(1, 4)], dtype=np.float64)
    hv = trsf.HVectorialPart()
    rot = np.array([[hv.Value(r, c) for c in range(1, 4)] for r in range(1, 4)], dtype=np.float64)
    return m, rot, trsf.ScaleFactor()


def _parse_triangulations(data: bytes) -> list:
    """OpenCascade's binary triangulation block -> [(nodes Nx3 f8, triangles Mx3 i4, normals Nx3 f4 or None)].

    Layout (BinTools format 4, x86): "Triangulations <n>\\n", then per triangulation: nodes,
    triangles (int32), has-UV and has-normals (1 byte each), deflection (f8), nodes (3 f8),
    UV (2 f8, if any), triangles (3 i4, 1-based), normals (3 f4, if any)."""
    nl = data.index(b"\n")
    head = data[:nl].split()
    if len(head) != 2 or head[0] != b"Triangulations":
        raise ValueError("not a triangulation block")
    pos = nl + 1
    out = []
    for _ in range(int(head[1])):
        nn, nt = (int(v) for v in np.frombuffer(data, "<i4", 2, pos))
        has_uv, has_n = data[pos + 8], data[pos + 9]
        if nn < 0 or nt < 0 or has_uv > 1 or has_n > 1:
            raise ValueError("unexpected triangulation record")
        pos += 18                                          # counts, flags, deflection
        nodes = np.frombuffer(data, "<f8", nn * 3, pos).reshape(nn, 3)
        pos += nn * 24 + (nn * 16 if has_uv else 0)
        tris = np.frombuffer(data, "<i4", nt * 3, pos).reshape(nt, 3)
        pos += nt * 12
        nrm = None
        if has_n:
            nrm = np.frombuffer(data, "<f4", nn * 3, pos).reshape(nn, 3)
            pos += nn * 12
        out.append((nodes, tris, nrm))
    if pos != len(data):
        raise ValueError("triangulation block has an unexpected length")
    return out


def _bulk_triangulations(occ, entries) -> list | None:
    """Nodes, triangles and normals of all faces in one call (instead of one call per node).

    ``entries``: (face, triangulation) in face order. Returns one record per entry, or None
    when the block does not match the faces (then the caller reads node by node)."""
    try:
        ss = occ["BinTools_ShapeSet"]()
        ss.SetWithTriangles(True)
        ss.SetWithNormals(True)
        builder = occ["BRep_Builder"]()
        index: dict = {}                                   # triangulation -> record (faces of repeated
        for _face, tri in entries:                         # sub-shapes share one triangulation)
            if tri in index:
                continue
            index[tri] = len(index)
            # a bare face holding only this triangulation: the real face's edges would also
            # bring in the neighbours' triangulations and mix up the order
            bare = occ["TopoDS_Face"]()
            builder.MakeFace(bare, tri)
            ss.Add(bare)
        buf = io.BytesIO()
        ss.WriteTriangulation(buf)
        unique = _parse_triangulations(buf.getvalue())
    except Exception:
        return None
    if len(unique) != len(index):
        return None
    records = [unique[index[tri]] for _face, tri in entries]
    for (face, tri), (nodes, tris, _nrm) in zip(entries, records):
        if len(nodes) != tri.NbNodes() or len(tris) != tri.NbTriangles():
            return None
    for k in {0, len(entries) - 1} if entries else ():   # spot check: the block holds the same numbers
        tri = entries[k][1]
        if tuple(records[k][0][0]) != tri.Node(1).Coord() or tuple(records[k][1][-1]) != \
                tri.Triangle(tri.NbTriangles()).Get():
            return None
    return records


def _is_plane(occ, face) -> bool:
    try:
        return occ["BRepAdaptor_Surface"](face, True).GetType() == occ["GeomAbs_SurfaceType"].GeomAbs_Plane
    except Exception:
        return False


def _record_normals(occ, face, tri, rec_normals, n_nodes: int):
    """Normals of one face: from the block, else (the block leaves them out for some faces) from OpenCascade."""
    if rec_normals is not None:                            # normalised in double, as OpenCascade's gp_Dir does
        n = rec_normals.astype(np.float64)
        ln = np.sqrt(n[:, 0] * n[:, 0] + n[:, 1] * n[:, 1] + n[:, 2] * n[:, 2])
        ok = ln > 0
        n[ok] /= ln[ok, None]
        return n
    if not tri.HasNormals():
        return None
    if _is_plane(occ, face):                               # a plane: one normal for every node
        first, last = tri.Normal(1).Coord(), tri.Normal(n_nodes).Coord()
        if first == last:
            return np.tile(np.array(first, dtype=np.float64), (n_nodes, 1))
    normal = tri.Normal
    return np.array([normal(i).Coord() for i in range(1, n_nodes + 1)], dtype=np.float64)


def _mesh_shape(occ, shape, lin_rel, ang, face_colours=None, already_meshed=False, axes: _Axes | None = None,
                bulk: bool = True):
    """Tessellate one part. Returns (positions, normals, triangles, tri_color_idx, colours).

    ``face_colours``: from _face_colour_list (a colour or None per face), or None.
    ``bulk``: read the triangles in one block (False: node by node, the old way)."""
    if not already_meshed:
        occ["BRepMesh_IncrementalMesh"](shape, lin_rel, True, ang, True)
    positions, normals, tris, tri_col = [], [], [], []
    palette = []
    offset = 0
    tri_offset = 0
    BRep_Tool = occ["BRep_Tool"]
    TopLoc_Location = occ["TopLoc_Location"]
    compute_normals = occ["BRepLib_ToolTriangulatedShape"].ComputeNormals_s
    REVERSED = occ["TopAbs_REVERSED"]
    faces = []                                             # (face number, face, location, triangulation)
    for face_no, face in enumerate(_faces(occ, shape)):
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None or tri.NbNodes() == 0 or tri.NbTriangles() == 0:
            continue
        if not tri.HasNormals():
            try:
                compute_normals(face, tri)
            except Exception:
                pass
        faces.append((face_no, face, loc, tri))
    records = _bulk_triangulations(occ, [(f, t) for _n, f, _l, t in faces]) if bulk else None
    for k, (face_no, face, loc, tri) in enumerate(faces):
        n_nodes = tri.NbNodes()
        n_tris = tri.NbTriangles()
        reversed_ = face.Orientation() == REVERSED
        if records is not None:
            rec_nodes, rec_tris, rec_nrm = records[k]
            pts = rec_nodes.astype(np.float64)
            t = rec_tris.astype(np.int64) - 1
            nrm = _record_normals(occ, face, tri, rec_nrm, n_nodes)
        else:
            # one call per node / triangle; numpy does the rest
            node = tri.Node
            pts = np.array([node(i).Coord() for i in range(1, n_nodes + 1)], dtype=np.float64)
            nrm = None
            if tri.HasNormals():
                normal = tri.Normal
                nrm = np.array([normal(i).Coord() for i in range(1, n_nodes + 1)], dtype=np.float64)
            triangle = tri.Triangle
            t = np.array([triangle(j).Get() for j in range(1, n_tris + 1)], dtype=np.int64) - 1
        has_n = nrm is not None
        if not has_n:
            nrm = np.zeros((n_nodes, 3), dtype=np.float64)
        if not loc.IsIdentity():
            m, rot, scale = _trsf_arrays(loc.Transformation())
            pts = pts @ m[:, :3].T + m[:, 3]
            if has_n:                          # as gp_Dir.Transform: rotate, normalise, flip on negative scale
                nrm = nrm @ rot.T
                ln = np.linalg.norm(nrm, axis=1, keepdims=True)
                ln[ln == 0] = 1.0
                nrm /= ln
                if scale < 0:
                    nrm = -nrm
        if reversed_ and has_n:
            nrm = -nrm
        if reversed_:
            t = t[:, (0, 2, 1)]
        # face colour
        cidx = -1
        if face_colours:
            colr = face_colours[face_no] if face_no < len(face_colours) else None
            if colr is not None:
                if colr not in palette:
                    palette.append(colr)
                cidx = palette.index(colr)
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
# Meshing on all cores
# --------------------------------------------------------------------------
# Reading the file and building the assembly happen in this process. Each unique part is
# then copied (OpenCascade's own binary format, in memory) to helper processes that mesh
# it and turn the triangles into arrays: one part per core at a time, biggest first.

PARALLEL_MIN_BYTES = 3_000_000      # smaller STEP files are done in well under a second anyway
MAX_WORKERS = 24
_JOB, _RESULT, _READY = b"FRJ1", b"FRR1", b"FRW1"
_HEAD = struct.Struct(">4sQ")


HELPER_MEMORY = 400 * 1024 * 1024   # OpenCascade plus one part being meshed, generous


def _free_memory() -> int | None:
    """Free physical memory in bytes, None if unknown."""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
            k32.GlobalMemoryStatusEx.restype = ctypes.c_int
            return int(st.ullAvailPhys) if k32.GlobalMemoryStatusEx(ctypes.byref(st)) else None
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return None


def worker_count() -> int:
    """Helper processes for meshing (0 = mesh in this process).

    Automatic: all cores but one, as far as free memory allows.
    FRESING_IMPORT_WORKERS overrides the automatic choice."""
    if os.path.basename(sys.executable).lower().startswith("blender"):
        return 0                       # not started as a plain Python: no helpers
    env = os.environ.get("FRESING_IMPORT_WORKERS", "").strip()
    if env.isdigit():
        n = int(env)
    else:
        cores = getattr(os, "process_cpu_count", os.cpu_count)() or 1   # cores this process may use
        n = cores - 1
        free = _free_memory()
        if free is not None:
            n = min(n, int(free // HELPER_MEMORY) - 2)   # keep room for the model itself
    n = min(n, MAX_WORKERS)
    return n if n >= 2 else 0


def _send(stream, tag: bytes, obj) -> None:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    stream.write(_HEAD.pack(tag, len(data)))
    stream.write(data)
    stream.flush()


def _recv(stream, tag: bytes):
    head = stream.read(_HEAD.size)
    if len(head) < _HEAD.size:
        raise EOFError("helper stopped")
    got, size = _HEAD.unpack(head)
    if got != tag:
        raise RuntimeError("helper sent something unexpected")
    data = stream.read(size)
    if len(data) < size:
        raise EOFError("helper stopped")
    return pickle.loads(data)


# ---- in a helper process ------------------------------------------------------

def _exit_with_parent(parent_pid: int) -> None:
    """A helper stops at once when the reader stops (also when Cancel kills it)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        handle = k32.OpenProcess(0x00100000, False, parent_pid)          # SYNCHRONIZE
        if not handle:
            os._exit(0)                                                   # already gone

        def watch():
            k32.WaitForSingleObject(handle, 0xFFFFFFFF)                    # INFINITE
            os._exit(0)
    else:
        def watch():
            while os.getppid() == parent_pid:
                time.sleep(0.5)
            os._exit(0)
    threading.Thread(target=watch, daemon=True).start()


def _mesh_job(occ, mid: int, blob: bytes, face_colours, lin_rel: float, ang: float):
    """Mesh one part sent as binary BRep. Returns (mid, result, axes, axis_faces, error)."""
    if os.environ.get("FRESING_TEST_CRASH_PART") == str(mid):
        os._exit(3)                                  # tests: a helper that dies on one part
    try:
        if os.environ.get("FRESING_TEST_FAIL_PART") == str(mid):
            raise MemoryError("test")                # tests: a part that fails in a helper
        shape = occ["TopoDS_Shape"]()
        occ["BinTools"].Read_s(shape, io.BytesIO(blob))
        axes = _Axes()
        res = _mesh_shape(occ, shape, lin_rel, ang, face_colours, axes=axes)
    except Exception as exc:
        return mid, None, [], [], str(exc) or exc.__class__.__name__
    return mid, res, axes.axes, axes.faces, None


def _no_crash_dialog() -> None:
    """Windows: a crash ends the process at once instead of waiting on an error-report window."""
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.SetErrorMode.argtypes = [ctypes.c_uint]
            k32.SetErrorMode.restype = ctypes.c_uint
            k32.SetErrorMode(0x0001 | 0x0002)        # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
        except Exception:
            pass


def worker_main(parent_pid: int) -> int:
    """Helper loop: jobs come in on stdin, results go out on stdout, until stdin closes."""
    _no_crash_dialog()
    _exit_with_parent(parent_pid)
    if os.name != "nt":
        try:
            os.nice(5)               # Windows: the reader starts helpers below normal priority
        except OSError:
            pass
    out_fd = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)              # anything OpenCascade prints must not end up in the result stream
    sys.stdout = open(os.devnull, "w")
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(0, os.O_BINARY)
        msvcrt.setmode(out_fd, os.O_BINARY)
    out = os.fdopen(out_fd, "wb")
    inp = sys.stdin.buffer
    occ = _occ()
    _send(out, _READY, os.getpid())
    while True:
        try:
            job = _recv(inp, _JOB)
        except EOFError:
            return 0
        _send(out, _RESULT, _mesh_job(occ, *job))


# ---- in the reader ----------------------------------------------------------------

def _kill_on_close_job():
    """Windows job object that ends its processes when the reader ends (also when it is killed)."""
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMITS(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED_LIMITS(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC_LIMITS), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryLimit", ctypes.c_size_t), ("PeakJobMemoryLimit", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None, None
    info = EXTENDED_LIMITS()
    info.BasicLimitInformation.LimitFlags = 0x00002000            # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):   # ExtendedLimitInformation
        return None, None

    def assign(proc) -> None:
        if not k32.AssignProcessToJobObject(job, int(proc._handle)):
            sys.stderr.write(f"helper not in job (error {ctypes.get_last_error()}); it stops by itself\n")
    return job, assign


def _die_with_parent() -> None:            # Linux: runs in the helper just before it starts
    import ctypes
    import signal
    ctypes.CDLL(None, use_errno=True).prctl(1, int(signal.SIGKILL))   # PR_SET_PDEATHSIG


class _Helpers:
    """Helper processes started at the beginning, so they load OpenCascade while the file is read."""

    def __init__(self, n: int):
        self.procs: list[subprocess.Popen] = []
        self.started = 0
        self._job = None                     # kept open as long as the reader runs
        kwargs: dict = {}
        assign = None
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000 | 0x00004000   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
            try:
                self._job, assign = _kill_on_close_job()
            except Exception:
                assign = None                # the helpers still stop by themselves, a bit later
        elif sys.platform.startswith("linux"):
            kwargs["preexec_fn"] = _die_with_parent
        cmd = [sys.executable, os.path.abspath(__file__), "--worker", str(os.getpid())]
        for _ in range(n):
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
            except OSError:
                break
            if assign is not None:
                try:
                    assign(proc)
                except Exception:
                    pass
            self.procs.append(proc)

    def run(self, jobs: list, on_result) -> tuple:
        """Hand out ``jobs`` (biggest first); ``on_result`` is called here for every result.

        Returns (mid, reason) for parts a helper stopped on, and the jobs nobody took.
        ``self.started``: helpers that came up."""
        todo: "queue.Queue" = queue.Queue()
        for job in jobs:
            todo.put(job)
        results: "queue.Queue" = queue.Queue()
        threads = [threading.Thread(target=self._feed, args=(p, todo, results), daemon=True) for p in self.procs]
        for t in threads:
            t.start()
        lost = []
        self.started = 0
        while any(t.is_alive() for t in threads) or not results.empty():
            try:
                kind, payload = results.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "ok":
                on_result(payload)
            elif kind == "ready":
                self.started += 1
            else:
                lost.append(payload)
        left = []
        while True:
            try:
                left.append(todo.get_nowait())
            except queue.Empty:
                break
        return lost, left

    @staticmethod
    def _feed(proc, todo, results) -> None:
        try:
            _recv(proc.stdout, _READY)
        except Exception:
            return                                   # helper did not start: it takes no work
        results.put(("ready", None))
        while True:
            try:
                job = todo.get_nowait()
            except queue.Empty:
                return
            try:
                _send(proc.stdin, _JOB, job)
            except Exception:
                todo.put(job)                         # this helper is gone: the part goes to another one
                return
            mid = job[0]
            del job[1:]                               # free the part copy while it is being meshed
            try:
                reply = _recv(proc.stdout, _RESULT)
            except Exception as exc:
                results.put(("lost", (mid, str(exc) or "helper stopped")))
                return
            results.put(("ok", reply))

    def close(self) -> None:
        for p in self.procs:
            try:
                p.stdin.close()
            except Exception:
                pass
        end = time.time() + 3.0
        for p in self.procs:
            try:
                p.wait(timeout=max(0.1, end - time.time()))
            except Exception:
                p.kill()
            for s in (p.stdout,):
                try:
                    s.close()
                except Exception:
                    pass


def _part_blob(occ, shape) -> bytes:
    buf = io.BytesIO()
    occ["BinTools"].Write_s(shape, buf, False, False, occ["BinTools_FormatVersion"].BinTools_FormatVersion_CURRENT)
    return buf.getvalue()


# --------------------------------------------------------------------------
# Main reader
# --------------------------------------------------------------------------

def read_step(path: str, out_dir: str, quality: str = "normal", workers: int | None = None) -> dict:
    """``workers``: helper processes for meshing; None = automatic (all cores but one, big files only)."""
    if workers is None:
        workers = worker_count()
        if os.path.getsize(path) < PARALLEL_MIN_BYTES and not os.environ.get("FRESING_IMPORT_WORKERS"):
            workers = 0
    helpers = _Helpers(workers) if workers >= 2 else None
    try:
        return _read_step(path, out_dir, quality, helpers)
    finally:
        if helpers is not None:
            helpers.close()


def _read_step(path: str, out_dir: str, quality: str, helpers: "_Helpers | None") -> dict:
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
    # so small parts (bolts) stay smooth next to big frames. With helper processes every
    # core meshes its own part; OpenCascade also uses all cores within a big part.
    shapes = [occ["XCAFDoc_ShapeTool"].GetShape_s(label) for label in mesh_labels]
    face_colours = [_face_colour_list(occ, shapes[mid], _face_colors(occ, stool, ctool, label))
                    for mid, label in enumerate(mesh_labels)]
    results: list = [None] * len(mesh_labels)       # (mesh result, axes, axis faces, error)
    counter = [0]
    where = [""]

    def store(reply) -> None:
        mid, res, ax, af, err = reply
        results[mid] = (res, ax, af, err)
        counter[0] += 1
        done = counter[0]
        if done % 10 == 1 or done == total:
            emit("mesh", 30 + 65 * done / total, f"Meshing part {done} of {total}{where[0]}")

    used_helpers = 0
    t_copy = 0.0
    if helpers is not None and helpers.procs and len(mesh_labels) >= 2:
        tc = time.time()
        jobs, pending = [], []
        for mid in range(len(shapes)):
            try:
                jobs.append([mid, _part_blob(occ, shapes[mid]), face_colours[mid], lin_rel, ang])
            except Exception:                           # (out of memory...) this part is meshed here instead
                pending.append(mid)
        jobs.sort(key=lambda j: -len(j[1]))            # biggest parts first: no core waits at the end
        t_copy = time.time() - tc
        where[0] = f" on {len(helpers.procs)} cores"
        retry = []

        def from_helper(reply) -> None:
            if reply[4] is not None:                    # failed in a helper (e.g. memory while all cores
                retry.append(reply[0])                  # were busy): try it again here, on its own
            else:
                store(reply)

        lost, left = helpers.run(jobs, from_helper)
        used_helpers = helpers.started
        del jobs
        for mid, reason in lost:                        # OpenCascade stopped on this part: skip it, keep the rest
            store((mid, None, [], [], f"the mesher stopped on this part ({reason})"))
        pending = sorted(pending + retry + [job[0] for job in left])   # left: no helper could take these
        where[0] = ""
    else:
        pending = list(range(len(mesh_labels)))
    for mid in pending:
        axes = _Axes()
        try:
            res = _mesh_shape(occ, shapes[mid], lin_rel, ang, face_colours[mid], axes=axes)
            store((mid, res, axes.axes, axes.faces, None))
        except Exception as exc:  # keep going, report the part
            store((mid, None, [], [], str(exc)))

    for mid in range(len(mesh_labels)):
        res, ax, af, err = results[mid]
        if err:
            emit("warning", 95, f"Could not mesh {mesh_names[mid]}: {err}")
        meta = {"name": mesh_names[mid], "tris": 0, "palette": [], "bbox": None,
                "axes": ax if res is not None else [], "axis_faces": af if res is not None else []}
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
            "mesh_helpers": used_helpers,
            "seconds_copy": round(t_copy, 1),
            "seconds_total": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(out_dir, "tree.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    emit("done", 100, "Import finished", stats=info["stats"])
    return info


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _no_crash_dialog()
    if argv[:1] == ["--worker"]:
        return worker_main(int(argv[1]))
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
