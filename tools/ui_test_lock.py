"""Real-app test, task 0213: the Client view's lock holds (bug hunt 0209, rows 2, 9, 23, 24).

* Row 9: Client view → Import STEP → an undoable action that adds no object (a family tick) → Ctrl+Z: every object
  still carries the lock's mark and cannot be clicked (the camera and the floor came back free).
* Row 24: the buttons of the functions the Client view shows work there (new camera view, Save scene, every paint
  scheme).
* Row 2: every way Blender offers to bring an Outliner back while locked – the editor-type menu of the area that
  replaced it, Shift+F9 over it, a new window, another of Blender's workspaces (Ctrl+Page Up), the area maximised with
  Ctrl+Space – ends with no Outliner, so nothing can be selected and deleted; the model keeps every object.
* Row 23: in Full access, a Set-up window step, then an unrelated action and Ctrl+Z: the step stays.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_lock.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_lock)."""

import importlib
import os
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lock"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lock.log"), "w")
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


def main_win():
    return bpy.context.window_manager.windows[0]


def view():
    win = main_win()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def centre(area):
    return area.x + area.width // 2, area.y + area.height // 2


def key_at(win, xy, k, **mods):
    x, y = xy
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, **mods)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, **mods)


def info_area(win=None):
    """The area that showed the Outliner before the lock (Info now)."""
    win = win or main_win()
    return next((a for a in win.screen.areas if a.type == "INFO"), None)


def outliners():
    """Every Outliner area of every window (none may stay while the lock is on)."""
    return [(w.screen.name, a.type) for w in bpy.context.window_manager.windows for a in w.screen.areas
            if a.type == "OUTLINER"]


def try_delete():
    """What a user would do in an Outliner: Select all, Delete. Returns how many objects are left."""
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type != "OUTLINER":
                continue
            region = next(r for r in a.regions if r.type == "WINDOW")
            try:
                with bpy.context.temp_override(window=w, screen=w.screen, area=a, region=region):
                    bpy.ops.outliner.select_all(action="SELECT")
                    bpy.ops.outliner.delete()
            except Exception as exc:  # noqa: BLE001
                log("delete refused:", exc)
    return len(bpy.data.objects)


def held(route):
    """After one route: no Outliner anywhere and every object still there and locked."""
    lock = mod("blender.lock")
    left = outliners()
    count = try_delete()
    check(f"row 2, {route}: the Outliner does not come back while locked, nothing can be deleted",
          not left and count == S["count"] and lock.ON[0], f"outliners {left}, {count} of {S['count']} objects")


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_esc():
    S["overlap"] = bpy.context.preferences.system.use_region_overlap      # put back at the end: Blender saves
    bpy.context.preferences.system.use_region_overlap = False             # changed preferences when it closes
    win, _area, region = view()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    return 0.4


@step
def s_esc2():
    win, _area, region = view()
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 0.8


@step
def s_client():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    lock = mod("blender.lock")
    check("Client view: the lock is on, the Outliner is replaced", lock.ON[0] and not outliners()
          and info_area() is not None, str([a.type for a in main_win().screen.areas]))
    with override():
        bpy.ops.fresing.import_step("EXEC_DEFAULT", True, filepath=CRANE, quality="draft")
    return 1.0


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    return 1.0


@step
def s_tick():
    lock = mod("blender.lock")
    check("row 9: after the import every object carries the lock's mark", lock.marked() == len(bpy.data.objects),
          f"{lock.marked()} of {len(bpy.data.objects)}")
    S["count"] = len(bpy.data.objects)
    with override():                         # an undoable action that adds no object
        bpy.ops.fresing.family_toggle("EXEC_DEFAULT", True, family="motion")
    S["ticks"] = dict(mod("blender.workspaces").ticks(bpy.context.scene))
    check("row 9: the family tick is set", "motion" in S["ticks"], str(S["ticks"]))
    return 0.8


@step
def s_undo():
    win, area, _region = view()
    key_at(win, centre(area), "Z", ctrl=True)
    return 1.5


@step
def s_undone():
    lock = mod("blender.lock")
    sc = bpy.context.scene
    free = [o.name for o in bpy.data.objects if lock.MARK not in o or not o.hide_select]
    check("row 9: Ctrl+Z took back the family tick only, the model is still there",
          "motion" not in mod("blender.workspaces").ticks(sc) and len(bpy.data.objects) == S["count"] > 20,
          f"{len(bpy.data.objects)} of {S['count']} objects")
    check("row 9: Ctrl+Z after an import leaves no object free (camera and floor included)", lock.ON[0] and not free,
          str(free))
    # ---- row 24: what the Client view shows works there ----
    with override():
        polls = {"camera_add": bpy.ops.fresing.camera_add.poll(), "shot_save": bpy.ops.fresing.shot_save.poll(),
                 "queue_schemes": bpy.ops.fresing.queue_schemes.poll()}
    check("row 24: New camera view, Save scene and Every paint scheme work in the Client view", all(polls.values()),
          str(polls))
    # ---- row 2, route 1: the editor-type menu of the area that replaced the Outliner (the menu sets this) ----
    info_area().ui_type = "OUTLINER"
    return 0.6


@step
def s_menu_route():
    held("editor-type menu")
    win = main_win()
    key_at(win, centre(info_area()), "F9", shift=True)           # route 2: Shift+F9 over it
    return 0.6


@step
def s_key_route():
    held("Shift+F9")
    names = [w.name for w in bpy.data.workspaces]
    S["workspace"] = main_win().workspace.name
    log("Blender's workspaces:", names)
    win, area, _region = view()
    key_at(win, centre(area), "PAGE_UP", ctrl=True)              # route 3: another of Blender's workspaces
    return 1.0


@step
def s_workspace_route():
    log("now in workspace", main_win().workspace.name)
    held("Ctrl+Page Up to another workspace")
    win = main_win()
    if win.workspace.name != S["workspace"]:
        win.workspace = bpy.data.workspaces[S["workspace"]]
    return 1.0


@step
def s_back():
    check("back in the app's own workspace", main_win().workspace.name == S["workspace"])
    with override():                                             # route 4: Window > New Window
        bpy.ops.wm.window_new()
    return 1.0


@step
def s_new_window():
    wins = bpy.context.window_manager.windows
    check("a new window opened", len(wins) == 2, str(len(wins)))
    if len(wins) == 2:
        a = next((a for a in wins[1].screen.areas if a.type != "VIEW_3D"), wins[1].screen.areas[0])
        a.ui_type = "OUTLINER"
    return 0.6


@step
def s_new_window_route():
    held("a new window")
    wins = bpy.context.window_manager.windows
    if len(wins) == 2:
        w = wins[1]
        with bpy.context.temp_override(window=w, screen=w.screen, area=w.screen.areas[0]):
            bpy.ops.wm.window_close()
    return 1.0


@step
def s_maximise():
    win = main_win()
    key_at(win, centre(info_area()), "SPACE", ctrl=True)         # route 5: the area maximised with Ctrl+Space
    return 1.0


@step
def s_maximised():
    win = main_win()
    check("Ctrl+Space maximised the Info area", win.screen.show_fullscreen or len(win.screen.areas) == 1,
          f"{len(win.screen.areas)} areas")
    win.screen.areas[0].ui_type = "OUTLINER"
    return 0.6


@step
def s_maximised_route():
    held("Ctrl+Space, then the editor-type menu")
    win = main_win()
    key_at(win, centre(win.screen.areas[0]), "SPACE", ctrl=True)
    return 1.0


@step
def s_unmaximised():
    win = main_win()
    check("back to the normal layout", any(a.type == "VIEW_3D" for a in win.screen.areas),
          str([a.type for a in win.screen.areas]))
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    return 1.0


@step
def s_full_access():
    lock = mod("blender.lock")
    check("Full access: the lock is off and the Outliner is back", not lock.ON[0] and lock.marked() == 0
          and outliners(), str(outliners()))
    # ---- row 23: Ctrl+Z of an unrelated action keeps the Set-up window's step ----
    with override():
        bpy.ops.fresing.setup_kind("EXEC_DEFAULT", True, kind="MECH")
        bpy.ops.fresing.setup_go("EXEC_DEFAULT", True, step=2)
    return 0.6


@step
def s_setup_set():
    s = bpy.context.scene.fresing
    S["setup"] = (s.setup_kind, s.setup_step)
    check("row 23: the Set-up step is Mechanism, step 3", S["setup"] == ("MECH", 2), str(S["setup"]))
    with override():                         # an unrelated undoable action
        bpy.ops.fresing.family_toggle("EXEC_DEFAULT", True, family="cnc")
    S["cnc"] = mod("blender.workspaces").family_on(bpy.context.scene, "cnc")
    return 0.8


@step
def s_setup_undo():
    win, area, _region = view()
    key_at(win, centre(area), "Z", ctrl=True)
    return 1.5


@step
def s_setup_undone():
    s = bpy.context.scene.fresing
    check("row 23: Ctrl+Z took back the other action (the CNC family tick)",
          mod("blender.workspaces").family_on(bpy.context.scene, "cnc") != S["cnc"])
    check("row 23: Ctrl+Z of another action keeps the Set-up window on its step", (s.setup_kind, s.setup_step)
          == S["setup"], f"{(s.setup_kind, s.setup_step)} (was {S['setup']})")
    return 0.2


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.context.preferences.system.use_region_overlap = S.get("overlap", True)
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
