"""Clash check (task 0065), the parts without Blender: which parts move together, boxes, the motion between two
frames, and turning the moments two parts were found inside each other into the rows the panel lists.

How a check works (``blender/clash.py`` drives it):

1. Every frame of the built animation is set once (and every corner of a G-code program between frames); the
   place of every part and whether it is shown are read.
2. **Rigid bodies.** Parts whose motion is the same at every moment (``D(t) = M(t) · M(start)⁻¹``) keep their place
   against each other the whole animation: they are never compared (``rigid_groups``). A welded frame, a bolt in its
   hole, everything one joint carries: one body.
3. **Broad phase.** For every pair of bodies that moves against each other: their boxes in the world at each moment,
   then the boxes of their parts (``box_pairs``).
4. **Between frames.** Where two bodies come near each other and together move more than ``STEP`` between two
   frames, extra moments are put in between; each body's motion between the two frames is followed as a screw
   motion (``screw_between``: exact for a turn about a fixed axis and for a straight move), so a fast part cannot
   jump through another one in one frame step.
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


def corners(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """(N, 8, 3) corners of boxes ``lo``/``hi`` (N, 3)."""
    sel = np.array([[(k >> a) & 1 for a in range(3)] for k in range(8)], dtype=bool)   # (8, 3)
    return np.where(sel[None], hi[:, None, :], lo[:, None, :])


def transform(m: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """``m`` (..., 4, 4) applied to ``pts`` (..., K, 3)."""
    return np.einsum("...ij,...kj->...ki", m[..., :3, :3], pts) + m[..., None, :3, 3]


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
