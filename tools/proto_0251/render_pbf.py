"""Prototype 0251: draw the particle bake (pbf.py) as a liquid surface – Geometry Nodes: Points to Volume ->
Volume to Mesh, smooth – with the same liquid material. Used by render_s.py (method pbf)."""

from __future__ import annotations

import bpy
import numpy as np

import bl


def surface_object(name, mat, spacing):
    me = bl.mesh(name, np.zeros((0, 3)))
    ob = bl.obj(name, me)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    m2p = n.new("GeometryNodeMeshToPoints")
    m2p.inputs["Radius"].default_value = 0.75 * spacing
    p2v = n.new("GeometryNodePointsToVolume")
    p2v.inputs["Density"].default_value = 1.0
    if "Voxel Size" in p2v.inputs:
        p2v.inputs["Voxel Size"].default_value = 0.4 * spacing
    v2m = n.new("GeometryNodeVolumeToMesh")
    if "Threshold" in v2m.inputs:
        v2m.inputs["Threshold"].default_value = 0.3
    sm = n.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = mat
    sh = n.new("GeometryNodeSetShadeSmooth")
    L = ng.links
    L.new(gi.outputs[0], m2p.inputs["Mesh"])
    L.new(m2p.outputs[0], p2v.inputs[0])
    L.new(p2v.outputs[0], v2m.inputs[0])
    L.new(v2m.outputs[0], sh.inputs[0])
    L.new(sh.outputs[0], sm.inputs[0])
    L.new(sm.outputs[0], go.inputs[0])
    mod = ob.modifiers.new("Liquid", "NODES")
    mod.node_group = ng
    return ob


def setup(npz, sc, carrier, place):
    D = np.load(npz)
    sp = float(D["spacing"])
    mat = bl.liquid_material("Liquid pbf")
    # no depth attribute on a meshed volume: full liquid look
    nt = mat.node_tree
    for l in list(nt.links):
        if l.to_node.name == "Mix Shader" and l.to_socket.name == "Fac":
            nt.links.remove(l)
    nt.nodes["Mix Shader"].inputs["Fac"].default_value = 1.0
    ob = surface_object("Liquid particles", mat, sp)
    off = np.concatenate([[0], np.cumsum(D["counts"])])
    pos = D["pos"]

    def update(f):
        f = min(f, len(D["counts"]) - 1)
        place(f)
        P = pos[off[f]:off[f + 1]]
        me = ob.data
        me.clear_geometry()
        if len(P):
            me.vertices.add(len(P))
            me.vertices.foreach_set("co", P.astype(np.float32).ravel())
        me.update()
    return update
