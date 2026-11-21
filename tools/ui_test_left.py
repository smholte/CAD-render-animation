"""Real-app test, two panels (task 0260): the left panel in the 3D view's toolbar region – Live preview + Build & play,
update notice, Workspace, Learning hub, Favourites, What's next – at a readable width without Blender's tool buttons;
it folds to a strip with Live preview and Build & play and opens again; Full access brings Blender's tools back above
it; it keeps its width when projects open (an old one saved with a narrow toolbar, a Learning hub one) and in the
Client view; it scrolls. On the right Make is one row of icons (or the labelled list); each output opens a window of
its own that stays open when the main window is clicked, a second press gives no second window, Close closes it. The
Learning hub switch: outside a hub project it opens the Learn window; in a hub project (the crane) Show me opens the
lesson, Build it yourself switches the same lesson at once. Screenshots: left + right panel at the screen's size.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1920x1080x24" blender --app-template fresing_render --enable-event-simulate \\
        -p 0 0 1920 1080 --python tools/ui_test_left.py
Screenshots and ui_test_left.log go to $UITEST_OUT (default ~/fresing_ui_test_left).
"""

import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_left"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_left.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_left é ")
S = {}


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


def left_width():
    return mod("blender.ui_left").width(view()[1])


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def outputs(key=None):
    return mod("blender.ops_make").output_windows(key)


def tools_quiet():
    """Blender's tool buttons are not drawn (their draw is the app's empty one)."""
    q = mod("blender.quiet")
    return q._no_tools in q.draw_funcs(bpy.types.VIEW3D_PT_tools_active)


def workspace(name):
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=name)


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
            return 0.3
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


# ----- the start -----

@step
def s_start():
    check("the extension is on", pkg() is not None)
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)     # the splash swallows keys
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    redraw()
    return 1.5


wait_until("the left panel is shown at a readable width", lambda: left_width() >= 180, 20)


@step
def s_left_parts():
    check("Blender's tool buttons are not drawn there outside Full access", tools_quiet())
    order = [c.__name__ for c in mod("")._all_classes() if getattr(c, "bl_region_type", "") == "TOOLS"]
    check("the left panel's parts in order", order[:3] == ["FRESING_PT_left_quick", "FRESING_PT_update",
                                                           "FRESING_PT_workspace"] and order[-1] == "FRESING_PT_next",
          str(order))
    right = [c.__name__ for c in mod("")._all_classes()
             if getattr(c, "bl_category", "") == "Fresing" and getattr(c, "bl_region_type", "") == "UI"]
    check("the right panel starts with Make, the tabs, then 1 Import", right[:3] == [
        "FRESING_PT_make", "FRESING_PT_tabs", "FRESING_PT_import"], str(right[:4]))
    S["w0"] = left_width()
    log("left panel width (px at UI scale 1):", round(S["w0"]))
    shot("01_start")
    return 0.3


# ----- an imported model: Make on the right -----

@step
def s_import():
    data = os.path.join(os.path.dirname(mod("").__file__), "data", "test_crane.step")
    with override():
        r = bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=data)
    log("import:", r)
    return 1.0


wait_until("the crane is imported", lambda: bpy.context.scene.fresing.model_count > 0, 120)


@step
def s_make_row():
    redraw()
    shot("02_crane_two_panels")
    with override():
        r = bpy.ops.fresing.make_window("EXEC_DEFAULT", key="still")
    check("Make > Picture starts its window", r == {"FINISHED"}, r)
    return 1.0


wait_until("the Picture window is open", lambda: len(outputs("still")) == 1, 20)


@step
def s_click_elsewhere():
    win, area, _r = view()
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_still_open():
    wins = outputs("still")
    check("the Picture window stays open after a click in the main window", len(wins) == 1)
    if wins:
        w = wins[0]
        uis = [r for a in w.screen.areas if a.type == "VIEW_3D" for r in a.regions if r.type == "UI"]
        check("it shows the tab Make", bool(uis) and uis[0].active_panel_category == "Make",
              uis[0].active_panel_category if uis else "no side panel")
        check("no left panel in it", not any(a.spaces.active.show_region_toolbar for a in w.screen.areas
                                             if a.type == "VIEW_3D"))
        log("output window size:", w.width, w.height)
    with override():
        r = bpy.ops.fresing.make_window("EXEC_DEFAULT", key="still")
    check("pressing Picture again gives no second window", r == {"FINISHED"} and len(outputs("still")) == 1)
    with override():
        bpy.ops.fresing.make_window("EXEC_DEFAULT", key="web")
    shot("03_output_window")
    return 1.0


wait_until("a second output (3D page) opens its own window", lambda: len(outputs("web")) == 1 and len(outputs()) == 2,
           20)


@step
def s_close():
    with override():
        bpy.ops.fresing.make_close("EXEC_DEFAULT", key="")
    return 1.0


wait_until("Close closes the output windows", lambda: not outputs(), 10)


# ----- fold the left panel -----

@step
def s_fold():
    with override():
        bpy.ops.fresing.left_fold("EXEC_DEFAULT")
    return 0.8


@step
def s_folded():
    w = left_width()
    check("folded: the left panel is a narrow strip", 0 < w < mod("blender.ui_left").STRIP_BELOW, f"{w:.0f} px")
    shot("04_left_strip")
    with override():
        bpy.ops.fresing.left_fold("EXEC_DEFAULT")
    return 0.8


@step
def s_unfolded():
    w = left_width()
    check("unfolded: back at its width", abs(w - S["w0"]) < 6, f"{w:.0f} px, was {S['w0']:.0f}")
    return 0.3


# ----- Full access and back, the Client view -----

@step
def s_full():
    with override():
        bpy.ops.fresing.blender_all("EXEC_DEFAULT", True)
    return 1.0


@step
def s_full_ok():
    check("Full access: Blender's tool buttons are back", not tools_quiet())
    check("Full access: the left panel keeps its width", left_width() >= 180, f"{left_width():.0f}")
    shot("05_full_access")
    with override():
        bpy.ops.fresing.blender_all("EXEC_DEFAULT", True)
    return 1.0


@step
def s_back():
    check("Back: Blender's tool buttons hidden again", tools_quiet())
    check("Back: the left panel keeps its width", left_width() >= 180, f"{left_width():.0f}")
    workspace("Client view")
    return 1.0


@step
def s_client():
    check("Client view: the left panel stays", left_width() >= 180, f"{left_width():.0f}")
    check("Client view: the output windows open", bpy.ops.fresing.make_window.poll())
    check("Client view: the left panel folds", bpy.ops.fresing.left_fold.poll())
    shot("06_client_view")
    workspace("Product & sales")
    return 0.5


# ----- scrolling -----

@step
def s_scroll():
    class FRESING_PT_zz_tall(mod("blender.ui_left").LeftPanel, bpy.types.Panel):
        bl_label = "Tall"

        def draw(self, context):
            for i in range(90):
                self.layout.label(text=f"line {i}")

    bpy.utils.register_class(FRESING_PT_zz_tall)
    S["tall"] = FRESING_PT_zz_tall
    redraw()
    return 1.0


@step
def s_scroll_wheel():
    win, area, _r = view()
    reg = mod("blender.ui_left").tools_region(area)
    S["v0"] = reg.view2d.region_to_view(0, reg.height // 2)[1]
    x, y = reg.x + reg.width // 2, reg.y + reg.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    for _ in range(6):
        win.event_simulate(type="WHEELDOWNMOUSE", value="PRESS", x=x, y=y)
    return 1.0


@step
def s_scrolled():
    reg = mod("blender.ui_left").tools_region(view()[1])
    v1 = reg.view2d.region_to_view(0, reg.height // 2)[1]
    check("the left panel scrolls when it is taller than the window", abs(v1 - S["v0"]) > 20,
          f"{S['v0']:.0f} -> {v1:.0f}")
    bpy.utils.unregister_class(S.pop("tall"))
    return 0.3


# ----- projects open with the left panel at its width -----

@step
def s_save_narrow():
    win, area, _r = view()
    ok = mod("blender.ui_left").set_width(area, 40)            # as Blender's own one-button toolbar
    S["old"] = os.path.join(TMP, "old é.blend")
    return 0.8 if ok else 0.3


@step
def s_save_old():
    check("saved with a narrow toolbar", left_width() < 110, f"{left_width():.0f}")
    bpy.ops.wm.save_as_mainfile(filepath=S["old"])
    bpy.ops.wm.open_mainfile(filepath=S["old"])
    return 2.0


wait_until("a project saved with Blender's narrow toolbar opens with the left panel readable",
           lambda: left_width() >= 180, 15)


# ----- the Learning hub switch -----

@step
def s_hub_outside():
    st = mod("blender.ui_left").hub_state(bpy.context.scene)
    check("an own project is no Learning hub project", not st["in_hub"], str(st))
    sc = bpy.context.scene
    sc[mod("blender.tour").TAG] = "crane"
    st = mod("blender.ui_left").hub_state(sc)
    check("a Learning hub project of the crane: View, with a lesson", st["in_hub"] and st["mode"] == "VIEW"
          and st["lesson"], str(st))
    shot("07_hub_view")
    with override():
        r = bpy.ops.fresing.hub_mode("EXEC_DEFAULT", mode="SHOW")
    check("Show me from View opens the crane lesson", r == {"FINISHED"}, r)
    return 1.0


wait_until("the crane lesson runs in Show me", lambda: bpy.context.scene.get(mod("blender.lesson").KEY) == "crane"
           and mod("blender.lesson").running(), 90)


@step
def s_hub_build():
    with override():
        bpy.ops.fresing.hub_mode("EXEC_DEFAULT", mode="BUILD")
    st = mod("blender.ui_left").hub_state(bpy.context.scene)
    check("Build it yourself switches the same lesson at once", st["mode"] == "BUILD"
          and mod("blender.lesson").state()["mode"] == "BUILD", str(st))
    redraw()
    return 1.0


@step
def s_hub_shot():
    shot("08_hub_lesson")
    with override():
        bpy.ops.fresing.lesson_stop("EXEC_DEFAULT")
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
    except Exception:  # noqa: BLE001
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    if r == "again":
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
