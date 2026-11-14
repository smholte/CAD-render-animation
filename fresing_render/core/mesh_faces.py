"""Faces of a plain triangle mesh, as a CAD model has them (task 0117). No Blender, NumPy only.

A mesh read from glTF or OBJ has no CAD faces: only triangles. The app wants faces all the same: a click picks a whole
face (looks, decals), and the joint picker needs the **axis** of a round face (a shaft, a hole, a slewing ring). This
module cuts a triangle mesh into faces and finds the axes of the facetted cylinders in it.

How it works, step by step
--------------------------
1. **Weld** the corners: positions within a tiny distance are one vertex (``weld``). Split normals and UV seams give
   a glTF mesh many copies of one corner; after welding the triangles are joined again, so a mesh with and without
   split normals gives the same faces.
2. **Edges** between triangles (``_Edges``): the welded corner pairs, sorted. Two triangles on one edge are
   neighbours; an edge with three or more triangles links each to its next few in the sorted list. The angle
   between two neighbours is taken with their winding in mind.
3. **Flat patches** (``_patches``): neighbours less than 1 degree apart are one patch (also when one of them is
   wound the other way: it is turned round). A slowly curving surface would chain into one big "flat" patch that is
   not flat: a patch whose triangles spread more than the limit is cut again with 0.1 and 0.01 degrees, and is
   single triangles after that. Triangles without area join a neighbour's patch.
4. **Cylinders** (``_cylinders``): the facets of a facetted cylinder are flat strips whose shared edges ("creases")
   all run along the axis. For every crease between two strips the centre is where the two strips'
   mid-perpendicular planes cross (exact for any two chords of one circle). Where two creases of one strip give the
   same centre and radius, the strip and both neighbours belong together. Each group found that way is checked as
   a whole, first all groups at once (``_quick_checks``: axis from the creases, circle from their mean, every corner
   on it), the groups that fail one by one (``_Fitter.check``: the circle most creases agree with, fitted to the
   corners on it by Gauss-Newton; only the triangles on it are taken, and a group may give more than one cylinder).
   A cylinder must also explain the bulge of its arc (not only lie within a share of a huge radius: a gently curved
   free surface), and its soft creases across the axis must not outweigh those along it (a sphere's columns, a
   height field). Pieces of a bend (a torus: pipe bends, ring fillets) are dropped (``_bends``). Strips next to an
   accepted cylinder whose corners lie on it (the last facet of an open arc) join it.
5. **The rest** (``_assemble``): patches that are not in a cylinder are joined over soft edges (less than 40
   degrees) into free-form faces ("other"); a patch with at least 5 % of such a surface's area, or a patch on its
   own (a box side), stays a flat face of its own.
6. Faces are numbered by their first triangle and every face is one block of triangles in the new order; the
   round faces' axes are stored like ``importer.step_reader._Axes`` does (same line = one axis, at most
   ``MAX_AXES``; lines are matched within 5e-5 in direction and 1e-4 x the mesh's diagonal rather than by
   rounding). One difference: the stored point is the point of the axis beside the middle of its first face, not
   the one nearest the origin (see the comment in ``split``).

Everything is vectorised over triangles and edges; Python loops run per cylinder group that the quick check did not
pass, and per cylinder that has a strip to grow by. Cones are not found yet (their facets meet in creases that are not
parallel): they come out as "other" or flat faces, and no face has kind 3 so far.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_AXES = 400

KIND_OTHER, KIND_FLAT, KIND_CYLINDER, KIND_CONE = 0, 1, 2, 3

FLAT_LEVELS = (1.0, 0.1, 0.01)   # degrees: neighbours closer than this are one flat patch (tried in this order)
SHARP_DEG = 40.0                 # an edge sharper than this always bounds a face
PARALLEL_DEG = 1.0               # creases this close in direction count as parallel
EDGE_PARALLEL_DEG = 0.5          # a mesh edge this close to a patch's crease direction bounds its strip
LOCAL_TOL = 0.003                # two crease estimates of one strip agree within this share of the radius
FIT_TOL = 0.002                  # every corner of an accepted cylinder lies within this share of its radius
NORMAL_TOL_DEG = 1.5             # every facet normal of an accepted cylinder is within this of square to the axis
OWN_FACE_SHARE = 0.05            # a flat patch with this share of its free-form surface stays a face of its own
BULGE_SHARE = 0.01               # ... and within this share of how far its arc bulges
LENGTH_RATIO = 0.75              # creases along the axis must be this long compared with soft creases across it,
SMOOTH_DEG, SMOOTH_WEIGHT = 2.0, 4.0  # where a crease across it smoother than SMOOTH_DEG counts SMOOTH_WEIGHT times
NOISE = 6e-8                     # rounding of a position: half a float32 step, as a share of its largest coordinate
NOISE_K = 4.0                    # a crease estimate's centre moves by up to NOISE_K x rounding x (radius / width)^2
NEIGHBOURS = 8                   # an edge (or a patch's crease list) links each item to this many next ones


@dataclass
class Faces:
    order: np.ndarray       # (m,) int64: new triangle k is old triangle order[k]; every face is one block
    starts: np.ndarray      # (F+1,) int32: first triangle of each face in the new order, plus m at the end
    kinds: np.ndarray       # (F,) uint8: 0 other, 1 flat, 2 cylinder, 3 cone
    axes: list              # [ox, oy, oz, dx, dy, dz, r] per unique axis (units of the positions)
    axis_faces: list        # flat [tri_start, tri_count, axis index, ...] in the new order, one triple per round face


# ---------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------

def _components(n: int, a, b) -> np.ndarray:
    """Connected pieces of a graph of ``n`` nodes and edges a-b: the smallest node of each piece, per node.

    Union by hooking (each root takes the smallest root it touches) and pointer jumping, all in NumPy."""
    lab = np.arange(n, dtype=np.int64)
    a = np.asarray(a, dtype=np.int64)
    b = np.asarray(b, dtype=np.int64)
    while len(a):
        ra, rb = lab[a], lab[b]
        diff = ra != rb
        if not diff.any():
            break
        a, b, ra, rb = a[diff], b[diff], ra[diff], rb[diff]
        np.minimum.at(lab, np.maximum(ra, rb), np.minimum(ra, rb))
        while True:                                   # follow every label to its root
            nxt = lab[lab]
            if np.array_equal(nxt, lab):
                break
            lab = nxt
    return lab


def _renumber(labels: np.ndarray) -> np.ndarray:
    """Labels 0..k-1, numbered in the order of their first appearance."""
    if len(labels) == 0:
        return np.zeros(0, dtype=np.int64)
    u, first, inv = np.unique(labels, return_index=True, return_inverse=True)
    rank = np.empty(len(u), dtype=np.int64)
    rank[np.argsort(first, kind="stable")] = np.arange(len(u))
    return rank[inv.ravel()]


def _unit(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rows of ``v`` scaled to length 1 (rows of length 0 stay 0), and the lengths."""
    ln = np.sqrt(np.einsum("ij,ij->i", v, v))
    return v / np.where(ln > 0, ln, 1.0)[:, None], ln


def _gather(starts: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Indices start..start+count-1 of several ranges, one after the other."""
    counts = np.asarray(counts, dtype=np.int64)
    total = int(counts.sum())
    if total == 0:
        return np.zeros(0, dtype=np.int64)
    offs = np.repeat(np.asarray(starts, dtype=np.int64) - np.concatenate(([0], np.cumsum(counts)[:-1])), counts)
    return offs + np.arange(total, dtype=np.int64)


def _pairs_in_groups(keys_sorted: np.ndarray, reach: int = NEIGHBOURS) -> tuple[np.ndarray, np.ndarray]:
    """Index pairs (i, j), i < j <= i + reach, of a sorted key list where the keys are equal."""
    out_i, out_j = [], []
    n = len(keys_sorted)
    for d in range(1, reach + 1):
        if d >= n:
            break
        same = np.flatnonzero(keys_sorted[:-d] == keys_sorted[d:])
        if not len(same):
            break                                     # no group has d + 1 members: none has more
        out_i.append(same)
        out_j.append(same + d)
    if not out_i:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    return np.concatenate(out_i), np.concatenate(out_j)


def _scale(pos: np.ndarray) -> tuple[float, float]:
    """The bounding-box diagonal and the size that sets the rounding noise (diagonal or largest coordinate)."""
    if len(pos) == 0:
        return 0.0, 0.0
    diag = float(np.linalg.norm(pos.max(0) - pos.min(0)))
    return diag, max(diag, float(np.abs(pos).max()))


def _clean(pos) -> np.ndarray:
    p = np.asarray(pos, dtype=np.float64).reshape(-1, 3)
    if not np.isfinite(p).all():
        p = np.where(np.isfinite(p), p, 0.0)
    return p


# ---------------------------------------------------------------------------------------------------------------
# welding and loose parts
# ---------------------------------------------------------------------------------------------------------------

def weld(pos, tol=None) -> np.ndarray:
    """One id per vertex (0..k-1, in the order of first appearance); positions within ``tol`` share an id.

    ``tol`` defaults to 1e-6 x the bounding-box diagonal (at least 1e-12, and at least 1e-6 x the largest side so
    the grid keys fit 64 bits). Positions go into cubes of side ``tol``; cubes that touch (also at an edge or a
    corner) are joined, so two points within ``tol`` always share an id even across a cube boundary (points up to
    about 3.5 x ``tol`` apart may share one too)."""
    p = _clean(pos)
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    lo = p.min(0)
    ext = p.max(0) - lo
    diag = float(np.linalg.norm(ext))
    t = 1e-6 * diag if tol is None else float(tol)
    t = max(t, 1e-12, 1e-6 * float(ext.max()))
    g = np.floor((p - lo) / t).astype(np.int64) + 1     # >= 1, so a neighbour cube's key is never negative
    size = g.max(0) + 2
    key = (g[:, 0] * size[1] + g[:, 1]) * size[2] + g[:, 2]
    cells, inv = np.unique(key, return_inverse=True)
    inv = inv.ravel()
    if len(cells) > 1:
        cg = np.empty((len(cells), 3), dtype=np.int64)  # the cube coordinates of every occupied cube
        cg[inv] = g
        a_all, b_all = [], []
        for o in [(1, j, k) for j in (-1, 0, 1) for k in (-1, 0, 1)] + [(0, 1, k) for k in (-1, 0, 1)] + [(0, 0, 1)]:
            q = cg + np.asarray(o)
            nk = (q[:, 0] * size[1] + q[:, 1]) * size[2] + q[:, 2]
            idx = np.searchsorted(cells, nk)
            idx = np.minimum(idx, len(cells) - 1)
            hit = np.flatnonzero(cells[idx] == nk)
            if len(hit):
                a_all.append(hit)
                b_all.append(idx[hit])
        if a_all:
            root = _components(len(cells), np.concatenate(a_all), np.concatenate(b_all))
            inv = root[inv]
    return _renumber(inv)


def loose_parts(pos, tri, tol=None) -> np.ndarray:
    """A label per triangle, 0..k-1 in the order of each piece's first triangle: triangles that share a welded
    corner (directly or through others) are one piece. Split normals and UV seams do not split a piece."""
    t = np.asarray(tri, dtype=np.int64).reshape(-1, 3)
    if len(t) == 0:
        return np.zeros(0, dtype=np.int64)
    w = weld(pos, tol)
    wt = w[t]
    lab = _components(int(w.max()) + 1, np.concatenate((wt[:, 0], wt[:, 1])), np.concatenate((wt[:, 1], wt[:, 2])))
    return _renumber(lab[wt[:, 0]])


# ---------------------------------------------------------------------------------------------------------------
# edges between triangles
# ---------------------------------------------------------------------------------------------------------------

class _Edges:
    """The mesh's edges after welding.

    Half-edges (one per triangle side, sides of zero length dropped) sorted by their corner pair; ``ta``/``tb`` are
    neighbouring triangles, ``same_way`` says whether their windings agree (they run the shared edge in opposite
    directions), ``eu``/``ev`` the edge's corners for every pair."""

    def __init__(self, T: np.ndarray, nv: int, wpos: np.ndarray, scale: float):
        m = len(T)
        hu = T.ravel()
        hv = T[:, [1, 2, 0]].ravel()
        ht = np.repeat(np.arange(m, dtype=np.int64), 3)
        keep = hu != hv
        hu, hv, ht = hu[keep], hv[keep], ht[keep]
        lo, hi = np.minimum(hu, hv), np.maximum(hu, hv)
        key = lo * np.int64(nv) + hi
        o = np.argsort(key, kind="stable")
        self.hu, self.hv, self.ht, self.key = hu[o], hv[o], ht[o], key[o]
        self.fwd = self.hu < self.hv
        # groups of half-edges on one edge
        n = len(self.key)
        if n:
            cut = np.flatnonzero(np.diff(self.key)) + 1
            self.gstart = np.concatenate(([0], cut)).astype(np.int64)
        else:
            self.gstart = np.zeros(0, dtype=np.int64)
        self.gsize = np.diff(np.concatenate((self.gstart, [n]))).astype(np.int64)
        self.group = np.repeat(np.arange(len(self.gstart)), self.gsize)
        i, j = _pairs_in_groups(self.key)
        good = self.ht[i] != self.ht[j]
        i, j = i[good], j[good]
        self.ta, self.tb = self.ht[i], self.ht[j]
        self.same_way = self.fwd[i] != self.fwd[j]
        self.eu, self.ev = self.hu[i], self.hv[i]
        if len(self.key):
            self._t_junctions(wpos, scale)

    def _t_junctions(self, wpos, scale):
        """Neighbours over a T-junction: a free edge that lies along a piece of another free edge (one facet has
        9 corners on a long edge, its neighbour only the 2 ends, as a non-conforming exporter writes). Free edges are
        sorted by their line (direction and foot, rounded on two grids half a step apart); along one line each edge
        is paired with the edge before it that reaches furthest, when they overlap."""
        h = self.gstart[self.gsize == 1]
        if len(h) < 2:
            return
        a, b = wpos[self.hu[h]], wpos[self.hv[h]]
        d, ln = _unit(b - a)
        keep = ln > 1e-9 * scale
        h, a, b, d, ln = h[keep], a[keep], b[keep], d[keep], ln[keep]
        if len(h) < 2:
            return
        first = np.argmax(np.abs(d) > 1e-9, axis=1)
        sign = np.where(d[np.arange(len(d)), first] < 0, -1.0, 1.0)
        dc = d * sign[:, None]                         # one direction per line
        sa, sb = np.einsum("ij,ij->i", a, dc), np.einsum("ij,ij->i", b, dc)
        foot = a - dc * sa[:, None]
        s0, s1 = np.minimum(sa, sb), np.maximum(sa, sb)
        tol = 1e-6 * scale
        pi, pj = [], []
        for shift in (0.0, 0.5):
            key = np.column_stack((np.floor(dc / 1e-3 + shift), np.floor(foot / (1e-5 * scale) + shift))).astype(np.int64)
            # one number per line (a hash: two lines that share one are told apart by the check below)
            line = (key * np.array([1000003, 998244353, 1000000007, 19260817, 2147483647, 362437], np.int64)).sum(1)
            _, inv, cnt = np.unique(line, return_inverse=True, return_counts=True)
            two = np.flatnonzero(cnt[inv.ravel()] > 1)  # only lines with more than one free edge
            if len(two) < 2:
                continue
            o = two[np.lexsort((-s1[two], s0[two], line[two]))]
            lo_ = line[o]
            new = np.concatenate(([True], lo_[1:] != lo_[:-1]))
            grp = np.cumsum(new) - 1
            # running furthest end within each line: lines are stacked one above the other
            e1 = s1[o]
            lift = grp * (float(e1.max() - s0.min()) + 1.0)
            run = np.maximum.accumulate(e1 - s0.min() + lift)
            idx = np.maximum.accumulate(np.where(e1 - s0.min() + lift >= run, np.arange(len(o)), 0))
            j = np.flatnonzero(~new)
            c = idx[j - 1]
            ovl = (run[j - 1] - lift[j]) - (s0[o[j]] - s0.min())
            good = ovl > tol
            pi.append(o[c[good]])
            pj.append(o[j[good]])
        if not pi:
            return
        pi, pj = np.concatenate(pi), np.concatenate(pj)
        if not len(pi):
            return
        pr = np.unique(np.column_stack((np.minimum(pi, pj), np.maximum(pi, pj))), axis=0)
        pi, pj = pr[:, 0], pr[:, 1]
        # both edges on one line (the shorter one's ends on the longer one's line)
        short = np.where(ln[pi] <= ln[pj], pi, pj)
        long_ = np.where(ln[pi] <= ln[pj], pj, pi)
        off = []
        for pnt in (a[short], b[short]):
            v = pnt - a[long_]
            off.append(np.linalg.norm(v - d[long_] * np.einsum("ij,ij->i", v, d[long_])[:, None], axis=1))
        good = (np.maximum(off[0], off[1]) <= 1e-5 * scale) & (self.ht[h[pi]] != self.ht[h[pj]])
        pi, pj, short = pi[good], pj[good], short[good]
        if not len(pi):
            return
        self.ta = np.concatenate((self.ta, self.ht[h[pi]]))
        self.tb = np.concatenate((self.tb, self.ht[h[pj]]))
        self.same_way = np.concatenate((self.same_way, np.einsum("ij,ij->i", d[pi], d[pj]) < 0))
        self.eu = np.concatenate((self.eu, self.hu[h[short]]))
        self.ev = np.concatenate((self.ev, self.hv[h[short]]))

    def boundary(self, plab: np.ndarray) -> np.ndarray:
        """Per half-edge: does it bound its patch (a free edge, or another patch on the same edge)?"""
        if not len(self.key):
            return np.zeros(0, dtype=bool)
        p = plab[self.ht]
        pmin = np.minimum.reduceat(p, self.gstart)
        pmax = np.maximum.reduceat(p, self.gstart)
        return ((pmin != pmax) | (self.gsize == 1))[self.group]


# ---------------------------------------------------------------------------------------------------------------
# flat patches
# ---------------------------------------------------------------------------------------------------------------

def _patches(m: int, nrm: np.ndarray, area: np.ndarray, flat: np.ndarray, E: _Edges, dots: np.ndarray) -> np.ndarray:
    """A patch label per triangle (0..P-1 by first triangle): neighbours in one plane, without drift.

    ``flat`` marks triangles with an area (the others join a neighbour's patch at the end)."""
    label = np.full(m, -1, dtype=np.int64)
    pending = flat.copy()
    base = flat[E.ta] & flat[E.tb]
    signed = np.where(E.same_way, dots, -dots)        # a neighbour wound the other way in the same plane gives -1
    for deg in FLAT_LEVELS:
        if not pending.any():
            break
        cos = np.cos(np.radians(deg))
        ok = base & pending[E.ta] & pending[E.tb] & (signed > cos)
        lab = _components(m, E.ta[ok], E.tb[ok])
        idx = np.flatnonzero(pending)
        roots = lab[idx]
        al = nrm[idx] * np.where(np.einsum("ij,ij->i", nrm[idx], nrm[roots]) < 0, -1.0, 1.0)[:, None]
        w = al * area[idx, None]
        mean = np.stack([np.bincount(roots, w[:, k], minlength=m) for k in range(3)], axis=1)
        mean, _ = _unit(mean)
        dev = np.einsum("ij,ij->i", al, mean[roots])
        lowest = np.full(m, 2.0)
        np.minimum.at(lowest, roots, dev)
        good = lowest[roots] >= cos - 1e-12
        label[idx[good]] = roots[good]
        pending[idx[good]] = False
    rest = np.flatnonzero(pending)
    label[rest] = rest                                 # still drifting after the finest level: single triangles
    # triangles without area take a neighbour's patch (a few rounds for chains of them)
    for _ in range(4):
        miss = label < 0
        if not miss.any():
            break
        a = np.concatenate((E.ta, E.tb))
        b = np.concatenate((E.tb, E.ta))
        s = miss[a] & ~miss[b]
        if not s.any():
            break
        best = np.full(m, np.iinfo(np.int64).max)
        np.minimum.at(best, a[s], label[b[s]])
        got = miss & (best < np.iinfo(np.int64).max)
        label[got] = best[got]
    miss = np.flatnonzero(label < 0)
    if len(miss):                                      # area-less triangles with no neighbour: pieces of their own
        lab = _components(m, E.ta, E.tb)
        label[miss] = m + lab[miss]
    return _renumber(label)


# ---------------------------------------------------------------------------------------------------------------
# cylinders
# ---------------------------------------------------------------------------------------------------------------

class _Patches:
    """Per patch: area, unit normal, centre; and the creases (patch pairs) between patches."""

    def __init__(self, plab, T, wpos, nrm, area, E: _Edges, tri_c, sgn):
        P = int(plab.max()) + 1
        self.P = P
        self.area = np.bincount(plab, area, minlength=P)
        ns = np.stack([np.bincount(plab, nrm[:, k] * area, minlength=P) for k in range(3)], axis=1)
        self.n, nl = _unit(ns)
        self.valid = nl > 1e-300
        cnt = np.bincount(plab, minlength=P).astype(float)
        wsum = np.where(self.area > 0, self.area, cnt)
        wt = np.where(self.area[plab] > 0, area, 1.0)
        self.c = np.stack([np.bincount(plab, tri_c[:, k] * wt, minlength=P) for k in range(3)], axis=1) / wsum[:, None]
        # creases: pairs of patches over an edge
        pa, pb = plab[E.ta], plab[E.tb]
        x = pa != pb
        sw = E.same_way[x] ^ (sgn[E.ta[x]] != sgn[E.tb[x]])    # winding as the patches' normals see it
        pa, pb, eu, ev = pa[x], pb[x], E.eu[x], E.ev[x]
        lo, hi = np.minimum(pa, pb), np.maximum(pa, pb)
        ck, first, inv = np.unique(lo * np.int64(P) + hi, return_index=True, return_inverse=True)
        inv = inv.ravel()
        self.ca, self.cb = lo[first], hi[first]
        elen = np.linalg.norm(wpos[ev] - wpos[eu], axis=1)
        self.clen = np.bincount(inv, elen, minlength=len(ck))
        # the crease's line: its longest edge (a patch that runs a little way into a bend has short edges off it)
        top = np.zeros(len(ck))
        np.maximum.at(top, inv, elen)
        cand = np.flatnonzero(elen >= top[inv])
        longest = np.full(len(ck), len(elen), dtype=np.int64)
        np.minimum.at(longest, inv[cand], cand)        # the first of the longest edges of every crease
        self.cpoint = 0.5 * (wpos[eu[longest]] + wpos[ev[longest]])
        self.cdir, _ = _unit(wpos[ev[longest]] - wpos[eu[longest]])
        d = np.einsum("ij,ij->i", self.n[self.ca], self.n[self.cb])
        d = np.where(sw[first], d, -d)
        self.soft = (d > np.cos(np.radians(SHARP_DEG))) & self.valid[self.ca] & self.valid[self.cb]
        # weight of a soft crease across a cylinder's axis in the length rule: one that is almost smooth means
        # the surface goes on curving the other way too (a height field), so it counts more
        self.across_w = np.where(d > np.cos(np.radians(SMOOTH_DEG)), SMOOTH_WEIGHT, 1.0) * self.clen
        e, el = _unit(np.cross(self.n[self.ca], self.n[self.cb]))
        self.e = self.cdir                             # direction of a crease = its line (checked against the planes)
        self.e_ok = self.soft & (el > 1e-4) & (np.abs(np.einsum("ij,ij->i", e, self.cdir)) > np.cos(np.radians(2.0)))
        # crease ends sorted by patch (CSR): every crease once from each side
        ends_p = np.concatenate((self.ca, self.cb))
        ends_c = np.concatenate((np.arange(len(ck)), np.arange(len(ck))))
        o = np.argsort(ends_p, kind="stable")
        self.end_p, self.end_c = ends_p[o], ends_c[o]
        self.end_other = np.where(self.ca[self.end_c] == self.end_p, self.cb[self.end_c], self.ca[self.end_c])
        self.end_start = np.searchsorted(self.end_p, np.arange(P + 1))


def _strip_frames(Pt: _Patches, E: _Edges, plab, wpos):
    """Per patch: its crease direction ``ep`` (the soft creases' direction with the most crease length parallel to
    it), and the middle ``mid`` and width of the strip across that direction (from its boundary edges parallel to
    it). ``has`` marks patches where both are known."""
    P = Pt.P
    sel = np.flatnonzero(Pt.e_ok[Pt.end_c])
    p, c = Pt.end_p[sel], Pt.end_c[sel]
    score = Pt.clen[c].copy()
    i, j = _pairs_in_groups(p)
    par = np.abs(np.einsum("ij,ij->i", Pt.e[c[i]], Pt.e[c[j]])) > np.cos(np.radians(PARALLEL_DEG))
    np.add.at(score, i[par], Pt.clen[c[j[par]]])
    np.add.at(score, j[par], Pt.clen[c[i[par]]])
    o = np.lexsort((np.arange(len(p)), -score, p))
    p_o = p[o]
    firsts = o[np.concatenate(([True], p_o[1:] != p_o[:-1]))] if len(o) else o
    ep = np.zeros((P, 3))
    has = np.zeros(P, dtype=bool)
    ep[p[firsts]] = Pt.e[c[firsts]]
    has[p[firsts]] = True
    # strip width across ep from the boundary edges that run along ep
    bnd = E.boundary(plab)
    h = np.flatnonzero(bnd)
    hp = plab[E.ht[h]]
    h, hp = h[has[hp]], hp[has[hp]]
    d, _ = _unit(wpos[E.hv[h]] - wpos[E.hu[h]])
    along = np.abs(np.einsum("ij,ij->i", d, ep[hp])) > np.cos(np.radians(EDGE_PARALLEL_DEG))
    h, hp = h[along], hp[along]
    t, _ = _unit(np.cross(ep, Pt.n))
    s0 = np.einsum("ij,ij->i", wpos[E.hu[h]], t[hp])
    s1 = np.einsum("ij,ij->i", wpos[E.hv[h]], t[hp])
    smin = np.full(P, np.inf)
    smax = np.full(P, -np.inf)
    np.minimum.at(smin, hp, np.minimum(s0, s1))
    np.maximum.at(smax, hp, np.maximum(s0, s1))
    width = smax - smin
    has &= np.isfinite(width) & (width > 0)
    centre_s = np.zeros(P)
    centre_s[has] = 0.5 * (smin[has] + smax[has])
    mid = Pt.c + t * (centre_s - np.einsum("ij,ij->i", t, Pt.c))[:, None]
    return ep, mid, has, np.where(has, width, 0.0)


def _crease_centres(Pt: _Patches, ep, mid, has, width, scale, noise):
    """Centre line and radius of the circle through the strips on both sides of each crease (where known), and how
    far rounding can move it: a strip's normal is only known to about rounding / width, and the two mid-lines
    cross at the crease's small angle (width / radius), so the centre moves by about rounding x (radius / width)^2
    (a 5 cm shaft of 32 sides at 300 m in float32: 2 % of its radius)."""
    ca, cb, e = Pt.ca, Pt.cb, Pt.e
    cosp = np.cos(np.radians(PARALLEL_DEG))
    ok = Pt.e_ok & has[ca] & has[cb]
    ok &= np.abs(np.einsum("ij,ij->i", e, ep[ca])) > cosp
    ok &= np.abs(np.einsum("ij,ij->i", e, ep[cb])) > cosp
    ta, _ = _unit(np.cross(e, Pt.n[ca]))
    tb, _ = _unit(np.cross(e, Pt.n[cb]))
    va = mid[ca] - Pt.cpoint
    vb = mid[cb] - Pt.cpoint
    va -= e * np.einsum("ij,ij->i", va, e)[:, None]
    vb -= e * np.einsum("ij,ij->i", vb, e)[:, None]
    ra = np.einsum("ij,ij->i", ta, va)
    rb = np.einsum("ij,ij->i", tb, vb)
    cc = np.einsum("ij,ij->i", ta, tb)
    det = 1.0 - cc * cc
    ok &= det > 1e-9
    det = np.where(ok, det, 1.0)
    al = (ra - cc * rb) / det
    be = (rb - cc * ra) / det
    off = al[:, None] * ta + be[:, None] * tb
    R = np.linalg.norm(off, axis=1)
    ok &= np.isfinite(R) & (R > 0) & (R < 1e3 * scale)
    w = np.maximum(np.minimum(width[ca], width[cb]), 1e-300)
    sig = np.where(ok, NOISE_K * noise * (np.where(ok, R, 0.0) / w) ** 2, 0.0)
    return Pt.cpoint + off, R, ok, sig


def _agreeing_groups(Pt: _Patches, C, R, ok, abs_tol, sig) -> np.ndarray:
    """Group label per patch (-1: none): a strip whose two creases give the same circle joins both neighbours."""
    P = Pt.P
    sel = np.flatnonzero(ok[Pt.end_c])
    p, c = Pt.end_p[sel], Pt.end_c[sel]
    other = Pt.end_other[sel]
    i, j = _pairs_in_groups(p)
    ci, cj = c[i], c[j]
    par = np.abs(np.einsum("ij,ij->i", Pt.e[ci], Pt.e[cj])) > np.cos(np.radians(PARALLEL_DEG))
    tol = LOCAL_TOL * np.maximum(R[ci], R[cj]) + abs_tol + sig[ci] + sig[cj]
    dv = C[ci] - C[cj]
    dv -= Pt.e[ci] * np.einsum("ij,ij->i", dv, Pt.e[ci])[:, None]
    agree = par & (np.abs(R[ci] - R[cj]) <= tol) & (np.linalg.norm(dv, axis=1) <= tol)
    i, j = i[agree], j[agree]
    a = np.concatenate((p[i], p[i]))
    b = np.concatenate((other[i], other[j]))
    lab = _components(P, a, b)
    member = np.zeros(P, dtype=bool)
    member[a] = True
    member[b] = True
    return np.where(member, lab, -1)


def _plane_frame(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two unit directions square to ``d`` and to each other."""
    x, y, z = float(d[0]), float(d[1]), float(d[2])
    u = np.array([0.0, z, -y]) if abs(x) < 0.9 else np.array([-z, 0.0, x])    # d x (1,0,0) or d x (0,1,0)
    u /= np.sqrt(u @ u)
    return u, np.array([y * u[2] - z * u[1], z * u[0] - x * u[2], x * u[1] - y * u[0]])


def _circle_2d(x: np.ndarray, y: np.ndarray, start, steps: int = 2):
    """Circle (cx, cy, R) through 2-D points: Gauss-Newton steps of the true distances from ``start``.
    None when the points do not make a circle."""
    cx, cy, R = start
    for _ in range(steps):
        dx, dy = x - cx, y - cy
        rr = np.hypot(dx, dy)
        rr = np.where(rr > 0, rr, 1e-300)
        J = np.stack((dx / rr, dy / rr, np.ones_like(rr)), axis=1)
        try:
            step = np.linalg.solve(J.T @ J, J.T @ (rr - R))
        except np.linalg.LinAlgError:
            break
        if not np.all(np.isfinite(step)):
            break
        cx, cy, R = cx + step[0], cy + step[1], R + step[2]
    if not np.all(np.isfinite((cx, cy, R))):
        return None
    return cx, cy, abs(R)


class _Fitter:
    """Checks candidate groups of strips as whole cylinders, drops the pieces of bends, grows the rest.

    ``taken`` holds, per triangle, the cylinder it belongs to (-1: none). A patch of a group may be taken only in
    part: where a pipe runs smoothly into a bend, a facet of the pipe and the first piece of the bend can lie in one
    plane (one patch); only the triangles with every corner on the circle go to the cylinder."""

    def __init__(self, Pt: _Patches, plab, T, wpos, abs_tol, scale, flat, nrm, sig):
        self.Pt, self.plab, self.T, self.wpos, self.abs_tol, self.scale = Pt, plab, T, wpos, abs_tol, scale
        self.sig = sig
        self.flat, self.nrm = flat, nrm
        o = np.argsort(plab, kind="stable")
        self.tri_of = o
        self.tri_start = np.searchsorted(plab[o], np.arange(Pt.P + 1))
        self.taken = np.full(len(plab), -1, dtype=np.int64)
        self.patch_owner = np.full(Pt.P, -1, dtype=np.int64)     # patches that belong to a cylinder (all or part)
        self.cyls: list = []                            # (axis direction, centre, radius) per accepted cylinder

    def _tris(self, patches):
        s = self.tri_start[patches]
        return self.tri_of[_gather(s, self.tri_start[patches + 1] - s)]

    def _ends(self, patches):
        s = self.Pt.end_start[patches]
        return _gather(s, self.Pt.end_start[patches + 1] - s)

    def check(self, patches, C, R, ok) -> list:
        """The cylinders a group of strips makes, one after the other (see ``_check_one``): a group can hold more
        than one, e.g. the two round ends of a slot joined by the flat between them, which looks like a strip of
        a third circle from both of its creases."""
        out = []
        left = np.asarray(patches, dtype=np.int64)
        for _ in range(16):
            if len(left) < 3:
                break
            res = self._check_one(left, C, R, ok)
            if res is None:
                break
            out.append(res)
            left = np.setdiff1d(left, np.unique(self.plab[res[4]]))
        return out

    def _check_one(self, patches, C, R, ok):
        """The best-supported cylinder among the strips: (direction, centre, radius, length along the axis,
        triangles), else None.

        The crease estimate that most others agree with gives the circle to start from (the median of those
        that agree) and the axis (the direction of their creases); the circle is fitted to the corners that lie
        on it; the triangles with every corner on it and a normal square to the axis are the cylinder. They must
        come from at least 3 strips, the circle must explain the strips' bulge (not only lie within a share of a
        huge radius: a gently curved free surface), and soft creases across the axis must not be longer than
        those along it (a sphere's columns)."""
        Pt = self.Pt
        k = self._ends(patches)
        c, other = Pt.end_c[k], Pt.end_other[k]
        inside = np.isin(other, patches)
        cc = np.unique(c[ok[c] & inside])               # the group's own crease estimates
        if len(cc) < 2:
            return None
        cand = cc if len(cc) <= 256 else cc[np.linspace(0, len(cc) - 1, 256).astype(np.int64)]
        dv = C[cand][:, None, :] - C[cc][None, :, :]
        e = Pt.e[cand]
        dv -= e[:, None, :] * np.einsum("ijk,ik->ij", dv, e)[:, :, None]
        tol = (LOCAL_TOL * R[cand] + self.abs_tol + self.sig[cand])[:, None] + self.sig[cc][None, :]
        agree = ((np.linalg.norm(dv, axis=2) <= tol) & (np.abs(R[cand][:, None] - R[cc][None, :]) <= tol)
                 & (np.abs(e @ Pt.e[cc].T) > np.cos(np.radians(PARALLEL_DEG))))
        best = int(np.argmax(agree.sum(axis=1)))
        sup = cc[agree[best]]
        es = Pt.e[sup]
        d = np.linalg.eigh(es.T @ es)[1][:, 2]
        sin_n = np.sin(np.radians(NORMAL_TOL_DEG))
        tris = self._tris(patches)
        tris = tris[self.flat[tris]]
        verts, inv = np.unique(self.T[tris].ravel(), return_inverse=True)
        u, v = _plane_frame(d)
        q = self.wpos[verts]
        base = q.mean(0)
        x, y = (q - base) @ u, (q - base) @ v
        cq = C[sup] - base
        circle = tuple(float(a) for a in np.median(np.stack((cq @ u, cq @ v, R[sup]), axis=1), axis=0))
        for _ in range(3):
            res = np.abs(np.hypot(x - circle[0], y - circle[1]) - circle[2])
            on = res <= FIT_TOL * circle[2] + self.abs_tol
            if on.sum() < 3:
                return None
            circle = _circle_2d(x[on], y[on], circle)
            if circle is None:
                return None
        cx, cy, Rf = circle
        if not (Rf < 1e3 * self.scale):
            return None
        on = np.abs(np.hypot(x - cx, y - cy) - Rf) <= FIT_TOL * Rf + self.abs_tol
        good = on[inv.reshape(-1, 3)].all(axis=1) & (np.abs(self.nrm[tris] @ d) <= sin_n)
        tris = tris[good]
        took = np.unique(self.plab[tris])
        if len(took) < 3:
            return None
        # the axis again from the cylinder's own triangles, and the circle once more in that frame
        Nt = self.nrm[tris]
        d = np.linalg.eigh(Nt.T @ Nt)[1][:, 0]
        u2, v2 = _plane_frame(d)
        c0 = cx * u + cy * v
        q = self.wpos[np.unique(self.T[tris].ravel())] - base
        x, y = q @ u2, q @ v2
        circle = _circle_2d(x, y, (float(c0 @ u2), float(c0 @ v2), Rf), steps=1)
        if circle is None:
            return None
        cx, cy, Rf = circle
        miss = float(np.abs(np.hypot(x - cx, y - cy) - Rf).max())
        if miss > BULGE_SHARE * _sagitta(Pt.n[took], Rf) + self.abs_tol:
            return None
        k = self._ends(took)
        c, other = Pt.end_c[k], Pt.end_other[k]
        soft = Pt.soft[c]
        along = np.abs(Pt.cdir[c] @ d) > np.cos(np.radians(10.0))
        l_along = Pt.clen[c[soft & np.isin(other, took) & along]].sum() * 0.5
        l_across = Pt.across_w[c[soft & ~along]].sum()
        if l_along < LENGTH_RATIO * l_across:
            return None
        h = q @ d
        return d, base + cx * u2 + cy * v2, Rf, float(h.max() - h.min()), tris

    def accept(self, tris, idx):
        """The triangles a careful check found go to cylinder ``idx``; triangles without area go with their patch."""
        self.taken[tris] = idx
        took = np.unique(self.plab[tris])
        self.patch_owner[took] = idx
        t = self._tris(took)
        t = t[~self.flat[t] & (self.taken[t] < 0)]
        self.taken[t] = idx

    def grow(self, idx):
        """Neighbouring strips (over soft creases along the axis) whose corners lie on the circle join whole."""
        Pt = self.Pt
        d, centre, R = self.cyls[idx]
        cos_along = np.cos(np.radians(EDGE_PARALLEL_DEG))
        sin_n = np.sin(np.radians(NORMAL_TOL_DEG))
        tol = FIT_TOL * R + self.abs_tol
        front = np.flatnonzero(self.patch_owner == idx)
        for _ in range(100000):
            k = self._ends(front)
            c, other = Pt.end_c[k], Pt.end_other[k]
            s = Pt.soft[c] & (self.patch_owner[other] < 0) & (np.abs(Pt.cdir[c] @ d) > cos_along)
            cand = np.unique(other[s])
            cand = cand[np.abs(Pt.n[cand] @ d) <= sin_n]
            take = []
            for p in cand:
                t = self._tris(np.array([p]))
                q = self.wpos[np.unique(self.T[t[self.flat[t]]])] - centre
                q -= np.outer(q @ d, d)
                if len(q) and np.abs(np.linalg.norm(q, axis=1) - R).max() <= tol:
                    take.append(p)
            if not take:
                break
            front = np.asarray(take, dtype=np.int64)
            self.patch_owner[front] = idx
            self.taken[self._tris(front)] = idx


def _bends(Pt: _Patches, gid: np.ndarray, D: np.ndarray, R: np.ndarray, L: np.ndarray) -> np.ndarray:
    """Which found cylinders are pieces of a bend (a torus: a pipe bend, a ring fillet; also a sphere's columns).

    Such a piece meets another found cylinder of the same radius at a soft crease, with an axis turned by a small
    angle, and that other one is not much shorter (a straight pipe going into a bend is many times longer than one
    piece of the bend, so it stays a cylinder)."""
    bend = np.zeros(len(D), dtype=bool)
    ga, gb = gid[Pt.ca], gid[Pt.cb]
    s = Pt.soft & (ga >= 0) & (gb >= 0) & (ga != gb)
    if not s.any():
        return bend
    ga, gb = ga[s], gb[s]
    cos = np.abs(np.einsum("ij,ij->i", D[ga], D[gb]))
    turned = (cos < np.cos(np.radians(PARALLEL_DEG))) & (cos > np.cos(np.radians(60.0)))
    same_r = np.abs(R[ga] - R[gb]) <= 0.02 * np.maximum(R[ga], R[gb])
    link = turned & same_r
    bend[ga[link & (L[gb] * 3.0 >= L[ga])]] = True
    bend[gb[link & (L[ga] * 3.0 >= L[gb])]] = True
    return bend


def _sagitta(normals: np.ndarray, R: float):
    """How far an arc of radius R bulges, judged from its strips' unit normals: ``normals`` (k, 3) of one arc, or
    already the length of their mean per arc (1 for a flat strip, about 0 for a full turn)."""
    rho = np.linalg.norm(np.asarray(normals).mean(axis=0)) if np.ndim(normals) == 2 else normals
    return R * np.minimum(1.0, 3.0 * (1.0 - rho))


def _quick_checks(Pt: _Patches, plab, T, wpos, nrm, flat, gp, G, C, R, ok, abs_tol, scale):
    """All groups checked at once, the plain way: axis from the creases' directions, circle from the mean of their
    centres and radii, then every corner on it, every normal square to it, the bulge explained and the length rule
    (see ``_Fitter._check_one``). (direction, point on the axis, radius, length along the axis, passed) per group; a
    group that fails here gets the careful check. A clean facetted cylinder passes here without a Python step."""
    ga, gb = gp[Pt.ca], gp[Pt.cb]
    inn = ok & (ga >= 0) & (ga == gb)
    gi = ga[inn]
    e = Pt.e[inn]
    cnt = np.bincount(gi, minlength=G)
    M = np.zeros((G, 9))
    for k in range(9):
        M[:, k] = np.bincount(gi, e[:, k // 3] * e[:, k % 3], minlength=G)
    M = M.reshape(G, 3, 3)
    has = cnt > 0
    M[~has] = np.eye(3)
    d = np.linalg.eigh(M)[1][:, :, 2]
    ci = C[inn] - d[gi] * np.einsum("ij,ij->i", C[inn], d[gi])[:, None]
    n_ = np.maximum(cnt, 1)
    c0 = np.stack([np.bincount(gi, ci[:, k], minlength=G) for k in range(3)], axis=1) / n_[:, None]
    tg = gp[plab]
    sel = np.flatnonzero((tg >= 0) & flat)
    g = tg[sel]
    # the circle through the corners (Kasa, all groups at once), each group in its own frame round the rough centre
    # the creases gave (their estimates carry the rounding of the strips' normals; the corners only their own)
    hx = np.where(np.abs(d[:, 0]) < 0.9, 1.0, 0.0)
    u, _ = _unit(np.cross(d, np.column_stack((hx, 1.0 - hx, np.zeros(G)))))
    v = np.cross(d, u)
    S = np.zeros((G, 9))
    for k in range(3):
        q = wpos[T[sel, k]] - c0[g]
        x, y = np.einsum("ij,ij->i", q, u[g]), np.einsum("ij,ij->i", q, v[g])
        z = x * x + y * y
        for col, val in enumerate((x * x, x * y, y * y, x, y, np.ones_like(x), x * z, y * z, z)):
            S[:, col] += np.bincount(g, val, minlength=G)
    A = np.stack((S[:, [0, 1, 3]], S[:, [1, 2, 4]], S[:, [3, 4, 5]]), axis=1)
    sol = (np.linalg.pinv(A) @ -S[:, 6:9, None])[:, :, 0]
    cx, cy = -0.5 * sol[:, 0], -0.5 * sol[:, 1]
    r2 = cx * cx + cy * cy - sol[:, 2]
    has &= np.isfinite(r2) & (r2 > 0)
    Rg = np.sqrt(np.where(has, r2, 1.0))
    centre = c0 + cx[:, None] * u + cy[:, None] * v
    worst = np.zeros(G)
    hmin = np.full(G, np.inf)
    hmax = np.full(G, -np.inf)
    for k in range(3):
        q = wpos[T[sel, k]] - centre[g]
        h = np.einsum("ij,ij->i", q, d[g])
        rad = np.linalg.norm(q - h[:, None] * d[g], axis=1)
        np.maximum.at(worst, g, np.abs(rad - Rg[g]))
        np.minimum.at(hmin, g, h)
        np.maximum.at(hmax, g, h)
    tilt = np.zeros(G)
    np.maximum.at(tilt, g, np.abs(np.einsum("ij,ij->i", nrm[sel], d[g])))
    # the bulge: mean length of the strips' normals per group
    pm = np.flatnonzero(gp >= 0)
    npg = np.stack([np.bincount(gp[pm], Pt.n[pm, k], minlength=G) for k in range(3)], axis=1)
    rho = np.linalg.norm(npg, axis=1) / np.maximum(np.bincount(gp[pm], minlength=G), 1)
    sag = _sagitta(rho, Rg)
    # the length rule
    pe = gp[Pt.end_p]
    s = (pe >= 0) & Pt.soft[Pt.end_c]
    pe, c, other = pe[s], Pt.end_c[s], Pt.end_other[s]
    along = np.abs(np.einsum("ij,ij->i", Pt.cdir[c], d[pe])) > np.cos(np.radians(10.0))
    inside = gp[other] == pe
    l_along = 0.5 * np.bincount(pe[along & inside], Pt.clen[c[along & inside]], minlength=G)
    l_across = np.bincount(pe[~along], Pt.across_w[c[~along]], minlength=G)
    long_enough = l_along >= LENGTH_RATIO * l_across
    passed = (has & (worst <= np.minimum(FIT_TOL * Rg, BULGE_SHARE * sag) + abs_tol)
              & (tilt <= np.sin(np.radians(NORMAL_TOL_DEG))) & long_enough & (Rg < 1e3 * scale))
    # a group that fails the length rule as a whole is a piece of a free surface: not worth the careful check
    return d, centre, Rg, np.where(np.isfinite(hmax - hmin), hmax - hmin, 0.0), passed, ~long_enough


def _cylinders(Pt: _Patches, E: _Edges, plab, T, wpos, scale, flat, nrm, noise) -> _Fitter:
    """Find the facetted cylinders: crease centres, groups of agreeing strips, each group checked as a whole
    (all at once the plain way, the rest one by one the careful way), pieces of bends dropped, the rest grown by
    the strips at their edges."""
    abs_tol = 1e-6 * scale
    ep, mid, has, width = _strip_frames(Pt, E, plab, wpos)
    C, R, ok, sig = _crease_centres(Pt, ep, mid, has, width, scale, noise)
    fit = _Fitter(Pt, plab, T, wpos, abs_tol, scale, flat, nrm, sig)
    group = _agreeing_groups(Pt, C, R, ok, abs_tol, sig)
    size = np.bincount(group[group >= 0], minlength=Pt.P)
    group = np.where((group >= 0) & (size[np.maximum(group, 0)] >= 3), group, -1)
    gp = np.full(Pt.P, -1, dtype=np.int64)
    members = np.flatnonzero(group >= 0)
    if not len(members):
        return fit
    gp[members] = _renumber(group[members])            # groups 0..G-1 in the order of their smallest patch
    G = int(gp.max()) + 1
    d, centre, Rg, L, passed, hopeless = _quick_checks(Pt, plab, T, wpos, nrm, flat, gp, G, C, R, ok, abs_tol, scale)
    # found cylinders: rows 0..G-1 are the groups that passed the plain check (all their patches), further rows the
    # careful check's results (their triangles); gid = the row of every patch
    gid = np.where((gp >= 0) & passed[np.maximum(gp, 0)], gp, -1)
    D, CEN, RR, LL = [d], [centre], [Rg], [L]
    rows_tris: dict = {}
    slow = np.flatnonzero(~passed & ~hopeless)
    if len(slow):
        mem = members[np.argsort(gp[members], kind="stable")]
        starts = np.searchsorted(gp[mem], np.arange(G + 1))
        row = G
        for g in slow:
            for res in fit.check(mem[starts[g]:starts[g + 1]], C, R, ok):
                D.append(res[0][None])
                CEN.append(res[1][None])
                RR.append(np.array([res[2]]))
                LL.append(np.array([res[3]]))
                rows_tris[row] = res[4]
                gid[np.unique(plab[res[4]])] = row
                row += 1
    D, CEN, RR, LL = np.concatenate(D), np.concatenate(CEN), np.concatenate(RR), np.concatenate(LL)
    found = np.concatenate((passed, np.ones(len(RR) - G, dtype=bool)))
    keep = found & ~_bends(Pt, gid, D, RR, LL)
    # store the cylinders: the plain ones in group order first, then the careful ones
    cyl = np.full(len(RR), -1, dtype=np.int64)
    cyl[keep] = np.arange(int(keep.sum()))
    fit.cyls = [(D[g], CEN[g], float(RR[g])) for g in np.flatnonzero(keep)]
    whole = keep[:G]
    pw = (gp >= 0) & whole[np.maximum(gp, 0)]
    fit.patch_owner[pw] = cyl[gp[pw]]
    tw = pw[plab]
    fit.taken[tw] = fit.patch_owner[plab[tw]]
    for row, tris in rows_tris.items():
        if keep[row]:
            fit.accept(tris, int(cyl[row]))
    # grow only the cylinders that have an unowned strip next to them over a soft crease along the axis
    if fit.cyls:
        Dk = np.array([c[0] for c in fit.cyls])
        oa, ob = fit.patch_owner[Pt.ca], fit.patch_owner[Pt.cb]
        s = Pt.soft & ((oa >= 0) != (ob >= 0))
        own = np.maximum(oa, ob)[s]
        along = np.abs(np.einsum("ij,ij->i", Pt.cdir[s], Dk[own])) > np.cos(np.radians(EDGE_PARALLEL_DEG))
        for idx in np.unique(own[along]):
            fit.grow(int(idx))
    return fit


# ---------------------------------------------------------------------------------------------------------------
# faces
# ---------------------------------------------------------------------------------------------------------------

def _assemble(Pt: _Patches, owner: np.ndarray):
    """A face key per patch and its kind: cylinders, free-form surfaces over soft creases, flat patches."""
    P = Pt.P
    key = np.arange(P, dtype=np.int64)
    kind = np.where(Pt.valid, KIND_FLAT, KIND_OTHER).astype(np.uint8)
    cyl = owner >= 0
    key[cyl] = P + owner[cyl]
    kind[cyl] = KIND_CYLINDER
    rest = ~cyl
    link = Pt.soft & rest[Pt.ca] & rest[Pt.cb]
    comp = _components(P, Pt.ca[link], Pt.cb[link])
    comp_area = np.bincount(comp, Pt.area, minlength=P)
    size = np.bincount(comp, minlength=P)
    share = np.divide(Pt.area, comp_area[comp], out=np.ones(P), where=comp_area[comp] > 0)
    own = rest & ((size[comp] == 1) | (share >= OWN_FACE_SHARE))
    free = rest & ~own
    link2 = Pt.soft & free[Pt.ca] & free[Pt.cb]
    comp2 = _components(P, Pt.ca[link2], Pt.cb[link2])
    size2 = np.bincount(comp2[free], minlength=P)
    key[free] = 2 * P + comp2[free]
    alone = free & (size2[comp2] == 1)
    kind[free & ~alone] = KIND_OTHER
    return key, kind


def _empty() -> Faces:
    return Faces(np.zeros(0, dtype=np.int64), np.zeros(1, dtype=np.int32), np.zeros(0, dtype=np.uint8), [], [])


def split(pos, tri, normals=None) -> Faces:
    """Cut a triangle mesh into faces (see the module's notes). ``normals`` are not needed and not used: the
    faces come from the positions alone, so split or broken normals make no difference."""
    t = np.asarray(tri, dtype=np.int64).reshape(-1, 3)
    m = len(t)
    if m == 0:
        return _empty()
    p = _clean(pos)
    wid = weld(p)
    nv = int(wid.max()) + 1
    first = np.unique(wid, return_index=True)[1]
    wpos = p[first]
    T = wid[t]
    diag, scale = _scale(wpos)
    scale = max(scale, 1e-12)
    P0, P1, P2 = wpos[T[:, 0]], wpos[T[:, 1]], wpos[T[:, 2]]
    nrm, dbl = _unit(np.cross(P1 - P0, P2 - P0))
    area = 0.5 * dbl
    flat = (dbl > 1e-14 * max(diag, 1e-12) ** 2) & (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])
    area = np.where(flat, area, 0.0)
    E = _Edges(T, nv, wpos, scale)
    dots = np.einsum("ij,ij->i", nrm[E.ta], nrm[E.tb])
    plab = _patches(m, nrm, area, flat, E, dots)
    # one side for every patch: triangles wound against their patch's first triangle are turned round
    ref = np.unique(plab, return_index=True)[1]
    sgn = np.where(np.einsum("ij,ij->i", nrm, nrm[ref[plab]]) < 0, -1, 1)
    nrm = nrm * sgn[:, None]
    Pt = _Patches(plab, T, wpos, nrm, area, E, (P0 + P1 + P2) / 3.0, sgn)
    fit = _cylinders(Pt, E, plab, T, wpos, scale, flat, nrm, NOISE * float(np.abs(wpos).max()))
    taken = fit.taken
    part = (fit.patch_owner[plab] >= 0) & (taken < 0)
    if part.any():                                     # triangles left over from patches a cylinder took in part
        plab = _renumber(np.where(part, plab + Pt.P, plab))
        Pt = _Patches(plab, T, wpos, nrm, area, E, (P0 + P1 + P2) / 3.0, sgn)
    owner = np.full(Pt.P, -1, dtype=np.int64)
    owner[plab] = taken
    key, pkind = _assemble(Pt, owner)
    face = _renumber(key[plab])
    F = int(face.max()) + 1
    order = np.argsort(face, kind="stable").astype(np.int64)
    counts = np.bincount(face, minlength=F)
    starts = np.concatenate(([0], np.cumsum(counts))).astype(np.int32)
    kinds = np.zeros(F, dtype=np.uint8)
    kinds[face] = pkind[plab]
    # one axis per line, like step_reader._Axes, but its point is the one beside the face's middle, not the one
    # nearest the origin: a direction read from a mesh is a little off (float32 corners), and the point nearest the
    # origin of a part hundreds of metres out would carry that error times the distance (5 % of a 1 cm pin at 100 m)
    axes: list = []
    axis_faces: list = []
    adir = np.zeros((MAX_AXES, 3))                     # direction and point of every stored axis
    apt = np.zeros((MAX_AXES, 3))
    q = max(1e-4 * diag, 1e-12)
    cyl_of_face = np.full(F, -1, dtype=np.int64)
    cp = np.flatnonzero(taken >= 0)
    cyl_of_face[face[cp]] = taken[cp]
    for f in np.flatnonzero(kinds == KIND_CYLINDER):
        d, centre, R = fit.cyls[int(cyl_of_face[f])]
        d = np.asarray(d, dtype=np.float64) / np.linalg.norm(d)
        nz = np.flatnonzero(np.abs(d) > 1e-9)
        if len(nz) and d[nz[0]] < 0:
            d = -d
        mid = wpos[T[order[starts[f]:starts[f + 1]]]].reshape(-1, 3).mean(axis=0)
        foot = centre + d * float(np.dot(mid - centre, d))
        n = len(axes)
        rel = foot - apt[:n]
        rel -= adir[:n] * np.einsum("ij,ij->i", rel, adir[:n])[:, None]
        hit = np.flatnonzero((np.abs(adir[:n] - d).max(axis=1) < 5e-5) & (np.einsum("ij,ij->i", rel, rel) < q * q))
        if len(hit):
            idx = int(hit[0])
            axes[idx][6] = max(axes[idx][6], float(R))
        elif n < MAX_AXES:
            idx = n
            adir[n], apt[n] = d, foot
            axes.append([float(foot[0]), float(foot[1]), float(foot[2]), float(d[0]), float(d[1]), float(d[2]),
                         float(R)])
        else:
            continue
        axis_faces.extend((int(starts[f]), int(counts[f]), idx))
    return Faces(order, starts, kinds, axes, axis_faces)
