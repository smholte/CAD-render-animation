"""Clash check (task 0065): after Build, find parts that run into each other in the animation.

``check(scene)`` (or ``steps(scene)``, which the panel's operator runs a little at a time so it can show progress and
be cancelled) goes through the built animation and lists every pair of parts that goes deeper into each other than
the clash depth (more than at the first frame), with the frames and the depth. How it works: ``core/clash.py``.

What is checked: every part of the model (not the ones excluded for good) and the tool copies a G-code build makes.
Chips, coolant, air, labels, decals, the toolpath, the surroundings and props, the hand of a tool change are not parts,
so they are left out. Milling (tasks 0027, 0040): the cutting part of a tool (from its tip up to the end of its
flutes, from the tool library) going through the workpiece is meant to cut, so it does not count; the rest of the
tool, its holder and the spindle do. With milling on, the workpiece is checked as it is cut at that moment.

**Hook for later tasks** (hoses and cables, task 0058): ``HOOKS`` holds functions ``fn(scene) -> (add, leave_out)``,
two lists of objects: objects to check as well (they must be meshes) and objects to leave out. A hose that bends
along with the parts it joins should be left out (it touches them on purpose).

The result is kept with the project (``scene.fresing.clash``, a few rows) together with a fingerprint of the built
keys: when the animation is built again the rows no longer fit it and are cleared (a timer started by a depsgraph
handler; ``drop_if_stale`` does it by hand).
"""

from __future__ import annotations

import hashlib
import math
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent

from ..core import clash as core
from . import build

MARK = "Clash: "                        # timeline markers this check makes start with it
RED = (1.0, 0.08, 0.05, 0.5)
HOOKS: list = []                        # fn(scene) -> (objects to add, objects to leave out); see the docstring
_RUNTIME: dict = {}                     # per scene: the signature cache, the parts shown red, the progress
_DRAW = {"handle": None, "batches": {}}


class ClashError(RuntimeError):
    pass


def settings(scene):
    return scene.fresing.clash


def runtime(scene) -> dict:
    return _RUNTIME.setdefault(scene.name, {})


# ---------------------------------------------------------------------------
# the built animation's fingerprint: results belong to one build
# ---------------------------------------------------------------------------

def _anim_ids(scene) -> list:
    from . import animation
    return [ob for ob in scene.objects if ob.get(animation.TAG)]


def _cheap_key(scene) -> tuple:
    from . import animation
    acts = [a.session_uid for a in bpy.data.actions if a.get(animation.TAG)]
    return (scene.fresing.anim_baked, scene.frame_start, scene.frame_end, len(acts), sum(acts))


def build_signature(scene) -> str:
    """Changes whenever the built keys change (another Build of other steps, Clear keys): every key of the objects the
    animation moves or hides, the frame range and the frame rate."""
    rt = runtime(scene)
    key = _cheap_key(scene)
    if rt.get("sig_key") == key and rt.get("sig"):
        return rt["sig"]
    from . import machining
    h = hashlib.blake2b(digest_size=16)
    s = scene.fresing
    h.update(f"{s.anim_baked}:{scene.frame_start}:{scene.frame_end}:{scene.render.fps}".encode())
    for ob in sorted(_anim_ids(scene), key=lambda o: o.name):
        h.update(ob.name.encode())
        for fc in machining._fcurves(ob):
            machining._hash_fcurve(h, fc)
    sig = h.hexdigest()
    rt["sig_key"], rt["sig"] = key, sig
    return sig


def is_built(scene) -> bool:
    from . import animation
    return bool(scene.fresing.anim_baked) and animation.has_keys(scene)


def state(scene) -> dict:
    """{'built', 'checked', 'stale', 'clashes', 'near', 'text'}: what the panel's header and the queue say."""
    c = settings(scene)
    built = is_built(scene)
    checked = bool(c.checked)
    stale = checked and (not built or c.signature != build_signature(scene))
    out = {"built": built, "checked": checked and not stale, "stale": stale,
           "clashes": int(c.clashes) if checked and not stale else 0,
           "near": int(c.near_misses) if checked and not stale else 0}
    if not built:
        out["text"] = "Build first" if not checked else "Not checked since the last Build"
    else:
        out["text"] = core.header(checked, stale, out["clashes"], out["near"])
    return out


def queue_note(scene, anim_name: str) -> str:
    """The one-line note when animation ``anim_name`` goes into the render queue ('' = nothing to say)."""
    c = settings(scene)
    st = state(scene)
    checked = st["checked"] and c.anim == anim_name
    return core.queue_note(anim_name, checked, st["clashes"] if checked else 0)


# ---------------------------------------------------------------------------
# what is checked
# ---------------------------------------------------------------------------

def label(ob) -> str:
    """The part's name as the tree shows it ("BOLT M8x20", or Inventor's "BOLT M8x20:3" when there are more)."""
    name = ob.get(build.PROP_NAME, ob.name)
    inst = ob.get(build.PROP_INSTANCE, "") or ""
    return inst if inst.startswith(name + ":") else name


def objects(scene) -> list:
    """The meshes the check compares: the parts (not the excluded ones) and the tool copies of a G-code build."""
    from . import gcode
    out = [ob for ob in build.iter_parts(scene) if not ob.get(build.PROP_EXCLUDED)]
    names = {ob.name for ob in out}
    for ob in gcode.copies(scene).values():
        if ob.type == "MESH" and ob.name in scene.objects and ob.name not in names:
            out.append(ob)
            names.add(ob.name)
    leave = set()
    for fn in HOOKS:
        add, left = fn(scene)
        for ob in add or ():
            if ob is not None and ob.type == "MESH" and ob.name not in names and ob.name in scene.objects:
                out.append(ob)
                names.add(ob.name)
        leave |= {ob.name for ob in (left or ()) if ob is not None}
    return [ob for ob in out if ob.name not in leave and ob.data is not None and len(ob.data.vertices)]


def workpieces(scene) -> set:
    """Names of the workpieces (milling's, the CNC machine's): a tool's cutting part may go through them."""
    from . import gcode, machining
    out = set()
    wp = machining.workpiece(scene)
    if wp is not None:
        out.add(wp.name)
    cw = gcode.settings(scene).workpiece
    if cw is not None and cw.name in scene.objects:
        out.add(cw.name)
    return out


def _gauge(spec) -> float:
    from ..core import tools as tcore
    r = tcore.resolved(spec)
    return float(r.gauge) if r.gauge > 0 else float(r.stick_out + r.holder_length)


class Tool:
    """A tool the check knows about, in its object's own space: the zone that cuts (from the tip up to the end of the
    flutes), the zone that follows the cut (the shank, as wide as the cutter, up to the holder) and, for a tool
    copy the app made, the part above its gauge line (inside the spindle or the pocket: never checked)."""

    def __init__(self, tip, axis, tool, stick_out: float = math.inf, gauge: float | None = None):
        self.cut = core.zone(tip, axis, tool.radius, -math.inf, tool.length)
        self.follow = core.zone(tip, axis, tool.radius, -math.inf, max(stick_out, tool.length))
        self.mount = core.zone(tip, axis, math.inf, gauge, math.inf) if gauge else None


def tools_of(scene) -> dict:
    """{object name: Tool} for every bit, the CNC machine's tool and its tool list parts, and the tool copies."""
    from ..core import tools as tcore
    from . import gcode, machining, tools
    out = {}
    for it, ob in machining.bits(scene):
        try:
            tip, axis = machining.on_turning_axis(ob, tuple(it.tip), tuple(it.axis), scene)
            out[ob.name] = Tool(tip, axis, machining.tool_of(it))
        except Exception:  # noqa: BLE001 - a bit without a shape is not a tool
            pass
    for ob in gcode.copies(scene).values():
        if "fr_tip" in ob and "fr_axis" in ob:
            try:
                spec = machining._spec_of_copy(ob)
                stick = tcore.resolved(spec).stick_out if spec is not None else math.inf
                gauge = _gauge(spec) if spec is not None else None
                out[ob.name] = Tool(tuple(ob["fr_tip"]), tuple(ob["fr_axis"]), machining._tool_any(ob), stick, gauge)
            except Exception:  # noqa: BLE001
                pass
    c = gcode.settings(scene)
    parts = [(row, row.obj) for row in c.tools if getattr(row, "obj", None) is not None]
    if c.tool is not None and not any(ob is c.tool for _r, ob in parts):
        parts.append((None, c.tool))
    for row, ob in parts:
        if ob.name in out or ob.name not in scene.objects or ob.type != "MESH":
            continue
        try:
            tip, axis, found = gcode._rest_tip(ob)
            if row is not None:
                spec = tools.spec_of(row)
                out[ob.name] = Tool(tuple(tip), tuple(axis), tcore.cutting_tool(spec), spec.stick_out)
            else:
                out[ob.name] = Tool(tuple(tip), tuple(axis), found)
        except Exception:  # noqa: BLE001
            pass
    return out


def holders(scene) -> set:
    """Names of the parts a tool sits in on purpose: the parts carrying a changer's pockets (a tool stands in its
    pocket). The spindle is found from the motion (the parts that move with the tool in it, see ``Check``)."""
    from . import gcode
    return {p.obj.name for p in gcode.settings(scene).pockets if p.obj is not None}


# ---------------------------------------------------------------------------
# meshes and the narrow phase
# ---------------------------------------------------------------------------

class Mesh:
    """A mesh in its own space with its BVH tree (made when first needed). The tree holds the mesh moved to its own
    centre: Blender's trees work in 32-bit numbers, and parts drawn far from their origin (a few metres) lost the
    tenths of a micrometre a ray needs to step past a face."""

    def __init__(self, verts: np.ndarray, tris: np.ndarray):
        self.v = np.ascontiguousarray(verts, dtype=np.float64)
        self.t = np.ascontiguousarray(tris, dtype=np.int64)
        self.lo = self.v.min(axis=0) if len(self.v) else np.zeros(3)
        self.hi = self.v.max(axis=0) if len(self.v) else np.zeros(3)
        self.c = (self.lo + self.hi) / 2.0
        self.vc = self.v - self.c
        vol = core.signed_volume(self.v - self.c, self.t)
        box = float(np.prod(np.maximum(self.hi - self.lo, 1e-6)))
        self.sign = 1.0
        self.closed = abs(vol) > 1e-4 * box        # a sheet (no volume): no inside, only its surface counts
        self._tree = None
        self._ptree = None
        if self.closed:
            self._orient()

    @property
    def tree(self):
        """The BVH tree of the mesh moved by ``-self.c`` (for finding faces that cut through each other)."""
        if self._tree is None:
            from mathutils.bvhtree import BVHTree
            self._tree = BVHTree.FromPolygons(self.vc.tolist(), self.t.tolist(), all_triangles=True)
        return self._tree

    @property
    def ptree(self):
        """The tree for nearest points and rays: the same surface with long faces cut into short ones."""
        if self._ptree is None:
            from mathutils.bvhtree import BVHTree
            v, t = core.split_long(self.vc, self.t)
            self._ptree = BVHTree.FromPolygons(v.tolist(), t.tolist(), all_triangles=True)
        return self._ptree

    def probe(self, pts: np.ndarray, near: float) -> tuple:
        """(deepest inside, smallest gap outside up to ``near``) of points in this mesh's space."""
        d, gap = self.depths(pts, near)
        return (float(d.max()) if len(d) else 0.0), gap

    def depths(self, pts: np.ndarray, near: float = 0.0) -> tuple:
        """(how deep each point is inside (0: outside or on the surface), smallest gap outside up to ``near``)."""
        out = np.zeros(len(pts))
        if not len(pts) or not len(self.t):
            return out, math.inf
        gap = math.inf
        find = self.ptree.find_nearest
        for k, p in enumerate((pts - self.c).tolist()):
            loc, nor, _i, dist = find(p)
            if loc is None:
                continue
            if self._inside(p, loc, nor, dist):
                out[k] = dist
            elif dist < gap:
                gap = dist
        if near <= 0.0:
            gap = math.inf
        return out, gap

    def _inside(self, p, loc, nor, dist) -> bool:
        if not self.closed or dist <= ON_SURFACE:
            return False
        s = self.sign * ((p[0] - loc[0]) * nor[0] + (p[1] - loc[1]) * nor[1] + (p[2] - loc[2]) * nor[2])
        if s < -0.5 * dist:
            return True                     # straight below a face
        if s < 0.5 * dist:
            return self._inside_by_rays(p)  # beside an edge or a corner: the face says little
        return False

    def _orient(self) -> None:
        """Make every face point outwards. CAD meshes do (a sample of faces says so); a mesh built of several pieces
        can have some turned inwards (found: the app-made tool copies, task 0065), and the inside test reads the
        side a point is on from the face nearest to it."""
        tri = self.vc[self.t]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        ln = np.linalg.norm(n, axis=1)
        good = np.flatnonzero(ln > 1e-14)
        if not len(good):
            return
        mid = tri.mean(axis=1)
        step = 2e-5

        def inward(idx):
            out = np.zeros(len(idx), dtype=bool)
            for k, i in enumerate(idx):
                p = mid[i] + n[i] / ln[i] * step
                out[k] = self._inside_by_rays(p.tolist(), self.tree)
            return out

        sample = good[np.linspace(0, len(good) - 1, min(len(good), 48)).astype(int)]
        flags = inward(sample)
        if not flags.any():
            return                                       # every face outwards (CAD parts)
        if flags.all():
            self.t = self.t[:, ::-1].copy()              # all turned inwards
        elif len(good) <= 50000:
            flip = np.zeros(len(self.t), dtype=bool)
            flip[good] = inward(good)
            self.t[flip] = self.t[flip][:, ::-1]
        else:
            self.sign = 1.0 if flags.mean() < 0.5 else -1.0
            return
        self._tree = self._ptree = None

    def depth_at(self, p) -> float:
        """How deep one point (this mesh's space) is inside (0 outside)."""
        d, _g = self.depths(np.asarray(p, dtype=np.float64)[None])
        return float(d[0])

    def _inside_by_rays(self, p, tree=None) -> bool:
        """Inside when rays from the point cross the surface an odd number of times (two of three rays agree)."""
        votes = 0
        ray = (tree or self.ptree).ray_cast
        for d in RAYS:
            n, start = 0, p
            for _k in range(256):
                loc, _nor, _i, _dist = ray(start, d)
                if loc is None:
                    break
                n += 1
                start = (loc[0] + d[0] * RAY_STEP, loc[1] + d[1] * RAY_STEP, loc[2] + d[2] * RAY_STEP)
            votes += n % 2
        return votes >= 2


RAYS = ((0.5772, 0.5774, 0.5776), (-0.3117, 0.8436, -0.4372), (0.8018, -0.2673, 0.5345))
RAY_STEP = 2e-6                          # m past a face before looking for the next one
ON_SURFACE = 1e-5                        # m: a point closer than this to a surface touches it (not inside)
POLISH = 2                               # the deepest few sampled points are moved to the deepest spot nearby
QUICK = 96                               # corners tried first when one deep point is enough


def _mesh_from(me) -> Mesh:
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    return Mesh(v.reshape(-1, 3), t.reshape(-1, 3))


def _box_of(m: Mesh, rel: np.ndarray) -> tuple:
    c = core.transform(rel, core.corners(m.lo[None], m.hi[None])[0])
    return c.min(axis=0), c.max(axis=0)


def _inside_box(pts: np.ndarray, lo, hi, margin: float) -> np.ndarray:
    return np.all((pts >= lo - margin) & (pts <= hi + margin), axis=1)


TRI_SPACING = 3.0 * core.MM
MAX_TRI_POINTS = 400


def narrow(a: Mesh, b: Mesh, rel: np.ndarray, zones_a=(), zones_b=(), near: float = 0.0, fine: bool = False,
           enough: float = math.inf) -> tuple:
    """How deep meshes ``a`` and ``b`` are in each other, and the gap between them when they do not touch (up to
    ``near``; inf when further or not asked). ``rel`` takes b's space to a's. ``zones_a``/``zones_b``: zones of a tool
    in its own space (``core.zone``) whose points do not count (its cutting part going through a workpiece).

    Both ways round (b's surface in a, a's surface in b): the mesh's corners near the other one and points spread
    over its triangles that cut through the other's surface are tested; the deepest few then slide over their own
    surface to the deepest spot nearby (``_polish``). The result is never deeper than the truth (the deepest point
    found); ``fine`` looks much closer (for the overlap two parts start with, worked out once per pair: a start
    overlap found too small would make every later moment look deeper than it is). ``enough``: stop as soon as the
    corners alone show the parts deeper than this (a clash is sure; the deepest moment is measured again later)."""
    spacing, most, starts, split, apart = ((TRI_SPACING / 3.0, MAX_TRI_POINTS * 20, POLISH * 4, 48, 5e-3) if fine
                                           else (TRI_SPACING, MAX_TRI_POINTS, POLISH, 8, 2e-3))
    margin = max(near, 1e-6)
    blo, bhi = _box_of(b, rel)
    if not core.boxes_overlap(a.lo, a.hi, blo, bhi, margin):
        return 0.0, math.inf
    inv = np.linalg.inv(rel)
    deep, gap = 0.0, math.inf

    def keep(pts_a_space, pts_b_space):
        ok = np.ones(len(pts_a_space), dtype=bool)
        if zones_a:
            ok &= ~core.in_zone(pts_a_space, zones_a)
        if zones_b:
            ok &= ~core.in_zone(pts_b_space, zones_b)
        return ok

    vb = core.transform(rel, b.v)                            # b's corners in a's space
    va = core.transform(inv, a.v)                            # a's corners in b's space
    if math.isfinite(enough):
        # a few corners first: two parts deep in each other show it at once
        for me, other, corners_o, to_me in ((b, a, vb, inv), (a, b, va, rel)):
            sel = np.flatnonzero(_inside_box(corners_o, other.lo, other.hi, margin))
            if len(sel) > QUICK:
                sel = sel[np.linspace(0, len(sel) - 1, QUICK).astype(int)]
                pts = corners_o[sel]
                in_me = core.transform(to_me, pts)
                ok = keep(pts, in_me) if other is a else keep(in_me, pts)
                d, _g = other.depths(pts[ok], 0.0)
                if len(d) and d.max() > enough:
                    return float(d.max()), 0.0
    # triangles that cut through the other's surface
    ta = tb = np.zeros((0, 3, 3))
    if len(a.t) and len(b.t):
        tri = vb[b.t]                                        # b's triangles in a's space
        tsel = np.all(tri.max(axis=1) >= a.lo - margin, axis=1) & np.all(tri.min(axis=1) <= a.hi + margin, axis=1)
        if np.any(tsel):
            from mathutils.bvhtree import BVHTree
            idx = np.flatnonzero(tsel)
            used, local = np.unique(b.t[idx], return_inverse=True)
            tree_b = BVHTree.FromPolygons((vb[used] - a.c).tolist(), local.reshape(-1, 3).tolist(),
                                          all_triangles=True)
            pairs = a.tree.overlap(tree_b)
            if pairs:
                pa = np.array(pairs, dtype=np.int64)
                pa = pa[~_flat_contact(a.v[a.t[pa[:, 0]]], vb[b.t[idx[pa[:, 1]]]])]
            if pairs and len(pa):
                ta = va[a.t[np.unique(pa[:, 0])]]                          # a's triangles, b's space
                tb = vb[b.t[idx[np.unique(pa[:, 1])]]]                     # b's triangles, a's space
    sides = ((b, a, vb, tb, inv, rel), (a, b, va, ta, rel, inv))
    found = {}
    for me, other, corners_o, _tris, to_me, _from in sides:
        # ``me``'s corners in ``other``'s space
        sel = _inside_box(corners_o, other.lo, other.hi, margin)
        pts = corners_o[sel]
        if not len(pts):
            continue
        in_me = core.transform(to_me, pts)
        ok = keep(pts, in_me) if other is a else keep(in_me, pts)
        pts = pts[ok]
        d, g = other.depths(pts, near)
        gap = min(gap, g)
        found[id(me)] = (pts, d)
        if len(d):
            deep = max(deep, float(d.max()))
    if deep > enough:
        return deep, 0.0
    for me, other, _corners, tris_o, to_me, from_me in sides:
        pts, d = found.get(id(me), (np.zeros((0, 3)), np.zeros(0)))
        if len(tris_o):
            # points spread over ``me``'s triangles that cut through ``other``'s surface
            tp, _w = core.triangle_points(tris_o, spacing, split)
            tp = core.thin_out(tp, most)
            in_me = core.transform(to_me, tp)
            ok = keep(tp, in_me) if other is a else keep(in_me, tp)
            tp = tp[ok]
            dt, _g = other.depths(tp, 0.0)
            pts, d = np.concatenate([pts, tp]), np.concatenate([d, dt])
        if not len(d) or d.max() <= 0.0:
            continue
        deep = max(deep, float(d.max()))

        def allowed(q, other=other, to_me=to_me):
            q = q[None]
            qm = core.transform(to_me, q)
            return bool(keep(q, qm)[0] if other is a else keep(qm, q)[0])

        surface = _surface_of(me, to_me, from_me)
        done: list = []
        for k in np.argsort(d)[::-1]:
            if d[k] <= 0.0 or len(done) >= starts:
                break
            if any(float(np.linalg.norm(pts[k] - q)) < apart for q in done):
                continue                                     # starts spread out: one per spot
            done.append(pts[k])
            deep = max(deep, _polish(other, pts[k], float(d[k]), surface, allowed))
    if deep > 0.0:
        gap = 0.0
    return deep, gap


def _flat_contact(ta: np.ndarray, tb: np.ndarray, tol: float = ON_SURFACE) -> np.ndarray:
    """Which pairs of triangles (both (K, 3, 3), same space) lie in one plane: faces resting on each other touch
    there, they cannot be inside each other (and checking them costs a lot: whole faces of two plates)."""
    na = np.cross(ta[:, 1] - ta[:, 0], ta[:, 2] - ta[:, 0])
    nb = np.cross(tb[:, 1] - tb[:, 0], tb[:, 2] - tb[:, 0])
    la, lb = np.linalg.norm(na, axis=1), np.linalg.norm(nb, axis=1)
    ok = (la > 1e-18) & (lb > 1e-18)
    na = na / np.where(la > 0, la, 1.0)[:, None]
    nb = nb / np.where(lb > 0, lb, 1.0)[:, None]
    parallel = np.linalg.norm(np.cross(na, nb), axis=1) < 1e-4
    dist = np.abs(np.einsum("ij,ikj->ik", na, tb - ta[:, :1, :])).max(axis=1)
    return ok & parallel & (dist < tol)


def _polish(mesh: Mesh, p: np.ndarray, d: float, surface, allowed=None, steps: int = 16) -> float:
    """Slide a point of one part's surface that is ``d`` deep inside ``mesh`` (both in mesh's space) over that surface
    to where it is deepest: a sampled point lands near the deepest spot, not on it (long faces get few samples).
    ``surface(q) -> (point, normal)``: the nearest point of the sliding part's own surface. Returns the depth found."""
    step = max(TRI_SPACING, d)
    best, best_d = p, d
    _q, n = surface(best)
    for _k in range(steps):
        loc, _nor, _i, _dist = mesh.ptree.find_nearest((best - mesh.c).tolist())
        if loc is None:
            break
        away = (best - mesh.c) - np.array(loc)            # from the nearest surface into the mesh
        away -= (away @ n) * n                             # along the sliding part's surface
        la = float(np.linalg.norm(away))
        if la < 1e-12:
            break
        trial, tn = surface(best + away / la * step)
        dt = mesh.depth_at(trial) if allowed is None or allowed(trial) else 0.0
        if dt > best_d + 1e-9:
            best, best_d, n = trial, dt, tn
        else:
            step *= 0.5
            if step < 1e-4:
                break
    return best_d


def _surface_of(m: Mesh, to_m: np.ndarray, from_m: np.ndarray):
    """``surface(q)`` for ``_polish``: q in another space; ``to_m`` takes it into m's space, ``from_m`` back."""
    rot = from_m[:3, :3]

    def surface(q):
        qm = to_m[:3, :3] @ q + to_m[:3, 3]
        loc, nor, _i, _dist = m.ptree.find_nearest((qm - m.c).tolist())
        if loc is None:
            return q, np.array([0.0, 0.0, 1.0])
        pt = np.array(loc) + m.c
        nv = rot @ np.array(nor)
        return rot @ pt + from_m[:3, 3], nv / max(float(np.linalg.norm(nv)), 1e-12)
    return surface


# ---------------------------------------------------------------------------
# reading the animation
# ---------------------------------------------------------------------------

class _Guard:
    """Milling and coolant redraw on every frame change; reading the motion does not need that."""

    def __enter__(self):
        from . import coolant, machining
        machining._STATE["guard"] += 1
        coolant._STATE["guard"] += 1
        return self

    def __exit__(self, *exc):
        from . import coolant, machining
        machining._STATE["guard"] -= 1
        coolant._STATE["guard"] -= 1
        return False


def sample_times(scene) -> list:
    """Every frame of the animation and the corners of a G-code program between frames."""
    from . import gcode
    f0, f1 = int(scene.frame_start), int(max(scene.frame_start, scene.frame_end))
    times = {float(f) for f in range(f0, f1 + 1)}
    times |= {round(t, 6) for t in gcode.corners(scene) if f0 < t < f1}
    return sorted(times)


def _set_time(scene, t: float) -> None:
    f = math.floor(t + 1e-9)
    scene.frame_set(int(f), subframe=float(t - f))


# ---------------------------------------------------------------------------
# the check
# ---------------------------------------------------------------------------

class Check:
    """One run of the check. ``steps()`` yields the share done (0 … 1); ``rows`` and ``stats`` at the end."""

    def __init__(self, scene, depth: float | None = None, near: float | None = None):
        c = settings(scene)
        self.scene = scene
        self.depth = float(c.depth if depth is None else depth)
        self.near = float((c.near_distance if c.use_near else 0.0) if near is None else near)
        self.rows: list = []
        self.stats: dict = {}

    # -- set-up ---------------------------------------------------------------
    def _setup(self):
        from . import machining
        scene = self.scene
        if not is_built(scene):
            raise ClashError("Build the animation first (Build & play above)")
        self.objs = objects(scene)
        if len(self.objs) < 2:
            raise ClashError("There are not two parts to compare")
        self.tools = tools_of(scene)
        self.wps = workpieces(scene)
        self.holders = holders(scene)
        self.mill = machining.workpiece(scene) if machining.is_active(scene) else None
        if self.mill is not None:
            machining.update_if_needed(scene)
        self.timeline = machining._timeline(scene) if self.mill is not None else None
        self.meshes: dict = {}
        self.mesh_key = []
        mill_s = machining.settings(scene)
        for ob in self.objs:
            me = ob.data
            if self.mill is not None and ob is self.mill and mill_s.stock_mesh is not None:
                me = mill_s.stock_mesh
            if me.name not in self.meshes:
                self.meshes[me.name] = _mesh_from(me)
            self.mesh_key.append(me.name)
        self.lo = np.array([self.meshes[k].lo for k in self.mesh_key])
        self.hi = np.array([self.meshes[k].hi for k in self.mesh_key])
        self.names = [ob.name for ob in self.objs]
        self.labels = [label(ob) for ob in self.objs]
        self.times = sample_times(scene)

    def _read(self):
        """Every part's world matrix and visibility at every moment (yields progress 0 … 0.4)."""
        scene = self.scene
        all_obs = scene.objects
        index = {ob.name: i for i, ob in enumerate(all_obs)}
        sel = np.array([index[n] for n in self.names])
        n_all = len(all_obs)
        buf = np.empty(n_all * 16, dtype=np.float64)
        hb = np.empty(n_all, dtype=bool)
        T = len(self.times)
        self.mats = np.empty((T, len(sel), 4, 4))
        self.vis = np.empty((T, len(sel)), dtype=bool)
        keep = (scene.frame_current, scene.frame_subframe)
        try:
            with _Guard():
                for k, t in enumerate(self.times):
                    _set_time(scene, t)
                    all_obs.foreach_get("matrix_world", buf)
                    all_obs.foreach_get("hide_render", hb)
                    self.mats[k] = buf.reshape(n_all, 4, 4)[sel].transpose(0, 2, 1)    # stored by columns
                    self.vis[k] = ~hb[sel]
                    if k % 10 == 0:
                        yield 0.4 * k / T
        finally:
            scene.frame_set(keep[0], subframe=keep[1])

    # -- the pairs -------------------------------------------------------------
    def _mesh_at(self, p: int, t: float) -> Mesh:
        if self.timeline is not None and self.objs[p] is self.mill:
            cache = self.wp_cache
            hit = cache.get(t)
            if hit is None:
                try:
                    v, tri, _src = self.timeline.mesh_at(float(t))
                    hit = Mesh(np.asarray(v, dtype=np.float64), np.asarray(tri, dtype=np.int64))
                except Exception:  # noqa: BLE001 - fall back to the uncut block
                    hit = self.meshes[self.mesh_key[p]]
                if len(cache) > 6:
                    cache.pop(next(iter(cache)))
                cache[t] = hit
            return hit
        return self.meshes[self.mesh_key[p]]

    def _zones(self, p: int, q: int) -> tuple:
        """The zones of p (its space) and of q (its space) whose points do not count against the other."""
        out = []
        for me, other in ((p, q), (q, p)):
            tool = self.tools.get(self.names[me])
            z = []
            if tool is not None:
                if tool.mount is not None:
                    z.append(tool.mount)
                if self.names[other] in self.wps:
                    # with milling on the workpiece is cut as it goes: only the flutes may be in it; without, the
                    # shank follows the hole the flutes made
                    z.append(tool.cut if self.timeline is not None and self.objs[other] is self.mill
                             else tool.follow)
            out.append(tuple(z))
        return out[0], out[1]

    def _pair(self, p: int, q: int, mp: np.ndarray, mq: np.ndarray, t: float, rel=None, fine: bool = False,
              enough: float = math.inf) -> tuple:
        """(depth, gap) of parts p, q with world matrices mp, mq at moment t."""
        rel = np.linalg.inv(mp) @ mq if rel is None else rel
        timed = self.timeline is not None and (self.objs[p] is self.mill or self.objs[q] is self.mill)
        key = (p, q, np.round(rel, 7).tobytes(), t if timed else None, fine, enough)
        hit = self.memo.get(key)
        if hit is not None:
            return hit
        za, zb = self._zones(p, q)
        hit = narrow(self._mesh_at(p, t), self._mesh_at(q, t), rel, za, zb, self.near, fine, enough)
        self.memo[key] = hit
        self.narrow_calls += 1
        return hit

    def _start(self, p: int, q: int) -> tuple:
        hit = self.base.get((p, q))
        if hit is None:
            # both readings are never deeper than the truth: the start overlap is the deeper of the two
            mp, mq, t = self.mats[0, p], self.mats[0, q], self.times[0]
            d1, g1 = self._pair(p, q, mp, mq, t)
            if d1 > 0.0:                         # they overlap at the start: how much matters, look closely
                d2, g2 = self._pair(p, q, mp, mq, t, fine=True)
                hit = (max(d1, d2), min(g1, g2))
            else:
                hit = (d1, g1)
            self.base[(p, q)] = hit
        return hit

    def _candidates(self, lo, hi, vis, gpairs) -> list:
        """Part pairs (p < q) of the group pairs ``gpairs`` whose boxes ``lo``/``hi`` (P, 3) meet, both shown."""
        margin = max(self.near, 1e-6)
        out = []
        for ga, gb in gpairs:
            ia = self.members[ga][vis[self.members[ga]]]
            ib = self.members[gb][vis[self.members[gb]]]
            if not len(ia) or not len(ib):
                continue
            # parts of a near b's box, of b near a's box
            blo, bhi = lo[ib].min(axis=0), hi[ib].max(axis=0)
            ia = ia[np.all((lo[ia] <= bhi + margin) & (hi[ia] >= blo - margin), axis=1)]
            if not len(ia):
                continue
            alo, ahi = lo[ia].min(axis=0), hi[ia].max(axis=0)
            ib = ib[np.all((lo[ib] <= ahi + margin) & (hi[ib] >= alo - margin), axis=1)]
            if not len(ib):
                continue
            for i, j in core.box_pairs(lo[ia], hi[ia], lo[ib], hi[ib], margin):
                p, q = int(ia[i]), int(ib[j])
                if p > q:
                    p, q = q, p
                if (p, q) not in self.skip:
                    out.append((p, q))
        return out

    def _moment(self, t: float, mats: np.ndarray, vis: np.ndarray, gpairs) -> None:
        """Check the group pairs ``gpairs`` at one moment (matrices ``mats`` (P, 4, 4), visibility ``vis``)."""
        lo, hi = core.world_boxes(mats, self.lo, self.hi)
        pairs = self._candidates(lo, hi, vis, gpairs)
        if pairs:
            pq = np.array(pairs, dtype=np.int64)
            self._check_pairs(pq[:, 0], pq[:, 1], mats[pq[:, 0]], mats[pq[:, 1]], t)

    def _check_pairs(self, P: np.ndarray, Q: np.ndarray, MP: np.ndarray, MQ: np.ndarray, t: float) -> None:
        """Check part pairs (P[i], Q[i]) with world matrices MP[i], MQ[i] at moment t. What is known from the last time
        a pair was worked out decides first, for all pairs at once: a pair that has not moved enough against the
        other since cannot have gone in deeper than allowed; one that was far deeper is surely still in."""
        rel = np.linalg.inv(MP) @ MQ
        start = [self._start(int(p), int(q)) for p, q in zip(P, Q)]
        d0 = np.array([x[0] for x in start])
        g0 = np.array([x[1] for x in start])
        allowed = np.maximum(d0, 0.0) * (1.0 + core.SLACK) + self.depth
        last = [self.last.get((int(p), int(q))) for p, q in zip(P, Q)]
        have = np.array([x is not None for x in last], dtype=bool)
        todo = np.ones(len(P), dtype=bool)
        if np.any(have):
            hi_ = np.flatnonzero(have)
            d_l = np.array([last[i][0] for i in hi_])
            g_l = np.array([last[i][1] for i in hi_])
            rel_l = np.stack([last[i][2] for i in hi_])
            moved = core.motion_many(rel_l, rel[hi_], self.lo[Q[hi_]], self.hi[Q[hi_]])
            may_near = (self.near > 0) & (g0[hi_] >= self.near) & (np.minimum(g_l, self.near) - moved < self.near)
            cannot = (d_l + moved <= allowed[hi_]) & ~may_near
            sure = (d_l - moved > allowed[hi_]) & (self.near <= 0)
            todo[hi_[cannot | sure]] = False
            self.pruned += int(np.count_nonzero(cannot | sure))
            for k in np.flatnonzero(sure):
                i = int(hi_[k])
                p, q = int(P[i]), int(Q[i])
                d = float(d_l[k] - moved[k])                 # at least this deep (a lower bound)
                self.hits.setdefault((p, q), []).append(core.Hit(t, d, core.excess(d, d0[i])))
                self.rels[(p, q, t)] = rel[i]
        for i in np.flatnonzero(todo):
            p, q = int(P[i]), int(Q[i])
            d, g = self._pair(p, q, MP[i], MQ[i], t, rel[i], enough=float(allowed[i]) if self.near <= 0 else math.inf)
            self.last[(p, q)] = (d, g, rel[i])
            if d <= 0.0 and g == math.inf:
                continue
            if d > allowed[i]:
                self.hits.setdefault((p, q), []).append(core.Hit(t, d, core.excess(d, d0[i])))
                self.rels[(p, q, t)] = rel[i]
            elif self.near > 0 and core.is_near(g, g0[i], self.near):
                self.near_hits.setdefault((p, q), []).append(core.Hit(t, g, 0.0))

    def _between(self, k: int, pairs: list, dmat: np.ndarray, groups: np.ndarray) -> int:
        """Extra moments between moment k and k+1 for the part pairs that move more than ``STEP`` against each other
        (each body follows its screw motion between the two moments). Returns how many moments were added."""
        if not pairs:
            return 0
        pq = np.array(pairs, dtype=np.int64)
        P, Q = pq[:, 0], pq[:, 1]
        mk, mk1 = self.mats[k], self.mats[k + 1]
        rel0 = np.linalg.inv(mk[P]) @ mk[Q]
        rel1 = np.linalg.inv(mk1[P]) @ mk1[Q]
        n = np.ceil(core.motion_many(rel0, rel1, self.lo[Q], self.hi[Q]) / core.STEP).astype(int) - 1
        n = np.minimum(n, core.MAX_SUB)
        tk = self.times[k]
        for i in np.flatnonzero(n > 0):                  # already in each other at moment k: nothing can slip past
            h = self.hits.get((int(P[i]), int(Q[i])))
            if h and h[-1].t == tk:
                n[i] = 0
        added = 0
        t0, t1 = self.times[k], self.times[k + 1]
        for nn in sorted(set(int(x) for x in n if x > 0)):
            sel = np.flatnonzero(n == nn)
            Ps, Qs = P[sel], Q[sel]
            gs = sorted({int(groups[x]) for x in np.concatenate([Ps, Qs])})
            for s_ in range(1, nn + 1):
                if not len(Ps):
                    break
                f = s_ / (nn + 1)
                t = t0 + (t1 - t0) * f
                dm = {g: core.screw_between(dmat[k, g], dmat[k + 1, g], f) for g in gs}
                DP = np.stack([dm[int(groups[x])] for x in Ps])
                DQ = np.stack([dm[int(groups[x])] for x in Qs])
                self._check_pairs(Ps, Qs, DP @ self.mats[0, Ps], DQ @ self.mats[0, Qs], t)
                added += 1
                # a pair found in each other between the frames cannot slip past any more: the next frame tells the
                # rest
                found = np.array([bool(self.hits.get((int(p), int(q)))) and self.hits[(int(p), int(q))][-1].t == t
                                  for p, q in zip(Ps, Qs)], dtype=bool)
                Ps, Qs = Ps[~found], Qs[~found]
        return added

    def _mounted(self, groups) -> set:
        """Pairs that touch on purpose: a tool and the spindle it sits in (the parts that move with a tool that is
        in the spindle at the start), a tool and a part carrying a changer's pockets."""
        from . import gcode, machining
        idx = {n: i for i, n in enumerate(self.names)}
        tools = {idx[n] for n in self.tools if n in idx}
        # the head: the assembly the spindle's own tool (or a milling bit) sits in, in the CAD tree
        spindle = [ob for _it, ob in machining.bits(self.scene)] + [gcode.settings(self.scene).tool]
        heads = {build.parent_assembly(ob).name for ob in spindle
                 if ob is not None and build.parent_assembly(ob) is not None}
        head = set()
        if heads:
            for i, ob in enumerate(self.objs):
                p = build.logical_parent(ob)
                while p is not None:
                    if p.name in heads:
                        head.add(i)
                        break
                    p = build.logical_parent(p)
        del groups
        head -= tools
        hold = {idx[n] for n in self.holders if n in idx}
        out = set()
        for t in tools:
            for o in head | hold:
                if o != t:
                    out.add((min(t, o), max(t, o)))
        return out

    def _deepest(self, p: int, q: int, row) -> None:
        """Measure the deepest moments of a row again in full (during the run a clash stops at its first sure sign)."""
        za, zb = self._zones(p, q)
        hs = sorted(row.hits, key=lambda h: h.t)
        # the deepest found, and moments spread over the row (some depths are lower bounds: see _check_pairs)
        pick = {id(h): h for h in sorted(hs, key=lambda h: -h.depth)[:3]}
        for i in np.linspace(0, len(hs) - 1, min(len(hs), 6)).astype(int):
            pick[id(hs[i])] = hs[i]
        for h in pick.values():
            rel = self.rels.get((p, q, h.t))
            if rel is None:
                continue
            d, _g = narrow(self._mesh_at(p, h.t), self._mesh_at(q, h.t), rel, za, zb)
            if d > row.depth:
                row.depth, row.t_deep = d, h.t

    def steps(self):
        t_start = time.perf_counter()
        self._setup()
        yield 0.01
        t0 = time.perf_counter()
        yield from self._read()
        t_read = time.perf_counter() - t0
        T, P = self.mats.shape[:2]
        d = core.deltas(self.mats)
        groups = core.rigid_groups(d)
        G = int(groups.max()) + 1 if P else 0
        self.members = [np.flatnonzero(groups == g) for g in range(G)]
        self.memo, self.base, self.hits, self.near_hits, self.last, self.rels = {}, {}, {}, {}, {}, {}
        self.wp_cache = {}
        self.narrow_calls = self.pruned = 0
        self.skip = self._mounted(groups)
        self.groups = groups
        # each group's box at the start (world) and its motion D(t) (from its first part)
        rep = [int(m[0]) for m in self.members]
        w_lo, w_hi = [], []
        for g in range(G):
            l_, h_ = core.world_boxes(self.mats[0, self.members[g]], self.lo[self.members[g]],
                                      self.hi[self.members[g]])
            w_lo.append(l_.min(axis=0))
            w_hi.append(h_.max(axis=0))
        w_lo, w_hi = np.array(w_lo).reshape(-1, 3), np.array(w_hi).reshape(-1, 3)
        margin = max(self.near, 1e-6)
        m0inv = np.linalg.inv(self.mats[0])
        dmat = np.einsum("tpij,pjk->tpik", self.mats[:, rep], m0inv[rep]) if G else np.zeros((T, 0, 4, 4))
        subs = 0
        t1 = time.perf_counter()
        for k in range(T):
            t = self.times[k]
            # group boxes now (from the start box moved by the group's motion)
            glo, ghi = core.world_boxes(dmat[k], w_lo, w_hi)
            gp = [(int(a), int(b)) for a, b in core.box_pairs(glo, ghi, glo, ghi, margin) if a < b]
            if gp:
                self._moment(t, self.mats[k], self.vis[k], gp)
            # between this moment and the next: extra moments for the part pairs that move far against each other
            if k + 1 < T:
                glo1, ghi1 = core.world_boxes(dmat[k + 1], w_lo, w_hi)
                slo, shi = np.minimum(glo, glo1), np.maximum(ghi, ghi1)
                swept = [(int(a), int(b)) for a, b in core.box_pairs(slo, shi, slo, shi, margin) if a < b]
                if swept:
                    lo0, hi0 = core.world_boxes(self.mats[k], self.lo, self.hi)
                    lo1, hi1 = core.world_boxes(self.mats[k + 1], self.lo, self.hi)
                    pairs = self._candidates(np.minimum(lo0, lo1), np.maximum(hi0, hi1), self.vis[k], swept)
                    subs += self._between(k, pairs, dmat, groups)
            if k % 5 == 0:
                yield 0.4 + 0.6 * k / T
        rows = []
        for kind, found in (("CLASH", self.hits), ("NEAR", self.near_hits)):
            for (p, q), hs in found.items():
                if kind == "NEAR" and (p, q) in self.hits:
                    continue
                for r in core.merge(hs, kind, self.labels[p], self.labels[q]):
                    r.names = (self.names[p], self.names[q])
                    if kind == "CLASH":
                        self._deepest(p, q, r)
                    rows.append(r)
        self.rows = core.sort_rows(rows)
        self.stats = {"seconds": time.perf_counter() - t_start, "read_s": t_read,
                      "check_s": time.perf_counter() - t1, "moments": T, "between": subs, "parts": P,
                      "bodies": G, "pairs": len(self.base), "narrow": self.narrow_calls, "pruned": self.pruned}
        yield 1.0


def check(scene, store: bool = True, **kw) -> Check:
    """Run the whole check at once (scripts, tests, the PC check). Stores the result unless ``store`` is False."""
    run = Check(scene, **kw)
    for _p in run.steps():
        pass
    if store:
        save(scene, run)
    return run


# ---------------------------------------------------------------------------
# the result in the project
# ---------------------------------------------------------------------------

def clear_markers(scene) -> int:
    gone = [m for m in scene.timeline_markers if m.name.startswith(MARK)]
    for m in gone:
        scene.timeline_markers.remove(m)
    return len(gone)


def save(scene, run: Check) -> None:
    c = settings(scene)
    c.rows.clear()
    clash_rows = [r for r in run.rows if r.kind == "CLASH"]
    for r in run.rows[:core.MAX_ROWS]:
        it = c.rows.add()
        it.kind = r.kind
        it.part_a, it.part_b = r.names
        it.label_a, it.label_b = r.a, r.b
        it.frame_from, it.frame_to = r.frame_from, r.frame_to
        it.deep = r.t_deep
        it.depth = r.depth
    c.clashes = len(clash_rows)
    c.near_misses = len(run.rows) - len(clash_rows)
    c.anim = scene.fresing.anim_baked
    c.signature = build_signature(scene)
    c.seconds = float(run.stats.get("seconds", 0.0))
    c.moments = int(run.stats.get("moments", 0)) + int(run.stats.get("between", 0))
    c.checked = True
    runtime(scene)["watch"] = _cheap_key(scene)
    c["_quiet"] = True
    try:
        c.rows_index = -1
    finally:
        del c["_quiet"]
    clear_markers(scene)
    seen = set()
    for r in clash_rows:
        f = max(int(scene.frame_start), r.frame_from)
        key = (f, r.a, r.b)
        if key in seen:
            continue
        seen.add(key)
        scene.timeline_markers.new(f"{MARK}{r.a} × {r.b}", frame=f)
    hide_red()


def clear(scene) -> None:
    """Forget the result: rows, markers, red parts."""
    c = settings(scene)
    c.rows.clear()
    c.checked = False
    c.clashes = c.near_misses = 0
    c.signature = ""
    clear_markers(scene)
    hide_red()


def drop_if_stale(scene) -> bool:
    """Clear a result that belongs to an earlier build. True when cleared."""
    c = settings(scene)
    if not c.checked:
        return False
    if is_built(scene) and c.signature == build_signature(scene):
        return False
    clear(scene)
    return True


# ---------------------------------------------------------------------------
# showing a row: frame, selection, red, framing
# ---------------------------------------------------------------------------

def show_row(context, scene, index: int) -> str:
    """Go to the row's deepest moment, select both parts, show them red, frame them in the 3D views. Returns a
    message ('' when fine)."""
    c = settings(scene)
    if not 0 <= index < len(c.rows):
        return ""
    r = c.rows[index]
    _set_time(scene, r.deep)
    obs = [bpy.data.objects.get(n) for n in (r.part_a, r.part_b)]
    obs = [ob for ob in obs if ob is not None and ob.name in scene.objects]
    if len(obs) < 2:
        return "One of the two parts is gone: check again"
    vl = context.view_layer if context is not None and context.view_layer else scene.view_layers[0]
    for ob in list(vl.objects.selected):
        try:
            ob.select_set(False, view_layer=vl)
        except RuntimeError:
            pass
    for ob in obs:
        try:
            ob.select_set(True, view_layer=vl)
        except RuntimeError:
            pass
    from . import handlers
    handlers.ignore_next(obs[0])             # just these two parts, not their subassembly
    vl.objects.active = obs[0]
    show_red(scene, [ob.name for ob in obs])
    _frame_selected(context)
    return ""


def _frame_selected(context) -> None:
    if context is None or getattr(context, "window_manager", None) is None:
        return
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            try:
                with context.temp_override(window=win, area=area, region=region):
                    bpy.ops.view3d.view_selected(use_all_regions=False)
            except Exception:  # noqa: BLE001 - framing is a help, never a reason to fail
                pass


def red_names(scene=None) -> list:
    return list(_DRAW.get("names") or [])


def show_red(scene, names: list) -> None:
    """Draw these parts red on top of the 3D view (an overlay: their materials stay as they are)."""
    _DRAW["names"] = list(names)
    _DRAW["batches"] = {}
    if _DRAW["handle"] is None:
        try:
            _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
        except Exception:  # noqa: BLE001
            _DRAW["handle"] = None
    _redraw()


def hide_red() -> None:
    _DRAW["names"] = []
    _DRAW["batches"] = {}
    if _DRAW["handle"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        except Exception:  # noqa: BLE001
            pass
        _DRAW["handle"] = None
    _redraw()


def _redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _batch(ob):
    import gpu
    from gpu_extras.batch import batch_for_shader
    me = ob.data
    key = (ob.name, me.name, len(me.vertices))
    hit = _DRAW["batches"].get(key)
    if hit is None:
        m = _mesh_from(me)
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        hit = (shader, batch_for_shader(shader, "TRIS", {"pos": m.v.astype(np.float32)},
                                        indices=m.t.astype(np.int32)))
        _DRAW["batches"][key] = hit
    return hit


def _draw() -> None:
    names = _DRAW.get("names")
    if not names:
        return
    try:
        import gpu
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")          # seen through other parts: the clash is often inside
        for n in names:
            ob = bpy.data.objects.get(n)
            if ob is None or ob.type != "MESH" or ob.hide_get():
                continue
            shader, batch = _batch(ob)
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(ob.matrix_world)
            shader.uniform_float("color", RED)
            batch.draw(shader)
            gpu.matrix.pop()
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
    except Exception:  # noqa: BLE001 - drawing must never break the view
        pass


# ---------------------------------------------------------------------------
# handlers: a new Build clears the result
# ---------------------------------------------------------------------------

def _stale_timer():
    try:
        for sc in bpy.data.scenes:
            if hasattr(sc, "fresing") and sc.fresing.clash.checked:
                runtime(sc).pop("sig_key", None)
                if drop_if_stale(sc):
                    _redraw()
    except Exception:  # noqa: BLE001
        pass
    return None


@persistent
def _on_depsgraph(scene, depsgraph=None):
    """A Build makes new actions: when the built keys may have changed, a timer compares the fingerprint (it may not
    write data here)."""
    if depsgraph is None or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        if not scene.fresing.clash.checked:
            return
        rt = runtime(scene)
        key = _cheap_key(scene)
        if rt.get("watch") == key:
            return
        rt["watch"] = key
        if not bpy.app.timers.is_registered(_stale_timer):
            bpy.app.timers.register(_stale_timer, first_interval=0.3)
    except Exception:  # noqa: BLE001
        pass


@persistent
def _on_load(_dummy=None):
    _RUNTIME.clear()
    hide_red()
    try:
        for sc in bpy.data.scenes:
            if hasattr(sc, "fresing") and sc.fresing.clash.checked:
                runtime(sc)["watch"] = _cheap_key(sc)
    except Exception:  # noqa: BLE001
        pass


def register():
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_load)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph), (bpy.app.handlers.load_post, _on_load)):
        while fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_stale_timer):
        bpy.app.timers.unregister(_stale_timer)
    hide_red()
    _RUNTIME.clear()
