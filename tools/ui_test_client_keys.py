"""Real-app test, task 0227: in the Client view nothing can be selected or deleted from the keyboard.

The owner (Windows 11, 20 Nov 2026) selected a part with a click in the 3D view while in the Client view, X opened
"Delete selected objects?" and Delete deleted it. The route found: Ctrl+Z right after picking the Client view undid
the pick – the lock went off and the part selected before was selected again. This test does what he could do:

* a part selected in All functions, then Workspace > Client view: the selection is gone, every object unclickable;
* Ctrl+Z: the project stays in the Client view, locked, nothing selected;
* a click on a part, A (select all): nothing selected; a part made clickable by a script, then clicked: taken back;
* X, Delete, Shift+X, Shift+Delete and Tab with the mouse on a part: swallowed by the lock, every object still there,
  still in Object Mode; the 3D view's Object menu > Delete deletes nothing;
* Workspace > Full access: a click selects the part and Delete deletes it, as before.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_client_keys.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_client_keys). Linux only: on GitHub's Windows machine (no
graphics card) Blender opens no window – tried in task 0227, it waited 4 minutes and was stopped. The Windows PC
check's line panel.workspaces checks the undo and the freed part there (no keys: a background Blender has none)."""

import importlib
import os
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_client_keys"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_client_keys.log"), "w", encoding="utf-8")
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


def view():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def boom():
    return next(o for o in bpy.context.scene.objects if o.get("fr_name") == "BOOM")


def part_spot():
    """A window position where the view shows the boom (its middle)."""
    from bpy_extras import view3d_utils
    from mathutils import Vector
    _win, _area, region = view()
    ob = boom()
    box = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    co = view3d_utils.location_3d_to_region_2d(region, region.data, sum(box, Vector()) / 8)
    return int(region.x + co.x), int(region.y + co.y)


def press(k, **mods):
    """A key with the mouse on the boom, as the owner pressed it."""
    win = view()[0]
    x, y = S["xy"]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, **mods)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, **mods)


def click():
    win = view()[0]
    x, y = S["xy"] = part_spot()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


def picked():
    return [o.name for o in bpy.context.selected_objects]


def locked_state():
    lock, workspaces = mod("blender.lock"), mod("blender.workspaces")
    sc = bpy.context.scene
    free = [o.name for o in sc.objects if not o.hide_select]
    return (workspaces.name_of(sc) == "Client view" and lock.ON[0] and not free and not picked()
            and bpy.context.view_layer.objects.active is None), \
        f"{workspaces.name_of(sc)}, lock {lock.ON[0]}, free {free[:3]}, selected {picked()[:3]}"


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
def s_import():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
        bpy.ops.fresing.import_step("EXEC_DEFAULT", True, filepath=CRANE, quality="draft")
    return 1.0


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    with override():
        bpy.ops.view3d.view_all()
    return 1.0


@step
def s_select_first():
    S["count"] = len(bpy.context.scene.objects)
    click()
    return 0.8


@step
def s_client():
    check("All functions: a click on the boom selects it (the click lands on a part)", boom().name in picked(),
          str(picked()[:4]))
    with override():                       # as the Workspace switcher's item does it
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 0.8


@step
def s_client_on():
    ok, detail = locked_state()
    check("Client view: the part selected before is no longer selected, every object unclickable", ok, detail)
    press("Z", ctrl=True)
    return 1.5


@step
def s_after_undo():
    ok, detail = locked_state()
    check("Ctrl+Z in the Client view: still the Client view, locked, nothing selected (before 0227 the lock went off "
          "and the part was selected again)", ok, detail)
    click()
    return 0.8


@step
def s_after_click():
    check("Client view: a click on a part selects nothing", not picked(), str(picked()[:3]))
    press("A")
    return 0.6


@step
def s_after_a():
    check("Client view: A (select all) selects nothing", not picked(), str(picked()[:3]))
    boom().hide_select = False                 # any other way a part could get free (a script, the Properties editor)
    click()
    return 0.8


@step
def s_after_freed():
    ok, detail = locked_state()
    check("Client view: a part made clickable again and clicked is taken back at once", ok and boom().hide_select,
          detail)
    S["swallowed"] = mod("blender.lock").SWALLOWED[0]
    press("X")
    return 0.5


@step
def s_x():
    press("DEL")
    return 0.5


@step
def s_del():
    press("X", shift=True)
    return 0.5


@step
def s_shift_x():
    press("DEL", shift=True)
    return 0.5


@step
def s_shift_del():
    press("TAB")
    return 0.8


@step
def s_keys():
    lock = mod("blender.lock")
    n = lock.SWALLOWED[0] - S["swallowed"]
    check("Client view: X, Delete, Shift+X, Shift+Delete and Tab are swallowed by the lock", n == 5, f"{n} of 5")
    check("Client view: after the keys every object is still there, still in Object Mode",
          len(bpy.context.scene.objects) == S["count"] and bpy.context.mode == "OBJECT",
          f"{len(bpy.context.scene.objects)} of {S['count']} objects, {bpy.context.mode}")
    with override():                       # the 3D view header's Object > Delete
        try:
            bpy.ops.object.delete("EXEC_DEFAULT", True, confirm=False)
        except RuntimeError as exc:
            log("Object > Delete refused:", str(exc).splitlines()[0])
    check("Client view: the Object menu's Delete deletes nothing", len(bpy.context.scene.objects) == S["count"],
          f"{len(bpy.context.scene.objects)} of {S['count']} objects")
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    return 1.0


@step
def s_full():
    lock = mod("blender.lock")
    check("Full access: the lock is off, nothing carries its mark", not lock.ON[0] and lock.marked() == 0)
    click()
    return 0.8


@step
def s_full_click():
    check("Full access: a click on the boom selects it again", boom().name in picked(), str(picked()[:4]))
    S["before_del"] = len(bpy.context.scene.objects)
    press("DEL")
    return 0.8


@step
def s_full_del():
    n = len(bpy.context.scene.objects)
    check("Full access: Delete deletes the selected part as before", n < S["before_del"],
          f"{n} objects, {S['before_del']} before")
    return 0.3


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
