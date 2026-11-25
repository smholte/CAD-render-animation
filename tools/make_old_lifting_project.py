"""Makes tests/data/old_lifting_0_2_192.blend (task 0348): a lifting plan saved by release 0.2.192 – an AT-40 set up on
the test loads, the pump skid hung on its hook on a 4-leg set – for the test that an old lifting project opens and works
with no lift path (tests/test_lifting_path_app.py). Run with the old release checked out beside it:

    git fetch --depth=1 origin tag v0.2.192 && git worktree add /tmp/old192 v0.2.192
    OLD=/tmp/old192 ~/venv/bin/python tools/make_old_lifting_project.py tests/data/old_lifting_0_2_192.blend
"""
import math
import os
import sys

sys.path.insert(0, os.environ["OLD"])
os.environ["FRESING_LIFTING_UNDERSTOOD"] = "1"
import bpy  # noqa: E402  (first: it makes addon_utils importable)
import addon_utils  # noqa: E402
import fresing_render  # noqa: E402

print("version", fresing_render.__version__)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
bpy.ops.wm.read_homefile(use_empty=True)
DATA = os.path.join(os.environ["OLD"], "fresing_render", "data")
assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, "test_loads.step"), quality="draft") == {"FINISHED"}
from fresing_render.blender import build, lifting, lifting_rig, logic  # noqa: E402
sc = bpy.context.scene
c = lifting.place(bpy.context, os.path.join(DATA, "lifting", "AT-40"), (1.0, 7.6, 0.0), math.pi)
lifting.apply_pose(sc, c, "Set up")
part = next(o for o in logic.descendants(build.model_roots(sc)[0]) if o.get(build.PROP_NAME) == "PUMP SKID.ASM")
ld = lifting.new_load(sc, [part], "Pump skid")
ld.mass_mode, ld.mass_t, ld.source = "ENTERED", 6.0, "ESTIMATE"
lifting_rig.find_named(sc, ld)
ld.leg_length = 4.0
p = lifting.above_load(sc, ld)
p[2] += 4.6 - ld.clearance
assert lifting.hook_to(sc, c, p, ld).ok
lifting_rig.hang(sc, c, ld)
print("hung", ld.rig_state, len(ld.points))
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1], compress=True)
