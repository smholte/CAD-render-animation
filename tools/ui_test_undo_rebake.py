"""Real-app test, task 0187 (bug hunt 6 row 4): Ctrl+Z after the cables were worked out again for a new vessel speed
must not show the new speed with the cable shapes of the old one. The sea cable test model is built, the vessel speed
changes, the re-bake job runs; any other action; Undo – the app works the cables out again.

    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_undo_rebake.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_undo_rebake)."""

import importlib
import os
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_undo_rebake"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_sea.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_undo_rebake.log"), "w")
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


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def wiggle():
    win, _area, region = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def moved():
    return mod("blender.vessel_motion").moved_since(bpy.context.scene, mod("blender.paths").MOTION_KEY)


def idle():
    return not mod("blender.rebake").running() and not mod("blender.rebake")._STATE["pending"]


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    return 1.0


@step
def s_built():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    paths, sea, animation = mod("blender.paths"), mod("blender.paths_sea"), mod("blender.animation")
    sea.set_up_test_model(sc)
    animation.bake(sc, sc.fresing.animations[sea.TEST_ANIMATION])
    with override():
        bpy.ops.ed.undo_push(message="Built")
    check("the sea cable is built", paths._baked(sc) and not moved())
    wm = sc.fresing.weather
    wm.enabled = True
    wm.vessel_speed = 1.0                                   # the seabed moves: the cables are worked out again
    it = paths.find(sc, sea.TEST_CABLE)
    it.sea_speed = "WEATHER"
    with override():
        bpy.ops.ed.undo_push(message="Vessel speed")        # (the step the property change pushes: before the re-bake)
    S["t"] = time.time()
    return 1.0


@step
def s_rebaked():
    if time.time() - S["t"] < 3.0 or not idle():
        wiggle()
        return "wait"
    check("the re-bake worked the cable out for the new speed", not moved())
    S["key"] = bpy.context.scene.get(mod("blender.paths").MOTION_KEY)
    with override():
        bpy.ops.ed.undo_push(message="Another action")
    bpy.context.scene.fresing.last_message = "another action"
    with override():
        bpy.ops.ed.undo()                                   # what Ctrl+Z calls (a simulated key press did nothing)
    S["t"] = time.time()
    return 1.0


@step
def s_undone():
    if time.time() - S["t"] < 4.0 or not idle():
        wiggle()
        return "wait"
    sc = bpy.context.scene
    check("after Undo the cables are worked out for the motion the scene has (no old shapes with new water)",
          not moved(), str(sc.get(mod("blender.paths").MOTION_KEY)))
    check("the animation is still built", mod("blender.paths")._baked(sc))
    return 1.0


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
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
