"""Real-app test: Help > Fresing Render user guide opens the guide shipped in the installed extension.

Install the extension (Linux build with the guide inside: tools/test_install_linux.py builds it that way)
and the app template first, see tools/ui_test_app.py. Then:

    xvfb-run -a -s "-screen 0 1920x1200x24" blender -p 0 0 1920 1200 --app-template fresing_render \\
        --enable-event-simulate --python tools/guide_test_app.py

The window must be 1920 x 1200 at UI scale 1.0: the test clicks "Help" in the top bar and then the
first entry of the menu, at fixed places. Opening the browser is replaced by a recorder (no browser
here); the test checks which file would open. Exit code 0 when every check passes; the log goes to
$GUIDETEST_OUT (default ~/fresing_guide_test).
"""

import os
import subprocess
import sys
import time
import traceback

import bpy

OUT = os.environ.get("GUIDETEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_guide_test"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "guide_test.log"), "w")
RESULTS = []
OPENED = []


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[GUIDETEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def template():
    """The app template's module (it defines the Help-menu entry)."""
    for name, m in list(sys.modules.items()):
        if name.endswith("fresing_render") and hasattr(m, "FRESING_OT_user_guide"):
            return m
    return None


def click(x_from_left, y_from_top):
    win = bpy.context.window_manager.windows[0]
    x, y = x_from_left, win.height - y_from_top
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def t_start():
    win = bpy.context.window_manager.windows[0]
    log("window", win.width, win.height, "ui scale", bpy.context.preferences.view.ui_scale)
    win.event_simulate(type="ESC", value="PRESS", x=900, y=600)       # close the splash screen
    win.event_simulate(type="ESC", value="RELEASE", x=900, y=600)
    return 1.5


@step
def t_registered():
    m = template()
    check("app template defines the guide entry", m is not None)
    if m is None:
        return 0.2
    m.open_path = lambda path: OPENED.append(path)                     # no browser here
    funcs = bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
    check("entry is in the Help menu", m._draw_help_menu in funcs)
    check("entry is the first item of the Help menu", funcs and funcs[0] is m._draw_help_menu)
    path = m.guide_path()
    check("guide found in the installed extension", path and os.sep + "guide" + os.sep in path
          and "extensions" in path, path)
    ok = False
    if path and os.path.isfile(path):
        text = open(path, encoding="utf-8").read()
        ok = "Fresing Render user guide" in text and "data:image/png;base64," in text and "<h2" in text
        log("guide size", f"{os.path.getsize(path) / 1e6:.2f} MB")
    check("guide is the complete page (title, chapters, pictures inside)", ok)
    return 0.5


@step
def t_open_menu():
    click(235, 13)                    # "Help" in the top bar
    return 1.5


@step
def t_shot_menu():
    subprocess.run(["import", "-window", "root", os.path.join(OUT, "help_menu.png")], check=False)
    return 0.3


@step
def t_click_entry():
    click(300, 38)                    # first entry: "Fresing Render user guide"
    return 1.5


@step
def t_opened():
    m = template()
    path = m.guide_path() if m else ""
    check("clicking the entry opens the guide", OPENED and OPENED[-1] == path, f"{OPENED}")
    OPENED.clear()
    res = bpy.ops.fresing.user_guide()
    check("the entry also works when called directly", res == {"FINISHED"} and OPENED == [path], f"{res}")
    # missing guide: a clear message, nothing opened
    if m is not None:
        real = m.guide_path
        m.guide_path = lambda: ""
        OPENED.clear()
        try:
            res = bpy.ops.fresing.user_guide()
        except RuntimeError as exc:           # the operator reports an error: Blender raises it to scripts
            res = {"ERROR: " + str(exc).strip()}
        m.guide_path = real
        check("missing guide: message 'run Install.bat again', nothing opened",
              not OPENED and any("Install.bat" in r for r in res), f"{res}")
    return 0.3


@step
def t_quit():
    failed = [n for n, ok in RESULTS if not ok]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed" + (f"; failed: {failed}" if failed else ""))
    LOG.close()
    os._exit(0 if not failed and RESULTS else 1)


_i = [0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    _i[0] += 1
    try:
        return fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        RESULTS.append((fn.__name__, False))
        return 0.3


bpy.context.preferences.view.ui_scale = 1.0
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
_t0 = time.time()
