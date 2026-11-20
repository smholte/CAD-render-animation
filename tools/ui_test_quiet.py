"""Real-app test, a quiet window (task 0241): outside Full access the 3D view header shows only View, gizmos, overlays,
X-ray, shading and the app's Make / Fresing buttons, no tool header row, no Scene / View Layer selectors in the top bar,
the splash shows Fresing's lines, File > New and Ctrl+N give only New project (mm, Cycles, the app's layout). Fresing >
Show all of Blender / Back to the Fresing window and Workspace > Full access bring everything back and away again,
repeatedly, with the previous workspace restored; greyed in the Client view; Edit Mode keeps Blender's header; a dummy
add-on's appended items are drawn throughout; patch / unpatch / patch is clean; projects of every kind open quiet. The
header width freed is measured from screenshots (px).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_quiet.py
Screenshots and ui_test_quiet.log go to $UITEST_OUT (default ~/fresing_ui_test_quiet).
"""

import os
import subprocess
import tempfile
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_quiet"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_quiet.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_quiet é ")
STATE = {}
COUNT = {"header": 0, "splash": 0, "topbar": 0, "file_new": 0}


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
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


# a second add-on's items: drawn whatever the app does to Blender's own drawing
def _dummy_header(self, context):
    COUNT["header"] += 1
    self.layout.label(text="", icon="FUND")


def _dummy_splash(self, context):
    COUNT["splash"] += 1


def _dummy_topbar(self, context):
    COUNT["topbar"] += 1


def _dummy_file_new(self, context):
    COUNT["file_new"] += 1


DUMMIES = (("VIEW3D_HT_header", _dummy_header), ("WM_MT_splash", _dummy_splash),
           ("TOPBAR_HT_upper_bar", _dummy_topbar), ("TOPBAR_MT_file_new", _dummy_file_new))


def tool_headers():
    return [a.spaces.active.show_region_tool_header for a in win0().screen.areas if a.type == "VIEW_3D"]


def header_empty_px(path):
    """Columns of the main 3D view's header that hold nothing (header colour from top to bottom)."""
    import numpy as np
    _win, area, _r = view()
    head = next(r for r in area.regions if r.type == "HEADER")
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[:, :, :3]            # rows from the bottom, as Blender's region y
    y0, y1 = head.y + 3, head.y + head.height - 3
    x0, x1 = head.x + 2, head.x + head.width - 2
    strip = px[y0:y1, x0:x1]
    flat = strip.reshape(-1, 3)
    vals, counts = np.unique(np.round(flat, 3), axis=0, return_counts=True)
    bg = vals[np.argmax(counts)]
    used = (np.abs(strip - bg).max(axis=2) > 0.02).any(axis=0)
    return int((~used).sum()), int(head.width)


def workspace(name):
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name=name)


def show_all():
    with override():
        return bpy.ops.fresing.blender_all("EXEC_DEFAULT", True)


def quiet_ok(tag, quiet=True):
    q, lock = mod("blender.quiet"), mod("blender.lock")
    if quiet:
        check(tag + ": quiet window on, Blender's tabs hidden", q.ON[0] and lock.tabs_hidden())
        check(tag + ": no tool header row", not any(tool_headers()), str(tool_headers()))
        check(tag + ": top bar without Scene / View Layer", bpy.types.TOPBAR_HT_upper_bar.draw_right is q._draw_right)
    else:
        check(tag + ": Blender's own drawing, tabs shown", not q.ON[0] and not lock.tabs_hidden())
        check(tag + ": top bar with Scene / View Layer", bpy.types.TOPBAR_HT_upper_bar.draw_right is not q._draw_right)


def lists_ok(tag):
    """Make, the Fresing button, the welcome box and the dummy add-on's items still in their draw lists."""
    q, ui_top, ui_header, welcome = (mod("blender.quiet"), mod("blender.ui_top"), mod("blender.ui_header"),
                                     mod("blender.welcome"))
    head = q.draw_funcs(bpy.types.VIEW3D_HT_header)
    names = [getattr(f, "__qualname__", "") for f in head]
    check(tag + ": header keeps Make, Fresing and the dummy add-on",
          ui_header._draw_header in head and _dummy_header in head
          and any("ui_top" in getattr(f, "__module__", "") for f in head), str(names))
    own = [f for f in head if getattr(f, "__qualname__", "") in ("VIEW3D_HT_header.draw", "_header")]
    check(tag + ": one drawing of Blender's part in the header", len(own) == 1, str(names))
    splash = q.draw_funcs(bpy.types.WM_MT_splash)
    check(tag + ": splash keeps the welcome box on top and the dummy", splash[0] is welcome._draw_splash
          and _dummy_splash in splash, str([getattr(f, "__qualname__", "") for f in splash]))
    return [f.__qualname__ for f in head]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("the extension is on", pkg() is not None)
    for cls_name, fn in DUMMIES:
        getattr(bpy.types, cls_name).append(fn)
    quiet_ok("app start")
    STATE["order"] = lists_ok("app start")
    q = mod("blender.quiet")
    check("the splash at the start is the quiet one", q.DRAWN["splash"] > 0, str(q.DRAWN))
    win, area, _r = view()                                     # close it: simulated keys reach nothing under it
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    redraw()
    return 1.0


@step
def s_drawn():
    q = mod("blender.quiet")
    check("the quiet header is drawn", q.DRAWN["header"] > 0, str(q.DRAWN))
    STATE["quiet_px"] = header_empty_px(shot("01_quiet_header"))
    log("empty header px (quiet):", STATE["quiet_px"])
    STATE["fn"] = q.DRAWN["file_new"]
    win, area, _r = view()
    x, y = area.x + area.width // 3, area.y + area.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="N", value="PRESS", x=x, y=y, ctrl=True)
    win.event_simulate(type="N", value="RELEASE", x=x, y=y, ctrl=True)
    return 0.8


@step
def s_ctrl_n_open():
    q = mod("blender.quiet")
    check("... and the dummy add-on's header and top-bar items with it", COUNT["header"] > 0 and COUNT["topbar"] > 0,
          str(COUNT))
    shot("02_ctrl_n")
    check("Ctrl+N opens the New list: New project only", q.DRAWN["file_new"] > STATE["fn"], str(q.DRAWN))
    check("... the dummy add-on's File > New item too", COUNT["file_new"] > 0, str(COUNT))
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 200, y=area.y + 200)
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 200, y=area.y + 200)
    return 0.6


@step
def s_splash():
    with override():
        bpy.ops.wm.splash("INVOKE_DEFAULT")
    return 1.0


@step
def s_splash_open():
    q = mod("blender.quiet")
    check("the splash shows Fresing's lines", q.DRAWN["splash"] > 0, str(q.DRAWN))
    check("... the dummy add-on's splash item still drawn", COUNT["splash"] > 0, str(COUNT))
    lines = q.splash_lines()
    check("... New project, Open, Recover, the tour, the demo, the guide",
          lines[:3] == ["wm.read_homefile", "wm.open_mainfile", "wm.recover_last_session"]
          and "fresing.tour_take" in lines and "fresing.demo_make" in lines and "fresing.user_guide" in lines,
          str(lines))
    shot("03_splash")
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    return 0.6


@step
def s_new_project():
    q = mod("blender.quiet")
    bpy.context.scene.unit_settings.length_unit = "METERS"
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.ops.wm.read_homefile(app_template=q.template())       # the line New project: as a fresh start
    return 2.0


@step
def s_new_project_ok():
    sc = bpy.context.scene
    check("New project: millimetres", sc.unit_settings.length_unit == "MILLIMETERS", sc.unit_settings.length_unit)
    check("New project: Cycles", sc.render.engine == "CYCLES", sc.render.engine)
    _w, area, _r = view()
    sp = area.spaces.active
    ui = next(r for r in area.regions if r.type == "UI")
    check("New project: the app's layout (side panel on the Fresing tab, toolbar folded)",
          sp.show_region_ui and not sp.show_region_toolbar and ui.active_panel_category == "Fresing",
          ui.active_panel_category)
    quiet_ok("New project")
    workspace("Product design & R&D")                          # the workspace Show all of Blender comes from
    return 0.6


@step
def s_show_all():
    q = mod("blender.quiet")
    check("the Fresing menu has Show all of Blender",
          "fresing.blender_all" in mod("blender.ui_topbar").entries() and q.menu_text() == q.SHOW_TEXT,
          q.menu_text())
    check("Show all of Blender runs", "FINISHED" in show_all())
    return 1.0


@step
def s_all_shown():
    q, ws = mod("blender.quiet"), mod("blender.workspaces")
    quiet_ok("Show all of Blender", quiet=False)
    check("... workspace Full access", ws.name_of(bpy.context.scene) == "Full access", ws.name_of(bpy.context.scene))
    check("... the tool header row and the toolbar back", all(tool_headers())
          and view()[1].spaces.active.show_region_toolbar, str(tool_headers()))
    check("... the entry now reads Back to the Fresing window", q.menu_text() == q.BACK_TEXT, q.menu_text())
    lists_ok("Blender's own drawing")
    redraw()
    return 1.0


@step
def s_full_px():
    STATE["full_px"] = header_empty_px(shot("04_full_header"))
    freed = STATE["quiet_px"][0] - STATE["full_px"][0]
    log(f"header width freed: {freed} px of {STATE['full_px'][1]} px (window {win0().width} px)")
    check("the quiet header frees width", freed > 150, f"{freed} px")
    # a mode other than Object Mode reached in Full access
    with override():
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.mode_set(mode="EDIT")
    show_all()                                                 # back to the quiet window while in Edit Mode
    redraw()
    STATE["hb"] = mod("blender.quiet").DRAWN["header_blender"]
    return 1.0


@step
def s_edit_mode():
    q = mod("blender.quiet")
    check("Edit Mode in the quiet window keeps Blender's header (mode menu)", q.DRAWN["header_blender"] > 0
          and q.ON[0], str(q.DRAWN))
    shot("05_edit_mode")
    with override():
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.delete()
    ws = mod("blender.workspaces")
    check("Back to the Fresing window: the workspace it came from", ws.name_of(bpy.context.scene)
          == "Product design & R&D", ws.name_of(bpy.context.scene))
    check("... the entry reads Show all of Blender again", q.menu_text() == q.SHOW_TEXT, q.menu_text())
    return 0.8


@step
def s_repeat():
    q = mod("blender.quiet")
    ok = True
    for _ in range(3):
        show_all()
        ok = ok and not q.ON[0]
        show_all()
        ok = ok and q.ON[0]
    ws = mod("blender.workspaces")
    check("Show all / Back three times more", ok and ws.name_of(bpy.context.scene) == "Product design & R&D",
          ws.name_of(bpy.context.scene))
    return 1.0


@step
def s_repeat_ok():
    quiet_ok("after the round trips")
    lists_ok("after the round trips")
    check("draw lists in the same order as at the start", lists_ok("order")[:] == STATE["order"])
    workspace("Client view")
    return 1.0


@step
def s_client():
    q = mod("blender.quiet")
    quiet_ok("Client view")
    check("Client view: Show all of Blender is greyed", not bpy.ops.fresing.blender_all.poll())
    check("... and its tooltip says why", "Client view" in q.FRESING_OT_blender_all.description(
        bpy.context, None))
    workspace("Full access")
    return 1.0


@step
def s_full_from_panel():
    q = mod("blender.quiet")
    quiet_ok("Workspace > Full access", quiet=False)
    check("... the tool header row back", all(tool_headers()), str(tool_headers()))
    show_all()                                                 # nothing remembered: the default workspace
    return 1.0


@step
def s_back_default():
    ws = mod("blender.workspaces")
    quiet_ok("Back with nothing remembered")
    check("... to the default workspace", ws.name_of(bpy.context.scene) == ws.default_name(),
          ws.name_of(bpy.context.scene))
    q = mod("blender.quiet")
    q.apply(False)
    q.apply(True)                                              # a patch / unpatch / patch round
    lists_ok("patch / unpatch / patch")
    check("... draw lists in the same order", lists_ok("order 2") == STATE["order"])
    return 0.5


def save_as(name, mark=None, old=False):
    sc = bpy.context.scene
    if mark:
        sc[mark] = "0.0.0"
    if old:                                                    # an older version's project: no workspace in it
        sc.fresing.ws_name = ""
        sc["fr_saved_by"] = "0.2.140"
    for a in win0().screen.areas:
        if a.type == "VIEW_3D":
            a.spaces.active.show_region_tool_header = True     # saved with Blender's full header
    path = os.path.join(TMP, name)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


@step
def s_save_old():
    STATE["old"] = save_as("old own é.blend", old=True)
    bpy.ops.wm.open_mainfile(filepath=STATE["old"])
    return 2.0


@step
def s_open_old():
    quiet_ok("an old own project saved with Blender's header")
    STATE["tour"] = save_as("tour set.blend", mark=mod("blender.tour").TAG)
    bpy.ops.wm.open_mainfile(filepath=STATE["tour"])
    return 2.0


@step
def s_open_tour():
    quiet_ok("a test tour project")
    for k in ("fr_tour",):
        if k in bpy.context.scene:
            del bpy.context.scene[k]
    STATE["demo"] = save_as("demo.blend", mark=mod("blender.demo").TAG)
    bpy.ops.wm.open_mainfile(filepath=STATE["demo"])
    return 2.0


@step
def s_open_demo():
    quiet_ok("the demo project")
    lists_ok("after opening projects")
    redraw()
    return 0.8


@step
def s_header_after_open():
    q = mod("blender.quiet")
    n = q.DRAWN["header"]
    redraw()
    STATE["n"] = n
    return 0.5


@step
def s_finish():
    q = mod("blender.quiet")
    check("the quiet header is drawn after opening projects", q.DRAWN["header"] > STATE["n"], str(q.DRAWN))
    for cls_name, fn in DUMMIES:
        getattr(bpy.types, cls_name).remove(fn)
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
