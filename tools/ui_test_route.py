"""Real-app test, Shape the route and Avoid other parts (task 0298): the avoid model (a block in a hose's way, a lift).
Avoid other parts is ticked: lowered, the hose lies on the block. Shape the route is started as a button starts it:
the mouse moves onto the hose's line (it lights up), a press there adds a via point, the mouse drags it sideways,
the release puts it down, Enter finishes: the hose runs through the dot. X over the dot removes it, Esc puts the route
back as it was. Undo takes a finished edit back, redo brings it again.

The events in the 3D view are real mouse and key events of the running operator.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_route.py
Screenshots and ui_test_route.log go to $UITEST_OUT (default ~/fresing_ui_test_route).
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

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_route"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
MODEL = os.path.join(DATA, "test_flex_avoid_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_route.log"), "w")
RESULTS = []
MM = 0.001


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
    return win, area, region


def override():
    win, area, region = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def ev(type_, value, xy, **kw):
    bpy.context.window_manager.windows[0].event_simulate(type=type_, value=value, x=xy[0], y=xy[1], **kw)


def wiggle():
    win, area, region = ui()
    ev("MOUSEMOVE", "NOTHING", (region.x + 300 + int(time.time()) % 7, region.y + 300))


def pixel(point):
    win, area, region = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(point))
    return int(round(region.x + co.x)), int(round(region.y + co.y))


def item():
    return bpy.context.scene.fresing.flex[0]


def vias():
    return mod("blender.flex_route").count(item())


def line():
    return mod("blender.flex").shape_now(bpy.context.scene, item())


STEPS = []
S = {}


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region = ui()
    ev("ESC", "PRESS", (region.x + 300, region.y + 300))
    ev("ESC", "RELEASE", (region.x + 300, region.y + 300))
    return 1.0


@step
def s_import():
    log("extension", pkg())
    with override():
        log("import", bpy.ops.fresing.import_step(filepath=MODEL, quality="draft"))
    return 1.0


@step
def s_setup():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    bpy.context.preferences.system.use_region_overlap = False
    flex, joints = mod("blender.flex"), mod("blender.joints")
    flex.set_up_test_avoid(sc, avoid=False)
    sc.fresing.flex_index = 0
    item().avoid = True
    joints.set_value(joints.find(sc, "Lift"), -0.4)
    bpy.context.view_layer.update()
    flex.refresh(sc)
    win, area, region = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((1, 0, 0), math.radians(90.0))          # from the front (−Y), Z up
    r3d.view_location = Vector((0.75, 0.0, 0.45))
    r3d.view_distance = 1.6
    mod("blender.panels").open_to("FRESING_PT_flex")
    pts = line()
    over = (pts[:, 0] > 0.53) & (pts[:, 0] < 0.91)                         # over the block (x 520 … 920 mm)
    lowest = float(pts[over, 2].min())
    check("Avoid other parts on, the lift down: the hose lies on the block, not in it", lowest > 0.40, f"{lowest:.3f}")
    with override():
        bpy.ops.ed.undo_push(message="Set up the avoid model")           # (as the buttons would have pushed it)
    wiggle()
    return 1.0


@step
def s_route_start():
    with override():
        r = bpy.ops.fresing.flex_route("INVOKE_DEFAULT", True)
    check("Shape the route starts", r == {"RUNNING_MODAL"}, str(r))
    pts = line()
    S["at"] = pts[len(pts) // 2 + 4]                       # a point on the hose over the block
    S["xy"] = pixel(S["at"])
    ev("MOUSEMOVE", "NOTHING", S["xy"])
    return 0.5


@step
def s_route_add():
    hot = mod("blender.ops_route")._DRAW["hot"]
    check("the mouse on the hose's line: it is under the mouse", hot is not None and hot[0] == "line", str(hot))
    ev("LEFTMOUSE", "PRESS", S["xy"])
    return 0.5


@step
def s_route_drag():
    check("a press on the line adds a via point", vias() == 1, str(vias()))
    x, y = S["xy"]
    for k in range(1, 6):                                   # dragged up 100 px
        ev("MOUSEMOVE", "NOTHING", (x, y + 20 * k))
    S["to"] = (x, y + 100)
    return 0.5


@step
def s_route_release():
    ev("LEFTMOUSE", "RELEASE", S["to"])
    return 0.5


@step
def s_route_enter():
    via = mod("blender.flex_route").stops_now(item())[1][0]
    S["via"] = via
    up = float(via[2] - S["at"][2])
    miss = float(np.linalg.norm(line() - via, axis=1).min())
    check("dragged up: the via point went up with the mouse", up > 0.05, f"{up * 1000:.0f} mm")
    check("… and the hose runs through it", miss < 0.1 * MM, f"{miss * 1000:.3f} mm")
    shot("route_dragged")
    win, area, region = ui()
    ev("RET", "PRESS", S["to"])
    ev("RET", "RELEASE", S["to"])
    return 0.5


@step
def s_after_enter():
    check("Enter: done, the via point stays", vias() == 1 and mod("blender.ops_route")._DRAW["item"] is None)
    with override():
        bpy.ops.ed.undo()
    return 1.0


@step
def s_undo():
    check("undo takes the edit back", vias() == 0, str(vias()))
    with override():
        bpy.ops.ed.redo()
    return 1.0


@step
def s_redo():
    check("redo brings the via point again", vias() == 1, str(vias()))
    with override():
        r = bpy.ops.fresing.flex_route("INVOKE_DEFAULT", True)
    via = mod("blender.flex_route").stops_now(item())[1][0]
    S["dot"] = pixel(via)
    ev("MOUSEMOVE", "NOTHING", S["dot"])
    return 0.5


@step
def s_remove():
    hot = mod("blender.ops_route")._DRAW["hot"]
    check("the mouse on the dot: the dot is under the mouse", hot is not None and hot[0] == "dot", str(hot))
    ev("X", "PRESS", S["dot"])
    ev("X", "RELEASE", S["dot"])
    return 0.5


@step
def s_esc():
    check("X over the dot removes it", vias() == 0, str(vias()))
    ev("ESC", "PRESS", S["dot"])
    ev("ESC", "RELEASE", S["dot"])
    return 0.5


@step
def s_after_esc():
    check("Esc: the route as it was (the via point back)", vias() == 1, str(vias()))
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
