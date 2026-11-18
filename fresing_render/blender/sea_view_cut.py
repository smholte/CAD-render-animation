"""The sea cut-away in the 3D view (task 0196, made cheap in task 0202).

The cut-away of task 0081 / 0148 is a shader effect: the sea, the hull foam (and, with "Cut the ground too", the seabed
and its stones) are see-through inside the box in a render. Solid view does not draw materials, so the box is cut out
of the *meshes* here, by a Geometry Nodes modifier "FR view cut" that is switched off for renders (``show_render``
off): a render is exactly what it was. It is the last modifier, after the waves.

Task 0202 measured 0.2.153's way (delete the faces inside the box: a copy of the whole mesh at every frame, because
the waves move): +6.2 ms a frame on the demo's Detailed sea. A node tree that works the cut out per point at every
frame was still +2.3 ms on the test vessel (~60 sums over 290,000 points), one that looks at each point's faces
+8.7 ms. So, three ways (the ``Way`` input):

- **Stored** (the sea and its hull foam: the waves move them at every frame, but only up and down): how far each
  point moves for the cut is worked out once, here in NumPy, and kept on the mesh as the point attribute
  ``fr_view_cut``; the modifier only adds it (one sum per point). The points inside the box go down by ``drop``
  (under whatever lies beneath them, so they are never seen), and the points round the box are put onto its walls –
  inside ones go down there, outside ones stay up – so the edge is the box's straight line and the wall stands
  straight: no spikes where the mesh's faces cross the box's edge at a slant.
- **Live** (the rippled seabed and its stones: they slide aft under the vessel with the cable's lay, the box stays
  with the vessel): the points inside the box (world) are let down, worked out in the nodes when the seabed moves.
- **Exact** (the Simple sea and seabed: a few big faces): a thin slab is cut by the box (Mesh Boolean).
"""

from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix

GROUP = "FR view cut 3"            # (0.2.153's "FR view cut" had other inputs: ``refresh`` swaps it)
MOD = "FR view cut"
OLD_GROUP = "FR view cut"
ATTR = "fr_view_cut"                # point attribute: the stored way's offset (object coordinates)
SLAB = 0.05                         # m: the thin slab under a Simple surface (the cut wall one sees)
HEIGHT = 2000.0                     # m: the exact way's box reaches this far up and down from the object
STORED, LIVE, EXACT = 0, 1, 2

_INPUTS = (("Origin", "NodeSocketVector"), ("Direction", "NodeSocketVector"), ("Size", "NodeSocketVector"),
           ("Drop", "NodeSocketFloat"), ("Way", "NodeSocketInt"))


# ---- the stored way: worked out here --------------------------------------------------------------------------


def offsets(points_world: np.ndarray, box, drop: float, band) -> np.ndarray:
    """How far each point (world x, y, z) moves for the cut, in world: inside the box down by ``drop``; within
    ``band`` of the box's outline onto it (``band``: metres, or one value per point – about a face's size there, so
    every face that crosses the outline has all its corners on it)."""
    p = np.asarray(points_world, float)
    o = np.array([float(box["origin"][0]), float(box["origin"][1])])
    u = np.array([float(box["dir"][0]), float(box["dir"][1])])
    u /= max(float(np.linalg.norm(u)), 1e-12)
    v = np.array([-u[1], u[0]])
    length, half = float(box["length"]), float(box["width"]) / 2.0
    d = p[:, :2] - o
    a, s = d @ u, d @ v
    band = np.broadcast_to(np.asarray(band, float), a.shape)
    inside = (a > 0.0) & (a < length) & (np.abs(s) < half)
    # outside, near: the nearest point of the box's outline
    a_c, s_c = np.clip(a, 0.0, length), np.clip(s, -half, half)
    gap = np.hypot(a - a_c, s - s_c)
    snap_out = ~inside & (gap < band)
    # inside, near a wall: onto the nearest wall
    to_end = np.minimum(a, length - a)
    to_side = half - np.abs(s)
    snap_in = inside & (np.minimum(to_end, to_side) < band)
    use_end = to_end < to_side
    a_w = np.where(use_end, np.where(a > length / 2.0, length, 0.0), a)
    s_w = np.where(use_end, s, np.sign(s) * half)
    a_new = np.where(snap_out, a_c, np.where(snap_in, a_w, a))
    s_new = np.where(snap_out, s_c, np.where(snap_in, s_w, s))
    out = np.zeros_like(p)
    out[:, :2] = (a_new - a)[:, None] * u + (s_new - s)[:, None] * v
    out[:, 2] = np.where(inside, -float(drop), 0.0)
    return out


def _world_matrix(ob) -> Matrix:
    """``ob``'s place as built (a new object's ``matrix_world`` is not worked out yet): its parent's and its own."""
    parent = ob.parent.matrix_world if ob.parent is not None else Matrix.Identity(4)
    return parent @ ob.matrix_parent_inverse @ ob.matrix_basis


def store(ob, box, drop: float, band) -> None:
    """The stored way's offsets on ``ob``'s mesh (attribute ``ATTR``, in the object's coordinates). ``band``: metres,
    or (metres, metres per metre from the object's origin)."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(float)
    m = np.array(_world_matrix(ob))
    w = co @ m[:3, :3].T + m[:3, 3]
    if isinstance(band, (tuple, list)):
        band = band[0] + band[1] * np.hypot(co[:, 0], co[:, 1])
    off = offsets(w, box, drop, band) @ np.linalg.inv(m[:3, :3]).T
    at = me.attributes.get(ATTR)
    if at is None or at.domain != "POINT" or at.data_type != "FLOAT_VECTOR":
        if at is not None:
            me.attributes.remove(at)
        at = me.attributes.new(ATTR, "FLOAT_VECTOR", "POINT")
    at.data.foreach_set("vector", off.astype(np.float32).ravel())


# ---- the nodes --------------------------------------------------------------------------------------------------


class _B:
    def __init__(self, ng):
        self.ng = ng

    def new(self, kind, **props):
        n = self.ng.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.ng.links.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        n = self.new("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def vec(self, op, a, b=None):
        n = self.new("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b)):
            self.put(n.inputs[i], v)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH") else n.outputs["Vector"]

    def scale(self, v, f):
        n = self.new("ShaderNodeVectorMath", operation="SCALE")
        self.put(n.inputs[0], v)
        self.put(n.inputs["Scale"], f)
        return n.outputs["Vector"]

    def comb(self, x, y, z):
        n = self.new("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def sep(self, v):
        n = self.new("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], v)
        return n.outputs

    def switch(self, flag, no, yes):
        sw = self.new("GeometryNodeSwitch", input_type="GEOMETRY")
        self.put(sw.inputs["Switch"], flag)
        self.put(sw.inputs["False"], no)
        self.put(sw.inputs["True"], yes)
        return sw.outputs["Output"]


def _group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get("fr_env") == "view_cut":
        return ng
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng["fr_env"] = "view_cut"
    ifc = ng.interface
    ifc.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ifc.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, kind in _INPUTS:
        ifc.new_socket(name, in_out="INPUT", socket_type=kind)
    b = _B(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    geo = gin.outputs["Geometry"]
    way = gin.outputs["Way"]

    # --- stored: one sum per point
    attr = b.new("GeometryNodeInputNamedAttribute", data_type="FLOAT_VECTOR")
    attr.inputs["Name"].default_value = ATTR
    stored = b.new("GeometryNodeSetPosition")
    b.put(stored.inputs["Geometry"], geo)
    b.put(stored.inputs["Offset"], attr.outputs["Attribute"])

    # --- live: the points inside the box let down (the box brought into the object's coordinates once: a few sums
    # per point; the seabed only slides, it never turns)
    own = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.put(own.inputs["Object"], b.new("GeometryNodeSelfObject").outputs[0])
    m_own = own.outputs["Transform"]
    inv = b.new("FunctionNodeInvertMatrix")
    b.put(inv.inputs[0], m_own)
    m_inv = inv.outputs["Matrix"]
    o, u, size = gin.outputs["Origin"], gin.outputs["Direction"], b.sep(gin.outputs["Size"])
    length, half = size["X"], size["Y"]
    mid_w = b.vec("ADD", o, b.scale(u, b.math("MULTIPLY", length, 0.5)))
    mid = b.new("FunctionNodeTransformPoint")
    b.put(mid.inputs["Vector"], mid_w)
    b.put(mid.inputs["Transform"], m_inv)
    u_l = b.new("FunctionNodeTransformDirection")
    b.put(u_l.inputs["Direction"], u)
    b.put(u_l.inputs["Transform"], m_inv)
    v_l = b.new("FunctionNodeTransformDirection")
    b.put(v_l.inputs["Direction"], b.vec("CROSS_PRODUCT", (0.0, 0.0, 1.0), u))
    b.put(v_l.inputs["Transform"], m_inv)
    d = b.vec("SUBTRACT", b.new("GeometryNodeInputPosition").outputs[0], mid.outputs[0])
    a = b.math("SUBTRACT", b.math("ABSOLUTE", b.vec("DOT_PRODUCT", d, u_l.outputs[0])),
               b.math("MULTIPLY", length, 0.5))                   # < 0 between the box's ends
    s = b.math("SUBTRACT", b.math("ABSOLUTE", b.vec("DOT_PRODUCT", d, v_l.outputs[0])), half)   # < 0 between its sides
    inside = b.math("LESS_THAN", b.math("MAXIMUM", a, s), 0.0)
    live = b.new("GeometryNodeSetPosition")
    b.put(live.inputs["Geometry"], geo)
    b.put(live.inputs["Offset"], b.comb(0.0, 0.0, b.math("MULTIPLY", inside,
                                                             b.math("MULTIPLY", gin.outputs["Drop"], -1.0))))

    # --- exact: a slab, the box taken away
    ext = b.new("GeometryNodeExtrudeMesh", mode="FACES")
    ext.inputs["Offset Scale"].default_value = -SLAB
    ext.inputs["Individual"].default_value = False
    b.put(ext.inputs["Mesh"], geo)
    cube = b.new("GeometryNodeMeshCube")
    b.put(cube.inputs["Size"], b.comb(length, b.math("MULTIPLY", half, 2.0), HEIGHT))
    us = b.sep(u)
    cw = b.sep(b.vec("ADD", o, b.scale(u, b.math("MULTIPLY", length, 0.5))))
    origin = b.new("FunctionNodeTransformPoint")                  # the object's origin in world: the box's middle z
    b.put(origin.inputs["Vector"], (0.0, 0.0, 0.0))
    b.put(origin.inputs["Transform"], m_own)
    place = b.new("FunctionNodeCombineTransform")
    b.put(place.inputs["Translation"], b.comb(cw["X"], cw["Y"], b.sep(origin.outputs[0])["Z"]))
    b.put(place.inputs["Rotation"], b.comb(0.0, 0.0, b.math("ARCTAN2", us["Y"], us["X"])))
    mm = b.new("FunctionNodeMatrixMultiply")
    b.put(mm.inputs[0], m_inv)
    b.put(mm.inputs[1], place.outputs[0])
    put_cube = b.new("GeometryNodeSetPosition")
    b.put(put_cube.inputs["Geometry"], cube.outputs["Mesh"])
    tc = b.new("FunctionNodeTransformPoint")
    b.put(tc.inputs["Vector"], b.new("GeometryNodeInputPosition").outputs[0])
    b.put(tc.inputs["Transform"], mm.outputs[0])
    b.put(put_cube.inputs["Position"], tc.outputs[0])
    boo = b.new("GeometryNodeMeshBoolean", operation="DIFFERENCE", solver="EXACT")
    b.put(boo.inputs["Mesh 1"], ext.outputs["Mesh"])
    b.put(boo.inputs["Mesh 2"], put_cube.outputs["Geometry"])

    # --- the one that is asked for (a Switch works out only the side it passes on)
    is_live = b.new("FunctionNodeCompare", data_type="INT", operation="EQUAL")
    b.put(is_live.inputs["A"], way)
    is_live.inputs["B"].default_value = LIVE
    is_exact = b.new("FunctionNodeCompare", data_type="INT", operation="EQUAL")
    b.put(is_exact.inputs["A"], way)
    is_exact.inputs["B"].default_value = EXACT
    out = b.switch(is_exact.outputs[0], b.switch(is_live.outputs[0], stored.outputs[0], live.outputs[0]),
                   boo.outputs["Mesh"])
    b.put(gout.inputs["Geometry"], out)
    return ng


def _ids(mod) -> dict:
    return {i.name: i.identifier for i in mod.node_group.interface.items_tree
            if getattr(i, "item_type", "") == "SOCKET" and i.in_out == "INPUT"}


def set_cut(ob, box, drop: float = 1.0, way: int = STORED, band=1.0) -> None:
    """The box open in the 3D view on ``ob`` (Solid and Material Preview): a viewport-only modifier, last in the stack.
    ``box`` None takes it off. ``drop`` (m): how far the points inside go down; ``way``: STORED / LIVE / EXACT (see the
    module's text); ``band``: the stored way's reach round the box (``store``)."""
    mod = ob.modifiers.get(MOD)
    if box is None:
        if mod is not None:
            ob.modifiers.remove(mod)
        if ob.type == "MESH" and ob.data.attributes.get(ATTR) is not None:
            ob.data.attributes.remove(ob.data.attributes[ATTR])
        return
    if mod is None or mod.type != "NODES":
        if mod is not None:
            ob.modifiers.remove(mod)
        mod = ob.modifiers.new(MOD, "NODES")
    if mod.node_group is None or mod.node_group.name != GROUP:
        mod.node_group = _group()
    mod.show_render = False
    mod.show_in_editmode = False
    mod.show_viewport = True
    if way == STORED:
        store(ob, box, drop, band)
    ids = _ids(mod)
    inputs = mod.properties.inputs
    for name, value in (("Origin", (float(box["origin"][0]), float(box["origin"][1]), 0.0)),
                        ("Direction", (float(box["dir"][0]), float(box["dir"][1]), 0.0)),
                        ("Size", (float(box["length"]), float(box["width"]) / 2.0, 0.0)),
                        ("Drop", float(drop)), ("Way", int(way))):
        getattr(inputs, ids[name]).value = value
    if list(ob.modifiers)[-1] != mod:                       # last: after the waves
        ob.modifiers.move(list(ob.modifiers).index(mod), len(ob.modifiers) - 1)
    ob.update_tag()


def old_cut_objects() -> list:
    """Objects whose view cut is an older one (0.2.153 deleted the faces: +6 ms a frame on a Detailed sea)."""
    return [ob for ob in bpy.data.objects
            if ob.type == "MESH" and (m := ob.modifiers.get(MOD)) is not None and m.type == "NODES"
            and (m.node_group is None or m.node_group.name != GROUP)]

