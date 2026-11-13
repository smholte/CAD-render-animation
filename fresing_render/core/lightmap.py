"""Lightmap UVs and baked-light numbers (task 0107). No Blender: pure Python + NumPy.

Baked light gives every placed copy of a part its own picture of the light it receives (copies stand in different
places, so their light differs). The steps:

1. **Charts** (``unwrap``, once per unique mesh). Each triangle goes to the side of a box its normal points at most
   (main axis and its sign, as ``web3d.box_uv``) and is projected flat onto that side (``u x v`` points out of the
   side). Points closer than ``WELD`` are welded first, because CAD meshes are split at sharp edges. Triangles of
   one side that share an edge form a piece. A piece can still lie over itself in projection (a helical ramp after
   one turn): every pair of triangles of a piece whose projections overlap is found (a grid of cells, then a
   separating-axis test), and such a piece is cut in two at the median of the direction that tells the two layers
   apart (nearly always the depth) until no piece overlaps itself. So the charts never overlap by construction.
   Hair-thin triangles (no trustworthy normal) join the side of a neighbour. Chart UVs are in metres, each chart's
   own lower-left corner at (0, 0).
2. **Sizes** (``texels_per_m``, ``chart_pixels``): texels per metre from the quality's texel budget and the area;
   each chart gets ``ceil(size * tpm) + 1`` texels plus ``padding`` on every side.
3. **Packing** (``pack``): the charts of all copies, largest first, into atlases of ``ATLAS`` px with a skyline
   (bottom-left: the lowest place along the skyline, then the leftmost). Deterministic.
4. **UVs per copy** (``place_uv``): chart metres -> pixels of the copy's place -> 0..1 of its atlas (v up, row 0 at
   the bottom, Blender's convention). Between the texels of two charts lie at least ``2 * padding`` free texels,
   so Cycles' bake margin (EXTEND, ``padding`` px) of one chart never reaches into a neighbour.

Small parts that are many (bolts, rollers) carry their light per vertex instead (``prefer_vertex``).

Encoding for the file: the light factor F (the baked light divided by the light on an open, upward surface) is stored
in 8 bits as ``v = (F / scale) ** (1 / curve)``, ``curve`` = ``CURVE``, ``scale`` = the 99.9th percentile of all F of
the export, at least 1 (``scale_of``, ``encode``, ``decode``). The square root keeps more steps in the dark corners.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ATLAS = 2048
CURVE = 2.0
QUALITY = {"DRAFT": {"samples": 16, "budget": 1_000_000, "padding": 2},
           "NORMAL": {"samples": 64, "budget": 4_000_000, "padding": 4},
           "FINE": {"samples": 256, "budget": 16_000_000, "padding": 4}}
MIN_TPM, MAX_TPM = 4.0, 400.0

WELD = 1e-6            # m: points closer than this are one point when charts are joined
SLIVER = 1e-5          # a triangle whose height is below this share of its longest edge has no trustworthy normal
TOUCH = 1e-9           # m: projections that only touch (shared edge or corner) within this do not overlap
_CELL_BUDGET = 16      # grid cells per triangle (on average per piece) when looking for overlapping pairs
_SAT_CHUNK = 400_000   # pairs per separating-axis batch
_RASTER_CHUNK = 4_000_000
_OPEN_ATLASES = 4      # packing tries the last few atlases only (older ones are as good as full)


@dataclass
class Unwrap:
    """The chart layout of one unique mesh."""
    uv: np.ndarray      # (m*3, 2) float64 metres, chart-local (chart corner at (0, 0)), corners as tris.ravel()
    chart: np.ndarray   # (m,) int32 chart of each triangle, 0..k-1
    size: np.ndarray    # (k, 2) float64 chart width and height in metres
    area: float         # surface area of the mesh (m²)

    @property
    def charts(self) -> int:
        return len(self.size)


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------

def _components(n: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Connected pieces of ``n`` items joined by the pairs (a[i], b[i]) -> labels 0..k-1, numbered in the order of
    each piece's first item (deterministic). Union by smaller label and pointer jumping, all in NumPy."""
    lab = np.arange(n, dtype=np.int64)
    a = np.asarray(a, np.int64)
    b = np.asarray(b, np.int64)
    while len(a):
        la, lb = lab[a], lab[b]
        ne = la != lb
        if not ne.any():
            break
        la, lb = la[ne], lb[ne]
        np.minimum.at(lab, np.maximum(la, lb), np.minimum(la, lb))
        while True:
            nxt = lab[lab]
            if np.array_equal(nxt, lab):
                break
            lab = nxt
        a, b = a[ne], b[ne]
    _, inv = np.unique(lab, return_inverse=True)       # roots are each piece's smallest item: order of first item
    return inv.astype(np.int64).ravel()


def _edge_pairs(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pairs of triangles that share an edge (welded vertex ids ``w`` (m, 3))."""
    m = len(w)
    e0 = np.concatenate([w[:, 0], w[:, 1], w[:, 2]])
    e1 = np.concatenate([w[:, 1], w[:, 2], w[:, 0]])
    tri = np.tile(np.arange(m, dtype=np.int64), 3)
    lo, hi = np.minimum(e0, e1), np.maximum(e0, e1)
    keep = lo != hi
    lo, hi, tri = lo[keep], hi[keep], tri[keep]
    nv = int(w.max()) + 1 if m else 1
    key = lo * nv + hi
    order = np.argsort(key, kind="stable")
    ks, ts = key[order], tri[order]
    same = ks[1:] == ks[:-1]
    a, b = ts[:-1][same], ts[1:][same]
    keep = a != b
    return a[keep], b[keep]


def _sat_overlap(P: np.ndarray, i: np.ndarray, j: np.ndarray, tol: float) -> np.ndarray:
    """True where the 2D triangles P[i] and P[j] (P (m, 3, 2)) overlap in area (separating-axis test; projections that
    only touch within ``tol`` do not count)."""
    out = np.zeros(len(i), bool)
    for s in range(0, len(i), _SAT_CHUNK):
        A, B = P[i[s:s + _SAT_CHUNK]], P[j[s:s + _SAT_CHUNK]]
        ea = np.roll(A, -1, axis=1) - A
        eb = np.roll(B, -1, axis=1) - B
        ax = np.concatenate([np.stack([-ea[..., 1], ea[..., 0]], -1), np.stack([-eb[..., 1], eb[..., 0]], -1)], 1)
        ln = np.linalg.norm(ax, axis=-1)
        valid = ln > 0
        ax = ax / np.where(valid, ln, 1.0)[..., None]
        pa = np.einsum("nkd,ncd->nkc", ax, A)
        pb = np.einsum("nkd,ncd->nkc", ax, B)
        sep = (pa.max(-1) <= pb.min(-1) + tol) | (pb.max(-1) <= pa.min(-1) + tol)
        out[s:s + _SAT_CHUNK] = ~(sep & valid).any(1)
    return out


def _overlapping_pairs(P: np.ndarray, lab: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pairs of triangles of one piece (``lab``) whose projections ``P`` (m, 3, 2) overlap; only triangles with
    ``use`` take part. Candidates from a grid of cells per piece (about ``_CELL_BUDGET`` cells per triangle)."""
    idx = np.nonzero(use)[0]
    if len(idx) < 2:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    Q = P[idx]
    L = lab[idx]
    bmin, bmax = Q.min(1), Q.max(1)
    nl = int(L.max()) + 1
    cnt = np.bincount(L, minlength=nl).astype(np.float64)
    ext = bmax - bmin
    mean = np.bincount(L, weights=np.maximum(ext[:, 0], ext[:, 1]), minlength=nl) / np.maximum(cnt, 1)
    cell = np.maximum(mean, 1e-9)
    gmin = np.full((nl, 2), np.inf)
    np.minimum.at(gmin, L, bmin)
    for _ in range(40):
        c = cell[L][:, None]
        lo = np.floor((bmin - gmin[L]) / c).astype(np.int64)
        hi = np.floor((bmax - gmin[L]) / c).astype(np.int64)
        n = (hi - lo + 1).prod(1)
        tot = np.bincount(L, weights=n, minlength=nl)
        over = tot > _CELL_BUDGET * cnt + 4096
        if not over.any():
            break
        cell = np.where(over, cell * 2.0, cell)
    nx = hi[:, 0] - lo[:, 0] + 1
    total = int(n.sum())
    rep = np.repeat(np.arange(len(idx)), n)
    start = np.cumsum(n) - n
    k = np.arange(total, dtype=np.int64) - start[rep]
    cx = lo[rep, 0] + k % nx[rep]
    cy = lo[rep, 1] + k // nx[rep]
    span = int(max(cx.max(), cy.max())) + 1
    key = (L[rep].astype(np.int64) * span + cx) * span + cy
    order = np.argsort(key, kind="stable")
    ks = key[order]
    tri = rep[order]
    first = np.r_[True, ks[1:] != ks[:-1]]
    gstart = np.nonzero(first)[0]
    gsize = np.diff(np.r_[gstart, len(ks)])
    gid = np.cumsum(first) - 1
    later = gstart[gid] + gsize[gid] - 1 - np.arange(len(ks))      # entries after this one in its cell
    npair = int(later.sum())
    if npair == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    pr = np.repeat(np.arange(len(ks)), later)
    off = np.arange(npair, dtype=np.int64) - (np.cumsum(later) - later)[pr]
    a, b = tri[pr], tri[pr + 1 + off]
    ca, cb = cx[order][pr], cy[order][pr]
    box = ((bmin[a] < bmax[b] - TOUCH) & (bmin[b] < bmax[a] - TOUCH)).all(1)
    # each pair once: only in the cell that holds the lower-left corner of the two boxes' common part
    box &= (ca == np.maximum(lo[a, 0], lo[b, 0])) & (cb == np.maximum(lo[a, 1], lo[b, 1]))
    a, b = a[box], b[box]
    hit = _sat_overlap(Q, a, b, TOUCH)
    return idx[a[hit]], idx[b[hit]]


def unwrap(points: np.ndarray, tris: np.ndarray) -> Unwrap:
    """Charts of one mesh: ``points`` (n, 3) metres in the mesh's own coordinates, ``tris`` (m, 3) vertex indices.
    No chart overlaps itself or another; see the module text for the method."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    tri = np.asarray(tris, np.int64).reshape(-1, 3)
    m = len(tri)
    if m == 0:
        return Unwrap(np.zeros((0, 2)), np.zeros(0, np.int32), np.zeros((0, 2)), 0.0)
    q = np.round(pts / WELD).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    wpts = pts[first]
    w = inv[tri]                                                   # welded vertex ids (m, 3)
    p = wpts[w]                                                    # (m, 3, 3)
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    dbl = np.linalg.norm(fn, axis=1)                               # twice the area
    area = float(dbl.sum() / 2.0)
    longest = np.max(np.linalg.norm(p - np.roll(p, 1, axis=1), axis=2), axis=1)
    sliver = dbl <= SLIVER * longest * longest
    axis = np.argmax(np.abs(fn), axis=1)
    sign = fn[np.arange(m), axis] < 0
    group = axis * 2 + sign

    ea, eb = _edge_pairs(w)
    if sliver.any():                                               # thin triangles join a neighbour's side
        ok = ~sliver
        for _ in range(4):
            for x, y in ((ea, eb), (eb, ea)):
                take = ~ok[x] & ok[y]
                group[x[take]] = group[y[take]]
                ok[x[take]] = True
            if ok.all():
                break
        axis = group // 2
        sign = group % 2 == 1
    b, c = (axis + 1) % 3, (axis + 2) % 3
    rows = np.arange(m)[:, None]
    u = p[rows, np.arange(3)[None, :], b[:, None]] * np.where(sign, -1.0, 1.0)[:, None]
    v = p[rows, np.arange(3)[None, :], c[:, None]]
    P = np.stack([u, v], -1)                                       # (m, 3, 2) projected, metres
    depth = p[np.arange(m), :, axis].mean(1) * np.where(sign, -1.0, 1.0)
    coord = np.stack([depth, u.mean(1), v.mean(1)], 1)

    same = group[ea] == group[eb]
    ea, eb = ea[same], eb[same]
    lab = _components(m, ea, eb)
    oi, oj = _overlapping_pairs(P, lab, ~sliver)

    for _ in range(64):                                            # cut pieces that lie over themselves
        bad = lab[oi] == lab[oj]
        if not bad.any():
            break
        bi, bj = oi[bad], oj[bad]
        nl = int(lab.max()) + 1
        d = np.abs(coord[bi] - coord[bj])
        score = np.stack([np.bincount(lab[bi], weights=d[:, k], minlength=nl) for k in range(3)], 1)
        choice = np.argmax(score, axis=1)
        isbad = np.zeros(nl, bool)
        isbad[lab[bi]] = True
        t = np.nonzero(isbad[lab])[0]
        x = coord[t, choice[lab[t]]]
        order = np.lexsort((t, x, lab[t]))
        ts, ls = t[order], lab[t][order]
        start = np.searchsorted(ls, ls, side="left")
        cnt = np.bincount(ls, minlength=nl)
        sub = np.zeros(m, np.int64)
        sub[ts] = (2 * (np.arange(len(ts)) - start) >= cnt[ls]).astype(np.int64)
        new = lab * 2 + sub
        keep = new[ea] == new[eb]
        lab = _components(m, ea[keep], eb[keep])

    k = int(lab.max()) + 1
    corner_lab = np.repeat(lab, 3)
    flat = P.reshape(-1, 2)
    lo = np.full((k, 2), np.inf)
    hi = np.full((k, 2), -np.inf)
    np.minimum.at(lo, corner_lab, flat)
    np.maximum.at(hi, corner_lab, flat)
    uv = flat - lo[corner_lab]
    return Unwrap(uv, lab.astype(np.int32), hi - lo, area)


# ---------------------------------------------------------------------------
# sizes, packing, UVs
# ---------------------------------------------------------------------------

def texels_per_m(area_m2: float, budget: int) -> float:
    """Texels per metre so that ``area_m2`` takes about ``budget`` texels, kept within MIN_TPM .. MAX_TPM."""
    if not area_m2 or area_m2 <= 0:
        return MAX_TPM
    return float(min(MAX_TPM, max(MIN_TPM, math.sqrt(budget / area_m2))))


def chart_pixels(size_m: np.ndarray, tpm: float, padding: int) -> np.ndarray:
    """Pixel size of each chart's place (k, 2) int: its texels (``ceil(size * tpm) + 1``) and ``padding`` on every
    side."""
    s = np.asarray(size_m, np.float64).reshape(-1, 2)
    return (np.ceil(s * tpm - 1e-9).astype(np.int64) + 1 + 2 * int(padding)).astype(np.int64)


def _window_max(h: np.ndarray, w: int) -> np.ndarray:
    """max(h[x : x + w]) for every x in 0 .. len(h) - w (van Herk / Gil-Werman, O(len(h)))."""
    W = len(h)
    n = -(-W // w) * w
    a = np.zeros(n, h.dtype)
    a[:W] = h
    blk = a.reshape(-1, w)
    pre = np.maximum.accumulate(blk, axis=1).ravel()
    suf = np.maximum.accumulate(blk[:, ::-1], axis=1)[:, ::-1].ravel()
    x = np.arange(W - w + 1)
    return np.maximum(suf[x], pre[x + w - 1])


class TooBig(ValueError):
    """Raised by ``pack`` when copies do not fit an empty atlas; ``items`` = their indices (scale them down)."""

    def __init__(self, items: list[int], atlas: int):
        self.items = list(items)
        super().__init__(f"{len(self.items)} copies do not fit an atlas of {atlas} px: {self.items[:10]}")


def _order(sz: np.ndarray) -> np.ndarray:
    """Charts tallest first, then widest, then in their own order."""
    return np.lexsort((np.arange(len(sz)), -sz[:, 0], -sz[:, 1]))


def _place_all(sky: np.ndarray, sz: np.ndarray, atlas: int) -> np.ndarray | None:
    """Put the charts ``sz`` (k, 2) on the skyline ``sky`` (changed in place) -> (k, 2) x, y, or None (sky unchanged)
    when one does not fit."""
    work = sky.copy()
    xy = np.zeros((len(sz), 2), np.int64)
    for r in _order(sz):
        w, h = int(sz[r, 0]), int(sz[r, 1])
        if w > atlas or h > atlas:
            return None
        ys = _window_max(work, w)
        x = int(np.argmin(ys))
        y = int(ys[x])
        if y + h > atlas:
            return None
        work[x:x + w] = y + h
        xy[r] = (x, y)
    sky[:] = work
    return xy


def fits(sizes: np.ndarray, atlas: int = ATLAS) -> bool:
    """True when the charts of one copy (k, 2) px fit together in one empty atlas (exactly as ``pack`` puts them)."""
    sz = np.asarray(sizes, np.int64).reshape(-1, 2)
    return _place_all(np.zeros(atlas, np.int64), sz, atlas) is not None


def pack(items: list[np.ndarray], atlas: int = ATLAS) -> list[np.ndarray]:
    """Places for the charts of several copies: ``items`` per copy (k_i, 2) int pixel sizes (padding included) ->
    per copy (k_i, 3) int: atlas index, x, y of each chart's lower-left corner (row 0 at the bottom).

    All charts of one copy land in the same atlas (each copy is baked into one image). Copies go tallest chart first
    (then the largest total), their charts tallest first; a copy goes to the first of the last ``_OPEN_ATLASES``
    atlases where all its charts fit (else a new one), each at the lowest place along that atlas's skyline (then the
    leftmost). Deterministic. Copies that do not fit an empty atlas raise ``TooBig`` (a ValueError) naming them all: shrink those (``fits`` tells) and pack again."""
    sizes = [np.asarray(s, np.int64).reshape(-1, 2) for s in items]
    out = [np.zeros((len(s), 3), np.int64) for s in sizes]
    if any((s < 1).any() for s in sizes):
        raise ValueError("a chart has a size below 1 pixel")
    bad = [i for i, s in enumerate(sizes) if len(s) and not fits(s, atlas)]
    if bad:
        raise TooBig(bad, atlas)
    tall = np.array([int(s[:, 1].max()) if len(s) else 0 for s in sizes], np.int64)
    tot = np.array([int((s[:, 0] * s[:, 1]).sum()) for s in sizes], np.int64)
    skylines: list[np.ndarray] = []
    for i in np.lexsort((np.arange(len(sizes)), -tot, -tall)):
        sz = sizes[i]
        if not len(sz):
            continue
        need = int(sz[:, 1].max())
        for ai in range(max(0, len(skylines) - _OPEN_ATLASES), len(skylines)):
            sky = skylines[ai]
            if int(sky.min()) + need > atlas:
                continue
            xy = _place_all(sky, sz, atlas)
            if xy is not None:
                break
        else:
            sky = np.zeros(atlas, np.int64)
            skylines.append(sky)
            ai = len(skylines) - 1
            xy = _place_all(sky, sz, atlas)
        out[i][:, 0] = ai
        out[i][:, 1:] = xy
    return out


def place_uv(un: Unwrap, tpm: float, places: np.ndarray, padding: int, atlas: int = ATLAS
             ) -> tuple[np.ndarray, np.ndarray]:
    """UVs of one copy: chart metres -> its places (``places`` (k, 3) from ``pack``) -> 0..1 of the atlas.
    Returns (uv (m*3, 2) float32, v up / row 0 at the bottom; atlas index of each triangle (m,))."""
    pl = np.asarray(places, np.int64).reshape(-1, 3)
    corner = np.repeat(un.chart.astype(np.int64), 3)
    org = pl[:, 1:3].astype(np.float64) + padding + 0.5            # texel centre of each chart's first texel
    px = org[corner] + np.asarray(un.uv, np.float64) * tpm
    return (px / atlas).astype(np.float32), pl[un.chart.astype(np.int64), 0].astype(np.int32)


VERTEX_MAX_PX = 16      # with ``size_m``: per-vertex light only for parts at most this many texels across


def prefer_vertex(n_vertices: int, area_m2: float, tpm: float, size_m: float | None = None) -> bool:
    """Per-vertex light rather than a map: when its vertices take fewer bytes than half the map's texels. With
    ``size_m`` (the part's longest side) also only when the part is at most ``VERTEX_MAX_PX`` texels across, so a big
    plain plate with few points keeps its shadows in a map."""
    if size_m is not None and size_m * tpm > VERTEX_MAX_PX:
        return False
    return n_vertices * 3 < area_m2 * tpm * tpm / 2.0


def image_size(area_m2: float, uv_area: float, tpm: float, max_px: int = ATLAS) -> tuple[int, int]:
    """Square power-of-two image (16 .. ``max_px``) for an object with its own UV set: its ``area_m2`` covers the
    share ``uv_area`` (0..1) of the UV square and should get about ``tpm`` texels per metre."""
    share = min(1.0, max(float(uv_area), 1e-6))
    side = math.sqrt(max(area_m2, 0.0) * tpm * tpm / share)
    px = 16
    while px < side and px < max_px:
        px *= 2
    px = min(px, max_px)
    return px, px


# ---------------------------------------------------------------------------
# encoding
# ---------------------------------------------------------------------------

def scale_of(values: list[np.ndarray]) -> float:
    """The export's ``scale``: the 99.9th percentile of the brightest channel of all light factors, at least 1."""
    parts = [np.asarray(v, np.float64).reshape(-1, 3).max(1) for v in values if np.size(v)]
    if not parts:
        return 1.0
    a = np.concatenate(parts)
    a = a[np.isfinite(a)]
    if not len(a):
        return 1.0
    return float(max(1.0, np.percentile(a, 99.9)))


def encode(f: np.ndarray, scale: float, curve: float = CURVE) -> np.ndarray:
    """Light factors -> 8 bits: ``round(255 * clip(f / scale, 0, 1) ** (1 / curve))``."""
    x = np.clip(np.nan_to_num(np.asarray(f, np.float64) / scale), 0.0, 1.0)
    return np.round(255.0 * x ** (1.0 / curve)).astype(np.uint8)


def decode(u8: np.ndarray, scale: float, curve: float = CURVE) -> np.ndarray:
    """8 bits -> light factors (float32), the inverse of ``encode``."""
    return ((np.asarray(u8, np.float64) / 255.0) ** curve * scale).astype(np.float32)


# ---------------------------------------------------------------------------
# picture clean-up
# ---------------------------------------------------------------------------

def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """``a`` moved by (dy, dx) with zeros coming in: out[y, x] = a[y - dy, x - dx]."""
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def dilate(pixels: np.ndarray, mask: np.ndarray, steps: int) -> np.ndarray:
    """Fill unbaked texels from baked ones, ``steps`` rings outward: each ring takes the mean of its baked (or already
    filled) 8 neighbours. Baked texels (``mask``) stay as they are. ``pixels`` (h, w, c) floats."""
    px = np.array(pixels, np.float32, copy=True)
    have = np.asarray(mask, bool).copy()
    if px.ndim == 2:
        px = px[..., None]
    nb = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    for _ in range(int(steps)):
        acc = np.zeros_like(px)
        n = np.zeros(have.shape, np.float32)
        hv = have.astype(np.float32)
        for dy, dx in nb:
            acc += _shift(px * hv[..., None], dy, dx)
            n += _shift(hv, dy, dx)
        new = (~have) & (n > 0)
        if not new.any():
            break
        px[new] = acc[new] / n[new][:, None]
        have |= new
    return px.reshape(np.shape(pixels)) if np.ndim(pixels) == 2 else px


def _box(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    """Sum over a window of 2r + 1 along ``axis`` (zeros outside)."""
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return hi - lo


def smooth(pixels: np.ndarray, mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """A denoise fallback: a box blur of ``radius`` that only mixes texels inside ``mask`` (normalised convolution);
    texels outside the mask stay as they are. Keep ``radius`` <= 2 * padding so charts never mix."""
    px = np.asarray(pixels, np.float32)
    two = px.ndim == 2
    if two:
        px = px[..., None]
    mk = np.asarray(mask, bool)
    mf = mk.astype(np.float64)
    num = _box(_box(px * mf[..., None], radius, 0), radius, 1)
    den = _box(_box(mf, radius, 0), radius, 1)
    out = px.copy()
    sel = mk & (den > 0)
    out[sel] = (num[sel] / den[sel][:, None]).astype(np.float32)
    return out[..., 0] if two else out


# ---------------------------------------------------------------------------
# checks and estimates
# ---------------------------------------------------------------------------

def overlap_texels(uv: np.ndarray, chart: np.ndarray, atlas_index: np.ndarray, atlas: int = ATLAS) -> int:
    """Test helper: texels baked by more than one triangle. Each triangle covers the texel centres strictly inside it
    (as Cycles bakes), so two edge neighbours of one chart never count; triangles of two charts, or of one chart
    overlapping in area, do. ``uv`` (m*3, 2) in 0..1, ``chart`` (m,) (kept for the record), ``atlas_index`` (m,)."""
    P = np.asarray(uv, np.float64).reshape(-1, 3, 2) * atlas
    ai = np.asarray(atlas_index, np.int64).reshape(-1)
    del chart
    x0 = np.ceil(P[..., 0].min(1) - 0.5).astype(np.int64)
    x1 = np.floor(P[..., 0].max(1) - 0.5).astype(np.int64)
    y0 = np.ceil(P[..., 1].min(1) - 0.5).astype(np.int64)
    y1 = np.floor(P[..., 1].max(1) - 0.5).astype(np.int64)
    nx = np.maximum(x1 - x0 + 1, 0)
    ny = np.maximum(y1 - y0 + 1, 0)
    a2 = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
          - (P[:, 1, 1] - P[:, 0, 1]) * (P[:, 2, 0] - P[:, 0, 0]))
    n = nx * ny * (np.abs(a2) > 1e-12)
    keys = []
    csum = np.cumsum(n)
    s = 0
    while s < len(n):
        base = csum[s - 1] if s else 0
        e = int(np.searchsorted(csum, base + _RASTER_CHUNK, side="right"))
        e = max(e, s + 1)
        t = np.arange(s, e)
        cnt = n[t]
        rep = np.repeat(t, cnt)
        k = np.arange(int(cnt.sum()), dtype=np.int64) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        x = x0[rep] + k % nx[rep]
        y = y0[rep] + k // nx[rep]
        cx, cy = x + 0.5, y + 0.5
        sg = np.sign(a2[rep])
        inside = np.ones(len(rep), bool)
        for i in range(3):
            A, B = P[rep, i], P[rep, (i + 1) % 3]
            wv = ((B[:, 0] - A[:, 0]) * (cy - A[:, 1]) - (B[:, 1] - A[:, 1]) * (cx - A[:, 0])) * sg
            inside &= wv > 1e-7
        keys.append((ai[rep] * atlas + y)[inside] * atlas + x[inside])
        s = e
    if not keys:
        return 0
    allk = np.concatenate(keys)
    _, c = np.unique(allk, return_counts=True)
    return int((c > 1).sum())


def estimate(texels: int, vertices: int, samples: int, passes: int, rate: float, gpu_factor: float,
             bytes_per_texel: float, copies_vertices: int = 0) -> dict:
    """Time and file size of a bake. ``rate`` = samples x texels (or vertices) per second on this CPU,
    ``gpu_factor`` = how many times faster the GPU is (an estimate), ``copies_vertices`` = vertices that get per-vertex
    light (3 bytes each, also counted in ``vertices``' time when the caller includes them there)."""
    cpu = (texels * samples * passes + vertices * samples * passes) / rate if rate > 0 else 0.0
    return {"seconds_cpu": float(cpu), "seconds_gpu": float(cpu / gpu_factor) if gpu_factor > 0 else float(cpu),
            "bytes": int(texels * bytes_per_texel + 3 * (vertices + copies_vertices))}
