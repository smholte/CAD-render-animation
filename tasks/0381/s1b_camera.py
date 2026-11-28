"""0381: put one fixed camera ("FR0381 cam") into the base project, so every variant renders the same view."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import bpy, addon_utils, fresing_render  # noqa
bpy.ops.wm.read_factory_settings(use_empty=True); addon_utils.enable("cycles", default_set=True); fresing_render.register()
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
from fresing_render.pccheck import stress
cam = stress._camera(bpy.context.scene); cam.name = "FR0381 cam"
bpy.ops.wm.save_mainfile()
