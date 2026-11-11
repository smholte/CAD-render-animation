"""Coolant in Blender (task 0042): the settings live in 4 Motion > CNC machine > Coolant
(``scene.fresing.coolant``), when it flows on each Run G-code program step (``gcode_coolant``).

* **The coolant space**: an empty "FR coolant" on the spindle head (a child of the spindle joint's frame, or of the
  tool's parent), at the tip of the tool in the spindle, +Z up the tool. It does not turn with the spindle. Everything
  the coolant draws hangs under it, so it goes wherever the head goes.
* **The build** (``prepare`` before the steps, ``record`` per G-code step) writes on that empty: the coolant spans
  (``fr_spans``: start, end, kind in frames), the cutting spans (``fr_cut``), the tip height and radius of every tool
  (``fr_tools``), gravity in its own space; and the keys of the wet level (``fr_wet``, read by the wet sheen).
* **Every frame** (a frame handler, also in the queue's background renders) draws the liquid for that frame from the
  frame number alone (``core/coolant.py``): the jets (mesh "FR coolant jets"), the drops (points "FR coolant drops",
  instanced as little spheres by Geometry Nodes) and, for "Automatic" nozzles, the hoses ("FR coolant hoses"),
  bent for the tool in the spindle. Same frame, same picture, whatever was shown before.
* **Wet sheen**: the block, the table and the vise carry ``fr_coolant_wet`` (how wet they get, 0 … 1); their
  materials get a few nodes that read it and multiply it with the wet level (a plain driver on the empty's
  ``fr_wet``: works with scripts off). Parts without the property look exactly as before. Chips get the wet level
  as a point attribute (``fr_wet``) and fly less far while coolant flows (``core/chips.py``).
"""

from __future__ import annotations

import threading

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import coolant as core
from . import build
from .idprops import store_array

ROOT = "FR coolant"
JETS = "FR coolant jets"
DROPS = "FR coolant drops"
HOSES = "FR coolant hoses"
COLLECTION = "FR Coolant"
NODE_GROUP = "FR coolant drops"
MAT_PREFIX = "FR coolant "
MAT_HOSE = "FR coolant hose"
TAG = "fr_coolant"                    # on everything made here (value: its role)
WET_ATTR = "fr_coolant_wet"           # on parts that get wet: how wet (0 … 1)
WET_PROP = "fr_wet"                   # on the root: the wet level now (keyed by the build)
PATCH = 1                             # version of the wet-sheen nodes put into materials
WET_NODE = "FR coolant wet"
WET_REACH = 0.15                      # m round the workpiece: parts this close get wet
MM = 0.001

_STATE = {"guard": 0}
_HOSE_KEY: dict = {}                  # scene name -> key of the hoses drawn now
#: scene name -> names of the parts marked wet, and the materials' state last checked for new ones (task 0071: walking
#: every part of a big machine at every frame cost 2-5 ms). Dropped when parts are marked, on load, undo, model update
_WET: dict = {}


def forget() -> None:
    _WET.clear()


def settings(scene):
    return scene.fresing.coolant


def is_on(scene) -> bool:
    return bool(settings(scene).enabled)


def root():
    ob = bpy.data.objects.get(ROOT)
    return ob if ob is not None and ob.get(TAG) == "root" else None


def _in_scene(scene, ob) -> bool:
    """``ob.name in scene.objects`` walks every object of the scene (0.7 ms next to a big machine): the coolant's
    objects are in a collection right under the scene's own."""
    top = scene.collection
    for col in ob.users_collection:
        if col == top or top.children.get(col.name) == col:
            return True
    return ob.name in scene.objects


def built(scene) -> bool:
    r = root()
    return r is not None and "fr_spans" in r and _in_scene(scene, r)


# ---------------------------------------------------------------------------
# the head and the coolant space
# ---------------------------------------------------------------------------

def head(scene):
    """The object the coolant hangs under: the part of the head that does not turn with the spindle."""
    from . import gcode
    c = gcode.settings(scene)
    tool = c.tool
    if tool is None:
        return None
    if c.spindle_joint:
        j = scene.fresing.joints.get(c.spindle_joint)
        if j is not None and j.frame is not None and gcode._carries(j, tool):
            return j.frame
    return tool.parent


def space_matrix(scene) -> Matrix:
    """The coolant space in the world: origin at the spindle tool's tip, Z up the tool, X as close to the
    head's X as it gets (so the hoses keep their place round the spindle whatever angle the spindle is at)."""
    from . import gcode
    tool = gcode.settings(scene).tool
    fw = tool.matrix_world @ gcode.tool_frame(tool)
    z = (fw.to_3x3() @ Vector((0, 0, 1))).normalized()
    h = head(scene)
    xref = (h.matrix_world.to_3x3() @ Vector((1, 0, 0))) if h is not None else Vector((1, 0, 0))
    x = xref - z * xref.dot(z)
    if x.length < 1e-6:
        x = Vector((0, 1, 0)) - z * z.y
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = fw.translation
    return m


def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _object(scene, name: str, role: str, data=True):
    ob = bpy.data.objects.get(name)
    if ob is not None and ob.get(TAG) != role:
        ob = None
    if ob is None:
        me = bpy.data.meshes.new(name) if data else None
        if me is not None:
            me[TAG] = role
        ob = bpy.data.objects.new(name, me)
        ob[TAG] = role
        ob[build.PROP_KIND] = "cnc"
        ob.hide_select = True
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    return ob


def ensure_root(scene):
    """The coolant space's empty, placed and parented to the head."""
    r = _object(scene, ROOT, "root", data=False)
    r.empty_display_type = "PLAIN_AXES"
    r.empty_display_size = 0.01
    h = head(scene)
    w = space_matrix(scene)
    if r.parent is not h:
        r.parent = h
    r.matrix_parent_inverse = Matrix.Identity(4)
    r.matrix_basis = (h.matrix_world.inverted_safe() @ w) if h is not None else w
    r.hide_viewport = False
    r.hide_render = False
    # the wet level: a custom property with a 0 … 1 range (Blender clamps keyed values to it)
    if WET_PROP not in r:
        r[WET_PROP] = 0.0
    ui = r.id_properties_ui(WET_PROP)
    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
    return r


def _child(scene, name: str, role: str, r):
    ob = _object(scene, name, role)
    ident = Matrix.Identity(4)
    if ob.parent is not r:
        ob.parent = r
        ob.matrix_parent_inverse = ident
        ob.matrix_basis = ident
    elif ob.matrix_basis != ident or ob.matrix_parent_inverse != ident:
        ob.matrix_parent_inverse = ident
        ob.matrix_basis = ident
    return ob


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------

def liquid_material(kind: str) -> bpy.types.Material:
    look = core.LIQUIDS.get(kind, core.LIQUIDS["EMULSION"])
    name = MAT_PREFIX + ("emulsion" if kind == "EMULSION" else "oil")
    sig = repr((1, look))
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == sig:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat[TAG] = sig
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*look.colour, 1.0)
    b.inputs["Roughness"].default_value = look.roughness
    b.inputs["IOR"].default_value = look.ior
    b.inputs["Transmission Weight"].default_value = look.transmission
    if look.milky:
        b.inputs["Subsurface Weight"].default_value = look.milky
        b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
        b.inputs["Subsurface Scale"].default_value = 0.0008
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    mat.diffuse_color = (*look.colour, 0.6)
    try:
        mat.surface_render_method = "DITHERED"
    except (AttributeError, TypeError):
        pass
    return mat


def hose_material() -> bpy.types.Material:
    mat = bpy.data.materials.get(MAT_HOSE)
    if mat is not None and mat.get(TAG) == "hose":
        return mat
    if mat is None:
        mat = bpy.data.materials.new(MAT_HOSE)
    mat[TAG] = "hose"
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    colour = (0.02, 0.12, 0.42, 1.0)                    # the usual Loc-Line blue
    b.inputs["Base Color"].default_value = colour
    b.inputs["Roughness"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 0.2
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    mat.diffuse_color = colour
    return mat


def _drops_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(NODE_GROUP)
    if ng is not None and ng.get(TAG) == "nodes":
        return ng
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(NODE_GROUP, "GeometryNodeTree")
    ng[TAG] = "nodes"
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gin = n.new("NodeGroupInput")
    gout = n.new("NodeGroupOutput")
    ico = n.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 2
    shade = n.new("GeometryNodeSetShadeSmooth")
    inst = n.new("GeometryNodeInstanceOnPoints")
    size = n.new("GeometryNodeInputNamedAttribute")
    size.data_type = "FLOAT"
    size.inputs["Name"].default_value = "fr_size"
    setmat = n.new("GeometryNodeSetMaterial")
    ng.links.new(ico.outputs["Mesh"], shade.inputs["Geometry"])
    ng.links.new(gin.outputs[0], inst.inputs["Points"])
    ng.links.new(shade.outputs[0], inst.inputs["Instance"])
    ng.links.new(size.outputs["Attribute"], inst.inputs["Scale"])
    ng.links.new(inst.outputs[0], setmat.inputs["Geometry"])
    ng.links.new(setmat.outputs[0], gout.inputs[0])
    return ng


# ---------------------------------------------------------------------------
# wet sheen: a few nodes in the materials of the parts that get wet
# ---------------------------------------------------------------------------

def _principled(mat):
    if mat is None or not getattr(mat, "use_nodes", False) or mat.node_tree is None:
        return []
    return [n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled" and not n.get(TAG)]


def _wet_driver(sock, r) -> None:
    fc = sock.driver_add("default_value")
    dr = fc.driver
    dr.type = "AVERAGE"
    while dr.variables:
        dr.variables.remove(dr.variables[0])
    v = dr.variables.new()
    v.name = "wet"
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = "OBJECT"
    v.targets[0].id = r
    v.targets[0].data_path = f'["{WET_PROP}"]'


def is_patched(mat) -> bool:
    return mat is not None and mat.get(TAG + "_patch") == PATCH


def patch_material(mat, r) -> bool:
    """Puts the wet-sheen nodes into ``mat`` (every Principled BSDF): darker, glossier, a clear wet film, drops on
    the sides. They do nothing for parts without ``fr_coolant_wet``. True when changed."""
    if mat is None or is_patched(mat):
        return False
    bsdfs = _principled(mat)
    if not bsdfs:
        return False
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links

    def new(kind, role, x, y):
        nd = nodes.new(kind)
        nd[TAG] = role
        nd.location = (x, y)
        nd.label = "Coolant: " + role.split(":")[0]
        return nd

    for k, b in enumerate(bsdfs):
        x0, y0 = b.location.x - 900, b.location.y - 600 - 400 * k
        tag = b.name
        gate = new("ShaderNodeAttribute", "gate", x0, y0)
        gate.attribute_type = "OBJECT"
        gate.attribute_name = WET_ATTR
        val = new("ShaderNodeValue", "level", x0, y0 - 160)
        val.name = WET_NODE if k == 0 else f"{WET_NODE} {k}"
        _wet_driver(val.outputs[0], r)
        wet = new("ShaderNodeMath", "wet", x0 + 180, y0)
        wet.operation = "MULTIPLY"
        wet.use_clamp = True
        links.new(gate.outputs["Fac"], wet.inputs[0])
        links.new(val.outputs[0], wet.inputs[1])
        w = wet.outputs[0]

        def source(name):
            sock = b.inputs[name]
            return sock.links[0].from_socket if sock.is_linked else None

        # base colour: darker where wet
        sock = b.inputs["Base Color"]
        mix = new("ShaderNodeMix", "base:" + tag, x0 + 400, y0 + 200)
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        links.new(w, mix.inputs["Factor"])
        src = source("Base Color")
        if src is not None:
            links.new(src, mix.inputs["A"])
        else:
            mix.inputs["A"].default_value = sock.default_value
        mix.inputs["B"].default_value = (0.58, 0.58, 0.58, 1.0)
        links.new(mix.outputs["Result"], sock)
        # roughness: much smoother where wet
        sock = b.inputs["Roughness"]
        rm = new("ShaderNodeMix", "rough:" + tag, x0 + 400, y0)
        rm.data_type = "FLOAT"
        links.new(w, rm.inputs["Factor"])
        src = source("Roughness")
        if src is not None:
            links.new(src, rm.inputs["A"])
        else:
            rm.inputs["A"].default_value = sock.default_value
        rm.inputs["B"].default_value = 0.12
        links.new(rm.outputs["Result"], sock)
        # a clear film on top
        sock = b.inputs["Coat Weight"]
        cw = new("ShaderNodeMath", "coat:" + tag, x0 + 400, y0 - 200)
        cw.operation = "MAXIMUM"
        src = source("Coat Weight")
        if src is not None:
            links.new(src, cw.inputs[0])
        else:
            cw.inputs[0].default_value = sock.default_value
        cm = new("ShaderNodeMath", "coat amount", x0 + 220, y0 - 220)
        cm.operation = "MULTIPLY"
        cm.inputs[1].default_value = 0.9
        links.new(w, cm.inputs[0])
        links.new(cm.outputs[0], cw.inputs[1])
        links.new(cw.outputs[0], sock)
        sock = b.inputs["Coat Roughness"]
        cr = new("ShaderNodeMix", "coatr:" + tag, x0 + 400, y0 - 380)
        cr.data_type = "FLOAT"
        links.new(w, cr.inputs["Factor"])
        src = source("Coat Roughness")
        if src is not None:
            links.new(src, cr.inputs["A"])
        else:
            cr.inputs["A"].default_value = sock.default_value
        cr.inputs["B"].default_value = 0.02
        links.new(cr.outputs["Result"], sock)
        # drops on the sides: round spots in the film on faces that are not flat
        if not b.inputs["Coat Normal"].is_linked:
            tc = new("ShaderNodeTexCoord", "coords", x0 - 200, y0 - 560)
            vor = new("ShaderNodeTexVoronoi", "drops", x0, y0 - 560)
            vor.inputs["Scale"].default_value = 260.0
            vor.inputs["Randomness"].default_value = 0.9
            links.new(tc.outputs["Object"], vor.inputs["Vector"])
            rng = new("ShaderNodeMapRange", "drop shape", x0 + 180, y0 - 560)
            rng.inputs["From Min"].default_value = 0.08
            rng.inputs["From Max"].default_value = 0.32
            rng.inputs["To Min"].default_value = 1.0
            rng.inputs["To Max"].default_value = 0.0
            links.new(vor.outputs["Distance"], rng.inputs["Value"])
            geo = new("ShaderNodeNewGeometry", "normal", x0 - 200, y0 - 760)
            sep = new("ShaderNodeSeparateXYZ", "up", x0, y0 - 760)
            links.new(geo.outputs["Normal"], sep.inputs[0])
            ab = new("ShaderNodeMath", "steep", x0 + 180, y0 - 760)
            ab.operation = "ABSOLUTE"
            links.new(sep.outputs["Z"], ab.inputs[0])
            side = new("ShaderNodeMath", "sides", x0 + 340, y0 - 760)
            side.operation = "SUBTRACT"
            side.inputs[0].default_value = 1.0
            side.use_clamp = True
            links.new(ab.outputs[0], side.inputs[1])
            st = new("ShaderNodeMath", "drop strength", x0 + 500, y0 - 720)
            st.operation = "MULTIPLY"
            links.new(side.outputs[0], st.inputs[0])
            links.new(w, st.inputs[1])
            bump = new("ShaderNodeBump", "bump:" + tag, x0 + 660, y0 - 600)
            bump.inputs["Distance"].default_value = 0.0004
            links.new(rng.outputs[0], bump.inputs["Height"])
            links.new(st.outputs[0], bump.inputs["Strength"])
            links.new(bump.outputs["Normal"], b.inputs["Coat Normal"])
    mat[TAG + "_patch"] = PATCH
    return True


def unpatch_material(mat) -> bool:
    """Takes the wet-sheen nodes out again; the material is as it was before. True when changed."""
    if mat is None or mat.node_tree is None or TAG + "_patch" not in mat:
        return False
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    first = {"base": "A", "rough": "A", "coatr": "A", "coat": 0}
    target = {"base": "Base Color", "rough": "Roughness", "coatr": "Coat Roughness", "coat": "Coat Weight",
              "bump": "Coat Normal"}
    for nd in [n for n in nodes if isinstance(n.get(TAG), str) and ":" in n.get(TAG)]:
        role, bname = nd[TAG].split(":", 1)
        b = nodes.get(bname)
        if b is None or role not in target:
            continue
        sock = b.inputs[target[role]]
        for ln in list(sock.links):
            links.remove(ln)
        if role == "bump":
            continue
        src = nd.inputs[first[role]]
        if src.is_linked:
            links.new(src.links[0].from_socket, sock)
        else:
            dv = src.default_value
            sock.default_value = tuple(dv) if hasattr(dv, "__len__") else dv
    for nd in [n for n in nodes if n.get(TAG)]:
        try:
            nd.outputs[0].driver_remove("default_value")
        except Exception:
            pass
        nodes.remove(nd)
    if nt.animation_data is not None and not nt.animation_data.drivers and nt.animation_data.action is None:
        nt.animation_data_clear()
    del mat[TAG + "_patch"]
    return True


def wet_objects(scene) -> list:
    """(object, how wet) of the parts that get wet: the workpiece, and the parts round it and under it that do not
    ride on the head (the table, the vise, clamps)."""
    from . import gcode, machining
    c = gcode.settings(scene)
    wp = machining.workpiece(scene) or c.workpiece
    if wp is None:
        return []
    pts = gcode._world_points(wp)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    h = head(scene)
    out = [(wp, 1.0)]
    seen = {wp.name}
    for ob in scene.objects:
        if ob.type != "MESH" or ob.name in seen or ob.get(build.PROP_KIND) != "part" or ob.data is None:
            continue
        if ob.hide_render or not len(ob.data.vertices):
            continue
        p = ob
        on_head = False
        while p is not None:
            if p is h:
                on_head = True
                break
            p = p.parent
        if on_head or ob is c.tool:
            continue
        bb = np.array([ob.matrix_world @ Vector(v) for v in ob.bound_box])
        blo, bhi = bb.min(axis=0), bb.max(axis=0)
        if bhi[0] < lo[0] - WET_REACH or blo[0] > hi[0] + WET_REACH:
            continue
        if bhi[1] < lo[1] - WET_REACH or blo[1] > hi[1] + WET_REACH:
            continue
        if bhi[2] < lo[2] - 0.06 or blo[2] > hi[2] + 0.01:         # under the block or beside it, not above
            continue
        near = max(0.0, max(lo[0] - bhi[0], blo[0] - hi[0], lo[1] - bhi[1], blo[1] - hi[1]))
        out.append((ob, 0.9 * (1.0 - 0.5 * near / WET_REACH)))
        seen.add(ob.name)
    return out


def _materials_of(ob) -> list:
    mats = []
    for slot in ob.material_slots:
        if slot.material is not None and slot.material not in mats:
            mats.append(slot.material)
    return mats


def wet_parts(scene) -> list:
    names = _WET.get(scene.name)
    if names is not None:
        obs = [bpy.data.objects.get(n) for n in names]
        if all(o is not None and WET_ATTR in o for o in obs):
            return obs
    obs = [ob for ob in scene.objects if WET_ATTR in ob]
    _WET[scene.name] = [o.name for o in obs]
    return obs


def apply_wet(scene, r) -> int:
    """Marks the parts that get wet and puts the sheen into their materials. Returns how many parts."""
    for ob in wet_parts(scene):
        del ob[WET_ATTR]
    _WET.pop(scene.name, None)
    _WET.pop((scene.name, "mats"), None)
    if not settings(scene).wet_parts:
        unpatch_all()
        return 0
    obs = wet_objects(scene)
    for ob, amount in obs:
        ob[WET_ATTR] = float(round(amount, 3))
        for mat in _materials_of(ob):
            patch_material(mat, r)
    _WET[scene.name] = [ob.name for ob, _a in obs]
    return len(obs)


def _patch_new_materials(scene, r) -> None:
    """Materials that came after the build (the milled block's cut faces) get the sheen too. Looked at again only
    when a material was added or a wet part's slots changed."""
    obs = wet_parts(scene)
    key = (len(bpy.data.materials), tuple((o.name, tuple(s.material.name if s.material else "" for s in
                                                          o.material_slots)) for o in obs))
    if _WET.get((scene.name, "mats")) == key:
        return
    for ob in obs:
        for mat in _materials_of(ob):
            if not is_patched(mat):
                patch_material(mat, r)
    _WET[(scene.name, "mats")] = key


def unpatch_all() -> None:
    for mat in bpy.data.materials:
        if TAG + "_patch" in mat:
            unpatch_material(mat)


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def prepare(scene) -> None:
    """Before a build: no coolant until the steps say so; the objects made (or removed) as set."""
    r = root()
    if r is not None:
        for k in ("fr_spans", "fr_cut", "fr_tools"):
            if k in r:
                del r[k]
    if not is_on(scene):
        remove(scene)
        return
    from . import gcode
    if gcode.problem(scene):
        return
    try:
        r = ensure_root(scene)
    except Exception as exc:                          # the motion is what matters
        print("Fresing Render: the coolant could not be set up:", exc)
        return
    _layout(scene, r)
    store_array(r, "fr_spans", np.zeros(0))
    store_array(r, "fr_cut", np.zeros(0))
    store_array(r, "fr_tools", np.zeros(0))
    g = space_matrix(scene).to_3x3().inverted_safe() @ Vector((0.0, 0.0, -core.G))
    r["fr_g"] = list(g)


def _tool_radius(ob, tip: Vector, axis: Vector) -> float:
    """The tool's cutting radius from its mesh: the widest point within 20 mm of the tip."""
    me = ob.data
    if me is None or not len(me.vertices):
        return 3 * MM
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) - np.array(tip)
    a = np.array(axis.normalized())
    along = co @ a
    rad = np.linalg.norm(co - along[:, None] * a[None, :], axis=1)
    near = (along >= -1e-4) & (along <= 0.02)
    r = float(rad[near].max()) if near.any() else float(rad.max())
    return max(0.5 * MM, min(r, 0.06))


def _layout(scene, r) -> None:
    """Where the automatic hoses start: a ring round the spindle nose (from the tool part's top end and the head's
    parts round the axis)."""
    from . import gcode
    c = gcode.settings(scene)
    tool = c.tool
    tip, axis, _t = gcode._rest_tip(tool)
    me = tool.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) - np.array(tip)
    a = np.array(axis.normalized())
    top = float((co @ a).max())                       # the tool part's top end: the spindle nose is about there
    r_tool = float(np.linalg.norm(co - np.outer(co @ a, a), axis=1).max())
    # the spindle nose: the narrowest part of the head that the axis passes through just above the tool. The root's
    # world matrix is not worked out yet when it was just made or parented (bug hunt 0068 row 9: the first Build
    # mounted the hoses 80 mm too high): its place is the coolant space itself
    inv = space_matrix(scene).inverted_safe()
    nose = None
    h = head(scene)
    if h is not None:
        for ob in h.children_recursive:
            if ob.type != "MESH" or ob is tool or ob.get(build.PROP_KIND) != "part" or ob.hide_render:
                continue
            bb = np.array([inv @ (ob.matrix_world @ Vector(v)) for v in ob.bound_box])
            blo, bhi = bb.min(axis=0), bb.max(axis=0)
            if not (blo[0] < 0 < bhi[0] and blo[1] < 0 < bhi[1]):
                continue
            if blo[2] > top + 0.08 or bhi[2] < top - 0.005:
                continue
            rad = float(min(-blo[0], bhi[0], -blo[1], bhi[1]))
            if rad > r_tool + 1e-4 and (nose is None or rad < nose[0]):
                nose = (rad, float(blo[2]))
    if nose is not None:
        ring, mount_z = nose[0] + core.RING_GAP, max(top, nose[1]) + 6 * MM
    else:
        ring, mount_z = max(r_tool + 25 * MM, 35 * MM), top + 6 * MM
    r["fr_ring"] = float(ring)
    r["fr_mount_z"] = float(mount_z)


def record(scene, sch, b, mach, f0: float, fps: float, offsets: dict) -> None:
    """A Run G-code program step was built: its coolant frames, its cutting frames, the tools it uses."""
    r = root()
    if r is None or "fr_spans" not in r or not is_on(scene):
        return
    s = settings(scene)
    from . import gcode
    cnc = gcode.settings(scene)
    sp = core.spans(sch.m_times(), sch.program_end, sch.spindle_keys(), b.gcode_coolant, s.flood_code,
                    s.mist_code, s.off_code)
    rows = [(f0 + a * fps, f0 + z * fps, k) for a, z, k in sp if z > a]
    old = np.array(r["fr_spans"], dtype=np.float64).reshape(-1)
    store_array(r, "fr_spans", np.concatenate([old, np.array(rows, dtype=np.float64).reshape(-1)]))
    # cutting: feed moves that reach the stock's top (program coordinates)
    top = None
    try:
        pts = gcode._world_points(mach.workpiece)
        loc = (pts - np.array(mach.zero)) @ np.array(mach.rot)
        top = float(loc[:, 2].max()) / MM
    except Exception:
        pass
    cut = [(f0 + a * fps, f0 + z * fps) for a, z in core.cutting_spans(sch.pieces, top)]
    old = np.array(r["fr_cut"], dtype=np.float64).reshape(-1)
    store_array(r, "fr_cut", np.concatenate([old, np.array(cut, dtype=np.float64).reshape(-1)]))
    # the tools: tip height in the coolant space (a longer tool reaches further down) and radius
    tools = {int(t): (z, rad) for t, z, rad in np.array(r["fr_tools"], dtype=np.float64).reshape(-1, 3)}
    copies = gcode.copies(scene)
    numbers = {0} | {n for _s, n, _t, _d in sch.tool_events if n} | ({sch.first_tool} if sch.first_tool else set())
    for n in numbers:
        ob = copies.get(n) if n else None
        if ob is not None and "fr_tip" in ob:
            rad = _tool_radius(ob, Vector(ob["fr_tip"]), Vector(ob["fr_axis"]))
        else:
            tip, axis, _t = gcode._rest_tip(cnc.tool)
            rad = _tool_radius(cnc.tool, tip, axis)
        tools[int(n)] = (-float(offsets.get(n, 0.0)), rad)
    store_array(r, "fr_tools", np.array([[t, z, rad] for t, (z, rad) in sorted(tools.items())],
                                        dtype=np.float64).reshape(-1))
    write_wet_keys(scene, r, fps)
    _lock_interface(scene)


def write_wet_keys(scene, r=None, fps: float | None = None) -> None:
    """The wet level's keys on the root (from all coolant spans of the build) and the sheen on the parts."""
    r = r or root()
    if r is None or "fr_spans" not in r:
        return
    from . import animation
    s = settings(scene)
    fps = fps or scene.render.fps / max(scene.render.fps_base, 1e-6)
    sp = spans(r)
    keys = core.wet_keys(sp, fps, 1.0, max(float(scene.frame_end), 1.0) + s.dry_time * fps + fps, dry=s.dry_time)
    cb = animation._channelbag(r, "OBJECT")
    animation._write(cb, f'["{WET_PROP}"]', 0, [(f, v, "LINEAR", "AUTO") for f, v in keys])
    if len(sp):
        apply_wet(scene, r)


def _lock_interface(scene) -> None:
    """Renders in the window lock the interface (the frame handler writes meshes; see machining.lock_interface)."""
    if not scene.render.use_lock_interface:
        scene.render.use_lock_interface = True


def spans(r=None) -> np.ndarray:
    r = r or root()
    if r is None or "fr_spans" not in r:
        return np.zeros((0, 3))
    return np.array(r["fr_spans"], dtype=np.float64).reshape(-1, 3)


def wet_spans(scene) -> np.ndarray:
    """(start, end) frames while coolant flows (for the chips)."""
    sp = spans() if is_on(scene) else np.zeros((0, 3))
    return sp[:, :2].copy()


def wet_level(scene, T) -> np.ndarray:
    """The surfaces' wet level at frames ``T`` (0 without coolant)."""
    sp = spans() if is_on(scene) else np.zeros((0, 3))
    fps = scene.render.fps / max(scene.render.fps_base, 1e-6)
    return core.wetness(T, sp, fps, dry=settings(scene).dry_time)


def describe(scene, sch, b) -> str:
    """'Coolant: flood 2 times, 12.4 s' for the step (video seconds)."""
    if not is_on(scene):
        return ""
    s = settings(scene)
    sp = core.spans(sch.m_times(), sch.program_end, sch.spindle_keys(), b.gcode_coolant, s.flood_code,
                    s.mist_code, s.off_code)
    if b.gcode_coolant == "OFF":
        return "Coolant: off in this step"
    if not sp:
        return f"Coolant: none (no M{s.flood_code} or M{s.mist_code} in the program)" if b.gcode_coolant == "PROGRAM" \
            else "Coolant: none (the spindle does not turn)"
    return "Coolant: " + core.describe(np.array(sp, dtype=float), 1.0)


def codes(scene) -> set:
    """The M-codes the coolant uses (not 'problems' of a program)."""
    s = settings(scene)
    return {f"M{x}" for x in (s.flood_code, s.mist_code, s.off_code, 7, 8, 9) if x}


def clear(scene) -> None:
    """'Clear keys': no coolant any more (the hoses stay)."""
    r = root()
    if r is not None:
        for k in ("fr_spans", "fr_cut", "fr_tools"):
            if k in r:
                del r[k]
        if WET_PROP in r:
            r[WET_PROP] = 0.0
    for name in (JETS, DROPS):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG) and ob.data is not None:
            ob.data.clear_geometry()


def remove(scene) -> None:
    """Coolant switched off: every coolant object, the sheen nodes and the marks on parts go."""
    for ob in wet_parts(scene):
        del ob[WET_ATTR]
    forget()
    unpatch_all()
    for name in (JETS, DROPS, HOSES, ROOT):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and getattr(me, "users", 1) == 0:
                bpy.data.meshes.remove(me)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and col.get(TAG) and not col.objects:
        bpy.data.collections.remove(col)
    ng = bpy.data.node_groups.get(NODE_GROUP)
    if ng is not None and ng.get(TAG) and ng.users == 0:
        bpy.data.node_groups.remove(ng)
    for mat in [m for m in bpy.data.materials if m.name.startswith(MAT_PREFIX) and m.get(TAG)]:
        if mat.users == 0:
            bpy.data.materials.remove(mat)
    _HOSE_KEY.pop(scene.name, None)


# ---------------------------------------------------------------------------
# picked nozzles
# ---------------------------------------------------------------------------

def _tool_tip_world(scene) -> Vector | None:
    from . import gcode
    tool = gcode.settings(scene).tool
    if tool is None:
        return None
    return tool.matrix_world @ gcode._rest_tip(tool)[0]


def _towards_local(ob, tip_local: Vector, toward) -> Vector:
    if toward is None:
        return Vector((0.0, 0.0, -1.0))
    d_world = Vector(toward) - ob.matrix_world @ tip_local
    if d_world.length < 1e-9:
        return Vector((0.0, 0.0, -1.0))
    d = ob.matrix_world.to_3x3().inverted_safe() @ d_world.normalized()
    return d.normalized() if d.length > 1e-12 else Vector((0.0, 0.0, -1.0))


def add_nozzle(scene, ob, point_world=None) -> str:
    """The part ``ob`` is a coolant nozzle; its tip from its shape (the end nearest the tool) or the clicked
    ``point_world``, aimed at the tool. Returns a note."""
    s = settings(scene)
    toward = _tool_tip_world(scene)
    if point_world is not None:
        tip = ob.matrix_world.inverted_safe() @ Vector(point_world)
        note = "tip at the clicked point, aimed at the tool"
    else:
        from . import air
        tip, _d = air.detect_nozzle(ob, toward)
        note = "tip read from its shape, aimed at the tool"
    d = _towards_local(ob, tip, toward)
    it = next((n for n in s.nozzles if n.obj is ob), None)
    if it is None:
        it = s.nozzles.add()
    it["_busy"] = True
    try:
        it.obj = ob
        it.uid = ob.get(build.PROP_UID, "")
        it.tip = tuple(tip)
        it.dir = tuple(d)
    finally:
        del it["_busy"]
    s.nozzles_index = list(s.nozzles).index(it)
    if s.source != "PARTS":
        s.source = "PARTS"
    else:
        look_changed(scene)
    return note


def aim_nozzle(scene, it, flip: bool = False) -> bool:
    if it.obj is None:
        return False
    if flip:
        d = -Vector(it.dir)
    else:
        toward = _tool_tip_world(scene)
        if toward is None:
            return False
        d = _towards_local(it.obj, Vector(it.tip), toward + Vector((0, 0, core.AIM_UP)))
    it.dir = tuple(d)
    return True


def problem(scene) -> str:
    s = settings(scene)
    if not s.enabled:
        return ""
    if s.source == "PARTS" and not any(n.obj is not None for n in s.nozzles):
        return "Pick the nozzles: click a nozzle part, press Use clicked part (or Click the nozzle point)"
    from . import gcode
    why = gcode.problem(scene)
    return f"CNC machine: {why}" if why else ""


# ---------------------------------------------------------------------------
# every frame
# ---------------------------------------------------------------------------

def _tool_at(scene, r, T: float) -> tuple:
    """(tip height, radius) of the tool in the spindle at frame ``T``, coolant space."""
    from . import gcode
    tools = {int(t): (z, rad) for t, z, rad in np.array(r["fr_tools"], dtype=np.float64).reshape(-1, 3)}
    n = 0
    for f, t in gcode.schedule(scene):
        if f <= T + 1e-6:
            n = t
        else:
            break
    return tools.get(n, tools.get(0, (0.0, 3 * MM)))


def _nozzles(scene, r, aim) -> list:
    s = settings(scene)
    if s.source == "AUTO":
        return core.auto_nozzles(s.auto_count, float(r.get("fr_ring", 0.04)), float(r.get("fr_mount_z", 0.05)),
                                 aim, s.auto_turn)
    inv = r.matrix_world.inverted_safe()
    out = []
    for it in s.nozzles:
        if it.obj is None:
            continue
        m = inv @ it.obj.matrix_world
        o = m @ Vector(it.tip)
        d = m.to_3x3() @ Vector(it.dir)
        if d.length < 1e-9:
            continue
        out.append(core.Nozzle(np.array(o), np.array(d.normalized())))
    return out


def _write_mesh(me, verts, faces) -> None:
    if not len(verts) and not len(me.vertices):
        return                                         # still empty: no update for Blender to work out
    me.clear_geometry()
    if len(verts):
        nv = len(verts)
        me.vertices.add(nv)
        me.vertices.foreach_set("co", np.asarray(verts, np.float32).reshape(-1))
        sizes = np.array([len(f) for f in faces], np.int32)
        me.loops.add(int(sizes.sum()))
        me.loops.foreach_set("vertex_index", np.array([i for f in faces for i in f], np.int32))
        me.polygons.add(len(faces))
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
        me.polygons.foreach_set("loop_start", starts)
        me.polygons.foreach_set("use_smooth", np.ones(len(faces), bool))
    me.update()


def _write_points(me, pos, size) -> None:
    n = len(pos)
    if not n and not len(me.vertices) and "fr_size" in me.attributes:
        return
    me.clear_geometry()
    if n:
        me.vertices.add(n)
        me.vertices.foreach_set("co", np.asarray(pos, np.float32).reshape(-1))
    a = me.attributes.get("fr_size")
    if a is None or a.data_type != "FLOAT":
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new("fr_size", "FLOAT", "POINT")
    if n:
        a.data.foreach_set("value", np.asarray(size, np.float32))
    me.update()


def _hoses(scene, r, aim) -> None:
    s = settings(scene)
    ob = bpy.data.objects.get(HOSES)
    want = s.source == "AUTO" and s.show_hoses
    if not want:
        if ob is not None and ob.get(TAG):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        _HOSE_KEY.pop(scene.name, None)
        return
    key = (round(float(aim[2]), 6), s.auto_count, round(s.auto_turn, 5), round(float(r.get("fr_ring", 0)), 6),
           round(float(r.get("fr_mount_z", 0)), 6))
    if ob is not None and ob.get(TAG) == "hoses" and _HOSE_KEY.get(scene.name) == key and ob.data.get("fr_key") \
            == repr(key):
        return
    ob = _child(scene, HOSES, "hoses", r)
    verts, faces = core.ring_mesh(float(r.get("fr_ring", 0.04)), float(r.get("fr_mount_z", 0.05)))
    verts, faces = list(verts), list(faces)
    for nz in _nozzles(scene, r, aim):
        v, f = core.hose_mesh(nz)
        off = len(verts)
        verts += list(v)
        faces += [tuple(x + off for x in face) for face in f]
    _write_mesh(ob.data, np.array(verts), faces)
    ob.data["fr_key"] = repr(key)
    if not ob.data.materials:
        ob.data.materials.append(hose_material())
    _HOSE_KEY[scene.name] = key


def refresh(scene, T: float | None = None) -> bool:
    """Draws the coolant as it is at frame ``T`` (default: the current frame). True when drawn."""
    r = root()
    if r is None or "fr_spans" not in r or not is_on(scene) or not _in_scene(scene, r):
        return False
    s = settings(scene)
    if T is None:
        T = float(scene.frame_current + scene.frame_subframe)
    fps = scene.render.fps / max(scene.render.fps_base, 1e-6)
    tip_z, radius = _tool_at(scene, r, T)
    tip = np.array([0.0, 0.0, tip_z])
    aim = tip + np.array([0.0, 0.0, core.AIM_UP])
    _hoses(scene, r, aim)
    sp = spans(r)
    cut = np.array(r["fr_cut"], dtype=np.float64).reshape(-1, 2)
    g = np.array(r.get("fr_g", (0.0, 0.0, -core.G)), dtype=np.float64)
    noz = _nozzles(scene, r, aim)
    fr = core.liquid_at(T, fps, sp, cut, noz, aim, tip, radius, s.flow, g, draft=s.draft,
                        reach=min(15 * MM, 2 * radius + 4 * MM))
    mat = liquid_material(s.liquid)
    jets = _child(scene, JETS, "jets", r)
    _write_mesh(jets.data, fr.verts, fr.faces)
    if not jets.data.materials:
        jets.data.materials.append(mat)
    elif jets.data.materials[0] is not mat:
        jets.data.materials[0] = mat
    drops = _child(scene, DROPS, "drops", r)
    mod = drops.modifiers.get("Drops")
    if mod is None:
        mod = drops.modifiers.new("Drops", "NODES")
    ng = _drops_group()
    if mod.node_group is not ng:
        mod.node_group = ng
    setmat = next(nd for nd in ng.nodes if nd.bl_idname == "GeometryNodeSetMaterial")
    if setmat.inputs["Material"].default_value is not mat:
        setmat.inputs["Material"].default_value = mat
    _write_points(drops.data, fr.drops, fr.sizes)
    for ob in (jets, drops):
        if ob.visible_shadow:                          # (set only on change: a set tags the object for an update)
            ob.visible_shadow = False
    return True


def _off_main_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _draw_frame(scene, pre: bool) -> None:
    if _STATE["guard"] or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        if not is_on(scene):
            return
        # automatic hoses need nothing of the new frame but its number: drawn before the frame is worked out, so
        # Blender works the scene out once (task 0071; after it, a second time: ~11 ms next to a big machine).
        # Picked nozzles are read where they are at the new frame: after it
        if pre != (settings(scene).source == "AUTO") or not built(scene):
            return
        if not bpy.app.background and _off_main_thread() and not scene.render.use_lock_interface:
            return
        if not _off_main_thread():
            r = root()
            if r is not None and settings(scene).wet_parts:
                _patch_new_materials(scene, r)
        _STATE["guard"] += 1
        try:
            refresh(scene)
        finally:
            _STATE["guard"] -= 1
    except Exception as exc:
        print("Fresing Render: coolant frame update failed:", exc)


@persistent
def _on_frame(scene, _depsgraph=None):
    _draw_frame(scene, False)


@persistent
def _on_frame_pre(scene, _depsgraph=None):
    _draw_frame(scene, True)


@persistent
def _on_load(_dummy=None):
    _HOSE_KEY.clear()
    forget()


# ---------------------------------------------------------------------------
# settings changed, model update
# ---------------------------------------------------------------------------

def look_changed(scene) -> None:
    """Flow, liquid, nozzles, draft: the current frame is drawn again."""
    _HOSE_KEY.pop(scene.name, None)
    try:
        refresh(scene)
    except Exception as exc:
        print("Fresing Render: coolant could not be drawn:", exc)


def settings_changed(scene) -> None:
    """Coolant on/off, codes, drying, sheen: the steps' summaries and the chips follow; switched off: it goes."""
    from . import chips, gcode, machining
    if not is_on(scene):
        remove(scene)
    else:
        r = root()
        if r is not None and "fr_spans" in r:
            try:
                write_wet_keys(scene, r)
                if not settings(scene).wet_parts:
                    apply_wet(scene, r)
            except Exception as exc:
                print("Fresing Render: coolant wet sheen:", exc)
        look_changed(scene)
    try:
        gcode.setup_changed(scene)
    except Exception:
        pass
    try:
        if machining.is_active(scene) and chips.wanted(scene):
            chips.settings_changed(scene)
    except Exception:
        pass


def before_model_update(scene) -> None:
    obs = wet_parts(scene)
    for ob in obs:
        del ob[WET_ATTR]
    forget()
    _WET["had_wet"] = bool(obs)


def after_model_update(scene, new) -> list:
    s = settings(scene)
    notes = []
    for i in range(len(s.nozzles) - 1, -1, -1):
        it = s.nozzles[i]
        if not it.uid:
            continue
        ob = new(it.uid)
        if ob is None:
            notes.append("Coolant: a nozzle part is gone in the new revision (pick it again in 4 Motion > CNC machine "
                         "> Coolant)")
            s.nozzles.remove(i)
            continue
        it["_busy"] = True
        try:
            it.obj = ob
            it.uid = ob.get(build.PROP_UID, "")
        finally:
            del it["_busy"]
    s.nozzles_index = min(s.nozzles_index, max(0, len(s.nozzles) - 1))
    # the hoses hang on the new head part, and the parts that get wet are marked again (bug hunt 0068 row 18)
    r = root()
    if r is not None and is_on(scene):
        from . import gcode
        try:
            bpy.context.view_layer.update()
            if not gcode.problem(scene):
                ensure_root(scene)
                if _WET.pop("had_wet", False) or len(spans(r)):
                    apply_wet(scene, r)
        except Exception as exc:
            notes.append(f"Coolant: could not be put on the new head ({exc}); build the animation again")
    return notes


def register():
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame), (bpy.app.handlers.frame_change_pre, _on_frame_pre),
                    (bpy.app.handlers.load_post, _on_load)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame), (bpy.app.handlers.frame_change_pre, _on_frame_pre),
                    (bpy.app.handlers.load_post, _on_load)):
        while fn in lst:
            lst.remove(fn)
