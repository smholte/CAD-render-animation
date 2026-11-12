"""Clash check (task 0065), the parts without Blender: which parts move together, boxes, the motion between two
frames, and turning the moments two parts were found inside each other into the rows the panel lists.

How a check works (``blender/clash.py`` drives it):

1. Every frame of the built animation is set once (and every corner of a G-code program between frames); the
   place of every part and whether it is shown are read.
2. **Rigid bodies.** Parts whose motion is the same at every moment (``D(t) = M(t) · M(start)⁻¹``) keep their place
   against each other the whole animation: they are never compared (``rigid_groups``). A welded frame, a bolt in its
   hole, everything one joint carries: one body.
   **Turning in place** (task 0092): a part that turns about an axis that stays put (against the world or against
   the body carrying it) and is round about it (a roller, a sheave, a drum, a coil, a shaft) fills the same room at
   every angle: it is held at its place and rides with its carrier only (``spin_stretches``, ``round_about``), so it
   joins the carrier's body. Parts of one body as read are never compared, held or not.
3. **Broad phase.** For every pair of bodies that moves against each other: their boxes in the world at each moment,
   then the boxes of their parts (``box_pairs``). Between two big parts a lower bound of their distance is looked
   for first (``box_tree`` of each mesh, ``tree_separation``, task 0092): parts proven apart need no point tested,
   and are not tested again until they have moved that much against each other.
4. **Between frames.** Where two bodies come near each other and together move more than ``STEP`` between two
   frames, extra moments are put in between; each body's motion between the two frames is followed as a screw
   motion (``screw_between``: exact for a turn about a fixed axis and for a straight move), so a fast part cannot
   jump through another one in one frame step. Two parts further apart than both can travel in that frame step need
   none (task 0092).
5. **Narrow phase** (Blender's BVH trees): how far the two meshes are inside each other, the *depth*. Points of
   each mesh (its corners, and points spread over the triangles that cut through the other mesh) are tested
   against the other mesh: a point inside counts with its distance to the other's surface; the depth is the
   largest. For two blocks pushed into each other this is how far they overlap; for two beams crossing it is the
   overlap across them.
6. A pair counts as a **clash** when its depth is more than the clash depth deeper than at the animation's first
   frame (``excess``): parts that touch or press into each other in the CAD model (a pin in its bore, a press fit)
   only count when they go in deeper. Moments in a row make one row (``merge``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

MM = 1e-3
DEPTH = 0.5 * MM              # owner's default: an overlap deeper than this is a clash
NEAR = 5.0 * MM               # "Warn about near misses (closer than …)"
STEP = 4.0 * MM               # at most this much motion of a pair between two moments that are checked
MAX_SUB = 48                  # at most this many extra moments between two frames for one pair
RIGID_TOL = 2e-5              # parts whose motion differs less than this (m, and per matrix entry) move as one
MAX_ROWS = 200                # rows kept with the project


# ---------------------------------------------------------------------------
# matrices
# ---------------------------------------------------------------------------

def deltas(mats: np.ndarray) -> np.ndarray:
    """``mats`` (T, P, 4, 4): every part's world matrix at every moment. Returns (P, T, 12): each part's motion
    since the first moment, ``M(t) · M(0)⁻¹`` (its top three rows)."""
    m0inv = np.linalg.inv(mats[0])                               # (P, 4, 4)
    d = np.einsum("tpij,pjk->ptik", mats, m0inv)                 # (P, T, 4, 4)
    return d[:, :, :3, :].reshape(d.shape[0], d.shape[1], 12)


def rigid_groups(d: np.ndarray, tol: float = RIGID_TOL) -> np.ndarray:
    """Group parts that move as one. ``d`` (P, T, 12) from ``deltas``. Returns a group number per part; group 0
    holds the parts that never move (when there are any)."""
    p = d.shape[0]
    if p == 0:
        return np.zeros(0, dtype=np.int64)
    flat = d.reshape(p, -1)
    ident = np.tile(np.array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0], dtype=np.float64), d.shape[1])
    labels = np.full(p, -1, dtype=np.int64)
    still = np.max(np.abs(flat - ident), axis=1) <= tol
    labels[still] = 0
    nxt = 1 if np.any(still) else 0
    rest = np.flatnonzero(~still)
    if not len(rest):
        return labels
    # sort along a fixed random direction: parts that move alike end up next to each other
    w = np.random.default_rng(65).uniform(0.5, 1.0, flat.shape[1])
    key = flat[rest] @ w
    window = tol * float(np.sum(w)) * 1.01
    order = rest[np.argsort(key, kind="stable")]
    keys = flat[order] @ w
    reps: list[int] = []                                         # part index of each open group's first part
    rep_key: list[float] = []
    rep_label: list[int] = []
    lo = 0
    for i, k in zip(order, keys):
        while lo < len(reps) and rep_key[lo] < k - window:
            lo += 1                                              # groups too far down the sorted line
        found = -1
        if lo < len(reps):
            cand = np.array(reps[lo:])
            diff = np.max(np.abs(flat[cand] - flat[i]), axis=1)
            hit = np.flatnonzero(diff <= tol)
            if len(hit):
                found = rep_label[lo + int(hit[0])]
        if found < 0:
            found = nxt
            nxt += 1
            reps.append(int(i))
            rep_key.append(float(k))
            rep_label.append(found)
        labels[i] = found
    return labels


PIECES = 60_000               # a mesh's triangles are cut into about this many pieces at most for its box tree
PIECE_MIN = 0.02              # m: … and pieces need not be smaller than this (task 0092)
FRONTIER = 50_000             # pairs of boxes waiting at most (more: it stops with the bound it has)


def piece_boxes(verts: np.ndarray, tris: np.ndarray, pieces: int = PIECES) -> tuple:
    """Boxes (lo, hi) of the triangles cut into n² smaller ones each (n from its longest edge), so that no box is much
    bigger than ``size`` – a long or wide triangle's box is mostly empty room. ``size`` is chosen so that there are
    about ``pieces`` boxes at most."""
    tri = verts[tris]
    if not len(tri):
        return np.zeros((0, 3)), np.zeros((0, 3))
    edge = np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2), axis=1)
    ext = float(np.max(verts.max(axis=0) - verts.min(axis=0)))
    size = max(PIECE_MIN, ext / 400.0)
    for _k in range(30):
        n = np.clip(np.ceil(edge / size), 1, 64).astype(np.int64)
        if int(np.sum(n * n)) <= max(pieces, len(tri)):
            break
        size *= 1.5
    los, his = [tri.min(axis=1)[n == 1]], [tri.max(axis=1)[n == 1]]
    for k in np.unique(n[n > 1]):
        t = tri[n == k]
        # the k² small triangles of each: corners at barycentric steps of 1/k
        ij = [(i, j) for i in range(k) for j in range(k - i)]
        up = np.array([[(i, j), (i + 1, j), (i, j + 1)] for i, j in ij], dtype=np.float64) / k
        down = np.array([[(i + 1, j), (i + 1, j + 1), (i, j + 1)] for i, j in ij if i + j + 1 < k],
                        dtype=np.float64).reshape(-1, 3, 2) / k
        w = np.concatenate([up, down])                                   # (k², 3 corners, 2)
        w0 = 1.0 - w[..., 0] - w[..., 1]
        sub = (w0[None, ..., None] * t[:, None, None, 0] + w[None, ..., 0, None] * t[:, None, None, 1]
               + w[None, ..., 1, None] * t[:, None, None, 2])           # (T, k², 3, 3)
        los.append(sub.min(axis=2).reshape(-1, 3))
        his.append(sub.max(axis=2).reshape(-1, 3))
    return np.concatenate(los), np.concatenate(his)


def box_tree(lo: np.ndarray, hi: np.ndarray) -> tuple:
    """A tree of boxes over boxes ``lo``/``hi`` (N, 3): every node halves its boxes at the middle of the longest side
    of their middles (all nodes of a level at once: a sort per block). Heap order: node 0 is the root, node i has
    children 2i+1 and 2i+2; the leaves (one box each) have none. Returns (node lo, node hi, children (M, 2), -1 for a
    leaf)."""
    n = len(lo)
    m = 1 << max(0, int(math.ceil(math.log2(max(n, 1)))))
    pad = np.concatenate([np.arange(n), np.repeat(n - 1, m - n)]) if n else np.zeros(1, dtype=np.int64)
    mid = ((lo + hi) / 2.0)[pad]
    perm = np.arange(m)
    blocks = 1
    while blocks < m:
        size = m // blocks
        c = mid[perm].reshape(blocks, size, 3)
        ax = np.argmax(c.max(axis=1) - c.min(axis=1), axis=1)                # (blocks,)
        key = np.take_along_axis(c, ax[:, None, None].repeat(size, axis=1), axis=2)[..., 0]
        perm = np.take_along_axis(perm.reshape(blocks, size), np.argsort(key, axis=1, kind="stable"), axis=1)
        perm = perm.reshape(-1)
        blocks *= 2
    leaf = pad[perm]
    nlo = np.empty((2 * m - 1, 3))
    nhi = np.empty((2 * m - 1, 3))
    nlo[m - 1:], nhi[m - 1:] = lo[leaf], hi[leaf]
    start = m - 1
    while start > 0:                                            # one level up: pairs of the level below
        width = start + 1
        up = (start - 1) // 2
        nlo[up:start] = nlo[start:start + width].reshape(-1, 2, 3).min(axis=1)
        nhi[up:start] = nhi[start:start + width].reshape(-1, 2, 3).max(axis=1)
        start = up
    kids = np.full((2 * m - 1, 2), -1, dtype=np.int64)
    inner = np.arange(m - 1)
    kids[:m - 1, 0], kids[:m - 1, 1] = 2 * inner + 1, 2 * inner + 2
    return nlo, nhi, kids


def _moved_boxes(m: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> tuple:
    """Boxes ``lo``/``hi`` (K, 3) moved by ``m`` (4x4): the boxes round them (K, 3)."""
    c = transform(m, corners(lo, hi))
    return c.min(axis=1), c.max(axis=1)


def _gaps2(alo, ahi, blo, bhi, rel: np.ndarray, inv: np.ndarray) -> np.ndarray:
    """Squared gaps between boxes a[k] (a's space) and b[k] (b's space; ``rel`` takes b's space to a's), seen along a's
    axes or along b's, whichever is wider (a long box turned grows; seen the other way round it does not). (K,)."""
    bl, bh = _moved_boxes(rel, blo, bhi)
    al, ah = _moved_boxes(inv, alo, ahi)
    g1 = np.maximum(0.0, np.maximum(alo - bh, bl - ahi))
    g2 = np.maximum(0.0, np.maximum(blo - ah, al - bhi))
    return np.maximum(np.einsum("ij,ij->i", g1, g1), np.einsum("ij,ij->i", g2, g2))


def tree_separation(ta: tuple, tb: tuple, rel: np.ndarray, need: float = math.inf, batch: int = 2048,
                    extra: int = 16) -> float:
    """A lower bound of the distance between two meshes from their box trees (``box_tree``; ``rel`` takes b's space to
    a's): the smallest gap between a leaf box of one and a leaf box of the other. Best first: the nearest pairs of
    nodes are opened first (a batch at a time, all at once), a pair no nearer than the best leaf gap found so far is
    dropped, and so is one at least ``need`` apart (a bound that big is enough). 0 when two leaf boxes meet. After
    the two trees' depths plus ``extra`` batches it stops with what it has (the nearest pair not opened yet bounds the
    rest): parts that nearly touch have very many pairs of boxes close together, and for them the bound is about 0
    anyway."""
    inv = np.linalg.inv(rel)
    alo, ahi, akid = ta
    blo, bhi, bkid = tb

    def gaps(ia, ib):
        return _gaps2(alo[ia], ahi[ia], blo[ib], bhi[ib], rel, inv)

    fa, fb = np.zeros(1, dtype=np.int64), np.zeros(1, dtype=np.int64)
    fg = gaps(fa, fb)
    best = math.inf
    cut = need * need
    if akid[0, 0] < 0 and bkid[0, 0] < 0:
        return math.sqrt(float(fg[0]))
    steps = int(math.log2(len(alo) + 1)) + int(math.log2(len(blo) + 1)) + extra
    for _step in range(steps + 1):
        if not len(fa):
            break
        lim = min(best, cut)
        over = fg >= lim
        if np.any(over & (fg >= cut)):
            best = min(best, float(fg[over & (fg >= cut)].min()))     # apart at least that much: enough
        fa, fb, fg = fa[~over], fb[~over], fg[~over]
        if not len(fa):
            break
        if len(fa) > FRONTIER or _step == steps:
            return math.sqrt(min(best, float(fg.min())))               # every pair left is at least this far apart
        size = min(batch, 16 << _step)                 # small batches first: a touching pair needs one short path
        if len(fa) > size:
            sel = np.zeros(len(fa), dtype=bool)
            zero = np.flatnonzero(fg <= 0.0)
            if len(zero) > size:                       # boxes that meet: the deepest first (heap order), to a leaf soon
                sel[zero[np.argpartition(-(fa[zero] + fb[zero]), size)[:size]]] = True
            else:
                sel[np.argpartition(fg, size)[:size]] = True
        else:
            sel = np.ones(len(fa), dtype=bool)
        ia, ib = fa[sel], fb[sel]
        fa, fb, fg = fa[~sel], fb[~sel], fg[~sel]
        # open the bigger node of each pair (a leaf cannot be opened)
        la, lb = akid[ia, 0] < 0, bkid[ib, 0] < 0
        sa = np.max(ahi[ia] - alo[ia], axis=1)
        sb = np.max(bhi[ib] - blo[ib], axis=1)
        open_a = ~la & (lb | (sa >= sb))
        na = np.concatenate([akid[ia[open_a], 0], akid[ia[open_a], 1], ia[~open_a], ia[~open_a]])
        nb = np.concatenate([ib[open_a], ib[open_a], bkid[ib[~open_a], 0], bkid[ib[~open_a], 1]])
        g = gaps(na, nb)
        leaf = (akid[na, 0] < 0) & (bkid[nb, 0] < 0)
        if np.any(leaf):
            best = min(best, float(g[leaf].min()))
            if best <= 0.0:
                return 0.0
        fa = np.concatenate([fa, na[~leaf]])
        fb = np.concatenate([fb, nb[~leaf]])
        fg = np.concatenate([fg, g[~leaf]])
    return math.sqrt(best) if math.isfinite(best) else math.inf


def corners(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """(N, 8, 3) corners of boxes ``lo``/``hi`` (N, 3)."""
    sel = np.array([[(k >> a) & 1 for a in range(3)] for k in range(8)], dtype=bool)   # (8, 3)
    return np.where(sel[None], hi[:, None, :], lo[:, None, :])


def transform(m: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """``m`` (..., 4, 4) applied to ``pts`` (..., K, 3)."""
    return np.matmul(pts, np.swapaxes(m[..., :3, :3], -1, -2)) + m[..., None, :3, 3]


def world_boxes(mats: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> tuple:
    """Boxes in the world (min, max, each (N, 3)) of N local boxes moved by ``mats`` (N, 4, 4)."""
    c = transform(mats, corners(lo, hi))
    return c.min(axis=1), c.max(axis=1)


def box_pairs(lo_a, hi_a, lo_b, hi_b, margin: float = 0.0, chunk: int = 2_000_000) -> np.ndarray:
    """Index pairs (i, j) whose boxes ``a[i]`` and ``b[j]`` overlap (or come closer than ``margin``). (K, 2)."""
    na, nb = len(lo_a), len(lo_b)
    if not na or not nb:
        return np.zeros((0, 2), dtype=np.int64)
    out = []
    step = max(1, chunk // max(1, nb))
    for s in range(0, na, step):
        e = min(na, s + step)
        ok = np.all((lo_a[s:e, None, :] <= hi_b[None, :, :] + margin)
                    & (lo_b[None, :, :] <= hi_a[s:e, None, :] + margin), axis=2)
        i, j = np.nonzero(ok)
        out.append(np.stack([i + s, j], axis=1))
    return np.concatenate(out) if out else np.zeros((0, 2), dtype=np.int64)


def boxes_overlap(lo_a, hi_a, lo_b, hi_b, margin: float = 0.0) -> bool:
    return bool(np.all(lo_a <= hi_b + margin) and np.all(lo_b <= hi_a + margin))


def motion(m0: np.ndarray, m1: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """How far (m) the corners of the box ``lo``/``hi`` move from ``m0`` to ``m1`` (4x4 each), at most."""
    c = corners(lo[None], hi[None])[0]
    return float(np.max(np.linalg.norm(transform(m1, c) - transform(m0, c), axis=1)))


def motion_many(m0: np.ndarray, m1: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """``motion`` for many at once: m0, m1 (K, 4, 4), boxes lo, hi (K, 3). (K,)."""
    if not len(m0):
        return np.zeros(0)
    c = corners(lo, hi)                                              # (K, 8, 3)
    return np.max(np.linalg.norm(transform(m1, c) - transform(m0, c), axis=2), axis=1)


def screw_between(m0: np.ndarray, m1: np.ndarray, s: float) -> np.ndarray:
    """The place a part has a share ``s`` (0 … 1) of the way from ``m0`` to ``m1`` (4x4 world matrices), moving as a
    screw: a turn about a fixed axis plus a slide along it (exact for a joint that turns or slides evenly)."""
    rel = m1 @ np.linalg.inv(m0)
    r, t = rel[:3, :3], rel[:3, 3]
    cos = (np.trace(r) - 1.0) / 2.0
    ang = math.acos(min(1.0, max(-1.0, cos)))
    out = np.eye(4)
    if ang < 1e-9:
        out[:3, 3] = t * s
        return out @ m0
    if math.pi - ang < 1e-6:                     # half a turn: the axis from the symmetric part
        w, v = np.linalg.eigh((r + r.T) / 2.0)
        axis = v[:, int(np.argmax(w))]
    else:
        axis = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / (2.0 * math.sin(ang))
    axis = axis / np.linalg.norm(axis)
    along = float(t @ axis)
    perp = t - along * axis
    # a point c on the axis: (I - R) c = perp (least squares: I - R has no rank along the axis)
    c = np.linalg.lstsq(np.eye(3) - r, perp, rcond=None)[0]
    c = c - (c @ axis) * axis
    a = ang * s
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    rs = np.eye(3) + math.sin(a) * k + (1.0 - math.cos(a)) * (k @ k)
    out[:3, :3] = rs
    out[:3, 3] = c - rs @ c + along * s * axis
    return out @ m0


# ---------------------------------------------------------------------------
# parts that turn in place (task 0092)
# ---------------------------------------------------------------------------
#
# A roller, a sheave, a drum or a coil turning about its own round axis fills the same room at every angle: checked
# moment by moment its box corners move all the time, so every pair near it was worked out again at every moment (and
# at extra moments between frames). ``spin_stretches`` finds the stretches of moments in which a body's motion against
# a carrier (the world, or the body it rides on) is a turn about one axis that stays put; ``round_about`` says whether a
# part's mesh is round about that axis (every point of its surface, turned, lands on its surface again). Such a part is
# held at its place at the start of the stretch, riding along with its carrier only (``blender/clash.py``): it then
# moves as one body with the carrier and is compared with the rest only when the carrier moves.

SPIN_TOL = 0.05 * MM          # a motion is a turn about an axis when no corner of the body's box is further off it
SPIN_MIN = 0.02               # rad: smaller turns are not used to find the axis (float32 places make it shaky)
MAX_STRETCHES = 64            # stretches looked for per body and carrier at most (the rest keeps its real motion)
ROUND_TOL = 0.05 * MM         # a turned point of a round part lies this close to its surface (plus the facets' sag)
ROUND_TURNS = (0.37, 1.23, 2.71, 4.05)    # rad: the turns tried (no multiples of a tooth's pitch for common counts)
ROUND_POINTS = 2500           # points of the surface tried at most (each turn)
RING_Q = 0.02 * MM            # vertices this close in (along, radius) lie on one ring
RING_MIN = 8                  # a ring needs this many vertices to tell the facet angle
RING_GAP = math.radians(30)   # a ring whose usual gap between vertices is wider is not a faceted circle


def rotation_about(c: np.ndarray, u: np.ndarray, phi) -> np.ndarray:
    """4x4 matrices (…, 4, 4): turns by ``phi`` (rad, any shape) about the line through ``c`` along unit ``u``."""
    phi = np.asarray(phi, dtype=np.float64)
    k = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]], dtype=np.float64)
    s, co = np.sin(phi)[..., None, None], np.cos(phi)[..., None, None]
    r = np.eye(3) + s * k + (1.0 - co) * (k @ k)
    out = np.zeros(phi.shape + (4, 4))
    out[..., :3, :3] = r
    out[..., :3, 3] = c - np.einsum("...ij,j->...i", r, c)
    out[..., 3, 3] = 1.0
    return out


def turn_angles(m: np.ndarray) -> np.ndarray:
    """How far (rad, 0 … π) the rigid motions ``m`` (…, 4, 4) turn."""
    tr = np.trace(m[..., :3, :3], axis1=-2, axis2=-1)
    return np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))


def screw_axis(m: np.ndarray) -> tuple:
    """(point c on the axis nearest the origin, unit direction u, angle, slide along u) of a rigid motion ``m`` (4x4)
    that turns (angle > 0)."""
    r, t = m[:3, :3], m[:3, 3]
    ang = float(turn_angles(m))
    if math.pi - ang < 1e-6:
        w, v = np.linalg.eigh((r + r.T) / 2.0)
        u = v[:, int(np.argmax(w))]
    else:
        u = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / (2.0 * math.sin(max(ang, 1e-12)))
    u = u / np.linalg.norm(u)
    along = float(t @ u)
    c = np.linalg.lstsq(np.eye(3) - r, t - along * u, rcond=None)[0]
    c = c - (c @ u) * u
    return c, u, ang, along


def signed_angles(m: np.ndarray, u: np.ndarray) -> np.ndarray:
    """The turn (rad, −π … π) of motions ``m`` (N, 4, 4) about direction ``u`` (their own axis taken along ``u``)."""
    r = m[:, :3, :3]
    s = np.stack([r[:, 2, 1] - r[:, 1, 2], r[:, 0, 2] - r[:, 2, 0], r[:, 1, 0] - r[:, 0, 1]], axis=1) / 2.0
    return np.arctan2(s @ u, (np.trace(r, axis1=1, axis2=2) - 1.0) / 2.0)


def off_axis(rel: np.ndarray, c: np.ndarray, u: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """How far (m) motions ``rel`` (N, 4, 4) take the points ``pts`` (K, 3) from where a pure turn about the line
    (c, u) by the same angle takes them. (N,)."""
    if not len(rel):
        return np.zeros(0)
    pure = rotation_about(c, u, signed_angles(rel, u))
    return np.max(np.linalg.norm(transform(rel, pts[None]) - transform(pure, pts[None]), axis=2), axis=1)


def spin_stretches(e: np.ndarray, lo: np.ndarray, hi: np.ndarray, tol: float = SPIN_TOL) -> list:
    """Stretches of moments in which motion ``e`` (T, 4, 4) is a turn about one fixed axis: [(s, end, c, u)], moments
    s … end-1, ``e[t] = turn about (c, u) · e[s]`` there, within ``tol`` at every corner of the box ``lo``/``hi`` (the
    body where ``e`` is the identity). Only stretches that really turn (by more than ``SPIN_MIN``) are listed; a still
    or sliding stretch keeps its real motion anyway. A turn that also slides along its axis is no turn in place. A
    stretch holds at least three moments (between any two places of a body moving in a plane there is a turn)."""
    T = len(e)
    pts = corners(np.asarray(lo, dtype=np.float64)[None], np.asarray(hi, dtype=np.float64)[None])[0]
    out = []
    s = 0
    for _attempt in range(MAX_STRETCHES):
        if s >= T - 1:
            break
        rel = e[s + 1:] @ np.linalg.inv(e[s])
        ang = turn_angles(rel)
        big = np.flatnonzero(ang > SPIN_MIN)
        if not len(big):
            break                                                    # nothing turns from here on
        n, k = 0, int(big[0])
        axis = None
        for loose in (True, False):
            c, u, _a, along = screw_axis(rel[k])
            if abs(along) > tol:                                     # slides along its axis: a screw, not in place
                axis = None
                break
            bad = off_axis(rel, c, u, pts) > (4.0 * tol if loose else tol)
            n = int(np.argmax(bad)) if bad.any() else len(rel)       # rel[0 … n-1] turn about it
            axis = (c, u)
            inside = big[big < n]
            if not len(inside):
                break
            k = int(inside[np.argmax(np.sin(np.minimum(ang[inside], math.pi / 2)))])   # the best-conditioned turn
        if axis is not None and n >= 2 and np.any(big < n):         # 2 moments: any flat motion is a turn
            out.append((s, s + 1 + n, axis[0], axis[1]))
            s = s + 1 + n
        else:
            s = s + max(1, n)
    return out


def _ring_sag(rel: np.ndarray, u: np.ndarray) -> float:
    """The facets' sag of a mesh round about an axis, from its vertices on rings (same place along the axis, same
    radius): a ring's usual gap between neighbours (its 75th percentile, so one wide gap – a flat cut through the ring –
    does not count) at its radius. -1 when no ring tells it (too few vertices on any ring: not a faceted round part)."""
    a = rel @ u
    rad = rel - a[:, None] * u
    r = np.linalg.norm(rad, axis=1)
    ok = r > 10 * RING_Q
    if not np.any(ok):
        return -1.0
    a, rad, r = a[ok], rad[ok], r[ok]
    e1 = np.cross(u, [1.0, 0.0, 0.0])
    if np.linalg.norm(e1) < 0.5:
        e1 = np.cross(u, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    th = np.arctan2(rad @ e2, rad @ e1)
    ka, kr = np.round(a / RING_Q).astype(np.int64), np.round(r / RING_Q).astype(np.int64)
    order = np.lexsort((th, kr, ka))
    ka, kr, th, r = ka[order], kr[order], th[order], r[order]
    new = np.ones(len(ka), dtype=bool)
    new[1:] = (ka[1:] != ka[:-1]) | (kr[1:] != kr[:-1])
    starts = np.flatnonzero(new)
    ends = np.append(starts[1:], len(ka))
    sag = -1.0
    for s0, e0 in zip(starts, ends):
        if e0 - s0 < RING_MIN:
            continue
        t = np.unique(th[s0:e0])
        if len(t) < RING_MIN:
            continue
        gaps = np.diff(np.append(t, t[0] + 2 * math.pi))
        g = float(np.percentile(gaps, 75))
        if g > RING_GAP:
            continue
        sag = max(sag, float(np.mean(r[s0:e0])) * (1.0 - math.cos(g / 2.0)))
    return sag


def _nearest_brute(verts: np.ndarray, tris: np.ndarray):
    tri = verts[tris]

    def nearest(pts):
        return np.array([float(np.min(np.linalg.norm(closest_on_triangles(p, tri) - p, axis=1))) for p in pts])
    return nearest


def round_about(verts: np.ndarray, tris: np.ndarray, c, u, nearest=None, tol: float = ROUND_TOL,
                most: int = ROUND_POINTS) -> bool:
    """Whether a mesh (its own space) is round about the line through ``c`` along ``u``: turned about it, it fills the
    same room. Points of its surface (its corners and points spread over its faces) turned by a few angles must land on
    its surface again, within ``tol`` plus the sag of its facets (a faceted cylinder turned by half a facet lies that
    far off itself; the sag is read from its rings of vertices, ``_ring_sag``). A flat cut, a key, teeth, a groove or
    a cam lobe lands points off the surface by their depth. ``nearest(points) -> distances`` to the surface (Blender's
    BVH tree in the check; a plain search here)."""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    if not len(tris):
        return False
    c = np.asarray(c, dtype=np.float64)
    u = np.asarray(u, dtype=np.float64)
    u = u / np.linalg.norm(u)
    sag = _ring_sag(verts - c, u)
    if sag < 0:
        return False
    size = float(np.max(verts.max(axis=0) - verts.min(axis=0)))
    pts, _w = triangle_points(verts[tris], max(size / 40.0, 0.5 * MM))
    pts = np.concatenate([thin_out(verts, most // 2), thin_out(pts[len(tris) * 3:], most // 2)])
    allowed = tol + sag
    nearest = nearest or _nearest_brute(verts, tris)
    head = thin_out(pts, 200)
    for batch in (head, pts):                                        # a part that is not round fails at once
        for phi in ROUND_TURNS:
            turned = transform(rotation_about(c, u, phi), batch[None])[0]
            if float(np.max(nearest(turned))) > allowed:
                return False
    return True


BAND_BINS = 64                # the (along, radius) grid of the room a part's features that are not round sweep
BAND_POINTS = 20_000          # points of its surface tried at most


def axial(c, u):
    """A unit direction and two unit directions square to it (u, e1, e2)."""
    u = np.asarray(u, dtype=np.float64)
    u = u / np.linalg.norm(u)
    e1 = np.cross(u, [1.0, 0.0, 0.0])
    if np.linalg.norm(e1) < 0.5:
        e1 = np.cross(u, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    return u, e1, np.cross(u, e1)


def unround_band(verts: np.ndarray, tris: np.ndarray, c, u, nearest=None, tol: float = ROUND_TOL):
    """Where a part that turns about the line (c, u) but is not round there (a sheave with spokes, a drum with a flange
    bolted on, a sprocket) is not round: the room its features sweep as it turns, as a grid over (along the axis,
    distance from it) in its own space. Points of its surface (every corner and points spread over its faces) that do
    not land on its surface again when turned (``round_about``) mark their cell; the cells round them too (the points
    lie up to a cell apart). Outside the marked cells every circle about the axis lies wholly inside, wholly outside or
    on the part at every angle: another part that stays out of them meets the part the same way at every angle (a
    rope lying in a spoked sheave's groove). Returns (grid (A, R) bool, a0, da, dr) or None (it cannot tell)."""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    c = np.asarray(c, dtype=np.float64)
    u, _e1, _e2 = axial(c, u)
    sag = _ring_sag(verts - c, u) if len(tris) else -1.0
    if sag < 0:
        return None
    size = float(np.max(verts.max(axis=0) - verts.min(axis=0)))
    spacing = max(size / 60.0, 0.5 * MM)
    tp, _w = triangle_points(verts[tris], spacing)
    pts = np.concatenate([verts, thin_out(tp[len(tris) * 3:], BAND_POINTS)])
    nearest = nearest or _nearest_brute(verts, tris)
    bad = np.zeros(len(pts), dtype=bool)
    for phi in ROUND_TURNS:
        turned = transform(rotation_about(c, u, phi), pts[None])[0]
        bad |= nearest(turned) > tol + sag
    rel = verts - c
    a_all = rel @ u
    r_all = np.linalg.norm(rel - a_all[:, None] * u, axis=1)
    reach = spacing + sag                       # points lie up to ``spacing`` apart, the facets' sag on top
    a0, a1 = float(a_all.min()) - 2 * reach, float(a_all.max()) + 2 * reach
    da = max((a1 - a0) / BAND_BINS, 1e-9)
    dr = max((float(r_all.max()) + 2 * reach) / BAND_BINS, 1e-9)
    grid = np.zeros((BAND_BINS, BAND_BINS), dtype=bool)                # covers the part and ``reach`` round it
    if np.any(bad):
        q = pts[bad] - c
        a = q @ u
        r = np.linalg.norm(q - a[:, None] * u, axis=1)
        ia = np.clip(np.floor((a - a0) / da).astype(np.int64), 0, BAND_BINS - 1)
        ir = np.clip(np.floor(r / dr).astype(np.int64), 0, BAND_BINS - 1)
        grid[ia, ir] = True
        reach_a = int(math.ceil(reach / da))
        reach_r = int(math.ceil(reach / dr))
        grown = np.zeros_like(grid)
        for i, j in zip(*np.nonzero(grid)):
            grown[max(0, i - reach_a):i + reach_a + 1, max(0, j - reach_r):j + reach_r + 1] = True
        grid = grown
    return grid, a0, da, dr


_EDGES = np.array([(i, i ^ (1 << k)) for i in range(8) for k in range(3) if not i & (1 << k)])   # the 12 edges


def line_box_distance(c, u, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """The distance from the line through ``c`` along unit ``u`` to each box ``lo``/``hi`` (K, 3): 0 where the line
    goes through the box, else the nearest of its 12 edges (a line that misses a box is nearest to it at an edge)."""
    c = np.asarray(c, dtype=np.float64)
    u = np.asarray(u, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (lo - c) / u, (hi - c) / u
    flat = np.abs(u) < 1e-12                                             # the line runs along a side's plane
    inside = np.all(~flat | ((c >= lo) & (c <= hi)), axis=1)
    tmin = np.max(np.where(flat, -np.inf, np.minimum(t1, t2)), axis=1)
    tmax = np.min(np.where(flat, np.inf, np.maximum(t1, t2)), axis=1)
    through = inside & (tmin <= tmax)
    cor = corners(lo, hi) - c                                            # (K, 8, 3)
    p0, p1 = cor[:, _EDGES[:, 0]], cor[:, _EDGES[:, 1]]                 # (K, 12, 3)
    q0 = p0 - (p0 @ u)[..., None] * u                                    # seen along the line
    d = (p1 - p0) - ((p1 - p0) @ u)[..., None] * u
    dd = np.einsum("kij,kij->ki", d, d)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.clip(np.where(dd > 0, -np.einsum("kij,kij->ki", q0, d) / dd, 0.0), 0.0, 1.0)
    dist = np.linalg.norm(q0 + s[..., None] * d, axis=2).min(axis=1)
    return np.where(through, 0.0, dist)


def tree_clear_of_band(band, c, u, tree: tuple, m: np.ndarray, margin: float = 0.0, most: int = 200_000) -> bool:
    """``clear_of_band`` for a whole mesh given by its box tree (``box_tree``, moved by ``m`` into the turning part's
    space): a node that is not clear is opened, down to the leaves (one piece each); any leaf not clear: not clear."""
    nlo, nhi, kids = tree
    idx = np.zeros(1, dtype=np.int64)
    while len(idx):
        lo, hi = world_boxes(np.broadcast_to(m, (len(idx), 4, 4)), nlo[idx], nhi[idx])
        bad = idx[~clear_of_band(band, c, u, lo, hi, margin, each=True)]
        if not len(bad):
            return True
        if np.any(kids[bad, 0] < 0) or len(bad) * 2 > most:
            return False
        idx = kids[bad].reshape(-1)
    return True


def clear_of_band(band, c, u, lo: np.ndarray, hi: np.ndarray, margin: float = 0.0, each: bool = False):
    """Whether boxes ``lo``/``hi`` (K, 3; the part's own space) all stay out of the marked cells of ``band``
    (``unround_band`` about the line (c, u)), at least ``margin`` away (``each``: per box). A box's place along the
    axis and its distance from it are taken generously (every point of the box lies within them)."""
    if band is None:
        return np.zeros(len(lo), dtype=bool) if each else False
    grid, a0, da, dr = band
    if not grid.any() or not len(lo):
        return np.ones(len(lo), dtype=bool) if each else True
    c = np.asarray(c, dtype=np.float64)
    u, _e1, _e2 = axial(c, u)
    cor = corners(lo, hi) - c                                            # (K, 8, 3)
    a = cor @ u
    a_lo, a_hi = a.min(axis=1) - margin, a.max(axis=1) + margin
    rows = np.flatnonzero(grid.any(axis=1))
    out = (a_hi < a0 + rows[0] * da) | (a_lo > a0 + (rows[-1] + 1) * da)   # beside the band along the axis: clear
    if np.all(out):
        return np.ones(len(lo), dtype=bool) if each else True
    k = np.flatnonzero(~out)
    rad = cor[k] - a[k][..., None] * u
    r_hi = np.linalg.norm(rad, axis=2).max(axis=1) + margin
    r_lo = line_box_distance(c, u, lo[k], hi[k]) - margin
    a_lo, a_hi = a_lo[k], a_hi[k]
    n_a, n_r = grid.shape
    i0 = np.clip(np.floor((a_lo - a0) / da).astype(np.int64), 0, n_a)
    i1 = np.clip(np.floor((a_hi - a0) / da).astype(np.int64) + 1, 0, n_a)
    j0 = np.clip(np.floor(r_lo / dr).astype(np.int64), 0, n_r)
    j1 = np.clip(np.floor(r_hi / dr).astype(np.int64) + 1, 0, n_r)
    sat = np.zeros((n_a + 1, n_r + 1), dtype=np.int64)                  # summed-area table of the marked cells
    sat[1:, 1:] = np.cumsum(np.cumsum(grid, axis=0), axis=1)
    hits = sat[i1, j1] - sat[i0, j1] - sat[i1, j0] + sat[i0, j0]
    if not each:
        return bool(np.all(hits == 0))
    ok = np.ones(len(lo), dtype=bool)
    ok[k] = hits == 0
    return ok


# ---------------------------------------------------------------------------
# points to test
# ---------------------------------------------------------------------------

def triangle_points(tri: np.ndarray, spacing: float, max_split: int = 8) -> tuple:
    """Points spread over triangles ``tri`` (N, 3, 3): every triangle split into n² smaller ones (n from its longest
    edge and ``spacing``), their corners. Returns (points (K, 3), the triangle of each point (K,))."""
    if not len(tri):
        return np.zeros((0, 3)), np.zeros(0, dtype=np.int64)
    edge = np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2), axis=1)
    n = np.clip(np.ceil(edge / max(spacing, 1e-9)), 1, max_split).astype(int)
    out = [tri.reshape(-1, 3)]
    which = [np.repeat(np.arange(len(tri)), 3)]
    for k in np.unique(n):
        if k <= 1:
            continue
        sel = np.flatnonzero(n == k)
        uv = np.array([(i / k, j / k) for i in range(k + 1) for j in range(k + 1 - i)
                       if 0 < i + j and (i, j) not in ((k, 0), (0, k))])
        if not len(uv):
            continue
        t = tri[sel]
        w0 = 1.0 - uv[:, 0] - uv[:, 1]
        pts = (w0[None, :, None] * t[:, None, 0] + uv[None, :, 0, None] * t[:, None, 1]
               + uv[None, :, 1, None] * t[:, None, 2])
        out.append(pts.reshape(-1, 3))
        which.append(np.repeat(sel, len(uv)))
    return np.concatenate(out), np.concatenate(which)


def clamp_to_triangle(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """The point of triangle ``tri`` (3, 3) nearest to ``p`` (on its plane, kept inside its edges)."""
    a, b, c = tri
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0:
        return a
    bp = p - b
    d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 <= d1 and d3 <= 0:
        return a + ab * (d1 / (d1 - d3))
    cp = p - c
    d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 <= d2 and d6 <= 0:
        return a + ac * (d2 / (d2 - d6))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)))
    den = 1.0 / (va + vb + vc)
    return a + ab * (vb * den) + ac * (vc * den)


def thin_out(pts: np.ndarray, most: int) -> np.ndarray:
    """At most ``most`` of the points, evenly picked (the same ones every time)."""
    if len(pts) <= most:
        return pts
    return pts[np.linspace(0, len(pts) - 1, most).astype(int)]


def zone(tip, axis, radius: float, a_lo: float, a_hi: float) -> tuple:
    """A round zone along a tool's axis: points closer than ``radius`` to the axis, from ``a_lo`` to ``a_hi`` along
    it from the tip (``math.inf`` for no limit), in the tool's own space."""
    a = np.asarray(axis, dtype=np.float64)
    n = float(np.linalg.norm(a))
    a = a / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])
    return (np.asarray(tip, dtype=np.float64), a, float(radius), float(a_lo), float(a_hi))


ZONE_MARGIN = 0.2 * MM


def in_zone(pts: np.ndarray, zones) -> np.ndarray:
    """Which points lie in any of ``zones`` (see ``zone``; a little margin round each)."""
    out = np.zeros(len(pts), dtype=bool)
    if not zones or not len(pts):
        return out
    m = ZONE_MARGIN
    for tip, axis, radius, a_lo, a_hi in zones:
        rel = pts - tip
        a = rel @ axis
        ok = (a >= a_lo - m) & (a <= a_hi + m)
        if math.isfinite(radius):
            r = np.linalg.norm(rel - a[:, None] * axis[None], axis=1)
            ok &= r <= radius + m
        out |= ok
    return out


def bound(rel_old: np.ndarray, rel_new: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """How far any point of a box ``lo``/``hi`` (b's own space) moves in a's space from ``rel_old`` to ``rel_new``:
    the most two parts' overlap (or gap) can have changed since it was last worked out (a rigid move is affine, so
    its largest displacement over a box is at a corner)."""
    return motion(rel_old, rel_new, lo, hi)


def closest_on_triangles(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """The point of each triangle ``tri`` (K, 3, 3) nearest to ``p`` (3,), in 64-bit numbers. (K, 3)."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.einsum("ij,ij->i", ab, ap), np.einsum("ij,ij->i", ac, ap)
    bp, cp = p - b, p - c
    d3, d4 = np.einsum("ij,ij->i", ab, bp), np.einsum("ij,ij->i", ac, bp)
    d5, d6 = np.einsum("ij,ij->i", ab, cp), np.einsum("ij,ij->i", ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    with np.errstate(divide="ignore", invalid="ignore"):
        den = va + vb + vc
        v = np.where(den != 0, vb / den, 0.0)
        w = np.where(den != 0, vc / den, 0.0)
        out = a + ab * v[:, None] + ac * w[:, None]                       # inside the face
        t_ab = np.where(d1 - d3 != 0, d1 / (d1 - d3), 0.0)
        t_ac = np.where(d2 - d6 != 0, d2 / (d2 - d6), 0.0)
        t_bc = np.where((d4 - d3) + (d5 - d6) != 0, (d4 - d3) / ((d4 - d3) + (d5 - d6)), 0.0)
    e_bc = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)
    out = np.where(e_bc[:, None], b + (c - b) * t_bc[:, None], out)
    e_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    out = np.where(e_ac[:, None], a + ac * t_ac[:, None], out)
    e_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    out = np.where(e_ab[:, None], a + ab * t_ab[:, None], out)
    out = np.where(((d6 >= 0) & (d5 <= d6))[:, None], c, out)
    out = np.where(((d3 >= 0) & (d4 <= d3))[:, None], b, out)
    out = np.where(((d1 <= 0) & (d2 <= 0))[:, None], a, out)
    return out


THIN = 4.0              # a face is cut until its pieces are no longer than THIN x its own width (task 0077)
MESH_BUDGET = 600_000   # about this many pieces per mesh at most: a bigger one is cut coarser (task 0077)


def split_long(verts: np.ndarray, tris: np.ndarray, longest: float = 25 * MM, rounds: int = 16) -> tuple:
    """The mesh with every long thin triangle cut into a strip of short ones, the pieces no longer than ``longest``
    or ``THIN`` x the face's own width, whichever is more (the vertices are not shared: fine for a search tree; the
    surface and each face's side stay exactly the same). Blender's 32-bit nearest-point search is millimetres off on
    the long thin faces CAD meshes have (a face 1 m long and 2.5 mm wide: cut to 25 mm); a wide face has no trouble.
    A mesh that would still become more than about ``MESH_BUDGET`` pieces is cut coarser: a vessel's 120 m deck and
    hull have faces 60 m long and millimetres wide, and cut to 25 mm by halving (as before task 0077) they became
    billions of pieces and the check ran out of memory. ``rounds`` is kept for old callers (unused)."""
    tri = verts[tris]                                                    # (N, 3, 3)
    if not len(tri):
        return tri.reshape(-1, 3), np.zeros((0, 3), dtype=np.int64)
    e = np.linalg.norm(tri - np.roll(tri, -1, axis=1), axis=2)          # edge k: corner k -> corner k+1
    k = np.argmax(e, axis=1)
    length = e[np.arange(len(tri)), k]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    width = THIN * area2 / np.maximum(length, 1e-12)
    target = np.maximum(longest, width)
    for _k in range(12):                                                 # a huge mesh: coarser, within the budget
        pieces = float(np.sum(2.0 * np.ceil(length / target)))
        if pieces <= MESH_BUDGET:
            break
        longest *= min(4.0, pieces / MESH_BUDGET)
        target = np.maximum(longest, width)
    n = np.ceil(length / target - 1e-9).astype(np.int64)
    cut = n > 1
    out = [tri[~cut]]
    for nn in np.unique(n[cut]):
        sel = np.flatnonzero(cut & (n == nn))
        r = np.arange(len(sel))
        kk = k[sel]
        p0, p1, p2 = tri[sel, kk], tri[sel, (kk + 1) % 3], tri[sel, (kk + 2) % 3]   # p0 -> p1 the longest edge
        u = np.arange(nn + 1) / nn
        a = p0[:, None] + (p1 - p0)[:, None] * u[None, :, None]          # (S, n+1, 3) along the longest edge
        l1 = np.linalg.norm(p2 - p0, axis=1)
        l2 = np.linalg.norm(p1 - p2, axis=1)
        n1 = np.clip(np.rint(nn * l1 / np.maximum(l1 + l2, 1e-12)), 1, nn - 1).astype(np.int64)
        i = np.arange(nn + 1)[None, :]
        f1 = np.minimum(i / n1[:, None], 1.0)                            # along p0 -> p2, then p2 -> p1
        f2 = np.clip((i - n1[:, None]) / (nn - n1)[:, None], 0.0, 1.0)
        b = np.where((i <= n1[:, None])[..., None], p0[:, None] + (p2 - p0)[:, None] * f1[..., None],
                     p2[:, None] + (p1 - p2)[:, None] * f2[..., None])
        t1 = np.stack([a[:, :-1], a[:, 1:], b[:, :-1]], axis=2)          # same turning sense as (p0, p1, p2)
        t2 = np.stack([a[:, 1:], b[:, 1:], b[:, :-1]], axis=2)
        out += [t1.reshape(-1, 3, 3), t2.reshape(-1, 3, 3)]
        del r
    tri = np.concatenate(out)
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    tri = tri[area > 0.0]                                                # the strip's two end pieces are points
    v = tri.reshape(-1, 3)
    return v, np.arange(len(v)).reshape(-1, 3)


def connected(n: int, tris: np.ndarray) -> np.ndarray:
    """A number per corner (``n`` corners): corners joined by faces ``tris`` share it (the smallest corner index of
    their piece)."""
    lab = np.arange(n)
    if not len(tris):
        return lab
    e0 = np.concatenate([tris[:, 0], tris[:, 1]])
    e1 = np.concatenate([tris[:, 1], tris[:, 2]])
    while True:
        a, b = lab[e0], lab[e1]
        m = np.minimum(a, b)
        new = lab.copy()
        np.minimum.at(new, a, m)
        np.minimum.at(new, b, m)
        for _k in range(8):                                   # follow the links to the root
            new = new[new]
        if np.array_equal(new, lab):
            return lab
        lab = new


def signed_volume(verts: np.ndarray, tris: np.ndarray) -> float:
    """The volume a closed mesh holds (positive when its triangles face outwards)."""
    if not len(tris):
        return 0.0
    v = verts[tris]
    return float(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6.0)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

@dataclass
class Hit:
    """One moment two parts were found too deep in each other (or too close)."""
    t: float                      # frame (fractional between frames)
    depth: float                  # m inside each other (a near miss: the gap)
    excess: float                 # m deeper than at the start (a near miss: 0)


@dataclass
class Row:
    kind: str                     # "CLASH" | "NEAR"
    a: str
    b: str
    frame_from: int
    frame_to: int
    t_deep: float                 # the moment of the deepest overlap (smallest gap)
    depth: float                  # deepest overlap (smallest gap), m
    hits: list = field(default_factory=list)
    names: tuple = ()             # the two objects' names (Blender)


def excess(depth: float, start_depth: float) -> float:
    """How much deeper than at the first frame two parts are inside each other."""
    return depth - max(0.0, start_depth)


SLACK = 0.5                   # parts that overlap at the start: their overlap is measured less exactly


def allowed_depth(start_depth: float, limit: float = DEPTH) -> float:
    """How deep two parts may be in each other before it counts: the clash depth past the overlap they start with,
    plus half of that overlap. Parts that touch start at (nearly) 0, so for them it is the clash depth; two meshes
    that overlap by centimetres in the CAD model (an eye drawn inside a solid bracket) are measured to a few
    millimetres only: the overlap is the deepest point found, and which one is found changes as they turn."""
    d0 = max(0.0, start_depth)
    return d0 + limit + SLACK * d0


def is_clash(depth: float, start_depth: float, limit: float = DEPTH) -> bool:
    return depth > allowed_depth(start_depth, limit)


def is_near(gap: float, start_gap: float, near: float) -> bool:
    """A near miss: closer than ``near`` while not touching, and they were further apart at the first frame."""
    return 0.0 < gap < near and start_gap >= near


def merge(hits: list, kind: str, a: str, b: str, gap: float = 1.0) -> list:
    """Hits of one pair (any order) -> rows: moments less than ``gap`` frames apart make one row."""
    rows: list[Row] = []
    for h in sorted(hits, key=lambda h: h.t):
        if rows and h.t - rows[-1].hits[-1].t <= gap + 1e-6:
            r = rows[-1]
            r.hits.append(h)
            r.frame_to = int(math.ceil(h.t - 1e-6))
            better = h.depth > r.depth if kind == "CLASH" else h.depth < r.depth
            if better:
                r.depth, r.t_deep = h.depth, h.t
        else:
            rows.append(Row(kind, a, b, int(math.floor(h.t + 1e-6)), int(math.ceil(h.t - 1e-6)), h.t, h.depth, [h]))
    return rows


def sort_rows(rows: list) -> list:
    """Clashes first, deepest first; then near misses, closest first."""
    return sorted(rows, key=lambda r: (r.kind != "CLASH", -r.depth if r.kind == "CLASH" else r.depth, r.frame_from))


def mm(x: float) -> str:
    v = x * 1000.0
    return f"{v:.1f} mm" if abs(v) < 100 else f"{v:.0f} mm"


def frames_text(r: Row) -> str:
    if r.frame_to <= r.frame_from:
        return f"frame {r.frame_from}"
    return f"frames {r.frame_from}–{r.frame_to}"


def row_text(r: Row) -> str:
    what = f"{mm(r.depth)} deep" if r.kind == "CLASH" else f"{mm(r.depth)} apart"
    return f"{r.a} × {r.b}: {frames_text(r)}, {what}"


def plural(n: int, word: str) -> str:
    from .words import plural as p
    return p(n, word, word + "es" if word.endswith(("sh", "ss")) else None)


def header(checked: bool, stale: bool, clashes: int, near: int = 0) -> str:
    """The state in the panel's header (after a Build)."""
    if not checked or stale:
        return "Not checked since the last Build"
    if clashes:
        return plural(clashes, "clash")
    if near:
        return plural(near, "near miss")
    return "No clashes"


def queue_note(anim: str, checked: bool, clashes: int) -> str:
    """The one-line note when an animation goes into the render queue ('' = nothing to say)."""
    if not checked:
        return f"'{anim}' was not checked for clashes (6 Animation > Clash check)"
    if clashes:
        return (f"'{anim}' has {plural(clashes, 'clash')}: parts run into each other "
                f"(6 Animation > Clash check)")
    return ""
