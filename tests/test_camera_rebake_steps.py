"""Task 0238 (bug hunt 0209 row 20): after a sea change the riding camera's keys were worked out again in one Python
call that set every frame of the animation (13 s on the demo's 4,481 frames, no redraw). Now the re-bake job's pass
through the frames (``flex.read_steps``, a frame per job step) reads the ridden part too, and the camera takes its
places from that pass (``camera_path.Context(places=)``): no frame is set in the camera's own step.

Model: tests/data/test_crane_a.step (public) on the Sea with vessel motion; a long animation (20 s) made here: the
camera rides the boom while it turns for 18 s, then moves back to the start camera.
"""

import math
import os
import sys
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(HERE))
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
PIVOT = Vector((0.1, 0.3, 0.4))
TOL = 1e-5                     # m / matrix entries: the camera path read in the pass vs. set frame by frame

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, cameras, clash, flex, joints, rebake  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _built(tmp_path):
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
    a.name = "Long ride"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j.name, 0.0, 18.0, "SMOOTH"
    b.use_from, b.to_angle = True, math.radians(90.0)
    for mode, t0, dur in (("RIDE", 0.0, 18.0), ("MOVE", 18.0, 2.0)):
        c = a.blocks.add()
        c.kind, c.camera_mode, c.start, c.duration = "CAMERA", mode, t0, dur
        if mode == "RIDE":
            c.cam_blend = 0.5
            boom = _ob(sc, "BOOM")
            c.target_uid, c.target_name = boom.get(build.PROP_UID), boom.get(build.PROP_NAME)
        else:
            c.camera = start
    s.animations_index = len(s.animations) - 1
    animation.bake(sc, a)
    assert sc.frame_end - sc.frame_start > 400
    return sc


def _camera_keys(sc) -> np.ndarray:
    cam = next(o for o in bpy.data.objects if o.get("fr_anim_camera"))
    out = []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        out.append(np.array(cam.matrix_world, dtype=float))
    return np.array(out)


def _old_way(sc) -> np.ndarray:
    """The keys as the re-bake worked them out before (the camera sets every frame itself)."""
    with flex.at_first_frame(sc):
        rebake.cameras(sc)
    return _camera_keys(sc)


def _rough_without_rebake(sc):
    sc.fresing.sea_state = "ROUGH"               # (the background re-bakes at once: worked out again below)


def test_the_camera_is_read_in_the_jobs_pass_and_gives_the_same_path(tmp_path, monkeypatch):
    sc = _built(tmp_path)
    _rough_without_rebake(sc)
    want = _old_way(sc)
    sc.frame_set(sc.frame_end)

    frames = sc.frame_end - sc.frame_start + 1
    steps, longest, after_read = 0, 0.0, False
    gen = rebake.steps(sc, {"cameras": True})
    t = time.perf_counter()
    for p in gen:
        now = time.perf_counter()
        longest, t = max(longest, now - t), now
        steps += 1
        if p >= rebake.READ_SHARE and not after_read:  # the pass is done: the camera's own step sets no frame
            after_read = True

            class _NoFrames:
                def __enter__(self):
                    raise AssertionError("the camera stepped through the frames itself")

                def __exit__(self, *a):
                    return False
            monkeypatch.setattr(clash, "_Guard", _NoFrames)
    monkeypatch.undo()
    assert after_read
    assert steps >= frames, f"only {steps} job steps for {frames} frames"
    assert longest < 1.0, f"one job step took {longest:.2f} s"
    assert sc.frame_current == sc.frame_end      # (the frame the user looked at)
    got = _camera_keys(sc)
    off = float(np.abs(got - want).max())
    assert off < TOL, f"the camera path is {off:.2e} off the frame-by-frame one"


def test_cancel_in_the_middle_of_the_cameras_pass_leaves_the_scene_as_it_was(tmp_path):
    sc = _built(tmp_path)
    _rough_without_rebake(sc)
    sc.frame_set(37)
    hidden = {o.name: o.hide_viewport for o in sc.objects}
    gen = rebake.steps(sc, {"cameras": True})
    for p in gen:
        if p > 0.4 * rebake.READ_SHARE:
            break
    assert any(o.hide_viewport and not hidden[o.name] for o in sc.objects)   # (the pass hides what it needs not)
    gen.close()                                  # Cancel
    rebake.cancelled(sc)
    assert sc.frame_current == 37
    assert {o.name: o.hide_viewport for o in sc.objects} == hidden
    assert flex.kept_read(sc, sc.frame_start, sc.frame_end - sc.frame_start + 1) == {}
    assert not sc.fresing.anim_baked             # the built animation came off (its keys were for the old sea)
    for o in sc.objects:
        ad = o.animation_data
        if ad is not None and ad.action is not None:
            assert not any(fc.mute for fc in flex._hide_curves(o)), o.name
