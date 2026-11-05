"""Where a decal lies on a part (task 0024). Pure numpy, no Blender.

A decal is a rectangle of picture on one CAD face of a part: a logo, a type plate, text, a
sticker. Everything is in the part's own coordinates (metres), so the decal moves, turns and
hides with the part.

* Flat faces (and faces that are neither flat nor round): the picture is projected straight onto
  the face, along the face's normal at the decal's centre.
* Round faces (cylinders: shafts, barrels, drums, tanks): the picture is wrapped round the face
  like a real sticker – the cylinder is unrolled, so the picture keeps its size all round.

``build`` returns the decal's own small mesh: the face's triangles cut to the rectangle, lifted
``OFFSET`` off the surface, with UV coordinates (0..1 across the picture).

The decal's place: ``anchor`` (a point on the face, where it was clicked), the face's ``normal``
there and an ``up`` direction (upright on the face). Moving by numbers (``shift``, in mm on the
face), turning (``angle``) and sizing (``width``, ``height``) are applied on top, so "Upright" and
"Fit to face" can always start again from the anchor.
"""

from __future__ import annotations

import math

import numpy as np

OFFSET = 0.0002          # m: the decal floats 0.2 mm above the face (no flicker in the view; not seen in renders)
FACING = 0.2             # flat projection: triangles turned further away than ~78° are left out
LOCATE_TOL = 0.001       # m: a model update finds the decal's face again when it is this close


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 1e-12, n, 1.0)


def upright_axes(normal, *up_hints) -> tuple[np.ndarray, np.ndarray]:
    """(right, up) on a face with this normal: ``up`` is the first hint that is not (nearly) along
    the normal, laid flat onto the face. Seen from the front of the face, ``right`` points right."""
    n = unit(normal)
    for hint in list(up_hints) + [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]:
        h = np.asarray(hint, dtype=np.float64)
        u = h - np.dot(h, n) * n
        if np.linalg.norm(u) > 0.15 * max(np.linalg.norm(h), 1e-12):
            u = unit(u)
            return unit(np.cross(u, n)), u
    raise ValueError("no up direction")         # not reachable: the three axes cannot all be along n


def rotate2(xy: np.ndarray, angle: float) -> np.ndarray:
    """Turn 2D points by ``angle`` (counter-clockwise)."""
    c, s = math.cos(angle), math.sin(angle)
    xy = np.asarray(xy, dtype=np.float64)
    return np.stack([c * xy[..., 0] - s * xy[..., 1], s * xy[..., 0] + c * xy[..., 1]], axis=-1)


# ---------------------------------------------------------------------------
# round faces
# ---------------------------------------------------------------------------


def fit_cylinder(points, normals) -> dict | None:
    """Axis, a point on the axis and radius when the face is (part of) a cylinder, else None.

    The normals of a cylinder all lie at right angles to its axis (and spread round it); its points
    all lie at one distance from the axis. Faces that are nearly flat (less than ~6° of arc) count
    as flat: projecting onto them is just as good."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    n = np.asarray(normals, dtype=np.float64).reshape(-1, 3)
    if len(p) < 6:
        return None
    if len(p) > 30000:                       # a big face: every k-th point says just as much
        step = len(p) // 30000 + 1
        p, n = p[::step], n[::step]
    n = unit(n)
    w, v = np.linalg.eigh(n.T @ n / len(n))
    if w[0] > 1e-4 or w[1] < 1e-3:
        return None
    axis = unit(v[:, 0])
    b1, b2 = upright_axes(axis, (1.0, 0.0, 0.0))
    xy = np.stack([p @ b1, p @ b2], axis=1)
    a = np.column_stack([2 * xy, np.ones(len(xy))])
    sol, *_ = np.linalg.lstsq(a, (xy ** 2).sum(axis=1), rcond=None)
    cx, cy, c = sol
    r2 = c + cx * cx + cy * cy
    if r2 <= 0:
        return None
    radius = math.sqrt(r2)
    dist = np.hypot(xy[:, 0] - cx, xy[:, 1] - cy)
    if np.abs(dist - radius).max() > 2e-3 * radius + 1e-6:
        return None
    return {"axis": axis, "centre": cx * b1 + cy * b2, "radius": radius}


# ---------------------------------------------------------------------------
# the decal's frame and its 2D chart of the face
# ---------------------------------------------------------------------------


def frame(anchor, normal, up, cyl: dict | None = None, *up_hints) -> dict:
    """Everything ``chart`` needs. On a round face the normal is the cylinder's own at the anchor."""
    anchor = np.asarray(anchor, dtype=np.float64)
    normal = unit(normal)
    if cyl is not None:
        rad = anchor - cyl["centre"]
        rad = rad - np.dot(rad, cyl["axis"]) * cyl["axis"]
        if np.linalg.norm(rad) < 1e-9:
            cyl = None
        else:
            rho = unit(rad)                                   # out from the axis through the anchor
            normal = rho if np.dot(rho, normal) >= 0 else -rho    # inside a pipe the face looks inwards
            cyl = dict(cyl, rho=rho, tau=unit(np.cross(cyl["axis"], rho)), r_anchor=float(np.linalg.norm(rad)),
                       along0=float(np.dot(anchor - cyl["centre"], cyl["axis"])))
    right, upv = upright_axes(normal, up, *up_hints)
    return {"anchor": anchor, "normal": normal, "right": right, "up": upv, "cyl": cyl}


def chart(points, fr: dict) -> tuple[np.ndarray, np.ndarray | None]:
    """2D coordinates of points of the face (metres, x right / y up on the upright decal, the anchor
    at 0,0) and, on a round face, their angle round the axis (None on a flat face)."""
    p = np.asarray(points, dtype=np.float64)
    cyl = fr["cyl"]
    if cyl is None:
        d = p - fr["anchor"]
        return np.stack([d @ fr["right"], d @ fr["up"]], axis=-1), None
    rel = p - cyl["centre"]
    along = rel @ cyl["axis"]
    radial = rel - along[..., None] * cyl["axis"]
    phi = np.arctan2(radial @ cyl["tau"], radial @ cyl["rho"])          # 0 at the anchor, -pi..pi round
    arc = cyl["r_anchor"] * phi
    t3 = arc[..., None] * cyl["tau"] + (along - cyl["along0"])[..., None] * cyl["axis"]
    return np.stack([t3 @ fr["right"], t3 @ fr["up"]], axis=-1), phi


def _usable(tri_pos: np.ndarray, tri_nrm: np.ndarray, fr: dict, phi, reach: float) -> np.ndarray:
    """Triangles the decal may lie on: on a flat face those facing the same way and near the
    anchor's plane, on a round face those that do not cross the far side (where the unrolled
    face is cut open)."""
    if fr["cyl"] is None:
        n = tri_nrm.mean(axis=1)
        facing = unit(n) @ fr["normal"] > FACING
        depth = np.abs((tri_pos.mean(axis=1) - fr["anchor"]) @ fr["normal"])
        return facing & (depth <= reach)
    ph = phi.reshape(-1, 3)
    return (ph.max(axis=1) - ph.min(axis=1)) < math.pi


# ---------------------------------------------------------------------------
# the decal mesh
# ---------------------------------------------------------------------------


def _clip(poly: list, axis: int, limit: float, keep_below: bool) -> list:
    """Sutherland-Hodgman: keep the part of a polygon on one side of s=limit (axis 0) or t=limit (1)."""
    out = []
    if not poly:
        return out
    prev = poly[-1]
    pv = prev[axis] - limit if keep_below else limit - prev[axis]
    for cur in poly:
        cv = cur[axis] - limit if keep_below else limit - cur[axis]
        if cv <= 0:
            if pv > 0:
                k = pv / (pv - cv)
                out.append(prev + k * (cur - prev))
            out.append(cur)
        elif pv <= 0:
            k = pv / (pv - cv)
            out.append(prev + k * (cur - prev))
        prev, pv = cur, cv
    return out


def build(tri_pos, tri_nrm, fr: dict, shift=(0.0, 0.0), angle: float = 0.0, width: float = 0.1,
          height: float = 0.1, mirror: bool = False, offset: float = OFFSET) -> dict:
    """The decal's mesh on these triangles of its face (part coordinates).

    Returns ``positions`` (V,3), ``normals`` (V,3), ``uv`` (V,2) and ``triangles`` (F,3); empty arrays
    when the decal lies off the face."""
    tri_pos = np.asarray(tri_pos, dtype=np.float64).reshape(-1, 3, 3)
    tri_nrm = np.asarray(tri_nrm, dtype=np.float64).reshape(-1, 3, 3)
    hw, hh = 0.5 * float(width), 0.5 * float(height)
    empty = {"positions": np.zeros((0, 3)), "normals": np.zeros((0, 3)), "uv": np.zeros((0, 2)),
             "triangles": np.zeros((0, 3), dtype=np.int64)}
    if not len(tri_pos) or hw <= 0 or hh <= 0:
        return empty
    # only triangles near the decal can touch it: on a flat face and round a cylinder a point that is
    # d away on the face is at most d away in space (big faces: most triangles go here)
    centre = fr["anchor"]
    if fr["cyl"] is None:
        c2 = rotate2(np.asarray(shift, dtype=np.float64), 0.0)
        centre = fr["anchor"] + c2[0] * fr["right"] + c2[1] * fr["up"]
    reach_3d = math.hypot(hw, hh) + (math.hypot(*shift) if fr["cyl"] is not None else 0.0)
    v0 = tri_pos[:, 0]
    e1, e2, d0 = tri_pos[:, 1] - v0, tri_pos[:, 2] - v0, v0 - centre
    size = np.sqrt(np.maximum(np.einsum("ij,ij->i", e1, e1), np.einsum("ij,ij->i", e2, e2)))
    near = np.sqrt(np.einsum("ij,ij->i", d0, d0)) <= reach_3d + size + 1e-9
    if not near.all():
        tri_pos, tri_nrm = tri_pos[near], tri_nrm[near]
        if not len(tri_pos):
            return empty
    tri_nrm = unit(tri_nrm)
    xy, phi = chart(tri_pos.reshape(-1, 3), fr)
    st = rotate2(xy - np.asarray(shift, dtype=np.float64), -float(angle)).reshape(-1, 3, 2)
    keep = _usable(tri_pos, tri_nrm, fr, phi, reach=max(hw, hh) + 1e-6)
    lo, hi = st.min(axis=1), st.max(axis=1)
    keep &= (hi[:, 0] >= -hw) & (lo[:, 0] <= hw) & (hi[:, 1] >= -hh) & (lo[:, 1] <= hh)
    # each corner as one row: s, t, x, y, z, nx, ny, nz
    rows = np.concatenate([st, tri_pos, tri_nrm], axis=2)[keep]
    inside = (np.abs(rows[:, :, 0]) <= hw).all(axis=1) & (np.abs(rows[:, :, 1]) <= hh).all(axis=1)
    verts = [rows[inside].reshape(-1, 8)]
    tris = [np.arange(3 * int(inside.sum()), dtype=np.int64).reshape(-1, 3)]
    count = len(verts[0])
    for tri in rows[~inside]:                        # only the triangles the outline cuts through
        poly = list(tri)
        for axis, limit, below in ((0, hw, True), (0, -hw, False), (1, hh, True), (1, -hh, False)):
            poly = _clip(poly, axis, limit, below)
            if len(poly) < 3:
                break
        if len(poly) < 3:
            continue
        verts.append(np.asarray(poly))
        k = len(poly)
        tris.append(count + np.stack([np.zeros(k - 2, dtype=np.int64), np.arange(1, k - 1), np.arange(2, k)], axis=1))
        count += k
    v = np.concatenate(verts, axis=0) if verts else np.zeros((0, 8))
    if not len(v):
        return empty
    nrm = unit(v[:, 5:8])
    u = v[:, 0] / (2 * hw)
    uv = np.stack([0.5 - u if mirror else 0.5 + u, 0.5 + v[:, 1] / (2 * hh)], axis=1)
    return {"positions": v[:, 2:5] + nrm * offset, "normals": nrm, "uv": uv,
            "triangles": np.concatenate(tris, axis=0)}


# ---------------------------------------------------------------------------
# fit to face, default size
# ---------------------------------------------------------------------------


def _inside_2d(points: np.ndarray, tris: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Which 2D points lie inside any of the 2D triangles (P,), triangles (T,3,2)."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    v0, v1 = b - a, c - a
    d = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    ok = np.abs(d) > 1e-18
    a, v0, v1, d = a[ok], v0[ok], v1[ok], d[ok]
    q = points[:, None, :] - a[None]
    l1 = (q[..., 0] * v1[:, 1] - q[..., 1] * v1[:, 0]) / d
    l2 = (v0[:, 0] * q[..., 1] - v0[:, 1] * q[..., 0]) / d
    return ((l1 >= -tol) & (l2 >= -tol) & (l1 + l2 <= 1 + tol)).any(axis=1)


def fit_to_face(tri_pos, tri_nrm, fr: dict, angle: float = 0.0, aspect: float = 1.0,
                margin: float = 0.9) -> tuple[tuple[float, float], float, float]:
    """(shift, width, height) of the biggest decal of this shape (``aspect`` = height / width) that
    fits on the face at this angle, with a little room round it. On a round face: on the half
    facing the anchor."""
    tri_pos = np.asarray(tri_pos, dtype=np.float64).reshape(-1, 3, 3)
    tri_nrm = unit(np.asarray(tri_nrm, dtype=np.float64).reshape(-1, 3, 3))
    xy, phi = chart(tri_pos.reshape(-1, 3), fr)
    keep = _usable(tri_pos, tri_nrm, fr, phi, reach=math.inf)
    if phi is not None:
        keep &= (np.abs(phi.reshape(-1, 3)) <= 0.5 * math.pi + 1e-9).all(axis=1)
    st = rotate2(xy, -float(angle)).reshape(-1, 3, 2)[keep]
    if not len(st):
        return (0.0, 0.0), 0.0, 0.0
    lo, hi = st.reshape(-1, 2).min(axis=0), st.reshape(-1, 2).max(axis=0)
    centre = 0.5 * (lo + hi)
    bw, bh = hi - lo
    aspect = max(float(aspect), 1e-6)
    w = min(bw, bh / aspect)
    edge = np.array([(x, y) for x in (-0.5, -0.25, 0.0, 0.25, 0.5) for y in (-0.5, -0.25, 0.0, 0.25, 0.5)
                     if abs(x) == 0.5 or abs(y) == 0.5])
    for _ in range(40):                      # shrink until the whole outline lies on the face (discs, notches)
        pts = centre + edge * np.array([w, w * aspect]) * 0.995
        if _inside_2d(pts, st).all():
            break
        w *= 0.95
    w *= margin
    shift = rotate2(centre, float(angle))
    return (float(shift[0]), float(shift[1])), float(w), float(w * aspect)


# ---------------------------------------------------------------------------
# finding the face again (model update, templates)
# ---------------------------------------------------------------------------


def locate(tri_pos, point, normal, tol: float = LOCATE_TOL) -> int:
    """Index of the triangle the point lies on (within ``tol``, facing the same way), or -1."""
    tri_pos = np.asarray(tri_pos, dtype=np.float64).reshape(-1, 3, 3)
    if not len(tri_pos):
        return -1
    p = np.asarray(point, dtype=np.float64)
    a, b, c = tri_pos[:, 0], tri_pos[:, 1], tri_pos[:, 2]
    n = np.cross(b - a, c - a)
    area2 = np.linalg.norm(n, axis=1)
    ok = area2 > 1e-18
    n = n / np.where(ok, area2, 1.0)[:, None]
    dist = np.einsum("ij,ij->i", p - a, n)
    q = p - dist[:, None] * n
    v0, v1, v2 = b - a, c - a, q - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) > 1e-30, den, 1.0)
    l1 = (d11 * d20 - d01 * d21) / den
    l2 = (d00 * d21 - d01 * d20) / den
    edge_tol = tol / np.sqrt(np.maximum(area2, 1e-30))       # a little room at the edges
    inside = (l1 >= -edge_tol) & (l2 >= -edge_tol) & (l1 + l2 <= 1 + edge_tol)
    good = ok & inside & (np.abs(dist) <= tol) & (n @ unit(normal) > 0.9)
    if not good.any():
        return -1
    idx = np.flatnonzero(good)
    return int(idx[np.argmin(np.abs(dist[idx]))])
