"""Delayed queue start (task 0050): Start later, Cancel, Start now, closing the project."""

import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")

import fresing_render  # noqa: E402
from fresing_render.blender import handlers, queue  # noqa: E402


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
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    yield sc
    queue.cancel_delay()
    if queue.is_running(sc):
        queue.kill(sc)


def add_still(sc):
    queue.add_job(sc, "STILL", shot="x", quality="draft")


def test_clock_time_today_or_tomorrow():
    now = time.mktime((2026, 11, 10, 17, 0, 0, 0, 0, -1))
    assert queue.seconds_until_clock(18, 30, now) == pytest.approx(5400)
    assert queue.seconds_until_clock(8, 0, now) == pytest.approx(15 * 3600)      # tomorrow
    assert queue.seconds_until_clock(17, 0, now) == pytest.approx(24 * 3600)     # exactly now = tomorrow


def test_schedule_needs_a_job_and_describes_itself(scene):
    with pytest.raises(RuntimeError):
        queue.schedule(scene, 60)
    add_still(scene)
    assert bpy.ops.fresing.queue_start_later(seconds=2 * 3600 + 14 * 60 - 5) == {"FINISHED"}
    assert queue.delay_pending()
    text = queue.describe_delay()
    assert text.startswith("Starts in 2 h 14 min - at ") and len(text.split(" at ")[1]) == 5
    assert bpy.app.timers.is_registered(queue._delay_tick)


def test_cancel_stops_it(scene):
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=300)
    assert bpy.ops.fresing.queue_start_cancel() == {"FINISHED"}
    assert not queue.delay_pending()
    assert not bpy.app.timers.is_registered(queue._delay_tick)
    assert not scene.fresing.queue_dir


def test_timer_starts_the_queue_at_the_time(scene):
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=0.3)
    time.sleep(0.4)
    assert queue._delay_tick() is None               # what Blender's timer does when the time has come
    assert not queue.delay_pending()
    assert scene.fresing.queue_dir and os.path.isfile(os.path.join(scene.fresing.queue_dir, "queue.json"))
    assert "on time" in scene.fresing.last_message


def test_start_now_starts_at_once(scene):
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=3600)
    assert bpy.ops.fresing.queue_start_now() == {"FINISHED"}
    assert not queue.delay_pending()
    assert scene.fresing.queue_dir


def test_a_running_render_makes_it_wait(scene, monkeypatch):
    """0070: at the time, a render still going (a Time test of the day) is waited for, then the queue starts."""
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=0)
    monkeypatch.setattr(queue, "is_running", lambda sc: True)
    assert queue._delay_tick() > 0
    assert queue.delay_pending() and queue.delay_waits_for_run(scene)
    monkeypatch.setattr(queue, "is_running", lambda sc: False)
    assert queue._delay_tick() is None
    assert not queue.delay_pending() and "on time" in scene.fresing.last_message


def test_closing_the_project_clears_it(scene):
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=3600)
    handlers._before_load()
    assert not queue.delay_pending()
    assert not bpy.app.timers.is_registered(queue._delay_tick)
    handlers._on_load()
    assert "closed" in scene.fresing.last_message


def test_another_project_cancels_it(scene, monkeypatch):
    add_still(scene)
    bpy.ops.fresing.queue_start_later(seconds=3600)
    queue._DELAY["project"] = "/somewhere/else.blend"
    assert queue._delay_tick() is None
    assert not queue.delay_pending() and "another project" in queue._DELAY["note"]
