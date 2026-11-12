"""Hoses, cables and drag chains that follow the motion (task 0058).

A hose in a CAD model is one stiff solid, drawn bent in the pose the designer chose. When the machine moves it
should bend along: both ends stay on their fittings, the length stays the same. A drag chain is a row of stiff
links (or one solid) that should roll over its bend. This file does that for the parts the user picks.

**No new model objects.** The hose part itself gets a Geometry Nodes modifier (``MOD``) that replaces its CAD shape
by a tube along the solved centreline; every CAD link of a chain gets one that moves the link's own shape to its
place on the chain; a chain drawn as one solid gets one that draws app-made links instead. So materials, paint
schemes, hiding, fades and selection keep working, and with the item (or the modifier) off the CAD shape shows
exactly as imported. The drawn shape takes the part's own material (slot 0 of the object).

**One shapes mesh per scene** (``SHAPES``, hidden, in the collection ``COLLECTION``): a list of points in world
coordinates, ``per frame`` points for one moment, moment after moment. A hose owns ``DRAWN`` points of each moment
(its centreline), a chain one point per link (the link's place; its X and Z axes are the point attributes ``fr_x``
and ``fr_z``). Each modifier knows its slice (``Offset``, ``Count``) and picks the moment from the frame shown:
``clamp(round(frame - First), 0, Frames - 1)``. The node trees bring the world points into the part's own space, so
the part may sit anywhere in the model tree.

* **Live** (no built animation): the mesh holds one moment (``Frames`` = 1). A handler looks after every update
  whether a part that an end sits on has moved; the items it concerns are solved again and written. Poses and
  saved scenes applied by a script call ``refresh``.
* **Built animation**: ``bake`` (the last step of every Build) reads the end parts' places at every frame, solves
  all frames at once and writes them all; playing and rendering then cost no Python, any frame can be rendered
  on its own, in any order, in the background and with scripts off. The places read are kept with the project, so a
  slider moved afterwards solves every frame again without stepping through the animation.

**Where an end is.** A hose is read in the CAD pose (whatever pose the model is in now): its centreline, diameter
and length (``core/flex_fit``), and for each end the part it touches there (its fitting). The end point and the
direction the hose runs there are kept in that part's own coordinates, so at any time the end is at
``part.matrix_world @ point``. A chain is read from its links' CAD places (``core/flex_chain.fit_links``): pitch,
bend radius, which end is fixed; its own frame is kept in the fixed part's coordinates and the last pin in the
moving part's.

The shapes come from ``core/flex`` (hoses: an elastic rod of fixed length under its weight) and
``core/flex_chain`` (chains: runs and a bend, every pin one pitch from the next). Both are pure functions of where
the ends are: the same frame gives the same shape whatever was shown before.

An item's settings are in props.py (``FRFlex``). Besides those it keeps a few plain custom properties of its
own: what the CAD file said (``cad_diameter``, ``cad_pitch``, ``cad_radius``, ``cad_mode``, ``cad_count``,
``cad_width``, ``cad_height`` – a number that differs from it was set by the user and survives a model update),
``a_user`` / ``b_user`` (the user picked the part this end sits on), ``swapped`` (the user swapped a chain's ends)
and ``link_name`` (the object of the app-made link). A CAD link carries its matrix in its pin frame (``LOCAL``).

Units: metres, world coordinates. Module-level caches hold names and numbers only and are dropped at undo, redo
and file load.
"""

from __future__ import annotations

import json
import math
import threading
from contextlib import contextmanager

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import flex_chain as CH
from ..core import flex_fit
from ..core.words import plural
from . import build, idprops

TAG = "fr_flex"                         # on flex parts, the shapes object and mesh, the node trees, app-made links
MOD = "FR flex"                         # the modifier's name on a flex part
SHAPES = "FR flex shapes"
COLLECTION = "Flex parts"
TREES = {"HOSE": "FR flex hose", "LINK": "FR flex link", "CHAIN": "FR flex chain"}
VERSION = 2                             # of the node trees: an older tree is made again
POINTS = 33                             # centreline points of a hose (what the solver gives)
DRAWN = POINTS + 2                      # … and what is kept: one more point close to each end (see ``_with_ends``)
END_SHARE = 0.25                        # that point lies this share of the first (last) piece from the end
SIDES = 16                              # of the tube's cross-section
SMOOTH = 3                              # the tube bends in this many pieces between two centreline points
LOCAL = "fr_flex_local"                 # on a CAD link: its matrix in its own pin frame (16 numbers, row by row)
MADE_LINK = "FR flex link"              # + the item's name: the link the app draws along a chain that is one solid
LENGTH_SPARE = 1.001                    # a CAD hose reads ~0.1 % short (facets): never "too short" in its own pose
USER_CHANGE = 0.002                     # a number differs this much from the CAD one: the user set it

_KEY = "fr_flex_shapes"                 # on the scene: its shapes object
_FRAMES, _PER, _FIRST = "fr_flex_frames", "fr_flex_per", "fr_flex_first"       # on the shapes object: its layout
_ENDS, _ENDS_OBS, _ENDS_FIRST = "fr_flex_ends", "fr_flex_ends_obs", "fr_flex_ends_first"   # the places read at Build
_INPUTS = (("Shapes", "NodeSocketObject"), ("First", "NodeSocketInt"), ("Frames", "NodeSocketInt"),
           ("Per frame", "NodeSocketInt"), ("Offset", "NodeSocketInt"), ("Count", "NodeSocketInt"),
           ("Radius", "NodeSocketFloat"), ("Link", "NodeSocketObject"))

# runtime only: nothing here outlives undo, redo or a file load, and no Blender object is kept
_STATE = {"busy": 0, "last": {}, "arrays": {}, "solves": 0, "steps": 0, "inputs": {}}


class FlexError(RuntimeError):
    """A part cannot be a hose or a chain; the text says why, in plain words."""


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------

def items(scene):
    return scene.fresing.flex


def active(scene):
    s = scene.fresing
    return s.flex[s.flex_index] if 0 <= s.flex_index < len(s.flex) else None


def find(scene, name: str):
    for it in scene.fresing.flex:
        if it.name == name:
            return it
    return None


def index_of(scene, item) -> int:
    for i, it in enumerate(scene.fresing.flex):
        if it == item:
            return i
    return -1


def _part_name(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def label(item) -> str:
    if item.name:
        return item.name
    if item.part is not None:
        return _part_name(item.part)
    return "Drag chain" if item.kind == "CHAIN" else "Hose"


def _word(item) -> str:
    return "Drag chain" if item.kind == "CHAIN" else "Hose"


def _unique(scene, base: str) -> str:
    names = {it.name for it in scene.fresing.flex}
    name, n = base, 2
    while name in names:
        name, n = f"{base} {n}", n + 1
    return name


@contextmanager
def _quiet(item):
    """Set an item's settings without its update callback answering each one."""
    item["_busy"] = True
    try:
        yield item
    finally:
        if "_busy" in item:
            del item["_busy"]


def _alive(scene, ob) -> bool:
    """The part is still there (a deleted object leaves ``None`` in the item)."""
    try:
        return ob is not None and bool(ob.name)
    except ReferenceError:
        return False


def link_objects(item) -> list:
    return [r.obj for r in item.links]


def parts_of(scene, item) -> list:
    """The model parts the item draws: the hose part, a chain's links (fixed end first), or the chain's solid."""
    if item.kind == "CHAIN" and not item.made_links:
        return [ob for ob in link_objects(item) if ob is not None]
    return [item.part] if item.part is not None else []


def flex_parts(scene) -> list:
    """Every part that is drawn by a hose or chain item."""
    out = []
    for it in scene.fresing.flex:
        out += parts_of(scene, it)
    return out


def broken(scene, item) -> str:
    """'' when the item has all its parts, else what is missing (plain words, for a list row)."""
    if item.kind == "CHAIN" and not item.made_links:
        obs = link_objects(item)
        if len(obs) < 4 or not all(_alive(scene, ob) for ob in obs):
            return "a link is gone"
        if any(LOCAL not in ob for ob in obs):
            return "its links must be read again ('Fit to the CAD pose')"
    elif not _alive(scene, item.part):
        return "its part is gone"
    if not _alive(scene, item.a_part):
        return "the part its fixed end sat on is gone" if item.kind == "CHAIN" else "the part its end A sat on is gone"
    if not _alive(scene, item.b_part):
        return "the part its moving end sat on is gone" if item.kind == "CHAIN" else "the part its end B sat on is gone"
    return ""


def _usable(scene) -> list:
    """[(index, item)] of the items that are on and have all their parts."""
    return [(i, it) for i, it in enumerate(scene.fresing.flex) if it.enabled and not broken(scene, it)]


def _baked(scene) -> bool:
    return bool(scene.fresing.anim_baked)


# ---------------------------------------------------------------------------
# places: now, and in the CAD pose
# ---------------------------------------------------------------------------

def _np(m) -> np.ndarray:
    return np.array(m, dtype=float)


def _world(ob) -> Matrix:
    """The object's world matrix now. A part hidden in the view is not worked out by Blender (its matrix_world
    is old): its place comes from its parent's."""
    if not ob.hide_viewport:
        return ob.matrix_world
    if ob.parent is None:
        return ob.matrix_basis
    return _world(ob.parent) @ ob.matrix_parent_inverse @ ob.matrix_basis


def _cad_world(ob, memo: dict | None = None) -> np.ndarray:
    """Where the object is in the CAD pose (4 x 4, world): the CAD matrices up to the model's root, which stays
    where it is now (a model moved by its root keeps its place)."""
    memo = {} if memo is None else memo
    m = memo.get(ob.name)
    if m is not None:
        return m
    p = build.logical_parent(ob)
    if p is None or ob.get(build.PROP_ROOT):
        m = _np(_world(ob))
    else:
        m = _cad_world(p, memo) @ _np(build.cad_basis(ob))
    memo[ob.name] = m
    return m


def _mesh_arrays(me):
    """(points (V, 3), triangles (T, 3)) of a mesh datablock, in its own coordinates."""
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    return co.reshape(-1, 3).astype(float), tri.reshape(-1, 3).astype(np.int64)


def _at(m: np.ndarray, p) -> np.ndarray:
    """Points (..., 3) moved by the matrix (4, 4)."""
    return np.asarray(p, dtype=float) @ m[:3, :3].T + m[:3, 3]


def _distance(points: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """The smallest distance between the points (P, 3) and the triangles a, b, c ((T, 3) each)."""
    if not len(points) or not len(a):
        return math.inf
    best = math.inf
    step = max(1, 400000 // max(1, len(a)))
    for k in range(0, len(points), step):
        p = points[k:k + step, None, :]
        ab, ac = (b - a)[None], (c - a)[None]
        n = np.cross(ab, ac)
        nn = np.einsum("...i,...i", n, n)
        ap = p - a[None]
        with np.errstate(divide="ignore", invalid="ignore"):
            # inside the triangle (seen along its normal): the distance to its plane
            u = np.einsum("...i,...i", np.cross(ap, ac), n) / nn          # weight of b
            v = np.einsum("...i,...i", np.cross(ab, ap), n) / nn          # weight of c
            plane = np.abs(np.einsum("...i,...i", ap, n)) / np.sqrt(nn)
        inside = (nn > 0.0) & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0)
        d = np.where(inside, plane, math.inf)
        for s0, s1 in ((a, b), (b, c), (c, a)):                           # else the nearest edge
            e = (s1 - s0)[None]
            ee = np.einsum("...i,...i", e, e)
            w = p - s0[None]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.clip(np.where(ee > 0.0, np.einsum("...i,...i", w, e) / ee, 0.0), 0.0, 1.0)
            q = w - t[..., None] * e
            d = np.minimum(d, np.where(inside, math.inf, np.sqrt(np.einsum("...i,...i", q, q))))
        best = min(best, float(d.min()))
    return best


class _Near:
    """Finds the model part a point touches in the CAD pose. Made once per reading (it walks the scene)."""

    def __init__(self, scene, memo: dict | None = None):
        self.memo = {} if memo is None else memo
        skip = {ob.name for ob in flex_parts(scene)}
        self.parts = [ob for ob in build.iter_parts(scene) if ob.name not in skip and len(ob.data.vertices)]
        self.world = np.stack([_cad_world(ob, self.memo) for ob in self.parts]) if self.parts else np.zeros((0, 4, 4))
        box = np.array([[tuple(c) for c in ob.bound_box] for ob in self.parts], dtype=float).reshape(-1, 8, 3)
        corners = np.einsum("kij,kcj->kci", self.world[:, :3, :3], box) + self.world[:, None, :3, 3]
        self.lo, self.hi = corners.min(axis=1), corners.max(axis=1)
        self.size = np.linalg.norm(self.hi - self.lo, axis=1)
        self.meshes: dict = {}

    def touching(self, points, reach: float, but=()):
        """(part, distance) of the part nearest to ``points`` ((P, 3), CAD world) within ``reach``; (None, inf)
        when there is none. Parts about as near as the nearest: the smallest wins (a bracket, not the beam)."""
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        if not len(self.parts) or not len(points):
            return None, math.inf
        lo, hi = points.min(axis=0) - reach, points.max(axis=0) + reach
        near = np.nonzero(((self.lo <= hi) & (self.hi >= lo)).all(axis=1))[0]
        found = []
        for k in near:
            ob = self.parts[k]
            if ob.name in but:
                continue
            if ob.data.name not in self.meshes:
                self.meshes[ob.data.name] = _mesh_arrays(ob.data)
            verts, tris = self.meshes[ob.data.name]
            w = _at(self.world[k], verts)
            a, b, c = w[tris[:, 0]], w[tris[:, 1]], w[tris[:, 2]]
            tlo, thi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
            keep = ((tlo <= hi) & (thi >= lo)).all(axis=1)
            d = _distance(points, a[keep], b[keep], c[keep])
            if d <= reach:
                found.append((d, float(self.size[k]), ob.name, ob))
        if not found:
            return None, math.inf
        nearest = min(f[0] for f in found)
        d, _size, _name, ob = min((f for f in found if f[0] <= nearest + 0.001), key=lambda f: (f[1], f[2]))
        return ob, d


def _local_point(ob, memo, p) -> np.ndarray:
    return _at(np.linalg.inv(_cad_world(ob, memo)), p)


def _local_dir(ob, memo, d) -> np.ndarray:
    v = np.linalg.inv(_cad_world(ob, memo))[:3, :3] @ np.asarray(d, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 0.0 else np.array([1.0, 0.0, 0.0])


def _stay_part(part):
    """The object an end stays with when it touches no part: the part's place in the CAD tree."""
    return build.logical_parent(part) or part


# ---------------------------------------------------------------------------
# reading a hose
# ---------------------------------------------------------------------------

def _read_hose(scene, part, near: _Near | None = None) -> dict:
    """The hose's numbers from its CAD shape and place. Raises FlexError with a plain reason."""
    name = _part_name(part)
    if part is None or part.type != "MESH" or part.data is None:
        raise FlexError(f"'{name}' is not a hose: it has no shape to read.")
    verts, tris = _mesh_arrays(part.data)
    tube = flex_fit.tube_centreline(verts, tris)
    if not tube.ok:
        raise FlexError(f"'{name}' is not a hose: {tube.problem}")
    near = near or _Near(scene)
    memo = near.memo
    w = _cad_world(part, memo)
    scale = float(np.cbrt(abs(np.linalg.det(w[:3, :3])))) or 1.0
    radius = tube.radius * scale
    out = {"length": tube.length * scale * LENGTH_SPARE, "diameter": 2.0 * radius, "notes": []}
    line = _at(w, tube.points)
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))])
    ends = (("a", "A", tube.points[0], tube.t0, run), ("b", "B", tube.points[-1], tube.t1, run[-1] - run))
    for key, letter, point, along, from_end in ends:
        p = _at(w, point)
        d = w[:3, :3] @ along
        out[key + "_world"] = (p, d)
        ob, _dist = near.touching(p[None], radius + 0.002, but=(part.name,))
        if ob is None:                          # an end pushed deep into a block: where its last piece goes in
            ob, _dist = near.touching(line[from_end <= 6.0 * radius], radius + 0.002, but=(part.name,))
        if ob is None:
            ob = _stay_part(part)
            out["notes"].append(f"End {letter} of '{name}' touches no part: it stays with '{_part_name(ob)}'; "
                                "click the part it is fixed to, then the pipette beside that end in the panel")
        out[key + "_part"] = ob
    out["memo"] = memo
    return out


def _store_hose(item, part, geo: dict, keep_user: bool = False) -> None:
    """Write what was read into the item. ``keep_user``: a length or diameter the user changed stays."""
    user_length = keep_user and _user_set(item.length, item.cad_length)
    user_diameter = keep_user and _user_set(item.diameter, item.get("cad_diameter", 0.0))
    with _quiet(item):
        item.kind = "HOSE"
        item.part = part
        item.part_uid = part.get(build.PROP_UID, "")
        for key in ("a", "b"):
            ob = geo[key + "_part"]
            if keep_user and item.get(key + "_user") and getattr(item, key + "_part") is not None:
                ob = getattr(item, key + "_part")         # the user picked this end's part: it stays
            p, d = geo[key + "_world"]
            setattr(item, key + "_part", ob)
            setattr(item, key + "_uid", ob.get(build.PROP_UID, ""))
            setattr(item, key + "_point", tuple(_local_point(ob, geo["memo"], p)))
            setattr(item, key + "_dir", tuple(_local_dir(ob, geo["memo"], d)))
        item.cad_length = geo["length"]
        if not user_length:
            item.length = geo["length"]
        item["cad_diameter"] = float(geo["diameter"])
        if not user_diameter:
            item.diameter = geo["diameter"]
    part[TAG] = True


def _user_set(value: float, cad: float) -> bool:
    return cad > 0.0 and abs(value - cad) > USER_CHANGE * cad


def add_hose(scene, part, soft: bool = False):
    """Make ``part`` a hose (``soft``: a cable) that bends along with the motion. Returns (item, notes).

    Raises FlexError when the part is no hose (a block, a ring, several pieces) or is one already."""
    _check_free(scene, [part])
    geo = _read_hose(scene, part)
    s = scene.fresing
    item = s.flex.add()
    with _quiet(item):
        item.name = _unique(scene, _part_name(part))
        item.stiffness, item.sag, item.min_radius = (0.2, 0.8, 0.0) if soft else (0.6, 0.5, 0.0)
    _store_hose(item, part, geo)
    s.flex_index = len(s.flex) - 1
    _rebuild(scene)
    return s.flex[len(s.flex) - 1], geo["notes"]


def _check_free(scene, parts) -> None:
    for ob in parts:
        if ob is None or ob.type != "MESH" or ob.data is None:
            raise FlexError(f"'{_part_name(ob) or 'Nothing'}' is not a part with a shape.")
    taken = {}
    for it in scene.fresing.flex:
        for ob in parts_of(scene, it):
            taken[ob.name] = it
    for ob in parts:
        if ob.name in taken:
            raise FlexError(f"'{_part_name(ob)}' already follows the motion as '{label(taken[ob.name])}'.")


# ---------------------------------------------------------------------------
# reading a drag chain
# ---------------------------------------------------------------------------

def _movers(ob) -> frozenset:
    """The joints, cylinders and mechanisms that move the object (the names of their empties above it)."""
    out = []
    p = ob.parent
    while p is not None:
        if p.get(build.PROP_KIND) in build.JOINT_KINDS:
            out.append(p.name)
        p = p.parent
    return frozenset(out)


def _above(asm, ob) -> bool:
    """``asm`` is ``ob`` or above it in the CAD tree."""
    p = ob
    while p is not None:
        if p == asm:
            return True
        p = build.logical_parent(p)
    return False


def _fixed_is_b(link, a_ob, b_ob) -> bool:
    """True when end B is the end that is rigid with the links (so it should be the fixed one), and end A is not."""
    home_a, home_b = _movers(a_ob) == _movers(link), _movers(b_ob) == _movers(link)
    if home_a == home_b:                                  # no joint tells them apart: the CAD tree
        home = build.logical_parent(link)
        home_a = _above(build.logical_parent(a_ob) if a_ob.type == "MESH" else a_ob, home)
        home_b = _above(build.logical_parent(b_ob) if b_ob.type == "MESH" else b_ob, home)
    return home_b and not home_a


def _read_chain(scene, links: list, swapped: bool = False) -> dict:
    """What chain the CAD links are (any order). Raises FlexError with a plain reason."""
    near = _Near(scene)
    memo = near.memo
    mats = np.stack([_cad_world(ob, memo) for ob in links])
    centres = np.stack([_at(mats[k], np.array([tuple(c) for c in ob.bound_box], dtype=float).mean(axis=0))
                        for k, ob in enumerate(links)])
    kinds = {}
    types = [kinds.setdefault(ob.data.name, len(kinds)) for ob in links]
    fit = CH.fit_links(mats, centres, types)
    if not fit.ok:
        raise FlexError(f"These {plural(len(links), 'part')} cannot be read as a drag chain: {fit.problem}")
    notes = [fit.problem] if fit.problem else []
    names = tuple(ob.name for ob in links)
    reach = max(0.5 * fit.pitch, 0.005)

    def end_part(k: int, letter: str):
        ob = links[int(fit.order[k])]
        verts, _tris = _mesh_arrays(ob.data)
        pts = _at(mats[int(fit.order[k])], verts[::max(1, len(verts) // 96)])
        found, _d = near.touching(pts, reach, but=names)
        if found is None:
            found = _stay_part(ob)
            notes.append(f"The {letter} end of the chain touches no part: it stays with '{_part_name(found)}'; "
                         "click the part it is fixed to, then the pipette beside that end in the panel")
        return found

    a_ob, b_ob = end_part(0, "fixed"), end_part(-1, "moving")
    if _fixed_is_b(links[int(fit.order[0])], a_ob, b_ob) != bool(swapped):
        fit = fit.reversed()
        a_ob, b_ob = b_ob, a_ob
    return {"fit": fit, "links": [links[int(k)] for k in fit.order], "a_part": a_ob, "b_part": b_ob,
            "memo": memo, "notes": notes}


def _read_solid(scene, part, swapped: bool = False) -> dict:
    """A chain drawn as one solid: its band read as runs and a bend. Raises FlexError."""
    name = _part_name(part)
    near = _Near(scene)
    memo = near.memo
    verts, _tris = _mesh_arrays(part.data)
    pts = _at(_cad_world(part, memo), verts)
    fit = CH.fit_solid(pts)
    if not fit.ok:
        raise FlexError(f"'{name}': {fit.problem}")
    notes = []
    reach = max(0.5 * fit.pitch, fit.height, 0.005)

    def end_part(pin, letter: str):
        close = pts[np.linalg.norm(pts - pin, axis=1) < max(fit.pitch, fit.height)]
        found, _d = near.touching(close[::max(1, len(close) // 96)] if len(close) else pin[None], reach,
                                  but=(part.name,))
        if found is None:
            found = _stay_part(part)
            notes.append(f"The {letter} end of the chain touches no part: it stays with '{_part_name(found)}'; "
                         "click the part it is fixed to, then the pipette beside that end in the panel")
        return found

    a_ob, b_ob = end_part(fit.pins[0], "fixed"), end_part(fit.pins[-1], "moving")
    if _fixed_is_b(part, a_ob, b_ob) != bool(swapped):
        fit = fit.reversed()
        a_ob, b_ob = b_ob, a_ob
    return {"fit": fit, "links": [], "a_part": a_ob, "b_part": b_ob, "memo": memo, "notes": notes}


def _store_chain(item, geo: dict, part=None, keep_user: bool = False) -> None:
    fit, memo = geo["fit"], geo["memo"]
    made = part is not None
    user = {}
    if keep_user:                                         # numbers the user set by hand stay
        for key in ("pitch", "radius"):
            if _user_set(getattr(item, key), item.get("cad_" + key, 0.0)):
                user[key] = getattr(item, key)
        if item.get("cad_mode") and item.mode != item.get("cad_mode"):
            user["mode"] = item.mode
        if made and item.get("cad_count") and item.count != item.get("cad_count"):
            user["count"] = item.count
        for key in ("width", "height"):
            if made and _user_set(getattr(item, key), item.get("cad_" + key, 0.0)):
                user[key] = getattr(item, key)
    with _quiet(item):
        item.kind = "CHAIN"
        item.made_links = made
        item.part = part
        item.part_uid = part.get(build.PROP_UID, "") if made else ""
        item.links.clear()
        for ob in geo["links"]:
            item.links.add().obj = ob
        item.link_uids = "\n".join(ob.get(build.PROP_UID, "") for ob in geo["links"])
        ends = (("a", geo["a_part"]), ("b", geo["b_part"]))
        for key, ob in ends:
            if keep_user and item.get(key + "_user") and getattr(item, key + "_part") is not None:
                ob = getattr(item, key + "_part")         # the user picked this end's part: it stays
            setattr(item, key + "_part", ob)
            setattr(item, key + "_uid", ob.get(build.PROP_UID, ""))
        frame = np.linalg.inv(_cad_world(item.a_part, memo)) @ fit.frame
        item.frame = tuple(frame.reshape(-1))
        item.a_point = tuple(frame[:3, 3])
        item.b_point = tuple(_local_point(item.b_part, memo, fit.pins[-1]))
        item.pitch, item.radius, item.count, item.mode = fit.pitch, fit.radius, fit.links, fit.mode
        item["cad_pitch"], item["cad_radius"] = float(fit.pitch), float(fit.radius)
        item["cad_mode"], item["cad_count"] = fit.mode, int(fit.links)
        if made:
            if fit.width > 0.0:
                item.width = fit.width
            if fit.height > 0.0:
                item.height = fit.height
            item["cad_width"], item["cad_height"] = float(item.width), float(item.height)
        for key, value in user.items():
            setattr(item, key, value)
    for k, ob in enumerate(geo["links"]):
        idprops.store_array(ob, LOCAL, fit.local[k])
        ob[TAG] = True
    if made:
        part[TAG] = True


def add_chain(scene, links: list, part=None):
    """A drag chain from its CAD ``links`` (any order), or from ``part``: a chain drawn as one solid, along which
    the app draws links. Returns (item, notes). Raises FlexError when the parts are no chain."""
    links = [ob for ob in (links or []) if ob is not None]
    if links:
        part = None
        _check_free(scene, links)
        geo = _read_chain(scene, links)
        base = _part_name(build.logical_parent(geo["links"][0])) or _part_name(geo["links"][0])
    elif part is not None:
        _check_free(scene, [part])
        geo = _read_solid(scene, part)
        base = _part_name(part)
    else:
        raise FlexError("Pick the chain's links, or the one part the chain is drawn as.")
    s = scene.fresing
    item = s.flex.add()
    with _quiet(item):
        item.name = _unique(scene, base or "Drag chain")
    _store_chain(item, geo, part)
    s.flex_index = len(s.flex) - 1
    _rebuild(scene)
    return s.flex[len(s.flex) - 1], geo["notes"]


def swap_ends(scene, item) -> None:
    """A chain: the other end is the fixed one. (Read from the CAD pose again; numbers set by hand stay.)"""
    if item.kind != "CHAIN" or broken(scene, item) in ("a link is gone", "its part is gone"):
        return
    swapped = not bool(item.get("swapped"))
    with _quiet(item):
        for key in ("a_user", "b_user"):
            if key in item:
                del item[key]
    geo = _read_solid(scene, item.part, swapped) if item.made_links else _read_chain(scene, link_objects(item), swapped)
    _store_chain(item, geo, item.part if item.made_links else None, keep_user=True)
    item["swapped"] = swapped
    _rebuild(scene)


def fit_to_cad(scene, item) -> list[str]:
    """Reset: the length, the ends, the pitch, the radius … as the CAD pose has them. Stiffness, sag and the
    smallest bend stay. Returns notes."""
    for key in ("a_user", "b_user", "swapped"):
        if key in item:
            del item[key]
    if item.kind == "HOSE":
        if not _alive(scene, item.part):
            return [f"{_word(item)} '{label(item)}': its part is gone"]
        geo = _read_hose(scene, item.part)
        _store_hose(item, item.part, geo)
    else:
        if item.made_links:
            if not _alive(scene, item.part):
                return [f"{_word(item)} '{label(item)}': its part is gone"]
            geo = _read_solid(scene, item.part)
        else:
            links = [ob for ob in link_objects(item) if _alive(scene, ob)]
            geo = _read_chain(scene, links)
        _store_chain(item, geo, item.part if item.made_links else None)
    _rebuild(scene)
    return geo["notes"]


def set_end_part(scene, item, end: str, ob) -> None:
    """End "A" or "B" sits on another part from now on (at the same place in the world as it is now)."""
    key = "a" if str(end).upper() == "A" else "b"
    old = getattr(item, key + "_part")
    if ob is None or ob == old:
        return
    was = _np(_world(old)) if old is not None else _np(_world(ob))
    to_new = np.linalg.inv(_np(_world(ob))) @ was
    with _quiet(item):
        setattr(item, key + "_part", ob)
        setattr(item, key + "_uid", ob.get(build.PROP_UID, ""))
        if item.kind == "CHAIN" and key == "a":
            frame = to_new @ np.array(item.frame, dtype=float).reshape(4, 4)
            item.frame = tuple(frame.reshape(-1))
            item.a_point = tuple(frame[:3, 3])
        else:
            setattr(item, key + "_point", tuple(_at(to_new, np.array(getattr(item, key + "_point")))))
            d = to_new[:3, :3] @ np.array(getattr(item, key + "_dir"))
            setattr(item, key + "_dir", tuple(d / (np.linalg.norm(d) or 1.0)))
        item[key + "_user"] = True
    _rebuild(scene)


def remove(scene, index: int) -> None:
    """Take the item off the list: its parts show their CAD shape again."""
    s = scene.fresing
    if not 0 <= index < len(s.flex):
        return
    item = s.flex[index]
    for ob in parts_of(scene, item):
        _strip(ob)
    _remove_made_link(item)
    s.flex.remove(index)
    s.flex_index = max(0, min(s.flex_index, len(s.flex) - 1))
    forget()
    if len(s.flex):
        _rebuild(scene)
    else:
        _remove_shapes(scene)


def _strip(ob) -> None:
    """A part is no flex part any more: modifier, tag and link matrix off."""
    try:
        mod = ob.modifiers.get(MOD)
        if mod is not None:
            ob.modifiers.remove(mod)
        for key in (TAG, LOCAL):
            if key in ob:
                del ob[key]
    except ReferenceError:
        pass


# ---------------------------------------------------------------------------
# the link the app draws (a chain that is one solid)
# ---------------------------------------------------------------------------

def _prism(outline: np.ndarray, z0: float, z1: float):
    """A flat outline (k, 2) in x, y pushed out from z0 to z1: (points, faces), faces looking outward."""
    x, y = outline[:, 0], outline[:, 1]
    if float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) < 0.0:
        outline = outline[::-1]
    k = len(outline)
    pts = [(float(px), float(py), z0) for px, py in outline] + [(float(px), float(py), z1) for px, py in outline]
    faces = [tuple(range(k - 1, -1, -1)), tuple(range(k, 2 * k))]
    faces += [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
    return pts, faces


def _made_link_data(pitch: float, width: float, height: float):
    """Points and faces of one app-made link in its pin frame: its first pin at the origin, x to the next pin, y
    from the fixed run towards the moving run, z across the chain. Two cranked side plates (the rear half sits
    inside the next link's front half, as real links do) and a bar at the top and at the bottom."""
    r = 0.5 * height
    t = min(max(0.06 * width, 0.0006), 0.2 * width)
    arc = np.linspace(0.5 * math.pi, 1.5 * math.pi, 9)
    rear = np.concatenate([[(0.62 * pitch, r)], np.stack([r * np.cos(arc), r * np.sin(arc)], axis=1),
                           [(0.62 * pitch, -r)]])
    front = np.stack([pitch - rear[:, 0], rear[:, 1]], axis=1)
    bar = 0.16 * height
    box = np.array([(0.3 * pitch, 0.0), (0.7 * pitch, 0.0), (0.7 * pitch, bar), (0.3 * pitch, bar)])
    pieces = []
    for side in (1.0, -1.0):
        z_in, z_mid, z_out = side * (0.5 * width - 2.0 * t), side * (0.5 * width - t), side * 0.5 * width
        pieces.append(_prism(rear, min(z_in, z_mid), max(z_in, z_mid)))
        pieces.append(_prism(front, min(z_mid, z_out), max(z_mid, z_out)))
    inner = 0.5 * width - 1.5 * t
    pieces.append(_prism(box + (0.0, r - bar), -inner, inner))
    pieces.append(_prism(box + (0.0, -r), -inner, inner))
    pts, faces = [], []
    for p, f in pieces:
        faces += [tuple(i + len(pts) for i in face) for face in f]
        pts += p
    return pts, faces


def _made_link_name(item) -> str:
    return item.get("link_name", "") or ""


def _made_link(scene, item):
    """The object of the app-made link of this chain (made or made again when its sizes changed)."""
    dims = (round(float(item.pitch), 6), round(float(item.width), 6), round(float(item.height), 6))
    ob = bpy.data.objects.get(_made_link_name(item)) if _made_link_name(item) else None
    if ob is not None and tuple(round(float(v), 6) for v in ob.get("fr_flex_dims", ())) == dims:
        return ob
    pts, faces = _made_link_data(*dims)
    me = bpy.data.meshes.new(f"{MADE_LINK} {label(item)}")
    me[TAG] = True
    me.from_pydata(pts, [], faces)
    me.update()
    if ob is None:
        ob = bpy.data.objects.new(f"{MADE_LINK} {label(item)}", me)
        ob[TAG] = True
        ob.hide_viewport = ob.hide_render = ob.hide_select = True
        _collection(scene).objects.link(ob)
        item["link_name"] = ob.name
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    ob["fr_flex_dims"] = list(dims)
    return ob


def _remove_made_link(item) -> None:
    ob = bpy.data.objects.get(_made_link_name(item)) if _made_link_name(item) else None
    if ob is None:
        return
    me = ob.data
    bpy.data.objects.remove(ob)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------
# the node trees (shared by all items)
# ---------------------------------------------------------------------------

class _Nodes:
    """A few short hands for building a node tree."""

    def __init__(self, ng):
        self.ng, self.count = ng, 0

    def new(self, idname: str, **props):
        n = self.ng.nodes.new(idname)
        for key, value in props.items():
            setattr(n, key, value)
        n.location = (200 * (self.count % 8), -220 * (self.count // 8))
        self.count += 1
        return n

    def link(self, a, b) -> None:
        self.ng.links.new(a, b)


def _sock(sockets, name: str, k: int = 0):
    """The k-th usable socket with this name (a node keeps one per data type; only one is in use)."""
    hits = [s for s in sockets if s.name == name and s.enabled and not getattr(s, "is_unavailable", False)]
    return hits[k]


def _moment(b: _Nodes, gin):
    """The index of the first point of this modifier's slice at the frame shown:
    clamp(round(frame - First), 0, Frames - 1) * Per frame + Offset."""
    time = b.new("GeometryNodeInputSceneTime")
    sub = b.new("ShaderNodeMath", operation="SUBTRACT")
    b.link(time.outputs["Frame"], sub.inputs[0])
    b.link(gin.outputs["First"], sub.inputs[1])
    rnd = b.new("ShaderNodeMath", operation="ROUND")
    b.link(sub.outputs[0], rnd.inputs[0])
    low = b.new("FunctionNodeIntegerMath", operation="MAXIMUM")
    b.link(rnd.outputs[0], low.inputs[0])
    low.inputs[1].default_value = 0
    last = b.new("FunctionNodeIntegerMath", operation="SUBTRACT")
    b.link(gin.outputs["Frames"], last.inputs[0])
    last.inputs[1].default_value = 1
    high = b.new("FunctionNodeIntegerMath", operation="MINIMUM")
    b.link(low.outputs[0], high.inputs[0])
    b.link(last.outputs[0], high.inputs[1])
    base = b.new("FunctionNodeIntegerMath", operation="MULTIPLY_ADD")
    b.link(high.outputs[0], base.inputs[0])
    b.link(gin.outputs["Per frame"], base.inputs[1])
    b.link(gin.outputs["Offset"], base.inputs[2])
    return base.outputs[0]


def _shapes_geometry(b: _Nodes, gin):
    info = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Shapes"], info.inputs["Object"])
    return info.outputs["Geometry"]


def _to_own_space(b: _Nodes):
    """World -> the part's own space: the inverse of its own transform."""
    me = b.new("GeometryNodeSelfObject")
    info = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(me.outputs[0], info.inputs["Object"])
    inv = b.new("FunctionNodeInvertMatrix")
    b.link(info.outputs["Transform"], inv.inputs[0])
    return inv.outputs["Matrix"]


def _sample(b: _Nodes, geometry, index, attribute: str = ""):
    """The shapes mesh's position (or a vector attribute) at a point index."""
    s = b.new("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT")
    b.link(geometry, s.inputs["Geometry"])
    b.link(index, s.inputs["Index"])
    if attribute:
        src = b.new("GeometryNodeInputNamedAttribute", data_type="FLOAT_VECTOR")
        src.inputs["Name"].default_value = attribute
        b.link(_sock(src.outputs, "Attribute"), _sock(s.inputs, "Value"))
    else:
        src = b.new("GeometryNodeInputPosition")
        b.link(src.outputs[0], _sock(s.inputs, "Value"))
    return _sock(s.outputs, "Value")


def _line(b: _Nodes, gin, base):
    """``Count`` points at this slice's places (world), and the index of each in the shapes mesh."""
    line = b.new("GeometryNodeMeshLine")
    b.link(gin.outputs["Count"], line.inputs["Count"])
    line.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
    own = b.new("GeometryNodeInputIndex")
    index = b.new("FunctionNodeIntegerMath", operation="ADD")
    b.link(base, index.inputs[0])
    b.link(own.outputs[0], index.inputs[1])
    return line.outputs["Mesh"], index.outputs[0]


def _build_hose(ng) -> None:
    """The part's shape is replaced by a round tube along its slice of the shapes mesh."""
    b = _Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    shapes = _shapes_geometry(b, gin)
    line, index = _line(b, gin, _moment(b, gin))
    here = b.new("FunctionNodeTransformPoint")
    b.link(_sample(b, shapes, index), here.inputs["Vector"])
    b.link(_to_own_space(b), here.inputs["Transform"])
    place = b.new("GeometryNodeSetPosition")
    b.link(line, place.inputs["Geometry"])
    b.link(here.outputs[0], place.inputs["Position"])
    curve = b.new("GeometryNodeMeshToCurve")
    b.link(place.outputs[0], curve.inputs["Mesh"])
    kind = b.new("GeometryNodeCurveSplineType", spline_type="CATMULL_ROM")
    b.link(curve.outputs[0], kind.inputs["Curve"])
    fine = b.new("GeometryNodeSetSplineResolution")
    b.link(kind.outputs[0], fine.inputs[0])
    fine.inputs["Resolution"].default_value = SMOOTH
    circle = b.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = SIDES
    b.link(gin.outputs["Radius"], circle.inputs["Radius"])
    tube = b.new("GeometryNodeCurveToMesh")
    b.link(fine.outputs[0], tube.inputs["Curve"])
    b.link(circle.outputs["Curve"], tube.inputs["Profile Curve"])
    tube.inputs["Fill Caps"].default_value = True
    smooth = b.new("GeometryNodeSetShadeSmooth", domain="FACE")
    b.link(tube.outputs[0], smooth.inputs[0])
    edge = b.new("GeometryNodeInputMeshEdgeAngle")                # the rim of the end caps stays a sharp edge
    soft = b.new("FunctionNodeCompare", data_type="FLOAT", operation="LESS_THAN")
    b.link(edge.outputs["Unsigned Angle"], soft.inputs[0])
    soft.inputs[1].default_value = 1.0
    rim = b.new("GeometryNodeSetShadeSmooth", domain="EDGE")
    b.link(smooth.outputs[0], rim.inputs[0])
    b.link(soft.outputs[0], rim.inputs["Shade Smooth"])
    b.link(_slot(b, rim.outputs[0]), gout.inputs[0])


def _slot(b: _Nodes, geometry):
    """A shape made by nodes has no material slot, and then the part's own material is not used (it renders
    without one). An empty Set Material gives it slot 0, which the part fills (materials hang on the object)."""
    mat = b.new("GeometryNodeSetMaterial")
    b.link(geometry, mat.inputs["Geometry"])
    return mat.outputs[0]


def _rotation(b: _Nodes, x, z):
    rot = b.new("FunctionNodeAxesToRotation", primary_axis="X", secondary_axis="Z")
    b.link(x, rot.inputs["Primary Axis"])
    b.link(z, rot.inputs["Secondary Axis"])
    return rot.outputs[0]


def _move(b: _Nodes, geometry, matrix):
    tr = b.new("GeometryNodeTransform")
    tr.inputs["Mode"].default_value = "Matrix"
    b.link(geometry, tr.inputs["Geometry"])
    b.link(matrix, tr.inputs["Transform"])
    return tr.outputs[0]


def _build_link(ng) -> None:
    """A CAD link: its own shape, moved to the place its point of the shapes mesh gives."""
    b = _Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    shapes = _shapes_geometry(b, gin)
    base = _moment(b, gin)
    place = b.new("FunctionNodeCombineTransform")
    b.link(_sample(b, shapes, base), place.inputs["Translation"])
    b.link(_rotation(b, _sample(b, shapes, base, "fr_x"), _sample(b, shapes, base, "fr_z")), place.inputs["Rotation"])
    both = b.new("FunctionNodeMatrixMultiply")
    b.link(_to_own_space(b), both.inputs[0])
    b.link(place.outputs[0], both.inputs[1])
    b.link(_move(b, gin.outputs["Geometry"], both.outputs[0]), gout.inputs[0])


def _build_chain(ng) -> None:
    """A chain that is one solid: the app-made link (``Link``) drawn at every point of the slice."""
    b = _Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    shapes = _shapes_geometry(b, gin)
    line, index = _line(b, gin, _moment(b, gin))
    place = b.new("GeometryNodeSetPosition")
    b.link(line, place.inputs["Geometry"])
    b.link(_sample(b, shapes, index), place.inputs["Position"])
    link = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Link"], link.inputs["Object"])
    inst = b.new("GeometryNodeInstanceOnPoints")
    b.link(place.outputs[0], inst.inputs["Points"])
    b.link(link.outputs["Geometry"], inst.inputs["Instance"])
    b.link(_rotation(b, _sample(b, shapes, index, "fr_x"), _sample(b, shapes, index, "fr_z")), inst.inputs["Rotation"])
    real = b.new("GeometryNodeRealizeInstances")
    b.link(inst.outputs[0], real.inputs[0])
    b.link(_slot(b, _move(b, real.outputs[0], _to_own_space(b))), gout.inputs[0])


_BUILDERS = {"HOSE": _build_hose, "LINK": _build_link, "CHAIN": _build_chain}


def _tree(kind: str):
    """The shared node tree for hoses, CAD links or solid chains; made (again) when missing or of an older version."""
    name = TREES[kind]
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get(TAG) == VERSION:
        return ng
    if ng is not None:
        ng.name = name + " old"
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng[TAG] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for label_, kind_ in _INPUTS:
        ng.interface.new_socket(label_, in_out="INPUT", socket_type=kind_)
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    _BUILDERS[kind](ng)
    _STATE["inputs"].pop(name, None)
    return ng


def _inputs(ng) -> dict:
    """Input name -> the identifier a modifier keeps its value under."""
    out = _STATE["inputs"].get(ng.name)
    if out is None:
        out = {s.name: s.identifier for s in ng.interface.items_tree
               if getattr(s, "item_type", "SOCKET") == "SOCKET" and s.in_out == "INPUT"}
        _STATE["inputs"][ng.name] = out
    return out


def _put(mod, identifier: str, value) -> bool:
    """Set a modifier input, only when it changes. True when it did."""
    slot = getattr(mod.properties.inputs, identifier)
    cur = slot.value
    if isinstance(value, float):
        same = cur is not None and abs(float(cur) - value) < 1e-9
    else:
        same = cur == value
    if not same:
        slot.value = value
    return not same


# ---------------------------------------------------------------------------
# the shapes mesh
# ---------------------------------------------------------------------------

def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col.hide_select = True
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _shapes(scene, create: bool = False):
    ob = scene.get(_KEY)
    if not isinstance(ob, bpy.types.Object):
        ob = None
    if ob is None and create:
        me = bpy.data.meshes.new(SHAPES)
        me[TAG] = True
        ob = bpy.data.objects.new(SHAPES, me)
        ob[TAG] = True
        ob.hide_viewport = ob.hide_render = ob.hide_select = True
        _collection(scene).objects.link(ob)
        scene[_KEY] = ob
    return ob


def _remove_shapes(scene) -> None:
    """The last item is gone: the shapes mesh, the collection and the unused node trees go too."""
    ob = _shapes(scene)
    if _KEY in scene:
        del scene[_KEY]
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and not len(col.objects) and not len(col.children):
        bpy.data.collections.remove(col)
    _drop_unused_trees()
    forget()


def _drop_unused_trees() -> None:
    for ng in [g for g in bpy.data.node_groups if g.get(TAG) is not None and g.users == 0]:
        bpy.data.node_groups.remove(ng)
    _STATE["inputs"].clear()


def _layout(scene) -> int:
    """Give every item its slice of a moment; returns the points per moment."""
    offset = 0
    for it in scene.fresing.flex:
        if broken(scene, it):
            n = 0
        elif it.kind == "HOSE":
            n = DRAWN
        else:
            n = int(it.count) if it.made_links else len(it.links)
        if it.offset != offset or it.points != n:
            with _quiet(it):
                it.offset, it.points = offset, n
        offset += n
    return offset


def _layout_of(sh) -> tuple:
    """(frames, points per moment, first frame) the shapes mesh holds now."""
    if sh is None:
        return 0, 0, 0
    return int(sh.get(_FRAMES, 0)), int(sh.get(_PER, 0)), int(sh.get(_FIRST, 0))


def _arrays(scene, frames: int, per: int):
    """The shapes mesh's numbers as arrays (frames, per, 3): places, X axes, Z axes. None when it holds another
    layout."""
    sh = _shapes(scene)
    if sh is None or _layout_of(sh)[:2] != (frames, per) or len(sh.data.vertices) != frames * per:
        return None
    hit = _STATE["arrays"].get(scene.name)
    if hit is not None and hit[0].shape == (frames, per, 3):
        return hit
    me = sh.data
    out = []
    x, z = me.attributes["fr_x"].data, me.attributes["fr_z"].data
    for coll, key in ((me.vertices, "co"), (x, "vector"), (z, "vector")):
        a = np.empty(frames * per * 3, np.float32)
        coll.foreach_get(key, a)
        out.append(a.reshape(frames, per, 3))
    _STATE["arrays"][scene.name] = tuple(out)
    return _STATE["arrays"][scene.name]


def _write_shapes(scene, arrays, first: int) -> None:
    co, fx, fz = arrays
    frames, per = co.shape[0], co.shape[1]
    sh = _shapes(scene, create=True)
    me = sh.data
    if len(me.vertices) != frames * per or "fr_x" not in me.attributes:
        new = bpy.data.meshes.new(SHAPES)
        new[TAG] = True
        new.vertices.add(frames * per)
        new.attributes.new("fr_x", "FLOAT_VECTOR", "POINT")
        new.attributes.new("fr_z", "FLOAT_VECTOR", "POINT")
        sh.data = new
        if me.users == 0:
            bpy.data.meshes.remove(me)
        me = new
    if frames * per:
        me.vertices.foreach_set("co", np.ascontiguousarray(co, np.float32).reshape(-1))
        me.attributes["fr_x"].data.foreach_set("vector", np.ascontiguousarray(fx, np.float32).reshape(-1))
        me.attributes["fr_z"].data.foreach_set("vector", np.ascontiguousarray(fz, np.float32).reshape(-1))
    me.update_tag()                             # (points only: nothing for mesh.update() to work out)
    for key, value in ((_FRAMES, frames), (_PER, per), (_FIRST, int(first))):
        if sh.get(key) != value:
            sh[key] = value
    if sh.parent is not None:
        sh.parent = None
    if sh.matrix_basis != Matrix.Identity(4):
        sh.matrix_basis = Matrix.Identity(4)
    _STATE["arrays"][scene.name] = (co, fx, fz)


def _sync(scene) -> None:
    """Every flex part has its modifier with the inputs of its slice; items that are off or broken show their CAD
    shape (modifier off)."""
    sh = _shapes(scene)
    frames, per, first = _layout_of(sh)
    for it in scene.fresing.flex:
        on = bool(it.enabled) and not broken(scene, it) and sh is not None
        if it.kind == "HOSE":
            kind = "HOSE"
        else:
            kind = "CHAIN" if it.made_links else "LINK"
        link = _made_link(scene, it) if (on and kind == "CHAIN") else None
        tree = _tree(kind) if on else None
        ins = _inputs(tree) if on else {}
        for k, ob in enumerate(parts_of(scene, it)):
            if not _alive(scene, ob):
                continue
            mod = ob.modifiers.get(MOD)
            if not on:
                if mod is not None and (mod.show_viewport or mod.show_render):
                    mod.show_viewport = mod.show_render = False
                continue
            if mod is None or mod.type != "NODES":
                if mod is not None:
                    ob.modifiers.remove(mod)
                mod = ob.modifiers.new(MOD, "NODES")
                if len(ob.modifiers) > 1:                 # first: what comes after works on the shape drawn
                    ob.modifiers.move(len(ob.modifiers) - 1, 0)
            changed = False
            if mod.node_group != tree:
                mod.node_group = tree
                changed = True
            values = {"Shapes": sh, "First": first, "Frames": frames, "Per frame": per,
                      "Offset": int(it.offset) + (k if kind == "LINK" else 0),
                      "Count": 1 if kind == "LINK" else int(it.points),
                      "Radius": 0.5 * float(it.diameter), "Link": link}
            for name, value in values.items():
                changed |= _put(mod, ins[name], value)
            if not (mod.show_viewport and mod.show_render):
                mod.show_viewport = mod.show_render = True
            if ob.get(TAG) is None:
                ob[TAG] = True
            if changed:
                ob.update_tag()
    old = [g for g in bpy.data.node_groups if g.get(TAG) is not None and g.get(TAG) != VERSION and g.users == 0]
    for ng in old:
        bpy.data.node_groups.remove(ng)


# ---------------------------------------------------------------------------
# solving
# ---------------------------------------------------------------------------

def _end_names(its) -> list:
    return sorted({ob.name for _i, it in its for ob in (it.a_part, it.b_part)})


def _places_now(its) -> dict:
    """Object name -> its world matrix now, as (1, 4, 4), for the end parts of these items."""
    out = {}
    for _i, it in its:
        for ob in (it.a_part, it.b_part):
            if ob.name not in out:
                out[ob.name] = _np(_world(ob))[None]
    return out


def _mm(metres: float) -> str:
    mm = metres * 1000.0
    return f"{mm:.1f}" if abs(mm) < 10.0 else f"{mm:.0f}"


def _solve(its, mats: dict, frames: int):
    """The shapes of these items at ``frames`` moments. ``mats``: end part name -> (frames, 4, 4) world matrices.

    Returns ({item index: (places, X axes, Z axes)}, {item index: (what, moment, number)}): arrays
    (frames, points, 3); a problem names the first moment it happens at ("short" with the most length missing
    at any moment, "tight" with the limit, "reach")."""
    out, problems = {}, {}
    hoses = [(i, it) for i, it in its if it.kind == "HOSE"]
    if hoses:
        from ..core import flex as HS
        h = len(hoses)
        p0, t0, p1, t1 = (np.empty((frames, h, 3)) for _ in range(4))
        length, stiff, sag, rmin = (np.empty((frames, h)) for _ in range(4))
        for k, (_i, it) in enumerate(hoses):
            a, b = mats[it.a_part.name], mats[it.b_part.name]
            p0[:, k] = np.array(it.a_point) @ a[:, :3, :3].transpose(0, 2, 1) + a[:, :3, 3]
            t0[:, k] = np.array(it.a_dir) @ a[:, :3, :3].transpose(0, 2, 1)
            p1[:, k] = np.array(it.b_point) @ b[:, :3, :3].transpose(0, 2, 1) + b[:, :3, 3]
            t1[:, k] = np.array(it.b_dir) @ b[:, :3, :3].transpose(0, 2, 1)
            length[:, k] = it.length
            stiff[:, k] = HS.stiff_length(it.diameter, it.stiffness)
            sag[:, k] = it.sag
            rmin[:, k] = it.min_radius
        if frames > 1:
            # the frames of a built animation, in their order: each hose keeps one shape along the motion where it
            # can (a slack hose often has two, and solved frame by frame it would jump from one to the other once)
            pts = np.empty((frames, h, POINTS, 3))
            short, tight = (np.zeros((frames, h), dtype=bool) for _ in range(2))
            need = np.empty((frames, h))
            for k in range(h):
                r = HS.solve_motion(p0[:, k], t0[:, k], p1[:, k], t1[:, k], length[:, k], stiff[:, k], sag[:, k],
                                    rmin[:, k], n=POINTS)
                pts[:, k], short[:, k], need[:, k], tight[:, k] = r.points, r.short, r.need, r.tight
        else:
            r = HS.solve_hoses(p0.reshape(-1, 3), t0.reshape(-1, 3), p1.reshape(-1, 3), t1.reshape(-1, 3),
                               length.reshape(-1), stiff.reshape(-1), sag.reshape(-1), rmin.reshape(-1), n=POINTS)
            pts = r.points.reshape(frames, h, POINTS, 3)
            short, need, tight = (x.reshape(frames, h) for x in (r.short, r.need, r.tight))
        _STATE["solves"] += frames * h
        zero = np.zeros((frames, DRAWN, 3))
        for k, (i, it) in enumerate(hoses):
            out[i] = (_with_ends(pts[:, k]), zero, zero)
            if short[:, k].any():               # the first moment it happens, and the most it is short by
                problems[i] = ("short", int(np.argmax(short[:, k])),
                               float((need[:, k] - it.length)[short[:, k]].max()))
            elif tight[:, k].any():
                problems[i] = ("tight", int(np.argmax(tight[:, k])), float(it.min_radius))
    for i, it in its:
        if it.kind != "CHAIN":
            continue
        a, b = mats[it.a_part.name], mats[it.b_part.name]
        frame = a @ np.array(it.frame, dtype=float).reshape(4, 4)               # chain -> world, per moment
        end = np.array(it.b_point) @ b[:, :3, :3].transpose(0, 2, 1) + b[:, :3, 3]
        inv = np.linalg.inv(frame)
        moving = np.einsum("fij,fj->fi", inv[:, :3, :3], end) + inv[:, :3, 3]
        count = int(it.count) if it.made_links else len(it.links)
        spec = CH.ChainSpec(float(it.pitch), count, float(it.radius), it.mode)
        c = CH.chain_pins(spec, moving)
        _STATE["solves"] += frames
        if it.made_links:
            m = frame[:, None] @ CH.pin_matrices(c.pins)
        else:
            local = np.stack([np.array(ob[LOCAL], dtype=float).reshape(4, 4) for ob in link_objects(it)])
            m = CH.link_matrices(c.pins, local, frame[:, None])
        x, z = m[..., :3, 0], m[..., :3, 2]
        x = x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)
        z = z / np.maximum(np.linalg.norm(z, axis=-1, keepdims=True), 1e-12)
        out[i] = (m[..., :3, 3], x, z)
        if c.short.any():
            problems[i] = ("reach", int(np.argmax(c.short)), 0.0)
    return out, problems


def _with_ends(pts: np.ndarray) -> np.ndarray:
    """(..., POINTS, 3) -> (..., DRAWN, 3): one more point on the first and on the last piece, close to the end.
    The tube is drawn as a smooth curve through the points; with three points in a line at each end it leaves
    its fittings exactly along the solver's first and last piece."""
    out = np.empty(pts.shape[:-2] + (DRAWN, 3))
    out[..., 0, :], out[..., 2:-2, :], out[..., -1, :] = pts[..., 0, :], pts[..., 1:-1, :], pts[..., -1, :]
    out[..., 1, :] = pts[..., 0, :] + END_SHARE * (pts[..., 1, :] - pts[..., 0, :])
    out[..., -2, :] = pts[..., -1, :] + END_SHARE * (pts[..., -2, :] - pts[..., -1, :])
    return out


def _problem_texts(item, problem, frame) -> tuple:
    """(the short text for the list, the warning sentence) of a problem; ``frame`` None = in the pose shown."""
    what, _k, number = problem
    when = "in this pose" if frame is None else f"at frame {frame}"
    name = label(item)
    if what == "short":
        return (f"too short {when}: needs {_mm(number)} mm more",
                f"Hose '{name}' is too short {when} (it needs {_mm(number)} mm more)")
    if what == "tight":
        return (f"bends tighter than {_mm(number)} mm {when}",
                f"Hose '{name}' bends tighter than {_mm(number)} mm {when}")
    return f"cannot reach {when}", f"Drag chain '{name}' cannot reach {when}"


def _note_problems(scene, its, problems: dict, first) -> list[str]:
    """Write each item's problem (or clear it); returns the warning sentences. ``first``: the frame of moment 0,
    None for the pose shown."""
    warnings = []
    for i, it in its:
        text, frame = "", 0
        if i in problems:
            frame = 0 if first is None else first + problems[i][1]
            text, sentence = _problem_texts(it, problems[i], None if first is None else frame)
            warnings.append(sentence)
        if it.problem != text or it.problem_frame != frame:
            with _quiet(it):
                it.problem, it.problem_frame = text, frame
    return warnings


def _patch(arrays, it, result) -> None:
    lo, n = int(it.offset), int(it.points)
    for dst, src in zip(arrays, result):
        dst[:, lo:lo + n] = src


def _moved(scene) -> list:
    """[(item index, key)] of the items that are on and whose end parts are not where they were solved for.
    (Runs after every update: it reads two matrices per item and nothing else.)"""
    out = []
    last = _STATE["last"]
    name = scene.name
    for i, it in enumerate(scene.fresing.flex):
        if not it.enabled:
            continue
        a, b = it.a_part, it.b_part
        if a is None or b is None:
            continue
        key = _np(_world(a)).tobytes() + _np(_world(b)).tobytes()
        if last.get((name, i)) != key:
            out.append((i, key))
    return out


def _live(scene, force: bool = False) -> bool:
    """Solve the items whose end parts moved (all with ``force``) for where the parts are now and write the
    one-moment shapes mesh. True when something was written."""
    moved = _moved(scene)
    if not moved and not force:
        return False
    per = sum(int(it.points) for it in scene.fresing.flex)
    whole = force or _arrays(scene, 1, per) is None
    if whole:
        per = _layout(scene)
        todo = _usable(scene)
        arrays = tuple(np.zeros((1, per, 3), np.float32) for _ in range(3))
    else:
        usable = dict(_usable(scene))
        todo = [(i, usable[i]) for i, _key in moved if i in usable]
        arrays = _arrays(scene, 1, per)
    for i, key in moved:
        _STATE["last"][(scene.name, i)] = key
    if not todo and not whole:
        return False
    results, problems = _solve(todo, _places_now(todo), 1)
    for i, it in todo:
        _patch(arrays, it, results[i])
    _write_shapes(scene, arrays, 0)
    _note_problems(scene, todo, problems, None)
    if whole:
        sh = _shapes(scene)
        for key in (_ENDS, _ENDS_OBS, _ENDS_FIRST):       # the places read at a Build belong to that Build
            if key in sh:
                del sh[key]
        _sync(scene)
    return True


def _read_places(scene, its, first: int, frames: int) -> dict:
    """Step through the frames and read the world matrices of these items' end parts: name -> (frames, 4, 4)."""
    from . import clash
    ends = {ob.name: ob for _i, it in its for ob in (it.a_part, it.b_part)}
    names = sorted(ends)
    obs = [ends[n] for n in names]
    out = {n: np.empty((frames, 4, 4)) for n in names}
    if not names:
        return out
    keep = (scene.frame_current, scene.frame_subframe)
    needed = set(names)
    shy = [o for o in scene.objects if not o.hide_viewport and o.name not in needed
           and any(m.type == "NODES" for m in getattr(o, "modifiers", ()))]
    for o in shy:                               # only drawn (hoses, links, toolpath, chips): not worked out per frame
        o.hide_viewport = True
    try:
        with clash._Guard():
            for k in range(frames):
                scene.frame_set(first + k)
                _STATE["steps"] += 1
                for n, ob in zip(names, obs):
                    out[n][k] = _np(_world(ob))
    finally:
        for o in shy:
            o.hide_viewport = False
        scene.frame_set(keep[0], subframe=keep[1])
    return out


def _store_places(scene, mats: dict, first: int) -> None:
    sh = _shapes(scene, create=True)
    names = sorted(mats)
    data = np.stack([mats[n][:, :3, :] for n in names], axis=1) if names else np.zeros((0, 0, 3, 4))
    idprops.store_array(sh, _ENDS, data, dtype=np.float32)
    sh[_ENDS_OBS] = json.dumps(names)
    sh[_ENDS_FIRST] = int(first)


def _stored_places(scene, names: list, first: int, frames: int):
    """The places read at the last Build for these objects, or None when they are not all there."""
    sh = _shapes(scene)
    if sh is None or _ENDS not in sh or int(sh.get(_ENDS_FIRST, -1)) != first:
        return None
    try:
        have = json.loads(sh.get(_ENDS_OBS, "[]"))
    except ValueError:
        return None
    if not set(names) <= set(have):
        return None
    data = np.array(sh[_ENDS], dtype=float)
    if data.size != frames * len(have) * 12:
        return None
    data = data.reshape(frames, len(have), 3, 4)
    out = {}
    for n in names:
        m = np.zeros((frames, 4, 4))
        m[:, :3, :] = data[:, have.index(n)]
        m[:, 3, 3] = 1.0
        out[n] = m
    return out


def _bake(scene, step: bool, only: int | None = None) -> list[str]:
    """Every frame of the built animation: read where the end parts are (``step``, or when they were not kept),
    solve, write. ``only``: just this item changed (the others' frames stay as they are)."""
    per = _layout(scene)
    its = _usable(scene)
    notes = [f"{_word(it)} '{label(it)}': {broken(scene, it)} (see 4 Motion > Hoses and drag chains)"
             for it in scene.fresing.flex if it.enabled and broken(scene, it)]
    first, end = int(scene.frame_start), int(max(scene.frame_start, scene.frame_end))
    frames = end - first + 1
    names = _end_names(its)
    mats = None if step else _stored_places(scene, names, first, frames)
    if mats is None:
        mats = _read_places(scene, its, first, frames)
        _store_places(scene, mats, first)
        only = None
    arrays = _arrays(scene, frames, per) if only is not None else None
    todo = its
    if arrays is not None and _layout_of(_shapes(scene))[2] == first:
        todo = [(i, it) for i, it in its if i == only]
    else:
        arrays = tuple(np.zeros((frames, per, 3), np.float32) for _ in range(3))
    results, problems = _solve(todo, mats, frames)
    for i, it in todo:
        _patch(arrays, it, results[i])
    _write_shapes(scene, arrays, first)
    _sync(scene)
    return notes + _note_problems(scene, todo, problems, first)


def _rebuild(scene, only: int | None = None) -> list[str]:
    """Shapes and modifiers again for how the list is now: live, or every frame of the built animation."""
    if not len(scene.fresing.flex):
        return []
    _STATE["busy"] += 1
    try:
        if _baked(scene):
            return _bake(scene, step=False, only=only)
        if only is None:
            _live(scene, force=True)
        else:
            _STATE["last"].pop((scene.name, only), None)
            _live(scene)
            _sync(scene)
        return []
    finally:
        _STATE["busy"] -= 1


# ---------------------------------------------------------------------------
# what the rest of the app calls
# ---------------------------------------------------------------------------

def changed(scene, item) -> None:
    """A setting of ``item`` changed (props.py calls this): its shape is worked out again, along a built
    animation too (from the places read at Build: no stepping through the frames)."""
    if _STATE["busy"]:
        return
    i = index_of(scene, item)
    if i < 0:
        return
    if item.kind == "CHAIN" and not item.made_links and item.count != len(item.links) and len(item.links):
        with _quiet(item):
            item.count = len(item.links)                  # CAD links: as many as there are
    same_layout = int(item.points) == (DRAWN if item.kind == "HOSE" else
                                       (int(item.count) if item.made_links else len(item.links)))
    if broken(scene, item) or not same_layout or _shapes(scene) is None:
        _rebuild(scene)
    elif not item.enabled:                      # off: its CAD shape shows; the others stay as they are
        if item.problem:
            with _quiet(item):
                item.problem, item.problem_frame = "", 0
        _sync(scene)
    else:
        _rebuild(scene, only=i)


def refresh(scene, force: bool = False) -> None:
    """Live: the shapes for where the parts are now (after a pose set by a script, in the background too). With a
    built animation the frames written at Build show; ``force`` works those out again."""
    if not len(scene.fresing.flex) or _STATE["busy"]:
        return
    if _baked(scene):
        if force:
            _rebuild(scene)
        return
    try:
        layer = bpy.context.view_layer if bpy.context.scene == scene else scene.view_layers[0]
        layer.update()                          # the parts' places are current (the handler may solve here already)
    except Exception:
        pass
    _STATE["busy"] += 1
    try:
        _live(scene, force=force)
    finally:
        _STATE["busy"] -= 1


def bake(scene, anim) -> list[str]:
    """The last step of every Build: every frame's shape of every hose and chain. Returns warnings."""
    if not len(scene.fresing.flex):
        return []
    forget()
    _STATE["busy"] += 1
    try:
        return _bake(scene, step=True)
    except Exception as exc:                    # a Build never fails over a hose
        return [f"The hoses and drag chains could not be worked out ({exc or type(exc).__name__}): "
                "they show as they were"]
    finally:
        _STATE["busy"] -= 1


def after_clear(scene) -> None:
    """'Clear keys': the hoses and chains follow the parts live again."""
    if not len(scene.fresing.flex):
        return
    forget()
    _STATE["busy"] += 1
    try:
        _live(scene, force=True)
    finally:
        _STATE["busy"] -= 1
    forget()                                    # the parts may not be back in place yet: look again at the next update


def _moment_now(scene, sh) -> int:
    frames, _per, first = _layout_of(sh)
    return max(0, min(int(round(scene.frame_current + scene.frame_subframe - first)), frames - 1))


def _slice_now(scene, item):
    sh = _shapes(scene)
    frames, per, _first = _layout_of(sh)
    arrays = _arrays(scene, frames, per) if sh is not None else None
    if arrays is None or not item.points:
        return None
    k = _moment_now(scene, sh)
    lo, n = int(item.offset), int(item.points)
    return tuple(a[k, lo:lo + n].astype(float) for a in arrays)


def shape_now(scene, item) -> np.ndarray:
    """What is drawn at the frame shown, read from the shapes mesh (not solved again), world coordinates:
    a hose's centreline (POINTS, 3); a chain's link places (links, 3) – a CAD link's own origin, an app-made
    link's first pin."""
    got = _slice_now(scene, item)
    if got is None:
        return np.zeros((0, 3))
    return np.delete(got[0], (1, DRAWN - 2), axis=0) if item.kind == "HOSE" else got[0]


def pins_now(scene, item) -> np.ndarray:
    """A chain's pins (links + 1, 3) at the frame shown, worked out from the shapes mesh."""
    got = _slice_now(scene, item)
    if got is None or item.kind != "CHAIN":
        return np.zeros((0, 3))
    co, x, z = got
    m = np.zeros((len(co), 4, 4))
    m[:, :3, 0], m[:, :3, 1], m[:, :3, 2], m[:, :3, 3], m[:, 3, 3] = x, np.cross(z, x), z, co, 1.0
    if not item.made_links:
        local = np.stack([np.array(ob[LOCAL], dtype=float).reshape(4, 4) for ob in link_objects(item)])
        m = m @ np.linalg.inv(local)
    last = m[-1, :3, 3] + m[-1, :3, 0] * float(item.pitch)
    return np.vstack([m[:, :3, 3], last[None]])


def status(scene, item) -> tuple[str, str]:
    """(a few words, "OK" | "WARN" | "ERROR" | "OFF") for the list row and the panel."""
    if not item.enabled:
        return "off", "OFF"
    why = broken(scene, item)
    if why:
        return why, "ERROR"
    if item.problem:
        return item.problem, "WARN"
    return "follows the motion", "OK"


_WORDS = {"HOSE": ("HOSE", "HOSES", "SLANG", "SLANGEN", "SCHLAUCH", "CABLE", "CABLES", "KABEL", "KABELS"),
          "CHAIN": ("DRAG CHAIN", "DRAGCHAIN", "ENERGY CHAIN", "CABLE CHAIN", "ENERGIEKETTE", "SCHLEPPKETTE",
                    "KABELRUPS", "SLEEPKETTING")}
# … but not the things that hold or end one
_NOT_WORDS = ("GLAND", "FITTING", "CLAMP", "CLIP", "TRAY", "REEL", "DRUM", "DUCT", "TIE", "CONNECTOR", "PLUG",
              "SOCKET", "NIPPLE", "COUPLING", "BRACKET", "HOLDER", "GUIDE", "SUPPORT", "LUG", "KLEM", "SCHELLE",
              "WARTEL", "VERSCHRAUBUNG", "HALTER", "BEUGEL", "GOOT", "KANAL")
_GROUPS = {"Hoses & tubing": "HOSE", "Cables": "HOSE", "Cable chains": "CHAIN"}
_TYPES = {"hose": "HOSE", "cable": "HOSE", "cable_chain": "CHAIN"}


def _kind_by_name(ob) -> str:
    """'HOSE', 'CHAIN' or '' from the part's material group, its part type and the words in its name."""
    from ..core import part_types
    group = str(ob.get(build.PROP_GROUP, "") or "")
    for g, kind in _GROUPS.items():
        if group == g or group.startswith(g + " #"):
            return kind
    name = _part_name(ob)
    try:
        t = part_types.type_of(name, build.path_of(ob))
    except Exception:
        t = None
    if t in _TYPES:
        return _TYPES[t]
    words = " " + " ".join(name.upper().replace(".", " ").replace("_", " ").replace("-", " ").split()) + " "
    if not any(f" {w} " in words for w in _NOT_WORDS):
        for kind in ("CHAIN", "HOSE"):
            if any(f" {w} " in words for w in _WORDS[kind]):
                return kind
    if t == "chain":                            # "CHAIN LINK": a drag chain's link when its shape repeats in a row
        return "LINKS?"
    return ""


def candidates(scene) -> list:
    """[(part, "HOSE" | "CHAIN")]: the model parts that look like a hose, a cable or a drag chain (by their part
    type and name) and are no flex part yet. A chain's links come one by one; ``siblings`` gives the whole row."""
    taken = {ob.name for ob in flex_parts(scene)}
    out, rows = [], {}
    for ob in build.iter_parts(scene):
        if ob.name in taken or ob.get(build.PROP_EXCLUDED):
            continue
        kind = _kind_by_name(ob)
        if kind == "LINKS?":
            p = build.logical_parent(ob)
            rows.setdefault((p.name if p is not None else "", ob.data.name), []).append(ob)
        elif kind:
            out.append((ob, kind))
    for row in rows.values():
        if len(row) >= 4 and _open_row(row):
            out += [(ob, "CHAIN") for ob in row]
    return out


def _open_row(row) -> bool:
    """Do these links lie in one open row with two ends? A drag chain does; a chain that runs round in a loop (a
    roller chain on its sprockets, a tensioner's track) has no end and is no drag chain."""
    mats = np.array([_np(ob.matrix_world) for ob in row])
    centres = np.array([tuple(ob.matrix_world @ (sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0))
                        for ob in row])
    return CH.open_row(mats, centres)


def siblings(scene, ob) -> list:
    """The parts that make one chain with ``ob``: the chain candidates in the same subassembly."""
    home = build.logical_parent(ob)
    return [o for o, kind in candidates(scene) if kind == "CHAIN" and build.logical_parent(o) == home]


def _clash_hook(scene):
    """The clash check leaves flex parts out: they bend with the parts they join (it would test the stiff CAD
    shape)."""
    return [], flex_parts(scene)


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def _new_object(scene, uid: str, by_uid: dict, mapping: dict):
    if not uid:
        return None
    ob = by_uid.get(uid)
    if ob is None:
        new = mapping.get(uid, uid)
        ob = next((o for o in scene.objects if o.get(build.PROP_UID) == new), None)
    return ob


def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]:
    """The model was replaced by a new revision: every item goes to the matching new parts (by their part IDs),
    is read again from the new CAD shapes and keeps what the user set. Returns notes for the report."""
    s = scene.fresing
    if not len(s.flex):
        return []
    notes = []
    forget()

    def concerned(it) -> bool:                  # an item of another model stays as it is
        uids = [it.part_uid, it.a_uid, it.b_uid] + it.link_uids.split("\n")
        return any(u and (u in mapping or u in by_uid) for u in uids)

    todo = [it for it in s.flex if concerned(it)]
    _STATE["busy"] += 1
    try:
        for it in todo:                         # first every item to its new parts, then read (ends never sit on
            with _quiet(it):                    # another flex part)
                for key in ("a", "b"):
                    ob = _new_object(scene, getattr(it, key + "_uid"), by_uid, mapping)
                    setattr(it, key + "_part", ob)
                    if ob is None and it.get(key + "_user"):
                        del it[key + "_user"]
                if it.kind == "HOSE" or it.made_links:
                    it.part = _new_object(scene, it.part_uid, by_uid, mapping)
                else:
                    uids = [u for u in it.link_uids.split("\n") if u]
                    links = [ob for ob in (_new_object(scene, u, by_uid, mapping) for u in uids) if ob is not None]
                    it["links_gone"] = len(uids) - len(links)
                    it.links.clear()
                    for ob in links:
                        it.links.add().obj = ob
        for it in todo:
            name = f"{_word(it)} '{label(it)}'"
            try:
                if it.kind == "HOSE" or it.made_links:
                    if it.part is None:
                        notes.append(f"{name}: its part is gone in the new revision")
                    elif it.kind == "HOSE":
                        _store_hose(it, it.part, _read_hose(scene, it.part), keep_user=True)
                    else:
                        _store_chain(it, _read_solid(scene, it.part, bool(it.get("swapped"))), it.part,
                                     keep_user=True)
                else:
                    gone = int(it.get("links_gone", 0))
                    del it["links_gone"]
                    if gone:
                        notes.append(f"{name}: {plural(gone, 'link')} of it {'is' if gone == 1 else 'are'} gone "
                                     "in the new revision")
                    if len(it.links) >= 4:
                        _store_chain(it, _read_chain(scene, link_objects(it), bool(it.get("swapped"))), None,
                                     keep_user=True)
            except FlexError as exc:
                notes.append(f"{name}: {exc}")
            except Exception as exc:            # a model update never fails over a hose
                notes.append(f"{name} could not be carried over ({exc or type(exc).__name__}): "
                             "use 'Fit to the CAD pose'")
    finally:
        _STATE["busy"] -= 1
    try:
        _rebuild(scene)
    except Exception as exc:
        notes.append(f"The hoses and drag chains could not be drawn again ({exc or type(exc).__name__})")
    return notes


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def forget() -> None:
    """Drop what this module remembers between calls (undo, redo, file load, a changed list)."""
    _STATE["last"].clear()
    _STATE["arrays"].clear()
    _STATE["inputs"].clear()


def _redraw_views() -> None:
    """The shapes were written after the update that moved the parts: evaluate once more and draw the views again
    right after this update, or the hoses lag one step behind until the next mouse move (as linkages.py)."""
    if bpy.app.background or bpy.app.timers.is_registered(_settle):
        return
    bpy.app.timers.register(_settle, first_interval=0.0)


def _settle():
    try:
        bpy.context.view_layer.update()
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass
    return None


def _follow(scene) -> None:
    if _STATE["busy"] or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        s = scene.fresing
        if not len(s.flex) or s.anim_baked:
            return                              # nothing to do, or the built animation's frames show
    except (AttributeError, ReferenceError):
        return
    if not bpy.app.background and threading.current_thread() is not threading.main_thread():
        return                                  # a render in the window: the shapes were written before it began
    _STATE["busy"] += 1
    try:
        if _live(scene):
            _redraw_views()
    except Exception as exc:                    # never break the app's update loop
        print("Fresing Render: hose update failed:", exc)
    finally:
        _STATE["busy"] -= 1


@persistent
def _on_depsgraph(scene, _depsgraph=None):
    _follow(scene)


@persistent
def _on_frame(scene, _depsgraph=None):
    """Keys the user made by hand (no built animation): the shapes follow at every frame."""
    from . import machining
    if machining._STATE["guard"]:               # something is only reading the motion (clash._Guard)
        return
    _follow(scene)


@persistent
def _on_load(_dummy=None):
    forget()


@persistent
def _on_undo(_scene=None, _dummy=None):
    forget()


def _handlers():
    h = bpy.app.handlers
    return ((h.depsgraph_update_post, _on_depsgraph), (h.frame_change_post, _on_frame), (h.load_post, _on_load),
            (h.undo_post, _on_undo), (h.redo_post, _on_undo))


def register() -> None:
    from . import clash
    for lst, fn in _handlers():
        if fn not in lst:
            lst.append(fn)
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


def unregister() -> None:
    from . import clash
    for lst, fn in _handlers():
        while fn in lst:
            lst.remove(fn)
    while _clash_hook in clash.HOOKS:
        clash.HOOKS.remove(_clash_hook)
    if bpy.app.timers.is_registered(_settle):
        bpy.app.timers.unregister(_settle)
    forget()


# ---------------------------------------------------------------------------
# the two test models (tests, the test tour, the PC check)
# ---------------------------------------------------------------------------

def _named(scene, name: str):
    for ob in scene.objects:
        if ob.get(build.PROP_NAME) == name:
            return ob
    raise FlexError(f"The model has no part '{name}'.")


def set_up_test_hoses(scene) -> dict:
    """The set-up of the hoses test model (test_flex_hoses_a.step, tools/make_test_flex.py): a rotate joint "Luff"
    on the arm (+ is tip up), a slide joint "Slide", the cylinder "Luff cylinder" following the arm, and the four
    items: three hydraulic hoses and the cable. Returns the names of what was made."""
    from . import cylinders, joints
    along_y = Vector((0.0, 1.0, 0.0))
    joints.create(scene, "ROTATE", [_named(scene, "ARM.ASM")], Vector((0.1, 0.2, 0.6)), -along_y, name="Luff")
    slide = _named(scene, "SLIDE.ASM")
    joints.create(scene, "SLIDE", [slide], slide.matrix_world.translation.copy(), Vector((1.0, 0.0, 0.0)),
                  name="Slide")
    bpy.context.view_layer.update()
    c, _notes = cylinders.create(scene, [_named(scene, "CYL.BARREL")], [_named(scene, "CYL.ROD")],
                                 (Vector((0.3, 0.2, 0.17)), along_y, _named(scene, "BASE.PIN")),
                                 (Vector((0.9, 0.2, 0.45)), along_y, _named(scene, "ARM.ROD.PIN")),
                                 name="Luff cylinder")
    cylinder = c.name
    bpy.context.view_layer.update()
    names = []
    for part, soft in (("HYDRAULIC HOSE ARM", False), ("HYDRAULIC HOSE CYL A", False),
                       ("HYDRAULIC HOSE CYL B", False), ("CABLE", True)):
        item, _n = add_hose(scene, _named(scene, part), soft=soft)
        names.append(item.name)
    return {"joints": ["Luff", "Slide"], "cylinder": cylinder, "items": names}


def set_up_test_chains(scene) -> dict:
    """The set-up of the drag chains test model (test_flex_chains_a.step): slide joints "Y", "X", "Z" on the
    gantry's three axes and the three chains "CHAIN X.ASM", "CHAIN Y.ASM", "CHAIN Z.ASM". Returns the names."""
    from . import joints
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _named(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation.copy(), Vector(d), name=name)
    bpy.context.view_layer.update()
    names = []
    for asm in ("CHAIN X.ASM", "CHAIN Y.ASM", "CHAIN Z.ASM"):
        home = _named(scene, asm)
        links = [ob for ob in build.iter_parts(scene) if build.logical_parent(ob) == home]
        item, _n = add_chain(scene, links)
        names.append(item.name)
    return {"joints": ["X", "Y", "Z"], "items": names}
