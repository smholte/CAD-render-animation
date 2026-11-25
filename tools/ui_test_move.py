"""Real-app test, task 0307: moving and turning with G / R in the 3D view sticks, or the app says why it cannot.

On the test crane in the workspace All functions, the boom clicked in the view (its subassembly BOOM.ASM selected):

* G, X, 1 0 0, Enter on the fresh import: the crane is locked in place – Blender's move does not start, nothing
  moves, the status bar names the subassembly and "Unlock in the popup" (before task 0307 the numbers showed in the
  header and the part was back on Enter, without a word);
* task 0338: G opens the Unlock popup by the mouse – Esc, a click outside and × close it with nothing changed; Unlock
  starts Blender's move at once (X 1 0 0 Enter moves it); then Lock it again shows in the top left below the view's
  text: a click within 5 s leaves it (and still deselects), a click after 5 s closes it; a second time Lock it again
  locks the boom again; at UI scale 2 the popup is twice as big and inside the view;
* a right-click on the boom: the menu shows "Unlock so it can move"; its entry unlocks BOOM.ASM;
* G, X, 1 0 0, Enter: the boom moves 100 mm along X and stays (1 s later, after a frame change);
* G, a mouse move, a left click: it moves and stays; R, Z, 3 0, Enter: it turns 30° and stays;
* after Build & play: G, X, 1 0 0, Enter moves nothing and the status bar says the animation is built and where to
  stop it; after Stop it to move joints by hand, G moves again.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_move.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_move)."""

import importlib
import math
import os
import time
import traceback
import types

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_move"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_move.log"), "w", encoding="utf-8")
RESULTS = []
S = {}
CH = {"ONE": "1", "ZERO": "0", "THREE": "3", "X": "x", "Z": "z"}


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
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    with override():
        bpy.ops.view3d.view_all()
    return 1.0


@step
def s_focus():
    _win, _area, region = view()                  # the first click into a region only focuses it
    click(xy=(region.x + region.width // 2, region.y + 8))
    return 0.5


# --- 1. the fresh import: locked in place -----------------------------------------------------------------------------

def _g_x_100():
    """G, X, 1 0 0 (mm) – Enter comes in the next step, as a person types."""
    S["before"], S["stopped"] = place(), mod("blender.place").STOPPED[0]
    mod("blender.place").LAST[0] = ""
    tap("G")


def _typed():
    for k in ("X", "ONE", "ZERO", "ZERO"):
        tap(k)


@step
def s_select():
    click()
    return 0.6


@step
def s_locked_g():
    S["basis"] = asm().matrix_basis.copy()
    check("A click on the boom selects its subassembly", asm().select_get(), str([o.name for o in
                                                                                   bpy.context.selected_objects][:4]))
    _g_x_100()
    return 0.4


@step
def s_locked_typed():
    S["modal"] = modal()
    _typed()                                       # the popup holds the keys: nothing moves, no Blender move
    return 0.3


@step
def s_locked_said():
    pl, pp = mod("blender.place"), mod("blender.place_popups")
    check("Locked in place: G does not start Blender's move (no numbers that come to nothing)",
          "TRANSFORM_OT_translate" not in S["modal"] + modal(), str(S["modal"]))
    check("Locked in place: G opens the Unlock popup by the mouse (task 0338)",
          "FRESING_OT_unlock_popup" in S["modal"] and pp.UNLOCK["on"] and _near_mouse(), str(S["modal"]))
    check("Locked in place: nothing moved", place() == S["before"], f"{place()} was {S['before']}")
    check("Locked in place: the status bar names the subassembly and the popup's Unlock",
          "'BOOM.ASM' is locked in place" in pl.LAST[0] and "Unlock in the popup" in pl.LAST[0]
          and pl.STOPPED[0] == S["stopped"] + 1, pl.LAST[0])
    tap("ESC")
    return 0.4


def _near_mouse():
    pp = mod("blender.place_popups")
    _ar, reg, c = pp.geometry("unlock")
    if c is None:
        return False
    x, y, w, h = c["box"]
    mx, my = S["xy"][0] - reg.x, S["xy"][1] - reg.y
    return 0 <= x - mx <= 60 and y - 10 <= my <= y + h + 10 and x + w <= reg.width and y + h <= reg.height


def _still_locked():
    return all(asm().lock_location) and all(asm().lock_rotation) and place() == S["before"]


@step
def s_pop_esc():
    pp = mod("blender.place_popups")
    check("Esc closes the Unlock popup and nothing changes", not pp.UNLOCK["on"] and _still_locked()
          and "FRESING_OT_unlock_popup" not in modal(), str(modal()))
    tap("G")
    return 0.4


@step
def s_pop_outside():
    _win, _area, region = view()
    S["outside"] = (region.x + 40, region.y + 40)
    move(S["outside"])
    tap("LEFTMOUSE", S["outside"])
    return 0.4


@step
def s_pop_outside_closed():
    pp = mod("blender.place_popups")
    check("A click outside closes it; nothing changes (the boom stays selected and locked)",
          not pp.UNLOCK["on"] and _still_locked() and asm().select_get(), str(modal()))
    move(S["xy"])
    tap("G")
    return 0.4


@step
def s_pop_x():
    xy = mod("blender.place_popups").point("unlock", "x")
    move(xy)
    tap("LEFTMOUSE", xy)
    return 0.4


@step
def s_pop_x_closed():
    check("× closes it; nothing changes", not mod("blender.place_popups").UNLOCK["on"] and _still_locked())
    move(S["xy"])
    tap("G")
    return 0.4


def _unlock_and_move():
    xy = mod("blender.place_popups").point("unlock", "button")
    S["unlock_at"] = xy
    move(xy)
    tap("LEFTMOUSE", xy)
    S["xy"] = xy


@step
def s_pop_unlock():
    _unlock_and_move()
    return 0.4


@step
def s_pop_moving():
    check("Unlock unlocks it and Blender's move starts at once", not any(asm().lock_location)
          and "TRANSFORM_OT_translate" in modal(), str(modal()))
    _typed()
    return 0.3


@step
def s_pop_enter():
    tap("RET")
    return 1.0


@step
def s_again_shown():
    pp = mod("blender.place_popups")
    now, was = place(), S["before"]
    check("… and X, 100, Enter moves it 100 mm", abs(now[0] - was[0] - 0.1) < 1e-4, f"{now} was {was}")
    ar, reg, c = pp.geometry("again")
    ok = c is not None and "FRESING_OT_lock_again" in modal()
    if ok:
        left, top = pp.top_clear(ar, reg)
        x, y, w, h = c["box"]
        ok = x >= left and y + h <= top and x < 40 * pp._scale() + left and y > reg.height / 2
    check("After the move: Lock it again in the top left, below the view's own text", ok,
          str(c["box"] if c else modal()))
    S["again_t"] = time.time()
    _win, _area, region = view()
    S["empty"] = (region.x + region.width - 60, region.y + 60)
    move(S["empty"])
    tap("LEFTMOUSE", S["empty"])                  # within 5 s: it stays, the click still does its job
    return 0.5


@step
def s_again_stays():
    pp = mod("blender.place_popups")
    check("A click within 5 s leaves it up, and still does its own job (the click on empty space deselects)",
          pp.AGAIN["on"] and not asm().select_get(), f"{time.time() - S['again_t']:.1f} s")
    return max(0.2, pp.STAY + 0.3 - (time.time() - S["again_t"]))


@step
def s_again_click():
    tap("LEFTMOUSE", S["empty"])
    return 0.4


@step
def s_again_closed():
    pp = mod("blender.place_popups")
    check("After 5 s a click anywhere closes it; it stays unlocked",
          not pp.AGAIN["on"] and "FRESING_OT_lock_again" not in modal() and not any(asm().lock_location))
    mod("blender.ops_place").set_lock(asm(), True)
    asm().matrix_basis = S["basis"]
    bpy.context.view_layer.update()
    click()
    return 0.6


@step
def s_lock_g():
    _g_x_100()
    return 0.4


@step
def s_lock_unlock():
    _unlock_and_move()
    return 0.4


@step
def s_lock_typed():
    _typed()
    return 0.3


@step
def s_lock_enter():
    tap("RET")
    return 1.0


@step
def s_lock_button():
    xy = mod("blender.place_popups").point("again", "button")
    check("A second time: Lock it again shows", xy is not None)
    if xy:
        move(xy)
        tap("LEFTMOUSE", xy)
    return 0.4


@step
def s_locked_again():
    pp = mod("blender.place_popups")
    check("Lock it again locks exactly what was unlocked, and closes",
          all(asm().lock_location) and all(asm().lock_rotation) and not pp.AGAIN["on"]
          and all(o.lock_location[0] for o in bpy.context.scene.objects
                  if o.get("fr_kind") == "assembly" and o != asm()), str(tuple(asm().lock_location)))
    asm().matrix_basis = S["basis"]
    bpy.context.view_layer.update()
    S["scale"] = bpy.context.preferences.view.ui_scale
    bpy.context.preferences.view.ui_scale = 2.0     # a 2560 px screen's scale
    return 0.8


@step
def s_big_g():
    click()
    return 0.6


@step
def s_big_g2():
    _g_x_100()
    return 0.5


@step
def s_big_check():
    pp = mod("blender.place_popups")
    _ar, reg, c = pp.geometry("unlock")
    ok = c is not None and c["scale"] >= 1.9
    if ok:
        x, y, w, h = c["box"]
        ok = 0 <= x and x + w <= reg.width and 0 <= y and y + h <= reg.height
    check("At UI scale 2 the popup is twice as big and inside the view", ok, str(c["box"] if c else "none"))
    S["xy"] = S["xy"]
    xy = pp.point("unlock", "x")
    if xy:
        move(xy)
        tap("LEFTMOUSE", xy)
    return 0.4


@step
def s_big_done():
    check("… and its × closes it", not mod("blender.place_popups").UNLOCK["on"] and _still_locked())
    bpy.context.preferences.view.ui_scale = S["scale"]
    return 0.8


# --- 2. the right-click menu's Unlock so it can move --------------------------------------------------------------------

@step
def s_rc():
    S["drawn"] = mod("blender.context_menu").DRAWN[0]
    click("RIGHTMOUSE")
    return 0.6


@step
def s_rc_esc():
    tap("ESC")
    return 0.4


@step
def s_unlock():
    cm = mod("blender.context_menu")
    target = bpy.data.objects[cm.HIT["target"]]
    check("The right-click menu offers Unlock so it can move", cm.DRAWN[0] > S["drawn"]
          and mod("blender.place").menu_text(target) == "Unlock so it can move", target.name)
    with override():
        res = bpy.ops.fresing.ctx_unlock("EXEC_DEFAULT", True, part=target.name)
    check("Unlock so it can move unlocks the boom's subassembly", res == {"FINISHED"} and not any(asm().lock_location)
          and not any(asm().lock_rotation), str(tuple(asm().lock_location)))
    return 0.3


# --- 3. G + X + number + Enter, G + mouse + click, R + Z + number + Enter: they stay --------------------------------

@step
def s_g():
    click()
    return 0.6


@step
def s_g2():
    _g_x_100()
    return 0.4


@step
def s_g_typed():
    S["modal"] = modal()
    _typed()
    return 0.3


@step
def s_g_enter():
    tap("RET")
    return 1.0


@step
def s_g_stays():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current + 5)
    bpy.context.scene.frame_set(bpy.context.scene.frame_current - 5)
    now, was = place(), S["before"]
    check("Unlocked: G starts Blender's move", "TRANSFORM_OT_translate" in S["modal"], str(S["modal"]))
    check("G, X, 100, Enter moves the boom 100 mm along X and it stays (1 s later, after a frame change)",
          abs(now[0] - was[0] - 0.1) < 1e-4 and now[1:] == was[1:], f"{now} was {was}")
    check("No message when it can move", mod("blender.place").LAST[0] == "", mod("blender.place").LAST[0])
    return 0.2


@step
def s_drag():
    S["before"] = place()
    tap("G")
    return 0.4


@step
def s_drag_move():
    x, y = S["xy"]
    move((x + 80, y + 30))
    return 0.4


@step
def s_drag_click():
    x, y = S["xy"]
    tap("LEFTMOUSE", (x + 80, y + 30))
    return 1.0


@step
def s_drag_stays():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    moved = sum(abs(a - b) for a, b in zip(place(), S["before"]))
    check("G, a mouse move and a left click move the boom and it stays", moved > 0.01, f"{place()} was {S['before']}")
    return 0.2


@step
def s_r():
    S["turn"] = turn()
    click()
    return 0.6


@step
def s_r2():
    tap("R")
    return 0.4


@step
def s_r_typed():
    for k in ("Z", "THREE", "ZERO"):
        tap(k)
    return 0.3


@step
def s_r_enter():
    tap("RET")
    return 1.0


@step
def s_r_stays():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    d = math.degrees((turn().z - S["turn"].z + math.pi) % (2 * math.pi) - math.pi)
    check("R, Z, 30, Enter turns the boom 30° and it stays", abs(abs(d) - 30) < 0.1, f"{d:.2f}°")
    asm().matrix_basis = S["basis"]              # back on its CAD place for the joint and the Build below
    with override():
        bpy.ops.view3d.view_all()
    return 0.5


# --- 4. after Build & play: the message; after Stop it moves again --------------------------------------------------

@step
def s_build():
    tour = mod("blender.tour")
    scene = bpy.context.scene
    with override():
        tour._boom_joint(scene)
        a = tour._animation(types.SimpleNamespace(s=scene.fresing), "Up")
        tour._joint_step(a, "Boom", 0, 1, 20)
        scene.fresing.animations_index = len(scene.fresing.animations) - 1
        res = bpy.ops.fresing.anim_build("EXEC_DEFAULT", True)
    check("Build & play", res == {"FINISHED"}, str(res))
    return 1.0


@step
def s_built_select():
    click()
    return 0.6


@step
def s_built_g():
    _g_x_100()
    return 0.4


@step
def s_built_typed():
    S["modal"] = modal()
    _typed()
    return 0.3


@step
def s_built_enter():
    tap("RET")
    return 0.8


@step
def s_built_said():
    pl = mod("blender.place")
    check("After Build: G moves nothing and the status bar says the animation is built and where to stop it",
          "TRANSFORM_OT_translate" not in S["modal"] and place() == S["before"]
          and pl.LAST[0].startswith("The animation is built") and "Stop it to move joints by hand" in pl.LAST[0],
          f"{S['modal']} {pl.LAST[0]}")
    with override():
        bpy.ops.fresing.anim_clear("EXEC_DEFAULT", True)
    return 0.8


@step
def s_stopped_select():
    click()
    return 0.6


@step
def s_stopped_g():
    _g_x_100()
    return 0.4


@step
def s_stopped_typed():
    _typed()
    return 0.3


@step
def s_stopped_enter():
    tap("RET")
    return 1.0


@step
def s_stopped_moved():
    now, was = place(), S["before"]
    check("After Stop it to move joints by hand: G moves again", abs(now[0] - was[0] - 0.1) < 1e-4, f"{now} was {was}")
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
