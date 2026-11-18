"""Task 0216 (bug hunt 7 row 10): a crane of a lifting plan beside the hull is not the machine the sea is made round.

A crane on the demo with its hook lowered beside the hull (Hook to here at z -15 m), then a sea change, Fit
surroundings or a model update: the waterline came out 6.46 m lower, the vessel's beam for the motion 27.3 -> 39.0 m.
Here a second copy of the sea test model stands in for the crane (its model root carries ``fr_lifting`` as
``lifting.rig_model`` gives it), moved down and to the side.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, surroundings, vessel_motion, world  # noqa: E402

MODEL = os.path.join(os.path.dirname(__file__), "data", "test_sea.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _sea(sc):
    s = sc.fresing
    s.background, s.env_detail = "SEA", "SIMPLE"
    s.vessel.enabled = True
    world.apply(sc, s)
    vessel_motion.sync(sc)
    bpy.context.view_layer.update()
    return vessel_motion.hull(sc)


def test_a_crane_beside_the_hull_leaves_the_sea_where_it_was(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    want_box = [np.array(v) for v in surroundings._model_box(sc)]
    want = _sea(sc)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    roots = build.model_roots(sc)
    assert len(roots) == 2
    crane = roots[1]
    crane["fr_lifting"] = "AT-40"
    crane.location.y += 12.0                           # beside the hull, its hook far down
    crane.location.z -= 15.0
    bpy.context.view_layer.update()
    with vessel_motion.at_rest(sc):                    # (measured on a still sea, as the surroundings do)
        got_box = surroundings._model_box(sc)
    assert np.abs(np.array(got_box[0]) - want_box[0]).max() < 1e-4
    assert np.abs(np.array(got_box[1]) - want_box[1]).max() < 1e-4
    surroundings.ensure(sc, sc.fresing, replace=True)  # Fit surroundings to the model
    got = _sea(sc)
    assert got["water"] == pytest.approx(want["water"], abs=1e-4)
    assert got["beam"] == pytest.approx(want["beam"], abs=1e-4)
    assert got["middle"] == pytest.approx(want["middle"], abs=1e-4)
    del crane["fr_lifting"]                            # (control: as a machine of its own it does count)
    with vessel_motion.at_rest(sc):
        assert np.abs(np.array(surroundings._model_box(sc)[0]) - want_box[0]).max() > 1.0
