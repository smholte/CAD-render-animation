"""Real-app test, Start here (task 0199): the welcome of a new user, What's new after an update, the Fresing menu.

Run with a settings folder that has no start file yet and with FRESING_WELCOME_TEST=1 (ci_real_app.py does both): the
app's own start decides what to show, the splash shows it, then this script plays more starts on the same start file
(``welcome.at_start(force=True)`` = what the next start of the app does) and drives the real windows with keys:

* a new user (task 0276): the first-start set-up at three starts, then never (its own test: ui_test_first_setup.py);
  the welcome window of the Fresing menu: Esc (Later) and Don't show this again; Take the test tour (Enter) starts the
  tour build, Cancel stops it;
* an existing user whose last version (written by this test) is older: What's new once with the right functions and
  test models; Make the tour (Enter) makes only the new and changed sets (count and time in the log); the next start
  and the same version again show nothing;
* the Fresing menu after Help in Full access, another workspace and the Client view; pictures at UI scale 1 and 2.

    FRESING_WELCOME_TEST=1 xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_start.py
"""

import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_start"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_start.log"), "w")
RESULTS = []
STATE = {}


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


def win():
    return bpy.context.window_manager.windows[0]


def override():
    w = win()
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region)


def key(k):
    w = win()
    x, y = w.width // 2, w.height // 2
    w.event_simulate("MOUSEMOVE", "NOTHING", x=x, y=y)
    w.event_simulate(k, "PRESS", x=x, y=y)
    w.event_simulate(k, "RELEASE", x=x, y=y)


def shot(name, crop=None):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    if crop:
        subprocess.run(["convert", path, "-crop", crop, "+repage", path], check=False)


def state():
    w = mod("blender.welcome")
    return w.core.load(w.state_path())


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


# ---------------------------------------------------------------------------
# a new user
# ---------------------------------------------------------------------------

def setup_windows():
    return mod("blender.first_setup").windows()


@step
def s_first_start():
    w = mod("blender.welcome")
    check("the extension is on", pkg() is not None)
    check("the first start in a new settings folder shows the set-up (task 0276)", w._RUN["shows"] == "setup", w._RUN)
    check("the start was counted", state()["welcome"]["later"] == 1, state())
    STATE["t0"] = time.time()
    return 0.5


@step
def s_setup_window():
    if not setup_windows() and time.time() - STATE["t0"] < 20:
        return -0.3
    check("... in a window of its own", bool(setup_windows()), len(bpy.context.window_manager.windows))
    shot("01_first_setup")
    mod("blender.first_setup").remember("")      # closed on the way: as Later
    mod("blender.first_setup").close_window()
    return 1.0


@step
def s_dialog_later():
    w = mod("blender.welcome")
    if w._quick_setup_open():                    # first run: Blender's quick set-up came first; Continue saves prefs
        bpy.ops.wm.save_userpref()
    with override():
        bpy.ops.fresing.welcome("INVOKE_DEFAULT", at_start=True)
    return 0.8


@step
def s_dialog_later_shot():
    shot("02_welcome_window")
    key("ESC")                                   # Cancel = Later
    return 0.6


@step
def s_two_more_starts():
    w = mod("blender.welcome")
    check("the set-up closed on the way: asked again", w.core.decide(state(), w.version()) == "setup", state())
    check("... its window is closed", not setup_windows())
    shown = [w.at_start(force=True) for _ in range(3)]   # the 2nd, 3rd and 4th start of the app
    check("Later: the set-up at three starts, then never", shown == ["setup", "setup", ""], shown)
    check("... after that updates bring What's new", state()["last_run"] == w.version(), state())
    return 0.3


@step
def s_never():
    w = mod("blender.welcome")
    w.save(w.core.fresh())                       # a new settings folder again
    w.at_start(force=True)
    with override():
        bpy.ops.fresing.welcome("INVOKE_DEFAULT", at_start=True, never=True)
    return 0.8


@step
def s_never_close():
    shot("03_welcome_never_ticked")
    key("ESC")
    return 0.6


@step
def s_never_check():
    w = mod("blender.welcome")
    check("Don't show this again: never at a start again",
          state()["welcome"]["never"] and w.at_start(force=True) == "", state())
    w.save(w.core.fresh())
    w.at_start(force=True)
    with override():
        bpy.ops.fresing.welcome("INVOKE_DEFAULT", at_start=True)
    return 0.8


@step
def s_take_tour():
    key("RET")                                   # Take the test tour
    return 1.5


@step
def s_take_tour_check():
    w, ops_tour = mod("blender.welcome"), mod("blender.ops_tour")
    running = ops_tour.building().get("running")
    check("Take the test tour starts making the tour", bool(running), ops_tour.building())
    check("... and the welcome is answered", state()["welcome"]["done"] and w.at_start(force=True) == "", state())
    shot("04_tour_making", crop=None)
    with override():
        res = bpy.ops.fresing.tour_cancel("EXEC_DEFAULT")
    check("Cancel making the test tour", res == {"FINISHED"}, res)
    return 2.0


@step
def s_cancelled():
    ops_tour = mod("blender.ops_tour")
    check("... the build stopped", not ops_tour.building().get("running"), ops_tour.building())
    import shutil
    tour, w = mod("blender.tour"), mod("blender.welcome")
    shutil.rmtree(tour.files_dir(tour.default_folder(), w.version()), ignore_errors=True)   # what it made so far
    return 0.3


# ---------------------------------------------------------------------------
# an existing user after an update
# ---------------------------------------------------------------------------

@step
def s_update():
    w, tour = mod("blender.welcome"), mod("blender.tour")
    older = os.environ.get("START_TEST_SINCE", "0.2.150")
    st = w.core.fresh()
    st.update(last_run=older)
    st["welcome"]["done"] = True
    w.save(st)                                   # this settings folder last ran an older version
    shows = w.at_start(force=True)
    check("a newer version than the last one run shows What's new", shows == "whats_new", shows)
    funcs = w.functions_new(older)
    sets = w.sets_new(older)
    want = [ts.id for ts in tour.SETS.values() if w.core.mark(ts.added, ts.changed, older, w.version())]
    check("What's new lists the functions added or improved since then",
          bool(funcs) and all(w.core.in_range(f.since if k == "new" else f.changed, older, w.version())
                              for f, k in funcs), [f.id for f, _k in funcs])
    check("... and the new and changed test models", [ts.id for ts, _k in sets] == want and want, want)
    log("What's new:", [f"{f.id} ({k})" for f, k in funcs], "sets:", [f"{ts.id} ({k})" for ts, k in sets])
    STATE["sets"] = want
    with override():
        bpy.ops.fresing.whats_new("INVOKE_DEFAULT", at_start=True)
    return 1.0


@step
def s_whats_new_later():
    shot("05_whats_new")
    key("ESC")                                   # Later: stays in the menu
    return 0.6


@step
def s_whats_new_pending():
    w = mod("blender.welcome")
    check("Later keeps What's new in the Fresing menu", w.core.whats_new_pending(state()), state())
    check("a second start shows nothing", w.at_start(force=True) == "")
    with override():
        bpy.ops.fresing.whats_new("INVOKE_DEFAULT", at_start=True)
    return 1.0


@step
def s_make_new_tour():
    key("RET")                                   # Make the tour (only the new and changed models)
    STATE["t0"] = time.time()
    return 2.0


@step
def s_wait_tour():
    ops_tour = mod("blender.ops_tour")
    if ops_tour.building().get("running") and time.time() - STATE["t0"] < 600:
        return -2.0                              # this step again in 2 s
    tour = mod("blender.tour")
    w = mod("blender.welcome")
    folder = tour.default_folder()
    made = tour.made_sets(folder, w.version())
    data = tour.read_progress(folder)
    secs = time.time() - STATE["t0"]
    log(f"tour of the new and changed models: {len(made)} of {len(tour.SETS)} sets in {secs:.0f} s "
        f"(build {data.get('seconds')} s): {made}")
    check("Make the tour made only the new and changed sets", sorted(made) == sorted(STATE["sets"]),
          f"{made} / {STATE['sets']}")
    check("... without errors", data.get("finished") and not data.get("errors"), data.get("errors"))
    check("What's new counts as opened", not w.core.whats_new_pending(state()), state())
    check("the same version again shows nothing", w.at_start(force=True) == "")
    st = state()
    st["last_run"] = "9.9.9"
    w.save(st)
    check("after a downgrade nothing shows", w.at_start(force=True) == "")
    return 0.5


# ---------------------------------------------------------------------------
# the Fresing menu
# ---------------------------------------------------------------------------

@step
def s_menu_full():
    topbar = mod("blender.ui_topbar")
    check("the Fresing menu is in the top bar", topbar._draw_in_editor_menus in
          bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize())
    for idname in topbar.entries():
        check(f"menu entry {idname} works (its operator is there)", topbar._has(idname))
    help_names = [getattr(f, "__name__", "") for f in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()]
    check("the Help menu keeps its Fresing lines", "_draw_help_menu" in help_names and "_draw_help" in help_names,
          help_names)
    with override():
        bpy.ops.wm.call_menu(name=topbar.MENU)
    return 0.8


@step
def s_menu_shot():
    shot("06_fresing_menu")
    key("ESC")
    return 0.4


@step
def s_about_open():
    about, files = mod("blender.about"), mod("blender.files")
    names = [getattr(f, "__name__", "") for f in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()]
    check("About Fresing Render is in the Help menu too (task 0206)", "_draw_about_help" in names and about._draw_about_help in
          bpy.types.TOPBAR_MT_help._dyn_ui_initialize(), names)
    opened = []
    real = files.open_path
    files.open_path = lambda path: opened.append(path)         # no text program in the test: only what would open
    try:
        for which, needle in (("LICENCE", "GNU GENERAL PUBLIC LICENSE"), ("NOTICES", "Third-party notices"),
                              ("COMPANY", "company"), ("TEXTS", "third-party")):
            opened.clear()
            with override():
                res = bpy.ops.fresing.about_open("EXEC_DEFAULT", which=which)
            path = opened[0] if opened else ""
            body = open(path, encoding="utf-8").read() if os.path.isfile(path) and which != "TEXTS" else path
            check(f"About > {which.title()} opens a file of this install, offline",
                  res == {"FINISHED"} and needle.lower() in body.lower(), f"{res} {path}")
    finally:
        files.open_path = real
    with override():
        bpy.ops.fresing.about("INVOKE_DEFAULT")
    return 2.0


@step
def s_about_shot():
    shot("06b_about", crop=None)
    fw = mod("blender.form_window")
    wins = fw.windows("fresing.about")
    check("About opens in a window of its own (task 0282)", len(wins) == 1, str(len(wins)))
    fw.close("fresing.about")                    # Close
    return 1.0


@step
def s_client_view():
    ws, lock, topbar = mod("blender.workspaces"), mod("blender.lock"), mod("blender.ui_topbar")
    scene = bpy.context.scene
    names = mod("core.workspaces").NAMES
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=names["cnc"])
    check("another workspace: lock.py draws the top bar (no workspace tabs)", lock.tabs_hidden())
    check("... the Fresing menu is in the top bar", topbar._draw_in_editor_menus in
          bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize())
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=names["client"])
    check("the Client view is on", lock.ON[0] and ws.locked(scene), ws.name_of(scene))
    check("lock.py draws the top bar (no workspace tabs)", lock.tabs_hidden())
    check("the Fresing menu is still in the top bar", topbar._draw_in_editor_menus in
          bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize())
    for idname in topbar.entries():
        if idname == "fresing.blender_all":      # task 0241: Show all of Blender is greyed here – the lock refuses it
            q = mod("blender.quiet")              # and its tooltip says how to unlock
            check("Client view: Show all of Blender is greyed, with the reason", not lock.allowed(idname)
                  and not bpy.ops.fresing.blender_all.poll()
                  and q.FRESING_OT_blender_all.description(bpy.context, None).startswith(q.LOCKED_TEXT))
            continue
        if idname == "fresing.backups_window":   # task 0246: no backups in the Client view – greyed, with the reason
            ob = mod("blender.ops_backups")
            check("Client view: Restore a backup… is greyed, with the reason", not lock.allowed(idname)
                  and not bpy.ops.fresing.backups_window.poll()
                  and ob.FRESING_OT_backups_window.description(bpy.context, None).startswith(ob.LOCKED_TEXT))
            continue
        if idname == "fresing.first_setup":      # task 0276: the set-up never opens in the Client view – greyed
            fs = mod("blender.first_setup")
            check("Client view: Set up again… is greyed, with the reason", not lock.allowed(idname)
                  and not bpy.ops.fresing.first_setup.poll()
                  and fs.FRESING_OT_first_setup.description(bpy.context, None).startswith(fs.LOCKED_TEXT))
            continue
        check(f"Client view: {idname} is not refused by the lock", lock.allowed(idname))
    check("Client view: a change of the project is still refused", not lock.allowed("fresing.joint_add"))
    with override():
        bpy.ops.wm.call_menu(name=topbar.MENU)
    return 0.8


@step
def s_client_shot():
    shot("07_menu_client_view")
    key("ESC")
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=mod("core.workspaces").NAMES["all"])
    return 0.5


@step
def s_scale_2():
    bpy.context.preferences.view.ui_scale = 2.0          # Windows display scaling 200 %
    w = mod("blender.welcome")
    w.save(dict(w.core.fresh(), last_run="0.2.150"))
    return 1.5


@step
def s_scale_2_open():
    with override():
        bpy.ops.fresing.whats_new("INVOKE_DEFAULT", at_start=True)
    return 1.5


@step
def s_scale_2_shot():
    shot("08_whats_new_200")
    key("ESC")
    return 0.5


@step
def s_scale_2_welcome():
    with override():
        bpy.ops.fresing.welcome("INVOKE_DEFAULT", at_start=True)
    return 1.5


@step
def s_scale_2_welcome_wait():
    return 0.5


@step
def s_scale_2_welcome_shot():
    shot("09_welcome_200")
    key("ESC")
    bpy.context.preferences.view.ui_scale = 1.0          # put the preference back (it is saved at quit)
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
    if isinstance(r, (int, float)) and r < 0:    # a step that waits: run it again
        return -r
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
