"""Real-app test, task 0289: a STEP file dropped on the 3D view comes in exactly as with Import STEP… (1 Import opens,
the panel's Detail and Up axis, the progress, the model's line, the message); Import again from the Imported models
fold takes the stored copy; a model's Up axis changes after the import and Undo puts it back; Remove from cache.

The drop is the call Blender's FileHandler makes (``fresing.import_step`` invoked in the 3D view with ``directory`` and
``files``): a simulated drag from outside Blender is not possible under xvfb.

    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_import_again.py
Screenshots and the log go to $UITEST_OUT (default ~/fresing_ui_test_import_again)."""

import importlib
import os
import shutil
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_import_again"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_import_again.log"), "w")
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


@step
def s_set_up():
    ops_import, panels = mod("blender.ops_import"), mod("blender.panels")
    cache = os.path.join(OUT, "cache")
    shutil.rmtree(cache, ignore_errors=True)
    ops_import.use_cache_root(cache)                      # a cache of its own: the first import is really read
    models = os.path.join(OUT, "models é")
    os.makedirs(models, exist_ok=True)
    S["file"] = os.path.join(models, "crane a.step")
    shutil.copy(MODEL, S["file"])
    s = bpy.context.scene.fresing
    s.import_quality, s.import_up_axis = "draft", "Y"
    panels.fold_sections()
    panels._TAB["v"] = "3"
    bpy.context.window_manager.fresing_tab = "3"
    _win, area, _region = ui()
    area.spaces.active.show_region_ui = False             # the side panel hidden: the drop must show it
    return 1.0


@step
def s_drop():
    ops_import, panels = mod("blender.ops_import"), mod("blender.panels")
    with override():
        ok = bpy.types.FRESING_FH_step.poll_drop(bpy.context)
        res = bpy.ops.fresing.import_step("INVOKE_DEFAULT", True, directory=os.path.dirname(S["file"]),
                                          files=[{"name": os.path.basename(S["file"])}])
    check("a .step file may be dropped on the 3D view", ok)
    check("the drop starts the import in the background, as the button", res == {"RUNNING_MODAL"}, str(res))
    job = ops_import._ACTIVE_JOB
    check("the import job runs", job is not None and not job.done)
    check("1 Import opens", panels.is_open(ops_import.PANEL))
    check("the section tab goes back to All", panels.tab() == "ALL" and bpy.context.window_manager.fresing_tab == "ALL")
    _win, area, _region = ui()
    check("the side panel shows", area.spaces.active.show_region_ui)
    ui_region = next(r for r in area.regions if r.type == "UI")
    check("on the Fresing tab", getattr(ui_region, "active_panel_category", "Fresing") == "Fresing",
          getattr(ui_region, "active_panel_category", ""))
    S["t"] = time.time()
    return 0.5


@step
def s_progress():
    ops_import = mod("blender.ops_import")
    job = ops_import._ACTIVE_JOB
    sc = bpy.context.scene
    if job is not None and not job.done:
        S["seen"] = S.get("seen") or sc.fresing.last_message.startswith("Importing crane a.step")
        wiggle()
        return "wait"
    if sc.fresing.model_count == 0:
        wiggle()
        return "wait"
    check("the progress line showed while it read", S.get("seen", False) or time.time() - S["t"] < 2.0)
    root = mod("blender.build").model_roots(sc)[0]
    check("the panel's Detail was used", root.get("fr_quality") == "draft", str(root.get("fr_quality")))
    check("the panel's Up axis was used", mod("blender.logic").up_axis_of(root) == "Y")
    check("the same message as the button", sc.fresing.last_message == "Imported crane a.step", sc.fresing.last_message)
    return 0.5


@step
def s_again():
    ops_import, ic = mod("blender.ops_import"), mod("core.import_cache")
    items = ic.entries(ops_import.cache_root())
    check("Imported models lists the import", len(items) == 1 and items[0].name == "crane a", str([e.name for e in items]))
    S["id"] = items[0].id if items else ""
    t = time.time()
    with override():
        res = bpy.ops.fresing.import_step("INVOKE_DEFAULT", True, again=S["id"])
    sc = bpy.context.scene
    check("Import again takes the stored copy at once", res == {"FINISHED"} and time.time() - t < 30, str(res))
    check("a second copy of the model is in", sc.fresing.model_count == 2)
    check("it says it came from the cache", "from cache" in sc.fresing.last_message, sc.fresing.last_message)
    return 0.5


@step
def s_up_axis():
    build, logic = mod("blender.build"), mod("blender.logic")
    sc = bpy.context.scene
    root = build.model_roots(sc)[1]
    S["root"] = root.name
    with override():
        bpy.ops.ed.undo_push(message="Before the up axis")
        res = bpy.ops.fresing.model_up_axis("INVOKE_DEFAULT", True, root=root.name, axis="Z")   # as a button: undo step
    check("Up axis: Z up turns the model", res == {"FINISHED"} and logic.up_axis_of(root) == "Z", str(res))
    with override():
        bpy.ops.ed.undo()
    root = bpy.data.objects.get(S["root"])
    check("one Undo puts it back", root is not None and logic.up_axis_of(root) == "Y")
    return 0.5


@step
def s_remove():
    ops_import, ic = mod("blender.ops_import"), mod("core.import_cache")
    with override():
        res = bpy.ops.fresing.cache_remove("EXEC_DEFAULT", entry=S["id"])
    check("Remove from cache frees it", res == {"FINISHED"} and not ic.entries(ops_import.cache_root()), str(res))
    ops_import.use_cache_root(None)
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
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
