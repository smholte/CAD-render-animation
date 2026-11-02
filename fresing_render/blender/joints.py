"""Joints: rotate or slide subassemblies about an axis.

How a joint is built in Blender (all native, so playback and background renders
need no add-on code):

    base (the subassembly it sits on)
     └─ joint frame   empty on the axis, local Z = axis direction, never moves
         └─ joint motion  empty that turns about / slides along its Z
              └─ moving subassemblies (re-parented, CAD parent remembered)

The joint value is a custom property ``fr_value`` on the motion empty (radians
or metres) with min/max from the joint limits; a driver copies it into the
motion's Z rotation or Z location. Animation keys go on ``fr_value``.

Joints whose base is moved by another joint follow it: that gives chains
(a trolley on a luffing boom). Changes to the joint structure are made in the
CAD pose (every joint at 0, no free moves) and the pose is restored after.
"""

from __future__ import annotations

import contextlib
import math

import bpy
from mathutils import Matrix, Vector

from . import build

VALUE = "fr_value"
EPS = 1e-7
# Matrices are stored in single precision by Blender: differences below this are rounding,
# not a move (1e-5 m = 0.01 mm; 1e-5 in a rotation entry = 0.0006 degrees).
MOVE_EPS = 1e-5


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------

def to_display(kind: str, value: float) -> float:
    """Internal value (rad / m) -> what the user reads (degrees / mm)."""
    return math.degrees(value) if kind == "ROTATE" else value * 1000.0


def from_display(kind: str, value: float) -> float:
    return math.radians(value) if kind == "ROTATE" else value / 1000.0


def unit_label(kind: str) -> str:
    return "°" if kind == "ROTATE" else "mm"


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def joints(scene):
    return scene.fresing.joints


def find(scene, name: str):
    return scene.fresing.joints.get(name)


def is_valid(j) -> bool:
    return j.frame is not None and j.motion is not None and j.motion.parent is j.frame


def joint_of_object(scene, ob):
    """The joint that moves ``ob`` directly (ob is one of its members), or None."""
    p = ob.parent
    if p is None or p.get(build.PROP_KIND) != "joint":
        return None
    for j in scene.fresing.joints:
        if j.motion is p:
            return j
    return None


def joint_for_empty(scene, ob):
    for j in scene.fresing.joints:
        if ob is j.frame or ob is j.motion:
            return j
    return None


def members(j) -> list:
    return [m.obj for m in j.members if m.obj is not None]


# ---------------------------------------------------------------------------
# values and limits
# ---------------------------------------------------------------------------

def get_value(j) -> float:
    if j.motion is None:
        return 0.0
    return float(j.motion.get(VALUE, 0.0))


def limits(j) -> tuple[float, float]:
    if not j.use_limits:
        return (-math.radians(3600), math.radians(3600)) if j.kind == "ROTATE" else (-1000.0, 1000.0)
    lo, hi = (j.rot_min, j.rot_max) if j.kind == "ROTATE" else (j.slide_min, j.slide_max)
    return (min(lo, hi), max(lo, hi))


def clamp(j, value: float) -> float:
    lo, hi = limits(j)
    return min(max(value, lo), hi)


def set_value(j, value: float, use_limits: bool = True) -> float:
    if j.motion is None:
        return 0.0
    v = clamp(j, value) if use_limits else value
    j.motion[VALUE] = float(v)
    j.motion.update_tag()
    return v


def apply_limits(j, model_size: float = 10.0) -> None:
    """Push the joint limits into the slider of the value property."""
    if j.motion is None:
        return
    lo, hi = limits(j)
    if j.kind == "ROTATE":
        soft = (lo, hi) if j.use_limits else (-math.pi, math.pi)
        subtype = "ANGLE"
    else:
        reach = max(0.1, model_size)
        soft = (lo, hi) if j.use_limits else (-reach, reach)
        subtype = "DISTANCE"
    ui = j.motion.id_properties_ui(VALUE)
    ui.update(min=lo, max=hi, soft_min=soft[0], soft_max=soft[1], subtype=subtype,
              step=100 if j.kind == "ROTATE" else 1, precision=1 if j.kind == "ROTATE" else 1,
              description="Joint position (drag, or type a number)")
    cur = get_value(j)
    if j.use_limits and (cur < lo or cur > hi):
        set_value(j, cur)


# ---------------------------------------------------------------------------
# the CAD pose (all joints at 0, no free moves)
# ---------------------------------------------------------------------------

def model_objects(scene):
    return [ob for ob in scene.objects if ob.get(build.PROP_KIND) in build.MODEL_KINDS]


def _is_identity(m: Matrix) -> bool:
    ident = Matrix.Identity(4)
    return all(abs(m[r][c] - ident[r][c]) < MOVE_EPS for r in range(4) for c in range(4))


def _same(a: Matrix, b: Matrix) -> bool:
    return all(abs(a[r][c] - b[r][c]) < MOVE_EPS for r in range(3) for c in range(4))


def free_moves(scene) -> dict:
    """{object name: delta} for every object moved away from its rest position."""
    out = {}
    for ob in model_objects(scene):
        rest = build.rest_basis(ob)
        basis = ob.matrix_basis
        if _same(basis, rest):              # cheap test first: almost nothing is moved
            continue
        try:
            delta = rest.inverted() @ basis
        except ValueError:
            continue
        if not _is_identity(delta):
            out[ob.name] = delta
    return out


def apply_free_moves(scene, deltas: dict, reset_others: bool = True) -> None:
    for ob in model_objects(scene):
        d = deltas.get(ob.name)
        if d is not None:
            ob.matrix_basis = build.rest_basis(ob) @ d
        elif reset_others:
            rest = build.rest_basis(ob)
            if not _same(ob.matrix_basis, rest):
                ob.matrix_basis = rest


def _update(scene) -> None:
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass


@contextlib.contextmanager
def cad_pose(scene):
    """Temporarily put the model in its CAD pose; restore joint values and free moves after."""
    from . import animation
    animation.clear_keys(scene)            # baked keys would fight the pose; rebuilt on demand
    values = {j.name: get_value(j) for j in scene.fresing.joints}
    deltas = free_moves(scene)
    for j in scene.fresing.joints:
        set_value(j, 0.0, use_limits=False)      # through set_value: tags the driver for an update
    apply_free_moves(scene, {}, reset_others=True)
    _update(scene)
    try:
        yield
    finally:
        apply_free_moves(scene, {n: d for n, d in deltas.items() if n in bpy.data.objects}, reset_others=False)
        for j in scene.fresing.joints:
            if j.name in values and j.motion is not None:
                set_value(j, values[j.name], use_limits=False)
        _update(scene)


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

def axis_matrix(origin: Vector, direction: Vector) -> Matrix:
    d = Vector(direction).normalized()
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(Vector(origin)) @ rot


def _parent_world(ob) -> Matrix:
    if ob.parent is None:
        return Matrix.Identity(4)
    return ob.parent.matrix_world @ ob.matrix_parent_inverse


def _set_world(ob, world: Matrix, parent_world: Matrix | None = None) -> None:
    pw = _parent_world(ob) if parent_world is None else parent_world
    ob.matrix_basis = pw.inverted() @ world


def _moved_by(ob, motion) -> bool:
    """True when ``motion`` is above ``ob`` in the real (Blender) parent chain."""
    p = ob
    while p is not None:
        if p is motion:
            return True
        p = p.parent
    return False


def _model_size(scene) -> float:
    s = scene.fresing
    if s.bounds_valid:
        return max(0.1, (Vector(s.bounds_max) - Vector(s.bounds_min)).length)
    return 5.0


def _new_empty(name: str, kind: str, collection, size: float, display: str) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = display
    ob.empty_display_size = size
    ob[build.PROP_KIND] = kind
    ob.lock_location = (True,) * 3
    ob.lock_rotation = (True,) * 3
    ob.lock_scale = (True,) * 3
    collection.objects.link(ob)
    return ob


def _add_driver(motion, kind: str) -> None:
    path, index = ("rotation_euler", 2) if kind == "ROTATE" else ("location", 2)
    for p, i in (("rotation_euler", 2), ("location", 2)):
        try:
            motion.driver_remove(p, i)
        except TypeError:
            pass
    fc = motion.driver_add(path, index)
    drv = fc.driver
    drv.type = "AVERAGE"                    # no Python expression: works with scripts disabled
    var = drv.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = motion
    var.targets[0].data_path = f'["{VALUE}"]'


def _attach(ob, motion, motion_world: Matrix) -> None:
    """Make ``ob`` move with ``motion`` (call in the CAD pose)."""
    world = ob.matrix_world.copy()
    if not isinstance(ob.get(build.PROP_CAD_PARENT), bpy.types.Object):
        if ob.parent is None or ob.parent.get(build.PROP_KIND) in build.JOINT_KINDS:
            raise RuntimeError(f"{ob.name} has no CAD parent")
        ob[build.PROP_CAD_PARENT] = ob.parent
    ob.parent = motion
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = motion_world.inverted() @ world
    build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)


def _detach(ob) -> None:
    """Put ``ob`` back under its CAD parent at its CAD place (call in the CAD pose)."""
    cad_parent = ob.get(build.PROP_CAD_PARENT)
    if not isinstance(cad_parent, bpy.types.Object):
        return
    ob.parent = cad_parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = build.cad_basis(ob)
    build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
    del ob[build.PROP_CAD_PARENT]


def unique_name(scene, base: str) -> str:
    names = {j.name for j in scene.fresing.joints}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def check_members(scene, objs, base, joint=None) -> str:
    """'' if ``objs`` can be moved by a joint sitting on ``base``, else a reason."""
    if not objs:
        return "Select the subassemblies that should move"
    for ob in objs:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            return f"{ob.name} is not part of the model"
        if build.logical_parent(ob) is None:
            return "The whole model cannot be a moving part; select subassemblies inside it"
        if base is not None and (base is ob or _moved_by(base, ob)):
            return f"'{ob.get(build.PROP_NAME, ob.name)}' cannot move itself: it carries the base of this joint"
    if joint is not None and base is not None and joint.motion is not None and _moved_by(base, joint.motion):
        return "A joint cannot sit on something it moves"
    return ""


def default_base(objs):
    """The CAD parent shared by the moving objects (the first one's parent when they differ)."""
    first = build.logical_parent(objs[0])
    return first


# ---------------------------------------------------------------------------
# public operations
# ---------------------------------------------------------------------------

def create(scene, kind: str, objs, origin, direction, name: str = "", base=None, ref=None):
    """New joint moving ``objs`` about/along the axis. Returns the joint item.

    ``origin``/``direction`` are world space in the current pose; they are stored relative
    to ``ref`` (the part that was clicked, default the base), so picking works with other
    joints moved or the model turned.
    """
    objs = [ob for ob in objs if ob is not None]
    # members inside other members move with them anyway
    objs = [ob for ob in objs if not any(o is not ob and _is_cad_ancestor(o, ob) for o in objs)]
    base = base or default_base(objs)
    reason = check_members(scene, objs, base)
    if reason:
        raise RuntimeError(reason)
    s = scene.fresing
    build.ensure_bases(scene)
    label = objs[0].get(build.PROP_NAME, objs[0].name)
    name = unique_name(scene, name or f"{label} {'rotate' if kind == 'ROTATE' else 'slide'}")
    size = _model_size(scene) * 0.08
    collection = (base.users_collection[0] if base is not None and base.users_collection
                  else objs[0].users_collection[0])
    ref = ref if ref is not None else base
    local = _local_axis(ref, origin, direction)
    with cad_pose(scene):
        for ob in objs:                         # an object is moved directly by one joint only
            other = joint_of_object(scene, ob)
            if other is not None:
                _remove_member(other, ob)
                _detach(ob)
        _update(scene)
        frame = _new_empty(f"Joint {name}", "joint_frame", collection, size, "SINGLE_ARROW")
        motion = _new_empty(f"Joint {name} (motion)", "joint", collection, size * 0.4, "PLAIN_AXES")
        frame.parent = base
        frame.matrix_parent_inverse = Matrix.Identity(4)
        world = _world_axis(ref, local)
        base_world = base.matrix_world.copy() if base is not None else Matrix.Identity(4)
        frame.matrix_basis = base_world.inverted() @ world
        motion.parent = frame
        motion.matrix_parent_inverse = Matrix.Identity(4)
        motion.matrix_basis = Matrix.Identity(4)
        motion.rotation_mode = "XYZ"
        motion[VALUE] = 0.0
        _add_driver(motion, kind)
        try:
            motion.hide_set(True)
        except RuntimeError:
            pass
        j = s.joints.add()
        j["name"] = name                        # no rename callback on creation
        j["_old_name"] = name
        j.kind = kind
        j.frame = frame
        j.motion = motion
        frame["fr_joint"] = name
        motion["fr_joint"] = name
        for ob in objs:
            _attach(ob, motion, world)
            m = j.members.add()
            m.obj = ob
    sync_base(j)
    apply_limits(j, _model_size(scene))
    s.joints_index = len(s.joints) - 1
    return j


def _local_axis(ref, origin, direction) -> Matrix:
    m = axis_matrix(origin, direction)
    return ref.matrix_world.inverted() @ m if ref is not None else m


def _world_axis(ref, local: Matrix) -> Matrix:
    m = ref.matrix_world @ local if ref is not None else local.copy()
    # keep it a clean rigid frame (no scale/shear from the reference)
    loc, rot, _scale = m.decompose()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def _is_cad_ancestor(a, b) -> bool:
    p = build.logical_parent(b)
    while p is not None:
        if p is a:
            return True
        p = build.logical_parent(p)
    return False


def _remove_member(j, ob) -> None:
    for i in reversed(range(len(j.members))):
        if j.members[i].obj is ob or j.members[i].obj is None:
            j.members.remove(i)


def add_members(scene, j, objs) -> int:
    objs = [ob for ob in objs if ob is not None and ob not in members(j)]
    objs = [ob for ob in objs if not any(_is_cad_ancestor(o, ob) for o in members(j) + objs if o is not ob)]
    reason = check_members(scene, objs, j.frame.parent if j.frame else None, j)
    if reason:
        raise RuntimeError(reason)
    with cad_pose(scene):
        for ob in objs:
            other = joint_of_object(scene, ob)
            if other is not None:
                _remove_member(other, ob)
                _detach(ob)
        _update(scene)
        world = j.motion.matrix_world.copy()
        for ob in objs:
            _attach(ob, j.motion, world)
            j.members.add().obj = ob
    return len(objs)


def remove_members(scene, j, objs) -> int:
    objs = [ob for ob in objs if ob in members(j)]
    with cad_pose(scene):
        for ob in objs:
            _remove_member(j, ob)
            _detach(ob)
    return len(objs)


def remove(scene, j) -> None:
    s = scene.fresing
    with cad_pose(scene):
        for ob in members(j):
            _detach(ob)
        for ob in (j.motion, j.frame):
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        idx = next(i for i, x in enumerate(s.joints) if x == j)
        s.joints.remove(idx)
    s.joints_index = min(s.joints_index, len(s.joints) - 1)


def sync_base(j) -> None:
    """Show the frame's parent in the 'Sits on' field without triggering a move."""
    from . import props
    key = ("base", j.as_pointer())
    props._BUSY.add(key)
    try:
        j.base = j.frame.parent if j.frame is not None else None
    finally:
        props._BUSY.discard(key)


def set_base(scene, j, base) -> None:
    """Make the joint sit on (move with) another subassembly."""
    reason = check_members(scene, members(j), base, j)
    if reason:
        raise RuntimeError(reason)
    with cad_pose(scene):
        world = j.frame.matrix_world.copy()
        j.frame.parent = base
        j.frame.matrix_parent_inverse = Matrix.Identity(4)
        _set_world(j.frame, world, base.matrix_world if base is not None else Matrix.Identity(4))
    sync_base(j)


def axis_world(j) -> tuple[Vector, Vector]:
    m = j.frame.matrix_world
    return m.translation.copy(), (m.to_3x3() @ Vector((0, 0, 1))).normalized()


def set_axis(scene, j, origin, direction, ref=None) -> None:
    """Move the joint axis (world space, current pose); the moving parts stay where they are."""
    ref = ref if ref is not None else j.frame.parent
    local = _local_axis(ref, origin, direction)
    with cad_pose(scene):
        worlds = {ob.name: ob.matrix_world.copy() for ob in members(j)}
        new_world = _world_axis(ref, local)
        _set_world(j.frame, new_world)
        for ob in members(j):
            ob.matrix_basis = new_world.inverted() @ worlds[ob.name]
            build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)


def flip(scene, j) -> None:
    o, d = axis_world(j)
    set_axis(scene, j, o, -d)


def set_kind(scene, j, kind: str) -> None:
    with cad_pose(scene):
        j.kind = kind
        _add_driver(j.motion, kind)
        j.motion.matrix_basis = Matrix.Identity(4)
    set_value(j, 0.0, use_limits=False)
    apply_limits(j, _model_size(scene))


def rename(scene, j, old: str) -> None:
    for ob in (j.frame, j.motion):
        if ob is not None:
            ob["fr_joint"] = j.name
    if j.frame is not None:
        j.frame.name = f"Joint {j.name}"
    if j.motion is not None:
        j.motion.name = f"Joint {j.name} (motion)"
    for pose in scene.fresing.poses:
        for v in pose.joints:
            if v.joint == old:
                v.joint = j.name
    for anim in scene.fresing.animations:
        for b in anim.blocks:
            if b.joint == old:
                b.joint = j.name


def reset_all(scene) -> None:
    for j in scene.fresing.joints:
        set_value(j, 0.0, use_limits=False)


# ---------------------------------------------------------------------------
# picking an axis on the model
# ---------------------------------------------------------------------------

def axis_from_hit(ob, polygon_index: int, hit: Vector, normal: Vector):
    """Axis under a click: the round face's axis when the click hit a hole/shaft, else the face normal.

    Returns (origin, direction, description); all world space.
    """
    me = ob.data if ob is not None and ob.type == "MESH" else None
    if me is not None and "fr_axes" in me and "fr_axis_faces" in me:
        faces = me["fr_axis_faces"]
        axes = me["fr_axes"]
        for k in range(0, len(faces), 3):
            start, count, idx = faces[k], faces[k + 1], faces[k + 2]
            if start <= polygon_index < start + count:
                a = axes[idx * 7: idx * 7 + 7]
                mw = ob.matrix_world
                o = mw @ Vector(a[0:3])
                d = (mw.to_3x3() @ Vector(a[3:6])).normalized()
                o = o + d * (Vector(hit) - o).dot(d)      # put the axis point where the user clicked
                r = a[6] * mw.to_scale()[0]
                desc = f"round face Ø{r * 2000:.1f} mm" if r > 0 else "round face"
                return o, d, desc
    return Vector(hit), Vector(normal).normalized(), "flat face (axis at right angles to it)"


# ---------------------------------------------------------------------------
# re-import support: joints as plain data
# ---------------------------------------------------------------------------

def to_specs(scene, values: dict | None = None, only=None) -> list[dict]:
    """Joints as plain data (object references by stable part ID). Call in the CAD pose."""
    out = []
    for j in scene.fresing.joints:
        if not is_valid(j) or (only is not None and j.name not in only):
            continue
        base = j.frame.parent
        out.append({
            "world": build.mat_to_list(j.frame.matrix_world),
            "name": j.name, "kind": j.kind, "value": (values or {}).get(j.name, get_value(j)),
            "use_limits": j.use_limits, "rot_min": j.rot_min, "rot_max": j.rot_max,
            "slide_min": j.slide_min, "slide_max": j.slide_max,
            "base": base.get(build.PROP_UID) if base is not None else None,
            "base_local": build.mat_to_list(j.frame.matrix_basis),
            "members": [ob.get(build.PROP_UID) for ob in members(j)],
        })
    return out


def _root(ob):
    while True:
        p = build.logical_parent(ob)
        if p is None:
            return ob
        ob = p


def dissolve_all(scene, root=None) -> list[dict]:
    """Remove the joints (of the model under ``root``, or all) and return them as specs."""
    s = scene.fresing

    def belongs(j) -> bool:
        if root is None:
            return True
        objs = members(j) + ([j.frame.parent] if j.frame is not None and j.frame.parent is not None else [])
        return any(_root(o) is root for o in objs)

    chosen = {j.name for j in s.joints if belongs(j)}
    values = {j.name: get_value(j) for j in s.joints}
    with cad_pose(scene):
        specs = to_specs(scene, values, only=chosen)
        for i in reversed(range(len(s.joints))):
            j = s.joints[i]
            if j.name not in chosen:
                continue
            for ob in members(j):
                _detach(ob)
            for ob in (j.motion, j.frame):
                if ob is not None:
                    bpy.data.objects.remove(ob, do_unlink=True)
            s.joints.remove(i)
        s.joints_index = min(s.joints_index, max(0, len(s.joints) - 1))
    return specs


def rebuild_from_specs(scene, specs: list[dict], by_uid: dict) -> list[str]:
    """Re-create joints on a new model revision. Returns warnings."""
    warnings = []
    values: dict[str, float] = {}
    for sp in specs:
        objs = [by_uid.get(u) for u in sp["members"]]
        missing = sum(1 for o in objs if o is None)
        objs = [o for o in objs if o is not None]
        if not objs:
            warnings.append(f"Joint '{sp['name']}' removed: its moving parts are no longer in the model")
            continue
        if missing:
            warnings.append(f"Joint '{sp['name']}': {missing} moving part(s) no longer in the model")
        base = by_uid.get(sp["base"]) if sp["base"] else None
        if sp["base"] and base is None:
            warnings.append(f"Joint '{sp['name']}': the part it sat on is gone; it now sits on its CAD parent")
            base = None
        if base is None:
            base = default_base(objs)
            world = build.list_to_mat(sp["world"])     # where the axis was (the model did not move)
        else:
            world = base.matrix_world @ build.list_to_mat(sp["base_local"])
        origin = world.translation
        direction = world.to_3x3() @ Vector((0, 0, 1))
        try:
            j = create(scene, sp["kind"], objs, origin, direction, name=sp["name"], base=base)
        except RuntimeError as exc:
            warnings.append(f"Joint '{sp['name']}' could not be rebuilt: {exc}")
            continue
        if j.name != sp["name"]:
            j["name"] = sp["name"]
            j["_old_name"] = sp["name"]
            rename(scene, j, sp["name"])
        j.use_limits = sp["use_limits"]
        j.rot_min, j.rot_max = sp["rot_min"], sp["rot_max"]
        j.slide_min, j.slide_max = sp["slide_min"], sp["slide_max"]
        apply_limits(j, _model_size(scene))
        values[j.name] = sp["value"]
    for name, v in values.items():          # values last: every joint was built in the CAD pose
        jj = find(scene, name)
        if jj is not None:
            set_value(jj, v)
    return warnings
