"""Real-app test, function windows (task 0282): a function's form opens in a window of its own.

Make a crane… (the owner's example) opens a window that shows only its form; a click in the main window leaves it
open; pressing the button again opens no second window and keeps what was typed; Save as my own workspace… opens a
second function window beside it; Esc with the mouse over a window closes that one only; closed and opened again, a
window comes back at the size it had (on Linux nothing can move a window – its place on Windows: the owner's steps);
Save pose…: Return over the window saves the pose with the name typed in it and the window closes; Make that is
refused keeps the window open and says why; the Client view refuses Save pose… as before (no window) and still opens
Save scene…; another project closes the windows of the one before.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        -p 0 0 1800 1200 --python tools/ui_test_forms.py
Screenshots and ui_test_forms.log go to $UITEST_OUT (default ~/fresing_ui_test_forms).
"""

import os
import subprocess
import sys
import time
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import form_shots  # noqa: E402

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_forms"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_forms.log"), "w")
RESULTS = []
S = {}
CRANE, WS, POSE, SHOT = "fresing.lifting_make", "fresing.workspace_save", "fresing.pose_save", "fresing.shot_save"


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
    return importlib.import_module(pkg() + ("." + name if name else ""))


def fw():
    return mod("blender.form_window")


def main_win():
    sm = mod("blender.ops_setup")
    return next(w for w in bpy.context.window_manager.windows if not sm.tab_of(w))


def view():
    win = main_win()
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def invoke(idname, **kw):
    cat, _, name = idname.partition(".")
    with override():
        return getattr(getattr(bpy.ops, cat), name)("INVOKE_DEFAULT", **kw)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def wins(idname=None):
    return fw().windows(idname)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def wait_until(name, cond, seconds=20.0):
    def fn():
        if "t_wait" not in S:
            S["t_wait"] = time.time()
        try:
            ok = cond()
        except Exception:  # noqa: BLE001
            ok = False
        if ok or time.time() - S["t_wait"] > seconds:
            check(name, ok, f"{time.time() - S.pop('t_wait'):.1f} s")
            return 0.5
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


@step
def s_start():
    check("the extension is on", pkg() is not None)
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)     # the splash swallows keys
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    p = mod("blender.prefs").get()
    S["was"] = {"window_places": p.window_places, "lifting_understood": p.lifting_understood}
    p.window_places = ""
    mod("blender.ops_make").forget_places()
    mod("blender.lifting").set_understood(True)        # Make a crane asks "I understand" once per user
    bpy.context.preferences.system.use_region_overlap = False
    return 1.5


# ----- Make a crane: a window that stays open -----

@step
def s_open_crane():
    m = mod("blender.ui_lifting_make").settings(bpy.context)
    m.kind, m.start = "AT", "AT-40"
    r = invoke(CRANE)
    check("Make a crane… opens (no dialog: its window is on its way)", r == {"FINISHED"}, str(r))
    return 0.5


wait_until("Make a crane opens in a window of its own", lambda: form_shots.ready_one(wins(CRANE)))
wait_until("… the window shows only its form (no view, no tabs, no headers)",
           lambda: mod("blender.ops_settings").shows_only_the_page(wins(CRANE)[0])[0], 10)


@step
def s_crane_drawn():
    win = wins(CRANE)[0]
    ok, other = mod("blender.ops_settings").shows_only_the_page(win)
    log("window", win.x, win.y, win.width, win.height, "other:", other)
    check("its title is the function's name", fw().title(CRANE) == "Make a crane", fw().title(CRANE))
    path = shot("01_make_a_crane")
    form_shots.crop(path, win, os.path.join(OUT, "dialog_8_make_crane.png"))     # the guide's picture
    d = mod("blender.ui_lifting_make").settings(bpy.context)
    d.name = "My typed crane"                         # what the user typed
    S["typed"] = d.name
    main, area, _r = view()                           # a click in the main 3D view
    x, y = area.x + area.width * 2 // 3, area.y + area.height // 3
    main.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    main.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    main.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_crane_stays():
    check("a click in the main window leaves the window open", len(wins(CRANE)) == 1)
    r = invoke(CRANE)
    check("pressing Make a crane again opens no second window", r == {"FINISHED"} and len(wins(CRANE)) == 1, str(r))
    d = mod("blender.ui_lifting_make").settings(bpy.context)
    check("… and what was typed stays", d.name == S["typed"], d.name)
    r = invoke(WS)
    check("Save as my own workspace… opens too", r == {"FINISHED"}, str(r))
    return 0.5


wait_until("two function windows are open at once", lambda: form_shots.ready_one(wins(WS)) and len(wins(CRANE)) == 1)


@step
def s_two():
    path = shot("02_two_windows")
    win = wins(WS)[0]
    form_shots.crop(path, win, os.path.join(OUT, "form_workspace_save.png"))
    d = fw().data(WS)
    d.name = "Two at once"
    check("each window has its own values", d.name == "Two at once"
          and mod("blender.ui_lifting_make").settings(bpy.context).name == S["typed"])
    form_shots.key(win, "ESC")                         # Esc with the mouse over the workspace window
    return 0.3


wait_until("Esc over a window closes that window only", lambda: not wins(WS) and len(wins(CRANE)) == 1, 8)


@step
def s_esc():
    check("… nothing was saved", not mod("blender.workspaces").is_own("Two at once"))
    with override():
        bpy.ops.fresing.form_close(form=CRANE)
    return 1.0


@step
def s_closed():
    check("Close closes the Make a crane window", not wins(CRANE))
    om = mod("blender.ops_make")
    S["kept"] = om.kept_size("form:" + CRANE)
    check("its size is kept in the settings file (Fresing's own preference)",
          S["kept"] is not None and '"form:fresing.lifting_make"' in mod("blender.prefs").get().window_places,
          str(S["kept"]))
    # as if the user had made it 560 x 640 (no window manager under xvfb to drag an edge with)
    om._kept()["sizes"]["form:" + CRANE] = [560, 640]
    om._store()
    invoke(CRANE)
    return 0.5


wait_until("opened again", lambda: len(wins(CRANE)) == 1)


@step
def s_size():
    win = wins(CRANE)[0]
    scale = bpy.context.preferences.system.ui_scale or 1.0
    w, h = win.width / scale, win.height / scale
    check("it opens at the size it had (560 x 640)", abs(w - 560) < 30 and abs(h - 640) < 30, f"{w:.0f} x {h:.0f}")
    with override():
        bpy.ops.fresing.form_close(form=CRANE)
    return 1.0


# ----- Save pose: Return is its Save; a refused Make says why -----

@step
def s_pose():
    check("closed", not wins(CRANE))
    S["poses"] = len(bpy.context.scene.fresing.poses)
    invoke(POSE)
    return 0.5


wait_until("Save pose… opens in a window", lambda: len(wins(POSE)) == 1)


@step
def s_pose_save():
    fw().data(POSE).name = "Typed in the window"
    form_shots.key(wins(POSE)[0], "RET")
    return 1.0


@step
def s_pose_saved():
    names = [p.name for p in bpy.context.scene.fresing.poses]
    check("Return over the window saves the pose with the name typed in it", "Typed in the window" in names, names)
    check("… and the window closes", not wins(POSE))
    S["undo"] = len(names)
    with override():
        bpy.ops.ed.undo()
    n = len(bpy.context.scene.fresing.poses)
    check("Ctrl+Z takes the pose back (an undo step of its own)", n == S["undo"] - 1, f"{S['undo']} -> {n}")
    invoke(WS)
    return 0.5


wait_until("Save as my own workspace… opens again", lambda: form_shots.ready_one(wins(WS)))


@step
def s_refused():
    fw().data(WS).name = ""                             # no name: the workspace cannot be saved
    with override():
        r = bpy.ops.fresing.form_ok(form=WS)
    form = fw()._FORMS.get(WS, {})
    check("Save with no name is refused: the window stays and says why", r == {"CANCELLED"} and len(wins(WS)) == 1
          and bool(form.get("error")), form.get("error", ""))
    redraw()
    return 0.8


@step
def s_refused_shot():
    path = shot("03_refused")
    form_shots.crop(path, wins(WS)[0], os.path.join(OUT, "form_refused.png"))
    fw().close(WS)
    return 1.0


# ----- the Client view: refused stays refused -----

@step
def s_client():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 2.0


@step
def s_client_check():
    try:
        r = invoke(POSE)
    except RuntimeError as exc:
        r = {"refused"}
        log("refused:", str(exc)[:120])
    check("Client view: Save pose… is refused as before – no window", r != {"FINISHED"} and not wins(POSE), str(r))
    r = invoke(SHOT)
    check("Client view: Save scene… (allowed there) opens its window", r == {"FINISHED"}, str(r))
    return 0.5


wait_until("… its window is there", lambda: len(wins(SHOT)) == 1)


@step
def s_full():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
    invoke(WS)
    return 2.0


wait_until("two windows before another project opens", lambda: len(wins()) == 2)


@step
def s_new_project():
    with override():
        bpy.ops.wm.read_homefile(app_template="fresing_render")
    return 1.0


wait_until("another project closes the windows of the one before", lambda: not wins(), 15)


@step
def s_keep_back():
    """Put things back: the next real-app test in this settings folder starts as before (CLAUDE.md 8)."""
    p = mod("blender.prefs").get()
    for n, v in S.get("was", {}).items():
        setattr(p, n, v)
    mod("blender.ops_make").forget_places()
    bpy.context.preferences.system.use_region_overlap = True
    return 2.5


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
    except Exception:  # noqa: BLE001
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    if r == "again":
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
