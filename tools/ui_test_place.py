"""Real-app test, task 0292: Place and Remove in the real app.

On the test crane with the crane lesson's joints, cylinder and animation, in the workspace All functions:

* the boom clicked in the view (BOOM.ASM selected), its lock clicked open; 2 Structure > Place open: the arrows and
  rings are wanted (the gizmo group's poll);
* Place's + step (a button press with its undo step): the boom moves 10 mm up and its joint's axis goes along; Ctrl+Z
  puts both back;
* Move with mouse: X, 1 0 0, Enter – the boom moves 100 mm along X and stays; the header showed the move while it ran;
* the crane selected, Delete: the Remove window opens and lists what goes, nothing is gone yet; Remove: the crane, its
  2 joints, the cylinder and the animation step are gone; Ctrl+Z: all of it is back (one undo step);
* the Client view: Delete is swallowed by the lock, no window.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_place.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_place)."""

import importlib
import math
import os
import time
import traceback
import types

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_place"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_place.log"), "w", encoding="utf-8")
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


def asm():
    return next(o for o in bpy.context.scene.objects if o.get("fr_name") == "BOOM.ASM")


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


def place():
    return tuple(round(v, 4) for v in asm().matrix_world.translation)


def turn():
    return asm().matrix_world.to_euler()


def modal():
    return [o.bl_idname for o in view()[0].modal_operators]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def scene():
    return bpy.context.scene


def joint():
    return mod("blender.joints").find(scene(), "Boom")


def axis_z():
    return mod("blender.joints").axis_world(joint())[0].z


def ctrl_z():
    xy = S.get("xy") or (view()[2].x + 300, view()[2].y + 300)
    win = view()[0]
    win.event_simulate(type="Z", value="PRESS", x=xy[0], y=xy[1], ctrl=True, unicode="z")
    win.event_simulate(type="Z", value="RELEASE", x=xy[0], y=xy[1], ctrl=True)


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
        bpy.ops.ed.undo_push(message="Crane set up")
        bpy.ops.view3d.view_all()
    return 1.0


@step
def s_focus():
    _win, _area, region = view()                  # the first click into a region only focuses it
    click(xy=(region.x + region.width // 2, region.y + 8))
    return 0.5


@step
def s_select():
    click()
    return 0.6


@step
def s_unlock():
    check("A click on the boom selects its subassembly", asm().select_get(),
          str([o.name for o in bpy.context.selected_objects][:4]))
    with override():
        res = bpy.ops.fresing.place_lock("EXEC_DEFAULT", True, name=asm().name)
    check("The lock beside its name frees the boom", res == {"FINISHED"} and not any(asm().lock_location))
    mod("blender.panels").open_to("FRESING_PT_place")
    for a in view()[0].screen.areas:
        a.tag_redraw()
    return 0.8


@step
def s_gizmo():
    with override():
        wanted = mod("blender.ui_place")._wanted(bpy.context)
    pn = mod("blender.panels")
    check("Place open, the boom free: the arrows and rings are shown", wanted,
          f"open {pn.is_open('FRESING_PT_place')} {pn.is_open('FRESING_PT_structure')} mode {bpy.context.mode} "
          f"target {getattr(mod('blender.place').target(bpy.context), 'name', None)} "
          f"refused '{mod('blender.place').refused(bpy.context)}'")
    S["z0"], S["axis0"] = asm().matrix_world.translation.z, axis_z()
    with override():
        scene().fresing.place.step_move = "10"
        res = bpy.ops.fresing.place_step("EXEC_DEFAULT", True, index=2, sign=1)
    check("Place + on Z: done", res == {"FINISHED"}, str(res))
    return 0.6


@step
def s_stepped():
    dz = asm().matrix_world.translation.z - S["z0"]
    check("The boom moved 10 mm up", abs(dz - 0.01) < 1e-5, f"{dz * 1000:.2f} mm")
    check("… and its joint's axis went along", abs(axis_z() - S["axis0"] - 0.01) < 1e-5,
          f"{(axis_z() - S['axis0']) * 1000:.2f} mm")
    ctrl_z()
    return 1.0


@step
def s_undone():
    dz = asm().matrix_world.translation.z - S["z0"]
    check("Ctrl+Z puts the boom back", abs(dz) < 1e-5, f"{dz * 1000:.2f} mm")
    check("… and its joint's axis", joint() is not None and abs(axis_z() - S["axis0"]) < 1e-5)
    S["x0"] = asm().matrix_world.translation.x
    _w, _a, region = view()
    S["xy"] = (region.x + region.width // 2, region.y + region.height // 2)
    move(S["xy"])
    with override():
        res = bpy.ops.fresing.place_mouse("INVOKE_DEFAULT", mode="MOVE")
    S["mouse"] = res
    return 0.4


@step
def s_mouse_keys():
    check("Move with mouse starts", "RUNNING_MODAL" in S["mouse"], str(S["mouse"]))
    S["running"] = mod("blender.ops_place").RUNNING[0]
    for k in ("X", "ONE", "ZERO", "ZERO"):
        tap(k)
    return 0.4


@step
def s_mouse_enter():
    tap("RET")
    return 0.8


@step
def s_mouse_done():
    dx = asm().matrix_world.translation.x - S["x0"]
    check("While it ran it said so (Move …)", S["running"] == "MOVE", S["running"])
    check("X 1 0 0 Enter: the boom moved 100 mm along X and stays", abs(dx - 0.1) < 1e-5, f"{dx * 1000:.2f} mm")
    check("… its CAD place moved (Build and poses keep it)", mod("blender.place").is_placed(asm()))
    root = next(o for o in scene().objects if o.get("fr_root"))
    for o in bpy.context.selected_objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    S["parts"] = sum(1 for o in scene().objects if o.get("fr_kind") == "part")
    S["joints"], S["cyl"] = len(scene().fresing.joints), len(scene().fresing.cylinders)
    tap("DEL")
    return 1.5


@step
def s_window():
    fw = mod("blender.form_window")
    lk = mod("blender.lock")
    check("Delete opens the Remove window", fw.is_open("fresing.remove"),
          f"kept {lk.KEPT[0]} last key {lk.LAST_KEY[0]} quiet {lk.keys_quiet()} note {mod('blender.place').NOTE[0]} "
          f"windows {len(bpy.context.window_manager.windows)} sel {[o.name for o in bpy.context.selected_objects][:3]}")
    n = sum(1 for o in scene().objects if o.get("fr_kind") == "part")
    check("… and nothing is gone yet", n == S["parts"], f"{n} parts")
    p = mod("blender.remove").plan(scene(), [next(o for o in scene().objects if o.get("fr_root"))])
    check("The window's list: 20 parts, 2 joints, 1 cylinder",
          (p["parts"], p["joints"], p["cylinders"]) == (20, 2, 1), str((p["parts"], p["joints"], p["cylinders"])))
    with override():
        res = fw.press_ok("fresing.remove", bpy.context)
    check("Remove removes it", res == {"FINISHED"} and scene().fresing.model_count == 0
          and not len(scene().fresing.joints) and not len(scene().fresing.cylinders), str(res))
    check("The window closed", not fw.is_open("fresing.remove"))
    return 1.0


@step
def s_undo_remove():
    ctrl_z()
    return 1.5


@step
def s_back():
    n = sum(1 for o in scene().objects if o.get("fr_kind") == "part")
    check("Ctrl+Z brings the crane back", n == S["parts"] and scene().fresing.model_count == 1, f"{n} parts")
    check("… with its joints and its cylinder", (len(scene().fresing.joints), len(scene().fresing.cylinders))
          == (S["joints"], S["cyl"]))
    check("… its joints still work", all(mod("blender.joints").is_valid(j) for j in scene().fresing.joints))
    S["swallowed"] = mod("blender.lock").SWALLOWED[0]
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 1.0


@step
def s_client_del():
    root = next(o for o in scene().objects if o.get("fr_root"))
    root.select_set(True)
    _w, _a, region = view()
    tap("DEL", (region.x + region.width // 2, region.y + region.height // 2))
    return 1.0


@step
def s_client_done():
    fw = mod("blender.form_window")
    check("Client view: Delete is swallowed by the lock, no Remove window",
          mod("blender.lock").SWALLOWED[0] > S["swallowed"] and not fw.is_open("fresing.remove"))
    check("Client view: the crane is still there", scene().fresing.model_count == 1)
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
