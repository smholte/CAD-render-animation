"""Updates inside the app (Blender part): check, panel, Update now, template refresh, Help menu (task 0020)."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time
import zipfile

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render import __version__, update_helper  # noqa: E402
from fresing_render.blender import updates  # noqa: E402
from fresing_render.core import updates as core  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.dirname(__file__))
from test_blender import FakeLayout  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Every test starts without a check result, a download or a status; Blender's config folder is a
    temporary one, so nothing is written into the real one."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    real = bpy.utils.user_resource

    def user_resource(kind, path="", create=False):
        if kind == "CONFIG":
            return str(cfg / path) if path else str(cfg)
        return real(kind, path=path, create=create)
    monkeypatch.setattr(bpy.utils, "user_resource", user_resource)
    updates._check.clear()
    updates._check["state"] = "idle"
    updates._dl.clear()
    updates._dl["active"] = False
    updates._status.clear()
    updates._ui.update(later=False)
    bpy.context.preferences.system.use_online_access = True
    yield cfg
    bpy.context.preferences.system.use_online_access = False


def _repo(tmp_path, version="9.9.9", platform=None):
    """A small update listing with a real (tiny) zip in it."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    zpath = repo / f"fresing_render-{version}.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("blender_manifest.toml", f'version = "{version}"\n')
    import hashlib
    data = zpath.read_bytes()
    item = {"id": "fresing_render", "version": version, "platforms": [platform or core.platform_tag()],
            "blender_version_min": "5.2.0", "blender_version_max": "5.3.0", "archive_url": f"./{zpath.name}",
            "archive_size": len(data), "archive_hash": "sha256:" + hashlib.sha256(data).hexdigest()}
    (repo / "index.json").write_text(json.dumps({"version": "v1", "data": [item]}), encoding="utf-8")
    (repo / "changelog.json").write_text(json.dumps({"versions": [
        {"version": version, "date": "6 Nov 2026", "title": "test", "text": "Panel 1\n- **New** thing\n  more"},
        {"version": __version__, "date": "5 Nov 2026", "title": "", "text": "- installed"}]}), encoding="utf-8")
    return (repo / "index.json").as_uri()


def _draw_panel(errors):
    fake = type("P", (), {"layout": FakeLayout(errors)})()
    updates.FRESING_PT_update.draw_header(fake, bpy.context)
    updates.FRESING_PT_update.draw(fake, bpy.context)


# ---- check ---------------------------------------------------------------------------------

def test_check_respects_online_access(monkeypatch, tmp_path):
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    bpy.context.preferences.system.use_online_access = False
    assert updates.check_now()["state"] == "off"
    assert not updates.FRESING_PT_update.poll(bpy.context)
    bpy.context.preferences.system.use_online_access = True
    res = updates.check_now()
    assert res["state"] == "available" and res["version"] == "9.9.9"
    assert [c["version"] for c in res["changes"]] == ["9.9.9"]
    assert updates.FRESING_PT_update.poll(bpy.context)


def test_check_in_background_thread(monkeypatch, tmp_path):
    import threading
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    go = threading.Event()
    real = core.check

    def slow_check(*a, **k):                              # holds the thread until the test lets it go
        go.wait(10)
        return real(*a, **k)
    monkeypatch.setattr(core, "check", slow_check)
    assert updates.check_in_background()
    assert updates._check["state"] == "checking"
    assert not updates.check_in_background()              # one check at a time
    assert updates._poll_check() == 0.5                   # still running: the timer asks again
    go.set()
    updates._thread.join(10)
    assert updates._poll_check() is None                  # the timer (main thread) takes the result over
    assert updates._check["state"] == "available" and updates._check["version"] == "9.9.9"


def test_check_operator_messages(monkeypatch, tmp_path):
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    assert bpy.ops.fresing.update_check() == {"FINISHED"}
    assert updates._check["state"] == "available"
    monkeypatch.setenv(core.URL_ENV, (tmp_path / "missing" / "index.json").as_uri())
    assert bpy.ops.fresing.update_check() == {"FINISHED"}            # reported, not raised
    assert updates._check["state"] == "error" and "could not reach" in updates._check["message"]
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path / "same", version=__version__))
    bpy.ops.fresing.update_check()
    assert updates._check["state"] == "none"


def test_later_hides_until_a_manual_check(monkeypatch, tmp_path):
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    updates.check_now()
    assert updates.notice_kind() == "available"
    bpy.ops.fresing.update_later()
    assert updates.notice_kind() == ""
    bpy.ops.fresing.update_check()
    assert updates.notice_kind() == "available"


def test_installer_config_file_sets_the_address(clean_state, tmp_path, monkeypatch):
    monkeypatch.delenv(core.URL_ENV, raising=False)
    url = _repo(tmp_path)
    (clean_state / core.URL_FILE).write_text(json.dumps({"url": url}), encoding="utf-8")
    assert updates.index_url()[0] == url
    assert updates.check_now()["state"] == "available"


# ---- panel ---------------------------------------------------------------------------------

def test_panel_draws_in_every_state(monkeypatch, tmp_path):
    errors: list[str] = []
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    updates.check_now()
    _draw_panel(errors)                                              # available
    updates._dl.update(active=True, version="9.9.9", done=10_000_000, total=48_000_000)
    _draw_panel(errors)                                              # downloading
    updates._dl.update(active=False, error="Download failed: no answer")
    _draw_panel(errors)                                              # download failed
    updates._dl.clear()
    updates._dl["active"] = False
    updates._check.update(state="needs_installer", version="1.0.0")
    _draw_panel(errors)
    updates._status.update(ok=True, message="Updated to 9.9.9.", to="9.9.9", changes=[
        {"version": "9.9.9", "title": "t", "text": "- a"}])
    _draw_panel(errors)
    updates._status.update(ok=False, message="it did not work", to="9.9.9")
    _draw_panel(errors)
    assert not errors, errors
    # the add-on preferences show the update settings
    from fresing_render.blender import prefs
    p = type("P", (), {"check_updates": True, "bl_rna": prefs.FRESING_AP_prefs.bl_rna})()
    for state in ("available", "none", "error", "off"):
        updates._check.update(state=state, version="9.9.9", message="x")
        prefs.draw_updates(FakeLayout(errors), p)
    assert not errors, errors


def test_status_left_by_the_helper(clean_state, monkeypatch):
    path = pathlib.Path(updates.status_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ok": True, "message": f"Updated to {__version__}.", "from": "0.0.1",
                                "to": __version__}), encoding="utf-8")
    monkeypatch.delenv(updates.RESTART_ENV, raising=False)
    updates.read_status()                                          # a background Blender leaves it for the app
    assert path.exists() and not updates._status
    monkeypatch.setenv(updates.RESTART_ENV, "[]")                   # (tests start the app in the background)
    updates.read_status()
    assert updates._status["ok"] and not path.exists()             # shown once
    assert updates.notice_kind() == "status"
    bpy.ops.fresing.update_close_status()
    assert updates.notice_kind() == ""
    # the helper said OK, but this is not the version it installed: say so
    path.write_text(json.dumps({"ok": True, "message": "Updated to 9.9.9.", "to": "9.9.9"}), encoding="utf-8")
    updates.read_status()
    assert not updates._status["ok"] and "did not take effect" in updates._status["message"]


# ---- update now ----------------------------------------------------------------------------

def test_preflight(monkeypatch):
    assert "not installed with Install.bat" in updates.preflight(bpy.context)       # source folder: no update
    monkeypatch.setattr(updates, "extension_repo", lambda: "user_default")
    bpy.ops.wm.read_homefile(use_empty=True)
    assert updates.preflight(bpy.context) == ""
    monkeypatch.setattr(updates, "project_dirty", lambda: True)         # changes in a project never saved:
    assert updates.preflight(bpy.context) == ""                          # no refusal (task 0316), the box asks
    updates._dl["active"] = True
    assert "already being downloaded" in updates.preflight(bpy.context)
    assert updates.preflight(bpy.context, downloaded=True) == ""


def test_update_now_downloads_saves_starts_helper_and_closes(monkeypatch, tmp_path):
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    monkeypatch.setenv(updates.RESTART_ENV, json.dumps(["blender", "--app-template", "fresing_render", "x.blend"]))
    monkeypatch.setattr(updates, "extension_repo", lambda: "user_default")
    tdir = tmp_path / "template"
    tdir.mkdir()
    (tdir / "__init__.py").write_text("# template", encoding="utf-8")
    monkeypatch.setattr(updates, "template_dir", lambda: str(tdir))
    started, closed = [], []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.append((cmd, kw)))
    monkeypatch.setattr(updates, "quit_app", lambda context: closed.append(True))
    bpy.ops.wm.read_homefile(use_empty=True)
    project = tmp_path / "project é.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    bpy.ops.mesh.primitive_cube_add()                                   # a change to save
    dirty = {"now": True}
    monkeypatch.setattr(updates, "project_dirty", lambda: dirty["now"])
    real_save = updates.save_project

    def save(context):
        err = real_save(context)
        dirty["now"] = bool(err)
        return err
    monkeypatch.setattr(updates, "save_project", save)
    t0 = project.stat().st_mtime_ns
    updates.check_now()
    assert bpy.ops.fresing.update_install() == {"FINISHED"}
    assert closed == [True] and not dirty["now"] and project.stat().st_mtime_ns > t0     # saved, then closed
    cmd, kw = started[0]
    assert cmd[1:4] == ["-I", "-X", "utf8"]                             # any character of a path can be printed
    assert cmd[4].endswith("update_helper.py") and cmd[5].endswith("plan.json")
    assert os.path.dirname(cmd[4]) == updates.update_dir()             # a copy outside the extension
    assert kw["cwd"] == updates.update_dir()
    plan = json.loads(pathlib.Path(cmd[5]).read_text(encoding="utf-8"))
    assert plan["expected_version"] == "9.9.9" and plan["old_version"] == __version__
    assert plan["repo"] == "user_default" and plan["wait_pid"] == os.getpid()
    assert plan["ext_dir"] == updates.PKG_DIR and plan["template_dir"] == str(tdir)
    assert plan["restart"] == ["blender", "--app-template", "fresing_render", "x.blend"]
    assert os.path.isfile(plan["zip"]) and plan["zip"].endswith("fresing_render-9.9.9.zip")
    assert plan["status_file"] == updates.status_path() and plan["log_file"] == updates.log_path()


def test_update_now_stops_on_a_damaged_download(monkeypatch, tmp_path):
    url = _repo(tmp_path)
    index = json.loads((tmp_path / "repo" / "index.json").read_text())
    index["data"][0]["archive_hash"] = "sha256:" + "00" * 32
    (tmp_path / "repo" / "index.json").write_text(json.dumps(index))
    monkeypatch.setenv(core.URL_ENV, url)
    monkeypatch.setattr(updates, "extension_repo", lambda: "user_default")
    monkeypatch.setattr(updates, "quit_app", lambda context: pytest.fail("must not close"))
    bpy.ops.wm.read_homefile(use_empty=True)
    updates.check_now()
    with pytest.raises(RuntimeError, match="damaged"):
        bpy.ops.fresing.update_install()
    assert not updates._dl["active"]


def test_restart_command_reopens_the_project(monkeypatch, tmp_path):
    monkeypatch.delenv(updates.RESTART_ENV, raising=False)
    assert updates.restart_command(bpy.context) == []                  # background: nothing to start again
    exe = tmp_path / "blender.exe"
    exe.write_bytes(b"")
    assert updates.build_restart(str(exe), "fresing_render", "C:/p/x.blend", windows=True) == \
        [str(exe), "--app-template", "fresing_render", "C:/p/x.blend"]
    (tmp_path / "blender-launcher.exe").write_bytes(b"")              # like the Desktop shortcut: no console
    assert updates.build_restart(str(exe), "", "", windows=True) == [str(tmp_path / "blender-launcher.exe")]
    assert updates.build_restart(str(exe), "", "", windows=False) == [str(exe)]


# ---- app template --------------------------------------------------------------------------

def test_refresh_template_copies_the_shipped_template(monkeypatch, tmp_path):
    pkg = tmp_path / "ext"
    (pkg / update_helper.TEMPLATE_FILES_DIR).mkdir(parents=True)
    new = (ROOT / "app_template" / "fresing_render" / "__init__.py").read_bytes()
    (pkg / update_helper.TEMPLATE_FILES_DIR / "__init__.py").write_bytes(new)
    tdir = tmp_path / "template"
    tdir.mkdir()
    (tdir / "__init__.py").write_bytes((ROOT / "tests" / "data" / "old_app_template" / "__init__.py").read_bytes())
    monkeypatch.setattr(updates, "PKG_DIR", str(pkg))
    monkeypatch.setattr(updates, "template_dir", lambda: str(tdir))
    assert updates.refresh_template() == ["__init__.py"]
    assert (tdir / "__init__.py").read_bytes() == new
    assert updates.refresh_template() == []
    monkeypatch.setattr(updates, "template_dir", lambda: "")            # no installed template: leave it
    assert updates.refresh_template() == []


def test_help_menu_entry_under_the_user_guide():
    spec = importlib.util.spec_from_file_location("fresing_template_test",
                                                  ROOT / "app_template" / "fresing_render" / "__init__.py")
    tmpl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tmpl)
    tmpl.register()
    try:
        updates._add_help_entry()
        funcs = [getattr(f, "__name__", "") for f in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()]
        assert funcs.index("_draw_help") == funcs.index("_draw_help_menu") + 1
        assert funcs.count("_draw_help") == 1
    finally:
        tmpl.unregister()
    assert bpy.ops.fresing.update_check.get_rna_type().description.startswith("Look on GitHub")


def test_app_started_while_an_update_installs(clean_state, monkeypatch):
    """Found in the review: someone double-clicks the Desktop icon while the helper installs."""
    import subprocess
    monkeypatch.setenv(updates.RESTART_ENV, "[]")
    busy = pathlib.Path(updates.update_dir()) / update_helper.BUSY_FILE
    busy.parent.mkdir(parents=True, exist_ok=True)
    helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        busy.write_text(json.dumps({"pid": helper.pid, "to": "9.9.9"}), encoding="utf-8")
        status = pathlib.Path(updates.status_path())
        status.write_text(json.dumps({"ok": True, "to": "9.9.9", "message": "x"}), encoding="utf-8")
        updates.read_status()
        assert updates._status.get("installing") and "being installed" in updates._status["message"]
        assert status.exists()                                     # left for the app the helper starts
        errors: list[str] = []
        _draw_panel(errors)
        assert not errors, errors
    finally:
        helper.kill()
        helper.wait()
    updates._status.clear()
    busy.write_text(json.dumps({"pid": helper.pid, "to": "9.9.9"}), encoding="utf-8")     # helper gone: ignored
    updates.read_status()
    assert not updates._status.get("installing")


# ---- task 0053: Update now and the project lock (bug hunt 0045 rows 4, 12) ----------------------

def test_update_now_refuses_a_project_a_colleague_has_open(monkeypatch, tmp_path):
    """Row 4: Update now saved over a shared project a colleague had open."""
    from fresing_render.blender import project_lock
    monkeypatch.setattr(updates, "extension_repo", lambda: "user_default")
    bpy.ops.wm.read_homefile(use_empty=True)
    project = tmp_path / "shared" / "kraan.blend"
    project.parent.mkdir()
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    assert updates.preflight(bpy.context) == ""                          # no lock: unchanged
    now = __import__("time").time()
    lock = pathlib.Path(project_lock.lock_path(str(project)))
    lock.write_text(json.dumps({"user": "anna", "computer": "WS-07", "pid": 4242, "since": now, "heartbeat": now}),
                    encoding="utf-8")
    problem = updates.preflight(bpy.context)
    assert "Someone else has this project open (anna on WS-07 since" in problem and "Save As first" in problem
    assert updates.preflight(bpy.context, downloaded=True) == problem   # also after the download, before saving
    # the button stays and says why when pressed
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    updates.check_now()
    assert bpy.ops.fresing.update_install.poll()
    with pytest.raises(RuntimeError, match="Someone else has this project open"):
        bpy.ops.fresing.update_install()
    assert not updates._dl.get("active")
    # the same user in a second window on this PC (row 19b)
    me = project_lock.me()
    other = __import__("subprocess").Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        monkeypatch.setattr(project_lock, "_window_alive", lambda pid: pid == other.pid)
        lock.write_text(json.dumps(dict(me, pid=other.pid, since=now, heartbeat=now)), encoding="utf-8")
        assert "also open in another Fresing Render window" in updates.preflight(bpy.context)
    finally:
        other.kill()
        other.wait()
    lock.write_text(json.dumps(dict(me, since=now, heartbeat=now)), encoding="utf-8")   # this window's own lock
    assert updates.preflight(bpy.context) == ""
    bpy.ops.wm.read_homefile(use_empty=True)


def test_update_panel_says_why_when_the_project_is_in_use(monkeypatch):
    from fresing_render.blender import project_lock
    updates._check.update(state="available", version="9.9.9", size=1000)
    monkeypatch.setitem(project_lock._STATE, "other", {"user": "anna", "computer": "WS-07", "since": 0})
    texts: list[str] = []
    real_wrap = __import__("fresing_render.blender.ui", fromlist=["wrap"]).wrap

    def wrap(layout, context, text, *a, **kw):
        texts.append(text)
        return real_wrap(layout, context, text, *a, **kw)
    monkeypatch.setattr("fresing_render.blender.ui.wrap", wrap)
    errors: list[str] = []
    _draw_panel(errors)
    assert not errors, errors
    assert any("in use by anna on WS-07" in t and "Save As first" in t for t in texts), texts


def test_killed_helper_does_not_block_update_now(clean_state, monkeypatch):
    """Row 12: an old installing.json (helper killed by a power cut) kept the app on "being installed" and hid
    Update now for good."""
    import time as _time
    monkeypatch.setenv(updates.RESTART_ENV, "[]")
    busy = pathlib.Path(updates.update_dir()) / update_helper.BUSY_FILE
    busy.parent.mkdir(parents=True, exist_ok=True)
    busy.write_text(json.dumps({"pid": os.getpid(), "to": "9.9.9", "exe": sys.executable,
                                "started": _time.time() - update_helper.BUSY_MAX_SECONDS - 10}), encoding="utf-8")
    status = pathlib.Path(updates.status_path())
    status.write_text(json.dumps({"ok": False, "to": "9.9.9", "message": "The update stopped."}), encoding="utf-8")
    updates.read_status()
    assert not updates._status.get("installing") and not busy.exists()
    assert updates._status.get("message") == "The update stopped." and not status.exists()   # the real status is read
    updates._status.clear()
    updates._check.update(state="available", version="9.9.9")
    assert updates.notice_kind() == "available"


# ---- task 0316: save or not ------------------------------------------------------------------

@pytest.fixture()
def updating(monkeypatch, tmp_path):
    """Update now ready to run against a small listing; Popen and the close are recorded; backups go to tmp."""
    from fresing_render.blender import backups
    from fresing_render.core import backups as bcore
    monkeypatch.setenv(core.URL_ENV, _repo(tmp_path))
    monkeypatch.delenv(updates.RESTART_ENV, raising=False)
    monkeypatch.setattr(updates, "extension_repo", lambda: "user_default")
    monkeypatch.setattr(updates, "template_dir", lambda: "")
    monkeypatch.setattr(updates, "_background", lambda: False)          # the restart command as in the app
    docs = tmp_path / "Documents"
    docs.mkdir()
    monkeypatch.setattr(backups, "documents", lambda: str(docs))
    monkeypatch.setattr(backups, "state_path", lambda: str(tmp_path / "config" / bcore.STATE_FILE))
    on = {"backups": True}
    monkeypatch.setattr(backups, "settings", lambda: (on["backups"], 5, 5, 7))
    rec = {"started": [], "closed": []}
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: rec["started"].append(cmd))
    monkeypatch.setattr(updates, "quit_app", lambda context, ask=True: rec["closed"].append(ask))
    bpy.ops.wm.read_homefile(use_empty=True)
    backups.restart_clock()
    backups._S["opened_at"] = time.time() - 1
    rec["on"] = on
    rec["backups"] = backups
    return rec


def _plan(rec) -> dict:
    return json.loads(pathlib.Path(rec["started"][-1][5]).read_text(encoding="utf-8"))


def _dirty_saved_project(tmp_path):
    project = tmp_path / "job é" / "Crane é.blend"
    project.parent.mkdir()
    bpy.context.scene["mark"] = "saved"
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    bpy.context.scene["mark"] = "changed"
    bpy.ops.mesh.primitive_cube_add()
    old = time.time() - 600                                             # saved 10 minutes ago
    os.utime(project, (old, old))
    return project


def test_update_without_saving_leaves_the_project_file_and_keeps_one_backup(updating, tmp_path, monkeypatch):
    project = _dirty_saved_project(tmp_path)
    monkeypatch.setattr(updates, "project_dirty", lambda: True)
    before = (project.stat().st_mtime_ns, project.read_bytes())
    updates.check_now()
    assert bpy.ops.fresing.update_install(save="DONT_SAVE") == {"FINISHED"}
    assert updating["closed"] == [False]                                # closed without "Save changes?"
    assert (project.stat().st_mtime_ns, project.read_bytes()) == before   # the project file is untouched
    kept = updates._dl["kept"]
    assert os.path.isfile(kept) and os.path.dirname(kept) == str(project.parent / "Backups")
    assert len(os.listdir(project.parent / "Backups")) == 1
    assert _plan(updating)["restart"][-1] == str(project)               # opens again with the saved file
    assert updating["backups"].offer()[0] is None                       # the next start asks nothing
    from fresing_render.core import backups as bcore                    # (without the mark it would ask)
    assert bcore.newest_newer(updating["backups"].project_backups(str(project)), os.path.getmtime(project)).path == kept


def test_update_without_saving_and_backups_off_makes_no_copy(updating, tmp_path, monkeypatch):
    project = _dirty_saved_project(tmp_path)
    monkeypatch.setattr(updates, "project_dirty", lambda: True)
    updating["on"]["backups"] = False
    updates.check_now()
    assert bpy.ops.fresing.update_install(save="DONT_SAVE") == {"FINISHED"}
    assert updating["closed"] == [False] and updates._dl["kept"] == ""
    assert not (project.parent / "Backups").exists()


def test_save_and_update_saves(updating, tmp_path, monkeypatch):
    project = _dirty_saved_project(tmp_path)
    dirty = {"now": True}                                               # (a background Blender keeps no undo)
    monkeypatch.setattr(updates, "project_dirty", lambda: dirty["now"])
    real_save = updates.save_project
    monkeypatch.setattr(updates, "save_project", lambda c: dirty.update(now=False) or real_save(c))
    t0 = project.stat().st_mtime_ns
    time.sleep(0.01)
    updates.check_now()
    assert bpy.ops.fresing.update_install(save="SAVE") == {"FINISHED"}
    assert updating["closed"] == [True] and project.stat().st_mtime_ns > t0
    assert not (project.parent / "Backups").exists()


def test_never_saved_without_saving_restarts_empty(updating, monkeypatch):
    bpy.context.scene["mark"] = "never saved"
    monkeypatch.setattr(updates, "project_dirty", lambda: True)
    updates.check_now()
    assert bpy.ops.fresing.update_install(save="DONT_SAVE") == {"FINISHED"}
    assert updating["closed"] == [False]
    restart = _plan(updating)["restart"]
    assert restart and not any(a.endswith(".blend") for a in restart)    # the app's empty start
    from fresing_render.core import backups as bcore
    kept = updates._dl["kept"]
    assert os.path.dirname(kept) == bcore.unsaved_folder(updating["backups"].documents())
    assert updating["backups"].offer()[0] is None                       # the next start asks nothing


def test_never_saved_save_in_the_background_says_so(updating, monkeypatch):
    monkeypatch.setattr(updates, "project_dirty", lambda: True)
    updates.check_now()
    with pytest.raises(RuntimeError, match="never been saved"):
        bpy.ops.fresing.update_install(save="SAVE")
    assert not updating["started"] and not updating["closed"]


def test_save_as_and_update_goes_on_after_the_save_and_stops_on_cancel(updating, tmp_path, monkeypatch):
    """The timer after Blender's Save As (the file browser itself needs a window: tools/ci_update_test.py)."""
    begun = []
    monkeypatch.setattr(updates, "begin_update", lambda context, save: begun.append(save))
    clock = {"t": 1000.0}
    monkeypatch.setattr(updates.time, "time", lambda: clock["t"])
    browser = {"open": True}
    monkeypatch.setattr(updates, "_save_browser_open", lambda: browser["open"])
    # cancelled: the browser was open, then closed without a file
    updates._save_as.update(t0=clock["t"], seen=False, gone=0.0)
    assert updates._wait_save_as() == 0.3
    browser["open"] = False
    clock["t"] += 0.3
    assert updates._wait_save_as() == 0.5                               # closed: a moment for the save
    clock["t"] += 1.1
    assert updates._wait_save_as() is None
    assert updates._ui["note"] == updates.NOT_SAVED_NOTE and not begun and not updates._save_as
    # saved: the update starts as Save and update
    updates._save_as.update(t0=clock["t"], seen=True, gone=0.0)
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "new project.blend"))
    updates.check_now()
    assert updates._wait_save_as() is None
    assert begun == ["SAVE"]


def test_no_save_question_is_for_this_close_only():
    prefs = bpy.context.preferences
    was = (prefs.view.use_save_prompt, prefs.is_dirty)
    try:
        prefs.view.use_save_prompt = True
        prefs.is_dirty = False
        updates.no_save_question(prefs)
        assert not prefs.view.use_save_prompt
        assert not prefs.is_dirty                                       # never written into the preferences
    finally:
        prefs.view.use_save_prompt = was[0]
        prefs.is_dirty = was[1]


def test_the_box_text_and_tooltips():
    t = updates.box_text("9.9.9", saved=True, backup=True)
    assert any("as you last saved it" in p for p in t) and t[-1] == "A backup copy is kept (Backups)."
    t = updates.box_text("9.9.9", saved=False, backup=False)
    assert any("opens again empty" in p for p in t) and not any("backup" in p for p in t)
    rna = bpy.ops.fresing.update_install.get_rna_type()
    assert "asks first" in rna.description and rna.properties["save"].description
    assert bpy.ops.fresing.update_box_cancel.get_rna_type().description
