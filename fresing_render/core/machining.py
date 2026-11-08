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

Units: metres (Blender's), angles of tips in degrees.
"""

from __future__ import annotations

import math
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

import numpy as np

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
    current last sample, moves forwards along it, and the axis turns less than ``angle_tol``."""
    n = len(o)
    if n == 0:
        return []
    if n == 1:
        return [(0, 0)]
    cos_tol = math.cos(angle_tol)
    segs = []
    i = 0
    while i < n - 1:
        def ok(k):
            a, b = o[i], o[k]
            if np.min(d[i + 1:k + 1] @ d[i]) < cos_tol:
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
        self.stock_id = stock.original_id()
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

    def touches(self, lo, hi) -> bool:
        return bool(np.all(hi >= self.lo) and np.all(lo <= self.hi))

    def cut(self, tiles: tuple, cutter, lo, hi) -> tuple:
        """``tiles`` minus ``cutter`` (bounding box lo..hi). Tiles it does not reach stay the same objects."""
        out = []
        changed = False
        for t in tiles:
            if t.ntri == 0 or np.any(hi < t.lo) or np.any(lo > t.hi):
                out.append(t)
                continue
            c = cutter if t.keep is None else cutter - t.keep
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

    def mesh(self, tiles: tuple, cache: dict | None = None) -> tuple:
        """(verts float32 (n, 3), tris int32 (m, 3), source int32 (m,)): source is the stock's face
        (the number given as face id) for uncut surfaces, -1 for surfaces the bit made."""
        vs, ts, ss = [], [], []
        off = 0
        for t in tiles:
            if t.ntri == 0:
                continue
            key = id(t.solid)
            hit = cache.get(key) if cache is not None else None
            if hit is None or hit[0] is not t.solid:
                hit = (t.solid,) + self._tile_mesh(t.solid)
                if cache is not None:
                    cache[key] = hit
            _s, v, tr, src = hit
            vs.append(v)
            ts.append(tr + off)
            ss.append(src)
            off += len(v)
        if not vs:
            return (np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32), np.zeros(0, np.int32))
        return np.concatenate(vs), np.concatenate(ts), np.concatenate(ss)

    def _tile_mesh(self, solid) -> tuple:
        m = solid.to_mesh()
        v = np.array(m.vert_properties[:, :3], dtype=np.float32)
        tr = np.array(m.tri_verts, dtype=np.int32)
        src = np.full(len(tr), -1, dtype=np.int32)
        ri, rid = np.asarray(m.run_index), np.asarray(m.run_original_id)
        fid = np.asarray(m.face_id)
        for k in range(len(rid)):
            if int(rid[k]) == self.stock_id:
                a, b = int(ri[k]) // 3, int(ri[k + 1]) // 3
                src[a:b] = fid[a:b]
        return v, tr, src


# ---------------------------------------------------------------------------
# the timeline: what the workpiece looks like at any frame
# ---------------------------------------------------------------------------

@dataclass
class Path:
    """One bit's tip (o) and axis (d) in the workpiece's coordinates at times t (frames)."""
    t: np.ndarray
    o: np.ndarray
    d: np.ndarray

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


class Timeline:
    """The workpiece at any time of the animation, for a set of bits and their paths."""

    KEEP_SECONDS = 0.25           # keep a state after this much boolean work (scrubbing back costs at most this)
    MEMORY_BUDGET = 256e6         # bytes for the kept states (a triangle costs about BYTES_PER_TRIANGLE)
    BYTES_PER_TRIANGLE = 250      # measured: Manifold keeps ~250 bytes per triangle

    def __init__(self, workpiece: Workpiece, cutters: list, paths: list, detail_name: str = "NORMAL"):
        self.wp = workpiece
        self.cutters = cutters
        self.paths = paths
        self.tol = detail(detail_name)["tol"]
        segs = []
        self.bit_segs: list[list[_Seg]] = []
        for b, (cut, p) in enumerate(zip(cutters, paths)):
            mine = []
            for i0, i1 in find_segments(p.o, p.d, self.tol):
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
        self.stats = Stats(segments=len(segs), cutting_segments=sum(1 for s in segs if s.cuts))
        self.t_first = min((float(p.t[0]) for p in paths if len(p.t)), default=0.0)

    def _may_cut(self, cut: Cutter, p: Path, i0: int, i1: int) -> bool:
        pts = np.concatenate([p.o[i0:i1 + 1], p.o[i0:i1 + 1] + p.d[i0:i1 + 1] * cut.length])
        lo = pts.min(axis=0) - cut.reach
        hi = pts.max(axis=0) + cut.reach
        return self.wp.touches(lo, hi)

    # -- applying cuts --------------------------------------------------------

    def _apply(self, tiles, b: int, o0, o1, d):
        cutter, (lo, hi) = self.cutters[b].sweep(o0, o1, d)
        if cutter is None or not self.wp.touches(lo, hi):
            return tiles
        t0 = time.perf_counter()
        out = self.wp.cut(tiles, cutter, lo, hi)
        dt = time.perf_counter() - t0
        self.stats.ops += 1
        self.stats.seconds += dt
        return out

    def _commit(self, tiles, s: _Seg):
        if not s.cuts:
            return tiles
        p = self.paths[s.bit]
        return self._apply(tiles, s.bit, p.o[s.i0], p.o[s.i1], p.d[s.i0])

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
            tiles = self._apply(tiles, b, p.o[s.i0], o, p.d[s.i0])
        return tiles

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

    def mesh_at(self, T: float) -> tuple:
        t0 = time.perf_counter()
        tiles = self.at(T)
        if len(self.mesh_cache) > 2 * len(tiles) + 8:      # forget meshes of tiles no longer shown
            alive = {id(t.solid) for t in tiles}
            self.mesh_cache = {k: v for k, v in self.mesh_cache.items() if k in alive}
        out = self.wp.mesh(tiles, self.mesh_cache)
        self.stats.last_ms = (time.perf_counter() - t0) * 1000
        self.stats.triangles = int(len(out[1]))
        self.stats.tiles = sum(1 for t in tiles if t.ntri)
        return out


def volume(tiles) -> float:
    return float(sum(t.solid.volume() for t in tiles if t.ntri))
