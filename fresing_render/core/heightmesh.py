"""Thinning one tile of the height map into long strips (task 0167). NumPy only.

Why
---
Task 0146 thinned a tile with a hierarchy of right triangles: a node is kept where leaving it out would move the
surface. That is *isotropic*: along a line that must be kept (the edge of a pass, a wall, the ridge between two
finishing passes) every node is kept, and the triangles round it stay small in both directions. The exact cut has
one long strip per pass there. A milling program runs along lines, so its surface changes little along them: this
module thins along the lines and keeps the rows across them.

How
---
A tile is ``n`` x ``n`` nodes (``n`` = 2^p + 1). One direction is picked per tile (``x``: the **chains** are the rows
of nodes, ``y``: the columns; the one that keeps fewer nodes). Then:

1. **Rows.** A row can be left out when every node of it lies within ``tol`` of the straight line between the same
   column's nodes of the kept rows above and below it, and the mark class of each column does not change between
   them. Decided by halving (rows 0 and n - 1 are always kept).
2. **Chains.** Along each kept row a node is kept where the straight line between the kept nodes beside it would
   miss a left-out node by more than ``tol``, or would join two mark classes. Also by halving; each final piece
   is checked against every node it replaces.
3. **Zip.** Between two kept rows the kept nodes of both are joined by a zip: walking from left to right, always
   advancing the row whose next node comes first (where both come at the same column of neighbouring rows, the
   way the finest triangles of the grid run - the same diagonal ``_snap`` looks at).
4. **Check.** The zip is compared with the finest triangles of the grid (every cell cut by its diagonal): every
   left-out node, and points along every edge between two rows where it crosses the grid's lines. Where the zip
   is more than ``tol`` off, a left-out row is kept again, or (between neighbouring rows) the nodes there; then
   zipped again.

Nodes on the tile's border: each tile decides its own (``own``), then takes the ones its neighbours keep on the
border they share (``forced``). Those never make it keep more: a node forced on a border chain (the first and last
row; with ``y`` the columns) joins that chain; one forced at the end of a row that was left out joins the side of
the zip between the two kept rows as a fan. So the tiles meet node for node, also near a corner where three meet.

Everything here works in **frame** indices (row, column) of the chosen direction; ``x`` is the tile's own, ``y`` its
transpose. Node number in the tile: ``row * n + column`` (of the tile, not the frame).
"""

from __future__ import annotations

import math

import numpy as np

CHECK_ROUNDS = 6                  # rounds of check and fix before the strips that are still off are kept whole


# ---------------------------------------------------------------------------
# the hierarchy of right triangles of one tile (task 0146)
# ---------------------------------------------------------------------------

_RTIN: dict = {}


def rtin(n: int) -> dict:
    """The right-triangle hierarchy of a tile of ``n`` x ``n`` cells (``n`` a power of two), worked out once.

    ``levels[l]`` = (a, b, c, m): node numbers (row * (n + 1) + column) of every triangle of level ``l`` - the
    ends of its long side, its right-angled corner, the middle of the long side (None at the last level). The
    children of triangle ``t`` are ``2 t`` and ``2 t + 1`` of the next level. ``groups[l]`` = (order, starts,
    nodes): the triangles of a level sorted by their middle node, to take the largest value per node."""
    hit = _RTIN.get(n)
    if hit is not None:
        return hit
    p = int(round(math.log2(n)))
    if 2 ** p != n:
        raise ValueError("a tile has a power of two cells along its side")
    a = np.array([[0, 0], [n, n]])
    b = np.array([[n, n], [0, 0]])
    c = np.array([[n, 0], [0, n]])
    idx = lambda q: (q[:, 1] * (n + 1) + q[:, 0]).astype(np.int64)      # noqa: E731
    levels, groups = [], []
    for level in range(2 * p + 1):
        last = level == 2 * p
        m = (a + b) // 2
        levels.append((idx(a), idx(b), idx(c), None if last else idx(m)))
        if not last:
            mi = idx(m)
            order = np.argsort(mi, kind="stable")
            nodes, starts = np.unique(mi[order], return_index=True)
            groups.append((order, starts, nodes))
            na, nb, nc = (np.empty((2 * len(a), 2), np.int64) for _k in range(3))
            na[0::2], na[1::2] = c, b
            nb[0::2], nb[1::2] = a, c
            nc[0::2], nc[1::2] = m, m
            a, b, c = na, nb, nc
    t = np.arange(n + 1)
    # the border once round, counter-clockwise seen from above (x to the right, y up)
    ring = np.concatenate([t[:-1], t[:-1] * (n + 1) + n, n * (n + 1) + t[:0:-1], t[:0:-1] * (n + 1)])
    hit = _RTIN[n] = dict(levels=levels, groups=groups, ring=ring, p=p,
                          sides=(t, t * (n + 1) + n, n * (n + 1) + t, t * (n + 1)))    # bottom, right, top, left
    return hit


def rtin_needed(tab: dict, P: np.ndarray, cls: np.ndarray, tol: float, forced: np.ndarray | None = None) -> np.ndarray:
    """Which nodes of a tile the thinned-out mesh keeps: True where leaving the node out would move the surface
    by more than ``tol`` (its distance from the middle of the long side it halves), would join two mark classes,
    or where a node below it in the hierarchy is kept. ``forced``: nodes kept whatever their own error."""
    levels, groups = tab["levels"], tab["groups"]
    need = np.zeros(len(P), bool) if forced is None else forced.copy()
    for level in range(len(groups) - 1, -1, -1):
        a, b, _c, m = levels[level]
        d = P[m] - 0.5 * (P[a] + P[b])
        val = (np.einsum("ij,ij->i", d, d) > tol * tol) | (cls[a] != cls[m]) | (cls[b] != cls[m])
        if level + 1 < len(groups):
            below = need[levels[level + 1][3]]
            val |= below[0::2] | below[1::2]
        order, starts, nodes = groups[level]
        need[nodes] |= np.logical_or.reduceat(val[order], starts)
    return need


def rtin_triangles(tab: dict, need: np.ndarray) -> np.ndarray:
    """The triangles (node numbers, counter-clockwise seen from above) of the hierarchy cut off where ``need``
    says a long side's middle is not kept."""
    levels = tab["levels"]
    act = np.arange(2)
    out = []
    for level, (a, b, c, m) in enumerate(levels):
        if m is None:
            split = np.zeros(len(act), bool)
        else:
            split = need[m[act]]
        done = act[~split]
        if len(done):
            out.append(np.stack([a[done], c[done], b[done]], axis=1))
        act = act[split]
        if not len(act):
            break
        act = np.stack([2 * act, 2 * act + 1], axis=1).reshape(-1)
    return np.concatenate(out) if out else np.zeros((0, 3), np.int64)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _seg_dist(p, a, b):
    """Distance of the points ``p`` from the segments ``a`` - ``b`` (arrays (..., 3) that broadcast)."""
    ab = b - a
    L2 = np.einsum("...k,...k->...", ab, ab)
    t = np.einsum("...k,...k->...", p - a, ab) / np.maximum(L2, 1e-300)
    t = np.clip(t, 0.0, 1.0)
    d = p - (a + t[..., None] * ab)
    return np.sqrt(np.einsum("...k,...k->...", d, d))


def _levels(n: int) -> list:
    """The halving of 0 .. n - 1 from the coarsest: [(half, middles), ...]."""
    out, half = [], (n - 1) // 2
    while half >= 1:
        out.append((half, np.arange(half, n - 1, 2 * half)))
        half //= 2
    return out


def _halving(bad_of, forced: np.ndarray, n: int) -> np.ndarray:
    """Which places 0 .. n - 1 (along the last axis of ``forced``) a halving keeps: the two ends; the middle of a
    piece whose parent was split, when the piece is bad (``bad_of(half, middles)`` -> bool (..., pieces): a node
    inside the piece is too far from the straight line, or the classes differ) or holds a forced place."""
    keep = forced.copy()
    keep[..., 0] = keep[..., -1] = True
    split = np.ones(forced.shape[:-1] + (1,), bool)       # the whole range is one piece, split if it must be
    cum = np.concatenate([np.zeros(forced.shape[:-1] + (1,), np.int64), np.cumsum(forced, axis=-1)], axis=-1)
    for half, mid in _levels(n):
        a, b = mid - half, mid + half
        inside = (cum[..., b] - cum[..., a + 1]) > 0         # a forced place strictly inside
        s = split & (bad_of(half, mid) | inside)
        keep[..., mid] |= s
        split = s.repeat(2, axis=-1)
    return keep


# ---------------------------------------------------------------------------
# 1. and 2.: rows and chains
# ---------------------------------------------------------------------------

def _rows_kept(Q: np.ndarray, cls: np.ndarray, tol: float) -> np.ndarray:
    """(n,) bool: the rows kept (frame indices). ``Q`` (n, n, 3), ``cls`` (n, n)."""
    n = Q.shape[0]

    def bad(half, mid):
        a, b = mid - half, mid + half
        w = 2 * half
        blocks = Q[:-1].reshape(-1, w, n, 3)[:, 1:]                       # (pieces, w - 1, n, 3)
        d = _seg_dist(blocks, Q[a][:, None], Q[b][:, None])
        cb = cls[:-1].reshape(-1, w, n)
        same = (cb == cb[:, :1]).all(axis=(1, 2)) & (cls[b] == cls[a]).all(axis=1)
        return (d > tol).any(axis=(1, 2)) | ~same
    return _halving(bad, np.zeros(n, bool), n)


def _chains(Q: np.ndarray, cls: np.ndarray, tol: float, forced: np.ndarray) -> np.ndarray:
    """(m, n) bool: the nodes kept along each of ``m`` rows (``Q`` (m, n, 3), ``cls`` (m, n))."""
    m, n = cls.shape

    def bad(half, mid):
        a, b = mid - half, mid + half
        w = 2 * half
        # every node strictly inside each piece, against the piece's chord: blocks of w nodes from a on
        blocks = Q[:, :-1].reshape(m, -1, w, 3)[:, :, 1:]                   # (m, pieces, w - 1, 3)
        d = _seg_dist(blocks, Q[:, a][:, :, None], Q[:, b][:, :, None])
        cb = cls[:, :-1].reshape(m, -1, w)
        same = (cb == cb[:, :, :1]).all(axis=2) & (cls[:, b] == cls[:, a])
        return (d > tol).any(axis=2) | ~same
    return _halving(bad, forced, n)


def _prune(Q: np.ndarray, cls: np.ndarray, K: np.ndarray, tol: float) -> np.ndarray:
    """Kept nodes of the chains (``K`` (m, n) for the ``m`` rows of ``Q``) that halving kept only because the
    pieces had to be halves: left out where the straight line between the kept nodes beside them still passes
    every node between within ``tol`` and joins no two classes. Every other one at a time, both ways round."""
    m, n = K.shape
    K = K.copy()
    cols = np.arange(n)
    for _round in range(2):
        for parity in (1, 0):
            rank = np.cumsum(K, axis=1) - 1                       # place of each kept node in its chain
            cand = K & (rank % 2 == parity)
            cand[:, 0] = cand[:, -1] = False
            r, c = np.nonzero(cand)
            if not len(r):
                continue
            # the kept nodes before and after each candidate
            prev = np.where(K, cols[None, :], -1)
            prev = np.maximum.accumulate(prev, axis=1)
            nxt = np.where(K, cols[None, :], n)
            nxt = np.minimum.accumulate(nxt[:, ::-1], axis=1)[:, ::-1]
            a = prev[r, c - 1]
            b = nxt[r, c + 1]
            inside = (cols[None, :] > a[:, None]) & (cols[None, :] < b[:, None])
            d = _seg_dist(Q[r], Q[r, a][:, None], Q[r, b][:, None])
            span = (cols[None, :] >= a[:, None]) & (cols[None, :] <= b[:, None])
            same = np.all(~span | (cls[r] == cls[r, a][:, None]), axis=1)
            ok = same & np.all(~inside | (d <= tol), axis=1)
            K[r[ok], c[ok]] = False
    return K


# ---------------------------------------------------------------------------
# 3.: the zip
# ---------------------------------------------------------------------------

class Zip:
    """The zip of every strip between kept rows ``R`` of a kept-node mask ``K`` (frame, (n, n)).

    Per event (one triangle each, sorted by strip and then left to right): ``s`` the strip, ``top`` whether the
    top row advanced, ``b0, t0`` the bottom and top nodes' columns before it, ``b1, t1`` after. Triangle corners
    (frame (row, column)): bottom event (r0, b0), (r0, b1), (r1, t0); top event (r0, b0), (r1, t1), (r1, t0) -
    counter-clockwise with the column as x and the row as y."""

    def __init__(self, K: np.ndarray, R: np.ndarray, parity: int = 0):
        n = K.shape[1]
        self.n, self.R = n, R
        KB, KT = K[R[:-1], 1:], K[R[1:], 1:]
        sb, cb = np.nonzero(KB)
        st, ct = np.nonzero(KT)
        cb, ct = cb + 1, ct + 1
        # (both rows' next node in the same column c of neighbouring rows: the finest triangles' diagonal decides
        # - from the bottom node c - 1 up to the top node c where the cell's row + column is even: top first)
        eb = (R[sb] + cb - 1 + parity) % 2 == 0
        et = (R[st] + ct - 1 + parity) % 2 == 0
        span = 2 * n + 2
        keys = np.concatenate([sb * span + 2 * cb + eb, st * span + 2 * ct + ~et])
        s = np.concatenate([sb, st])
        c = np.concatenate([cb, ct])
        top = np.concatenate([np.zeros(len(sb), bool), np.ones(len(st), bool)])
        o = np.argsort(keys, kind="stable")
        s, c, top = s[o], c[o], top[o]
        big = 4 * n
        b1 = np.maximum.accumulate(s * big + np.where(top, 0, c)) - s * big
        t1 = np.maximum.accumulate(s * big + np.where(top, c, 0)) - s * big
        first = np.ones(len(s), bool)
        first[1:] = s[1:] != s[:-1]
        b0, t0 = np.roll(b1, 1), np.roll(t1, 1)
        b0[first], t0[first] = 0, 0
        self.s, self.top, self.b0, self.t0, self.b1, self.t1, self.first = s, top, b0, t0, b1, t1, first
        self.r0, self.r1 = R[s], R[s + 1]
        last = np.ones(len(s), bool)
        last[:-1] = s[1:] != s[:-1]
        self.last = last

    def corners(self) -> np.ndarray:
        """(events, 3, 2): the triangles' corners as (row, column)."""
        A = np.stack([self.r0, self.b0], axis=1)
        B = np.where(self.top[:, None], np.stack([self.r1, self.t1], axis=1), np.stack([self.r0, self.b1], axis=1))
        C = np.stack([self.r1, self.t0], axis=1)
        return np.stack([A, B, C], axis=1)


def _ref(Q: np.ndarray, y, x, parity: int = 0):
    """The finest triangles of the grid at the places (row ``y``, column ``x``), floats: (..., 3)."""
    n = Q.shape[0]
    i = np.clip(np.floor(y).astype(np.int64), 0, n - 2)
    j = np.clip(np.floor(x).astype(np.int64), 0, n - 2)
    fy, fx = (y - i)[..., None], (x - j)[..., None]
    P00, P01, P10, P11 = Q[i, j], Q[i, j + 1], Q[i + 1, j], Q[i + 1, j + 1]
    even = ((i + j + parity) % 2 == 0)[..., None]
    lower = fx >= fy
    v_even = np.where(lower, P00 + fx * (P01 - P00) + fy * (P11 - P01), P00 + fy * (P10 - P00) + fx * (P11 - P10))
    ll = (fx + fy) <= 1.0
    v_odd = np.where(ll, P00 + fx * (P01 - P00) + fy * (P10 - P00),
                     P11 + (1.0 - fx) * (P10 - P11) + (1.0 - fy) * (P01 - P11))
    return np.where(even, v_even, v_odd)


def _plane_dist(T: np.ndarray, p: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Distance of the points ``p`` from the planes of the triangles ``T`` (k, 3, 3); where a triangle has no area,
    from ``z`` (the point of the triangle at the same place)."""
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    e = np.max(np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2), axis=1)
    ok = ln > 1e-9 * np.maximum(e * e, 1e-300)
    d = np.abs(np.einsum("ij,ij->i", nrm, p - T[:, 0])) / np.maximum(ln, 1e-300)
    return np.where(ok, d, np.linalg.norm(p - z, axis=1))


def _check(Q: np.ndarray, K: np.ndarray, R: np.ndarray, z: Zip, tol: float, parity: int):
    """Where the zip is more than ``tol`` off the finest triangles: (rows to keep, nodes to keep) as frame indices
    - a list of rows, and (row, column) pairs."""
    n = Q.shape[0]
    tri = z.corners()
    T = Q[tri[:, :, 0], tri[:, :, 1]]                         # (events, 3, 3)
    rows_add, nodes_add = [], []
    E = len(z.s)
    nstrip = len(R) - 1
    # states: per strip the edge before its first event, then after each event
    starts = np.flatnonzero(z.first)
    # -- a) every node of a left-out row, against the triangle it lies in -------------------------------------
    gap = R[1:] - R[:-1]
    multi = np.flatnonzero(gap > 1)
    if len(multi):
        ks = np.concatenate([np.arange(R[s] + 1, R[s + 1]) for s in multi])
        ss = np.repeat(multi, gap[multi] - 1)
        frac = (ks - R[ss]) / (R[ss + 1] - R[ss])
        # the states of each strip (its first state 0, 0 and the state after each event)
        ev_count = np.bincount(z.s, minlength=nstrip)
        st_start = np.concatenate([[0], np.cumsum(ev_count + 1)])[:-1]
        Sb = np.zeros(E + nstrip, np.int64)
        St = np.zeros(E + nstrip, np.int64)
        pos = np.arange(E) + z.s + 1                         # (each strip's states shifted by the strips before)
        Sb[pos], St[pos] = z.b1, z.t1
        cnt = ev_count[ss] + 1
        g = np.repeat(np.arange(len(ks)), cnt)
        idx = np.repeat(st_start[ss], cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))
        xs = Sb[idx] + frac[g] * (St[idx] - Sb[idx]) + g * (2.0 * n)
        cols = np.arange(n)
        qg = np.repeat(np.arange(len(ks)), n)
        qx = np.tile(cols, len(ks)).astype(float)
        loc = np.searchsorted(xs, qx + qg * (2.0 * n), side="right") - 1
        first_of = np.repeat(np.cumsum(cnt) - cnt, n)
        local = np.clip(loc - first_of, 0, np.repeat(cnt, n) - 2)
        ev = starts[ss][qg] + local                             # the event (triangle) the node lies in
        qk = np.repeat(ks, n)
        P = Q[qk, np.tile(cols, len(ks))]
        # (the point of that triangle at the node's place, for triangles without area)
        tc = tri[ev].astype(float)
        a, b, c = tc[:, 0], tc[:, 1], tc[:, 2]
        v0, v1 = b - a, c - a
        w = np.stack([qk.astype(float), qx], axis=1) - a
        den = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
        den = np.where(np.abs(den) < 1e-12, 1.0, den)
        l1 = (w[:, 0] * v1[:, 1] - w[:, 1] * v1[:, 0]) / den
        l2 = (v0[:, 0] * w[:, 1] - v0[:, 1] * w[:, 0]) / den
        Z = T[ev, 0] + l1[:, None] * (T[ev, 1] - T[ev, 0]) + l2[:, None] * (T[ev, 2] - T[ev, 0])
        d = _plane_dist(T[ev], P, Z)
        off = d > tol
        if off.any():
            rows_add.extend(np.unique(qk[off]).tolist())
    # -- b) the edges between the rows, where they cross the grid's lines ----------------------------------------
    inner = ~z.last                                          # the state after each event but the last of a strip
    e = np.flatnonzero(inner)
    if len(e):
        b, t, r0, r1 = z.b1[e], z.t1[e], z.r0[e], z.r1[e]
        dc, dr = np.abs(t - b), r1 - r0
        fine = (dr == 1) & ((dc == 0) | ((dc == 1) & (((r0 + np.minimum(b, t) + parity) % 2 == 0) == (t > b))))
        e, b, t, r0, r1, dc, dr = e[~fine], b[~fine], t[~fine], r0[~fine], r1[~fine], dc[~fine], dr[~fine]
        if len(e):
            cnt = 2 * (dc + dr)
            g = np.repeat(np.arange(len(e)), cnt - 1)
            j = np.arange(int((cnt - 1).sum())) - np.repeat(np.cumsum(cnt - 1) - (cnt - 1), cnt - 1) + 1
            f = j / cnt[g]
            y = r0[g] + f * dr[g]
            x = b[g] + f * (t[g] - b[g])
            Rf = _ref(Q, y, x, parity)
            Zp = Q[r0[g], b[g]] + f[:, None] * (Q[r1[g], t[g]] - Q[r0[g], b[g]])
            d = np.maximum(_plane_dist(T[e[g]], Rf, Zp), _plane_dist(T[e[g] + 1], Rf, Zp))
            off = d > tol
            if off.any():
                gy, gx, gr0, gr1 = y[off], x[off], r0[g][off], r1[g][off]
                many = gr1 - gr0 > 1
                if many.any():
                    k = np.clip(np.rint(gy[many]), gr0[many] + 1, gr1[many] - 1).astype(np.int64)
                    rows_add.extend(np.unique(k).tolist())
                one = ~many
                if one.any():
                    for col in (np.floor(gx[one]), np.ceil(gx[one])):
                        col = np.clip(col, 0, n - 1).astype(np.int64)
                        nodes_add.append(np.stack([gr0[one], col], axis=1))
                        nodes_add.append(np.stack([gr1[one], col], axis=1))
    nodes = np.unique(np.concatenate(nodes_add), axis=0) if nodes_add else np.zeros((0, 2), np.int64)
    return sorted(set(rows_add)), nodes


# ---------------------------------------------------------------------------
# the whole: own and forced
# ---------------------------------------------------------------------------

def _frame(arr, axis: str):
    """A (n, n, ...) array in the frame of a direction (``y``: transposed)."""
    return arr if axis == "x" else np.swapaxes(arr, 0, 1)


def _estimate(K: np.ndarray, R: np.ndarray) -> int:
    """How many triangles the zip of these rows has (each kept node but a row's first adds one to each strip it
    borders)."""
    per = K[R].sum(axis=1) - 1
    return int(2 * per.sum() - per[0] - per[-1])


def _zip_tris(z: Zip, axis: str, n: int) -> np.ndarray:
    """The zip's triangles as node numbers of the tile, counter-clockwise seen from above."""
    tri = z.corners()
    if axis == "x":
        return (tri[:, :, 0] * n + tri[:, :, 1]).astype(np.int64)
    return (tri[:, :, 1] * n + tri[:, :, 0])[:, ::-1].astype(np.int64)    # (transposed: every turn flips)


def own(P: np.ndarray, Q: np.ndarray, cls: np.ndarray, tol: float, parity: int = 0) -> dict:
    """A tile's own thinning, without its neighbours: ``P``, ``Q`` (n, n, 3) the nodes (``Q``: as judged, without
    the fine ridges), ``cls`` (n, n) mark classes. Of the right triangles (task 0146) and the strips along x or y,
    the one with the fewest triangles. Returns ``kind`` ("rtin", "x" or "y"), ``tri`` (m, 3) node numbers of the
    tile, counter-clockwise seen from above, and ``need`` (n * n bool: the nodes they use)."""
    n = Q.shape[0]
    tab = rtin(n - 1)
    need = rtin_needed(tab, Q.reshape(-1, 3), cls.reshape(-1), tol)
    tri = rtin_triangles(tab, need)
    best = dict(kind="rtin", tri=tri, need=need)
    if len(tri) <= 2:
        return best
    cands = []
    for axis in ("x", "y"):
        q, c = _frame(Q, axis), _frame(cls, axis)
        R = np.flatnonzero(_rows_kept(q, c, tol))
        K = np.zeros((n, n), bool)
        K[R] = _prune(q[R], c[R], _chains(q[R], c[R], tol, np.zeros((len(R), n), bool)), tol)
        cands.append((_estimate(K, R), axis, R, K))
    cands.sort(key=lambda x: x[0])
    for est, axis, R, K in cands:
        if est >= len(best["tri"]):
            break
        R, K = _checked(_frame(Q, axis), _frame(cls, axis), R, K, tol, parity)
        R, K, z = _unfolded(P, Q, cls, tol, R, K, axis, parity)
        tri = _zip_tris(z, axis, n)
        if len(tri) < len(best["tri"]):
            need = np.zeros(n * n, bool)
            need[tri.reshape(-1)] = True
            best = dict(kind=axis, tri=tri, need=need)
    return best


def _unfolded(P: np.ndarray, Q: np.ndarray, cls: np.ndarray, tol: float, R, K, axis: str, parity: int) -> tuple:
    """The zip, where no triangle lies turned over seen from above at the nodes' real places (nodes moved onto a
    wall can make a long triangle fold): round such a triangle every row of its strip is kept, with every node
    under it and one more each side; after a few rounds the strip whole. Returns (R, K, zip)."""
    n = K.shape[0]
    p = _frame(P, axis)
    q, c = _frame(Q, axis), _frame(cls, axis)
    for _round in range(6):
        z = Zip(K, R, parity)
        tri = z.corners()
        T = p[tri[:, :, 0], tri[:, :, 1]]
        e1, e2 = T[:, 1, :2] - T[:, 0, :2], T[:, 2, :2] - T[:, 0, :2]
        area = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        size = np.maximum(np.einsum("ij,ij->i", e1, e1), np.einsum("ij,ij->i", e2, e2))
        if axis == "y":
            area = -area                                 # (the frame is the tile turned over)
        span = tri[:, :, 1].max(axis=1) - tri[:, :, 1].min(axis=1)
        finest = (z.r1 - z.r0 == 1) & (span <= 1)              # (the grid's own triangles: nothing to keep)
        bad = np.flatnonzero((area < -1e-9 * size) & ~finest)
        if not len(bad):
            return R, K, z
        if _round >= 3:
            for s in np.unique(z.s[bad]):
                K[R[s]:R[s + 1] + 1] = True
        else:
            force = np.zeros((n, n), bool)
            for e in bad:
                r0, r1 = z.r0[e], z.r1[e]
                lo, hi = max(0, tri[e, :, 1].min() - 1), min(n - 1, tri[e, :, 1].max() + 1)
                force[r0:r1 + 1, lo:hi + 1] = True
            rows = np.flatnonzero(force.any(axis=1))
            new = np.setdiff1d(rows, R)
            K[rows] |= force[rows]
            if len(new):
                K[new] = _chains(q[new], c[new], tol, K[new])
        R = np.flatnonzero(K.any(axis=1))
    return R, K, Zip(K, R, parity)


def _checked(q, c, R, K, tol, parity):
    """Rows and nodes after checking the zip against the finest triangles and keeping more where it is off."""
    n = q.shape[0]
    K = K.copy()
    for _round in range(CHECK_ROUNDS + 1):
        z = Zip(K, R, parity)
        rows_add, nodes_add = _check(q, K, R, z, tol, parity)
        if not rows_add and not len(nodes_add):
            return R, K
        if _round == CHECK_ROUNDS:
            # still off: those strips keep every row and every node
            for r in rows_add:
                s = int(np.searchsorted(R, r) - 1)
                K[R[s]:R[s + 1] + 1] = True
            for r, _col in nodes_add:
                s = min(int(np.searchsorted(R, r, side="right") - 1), len(R) - 2)
                K[R[s]:R[s + 1] + 1] = True
            return np.flatnonzero(K.any(axis=1)), K
        if rows_add:
            new = np.setdiff1d(np.array(rows_add, np.int64), R)
            if len(new):
                K[new] = _chains(q[new], c[new], tol, K[new])
                R = np.union1d(R, new)
        if len(nodes_add):
            K[nodes_add[:, 0], nodes_add[:, 1]] = True
    return R, K


def triangles(me: dict, forced: np.ndarray | None) -> tuple:
    """The triangles of a tile (node numbers, counter-clockwise seen from above) and the nodes they use: ``me``
    from ``own``, ``forced`` (n * n bool or None) the nodes on the border its neighbours keep. A forced node the
    tile does not keep itself lies on the side of one of its triangles along the border: that triangle becomes a
    fan from its corner across. So a forced node never makes the tile keep another one: tiles meet node for node,
    also where three or four meet."""
    tri, need = me["tri"], me["need"]
    if forced is None:
        return tri, need
    extra = forced & ~need
    if not extra.any():
        return tri, need
    n = int(round(math.sqrt(len(need))))
    return _fan_in(tri, np.flatnonzero(extra), n), need | forced


def _fan_in(tri: np.ndarray, nodes: np.ndarray, n: int) -> np.ndarray:
    """The triangles with the border nodes ``nodes`` put into the sides along the border they lie on."""
    r, c = tri // n, tri % n
    # per triangle side (corner k to corner k + 1, the turn's order): on which border it runs, if any
    a, b = np.arange(3), (np.arange(3) + 1) % 3
    ra, ca, rb, cb = r[:, a], c[:, a], r[:, b], c[:, b]
    side = np.full(ra.shape, -1)
    side[(ra == 0) & (rb == 0)] = 0
    side[(ca == n - 1) & (cb == n - 1)] = 1
    side[(ra == n - 1) & (rb == n - 1)] = 2
    side[(ca == 0) & (cb == 0)] = 3
    nr, nc = nodes // n, nodes % n
    on = [nodes[nr == 0], nodes[nc == n - 1], nodes[nr == n - 1], nodes[nc == 0]]
    pos = lambda q, s: (q % n) if s in (0, 2) else (q // n)          # noqa: E731  (place along the side)
    out, drop = [], np.zeros(len(tri), bool)
    for t_, k in zip(*np.nonzero(side >= 0)):
        s = int(side[t_, k])
        if not len(on[s]):
            continue
        p, q = int(tri[t_, k]), int(tri[t_, (k + 1) % 3])
        lo, hi = sorted((pos(p, s), pos(q, s)))
        mid = on[s][(pos(on[s], s) > lo) & (pos(on[s], s) < hi)]
        if not len(mid):
            continue
        if drop[t_]:                             # (a corner triangle with forced nodes on both its border sides)
            continue
        X = int(tri[t_, (k + 2) % 3])
        mid = mid[np.argsort(pos(mid, s))]
        if pos(p, s) > pos(q, s):
            mid = mid[::-1]
        chain = [p] + mid.tolist() + [q]
        rest = [(chain[j], chain[j + 1], X) for j in range(len(chain) - 1)]
        drop[t_] = True
        # a second border side of the same triangle: fan those of the new triangle that holds it
        k2 = [j for j in range(3) if j != k and side[t_, j] >= 0]
        if k2:
            sub = _fan_in(np.array(rest, np.int64), nodes, n)
            out.append(sub)
        else:
            out.append(np.array(rest, np.int64))
    if not out:
        return tri
    return np.concatenate([tri[~drop]] + out)


def split_edges(tri: np.ndarray, edges: np.ndarray, first: int) -> tuple:
    """Extra vertices on edges of a triangulation (task 0167: the foot of a wall above a rounded strip, the second
    rim of a rib): ``edges`` (k, 2) node numbers - vertex ``first + j`` lies on the straight edge ``edges[j]``
    (several on one edge: in order from ``edges[j, 0]``). Every triangle with such an edge is cut in two through
    the vertex. Returns (triangles, done): ``done[j]`` False where no triangle has that edge (the thinning went
    across it)."""
    tri = np.asarray(tri, np.int64)
    done = np.zeros(len(edges), bool)
    if not len(edges):
        return tri, done
    out = [list(t) for t in tri.tolist()]
    # the triangles round each edge, by its two ends (either way round)
    where: dict = {}
    for k, t in enumerate(out):
        for i in range(3):
            where.setdefault((min(t[i], t[(i + 1) % 3]), max(t[i], t[(i + 1) % 3])), []).append(k)
    for j, (u, v) in enumerate(edges.tolist()):
        key = (min(u, v), max(u, v))
        ks = where.pop(key, [])
        if not ks:
            continue
        done[j] = True
        e = first + j
        for k in ks:
            t = out[k]
            i = next(i for i in range(3) if {t[i], t[(i + 1) % 3]} == {u, v})
            a, b, c = t[i], t[(i + 1) % 3], t[(i + 2) % 3]
            out[k] = [a, e, c]
            out.append([e, b, c])
            n2 = len(out) - 1
            bc = (min(b, c), max(b, c))
            where[bc] = [n2 if x == k else x for x in where.get(bc, [])]
            for p, q, kk in ((a, e, k), (e, c, k), (e, c, n2), (e, b, n2)):
                where.setdefault((min(p, q), max(p, q)), []).append(kk)
    return np.array(out, np.int64).reshape(-1, 3), done
