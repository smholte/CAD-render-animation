"""0381 option 4: does Blender's thread count change the per-update cost? Real Blender, background, NO app:
blender -b --factory-startup -t <n> --python s8_threads.py -- out.json   (11,500 mesh objects, as s2_scaling.py)"""
import sys, json, os
sys.argv = [sys.argv[0], "/dev/null"]
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s2_scaling.py")
exec(open(src).read().split("out = {}")[0])
out = sys.argv_saved if False else None
import bpy
res = {}
for n in (2000, 11500):
    sc, obs = scene_of(n)
    res[n] = step_ms(obs, steps=80)
print("0381", bpy.app.version_string, "threads", bpy.context.scene.render.threads, res, flush=True)
