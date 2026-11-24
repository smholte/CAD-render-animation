"""Hoses that keep out of other parts (task 0298), without Blender.

A hose with **Avoid other parts** on stays outside the parts near it: it lies on them and slides along, with its own
radius. ``core/flex`` does the bending; this module says where the other parts are: a **field** that answers, for any
points in the world, how far each is from the nearest surface of the parts it may touch (signed: negative inside a
part) and the direction out of it.

Words and units (metres, world coordinates):
* body   – one part's shape in its own coordinates: a box it lies in (``lo``, ``hi``) and ``distance(points)`` ->
           (signed distance (m,), unit direction out (m, 3)). ``Box`` and ``Ball`` are exact shapes (tests, and the
           blocks of test models); the app's parts are meshes (``blender/flex_avoid.py``, Blender's BVH trees);
* entry  – one body at one place for one *row* of a hose batch (a hose at one frame): which body, and the body's
           world matrix there (turn + move, no scale: a scaled part's body is made at its scale);
* reach  – the box each row's hose can lie in (its two ends and half its length round them): entries whose body
           stays clear of it are dropped at once, and a point further than ``margin`` from a body's box is not
           asked (it is "far": no surface near, nothing to push it);
* clear  – how far the centreline keeps from a surface: the hose's radius (+ a little).

The field is a pure function of its inputs; a row asks only its own entries, so a batch gives every hose what it
would get alone.
"""

from __future__ import annotations

import numpy as np

FAR = np.inf                    # the distance of a point no body is near
MARGIN = 0.005                  # m: points this much further from a body's box than ``clear`` are not asked


class Body:
    """A shape in its own coordinates. Subclasses give ``lo``, ``hi`` and ``distance``."""

    lo: np.ndarray
    hi: np.ndarray

    def distance(self, pts: np.ndarray) -> tuple:
        raise NotImplementedError

    def exit(self, pts: np.ndarray, dirs: np.ndarray) -> np.ndarray:
        """How far points inside go along the unit directions ``dirs`` before they are out (m,); inf: never."""
        raise NotImplementedError


class Box(Body):
    """A box from ``lo`` to ``hi`` (its own axes): the exact signed distance and the direction out."""

    def __init__(self, lo, hi):
        self.lo = np.asarray(lo, dtype=float).reshape(3)
        self.hi = np.asarray(hi, dtype=float).reshape(3)

    def distance(self, pts: np.ndarray) -> tuple:
        c = 0.5 * (self.lo + self.hi)
        h = 0.5 * (self.hi - self.lo)
        p = np.asarray(pts, dtype=float) - c
        q = np.abs(p) - h
        outside = np.maximum(q, 0.0)
        out_len = np.sqrt(np.einsum("mk,mk->m", outside, outside))
        inside = np.minimum(q.max(axis=1), 0.0)
        dist = out_len + inside
        sign = np.where(p < 0.0, -1.0, 1.0)
        n_out = outside * sign / np.where(out_len > 0.0, out_len, 1.0)[:, None]
        axis = q.argmax(axis=1)                          # inside (or on the surface): out through the nearest face
        n_in = np.zeros_like(p)
        n_in[np.arange(len(p)), axis] = sign[np.arange(len(p)), axis]
        return dist, np.where((out_len > 0.0)[:, None], n_out, n_in)

    def exit(self, pts: np.ndarray, dirs: np.ndarray) -> np.ndarray:
        p, u = np.asarray(pts, dtype=float), np.asarray(dirs, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(u > 0.0, (self.hi - p) / u, np.where(u < 0.0, (self.lo - p) / u, np.inf))
        return np.maximum(t.min(axis=1), 0.0)


class Ball(Body):
    """A ball of ``radius`` round ``centre``."""

    def __init__(self, centre, radius: float):
        self.c = np.asarray(centre, dtype=float).reshape(3)
        self.r = float(radius)
        self.lo, self.hi = self.c - self.r, self.c + self.r

    def distance(self, pts: np.ndarray) -> tuple:
        v = np.asarray(pts, dtype=float) - self.c
        ln = np.sqrt(np.einsum("mk,mk->m", v, v))
        n = np.where((ln > 0.0)[:, None], v / np.where(ln > 0.0, ln, 1.0)[:, None], np.array([0.0, 0.0, 1.0]))
        return ln - self.r, n

    def exit(self, pts: np.ndarray, dirs: np.ndarray) -> np.ndarray:
        v = np.asarray(pts, dtype=float) - self.c
        u = np.asarray(dirs, dtype=float)
        b = np.einsum("mk,mk->m", v, u)
        c = np.einsum("mk,mk->m", v, v) - self.r * self.r
        return np.maximum(-b + np.sqrt(np.maximum(b * b - c, 0.0)), 0.0)


def world_box(m: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> tuple:
    """The world box (lo, hi) of a body's box moved by m ((E, 4, 4))."""
    c = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
    corners = lo[:, None, :] + c[None] * (hi - lo)[:, None, :]                 # (E, 8, 3)
    w = np.einsum("eij,ekj->eki", m[:, :3, :3], corners) + m[:, None, :3, 3]
    return w.min(axis=1), w.max(axis=1)


def reach_box(p0: np.ndarray, p1: np.ndarray, length: np.ndarray, clear: np.ndarray) -> tuple:
    """The box (lo, hi) a hose of ``length`` between p0 and p1 (rows) can lie in: every point of it is within half its
    length of one of its ends (the longer half reaches the far end)."""
    p0, p1 = np.asarray(p0, dtype=float).reshape(-1, 3), np.asarray(p1, dtype=float).reshape(-1, 3)
    r = (0.5 * np.asarray(length, dtype=float) + np.asarray(clear, dtype=float)).reshape(-1)[:, None]
    return np.minimum(p0, p1) - r, np.maximum(p0, p1) + r


class Field:
    """Where the parts a batch of hoses must keep out of are.

    ``bodies``: a list of ``Body``; ``rows``, ``which`` (E,) int and ``places`` (E, 4, 4): entry e is body
    ``which[e]`` at world matrix ``places[e]`` for batch row ``rows[e]``. ``reach`` (lo, hi), each (R, 3): drops the
    entries whose world box stays clear of their row's box. ``margin``: how far beyond ``clear`` a body is still
    asked (``MARGIN``).

    ``field(ids, pts, clear, toward=None)``: ``ids`` (b,) the batch rows of ``pts`` (b, P, 3) -> (signed distance
    (b, P), unit direction out (b, P, 3)) to the nearest body of each row (``FAR`` and 0 where none is near).
    ``toward`` (b, P, 3) unit directions: a point inside a body leaves it that way instead of through the nearest
    face – its "distance" is then minus how far it has to go that way, its direction out that one (the hose comes
    out of a part the side it went in, see ``core/flex._avoid``)."""

    def __init__(self, bodies, rows, which, places, reach=None, margin: float = MARGIN, clear=None):
        self.bodies = list(bodies)
        rows = np.asarray(rows, dtype=np.int64).reshape(-1)
        which = np.asarray(which, dtype=np.int64).reshape(-1)
        places = np.asarray(places, dtype=float).reshape(-1, 4, 4)
        self.margin = float(margin)
        self.asked = 0                                  # points handed to the bodies so far (cost, tests)
        if len(rows):
            lo = np.stack([self.bodies[k].lo for k in which])
            hi = np.stack([self.bodies[k].hi for k in which])
            if reach is not None:
                wlo, whi = world_box(places, lo, hi)
                rlo, rhi = np.asarray(reach[0], dtype=float), np.asarray(reach[1], dtype=float)
                keep = ((wlo <= rhi[rows] + self.margin) & (whi >= rlo[rows] - self.margin)).all(axis=1)
                rows, which, places, lo, hi = rows[keep], which[keep], places[keep], lo[keep], hi[keep]
        else:
            lo = hi = np.zeros((0, 3))
        self.rows, self.which, self.places = rows, which, places
        self.lo, self.hi = lo, hi
        self.inv = np.linalg.inv(places) if len(places) else np.zeros((0, 4, 4))

    def __len__(self) -> int:
        return len(self.rows)

    def rows_with_bodies(self) -> np.ndarray:
        """The batch rows that have at least one body near them."""
        return np.unique(self.rows)

    def __call__(self, ids, pts, clear=0.0, toward=None) -> tuple:
        ids = np.asarray(ids, dtype=np.int64).reshape(-1)
        pts = np.asarray(pts, dtype=float)
        b, p = pts.shape[:2]
        dist = np.full((b, p), FAR)
        out = np.zeros((b, p, 3))
        if not len(self.rows) or not b:
            return dist, out
        pos_of = np.full(max(int(self.rows.max()), int(ids.max())) + 1, -1, dtype=np.int64)
        pos_of[ids] = np.arange(b)
        es = np.flatnonzero(pos_of[self.rows] >= 0) if self.rows.max() < len(pos_of) else np.zeros(0, int)
        if not len(es):
            return dist, out
        reach = np.broadcast_to(np.asarray(clear, dtype=float).reshape(-1), (b,)) if np.ndim(clear) else \
            np.full(b, float(clear))
        for k in np.unique(self.which[es]):
            ek = es[self.which[es] == k]
            body = self.bodies[k]
            pos = pos_of[self.rows[ek]]
            inv = self.inv[ek]
            local = np.einsum("eij,epj->epi", inv[:, :3, :3], pts[pos]) + inv[:, None, :3, 3]
            grow = (reach[pos] + self.margin)[:, None, None]
            near = ((local >= self.lo[ek][:, None, :] - grow) & (local <= self.hi[ek][:, None, :] + grow)).all(axis=2)
            if not near.any():
                continue
            e_i, p_i = np.nonzero(near)
            self.asked += len(e_i)
            d, n_local = body.distance(local[e_i, p_i])
            n_world = np.einsum("mij,mj->mi", self.places[ek][e_i, :3, :3], n_local)
            if toward is not None:
                deep = np.flatnonzero(d < 0.0)
                if len(deep):
                    u = toward[pos[e_i[deep]], p_i[deep]]
                    rot = self.places[ek][e_i[deep], :3, :3]
                    go = body.exit(local[e_i[deep], p_i[deep]], np.einsum("mji,mj->mi", rot, u))
                    fine = np.isfinite(go)
                    d[deep[fine]] = -go[fine]
                    n_world[deep[fine]] = u[fine]
            rows_p = pos[e_i]
            # the nearest body wins; two entries of one row may be asked here (one body at two places): in turn
            order = np.argsort(d, kind="stable")[::-1]  # the nearest last, so it is written last
            rows_p, p_i, d, n_world = rows_p[order], p_i[order], d[order], n_world[order]
            better = d < dist[rows_p, p_i]
            # several candidates for one point: keep the smallest (written last among those that are better)
            rows_p, p_i, d, n_world = rows_p[better], p_i[better], d[better], n_world[better]
            dist[rows_p, p_i] = d
            out[rows_p, p_i] = n_world
            # a candidate written before a smaller one of the same point is overwritten; one written after a smaller
            # one cannot be (sorted): the minimum stays
        return dist, out
