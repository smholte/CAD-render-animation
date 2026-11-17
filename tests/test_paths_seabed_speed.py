"""Task 0192 (bug hunt 6 row 8): the seabed under a sea cable whose "Vessel speed" is the vessel's own
(``sea_speed`` WEATHER) sails at the speed of 5 Scene & Render > Vessel at work and of its steps – the speed the wake
shows – whether or not Weather & time is on (``paths_sea.sync_bed`` / ``moves_by_time`` / ``ahead_keys``).

Before: one constant Weather & time vessel speed, only with Weather & time on – Still: the seabed still sailed 17.78 m
in 289 frames; a step Ahead -> Still at 4 s: it went on at 3 kn; a step Ahead 1 kn: 3 kn; Weather & time off: 0 m.

Model: tests/data/test_moving.step, ``paths.set_up_moving_model`` (3 kn, "Cable end" into the sea, 289 frames).
"""

import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_moving.step")
sys.path.insert(0, os.path.dirname(HERE))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea  # noqa: E402

KN = 0.514444
FPS = 25.0


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("seabed_speed"))


def _scene(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_moving_model(sc, with_let_go=False)
    it = paths.find(sc, paths.MOVING_CABLE)
    assert it.b_kind == "SEA" and it.sea_speed == "WEATHER"
    return sc


def _sailed(sc, frames) -> np.ndarray:
    """Metres the seabed moved aft (along the lay direction) at ``frames``, from the first frame."""
    it = paths.find(sc, paths.MOVING_CABLE)
    u = np.array(it.sea_dir, dtype=float)
    u[2] = 0.0
    u /= np.linalg.norm(u)
    out = []
    for f in frames:
        sc.frame_set(f)
        out.append(float(np.array(paths_sea.bed(sc).matrix_world.translation)[:2] @ u[:2]))
    sc.frame_set(sc.frame_start)
    return np.array(out) - out[0] if frames[0] == sc.frame_start else np.array(out)


def _step(sc, start, dur, mode, speed=0.0):
    a = sc.fresing.animations[paths.MOVING_ANIMATION]
    b = a.blocks.add()
    b.kind, b.start, b.duration, b.easing = "VESSEL", start, dur, "LINEAR"
    b.vw_mode, b.vw_speed = mode, speed
    return a


def test_still_vessel_keeps_the_seabed_still(folder):
    sc = _scene(folder)
    sc.fresing.vessel_work.mode = "STILL"
    assert not paths_sea.moves_by_time(sc, paths.find(sc, paths.MOVING_CABLE))
    got = _sailed(sc, [1, 100, 289])
    assert np.abs(got).max() < 1e-4, got                  # (before: 17.78 m at frame 289)


def test_weather_off_the_seabed_still_sails(folder):
    sc = _scene(folder)
    sc.fresing.weather.enabled = False
    got = _sailed(sc, [1, 289])
    want = 3.0 * KN * 288 / sc.render.fps                # (before: 0 m)
    assert abs(got[-1] - want) < 1e-3, (got, want)
    sc.fresing.weather.enabled = True                     # (the speed is the same either way)
    assert abs(_sailed(sc, [1, 289])[-1] - want) < 1e-3


def test_a_step_ahead_to_still_stops_the_seabed(folder):
    sc = _scene(folder)
    a = _step(sc, 4.0, 1.0, "STILL")
    animation.bake(sc, a)
    keyed = paths_sea.ahead_keys(sc)
    assert keyed is not None and keyed[0] == pytest.approx(3.0) and keyed[-1] == pytest.approx(0.0)
    got = _sailed(sc, [1, 101, 126, 150, 200, 289])
    at4 = 3.0 * KN * 4.0
    assert abs(got[1] - at4) < 1e-3, got                  # 3 kn for 4 s
    assert abs(got[2] - (at4 + 1.5 * KN * 1.0)) < 1e-3, got   # the step's second: 3 -> 0 kn
    assert np.ptp(got[2:]) < 1e-6, got                    # still from 5 s on (before: 9.20 / 12.29 / 17.78 m)
    animation.clear_keys(sc)                              # Clear keys: the panel's speed again (Ahead 3 kn)
    assert paths_sea.ahead_keys(sc) is None
    got = _sailed(sc, [1, 289])
    assert abs(got[-1] - 3.0 * KN * 288 / sc.render.fps) < 1e-3, got


def test_a_step_ahead_1_kn_sails_the_seabed_at_1_kn(folder):
    sc = _scene(folder)
    a = _step(sc, 4.0, 0.0, "AHEAD", 1.0)
    animation.bake(sc, a)
    got = _sailed(sc, [1, 101, 289])
    v = np.diff(got) / (np.diff([1, 101, 289]) / FPS) / KN
    assert v[0] == pytest.approx(3.0, abs=0.02) and v[1] == pytest.approx(1.0, abs=0.02), v   # (before: 3 kn)


def test_a_new_speed_after_a_build_with_steps_takes_the_build_off(folder):
    """The independent tester of task 0192: the steps' speed is keyed at Build; a new vessel speed afterwards made
    them old and the seabed sailed on at 3 kn (the cable's end 4.6 m off a Build at 5 kn). Now: "Build again"."""
    sc = _scene(folder)
    a = _step(sc, 4.0, 1.0, "STILL")
    animation.bake(sc, a)
    assert sc.fresing.anim_baked
    sc.fresing.weather.vessel_speed = 3.0                 # (the same speed again: nothing happens)
    assert sc.fresing.anim_baked
    sc.fresing.weather.vessel_speed = 5.0
    assert not sc.fresing.anim_baked and "Build again" in sc.fresing.last_message
    animation.bake(sc, a)                                 # built again: the steps at 5 kn
    got = _sailed(sc, [1, 101])
    assert abs(got[-1] - 5.0 * KN * 4.0) < 1e-3, got
