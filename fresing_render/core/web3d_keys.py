"""Smaller animation in the web 3D file (task 0175, study 0149 rank 1), no Blender.

Every moving part of a web export has a place per frame (translation, rotation, scale). Here:

* ``node_track``: which moments a part keeps and how its numbers are written, so that what three.js plays between
  the kept moments stays within ``POS_TOL`` (0.1 mm) of the place, ``ANGLE_TOL`` (0.05°) of the turn and ``NODE_TOL``
  (1 mm) at the far end of the part (a long part turning: its far end moves the most) – at **every** frame of the
  animation, checked with the numbers as the file holds them (16-bit rotations, translations on a fixed grid).
  A part whose place or turn never changes gets no track for it (its node holds the value); a part that is only
  shown and hidden gets a key only where that changes.
* ``played``: what three.js r180 plays at a time from such keys (``QuaternionLinearInterpolant`` = its
  ``slerpFlat``, ``Object3D.updateMatrix`` = its ``compose``) – the tests' reference and the error measure.
* meshopt **filters** (``EXT_meshopt_compression``): ``exp_encode`` / ``exp_decode`` (EXPONENTIAL: each number as a
  24-bit whole number times a power of two – one power per column, so the fixed grid packs tightly) and
  ``quat_encode`` / ``quat_decode`` (QUATERNION: three 16-bit components and which one was left out). Both in NumPy,
  bit for bit as meshopt's decoder in the page (``tests/test_web3d_keys.py`` compares with Blender's own meshopt
  library where it is there).

Units: metres, seconds, quaternions (x, y, z, w) as glTF stores them.
"""

from __future__ import annotations

import math

import numpy as np

POS_TOL = 1e-4                      # m: a part's place between kept moments (0149: 0.1 mm)
ANGLE_TOL = math.radians(0.05)      # its turn (0149: 0.05°)
NODE_TOL = 1e-3                     # m: at the far end of the part (0142's rule, kept for long parts)
STILL = 1e-6                        # a track whose numbers never move more than this is left out
EXP_STEP = -16                      # translations on a grid of 2^-16 m (0.015 mm) while they fit in 24 bits
EXP_TIME = -20                      # times on a grid of 2^-20 s (about 1 µs)
Q16 = 32767.0


# ---------------------------------------------------------------------------
# what three.js plays
# ---------------------------------------------------------------------------

def slerp_flat(qa, qb, w) -> np.ndarray:
    """three.js ``Quaternion.slerpFlat`` for rows ``qa``, ``qb`` (m, 4) and weights ``w`` (m,), float64. Like three:
    the inputs are used as they are (not made unit first); only the near-straight case is made unit again."""
    qa = np.asarray(qa, np.float64)
    qb = np.asarray(qb, np.float64)
    w = np.asarray(w, np.float64).reshape(-1)
    cos = (qa * qb).sum(axis=1)
    dirn = np.where(cos >= 0.0, 1.0, -1.0)
    sqr_sin = 1.0 - cos * cos
    s = 1.0 - w
    t = w.copy()
    big = sqr_sin > np.finfo(np.float64).eps
    sn = np.sqrt(np.where(big, sqr_sin, 1.0))
    ln = np.arctan2(sn, cos * dirn)
    s = np.where(big, np.sin(s * ln) / sn, s)
    t = np.where(big, np.sin(t * ln) / sn, t)
    out = qa * s[:, None] + qb * (t * dirn)[:, None]
    lerp = ~big
    if lerp.any():
        out[lerp] /= np.linalg.norm(out[lerp], axis=1, keepdims=True)
    same = (qa == qb).all(axis=1) | (w == 0.0)
    out[same] = qa[same]
    out[w == 1.0] = qb[w == 1.0]
    return out


def rot_matrix(q) -> np.ndarray:
    """three.js ``Matrix4.compose``'s 3 x 3 part of quaternions (m, 4): the unit formula, also for a quaternion that
    is not quite unit (as 16-bit numbers give)."""
    q = np.asarray(q, np.float64)
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    return np.stack([np.stack([1 - (yy + zz), xy - wz, xz + wy], -1),
                     np.stack([xy + wz, 1 - (xx + zz), yz - wx], -1),
                     np.stack([xz - wy, yz + wx, 1 - (xx + yy)], -1)], -2)


def _interval(times, keys_t, at):
    """For each time ``at``: the kept moment before (index into ``keys_t``) and the weight to the next."""
    keys_t = np.asarray(keys_t, np.float64)
    at = np.asarray(at, np.float64)
    if len(keys_t) == 1:
        return np.zeros(len(at), int), np.zeros(len(at))
    i = np.clip(np.searchsorted(keys_t, at, side="right") - 1, 0, len(keys_t) - 2)
    span = keys_t[i + 1] - keys_t[i]
    w = np.clip((at - keys_t[i]) / np.where(span > 0, span, 1.0), 0.0, 1.0)
    return i, w


def played(keys_t, values, at, path: str) -> np.ndarray:
    """What three.js plays of a LINEAR track (``keys_t``, ``values`` as the file holds them, after its normalising)
    at the times ``at``: (m, 3) for a translation or scale, (m, 4) for a rotation."""
    v = np.asarray(values, np.float64)
    i, w = _interval(None, keys_t, at)
    if len(v) == 1:
        return np.repeat(v, len(w), axis=0)
    if path == "rotation":
        return slerp_flat(v[i], v[i + 1], w)
    return v[i] * (1.0 - w)[:, None] + v[i + 1] * w[:, None]


def turn_error(p, q) -> tuple[np.ndarray, np.ndarray]:
    """(angle in radians, the largest change of the 3 x 3 matrix) between played ``p`` and true unit ``q`` (m, 4).
    The second is what a point 1 m from the origin moves by (also when ``p`` is not quite unit)."""
    pn = p / np.maximum(np.linalg.norm(p, axis=1, keepdims=True), 1e-300)
    dot = np.abs((pn * q).sum(axis=1))
    ang = 2.0 * np.arccos(np.clip(dot, -1.0, 1.0))
    d = rot_matrix(p) - rot_matrix(q)
    return ang, np.sqrt((d * d).sum(axis=(1, 2)))


# ---------------------------------------------------------------------------
# numbers as the file holds them
# ---------------------------------------------------------------------------

def unit(q) -> np.ndarray:
    """Quaternions made unit and on one side (each one the short way from the one before, as Blender's turns were
    read: q and -q are the same turn)."""
    q = np.asarray(q, np.float64)
    q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-300)
    if len(q) > 1:
        flip = np.cumsum((q[1:] * q[:-1]).sum(axis=1) < 0) % 2
        q[1:][flip == 1] *= -1.0
    return q


def short_rot(q) -> np.ndarray:
    """Unit quaternions -> the normalised 16-bit numbers the file holds (int16 (m, 4))."""
    return np.clip(np.round(np.asarray(q, np.float64) * Q16), -32767, 32767).astype(np.int16)


def read_short(s) -> np.ndarray:
    """glTF's reading of normalised 16-bit numbers: max(c / 32767, -1)."""
    return np.maximum(np.asarray(s, np.float64) / Q16, -1.0)


def exp_exponent(values, step: int = EXP_STEP, big: float = 0.0) -> np.ndarray:
    """The power of two per column of ``values`` (m, n): ``step``, or as much coarser as the column's largest number
    (or ``big``) needs to fit 24 bits."""
    v = np.abs(np.asarray(values, np.float64))
    big = np.maximum(v.max(axis=0) if len(v) else np.zeros(v.shape[1]), abs(float(big)))
    e = np.full(big.shape, int(step), np.int64)
    over = big > (2 ** 23 - 1) * np.exp2(e.astype(np.float64))
    if over.any():
        need = np.ceil(np.log2(np.maximum(big[over], 1e-300) / (2 ** 23 - 1)))
        e[over] = np.maximum(e[over], need.astype(np.int64))
    return np.clip(e, -100, 100)


def exp_encode(values, step: int = EXP_STEP, big: float = 0.0) -> np.ndarray:
    """EXPONENTIAL filter: (m, n) numbers -> (m, n) uint32 (top byte the power of two, the rest a 24-bit whole
    number). One power per column: neighbouring rows differ only in the low bytes, which meshopt packs."""
    v = np.asarray(values, np.float64)
    if v.ndim == 1:
        v = v[:, None]
    e = exp_exponent(v, step, big)
    m = np.clip(np.round(v / np.exp2(e.astype(np.float64))[None]), -(2 ** 23), 2 ** 23 - 1).astype(np.int64)
    return ((m & 0xFFFFFF) | ((e[None] & 0xFF) << 24)).astype(np.uint32)


def exp_decode(u) -> np.ndarray:
    """meshopt's EXPONENTIAL decode, as the page does it: float32 (m, n)."""
    u = np.asarray(u, np.uint32)
    m = (u.astype(np.int64) << 40).astype(np.int64) >> 40           # bits 0-23 as a signed number
    e = (u.view(np.int32).astype(np.int64) >> 24)
    scale = ((e + 127).astype(np.uint32) << 23).view(np.float32)
    return (m.astype(np.float32) * scale).astype(np.float32)


def quat_encode(q, bits: int = 16) -> np.ndarray:
    """QUATERNION filter (meshopt's ``encodeFilterQuat``): unit quaternions (m, 4) -> int16 (m, 4)."""
    q = np.asarray(q, np.float32)
    qc = np.argmax(np.abs(q), axis=1)
    rows = np.arange(len(q))
    sign = np.where(q[rows, qc] < 0, -1.0, 1.0).astype(np.float32)
    scaler = np.float32(math.sqrt(2.0))
    lim = (1 << (bits - 1)) - 1
    out = np.zeros((len(q), 4), np.int16)
    for j in range(3):
        c = q[rows, (qc + 1 + j) & 3] * scaler * sign
        out[:, j] = _snorm(c, lim)
    out[:, 3] = (np.int32(_snorm(np.float32(1.0), lim)) & ~3) | qc
    return out


def _snorm(v, lim: int):
    """meshopt_quantizeSnorm: round(v * lim) with v clamped to [-1, 1], halves away from zero."""
    v = np.clip(np.asarray(v, np.float32), -1.0, 1.0) * np.float32(lim)
    return (v + np.where(v >= 0, np.float32(0.5), np.float32(-0.5))).astype(np.int32)


def quat_decode(d) -> np.ndarray:
    """meshopt's QUATERNION decode, as the page does it: int16 (m, 4) -> the normalised 16-bit quaternions
    (int16 (m, 4)) the accessor then holds."""
    d = np.asarray(d, np.int16).astype(np.int32)
    sf = (d[:, 3] | 3).astype(np.float32)
    ss = np.float32(1.0 / math.sqrt(2.0)) / sf
    x, y, z = (d[:, k].astype(np.float32) * ss for k in range(3))
    ww = np.float32(1.0) - x * x - y * y - z * z
    w = np.sqrt(np.maximum(ww, np.float32(0.0)))
    qc = d[:, 3] & 3
    out = np.zeros((len(d), 4), np.int16)
    rows = np.arange(len(d))
    for c, off in ((x, 1), (y, 2), (z, 3), (w, 0)):
        f = c * np.float32(Q16)
        out[rows, (qc + off) & 3] = (f + np.where(f >= 0, np.float32(0.5), np.float32(-0.5))).astype(np.int32)
    return out


def file_times(times, packed: bool, end: float | None = None) -> np.ndarray:
    """Times as the file holds them (float32 values): on the EXPONENTIAL grid in a compressed file (one grid for the
    whole animation: its fineness from ``end``, the animation's last time, default the last of ``times``), else
    float32. ``Gltf.animation`` writes them so; the keys are chosen and checked with them."""
    tm = np.asarray(times, np.float64)
    if packed and len(tm):
        return exp_decode(exp_encode(tm[:, None], EXP_TIME, tm.max() if end is None else end))[:, 0]
    return tm.astype(np.float32)


# ---------------------------------------------------------------------------
# which moments to keep
# ---------------------------------------------------------------------------

def thin(n: int, error) -> np.ndarray:
    """``web3d_tubes.thin``: the first, the last and, split at the worst moment, every moment that blending between
    its kept neighbours cannot give (``error`` <= 1)."""
    from .web3d_tubes import thin as _thin
    return _thin(n, error)


class Track:
    """A moving part's kept moments: ``keys`` (indices into the frames), and per path ("translation", "rotation",
    "scale") the values as the file holds them (``file``) and as the page reads them back (``read``), or no entry
    when that path never changes. ``rot16``: rotations as 16-bit numbers (else float32, a part too long for them).
    ``error`` (filled by ``check``): the largest (place m, turn rad, far end m) over every frame."""

    def __init__(self):
        self.keys = np.zeros(0, int)
        self.paths: dict = {}
        self.rot16 = False
        self.error = (0.0, 0.0, 0.0)
        self.packed = True

    def how(self, path: str) -> str:
        if path == "rotation" and self.rot16:
            return "quat" if self.packed else "short"
        if path == "translation" and self.packed:
            return "exp"
        return ""


def node_track(t, q, s=None, reach: float = 1.0, frames=None, packed: bool = True, pos_tol: float = POS_TOL,
               angle_tol: float = ANGLE_TOL, node_tol: float = NODE_TOL) -> Track:
    """The track of one moving part: ``t`` (F, 3), ``q`` (F, 4), ``s`` (F, 3) or None (scale never changes),
    ``reach`` (m from its origin), ``frames`` (F,) seconds. ``packed``: translations on the EXPONENTIAL grid
    (a compressed file), else float32. The kept moments hold every frame within the tolerances as played."""
    t = np.asarray(t, np.float64)
    q = unit(q)
    f = len(t)
    tm = np.arange(f, dtype=np.float64) if frames is None else np.asarray(frames, np.float64)
    tk = file_times(tm, packed).astype(np.float64)       # the keys' times as the page reads them
    reach = max(float(reach), 1e-6)
    tr = Track()
    tr.packed = bool(packed)
    moves_t = f > 1 and float(np.abs(t - t[:1]).max()) > STILL
    moves_q = f > 1 and float(np.abs(q - q[:1]).max()) > STILL
    moves_s = s is not None and f > 1 and float(np.abs(np.asarray(s) - np.asarray(s)[:1]).max()) > STILL
    # as the file will hold them
    tf = exp_decode(exp_encode(t)).astype(np.float64) if packed else t.astype(np.float32).astype(np.float64)
    if packed:                                  # QUATERNION filter: what the page reads back
        qfile = quat_encode(q)
        q16 = read_short(quat_decode(qfile))
    else:
        qfile = short_rot(q)
        q16 = read_short(qfile)
    _ang, dist = turn_error(q16, q)
    tr.rot16 = bool((dist * reach).max(initial=0.0) <= 0.25 * node_tol)
    qf = q16 if tr.rot16 else q.astype(np.float32).astype(np.float64)
    sv = None if s is None else np.asarray(s, np.float64)
    sf = None if sv is None else sv.astype(np.float32).astype(np.float64)

    def error(a, b, i):
        w = np.clip(np.where(tk[b] > tk[a], (tm[i] - tk[a]) / np.where(tk[b] > tk[a], tk[b] - tk[a], 1.0), 0.0),
                    0.0, 1.0)
        err = np.zeros(len(i))
        if moves_t:
            e = np.linalg.norm(tf[a] * (1 - w)[:, None] + tf[b] * w[:, None] - t[i], axis=1)
            err = np.maximum(err, e / pos_tol)
        if moves_q:
            ang, dd = turn_error(slerp_flat(qf[a], qf[b], w), q[i])
            err = np.maximum(err, np.maximum(ang / angle_tol, dd * reach / node_tol))
        if moves_s:
            e = np.abs(sf[a] * (1 - w)[:, None] + sf[b] * w[:, None] - sv[i]).max(axis=1) * reach
            err = np.maximum(err, e / node_tol)
        return err

    if not (moves_t or moves_q or moves_s):
        tr.keys = np.zeros(0, int)
        return tr
    tr.keys = thin(f, error)
    k = tr.keys
    if moves_t:
        tr.paths["translation"] = (exp_encode(t[k]) if packed else t[k].astype(np.float32), tf[k])
    if moves_q:
        tr.paths["rotation"] = (qfile[k] if tr.rot16 else q[k].astype(np.float32), qf[k])
    if moves_s:
        tr.paths["scale"] = (sv[k].astype(np.float32), sf[k])
    return tr


def check(tr: Track, t, q, s=None, reach: float = 1.0, frames=None, packed: bool | None = None
          ) -> tuple[float, float, float]:
    """The largest (place m, turn rad, far end m) between what ``tr`` plays and the true place at every frame (the
    tests' bound). A path without a track is held at the first frame's value."""
    t = np.asarray(t, np.float64)
    q = unit(q)
    f = len(t)
    tm = np.arange(f, dtype=np.float64) if frames is None else np.asarray(frames, np.float64)
    tk = file_times(tm, tr.packed if packed is None else packed).astype(np.float64)
    kt = tk[tr.keys] if len(tr.keys) else tk[:1]
    pt = played(kt, tr.paths["translation"][1], tm, "translation") if "translation" in tr.paths else \
        np.repeat(t[:1], f, axis=0)
    pq = played(kt, tr.paths["rotation"][1], tm, "rotation") if "rotation" in tr.paths else \
        np.repeat(q[:1], f, axis=0)
    ang, dd = turn_error(pq, q)
    far = dd * reach
    if s is not None:
        sv = np.asarray(s, np.float64)
        ps = played(kt, tr.paths["scale"][1], tm, "scale") if "scale" in tr.paths else np.repeat(sv[:1], f, axis=0)
        far = np.maximum(far, np.abs(ps - sv).max(axis=1) * reach)
    tr.error = (float(np.linalg.norm(pt - t, axis=1).max()), float(ang.max()), float(far.max()))
    return tr.error


def changes(shown) -> np.ndarray:
    """Kept moments of a shown / hidden (STEP) track: the first, every moment it changes and the last."""
    v = np.asarray(shown, bool)
    if not len(v):
        return np.zeros(0, int)
    k = np.concatenate([[0], np.where(v[1:] != v[:-1])[0] + 1, [len(v) - 1]])
    return np.unique(k)
