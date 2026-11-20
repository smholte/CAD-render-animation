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
GUIDE = "fr_flex_guide_"                # + "a" / "b", on a hose part: its CAD centreline (GUIDE_POINTS x 3) in the
GUIDE_POINTS = 17                       # coordinates of the part each end sits on
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
_STATE = {"busy": 0, "last": {}, "arrays": {}, "solves": 0, "steps": 0, "inputs": {}, "read": None, "solved": {},
          "moved_rigid": 0, "motion_scene": None}
RIGID_TOL = 2e-5                        # m (and rad): the two end parts kept their places to each other (float32)
GRAVITY_TURN = math.radians(0.5)        # a hose moved as a whole may turn this far against gravity (task 0121)
MOTION_WAIT = 0.4                       # s: a vessel-motion slider rests this long before the hoses are baked again
READ_HOOKS: list = []                   # fn(scene) -> objects whose places Build should read in the hoses' pass
#                                         through the frames too (cables: blender/paths.py), see ``read_places``


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
    if item.kind == "HOSE":
        for k, c in enumerate(item.clips):
            if not _alive(scene, c.part):
                return f"the part clip {k + 1} sat on is gone"
    return ""


def end_objects(item) -> list:
    """The parts the item's shape hangs on: end A, end B and (a drawn hose) every clip's part, in that order."""
    return [item.a_part, item.b_part] + ([c.part for c in item.clips] if item.kind == "HOSE" else [])


def hose_points(item) -> int:
    """Points of a hose in a moment of the shapes mesh: DRAWN per segment, a clip's point once (task 0240)."""
    from ..core import flex as HS
    return HS.segment_points(len(item.clips) + 1, DRAWN)


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
        # an excluded part (hidden for good) is never what an end or a bend rests on (task 0082: the demo's second end
        # lies on the lay cable's path, kept out until the quadrant operation)
        self.parts = [ob for ob in build.iter_parts(scene) if ob.name not in skip and len(ob.data.vertices)
                      and not ob.get(build.PROP_EXCLUDED) and not ob.get("fr_drawn")]
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
    out["line"] = line                          # the CAD centreline, world: which way the hose lies (the guide)
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
            if geo.get("line") is not None:     # the CAD centreline as this end's part sees it (see _guides)
                from ..core import flex as HS
                idprops.store_array(part, GUIDE + key, _local_point(ob, geo["memo"], HS.resample(geo["line"],
                                                                                                GUIDE_POINTS)))
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


# ---------------------------------------------------------------------------
# drawn in the app by clicking points (task 0240)
# ---------------------------------------------------------------------------

DRAWN_DIAMETER = {False: 0.02, True: 0.012}    # a hose / a cable drawn with no round face to read it from
SAME_SPOT = 0.001                       # m: two clicks this close are one click


def _dedupe(spots: list) -> list:
    """The spots without a click repeated on the same place (a double click, the same face twice)."""
    out = []
    for sp in spots:
        if out and out[-1]["part"] == sp["part"] and \
                float(np.linalg.norm(np.asarray(out[-1]["point"]) - np.asarray(sp["point"]))) < SAME_SPOT:
            continue
        out.append(sp)
    return out


def _stops(item) -> list:
    """[(point, direction)] in the world now: end A, the clips, end B (directions along the hose, A -> B)."""
    from . import drawn
    out = [drawn.world_spot(item.a_part, item.a_point, item.a_dir)]
    out += [drawn.world_spot(c.part, c.point, c.dir) for c in item.clips]
    out.append(drawn.world_spot(item.b_part, item.b_point, item.b_dir))
    return out


def _natural_now(item) -> tuple:
    """(length of each segment, the lines) for where the ends and clips are now (``core/flex.natural_length``)."""
    from ..core import flex as HS
    least = max(float(item.min_radius), HS.LEAST_BEND * float(item.diameter))
    stops = _stops(item)
    lengths, lines = [], []
    for (p0, t0), (p1, t1) in zip(stops[:-1], stops[1:]):
        length, line = HS.natural_length(p0, t0, p1, t1, least)
        lengths.append(length)
        lines.append(line)
    return lengths, lines


def travel_joints(scene, item) -> list:
    """The joints that move one of the item's end parts (or clips) against another: the hose must reach over their
    travel. Names, nearest first."""
    obs = [o for o in end_objects(item) if o is not None]
    sets = [_movers(o) for o in obs]
    if not sets:
        return []
    moving = set().union(*sets) - set.intersection(*[set(x) for x in sets])
    names = []
    for j in scene.fresing.joints:
        if any(o is not None and o.name in moving for o in (j.motion, j.frame)) and j.name not in names:
            names.append(j.name)
    return names


def _natural(scene, item) -> tuple:
    """(length of each segment, the lines, the joints with no limits) the hose needs: where its ends and clips are
    now, and – unless an animation is built – at both ends of the travel of each joint between them that has limits
    (each segment the longest of those). The lines are those of now."""
    from . import joints
    lengths, lines = _natural_now(item)
    free = []
    if _baked(scene):
        return lengths, lines, free
    best = np.array(lengths)
    for name in travel_joints(scene, item):
        j = joints.find(scene, name)
        if j is None or j.follows:
            continue
        if not j.use_limits:
            free.append(name)
            continue
        lo, hi = (j.rot_min, j.rot_max) if j.kind == "ROTATE" else (j.slide_min, j.slide_max)
        now = joints.get_value(j)
        try:
            for v in (lo, hi):
                joints.set_value(j, float(v))
                bpy.context.view_layer.update()
                best = np.maximum(best, _natural_now(item)[0])
        finally:
            joints.set_value(joints.find(scene, name), now)
            bpy.context.view_layer.update()
    return [float(x) for x in best], lines, free


def default_size(scene, item) -> list[str]:
    """A drawn hose: the length (and each segment's share) it starts with, for where its ends and clips are now.
    A drawn chain: the links it starts with. Returns notes."""
    from . import drawn
    from ..core import flex as HS
    why = broken(scene, item)
    if why:
        return [f"{_word(item)} '{label(item)}': {why}"]
    if item.kind == "HOSE":
        _STATE["busy"] += 1
        try:
            lengths, lines, _free = _natural(scene, item)
        finally:
            _STATE["busy"] -= 1
        with _quiet(item):
            item.length = float(sum(lengths))
            item.cad_length = item.length
            item["shares"] = [float(x) for x in HS.shares(lengths)]
        line = HS.join(lines)
        drawn.set_tube(item.part, line, 0.5 * float(item.diameter))
        if not len(item.clips):
            _store_guides(item, line)
    else:
        size = _chain_size(scene, item)
        with _quiet(item):
            item.count = size["count"]
    _rebuild(scene)
    return []


def _store_guides(item, line: np.ndarray) -> None:
    """The drawn line as each end's part sees it: the hose stays on the side it was drawn on (see ``_guide``)."""
    from ..core import flex as HS
    pts = HS.resample(line, GUIDE_POINTS)
    for key in ("a", "b"):
        ob = getattr(item, key + "_part")
        inv = np.linalg.inv(_np(ob.matrix_world))
        idprops.store_array(item.part, GUIDE + key, _at(inv, pts))


def draw_hose(scene, spots: list, soft: bool = False, name: str = "", diameter: float = 0.0, replace=None):
    """A hose (``soft``: a cable) the user drew by clicking: ``spots`` (``drawn.spot`` of each click) = end A, the
    clips it runs through, end B. It gets the app's own object, a diameter from end A's round face (else B's, else
    ``DRAWN_DIAMETER``), the length of a smooth line between its ends and clips that keeps its bends wide
    (``core/flex.natural_length``) and 5 % more, and follows the motion like a hose read from CAD. ``replace``: a
    simplified CAD hose it replaces (``drawn.replace``). Returns (item, notes). Raises FlexError."""
    from . import drawn
    from ..core import flex as HS
    spots = _dedupe(list(spots or []))
    if len(spots) < 2:
        raise FlexError("Click the fitting at end A, then (optional) the clips, then the fitting at end B.")
    for sp in spots:
        if sp["part"] is None or drawn.is_drawn(sp["part"]) or sp["part"].get(build.PROP_KIND) != "part":
            raise FlexError("Each click must be on a part of the model (not on a drawn hose or cable).")
    taken = {ob.name for ob in flex_parts(scene)}
    for sp in spots:
        if sp["part"].name in taken:
            raise FlexError(f"'{_part_name(sp['part'])}' is a hose or chain itself: click the fitting or clip it "
                            "is fixed to.")
    if not diameter:
        diameter = next((sp["diameter"] for sp in (spots[0], spots[-1]) if sp["round"] and sp["diameter"] > 0.0),
                        DRAWN_DIAMETER[bool(soft)])
        diameter = float(min(max(diameter, 0.002), 0.3))
    pts = [np.asarray(sp["point"], dtype=float) for sp in spots]
    dirs = [np.asarray(sp["dir"], dtype=float) for sp in spots]
    dirs[-1] = -dirs[-1]                        # end B: the direction the hose arrives in (into the fitting)
    for k in range(1, len(spots) - 1):          # a clip: along the way from the stop before to the stop after
        way = pts[k + 1] - pts[k - 1]
        if not spots[k]["round"]:               # on a flat face: the hose lies on it, along it
            n = dirs[k] / (np.linalg.norm(dirs[k]) or 1.0)
            pts[k] = pts[k] + n * 0.5 * diameter
            along = way - n * float(way @ n)
            if float(np.linalg.norm(along)) < 1e-9:
                along = np.cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.9 else np.cross(n, (1.0, 0.0, 0.0))
            dirs[k] = along / np.linalg.norm(along)
        elif float(dirs[k] @ way) < 0.0:        # through a bore: along its axis, the way the hose goes
            dirs[k] = -dirs[k]
    s = scene.fresing
    item = s.flex.add()
    index = len(s.flex) - 1
    base = name or ("Cable" if soft else "Hose")
    with _quiet(item):
        item.name = _unique(scene, base if name else f"{base} 1")
        item["name_was"] = item.name
        item.kind = "HOSE"
        item.drawn = True
        item.diameter = diameter
        item["cad_diameter"] = diameter
        item.stiffness, item.sag, item.min_radius = (0.2, 0.8, 0.0) if soft else (0.6, 0.5, 0.0)
        for key, sp, d in (("a", spots[0], dirs[0]), ("b", spots[-1], dirs[-1])):
            ob = sp["part"]
            inv = np.linalg.inv(_np(ob.matrix_world))
            local = inv[:3, :3] @ d
            setattr(item, key + "_part", ob)
            setattr(item, key + "_uid", ob.get(build.PROP_UID, ""))
            setattr(item, key + "_point", tuple(_at(inv, sp["point"])))
            setattr(item, key + "_dir", tuple(local / (np.linalg.norm(local) or 1.0)))
            item[key + "_user"] = True
        for sp, p, d in zip(spots[1:-1], pts[1:-1], dirs[1:-1]):
            c = item.clips.add()
            ob = sp["part"]
            inv = np.linalg.inv(_np(ob.matrix_world))
            local = inv[:3, :3] @ d
            c.part, c.uid = ob, ob.get(build.PROP_UID, "")
            c.point = tuple(_at(inv, p))
            c.dir = tuple(local / (np.linalg.norm(local) or 1.0))
    item = s.flex[index]
    _STATE["busy"] += 1                         # (the joints are moved to the ends of their travel and back)
    try:
        lengths, lines, free = _natural(scene, item)
    finally:
        _STATE["busy"] -= 1
    item = s.flex[index]
    line = HS.join(lines)
    part = drawn.make_object(scene, "CABLE" if soft else "HOSE", item.name, line, 0.5 * diameter)
    with _quiet(item):
        item.part = part
        item.part_uid = part.get(build.PROP_UID, "")
        item.length = float(sum(lengths))
        item.cad_length = item.length
        item["shares"] = [float(x) for x in HS.shares(lengths)]
    part[TAG] = True
    if not len(item.clips):
        _store_guides(item, line)
    notes = []
    if free:
        notes.append(f"{_word(item)} '{item.name}' is as long as this pose needs: "
                     f"{', '.join(repr(n) for n in free[:2])} {'has' if len(free) == 1 else 'have'} no limits. Give "
                     "the joint its limits and press 'Length as drawn' – or move it to its ends and check the hose")
    if replace is not None:
        try:
            drawn.replace(scene, item, replace)
        except drawn.DrawError as exc:
            notes.append(str(exc))
    s.flex_index = index
    _rebuild(scene)
    return s.flex[index], notes


def _travel_joint(scene, moving, fixed):
    """The joint nearest above ``moving`` in the tree that does not move ``fixed`` too: what carries the moving end."""
    from . import joints
    above_fixed = _movers(fixed)
    by_empty = {}
    for j in scene.fresing.joints:
        for o in (j.motion, j.frame):
            if o is not None:
                by_empty[o.name] = j.name
    p = moving.parent
    while p is not None:
        if p.get(build.PROP_KIND) in build.JOINT_KINDS and p.name not in above_fixed and p.name in by_empty:
            return joints.find(scene, by_empty[p.name])
        p = p.parent
    return None


def _chain_frame(scene, a_spot: dict, b_spot: dict, flip: bool = False) -> tuple:
    """(frame 4 x 4 world: origin = the fixed pin, x along the fixed run towards the bend, y towards the moving run,
    z across; the gap between the runs; the travel joint or None) for a chain between the two clicked brackets."""
    from . import joints
    a, b = np.asarray(a_spot["point"], dtype=float), np.asarray(b_spot["point"], dtype=float)
    j = _travel_joint(scene, b_spot["part"], a_spot["part"])
    u = None
    if j is not None and j.kind == "SLIDE":
        u = np.array(joints.axis_world(j)[1], dtype=float)
    if u is None:                               # no slide: along the clicked faces, square to the gap
        gap = b - a
        n = np.asarray(a_spot["dir"], dtype=float)
        u = gap - n * float(gap @ n)
        if float(np.linalg.norm(u)) < 1e-6:
            u = np.cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.9 else np.cross(n, (1.0, 0.0, 0.0))
    u = u / np.linalg.norm(u)
    d = b - a
    v = d - u * float(d @ u)
    na, nb = (np.asarray(sp.get("dir", (0.0, 0.0, 0.0)), dtype=float) for sp in (a_spot, b_spot))
    if abs(float(na @ nb)) > 0.95 and abs(float(na @ u)) < 0.1:
        # both brackets clicked on a side face (the same way): that is across the chain – the runs lie in a plane
        # square to it, whatever the two faces' offset sideways (the chain then rises evenly to the moving end)
        wn = na - u * float(na @ u)
        wn /= np.linalg.norm(wn)
        v = v - wn * float(v @ wn)
    gap = float(np.linalg.norm(v))
    if gap < 1e-4:
        raise FlexError("The two brackets lie on one line along the travel: click the bracket of the moving run, "
                        "which lies above (or beside) the fixed run.")
    v /= gap
    if float(d @ u) < -1e-6:                    # the bend lies beyond the moving end
        u = -u
    if flip:
        u = -u
    w = np.cross(u, v)
    frame = np.eye(4)
    frame[:3, 0], frame[:3, 1], frame[:3, 2], frame[:3, 3] = u, v, w, a
    return frame, gap, j


def _chain_size(scene, item) -> dict:
    """The links a drawn chain needs for its travel: {"count"} (the joint's limits when it has them, else the
    moving end's distance from the fixed end now, at least 4 bend radii either way)."""
    from . import joints
    frame = _np(_world(item.a_part)) @ np.array(item.frame, dtype=float).reshape(4, 4)
    end = _at(_np(_world(item.b_part)), np.array(item.b_point))
    u_now = float((end - frame[:3, 3]) @ frame[:3, 0])
    R, p = float(item.radius), float(item.pitch)
    j = _travel_joint(scene, item.b_part, item.a_part)
    lo = hi = u_now
    if j is not None and j.kind == "SLIDE" and j.use_limits:
        sign = float(np.sign(np.array(joints.axis_world(j)[1]) @ frame[:3, 0])) or 1.0
        now = joints.get_value(j)
        ends = [u_now + sign * (float(j.slide_min) - now), u_now + sign * (float(j.slide_max) - now)]
        lo, hi = min(ends), max(ends)
    else:
        reach = max(abs(u_now), 4.0 * R)
        lo, hi = -reach, reach
    length = math.pi * R + max(hi, -lo, 0.0) + 2.0 * p
    return {"count": int(max(4, math.ceil(length / p)))}


def draw_chain(scene, fixed: dict, moving: dict, name: str = "", flip: bool = False, replace=None):
    """A drag chain the user drew by clicking its two brackets (``drawn.spot`` of each): the fixed end's and the
    moving end's. The runs lie along the travel of the joint that moves the moving bracket (else along the clicked
    faces); bend radius = half the gap between the runs; link length, height and width follow from the radius, the
    number of links from the travel. ``flip``: the bend on the other side. The app draws the links. ``replace``: a
    simplified CAD chain it replaces. Returns (item, notes). Raises FlexError."""
    from . import drawn
    a_ob, b_ob = fixed["part"], moving["part"]
    for ob in (a_ob, b_ob):
        if ob is None or drawn.is_drawn(ob) or ob.get(build.PROP_KIND) != "part":
            raise FlexError("Click the brackets on parts of the model (not on a drawn hose, cable or chain).")
    if a_ob == b_ob:
        raise FlexError(f"Both brackets are on '{_part_name(a_ob)}': the moving bracket sits on the part that moves.")
    taken = {ob.name for ob in flex_parts(scene)}
    if a_ob.name in taken or b_ob.name in taken:
        raise FlexError("A bracket was clicked on a hose or chain itself: click the parts the chain is fixed to.")
    frame, gap, j = _chain_frame(scene, fixed, moving, flip)
    radius = max(0.5 * gap, 0.01)
    height = min(max(radius / 3.0, 0.008), 0.15)
    pitch = min(CH.PITCH_PER_HEIGHT * height, radius / (CH.MIN_RADIUS + 0.05))
    width = 2.4 * height
    s = scene.fresing
    item = s.flex.add()
    index = len(s.flex) - 1
    with _quiet(item):
        item.name = _unique(scene, name or "Drag chain 1")
        item["name_was"] = item.name
        item.kind = "CHAIN"
        item.drawn = True
        item.made_links = True
        for key, ob in (("a", a_ob), ("b", b_ob)):
            setattr(item, key + "_part", ob)
            setattr(item, key + "_uid", ob.get(build.PROP_UID, ""))
            item[key + "_user"] = True
        local = np.linalg.inv(_np(a_ob.matrix_world)) @ frame
        item.frame = tuple(local.reshape(-1))
        item.a_point = tuple(local[:3, 3])
        item.b_point = tuple(_at(np.linalg.inv(_np(b_ob.matrix_world)), moving["point"]))
        item.radius, item.pitch, item.width, item.height = radius, pitch, width, height
        item.mode = "STRAIGHT"
        item["flip"] = bool(flip)
    item = s.flex[index]
    with _quiet(item):
        item.count = _chain_size(scene, item)["count"]
    spec = CH.ChainSpec(float(item.pitch), int(item.count), float(item.radius), item.mode)
    moving_local = _at(np.linalg.inv(frame), moving["point"])
    pins = _at(frame, CH.chain_pins(spec, moving_local[None]).pins[0])
    part = drawn.make_object(scene, "CHAIN", item.name, pins, 0.5 * height)
    with _quiet(item):
        item.part = part
        item.part_uid = part.get(build.PROP_UID, "")
    part[TAG] = True
    notes = []
    if j is None:
        notes.append(f"Drag chain '{item.name}': no slide joint moves '{_part_name(b_ob)}' – the runs lie along the "
                     "clicked faces. Check 'Links' when the axis is made")
    if replace is not None:
        try:
            drawn.replace(scene, item, replace)
        except drawn.DrawError as exc:
            notes.append(str(exc))
    s.flex_index = index
    _rebuild(scene)
    return s.flex[index], notes


def flip_bend(scene, item) -> None:
    """A drawn chain: its bend goes to the other side (the fixed run runs the other way along the travel)."""
    if not item.drawn or item.kind != "CHAIN" or broken(scene, item):
        return
    a = _np(_world(item.a_part))
    frame = a @ np.array(item.frame, dtype=float).reshape(4, 4)
    frame[:3, 0] = -frame[:3, 0]
    frame[:3, 2] = -frame[:3, 2]                # (x, y, z) stays right-handed
    local = np.linalg.inv(a) @ frame
    with _quiet(item):
        item.frame = tuple(local.reshape(-1))
        item["flip"] = not bool(item.get("flip"))
    _rebuild(scene)


def swap_ends(scene, item) -> None:
    """A chain: the other end is the fixed one. (Read from the CAD pose again; numbers set by hand stay.)"""
    if item.kind != "CHAIN" or broken(scene, item) in ("a link is gone", "its part is gone"):
        return
    if item.drawn:                              # task 0240: the other bracket is the fixed one
        if broken(scene, item):
            return
        a = _np(_world(item.a_part))
        frame = a @ np.array(item.frame, dtype=float).reshape(4, 4)
        fixed = {"part": item.b_part, "point": _at(_np(_world(item.b_part)), np.array(item.b_point))}
        moving = {"part": item.a_part, "point": frame[:3, 3]}
        new = frame.copy()                      # the runs swap: the bend stays where it is (x), y and z turn over
        new[:3, 1], new[:3, 2], new[:3, 3] = -frame[:3, 1], -frame[:3, 2], fixed["point"]
        with _quiet(item):
            a_uid, b_uid = item.a_uid, item.b_uid
            item.a_part, item.b_part = fixed["part"], moving["part"]
            item.a_uid, item.b_uid = b_uid, a_uid
            local = np.linalg.inv(_np(_world(item.a_part))) @ new
            item.frame = tuple(local.reshape(-1))
            item.a_point = tuple(local[:3, 3])
            item.b_point = tuple(_at(np.linalg.inv(_np(_world(item.b_part))), moving["point"]))
            item["swapped"] = not bool(item.get("swapped"))
        _rebuild(scene)
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
    if item.drawn:                              # task 0240: no CAD shape – the first numbers for where it is now
        return default_size(scene, item)
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
            if item.part is not None and GUIDE + key in item.part:
                idprops.store_array(item.part, GUIDE + key,
                                    _at(to_new, np.array(item.part[GUIDE + key], dtype=float).reshape(-1, 3)))
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
    if item.drawn:                              # task 0240: the app's own object goes, the CAD parts it replaced show
        from . import drawn
        drawn.unreplace(scene, item)
        made = item.part
        item.part = None
        drawn.delete_object(made)
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
        for key in (TAG, LOCAL, GUIDE + "a", GUIDE + "b"):
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
    b.link(_slot(b, _shade(b, tube.outputs[0])), gout.inputs[0])


def _shade(b: _Nodes, geometry):
    """A tube's faces smooth, the rim of its end caps a sharp edge (cables use it too: blender/paths.py)."""
    smooth = b.new("GeometryNodeSetShadeSmooth", domain="FACE")
    b.link(geometry, smooth.inputs[0])
    edge = b.new("GeometryNodeInputMeshEdgeAngle")                # the rim of the end caps stays a sharp edge
    soft = b.new("FunctionNodeCompare", data_type="FLOAT", operation="LESS_THAN")
    b.link(edge.outputs["Unsigned Angle"], soft.inputs[0])
    soft.inputs[1].default_value = 1.0
    rim = b.new("GeometryNodeSetShadeSmooth", domain="EDGE")
    b.link(smooth.outputs[0], rim.inputs[0])
    b.link(soft.outputs[0], rim.inputs["Shade Smooth"])
    return rim.outputs[0]


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
            n = hose_points(it)
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
    return sorted({ob.name for _i, it in its for ob in end_objects(it)})


def _places_now(its) -> dict:
    """Object name -> its world matrix now, as (1, 4, 4), for the end parts of these items."""
    out = {}
    for _i, it in its:
        for ob in end_objects(it):
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
        # one row per segment: a hose without clips is one segment, a drawn hose through clips one per stretch
        # between them (task 0240), each with its share of the length and the clip's direction at both its ends
        rows = []                               # (k of the hose, segment, from, to)
        for k, (_i, it) in enumerate(hoses):
            obs = end_objects(it)
            stops = [(obs[0], it.a_point, it.a_dir)] + [(c.part, c.point, c.dir) for c in it.clips] \
                + [(obs[1], it.b_point, it.b_dir)]
            for seg in range(len(stops) - 1):
                rows.append((k, seg, stops[seg], stops[seg + 1]))
        h = len(rows)
        p0, t0, p1, t1 = (np.empty((frames, h, 3)) for _ in range(4))
        length, stiff, sag, rmin = (np.empty((frames, h)) for _ in range(4))
        guide = np.full((frames, h, GUIDE_POINTS, 3), np.nan)       # (a row of NaN: no guide for that row)

        def at(ob, point, direction):
            m = mats[ob.name]
            return (np.array(point) @ m[:, :3, :3].transpose(0, 2, 1) + m[:, :3, 3],
                    np.array(direction) @ m[:, :3, :3].transpose(0, 2, 1))

        for r, (k, seg, (oa, pa, da), (ob_, pb, db)) in enumerate(rows):
            it = hoses[k][1]
            p0[:, r], t0[:, r] = at(oa, pa, da)
            p1[:, r], t1[:, r] = at(ob_, pb, db)
            length[:, r] = it.length * _share(it, seg)
            stiff[:, r] = HS.stiff_length(it.diameter, it.stiffness)
            sag[:, r] = it.sag
            rmin[:, r] = it.min_radius
            if not len(it.clips):               # which way the hose lies: it stays on the side CAD drew it on
                g = _guide(it, mats[it.a_part.name], mats[it.b_part.name])
                if g is not None:
                    guide[:, r] = g
        if frames > 1:
            # the frames of a built animation, in their order: each hose keeps one shape along the motion where it
            # can (a slack hose often has two, and solved frame by frame it would jump from one to the other once)
            pts = np.empty((frames, h, POINTS, 3))
            short, tight = (np.zeros((frames, h), dtype=bool) for _ in range(2))
            need = np.empty((frames, h))
            for r in range(h):
                res = HS.solve_motion(p0[:, r], t0[:, r], p1[:, r], t1[:, r], length[:, r], stiff[:, r], sag[:, r],
                                      rmin[:, r], n=POINTS, guide=guide[:, r])
                pts[:, r], short[:, r], need[:, r], tight[:, r] = res.points, res.short, res.need, res.tight
        else:
            res = HS.solve_hoses(p0.reshape(-1, 3), t0.reshape(-1, 3), p1.reshape(-1, 3), t1.reshape(-1, 3),
                                 length.reshape(-1), stiff.reshape(-1), sag.reshape(-1), rmin.reshape(-1), n=POINTS,
                                 guide=guide.reshape(-1, GUIDE_POINTS, 3))
            pts = res.points.reshape(frames, h, POINTS, 3)
            short, need, tight = (x.reshape(frames, h) for x in (res.short, res.need, res.tight))
        _STATE["solves"] += frames * h
        missing = np.where(short, need - length, 0.0)
        for k, (i, it) in enumerate(hoses):
            mine = [r for r, row in enumerate(rows) if row[0] == k]
            line = HS.join([_with_ends(pts[:, r]) for r in mine])
            zero = np.zeros(line.shape)
            out[i] = (line, zero, zero)
            sh, ti = short[:, mine].any(axis=1), tight[:, mine].any(axis=1)
            if sh.any():                        # the first moment it happens, and the most it is short by
                problems[i] = ("short", int(np.argmax(sh)), float(missing[:, mine].sum(axis=1).max()))
            elif ti.any():
                problems[i] = ("tight", int(np.argmax(ti)), float(it.min_radius))
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


def _share(it, seg: int) -> float:
    """The share of the hose's length its segment ``seg`` has (a drawn hose through clips, task 0240)."""
    n = len(it.clips) + 1
    if n == 1:
        return 1.0
    have = it.get("shares")
    if have is not None and len(have) == n:
        a = np.maximum(np.array(have, dtype=float), 0.0)
        if a.sum() > 0.0:
            return float(a[seg] / a.sum())
    return 1.0 / n


def _guide(it, a: np.ndarray, b: np.ndarray):
    """Which way the hose lies, at ``frames`` moments: its CAD centreline carried along by the two parts its ends
    sit on – at end A it moves with A's part, at end B with B's, in between it goes over from the one to the other
    (``core/flex.carried``: a share of the turn-and-slide between the two parts, so the line keeps its bow across a
    hinge). In the CAD pose this is the CAD centreline itself. (frames, GUIDE_POINTS, 3), world; None for a hose
    without one."""
    part = it.part
    if part is None or GUIDE + "a" not in part or GUIDE + "b" not in part:
        return None
    ga = np.array(part[GUIDE + "a"], dtype=float).reshape(-1, 3)
    gb = np.array(part[GUIDE + "b"], dtype=float).reshape(-1, 3)
    if ga.shape != gb.shape or len(ga) != GUIDE_POINTS:
        return None
    from ..core import flex as HS
    wa = ga @ a[:, :3, :3].transpose(0, 2, 1) + a[:, None, :3, 3]
    wb = gb @ b[:, :3, :3].transpose(0, 2, 1) + b[:, None, :3, 3]
    return HS.carried(wa, wb)


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
        obs = end_objects(it)
        if any(o is None for o in obs):
            continue
        key = b"".join(_np(_world(o)).tobytes() for o in obs)
        if last.get((name, i)) != key:
            out.append((i, key))
    return out


def _down_in(m: np.ndarray) -> np.ndarray:
    """World down in the coordinates of the part whose world matrix is ``m``."""
    r = m[:3, :3]
    d = np.linalg.solve(r, np.array((0.0, 0.0, -1.0)))
    return d / max(np.linalg.norm(d), 1e-12)


def _remember(scene, i, it, mats: dict, arrays) -> None:
    """Keep what item i was solved for (its end parts' places) and its solved slice: moved as a whole later."""
    a = mats[it.a_part.name][0]
    rel = np.stack([np.linalg.solve(a, mats[o.name][0]) for o in end_objects(it)[1:]])
    lo, n = int(it.offset), int(it.points)
    _STATE["solved"][(scene.name, i)] = (a, rel, _down_in(a),
                                         tuple(np.array(x[0, lo:lo + n], dtype=float) for x in arrays))


def _carried(scene, i, it, mats: dict):
    """Item i's slice moved along with its end parts when they moved as one body since it was solved (the pair kept
    its places to each other and, for a hose, turned less than ``GRAVITY_TURN`` against gravity – its sag is the
    same then); None when it has to be solved again (task 0121: vessel motion moves every pair at every frame)."""
    kept = _STATE["solved"].get((scene.name, i))
    if kept is None:
        return None
    a0, rel0, down0, (co, fx, fz) = kept
    if co.shape[0] != int(it.points):
        return None
    a = mats[it.a_part.name][0]
    rel = np.stack([np.linalg.solve(a, mats[o.name][0]) for o in end_objects(it)[1:]])
    if rel.shape != rel0.shape or not np.allclose(rel, rel0, rtol=0.0, atol=RIGID_TOL):
        return None
    if it.kind == "HOSE" and float(np.dot(_down_in(a), down0)) < math.cos(GRAVITY_TURN):
        return None
    d = a @ np.linalg.inv(a0)
    r, t = d[:3, :3], d[:3, 3]
    return (co @ r.T + t)[None], (fx @ r.T)[None], (fz @ r.T)[None]


def _live(scene, force: bool = False) -> bool:
    """Solve the items whose end parts moved (all with ``force``) for where the parts are now and write the
    one-moment shapes mesh. An item whose two end parts moved as one body is moved, not solved. True when something
    was written."""
    moved = _moved(scene)
    if not moved and not force:
        return False
    per = sum(int(it.points) for it in scene.fresing.flex)
    whole = force or _arrays(scene, 1, per) is None
    if whole:
        per = _layout(scene)
        todo = _usable(scene)
        arrays = tuple(np.zeros((1, per, 3), np.float32) for _ in range(3))
        for k in [k for k in _STATE["solved"] if k[0] == scene.name]:
            del _STATE["solved"][k]
    else:
        usable = dict(_usable(scene))
        todo = [(i, usable[i]) for i, _key in moved if i in usable]
        arrays = _arrays(scene, 1, per)
    for i, key in moved:
        _STATE["last"][(scene.name, i)] = key
    if not todo and not whole:
        return False
    mats = _places_now(todo)
    solve = []
    for i, it in todo:
        carried = None if whole else _carried(scene, i, it, mats)
        if carried is None:
            solve.append((i, it))
        else:
            _patch(arrays, it, carried)
            _STATE["moved_rigid"] += 1
    if solve:
        results, problems = _solve(solve, mats, 1)
        for i, it in solve:
            _patch(arrays, it, results[i])
            _remember(scene, i, it, mats, arrays)
    _write_shapes(scene, arrays, 0)
    if solve:
        _note_problems(scene, solve, problems, None)
    if whole:
        sh = _shapes(scene)
        for key in (_ENDS, _ENDS_OBS, _ENDS_FIRST):       # the places read at a Build belong to that Build
            if key in sh:
                del sh[key]
        _sync(scene)
    return True


def _read_places(scene, its, first: int, frames: int) -> dict:
    """Step through the frames and read the world matrices of these items' end parts: name -> (frames, 4, 4).
    What ``READ_HOOKS`` ask for is read in the same pass and kept for them (``read_places`` hands it out)."""
    also = []
    for fn in READ_HOOKS:
        try:
            also += [ob for ob in (fn(scene) or ()) if ob is not None]
        except Exception as exc:                # never break a Build over another module's wish
            print("Fresing Render: read hook failed:", exc)
    return read_places(scene, [ob for _i, it in its for ob in end_objects(it)], first, frames, also=also,
                       keep=True)


def drop_read() -> None:
    """Forget the places a Build's pass through the frames read (the last module that wanted them calls this)."""
    _STATE["read"] = None


def _hide_curves(ob) -> list:
    """The object's keys on its visibility in the view (Build writes them for Show / Hide / Fade steps)."""
    ad = ob.animation_data
    if ad is None or ad.action is None or getattr(ad, "action_slot", None) is None:
        return []
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return [fc for fc in cb.fcurves if fc.data_path == "hide_viewport"] if cb is not None else []


def depends_on(obs) -> set:
    """The names of these objects and of every object their places depend on: parents, constraint targets, the
    objects their drivers read (and so on). Task 0159: reading the places, Blender works out only these – an object
    hidden in the view is left out of the scene's evaluation unless something shown depends on it."""
    seen: set = set()
    todo = [ob for ob in obs if ob is not None]
    while todo:
        ob = todo.pop()
        if ob.name in seen:
            continue
        seen.add(ob.name)
        if ob.parent is not None:
            todo.append(ob.parent)
        for c in getattr(ob, "constraints", ()):
            for attr in ("target", "pole_target"):
                t = getattr(c, attr, None)
                if isinstance(t, bpy.types.Object):
                    todo.append(t)
            for t in getattr(c, "targets", ()):         # (an Armature constraint's list)
                t = getattr(t, "target", None)
                if isinstance(t, bpy.types.Object):
                    todo.append(t)
        ad = ob.animation_data
        for fc in (ad.drivers if ad is not None else ()):
            for v in fc.driver.variables:
                for t in v.targets:
                    if isinstance(t.id, bpy.types.Object):
                        todo.append(t.id)
    return seen


def read_places(scene, obs, first: int, frames: int, keep_shown: bool = True, also=(), keep: bool = False) -> dict:
    """Step through ``frames`` frames from ``first`` and read where these objects are: name -> (frames, 4, 4), world.

    Objects that are only drawn by nodes (hoses, links, cables, the toolpath, chips) are hidden meanwhile, so they
    are not worked out at every frame. ``keep_shown`` False: also when they are among ``obs`` (a hidden object's
    place is worked out from its parent's, see ``_world``). ``also``: more objects read in the same pass (never
    kept shown), not returned. ``keep``: everything read is remembered until ``drop_read`` or ``forget`` – a later
    call for the same frames whose objects were all read then is answered from that, without stepping (the hoses'
    pass at Build reads for the cables too: blender/paths.py)."""
    gen = read_steps(scene, obs, first, frames, keep_shown=keep_shown, also=also, keep=keep)
    while True:
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value


def pause_read_for_save() -> bool:
    """Ctrl+S / autosave while ``read_steps`` runs (task 0187, bug hunt 6 row 3): the project is saved with the
    visibility and the frame it had before the read, not with most parts hidden. ``resume_read`` hides them again."""
    pz = _STATE.get("pause")
    if not pz:
        return False
    scene = bpy.data.scenes.get(pz[0])
    if scene is None:
        return False

    pz[2]()
    scene.frame_current, scene.frame_subframe = pz[1][0], pz[1][1]
    _STATE["paused"] = True
    return True


def resume_read() -> None:
    pz = _STATE.get("pause")
    if _STATE.pop("paused", False) and pz:
        pz[3]()


class ReadLost(RuntimeError):
    """An object the pass through the frames reads was deleted meanwhile (task 0192): the re-bake starts over."""


def read_steps(scene, obs, first: int, frames: int, keep_shown: bool = True, also=(), keep: bool = False):
    """``read_places`` as a generator (task 0160: the re-bake after a sea change runs as a long job with progress and
    Cancel): yields how far it is (0 … 1) after each frame, returns the places. Closed early (Cancel), it puts the
    visibility and the frame back and keeps nothing."""
    from . import clash
    ends = {ob.name: ob for ob in obs if ob is not None}
    names = sorted(ends)
    kept = _STATE["read"]
    if kept is not None and kept[0] == (scene.name, int(first), int(frames)) and all(n in kept[1] for n in names):
        return {n: kept[1][n] for n in names}
    extra = {ob.name: ob for ob in also if ob is not None and ob.name not in ends}
    every = {**ends, **extra}
    out = {n: np.empty((frames, 4, 4)) for n in every}
    if not every or frames < 1:
        return {n: out[n] for n in names}
    keep_at = (scene.frame_current, scene.frame_subframe)
    needed = set(names) if keep_shown else set()
    used = depends_on(every.values()) if _STATE.get("closure", True) else None
    # only drawn (hoses, links, toolpath, chips), or nothing read depends on it: not worked out per frame. Task 0159:
    # whatever no read place depends on stays hidden, also where Build keyed it shown (its visibility keys are muted
    # meanwhile) – the demo's pass through its 3,806 frames went from 54 to ~20 s, the places read exactly the same
    shy = [(o, o.hide_viewport) for o in scene.objects if o.name not in needed
           and (used is not None and o.name not in used or any(m.type == "NODES" for m in getattr(o, "modifiers", ())))
           and (not o.hide_viewport or used is not None)]
    # task 0192 (the owner's "StructRNA of type Object has been removed"): a sea, weather or vessel setting changed
    # while the re-bake job ran makes the surroundings again – the objects this pass hid are deleted meanwhile. Kept by
    # name and looked up again: what is gone is skipped
    muted = [(o.name, fc.data_path, fc.array_index) for o, _h in shy if used is not None
             for fc in _hide_curves(o) if not fc.mute]
    for o, _h in shy:
        if used is not None:
            for fc in _hide_curves(o):
                fc.mute = True
        if not o.hide_viewport:
            o.hide_viewport = True
    shy = [(o.name, h) for o, h in shy]

    def _curves():
        for name, path, index in muted:
            o = bpy.data.objects.get(name)
            fc = next((c for c in _hide_curves(o) if c.data_path == path and c.array_index == index), None) \
                if o is not None else None
            if fc is not None:
                yield fc

    def _back():                                 # visibility and keys as they were (also for a save in the job)
        for fc in _curves():
            fc.mute = False
        for name, h in shy:
            o = bpy.data.objects.get(name)
            if o is not None and o.hide_viewport != h:
                o.hide_viewport = h

    def _again():
        for fc in _curves():
            fc.mute = True
        for name, _h in shy:
            o = bpy.data.objects.get(name)
            if o is not None and not o.hide_viewport:
                o.hide_viewport = True

    # a save meanwhile writes the frame the user had: the one before ``at_first_frame`` showed the first frame (task
    # 0216, bug hunt 7 row 28: a copy saved during the re-bake reopened at frame 1, not at 150)
    shown = _STATE.get("shown") or []
    save_at = next((at for name, at in shown if name == scene.name), keep_at)
    _STATE["pause"] = (scene.name, save_at, _back, _again)
    try:
        with clash._Guard():
            for k in range(frames):
                scene.frame_set(first + k)
                _STATE["steps"] += 1
                for n, ob in every.items():
                    try:
                        out[n][k] = _np(_world(ob))
                    except ReferenceError:      # (deleted meanwhile: the places read so far are of no use)
                        raise ReadLost(n) from None
                yield (k + 1) / frames
    finally:
        _STATE["pause"] = None
        _back()
        scene.frame_set(keep_at[0], subframe=keep_at[1])
    if keep:
        _STATE["read"] = ((scene.name, int(first), int(frames)), out)
    return {n: out[n] for n in names}


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
            _STATE["solved"].pop((scene.name, only), None)      # its settings changed: solve it again
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
    same_layout = int(item.points) == (hose_points(item) if item.kind == "HOSE" else
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
        out = _bake(scene, step=True)
        _remember_motion(scene)
        return out
    except Exception as exc:                    # a Build never fails over a hose
        return [f"The hoses and drag chains could not be worked out ({exc or type(exc).__name__}): "
                "they show as they were"]
    finally:
        _STATE["busy"] -= 1


MOTION_KEY = "fr_flex_motion_key"       # on the scene: the vessel motion the built shapes were worked out for (0137)


def motion_changed(scene, force: bool = True) -> None:
    """Vessel motion changed after Build (vessel_motion.follow, task 0121): the end parts move another way at every
    frame, so a built animation's shapes are worked out again – at once in the background, in the window once the
    slider has rested ``MOTION_WAIT`` s (dragging it would step through the whole animation at every move).
    ``force`` False: only when the motion differs from the one of the Build (task 0137)."""
    if not len(scene.fresing.flex) or not _baked(scene) or _STATE["busy"]:
        return
    from . import vessel_motion
    if not force and not vessel_motion.moved_since(scene, MOTION_KEY, seabed=False):
        return
    from . import rebake
    if bpy.app.background:                      # one pass with whatever else the change needs (task 0192)
        rebake.background(scene, "flex", force)
        return
    rebake.request(scene, "flex", force)      # in the window: a long job with progress and Cancel (task 0160)


@contextmanager
def at_first_frame(scene):
    """Show the animation's first frame meanwhile, then the frame shown before (task 0160, bug hunt 0147 row 6): a
    re-bake after Build works everything out from the first frame, as Build does (task 0138) – let go, the clock of a
    sailing seabed and what follows them read the frame shown."""
    here, sub = int(scene.frame_current), float(scene.frame_subframe)
    first = int(scene.frame_start)
    moved = here != first or bool(sub)
    shown = _STATE.setdefault("shown", [])
    shown.append((scene.name, (here, sub)))      # (what a save meanwhile writes: read_steps)
    if moved:
        scene.frame_set(first)
    try:
        yield
    finally:
        if shown and shown[-1][0] == scene.name:
            shown.pop()
        if moved:
            scene.frame_set(here, subframe=sub)


def _motion_bake(scene, kept: bool = False) -> list[str]:
    """Work the built shapes out again for a new vessel motion. ``kept``: the places were read for this re-bake
    already (``read_places(keep=True)`` after the change, the re-bake job of task 0160)."""
    with at_first_frame(scene):
        _STATE["busy"] += 1
        if not kept:
            _STATE["read"] = None               # places read before the change are the old motion's
        try:
            out = _bake(scene, step=True)       # (``kept``: read_places answers from what the job read)
            _remember_motion(scene)
            return out
        except Exception as exc:                # never break the UI over a hose
            print("Fresing Render: hoses not worked out again:", exc)
            return []
        finally:
            if not kept:
                _STATE["read"] = None
            _STATE["busy"] -= 1


def _remember_motion(scene) -> None:
    try:
        from . import vessel_motion
        vessel_motion.remember(scene, MOTION_KEY, seabed=False)
    except Exception:
        pass


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
    if item.kind != "HOSE":
        return got[0]
    segs = len(item.clips) + 1                  # (each segment has its two extra points near its ends)
    drop = [s_ * (DRAWN - 1) + k for s_ in range(segs) for k in (1, DRAWN - 2)]
    return np.delete(got[0], drop, axis=0)


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
        if ob.name in taken or ob.get(build.PROP_EXCLUDED) or ob.get("fr_drawn"):
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
        uids = [it.part_uid, it.a_uid, it.b_uid] + it.link_uids.split("\n") + [c.uid for c in it.clips] \
            + it.replace_uids.split("\n")
        return any(u and (u in mapping or u in by_uid) for u in uids)

    todo = [it for it in s.flex if concerned(it)]
    last = {it.name: shape_now(scene, it) for it in todo if it.drawn}     # (task 0240: a part gone keeps its place)
    _STATE["busy"] += 1
    try:
        for it in todo:                         # first every item to its new parts, then read (ends never sit on
            with _quiet(it):                    # another flex part)
                for key in ("a", "b"):
                    ob = _new_object(scene, getattr(it, key + "_uid"), by_uid, mapping)
                    setattr(it, key + "_part", ob)
                    if ob is None and it.get(key + "_user"):
                        del it[key + "_user"]
                if it.drawn:                    # task 0240: the app's own object stays; clips go to the new parts
                    for c in it.clips:
                        c.part = _new_object(scene, c.uid, by_uid, mapping)
                    from . import drawn
                    drawn.after_model_update(scene, it, by_uid, mapping)
                elif it.kind == "HOSE" or it.made_links:
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
                if it.drawn:                    # nothing to read again: drawn by hand
                    why = broken(scene, it)
                    if why:
                        notes.append(f"{name}: {why} in the new revision – it keeps its last place")
                        pts = last.get(it.name)
                        if pts is not None and len(pts) >= 2 and _alive(scene, it.part):
                            from . import drawn
                            drawn.set_tube(it.part, pts, 0.5 * float(it.diameter if it.kind == "HOSE" else
                                                                     it.height))
                    continue
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
    _STATE["solved"].clear()
    _STATE["arrays"].clear()
    _STATE["inputs"].clear()
    _STATE["read"] = None


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
    try:                                        # task 0187 (bug hunt 6 row 4): undo can bring back a motion (water level,
        scene = bpy.context.scene               # sea state, speed) with the shapes worked out for another one
        if scene is not None and hasattr(scene, "fresing"):
            motion_changed(scene, force=False)
    except Exception as exc:                    # never break an undo over this
        print("Fresing Render: cables and hoses not worked out again after undo:", exc)


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
    from . import rebake
    for fn in (_settle, rebake._timer):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
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
