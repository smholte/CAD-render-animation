"""Hoses and cables that keep out of other parts (task 0298): which parts, and their shapes for the solver.

A hose item with **Avoid other parts** on (``FRFlex.avoid``) is solved with a field of the parts near it
(``core/flex_avoid.Field``): ``core/flex`` then keeps its centreline at least its radius (+ ``GAP``) from their
surfaces – it lies on them and slides along – live and at Build.

**Which parts count** (the choice of the brief: everything visible near it, no picking): every model part that is
shown (not hidden, not excluded), is not a hose, cable or chain itself, not a drawn object and not one of the parts
the item's ends and clips sit on (a hose goes *into* its fittings), and whose box comes within the hose's reach in the
pose it is in now: the box round its two ends grown by its whole length (half of it is enough for the pose shown; the
other half catches parts that come near while the machine moves). Parts that move into that room from further away
during an animation are not seen. The list is worked out again at every Build, at every change of the item and when
the pose is solved again (``forget`` drops it).

**A part's shape**: its mesh (scaled as the object is), with the clash check's own inside test (``clash.Mesh``: the
nearest face, rays beside an edge) and Blender's BVH tree with long faces cut short (``core/clash.split_long``). The
world matrix the field gets is the part's place without its scale. Made once per mesh and kept until undo, redo or a
file load.
"""

from __future__ import annotations

import math

import numpy as np

from ..core import flex_avoid as FA
from . import build

GAP = 0.0005                    # m: the hose's surface keeps this far from another part's (besides its radius)
_STATE = {"bodies": {}, "parts": {}}


class MeshBody(FA.Body):
    """A part's mesh as a body of ``core/flex_avoid`` (its own coordinates, scaled as the object)."""

    def __init__(self, verts: np.ndarray, tris: np.ndarray):
        from . import clash
        self.mesh = clash.Mesh(verts, tris)
        self.lo, self.hi = self.mesh.lo.copy(), self.mesh.hi.copy()

    def distance(self, pts: np.ndarray) -> tuple:
        m = self.mesh
        pts = np.asarray(pts, dtype=float)
        dist = np.full(len(pts), FA.FAR)
        way = np.zeros((len(pts), 3))
        if not len(m.t):
            return dist, way
        find = m.ptree.find_nearest
        for k, p in enumerate((pts - m.c).tolist()):
            loc, nor, _i, d = find(p)
            if loc is None:
                continue
            v = np.array((p[0] - loc[0], p[1] - loc[1], p[2] - loc[2]))
            inside = m._inside(p, loc, nor, d)
            if d > 1e-9:
                way[k] = (-v if inside else v) / d
            else:
                way[k] = np.array(nor) * m.sign
            dist[k] = -d if inside else d
        return dist, way

    def exit(self, pts: np.ndarray, dirs: np.ndarray) -> np.ndarray:
        m = self.mesh
        out = np.full(len(pts), np.inf)
        if not len(m.t):
            return out
        ray = m.ptree.ray_cast
        for k, (p, u) in enumerate(zip((np.asarray(pts, dtype=float) - m.c).tolist(),
                                       np.asarray(dirs, dtype=float).tolist())):
            loc, _nor, _i, d = ray(p, u)
            if loc is not None:
                out[k] = d
        return out


def forget() -> None:
    _STATE["bodies"].clear()
    _STATE["parts"].clear()


def _rigid(m) -> np.ndarray:
    """A world matrix without its scale (4, 4) or (F, 4, 4)."""
    m = np.array(m, dtype=float)
    r = m[..., :3, :3]
    ln = np.linalg.norm(r, axis=-2, keepdims=True)
    m[..., :3, :3] = r / np.where(ln > 0.0, ln, 1.0)
    return m


def _scale(ob) -> np.ndarray:
    return np.array([float(c.length) for c in ob.matrix_world.to_3x3().col])


def body_of(ob):
    """The part's body (made once per mesh and scale), or None when it has no faces."""
    me = ob.data
    if me is None or not len(me.vertices):
        return None
    scale = _scale(ob)
    key = (me.name, len(me.vertices), tuple(np.round(scale, 6)))
    got = _STATE["bodies"].get(key)
    if got is None:
        from .flex import _mesh_arrays
        v, t = _mesh_arrays(me)
        got = MeshBody(v * scale, t) if len(t) else None
        _STATE["bodies"][key] = got
    return got


def clear_of(item) -> float:
    """How far the centreline keeps from another part's surface: the hose's radius + ``GAP``."""
    return 0.5 * float(item.diameter) + GAP


def _shown(ob) -> bool:
    try:
        return not ob.hide_viewport and not ob.hide_get() and not ob.get(build.PROP_EXCLUDED)
    except RuntimeError:                         # (not in the view layer)
        return False


def parts_for(scene, item) -> list:
    """The parts this hose keeps out of (see the module's text), nearest first; [] when Avoid is off."""
    if item.kind != "HOSE" or not getattr(item, "avoid", False) or item.a_part is None or item.b_part is None:
        return []
    key = (scene.name, item.name)
    names = _STATE["parts"].get(key)
    if names is None:
        names = _find(scene, item)
        _STATE["parts"][key] = names
    out = []
    for n in names:
        ob = scene.objects.get(n)
        if ob is not None:
            out.append(ob)
    return out


def drop(scene, item=None) -> None:
    """Work the list of parts out again (one item, or every item of the scene)."""
    for k in [k for k in _STATE["parts"] if k[0] == scene.name and (item is None or k[1] == item.name)]:
        del _STATE["parts"][k]


def _find(scene, item) -> list:
    from . import flex
    skip = {ob.name for ob in flex.flex_parts(scene)} | {ob.name for ob in flex.end_objects(item) if ob is not None}
    a = np.array(item.a_part.matrix_world, dtype=float)
    b = np.array(item.b_part.matrix_world, dtype=float)
    pa = a[:3, :3] @ np.array(item.a_point) + a[:3, 3]
    pb = b[:3, :3] @ np.array(item.b_point) + b[:3, 3]
    reach = float(item.length) + clear_of(item)
    lo, hi = np.minimum(pa, pb) - reach, np.maximum(pa, pb) + reach
    found = []
    for ob in build.iter_parts(scene):
        if ob.name in skip or ob.get("fr_drawn") or ob.type != "MESH" or not _shown(ob):
            continue
        if ob.data is None or not len(ob.data.vertices):
            continue
        m = np.array(ob.matrix_world, dtype=float)
        box = np.array([tuple(c) for c in ob.bound_box], dtype=float) @ m[:3, :3].T + m[:3, 3]
        blo, bhi = box.min(axis=0), box.max(axis=0)
        if (blo <= hi).all() and (bhi >= lo).all():
            mid = 0.5 * (blo + bhi)
            found.append((float(np.linalg.norm(mid - 0.5 * (pa + pb))), ob.name))
    found.sort()
    return [n for _d, n in found[:MOST]]


MOST = 64                       # parts at most per hose (the nearest)


def field(rows: list, mats: dict, frames: int):
    """The field for a batch of solver rows. ``rows``: per row, (frame or None for all frames, [objects]) – a row
    of a one-moment batch gives its frame index 0; ``mats``: object name -> (frames, 4, 4). Returns
    ``core/flex_avoid.Field`` or None when no row has a part to avoid."""
    bodies, index = [], {}
    r_ix, which, places = [], [], []
    for r, (frame, obs) in enumerate(rows):
        for ob in obs:
            body = body_of(ob)
            if body is None or ob.name not in mats:
                continue
            k = index.get(id(body))
            if k is None:
                k = index[id(body)] = len(bodies)
                bodies.append(body)
            m = mats[ob.name]
            if frame is None:
                for f in range(frames):
                    r_ix.append(f)
                    which.append(k)
                    places.append(_rigid(m[f]))
            else:
                r_ix.append(r)
                which.append(k)
                places.append(_rigid(m[frame]))
    if not r_ix:
        return None
    return FA.Field(bodies, r_ix, which, np.array(places))


def nearest_gap(scene, item, points: np.ndarray) -> tuple:
    """(the smallest gap between the hose's surface and a part it avoids, that part's name) for its centreline
    points now (world), checked at ``CHECK`` points per piece; (inf, '') when there is none."""
    obs = parts_for(scene, item)
    if not len(obs) or len(points) < 2:
        return math.inf, ""
    from ..core import flex as HS
    fine = HS.resample(points, max(len(points) * CHECK, 2))
    best, who = math.inf, ""
    for ob in obs:
        body = body_of(ob)
        if body is None:
            continue
        m = _rigid(np.array(ob.matrix_world, dtype=float))
        inv = np.linalg.inv(m)
        local = fine @ inv[:3, :3].T + inv[:3, 3]
        grow = clear_of(item) + 0.05
        near = ((local >= body.lo - grow) & (local <= body.hi + grow)).all(axis=1)
        if not near.any():
            continue
        d, _w = body.distance(local[near])
        g = float(d.min()) - 0.5 * float(item.diameter)
        if g < best:
            best, who = g, ob.name
    return best, who


CHECK = 4                       # points per piece of the centreline when the gap is measured
