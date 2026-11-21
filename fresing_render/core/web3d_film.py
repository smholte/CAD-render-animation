"""Film on the web 3D page (task 0252), no Blender: the video's Animation camera as the page plays it.

The export reads the Animation camera at every frame of the page's motion (place, turn, field of view). Here:

* ``pose``: a Blender camera's world matrix -> its place and turn in the page's (three.js) world: x, z, -y, the
  camera's own axes as Blender's (both look along their -z, up along +y).
* ``encode``: the moments the page needs. The track is cut into runs at the video's **cuts** (a jump between two
  frames: never blended); in each run only the moments that blending between their kept neighbours cannot give are
  kept (straight for the place and the field of view, three.js ``slerpFlat`` for the turn) – checked with the numbers
  as the file holds them, at **every** frame: the place within ``pos_tol`` (0.25 mm per metre of the model, at least
  0.25 mm), the turn and the field of view within 0.02°. The numbers are written as whole numbers, each the step
  from the kept moment before (short JSON).
* ``decode`` / ``sample``: what the page reads back and plays at a time (``fr_page.js`` does the same) – the tests'
  reference.
* ``captions``: the video's captions (``core/brand.caption_list``) as seconds of the page's motion.

One film today (``kind`` "ANIMATION"); the page reads a list ``films`` so the turntable's and the product video's
cameras can follow (TASKS.md "Later").

Units: metres, seconds, degrees; quaternions (x, y, z, w) in the page's world.
"""

from __future__ import annotations

import json
import math

import numpy as np

from . import brand
from .web3d_keys import slerp_flat, thin, unit

POS_TOL_PER_M = 0.25e-3          # m of place per metre of the model's size (the brief: ~1 mm per metre)
POS_TOL_MIN = 0.25e-3            # m: never finer than this is asked for
ANGLE_TOL = math.radians(0.02)   # the turn
FOV_TOL = 0.02                   # degrees of the vertical field of view
Q_STEP = 1e-5                    # quaternion components as whole numbers of this
V_STEP = 1e-3                    # degrees of field of view as whole numbers of this
CUT_FACTOR = 6.0                 # a step this many times its neighbours' (and big) is a jump, when no cut list
B2T = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])
KIND_ANIMATION = "ANIMATION"


def pos_tol(size_m: float) -> float:
    return max(POS_TOL_MIN, POS_TOL_PER_M * max(float(size_m), 0.0))


def _quat_of(m: np.ndarray) -> np.ndarray:
    """Unit quaternions (x, y, z, w) of rotation matrices (n, 3, 3) (their scale taken off)."""
    m = np.asarray(m, np.float64)
    m = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-300)
    n = len(m)
    q = np.empty((n, 4))
    tr = m[:, 0, 0] + m[:, 1, 1] + m[:, 2, 2]
    for k in range(n):
        a = m[k]
        if tr[k] > 0:
            s = 0.5 / math.sqrt(tr[k] + 1.0)
            q[k] = [(a[2, 1] - a[1, 2]) * s, (a[0, 2] - a[2, 0]) * s, (a[1, 0] - a[0, 1]) * s, 0.25 / s]
        elif a[0, 0] > a[1, 1] and a[0, 0] > a[2, 2]:
            s = 2.0 * math.sqrt(1.0 + a[0, 0] - a[1, 1] - a[2, 2])
            q[k] = [0.25 * s, (a[0, 1] + a[1, 0]) / s, (a[0, 2] + a[2, 0]) / s, (a[2, 1] - a[1, 2]) / s]
        elif a[1, 1] > a[2, 2]:
            s = 2.0 * math.sqrt(1.0 + a[1, 1] - a[0, 0] - a[2, 2])
            q[k] = [(a[0, 1] + a[1, 0]) / s, 0.25 * s, (a[1, 2] + a[2, 1]) / s, (a[0, 2] - a[2, 0]) / s]
        else:
            s = 2.0 * math.sqrt(1.0 + a[2, 2] - a[0, 0] - a[1, 1])
            q[k] = [(a[0, 2] + a[2, 0]) / s, (a[1, 2] + a[2, 1]) / s, 0.25 * s, (a[1, 0] - a[0, 1]) / s]
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def pose(matrices) -> tuple[np.ndarray, np.ndarray]:
    """Blender world matrices (n, 4, 4) of a camera -> (place (n, 3), turn (n, 4)) in the page's world."""
    m = np.asarray(matrices, np.float64).reshape(-1, 4, 4)
    pos = m[:, :3, 3] @ B2T.T
    rot = np.einsum("ij,njk->nik", B2T, m[:, :3, :3])
    return pos, unit(_quat_of(rot))


def matrix_of(pos, quat) -> np.ndarray:
    """The page's place and turn -> Blender world matrices (n, 4, 4) (tests)."""
    from .web3d_keys import rot_matrix
    pos = np.asarray(pos, np.float64).reshape(-1, 3)
    q = np.asarray(quat, np.float64).reshape(-1, 4)
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    out = np.tile(np.eye(4), (len(pos), 1, 1))
    out[:, :3, :3] = np.einsum("ji,njk->nik", B2T, rot_matrix(q))
    out[:, :3, 3] = pos @ B2T
    return out


def fovs(vfov_deg, aspect: float):
    """The horizontal field of view (degrees) that goes with a vertical one for a picture of ``aspect`` (w / h)."""
    v = np.radians(np.asarray(vfov_deg, np.float64))
    return np.degrees(2.0 * np.arctan(np.tan(v / 2.0) * float(aspect)))


def find_cuts(pos, quat, vfov, size_m: float) -> list[int]:
    """Frames ``i`` where the camera jumps from frame ``i - 1`` (a cut), read from the numbers alone: a step far
    longer (or a turn far bigger) than the steps around it, and big. The export gives the video's own cuts instead
    (``Job``: the Cut steps); this is for a track without them."""
    pos = np.asarray(pos, np.float64)
    q = np.asarray(quat, np.float64)
    n = len(pos)
    if n < 3:
        return []
    d = np.linalg.norm(np.diff(pos, axis=0), axis=1) / max(float(size_m), 1e-6)
    a = 2.0 * np.arccos(np.clip(np.abs((q[1:] * q[:-1]).sum(axis=1)), 0.0, 1.0))
    v = np.abs(np.diff(np.asarray(vfov, np.float64))) / 10.0
    step = np.maximum(np.maximum(d, a), v)
    out = []
    for k in range(len(step)):
        around = [step[j] for j in (k - 1, k + 1) if 0 <= j < len(step)]
        if step[k] > 0.05 and step[k] > CUT_FACTOR * max(around + [1e-9]):
            out.append(k + 1)
    return out


def _runs(n: int, cuts) -> list[tuple[int, int]]:
    starts = [0] + sorted(c for c in set(int(c) for c in cuts) if 0 < c < n)
    return [(s, (starts[k + 1] - 1) if k + 1 < len(starts) else n - 1) for k, s in enumerate(starts)]


def _q_file(q) -> np.ndarray:
    return np.round(np.asarray(q, np.float64) / Q_STEP).astype(np.int64)


def _q_read(qi) -> np.ndarray:
    q = np.asarray(qi, np.float64) * Q_STEP
    return q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-300)


def encode(pos, quat, vfov, fps: float, aspect: float, size_m: float, cuts=(), name: str = "Animation camera",
           kind: str = KIND_ANIMATION) -> dict:
    """The film block of the page's settings from a camera's place (n, 3), turn (n, 4) and vertical field of view
    (n,) in degrees at every frame of the page's motion (frame k at k / ``fps`` s). ``cuts``: frames that jump from
    the frame before. ``aspect``: the render's width / height (the page fits that frame into its free area)."""
    pos = np.asarray(pos, np.float64).reshape(-1, 3)
    q = unit(np.asarray(quat, np.float64).reshape(-1, 4))
    v = np.asarray(vfov, np.float64).reshape(-1)
    n = len(pos)
    tol = pos_tol(size_m)
    ps = tol / 8.0
    pi = np.round(pos / ps).astype(np.int64)
    qi = _q_file(q)
    vi = np.round(v / V_STEP).astype(np.int64)
    pr, qr, vr = pi * ps, _q_read(qi), vi * V_STEP
    cuts = sorted(c for c in set(int(c) for c in cuts) if 0 < c < n)
    keys = []
    for s, e in _runs(n, cuts):
        m = e - s + 1
        sl = slice(s, e + 1)
        tp, tq, tv = pos[sl], q[sl], v[sl]
        fp, fq, fv = pr[sl], qr[sl], vr[sl]

        def error(a, b, i, tp=tp, tq=tq, tv=tv, fp=fp, fq=fq, fv=fv):
            w = ((i - a) / np.maximum(b - a, 1)).astype(np.float64)
            ep = np.linalg.norm(fp[a] * (1 - w)[:, None] + fp[b] * w[:, None] - tp[i], axis=1) / tol
            qq = slerp_flat(fq[a], fq[b], w)
            qq /= np.linalg.norm(qq, axis=1, keepdims=True)
            ea = 2.0 * np.arccos(np.clip(np.abs((qq * tq[i]).sum(axis=1)), 0.0, 1.0)) / ANGLE_TOL
            ev = np.abs(fv[a] * (1 - w) + fv[b] * w - tv[i]) / FOV_TOL
            return np.maximum(np.maximum(ep, ea), ev)

        keys.extend((thin(m, error) + s).tolist())
    keys = np.array(sorted(set(keys)), np.int64)

    def deltas(a):
        a = np.asarray(a, np.int64)
        return np.concatenate([a[:1], np.diff(a, axis=0)]).reshape(-1).tolist()

    return {"name": str(name), "kind": str(kind), "fps": float(fps), "n": int(n), "aspect": round(float(aspect), 6),
            "ps": ps, "k": deltas(keys), "p": deltas(pi[keys]), "q": deltas(qi[keys]), "v": deltas(vi[keys]),
            "cut": cuts}


def decode(film: dict) -> dict:
    """The film block -> {"keys" (frame numbers), "t" (s), "pos", "quat" (unit), "vfov", "cuts" (set), "fps", "n",
    "aspect", "duration"} as the page reads it."""
    k = np.cumsum(np.asarray(film["k"], np.int64))
    m = len(k)
    p = np.cumsum(np.asarray(film["p"], np.int64).reshape(m, 3), axis=0) * float(film["ps"])
    q = _q_read(np.cumsum(np.asarray(film["q"], np.int64).reshape(m, 4), axis=0))
    v = np.cumsum(np.asarray(film["v"], np.int64)) * V_STEP
    fps = float(film["fps"])
    return {"keys": k, "t": k / fps, "pos": p, "quat": q, "vfov": v, "cuts": set(int(c) for c in film.get("cut", [])),
            "fps": fps, "n": int(film["n"]), "aspect": float(film["aspect"]),
            "duration": (int(film["n"]) - 1) / fps}


def sample(dec: dict, t) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(place (m, 3), turn (m, 4), vertical fov (m,)) the page shows at the times ``t`` (s, within the motion):
    blended between kept moments, held before a cut until the cut's frame."""
    t = np.clip(np.atleast_1d(np.asarray(t, np.float64)), 0.0, dec["duration"])
    keys = dec["keys"]
    if len(keys) == 1:
        z = np.zeros(len(t), int)
        return dec["pos"][z], dec["quat"][z], dec["vfov"][z]
    x = t * dec["fps"]
    i = np.clip(np.searchsorted(keys, x, side="right") - 1, 0, len(keys) - 2)
    span = (keys[i + 1] - keys[i]).astype(np.float64)
    w = np.clip((x - keys[i]) / np.maximum(span, 1e-9), 0.0, 1.0)
    held = np.array([int(keys[j + 1]) in dec["cuts"] for j in i]) & (x < keys[i + 1])
    w = np.where(held, 0.0, w)
    p = dec["pos"][i] * (1 - w)[:, None] + dec["pos"][i + 1] * w[:, None]
    q = slerp_flat(dec["quat"][i], dec["quat"][i + 1], w)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    v = dec["vfov"][i] * (1 - w) + dec["vfov"][i + 1] * w
    return p, q, v


def errors(dec: dict, pos, quat, vfov) -> tuple[float, float, float]:
    """The largest (place m, turn degrees, fov degrees) between the film as played and the camera at every frame."""
    n = len(pos)
    p, q, v = sample(dec, np.arange(n) / dec["fps"])
    ep = float(np.linalg.norm(p - np.asarray(pos), axis=1).max())
    qt = unit(np.asarray(quat, np.float64))
    ea = float(np.degrees(2.0 * np.arccos(np.clip(np.abs((q * qt).sum(axis=1)), 0.0, 1.0))).max())
    ev = float(np.abs(v - np.asarray(vfov)).max())
    return ep, ea, ev


def size_bytes(block) -> int:
    """Bytes the block adds to the page's settings (compact JSON, as ``page_html`` writes it)."""
    return len(json.dumps(block, separators=(",", ":")).encode("utf-8"))


def captions(steps, fps: float, body_frames: int) -> list[dict]:
    """The video's captions (``video.captions_of``: (text, start s, end s)) as the video shows them
    (``brand.caption_list``: at least 1.5 s, never into the next one, never past the end), in seconds of the page's
    motion: [{"text", "a", "b"}]; frame f of the video starts at (f - 1) / fps."""
    out = []
    for c in brand.caption_list(list(steps), int(round(fps)), 0, int(body_frames)):
        out.append({"text": c.text, "a": round((c.start - 1) / fps, 4), "b": round(c.end / fps, 4)})
    return out
