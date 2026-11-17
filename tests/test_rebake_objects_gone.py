"""Task 0192 (the owner's error on the demo in 0.2.146): "The cables could not be worked out again (StructRNA of type
Object has been removed)". The re-bake job's pass through the frames (``flex.read_steps``) hid every object the read
places do not depend on and kept Python references to them; a sea, weather or vessel setting changed while the job ran
makes the surroundings again – those objects were deleted, and putting their visibility back failed.

Now they are kept by name and looked up again (what is gone is skipped), and an object the pass READS that is deleted
meanwhile makes the job start over (``flex.ReadLost``, ``rebake.steps``).

Model: tests/data/test_moving.step, ``paths.set_up_moving_model`` (a sea cable that moves with the clock).
"""

import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(HERE))
MODEL = os.path.join(HERE, "data", "test_moving.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, flex, paths, rebake  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _built(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    flex.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_moving_model(sc)
    animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    return sc


def _shape(sc) -> np.ndarray:
    sh = paths._shapes(sc, paths.find(sc, paths.MOVING_CABLE))
    co = np.empty(len(sh.data.vertices) * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    return co


def _stand_in(sc, name):
    """An object like the sea's (no read place depends on it: the pass hides it)."""
    ob = bpy.data.objects.new(name, None)
    sc.collection.objects.link(ob)
    return ob


def test_an_object_the_pass_hid_is_deleted_during_the_job(tmp_path):
    sc = _built(tmp_path)
    want = _shape(sc)
    _stand_in(sc, "Sea stand-in")
    gen = rebake.steps(sc, {"paths": True})
    for _ in range(5):
        next(gen)
    assert bpy.data.objects["Sea stand-in"].hide_viewport          # (hidden by the pass)
    bpy.data.objects.remove(bpy.data.objects["Sea stand-in"])      # the surroundings made again meanwhile
    for _ in gen:                                                   # (before: ReferenceError, "StructRNA of type
        pass                                                        # Object has been removed")
    assert np.abs(_shape(sc) - want).max() < 1e-5
    assert not any(o.hide_viewport for o in sc.objects if o.name.startswith("FR flex"))


def test_an_object_the_pass_reads_is_deleted_the_job_starts_over(tmp_path, monkeypatch):
    sc = _built(tmp_path)
    want = _shape(sc)
    _stand_in(sc, "Rig stand-in")
    real = rebake._paths_objects

    def with_rig(scene):                         # (a read object made again by a setting: the vessel rig)
        obs, animated = real(scene)
        rig = bpy.data.objects.get("Rig stand-in")
        return obs + ([rig] if rig is not None else []), animated
    monkeypatch.setattr(rebake, "_paths_objects", with_rig)
    gen = rebake.steps(sc, {"paths": True})
    for _ in range(5):
        next(gen)
    bpy.data.objects.remove(bpy.data.objects["Rig stand-in"])
    for _ in gen:                                # starts over without it (before: ReferenceError)
        pass
    assert np.abs(_shape(sc) - want).max() < 1e-5
