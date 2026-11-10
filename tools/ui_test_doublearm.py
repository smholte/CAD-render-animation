"""Real-app test, double-arm tool changer (task 0064): on the test mill with an arm and a 12-pot magazine
(tools/make_test_atc.py), pick 'Double-arm', click the arm's hub and the station pot's hinge in the view, press Check
(it plays one change in the view and says everything fits), build the animation: at the first change the arm holds
the old and the new tool at its half turn, and every hand-over (spindle -> arm, pot -> arm, arm -> spindle, arm -> pot)
is within 0.01 mm; save and open again.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_doublearm.py
Screenshots and ui_test_doublearm.log go to $UITEST_OUT (default ~/fresing_ui_test_doublearm).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_doublearm"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_atc.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_doublearm.log"), "w")
RESULTS = []
STATE = {}
MM = 0.001


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


def op(_idname, *args, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)(*(args or ("EXEC_DEFAULT", True)), **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def sidebar_shot(name, height=1500):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + "_full.png")], check=False)
    subprocess.run(["convert", os.path.join(OUT, name + "_full.png"), "-fuzz", "3%", "-trim", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def to_window(world_pt):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(region.x + co.x), int(region.y + co.y)


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def find(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def deselect():
    for o in bpy.context.selected_objects:
        o.select_set(False)


def open_panel():
    """The CNC machine panel starts closed: a copy that starts open."""
    cls = bpy.types.FRESING_PT_cnc
    if "DEFAULT_CLOSED" in cls.bl_options:
        bpy.utils.unregister_class(cls)
        cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
        bpy.utils.register_class(cls)


def front_view(at, distance=0.5):
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"                      # from the front (looking along +Y)
    r3d.view_rotation = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0))
    r3d.view_location = Vector(at)
    r3d.view_distance = distance
    redraw()


def world(o):
    """World matrix from the (evaluated) parent's: a hidden object is not evaluated."""
    return o.parent.matrix_world @ o.matrix_parent_inverse @ o.matrix_basis


def gap(p, q):
    me = p.data
    idx = range(0, len(me.vertices), max(1, len(me.vertices) // 6))
    mp, mq = world(p), world(q)
    return max((mp @ me.vertices[i].co - mq @ me.vertices[i].co).length for i in idx) / MM


def at_time(sc, a, t):
    f = 1 + t * int(a.fps)
    sc.frame_set(int(f), subframe=f - int(f))


def schedule(sc):
    gcode, core, animation = mod("blender.gcode"), mod("core.gcode"), mod("blender.animation")
    a = animation.active(sc)
    b = next(x for x in a.blocks if x.kind == "GCODE")
    mach = gcode.Machine(sc)
    return a, b, mach, core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0],
                                     gcode.timing(sc, a, b, mach))


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
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    sc = bpy.context.scene
    path = os.path.join(OUT, "double arm test.ngc")         # a space in the name
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(mod("blender.doublearm").TEST_PROGRAM)
    r1 = op("fresing.anim_add")
    r2 = op("fresing.block_add", kind="GCODE")
    a = mod("blender.animation").active(sc)
    b = a.blocks[a.blocks_index]
    b.gcode_file = path                                   # what the file browser does
    mod("blender.doublearm").set_up_test_model(sc, b, arm=False)
    check("the mill is set up: axes, spindle, magazine, tools", r1 == r2 == {"FINISHED"}
          and mod("blender.gcode").problem(sc) == "" and len(sc.fresing.cnc.tools) == 3)
    win, area, region, sb = ui()
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    sc.fresing.cnc.changer = "ARM"                        # the 'Double-arm' button
    front_view((-0.2, 0.0, 0.32), 0.45)
    return 1.0


@step
def s_hub_start():
    sc = bpy.context.scene
    dbl = mod("blender.doublearm")
    check("'Double-arm' asks for the arm first", any("arm" in p for p in dbl.problems(sc)), dbl.problems(sc)[:1])
    deselect()
    with override():
        r = bpy.ops.fresing.cnc_arm_hub("INVOKE_DEFAULT")
    check("'Click the arm's hub' waits for a click", r == {"RUNNING_MODAL"}, r)
    return 0.8


@step
def s_hub_click():
    x, y = to_window((-0.13, -0.03, 0.325))                # the hub's round side, above the arm's bar
    log("hub click at", x, y)
    click(x, y)
    return 1.5


@step
def s_hub_done():
    wiggle()
    sc = bpy.context.scene
    c = sc.fresing.cnc
    dbl = mod("blender.doublearm")
    slide, turn = dbl.arm_joints(sc)
    check("a click on the hub makes the arm's turn and stroke", turn is not None and slide is not None,
          (c.arm_turn, c.arm_slide))
    if turn is not None:
        o, d = mod("blender.joints").axis_world(turn)
        check("the arm turns about the hub's axis (vertical, x = -130)", abs(d.z) > 0.9999
              and abs(o.x + 0.13) < 1e-4 and abs(o.y) < 1e-4, (tuple(o), tuple(d)))
    check("the grip angle is read from the claws: 90°", abs(math.degrees(c.arm_grip) - 90.0) < 0.05,
          math.degrees(c.arm_grip))
    check("the stroke is set for BT30: 76 mm", abs(c.arm_stroke - 0.076) < 1e-6, c.arm_stroke)
    c.pot_tip = True                                      # the 'Pots tip down' box
    front_view((-0.31, 0.0, 0.35), 0.25)
    with override():
        r = bpy.ops.fresing.cnc_arm_hinge("INVOKE_DEFAULT")
    check("'Click the hinge' waits for a click", r == {"RUNNING_MODAL"}, r)
    return 0.8


@step
def s_hinge_click():
    x, y = to_window((-0.31, -0.02, 0.3535))              # the station pot's hinge pin, its front end
    log("hinge click at", x, y)
    click(x, y)
    return 2.0


@step
def s_hinge_done():
    wiggle()
    sc = bpy.context.scene
    c = sc.fresing.cnc
    tc = mod("blender.toolchange")
    tips = [p.tip_joint for p in c.pockets if p.tip_joint]
    check("a click on the hinge makes 12 pots, each with its tip joint", len(c.pockets) == 12 and len(tips) == 12,
          (len(c.pockets), len(tips)))
    check("the set-up has no problems", not tc.problems(sc), tc.problems(sc)[:2])
    r = op("fresing.cnc_arm_check")
    lines = mod("blender.doublearm").LAST_CHECK
    check("Check: everything fits (claw and pot on the axes, stroke)", r == {"FINISHED"} and lines
          and all(ok for ok, _t in lines), [t for _ok, t in lines][:4])
    front_view((-0.15, 0.0, 0.27), 0.6)
    STATE["turn"] = c.arm_turn
    with override():
        r = bpy.ops.fresing.cnc_arm_check("INVOKE_DEFAULT")
    check("Check plays one change in the view", r == {"RUNNING_MODAL"}, r)
    STATE["t_check"] = time.time()
    return 0.6


@step
def s_check_playing():
    sc = bpy.context.scene
    j = sc.fresing.joints.get(STATE["turn"])
    v = mod("blender.joints").get_value(j)
    STATE["moved"] = abs(v) > 0.05
    shot("check_playing")
    return 3.0


@step
def s_check_done():
    sc = bpy.context.scene
    j = sc.fresing.joints.get(STATE["turn"])
    v = mod("blender.joints").get_value(j)
    check("the arm turned during Check and is back at rest after it", STATE.get("moved") and abs(v) < 1e-6,
          (STATE.get("moved"), v))
    sidebar_shot("panel_toolchange_arm")
    r = op("fresing.anim_build", play=False)
    check("Build animation", r == {"FINISHED"}, r)
    return 1.0


@step
def s_handovers():
    sc = bpy.context.scene
    a, b, mach, sch = schedule(sc)
    gcode = mod("blender.gcode")
    arm = [x for x in sch.changes if x.kind == "arm"]
    check("three double-arm changes, random pots (T1 comes back from pot 2)",
          [(x.tool, x.new_pocket) for x in arm] == [(2, 2), (3, 5), (1, 2)],
          [(x.tool, x.new_pocket) for x in arm])
    rows = {p.number: p for p in sc.fresing.cnc.pockets}

    def held(n):
        return next(o for o in bpy.data.objects if o.get("fr_cnc_carry") == n and not o.hide_render)

    def spindle_of(n):
        return mach.tool if n == 1 else gcode.copies()[n]

    def in_pot(n, pk):
        return next(o for o in bpy.data.objects if o.get("fr_cnc_pocket") == n and o.parent is rows[pk].obj)

    worst = 0.0
    x = arm[0]
    t = x.arm_times()
    at_time(sc, a, t["grip"][1] + 1e-4)
    worst = max(worst, gap(held(x.old), spindle_of(x.old)), gap(held(x.tool), in_pot(x.tool, x.new_pocket)))
    at_time(sc, a, t["push"][1] - 1e-4)
    worst = max(worst, gap(held(x.tool), spindle_of(x.tool)), gap(held(x.old), in_pot(x.old, x.new_pocket)))
    check("every hand-over of the first change within 0.01 mm", worst < 0.01, f"{worst:.5f} mm")
    at_time(sc, a, (t["swap"][0] + t["swap"][1]) / 2)
    on_arm = sorted(o["fr_cnc_carry"] for o in bpy.data.objects if o.get("fr_cnc_carry") and not o.hide_render)
    tj = sc.fresing.joints[rows[x.new_pocket].tip_joint]
    check("at the half turn the arm holds T1 and T2; pot 2 is tipped down", on_arm == [1, 2]
          and abs(abs(mod("blender.joints").get_value(tj)) - math.pi / 2) < 1e-4, on_arm)
    front_view((-0.13, 0.0, 0.22), 0.6)
    shot("half_turn")
    path = os.path.join(OUT, "double arm é.blend")
    r = op("wm.save_as_mainfile", filepath=path)
    STATE["blend"] = path
    check("save the project", r == {"FINISHED"}, r)
    return 0.5


@step
def s_reopen():
    r = op("wm.open_mainfile", filepath=STATE["blend"])
    STATE["reopened"] = r
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    c = sc.fresing.cnc
    dbl = mod("blender.doublearm")
    a, b, mach, sch = schedule(sc)
    x = next(x for x in sch.changes if x.kind == "arm")
    t = x.arm_times()
    at_time(sc, a, (t["swap"][0] + t["swap"][1]) / 2)
    on_arm = sorted(o["fr_cnc_carry"] for o in bpy.data.objects if o.get("fr_cnc_carry") and not o.hide_render)
    check("opened again: the arm, 12 pots and the half turn as before", STATE.get("reopened") == {"FINISHED"}
          and dbl.arm_joints(sc)[1] is not None and len(c.pockets) == 12 and on_arm == [1, 2], on_arm)
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
