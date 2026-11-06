"""Real-app test, mechanisms (task 0014): Base from the selection, Add mechanism (a 3-stage scissor lift and a
four-bar), the platform's height (field and buttons), the drive angle dragged in the panel (the 3D view's
update moves the arms), undo/redo, a Lift height animation step built and scrubbed, "Show joint arrows", save
and open again, Remove.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_linkage.py
Screenshots and ui_test_linkage.log go to $UITEST_OUT (default ~/fresing_ui_test_linkage).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_linkage"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_linkage_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_linkage.log"), "w")
RESULTS = []
STATE = {}
# the test model (tools/make_test_linkage.py), metres: scissor arms 1 m, 15° in the CAD pose, fixed pin z 0.1
PHI0 = math.radians(15.0)
Z0 = 0.1


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


def axis_xz(name):
    part = named(name)
    p = part.matrix_world @ Vector(part.data["fr_axes"][0:3])
    return p.x, p.z


def lift():
    s = bpy.context.scene.fresing
    return s.mechanisms.get("Scissor lift")


def drive(m):
    return mod("blender.linkages").input_joint(bpy.context.scene, m)


def height_ok(phi):
    z = axis_xz("LIFT.PLATFORM.PIN")[1]
    return abs(z - (Z0 + 3 * math.sin(phi))) < 2e-5, f"{z * 1000:.2f} mm, want {(Z0 + 3 * math.sin(phi)) * 1000:.2f}"


def open_panel():
    """The Mechanisms panel starts closed: a copy that starts open."""
    cls = bpy.types.FRESING_PT_mechanisms
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
    r3d.view_location = Vector((0.6, 0.0, 1.2))
    r3d.view_distance = 4.0
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_base_and_add():
    s = bpy.context.scene.fresing
    s.mech_kind = "SCISSOR"
    select([named("LIFT.BASE.ASM")])
    r = op("fresing.mechanism_pick_base")
    check("Base takes the selection", r == {"FINISHED"} and s.mech_base is not None
          and s.mech_base.get("fr_name") == "LIFT.BASE.ASM", s.last_message)
    arms = [named(f"LIFT.ARM.{k}.{i}") for i in (1, 2, 3) for k in ("IN", "OUT")]
    select(arms + [named("LIFT.PLATFORM.ASM")])
    redraw()
    return 0.8


@step
def s_add():
    sidebar_shot("01_picked", 1300)
    s = bpy.context.scene.fresing
    r = op("fresing.mechanism_add")
    m = lift()
    check("Add mechanism makes the scissor lift", r == {"FINISHED"} and m is not None, s.last_message)
    if m is None:
        return 0.5
    d = mod("blender.linkages").setup(m)
    check("9 pins and 2 rollers found from the holes", len(d["pins"]) == 9 and len(d["slots"]) == 2,
          (len(d["pins"]), len(d["slots"])))
    check("the base pick is cleared", s.mech_base is None)
    check("the CAD height", abs(m.height - 3 * math.sin(PHI0)) < 2e-5, f"{m.height * 1000:.2f} mm")
    return 0.8


@step
def s_height_field():
    m = lift()
    m.height = 1.5                                          # what typing 1500 mm in the field does
    with override():
        bpy.ops.ed.undo_push(message="height")
    redraw()
    wiggle()
    return 1.0


@step
def s_height_moved():
    m = lift()
    ok, why = height_ok(math.asin(0.5))
    check("the Height field raises the platform to 1500 mm (pin to pin)", ok, why)
    j = drive(m)
    a = mod("blender.joints").get_value(j)
    check("... the drive joint at asin(0.5) - 15° = 15°", abs(a - (math.asin(0.5) - PHI0)) < 1e-6,
          f"{math.degrees(a):.4f}°")
    r = op("fresing.mechanism_height", target="HIGH")
    check("Highest: arms standing (90°)", r == {"FINISHED"} and m.height > 2.99, f"{m.height * 1000:.1f} mm")
    r = op("fresing.mechanism_height", target="LOW")
    check("Lowest: 2 % of the highest", r == {"FINISHED"} and abs(m.height - 0.06) < 5e-4, f"{m.height * 1000:.1f} mm")
    # the drive angle, dragged in the panel: a plain custom property; the 3D view's update moves the arms
    j.motion["fr_value"] = math.radians(25)
    j.motion.update_tag()
    with override():
        bpy.ops.ed.undo_push(message="drive")
    redraw()
    wiggle()
    return 1.0


@step
def s_dragged():
    ok, why = height_ok(PHI0 + math.radians(25))
    check("the drive angle at 25°: the arms follow (handler)", ok, why)
    shot("02_raised")
    key("Z", ctrl=True)                                     # undo the 25°
    return 1.5


@step
def s_after_undo():
    wiggle()
    m = lift()
    check("undo: back to its lowest", m is not None and abs(m.height - 0.06) < 5e-4,
          f"{m.height * 1000:.1f} mm" if m else "")
    key("Z", ctrl=True, shift=True)
    return 1.5


@step
def s_after_redo():
    wiggle()
    ok, why = height_ok(PHI0 + math.radians(25))
    check("redo: 25° again", ok, why)
    s = bpy.context.scene.fresing
    op("fresing.anim_add")
    r = op("fresing.block_add", kind="MECHANISM")
    a = s.animations[s.animations_index]
    b = a.blocks[-1]
    check("Add step > Lift height picks the lift", r == {"FINISHED"} and b.kind == "MECHANISM"
          and b.mechanism == "Scissor lift", b.mechanism)
    b.use_from, b.from_height, b.to_height, b.easing, b.duration = False, 0.5, 2.5, "LINEAR", 2.0
    r = op("fresing.anim_build", play=False)
    STATE["anim"] = a.name
    check("Build & play with a Lift height step", r == {"FINISHED"}, s.last_message)
    return 1.0


@step
def s_scrub():
    sc = bpy.context.scene
    anim = mod("blender.animation")
    a = sc.fresing.animations[STATE["anim"]]
    f0, f1 = anim.frame_of(a, 0.0), anim.frame_of(a, 2.0)
    mid = (f0 + f1) // 2
    sc.frame_set(mid)
    want = 0.5 + 2.0 * (mid - f0) / (f1 - f0)
    z = axis_xz("LIFT.PLATFORM.PIN")[1] - Z0
    check("half way the platform is half way up (keys on every arm)", abs(z - want) < 2e-5,
          f"{z * 1000:.2f} mm, want {want * 1000:.2f}")
    m = lift()
    e = next(ln.empty for ln in m.links if ln.empty is not None)
    check("the arms move by keys, no drivers (plays with scripts off)", e.animation_data is not None
          and e.animation_data.action is not None and not e.animation_data.drivers)
    op("fresing.anim_clear")
    return 1.0


@step
def s_four_bar():
    sc = bpy.context.scene
    s = sc.fresing
    ok, why = height_ok(PHI0 + math.radians(25))
    check("Stop the animation: back to 25°", ok, why)
    s.mech_kind = "FOURBAR"
    select([named("FOURBAR.BASE.ASM")])
    op("fresing.mechanism_pick_base")
    crank = named("FOURBAR.CRANK.ASM")
    select([named("FOURBAR.COUPLER.ASM"), named("FOURBAR.ROCKER.ASM"), crank], active=crank)
    r = op("fresing.mechanism_add")
    m = s.mechanisms.get("Four-bar or parallel arm")
    check("Add mechanism makes the four-bar, the crank (clicked last) drives", r == {"FINISHED"} and m is not None
          and {o.get("fr_name") for o in mod("blender.joints").members(drive(m))} == {"FOURBAR.CRANK.ASM"},
          s.last_message)
    if m is None:
        return 0.5
    drive(m).motion["fr_value"] = math.radians(200)      # as dragging the Drive angle field (with its undo step)
    drive(m).motion.update_tag()
    with override():
        bpy.ops.ed.undo_push(message="drive")
    redraw()
    wiggle()
    return 1.0


def four_bar_lengths():
    bx, bz = axis_xz("FOURBAR.CRANK.PIN")
    cx, cz = axis_xz("FOURBAR.ROCKER.PIN")
    bc, dc, ab = math.hypot(cx - bx, cz - bz), math.hypot(cx - 2.4, cz - 0.3), math.hypot(bx - 2.0, bz - 0.3)
    m = bpy.context.scene.fresing.mechanisms.get("Four-bar or parallel arm")
    lk = mod("blender.linkages")
    why = (f"BC {bc * 1000:.3f} DC {dc * 1000:.3f} AB {ab * 1000:.3f} mm; crank at "
           f"{math.degrees(math.atan2(bz - 0.3, bx - 2.0)):.2f}°; drive "
           f"{math.degrees(mod('blender.joints').get_value(drive(m))):.2f}°, solved {math.degrees(lk.solved(m)):.2f}°"
           f" {m.status}")
    return abs(bc - 0.35) < 2e-5 and abs(dc - 0.25) < 2e-5 and abs(ab - 0.12) < 2e-5, why


@step
def s_four_bar_moved():
    ok, why = four_bar_lengths()
    check("the four-bar's links keep their lengths at 200°", ok, why)
    wiggle()
    return 1.0


@step
def s_four_bar_later():
    ok, why = four_bar_lengths()
    check("... and one step later", ok, why)
    s = bpy.context.scene.fresing
    s.mechanisms_index = s.mechanisms.find("Scissor lift")
    try:
        s.show_joints = False
        m = lift()
        ok = m.frame.hide_viewport
        s.show_joints = True
        ok = ok and not m.frame.hide_viewport
        check("'Show joint arrows' hides and shows the mechanisms' markers", ok)
    except Exception as exc:
        check("'Show joint arrows' hides and shows the mechanisms' markers", False, repr(exc))
    return 0.5


@step
def s_panel_alone():
    """For the user guide picture: only the Mechanisms panel in the side panel (a top-level copy, open)."""
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, n)
        if getattr(cls, "bl_parent_id", ""):
            bpy.utils.unregister_class(cls)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        bpy.utils.unregister_class(getattr(bpy.types, n))
    base = mod("blender.ui_motion").FRESING_PT_mechanisms
    bpy.utils.register_class(type("FRESING_PT_mechanisms_alone", (base,), {
        "bl_idname": "FRESING_PT_mechanisms_alone", "bl_parent_id": "", "bl_options": set()}))
    bpy.context.scene.fresing.last_message = ""
    redraw()
    wiggle()
    return 1.5


@step
def s_screens():
    wiggle()
    sidebar_shot("panel4_mechanisms_full", 1700)
    subprocess.run(["convert", os.path.join(OUT, "panel4_mechanisms_full.png"), "-fuzz", "3%", "-trim", "+repage",
                    os.path.join(OUT, "panel4_mechanisms.png")], check=False)
    shot("03_both")
    path = os.path.join(OUT, "mechanism_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    m = lift()
    check("reopened: both mechanisms", m is not None and len(sc.fresing.mechanisms) == 2)
    if m is None:
        return 0.5
    ok, why = height_ok(PHI0 + math.radians(25))
    check("reopened: the lift where it was", ok, why)
    m.height = 2.0
    bpy.context.view_layer.update()
    ok, why = height_ok(math.asin(2.0 / 3.0))
    check("reopened: the height still moves the arms", ok, why)
    sc.fresing.mechanisms_index = sc.fresing.mechanisms.find("Scissor lift")
    arm = named("LIFT.ARM.OUT.2")
    r = op("fresing.mechanism_remove")
    bpy.context.view_layer.update()
    ok, why = height_ok(PHI0)
    check("Remove: the arms go back under their CAD subassembly, at their CAD place", r == {"FINISHED"}
          and sc.fresing.mechanisms.get("Scissor lift") is None and arm.parent.get("fr_name") == "LIFT.ASM" and ok, why)
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
