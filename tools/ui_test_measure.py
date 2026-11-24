"""Real-app test, task 0322: Measure in the 3D view.

On the test crane: the top bar draws **Measure** (found on screen by drawing the top bar with and without it); the key
**M** over the 3D view starts the tool, two clicks (the base's top face, then its front face) make a measurement (90°,
the faces' angle), a click on its label copies the value, Esc leaves; started from the top bar (the drop-down's
buttons), **Edge length** takes the edge nearest the mouse and gives the same length the face data says; one click on
the top bar's button opens the drop-down; in the **Client view** M still measures; in **Full access** M is Blender's own
again and **Alt+M** measures. Pictures for the guide (the drop-down) and the report (the view with labels) go to
$UITEST_OUT.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/ms xvfb-run -a -s "-screen 0 1800x1200x24" blender \\
        -p 0 0 1800 1200 --app-template fresing_render --enable-event-simulate --python tools/ui_test_measure.py
"""

import importlib
import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Euler, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_measure"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_measure.log"), "w")
RESULTS = []
S = {}
STEPS = []


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


def win0():
    return bpy.context.window_manager.windows[0]


def view():
    win = win0()
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def step(fn):
    STEPS.append(fn)
    return fn


def key(k, **mods):
    """A key with the mouse where it was last moved (a simulated key without x, y lands at the window's corner)."""
    win = win0()
    x, y = S.get("mouse", (win.width // 2, win.height // 2))
    win.event_simulate(type=k, value="PRESS", x=int(x), y=int(y), **mods)
    win.event_simulate(type=k, value="RELEASE", x=int(x), y=int(y), **mods)


def esc():
    key("ESC")


def move(x, y):
    S["mouse"] = (x, y)
    win0().event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x), y=int(y))


def click(x, y):
    win = win0()
    move(x, y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=int(x), y=int(y))
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=int(x), y=int(y))


def at(p):
    """The window point (x, y) of the world point ``p`` in the main 3D view."""
    from bpy_extras import view3d_utils
    _win, _area, region = view()
    xy = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(p))
    return region.x + xy.x, region.y + xy.y


def redraw_all():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()
    win = win0()
    try:
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    except Exception as exc:  # noqa: BLE001
        log("redraw:", exc)
    try:
        mod("blender.lock")._topbar_redraw()
    except Exception:  # noqa: BLE001
        pass
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=42, y=win.height - 12)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=win.width // 2 + int(time.time() * 7) % 11,
                       y=win.height // 2)


def grab(name, crop=None):
    path = os.path.join(OUT, name)
    cmd = ["import", "-window", "root"]
    if crop:
        x, y, w, h = crop
        cmd += ["-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y)}", "+repage"]
    subprocess.run(cmd + [path], check=False)
    return path


def pixels(path):
    raw = subprocess.run(["convert", path, "-depth", "8", "ppm:-"], capture_output=True, check=False).stdout
    parts = raw.split(b"\n", 3)
    w, h = (int(v) for v in parts[1].split())
    return w, h, parts[3]


def topbar_height():
    return int(30 * bpy.context.preferences.system.ui_scale * 1.2) + 4


def _diff_columns(a, b):
    wa, ha, da = pixels(a)
    wb, hb, db = pixels(b)
    if (wa, ha) != (wb, hb):
        return None
    cols = []
    for x in range(wa):
        for y in range(ha):
            i = (y * wa + x) * 3
            if da[i:i + 3] != db[i:i + 3]:
                cols.append(x)
                break
    return (cols[0], cols[-1]) if cols else None


def tool():
    return mod("blender.measure").tool_state()


@step
def s_splash():
    esc()
    return 1.0


@step
def s_import():
    S["overlap"] = bpy.context.preferences.system.use_region_overlap
    bpy.context.preferences.system.use_region_overlap = False
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    S["t_import"] = time.time()
    return 1.0


@step
def s_setup():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0 and time.time() - S["t_import"] < 120:
        return "again"
    check("the test crane is imported", sc.fresing.model_count > 0)
    _win, area, region = view()
    rv3d = region.data
    rv3d.view_perspective = "PERSP"
    rv3d.view_location = Vector((2.5, 1.2, 0.4))
    rv3d.view_rotation = Euler((math.radians(62), 0.0, math.radians(22))).to_quaternion()
    rv3d.view_distance = 7.5
    area.spaces.active.shading.type = "SOLID"
    redraw_all()
    return 1.0


@step
def s_key_m():
    x, y = at((1.0, 2.2, 0.5))
    move(x, y)
    key("M")
    return 1.0


@step
def s_two_clicks():
    t = tool()
    check("M over the 3D view starts Measure", t is not None, "" if t is None else t["kind"])
    if t is None:
        return 0.5
    S["n0"] = len(bpy.context.scene.fresing_measure.items)
    click(*at((1.0, 2.2, 0.5)))                     # the base's top face
    return 0.8


@step
def s_second_click():
    t = tool()
    check("the first click is kept", t is not None and len(t["picks"]) == 1,
          "" if t is None else str([p.what for _n, p in t["picks"]]))
    click(*at((3.6, 0.0, 0.2)))                     # the base's front face
    return 1.0


@step
def s_measured():
    sc = bpy.context.scene
    measure = mod("blender.measure")
    st = sc.fresing_measure
    ok = len(st.items) == S.get("n0", 0) + 1
    r = measure.result(sc, st.items[-1]) if ok else None
    check("two clicks make a measurement: top face to front face = 90.00°",
          r is not None and r.angle is not None and abs(r.angle - 90.0) < 0.01, "" if r is None else r.lines[0])
    redraw_all()
    return 1.0


@step
def s_copy_label():
    measure = mod("blender.measure")
    ops = mod("blender.ops_measure")
    _win, area, region = view()
    got = measure._S["rects"].get(area.as_pointer())
    rects = got[2] if got else []
    check("the measurement's label is drawn in the 3D view", len(rects) >= 1, str(len(rects)))
    if rects:
        x0, y0, x1, y1, _i = rects[-1]
        ops.COPIED[0] = ""
        click(region.x + (x0 + x1) / 2, region.y + (y0 + y1) / 2)
    return 0.8


@step
def s_copied():
    ops = mod("blender.ops_measure")
    check("a click on the label copies its value", ops.COPIED[0] == "90.00°", repr(ops.COPIED[0]))
    esc()
    return 0.8


@step
def s_left():
    check("Esc leaves Measure", tool() is None)
    win = win0()
    with bpy.context.temp_override(window=win, screen=win.screen, area=None, region=None):   # as from the top bar
        res = bpy.ops.fresing.measure("INVOKE_DEFAULT", kind="EDGE")
    check("the drop-down's Edge length starts Measure in the 3D view", res == {"RUNNING_MODAL"} or tool() is not None,
          str(res))
    x, y = at((2.6, 0.02, 0.48))                    # on the chamfer along the base's front top edge
    move(x, y)
    S["edge_at"] = (x, y)
    return 0.8


@step
def s_edge_click():
    t = tool()
    lk = t.get("look") if t else None
    check("Edge length: the hover offers an edge", lk is not None and lk.pick is not None and lk.pick.kind == "line",
          "" if lk is None else lk.text)
    S["edge_len"] = lk.pick.length if lk is not None and lk.pick is not None and lk.pick.kind == "line" else None
    S["n1"] = len(bpy.context.scene.fresing_measure.items)
    click(*S["edge_at"])
    return 0.8


@step
def s_edge_done():
    sc = bpy.context.scene
    measure = mod("blender.measure")
    st = sc.fresing_measure
    item = st.items[-1] if len(st.items) > S["n1"] else None
    r = measure.result(sc, item) if item is not None else None
    check("one click: the edge's length, as the face data says",
          r is not None and S["edge_len"] is not None and abs(r.dist - S["edge_len"]) < 1e-6 and item.kind == "EDGE",
          "" if r is None else r.lines[0])
    redraw_all()
    return 1.0


@step
def s_view_picture():
    _win, area, _region = view()
    grab("measure_view.png", (area.x, win0().height - area.y - area.height, area.width, area.height))
    esc()
    return 0.8


@step
def s_find_button():
    ui = mod("blender.ui_measure")
    S["drawn0"] = ui.DRAWN["button"]
    S["on"] = grab("_topbar_on.png", (0, 0, win0().width, topbar_height()))
    ui.HIDE[0] = True
    redraw_all()
    return 1.0


@step
def s_find_button_2():
    ui = mod("blender.ui_measure")
    off = grab("_topbar_off.png", (0, 0, win0().width, topbar_height()))
    ui.HIDE[0] = False
    redraw_all()
    cols = _diff_columns(S["on"], off)
    check("the top bar draws the Measure button", ui.DRAWN["button"] > S["drawn0"] and cols is not None, f"{cols}")
    S["button"] = cols
    return 1.0


@step
def s_click_open():
    ui = mod("blender.ui_measure")
    cols = S.get("button")
    if not cols:
        return 0.5
    S["menu0"] = ui.DRAWN["panel"]
    S["click"] = ((cols[0] + cols[1]) // 2, win0().height - topbar_height() // 2 + 2)
    click(*S["click"])
    return 1.5


@step
def s_opened_or_again():
    ui = mod("blender.ui_measure")
    if S.get("button") and ui.DRAWN["panel"] == S["menu0"]:
        log("the first click only focused the top bar: once more")
        click(*S["click"])
    return 1.5


@step
def s_opened():
    ui = mod("blender.ui_measure")
    cols = S.get("button") or (0, 0)
    check("one click on Measure opens the drop-down", S.get("button") is not None and ui.DRAWN["panel"] > S["menu0"])
    grab("measure_menu_full.png")
    w = int(ui.UNITS_X * 20 * bpy.context.preferences.system.ui_scale) + 140
    x0 = max(0, (cols[0] + cols[1]) // 2 - w // 2)
    grab("measure_menu.png", (x0, 0, w, 560))
    esc()
    return 1.0


@step
def s_client_view():
    sc = bpy.context.scene
    mod("blender.workspaces").switch(sc, "Client view")
    redraw_all()
    return 1.5


@step
def s_client_key():
    move(*at((1.0, 2.2, 0.5)))
    key("M")
    return 1.0


@step
def s_client_measuring():
    check("the Client view measures (M)", tool() is not None)
    esc()
    return 0.8


@step
def s_full_access():
    check("Esc leaves Measure in the Client view", tool() is None)
    sc = bpy.context.scene
    mod("blender.workspaces").switch(sc, "Full access")
    redraw_all()
    return 1.5


@step
def s_full_m():
    move(*at((1.0, 2.2, 0.5)))
    key("M")
    return 1.0


@step
def s_full_alt_m():
    check("in Full access M is Blender's own (Measure does not start)", tool() is None)
    esc()                                           # Blender's "move to collection" menu
    return 0.5


@step
def s_full_alt_m_2():
    move(*at((1.0, 2.2, 0.5)))
    key("M", alt=True)
    return 1.0


@step
def s_full_alt_m_done():
    check("Alt+M measures in Full access", tool() is not None)
    esc()
    mod("blender.workspaces").switch(bpy.context.scene, "All functions")
    return 0.8


@step
def s_finish():
    bpy.context.preferences.system.use_region_overlap = S.get("overlap", True)   # Blender saves preferences
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
        return 1.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
