"""Adjust a look (task 0314) – Blender side: the shared node group "FR adjust", putting it into a group's material,
the live update while a slider moves, Reset, and Open in the shader editor.

The node group's inputs are named as the picker's sliders (Shine, Metal ↔ paint, Dirt, Relief, Clear coat), so an
animator who opens the nodes finds the same words. ``core/look_adjust.py`` has the ranges and the same formulas in
plain Python (the tests compare them with the nodes' wiring).

A material gets the node only when a slider is away from its default, or when it was opened in the shader editor
(``KEEP`` on the material): a look nobody adjusted keeps exactly its own nodes and render time.
"""

from __future__ import annotations

import bpy

from ..core import look_adjust as LA

GROUP = "FR adjust"
NODE = "FR adjust"                 # the node's name in a material
VERSION = 1                        # raise when the group's nodes change: it is made again
PROP_VERSION = "fr_adjust_version"
PROP_KEY = "fr_adjust"             # on a material: the values its node shows (core.look_adjust.key)
KEEP = "fr_adjust_keep"            # on a material: keep the node even at the defaults (opened in the shader editor)
GROUP_PROPS = {"shine": "adj_shine", "metal": "adj_metal", "dirt": "adj_dirt", "relief": "adj_relief",
               "coat": "adj_coat"}

#: the group's inputs: (name, socket type, default); the sliders' names come from core.look_adjust.SLIDERS
LOOK_IN = (("Colour", "NodeSocketColor", (0.8, 0.8, 0.8, 1.0)), ("Metallic", "NodeSocketFloat", 0.0),
           ("Roughness", "NodeSocketFloat", 0.4), ("Normal", "NodeSocketVector", (0.0, 0.0, 1.0)),
           ("Geometry normal", "NodeSocketVector", (0.0, 0.0, 1.0)), ("Coat", "NodeSocketFloat", 0.0))
OUTS = (("Colour", "NodeSocketColor"), ("Metallic", "NodeSocketFloat"), ("Roughness", "NodeSocketFloat"),
        ("Normal", "NodeSocketVector"), ("Coat", "NodeSocketFloat"))


def label(name: str) -> str:
    return LA.SLIDERS[name][0]


def values_of(g) -> dict:
    return LA.clean({k: getattr(g, p) for k, p in GROUP_PROPS.items()})


def group_key(g) -> str:
    return LA.key(values_of(g))


def node_group():
    """The shared node group (made, or made again when its version is older)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.bl_idname == "ShaderNodeTree" and int(ng.get(PROP_VERSION, 0)) >= VERSION:
        return ng
    if ng is None or ng.bl_idname != "ShaderNodeTree":
        ng = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    _build(ng)
    return ng


def _build(ng) -> None:
    from .materials import _Nodes
    ng.nodes.clear()
    ng.interface.clear()
    for name, kind, d in LOOK_IN:
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        s.default_value = d
        if name == "Geometry normal":
            s.hide_value = True
    for k, (lab, lo, hi, d, tip) in LA.SLIDERS.items():
        s = ng.interface.new_socket(lab, in_out="INPUT", socket_type="NodeSocketFloat")
        s.min_value, s.max_value, s.default_value = lo, hi, d
        s.description = tip
    for name, kind in OUTS:
        ng.interface.new_socket(name, in_out="OUTPUT", socket_type=kind)
    b = _Nodes(ng)
    gi = b.node("NodeGroupInput", -1400, 0)
    go = b.node("NodeGroupOutput", 900, 0)
    i = gi.outputs

    def lab(k):
        return i[LA.SLIDERS[k][0]]

    def madd(a, m, c, x, y):
        """a x m + c"""
        n = b.node("ShaderNodeMath", x, y)
        n.operation = "MULTIPLY_ADD"
        for sock, v in zip(n.inputs, (a, m, c)):
            b.put(sock, v)
        return n.outputs[0]

    # Shine: towards ROUGH_SHINY (+) or ROUGH_DULL (-) by |Shine| (core.look_adjust.roughness)
    s = lab("shine")
    t = b.math("MAXIMUM", s, 0.0, x=-1100, y=300)
    u = b.math("MAXIMUM", b.math("MULTIPLY", s, -1.0, x=-1250, y=200), 0.0, x=-1100, y=200)
    keep = b.math("SUBTRACT", 1.0, b.math("ABSOLUTE", s, x=-1250, y=400), x=-1100, y=400)
    r = b.math("MULTIPLY", i["Roughness"], keep, x=-950, y=350)
    r = madd(t, LA.ROUGH_SHINY, r, -800, 350)
    r = madd(u, LA.ROUGH_DULL, r, -650, 350)
    # Metal ↔ paint: towards 1 (+) or 0 (-)
    k = lab("metal")
    tk = b.math("MAXIMUM", k, 0.0, x=-1100, y=-50)
    kk = b.math("SUBTRACT", 1.0, b.math("ABSOLUTE", k, x=-1250, y=-150), x=-1100, y=-150)
    m = madd(i["Metallic"], kk, tk, -950, -100)
    # Dirt: soft patches (a noise on the object's coordinates) x Dirt
    patch = b.map(b.noise(None, LA.DIRT_SCALE, 3.0, x=-1100, y=-450), 0.4, 0.7, 0.0, 1.0, x=-950, y=-450)
    f = b.math("MULTIPLY", lab("dirt"), patch, x=-800, y=-400, clamp=True)
    col = b.mix("RGBA", b.math("MULTIPLY", f, LA.DIRT_SHARE, x=-650, y=-300), i["Colour"], (*LA.DIRT_RGB, 1.0),
                x=-450, y=-250)
    r = b.mix("FLOAT", f, r, LA.DIRT_ROUGH, x=-450, y=350)
    r = b.math("MINIMUM", b.math("MAXIMUM", r, LA.ROUGH_SHINY, x=-300, y=350), 1.0, x=-150, y=350, clamp=True)
    m = b.math("MULTIPLY", m, b.math("SUBTRACT", 1.0, f, x=-650, y=-150), x=-450, y=-100, clamp=True)
    # Relief: the look's normal tilted away from the surface's own by Relief (0 = smooth, 1 = as made)
    d = b.vmath("SUBTRACT", i["Normal"], i["Geometry normal"], x=-650, y=-650)
    nrm = b.vmath("NORMALIZE", b.vmath("ADD", i["Geometry normal"],
                                       b.vmath("SCALE", d, scale=lab("relief"), x=-450, y=-650), x=-300, y=-650),
                  x=-150, y=-650)
    coat = b.math("MAXIMUM", i["Coat"], lab("coat"), x=-450, y=-850, clamp=True)
    for name, sock in (("Colour", col), ("Metallic", m), ("Roughness", r), ("Normal", nrm), ("Coat", coat)):
        ng.links.new(sock, go.inputs[name])
    ng[PROP_VERSION] = VERSION


def wanted(mat, values: dict) -> bool:
    return not LA.is_default(values) or bool(mat.get(KEEP))


def insert(b, mat, bsdf, spec: dict, values: dict, color, metallic, rough, normal):
    """Put the node between the look and the BSDF (``materials.build_nodes``). Returns (colour, metallic, roughness,
    normal) to feed the BSDF; the coat goes straight to it."""
    n = b.node("ShaderNodeGroup", 50, -150)
    n.node_tree = node_group()
    n.name = n.label = NODE
    geo = b.node("ShaderNodeNewGeometry", -150, -600)
    b.put(n.inputs["Colour"], color)
    b.put(n.inputs["Metallic"], metallic)
    b.put(n.inputs["Roughness"], rough)
    b.put(n.inputs["Normal"], normal if normal is not None else geo.outputs["Normal"])
    b.put(n.inputs["Geometry normal"], geo.outputs["Normal"])
    b.put(n.inputs["Coat"], float(spec.get("coat", 0.0)))
    set_inputs(n, values)
    b.put(bsdf.inputs["Coat Weight"], n.outputs["Coat"])
    if not spec.get("coat"):
        bsdf.inputs["Coat Roughness"].default_value = LA.COAT_ROUGH
    mat[PROP_KEY] = LA.key(values)
    o = n.outputs
    return o["Colour"], o["Metallic"], o["Roughness"], o["Normal"]


def set_inputs(node, values: dict) -> None:
    v = LA.clean(values)
    for k in LA.NAMES:
        node.inputs[label(k)].default_value = v[k]


def node_of(mat):
    nt = mat.node_tree if mat is not None else None
    n = nt.nodes.get(NODE) if nt is not None else None
    return n if n is not None and n.bl_idname == "ShaderNodeGroup" else None


def _viewport(mat, material_id: str, values: dict) -> None:
    from ..core import materials_lib
    spec = materials_lib.get(material_id)
    r, m = LA.viewport(float(spec.get("roughness", 0.4)), float(spec.get("metallic", 0.0)), values)
    mat.roughness, mat.metallic = r, m


def live(g, context) -> None:
    """A slider moved: the node's inputs when the material has the node (no rebuild), else the whole look again."""
    from . import materials, props
    if g.material == "blender_material":
        return
    mat = bpy.data.materials.get(materials.material_name(g.name))
    values = values_of(g)
    n = node_of(mat)
    if n is not None and mat.get("fr_material") == g.material:
        set_inputs(n, values)
        mat[PROP_KEY] = LA.key(values)
        _viewport(mat, g.material, values)
        mat.node_tree.update_tag()
        from . import material_picker
        material_picker.adjusted(g)
        return
    props._group_look_changed(g, context)
    from . import material_picker
    material_picker.adjusted(g)


def write(g, values: dict) -> None:
    """Set a group's sliders without an update each (one rebuild follows)."""
    v = LA.clean(values)
    for k, p in GROUP_PROPS.items():
        g[p] = v[k]


def keep_node(g) -> bpy.types.Material | None:
    """Open in the shader editor: the group's material keeps its "FR adjust" node from now on."""
    from . import materials
    if g.material == "blender_material":
        return materials.group_material(g)
    mat = materials.group_material(g)
    if mat is not None and node_of(mat) is None:
        mat[KEEP] = True
        materials.build_nodes(mat, g.material, g.color, g.wear, finish=materials.group_finish(g), rust=g.rust,
                              adjust=group_key(g))
    return mat


def open_editor(mat_name: str):
    """(From a timer: screens are changed only there, CLAUDE.md.) A new window of the main window's workspace whose
    biggest 3D view becomes the shader editor, pinned to the material, the "FR adjust" node picked."""
    from . import ops_setup
    mat = bpy.data.materials.get(mat_name)
    win, _area, _region = ops_setup.main_view()
    if mat is None or win is None or mat.node_tree is None:
        return None
    wm = bpy.context.window_manager
    before = list(wm.windows)
    try:
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.wm.window_new()
    except RuntimeError as exc:
        print("Fresing Render: the shader editor's window did not open:", exc)
        return None
    new = [w for w in wm.windows if w not in before]
    if not new:
        return None
    areas = sorted(new[0].screen.areas, key=lambda a: (a.type != "VIEW_3D", -a.width * a.height))
    if not areas:
        return None
    area = areas[0]
    area.ui_type = "ShaderNodeTree"
    space = area.spaces.active
    try:
        space.shader_type = "OBJECT"
        space.pin = True
        space.node_tree = mat.node_tree
    except (AttributeError, TypeError, RuntimeError) as exc:
        print("Fresing Render: the shader editor is not pinned to the material:", exc)
    n = node_of(mat)
    if n is not None:
        for other in mat.node_tree.nodes:
            other.select = False
        n.select = True
        mat.node_tree.nodes.active = n
    return None
