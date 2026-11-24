"""Updates inside the app: "Update available: 0.x.y" -> Update now -> the app closes, updates, opens again.

* At start-up (a few seconds after the window opens) the newest version is looked up on GitHub
  (``core/updates.py``; off in Preferences or when Blender's online access is off).
* The panel "Update available" at the top of the Fresing tab shows the new version, what's new
  (from the changelog) and **Update now**.
* Update now: download the extension zip (checked against size and SHA-256), save the project,
  start ``update_helper.py`` with Blender's own Python and close Blender. The helper installs the
  zip with Blender's own extension installer, copies the new app template and starts the app again
  with the same project. At that start the panel says "Updated to 0.x.y" (or what went wrong).
* Task 0316: with unsaved changes Update now asks first (a box of its own, ``draw``): **Save and update**
  (a project never saved: **Save as… and update** – Blender's Save As, the update goes on once it is
  saved, ``_wait_save_as``) or **Update without saving**: one backup copy (when backups are on, marked as
  dealt with so the next start asks nothing – ``backups.keep_unsaved_work``), then the app closes without
  Blender's "Save changes?" (``no_save_question``) and opens again with the file as it is on disk, or
  empty. Scripts and tests choose with the operator's ``save`` ('SAVE' / 'DONT_SAVE').
* The app template (``app_template/`` in the repository) ships inside the extension as
  ``app_template_files/``; the helper copies it, and every start copies it again when it differs
  (an update made some other way brings the right template too).
* Help > Check for Fresing Render updates asks at any time.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time

import bpy

from .. import __version__ as INSTALLED
from .. import update_helper
from ..core import updates as core

PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_NAME = "fresing_render"
RESTART_ENV = "FRESING_UPDATE_RESTART"       # tests: the command that starts the app again (JSON list)
RESTART_EXTRA_ENV = "FRESING_UPDATE_RESTART_EXTRA"   # tests: arguments added to the usual command (JSON list)
CHECK_DELAY = 4.0                            # seconds after start-up

# result of the last check (main thread only)
_check: dict = {"state": "idle"}
# download in progress (written by the download thread, read by the main thread)
_dl: dict = {"active": False}
# message left by update_helper.py for this start ("Updated to 0.x.y" or what went wrong)
_status: dict = {}
_ui = {"later": False, "manual": False, "note": ""}
_thread: threading.Thread | None = None


# ---------------------------------------------------------------------------
# where things are
# ---------------------------------------------------------------------------

def update_dir() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), "fresing_update")


def status_path() -> str:
    return os.path.join(update_dir(), "status.json")


def log_path() -> str:
    return os.path.join(update_dir(), "update.log")


def index_url() -> tuple[str, str]:
    return core.index_url_from(bpy.utils.user_resource("CONFIG"))


def template_dir() -> str:
    """The installed app template (Install.bat puts it there); '' when there is none."""
    path = bpy.utils.user_resource("SCRIPTS", path=os.path.join("startup", "bl_app_templates_user", TEMPLATE_NAME))
    return path if os.path.isfile(os.path.join(path, "__init__.py")) else ""


def extension_repo() -> str:
    """The extension repository this copy is installed in ('user_default'); '' when it is not
    installed as an extension (development, tests from the source folder)."""
    parts = __package__.split(".")
    if len(parts) >= 3 and parts[0] == "bl_ext":
        return parts[1]
    return ""


def addon_prefs():
    from . import prefs
    return prefs.get()


# ---------------------------------------------------------------------------
# app template
# ---------------------------------------------------------------------------

def refresh_template() -> list[str]:
    """Copy the app template that ships inside this extension over the installed one where it
    differs (it takes effect at the next start). Returns the files copied."""
    src = os.path.join(PKG_DIR, update_helper.TEMPLATE_FILES_DIR)
    dst = template_dir()
    if not (os.path.isdir(src) and dst):
        return []
    changed = update_helper.copy_template(src, dst)
    if changed:
        print("Fresing Render: app template updated:", ", ".join(changed))
    return changed


# ---------------------------------------------------------------------------
# checking
# ---------------------------------------------------------------------------

def _redraw() -> None:
    wm = bpy.context.window_manager
    if wm is None:
        return
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type in ("VIEW_3D", "PREFERENCES", "TOPBAR"):
                area.tag_redraw()


def check_now(manual: bool = False, timeout: float = core.TIMEOUT) -> dict:
    """Look for a newer version now (waits for the answer)."""
    global _check
    if not bpy.app.online_access:
        _check = {"state": "off", "message": "Blender's online access is off (Edit > Preferences > System > "
                                             "Network > Allow Online Access)"}
        return _check
    url, _src = index_url()
    _check = core.check(url, INSTALLED, tuple(bpy.app.version), timeout=timeout)
    _check["checked_at"] = time.time()
    if manual:
        _ui["later"] = False
    return _check


_pending: dict = {}


def check_in_background() -> bool:
    """Start a check that does not hold up the app; the panel appears when it finds something."""
    global _thread, _check
    if _thread is not None and _thread.is_alive():
        return False
    if not bpy.app.online_access:
        _check = {"state": "off"}
        return False
    url, _src = index_url()
    version = tuple(bpy.app.version)
    _pending.clear()

    def work():
        _pending["result"] = core.check(url, INSTALLED, version)

    _check = {"state": "checking"}
    _thread = threading.Thread(target=work, name="fresing-update-check", daemon=True)
    _thread.start()
    bpy.app.timers.register(_poll_check, first_interval=0.5)
    return True


def _poll_check():
    """Timer (main thread): take the result of the background check over."""
    global _check
    if _thread is not None and _thread.is_alive():
        return 0.5
    _check = dict(_pending.get("result") or {"state": "error", "message": "the check stopped"},
                  checked_at=time.time())
    if _check.get("state") == "available":
        print(f"Fresing Render: update available: {_check.get('version')}")
    _redraw()
    return None


def _startup_check():
    try:
        p = addon_prefs()
        if p is not None and not p.check_updates:
            return None
        if bpy.app.online_access:
            check_in_background()
    except Exception as exc:  # noqa: BLE001 - never disturb the start of the app
        print("Fresing Render: update check failed:", exc)
    return None


# ---------------------------------------------------------------------------
# updating
# ---------------------------------------------------------------------------

def preflight(context, downloaded: bool = False) -> str:
    """'' when an update can start now, otherwise what is in the way (in plain words).
    ``downloaded``: asked again once the download is done (it is no longer "in the way")."""
    if not extension_repo():
        return "This copy of Fresing Render was not installed with Install.bat, so it cannot update itself"
    if _dl.get("active") and not downloaded:
        return "The update is already being downloaded"
    try:
        from . import ops_import
        job = ops_import._ACTIVE_JOB
        if job is not None and not job.done:
            return "A STEP import is running: wait until it has finished, then press Update now"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import queue
        if any(queue.is_running(scene) for scene in bpy.data.scenes) or any(
                r["pid"] and queue._pid_alive(r["pid"], r["dir"]) for r in queue._RUNS.values()):
            return ("The render queue is still running (panel 7): update when it has finished, "
                    "or stop it first")
        if queue.delay_pending():           # the restart would drop it silently (0068 row 3)
            return (f"A delayed queue start is set for {queue.delay_clock()} (panel 7): cancel it (Cancel), or "
                    "update when that queue has finished")
    except Exception:  # noqa: BLE001
        pass
    other = lock_holder()
    if other.startswith("you,"):
        return ("This project is also open in another Fresing Render window on this PC: close that window "
                "first, then press Update now")
    if other:
        return (f"Someone else has this project open ({other}): Save As first (File > Save As…, a new name), or "
                "open another project, then press Update now. Updating would save over their work")
    others = other_blenders()
    if others:
        return (f"Another Fresing Render is still open ({len(others)} more Blender running: a second window, a "
                "queued render or the PC check). Close it first, then press Update now")
    return ""


def lock_holder() -> str:
    """Who else has the open project (a colleague, or this user in another window), read from its lock now; ''
    when nobody. Update now saves the project before closing, so it must not run then (bug hunt 0045 row 4)."""
    path = bpy.data.filepath
    if not path:
        return ""
    from . import project_lock
    try:
        info = project_lock.other_user(path)
    except Exception:  # noqa: BLE001 - a share that cannot be read: no lock
        return ""
    return project_lock.describe(info) if info else ""


def other_blenders() -> list[int]:
    """Other Blenders started from this app's Blender folder (the helper would have to wait for them)."""
    exe = bpy.app.binary_path
    if not exe or os.path.basename(exe).lower() not in update_helper.BLENDER_NAMES:
        return []                                    # Blender as a Python module (tests)
    try:
        return update_helper.other_blenders(os.path.dirname(exe), exclude=(os.getpid(),))
    except Exception:  # noqa: BLE001
        return []


def project_dirty() -> bool:
    return bool(bpy.data.is_dirty)


NEVER_SAVED = "This project has never been saved: save it first (File > Save As…), then press Update now"
NOT_SAVED_NOTE = "Not saved, so the update did not start. Press Update now again when you are ready."


def box_text(version: str, saved: bool, backup: bool) -> list[str]:
    """The Update now box's text when the project has unsaved changes (task 0316), one paragraph per item."""
    out = [f"Fresing Render downloads {version}, closes, updates and opens again by itself (about a minute). "
           "This project has unsaved changes."]
    if saved:
        out.append("Save and update: your changes are saved first; the project opens again.")
        out.append("Without saving, the app opens again with the project as you last saved it – the changes since "
                   "then are lost.")
    else:
        out.append("Save as… and update: choose a name and a folder first; the update goes on once it is saved.")
        out.append("Without saving, the app opens again empty – this project is not kept as a project file.")
    if backup:
        out.append("A backup copy is kept (Backups).")
    return out


def backups_on() -> bool:
    try:
        from . import backups
        return bool(backups.settings()[0])
    except Exception:  # noqa: BLE001
        return False


def save_project(context) -> str:
    """Save the open project before closing; '' or what went wrong."""
    try:
        with context.temp_override(**_window_override()):
            bpy.ops.wm.save_mainfile()
    except Exception as exc:  # noqa: BLE001
        return f"The project could not be saved ({exc}): save it yourself, then press Update now"
    return ""


def restart_command(context) -> list[str]:
    """How to start the app again after the update: the same program, app layout and project."""
    if os.environ.get(RESTART_ENV):
        return list(json.loads(os.environ[RESTART_ENV]))
    if _background():
        return []
    extra = json.loads(os.environ[RESTART_EXTRA_ENV]) if os.environ.get(RESTART_EXTRA_ENV) else []
    return build_restart(bpy.app.binary_path, getattr(context.preferences, "app_template", "") or "",
                         bpy.data.filepath, sys.platform == "win32") + list(extra)


def _background() -> bool:
    return bool(bpy.app.background)


def build_restart(exe: str, template: str, filepath: str, windows: bool) -> list[str]:
    if windows:                                 # starts Blender without a console window (as the shortcut)
        from .. import winexe                   # task 0177: "Fresing Render.exe" when it is there and usable
        copy = winexe.copy_path(winexe.blender_exe_of(exe))
        launcher = os.path.join(os.path.dirname(exe), "blender-launcher.exe")
        if (winexe.is_copy(exe) and os.path.isfile(exe)) or (
                os.path.isfile(copy) and winexe.usable(winexe.blender_exe_of(exe)) and winexe.sac_state() == 0):
            exe = copy
        elif os.path.isfile(launcher):
            exe = launcher
    cmd = [exe]
    if template:
        cmd += ["--app-template", template]
    if filepath:
        cmd.append(filepath)
    return cmd


def _download_worker(info: dict, dest: str) -> None:
    def progress(done, total):
        _dl["done"], _dl["total"] = done, total

    try:
        core.download(info["url"], dest, size=info.get("size", 0), sha256=info.get("sha256", ""),
                      version=INSTALLED, progress=progress, should_stop=lambda: _dl.get("stop"))
        _dl["path"] = dest
    except core.DownloadError as exc:
        _dl["error"] = "" if str(exc) == "stopped" else f"Download failed: {exc}"
    except Exception as exc:  # noqa: BLE001
        _dl["error"] = "Download failed: " + core.describe_error(exc)


def start_download(info: dict, blocking: bool = False, save: str = "SAVE") -> None:
    os.makedirs(update_dir(), exist_ok=True)
    for old in os.listdir(update_dir()):                     # earlier, unfinished downloads
        if old.endswith((".zip", ".part")):
            try:
                os.remove(os.path.join(update_dir(), old))
            except OSError:
                pass
    dest = os.path.join(update_dir(), f"fresing_render-{info['version']}.zip")
    _dl.clear()
    _dl.update(active=True, version=info["version"], done=0, total=info.get("size", 0), error="", path="",
               stop=False, save=save)
    if blocking:
        _download_worker(info, dest)
        return
    th = threading.Thread(target=_download_worker, args=(info, dest), name="fresing-update-download", daemon=True)
    _dl["thread"] = th
    th.start()


def launch_helper(context, zip_path: str, version: str) -> dict:
    """Write the plan, start update_helper.py (a copy outside the extension folder, which the
    update replaces) with Blender's own Python. Returns the plan."""
    from ..importer.runner import python_executable
    work = update_dir()
    os.makedirs(work, exist_ok=True)
    helper = os.path.join(work, "update_helper.py")
    shutil.copy2(update_helper.__file__, helper)
    try:                                                  # keep the log short: the last runs only
        if os.path.getsize(log_path()) > 500_000:
            os.replace(log_path(), log_path() + ".old")
    except OSError:
        pass
    try:
        os.remove(status_path())
    except OSError:
        pass
    plan = {
        "blender": bpy.app.binary_path,
        "wait_pid": os.getpid(),
        "zip": zip_path,
        "expected_version": version,
        "old_version": INSTALLED,
        "repo": extension_repo() or "user_default",
        "ext_dir": PKG_DIR,
        "template_dir": template_dir(),
        "restart": restart_command(context),
        "status_file": status_path(),
        "log_file": log_path(),
    }
    plan_path = os.path.join(work, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)
    import subprocess
    # -X utf8: the helper's console output may hold any character of a path (a hidden console's code
    # page cannot); -I: nothing from the environment or from its folder is loaded
    cmd = [python_executable(), "-I", "-X", "utf8", helper, plan_path]
    kwargs = dict(cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  close_fds=True)
    if sys.platform == "win32":
        flags = update_helper.CREATE_NO_WINDOW | update_helper.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(cmd, creationflags=flags | update_helper.CREATE_BREAKAWAY_FROM_JOB, **kwargs)
        except OSError:
            subprocess.Popen(cmd, creationflags=flags, **kwargs)
    else:
        subprocess.Popen(cmd, start_new_session=True, **kwargs)
    return plan


def _window_override():
    wm = bpy.context.window_manager
    win = bpy.context.window or (wm.windows[0] if wm and wm.windows else None)
    return {"window": win} if win is not None else {}


def finish_update(context=None) -> str:
    """After the download: save (or not: ``_dl["save"]``, task 0316), start the helper, close the app. Returns an
    error text or ''.

    In a window, Blender counts a saved project as saved only once its event loop has run again: closing
    straight after saving would still ask "Save changes?". So after saving, the helper is started and
    the app closed by a timer a moment later (``_close_when_saved``)."""
    context = context or bpy.context
    path = _dl.get("path", "")
    if not path or not os.path.isfile(path):
        return "The download is missing: press Update now again"
    problem = preflight(context, downloaded=True)
    if problem:
        return problem
    if project_dirty() and _dl.get("save") == "DONT_SAVE":
        update_without_saving(context)
        return ""
    if project_dirty() and not bpy.data.filepath:
        return NEVER_SAVED
    if project_dirty() and bpy.data.filepath:
        err = save_project(context)
        if err:
            return err
        if not bpy.app.background:
            _dl.update(active=True, saving=time.time())
            bpy.app.timers.register(_close_when_saved, first_interval=0.3)
            return ""
    launch_and_quit(context)
    return ""


def launch_and_quit(context) -> None:
    launch_helper(context, _dl["path"], _dl.get("version", ""))
    _dl["active"] = False
    print(f"Fresing Render: closing to install {_dl.get('version', '')}; it opens again by itself")
    quit_app(context)


def update_without_saving(context) -> None:
    """Task 0316: one backup copy of the unsaved work (when backups are on; the next start does not offer it), then
    the helper and a close without Blender's "Save changes?". The app opens again with the project file as it is on
    disk (``restart_command`` names ``bpy.data.filepath``), or empty when it was never saved."""
    try:
        from . import backups
        _dl["kept"] = backups.keep_unsaved_work(context.scene)
    except Exception as exc:  # noqa: BLE001 - a backup that fails must not stop the update
        _dl["kept"] = ""
        print("Fresing Render: no backup copy before the update:", exc)
    launch_helper(context, _dl["path"], _dl.get("version", ""))
    _dl["active"] = False
    print(f"Fresing Render: closing without saving to install {_dl.get('version', '')}; it opens again by itself")
    quit_app(context, ask=False)


def no_save_question(prefs) -> None:
    """Close without Blender's "Save changes?" window (task 0316): its preference "Save Prompt" is switched off for
    this close only. Blender writes changed preferences when it closes (with Auto-Save Preferences on), so: the
    user's own pending changes are saved first, as that close would have done, and the preferences are then marked
    unchanged – the switched-off prompt is never written; the next start has it on again."""
    view = prefs.view
    if not view.use_save_prompt:
        return
    auto = bool(prefs.use_preferences_save)
    if prefs.is_dirty and auto and not bpy.app.background:
        try:
            bpy.ops.wm.save_userpref()
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: could not save the preferences before closing:", exc)
    was = bool(prefs.is_dirty)
    view.use_save_prompt = False
    prefs.is_dirty = was and not auto


def _save_browser_open() -> bool:
    """Is Blender's Save As file browser open (in any window)?"""
    wm = bpy.context.window_manager
    for win in (wm.windows if wm else ()):
        for area in (win.screen.areas if win.screen else ()):
            if area.type != "FILE_BROWSER":
                continue
            op = getattr(area.spaces.active, "active_operator", None)
            if op is not None and "save_as_mainfile" in (getattr(op, "bl_idname", "") or "").lower():
                return True
    return False


_save_as: dict = {}


def start_save_as(context) -> str:
    """Save as… and update (task 0316): Blender's Save As; ``_wait_save_as`` starts the update once the project
    has a file. '' or what went wrong."""
    try:
        with context.temp_override(**_window_override()):
            from . import project_name          # task 0291: a new project's name proposed
            kw = {} if bpy.data.filepath else {"filepath": project_name.proposed_path(bpy.context.scene)}
            bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT", **kw)
    except Exception as exc:  # noqa: BLE001
        return f"Save As could not open ({exc}): save the project with File > Save As, then press Update now"
    _save_as.clear()
    _save_as.update(t0=time.time(), seen=False, gone=0.0)
    if not bpy.app.timers.is_registered(_wait_save_as):
        bpy.app.timers.register(_wait_save_as, first_interval=0.3)
    return ""


def _wait_save_as():
    """Timer after Save as… and update: the project saved -> the update starts as "Save and update"; the file
    browser closed without a save (Cancel) -> a plain line, Update now stays offered."""
    try:
        if not _save_as:
            return None
        if bpy.data.filepath:
            _save_as.clear()
            problem = preflight(bpy.context)
            if problem:
                _ui["note"] = problem
            else:
                begin_update(bpy.context, "SAVE")
            _redraw()
            return None
        now = time.time()
        if _save_browser_open():
            _save_as.update(seen=True, gone=0.0)
            return 0.3
        if not _save_as["seen"] and now - _save_as["t0"] < 5.0:
            return 0.3                              # the browser is still opening
        if not _save_as["gone"]:
            _save_as["gone"] = now                   # closed: the save itself may follow a moment later
            return 0.5
        if now - _save_as["gone"] < 1.0:
            return 0.3
        _save_as.clear()
        _ui["note"] = NOT_SAVED_NOTE
        _redraw()
    except Exception as exc:  # noqa: BLE001
        _save_as.clear()
        _ui["note"] = f"The update did not start ({exc})"
        _redraw()
    return None


def begin_update(context, save: str) -> None:
    """Start the download in the window (its timer finishes the update)."""
    info = dict(_check)
    _ui["note"] = ""
    start_download(info, save=save)
    if not bpy.app.timers.is_registered(_poll_download):
        bpy.app.timers.register(_poll_download, first_interval=0.25)


def _close_when_saved():
    """Timer after saving: once Blender counts the project as saved, start the helper and close."""
    if project_dirty():
        if time.time() - _dl.get("saving", 0) < 5.0:
            return 0.3
        _dl.update(active=False, error="The project could not be saved: save it yourself, then press Update now")
        _redraw()
        return None
    try:
        launch_and_quit(bpy.context)
    except Exception as exc:  # noqa: BLE001
        _dl.update(active=False, error=f"The update could not start ({exc})")
        _redraw()
    return None


def quit_app(context, ask: bool = True) -> None:
    """Close Blender (the project is saved by then, or the user chose not to save it: ``ask=False`` closes without
    Blender's "Save changes?"); update_helper.py waits for this."""
    if sys.platform == "win32":                 # let the app that the helper starts come to the front
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)        # ASFW_ANY
        except Exception:  # noqa: BLE001
            pass
    if not ask:
        no_save_question(context.preferences)
    with context.temp_override(**_window_override()):
        bpy.ops.wm.quit_blender()


def _poll_download():
    th = _dl.get("thread")
    if th is not None and th.is_alive():
        _redraw()
        return 0.25
    if _dl.get("stop") or _dl.get("error"):
        _dl["active"] = False
        _redraw()
        return None
    err = finish_update()
    if err:
        _dl.update(active=False, error=err)
        _redraw()
    return None


def read_status() -> None:
    """The message update_helper.py left for this start; shown once, then the file is removed.

    A Blender in the background (render queue, self-test, Blender's own installer run by the helper)
    leaves it for the app; only the tests start the app again in the background (RESTART_ENV)."""
    global _status
    if bpy.app.background and not os.environ.get(RESTART_ENV):
        return
    info = update_helper.busy_helper(os.path.join(update_dir(), update_helper.BUSY_FILE))
    if info is not None:              # a helper killed half-way leaves an old file: busy_helper removes it
        _status = {"ok": False, "installing": True, "to": info.get("to", ""),
                   "message": f"Fresing Render {info.get('to', '')} is being installed right now. Close this "
                              "window without saving; the app opens again by itself in a moment."}
        print("Fresing Render: an update is being installed")
        return
    path = status_path()
    try:
        with open(path, encoding="utf-8") as fh:
            _status = json.load(fh)
        os.remove(path)
    except (OSError, ValueError):
        return
    if _status.get("ok") and _status.get("to") and _status.get("to") != INSTALLED:
        _status = dict(_status, ok=False, message=f"The update to {_status['to']} did not take effect: "
                                                  f"this is still {INSTALLED}.")
    print("Fresing Render update:", _status.get("message", ""))
    if _status.get("ok"):                    # "what's new" of the version just installed
        _status["changes"] = _installed_changes(_status.get("from", ""))


def _installed_changes(old: str) -> list:
    """What's new since ``old``, from changelog.json next to the installed extension (shipped by the
    build); [] when there is none."""
    try:
        with open(os.path.join(PKG_DIR, core.CHANGELOG_NAME), encoding="utf-8") as fh:
            versions = json.load(fh).get("versions", [])
    except (OSError, ValueError, AttributeError):
        return []
    return core.changes_between(versions, old or "0", INSTALLED)


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

def _draw_changes(layout, context, entries: list, limit: int = 40) -> None:
    from .ui import wrap
    shown = 0
    for head, paras in core.whats_new_paragraphs(entries):
        wrap(layout, context, head, icon="DOT")
        for p in paras:
            if shown >= limit:
                layout.label(text="… more on the release page")
                return
            wrap(layout, context, p, inset=12)
            shown += 1


class FRESING_OT_update_check(bpy.types.Operator):
    """Look on GitHub for a newer version of Fresing Render now. If there is one, the Fresing tab shows
    "Update available" with what's new and an Update now button"""

    bl_idname = "fresing.update_check"
    bl_label = "Check for Fresing Render updates"

    def execute(self, context):
        res = check_now(manual=True, timeout=12)
        state = res.get("state")
        if state == "available":
            msg = f"Update available: {res['version']}. Press Update now in the Fresing tab"
            self.report({"INFO"}, msg)
        elif state == "none":
            msg = f"You have the newest version ({INSTALLED})"
            self.report({"INFO"}, msg)
        elif state == "needs_installer":
            msg = f"Version {res['version']} needs a new installer: download it from the release page"
            self.report({"WARNING"}, msg)
        else:
            msg = "Could not check for updates: " + res.get("message", "unknown problem")
            self.report({"WARNING"}, msg)
        if not bpy.app.background:
            def draw(menu, _ctx):
                col = menu.layout.column()
                col.label(text=msg, icon="INFO" if state in ("available", "none") else "ERROR")
                if state == "available":
                    col.operator("fresing.update_install", icon="IMPORT")
                elif state == "needs_installer":
                    col.operator("fresing.update_release_page", text="Open the release page", icon="URL")
            context.window_manager.popup_menu(draw, title="Fresing Render updates", icon="FILE_REFRESH")
        _redraw()
        return {"FINISHED"}


SAVE_ITEMS = (("SAVE", "Save and update", "Save the project first (a project never saved: Save As), then update"),
              ("DONT_SAVE", "Update without saving", "Update without saving the changes since the last save"))
BOX_WIDTH = 560
BOX_CHARS = 96                                    # characters per line of the box's text at its width


class FRESING_OT_update_install(bpy.types.Operator):
    """Download the new version, close Fresing Render, install the update and open the app again (about a
    minute). With unsaved changes it asks first: save them, or update without saving. Your projects, renders and
    settings stay as they are"""

    bl_idname = "fresing.update_install"
    bl_label = "Update now"

    save: bpy.props.EnumProperty(
        name="Unsaved changes", items=SAVE_ITEMS, default="SAVE", options={"SKIP_SAVE"},
        description="What happens to unsaved changes: saved first (Save and update), or left out (Update without "
                    "saving)")

    @classmethod
    def poll(cls, context):
        return _check.get("state") == "available" and not _dl.get("active")

    @classmethod
    def description(cls, context, properties):
        if not properties.is_property_set("save"):
            return " ".join(cls.__doc__.split())
        if properties.save == "DONT_SAVE":
            if bpy.data.filepath:
                return ("Updates without saving: the app closes and opens again with the project as you last "
                        "saved it – the changes since then are lost. A backup copy is kept when backups are on")
            return ("Updates without saving: the app closes and opens again empty – this project is not kept as "
                    "a project file. A backup copy is kept when backups are on")
        if not bpy.data.filepath:
            return ("Opens Save As: choose a name and a folder for the project. Once it is saved, the update goes "
                    "on by itself (download, close, update, open again with the project)")
        return ("Saves your changes, then downloads the update, closes, updates and opens again with the "
                "project (about a minute)")

    def invoke(self, context, event):
        problem = preflight(context)
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        _ui["note"] = ""
        if project_dirty():                          # task 0316: save or not – the box below (draw)
            return context.window_manager.invoke_popup(self, width=BOX_WIDTH)
        msg = (f"Fresing Render downloads {_check.get('version')}, closes, updates and opens again by itself "
               "(about a minute).")
        return context.window_manager.invoke_confirm(self, event, title=f"Update to {_check.get('version')}",
                                                     message=msg, confirm_text="Update now", icon="INFO")

    def draw(self, context):
        import textwrap
        layout = self.layout
        layout.label(text=f"Update to {_check.get('version', '')}", icon="IMPORT")
        saved = bool(bpy.data.filepath)
        col = layout.column(align=True)
        for i, para in enumerate(box_text(_check.get("version", ""), saved, backups_on())):
            if i:
                col.separator(factor=0.4)
            for line in textwrap.wrap(para, BOX_CHARS):
                col.label(text=line)
        layout.separator()
        row = layout.row()
        row.scale_y = 1.3
        row.operator_context = "EXEC_DEFAULT"        # the buttons run the update; they do not open this box again
        op = row.operator("fresing.update_install", text="Save and update" if saved else "Save as… and update",
                          icon="FILE_TICK", depress=True)
        op.save = "SAVE"
        op = row.operator("fresing.update_install", text="Update without saving", icon="IMPORT")
        op.save = "DONT_SAVE"
        row.operator("fresing.update_box_cancel", text="Cancel")

    def execute(self, context):
        problem = preflight(context)
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        _ui["note"] = ""
        if self.save == "SAVE" and project_dirty() and not bpy.data.filepath:
            if bpy.app.background:                   # no file browser here
                self.report({"ERROR"}, NEVER_SAVED)
                return {"CANCELLED"}
            err = start_save_as(context)             # the update starts once the project is saved
            if err:
                self.report({"ERROR"}, err)
                return {"CANCELLED"}
            return {"FINISHED"}
        info = dict(_check)
        if bpy.app.background:                       # tests and scripts: everything in one go
            start_download(info, blocking=True, save=self.save)
            if _dl.get("error"):
                self.report({"ERROR"}, _dl["error"])
                _dl["active"] = False
                return {"CANCELLED"}
            err = finish_update(context)
            if err:
                self.report({"ERROR"}, err)
                return {"CANCELLED"}
            return {"FINISHED"}
        begin_update(context, self.save)
        self.report({"INFO"}, f"Downloading Fresing Render {info.get('version')}…")
        return {"FINISHED"}


class FRESING_OT_update_box_cancel(bpy.types.Operator):
    """Close this box without updating: nothing is downloaded, saved or changed. Update now stays offered"""

    bl_idname = "fresing.update_box_cancel"
    bl_label = "Cancel"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_update_cancel(bpy.types.Operator):
    """Stop downloading the update. Nothing has been changed yet; you can press Update now again later"""

    bl_idname = "fresing.update_cancel"
    bl_label = "Stop"

    def execute(self, context):
        _dl["stop"] = True
        return {"FINISHED"}


class FRESING_OT_update_later(bpy.types.Operator):
    """Hide the update notice until Fresing Render starts again. Help > Check for Fresing Render updates
    brings it back"""

    bl_idname = "fresing.update_later"
    bl_label = "Later"

    def execute(self, context):
        _ui["later"] = True
        _dl.pop("error", None)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_update_close_status(bpy.types.Operator):
    """Hide this message; it is only shown at the first start after an update. Help > Check for Fresing Render
    updates looks for newer versions"""

    bl_idname = "fresing.update_close_status"
    bl_label = "Close"

    def execute(self, context):
        _status.clear()
        if _check.get("state") in ("error", "off", "none"):
            _check["state"] = "idle"
        _redraw()
        return {"FINISHED"}


class FRESING_OT_update_release_page(bpy.types.Operator):
    """Open the release page on GitHub in your web browser: what's new in full, and the installer of that
    version (FresingRender-…-windows.zip) for a new PC"""

    bl_idname = "fresing.update_release_page"
    bl_label = "Release page"

    def execute(self, context):
        if _status:
            url = core.release_page(_status.get("to", "") if _status.get("ok") else "", index_url()[0])
        else:
            url = _check.get("release_page") or core.RELEASES_PAGE
        bpy.ops.wm.url_open(url=url)
        return {"FINISHED"}


class FRESING_OT_update_show_log(bpy.types.Operator):
    """Open the update log in a text editor: every step of the last updates, with the messages of Blender's
    installer. Useful when an update did not work"""

    bl_idname = "fresing.update_show_log"
    bl_label = "Show the update log"

    def execute(self, context):
        from . import files
        path = log_path()
        if not os.path.isfile(path):
            self.report({"WARNING"}, "There is no update log yet")
            return {"CANCELLED"}
        files.open_path(path)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# panel at the top of the Fresing tab (only when there is something to say)
# ---------------------------------------------------------------------------

def notice_kind() -> str:
    if _dl.get("active") or _dl.get("error"):
        return "download"
    if _status:
        return "status"
    state = _check.get("state")
    if state in ("available", "needs_installer") and not _ui["later"]:
        return state
    return ""


class FRESING_PT_update(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"              # task 0260: at the top of the left panel (ui_left.py)
    _fr_left = True
    bl_label = ""                         # the header says it all (draw_header)
    bl_order = 0                          # with 1 Import; registered before it, so it sits on top

    @classmethod
    def poll(cls, context):
        return bool(notice_kind())

    def draw_header(self, context):
        kind = notice_kind()
        if kind == "status" and _status.get("installing"):
            self.layout.label(text=f"Installing {_status.get('to', '')}…", icon="SORTTIME")
        elif kind == "status":
            ok = _status.get("ok")
            self.layout.label(text=f"Updated to {_status.get('to')}" if ok else "The update did not work",
                              icon="CHECKMARK" if ok else "ERROR")
        elif kind == "download":
            self.layout.label(text=f"Updating to {_dl.get('version', '')}", icon="IMPORT")
        else:
            self.layout.label(text=f"Update available: {_check.get('version', '')}", icon="IMPORT")

    def draw(self, context):
        from .ui import fold, primary, wrap
        layout = self.layout
        kind = notice_kind()
        if kind == "status" and _status.get("installing"):
            box = layout.box()
            box.alert = True
            wrap(box, context, _status.get("message", ""), inset=12)
            return
        if kind == "status":
            box = layout.box()
            box.alert = not _status.get("ok")
            if _status.get("ok"):
                text = (f"Fresing Render was updated from {_status.get('from') or 'the old version'} to "
                        f"{_status.get('to')}. Everything else is as it was.")
            else:
                text = _status.get("message", "") + f" You are still on {INSTALLED}; it works as before."
            wrap(box, context, text, inset=12)
            if _status.get("ok"):
                body = fold(layout, "fresing_update_new", "What's new", icon="INFO", closed=False)
                if body is not None:
                    if _status.get("changes"):
                        _draw_changes(body, context, _status["changes"])
                    else:
                        body.label(text="See the release page")
            row = layout.row(align=True)
            if not _status.get("ok"):
                row.operator("fresing.update_show_log", icon="TEXT")
            if _status.get("to"):
                row.operator("fresing.update_release_page", icon="URL")
            row.operator("fresing.update_close_status", icon="X")
            return
        if kind == "download":
            if _dl.get("active"):
                total = _dl.get("total") or 0
                done = _dl.get("done") or 0
                frac = done / total if total else 0.0
                layout.progress(factor=frac, text=f"Downloading… {done / 1e6:.0f} of {total / 1e6:.0f} MB")
                if _dl.get("save") == "DONT_SAVE":
                    after = "Then Fresing Render closes without saving and opens again with the new version."
                else:
                    after = "Then Fresing Render saves your project, closes and opens again with the new version."
                wrap(layout, context, after, icon="INFO")
                layout.operator("fresing.update_cancel", icon="CANCEL")
            else:
                wrap(layout, context, _dl.get("error", ""), icon="ERROR", alert=True)
                row = layout.row(align=True)
                row.operator("fresing.update_install", text="Try again", icon="FILE_REFRESH")
                row.operator("fresing.update_later", icon="TIME")
            return
        if kind == "needs_installer":
            wrap(layout, context, f"Version {_check.get('version')} needs a new installer (it comes with a "
                                  "newer Blender). Download it from the release page and run Install.bat.",
                 icon="INFO")
            row = layout.row(align=True)
            row.operator("fresing.update_release_page", icon="URL")
            row.operator("fresing.update_later", icon="TIME")
            return
        # an update is available
        size = _check.get("size") or 0
        line = f"You have {INSTALLED}. New: {_check.get('version')}"
        if _check.get("date"):
            line += f" ({_check['date']})"
        wrap(layout, context, line + ".")
        from . import project_lock
        if project_lock.warning():
            wrap(layout, context, f"This project is in use by {project_lock.warning()}: Save As first (a new "
                                  "name), then Update now.", icon="ERROR", alert=True)
        if _ui.get("note"):
            wrap(layout, context, _ui["note"], icon="ERROR", alert=True)
        primary(layout, "fresing.update_install", "Update now", "IMPORT")
        wrap(layout, context, "Closes the app, updates it and opens it again (download "
                              f"{size / 1e6:.0f} MB, about a minute). With unsaved changes it asks first: save "
                              "them or not.", icon="INFO")
        body = fold(layout, "fresing_update_whats_new", "What's new", icon="INFO")
        if body is not None:
            if _check.get("changes"):
                _draw_changes(body, context, _check["changes"])
            else:
                body.label(text="See the release page")
        row = layout.row(align=True)
        row.operator("fresing.update_release_page", icon="URL")
        row.operator("fresing.update_later", icon="TIME")


# ---------------------------------------------------------------------------
# Help menu: Check for Fresing Render updates (under the user guide entry of the app template)
# ---------------------------------------------------------------------------

def _draw_help(self, context):
    self.layout.operator("fresing.update_check", icon="FILE_REFRESH")
    self.layout.separator()


def _add_help_entry() -> None:
    menu = bpy.types.TOPBAR_MT_help
    menu.remove(_draw_help)
    try:
        funcs = menu._dyn_ui_initialize()
        at = next((i + 1 for i, f in enumerate(funcs) if getattr(f, "__name__", "") == "_draw_help_menu"), 0)
        funcs.insert(at, _draw_help)
    except (AttributeError, TypeError):
        menu.prepend(_draw_help)


CLASSES = (FRESING_OT_update_check, FRESING_OT_update_install, FRESING_OT_update_box_cancel, FRESING_OT_update_cancel,
           FRESING_OT_update_later,
           FRESING_OT_update_close_status, FRESING_OT_update_release_page, FRESING_OT_update_show_log,
           FRESING_PT_update)


def register():
    try:
        read_status()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: could not read the update status:", exc)
    try:
        refresh_template()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: could not update the app template:", exc)
    _add_help_entry()
    if not bpy.app.background and not bpy.app.timers.is_registered(_startup_check):
        bpy.app.timers.register(_startup_check, first_interval=CHECK_DELAY, persistent=True)


def unregister():
    bpy.types.TOPBAR_MT_help.remove(_draw_help)
    if bpy.app.timers.is_registered(_startup_check):
        bpy.app.timers.unregister(_startup_check)
    _dl["stop"] = True
