"""Assembly sequence step (task 0100): take a subassembly apart part by part, or put it together.

The step's settings live on the animation step (``FRAnimBlock.seq_*``); ``core/sequence.py`` works out the order, the
direction and the distance of every part and the times. Here:

- which parts move (``movers``): every part of the subassembly, except parts the app draws (hoses, cables, drag
  chain links: they follow their end parts) and parts left out for good. A part that rides on another part of the
  subassembly (a joint on a part carries it) flies on its own too (task 0129): it leaves before its carrier, from
  where the carrier has put it, and stays where it flew while the carrier flies out under it (``_rider_keys``);
- where they are when the step starts: the joints and moved parts of the earlier steps are set for a moment and the
  world is read (``_world_at``), so a subassembly a joint has turned comes apart along its own (turned) axes;
- the keys: each part's own place (``rest @ delta``, as Go to pose writes them), the world offset turned into the
  part's own space; hidden / faded at the end (or before it comes in) through the same keys as Show / Fade steps;
- trail lines (task 0073): one per part, made and removed by Build (``FRTrail.seq_owner``);
- a part whose way out runs into a part still in place is reported (rays from its points), not solved; a part whose
  way runs into a part outside the subassembly (a frame round it) takes another way (task 0129, ``Obstacles``);
- the preview: the slider in the step's box moves the parts in the view without building.

Put together = the exact reverse of take apart: the same lines and times played backwards, ending at the place the
part had before a Take apart step moved it (or where it is when the step starts).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import fasteners
from ..core import sequence as core
from . import build, joints, logic

KIND = "SEQUENCE"
PREVIEW = "fr_seq_preview"           # on a part while the preview has moved it: its basis before (16 numbers)
TRAIL_COLOR = (0.1, 0.55, 1.0)
MIN_HIT = 1e-4                        # m: a ray that hits closer than this only touches (a part sitting on another)
RAY_POINTS = 48                       # rays per part for the blocked-way check
SHRINK = 1e-4                         # m: a part's way is drawn this much inside it (a part on another only touches)
PAD = 1.2                             # a way out is tested this much further than asked (later asks hit the cache)


# ---------------------------------------------------------------------------
# which parts
# ---------------------------------------------------------------------------

def target(scene, b, uids: dict | None = None):
    if not b.target_uid:
        return None
    if uids is None:
        from . import states
        uids = states.by_uid(scene)
    return uids.get(b.target_uid)


@dataclass
class Movers:
    parts: list = field(default_factory=list)       # objects that fly, model-tree order (riders too, task 0129)
    riders: dict = field(default_factory=dict)       # carrier name -> parts that ride on it (directly or further up)
    left_out: list = field(default_factory=list)     # hoses, chain links (drawn by the app)
    carriers: dict = field(default_factory=dict)     # rider name -> the movers that carry it (nearest first)

    def carried(self) -> dict:
        """For core.plan: index of a part -> indices of the parts that ride on it."""
        return _carried_of(self.parts)


def movers(scene, ob, tree=None) -> Movers:
    out = Movers()
    if ob is None:
        return out
    tree = tree or logic.Tree(scene)
    try:
        from . import flex
        drawn = {o.name for o in flex.flex_parts(scene)}
    except Exception:
        drawn = set()
    order: list = []

    def walk(node):
        kids = sorted(tree.children(node), key=lambda o: o.name)
        for c in kids:
            order.append(c)
            walk(c)
    if ob.get(build.PROP_KIND) == "part":
        order.append(ob)
    walk(ob)
    parts = []
    for o in order:
        if o.get(build.PROP_KIND) != "part" or o.get(build.PROP_EXCLUDED) or o.type != "MESH":
            continue
        if o.name in drawn or o.get("fr_flex"):
            out.left_out.append(o)
            continue
        parts.append(o)
    names = {o.name for o in parts}
    for o in parts:
        out.parts.append(o)
        chain = []
        p = o.parent
        while p is not None:
            if p.name in names:
                chain.append(p.name)
            p = p.parent
        if chain:
            out.carriers[o.name] = chain
            for c in chain:
                out.riders.setdefault(c, []).append(o)
    return out


def is_fastener(ob) -> bool:
    return fasteners.parse(str(ob.get(build.PROP_NAME, ob.name))) is not None


def count(scene, b) -> None:
    """Store the step's part counts (shown in its box; Tree walks the whole scene, so not at every redraw)."""
    m = movers(scene, target(scene, b))
    n = len(m.parts)
    b.seq_count = n
    b.seq_fasteners = sum(1 for o in m.parts if is_fastener(o))
    b.seq_left_out = len(m.left_out)
    b.seq_riders = len(m.carriers)
    sync_duration(b)


def sync_duration(b) -> None:
    d = round(core.duration(b.seq_count, b.seq_part_time, b.seq_overlap / 100.0), 3)
    if abs(b.duration - d) > 1e-6:
        b.duration = d


def prepare(scene, anim) -> None:
    """Before Build works out the length: every Assembly sequence step's length from its parts."""
    for b in anim.blocks:
        if b.enabled and b.kind == KIND:
            if not b.seq_id:
                b.seq_id = uuid.uuid4().hex[:12]
            count(scene, b)


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------

AXES = {"X": 0, "Y": 1, "Z": 2}


def axis_of(b, sub_world: Matrix) -> Vector:
    """The world direction of the step's axis: the subassembly's own X / Y / Z (turned with it), + or -."""
    name = b.seq_axis
    col = sub_world.to_3x3().col[AXES.get(name.lstrip("-"), 2)].normalized()
    return -col if name.startswith("-") else col


def settings(b, sub_world: Matrix) -> core.Settings:
    m3 = sub_world.to_3x3()
    frame = tuple(tuple(m3.col[k].normalized()) for k in range(3))
    return core.Settings(direction=b.seq_direction, axis=tuple(axis_of(b, sub_world)), up=(0.0, 0.0, 1.0),
                         distance=float(b.seq_distance), by_size=bool(b.seq_by_size), order=b.seq_order,
                         part_time=float(b.seq_part_time), overlap=float(b.seq_overlap) / 100.0,
                         put_together=b.seq_mode == "TOGETHER", frame=frame)


def corners(ob) -> np.ndarray:
    m = ob.matrix_world
    return np.array([tuple(m @ Vector(c)) for c in ob.bound_box])


def plan_now(b, sub, parts: list, rays=None, obstacles=None, carried: dict | None = None, scene=None) -> list:
    """The plan from where the parts are in the scene now (their matrix_world). ``rays``: a ``Rays`` of ``parts``
    (made here when not given) lets Outside in wait with a part whose way out is blocked. ``obstacles``: an
    ``Obstacles`` (made here from ``scene`` when not given; False: none) sends a part whose way runs into a part
    outside the subassembly another way. ``carried``: ``Movers.carried()`` (worked out here when not given)."""
    scene = scene or bpy.context.scene
    cp = [core.Part(o.name, corners(o), is_fastener(o), i) for i, o in enumerate(parts)]
    if carried is None:
        carried = _carried_of(parts)
    if obstacles is None:
        obstacles = Obstacles(scene, sub, parts)
    return core.plan(cp, settings(b, sub.matrix_world), rays if rays is not None else Rays(parts),
                     obstacle=obstacles or None, carried=carried)


def _carried_of(parts: list) -> dict:
    index = {o.name: i for i, o in enumerate(parts)}
    out: dict = {}
    for i, o in enumerate(parts):
        p = o.parent
        while p is not None:
            if p.name in index:
                out.setdefault(index[p.name], []).append(i)
            p = p.parent
    return out


def _carriers_of(parts: list) -> dict:
    """name -> the parts of ``parts`` that carry it (a joint on them), nearest first."""
    names = {o.name for o in parts}
    out = {}
    for o in parts:
        chain = []
        p = o.parent
        while p is not None:
            if p.name in names:
                chain.append(p.name)
            p = p.parent
        if chain:
            out[o.name] = chain
    return out


def _offset_delta(delta: Matrix, world: Matrix, offset) -> Matrix:
    """The part's delta (its place relative to its rest place) moved by ``offset`` in the world, its parent kept."""
    return delta @ world.inverted() @ Matrix.Translation(Vector(tuple(offset))) @ world


class _WorldAt:
    """For a moment: every joint at ``values``, every object at its delta, the world updated (then put back)."""

    def __init__(self, scene, values: dict, deltas: dict):
        self.scene, self.values, self.deltas = scene, values, deltas

    def __enter__(self):
        s = self.scene.fresing
        self.keep_v = {j.name: joints.get_value(j) for j in s.joints if not j.follows}
        self.keep_b = {}
        by_name = self.scene.objects
        for j in s.joints:
            if j.name in self.values and not j.follows:
                joints.set_value(j, self.values[j.name], use_limits=False)
        for name, d in self.deltas.items():
            ob = by_name.get(name)
            if ob is None:
                continue
            self.keep_b[name] = ob.matrix_basis.copy()
            ob.matrix_basis = build.rest_basis(ob) @ d
        bpy.context.view_layer.update()
        return self

    def __exit__(self, *exc):
        s = self.scene.fresing
        for j in s.joints:
            if j.name in self.keep_v:
                joints.set_value(j, self.keep_v[j.name], use_limits=False)
        for name, m in self.keep_b.items():
            ob = self.scene.objects.get(name)
            if ob is not None:
                ob.matrix_basis = m
        bpy.context.view_layer.update()
        return False


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

@dataclass
class Keys:
    """What Build hands an Assembly sequence step (animation.bake's own key lists)."""
    anim: object
    jstate: dict
    ostate: dict
    okeys: dict
    vkeys: dict
    fkeys: dict
    fxray: dict
    home: dict                    # name -> delta before a Take apart step moved it
    merge: object
    warnings: list
    uids: dict
    tree: object = None


def label(b) -> str:
    what = b.target_name or "?"
    return f"Take apart {what}" if b.seq_mode == "APART" else f"Put together {what}"


def bake_step(scene, b, f_start: int, k: Keys) -> None:
    from . import animation
    name = animation.block_label(b)
    sub = target(scene, b, k.uids)
    if sub is None:
        k.warnings.append(f"'{name}': pick a subassembly" if not b.target_uid else f"'{name}': subassembly not found")
        return
    m = movers(scene, sub, k.tree)
    if not m.parts:
        k.warnings.append(f"'{name}': '{b.target_name}' has no parts that can move")
        return
    ident = Matrix.Identity(4)
    together = b.seq_mode == "TOGETHER"
    start = {o.name: k.ostate.get(o.name, ident) for o in m.parts}
    home = {n: (k.home.get(n, d) if together else d) for n, d in start.items()}
    deltas = dict(k.ostate)
    deltas.update(home)
    hidden = {n for n, keys in k.vkeys.items() if keys and _value_at(keys, f_start)}
    from . import vessel_motion
    with vessel_motion.at_rest(scene), _WorldAt(scene, k.jstate, deltas):    # measured on a still sea (0121)
        rays = Rays(m.parts)
        obstacles = Obstacles(scene, sub, m.parts, hidden=hidden, tree=k.tree)
        moves = plan_now(b, sub, m.parts, rays, obstacles, m.carried(), scene)
        worlds = {o.name: o.matrix_world.copy() for o in m.parts}
        k.warnings.extend(blocked(b, m.parts, moves, rays, obstacles))
    interp, ez = animation.EASING.get(b.easing, animation.EASING["SMOOTH"])
    merge = k.merge
    by_name = {o.name: o for o in m.parts}
    frames = {}
    for mv in moves:
        f0 = animation.frame_of(k.anim, b.start + mv.t0)
        frames[mv.name] = (f0, max(animation.frame_of(k.anim, b.start + mv.t1), f0 + 1))
    for mv in moves:
        ob = by_name[mv.name]
        f0, f1 = frames[mv.name]
        d_home = home[mv.name]
        d_out = _offset_delta(d_home, worlds[mv.name], mv.offset)
        keys = k.okeys.setdefault(mv.name, [(1, k.ostate.get(mv.name, ident), "CONSTANT", "AUTO")])
        if mv.name in m.carriers:
            _rider_keys(b, mv, moves, m.carriers[mv.name], frames, worlds[mv.name], d_home, f_start, keys, merge)
            k.ostate[mv.name] = keys[-1][1]
            if together:
                k.home.pop(mv.name, None)
            else:
                k.home.setdefault(mv.name, start[mv.name])
        elif together:
            merge(keys, f_start, d_out, "CONSTANT")         # out from the step's start, then each comes in
            merge(keys, f0, d_out, interp, ez)
            merge(keys, f1, d_home, "CONSTANT")
            k.ostate[mv.name] = d_home
            k.home.pop(mv.name, None)
        else:
            merge(keys, f0, start[mv.name], interp, ez)
            merge(keys, f1, d_out, "CONSTANT")
            k.ostate[mv.name] = d_out
            k.home.setdefault(mv.name, start[mv.name])
        _visibility(b, [ob], f_start, f0, f1, k, interp, ez)
    if b.seq_trails:
        _trails(scene, k.anim, b, m.parts)


def _value_at(keys: list, frame: int):
    """The value of a list of (frame, value, …) keys at ``frame`` (the last key at or before it)."""
    v = keys[0][1]
    for f, val, *_rest in keys:
        if f > frame:
            break
        v = val
    return v


def _share(b, mv, t: float) -> float:
    """How far out ``mv`` is at ``t`` s from the step's start: 0 = in place, 1 = out (eased as the step)."""
    from . import animation
    p = animation.ease(b.easing, (t - mv.t0) / max(1e-9, mv.t1 - mv.t0))
    return 1.0 - p if b.seq_mode == "TOGETHER" else p


def _rider_offset(b, mv, by_name: dict, carriers: list, t: float) -> Vector:
    """The world offset a rider's own place must take at ``t`` so that it is where it flew to: its own flight minus
    what its carriers' flights move it by (they carry it)."""
    x = Vector(tuple(mv.offset)) * _share(b, mv, t)
    for c in carriers[:1]:                   # the nearest carrier's world motion is its own flight
        cm = by_name.get(c)
        if cm is not None:
            x -= Vector(tuple(cm.offset)) * _share(b, cm, t)
    return x


def _rider_keys(b, mv, moves: list, carriers: list, frames: dict, world: Matrix, d_home: Matrix, f_start: int,
                keys: list, merge) -> None:
    """A rider's keys: one on every frame while it or a part that carries it flies (LINEAR in between), so it is
    exactly where it flew to on every frame while its carrier flies out under it (or comes in, put together)."""
    from . import animation
    by_name = {x.name: x for x in moves}
    carriers = carriers[:1]          # the nearest carrier's world motion is its own flight (it is kept so itself)
    want = set()
    for f0, f1 in [frames[mv.name]] + [frames[c] for c in carriers if c in frames]:
        want.update(range(f0, f1 + 1))

    def share_at(x, f):
        # measured between the part's own key frames, exactly as Blender eases a carrier between its two keys
        f0, f1 = frames[x.name]
        p = animation.ease(b.easing, (f - f0) / max(1, f1 - f0))
        return 1.0 - p if b.seq_mode == "TOGETHER" else p

    def offset_at(f):
        x = Vector(tuple(mv.offset)) * share_at(mv, f)
        for c in carriers:
            cm = by_name.get(c)
            if cm is not None:
                x -= Vector(tuple(cm.offset)) * share_at(cm, f)
        return x
    if b.seq_mode == "TOGETHER":
        merge(keys, f_start, _offset_delta(d_home, world, offset_at(f_start)), "CONSTANT")
    for f in sorted(want):
        merge(keys, f, _offset_delta(d_home, world, offset_at(f)), "LINEAR")
    last = max(want)
    keys[-1] = (last, keys[-1][1], "CONSTANT", "AUTO")


def _visibility(b, group: list, f_start: int, f0: int, f1: int, k: Keys, interp: str, ez: str) -> None:
    """Hide at the end / Fade (take apart), or hidden until it comes in / fading in (put together)."""
    end = b.seq_end
    if end == "STAY":
        return
    together = b.seq_mode == "TOGETHER"
    merge = k.merge
    for t in group:
        keys = k.vkeys.setdefault(t.name, [(1, bool(t.hide_render), "CONSTANT", "AUTO")])
        if together:
            merge(keys, f_start, True, "CONSTANT")
            merge(keys, f0, False, "CONSTANT")
        else:
            merge(keys, f1, True, "CONSTANT")
        if end != "FADE":
            continue
        from . import fade
        for o in fade.prepare(t):
            k.fxray[o.name] = (False, tuple(fade.DEFAULT_COLOR), float(fade.DEFAULT_STRENGTH))
            v0, v1 = (1.0, 0.0) if together else (0.0, 1.0)
            fk = k.fkeys.setdefault(o.name, [(1, float(o.get(fade.FADE, 0.0)) if not o.get(fade.LOOK) else 0.0,
                                              "CONSTANT", "AUTO")])
            if together:
                merge(fk, f_start, v0, "CONSTANT")
            merge(fk, f0, v0, interp, ez)
            merge(fk, f1, v1, "CONSTANT")


# ---------------------------------------------------------------------------
# a part whose way out is blocked
# ---------------------------------------------------------------------------

class Rays:
    """Rays from a part's points along its way out, against the other parts where they stand (world, read once).
    ``core.plan`` sets ``dirs`` and asks ``rays(i, j)``: does part i, leaving, run into part j?"""

    FAR = 1e4                                    # m: "anywhere along its way"

    def __init__(self, parts: list):
        self.parts = parts
        self.dirs = None
        self._trees: dict = {}
        self._points: dict = {}

    def tree(self, j):
        if j not in self._trees:
            from mathutils.bvhtree import BVHTree
            ob = self.parts[j]
            me = ob.data
            mw = ob.matrix_world
            self._trees[j] = (BVHTree.FromPolygons([mw @ v.co for v in me.vertices],
                                                   [tuple(p.vertices) for p in me.polygons])
                              if len(me.polygons) else None)
        return self._trees[j]

    def points(self, i) -> list:
        """Up to RAY_POINTS of the part's points (world), drawn SHRINK inside it: a part sliding along the face it
        sits on would graze that part's edges (task 0129)."""
        if i not in self._points:
            pts, _t, _e = _mesh_world(self.parts[i], SHRINK, triangles=False)
            n = len(pts)
            idx = np.unique(np.linspace(0, n - 1, min(RAY_POINTS, n)).astype(int)) if n else []
            self._points[i] = [Vector(tuple(pts[k])) for k in idx]
        return self._points[i]

    def hit(self, i, j, direction, distance: float) -> bool:
        tr = self.tree(j)
        if tr is None:
            return False
        u = Vector(tuple(direction))
        for p in self.points(i):
            loc, _n, _k, d = tr.ray_cast(p, u, distance)
            if loc is not None and d is not None and d > MIN_HIT:
                return True
        return False

    def __call__(self, i, j) -> bool:
        return self.hit(i, j, self.dirs[i], self.FAR)


def _mesh_world(ob, shrink: float = 0.0, triangles: bool = True):
    """(points (n, 3) world, triangles (m, 3), edges (k, 2)) of a part's mesh; ``shrink``: every side drawn this much
    inside (towards the middle of its box)."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tri = np.zeros(0, dtype=np.int32)
    ed = np.zeros(0, dtype=np.int32)
    if triangles:
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        ed = np.empty(len(me.edges) * 2, dtype=np.int32)
        me.edges.foreach_get("vertices", ed)
    mw = np.array(ob.matrix_world)
    pts = co @ mw[:3, :3].T + mw[:3, 3] if n else np.zeros((0, 3))
    if shrink > 0.0 and n:
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        mid, half = (lo + hi) / 2.0, (hi - lo) / 2.0
        k = np.where(half > shrink, 1.0 - shrink / np.maximum(half, 1e-12), 0.5)
        pts = mid + (pts - mid) * k
    return pts, tri.reshape(-1, 3), ed.reshape(-1, 2)


class Obstacles:
    """The model's parts outside the subassembly that a part's way can run into (task 0129). ``core.plan`` asks
    ``obstacles(i, u, dist)``: does part i, flying ``dist`` m along ``u``, run into one of them?

    Only parts whose box meets the box of the way are looked at (NumPy, all at once); for those, the part's way – its
    mesh drawn ``SHRINK`` inside it, at the start, at the end and its edges swept between – is tested against their
    triangles near the subassembly (BVH overlap), and rays from their points inside the way go back against the part
    (a small part lying wholly inside the way). A part only touching another (on a plate) is not stopped."""

    def __init__(self, scene, sub, parts: list, hidden=(), tree=None):
        self.parts = parts
        self.hit_name = {}
        self._mesh: dict = {}
        self._trees: dict = {}
        self._pts: dict = {}
        self._clear: dict = {}                       # (i, way) -> furthest distance found clear
        self._stop: dict = {}                        # (i, way) -> (nearest distance found blocked, obstacle)
        tree = tree or logic.Tree(scene)
        inside = {o.name for o in parts}
        if sub is not None:
            inside.add(sub.name)
            inside.update(o.name for o in logic.descendants(sub, tree))
        try:
            from . import flex
            drawn = {o.name for o in flex.flex_parts(scene)}
        except Exception:
            drawn = set()
        hidden = set(hidden)
        movers_ = {o.name for o in parts}

        def carried(o):                                # rides on a part that flies (a joint on it): flies along
            p = o.parent
            while p is not None:
                if p.name in movers_:
                    return True
                p = p.parent
            return False
        obs = []
        for o in scene.objects:
            if (o.type != "MESH" or o.get(build.PROP_KIND) != "part" or o.get(build.PROP_EXCLUDED)
                    or o.name in inside or o.name in drawn or o.get("fr_flex") or o.name in hidden
                    or o.hide_render or not len(o.data.polygons) or carried(o)):
                continue
            obs.append(o)
        self.obs = obs
        if obs:
            bb = np.array([[tuple(o.matrix_world @ Vector(c)) for c in o.bound_box] for o in obs])
            self.lo, self.hi = bb.min(axis=1), bb.max(axis=1)
        else:
            self.lo = self.hi = np.zeros((0, 3))
        pc = np.array([[tuple(o.matrix_world @ Vector(c)) for c in o.bound_box] for o in parts]).reshape(-1, 3) \
            if parts else np.zeros((1, 3))
        lo, hi = pc.min(axis=0), pc.max(axis=0)
        reach = 2.0 * float(np.linalg.norm(hi - lo)) + 1.0
        self.region = (lo - reach, hi + reach)        # obstacle triangles further out are left out of their trees

    def __bool__(self):
        return bool(self.obs)

    def mesh(self, i):
        """(points, triangles, their normals, edges, the two triangles of each edge (-1: none)) of part i, world,
        drawn SHRINK inside it."""
        if i not in self._mesh:
            pts, tri, _ed = _mesh_world(self.parts[i], SHRINK)
            if len(tri):
                a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
                nrm = np.cross(b - a, c - a)
                e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
                f = np.tile(np.arange(len(tri)), 3)
                key = e[:, 0].astype(np.int64) * (len(pts) + 1) + e[:, 1]
                o = np.argsort(key, kind="stable")
                key, e, f = key[o], e[o], f[o]
                first = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
                count = np.diff(np.r_[first, len(key)])
                f0 = f[first]
                f1 = np.where(count >= 2, f[np.minimum(first + 1, len(f) - 1)], -1)
                edges, pairs = e[first], np.stack([f0, f1], axis=1)
            else:
                nrm = np.zeros((0, 3))
                edges, pairs = np.zeros((0, 2), dtype=int), np.zeros((0, 2), dtype=int)
            self._mesh[i] = (pts, tri, nrm, edges, pairs)
        return self._mesh[i]

    def tree(self, k):
        if k not in self._trees:
            from mathutils.bvhtree import BVHTree
            pts, tri, _ed = _mesh_world(self.obs[k])
            lo, hi = self.region
            if len(tri):
                t = pts[tri]
                keep = np.all(t.max(axis=1) >= lo, axis=1) & np.all(t.min(axis=1) <= hi, axis=1)
                tri = tri[keep]
            self._pts[k] = pts
            self._trees[k] = BVHTree.FromPolygons(pts.tolist(), tri.tolist()) if len(tri) else None
        return self._trees[k]

    def _way_tree(self, i, u, dist):
        """The surface of the room part i sweeps moving ``dist`` along ``u``: its faces turned away from the way at
        the start, those turned towards it at the end, and the edges between the two kinds swept between."""
        from mathutils.bvhtree import BVHTree
        pts, tri, nrm, edges, pairs = self.mesh(i)
        u = np.asarray(u, dtype=float)
        n = len(pts)
        s = nrm @ u
        back, front = tri[s <= 0.0], tri[s >= 0.0] + n
        side = s[pairs[:, 0]] > 0.0
        other = np.where(pairs[:, 1] >= 0, s[np.maximum(pairs[:, 1], 0)] > 0.0, ~side)
        sil = edges[side != other]
        quads = np.stack([sil[:, 0], sil[:, 1], sil[:, 1] + n, sil[:, 0] + n], axis=1)
        allp = np.concatenate([pts, pts + u * dist])
        return BVHTree.FromPolygons(allp.tolist(), back.tolist() + front.tolist() + quads.tolist()), allp

    def __call__(self, i, u, dist) -> bool:
        if not len(self.obs) or dist <= 0.0:
            return False
        key = (i, tuple(np.round(np.asarray(u, dtype=float), 6)))
        if dist <= self._clear.get(key, -1.0):
            return False
        stop = self._stop.get(key)
        if stop is not None and dist >= stop[0]:
            self.hit_name[i] = stop[1]
            return True
        if not len(self.mesh(i)[0]):
            return False
        if not self._test(i, u, dist * PAD, key):             # a little further: a later ask a little further is known
            return False
        return self._test(i, u, dist, key)                    # blocked further out: the asked distance itself

    def _test(self, i, u, dist, key) -> bool:
        if dist <= self._clear.get(key, -1.0):
            return False
        stop = self._stop.get(key)
        if stop is not None and dist >= stop[0]:
            self.hit_name[i] = stop[1]
            return True
        pts = self.mesh(i)[0]
        a, z = pts.min(axis=0), pts.max(axis=0)
        off = np.asarray(u, dtype=float) * dist
        lo, hi = np.minimum(a, a + off), np.maximum(z, z + off)
        near = np.flatnonzero(np.all(self.hi > lo, axis=1) & np.all(self.lo < hi, axis=1))
        if not len(near):
            self._clear[key] = max(dist, self._clear.get(key, -1.0))
            return False
        way, _allp = self._way_tree(i, u, dist)
        back = None
        for k in near:
            tr = self.tree(int(k))
            if tr is None:
                continue
            hit = bool(way.overlap(tr))
            if not hit:                                       # an obstacle wholly inside the way
                p = self._pts[int(k)]
                p = p[np.all((p > lo) & (p < hi), axis=1)]
                if len(p):
                    if back is None:
                        from mathutils.bvhtree import BVHTree
                        _p, tri = self.mesh(i)[:2]
                        back = BVHTree.FromPolygons(_p.tolist(), tri.tolist())
                    neg = Vector(tuple(-np.asarray(u, dtype=float)))
                    for q in p[np.unique(np.linspace(0, len(p) - 1, min(RAY_POINTS, len(p))).astype(int))]:
                        loc, _n, _f, d = back.ray_cast(Vector(tuple(q)), neg, dist)
                        if loc is not None:
                            hit = True
                            break
            if hit:
                name = self.obs[int(k)].get(build.PROP_NAME, self.obs[int(k)].name)
                self.hit_name[i] = name
                old = self._stop.get(key)
                if old is None or dist < old[0]:
                    self._stop[key] = (dist, name)
                return True
        self._clear[key] = max(dist, self._clear.get(key, -1.0))
        return False


def blocked(b, parts: list, moves: list, rays: Rays | None = None, obstacles: Obstacles | None = None) -> list[str]:
    """Warnings for parts whose straight way out runs into a part of the subassembly that is still in place when they
    leave (taken apart; putting together is the same way backwards), or into a part outside it (task 0129: only
    when no other way was clear)."""
    from . import animation
    rays = rays or Rays(parts)
    index = {o.name: n for n, o in enumerate(parts)}
    rank = {mv.name: mv.rank for mv in moves}
    way = "out" if b.seq_mode == "APART" else "in"
    out = []
    for mv in sorted(moves, key=lambda x: x.rank):
        if mv.distance <= 0.0:
            continue
        i = index[mv.name]
        ob = parts[i]
        what = ob.get(build.PROP_NAME, ob.name)
        hit_by = next((o for o in parts if rank[o.name] > mv.rank
                       and rays.hit(i, index[o.name], mv.direction, mv.distance)), None)
        if hit_by is not None:
            out.append(f"'{animation.block_label(b)}': '{what}' runs into "
                       f"'{hit_by.get(build.PROP_NAME, hit_by.name)}' on its way {way}: try another order or direction")
        elif obstacles and obstacles(i, mv.direction, mv.distance):
            out.append(f"'{animation.block_label(b)}': '{what}' runs into '{obstacles.hit_name.get(i, '?')}' "
                       f"(outside the subassembly) on its way {way}, and no other way is clear: try another "
                       "direction or a shorter distance")
    return out


# ---------------------------------------------------------------------------
# trail lines (task 0073)
# ---------------------------------------------------------------------------

def _trails(scene, anim, b, parts: list) -> None:
    """One trail line per part of this step (made once; Build reads them along the motion afterwards)."""
    from . import trails
    s = scene.fresing
    have = {(t.seq_owner, t.part.name if t.part is not None else "") for t in s.trails}
    for ob in parts:
        if (b.seq_id, ob.name) in have:
            continue
        keep = s.trails_index
        t = trails.add(scene, ob, "CLICKED", local=_box_centre(ob))
        t["_busy"] = True
        t.seq_owner = b.seq_id
        t.animation = anim.name
        t.color = TRAIL_COLOR
        t.thickness = 0.002
        t.name = f"{label(b)}: {ob.get(build.PROP_NAME, ob.name)}"
        del t["_busy"]
        s.trails_index = keep


def _box_centre(ob) -> tuple:
    bb = [Vector(c) for c in ob.bound_box]
    return tuple(sum(bb, Vector()) / 8.0)


def tidy_trails(scene) -> int:
    """Remove the trail lines of Assembly sequence steps that are gone, off, or no longer want them."""
    from . import trails
    s = scene.fresing
    want = {b.seq_id for a in s.animations for b in a.blocks
            if b.kind == KIND and b.enabled and b.seq_trails and b.seq_id}
    n = 0
    for i in range(len(s.trails) - 1, -1, -1):
        t = s.trails[i]
        if t.seq_owner and t.seq_owner not in want:
            trails.remove(scene, i)
            n += 1
    return n


# ---------------------------------------------------------------------------
# preview (without building)
# ---------------------------------------------------------------------------

_PLAN: dict = {}                      # the preview's plan while its slider moves (task 0121): "key", "moves", …


def end_preview(scene) -> None:
    """Put back every part the preview moved (Build, Clear keys, a model update)."""
    _PLAN.clear()
    moved = False
    for ob in scene.objects:
        if PREVIEW in ob:
            m = build.get_mat(ob, PREVIEW)
            if m is not None:
                ob.matrix_basis = m
            del ob[PREVIEW]
            moved = True
    for a in scene.fresing.animations:
        for b in a.blocks:
            if b.kind == KIND and b.seq_preview != 0.0:
                b["seq_preview"] = 0.0
    if moved:
        bpy.context.view_layer.update()


def _plan_key(scene, b, sub, parts: list) -> tuple:
    """What the preview's plan depends on: (the step's settings and the part names, every place as numbers). The
    places are compared within 1 µm (``_same_plan``): parts put back from the preview come back with float32 noise,
    which made the plan be worked out a second time at the slider's second step (found in task 0129)."""
    names = ("seq_mode", "seq_direction", "seq_axis", "seq_distance", "seq_by_size", "seq_order", "seq_part_time",
             "seq_overlap", "target_uid")
    ident = (scene.name, b.as_pointer(), tuple(getattr(b, n) for n in names), sub.name, tuple(o.name for o in parts))
    places = np.array([list(sub.matrix_world)] + [list(o.matrix_world) for o in parts], dtype=float).ravel()
    return ident, places


def _same_plan(a, b) -> bool:
    return (a is not None and b is not None and a[0] == b[0] and a[1].shape == b[1].shape
            and bool(np.allclose(a[1], b[1], rtol=0.0, atol=1e-6)))


def preview(scene, b, share: float) -> None:
    """Show the step at ``share`` (0 … 1 of its length) in the view: the parts move, nothing is keyed. The plan is
    kept while only the slider moves (task 0121: planning again at every step took seconds on big subassemblies)."""
    from . import animation
    if scene.fresing.anim_baked:
        keep = b.seq_preview
        animation.clear_keys(scene)                   # keys would hold the parts where Build left them
        b["seq_preview"] = keep                       # (clear_keys ends every preview: this one goes on)
        scene.fresing.last_message = ("The Assembly sequence preview took the built animation off: "
                                      "press Build animation again when done")
    for ob in scene.objects:                          # back to where they were, then plan from there
        if PREVIEW in ob:
            m = build.get_mat(ob, PREVIEW)
            if m is not None:
                ob.matrix_basis = m
    bpy.context.view_layer.update()
    sub = target(scene, b)
    m = movers(scene, sub) if sub is not None else None
    if share <= 0.0 or sub is None or not m.parts:
        _PLAN.clear()
        for ob in scene.objects:
            if PREVIEW in ob:
                del ob[PREVIEW]
        return
    key = _plan_key(scene, b, sub, m.parts)
    if not _same_plan(_PLAN.get("key"), key):
        _PLAN.clear()
        _PLAN.update(key=key, moves=plan_now(b, sub, m.parts, carried=m.carried(), scene=scene),
                     worlds={o.name: o.matrix_world.copy() for o in m.parts})
    moves, worlds = _PLAN["moves"], _PLAN["worlds"]
    total = core.duration(len(m.parts), b.seq_part_time, b.seq_overlap / 100.0)
    t = share * total
    by_name = {o.name: o for o in m.parts}
    by_move = {mv.name: mv for mv in moves}
    for mv in moves:
        ob = by_name[mv.name]
        if PREVIEW not in ob:
            build.set_mat(ob, PREVIEW, ob.matrix_basis)
        if mv.name in m.carriers:
            x = _rider_offset(b, mv, by_move, m.carriers[mv.name], t)
        else:
            x = Vector(tuple(mv.offset)) * _share(b, mv, t)
        basis = build.get_mat(ob, PREVIEW)
        w = worlds[mv.name]
        ob.matrix_basis = basis @ w.inverted() @ Matrix.Translation(x) @ w
    bpy.context.view_layer.update()
