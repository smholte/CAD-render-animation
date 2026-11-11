"""Render queue and update safety (task 0070, bug hunt 0068 rows 1-5 and 19e-h).

Each test repeats the bug hunt's script for its row: it failed on 0.2.55 and passes now.
"""

import json
import os
import subprocess
import sys
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")

import fresing_render  # noqa: E402
from fresing_render.blender import project_lock, queue, updates  # noqa: E402

REAL_POPEN = subprocess.Popen

# stands in for the background Blender: writes a running status with every job RUNNING, then waits
FAKE_RUNNER = """
import json, os, platform, sys, time
qdir = sys.argv[1]
q = json.load(open(os.path.join(qdir, "queue.json")))
st = {"pid": os.getpid(), "host": platform.node(), "running": True, "started": time.time(),
      "jobs": {j["id"]: {"status": "RUNNING", "progress": 10.0, "message": "Rendering"} for j in q["jobs"]}}
json.dump(st, open(os.path.join(qdir, "status.json"), "w"))
time.sleep(120)
"""


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def runners(monkeypatch):
    """queue.start launches the fake runner instead of a background Blender; all are ended afterwards."""
    started = []

    def popen(cmd, **kwargs):
        qdir = cmd[2] if cmd[0] == sys.executable else cmd[-2]
        p = REAL_POPEN([sys.executable, "-c", FAKE_RUNNER, qdir], stdout=kwargs.get("stdout"),
                       stderr=subprocess.STDOUT)
        started.append(p)
        return p

    monkeypatch.setattr(queue.subprocess, "Popen", popen)
    monkeypatch.setattr(queue, "_PROCS", {})
    yield started
    for p in started:
        p.kill()
        p.wait()


@pytest.fixture()
def scene(tmp_path, monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    monkeypatch.setattr(queue, "_RUNS", {})
    monkeypatch.setattr(queue, "_DELAY", {"when": 0.0, "project": "", "note": ""})
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path / "renders")
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    yield sc
    queue.cancel_delay()


def add_still(sc, name="x"):
    return queue.add_job(sc, "STILL", shot=name, quality="draft").job_id


def wait_status(qdir, seconds=20):
    t0 = time.time()
    while not os.path.isfile(os.path.join(qdir, "status.json")) and time.time() - t0 < seconds:
        time.sleep(0.05)
    time.sleep(0.1)


# ---------------------------------------------------------------------------
# row 1: Start later survives the first Save / Save As
# ---------------------------------------------------------------------------


def test_start_later_survives_save_and_save_as(scene, tmp_path):
    add_still(scene)
    queue.schedule(scene, 3600)                      # the project was never saved
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "first.blend"))
    queue._delay_tick()
    assert queue.delay_pending(), queue._DELAY["note"]
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "second name.blend"))
    queue._delay_tick()
    assert queue.delay_pending(), queue._DELAY["note"]
    assert queue._DELAY["project"] == os.path.normcase(os.path.abspath(str(tmp_path / "second name.blend")))


def test_save_as_a_copy_does_not_move_it(scene, tmp_path):
    add_still(scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "p.blend"))
    queue.schedule(scene, 3600)
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "copy.blend"), copy=True)
    assert queue._DELAY["project"] == os.path.normcase(os.path.abspath(str(tmp_path / "p.blend")))
    queue._delay_tick()
    assert queue.delay_pending()


# ---------------------------------------------------------------------------
# row 2: starting a queue never tidies away a live one; folder names are unique
# ---------------------------------------------------------------------------


def _queue_folder(root, name, status=None, age=0.0):
    qd = os.path.join(root, name)
    os.makedirs(qd)
    with open(os.path.join(qd, "queue.json"), "w") as fh:
        json.dump({"jobs": [{"id": name}]}, fh)
    open(os.path.join(qd, "project.blend"), "wb").write(b"BLENDER")
    if status is not None:
        with open(os.path.join(qd, "status.json"), "w") as fh:
            json.dump(status, fh)
    if age:
        old = time.time() - age
        for f in os.listdir(qd):
            os.utime(os.path.join(qd, f), (old, old))
    return qd


def _dead_pid():
    p = REAL_POPEN([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_tidy_keeps_live_queues(tmp_path):
    root = str(tmp_path / "_queue")
    here = queue._host()
    just_started = _queue_folder(root, "a")                                   # no status yet
    colleague = _queue_folder(root, "b", {"pid": 4242, "host": "OTHER-PC", "running": True})
    ended = _queue_folder(root, "c", {"pid": 4243, "host": here, "running": False})
    killed_here = _queue_folder(root, "d", {"pid": _dead_pid(), "host": here, "running": True})
    stale = _queue_folder(root, "e", {"pid": 4244, "host": "OTHER-PC", "running": True}, age=2 * 86400)
    queue._tidy_old_queues(root)
    has = lambda qd: os.path.isfile(os.path.join(qd, "project.blend"))  # noqa: E731
    assert has(just_started) and has(colleague)
    assert not has(ended) and not has(killed_here) and not has(stale)


def test_queue_folders_are_unique_and_never_shared(tmp_path, monkeypatch):
    root = str(tmp_path / "_queue")
    a, b = queue.new_queue_dir(root), queue.new_queue_dir(root)              # the same second
    assert a != b
    monkeypatch.setattr(queue.time, "strftime", lambda *_a: "2026-11-11_220000")

    class Same:
        hex = "abcdef0000"

    monkeypatch.setattr(queue.uuid, "uuid4", lambda: Same())
    queue.new_queue_dir(root)
    with pytest.raises(FileExistsError):
        queue.new_queue_dir(root)


# ---------------------------------------------------------------------------
# row 3: Update now refuses while a delayed start waits
# ---------------------------------------------------------------------------


def test_update_refuses_with_a_delayed_start(scene, monkeypatch):
    monkeypatch.setattr(updates, "extension_repo", lambda: object())
    add_still(scene)
    queue.schedule(scene, 3600)
    why = updates.preflight(bpy.context)
    assert why.startswith(f"A delayed queue start is set for {queue.delay_clock()}") and "cancel it" in why
    queue.cancel_delay()
    assert "delayed" not in updates.preflight(bpy.context)


# ---------------------------------------------------------------------------
# row 4: one runtime per project
# ---------------------------------------------------------------------------


def test_each_project_keeps_its_own_running_queue(scene, tmp_path, runners):
    a_path, b_path = str(tmp_path / "A.blend"), str(tmp_path / "B.blend")
    add_still(scene, "a")
    bpy.ops.wm.save_as_mainfile(filepath=a_path)
    scene.fresing.queue[0].shot = "b"
    bpy.ops.wm.save_as_mainfile(filepath=b_path, copy=True)
    a_job = scene.fresing.queue[0].job_id
    qa = queue.start(bpy.context)                    # A's queue; the file is not saved afterwards
    wait_status(qa)
    bpy.ops.wm.open_mainfile(filepath=b_path)
    sb = bpy.context.scene
    assert not queue.is_running(sb)
    assert "A.blend" in queue.describe_others(sb)    # the warning before a second runner
    qb = queue.start(bpy.context)
    wait_status(qb)
    assert qa != qb and len(queue._RUNS) == 2
    # reopen A: its jobs show running, and a second runner for them is refused
    bpy.ops.wm.open_mainfile(filepath=a_path)
    sa = bpy.context.scene
    assert queue.is_running(sa) and queue.current(sa)[1] == qa
    queue.sync(sa)
    assert sa.fresing.queue[0].status == "RUNNING"
    with pytest.raises(RuntimeError, match="already running"):
        queue.start(bpy.context)
    # Stop now in B stops only B
    bpy.ops.wm.open_mainfile(filepath=b_path)
    sb = bpy.context.scene
    queue.kill(sb)
    runners[1].wait(timeout=10)
    assert runners[0].poll() is None, "A's runner keeps going"
    assert queue._RUNS[qa]["killed"] is False and queue._RUNS[qb]["killed"] is True
    bpy.ops.wm.open_mainfile(filepath=a_path)
    sa = bpy.context.scene
    queue.sync(sa)
    assert sa.fresing.queue[0].status == "RUNNING" and sa.fresing.queue[0].job_id == a_job


def test_a_restarted_app_finds_the_live_queue(scene, tmp_path, runners, monkeypatch):
    a_path = str(tmp_path / "A.blend")
    add_still(scene)
    bpy.ops.wm.save_as_mainfile(filepath=a_path)
    qa = queue.start(bpy.context)
    wait_status(qa)
    monkeypatch.setattr(queue, "_RUNS", {})          # the app was closed and started again
    monkeypatch.setattr(queue, "_PROCS", {})
    bpy.ops.wm.open_mainfile(filepath=a_path)        # the file does not name the queue folder
    sa = bpy.context.scene
    assert queue.is_running(sa) and sa.fresing.queue_dir == qa
    with pytest.raises(RuntimeError, match="already being rendered|already running"):
        queue.start(bpy.context)


# ---------------------------------------------------------------------------
# row 5: Render animation / Time test / Current view + start don't start the delayed jobs
# ---------------------------------------------------------------------------


def test_a_new_job_starts_alone_while_a_delay_waits(scene, runners):
    s = scene.fresing
    night = add_still(scene, "overnight")
    queue.schedule(scene, 3600)
    if scene.camera is None:
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    assert bpy.ops.fresing.queue_add(kind="STILL", start=True) == {"FINISHED"}
    qdir = s.queue_dir
    ids = [j["id"] for j in json.load(open(os.path.join(qdir, "queue.json")))["jobs"]]
    assert night not in ids and len(ids) == 1
    assert queue.delay_pending(), "the overnight start stays set"
    assert s.queue[0].job_id == night and s.queue[0].status == "WAITING"
    assert "only" in s.last_message


def test_start_queue_while_a_delay_waits_starts_now_and_says_so(scene, runners):
    add_still(scene)
    queue.schedule(scene, 3600)
    assert bpy.ops.fresing.queue_start() == {"FINISHED"}
    assert not queue.delay_pending()
    assert "delayed start is cancelled" in scene.fresing.last_message


# ---------------------------------------------------------------------------
# row 19 e-h
# ---------------------------------------------------------------------------


def test_pc_stays_awake_while_a_delay_waits(scene, monkeypatch):
    calls = []
    monkeypatch.setattr(queue, "_set_execution_state", calls.append)
    monkeypatch.setattr(queue, "_AWAKE", {"on": False})
    add_still(scene)
    queue.schedule(scene, 3600)
    assert calls == [0x80000001]                     # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    queue.cancel_delay()
    assert calls == [0x80000001, 0x80000000]         # back to normal


def test_lock_is_swapped_in_whole(tmp_path, monkeypatch):
    path = str(tmp_path / "p.blend")
    swaps = []
    real = os.replace
    monkeypatch.setattr(project_lock.os, "replace", lambda a, b: (swaps.append((a, b)), real(a, b)))
    project_lock.write(path)
    assert swaps and swaps[0][1] == project_lock.lock_path(path)
    assert json.load(open(project_lock.lock_path(path)))["pid"] == os.getpid()
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_own_pid_is_never_a_live_runner(scene, tmp_path):
    s = scene.fresing
    add_still(scene)
    qdir = str(tmp_path / "q")
    os.makedirs(qdir)
    with open(os.path.join(qdir, "status.json"), "w") as fh:
        json.dump({"pid": os.getpid(), "running": True, "jobs": {}}, fh)
    s.queue_dir, s.queue_pid = qdir, os.getpid()
    assert not queue._pid_alive_os(os.getpid())
    assert not queue.is_running(scene)
    queue.kill(scene)                                # must not end this process
    assert os.getpid()


def test_finished_job_stays_done_when_the_last_write_was_lost(scene, tmp_path):
    s = scene.fresing
    job = add_still(scene)
    qdir = str(tmp_path / "q")
    os.makedirs(qdir)
    with open(os.path.join(qdir, "queue.json"), "w") as fh:
        json.dump({"jobs": [{"id": job, "kind": "STILL"}]}, fh)
    with open(os.path.join(qdir, "status.json"), "w") as fh:             # the runner's last writes were lost
        json.dump({"pid": _dead_pid(), "running": True, "jobs": {job: {"status": "RUNNING"}}}, fh)
    with open(os.path.join(qdir, f"done_{job}.json"), "w") as fh:
        json.dump({"output": "/r/x.png", "message": "Saved x.png"}, fh)
    s.queue_dir, s.queue_pid = qdir, 0
    s.queue_pid = int(json.load(open(os.path.join(qdir, "status.json")))["pid"])
    assert not queue.sync(scene)
    assert s.queue[0].status == "DONE" and s.queue[0].output == "/r/x.png"
