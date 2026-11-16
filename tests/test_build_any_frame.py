"""Task 0138 (bug hunt 0131 row 6, cause from study 0141): Build gives the same animation whatever frame is shown.

Model: tests/data/test_moving.step set up by ``paths.set_up_moving_model`` (a cable over the stern into the sea, the
vessel sailing at 3 kn, the end let go at 9.2 s) plus a saved scene as the animation's start scene. Applying that
scene sets the water level again; that used to set every sea cable's touch-down again in the pose shown at the
frame shown – with a later frame shown, let go and the clock moved it (21 m on this model, 114 m on the demo)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea, states  # noqa: E402

MODEL = os.path.join(os.path.dirname(__file__), "data", "test_moving.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("anyframe"))


def set_up(folder, let_go=True, clock=True, start_scene=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_moving_model(sc, with_let_go=let_go)
    s = sc.fresing
    if not clock:                               # the seabed moves with the payout (nothing is paid out): it stands still
        s.weather.enabled = False
        s.weather.vessel_speed = 0.0
        paths.find(sc, paths.MOVING_CABLE).sea_speed = "LAY"
        paths_sea.changed(sc, paths.find(sc, paths.MOVING_CABLE))
    a = s.animations[paths.MOVING_ANIMATION]
    states.save_shot(sc, "Start")
    if start_scene:
        a.start_shot = "Start"
    return sc, a


def cable(sc):
    return paths.find(sc, paths.MOVING_CABLE)


def shapes(sc, item):
    sh = paths._shapes(sc, item)
    frames, per, _first = paths._layout_of(sh)
    co = np.empty(len(sh.data.vertices) * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    return co.reshape(frames, per, 3).astype(float)


def state(sc, out=None):
    it = cable(sc)
    return np.array(it.sea_start), float(it.sea_mark), shapes(sc, it), list((out or {}).get("warnings", []))


def assert_same(ref, now, shapes_too=True):
    assert np.linalg.norm(now[0] - ref[0]) < 1e-6, f"touch-down moved {np.linalg.norm(now[0] - ref[0]):.3f} m"
    assert abs(now[1] - ref[1]) < 1e-6, f"mark {ref[1]:.3f} -> {now[1]:.3f}"
    if shapes_too:
        assert now[2].shape == ref[2].shape
        assert float(np.abs(now[2] - ref[2]).max()) < 1e-5
    assert now[3] == ref[3]


@pytest.mark.parametrize("let_go, clock", [(True, True), (True, False), (False, True)],
                         ids=["let-go-and-clock", "let-go-only", "clock-only"])
def test_build_at_the_last_frame_is_the_build_at_the_first(folder, let_go, clock):
    """Study 0141 cases A, B, C (before the fix: the touch-down moved 21.04 / 3.44 / 17.78 m)."""
    sc, a = set_up(folder, let_go=let_go, clock=clock)
    ref = state(sc, animation.bake(sc, a))
    sc.frame_set(sc.frame_end)
    out = animation.bake(sc, a)
    assert sc.frame_current == 1
    assert_same(ref, state(sc, out))


def test_go_to_scene_at_the_last_frame_keeps_the_touch_down(folder):
    """Case F: no start scene, "Go to scene" clicked at the last frame, then Build (before: 21.04 m off, and a Build
    with frame 1 shown did not put it right)."""
    sc, a = set_up(folder, start_scene=False)
    ref = state(sc, animation.bake(sc, a))
    sc.frame_set(sc.frame_end)
    states.apply_shot(sc, "Start")
    sc.frame_set(sc.frame_end)
    assert_same(ref, state(sc), shapes_too=False)
    out = animation.bake(sc, a)
    assert_same(ref, state(sc, out))


@pytest.mark.parametrize("built", [True, False], ids=["built", "not-built"])
def test_the_same_layback_typed_again_at_a_late_frame_keeps_the_touch_down(folder, built):
    """Case G: the same layback typed again at the last frame (before: 21.04 m built, 18.52 m not built)."""
    sc, a = set_up(folder, start_scene=False)
    if built:
        animation.bake(sc, a)
    else:
        sc.frame_end = 289
    it = cable(sc)
    ref = np.array(it.sea_start), float(it.sea_mark)
    sc.frame_set(sc.frame_end)
    it.sea_layback = float(it.sea_layback)
    it = cable(sc)
    assert np.linalg.norm(np.array(it.sea_start) - ref[0]) < 1e-6
    assert abs(float(it.sea_mark) - ref[1]) < 1e-6


def test_the_same_water_level_set_again_at_a_late_frame_keeps_the_touch_down(folder):
    sc, a = set_up(folder, start_scene=False)
    it = cable(sc)
    ref = np.array(it.sea_start), float(it.sea_mark)
    sc.frame_end = 289
    sc.frame_set(sc.frame_end)
    sc.fresing.water_level = float(sc.fresing.water_level)
    it = cable(sc)
    assert np.linalg.norm(np.array(it.sea_start) - ref[0]) < 1e-6
    assert abs(float(it.sea_mark) - ref[1]) < 1e-6


def test_a_new_water_depth_still_sets_the_touch_down_again(folder):
    """Not a fault to fix: a changed water depth sets the cable on the new seabed (task 0081)."""
    sc, a = set_up(folder, start_scene=False)
    it = cable(sc)
    z0 = float(it.sea_start[2])
    it.sea_depth = float(it.sea_depth) + 2.0         # (the model's cable has a depth of its own: 15 m)
    it = cable(sc)
    assert abs(float(it.sea_start[2]) - (z0 - 2.0)) < 1e-4
