"""Real-app test, cylinders (task 0013): Barrel and Rod from the selection, Add cylinder with real clicks on the
two pins in the view, the cylinder follows the arm, Drives the arm (Fully out, the stroke field), undo/redo, a
Move cylinder animation step, the "Show joint arrows" tick box (NameError before 0.2.24), save and open again,
Remove.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_cylinder.py
Screenshots and ui_test_cylinder.log go to $UITEST_OUT (default ~/fresing_ui_test_cylinder).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Matrix, Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_cylinder"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_cylinder_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_cylinder.log"), "w")
RESULTS = []
STATE = {}
# the luffer (tools/make_test_cylinder.py), metres: arm pivot, barrel pin, rod pin of the cylinder at y = 0.08
P = Vector((0.1, 0.08, 0.6))
B = Vector((0.5, 0.08, 0.15))
R = Vector((0.8, 0.08, 0.45))
L0 = math.hypot(0.3, 0.3)
CLOSED, FULL = L0 - 0.060, 0.190


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


def to_window(world_pt):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(round(region.x + co.x)), int(round(region.y + co.y))


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


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


def named(name, y=None):
    """The object with this CAD name (with ``y``: the one whose parts span that y)."""
    for o in bpy.context.scene.objects:
        if o.get("fr_name") != name:
            continue
        if y is None:
            return o
        parts = [o] if o.type == "MESH" else [d for d in o.children_recursive if d.type == "MESH"]
        ys = [(d.matrix_world @ Vector(c)).y for d in parts for c in d.bound_box]
        if ys and min(ys) - 1e-4 <= y <= max(ys) + 1e-4:
            return o
    return None


def select_only(ob):
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob


def cyl():
    s = bpy.context.scene.fresing
    return s.cylinders[0] if len(s.cylinders) else None


def luff():
    return bpy.context.scene.fresing.joints.get("Luff")


def rod_pin_at(angle):
    return P + Matrix.Rotation(angle, 3, "Y") @ (R - P)


def law_of_cosines(length):
    a, c = (B - P).length, (R - P).length
    return math.acos((a * a + c * c - L0 * L0) / (2 * a * c)) - math.acos((a * a + c * c - length * length) / (2 * a * c))


def eye_error(angle):
    """How far the rod's eye centre is from where the arm carries the rod pin (m)."""
    eye = named("ROD.EYE", 0.08)
    return (eye.matrix_world @ STATE["eye_local"] - rod_pin_at(angle)).length


def open_panel():
    """The Cylinders panel starts closed: a copy that starts open."""
    cls = bpy.types.FRESING_PT_cylinders
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
    joints = mod("blender.joints")
    joints.create(sc, "ROTATE", [named("ARM.ASM")], Vector((0.1, 0.2, 0.6)), Vector((0, 1, 0)), name="Luff")
    eye = named("ROD.EYE", 0.08)
    STATE["eye_local"] = eye.matrix_world.inverted() @ R           # the rod eye's centre, on the part
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    # from the front (-Y), 25° from above: the pins' round sides in front of the brackets are seen
    r3d.view_rotation = Quaternion((math.cos(math.radians(32.5)), math.sin(math.radians(32.5)), 0, 0))
    r3d.view_location = Vector((0.55, 0.2, 0.35))
    r3d.view_distance = 1.6
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_pick_parts():
    s = bpy.context.scene.fresing
    select_only(named("CYL.BARREL", 0.08))
    r1 = op("fresing.cylinder_pick_parts", role="BARREL")
    select_only(named("CYL.ROD", 0.08))
    r2 = op("fresing.cylinder_pick_parts", role="ROD")
    check("Barrel and Rod take the selection", r1 == r2 == {"FINISHED"} and len(s.cyl_pick_barrel) == 1
          and s.cyl_pick_barrel[0].obj.get("fr_name") == "CYL.BARREL" and len(s.cyl_pick_rod) == 1
          and s.cyl_pick_rod[0].obj.get("fr_name") == "CYL.ROD", s.last_message)
    redraw()
    return 0.8


@step
def s_add():
    sidebar_shot("01_picked", 1300)
    with override():
        res = bpy.ops.fresing.cylinder_add("INVOKE_DEFAULT")
    check("Add cylinder waits for the clicks on the pins", res == {"RUNNING_MODAL"}, res)
    # the top of BASE.PIN where it sticks out in front of the bracket (y -20 … 0 mm)
    click(*to_window(Vector((0.5, -0.008, 0.15 + 0.0199))))
    return 0.8


@step
def s_click_rod_pin():
    check("one click: no cylinder yet", len(bpy.context.scene.fresing.cylinders) == 0)
    click(*to_window(Vector((0.8, -0.008, 0.45 + 0.0199))))       # the top of ARM.ROD.PIN
    return 1.0


@step
def s_made():
    wiggle()
    s = bpy.context.scene.fresing
    c = cyl()
    check("two clicks on the pins add the cylinder", c is not None, s.last_message)
    if c is None:
        return 0.5
    check("its pins sit in BASE.PIN and ARM.ROD.PIN", c.frame.parent.get("fr_name") == "BASE.PIN"
          and c.pin.parent.get("fr_name") == "ARM.ROD.PIN")
    check("barrel pin found exactly (round face)", (c.frame.matrix_world.translation - B).length < 1e-5,
          tuple(round(v, 5) for v in c.frame.matrix_world.translation))
    check("closed length and stroke read from the parts", c.measured and abs(c.closed_length - CLOSED) < 2e-4
          and abs(c.full_stroke - FULL) < 2e-4, (round(c.closed_length, 5), round(c.full_stroke, 5)))
    check("the picks are cleared for the next cylinder", len(s.cyl_pick_barrel) == len(s.cyl_pick_rod) == 0)
    mod("blender.joints").set_value(luff(), math.radians(20))
    bpy.context.view_layer.update()
    redraw()
    return 0.8


@step
def s_follows():
    err = eye_error(math.radians(20))
    check("follows the arm: the rod's eye stays on its pin (0.01 mm)", err < 1e-5, f"{err * 1000:.4f} mm")
    shot("02_follows")
    r = op("fresing.cylinder_mode", mode="DRIVE")
    c = cyl()
    j = luff()
    check("Drives the arm", r == {"FINISHED"} and c.mode == "DRIVE" and j.use_limits, bpy.context.scene.fresing.last_message)
    r = op("fresing.cylinder_stroke", target="OUT")
    a = mod("blender.joints").get_value(j)
    check("Fully out: the arm angle is the law of cosines'", r == {"FINISHED"}
          and abs(a - law_of_cosines(c.closed_length + c.full_stroke)) < 1e-5, f"{math.degrees(a):.3f}°")
    bpy.context.view_layer.update()
    check("... and the eye is on its pin there", eye_error(a) < 1e-5)
    STATE["out_angle"] = a
    redraw()
    return 0.8


@step
def s_stroke_field():
    c = cyl()
    c.stroke = 0.1                                         # what typing 100 mm in the field does
    with override():
        bpy.ops.ed.undo_push(message="stroke")
    bpy.context.view_layer.update()
    a = mod("blender.joints").get_value(luff())
    check("the Stroke field moves the arm", abs(a - law_of_cosines(c.closed_length + 0.1)) < 1e-5
          and abs(c.stroke - 0.1) < 1e-5, f"{math.degrees(a):.3f}°")
    redraw()
    return 0.8


@step
def s_panel_alone():
    """For the user guide picture: only the Cylinders panel in the side panel (a top-level copy, open)."""
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, n)
        if getattr(cls, "bl_parent_id", ""):
            bpy.utils.unregister_class(cls)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        bpy.utils.unregister_class(getattr(bpy.types, n))
    base = mod("blender.ui_motion").FRESING_PT_cylinders
    bpy.utils.register_class(type("FRESING_PT_cylinders_alone", (base,), {
        "bl_idname": "FRESING_PT_cylinders_alone", "bl_parent_id": "", "bl_options": set()}))
    bpy.context.scene.fresing.last_message = ""
    redraw()
    wiggle()
    return 1.5


@step
def s_screens():
    wiggle()
    sidebar_shot("panel4_cylinders_full", 1700)
    subprocess.run(["convert", os.path.join(OUT, "panel4_cylinders_full.png"), "-fuzz", "3%", "-trim", "+repage",
                    os.path.join(OUT, "panel4_cylinders.png")], check=False)
    shot("03_driven")
    key("Z", ctrl=True)                                    # undo the 100 mm
    return 1.5


@step
def s_after_undo():
    wiggle()
    a = mod("blender.joints").get_value(luff())
    check("undo: back to fully out", abs(a - STATE["out_angle"]) < 1e-5, f"{math.degrees(a):.3f}°")
    key("Z", ctrl=True, shift=True)
    return 1.5


@step
def s_after_redo():
    wiggle()
    c = cyl()
    check("redo: 100 mm again", c is not None and abs(mod("blender.cylinders").stroke_now(bpy.context.scene, c) - 0.1)
          < 1e-5)
    # a Move cylinder step, filled in from the selected cylinder, built like Build & play
    s = bpy.context.scene.fresing
    op("fresing.anim_add")
    r = op("fresing.block_add", kind="CYLINDER")
    a = s.animations[s.animations_index]
    b = a.blocks[-1]
    check("Add step > Move cylinder picks the cylinder", r == {"FINISHED"} and b.kind == "CYLINDER" and b.cylinder == c.name,
          b.cylinder)
    b.use_from, b.from_stroke, b.to_stroke, b.easing, b.duration = False, 0.0, FULL, "LINEAR", 2.0
    r = op("fresing.anim_build", play=False)
    STATE["anim"] = a.name
    check("Build & play with a Move cylinder step", r == {"FINISHED"}, s.last_message)
    return 1.0


@step
def s_scrub():
    sc = bpy.context.scene
    anim = mod("blender.animation")
    a = sc.fresing.animations[STATE["anim"]]
    f0, f1 = anim.frame_of(a, 0.0), anim.frame_of(a, 2.0)
    mid = (f0 + f1) // 2
    sc.frame_set(mid)
    stroke = FULL * (mid - f0) / (f1 - f0)
    c = cyl()
    ang = mod("blender.joints").get_value(luff())
    check("half way the rod is out by half the stroke, the arm where the triangle says",
          abs(ang - law_of_cosines(c.closed_length + stroke)) < 3e-5 and eye_error(ang) < 1e-5,
          f"{math.degrees(ang):.3f}°")
    op("fresing.anim_clear")
    # the tick box under the joint list (0.2.19: NameError)
    s = sc.fresing
    try:
        s.show_joints = False
        ok = c.frame.hide_get() and luff().frame.hide_get()
        s.show_joints = True
        ok = ok and not c.frame.hide_get()
        check("'Show joint arrows' hides and shows joint arrows and cylinder markers", ok)
    except Exception as exc:
        check("'Show joint arrows' hides and shows joint arrows and cylinder markers", False, repr(exc))
    path = os.path.join(OUT, "cylinder_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    c = cyl()
    check("reopened: the cylinder drives the arm", c is not None and c.mode == "DRIVE")
    if c is None:
        return 0.5
    mod("blender.cylinders").set_stroke(sc, c, 0.05)
    a = mod("blender.joints").get_value(luff())
    bpy.context.view_layer.update()
    check("reopened: stroke 50 mm moves the arm, eye on its pin", abs(a - law_of_cosines(c.closed_length + 0.05))
          < 1e-5 and eye_error(a) < 1e-5)
    rod = named("CYL.ROD", 0.08)
    r = op("fresing.cylinder_remove")
    check("Remove: the rod goes back under its CAD subassembly", r == {"FINISHED"} and not len(sc.fresing.cylinders)
          and rod.parent.get("fr_name") == "CYL.ASM")
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
