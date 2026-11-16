"""Face data for measuring in the web 3D page (task 0135), no Blender.

The page measures on the CAD faces a visitor clicks: a flat face is a plane (normal, offset), a round face an axis
(point, direction) with its own radius. The importer keeps a part's CAD faces as blocks of triangles
(``fr_face_starts``) and the axes of its round faces (``fr_axes`` / ``fr_axis_faces``: faces on one axis line
share ONE axis that carries the largest radius of them, task 0122) – the radius of the clicked face is worked out
here again from its own points.

What a mesh carries in the file (``pack``): two arrays, kept as accessors the page reads once –

* **runs** (uint32, pairs): ``(first triangle, face row)`` in the order the mesh's triangles are written (its
  primitives one after the other); a run lasts until the next one starts. Row ``NONE`` = no face data (a free-form
  face: the page measures from the clicked point only).
* **rows** (float32, ``ROW`` numbers each): ``kind, a, b, c, d, e, f, g`` in the mesh's own coordinates as written
  (16-bit points: ``(x - centre) / step``; the page's matrix of that mesh brings them to the world):

  - ``FLAT``  (1): normal ``a b c`` (unit), ``d`` = normal · point on the face.
  - ``ROUND`` (2): a point on the axis ``a b c``, its direction ``d e f`` (unit), radius ``g`` (a cylinder).
  - ``AXIS``  (3): as ROUND without a single radius (a cone, a torus, a fillet round an axis): centre to centre
    works, no diameter (``g`` = 0).

Measured cost: see the task 0135 report (``cost``).
"""

from __future__ import annotations

import numpy as np

FLAT, ROUND, AXIS = 1, 2, 3
ROW = 8
NONE = 0xFFFFFFFF
FLAT_MM = 0.005          # mm: a flat CAD face's points lie on one plane (+ 1e-6 of its size)
ROUND_SHARE = 0.002      # a cylinder's points lie on one radius (+ 0.005 mm); more spread: a cone or a torus


def face_of_triangles(n_tri: int, starts) -> np.ndarray:
    """CAD face number of each of ``n_tri`` triangles from ``fr_face_starts`` (the first triangle of every face,
    plus the total at the end). -1 where the starts do not cover a triangle."""
    s = np.asarray(starts, np.int64).ravel()
    out = np.full(n_tri, -1, np.int64)
    if len(s) < 2 or n_tri == 0:
        return out
    f = np.searchsorted(s, np.arange(n_tri), side="right") - 1
    ok = (f >= 0) & (f < len(s) - 1) & (np.arange(n_tri) < s[-1])
    out[ok] = f[ok]
    return out


def classify(points: np.ndarray, tri: np.ndarray, face: np.ndarray, axes=None, axis_faces=None) -> dict:
    """{CAD face number: row (ROW floats)} for the flat and round faces of one mesh.

    ``points`` (n, 3) in metres (the mesh's own coordinates), ``tri`` (m, 3) point numbers of each triangle,
    ``face`` (m) CAD face of each triangle (``face_of_triangles``), ``axes`` the flat ``fr_axes`` list (7 per
    axis), ``axis_faces`` the flat ``fr_axis_faces`` list (first triangle, count, axis number)."""
    p = np.asarray(points, np.float64)
    tri = np.asarray(tri, np.int64).reshape(-1, 3)
    face = np.asarray(face, np.int64)
    rows: dict = {}
    if not len(tri):
        return rows
    ax = np.asarray(axes if axes is not None else [], np.float64).reshape(-1, 7)
    af = np.asarray(axis_faces if axis_faces is not None else [], np.int64).reshape(-1, 3)
    round_of: dict = {}                                       # face -> axis number
    for start, count, k in af:
        if 0 <= k < len(ax) and 0 <= start < len(face):
            f = int(face[start])
            if f >= 0:
                round_of[f] = int(k)
    order = np.argsort(face, kind="stable")
    fs = face[order]
    cut = np.flatnonzero(np.diff(fs)) + 1
    for block in np.split(order, cut):
        f = int(face[block[0]])
        if f < 0:
            continue
        idx = np.unique(tri[block].ravel())
        v = p[idx]
        if f in round_of:
            a = ax[round_of[f]]
            o, d = a[0:3], a[3:6] / (np.linalg.norm(a[3:6]) or 1.0)
            rel = v - o
            dist = np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)
            r = float(np.median(dist))
            kind = ROUND if float(dist.max() - dist.min()) <= ROUND_SHARE * r + FLAT_MM * 1e-3 else AXIS
            rows[f] = [float(kind), *o.tolist(), *d.tolist(), r if kind == ROUND else 0.0]
            continue
        a, b, c = p[tri[block, 0]], p[tri[block, 1]], p[tri[block, 2]]
        cr = np.cross(b - a, c - a)
        n = cr.sum(axis=0)
        ln = float(np.linalg.norm(n))
        area2 = float(np.linalg.norm(cr, axis=1).sum())
        if ln <= 1e-12 or ln < 0.999 * area2:                # the triangles do not all face one way
            continue
        n = n / ln
        dd = v @ n
        size = float(np.ptp(v, axis=0).max()) if len(v) else 0.0
        if float(dd.max() - dd.min()) <= FLAT_MM * 1e-3 + 1e-6 * size:
            rows[f] = [float(FLAT), *n.tolist(), float(dd.mean()), 0.0, 0.0, 0.0]
    return rows


def to_written(rows: dict, centre=None, step: float | None = None) -> dict:
    """The rows in the coordinates the mesh is written in: 16-bit points ``(x - centre) / step``."""
    if centre is None or not step:
        return rows
    c = np.asarray(centre, np.float64)
    out = {}
    for f, r in rows.items():
        r = list(r)
        if int(r[0]) == FLAT:
            r[4] = (r[4] - float(np.dot(r[1:4], c))) / step
        else:
            r[1:4] = ((np.asarray(r[1:4]) - c) / step).tolist()
            r[7] = r[7] / step
        out[f] = r
    return out


def pack(face_per_primitive: list[np.ndarray], rows: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """(runs uint32 (k, 2), rows float32 (j, ROW)) of one mesh: ``face_per_primitive`` the CAD face of each
    triangle of each primitive in the order written. None when no triangle has face data."""
    face = np.concatenate([np.asarray(f, np.int64) for f in face_per_primitive]) if face_per_primitive else \
        np.zeros(0, np.int64)
    used = sorted(f for f in rows if f in set(face.tolist()))
    if not used:
        return None
    row_of = {f: i for i, f in enumerate(used)}
    lut = np.full(int(face.max()) + 2 if len(face) else 1, NONE, np.int64)
    for f, i in row_of.items():
        lut[f] = i
    rid = np.where(face >= 0, lut[np.clip(face, 0, len(lut) - 1)], NONE)
    change = np.flatnonzero(np.r_[True, rid[1:] != rid[:-1]])
    runs = np.stack([change, rid[change]], axis=1).astype(np.uint32)
    table = np.asarray([rows[f] for f in used], np.float32).reshape(-1, ROW)
    return runs, table


def row_at(runs: np.ndarray, table: np.ndarray, triangle: int):
    """The row of a written triangle (the page does the same): None for a face without data."""
    k = int(np.searchsorted(runs[:, 0], triangle, side="right")) - 1
    if k < 0 or int(runs[k, 1]) == NONE:
        return None
    return table[int(runs[k, 1])]


def write(gltf, faces: dict) -> int:
    """Put every mesh's (runs, rows) into ``gltf`` (core.web3d.Gltf) as two accessors each, named in the file's own
    extras: ``extras.fr_faces = {version, row, meshes: {mesh number: [runs, rows]}}``. Meshes that share one pair
    (a baked copy of a mesh) share its accessors. Returns the bytes added (before compression)."""
    from . import web3d as core
    if not faces:
        return 0
    acc: dict = {}
    out: dict = {}
    for k, (runs, rows) in sorted(faces.items()):
        key = id(runs)
        if key not in acc:
            acc[key] = [gltf.accessor(np.asarray(runs, np.uint32).ravel(), "SCALAR", core.UINT, pack=True),
                        gltf.accessor(np.asarray(rows, np.float32).ravel(), "SCALAR", core.FLOAT, pack=True)]
        out[str(int(k))] = acc[key]
    gltf.doc.setdefault("extras", {})["fr_faces"] = {"version": 1, "row": ROW, "meshes": out}
    return cost(list({id(r): (r, t) for r, t in faces.values()}.values()))


def read(data: bytes) -> dict:
    """{mesh number: (runs (k, 2) uint32, rows (j, ROW) float32)} of a ``.glb`` (tests, the PC check)."""
    from . import web3d as core
    doc, binary = core.read_glb(data)
    fx = (doc.get("extras") or {}).get("fr_faces") or {}
    out = {}
    for k, (ra, ta) in (fx.get("meshes") or {}).items():
        out[int(k)] = (core.accessor_array(doc, binary, ra).reshape(-1, 2).astype(np.uint32),
                       core.accessor_array(doc, binary, ta).reshape(-1, ROW).astype(np.float32))
    return out


def cost(meshes: list[tuple[np.ndarray, np.ndarray]]) -> int:
    """Bytes the face data adds to a file (before compression): runs and rows of every mesh."""
    return int(sum(r.nbytes + t.nbytes for r, t in meshes))
