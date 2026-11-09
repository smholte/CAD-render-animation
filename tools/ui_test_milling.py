"""Real-app test, milling (task 0027): pick the bit and the workpiece with real clicks in the view, the
cut follows the timeline (scrub, playback, a changed animation is read again by itself), undo/redo,
save and open again, Stop milling. Chips (task 0028): Few shows chips that follow the timeline, Clear chips,
chips after opening again, Stop milling takes them away.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_milling.py
Screenshots and ui_test_milling.log go to $UITEST_OUT (default ~/fresing_ui_test_milling).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_milling"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_mill.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_milling.log"), "w")
RESULTS = []
STATE = {}
MM = 0.001
STOCK = "STOCK 200x200x40"
SLOT_VOLUME = (50 * 10 + math.pi * 25) * 5          # mm³: Ø10, 50 mm long, 5 mm deep


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
    return int(region.x + co.x), int(region.y + co.y)


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


def find(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def removed():
    """(bounding box in mm, volume in mm³) of what is cut out of the stock, from the mesh shown."""
    import manifold3d as mf
    import numpy as np
    core = mod("core.machining")
    me = find(STOCK).data
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    stock = mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.03))
    gone = stock - core.solid_from_mesh(v.reshape(-1, 3), t.reshape(-1, 3))
    return [round(x / MM, 2) for x in gone.bounding_box()], gone.volume() / MM ** 3


def open_panel():
    """The Milling panel starts closed: a copy that starts open (and panel 4 itself open)."""
    for name in ("FRESING_PT_milling", "FRESING_PT_milling_chips"):
        cls = getattr(bpy.types, name)
        if "DEFAULT_CLOSED" in cls.bl_options:
            bpy.utils.unregister_class(cls)
            cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
            bpy.utils.register_class(cls)


def chip_points():
    """(chips riding with the workpiece, chips that fell off) shown now."""
    out = []
    for name in ("FR Chips", "FR Chips (fallen)"):
        o = bpy.data.objects.get(name)
        out.append(len(o.data.vertices) if o is not None and o.data is not None else 0)
    return tuple(out)


def build_animation(z_mm):
    """Plunge, 50 mm along X, back up; built like 'Build & play' (without playing)."""
    s = bpy.context.scene.fresing
    a = s.animations.get("Mill") or s.animations.add()
    a.name, a.tail = "Mill", 0.0
    a.blocks.clear()
    for j, start, dur, to in (("Z", 0.0, 1.0, z_mm), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    s.animations_index = list(s.animations).index(a)
    return op("fresing.anim_build", play=False)          # like the button: with an undo step


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
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = find(asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    mod("blender.logic").set_hidden(find("FINISHED PART"), True)     # same place as the stock
    build_animation(-25.0)
    STATE["frames"] = sc.frame_end
    # view from the front, the head and the block in view
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0))
    r3d.view_location = Vector((0.0, 0.0, 0.1))
    r3d.view_distance = 0.6
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_click_bit():
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bit = find("END MILL D10")
    click(*to_window(bit.matrix_world @ Vector((0, 0, 0.02))))
    return 0.8


@step
def s_use_bit():
    wiggle()
    active = bpy.context.view_layer.objects.active
    check("a click on the bit makes it the clicked part", active is not None and active.get("fr_name") == "END MILL D10",
          active.get("fr_name") if active else None)
    shot("01_bit_clicked")
    r = op("fresing.mill_add_bit")
    m = bpy.context.scene.fresing.milling
    check("'Use as bit' reads the bit's shape", r == {"FINISHED"} and len(m.bits) == 1
          and m.bits[0].detected == "Flat end mill Ø10.0 mm, 40 mm long", [b.detected for b in m.bits])
    for o in bpy.context.selected_objects:
        o.select_set(False)
    click(*to_window((0.0, -0.1, 0.05)))                  # the front face of the stock
    return 0.8


@step
def s_use_workpiece():
    wiggle()
    active = bpy.context.view_layer.objects.active
    check("a click on the block makes it the clicked part", active is not None and active.get("fr_name") == STOCK,
          active.get("fr_name") if active else None)
    r = op("fresing.mill_set_workpiece")
    m = bpy.context.scene.fresing.milling
    check("'Use as workpiece' gives it a mesh of its own", r == {"FINISHED"} and m.workpiece is find(STOCK)
          and find(STOCK).data.name == f"{STOCK} (milled)", find(STOCK).data.name)
    return 1.5                                           # the motion is read a moment later, by itself


@step
def s_scrub_end():
    sc = bpy.context.scene
    m = sc.fresing.milling
    check("the motion was read by itself", m.path_sig == mod("blender.machining").signature(sc))
    sc.frame_set(STATE["frames"])
    box, vol = removed()
    check("at the end the slot is cut", abs(vol - SLOT_VOLUME) < 0.005 * SLOT_VOLUME and box[2] == 65.0
          and box[3] == 55.0, (box, round(vol)))
    sc.frame_set(51)
    box, vol = removed()
    check("half way the slot is half done", box[3] == 30.0, box)
    STATE["mesh51"] = len(find(STOCK).data.polygons), round(vol, 3)
    sc.frame_set(1)
    check("on the first frame nothing is cut yet", removed()[1] < 1e-3)
    sc.frame_set(51)
    check("scrubbing back gives the same cut", (len(find(STOCK).data.polygons), round(removed()[1], 3))
          == STATE["mesh51"])
    redraw()
    return 0.5


@step
def s_chips_on():
    bpy.context.scene.fresing.milling.chips = "FEW"      # what picking 'Few' in the Chips drop-down does
    redraw()
    return 1.0


@step
def s_chips():
    sc = bpy.context.scene
    ch = mod("blender.chips")
    m = sc.fresing.milling
    sc.frame_set(STATE["frames"])
    end = chip_points()
    check("chips: 'Few' shows chips on the block and the table, and on the bed", end[0] > 0 and end[1] > 0, end)
    sc.frame_set(1)
    check("chips: none before the bit cuts", chip_points() == (0, 0), chip_points())
    sc.frame_set(STATE["frames"])
    check("chips: scrubbing back gives the same chips", chip_points() == end, chip_points())
    st = ch.status(sc)
    check("chips: the panel says how many were worked out", "chips worked out" in st, st)
    log("chips:", st)
    r = op("fresing.chips_clear")
    check("Clear chips removes them", r == {"FINISHED"} and m.chips == "NONE"
          and bpy.data.objects.get("FR Chips") is None, (r, m.chips))
    m.chips = "FEW"                                      # on again for the rest of the test
    sc.frame_set(51)
    shot("02b_chips")
    return 0.5


@step
def s_cut_look():
    """Task 0051: the block as sawn aluminium plate; the faces the bit cut show machined aluminium."""
    sc = bpy.context.scene
    mach = mod("blender.machining")
    wp = sc.fresing.milling.workpiece
    sc.fresing.groups[wp["fr_group"]].material = "aluminium_sawn"
    sc.frame_set(STATE["frames"])
    n = int(wp.data.get(mach.CUT_SLOT, -1))
    mat = wp.material_slots[n].material if 0 < n < len(wp.material_slots) else None
    used = {p.material_index for p in wp.data.polygons}
    check("cut faces: their own slot shows machined aluminium, the outside sawn plate",
          mat is not None and mat.get("fr_material") == "aluminium_machined" and n in used and 0 in used
          and wp.material_slots[0].material.get("fr_material") == "aluminium_sawn",
          (n, mat.name if mat else None, sorted(used)))
    sc.frame_set(51)
    return 0.5


@step
def s_panel_alone():
    """For the user guide picture: only the Milling panel in the side panel (a top-level copy, open)."""
    shot("02_half_way")
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, n)
        if getattr(cls, "bl_parent_id", ""):
            bpy.utils.unregister_class(cls)
    for n in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        bpy.utils.unregister_class(getattr(bpy.types, n))
    base = mod("blender.ui_machining").FRESING_PT_milling
    bpy.utils.register_class(type("FRESING_PT_milling_alone", (base,), {
        "bl_idname": "FRESING_PT_milling_alone", "bl_parent_id": "", "bl_options": set()}))
    chips_panel = mod("blender.ui_machining").FRESING_PT_milling_chips    # and the Chips sub-panel under it
    bpy.utils.register_class(type("FRESING_PT_milling_chips_alone", (chips_panel,), {
        "bl_idname": "FRESING_PT_milling_chips_alone", "bl_parent_id": "", "bl_options": set()}))
    redraw()
    wiggle()
    return 1.5


@step
def s_screens():
    sidebar_shot("panel4_milling_full", 1400)
    subprocess.run(["convert", os.path.join(OUT, "panel4_milling_full.png"), "-fuzz", "3%", "-trim", "+repage",
                    os.path.join(OUT, "panel4_milling.png")], check=False)
    with override():
        bpy.ops.screen.animation_play()
    STATE["t_play"] = time.time()
    return 2.0


@step
def s_playing():
    sc = bpy.context.scene
    playing = bpy.context.window_manager.windows[0].screen.is_animation_playing
    check("playback runs with milling on", playing and sc.frame_current != 51, sc.frame_current)
    with override():
        bpy.ops.screen.animation_cancel(restore_frame=False)
    status = mod("blender.machining").status(sc)
    check("the panel shows the state of the cut", status.startswith("Frame "), status)
    log("status while playing:", status)
    # a deeper animation: read again by itself
    build_animation(-27.0)
    return 1.5


@step
def s_after_change():
    sc = bpy.context.scene
    sc.frame_set(STATE["frames"])
    box, _vol = removed()
    check("a rebuilt animation is followed by itself (2 mm deeper)", box[2] == 63.0, box)
    shot("03_deeper")
    key("Z", ctrl=True)                                  # undo the rebuild
    return 1.5


@step
def s_undo_wait():
    wiggle()                                             # the motion that is back is read a moment later
    return 1.5


@step
def s_after_undo():
    sc = bpy.context.scene
    log("after undo: milled mesh", find(STOCK).data.name, "path read", sc.fresing.milling.path_sig ==
        mod("blender.machining").signature(sc))
    sc.frame_set(STATE["frames"] - 1)
    sc.frame_set(STATE["frames"])
    box, _vol = removed()
    check("undo: the cut follows the animation that is back", box[2] == 65.0, box)
    key("Z", ctrl=True, shift=True)
    return 1.5


@step
def s_redo_wait():
    log("after redo")
    wiggle()
    return 1.5


@step
def s_after_redo():
    sc = bpy.context.scene
    sc.frame_set(STATE["frames"] - 1)
    sc.frame_set(STATE["frames"])
    box, _vol = removed()
    check("redo: deeper again", box[2] == 63.0, box)
    path = os.path.join(OUT, "milling_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    m = sc.fresing.milling
    check("reopened: the set-up is kept", len(m.bits) == 1 and m.workpiece is find(STOCK))
    sc.frame_set(1)
    sc.frame_set(STATE["frames"])
    box, _vol = removed()
    check("reopened: the cut follows the timeline", box[2] == 63.0, box)
    check("reopened: the chips are back", m.chips == "FEW" and sum(chip_points()) > 0, chip_points())
    r = op("fresing.mill_stop")
    check("Stop milling: the block is whole again", r == {"FINISHED"} and not find(STOCK).data.get("fr_milled")
          and len(m.bits) == 0, find(STOCK).data.name)
    check("Stop milling: the chips are gone", bpy.data.objects.get("FR Chips") is None
          and bpy.data.objects.get("FR Chips (fallen)") is None)
    shot("04_stopped")
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
