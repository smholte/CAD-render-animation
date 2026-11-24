"""Shape hints (task 0302): what an unnamed part is, from its mesh alone.

A part called "Part123", "Onderdeel4" or "Teil1" says nothing; its shape sometimes does. This module looks at
one part's triangle mesh and answers with one of a few kinds only when the shape leaves no doubt:

* ``"washer"`` – a thin flat ring: round outside, a round hole in the middle, nothing else (no bolt holes,
  no hub, no teeth);
* ``"hex_nut"`` – a hexagonal prism with a round bore through it, about as high as a nut;
* ``"o_ring"`` – a torus: every point the same distance from one circle, no flat face.

Anything else gives ``""``. The tests are strict on purpose: a part this module calls a washer must be one,
a washer it misses keeps the group its CAD material or colour gives it. The part library uses the answer only
for parts whose name, parent assemblies and name material give nothing (``part_types.shape_may_decide``).

No Blender: plain NumPy on the points (metres) and triangles of one part in its own coordinates.

    >>> import numpy as np
    >>> hint(np.zeros((0, 3)), np.zeros((0, 3), dtype=int))
    ''
"""

from __future__ import annotations

import numpy as np

KINDS = ("washer", "hex_nut", "o_ring")

MAX_TRIS = 20000          # a bigger mesh is no small standard part
MAX_SIZE = 0.16           # m: the largest washer / nut / O-ring looked at (M64 washer: 0.125 m)
MIN_SIZE = 0.0015         # m


def _tri_data(p, t):
    v0, v1, v2 = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    cr = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(cr, axis=1)
    keep = ln > 1e-18
    area = ln * 0.5
    n = np.zeros_like(cr)
    n[keep] = cr[keep] / ln[keep, None]
    cen = (v0 + v1 + v2) / 3.0
    return area, n, cen, keep


def _candidate_axes(cen, area):
    """The axes to try: the eigenvector whose second moment stands apart from the other two first."""
    w = area / area.sum()
    c = (cen * w[:, None]).sum(axis=0)
    d = cen - c
    cov = (d * w[:, None]).T @ d
    vals, vecs = np.linalg.eigh(cov)
    gap_low, gap_high = vals[1] - vals[0], vals[2] - vals[1]
    order = [0, 2, 1] if gap_low >= gap_high else [2, 0, 1]
    return c, [vecs[:, i] for i in order]


def _covers_axis(p, t, n, a, c, u, v) -> bool:
    """True when a flat face square to the axis lies across the axis (no hole through the middle)."""
    flat = np.abs(n @ a) > 0.99
    if not flat.any():
        return False
    tri = p[t[flat]] - c
    x, y = tri @ u, tri @ v                                     # (k, 3) each
    s0 = x[:, 0] * y[:, 1] - x[:, 1] * y[:, 0]
    s1 = x[:, 1] * y[:, 2] - x[:, 2] * y[:, 1]
    s2 = x[:, 2] * y[:, 0] - x[:, 0] * y[:, 2]
    inside = ((s0 >= 0) & (s1 >= 0) & (s2 >= 0)) | ((s0 <= 0) & (s1 <= 0) & (s2 <= 0))
    return bool(inside.any())


def _judge(p, t, area, n, cen, c, a) -> str:
    a = a / np.linalg.norm(a)
    u = np.cross(a, (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0))
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    d = p - c
    h = d @ a
    rx, ry = d @ u, d @ v
    rho = np.hypot(rx, ry)
    ro, ri = float(rho.max()), float(rho.min())
    thick = float(np.ptp(h))
    if ro <= 0 or thick <= 0:
        return ""
    along = np.abs(n @ a)
    # ---- O-ring: a torus – every point the same distance from the middle circle, at many heights (a ring of
    # square section has its points at the same distance too, but only at its four corners)
    if ri > 0.3 * ro:
        rc, rs = 0.5 * (ro + ri), 0.5 * (ro - ri)
        dist = np.hypot(rho - rc, h)
        if (rs > 0 and abs(thick - 2 * rs) < 0.1 * rs and np.all(np.abs(dist - rs) < 0.08 * rs)
                and len(np.unique(np.round(h / rs * 20))) >= 8):
            return "o_ring"

    if _covers_axis(p, t, n, a, c, u, v) or ri < 0.2 * ro:
        return ""                                               # no hole through the middle

    # side faces (square to the axis) on the outside: their directions tell round from hexagonal
    side = (along < 0.2) & (np.hypot((cen - c) @ u, (cen - c) @ v) > 0.75 * ro)
    if not side.any():
        return ""
    w = area[side]
    ang = np.arctan2(n[side] @ v, n[side] @ u)
    six = np.abs((w * np.exp(6j * ang)).sum()) / w.sum()

    if six >= 0.9:                                              # ---- hexagonal outside
        theta0 = np.angle((w * np.exp(6j * ang)).sum()) / 6.0
        dirs = theta0 + np.arange(6) * np.pi / 3.0
        proj = rx[:, None] * np.cos(dirs)[None, :] + ry[:, None] * np.sin(dirs)[None, :]
        apothem = float(proj.max(axis=0).mean())
        across = 2.0 * apothem
        if not (0.003 <= across <= 0.1 and 0.3 <= thick / across <= 1.3 and 0.35 <= ri / apothem <= 0.85):
            return ""
        # only the bore (with its chamfer) and the hexagon (with its chamfer): no collar, no flange
        if np.all((rho <= ri * 1.35) | (rho >= 0.8 * apothem)) and ro <= apothem * 1.2:
            return "hex_nut"
        return ""

    # ---- round outside: a washer is a thin flat ring and nothing else
    dirs_seen = len(np.unique(np.round(ang / (np.pi / 90.0)).astype(int)))
    if six > 0.3 or dirs_seen < 12:
        return ""
    if not (0.02 <= thick / (2 * ro) <= 0.25 and 0.3 <= ri / ro <= 0.85):
        return ""
    if np.all((rho <= ri + 0.05 * ro) | (rho >= 0.95 * ro)):
        return "washer"
    return ""


def hint(points, triangles) -> str:
    """The kind of standard part a mesh is ("washer", "hex_nut", "o_ring"), or "" when unsure.

    ``points``: (n, 3) in metres, the part's own coordinates; ``triangles``: (m, 3) indices."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if len(t) < 8 or len(t) > MAX_TRIS or len(p) < 6:
        return ""
    if t.min() < 0 or t.max() >= len(p) or not np.all(np.isfinite(p)):
        return ""
    size = float(np.ptp(p, axis=0).max())
    if not (MIN_SIZE <= size <= MAX_SIZE):
        return ""
    area, n, cen, keep = _tri_data(p, t)
    if area.sum() <= 0:
        return ""
    area, n, cen, t = area[keep], n[keep], cen[keep], t[keep]
    c, axes = _candidate_axes(cen, area)
    for a in axes:
        kind = _judge(p, t, area, n, cen, c, a)
        if kind:
            return kind
    return ""
