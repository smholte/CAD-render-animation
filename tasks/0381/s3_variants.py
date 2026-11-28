"""0381 prototype (throw-away, not app code): turn the imported stress model into a variant with fewer objects.
python s3_variants.py <in.blend> <variant> <out.blend>
variants: base (unchanged) · fasteners_gn · repeated_gn · rigid_gn · rigid_joined · fasteners_off
  *_gn      : the parts become instances of a Geometry Nodes modifier on ONE object per carrier (points with a FLOAT4X4
              local matrix + a prototype index; one hidden prototype object per mesh + look); mesh data stays shared
  rigid_*   : every part, carrier = the nearest joint mover above it (or the model root) = one object per rigid body
  fasteners_gn / repeated_gn : carrier = the part's own parent (sub-assembly empty or joint mover)
  rigid_joined : one real joined mesh per rigid body, face attribute fr_part = which part (picking / looks / paint)
  fasteners_off : the fasteners stay objects but are 'Disable in viewports' + renders (option 3: left out)"""
import json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import numpy as np
import bpy, addon_utils  # noqa
import fresing_render
src, variant, out = sys.argv[1:4]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
bpy.ops.wm.open_mainfile(filepath=src)
from fresing_render.blender import build
scene = bpy.context.scene
parts = list(build.iter_parts(scene))
movers = {j.motion for j in scene.fresing.joints if j.motion}
root = build.model_roots(scene)[0]
t0 = time.time()

def is_fastener(o):
    return o.get("fr_group", "").startswith("Fasteners")

def carrier_rigid(o):
    p = o.parent
    while p is not None and p not in movers and p is not root:
        p = p.parent
    return p or root

def node_tree(protos):
    ng = bpy.data.node_groups.new("FR0381 instances", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes; L = ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
    ci = N.new("GeometryNodeCollectionInfo"); ci.inputs["Collection"].default_value = protos
    ci.inputs["Separate Children"].default_value = True; ci.inputs["Reset Children"].default_value = True
    ci.transform_space = "ORIGINAL"
    iop = N.new("GeometryNodeInstanceOnPoints"); iop.inputs["Pick Instance"].default_value = True
    idx = N.new("GeometryNodeInputNamedAttribute"); idx.data_type = "INT"; idx.inputs["Name"].default_value = "fr_proto"
    mat = N.new("GeometryNodeInputNamedAttribute"); mat.data_type = "FLOAT4X4"; mat.inputs["Name"].default_value = "fr_m"
    sit = N.new("GeometryNodeSetInstanceTransform")
    L.new(gi.outputs[0], iop.inputs["Points"]); L.new(ci.outputs[0], iop.inputs["Instance"])
    L.new(idx.outputs[0], iop.inputs["Instance Index"])
    L.new(iop.outputs[0], sit.inputs["Instances"]); L.new(mat.outputs[0], sit.inputs["Transform"])
    L.new(sit.outputs[0], go.inputs[0])
    return ng

def object_mats(o):
    return tuple((s.link, s.material.name if s.material else "") for s in o.material_slots)

def to_instances(chosen, carrier_of):
    protos = bpy.data.collections.new("FR0381 prototypes")
    unlinked = variant.endswith("_x")      # *_x: the prototype collection is in no scene at all
    if not unlinked:
        scene.collection.children.link(protos)
    key_to_idx, proto_obs = {}, []
    groups = {}
    for o in chosen:
        k = (o.data.name, object_mats(o))
        if k not in key_to_idx:
            key_to_idx[k] = len(proto_obs)
            p = bpy.data.objects.new(f"FRP {len(proto_obs):05d}", o.data)
            for i, s in enumerate(o.material_slots):
                p.material_slots[i].link = s.link
                if s.link == "OBJECT":
                    p.material_slots[i].material = s.material
            protos.objects.link(p)
            proto_obs.append(p)
        groups.setdefault(carrier_of(o), []).append(o)
    # prototypes: in the scene, but not drawn or rendered themselves (Collection Info still reads them)
    if not unlinked:
        lc = bpy.context.view_layer.layer_collection.children[protos.name]
        lc.hide_viewport = True
        protos.hide_render = True
    else:
        protos.use_fake_user = True
    ng = node_tree(protos)
    made = 0
    part_map = {}
    for car, obs in groups.items():
        cw_inv = car.matrix_world.inverted()
        me = bpy.data.meshes.new(f"FR0381 points {car.name}")
        me.vertices.add(len(obs))
        M = np.empty((len(obs), 4, 4), np.float32)
        P = np.empty(len(obs), np.int32)
        for i, o in enumerate(obs):
            M[i] = np.array(cw_inv @ o.matrix_world)
            P[i] = key_to_idx[(o.data.name, object_mats(o))]
        me.vertices.foreach_set("co", np.ascontiguousarray(M[:, :3, 3]).ravel())
        a = me.attributes.new("fr_m", "FLOAT4X4", "POINT"); a.data.foreach_set("value", np.ascontiguousarray(M.transpose(0, 2, 1)).ravel())
        me.attributes.new("fr_proto", "INT", "POINT").data.foreach_set("value", P)
        ob = bpy.data.objects.new(f"FR0381 inst {car.name}", me)
        ob.parent = car
        ob.matrix_parent_inverse.identity()
        ob["fr_parts"] = [o.get("fr_uid", o.name) for o in obs]      # instance i = this part (pick / looks)
        scene.collection.objects.link(ob)
        mod = ob.modifiers.new("FR instances", "NODES"); mod.node_group = ng
        made += 1
    bpy.data.batch_remove(chosen)
    return made, len(proto_obs)

def joined(chosen, carrier_of):
    groups = {}
    for o in chosen:
        groups.setdefault(carrier_of(o), []).append(o)
    made = 0
    for car, obs in groups.items():
        cw_inv = car.matrix_world.inverted()
        mats, mat_idx = [], {}
        V, Fv, Floop, Fmat, Fpart, N = [], [], [], [], [], []
        voff = 0
        for pi, o in enumerate(obs):
            me = o.data
            nv = len(me.vertices); nl = len(me.loops); nf = len(me.polygons)
            co = np.empty(nv * 3, np.float32); me.vertices.foreach_get("co", co)
            Mx = np.array(cw_inv @ o.matrix_world, np.float64)
            co = co.reshape(-1, 3) @ Mx[:3, :3].T + Mx[:3, 3]
            V.append(co)
            if "custom_normal" in me.attributes and me.attributes["custom_normal"].domain == "POINT":
                n = np.empty(nv * 3, np.float32); me.attributes["custom_normal"].data.foreach_get("vector", n)
                N.append(n.reshape(-1, 3) @ Mx[:3, :3].T)
            else:
                N.append(np.zeros((nv, 3), np.float32))
            lv = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", lv); Fv.append(lv + voff)
            ls = np.empty(nf, np.int32); me.polygons.foreach_get("loop_total", ls); Floop.append(ls)
            mi = np.empty(nf, np.int32); me.polygons.foreach_get("material_index", mi)
            remap = []
            for s in o.material_slots:
                m = s.material
                if m not in mat_idx:
                    mat_idx[m] = len(mats); mats.append(m)
                remap.append(mat_idx[m])
            Fmat.append(np.array(remap or [0], np.int32)[mi] if remap else mi)
            Fpart.append(np.full(nf, pi, np.int32))
            voff += nv
        V = np.concatenate(V); Fv = np.concatenate(Fv); Floop = np.concatenate(Floop)
        me = bpy.data.meshes.new(f"FR0381 joined {car.name}")
        me.vertices.add(len(V)); me.vertices.foreach_set("co", V.astype(np.float32).ravel())
        me.loops.add(len(Fv)); me.loops.foreach_set("vertex_index", Fv)
        me.polygons.add(len(Floop))
        starts = np.concatenate([[0], np.cumsum(Floop)[:-1]]).astype(np.int32)
        me.polygons.foreach_set("loop_start", starts); me.polygons.foreach_set("loop_total", Floop)
        me.polygons.foreach_set("material_index", np.concatenate(Fmat))
        me.update(calc_edges=True)
        me.attributes.new("fr_part", "INT", "FACE").data.foreach_set("value", np.concatenate(Fpart))
        cn = me.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")
        cn.data.foreach_set("vector", np.concatenate(N).astype(np.float32).ravel())
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(f"FR0381 body {car.name}", me)
        ob.parent = car; ob.matrix_parent_inverse.identity()
        ob["fr_parts"] = [o.get("fr_uid", o.name) for o in obs]      # fr_part i = this part
        scene.collection.objects.link(ob)
        made += 1
    bpy.data.batch_remove(chosen)
    return made, 0

def library(chosen, carrier_of):
    """rigid_lib: every distinct (mesh, look) once in ONE library mesh (face attribute fr_proto), not in the scene;
    each carrier's GN splits it into instances (Split to Instances, by fr_proto) and puts them on its points."""
    key_to_idx, keys = {}, []
    for o in chosen:
        k = (o.data.name, object_mats(o))
        if k not in key_to_idx:
            key_to_idx[k] = len(keys); keys.append(o)
    # the library: a joined mesh of the prototypes, each at its own origin
    mats, mat_idx = [], {}
    V, Fv, Floop, Fmat, Fpro, N = [], [], [], [], [], []
    voff = 0
    for pi, o in enumerate(keys):
        me = o.data
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); V.append(co.reshape(-1, 3))
        if "custom_normal" in me.attributes and me.attributes["custom_normal"].domain == "POINT":
            n = np.empty(len(me.vertices) * 3, np.float32); me.attributes["custom_normal"].data.foreach_get("vector", n)
            N.append(n.reshape(-1, 3))
        else:
            N.append(np.zeros((len(me.vertices), 3), np.float32))
        lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv); Fv.append(lv + voff)
        ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", ls); Floop.append(ls)
        mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
        remap = []
        for sl in o.material_slots:
            if sl.material not in mat_idx:
                mat_idx[sl.material] = len(mats); mats.append(sl.material)
            remap.append(mat_idx[sl.material])
        Fmat.append(np.array(remap, np.int32)[mi] if remap else mi)
        Fpro.append(np.full(len(ls), pi, np.int32))
        voff += len(me.vertices)
    V = np.concatenate(V); Fv = np.concatenate(Fv); Floop = np.concatenate(Floop)
    lib = bpy.data.meshes.new("FR0381 library")
    lib.vertices.add(len(V)); lib.vertices.foreach_set("co", V.ravel())
    lib.loops.add(len(Fv)); lib.loops.foreach_set("vertex_index", Fv)
    lib.polygons.add(len(Floop))
    lib.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(Floop)[:-1]]).astype(np.int32))
    lib.polygons.foreach_set("loop_total", Floop); lib.polygons.foreach_set("material_index", np.concatenate(Fmat))
    lib.update(calc_edges=True)
    lib.attributes.new("fr_proto", "INT", "FACE").data.foreach_set("value", np.concatenate(Fpro))
    lib.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", np.concatenate(N).ravel())
    for m in mats:
        lib.materials.append(m)
    libob = bpy.data.objects.new("FR0381 library", lib)       # in no scene
    libob.use_fake_user = True
    ng = bpy.data.node_groups.new("FR0381 library instances", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    Nn, Ll = ng.nodes, ng.links
    gi, go = Nn.new("NodeGroupInput"), Nn.new("NodeGroupOutput")
    oi = Nn.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = libob; oi.transform_space = "ORIGINAL"
    sp = Nn.new("GeometryNodeSplitToInstances"); sp.domain = "FACE"
    gid = Nn.new("GeometryNodeInputNamedAttribute"); gid.data_type = "INT"; gid.inputs["Name"].default_value = "fr_proto"
    iop = Nn.new("GeometryNodeInstanceOnPoints"); iop.inputs["Pick Instance"].default_value = True
    idx = Nn.new("GeometryNodeInputNamedAttribute"); idx.data_type = "INT"; idx.inputs["Name"].default_value = "fr_proto"
    mat = Nn.new("GeometryNodeInputNamedAttribute"); mat.data_type = "FLOAT4X4"; mat.inputs["Name"].default_value = "fr_m"
    sit = Nn.new("GeometryNodeSetInstanceTransform")
    Ll.new(oi.outputs["Geometry"], sp.inputs["Geometry"]); Ll.new(gid.outputs[0], sp.inputs["Group ID"])
    Ll.new(gi.outputs[0], iop.inputs["Points"]); Ll.new(sp.outputs["Instances"], iop.inputs["Instance"])
    Ll.new(idx.outputs[0], iop.inputs["Instance Index"])
    Ll.new(iop.outputs[0], sit.inputs["Instances"]); Ll.new(mat.outputs[0], sit.inputs["Transform"])
    Ll.new(sit.outputs[0], go.inputs[0])
    groups = {}
    for o in chosen:
        groups.setdefault(carrier_of(o), []).append(o)
    for car, obs in groups.items():
        cw_inv = car.matrix_world.inverted()
        me = bpy.data.meshes.new(f"FR0381 points {car.name}")
        me.vertices.add(len(obs))
        M = np.array([np.array(cw_inv @ o.matrix_world) for o in obs], np.float32)
        P = np.array([key_to_idx[(o.data.name, object_mats(o))] for o in obs], np.int32)
        me.vertices.foreach_set("co", np.ascontiguousarray(M[:, :3, 3]).ravel())
        me.attributes.new("fr_m", "FLOAT4X4", "POINT").data.foreach_set("value", np.ascontiguousarray(M.transpose(0, 2, 1)).ravel())
        me.attributes.new("fr_proto", "INT", "POINT").data.foreach_set("value", P)
        for m in mats:
            me.materials.append(m)          # the instances' faces use the library's slots
        ob = bpy.data.objects.new(f"FR0381 inst {car.name}", me)
        ob.parent = car; ob.matrix_parent_inverse.identity()
        ob["fr_parts"] = [o.get("fr_uid", o.name) for o in obs]
        scene.collection.objects.link(ob)
        ob.modifiers.new("FR instances", "NODES").node_group = ng
    bpy.data.batch_remove(chosen)
    return len(groups), len(keys)

info = {"variant": variant, "parts_before": len(parts), "objects_before": len(bpy.data.objects)}
base_variant = variant[:-2] if variant.endswith("_x") else variant
if base_variant == "fasteners_gn":
    ch = [o for o in parts if is_fastener(o)]
    info["moved_into"], info["prototypes"] = to_instances(ch, lambda o: o.parent or root)
elif base_variant == "repeated_gn":
    ch = [o for o in parts if o.data.users >= 4]
    info["moved_into"], info["prototypes"] = to_instances(ch, lambda o: o.parent or root)
elif variant == "rigid_lib":
    ch = parts
    info["moved_into"], info["prototypes"] = library(ch, carrier_rigid)
elif base_variant == "rigid_gn":
    ch = parts
    info["moved_into"], info["prototypes"] = to_instances(ch, carrier_rigid)
elif variant == "rigid_joined":
    ch = parts
    info["moved_into"], info["prototypes"] = joined(ch, carrier_rigid)
elif variant == "fasteners_off":
    ch = [o for o in parts if is_fastener(o)]
    for o in ch:
        o.hide_viewport = True; o.hide_render = True
    info["moved_into"] = 0
else:
    ch = []
info["parts_changed"] = len(ch)
info["make_s"] = round(time.time() - t0, 2)
bpy.context.view_layer.update()
info["objects_after"] = len(bpy.data.objects)
bpy.ops.wm.save_as_mainfile(filepath=out)
json.dump(info, open(out + ".variant.json", "w"), indent=1)
print(json.dumps(info))
