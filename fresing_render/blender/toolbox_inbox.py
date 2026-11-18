"""The Toolbox inbox in the app (task 0217): a house sent from House Planner arrives by itself, the owner presses
**Bake now** once, and the bake package goes back to House Planner's inbox by itself.

``core/toolbox.py`` does the folder (no Blender); this module drives it:

* a timer (``bpy.app.timers``, persistent across file loads) looks at the inbox every 2 seconds – every second while a
  job of it runs –, only in a copy of the app with a window (not in the render queue's, the PC check's or any other
  background Blender). ``alive.json`` at least every 10 s while Blender is free; deleted on closing (``atexit``) when
  this copy wrote the newest one. Nothing of it ever raises out of the timer.
* ``bake-house`` (owner's answer A, 18 Nov 2026): Bake now makes **a scene of its own** in the open project ("House –
  <title>"), shows it in the window, imports the house there (``house_import.import_scene`` into a temp folder) and
  starts the existing ``fresing.house_bake`` (its progress and Cancel in the House panel). When the bake ends
  (``ops_house.ENDED``) the package goes back as a reply job, the status becomes ``done``, the window shows the
  owner's scene again and the house scene is removed – the world and floor rebuilt from the owner's own settings (they
  are shared by name between scenes). The owner's project is as it was.
* ``import-step``: Import now runs the same STEP import as File > Import, of a copy of the file kept in
  ``Documents/Fresing Render/From the Toolbox`` (the job's own file is deleted once the job is final).
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import time
from pathlib import Path

import bpy

from ..core import toolbox as tb

TICK = 2.0                       # s between two looks (FORMAT.md 6.3)
TICK_RUNNING = 1.0               # s while a job runs: progress and cancel.json
_S: dict = {"inbox": None, "timer": False, "atexit": False, "bake": None, "import": None, "options": {}}


# ---------------------------------------------------------------------------
# set-up
# ---------------------------------------------------------------------------

def app_version() -> str:
    from .. import __version__
    return str(__version__)


def program() -> str:
    """What the Desktop shortcut starts ("Fresing Render.exe", else Blender's launcher; tasks 0177 / 0212)."""
    try:
        from .. import winexe
        return winexe.app_exe(bpy.app.binary_path) or ""
    except Exception:  # noqa: BLE001
        return bpy.app.binary_path or ""


def documents() -> Path:
    """The user's Documents (Windows asks the shell: OneDrive may have moved it; independent review, task 0217)."""
    try:
        from . import rule_sets
        return Path(rule_sets.documents_dir())
    except Exception:  # noqa: BLE001
        return Path.home() / "Documents"


def keep_dir() -> Path:
    return documents() / "Fresing Render" / "House bakes"


def wanted() -> bool:
    """Only a copy with a window watches the inbox (review 4b): the render queue, the PC check and every other
    background Blender leave it alone; FRESING_NO_TOOLBOX switches it off (tests)."""
    return not bpy.app.background and not os.environ.get("FRESING_NO_TOOLBOX")


def inbox() -> tb.Inbox | None:
    return _S["inbox"]


def use_folder(root, keep: Path | None = None, *, timer: bool | None = None, home_after: bool = False,
               **options) -> tb.Inbox:
    """Watch the Toolbox folder ``root`` from now on (the app at start: ``tb.home()``; the test tour and tests a
    folder of their own). ``options``: kwargs of the bake (``samples``, ``photo_samples``, ``quick``: tests bake
    small). ``home_after``: once its jobs are over, the app watches the real Toolbox folder again (the test tour)."""
    old = _S["inbox"]
    if old is not None and Path(old.root) != Path(root):
        old.remove_alive()
    ib = tb.Inbox(Path(root), app_version(), program(), ["--app-template", "fresing_render"],
                  keep_dir=keep or keep_dir())
    _S["inbox"] = ib
    _S["options"] = dict(options)
    _S["home_after"] = home_after
    ib.start()
    if timer if timer is not None else not bpy.app.background:
        _start_timer()
    return ib


def _start_timer() -> None:
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)
    _S["timer"] = True


def register() -> None:
    from . import ops_house
    if _bake_ended not in ops_house.ENDED:
        ops_house.ENDED.append(_bake_ended)
    if not wanted():
        return
    try:
        use_folder(tb.home())
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render (Toolbox):", exc)
    if not _S["atexit"]:
        atexit.register(closing)
        _S["atexit"] = True


def unregister() -> None:
    from . import ops_house
    if _bake_ended in ops_house.ENDED:
        ops_house.ENDED.remove(_bake_ended)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    closing()
    _S["inbox"] = None


def closing() -> None:
    """Blender closes: alive.json goes when this copy wrote the newest one; a job waiting stays waiting (the next
    start asks again), a running one is ended by the next start (FORMAT.md 6.3)."""
    ib = _S["inbox"]
    if ib is not None:
        try:
            ib.remove_alive()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# the timer
# ---------------------------------------------------------------------------

def busy() -> str:
    """The long job that has the PC or the project now ('' = free): a house bake, web export, clash check, re-bake,
    a STEP import, the render queue."""
    from . import ops_import, queue
    for sc in bpy.data.scenes:
        try:
            b = queue.busy_job(sc)
            if b:
                return b
            if queue.is_running(sc):
                return "the render queue"
        except Exception:  # noqa: BLE001
            continue
    job = getattr(ops_import, "_ACTIVE_JOB", None)
    if job is not None and not job.done:
        return "a STEP import"
    return ""


def _tick():
    ib = _S["inbox"]
    if ib is None:
        return None
    try:
        events = look()
        for e in events:
            report(e)
        if events:
            redraw()
    except Exception as exc:  # noqa: BLE001 - the timer never stops for a fault
        print("Fresing Render (Toolbox):", exc)
    return TICK_RUNNING if (_S["bake"] or _S["import"]) else TICK


def look() -> list[str]:
    """One look (the timer's work; tests call it directly)."""
    ib = _S["inbox"]
    if ib is None:
        return []
    events = ib.look(busy())
    _follow_bake()
    _follow_import()
    _maybe_home()
    return events


def _maybe_home() -> None:
    """A folder of the test tour: once nothing of it waits or runs, back to the real Toolbox folder."""
    ib = _S["inbox"]
    if not _S.get("home_after") or ib is None or ib.jobs or _S["bake"] or _S["import"]:
        return
    _S["home_after"] = False
    if wanted():
        try:
            use_folder(tb.home())
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render (Toolbox):", exc)


def report(text: str) -> None:
    """A line in Blender's status bar (the timer has no operator of its own)."""
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm and wm.windows else None
    if win is None:
        return
    try:
        with bpy.context.temp_override(window=win):
            bpy.ops.fresing.toolbox_report(text=text[:250])
    except Exception:  # noqa: BLE001
        pass


def redraw() -> None:
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            area.tag_redraw()


def waiting() -> list[tb.Job]:
    ib = _S["inbox"]
    return [j for j in ib.jobs.values() if j.state == "waiting"] if ib else []


def running() -> tb.Job | None:
    ib = _S["inbox"]
    jid = (_S["bake"] or _S["import"] or {}).get("job")
    return ib.jobs.get(jid) if ib and jid else None


LAST_SHOWN = 600.0               # s the panel shows how the last job ended


def to_show() -> bool:
    """Something of the Toolbox for the House panel: a job waiting or running, or one that just ended."""
    return bool(waiting() or running() is not None or last_result())


def fraction() -> float:
    from . import ops_house
    run = _S["bake"]
    if run and run["scene"] in bpy.data.scenes:
        return float(ops_house.runtime(bpy.data.scenes[run["scene"]]).get("progress", 0.0))
    imp = _S["import"]
    if imp and imp.get("job_obj") is not None:
        return float(getattr(imp["job_obj"], "pct", 0.0)) / 100.0
    return 0.0


def last_result() -> str:
    last = _S.get("last")
    if last and time.time() - last[1] < LAST_SHOWN:
        return last[0]
    return ""


def cancel() -> bool:
    """Cancel in the Toolbox lines: the house bake stops as its own Cancel does."""
    from . import ops_house
    run = _S["bake"]
    if run and run["scene"] in bpy.data.scenes:
        ops_house.runtime(bpy.data.scenes[run["scene"]])["cancel"] = True
        return True
    return False


def last_note() -> str:
    ib = _S["inbox"]
    if ib is None:
        return ""
    return ib.problem or (ib.notes[-1] if ib.notes else "")


# ---------------------------------------------------------------------------
# Bake now
# ---------------------------------------------------------------------------

def start(context, jid: str) -> str:
    """The owner pressed Bake now / Import now. Returns '' or why it did not start (a sentence)."""
    ib = _S["inbox"]
    if ib is None:
        return "The Toolbox folder is not in use"
    j = ib.jobs.get(jid)
    if j is None:
        return "This job is no longer there"
    if _S["bake"] or _S["import"]:
        return "Another job from the Toolbox is running: wait for it"
    b = busy()
    if b:
        return f"Fresing Render is busy ({b}): try again when it is done"
    if j.action == "bake-house":
        return _start_bake(context, ib, j)
    if j.action == "import-step":
        return _start_import(context, ib, j)
    return f"Fresing Render cannot do {j.action}"


def not_now(jid: str) -> None:
    ib = _S["inbox"]
    if ib is not None and jid in ib.jobs and ib.jobs[jid].state == "waiting":
        ib.not_now(jid)


def _window(context):
    if bpy.app.background:                  # (Blender as a module has a window that is never drawn: work at once)
        return None
    win = getattr(context, "window", None)
    if win is None:
        wm = bpy.context.window_manager
        win = wm.windows[0] if wm and wm.windows and not bpy.app.background else None
    return win


def _start_bake(context, ib: tb.Inbox, j: tb.Job) -> str:
    from . import house_import
    why = ib.begin(j.id, "Importing the house")
    if why:
        return why
    orig = context.scene
    win = _window(context)
    title = j.title
    name = tb.one_line(f"House – {title}", 60)
    scene = bpy.data.scenes.new(name)
    temp = tempfile.mkdtemp(prefix="fr_toolbox_")
    run = {"job": j.id, "scene": scene.name, "orig": orig.name, "orig_world": orig.world.name if orig.world else "",
           "orig_objects": {ob.name for ob in orig.objects},
           "temp": temp, "window": win, "path": os.path.join(temp, house_import.safe_name(title) + ".hpbake"),
           "started": time.time()}
    _S["bake"] = run
    try:
        from . import workspaces
        workspaces.use_all(scene)            # a scene of the app's own: every function, never locked
    except Exception:  # noqa: BLE001
        pass
    try:
        src = j.files[0][2]
        if win is not None:
            win.scene = scene                # the owner sees the house while it bakes; the House panel shows Cancel
        vl = scene.view_layers[0]
        over = {"window": win} if win else {}
        with bpy.context.temp_override(scene=scene, view_layer=vl, **over):
            house_import.import_scene(scene, str(src), folder=os.path.join(temp, "house"))
        ib.progress(j.id, 0.0, "Baking")
        opts = {k: v for k, v in _S["options"].items() if k in ("samples", "photo_samples", "quick")}
        if win is not None:      # as a button does: modal, its progress and Cancel in the House panel
            with bpy.context.temp_override(window=win, scene=scene, view_layer=vl):
                res = bpy.ops.fresing.house_bake("EXEC_DEFAULT", filepath=run["path"], **opts)
            if res == {"CANCELLED"}:              # (it said why through ENDED: then this does nothing)
                _finish_bake(run, "failed", "The bake could not start")
        else:                    # Blender as a module (tests): at once, the operator's own steps
            from . import house_bake, ops_house
            o = {"samples": int(opts.get("samples", 0)), "photo_samples": int(opts.get("photo_samples", 0)),
                 "quick": bool(opts.get("quick"))}
            with bpy.context.temp_override(scene=scene, view_layer=vl):   # settings' updates reach this scene
                job = house_bake.HouseBake(scene, run["path"], **ops_house.bake_options(scene, **o))
                try:
                    ops_house.run_at_once(job)
                except RuntimeError:
                    pass                          # (told through ENDED)
    except Exception as exc:  # noqa: BLE001 - a house that cannot be imported: the job fails, the project stays
        text = str(exc)
        _finish_bake(run, "failed", f"The house could not be imported: {text}")
        if win is None:
            tidy_bake(run)
        return tb.one_line(text)
    if run.get("finished") and win is None:       # without a window the bake ran at once: tidy outside its context
        tidy_bake(run)
    return ""


def _follow_bake() -> None:
    run = _S["bake"]
    ib = _S["inbox"]
    if not run or ib is None:
        return
    from . import ops_house
    j = ib.jobs.get(run["job"])
    rt = ops_house.runtime(bpy.data.scenes.get(run["scene"])) if run["scene"] in bpy.data.scenes else {}
    if j is not None and j.cancel_asked and rt.get("running"):
        rt["cancel"] = True                                  # cancel.json: stop as Cancel does
        run["by_sender"] = True
    if rt.get("running"):
        ib.progress(run["job"], float(rt.get("progress", 0.0)) * 0.98, rt.get("text", "Baking"))


def _bake_ended(scene, outcome: str, info, filepath: str) -> None:
    """``ops_house.ENDED``: a house bake ended. Only the bake this module started is answered."""
    run = _S["bake"]
    if not run or os.path.abspath(filepath or "") != os.path.abspath(run["path"]):
        return
    if outcome == "done":
        moments = int((info or {}).get("moments", 0) or 0)
        from ..core import words
        text = f"Baked {words.plural(moments, 'moment')}" if moments else "Baked"
        _finish_bake(run, "done", text)
    elif outcome == "cancelled":
        by = run.get("by_sender")
        ib = _S["inbox"]
        j = ib.jobs.get(run["job"]) if ib else None
        who = (j.sender if j else "") or "the sender"
        _finish_bake(run, "cancelled", f"Cancelled by {who}; nothing was sent" if by else
                     "Cancelled in Fresing Render; nothing was sent")
    else:
        _finish_bake(run, "failed", str(info or "The bake failed"))


def _finish_bake(run: dict, outcome: str, text: str) -> None:
    """The reply (first) and the status (second), then the owner's scene back and the house scene gone – the tidying
    a moment later, outside the bake operator that is just ending."""
    ib = _S["inbox"]
    if run.get("finished"):
        return
    run["finished"] = True
    try:
        if ib is not None:
            if outcome == "done" and os.path.isfile(run["path"]):
                _rid, text = ib.reply(run["job"], [Path(run["path"])], text)
            else:
                ib.finish(run["job"], outcome if outcome != "done" else "failed",
                          text if outcome != "done" else "The bake wrote no package", code="error"
                          if outcome in ("failed", "done") else None)
            run["text"] = text
    finally:
        if run.get("window") is not None:          # (without a window _start_bake tidies once the bake call is back)
            bpy.app.timers.register(lambda: tidy_bake(run), first_interval=0.2)


def tidy_bake(run: dict | None = None):
    """The owner's scene back in the window, the house scene removed, the world and floor rebuilt from the owner's own
    settings, the temp folder deleted. Returns None (a timer that runs once)."""
    run = run or _S["bake"]
    if not run:
        return None
    try:
        orig = bpy.data.scenes.get(run["orig"])
        scene = bpy.data.scenes.get(run["scene"])
        win = run.get("window")
        try:
            if win is not None and orig is not None and win.scene == scene:
                win.scene = orig
        except ReferenceError:
            pass
        if scene is not None:
            remove_scene(scene, keep=orig)
        if orig is not None:
            put_back_world(orig, run.get("orig_world", ""))
            take_out_helpers(orig, run.get("orig_objects", set()))
        shutil.rmtree(run["temp"], ignore_errors=True)
        line = ("Sent back to House Planner" if (run.get("text") or "").endswith("House Planner")
                else (run.get("text") or "The house job ended"))
        _S["last"] = (line, time.time())
        report(line)
    finally:
        if _S["bake"] is run:
            _S["bake"] = None
        redraw()
    return None


def remove_scene(scene, keep=None) -> None:
    """Remove a scene made for a job with what only it uses (objects, their meshes and materials, its collections).
    An object or collection the owner's scenes use too is left."""
    others = [s for s in bpy.data.scenes if s != scene]
    obs = [ob for ob in scene.objects if all(s == scene for s in ob.users_scene)]
    datas = {ob.data for ob in obs if ob.data is not None}
    cols = [c for c in scene.collection.children_recursive
            if not any(c.name in o.collection.children_recursive or c == o.collection for o in others)]
    if obs:
        bpy.data.batch_remove(obs)
    for c in cols:
        try:
            bpy.data.collections.remove(c)
        except ReferenceError:
            pass
    mats = set()
    for d in datas:
        try:
            if getattr(d, "users", 1) == 0:
                mats.update(m for m in getattr(d, "materials", []) if m is not None)
                bpy.data.batch_remove([d])
        except ReferenceError:
            pass
    for m in mats:
        try:
            if m.users == 0:
                bpy.data.materials.remove(m)
        except ReferenceError:
            pass
    bpy.data.scenes.remove(scene)


def put_back_world(orig, world_name: str) -> None:
    """The world and floor are the app's, shared by name between scenes: the house scene's sky and weather changed
    them. Rebuilt from the owner's scene's own settings when it used the app's world; else its own world (or none)
    put back."""
    from . import world
    try:
        if world_name == world.WORLD_NAME:
            world.apply(orig, orig.fresing)
        else:
            orig.world = bpy.data.worlds.get(world_name) if world_name else None
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (Toolbox): the world could not be rebuilt:", exc)


def take_out_helpers(orig, before: set) -> None:
    """The app's helpers (floor, weather) that the house's settings put into the owner's scene while it baked."""
    for ob in [o for o in orig.objects if o.name not in before]:
        if not (ob.get("fr_helper") or ob.get("fr_weather") is not None or ob.get("fr_house")):
            continue
        cols = [orig.collection] + list(orig.collection.children_recursive)
        for col in [c for c in ob.users_collection if c in cols]:
            col.objects.unlink(ob)
        if ob.users == 0:
            data = ob.data
            bpy.data.objects.remove(ob)
            if data is not None and data.users == 0:
                try:
                    bpy.data.batch_remove([data])
                except Exception:  # noqa: BLE001
                    pass


# ---------------------------------------------------------------------------
# Import now
# ---------------------------------------------------------------------------

def import_dir() -> Path:
    return documents() / "Fresing Render" / "From the Toolbox"


def _start_import(context, ib: tb.Inbox, j: tb.Job) -> str:
    why = ib.begin(j.id, "Importing the STEP file")
    if why:
        return why
    name, _kind, src = j.files[0]
    try:
        d = import_dir()
        d.mkdir(parents=True, exist_ok=True)
        stem, ext = os.path.splitext(name)
        dest, n = d / name, 2
        while dest.exists():
            dest, n = d / f"{stem} ({n}){ext}", n + 1
        shutil.copyfile(src, dest)
    except OSError as exc:
        ib.finish(j.id, "failed", f"The file could not be copied out of the Toolbox folder: {exc}", code="error")
        return str(exc)
    from . import ops_import
    _S["import"] = {"job": j.id, "path": str(dest), "before": getattr(ops_import, "_ACTIVE_JOB", None)}
    try:
        res = bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=str(dest))
    except Exception as exc:  # noqa: BLE001
        res = {"CANCELLED"}
        _S["import"]["error"] = str(exc)
    run = _S["import"]
    job = getattr(ops_import, "_ACTIVE_JOB", None)
    if "RUNNING_MODAL" in res and job is not None and job is not run["before"]:
        run["job_obj"] = job                                      # read in the background: followed by the timer
        return ""
    msg = run.get("error") or (context.scene.fresing.last_message if res == {"CANCELLED"} else "")
    _S["import"] = None
    if res == {"FINISHED"}:
        ib.finish(j.id, "done", f"Imported {os.path.basename(str(dest))}")
        return ""
    ib.finish(j.id, "failed", msg or "The import failed", code="error")
    return msg or "The import failed"


def _follow_import() -> None:
    run = _S["import"]
    ib = _S["inbox"]
    if not run or ib is None or "job_obj" not in run:
        return
    job = run["job_obj"]
    ib.progress(run["job"], float(getattr(job, "pct", 0.0)) / 100.0, f"Importing: {getattr(job, 'message', '')}")
    if not job.done:
        return
    _S["import"] = None
    if job.error == "Cancelled":
        ib.finish(run["job"], "cancelled", "Cancelled in Fresing Render (Esc)")
    elif job.error:
        ib.finish(run["job"], "failed", f"Import failed: {job.error}", code="error")
    else:
        ib.finish(run["job"], "done", f"Imported {os.path.basename(run['path'])}")


__all__ = ["register", "unregister", "use_folder", "inbox", "look", "start", "not_now", "waiting", "running"]
