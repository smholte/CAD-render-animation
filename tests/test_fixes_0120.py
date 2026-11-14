"""Task 0120: bug hunt 0118 rows 1, 6, 11, 13, 15, 16, 18 – each test failed before its fix."""

import math
import os
import threading
import time
import types

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, cameras, clash, fade, logic, longjob, ops_clash,  # noqa: E402
                                    ops_house, ops_web3d, queue, render, section, states, ui_weather, weather,
                                    weather_sky, web3d)

YELLOW = "Colour #F9A800"          # the crane's yellow group


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path, monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    monkeypatch.setattr(queue, "_RUNS", {})
    monkeypatch.setattr(queue, "_DELAY", {"when": 0.0, "project": "", "note": ""})
    sc = bpy.context.scene
    s = sc.fresing
    s.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    cameras.add_camera(sc, "FRONT")
    logic.save_scheme(s, "Own")
    for name, colour in (("Red", "#E00000"), ("Blue", "#0030E0")):
        s.groups[YELLOW].color = colour
        logic.save_scheme(s, name)
    logic.apply_scheme(sc, "Own")
    a = s.animations.add()
    a.name, a.fps, a.tail = "Spin", "25", 0.0
    b = a.blocks.add()
    b.kind, b.camera_mode, b.orbit_angle, b.start, b.duration = "CAMERA", "ORBIT", math.radians(30), 0.0, 0.2
    yield sc
    for rt in (ops_house.runtime(sc), web3d.runtime(sc), clash.runtime(sc)):
        rt.clear()
    queue.cancel_delay()
    if queue.is_running(sc):
        queue.kill(sc)


# -- row 1: every paint scheme with a start scene -------------------------------------------------------------

def test_animation_jobs_keep_their_scheme_over_the_start_scene(scene, monkeypatch):
    s = scene.fresing
    states.save_shot(scene, "Start")                    # saved in the Own colours
    s.animations["Spin"].start_shot = "Start"
    seen = {}

    def fake_animation(sc, job, progress, should_stop):
        queue._setup_animation(sc, job, progress)
        seen[job["scheme"]] = sc.fresing.groups[YELLOW].color
        return ""

    monkeypatch.setattr(queue, "render_animation", fake_animation)
    for name in ("Red", "Blue"):
        queue.run_job(scene, {"kind": "ANIMATION", "animation": "Spin", "quality": "preview", "id": "x",
                              "out_dir": s.out_folder, "scheme": name}, lambda *a: None, lambda: False)
    assert seen == {"Red": "#E00000", "Blue": "#0030E0"}


# -- row 6: a queued still renders at the frame it was added at ------------------------------------------------

def test_add_image_renders_at_its_own_frame(scene, monkeypatch):
    s = scene.fresing
    scene.frame_end = 100
    scene.frame_set(60)
    assert bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}
    shot = s.shots[s.queue[-1].shot]
    assert shot[queue.SHOT_FRAME] == 60
    scene.frame_set(1)
    frames = []

    def fake_still(sc, settings, quality, watermark=False):
        frames.append(sc.frame_current)
        return {"path": ""}

    monkeypatch.setattr(render, "render_still", fake_still)
    queue.run_job(scene, {"kind": "STILL", "shot": shot.name, "quality": "draft", "out_dir": s.out_folder},
                  lambda *a: None, lambda: False)
    assert frames == [60]


# -- row 11: no queue start (now, later) during a House bake / web 3D export / clash check ------------------------

@pytest.mark.parametrize("which,label", [(ops_house, "House bake"), (web3d, "Web 3D export"),
                                         (clash, "Clash check")])
def test_queue_waits_while_a_long_job_changes_the_project(scene, which, label):
    s = scene.fresing
    queue.add_job(scene, "STILL", shot=states.save_shot(scene, "A").name)
    which.runtime(scene)["running"] = True
    assert queue.busy_job(scene) == label
    with pytest.raises(RuntimeError, match=label):
        queue.start(bpy.context)
    with pytest.raises(RuntimeError, match=label):        # the button: the same reason as an error
        bpy.ops.fresing.queue_start()
    assert not queue.is_running(scene)
    # Start later is due now: it waits for the job instead of copying the half-done project
    queue._DELAY.update(when=time.time() - 1.0, project=queue._project_key(), note="")
    assert queue._delay_tick() is not None
    assert queue.delay_pending() and not queue.is_running(scene)
    # Ctrl+S: a warning (Blender cannot stop the save)
    assert label in queue.warn_busy_save(scene) and label in s.last_message
    which.runtime(scene)["running"] = False
    assert queue.busy_job(scene) == "" and queue.warn_busy_save(scene) == ""
    queue.cancel_delay()


# -- row 13: Ctrl+Z is kept from Blender while a long job runs ------------------------------------------------

def _event(type_, ctrl=True, shift=False, value="PRESS"):
    return types.SimpleNamespace(type=type_, value=value, ctrl=ctrl, shift=shift, oskey=False)


def test_undo_keys():
    assert longjob.is_undo(_event("Z")) and longjob.is_undo(_event("Z", shift=True)) and longjob.is_undo(_event("Y"))
    assert not longjob.is_undo(_event("Z", ctrl=False)) and not longjob.is_undo(_event("Z", value="RELEASE"))
    assert not longjob.is_undo(_event("TIMER", ctrl=False))


@pytest.mark.parametrize("op", [ops_web3d.FRESING_OT_web3d_export, ops_house.FRESING_OT_house_bake,
                                ops_clash.FRESING_OT_clash_check])
def test_long_jobs_swallow_undo(scene, op):
    reports = []
    me = types.SimpleNamespace(report=lambda kind, text: reports.append(text), _gen=iter(()), _timer=None)
    assert op.modal(me, bpy.context, _event("Z")) == {"RUNNING_MODAL"}       # was PASS_THROUGH: Blender undid
    assert reports and "Cancel" in reports[0] and "Cancel" in scene.fresing.last_message
    assert op.modal(me, bpy.context, _event("MOUSEMOVE", ctrl=False)) == {"PASS_THROUGH"}


# -- row 15: no cut-away writes at render start off the main thread ---------------------------------------------

def test_render_init_never_syncs_off_the_main_thread(scene, monkeypatch):
    calls = []
    monkeypatch.setattr(section, "sync", lambda sc: calls.append(threading.current_thread().name))
    assert bpy.ops.fresing.cut_add(what="MODEL") == {"FINISHED"}
    calls.clear()
    t = threading.Thread(target=section._on_render_init, args=(scene,), name="render job")
    t.start()
    t.join()
    assert calls == []                                   # the render job's thread writes nothing
    section._on_render_init(scene)
    assert calls == [threading.main_thread().name]
    calls.clear()
    render.prepare_still(scene, scene.fresing, "draft")   # the app's own render button syncs first
    assert calls == [threading.main_thread().name]


# -- row 16: Build says so when the start scene puts the weather off ------------------------------------------

def test_build_warns_when_the_start_scene_switches_the_weather_off(scene):
    s = scene.fresing
    states.save_shot(scene, "Start")                    # saved without weather
    s.animations["Spin"].start_shot = "Start"
    s.weather.enabled = True
    info = animation.bake(scene, s.animations["Spin"])
    assert not s.weather.enabled                         # by design: the start scene's weather
    assert any("has no weather" in w and "'Start'" in w for w in info["warnings"]), info["warnings"]
    animation.clear_keys(scene)
    states.save_shot(scene, "Start")                    # saved again, now without weather on either side
    info = animation.bake(scene, s.animations["Spin"])
    assert not any("weather" in w for w in info["warnings"])
    assert animation._weather_note("S", '{"weather": {"enabled": false}}',
                                   '{"weather": {"enabled": true, "preset": "STORM"}}').startswith("Build put back")


# -- row 18 ---------------------------------------------------------------------------------------------------

def test_panel_counts_are_kept_between_redraws(scene, monkeypatch):
    walks = []
    real = fade.xray_parts
    monkeypatch.setattr(fade, "xray_parts", lambda sc: walks.append(1) or real(sc))
    assert fade.xray_count(scene) == 0 and fade.xray_count(scene) == 0
    assert len(walks) == 1                               # one walk for two redraws
    part = next(o for o in scene.objects if o.type == "MESH" and o.get("fr_kind") == "part")
    fade.apply_look(scene, [part])
    assert fade.xray_count(scene) == 1                   # the look given: counted again at once
    fade.remove_look(scene, [part])
    assert fade.xray_count(scene) == 0
    # work lights
    n0 = ui_weather.light_count(scene)
    assert n0 == len(weather_sky.work_lights(scene))
    # cut-away: one walk per change, not per redraw
    assert bpy.ops.fresing.cut_add(what="MODEL") == {"FINISHED"}
    cut = section.active(scene)
    want = len(section.cut_parts(scene, cut))
    assert want > 0
    walked = []
    real_cp = section.cut_parts
    monkeypatch.setattr(section, "cut_parts", lambda sc, c: walked.append(1) or real_cp(sc, c))
    assert section.cut_count(scene, cut) == want and section.cut_count(scene, cut) == want
    assert len(walked) <= 1
    assert not hasattr(section, "_cut_objects")          # the dead function is gone (row 18b)


def test_scene_action_no_orphan_and_users_own_action_kept(scene):
    ad = scene.animation_data_create()
    own = bpy.data.actions.new("My scene keys")
    ad.action = own
    scene["my_value"] = 1.0
    scene.keyframe_insert('["my_value"]', frame=1)      # a key of the user's own on the scene
    # what a Weather & time step does at Build (weather.bake): the app's keys on the scene
    cb = animation._channelbag(scene, "SCENE")
    animation._write(cb, '["fr_wx_test"]', 0, [(1.0, 0.0, "LINEAR", "AUTO"), (10.0, 1.0, "LINEAR", "AUTO")])
    scene[weather.STEP_TAG] = True
    s = scene.fresing
    s.anim_baked = "x"
    assert scene.animation_data.action is not own
    app_action = scene.animation_data.action.name
    animation.clear_keys(scene)
    assert app_action not in bpy.data.actions             # no orphan "FR Scene" left behind
    assert scene.animation_data.action == own              # the user's own keys are back
    assert not any(a.get(animation.TAG) for a in bpy.data.actions if a.users == 0)
    assert animation.USER_ACTION not in scene and animation.TAG not in scene
