"""Real-app test, automatic backups (task 0246): the app's own timer makes a backup once the interval has gone by and
something changed (an Empty added like a button would); the open project keeps its path and its "unsaved" mark, Ctrl+Z
still takes the Empty away; the save handlers (queue, usage, "in use" file) keep out; an idle app makes no file; none
in the Client view nor while a clash check runs; Restore keeps the work as a backup and opens the chosen one; the start
question shows for a saved project whose backup is newer and, at the start, for unsaved work (Esc = turned down).

Install the extension and the app template first (see ui_test_app.py), then run (FRESING_BACKUP_TEST: backups and
the start question work although events are simulated):
    FRESING_BACKUP_TEST=1 xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_backups.py
ui_test_backups.log goes to $UITEST_OUT (default ~/fresing_ui_test_backups).
"""

import os
import shutil
import subprocess
import tempfile
import time
import traceback

import bpy

os.environ.setdefault("FRESING_BACKUP_TEST", "1")
OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_backups"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_backups.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_backups é ")
DOCS = os.path.join(TMP, "Documents")
STATE = {}
CALLS = []
TICK_WAIT = 12.0                          # the timer looks every 10 s


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def win0():
    return bpy.context.window_manager.windows[0]


def override():
    win = win0()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def esc():
    win = win0()
    win.event_simulate(type="ESC", value="PRESS")
    win.event_simulate(type="ESC", value="RELEASE")


def files():
    folder = os.path.join(os.path.dirname(STATE["project"]), "Backups")
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def due_now():
    b = mod("blender.backups")
    b._S["since"] = time.time() - 3600
    b._S["retry_at"] = 0.0


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_setup():
    esc()                                                    # the splash
    b = mod("blender.backups")
    b.documents = lambda: DOCS
    b.state_path = lambda: os.path.join(TMP, "config", "fresing_backups.json")
    p = mod("blender.prefs").get()
    check("the four settings are in Fresing's preferences",
          p is not None and (p.backups_on, p.backup_minutes, p.backup_keep, p.backup_days) == (True, 5, 5, 7),
          str(p and (p.backups_on, p.backup_minutes, p.backup_keep, p.backup_days)))
    q, u, lk = mod("blender.queue"), mod("blender.usage"), mod("blender.project_lock")
    for m, name in ((q, "project_saved"), (u, "save"), (lk, "write")):
        real = getattr(m, name)

        def wrapped(*a, _real=real, _n=name, **k):
            CALLS.append(_n)
            return _real(*a, **k)
        setattr(m, name, wrapped)
    STATE["project"] = os.path.join(TMP, "Projekt é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=STATE["project"])
    CALLS.clear()
    return 1.0


@step
def s_change():
    STATE["lock"] = STATE["project"] + ".inuse"
    STATE["lock_mtime"] = os.path.getmtime(STATE["lock"]) if os.path.isfile(STATE["lock"]) else None
    n = len(bpy.data.objects)
    with override():
        bpy.ops.object.empty_add("EXEC_DEFAULT", True)
    check("an Empty was added", len(bpy.data.objects) == n + 1)
    STATE["n"] = n
    STATE["dirty"] = bpy.data.is_dirty
    due_now()
    return TICK_WAIT


@step
def s_backup_made():
    made = files()
    check("the timer made one backup in Backups next to the project", len(made) == 1, str(made))
    check("its name is '<project> backup <date> <time>.blend'",
          made and made[0].startswith("Projekt é backup ") and made[0].endswith(".blend"), str(made))
    check("the open project keeps its path", bpy.data.filepath == STATE["project"], bpy.data.filepath)
    check("the open project keeps its unsaved mark", bpy.data.is_dirty and STATE["dirty"], str(bpy.data.is_dirty))
    check("the save handlers kept out (queue, usage, 'in use' file)", CALLS == [], str(CALLS))
    lm = os.path.getmtime(STATE["lock"]) if os.path.isfile(STATE["lock"]) else None
    check("the 'in use' file was not touched", lm == STATE["lock_mtime"], f"{STATE['lock_mtime']} -> {lm}")
    check("the side panel says 'Backup saved'", bpy.context.scene.fresing.last_message.startswith("Backup saved"),
          bpy.context.scene.fresing.last_message)
    with override():
        bpy.ops.ed.undo()
    check("Ctrl+Z still takes the Empty away after the backup", len(bpy.data.objects) == STATE["n"],
          str(len(bpy.data.objects)))
    with override():
        bpy.ops.ed.redo()
    check("redo brings it back", len(bpy.data.objects) == STATE["n"] + 1)
    return 1.0


@step
def s_idle():
    mod("blender.backups").restart_clock()
    STATE["files"] = files()
    return 3.0                                              # whatever the app does by itself meanwhile


@step
def s_idle_due():
    due_now()
    return TICK_WAIT


@step
def s_idle_check():
    b = mod("blender.backups")
    check("an idle app makes no new backup", files() == STATE["files"], f"{files()} changes {b._S['changes']} "
                                                                       f"base {b._S['base']}")
    ws = mod("blender.workspaces")
    ws.switch(bpy.context.scene, "Client view")
    b._S["changes"] += 1
    due_now()
    return TICK_WAIT


@step
def s_client_check():
    b = mod("blender.backups")
    check("no backup in the Client view", files() == STATE["files"] and b._S["last_reason"] == "Client view",
          f"{b._S['last_reason']!r} {len(files())}")
    with override():
        check("Restore a backup… is greyed in the Client view", not bpy.ops.fresing.backups_window.poll())
    ws = mod("blender.workspaces")
    ws.switch(bpy.context.scene, "Full access")
    ws.switch(bpy.context.scene, "All functions")
    clash = mod("blender.clash")
    STATE["runtime"] = clash.runtime
    clash.runtime = lambda scene: {"running": True}
    b._S["changes"] += 1
    due_now()
    return TICK_WAIT


@step
def s_busy_check():
    b = mod("blender.backups")
    check("no backup while a clash check runs", files() == STATE["files"] and b._S["last_reason"] == "Clash check",
          f"{b._S['last_reason']!r}")
    mod("blender.clash").runtime = STATE["runtime"]
    b._S["changes"] += 1
    due_now()
    return TICK_WAIT


@step
def s_after_busy():
    check("tried again once the job is done", len(files()) == len(STATE["files"]) + 1, str(files()))
    win = win0()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=win.width // 2, y=win.height // 2)
    with override():
        bpy.ops.fresing.backups_window("INVOKE_DEFAULT")
    return 1.5


@step
def s_window_shot():
    shot("restore_window")                                 # the guide's picture (docs/img/backups_window.png)
    esc()
    return 1.0


@step
def s_restore():
    STATE["first"] = os.path.join(os.path.dirname(STATE["project"]), "Backups", files()[0])
    bpy.context.scene["mark"] = "work now"
    STATE["before_restore"] = files()
    with override():
        r = bpy.ops.fresing.backup_restore("EXEC_DEFAULT", path=STATE["first"])
    check("Restore ran", r == {"FINISHED"}, str(r))
    return 3.0


@step
def s_restore_check():
    check("the project file opened again", bpy.data.filepath == STATE["project"], bpy.data.filepath)
    check("the restored project has the backup's Empty", any(o.type == "EMPTY" for o in bpy.data.objects))
    check("the restored project is the backup, not the work", bpy.context.scene.get("mark") != "work now")
    check("the work before Restore was kept as a backup", len(files()) == len(STATE["before_restore"]) + 1,
          str(files()))
    b = mod("blender.backups")
    newest = b.project_backups()[0]
    future = time.time() + 300
    os.utime(newest.path, (future, future))
    STATE["newer"] = newest.path
    b._S["shown"] = ""
    bpy.ops.wm.open_mainfile(filepath=STATE["project"])
    return 6.0


@step
def s_question_saved():
    b = mod("blender.backups")
    check("the start question shows for a newer backup", b._S["shown"] == STATE["newer"], b._S["shown"])
    shot("question_saved")
    esc()
    return 1.0


@step
def s_unsaved():
    bpy.ops.wm.read_homefile()
    b, core = mod("blender.backups"), mod("core.backups")
    folder = core.unsaved_folder(DOCS)
    os.makedirs(folder, exist_ok=True)
    from datetime import datetime
    STATE["unsaved"] = os.path.join(folder, core.backup_name(core.UNSAVED_NAME, datetime.now()))
    shutil.copyfile(STATE["project"], STATE["unsaved"])
    b._S["shown"] = ""
    b._schedule_question(first=0.5)                        # as at the start of the app
    return 4.0


@step
def s_question_unsaved():
    b = mod("blender.backups")
    check("the start question shows for unsaved work", b._S["shown"] == STATE["unsaved"], b._S["shown"])
    shot("question_unsaved")
    esc()
    return 1.5


@step
def s_turned_down():
    b, core = mod("blender.backups"), mod("core.backups")
    handled = core.load_state(b.state_path())["handled"]
    check("Esc turns it down: not asked again", os.path.basename(STATE["unsaved"]) in handled, str(handled))
    found, _mt = b.offer()
    check("nothing more to ask", found is None)
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
