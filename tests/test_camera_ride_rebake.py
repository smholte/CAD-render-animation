"""Task 0192 (bug hunt 6 row 7): a camera step that rides on a part (or flies a path, or keeps a part in the middle) was
worked out at Build for the vessel motion of that moment. After Build the sea changes: the re-bake (``rebake.cameras``,
through ``vessel_motion.follow``) takes its keys again, so they are what a Build with the new sea gives (before: the
camera riding the hull kept the old sea's heave, up to 1.48 m off on the small demo) – also with no hose or sea cable
in the project, and as one pass in the background (``rebake.gathered``).

Model: tests/data/test_crane_a.step on the Sea with vessel motion; the camera rides the BOOM while it turns, then
moves back to the start camera (a MOVE starts where the ride ends).
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(HERE))
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
PIVOT = Vector((0.1, 0.3, 0.4))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, camera_path, cameras, joints, rebake  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    s = sc.fresing
    s.background = "SEA"
    s.sea_state = "CALM"
    s.vessel.enabled = True
    bpy.context.view_layer.update()
    j = joints.create(sc, "ROTATE", [_ob(sc, "BOOM.ASM")], PIVOT, Vector((0.0, 0.0, 1.0)), ref=_ob(sc, "BOOM.PIN"))
    start = cameras.add_camera(sc, "ISO", name="Start")
    sc.camera = start
    a = s.animations.add()
    a.name = "Ride"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j.name, 0.0, 3.0, "SMOOTH"
    b.use_from, b.to_angle = True, math.radians(60.0)
    for mode, t0, dur in (("RIDE", 0.0, 3.0), ("MOVE", 3.0, 1.0)):
        c = a.blocks.add()
        c.kind, c.camera_mode, c.start, c.duration = "CAMERA", mode, t0, dur
        if mode == "RIDE":
            c.cam_blend = 0.0
            boom = _ob(sc, "BOOM")
            c.target_uid, c.target_name = boom.get(build.PROP_UID), boom.get(build.PROP_NAME)
        else:
            c.camera = start
    s.animations_index = len(s.animations) - 1
    return sc, a


def _camera_keys(sc) -> np.ndarray:
    cam = next(o for o in bpy.data.objects if o.get("fr_anim_camera"))
    out = []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        out.append(np.array(cam.matrix_world, dtype=float))
    return np.array(out)


def test_the_rebake_takes_the_riding_cameras_keys_again(tmp_path):
    sc, a = _scene(tmp_path)
    animation.bake(sc, a)
    calm = _camera_keys(sc)

    sc.frame_set(sc.frame_end)                   # (the user looks at the last frame)
    sc.fresing.sea_state = "ROUGH"               # the background: re-bake at once, one pass
    assert sc.fresing.anim_baked                 # (not taken off: worked out again)
    got = _camera_keys(sc)

    sc2, a2 = _scene(tmp_path)                   # a Build at ROUGH, from the start
    sc2.fresing.sea_state = "ROUGH"
    animation.bake(sc2, a2)
    want = _camera_keys(sc2)
    assert got.shape == want.shape
    assert np.abs(calm - want).max() > 0.01      # (the sea moves the ridden boom: the keys must change)
    off = float(np.abs(got - want).max())
    assert off < 1e-4, f"the riding camera is {off:.4f} off a Build with ROUGH"   # (before: the CALM keys)
    assert sc2.get(camera_path.CENTRE) is not None and rebake.moving_cameras(sc2)
