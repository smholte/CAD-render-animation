"""Real-app test, shorter top-bar menus and Blender's side-panel tabs (task 0367, study 0222 package C).

Outside Full access: File, Render, Window and Help are the quiet ones (their draws counted), Help's sub-menu "Blender"
opens with Blender's own lines; Blender's tabs Tool, View, Animation, Item (also with a part selected – its Transform
panel is C code, hidden through its poll) and glTF Variants are gone from the side panel, another add-on's tab still
shows and is drawn, the Fresing tab stays in front after selecting a part. Fresing > Show all of Blender brings
Blender's menus and tabs back (the Item tab can be chosen again), Back hides them again. The Client view keeps its own
File menu and greys the Keys tab's "Blender's own key settings". A screenshot of each menu and of the side panel.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_menus.py
Screenshots and ui_test_menus.log go to $UITEST_OUT (default ~/fresing_ui_test_menus).
"""

import os
import subprocess
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_menus"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_menus.log"), "w")
RESULTS = []
STATE = {}
COUNT = {"other": 0}
OTHER_TAB = "Other add-on"


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


def view():
    win = win0()
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def side():
    win, area, _r = view()
    return next(r for r in area.regions if r.type == "UI")


def override(region=None):
    win, area, reg = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region or reg, scene=win.scene)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def can_pick(tab: str) -> bool:
    """Can the side panel's tab be chosen? (Blender refuses a tab that is not shown.)"""
    with override(side()):
        try:
            side().active_panel_category = tab
            return True
        except (TypeError, AttributeError):
            return False


def esc():
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)


def open_menu(name):
    with override():
        bpy.ops.wm.call_menu(name=name)


def workspace(name):
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=name)


def show_all():
    with override():
        return bpy.ops.fresing.blender_all("EXEC_DEFAULT", True)


class FR_TEST_PT_other(bpy.types.Panel):
    """Another add-on's panel in a tab of its own: it must still show."""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = OTHER_TAB
    bl_label = "Other add-on"

    def draw(self, context):
        COUNT["other"] += 1
        self.layout.label(text="another add-on")


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("the extension is on", pkg() is not None)
    q = mod("blender.quiet")
    check("the window is quiet at the start", q.ON[0])
    esc()                                                     # the splash
    view_prefs = bpy.context.preferences.view                 # no tooltip over the menus' pictures (put back at
    STATE["tooltips"] = view_prefs.show_tooltips              # the end: Blender saves preferences when it closes)
    view_prefs.show_tooltips = False
    bpy.utils.register_class(FR_TEST_PT_other)
    me = bpy.data.meshes.new("Menu test part")
    me.from_pydata([(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new("Menu test part", me)
    bpy.context.scene.collection.objects.link(ob)
    STATE["part"] = ob.name
    _w, area, _r = view()
    area.spaces.active.show_region_ui = True
    redraw()
    return 1.5


@step
def s_select():
    ob = bpy.data.objects[STATE["part"]]
    with override():
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
    can_pick("Fresing")
    redraw()
    return 1.0


@step
def s_tabs_quiet():
    p = mod("blender.panels")
    check("Blender's Transform panel (C code) found", bool(p.C_PANEL["transform"]), str(p.C_PANEL))
    check("... and hidden while quiet", p.c_panels_hidden())
    check("a part is selected and active", bpy.context.view_layer.objects.active is not None
          and bpy.context.view_layer.objects.active.name == STATE["part"])
    check("the Fresing tab stays in front after selecting a part", side().active_panel_category == "Fresing",
          side().active_panel_category)
    for tab in ("Item", "Tool", "View", "Animation"):
        check(f"Blender's tab {tab} cannot be chosen (hidden)", not can_pick(tab))
    shot("sidebar_part_selected")
    check(f"another add-on's tab '{OTHER_TAB}' still shows", can_pick(OTHER_TAB))
    STATE["other"] = COUNT["other"]
    redraw()
    return 0.8


@step
def s_other_drawn():
    check("... and its panel is drawn", COUNT["other"] > STATE["other"], str(COUNT))
    can_pick("Fresing")
    redraw()
    return 0.5


MENUS = (("TOPBAR_MT_file", "file"), ("TOPBAR_MT_render", "render"), ("TOPBAR_MT_window", "window"),
         ("TOPBAR_MT_help", "help"))


def _menu_steps(cls_name, key):
    def open_it():
        STATE[key] = mod("blender.quiet").DRAWN[key]
        open_menu(cls_name)
        return 0.8

    def judge():
        q = mod("blender.quiet")
        check(f"the quiet {cls_name[10:].title()} menu is drawn", q.DRAWN[key] > STATE[key], str(q.DRAWN))
        shot("menu_" + key)
        esc()
        return 0.5
    open_it.__name__, judge.__name__ = "s_open_" + key, "s_judge_" + key
    STEPS.append(open_it)
    STEPS.append(judge)


for _c, _k in MENUS:
    _menu_steps(_c, _k)


@step
def s_help_line_last():
    q = mod("blender.quiet")
    funcs = bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
    check("Help's sub-menu Blender is the last line", funcs[-1] is q._help_blender_line,
          str([getattr(f, "__name__", "") for f in funcs]))
    STATE["hb"] = q.DRAWN["help_blender"]
    open_menu(q.HELP_MENU)
    return 0.8


@step
def s_help_blender():
    q = mod("blender.quiet")
    check("the sub-menu Blender opens (Blender's help lines)", q.DRAWN["help_blender"] > STATE["hb"], str(q.DRAWN))
    shot("menu_help_blender")
    esc()
    check("Show all of Blender runs", "FINISHED" in show_all())
    redraw()
    return 1.5


@step
def s_loud():
    q, p = mod("blender.quiet"), mod("blender.panels")
    check("Full access: Blender's own drawing", not q.ON[0])
    check("Full access: Blender's Transform panel back", not p.c_panels_hidden())
    check("Full access: the Item tab can be chosen again", can_pick("Item"))
    check("Full access: the View tab can be chosen again", can_pick("View"))
    shot("sidebar_full_access")
    can_pick("Fresing")
    STATE["file"] = q.DRAWN["file"]
    open_menu("TOPBAR_MT_file")
    return 0.8


@step
def s_loud_file():
    q = mod("blender.quiet")
    check("Full access: File is Blender's own (the quiet one not drawn)", q.DRAWN["file"] == STATE["file"],
          str(q.DRAWN))
    shot("menu_file_full_access")
    esc()
    funcs = bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
    check("Full access: no sub-menu Blender in Help", q._help_blender_line not in funcs)
    check("Back to the Fresing window runs", "FINISHED" in show_all())
    redraw()
    return 1.5


@step
def s_back():
    q, p = mod("blender.quiet"), mod("blender.panels")
    check("back: quiet again", q.ON[0])
    check("back: Blender's Transform panel hidden again", p.c_panels_hidden())
    check("back: the Item tab cannot be chosen", not can_pick("Item"))
    check("back: another add-on's tab still shows", can_pick(OTHER_TAB))
    can_pick("Fresing")
    workspace("Client view")
    redraw()
    return 1.0


@step
def s_client():
    q = mod("blender.quiet")
    with override():
        check("Client view: Blender's own key settings greyed", not bpy.ops.fresing.keys_blender.poll())
        desc = bpy.ops.fresing.keys_blender.get_rna_type().description
    keys = mod("blender.keys")
    check("... with a tooltip that says why", "Client view" in keys.FRESING_OT_keys_blender.description(
        bpy.context, None), desc)
    STATE["file"] = q.DRAWN["file"]
    open_menu("TOPBAR_MT_file")
    return 0.8


@step
def s_client_file():
    q = mod("blender.quiet")
    check("Client view: its own File menu (not the quiet one)", q.DRAWN["file"] == STATE["file"], str(q.DRAWN))
    shot("menu_file_client")
    esc()
    workspace("Full access")
    workspace("All functions")
    return 0.8


@step
def s_finish():
    with override():
        check("out of the Client view: Blender's key settings can be opened", bpy.ops.fresing.keys_blender.poll())
    bpy.context.preferences.view.show_tooltips = STATE.get("tooltips", True)
    try:
        bpy.utils.unregister_class(FR_TEST_PT_other)
    except RuntimeError:
        pass
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
