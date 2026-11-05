"""Couplings move with "Auto Run Python Scripts" off (task 0012).

Runs inside the real Blender program on a saved project, with scripts disabled and without the
extension (only Blender itself evaluates the file):

    blender --factory-startup -b -Y project.blend --python tools/coupling_check_noscripts.py -- \
        <leader joint> <value> <follower joint> [<follower joint> ...]

Sets the leader joint's value, lets Blender update the scene, and prints one line per joint with
the position of its motion (angle in rad or slide in m):
    NOSCRIPTS <joint> <value>
then the value of the test's control driver (Python only: it must stay as saved) and
"NOSCRIPTS autoexec_fail <True|False>" (True: Blender refused that Python driver, so scripts were
really off). The real-app test (ui_test_app2.py) compares the values with the ones worked out by hand.
"""

import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
leader, value, names = args[0], float(args[1]), args[2:]
motions = {o.get("fr_joint"): o for o in bpy.data.objects if o.get("fr_kind") == "joint"}
anim = [o for o in motions.values() if o.animation_data is not None and o.animation_data.action is not None]
for o in anim:                                   # baked animation keys would overrule the value
    o.animation_data.action = None
motions[leader]["fr_value"] = value
motions[leader].update_tag()
bpy.context.view_layer.update()
for name in [leader] + names:
    m = motions[name]
    # what really moves: the motion's driven channel (its rotation or slide), not the value copy
    fc = next((f for f in (m.animation_data.drivers if m.animation_data else [])
               if f.data_path in ("rotation_euler", "location") and f.array_index == 2), None)
    v = getattr(m, fc.data_path)[2] if fc is not None else m["fr_value"]
    print("NOSCRIPTS", name, repr(float(v)), flush=True)
# the test puts a Python-only driver on an empty "NOSCRIPTS control" (value = leader x 5, with an
# attribute lookup that Blender never runs when scripts are off): it must not have moved
control = bpy.data.objects.get("NOSCRIPTS control")
if control is not None:
    print("NOSCRIPTS control", repr(float(control.get("v", 0.0))), flush=True)
print("NOSCRIPTS autoexec_fail", bpy.app.autoexec_fail, flush=True)
