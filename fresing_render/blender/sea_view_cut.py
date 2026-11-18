"""The sea cut-away in the 3D view (task 0196).

The cut-away of task 0081 / 0148 is a shader effect: the sea (and, with "Cut the ground too", the seabed) are
see-through inside the box in a render. Solid view does not draw materials, so the owner saw one grey sheet there.
Here the same box is cut out of the *mesh*, by a Geometry Nodes modifier "FR view cut" that is switched off for
renders (``show_render`` off): a render is exactly what it was.

How, two ways (the ``Exact`` input): a flat surface of a few faces (Simple) gets a thin slab and the box is taken
away with Mesh Boolean – exact, and Blender keeps the result while nothing changes. A surface with many points
(Detailed: the waves, the seabed's ripples) has the points inside the box let down under whatever lies beneath them:
no copy of the mesh, so it is cheap while waves move at every frame; the edge follows the surface's own points and a
wall of that depth stands round the box. The modifier is the last in the stack, after the waves.

The box comes in world numbers (the shader's ``fr_seacut_o/u/s``) and is turned into the object's own frame here.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

GROUP = "FR view cut"
MOD = "FR view cut"
SLAB = 0.05                 # m: how thick the thin slab under the surface is (the cut wall one sees)
HEIGHT = 400.0              # m: the box reaches this far up and down (the sea's rim rises 400 m)

_INPUTS = (("Centre", "NodeSocketVector"), ("Angle", "NodeSocketFloat"), ("Size", "NodeSocketVector"),
           ("Exact", "NodeSocketBool"), ("Drop", "NodeSocketFloat"))


def _group() -> bpy.types.NodeTree:
    """Two ways to cut, picked by the ``Exact`` input (a Switch works out only the one that is picked):
    exact = a thin slab + Mesh Boolean (the box's edge is exact; for a plain flat surface of a few faces, which
    Blender keeps while nothing changes); not exact = the points inside the box let down by ``Drop`` (below what lies
    under them, so they are never seen): no copy of the mesh, cheap enough for waves that move at every frame; the
    edge follows the surface's own points (about a metre) and a wall of that depth stands round the box."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng["fr_env"] = "view_cut"
    ifc = ng.interface
    ifc.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ifc.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, kind in _INPUTS:
        ifc.new_socket(name, in_out="INPUT", socket_type=kind)
    nodes, links = ng.nodes, ng.links
    new = nodes.new
    gin, gout = new("NodeGroupInput"), new("NodeGroupOutput")

    def math(op, a, b=None):
        n = new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def vec(op, a, b):
        n = new("ShaderNodeVectorMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, bpy.types.NodeSocket):
                links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs["Value"] if op == "DOT_PRODUCT" else n.outputs["Vector"]

    # --- exact: a slab, the box taken away
    ext = new("GeometryNodeExtrudeMesh")
    ext.mode = "FACES"
    ext.inputs["Offset Scale"].default_value = -SLAB
    ext.inputs["Individual"].default_value = False
    links.new(gin.outputs["Geometry"], ext.inputs["Mesh"])
    cube = new("GeometryNodeMeshCube")
    links.new(gin.outputs["Size"], cube.inputs["Size"])
    tr = new("GeometryNodeTransform")
    links.new(cube.outputs["Mesh"], tr.inputs["Geometry"])
    links.new(gin.outputs["Centre"], tr.inputs["Translation"])
    comb = new("ShaderNodeCombineXYZ")
    links.new(gin.outputs["Angle"], comb.inputs["Z"])
    links.new(comb.outputs["Vector"], tr.inputs["Rotation"])
    boo = new("GeometryNodeMeshBoolean")
    boo.operation = "DIFFERENCE"
    boo.solver = "EXACT"
    links.new(ext.outputs["Mesh"], boo.inputs["Mesh 1"])
    links.new(tr.outputs["Geometry"], boo.inputs["Mesh 2"])
    # --- cheap: the faces whose centre is in the box
    ang = gin.outputs["Angle"]
    cs, sn = math("COSINE", ang), math("SINE", ang)
    uvec, vvec = new("ShaderNodeCombineXYZ"), new("ShaderNodeCombineXYZ")
    links.new(cs, uvec.inputs["X"])
    links.new(sn, uvec.inputs["Y"])
    links.new(math("MULTIPLY", sn, -1.0), vvec.inputs["X"])
    links.new(cs, vvec.inputs["Y"])
    d = vec("SUBTRACT", new("GeometryNodeInputPosition").outputs["Position"], gin.outputs["Centre"])
    sep = new("ShaderNodeSeparateXYZ")
    links.new(gin.outputs["Size"], sep.inputs[0])
    along = math("LESS_THAN", math("ABSOLUTE", vec("DOT_PRODUCT", d, uvec.outputs["Vector"])),
                 math("MULTIPLY", sep.outputs["X"], 0.5))
    side = math("LESS_THAN", math("ABSOLUTE", vec("DOT_PRODUCT", d, vvec.outputs["Vector"])),
                math("MULTIPLY", sep.outputs["Y"], 0.5))
    dele = new("GeometryNodeSetPosition")
    links.new(gin.outputs["Geometry"], dele.inputs["Geometry"])
    links.new(math("MULTIPLY", along, side), dele.inputs["Selection"])
    down = new("ShaderNodeCombineXYZ")
    links.new(math("MULTIPLY", gin.outputs["Drop"], -1.0), down.inputs["Z"])
    links.new(down.outputs["Vector"], dele.inputs["Offset"])
    # --- the one that is asked for
    sw = new("GeometryNodeSwitch")
    sw.input_type = "GEOMETRY"
    links.new(gin.outputs["Exact"], sw.inputs["Switch"])
    links.new(dele.outputs["Geometry"], sw.inputs["False"])
    links.new(boo.outputs["Mesh"], sw.inputs["True"])
    links.new(sw.outputs["Output"], gout.inputs["Geometry"])
    return ng


def _local_box(ob, box) -> tuple[Vector, float, Vector]:
    """Centre, turn about z and size of the cube, in ``ob``'s own frame (the box is in world)."""
    parent = ob.parent.matrix_world if ob.parent is not None else Matrix.Identity(4)
    world = parent @ Matrix.Translation(ob.location)
    inv = world.inverted()
    o = Vector((float(box["origin"][0]), float(box["origin"][1]), 0.0))
    u = Vector((float(box["dir"][0]), float(box["dir"][1]), 0.0))
    u.normalize()
    length, width = float(box["length"]), float(box["width"])
    centre = inv @ (o + u * (length / 2.0))
    ux = inv.to_3x3() @ u
    centre.z = 0.0
    return centre, math.atan2(ux.y, ux.x), Vector((length, width, HEIGHT))


def set_cut(ob, box, exact: bool = True, drop: float = 1.0) -> None:
    """Put the view cut on ``ob`` for ``box`` (None: take it off). Viewport only, first in the stack."""
    mod = ob.modifiers.get(MOD)
    if box is None:
        if mod is not None:
            ob.modifiers.remove(mod)
        return
    if mod is None:
        mod = ob.modifiers.new(MOD, "NODES")
        mod.node_group = _group()
        mod.show_render = False
        mod.show_in_editmode = False
    centre, angle, size = _local_box(ob, box)
    inputs = mod.properties.inputs
    ids = {i.name: i.identifier for i in mod.node_group.interface.items_tree if getattr(i, "in_out", "") == "INPUT"}
    getattr(inputs, ids["Centre"]).value = tuple(centre)
    getattr(inputs, ids["Angle"]).value = float(angle)
    getattr(inputs, ids["Size"]).value = tuple(size)
    getattr(inputs, ids["Exact"]).value = bool(exact)
    getattr(inputs, ids["Drop"]).value = float(drop)
    mod.show_viewport = True
    ob.update_tag()
