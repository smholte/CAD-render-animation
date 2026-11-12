"""Milling: the bit takes material away from the workpiece (task 0027). No Blender here.

How it works
------------
* The **bit** is a solid of revolution: a profile (radius over height, from the tip up) turned
  about its axis. The profile comes from the bit's own shape (flat, ball, corner radius, V, drill
  are recognised; anything else is used as it is) or from the numbers the owner types in.
* The **path** is the bit's tip and axis in the workpiece's own coordinates, sampled at every frame
  of the animation (and between frames where the move is curved). The workpiece may move too (a
  table that slides): the path is relative to it.
* Samples that lie on one straight line with the bit's axis unchanged form one **segment**. The
  volume a convex bit sweeps along a straight segment is exactly the convex hull of the bit at both
  ends, so one boolean per segment is enough - not one per frame. A slot of 200 frames is one cut.
* The **workpiece** is the stock minus every finished segment (a mesh boolean with the Manifold
  library, the same library as Blender's "Manifold" boolean solver), minus the part of the segment
  the bit is in right now. Exact, sharp edges like the CAD part, in any direction (ready for 4/5
  axes: tilted moves just give shorter segments).
* The stock is cut into **tiles** once a piece gets big, so a cut only touches the tiles it
  reaches and costs the same at the end of a long program as at the start.
* **Finish at the CAD part** (optional): every cut first loses the finished part's volume, so the
  material never goes below the CAD part's surface, even if the motion is a little too deep.
* States at segment boundaries are kept (checkpoints), so scrubbing backwards is quick. Every state
  is made by the same steps in the same order from the stock, so going back and forth always gives
  exactly the same mesh.
* **Which move made a face** (tool marks, task 0061): every solid a cut takes away has its own Manifold id, and
  Manifold keeps that id on the faces the cut leaves, through every later cut. ``Timeline.moves`` has one row per
  straight move; ``mesh_at(T, moves=True)`` names for each triangle the row of the move that made it last, and
  ``mark_faces`` turns that into what the cut-face material reads (``core/toolmarks.py`` is the contract).

Units: metres (Blender's), angles of tips in degrees.
"""

from __future__ import annotations

import math
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

import numpy as np

from . import toolmarks as _tm

MM = 0.001

try:                                       # bundled with the app (wheel in the extension)
    import manifold3d as _mf
except Exception:                          # pragma: no cover - only without the wheel
    _mf = None


def available() -> bool:
    return _mf is not None


# ---------------------------------------------------------------------------
# detail levels
# ---------------------------------------------------------------------------

# seg: corners of the bit's circle; tol: a sample this far off the line starts a new segment;
# tile: a piece of the workpiece with more triangles than this is cut in two
DETAIL = {
    "FINE": {"seg": 64, "tol": 0.002 * MM, "tile": 30000, "label": "Fine"},
    "NORMAL": {"seg": 40, "tol": 0.005 * MM, "tile": 20000, "label": "Normal"},
    "FAST": {"seg": 24, "tol": 0.01 * MM, "tile": 12000, "label": "Fast"},
}
ANGLE_TOL = math.radians(0.05)            # the bit's axis may turn this much within one straight segment
# … while a rotary axis turns the part (task 0066): the tip's chord still keeps to the detail level's tolerance, but
# the bit's axis may turn this much in one cut (a 4th-axis turn would otherwise be cut in 0.05° slices)
TURN_ANGLE_TOL = math.radians(0.5)


def detail(name: str) -> dict:
    return DETAIL.get(name, DETAIL["NORMAL"])


# ---------------------------------------------------------------------------
# the bit
# ---------------------------------------------------------------------------

SHAPES = {
    "FLAT": "Flat end mill",
    "BALL": "Ball end mill",
    "BULL": "Corner radius end mill",
    "VEE": "V-bit / chamfer mill",
    "DRILL": "Drill",
    "CUSTOM": "Shape of the part",
}


@dataclass
class Tool:
    kind: str = "FLAT"
    radius: float = 5 * MM
    length: float = 40 * MM
    corner: float = 1 * MM                 # BULL: corner radius
    angle: float = 90.0                    # VEE / DRILL: included tip angle (degrees)
    profile: tuple = ()                    # CUSTOM: ((z, r), ...) from the tip up

    def key(self) -> tuple:
        return (self.kind, round(self.radius, 9), round(self.length, 9), round(self.corner, 9),
                round(self.angle, 6), tuple((round(z, 9), round(r, 9)) for z, r in self.profile))


def describe(tool: Tool) -> str:
    d = f"Ø{tool.radius * 2000:.1f} mm"
    if tool.kind == "BULL":
        d += f" R{tool.corner * 1000:.1f}"
    if tool.kind in ("VEE", "DRILL"):
        d += f" {tool.angle:.0f}°"
    return f"{SHAPES.get(tool.kind, tool.kind)} {d}, {tool.length * 1000:.0f} mm long"


def _arc(cz, cr, rad, a0, a1, n) -> list:
    """Points of an arc in the (z, r) plane around (cz, cr), angles from the +r direction towards -z."""
    out = []
    for k in range(n + 1):
        a = a0 + (a1 - a0) * k / n
        out.append((cz - rad * math.sin(a), cr + rad * math.cos(a)))
    return out


def tool_profile(tool: Tool, seg: int = 40) -> list:
    """(z, r) from the tip (z = 0) up to the top of the bit; r = 0 is a point on the axis."""
    R, L = max(tool.radius, 1e-5), max(tool.length, 1e-4)
    arc_n = max(3, seg // 4)
    if tool.kind == "BALL":
        r = min(R, L)
        pts = [(0.0, 0.0)] + [(r - r * math.cos(t), r * math.sin(t))
                              for t in np.linspace(0, math.pi / 2, arc_n + 1)[1:]]
        pts.append((L, R))
    elif tool.kind == "BULL":
        c = min(max(tool.corner, 0.0), R)
        if c <= 1e-7:
            pts = [(0.0, R), (L, R)]
        else:
            pts = [(c - c * math.cos(t), (R - c) + c * math.sin(t))
                   for t in np.linspace(0, math.pi / 2, arc_n + 1)]
            pts.append((L, R))
    elif tool.kind in ("VEE", "DRILL"):
        half = math.radians(min(max(tool.angle, 1.0), 179.0)) / 2
        h = R / math.tan(half)
        pts = [(0.0, 0.0), (min(h, L), R if h <= L else L * math.tan(half))]
        if h < L:
            pts.append((L, R))
    elif tool.kind == "CUSTOM" and len(tool.profile) >= 2:
        pts = [(float(z), float(r)) for z, r in tool.profile]
    else:
        pts = [(0.0, R), (L, R)]
    return _clean_profile(pts)


def _clean_profile(pts) -> list:
    out = []
    for z, r in pts:
        z, r = float(z), max(0.0, float(r))
        if out and abs(z - out[-1][0]) < 1e-9 and abs(r - out[-1][1]) < 1e-9:
            continue
        out.append((z, r))
    return out


def convex_pieces(profile: list) -> list:
    """Split a profile into pieces whose solid of revolution is convex (radius concave in height).

    Flat, ball, corner radius, V and drill bits are one piece. A bit whose shank is wider than its
    cutter (or a T-slot cutter) gets two or more; each piece is swept on its own."""
    if len(profile) < 2:
        return [profile]
    pieces, cur = [], [profile[0], profile[1]]

    def slope(a, b):
        dz = b[0] - a[0]
        dr = b[1] - a[1]
        if dz <= 1e-12:
            return math.inf if dr > 0 else (-math.inf if dr < 0 else 0.0)
        return dr / dz

    last = slope(profile[0], profile[1])
    for p in profile[2:]:
        s = slope(cur[-1], p)
        if s > last + 1e-9 and not (math.isinf(s) and math.isinf(last) and s == last):
            pieces.append(cur)
            cur = [cur[-1], p]
        else:
            cur.append(p)
        last = s
    pieces.append(cur)
    return pieces


def piece_points(piece: list, seg: int) -> np.ndarray:
    """Points of one convex piece in the bit's space (tip at the origin, axis +Z)."""
    a = np.linspace(0.0, 2.0 * math.pi, seg, endpoint=False)
    c, s = np.cos(a), np.sin(a)
    rings = []
    for z, r in piece:
        if r < 1e-9:
            rings.append(np.array([[0.0, 0.0, z]]))
        else:
            rings.append(np.stack([c * r, s * r, np.full(seg, z)], axis=1))
    return np.vstack(rings)


def basis(d) -> tuple:
    """Two unit vectors at right angles to ``d`` (the same ones every time for the same ``d``)."""
    d = np.asarray(d, dtype=float)
    ref = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(d, ref)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    return e1, e2


def place(points: np.ndarray, origin, d) -> np.ndarray:
    """Bit-space points -> workpiece space, tip at ``origin``, axis along ``d`` (unit)."""
    e1, e2 = basis(d)
    return (np.asarray(origin, float)[None, :] + points[:, :1] * e1[None, :] + points[:, 1:2] * e2[None, :]
            + points[:, 2:3] * np.asarray(d, float)[None, :])


class Cutter:
    """The bit's shape at one detail level, ready to sweep."""

    def __init__(self, tool: Tool, detail_name: str = "NORMAL"):
        self.tool = tool
        self.seg = detail(detail_name)["seg"]
        self.profile = tool_profile(tool, self.seg)
        self.pieces = [piece_points(p, self.seg) for p in convex_pieces(self.profile)]
        self.reach = max(max(r for _z, r in self.profile), 1e-6)
        self.length = max(z for z, _r in self.profile)

    def sweep(self, o0, o1, d):
        """The volume the bit fills moving straight from tip ``o0`` to tip ``o1`` (axis ``d``):
        (Manifold or None, bounding box (lo, hi))."""
        solids, lo, hi = [], None, None
        for pts in self.pieces:
            p = np.vstack([place(pts, o0, d), place(pts, o1, d)])
            plo, phi = p.min(axis=0), p.max(axis=0)
            lo = plo if lo is None else np.minimum(lo, plo)
            hi = phi if hi is None else np.maximum(hi, phi)
            h = _mf.Manifold.hull_points(p)
            if not h.is_empty():
                solids.append(h)
        if not solids:
            return None, (lo, hi)
        if len(solids) == 1:
            return solids[0], (lo, hi)
        return _mf.Manifold.batch_boolean(solids, _mf.OpType.Add), (lo, hi)


# ---------------------------------------------------------------------------
# recognising the bit from its shape
# ---------------------------------------------------------------------------

def axis_from_points(points: np.ndarray) -> tuple:
    """Main direction of a long thin part (its axis) through its centre."""
    c = points.mean(axis=0)
    _u, _s, vt = np.linalg.svd(points - c, full_matrices=False)
    return c, vt[0] / np.linalg.norm(vt[0])


MAX_LEVELS = 1500                 # heights at which the outline of a part is read (task 0040)


def profile_from_points(points: np.ndarray, origin, d, tris=None) -> tuple:
    """(z, r) outline of the part about the axis, z from its lowest point along ``d``.

    With ``tris`` (the mesh's triangles) the outline is the widest point of the part's *cross-section* at each
    height - also between vertices. That matters for fluted tools: on a helix the vertices at one height are often
    all in a flute, so the vertices alone gave a radius between the core and the outer diameter (0037: a fluted
    Ø12 end mill read as Ø10.4). Returns (profile, z_min, z_max) - z measured from ``origin`` along ``d``."""
    d = np.asarray(d, float) / np.linalg.norm(d)
    q = points - np.asarray(origin, float)[None, :]
    z = q @ d
    r = np.linalg.norm(q - z[:, None] * d[None, :], axis=1)
    zmin, zmax = float(z.min()), float(z.max())
    zz = np.round(z - zmin, 7)
    order = np.argsort(zz, kind="stable")
    zs, rs = zz[order], r[order]
    levels, starts = np.unique(zs, return_index=True)
    rmax = np.maximum.reduceat(rs, starts)
    if tris is not None and len(tris):
        t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
        # heights to read: where many vertices lie (flat faces, steps, rings: also just above and below them, so a
        # step stays sharp), an even spread (a plain cylinder has vertices only at its ends) and the ends
        counts = np.diff(np.append(starts, len(zs)))
        busy = levels[counts >= 3]
        if len(busy) > MAX_LEVELS // 3:
            busy = np.sort(busy[np.argsort(-counts[counts >= 3], kind="stable")[:MAX_LEVELS // 3]])
        top = float(levels[-1])
        n_even = int(min(MAX_LEVELS // 3, max(2, top / (0.05 * MM))))
        eps = 2e-6
        lv = np.concatenate([busy, busy - eps, busy + eps, np.linspace(0.0, top, n_even), levels[:1], levels[-1:]])
        if len(levels) <= MAX_LEVELS // 3:
            lv = np.concatenate([lv, levels])
        lv = np.unique(np.round(np.clip(lv, 0.0, top), 9))
        keep = np.searchsorted(levels, lv)
        hit = (keep < len(levels)) & (np.abs(levels[np.minimum(keep, len(levels) - 1)] - lv) < 1e-12)
        base = np.zeros(len(lv))
        base[hit] = rmax[keep[hit]]
        levels, rmax = lv, np.maximum(base, _section_radius(q, d, zmin, t, lv))
    prof = list(zip(levels.tolist(), rmax.tolist()))
    return _simplify(prof, 0.005 * MM), zmin, zmax


def _section_radius(q: np.ndarray, d: np.ndarray, zmin: float, tris: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """For each height: the largest distance from the axis of the points where the triangles' edges cross it.
    (Along a straight edge the distance from the axis is largest at an end, so these points give the widest
    point of the cross-section.)"""
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    z = q @ d - zmin
    za, zb = z[e[:, 0]], z[e[:, 1]]
    swap = za > zb
    e[swap] = e[swap][:, ::-1]
    za, zb = np.minimum(za, zb), np.maximum(za, zb)
    keep = zb - za > 1e-9
    e, za, zb = e[keep], za[keep], zb[keep]
    out = np.zeros(len(levels))
    i0 = np.searchsorted(levels, za, side="left")
    i1 = np.searchsorted(levels, zb, side="right")
    n = i1 - i0
    perp = q - (q @ d)[:, None] * d[None, :]
    CH = 400000
    k = 0
    while k < len(e):
        # a chunk of edges whose level crossings fit in memory
        cs = np.cumsum(n[k:])
        j = k + max(1, int(np.searchsorted(cs, CH)))
        sl = slice(k, j)
        cnt = n[sl]
        tot = int(cnt.sum())
        if tot:
            ei = np.repeat(np.arange(k, j), cnt)
            li = np.repeat(i0[sl] - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt) + np.arange(tot)
            f = (levels[li] - za[ei]) / (zb[ei] - za[ei])
            p = perp[e[ei, 0]] * (1 - f)[:, None] + perp[e[ei, 1]] * f[:, None]
            np.maximum.at(out, li, np.linalg.norm(p, axis=1))
        k = j
    return out


def _simplify(prof: list, tol: float) -> list:
    """Douglas-Peucker on the outline (keeps its ends)."""
    if len(prof) <= 2:
        return prof
    p = np.array(prof)
    keep = np.zeros(len(p), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(p) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = p[i], p[j]
        ab = b - a
        L = np.hypot(*ab)
        seg = p[i + 1:j] - a
        if L < 1e-12:
            dist = np.hypot(seg[:, 0], seg[:, 1])
        else:
            dist = np.abs(seg[:, 0] * ab[1] - seg[:, 1] * ab[0]) / L
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return [tuple(x) for x in p[keep].tolist()]


def classify(profile: list) -> Tool:
    """Recognise flat, ball, corner radius, V-bit and drill from an outline; otherwise CUSTOM."""
    prof = _clean_profile(profile)
    if len(prof) < 2:
        return Tool("CUSTOM", radius=1 * MM, length=1 * MM, profile=tuple(prof))
    Z = np.array([p[0] for p in prof])
    Rr = np.array([p[1] for p in prof])
    L = float(Z[-1])
    # the cutter's radius: where the outline stops growing for the first time
    i = 0
    while i + 1 < len(Rr) and Rr[i + 1] > Rr[i] + 1e-7 + 1e-5 * Rr.max():
        i += 1
    R, zR = float(Rr[i]), float(Z[i])
    # a little higher up the outline may still widen a few percent (a corner chamfer, a land of a fluted
    # cutter): the cutter's radius is the widest point close above (task 0040)
    win = (Z > zR) & (Z <= zR + max(0.5 * R, 0.5 * MM)) & (Rr <= 1.06 * R + 0.02 * MM)
    if np.any(win) and float(Rr[win].max()) > R:
        R = float(Rr[win].max())
        zR = float(Z[np.argmax(Rr >= R - max(0.002 * R, 0.002 * MM))])
    if R <= 1e-6:
        return Tool("CUSTOM", radius=float(Rr.max()), length=L, profile=tuple(prof))
    r0 = float(Rr[0])
    tol_r = max(0.02 * R, 0.01 * MM)

    def r_at(z):
        return float(np.interp(z, Z, Rr))

    cust = Tool("CUSTOM", radius=R, length=L, profile=tuple(prof))
    if zR <= max(0.01 * R, 0.005 * MM) and abs(r0 - R) <= tol_r:
        return Tool("FLAT", radius=R, length=L)
    # a flat bottom with a small chamfer or edge break on the corner (not a corner radius): a flat end mill
    if r0 >= 0.85 * R and zR <= max(0.08 * R, 0.05 * MM) and \
            abs(r_at(zR / 2) - (r0 + R) / 2) <= 0.25 * (R - r0) + 0.002 * MM:
        return Tool("FLAT", radius=R, length=L)
    if r0 <= tol_r:
        # ball: r(z) = sqrt(2 R z - z^2) up to z = R
        if abs(zR - R) <= 0.06 * R and all(abs(r_at(f * R) - math.sqrt(max(0.0, 2 * R * f * R - (f * R) ** 2)))
                                          <= 0.04 * R for f in (0.25, 0.5, 0.75)):
            return Tool("BALL", radius=R, length=L)
        # V / drill: r grows linearly to R
        if zR > 1e-6 and all(abs(r_at(f * zR) - f * R) <= 0.03 * R for f in (0.25, 0.5, 0.75)):
            angle = math.degrees(2 * math.atan2(R, zR))
            kind = "DRILL" if 112.0 <= angle <= 124.0 or 128.0 <= angle <= 142.0 else "VEE"
            return Tool(kind, radius=R, length=L, angle=round(angle, 1))
        return cust
    # corner radius: flat bottom of radius R - c, then a quarter circle of radius c
    c = R - r0
    if c > 0 and abs(zR - c) <= 0.08 * c + 0.002 * MM and \
            abs(r_at(c * (1 - math.cos(math.pi / 4))) - (r0 + c * math.sin(math.pi / 4))) <= 0.05 * c + 0.002 * MM:
        return Tool("BULL", radius=R, length=L, corner=c)
    return cust


# ---------------------------------------------------------------------------
# the path: straight segments
# ---------------------------------------------------------------------------

def find_segments(o: np.ndarray, d: np.ndarray, tol: float, angle_tol: float = ANGLE_TOL) -> list:
    """Split samples into straight runs: (first sample, last sample) pairs, end = next start.

    A run keeps going while every sample stays within ``tol`` of the line from its first to its
    current last sample, moves forwards along it, and the axis turns less than ``angle_tol`` (one angle, or one
    per sample: the run keeps to the smallest of its samples', task 0066)."""
    n = len(o)
    if n == 0:
        return []
    if n == 1:
        return [(0, 0)]
    per_sample = not np.isscalar(angle_tol)
    if per_sample:
        cos_each = np.cos(np.asarray(angle_tol, float).reshape(-1))
    cos_tol = math.cos(angle_tol) if not per_sample else 1.0
    segs = []
    i = 0
    while i < n - 1:
        def ok(k):
            a, b = o[i], o[k]
            lim = float(np.max(cos_each[i:k + 1])) if per_sample else cos_tol
            if np.min(d[i + 1:k + 1] @ d[i]) < lim:
                return False
            ab = b - a
            L = float(np.linalg.norm(ab))
            q = o[i:k + 1] - a
            if L < 1e-12:
                return float(np.max(np.linalg.norm(q, axis=1))) <= tol
            u = ab / L
            t = q @ u
            perp = np.linalg.norm(q - t[:, None] * u[None, :], axis=1)
            return float(perp.max()) <= tol and bool(np.all(np.diff(t) >= -tol))
        best, step = i + 1, 1
        while True:
            k = min(n - 1, best + step)
            if k == best:
                break
            if ok(k):
                best, step = k, step * 2
            elif step == 1:
                break
            else:
                step = 1
        segs.append((i, best))
        i = best
    return segs


# ---------------------------------------------------------------------------
# the workpiece
# ---------------------------------------------------------------------------

class SolidError(RuntimeError):
    pass


def solid_from_mesh(verts: np.ndarray, tris: np.ndarray, face_ids=None):
    """Manifold from triangles; coincident vertices of neighbouring CAD faces are joined first."""
    if _mf is None:
        raise SolidError("The Manifold library is missing")
    v = np.array(verts, dtype=np.float32).reshape(-1, 3)
    t = np.array(tris, dtype=np.uint32).reshape(-1, 3)
    kw = {}
    if face_ids is not None:
        kw["face_id"] = np.array(face_ids, dtype=np.uint32)
    mesh = _mf.Mesh(vert_properties=v, tri_verts=t, **kw)
    mesh.merge()
    m = _mf.Manifold(mesh)
    if m.status() != _mf.Error.NoError or m.is_empty():
        # second try: join vertices that are equal to 1 µm (some exporters leave tiny gaps)
        q = np.round(v.astype(np.float64) / 1e-6).astype(np.int64)
        _u, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
        mesh = _mf.Mesh(vert_properties=np.array(v[first], np.float32),
                        tri_verts=np.array(inv.reshape(-1)[t], np.uint32), **kw)
        m = _mf.Manifold(mesh)
        if m.status() != _mf.Error.NoError or m.is_empty():
            raise SolidError("not a closed solid")
    return m


@dataclass
class Tile:
    lo: np.ndarray
    hi: np.ndarray
    solid: object                 # Manifold
    keep: object = None           # the finished part inside this tile (Manifold) or None
    ntri: int = 0


def _box(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return _mf.Manifold.cube(tuple((hi - lo).tolist())).translate(tuple(lo.tolist()))


class Workpiece:
    """The stock (and the optional finished part) as solids, and how a cut changes them."""

    def __init__(self, stock, finished=None, detail_name: str = "NORMAL"):
        self.stock = stock
        # the id Manifold gave the stock's triangles: kept through every cut, so uncut faces keep their CAD face
        # (``original_id()`` is -1 for a solid made from a mesh – every face then counted as cut, task 0051)
        runs = np.asarray(stock.to_mesh().run_original_id)
        self.stock_id = int(runs[0]) if len(runs) == 1 else stock.original_id()
        self.tile_max = detail(detail_name)["tile"]
        b = stock.bounding_box()
        pad = 1e-4
        self.lo, self.hi = np.array(b[:3]) - pad, np.array(b[3:]) + pad
        keep = None
        if finished is not None and not finished.is_empty():
            keep = finished ^ stock          # only what lies inside the stock
            if keep.is_empty():
                keep = None
        self.first = (Tile(self.lo.copy(), self.hi.copy(), stock, keep, stock.num_tri()),)
        # {Manifold id of a solid a cut took away: the tag given with that cut} (task 0061). A timeline keeps a
        # dict of its own (``Timeline.cut_ids``): this one is for cuts made without one
        self.cut_ids: dict = {}

    def touches(self, lo, hi) -> bool:
        return bool(np.all(hi >= self.lo) and np.all(lo <= self.hi))

    def cut(self, tiles: tuple, cutter, lo, hi, tag=None, ids: dict | None = None) -> tuple:
        """``tiles`` minus ``cutter`` (bounding box lo..hi). Tiles it does not reach stay the same objects.

        ``tag`` (the move's row, a whole number): the faces this cut leaves can be found again – the solid taken
        away gets one Manifold id of its own, written into ``ids`` (default ``self.cut_ids``) as id -> tag."""
        out = []
        changed = False
        if tag is not None:
            ids = self.cut_ids if ids is None else ids
            if cutter.original_id() < 0:       # made of several pieces: one id for the whole bit
                cutter = cutter.as_original()
        for t in tiles:
            if t.ntri == 0 or np.any(hi < t.lo) or np.any(lo > t.hi):
                out.append(t)
                continue
            c = cutter
            if t.keep is not None:
                c = cutter - t.keep
                if tag is not None:            # trimmed by the finished part: its faces would keep two ids
                    c = c.as_original()
            if tag is not None:
                ids[c.original_id()] = tag
            s = t.solid - c
            n = s.num_tri()
            changed = True
            nt = Tile(t.lo, t.hi, s, t.keep, n)
            if n > self.tile_max:
                out.extend(self._split(nt))
            else:
                out.append(nt)
        return tuple(out) if changed else tiles

    def _split(self, t: Tile) -> list:
        size = t.hi - t.lo
        ax = int(np.argmax(size))
        if size[ax] < 4 * MM:
            return [t]
        # a little off the middle, so the seam does not fall on the round numbers CAM programs use
        at = float(t.lo[ax] + size[ax] * 0.5137)
        n = np.zeros(3)
        n[ax] = 1.0
        upper, lower = t.solid.split_by_plane(tuple(n.tolist()), at)
        ku = kl = None
        if t.keep is not None:
            ku, kl = t.keep.split_by_plane(tuple(n.tolist()), at)
            ku = None if ku.is_empty() else ku
            kl = None if kl.is_empty() else kl
        hi_l, lo_u = t.hi.copy(), t.lo.copy()
        hi_l[ax] = at
        lo_u[ax] = at
        out = []
        for lo, hi, s, k in ((t.lo, hi_l, lower, kl), (lo_u, t.hi, upper, ku)):
            out.append(Tile(lo, hi, s, k, s.num_tri()))
        return out

    def mesh(self, tiles: tuple, cache: dict | None = None, moves: bool = False, ids: dict | None = None) -> tuple:
        """(verts float32 (n, 3), tris int32 (m, 3), source int32 (m,)): source is the stock's face
        (the number given as face id) for uncut surfaces, -1 for surfaces the bit made.

        ``moves=True``: a fourth array, int32 (m,): the tag of the cut that made the triangle last (``cut``'s
        ``tag``, looked up in ``ids``, default ``self.cut_ids``); -1 for the stock's own faces and for faces
        nobody knows the maker of (where a tile was split in two)."""
        rows = self.tile_meshes(tiles, cache, ids)
        return self.joined(rows, moves)

    def tile_meshes(self, tiles: tuple, cache: dict | None = None, ids: dict | None = None) -> list:
        """One row per tile that has triangles: ``[solid, verts, tris, source, move, marks]`` (the tile's own
        vertex numbers; ``marks`` is None until ``Timeline.mesh_at`` fills it in). Rows are kept in ``cache``.
        After these six a row has the tile's corner normals (None until asked for) and its box (lo, hi)."""
        ids = self.cut_ids if ids is None else ids
        rows = []
        for t in tiles:
            if t.ntri == 0:
                continue
            key = id(t.solid)
            hit = cache.get(key) if cache is not None else None
            if hit is None or hit[0] is not t.solid:
                hit = [t.solid, *self._tile_arrays(t.solid, ids), None, None, t.lo, t.hi]
                if cache is not None:
                    cache[key] = hit
            rows.append(hit)
        return rows

    @staticmethod
    def joined(rows: list, moves: bool = False) -> tuple:
        """The rows of ``tile_meshes`` as one mesh: (verts, tris, source) and, with ``moves``, the move."""
        if not rows:
            out = (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32), np.zeros(0, np.int32))
            return out + (np.zeros(0, np.int32),) if moves else out
        if len(rows) == 1:
            _s, v, tr, src, mv = rows[0][:5]
            return (v, tr, src, mv) if moves else (v, tr, src)
        off = np.cumsum([0] + [len(r[1]) for r in rows[:-1]])
        out = (np.concatenate([r[1] for r in rows]), np.concatenate([r[2] + o for r, o in zip(rows, off)]),
               np.concatenate([r[3] for r in rows]))
        return out + (np.concatenate([r[4] for r in rows]),) if moves else out

    def _tile_mesh(self, solid) -> tuple:
        return self._tile_arrays(solid, None)[:3]

    def _tile_arrays(self, solid, ids: dict | None) -> tuple:
        """(verts, tris, source, move) of one solid; ``move`` is -1 everywhere without ``ids``."""
        m = solid.to_mesh()
        v = np.array(m.vert_properties[:, :3], dtype=np.float32)
        tr = np.array(m.tri_verts, dtype=np.int32)
        src = np.full(len(tr), -1, dtype=np.int32)
        mv = np.full(len(tr), -1, dtype=np.int32)
        ri, rid = np.asarray(m.run_index), np.asarray(m.run_original_id)
        fid = np.asarray(m.face_id)
        for k in range(len(rid)):
            a, b = int(ri[k]) // 3, int(ri[k + 1]) // 3
            if int(rid[k]) == self.stock_id:
                src[a:b] = fid[a:b]
            elif ids:
                mv[a:b] = ids.get(int(rid[k]), -1)
        return v, tr, src, mv


# ---------------------------------------------------------------------------
# the timeline: what the workpiece looks like at any frame
# ---------------------------------------------------------------------------

@dataclass
class Path:
    """One bit's tip (o) and axis (d) in the workpiece's coordinates at times t (frames)."""
    t: np.ndarray
    o: np.ndarray
    d: np.ndarray
    angle_tol: object = None      # per sample (radians) where the part turns (task 0066); None: ANGLE_TOL

    def __post_init__(self):
        self.t = np.asarray(self.t, float).reshape(-1)
        self.o = np.asarray(self.o, float).reshape(-1, 3)
        self.d = np.asarray(self.d, float).reshape(-1, 3)
        n = np.linalg.norm(self.d, axis=1)
        n[n < 1e-12] = 1.0
        self.d = self.d / n[:, None]


@dataclass
class _Seg:
    bit: int
    i0: int
    i1: int
    t0: float
    t1: float
    cuts: bool = True
    order: int = 0


@dataclass
class Stats:
    ops: int = 0                  # booleans done
    seconds: float = 0.0
    last_ms: float = 0.0
    triangles: int = 0
    tiles: int = 1
    segments: int = 0
    cutting_segments: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class Moves:
    """The straight moves of a timeline, one row per move (row = its place in end-time order, ``_Seg.order``):
    what the tool marks on a cut face are worked out from (task 0061). Metres, frames."""
    bit: np.ndarray               # (n,) int32: which bit (index into the timeline's cutters and paths)
    o0: np.ndarray                # (n, 3) the tip at the move's start
    o1: np.ndarray                # (n, 3) ... and at its end
    d: np.ndarray                 # (n, 3) the tool's axis, unit, from the tip up into the tool
    t0: np.ndarray                # (n,) frames
    t1: np.ndarray
    dist: np.ndarray              # (n,) how far the same bit had cut sideways (across its axis) before this move
    per_tooth: np.ndarray         # (n,) feed per tooth: the distance between two marks of the bit's side or bottom
    per_rev: np.ndarray           # (n,) feed per turn of the spindle
    cuts: np.ndarray              # (n,) bool: the move comes near the workpiece
    owner: np.ndarray             # (n,) int32: the row whose marks this move's faces show: its own; for a move
    #                               straight back out of the cut and for standing still the move before; for a
    #                               plunge the sideways move that starts at its bottom
    step: np.ndarray = None       # (n,) the step-down: how much deeper a level sideways move runs than the nearest
    #                               pass of the same bit above it that it runs along (0: none); the line on a wall
    tables: dict = field(default_factory=dict, repr=False)      # what ``mark_faces`` worked out per move

    def __len__(self) -> int:
        return len(self.bit)


class Timeline:
    """The workpiece at any time of the animation, for a set of bits and their paths."""

    KEEP_SECONDS = 0.25           # keep a state after this much boolean work (scrubbing back costs at most this)
    MEMORY_BUDGET = 256e6         # bytes for the kept states (a triangle costs about BYTES_PER_TRIANGLE)
    BYTES_PER_TRIANGLE = 250      # measured: Manifold keeps ~250 bytes per triangle
    IDS_MAX = 300000              # ids of cuts remembered (``cut_ids``) before everything kept is made again

    def __init__(self, workpiece: Workpiece, cutters: list, paths: list, detail_name: str = "NORMAL"):
        self.wp = workpiece
        self.cutters = cutters
        self.paths = paths
        self.tol = detail(detail_name)["tol"]
        segs = []
        self.bit_segs: list[list[_Seg]] = []
        for b, (cut, p) in enumerate(zip(cutters, paths)):
            mine = []
            for i0, i1 in find_segments(p.o, p.d, self.tol,
                                        ANGLE_TOL if p.angle_tol is None else p.angle_tol):
                s = _Seg(b, i0, i1, float(p.t[i0]), float(p.t[i1]))
                s.cuts = self._may_cut(cut, p, i0, i1)
                mine.append(s)
            self.bit_segs.append(mine)
            segs += mine
        segs.sort(key=lambda s: (s.t1, s.bit, s.t0))
        for k, s in enumerate(segs):
            s.order = k
        self.segs = segs
        self.ends = [s.t1 for s in segs]
        self.bit_t1 = [[s.t1 for s in mine] for mine in self.bit_segs]
        # kept states, by the number of segments done. Every state is made by the same steps in the
        # same order from the stock, so where states are kept never changes a result.
        self.states: dict[int, tuple] = {0: workpiece.first}
        self.last = (0, workpiece.first)
        self.mesh_cache: dict = {}
        # {Manifold id of the solid a cut took away: the move's row}: which move made a face (task 0061)
        self.cut_ids: dict = {}
        self.moves = self._moves()
        self.stats = Stats(segments=len(segs), cutting_segments=sum(1 for s in segs if s.cuts))
        self.t_first = min((float(p.t[0]) for p in paths if len(p.t)), default=0.0)

    def _moves(self) -> Moves:
        n = len(self.segs)
        o0, o1, d = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros((n, 3))
        dist = np.zeros(n)
        per_tooth, per_rev = np.zeros(n), np.zeros(n)
        owner = np.arange(n, dtype=np.int32)
        typical = typical_feed("")[0]
        same = math.cos(2 * ANGLE_TOL)
        for b, mine in enumerate(self.bit_segs):         # (a bit's own moves are in time order)
            p = self.paths[b]
            flutes = default_flutes(self.cutters[b].tool.kind)
            run = 0.0
            last = down = None                           # the last move with marks of its own; a plunge just made
            for s in mine:
                k = s.order
                o0[k], o1[k], d[k] = p.o[s.i0], p.o[s.i1], p.d[s.i0]
                dist[k] = run
                per_tooth[k], per_rev[k] = typical, typical * flutes
                v = o1[k] - o0[k]
                up = float(v @ d[k])
                length, side = float(np.linalg.norm(v)), float(np.linalg.norm(v - up * d[k]))
                if s.cuts:
                    run += side
                straight = side < 0.02 * length or side < 1e-6       # along the axis, or not at all
                # Two solids of one bit that lie on each other share faces, and which of the two a shared face
                # then belongs to is a toss-up, triangle by triangle. So such moves show one move's marks:
                if last is not None and float(d[last] @ d[k]) > same and (length < 1e-6 or (straight and up > 0)):
                    owner[k] = last                      # standing still, or straight back out: the move before
                    if length >= 1e-6:
                        down = None                      # (out again: the next move does not start at the bottom)
                    continue
                if down is not None and not straight and float(d[down] @ d[k]) > same:
                    owner[down] = k                      # a plunge, then sideways from its bottom: the bit's
                last = k                                 # heel sweeps the plunge's floor as it leaves
                down = k if straight and up < 0 else None
        for k in range(n):                               # (standing still after a plunge: two steps)
            r = owner[k]
            while owner[r] != r:
                r = owner[r]
            owner[k] = r
        return Moves(bit=np.array([s.bit for s in self.segs], np.int32), o0=o0, o1=o1, d=d,
                     t0=np.array([s.t0 for s in self.segs], float), t1=np.array([s.t1 for s in self.segs], float),
                     dist=dist, per_tooth=per_tooth, per_rev=per_rev,
                     cuts=np.array([s.cuts for s in self.segs], bool), owner=owner, step=self._steps(o0, o1, d))

    STEP_LOOK_BACK = 2000         # moves of the same bit looked at for the pass above

    def _steps(self, o0, o1, d) -> np.ndarray:
        """``Moves.step``: for every level sideways move that cuts, how far below the nearest earlier pass of the
        same bit (same axis) it runs, when that pass came within the tool's radius of it seen along the axis –
        the pocket's depth before, not a cut somewhere else on the part. A wall cut in several depths along the
        same contour is one flat face (the deeper pass's side lies on the wall above), so nothing in the mesh
        shows where the depths meet: the marks draw that line from this number."""
        step = np.zeros(len(self.segs))
        for b, mine in enumerate(self.bit_segs):
            reach = self.cutters[b].reach
            ks = []
            for s in mine:
                k = s.order
                v = o1[k] - o0[k]
                up = float(v @ d[k])
                side = float(np.linalg.norm(v - up * d[k]))
                if s.cuts and side > 1e-6 and abs(up) < 2e-5:
                    ks.append(k)
            if len(ks) < 2:
                continue
            ks = np.array(ks)
            A, B, D = o0[ks], o1[ks], d[ks]
            for j in range(1, len(ks)):
                lo = max(0, j - self.STEP_LOOK_BACK)
                a, bb, ax = A[lo:j], B[lo:j], D[j]
                same = (D[lo:j] @ ax) > math.cos(2 * ANGLE_TOL)
                above = (a - A[j]) @ ax                               # how much higher the earlier passes ran
                ok = same & (above > 2e-5) & (above < self.cutters[b].length)
                if not ok.any():
                    continue
                a, bb, above = a[ok], bb[ok], above[ok]
                near = np.zeros(len(a), bool)
                ab = bb - a
                ab -= (ab @ ax)[:, None] * ax
                l2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-18)
                for x in (A[j], 0.5 * (A[j] + B[j]), B[j]):           # start, middle, end of this move
                    q = x - a
                    q -= (q @ ax)[:, None] * ax
                    t = np.clip(np.einsum("ij,ij->i", q, ab) / l2, 0.0, 1.0)
                    off = q - t[:, None] * ab
                    near |= np.einsum("ij,ij->i", off, off) < reach * reach
                if near.any():
                    step[ks[j]] = float(above[near].min())
        return step

    def set_feeds(self, per_tooth, per_rev) -> None:
        """The feed per tooth and per turn of the spindle of every move (metres, one number per row of
        ``moves``): the distance between two tool marks. For a face mill give its feed per turn as both (its
        floor shows one arc per turn). The marks already worked out are forgotten."""
        n = len(self.segs)
        pt = np.array(per_tooth, dtype=float).reshape(-1)
        pr = np.array(per_rev, dtype=float).reshape(-1)
        if len(pt) != n or len(pr) != n:
            raise ValueError(f"set_feeds wants {n} numbers each (one per move), got {len(pt)} and {len(pr)}")
        self.moves.per_tooth, self.moves.per_rev = pt, pr
        self.moves.tables.clear()
        self.mesh_cache = {}

    def _may_cut(self, cut: Cutter, p: Path, i0: int, i1: int) -> bool:
        pts = np.concatenate([p.o[i0:i1 + 1], p.o[i0:i1 + 1] + p.d[i0:i1 + 1] * cut.length])
        lo = pts.min(axis=0) - cut.reach
        hi = pts.max(axis=0) + cut.reach
        return self.wp.touches(lo, hi)

    # -- applying cuts --------------------------------------------------------

    def _apply(self, tiles, b: int, o0, o1, d, tag=None):
        cutter, (lo, hi) = self.cutters[b].sweep(o0, o1, d)
        if cutter is None or not self.wp.touches(lo, hi):
            return tiles
        t0 = time.perf_counter()
        out = self.wp.cut(tiles, cutter, lo, hi, tag=tag, ids=self.cut_ids)
        dt = time.perf_counter() - t0
        self.stats.ops += 1
        self.stats.seconds += dt
        return out

    def _commit(self, tiles, s: _Seg):
        if not s.cuts:
            return tiles
        p = self.paths[s.bit]
        return self._apply(tiles, s.bit, p.o[s.i0], p.o[s.i1], p.d[s.i0], tag=int(self.moves.owner[s.order]))

    def committed(self, k: int) -> tuple:
        """The workpiece after the first ``k`` segments (in end-time order)."""
        k = max(0, min(k, len(self.segs)))
        start = max((c for c in self.states if c <= k), default=0)
        lk, lt = self.last
        if start < lk <= k:
            start, tiles = lk, lt
        else:
            tiles = self.states[start]
        work = 0.0
        for i in range(start, k):
            before = self.stats.seconds
            tiles = self._commit(tiles, self.segs[i])
            work += self.stats.seconds - before
            if work >= self.KEEP_SECONDS:
                self._keep(i + 1, tiles)
                work = 0.0
        self.last = (k, tiles)
        return tiles

    def kept_bytes(self) -> float:
        seen = {}
        for tiles in self.states.values():
            for t in tiles:
                seen[id(t.solid)] = t.ntri
        return sum(seen.values()) * self.BYTES_PER_TRIANGLE

    def _keep(self, k: int, tiles) -> None:
        self.states[k] = tiles
        while len(self.states) > 2 and self.kept_bytes() > self.MEMORY_BUDGET:   # thin out: every other one goes
            keys = sorted(self.states)
            for c in keys[1:-1:2]:
                del self.states[c]
            if len(keys) <= 3:
                break

    def at(self, T: float) -> tuple:
        """The workpiece at time ``T`` (frames, may be between frames)."""
        T = max(float(T), self.t_first)
        if len(self.cut_ids) > self.IDS_MAX:
            self._forget()
        k = bisect_right(self.ends, T + 1e-9)
        tiles = self.committed(k)
        for b, mine in enumerate(self.bit_segs):          # the part of the current segment done so far
            j = bisect_right(self.bit_t1[b], T + 1e-9)
            if j >= len(mine):
                continue
            s = mine[j]
            if not s.cuts or T < s.t0 - 1e-9 or (T <= s.t0 + 1e-9 and j > 0):
                continue                       # not started yet (or exactly where the last one ended)
            p = self.paths[b]
            o = self._pos(p, s, T)
            tiles = self._apply(tiles, b, p.o[s.i0], o, p.d[s.i0], tag=int(self.moves.owner[s.order]))
        return tiles

    def _forget(self) -> None:
        """Too many ids of cuts remembered (every state made again has new ones): drop everything kept. The next
        state is made from the stock by the same steps, so it is the same mesh as before."""
        self.states = {0: self.wp.first}
        self.last = (0, self.wp.first)
        self.mesh_cache = {}
        self.cut_ids.clear()

    @staticmethod
    def _pos(p: Path, s: _Seg, T: float) -> np.ndarray:
        ts = p.t[s.i0:s.i1 + 1]
        j = bisect_left(ts.tolist(), T)
        if j <= 0:
            return p.o[s.i0]
        if j >= len(ts):
            return p.o[s.i1]
        a, b = ts[j - 1], ts[j]
        f = 0.0 if b - a <= 1e-12 else (T - a) / (b - a)
        return p.o[s.i0 + j - 1] * (1 - f) + p.o[s.i0 + j] * f

    def mesh_at(self, T: float, moves: bool = False, marks: bool = False, normals: bool = False) -> tuple:
        """The workpiece's mesh at time ``T``: (verts, tris, source) as ``Workpiece.mesh``.

        ``moves=True``: also int32 per triangle, the row in ``self.moves`` of the move that made it last (-1: a
        face of the stock, or a face whose maker is not known). A move straight back out of the cut and a bit
        standing still count as the move before, a plunge as the sideways move that starts at its bottom
        (``moves.owner``): their solids lie on each other.

        ``marks=True``: five results – the move and, fifth, the four arrays of ``mark_faces``, worked out once
        per tile and kept with its mesh, so a frame that changes one tile works out the marks of that tile only.

        ``normals=True``: one more result at the end – a unit normal per triangle corner, float32
        (triangles * 3, 3), from ``cut_normals.corner_normals`` (flat faces flat, round walls smooth, needle
        triangles take their neighbour's; the faces that close a tile inside the material do not count), also
        worked out once per tile."""
        t0 = time.perf_counter()
        tiles = self.at(T)
        if len(self.mesh_cache) > 2 * len(tiles) + 8:      # forget meshes of tiles no longer shown
            alive = {id(t.solid) for t in tiles}
            self.mesh_cache = {k: v for k, v in self.mesh_cache.items() if k in alive}
        rows = self.wp.tile_meshes(tiles, self.mesh_cache, self.cut_ids)
        out = self.wp.joined(rows, moves or marks)
        if marks:
            for r in rows:
                if r[5] is None:
                    r[5] = mark_faces(r[1], r[2], r[4], self.moves, self.cutters)
            if len(rows) == 1:
                out += (rows[0][5],)
            elif rows:
                out += (tuple(np.concatenate([r[5][k] for r in rows]) for k in range(4)),)
            else:
                out += (tuple(np.zeros((0, 3), np.float32) for _k in range(4)),)
        if normals:
            from . import cut_normals
            for r in rows:
                if r[6] is None:
                    r[6] = cut_normals.corner_normals(r[1], r[2], skip=cut_normals.seam_faces(r[1], r[2], r[7], r[8]))
            if len(rows) == 1:
                out += (rows[0][6],)
            elif rows:
                out += (np.concatenate([r[6] for r in rows]),)
            else:
                out += (np.zeros((0, 3), np.float32),)
        self.stats.last_ms = (time.perf_counter() - t0) * 1000
        self.stats.triangles = int(len(out[1]))
        self.stats.tiles = sum(1 for t in tiles if t.ntri)
        return out


# ---------------------------------------------------------------------------
# tool marks: what the cut-face material is told about each face (task 0061)
# ---------------------------------------------------------------------------

_COS_FLOOR = math.cos(math.radians(4.0))     # a face this square to the tool's axis is a floor
_SIN_WALL = math.sin(math.radians(4.0))      # a face this close to along the axis is a wall


def default_flutes(kind: str) -> int:
    """Cutting edges of a bit nobody gave a number for, by its shape."""
    return {"FLAT": 3, "BALL": 2, "VEE": 2, "DRILL": 2, "BULL": 4}.get(kind, 3)


def flat_radius(cutter: Cutter) -> float:
    """Radius of the flat bottom of a bit (the circle its bottom edge runs on); 0 when it ends in a point or a
    ball, or when the flat is smaller than 5 % of the bit."""
    prof = cutter.profile
    if not prof:
        return 0.0
    z0, r0 = prof[0]
    full = cutter.tool.radius if cutter.tool.radius > 1e-9 else cutter.reach
    if abs(z0) > 1e-7 or r0 <= 0.05 * full:
        return 0.0
    return float(r0)


def _mark_tables(moves: Moves, cutters: list) -> dict:
    """What ``mark_faces`` gives a face, worked out once per move for each of the three ways a face can lie
    against the tool's axis (0 floor, 1 wall, 2 slanted): float32 tables with a row per (move, way), and three
    rows of zeros at the end for faces no move made. Kept on ``moves``."""
    key = tuple(id(c) for c in cutters)
    tb = moves.tables
    if tb.get("key") == key:
        return tb
    T = _tm
    n = len(moves)
    a = np.array(moves.d, dtype=float).reshape(-1, 3)
    v = moves.o1 - moves.o0
    length = np.linalg.norm(v, axis=1)
    side = v - np.einsum("ij,ij->i", v, a)[:, None] * a          # the move without its part along the axis
    ls = np.linalg.norm(side, axis=1)
    plunge = (ls < 0.02 * length) | (ls < 1e-6)
    dh = np.zeros((n, 3))
    go = ~plunge
    dh[go] = side[go] / ls[go, None]
    rflat = np.array([flat_radius(c) for c in cutters] + [0.0])[moves.bit]
    cls = np.array([{"VEE": 1, "DRILL": 2}.get(c.tool.kind, 0) for c in cutters] + [0], np.int8)[moves.bit]
    sp = np.zeros((n, 7))                     # the distance between two marks, per kind
    sp[:, T.ARCS] = sp[:, T.FLANK] = sp[:, T.ACROSS] = moves.per_tooth
    sp[:, T.RINGS_WALL] = moves.per_rev
    sp[:, T.ALONG] = T.SPACING_ALONG
    sp[:, T.RINGS] = T.SPACING_RINGS
    sp = np.clip(sp, T.SPACING_MIN, T.SPACING_MAX)
    sp[:, T.NONE] = 0.0
    back = np.zeros((n, 7))                   # how far back along the feed the marks start: they carry on from
    for k in (T.ARCS, T.FLANK, T.ACROSS):     # the bit's move before
        back[:, k] = np.mod(moves.dist, sp[:, k])
    kind = np.empty((n, 3), dtype=np.int64)   # per move and way the face lies: floor, wall, slanted
    kind[:, 0] = np.where(plunge, T.RINGS, np.where(rflat > 0.0, T.ARCS, T.ACROSS))
    kind[:, 1] = np.where(plunge, T.RINGS_WALL, T.FLANK)
    kind[:, 2] = np.where(plunge | (cls == 2), T.RINGS, np.where(cls == 1, T.ALONG, T.ACROSS))
    o = np.zeros((3 * n + 3, 3), np.float32)
    d = np.zeros((3 * n + 3, 3), np.float32)
    pr = np.zeros((3 * n + 3, 3), np.float32)
    if n:
        rows = np.arange(n)[:, None]
        o[:3 * n] = (moves.o0[:, None, :] - dh[:, None, :] * back[rows, kind][:, :, None]).reshape(-1, 3)
        d[:3 * n] = np.repeat(dh, 3, axis=0)
        second = np.repeat(rflat[:, None], 3, axis=1)             # the flat bottom's radius; on a wall (FLANK)
        if moves.step is not None:                                # the step-down instead (core/toolmarks.py)
            second[:, 1] = np.where(plunge, 0.0, moves.step)
        else:
            second[:, 1] = np.where(plunge, rflat, 0.0)
        pr[:3 * n] = np.stack([kind, second, sp[rows, kind]], axis=2).reshape(-1, 3)
    a32 = np.zeros((n + 1, 3), np.float32)
    a32[:n] = a
    tb.clear()
    tb.update(key=key, o=o, d=d, p=pr, a=a32, plunge=plunge, sp=sp, back=back)
    return tb


def mark_faces(verts: np.ndarray, tris: np.ndarray, move: np.ndarray, moves: Moves, cutters: list) -> tuple:
    """What the cut-face material reads on every triangle: ``(o, d, a, p)``, four float32 (m, 3) arrays, the
    attributes ``fr_mk_o`` / ``fr_mk_d`` / ``fr_mk_a`` / ``fr_mk_p`` of ``core/toolmarks.py``.

    ``move``: per triangle the row in ``moves`` of the move that made it (-1: none – all four rows are zeros,
    which is kind NONE). ``cutters``: the timeline's (``moves.bit`` points into them). The kind of marks comes
    from the face's normal against the tool's axis and from the tool's shape:

    * a floor facing the tool (within 4°): arcs under a flat-bottomed tool moving sideways, fine lines across the
      pass under a ball, V or drill point, rings where the tool went straight down;
    * a wall (within 4° of along the axis): lines along the axis, one per tooth; rings round the axis, one per
      turn, in a plunged or drilled hole;
    * a slanted or curved face: lines along the path for a V-bit, rings for a drill point, lines across the pass
      for everything else; rings after a plunge.

    (A plunge followed by a sideways move from its bottom comes here as that sideways move – ``moves.owner`` –
    so the start of a slot shows the slot's marks; a hole that is only drilled or plunged shows rings.)

    The spacing is ``moves.per_tooth`` (arcs, wall lines, lines across a pass) or ``moves.per_rev`` (the rings of
    a hole's wall), kept between ``SPACING_MIN`` and ``SPACING_MAX``. ``fr_mk_o`` is the tip at the move's start,
    moved back along the feed by what the bit had cut before (modulo the spacing): the marks of one move carry on
    into the next."""
    m = len(tris)
    move = np.asarray(move).reshape(-1)
    n = len(moves)
    if m == 0 or n == 0:
        return tuple(np.zeros((m, 3), np.float32) for _k in range(4))
    tb = _mark_tables(moves, cutters)
    row = np.where((move >= 0) & (move < n), move, n)      # (row n: the zeros)
    tr = np.asarray(tris)
    vv = np.asarray(verts, dtype=np.float32)
    p0 = vv[tr[:, 0]]
    e1, e2 = vv[tr[:, 1]] - p0, vv[tr[:, 2]] - p0
    a = tb["a"][row]
    # the face's normal (out of the material: the triangle's winding) against the tool's axis
    nx = e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1]
    ny = e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2]
    nz = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    c = (nx * a[:, 0] + ny * a[:, 1] + nz * a[:, 2]) / np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-30)
    way = np.where(c > _COS_FLOOR, 0, np.where(np.abs(c) < _SIN_WALL, 1, 2))
    k = row * 3 + way
    return tb["o"][k], tb["d"][k], a, tb["p"][k]


def typical_feed(block_id: str) -> tuple:
    """(feed per tooth in metres, the material in words) for a block of this material id (3 Looks), when no
    program gives a feed and a spindle speed. The words are '' for a material the table does not know."""
    if block_id in _CUT_ALU:
        return 0.05 * MM, "aluminium"
    if block_id in _CUT_STEEL:
        return 0.03 * MM, "steel"
    if block_id in ("stainless_brushed", "stainless_polished"):
        return 0.025 * MM, "stainless steel"
    if block_id in ("cast_iron", "cast_iron_painted"):
        return 0.04 * MM, "cast iron"
    if block_id in _CUT_BRIGHT or block_id == "nickel_plated":
        return 0.04 * MM, {"bronze": "bronze", "copper": "copper", "zinc_diecast": "zinc"}.get(block_id, "brass")
    if block_id in _CUT_PLASTIC:
        return 0.08 * MM, "plastic"
    return 0.04 * MM, ""


def volume(tiles) -> float:
    return float(sum(t.solid.volume() for t in tiles if t.ntri))


# ---------------------------------------------------------------------------
# the look of cut faces (task 0051)
# ---------------------------------------------------------------------------

#: face-milling marks on fresh cuts (the same kind as *Steel, machined*)
_MILLED = dict(kind="milled", scale=1500.0, rough=0.04, bump=0.008)

_CUT_ALU = ("aluminium_machined", "aluminium_anodized", "aluminium_anodized_color", "aluminium_anodized_black",
            "aluminium_profile", "aluminium_sawn")
_CUT_STEEL = ("steel_raw", "steel_machined", "steel_ground", "steel_turned", "zinc_plated", "zinc_yellow",
              "zinc_flake", "galvanized", "black_oxide", "chrome", "chrome_rod")
_CUT_BRIGHT = ("brass", "bronze", "copper", "zinc_diecast")
_CUT_PLASTIC = ("pom_white", "pom_black", "plastic_gloss", "plastic_matte")


def cut_look(block_id: str) -> tuple | None:
    """What a face the cutter made looks like, from the block's material id (3 Looks).

    Returns ``(material id, tweaks, label)`` – the tweaks change that material's settings
    (``materials_lib``) – or None when the cut looks like the block itself (paint, glass, anything else)."""
    from . import materials_lib as ml
    if block_id in _CUT_ALU:
        return "aluminium_machined", {}, "Aluminium, machined"
    if block_id in _CUT_STEEL:
        return "steel_machined", {}, "Steel, machined"
    if block_id in ("stainless_brushed", "stainless_polished"):
        return ("stainless_brushed", dict(anisotropic=0.0, roughness=0.22, marks=dict(_MILLED)),
                "Stainless, machined")
    if block_id in ("cast_iron", "cast_iron_painted"):      # bare grey iron, a little dull
        return ("steel_machined", dict(base_color=(0.47, 0.47, 0.48), metallic=0.9, roughness=0.34,
                                       marks=dict(_MILLED, rough=0.06), marks_look="cast_iron"),
                "Cast iron, machined")
    if block_id == "nickel_plated":                         # plated brass fittings: brass underneath
        block_id = "brass"
    if block_id in _CUT_BRIGHT:
        spec = ml.MATERIALS[block_id]
        return (block_id, dict(roughness=max(0.1, float(spec.get("roughness", 0.25)) - 0.1), marks=dict(_MILLED)),
                f"{spec['label']}, machined")
    if block_id in _CUT_PLASTIC:                            # the same plastic, a little more matte, no gloss
        spec = ml.MATERIALS[block_id]
        return (block_id, dict(roughness=min(1.0, float(spec.get("roughness", 0.4)) + 0.12), bump=None, peel=None,
                               coat=0.0), f"{spec['label']} (cut)")
    return None
