"""Real-app test, task 0062: the Set-up window (fresing_render/blender/ops_setup.py, ui_setup.py).

The window is opened on the test gantry; checked in the real app: a second window is there and the main window's
areas have the sizes they had; its side panel shows the tab "Set-up"; a real click on its blue Next button (found in a
screenshot) goes on a step, Back and a step number through their operator; a click on a part in the MAIN window's 3D
view selects it while the Set-up window is open, and "Use as workpiece" pressed in the Set-up window takes it; the
work zero's click picker started from the Set-up window takes a click in the main window; the kind switch shows the
mechanism's steps; the project saved and opened again brings the window back on its tab; closing it leaves the main
window as it was; it opens a second time; a project saved without the window closes it; at UI scale 1.5 the window is
as wide as the bigger side panel.

    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 \\
        --app-template fresing_render --enable-event-simulate --python tools/ui_test_setup.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_setup): the Set-up window at every step
(setup_cnc_1.png … setup_cnc_5.png, setup_mech_1.png … setup_mech_4.png) and all of them side by side
(setup_steps.png) – the picture to look at after a change: nothing cut off with "…", every step readable."""

import importlib
import os
import subprocess
import tempfile
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_setup"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_gantry.step")
STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_setup.log"), "w")
RESULTS = []
S = {}


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


def ops():
    return mod("blender.ops_setup")


MINE = []
COST = {"n": 0, "t": 0.0}


def register_mine():
    """Until fresing_render/__init__.py registers the Set-up window's classes itself. Also times the panel."""
    for cls in ops().CLASSES + mod("blender.ui_setup").CLASSES:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
            MINE.append(cls)
    ui_setup = mod("blender.ui_setup")
    if getattr(ui_setup.draw_setup, "timed", False):
        return
    plain = ui_setup.draw_setup

    def draw_setup(layout, context):
        t = time.perf_counter()
        plain(layout, context)
        COST["n"] += 1
        COST["t"] += time.perf_counter() - t
    draw_setup.timed = True
    ui_setup.draw_setup = draw_setup


def main_win():
    return next(w for w in bpy.context.window_manager.windows if not ops().is_setup_window(w))


def setup_win():
    wins = ops().setup_windows()
    return wins[0] if wins else None


def view(win=None):
    win = win or main_win()
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override(win=None, sidebar=False):
    win, area, region, sb = view(win)
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if sidebar else region,
                                     scene=win.scene)


def press(idname, win=None, **kw):
    """An operator called like a button press in that window's side panel (EXEC, with an undo step)."""
    group, name = idname.split(".")
    with override(win, sidebar=True):
        return getattr(getattr(bpy.ops, group), name)("EXEC_DEFAULT", True, **kw)


def areas():
    return sorted((a.type, a.x, a.y, a.width, a.height) for a in main_win().screen.areas)


def find(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def to_window(world_pt):
    win, _area, region, _sb = view()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(region.x + co.x), int(region.y + co.y)


def click(win, x, y):
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 2, y=y + 2)


def top_of(name):
    """A point on the top face of a part, a little off its centre (world)."""
    o = find(name)
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    top = max(p.z for p in pts)
    cx = sum(p.x for p in pts) / 8 + 0.02
    cy = sum(p.y for p in pts) / 8 + 0.02
    return (cx, cy, top)


def screen_height():
    """The height of the whole screen, from a screenshot of it."""
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    out = subprocess.run(["identify", "-format", "%h", full], capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else main_win().height


def shot_setup(name):
    """The Set-up window cut out of a screenshot of the whole screen; returns the picture's path."""
    win = setup_win()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = S["screen_h"] - (win.y + win.height)
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["convert", full, "-crop", f"{win.width}x{win.height}+{win.x}+{top}", "+repage", path],
                   check=False)
    return path


def blue_button(path):
    """(x, y) in the Set-up window (Blender's window coordinates, y up) of the middle of the lowest blue button in
    a picture of that window: the Next button. None when there is no blue button."""
    import numpy as np
    img = bpy.data.images.load(path)
    try:
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
    finally:
        bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)                                  # rows from the bottom, as Blender's window
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    blue = (b > 0.5) & (b - r > 0.25) & (b - g > 0.12)
    rows = np.where(blue.sum(axis=1) > 40)[0]                 # rows with a long run of button blue
    if not len(rows):
        return None
    low = [rows[0]]
    for y in rows[1:]:
        if y != low[-1] + 1:
            break
        low.append(y)
    cols = np.where(blue[low[0]:low[-1] + 1].any(axis=0))[0]
    return int((cols[0] + cols[-1]) / 2), int((low[0] + low[-1]) / 2)


def tab_of(win):
    _w, _a, _r, sb = view(win)
    try:
        return sb.active_panel_category
    except Exception as exc:  # noqa: BLE001
        return f"? {exc}"


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_esc_press():
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="ESC", value="PRESS", x=700, y=600)        # the splash screen: nothing gets past it
    return 0.5


@step
def s_esc_release():
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=600)
    return 0.5


@step
def s_import():
    register_mine()
    S["screen_h"] = screen_height()
    check("no Set-up window at the start", len(bpy.context.window_manager.windows) == 1 and setup_win() is None)
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    return 1.0


@step
def s_joints():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    joints = mod("blender.joints")
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = find(asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    with override():
        bpy.ops.view3d.view_all()
    return 1.5


@step
def s_open():
    S["areas"] = areas()
    S["screens"] = len(bpy.data.screens)
    S["folder"] = tempfile.mkdtemp(prefix="fr_setup_")
    S["plain"] = os.path.join(S["folder"], "no window.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=S["plain"])
    log("main window", main_win().width, "x", main_win().height, "areas", S["areas"])
    S["t"] = time.time()
    res = press("fresing.setup_window", kind="CNC")
    check("the Set-up window button runs", res == {"FINISHED"}, str(res))
    return 0.2


@step
def s_opened():
    if (setup_win() is None or ops()._STATE["busy"]) and time.time() - S["t"] < 10:
        return "wait"
    wm = bpy.context.window_manager
    win = setup_win()
    check("the Set-up window opened: two windows", len(wm.windows) == 2 and win is not None,
          f"{len(wm.windows)} windows after {time.time() - S['t']:.2f} s")
    if win is None:
        return 0.2
    scale = bpy.context.preferences.system.ui_scale
    log("Set-up window", win.width, "x", win.height, "at", win.x, win.y, "UI scale", scale)
    side = view()[3].width
    check("it is as wide as the side panel and about 560 px high at UI scale 1.0",
          abs(win.width - (side + 4)) <= 6 and abs(win.height - 560 * scale) <= 24,
          f"{win.width} x {win.height}, the main side panel is {side} wide")
    check("the main window's areas are as they were", areas() == S["areas"], str(areas()))
    check("its screen carries the mark, the main window's does not",
          ops().is_setup_window(win) and not ops().is_setup_window(main_win()))
    return 1.0


@step
def s_tab():
    win = setup_win()
    if tab_of(win) != "Set-up" and time.time() - S["t"] < 20:
        return "wait"
    _w, area, region, sb = view(win)
    sp = area.spaces.active
    check("its side panel shows the tab Set-up", tab_of(win) == "Set-up", tab_of(win))
    check("the main window stays on the Fresing tab", tab_of(main_win()) == "Fresing", tab_of(main_win()))
    log("Set-up window: side panel", sb.width, "x", sb.height, "view", region.width, "x", region.height)
    check("the side panel fills the window: nothing but the panel",
          sb.width >= win.width - 8 and sb.height >= win.height - 8 and region.width - sb.width <= 8,
          f"{sb.width} x {sb.height} of {win.width} x {win.height}, 3D view {region.width} wide")
    high = {r.type: r.height for r in area.regions}
    check("no header, tool header, toolbar, overlays or gizmos in it, solid shading",
          not sp.show_region_header and high["HEADER"] <= 1 and high["TOOL_HEADER"] <= 1
          and not sp.show_region_toolbar and not sp.overlay.show_overlays and not sp.show_gizmo
          and sp.shading.type == "SOLID", str(high))
    check("the scene's set-up is the CNC mill, step 1", mod("blender.ui_setup").current(bpy.context.scene)[:2]
          == ("CNC", 0))
    return 1.0


@step
def s_shot_cnc():
    S["shot"] = shot_setup("setup_cnc")
    return 0.3


@step
def s_click_next():
    at = blue_button(S["shot"])
    check("the picture of the window shows a blue Next button", at is not None, str(at))
    if at is not None:
        win = setup_win()
        click(win, at[0], at[1])                                # a real click, through the window's own events
    S["t"] = time.time()
    return 0.3


@step
def s_next_clicked():
    sc = bpy.context.scene
    if sc.fresing.setup_step == 0 and time.time() - S["t"] < 5:    # (a step's wait counts from the step's start)
        return "wait"
    check("a click on Next in the Set-up window goes to step 2", sc.fresing.setup_step == 1,
          str(sc.fresing.setup_step))
    win = setup_win()
    press("fresing.setup_go", win, step=sc.fresing.setup_step + 1)
    check("Next again: step 3 (Tool and workpiece)", sc.fresing.setup_step == 2)
    press("fresing.setup_go", win, step=sc.fresing.setup_step - 1)
    check("Back: step 2", sc.fresing.setup_step == 1)
    press("fresing.setup_go", win, step=4)
    check("the step number 5: step 5", sc.fresing.setup_step == 4)
    press("fresing.setup_go", win, step=9)
    check("a step past the end stays on the last step", sc.fresing.setup_step == 4)
    press("fresing.setup_go", win, step=2)
    return 0.5


@step
def s_click_part():
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = None
    x, y = to_window(top_of(STOCK))
    click(main_win(), x, y)                                     # in the MAIN window, the Set-up window open
    S["t"] = time.time()
    return 0.3


@step
def s_part_clicked():
    sc = bpy.context.scene
    active = bpy.context.view_layer.objects.active
    if active is None and time.time() - S["t"] < 5:
        return "wait"
    check("a click on a part in the main window selects it while the Set-up window is open",
          active is not None and active.get("fr_name") == STOCK and active.select_get(),
          str(active.get("fr_name") if active else None))
    check("the Set-up window is still open", setup_win() is not None and len(bpy.context.window_manager.windows) == 2)
    win = setup_win()
    press("fresing.cnc_use_workpiece", win)
    cnc = sc.fresing.cnc
    check("Use as workpiece, pressed in the Set-up window, takes the clicked part",
          cnc.workpiece is not None and cnc.workpiece.get("fr_name") == STOCK)
    press("fresing.cnc_find_axes", win)
    check("Find the axes, pressed in the Set-up window, picks X, Y and Z",
          (cnc.x_joint, cnc.y_joint, cnc.z_joint) == ("X", "Y", "Z"))
    tool = find(T1)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    tool.select_set(True)
    bpy.context.view_layer.objects.active = tool
    press("fresing.cnc_use_tool", win)
    check("the machine is ready", mod("blender.gcode").problem(sc) == "", mod("blender.gcode").problem(sc))
    ui_setup = mod("blender.ui_setup")
    with override(win, sidebar=True):
        done = [ui_setup.is_done(bpy.context, "CNC", k) for k in range(5)]
    check("the steps that are done know it (axes, tool and workpiece, work zero)",
          done == [True, False, True, True, False], str(done))
    # the work zero by a click: the picker is started from the Set-up window and runs in the main window
    cnc.zero_mode = "POINT"
    S["zero"] = tuple(cnc.zero_point)
    press("fresing.setup_go", win, step=3)
    with override(win, sidebar=True):
        res = bpy.ops.fresing.setup_in_view("INVOKE_DEFAULT", True, op="fresing.cnc_zero_click")
    check("'Click the zero point' starts from the Set-up window", res == {"FINISHED"}, str(res))
    return 1.0


@step
def s_zero_move():
    x, y = S["at"] = to_window(top_of(STOCK))
    main_win().event_simulate(type="MOUSEMOVE", value="NOTHING", x=x - 6, y=y - 6)
    return 0.5


@step
def s_zero_click():
    click(main_win(), *S["at"])
    S["t"] = time.time()
    return 0.3


@step
def s_zero_clicked():
    cnc = bpy.context.scene.fresing.cnc
    now = tuple(cnc.zero_point)
    if now == S["zero"] and time.time() - S["t"] < 5:
        return "wait"
    check("its click in the main window sets the work zero", now != S["zero"] and cnc.zero_mode == "POINT",
          f"{S['zero']} -> {now}")
    return 0.5


def shots(kind, n):
    """A picture of every step of a set-up: setup_<kind>_<step>.png."""
    def go(k):
        def s_go():
            press("fresing.setup_go", setup_win(), step=k)
            return 0.4

        def s_shot():
            shot_setup(f"setup_{kind}_{k + 1}")
            return 0.1
        return s_go, s_shot
    for k in range(n):
        STEPS.extend(go(k))


shots("cnc", 5)


@step
def s_kind():
    sc = bpy.context.scene
    win = setup_win()
    res = press("fresing.setup_kind", win, kind="MECH")
    check("the kind switch shows the mechanism, from its first step",
          res == {"FINISHED"} and mod("blender.ui_setup").current(sc)[:2] == ("MECH", 0)
          and (sc.fresing.setup_kind, sc.fresing.setup_step) == ("MECH", 0))
    return 0.5


shots("mech", 4)


@step
def s_pictures():
    """All steps side by side (setup_steps.png): the picture to look at – nothing cut off, every step readable."""
    names = [f"setup_cnc_{k}" for k in range(1, 6)] + [f"setup_mech_{k}" for k in range(1, 5)]
    files = [os.path.join(OUT, n + ".png") for n in names]
    check("a picture of every step of both set-ups", all(os.path.isfile(f) and os.path.getsize(f) > 2000
                                                         for f in files))
    subprocess.run(["convert"] + files + ["+append", os.path.join(OUT, "setup_steps.png")], check=False)
    press("fresing.setup_go", setup_win(), step=1)
    res = press("fresing.setup_window", kind="MECH")             # the button again: no second window
    check("the button pressed again opens no second window",
          res == {"FINISHED"} and len(bpy.context.window_manager.windows) == 2)
    return 0.5


@step
def s_save_and_open():
    S["blend"] = os.path.join(S["folder"], "set-up test.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=S["blend"])
    S["size"] = (setup_win().width, setup_win().height)
    with override():
        bpy.ops.wm.open_mainfile(filepath=S["blend"])
    S["t"] = time.time()
    return 1.0


@step
def s_loaded():
    register_mine()
    # what a load handler does that puts every 3D view on the Fresing tab – all but the Set-up windows
    for win in bpy.context.window_manager.windows:
        if ops().is_setup_window(win):
            continue
        for area in win.screen.areas:
            for region in area.regions:
                if area.type == "VIEW_3D" and region.type == "UI":
                    try:
                        region.active_panel_category = "Fresing"
                    except Exception:  # noqa: BLE001
                        pass
    ops().restore_tabs()
    S["t"] = time.time()
    return 1.0


@step
def s_back_on_tab():
    win = setup_win()
    if (win is None or tab_of(win) != "Set-up") and time.time() - S["t"] < 10:
        return "wait"
    sc = bpy.context.scene
    check("the project opened again brings the Set-up window back",
          win is not None and len(bpy.context.window_manager.windows) == 2,
          f"{len(bpy.context.window_manager.windows)} windows")
    if win is None:
        return 0.2
    check("… on its tab", tab_of(win) == "Set-up", tab_of(win))
    check("… with its size", abs(win.width - S["size"][0]) <= 4 and abs(win.height - S["size"][1]) <= 4,
          f"{win.width} x {win.height}, was {S['size']}")
    check("… on the mechanism's step 2, as it was saved",
          mod("blender.ui_setup").current(sc)[:2] == ("MECH", 1))
    check("the main window is on the Fresing tab", tab_of(main_win()) == "Fresing", tab_of(main_win()))
    check("the main window's areas are as they were", areas() == S["areas"], str(areas()))
    return 0.5


@step
def s_close():
    win = setup_win()
    with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
        bpy.ops.wm.window_close()
    return 1.0


@step
def s_closed():
    wm = bpy.context.window_manager
    check("closing the Set-up window leaves one window", len(wm.windows) == 1 and setup_win() is None)
    check("the main window's areas are as they were", areas() == S["areas"], str(areas()))
    log("screens at the start", S["screens"], "now", len(bpy.data.screens))
    S["t"] = time.time()
    res = press("fresing.setup_window")
    check("the button opens it again", res == {"FINISHED"}, str(res))
    return 0.3


@step
def s_reopened():
    win = setup_win()
    if (win is None or ops()._STATE["busy"] or tab_of(win) != "Set-up") and time.time() - S["t"] < 15:
        return "wait"
    check("opened a second time, on its tab, the kind and step kept",
          win is not None and tab_of(win) == "Set-up"
          and mod("blender.ui_setup").current(bpy.context.scene)[:2] == ("MECH", 1),
          f"{time.time() - S['t']:.2f} s")
    check("the main window's areas are as they were", areas() == S["areas"], str(areas()))
    res = press("fresing.setup_close")
    check("Close the Set-up window closes it",
          res == {"FINISHED"} and len(bpy.context.window_manager.windows) == 1)
    return 0.5


@step
def s_scale():
    bpy.context.preferences.view.ui_scale = 1.5                 # a 4K screen at 150 %
    return 1.5


@step
def s_scale_open():
    S["areas15"] = areas()
    S["side15"] = view()[3].width
    S["t"] = time.time()
    press("fresing.setup_window", kind="CNC")
    return 0.3


@step
def s_scale_opened():
    win = setup_win()
    if (win is None or ops()._STATE["busy"] or tab_of(win) != "Set-up") and time.time() - S["t"] < 15:
        return "wait"
    scale = bpy.context.preferences.system.ui_scale
    _w, _area, _region, sb = view(win)
    high = min(560 * scale, view()[1].height - 60 * scale)       # as high as wanted, or as the 3D view allows
    log("UI scale", round(scale, 3), "Set-up window", win.width, "x", win.height, "side panel", sb.width, "x",
        sb.height, "main side panel", S["side15"])
    check("at UI scale 1.5 the window is as wide as the bigger side panel, and the panel fills it",
          abs(win.width - (S["side15"] + 4)) <= 6 and abs(win.height - high) <= 24 and sb.width >= win.width - 8,
          f"{win.width} x {win.height}")
    shot_setup("setup_scale15")
    res = press("fresing.setup_close", win)                      # pressed in the Set-up window itself
    check("Close pressed in the Set-up window itself runs", res == {"FINISHED"}, str(res))
    S["t"] = time.time()                    # (it closes a moment later: Blender needs the window until then)
    return 0.3


@step
def s_scale_back():
    if setup_win() is not None and time.time() - S["t"] < 5:
        return "wait"
    check("… and closes it", len(bpy.context.window_manager.windows) == 1 and setup_win() is None,
          f"{time.time() - S['t']:.2f} s")
    check("the main window's areas are as they were (UI scale 1.5)", areas() == S["areas15"], str(areas()))
    bpy.context.preferences.view.ui_scale = 1.0
    return 1.5


@step
def s_plain_open():
    S["t"] = time.time()
    press("fresing.setup_window")
    return 0.3


@step
def s_plain_load():
    win = setup_win()
    if (win is None or ops()._STATE["busy"]) and time.time() - S["t"] < 15:
        return "wait"
    with override():
        bpy.ops.wm.open_mainfile(filepath=S["plain"])            # saved before the window was first opened
    return 1.5


@step
def s_plain_loaded():
    register_mine()
    ops().restore_tabs()
    wm = bpy.context.window_manager
    check("a project saved without the Set-up window closes it: one window, no Set-up window",
          len(wm.windows) == 1 and setup_win() is None, f"{len(wm.windows)} windows")
    return 1.0


@step
def s_finish():
    check("the main window's areas are as they were at the end", areas() == S["areas"], str(areas()))
    log("the Set-up panel was drawn", COST["n"], "times,", round(1000 * COST["t"] / max(COST["n"], 1), 2),
        "ms each")
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    for cls in reversed(MINE):
        bpy.utils.unregister_class(cls)
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
        if time.time() - _w[0] > 120:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 0.3
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
