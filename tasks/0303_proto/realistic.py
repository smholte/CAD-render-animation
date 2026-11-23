"""Study 0303 prototype: Blender Studio's CC0 "Human Base Meshes" body on the person's own 17-bone rig.

Steps (a build task would do the same once per body and store the result as a small file in the app):
1. ``landmarks``: the joints of the base mesh in its A-pose (picked once per body from its own shape – here by hand
   from front and side plots, ``LANDMARKS``).
2. ``weights``: Blender's automatic weights (bone heat) for an armature with the rig's 17 bone names on those joints.
3. ``to_rest``: every bone's turn + stretch from the fitted bone onto the rig's rest bone (linear blend skinning): the
   body now stands in the rig's rest pose, so the app's walks, actions and IK move it like today's person.
4. ``dress``: work clothes without a cloth simulation – the body's own surface, pushed out a few millimetres where the
   clothes are (coverall, boots), coloured per region; reflective bands, a hard hat; the face smoothed (no likeness).

Needs the bundle unpacked (``HBM`` env: the folder with the .npz files written by ``export_hbm.py``). Nothing of the
bundle is committed.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from fresing_render.core import person_rig as R          # noqa: E402
from fresing_render.core import props_detail as P        # noqa: E402

# joints of the base meshes in their own A-pose (x: the figure's left, y: back, z: up; the mesh centred on x = 0).
# Per side the left values are given; the right side mirrors x. (bone: head point; *_tip: the tail of the last bone)
LANDMARKS = {
    "male": dict(
        pelvis=(0, 0.0, 0.92), spine=(0, 0.005, 1.02), chest=(0, 0.01, 1.2), neck=(0, 0.0, 1.43),
        head=(0, -0.005, 1.5), head_tip=(0, -0.005, 1.684),
        arm=(0.17, 0.0, 1.355), forearm=(0.3, 0.01, 1.08), hand=(0.375, -0.035, 0.86), hand_tip=(0.43, -0.1, 0.74),
        thigh=(0.09, 0.0, 0.88), shin=(0.125, -0.01, 0.48), foot=(0.165, 0.04, 0.085), foot_tip=(0.2, -0.16, 0.015)),
    "female": dict(
        pelvis=(0, 0.0, 0.9), spine=(0, 0.01, 1.0), chest=(0, 0.015, 1.17), neck=(0, 0.01, 1.4),
        head=(0, 0.0, 1.47), head_tip=(0, 0.0, 1.641),
        arm=(0.16, 0.01, 1.325), forearm=(0.25, 0.025, 1.05), hand=(0.335, -0.02, 0.84), hand_tip=(0.405, -0.075, 0.72),
        thigh=(0.085, 0.0, 0.86), shin=(0.115, -0.01, 0.47), foot=(0.12, 0.035, 0.08), foot_tip=(0.135, -0.165, 0.015)),
}
_NEXT = {"pelvis": "spine", "spine": "chest", "chest": "neck", "neck": "head", "head": "head_tip",
         "arm": "forearm", "forearm": "hand", "hand": "hand_tip", "thigh": "shin", "shin": "foot", "foot": "foot_tip"}


def fitted_bones(body: str) -> dict:
    """{bone: (head, tail)} of the base mesh's own A-pose."""
    L = {k: np.asarray(v, float) for k, v in LANDMARKS[body].items()}
    out = {}
    for b in R.BONES:
        if b[:2] in ("l_", "r_"):
            sd = 1.0 if b[0] == "l" else -1.0
            kind = b[2:]
            m = np.array((sd, 1.0, 1.0))
            out[b] = (L[kind] * m, L[_NEXT[kind]] * m)
        else:
            out[b] = (L[b], L[_NEXT[b]])
    return out


def _turn(a, b):
    """The smallest turn taking unit vector a onto b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3)
    K = np.array(((0, -v[2], v[1]), (v[2], 0, -v[0]), (-v[1], v[0], 0))) / s
    ang = math.atan2(s, c)
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def to_rest(co, W, body: str, fig: R.Figure):
    """The base mesh's points moved from its A-pose onto the rig's rest pose: per bone, turn the fitted bone onto the
    rest bone and stretch it along itself to the rest bone's length; blend by the weights."""
    fb = fitted_bones(body)
    out = np.zeros_like(co)
    for j, b in enumerate(R.BONES):
        w = W[:, j]
        if not np.any(w):
            continue
        h0, t0 = fb[b]
        h1, _R1, t1 = fig.rest_fk[b]
        d0, d1 = t0 - h0, t1 - h1
        T = _turn(d0, d1)
        u = d0 / np.linalg.norm(d0)
        s = np.linalg.norm(d1) / np.linalg.norm(d0)
        S = np.eye(3) + (s - 1.0) * np.outer(u, u)          # stretch along the fitted bone only
        M = T @ S
        out += w[:, None] * ((co - h0) @ M.T + h1)
    return out


def vertex_normals(co, polys):
    n = np.zeros_like(co)
    for p in polys:
        a, b, c = co[p[0]], co[p[1]], co[p[2]]
        fn = np.cross(b - a, c - a)
        if len(p) == 4:
            fn = fn + np.cross(c - a, co[p[3]] - a)
        n[list(p)] += fn
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(ln > 0, ln, 1.0)


def polys_of(d) -> list:
    sizes, loops = d["sizes"], d["loops"]
    out, i = [], 0
    for s in sizes:
        out.append(tuple(int(x) for x in loops[i:i + s]))
        i += s
    return out


def neighbours(n, polys):
    nb = [set() for _ in range(n)]
    for p in polys:
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            nb[a].add(b)
            nb[b].add(a)
    return [np.fromiter(s, int) for s in nb]


def smooth(co, sel, nb, rounds=8, amount=0.5):
    """Laplacian smoothing of the selected points (a mask): takes the scan's own face off."""
    co = co.copy()
    idx = np.nonzero(sel)[0]
    for _ in range(rounds):
        new = co.copy()
        for i in idx:
            new[i] = co[i] * (1 - amount) + co[nb[i]].mean(axis=0) * amount
        co = new
    return co


OUTFITS = {   # region -> material (the same colours as today's person)
    "OFFSHORE": dict(suit="cloth_orange", band="reflective", boots="boots_black", hat="helmet_white"),
    "WORKSHOP": dict(suit="cloth_navy", band="cloth_navy", boots="boots_black", hat="helmet_yellow"),
    "OFFICE": dict(suit="cloth_trousers", band="reflective", boots="boots_brown", hat="helmet_white", vest="hivis_yellow"),
}


def dress(rest, polys, W, fig: R.Figure, outfit="OFFSHORE", skin_mat="skin_2", nb=None):
    """(points, material per face, names): clothes as the body's own surface pushed out where they are (more on the
    trunk and thighs, where a coverall hangs loose) and smoothed there (``nb``: the points' neighbours) – the muscles
    of the scan go under the cloth."""
    o = OUTFITS[outfit]
    bi = {b: i for i, b in enumerate(R.BONES)}
    dom = W.argmax(axis=1)
    k = fig.k
    nrm = vertex_normals(rest, polys)
    z = rest[:, 2]
    head_like = np.isin(dom, [bi["head"]]) | ((dom == bi["neck"]) & (z > fig.rest_fk["neck"][0][2] + 0.03 * k))
    hand = np.isin(dom, [bi["l_hand"], bi["r_hand"]])
    hand_skin = hand.copy()
    for sd in "lr":                                        # the sleeve ends a little above the wrist
        h0 = fig.rest_fk[f"{sd}_hand"][0]
        hand_skin |= (dom == bi[f"{sd}_forearm"]) & (np.linalg.norm(rest - h0, axis=1) < 0.03 * k)
    boot = (z < 0.16 * k)
    skin = head_like | hand_skin
    cloth = ~skin & ~boot
    loose = np.isin(dom, [bi[b] for b in ("pelvis", "spine", "chest", "l_thigh", "r_thigh")])
    push = np.where(cloth, np.where(loose, 0.014, 0.009) * k, 0.0) + np.where(boot, 0.008 * k, 0.0)
    pts = rest + nrm * push[:, None]
    if nb is not None:
        pts = smooth(pts, cloth & ~np.isin(dom, [bi["neck"]]), nb, rounds=6, amount=0.5)
    names = [skin_mat, o["suit"], o["band"], o["boots"]]
    if "vest" in o:
        names.append(o["vest"])
    mat = []
    chest_h = fig.rest_fk["chest"][0][2]
    for p in polys:
        p = list(p)
        c = rest[p].mean(axis=0)
        if skin[p].mean() > 0.5:
            mat.append(0)
        elif boot[p].mean() > 0.5:
            mat.append(3)
        else:
            m = 1
            db = R.BONES[int(np.bincount(dom[p], minlength=17).argmax())]
            if db[2:] in ("arm", "forearm", "shin", "thigh"):
                h, _r, t = fig.rest_fk[db]
                u = float(np.dot(c - h, t - h) / np.dot(t - h, t - h))
                if (db[2:] == "forearm" and 0.45 < u < 0.6) or (db[2:] == "shin" and 0.3 < u < 0.42):
                    m = 2
            elif db in ("spine", "chest") and abs(c[0]) < 0.17 * k and (abs(c[2] - (chest_h - 0.03 * k)) < 0.018 * k or
                                               abs(c[2] - (chest_h - 0.1 * k)) < 0.018 * k):
                m = 2
            if "vest" in o and db in ("chest", "spine") and c[2] > chest_h - 0.08 * k and m == 1:
                m = 4
            mat.append(m)
    return pts, np.asarray(mat), names


def hard_hat(fig: R.Figure, mat: str, top_z: float, head_c) -> list:
    """A hard hat (shell, brim, ridge) as lofts of props_detail, sized to the scanned head."""
    from fresing_render.core.props_detail import ellipsoid, _loft, _ellipse
    X, Y, Z = np.eye(3)
    c = np.array((head_c[0], head_c[1] + 0.004, top_z - 0.1))
    sh = [ellipsoid(mat, c, 0.104, 0.125, 0.112, 32, None, lat_from=0.0)]
    brim = [_ellipse(c + Z * dz, X, Y, rx, ry, 32) for dz, rx, ry in
            ((0.004, 0.103, 0.124), (-0.003, 0.112, 0.136), (-0.008, 0.113, 0.137), (-0.004, 0.103, 0.123))]
    sh.append(_loft(mat, brim, caps=False))
    peak = [_ellipse(c + Z * dz - Y * 0.118, X, Y, 0.08, ry, 16) for dz, ry in ((0.0, 0.03), (-0.006, 0.036),
                                                                                 (-0.01, 0.024))]
    sh.append(_loft(mat, peak))
    ridge = [_ellipse(c + Y * yy + Z * (0.112 * math.sqrt(max(0.0, 1 - (yy / 0.125) ** 2)) - 0.004), X, Z, 0.012,
                      0.012, 8) for yy in np.linspace(-0.11, 0.11, 9)]
    sh.append(_loft(mat, ridge))
    return sh
