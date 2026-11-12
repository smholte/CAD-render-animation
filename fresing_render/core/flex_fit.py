"""A hose's centreline read from its triangle mesh, without Blender (task 0058).

``tube_centreline(verts, tris)`` takes the mesh of one hose, cable or pipe as the importer made it (a tube swept
along a path in 3D: solid or with a bore, 8 sides or 64, a hex ferrule on an end) and gives the line through the
middle of it from end to end, its outer radius, its length and the direction it leaves each end. Any unit; NumPy
only (Blender's Python has no SciPy).

How it works:

1. **Weld.** The importer repeats the vertices along the seams of the CAD faces; vertices closer together than a
   millionth of the part's size become one, in an order that depends on their places only (so a shuffled mesh gives
   the same answer).
2. **Which way the tube runs.** Distances along the surface (over the triangles' edges) from any vertex find one
   end, from that end the other (a "double sweep"). Their difference rises steadily from one end to the other
   whatever way the tube bends. (A tube with a bore: its inside wall is a tube length away from its outside wall
   along the surface, so the ends are looked for with the vertices lumped together in boxes first.)
3. **Slices.** The triangles are cut along levels of that number: every level gives a closed line round the tube,
   its middle is a point of the centreline. Cutting triangles (not sorting vertices) matters: a straight piece of
   a CAD tube has vertices at its two ends only.
4. **Square slices.** Four more times the tube is cut, now by how far along the centreline found so far each
   vertex lies (so the cuts are square to the tube), the last time 8 cuts per diameter. A circle is fitted to each
   cut line – to the line, not its corners, so a tube of 8 flat sides gives its exact middle. Cuts that run through
   an end face or a shoulder are not used; the bore's wall is left out where the triangles' facing tells it apart.
5. **Ends.** A line (a parabola when the end is bent) through the last diameter of centres gives the end's
   direction; the end point is where it meets the end face (the furthest vertex along it).
6. **Checks.** At least 3 diameters long, about the same thickness all along, round: else ``ok`` is False and
   ``problem`` says why in plain words. Nothing here raises on a bad mesh.

End 0 is the end with the smaller x (then y, then z). Measured (tests/test_flex_fit.py; a web session, 4 cores):
tubes of 8 to 32 sides along straight, arc, S and helix paths, solid or with a bore, with a hex ferrule: centreline
within 1 % of the radius, length within 0.02 %, ends within 0.1 mm on a Ø20 hose, end directions within 0.5°; the
hoses of the test model as the importer meshes them at Draft: length 0.1 % short (the facets cut the bends'
corners), ends and diameter exact. 20,000 triangles take 0.1 s.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

WELD = 1e-6            # vertices closer than this share of the part's size are one
SLENDER = 3.0          # a hose is at least this many diameters long
THICKNESS = 0.25       # a slice counts as "another thickness" when its radius is this far from the usual one
THICK_SHARE = 0.30     # at most this share of the length may have another thickness (ferrules, a nut)
ROUND_BAND = 0.90      # a slice's outline counts as "on the outside" beyond this share of its biggest radius …
ROUND_SHARE = 0.26     # … and at least this share of it must be (a square bar: 0.21, a hex with a bore: 0.3)
ROUND_GAP = 0.35       # a slice is used when its cut line goes (nearly) all the way round: about 260° or more
FACING = 0.7           # a triangle whose normal lies this much along the tube is an end face or a shoulder
PER_DIAMETER = 8.0     # slices of the last pass: this many per diameter …
LEVELS = (64, 1024)    # … within these limits
PASSES = 4             # square cuts: three coarser ones that steer, the last at the final fineness

_NOT_SLENDER = "The part is not long and thin: a hose is at least 3 times as long as it is thick."
_NOT_EVEN = "The part's thickness changes too much along its length for a hose."
_NOT_ROUND = "The part is not round like a hose."
_RING = "The part is a closed ring: it has no two ends."
_PIECES = "The part is made of separate pieces: pick one hose."
_NO_MESH = "The part has no shape to read."
_UNREADABLE = "The part's shape could not be read as a hose."


@dataclass
class Tube:
    ok: bool
    problem: str
    points: np.ndarray       # (n, 3) the centreline from end 0 to end 1, equally spaced
    radius: float            # the outer radius
    length: float            # along the centreline
    t0: np.ndarray           # unit, along the centreline from end 0 to end 1, at end 0
    t1: np.ndarray           # the same at end 1


def _fail(problem: str) -> Tube:
    return Tube(False, problem, np.zeros((0, 3)), 0.0, 0.0, np.zeros(3), np.zeros(3))


def tube_centreline(verts, tris, n: int = 65) -> Tube:
    """The centreline of a tube mesh: ``verts`` (V, 3) float, ``tris`` (T, 3) int (not welded is fine)."""
    try:
        v = np.asarray(verts, dtype=np.float64)
        t = np.asarray(tris)
        if v.ndim != 2 or v.shape[1] != 3 or t.ndim != 2 or t.shape[1] != 3 or len(v) < 4 or len(t) < 4:
            return _fail(_NO_MESH)
        t = t.astype(np.int64)
        return _fit(v, t, max(int(n), 2))
    except Exception:                                   # never raise on a bad mesh (the caller shows `problem`)
        return _fail(_UNREADABLE)


# ---------------------------------------------------------------------------------------------------------
# the mesh: weld, edges, distances along the surface
# ---------------------------------------------------------------------------------------------------------

def _weld(v: np.ndarray, tris: np.ndarray):
    """Vertices at the same place become one; returns (points, triangles, size) in an order set by place alone."""
    good = np.isfinite(v).all(axis=1)
    tris = tris[((tris >= 0) & (tris < len(v))).all(axis=1)]
    tris = tris[good[tris].all(axis=1)]
    if len(tris) < 4:
        return None
    used = np.zeros(len(v), dtype=bool)
    used[tris.ravel()] = True
    lo, hi = v[used].min(axis=0), v[used].max(axis=0)
    size = float(np.linalg.norm(hi - lo))
    if not size > 0.0:
        return None
    tol = size * WELD
    rel = (v - lo) / tol
    rel[~good] = 0.0

    def keys(shift):
        q = np.floor(rel + shift).astype(np.int64)
        return (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]

    # two grids half a cell apart: two vertices a hair apart that fall either side of a cell wall of one grid
    # share a cell of the other
    _, a = np.unique(keys(0.5), return_inverse=True)
    _, b = np.unique(keys(1.0), return_inverse=True)
    lab = a.copy()
    for _ in range(16):
        low = np.full(int(b.max()) + 1, len(v), dtype=np.int64)
        np.minimum.at(low, b, lab)
        nxt = low[b]
        low = np.full(int(a.max()) + 1, len(v), dtype=np.int64)
        np.minimum.at(low, a, nxt)
        nxt = low[a]
        if np.array_equal(nxt, lab):
            break
        lab = nxt
    _, lab = np.unique(lab, return_inverse=True)        # 0 … m-1, ordered by place (x, then y, then z)
    t = lab[tris]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    if len(t) < 4:
        return None
    first = np.argmin(t, axis=1)                        # the smallest corner first, the turning sense kept
    t = np.take_along_axis(t, (first[:, None] + np.arange(3)) % 3, axis=1)
    m = int(lab.max()) + 1
    t = np.unique(t[:, 0] * m * m + t[:, 1] * m + t[:, 2]) if m < 2_000_000 else None
    if t is None:
        return None
    t = np.stack([t // (m * m), (t // m) % m, t % m], axis=1)
    cnt = np.bincount(lab, minlength=m).astype(np.float64)
    p = np.stack([np.bincount(lab, weights=np.where(good, v[:, k], 0.0), minlength=m) for k in range(3)], axis=1)
    p /= np.maximum(cnt, 1.0)[:, None]
    keep = np.zeros(m, dtype=bool)                      # leave out vertices no triangle uses
    keep[t.ravel()] = True
    if not keep.all():
        new = np.cumsum(keep) - 1
        p, t = p[keep], new[t]
    return p, t, size


def _table(count: int, a: np.ndarray, b: np.ndarray, w: np.ndarray):
    """Edges a–b of length w as a neighbour table: (start of each point's row, neighbours, lengths)."""
    src = np.concatenate([a, b])
    dst = np.concatenate([b, a])
    ww = np.concatenate([w, w])
    order = np.argsort(src, kind="stable")
    start = np.zeros(count + 1, dtype=np.int64)
    np.cumsum(np.bincount(src, minlength=count), out=start[1:])
    return start, dst[order], ww[order]


def _edges(p: np.ndarray, t: np.ndarray):
    """The mesh's edges: (their two vertices), the neighbour table, closed (every edge between two triangles)."""
    m = len(p)
    pair = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [0, 2]]])
    key, count = np.unique(pair.min(axis=1) * m + pair.max(axis=1), return_counts=True)
    a, b = key // m, key % m
    return (a, b), _table(m, a, b, np.linalg.norm(p[a] - p[b], axis=1)), bool((count == 2).all())


def _far_ends(p: np.ndarray, edges, size: float):
    """A vertex near each end of a tube with a bore. Along the surface the bore's wall is a tube length away from
    the outside wall (round an end face), so the vertex "furthest away" is not at an end; here the vertices are
    first lumped together in boxes of ``size`` (both walls in one box) and the two ends looked for among the
    boxes."""
    a, b = edges
    q = np.floor((p - p.min(axis=0)) / size).astype(np.int64)
    _, cell, members = np.unique((q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2], return_inverse=True,
                                 return_counts=True)
    hub = np.stack([np.bincount(cell, weights=p[:, k]) for k in range(3)], axis=1) / members[:, None]
    count = len(members)
    ca, cb = cell[a], cell[b]
    key = np.unique(np.minimum(ca, cb) * count + np.maximum(ca, cb))
    ca, cb = key // count, key % count
    ca, cb = ca[ca != cb], cb[ca != cb]
    table = _table(count, ca, cb, np.linalg.norm(hub[ca] - hub[cb], axis=1))
    d = _distances(table, int(cell[0]), count)
    d[~np.isfinite(d)] = -1.0
    one = int(np.argmax(d))
    d = _distances(table, one, count)
    d[~np.isfinite(d)] = -1.0
    two = int(np.argmax(d))
    return int(np.flatnonzero(cell == one)[0]), int(np.flatnonzero(cell == two)[0])


def _distances(graph, source: int, m: int) -> np.ndarray:
    """Shortest way along the edges from one vertex to every other (the wave front worked on as whole arrays)."""
    start, nbr, w = graph
    keep = m
    d = np.full(m, np.inf)
    d[source] = 0.0
    front = np.array([source], dtype=np.int64)
    while front.size:
        s0 = start[front]
        cnt = start[front + 1] - s0
        total = int(cnt.sum())
        if total == 0:
            break
        first = np.cumsum(cnt) - cnt
        e = np.repeat(s0 - first, cnt) + np.arange(total)
        cand = np.repeat(d[front], cnt) + w[e]
        to = nbr[e]
        better = cand < d[to]
        to, cand = to[better], cand[better]
        if not to.size:
            break
        np.minimum.at(d, to, cand)
        seen = np.zeros(m, dtype=bool)
        seen[to] = True
        front = np.flatnonzero(seen)
    return d[:keep]


# ---------------------------------------------------------------------------------------------------------
# slices
# ---------------------------------------------------------------------------------------------------------


def _cut(p: np.ndarray, t: np.ndarray, s: np.ndarray, c0: float, dc: float, k: int):
    """Cut the triangles along the levels c0 + i·dc (i = 0 … k-1) of the number ``s`` each vertex has.

    Returns for every piece of a cut line: its level, its triangle, its two end points.

    Whether a vertex lies above a level is decided once per vertex (``top``: the highest level at or below it),
    so two triangles never disagree about a vertex that lies on a level to the last digit – a ring of a CAD
    tube often does – and every cut line closes."""
    top = np.floor((s - c0) / dc).astype(np.int64)
    st = s[t]
    order = np.argsort(st, axis=1)
    tv = np.take_along_axis(t, order, axis=1)
    ss = np.take_along_axis(st, order, axis=1)
    tt = np.sort(top[t], axis=1)
    i0 = np.maximum(tt[:, 0] + 1, 0)
    cnt = np.maximum(np.minimum(tt[:, 2], k - 1) - i0 + 1, 0)
    total = int(cnt.sum())
    tri = np.repeat(np.arange(len(t)), cnt)
    lev = np.repeat(i0 - (np.cumsum(cnt) - cnt), cnt) + np.arange(total)
    val = c0 + lev * dc
    pa, pb, pc = p[tv[tri, 0]], p[tv[tri, 1]], p[tv[tri, 2]]
    a, b, c = ss[tri, 0], ss[tri, 1], ss[tri, 2]
    one = pa + np.clip((val - a) / (c - a), 0.0, 1.0)[:, None] * (pc - pa)
    low = lev <= tt[tri, 1]                             # the middle corner is above: the cut leaves through a–b
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(low, (val - a) / (b - a), (val - b) / (c - b))
    f = np.clip(np.where(np.isfinite(f), f, 0.0), 0.0, 1.0)
    two = np.where(low[:, None], pa + f[:, None] * (pb - pa), pb + f[:, None] * (pc - pb))
    return lev, tri, one, two


def _middles(lev, one, two, k: int):
    """The middle of each level's cut line (every piece counts by its length), and how many pieces it has."""
    length = np.linalg.norm(two - one, axis=1)
    mid = 0.5 * (one + two)
    tot = np.bincount(lev, weights=length, minlength=k)
    c = np.stack([np.bincount(lev, weights=length * mid[:, i], minlength=k) for i in range(3)], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        c /= tot[:, None]
    return c, np.bincount(lev, minlength=k)


def _along(q: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])


def _at(q: np.ndarray, sq: np.ndarray, s: np.ndarray) -> np.ndarray:
    """The points at the distances ``s`` along the line ``q`` (straight on beyond its ends)."""
    out = np.stack([np.interp(s, sq, q[:, k]) for k in range(3)], axis=1)
    before, after = s < sq[0], s > sq[-1]
    if before.any():
        out[before] = q[0] + np.outer(s[before] - sq[0], _unit(q[1] - q[0]))
    if after.any():
        out[after] = q[-1] + np.outer(s[after] - sq[-1], _unit(q[-1] - q[-2]))
    return out


def _project(p: np.ndarray, q: np.ndarray, sq: np.ndarray, guess: np.ndarray, reach: int) -> np.ndarray:
    """How far along the line ``q`` each point lies (the nearest place on it; the first and last piece go on
    beyond their ends). Only the pieces within ``reach`` of the guess are tried: a hose may pass close to itself."""
    seg = q[1:] - q[:-1]
    l2 = np.maximum((seg * seg).sum(axis=1), 1e-300)
    ln = np.sqrt(l2)
    last = len(seg) - 1
    j0 = np.clip(np.searchsorted(sq, guess) - 1, 0, last)
    best = np.full(len(p), np.inf)
    out = np.zeros(len(p))
    for off in range(-reach, reach + 1):
        j = np.clip(j0 + off, 0, last)
        d = p - q[j]
        f = (d * seg[j]).sum(axis=1) / l2[j]
        f = np.clip(f, np.where(j == 0, -np.inf, 0.0), np.where(j == last, np.inf, 1.0))
        r = d - f[:, None] * seg[j]
        dd = (r * r).sum(axis=1)
        take = dd < best
        best = np.where(take, dd, best)
        out = np.where(take, sq[j] + f * ln[j], out)
    return out


def _frames(tan: np.ndarray):
    """Two directions square to each tangent (and to each other)."""
    least = np.argmin(np.abs(tan), axis=1)
    ref = np.zeros_like(tan)
    ref[np.arange(len(tan)), least] = 1.0
    u = np.cross(tan, ref)
    u /= np.linalg.norm(u, axis=1)[:, None]
    return u, np.cross(tan, u)


def _dot(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.einsum("ij,ij->i", a, b)


def _circles(lev, one, two, normal, base, tan, k: int, scale: float):
    """A circle through each level's cut line (the pieces on end faces and shoulders left out: their triangles
    face along the tube). Returns centres (k, 3), the radius of the outside (k,), the share of the outline that
    lies on the outside (k,), usable (k,): a whole outline and a believable circle.

    The fit is over the cut *line* (each piece's two ends and its middle, weighted 1 : 1 : 4 – exact for the sums
    used), not over its corners: where the cut crosses a diagonal inside a flat facet must not matter, or a tube
    with few sides pulls its own centreline about from pass to pass."""
    u, w = _frames(tan)
    tl = tan[lev]
    wall = np.abs(_dot(normal, tl)) < FACING
    clean = np.bincount(lev[~wall], minlength=k) == 0       # a cut through an end face is not a whole outline
    lev, one, two, normal, tl = lev[wall], one[wall], two[wall], normal[wall], tl[wall]
    ul, wl, bl = u[lev], w[lev], base[lev]
    d1, d2 = (one - bl) / scale, (two - bl) / scale
    x1, y1, x2, y2 = _dot(d1, ul), _dot(d1, wl), _dot(d2, ul), _dot(d2, wl)
    zm = 0.5 * (_dot(d1, tl) + _dot(d2, tl))
    xm, ym = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    length = np.sqrt(_dot(d2 - d1, d2 - d1))
    # a bore: when the triangles all face out of the material (the importer's do), the pieces that face the
    # centreline are the bore's and are left out; told by the pieces furthest out, which are on the outside
    far = xm * xm + ym * ym
    most = np.zeros(k)
    np.maximum.at(most, lev, far)
    facing = xm * _dot(normal, ul) + ym * _dot(normal, wl) > 0
    vote = length * (far > 0.9 * most[lev])
    share_out = float((vote * facing).sum()) / max(float(vote.sum()), 1e-300)
    if share_out > 0.95 or share_out < 0.05:
        keep = facing == (share_out > 0.5)
        lev, length, zm = lev[keep], length[keep], zm[keep]
        x1, y1, x2, y2, xm, ym = x1[keep], y1[keep], x2[keep], y2[keep], xm[keep], ym[keep]
    r1, r2, rm = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, xm * xm + ym * ym
    sixth = length / 6.0

    def add(f1, f2, fm):                                    # the sum along the cut line (Simpson's rule)
        return np.bincount(lev, weights=sixth * (f1 + f2 + 4.0 * fm), minlength=k)

    s1 = np.bincount(lev, weights=length, minlength=k)
    sx, sy = add(x1, x2, xm), add(y1, y2, ym)
    sz = np.bincount(lev, weights=length * zm, minlength=k)
    sxx, sxy, syy = add(x1 * x1, x2 * x2, xm * xm), add(x1 * y1, x2 * y2, xm * ym), add(y1 * y1, y2 * y2, ym * ym)
    sxr, syr, sr = add(x1 * r1, x2 * r2, xm * rm), add(y1 * r1, y2 * r2, ym * rm), add(r1, r2, rm)
    ok = clean & (np.bincount(lev, minlength=k) >= 6) & (s1 > 0)
    safe = np.where(ok, s1, 1.0)
    mat = np.zeros((k, 3, 3))
    mat[:, 0, 0], mat[:, 0, 1], mat[:, 0, 2] = sxx, sxy, sx
    mat[:, 1, 0], mat[:, 1, 1], mat[:, 1, 2] = sxy, syy, sy
    mat[:, 2, 0], mat[:, 2, 1], mat[:, 2, 2] = sx, sy, s1
    rhs = np.stack([sxr, syr, sr], axis=1)
    flat = ~ok | ~(np.linalg.det(mat) > 1e-9 * safe ** 3 * np.maximum(sr / safe, 1e-300) ** 2)
    mat[flat] = np.eye(3)
    sol = np.linalg.solve(mat, rhs[:, :, None])[:, :, 0]
    cx, cy = 0.5 * sol[:, 0], 0.5 * sol[:, 1]
    rho2 = sol[:, 2] + cx * cx + cy * cy
    with np.errstate(invalid="ignore"):
        ok = ~flat & np.isfinite(cx + cy + rho2) & (rho2 > 0.16) & (rho2 < 6.25) & (cx * cx + cy * cy < 4.0)
    cx, cy = np.where(ok, cx, 0.0), np.where(ok, cy, 0.0)
    centre = base + scale * (cx[:, None] * u + cy[:, None] * w + (sz / safe)[:, None] * tan)
    cxl, cyl = cx[lev], cy[lev]
    dist1, dist2 = np.hypot(x1 - cxl, y1 - cyl), np.hypot(x2 - cxl, y2 - cyl)
    ex, ey = xm - cxl, ym - cyl
    distm = np.hypot(ex, ey)
    near = np.maximum(distm, 1e-300)                        # all the way round: these add up to nothing
    round_x = np.bincount(lev, weights=length * ex / near, minlength=k)
    round_y = np.bincount(lev, weights=length * ey / near, minlength=k)
    ok &= np.hypot(round_x, round_y) <= ROUND_GAP * safe
    outer = np.zeros(k)
    np.maximum.at(outer, lev, np.maximum(dist1, dist2))
    band = ROUND_BAND * outer[lev]
    on = add((dist1 > band).astype(float), (dist2 > band).astype(float), (distm > band).astype(float))
    return centre, outer * scale, on / safe, ok


def _end(c: np.ndarray, s: np.ndarray, span: float, radius: float) -> np.ndarray:
    """The centreline near its first point, from the centres within ``span`` of it: a straight line when they
    lie on one (to 0.3 % of the radius), else a parabola. Coefficients as np.polyfit gives them, over the
    distance from the first centre."""
    count = int(min(max(int(np.searchsorted(s, s[0] + span, side="right")), 3), len(c)))
    x = s[:count] - s[0]
    pts = c[:count]
    line = np.polyfit(x, pts, 1)
    rest = pts - (np.outer(x, line[0]) + line[1])
    if count >= 5 and float(np.sqrt((rest * rest).sum(axis=1).mean())) > 0.003 * radius:
        return np.polyfit(x, pts, 2)
    return line


def _on(co: np.ndarray, x: float):
    """Point and direction (not unit) of the curve of ``_end`` at x."""
    if len(co) == 3:
        return co[0] * x * x + co[1] * x + co[2], 2.0 * co[0] * x + co[1]
    return co[0] * x + co[1], co[0]


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _end_face(co: np.ndarray, near: np.ndarray):
    """Where the curve of ``_end`` leaves the tube: the point on the end face (the furthest vertex along the
    curve's own direction there) and the unit direction into the tube."""
    x = 0.0
    for _ in range(4):
        pt, dv = _on(co, x)
        speed = float(np.linalg.norm(dv))
        x += float(((near - pt) @ dv).min()) / max(speed * speed, 1e-300)
    pt, dv = _on(co, x)
    return pt, _unit(dv)


# ---------------------------------------------------------------------------------------------------------
# the fit
# ---------------------------------------------------------------------------------------------------------

def _fit(verts: np.ndarray, tris: np.ndarray, n: int) -> Tube:
    welded = _weld(verts, tris)
    if welded is None:
        return _fail(_NO_MESH)
    p, t, size = welded
    m = len(p)
    if m < 4 or len(t) < 4:
        return _fail(_NO_MESH)
    origin = p.mean(axis=0)
    p = p - origin
    edges, graph, closed = _edges(p, t)
    normal = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    area_t = 0.5 * np.linalg.norm(normal, axis=1)
    area = float(area_t.sum())
    if not area > 0.0:
        return _fail(_NO_MESH)

    # 2. the two ends: furthest from any vertex, then furthest from that one
    d = _distances(graph, 0, m)
    if not np.isfinite(d).all():
        reached = np.isfinite(d)
        keep = reached[t[:, 0]]
        if area_t[keep].sum() < 0.98 * area:
            return _fail(_PIECES)
        new = np.cumsum(reached) - 1                    # crumbs beside the hose: leave them out
        p, t, area_t, normal = p[reached], new[t[keep]], area_t[keep], normal[keep]
        m, area = len(p), float(area_t.sum())
        edges, graph, closed = _edges(p, t)
        d = _distances(graph, 0, m)
    normal = normal / np.maximum(2.0 * area_t, 1e-300)[:, None]
    end_a = int(np.argmax(d))
    da = _distances(graph, end_a, m)
    end_b = int(np.argmax(da))
    db = _distances(graph, end_b, m)
    reach = float(da[end_b])
    if not reach > 0.0:
        return _fail(_NO_MESH)
    thick = area / (2.0 * np.pi * reach)                # a first idea of the radius (a bore counts double)
    euler = m - len(edges[0]) + len(t)
    genus_one = closed and euler == 0                   # a ring – or a pipe with a bore
    if euler != 2:                                      # not a plain closed skin: a bore
        end_a, end_b = _far_ends(p, edges, thick)
        da = _distances(graph, end_a, m)
        db = _distances(graph, end_b, m)
        reach = float(da[end_b])
        if not reach > 0.0:
            return _fail(_NO_MESH)
    # what to say when the slices below make no sense: a block or a plate is "not long and thin"
    vague = _NOT_SLENDER if reach < 4.0 * SLENDER * thick else _UNREADABLE

    # 3. slices along the tube, by the difference of the two distances (not the last 3 radii: the two "ends"
    #    found are corners on the rims, the slices next to them lie askew)
    f = 0.5 * (da - db + reach)                         # 0 at end A … reach at end B
    k0 = int(np.clip(round(reach / thick), 8, 96))
    margin = min(3.0 * thick, 0.25 * reach)
    dc = (reach - 2.0 * margin) / k0
    lev, _tri, one, two = _cut(p, t, f, margin + 0.5 * dc, dc, k0)
    centre, pieces = _middles(lev, one, two, k0)
    ok = pieces >= 3
    if ok.sum() < 4:
        return _fail(vague)
    wide = np.zeros(k0)
    np.maximum.at(wide, lev, np.linalg.norm(0.5 * (one + two) - centre[lev], axis=1))
    wide = wide[ok]
    centre, par = centre[ok], (margin + (np.arange(k0) + 0.5) * dc)[ok]
    radius = float(np.median(wide))
    if not radius > 0.0:
        return _fail(vague)

    # 4. cut again square to the centreline found so far, four times; the last time at the final fineness
    param, lo, hi, pad = f, 0.0, reach, 3.0 * thick
    outer = share = None
    for step in range(PASSES):
        s_c = _along(centre)
        p0, d0 = _on(_end(centre, s_c, 2.0 * radius, radius), 0.0)
        p1, d1 = _on(_end(centre[::-1], s_c[-1] - s_c[::-1], 2.0 * radius, radius), 0.0)
        ext0, ext1 = par[0] - lo + pad, hi - par[-1] + pad      # the line goes on straight beyond the tube's ends
        q = np.concatenate([[p0 - ext0 * _unit(d0)], centre, [p1 - ext1 * _unit(d1)]])
        sq = _along(q)
        guess = np.interp(param, np.concatenate([[par[0] - ext0], par, [par[-1] + ext1]]), sq)
        seg = sq[-1] / (len(q) - 1)
        s = _project(p, q, sq, guess, int(np.ceil((3.0 if step == 0 else 1.0) * radius / seg)) + 1)
        lo, hi = float(s.min()), float(s.max())
        length = hi - lo
        if not length > 0.0:
            return _fail(vague)
        k = int(np.clip(np.ceil(PER_DIAMETER * length / (2.0 * radius)), LEVELS[0], LEVELS[1]))
        if step < PASSES - 1:                           # the earlier passes only steer: coarser is enough
            k = min(k, 4 * k0) if step == 0 else max(k // 2, min(k, LEVELS[0]))
        dc = length / k
        levels = lo + (np.arange(k) + 0.5) * dc
        base = _at(q, sq, levels)
        tan = _at(q, sq, levels + 0.5 * dc) - _at(q, sq, levels - 0.5 * dc)
        tan /= np.maximum(np.linalg.norm(tan, axis=1), 1e-300)[:, None]
        lev, tri, one, two = _cut(p, t, s, levels[0], dc, k)
        centre, outer, share, good = _circles(lev, one, two, normal[tri], base, tan, k, radius)
        if good.sum() < max(4, k // 2):
            return _fail(vague)
        centre, par, outer, share = centre[good], levels[good], outer[good], share[good]
        radius = float(np.median(outer))
        param, pad = s, 2.0 * radius
        if step == 0 and length < 0.5 * SLENDER * 2.0 * radius:
            break                                       # far from slender: no need to look closer

    # 5. the ends: the direction from the last diameter of centres, the point on the end face
    s_c = _along(centre)
    e0, d0 = _end_face(_end(centre, s_c, 2.0 * radius, radius), p[param <= lo + 3.0 * dc])
    e1, d1 = _end_face(_end(centre[::-1], s_c[-1] - s_c[::-1], 2.0 * radius, radius), p[param >= hi - 3.0 * dc])
    line = np.concatenate([[e0], centre, [e1]])
    s_line = _along(line)
    length = float(s_line[-1])

    # 6. is it a hose?
    ring = genus_one and float(np.median(wide[len(wide) // 4: len(wide) // 4 + max(len(wide) // 2, 1)])) > 3 * thick
    if length < SLENDER * 2.0 * radius:
        return _fail(_RING if ring else _NOT_SLENDER)
    if (np.abs(outer / radius - 1.0) > THICKNESS).mean() > THICK_SHARE:
        return _fail(_RING if ring else _NOT_EVEN)
    if float(np.median(share)) < ROUND_SHARE:
        return _fail(_NOT_ROUND)

    points = _at(line, s_line, np.linspace(0.0, length, n))
    points[0], points[-1] = e0, e1
    t0, t1 = d0, -d1
    eps = 1e-9 * size
    for i in range(3):
        if abs(e0[i] - e1[i]) > eps:
            if e0[i] > e1[i]:
                points, t0, t1 = points[::-1].copy(), -t1, -t0
            break
    return Tube(True, "", points + origin, radius, length, t0, t1)
