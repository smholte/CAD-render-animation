"""Real-app test, the first-start set-up (task 0276).

Run on a settings folder WITHOUT Blender's saved preferences and without a start file (ci_real_app.py copies the
installed folder and takes both out), with FRESING_WELCOME_TEST=1 (the set-up shows although events are simulated) and
FRESING_SETUP_PROBE_LINES (the PC check's lines shortened):

* the first start: Blender's preferences are saved by the app before its splash (so Blender's quick set-up cannot
  come), the splash is left out on this start, the set-up opens in a window of its own;
* the whole way with real clicks on Next (the blue button at the bottom of the page): language, the work ticks and
  their workspace (none = Essentials, one = its workspace, two = All functions), the PC lines in plain words, a
  company's set-up file shown with what it sets, the Learning hub started and cancelled, Close at the end – the start
  file says "done" with the ticks, and the next start shows nothing;
* Set up again… from the Fresing menu, and **Skip set-up** clicked (top right): "skipped", the window closes;
* a company's set-up file with "first_setup": "skip": a new user starts straight in; an update from 0.2.195 shows
  What's new, not the set-up; the Client view never opens it.

    FRESING_WELCOME_TEST=1 xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_first_setup.py
GUIDE_OUT=<folder>: the guide pictures of each step go there.
"""

import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_first_setup"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_first_setup.log"), "w")
RESULTS = []
S = {}
TMP = tempfile.mkdtemp(prefix="fr_first é ")


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


def fs():
    return mod("blender.first_setup")


def values():
    return fs().values()


def state():
    w = mod("blender.welcome")
    return w.core.load(w.state_path())


def wins():
    return fs().windows()


def page(win):
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return area, next(r for r in area.regions if r.type == "TOOLS")


def main_override():
    sm = mod("blender.ops_setup")
    win, area, region = sm.main_view(bpy.context)
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region)


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def screen_h(path):
    out = subprocess.run(["identify", "-format", "%h", path], capture_output=True, text=True).stdout
    return int(out or 2600)


def crop_page(path, name):
    """The set-up's page cut from a root screenshot; with GUIDE_OUT set, into the guide's pictures too."""
    win = wins()[0]
    _a, reg = page(win)
    h = screen_h(path)
    left, top = win.x + reg.x, h - (win.y + reg.y + reg.height)
    dst = os.path.join(OUT, name + "_page.png")
    subprocess.run(["convert", path, "-crop", f"{reg.width}x{reg.height}+{left}+{top}", "+repage", dst], check=False)
    got = subprocess.run(["convert", dst, "-fuzz", "3%", "-trim", "-format", "%h %Y", "info:"],
                         capture_output=True, text=True).stdout.split()
    if len(got) == 2:                    # down to the page's last row
        hh = int(got[0]) + int(got[1].split("+")[-1]) + 10
        subprocess.run(["convert", dst, "-crop", f"{reg.width}x{hh}+0+0", "+repage", dst], check=False)
    guide = os.environ.get("GUIDE_OUT")
    if guide:
        subprocess.run(["cp", dst, os.path.join(guide, name + ".png")], check=False)
    return dst


def blue_button(path):
    """(x, y) in window pixels of the lowest blue (pressed-in) button on the set-up's page: Next, or Close on the last
    step. Read from the screenshot (Blender's pressed buttons are its accent blue)."""
    win = wins()[0]
    _a, reg = page(win)
    h = screen_h(path)
    left, top = win.x + reg.x, h - (win.y + reg.y + reg.height)
    txt = os.path.join(OUT, "_blue.txt")
    subprocess.run(["convert", path, "-crop", f"{reg.width}x{reg.height}+{left}+{top}", "+repage", "-scale", "50%",
                    "-depth", "8", "txt:" + txt], check=False)
    best = None
    with open(txt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            try:
                xy, rest = line.split(":", 1)
                x, y = (int(v) for v in xy.split(","))
                rgb = rest.split("(")[1].split(")")[0].split(",")
                r, g, b = (float(v) for v in rgb[:3])
            except (ValueError, IndexError):
                continue
            if b > 150 and b - r > 70 and g > 80 and b - g > 40:          # the accent blue
                if best is None or y > best[1]:
                    best = (x, y, [x])
                elif y == best[1]:
                    best[2].append(x)
    if best is None:
        return None
    xs = best[2]
    x_img, y_img = (min(xs) + max(xs)) / 2 * 2, best[1] * 2 - 8      # a little above the blue's lowest pixel row
    return int(reg.x + x_img), int(reg.y + reg.height - y_img)


def click(win, x, y):
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def wait_until(name, cond, seconds=30.0):
    def fn():
        if "t_wait" not in S:
            S["t_wait"] = time.time()
        try:
            ok = cond()
        except Exception:  # noqa: BLE001
            ok = False
        if ok or time.time() - S["t_wait"] > seconds:
            check(name, ok, f"{time.time() - S.pop('t_wait'):.1f} s")
            return 0.4
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


def press_next(expect):
    """A real click on the blue button; then the step must be ``expect``."""
    @step
    def press():
        win = wins()[0]
        redraw()
        path = shot("_next")
        pt = blue_button(path)
        S["pt"] = pt
        if pt is None:
            check(f"the blue button is found (towards {expect})", False)
            return 0.3
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=pt[0], y=pt[1] + 40)   # (the first click after
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=pt[0], y=pt[1] + 40)     # moving in may only focus)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=pt[0], y=pt[1] + 40)
        return 0.3

    @step
    def press2():
        pt = S.get("pt")
        if pt is not None and wins():
            click(wins()[0], *pt)
        return 0.8

    wait_until(f"a click on the blue button goes to the step {expect}",
               lambda: values().step == expect if expect != "closed" else not wins(), 8)


# ---------------------------------------------------------------------------
# the first start
# ---------------------------------------------------------------------------

@step
def s_start():
    w = mod("blender.welcome")
    check("the extension is on", pkg() is not None)
    check("Blender's preferences were saved by the app at the start (so its quick set-up cannot come)",
          fs().userpref_saved())
    check("this start shows the set-up", w._RUN["shows"] == "setup", w._RUN)
    check("... Blender's splash left out on this start", fs()._S.get("splash_hidden"), fs()._S)
    S["t0"] = time.time()
    return 0.5


wait_until("the set-up opens in a window of its own", lambda: bool(wins()) and page(wins()[0])[1].width > 200, 25)


@step
def s_stays():                              # 0328 row 1: it closed itself ~1.5 s after it opened
    S["t_open"] = time.time()
    return 4.0


@step
def s_stays2():
    check("the set-up stays open (4 s after it opened: still there, on Welcome)", bool(wins()) and
          values().step == "welcome", f"{time.time() - S['t_open']:.1f} s, windows {len(wins())}")
    return 0.3


@step
def s_page_only():
    ok, other = mod("blender.ops_settings").shows_only_the_page(wins()[0])
    check("the set-up window shows only its page (no tabs, view, headers, left panel)", ok, other)
    check("... on step 1 Welcome", values().step == "welcome", values().step)
    langs = [k for k, _t, _d in fs().languages_here()]
    check("the languages offered: English first", langs and langs[0] == "en_US", langs)
    return 1.0


@step
def s_shot_welcome():
    crop_page(shot("01_welcome"), "first_setup_welcome")
    return 0.3


press_next("work")


@step
def s_work():
    p = mod("blender.prefs").get()
    S["was_ws"] = p.default_workspace
    v = values()
    check("no tick: Essentials (not chosen)", p.default_workspace == "", p.default_workspace)
    v.work_cnc = True
    one = p.default_workspace
    v.work_sales = True
    two = p.default_workspace
    v.work_sales = False
    cnc = mod("core.workspaces").NAMES["cnc"]
    check("one tick: its workspace", one == cnc, one)
    check("two ticks: All functions", two == "All functions", two)
    check("back to one tick", p.default_workspace == cnc, p.default_workspace)
    redraw()
    return 1.0


@step
def s_shot_work():
    crop_page(shot("02_work"), "first_setup_work")
    return 0.3


press_next("pc")
wait_until("step 3 looks at the PC by itself (a second Blender)", lambda: fs().probe_running() or fs()._S["probe"], 5)
wait_until("... and answers", lambda: not fs().probe_running() and fs()._S["probe"] is not None, 240)


@step
def s_pc():
    probe = fs()._S["probe"] or {}
    core = mod("core.first_setup")
    bad = core.probe_failed_text(probe)
    check("the PC check's lines ran", not bad, bad or [r.get("id") for r in probe.get("results", [])])
    s = core.pc_summary(probe)
    check("... said in plain words (render device, a suggestion)",
          any("Renders on" in t for _i, t in s["lines"]) and s["suggest"], s["lines"])
    log("PC lines:", s["lines"], "| slow:", s["slow"], "|", probe.get("seconds"), "s")
    p = mod("blender.prefs").get()
    check("... Live preview set as suggested", p.live_preview == s["live_preview"], p.live_preview)
    redraw()
    return 1.0


@step
def s_shot_pc():
    crop_page(shot("03_pc"), "first_setup_pc")
    return 0.3


press_next("company")


@step
def s_company():
    L = mod("core.locations")
    loc = mod("blender.locations")
    path = os.path.join(TMP, "Bedrijf é" + L.SETUP_EXT)
    L.write_setup(path, L.from_data({"id": "uitest-first", "name": "Test company", "label": "Company",
                                     "settings": {"keep_howto": True},
                                     "first_start": {"workspace": "Sales"}}))
    loc.install(path)                     # as Open set-up file… / a drop on the window does
    S["setup_id"] = "uitest-first"
    check("a set-up file brought in from the set-up's step", loc.setup_of("uitest-first") is not None)
    check("... 'Different from standard' lists what it sets", bool(loc.differences()), len(loc.differences()))
    ws, badge = fs().setup_workspace()
    check("... its workspace is offered in step 2", ws == "Sales", (ws, badge))
    redraw()
    return 1.0


@step
def s_shot_company():
    crop_page(shot("04_company"), "first_setup_company")
    return 0.3


press_next("hub")


@step
def s_hub():
    check("the hub is not made yet here", fs().hub_state()[0] == "none", fs().hub_state())
    with main_override():
        bpy.ops.fresing.first_setup_hub("EXEC_DEFAULT", True)
    return 1.0


wait_until("Make it now starts making the Learning hub (in the main window)", lambda: fs().hub_state()[0] == "making", 10)


@step
def s_hub_shot():
    redraw()
    crop_page(shot("05_hub"), "first_setup_hub")
    with main_override():
        res = bpy.ops.fresing.tour_cancel("EXEC_DEFAULT")
    check("... and it can be cancelled", res == {"FINISHED"}, res)
    return 2.0


@step
def s_hub_gone():
    import shutil
    tour, w = mod("blender.tour"), mod("blender.welcome")
    shutil.rmtree(tour.files_dir(tour.default_folder(), w.version()), ignore_errors=True)
    hp = mod("blender.hub_progress")
    hp.dismiss()
    return 0.5


press_next("done")


@step
def s_shot_done():
    redraw()
    crop_page(shot("06_done"), "first_setup_done")
    return 0.3


press_next("closed")


@step
def s_done():
    st = state()
    w = mod("blender.welcome")
    check("Close: the set-up is done", st["setup"]["state"] == "done", st["setup"])
    check("... the ticks kept in the start file", st["setup"]["work"] == ["cnc"], st["setup"]["work"])
    check("... the next start shows nothing", w.at_start(force=True) == "", st)
    check("... the Learning hub opens on Machining", fs().suggested_chapter() == "Machining", fs().suggested_chapter())
    return 0.5


# ---------------------------------------------------------------------------
# Set up again…, Skip
# ---------------------------------------------------------------------------

@step
def s_again():
    ui_topbar = mod("blender.ui_topbar")
    check("Fresing > Set up again… is in the menu", "fresing.first_setup" in ui_topbar.entries())
    with main_override():
        res = bpy.ops.fresing.first_setup("EXEC_DEFAULT", True)
    check("Set up again… opens the set-up", res == {"FINISHED"}, res)
    return 0.5


wait_until("... its window", lambda: bool(wins()) and page(wins()[0])[1].width > 200, 20)


@step
def s_again_values():
    check("... on step 1 with the ticks kept", values().step == "welcome" and values().work_cnc, values().step)
    return 0.8


@step
def s_skip():
    win = wins()[0]
    _a, reg = page(win)
    scale = bpy.context.preferences.system.ui_scale or 1.0
    x, y = reg.x + reg.width - int(45 * scale), reg.y + reg.height - int(22 * scale)    # "Skip set-up", top right
    S["skip"] = (x, y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y - 60)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y - 60)        # (focus)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y - 60)
    return 0.4


@step
def s_skip_click():
    if wins():
        click(wins()[0], *S["skip"])
    return 1.0


wait_until("a click on Skip set-up closes the window", lambda: not wins(), 8)


@step
def s_skipped():
    check("... and says skipped", state()["setup"]["state"] == "skipped", state()["setup"])
    return 0.3


# ---------------------------------------------------------------------------
# a company's skip, an update, the Client view
# ---------------------------------------------------------------------------

@step
def s_it_skip():
    L = mod("core.locations")
    loc, w = mod("blender.locations"), mod("blender.welcome")
    path = os.path.join(TMP, "Managed é" + L.SETUP_EXT)
    L.write_setup(path, L.from_data({"id": "uitest-skip", "name": "Managed PCs", "first_setup": "skip"}))
    loc.install(path)
    w.save(w.core.fresh())                                   # a new user on a managed PC
    shows = w.at_start(force=True)
    st = state()
    check("a set-up file with \"first_setup\": \"skip\": the set-up does not show",
          shows == "" and st["setup"]["state"] == "skipped" and st["setup"]["by"] == "it", (shows, st["setup"]))
    loc.remove("uitest-skip")
    loc.remove(S.get("setup_id", ""))
    w.save(dict(w.core.fresh(), last_run="0.2.195"))         # an update from a version before the set-up
    shows = w.at_start(force=True)
    check("an update from 0.2.195 shows What's new, not the set-up", shows == "whats_new", shows)
    lock = mod("blender.lock")
    lock.ON[0] = True
    why = fs().open_window()
    lock.ON[0] = False
    check("the Client view never opens it", bool(why) and not wins(), why)
    return 0.5


@step
def s_finish():
    p = mod("blender.prefs").get()
    p.default_workspace = S.get("was_ws", "")
    w = mod("blender.welcome")
    w.save(dict(w.core.fresh(), last_run=w.version()))
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.app.timers.register(lambda: (bpy.ops.wm.quit_blender(), None)[1], first_interval=2.0)
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
        return 0.3
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
