"""Real-app test, hoses drawn by clicking (task 0240): the hoses model with its joints and no hose in the list.
Draw hose (replacing the CAD hose HYDRAULIC HOSE ARM, which hides while clicking): the mouse moves onto the valve
block's fitting – the hover shows that part –, a click; Backspace takes it back; the click again; the mouse onto the
arm's fitting, a click; Enter. The drawn hose is in the list, its ends on the two fittings, the CAD hose hidden for
good; the arm luffs and the hose follows. Then Draw hose again, one click and Esc: nothing is drawn. Undo takes the
drawn hose back, redo brings it again.

The clicks in the 3D view are real mouse events of a running picker (the operator is started as a button starts it).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_drawn.py
Screenshots and ui_test_drawn.log go to $UITEST_OUT (default ~/fresing_ui_test_drawn).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
import numpy as np
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_drawn"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_drawn.log"), "w")
RESULTS = []
MM = 0.001
VALVE_TOP = Vector((0.432, -0.069, 0.22))       # FITTING VALVE C's end face (tools/make_test_flex.py)
ARM_FACE = Vector((1.002, 0.12, 0.6))           # FITTING ARM's end face, looking along -Y
LUFF = math.radians(15.0)


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


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def move(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)


def press(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def key(k, ctrl=False):
    win, area, region, _sb = ui()
    x, y = region.x + 200, region.y + 200
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def view(location, distance, turn=0.0, tilt=58.0):
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = (Quaternion((0, 0, 1), math.radians(-turn)) @ Quaternion((1, 0, 0), math.radians(tilt)))
    r3d.view_location = Vector(location)
    r3d.view_distance = distance
    area.spaces.active.shading.type = "SOLID"
    redraw()


def pixel(point):
    """The window pixel where ``point`` (world) shows, a hair towards the viewer."""
    win, area, region, sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(point))
    return int(round(region.x + co.x)), int(round(region.y + co.y))


def flex():
    return mod("blender.flex")


def items():
    return bpy.context.scene.fresing.flex


def said() -> str:
    return bpy.context.scene.fresing.last_message


def start_draw(**kw):
    with override():
        return bpy.ops.fresing.flex_draw("INVOKE_DEFAULT", True, **kw)


def hovered():
    h = mod("blender.hover").current()
    return (bpy.context.scene.objects[h.part].get("fr_name") if h is not None and h.part else "")


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region, sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 1.0


@step
def s_import():
    log("extension", pkg())
    with override():
        res = bpy.ops.fresing.import_step(filepath=HOSES, quality="draft")
    log("import", res, said())
    return 1.0


@step
def s_wait():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    bpy.context.preferences.system.use_region_overlap = False
    joints = mod("blender.joints")
    flex().set_up_test_hoses(sc)
    while len(items()):
        flex().remove(sc, 0)
    luff = joints.find(sc, "Luff")
    luff.rot_min, luff.rot_max, luff.use_limits = math.radians(-20), math.radians(20), True
    mod("blender.panels").open_to("FRESING_PT_flex")
    view((0.7, 0.05, 0.4), 1.6)
    check("the hoses model: joints made, nothing in the list", len(items()) == 0
          and joints.find(sc, "Slide") is not None)
    wiggle()
    return 1.5


@step
def s_draw_start():
    r = start_draw(kind="HOSE", replace=named("HYDRAULIC HOSE ARM").name)
    check("Draw hose starts its picker", r == {"RUNNING_MODAL"}, str(r))
    check("… and the CAD hose it replaces hides while clicking", not named("HYDRAULIC HOSE ARM").visible_get())
    return 1.0


@step
def s_hover_valve():
    move(*pixel(VALVE_TOP + Vector((0, -0.002, 0.002))))
    return 0.8


@step
def s_click_valve():
    check("the hover shows the valve block's fitting under the mouse", hovered() == "FITTING VALVE C", hovered())
    press(*pixel(VALVE_TOP + Vector((0, -0.002, 0.002))))
    return 0.8


@step
def s_backspace():
    shot("draw_hose_first_click")
    key("BACK_SPACE")
    return 0.5


@step
def s_click_valve_again():
    x, y = pixel(VALVE_TOP + Vector((0, -0.002, 0.002)))
    move(x, y)
    press(x, y)
    return 0.8


@step
def s_hover_arm():
    move(*pixel(ARM_FACE + Vector((0.0, -0.002, 0.0))))
    return 0.8


@step
def s_click_arm():
    check("the hover shows the arm's fitting under the mouse", hovered() == "FITTING ARM", hovered())
    press(*pixel(ARM_FACE + Vector((0.0, -0.002, 0.0))))
    return 0.8


@step
def s_enter():
    key("RET")
    return 1.5


@step
def s_drawn():
    sc = bpy.context.scene
    drawn = mod("blender.drawn")
    it = flex().find(sc, "Hose 1")
    check("Enter: the hose is drawn and in the list", it is not None and len(items()) == 1 and it.drawn, said())
    if it is None:
        return 0.5
    check("its ends sit on the two fittings clicked (Backspace took the first click back: no clip)",
          it.a_part == named("FITTING VALVE C") and it.b_part == named("FITTING ARM") and len(it.clips) == 0)
    a = drawn.world_spot(it.a_part, it.a_point, it.a_dir)[0]
    check("end A in the middle of the valve fitting's face", np.linalg.norm(a - np.array((0.43, -0.07, 0.22))) < 1e-4,
          f"{a}")
    cad = named("HYDRAULIC HOSE ARM")
    check("the CAD hose is hidden for good (replaced)", cad.get("fr_excluded") and not cad.visible_get()
          and cad.hide_render)
    check("it follows the motion", flex().status(sc, it)[1] == "OK", flex().status(sc, it)[0])
    shot("draw_hose_done")
    joints = mod("blender.joints")
    joints.set_value(joints.find(sc, "Luff"), LUFF)
    bpy.context.view_layer.update()
    wiggle()
    return 1.0


@step
def s_follows():
    sc = bpy.context.scene
    it = flex().find(sc, "Hose 1")
    drawn = mod("blender.drawn")
    line = flex().shape_now(sc, it)
    b = drawn.world_spot(it.b_part, it.b_point, it.b_dir)[0]
    off = float(np.linalg.norm(line[-1] - b))
    check("Luff 15°: the drawn hose's end B stays on the arm's fitting", off < 0.1 * MM and b[2] > 0.7,
          f"{off * 1000:.4f} mm")
    check("… and it is long enough over the luff's limits", flex().status(sc, it)[1] == "OK",
          flex().status(sc, it)[0])
    r = start_draw(kind="HOSE")
    check("Draw hose again starts", r == {"RUNNING_MODAL"})
    x, y = pixel(VALVE_TOP + Vector((0, -0.002, 0.002)))
    move(x, y)
    press(x, y)
    return 0.8


@step
def s_esc():
    key("ESC")
    return 0.8


@step
def s_nothing_drawn():
    check("one click and Esc: nothing more is drawn", len(items()) == 1, said())
    check("… and the picker has ended", not mod("blender.hover").active())
    with override():
        bpy.ops.ed.undo()
    return 1.0


@step
def s_undone():
    sc = bpy.context.scene
    n = len(sc.fresing.flex)
    check("undo: the drawn hose is gone, the CAD hose shows again", n == 0 and not named("HYDRAULIC HOSE ARM")
          .get("fr_excluded"), f"{n} in the list")
    with override():
        bpy.ops.ed.redo()
    return 1.0


@step
def s_redone():
    sc = bpy.context.scene
    it = flex().find(sc, "Hose 1")
    check("redo: it is back, drawn, and follows the motion", it is not None and it.drawn
          and flex().status(sc, it)[1] == "OK")
    bpy.context.preferences.system.use_region_overlap = True
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
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
        wiggle()
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
