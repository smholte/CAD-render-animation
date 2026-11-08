"""Real-app test, G-code (task 0026): on the test gantry, set up the CNC machine with real clicks in the view
(Find the axes, Tool, Workpiece, a clicked work zero that snaps to a corner), add a "Run G-code program" step,
Build: the tool's tip follows the program (lines, arcs in two planes, a drilling cycle) within 0.01 mm, the
tool change shows T2 in the spindle (a copy of the carousel's part), the toolpath is drawn, playback runs,
save and open again, build again.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_gcode.py
Screenshots and ui_test_gcode.log go to $UITEST_OUT (default ~/fresing_ui_test_gcode). The two panel pictures
for the user guide are also printed into the log as base64 (between GUIDE-PNG lines), so a chat that cannot
download the run's files can still read them.
"""

import base64
import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_gcode"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_gantry.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_gcode.log"), "w")
RESULTS = []
STATE = {}
MM = 0.001
STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"
PROGRAM = """%
(UI TEST)
(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
G21 G90 G94 G17 G91.1
G54
S9000 M3
G0 X20 Y20 Z5
G1 Z-2 F600
G1 X120 F1500
G2 X140 Y40 I0 J20
G18 G3 X120 Z-2 I-10 K0
G17 G0 Z10
G53 G0 Z0
T2 M6
G98 G81 X40 Y150 Z-5 R2 F300
X60
G80
G53 G0 Z0
M30
%
"""


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


def print_png(name):
    """The guide picture in the log, base64 (the chats cannot download the run's files)."""
    path = os.path.join(OUT, name + ".png")
    if not os.path.isfile(path):
        return
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    log(f"GUIDE-PNG {name} {len(data)}")
    for k in range(0, len(data), 4000):
        print("GUIDE-PNG:" + data[k:k + 4000], flush=True)
    log(f"GUIDE-PNG-END {name}")


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


def worst_error(sc, step_frames=3):
    """Worst distance (mm) between T1's tip and the program over the animation (frames where T1 shows)."""
    gcode = mod("blender.gcode")
    core = mod("core.gcode")
    animation = mod("blender.animation")
    a = animation.active(sc)
    b = next(x for x in a.blocks if x.kind == "GCODE")
    sc.frame_set(1)
    mach = gcode.Machine(sc)
    sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0], gcode.timing(sc, a, b))
    tool = find(T1)
    tip = gcode._rest_tip(tool)[0]
    zero = sc.fresing.cnc.zero_empty
    worst = 0.0
    for f in range(1, sc.frame_end + 1, step_frames):
        sc.frame_set(f)
        if tool.hide_render:
            continue
        got = zero.matrix_world.inverted() @ (tool.matrix_world @ tip) / MM
        want = Vector(sch.point_at((f - 1) / animation.fps_of(a))) - Vector(mach.g54)
        worst = max(worst, (got - want).length)
    return worst


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
    joints = mod("blender.joints")
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = find(asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"                      # from the front
    r3d.view_rotation = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0))
    r3d.view_location = Vector((0.1, 0.0, 0.07))
    r3d.view_distance = 0.9
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_find_axes():
    r = op("fresing.cnc_find_axes")
    c = bpy.context.scene.fresing.cnc
    check("Find the axes picks X, Y and Z", r == {"FINISHED"} and (c.x_joint, c.y_joint, c.z_joint) == ("X", "Y", "Z"),
          (c.x_joint, c.y_joint, c.z_joint))
    deselect()
    click(*to_window(find(T1).matrix_world @ Vector((0, 0, 0.015))))
    return 0.8


@step
def s_use_tool():
    wiggle()
    active = bpy.context.view_layer.objects.active
    check("a click on the tool makes it the clicked part", active is not None and active.get("fr_name") == T1,
          active.get("fr_name") if active else None)
    r = op("fresing.cnc_use_tool")
    check("'Tool' takes it as the tool in the spindle", r == {"FINISHED"} and bpy.context.scene.fresing.cnc.tool is find(T1))
    deselect()
    click(*to_window((0.0, -0.1, 0.015)))                 # the stock's front face
    return 0.8


@step
def s_use_workpiece():
    wiggle()
    sc = bpy.context.scene
    active = bpy.context.view_layer.objects.active
    check("a click on the block makes it the clicked part", active is not None and active.get("fr_name") == STOCK,
          active.get("fr_name") if active else None)
    r = op("fresing.cnc_use_workpiece")
    gcode = mod("blender.gcode")
    check("'Workpiece' takes the block; the set-up is ready", r == {"FINISHED"} and gcode.problem(sc) == "",
          gcode.problem(sc))
    z = sc.fresing.cnc.zero_empty
    check("the work zero shows on the block's top centre", z is not None
          and (z.matrix_world.translation - Vector((0, 0, 0.03))).length < 1e-6,
          tuple(z.matrix_world.translation) if z else None)
    sc.fresing.cnc.zero_mode = "POINT"                    # what picking 'Clicked point' does
    redraw()
    return 0.8


@step
def s_zero_click_start():
    with override():
        r = bpy.ops.fresing.cnc_zero_click("INVOKE_DEFAULT")
    check("'Click the zero point' waits for a click", r == {"RUNNING_MODAL"}, r)
    return 0.8


@step
def s_zero_click():
    # 2 mm from the block's front left corner, on its front face: snaps onto the corner (-150, -100, 30)
    click(*to_window((-0.148, -0.1, 0.028)))
    return 1.0


@step
def s_zero_clicked():
    wiggle()
    sc = bpy.context.scene
    z = sc.fresing.cnc.zero_empty
    pos = z.matrix_world.translation / MM
    check("the clicked zero snaps onto the corner", (pos - Vector((-150, -100, 30))).length < 1e-3, tuple(pos))
    # the program below is written for the front left corner
    path = os.path.join(OUT, "ui test part.ngc")               # a space in the name
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(PROGRAM)
    STATE["path"] = path
    r1 = op("fresing.anim_add")
    r2 = op("fresing.block_add", kind="GCODE")
    a = mod("blender.animation").active(sc)
    b = a.blocks[a.blocks_index]
    b.gcode_file = path                                   # what the file browser does
    gcode = mod("blender.gcode")
    info = gcode.info(sc, b)
    check("a 'Run G-code program' step reads the program", r1 == r2 == {"FINISHED"} and b.kind == "GCODE"
          and info.get("lines") == PROGRAM.count("\n") and b.duration > 1.0, (info.get("lines"), b.duration))
    check("the program's tools are listed (T1, T2)", info.get("tools") == [2] or info.get("tools") == [1, 2],
          info.get("tools"))
    r = op("fresing.cnc_tools_from_program")
    c = sc.fresing.cnc
    check("Tools from the program adds T1 and T2", r == {"FINISHED"} and sorted(t.number for t in c.tools) == [1, 2],
          [t.number for t in c.tools])
    c.tools_index = next(i for i, t in enumerate(c.tools) if t.number == 2)
    win, area, region, sb = ui()
    area.spaces.active.region_3d.view_location = Vector((0.56, 0.0, 0.12))     # the carousel in the middle
    redraw()
    return 0.8


@step
def s_click_t2():
    deselect()
    click(*to_window(find("TOOL T2 BALL D4").matrix_world @ Vector((0, 0, 0.012))))
    return 0.8


@step
def s_tool_part():
    wiggle()
    sc = bpy.context.scene
    r = op("fresing.cnc_tool_part")
    c = sc.fresing.cnc
    t2 = next(t for t in c.tools if t.number == 2)
    check("'Use clicked part' makes the carousel's ball mill T2", r == {"FINISHED"} and t2.obj is find("TOOL T2 BALL D4"))
    check("its sizes are read from the part: ball end mill Ø4, 30 mm out (task 0040)",
          t2.kind == "BALL" and abs(t2.diameter - 4 * MM) < 0.05 * MM and abs(t2.length - 30 * MM) < 0.05 * MM,
          (t2.kind, t2.diameter, t2.length))
    STATE["tools_row"] = c.tools_index
    next(t for t in c.tools if t.number == 1).obj = find(T1)
    win, area, region, sb = ui()
    area.spaces.active.region_3d.view_location = Vector((0.1, 0.0, 0.07))
    # for the user guide picture: only the CNC machine panel (a top-level copy, folds open)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, n)
        if getattr(cls, "bl_parent_id", ""):
            bpy.utils.unregister_class(cls)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        bpy.utils.unregister_class(getattr(bpy.types, n))
    mod("blender.ui")._OPEN_FOLDS = True
    base = mod("blender.ui_gcode").FRESING_PT_cnc
    bpy.utils.register_class(type("FRESING_PT_cnc_alone", (base,), {
        "bl_idname": "FRESING_PT_cnc_alone", "bl_parent_id": "", "bl_options": set()}))
    redraw()
    wiggle()
    return 1.5


@step
def s_build():
    sc = bpy.context.scene
    sidebar_shot("panel4_cnc", 1400)
    print_png("panel4_cnc")
    # the Tools sub-panel alone (task 0040): T2 selected, its sizes and shape under the list
    bpy.utils.unregister_class(bpy.types.FRESING_PT_cnc_alone)
    tbase = mod("blender.ui_gcode").FRESING_PT_cnc_tools
    bpy.utils.register_class(type("FRESING_PT_cnc_tools_alone", (tbase,), {
        "bl_idname": "FRESING_PT_cnc_tools_alone", "bl_parent_id": "", "bl_options": set()}))
    sc.fresing.cnc.tools_index = STATE.get("tools_row", 0)
    mod("blender.ui")._OPEN_FOLDS = False
    redraw()
    wiggle()
    return 1.0


@step
def s_tools_shot():
    sc = bpy.context.scene
    sidebar_shot("panel4_tools", 1100)
    print_png("panel4_tools")
    check("the Tools panel shows the list (task 0040)", os.path.isfile(os.path.join(OUT, "panel4_tools.png"))
          and len(sc.fresing.cnc.tools) == 2)
    r = op("fresing.anim_build", play=False)
    check("Build: finished", r == {"FINISHED"}, sc.fresing.last_message)
    return 1.0


@step
def s_built():
    sc = bpy.context.scene
    gcode = mod("blender.gcode")
    w = worst_error(sc)
    check("the tool's tip follows the program within 0.01 mm", w < 0.01, f"{w:.4f} mm")
    copy = next((o for o in bpy.data.objects if o.get(gcode.TAG) == "tool" and o.get("fr_cnc_t") == 2), None)
    sc.frame_set(sc.frame_end)
    check("after M6, T2 shows in the spindle and not in the carousel", copy is not None and not copy.hide_render
          and find(T1).hide_render and find("TOOL T2 BALL D4").hide_render)
    sc.frame_set(1)
    check("before M6, T1 is in the spindle", copy is not None and copy.hide_render and not find(T1).hide_render)
    path = gcode.path_object()
    check("the toolpath is drawn on the block", path is not None and path.parent is sc.fresing.cnc.zero_empty
          and len(path.data.vertices) > 50, len(path.data.vertices) if path else None)
    sc.frame_set(int(sc.frame_end * 0.4))
    redraw()
    shot("01_running")
    with override():
        bpy.ops.screen.animation_play()
    return 2.0


@step
def s_playing():
    sc = bpy.context.scene
    playing = bpy.context.window_manager.windows[0].screen.is_animation_playing
    check("playback runs", playing, sc.frame_current)
    with override():
        bpy.ops.screen.animation_cancel(restore_frame=False)
    # the step's panel (6 Animation) for the guide
    a = mod("blender.animation").active(sc)
    STATE["frames"] = sc.frame_end
    check("the video is as long as the program (+ hold at the end)",
          abs((sc.frame_end - 1) / 25 - a.blocks[0].duration - a.tail) < 0.05, (sc.frame_end, a.blocks[0].duration))
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, n)
        if getattr(cls, "bl_parent_id", ""):
            bpy.utils.unregister_class(cls)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        bpy.utils.unregister_class(getattr(bpy.types, n))
    base = mod("blender.ui_motion").FRESING_PT_animation
    bpy.utils.register_class(type("FRESING_PT_animation_alone", (base,), {
        "bl_idname": "FRESING_PT_animation_alone", "bl_options": set()}))
    redraw()
    wiggle()
    return 1.5


@step
def s_step_shot():
    sidebar_shot("panel6_gcode", 1400)
    print_png("panel6_gcode")
    sc = bpy.context.scene
    path = os.path.join(OUT, "gcode_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    _ = sc
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    gcode = mod("blender.gcode")
    gcode._CACHE.clear()
    check("reopened: the CNC set-up is kept", gcode.problem(sc) == "" and len(sc.fresing.cnc.tools) == 2,
          gcode.problem(sc))
    os.rename(STATE["path"], STATE["path"] + ".moved")      # the file gone: the copy in the project is used
    r = op("fresing.anim_build", play=False)
    check("reopened: built again from the copy in the project", r == {"FINISHED"} and sc.frame_end == STATE["frames"],
          (sc.frame_end, STATE["frames"]))
    w = worst_error(sc, 7)
    check("reopened: the tip follows the program", w < 0.01, f"{w:.4f} mm")
    r = op("fresing.anim_clear")
    check("Clear: the tool copies go, T1 shows", r == {"FINISHED"} and find(T1).hide_render is False
          and not [o for o in bpy.data.objects if o.get(gcode.TAG) == "tool"])
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
