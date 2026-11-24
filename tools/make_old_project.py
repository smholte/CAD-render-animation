"""Makes tests/data/old_project_0_2_195.blend (task 0273): a project saved by release 0.2.195, for the test that old
projects open unchanged (tests/test_material_picker.py). Run with the old release checked out beside it:

    git worktree add /tmp/old195 v0.2.195
    OLD=/tmp/old195 ~/venv/bin/python tools/make_old_project.py tests/data/old_project_0_2_195.blend
"""
import os
import sys
sys.path.insert(0, os.environ["OLD"])
import bpy, addon_utils
import fresing_render
print("version", fresing_render.__version__)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
bpy.ops.wm.read_homefile(use_empty=True)
assert bpy.ops.fresing.import_step(filepath=os.path.join(os.environ["OLD"], "tests", "data", "test_machine.step"), quality="draft") == {"FINISHED"}
s = bpy.context.scene.fresing
looks = [("paint_satin", "RAL 5010", 0.3), ("steel_ground", "", 0.0), ("powder_coat", "RAL 9005", 0.1), ("paint_gloss", "RAL 3020", 0.0)]
for g, (m, c, w) in zip(s.groups, looks):
    g.material = m
    if c: g.color = c
    g.wear = w
from fresing_render.blender import logic
logic.save_scheme(s, "Blue")
print([(g.name, g.material, g.color, round(g.wear, 2)) for g in s.groups])
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1], compress=True)
