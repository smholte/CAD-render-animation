"""Trail lines (task 0073): the path a point of a part takes, drawn as a tube.

At every Build the point is read in the world at every frame (and at a G-code program's corners between frames, as the
clash check reads, ``clash.sample_times``), with milling and coolant skipping their per-frame work. The points go into a
mesh of edges with the frame of each point (``fr_frame``); a Geometry Nodes modifier turns the edges into a tube, the
way the toolpath does (``gcode._node_group``), and with "Draw as it goes" leaves out the points after the current
frame. The tube glows in its colour without lighting the scene (``gcode.no_light``, as task 0071 did for the toolpath).
The line is kept with the project: a still or a queued video of a built animation shows it.
"""

from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import build

TAG = "fr_trail"                  # on the trail objects, meshes and materials
KIND = "trail"                    # fr_kind of a trail object
NODE_GROUP = "FR trail"
COLLECTION = "Trail lines"


def settings(scene):
    return scene.fresing.trails


def active(scene):
    s = scene.fresing
    return s.trails[s.trails_index] if 0 <= s.trails_index < len(s.trails) else None


def label(t) -> str:
    if t.name:
        return t.name
    if t.part is not None:
        return t.part.get(build.PROP_NAME, t.part.name)
    return "Trail"


def add(scene, part, point: str = "ORIGIN", local=None):
    s = scene.fresing
    t = s.trails.add()
    t["_busy"] = True
    t.part = part
    t.part_uid = part.get(build.PROP_UID, "") if part is not None else ""
    t.point = point
    if local is not None:
        t.local = tuple(local)
    if point == "TIP" and part is not None and tip_of(scene, part) is None:
        t.point = "ORIGIN"
    from . import animation
    a = animation.active(scene)
    if a is not None:
        t.animation = a.name
    t.color = PALETTE[(len(s.trails) - 1) % len(PALETTE)]
    del t["_busy"]
    s.trails_index = len(s.trails) - 1
    return t


PALETTE = ((1.0, 0.35, 0.05), (0.1, 0.8, 0.25), (0.95, 0.1, 0.6), (0.1, 0.55, 1.0), (0.95, 0.85, 0.05))


def remove(scene, index: int) -> None:
    s = scene.fresing
    if not 0 <= index < len(s.trails):
        return
    _remove_object(s.trails[index])
    s.trails.remove(index)
    s.trails_index = max(0, min(s.trails_index, len(s.trails) - 1))


def _remove_object(t) -> None:
    ob = t.obj
    if ob is None:
        return
    me = ob.data
    name, ng_name = ob.get("fr_trail_mat"), ob.get("fr_trail_ng")
    t.obj = None
    bpy.data.objects.remove(ob)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    mat = bpy.data.materials.get(name) if isinstance(name, str) else None
    if mat is not None and mat.users == 0:
        bpy.data.materials.remove(mat)
    ng = bpy.data.node_groups.get(ng_name) if isinstance(ng_name, str) else None
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)


# ---------------------------------------------------------------------------
# the point
# ---------------------------------------------------------------------------

def tip_of(scene, part):
    """The tool tip in the part's own space: a milling bit's tip, or the tip the CNC tool list keeps; else None."""
    from . import machining
    try:
        for it, ob in machining.bits(scene):
            if ob is part:
                return Vector(machining._tip_of(it))
    except Exception:
        pass
    if part.get("fr_tip") is not None:
        return Vector(tuple(part["fr_tip"]))
    try:
        from . import gcode
        if gcode.settings(scene).tool is part:
            return Vector(gcode._rest_tip(part)[0])
    except Exception:
        pass
    return None


def local_point(scene, t) -> Vector:
    if t.point == "CLICKED":
        return Vector(t.local)
    if t.point == "TIP" and t.part is not None:
        tip = tip_of(scene, t.part)
        if tip is not None:
            return tip
    return Vector((0.0, 0.0, 0.0))


def point_text(scene, t) -> str:
    if t.point == "TIP" and t.part is not None and tip_of(scene, t.part) is None:
        return "This part is no milling bit or CNC tool: its origin is used"
    return ""


# ---------------------------------------------------------------------------
# reading the path
# ---------------------------------------------------------------------------

def _used(scene, anim) -> list:
    out = []
    for t in scene.fresing.trails:
        if t.part is None or t.part.name not in scene.objects:
            continue
        if t.animation and anim is not None and t.animation != anim.name:
            continue
        out.append(t)
    return out


def sample(scene, items: list) -> list:
    """[(times, points n x 3 in metres, world)] for every trail of ``items``: read at every frame and corner."""
    from . import clash
    times = clash.sample_times(scene)
    locs = [local_point(scene, t) for t in items]
    pts = [np.empty((len(times), 3)) for _ in items]
    keep = (scene.frame_current, scene.frame_subframe)
    needed = {t.part for t in items}
    shy = [o for o in scene.objects if not o.hide_viewport and o not in needed and o.get(TAG) is None
           and any(m.type == "NODES" for m in getattr(o, "modifiers", ()))]
    for o in shy:                               # only drawn (toolpath, chips, coolant): not worked out at every frame
        o.hide_viewport = True
    try:
        with clash._Guard():
            for k, tm in enumerate(times):
                clash._set_time(scene, tm)
                for i, t in enumerate(items):
                    pts[i][k] = tuple(t.part.matrix_world @ locs[i])
    finally:
        for o in shy:
            o.hide_viewport = False
        scene.frame_set(keep[0], subframe=keep[1])
    return [(np.array(times), p) for p in pts]


def update_all(scene, anim) -> list[str]:
    """Called at the end of every Build: the trail lines of this animation are read again; the others are hidden.
    Returns warnings."""
    s = scene.fresing
    if not len(s.trails):
        return []
    warnings = []
    items = [t for t in _used(scene, anim) if t.enabled]
    for t in s.trails:
        if t not in items and t.obj is not None:
            _show(t, False)
    for t in s.trails:
        if t.part is None:
            warnings.append(f"Trail line '{label(t)}': its part is gone (pick it again in 6 Animation > Trail lines)")
    if not items:
        return warnings
    for t, (times, pts) in zip(items, sample(scene, items)):
        _write(scene, t, times, pts)
    return warnings


def _write(scene, t, times, pts) -> None:
    """Make (or replace) the trail's mesh: the points, the edges between them, the frame of each point."""
    keep = np.ones(len(pts), dtype=bool)                 # drop points where it stands still (fewer to draw)
    if len(pts) > 2:
        d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        keep[1:-1] = (d[:-1] > 1e-7) | (d[1:] > 1e-7)
    pts, times = pts[keep], times[keep]
    n = len(pts)
    me = bpy.data.meshes.new(f"FR trail {label(t)}")
    me[TAG] = True
    me.vertices.add(n)
    me.vertices.foreach_set("co", pts.astype(np.float32).reshape(-1))
    if n > 1:
        ed = np.stack([np.arange(n - 1), np.arange(1, n)], axis=1).astype(np.int32)
        me.edges.add(n - 1)
        me.edges.foreach_set("vertices", ed.reshape(-1))
    me.update()
    a = me.attributes.new("fr_frame", "FLOAT", "POINT")
    a.data.foreach_set("value", times.astype(np.float32))
    ob = t.obj
    if ob is None or ob.name not in bpy.data.objects:
        ob = bpy.data.objects.new(f"Trail {label(t)}", me)
        ob[TAG] = True
        ob[build.PROP_KIND] = KIND
        ob.hide_select = True
        t["_busy"] = True
        t.obj = ob
        del t["_busy"]
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    ob.parent = None
    ob.matrix_world = Matrix.Identity(4)
    t["_busy"] = True
    t.count = n
    del t["_busy"]
    style(scene, t)


def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _show(t, on: bool, render: bool = True) -> None:
    ob = t.obj
    if ob is None:
        return
    if ob.hide_viewport == on:
        ob.hide_viewport = not on
    want = not (on and render)
    if ob.hide_render != want:
        ob.hide_render = want


# ---------------------------------------------------------------------------
# the look: a tube that glows in its colour
# ---------------------------------------------------------------------------

def material(t) -> bpy.types.Material:
    from . import gcode
    name = f"FR trail {label(t)}"
    ob = t.obj
    mat = None
    if ob is not None:
        mat = ob.get("fr_trail_mat")
        mat = bpy.data.materials.get(mat) if isinstance(mat, str) else None
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat[TAG] = True
        try:
            mat.use_nodes = True
        except Exception:
            pass
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 1.5
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        if ob is not None:
            ob["fr_trail_mat"] = mat.name
    rgb = tuple(t.color)
    em = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeEmission"), None)
    if em is not None and tuple(em.inputs["Color"].default_value)[:3] != rgb:
        em.inputs["Color"].default_value = (*rgb, 1.0)
    if tuple(mat.diffuse_color)[:3] != rgb:
        mat.diffuse_color = (*rgb, 1.0)
    gcode.no_light(mat)
    return mat


def node_group(t, ob) -> bpy.types.NodeTree:
    """The trail's own node tree: edges -> a tube; with Grow the points after the current frame are left out.
    Its settings sit in the tree's nodes (named "radius", "grow", "material"), so each trail has its own."""
    name = ob.get("fr_trail_ng")
    ng = bpy.data.node_groups.get(name) if isinstance(name, str) else None
    if ng is not None and ng.get(TAG) == 1:
        return ng
    ng = bpy.data.node_groups.new(f"{NODE_GROUP} {label(t)}", "GeometryNodeTree")
    ng[TAG] = 1
    ob["fr_trail_ng"] = ng.name
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    frame_attr = n.new("GeometryNodeInputNamedAttribute")
    frame_attr.data_type = "FLOAT"
    frame_attr.inputs["Name"].default_value = "fr_frame"
    now = n.new("GeometryNodeInputSceneTime")
    later = n.new("FunctionNodeCompare")
    later.data_type = "FLOAT"
    later.operation = "GREATER_THAN"
    both = n.new("FunctionNodeBooleanMath")
    both.operation = "AND"
    both.name = "grow"                              # its second input: Draw as it goes
    delete = n.new("GeometryNodeDeleteGeometry")
    delete.domain = "POINT"
    to_curve = n.new("GeometryNodeMeshToCurve")
    circle = n.new("GeometryNodeCurvePrimitiveCircle")
    circle.name = "radius"
    circle.inputs["Resolution"].default_value = 8
    to_mesh = n.new("GeometryNodeCurveToMesh")
    setmat = n.new("GeometryNodeSetMaterial")
    setmat.name = "material"
    L.new(frame_attr.outputs["Attribute"], later.inputs[0])
    L.new(now.outputs["Frame"], later.inputs[1])
    L.new(later.outputs["Result"], both.inputs[0])
    L.new(gin.outputs["Geometry"], delete.inputs["Geometry"])
    L.new(both.outputs[0], delete.inputs["Selection"])
    L.new(delete.outputs["Geometry"], to_curve.inputs["Mesh"])
    L.new(to_curve.outputs["Curve"], to_mesh.inputs["Curve"])
    L.new(circle.outputs["Curve"], to_mesh.inputs["Profile Curve"])
    if "Fill Caps" in to_mesh.inputs:
        to_mesh.inputs["Fill Caps"].default_value = True
    L.new(to_mesh.outputs["Mesh"], setmat.inputs["Geometry"])
    L.new(setmat.outputs["Geometry"], gout.inputs["Geometry"])
    for k, node in enumerate((gin, delete, to_curve, to_mesh, setmat, gout)):
        node.location = (k * 220, 0)
    for k, node in enumerate((frame_attr, now, later, both, circle)):
        node.location = (k * 200, -300)
    return ng


def _put(sock, value) -> bool:
    cur = sock.default_value
    if isinstance(value, bpy.types.ID):
        same = cur is not None and cur == value
    else:
        same = abs(float(cur) - float(value)) < 1e-9
    if not same:
        sock.default_value = value
    return not same


def style(scene, t) -> None:
    """Colour, thickness, grow, in renders, on/off of the trail's object (as the trail's settings say)."""
    ob = t.obj
    if ob is None or ob.name not in bpy.data.objects:
        return
    mod = ob.modifiers.get("Trail")
    if mod is None:
        mod = ob.modifiers.new("Trail", "NODES")
    ng = node_group(t, ob)
    if mod.node_group is not ng:
        mod.node_group = ng
    mat = material(t)
    changed = _put(ng.nodes["radius"].inputs["Radius"], max(1e-5, float(t.thickness) / 2.0))
    changed |= _put(ng.nodes["grow"].inputs[1], bool(t.grow))
    changed |= _put(ng.nodes["material"].inputs["Material"], mat)
    built = scene.fresing.anim_baked
    mine = bool(built) and (not t.animation or t.animation == built)     # only over the motion it was read from
    _show(t, bool(t.enabled) and mine, bool(t.in_render))
    if changed:
        ob.update_tag()


def after_clear(scene) -> None:
    """'Clear keys': the parts are back where they were, so the lines (read along the motion) are hidden."""
    for t in scene.fresing.trails:
        _show(t, False)


def frame_points(scene, t):
    """(frames, points) of the trail's mesh: for tests and the PC check."""
    ob = t.obj
    if ob is None:
        return np.zeros(0), np.zeros((0, 3))
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    fr = np.empty(n, np.float32)
    me.attributes["fr_frame"].data.foreach_get("value", fr)
    return fr.astype(float), co.reshape(-1, 3).astype(float)


def after_model_update(scene, by_uid_new: dict, mapping: dict) -> list[str]:
    notes = []
    for t in scene.fresing.trails:
        if not t.part_uid:
            continue
        uid = mapping.get(t.part_uid, t.part_uid)
        ob = by_uid_new.get(t.part_uid) or next((o for o in scene.objects if o.get(build.PROP_UID) == uid), None)
        t["_busy"] = True
        t.part = ob
        t.part_uid = ob.get(build.PROP_UID, "") if ob is not None else ""
        del t["_busy"]
        if ob is None:
            notes.append(f"Trail line '{label(t)}': its part is gone in the new revision")
    return notes
