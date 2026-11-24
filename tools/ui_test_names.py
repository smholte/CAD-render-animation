"""Real-app test, project names (task 0291): a new project with the test crane imported – Ctrl+S opens the save
browser with the crane's name in the crane's folder; Blender's own Save (another way to the browser) gets the same
name; the setting "Leave empty" proposes none; after saving, Ctrl+Shift+S opens the Save-as box with "<name> (1)"
selected – typing replaces it and Return saves the new project; the File menu's Save / Save As are the app's.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_names.py
ui_test_names.log goes to $UITEST_OUT (default ~/fresing_ui_test_names).
"""

import os
import shutil
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_names"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_names.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_names é ")
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
MODELS = os.path.join(TMP, "Modeller ø")
CRANE = os.path.join(MODELS, "test_crane_a.step")
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


def win0():
    return bpy.context.window_manager.windows[0]


def override():
    win = win0()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def key(k, win=None, **mods):
    """A key in the main window's 3D view (or in ``win``: the file browser's window)."""
    win = win or win0()
    view = next((a for a in win.screen.areas if a.type in ("VIEW_3D", "FILE_BROWSER")), win.screen.areas[0])
    x, y = view.x + view.width // 2, view.y + view.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", **mods)
    win.event_simulate(type=k, value="RELEASE", **mods)


DIGITS = dict(zip("0123456789", ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")))


def typed(text):
    win = win0()
    for c in text:
        k = {" ": "SPACE"}.get(c) or DIGITS.get(c) or c.upper()
        win.event_simulate(type=k, value="PRESS", unicode=c)
        win.event_simulate(type=k, value="RELEASE")


def browser_window():
    for win in bpy.context.window_manager.windows:
        if any(a.type == "FILE_BROWSER" for a in win.screen.areas):
            return win
    return None


def esc():
    key("ESC", win=browser_window())                         # the browser's own window when one is open


def browser():
    """(params, operator id) of an open save browser, or (None, "")."""
    win = browser_window()
    for area in (win.screen.areas if win else ()):
        if area.type == "FILE_BROWSER":
            sp = area.spaces.active
            op = getattr(sp, "active_operator", None)
            return sp.params, (getattr(op, "bl_idname", "") or "")
    return None, ""


def directory(params):
    d = params.directory
    d = d.decode("utf-8") if isinstance(d, bytes) else d
    return os.path.normpath(d)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_setup():
    esc()                                                    # the splash
    os.makedirs(MODELS, exist_ok=True)
    shutil.copyfile(SRC, CRANE)
    pn = mod("blender.project_name")
    check("the File menu's Save and Save As are the app's", pn.menu_swapped())
    check("Ctrl+S and Ctrl+Shift+S are the app's keys", len(pn._S["keys"]) == 2)
    check("a new project has no file", bpy.data.filepath == "")
    check("nothing imported: Untitled project", pn.proposal() == "Untitled project", pn.proposal())
    return 1.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    STATE["t0"] = time.time()
    return 1.0


@step
def s_wait_import():
    s = bpy.context.scene.fresing
    if s.model_count == 0:
        if time.time() - STATE["t0"] > 300:
            check("the test crane imported", False, s.last_message)
            return 0.5
        return "again"
    pn = mod("blender.project_name")
    STATE["name"] = pn.proposal()
    check("the test crane imported", s.model_count == 1, s.last_message)
    check("the proposal is the crane's name", STATE["name"] not in ("", "Untitled project")
          and " v" not in STATE["name"] and ".st" not in STATE["name"].lower(), STATE["name"])
    return 1.0


@step
def s_ctrl_s():
    key("S", ctrl=True)
    return 1.5


@step
def s_ctrl_s_browser():
    params, op = browser()
    check("Ctrl+S opens the save browser", params is not None and "save_as" in op.lower(), op)
    if params is not None:
        check("… with the crane's name filled in", params.filename == STATE["name"] + ".blend", params.filename)
        check("… in the crane's folder", directory(params) == os.path.normpath(MODELS), directory(params))
    shot("01_ctrl_s")
    esc()
    return 1.0


@step
def s_blender_save():
    check("the browser closed again", browser()[0] is None)
    pn = mod("blender.project_name")
    STATE["filled"] = pn.FILLED[0]
    with override():                                         # Blender's own Save (as the "Save changes?" question)
        bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")
    return 1.5


@step
def s_blender_save_browser():
    pn = mod("blender.project_name")
    params, _op = browser()
    check("Blender's own Save gets the same name", params is not None and params.filename == STATE["name"] + ".blend",
          params.filename if params else "no browser")
    check("… filled in once by the browser's handler", pn.FILLED[0] == STATE["filled"] + 1, pn.FILLED[0])
    esc()
    return 1.0


@step
def s_leave_empty():
    p = mod("blender.prefs").get()
    p.new_project_name = "empty"
    key("S", ctrl=True)
    return 1.5


@step
def s_leave_empty_browser():
    params, _op = browser()
    check("Leave empty: the browser opens with no name", params is not None and params.filename == "",
          params.filename if params else "no browser")
    esc()
    mod("blender.prefs").get().new_project_name = "model"
    return 1.0


@step
def s_save():
    STATE["project"] = os.path.join(MODELS, STATE["name"] + ".blend")
    with override():
        bpy.ops.wm.save_as_mainfile("EXEC_DEFAULT", filepath=STATE["project"])
    check("the project saved under the crane's name", bpy.data.filepath == STATE["project"], bpy.data.filepath)
    key("S", ctrl=True, shift=True)
    return 1.5


@step
def s_save_as_box():
    shot("02_save_as")
    check("Ctrl+Shift+S opens no browser on a saved project", browser()[0] is None)
    typed("Kran 2")                                          # the selected "(1)" name is typed over
    return 1.0


@step
def s_save_as_type():
    key("RET")                                               # ends the typing
    return 0.8


@step
def s_save_as_ok():
    key("RET")                                               # Save
    return 1.5


@step
def s_saved_as():
    want = os.path.join(MODELS, "Kran 2.blend")
    check("typing replaced the proposal and Return saved it", bpy.data.filepath == want and os.path.isfile(want),
          bpy.data.filepath)
    check("the first file is still there", os.path.isfile(STATE["project"]))
    shot("03_saved_as")
    pn = mod("blender.project_name")
    check("the next Save as proposes Kran 2 (1)", pn.save_as_proposal() == "Kran 2 (1)", pn.save_as_proposal())
    key("S", ctrl=True, shift=True)
    return 1.5


@step
def s_save_as_enter():
    key("RET")                                               # the proposal kept: Return ends the field …
    return 0.8


@step
def s_save_as_enter2():
    key("RET")                                               # … and saves
    return 1.5


@step
def s_saved_as_proposal():
    want = os.path.join(MODELS, "Kran 2 (1).blend")
    check("Return twice saves the proposal \"Kran 2 (1)\"", bpy.data.filepath == want and os.path.isfile(want),
          bpy.data.filepath)
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
    if r == "again":
        return 0.3
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
