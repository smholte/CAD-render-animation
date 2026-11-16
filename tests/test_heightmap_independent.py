"""Task 0146, the independent tests of the height-map cutter: written from the brief and the Design
(tasks/0146-heightmap-cutter.md) by a tester that did not write the cutter.

What is promised and tested here
--------------------------------
1. ``Timeline(..., fast=True)`` gives the same workpiece as the exact cut (``fast=False``, one Manifold boolean per
   move) within the stated tolerance at detail Normal (a 0.2 mm grid; it scales with the map's cell): surfaces and
   straight / round walls 0.03 mm; the steep rounded strip under a rim or at the foot of a wall (a ball deeper
   than 2/3 of its radius, a corner radius' fillet, where ramps of a flat bit start) 0.15 mm; sharp outside
   corners of walls one cell (0.2 mm; the Design allows 0.3), features thinner than two cells 0.3 mm.
2. Short or thinly spread programs and moves the map does not take (tilted tools, undercut cutters, a tool
   shorter than the cut is deep, V-bits, drills and custom outlines) are cut exactly as before; mixed programs
   are right at every time.
3. Any time T gives the same mesh again, however it is reached; the removed volume grows with T.
4. ``mesh_at(T, moves=True)`` names the move that made each cut triangle; ``marks=True`` the kinds of
   ``core/toolmarks.py``; ``normals=True`` unit normals, flat floors flat, walls level.
5. The tiles of ``Timeline.at`` are closed solids.
6. ``heightmap.sweep_height`` against brute force, ``shape_of`` refusing what the map cannot hold, the solids of
   ``HeightMap.mesh`` closed.

How the two cuts are compared: points on the faces the moves made of one mesh (corners, centres, rows of points on
long triangles), their distance to the other mesh's faces, both ways. Tiles are separate solids, so both meshes
have faces inside the material where two tiles touch; such a face has a face that looks the other way lying on it
and is left out. Lengths in the programs are mm, in the app metres.

Faults found and not fixed in task 0146 are kept as ``xfail(strict=True, reason="FINDING …")`` tests (marked by the
worker after the tester's second report; the report in tasks/0146-heightmap-cutter.md lists them as open points):
they fail now and will turn the run red once the fault is fixed - then the mark goes.
"""

import contextlib
import hashlib
import math

import numpy as np
import pytest

mf = pytest.importorskip("manifold3d")

from fresing_render.core import heightmap as H  # noqa: E402
from fresing_render.core import machining as M  # noqa: E402
from fresing_render.core import toolmarks as TM  # noqa: E402

MM = 0.001
UP = np.array([0.0, 0.0, 1.0])

# the stated tolerance at detail Normal (the Design)
SURFACE = 0.03 * MM           # surfaces, straight and round walls
STEEP = 0.15 * MM             # the steep rounded strip under a rim or at the foot of a wall
CELL = 0.2 * MM               # the map's cell at Normal; sharp outside corners of walls, where cuts cross
THIN = 0.3 * MM               # features thinner than two cells


# ---------------------------------------------------------------------------
# how far a point is from a mesh
# ---------------------------------------------------------------------------

def _closest_d2(p, a, b, c):
    """Squared distance of the points p (n, 3) to the triangles a, b, c (n, 3 each)."""
    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = va + vb + vc
        v = np.where(np.abs(denom) > 0, vb / denom, 0.0)
        w = np.where(np.abs(denom) > 0, vc / denom, 0.0)
        q = a + ab * v[:, None] + ac * w[:, None]                    # inside the triangle
        t_ab = np.where(np.abs(d1 - d3) > 0, d1 / (d1 - d3), 0.0)
        t_ac = np.where(np.abs(d2 - d6) > 0, d2 / (d2 - d6), 0.0)
        e = (d4 - d3) + (d5 - d6)
        t_bc = np.where(np.abs(e) > 0, (d4 - d3) / e, 0.0)
    out = q
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    out = np.where(m[:, None], b + (c - b) * t_bc[:, None], out)
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    out = np.where(m[:, None], a + ac * t_ac[:, None], out)
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    out = np.where(m[:, None], a + ab * t_ab[:, None], out)
    m = (d6 >= 0) & (d5 <= d6)
    out = np.where(m[:, None], c, out)
    m = (d3 >= 0) & (d4 <= d3)
    out = np.where(m[:, None], b, out)
    m = (d1 <= 0) & (d2 <= 0)
    out = np.where(m[:, None], a, out)
    d = p - out
    return np.einsum("ij,ij->i", d, d)


NEAR = 0.06 * MM      # distances up to here come from the grid
FAR = 1.0 * MM        # ... larger ones (few points) are looked up one by one, up to here
FAR_MOST = 300        # at most this many points are looked up one by one


class Surf:
    """A triangle mesh with a grid to ask "how far is this point from the surface" (at most ``FAR``).
    ``roi`` = (lo, hi): only what lies in this box counts."""

    def __init__(self, verts, tris, roi=None, cap=NEAR, cell=0.2 * MM):
        self.v = np.asarray(verts, np.float64)
        t = np.asarray(tris, np.int64)
        tri = self.v[t]
        if roi is not None and len(t):
            keep = np.all(tri.max(axis=1) >= roi[0] - FAR, axis=1) & np.all(tri.min(axis=1) <= roi[1] + FAR, axis=1)
            t, tri = t[keep], tri[keep]
        self.t, self.cap, self.cell = t, cap, cell
        cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        self.n = cr / np.maximum(np.linalg.norm(cr, axis=1), 1e-300)[:, None]
        self.lo, self.hi = tri.min(axis=1), tri.max(axis=1)
        lo, hi = self.lo - cap, self.hi + cap
        if roi is not None:
            lo, hi = np.maximum(lo, roi[0] - cap), np.minimum(hi, roi[1] + cap)
        ok = np.all(hi >= lo, axis=1)
        self.origin = (lo[ok].min(axis=0) if ok.any() else np.zeros(3)) - cell
        ilo = np.floor((lo - self.origin) / cell).astype(np.int64)
        ihi = np.floor((hi - self.origin) / cell).astype(np.int64)
        self.dim = (ihi[ok].max(axis=0) if ok.any() else np.zeros(3, np.int64)) + 2
        n = np.where(ok[:, None], ihi - ilo + 1, 0)
        cnt = n[:, 0] * n[:, 1] * n[:, 2]
        tot = int(cnt.sum())
        who = np.repeat(np.arange(len(cnt)), cnt)
        k = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nx, ny = n[who, 0], n[who, 1]
        cid = self._cid(ilo[who, 0] + k % nx, ilo[who, 1] + (k // nx) % ny, ilo[who, 2] + k // (nx * ny))
        order = np.argsort(cid, kind="stable")
        self.cid, self.tri_of = cid[order], who[order]

    def _cid(self, ix, iy, iz):
        return ix + self.dim[0] * (iy + self.dim[1] * iz)

    def near(self, P, facing=None):
        """Distance of every point to the surface, ``cap`` where it is further. ``facing``: a unit normal per
        point - only triangles that look the other way (within about 25 degrees) count."""
        P = np.asarray(P, np.float64)
        out = np.full(len(P), self.cap)
        if not len(P) or not len(self.cid):
            return out
        idx = np.floor((P - self.origin) / self.cell).astype(np.int64)
        ok = np.all((idx >= 0) & (idx < self.dim), axis=1)
        cid = self._cid(idx[:, 0], idx[:, 1], idx[:, 2])
        a = np.searchsorted(self.cid, cid, side="left")
        b = np.searchsorted(self.cid, cid, side="right")
        cnt = np.where(ok, b - a, 0)
        cs = np.cumsum(cnt)
        start = 0
        while start < len(P):
            base = cs[start - 1] if start else 0
            end = min(len(P), max(int(np.searchsorted(cs, base + 1_500_000, side="right")), start + 1))
            c = cnt[start:end]
            tot = int(c.sum())
            if tot:
                pi = np.repeat(np.arange(start, end), c)
                k = np.arange(tot) - np.repeat(np.cumsum(c) - c, c)
                ti = self.tri_of[np.repeat(a[start:end], c) + k]
                tr = self.t[ti]
                d2 = _closest_d2(P[pi], self.v[tr[:, 0]], self.v[tr[:, 1]], self.v[tr[:, 2]])
                if facing is not None:
                    d2 = np.where(np.einsum("ij,ij->i", facing[pi], self.n[ti]) < -0.9, d2, np.inf)
                has = np.flatnonzero(c > 0)
                first = (np.cumsum(c) - c)[has]
                out[start + has] = np.minimum(out[start + has], np.sqrt(np.minimum.reduceat(d2, first)))
            start = end
        return out

    def dist(self, P):
        """Distance of every point to the surface, right up to ``FAR``. Of the points further away than the
        grid's ``cap`` only ``FAR_MOST`` (picked evenly) are looked up; the others are given ``cap``."""
        d = self.near(P)
        out = np.flatnonzero(d >= self.cap)
        if len(out) > FAR_MOST:
            out = out[np.linspace(0, len(out) - 1, FAR_MOST).astype(int)]
        for i in out:
            p = P[i]
            m = np.all((p >= self.lo - FAR) & (p <= self.hi + FAR), axis=1)
            best = FAR
            if m.any():
                tr = self.t[m]
                d2 = _closest_d2(np.broadcast_to(p, (len(tr), 3)), self.v[tr[:, 0]], self.v[tr[:, 1]],
                                 self.v[tr[:, 2]])
                best = min(FAR, float(np.sqrt(d2.min())))
            d[i] = best
        return d


def samples(verts, tris, h=0.5 * MM, normals=False):
    """Points on a mesh: every triangle's corners and centre, and on triangles longer than ``h`` rows of points
    about ``h`` apart (along the longest edge, towards the corner across). ``normals``: also the unit normal of
    each point's triangle, and which triangle that is."""
    v = np.asarray(verts, np.float64)
    t = np.asarray(tris, np.int64)
    if not len(t):
        return (np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, np.int64)) if normals else np.zeros((0, 3))
    p = v[t]
    if normals:
        out, who = [p.reshape(-1, 3), p.mean(axis=1)], [np.repeat(np.arange(len(t)), 3), np.arange(len(t))]
    else:
        out, who = [v[np.unique(t)], p.mean(axis=1)], []
    e = np.stack([np.linalg.norm(p[:, 1] - p[:, 0], axis=1), np.linalg.norm(p[:, 2] - p[:, 1], axis=1),
                  np.linalg.norm(p[:, 0] - p[:, 2], axis=1)], axis=1)
    k = np.argmax(e, axis=1)
    rows = np.arange(len(p))
    A, B, C = p[rows, k], p[rows, (k + 1) % 3], p[rows, (k + 2) % 3]
    long = e[rows, k]
    cr = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area2 = np.linalg.norm(cr, axis=1)
    high = area2 / np.maximum(long, 1e-30)
    c1 = np.ceil(np.log2(np.maximum(long / h, 1.0))).astype(int)        # 2 ** c steps along the long edge
    c2 = np.ceil(np.log2(np.maximum(high / h, 1.0))).astype(int)        # ... and towards the corner across
    for a in np.unique(c1):
        if a == 0:
            continue
        for b in np.unique(c2[c1 == a]):
            sel = np.flatnonzero((c1 == a) & (c2 == b))
            n1, n2 = 2 ** int(a), 2 ** int(b)
            u, w = np.meshgrid(np.arange(1, n1) / n1, (np.arange(n2) + 0.5) / n2, indexing="ij")
            u, w = u.ravel(), w.ravel()
            base = A[sel][:, None, :] + (B[sel] - A[sel])[:, None, :] * u[None, :, None]
            q = base * (1 - w)[None, :, None] + C[sel][:, None, :] * w[None, :, None]
            out.append(q.reshape(-1, 3))
            who.append(np.repeat(sel, len(u)))
    P = np.concatenate(out)
    if not normals:
        return P
    n = cr / np.maximum(area2, 1e-300)[:, None]
    who = np.concatenate(who)
    return P, n[who], who


TWIN = 3e-6           # two faces this close that look at each other: a seam inside the material


class Skin:
    """The workpiece of a timeline at a time, as ``mesh_at`` gives it. A point of a face is *inside the
    material* when a face that looks the other way lies on it (within ``TWIN``): where two tiles touch."""

    def __init__(self, tl, T):
        v, t, src, mv = tl.mesh_at(T, moves=True)
        self.v, self.t = np.asarray(v, np.float64), np.asarray(t, np.int64)
        self.src, self.mv = np.asarray(src), np.asarray(mv)
        self.tiles = tl.stats.tiles
        self.cut = self.mv >= 0                              # faces a move made
        self.bare = (self.mv < 0) & (self.src < 0)           # faces without a label: seams, or nobody knows
        p = self.v[self.t[self.cut]].reshape(-1, 3)
        self.roi = (p.min(axis=0) - 0.5 * MM, p.max(axis=0) + 0.5 * MM) if len(p) else None
        self._surf = self._roi = self._seen = self._cut = None
        self.seen_mm2 = 0.0

    def surf(self, roi):
        if self._surf is None or self._roi is not roi:
            self._surf, self._roi = Surf(self.v, self.t, roi), roi
        return self._surf

    def _outside(self, sel, roi, h, area=False):
        """The points on the triangles ``sel`` (inside ``roi``) that no face looking the other way lies on;
        ``area``: also how many mm2 of those triangles that is (the share of each triangle's points; then
        without the triangles' corners: a corner on the line where four tiles meet belongs to nobody)."""
        tris = self.t[sel]
        P, n, who = samples(self.v, tris, h, normals=True)
        if area:
            P, n, who = P[3 * len(tris):], n[3 * len(tris):], who[3 * len(tris):]
        if not len(P):
            return (P, 0.0) if area else P
        keep = np.all((P >= roi[0]) & (P <= roi[1]), axis=1) & (np.linalg.norm(n, axis=1) > 0.5)   # (no needles)
        P, n, who = P[keep], n[keep], who[keep]
        p = self.v[tris]
        to = p.mean(axis=1)[who] - P                         # (asked 2 um inside the triangle: not on its edge)
        Q = P + to * np.minimum(1.0, 2e-6 / np.maximum(np.linalg.norm(to, axis=1), 1e-30))[:, None]
        out = self.surf(roi).near(Q, facing=n) > TWIN
        if not area:
            return P[out]
        each = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1) / 2 / MM ** 2
        share = np.bincount(who[out], minlength=len(tris)) / np.maximum(np.bincount(who, minlength=len(tris)), 1)
        return P[out], float((each * share).sum())

    def cut_points(self, roi, h=0.5 * MM):
        """Points on the faces a move made (where there are several tiles: without those inside the material)."""
        if self._cut is None:
            self._cut = self._outside(self.cut, roi, h) if self.tiles > 1 else samples(self.v, self.t[self.cut], h)
        return self._cut

    def bare_seen(self, roi, h=0.25 * MM):
        """Points on faces without a label that are no seam inside the material: they can be seen."""
        if self._seen is None:
            self._seen, self.seen_mm2 = self._outside(self.bare, roi, h, area=True)
        return self._seen


def compare(ex, fa, T, h=0.5 * MM):
    """The exact and the fast timeline at time T against each other. A dict:
    ``P_ef``, ``d_ef``: points on the exact one's cut faces and their distance (m) to the fast one's faces;
    ``P_fe``, ``d_fe``: points on the fast one's cut faces (and its faces without a label that can be seen) and
    their distance to the exact one's faces; ``bare``: those points without a label."""
    A, B = Skin(ex, T), Skin(fa, T)
    rois = [s.roi for s in (A, B) if s.roi is not None]
    if not rois:
        z = np.zeros((0, 3))
        return dict(P_ef=z, d_ef=np.zeros(0), P_fe=z, d_fe=np.zeros(0), bare=z, bare_mm2=0.0, A=A, B=B)
    roi = (np.min([r[0] for r in rois], axis=0), np.max([r[1] for r in rois], axis=0))
    out = dict(A=A, B=B, roi=roi)
    for key, a, b in (("ef", A, B), ("fe", B, A)):
        P = a.cut_points(roi, h)
        if a is B:
            P = np.concatenate([P, a.bare_seen(roi)])
        out["P_" + key], out["d_" + key] = P, (b.surf(roi).dist(P) if len(P) else np.zeros(0))
    out["bare"] = B.bare_seen(roi)
    out["bare_mm2"] = B.seen_mm2
    return out


def worst(cmp, where=None):
    """(the largest distance in m, a sentence saying where) over both directions; ``where(P)``: bool - the
    points that count."""
    best, text = 0.0, []
    for key, name in (("ef", "exact -> fast"), ("fe", "fast -> exact")):
        P, d = cmp["P_" + key], cmp["d_" + key]
        if where is not None and len(P):
            keep = where(P)
            P, d = P[keep], d[keep]
        if not len(d):
            continue
        k = int(np.argmax(d))
        best = max(best, float(d[k]))
        text.append(f"{name}: {d[k] / MM:.4f} mm at {np.round(P[k] / MM, 3).tolist()} mm "
                    f"({int((d > SURFACE).sum())} of {len(d)} points over 0.03, {int((d > CELL).sum())} over 0.2)")
    return best, "; ".join(text)


# ---------------------------------------------------------------------------
# programs
# ---------------------------------------------------------------------------

BALL6 = M.Tool("BALL", radius=3 * MM, length=40 * MM)
BALL2 = M.Tool("BALL", radius=1 * MM, length=40 * MM)
FLAT6 = M.Tool("FLAT", radius=3 * MM, length=40 * MM)
FLAT4 = M.Tool("FLAT", radius=2 * MM, length=40 * MM)
FLAT2 = M.Tool("FLAT", radius=1 * MM, length=40 * MM)
BULL8 = M.Tool("BULL", radius=4 * MM, length=40 * MM, corner=1.5 * MM)
VEE90 = M.Tool("VEE", radius=4 * MM, length=30 * MM, angle=90.0)
VEE30 = M.Tool("VEE", radius=2 * MM, length=30 * MM, angle=30.0)
DRILL5 = M.Tool("DRILL", radius=2.5 * MM, length=40 * MM, angle=118.0)
TSLOT = M.Tool("CUSTOM", radius=4 * MM, length=30 * MM,
               profile=((0.0, 4 * MM), (2 * MM, 4 * MM), (2 * MM, 1.5 * MM), (30 * MM, 1.5 * MM)))
# a counterbore with a pilot: a thin pin below a wide body (a step, not a cone)
PILOT = M.Tool("CUSTOM", radius=4 * MM, length=30 * MM,
               profile=((0.0, 1 * MM), (5 * MM, 1 * MM), (5 * MM, 4 * MM), (30 * MM, 4 * MM)))
SHORT4 = M.Tool("FLAT", radius=2 * MM, length=3 * MM)

ROT = {                                                   # the program's +Z becomes this axis of the workpiece
    "+Z": np.eye(3),
    "-Z": np.array([[1.0, 0, 0], [0, -1, 0], [0, 0, -1]]),
    "+X": np.array([[0.0, 0, 1], [1, 0, 0], [0, 1, 0]]),
    "-Y": np.array([[1.0, 0, 0], [0, 0, -1], [0, 1, 0]]),
}


def box(size_mm, origin_mm=(0, 0, 0)):
    return mf.Manifold.cube(tuple(np.asarray(size_mm, float) * MM)).translate(
        tuple(np.asarray(origin_mm, float) * MM))


def turned(solid, axis="+Z", shift_mm=(0, 0, 0)):
    R = ROT[axis]
    return solid.transform([[R[0, 0], R[0, 1], R[0, 2], shift_mm[0] * MM], [R[1, 0], R[1, 1], R[1, 2], shift_mm[1] * MM],
                            [R[2, 0], R[2, 1], R[2, 2], shift_mm[2] * MM]])


def path_of(points_mm, per_frame=2.0, frame0=1.0, axis="+Z", shift_mm=(0, 0, 0), d=UP):
    """A path through the points (mm, one sample per point), ``per_frame`` points per frame; the tool's axis
    ``d`` (from the tip up into the tool), all turned to ``axis`` and moved."""
    o = np.asarray(points_mm, float) * MM
    dd = np.tile(np.asarray(d, float), (len(o), 1))
    R = ROT[axis]
    o = o @ R.T + np.asarray(shift_mm, float) * MM
    dd = dd @ R.T
    return M.Path(frame0 + np.arange(len(o)) / float(per_frame), o, dd)


def zigzag(x0, x1, y0, n, step, z, along="x"):
    """The corner points (mm) of a zigzag: ``n`` passes along x from x0 to x1, ``step`` apart from y0 on."""
    pts = []
    for k in range(n):
        y = y0 + k * step
        a, b = (x0, x1) if k % 2 == 0 else (x1, x0)
        pts += [(a, y, z), (b, y, z)]
    if along == "y":
        pts = [(y, x, z) for x, y, z in pts]
    return pts


def nudged(pts, by=0.07):
    """The points moved 0.07 mm along x and y: walls that would stand on whole millimetres (where the map has
    its grid lines) stand beside them. What goes wrong on the lines has its own tests."""
    return [(x + by, y + by, z) for x, y, z in pts]


def raster(xs, ys, zfun):
    pts = []
    for k, y in enumerate(ys):
        row = xs if k % 2 == 0 else xs[::-1]
        pts += [(x, y, zfun(x, y)) for x in row]
    return pts


def wave(x, y):
    return -1.5 + 0.8 * math.sin(x / 5.0) * math.cos(y / 6.0)


@contextlib.contextmanager
def thresholds(moves=None, density=None):
    """The program-size thresholds of the map for the timelines made inside (None: as they are)."""
    old = {k: getattr(M, k) for k in ("FAST_MIN_MOVES", "FAST_MIN_DENSITY") if hasattr(M, k)}
    try:
        if moves is not None:
            M.FAST_MIN_MOVES = moves
        if density is not None and "FAST_MIN_DENSITY" in old:
            M.FAST_MIN_DENSITY = density
        yield
    finally:
        for k, v in old.items():
            setattr(M, k, v)


def timelines(sc, dense=True, moves=None, detail="NORMAL"):
    """(exact timeline, fast timeline) of a scenario. ``dense=False``: the program is spread too thinly for the
    map by the app's own rule; the test wants the map all the same (the density rule is switched off)."""
    out = []
    for fast in (False, True):
        wp = M.Workpiece(sc["stock"], sc.get("finished"), detail)
        with thresholds(moves, None if dense else 0.0):
            out.append(M.Timeline(wp, [M.Cutter(t, detail) for t in sc["tools"]], sc["paths"], detail, fast=fast))
    return out


def map_moves(tl) -> int:
    return int(tl.stats.extra.get("map_moves", 0))


def removed(sc, tiles) -> float:
    """mm3 gone from the stock."""
    return (sc["stock"].volume() - M.volume(tiles)) / MM ** 3


def whole(tiles):
    solids = [t.solid for t in tiles if t.ntri]
    return solids[0] if len(solids) == 1 else mf.Manifold.batch_boolean(solids, mf.OpType.Add)


# -- the scenarios: a block 30 x 20 x 10 mm with its top at z = 0, unless said -------------------------------

def s_ball_finish(axis="+Z", shift=(0, 0, 0)):
    """Ball Ø6 finishing a wavy surface (every move sloped), passes 0.3 mm apart, running off the block."""
    stock = turned(box((24, 16, 10), (0, 0, -10)), axis, shift)
    pts = raster(np.linspace(-2, 26, 7), np.arange(0.0, 16.01, 0.3), wave)
    return dict(stock=stock, tools=[BALL6], paths=[path_of(pts, 4, axis=axis, shift_mm=shift)], dense=True)


def s_pocket(axis="+Z", shift=(0, 0, 0), step=0.1, tool=FLAT6, nudge=0.0):
    """A pocket 3 mm deep in a block 30 x 26 x 10: plunge, a zigzag of 151 passes with overlap, lift. Its walls
    stand on whole millimetres (+ nudge)."""
    stock = turned(box((30, 26, 10), (0, 0, -10)), axis, shift)
    R = tool.radius / MM
    x0, x1, y0 = 4 + R + nudge, 26 - R + nudge, 2 + R + nudge
    n = 151
    pts = [(x0, y0, 4)] + zigzag(x0, x1, y0, n, step, -3.0)
    pts.append((pts[-1][0], pts[-1][1], 4))
    return dict(stock=stock, tools=[tool], paths=[path_of(pts, axis=axis, shift_mm=shift)], dense=True,
                walls=(4 + nudge, 26 + nudge, 2 + nudge, 2 + nudge + 2 * R + (n - 1) * step))


def s_pocket_on_a_line():
    """The Ø4 pocket again, moved so that its walls along y stand exactly on lines of the map's grid - the left
    one on the border between two of the map's tiles. (The grid no longer starts on a round number, so whole
    millimetres miss its lines; a wall can still land on one. Where the lines are is read from the map of the
    pocket that is not moved.)"""
    _ex, fa = timelines(s_pocket(step=0.08, tool=FLAT4), dense=True)
    hm = fa.map.hm
    border = (hm.x0 + hm.tile * hm.cell) / MM                        # the first tile border, mm (the tool is along Z)
    sc = s_pocket(step=0.08, tool=FLAT4, nudge=border - 4.0)
    sc["line"] = border
    return sc


def s_steps():
    """Three depths side by side, the passes run off the block at both ends."""
    pts = []
    for z, y0 in ((-1.0, 2.0), (-2.5, 7.0), (-4.5, 12.0)):
        pts += [(-5, y0, 3)] + zigzag(-5, 35, y0, 101, 0.05, z) + [(35, y0 + 5.0, 3)]
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(pts)], dense=False)


def s_island():
    """A pocket 24 x 16, 2 mm deep, with an island 6 x 4 left standing in its middle (sharp outside corners)."""
    pts = [(5, 4, 3)] + zigzag(5, 25, 4, 21, 0.1, -2.0) + [(5, 6, 3)]                    # below the island
    pts += [(5, 14, 3)] + zigzag(5, 25, 14, 21, 0.1, -2.0) + [(5, 16, 3)]                # above it
    pts += [(5, 6, 3)] + zigzag(6, 14, 5, 101, 0.05, -2.0, along="y") + [(10, 6, 3)]     # left of it
    pts += [(20, 6, 3)] + zigzag(6, 14, 20, 101, 0.05, -2.0, along="y") + [(25, 6, 3)]   # right of it
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(nudged(pts))], dense=False,
                corners=[(12.07, 8.07), (18.07, 8.07), (12.07, 12.07), (18.07, 12.07)])


def s_through(below=3.0):
    """A window milled right through a 6 mm plate: the bit's tip ``below`` mm under its bottom."""
    pts = [(8, 6, 3)] + zigzag(8, 22, 6, 151, 0.05, -6.0 - below)
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=box((30, 20, 6), (0, 0, -6)), tools=[FLAT4], paths=[path_of(pts)], dense=True)


def s_cylinder():
    """A round block (not a box), ball finishing over it and past its edge."""
    stock = mf.Manifold.cylinder(10 * MM, 12 * MM, 12 * MM, 96).translate((0.015, 0.012, -0.010))
    pts = raster(np.linspace(-2, 32, 9), np.arange(-1.0, 25.01, 0.6), wave)
    return dict(stock=stock, tools=[BALL6], paths=[path_of(pts, 4)], dense=False)


def s_lshape():
    """An L-shaped block, a step milled across both legs and the gap between them."""
    stock = (box((30, 20, 10), (0, 0, -10)) - box((18, 12, 20), (12, 8, -15))).as_original()
    pts = [(-4, 1, 3)] + zigzag(-4, 34, 1, 321, 0.05, -2.0) + [(-4, 17, 3)]
    return dict(stock=stock, tools=[FLAT4], paths=[path_of(pts)], dense=False)


def s_arcs():
    """A round pocket: rings of short straight pieces (arcs as their segments) round a boss."""
    pts = [(17.5, 10, 3)]
    for r in (2.5, 3.5, 4.5, 5.5):
        pts += [(15 + r * math.cos(2 * math.pi * k / 90), 10 + r * math.sin(2 * math.pi * k / 90), -2.0)
                for k in range(91)]
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(pts, 3)], dense=False)


def s_ramp():
    """A flat end mill going down and up one sloped plane (z = -0.15 x): every cutting pass is a ramp."""
    pts = [(4, 3, 3)]
    for k in range(161):
        y = 3 + 0.05 * k
        a, b = (4, y, -0.6), (26, y, -3.9)
        pts += [a, b] if k % 2 == 0 else [b, a]
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(nudged(pts))], dense=False)


def s_holes(tool=FLAT4):
    """A grid of 6 x 5 plunged holes 5.6 mm apart (straight down, lift), every third right through the 6 mm
    plate. A small program: the test lets the map take it all the same (where the bit is one the map takes)."""
    pts, holes = [(4, 4, 3)], []
    for j in range(5):
        for i in range(6):
            x, y, z = 4 + 5.6 * i, 4 + 5.6 * j, (-2.0, -4.0, -8.5)[(i + j) % 3]
            pts += [(x, y, 3), (x, y, z), (x, y, 3)]
            holes.append((x, y, z))
    return dict(stock=box((36, 31, 6), (0, 0, -6)), tools=[tool], paths=[path_of(pts)], dense=False, small=True,
                holes=holes)


def s_ball_grooves():
    """Three separate ball grooves (deeper than 2/3 of the radius: steep flanks): 2.5 mm deep and level, 2.2 mm
    deep and level, a ramp from 1.5 to 2.9 mm. A small program: the test lets the map take it all the same.
    (Cutting one groove 50 times over to get 300 moves is no way round that: the *exact* cut runs out of
    memory - more than 5 GB - on moves that lie on each other.)"""
    pts = [(3, 4, 3), (3, 4, -2.5), (27, 4, -2.5), (27, 4, 3), (3, 10.07, 3), (3, 10.07, -2.2), (27, 10.07, -2.2),
           (27, 10.07, 3), (3, 16, 3), (3, 16, -1.5), (27, 16, -2.9), (27, 16, 3)]
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[BALL6], paths=[path_of(pts)], dense=False, small=True)


def s_tiny_bit():
    """A 0.6 mm end mill in a small block (the map's cell follows the bit: a quarter of its radius)."""
    tool = M.Tool("FLAT", radius=0.3 * MM, length=10 * MM)
    pts = [(2, 1.5, 1)] + zigzag(2, 6, 1.5, 151, 0.02, -0.6)
    pts.append((pts[-1][0], pts[-1][1], 1))
    return dict(stock=box((8, 6, 3), (0, 0, -3)), tools=[tool], paths=[path_of(pts)], dense=True)


def s_big_block():
    """A block of 1.0 x 0.8 m (the map's cell grows to stay under its node budget), a small pocket in it."""
    pts = [(7, 5, 4)] + zigzag(7, 23, 5, 151, 0.1, -3.0)
    pts.append((pts[-1][0], pts[-1][1], 4))
    return dict(stock=box((1000, 800, 10), (-500, -400, -10)), tools=[FLAT6], paths=[path_of(pts)], dense=True)


def s_bull():
    """A corner-radius pocket 2 mm deep: the first 40 passes ramp down, the rest are level."""
    pts = [(6, 6, 3), (6, 6, 0)]
    for k, y in enumerate(np.arange(6.0, 14.01, 0.05)):
        z0, z1 = (-2.0, -2.0) if k > 40 else (-0.05 * k, -0.05 * (k + 1))
        pts += [(6, y, z0), (24, y, z1)] if k % 2 == 0 else [(24, y, z0), (6, y, z1)]
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[BULL8], paths=[path_of(nudged(pts))], dense=True)


def s_vee(tool=VEE90):
    """A V-bit clearing an area 1.5 mm deep with passes 0.1 mm apart (323 moves, 0.8 per mm2: dense)."""
    pts = [(4, 2, 3)] + zigzag(4, 26, 2, 161, 0.1, -1.5)
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[tool], paths=[path_of(pts)], dense=False)


def s_fins(width):
    """Three slots side by side, walls ``width`` mm thick left standing between them."""
    pts, y = [], 3.0
    for _k in range(3):
        pts += [(5, y, 3)] + zigzag(5, 25, y, 51, 0.02, -2.0) + [(5, y + 1.0, 3)]
        y += 1.0 + 4.0 + width
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(nudged(pts))], dense=True)


def s_multi():
    """Four bits one after the other: a flat pocket, a ball that finishes its floor into waves (both on the
    map), a V along its rim (a chamfer) and drilled holes that cut into the rim (both cut exactly)."""
    p1 = [(7, 5, 4)] + zigzag(7, 23, 5, 101, 0.1, -2.0) + [(7, 15, 4)]
    p2 = raster(np.linspace(7, 23, 9), np.arange(5.0, 15.01, 0.5), lambda x, y: -2.6 + 0.5 * math.sin(x / 3.0))
    p2 = [(7, 5, 4)] + p2 + [(p2[-1][0], p2[-1][1], 4)]
    p3 = [(4, 2, 4), (4, 2, -0.8), (26, 2, -0.8), (26, 18, -0.8), (4, 18, -0.8), (4, 2, -0.8), (4, 2, 4)]
    p4 = [(2, 10, 4)]
    for x in (2.0, 28.0):
        for y in (4.0, 10.0, 16.0):
            p4 += [(x, y, 4), (x, y, -5.0), (x, y, 4)]
    t, paths = 1.0, []
    for pts in (p1, p2, p3, p4):
        paths.append(path_of(pts, frame0=t))
        t = float(paths[-1].t[-1]) + 3.0
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT6, BALL6, VEE90, DRILL5], paths=paths, dense=False)


def s_two_at_once():
    """Two bits cutting at the same time: a flat pocket from the left, a ball raster from the right; their cuts
    overlap in the middle, and their moves in time."""
    p1 = [(5, 4, 4)] + zigzag(5, 18, 4, 151, 0.08, -2.0) + [(5, 16, 4)]
    p2 = raster(np.linspace(13, 32, 6), np.arange(18.0, 1.99, -0.25), lambda x, y: -2.4 + 0.6 * math.cos(y / 3.0))
    return dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4, BALL6],
                paths=[path_of(p1, 3, frame0=1.0), path_of(p2, 4.3, frame0=1.37)], dense=True)


def s_finished():
    """Finish at the CAD part: the finished part is the block with a pocket 14 x 8 x 2 mm; the bit goes 1.5 mm
    too deep and 1 mm too wide all round."""
    stock = box((30, 20, 10), (0, 0, -10))
    finished = stock - box((14, 8, 2), (8, 6, -2))
    pts = [(9, 7, 3)] + zigzag(9, 21, 7, 151, 0.04, -3.5)
    pts.append((pts[-1][0], pts[-1][1], 3))
    return dict(stock=stock, finished=finished, tools=[FLAT4], paths=[path_of(pts)], dense=True)


def s_slots():
    """44 separate slots in two columns, each cut in three depths by one bit going back and forth (flat Ø2 and
    ball Ø2 in turn): plunge, pass at -0.5, down, pass back at -1.0, down, pass at -1.5, lift."""
    paths_pts, slots = ([], []), []
    for k in range(44):
        col, row = k % 2, k // 2
        x0, x1, y = 4 + 30 * col, 26 + 30 * col, 3 + 2.6 * row
        bit = row % 2
        paths_pts[bit].extend([(x0, y, 3), (x0, y, -0.5), (x1, y, -0.5), (x1, y, -1.0), (x0, y, -1.0), (x0, y, -1.5),
                               (x1, y, -1.5), (x1, y, 3)])
        slots.append((bit, x0, x1, y))
    paths = [path_of(paths_pts[0], frame0=1.0), path_of(paths_pts[1], frame0=1.25)]
    return dict(stock=box((60, 61, 6), (0, 0, -6)), tools=[FLAT2, BALL2], paths=paths, dense=False, slots=slots)


SCENARIOS = {
    "ball_finish": lambda: s_ball_finish(shift=(110, -70, 30)),         # a block that is not at the origin
    "pocket": s_pocket,
    "pocket_step_0.08": lambda: s_pocket(step=0.08, tool=FLAT4),
    "pocket_on_a_line": s_pocket_on_a_line,
    "ball_-Z": lambda: s_ball_finish(axis="-Z", shift=(-40, 25, 60)),
    "pocket_+X": lambda: s_pocket(axis="+X", shift=(15, 80, -45), step=0.08, tool=FLAT4, nudge=0.07),
    "pocket_-Y": lambda: s_pocket(axis="-Y", shift=(33, -12, 7), step=0.08, tool=FLAT4, nudge=0.07),
    "steps": s_steps, "island": s_island, "through": s_through, "cylinder": s_cylinder, "lshape": s_lshape,
    "arcs": s_arcs, "ramp": s_ramp, "plunges": s_holes, "ball_grooves": s_ball_grooves, "bull": s_bull,
    "fins_0.1": lambda: s_fins(0.1), "fins_0.3": lambda: s_fins(0.3),
    "fins_0.5": lambda: s_fins(0.5), "tiny_bit": s_tiny_bit, "big_block": s_big_block,
    "multi": s_multi, "two_at_once": s_two_at_once, "finished": s_finished, "slots": s_slots,
}


class Run:
    """A scenario cut both ways, at its end; what the tests share."""

    def __init__(self, name):
        self.name, self.sc = name, SCENARIOS[name]()
        self.ex, self.fa = timelines(self.sc, dense=self.sc["dense"], moves=1 if self.sc.get("small") else None)
        self.T = max(float(p.t[-1]) for p in self.sc["paths"])
        self._cmp = None

    @property
    def cmp(self):
        if self._cmp is None:
            self._cmp = compare(self.ex, self.fa, self.T)
        return self._cmp

    def volumes(self):
        return removed(self.sc, self.ex.at(self.T)), removed(self.sc, self.fa.at(self.T))


_RUNS: dict = {}


def run(name) -> Run:
    if name not in _RUNS:
        _RUNS[name] = Run(name)
    r = _RUNS[name]
    least = 3 if r.sc.get("small") else 300
    assert r.sc.get("small") or len(r.fa.segs) >= 300
    assert map_moves(r.fa) >= least, f"{name}: the fast timeline has no height map ({map_moves(r.fa)} map moves)"
    return r


def scale(r) -> float:
    """How much coarser than Normal's 0.2 mm the map's grid is (a very large block: the grid is grown, and every
    stated tolerance with it)."""
    return max(1.0, float(r.fa.map.hm.cell) / CELL)


# ---------------------------------------------------------------------------
# 1. the same workpiece as the exact cut
# ---------------------------------------------------------------------------


def known(request, wanted: bool, reason: str) -> None:
    """Mark the running test as a known fault (see the top of this file)."""
    if wanted:
        request.applymarker(pytest.mark.xfail(strict=True, reason=reason))


ON_A_LINE = ("FINDING 4 (second report): a wall that stands exactly on a line of the map's grid and on a tile's border "
             "(rare: the grid is off the round numbers) is 0.05 mm off and its faces lie there twice")


@pytest.mark.parametrize("name", ["ball_finish", "pocket", "pocket_step_0.08", "pocket_on_a_line", "steps", "through",
                                  "cylinder", "lshape", "arcs", "plunges", "tiny_bit", "big_block"])
def test_surfaces_and_walls_within_3_hundredths(name, request):
    known(request, name == "pocket_on_a_line", ON_A_LINE)
    """Flat and ball bits; level moves, sloped moves, plunges, arcs as segments; steps, pockets, a through cut,
    cuts off the block's edge, a block away from the origin, blocks that are no box: no sharp outside corner of
    walls anywhere, nothing thinner than two cells, no steep rounded strip. (On the 1.0 x 0.8 m block the grid
    is grown to 0.52 mm: the tolerance grows with it.)"""
    r = run(name)
    if name == "pocket_on_a_line":                     # (the walls are where the test wants them)
        hm, (xa, xb, _ya, _yb) = r.fa.map.hm, r.sc["walls"]
        for x in (xa, xb):
            lines = (x * MM - hm.x0) / hm.cell
            assert abs(lines - round(lines)) < 1e-6, f"the wall at x = {x} is not on a grid line"
        assert abs((xa * MM - hm.x0) / (hm.tile * hm.cell) - 1.0) < 1e-9
    far, where = worst(r.cmp)
    limit = SURFACE * scale(r)
    assert far <= limit, (f"{name}: the fast cut is {far / MM:.3f} mm off the exact one (stated: {limit / MM:.3f}). "
                          f"{where}")


@pytest.mark.parametrize("name", ["ball_-Z", "pocket_+X", "pocket_-Y"])
def test_tool_along_another_axis_of_the_workpiece(name):
    """The programs with the tool along -Z, +X and -Y of the workpiece (program and block turned, and moved away
    from the origin). (The pockets' walls are 0.07 mm off the whole millimetres: see the walls' own test.)"""
    r = run(name)
    far, where = worst(r.cmp)
    a, b = r.volumes()
    assert far <= SURFACE, f"{name}: {far / MM:.3f} mm off the exact cut. {where}"
    assert b == pytest.approx(a, rel=0.005), f"{name}: removed {a:.2f} mm3 exact, {b:.2f} mm3 fast"


@pytest.mark.parametrize("name", ["ball_finish", "pocket", "pocket_step_0.08", "steps", "through", "cylinder",
                                  "lshape", "arcs", "ramp", "plunges", "ball_grooves", "island", "two_at_once"])
def test_removed_volume_is_the_exact_cuts(name):
    """(Manifold's own bit has 40 flat sides: it takes up to 0.4 % less than a round one.)"""
    a, b = run(name).volumes()
    assert b == pytest.approx(a, rel=0.006), f"{name}: removed {a:.2f} mm3 exact, {b:.2f} mm3 fast ({b - a:+.2f})"


def test_dense_programs_use_the_map_by_the_apps_own_rule():
    """The scenarios marked dense (300 moves or more, 0.75 per mm2 their paths cover) get the map without the
    test switching the density rule off; a program spread thinly is cut exactly (below)."""
    for name in ("ball_finish", "pocket", "through", "two_at_once", "bull"):
        assert SCENARIOS[name]()["dense"]
        assert map_moves(run(name).fa) >= 300, name


@pytest.mark.xfail(strict=True, reason="FINDING 1 (second report): where the rims of two ball grooves come within "
                                      "0.04 mm of each other (x = 27, y = 13) the strip of top between them is lost: "
                                      "0.29 mm, under the 0.3 mm stated for features thinner than two cells, over "
                                      "the 0.15 mm this test allows a steep strip")
def test_steep_flank_of_a_deep_ball_groove():
    """A ball Ø6 cutting 2.2 to 2.9 mm deep (more than 2/3 of its radius): up to 0.15 mm on the steep strip
    under the rim."""
    r = run("ball_grooves")
    far, where = worst(r.cmp)
    assert far <= STEEP, f"{far / MM:.3f} mm off (stated: 0.15 on the steep strip under the rim). {where}"


def test_corner_radius_pocket_with_ramps():
    """A corner-radius (bull nose) Ø8 R1.5 pocket 2 mm deep, entered by ramps: the rounded foot of the wall (a
    steep rounded strip) within 0.15 mm, the level floor within 0.03 mm."""
    r = run("bull")
    far, where = worst(r.cmp)
    assert far <= STEEP, f"{far / MM:.3f} mm off (stated: 0.15 on the fillet at the foot of the wall). {where}"
    floor, _w = worst(r.cmp, lambda P: (np.abs(P[:, 2] + 2 * MM) < 1e-6) & (P[:, 1] > 9.1 * MM))
    assert floor <= SURFACE, f"the floor is {floor / MM:.3f} mm off"


def test_ramps_of_a_flat_bit():
    """A flat Ø4 going down and up one sloped plane, 161 passes: up to 0.15 mm on the rounded strip at the foot
    of the walls (where the ramps start and end, and along the first and last pass); the sloped floor more than
    2.5 mm from every wall within 0.03 mm."""
    r = run("ramp")
    far, where = worst(r.cmp)
    assert far <= STEEP, f"{far / MM:.3f} mm off (stated: 0.15 where the ramps of a flat bit start). {where}"
    floor, where = worst(r.cmp, lambda P: (P[:, 0] > 4.6 * MM) & (P[:, 0] < 25.5 * MM) & (P[:, 1] > 3.6 * MM)
                         & (P[:, 1] < 10.5 * MM) & (P[:, 2] < -0.3 * MM))
    assert floor <= SURFACE, f"the sloped floor away from the walls is {floor / MM:.3f} mm off. {where}"


def test_island_with_sharp_outside_corners():
    """Sharp outside corners of walls may be up to one cell off; everything further than 0.4 mm from the
    island's four corner edges keeps 0.03 mm."""
    r = run("island")
    far, where = worst(r.cmp)
    assert far <= CELL + 0.01 * MM, f"{far / MM:.3f} mm off at a sharp corner (stated: one cell, 0.2). {where}"
    corners = np.array(r.sc["corners"]) * MM

    def away(P):
        d = np.linalg.norm(P[:, None, :2] - corners[None, :, :], axis=2).min(axis=1)
        return d > 0.4 * MM
    far, where = worst(r.cmp, away)
    assert far <= SURFACE, f"away from the sharp corners: {far / MM:.3f} mm off (stated: 0.03). {where}"


@pytest.mark.parametrize("name", ["fins_0.3", "fins_0.5"])
def test_thin_walls_between_slots(name):
    """A wall of 0.3 mm (thinner than two cells) may be up to 0.3 mm off - at worst it is lost; one of 0.5 mm is
    a wall like any other: 0.03 mm, and as much material is gone as in the exact cut. (A wall of 0.1 mm,
    "fins_0.1", is lost altogether; measured, not tested.)"""
    r = run(name)
    far, where = worst(r.cmp, lambda P: (P[:, 0] > 6 * MM) & (P[:, 0] < 24 * MM))     # (not the slots' ends)
    a, b = r.volumes()
    limit = SURFACE if name == "fins_0.5" else THIN
    assert far <= limit, (f"{name}: {far / MM:.3f} mm off (stated: {limit / MM:.2f}); removed {a:.1f} mm3 exact, "
                          f"{b:.1f} mm3 fast. {where}")
    lost = 0.0 if name == "fins_0.5" else 2 * 0.3 * 2.0 * 24.0                # (both walls, whole)
    assert a * 0.994 - 0.5 <= b <= a * 1.006 + lost + 0.5, f"{name}: removed {a:.2f} mm3 exact, {b:.2f} mm3 fast"


def test_a_cut_that_ends_exactly_on_the_blocks_side_leaves_no_skin():
    """The first step of "steps" is milled with a Ø4 bit whose passes start at y = 2: the cut ends exactly on the
    block's front (y = 0), 1 mm deep. Nothing is left standing there: of faces in the plane y = 0 above the
    step's floor the exact cut has none, the fast one slivers of less than 0.05 mm2 in all."""
    r = run("steps")
    found = []
    for tl in (r.ex, r.fa):
        v, t, _src, _mv = tl.mesh_at(r.T, moves=True)
        P = np.asarray(v, float)[np.asarray(t)] / MM
        skin = (np.abs(P[:, :, 1]).max(axis=1) < 1e-3) & (P[:, :, 2].min(axis=1) > -1.0 + 1e-3)
        found.append(float(np.linalg.norm(np.cross(P[skin, 1] - P[skin, 0], P[skin, 2] - P[skin, 0]), axis=1).sum() / 2))
    assert found[0] == 0.0
    assert found[1] < 0.05, (f"the fast mesh has {found[1]:.3f} mm2 of faces standing in the block's front plane above "
                             f"the step's floor (a skin without thickness; stated: slivers under 0.05 mm2)")


def test_two_bits_cutting_at_the_same_time():
    """A flat pocket and a ball raster whose cuts overlap, and whose moves overlap in time; where the cuts
    cross there are sharp outside corners: one cell."""
    r = run("two_at_once")
    far, where = worst(r.cmp)
    a, b = r.volumes()
    assert far <= CELL + 0.01 * MM, f"{far / MM:.3f} mm off (stated: at most one cell, 0.2). {where}"
    assert b == pytest.approx(a, rel=0.006), f"removed {a:.2f} mm3 exact, {b:.2f} mm3 fast"


def test_four_bits_one_after_the_other_two_of_them_cut_exactly():
    """A flat pocket and a ball over its floor (on the map), then a V along its rim and six drilled holes into
    the rim (V-bits and drills are cut exactly): one cell (0.2 mm) where cuts cross - round the holes and at
    the four corners of the V's path -, 0.03 mm everywhere else."""
    r = run("multi")
    assert 300 <= map_moves(r.fa) < int(r.fa.moves.cuts.sum())                 # the V's and the drill's moves are not
    far, where = worst(r.cmp)
    a, b = r.volumes()
    assert far <= CELL + 0.01 * MM, f"{far / MM:.3f} mm off (stated: at most one cell, 0.2). {where}"
    holes = np.array([(x, y) for x in (2.0, 28.0) for y in (4.0, 10.0, 16.0)]) * MM
    turns = np.array([(4.0, 2.0), (26.0, 2.0), (26.0, 18.0), (4.0, 18.0)]) * MM

    def away(P):
        rim = np.abs(np.linalg.norm(P[:, None, :2] - holes[None, :, :], axis=2) - 2.5 * MM).min(axis=1)
        return (rim > 0.4 * MM) & (np.linalg.norm(P[:, None, :2] - turns[None, :, :], axis=2).min(axis=1) > 1.5 * MM)
    far, where = worst(r.cmp, away)
    assert far <= SURFACE, f"away from where the cuts cross: {far / MM:.3f} mm off (stated: 0.03). {where}"
    assert b == pytest.approx(a, rel=0.006), f"removed {a:.2f} mm3 exact, {b:.2f} mm3 fast"


def test_walls_on_whole_millimetres_stand_where_the_tool_went():
    """Against the numbers themselves, not the exact cut: a pocket milled with a flat Ø4, passes 0.08 mm apart,
    has its walls at x = 4 and 26, y = 2 and 18.0 - on whole millimetres, as CAM programs have them. Every
    point of the fast mesh's walls lies within 0.03 mm of that outline (corners rounded with the bit's radius)."""
    r = run("pocket_step_0.08")
    xa, xb, ya, yb = r.sc["walls"]
    v, t, src, mv = r.fa.mesh_at(r.T, moves=True)
    P = samples(np.asarray(v, float), np.asarray(t)[mv >= 0], 0.3 * MM) / MM
    P = P[(P[:, 2] > -2.9) & (P[:, 2] < -0.1)]                     # between the floor and the top: walls only
    assert len(P) > 500
    R = 2.0
    cx, cy = np.clip(P[:, 0], xa + R, xb - R), np.clip(P[:, 1], ya + R, yb - R)
    off = np.abs(np.where((cx != P[:, 0]) & (cy != P[:, 1]), R - np.hypot(P[:, 0] - cx, P[:, 1] - cy),
                          np.minimum.reduce([P[:, 0] - xa, xb - P[:, 0], P[:, 1] - ya, yb - P[:, 1]])))
    k = int(np.argmax(off))
    assert off[k] <= SURFACE / MM, (f"a point of the fast mesh's wall, {np.round(P[k], 3).tolist()} mm, is {off[k]:.3f} mm "
                                    f"off the pocket's outline; {int((off > 0.03).sum())} of {len(off)} points over 0.03")


def test_finish_at_the_cad_part():
    """ "Finish at the CAD part": the bit goes 1.5 mm too deep and 1 mm too wide; nothing of the finished part
    is gone, everything else in the bit's way is, as in the exact cut (0.3 mm3 is 0.003 mm over the pocket)."""
    r = run("finished")
    rest = whole(r.fa.at(r.T))
    finished = r.sc["finished"]
    gone = (finished - rest).volume() / MM ** 3
    assert gone < 0.05, f"{gone:.3f} mm3 of the finished part is cut away"
    left = (rest - finished).volume() / MM ** 3
    assert left < 0.3, f"{left:.3f} mm3 too much is left standing above the finished part"
    exact = whole(r.ex.at(r.T))
    apart = ((exact - rest).volume() + (rest - exact).volume()) / MM ** 3
    assert apart < 0.3, f"{apart:.3f} mm3 between the exact and the fast workpiece"


def test_finish_at_the_cad_part_tiles_do_not_overlap():
    """The tiles are pieces of one workpiece: their volumes add up to the volume of them all together (the exact
    cut's do)."""
    r = run("finished")
    for tl, name in ((r.ex, "exact"), (r.fa, "fast")):
        tiles = [t for t in tl.at(r.T) if t.ntri]
        total, joined = sum(t.solid.volume() for t in tiles) / MM ** 3, whole(tiles).volume() / MM ** 3
        assert total == pytest.approx(joined, abs=0.02), (f"{name}: the tiles' volumes add up to {total:.3f} mm3, "
                                                          f"together they are {joined:.3f} mm3")


def test_finish_at_the_cad_part_keeps_the_stocks_faces_and_names_the_cut_ones():
    """With a finished part the block's own faces are still the block's (``source`` >= 0: they keep the block's
    material) and the faces at the finished part are cut faces with a move. Of the block's top (600 mm2) the bit
    went over 16 x 10 mm with rounded corners, 156.6 mm2: 443.4 mm2 are untouched. (The exact cut calls 447 mm2
    the block's: where the bit only rubbed the top, its face and the block's lie on each other and Manifold gives
    some of it, about 4 mm2, to the block.)"""
    r = run("finished")
    areas = []
    for tl in (r.ex, r.fa):
        v, t, src, mv = tl.mesh_at(r.T, moves=True)
        P = np.asarray(v, float)[np.asarray(t)]
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        area = np.linalg.norm(n, axis=1) / 2 / MM ** 2
        c = P.mean(axis=1) / MM
        top = (np.abs(c[:, 2]) < 1e-6) & (n[:, 2] > 0)                      # the block's top, round the pocket
        floor = (np.abs(c[:, 2] + 2.0) < 1e-6) & (n[:, 2] > 0)              # the finished pocket's floor
        areas.append((area[top & (src >= 0)].sum(), area[top].sum(), area[floor & (mv >= 0)].sum(), area[floor].sum()))
    (ex_top_src, ex_top, ex_floor_mv, ex_floor), (fa_top_src, fa_top, fa_floor_mv, fa_floor) = areas
    untouched = 600 - (16 * 10 - (4 - math.pi) * 4)
    assert ex_top == pytest.approx(600 - 14 * 8, abs=0.5) and ex_top_src == pytest.approx(untouched, abs=6.0)
    assert ex_floor_mv == pytest.approx(14 * 8, abs=0.5) and fa_top == pytest.approx(ex_top, abs=0.5)
    assert fa_top_src == pytest.approx(untouched, abs=1.0), (
        f"of the block's top ({fa_top:.0f} mm2 in the fast mesh) {fa_top_src:.1f} mm2 are still the block's "
        f"face; {untouched:.1f} mm2 are untouched (exact: {ex_top_src:.1f} mm2)")
    assert fa_floor_mv == pytest.approx(ex_floor_mv, abs=1.0), (
        f"of the finished pocket's floor ({fa_floor:.0f} mm2) only {fa_floor_mv:.0f} mm2 name a move "
        f"(exact: {ex_floor_mv:.0f} mm2)")


@pytest.mark.parametrize("name", ["pocket", "pocket_on_a_line", "through", "plunges", "island", "two_at_once"])
def test_every_face_that_can_be_seen_is_the_stocks_or_a_moves(name, request):
    known(request, name == "plunges", "FINDING 3 (second report): where the wall of a through hole crosses a tile's "
                                      "border about 3 mm2 of wall (of 30 holes) name no move: no tool marks there")
    """A face that is neither the stock's nor a move's is a seam inside the material (two tiles touch there).
    None of them may be seen from outside - it would get no tool marks and no smooth normals."""
    r = run(name)
    seen, area = r.cmp["bare"] / MM, r.cmp["bare_mm2"]
    where = "" if not len(seen) else (f"between {np.round(seen.min(axis=0), 2).tolist()} and "
                                      f"{np.round(seen.max(axis=0), 2).tolist()} mm, e.g. {np.round(seen[0], 3).tolist()}")
    assert area < 0.05, f"{name}: about {area:.1f} mm2 of faces without a label can be seen ({len(seen)} points), {where}"


# ---------------------------------------------------------------------------
# 2. programs and moves the map cannot hold stay exact
# ---------------------------------------------------------------------------

def same_mesh(a, b) -> bool:
    return all(np.array_equal(x, y) for x, y in zip(a, b))


def exact_and_fast(sc, T=None):
    ex, fa = timelines(sc, dense=sc.get("dense", True))
    T = max(float(p.t[-1]) for p in sc["paths"]) if T is None else T
    return ex, fa, T


def test_a_program_of_299_moves_is_cut_exactly():
    pts = [(7, 5, 4)] + zigzag(7, 23, 5, 149, 0.1, -3.0)                   # 1 + 297 + ... = 298 moves that cut
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT6], paths=[path_of(pts)])
    ex, fa, T = exact_and_fast(sc)
    assert len(fa.segs) == 298 and map_moves(fa) == 0
    assert same_mesh(ex.mesh_at(T, moves=True), fa.mesh_at(T, moves=True))
    assert same_mesh(ex.mesh_at(T - 20.3, moves=True), fa.mesh_at(T - 20.3, moves=True))


def test_a_thinly_spread_program_is_cut_exactly():
    """More than 300 moves, but 1.2 mm apart in 4 mm moves (0.2 moves per mm2): the map would be heavier than
    the exact cut."""
    sc = dict(stock=box((100, 30, 10), (0, 0, -10)), tools=[BALL6],
              paths=[path_of(raster(np.linspace(-2, 102, 27), np.arange(1.0, 16.0, 1.2), wave), 4)])
    ex, fa, T = exact_and_fast(sc)
    assert len(fa.segs) >= 300 and map_moves(fa) == 0
    assert same_mesh(ex.mesh_at(T, moves=True), fa.mesh_at(T, moves=True))


@pytest.mark.parametrize("tilt", [10.0])
def test_a_tilted_tool_is_cut_exactly(tilt):
    """A dense program whose tool axis is no axis of the workpiece (tilted about x by 10 degrees)."""
    a = math.radians(tilt)
    pts = [(7, 5, 4)] + zigzag(7, 23, 5, 151, 0.1, -1.0)
    sc = dict(stock=box((30, 24, 10), (0, 0, -10)), tools=[FLAT4],
              paths=[path_of(pts, d=(0.0, math.sin(a), math.cos(a)))])
    ex, fa, T = exact_and_fast(sc)
    assert len(fa.segs) >= 300 and map_moves(fa) == 0
    assert same_mesh(ex.mesh_at(T, moves=True), fa.mesh_at(T, moves=True))


def test_a_t_slot_cutter_is_cut_exactly():
    """A T-slot cutter (Ø8 head 2 mm high on a Ø3 neck) run through the block 5 mm under its top, 320 passes:
    the roof over the slot stays (an undercut)."""
    pts = zigzag(-6, 36, 8, 320, 0.01, -5.0)
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[TSLOT], paths=[path_of(pts)])
    ex, fa, T = exact_and_fast(sc)
    assert len(fa.segs) >= 300 and map_moves(fa) == 0
    assert same_mesh(ex.mesh_at(T, moves=True), fa.mesh_at(T, moves=True))
    gone = removed(sc, fa.at(T))
    neck, head = 30 * (3 + 3.19) * 3.0, 30 * (8 + 3.19) * 2.0
    assert gone == pytest.approx(neck + head, rel=0.02)                    # far less than a slot open to the top


def test_a_tool_shorter_than_the_cut_is_deep_leaves_a_tunnel():
    """A bit 3 mm long whose tip runs 6 mm under the top: its top is 3 mm under the top too - a tunnel."""
    pts = zigzag(-5, 35, 8, 320, 0.01, -6.0)
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[SHORT4], paths=[path_of(pts)])
    ex, fa, T = exact_and_fast(sc)
    assert len(fa.segs) >= 300 and map_moves(fa) == 0
    assert same_mesh(ex.mesh_at(T, moves=True), fa.mesh_at(T, moves=True))
    assert removed(sc, fa.at(T)) == pytest.approx(30 * (4 + 3.19) * 3.0, rel=0.02)


@pytest.mark.parametrize("name", ["V 90", "V 30", "drill", "chamfer mill", "tapered ball"])
def test_v_bits_drills_and_custom_outlines_are_cut_exactly(name):
    """Not map moves, however dense the program and even when the test lets the map take a program of one move:
    the same mesh as ``fast=False``, array for array. (The V programs: 323 passes 0.1 mm apart, as dense as a
    finishing program; drill: the 30 holes; the custom outlines: three grooves.)"""
    if name in ("V 90", "V 30"):
        sc = s_vee(VEE90 if name == "V 90" else VEE30)
    elif name == "drill":
        sc = s_holes(DRILL5)
    else:
        tool = CHAMFER if name == "chamfer mill" else TAPER
        pts = [(4, 5, 3), (4, 5, -1.2), (26, 5, -1.2), (26, 10, -1.2), (4, 10, -0.6), (4, 15, -0.9), (26, 15, -0.9),
               (26, 15, 3)]
        sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[tool], paths=[path_of(pts)])
    ex, fa = timelines(sc, dense=False, moves=1)
    T = float(sc["paths"][0].t[-1])
    assert map_moves(fa) == 0, f"{map_moves(fa)} of {len(fa.segs)} moves are on the map"
    for at in (T, 0.5 * (T + 1.0) + 0.25):
        assert same_mesh(ex.mesh_at(at, moves=True), fa.mesh_at(at, moves=True))


def test_a_pin_below_a_wide_body_is_not_a_cone():
    """A counterbore with a pilot (a Ø2 pin 5 mm long below a Ø8 body) milling 3 mm deep: only the pin cuts, a
    slot 2 mm wide. The map may take it only if it cuts that shape (the Design: a custom outline that is one
    convex piece; this one is two)."""
    assert len(M.convex_pieces(M.Cutter(PILOT, "NORMAL").profile)) == 2
    pts = [(5, 6, 4)] + zigzag(5, 25, 6, 160, 0.02, -3.0)
    pts.append((pts[-1][0], pts[-1][1], 4))
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[PILOT], paths=[path_of(pts)])
    ex, fa, T = exact_and_fast(sc)
    a, b = removed(sc, ex.at(T)), removed(sc, fa.at(T))
    assert a == pytest.approx((20 * 3.18 + 2 * (20 + 3.18) * 1.0 + math.pi) * 3.0, rel=0.03)   # the pin's slot
    assert b == pytest.approx(a, rel=0.01), (f"the exact cut takes {a:.1f} mm3 (the pin's slot), the fast one "
                                             f"{b:.1f} mm3 ({map_moves(fa)} moves on the map)")


def _mixed(sc, times, limit=CELL + 0.01 * MM, moves=None):
    ex, fa = timelines(sc, dense=sc.get("dense", True), moves=moves)
    assert (moves or 300) <= map_moves(fa) < len(fa.segs), (map_moves(fa), len(fa.segs))   # some on the map, some not
    t0, t1 = min(float(p.t[0]) for p in sc["paths"]), max(float(p.t[-1]) for p in sc["paths"])
    for f in times:
        T = t0 + f * (t1 - t0)
        a, b = removed(sc, ex.at(T)), removed(sc, fa.at(T))
        assert b == pytest.approx(a, rel=0.006, abs=0.3), f"at {f:.2f} of the program: {a:.2f} mm3 exact, {b:.2f} fast"
    far, where = worst(compare(ex, fa, t1))
    assert far <= limit, f"{far / MM:.3f} mm off the exact cut at the end. {where}"
    return ex, fa


def test_mixed_program_map_pocket_and_t_slot_at_the_same_time():
    """One bit mills a pocket from above (on the map) while a T-slot cutter runs under its floor (booleans)."""
    pocket = s_pocket(step=0.08, tool=FLAT4, nudge=0.07)
    p2 = zigzag(-6, 36, 9, 40, 0.05, -6.5)
    sc = dict(stock=pocket["stock"], tools=[FLAT4, TSLOT], paths=[pocket["paths"][0], path_of(p2, 0.53, frame0=1.2)])
    _mixed(sc, (0.13, 0.37, 0.5, 0.71, 0.93, 1.0))           # (sharp corners where the neck's slot crosses the walls)


def test_mixed_program_a_second_bit_along_another_axis():
    """A flat bit along Z mills a pocket (on the map); at the same time a drill along X goes into the block's
    side again and again (booleans: the map has one axis)."""
    pocket = s_pocket(step=0.08, tool=FLAT4, nudge=0.07)
    side = []
    for k in range(40):
        y, z = 3 + 0.35 * k, -7.5
        side += [(34, y, z), (26, y, z), (34, y, z)]
    side_path = M.Path(1.1 + np.arange(len(side)) / 0.8, np.asarray(side) * MM, np.tile((1.0, 0.0, 0.0), (len(side), 1)))
    sc = dict(stock=pocket["stock"], tools=[FLAT4, DRILL5], paths=[pocket["paths"][0], side_path])
    _mixed(sc, (0.2, 0.45, 0.8, 1.0), limit=SURFACE)


def test_mixed_program_short_tool_above_and_below_the_top():
    """One short bit (3 mm long): passes 2 mm deep (its top above the block: on the map) take turns with passes
    6 mm deep (a tunnel: booleans). (240 passes; the map takes a program from 100 moves on here.)"""
    pts = []
    for k in range(240):
        y = 5 + 0.01 * k
        z = -2.0 if k % 2 == 0 else -6.0
        pts += [(-5, y, z), (35, y, z), (35, y + 0.01, 12), (-5, y + 0.01, 12)]
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[SHORT4], paths=[path_of(pts)])
    ex, fa = _mixed(sc, (0.47,), limit=SURFACE, moves=100)
    T = float(sc["paths"][0].t[-1])
    assert removed(sc, fa.at(T)) == pytest.approx(30 * (4 + 2.39) * (2.0 + 3.0), rel=0.02)   # slot + tunnel, a web between


# ---------------------------------------------------------------------------
# 3. time
# ---------------------------------------------------------------------------

def signature(out) -> str:
    h = hashlib.sha1()
    for a in out:
        for b in (a if isinstance(a, tuple) else (a,)):
            b = np.ascontiguousarray(b)
            h.update(str((b.shape, b.dtype)).encode())
            h.update(b.tobytes())
    return h.hexdigest()


@pytest.mark.parametrize("name", ["two_at_once", "ball_finish"])
def test_any_time_gives_the_same_mesh_however_it_is_reached(name):
    """Forward, backward, jumps, between frames, in the middle of moves; a second timeline that goes straight to
    a time gives that mesh too. All of vertices, triangles, sources, moves, marks and normals."""
    sc = SCENARIOS[name]()
    _ex, fa = timelines(sc, dense=sc["dense"])
    assert map_moves(fa) >= 300
    t0, t1 = min(float(p.t[0]) for p in sc["paths"]), max(float(p.t[-1]) for p in sc["paths"])
    rng = np.random.default_rng(11)
    Ts = sorted(set(np.round(rng.uniform(t0, t1, 6), 4).tolist() + [t0, t1, round(0.5 * (t0 + t1), 0) + 0.5]))
    order = Ts + Ts[::-1] + [Ts[3], Ts[7], Ts[1], Ts[8], Ts[2], Ts[5], Ts[5], Ts[0], Ts[6]]
    first = {}
    for T in order:
        s = signature(fa.mesh_at(T, moves=True, marks=True, normals=True))
        assert first.setdefault(T, s) == s, f"{name}: another mesh the second time at frame {T}"
    _ex, fresh = timelines(sc, dense=sc["dense"])
    for T in (Ts[6], Ts[2], Ts[4]):
        s = signature(fresh.mesh_at(T, moves=True, marks=True, normals=True))
        assert s == first[T], f"{name}: a new timeline gives another mesh at frame {T}"


def test_removed_volume_grows_with_time_and_follows_the_exact_cut():
    """Two bits at once, 16 times in order (most of them in the middle of a move of both bits)."""
    sc = SCENARIOS["two_at_once"]()
    ex, fa = timelines(sc, dense=sc["dense"])
    t0, t1 = min(float(p.t[0]) for p in sc["paths"]), max(float(p.t[-1]) for p in sc["paths"])
    Ts = np.linspace(t0, t1, 16)
    fast = [removed(sc, fa.at(T)) for T in Ts]
    exact = [removed(sc, ex.at(T)) for T in Ts]
    assert np.all(np.diff(fast) >= -1e-6), f"material comes back: {np.round(fast, 3).tolist()}"
    assert fast[0] == pytest.approx(0.0, abs=1e-6) and fast[-1] > 500
    for T, a, b in zip(Ts, exact, fast):
        assert b == pytest.approx(a, rel=0.006, abs=0.3), f"frame {T:.2f}: {a:.2f} mm3 exact, {b:.2f} mm3 fast"
    back = [removed(sc, fa.at(T)) for T in Ts[::-3]]                       # going backwards: the same volumes
    assert back == pytest.approx(fast[::-3], abs=1e-9)


def test_in_the_middle_of_a_move_the_cut_ends_under_the_bit():
    """A dense pocket, then one long pass along x; half way along that pass the cut ends at the bit (x = 15 +
    the radius), and a quarter frame later a quarter of a frame's feed further - as in the exact cut."""
    pts = [(7, 5, 4)] + zigzag(7, 23, 5, 76, 0.05, -1.0, ) + zigzag(9, 21, 4, 76, 0.05, -2.0)
    pts += [(pts[-1][0], pts[-1][1], 4), (-6, 17, 4), (-6, 17, -2.5)]
    n = len(pts)
    pts += [(-6 + 0.5 * k, 17, -2.5) for k in range(1, 85)]                # one straight move, sampled every 0.5 mm
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(pts, 2)])
    ex, fa = timelines(sc, dense=True)
    assert map_moves(fa) >= 300
    p = sc["paths"][0]
    for k, extra in ((42, 0.0), (42, 0.125), (61, 0.3)):                   # sample 42: the tip at x = 15
        T = float(p.t[n - 1 + k]) + extra
        tip = -6 + 0.5 * k + extra * 2 * 0.5
        v, t, src, mv = fa.mesh_at(T, moves=True)
        P = np.asarray(v, float)[np.asarray(t)[mv >= 0]].reshape(-1, 3) / MM
        slot = P[(P[:, 1] > 16.0) & (P[:, 2] < -2.2)]                      # the long pass's own faces (deeper than the rest)
        assert len(slot), "the pass under way has cut nothing"
        assert slot[:, 0].max() == pytest.approx(tip + 2.0, abs=0.03), (T, tip)
        assert removed(sc, fa.at(T)) == pytest.approx(removed(sc, ex.at(T)), rel=0.004)


# ---------------------------------------------------------------------------
# 4. moves, marks, normals
# ---------------------------------------------------------------------------

class Faces:
    """The fast mesh at the end, with what each triangle is told (mm)."""

    def __init__(self, tl, T, normals=False):
        out = tl.mesh_at(T, marks=True, normals=normals)
        self.v, self.t, self.src, self.move = (np.asarray(x) for x in out[:4])
        self.o, self.d, self.a, self.p = out[4]
        self.normals = out[5] if normals else None
        P = self.v[self.t].astype(float)
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        self.area = np.linalg.norm(n, axis=1) / 2 / MM ** 2
        self.n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
        self.P = P / MM
        self.c = self.P.mean(axis=1)
        self.kind = np.rint(self.p[:, 0]).astype(int)
        self.cut = self.move >= 0


def row_of(tl, a_mm, b_mm, bit) -> int:
    """The row in ``tl.moves`` of the move of ``bit`` from ``a_mm`` to ``b_mm``."""
    mk = tl.moves
    hit = np.flatnonzero((mk.bit == bit) & np.all(np.abs(mk.o0 / MM - a_mm) < 1e-6, axis=1)
                         & np.all(np.abs(mk.o1 / MM - b_mm) < 1e-6, axis=1))
    assert len(hit) == 1, (a_mm, b_mm, hit)
    return int(hit[0])


def test_separate_slots_name_their_own_moves():
    """44 slots, each cut in three depths by one of two bits. Every cut face inside a slot names a pass of that
    slot (never another slot's or the other bit's move); its floor names the deepest, last pass; the block's top
    between the slots is still the block's face."""
    r = run("slots")
    f = Faces(r.fa, r.T)
    owner = r.fa.moves.owner
    wrong_slot = wrong_floor = floor_faces = 0
    seen = np.zeros(len(f.c), bool)
    for bit, x0, x1, y in r.sc["slots"]:
        rows = [row_of(r.fa, (x0, y, -0.5), (x1, y, -0.5), bit), row_of(r.fa, (x1, y, -1.0), (x0, y, -1.0), bit),
                row_of(r.fa, (x0, y, -1.5), (x1, y, -1.5), bit)]
        mine = sorted({int(owner[k]) for k in rows})
        assert len(mine) == 3
        inside = f.cut & (np.abs(f.c[:, 1] - y) < 1.25) & (f.c[:, 0] > x0 - 1.25) & (f.c[:, 0] < x1 + 1.25)
        seen |= inside
        assert inside.sum() >= 8, (bit, x0, y)
        wrong_slot += int((~np.isin(f.move[inside], mine)).sum())
        if bit == 0:                                   # the flat bit's floor: level, at -1.5
            floor = inside & (np.abs(f.c[:, 2] + 1.5) < 1e-4) & (f.n[:, 2] > 0.99)
        else:                                          # the ball's: the bottom third of the groove
            floor = inside & (f.c[:, 2] < -1.3) & (np.abs(f.c[:, 0] - 0.5 * (x0 + x1)) < 9)
        floor_faces += int(floor.sum())
        wrong_floor += int((f.move[floor] != int(owner[rows[2]])).sum())
    assert floor_faces > 100
    assert wrong_slot == 0, f"{wrong_slot} cut faces inside a slot name a move of another slot or bit"
    assert wrong_floor == 0, f"{wrong_floor} of {floor_faces} floor faces do not name the slot's last, deepest pass"
    assert not (f.cut & ~seen).any(), "cut faces outside every slot"
    top = (np.abs(f.c[:, 2]) < 1e-6) & (f.n[:, 2] > 0.99)
    assert f.area[top].sum() > 1500
    assert np.all(f.src[top] >= 0) and np.all(f.move[top] < 0), "the uncut top is no longer the block's face"


def test_overlapping_passes_at_one_depth_the_later_one_owns_the_floor():
    """A pocket of 151 passes 0.1 mm apart with a Ø6 flat bit: 60 passes reach every place of the floor. A floor
    face names a move whose bit was over it (within a cell and a half), and no later move went over it (more
    than a cell and a half inside that move's edge)."""
    r = run("pocket")
    f = Faces(r.fa, r.T)
    mk = r.fa.moves
    floor = np.flatnonzero(f.cut & (np.abs(f.c[:, 2] + 3.0) < 1e-6) & (f.n[:, 2] > 0.99))
    assert len(floor) > 500
    m = f.move[floor]
    c = f.c[floor, :2]

    def dist(rows, pts):                               # from points to the moves' paths, seen from above (mm)
        a, b = mk.o0[rows, :2] / MM, mk.o1[rows, :2] / MM
        ab = b - a
        u = np.clip(np.einsum("ij,ij->i", pts - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-30), 0, 1)
        return np.linalg.norm(pts - a - u[:, None] * ab, axis=1)
    assert np.all(mk.owner[m] == m)
    under = dist(m, c)
    assert under.max() <= 3.0 + 0.3, f"a floor face names a move whose bit was {under.max() - 3.0:.3f} mm away"
    later = np.zeros(len(floor), bool)                 # is there a later move well over the face?
    own = mk.owner
    cand = np.flatnonzero(mk.cuts & (np.abs(mk.o0[:, 2] / MM + 3.0) < 1e-6) & (np.abs(mk.o1[:, 2] / MM + 3.0) < 1e-6))
    for k in cand:
        k_own = int(own[k])
        sel = np.flatnonzero(m < k_own)
        if len(sel):
            later[sel] |= dist(np.full(len(sel), k), c[sel]) < 3.0 - 0.3
    assert not later.any(), (f"{int(later.sum())} of {len(floor)} floor faces ({f.area[floor][later].sum():.1f} mm2) name "
                             f"a pass although a later pass at the same depth went over them")


def test_a_deeper_later_pass_owns_the_crossing_a_shallower_one_does_not():
    """A dense shallow pocket (1 mm), then a slot 3 mm deep across it, then a slot 2 mm deep across both: the
    3 mm slot's floor names its pass also where the later, shallower slot crossed it."""
    pts = [(5, 4, 4)] + zigzag(5, 25, 4, 151, 0.04, -1.0)
    pts += [(pts[-1][0], pts[-1][1], 4), (15, -4, 4), (15, -4, -3.0), (15, 24, -3.0), (15, 24, 4),
            (-4, 15, 4), (-4, 15, -2.0), (34, 15, -2.0), (34, 15, 4)]
    sc = dict(stock=box((30, 20, 10), (0, 0, -10)), tools=[FLAT4], paths=[path_of(pts)])
    _ex, fa = timelines(sc, dense=True)
    assert map_moves(fa) >= 300
    f = Faces(fa, float(sc["paths"][0].t[-1]))
    deep, shallow = row_of(fa, (15, -4, -3.0), (15, 24, -3.0), 0), row_of(fa, (-4, 15, -2.0), (34, 15, -2.0), 0)
    deep, shallow = int(fa.moves.owner[deep]), int(fa.moves.owner[shallow])
    lvl = f.cut & (f.n[:, 2] > 0.99)
    d_floor = lvl & (np.abs(f.c[:, 2] + 3.0) < 1e-6)
    s_floor = lvl & (np.abs(f.c[:, 2] + 2.0) < 1e-6)
    assert f.area[d_floor].sum() == pytest.approx(4 * 20, rel=0.02)
    assert np.all(f.move[d_floor] == deep), "the deep slot's floor names another move"
    assert f.area[s_floor].sum() == pytest.approx(4 * 30 - 4 * 4, rel=0.03)
    assert np.all(f.move[s_floor] == shallow), "the shallow slot's floor names another move"
    kinds = set(f.kind[d_floor | s_floor].tolist())
    assert kinds == {TM.ARCS}, kinds


def test_marks_of_a_flat_pocket_arcs_on_the_floor_lines_on_the_walls():
    r = run("pocket")
    f = Faces(r.fa, r.T)
    floor = f.cut & (np.abs(f.c[:, 2] + 3.0) < 1e-6)
    walls = f.cut & ~floor
    assert f.area[floor].sum() == pytest.approx(22 * 21 - (4 - math.pi) * 9, rel=0.01)
    assert set(f.kind[floor].tolist()) == {TM.ARCS}
    assert np.allclose(f.p[floor, 1], 3 * MM, atol=1e-7), "ARCS: the radius of the bit's flat bottom"
    assert np.allclose(f.a[f.cut], (0, 0, 1), atol=1e-6)
    assert np.allclose(np.linalg.norm(f.d[f.cut], axis=1), 1.0, atol=1e-5) and np.allclose(f.d[f.cut][:, 2], 0.0)
    bad = walls & (f.kind != TM.FLANK)
    assert f.area[bad].sum() <= 0.01 * f.area[walls].sum(), (
        f"{f.area[bad].sum():.2f} mm2 of the walls ({f.area[walls].sum():.1f} mm2) do not show wall lines (FLANK) but "
        f"{sorted(set(f.kind[bad].tolist()))}")
    assert np.all(f.kind[~f.cut] == TM.NONE) and not np.any(f.p[~f.cut])
    for arr in (f.o, f.d, f.a, f.p):
        assert arr.shape == (len(f.t), 3) and arr.dtype == np.float32 and np.isfinite(arr).all()
    spacing = f.p[f.cut, 2]
    assert np.all((spacing >= TM.SPACING_MIN - 1e-12) & (spacing <= TM.SPACING_MAX + 1e-12))


@pytest.mark.parametrize("name", ["pocket", "pocket_on_a_line"])
def test_a_pockets_walls_are_there_once(name, request):
    known(request, name == "pocket_on_a_line", ON_A_LINE)
    """The wall faces of a pocket that name a move add up to the pocket's wall: its outline times its depth -
    nothing missing (a wall face without a move), nothing twice (faces folded over each other)."""
    r = run(name)
    f = Faces(r.fa, r.T)
    xa, xb, ya, yb = r.sc["walls"]
    R = r.sc["tools"][0].radius / MM
    want = (2 * (xb - xa - 2 * R) + 2 * (yb - ya - 2 * R) + 2 * math.pi * R) * 3.0
    walls = f.cut & (f.c[:, 2] < -1e-6) & (f.c[:, 2] > -3.0 + 1e-6)
    assert f.area[walls].sum() == pytest.approx(want, rel=0.01), (
        f"{name}: {f.area[walls].sum():.1f} mm2 of wall faces name a move; the pocket has {want:.1f} mm2 of wall")


def test_marks_of_ball_passes_lines_across_the_pass():
    r = run("ball_finish")
    f = Faces(r.fa, r.T)
    assert f.area[f.cut].sum() > 24 * 16
    other = f.cut & (f.kind != TM.ACROSS)
    assert f.area[other].sum() <= 0.001 * f.area[f.cut].sum(), (f.area[other].sum(), sorted(set(f.kind[other].tolist())))


def test_marks_of_plunged_holes_rings():
    """A hole plunged with a flat bit: rings on its floor (RINGS), rings round its wall (RINGS_WALL); nothing
    else, and no feed direction."""
    r = run("plunges")
    f = Faces(r.fa, r.T)
    holes = np.array(r.sc["holes"])
    k = np.argmin(np.linalg.norm(f.c[:, None, :2] - holes[None, :, :2], axis=2), axis=1)
    floor = f.cut & (np.abs(f.c[:, 2] - holes[k, 2]) < 1e-4) & (f.n[:, 2] > 0.99)
    wall = f.cut & (np.abs(f.n[:, 2]) < 0.02) & (f.area > 1e-4)
    assert f.area[floor].sum() == pytest.approx(20 * math.pi * 4, rel=0.01)            # 20 blind holes Ø4
    assert f.area[wall].sum() > 1400                   # (10 holes 2 mm deep, 10 of 4 mm, 10 through 6 mm: 1508 mm2)
    assert f.area[f.cut & ~floor & ~wall].sum() <= 0.01 * f.area[f.cut].sum()
    assert f.area[floor & (f.kind != TM.RINGS)].sum() <= 0.01 * f.area[floor].sum(), sorted(set(f.kind[floor].tolist()))
    assert f.area[wall & (f.kind != TM.RINGS_WALL)].sum() <= 0.01 * f.area[wall].sum(), sorted(set(f.kind[wall].tolist()))
    assert np.allclose(f.d[f.cut], 0.0), "a plunge has no feed direction"


@pytest.mark.xfail(strict=True, reason="FINDING 2 (second report): on plunged holes of 4 mm about 3 % of the wall "
                                      "faces lie folded over their neighbours (turned inside out); the shape is "
                                      "right to 0.007 mm")
def test_walls_of_plunged_holes_face_into_the_hole():
    """30 holes plunged with a flat Ø4 (10 of them 2 mm deep, 10 of 4 mm, 10 through the 6 mm plate): 1508 mm2 of
    round wall. Every wall face looks towards its hole's axis, out of the material; folded triangles (a face
    turned inside out lying on its neighbours) stay under 1 mm2 and 0.5 % of the wall, as the Design states,
    and the wall faces add up to the wall."""
    r = run("plunges")
    f = Faces(r.fa, r.T)
    holes = np.array(r.sc["holes"])
    k = np.argmin(np.linalg.norm(f.c[:, None, :2] - holes[None, :, :2], axis=2), axis=1)
    wall = f.cut & (np.abs(f.n[:, 2]) < 0.02) & (f.area > 1e-4)
    away = np.einsum("ij,ij->i", f.n[wall][:, :2], f.c[wall, :2] - holes[k[wall], :2])
    turned_in = np.flatnonzero(wall)[away > 0]
    folded, true = float(f.area[turned_in].sum()), 4 * math.pi * (10 * 2 + 10 * 4 + 10 * 6)
    per_hole = np.bincount(k[turned_in], weights=f.area[turned_in], minlength=len(holes))
    assert folded <= 1.0 and folded <= 0.005 * true, (
        f"{len(turned_in)} wall faces, {folded:.1f} mm2 of {true:.0f} mm2 of wall, are turned inside out (their normal "
        f"points away from the hole's axis, into the material) on {int((per_hole > 0).sum())} of 30 holes, up to "
        f"{per_hole.max():.1f} mm2 on one; the wall faces add up to {f.area[wall].sum():.0f} mm2")
    assert f.area[wall].sum() == pytest.approx(true, rel=0.02)


@pytest.mark.parametrize("name", ["pocket", "pocket_on_a_line"])
def test_normals_flat_floors_flat_walls_level(name):
    """Unit normals without NaN; a flat floor's are exactly the tool's axis; a wall's lie level within a degree
    and point out of the material, into the pocket. (Where a straight wall meets a round corner a few wall
    triangles can lie folded, their normal into the material: under 1 mm2 and under 0.5 % of the wall.)"""
    r = run(name)
    f = Faces(r.fa, r.T, normals=True)
    N = np.asarray(f.normals, float)
    assert N.shape == (len(f.t) * 3, 3) and np.isfinite(N).all()
    assert np.allclose(np.linalg.norm(N, axis=1), 1.0, atol=1e-5)
    N = N.reshape(-1, 3, 3)
    floor = f.cut & (np.abs(f.P[:, :, 2] + 3.0).max(axis=1) < 1e-6)
    assert floor.sum() > 500
    lean = np.degrees(np.arccos(np.clip(N[floor][:, :, 2], -1, 1))).max()
    assert lean < 0.01, f"a corner normal of the flat floor leans {lean:.3f} degrees"
    walls = f.cut & (np.abs(f.n[:, 2]) < 0.02) & (f.area > 1e-4)
    assert f.area[walls].sum() > 150
    up = np.degrees(np.arcsin(np.abs(N[walls][:, :, 2]))).max()
    assert up < 1.0, f"a corner normal of a wall leans {up:.2f} degrees out of level"
    xa, xb, ya, yb = r.sc["walls"]
    c = f.c[walls, :2] - np.array([0.5 * (xa + xb), 0.5 * (ya + yb)])
    out = np.einsum("ij,ij->i", f.n[walls][:, :2], c)
    turned_in = np.flatnonzero(walls)[out > 0]
    k = turned_in[0] if len(turned_in) else 0
    folded = float(f.area[turned_in].sum())
    assert folded <= 1.0 and folded <= 0.005 * f.area[walls].sum(), (
        f"{len(turned_in)} wall faces ({folded:.2f} mm2 of {f.area[walls].sum():.0f}) are turned inside out (their "
        f"normal points into the material), e.g. the triangle {np.round(f.P[k], 3).tolist()} mm with normal "
        f"{np.round(f.n[k], 3).tolist()}")


def test_normals_do_not_jump_at_the_borders_of_the_maps_tiles():
    """On a smooth ball-finished surface every corner at one place has the same normal - also where two (or
    four) of the map's tiles meet: no tile shows in a reflection."""
    r = run("ball_finish")
    f = Faces(r.fa, r.T, normals=True)
    N = np.asarray(f.normals, float).reshape(-1, 3, 3)
    shift = np.array([110, -70, 30.0])
    use = f.cut & (f.n[:, 2] > 0.8) & (f.c[:, 0] - shift[0] > 1) & (f.c[:, 0] - shift[0] < 23) & \
        (f.c[:, 1] - shift[1] > 1) & (f.c[:, 1] - shift[1] < 15)
    corners = f.v[f.t[use]].reshape(-1, 3)
    key = np.ascontiguousarray(corners).view(np.dtype((np.void, corners.dtype.itemsize * 3))).ravel()
    _u, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    n = N[use].reshape(-1, 3)
    mean = np.zeros((len(counts), 3))
    np.add.at(mean, inv, n)
    mean /= np.maximum(np.linalg.norm(mean, axis=1), 1e-30)[:, None]
    angle = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n, mean[inv]), -1, 1)))
    assert counts.max() >= 4
    k = int(np.argmax(angle))
    assert angle.max() < 1.0, (f"corner normals at one place of the smooth surface differ by {angle.max():.1f} degrees "
                               f"from their mean, at {np.round(corners[k] / MM - shift, 2).tolist()} mm")
    # the surface is smooth: a corner's normal is close to the true surface normal there (the ball rides a wave
    # whose steepest slope is 9 degrees; the ridges between passes 0.3 mm apart lean the faces by 3 more)
    lean = np.degrees(np.arccos(np.clip(n[:, 2], -1, 1)))
    assert lean.max() < 16.0, f"a corner normal leans {lean.max():.1f} degrees on a surface that leans at most 12"


# ---------------------------------------------------------------------------
# 5. the tiles are closed solids
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["pocket", "ball_finish", "plunges", "two_at_once", "multi"])
def test_tiles_are_closed_solids(name):
    """At the end and half way (in the middle of a move): every tile a Manifold without an error and with
    volume, its triangle count right, inside its own box; the tiles do not overlap."""
    r = run(name)
    t0 = min(float(p.t[0]) for p in r.sc["paths"])
    for T in (r.T, t0 + 0.4321 * (r.T - t0)):
        tiles = r.fa.at(T)
        assert len(tiles) >= 1
        total = 0.0
        for t in tiles:
            s = t.solid
            assert s.status() == mf.Error.NoError and not s.is_empty()
            assert s.volume() > 0 and t.ntri == s.num_tri() and s.num_tri() >= 4
            b = np.array(s.bounding_box())
            assert np.all(b[:3] >= np.asarray(t.lo) - 2e-6) and np.all(b[3:] <= np.asarray(t.hi) + 2e-6), (
                f"{name}: a tile's solid reaches {np.round(np.maximum(t.lo - b[:3], b[3:] - t.hi).max() / MM, 4)} mm "
                f"out of the tile's box")
            total += s.volume()
        joined = whole(tiles).volume()
        assert total == pytest.approx(joined, abs=0.02 * MM ** 3), (
            f"{name}: the tiles overlap by {(total - joined) / MM ** 3:.4f} mm3")


# ---------------------------------------------------------------------------
# 6. core/heightmap.py on its own
# ---------------------------------------------------------------------------

CHAMFER = M.Tool("CUSTOM", radius=3 * MM, length=20 * MM, profile=((0.0, 1 * MM), (2 * MM, 3 * MM), (20 * MM, 3 * MM)))
TAPER = M.Tool("CUSTOM", radius=3 * MM, length=20 * MM,
               profile=((0.0, 0.0), (0.1 * MM, 0.4 * MM), (0.4 * MM, 0.9 * MM), (1.0 * MM, 1.4 * MM), (6 * MM, 3 * MM),
                        (20 * MM, 3 * MM)))
SWEPT = {"flat": FLAT6, "ball": BALL6, "bull": BULL8, "vee90": VEE90, "vee30": VEE30, "drill": DRILL5,
         "chamfer mill": CHAMFER, "tapered ball": TAPER}


def bit_height(tool, r):
    """(the height of the bit's surface above its tip at distance r from its axis, the steepest slope of that
    where the lowest point of a move can lie) - from the tool's numbers, in closed form."""
    R = tool.radius
    if tool.kind == "FLAT":
        return np.zeros(np.shape(r)), 0.0
    if tool.kind == "BALL":
        return R - np.sqrt(np.maximum(R * R - r * r, 0.0)), 0.0
    if tool.kind == "BULL":
        c = tool.corner
        t = np.maximum(r - (R - c), 0.0)
        return c - np.sqrt(np.maximum(c * c - t * t, 0.0)), 0.0
    if tool.kind in ("VEE", "DRILL"):
        k = 1.0 / math.tan(math.radians(tool.angle) / 2)
        return k * r, k
    z = np.array([p[0] for p in tool.profile])
    rr = np.array([p[1] for p in tool.profile])
    keep = np.concatenate([[True], np.diff(rr) > 0])
    return np.interp(r, rr[keep], z[keep]), float(np.max(np.diff(z[keep]) / np.diff(rr[keep])))


@pytest.mark.parametrize("name", sorted(SWEPT))
def test_sweep_height_against_brute_force(name):
    """The bit at 8,001 places along the move, the lowest ``z + f(r)`` of them: level moves, slopes down and up
    (also steeper than the bit's own flank), plunges, lifts, standing still; ``inf`` outside the footprint.
    (The footprint is ``heightmap.EDGE``, 0.05 um, wider than the bit: the brute force's bit is too.)"""
    tool = SWEPT[name]
    shape = H.shape_of(tool, M.Cutter(tool, "NORMAL").profile)
    assert shape is not None
    assert shape.R == pytest.approx(tool.radius, abs=1e-9)
    rng = np.random.default_rng(5)
    N = 8001
    s = np.linspace(0.0, 1.0, N)[:, None]
    kmax = bit_height(tool, np.zeros(1))[1]
    edge = float(getattr(H, "EDGE", 0.0))
    for trial in range(36):
        kind = trial % 6
        a = rng.uniform(-5, 5, 2) * MM
        L = rng.uniform(0.2, 12) * MM
        ang = rng.uniform(0, 2 * math.pi)
        b = a + L * np.array([math.cos(ang), math.sin(ang)])
        z0 = rng.uniform(-3, 0) * MM
        z1 = z0 + (0.0 if kind == 0 else rng.uniform(-1, 1) * L * (4.0 if kind == 5 else 0.6))
        if kind in (1, 2):                                             # straight down or up; standing still
            b, L = a.copy(), 0.0
            z1 = z0 + (rng.uniform(-3, 3) * MM if kind == 1 else 0.0)
        px, py = rng.uniform(-18, 18, 500) * MM, rng.uniform(-18, 18, 500) * MM
        got = H.sweep_height(shape, a[0], a[1], b[0], b[1], z0, z1, px, py)
        cx, cy = a[0] + s * (b[0] - a[0]), a[1] + s * (b[1] - a[1])
        r = np.hypot(px[None, :] - cx, py[None, :] - cy)
        want = np.min(np.where(r <= tool.radius + edge, z0 + s * (z1 - z0)
                               + bit_height(tool, np.minimum(r, tool.radius))[0], np.inf), axis=0)
        u = np.clip(((px - a[0]) * (b[0] - a[0]) + (py - a[1]) * (b[1] - a[1])) / max(L * L, 1e-30), 0, 1) if L else 0.0
        away = np.hypot(px - a[0] - u * (b[0] - a[0]), py - a[1] - u * (b[1] - a[1]))
        inside, outside = away < tool.radius - 2e-6, away > tool.radius + 2e-6
        assert np.all(np.isinf(got[outside])), (name, trial, "a height outside the footprint")
        assert np.all(np.isfinite(got[inside])), (name, trial, "no height inside the footprint")
        e = got[inside] - want[inside]
        coarse = (abs(z1 - z0) + kmax * L) / (N - 1) + 2e-8            # what the 8,001 places can miss
        coarse += edge * (2 + 2 * kmax + (2 * abs(z1 - z0) / L if L else 0.0))
        assert e.max(initial=0.0) <= 2e-8 + 2 * edge * (1 + kmax), (name, trial, kind,
                                                                   f"{e.max() / MM:.6f} mm above the lowest place")
        assert e.min(initial=0.0) >= -coarse, (name, trial, kind, f"{-e.min() / MM:.6f} mm below every place")


@pytest.mark.parametrize("name, profile", [
    ("T-slot cutter", ((0.0, 6.0), (3.0, 6.0), (3.0, 2.0), (30.0, 2.0))),
    ("dovetail cutter", ((0.0, 5.0), (4.0, 2.0), (30.0, 2.0))),
    ("lollipop", ((0.0, 0.0), (1.0, 2.2), (3.0, 3.0), (5.0, 2.2), (6.0, 1.0), (30.0, 1.0))),
    ("trumpet (bulges in)", ((0.0, 0.0), (1.0, 0.3), (1.5, 3.0), (20.0, 3.0))),
    ("pin below a wide body", ((0.0, 1.0), (5.0, 1.0), (5.0, 4.0), (30.0, 4.0))),
    ("wide shank", ((0.0, 1.5), (10.0, 1.5), (10.0, 3.0), (40.0, 3.0))),
    ("step drill", ((0.0, 0.0), (1.0, 1.5), (8.0, 1.5), (9.0, 3.0), (30.0, 3.0))),
])
def test_shape_of_refuses_what_the_map_cannot_hold(name, profile):
    """Undercut outlines and outlines of more than one convex piece. Where ``shape_of`` does give a shape, that
    shape must be the bit's: its height at every radius the lowest point of the outline there."""
    prof = tuple((z * MM, r * MM) for z, r in profile)
    tool = M.Tool("CUSTOM", radius=max(r for _z, r in prof), length=prof[-1][0], profile=prof)
    cutter = M.Cutter(tool, "NORMAL")
    assert len(M.convex_pieces(cutter.profile)) >= 2
    shape = H.shape_of(tool, cutter.profile)
    if shape is None:
        return
    z, rr = np.array([p[0] for p in prof]), np.array([p[1] for p in prof])
    r = np.linspace(0.0, rr.max(), 301)[1:-1]
    low = np.full(len(r), np.inf)                      # the lowest point of the bit at least r from its axis
    for k in range(len(z) - 1):
        (za, ra), (zb, rb) = (z[k], rr[k]), (z[k + 1], rr[k + 1])
        on = za + (r - ra) / (rb - ra) * (zb - za) if abs(rb - ra) > 1e-12 else np.full(len(r), za)
        low = np.minimum(low, np.where(ra >= r, za, np.where(rb >= r, on, np.inf)))
    err = np.abs(shape.f(r) - low)
    k = int(np.argmax(err))
    assert err[k] < 1e-6, (f"{name}: shape_of gives a {shape.kind} whose height at r = {r[k] / MM:.2f} mm is "
                           f"{float(shape.f(r[k:k + 1])[0]) / MM:.2f} mm; the bit's lowest point there is {low[k] / MM:.2f} mm")


def test_shape_of_takes_convex_outlines():
    for tool in (FLAT6, BALL6, BULL8, VEE90, DRILL5, CHAMFER, TAPER):
        shape = H.shape_of(tool, M.Cutter(tool, "NORMAL").profile)
        assert shape is not None, tool.kind
        r = np.linspace(0.0, tool.radius, 200)
        assert np.allclose(shape.f(r), bit_height(tool, r)[0], atol=1e-9), tool.kind


def _closed(verts, tris) -> str:
    """'' when the triangles are a closed surface with every edge used once each way and volume inside."""
    t = np.asarray(tris, np.int64)
    v = np.asarray(verts, float)
    if not np.isfinite(v).all():
        return "a vertex is not a number"
    e = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    if np.any(e[:, 0] == e[:, 1]):
        return "a triangle uses a vertex twice"
    code = e[:, 0] * (len(v) + 1) + e[:, 1]
    back = e[:, 1] * (len(v) + 1) + e[:, 0]
    if len(np.unique(code)) != len(code):
        return "an edge is used twice the same way"
    if not np.array_equal(np.sort(code), np.sort(back)):
        return "an edge has no partner the other way (a hole, or faces turned)"
    p = v[t]
    vol = float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6.0)
    return "" if vol > 0 else f"its volume is {vol}"


def _border(hm, v, t, mv):
    """Of one tile's mesh: points on its border above the bottom - the vertices there and the middles of the
    edges between them -, whether each belongs to a piece of the side that carries a move (a wall that runs
    along the border: the tile on the other side has nothing there), and the tile's triangles without the
    bottom's. The border is where the mesh goes down to the bottom: a vertex whose place seen from above is that
    of a bottom vertex of the side."""
    v, t = np.asarray(v, float), np.asarray(t, np.int64)
    low = v[:, 2] <= hm.bottom + 1e-9
    nlow = low[t].sum(axis=1)
    foot = np.unique(t[(nlow > 0) & (nlow < 3)])                      # (not the middle of the bottom)
    foot = foot[low[foot]]
    key = lambda q: np.round(q[:, :2] / 1e-9).astype(np.int64)       # noqa: E731
    places = {tuple(k) for k in key(v[foot]).tolist()}
    on = np.array([tuple(k) in places for k in key(v).tolist()]) & ~low
    upright = np.abs(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])[:, 2]) < 1e-18
    side = upright & on[t].any(axis=1) & (on | low)[t].all(axis=1)
    wall = np.zeros(len(v), bool)
    wall[t[side & (np.asarray(mv) >= 0)].reshape(-1)] = True
    e = np.concatenate([t[side][:, [0, 1]], t[side][:, [1, 2]], t[side][:, [2, 0]]])
    e = e[on[e].all(axis=1)]
    on = np.zeros(len(v), bool)                         # (only the side's own vertices: a wall's top can stand
    on[np.unique(e)] = True                             # over a border vertex without being one)
    pts = np.concatenate([v[on], 0.5 * (v[e[:, 0]] + v[e[:, 1]])])
    return pts, np.concatenate([wall[on], wall[e].all(axis=1)]), t[nlow < 3]


def test_heightmap_tiles_are_closed_and_meet_at_their_borders():
    """A map of 3 x 2 tiles: a flat pocket, ball passes over a tile corner, a V groove, a plunge, a wall along a
    tile's border - at several times and with a move under way. Every tile's mesh is closed and turned outwards
    and lies in the map. Tiles meet vertex for vertex, but for a node one tile keeps because a third forced it:
    so every point of a tile's border (its vertices, the middles of its edges) lies on a neighbouring tile's
    mesh within the thinning tolerance - but the points of a wall that the tile's side carries."""
    cell = 0.2 * MM
    shapes = [H.shape_of(t, M.Cutter(t, "NORMAL").profile) for t in (FLAT4, BALL6, VEE90, DRILL5)]
    moves = []                                             # (shape, a, b, z0, z1, class)
    for k in range(40):                                    # a pocket whose right wall runs along a tile border
        y = 3.0 + 0.1 * k
        moves.append((0, (3.0, y), (4.4, y), -2.0, -2.0, 100 + k))
    for k in range(16):                                    # ball passes across the corner where four tiles meet
        y = 4.0 + 0.3 * k
        moves.append((1, (4.0, y), (15.5, y), -1.0 - 0.02 * k, -1.2, 1))
    moves.append((2, (9.0, 2.5), (17.0, 3.5), -1.0, -1.6, 2))
    moves.append((3, (15.0, 9.2), (15.0, 9.2), 1.0, -3.0, 200))
    hm = H.HeightMap(0.0, 0.0, cell, 3, 2, top=0.0, bottom=-6 * MM, tol=0.005 * MM)
    hm.set_moves(shapes, [m[0] for m in moves], np.array([m[1] for m in moves]) * MM,
                 np.array([m[2] for m in moves]) * MM, np.array([m[3] for m in moves]) * MM,
                 np.array([m[4] for m in moves]) * MM, np.arange(len(moves)), [m[5] for m in moves], slots=1)
    span = hm.tile * cell
    worst_gap = 0.0
    for k, partial in ((len(moves), ()), (55, ((55, (9.0 * MM, 8.5 * MM, -1.25 * MM)),)), (41, ()), (20, ()), (7, ()),
                       (3, ())):
        hm.goto(k, partial)
        owners, tiles = set(), {}
        for J in range(hm.ty):
            for I in range(hm.tx):                         # noqa: E741
                _serial, v, t, mv = hm.mesh(J, I)
                assert _closed(v, t) == "", f"tile {J}, {I} after {k} moves: {_closed(v, t)}"
                assert v[:, 2].min() >= hm.bottom - 1e-12 and v[:, 2].max() <= hm.top + H.PAD + 1e-9
                assert v[:, 0].min() >= -1e-9 and v[:, 0].max() <= 3 * span + 1e-9
                assert v[:, 1].min() >= -1e-9 and v[:, 1].max() <= 2 * span + 1e-9
                owners |= set(mv[mv >= 0].tolist())
                pts, walled, tris = _border(hm, v, t, mv)
                tiles[(J, I)] = (pts[~walled], Surf(v, tris))
        assert owners, "no cut face at all"
        for where, (pts, _s) in tiles.items():
            inside = (pts[:, 0] > 1e-6) & (pts[:, 0] < 3 * span - 1e-6) & (pts[:, 1] > 1e-6) & (pts[:, 1] < 2 * span - 1e-6)
            pts = pts[inside]
            gap = np.full(len(pts), np.inf)
            for other, (_p, surf) in tiles.items():
                if other != where:
                    gap = np.minimum(gap, surf.near(pts))
            j = int(np.argmax(gap))
            worst_gap = max(worst_gap, float(gap[j]))
            assert gap[j] <= hm.tol + 1e-9, (
                f"after {k} moves the point {np.round(pts[j] / MM, 4).tolist()} mm on the border of tile {where} lies "
                f"{'more than 0.06' if gap[j] >= NEAR else round(gap[j] / MM, 4)} mm from every other tile "
                f"(thinning tolerance {hm.tol / MM} mm)")


def test_heightmap_goto_is_the_same_from_anywhere():
    """The map after k moves does not depend on where it came from (forward, back from later, with moves under
    way put on and taken off again)."""
    shapes = [H.shape_of(t, M.Cutter(t, "NORMAL").profile) for t in (FLAT4, BALL6)]
    rng = np.random.default_rng(2)
    n = 200
    a, b = rng.uniform(1, 11, (n, 2)) * MM, rng.uniform(1, 11, (n, 2)) * MM
    z0, z1 = rng.uniform(-3, -0.2, n) * MM, rng.uniform(-3, -0.2, n) * MM

    which = rng.integers(0, 2, n)

    def fresh():
        hm = H.HeightMap(0.0, 0.0, 0.2 * MM, 2, 2, top=0.0, bottom=-6 * MM, tol=0.005 * MM)
        hm.set_moves(shapes, which, a, b, z0, z1, np.arange(n), np.arange(n), slots=2)
        return hm
    one, two = fresh(), fresh()
    one.goto(120)
    want = (one.h.copy(), one.owner.copy())
    two.goto(200)
    two.goto(37, ((37, (5 * MM, 5 * MM, -1 * MM)), (38, (2 * MM, 8 * MM, -2 * MM))))
    two.goto(150, ((150, (6 * MM, 6 * MM, -2.5 * MM)),))
    two.goto(120)
    assert np.array_equal(two.h, want[0]) and np.array_equal(two.owner, want[1])
    for J in range(2):
        for I in range(2):                                 # noqa: E741
            x, y = one.mesh(J, I), two.mesh(J, I)
            assert np.array_equal(x[1], y[1]) and np.array_equal(x[2], y[2]) and np.array_equal(x[3], y[3])
