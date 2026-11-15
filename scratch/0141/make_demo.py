import sys, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy, addon_utils, fresing_render
from fresing_render.blender import demo
small = sys.argv[1] == "small"
folder = sys.argv[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
t = time.time()
out = demo.build_project(folder, "9.9.9", small=small, progress=lambda st, text, done, total: None)
print("MADE", out["path"], round(time.time() - t), "s", flush=True)
