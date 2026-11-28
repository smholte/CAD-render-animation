"""Clearances, reach envelope, exclusion zone, ground footprint and the plan sheet (task 0349, Lifting lane L6b):
8 Lifting plan > Clearance & zones. The numbers are ``core/lifting_zones``'s; this module reads the project.

* **Clearance**: what moves in the lift – the crane's parts that turn with its slew, the hook block, the load and its
  rigging – against every other part shown (other models, other cranes as they stand, props, a hall's walls; not the
  ground, the floor or the sea). Each part's triangles once, in its joint's frame at zero (``Body``); at any joint
  values the joint's motion (the crane's file, the rig) puts them in place – no frame is set. The row ``CLR`` joins
  the checks (live and along the path); what the load stands on at the pick and the set-down does not count for it.
* **Reach rings, exclusion zone, ground footprint**: drawn on the ground in the 3D view where the Lifting plan shows
  (POST_VIEW), never in a camera's picture; worked out at most ``lifting_path.LIVE_EVERY`` apart, only on a change.
* **Plan sheet…**: one page (HTML, A4 landscape) next to the project's outputs with the plan view, the range diagram
  and the checks table – opened in the browser to print.
"""

from __future__ import annotations

import datetime
import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from ..core import lifting as core
from ..core import lifting_path as P
from ..core import lifting_zones as Z
from . import build, joints, lifting

GROUND_ROLES = {"floor", "sea", "seabed", "stones", "soil", "spray", "hull_foam", "sea_cut", "photo_dome",
                "photo_ground", "root", "lights", "sky"}
ENV_TAG = "fr_env"                     # surroundings.TAG
RIGGING_TAG = "fr_rigging"             # lifting_rig.TAG
LIFT_GAP = 0.02                        # m: the drawings lie this far above the ground


def changed(scene) -> None:
    """A setting of the panel changed: the cached clearance and drawing go, the views are drawn again."""
    forget()
    from . import lifting_path
    lifting_path.forget()
    _redraw()


def forget() -> None:
    _CLEAR.clear()
    _VIEW.update(key=None, data=None, at=0.0)
    _LIVE_CLR.update(key=None, row=None, row_key=None)


def _redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------------------------------
# what moves and what stands

def carrier_joint(scene, ob):
    """The app joint that moves ``ob`` (directly or through its sub-assemblies), or None."""
    p = ob.parent
    while p is not None:
        if p.get(build.PROP_KIND) == "joint":
            for j in scene.fresing.joints:
                if j.motion is p:
                    return j
        p = p.parent
    return None


def _scale() -> np.ndarray:
    S = np.eye(4)
    S[0, 0] = S[1, 1] = S[2, 2] = 0.001
    return S


def motion_of(crane, rig):
    """``motion(joint, values)``: the joint's frame now against its frame at zero, in the world (m): the rig's motion
    (model frame, mm) carried to the world by the crane's root."""
    R = np.array(crane.root.matrix_world)
    S = _scale()
    A = R @ S
    Ai = np.linalg.inv(A)

    def motion(joint, values):
        return A @ rig.motion(joint, values) @ Ai
    return motion


def _visible(ob) -> bool:
    try:
        return ob.visible_get()
    except Exception:  # noqa: BLE001
        return not ob.hide_viewport


def _arrays(ob):
    from . import clash
    return clash._mesh_arrays(ob.data)


def _world(ob, v):
    M = np.array(ob.matrix_world)
    return v.astype(np.float64) @ M[:3, :3].T + M[:3, 3]


_POINTS: dict = {}


def _points(key, verts, tris):
    got = _POINTS.get(key)
    if got is None:
        if len(_POINTS) > 4000:
            _POINTS.clear()
        got = Z.sample(verts, tris)
        _POINTS[key] = got
    return got


class BVHObstacles:
    """The obstacles as one Blender BVH tree (world, m, round a local origin: 32-bit numbers), with the same methods
    as ``core.lifting_zones.Triangles``: ``nearest`` = Blender's own nearest point on the triangles."""

    def __init__(self, parts):
        from mathutils.bvhtree import BVHTree
        self.parts = list(parts)
        self.names, verts, polys, owner, lo, hi = [], [], [], [], [], []
        n = 0
        allv = [np.asarray(v, float) for _nm, v, _t in parts]
        self.origin = np.mean(np.vstack(allv), axis=0) if allv else np.zeros(3)
        for k, (name, v, t) in enumerate(parts):
            v = np.asarray(v, float)
            t = np.asarray(t, np.int64).reshape(-1, 3)
            self.names.append(name)
            verts.append(v - self.origin)
            polys.append(t + n)
            owner.append(np.full(len(t), k))
            lo.append(v.min(axis=0))
            hi.append(v.max(axis=0))
            n += len(v)
        self.lo = np.array(lo).reshape(-1, 3)
        self.hi = np.array(hi).reshape(-1, 3)
        self.owner = np.concatenate(owner) if owner else np.zeros(0, np.int64)
        self.tree = BVHTree.FromPolygons(np.vstack(verts).tolist(), np.vstack(polys).tolist()) if parts else None

    def nearest(self, points, need: float):
        pts = np.asarray(points, float) - self.origin
        d = np.full(len(pts), np.inf)
        who = np.full(len(pts), -1, np.int64)
        if self.tree is None:
            return d, who
        f = self.tree.find_nearest
        hit, cos, nrms = [], [], []
        for i, p in enumerate(pts):
            co, nrm, idx, dist = f(Vector(p), need)
            if co is not None:
                d[i], who[i] = dist, self.owner[idx]
                hit.append(i)
                cos.append(co)
                nrms.append(nrm)
        if hit:                                         # behind the nearest face, straight below it: inside (0 m)
            gap = pts[hit] - np.array(cos)
            n = np.array(nrms)
            g = np.linalg.norm(gap, axis=1)
            nn = np.linalg.norm(n, axis=1)
            inside = (g > 1e-9) & (nn > 1e-12) & (np.einsum("ij,ij->i", gap, n) < -Z.FACING * g * nn)
            d[np.array(hit)[inside]] = 0.0
        return d, who

    def without(self, drop):
        keep = [k for k in range(len(self.parts)) if k not in drop]
        return BVHObstacles([self.parts[k] for k in keep]), np.array(keep, np.int64)


def _mkey(ob, extra) -> tuple:
    M = np.round(np.array(ob.matrix_world), 5)
    return (ob.name, ob.data.name, len(ob.data.vertices), extra, M.tobytes())


def moving_objects(scene, crane, load):
    """[(object, kind, rig joint)] of what moves in the lift: the crane's mesh parts carried by a joint that turns with
    the slew, and – when the load hangs on this crane – the load's parts and its rigging (they follow the hoist)."""
    rig = lifting.rig_of(crane)
    pre = lifting.prefix(crane)
    slew = rig.role.get("slew")
    out = []
    for ob in crane.root.children_recursive:
        if ob.type != "MESH" or not _visible(ob) or ob.get(build.PROP_KIND) not in ("part", None):
            continue
        if "ROPE" in str(ob.get(build.PROP_NAME, ob.name)).upper():
            continue                                       # the hoist rope hangs from the boom head to the hook
        j = carrier_joint(scene, ob)
        if j is None or not j.name.startswith(pre):
            continue
        name = j.name[len(pre):]
        if name not in rig.by or (slew and slew not in rig.chain(name)):
            continue
        out.append((ob, "crane", name))
    if load is not None and load.rig_state == "HUNG" and load.hung_on == crane.name:
        hoist = rig.role.get("hoist")
        for ob in lifting.load_parts(load):
            if _visible(ob):
                out.append((ob, "load", hoist))
        for ob in scene.objects:
            if ob.type == "MESH" and ob.get(RIGGING_TAG) == load.name and _visible(ob):
                out.append((ob, "rigging", hoist))
    return out


def obstacle_objects(scene, crane, load, moving) -> list:
    """Every mesh shown that can be in the way: not this crane, not the load or its rigging, not the ground, the floor
    or the sea of the surroundings, not an app helper that is not a part (cable shapes)."""
    own = {o.name for o in crane.root.children_recursive} | {crane.root.name}
    own |= {o.name for o, _k, _j in moving}
    if load is not None:
        own |= {o.name for o in lifting.load_parts(load)}
    out = []
    for ob in scene.objects:
        if ob.type != "MESH" or ob.name in own or not _visible(ob):
            continue
        if ob.get(ENV_TAG) in GROUND_ROLES or (load is not None and ob.get(RIGGING_TAG) == load.name):
            continue
        if ob.get(RIGGING_TAG) is not None and load is None:
            continue
        if _helper(ob):
            continue
        if len(ob.data.polygons) == 0:
            continue
        out.append(ob)
    return out


def _helper(ob) -> bool:
    """An object the app draws for itself (a rope on a drum, cable shapes): not a part, a prop or surroundings."""
    return (ob.name.startswith("FR ") and ob.get(ENV_TAG) is None and ob.get(build.PROP_KIND) != "part"
            and ob.get("fr_prop") is None)


def fingerprint(scene, crane, load) -> tuple:
    """A cheap key of everything the clearance depends on but the joint values: every object's own place (its local
    matrix – a joint's motion, a part hung on the hook or drawn by the rigging keep theirs while the crane moves; the
    joints' own empties left out), what is shown, the meshes' sizes, the clearance needed, the crane's place."""
    L = lifting.plan(scene)
    obs = []
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) == "joint" or (ob.type != "MESH" and ob.parent is not None) or _helper(ob):
            continue                     # joints' and cylinders' empties turn with the crane: meshes and roots count;
                                         # the app's own drawn helpers (the rope on the drum) are no obstacles
        m = tuple(round(x, 5) for row in ob.matrix_basis for x in row)     # turned or scaled in place counts too
        obs.append((ob.name, m, ob.hide_viewport, ob.hide_get(), len(ob.data.vertices) if ob.type == "MESH" else -1))
    rk = (load.name, load.rig_state, load.hung_on) if load is not None else None
    return (crane.name, round(float(L.clearance_m), 4), rk, hash(tuple(obs)),
            tuple(np.round(np.array(crane.root.matrix_world), 5).ravel()))


_CLEAR: dict = {}


def clearance_for(scene, crane, load) -> Z.Clearance:
    """The lift's clearance (cached on ``fingerprint``)."""
    key = fingerprint(scene, crane, load)
    got = _CLEAR.get(crane.name)
    if got is not None and got[0] == key:
        return got[1]
    rig = lifting.rig_of(crane)
    motion = motion_of(crane, rig)
    vals = lifting.values(scene, crane)
    moving = moving_objects(scene, crane, load)
    bodies = []
    for ob, kind, jn in moving:
        v, t = _arrays(ob)
        if not len(t):
            continue
        G = motion(jn, vals)
        w = _world(ob, v)
        pw, sp = _points(("body", _mkey(ob, None)), w, t)   # on the surface, world, as it stands now
        if not len(pw):
            continue
        z = (pw - G[:3, 3]) @ G[:3, :3]                     # into the joint's frame at zero (G is rigid)
        bodies.append(Z.Body(str(ob.get(build.PROP_NAME, ob.name)), kind, jn, z, z.min(axis=0), z.max(axis=0),
                             spacing=sp))
    # only what the lift can come near: within the moving parts' reach of the slew axis (+ the search distance)
    centre = lifting.to_world(crane, rig.slew_centre(vals))
    reach = 0.0
    for b in bodies:
        c = np.array([[x, y, zz] for x in (b.lo[0], b.hi[0]) for y in (b.lo[1], b.hi[1]) for zz in (b.lo[2], b.hi[2])])
        reach = max(reach, float(np.max(np.linalg.norm(c[:, :2] - centre[:2], axis=1))))
    if load is not None and load.rig_state == "HUNG":
        reach += 2.0
    need = Z.NEED * float(lifting.plan(scene).clearance_m) / core.DEFAULT_LIMITS.crane
    parts = []
    for ob in obstacle_objects(scene, crane, load, moving):
        bb = np.array([ob.matrix_world @ Vector(c) for c in ob.bound_box])
        lo, hi = bb.min(axis=0), bb.max(axis=0)
        near = np.clip(centre[:2], lo[:2], hi[:2])
        if float(np.linalg.norm(near - centre[:2])) > reach + need:
            continue
        v, t = _arrays(ob)
        if not len(t):
            continue
        parts.append((str(ob.get(build.PROP_NAME, ob.name)), _world(ob, v), t))
    obstacles = BVHObstacles(parts)
    c = Z.Clearance(bodies, obstacles, motion, float(lifting.plan(scene).clearance_m))
    c.leave_out_touching([vals])                         # what the load stands on now (the pick)
    from . import lifting_path
    a = lifting_path.path_anim(scene)
    if a is not None and scene.fresing.anim_baked == a.name:
        try:
            at, _keys, (f0, f1) = lifting_path.reader(scene, crane)
            c.leave_out_touching([at(f0), at(f1)])
        except Exception:  # noqa: BLE001
            pass
    _CLEAR[crane.name] = (key, c)
    return c


LIVE_STILL = 0.3                       # s: the live clearance is worked out once the pose stood this long
_LIVE_CLR: dict = {"key": None, "seen": 0.0, "row": None, "row_key": None, "timer": False}


def live_row(scene, crane, load, key, force: bool = False):
    """The clearance row at the pose shown – worked out once the pose (``key``) has stood still ``LIVE_STILL`` s (a
    drag costs nothing): until then the last row, marked as being worked out."""
    now = time.perf_counter()
    S = _LIVE_CLR
    if S["row_key"] == key and S["row"] is not None:
        return S["row"]
    if S["key"] != key:
        S.update(key=key, seen=now)
    if not force and now - S["seen"] < LIVE_STILL:
        _later()
        last = S["row"]
        if last is None:
            return P.grey("CLR", "being worked out")
        out = P.Row(**{k: getattr(last, k) for k in ("id", "title", "status", "use", "value", "limit", "words",
                                                     "amber_at", "measure")})
        out.words = last.words + " (the pose moved: working it out again)"
        return out
    try:
        row = clearance_for(scene, crane, load).row(lifting.values(scene, crane))
    except Exception as exc:  # noqa: BLE001
        row = P.grey("CLR", str(exc).rstrip(".").lower())
    S.update(row=row, row_key=key)
    return row


def _later() -> None:
    if _LIVE_CLR["timer"] or bpy.app.background:
        return
    _LIVE_CLR["timer"] = True

    def tick():
        _LIVE_CLR["timer"] = False
        from . import lifting_path
        lifting_path.forget_live()
        _redraw()
        return None
    bpy.app.timers.register(tick, first_interval=LIVE_STILL + 0.05)


def row_function(scene, crane, load):
    """values -> the clearance row (for ``lifting_path.numbers``)."""
    c = clearance_for(scene, crane, load)
    return c.row


# ---------------------------------------------------------------------------------------------------------------------
# what is drawn: reach rings, the exclusion zone, the footprint

def _flat_to_world(crane, rig, xy, z_m: float = 0.0) -> np.ndarray:
    x, y = xy
    p = np.array([x, z_m, y]) if rig.up_axis == "Y" else np.array([x, y, z_m])
    return lifting.to_world(crane, p * 1000.0)


def tail_radius(scene, crane) -> float:
    """How far what turns with the slew (not the boom) reaches from the slew axis, m: the tail swing."""
    rig = lifting.rig_of(crane)
    slew = rig.role.get("slew")
    vals = lifting.values(scene, crane)
    c = lifting.to_world(crane, rig.slew_centre(vals))
    a = np.array(crane.root.matrix_world)[:3, :3] @ rig.axis(slew, vals) if slew else np.array([0.0, 0.0, 1.0])
    a = a / np.linalg.norm(a)
    pre = lifting.prefix(crane)
    best = 0.0
    for ob in crane.root.children_recursive:
        if ob.type != "MESH" or not _visible(ob):
            continue
        j = carrier_joint(scene, ob)
        if j is None or j.name != pre + str(slew):
            continue
        for co in ob.bound_box:
            p = np.array(ob.matrix_world @ Vector(co)) - c
            p = p - (p @ a) * a
            best = max(best, float(np.linalg.norm(p)))
    return best


def load_radius(load) -> float:
    """The load's half-size on the ground, m (0: no load)."""
    if load is None:
        return 0.0
    pts = []
    for ob in lifting.load_parts(load):
        pts += [np.array(ob.matrix_world @ Vector(c)) for c in ob.bound_box]
    if not pts:
        return 0.0
    p = np.array(pts)
    d = p.max(axis=0) - p.min(axis=0)
    return float(math.hypot(d[0], d[1]) / 2.0)


def view_data(scene, crane=None, load=None, values=None, path=None) -> dict | None:
    """What the plan view shows at ``values`` (default: now): world x-y (and the ground's z) of the slew centre, the
    reach rings, the footprint patches, the exclusion zone round ``path`` (hook points, world) – None without a
    crane."""
    from . import lifting_path as LP
    crane = crane if crane is not None else lifting.active_crane(scene)
    load = load if load is not None else lifting.active_load(scene)
    if crane is None or crane.root is None:
        return None
    L = lifting.plan(scene)
    rig = lifting.rig_of(crane)
    vals = values if values is not None else lifting.values(scene, crane)
    ck = LP.checks(scene, crane, load)
    ground = _flat_to_world(crane, rig, (0.0, 0.0))[2] + LIFT_GAP
    sc = lifting.to_world(crane, rig.slew_centre(vals))
    ro = LP.P.LR.readout(rig, vals, ck.charts, lifting.setup(scene, crane), load_kg=ck.plan.load_kg,
                         contingency=ck.plan.contingency, hook_block_kg=ck.plan.hook_block_kg,
                         rigging_kg=ck.plan.rigging_kg)
    re = Z.reach(ro.chart, ro.gross)
    rings = [(r, st) for r, st in ((re.full, core.RED), (re.amber, core.AMBER)) if r is not None]
    patches = []
    for pt in Z.footprint(ck, vals):
        d = pt.to_dict()
        d["corners"] = [tuple(_flat_to_world(crane, rig, c)[:2]) for c in pt.corners]
        patches.append(d)
    hook = lifting.to_world(crane, rig.hook(vals))
    pts = [tuple(p[:2]) for p in (path or [hook])]
    supports = [c for d in patches for c in d["corners"]]
    zone = Z.exclusion_zone(tuple(sc[:2]), tail_radius(scene, crane), supports, pts, load_radius(load),
                            float(L.zone_margin))
    return {"slew": tuple(sc[:2]), "z": float(ground), "rings": rings, "patches": patches, "zone": zone,
            "path": pts, "reach": {"full": re.full, "amber": re.amber, "longest": re.longest, "words": re.words,
                                   "gross": re.gross},
            "hook": (ro.radius, ro.height)}


_VIEW: dict = {"key": None, "data": None, "at": 0.0}


def live_view(scene):
    """``view_data`` at the pose shown, with the checked path's hook points when the path is checked and fresh;
    looked at most every ``lifting_path.LIVE_EVERY`` s and worked out only on a change."""
    from . import lifting_path as LP
    now = time.perf_counter()
    if _VIEW["data"] is not None and now - _VIEW["at"] < LP.LIVE_EVERY:
        return _VIEW["data"]
    crane, load = lifting.active_crane(scene), lifting.active_load(scene)
    if crane is None or crane.root is None:
        return None
    try:
        key = (LP._live_key(scene, crane, load), round(float(lifting.plan(scene).zone_margin), 4),
               lifting.plan(scene).path_result[:64], len(lifting.plan(scene).path_result))
    except Exception:  # noqa: BLE001
        return None
    _VIEW["at"] = now
    if key == _VIEW["key"]:
        return _VIEW["data"]
    r = LP.result(scene)
    path = None
    if r is not None and not LP.stale(scene):
        path = [np.array(p) for p in (r.get("view") or {}).get("path_world", [])] or None
    try:
        data = view_data(scene, crane, load, path=path)
    except Exception:  # noqa: BLE001 - a crane being set up, a broken file: nothing drawn
        data = None
    _VIEW.update(key=key, data=data)
    return data


def path_view(scene, crane, load, at_vals, f0: float, f1: float, found) -> dict:
    """The checked path's view for the plan sheet: the hook's path (world, and radius / height for the range diagram)
    at 0.25 s steps, the footprint at the ground check's worst moment, the exclusion zone round the whole path."""
    rig = lifting.rig_of(crane)
    fps = float(scene.render.fps) / float(scene.render.fps_base or 1.0)
    n = max(2, int(math.ceil((f1 - f0) / max(fps / 4.0, 1.0))) + 1)
    pts, side = [], []
    for f in np.linspace(f0, f1, n):
        v = at_vals(float(f))
        pts.append(lifting.to_world(crane, rig.hook(v)))
        side.append(rig.radius_height(v))
    t = None
    for cid in ("C5", "C6"):
        w = found.worst.get(cid)
        if w is not None and w.t is not None:
            t = w.t
    d = view_data(scene, crane, load, values=at_vals(t if t is not None else f0), path=pts)
    d["path_world"] = [list(map(float, p)) for p in pts]
    d["side"] = [list(map(float, x)) for x in side]
    d["ground_t"] = t
    return d


# ---------------------------------------------------------------------------------------------------------------------
# drawing in the 3D view

_DRAW = {"handle": None}
RGBA = {core.OK: (0.30, 0.69, 0.31, 0.55), core.AMBER: (0.98, 0.66, 0.15, 0.65), core.RED: (0.90, 0.22, 0.21, 0.7),
        core.NOT_CHECKED: (0.6, 0.6, 0.6, 0.5)}


def _draw():
    ctx = bpy.context
    scene = getattr(ctx, "scene", None)
    if scene is None or not hasattr(scene, "fresing") or not scene.fresing.lifting.cranes:
        return
    rv3d = ctx.region_data
    if rv3d is None or rv3d.view_perspective == "CAMERA":
        return
    if not lifting.cog_shown(scene) or not lifting.understood():
        return
    L = lifting.plan(scene)
    if not (L.show_reach or L.show_zone or L.show_footprint):
        return
    d = live_view(scene)
    if d is None:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    z = d["z"]
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    flat = gpu.shader.from_builtin("UNIFORM_COLOR")

    def fill(tris, col):
        if not tris:
            return
        b = batch_for_shader(flat, "TRIS", {"pos": tris})
        flat.uniform_float("color", col)
        b.draw(flat)

    line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    vp = gpu.state.viewport_get()
    line.uniform_float("viewportSize", (vp[2], vp[3]))

    def loop(pts, col, width=2.0):
        if len(pts) < 2:
            return
        seq = [(x, y, z) for x, y in pts] + [(pts[0][0], pts[0][1], z)]
        b = batch_for_shader(line, "LINE_STRIP", {"pos": seq})
        line.uniform_float("lineWidth", width)
        line.uniform_float("color", col)
        b.draw(line)

    if L.show_zone and len(d["zone"]) >= 3:
        cx = sum(p[0] for p in d["zone"]) / len(d["zone"])
        cy = sum(p[1] for p in d["zone"]) / len(d["zone"])
        tris = []
        for a, b in zip(d["zone"], d["zone"][1:] + d["zone"][:1]):
            tris += [(cx, cy, z - 0.005), (a[0], a[1], z - 0.005), (b[0], b[1], z - 0.005)]
        fill(tris, (0.9, 0.2, 0.2, 0.10))
        loop(d["zone"], (0.85, 0.1, 0.1, 0.95), 3.0)
    if L.show_reach:
        for r, st in d["rings"]:
            loop(Z.circle(d["slew"], r, 128), RGBA[st][:3] + (0.95,), 2.5)
    if L.show_footprint:
        for pt in d["patches"]:
            c = pt["corners"]
            fill([(c[0][0], c[0][1], z), (c[1][0], c[1][1], z), (c[2][0], c[2][1], z),
                  (c[0][0], c[0][1], z), (c[2][0], c[2][1], z), (c[3][0], c[3][1], z)], RGBA[pt["status"]])
            loop(c, (0.1, 0.1, 0.1, 0.8), 1.0)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


def register():
    if _DRAW["handle"] is None and not bpy.app.background:
        _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    if _DRAW["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        _DRAW["handle"] = None
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)


@bpy.app.handlers.persistent
def _load_post(_dummy=None):
    forget()
    _POINTS.clear()


# ---------------------------------------------------------------------------------------------------------------------
# the plan sheet

def sheet_path(scene) -> str:
    from . import render
    base = os.path.splitext(os.path.basename(bpy.data.filepath or ""))[0] or "lift"
    return os.path.join(render.default_output_dir(scene), f"{base} – lift plan.html")


def plan_sheet(scene, path: str | None = None) -> str:
    """Write the plan sheet (HTML): the checked path's rows and view when they are fresh, else the pose shown.
    Returns the file's path."""
    from . import lifting_path as LP
    crane, load = lifting.active_crane(scene), lifting.active_load(scene)
    if crane is None:
        raise ValueError("No crane yet: place one under Equipment.")
    L = lifting.plan(scene)
    rig = lifting.rig_of(crane)
    r = LP.result(scene)
    fresh = r is not None and not LP.stale(scene)
    if fresh:
        rows = LP.rows(scene)
        v = r.get("view") or {}
        view = dict(v) if v else view_data(scene, crane, load)
        when = f"along '{r.get('anim')}', frames {r['frames'][0]:g}–{r['frames'][1]:g} ({r['evaluations']} moments)"
    else:
        rows = LP.live_rows(scene, crane, load, force=True)
        rows = rows if isinstance(rows, list) else []
        view = view_data(scene, crane, load)
        when = "the pose shown (the path is not checked" + (" – changed since" if r is not None else "") + ")"
    vals = lifting.values(scene, crane)
    curve = Z.range_curve(rig, vals)
    ck = LP.checks(scene, crane, load)
    ro = LP.P.LR.readout(rig, vals, ck.charts, lifting.setup(scene, crane), load_kg=ck.plan.load_kg,
                         contingency=ck.plan.contingency, hook_block_kg=ck.plan.hook_block_kg,
                         rigging_kg=ck.plan.rigging_kg)
    chart_rows = list(zip(ro.chart.radius, ro.chart.capacity)) if ro.chart is not None else []
    re = view.get("reach") or {}
    rng = Z.range_svg(curve, chart_rows, re.get("full"), re.get("amber"), hook=tuple(view.get("hook") or ()) or None,
                      path=[tuple(p) for p in view.get("side") or []])
    plan = Z.plan_svg(view)
    m = lifting.load_mass(scene, load)[0] if load is not None else 0.0
    lines = [("Crane:", f"{crane.name}"), ("Load:", f"{load.name}, {core.tonnes(m):.2f} t" if load else "none"),
             ("Checked:", when), ("Chart:", ro.chart.name if ro.chart is not None else "none applies"),
             ("Clearance needed:", f"{L.clearance_m:.2f} m"), ("Exclusion zone margin:", f"{L.zone_margin:.2f} m"),
             ("Allowable ground pressure:", f"{L.allowable_kpa:.0f} kPa" if L.allowable_kpa > 0 else "not entered"),
             ("Mat:", f"{L.mat_size[0]:g} × {L.mat_size[1]:g} m" if min(L.mat_size) > 0 else "none (the pad)"),
             ("Made:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))]
    notes = [core.NOT_CHECKED_BY_APP[0].upper() + core.NOT_CHECKED_BY_APP[1:] + ": this sheet is a planning aid.",
             f"Clearance needed by default: {Z.REQUIRED_SOURCE}. A clearance is measured from points 5 cm apart on "
             "the moving parts to the obstacles' faces: the true gap, or up to about 3 cm more.",
             "Exclusion zone: the crane's tail swing (OSHA 29 CFR 1926.1424(a): mark the swing radius of the rotating "
             "superstructure), its outriggers or tracks and the load's path, widened by the margin.",
             re.get("words") or ""]
    if ro.sample:
        notes.insert(0, core.SAMPLE_MARK)
    page = Z.sheet_html(f"Lift plan – {load.name if load else crane.name}", lines, plan, rng, rows,
                        [n for n in notes if n])
    path = path or sheet_path(scene)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


def summary(scene) -> dict:
    """For tests and the PC check: what the panel and the drawing show now."""
    d = live_view(scene) or {}
    return json.loads(json.dumps({k: d.get(k) for k in ("rings", "zone", "patches", "reach")}, default=float))
