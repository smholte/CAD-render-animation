"""Real-app test, task 0181: the usage tracker – the favourites bar, a click counted with its panel, the declutter
question, My usage.

On the test crane, with a made-up usage file (counts and 19 earlier starts): the next start sorts the bar, the bar
shows under the Workspace row with the declutter question under it; a real click on a favourite opens its section
and points at its button; a real click on *Sort parts into groups* counts for "Material groups" from the panel it was
in, with time saved per part; a real click on *Hide* hides the panel asked about; My usage opens; Back to the
workspace as it came shows it again. Buttons are found through the lesson highlight's ``found()``.

    FRESING_USAGE_TEST=1 BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/us xvfb-run -a -s "-screen 0 1800x1300x24" \\
        blender -p 0 0 1800 1300 --app-template fresing_render --enable-event-simulate --python tools/ui_test_usage.py
"""

import importlib
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_usage"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("FRESING_USAGE_TEST", "1")
os.environ["FRESING_USAGE_FILE"] = os.path.join(OUT, "usage é", "fresing_usage.json")
LOG = open(os.path.join(OUT, "ui_test_usage.log"), "w")
RESULTS = []
S = {}
def _fs():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import form_shots
    return form_shots


STEPS = []
KEPT = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def mod(name):
    import addon_utils
    pkg = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
    return importlib.import_module(pkg + "." + name)


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return (win, area, next(r for r in area.regions if r.type == "WINDOW"),
            next(r for r in area.regions if r.type == "UI"))


def override(side=False):
    win, area, region, sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if side else region,
                                     scene=win.scene)


def step(fn):
    STEPS.append(fn)
    return fn


def click(x, y):
    win = ui()[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def mouse_away():
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300, y=region.y + 300)


def grab_side(name):
    win, _area, _region, sb = ui()
    path = os.path.join(OUT, name)
    subprocess.run(["import", "-window", "root", "-crop",
                    f"{sb.width}x{min(sb.height, 900)}+{sb.x}+{win.height - (sb.y + sb.height)}", "+repage", path],
                   check=False)


def hl():
    return mod("blender.highlight")


def usage():
    return mod("blender.usage")


def redraw():
    for area in ui()[0].screen.areas:
        area.tag_redraw()


def point_and_wait(name, panel, button, text):
    """Two steps: point at the button, then wait until the highlight found it; S['box'] = its centre (window px)."""
    def point():
        S.pop("box", None)
        hl().point(panel=panel, button=button, text=text)
        S["t0"] = time.time()
        redraw()
        return 0.5

    def wait():
        f = hl().found()
        box = f.get("button") if f else None
        if box is None:
            if time.time() - S["t0"] > 20:
                check(f"{name}: the button is on screen", False, f"found {f}")
                hl().clear()
                return 0.2
            redraw()
            return "again"
        _w, _a, _r, sb = ui()
        rx, ry = (f.get("region") or (sb.x, sb.y))[:2]      # task 0260: the left panel or the side panel
        S["box"] = (rx + (box[0] + box[2]) // 2, ry + (box[1] + box[3]) // 2)
        check(f"{name}: the button is on screen", True, f"{box}")
        hl().clear()
        mouse_away()
        return 0.5
    point.__name__, wait.__name__ = "point_" + name, "wait_" + name
    STEPS.append(point)
    STEPS.append(wait)


def hover_found():
    """The mouse onto the button first (a user's hand gets there before the click)."""
    if "box" in S:
        ui()[0].event_simulate(type="MOUSEMOVE", value="NOTHING", x=S["box"][0], y=S["box"][1])
        S["n_hover"] = S.get("n_hover", 0) + 1
    return 0.6


def shot_hover():
    grab_side(f"hover_{S.get('n_hover', 0)}.png")
    return 0.1


def click_found():
    if "box" in S:
        click(*S["box"])
        mouse_away()
    return 1.0


# ---------------------------------------------------------------------------

@step
def s_setup():
    prefs = bpy.context.preferences
    KEPT.update(overlap=prefs.system.use_region_overlap)
    prefs.system.use_region_overlap = False
    us = usage()
    check("counting is on for this test", us.counting(), os.environ.get("FRESING_USAGE_TEST"))
    with override():
        r = bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    check("the import of the test crane starts", r in ({"FINISHED"}, {"RUNNING_MODAL"}), r)
    S["t0"] = time.time()
    return 1.0


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0 and time.time() - S["t0"] < 120:
        return "again"
    check("the test crane is imported", bpy.context.scene.fresing.model_count > 0)
    us = usage()
    us.forget()
    s = us.state()
    s["functions"] = {"scene.turntable": [5, 19], "looks.decals": [3, 18], "help.pc_check": [2, 15]}
    s["sessions"] = 19
    us.start()                                            # what the next start of the app does
    check("the next start counted a session", us.state()["sessions"] == 20, us.state()["sessions"])
    bar = us.bar(bpy.context.scene)
    check("the bar is sorted at the start", bar == ["scene.turntable", "looks.decals", "help.pc_check"], bar)
    us.project_changed(bpy.context.scene)
    S["asked"] = us.prompt()
    check("after 20 starts one unused panel is asked about", bool(S["asked"]), S["asked"])
    used = set(mod("blender.workspaces").used_functions(bpy.context.scene))
    check("... not one the project uses", not used & set(mod("core.usage").panel_functions(S["asked"])), used)
    with override(side=True):
        bpy.ops.view2d.scroll_up(page=True)
    redraw()
    return 1.0


@step
def s_shot_bar():
    grab_side("01_favourites_and_question.png")
    check("the favourites panel shows", bpy.types.FRESING_PT_favourites.poll(bpy.context))
    _w, _a, _r, sb = ui()
    click(sb.x + sb.width // 2, sb.y + sb.height - 12)     # a first click on the side panel's empty top edge
    _w, area, _r, _sb = ui()                               # task 0260: the favourites are on the left panel – a first
    left = next(r for r in area.regions if r.type == "TOOLS")   # click on its empty bottom gives it the focus
    click(left.x + left.width // 2, left.y + 12)
    return 0.6


point_and_wait("favourite", "FRESING_PT_favourites", "fresing.usage_go", "Logos & stickers")


step(hover_found)
step(shot_hover)


@step
def s_click_favourite():
    S["clicks_before"] = sum(usage().state()["buttons"].values())
    return click_found()


@step
def s_after_favourite():
    panels = mod("blender.panels")
    wm = bpy.context.window_manager
    if wm.fresing_tab != "3":                             # diagnosis: does the button work when called directly?
        try:
            with override(side=True):
                log("direct call:", bpy.ops.fresing.usage_go("INVOKE_DEFAULT", fid="looks.decals"), wm.fresing_tab)
        except Exception as exc:  # noqa: BLE001
            log("direct call failed:", exc)
        wm.fresing_tab = "ALL"
    check("a click on a favourite shows its section (tab 3)", wm.fresing_tab == "3", wm.fresing_tab)
    check("... opened down to its panel", panels.is_open("FRESING_PT_decals"))
    check("... and points at its button", usage()._S["go"] == "looks.decals", usage()._S["go"])
    check("going to a favourite is not counted as a use",
          sum(usage().state()["buttons"].values()) == S["clicks_before"], usage().state()["buttons"])
    grab_side("02_after_favourite.png")
    usage()._end_go()
    return 0.5


point_and_wait("sort", "FRESING_PT_looks", "fresing.apply_rules", "Sort parts into groups")


STEPS.append(lambda: hover_found())


@step
def s_click_sort():
    S["mat_before"] = usage().state()["functions"].get("looks.materials", [0, 0])[0]
    return click_found()


@step
def s_after_sort():
    st = usage().state()
    n = st["functions"].get("looks.materials", [0, 0])[0]
    check("a real click on Sort parts into groups counts for Material groups", n == S["mat_before"] + 1, n)
    check("... the click knew its panel", usage()._S["last_panel"] == "FRESING_PT_looks", usage()._S["last_panel"])
    check("... with time saved per part (an estimate)", st["saved"].get("looks.materials", 0) >= 5 * 10,
          st["saved"].get("looks.materials"))
    wm = bpy.context.window_manager
    wm.fresing_tab = "ALL"
    with override(side=True):
        bpy.ops.view2d.scroll_up(page=True)
    redraw()
    return 0.8


point_and_wait("hide", "FRESING_PT_favourites", "fresing.usage_declutter", "Hide it")


STEPS.append(lambda: hover_found())


@step
def s_click_hide():
    return click_found()


@step
def s_after_hide():
    us = usage()
    panel = S["asked"]
    hidden = mod("blender.workspaces").PERSONAL["hide"]
    check("Hide: the panel's functions are hidden for this user", set(mod("core.usage").panel_functions(panel))
          <= set(hidden), hidden)
    cls = getattr(bpy.types, panel)
    check("... the panel no longer shows", mod("blender.workspaces").panel_hidden(bpy.context.scene, panel), panel)
    check("... the question is gone for this session", us.prompt() == "", us.prompt())
    check("... and was written to the usage file", us.save(force=True) and os.path.isfile(us.path()), us.path())
    S["cls"] = cls
    grab_side("03_after_hide.png")
    return 0.3


@step
def s_window():
    with override():
        bpy.ops.fresing.usage_window("INVOKE_DEFAULT")
    return 1.0


@step
def s_window_shot():
    subprocess.run(["import", "-window", "root", os.path.join(OUT, "04_my_usage.png")], check=False)
    grab_side("05_bar_after_hide.png")
    return 0.4


@step
def s_window_close():
    # task 0271: My usage is a tab of the Fresing Settings window (it opens a moment after the button)
    import importlib
    st = importlib.import_module(usage().__name__.rsplit(".", 1)[0] + ".ops_settings")
    if not st.settings_windows():
        S["t_wait_settings"] = S.get("t_wait_settings", 0) + 1
        if S["t_wait_settings"] < 40:
            return "again"
    with override():
        bpy.ops.fresing.settings_close("EXEC_DEFAULT")
    return 0.5


@step
def s_reset():
    with override():
        bpy.ops.fresing.usage_reset()
    panel = S["asked"]
    check("Back to the workspace as it came shows the panel again",
          not mod("blender.workspaces").panel_hidden(bpy.context.scene, panel), panel)
    check("... and no personal hides are left", usage().state()["hidden"] == [], usage().state()["hidden"])
    return 0.3


@step
def s_learn_ask():
    """Task 0208: a second question, this time answered with the learning list."""
    us = usage()
    us.state()["learning"] = mod("core.learning").fresh()          # an earlier run's list stays in the file
    S["panel2"] = "FRESING_PT_xray" if S["asked"] != "FRESING_PT_xray" else "FRESING_PT_decals"
    us._S["prompt"] = S["panel2"]
    S["fid2"] = mod("core.learning").target_of_panel(S["panel2"])
    check("the second question has a function to teach", bool(S["fid2"]), S["panel2"])
    with override(side=True):
        bpy.ops.view2d.scroll_up(page=True)
    redraw()
    return 0.8


point_and_wait("learn_guide", "FRESING_PT_favourites", "fresing.learn_show", "Show me in the guide")
point_and_wait("learn_tour", "FRESING_PT_favourites", "fresing.learn_show", "Show me in the Learning hub")
point_and_wait("learn_list", "FRESING_PT_favourites", "fresing.usage_declutter", "Add to my learning list")


@step
def s_shot_learn():
    grab_side("06_learn_question.png")
    return 0.1


STEPS.append(lambda: hover_found())


@step
def s_click_learn():
    return click_found()


@step
def s_after_learn():
    us = usage()
    L = mod("core.learning")
    s = us.state()
    check("Add to my learning list puts the function on the list", L.find(s, S["fid2"]) is not None, S["fid2"])
    check("... the question is gone and nothing was hidden", us.prompt() == "" and s["hidden"] == [], s["hidden"])
    before = len(s["learning"]["list"])
    with override():
        bpy.ops.fresing.learn_add_new(since="0.2.100")
    check("What's new adds the new functions to the list", len(s["learning"]["list"]) > before,
          len(s["learning"]["list"]))
    with override():
        bpy.ops.fresing.learn_window("INVOKE_DEFAULT")
    return 2.0


@step
def s_learn_window_wait():
    S.setdefault("t_lw", time.time())
    if not _fs().ready_one(mod("blender.form_window").windows("fresing.learn_window")) and time.time() - S["t_lw"] < 15:
        return "again"
    return 1.0


@step
def s_learn_window_shot():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import form_shots
    path = os.path.join(OUT, "07_learning_list.png")
    subprocess.run(["import", "-window", "root", path], check=False)
    fw = mod("blender.form_window")
    wins = fw.windows("fresing.learn_window")
    check("My learning list opens in a window of its own (task 0282)", len(wins) == 1, str(len(wins)))
    if wins:                                       # the guide's picture (docs/img/learning_list.png)
        form_shots.crop(path, wins[0], os.path.join(OUT, "learning_list.png"))
        form_shots.key(wins[0], "ESC")             # Esc with the mouse over it closes it
    return 1.0


@step
def s_learn_window_close():
    S.setdefault("t_esc", time.time())
    if mod("blender.form_window").windows("fresing.learn_window") and time.time() - S["t_esc"] < 8:
        return "again"
    check("… Esc over it closes it", not mod("blender.form_window").windows("fresing.learn_window"))
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    if KEPT:
        bpy.context.preferences.system.use_region_overlap = KEPT["overlap"]
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
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
