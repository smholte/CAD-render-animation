"""0381 prototype: import the stress model with the app (Blender as a Python module), make its 8 joints, save.
python s1_import.py <step> <quality> <out.blend>"""
import json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import bpy, addon_utils  # noqa
import fresing_render
step, quality, out = sys.argv[1:4]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import workspaces, build
from fresing_render.pccheck import stress
scene = bpy.context.scene
workspaces.use_all(scene)
t0 = time.time()
res = bpy.ops.fresing.import_step(filepath=step, quality=quality)
t_imp = time.time() - t0
print("import", res, round(t_imp, 1), "s", flush=True)
sheet = json.load(open(os.path.splitext(step)[0] + ".joints.json"))
t0 = time.time()
n = stress.make_joints(scene, sheet)
bpy.context.view_layer.update()
print("joints", n, round(time.time() - t0, 1), "s")
parts = list(build.iter_parts(scene))
print("objects", len(bpy.data.objects), "parts", len(parts), "meshes", len(bpy.data.meshes))
t0 = time.time()
bpy.ops.wm.save_as_mainfile(filepath=out)
print("save", round(time.time() - t0, 1), "s", os.path.getsize(out) / 1e6, "MB")
json.dump({"import_s": t_imp, "objects": len(bpy.data.objects), "parts": len(parts)},
          open(out + ".json", "w"))
