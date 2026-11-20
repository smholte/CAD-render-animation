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

* **edges** (float32, task 0219): the CAD edges where two faces meet, found in the mesh (``edges``: mesh edges that
  two faces share, chained, fitted), one record after the other: ``kind, row a, row b`` (the face rows on both
  sides, -1 for a face without a row; an edge is kept only when one side has a row: the page finds it from the face
  under the pointer), then in the mesh's written coordinates:

  - ``LINE``   (4): 6 numbers – its two ends ``a b c``, ``d e f`` (a straight edge: two flat faces, a flat face and a
    cylinder along its axis …).
  - ``CIRCLE`` (5): 9 numbers – centre ``a b c``, the point where the arc starts ``d e f`` (the radius is its distance
    from the centre), the axis times the arc's angle ``g h i`` (right hand; 2π: a whole circle) – a hole's rim, where
    a rounding meets a flat face.

  ``unpack_edges`` gives them as rows of ``EROW`` numbers (a line's last three 0).

  Other edges (splines, an ellipse where a cylinder meets a tilted plane) are left out.

Measured cost: see the task 0135 report (``cost``); edges: the task 0219 report.
"""

from __future__ import annotations

import numpy as np

FLAT, ROUND, AXIS = 1, 2, 3
LINE, CIRCLE = 4, 5
ROW = 8
EROW = 12
EDGE_MM = 0.005          # mm: a fitted edge's points lie on its line / circle (+ 1e-6 of their distance from the
#                          origin, + 1/500 of the mean segment: the mesh's nodes lie ON the CAD edge, so this is tight)
NONE = 0xFFFFFFFF
FLAT_MM = 0.005          # mm: a flat CAD face's points lie on one plane (+ 1e-6 of its size)
ROUND_MM = 0.002         # mm: a cylinder's points lie on one radius (+ 32-bit rounding: 1e-6 of their distance
#                          from the part's origin); more spread: a cone or a torus (0.35 mm fillets, shallow cones)


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
            tol = ROUND_MM * 1e-3 + 1e-6 * float(np.abs(v).max())
            kind = ROUND if float(dist.max() - dist.min()) <= tol else AXIS
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


def _weld(p: np.ndarray, tol: float) -> np.ndarray:
    """A number per point, the same for points within about ``tol`` (the importer meshes every CAD face with its own
    points; the faces' points along a shared edge are the same nodes of that edge)."""
    q = np.floor(p / tol + 0.5).astype(np.int64)
    _u, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.ravel()


def _chains(seg: np.ndarray) -> list[np.ndarray]:
    """Connected pieces of a set of segments (k, 2) of point numbers: a list of segment index arrays."""
    parent: dict = {}

    def find(a):
        while parent.get(a, a) != a:
            parent[a] = parent.get(parent[a], parent[a])
            a = parent[a]
        return a
    for a, b in seg.tolist():
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([find(a) for a in seg[:, 0].tolist()])
    order = np.argsort(roots, kind="stable")
    cut = np.flatnonzero(np.diff(roots[order])) + 1
    return np.split(order, cut)


def fit_edge(pts: np.ndarray, seg: np.ndarray, tol: float):
    """A line or a circle through the points of one chain of segments: ``(LINE, a, b)``, ``(CIRCLE, centre, start,
    axis x angle)`` or None. ``pts`` (n, 3) the chain's points, ``seg`` (k, 2) its segments as numbers into ``pts``."""
    if len(pts) < 2:
        return None
    c0 = pts.mean(axis=0)
    rel = pts - c0
    _u, sv, vt = np.linalg.svd(rel, full_matrices=False)
    d = vt[0]
    t = rel @ d
    off = rel - np.outer(t, d)
    if float(np.linalg.norm(off, axis=1).max()) <= tol:
        return LINE, c0 + d * float(t.min()), c0 + d * float(t.max()), np.zeros(3)
    if len(pts) < 4:
        return None
    n = vt[2]
    if float(np.abs(rel @ n).max()) > tol:
        return None                                       # not in one plane
    e1, e2 = vt[0], vt[1]
    x, y = rel @ e1, rel @ e2                              # the circle in its plane: x² + y² + D x + E y + F = 0
    A = np.stack([x, y, np.ones_like(x)], axis=1)
    sol, *_ = np.linalg.lstsq(A, -(x * x + y * y), rcond=None)
    cx, cy = -sol[0] / 2, -sol[1] / 2
    r2 = cx * cx + cy * cy - sol[2]
    if r2 <= 0:
        return None
    r = float(np.sqrt(r2))
    rr = np.hypot(x - cx, y - cy)
    if float(np.abs(rr - r).max()) > tol or r > 1e3 * float(np.ptp(rel, axis=0).max() + tol):
        return None
    centre = c0 + e1 * cx + e2 * cy
    ang = np.arctan2(y - cy, x - cx)
    # how far round: a closed chain (every point on two segments) is a whole circle; else the largest gap
    deg = np.bincount(seg.ravel(), minlength=len(pts))
    axis = np.cross(e1, e2)
    if (deg == 2).all() and len(seg) == len(pts):
        start = pts[int(np.argmax(ang))]
        return CIRCLE, centre, start, axis * (2 * np.pi)
    a = np.sort(ang)
    gaps = np.diff(np.r_[a, a[0] + 2 * np.pi])
    k = int(np.argmax(gaps))
    first = a[(k + 1) % len(a)]
    sweep = 2 * np.pi - float(gaps[k])
    start = pts[int(np.argmin(np.abs(np.angle(np.exp(1j * (ang - first))))))]
    return CIRCLE, centre, start, axis * sweep


def edges(points: np.ndarray, tri: np.ndarray, face: np.ndarray, rows: dict) -> list:
    """The CAD edges between two faces of one mesh (task 0219): a list of ``(face a, face b, kind, p1, p2, p3)`` in
    the mesh's own coordinates (see the module's ``edges``), only where face a or b has a row (``classify``).

    A mesh edge is on a CAD edge when it borders a triangle of face a and one of face b (points welded); the
    segments of one pair of faces are cut into connected chains, each fitted with a line or a circle within a
    tolerance from the facet size (``EDGE_MM`` + 1/500 of the mean segment + 32-bit rounding). A chain that is
    neither (a spline, an ellipse) is left out."""
    p = np.asarray(points, np.float64)
    tri = np.asarray(tri, np.int64).reshape(-1, 3)
    face = np.asarray(face, np.int64)
    if not len(tri) or not rows:
        return []
    size = float(np.ptp(p, axis=0).max()) if len(p) else 0.0
    far = float(np.abs(p).max()) if len(p) else 0.0
    wid = _weld(p, max(1e-7, 2e-7 * far, 1e-6 * size))
    t = wid[tri]
    e = np.concatenate([t[:, (0, 1)], t[:, (1, 2)], t[:, (2, 0)]])
    ef = np.concatenate([face, face, face])
    e = np.sort(e, axis=1)
    keep = (e[:, 0] != e[:, 1]) & (ef >= 0)
    e, ef = e[keep], ef[keep]
    # an edge on a face's border: used once by that face
    key = np.stack([e[:, 0], e[:, 1], ef], axis=1)
    uk, cnt = np.unique(key, axis=0, return_counts=True)
    border = uk[cnt == 1]
    if not len(border):
        return []
    ek = border[:, 0] * (int(border[:, 1].max()) + 1) + border[:, 1]
    order = np.argsort(ek, kind="stable")
    border, ek = border[order], ek[order]
    _uk, at, cnt = np.unique(ek, return_index=True, return_counts=True)
    same = at[cnt == 2]                                    # exactly two faces on that edge
    fa = np.minimum(border[same, 2], border[same + 1, 2])
    fb = np.maximum(border[same, 2], border[same + 1, 2])
    seg = border[same, :2]
    has = np.array([int(a) in rows or int(b) in rows for a, b in zip(fa.tolist(), fb.tolist())], bool)
    fa, fb, seg = fa[has], fb[has], seg[has]
    if not len(seg):
        return []
    # one point per weld number (the first)
    first = np.full(int(wid.max()) + 1, -1, np.int64)
    first[wid[::-1]] = np.arange(len(wid))[::-1]
    pair = fa * (int(fb.max()) + 1) + fb
    order = np.argsort(pair, kind="stable")
    cut = np.flatnonzero(np.diff(pair[order])) + 1
    out = []
    for block in np.split(order, cut):
        a, b = int(fa[block[0]]), int(fb[block[0]])
        for ch in _chains(seg[block]):
            s = seg[block][ch]
            ids, local = np.unique(s, return_inverse=True)
            pts = p[first[ids]]
            mean_seg = float(np.linalg.norm(pts[local.reshape(-1, 2)[:, 0]] - pts[local.reshape(-1, 2)[:, 1]],
                                            axis=1).mean())
            tol = EDGE_MM * 1e-3 + 2e-3 * mean_seg + 1e-6 * far
            got = fit_edge(pts, local.reshape(-1, 2), tol)
            if got is not None:
                out.append((a, b, got[0], *[np.asarray(v, np.float64) for v in got[1:]]))
    return out


def edges_to_written(found: list, centre=None, step: float | None = None) -> list:
    """The edges in the coordinates the mesh is written in (as ``to_written``)."""
    if centre is None or not step:
        return found
    c = np.asarray(centre, np.float64)
    return [(a, b, kind, (p1 - c) / step, (p2 - c) / step, p3) for a, b, kind, p1, p2, p3 in found]


def row_numbers(face_per_primitive: list, rows: dict) -> dict:
    """{CAD face: its row number in ``pack``'s table}."""
    face = np.concatenate([np.asarray(f, np.int64) for f in face_per_primitive]) if face_per_primitive else \
        np.zeros(0, np.int64)
    present = set(np.unique(face).tolist())
    return {f: i for i, f in enumerate(sorted(f for f in rows if f in present))}


def pack_edges(found: list, row_of: dict) -> np.ndarray | None:
    """The edge records (float32, one after the other): ``kind, row a, row b`` + 6 numbers (a line) or 9 (a circle;
    the axis x angle is the same in written coordinates); None without edges."""
    flat: list = []
    for a, b, kind, p1, p2, p3 in found:
        ra, rb = row_of.get(a, -1), row_of.get(b, -1)
        if ra < 0 and rb < 0:
            continue
        flat += [float(kind), float(ra), float(rb), *np.asarray(p1).tolist(), *np.asarray(p2).tolist()]
        if kind == CIRCLE:
            flat += np.asarray(p3).tolist()
    return np.asarray(flat, np.float32) if flat else None


def unpack_edges(flat) -> np.ndarray:
    """The records of ``pack_edges`` as rows of ``EROW`` numbers (a line's last three 0)."""
    flat = np.asarray(flat, np.float32).ravel()
    out, i = [], 0
    while i + 9 <= len(flat):
        n = 12 if int(round(float(flat[i]))) == CIRCLE else 9
        out.append(np.r_[flat[i:i + n], np.zeros(12 - n, np.float32)])
        i += n
    return np.asarray(out, np.float32).reshape(-1, EROW)


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
    row_of = row_numbers(face_per_primitive, rows)
    used = sorted(row_of, key=row_of.get)
    if not used:
        return None
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
    for k, got in sorted(faces.items()):
        runs, rows = got[0], got[1]
        key = id(runs)
        if key not in acc:
            acc[key] = [gltf.accessor(np.asarray(runs, np.uint32).ravel(), "SCALAR", core.UINT, pack=True),
                        gltf.accessor(np.asarray(rows, np.float32).ravel(), "SCALAR", core.FLOAT, pack=True)]
            if len(got) > 2 and got[2] is not None and len(got[2]):          # task 0219: the edges
                acc[key].append(gltf.accessor(np.asarray(got[2], np.float32).ravel(), "SCALAR", core.FLOAT,
                                              pack=True))
        out[str(int(k))] = acc[key]
    gltf.doc.setdefault("extras", {})["fr_faces"] = {"version": 1, "row": ROW, "meshes": out}
    return cost(list({id(v[0]): v for v in faces.values()}.values()))


def read(data: bytes) -> dict:
    """{mesh number: (runs (k, 2) uint32, rows (j, ROW) float32)} of a ``.glb`` (tests, the PC check)."""
    from . import web3d as core
    doc, binary = core.read_glb(data)
    fx = (doc.get("extras") or {}).get("fr_faces") or {}
    out = {}
    for k, acc in (fx.get("meshes") or {}).items():
        out[int(k)] = (core.accessor_array(doc, binary, acc[0]).reshape(-1, 2).astype(np.uint32),
                       core.accessor_array(doc, binary, acc[1]).reshape(-1, ROW).astype(np.float32))
    return out


def read_edges(data: bytes) -> dict:
    """{mesh number: edges (k, EROW) float32, see ``unpack_edges``} of a ``.glb`` (task 0219; meshes without edges are
    left out)."""
    from . import web3d as core
    doc, binary = core.read_glb(data)
    fx = (doc.get("extras") or {}).get("fr_faces") or {}
    out = {}
    for k, acc in (fx.get("meshes") or {}).items():
        if len(acc) > 2:
            out[int(k)] = unpack_edges(core.accessor_array(doc, binary, acc[2]))
    return out


def cost(meshes: list) -> int:
    """Bytes the face data adds to a file (before compression): runs, rows and edges of every mesh."""
    return int(sum(sum(np.asarray(a).nbytes for a in m if a is not None) for m in meshes))
