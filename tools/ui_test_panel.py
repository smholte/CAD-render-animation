"""Real-app test, task 0062: the cleaner side panel.

The app starts with sections 1–7 folded and Blender's workspace tabs hidden; a title opens its section, Ctrl+click
keeps one open, a section tab shows one section; a workspace hides panels and keeps the work; a family in use asks
before it hides; an own workspace is a file a colleague's library folder can take; the Client view locks the project
(a click on a part selects nothing, Delete deletes nothing, the Outliner is replaced) and Full access undoes it; a
project saved by an older version opens folded, in the default workspace, with what it uses shown; the Make list opens
an output's settings as a popover.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_panel.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_panel)."""

import importlib
import os
import shutil
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_panel"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
GANTRY = os.path.join(HERE, "..", "tests", "data", "test_gantry.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_panel.log"), "w")
RESULTS = []
S = {"tmp": tempfile.mkdtemp(prefix="fr_panel_")}
SECTIONS = ("import", "structure", "looks", "motion", "scene", "animation", "queue")


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
    region = next(r for r in area.regions if r.type == "WINDOW")
    sb = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sb


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def redraw():
    win, area, region, _sb = ui()
    for a in win.screen.areas:
        a.tag_redraw()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 200 + int(time.time() * 10) % 9, y=region.y + 200)


def shot(name, crop=None):
    full = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", full], check=False)
    if crop:
        x, y, w, h = crop
        subprocess.run(["convert", full, "-crop", f"{w}x{h}+{x}+{y}", "+repage", full], check=False)
    return full


def top_bar_ink() -> int:
    """How much is written in the top bar right of the menus (Blender's workspace tabs are text there)."""
    win = bpy.context.window_manager.windows[0]
    full = os.path.join(OUT, "_bar.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    raw = subprocess.run(["convert", full, "-crop", f"{win.width - 700}x22+320+3", "+repage", "-colorspace", "Gray",
                          "-depth", "8", "gray:-"], capture_output=True, check=False).stdout
    return sum(1 for b in raw if b > 110)


def key(k, **mods):
    win, _area, region, _sb = ui()
    x, y = S.get("xy") or (region.x + region.width // 2, region.y + region.height // 2)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, **mods)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, **mods)


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


# ---- which panel bodies Blender really draws (a body is only drawn when its panel shows and is open) ----
DRAWN = {}


def watch(names):
    panels = mod("blender.panels")
    for name in names:
        cls = getattr(bpy.types, name)
        body = panels.body_of(cls)
        if getattr(body, "_counted", False):
            continue

        def counted(self, context, _body=body, _name=name):
            DRAWN[_name] = DRAWN.get(_name, 0) + 1
            return _body(self, context)
        counted._counted = True
        cls.draw = panels._make_draw(cls, counted)


def drawn(name):
    return DRAWN.get("FRESING_PT_" + name, 0)


def part_spot():
    """A window position where the view shows a part of the model (the boom's middle)."""
    from bpy_extras import view3d_utils
    win, area, region, _sb = ui()
    ob = next(o for o in bpy.context.scene.objects if o.get("fr_name") == "BOOM")
    from mathutils import Vector
    box = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    centre = sum(box, Vector()) / 8
    co = view3d_utils.location_3d_to_region_2d(region, region.data, centre)
    return int(region.x + co.x), int(region.y + co.y), ob


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_esc():
    bpy.context.preferences.system.use_region_overlap = False
    win, _area, region, _sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    return 0.4


@step
def s_esc2():
    win, _area, region, _sb = ui()
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 0.8


@step
def s_start():
    panels, workspaces, lock = mod("blender.panels"), mod("blender.workspaces"), mod("blender.lock")
    sc = bpy.context.scene
    _win, _area, _region, sb = ui()
    check("start: the side panel shows the Fresing tab", getattr(sb, "active_panel_category", "") == "Fresing")
    check("start: sections 1–7 are folded", not any(panels.is_open("FRESING_PT_" + s) for s in SECTIONS),
          str(sorted(panels.OPEN)))
    check("start: a new project is in the workspace All functions", workspaces.name_of(sc) == "All functions"
          and not lock.ON[0], sc.fresing.ws_name)
    check("start: Blender's own workspace tabs are hidden", lock.tabs_hidden())
    S["ink_hidden"] = top_bar_ink()
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="draft")
    return 1.0


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    watch(["FRESING_PT_" + n for n in SECTIONS + ("find", "cutaway", "cnc", "cables", "make", "camera")])
    redraw()
    return 1.0


@step
def s_folded():
    check("after the import every section is still folded: no section body is drawn",
          all(drawn(s) == 0 for s in SECTIONS), str({s: drawn(s) for s in SECTIONS}))
    check("the Make list above 1 Import is drawn", drawn("make") > 0)
    shot("1_folded")
    with override():
        bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", True, name="FRESING_PT_looks")
    redraw()
    return 1.0


@step
def s_opened():
    check("a click on the title opens 3 Looks: its body and its open sub-panel are drawn",
          drawn("looks") > 0 and drawn("find") > 0 and drawn("cutaway") == 0 and drawn("motion") == 0,
          str(DRAWN))
    with override():
        bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", True, name="FRESING_PT_scene")
        bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", True, name="FRESING_PT_motion", only=True)
    DRAWN.clear()
    redraw()
    return 1.0


@step
def s_only():
    check("Ctrl+click on 4 Motion: only that section stays open",
          drawn("motion") > 0 and drawn("looks") == 0 and drawn("scene") == 0, str(DRAWN))
    from_prefs = mod("blender.prefs").get()
    check("the Ctrl+click hint is not needed any more", from_prefs is None or from_prefs.knows_ctrl_click)
    bpy.context.window_manager.fresing_tab = "5"
    DRAWN.clear()
    redraw()
    return 1.0


@step
def s_tab():
    check("tab 5 shows only 5 Scene & Render, opened", drawn("scene") > 0 and drawn("camera") > 0
          and drawn("motion") == 0 and drawn("import") == 0, str(DRAWN))
    shot("2_tab5")
    bpy.context.window_manager.fresing_tab = "ALL"
    panels = mod("blender.panels")
    panels.open_all()
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Offshore & cable laying")
    DRAWN.clear()
    redraw()
    return 1.0


@step
def s_workspace():
    workspaces = mod("blender.workspaces")
    sc = bpy.context.scene
    check("workspace Offshore & cable laying: CNC machine hidden, Cables and paths shown",
          drawn("cnc") == 0 and drawn("cables") > 0 and drawn("motion") > 0, str(DRAWN))
    with override():
        bpy.ops.fresing.family_toggle("EXEC_DEFAULT", True, family="offshore")
    DRAWN.clear()
    redraw()
    return 1.0


@step
def s_family():
    workspaces, W = mod("blender.workspaces"), mod("core.workspaces")
    sc = bpy.context.scene
    check("family Cables, drums & sea ticked off: its panels are gone", drawn("cables") == 0 and drawn("motion") > 0
          and not workspaces.family_on(sc, "offshore"), str(DRAWN))
    # a family the project uses asks first (the question's text), and hiding keeps the work
    joints = mod("blender.joints")
    before = len(sc.objects)
    sc.fresing.cnc.x_joint = "X"
    uses = workspaces.in_use(sc).get("cnc", [])
    text = W.hide_warning("cnc", uses)
    check("hiding a family in use: the question names what is set up", "a CNC machine" in text
          and "only the panels are hidden" in text, text)
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
        bpy.ops.fresing.family_toggle("EXEC_DEFAULT", True, family="cnc")       # = Hide anyway
    check("Hide anyway hides it and keeps the work", not workspaces.family_on(sc, "cnc")
          and sc.fresing.cnc.x_joint == "X" and len(sc.objects) == before and workspaces.hidden_in_use(sc) == ["cnc"])
    with override():
        bpy.ops.fresing.workspace_show_used("EXEC_DEFAULT", True)
    check("Show what the project uses brings it back", workspaces.family_on(sc, "cnc"))
    sc.fresing.cnc.x_joint = ""
    del joints
    return 0.3


@step
def s_own():
    """An own workspace: one file; a colleague's library folder gets it by copying the file, then Refresh."""
    workspaces, prefs = mod("blender.workspaces"), mod("blender.prefs")
    sc = bpy.context.scene
    p = prefs.get()
    mine, theirs = os.path.join(S["tmp"], "my library"), os.path.join(S["tmp"], "colleague's library")
    os.makedirs(mine)
    os.makedirs(theirs)
    S["lib_before"] = p.library_path
    p.library_path = mine
    workspaces.forget_scan()
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=mod("core.workspaces").NAMES["cnc"])
        bpy.ops.fresing.family_toggle("EXEC_DEFAULT", True, family="web")
        res = bpy.ops.fresing.workspace_save("EXEC_DEFAULT", True, name="Mill demos", note="demo days")
    files = os.listdir(os.path.join(mine, "Workspaces")) if os.path.isdir(os.path.join(mine, "Workspaces")) else []
    check("Save as my own: one file in the library folder Workspaces", res == {"FINISHED"}
          and files == ["Mill demos.json"] and sc.fresing.ws_name == "Mill demos", str(files))
    p.library_path = theirs                                   # the colleague's PC
    workspaces.forget_scan()
    check("the colleague does not have it yet", not workspaces.is_own("Mill demos"))
    check("the project still shows the same without the file", not workspaces.family_on(sc, "web")
          and not workspaces.family_on(sc, "offshore") and workspaces.current(sc).name == "Mill demos")
    os.makedirs(os.path.join(theirs, "Workspaces"))
    shutil.copy(os.path.join(mine, "Workspaces", "Mill demos.json"), os.path.join(theirs, "Workspaces"))
    with override():
        bpy.ops.fresing.workspace_refresh("EXEC_DEFAULT", True)
    check("after copying the file and Refresh the colleague has it", workspaces.is_own("Mill demos")
          and any(n == "Mill demos" for n, _note, _own in workspaces.names()))
    with override():
        bpy.ops.fresing.workspace_rename("EXEC_DEFAULT", True, name="Mill demo days")
    check("Rename renames the file", os.listdir(os.path.join(theirs, "Workspaces")) == ["Mill demo days.json"]
          and sc.fresing.ws_name == "Mill demo days")
    with override():
        bpy.ops.fresing.workspace_delete("EXEC_DEFAULT", True)
    check("Delete deletes the file; the project keeps its copy", os.listdir(os.path.join(theirs, "Workspaces")) == []
          and not workspaces.family_on(sc, "web"))
    p.library_path = S["lib_before"]
    workspaces.forget_scan()
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    redraw()
    return 1.2


@step
def s_full_access():
    lock = mod("blender.lock")
    S["ink_shown"] = top_bar_ink()
    check("Full access shows Blender's workspace tabs again", not lock.tabs_hidden()
          and S["ink_shown"] > S["ink_hidden"] + 300, f"ink {S['ink_hidden']} -> {S['ink_shown']}")
    shot("3_full_access", (0, 0, 1800, 60))
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    redraw()
    return 1.2


@step
def s_client():
    lock, panels = mod("blender.lock"), mod("blender.panels")
    win, _area, _region, _sb = ui()
    sc = bpy.context.scene
    check("Client view: the lock is on, every object unclickable and locked in place",
          lock.ON[0] and all(o.hide_select and all(o.lock_location) for o in sc.objects))
    check("Client view: Blender's tabs are hidden again", lock.tabs_hidden() and top_bar_ink() < S["ink_shown"] - 300)
    check("Client view: an editing button is refused, looking and rendering still work",
          bpy.ops.fresing.group_add.poll() is False and bpy.ops.fresing.light_look.poll()
          and bpy.ops.fresing.render.poll())
    check("Client view: the Outliner is replaced", not any(a.type == "OUTLINER" for a in win.screen.areas)
          and any(a.type == "INFO" for a in win.screen.areas), str([a.type for a in win.screen.areas]))
    DRAWN.clear()
    panels.open_all()
    redraw()
    x, y, ob = part_spot()
    S["xy"] = (x, y)
    S["part"] = ob.name
    S["count"] = len(sc.objects)
    click(x, y)
    return 0.8


@step
def s_client_click():
    sc = bpy.context.scene
    check("Client view: the editing panels are gone, 5 Scene & Render is there",
          drawn("looks") == 0 and drawn("motion") == 0 and drawn("scene") > 0, str(DRAWN))
    check("Client view: a click on a part selects nothing", not bpy.context.selected_objects
          and bpy.context.view_layer.objects.active is None, str([o.name for o in bpy.context.selected_objects]))
    shot("4_client")
    key("DEL")
    return 0.5


@step
def s_client_keys():
    key("X")
    return 0.5


@step
def s_client_tab():
    key("TAB")
    return 0.8


@step
def s_client_after_keys():
    sc = bpy.context.scene
    check("Client view: Delete, X and Tab change nothing", len(sc.objects) == S["count"]
          and bpy.context.mode == "OBJECT" and S["part"] in sc.objects, f"{len(sc.objects)} objects, {bpy.context.mode}")
    path = os.path.join(S["tmp"], "client.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_client_reopened():
    lock, workspaces = mod("blender.lock"), mod("blender.workspaces")
    sc = bpy.context.scene
    check("a Client view project opens locked", lock.ON[0] and workspaces.name_of(sc) == "Client view"
          and all(o.hide_select for o in sc.objects))
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    redraw()
    return 1.0


@step
def s_unlocked():
    lock = mod("blender.lock")
    win, _area, _region, _sb = ui()
    sc = bpy.context.scene
    check("Full access undoes the lock: nothing carries its mark, editing works, the Outliner is back",
          not lock.ON[0] and lock.marked() == 0 and bpy.ops.fresing.group_add.poll()
          and any(a.type == "OUTLINER" for a in win.screen.areas), str([a.type for a in win.screen.areas]))
    x, y, _ob = part_spot()
    click(x, y)
    return 0.8


@step
def s_unlocked_click():
    check("after the unlock a click on a part selects it again", len(bpy.context.selected_objects) >= 1)
    # ---- a project saved by a version before workspaces: default workspace + what it uses, sections folded ----
    workspaces, panels = mod("blender.workspaces"), mod("blender.panels")
    sc = bpy.context.scene
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
    sc.fresing.cnc.x_joint = "X"
    sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks, sc.fresing.panels_open = "", "", "", ""
    panels.open_all()
    p = mod("blender.prefs").get()
    S["default_before"] = p.default_workspace
    p.default_workspace = "Offshore & cable laying"
    path = os.path.join(S["tmp"], "old project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_old_project():
    workspaces, panels = mod("blender.workspaces"), mod("blender.panels")
    sc = bpy.context.scene
    p = mod("blender.prefs").get()
    _win, _area, _region, sb = ui()
    check("an older project opens in the default workspace with what it uses shown",
          sc.fresing.ws_name == "Offshore & cable laying" and workspaces.family_on(sc, "cnc")
          and workspaces.hidden_in_use(sc) == [], f"{sc.fresing.ws_name} {sc.fresing.ws_ticks}")
    check("an older project opens with sections 1–7 folded, on the Fresing tab",
          not any(panels.is_open("FRESING_PT_" + s) for s in SECTIONS)
          and getattr(sb, "active_panel_category", "") == "Fresing", str(sorted(panels.OPEN)))
    p.default_workspace = S["default_before"]
    # ---- "Keep sections as I left them" ----
    p.keep_sections = True
    panels.open_to("FRESING_PT_cutaway")
    path = os.path.join(S["tmp"], "kept.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    panels.fold_sections()
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_kept():
    panels = mod("blender.panels")
    p = mod("blender.prefs").get()
    check("Keep sections as I left them: the project opens with what was open",
          panels.is_open("FRESING_PT_looks") and panels.is_open("FRESING_PT_cutaway"))
    p.keep_sections = False
    panels.fold_sections()
    # ---- Make: an output's own settings as a popover, also from the 3D view's header ----
    ui_top = mod("blender.ui_top")
    check("Make is in the 3D view's header",
          ui_top._draw_view_header in bpy.types.VIEW3D_HT_header.draw._draw_funcs)
    cls = bpy.types.FRESING_PT_make_still
    body = cls.draw

    def counted(self, context):
        DRAWN["make_still"] = DRAWN.get("make_still", 0) + 1
        return body(self, context)
    cls.draw = counted
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 400, y=region.y + 400)
    with override():
        bpy.ops.wm.call_panel("INVOKE_DEFAULT", name="FRESING_PT_make_still", keep_open=True)
    return 1.2


@step
def s_make():
    check("Make > Picture opens Image size & render as a popover although 5 Scene & Render is folded",
          DRAWN.get("make_still", 0) > 0, str(DRAWN.get("make_still", 0)))
    shot("5_make_popover")
    win, _area, region, _sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 30, y=region.y + 30)
    return 0.4


@step
def s_make_closed():
    win, _area, region, _sb = ui()
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 30, y=region.y + 30)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 60, y=region.y + 60)
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    shutil.rmtree(S["tmp"], ignore_errors=True)
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_w = [0.0]


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
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 300:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
