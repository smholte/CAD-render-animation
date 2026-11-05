"""Hydraulic and electric cylinders (task 0013).

How a cylinder is built in Blender (all native: constraints and one simple-expression driver per
telescopic stage, so playback, background renders and files with scripts disabled need no add-on code):

    barrel carrier (the part the barrel's pin is in: machine side)
     └─ cylinder frame   empty on the barrel pin; Z = pin axis, X towards the rod pin (CAD pose)
         └─ barrel       empty, Locked Track (turns about Z so X aims at the rod pin)
             ├─ the barrel's subassemblies (re-parented, CAD parent remembered)
             ├─ rod      empty, Copy Location from the rod pin: slides along X, its eye on the pin
             │    └─ the rod's subassemblies
             └─ stage i  empty (telescopic), a driver slides it a share of the rod's travel
    rod carrier (the part the rod's pin is in: the moving part)
     └─ rod pin          empty on the rod pin (taken in the barrel pin's plane)

Follow mode is just that: whatever moves the rod carrier (a joint, a stack, a coupling, a motor), the
cylinder goes along, both eyes on their pins. Drive mode: the stroke is what the owner sets, and the
joint that moves the rod pin (the arm's) turns to match – worked out exactly from the triangle pivot,
barrel pin, rod pin (``core.cylinders.Drive``). The joint keeps its own value (angle or distance): poses,
saved scenes, the render queue and model updates need nothing new; a "Move cylinder" animation step
writes the joint's value on every frame from the stroke.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from ..core import cylinders as C
from ..core.words import plural
from . import build, joints

KIND_FRAME, KIND_BARREL, KIND_ROD, KIND_PIN, KIND_STAGE = build.CYLINDER_KINDS
MOVERS = ("joint", KIND_BARREL, KIND_ROD, KIND_STAGE)       # empties that move what hangs on them
PROP = "fr_cylinder"


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def cylinders(scene):
    return scene.fresing.cylinders


def find(scene, name: str):
    return scene.fresing.cylinders.get(name)


def is_valid(c) -> bool:
    return (c.frame is not None and c.barrel_empty is not None and c.rod_empty is not None and c.pin is not None
            and c.barrel_empty.parent is c.frame and c.rod_empty.parent is c.barrel_empty)


def _objs(coll) -> list:
    return [r.obj for r in coll if r.obj is not None]


def barrel_objs(c) -> list:
    return _objs(c.barrel)


def rod_objs(c) -> list:
    return _objs(c.rod)


def stage_objs(c) -> list:
    return _objs(c.stages)


def members(c) -> list:
    return barrel_objs(c) + stage_objs(c) + rod_objs(c)


def empties(c) -> list:
    return [o for o in [c.rod_empty, *_objs(c.stage_empties), c.barrel_empty, c.frame, c.pin] if o is not None]


def cylinder_of_object(scene, ob):
    """The cylinder that moves ``ob`` directly (one of its barrel / rod / stage parts), or None."""
    p = ob.parent
    if p is None or p.get(build.PROP_KIND) not in (KIND_BARREL, KIND_ROD, KIND_STAGE):
        return None
    return find(scene, p.get(PROP, ""))


def cylinder_for_empty(scene, ob):
    if ob is None or ob.get(build.PROP_KIND) not in build.CYLINDER_KINDS:
        return None
    return find(scene, ob.get(PROP, ""))


def label(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name)


def unique_name(scene, base: str) -> str:
    names = {c.name for c in scene.fresing.cylinders}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def _update(scene=None) -> None:
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# lengths and the stroke
# ---------------------------------------------------------------------------

def length_now(c) -> float:
    """Pin-to-pin length as the view shows it now (m)."""
    if c.frame is None or c.pin is None:
        return 0.0
    return (c.frame.matrix_world.translation - c.pin.matrix_world.translation).length


def length_cad(c) -> float:
    """Pin-to-pin length in the CAD pose (where the rod empty sits on the barrel's X axis)."""
    return float(c.rod_empty.matrix_basis.translation.x) if c.rod_empty is not None else 0.0


def stroke_now(scene, c) -> float:
    """How far the rod is out (m): pin-to-pin length minus the closed length."""
    j, _reason = arm_joint(scene, c) if c.mode == "DRIVE" else (None, "")
    if j is not None:
        try:
            return drive(scene, c, j).length_at(joints.get_value(j)) - c.closed_length
        except RuntimeError:
            pass
    return length_now(c) - c.closed_length


def outside_stroke(c, stroke: float) -> bool:
    return stroke < -1e-5 or stroke > c.full_stroke + 1e-5


# ---------------------------------------------------------------------------
# drive mode: the arm's joint follows the stroke
# ---------------------------------------------------------------------------

def _mover_above(ob):
    """The nearest empty above ``ob`` (``ob`` itself included) that moves things: a joint's motion or a
    cylinder's barrel / rod / stage. None when nothing moves it."""
    p = ob
    seen = set()
    while p is not None and p.name not in seen:
        seen.add(p.name)
        if p.get(build.PROP_KIND) in MOVERS:
            return p
        p = p.parent
    return None


def arm_joint(scene, c):
    """(joint, '') – the joint the stroke drives: the one that moves the rod pin – or (None, reason)."""
    if not is_valid(c):
        return None, "This cylinder is broken (one of its markers was deleted): remove it and add it again"
    mover = _mover_above(c.pin.parent)
    if mover is None:
        return None, ("Nothing moves the rod's pin yet: add a joint for the arm (Add rotate joint above), "
                      "then the cylinder follows it")
    if mover.get(build.PROP_KIND) != "joint":
        other = find(scene, mover.get(PROP, ""))
        who = f"cylinder '{other.name}'" if other is not None else "another cylinder"
        return None, f"The rod's pin moves with {who}: this cylinder can only follow"
    j = next((x for x in scene.fresing.joints if x.motion is mover), None)
    if j is None or not joints.is_valid(j):
        return None, "The joint that moves the rod's pin is broken: remove it and add it again"
    if j.follows:
        return None, f"'{j.name}' follows '{j.follows}': it cannot be driven by the cylinder too"
    if joints.is_motor(j):
        return None, f"'{j.name}' is a motor: it cannot be driven by a cylinder"
    if _mover_above(c.frame.parent) is not _mover_above(j.frame.parent):
        return None, (f"The barrel's pin does not stay put relative to '{j.name}': drive mode needs the barrel's "
                      "pin on the part the arm turns on")
    _o, pin_axis = frame_axis(c)
    _jo, j_axis = joints.axis_world(j)
    if j.kind == "ROTATE" and not C.parallel(pin_axis, j_axis):
        return None, f"'{j.name}' does not turn about the pins' direction: drive mode needs that"
    if j.kind == "SLIDE" and abs(pin_axis.dot(j_axis)) > math.sin(C.PARALLEL_TOL):
        return None, f"'{j.name}' slides along the pins' direction: the cylinder cannot push it"
    return j, ""


def frame_axis(c) -> tuple[Vector, Vector]:
    m = c.frame.matrix_world
    return m.translation.copy(), (m.to_3x3() @ Vector((0, 0, 1))).normalized()


def drive(scene, c, j=None) -> C.Drive:
    """The stroke-to-joint geometry, read from the model (any pose: what it uses moves rigidly)."""
    if j is None:
        j, reason = arm_joint(scene, c)
        if j is None:
            raise RuntimeError(reason)
    fw = j.frame.matrix_world.inverted()
    mw = j.motion.matrix_world.inverted()
    b = fw @ c.frame.matrix_world.translation               # barrel pin: fixed relative to the joint's frame
    r0 = mw @ c.pin.matrix_world.translation                 # rod pin: fixed on the joint's motion (= frame at 0)
    try:
        return C.Drive(j.kind, tuple(b), tuple(r0))
    except ValueError as exc:
        raise RuntimeError(f"Drive mode is not possible: {exc}") from exc


def joint_value_for_stroke(scene, c, stroke: float, j=None) -> float:
    d = drive(scene, c, j)
    return d.value_for(c.closed_length + stroke)


def set_stroke(scene, c, stroke: float) -> float:
    """Move the arm so the rod is out by ``stroke`` (m), within the arm joint's limits. Returns the stroke."""
    j, reason = arm_joint(scene, c)
    if j is None:
        raise RuntimeError(reason)
    joints.set_value(j, joint_value_for_stroke(scene, c, stroke, j))
    _update(scene)
    return drive(scene, c, j).length_at(joints.get_value(j)) - c.closed_length


def sync_limits(scene, c) -> str:
    """Drive mode: the arm joint's limits become what the cylinder allows (closed … fully out).
    Returns a message for the owner ('' when nothing changed)."""
    if c.mode != "DRIVE":
        return ""
    j, _reason = arm_joint(scene, c)
    if j is None:
        return ""
    try:
        lo, hi = drive(scene, c, j).values_for_range(c.closed_length, c.closed_length + c.full_stroke)
    except RuntimeError:
        return ""
    if j.kind == "ROTATE":
        j.rot_min, j.rot_max = lo, hi
    else:
        j.slide_min, j.slide_max = lo, hi
    j.use_limits = True
    joints.apply_limits(j, joints._model_size(scene))
    lo_t, hi_t = (joints.to_display(j.kind, v) for v in (lo, hi))
    unit = joints.unit_label(j.kind)
    return f"'{j.name}' now stops where the cylinder does: {lo_t:.1f}{unit} … {hi_t:.1f}{unit}"


def set_mode(scene, c, mode: str) -> str:
    """Follow the arm, or drive it by the stroke. Returns a message; RuntimeError when not possible."""
    if mode == "DRIVE":
        j, reason = arm_joint(scene, c)
        if j is None:
            raise RuntimeError(reason)
        drive(scene, c, j)                                   # raises with the reason when not possible
    c["mode"] = 1 if mode == "DRIVE" else 0                  # (no update callback: it would call us again)
    return sync_limits(scene, c)


# ---------------------------------------------------------------------------
# picking: pins and what they sit on
# ---------------------------------------------------------------------------

def _inside(ob, objs) -> bool:
    """True when ``ob`` is one of ``objs`` or inside one of them (CAD tree or real parents)."""
    names = {o.name for o in objs}
    p = ob
    while p is not None:
        if p.name in names:
            return True
        p = build.logical_parent(p)
    return any(joints._moved_by(ob, o) for o in objs)


def _round_face_on(ob, point: Vector, axis: Vector, tol: float) -> bool:
    """True when ``ob``'s mesh has a round face (hole or shaft) on the line through ``point`` along ``axis``."""
    me = ob.data if ob.type == "MESH" else None
    if me is None or "fr_axes" not in me:
        return False
    axes = me["fr_axes"]
    mw = ob.matrix_world
    for k in range(0, len(axes) - 6, 7):
        o = mw @ Vector(axes[k:k + 3])
        d = (mw.to_3x3() @ Vector(axes[k + 3:k + 6]))
        if d.length < 1e-9 or not C.parallel(d, axis):
            continue
        d.normalize()
        off = (point - o) - d * (point - o).dot(d)
        if off.length < tol:
            return True
    return False


def find_carrier(scene, point: Vector, axis: Vector, exclude: list):
    """The part a pin sits in when the click hit the cylinder itself: parts around the pin point with a hole
    or shaft on the pin's axis, the biggest one first (the bracket or arm rather than the pin)."""
    size = joints._model_size(scene)
    tol = max(1e-4, size * 0.002)
    best, best_vol = None, -1.0
    for ob in build.iter_parts(scene):
        if ob.type != "MESH" or not ob.visible_get():
            continue
        corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = Vector(tuple(min(v[i] for v in corners) for i in range(3)))
        hi = Vector(tuple(max(v[i] for v in corners) for i in range(3)))
        if any(point[i] < lo[i] - tol or point[i] > hi[i] + tol for i in range(3)):
            continue
        if _inside(ob, exclude) or not _round_face_on(ob, point, axis, tol):
            continue
        mover = _mover_above(ob)
        if mover is not None and mover.get(build.PROP_KIND) != "joint":
            continue                                       # part of another cylinder: it moves itself
        vol = (hi - lo).x * (hi - lo).y * (hi - lo).z
        if vol > best_vol:
            best, best_vol = ob, vol
    return best


def check_parts(scene, barrel, rod, stages=(), cylinder=None) -> str:
    """'' when these can make a cylinder, else the reason."""
    if not barrel:
        return "Pick the barrel first: select it, then press Barrel"
    if not rod:
        return "Pick the rod first: select it, then press Rod"
    groups = (("barrel", barrel), ("rod", rod), ("stage", stages))
    seen = {}
    for role, objs in groups:
        for ob in objs:
            if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
                return f"{ob.name} is not part of the model"
            if build.logical_parent(ob) is None:
                return "The whole model cannot be part of a cylinder: pick its barrel and rod inside it"
            if ob.name in seen:
                return f"'{label(ob)}' is picked as {seen[ob.name]} and as {role}: pick it once"
            seen[ob.name] = role
            j = joints.joint_of_object(scene, ob)
            if j is not None:
                return (f"'{label(ob)}' moves with joint '{j.name}': remove it from that joint first "
                        "(the cylinder moves it now)")
            other = cylinder_of_object(scene, ob)
            if other is not None and (cylinder is None or other.name != cylinder.name):
                return f"'{label(ob)}' is already part of cylinder '{other.name}'"
    every = [ob for _r, objs in groups for ob in objs]
    for ob in every:
        for other in every:
            if other is not ob and joints._is_cad_ancestor(other, ob):
                return (f"'{label(ob)}' is inside '{label(other)}': pick the barrel and the rod as separate "
                        "subassemblies (or parts)")
    return ""


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------

def _frame_matrix(barrel_pin: Vector, rod_pin: Vector, pin_axis: Vector) -> Matrix:
    x, y, z = C.axis_frame(tuple(barrel_pin), tuple(rod_pin), tuple(pin_axis))
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = barrel_pin
    return m


def _place(ob, parent, world: Matrix, parent_world: Matrix | None = None) -> None:
    """Parent ``ob`` and put it at ``world``. A parent made a moment ago has no world matrix yet (Blender
    works it out at the next update): pass ``parent_world`` for it."""
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    pw = parent_world if parent_world is not None else (parent.matrix_world if parent is not None
                                                        else Matrix.Identity(4))
    ob.matrix_basis = pw.inverted() @ world


def _front_along(objs, frame_world: Matrix) -> float:
    """How far along the cylinder's axis the parts reach (the front end of a telescopic stage)."""
    inv = frame_world.inverted()
    tree_parts = _parts_of(objs)
    best = -math.inf
    for ob in tree_parts:
        for corner in ob.bound_box:
            best = max(best, (inv @ (ob.matrix_world @ Vector(corner))).x)
    return best


def _parts_of(objs) -> list:
    from . import logic
    tree = logic.Tree()
    out = []
    for ob in objs:
        if ob.get(build.PROP_KIND) == "part":
            out.append(ob)
        out += [d for d in tree.descendants(ob) if d.get(build.PROP_KIND) == "part"]
    return out


def _triangles(objs, frame_world: Matrix):
    """The parts' triangles in the cylinder's frame (numpy (n, 3, 3), metres)."""
    import numpy as np
    inv = np.array(frame_world.inverted())
    out = []
    for ob in _parts_of(objs):
        me = ob.data if ob.type == "MESH" else None
        if me is None or not len(me.polygons):
            continue
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        idx = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", idx)
        m = inv @ np.array(ob.matrix_world)
        pts = co @ m[:3, :3].T + m[:3, 3]
        out.append(pts[idx.reshape(-1, 3)])
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def _stage_driver(stage, frame, pin, share: float, length: float) -> None:
    """A telescopic stage slides ``share`` of the rod's travel: ``d * share - share * cad length`` with ``d`` the
    distance between the pins (a simple expression: no Python needed)."""
    for p, i in (("location", 0),):
        try:
            stage.driver_remove(p, i)
        except TypeError:
            pass
    fc = stage.driver_add("location", 0)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "d"
    var.type = "LOC_DIFF"
    var.targets[0].id = frame
    var.targets[1].id = pin
    drv.expression = f"d * {share!r} - {share * length!r}"


def _new_empty(name, kind, collection, size, display, cyl_name):
    ob = joints._new_empty(name, kind, collection, size, display)
    ob[PROP] = cyl_name
    return ob


def _build(scene, name: str, barrel, rod, stages, frame_world: Matrix, pin_world: Matrix, barrel_carrier,
           rod_carrier):
    """Make the empties and hang the parts on them (call in the CAD pose). Returns the new item."""
    s = scene.fresing
    show = s.show_joints
    size = joints._model_size(scene) * 0.02
    collection = (barrel_carrier.users_collection[0] if barrel_carrier.users_collection
                  else barrel[0].users_collection[0])
    length = (pin_world.translation - frame_world.translation).length
    frame = _new_empty(f"Cylinder {name}", KIND_FRAME, collection, size, "SPHERE", name)
    _place(frame, barrel_carrier, frame_world)
    pin = _new_empty(f"Cylinder {name} (rod pin)", KIND_PIN, collection, size, "SPHERE", name)
    _place(pin, rod_carrier, pin_world)
    aim = _new_empty(f"Cylinder {name} (barrel)", KIND_BARREL, collection, size * 3, "SINGLE_ARROW", name)
    _place(aim, frame, frame_world, frame_world)
    rod_e = _new_empty(f"Cylinder {name} (rod)", KIND_ROD, collection, size * 2, "PLAIN_AXES", name)
    _place(rod_e, aim, frame_world @ Matrix.Translation((length, 0.0, 0.0)), frame_world)
    con = aim.constraints.new("LOCKED_TRACK")
    con.name = "Aim at the rod pin"
    con.target = pin
    con.track_axis = "TRACK_X"
    con.lock_axis = "LOCK_Z"
    con = rod_e.constraints.new("COPY_LOCATION")
    con.name = "Eye on the rod pin"
    con.target = pin
    order = sorted(stages, key=lambda ob: _front_along([ob], frame_world))
    stage_es = []
    for i, (ob, share) in enumerate(zip(order, C.stage_shares(len(order)))):
        e = _new_empty(f"Cylinder {name} (stage {i + 1})", KIND_STAGE, collection, size, "PLAIN_AXES", name)
        _place(e, aim, frame_world, frame_world)
        _stage_driver(e, frame, pin, share, length)
        stage_es.append(e)
    for ob in (aim, rod_e, *stage_es):
        try:
            ob.hide_set(True)
        except RuntimeError:
            pass
    for ob in (frame, pin):
        try:
            ob.hide_set(not show)
        except RuntimeError:
            pass
    _update(scene)
    rod_world = frame_world @ Matrix.Translation((length, 0.0, 0.0))
    c = s.cylinders.add()
    c["name"] = name
    c["_old_name"] = name
    c.frame, c.pin, c.barrel_empty, c.rod_empty = frame, pin, aim, rod_e
    for ob in barrel:
        joints._attach(ob, aim, frame_world)
        c.barrel.add().obj = ob
    for ob in rod:
        joints._attach(ob, rod_e, rod_world)
        c.rod.add().obj = ob
    for ob, e in zip(order, stage_es):
        joints._attach(ob, e, frame_world)
        c.stages.add().obj = ob
        c.stage_empties.add().obj = e
    s.cylinders_index = len(s.cylinders) - 1
    return c


def create(scene, barrel, rod, barrel_pin, rod_pin, name: str = "", stages=(), barrel_carrier=None,
           rod_carrier=None):
    """A new cylinder. ``barrel_pin`` / ``rod_pin``: (origin, direction, clicked object) in the current pose,
    world space – the clicks on the two pins. Returns (cylinder, notes); RuntimeError with the reason."""
    barrel = [ob for ob in barrel if ob is not None]
    rod = [ob for ob in rod if ob is not None]
    stages = [ob for ob in stages if ob is not None]
    reason = check_parts(scene, barrel, rod, stages)
    if reason:
        raise RuntimeError(reason)
    parts = barrel + rod + stages
    (ob_, db_, ref_b), (or_, dr_, ref_r) = barrel_pin, rod_pin
    local_b = joints._local_axis(ref_b, ob_, db_)
    local_r = joints._local_axis(ref_r, or_, dr_)
    notes = []
    build.ensure_bases(scene)
    with joints.cad_pose(scene):
        wb, wr = joints._world_axis(ref_b, local_b), joints._world_axis(ref_r, local_r)
        pb, nb = wb.translation.copy(), (wb.to_3x3() @ Vector((0, 0, 1))).normalized()
        pr, nr = wr.translation.copy(), (wr.to_3x3() @ Vector((0, 0, 1))).normalized()

        def carrier(given, ref, point, axis, role):
            if given is not None:
                ob = given
            elif ref is not None and not _inside(ref, parts):
                ob = ref
            else:
                ob = find_carrier(scene, point, axis, parts)
            if ob is None and role == "barrel":
                ob = build.logical_parent(barrel[0])
                notes.append(f"Could not tell which part holds the barrel's pin: it sits on '{label(ob)}' "
                             "(change it under Set-up)")
            if ob is None:
                raise RuntimeError("Could not tell which part holds the rod's pin: click the pin, or the hole in "
                                   "the part the rod is fixed to (not the rod's own eye)")
            if _inside(ob, parts):
                raise RuntimeError(f"The {role}'s pin cannot sit on '{label(ob)}': that is part of the cylinder")
            return ob

        bc = carrier(barrel_carrier, ref_b, pb, nb, "barrel")
        rc = carrier(rod_carrier, ref_r, pr, nb, "rod")
        angle = math.degrees(C.angle_between_lines(nb, nr))
        if angle > math.degrees(C.PARALLEL_TOL):
            notes.append(f"The two pins are {angle:.1f}° out of parallel: the cylinder follows, but its eyes "
                         "may not sit square on the pins")
        # the pins' centres in the barrel's mid-plane (where its eye is), wherever along the pin it was clicked
        mn, mx = build.world_bounds(_parts_of(barrel))
        mid = Vector(((mn + mx) / 2).tolist())
        pb = pb + nb * (mid - pb).dot(nb)
        pr = Vector(C.into_plane(tuple(pr), tuple(pb), tuple(nb)))
        if (pr - pb).length < 1e-3:
            raise RuntimeError("Both pins are at the same place: click the barrel's pin, then the rod's pin")
        fw = _frame_matrix(pb, pr, nb)
        pw = fw.copy()
        pw.translation = pr
        name = unique_name(scene, name or f"{label(barrel[0])} cylinder")
        c = _build(scene, name, barrel, rod, stages, fw, pw, bc, rc)
        estimate(scene, c)
    if _mover_above(rc) is _mover_above(bc):
        notes.append("Nothing moves it yet: add a joint for the arm, the cylinder then follows it")
    return c, notes


def estimate(scene, c) -> bool:
    """Closed length and full stroke read from the parts (call in the CAD pose). True when measured."""
    fw = c.frame.matrix_world.copy()
    t = C.estimate_travel(_triangles(barrel_objs(c) + stage_objs(c), fw), _triangles(rod_objs(c), fw),
                          length_cad(c))
    c["closed_length"] = t.closed
    c["full_stroke"] = t.full
    c["measured"] = t.measured
    return t.measured


def remove(scene, c) -> None:
    """Remove a cylinder: its parts go back to their CAD place."""
    s = scene.fresing
    name = c.name
    with joints.cad_pose(scene):
        c = find(scene, name)
        for ob in members(c):
            joints._detach(ob)
        for ob in empties(c):
            bpy.data.objects.remove(ob, do_unlink=True)
        idx = next(i for i, x in enumerate(s.cylinders) if x.name == name)
        s.cylinders.remove(idx)
    s.cylinders_index = min(s.cylinders_index, len(s.cylinders) - 1)


def rename(scene, c, old: str) -> None:
    for ob in empties(c):
        ob[PROP] = c.name
    for ob, suffix in ((c.frame, ""), (c.pin, " (rod pin)"), (c.barrel_empty, " (barrel)"), (c.rod_empty, " (rod)")):
        if ob is not None:
            ob.name = f"Cylinder {c.name}{suffix}"
    for i, r in enumerate(c.stage_empties):
        if r.obj is not None:
            r.obj.name = f"Cylinder {c.name} (stage {i + 1})"
    for anim in scene.fresing.animations:
        for b in anim.blocks:
            if b.cylinder == old:
                b.cylinder = c.name


def show(scene, visible: bool) -> None:
    for c in scene.fresing.cylinders:
        for ob in (c.frame, c.pin):
            if ob is not None:
                try:
                    ob.hide_set(not visible)
                except RuntimeError:
                    pass


# ---------------------------------------------------------------------------
# changes and model updates: a cylinder as plain data
# ---------------------------------------------------------------------------

def to_spec(c) -> dict:
    """A cylinder as plain data (parts by their stable ID). Call in the CAD pose."""
    def uids(objs):
        return [ob.get(build.PROP_UID) for ob in objs]
    return {
        "name": c.name, "mode": c.mode, "closed": c.closed_length, "full": c.full_stroke,
        "measured": bool(c.measured),
        "barrel": uids(barrel_objs(c)), "rod": uids(rod_objs(c)), "stages": uids(stage_objs(c)),
        "barrel_carrier": c.frame.parent.get(build.PROP_UID) if c.frame.parent is not None else None,
        "rod_carrier": c.pin.parent.get(build.PROP_UID) if c.pin.parent is not None else None,
        "frame_local": build.mat_to_list(c.frame.matrix_basis),
        "pin_local": build.mat_to_list(c.pin.matrix_basis),
        "frame_world": build.mat_to_list(c.frame.matrix_world),
        "pin_world": build.mat_to_list(c.pin.matrix_world),
    }


def _dissolve(scene, c) -> None:
    """Take a cylinder apart, no CAD pose of its own (the caller is in it)."""
    s = scene.fresing
    for ob in members(c):
        joints._detach(ob)
    for ob in empties(c):
        bpy.data.objects.remove(ob, do_unlink=True)
    idx = next(i for i, x in enumerate(s.cylinders) if x == c)
    s.cylinders.remove(idx)


def _belongs(c, root) -> bool:
    if root is None:
        return True
    objs = members(c) + [o for o in (c.frame.parent if c.frame else None, c.pin.parent if c.pin else None)
                         if o is not None]
    return any(joints._root(o) is root for o in objs)


def before_model_update(scene, root=None) -> list[dict]:
    """Model update: the cylinders of the model under ``root`` come apart (parts back in the CAD tree);
    their specs are returned to build them again on the new revision."""
    specs = []
    with joints.cad_pose(scene):
        for name in [c.name for c in scene.fresing.cylinders]:
            c = find(scene, name)
            if not is_valid(c) or not _belongs(c, root):
                continue
            specs.append(to_spec(c))
            _dissolve(scene, c)
        scene.fresing.cylinders_index = max(0, min(scene.fresing.cylinders_index, len(scene.fresing.cylinders) - 1))
    return specs


def rebuild_from_specs(scene, specs: list[dict], by_uid: dict) -> list[str]:
    """Build the cylinders again on the new revision (after the joints). Returns notes for the report."""
    notes = []
    for sp in specs:
        def objs(key):
            return [o for o in (by_uid.get(u) for u in sp.get(key, [])) if o is not None]
        barrel, rod, stages = objs("barrel"), objs("rod"), objs("stages")
        if not barrel or not rod:
            notes.append(f"Cylinder '{sp['name']}' removed: its barrel or rod is no longer in the model")
            continue
        lost = len(sp["barrel"]) + len(sp["rod"]) + len(sp.get("stages", [])) - len(barrel) - len(rod) - len(stages)
        if lost:
            notes.append(f"Cylinder '{sp['name']}': {plural(lost, 'part')} no longer in the model")
        try:
            with joints.cad_pose(scene):
                bc = by_uid.get(sp["barrel_carrier"]) if sp.get("barrel_carrier") else None
                rc = by_uid.get(sp["rod_carrier"]) if sp.get("rod_carrier") else None
                fw = (bc.matrix_world @ build.list_to_mat(sp["frame_local"]) if bc is not None
                      else build.list_to_mat(sp["frame_world"]))
                pw = (rc.matrix_world @ build.list_to_mat(sp["pin_local"]) if rc is not None
                      else build.list_to_mat(sp["pin_world"]))
                if bc is None:
                    bc = build.logical_parent(barrel[0])
                    notes.append(f"Cylinder '{sp['name']}': the part its barrel's pin was in is gone; it now sits "
                                 f"on '{label(bc)}'")
                if rc is None:
                    notes.append(f"Cylinder '{sp['name']}' removed: the part its rod's pin was in is gone")
                    continue
                reason = check_parts(scene, barrel, rod, stages)
                if reason:
                    raise RuntimeError(reason)
                # the pins may have moved in the new revision: aim the frame at the rod pin again
                axis = fw.to_3x3() @ Vector((0, 0, 1))
                pr = Vector(C.into_plane(tuple(pw.translation), tuple(fw.translation), tuple(axis)))
                fw = _frame_matrix(fw.translation.copy(), pr, axis)
                pw = fw.copy()
                pw.translation = pr
                name = unique_name(scene, sp["name"])
                c = _build(scene, name, barrel, rod, stages, fw, pw, bc, rc)
                c["closed_length"] = sp["closed"]
                c["full_stroke"] = sp["full"]
                c["measured"] = sp.get("measured", False)
        except RuntimeError as exc:
            notes.append(f"Cylinder '{sp['name']}' could not be rebuilt: {exc}")
            continue
        if sp.get("mode") == "DRIVE":
            try:
                set_mode(scene, find(scene, name), "DRIVE")
            except RuntimeError as exc:
                notes.append(f"Cylinder '{sp['name']}' follows its arm now: {exc}")
    return notes


def rebuild(scene, c, **changes) -> object:
    """Build a cylinder again with other parts or pin carriers (``barrel``, ``rod``, ``stages``,
    ``barrel_carrier``, ``rod_carrier``: objects). Keeps its name, mode and lengths."""
    name = c.name
    with joints.cad_pose(scene):
        c = find(scene, name)
        sp = to_spec(c)
        barrel = changes.get("barrel", barrel_objs(c))
        rod = changes.get("rod", rod_objs(c))
        stages = changes.get("stages", stage_objs(c))
        bc = changes.get("barrel_carrier", c.frame.parent)
        rc = changes.get("rod_carrier", c.pin.parent)
        fw, pw = c.frame.matrix_world.copy(), c.pin.matrix_world.copy()
        idx = next(i for i, x in enumerate(scene.fresing.cylinders) if x.name == name)
        # check before taking it apart (its own parts may be picked again)
        reason = check_parts(scene, barrel, rod, stages, cylinder=c)
        if reason:
            raise RuntimeError(reason)
        for ob, role in ((bc, "barrel"), (rc, "rod")):
            if ob is None or _inside(ob, barrel + rod + stages):
                raise RuntimeError(f"The {role}'s pin cannot sit on '{label(ob) if ob else '-'}': pick a part "
                                   "outside the cylinder")
        _dissolve(scene, c)
        c = _build(scene, name, barrel, rod, stages, fw, pw, bc, rc)
        c["closed_length"] = sp["closed"]
        c["full_stroke"] = sp["full"]
        c["measured"] = sp["measured"]
        n = len(scene.fresing.cylinders)
        scene.fresing.cylinders.move(n - 1, idx)
        scene.fresing.cylinders_index = idx
    c = find(scene, name)
    if sp["mode"] == "DRIVE":
        try:
            set_mode(scene, c, "DRIVE")
        except RuntimeError:
            pass
    return c
