"""Assembly sequence step (task 0100): take a subassembly apart part by part, or put it together.

The step's settings live on the animation step (``FRAnimBlock.seq_*``); ``core/sequence.py`` works out the order, the
direction and the distance of every part and the times. Here:

- which parts move (``movers``): every part of the subassembly, except parts the app draws (hoses, cables, drag
  chain links: they follow their end parts), parts left out for good, and parts that ride on another part of the
  subassembly (a joint on a part carries them: they ride along with it);
- where they are when the step starts: the joints and moved parts of the earlier steps are set for a moment and the
  world is read (``_world_at``), so a subassembly a joint has turned comes apart along its own (turned) axes;
- the keys: each part's own place (``rest @ delta``, as Go to pose writes them), the world offset turned into the
  part's own space; hidden / faded at the end (or before it comes in) through the same keys as Show / Fade steps;
- trail lines (task 0073): one per part, made and removed by Build (``FRTrail.seq_owner``);
- a part whose way out runs into a part still in place is reported (rays from its points), not solved;
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
    parts: list = field(default_factory=list)       # objects that fly, model-tree order
    riders: dict = field(default_factory=dict)       # mover name -> parts that ride on it
    left_out: list = field(default_factory=list)     # hoses, chain links (drawn by the app)


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
        carrier = None
        p = o.parent
        while p is not None:
            if p.name in names:
                carrier = p
            p = p.parent
        if carrier is None:
            out.parts.append(o)
        else:
            out.riders.setdefault(carrier.name, []).append(o)
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
    b.seq_riders = sum(len(v) for v in m.riders.values())
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
    return core.Settings(direction=b.seq_direction, axis=tuple(axis_of(b, sub_world)), up=(0.0, 0.0, 1.0),
                         distance=float(b.seq_distance), by_size=bool(b.seq_by_size), order=b.seq_order,
                         part_time=float(b.seq_part_time), overlap=float(b.seq_overlap) / 100.0,
                         put_together=b.seq_mode == "TOGETHER")


def corners(ob) -> np.ndarray:
    m = ob.matrix_world
    return np.array([tuple(m @ Vector(c)) for c in ob.bound_box])


def plan_now(b, sub, parts: list, rays=None) -> list:
    """The plan from where the parts are in the scene now (their matrix_world). ``rays``: a ``Rays`` of ``parts``
    (made here when not given) lets Outside in wait with a part whose way out is blocked."""
    cp = [core.Part(o.name, corners(o), is_fastener(o), i) for i, o in enumerate(parts)]
    return core.plan(cp, settings(b, sub.matrix_world), rays if rays is not None else Rays(parts))


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
    from . import vessel_motion
    with vessel_motion.at_rest(scene), _WorldAt(scene, k.jstate, deltas):    # measured on a still sea (0121)
        rays = Rays(m.parts)
        moves = plan_now(b, sub, m.parts, rays)
        worlds = {o.name: o.matrix_world.copy() for o in m.parts}
        k.warnings.extend(blocked(b, m.parts, moves, rays))
    interp, ez = animation.EASING.get(b.easing, animation.EASING["SMOOTH"])
    merge = k.merge
    by_name = {o.name: o for o in m.parts}
    seq_start = b.start
    for mv in moves:
        ob = by_name[mv.name]
        f0 = animation.frame_of(k.anim, seq_start + mv.t0)
        f1 = max(animation.frame_of(k.anim, seq_start + mv.t1), f0 + 1)
        d_home = home[mv.name]
        d_out = _offset_delta(d_home, worlds[mv.name], mv.offset)
        keys = k.okeys.setdefault(mv.name, [(1, k.ostate.get(mv.name, ident), "CONSTANT", "AUTO")])
        if together:
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
        group = [ob] + m.riders.get(ob.name, [])
        _visibility(b, group, f_start, f0, f1, k, interp, ez)
    if b.seq_trails:
        _trails(scene, k.anim, b, m.parts)


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
        if i not in self._points:
            ob = self.parts[i]
            me = ob.data
            n = len(me.vertices)
            co = np.empty(n * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            idx = np.unique(np.linspace(0, n - 1, min(RAY_POINTS, n)).astype(int)) if n else []
            mw = ob.matrix_world
            self._points[i] = [mw @ Vector(tuple(co[k])) for k in idx]
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


def blocked(b, parts: list, moves: list, rays: Rays | None = None) -> list[str]:
    """Warnings for parts whose straight way out runs into a part of the subassembly that is still in place when they
    leave (taken apart; putting together is the same way backwards)."""
    from . import animation
    rays = rays or Rays(parts)
    index = {o.name: n for n, o in enumerate(parts)}
    rank = {mv.name: mv.rank for mv in moves}
    out = []
    for mv in sorted(moves, key=lambda x: x.rank):
        if mv.distance <= 0.0:
            continue
        i = index[mv.name]
        hit_by = next((o for o in parts if rank[o.name] > mv.rank
                       and rays.hit(i, index[o.name], mv.direction, mv.distance)), None)
        if hit_by is not None:
            ob = parts[i]
            out.append(f"'{animation.block_label(b)}': '{ob.get(build.PROP_NAME, ob.name)}' runs into "
                       f"'{hit_by.get(build.PROP_NAME, hit_by.name)}' on its way "
                       f"{'out' if b.seq_mode == 'APART' else 'in'}: try another order or direction")
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
    """What the preview's plan depends on: the step's settings, the subassembly and every part's place."""
    def flat(m):
        return tuple(round(x, 7) for r in m for x in r)
    names = ("seq_mode", "seq_direction", "seq_axis", "seq_distance", "seq_by_size", "seq_order", "seq_part_time",
             "seq_overlap", "target_uid")
    return (scene.name, b.as_pointer(), tuple(getattr(b, n) for n in names), sub.name, flat(sub.matrix_world),
            tuple((o.name, flat(o.matrix_world)) for o in parts))


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
    if _PLAN.get("key") != key:
        _PLAN.clear()
        _PLAN.update(key=key, moves=plan_now(b, sub, m.parts),
                     worlds={o.name: o.matrix_world.copy() for o in m.parts})
    moves, worlds = _PLAN["moves"], _PLAN["worlds"]
    total = core.duration(len(m.parts), b.seq_part_time, b.seq_overlap / 100.0)
    t = share * total
    by_name = {o.name: o for o in m.parts}
    for mv in moves:
        ob = by_name[mv.name]
        if PREVIEW not in ob:
            build.set_mat(ob, PREVIEW, ob.matrix_basis)
        p = (t - mv.t0) / max(1e-9, mv.t1 - mv.t0)
        p = animation.ease(b.easing, p)
        if b.seq_mode == "TOGETHER":
            p = 1.0 - p
        basis = build.get_mat(ob, PREVIEW)
        w = worlds[mv.name]
        ob.matrix_basis = basis @ w.inverted() @ Matrix.Translation(Vector(tuple(mv.offset)) * p) @ w
    bpy.context.view_layer.update()
