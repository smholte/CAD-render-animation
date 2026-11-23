"""Study 0303: writes the Human Base Meshes bodies (male / female realistic: base mesh at multires levels 0-2, eyes) as
.npz files for realistic.py / weights_bpy.py. Run in real Blender with scripts off, on the bundle from
https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip (CC0):
  blender -b --factory-startup --disable-autoexec human_base_meshes_bundle.blend --python export_hbm.py -- <out dir>
Nothing of the bundle is committed."""
import bpy, numpy as np, sys
out = sys.argv[sys.argv.index("--")+1]
dg = bpy.context.evaluated_depsgraph_get()
for name in ("GEO-body_male_realistic", "GEO-body_female_realistic"):
    ob = bpy.data.objects[name]
    print(name, "uv:", [u.name for u in ob.data.uv_layers], "matrix", [list(r) for r in ob.matrix_world])
    eyes = [c for c in ob.children if c.type == "MESH"]
    for lvl in (0, 1, 2):
        for m in ob.modifiers:
            if m.type == "MULTIRES":
                m.levels = lvl; m.render_levels = lvl
        dg.update()
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        n = len(me.vertices); co = np.zeros(n*3, np.float32); me.vertices.foreach_get("co", co)
        lt = []; 
        sizes = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", sizes)
        loops = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
        uv = None
        if me.uv_layers:
            uv = np.zeros(len(me.loops)*2, np.float32); me.uv_layers[0].data.foreach_get("uv", uv)
        co = co.reshape(-1,3) @ np.asarray(ob.matrix_world)[:3,:3].T + np.asarray(ob.matrix_world)[:3,3]
        d = dict(co=co, sizes=sizes, loops=loops)
        if uv is not None: d["uv"] = uv
        np.savez_compressed(f"{out}/{name}_L{lvl}.npz", **d)
        print(name, lvl, n, len(sizes), co.min(0).round(3), co.max(0).round(3))
        ev.to_mesh_clear()
    for e in eyes:
        me = e.data; n=len(me.vertices); co=np.zeros(n*3,np.float32); me.vertices.foreach_get("co",co)
        M = np.asarray(e.matrix_world); co = co.reshape(-1,3)@M[:3,:3].T+M[:3,3]
        sizes = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", sizes)
        loops = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
        np.savez_compressed(f"{out}/{e.name}.npz", co=co, sizes=sizes, loops=loops); print(e.name, n, co.mean(0).round(3))
