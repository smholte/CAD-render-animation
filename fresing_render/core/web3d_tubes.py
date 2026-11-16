"""Moving cables, ropes, hoses and links on the web page (task 0142), no Blender.

The app draws a cable, a wire rope, a hose and the rope on a spool with Geometry Nodes: a round tube along a centre
line (``Curve to Mesh`` of a circle). Track links, drag-chain links and things riding on a cable are moved as one
piece by a modifier. The export reads back what Blender draws at each frame (``blender/web3d_drawn.py``) and keeps it
small with what is here:

* ``find_rings``: a tube's evaluated points -> its ring centres, the first point of each ring (the ring's turn), the
  radius and the number of sides. ``Curve to Mesh`` writes ring after ring, each starting at angle 0.
* ``tangents``, ``transport``, ``chords``: the centre line's directions (Blender's rule for a poly curve: the sum of
  the two unit pieces), the ring's turn carried along by the smallest turn from one point to the next (Blender's
  "minimum twist" normals: the page gets the first one only and carries it along, measured within 0.003°), and the
  length along it (the cable look's ``s`` = s0 + chords, within 0.05 mm of the app's own on the test models).
* ``fit_rigid``: the move of a piece (4 well-spread points before and after; ``spread``).
* ``thin`` / ``thin_frames`` / ``thin_node``: which moments to keep – a split at the worst moment (Douglas–Peucker
  over time) until straight-line blending between kept moments is off by at most the tolerance everywhere.
* ``pack``: the kept centre lines as 16-bit numbers per point (each point's own range over time).
* ``at``: what the page works out at a time (``fresing_render/web/fr_tubes.js`` does the same in JavaScript; the
  tests compare both with the app).

Units: the part's own coordinates (metres unless the part is scaled); tolerances are passed in those units.
"""

from __future__ import annotations

import math

import numpy as np

POS_TOL = 0.001          # m: a kept moment may be off by this much (points, the ring's turn at the radius)
S_TOL = 0.002            # m: ... the length along the cable and the metres paid out (the look's stripes)
NODE_TOL = 0.001         # m: a moving part's place (at the far end of the part from its origin)
CUT_EPS = 1e-6           # relative: a spool's cut this close to a point of its path is on it (float32 lengths)
TURN_TOL = math.radians(3.0)   # the page's own ring turn may be this far off the app's (only the looks' angle)
SIDES_MAX = 64           # most sides a ring is looked for with
FIT = 4                  # points a rigid move is fitted from
RIGID_TOL = 2e-5         # m (per metre of size): the evaluated mesh is the part's own moved as one piece
CHUNK = 192              # moments compared at a time while thinning (memory)
VERSION = 1              # of ``extras.fr_tube``


# ---------------------------------------------------------------------------
# reading a tube back
# ---------------------------------------------------------------------------

def find_rings(co, sides: int | None = None, rel: float = 2e-3):
    """``co`` (N, 3): an evaluated tube's points, ring after ring. Returns (centres (R, 3), first point direction of
    each ring (R, 3, unit), radius, sides) or None when they are not rings of one radius (a ring must be round and
    flat: two neighbouring rings are round about their middle too, but not flat)."""
    co = np.asarray(co, np.float64).reshape(-1, 3)
    n = len(co)
    cands = [sides] if sides else range(3, SIDES_MAX + 1)
    for s in cands:
        if s is None or s < 3 or n % s or n // s < 2:
            continue
        r = co.reshape(-1, s, 3)
        c = r.mean(axis=1)
        d = np.linalg.norm(r - c[:, None], axis=2)
        rad = float(d.mean())
        if rad <= 0.0 or np.abs(d - rad).max() > rel * rad + 1e-7:
            continue
        # flat: no point far from the plane through the centre square to the tangent of the ring's own points
        a = r[:, 0] - c
        b = r[:, s // 4 if s >= 4 else 1] - c
        nrm = np.cross(a, b)
        ln = np.linalg.norm(nrm, axis=1)
        if (ln <= 1e-12 * rad * rad).any():
            continue
        nrm /= ln[:, None]
        off = np.abs(((r - c[:, None]) * nrm[:, None]).sum(axis=2))
        if off.max() > rel * rad + 1e-7:
            continue
        first = a / np.linalg.norm(a, axis=1)[:, None]
        return c, first, rad, s
    return None


def tangents(p, min_len: float = 0.0) -> np.ndarray:
    """Unit directions along a poly line (n, 3): at a point the sum of the unit pieces on both sides (Blender's rule
    for poly curves), at the ends the end piece. ``min_len`` > 0: pieces are looked past until they add up to
    that much on each side (16-bit points make the direction of a piece a fraction of a millimetre long noise; the
    export passes 32 steps of its points). A piece of length 0 counts as nothing."""
    p = np.asarray(p, np.float64)
    n = len(p)
    out = np.zeros((n, 3))
    if n < 2:
        out[:, 2] = 1.0
        return out
    if min_len > 0.0:
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
        if seg.min() < min_len:
            return _tangents_far(p, min_len)
    seg = np.diff(p, axis=0)
    ln = np.linalg.norm(seg, axis=1)
    u = np.where(ln[:, None] > 1e-12, seg / np.maximum(ln, 1e-300)[:, None], 0.0)
    out[0] = u[0]
    out[-1] = u[-1]
    out[1:-1] = u[:-1] + u[1:]
    return _unit_or_near(out)


def _unit_or_near(out):
    n = len(out)
    ln = np.linalg.norm(out, axis=1)
    bad = ln < 1e-12
    if bad.any():                                  # a point on a piece of length 0: the nearest direction
        good = np.where(~bad)[0]
        if not len(good):
            out[:] = (0.0, 0.0, 1.0)
            return out
        idx = good[np.clip(np.searchsorted(good, np.arange(n)), 0, len(good) - 1)]
        out[bad] = out[idx[bad]]
        ln = np.linalg.norm(out, axis=1)
    return out / ln[:, None]


def _tangents_far(p, min_len: float) -> np.ndarray:
    """``tangents`` with the pieces on each side summing up to at least ``min_len`` (or reaching the line's end)."""
    n = len(p)
    cum = chords(p)
    back = np.clip(np.searchsorted(cum, cum - min_len, side="right") - 1, 0, n - 1)
    ahead = np.clip(np.searchsorted(cum, cum + min_len, side="left"), 0, n - 1)
    out = np.zeros((n, 3))
    for j in (back, ahead):
        v = (p[j] - p) if j is ahead else (p - p[j])
        ln = np.linalg.norm(v, axis=1)
        out += np.where(ln[:, None] > 1e-12, v / np.maximum(ln, 1e-300)[:, None], 0.0)
    return _unit_or_near(out)


def _rotate(v, a, b):
    """``v`` turned by the smallest turn that takes unit ``a`` to unit ``b``."""
    ax = np.cross(a, b)
    s = float(np.linalg.norm(ax))
    c = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if s < 1e-12:
        return v
    k = ax / s
    ang = math.atan2(s, c)
    return v * math.cos(ang) + np.cross(k, v) * math.sin(ang) + k * np.dot(k, v) * (1.0 - math.cos(ang))


def transport(t, n0) -> np.ndarray:
    """The ring's turn along the line: ``n0`` (square to ``t[0]``) carried from point to point by the smallest turn
    between the tangents (Blender's minimum-twist normals of a curve that is not closed)."""
    t = np.asarray(t, np.float64)
    out = np.zeros_like(t)
    v = np.asarray(n0, np.float64)
    v = v - t[0] * np.dot(v, t[0])
    v /= max(np.linalg.norm(v), 1e-300)
    out[0] = v
    for i in range(1, len(t)):
        v = _rotate(v, t[i - 1], t[i])
        v = v - t[i] * np.dot(v, t[i])
        v /= max(np.linalg.norm(v), 1e-300)
        out[i] = v
    return out


def transport_many(t, n0) -> np.ndarray:
    """``transport`` for K lines at once: ``t`` (K, n, 3) tangents, ``n0`` (K, 3) -> (K, n, 3)."""
    t = np.asarray(t, np.float64)
    out = np.zeros_like(t)
    v = np.asarray(n0, np.float64).copy()
    v -= t[:, 0] * (v * t[:, 0]).sum(axis=1, keepdims=True)
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-300)
    out[:, 0] = v
    for i in range(1, t.shape[1]):
        a, b = t[:, i - 1], t[:, i]
        ax = np.cross(a, b)
        sn = np.linalg.norm(ax, axis=1, keepdims=True)
        cs = np.clip((a * b).sum(axis=1, keepdims=True), -1.0, 1.0)
        k = ax / np.maximum(sn, 1e-300)
        ang = np.arctan2(sn, cs)
        r = v * np.cos(ang) + np.cross(k, v) * np.sin(ang) + k * (k * v).sum(axis=1, keepdims=True) * (1 - np.cos(ang))
        v = np.where(sn > 1e-12, r, v)
        v -= b * (v * b).sum(axis=1, keepdims=True)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-300)
        out[:, i] = v
    return out


def oct_encode(n) -> np.ndarray:
    """Unit vectors (…, 3) -> octahedral (…, 2) int16 (about 0.005° apart)."""
    n = np.asarray(n, np.float64)
    n = n / np.maximum(np.abs(n).sum(axis=-1, keepdims=True), 1e-300)
    x, y, z = n[..., 0], n[..., 1], n[..., 2]
    ox = np.where(z < 0, (1.0 - np.abs(y)) * np.where(x >= 0, 1.0, -1.0), x)
    oy = np.where(z < 0, (1.0 - np.abs(x)) * np.where(y >= 0, 1.0, -1.0), y)
    return np.clip(np.round(np.stack([ox, oy], axis=-1) * 32767.0), -32767, 32767).astype(np.int16)


def oct_decode(e) -> np.ndarray:
    """``oct_encode`` back: (…, 2) int16 -> unit (…, 3)."""
    e = np.asarray(e, np.float64) / 32767.0
    x, y = e[..., 0], e[..., 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    t = np.clip(-z, 0.0, None)
    x = x + np.where(x >= 0, -t, t)
    y = y + np.where(y >= 0, -t, t)
    v = np.stack([x, y, z], axis=-1)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-300)


def chords(p) -> np.ndarray:
    """Metres along a poly line from its first point (n)."""
    p = np.asarray(p, np.float64)
    if len(p) < 2:
        return np.zeros(len(p))
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])


# ---------------------------------------------------------------------------
# a piece moved as a whole
# ---------------------------------------------------------------------------

def spread(co, k: int = FIT) -> np.ndarray:
    """``k`` point indices far apart (the farthest from the middle, then each farthest from those before): a move
    fitted from them is as good as from all."""
    co = np.asarray(co, np.float64).reshape(-1, 3)
    if not len(co):
        return np.zeros(0, int)
    first = int(np.argmax(np.linalg.norm(co - co.mean(axis=0), axis=1)))
    out = [first]
    dist = np.linalg.norm(co - co[first], axis=1)
    for _ in range(1, min(k, len(co))):
        nxt = int(np.argmax(dist))
        if dist[nxt] <= 0.0:
            break
        out.append(nxt)
        dist = np.minimum(dist, np.linalg.norm(co - co[nxt], axis=1))
    if len(out) >= 3:                       # off the line through the first two, then off the plane of three
        a, b = co[out[0]], co[out[1]]
        ab = b - a
        lab = np.linalg.norm(ab)
        if lab > 0:
            off = np.linalg.norm(np.cross(co - a, ab / lab), axis=1)
            out[2] = int(np.argmax(off))
            if len(out) >= 4:
                nrm = np.cross(ab, co[out[2]] - a)
                ln = np.linalg.norm(nrm)
                if ln > 0:
                    out[3] = int(np.argmax(np.abs((co - a) @ (nrm / ln))))
    return np.array(sorted(set(out)), int)


def fit_rigid_many(a, b) -> np.ndarray:
    """``fit_rigid`` of points ``a`` (k, 3) onto each of ``b`` (F, k, 3): (F, 4, 4) moves."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    ca = a.mean(axis=0)
    cb = b.mean(axis=1)
    h = np.einsum("ki,fkj->fij", a - ca, b - cb[:, None])
    u, _s, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(np.einsum("fji,fkj->fik", vt, u)))
    d = np.where(d == 0, 1.0, d)
    dm = np.zeros((len(b), 3, 3))
    dm[:, 0, 0] = dm[:, 1, 1] = 1.0
    dm[:, 2, 2] = d
    r = np.einsum("fji,fjk,flk->fil", vt, dm, u)
    m = np.zeros((len(b), 4, 4))
    m[:, :3, :3] = r
    m[:, :3, 3] = cb - np.einsum("fij,j->fi", r, ca)
    m[:, 3, 3] = 1.0
    return m


def fit_rigid(a, b):
    """The move (4 x 4: turn + shift, no mirror) that takes points ``a`` (k, 3) closest to ``b``, and the largest
    distance left (Kabsch)."""
    a = np.asarray(a, np.float64).reshape(-1, 3)
    b = np.asarray(b, np.float64).reshape(-1, 3)
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    h = (a - ca).T @ (b - cb)
    u, _s, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T)) or 1.0
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = cb - r @ ca
    left = float(np.linalg.norm(a @ r.T + m[:3, 3] - b, axis=1).max()) if len(a) else 0.0
    return m, left


# ---------------------------------------------------------------------------
# which moments to keep
# ---------------------------------------------------------------------------

def thin(n: int, error) -> np.ndarray:
    """Kept moment indices of ``n``: the first, the last and, split at the worst, every moment that straight-line
    blending between its neighbours in the list cannot give. ``error(a, b, i)`` -> error / tolerance of the moments
    ``i`` blended between ``a`` and ``b`` (arrays of the same length; all segments of one level at once)."""
    if n <= 2:
        return np.arange(n)
    keep = np.zeros(n, bool)
    keep[[0, n - 1]] = True
    segs = np.array([[0, n - 1]])
    while len(segs):
        segs = segs[segs[:, 1] - segs[:, 0] >= 2]
        if not len(segs):
            break
        ln = segs[:, 1] - segs[:, 0] - 1
        sid = np.repeat(np.arange(len(segs)), ln)
        start = np.repeat(segs[:, 0], ln)
        first = np.concatenate([[0], np.cumsum(ln)[:-1]])
        i = start + 1 + (np.arange(len(sid)) - np.repeat(first, ln))
        err = np.asarray(error(start, np.repeat(segs[:, 1], ln), i), np.float64)
        worst = np.maximum.reduceat(err, first)
        bad = worst > 1.0
        if not bad.any():
            break
        order = np.lexsort((-err, sid))                  # per segment, its worst moment first
        top = order[np.concatenate([[0], np.cumsum(ln)[:-1]])]
        cut = i[top][bad]
        keep[cut] = True
        segs = np.concatenate([np.c_[segs[bad, 0], cut], np.c_[cut, segs[bad, 1]]])
    return np.where(keep)[0]


def _weights(tm, a, b, i):
    span = tm[b] - tm[a]
    return np.where(span > 0, (tm[i] - tm[a]) / np.where(span > 0, span, 1.0), 0.0)


def thin_frames(x, tol: float, frames: np.ndarray | None = None) -> np.ndarray:
    """Kept moments of ``x`` (F, n, 3) or (F, n): each kept point lies within ``tol`` of the straight blend of its
    kept neighbours. ``frames``: the moments' times (blending by time; default 0, 1, 2 …)."""
    x = np.asarray(x, np.float32)
    f = len(x)
    x = x.reshape(f, -1, x.shape[-1] if x.ndim == 3 else 1)
    tm = np.arange(f, dtype=np.float64) if frames is None else np.asarray(frames, np.float64)
    tol = max(float(tol), 1e-12)

    def error(a, b, i):
        out = np.empty(len(i))
        w_all = _weights(tm, a, b, i)
        for s in range(0, len(i), CHUNK):
            e = slice(s, s + CHUNK)
            w = w_all[e][:, None, None]
            d = x[i[e]].astype(np.float64) - (x[a[e]] * (1.0 - w) + x[b[e]] * w)
            out[e] = np.sqrt((d * d).sum(axis=2)).max(axis=1)
        return out / tol

    return thin(f, error)


def _qnorm(q):
    return q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-300)


def slerp(qa, qb, w):
    """Quaternions (x, y, z, w) blended the short way (as three.js plays a rotation track); ``qa``, ``qb`` (4,) or
    (m, 4) each, ``w`` (m,)."""
    qa = np.atleast_2d(np.asarray(qa, np.float64))
    qb = np.atleast_2d(np.asarray(qb, np.float64)).copy()
    w = np.asarray(w, np.float64).reshape(-1, 1)
    d = (qa * qb).sum(axis=1, keepdims=True)
    qb = np.where(d < 0.0, -qb, qb)
    d = np.abs(d)
    th = np.arccos(np.clip(d, -1.0, 1.0))
    sn = np.sin(th)
    near = d > 0.9995
    safe = np.where(near, 1.0, sn)
    out = np.where(near, qa * (1.0 - w) + qb * w,
                   (np.sin((1.0 - w) * th) * qa + np.sin(w * th) * qb) / safe)
    return _qnorm(out)


def thin_node(t, q, s=None, reach: float = 1.0, tol: float = NODE_TOL, frames=None) -> np.ndarray:
    """Kept moments of a moving part's track: translation ``t`` (F, 3), rotation ``q`` (F, 4, x y z w) and scale
    ``s`` (F, 3) or None, blended as a viewer plays them (straight, short-way slerp, straight); ``reach`` = how far
    the part reaches from its own origin (a turn moves it that much more)."""
    t = np.asarray(t, np.float64)
    q = _qnorm(np.asarray(q, np.float64))
    s = None if s is None else np.asarray(s, np.float64)
    f = len(t)
    tm = np.arange(f, dtype=np.float64) if frames is None else np.asarray(frames, np.float64)
    reach = max(float(reach), 1e-6)
    tol = max(float(tol), 1e-12)

    def error(a, b, i):
        w = _weights(tm, a, b, i)[:, None]
        err = np.linalg.norm(t[i] - (t[a] * (1 - w) + t[b] * w), axis=1)
        qq = slerp(q[a], q[b], w[:, 0])
        dot = np.abs((qq * q[i]).sum(axis=1))
        err = np.maximum(err, 2.0 * np.arccos(np.clip(dot, -1.0, 1.0)) * reach)
        if s is not None:
            err = np.maximum(err, np.abs(s[i] - (s[a] * (1 - w) + s[b] * w)).max(axis=1) * reach)
        return err / tol

    return thin(f, error)


# ---------------------------------------------------------------------------
# into the file
# ---------------------------------------------------------------------------

def pack(points, s=None, max_step: float | None = None):
    """Kept centre lines (K, n, 3) and, when given, the lengths along the cable (K, n) -> (lo (n, 3) float32, step
    (n,) float32, slo (n,) float32 or None, sstep (n,) or None, q (K, n, 4) uint16 or None when K == 1). Each point
    has its own range over time (a point that hardly moves keeps micrometres); the page works out ``lo + step * q``
    (and ``slo + sstep * q[3]``). Moment after moment (key-major): meshopt packs that tighter."""
    p = np.asarray(points, np.float64)
    k, n = p.shape[:2]
    sa = None if s is None else np.asarray(s, np.float64)
    if k == 1:
        return (p[0].astype(np.float32), np.zeros(n, np.float32), None if sa is None else sa[0].astype(np.float32),
                None if sa is None else np.zeros(n, np.float32), None)

    def ranged(v, lo):
        step = (v.max(axis=0) - lo.astype(np.float64)) / 65535.0
        if step.ndim > 1:
            step = step.max(axis=1)
        return np.where(step > 0.0, step, 0.0).astype(np.float32)

    lo = p.min(axis=0).astype(np.float32)
    step = ranged(p, lo)
    if max_step is not None and float(step.max()) > max_step:
        # a point travels too far for 16 bits within the tolerance (over ~65 m): 32-bit numbers, step 1
        q = np.zeros((k, n, 4), np.float32)
        q[..., :3] = p - lo.astype(np.float64)[None]
        slo = sstep = None
        if sa is not None:
            slo = sa.min(axis=0).astype(np.float32)
            sstep = np.ones(n, np.float32)
            q[..., 3] = sa - slo.astype(np.float64)[None]
        return lo, np.ones(n, np.float32), slo, sstep, q
    q = np.zeros((k, n, 4), np.uint16)
    safe = np.where(step > 0.0, step.astype(np.float64), 1.0)
    q[..., :3] = np.clip(np.round((p - lo.astype(np.float64)[None]) / safe[None, :, None]), 0, 65535)
    slo = sstep = None
    if sa is not None:
        slo = sa.min(axis=0).astype(np.float32)
        sstep = ranged(sa, slo)
        ssafe = np.where(sstep > 0.0, sstep.astype(np.float64), 1.0)
        q[..., 3] = np.clip(np.round((sa - slo.astype(np.float64)[None]) / ssafe[None]), 0, 65535)
    return lo, step, slo, sstep, q


def unpack(lo, step, q, k: int) -> np.ndarray:
    """``pack``'s points back: (K, n, 3) float64."""
    lo = np.asarray(lo, np.float64).reshape(-1, 3)
    if q is None or k == 1:
        return lo[None]
    q = np.asarray(q, np.float64).reshape(k, len(lo), 4)
    return lo[None] + np.asarray(step, np.float64).reshape(-1)[None, :, None] * q[..., :3]


def unpack_s(slo, sstep, q, k: int) -> np.ndarray:
    """``pack``'s lengths along the cable back: (K, n)."""
    slo = np.asarray(slo, np.float64).reshape(-1)
    if q is None or k == 1:
        return slo[None]
    q = np.asarray(q, np.float64).reshape(k, len(slo), 4)
    return slo[None] + np.asarray(sstep, np.float64).reshape(-1)[None] * q[..., 3]


def blend_at(times, values, t: float):
    """Straight blend of (K, …) ``values`` at time ``t`` (held before the first and after the last)."""
    times = np.asarray(times, np.float64)
    values = np.asarray(values, np.float64)
    if len(times) == 1 or t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    k = int(np.searchsorted(times, t, side="right")) - 1
    w = (t - times[k]) / max(times[k + 1] - times[k], 1e-12)
    a, b = values[k], values[k + 1]
    return np.where(a == b, a, a * (1.0 - w) + b * w)          # equal moments: exactly that value


def _point_at(p, s, x):
    """The point at length ``x`` along (p, s) and the piece's direction there."""
    j = int(np.clip(np.searchsorted(s, x, side="right") - 1, 0, len(s) - 2))
    ln = s[j + 1] - s[j]
    w = 0.0 if ln <= 0 else (x - s[j]) / ln
    d = p[j + 1] - p[j]
    return p[j] * (1 - w) + p[j + 1] * w, j, w, d


def trimmed(p, s, lo: float, hi: float):
    """The part of a poly line (p, s) a spool draws between lengths lo and hi, as ``spool._build_tree`` cuts it: a
    point is dropped when it lies before lo or when its piece starts past hi; a kept point past hi is moved back
    along its piece onto hi (the rope ends exactly there, and starts at a point of the wound path). (points,
    lengths): none or one point when the spool holds nothing or a cut inside one piece (the app then draws nothing
    either)."""
    p = np.asarray(p, np.float64)
    s = np.asarray(s, np.float64)
    prev = np.concatenate([s[:1], s[:-1]])
    eps = CUT_EPS * max(1.0, abs(lo), abs(hi))                 # (a cut on a point of the path keeps that point)
    keep = ~((s < lo - eps) | (prev > hi + eps))
    idx = np.where(keep)[0]
    pts = p[idx].copy()
    ss = s[idx].copy()
    past = ss > hi
    for k in np.where(past)[0]:
        i = idx[k]
        j = max(i - 1, 0)
        ln = s[i] - s[j]
        w = 0.0 if ln <= 1e-9 else min(1.0, max(0.0, (hi - s[j]) / ln))
        pts[k] = p[j] * (1.0 - w) + p[i] * w
        ss[k] = hi
    return pts, ss


def at(spec: dict, arrays: dict, t: float) -> dict:
    """What the page draws at time ``t`` (seconds from the animation's start): {"points" (m, 3), "normals" (m, 3),
    "tangents", "s" (m,), "pay"} in the part's own coordinates. ``arrays``: the accessors of ``spec`` read back
    ({"times", "lo", "step", "q", "n0", "s0", "pay_t", "pay", "trim_t", "trim", "s"} as present)."""
    k = int(spec.get("k", 1))
    pts = unpack(arrays["lo"], arrays.get("step"), arrays.get("q"), k)
    times = arrays.get("times")
    if times is None or k == 1:
        times = np.zeros(1)
    p = blend_at(times, pts, t)
    n0 = blend_at(times, np.asarray(arrays["n0"], np.float64).reshape(-1, 3), t)
    s0 = float(blend_at(times, np.asarray(arrays["s0"], np.float64).reshape(-1), t))
    unit = float(spec.get("unit", 1.0))
    if arrays.get("s") is not None:
        s = np.asarray(arrays["s"], np.float64)
    elif arrays.get("slo") is not None:
        sk = unpack_s(arrays["slo"], arrays.get("sstep"), arrays.get("q"), k)
        s = blend_at(times, sk, t)
    else:
        s = s0 + chords(p) * unit
    if arrays.get("trim") is not None:
        tt = arrays.get("trim_t")
        tr = blend_at(np.zeros(1) if tt is None else tt, np.asarray(arrays["trim"], np.float64).reshape(-1, 2), t)
        p, s = trimmed(p, s, float(tr[0]), float(tr[1]))
        if arrays.get("trim_n0") is not None:
            n0 = blend_at(np.zeros(1) if tt is None else tt, np.asarray(arrays["trim_n0"], np.float64).reshape(-1, 3), t)
    tg = tangents(p, float(spec.get("tmin", 0.0)))
    if len(p) == 0:
        nr = np.zeros((0, 3))
    elif arrays.get("nq") is not None:            # the app's own ring turns (a line the page cannot carry them along)
        nk = oct_decode(np.asarray(arrays["nq"]).reshape(k, -1, 2))
        nr = blend_at(times, nk, t)
        nr = nr - tg * (nr * tg).sum(axis=1, keepdims=True)
        nr /= np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-300)
    else:
        nr = transport(tg, n0)
    pay = 0.0
    if arrays.get("pay") is not None:
        pt = arrays.get("pay_t")
        pay = float(blend_at(np.zeros(1) if pt is None else pt, np.asarray(arrays["pay"], np.float64).reshape(-1), t))
    elif spec.get("pay") is not None and not isinstance(spec.get("pay"), dict):
        pay = float(spec["pay"])
    return {"points": p, "normals": nr, "tangents": tg, "s": s, "pay": pay}


def look_for_page(kind: str, look, d: dict, srgb_to_linear, served: dict | None = None) -> dict:
    """The numbers the page's cable look needs: ``kind`` "POWER" | "ROPE" | "SERVED", ``look`` the object's
    ``fr_cable_look`` (4 numbers or None), ``d`` the look's settings (``cable_looks.defaults``). Served cable (task
    0158): ``served`` = ``cable_looks._served(...)`` of the object, with ``yarn_rgb`` / ``band_rgb`` (linear, or None:
    the library's)."""
    lin = lambda c: [round(float(srgb_to_linear(v)), 6) for v in c[:3]]   # noqa: E731
    if kind == "SERVED":
        v = served or {}
        rgb = lambda key, lib: ([round(float(c), 6) for c in v[key][:3]] if v.get(key) else lin(d[lib]))  # noqa: E731
        return {"kind": "SERVED", "pitch": float(v.get("distance", d["pitch"])),
                "width": float(v.get("width", d["width"])), "count": int(v.get("count", d["count"])),
                "gap": float(v.get("gap", d["gap"])), "yarn_pitch": float(v.get("yarn_pitch", d["yarn_pitch"])),
                "yarn_starts": int(v.get("starts", 0)), "radius": float(v.get("radius", 0.5 * d["diameter"])),
                "wear": float(v.get("wear", d["wear"])), "band_wear": float(v.get("band_wear", d["band_wear"])),
                "yarn": rgb("yarn_rgb", "yarn"), "band": rgb("band_rgb", "band"), "dust": lin(d["dust"]),
                "variation": float(d["variation"]), "fibres": float(d["fibres"]), "rag": float(d["rag"]),
                "strand_height": float(d["strand_height"]), "bump": float(d["bump"]),
                "yarn_rough": float(d["yarn_roughness"]), "paint_rough": float(d["paint_roughness"])}
    pitch, starts, width = float(d["pitch"]), int(d["starts"]), float(d.get("width", 0.0))
    if look is not None and len(look) >= 3 and float(look[0]) > 1e-6:
        pitch = float(look[0])
        starts = int(math.floor(float(look[1]) + 0.5))
        width = min(1.0, max(0.0, float(look[2])))
    if kind == "ROPE":
        return {"kind": "ROPE", "pitch": pitch, "starts": starts, "wires": float(d["wires"]),
                "slant": float(d["slant"]), "grease": lin(d["grease"]), "grease_amount": float(d["grease_amount"]),
                "grease_metallic": float(d["grease_metallic"]), "grease_rough": float(d["grease_roughness"]),
                "wire_dark": float(d["wire_dark"]), "strand_radius": float(d["strand_radius"]),
                "wire_height": float(d["wire_height"]), "bump": float(d["bump"])}
    return {"kind": "POWER", "pitch": pitch, "starts": starts, "width": width, "stripe": lin(d["stripe"]),
            "stripe_rough": float(d["stripe_roughness"]), "edge": float(d["edge"])}
