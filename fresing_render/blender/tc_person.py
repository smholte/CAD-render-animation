"""The operator who changes the tool (task 0156): a whole person at a manual tool change.

The step's choice "Who changes the tool" (6 Animation > Run G-code program > Lines, tool changes …) is None, Hand or
Person. With Person, "Build animation" puts the operator in (a person of 0155 with 0157's rig, in its own collection
"FR operator", tagged ``TAG``), a tool trolley beside it and the tools lying on the trolley's top:

* while the G-code steps are built (``toolchange.tool_keys_plain``), every manual change with the person calls
  ``change``: the tool copies the hand carries and the ones on the trolley are made, their visibility keyed at the
  moments of ``core/toolchange.person_keys`` (old tool out at the end of "release", new tool in at the end of "clamp"),
  and the door's joint keyed open and closed;
* at the end of the Build ``bake`` reads where the holder is in each pause, finds a stand spot in front of the spindle,
  a spot for the trolley and a clear way from the start spot (``core/tc_person.Floor``: what stands in the way between
  knee and head height, the door also open), plans the walk and the moves (``core/tc_person.Operator``) and keys every
  frame: the person (``person_rig.key_poses``) and the tools in the hand (their world matrix).

The person never walks through the machine: its way is planned round everything shown. The clash check knows it
(``_clash_hook``: its body as it stands, moved along its way). "Clear keys" removes the tool copies (they are "tool"
copies of gcode.py) and puts the operator back where it stood; ``operator_visible`` (scene, saved with a shot) hides
the operator, its trolley and the tools it carries for a shot (the tools then swap in the spindle as without a hand).

The two spots can be moved: "Show the spots" makes the empties "FR operator stand" and "FR operator start"; while they
exist their places are used.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector  # noqa: F401

from ..core import people as PL
from ..core import tc_person as core
from ..core import toolchange as TC
from . import build, gcode, joints, person_rig

TAG = "fr_tc_operator"              # on the operator: "person"; its trolley: "trolley"; its spots: "stand" / "start"
COLLECTION = "FR operator"
NAME = "Operator"
TROLLEY = "FR tool trolley"
STAND, START = "FR operator stand", "FR operator start"
HOME = "fr_home"                    # where the operator stood before the Build: (x, y, z, turn)
CARRY = "fr_cnc_hold"               # on a tool copy in the operator's hand: its T number
ON_TROLLEY = "fr_cnc_trolley"       # on a tool copy lying on the trolley: its T number
AREA = 4.0                          # m round the spindle the floor is read for the way in
_PENDING: dict = {}                 # per scene: the changes of the Build that is running


def settings(scene):
    return gcode.settings(scene)


def is_on(b) -> bool:
    """Whether a G-code step has the person change the tools."""
    return getattr(b, "gcode_operator", "") == "PERSON"


# ---------------------------------------------------------------------------
# objects
# ---------------------------------------------------------------------------

def _collection(scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def operator(scene=None):
    """The operator person (or None)."""
    for ob in bpy.data.objects:
        if ob.get(TAG) == "person" and (scene is None or ob.name in scene.objects):
            return ob
    return None


def trolley(scene=None):
    for ob in bpy.data.objects:
        if ob.get(TAG) == "trolley" and (scene is None or ob.name in scene.objects):
            return ob
    return None


def spot(scene, which: str):
    """The empty the owner moves for the stand spot ("stand") or the start spot ("start"), or None."""
    for ob in bpy.data.objects:
        if ob.get(TAG) == which and ob.name in scene.objects:
            return ob
    return None


def _move_to_own(scene, ob) -> None:
    col = _collection(scene)
    for c in list(ob.users_collection):
        if c is not col:
            c.objects.unlink(ob)
    if ob.name not in col.objects:
        col.objects.link(ob)


def ensure_operator(scene, location=None, heading: float = 0.0):
    """The operator person, made when there is none (a person prop of 0155 with 0157's rig, gloves on, no helmet)."""
    from . import surroundings as sur
    ob = operator(scene)
    c = settings(scene)
    if ob is None:
        ob = sur.add_prop(scene, "PERSON")
        ob.name = NAME
        ob[TAG] = "person"
        _move_to_own(scene, ob)
        ob.location = Vector(location) if location is not None else ob.location
        ob.rotation_euler.z = heading
    ps = ob.fresing_person
    want = {"height_choice": c.op_height, "outfit": c.op_outfit, "gloves": True, "helmet": bool(c.op_helmet),
            "pose": "STANDING"}
    changed = False
    for k, v in want.items():
        if getattr(ps, k) != v:
            setattr(ps, k, v)
            changed = True
    arm = person_rig.ensure(ob)
    if changed:
        person_rig.rebuild(ob)
        arm = person_rig.rig_of(ob)
    if arm is not None:
        _move_to_own(scene, arm)
    return ob


def ensure_trolley(scene):
    from . import surroundings as sur
    ob = trolley(scene)
    if ob is None:
        ob = sur.add_prop(scene, "TOOL_TROLLEY")
        ob.name = TROLLEY
        ob[TAG] = "trolley"
        _move_to_own(scene, ob)
    return ob


def show_spots(scene) -> tuple:
    """Make (or keep) the two empties the owner moves: the stand spot and the start spot, at the places the last Build
    used (or worked out now). Returns (stand, start)."""
    col = _collection(scene)
    places = auto_spots(scene)
    out = []
    for which, name, size in (("stand", STAND, 0.3), ("start", START, 0.4)):
        ob = spot(scene, which)
        if ob is None:
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "SINGLE_ARROW" if which == "stand" else "CIRCLE"
            ob.empty_display_size = size
            ob[TAG] = which
            col.objects.link(ob)
            p = places.get(which)
            if p is not None:
                ob.location = Vector(p[:3])
                ob.rotation_euler = (0.0 if which == "stand" else math.pi / 2, 0.0, p[3] if len(p) > 3 else 0.0)
            ob.hide_render = True
        out.append(ob)
    return tuple(out)


def remove_spots(scene) -> None:
    for which in ("stand", "start"):
        ob = spot(scene, which)
        if ob is not None:
            bpy.data.objects.remove(ob)


def auto_spots(scene) -> dict:
    """The places the last Build used: {"stand": (x, y, z, heading), "start": (x, y, z)} (empty before one)."""
    c = settings(scene)
    out = {}
    for k in ("stand", "start"):
        v = c.get(f"fr_op_{k}")
        if v is not None:
            out[k] = tuple(float(x) for x in v)
    return out


# ---------------------------------------------------------------------------
# while the G-code steps are built
# ---------------------------------------------------------------------------

def begin(scene) -> None:
    """A Build starts: nothing collected yet."""
    _PENDING[scene.name] = {"changes": [], "copies": {}, "trolley": {}, "door": None}


def _pending(scene) -> dict:
    return _PENDING.setdefault(scene.name, {"changes": [], "copies": {}, "trolley": {}, "door": None})


def _tool_copy(name, src, col, tag, n):
    cp = bpy.data.objects.new(name, src.data)
    cp[gcode.TAG] = "tool"
    cp[tag] = n
    cp[build.PROP_KIND] = "cnc"
    cp.hide_select = True
    col.objects.link(cp)
    for i, slot in enumerate(src.material_slots):
        if slot.link == "OBJECT" and i < len(cp.material_slots):
            cp.material_slots[i].link = "OBJECT"
            cp.material_slots[i].material = slot.material
    cp.rotation_mode = "QUATERNION"
    cp.hide_render = cp.hide_viewport = True
    return cp


def start_step(scene, f0: float, numbers: list, start: int, show: dict, spindle, key, prog=None) -> None:
    """A step whose manual changes the person does starts: its tools lie on the trolley, but the one in the
    spindle."""
    from . import toolchange
    pend = _pending(scene)
    col = gcode._collection(scene)
    gauges = pend.setdefault("gauge", {})
    for n in numbers:
        if n not in gauges and prog is not None:
            try:
                gauges[n] = float(toolchange.gauge_of(scene, prog, n))
            except Exception:
                pass
        src = show.get(n, spindle) if n else spindle
        if n not in pend["copies"]:
            carried = _tool_copy(f"FR tool T{n} in the operator's hand", src, col, CARRY, n)
            carried["fr_cnc_src"] = src.name                  # what shows the tool in the spindle
            pend["copies"][n] = (carried.name, src.name)
            pend["trolley"][n] = _tool_copy(f"FR tool T{n} on the trolley", src, col, ON_TROLLEY, n).name
        key(bpy.data.objects[pend["trolley"][n]], f0, n == start)
        key(bpy.data.objects[pend["copies"][n][0]], f0, True)


def change(scene, mach, c, old: int, f0: float, fps: float, key, jkeys, jstate, busy_until, merge,
           step_start: float) -> None:
    """One manual change done by the person: the copies' visibility and the door's keys (the places come in
    ``bake``)."""
    from . import animation
    pend = _pending(scene)
    t0, length = c.hand
    moves = TC.person_keys(t0, length, c.door)
    at = {name: (a, b) for a, b, name in moves}
    out_t, in_t = TC.person_events(t0, length, c.door)
    for n, hidden_from, shown_from in ((old, at["set"][1], out_t), (c.tool, in_t, at["take"][1])):
        names = pend["copies"].get(n)
        if names is None:
            continue
        carried = bpy.data.objects.get(names[0])
        lying = bpy.data.objects.get(pend["trolley"][n])
        if n == old:                                # out of the spindle into the hand, then onto the trolley
            key(carried, f0 + out_t * fps, False)
            key(carried, f0 + at["set"][1] * fps, True)
            key(lying, f0 + at["set"][1] * fps, False)
        else:                                       # off the trolley into the hand, then into the spindle
            key(lying, f0 + at["take"][1] * fps, True)
            key(carried, f0 + at["take"][1] * fps, False)
            key(carried, f0 + in_t * fps, True)
    j = door_joint(scene)
    if j is not None and c.door > 0 and "open" in at:
        keys = jkeys.setdefault(j.name, [(1, jstate.get(j.name, joints.get_value(j)), "CONSTANT", "AUTO")])
        closed, opened = door_values(scene, j)
        interp, ez = animation.EASING["SMOOTH"]
        for (a, b), v0, v1 in ((at["open"], closed, opened), (at["close"], opened, closed)):
            merge(keys, f0 + a * fps, v0, interp, ez)
            merge(keys, f0 + b * fps, v1, "CONSTANT")
        jstate[j.name] = closed
        busy_until[j.name] = max(busy_until.get(j.name, 0), int(math.ceil(f0 + at["close"][1] * fps)))
    pend["changes"].append({"t0": step_start + t0, "length": length, "door": c.door, "old": old, "new": c.tool,
                            "frame": f0 + (t0 + length / 2) * fps})


# ---------------------------------------------------------------------------
# the door
# ---------------------------------------------------------------------------

def door_joint(scene):
    c = settings(scene)
    if not c.op_door:
        return None
    j = scene.fresing.joints.get(c.op_door)
    if j is None or j.kind not in ("SLIDE", "ROTATE"):
        return None
    return j


def door_values(scene, j) -> tuple:
    """(closed, open) values of the door's joint: closed as in the CAD model (0), open as set."""
    c = settings(scene)
    return 0.0, float(c.op_door_open if j.kind == "SLIDE" else c.op_door_angle)


def door_time(scene) -> float:
    """Seconds the door takes to open (0: no door)."""
    j = door_joint(scene)
    if j is None:
        return 0.0
    closed, opened = door_values(scene, j)
    if abs(opened - closed) < 1e-6:
        return 0.0
    sp = 0.7 if j.kind == "SLIDE" else math.radians(110)
    return max(TC.DOOR_MIN, abs(opened - closed) / sp)


def _door(scene, toward) -> core.Door | None:
    """The door as the core needs it, read in the CAD pose of the door (value 0)."""
    j = door_joint(scene)
    if j is None:
        return None
    closed, opened = door_values(scene, j)
    if abs(opened - closed) < 1e-6:
        return None
    origin, d = joints.axis_world(j)
    v_now = joints.get_value(j)
    pts = []
    for ob in _members(j):
        if ob.type != "MESH" or ob.data is None:
            continue
        v = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", v)
        M = np.array(ob.matrix_world)
        p = v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        pts.append(p)
    if not pts:
        return None
    pts = np.concatenate(pts)
    dd = np.array(d, float)
    o = np.array(origin, float)
    door = core.Door("SLIDE" if j.kind == "SLIDE" else "ROTATE", o, dd, closed, opened, np.zeros(3),
                     np.asarray(toward, float))
    back = door.move(v_now)                              # read where it is now: take it back to closed
    inv = core.PL.inv4(back)
    pts = pts @ inv[:3, :3].T + inv[:3, 3]
    from . import surroundings as sur
    door.handle = handle_point(pts, door, np.asarray(toward, float), sur.floor_height(scene))
    return door


def _members(j) -> list:
    out = []
    for m in getattr(j, "members", []):
        ob = getattr(m, "obj", None)
        if ob is not None:
            out.append(ob)
            out += [c for c in ob.children_recursive if c.type == "MESH"]
    return out


def handle_point(pts: np.ndarray, door: core.Door, toward: np.ndarray, floor_z: float) -> np.ndarray:
    """Where a hand takes the door (its points closed): on its face towards the person, at the edge it opens from
    (a slide: the edge away from the way it opens; a turn: the edge furthest from the hinge), at about hand height."""
    t = core.unit(np.array((toward[0], toward[1], 0.0)))
    front = pts[pts @ t >= float(np.max(pts @ t)) - 0.05]
    if door.kind == "SLIDE":
        dirn = core.unit(door.direction) * (1.0 if door.open >= door.closed else -1.0)
        s = front @ dirn
        edge = front[s <= float(np.min(s)) + 0.08]
    else:
        ax = core.unit(door.direction)
        rel = front - door.origin
        rad = np.linalg.norm(rel - np.outer(rel @ ax, ax), axis=1)
        edge = front[rad >= float(np.max(rad)) - 0.08]
    zs = edge[:, 2]
    want = floor_z + 1.1
    z = min(max(float(np.min(zs)) + 0.06, want), float(np.max(zs)) - 0.06) if len(zs) else want
    if len(zs) and float(np.max(zs)) - float(np.min(zs)) < 0.12:
        z = float(np.mean(zs))
    near = edge[np.argsort(np.abs(zs - z))[:max(1, len(edge) // 4)]]
    p = near.mean(axis=0)
    p = p + t * (float(np.max(near @ t)) - float(p @ t))     # its front, towards the person
    p[2] = z
    return p - t * 0.011                              # the middle of a handle bar (Ø22), not its front


# ---------------------------------------------------------------------------
# reading the scene
# ---------------------------------------------------------------------------

def _world(ob) -> Matrix:
    """An object's world matrix also while it is hidden (a hidden object is not worked out by Blender)."""
    if ob.parent is None:
        return ob.matrix_world.copy() if not ob.hide_viewport else ob.matrix_basis.copy()
    return _world(ob.parent) @ ob.matrix_parent_inverse @ ob.matrix_basis if ob.hide_viewport else \
        ob.matrix_world.copy()


def _np4(M) -> np.ndarray:
    return np.array([list(r) for r in M], float)


def _tool_shape(ob, spindle) -> tuple:
    """(tip frame in the object's own space (4x4), the tool's points in that frame)."""
    from . import toolchange
    F = toolchange._frame_of(ob, spindle)
    me = ob.data
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    inv = _np4(F.inverted())
    p = v.reshape(-1, 3) @ inv[:3, :3].T + inv[:3, 3]
    return _np4(F), p


def _floor(scene, centre_xy, skip: set, also=()) -> core.Floor:
    """What stands on the floor round ``centre_xy`` between knee and head height (every shown mesh but the operator,
    its tools, people and items), and the door also open. ``also``: points the map must reach (the owner's spots)."""
    from . import surroundings as sur
    z = sur.floor_height(scene)
    pts = np.array([tuple(centre_xy[:2])] + [tuple(p[:2]) for p in also], float)
    lo = pts.min(axis=0) - AREA
    hi = pts.max(axis=0) + AREA
    fl = core.Floor(lo, hi, z=z, cell=0.04)
    door = door_joint(scene)
    door_obs = {ob.name for ob in (_members(door) if door is not None else [])}
    move = None
    if door is not None:
        try:
            dd = _door(scene, (0.0, -1.0, 0.0))
            if dd is not None:
                move = dd.move(dd.open) @ core.PL.inv4(dd.move(joints.get_value(door)))
        except Exception:
            move = None
    for ob in scene.objects:
        if ob.type != "MESH" or ob.name in skip or ob.hide_render or ob.hide_viewport or ob.data is None:
            continue
        if ob.get(TAG) or ob.get(gcode.TAG) == "tool" or ob.get("fr_item") or ob.get("fr_person_path"):
            continue
        if ob.get(sur.PROP_TAG) == "PERSON":
            continue
        if not len(ob.data.polygons):
            continue
        M = _np4(ob.matrix_world)
        bb = np.array([tuple(c) for c in ob.bound_box]) @ M[:3, :3].T + M[:3, 3]
        if (bb[:, 0].max() < lo[0] or bb[:, 0].min() > hi[0] or bb[:, 1].max() < lo[1] or bb[:, 1].min() > hi[1]
                or bb[:, 2].max() < z + core.BAND[0] or bb[:, 2].min() > z + core.BAND[1]):
            continue
        me = ob.data
        me.calc_loop_triangles()
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", v)
        t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", t)
        pts = v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        tris = pts[t.reshape(-1, 3)]
        fl.add_triangles(tris)
        if move is not None and ob.name in door_obs:
            tris2 = tris @ move[:3, :3].T + move[:3, 3]
            fl.add_triangles(tris2)
    return fl


def _button(scene, H: np.ndarray, toward: np.ndarray, skip: set):
    """A point on the head above the holder on the person's left, where a hand presses the drawbar button: (point,
    the way the face looks) or None."""
    dg = bpy.context.evaluated_depsgraph_get()
    z = core.unit(H[:3, 2])
    t = core.unit(np.array((toward[0], toward[1], 0.0)))
    left = np.cross(t, z)                      # the person's left (it faces -t, z up)
    tries = [(up, side) for side in (0.13, 0.11, 0.15, 0.09) for up in (0.16, 0.13, 0.19, 0.1, 0.22)]
    for up, side in tries:                     # the hand beside the spindle, not on it
        p0 = H[:3, 3] + z * up + left * side
        o = Vector(p0 + t * 0.5)
        for _i in range(4):
            ok, loc, nrm, _f, ob, _m = scene.ray_cast(dg, o, Vector(-t), distance=0.75)
            if not ok:
                break
            ob = getattr(ob, "original", ob)
            if ob.name in skip or ob.get(gcode.TAG) == "tool" or ob.get(TAG):
                o = loc - Vector(t) * 1e-3
                continue
            p = np.array(loc)
            if float(np.linalg.norm((p - H[:3, 3]) - z * float(np.dot(p - H[:3, 3], z)))) < 0.16 and \
                    float(np.dot(np.array(nrm), t)) > 0.5:
                return p, np.array(nrm)
            break
    return None


# ---------------------------------------------------------------------------
# the end of the Build
# ---------------------------------------------------------------------------

def bake(scene, anim) -> list:
    """Plan and key the operator for the changes collected in this Build. Returns warnings."""
    from . import animation
    pend = _PENDING.pop(scene.name, None)
    if not pend or not pend["changes"]:
        _hide_unused(scene)
        return []
    warnings = []
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError as exc:
        return [f"The operator: {exc}"]
    fps = animation.fps_of(anim)
    spindle = mach.tool
    from . import toolchange
    ob_person = operator(scene)
    skip = {spindle.name}
    if ob_person is not None:
        skip |= {ob_person.name}
    stations = []
    grips = {}
    first_H = None
    shapes = {}
    toward = np.array((0.0, -1.0, 0.0))
    st_ob, start_ob = spot(scene, "stand"), spot(scene, "start")
    fps_b = fps

    def sample_at(frame: float, n: int):
        """(grip point, axis, the copy of tool n as it sits in the spindle, its tip frame, its points) at a frame."""
        scene.frame_set(int(round(frame)))
        W = _np4(_world(spindle) @ gcode.tool_frame(spindle))     # the reference tip in the spindle
        axis = core.unit(W[:3, 2])
        nose = W[:3, 3] + axis * toolchange.ref_gauge(scene, mach)  # the spindle's gauge line (its nose)
        depth = core.GRIP_BELOW
        names = pend["copies"].get(n)
        src = bpy.data.objects.get(names[1]) if names is not None else None
        if src is None:
            return nose - axis * depth, axis, None
        if n not in shapes:
            shapes[n] = _tool_shape(src, spindle)
        F, pts = shapes[n]
        g = pend.get("gauge", {}).get(n) or toolchange.ref_gauge(scene, mach)
        Wsrc = _np4(_world(src))
        tip = Wsrc @ F
        own = tip[:3, 3] + core.unit(tip[:3, 2]) * g
        if float(np.dot(own - nose, axis)) < 0.0:            # a tool shown lower than the spindle's nose
            nose = own
        depth = core.grip_depth(pts, g)
        return nose - axis * depth, axis, (Wsrc, tip, pts)

    for ch in pend["changes"]:
        out_t, in_t = TC.person_events(ch["t0"], ch["length"], ch["door"])
        f_out, f_in = 1.0 + out_t * fps_b - 0.5, 1.0 + in_t * fps_b + 0.5    # just before the old tool comes out,
        g_old, ax_old, t_old = sample_at(f_out, ch["old"])                      # just after the new one is in
        g_new, ax_new, t_new = sample_at(f_in, ch["new"])
        if first_H is None:
            first_stand = np.array(st_ob.matrix_world.translation[:2]) if st_ob is not None else None
            first_H = g_old
        tools = {}
        if t_old is not None:
            tools[ch["old"]] = t_old
        if t_new is not None:
            tools[ch["new"]] = t_new
        stations.append((ch, (g_old, ax_old, f_out), (g_new, ax_new, f_in), tools))
    if first_H is None:
        return warnings
    # the stand spot: in front of the spindle (−y of the world, as the hand of task 0041), or the owner's
    fl = _floor(scene, first_H[:2], skip,
                [np.array(o.matrix_world.translation[:2]) for o in (st_ob, start_ob) if o is not None])
    if first_stand is None:
        stand_xy = core.stand_spot(fl, first_H[:2], toward[:2])
        if stand_xy is None:
            return ["The operator: there is no free spot in front of the spindle to stand on (move the stand spot: "
                    "6 Animation > Run G-code program > Lines, tool changes … > Show the spots)"]
    else:
        stand_xy = first_stand
        if not fl.is_free(stand_xy, core.BODY):
            warnings.append("The operator's stand spot is too close to the machine: it may stand in it")
    heading = PL.heading_of(first_H[:2] - stand_xy)
    toward_p = np.array((stand_xy[0] - first_H[0], stand_xy[1] - first_H[1], 0.0))
    right_way = core.palm_way(heading)
    # the trolley
    c = settings(scene)
    tr = core.trolley_spot(fl, stand_xy, heading)
    trol_ob = ensure_trolley(scene)
    trol = None
    if tr is not None:
        centre, th = tr
        trol_ob.location = (float(centre[0]), float(centre[1]), fl.z)
        trol_ob.rotation_euler = (0.0, 0.0, th + math.pi / 2)
        trol_ob.hide_render = trol_ob.hide_viewport = False
        bpy.context.view_layer.update()
        top = _trolley_top(scene, trol_ob, fl.z)
        trol = core.Trolley(centre, th, top)
        fl.add_triangles(_mesh_tris(trol_ob))
    else:
        trol_ob.hide_render = trol_ob.hide_viewport = True
        warnings.append("The operator: there is no room for the tool trolley on its right: the tools are not laid "
                        "down (move the stand spot: Show the spots)")
    # the stations in the core's terms
    k_stations = []
    for ch, (grip_pt, axis, f_out), (grip_n, axis_n, f_in), tools in stations:
        H = core.m4(core.frame_of(axis, right_way), grip_pt)
        Hn = core.m4(core.frame_of(axis_n, right_way), grip_n)
        tw = {}
        for n, (Wsrc, tip_world, pts) in tools.items():
            tw[n] = Wsrc
            if n not in grips:
                L = np.linalg.inv(Wsrc) @ (H if n == ch["old"] else Hn)   # the grip frame in the copy's own space
                rad = np.linalg.norm(pts[:, :2], axis=1)
                grips[n] = (L, float(rad.max()) if len(rad) else 0.03)
        s = core.Station(ch["old"], ch["new"], ch["t0"], ch["length"], H, tw, grips, door=ch["door"],
                         spindle_new=Hn)
        hr = []
        for n, (Wsrc, tip_world, pts) in tools.items():
            Lg = np.linalg.inv(tip_world) @ (H if n == ch["old"] else Hn)
            zg = Lg[2, 3]
            near = pts[np.abs(pts[:, 2] - zg) < 0.006]
            if len(near):
                hr.append(float(np.linalg.norm(near[:, :2], axis=1).max()))
        s.holder_r = min(0.045, max(0.012, max(hr))) if hr else core.HOLDER_R
        if c.op_button:
            scene.frame_set(int(round(f_out)))
            s.button = _button(scene, H, toward_p, skip)
            scene.frame_set(int(round(f_in)))
            s.button_new = _button(scene, Hn, toward_p, skip)
            if s.button is None or s.button_new is None:
                s.button = s.button_new = None
        k_stations.append(s)
    numbers = sorted(pend["copies"])
    if trol is not None:
        left_over = core.place_tools(trol, numbers, grips, heading)
        if left_over:
            warnings.append("The operator: " + ", ".join(f"T{n}" for n in left_over) + " do not fit on the trolley "
                            "(it holds about 6 tools): they appear and go in the hand")
        for n, M in trol.slots.items():
            lying = bpy.data.objects.get(pend["trolley"][n])
            if lying is not None:
                lying.matrix_world = Matrix(M.tolist())
        _cradles(scene, trol, grips, shapes, pend, spindle)
    # the start spot and the way in
    if start_ob is not None:
        start_xy = np.array(start_ob.matrix_world.translation[:2])
    else:
        side = -1.0                                 # from the left: the trolley stands on the right
        cand = [stand_xy + np.array(PL.facing(heading)) * -2.4 + np.array(PL.left_of(heading)) * side * 1.4,
                stand_xy + np.array(PL.facing(heading)) * -2.6, stand_xy + np.array(PL.left_of(heading)) * side * 2.4]
        start_xy = None
        for p in cand:
            q = fl.nearest_free(p, core.BODY + core.WALK_MARGIN, 1.5)
            if q is not None and core.way_to(fl, q, stand_xy) is not None:
                start_xy = q
                break
    way = core.way_to(fl, start_xy, stand_xy) if start_xy is not None else None
    if way is None:
        way = [stand_xy]
        warnings.append("The operator: no clear way to the machine was found – it stands at the machine from the start "
                        "(move the start spot: Show the spots)")
    door = _door(scene, toward_p)
    op = core.Operator(_height(c), way[0], stand_xy, way, k_stations, trol, fl.z, door=door, name=NAME, floor=fl)
    op.plan()
    c["fr_op_stand"] = [float(stand_xy[0]), float(stand_xy[1]), fl.z, heading]
    c["fr_op_start"] = [float(way[0][0]), float(way[0][1]), fl.z]
    # key every frame
    ob = ensure_operator(scene, (float(way[0][0]), float(way[0][1]), fl.z), op.person.spec.heading)
    if ob.get(HOME) is None:
        ob[HOME] = [ob.location.x, ob.location.y, ob.location.z, ob.rotation_euler.z]
    body_mesh(ob)
    f_end = scene.frame_end
    frames = list(range(1, f_end + 1))
    times = [(f - 1) / fps for f in frames]
    rows = op.sample(times)
    person_rig.key_poses(ob, frames, [r[1] for r in rows], [r[0] for r in rows])
    ob.hide_render = ob.hide_viewport = False
    _key_carried(pend, frames, rows)
    big = [m for m in op.misses if m[4] and m[2] > 0.015]       # where it must be exact: on a tool, the handle
    if big:
        worst = max(big, key=lambda m: m[2])
        what = "the door's handle" if worst[3] in core.DOOR_MOVES else "the tool"
        warnings.append(f"The operator's hand stays {worst[2] * 100:.0f} cm short of {what} at {worst[0]:.1f} s "
                        f"({worst[3]}) – move the stand spot closer (Show the spots)")
    warnings += [f"The operator: {n}" for n in op.notes]
    c["fr_op_times"] = [float(x) for row in op.change_times() for x in row]
    scene.frame_set(1)
    apply_visible(scene)
    return warnings


ARMS = ("l_arm", "l_forearm", "l_hand", "r_arm", "r_forearm", "r_hand")


def body_mesh(ob):
    """The operator's body without its arms (a mesh of its own, ``clash.CLASH_MESH`` on the operator): what the
    clash check moves along its way. The arms reach into the machine on purpose; the tests check them posed."""
    from . import clash
    me = ob.data
    name = f"FR operator body {me.name}"
    sig = f"{me.name}:{len(me.vertices)}"
    old = ob.get(clash.CLASH_MESH)
    if isinstance(old, bpy.types.Mesh) and old.get("fr_sig") == sig:
        return old
    arm_idx = {g.index for g in ob.vertex_groups if g.name in ARMS}
    n = len(me.vertices)
    arm_w = np.zeros(n)
    other_w = np.zeros(n)
    for v in me.vertices:
        for g in v.groups:
            if g.group in arm_idx:
                arm_w[v.index] += g.weight
            else:
                other_w[v.index] += g.weight
    is_arm = arm_w > other_w
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    faces = [tuple(p.vertices) for p in me.polygons if not any(is_arm[i] for i in p.vertices)]
    used = sorted({i for f in faces for i in f})
    remap = {i: k for k, i in enumerate(used)}
    verts = co.reshape(-1, 3)[used]
    body = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    body.clear_geometry()
    body.from_pydata([tuple(v) for v in verts], [], [tuple(remap[i] for i in f) for f in faces])
    body["fr_sig"] = sig
    body.update()
    ob[clash.CLASH_MESH] = body
    return body


def _cradles(scene, trol, grips: dict, shapes: dict, pend: dict, spindle) -> None:
    """Two small rubber cradles under every tool lying on the trolley: one under its holder beyond the hand, one under
    its cutter's side (the fist round the holder then clears the trolley's top)."""
    boxes = []
    for n, M in trol.slots.items():
        if n not in shapes:
            src = bpy.data.objects.get(pend["copies"][n][1])
            if src is None:
                continue
            shapes[n] = _tool_shape(src, spindle)
        F, pts = shapes[n]
        zg = float((np.linalg.inv(F) @ grips[n][0])[2, 3])          # the grip along the axis (tip frame)
        lo, hi = float(pts[:, 2].min()), float(pts[:, 2].max())
        W = M @ F
        axis = W[:3, 2]
        across = np.cross(axis, (0.0, 0.0, 1.0))
        across /= np.linalg.norm(across) or 1.0
        for s in (min(hi - 0.004, zg + 0.052), max(lo + 0.006, zg - 0.062)):
            near = pts[np.abs(pts[:, 2] - s) < 0.005]
            if not len(near):
                continue
            wp = near @ W[:3, :3].T + W[:3, 3]
            centre = W[:3, :3] @ np.array((0.0, 0.0, s)) + W[:3, 3]
            boxes.append((centre[:2], axis[:2], across[:2], float(wp[:, 2].min()) - 0.0005))
    ob = next((o for o in bpy.data.objects if o.get(TAG) == "cradles"), None)
    if not boxes:
        if ob is not None:
            ob.hide_render = ob.hide_viewport = True
        return
    verts, faces = [], []
    for c, ax, ac, top in boxes:
        ax3 = np.array((ax[0], ax[1], 0.0))
        ax3 /= np.linalg.norm(ax3) or 1.0
        ac3 = np.array((ac[0], ac[1], 0.0))
        base = len(verts)
        for dz in (trol.top, top):
            for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.array((c[0], c[1], dz)) + ax3 * (0.005 * i) + ac3 * (0.02 * j)
                verts.append(tuple(p))
        faces += [(base, base + 3, base + 2, base + 1), (base + 4, base + 5, base + 6, base + 7),
                  (base, base + 1, base + 5, base + 4), (base + 1, base + 2, base + 6, base + 5),
                  (base + 2, base + 3, base + 7, base + 6), (base + 3, base, base + 4, base + 7)]
    me = bpy.data.meshes.new("FR tool cradles")
    me.from_pydata(verts, [], faces)
    me.materials.append(_rubber())
    if ob is None:
        ob = bpy.data.objects.new("FR tool cradles", me)
        ob[TAG] = "cradles"
        _collection(scene).objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    ob.hide_render = ob.hide_viewport = False


def _rubber():
    mat = bpy.data.materials.get("FR rubber cradle")
    if mat is None:
        mat = bpy.data.materials.new("FR rubber cradle")
        mat.diffuse_color = (0.03, 0.03, 0.035, 1.0)
        try:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            bsdf.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.8
        except Exception:
            pass
    return mat


def _height(c) -> float:
    try:
        return float(c.op_height)
    except (TypeError, ValueError):
        return 1.75


def _mesh_tris(ob) -> np.ndarray:
    me = ob.data
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    M = _np4(ob.matrix_world)
    pts = v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return pts[t.reshape(-1, 3)]


def _trolley_top(scene, ob, floor_z: float) -> float:
    """The height of the trolley's top: a ray down onto it near its middle."""
    dg = bpy.context.evaluated_depsgraph_get()
    c = ob.matrix_world.translation
    best = None
    for dx, dy in ((0.0, 0.0), (0.1, 0.05), (-0.1, -0.05)):
        o = Vector((c.x + dx, c.y + dy, floor_z + 2.0))
        ok, loc, _n, _i, hit, _m = scene.ray_cast(dg, o, Vector((0, 0, -1)), distance=2.5)
        if ok and getattr(hit, "original", hit) == ob:
            best = max(best or -1e9, loc.z)
    return float(best) if best is not None else floor_z + core.TROLLEY_SIZE[2]


def _key_carried(pend: dict, frames: list, rows: list) -> None:
    """Each tool copy in the hand: its world matrix at every frame it is carried (it has no parent)."""
    from . import animation
    for n, (name, _src) in pend["copies"].items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        ob.parent = None
        ob.rotation_mode = "QUATERNION"
        cb = animation._channelbag(ob, "OBJECT")
        loc_rows = [[], [], []]
        rot_rows = [[], [], [], []]
        prev = None
        last = None
        for f, r in zip(frames, rows):
            M = r[2].get(n)
            if M is None:
                continue
            loc, q, _s = Matrix(M.tolist()).decompose()
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q
            for i in range(3):
                loc_rows[i].append((f, float(loc[i]), "LINEAR", "AUTO"))
            for i in range(4):
                rot_rows[i].append((f, float(q[i]), "LINEAR", "AUTO"))
            last = M
        if last is None:
            continue
        for i in range(3):
            animation._write(cb, "location", i, person_rig._thin(loc_rows[i]))
        for i in range(4):
            animation._write(cb, "rotation_quaternion", i, person_rig._thin(rot_rows[i]))


def _hide_unused(scene) -> None:
    """No step had the person this Build: the operator and its trolley are hidden (they stay for the next one)."""
    for ob in [operator(scene), trolley(scene)] + [o for o in bpy.data.objects if o.get(TAG) == "cradles"]:
        if ob is not None:
            ob.hide_render = ob.hide_viewport = True


# ---------------------------------------------------------------------------
# shown or hidden for a shot, Clear keys, the clash check
# ---------------------------------------------------------------------------

def _visibility_curves(ob):
    ad = ob.animation_data
    if ad is None or ad.action is None:
        return []
    from . import machining
    return [fc for fc in machining._fcurves(ob) if fc.data_path in ("hide_render", "hide_viewport")]


def apply_visible(scene) -> None:
    """Show or hide the operator, its trolley and the tools it carries or laid down (``operator_visible``, saved with
    a shot). Hidden, the tools swap in the spindle as without anyone."""
    show = bool(getattr(scene.fresing, "operator_visible", True))
    obs = [operator(scene), trolley(scene)] + [o for o in bpy.data.objects if o.get(TAG) == "cradles"]
    obs += [o for o in bpy.data.objects if CARRY in o or ON_TROLLEY in o]
    for ob in obs:
        if ob is None:
            continue
        curves = _visibility_curves(ob)
        for fc in curves:
            fc.mute = not show
        if not show:
            ob.hide_render = ob.hide_viewport = True
        elif not curves and ob.get(TAG) in ("person", "trolley", "cradles"):
            used = ob.get(TAG) in ("trolley", "cradles") and trolley(scene) is not None
            if ob.get(TAG) == "person" and _built(ob) or used and _built(operator(scene)):
                ob.hide_render = ob.hide_viewport = False
    try:
        scene.frame_set(scene.frame_current)
    except Exception:
        pass


def _built(ob) -> bool:
    return ob is not None and ob.animation_data is not None and ob.animation_data.action is not None


def after_clear(scene) -> None:
    """Clear keys: the operator back where it stood, in its panel pose."""
    ob = operator(scene)
    if ob is None:
        return
    h = ob.get(HOME)
    if h is not None:
        ob.location = (h[0], h[1], h[2])
        ob.rotation_euler.z = h[3]
        del ob[HOME]
    if person_rig.rig_of(ob) is not None:
        person_rig.set_pose(ob, person_rig.figure(ob).from_angles("STANDING"))


def _clash_hook(scene):
    """The operator is checked as a body (standing, moved along its way); its trolley and tools are left out."""
    ob = operator(scene)
    add = [ob] if ob is not None and _built(ob) and not ob.hide_render else []
    leave = [o for o in (trolley(scene),) if o is not None]
    return add, leave


def register() -> None:
    from . import clash
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


def unregister() -> None:
    from . import clash
    while _clash_hook in clash.HOOKS:
        clash.HOOKS.remove(_clash_hook)


# ---------------------------------------------------------------------------
# the test model (tour set "operator", PC-check line "toolchange.person")
# ---------------------------------------------------------------------------

TEST_ANIM = "A person changes the tool"
TEST_PROGRAM = """(OPERATOR: T1 END MILL D10, T2 BALL MILL D8 - BT30, CHANGED BY HAND)
G21 G90 G94 G17 G54
T1 M6 G43 H1
S8000 M3
G0 X-40 Y-30 Z5
G1 Z-1 F2000
G1 X40 F1500
G0 Z40
M5
G0 X0 Y0 Z180
T2 M6 G43 H2
S9000 M3
G0 X-40 Y30 Z5
G1 Z-1 F2000
G1 X40 F1500
G0 Z60
M5
M30
"""


def _part(scene, name):
    hits = sorted((o for o in scene.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    if not hits:
        raise RuntimeError(f"the test model has no part '{name}'")
    return hits[0]


def set_up_test_model(scene, ngc_path: str):
    """The test mill on its cabinet (tests/data/test_mill_cabinet.step, tools/make_test_mill_cabinet.py) set up for
    one manual change from T1 to T2 that the operator does: X/Y/Z joints, the CNC machine, two BT30 tools, the door's
    slide joint "Door" (open at +530 mm), and an animation with the program (``TEST_PROGRAM`` written to
    ``ngc_path``) whose tool changes are done by the person. Returns the animation."""
    from . import logic, tools
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _part(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    t1 = _part(scene, "END MILL D10 BT30")
    gcode.use_tool(scene, t1)
    gcode.use_workpiece(scene, _part(scene, "STOCK 200x200x40"))
    if gcode.problem(scene):
        raise RuntimeError(f"the CNC set-up is not ready: {gcode.problem(scene)}")
    for name in ("FINISHED PART", "BALL MILL D6"):          # a shape on the stock, a spare tool on the head
        logic.set_hidden(_part(scene, name), True)
    end = tools.add_row(scene, "FLAT", 1)                    # T1: the model's own end mill in its holder
    tools.use_part(scene, end, t1)
    end.diameter, end.length, end.holder, end.holder_length = 0.01, 0.036, "BT30", 0.084
    end.gauge_length = 0.12                                  # tip to the flange's top (tools/make_test_mill_cabinet)
    ball = tools.add_row(scene, "BALL", 2)
    ball.diameter, ball.length, ball.holder, ball.holder_length = 0.008, 0.1, "BT30", 0.06
    door = _part(scene, "SLIDING DOOR")
    joints.create(scene, "SLIDE", [door], door.matrix_world.translation, Vector((1.0, 0.0, 0.0)), name="Door")
    c = settings(scene)
    c.op_door, c.op_door_open = "Door", 0.53
    with open(ngc_path, "w", encoding="utf-8") as fh:
        fh.write(TEST_PROGRAM)
    a = scene.fresing.animations.add()
    a.name, a.tail = TEST_ANIM, 0.0
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_tc_time, b.gcode_path = "FIT", 26.0, 1.0, False
    b.gcode_operator = "PERSON"
    b.gcode_file = ngc_path
    gcode.step_changed(scene, b)
    return a


def test_camera_points() -> np.ndarray:
    """Corners round the operator at the test mill (for a camera that frames them)."""
    return np.array([(x, y, z) for x in (-0.9, 1.0) for y in (-2.0, 0.4) for z in (0.0, 1.9)])


def check_test_model(scene) -> str:
    """After the Build of ``set_up_test_model``'s animation: the operator is built and keyed, the door opens, the hand
    carries the tool. Raises with a plain reason."""
    ob = operator(scene)
    if ob is None or not _built(ob):
        raise RuntimeError("there is no operator with keys (press Build & play)")
    if ob.hide_render and getattr(scene.fresing, "operator_visible", True):
        raise RuntimeError("the operator is hidden")
    j = scene.fresing.joints.get("Door")
    if j is None:
        raise RuntimeError("the door's joint is missing")
    carried = [o for o in scene.objects if CARRY in o]
    if len(carried) < 2:
        raise RuntimeError("the tool copies the operator carries are missing")
    return words(scene) or "the operator is built"


def words(scene) -> str:
    """'Operator: 6.3 s per change' after a Build with the person."""
    c = settings(scene)
    v = c.get("fr_op_times")
    if not v:
        return ""
    rows = [tuple(v[i:i + 3]) for i in range(0, len(v) - 2, 3)]
    return "The operator takes " + ", ".join(f"{r[2]:.1f} s" for r in rows[:4]) + " per change"
