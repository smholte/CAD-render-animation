"""Real-app test, task 0253: Blender's keys outside Full access, F12 / Ctrl+F12 and the right-click menu.

On the test crane in the workspace All functions (not Full access), with the boom selected and the mouse on it:

* every swallowed key of ``lock.BLENDER_KEYS`` that acts in the 3D view (X, Delete, Shift+X, Shift+Delete, Tab,
  Ctrl+Tab, Shift+D, Alt+D, Ctrl+J, Ctrl+P, Alt+P, Ctrl+A, M, Shift+M, Shift+A, Ctrl+H, Ctrl+0 … 5, Ctrl+Page Up / Down,
  I, Alt+I, K) is pressed: each is counted as swallowed, and afterwards objects, names, parents, visibility, the mode,
  the workspace and the keyframes are unchanged;
* H still hides the boom, Alt+H shows it again;
* F12 / Ctrl+F12 run the app's render (``fresing.key_render``; its work is replaced by a counter here: a real render
  under xvfb takes minutes);
* a right-click on the boom: the boom becomes the selected one, the Fresing menu opens (drawn, other add-ons' items
  kept); Esc closes it; Return in the open menu runs the entry under the mouse, its first (Zoom to it: the view moves); then each
  entry on the part under the mouse – Zoom to it, Show in 2 Structure, Hide, Show all, Show only this, Show all, Add a
  label here, Add joint here… (the axis pick starts, Esc ends it); a right-click on empty space: Zoom to all, Show all;
* the Client view: a right-click selects nothing, Hide hides in the view only, Shift+D is swallowed by the lock;
* Full access: the right-click shows Blender's own menu, Delete deletes the selected part as before, F12 is Blender's.

    xvfb-run -a -s "-screen 0 1800x1300x24" blender -p 0 0 1800 1300 --app-template fresing_render \\
        --enable-event-simulate --python tools/ui_test_keys.py
The log goes to $UITEST_OUT (default ~/fresing_ui_test_keys). Linux only (as ui_test_client_keys.py)."""

import importlib
import os
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_keys"))
HERE = os.path.dirname(os.path.abspath(__file__))
CRANE = os.path.join(HERE, "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_keys.log"), "w", encoding="utf-8")
RESULTS = []
S = {}

# the swallowed keys pressed in the 3D view: (key, modifiers)
PRESSED = [("X", {}), ("DEL", {}), ("X", {"shift": True}), ("DEL", {"shift": True}), ("TAB", {}),
           ("TAB", {"ctrl": True}), ("D", {"shift": True}), ("D", {"alt": True}), ("J", {"ctrl": True}),
           ("P", {"ctrl": True}), ("P", {"alt": True}), ("A", {"ctrl": True}), ("M", {}), ("M", {"shift": True}),
           ("A", {"shift": True}), ("H", {"ctrl": True}),
           *((k, {"ctrl": True}) for k in ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE")),
           ("PAGE_UP", {"ctrl": True}), ("PAGE_DOWN", {"ctrl": True}), ("I", {}), ("I", {"alt": True}), ("K", {})]


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
    from bpy_extras import view3d_utils
    from mathutils import Vector
    _win, _area, region = view()
    ob = boom()
    box = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    co = view3d_utils.location_3d_to_region_2d(region, region.data, sum(box, Vector()) / 8)
    return int(region.x + co.x), int(region.y + co.y)


def empty_spot():
    _win, _area, region = view()
    return region.x + 40, region.y + region.height - 40          # the top left corner of the view: sky


def move(x, y):
    view()[0].event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)


def press(k, xy=None, **mods):
    win = view()[0]
    x, y = xy or S["xy"]
    move(x, y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, **mods)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, **mods)


def click(button="LEFTMOUSE", xy=None):
    win = view()[0]
    x, y = xy or part_spot()
    S["xy"] = (x, y) if xy is None else S.get("xy", (x, y))
    move(x, y)
    win.event_simulate(type=button, value="PRESS", x=x, y=y)
    win.event_simulate(type=button, value="RELEASE", x=x, y=y)


def picked():
    return [o.name for o in bpy.context.selected_objects]


def state():
    sc = bpy.context.scene
    keys = sum(len(fc.keyframe_points) for a in bpy.data.actions for fc in getattr(a, "fcurves", ()))
    return (sorted((o.name, o.parent.name if o.parent else "", o.hide_get(), o.hide_render) for o in sc.objects),
            bpy.context.mode, len(bpy.data.actions), keys, len(bpy.data.collections),
            mod("blender.workspaces").name_of(sc), bpy.context.window.workspace.name)


def view_place():
    rv3d = view()[2].data
    return tuple(round(v, 4) for v in rv3d.view_location) + (round(rv3d.view_distance, 4),)


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
def s_focus():
    _win, _area, region = view()                  # the first click into a region only focuses it
    click(xy=(region.x + region.width // 2, region.y + 8))
    return 0.5


@step
def s_select():
    lock = mod("blender.lock")
    check("All functions: Blender's keys are swallowed (not Full access)", lock.keys_quiet())
    click()
    return 0.8


@step
def s_keys_start():
    check("A click on the boom selects it", boom().name in picked(), str(picked()[:4]))
    S["state"], S["kept"], S["i"] = state(), mod("blender.lock").KEPT[0], 0
    return 0.1


def _press_next():
    i = S["i"]
    if i >= len(PRESSED):
        return False
    k, mods = PRESSED[i]
    press(k, **mods)
    S["i"] = i + 1
    return True


for _n in range(len(PRESSED)):
    @step
    def s_key():
        _press_next()
        return 0.35


@step
def s_keys_done():
    lock = mod("blender.lock")
    n = lock.KEPT[0] - S["kept"]
    check(f"Each of the {len(PRESSED)} Blender keys pressed in the view is swallowed", n == len(PRESSED),
          f"{n} of {len(PRESSED)}; last {lock.LAST_KEY[0]}")
    after = state()
    check("After the keys nothing changed: objects, names, parents, visibility, mode, keyframes, workspace",
          after == S["state"], "" if after == S["state"] else f"{after[1:]} vs {S['state'][1:]}")
    check("The status bar line says how to get Blender's keys", "Show all of Blender" in lock.KEY_MESSAGE)
    press("H")
    return 0.5


@step
def s_h():
    check("H still hides the boom (Blender's hide is kept)", boom().hide_get())
    press("H", alt=True)
    return 0.5


@step
def s_alt_h():
    check("Alt+H shows it again", not boom().hide_get())
    lock = mod("blender.lock")
    S["renders"] = []
    S["orig_exec"] = lock.FRESING_OT_key_render.execute

    def counted(self, context):                      # a real render under xvfb takes minutes: count the call
        S["renders"].append(bool(self.animation))
        return {"FINISHED"}
    lock.FRESING_OT_key_render.execute = counted
    press("F12")
    return 0.5


@step
def s_f12():
    press("F12", ctrl=True)
    return 0.5


@step
def s_ctrl_f12():
    check("F12 and Ctrl+F12 run the app's Render image / Render animation", S["renders"] == [False, True],
          str(S["renders"]))
    mod("blender.lock").FRESING_OT_key_render.execute = S["orig_exec"]
    cm = mod("blender.context_menu")
    S["opened"], S["drawn"], S["other"] = cm.OPENED[0], cm.DRAWN[0], 0

    def other_addon(self, context):                  # another add-on's item in Blender's object menu
        S["other"] += 1
        self.layout.label(text="Other add-on")
    S["other_fn"] = other_addon
    bpy.types.VIEW3D_MT_object_context_menu.append(other_addon)
    with override():
        bpy.ops.object.select_all(action="DESELECT")
    click("RIGHTMOUSE")
    return 0.8


@step
def s_menu_open():
    cm = mod("blender.context_menu")
    target = cm.target_of(bpy.context.scene, boom())
    check("Right-click on the boom opens the Fresing menu", cm.OPENED[0] > S["opened"] and cm.DRAWN[0] > S["drawn"],
          f"opened {cm.OPENED[0] - S['opened']}, drawn {cm.DRAWN[0] - S['drawn']}")
    check("… on the part under the mouse, which is now the selected one (as a left click)",
          cm.HIT["part"] == boom().name and cm.HIT["target"] == target.name and boom().name in picked(),
          f"{cm.HIT}, selected {picked()[:3]}")
    check("Another add-on's item in Blender's object menu is still drawn in the Fresing menu", S["other"] > 0)
    bpy.types.VIEW3D_MT_object_context_menu.remove(S["other_fn"])
    S["view"] = view_place()
    press("RET")                       # Blender opens the menu with the mouse on its first entry
    return 0.8


@step
def s_menu_first():
    cm = mod("blender.context_menu")
    check("Return in the open menu runs the entry under the mouse, the first: Zoom to it (the view moved)", view_place() != S["view"],
          f"{S['view']} -> {view_place()}")
    return 0.2


def _entry(idname, **kw):
    """Right-click the boom, close the menu (Esc), run an entry on what was hit – as the menu's item does."""
    cm = mod("blender.context_menu")
    op = getattr(bpy.ops.fresing, idname)
    args = dict(kw)
    if "part" in args and args["part"] is None:
        args["part"] = cm.HIT["target"]
    with override():
        return op("EXEC_DEFAULT", True, **args)


@step
def s_rc_entries():
    click("RIGHTMOUSE")
    return 0.6


@step
def s_rc_esc():
    press("ESC")
    return 0.4


@step
def s_entries():
    cm = mod("blender.context_menu")
    target = bpy.data.objects[cm.HIT["target"]]
    S["view"] = view_place()
    with override():
        bpy.ops.view3d.view_all()
    before = view_place()
    _entry("ctx_zoom", part=None)
    check("Zoom to it frames the part", view_place() != before, f"{before} -> {view_place()}")
    _entry("ctx_tree", part=None)
    s = bpy.context.scene.fresing
    row = mod("blender.tree").row_of(bpy.context.scene, target)
    check("Show in 2 Structure picks its row", row is not None and s.tree_index == row, f"row {row}, {s.tree_index}")
    _entry("ctx_hide", part=None)
    check("Hide hides it (also in renders)", boom().hide_get() and boom().hide_render)
    _entry("ctx_show_all")
    check("Show all brings it back", not boom().hide_get())
    _entry("ctx_only", part=None)
    others = [o for o in bpy.context.scene.objects if o.get("fr_kind") == "part"
              and o.name not in {x.name for x in cm._subtree(bpy.context.scene, target)}]
    check("Show only this hides everything else", others and all(o.hide_get() for o in others) and not boom().hide_get())
    _entry("ctx_show_all")
    check("Show all ends Show only", not any(o.hide_get() for o in others))
    n = len(s.callouts)
    _entry("ctx_label", part=cm.HIT["part"], point=cm.HIT["point"])
    check("Add a label here adds a label on the boom at the clicked spot",
          len(s.callouts) == n + 1 and s.callouts[-1].part == boom(), f"{len(s.callouts)} labels")
    return 0.3


@step
def s_joint():
    cm = mod("blender.context_menu")
    S["joints"] = len(bpy.context.scene.fresing.joints)
    with override():
        bpy.ops.fresing.ctx_joint("INVOKE_DEFAULT", True, part=cm.HIT["target"])
    return 0.6


@step
def s_joint_pick():
    target = bpy.data.objects[mod("blender.context_menu").HIT["target"]]
    modal = [o.bl_idname for o in getattr(bpy.context.window, "modal_operators", ())]
    check("Add joint here… selects it and starts Add joint's axis pick",
          target.name in picked() and "FRESING_OT_joint_pick_axis" in modal, f"{picked()[:3]}, {modal}")
    press("ESC")
    return 0.5


@step
def s_empty():
    check("Esc ends the pick: no joint made", len(bpy.context.scene.fresing.joints) == S["joints"])
    click("RIGHTMOUSE", xy=empty_spot())
    return 0.6


@step
def s_empty_menu():
    cm = mod("blender.context_menu")
    check("Right-click on empty space: the menu with Zoom to all / Show all (nothing hit)", cm.HIT["target"] == "",
          str(cm.HIT))
    press("ESC", xy=empty_spot())
    return 0.3


@step
def s_client():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 0.8


@step
def s_client_rc():
    S["count"] = len(bpy.context.scene.objects)
    click("RIGHTMOUSE")
    return 0.6


@step
def s_client_menu():
    cm = mod("blender.context_menu")
    check("Client view: right-click on the boom opens the menu, nothing is selected",
          cm.HIT["part"] == boom().name and cm.HIT["client"] and not picked(), f"{cm.HIT}, {picked()[:3]}")
    press("ESC")
    return 0.3


@step
def s_client_hide():
    _entry("ctx_hide", part=None)
    check("Client view: Hide hides it in the view only (renders unchanged)",
          boom().hide_get() and not boom().hide_render)
    S["sw"] = mod("blender.lock").SWALLOWED[0]
    press("D", shift=True)
    return 0.5


@step
def s_client_key():
    lock = mod("blender.lock")
    check("Client view: Shift+D is swallowed with the lock's message", lock.SWALLOWED[0] == S["sw"] + 1)
    check("Client view: nothing deleted or added", len(bpy.context.scene.objects) == S["count"])
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    return 1.0


@step
def s_full():
    check("Leaving the Client view shows what its menu hid", not boom().hide_get())
    cm = mod("blender.context_menu")
    S["opened"] = cm.OPENED[0]
    click()
    return 0.6


@step
def s_full_rc():
    click("RIGHTMOUSE")
    return 0.6


@step
def s_full_menu():
    cm = mod("blender.context_menu")
    check("Full access: the right-click opens Blender's own menu, not the Fresing one", cm.OPENED[0] == S["opened"]
          and not mod("blender.lock").keys_quiet())
    press("ESC")
    return 0.3


@step
def s_full_del():
    S["before_del"] = len(bpy.context.scene.objects)
    click()
    return 0.5


@step
def s_full_del2():
    press("DEL")
    return 0.8


@step
def s_full_deleted():
    n = len(bpy.context.scene.objects)
    check("Full access: Delete deletes the selected part as before", n < S["before_del"],
          f"{n} objects, {S['before_del']} before")
    check("Full access: F12 is Blender's (the app's F12 is off)", not bpy.ops.fresing.key_render.poll())
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
