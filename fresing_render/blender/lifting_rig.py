"""Rigging in the scene (task 0232, Lifting lane L5): 8 Lifting plan > Rigging.

* **Lift points** of the active load: clicked on its parts (the hover picker of 0088: a click in a padeye's hole puts
  the point on the hole's axis), or found by their parts' names (``find_named``: padeyes, lifting lugs and eyes, the
  top corner castings of a container). Stored on the part, in its own coordinates.
* **Gear**: a sling set, shackles and, if wanted, a spreader beam or frame (``core/lifting_gear``: the built-in
  samples and the user's own files in "Lifting equipment").
* **Hang on the hook** works out where the load comes to rest under the active crane's hook (``core/lifting_hang``)
  and puts it there: an empty "FR hang <load>" sits on the hook (a child of the hoist's motion) in the solved pose, and
  each of the load's parts gets a Child Of constraint "FR hang" on it (inverse = identity: the part's own place is
  kept as its rest place, the empty adds the move). The slings, shackles and spreader are drawn as the app's own
  objects on the hook. Everything is rigid against the hook, so the load follows Hook to here, a crane pose, a
  joint step and a Build by Blender's own parenting – nothing runs per frame.
* **Set down** takes the empty off the hook where it is (the load stays there); the slings and the spreader are
  hidden. **Remove** takes the constraints off: the parts are back where they stood.
* The result (each leg's angle and force, checks C2–C4) is kept as JSON on the load (``rig_result``); it is worked
  out when the load is hung and marked out of date when the mass, the gear or the legs change after that.
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import lifting as core
from ..core import lifting_gear as GR
from ..core import lifting_hang as HG
from . import build, lifting, logic

CON = "FR hang"
HANG = "FR hang "
SLING = "FR sling "
SHACKLE = "FR shackle "
SPREADER = "FR spreader "
LINK = "FR master link "
TAG = "fr_rigging"                     # on every object the rigging made: the load's name
NAMED = ("PADEYE", "PAD EYE", "LIFTING LUG", "LIFT LUG", "LIFTING EYE", "LIFT POINT", "LIFTING POINT",
         "CORNER CASTING TOP", "TOP CORNER CASTING")
MODES = {"RIGID": "rigid", "EQUALISED": "equalised", "DNV": "dnv"}


# ---------------------------------------------------------------------------------------------------------------------
# gear

def gear_items() -> list:
    return GR.list_gear(lifting.library())


def gear(path: str):
    if not path:
        return None
    it = GR.find(path, lifting.library())
    return GR.gear_of(it) if it is not None else None


def gear_choices(kind: str) -> list:
    """(path, name) of the gear of one kind ('sling', 'shackle', 'spreader': beams and frames), own first."""
    kinds = ("spreader_beam", "lifting_frame") if kind == "spreader" else (kind,)
    return [(it.path or it.folder, it.name) for it in gear_items() if it.kind in kinds and it.ok]


# ---------------------------------------------------------------------------------------------------------------------
# lift points

def _letter(i: int) -> str:
    return chr(ord("A") + i) if i < 26 else f"P{i + 1}"


def point_world(p) -> np.ndarray | None:
    """A lift point where it is now (world, m; on the hook it moves with the load)."""
    if p.obj is None:
        return None
    return np.array(p.obj.matrix_world @ Vector(tuple(p.co)))


def point_rest(p) -> np.ndarray:
    """A lift point where it is with the load at rest (``solve`` takes the hang's constraints off first)."""
    return point_world(p)


def add_point(scene, load, ob, world) -> object:
    """A lift point on the part ``ob`` at ``world`` (m, where the part stands now)."""
    if ob is None or ob not in lifting.load_parts(load):
        raise ValueError("Click a part of the load: the lift point must be on the load.")
    M = np.array(ob.matrix_world)
    co = (np.linalg.inv(M) @ np.r_[np.asarray(world, float), 1.0])[:3]
    for q in load.points:
        if q.obj == ob and np.linalg.norm(np.asarray(q.co) - co) < 1e-4:
            raise ValueError("That lift point is there already.")
    p = load.points.add()
    p.name = _letter(len(load.points) - 1)
    p.obj = ob
    p.co = tuple(float(x) for x in co)
    load.points_index = len(load.points) - 1
    lifting._READ.clear()
    return p


def point_of_click(ob, polygon: int, loc, normal) -> np.ndarray:
    """Where a click on a part puts the lift point: on a hole's axis (a padeye's: where the shackle pin goes), else the
    clicked spot."""
    from . import joints
    o, d, desc = joints.axis_from_hit(ob, polygon, Vector(loc), Vector(normal))
    if desc.startswith("round face"):
        return np.array(o)
    return np.asarray(loc, float)


def _named_point(ob) -> np.ndarray:
    """A named lift part's point (world): the middle of its widest hole across a thin plate (a padeye), else the
    middle of its top (a corner casting's slot)."""
    me = ob.data
    M = np.array(ob.matrix_world)
    corners = np.array([list(v) for v in ob.bound_box])
    lo, hi = corners.min(axis=0), corners.max(axis=0)
    mid = 0.5 * (lo + hi)
    size = float(np.max(hi - lo))
    best = None
    if me is not None and "fr_axes" in me:
        ax = list(me["fr_axes"])
        for k in range(0, len(ax), 7):
            o, d, r = np.array(ax[k:k + 3]), np.array(ax[k + 3:k + 6]), abs(float(ax[k + 6]))
            if r <= 0 or r > 0.4 * size or abs(d[2]) > 0.3 * np.linalg.norm(d):
                continue
            d = d / np.linalg.norm(d)
            c = o + d * float((mid - o) @ d)              # on the axis, in the part's middle
            if best is None or r > best[1]:
                best = (c, r)
    p = best[0] if best is not None else np.array([mid[0], mid[1], hi[2]])
    return (M @ np.r_[p, 1.0])[:3]


def find_named(scene, load) -> int:
    """Add a lift point on every part of the load named like a lift point (padeye, lifting lug or eye, the top
    corner casting of a container) that has none yet. Returns how many were added."""
    have = {q.obj.name for q in load.points if q.obj is not None}
    n = 0
    for ob in lifting.load_parts(load):
        name = str(ob.get(build.PROP_NAME, ob.name)).upper()
        if ob.name in have or not any(w in name for w in NAMED):
            continue
        p = add_point(scene, load, ob, _named_point(ob))
        p.named = True
        n += 1
    return n


def remove_point(scene, load, index: int) -> None:
    if 0 <= index < len(load.points):
        load.points.remove(index)
        for i, p in enumerate(load.points):
            p.name = _letter(i)
        load.points_index = max(0, min(load.points_index, len(load.points) - 1))
        lifting._READ.clear()


# ---------------------------------------------------------------------------------------------------------------------
# the hang

def top_objects(load) -> list:
    """The objects the hang moves: the load's own parts / sub-assemblies (or its box), none inside another."""
    if load.kind == "BOX":
        return [load.box] if load.box is not None else []
    objs = [r.obj for r in load.parts if r.obj is not None]
    names = {o.name for o in objs}
    out = []
    for o in objs:
        up, inside = build.logical_parent(o), False
        while up is not None:
            if up.name in names:
                inside = True
                break
            up = build.logical_parent(up)
        if not inside:
            out.append(o)
    return out


def _detach(load) -> None:
    for ob in top_objects(load):
        c = ob.constraints.get(CON)
        if c is not None:
            ob.constraints.remove(c)


def _attach(load) -> None:
    for ob in top_objects(load):
        c = ob.constraints.get(CON) or ob.constraints.new("CHILD_OF")
        c.name = CON
        c.target = load.hang
        c.set_inverse_pending = False
        c.inverse_matrix = Matrix.Identity(4)


def _delete_drawn(load) -> None:
    for r in load.rig_objects:
        ob = r.obj
        if ob is None:
            continue
        me = ob.data if ob.type == "MESH" else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    load.rig_objects.clear()


def _hook_motion(scene, crane):
    from . import joints
    rig = lifting.rig_of(crane)
    j = joints.find(scene, lifting.prefix(crane) + rig.role["hoist"])
    if j is None or j.motion is None:
        raise ValueError(f"{crane.name}: its hoist joint is gone.")
    return j.motion


def lengths(load, g) -> list:
    base = float(load.leg_length) if load.leg_length > 0 else (g.length if g is not None else GR.DEFAULT_LENGTH)
    return [float(p.length) if p.length > 0 else base for p in load.points]


def _yaw(points_xy) -> float:
    P = np.asarray(points_xy, float)
    if len(P) == 2:
        d = P[1] - P[0]
        return math.atan2(d[1], d[0])
    c = P - P.mean(axis=0)
    w, v = np.linalg.eigh(c.T @ c)
    d = v[:, int(np.argmax(w))]
    return math.atan2(d[1], d[0])


def _spreader_rest(load, sp, pts, cog):
    """The spreader at rest over the load (world): turned along the lift points, its bottom padeyes paired with the
    nearest lift points. Returns (cog, top points, bottom points in the lift points' order, its 4 x 4 rest matrix)."""
    yaw = _yaw([p[:2] for p in pts])
    R = np.array([[math.cos(yaw), -math.sin(yaw), 0.0], [math.sin(yaw), math.cos(yaw), 0.0], [0.0, 0.0, 1.0]])
    z = max(p[2] for p in pts) + float(load.leg_length) + sp.height
    c = np.array([cog[0], cog[1], z])
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = R, c
    bottom = [(M @ np.r_[b, 1.0])[:3] for b in sp.bottom]
    top = [(M @ np.r_[t, 1.0])[:3] for t in sp.top]
    order, free = [], list(range(len(bottom)))
    for p in pts:
        k = min(free, key=lambda i: float(np.linalg.norm((bottom[i] - p)[:2])))
        free.remove(k)
        order.append(bottom[k])
    return (M @ np.r_[sp.cog, 1.0])[:3], top, order, M


def solve(scene, crane, load):
    """Work out the hang for the load as it stands (its parts at rest): (Hang, what was used)."""
    if not load.points:
        raise ValueError("Pick the lift points first (Find lift points, or Add lift point and click on the load).")
    m, _src = lifting.load_mass(scene, load)
    mass = m * float(load.contingency)
    if mass <= 0:
        raise ValueError("The load has no mass: enter it under Load first.")
    sling = gear(load.sling)
    sp = gear(load.spreader) if load.spreader else None
    if sp is not None and sp.problems:
        raise ValueError(sp.problems[0])
    if sp is not None and len(sp.bottom) != len(load.points):
        raise ValueError(f"{sp.name} has {len(sp.bottom)} bottom padeyes for {len(load.points)} lift points: pick a "
                         "spreader with as many, or change the lift points.")
    was = load.rig_state
    if was != "NONE":
        _detach(load)
        lifting._update()
    pts = [point_rest(p) for p in load.points]
    cog = _cog_rest(load)
    hook = lifting._hook_block_world(scene, crane)
    if hook is None:
        raise ValueError(f"{crane.name} has no hook block.")
    L = lengths(load, sling)
    names = [p.name for p in load.points]
    if sp is None:
        h = HG.single(mass, cog, pts, L, hook, names)
        used = {"spreader": None}
    else:
        sc, top, bottom, M0 = _spreader_rest(load, sp, pts, cog)
        h = HG.with_spreader(mass, cog, pts, L, sp.mass, sc, top, bottom, float(load.top_length), hook, names)
        used = {"spreader": sp, "spreader_rest": M0}
    if was != "NONE":
        _attach(load)
        lifting._update()
    used.update(mass=mass, sling=sling, lengths=L, points=pts, cog=cog)
    return h, used


def _cog_rest(load) -> np.ndarray:
    c = lifting.cog_world(load)
    if c is None:
        raise ValueError("The load has no CoG: work it out again under Load.")
    return np.asarray(c, float)


def rigging_mass(load) -> float:
    """kg: the slings (legs x mass per m + master link), a shackle per lift point, the spreader and its top legs."""
    if not load.points:
        return 0.0
    out = 0.0
    sl = gear(load.sling)
    if sl is not None and not sl.problems:
        out += sl.sling_mass(lengths(load, sl))
    sh = gear(load.shackle)
    if sh is not None and not sh.problems:
        out += sh.mass * len(load.points)
    sp = gear(load.spreader) if load.spreader else None
    if sp is not None and not sp.problems:
        out += sp.mass
        if sl is not None and not sl.problems:
            out += len(sp.top) * float(load.top_length) * sl.mass_per_m
    return out


def _key(scene, load) -> list:
    m, _ = lifting.load_mass(scene, load)
    return [round(m, 3), round(float(load.contingency), 4), load.sling, load.shackle, load.spreader,
            round(float(load.leg_length), 4), round(float(load.top_length), 4), load.leg_mode,
            [(p.obj.name if p.obj else "", [round(x, 5) for x in p.co], round(p.length, 4)) for p in load.points]]


def _auto_gear(load, h, mass) -> None:
    """Gear not picked yet: the smallest built-in chain sling and shackle that cover the legs' planned forces."""
    if not load.sling:
        legs = len([lg for lg in h.legs if lg.at_hook]) if len(h.poses) == 1 else 2
        f = max(HG.design_force(h, lg, mass, MODES[load.leg_mode]) for lg in h.legs) / core.G
        it = GR.sling_for(f, 4 if legs >= 3 else legs, "chain") or GR.sling_for(f, 4 if legs >= 3 else legs, "wire")
        if it is not None:
            load["sling"] = it.path
    if not load.shackle:
        f = max(HG.design_force(h, lg, mass, MODES[load.leg_mode]) for lg in h.legs) / core.G
        it = GR.shackle_for(f)
        if it is not None:
            load["shackle"] = it.path


def results(scene, h, used, load) -> dict:
    sling = gear(load.sling)
    shackle = gear(load.shackle)
    sp = used.get("spreader")
    mass = used["mass"]
    rows = HG.checks(h, mass, leg_wll=sling.wll if sling and not sling.problems else None,
                     shackle_wll=shackle.wll if shackle and not shackle.problems else None,
                     mode=MODES[load.leg_mode], spreader_wll=sp.wll if sp is not None else None,
                     spreader_mass=sp.mass if sp is not None else 0.0)
    return {
        "key": _key(scene, load),
        "legs": [{"name": lg.name, "force": lg.force, "angle": lg.angle, "taut": lg.taut, "at_hook": lg.at_hook,
                  "length": lg.length, "planned": HG.design_force(h, lg, mass, MODES[load.leg_mode])}
                 for lg in h.legs],
        "tilt": h.tilts[0], "problems": list(h.problems), "notes": list(h.notes), "mass": mass,
        "rigging": rigging_mass(load),
        "checks": [{"check": r.check, "title": r.title, "status": r.status, "use": r.use, "message": r.message,
                    "words": r.words,
                    "parts": [{"title": p.title, "status": p.status, "use": p.use, "message": p.message}
                              for p in r.parts]} for r in rows],
    }


def result(load) -> dict | None:
    try:
        return json.loads(load.rig_result) if load.rig_result else None
    except ValueError:
        return None


def stale(scene, load) -> bool:
    r = result(load)
    return r is not None and r.get("key") != json.loads(json.dumps(_key(scene, load)))


def hang(scene, crane, load) -> object:
    """Hang the load on the crane's hook (again): solve, put the empty on the hook, the constraints on the parts, the
    slings, shackles and spreader in the scene. Returns the Hang (its problems refuse: ValueError)."""
    h, used = solve(scene, crane, load)
    if not h.ok:
        raise ValueError(h.problems[0])
    _auto_gear(load, h, used["mass"])
    hook_ob = _hook_motion(scene, crane)
    _detach(load)
    _delete_drawn(load)
    lifting._update()
    emp = load.hang
    if emp is None or emp.name not in bpy.data.objects:
        emp = bpy.data.objects.new(HANG + load.name, None)
        emp.empty_display_type = "PLAIN_AXES"
        emp.empty_display_size = 0.01
        emp.hide_render = True
        emp.hide_select = True
        emp[TAG] = load.name
        coll = crane.root.users_collection[0] if crane.root.users_collection else scene.collection
        coll.objects.link(emp)
        load.hang = emp
    emp.parent = None
    emp.matrix_world = Matrix(h.poses[0].tolist())
    lifting._update()
    emp.parent = hook_ob
    emp.matrix_parent_inverse = hook_ob.matrix_world.inverted()
    emp.matrix_basis = Matrix(h.poses[0].tolist())
    _attach(load)
    _draw(scene, crane, load, h, used, hook_ob, emp)
    load.rig_state = "HUNG"
    load.hung_on = crane.name
    load.rig_result = json.dumps(results(scene, h, used, load), default=float)
    lifting._READ.clear()
    lifting._update()
    return h


def set_down(scene, load) -> None:
    """Take the load off the hook where it is: the empty stays in place, the slings and the spreader are hidden."""
    if load.rig_state != "HUNG" or load.hang is None:
        raise ValueError("The load is not on the hook.")
    emp = load.hang
    W = emp.matrix_world.copy()
    emp.parent = None
    emp.matrix_world = W
    for r in load.rig_objects:
        ob = r.obj
        if ob is not None and not ob.name.startswith(SHACKLE):
            ob.hide_viewport = True
            ob.hide_render = True
    load.rig_state = "DOWN"
    load.hung_on = ""
    lifting._READ.clear()
    lifting._update()


def remove(scene, load) -> None:
    """Take the rigging off: the parts are back where they stood (the lift points stay)."""
    _detach(load)
    _delete_drawn(load)
    if load.hang is not None and load.hang.name in bpy.data.objects:
        bpy.data.objects.remove(load.hang, do_unlink=True)
    load.hang = None
    load.rig_state = "NONE"
    load.hung_on = ""
    load.rig_result = ""
    lifting._READ.clear()
    lifting._update()


def on_crane_removed(scene, crane) -> None:
    """A crane taken out of the plan: a load on its hook is set down where it is."""
    for ld in lifting.plan(scene).loads:
        if ld.rig_state == "HUNG" and ld.hung_on == crane.name:
            set_down(scene, ld)


def on_load_removed(scene, load) -> None:
    remove(scene, load)


# ---------------------------------------------------------------------------------------------------------------------
# drawing the gear (the app's own objects)

def _frame_from(a, b):
    w = np.asarray(b, float) - np.asarray(a, float)
    w = w / max(1e-12, float(np.linalg.norm(w)))
    u = np.cross(w, [0.0, 0.0, 1.0]) if abs(w[2]) < 0.95 else np.cross(w, [1.0, 0.0, 0.0])
    u = u / np.linalg.norm(u)
    return u, np.cross(w, u), w


def _bar(vs, fs, a, b, r, n=8):
    """A round bar from a to b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u, v, _w = _frame_from(a, b)
    base = len(vs)
    for end in (a, b):
        for k in range(n):
            t = 2 * math.pi * k / n
            vs.append(end + r * (u * math.cos(t) + v * math.sin(t)))
    for k in range(n):
        k2 = (k + 1) % n
        fs.append((base + k, base + k2, base + n + k2, base + n + k))
    fs.append(tuple(base + k for k in reversed(range(n))))
    fs.append(tuple(base + n + k for k in range(n)))


def _box(vs, fs, M, size):
    lx, wy, hz = (s / 2 for s in size)
    base = len(vs)
    for z in (-hz, hz):
        for x, y in ((-lx, -wy), (lx, -wy), (lx, wy), (-lx, wy)):
            vs.append((M @ np.r_[x, y, z, 1.0])[:3])
    fs += [(base + 0, base + 3, base + 2, base + 1), (base + 4, base + 5, base + 6, base + 7),
           (base + 0, base + 1, base + 5, base + 4), (base + 1, base + 2, base + 6, base + 5),
           (base + 2, base + 3, base + 7, base + 6), (base + 3, base + 0, base + 4, base + 7)]


def _shackle_shape(vs, fs, p, up, g):
    """A bow shackle with its pin through p, its bow towards ``up`` (the leg): pin, two legs of the bow, its crown."""
    pin = g.pin if g is not None and g.pin > 0 else 0.03
    wid = g.inside_width if g is not None and g.inside_width > 0 else 1.6 * pin
    ln = g.inside_length if g is not None and g.inside_length > 0 else 3.9 * pin
    bow = g.bow if g is not None and g.bow > 0 else 0.85 * pin
    up = np.asarray(up, float) / max(1e-12, float(np.linalg.norm(up)))
    side = np.cross(up, [0.0, 0.0, 1.0])
    if np.linalg.norm(side) < 1e-6:
        side = np.array([1.0, 0.0, 0.0])
    side = side / np.linalg.norm(side)                    # the pin's axis: square to the leg, level
    half = wid / 2 + bow / 2
    a, b = p - side * (half + bow), p + side * (half + bow)
    _bar(vs, fs, a, b, pin / 2)
    top = p + up * ln
    pts = [p - side * half]
    for k in range(1, 8):                                  # the bow: down one side, round the crown, up the other
        t = math.pi * k / 8
        pts.append(top - up * (wid / 2) + (-math.cos(t) * side * half) + up * (math.sin(t) * wid / 2 * 1.4))
    pts.append(p + side * half)
    pts = [pts[0], p - side * half + up * (ln - wid / 2)] + pts[1:-1] + [p + side * half + up * (ln - wid / 2), pts[-1]]
    for q0, q1 in zip(pts, pts[1:]):
        _bar(vs, fs, q0, q1, bow / 2, n=6)
    return top


def _mat(kind: str, colour: str = ""):
    from . import materials
    ral = {"violet": "RAL 4005", "green": "RAL 6018", "yellow": "RAL 1023", "grey": "RAL 7037", "red": "RAL 3020",
           "brown": "RAL 8011", "blue": "RAL 5015", "orange": "RAL 2004"}
    try:
        if kind == "chain":
            return materials.ensure_material("Chain sling", "steel_raw", "")
        if kind == "wire":
            return materials.ensure_material("Wire rope sling", "galvanized", "")
        if kind == "round":
            return materials.ensure_material(f"Round sling {colour or 'blue'}", "paint_satin",
                                             ral.get(colour, "RAL 5015"))
        if kind == "shackle":
            return materials.ensure_material("Shackles", "paint_satin", "RAL 2004")
        return materials.ensure_material("Spreader", "paint_satin", "RAL 1003")
    except Exception:  # noqa: BLE001
        return None


def _new(name, vs, fs, coll, mat, parent, tag, load):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in vs], [], fs)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat is not None:
        ob.data.materials.append(mat)
    ob.parent = parent
    ob.matrix_parent_inverse = parent.matrix_world.inverted()
    ob[TAG] = tag
    ob.hide_select = True
    r = load.rig_objects.add()
    r.obj = ob
    return ob


def _draw(scene, crane, load, h, used, hook_ob, emp) -> None:
    lifting._update()
    coll = crane.root.users_collection[0] if crane.root.users_collection else scene.collection
    sling = gear(load.sling)
    shackle = gear(load.shackle)
    kind = sling.material if sling is not None and not sling.problems else "chain"
    d = sling.diameter if sling is not None and sling.diameter > 0 else 0.016
    rad = d * (0.9 if kind == "chain" else 0.5 if kind == "wire" else 0.45)
    mat_sl = _mat(kind, sling.colour if sling is not None else "")
    for lg in h.legs:
        vs, fs = [], []
        bottom = np.asarray(lg.bottom, float)
        up = np.asarray(lg.top, float) - bottom
        top = bottom
        if not lg.at_hook or len(h.poses) == 1:           # a shackle at every lift point (not at the spreader's top)
            svs, sfs = [], []
            top = _shackle_shape(svs, sfs, bottom, up, shackle)
            _new(f"{SHACKLE}{load.name} {lg.name}", svs, sfs, coll, _mat("shackle"), emp, load.name, load)
        _bar(vs, fs, top, lg.top, rad, n=8)
        _new(f"{SLING}{load.name} {lg.name}", vs, fs, coll, mat_sl, hook_ob, load.name, load)
    # the master link on the hook
    vs, fs = [], []
    H = np.asarray(h.hook, float)
    r_link = max(0.04, 2.5 * d)
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
        p0 = H + np.array([r_link * 0.6 * math.cos(a0), 0.0, r_link * math.sin(a0) - r_link * 0.4])
        p1 = H + np.array([r_link * 0.6 * math.cos(a1), 0.0, r_link * math.sin(a1) - r_link * 0.4])
        _bar(vs, fs, p0, p1, max(0.008, 0.7 * rad), n=6)
    _new(f"{LINK}{load.name}", vs, fs, coll, _mat("chain"), hook_ob, load.name, load)
    sp = used.get("spreader")
    if sp is not None:
        M = h.poses[1] @ used["spreader_rest"]
        span = max(float(np.ptp(np.array(sp.bottom)[:, 0])), float(np.ptp(np.array(sp.top)[:, 0])), 0.5)
        across = float(np.ptp(np.array(sp.bottom)[:, 1]))
        vs, fs = [], []
        if across > 0.3:                                  # a frame: two long beams and two cross beams
            for y in (-across / 2, across / 2):
                T = M.copy()
                T[:3, 3] = (M @ np.r_[0.0, y, 0.0, 1.0])[:3]
                _box(vs, fs, T, (span + 0.2, 0.6 * sp.height, sp.height))
            for x in (-span / 2, span / 2):
                T = M.copy()
                T[:3, 3] = (M @ np.r_[x, 0.0, 0.0, 1.0])[:3]
                _box(vs, fs, T, (0.6 * sp.height, across, sp.height))
        else:
            _box(vs, fs, M, (span + 0.2, 0.6 * sp.height, sp.height))
        for p in list(sp.top) + list(sp.bottom):
            T = M.copy()
            T[:3, 3] = (M @ np.r_[p, 1.0])[:3]
            _box(vs, fs, T, (0.04, 0.03, 0.18))
        _new(f"{SPREADER}{load.name}", vs, fs, coll, _mat("spreader"), hook_ob, load.name, load)


# ---------------------------------------------------------------------------------------------------------------------
# model update, checks

def after_model_update(scene, by_uid) -> None:
    """The load's parts are new objects: the lift points go to them, the hang's constraints are put on them again."""
    for ld in lifting.plan(scene).loads:
        for p in ld.points:
            ob = p.obj
            if ob is None:
                continue
            uid = ob.get(build.PROP_UID)
            new = by_uid.get(uid) if uid is not None else None
            if new is not None and new != ob:
                p.obj = new
        if ld.rig_state != "NONE" and ld.hang is not None:
            _attach(ld)


def check_hang(scene, crane=None, load=None, rel: float = 0.01) -> str:
    """The first load as hung: its CoG straight under the hook, each leg's force against the hand formulas (C2: in-plane
    statics, C3 rule), the load following the hook. Raises ValueError; returns a one-line summary."""
    L = lifting.plan(scene)
    load = load or (L.loads[0] if L.loads else None)
    if load is None or load.rig_state != "HUNG":
        raise ValueError("no load on the hook")
    crane = crane or next((c for c in L.cranes if c.name == load.hung_on), None)
    if crane is None:
        raise ValueError("the crane the load hangs on is gone")
    lifting._update()
    hook = lifting._hook_block_world(scene, crane)
    cog = lifting.cog_world(load)
    tol = 0.005 if not load.spreader else 0.05           # with a spreader: the CoG of load + spreader is under it
    if np.linalg.norm((cog - hook)[:2]) > tol:
        raise ValueError(f"the CoG is {np.linalg.norm((cog - hook)[:2]) * 1000:.0f} mm beside the hook")
    r = result(load)
    pts = [point_world(p) for p in load.points]
    m = r["mass"]
    hook_legs = [lg for lg in r["legs"] if lg["at_hook"]]
    if not load.spreader and len(hook_legs) == 2:
        ref = core.two_leg(m, pts[0], pts[1], hook).details["force"]
    elif not load.spreader and len(hook_legs) in (3, 4):
        ref = core.multi_leg(m, pts, hook, mode=MODES[load.leg_mode]).details["force"]
        got = [lg["planned"] for lg in hook_legs]
        ref = list(ref)
        if any(abs(a - b) > rel * max(b, 1.0) for a, b in zip(got, ref)):
            raise ValueError("the planned leg forces are not the C3 rule's")
        ref = None
    else:
        ref = None
    if ref is not None:
        got = [lg["force"] for lg in hook_legs]
        if any(abs(a - b) > rel * max(b, 1.0) for a, b in zip(got, ref)):
            raise ValueError("the leg forces are not the hand formula's: "
                             + ", ".join(f"{core.tonnes(a / core.G):.3f} t vs {core.tonnes(b / core.G):.3f} t"
                                         for a, b in zip(got, ref)))
    up = sum(lg["force"] for lg in r["legs"] if lg["taut"] and lg["at_hook"])
    if up < m * core.G * (1 - rel):
        raise ValueError("the legs at the hook carry less than the load")
    # it follows the hook: lower it 0.5 m and look again
    rig = lifting.rig_of(crane)
    hoist = rig.role["hoist"]
    was = lifting.values(scene, crane)
    try:
        lifting.set_values(scene, crane, {hoist: float(was.get(hoist, 0.0)) + 500.0})
        lifting._update()
        moved = lifting.cog_world(load) - cog
    finally:
        lifting.set_values(scene, crane, {hoist: float(was.get(hoist, 0.0))})
        lifting._update()
    if np.linalg.norm(moved - np.array([0, 0, -0.5])) > 0.002:
        raise ValueError(f"the load did not follow the hook ({moved})")
    forces = ", ".join(f"{lg['name']} {core.tonnes(lg['force'] / core.G):.2f} t at {lg['angle']:.0f}°"
                       for lg in r["legs"])
    return f"{load.name} on {crane.name}: tilt {r['tilt']:.1f}°, legs {forces}"
