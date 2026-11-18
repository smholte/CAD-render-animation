"""Task 0160 (bug hunt 0147 rows 5, 8, 12, 20, 21a): cables into the sea after Build, in Blender as a Python module.

Model: tests/data/test_moving.step set up by ``paths.set_up_moving_model`` (a cable over the stern into the sea, the
vessel sailing at 3 kn, the cable end and the sheave let go at 9.2 s, settling onto the seabed in 2 s), as in
tests/test_build_any_frame.py.

- row 5: a project last built at a late frame by 0.2.104 – 0.2.112 kept a touch-down set in that frame's pose for
  good; opening it now sets it once at the first frame (the old Build is played here by setting the touch-down in
  the pose of the last frame, as that code did).
- row 8: the water level changed after Build: the built cable is worked out again on the new seabed (it lay 1 m under
  the seabed at every frame).
- row 12: Build puts the start scene's sea and weather back, but says which values it changed; 'Save into start
  scene' keeps them.
- row 20: a scene not brought up to date at load (appended from an older file) is at Build.
- row 21a: the settle of what was let go has no one-frame twitch (0.8 m and back), and two Builds give one shape.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea, states  # noqa: E402
from fresing_render.core import catenary as C  # noqa: E402

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
    return str(tmp_path_factory.mktemp("sea_after_build"))


def set_up(folder, start_scene=True, sea=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_moving_model(sc)
    if sea:
        sc.fresing.background = "SEA"
        sc.fresing.water_level = 2.0
    a = sc.fresing.animations[paths.MOVING_ANIMATION]
    if start_scene:
        states.save_shot(sc, "Start")
        a.start_shot = "Start"
    return sc, a


def cable(sc):
    return paths.find(sc, paths.MOVING_CABLE)


def shapes(sc):
    sh = paths._shapes(sc, cable(sc))
    frames, per, _first = paths._layout_of(sh)
    co = np.empty(len(sh.data.vertices) * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    return co.reshape(frames, per, 3).astype(float)


def touch_down(sc):
    it = cable(sc)
    return np.array(it.sea_start, dtype=float), float(it.sea_mark)


def end_above_bed(sc, frames):
    """m: the cable's end above where it lies on the seabed, at these frames (0 = on it)."""
    out = []
    for f in frames:
        sc.frame_set(f)
        it = cable(sc)
        p = paths.shape_now(sc, it)[-1]
        out.append(float(p[2] - paths_sea.waterline(sc) - paths_sea.bottom_z(sc, it)))
    return np.array(out)


# ---------------------------------------------------------------------------------------------------------------------
# row 8: the water level after Build
# ---------------------------------------------------------------------------------------------------------------------

def test_water_level_after_build_works_the_cable_out_again(folder):
    sc, a = set_up(folder, start_scene=False, sea=True)
    animation.bake(sc, a)
    frames = [1, 150, sc.frame_end]
    assert np.abs(end_above_bed(sc, frames)).max() < 1e-3
    sc.fresing.water_level = 3.0                 # after Build (the update callback's route)
    assert sc.fresing.anim_baked
    got_end = end_above_bed(sc, frames)
    assert np.abs(got_end).max() < 1e-3, got_end            # before: -1.0 m at every frame
    got = shapes(sc)
    animation.bake(sc, a)                        # a Build with the new level gives the same at every frame
    want = shapes(sc)
    assert got.shape == want.shape and float(np.abs(got - want).max()) < 1e-4


# ---------------------------------------------------------------------------------------------------------------------
# rows 5 and 20: older projects
# ---------------------------------------------------------------------------------------------------------------------

def _old_late_build(sc):
    """What 0.2.104 – 0.2.112 left after a Build at the last frame: the touch-down set in that frame's pose (the
    let-go and the sailing seabed had moved things), and no stamp."""
    sc.frame_set(sc.frame_end)
    real = paths_sea._first_rel
    paths_sea._first_rel = lambda scene, item, slots, live=False: (paths._rel_now(item, slots)[None],
                                                                   int(scene.frame_start))
    try:
        paths_sea.anchor(sc, cable(sc))
    finally:
        paths_sea._first_rel = real
    del sc[paths.ANCHOR_STAMP]


def test_an_old_project_built_at_a_late_frame_builds_right_once_opened(folder):
    sc, a = set_up(folder)
    animation.bake(sc, a)
    ref = touch_down(sc), shapes(sc)

    sc, a = set_up(folder)
    animation.bake(sc, a)
    _old_late_build(sc)
    assert np.linalg.norm(touch_down(sc)[0] - ref[0][0]) > 5.0           # (the old fault: 18 m off on this model)
    path = os.path.join(folder, "late_old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.get(paths.ANCHOR_STAMP)
    sc.frame_set(1)
    animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    now = touch_down(sc), shapes(sc)
    assert np.linalg.norm(now[0][0] - ref[0][0]) < 1e-6 and abs(now[0][1] - ref[0][1]) < 1e-6
    assert now[1].shape == ref[1].shape and float(np.abs(now[1] - ref[1]).max()) < 1e-5


def test_opening_a_project_of_this_version_changes_nothing(folder):
    sc, a = set_up(folder)
    animation.bake(sc, a)
    ref = touch_down(sc)
    assert sc.get(paths.ANCHOR_STAMP)                                       # stamped when the cable was made
    path = os.path.join(folder, "new.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    now = touch_down(bpy.context.scene)
    assert np.linalg.norm(now[0] - ref[0]) == 0.0 and now[1] == ref[1]


def test_an_unstamped_scene_is_brought_up_to_date_at_build(folder):
    """Row 20: a scene appended from an older file is not seen by load_post; Build brings it up to date, so it builds
    as it does after save + reopen (the settle 0 s of task 0137, the touch-down at the first frame)."""
    sc, a = set_up(folder)
    animation.bake(sc, a)
    ref = touch_down(sc), shapes(sc)

    sc, a = set_up(folder)
    animation.bake(sc, a)
    _old_late_build(sc)
    it = cable(sc)
    del it["sea_settle"]                        # (0.2.109 and older: "Settles in" never set)
    del sc[paths.SETTLE_STAMP]
    animation.bake(sc, a)                        # no load in between
    assert sc.get(paths.SETTLE_STAMP) and sc.get(paths.ANCHOR_STAMP)
    assert cable(sc).sea_settle == 0.0                                     # as a reopened 0.2.109 file
    assert np.linalg.norm(touch_down(sc)[0] - ref[0][0]) < 1e-6
    # the same scene saved and reopened before its Build builds the same
    sc2, a2 = set_up(folder)
    animation.bake(sc2, a2)
    _old_late_build(sc2)
    del cable(sc2)["sea_settle"]
    del sc2[paths.SETTLE_STAMP]
    path = os.path.join(folder, "appended.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc2 = bpy.context.scene
    want = shapes_after_build(sc2)
    assert cable(sc2).sea_settle == 0.0
    assert want.shape[1] > 0


def shapes_after_build(sc):
    animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    return shapes(sc)


# ---------------------------------------------------------------------------------------------------------------------
# row 21a: the settle twitch
# ---------------------------------------------------------------------------------------------------------------------

def _twitch(sh) -> float:
    """m: the largest step of a point from one frame to the next that comes back the frame after (or the one after
    that) – a twitch, not a motion."""
    worst = 0.0
    for g in (1, 2):
        out = np.linalg.norm(sh[1:-g] - sh[:-g - 1], axis=2)
        back = np.linalg.norm(sh[g + 1:] - sh[:-g - 1], axis=2)
        worst = max(worst, float(np.minimum(out, out - back).max()))
    return worst


def test_the_settle_has_no_one_frame_twitch_and_two_builds_agree(folder):
    sc, a = set_up(folder, start_scene=False)
    animation.bake(sc, a)
    first = shapes(sc)
    assert _twitch(first) < 0.3, _twitch(first)                            # before: 0.82 m (frames 278 -> 279)
    cable(sc).sea_settle = 3.0                  # another Build in between leaves other numbers behind
    animation.bake(sc, a)
    cable(sc).sea_settle = paths.MOVING_SETTLE
    animation.bake(sc, a)
    again = shapes(sc)
    assert first.shape == again.shape and float(np.abs(first - again).max()) < 1e-6


def test_steady_hang_off_puts_back_a_lone_frame_on_the_other_answer():
    """The core part: a moment whose wrap is the other answer than the moments on both sides is worked out again
    from the moment before (the twitch's numbers, read from the test model at frames 277 … 281)."""
    hit = []
    real = C.hang_off

    def fake(centre, axis, radius, side, arrive, wrap_max, start, aft, bottom_z, length0, psi0=None):
        n = len(np.asarray(centre).reshape(-1, 3))
        if psi0 is None:
            psi = np.array([3.14, 3.14, 1.05, 3.14, 3.14])[:n]
        else:
            hit.append(np.asarray(psi0).copy())
            psi = np.asarray(psi0, dtype=float)
        return {"psi": psi.copy(), "T": np.zeros((n, 3)), "L": np.arange(n, dtype=float)}

    C.hang_off = fake
    try:
        res = C.hang_off_steady(np.zeros((5, 3)), np.tile([0.0, 0.0, 1.0], (5, 1)), 0.5, 1.0, np.zeros((5, 3)), 3.14,
                                np.zeros(3), np.array([1.0, 0.0, 0.0]), -15.0, np.full(5, 70.0))
    finally:
        C.hang_off = real
    assert np.allclose(res["psi"], 3.14) and len(hit) == 1 and np.allclose(hit[0], [3.14])
    assert res["L"][2] == 0.0                   # the whole row taken from the new solve


# ---------------------------------------------------------------------------------------------------------------------
# row 12: the start scene never silent
# ---------------------------------------------------------------------------------------------------------------------

def test_build_names_the_start_scene_values_it_puts_back(folder):
    sc, a = set_up(folder, sea=True)
    w = sc.fresing.weather
    assert w.enabled and w.vessel_speed == pytest.approx(paths.MOVING_SPEED)
    animation.bake(sc, a)
    w.vessel_speed = 6.0                        # after Build: the owner changes it …
    sc.fresing.sea_state = "ROUGH"
    changes = states.start_scene_changes(sc, "Start")
    assert {c[0] for c in changes} == {"sea_state", "weather.vessel_speed"}
    warnings = animation.bake(sc, a)["warnings"]                     # … and Build puts the start scene back
    note = [t for t in warnings if "start scene 'Start'" in t]
    assert len(note) == 1 and "Vessel speed 6 kn → 3 kn" in note[0] and "Sea Rough → Calm" in note[0], warnings
    assert "Save into start scene" in note[0]
    assert w.vessel_speed == pytest.approx(paths.MOVING_SPEED) and sc.fresing.sea_state == "CALM"
    assert not [t for t in animation.bake(sc, a)["warnings"] if "start scene" in t]       # nothing changed: silent


def test_save_into_start_scene_keeps_the_values_at_build(folder):
    sc, a = set_up(folder, sea=True)
    sc.fresing.weather.vessel_speed = 6.0
    sc.fresing.sea_state = "ROUGH"
    sc.fresing.animations_index = list(sc.fresing.animations).index(a)
    assert bpy.ops.fresing.save_into_start_scene(keys="weather") == {"FINISHED"}
    assert [c[0] for c in states.start_scene_changes(sc, "Start")] == ["sea_state"]      # only what was asked
    assert bpy.ops.fresing.save_into_start_scene() == {"FINISHED"}
    assert states.start_scene_changes(sc, "Start") == []
    warnings = animation.bake(sc, a)["warnings"]
    assert not [t for t in warnings if "start scene" in t], warnings
    assert sc.fresing.weather.vessel_speed == pytest.approx(6.0) and sc.fresing.sea_state == "ROUGH"


# ---------------------------------------------------------------------------------------------------------------------
# what the independent tester found (task 0160)
# ---------------------------------------------------------------------------------------------------------------------

def test_water_level_after_build_sets_the_touch_down_on_the_new_seabed(folder):
    sc, a = set_up(folder, start_scene=False, sea=True)
    sc.fresing.water_level = 3.0                 # not built: the touch-down on the 3.0 seabed
    want = touch_down(sc)
    sc, a = set_up(folder, start_scene=False, sea=True)
    animation.bake(sc, a)
    ref = shapes(sc)
    sc.fresing.water_level = 3.0                 # built (before: the touch-down of the 2.0 water, 0.75 m of mark off)
    got = touch_down(sc)
    assert np.linalg.norm(got[0] - want[0]) < 1e-5 and abs(got[1] - want[1]) < 1e-5, (got, want)
    sc.fresing.water_level = 2.0                 # and back: as if it never changed (before: 3.43 m off)
    assert float(np.abs(shapes(sc) - ref).max()) < 1e-4


def test_a_touch_down_kept_in_a_pose_moved_by_hand_survives_save_and_reopen(folder):
    """Not built: the touch-down set in one pose is kept when the pose changes (by design); opening the file does
    not set it again."""
    sc, a = set_up(folder, start_scene=False)
    ref = touch_down(sc)
    del sc[paths.ANCHOR_STAMP]                   # (a file of 0.2.113 – 0.2.120: no stamp)
    from fresing_render.blender import joints
    joints.set_value(joints.find(sc, "Travel"), 5.0)
    path = os.path.join(folder, "hand_pose.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    now = touch_down(bpy.context.scene)
    assert np.linalg.norm(now[0] - ref[0]) == 0.0 and now[1] == ref[1]


def test_save_into_a_start_scene_without_weather_saves_the_whole_weather(folder):
    sc, a = set_up(folder, start_scene=False)
    w = sc.fresing.weather
    w.enabled = False
    states.save_shot(sc, "No weather")
    a.start_shot = "No weather"
    w.enabled = True
    w.hour, w.vessel_speed = 7.25, 5.0
    states.save_into_start_scene(sc, "No weather", ["weather"])
    assert states.start_scene_changes(sc, "No weather") == []
    warnings = animation.bake(sc, a)["warnings"]
    assert not [t for t in warnings if "start scene" in t], warnings
    assert w.enabled and w.hour == pytest.approx(7.25) and w.vessel_speed == pytest.approx(5.0)


def test_foam_and_moving_waves_are_named_too(folder):
    sc, a = set_up(folder, sea=True)
    sc.fresing.sea_foam = not sc.fresing.sea_foam
    sc.fresing.sea_moving = not sc.fresing.sea_moving
    assert {"sea_foam", "sea_moving"} <= {c[0] for c in states.start_scene_changes(sc, "Start")}


def test_steady_hang_off_slices_three_moments():
    assert list(C._rows(np.array([1.0, 2.0, 3.0]), np.array([1]), 3)) == [2.0]
    assert list(C._rows(np.zeros((3, 3)), np.array([0, 2]), 3).shape) == [2, 3]


# ---------------------------------------------------------------------------------------------------------------------
# task 0216 (bug hunt 7 row 7): undo / a copy saved during the re-bake bring back new water with the old cable
# ---------------------------------------------------------------------------------------------------------------------

def _water_without_rebake(sc, monkeypatch, level):
    """The water changed and the cable was not worked out again: what an undo step after the re-bake brings back
    (the water of the change, the shapes and keys of the Build before it), or a copy saved while the job ran."""
    with monkeypatch.context() as m:
        m.setattr(paths, "motion_changed", lambda *a, **k: None)
        sc.fresing.water_level = level


def test_undo_after_a_water_change_works_the_cable_out_again(folder, monkeypatch):
    """Water level 2 -> 3 m, re-bake, Undo: water 3.0 with the cable 1 m under the seabed and no re-bake (the key held
    the vessel / seabed motion only)."""
    sc, a = set_up(folder, start_scene=False, sea=True)
    animation.bake(sc, a)
    frames = [1, 150, sc.frame_end]
    _water_without_rebake(sc, monkeypatch, 3.0)
    assert np.abs(end_above_bed(sc, frames)).max() > 0.5          # the old cable under the new seabed
    assert paths.sea_moved(sc)
    paths._on_undo()
    assert sc.fresing.anim_baked and not paths.sea_moved(sc)
    got = end_above_bed(sc, frames)
    assert np.abs(got).max() < 1e-3, got


def test_a_cable_depth_of_its_own_is_in_the_water_key(folder):
    sc, a = set_up(folder, start_scene=False, sea=True)
    animation.bake(sc, a)
    assert not paths.sea_moved(sc)
    it = cable(sc)
    with paths._quiet(it):
        it.sea_depth = float(paths_sea.depth(sc, it)) + 2.0
    assert paths.sea_moved(sc)


def test_a_copy_saved_with_the_old_cable_is_worked_out_again_when_it_opens(folder, monkeypatch, tmp_path):
    """Case 2 of row 7: a copy saved during the job opened with the new water and the old cable, never re-baked."""
    sc, a = set_up(folder, start_scene=False, sea=True)
    animation.bake(sc, a)
    frames = [1, 150, sc.frame_end]
    _water_without_rebake(sc, monkeypatch, 3.0)
    want_line = paths_sea.waterline(sc)
    path = str(tmp_path / "copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.fresing.anim_baked and not paths.sea_moved(sc)
    bpy.context.view_layer.update()
    assert paths_sea.waterline(sc) == pytest.approx(want_line, abs=1e-5)      # (the surroundings stay where they were)
    got = end_above_bed(sc, frames)
    assert np.abs(got).max() < 1e-3, got
