"""Real-app test, clash check (task 0065): the two-arm test model, Build, Check for clashes (the modal operator with
its progress, as a click), the row, a click on it (frame, selection, red overlay, the view zooms, materials untouched),
the marker, Cancel, the render-queue note, Build again clears the result, save and open again.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_clash.py
Screenshots and ui_test_clash.log go to $UITEST_OUT (default ~/fresing_ui_test_clash).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_clash"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_clash.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_clash.log"), "w")
RESULTS = []
STATE = {}


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


def op(_idname, _how="EXEC_DEFAULT", **kw):
    """Call an operator like a button press (with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)(_how, True, **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def clash():
    return mod("blender.clash")


def settings():
    return bpy.context.scene.fresing.clash


def open_panels():
    """6 Animation and its Clash check start closed: copies that start open (children registered again after)."""
    parent = bpy.types.FRESING_PT_animation
    kids = [c for c in bpy.types.Panel.__subclasses__() if getattr(c, "bl_parent_id", "") == "FRESING_PT_animation"]
    for c in kids:
        bpy.utils.unregister_class(c)
    bpy.utils.unregister_class(parent)
    parent.bl_options = set(parent.bl_options) - {"DEFAULT_CLOSED"}
    bpy.utils.register_class(parent)
    for c in kids:
        if c.__name__ == "FRESING_PT_clash":
            c.bl_options = set(c.bl_options) - {"DEFAULT_CLOSED"}
        bpy.utils.register_class(c)


def build():
    a = bpy.context.scene.fresing.animations["Arms meet"]
    s = bpy.context.scene.fresing
    s.animations_index = list(s.animations).index(a)
    return op("fresing.anim_build")


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
        res = bpy.ops.fresing.import_step(filepath=MODEL, quality="normal")
    log("import", res, bpy.context.scene.fresing.last_message)
    return 1.0


@step
def s_wait():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((1, 0, 0, 0))                    # from the top
    r3d.view_location = Vector((0.4, 0.25, 0.0))
    r3d.view_distance = 3.0
    area.spaces.active.shading.type = "SOLID"
    STATE["view"] = r3d.view_location.copy()
    open_panels()
    redraw()
    return 1.0


@step
def s_set_up():
    sc = bpy.context.scene
    s = sc.fresing
    a = s.animations.add()
    a.name, a.tail, a.fps = "Arms meet", 0.0, "25"
    mod("blender.tour").clash_arms(sc, a)
    st = clash().state(sc)
    check("before Build: nothing to check yet", not st["built"] and not st["checked"])
    r = build()
    check("Build", r == {"FINISHED"} and s.anim_baked == "Arms meet")
    st = clash().state(sc)
    check("header: Not checked since the last Build", st["built"] and st["text"] == "Not checked since the last Build",
          st["text"])
    # the render queue's note for an animation never checked
    n = len(s.queue)
    r = op("fresing.queue_add", kind="ANIMATION", name="Arms meet", start=False)
    check("queue note: not checked", r == {"FINISHED"} and "was not checked for clashes" in s.last_message
          and len(s.queue) == n + 1, s.last_message)
    s.queue.remove(len(s.queue) - 1)
    STATE["mats"] = {n: [sl.material.name if sl.material else "" for sl in named(n).material_slots]
                     for n in ("ARM.A", "ARM.B")}
    with override():
        r = bpy.ops.fresing.clash_check("INVOKE_DEFAULT")
    check("Check for clashes starts (with its progress)", r == {"RUNNING_MODAL"}, f"{r}")
    STATE["t0"] = time.time()
    return 0.2


@step
def s_running():
    rt = clash().runtime(bpy.context.scene)
    if rt.get("running"):
        STATE["saw_running"] = True
        wiggle()
        return "wait"
    check("the check ran and finished", STATE.get("saw_running", False) or settings().checked,
          f"{time.time() - STATE['t0']:.1f} s")
    return 0.5


@step
def s_result():
    sc = bpy.context.scene
    c = settings()
    st = clash().state(sc)
    check("header: 1 clash", st["text"] == "1 clash", st["text"])
    rows = [r for r in c.rows if r.kind == "CLASH"]
    ok = len(rows) == 1 and {rows[0].label_a, rows[0].label_b} == {"ARM.A", "ARM.B"}
    check("the list: ARM.A × ARM.B", ok, "; ".join(f"{r.label_a} × {r.label_b}" for r in c.rows))
    if ok:
        r = rows[0]
        check("6.0 mm deep (±0.2), until the last frame",
              abs(r.depth * 1000 - 6.0) < 0.2 and r.frame_to == sc.frame_end,
              f"{r.depth * 1000:.2f} mm, frames {r.frame_from}-{r.frame_to}")
        marks = [m for m in sc.timeline_markers if m.name.startswith(clash().MARK)]
        check("a marker at the start of the clash", len(marks) == 1 and marks[0].frame == r.frame_from,
              ", ".join(f"{m.name}@{m.frame}" for m in marks))
    sc.frame_set(1)
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
    c.rows_index = 0                                       # a click on the row
    wiggle()
    return 1.0


@step
def s_clicked():
    sc = bpy.context.scene
    c = settings()
    r = c.rows[0]
    check("click: the time line at the deepest moment", abs(sc.frame_current + sc.frame_subframe - r.deep) < 1e-3,
          f"{sc.frame_current} vs {r.deep}")
    sel = {o.get("fr_name") for o in bpy.context.selected_objects}
    check("click: both arms selected", sel == {"ARM.A", "ARM.B"}, f"{sel}")
    check("click: both drawn red (an overlay)", set(clash().red_names()) == {named("ARM.A").name, named("ARM.B").name}
          and clash()._DRAW["handle"] is not None)
    mats = {n: [sl.material.name if sl.material else "" for sl in named(n).material_slots] for n in ("ARM.A", "ARM.B")}
    check("materials untouched", mats == STATE["mats"], f"{mats}")
    win, area, region, sb = ui()
    moved = (area.spaces.active.region_3d.view_location - STATE["view"]).length
    check("click: the view zoomed to the two arms", moved > 1e-3, f"{moved:.3f} m")
    shot("01_clash_red")
    # Cancel: a second check stopped at once keeps the result before it
    with override():
        r1 = bpy.ops.fresing.clash_check("INVOKE_DEFAULT")
    r2 = op("fresing.clash_cancel")
    STATE["cancel"] = (r1, r2)
    return 0.5


@step
def s_cancelled():
    rt = clash().runtime(bpy.context.scene)
    if rt.get("running"):
        wiggle()
        return "wait"
    c = settings()
    check("Cancel stops the check, the result stays", STATE["cancel"] == ({"RUNNING_MODAL"}, {"FINISHED"})
          and c.checked and c.clashes == 1 and "cancelled" in bpy.context.scene.fresing.last_message,
          f"{STATE['cancel']} {bpy.context.scene.fresing.last_message}")
    s = bpy.context.scene.fresing
    r = op("fresing.queue_add", kind="ANIMATION", name="Arms meet", start=False)
    check("queue note: has a clash", r == {"FINISHED"} and "has 1 clash" in s.last_message, s.last_message)
    s.queue.remove(len(s.queue) - 1)
    clash().hide_red()
    path = os.path.join(OUT, "clash_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    c = settings()
    st = clash().state(sc)
    check("reopened: the result is kept", c.checked and len(c.rows) == 1 and st["text"] == "1 clash", st["text"])
    # Build again with another end: the result no longer fits and goes (markers too)
    a = sc.fresing.animations["Arms meet"]
    a.blocks[0].to_angle = math.radians(-80)
    r = build()
    check("Build again", r == {"FINISHED"})
    wiggle()
    return 1.5


@step
def s_rebuilt():
    sc = bpy.context.scene
    c = settings()
    st = clash().state(sc)
    marks = [m for m in sc.timeline_markers if m.name.startswith(clash().MARK)]
    check("Build again clears the result and its markers", not c.checked and len(c.rows) == 0 and not marks,
          f"{st['text']}, {len(c.rows)} rows, {len(marks)} markers")
    check("header after the new Build: Not checked since the last Build",
          st["text"] == "Not checked since the last Build", st["text"])
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
        wiggle()                                         # events keep the import's timer going
        return 0.5
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
