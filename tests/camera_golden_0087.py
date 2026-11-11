"""Builds the animation of tests/test_camera_ride.py::test_old_camera_steps_keys_unchanged and prints its camera keys
as JSON. Run once with the code before task 0087 to write tests/data/camera_keys_0087.json:

    ~/venv/bin/python tests/camera_golden_0087.py tests/data/camera_keys_0087.json
"""

import json
import math
import os
import sys

import bpy
import addon_utils

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, cameras  # noqa: E402

CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


def old_steps_scene():
    """The crane, two saved cameras and an animation with every old camera step (Cut, Move to, Orbit)."""
    sc = bpy.context.scene
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    c1 = cameras.add_camera(sc, "ISO", name="Golden one")
    c2 = cameras.add_camera(sc, "FRONT", lens=35.0, name="Golden two")
    sc.camera = c1
    s = sc.fresing
    a = s.animations.add()
    a.name = "Golden"
    for kind, mode, cam, start, dur, ez, ang in (
            ("CAMERA", "ORBIT", None, 0.0, 1.5, "SMOOTH", 60.0),
            ("CAMERA", "MOVE", c2, 1.5, 1.0, "LINEAR", 0.0),
            ("CAMERA", "CUT", c1, 2.6, 0.0, "SMOOTH", 0.0),
            ("CAMERA", "MOVE", c2, 3.0, 1.2, "EASE_IN", 0.0),
            ("CAMERA", "ORBIT", None, 4.2, 1.0, "EASE_OUT", -45.0)):
        b = a.blocks.add()
        b.kind, b.camera_mode, b.start, b.duration, b.easing = kind, mode, start, dur, ez
        b.orbit_angle = math.radians(ang)
        if cam is not None:
            b.camera = cam
    return sc, a


def keys(sc):
    cam = sc.camera
    out = {}
    for idb, tag in ((cam, "ob"), (cam.data, "cam")):
        act = idb.animation_data.action
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        out[f"{tag}:{fc.data_path}:{fc.array_index}"] = [
                            [round(k.co[0], 6), round(k.co[1], 7)] for k in fc.keyframe_points]
    return out


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc, a = old_steps_scene()
    info = animation.bake(sc, a)
    assert not info["warnings"], info
    with open(sys.argv[1], "w") as fh:
        json.dump(keys(sc), fh, sort_keys=True)
