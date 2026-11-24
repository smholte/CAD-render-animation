"""Real-app test, task 0293: Copy and Paste in the real app.

On the test crane with the crane lesson's joints, cylinder and animation, in the workspace All functions:

* the crane selected, Ctrl+C (the app's key outside Full access): Copy remembers it;
* Ctrl+V: a copy "TEST.CRANE (2)" beside it with joints "Boom (2)", "Trolley (2)" and its own cylinder, selected and
  free to move; the Move / turn window opens and says what came along; the copy's boom moves by itself;
* Ctrl+Z (one step): the copy is gone, the crane and its joints are as before;
* a right-click on the boom: the menu draws (Copy, Paste here); Paste here at the clicked spot puts the copy there;
  Ctrl+Z again;
* the Client view: Ctrl+V makes no copy.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_copy.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_copy)."""

import importlib
import math
import os
import time
import traceback
import types

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_copy"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_copy.log"), "w", encoding="utf-8")
RESULTS = []
S = {}
CH = {"ONE": "1", "ZERO": "0", "THREE": "3", "X": "x", "Z": "z"}
J0 = {}


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
    """A pixel on the boom itself (a ray through it hits the boom, not the trolley riding on it)."""
    from bpy_extras import view3d_utils
    from mathutils import Vector
    _win, _area, region = view()
    ob = boom()
    box = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector([min(p[i] for p in box) for i in range(3)])
    hi = Vector([max(p[i] for p in box) for i in range(3)])
    dg = bpy.context.evaluated_depsgraph_get()
    for f in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
        co = view3d_utils.location_3d_to_region_2d(region, region.data, lo + (hi - lo) * f)
        if co is None:
            continue
        org = view3d_utils.region_2d_to_origin_3d(region, region.data, co)
        d = view3d_utils.region_2d_to_vector_3d(region, region.data, co)
        hit, _p, _n, _i, what, _m = bpy.context.scene.ray_cast(dg, org, d)
        if hit and what is not None and what.get("fr_name") == "BOOM":
            return int(region.x + co.x), int(region.y + co.y)
    raise RuntimeError("no pixel of the view shows the boom")


def ev(t, value, xy):
    win = view()[0]
    if t in CH and value == "PRESS":           # typed numbers need their character (transform's number input)
        win.event_simulate(type=t, value=value, x=xy[0], y=xy[1], unicode=CH[t])
    else:
        win.event_simulate(type=t, value=value, x=xy[0], y=xy[1])


def tap(t, xy=None):
    xy = xy or S["xy"]
    ev(t, "PRESS", xy)
    ev(t, "RELEASE", xy)


def move(xy):
    view()[0].event_simulate(type="MOUSEMOVE", value="NOTHING", x=xy[0], y=xy[1])


def click(button="LEFTMOUSE", xy=None):
    if xy is None:                              # a second click on the same spot cycles to the object behind it
        for o in bpy.context.selected_objects:   # (Blender's own): start from nothing selected
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
    xy = xy or part_spot()
    S["xy"] = xy
    move(xy)
    tap(button, xy)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def scene():
    return bpy.context.scene


def root(name="TEST.CRANE"):
    return next((o for o in scene().objects if o.get("fr_root") and o.get("fr_name") == name), None)


def key(t, ctrl=False, xy=None):
    xy = xy or S.get("xy") or (view()[2].x + 300, view()[2].y + 300)
    win = view()[0]
    win.event_simulate(type=t, value="PRESS", x=xy[0], y=xy[1], ctrl=ctrl, unicode=t.lower())
    win.event_simulate(type=t, value="RELEASE", x=xy[0], y=xy[1], ctrl=ctrl)


def counts():
    s = scene().fresing
    return s.model_count, len(s.joints), len(s.cylinders)


def pick(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


@step
def s_esc():
    S["overlap"] = bpy.context.preferences.system.use_region_overlap      # put back at the end: Blender saves
    bpy.context.preferences.system.use_region_overlap = False             # changed preferences when it closes
    _win, _area, region = view()
    ev("ESC", "PRESS", (region.x + 300, region.y + 300))
    return 0.4


@step
def s_esc2():
    _win, _area, region = view()
    ev("ESC", "RELEASE", (region.x + 300, region.y + 300))
    return 0.8


@step
def s_import():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
        bpy.ops.fresing.import_step("EXEC_DEFAULT", True, filepath=CRANE, quality="draft")
    return 1.0


@step
def s_imported():
    if scene().fresing.model_count == 0:
        return "wait"
    with override():
        mod("blender.lesson").run(scene(), "crane")
        mod("blender.animation").clear_keys(scene())
        bpy.ops.ed.undo_push(message="Crane set up")
        bpy.ops.view3d.view_all()
    return 1.0


@step
def s_focus():
    _win, _area, region = view()                  # the first click into a region only focuses it
    click(xy=(region.x + region.width // 2, region.y + 8))
    return 0.5


@step
def s_copy():
    pick(root())
    _w, _a, region = view()
    S["xy"] = (region.x + region.width // 2, region.y + region.height // 2)
    move(S["xy"])
    S["before"] = counts()
    key("C", ctrl=True)
    return 0.6


@step
def s_copied():
    cp = mod("blender.copy")
    check("Ctrl+C copies the crane (the app's Copy)", cp.CLIP["names"] == [root().name], str(cp.CLIP))
    check("… and says so", "Copied 'TEST.CRANE'" in scene().fresing.last_message, scene().fresing.last_message)
    key("V", ctrl=True)
    return 2.0


@step
def s_pasted():
    fw = mod("blender.form_window")
    c = counts()
    check("Ctrl+V pastes a second crane with 2 joints and a cylinder", c == (2, 4, 2), str(c))
    r2 = root("TEST.CRANE (2)")
    check("The copy is 'TEST.CRANE (2)', selected and free to move", r2 is not None and r2.select_get()
          and bpy.context.view_layer.objects.active is r2 and not mod("blender.place").locked(r2))
    names = [j.name for j in scene().fresing.joints]
    check("Its joints are 'Boom (2)' and 'Trolley (2)'", names == ["Boom", "Trolley", "Boom (2)", "Trolley (2)"],
          str(names))
    if r2 is not None:
        lo1, hi1 = mod("blender.place").bounds(scene(), root())
        lo2, _hi2 = mod("blender.place").bounds(scene(), r2)
        check("It stands beside the crane", lo2.x > hi1.x, f"{lo2.x:.3f} vs {hi1.x:.3f}")
        note = mod("blender.ui_place").copy_note(r2)
        check("… and says what came along", bool(note) and "2 joints, 1 cylinder" in note[0], str(note[:1]))
    j = mod("blender.joints")
    b2 = next(o for o in scene().objects if o.get("fr_name") == "BOOM" and o.get("fr_uid", "").startswith("~2/"))
    b1 = next(o for o in scene().objects if o.get("fr_name") == "BOOM" and not o.get("fr_uid", "").startswith("~"))
    w1 = b1.matrix_world.copy()
    j.set_value(j.find(scene(), "Boom (2)"), math.radians(30.0))
    bpy.context.view_layer.update()
    check("The copy's boom moves by itself", abs(b2.matrix_world.to_euler().y + math.radians(30.0)) < 1e-4
          and (w1.translation - b1.matrix_world.translation).length < 1e-6)
    S["t_window"] = time.time()
    return 0.5


@step
def s_window():
    fw = mod("blender.form_window")
    if not fw.is_open("fresing.place_window") and time.time() - S["t_window"] < 8.0:
        return "wait"                            # it opens from a timer (a new window takes a moment)
    check("The Move / turn window opens for it", fw.is_open("fresing.place_window"),
          f"{mod('blender.ops_copy').OPENED[0]} windows {len(bpy.context.window_manager.windows)}")
    with override():
        fw.close("fresing.place_window", bpy.context)
    return 1.5


@step
def s_undo():
    pick(root("TEST.CRANE (2)") or root())
    move(S["xy"])
    key("Z", ctrl=True)
    return 1.5


@step
def s_undone():
    c = counts()
    check("Ctrl+Z takes the copy away in one step", c == S["before"] and root("TEST.CRANE (2)") is None, str(c))
    check("… the crane's joints still work", all(mod("blender.joints").is_valid(x) for x in scene().fresing.joints))
    S["drawn"] = mod("blender.context_menu").DRAWN[0]
    click("RIGHTMOUSE")
    return 1.0


@step
def s_menu():
    cm = mod("blender.context_menu")
    check("A right-click on the boom opens the Fresing menu (Copy, Paste here)", cm.DRAWN[0] > S["drawn"],
          f"{cm.DRAWN[0]} {S['drawn']}")
    S["point"] = tuple(cm.HIT["point"])
    tap("ESC")
    return 0.6


@step
def s_paste_here():
    with override():
        res = bpy.ops.fresing.paste("EXEC_DEFAULT", True, here=True, point=S["point"], open_place=False)
    check("Paste here: done", res == {"FINISHED"}, str(res))
    r2 = root("TEST.CRANE (2)")
    if r2 is not None:
        from mathutils import Vector
        lo, hi = mod("blender.place").bounds(scene(), r2)
        mid = (lo + hi) / 2.0
        p = Vector(S["point"])
        check("… the copy stands on the clicked spot", abs(mid.x - p.x) < 1e-3 and abs(mid.y - p.y) < 1e-3
              and abs(lo.z - p.z) < 1e-3, f"mid {tuple(round(v, 3) for v in mid)} spot {S['point']}")
    move(S["xy"])
    key("Z", ctrl=True)
    return 1.5


@step
def s_client():
    check("Ctrl+Z again: one crane", counts() == S["before"], str(counts()))
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 1.0


@step
def s_client_paste():
    move(S["xy"])
    key("V", ctrl=True)
    return 1.0


@step
def s_client_done():
    check("Client view: Ctrl+V makes no copy", counts()[0] == 1, str(counts()))
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
    return 0.8


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
