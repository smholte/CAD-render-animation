"""Task 0371: Cancel, then Make it again – the reader of a cancelled demo build is stopped for sure, and a new build
starts only once nothing of the last one runs.

On the owner's PC (0.2.270, kit 2) Make it → Cancel → Make it ended with "Import failed: Reader stopped (code
3221225477)" a few minutes later. Here: ``core/proctree.Tree`` (the build and every program it starts), the build
buttons' look at an ended build (``ops_demo.end_step``: what is left is stopped and waited for), a real STEP reader
whose parent is gone (it is stopped with the tree), a reader cancelled half-way and read again, the reader's stop
message (which file, what the code means) and its work folder's name. The public demo's Cancel + Make it again is in
``test_demo_project.py``; the log line by line and the start without "format could not be read" in
``test_compat_blender.py`` / below.
"""

import os
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fresing_render.core import proctree  # noqa: E402
from fresing_render.importer import runner  # noqa: E402

LINUX = sys.platform.startswith("linux")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")


def _running(pid: int) -> bool:
    """A process that runs (an ended one nobody collected yet does not)."""
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as fh:
            stat = fh.read()
    except OSError:
        return False
    return stat[stat.rfind(")") + 2:].split()[0] not in ("Z", "X")


def _orphan_script(path: str) -> str:
    """A program that starts a long-running child of its own, writes the child's number to ``path`` and ends at once:
    the child is left running without its parent (as a reader is when the build's Blender is gone)."""
    return ("import subprocess, sys\n"
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            f"open({path!r}, 'w').write(str(c.pid))\n")


@pytest.mark.skipif(not LINUX, reason="process groups and /proc: Linux (Windows: the job object, on GitHub's Windows)")
def test_a_tree_is_alive_while_a_program_it_started_runs(tmp_path):
    pid_file = str(tmp_path / "child")
    tree = proctree.Tree([sys.executable, "-c", _orphan_script(pid_file)])
    tree.proc.wait(timeout=30)
    child = int(open(pid_file).read())
    assert _running(child)
    assert tree.alive(), "the build's own program has ended, but a program it started still runs"
    tree.kill()
    assert tree.wait(10)
    assert not _running(child)
    assert not tree.alive()


@pytest.mark.skipif(not LINUX, reason="process groups and /proc: Linux")
def test_kill_stops_the_whole_tree_and_nothing_else(tmp_path):
    outside = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        pid_file = str(tmp_path / "child")
        code = _orphan_script(pid_file) + "import time; time.sleep(60)\n"
        tree = proctree.Tree([sys.executable, "-c", code])
        t0 = time.time()
        while not os.path.isfile(pid_file) or not open(pid_file).read():
            assert time.time() - t0 < 30
            time.sleep(0.05)
        child = int(open(pid_file).read())
        assert tree.alive() and _running(child)
        tree.kill()
        assert tree.wait(10)
        assert not _running(child) and tree.proc.poll() is not None
        assert outside.poll() is None, "a program outside the tree was stopped"
    finally:
        outside.kill()
        outside.wait()


def test_a_tree_that_ended_by_itself_is_not_alive():
    tree = proctree.Tree([sys.executable, "-c", "pass"])
    tree.proc.wait(timeout=30)
    assert tree.wait(10)
    tree.kill()                                        # nothing left: nothing happens
    assert not tree.alive()
    tree.close()


@pytest.mark.skipif(not LINUX, reason="/proc: Linux")
def test_a_reader_left_running_by_a_stopped_build_is_stopped_with_the_tree(tmp_path):
    """The case the owner's PC points at: the build's program is gone, a STEP reader it started (with its helpers)
    still reads. The tree stops it, and its helpers stop with it."""
    pytest.importorskip("OCP")
    pid_file = str(tmp_path / "reader")
    code = ("import sys, os\n"
            f"sys.path.insert(0, {ROOT!r})\n"
            "from fresing_render.importer import runner\n"
            f"job = runner.ImportJob({CRANE_B!r}, 'fine', {str(tmp_path / 'cache')!r})\n"
            "job.start()\n"
            f"open({pid_file!r}, 'w').write(str(job.proc.pid))\n"
            "os._exit(0)\n")                            # the build ends without stopping its reader
    env = dict(os.environ, FRESING_IMPORT_WORKERS="2")
    tree = proctree.Tree([sys.executable, "-c", code], env=env)
    tree.proc.wait(timeout=60)
    reader = int(open(pid_file).read())
    assert _running(reader), "the reader should still be reading (the test needs a longer read)"
    assert tree.alive()
    tree.kill()
    assert tree.wait(15)
    assert not _running(reader)


# ---- the reader: cancelled half-way, then read again ------------------------------------------------------------

def test_a_cancelled_read_then_the_same_file_again(tmp_path, monkeypatch):
    pytest.importorskip("OCP")
    monkeypatch.setenv("FRESING_IMPORT_WORKERS", "2")
    cache = str(tmp_path / "cache")
    first = runner.ImportJob(CRANE_B, "fine", cache)
    first.start()
    t0 = time.time()
    while first.pct <= 0 and time.time() - t0 < 60:     # cancelled while it reads, not before it started
        first.poll()
        time.sleep(0.05)
    first.cancel()
    assert first.proc.poll() is not None, "Cancel left the reader running"
    assert not os.path.exists(first.tmp_dir)
    second = runner.ImportJob(CRANE_B, "fine", cache)
    assert second.tmp_dir != first.tmp_dir
    second.start()
    t0 = time.time()
    while not second.poll():
        assert time.time() - t0 < 180
        time.sleep(0.1)
    assert second.error is None, second.error
    assert second.cached
    leftovers = [n for n in os.listdir(cache) if ".partial" in n]
    assert not leftovers, leftovers


def test_two_jobs_of_one_file_never_share_a_work_folder(tmp_path, monkeypatch):
    """Windows gives a process number out again quickly: a job of a new build with the old build's number (and the
    same job count) must not get the old build's half-written folder."""
    import itertools
    a = runner.ImportJob(CRANE_B, "draft", str(tmp_path))
    monkeypatch.setattr(runner, "_JOB_NUMBER", itertools.count(int(a.tmp_dir.rsplit("-", 2)[1])))
    b = runner.ImportJob(CRANE_B, "draft", str(tmp_path))
    assert a.cache_dir == b.cache_dir and a.tmp_dir != b.tmp_dir
    assert os.path.basename(b.tmp_dir).startswith(os.path.basename(b.cache_dir) + ".partial-")


# ---- a reader that stops says which model and why ---------------------------------------------------------------

@pytest.mark.parametrize("code, words", [
    (3221225477, "crashed: access violation, code 0xC0000005"),
    (-1073741819, "crashed: access violation, code 0xC0000005"),
    (0xC0000017, "ran out of memory, code 0xC0000017"),
    (0xC0000999, "crashed, code 0xC0000999"),
    (-9, "was stopped (out of memory, or another program), SIGKILL"),
    (-11, "crashed: access violation, SIGSEGV"),
    (1, "code 1"),
])
def test_exit_codes_in_words(code, words):
    assert runner.code_text(code) == words


def test_a_reader_that_crashes_names_its_file_not_its_folder(tmp_path, monkeypatch):
    model = tmp_path / "Users" / "someone" / "Documents" / "demo_park.step"
    model.parent.mkdir(parents=True)
    model.write_text("ISO-10303-21;\n")
    job = runner.ImportJob(str(model), "draft", str(tmp_path / "cache"))
    crash = "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)" if LINUX else "import os; os._exit(-1073741819)"
    monkeypatch.setattr(job, "command", lambda: [sys.executable, "-c", crash])
    job.start()
    t0 = time.time()
    while not job.poll():
        assert time.time() - t0 < 30
        time.sleep(0.05)
    assert job.error.startswith("Reader stopped while reading demo_park.step (crashed: access violation"), job.error
    assert "someone" not in job.error and "Documents" not in job.error


# ---- the Make demo project buttons: an ended build is waited for ------------------------------------------------

@pytest.mark.skipif(not LINUX, reason="/proc: Linux")
def test_make_it_waits_until_nothing_of_the_last_build_runs(tmp_path):
    pytest.importorskip("bpy")
    from fresing_render.blender import ops_demo
    pid_file = str(tmp_path / "child")
    tree = proctree.Tree([sys.executable, "-c", _orphan_script(pid_file)])
    ops_demo._BUILD.clear()
    ops_demo._BUILD.update(proc=tree.proc, tree=tree, folder=str(tmp_path), version="0.0.0", cancel_at=time.time())
    try:
        tree.proc.wait(timeout=30)                      # the build stopped by itself after Cancel …
        child = int(open(pid_file).read())
        assert ops_demo.running(), "Make it must wait: a program of the cancelled build still runs"
        assert "still stopping" in ops_demo._busy_text()
        t0 = time.time()
        while not ops_demo.end_step():                  # … the buttons stop what it left and wait for it
            assert time.time() - t0 < 15
            time.sleep(0.1)
        assert not _running(child)
        assert not ops_demo.running()
    finally:
        tree.kill()
        ops_demo._BUILD.clear()


@pytest.mark.skipif(not LINUX, reason="/proc: Linux")
def test_cancel_stops_a_build_that_does_not_stop_by_itself(tmp_path):
    pytest.importorskip("bpy")
    from fresing_render.blender import ops_demo
    pid_file = str(tmp_path / "child")
    code = _orphan_script(pid_file) + "import time; time.sleep(120)\n"   # inside an import: never looks at Cancel
    tree = proctree.Tree([sys.executable, "-c", code])
    ops_demo._BUILD.clear()
    ops_demo._BUILD.update(proc=tree.proc, tree=tree, folder=str(tmp_path), version="0.0.0", cancel_at=time.time())
    try:
        t0 = time.time()
        while not os.path.isfile(pid_file) or not open(pid_file).read():
            assert time.time() - t0 < 30
            time.sleep(0.05)
        child = int(open(pid_file).read())
        assert ops_demo.end_step() is False             # Cancel waits CANCEL_WAIT for the build to stop by itself
        assert tree.proc.poll() is None
        later = time.time() + ops_demo.CANCEL_WAIT + 1
        t0 = time.time()
        while not ops_demo.end_step(now=later):
            assert time.time() - t0 < 15
            time.sleep(0.1)
            later = time.time() + ops_demo.CANCEL_WAIT + 1
        assert tree.proc.poll() is not None and not _running(child)
        assert not ops_demo.running()
    finally:
        tree.kill()
        ops_demo._BUILD.clear()


# ---- the build's log: line by line ------------------------------------------------------------------------------

def test_the_log_has_every_line_even_when_the_build_ends_at_once(tmp_path):
    """The owner's log ended at "Joints 310/319", ten stages before the import that failed: lines still sitting in a
    buffer when the program ended were lost. Every progress line, an import's start and its failure go out at once."""
    pytest.importorskip("bpy")
    log = tmp_path / "Make demo log.txt"
    code = ("import os, sys\n"
            f"sys.path.insert(0, {ROOT!r})\n"
            "from fresing_render.blender import demo, ops_import\n"
            "demo._line_buffered()\n"
            "print('Fresing Render: a plain print')\n"
            "demo._line('Joints: Joints 310/319')\n"
            "demo._line('The wind park round the vessel')\n"
            "ops_import.log_line('Import failed: Reader stopped while reading demo_park.step (crashed: access "
            "violation, code 0xC0000005).')\n"
            "os._exit(1)\n")                            # ends without flushing anything
    with open(log, "w", encoding="utf-8") as fh:
        subprocess.run([sys.executable, "-c", code], stdout=fh, stderr=subprocess.STDOUT, timeout=120, check=False)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[-4:] == ["Fresing Render: a plain print", "Joints: Joints 310/319", "The wind park round the vessel",
                          "Fresing Render: Import failed: Reader stopped while reading demo_park.step (crashed: "
                          "access violation, code 0xC0000005)."], lines
