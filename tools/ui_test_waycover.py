"""Real-app test, way covers (task 0034): pick the axis, click the parts of five sections (two of them of two
parts), Add section x5, a part twice is refused, Make it, the axis dragged (the covers follow 100 mm per 500 mm),
Flip, Remove section, save and open again, Remove way cover.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_waycover.py
Screenshots and ui_test_waycover.log go to $UITEST_OUT (default ~/fresing_ui_test_waycover).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_waycover"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_waycover_b.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_waycover.log"), "w")
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


def op(_idname, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", True, **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def sidebar_shot(name, height=1500):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def key(k, ctrl=False, shift=False):
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl, shift=shift)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def select(objs, active=None):
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active or objs[-1]



SECTIONS = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
            ["COVER.5"]]


def cover():
    return bpy.context.scene.fresing.waycover


def min_x(o):
    return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)


def open_panel():
    """The Way covers panel starts closed: a copy that starts open."""
    cls = bpy.types.FRESING_PT_waycover
    if "DEFAULT_CLOSED" in cls.bl_options:
        bpy.utils.unregister_class(cls)
        cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
        bpy.utils.register_class(cls)


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
    r3d.view_rotation = Quaternion((math.cos(math.radians(45)), math.sin(math.radians(45)), 0, 0))     # front
    r3d.view_location = Vector((0.5, 0.0, 0.1))
    r3d.view_distance = 2.5
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_axis():
    sc = bpy.context.scene
    joints = mod("blender.joints")
    j = joints.create(sc, "SLIDE", [named("CARRIAGE")], Vector((0.1, 0.15, 0.1)), Vector((1, 0, 0)), name="X axis")
    j.use_limits = True
    j.slide_min, j.slide_max = 0.0, 0.5
    cover().axis = "X axis"
    check("the axis is picked and accepted", mod("blender.waycover").axis_problem(sc) == "")
    r = op("fresing.waycover_read_total")
    check("Read from the axis: 500 mm", r == {"FINISHED"} and abs(cover().total - 0.5) < 1e-5, f"{cover().total}")
    return 0.5


@step
def s_sections():
    for g in SECTIONS:
        select([named(n) for n in g])
        op("fresing.waycover_add")
    c = cover()
    check("five sections added", len(c.sections) == 5, f"{len(c.sections)}")
    wc = mod("blender.waycover")
    check("sections 1 and 3 hold two parts", len(wc.parts_of(bpy.context.scene, c.sections[0])) == 2
          and len(wc.parts_of(bpy.context.scene, c.sections[2])) == 2)
    select([named("COVER.2"), named("COVER.4")])
    r = op("fresing.waycover_add")
    check("a part in a section already is refused", r == {"CANCELLED"} and len(c.sections) == 5, bpy.context.scene.fresing.last_message)
    select([named("CARRIAGE")])
    r = op("fresing.waycover_add")
    check("the carriage (moved by the axis) is refused", r == {"CANCELLED"} and len(c.sections) == 5)
    return 0.5


@step
def s_make():
    sc = bpy.context.scene
    rest = {k: min_x(named(SECTIONS[k][0])) for k in range(5)}
    STATE["rest"] = rest
    r = op("fresing.waycover_make")
    check("Make it", r == {"FINISHED"} and all(mod("blender.waycover").is_made(sc, s) for s in cover().sections))
    check("the state line", mod("blender.waycover").status(sc) == "5 sections · 100 mm each · follows 'X axis'",
          mod("blender.waycover").status(sc))
    mod("blender.joints").set_value(sc.fresing.joints.get("X axis"), 0.5)
    bpy.context.view_layer.update()
    wiggle()
    return 1.0


@step
def s_follow():
    rest = STATE["rest"]
    got = [(min_x(named(SECTIONS[k][0])) - rest[k]) * 1000 for k in range(5)]
    check("axis 500 mm: sections at 100, 200, 300, 400, 500 mm", all(abs(g - 100 * (k + 1)) < 0.05 for k, g in enumerate(got)),
          ", ".join(f"{g:.2f}" for g in got))
    c = cover()
    c.flip = True
    bpy.context.view_layer.update()
    wiggle()
    return 1.0


@step
def s_flip():
    rest = STATE["rest"]
    got = [(min_x(named(SECTIONS[k][0])) - rest[k]) * 1000 for k in range(5)]
    check("Flip: the covers open the other way", all(abs(g + 100 * (k + 1)) < 0.05 for k, g in enumerate(got)),
          ", ".join(f"{g:.2f}" for g in got))
    cover().flip = False
    c = cover()
    c.sections_index = 1
    r = op("fresing.waycover_remove")
    bpy.context.view_layer.update()
    got1 = (min_x(named("COVER.1.PLATE")) - rest[0]) * 1000
    check("Remove section: four sections share the travel (125 mm for the first)", r == {"FINISHED"}
          and len(c.sections) == 4 and abs(got1 - 125) < 0.05, f"{got1:.2f}")
    check("the removed section's part is back in CAD", abs(min_x(named("COVER.2")) - rest[1]) < 2e-5)
    open_panel()
    redraw()
    wiggle()
    return 1.5


@step
def s_screens():
    wiggle()
    sidebar_shot("panel4_waycover", 1700)
    path = os.path.join(OUT, "waycover_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    c = cover()
    wc = mod("blender.waycover")
    check("reopened: axis, four sections, all made", c.axis == "X axis" and len(c.sections) == 4
          and all(wc.is_made(sc, s) for s in c.sections))
    r = op("fresing.waycover_remove_all")
    check("Remove way cover: no sections, the axis stays", r == {"FINISHED"} and len(c.sections) == 0
          and sc.fresing.joints.get("X axis") is not None and len(sc.fresing.joints) == 1)
    shot("04_removed")
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
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
