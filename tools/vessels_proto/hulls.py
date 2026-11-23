"""Invented generic hulls at real size (study 0312). No Blender: meshes as NumPy arrays (metres; x to the bow,
y to port, z up, the design waterline at z = 0 only for the numbers in the presets – the hydrostatics find their own).

* ``monohull`` – a lofted hull: stations across, a fine bow, a flat bottom amidships, a transom.
* ``catamaran`` – two slender demi-hulls (a crew transfer vessel) joined by a wet deck.
* ``box`` – a closed box (a container, a barge's pontoon).

Every mesh is closed and its faces point outward (checked by ``volume`` > 0).
"""

from __future__ import annotations

import math

import numpy as np


def _grid_faces(nu: int, nv: int, closed_v: bool = False) -> np.ndarray:
    f = []
    vv = nv if closed_v else nv - 1
    for i in range(nu - 1):
        for j in range(vv):
            a, b = i * nv + j, i * nv + (j + 1) % nv
            c, d = (i + 1) * nv + (j + 1) % nv, (i + 1) * nv + j
            f.append((a, b, d))
            f.append((b, c, d))
    return np.array(f, int)


def monohull(length: float, beam: float, depth: float, draught: float, bow_share: float = 0.3,
             stern_share: float = 0.1, deadrise: float = 0.15, flare: float = 0.08, n_st: int = 48, n_half: int = 14):
    """A closed monohull. Stations from the transom (x = -L/2) to the stem (x = +L/2); the keel at z = -draught,
    the deck edge at z = depth - draught. Returns (verts, faces)."""
    xs = np.linspace(-length / 2, length / 2, n_st)
    keel, top = -draught, depth - draught
    rings = []
    for x in xs:
        s = (x + length / 2) / length                          # 0 transom … 1 stem
        half = beam / 2
        if s > 1 - bow_share:                                  # the bow narrows to the stem (a curved waterline)
            q = (s - (1 - bow_share)) / bow_share
            half *= math.sqrt(max(1 - q ** 2.2, 0.0)) * 0.98 + 0.02
        if s < stern_share:                                    # the stern narrows a little to the transom
            half *= 0.86 + 0.14 * s / stern_share
        # the bottom rises towards the bow (forefoot) and a little at the stern
        rise = 0.0
        if s > 0.75:
            rise = (s - 0.75) / 0.25
            rise = rise ** 1.8 * (depth * 0.55)
        if s < 0.08:
            rise = (0.08 - s) / 0.08 * draught * 0.35
        kz = keel + rise
        # one half section from the keel (centre line) up the side to the deck edge, then mirrored
        pts = []
        for j in range(n_half):
            t = j / (n_half - 1)
            if t < 0.35:                                       # bottom: deadrise from the keel to the bilge
                tt = t / 0.35
                yy = half * 0.85 * tt
                zz = kz + deadrise * half * tt
            elif t < 0.55:                                     # the bilge: a quarter round
                tt = (t - 0.35) / 0.2
                a = tt * math.pi / 2
                r = half * 0.15
                yy = half * 0.85 + r * math.sin(a)
                zz = kz + deadrise * half + r * (1 - math.cos(a))
            else:                                              # the side up to the deck, with a little flare
                tt = (t - 0.55) / 0.45
                z0 = kz + deadrise * half + half * 0.15
                zz = z0 + (top - z0) * tt
                yy = half * (1 + flare * tt * tt)
            pts.append((yy, zz))
        sec = [(x, -y, z) for (y, z) in reversed(pts)] + [(x, y, z) for (y, z) in pts[1:]]
        rings.append(sec)
    v = np.array(rings, float)                                 # n_st x m x 3
    nst, m = v.shape[:2]
    verts = v.reshape(-1, 3)
    faces = [_grid_faces(nst, m, closed_v=True)]      # closed: the last strip is the deck
    # deck (top edge to top edge across), transom and the stem cap: fans to a middle point
    caps = []
    extra = []
    base = len(verts)
    # transom (first ring) and stem (last ring): fan from the ring's own centre
    for ring_i, flip in ((0, False), (nst - 1, True)):
        ring = v[ring_i]
        c = ring.mean(axis=0)
        ci = base + len(extra)
        extra.append(c)
        idx = ring_i * m + np.arange(m)
        for j in range(m):
            a, b = idx[j], idx[(j + 1) % m]
            caps.append((ci, b, a) if not flip else (ci, a, b))
    verts = np.concatenate([verts, np.array(extra)])
    faces.append(np.array(caps, int))
    f = np.concatenate(faces)
    if volume(verts, f) < 0:
        f = f[:, ::-1]
    return verts, f


def catamaran(length: float, beam: float, hull_beam: float, depth: float, draught: float):
    """Two demi-hulls ``hull_beam`` wide whose middles are ``beam - hull_beam`` apart (``beam`` overall)."""
    v1, f1 = monohull(length, hull_beam, depth, draught, bow_share=0.42, stern_share=0.05, deadrise=0.5, flare=0.0,
                      n_st=40, n_half=10)
    off = (beam - hull_beam) / 2
    a = v1 + (0, off, 0)
    b = v1 + (0, -off, 0)
    return np.concatenate([a, b]), np.concatenate([f1, f1 + len(v1)])


def box(sx: float, sy: float, sz: float, z0: float = 0.0):
    """A closed box, its bottom at ``z0``."""
    x, y = sx / 2, sy / 2
    v = np.array([(-x, -y, z0), (x, -y, z0), (x, y, z0), (-x, y, z0),
                  (-x, -y, z0 + sz), (x, -y, z0 + sz), (x, y, z0 + sz), (-x, y, z0 + sz)], float)
    f = np.array([(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
                  (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)], int)
    return v, f


def volume(verts, faces) -> float:
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
