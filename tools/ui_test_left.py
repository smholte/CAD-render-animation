"""Real-app test, two panels (task 0260): the left panel in the 3D view's toolbar region – Live preview + Build & play,
update notice, Workspace, Learning hub, Favourites, What's next – at a readable width without Blender's tool buttons;
it folds to a strip with Live preview and Build & play and opens again; Full access brings Blender's tools back above
it; it keeps its width when projects open (an old one saved with a narrow toolbar, a Learning hub one) and in the
Client view; it scrolls. On the right Make is one row of icons (or the labelled list); each output opens a window of
its own that stays open when the main window is clicked, a second press gives no second window, Close closes it. The
Learning hub switch: outside a hub project it opens the Learn window; in a hub project (the crane) Show me opens the
lesson, Build it yourself switches the same lesson at once. Task 0278: the crane lesson's Build & play step points at
the left panel's button (open, and the strip's icon when folded); Favourites, Learning hub and Workspace fold with
their arrows and keep it through a real restart (a second app, ``ui_test_left_restart.py``, in the same settings
folder). Task 0308: each output window has a strip of every output on its left (one icon wide, the names when it is
dragged wider; Blender's tool buttons and its tabs Tool / View / Animation not there), its buttons switch the window;
Render this view saves a picture and leaves no camera behind. Screenshots: left + right panel at the screen's size.

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


def guide_crop(path, name, height=330):
    """Task 0260: the left panel's top as a user guide picture (GUIDE_OUT set: docs/img), cut from a screenshot."""
    out = os.environ.get("GUIDE_OUT")
    if not out:
        return
    win, area, _r = view()
    reg = mod("blender.ui_left").tools_region(area)
    top = win.height - (reg.y + reg.height)
    h = min(int(height * (bpy.context.preferences.system.ui_scale or 1.0)), reg.height)
    subprocess.run(["convert", path, "-crop", f"{reg.width}x{h}+{reg.x}+{top}", "+repage",
                    os.path.join(out, name + ".png")], check=False)


def window_crop(path, name, win, height=300):
    """Task 0308: an output window's top as a user guide picture (GUIDE_OUT set: docs/img)."""
    out = os.environ.get("GUIDE_OUT")
    if not out:
        return
    top = main_win().height - (win.y + win.height)
    h = min(int(height * (bpy.context.preferences.system.ui_scale or 1.0)), win.height)
    subprocess.run(["convert", path, "-crop", f"{win.width}x{h}+{win.x}+{top}", "+repage",
                    os.path.join(out, name + ".png")], check=False)


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
    order = [c.__name__ for c in mod("")._all_classes() if getattr(c, "bl_region_type", "") == "TOOLS"
             and getattr(c, "bl_space_type", "") == "VIEW_3D"      # task 0272: not the file browser's STEP folders
             and c.__name__ not in ("FRESING_PT_settings_window",   # task 0271: shows only in the Settings window
                                    "FRESING_PT_form_window",        # task 0282: only in a function window
                                    "FRESING_PT_first_setup",        # task 0276: only in the set-up window
                                    "FRESING_PT_make_strip",         # task 0308: only in an output window
                                    "FRESING_PT_materials_window")]  # task 0273: only in the Materials window
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
    data = os.path.join(os.path.dirname(mod("").__file__), "data", "test_crane_a.step")
    with override():
        r = bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=data)
    log("import:", r)
    return 1.0


wait_until("the crane is imported", lambda: bpy.context.scene.fresing.model_count > 0, 120)


@step
def s_make_row():
    redraw()
    guide_crop(shot("02_crane_two_panels"), "left_panel")
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
        log("output window size:", w.width, w.height)
    with override():
        r = bpy.ops.fresing.make_window("EXEC_DEFAULT", key="still")
    check("pressing Picture again gives no second window", r == {"FINISHED"} and len(outputs("still")) == 1)
    return 1.0


def _strip():
    w = outputs()
    return mod("blender.ops_make").strip_width(w[0]) if w else 0.0


wait_until("task 0308: the outputs strip on the window's left, one icon wide", lambda: 30 < _strip() < 70, 15)


@step
def s_strip():
    w = outputs()[0]
    om = mod("blender.ops_make")
    area = om._view_area(w)
    sp = area.spaces.active
    check("the settings still show beside the strip", sp.show_region_ui and om._region(area, "UI").width > 200,
          f"side panel {om._region(area, 'UI').width} px, strip {_strip():.0f} px, window {w.width} px")
    S["view_beside"] = area.width - om._region(area, "UI").width - om._region(area, "TOOLS").width
    check("no empty 3D view beside the strip and the settings", S["view_beside"] <= 16, f"{S['view_beside']} px")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=om._region(area, "TOOLS")):
        quiet = not bpy.types.VIEW3D_PT_tools_active.poll(bpy.context)
        mine = bpy.types.FRESING_PT_make_strip.poll(bpy.context)
        left = [n for n in mod("blender.panels").LEFT if getattr(bpy.types, n).poll(bpy.context)]
    check("Blender's tool buttons are not in the strip", quiet)
    check("the strip shows the outputs, no left panel", mine and not left, ", ".join(left))
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=om._region(area, "UI")):
        shown = [c.__name__ for c in mod("blender.ops_settings").tab_panels() if c.poll(bpy.context)]
    check("Blender's tabs Tool, View, Animation hidden in the window", not shown, ", ".join(shown))
    redraw()
    return 0.8


@step
def s_strip_shot():
    w = outputs()[0]
    window_crop(shot("03a_output_strip_narrow"), "make_strip_narrow", w)
    om = mod("blender.ops_make")
    with bpy.context.temp_override(window=w, screen=w.screen, area=om._view_area(w)):
        r = bpy.ops.fresing.make_switch("EXEC_DEFAULT", key="web")
    check("a strip button switches the window to the 3D page", r == {"FINISHED"} and len(outputs()) == 1
          and len(outputs("web")) == 1, r)
    redraw()
    return 1.0


@step
def s_strip_widen():
    w = outputs()[0]
    om = mod("blender.ops_make")
    shot("03a2_web_narrow")
    log("tab:", om._region(om._view_area(w), "UI").active_panel_category)
    ok = mod("blender.ui_left").set_width(om._view_area(w), 150)     # as the user drags the strip wider
    check("the strip can be made wider", ok)
    return 0.8


def _settings_fill():
    w = outputs()
    if not w:
        return False
    om = mod("blender.ops_make")
    area = om._view_area(w[0])
    side, tools = om._region(area, "UI"), om._region(area, "TOOLS")
    S["fill"] = f"strip {tools.width} px, settings {side.width} px, view {area.width} px"
    return side.width > 150 and abs(area.width - tools.width - side.width - om.FILL_GAP) <= om.FILL_SLACK + 4


wait_until("the wider strip shows the names", lambda: _strip() >= mod("blender.ops_make").NAMES_FROM, 10)
wait_until("… and the settings shrink to the rest of the window (still shown)", _settings_fill, 10)


@step
def s_strip_wide_draw():
    log("wide strip:", S.get("fill"))
    redraw()
    return 1.0


@step
def s_strip_wide():
    w = outputs()[0]
    window_crop(shot("03b_output_strip_wide"), "make_strip_wide", w)
    om = mod("blender.ops_make")
    side = om._region(om._view_area(w), "UI")
    log("tab:", side.active_panel_category, side.x, side.y, side.width, side.height, side.view2d.region_to_view(0, side.height - 1))
    x, y = side.x + side.width // 2, side.y + side.height // 2
    w.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    return 2.0


@step
def s_strip_wide2():
    shot("03c_output_strip_wide_later")
    w = outputs()[0]
    om = mod("blender.ops_make")
    side = om._region(om._view_area(w), "UI")
    log("tab later:", side.width, side.view2d.region_to_view(0, side.height - 1))
    w = outputs()[0]
    om = mod("blender.ops_make")
    with bpy.context.temp_override(window=w, screen=w.screen, area=om._view_area(w)):
        r = bpy.ops.fresing.make_switch("EXEC_DEFAULT", key="still")
    check("… and back to the Picture", r == {"FINISHED"} and len(outputs("still")) == 1 and len(outputs()) == 1)
    with override():
        bpy.ops.fresing.make_window("EXEC_DEFAULT", key="web")
    return 1.0


wait_until("a second output (3D page) opens its own window", lambda: len(outputs("web")) == 1 and len(outputs()) == 2,
           20)


@step
def s_close():
    redraw()
    shot("03_output_windows")
    w = outputs("web")
    if w:
        log("3D page window:", w[0].x, w[0].y, w[0].width, w[0].height)
    with override():
        bpy.ops.fresing.make_close("EXEC_DEFAULT", key="")
    return 1.0


wait_until("Close closes the output windows", lambda: not outputs(), 10)


# ----- task 0308: Render this view -----

def _things():
    sc = bpy.context.scene
    return (sc.camera.name if sc.camera else "", len(bpy.data.objects), len(bpy.data.cameras))


@step
def s_render_view():
    sc = bpy.context.scene
    s = sc.fresing
    s.out_format, s.out_custom_w, s.out_custom_h, s.quality, s.use_gpu = "custom", 160, 90, "draft", False
    S["before_view"] = _things()
    S["last"] = s.last_render
    with override():
        r = bpy.ops.fresing.render_view("EXEC_DEFAULT", True)
    check("Render this view starts", r == {"RUNNING_MODAL"} or r == {"FINISHED"}, r)
    return 1.0


wait_until("Render this view saves the picture", lambda: (not bpy.app.is_job_running("RENDER"))
           and "_View_" in os.path.basename(bpy.context.scene.fresing.last_render)
           and os.path.isfile(bpy.context.scene.fresing.last_render), 240)


@step
def s_render_view_done():
    check("Render this view leaves no camera and the active camera as it was", _things() == S["before_view"],
          f"{_things()} / {S['before_view']}")
    for win in list(bpy.context.window_manager.windows):        # Blender's render window: closed again
        if win.screen is not None and any(a.type == "IMAGE_EDITOR" for a in win.screen.areas) and win != main_win():
            with bpy.context.temp_override(window=win):
                bpy.ops.wm.window_close()
    return 1.0


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
    workspace("All functions")
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
    redraw()
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
    guide_crop(shot("08_hub_lesson"), "left_hub", 400)
    les = mod("blender.lesson")
    S["build_at"] = next(i for i, st in enumerate(les.LESSONS["crane"].steps) if st.function == "animation.build")
    with override():
        les.start(bpy.context.scene, "crane", "BUILD", at=S["build_at"])      # task 0278: the Build & play step
    redraw()
    return 1.0


def _left_target():
    h = mod("blender.highlight")
    t = h._S["target"] or {}
    return t.get("panel") == "FRESING_PT_left_quick" and t.get("button") == "fresing.anim_build" \
        and bool(h.found().get("button"))


wait_until("the crane lesson's Build step points at Build & play on the left panel", _left_target, 30)


@step
def s_lesson_strip():
    check("the lesson waits at its Build & play step",
          mod("blender.lesson").state()["step"] == S["build_at"], str(mod("blender.lesson").state()))
    shot("09_lesson_build_left")
    with override():
        bpy.ops.fresing.left_fold("EXEC_DEFAULT")
    mod("blender.highlight")._S["seen"] = {}            # what the next redraw of the strip sees
    redraw()
    return 1.0


wait_until("folded to the strip: the lesson points at the strip's Build & play icon",
           lambda: mod("blender.ui_left").folded() and _left_target(), 20)


@step
def s_lesson_unfold():
    shot("10_lesson_build_strip")
    with override():
        bpy.ops.fresing.left_fold("EXEC_DEFAULT")
        bpy.ops.fresing.lesson_stop("EXEC_DEFAULT")
    return 0.8


# ----- task 0278: Favourites folds, and every left section keeps its fold after a restart -----

LEFT_FOLDS = ("FRESING_PT_favourites", "FRESING_PT_hub", "FRESING_PT_workspace")


@step
def s_fav_pin():
    us = mod("blender.usage")
    S["pinned"] = "scene.still" not in us.state()["bar"]["pins"]
    if S["pinned"]:
        us.pin("scene.still", True)
    panels = mod("blender.panels")
    S["was_open"] = {n: panels.is_open(n) for n in LEFT_FOLDS}
    with override():
        check("the favourites bar shows (a pin)", bpy.types.FRESING_PT_favourites.poll(bpy.context))
    redraw()
    return 0.8


@step
def s_fav_fold():
    guide_crop(shot("11_favourites_open"), "usage_bar", 330)
    panels = mod("blender.panels")
    with override():
        for n in LEFT_FOLDS:                      # as the arrow in each title row: fold what is open, open the rest
            bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", name=n)
        bpy.ops.fresing.next_fold("EXEC_DEFAULT")        # What's next: its own arrow (task 0260), kept the same way
    S["want"] = {n: not S["was_open"][n] for n in LEFT_FOLDS}
    S["next_folded"] = mod("blender.ui_left").next_folded()
    check("Favourites folds with its arrow", panels.is_open("FRESING_PT_favourites") == S["want"][
        "FRESING_PT_favourites"] and not S["want"]["FRESING_PT_favourites"], str(S["want"]))
    kept = mod("blender.ui_left").store()
    check("the folds are written to the user's settings file", kept.get("open") == S["want"]
          and kept.get("next_folded") == S["next_folded"], str(kept))
    redraw()
    return 0.8


@step
def s_restart():
    shot("12_favourites_folded")
    out = os.path.join(TMP, "restart.json")
    env = dict(os.environ, FR_LEFT_RESTART_OUT=out, UITEST_OUT=os.path.join(OUT, "restart"))
    child = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_test_left_restart.py")
    t = time.time()
    try:
        subprocess.run([bpy.app.binary_path, "--app-template", "fresing_render", "--enable-event-simulate",
                        "-p", "0", "0", "1280", "900", "--python", child], env=env, timeout=240, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log("the restarted app did not finish in 240 s")
    import json
    try:
        got = json.load(open(out, encoding="utf-8"))
    except (OSError, ValueError):
        got = {}
    log(f"restarted app ({time.time() - t:.0f} s):", got)
    for n in LEFT_FOLDS:
        check(f"after a restart {n[11:]} is {'open' if S['want'][n] else 'folded'} as left",
              n in got.get("open", {}) and got["open"][n] == S["want"][n], str(got.get("open")))
    check("after a restart What's next is as left", got.get("next_folded") == S["next_folded"],
          f"{got.get('next_folded')}, left {S['next_folded']}")
    check("after a restart the Favourites header still shows (the pin)", got.get("favourites_poll") is True,
          str(got.get("favourites_poll")))
    return 0.3


@step
def s_fav_back():
    """Put everything back: the next real-app test in this settings folder starts as before (CLAUDE.md 8)."""
    with override():
        for n in LEFT_FOLDS:
            bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", name=n)
        bpy.ops.fresing.next_fold("EXEC_DEFAULT")
    if S.get("pinned"):
        mod("blender.usage").pin("scene.still", False)
    mod("blender.ui_left").store_set(open={})
    return 0.3


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
