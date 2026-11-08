"""Task 0038: arrays in ID properties. Blender 5.2.3 corrupts its memory when an array property gets a NumPy
array of another length; milling read the bits' path again that way and crashed (task 0037, problem 1)."""

import os
import subprocess
import sys
import time

import numpy as np
import pytest

import bpy  # noqa: E402
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import machining  # noqa: E402
from fresing_render.blender.idprops import store_array  # noqa: E402

HERE = os.path.dirname(__file__)
CHILD = os.path.join(HERE, "milling_crash_child.py")


def _child(*args, timeout=900):
    env = dict(os.environ, PYTHONPATH=os.path.dirname(HERE))
    return subprocess.run([sys.executable, CHILD, *args], env=env, capture_output=True, text=True,
                          cwd=os.path.dirname(HERE), timeout=timeout)


def test_store_array_reads_back_right():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for n in (250, 2000, 10, 2000, 0, 7):
        v = np.random.default_rng(n).random(n)
        store_array(sc, "fr_test", v)
        back = np.array(sc["fr_test"], dtype=np.float64)
        assert back.shape == (n,) and np.array_equal(back, v)
    store_array(sc, "fr_test", [[1.0, 2.0], [3.0, 4.0]])           # nested lists come out flat
    assert list(sc["fr_test"]) == [1.0, 2.0, 3.0, 4.0]
    junk = [np.ones(300_000) for _ in range(30)]                    # still alive after big allocations
    del junk
    assert list(sc["fr_test"]) == [1.0, 2.0, 3.0, 4.0]


def test_no_numpy_array_is_assigned_to_an_id_property_directly():
    """The milling path goes through store_array; nothing writes item["fr_..."] = np.… in the app."""
    import re
    bad = []
    pat = re.compile(r"""\[\s*["'][^"']+["']\s*\]\s*=\s*np\.""")
    root = os.path.join(os.path.dirname(HERE), "fresing_render", "blender")
    for name in os.listdir(root):
        if name.endswith(".py") and name != "idprops.py":      # its docstring shows the bad way
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if pat.search(line):
                        bad.append(f"{name}:{i}: {line.strip()}")
    assert not bad, bad


def test_reading_the_path_again_with_another_length_does_not_crash():
    """Before 0.2.33 this child died every time (segfault / "corrupted size vs. prev_size", 5 of 5 on the
    4-core test machine with --unsafe); it must now pass several times in a row."""
    for _ in range(2):
        done = _child("--rounds", "5")
        assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout[-2000:]}\n{done.stderr[-3000:]}"
        assert "OK" in done.stdout


def test_project_saved_the_old_way_opens_and_cuts(tmp_path):
    """A project saved by 0.2.32 or older (path stored as a NumPy array) is read again with another length."""
    path = str(tmp_path / "old.blend")
    done = _child("--rounds", "0", "--unsafe", "--save", path)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-3000:]
    done = _child("--rounds", "4", "--open", path)
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout[-2000:]}\n{done.stderr[-3000:]}"
    assert "OK" in done.stdout


@pytest.fixture()
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_queue_makes_the_mp4_after_the_count_changed(addon, tmp_path):
    """The saved project holds a path of one length, the queue reads it again with another and makes an MP4."""
    sys.path.insert(0, HERE)
    import milling_crash_child as child

    from fresing_render.blender import logic, queue
    sc = bpy.context.scene
    s = sc.fresing
    s.out_folder = str(tmp_path)
    child.set_up(sc)
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):
        logic.set_hidden(child.ob(sc, name), True)
    child.anim(sc, 0.08, "Mill")
    first = machining.sample(sc)
    child.anim(sc, 0.16, "Mill")                    # built again, longer: the stored path is now out of date
    s.use_gpu = False
    a = s.animations["Mill"]
    a.out_resolution, a.quality, a.video = "preview", "draft", "MP4"
    queue.add_job(sc, "ANIMATION", animation="Mill")
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "mill.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(sc) and time.time() - t0 < 900:
        time.sleep(1.0)
    queue.sync(sc)
    job = s.queue[0]
    log = queue.log_tail(qdir, 60)
    assert job.status == "DONE", (job.message, log)
    mp4 = job.output + ".mp4" if not job.output.endswith(".mp4") else job.output
    assert os.path.isfile(mp4) and os.path.getsize(mp4) > 1000, (job.output, os.listdir(tmp_path), log)
    assert first > 0


def test_mp4_encode_scene_keeps_no_frame_cache():
    """Task 0043: the throw-away encode scene must not cache every 4K frame."""
    from fresing_render.blender import queue
    sc = bpy.data.scenes.new("t")
    sc.sequence_editor_create()
    queue._no_frame_cache(sc)
    se = sc.sequence_editor
    assert not se.use_cache_raw and not se.use_cache_final
    bpy.data.scenes.remove(sc)
