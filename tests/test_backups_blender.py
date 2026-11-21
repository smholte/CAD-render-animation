"""Task 0246: automatic backups in Blender (as a module) – the copy leaves the open project as it was, the save
handlers keep out, the waits (Client view, each long job), nothing changed = no file, Restore keeps the work and puts
the backup back, the start question's choice, the preferences. The timer, undo and the windows: tools/ui_test_backups.py.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import backups  # noqa: E402
from fresing_render.core import backups as core  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def project(tmp_path, monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=False)
    docs = tmp_path / "Documents"
    docs.mkdir()
    monkeypatch.setattr(backups, "documents", lambda: str(docs))
    monkeypatch.setattr(backups, "state_path", lambda: str(tmp_path / "config" / core.STATE_FILE))
    folder = tmp_path / "job é"
    folder.mkdir()
    path = str(folder / "Crane é.blend")
    bpy.context.scene["mark"] = "saved"
    bpy.ops.wm.save_as_mainfile(filepath=path)
    backups.restart_clock()
    yield path


def _mark_in(path: str) -> str:
    import shutil
    import tempfile
    copy = os.path.join(tempfile.mkdtemp(), "read.blend")       # (Blender does not load from the open file)
    shutil.copyfile(path, copy)
    with bpy.data.libraries.load(copy) as (src, dst):
        dst.scenes = list(src.scenes)
    sc = dst.scenes[0]
    mark = sc.get("mark", "")
    bpy.data.scenes.remove(sc)
    return mark


def _change(mark: str) -> None:
    bpy.context.scene["mark"] = mark
    backups._S["changes"] += 1


def test_a_backup_is_a_copy_and_the_project_stays_as_it_was(project):
    _change("work")
    dirty = bpy.data.is_dirty
    path = backups.make(now=datetime(2026, 11, 20, 14, 35))
    assert path == os.path.join(os.path.dirname(project), "Backups", "Crane é backup 2026-11-20 14-35.blend")
    assert os.path.isfile(path)
    assert bpy.data.filepath == project and bpy.data.is_dirty == dirty
    assert _mark_in(path) == "work" and _mark_in(project) == "saved"
    assert bpy.context.scene.fresing.last_message == "Backup saved 14:35"
    assert not backups.changed()


def test_the_save_handlers_keep_out(project, monkeypatch):
    from fresing_render.blender import project_lock, queue, usage
    calls = []
    monkeypatch.setattr(queue, "project_saved", lambda: calls.append("queue"))
    monkeypatch.setattr(queue, "warn_busy_save", lambda scene: calls.append("busy") or "")
    monkeypatch.setattr(usage, "save", lambda: calls.append("usage"))
    monkeypatch.setattr(project_lock, "write", lambda p: calls.append("lock"))
    monkeypatch.setattr(project_lock, "_take", lambda p: calls.append("take"))
    _change("x")
    assert backups.make()
    assert calls == []
    bpy.ops.wm.save_mainfile()                     # the project's own save still reaches them
    assert "queue" in calls and "usage" in calls


def test_nothing_changed_makes_no_file(project, monkeypatch):
    monkeypatch.setattr(backups, "enabled_here", lambda: True)
    backups._S["since"] -= 3600
    assert backups.tick() == ""
    assert not os.path.isdir(os.path.join(os.path.dirname(project), "Backups"))
    _change("y")
    assert backups.tick()
    assert backups.tick() == ""                    # made: not due again, nothing changed


def test_a_manual_save_restarts_the_clock(project, monkeypatch):
    monkeypatch.setattr(backups, "enabled_here", lambda: True)
    _change("z")
    backups._S["since"] -= 3600
    bpy.ops.wm.save_mainfile()
    assert time.time() - backups._S["since"] < 5 and not backups.changed()
    assert backups.tick() == ""


def test_no_backup_in_the_client_view(project):
    from fresing_render.blender import workspaces
    scene = bpy.context.scene
    workspaces.switch(scene, "Client view")
    try:
        _change("c")
        assert backups.make(force=True) == ""
        assert backups._S["last_reason"] == "Client view"
    finally:
        workspaces.switch(scene, "Full access")
        workspaces.switch(scene, "All functions")


@pytest.mark.parametrize("kind", ["rebake", "ops_house", "web3d", "clash"])
def test_no_backup_while_a_long_job_runs(project, monkeypatch, kind):
    import importlib
    if kind == "rebake":
        from fresing_render.blender import rebake
        monkeypatch.setattr(rebake, "running", lambda scene: True)
    else:
        m = importlib.import_module(f"fresing_render.blender.{kind}")
        monkeypatch.setattr(m, "runtime", lambda scene: {"running": True})
    _change("j")
    assert backups.make(force=True) == ""
    assert backups._S["last_reason"] in ("Cable re-bake", "House bake", "Web 3D export", "Clash check")
    assert not os.path.isdir(os.path.join(os.path.dirname(project), "Backups"))


@pytest.mark.parametrize("what", ["render queue", "tour", "demo", "import", "pick"])
def test_no_backup_while_other_work_runs(project, monkeypatch, what):
    from fresing_render.blender import hover, ops_demo, ops_import, ops_tour, queue
    if what == "render queue":
        monkeypatch.setattr(queue, "is_running", lambda scene: True)
    elif what == "tour":
        monkeypatch.setattr(ops_tour, "progress_text", lambda: "Making the test tour …")
    elif what == "demo":
        monkeypatch.setattr(ops_demo, "running", lambda: True)
    elif what == "import":
        monkeypatch.setattr(ops_import, "_ACTIVE_JOB", type("J", (), {"done": False})())
    else:
        monkeypatch.setattr(hover, "active", lambda: True)
    assert backups.wait_reason(bpy.context.scene)
    assert backups.make(force=True) == ""


def test_switched_off_and_the_keep_rule(project, monkeypatch):
    from fresing_render.blender import prefs
    if prefs.get() is None:                        # the preferences exist only for an enabled add-on: make its entry
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    p = prefs.get()
    assert p is not None and (p.backups_on, p.backup_minutes, p.backup_keep, p.backup_days) == (True, 5, 5, 7)
    p.backups_on = False
    try:
        _change("off")
        assert backups.make() == ""
    finally:
        p.backups_on = True
    p.backup_keep, p.backup_days = 2, 0
    try:
        folder = os.path.join(os.path.dirname(project), "Backups")
        for m in range(4):
            _change(f"k{m}")
            backups.make(now=datetime(2026, 11, 20, 10, m))
        other = os.path.join(folder, "my notes.blend")
        open(other, "wb").close()
        left = sorted(os.listdir(folder))
        assert left == ["Crane é backup 2026-11-20 10-02.blend", "Crane é backup 2026-11-20 10-03.blend",
                        "my notes.blend"]
    finally:
        p.backup_keep, p.backup_days = 5, 7


def test_a_folder_that_cannot_be_written_falls_back(project, monkeypatch):
    real = backups._writable
    backups._FAILED.clear()
    monkeypatch.setattr(backups, "_writable", lambda f: False if f.endswith(os.sep + "Backups") and
                        "Documents" not in f else real(f))
    _change("fb")
    path = backups.make()
    assert os.path.basename(os.path.dirname(path)).startswith("Crane é ")
    assert os.path.basename(os.path.dirname(os.path.dirname(path))) == "Projects"
    assert "fallback:" + os.path.dirname(path) in backups._S["said"]          # said once, then "Backup saved"
    assert path in [b.path for b in backups.project_backups()]


def test_not_enough_space_says_so_once(project, monkeypatch):
    monkeypatch.setattr(backups, "_free", lambda f: 10)
    backups._S["said"].discard("space")
    _change("s")
    assert backups.make() == "" and backups._S["last_reason"] == "not enough free space"
    assert bpy.context.scene.fresing.last_message.startswith("No backup: less than")
    bpy.context.scene.fresing.last_message = ""
    assert backups.make() == "" and bpy.context.scene.fresing.last_message == ""


def test_restore_keeps_the_work_and_puts_the_backup_back(project):
    _change("backup one")
    first = backups.make(now=datetime(2026, 11, 20, 9, 0))
    _change("work now")
    backups.restore(first)
    assert bpy.data.filepath == project
    assert bpy.context.scene["mark"] == "backup one"
    found = backups.project_backups()
    assert len(found) == 2
    kept = next(b for b in found if b.path != first)
    assert _mark_in(kept.path) == "work now"
    # the restored project is newer than every backup: no question when it opens again
    b, _mt = backups.offer()
    assert b is None


def test_the_start_question_for_a_saved_and_an_unsaved_project(project, tmp_path):
    _change("newer")
    path = backups.make()
    future = time.time() + 120
    os.utime(path, (future, future))
    b, mt = backups.offer()
    assert b is not None and b.path == path and mt is not None
    assert "is newer than your saved project" in core.offer_text(b, mt)
    # an unsaved project's backup from the last 24 h, offered once at the start
    bpy.ops.wm.read_homefile(app_template="")
    bpy.context.scene["mark"] = "never saved"
    backups._S["changes"] += 1
    unsaved = backups.make()
    assert os.path.dirname(unsaved) == core.unsaved_folder(backups.documents())
    b, mt = backups.offer()
    assert b is not None and b.path == unsaved and mt is None
    core.mark_handled(backups.state_path(), [unsaved])
    b, _mt = backups.offer()
    assert b is None
    with open(backups.state_path(), encoding="utf-8") as f:
        assert os.path.basename(unsaved) in f.read()


def test_restore_of_unsaved_work_opens_a_recovered_file(project):
    bpy.ops.wm.read_homefile(app_template="")
    bpy.context.scene["mark"] = "lost work"
    backups._S["changes"] += 1
    path = backups.make()
    target = backups.restore(path)
    assert core.RECOVERED in target and bpy.data.filepath == target
    assert bpy.context.scene["mark"] == "lost work"
    assert os.path.isfile(path)                    # the backup itself stays


def test_the_menu_entry_and_the_client_view():
    from fresing_render.blender import lock, ui_topbar, workspaces
    e = ui_topbar.entries()
    assert e.index("fresing.backups_window") == e.index("fresing.usage_window") - 1
    assert not lock.allowed("fresing.backups_window")
    bpy.ops.wm.read_factory_settings(use_empty=False)
    scene = bpy.context.scene
    assert bpy.ops.fresing.backups_window.poll()
    workspaces.switch(scene, "Client view")
    try:
        assert not bpy.ops.fresing.backups_window.poll()
    finally:
        workspaces.switch(scene, "Full access")


def test_a_colleague_has_the_project_open(project, monkeypatch):
    """Their backups next to the project are their unsaved work: not offered, not restored over their file, not
    cleaned by this user; this user's backups go to the app folder (independent review of task 0246)."""
    _change("theirs")
    theirs = backups.make()
    future = time.time() + 300
    os.utime(theirs, (future, future))
    monkeypatch.setattr(backups, "other_user", lambda p: {"user": "colleague"})
    assert backups.offer() == (None, None)
    with pytest.raises(RuntimeError):
        backups.restore(theirs)
    _change("mine")
    mine = backups.make()
    assert os.path.dirname(mine) == core.fallback_folder(backups.documents(), project)
    assert os.path.isfile(theirs)


def test_a_path_too_long_goes_to_the_app_folder(project, monkeypatch):
    monkeypatch.setattr(core, "MAX_PATH", 20)
    _change("long")
    path = backups.make()
    assert os.path.dirname(path) == core.fallback_folder(backups.documents(), project)


def test_a_failed_save_falls_back(project, monkeypatch):
    real = backups.write_copy
    backups._FAILED.clear()

    def fail_next_to(p):
        if os.sep + "Backups" + os.sep in p and "Documents" not in p:
            raise OSError("path too long")
        real(p)
    monkeypatch.setattr(backups, "write_copy", fail_next_to)
    _change("f")
    path = backups.make()
    assert path and os.path.dirname(path) == core.fallback_folder(backups.documents(), project)
    backups._FAILED.clear()


def test_restore_leaves_no_temporary_file_and_the_project_is_newest(project):
    _change("one")
    first = backups.make()
    future = time.time() + 60                       # a file server's clock ahead of this PC
    os.utime(first, (future, future))
    backups.restore(first)
    assert not os.path.exists(project + ".fresing-restore")
    assert backups.offer()[0] is None
