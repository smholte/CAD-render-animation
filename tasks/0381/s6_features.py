"""0381: what still works when parts are Geometry Nodes instances on one object (Blender as a module, no app).
A synthetic scene: 2 prototype meshes, 200 parts as instances of one carrier object. Checks:
 pick   - scene.ray_cast gives the prototype object + the instance matrix -> the part by matching the matrix
 hide   - one part hidden by a point attribute (Instance on Points' Selection)
 look   - a colour per part from a point attribute read by the material (Attribute node, type INSTANCER), Cycles
 eevee  - the same picture with EEVEE (skipped when it cannot start: no GL here)"""
import json, sys, time
import numpy as np
import bpy, bmesh
from mathutils import Matrix, Vector
out = sys.argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
protos = bpy.data.collections.new("protos")
P = []
for i, size in enumerate((0.4, 0.25)):
    me = bpy.data.meshes.new(f"m{i}"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=size); bm.to_mesh(me); bm.free()
    mat = bpy.data.materials.new(f"look{i}"); mat.use_nodes = True
    nt = mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_type = "INSTANCER"; at.attribute_name = "fr_tint"
    nt.links.new(at.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.append(mat)
    o = bpy.data.objects.new(f"FRP {i:05d}", me); protos.objects.link(o); P.append(o)
n = 200
M = np.zeros((n, 4, 4), np.float32); idx = np.zeros(n, np.int32); tint = np.zeros((n, 4), np.float32)
for k in range(n):
    m = Matrix.Translation(((k % 20) * 1.0, (k // 20) * 1.0, 0)) @ Matrix.Rotation(0.1 * k, 4, "Z")
    M[k] = np.array(m); idx[k] = k % 2; tint[k] = (k / n, 0.2, 1 - k / n, 1)
me = bpy.data.meshes.new("pts"); me.vertices.add(n); me.vertices.foreach_set("co", np.ascontiguousarray(M[:, :3, 3]).ravel())
me.attributes.new("fr_m", "FLOAT4X4", "POINT").data.foreach_set("value", np.ascontiguousarray(M.transpose(0, 2, 1)).ravel())
me.attributes.new("fr_proto", "INT", "POINT").data.foreach_set("value", idx)
me.attributes.new("fr_tint", "FLOAT_COLOR", "POINT").data.foreach_set("color", tint.ravel())
show = np.ones(n, bool); me.attributes.new("fr_show", "BOOLEAN", "POINT").data.foreach_set("value", show)
car = bpy.data.objects.new("carrier", me); sc.collection.objects.link(car)
car.matrix_world = Matrix.Translation((5, -3, 1))
ng = bpy.data.node_groups.new("inst", "GeometryNodeTree")
ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
N, L = ng.nodes, ng.links
gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
ci = N.new("GeometryNodeCollectionInfo"); ci.inputs["Collection"].default_value = protos
ci.inputs["Separate Children"].default_value = True; ci.inputs["Reset Children"].default_value = True
iop = N.new("GeometryNodeInstanceOnPoints"); iop.inputs["Pick Instance"].default_value = True
def named(t, name):
    a = N.new("GeometryNodeInputNamedAttribute"); a.data_type = t; a.inputs["Name"].default_value = name; return a
sit = N.new("GeometryNodeSetInstanceTransform")
L.new(gi.outputs[0], iop.inputs["Points"]); L.new(ci.outputs[0], iop.inputs["Instance"])
L.new(named("INT", "fr_proto").outputs[0], iop.inputs["Instance Index"])
L.new(named("BOOLEAN", "fr_show").outputs[0], iop.inputs["Selection"])
L.new(iop.outputs[0], sit.inputs["Instances"]); L.new(named("FLOAT4X4", "fr_m").outputs[0], sit.inputs["Transform"])
L.new(sit.outputs[0], go.inputs[0])
car.modifiers.new("inst", "NODES").node_group = ng
vl = bpy.context.view_layer; vl.update()
res = {}
dg = bpy.context.evaluated_depsgraph_get()
res["instances"] = sum(1 for i in dg.object_instances if i.is_instance)

# pick: rays down onto 50 parts; the part is found from the prototype and the instance matrix
W = np.array(car.matrix_world) @ M          # every part's world matrix
ok = 0; t0 = time.perf_counter()
for k in range(0, n, 4):
    org = Vector(W[k][:3, 3]) + Vector((0, 0, 5))
    hit, loc, nrm, face, ob, Mi = bpy.context.scene.ray_cast(dg, org, Vector((0, 0, -1)))
    if not hit:
        continue
    cand = np.where(idx == int(ob.name.split()[-1]))[0]
    d = np.abs(W[cand] - np.array(Mi)).reshape(len(cand), -1).max(axis=1)
    found = int(cand[np.argmin(d)]) if d.min() < 1e-4 else -1
    ok += found == k
res["pick_found_right_part"] = f"{ok} of {len(range(0, n, 4))}"
res["pick_ms_each"] = round((time.perf_counter() - t0) * 1000 / len(range(0, n, 4)), 3)

# hide one part
show[7] = False; me.attributes["fr_show"].data.foreach_set("value", show); me.update(); vl.update()
dg = bpy.context.evaluated_depsgraph_get()
res["instances_after_hiding_one"] = sum(1 for i in dg.object_instances if i.is_instance)

# a colour per part in a render
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
cam.location = (14.5, 1.5, 30); sc.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sc.render.resolution_x, sc.render.resolution_y = 160, 120
for eng in ("CYCLES", "BLENDER_EEVEE"):
    try:
        sc.render.engine = eng
        if eng == "CYCLES":
            sc.cycles.samples = 4; sc.cycles.device = "CPU"
        sc.render.filepath = out.replace(".json", f"_{eng}.png")
        bpy.ops.render.render(write_still=True)
        px = np.array(bpy.data.images.load(sc.render.filepath).pixels[:]).reshape(120, 160, 4)
        cols = px[px[..., 3] > 0][:, :3]
        res[f"{eng} distinct colours"] = int(len(np.unique(np.round(cols * 20), axis=0)))
    except Exception as e:  # noqa
        res[f"{eng}"] = "could not render: " + str(e)[:80]
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res))
