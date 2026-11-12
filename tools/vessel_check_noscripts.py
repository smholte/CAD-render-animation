"""Vessel motion plays with "Auto Run Python Scripts" off (task 0085).

Runs inside the real Blender program on a saved project, with scripts disabled and without the extension (only
Blender itself evaluates the file):

    blender --factory-startup -b -Y project.blend --python tools/vessel_check_noscripts.py -- <object> <frame> ...

Prints, per frame, the object's world matrix (16 numbers) as ``NOSCRIPTS <frame> <json>``, then the value of the
test's control driver ("NOSCRIPTS control <value>": a Python-only driver on the frame that must stay as saved) and
"NOSCRIPTS autoexec_fail <True|False>" (True: Blender refused that Python driver, so scripts were really off).
"""

import json
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
name, frames = args[0], [int(a) for a in args[1:]]
ob = bpy.data.objects[name]
scene = bpy.context.scene
for f in frames:
    scene.frame_set(f)
    bpy.context.view_layer.update()
    print("NOSCRIPTS", f, json.dumps([v for row in ob.matrix_world for v in row]), flush=True)
control = bpy.data.objects.get("NOSCRIPTS control")
if control is not None:
    print("NOSCRIPTS control", repr(float(control.get("v", 0.0))), flush=True)
print("NOSCRIPTS autoexec_fail", bpy.app.autoexec_fail, flush=True)
