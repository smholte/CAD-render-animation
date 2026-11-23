"""Study 0300: the invented test model as a Blender scene (Blender 5.2.3, also as a Python module) – four stations
side by side on a bed, each moved by a keyed "joint" (a plain keyed empty stands in for the app's joint):

1. a coil spring between a base plate and a top plate that slides down (compression) and up again;
2. a rubber buffer on the bed, hit by a stop on a carriage that slides along;
3. a bellows (boot) on a cylinder: cuffs on the barrel's end and on the rod's eye, the rod goes in and out;
4. a tyre on a wheel that rolls along the ground while the load on it goes up and down.

``build(variant)``: variant "soft" = the deformers on, "rigid" = as the app shows it today.
"""

from __future__ import annotations

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import nodes  # noqa: E402
import read  # noqa: E402
import shapes  # noqa: E402

FRAMES = 96


def mesh_object(name, vfn, coll, mat=None, at=(0, 0, 0)):
    v, f, n = vfn[:3]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", np.asarray(v, np.float32).reshape(-1))
    me.loops.add(len(f) * 3)
    me.loops.foreach_set("vertex_index", np.asarray(f, np.int32).reshape(-1))
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    a = me.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", np.asarray(n, np.float32).reshape(-1))
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = at
    coll.objects.link(ob)
    return ob


def material(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def key(ob, path, frames_values, index=-1):
    for fr, val in frames_values:
        if index >= 0:
            getattr(ob, path)[index] = val
            ob.keyframe_insert(path, index=index, frame=fr)
        else:
            setattr(ob, path, val)
            ob.keyframe_insert(path, frame=fr)


def set_inputs(mod, **vals):
    """Modifier inputs by name (Blender 5.2: ``mod.properties.inputs.<identifier>.value`` or ``mod[identifier]``)."""
    for item in mod.node_group.interface.items_tree:
        if getattr(item, "in_out", "") != "INPUT" or item.name not in vals:
            continue
        val = vals[item.name]
        try:
            getattr(mod.properties.inputs, item.identifier).value = val
        except Exception:
            mod[item.identifier] = val


def build(variant="soft", helix=1.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    coll = sc.collection
    steel = material("steel", (0.62, 0.64, 0.66), 0.3, 1.0)
    paint = material("paint", (0.12, 0.31, 0.47), 0.45)
    spring_m = material("spring", (0.75, 0.55, 0.18), 0.3, 1.0)
    rubber = material("rubber", (0.03, 0.03, 0.03), 0.65)
    bed = mesh_object("Bed", shapes.box(1.00, 0.30, 0.02, 0.35, 0, -0.02), coll, paint)
    out = {"bed": bed}
    soft = variant == "soft"

    # 1 · spring between two plates; the top plate slides down 30 mm and back
    x = 0.0
    base = mesh_object("Spring base", shapes.box(0.08, 0.08, 0.01, 0, 0, 0), coll, steel, at=(x, 0, 0))
    top = mesh_object("Spring top", shapes.box(0.08, 0.08, 0.01, 0, 0, 0), coll, steel, at=(x, 0, 0.09))
    v, f, n, facts = shapes.spring()
    spr = mesh_object("Compression spring", (v, f, n), coll, spring_m, at=(x, 0, 0.01))
    key(top, "location", [(1, 0.09), (40, 0.06), (56, 0.06), (96, 0.09)], index=2)
    out["spring"] = (spr, base, top, facts)
    if soft:
        r = read.spring(v, f)
        u = Vector(r["axis"])
        org = Vector(r["origin"])
        ref = Vector(r["ref"])
        side = u.cross(ref) * (1 if r["hand"] == "right" else -1)
        g = bpy.data.node_groups.get("FR soft axial") or nodes.axial()
        mod = spr.modifiers.new("FR soft", "NODES")
        mod.node_group = g
        flip = 1 if u.z > 0 else -1
        set_inputs(mod, **{"Seat A": base, "Seat A point": (0, 0, 0.01), "Seat B": top, "Seat B point": (0, 0, 0),
                           "Origin": org, "Axis": u, "Ref": ref, "Side": side, "Free length": r["free"],
                           "Active from": r["z1"], "Active to": r["z2"], "Phase": r["phi1"], "Pitch": r["pitch"],
                           "Wire": r["wire"], "Helix": helix, "Shortest": r["solid"]})
        out["spring_read"] = r

    # 2 · rubber buffer on the bed, a carriage with a stop comes down onto it
    x = 0.30
    v, f, n = shapes.buffer()
    buf = mesh_object("Rubber buffer", (v, f, n), coll, rubber, at=(x, 0, 0))
    car = mesh_object("Carriage", shapes.box(0.10, 0.10, 0.02, 0, 0, 0), coll, paint, at=(x, 0, 0.045))
    stop = mesh_object("Stop", shapes.box(0.04, 0.04, 0.012, 0, 0, -0.012), coll, steel)
    stop.parent = car
    key(car, "location", [(1, 0.045), (36, 0.0285), (60, 0.0285), (96, 0.045)], index=2)   # 0.008 into 0.025 mm
    out["buffer"] = (buf, car, stop)
    if soft:
        g = bpy.data.node_groups.get("FR soft squeeze") or nodes.squeeze()
        mod = buf.modifiers.new("FR soft", "NODES")
        mod.node_group = g
        set_inputs(mod, **{"Presser": stop, "Presser point": (0, 0, -0.012), "Origin": (0, 0, 0),
                           "Axis": (0, 0, 1), "Free height": 0.025, "Bulge": 1.0})

    # 3 · bellows on a cylinder: barrel lying along +x, rod goes in and out 40 mm
    x = 0.55
    barrel = mesh_object("Barrel", shapes.revolve([(0, 0), (0.03, 0), (0.03, 0.16), (0, 0.16)]), coll, paint,
                         at=(x, 0, 0.05))
    barrel.rotation_euler = (0, math.pi / 2, 0)
    rod_end = bpy.data.objects.new("Rod end", None)
    coll.objects.link(rod_end)
    rod_end.location = (x + 0.16 + 0.12, 0, 0.05)
    rod_end.rotation_euler = (0, math.pi / 2, 0)
    rod = mesh_object("Rod", shapes.revolve([(0, -0.20), (0.012, -0.20), (0.012, 0.0), (0, 0.0)]), coll, steel)
    rod.parent = rod_end
    eye = mesh_object("Rod eye", shapes.revolve([(0, 0), (0.02, 0), (0.02, 0.03), (0, 0.03)]), coll, steel)
    eye.parent = rod_end
    (bv, bf, bn), bfacts = shapes.bellows(length=0.12)
    bel = mesh_object("Bellows", (bv, bf, bn), coll, rubber, at=(x + 0.16, 0, 0.05))
    bel.rotation_euler = (0, math.pi / 2, 0)
    key(rod_end, "location", [(1, x + 0.28), (40, x + 0.24), (56, x + 0.24), (80, x + 0.31), (96, x + 0.28)], index=0)
    out["bellows"] = (bel, barrel, rod_end, bfacts)
    if soft:
        g = bpy.data.node_groups.get("FR soft axial") or nodes.axial()
        mod = bel.modifiers.new("FR soft", "NODES")
        mod.node_group = g
        set_inputs(mod, **{"Seat A": barrel, "Seat A point": (0, 0, 0.16), "Seat B": rod_end, "Seat B point": (0, 0, 0),
                           "Origin": (0, 0, 0), "Axis": (0, 0, 1), "Free length": 0.12,
                           "Active from": bfacts["cuff"], "Active to": 0.12 - bfacts["cuff"], "Helix": 0.0,
                           "Pitch": 1.0, "Wire": 1.0, "Shortest": 0.03})

    # 4 · tyre on a wheel rolling along x; the axle goes up and down (a load bouncing)
    x = 1.6
    hub = bpy.data.objects.new("Axle", None)
    coll.objects.link(hub)
    hub.location = (x, 0, 0.3)
    v, f, n = shapes.tyre()
    ty = mesh_object("Tyre", (v, f, n), coll, rubber)
    ty.parent = hub
    ty.rotation_euler = (math.pi / 2, 0, 0)
    rim = mesh_object("Rim", shapes.revolve([(0, -0.09), (0.2, -0.09), (0.2, 0.09), (0, 0.09)]), coll, steel)
    rim.parent = hub
    rim.rotation_euler = (math.pi / 2, 0, 0)
    gro = bpy.data.objects.new("Ground", None)
    coll.objects.link(gro)
    gro.location = (0, 0, 0.0)
    key(hub, "location", [(1, 0.29), (30, 0.265), (50, 0.29), (70, 0.255), (96, 0.29)], index=2)
    key(hub, "location", [(1, x - 0.1), (96, x + 0.1)], index=0)
    key(hub, "rotation_euler", [(1, 0.0), (96, -0.2 / 0.3)], index=1)
    out["tyre"] = (ty, hub, gro)
    if soft:
        g = bpy.data.node_groups.get("FR soft ground") or nodes.ground()
        mod = ty.modifiers.new("FR soft", "NODES")
        mod.node_group = g
        set_inputs(mod, **{"Ground": gro, "Centre": (0, 0, 0), "Axle": (0, 0, 1), "Radius": 0.30,
                           "Wall band": 0.09, "Bulge": 0.6})
    for fc in [a for ob in bpy.data.objects if ob.animation_data and ob.animation_data.action
               for a in _fcurves(ob)]:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    return out


def _fcurves(ob):
    act = ob.animation_data.action
    try:
        return list(act.fcurves)
    except AttributeError:          # 5.x layered actions
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out += list(bag.fcurves)
        return out


def evaluated(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    v = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", v)
    me.calc_loop_triangles()
    f = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", f)
    f = f.reshape(-1, 3)
    e.to_mesh_clear()
    return v.reshape(-1, 3).astype(np.float64), f
