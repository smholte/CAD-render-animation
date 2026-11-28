"""0381: Blender's own per-update cost as a function of object count (Blender as a Python module, no app).
For each N: N mesh objects sharing one 12-triangle box, under a 3-level tree of empties (like an assembly);
one object moved per step + view-layer update, 60 steps, mean ms. Variants show what scales."""
import sys, time, json, math
import bpy, bmesh

def box():
    me = bpy.data.meshes.new("box")
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=0.1); bm.to_mesh(me); bm.free()
    return me

def scene_of(n, kind="mesh", tree=True, mats=1):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    me = box()
    for i in range(mats):
        m = bpy.data.materials.new(f"m{i}")
        me.materials.append(m) if i == 0 else None
    col = sc.collection
    parents = []
    if tree:
        root = bpy.data.objects.new("root", None); col.objects.link(root)
        for a in range(max(1, n // 400)):
            e = bpy.data.objects.new(f"asm{a}", None); e.parent = root; col.objects.link(e); parents.append(e)
    obs = []
    for i in range(n):
        o = bpy.data.objects.new(f"p{i}", me if kind == "mesh" else None)
        o.location = (i % 100 * 0.2, i // 100 % 100 * 0.2, i // 10000 * 0.2)
        if parents:
            o.parent = parents[i % len(parents)]
        col.objects.link(o); obs.append(o)
    bpy.context.view_layer.update()
    return sc, obs

def step_ms(obs, steps=60, tag=None):
    vl = bpy.context.view_layer
    mover = obs[len(obs) // 2]
    vl.update()
    t = []
    for k in range(steps):
        t0 = time.perf_counter()
        mover.location.z = 0.001 * k
        vl.update()
        t.append((time.perf_counter() - t0) * 1000)
    t.sort()
    return round(sum(t[5:-5]) / (len(t) - 10), 3)

out = {}
for n in (500, 2000, 5000, 11500, 23000):
    sc, obs = scene_of(n)
    out[f"mesh {n}"] = step_ms(obs)
    print("mesh", n, out[f"mesh {n}"], flush=True)
for n in (11500,):
    sc, obs = scene_of(n, kind="empty"); out[f"empty {n}"] = step_ms(obs)
    sc, obs = scene_of(n, tree=False); out[f"mesh flat {n}"] = step_ms(obs)
    # half of them hidden in different ways
    for how in ("hide_set", "hide_viewport", "exclude"):
        sc, obs = scene_of(n)
        if how == "exclude":
            c = bpy.data.collections.new("far"); sc.collection.children.link(c)
            for o in obs[: n // 2]:
                sc.collection.objects.unlink(o); c.objects.link(o)
            bpy.context.view_layer.layer_collection.children["far"].exclude = True
            keep = obs[n // 2:]
        else:
            for o in obs[: n // 2]:
                if how == "hide_set": o.hide_set(True)
                else: o.hide_viewport = True
            keep = obs[n // 2:]
        bpy.context.view_layer.update()
        out[f"half {how} {n}"] = step_ms(keep)
        print(how, out[f"half {how} {n}"], flush=True)
    # one object instead: everything joined / instanced by geometry nodes
print(json.dumps(out, indent=1))
json.dump(out, open(sys.argv[1], "w"), indent=1)
