"""Task 0229, stand-in (study 0226): a CAD-pose wrap set by hand (``wrap_user`` / ``wrap_cad``) on a sheave that sits
on a MOVING part is kept through a model update with the same file – also when the moving part is posed away from its
CAD place at the time of the update.

Until now only the private demo vessel proved this for a sheave that rides on a joint (its top pulley);
``tests/test_paths_update_same.py::test_a_wrap_set_by_hand_is_kept_through_an_update`` proves it for a still sheave
(test_paths_a). Here: the swivel test model (tests/data/test_swivel.step, ``paths_swivel.set_up_test_model``): the
davit wire's SHEAVE sits on the swivel head, which turns on the swivel joint and rides on the davit's "Slew" joint.
The wrap is set by hand (a little less than read from the CAD, as the demo set its top pulley's), then the model is
updated with the same file; the wrap, the user's mark, the contact's swivel, the joints' values and the wire's path stay.
"""

import math
import os

import numpy as np
import pytest

pytest.importorskip("OCP")
bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "data", "test_swivel.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, flex, joints, paths, paths_swivel  # noqa: E402

LESS = 0.1                      # rad: the wrap set by hand is this much less than read from the CAD (as the demo's
#                                 top pulley: drawn not quite as far round; a wrap far smaller than the wire's real one
#                                 is warned about as a loop once the davit slews: 3° set, 138° at -40°)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("wrap_moving"))


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def wire(sc):
    return paths.find(sc, paths_swivel.TEST_CABLE)


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


@pytest.fixture()
def davit(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    made = paths_swivel.set_up_test_model(sc)
    assert made["contacts"] == ["SHEAVE"]
    update()
    return sc


def _update_same(sc):
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    return wire(sc)


def _set_wrap_by_hand(sc):
    it = wire(sc)
    c = it.contacts[0]
    assert c.kind == "SHEAVE" and c.swivel == paths_swivel.TEST_SWIVEL
    assert c.wrap_cad > 0.1 and not c.wrap_user          # (read from the CAD: the wire goes a quarter round it)
    # the sheave rides on a moving part: its carrier is under the swivel, which rides on the slew
    assert paths_swivel._under(c.carrier, joints.find(sc, paths_swivel.TEST_SWIVEL).motion)
    assert paths_swivel._under(c.carrier, joints.find(sc, paths_swivel.TEST_SLEW).motion)
    wanted = float(c.wrap_cad) - LESS
    c.wrap_cad = wanted
    c.wrap_user = True
    return wire(sc), wanted


def _check_kept(sc, it, wanted):
    assert len(it.contacts) == 1, [c.name for c in it.contacts]
    c = it.contacts[0]
    assert c.name == "SHEAVE" and c.kind == "SHEAVE"
    assert c.wrap_user, "the wrap's 'set by hand' mark was lost in the update"
    assert c.wrap_cad == pytest.approx(wanted, abs=1e-6), \
        f"wrap {math.degrees(c.wrap_cad):.2f}° after the update, {math.degrees(wanted):.2f}° set by hand"
    assert c.swivel == paths_swivel.TEST_SWIVEL
    assert paths_swivel._under(c.carrier, joints.find(sc, paths_swivel.TEST_SWIVEL).motion)
    assert it.problem == "", it.problem


def test_a_wrap_set_by_hand_on_a_sheave_on_a_moving_part_is_kept(davit):
    sc = davit
    it, wanted = _set_wrap_by_hand(sc)
    before = paths.shape_now(sc, it)
    it = _update_same(sc)
    _check_kept(sc, it, wanted)
    after = paths.shape_now(sc, it)
    assert len(after) > 2 and np.isfinite(after).all()
    assert abs(float(np.linalg.norm(np.diff(after, axis=0), axis=1).sum())
               - float(np.linalg.norm(np.diff(before, axis=0), axis=1).sum())) < 1e-3


@pytest.mark.parametrize("slew_deg", [30.0, -40.0])
def test_kept_when_the_moving_part_is_posed_away_from_its_cad_place(davit, slew_deg):
    sc = davit
    it, wanted = _set_wrap_by_hand(sc)
    slew = joints.find(sc, paths_swivel.TEST_SLEW)
    sheave = named(sc, "SHEAVE")
    at_cad = np.array(sheave.matrix_world)[:3, 3].copy()
    joints.set_value(slew, math.radians(slew_deg))
    update()
    paths.refresh(sc)
    update()
    posed = np.array(named(sc, "SHEAVE").matrix_world)[:3, 3].copy()
    assert np.linalg.norm(posed - at_cad) > 1.0           # (the sheave is metres away from its CAD place)
    it = wire(sc)
    assert it.contacts[0].wrap_cad == pytest.approx(wanted, abs=1e-6)   # (posing keeps it too)
    assert it.problem == "", it.problem
    it = _update_same(sc)
    _check_kept(sc, it, wanted)
    # the pose is kept through the update, and the sheave with it
    assert math.degrees(joints.get_value(joints.find(sc, paths_swivel.TEST_SLEW))) == pytest.approx(slew_deg, abs=1e-3)
    assert np.allclose(np.array(named(sc, "SHEAVE").matrix_world)[:3, 3], posed, atol=1e-4)
    paths.refresh(sc)
    update()
    it = wire(sc)
    assert it.problem == "" and it.contacts[0].wrap_cad == pytest.approx(wanted, abs=1e-6)
