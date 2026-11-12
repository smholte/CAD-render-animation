"""Normals for the milled workpiece (task 0061): flat faces flat, round walls smooth, sharp edges crisp. No Blender.

Why the app works them out itself
---------------------------------
A boolean leaves many **needle triangles** behind: three points (almost) on one line along the edge of a face, often
with no area at all (on the milled test block 239 of 2,220 triangles are lower than 1/1000 of their length, 26 have
area exactly 0). Such a triangle has no direction of its own - the one worked out from its corners is rounding
noise (Blender's own, in 32 bits, was more than 30 degrees off on 42 of them). Blender's "smooth by angle" trusts
it all the same: it marks an edge sharp by the angle between the two faces at it, so a needle between a floor and a
wall can join the two, and it mixes the needle's direction into the corners of its flat neighbours, weighted by
the needle's corner angle (up to 180 degrees). The result: big flat triangles whose normal leans up to 10 degrees
at one corner - the dark facets in reflections.

What ``corner_normals`` does
----------------------------
* One normal per triangle corner: the sum of the **planes** round its vertex that point within ``angle`` of this
  corner's own triangle. So triangles in one plane give exactly the face normal, the 9 degree facets of a round
  wall blend, and nothing is shaded across an edge sharper than ``angle``.
* **Every plane counts once**, however many triangles it has at the vertex and however wide they are there. All
  along the edge between two flat strips of a round wall every vertex then gets the same normal - also where a
  later cut chopped a strip into odd triangles, and on both sides of a seam between two tiles. (Weights by area or
  by corner angle change from vertex to vertex: ripples along the wall, a visible line at a seam.) The triangles
  of one plane share its vote by how well their direction is known (height squared).
* **A big flat face stays flat.** Two planes that meet at a vertex are compared by how far each reaches away from
  the edge they share. One that reaches ``BIG`` times further than the other is the flat face and the other a small
  facet next to it: the small one has no say in the big one's normal, and takes the big one's direction at that
  edge. A floor next to the shallow facets a ball mill left, the flank of a V-groove next to the fan of its round
  end, a straight wall next to its rounded corner: the flat face keeps exactly its own normal and the small facets
  run into it smoothly – as on the CAD part, where a rounding starts with the flat face's direction. (Before, such
  a floor leaned up to 18 degrees at the corners that touch the facets: found by the independent tests of task
  0061.) The strips of a round wall all reach as far from their edges as each other – their width, however long
  they are and wherever a seam between tiles cuts them – and blend as before.
  (Narrow flat strips between the shallow facets of ball-mill passes are as small as those facets and blend with
  them: a scalloped surface is shaded smooth. Comparing whole planes by their area in the mesh was tried and
  dropped: it differs on the two sides of a seam between tiles.)
* A triangle **too thin to trust** (lower than ``NOISE`` rounding steps of 32-bit coordinates, or than ``SLIVER``
  x its longest edge) counts for nothing in its neighbours' normals, and takes the direction of the real triangle
  across its longest edge (through other needles if need be) as its own - it is shaded as a piece of that face.

Vertices are shared within one tile of the workpiece only (tiles are separate solids), and one call is one tile.
That is enough: where a seam runs through a flat face both sides are flat, and where it crosses the edge between two
strips of a round wall both sides see the same two planes - **if the flat faces that close each tile inside the
material are left out** (``skip=seam_faces(verts, tris, tile.lo, tile.hi)``; measured: the report of task 0061).
``weld=True`` joins vertices at the same place first, for a mesh of several tiles in one call.

Units: any (metres in the app). Angles in radians.
"""

from __future__ import annotations

import math

import numpy as np

SHARP_ANGLE = math.radians(30.0)      # edges sharper than this stay crisp (the same as blender/machining.py)
SAME = math.radians(0.1)              # triangles closer than this (plus their rounding noise) are one plane
SLIVER = 1e-5                         # lower than this x its longest edge: a needle, its normal is not used
NOISE = 128.0                         # ... or lower than this many 32-bit rounding steps of the coordinates
WELD = 1e-7                           # weld=True: points closer than about this are one vertex
PAIRS = 1_500_000                     # pairs of triangles round a vertex worked out in one go (memory)
EXACT = 8                             # fans up to this size are worked out with others of exactly that size
BIG = 6.0                             # a plane reaching this many times less far from a shared edge has no say
BIG_POWER = 8                         # (a plane's reach at a vertex: its triangles' reaches, summed with this power)
RUN_IN = math.radians(16.0)           # a small facet takes the flat face's direction up to this angle between them
_COS_RUN_IN = math.cos(RUN_IN)
ROUNDS = 16                           # needles next to needles: how far a real neighbour's direction is passed on
_EPS32 = float(np.finfo(np.float32).eps)


def corner_normals(verts, tris, angle: float = SHARP_ANGLE, weld: bool = False, skip=None) -> np.ndarray:
    """Unit normals, one per triangle corner: float32 (len(tris) * 3, 3) in the order of ``tris.reshape(-1)``.

    ``verts`` (n, 3), ``tris`` (m, 3) vertex numbers. ``angle``: faces further apart than this are not blended.
    ``weld``: treat vertices at the same place as one (a mesh of several tiles); off, only shared numbers count.
    ``skip``: True for triangles nobody sees (``seam_faces``): they pull no other normal and stay flat themselves.
    Never NaN: a triangle without a direction and without a real neighbour gets +Z.
    """
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3).astype(np.intp, copy=False)
    m = len(t)
    if m == 0:
        return np.zeros((0, 3), dtype=np.float32)
    fn, trust, fuzz, thin, edge2 = _faces(v, t)
    hidden = None
    if skip is not None:
        hidden = np.asarray(skip, dtype=bool).reshape(-1)
        trust[hidden] = 0.0
    # from every corner to the two other corners of its triangle (nothing for needles and hidden faces): how far
    # a triangle reaches away from an edge at that vertex
    p = v.take(t, axis=0)
    to_a = np.zeros((3 * m + 1, 3))
    to_b = np.zeros((3 * m + 1, 3))
    to_a[:3 * m] = (p[:, (1, 2, 0)] - p).reshape(-1, 3)
    to_b[:3 * m] = (p[:, (2, 0, 1)] - p).reshape(-1, 3)
    gone = np.repeat(thin if hidden is None else (thin | hidden), 3)
    to_a[:3 * m][gone] = 0.0
    to_b[:3 * m][gone] = 0.0
    np.nan_to_num(to_a, copy=False)
    np.nan_to_num(to_b, copy=False)
    ids = _weld(v)[t] if weld else t
    # the corners sorted by vertex: the triangles round one vertex lie next to each other
    vid = ids.reshape(-1)
    order = np.argsort(vid)
    counts = np.bincount(vid)
    start = np.cumsum(counts) - counts
    any_thin = bool(thin.any())
    source = ~thin if hidden is None else ~(thin | hidden)
    ref = _references(fn, thin, source, edge2, ids, order, start, counts) if any_thin else fn
    cos = math.cos(angle)
    # one more triangle (number m, corner 3 m) that is nothing: it fills up the fans that are worked out together
    order = np.append(order, 3 * m)
    face = order // 3                                    # the triangle of each sorted corner
    blank = np.zeros((1, 3))
    fn_ = np.concatenate([fn, blank])
    ref_ = np.concatenate([ref, blank]) if any_thin else fn_
    trust_, fuzz_, thin_ = np.append(trust, 0.0), np.append(fuzz, 0.0), np.append(thin, False)
    out = np.zeros((3 * m + 1, 3))
    used = np.flatnonzero(counts)
    sizes = counts[used]
    room = _rooms(sizes)
    for k in np.unique(room).tolist():                  # all vertices with (up to) k triangles round them at once
        vs = used[room == k]
        if k == 1:
            out[order[start[vs]]] = fn[face[start[vs]]]
            continue
        if k * k > PAIRS:
            for x in vs.tolist():
                _huge(out, order, face, int(start[x]), int(counts[x]), fn_, ref_, trust_, fuzz_, cos)
            continue
        step = max(1, PAIRS // (k * k))
        for i in range(0, len(vs), step):
            at = start[vs[i:i + step], None] + np.arange(k)                    # (vertices, k) sorted corners
            if k > EXACT:
                at[np.arange(k) >= counts[vs[i:i + step], None]] = 3 * m
            f = face.take(at)
            n = fn_.take(f, axis=0)
            dots = np.matmul(n, np.ascontiguousarray(n.transpose(0, 2, 1)))                   # (vertices, k, k)
            if any_thin:
                rows = np.nonzero(thin_.take(f))
                if len(rows[0]):                         # a needle looks round with its neighbour's direction
                    dots[rows] = np.matmul(n[rows[0]], ref_[f[rows]][:, :, None])[:, :, 0]
            corner = order.take(at)
            out[corner] = _blend(dots, n, trust_.take(f), fuzz_.take(f), cos, to_a.take(corner, axis=0),
                                 to_b.take(corner, axis=0), thin_.take(f) if any_thin else None)
    out = out[:3 * m]
    if hidden is not None:
        flat = np.flatnonzero(hidden & ~thin)
        out.reshape(m, 3, 3)[flat] = fn[flat][:, None, :]
    return _finish(out, ref, trust, fn, vid, m)


def seam_faces(verts, tris, lo, hi) -> np.ndarray:
    """True for the triangles that lie in a side of the box ``lo`` .. ``hi`` (a tile of the workpiece).

    Where the workpiece is split in tiles each tile is closed by a flat face inside the material. Nobody sees it,
    but it touches the cut faces along the seam: a wall that crosses the seam within the angle of it would lean
    towards it (measured 4 to 13 degrees, another way on each side: a line along the seam). Give the result to
    ``corner_normals`` as ``skip``. The block's own outer faces are not on the box (it is a little bigger).
    """
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3)
    sides = np.concatenate([np.asarray(lo, dtype=np.float64).reshape(3), np.asarray(hi, dtype=np.float64).reshape(3)])
    tol = 8.0 * _EPS32 * max(float(np.abs(sides).max()), 1e-30)
    on = np.zeros(len(v), dtype=np.uint8)                # per vertex one bit for each side it lies in
    for j in range(6):
        on |= (np.abs(v[:, j % 3] - sides[j]) <= tol).astype(np.uint8) << j
    return (on.take(t[:, 0]) & on.take(t[:, 1]) & on.take(t[:, 2])) != 0


def _rooms(sizes: np.ndarray) -> np.ndarray:
    """How many places the fan of each vertex gets: its own size up to EXACT, above that 12, 16, 24, 32, 48 ...
    (the few big fans are filled up with nothing, so they are worked out in a handful of goes)."""
    room = sizes.copy()
    big = sizes > EXACT
    if big.any():
        k = sizes[big]
        top = np.left_shift(1, np.ceil(np.log2(k)).astype(np.intp))
        room[big] = np.where(k * 4 <= top * 3, top * 3 // 4, top)
    return room


def _huge(out, order, face, a: int, k: int, fn, ref, trust, fuzz, cos: float) -> None:
    """One fan too big to hold all its pairs at once (thousands of triangles round one vertex): rows at a time."""
    f = face[a:a + k]
    n, w, z = fn[f], trust[f], fuzz[f]
    rows = max(1, PAIRS // k)
    share = np.empty(k)
    for r in range(0, k, rows):                          # each plane's vote, shared among its triangles
        share[r:r + rows] = ((1.0 - n[r:r + rows] @ n.T) < (z[r:r + rows, None] + z) ** 2) @ w
    contrib = n * (w / np.maximum(share, 1e-300))[:, None]
    for r in range(0, k, rows):
        near = (ref[f[r:r + rows]] @ n.T) > cos
        out[order[a + r:a + min(k, r + rows)]] = near.astype(np.float64) @ contrib


def _blend(dots, n, w, fuzz, cos: float, to_a, to_b, thin=None) -> np.ndarray:
    """Round each vertex (first axis): for every triangle the sum of the planes that point within the angle of it.

    Every plane counts once: its triangles share its vote by how well their direction is known (``w``). Two
    triangles are one plane when they are closer than their directions are certain (``fuzz``).

    ``to_a``, ``to_b``: from the vertex to each triangle's two other corners. A plane that reaches ``BIG`` times
    further from the edge it shares with another is the flat face of the two: the small one has no say in its
    normal and takes its direction. (How far triangle j reaches from its edge with plane i is how far its corners
    stand out of plane i, over the sine of the angle between the two – the same sine both ways, so it drops out.)
    ``thin``: the needles; they look round with their neighbour's direction and are left out of this.
    """
    limit = fuzz[:, :, None] + fuzz[:, None, :]
    limit *= limit
    same = 1.0 - dots < limit
    share = np.matmul(same.astype(np.float64), w[:, :, None])                                  # (vertices, k, 1)
    contrib = n * (w[:, :, None] / np.maximum(share, 1e-300))
    near = dots > cos
    # rise[i, j]: how far triangle j stands out of the plane of triangle i; reach[i, j]: the same for all of j's plane
    rise = np.maximum(np.abs(np.matmul(n, to_a.transpose(0, 2, 1))), np.abs(np.matmul(n, to_b.transpose(0, 2, 1))))
    scale = np.maximum(rise.max(axis=(1, 2), keepdims=True), 1e-300)
    reach = np.matmul((rise / scale) ** BIG_POWER, same.astype(np.float64))
    limit8 = BIG ** BIG_POWER
    mine = reach.transpose(0, 2, 1)                       # mine[i, j]: how far i's plane stands out of j's
    other = near & ~same
    # over[i, j]: j is the flat face, i a small facet next to it
    over = reach > limit8 * mine
    under = over.transpose(0, 2, 1)
    # ... and the two nearly in line (the first strip of a rounding, the first facet of a ball pass): a steeper
    # small face keeps its own say and shows the crease it has
    rules = other & over & ~under & (dots > _COS_RUN_IN)
    small = other & under & ~over                         # the other way round: j has no say in i's normal
    if thin is not None:
        rules &= ~thin[:, :, None]
        small &= ~thin[:, :, None]
    ruled = rules.any(axis=2, keepdims=True)
    votes = np.where(ruled, rules, near & ~small)
    return np.matmul(votes.astype(np.float64), contrib)


def _faces(v: np.ndarray, t: np.ndarray) -> tuple:
    """(unit face normals, how well each is known (m,), how far off it may be (m,), too thin to trust (m,),
    squared edge lengths (m, 3))."""
    p0, p1, p2 = v.take(t[:, 0], axis=0), v.take(t[:, 1], axis=0), v.take(t[:, 2], axis=0)
    a, b, c = p1 - p0, p2 - p1, p0 - p2                  # the edges leaving corner 0, 1, 2
    n = np.empty_like(a)                                 # a x (-c), twice the area long
    n[:, 0] = a[:, 2] * c[:, 1] - a[:, 1] * c[:, 2]
    n[:, 1] = a[:, 0] * c[:, 2] - a[:, 2] * c[:, 0]
    n[:, 2] = a[:, 1] * c[:, 0] - a[:, 0] * c[:, 1]
    area2 = np.sqrt(np.einsum("ij,ij->i", n, n))
    edge2 = np.empty_like(a)
    for j, e in enumerate((a, b, c)):
        edge2[:, j] = np.einsum("ij,ij->i", e, e)
    longest = np.sqrt(edge2.max(axis=1))
    size = float(np.abs(v).max()) if v.size else 0.0
    if not math.isfinite(size):
        finite = np.isfinite(v)
        size = float(np.abs(v[finite]).max()) if finite.any() else 0.0
    step = _EPS32 * size                                 # coordinates are rounded to about this
    with np.errstate(divide="ignore", invalid="ignore"):
        height = area2 / longest                         # above the longest edge
        thin = ~(height > np.maximum(SLIVER * longest, NOISE * step))               # NaN counts as thin
        fn = n / area2[:, None]
        # rounding turns a triangle by up to about (2 steps) / height: trust goes with height squared ...
        trust = height * height
        # ... and two triangles are one plane when they are closer than SAME plus what rounding may have done
        # (as 1 - cos = angle squared / 2, hence the root of 2)
        fuzz = (SAME + 2.0 * step / height) / math.sqrt(2.0)
    fn[thin] = 0.0
    trust[thin] = 0.0
    fuzz[thin] = 0.0
    return fn, trust, fuzz, thin, edge2


def _weld(v: np.ndarray) -> np.ndarray:
    """For every vertex the number of the first vertex at (about) the same place."""
    with np.errstate(invalid="ignore"):
        q = np.round(np.nan_to_num(v) / WELD).astype(np.int64)
    q -= q.min(axis=0)
    span = q.max(axis=0) + 1
    if float(span[0]) * float(span[1]) * float(span[2]) < 2.0 ** 62:
        _u, first, inv = np.unique((q[:, 0] * span[1] + q[:, 1]) * span[2] + q[:, 2],
                                   return_index=True, return_inverse=True)
    else:
        _u, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    return first[inv.reshape(-1)]


def _references(fn, thin, source, edge2, ids, order, start, counts) -> np.ndarray:
    """The face normals, with for every needle the direction of the real triangle next to it (``source``: the
    triangles whose direction may be passed on)."""
    s = np.flatnonzero(thin)
    ns = len(s)
    # the triangle across each edge of a needle: one round the edge's end that also has its start
    a = ids[s].reshape(-1)                               # edge j of a needle runs from corner j ...
    b = ids[s][:, (1, 2, 0)].reshape(-1)                 # ... to the next one
    me = np.repeat(s, 3)
    cnt = counts[b]
    edge = np.repeat(np.arange(3 * ns), cnt)             # one entry per (edge, triangle round its end)
    within = np.arange(len(edge)) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    face = order[start[b][edge] + within] // 3
    hit = (ids[face] == a[edge][:, None]).any(axis=1) & (face != me[edge])
    nb = np.full(3 * ns, -1, dtype=np.intp)
    for sel in (hit & ~source[face], hit & source[face]):      # a real triangle wins over another needle
        nb[edge[sel]] = face[sel]
    nb = nb.reshape(ns, 3)
    by_length = np.argsort(-edge2[s], axis=1, kind="stable")                  # the longest edge first
    nb = np.take_along_axis(nb, by_length, axis=1)
    ref = fn.copy()
    known = source.copy()
    todo = np.arange(ns)
    for _round in range(ROUNDS):
        if len(todo) == 0:
            break
        cand = nb[todo]
        ok = (cand >= 0) & known[cand]
        got = ok.any(axis=1)
        if not got.any():
            break
        pick = cand[got, np.argmax(ok[got], axis=1)]
        ref[s[todo[got]]] = ref[pick]
        known[s[todo[got]]] = True                       # after the whole round: one step per round
        todo = todo[~got]
    return ref


def _finish(out, ref, trust, fn, vid, m) -> np.ndarray:
    """Unit length; a corner that got nothing takes its triangle's direction, else whatever is round its vertex."""
    length = np.sqrt(np.einsum("ij,ij->i", out, out))
    bad = ~(length > 1e-12)
    if bad.any():
        i = np.flatnonzero(bad)
        out[i] = ref[i // 3]
        length[i] = np.sqrt(np.einsum("ij,ij->i", out[i], out[i]))
        still = i[~(length[i] > 1e-12)]
        if len(still):                                   # a needle among needles: all real faces at its vertex
            contrib = np.repeat(fn * (trust / max(float(trust.max()), 1e-300))[:, None], 3, axis=0)
            nv = int(vid.max()) + 1
            total = np.stack([np.bincount(vid, weights=contrib[:, j], minlength=nv) for j in range(3)], axis=1)
            out[still] = total[vid[still]]
            length[still] = np.sqrt(np.einsum("ij,ij->i", out[still], out[still]))
            last = still[~(length[still] > 1e-12)]
            out[last] = (0.0, 0.0, 1.0)
            length[last] = 1.0
    out /= length[:, None]
    return out.astype(np.float32)
