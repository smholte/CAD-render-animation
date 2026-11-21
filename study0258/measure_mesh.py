"""Task 0258 (throw-away): boxes of the mesh test models and the sample house, read with bpy."""
import sys, bpy
from mathutils import Vector
for f in sys.argv[1:]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if f.endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=f)
    else:
        bpy.ops.import_scene.gltf(filepath=f)
    bpy.context.view_layer.update()
    pts = [ob.matrix_world @ Vector(c) for ob in bpy.data.objects if ob.type == "MESH" for c in ob.bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]; hi = [max(p[i] for p in pts) for i in range(3)]
    print("BOX", f.split("/")[-1], " x ".join(f"{1000*(h-l):.0f}" for l, h in zip(lo, hi)), "mm  z", f"{1000*lo[2]:.0f}..{1000*hi[2]:.0f}")
    big = sorted(bpy.data.objects, key=lambda o: -max(o.dimensions) if o.type == "MESH" else 0)[:8]
    for ob in big:
        if ob.type == "MESH":
            print("   ", ob.name[:30], " x ".join(f"{1000*d:.0f}" for d in ob.dimensions))
