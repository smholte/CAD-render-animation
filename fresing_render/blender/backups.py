"""Automatic project backups (task 0246): the timer, the save, the question at the start.

Every ``TICK`` seconds a timer looks whether a backup is due: the interval (Preferences, 5 min) has gone by since the
last backup, save or open, and something changed since then (a scene update counted by ``_on_change``). It then saves a
copy of the open project with ``wm.save_as_mainfile(copy=True, relative_remap=False)``: the open project keeps its
path, title, "unsaved" mark and undo, and the copy keeps the project's relative paths (``core/backups`` docstring).

Blender runs the save handlers for a copy too: ``saving()`` is True meanwhile, and the app's own save handlers
(``handlers.py``, ``usage.py``, ``project_lock.py``) return at once – no usage count, no "in use" stamp, no cable-read
pause.

No backup: switched off, the Client view, a long job (``queue.busy_job``), a render or the render queue, the test
tour or the demo being made, an import, the animation playing, a pick in the 3D view, too little free space; it is
tried again ``core.RETRY_SECONDS`` later. Never in a background Blender, nor with ``FRESING_NO_BACKUPS``; under
simulated events (real-app tests) only with ``FRESING_BACKUP_TEST``.
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import date, datetime

import bpy
from bpy.app.handlers import persistent

from ..core import backups as core

TICK = 10.0                              # seconds between looks (a due backup waits at most this long)
NO_ENV = "FRESING_NO_BACKUPS"
TEST_ENV = "FRESING_BACKUP_TEST"
QUIET_AFTER = 1.0                        # seconds: the scene updates our own message causes are not "a change"

_S = {
    "saving": False,                     # a backup is being written: the save handlers keep out
    "since": 0.0,                        # the last backup, save or open (time.time())
    "changes": 0,                        # scene updates counted since the start
    "base": 0,                           # ... at the last backup, save or open
    "quiet_until": 0.0,
    "retry_at": 0.0,
    "said": set(),                       # once-per-session messages already given ("space", "fallback:<folder>")
    "last": "",                          # the last backup's path (tests, the PC check)
    "last_reason": "",                   # why the last look made no backup ("" = it made one or was not due)
    "asked": False,                      # the start question was dealt with in this session
    "start_wait": 0,
    "start_mark": None,
    "shown": "",                         # the backup the last start question was about (tests)
}


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

def settings() -> tuple:
    """(on, minutes, keep_last, days) from Fresing's preferences (defaults without them)."""
    from . import prefs
    p = prefs.get()
    if p is None:
        return True, core.DEFAULT_MINUTES, core.DEFAULT_KEEP, core.DEFAULT_DAYS
    return (bool(p.backups_on), core.clamp(p.backup_minutes, core.RANGE_MINUTES),
            core.clamp(p.backup_keep, core.RANGE_KEEP), core.clamp(p.backup_days, core.RANGE_DAYS))


def documents() -> str:
    from . import rule_sets
    return rule_sets.documents_dir()


def saving() -> bool:
    """Is a backup being written now? (The save handlers return at once while it is.)"""
    return _S["saving"]


def enabled_here() -> bool:
    if bpy.app.background or os.environ.get(NO_ENV):
        return False
    return not getattr(bpy.app, "use_event_simulate", False) or bool(os.environ.get(TEST_ENV))


# ---------------------------------------------------------------------------
# why not now
# ---------------------------------------------------------------------------

def _playing() -> bool:
    wm = bpy.context.window_manager
    for win in (wm.windows if wm else ()):
        if win.screen is not None and win.screen.is_animation_playing:
            return True
    return False


def wait_reason(scene) -> str:
    """Why a backup must wait now ("" = it may be made). Plain words for the message and the tests."""
    if scene is None or getattr(scene, "fresing", None) is None:
        return "no project"
    try:
        from . import workspaces
        if workspaces.locked(scene):
            return "Client view"
    except Exception:  # noqa: BLE001
        pass
    from . import queue
    busy = queue.busy_job(scene)
    if busy:
        return busy
    for job in ("RENDER", "OBJECT_BAKE", "COMPOSITE"):
        try:
            if bpy.app.is_job_running(job):
                return "a render" if job == "RENDER" else "a bake"
        except (TypeError, ValueError):
            pass
    try:
        if queue.is_running(scene):
            return "the render queue"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import ops_tour
        if ops_tour.progress_text():
            return "the Learning hub being made"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import ops_demo
        if ops_demo.running():
            return "the demo project being made"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import ops_import
        job = ops_import._ACTIVE_JOB
        if job is not None and not job.done:
            return "an import"
    except Exception:  # noqa: BLE001
        pass
    try:
        if _playing():
            return "the animation playing"
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import hover
        if hover.active():
            return "a pick in the 3D view"
    except Exception:  # noqa: BLE001
        pass
    return ""


def changed() -> bool:
    """Did anything change since the last backup, save or open?"""
    return _S["changes"] != _S["base"]


# ---------------------------------------------------------------------------
# folders
# ---------------------------------------------------------------------------

_FAILED: set = set()                     # folders that could not be written this session (no probe every 30 s)


def _writable(folder: str) -> bool:
    if folder in _FAILED:
        return False
    if not _try_write(folder):
        _FAILED.add(folder)
        return False
    return True


def _try_write(folder: str) -> bool:
    probe = os.path.join(folder, f".fresing-write-test-{os.getpid()}")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(probe, "wb") as f:
            f.write(b"0")
    except OSError:
        return False
    try:
        os.remove(probe)
    except OSError:
        pass                             # a share that lets us write but not delete: the folder is still usable
    return True


def other_user(project_path: str):
    """Someone else has this project open (the "in use" file of project_lock): their work, their backups."""
    if not project_path:
        return None
    try:
        from . import project_lock
        return project_lock.other_user(project_path)
    except Exception:  # noqa: BLE001
        return None


def _fits(folder: str, project_path: str) -> bool:
    """Does a backup's full path stay under Windows' path limit in this folder?"""
    name = core.backup_name(core.project_name(project_path), datetime(2000, 1, 1), seconds=True)
    return len(os.path.join(folder, name)) <= core.MAX_PATH


def target_folder(project_path: str) -> tuple[str, str]:
    """(folder, note): where this project's backups go now; a note when it is the fallback (said once)."""
    docs = documents()
    if not project_path:
        folder = core.unsaved_folder(docs)
        return (folder, "") if _writable(folder) else ("", f"Backups cannot be written to {folder}")
    usual = core.folder_next_to(project_path)
    fb = core.fallback_folder(docs, project_path)
    other = other_user(project_path)
    if other is None and _fits(usual, project_path) and _writable(usual):
        return usual, ""
    why = ("Someone else has this project open" if other is not None else
           "The folder next to the project cannot be written" if _fits(usual, project_path) else
           "The path next to the project is too long")
    if _writable(fb):
        return fb, f"{why}: backups go to {fb}"
    return "", f"Backups cannot be written next to the project nor to {fb}"


def project_size(project_path: str, folder: str) -> int:
    try:
        return os.path.getsize(project_path)
    except OSError:
        pass
    found = core.listing(folder, core.project_name(project_path)) if folder else []
    return found[0].size if found else 0


def _free(folder: str) -> int:
    try:
        return shutil.disk_usage(folder).free
    except OSError:
        return 1 << 62


def _say(scene, text: str) -> None:
    try:
        if scene is not None and getattr(scene, "fresing", None) is not None:
            _S["quiet_until"] = time.time() + QUIET_AFTER
            scene.fresing.last_message = text
    except Exception:  # noqa: BLE001
        pass
    print("Fresing Render (backups):", text)


def _once(scene, key: str, text: str) -> None:
    if key not in _S["said"]:
        _S["said"].add(key)
        _say(scene, text)


# ---------------------------------------------------------------------------
# the save
# ---------------------------------------------------------------------------

def write_copy(path: str) -> None:
    """Save the open project's working state to ``path`` without changing the open project."""
    _S["saving"] = True
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, relative_remap=False, check_existing=False)
    finally:
        _S["saving"] = False


def make(scene=None, force: bool = False, now: datetime | None = None, note: bool = True) -> str:
    """Make one backup of the open project now (``force``: also when nothing changed and not due; the waits for a
    long job etc. still hold). Returns the backup's path, or "" with the reason in ``_S["last_reason"]``."""
    scene = scene if scene is not None else bpy.context.scene
    _S["last_reason"] = ""
    if _S["saving"]:
        _S["last_reason"] = "a backup is being written"
        return ""
    on, _minutes, keep_last, days = settings()
    if not on and not force:
        _S["last_reason"] = "switched off"
        return ""
    why = wait_reason(scene)
    if why:
        _S["last_reason"] = why
        return ""
    project = bpy.data.filepath
    folder, fb_note = target_folder(project)
    if not folder:
        _S["last_reason"] = "no folder"
        _once(scene, "nofolder", fb_note)
        return ""
    if fb_note:
        _once(scene, "fallback:" + folder, fb_note)
    size = project_size(project, folder)
    if not core.enough_space(_free(folder), size):
        _S["last_reason"] = "not enough free space"
        _once(scene, "space", f"No backup: less than {core.size_text(int(core.FREE_FACTOR * size))} free on the disk "
                              f"of {folder}")
        return ""
    when = now or datetime.now()
    name = core.project_name(project)
    path = core.free_name(folder, name, when)
    changes_before = _S["changes"]
    t0 = time.perf_counter()
    try:
        write_copy(path)
    except Exception as exc:  # noqa: BLE001 - a failed backup must never stop the work
        fb = core.fallback_folder(documents(), project) if project else ""
        path = ""
        if fb and folder != fb and _writable(fb):            # e.g. a path Windows finds too long: the app folder
            _FAILED.add(folder)
            folder = fb
            path = core.free_name(folder, name, when)
            try:
                write_copy(path)
                _once(scene, "fallback:" + folder, f"Backups go to {folder} (next to the project: {exc})")
            except Exception as exc2:  # noqa: BLE001
                exc, path = exc2, ""
        if not path:
            _S["last_reason"] = f"could not save: {exc}"
            _once(scene, "error", f"A backup could not be saved: {exc}")
            return ""
    _S["seconds"] = time.perf_counter() - t0
    _S["since"], _S["base"], _S["last"] = time.time(), changes_before, path
    core.clean(folder, name, keep_last, days, when.date())
    if note:
        _say(scene, f"Backup saved {when.strftime('%H:%M')}")
    return path


def tick() -> str:
    """One look of the timer: a backup when due. Returns the path made or ""."""
    on, minutes, _k, _d = settings()
    if not on or not enabled_here():
        return ""
    now = time.time()
    if now < _S["retry_at"]:
        return ""
    if not core.due(now, _S["since"], minutes) or not changed():
        return ""
    path = make()
    if not path:
        _S["retry_at"] = now + core.RETRY_SECONDS
    return path


def _timer():
    try:
        tick()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (backups):", exc)
    return TICK


# ---------------------------------------------------------------------------
# what the project's backups are
# ---------------------------------------------------------------------------

def project_backups(project_path: str | None = None) -> list:
    path = bpy.data.filepath if project_path is None else project_path
    return core.all_backups(path, documents())


def saved_mtime(project_path: str) -> float | None:
    try:
        return os.path.getmtime(project_path) if project_path else None
    except OSError:
        return None


def state_path() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), core.STATE_FILE)


def _replace(src: str, dst: str) -> None:
    """Copy ``src`` over ``dst`` through a temporary file next to it; a name Windows still holds for a moment (a virus
    scan) is tried again for up to 3 s."""
    tmp = dst + ".fresing-restore"
    try:
        shutil.copyfile(src, tmp)
        for i in range(31):
            try:
                os.replace(tmp, dst)
                break
            except PermissionError:
                if i == 30:
                    raise
                time.sleep(0.1)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    # the restored project is the newest: its backups are not "newer" any more – also when the backups' times come
    # from a file server's clock ahead of this PC's, or a disk that stores times in 2 s steps
    newest = max((b.mtime for b in project_backups(dst)), default=0.0)
    t = max(time.time(), newest + core.NEWER_MARGIN + 1.0)
    os.utime(dst, (t, t))


def restore(backup_path: str) -> str:
    """Put a backup back. A saved project: the open working state is first kept as a backup itself, then the backup
    replaces the project file and the project opens. An unsaved project: the backup is copied to
    ``Documents\\Fresing Render\\Recovered projects`` and opens from there. Returns the file that opened."""
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(backup_path)
    project = bpy.data.filepath
    if project and other_user(project) is not None:
        raise RuntimeError("someone else has this project open: save your work under another name (File > Save As)")
    if project:
        folder = os.path.dirname(backup_path)
        name = core.project_name(project)
        keep = core.free_name(folder, name, datetime.now())
        write_copy(keep)                 # the work as it is now, in case the backup was the wrong one
        _replace(backup_path, project)
        target = project
    else:
        out = core.recovered_folder(documents())
        os.makedirs(out, exist_ok=True)
        stamp = datetime.fromtimestamp(os.path.getmtime(backup_path)).strftime("%Y-%m-%d %H-%M")
        target = os.path.join(out, f"Recovered project {stamp}.blend")
        n = 2
        while os.path.exists(target):
            target = os.path.join(out, f"Recovered project {stamp} ({n}).blend")
            n += 1
        shutil.copyfile(backup_path, target)
        try:
            core.mark_handled(state_path(), [backup_path])
        except OSError:
            pass
    bpy.ops.wm.open_mainfile(filepath=target)
    return target


# ---------------------------------------------------------------------------
# the question at the start
# ---------------------------------------------------------------------------

def offer() -> tuple:
    """(backup, saved_mtime) to ask about now, or (None, None). A saved project: its newest backup when it is newer
    than the file. No project: an unsaved project's backup from the last 24 h not dealt with yet."""
    project = bpy.data.filepath
    found = project_backups(project)
    if project:
        if other_user(project) is not None:          # their backups are their unsaved work: never offered here
            return None, None
        mt = saved_mtime(project)
        return (core.newest_newer(found, mt), mt) if mt is not None else (None, None)
    b = core.unsaved_offer(found, time.time(), core.load_state(state_path())["handled"])
    return b, None


def _welcome_open() -> bool:
    """The welcome or What's new window of this start may still be open: wait for it (``welcome.py`` is not
    changed). Closed when its answer was written to the start file, or once the user works in the project, or after
    3 minutes."""
    try:
        from . import welcome
    except Exception:  # noqa: BLE001
        return False
    run = welcome._RUN
    if not run.get("done"):
        return True
    if not run.get("shows"):
        return False
    path = welcome.state_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    if _S["start_mark"] is None:
        _S["start_mark"] = (mtime, _S["changes"], time.time())
        return True
    m0, c0, t0 = _S["start_mark"]
    return not (mtime > m0 or _S["changes"] != c0 or time.time() - t0 > 180)


def ask(force: bool = False) -> bool:
    """Show the start question when there is something to ask. Returns True when it was shown."""
    b, _mt = offer()
    if b is None:
        return False
    scene = bpy.context.scene
    try:
        from . import workspaces
        if scene is not None and workspaces.locked(scene) and not force:
            return False
    except Exception:  # noqa: BLE001
        pass
    from . import welcome
    kw = welcome._window_override()
    if kw is None:
        return False
    try:
        with bpy.context.temp_override(**kw):
            bpy.ops.fresing.backup_offer("INVOKE_DEFAULT", path=b.path)
        _S["shown"] = b.path
        return True
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (backups): could not ask:", exc)
        return False


def _start_timer():
    """After a project opened (and once at the start for unsaved work): ask, when the welcome is out of the way."""
    try:
        if _S["asked"] or not enabled_here():
            return None
        wm = bpy.context.window_manager
        if wm is None or not wm.windows:
            return 1.0
        if _welcome_open():
            _S["start_wait"] += 1
            return 1.0 if _S["start_wait"] < 600 else None
        _S["asked"] = True
        ask()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (backups):", exc)
    return None


def _schedule_question(first: float = 2.0) -> None:
    _S["asked"] = False
    _S["start_wait"] = 0
    if bpy.app.timers.is_registered(_start_timer):
        bpy.app.timers.unregister(_start_timer)
    if enabled_here():
        bpy.app.timers.register(_start_timer, first_interval=first)


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def restart_clock() -> None:
    _S["since"], _S["base"], _S["retry_at"] = time.time(), _S["changes"], 0.0


@persistent
def _on_change(_scene=None, _depsgraph=None):
    if not _S["saving"] and time.time() >= _S["quiet_until"]:
        _S["changes"] += 1


@persistent
def _on_save(_dummy=None):
    if _S["saving"]:
        return
    restart_clock()                      # a manual save restarts the 5 minutes
    try:                                 # an unsaved project saved as a project: its unsaved backups are dealt with
        if _S.get("was_unsaved") and bpy.data.filepath:
            folder = core.unsaved_folder(documents())
            mine = [b.path for b in core.listing(folder, core.UNSAVED_NAME) if b.mtime >= _S.get("opened_at", 0)]
            if mine:
                core.mark_handled(state_path(), mine)
    except Exception:  # noqa: BLE001
        pass
    _S["was_unsaved"] = not bpy.data.filepath


@persistent
def _on_load(_dummy=None):
    restart_clock()
    _S["opened_at"] = time.time()
    _S["was_unsaved"] = not bpy.data.filepath
    _S["start_mark"] = None
    if bpy.data.filepath:
        _schedule_question()


_HANDLERS = (("depsgraph_update_post", _on_change), ("save_post", _on_save), ("load_post", _on_load))


def register() -> None:
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)
    restart_clock()
    _S["opened_at"] = time.time()
    _S["was_unsaved"] = True
    if not bpy.app.background and not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=TICK, persistent=True)
    _schedule_question(first=3.0)        # unsaved work of a session that stopped (or the project of the command line)


def unregister() -> None:
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
    for fn in (_timer, _start_timer):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)


def today() -> date:
    return date.today()
