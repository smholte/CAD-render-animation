"""0381: the 3D view's per-object drawing cost, real Blender under xvfb (software OpenGL), NO app.
11,500 boxes of 12 triangles (few triangles, so the object count shows): as objects / as GN instances on one object /
as one joined mesh. View redrawn 20 x after one box moved (a drag step + draw).
xvfb-run ... blender -p 0 0 1280 720 --factory-startup --python s7_draw_synth.py -- <objects|gn|joined> out.json"""
import bpy, bmesh, json, sys, time
import numpy as np
kind, out = sys.argv[sys.argv.index("--") + 1:][:2]
N = 11500

def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    sc = bpy.context.scene
    me = bpy.data.meshes.new("box"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.1); bm.to_mesh(me); bm.free()
    pos = np.array([(i % 100 * 0.2, i // 100 % 100 * 0.2, 0) for i in range(N)], np.float32)
    root = bpy.data.objects.new("root", None); sc.collection.objects.link(root)
    if kind == "objects":
        for i in range(N):
            o = bpy.data.objects.new(f"p{i}", me); o.location = pos[i]; o.parent = root; sc.collection.objects.link(o)
        return bpy.data.objects["p5000"]
    if kind == "gn":
        pts = bpy.data.meshes.new("pts"); pts.vertices.add(N); pts.vertices.foreach_set("co", pos.ravel())
        car = bpy.data.objects.new("car", pts); car.parent = root; sc.collection.objects.link(car)
        proto = bpy.data.objects.new("proto", me)       # not in the scene
        ng = bpy.data.node_groups.new("i", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
        oi = ng.nodes.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = proto
        iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
        ng.links.new(gi.outputs[0], iop.inputs["Points"]); ng.links.new(oi.outputs["Geometry"], iop.inputs["Instance"])
        ng.links.new(iop.outputs[0], go.inputs[0])
        car.modifiers.new("i", "NODES").node_group = ng
        return root
    # joined
    v = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", v); v = v.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
    big = bpy.data.meshes.new("joined")
    V = (v[None] + pos[:, None]).reshape(-1, 3)
    L = (lv[None] + (np.arange(N) * len(v))[:, None]).ravel()
    big.vertices.add(len(V)); big.vertices.foreach_set("co", V.ravel())
    big.loops.add(len(L)); big.loops.foreach_set("vertex_index", L)
    big.polygons.add(N * 6); big.polygons.foreach_set("loop_start", np.arange(N * 6, dtype=np.int32) * 4)
    big.polygons.foreach_set("loop_total", np.full(N * 6, 4, np.int32)); big.update(calc_edges=True)
    o = bpy.data.objects.new("joined", big); o.parent = root; sc.collection.objects.link(o)
    return root

def area3d():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                return w, a, [r for r in a.regions if r.type == "WINDOW"][0]

def run():
    mover = build()
    w, a, r = area3d()
    a.spaces.active.shading.type = "SOLID"; a.spaces.active.overlay.show_overlays = False
    with bpy.context.temp_override(window=w, area=a, region=r):
        bpy.ops.view3d.view_all()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=3)
        t0 = time.perf_counter(); bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        still = (time.perf_counter() - t0) * 50
        t = []
        for k in range(20):
            t0 = time.perf_counter(); mover.location.z = 0.01 * k
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=1); t.append((time.perf_counter() - t0) * 1000)
    t.sort()
    res = {"kind": kind, "objects": len(bpy.data.objects), "redraw_ms": round(still, 1),
           "move_and_draw_ms": round(sum(t[2:-2]) / 16, 1)}
    json.dump(res, open(out, "w")); print("0381", res, flush=True)
    bpy.ops.wm.quit_blender()

bpy.app.timers.register(run, first_interval=2.0)
