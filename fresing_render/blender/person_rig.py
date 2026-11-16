"""The person's armature (task 0157; shared with task 0156): bones from ``core/props_detail.skeleton()``, the lofted
skin bound to them, poses and keys.

A person prop (``fr_prop = PERSON``, task 0155) stays the object that is placed and moved; ``ensure(ob)`` gives it a
rig: its mesh is made again in the rest pose (Standing) with one vertex group per bone and six hand shape keys, and an
armature object "FR rig <name>" becomes its child with an identity local matrix (it rides wherever the person goes).
An Armature modifier "FR rig" sits before the level-of-detail modifier "FR prop detail". The hands' shape keys
(``open_l/r``: fingers straight, ``grip_l/r``: a fist round a handle, ``point_l/r``: the index finger straight) are driven by
simple-expression drivers from the armature's custom properties ``fr_open_l`` … (works with scripts off; keys of the
fingers live on the armature with the bones).

API (figure space and poses: ``core/person_rig.py``)::

    arm = person_rig.ensure(ob)                    # the rig (made once; again after a height or clothes change)
    fig = person_rig.figure(ob)                    # core Figure of this person's height
    pose = fig.rest(); fig.arm_ik(pose, "r", wrist, elbow)
    person_rig.set_pose(ob, pose)                  # shows it now (no keys)
    person_rig.key_poses(ob, frames, poses, roots) # keys on the armature (and on the person object: roots =
                                                   # (x, y, z, heading) per frame; None: the object is not keyed)
    m = person_rig.bone_world(ob, "r_hand")        # a pose bone's world matrix (Blender's bone frame: Y along it)
    person_rig.remove(ob)                          # back to a still figure in its panel pose

The keys use ``animation._channelbag`` (tagged ``fr_anim``): Clear keys drops them like every other Build key.
"""

from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix

from ..core import person_rig as core
from ..core import props_detail as P
from ..core import surroundings as S

RIG_TAG = "fr_person_rig"           # on the armature: the person object's name
RIGGED = "fr_rigged"                # on the person object: 1 once it has a rig
MOD = "FR rig"
VERSION = 1                         # fr_rig_ver on the person object
FINGER_KEYS = ("open_l", "open_r", "grip_l", "grip_r", "point_l", "point_r")


# =============================================================================
# finding things
# =============================================================================


def rig_of(ob):
    """The person's armature (None: it has none)."""
    if ob is None:
        return None
    for ch in ob.children:
        if ch.type == "ARMATURE" and ch.get(RIG_TAG):
            return ch
    return None


def is_rigged(ob) -> bool:
    return rig_of(ob) is not None


def figure(ob) -> core.Figure:
    from . import props_scale
    return _figure(props_scale.person_settings(ob)["height"])


_FIGS: dict = {}


def _figure(height: float) -> core.Figure:
    key = round(float(height), 4)
    if key not in _FIGS:
        _FIGS[key] = core.Figure(key)
    return _FIGS[key]


# =============================================================================
# the mesh: both levels of detail in the rest pose, weights, hand shape keys
# =============================================================================

_ARRAYS: dict = {}                  # settings -> (verts, faces data, anchors, groups, keys) (shapes are pure maths)


def _variant(angles: dict, side: str, fingers: float, point: float) -> dict:
    d = dict(angles)
    d[f"{side}_fingers"] = fingers
    d[f"{side}_point"] = point
    return d


def _shape_lists(settings: dict, angles: dict) -> list:
    s = {k: v for k, v in settings.items() if k != "pose"}
    return [(1, S.prop_shapes("PERSON", P.DETAILED, pose=angles, **s)),
            (2, S.prop_shapes("PERSON", P.LIGHT, pose=angles, **s))]


def _verts_of(levels) -> np.ndarray:
    from . import surroundings as sur
    m = sur._Mesh()
    for _lv, shapes in levels:
        for sh in shapes:
            m.shape(sh, 0)
    return np.concatenate(m.verts) if m.verts else np.zeros((0, 3))


def _arrays(settings: dict):
    key = tuple(sorted((k, v) for k, v in settings.items() if k != "pose"))
    hit = _ARRAYS.get(key)
    if hit is not None:
        return hit
    from . import surroundings as sur
    rest = dict(P.POSES[core.REST_POSE])
    levels = _shape_lists(settings, rest)
    mats = sorted({sh.mat for _lv, shapes in levels for sh in shapes})
    index = {k: i for i, k in enumerate(mats)}
    m = sur._Mesh()
    lods, anchors, groups = [], [], []
    g = 0
    for lv, shapes in levels:
        for sh in shapes:
            v0, f0 = m.n, len(m.faces)
            m.shape(sh, index[sh.mat])
            nv = m.n - v0
            lods += [lv] * (len(m.faces) - f0)
            if not nv:
                continue
            pts = m.verts[-1]
            if isinstance(sh, S.Loft):
                rings = np.asarray(sh.rings, float)
                cen = rings.mean(axis=1)
                a = np.repeat(cen, rings.shape[1], axis=0)
                if nv > len(a):                       # the cap centres
                    a = np.concatenate([a, cen[:1], cen[-1:]])
                anchors.append(a[:nv])
            else:
                anchors.append(np.asarray(pts, float))
            groups += [g] * nv
            g += 1
    verts = np.concatenate(m.verts)
    fig = _figure(settings["height"])
    W = core.bind(fig, np.concatenate(anchors), np.asarray(groups))
    keys = {}
    for name in FINGER_KEYS:
        kind, side = name.split("_")
        fingers, point = {"open": (0.0, 0.0), "grip": (1.0, 0.0), "point": (0.95, 1.0)}[kind]
        keys[name] = _verts_of(_shape_lists(settings, _variant(rest, side, fingers, point)))
        if len(keys[name]) != len(verts):
            raise RuntimeError("the hand shapes do not match the rest mesh")
    out = (m, lods, mats, W, verts, keys)
    if len(_ARRAYS) > 8:
        _ARRAYS.clear()
    _ARRAYS[key] = out
    return out


def make_mesh(name: str, settings: dict) -> bpy.types.Mesh:
    """The person in its rest pose: both levels (``fr_lod``), a vertex group per bone, the hand shape keys."""
    from . import props_scale
    m, lods, mats, W, verts, keys = _arrays(settings)
    me = m.to_mesh(name)
    att = me.attributes.new(props_scale.LOD_ATTR, "INT", "FACE")
    att.data.foreach_set("value", np.asarray(lods, dtype=np.int32))
    for k in mats:
        me.materials.append(props_scale.material(k))
    me["fr_rest_pose"] = core.REST_POSE
    return me


def _weights(ob, settings: dict) -> None:
    _m, _l, _mats, W, _v, _k = _arrays(settings)
    ob.vertex_groups.clear()
    for j, b in enumerate(core.BONES):
        vg = ob.vertex_groups.new(name=b)
        col = W[:, j]
        idx = np.nonzero(col > 1e-6)[0]
        if not len(idx):
            continue
        vals = np.round(col[idx], 3)
        for v in np.unique(vals):                    # one call per weight value, not per point
            sel = idx[vals == v]
            vg.add([int(i) for i in sel], float(v), "REPLACE")


def _shape_keys(ob, settings: dict, arm) -> None:
    _m, _l, _mats, _W, verts, keys = _arrays(settings)
    me = ob.data
    if me.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    for name in FINGER_KEYS:
        kb = me.shape_keys.key_blocks.get(name) or ob.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", keys[name].astype(np.float32).ravel())
        kb.slider_min, kb.slider_max = 0.0, 1.0
        prop = "fr_" + name
        if prop not in arm:
            arm[prop] = 0.0
            arm.id_properties_ui(prop).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                              description="How far the hand's shape key is on (task 0157)")
        try:
            kb.driver_remove("value")
        except Exception:
            pass
        fc = kb.driver_add("value")
        drv = fc.driver
        drv.type = "SCRIPTED"
        drv.expression = "v"                        # a simple expression: works with scripts off
        var = drv.variables.new()
        var.name = "v"
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = arm
        var.targets[0].data_path = f'["{prop}"]'


# =============================================================================
# the armature
# =============================================================================


def _bones(arm, fig: core.Figure) -> None:
    """(Re)make the bones in edit mode at the rest pose of ``fig``. The mode switches get their own context (a timer,
    the test tour's build and a background run have no active object of their own)."""
    view = bpy.context.view_layer
    keep_active = view.objects.active
    if bpy.context.mode != "OBJECT" and keep_active is not None:
        try:
            with bpy.context.temp_override(active_object=keep_active, object=keep_active):
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    hidden = arm.hide_viewport
    arm.hide_viewport = False
    arm.hide_set(False)
    view.objects.active = arm
    over = dict(active_object=arm, object=arm, edit_object=arm, selected_objects=[arm],
                selected_editable_objects=[arm], view_layer=view)
    with bpy.context.temp_override(**over):
        bpy.ops.object.mode_set(mode="EDIT")
    try:
        eb = arm.data.edit_bones
        for b in list(eb):
            eb.remove(b)
        for name in core.BONES:
            head, B, ln = fig.rest_matrix(name)
            bone = eb.new(name)
            bone.head = tuple(head)
            bone.tail = tuple(head + B[:, 1] * ln)
            bone.align_roll(tuple(B[:, 2]))
            bone.use_deform = True
        for name in core.BONES:
            par = core.PARENT[name]
            if par:
                eb[name].parent = eb[par]
                eb[name].use_connect = False
    finally:
        with bpy.context.temp_override(**over):
            bpy.ops.object.mode_set(mode="OBJECT")
        view.objects.active = keep_active
        arm.hide_viewport = hidden
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"


def ensure(ob, rebuild: bool = False):
    """Give a person prop its rig (or make it again after its height or clothes changed). Returns the armature."""
    from . import props_scale
    from . import surroundings as sur
    if ob is None or ob.get(sur.PROP_TAG) != "PERSON":
        raise ValueError("not a person")
    arm = rig_of(ob)
    if arm is not None and not rebuild and int(ob.get("fr_rig_ver", 0)) >= VERSION:
        return arm
    settings = props_scale.person_settings(ob)
    fig = _figure(settings["height"])
    old = ob.data
    name = old.name if old is not None else ob.name
    if old is not None:
        old.name = name + " (old)"
    ob.data = make_mesh(name, settings)
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    if arm is None:
        data = bpy.data.armatures.new(f"FR rig {ob.name}")
        arm = bpy.data.objects.new(f"FR rig {ob.name}", data)
        for col in ob.users_collection:
            col.objects.link(arm)
        arm.parent = ob
        arm.matrix_parent_inverse = Matrix.Identity(4)
        arm.matrix_basis = Matrix.Identity(4)
        arm[RIG_TAG] = ob.name
        data.display_type = "STICK"
        arm.show_in_front = False
        arm.hide_render = True
        arm.hide_select = True
    _bones(arm, fig)
    _weights(ob, settings)
    _shape_keys(ob, settings, arm)
    mod = ob.modifiers.get(MOD)
    if mod is None:
        mod = ob.modifiers.new(MOD, "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_deform_preserve_volume = False
    props_scale.ensure_modifier(ob)
    i = list(ob.modifiers).index(mod)
    if i != 0:
        ob.modifiers.move(i, 0)
    ob[RIGGED] = 1
    ob["fr_rig_ver"] = VERSION
    ob.data["fr_rig_sig"] = repr(sorted((k, v) for k, v in settings.items() if k != "pose"))
    ob[props_scale.VER_KEY] = props_scale.VERSION
    arm.hide_viewport = True                    # the bones are not shown; the mesh still follows them
    set_pose(ob, fig.from_angles(settings["pose"]))
    return arm


def remove(ob) -> None:
    """Take the rig away: the person is a still figure in its panel pose again."""
    from . import props_scale
    arm = rig_of(ob)
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ob.modifiers.remove(mod)
    if arm is not None:
        data = arm.data
        bpy.data.objects.remove(arm)
        if data is not None and data.users == 0:
            bpy.data.armatures.remove(data)
    ob.vertex_groups.clear()
    for k in (RIGGED, "fr_rig_ver"):
        if k in ob:
            del ob[k]
    props_scale.rebuild(ob)


def rebuild(ob) -> None:
    """After a setting of a rigged person changed: the pose alone is set on the bones; height and clothes make the
    mesh and the bones again."""
    from . import props_scale
    settings = props_scale.person_settings(ob)
    me = ob.data
    sig = repr(sorted((k, v) for k, v in settings.items() if k != "pose"))
    if me is not None and me.get("fr_rig_sig") == sig and rig_of(ob) is not None:
        set_pose(ob, figure(ob).from_angles(settings["pose"]))
        return
    ensure(ob, rebuild=True)


# =============================================================================
# poses and keys
# =============================================================================


def finger_values(pose: core.Pose) -> dict:
    """The six hand shape keys for a pose's fingers (0 open … 1 fist; ``point``: the index finger straight)."""
    out = {}
    for s in core.SIDES:
        f = float(pose.fingers.get(s, core.FINGERS_REST))
        p = min(1.0, max(0.0, float(pose.point.get(s, 0.0))))
        rest = core.FINGERS_REST
        out[f"open_{s}"] = max(0.0, (rest - f) / rest) * (1 - p)
        out[f"grip_{s}"] = min(1.0, max(0.0, (f - rest) / (1.0 - rest))) * (1 - p)
        out[f"point_{s}"] = p
    return out


def set_pose(ob, pose: core.Pose) -> None:
    """Show a pose now (no keys)."""
    arm = rig_of(ob)
    if arm is None:
        return
    fig = figure(ob)
    for b in core.BONES:
        pb = arm.pose.bones.get(b)
        if pb is None:
            continue
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = fig.blender_quaternion(pose, b)
    arm.pose.bones["pelvis"].location = fig.blender_location(pose)
    for k, v in finger_values(pose).items():
        arm["fr_" + k] = float(v)
    arm.update_tag()
    ob.update_tag()


def _thin(rows: list, tol: float = 1e-6) -> list:
    """Drop the keys inside a stretch where the value stays the same (its ends are kept)."""
    if len(rows) <= 2:
        return rows
    out = [rows[0]]
    for i in range(1, len(rows) - 1):
        a, b, c = rows[i - 1][1], rows[i][1], rows[i + 1][1]
        if abs(b - a) < tol and abs(c - b) < tol:
            continue
        out.append(rows[i])
    out.append(rows[-1])
    return out


def key_poses(ob, frames: list, poses: list, roots: list | None = None) -> int:
    """Keys of a pose per frame on the armature (bones, pelvis, fingers) and, with ``roots`` ((x, y, z, heading) per
    frame), the person object's place and turn. Returns how many keys were written."""
    from . import animation
    arm = rig_of(ob)
    if arm is None:
        arm = ensure(ob)
    fig = figure(ob)
    cb = animation._channelbag(arm, "OBJECT")
    n = 0
    for b in core.BONES:
        qs = []
        prev = None
        for p in poses:
            q = np.asarray(fig.blender_quaternion(p, b))
            if prev is not None and float(np.dot(q, prev)) < 0:
                q = -q
            qs.append(q)
            prev = q
        path = f'pose.bones["{b}"].rotation_quaternion'
        for i in range(4):
            rows = _thin([(f, float(q[i]), "LINEAR", "AUTO") for f, q in zip(frames, qs)])
            animation._write(cb, path, i, rows)
            n += len(rows)
    locs = [fig.blender_location(p) for p in poses]
    for i in range(3):
        rows = _thin([(f, float(v[i]), "LINEAR", "AUTO") for f, v in zip(frames, locs)])
        animation._write(cb, 'pose.bones["pelvis"].location', i, rows)
        n += len(rows)
    fv = [finger_values(p) for p in poses]
    for k in FINGER_KEYS:
        rows = _thin([(f, float(v[k]), "LINEAR", "AUTO") for f, v in zip(frames, fv)])
        animation._write(cb, f'["fr_{k}"]', 0, rows)
        n += len(rows)
    if roots is not None:
        ocb = animation._channelbag(ob, "OBJECT")
        ob.rotation_mode = "XYZ"
        for i in range(3):
            rows = _thin([(f, float(r[i]), "LINEAR", "AUTO") for f, r in zip(frames, roots)])
            animation._write(ocb, "location", i, rows)
            n += len(rows)
        hs = np.unwrap([float(r[3]) for r in roots]) if roots else []
        rows = _thin([(f, float(h), "LINEAR", "AUTO") for f, h in zip(frames, hs)])
        animation._write(ocb, "rotation_euler", 2, rows)
        n += len(rows)
    return n


def bone_world(ob, bone: str) -> Matrix:
    """A pose bone's world matrix as it is now (head at its translation; Blender's bone frame, Y along the bone)."""
    arm = rig_of(ob)
    pb = arm.pose.bones[bone]
    return ob.matrix_world @ arm.matrix_parent_inverse @ arm.matrix_basis @ pb.matrix
