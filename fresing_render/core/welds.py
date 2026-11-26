"""Welds (task 0319): where two sets of faces meet, the bead laid along it, and the rules per metal. No Blender.

**Finding the seams** (``find_seams``). Two *sides*, each a part's triangles in world coordinates (metres) with the CAD
face of every triangle and the triangles the user picked (``Side``). A seam is a line where a picked face of side A
and a picked face of side B meet with air between them – the corner a welder fills:

1. *Candidates*: the CAD edges of one side (mesh edges between two CAD faces, or a face's open border) that lie on
   the other side's surface or within ``gap`` of it (a plate standing on a plate, a tube in a plate's hole, a coped tube
   on a tube, a root gap of a few mm), and the lines where a triangle of one side crosses one of the other (a tube
   pushed through a plate without a hole, an uncoped tube on a tube). Coincident faces (two plates lying on each other)
   are contact, not a crossing.
2. *The corner at every sample*: in the plane square to the line, each face of both parts near the point is a ray from
   the line (one way, or both ways when the face runs on past it), with its outward normal. Sorted round the line, two
   neighbouring rays leave an *air* sector when the sector lies on the outside of both their faces. A sector bounded by
   a picked face of A and a picked face of B is a weld corner: a **fillet** (35°–160°), 160°–200° a **butt** (two plates
   edge to edge, flush). This decides one-sided, both sides, lap, T, butt, tube in a hole and saddle the same way, and
   leaves out the inside of the joint (the faces in contact).
3. *Seams*: neighbouring samples with the same kind of corner are chained across edges (a hole's rim of 32 edges is one
   closed seam, an **all-round** weld); a sharp turn (> 50°) starts a new seam, its ends joined to the next by a mitre (a square post welded round). A seam found twice (from each part's
   edge, or as an edge and a crossing) is kept once.

**The bead** (``bead``): at every point of a seam a ring across the corner – from the toe on A to the toe on B, bulging
a little into the air (fillet: legs z = a / cos(θ/2) for the throat a; butt: a cap ``width`` wide with a small crown);
the toes are tucked 0.1 mm into the parts so no gap shows. Ends taper over about one leg (a start / end crater when
asked). Intermittent welds are pieces of ``length`` every ``pitch``. Beside each toe a **heat zone** strip lies on the
part's own surface (points projected onto the part, 0.05 mm off it), as wide as the tint of the metal reaches. UVs:
bead u = metres along the seam, v = 0 at toe A … 1 at toe B; heat strips u = metres along, v = metres from the toe.

**Rules** (``metal_of``, ``defaults``): the parts' looks say steel / stainless / aluminium / galvanised / painted;
the process, finish, size and the warning for two different metals follow from them.

**Model update** (``face_prints``, ``match_faces``): a picked CAD face is found again on the new mesh by its centre,
area and mean normal (the face numbers change between revisions).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

GAP = 0.002               # m: a face this close to the other part counts as meeting it (a root gap, a loose fit)
STEP = 0.020              # m: the corner is looked at at least this often along a seam (its ends found by bisection)
FINE = 0.001              # m: how finely an edge is tested for lying on the other part
SHARP = 50.0              # degrees: a seam turning more than this starts a new seam (an octagon is still one)
FILLET = (35.0, 160.0)    # degrees: the air corner of a fillet (sharper corners are not welded: slivers)
BUTT = (160.0, 200.0)     # degrees: two faces flush, edge to edge
MIN_LEN = 0.003           # m: shorter pieces are left out
TUCK = 0.0001             # m: toes go this far into the parts
LIFT = 0.00005            # m: heat strips float this far off the part's surface
MERGE = 1e-6              # m: points this close are one point (the importer's faces do not share points)
SHEET = 0.0003            # m: faces of one part farther from the line than its nearest face + this are not at the corner
EPS = 2e-6                # m: "within the gap" allows this much rounding (32-bit points from Blender)
CONTACT_DEG = 20.0        # two crossing triangles closer to parallel than this are faces in contact, not a crossing
EDGE_DEG = 30.0           # mesh edges bent more than this are edges even without CAD face data

KINDS = ("FILLET", "BUTT")
METALS = ("STEEL", "STAINLESS", "ALUMINIUM")
PROCESSES = ("MAG", "TIG", "MIG", "STICK")
FINISHES = ("AS_WELDED", "PAINTED", "GROUND")

# heat-zone width per metal (m beyond the toe, plus a share of the leg): stainless shows its tint bands to ~16 mm
# beside an 8 mm bead (study 0270 #21), MIG aluminium its soot band, steel a narrow blue-grey oxide
HEAT = {"STEEL": (0.006, 0.8), "STAINLESS": (0.010, 1.2), "ALUMINIUM": (0.006, 1.0)}
RIPPLE = {"MAG": 0.0016, "TIG": 0.0011, "MIG": 0.0020, "STICK": 0.0024}   # m between ripples


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def unit(v) -> np.ndarray:
    v = np.asarray(v, np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 1e-15, n, 1.0)


def closest_on_triangles(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Closest point on triangle (a, b, c) to p, for rows of each (Ericson, Real-Time Collision Detection 5.1.5)."""
    p, a, b, c = (np.asarray(x, np.float64) for x in (p, a, b, c))
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    out = np.empty_like(p)
    done = np.zeros(len(p), bool)

    def put(mask, val):
        nonlocal done
        m = mask & ~done
        if m.any():
            out[m] = val[m] if np.ndim(val) == 2 else val
            done |= m

    with np.errstate(divide="ignore", invalid="ignore"):
        put((d1 <= 0) & (d2 <= 0), a)
        put((d3 >= 0) & (d4 <= d3), b)
        t = np.where((d1 - d3) != 0, d1 / (d1 - d3), 0.0)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * t[:, None])
        put((d6 >= 0) & (d5 <= d6), c)
        t = np.where((d2 - d6) != 0, d2 / (d2 - d6), 0.0)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * t[:, None])
        den = (d4 - d3) + (d5 - d6)
        t = np.where(den != 0, (d4 - d3) / den, 0.0)
        put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), b + (c - b) * t[:, None])
        den = va + vb + vc
        den = np.where(np.abs(den) > 1e-300, den, 1.0)
        v, w = vb / den, vc / den
        put(np.ones(len(p), bool), a + ab * v[:, None] + ac * w[:, None])
    return out


# ---------------------------------------------------------------------------
# a part as the finder sees it
# ---------------------------------------------------------------------------

@dataclass
class Side:
    """One part: ``points`` (n, 3) world metres, ``tris`` (m, 3), ``face`` (m) CAD face of each triangle (-1: none),
    ``picked`` (m) bool – the triangles of the picked faces (all of them for "two parts")."""
    points: np.ndarray
    tris: np.ndarray
    face: np.ndarray | None = None
    picked: np.ndarray | None = None
    # worked out by ``prepare``
    v: np.ndarray = field(default=None, repr=False)          # (m, 3, 3) corners
    n: np.ndarray = field(default=None, repr=False)          # (m, 3) unit normals
    lo: np.ndarray = field(default=None, repr=False)
    hi: np.ndarray = field(default=None, repr=False)
    edges: np.ndarray = field(default=None, repr=False)      # (e, 2) welded point numbers of the CAD edges
    edge_tris: np.ndarray = field(default=None, repr=False)  # (e, 2) triangles on both sides (-1: open border)
    wp: np.ndarray = field(default=None, repr=False)         # welded points

    def prepare(self) -> "Side":
        pts = np.asarray(self.points, np.float64).reshape(-1, 3)
        tris = np.asarray(self.tris, np.int64).reshape(-1, 3)
        m = len(tris)
        face = np.full(m, -1, np.int64) if self.face is None else np.asarray(self.face, np.int64).reshape(-1)
        picked = np.ones(m, bool) if self.picked is None else np.asarray(self.picked, bool).reshape(-1)
        v = pts[tris] if m else np.zeros((0, 3, 3))
        nrm = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]) if m else np.zeros((0, 3))
        area2 = np.linalg.norm(nrm, axis=1)
        ok = area2 > 1e-14
        self.tris, self.face, self.picked = tris[ok], face[ok], picked[ok]
        self.v, self.n = v[ok], unit(nrm[ok])
        if len(self.v):                      # an inside-out mesh (a mirrored part): its faces turned the right way
            c = self.v.reshape(-1, 3).mean(0)
            w = self.v - c
            vol = float(np.einsum("ij,ij->i", w[:, 0], np.cross(w[:, 1], w[:, 2])).sum()) / 6.0
            if vol < 0:
                self.tris = self.tris[:, ::-1]
                self.v = self.v[:, ::-1]
                self.n = -self.n
        self.lo = self.v.min(1) if len(self.v) else np.zeros((0, 3))
        self.hi = self.v.max(1) if len(self.v) else np.zeros((0, 3))
        # weld points by place: the importer gives every CAD face its own points
        key = np.round(pts / MERGE).astype(np.int64)
        _u, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        wp = np.zeros((len(_u), 3))
        wp[inv] = pts
        self.wp = wp
        wt = inv[self.tris]
        e = np.concatenate([wt[:, [0, 1]], wt[:, [1, 2]], wt[:, [2, 0]]])
        tri_of = np.tile(np.arange(len(wt)), 3)
        e = np.sort(e, axis=1)
        keep = e[:, 0] != e[:, 1]
        e, tri_of = e[keep], tri_of[keep]
        order = np.lexsort((e[:, 1], e[:, 0]))
        e, tri_of = e[order], tri_of[order]
        if len(e):
            new = np.ones(len(e), bool)
            new[1:] = np.any(e[1:] != e[:-1], axis=1)
            start = np.flatnonzero(new)
            count = np.diff(np.append(start, len(e)))
            ue = e[start]
            t0 = tri_of[start]
            t1 = np.where(count >= 2, tri_of[np.minimum(start + 1, len(e) - 1)], -1)
            many = count > 2                                   # a non-manifold edge: an edge whatever its faces
            f0 = self.face[t0]
            f1 = np.where(t1 >= 0, self.face[np.maximum(t1, 0)], -2)
            cosang = np.where(t1 >= 0, (self.n[t0] * self.n[np.maximum(t1, 0)]).sum(1), -1.0)
            feature = (t1 < 0) | many | ((f0 != f1) & (f0 >= 0)) | (cosang < math.cos(math.radians(EDGE_DEG)))
            pick = self.picked[t0] | np.where(t1 >= 0, self.picked[np.maximum(t1, 0)], False)
            sel = feature & pick
            self.edges, self.edge_tris = ue[sel], np.stack([t0[sel], t1[sel]], 1)
        else:
            self.edges, self.edge_tris = np.zeros((0, 2), np.int64), np.zeros((0, 2), np.int64)
        return self

    _act: np.ndarray | None = field(default=None, repr=False)   # ``restrict``: only these triangles are looked at

    def restrict(self, lo=None, hi=None) -> None:
        """Look only at the triangles whose box meets lo..hi (the region where two parts meet); None: all again."""
        if lo is None:
            self._act = None
            return
        self._act = np.flatnonzero(np.all(self.lo <= np.asarray(hi), 1) & np.all(self.hi >= np.asarray(lo), 1))

    def near(self, lo, hi, pad: float) -> np.ndarray:
        """Triangles whose box meets the box lo..hi grown by ``pad``."""
        if self._act is not None:
            a = self._act
            return a[np.all(self.lo[a] <= np.asarray(hi) + pad, 1) & np.all(self.hi[a] >= np.asarray(lo) - pad, 1)]
        return np.flatnonzero(np.all(self.lo <= np.asarray(hi) + pad, 1) & np.all(self.hi >= np.asarray(lo) - pad, 1))

    def nearest_local(self, pts: np.ndarray, reach: float, chunk: int = 24, batch: int = 120000):
        """``distance`` for points that only care about the surface within ``reach`` (projections): the points in small
        runs (they come in order along a seam), each against the triangles near it. Points farther than ``reach`` from
        every triangle get distance inf and triangle -1.

        Task 0368: the runs are not measured one by one (each call cost ~0.5 ms of NumPy overhead for a few hundred
        pairs); every run's (point, triangle) pairs go into one array, ``batch`` pairs at a time, and each point takes
        its nearest pair – the same numbers, the same triangle on a tie (the lowest number), as run by run."""
        pts = np.asarray(pts, np.float64).reshape(-1, 3)
        n = len(pts)
        d = np.full(n, np.inf)
        q = np.zeros((n, 3))
        t = np.full(n, -1, np.int64)
        if not n or not len(self.v):
            return d, q, t
        cand = self._act if self._act is not None else np.arange(len(self.v))
        if not len(cand):
            return d, q, t
        starts = np.arange(0, n, chunk)
        ends = np.minimum(starts + chunk, n)
        clo = np.minimum.reduceat(pts, starts, axis=0) - reach
        chi = np.maximum.reduceat(pts, starts, axis=0) + reach
        tlo, thi = self.lo[cand], self.hi[cand]
        per = max(1, 4000000 // max(1, len(cand)))          # chunk boxes x triangles at a time (a bool matrix)
        pi_all, ti_all = [], []
        for c0 in range(0, len(starts), per):
            c1 = min(len(starts), c0 + per)
            hit = (np.all(tlo[None] <= chi[c0:c1, None], 2) & np.all(thi[None] >= clo[c0:c1, None], 2))
            ci, tj = np.nonzero(hit)                          # chunk, candidate (in order of both)
            if not len(ci):
                continue
            cnt = ends[c0 + ci] - starts[c0 + ci]             # points per pair of (chunk, triangle)
            # every point of the chunk with every triangle of the chunk, the points of a chunk in order
            pair_chunk = np.repeat(np.arange(len(ci)), cnt)
            off = np.arange(len(pair_chunk)) - np.repeat(np.cumsum(cnt) - cnt, cnt)
            pi_all.append(starts[c0 + ci][pair_chunk] + off)
            ti_all.append(cand[tj][pair_chunk])
        if not pi_all:
            return d, q, t
        pi = np.concatenate(pi_all)
        ti = np.concatenate(ti_all)
        # a lower bound per pair: the triangle's box and its plane are never farther than the triangle. Each point is
        # measured exactly against its pairs with the smallest bound first; a pair whose bound lies beyond that cannot
        # be the nearest and is left out (so nothing changes but the time)
        pp = pts[pi]
        gap = np.maximum(np.maximum(self.lo[ti] - pp, pp - self.hi[ti]), 0.0)
        lb = np.sqrt((gap * gap).sum(1))
        lb = np.maximum(lb, np.abs(((pp - self.v[ti, 0]) * self.n[ti]).sum(1)) * (1 - 1e-9))
        mlb = np.full(n, np.inf)
        np.minimum.at(mlb, pi, lb)
        first = lb <= mlb[pi]
        dd, _qq = self._pairs(pts, pi[first], ti[first])
        ub = np.full(n, np.inf)
        np.minimum.at(ub, pi[first], dd)
        keep = lb <= ub[pi] * (1 + 1e-9) + 1e-12
        pi, ti = pi[keep], ti[keep]
        for s in range(0, len(pi), batch):
            P, T = pi[s:s + batch], ti[s:s + batch]
            dd, qq = self._pairs(pts, P, T)
            m = np.full(n, np.inf)
            np.minimum.at(m, P, dd)
            at = dd == m[P]                                   # the nearest pairs (several on a tie)
            tm = np.full(n, np.iinfo(np.int64).max)
            np.minimum.at(tm, P[at], T[at])
            win = at & (T == tm[P])                           # ... the lowest triangle among them: one per point
            P, T, dd, qq = P[win], T[win], dd[win], qq[win]
            better = (dd < d[P]) | ((dd == d[P]) & (T < t[P]))
            P, T, dd, qq = P[better], T[better], dd[better], qq[better]
            d[P], q[P], t[P] = dd, qq, T
        return d, q, t

    def _pairs(self, pts, P, T):
        """(distance, nearest point) of point P[i] to triangle T[i]."""
        pp = pts[P]
        vv = self.v[T]
        qq = closest_on_triangles(pp, vv[:, 0], vv[:, 1], vv[:, 2])
        return np.linalg.norm(qq - pp, axis=1), qq

    def distance(self, pts: np.ndarray, tri_idx: np.ndarray | None = None, chunk: int = 200000):
        """(distance, nearest point, triangle) from each point to this side's surface (``tri_idx``: only these)."""
        pts = np.asarray(pts, np.float64).reshape(-1, 3)
        idx = np.arange(len(self.v)) if tri_idx is None else np.asarray(tri_idx, np.int64)
        k = len(pts)
        best = np.full(k, np.inf)
        bq = np.zeros((k, 3))
        bt = np.full(k, -1, np.int64)
        if not len(idx) or not k:
            return best, bq, bt
        per = max(1, chunk // len(idx))
        for s in range(0, k, per):
            p = pts[s:s + per]
            pp = np.repeat(p, len(idx), axis=0)
            vv = np.tile(self.v[idx], (len(p), 1, 1))
            q = closest_on_triangles(pp, vv[:, 0], vv[:, 1], vv[:, 2])
            d = np.linalg.norm(q - pp, axis=1).reshape(len(p), len(idx))
            j = np.argmin(d, axis=1)
            r = np.arange(len(p))
            best[s:s + per] = d[r, j]
            bq[s:s + per] = q.reshape(len(p), len(idx), 3)[r, j]
            bt[s:s + per] = idx[j]
        return best, bq, bt


# ---------------------------------------------------------------------------
# the corner at one point
# ---------------------------------------------------------------------------

@dataclass
class Corner:
    kind: str                      # FILLET / BUTT
    theta: float                   # degrees, the air corner
    oa: np.ndarray                 # where A's face leaves the line, its direction, its normal, its triangle
    da: np.ndarray
    na: np.ndarray
    ta: int
    ob: np.ndarray
    db: np.ndarray
    nb: np.ndarray
    tb: int
    sa: float = 1.0                # a mitred end (two seams meeting at a turn): the toe lies this much further out
    sb: float = 1.0

    @property
    def mid(self) -> np.ndarray:
        """Into the air, half way between the two faces."""
        s = self.da + self.db
        if np.linalg.norm(s) < 1e-6:
            return unit(self.na + self.nb)
        return unit(s)


def _rays(side: Side, p: np.ndarray, t: np.ndarray, reach: float):
    """The faces of ``side`` near p as rays in the plane square to t: list of (angle-ready dir, origin, normal, tri,
    picked)."""
    lo, hi = p - reach, p + reach
    idx = side.near(lo, hi, 0.0)
    out = []
    if not len(idx):
        return out
    v, n = side.v[idx], side.n[idx]
    along = np.abs(n @ t)
    keep = along < 0.6                                       # the face runs along the line (contains t, roughly)
    idx, v, n = idx[keep], v[keep], n[keep]
    if not len(idx):
        return out
    # the triangle cut by the plane through p square to t: a segment (all triangles at once)
    h = (v - p) @ t                                          # (k, 3) heights of the corners above the plane
    k = len(idx)
    cand = np.full((k, 6, 3), np.nan)                        # up to 3 corners on the plane + 3 edge crossings
    on = np.abs(h) < 1e-12
    cand[:, :3][on] = v[on]
    for e, (ia, ib) in enumerate(((0, 1), (1, 2), (2, 0))):
        ha, hb = h[:, ia], h[:, ib]
        cross = ((ha < -1e-12) & (hb > 1e-12)) | ((ha > 1e-12) & (hb < -1e-12))
        if cross.any():
            f = ha[cross] / (ha[cross] - hb[cross])
            cand[cross, 3 + e] = v[cross, ia] + (v[cross, ib] - v[cross, ia]) * f[:, None]
    valid = ~np.isnan(cand[:, :, 0])
    ok = valid.sum(1) >= 2
    if not ok.any():
        return out
    idx, v, n, cand, valid = idx[ok], v[ok], n[ok], cand[ok], valid[ok]
    d = unit(np.cross(t, n))                                 # (k, 3)
    sv = np.einsum("kcj,kj->kc", np.nan_to_num(cand - p), d)
    s0 = np.where(valid, sv, np.inf).min(1)
    s1 = np.where(valid, sv, -np.inf).max(1)
    q0 = cand[np.arange(len(idx)), np.argmin(np.where(valid, sv, np.inf), 1)]
    foot = q0 + d * (np.clip(0.0, s0, s1) - s0)[:, None]     # the segment's point nearest to p
    off = p - foot
    off -= np.outer(off @ t, t)
    dist = np.linalg.norm(off, axis=1)
    # only the part's face(s) nearest the line: a thin sheet's far side (1 – 2 mm away, within the search radius)
    # is not a face of this corner
    near = (dist <= reach) & (dist <= (dist.min() if len(dist) else 0.0) + SHEET)
    span = s1 - s0
    eps = np.minimum(1e-5, 0.05 * span)
    fwd = near & (s1 > eps) & (s1 > np.maximum(s0, 0.0) + eps)
    back = near & (s0 < -eps) & (s0 < np.minimum(s1, 0.0) - eps)
    picked = side.picked[idx]
    for i in np.flatnonzero(fwd | back):
        if fwd[i]:
            out.append((d[i], foot[i], n[i], int(idx[i]), bool(picked[i])))
        if back[i]:
            out.append((-d[i], foot[i], n[i], int(idx[i]), bool(picked[i])))
    return out


def corners_at(a: Side, b: Side, p, t, reach: float) -> list[Corner]:
    """The weld corners at point p on a line of direction t (unit): air sectors between a picked face of A and a
    picked face of B."""
    p, t = np.asarray(p, np.float64), unit(t)
    u = unit(np.cross(t, [1.0, 0.0, 0.0] if abs(t[0]) < 0.9 else [0.0, 1.0, 0.0]))
    w = np.cross(t, u)
    rays = []
    for tag, side in (("A", a), ("B", b)):
        for d, o, n, tri, picked in _rays(side, p, t, reach):
            ang = math.atan2(d @ w, d @ u)
            rays.append((ang, tag, d, o, n, tri, picked))
    if len(rays) < 2:
        return []
    rays.sort(key=lambda r: r[0])
    # the same face direction twice (a face cut in two triangles at the point): keep one per side, normal and angle
    merged = []
    for r in rays:
        if merged and abs(r[0] - merged[-1][0]) < math.radians(2.0) and r[1] == merged[-1][1] \
                and (r[4] @ merged[-1][4]) > 0.9:
            if r[6] and not merged[-1][6]:
                merged[-1] = r
            continue
        merged.append(r)
    if len(merged) > 1 and merged[0][1] == merged[-1][1] and (merged[0][4] @ merged[-1][4]) > 0.9 \
            and abs(merged[0][0] + 2 * math.pi - merged[-1][0]) < math.radians(2.0):
        merged.pop()
    out = []
    k = len(merged)
    for i in range(k):
        r1, r2 = merged[i], merged[(i + 1) % k]
        a1, a2 = r1[0], r2[0] + (2 * math.pi if i + 1 == k else 0.0)
        span = a2 - a1
        if span < math.radians(FILLET[0]) or span > math.radians(BUTT[1]) or r1[1] == r2[1]:
            continue
        if not (r1[6] and r2[6]):
            continue
        am = a1 + span / 2
        m = u * math.cos(am) + w * math.sin(am)
        if (m @ r1[4]) <= 1e-3 or (m @ r2[4]) <= 1e-3:          # the sector is inside a part
            continue
        ra, rb = (r1, r2) if r1[1] == "A" else (r2, r1)
        deg = math.degrees(span)
        kind = "FILLET" if deg < FILLET[1] else "BUTT"
        out.append(Corner(kind, deg, ra[3], ra[2], ra[4], ra[5], rb[3], rb[2], rb[4], rb[5]))
    return out


# ---------------------------------------------------------------------------
# candidates: edges on the other part, crossings
# ---------------------------------------------------------------------------

def _edge_candidates(x: Side, y: Side, gap: float, step: float):
    """Pieces of x's CAD edges that lie on y (within gap): list of (points (k, 3), tangent) – k >= 2, in order."""
    out = []
    if not len(x.edges) or not len(y.v):
        return out
    p0, p1 = x.wp[x.edges[:, 0]], x.wp[x.edges[:, 1]]
    ylo, yhi = y.lo.min(0) - gap - EPS, y.hi.max(0) + gap + EPS
    elo, ehi = np.minimum(p0, p1), np.maximum(p0, p1)
    near = np.all(elo <= yhi, 1) & np.all(ehi >= ylo, 1)
    for i in np.flatnonzero(near):
        a, b = p0[i], p1[i]
        L = np.linalg.norm(b - a)
        if L < 1e-9:
            continue
        idx = y.near(np.minimum(a, b), np.maximum(a, b), gap + EPS)
        if not len(idx):
            continue
        n = max(2, min(2000, int(math.ceil(L / FINE)) + 1))     # finely: a thin part crossing a long edge is seen
        s = np.linspace(0.0, 1.0, n)
        pts = a + (b - a) * s[:, None]
        d, _q, _t = y.distance(pts, idx)
        on = d <= gap + EPS
        if not on.any():
            continue
        # sharpen the ends of the pieces that lie on y (bisection between a point on and one off)
        segs = []
        j = 0
        while j < n:
            if not on[j]:
                j += 1
                continue
            k = j
            while k + 1 < n and on[k + 1]:
                k += 1
            s0, s1 = s[j], s[k]
            if j > 0:
                s0 = _bisect(y, idx, a, b, s[j - 1], s[j], gap)
            if k < n - 1:
                s1 = _bisect(y, idx, a, b, s[k + 1], s[k], gap)
            if (s1 - s0) * L >= 1e-5:
                segs.append((s0, s1))
            j = k + 1
        t = (b - a) / L
        for s0, s1 in segs:
            m = max(5, int(math.ceil((s1 - s0) * L / step)) + 1)      # a short piece: still a few looks inside it
            ss = np.linspace(s0, s1, m)
            out.append((a + (b - a) * ss[:, None], t))
    return out


def _bisect(y: Side, idx, a, b, s_off, s_on, gap, rounds: int = 12) -> float:
    for _ in range(rounds):
        sm = 0.5 * (s_off + s_on)
        d, _q, _t = y.distance((a + (b - a) * sm)[None], idx)
        if d[0] <= gap + EPS:
            s_on = sm
        else:
            s_off = sm
    return s_on


def _crossings(a: Side, b: Side, step: float):
    """Lines where a triangle of A crosses one of B (not faces in contact): list of (points, tangent)."""
    out = []
    if not len(a.v) or not len(b.v):
        return out
    lo, hi = np.maximum(a.lo.min(0), b.lo.min(0)), np.minimum(a.hi.max(0), b.hi.max(0))
    if np.any(lo > hi + 1e-9):
        return out
    ia, ib = a.near(lo, hi, 1e-9), b.near(lo, hi, 1e-9)
    if not len(ia) or not len(ib):
        return out
    cos_c = math.cos(math.radians(CONTACT_DEG))
    for s in range(0, len(ia), 256):
        ca = ia[s:s + 256]
        ov = (np.all(a.lo[ca][:, None, :] <= b.hi[ib][None, :, :] + 1e-9, 2)
              & np.all(a.hi[ca][:, None, :] >= b.lo[ib][None, :, :] - 1e-9, 2))
        pa, pb = np.nonzero(ov)
        if not len(pa):
            continue
        ta, tb = ca[pa], ib[pb]
        na, nb = a.n[ta], b.n[tb]
        keep = np.abs((na * nb).sum(1)) < cos_c
        ta, tb, na, nb = ta[keep], tb[keep], na[keep], nb[keep]
        for k in range(len(ta)):
            seg = _tri_tri(a.v[ta[k]], na[k], b.v[tb[k]], nb[k])
            if seg is None:
                continue
            p, q = seg
            L = np.linalg.norm(q - p)
            if L < 1e-5:
                continue
            m = max(2, int(math.ceil(L / step)) + 1)
            ss = np.linspace(0.0, 1.0, m)
            out.append((p + (q - p) * ss[:, None], (q - p) / L))
    return out


def _cut(v, h):
    """The segment where triangle v (3, 3) with signed heights h crosses height 0, or None."""
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        if (h[i] < 0 < h[j]) or (h[j] < 0 < h[i]):
            pts.append(v[i] + (v[j] - v[i]) * (h[i] / (h[i] - h[j])))
        elif h[i] == 0:
            pts.append(v[i])
    if len(pts) < 2:
        return None
    return pts[0], pts[-1]


def _tri_tri(va, na, vb, nb):
    ha = (va - vb[0]) @ nb
    if np.all(ha > -1e-12) or np.all(ha < 1e-12):
        return None
    hb = (vb - va[0]) @ na
    if np.all(hb > -1e-12) or np.all(hb < 1e-12):
        return None
    sa, sb = _cut(va, ha), _cut(vb, hb)
    if sa is None or sb is None:
        return None
    d = unit(np.cross(na, nb))
    a0, a1 = sorted(((sa[0] @ d, 0), (sa[1] @ d, 1)))
    b0, b1 = sorted(((sb[0] @ d, 0), (sb[1] @ d, 1)))
    lo, hi = max(a0[0], b0[0]), min(a1[0], b1[0])
    if hi - lo < 1e-9:
        return None
    base = sa[0] - d * (sa[0] @ d)
    return base + d * lo, base + d * hi


# ---------------------------------------------------------------------------
# seams
# ---------------------------------------------------------------------------

@dataclass
class Seam:
    points: np.ndarray             # (k, 3) on the line, world m
    corners: list                  # Corner per point
    closed: bool = False
    kind: str = "FILLET"
    joins: list = field(default_factory=lambda: [None, None])   # [start, end]: (seam number, 0 start / 1 end) of a
    #                                                             seam meeting it there at a turn (mitred ends)

    @property
    def length(self) -> float:
        p = self.points
        L = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0
        if self.closed and len(p) > 2:
            L += float(np.linalg.norm(p[0] - p[-1]))
        return L

    @property
    def mid(self) -> np.ndarray:
        return self.points[len(self.points) // 2]

    def faces(self, side: Side, which: str) -> set:
        f = side.face
        return {int(f[c.ta if which == "A" else c.tb]) for c in self.corners}

    def angle(self) -> float:
        return float(np.median([c.theta for c in self.corners])) if self.corners else 0.0


def _similar(c1: Corner, c2: Corner) -> bool:
    return c1.kind == c2.kind and float(c1.mid @ c2.mid) > math.cos(math.radians(SHARP))


def find_seams(a: Side, b: Side, gap: float = GAP, step: float = STEP) -> list[Seam]:
    """Every line where a picked face of A meets a picked face of B with air between them (see the module text)."""
    for s in (a, b):
        if s.v is None:
            s.prepare()
    reach = gap + 0.0005
    lo = np.maximum(a.lo.min(0), b.lo.min(0)) - (gap + 0.002) if len(a.v) and len(b.v) else None
    hi = np.minimum(a.hi.max(0), b.hi.max(0)) + (gap + 0.002) if len(a.v) and len(b.v) else None
    if lo is None or np.any(lo > hi):
        return []
    a.restrict(lo, hi)                       # only the region where the two parts can meet
    b.restrict(lo, hi)
    try:
        return _find(a, b, gap, step, reach)
    finally:
        a.restrict()
        b.restrict()


def _find(a: Side, b: Side, gap: float, step: float, reach: float) -> list[Seam]:
    sources = [_edge_candidates(b, a, gap, step), _edge_candidates(a, b, gap, step), _crossings(a, b, step)]
    runs = []                     # (points, corners) pieces with one corner kind each
    dup = gap + 0.0006
    cos_s = math.cos(math.radians(SHARP))
    for si, cands in enumerate(sources):
        crossing = si == 2
        # what the earlier sources found: a seam found again (from the other part's edge, or as a crossing) is skipped
        seg_a, seg_b, seg_m = [], [], []
        for rp, rc in runs:
            seg_a.extend(rp[:-1])
            seg_b.extend(rp[1:])
            seg_m.extend(c.mid for c in rc[:-1])
        seg_a, seg_b, seg_m = np.array(seg_a).reshape(-1, 3), np.array(seg_b).reshape(-1, 3), np.array(seg_m).reshape(-1, 3)

        def close_along(p, t):
            """Earlier seams that run here the same way (a bool per segment)."""
            if not len(seg_a):
                return np.zeros(0, bool)
            ab = seg_b - seg_a
            L2 = np.maximum((ab * ab).sum(1), 1e-18)
            s = np.clip(((p - seg_a) * ab).sum(1) / L2, 0.0, 1.0)
            d = np.linalg.norm(seg_a + ab * s[:, None] - p, axis=1)
            along = np.abs(ab @ t) / np.sqrt(L2)
            return (d < dup) & (along > cos_s)

        def seen(p, c, t):
            """Found before: an earlier seam runs here, the same way, with a corner facing the same way."""
            close = close_along(p, t)
            return bool(close.any() and (seg_m[close] @ c.mid > cos_s).any())

        for pts, t in cands:
            # pass 0 follows one corner along the candidate; where a point has two corners (two blocks touching along
            # one edge: two air sectors), pass 1 follows the other
            first: dict = {}
            multi = _follow(a, b, pts, t, reach, crossing, close_along, seen, runs, first, None)
            if multi:
                _follow(a, b, pts, t, reach, crossing, close_along, seen, runs, None, first)
    return _chain(runs)


def _follow(a, b, pts, t, reach, crossing, close_along, seen, runs, record, exclude) -> bool:
    """Walk a candidate's points, following one weld corner; append its runs (points, corners) to ``runs``. ``record``:
    a dict that gets the corner taken at each point; ``exclude``: such a dict – corners like those are not taken.
    Returns whether some point had more than one corner."""
    cur_p, cur_c = [], []
    multi = [False]

    def flush():
        if len(cur_p) >= 2:
            runs.append((np.array(cur_p), list(cur_c)))
        cur_p.clear()
        cur_c.clear()

    inset = min(5e-4, 0.1 * float(np.linalg.norm(pts[-1] - pts[0])))

    def corner(j, p, like=None):
        if crossing and close_along(p, t).any():
            return None                      # a faceted round face poking through its neighbour along a seam found
        q = p
        if j == 0:
            q = p + t * inset
        elif j == len(pts) - 1:
            q = p - t * inset
        cs = corners_at(a, b, q, t, reach)
        if len(cs) > 1:
            multi[0] = True
        if exclude is not None and j in exclude and exclude[j] is not None:
            cs = [x for x in cs if not _similar(x, exclude[j])]
        if not cs:
            return None
        c = max(cs, key=lambda x: float(x.mid @ like.mid)) if like is not None else cs[0]
        if like is not None and not _similar(like, c):
            return None
        if q is not p:                       # measured a little inside the end: it belongs to the end point itself
            c = Corner(c.kind, c.theta, c.oa + (p - q), c.da, c.na, c.ta, c.ob + (p - q), c.db, c.nb, c.tb)
        return None if seen(p, c, t) else c

    def edge(p_on, c_on, p_off, rounds=10):
        """Where the corner of p_on stops on the way to p_off: (point, corner) as near to it as found."""
        for _ in range(rounds):
            pm = 0.5 * (p_on + p_off)
            cm = corner(-1, pm, c_on)
            if cm is not None:
                p_on, c_on = pm, cm
            else:
                p_off = pm
        return p_on, c_on

    prev = None                                         # (point, corner or None) of the sample before
    for j, p in enumerate(pts):
        c = corner(j, p, cur_c[-1] if cur_c else None)
        if c is None and not cur_c:
            c = corner(j, p)
        if record is not None:
            record[j] = c
        if c is None or (cur_c and not _similar(cur_c[-1], c)):
            if cur_c and np.linalg.norm(p - cur_p[-1]) > 1e-5:
                pe, ce = edge(cur_p[-1], cur_c[-1], p)
                if np.linalg.norm(pe - cur_p[-1]) > 1e-5:
                    cur_p.append(pe)
                    cur_c.append(ce)
            flush()
        if c is not None:
            if not cur_c and prev is not None and prev[1] is None:
                ps, cs_ = edge(p, c, prev[0])
                if np.linalg.norm(ps - p) > 1e-5:
                    cur_p.append(ps)
                    cur_c.append(cs_)
            cur_p.append(p)
            cur_c.append(c)
        prev = (p, c)
    flush()
    return multi[0]


def _chain(runs) -> list[Seam]:
    """Join pieces whose ends meet (same kind, no sharp turn) into seams; mark closed loops."""
    tol = 2e-4
    pieces = [[np.array(p), list(c)] for p, c in runs if len(p) >= 2]
    # within a piece: drop points that repeat
    for pc in pieces:
        keep = [0]
        for i in range(1, len(pc[0])):
            if np.linalg.norm(pc[0][i] - pc[0][keep[-1]]) > 1e-6:
                keep.append(i)
        pc[0] = pc[0][keep]
        pc[1] = [pc[1][i] for i in keep]
    pieces = [pc for pc in pieces if len(pc[0]) >= 2]
    cos_sharp = math.cos(math.radians(SHARP))

    def can(c1, t1, c2, t2):
        return _similar(c1, c2) and float(t1 @ t2) > cos_sharp

    changed = True
    while changed:
        changed = False
        for i in range(len(pieces)):
            if pieces[i] is None:
                continue
            for j in range(len(pieces)):
                if i == j or pieces[j] is None:
                    continue
                pi, pj = pieces[i], pieces[j]
                for flip in (False, True):
                    qp, qc = (pj[0][::-1], pj[1][::-1]) if flip else (pj[0], pj[1])
                    if np.linalg.norm(pi[0][-1] - qp[0]) < tol:
                        ti = unit(pi[0][-1] - pi[0][-2])
                        tj = unit(qp[1] - qp[0])
                        if can(pi[1][-1], ti, qc[0], tj):
                            pi[0] = np.concatenate([pi[0], qp[1:]])
                            pi[1] = pi[1] + qc[1:]
                            pieces[j] = None
                            changed = True
                            break
                if pieces[j] is None:
                    continue
        pieces_ = [p for p in pieces if p is not None]
        if len(pieces_) != len(pieces):
            pieces = pieces_
            changed = True
            continue
    out = []
    for p, c in pieces:
        closed = False
        if len(p) > 3 and np.linalg.norm(p[0] - p[-1]) < tol:
            t1, t2 = unit(p[-1] - p[-2]), unit(p[1] - p[0])
            if can(c[-1], t1, c[0], t2):
                closed = True
                p, c = p[:-1], c[:-1]
        s = Seam(p, c, closed)
        kinds = [x.kind for x in c]
        s.kind = max(set(kinds), key=kinds.count)
        if s.length >= MIN_LEN:
            out.append(s)
    out.sort(key=lambda s: (-s.length, tuple(np.round(s.mid, 4))))
    _joins(out, tol)
    return out


def _joins(seams: list, tol: float) -> None:
    """Open seams whose ends meet at a turn (the corners of a square post, a fin's foot) are joined: their beads get
    mitred ends there instead of tapers, so the weld runs round the corner without a notch."""
    ends = []
    for i, s in enumerate(seams):
        if not s.closed:
            ends.append((i, 0, s.points[0], s.corners[0]))
            ends.append((i, 1, s.points[-1], s.corners[-1]))
    for x in range(len(ends)):
        i, e, p, c = ends[x]
        if seams[i].joins[e] is not None:
            continue
        for y in range(len(ends)):
            j, f, q, d = ends[y]
            if j == i or seams[j].joins[f] is not None or np.linalg.norm(p - q) > max(tol, 1e-3):
                continue
            if miter(c, d) is None:
                continue
            seams[i].joins[e] = (j, f)
            seams[j].joins[f] = (i, e)
            break


# ---------------------------------------------------------------------------
# the bead
# ---------------------------------------------------------------------------

@dataclass
class Look:
    """What the bead's shape needs from the weld's settings (sizes in metres)."""
    size: float = 0.005            # fillet: throat a; butt: cap width
    kind: str = "AUTO"             # AUTO (as found) / FILLET / BUTT
    finish: str = "AS_WELDED"
    craters: bool = False
    intermittent: bool = False
    length: float = 0.050
    pitch: float = 0.150
    heat: float = 0.012            # heat-zone width beyond each toe (0: none)
    across: int = 9                # points across the bead


def simplify(points: np.ndarray, corners: list, closed: bool, tol: float = 5e-5, turn_deg: float = 2.0):
    """Indices of the points to keep: the line stays within ``tol`` and the corner's faces within ``turn_deg``."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    keep = [0]
    i = 0
    cos_t = math.cos(math.radians(turn_deg))
    while i < n - 1:
        j = i + 1
        while j + 1 < n:
            cand = j + 1
            ok = True
            a, b = points[i], points[cand]
            ab = b - a
            L2 = float(ab @ ab)
            for k in range(i + 1, cand):
                s = float((points[k] - a) @ ab) / L2 if L2 > 0 else 0.0
                if np.linalg.norm(a + ab * s - points[k]) > tol:
                    ok = False
                    break
                ck = corners[k]
                if float(ck.da @ corners[i].da) < cos_t or float(ck.db @ corners[i].db) < cos_t \
                        or float(ck.da @ corners[cand].da) < cos_t or float(ck.db @ corners[cand].db) < cos_t:
                    ok = False
                    break
            if not ok:
                break
            j = cand
        keep.append(j)
        i = j
    return keep


def legs(c: Corner, look: Look, kind: str) -> tuple[float, float]:
    """(toe distance along A, along B) from the root."""
    if kind == "BUTT":
        return look.size / 2 * c.sa, look.size / 2 * c.sb
    half = math.radians(min(c.theta, 150.0)) / 2
    z = look.size / max(math.cos(half), 0.25)
    return z * c.sa, z * c.sb


def _ring(c: Corner, look: Look, kind: str, scale: float = 1.0, dip: float = 0.0):
    """Points across the bead from toe A to toe B (k, 3) at one corner."""
    za, zb = legs(c, look, kind)
    za, zb = za * scale, zb * scale
    root = 0.5 * (c.oa + c.ob)
    ta = root + c.da * za - c.na * TUCK
    tb = root + c.db * zb - c.nb * TUCK
    chord = tb - ta
    out = unit(c.mid if kind == "FILLET" else unit(c.na + c.nb))
    # the bulge square to the chord, into the air
    out = unit(out - chord * float(out @ chord) / max(float(chord @ chord), 1e-18))
    if kind == "BUTT":
        # ground flush: the cap's middle just over the plates (the toes are tucked in by TUCK)
        crown = 0.12 * look.size if look.finish != "GROUND" else TUCK + 0.00004
        h = crown
    else:
        h = (0.12 * look.size + 0.0003) if look.finish != "GROUND" else -0.04 * look.size
    h = h * scale * (1.0 - dip)
    if dip:
        h -= dip * 0.15 * look.size * scale
    s = np.linspace(0.0, 1.0, look.across)
    bump = np.sin(np.pi * s) ** 0.8
    pts = ta + np.outer(s, chord) + np.outer(bump * h, out)
    if kind == "BUTT" and look.finish != "GROUND":
        pts += np.outer(np.sin(np.pi * s) ** 4 * 0.0, out)
    return pts


def _arc_len(points: np.ndarray, closed: bool) -> np.ndarray:
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def pieces_of(total: float, look: Look, closed: bool) -> list[tuple[float, float]]:
    """(start, end) in metres along a seam: the whole seam, or the pieces of an intermittent weld. Gaps under 1 mm are
    no gaps (continuous). On a closed seam the pieces are spread evenly round it (the pitch rounded so they fit)."""
    if not look.intermittent or look.pitch < look.length + 0.001 or total <= look.length:
        return [(0.0, total)]
    if closed:
        n = max(1, int(round(total / look.pitch)))
        pitch = total / n
        if pitch < look.length + 0.001:
            return [(0.0, total)]
        return [(k * pitch, k * pitch + look.length) for k in range(n)]
    n = max(1, int((total - look.length) // look.pitch) + 1)
    used = (n - 1) * look.pitch + look.length
    s0 = 0.5 * (total - used)                               # centred on an open seam
    return [(s0 + k * look.pitch, s0 + k * look.pitch + look.length) for k in range(n)]


def _interp_corner(c1: Corner, c2: Corner, s: float) -> Corner:
    def lerp(x, y):
        return x + (y - x) * s
    return Corner(c1.kind, lerp(c1.theta, c2.theta), lerp(c1.oa, c2.oa), unit(lerp(c1.da, c2.da)),
                  unit(lerp(c1.na, c2.na)), c1.ta, lerp(c1.ob, c2.ob), unit(lerp(c1.db, c2.db)),
                  unit(lerp(c1.nb, c2.nb)), c1.tb, lerp(c1.sa, c2.sa), lerp(c1.sb, c2.sb))


def miter(c: Corner, other: Corner) -> Corner | None:
    """The corner at the end of a seam that meets ``other``'s end at a turn (a square post's corner): the face both
    share keeps its direction, the turning one takes the direction half way between the two, its toe stretched onto
    where the two toe lines meet. None when they do not share a face (no mitre)."""
    if c.kind != other.kind:
        return None
    same_a, same_b = float(c.da @ other.da) > 0.95, float(c.db @ other.db) > 0.95
    if same_a == same_b:
        return None
    out = Corner(c.kind, c.theta, c.oa, c.da, c.na, c.ta, c.ob, c.db, c.nb, c.tb, c.sa, c.sb)
    if same_b:
        m = c.da + other.da
        if np.linalg.norm(m) < 1e-6:
            return None
        out.da = unit(m)
        out.sa = c.sa / max(float(out.da @ c.da), 0.3)
        out.nb = unit(c.nb + other.nb)       # the shared part's corner edge: tucked in along both its faces
    else:
        m = c.db + other.db
        if np.linalg.norm(m) < 1e-6:
            return None
        out.db = unit(m)
        out.sb = c.sb / max(float(out.db @ c.db), 0.3)
        out.na = unit(c.na + other.na)
    return out


def _cut_piece(points, corners, closed, s0, s1):
    """Points and corners of the seam between arc lengths s0 and s1."""
    if closed:
        points = np.concatenate([points, points[:1]])
        corners = corners + corners[:1]
    L = _arc_len(points, False)

    def at(s):
        i = int(np.clip(np.searchsorted(L, s, side="right") - 1, 0, len(L) - 2))
        f = (s - L[i]) / max(L[i + 1] - L[i], 1e-12)
        f = min(max(f, 0.0), 1.0)
        return points[i] + (points[i + 1] - points[i]) * f, _interp_corner(corners[i], corners[i + 1], f)

    p0, c0 = at(s0)
    p1, c1 = at(s1)
    inner = [(points[i], corners[i]) for i in range(len(points)) if s0 + 1e-6 < L[i] < s1 - 1e-6]
    pts = [p0] + [p for p, _c in inner] + [p1]
    cs = [c0] + [c for _p, c in inner] + [c1]
    return np.array(pts), cs


@dataclass
class BeadMesh:
    verts: np.ndarray              # (n, 3) world m
    faces: list                    # quads / triangles (point numbers)
    uv: list                       # per face corner (u, v), same order as faces flattened
    mat: list                      # per face: 0 bead, 1 heat zone
    length: float = 0.0            # bead length (m), all pieces
    end: list = field(default_factory=list)   # per face corner: (start, end) of its piece in metres along the seam
    #                                              (closed: (-1000, 1000)); with u the shader knows how far an end is


def bead(seam: Seam, look: Look, surface_a: Side | None = None, surface_b: Side | None = None,
         ends: tuple = (None, None)) -> BeadMesh:
    """The bead (and heat-zone strips when surfaces are given and ``look.heat`` > 0) of one seam. ``ends``: the corner
    of the seam joined at its start / end (``Seam.joins``, when that one is welded too): a mitred end there, no taper."""
    kind = seam.kind if look.kind == "AUTO" else look.kind
    keep = simplify(seam.points, seam.corners, seam.closed)
    pts = seam.points[keep]
    cs = [seam.corners[i] for i in keep]
    mit = [None, None]
    if not seam.closed and not look.intermittent:
        for e, other in enumerate(ends):
            if other is not None:
                mit[e] = miter(cs[0 if e == 0 else -1], other)
        if mit[0] is not None:
            cs[0] = mit[0]
        if mit[1] is not None:
            cs[-1] = mit[1]
    closed = seam.closed
    total = float(_arc_len(np.concatenate([pts, pts[:1]]) if closed else pts, False)[-1])
    verts, faces, uvs, mats = [], [], [], []
    length = 0.0
    n_uv = 0
    ends = []
    pieces = pieces_of(total, look, closed)
    whole = closed and len(pieces) == 1 and pieces[0][1] - pieces[0][0] >= total - 1e-9
    for s0, s1 in pieces:
        if whole:
            pp, pc = pts, cs
        else:
            pp, pc = _cut_piece(pts, cs, closed, s0, s1)
        if len(pp) < 2:
            continue
        length += (total if whole else s1 - s0)
        _bead_piece(pp, pc, look, kind, whole, s0, verts, faces, uvs, mats,
                    taper=(not (mit[0] is not None and s0 <= 1e-9), not (mit[1] is not None and s1 >= total - 1e-9)))
        if surface_a is not None and surface_b is not None and look.heat > 0:
            _heat(pp, pc, look, kind, whole, s0, surface_a, surface_b, verts, faces, uvs, mats)
        span = (s0, s0 + float(_arc_len(pp, False)[-1])) if not whole else (-1000.0, 1000.0)
        if not whole:                         # a mitred end does not fade: the joined seam's tint goes on round it
            span = (-1000.0 if (mit[0] is not None and s0 <= 1e-9) else span[0],
                    1000.0 if (mit[1] is not None and s1 >= total - 1e-9) else span[1])
        ends.extend([span] * (len(uvs) - n_uv))
        n_uv = len(uvs)
    v = np.array(verts, np.float64).reshape(-1, 3) if verts else np.zeros((0, 3))
    return BeadMesh(v, faces, uvs, mats, length, ends)


def job_beads(shared: dict, jobs: list) -> list:
    """A helper process's job (task 0368, ``core/weld_pool.py``): ``bead(*job)`` for each job of one weld (its sides
    prepared here when they come unprepared)."""
    for job in jobs:
        for side in job[2:4]:
            if side is not None and side.v is None:
                side.prepare()
    return [bead(*job) for job in jobs]


def _bead_piece(pp, pc, look, kind, closed, s0, verts, faces, uvs, mats, taper=(True, True)):
    k = look.across
    cap = [False, False]
    if kind == "BUTT":                     # a butt weld ends square with its plates (run-off cut away): a flat end
        cap = [taper[0], taper[1]]
        taper = (False, False)
    u = s0 + _arc_len(pp, False)
    rings, us = [], []
    if not closed and taper[0]:                               # the start: a taper (and a crater) before the first point
        z = legs(pc[0], look, kind)[0]
        t = unit(pp[1] - pp[0])
        for f, sc in ((0.75, 0.05), (0.45, 0.55), (0.18, 0.88)):
            back = min(z * f, 0.45 * float(np.linalg.norm(pp[-1] - pp[0])))
            rings.append(_ring(pc[0], look, kind, sc, dip=0.0) - t * back)
            us.append(u[0] - back)
        if look.craters:
            rings[-1] = _ring(pc[0], look, kind, 0.88, dip=0.5) - t * min(z * 0.18, 0.45 * float(np.linalg.norm(pp[-1] - pp[0])))
    for p, c, uu in zip(pp, pc, u):
        rings.append(_ring(c, look, kind))
        us.append(uu)
    if not closed and taper[1]:
        z = legs(pc[-1], look, kind)[0]
        t = unit(pp[-1] - pp[-2])
        for f, sc in ((0.18, 0.88), (0.45, 0.55), (0.75, 0.05)):
            fwd = min(z * f, 0.45 * float(np.linalg.norm(pp[-1] - pp[0])))
            dip = 0.5 if (look.craters and f == 0.18) else 0.0
            rings.append(_ring(pc[-1], look, kind, sc, dip=dip) + t * fwd)
            us.append(u[-1] + fwd)
    base = len(verts)
    for r in rings:
        verts.extend(r.tolist())
    nr = len(rings)
    vs = np.linspace(0.0, 1.0, k)
    for i in range(nr - 1 + (1 if closed else 0)):
        j = (i + 1) % nr
        uj = us[j] if j > i else us[i] + float(np.linalg.norm(pp[0] - pp[-1]))
        for q in range(k - 1):
            a, b = base + i * k + q, base + i * k + q + 1
            c, d = base + j * k + q + 1, base + j * k + q
            faces.append((a, b, c, d))
            uvs.extend([(us[i], vs[q]), (us[i], vs[q + 1]), (uj, vs[q + 1]), (uj, vs[q])])
            mats.append(0)
    for e, on in enumerate(cap):
        if not on or closed:
            continue
        r = 0 if e == 0 else nr - 1
        ring = [base + r * k + q for q in range(k)]
        faces.append(tuple(ring if e == 0 else ring[::-1]))
        uvs.extend([(us[r], vs[q]) for q in (range(k) if e == 0 else range(k - 1, -1, -1))])
        mats.append(0)


def _project(side: Side, pts: np.ndarray, lift: float):
    d, q, t = side.nearest_local(pts, 0.01)
    ok = t >= 0
    out = pts.copy()
    out[ok] = q[ok] + side.n[t[ok]] * lift
    return out, d


HEAT_COLS = (0.0, 0.2, 0.45, 0.72, 1.0)


def _heat_rows(pts, cs, look, kind, which, side):
    """Rows of heat-strip points across the strip at each seam point, on the part's surface: (k, cols, 3)."""
    rows = []
    for c in cs:
        za, zb = legs(c, look, kind)
        root = 0.5 * (c.oa + c.ob)
        start = 0.0 if look.finish == "GROUND" else 0.92       # ground flush: the brushed band runs under the cap
        if which == "A":
            toe, d, n, st = root + c.da * za * start, c.da, c.na, c.sa
        else:
            toe, d, n, st = root + c.db * zb * start, c.db, c.nb, c.sb
        rows.append([toe + d * (look.heat * st * f) + n * LIFT for f in HEAT_COLS])
    rows = np.array(rows)
    flat, _d = _project(side, rows.reshape(-1, 3), LIFT)
    return flat.reshape(rows.shape)


def _sunk(side: Side, pts: np.ndarray) -> np.ndarray:
    """Which points lie less than half the lift above the part's surface (a strip's chord dipping under a curved,
    faceted face): bool per point."""
    d, q, t = side.nearest_local(pts, 0.01)
    ok = t >= 0
    h = np.full(len(pts), LIFT)
    h[ok] = ((pts[ok] - q[ok]) * side.n[t[ok]]).sum(1)
    return h < 0.5 * LIFT


def _heat(pp, pc, look, kind, closed, s0, sa, sb, verts, faces, uvs, mats):
    cols = HEAT_COLS
    for which, side in (("A", sa), ("B", sb)):
        pts, cs = list(pp), list(pc)
        u = list(s0 + _arc_len(np.array(pts), False))
        rows = list(_heat_rows(pts, cs, look, kind, which, side))
        for _round in range(5):                                # more rows where the strip would dip under a curve
            n = len(rows)
            pairs = [(i, i + 1) for i in range(n - 1)] + ([(n - 1, 0)] if closed else [])
            mids = np.array([0.5 * (rows[i] + rows[j]) for i, j in pairs]).reshape(-1, len(cols), 3)
            if not len(mids):
                break
            bad = _sunk(side, mids.reshape(-1, 3)).reshape(len(pairs), len(cols)).any(1)
            if not bad.any():
                break
            ks = sorted(np.flatnonzero(bad), reverse=True)
            new_p = [0.5 * (pts[pairs[k][0]] + pts[pairs[k][1]]) for k in ks]
            new_c = [_interp_corner(cs[pairs[k][0]], cs[pairs[k][1]], 0.5) for k in ks]
            new_rows = _heat_rows(new_p, new_c, look, kind, which, side)          # one projection for all of them
            for k, p, c, row in zip(ks, new_p, new_c, new_rows):
                i, j = pairs[k]
                uu = u[i] + 0.5 * float(np.linalg.norm(pts[j] - pts[i]))
                pts.insert(i + 1, p)
                cs.insert(i + 1, c)
                u.insert(i + 1, uu)
                rows.insert(i + 1, row)
        rows = np.array(rows)
        base = len(verts)
        verts.extend(rows.reshape(-1, 3).tolist())
        m = len(cols)
        nr = len(rows)
        for i in range(nr - 1 + (1 if closed else 0)):
            j = (i + 1) % nr
            uj = u[j] if j > i else u[i] + float(np.linalg.norm(pts[0] - pts[-1]))
            for q in range(m - 1):
                a, b = base + i * m + q, base + i * m + q + 1
                c_, d_ = base + j * m + q + 1, base + j * m + q
                # wound so the strip faces out of the part (its normal along the part's)
                faces.append((a, d_, c_, b) if which == "A" else (a, b, c_, d_))
                vv = [cols[q] * look.heat, cols[q + 1] * look.heat]
                if which == "A":
                    uvs.extend([(u[i], vv[0]), (uj, vv[0]), (uj, vv[1]), (u[i], vv[1])])
                else:
                    uvs.extend([(u[i], vv[0]), (u[i], vv[1]), (uj, vv[1]), (uj, vv[0])])
                mats.append(1)


# ---------------------------------------------------------------------------
# sizes, metals and rules
# ---------------------------------------------------------------------------

def thickness(side: Side, point, normal, reach: float = 0.2) -> float:
    """How thick the part is under ``point`` on its face of outward ``normal``: the ray into the part to the next
    face (m); 0 when nothing is hit."""
    p = np.asarray(point, np.float64) - unit(normal) * 1e-6
    d = -unit(normal)
    v = side.v
    if v is None or not len(v):
        return 0.0
    e1, e2 = v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]
    h = np.cross(d, e2)
    det = (e1 * h).sum(1)
    ok = np.abs(det) > 1e-15
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = p - v[:, 0]
    uu = (s * h).sum(1) * inv
    q = np.cross(s, e1)
    vv = (q @ d) * inv
    t = (e2 * q).sum(1) * inv
    hit = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 2e-5) & (t < reach)
    return float(t[hit].min()) if hit.any() else 0.0


def metal_of(material_id: str, category: str = "") -> str:
    """STEEL / STAINLESS / ALUMINIUM / GALVANISED / PAINTED / OTHER (not a metal one welds) from a look's id."""
    m = (material_id or "").lower()
    if "stainless" in m:
        return "STAINLESS"
    if "aluminium" in m or "aluminum" in m:
        return "ALUMINIUM"
    if "galv" in m or m.startswith("zinc"):
        return "GALVANISED"
    if category == "Paint" or m.startswith("paint") or m.startswith("powder") or m.endswith("_painted"):
        return "PAINTED"
    if category in ("Plastic & rubber", "Glass", "Light", "Other") and m not in ("", "from_file"):
        return "OTHER"
    if m in ("copper", "brass", "bronze", "chrome", "nickel_plated"):
        return "OTHER"
    return "STEEL"


def base_metal(kind: str) -> str:
    """The metal under a look: painted and galvanised parts are steel."""
    return kind if kind in ("STAINLESS", "ALUMINIUM") else "STEEL"


def defaults(kind_a: str, kind_b: str, thick_mm: float) -> dict:
    """The settings a new weld starts with, from the two parts' looks (``metal_of``) and the thinner part's thickness."""
    metal = base_metal(kind_a)
    t = thick_mm if thick_mm > 0 else 8.0
    process = {"STEEL": "MAG", "STAINLESS": "TIG", "ALUMINIUM": "MIG" if t >= 4.0 else "TIG"}[metal]
    painted = "A" if kind_a == "PAINTED" else ("B" if kind_b == "PAINTED" else "")
    a = min(12.0, max(2.0, round(0.5 * t * 2) / 2))
    return {"metal": metal, "process": process, "finish": "PAINTED" if painted else "AS_WELDED",
            "paint_from": painted or "A", "size": a, "butt_width": round(1.15 * t + 2.0, 1),
            "zinc": "GALVANISED" in (kind_a, kind_b)}


def warning(kind_a: str, kind_b: str) -> str:
    """A calm word when the two parts are not the same metal ('' when they are)."""
    words = {"STEEL": "steel", "STAINLESS": "stainless steel", "ALUMINIUM": "aluminium"}
    if "OTHER" in (kind_a, kind_b):
        return "One of the parts does not look like a metal that is welded – check its look (3 Looks)"
    ma, mb = base_metal(kind_a), base_metal(kind_b)
    if ma != mb:
        return (f"The parts are {words[ma]} and {words[mb]}: a weld between them is unusual – the bead shows "
                f"the look of {words[ma]}")
    return ""


def rust_of(metal: str, finish: str, rust: float, wear: float, zinc: bool, zinc_sprayed: bool, pickled: bool) -> dict:
    """Where the weld rusts (study of the brief, 0..1 each): ``bead`` and ``heat`` red rust on the bead and its heat
    zone, ``toes`` rust where worn paint left the toes bare, ``tea`` a faint brown on unpickled stainless."""
    rust = max(0.0, min(1.0, rust))
    out = {"bead": 0.0, "heat": 0.0, "toes": 0.0, "tea": 0.0}
    if metal == "ALUMINIUM":
        return out                                           # aluminium never rusts
    if metal == "STAINLESS":
        out["tea"] = 0.0 if pickled else 0.35 * rust
        return out
    if finish == "PAINTED":
        out["toes"] = rust * min(1.0, wear * 2.0)             # only where Wear took the paint off
        return out
    if zinc and zinc_sprayed:
        return out
    out["bead"] = min(1.0, rust * 1.4)                       # the bead and its heat zone rust first
    out["heat"] = min(1.0, rust * 1.2)
    return out


def heat_width(metal: str, size: float) -> float:
    base, k = HEAT.get(metal, HEAT["STEEL"])
    return base + k * size


# ---------------------------------------------------------------------------
# finding picked faces again after a model update
# ---------------------------------------------------------------------------

def face_prints(points: np.ndarray, tris: np.ndarray, face: np.ndarray, faces) -> dict:
    """{face: [cx, cy, cz, area, nx, ny, nz]} in the part's own coordinates: centre, area and area-weighted normal."""
    pts = np.asarray(points, np.float64)
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    face = np.asarray(face, np.int64)
    out = {}
    for f in faces:
        sel = face == int(f)
        if not sel.any():
            continue
        v = pts[tris[sel]]
        cr = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        ar = 0.5 * np.linalg.norm(cr, axis=1)
        A = float(ar.sum())
        c = (v.mean(1) * ar[:, None]).sum(0) / A if A > 0 else v.reshape(-1, 3).mean(0)
        n = 0.5 * cr.sum(0) / A if A > 0 else np.zeros(3)
        out[int(f)] = [*map(float, c), A, *map(float, n)]
    return out


def match_faces(prints: dict, points: np.ndarray, tris: np.ndarray, face: np.ndarray, tol: float = 0.0005):
    """{old face: new face or None}: the new face with the same centre (within ``tol`` + 0.5 % of its size), area (3 %)
    and mean normal."""
    face = np.asarray(face, np.int64)
    new = face_prints(points, tris, face, np.unique(face[face >= 0]))
    keys = list(new)
    arr = np.array([new[k] for k in keys]) if keys else np.zeros((0, 7))
    out = {}
    for f, pr in prints.items():
        pr = np.asarray(pr, np.float64)
        if not len(arr):
            out[int(f)] = None
            continue
        dc = np.linalg.norm(arr[:, :3] - pr[:3], axis=1)
        size = math.sqrt(max(pr[3], 1e-12))
        da = np.abs(arr[:, 3] - pr[3]) / max(pr[3], 1e-12)
        dn = np.linalg.norm(arr[:, 4:] - pr[4:], axis=1)
        ok = (dc <= tol + 0.005 * size) & (da <= 0.03) & (dn <= 0.05)
        if not ok.any():
            out[int(f)] = None
            continue
        j = np.flatnonzero(ok)[np.argmin(dc[ok])]
        out[int(f)] = int(keys[j])
    return out


# ---------------------------------------------------------------------------
# keeping seams in the project
# ---------------------------------------------------------------------------

KIND_CODE = {"FILLET": 0, "BUTT": 1}
_ROW = 26                 # floats per point: p, oa, da, na, ob, db, nb (3 each), theta, sa, sb, ta, tb


def pack_seams(seams: list) -> str:
    """The seams as text for the project (base64 of 32-bit numbers), simplified as the bead uses them; ``unpack_seams``
    gives them back. A weld keeps its seams where they were found, so a change of a setting never looks for them again
    where the parts happen to stand (an exploded view, a pose)."""
    import base64
    out = [np.array([len(seams)], np.float32)]
    for s in seams:
        keep = simplify(s.points, s.corners, s.closed)
        j0 = s.joins[0] or (-1, -1)
        j1 = s.joins[1] or (-1, -1)
        out.append(np.array([len(keep), float(s.closed), KIND_CODE.get(s.kind, 0), j0[0], j0[1], j1[0], j1[1]],
                            np.float32))
        rows = []
        for i in keep:
            c = s.corners[i]
            rows.append(np.concatenate([s.points[i], c.oa, c.da, c.na, c.ob, c.db, c.nb,
                                        [c.theta, c.sa, c.sb, c.ta, c.tb]]))
        out.append(np.asarray(rows, np.float32).ravel())
    return base64.b64encode(np.concatenate(out).tobytes()).decode("ascii")


def unpack_seams(text: str) -> list:
    import base64
    a = np.frombuffer(base64.b64decode(text.encode("ascii")), np.float32).astype(np.float64)
    n = int(a[0])
    at = 1
    out = []
    kinds = {v: k for k, v in KIND_CODE.items()}
    for _ in range(n):
        k, closed, kind = int(a[at]), bool(a[at + 1]), kinds.get(int(a[at + 2]), "FILLET")
        j = [int(x) for x in a[at + 3:at + 7]]
        at += 7
        rows = a[at:at + k * _ROW].reshape(k, _ROW)
        at += k * _ROW
        cs = [Corner(kind, float(r[21]), r[3:6].copy(), unit(r[6:9]), unit(r[9:12]), int(r[24]),
                     r[12:15].copy(), unit(r[15:18]), unit(r[18:21]), int(r[25]), float(r[22]), float(r[23]))
              for r in rows]
        s = Seam(rows[:, :3].copy(), cs, closed, kind)
        s.joins = [(j[0], j[1]) if j[0] >= 0 else None, (j[2], j[3]) if j[2] >= 0 else None]
        out.append(s)
    return out
