"""Screenshots of the whole Fresing side panel in the real app, with a realistic project state.

Every Fresing panel and sub-panel is opened; the window is very tall so the whole side panel
fits in one image, which is then cut into readable pieces.

Run (fresh user folder with the extension + app template installed):
    BLENDER_USER_RESOURCES=<user> xvfb-run -a -s "-screen 0 1500x7000x24" blender -p 0 0 1500 7000 \
        --app-template fresing_render --enable-event-simulate --python tools/ui_screens.py
Output: $UISHOT_OUT (default ~/fresing_ui_screens): sidebar_full.png, sidebar_part_N.png, ui_screens.log
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Vector

OUT = os.environ.get("UISHOT_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_screens"))
CRANE = os.environ.get("UISHOT_MODEL") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests",
                                                       "data", "test_crane_a.step")
SIDEBAR_W = int(os.environ.get("UISHOT_SIDEBAR", "430"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_screens.log"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UISHOT]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def pkg():
    import addon_utils
    for m in addon_utils.modules():
        if m.__name__.endswith("fresing_render"):
            return m.__name__
    return None


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def areas():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = areas()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def ob(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n]


def open_all_panels():
    """Panels that start closed are registered again without that flag (before they are first drawn)."""
    names = [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]
    for name in names:
        cls = getattr(bpy.types, name)
        if "DEFAULT_CLOSED" in getattr(cls, "bl_options", set()):
            try:
                bpy.utils.unregister_class(cls)
                cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
                bpy.utils.register_class(cls)
            except Exception:
                log("reopen failed", name, traceback.format_exc())


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region, sb = areas()
    log("ui scale", bpy.context.preferences.view.ui_scale, "window", win.width, win.height, "sidebar", sb.width)
    win.event_simulate(type="ESC", value="PRESS", x=700, y=3500)
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=3500)
    if not os.environ.get("UISHOT_SIDEBAR"):
        return 1.0
    # drag the side panel's edge to a fixed width
    x0, y0 = sb.x + 2, sb.y + sb.height // 2
    target = area.x + area.width - SIDEBAR_W
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x0, y=y0)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x0, y=y0)
    for k in range(1, 21):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x0 + (target - x0) * k / 20), y=y0)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=target, y=y0)
    return 1.0


@step
def s_import():
    with override():
        res = bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    log("import started", res, bpy.context.scene.fresing.last_message)
    return 1.0


@step
def s_wait_import():
    if bpy.context.scene.fresing.model_count == 0:
        log("waiting:", bpy.context.scene.fresing.last_message)
        return "wait"
    return 0.5


@step
def s_state():
    """A project in the middle of the work: joints, poses, scenes, an animation, a queue.

    UISHOT_EMPTY=1: right after the import (what a new user sees first).
    UISHOT_FOLLOW_LAST=1 (any model): the last part is clicked, so the tree must open and scroll to it."""
    if os.environ.get("UISHOT_FOLLOW_LAST"):
        sc = bpy.context.scene
        rows = sc.fresing.tree
        deepest = max(it.depth for it in rows)
        last = [it for it in rows if it.depth == deepest][-1].obj    # far down a closed tree
        for o in bpy.context.selected_objects:
            o.select_set(False)
        sc.fresing.pick_mode = "PART"
        last.select_set(True)
        bpy.context.view_layer.objects.active = last
        log("clicked", last.get("fr_name"))
        return 1.0
    if os.environ.get("UISHOT_EMPTY"):
        if os.environ.get("UISHOT_ACTIVE"):                   # a part clicked (e.g. painted faces listed)
            part = ob(os.environ["UISHOT_ACTIVE"])
            part.select_set(True)
            bpy.context.view_layer.objects.active = part
        return 1.0
    sc = bpy.context.scene
    s = sc.fresing
    joints, states, queue = mod("blender.joints"), mod("blender.states"), mod("blender.queue")
    pin = ob("BOOM.PIN")
    pivot = Vector((0.1, 0.3, 0.42))
    origin, direction, _desc = joints.axis_from_hit(pin, 0, pivot, Vector((0, 0, 1)))
    j1 = joints.create(sc, "ROTATE", [ob("BOOM.ASM")], origin, direction, ref=pin, name="Boom luff")
    j1.use_limits = True
    j2 = joints.create(sc, "SLIDE", [ob("TROLLEY.ASM")], Vector((0.7, 0.3, 0.45)), Vector((1, 0, 0)),
                       name="Trolley", base=None)
    s.joints_index = 0
    joints.set_value(j1, math.radians(20))
    states.save_pose(sc, "Working")
    states.save_pose(sc, "Transport")
    states.save_visibility(sc, "Without cover")
    states.save_shot(sc, "Side view")
    states.save_shot(sc, "Detail boom")
    a = s.animations.add()
    a.name = "Luff and travel"
    a.tail = 0.5
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.to_angle = "JOINT", j1.name, 0.0, 2.0, math.radians(45)
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.to_dist = "JOINT", j2.name, 2.0, 3.0, 0.4
    b = a.blocks.add()
    b.kind, b.camera_mode, b.orbit_angle, b.start, b.duration = "CAMERA", "ORBIT", math.radians(60), 0.0, 5.0
    a.blocks_index = 0
    s.animations_index = 0
    done = queue.add_job(sc, "STILL", shot="Side view")
    done.status, done.message, done.output = "DONE", "Saved crane_Side_view_1920x1080.png", CRANE
    q = queue.add_job(sc, "ANIMATION", animation=a.name)
    q.status, q.progress, q.message = "RUNNING", 42.0, "Frame 53 of 125 on GPU (6.1 s per frame, about 7 min left)"
    s.queue_index = 1
    s.last_render = CRANE
    mod("blender.tree").follow_view(sc, ob("BOOM.PIN"))      # tree opened down to a part
    s.find_text = "boom"                                     # a search in Find & sort parts
    active = os.environ.get("UISHOT_ACTIVE", "BOOM.ASM")       # UISHOT_ACTIVE=BOOM.PIN: a part clicked
    if os.environ.get("UISHOT_STACK"):
        # UISHOT_STACK=1: a second joint on the trolley rides on "Trolley"; the trolley is selected,
        # so Add joint says it goes on top, and the joint on top is the selected one in the list
        joints.create(sc, "SLIDE", [ob("TROLLEY.ASM")], Vector((0.7, 0.3, 0.45)), Vector((0, 1, 0)),
                      name="Trolley side shift")
        s.joints_index = len(s.joints) - 1
        active = "TROLLEY.ASM"
        if os.environ.get("UISHOT_STACK") == "bottom":
            s.joints_index = 1                                 # the bottom of the stack: "Carries: ..."
    for o in bpy.context.selected_objects:
        o.select_set(False)
    boom = ob(active)
    boom.select_set(True)
    bpy.context.view_layer.objects.active = boom
    return 1.0


@step
def s_settle():
    """Let the panels finish sliding into place (they animate on redraws)."""
    win, area, region, sb = areas()
    for k in range(30):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=sb.x + 50 + k, y=sb.y + 200 + 40 * k)
    for a in win.screen.areas:
        a.tag_redraw()
    return 3.0


@step
def s_settle2():
    win, area, region, sb = areas()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 200, y=region.y + 200)
    for a in win.screen.areas:
        a.tag_redraw()
    return 3.0


@step
def s_shot():
    win, area, region, sb = areas()
    full = os.path.join(OUT, "screen.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    # side panel only (screen y grows downwards, Blender's upwards)
    h = win.height
    top = h - (sb.y + sb.height)
    crop = os.path.join(OUT, "sidebar_full.png")
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{sb.height}+{sb.x}+{top}", "+repage",
                    "-trim", "+repage", crop], check=False)
    log("sidebar", sb.x, sb.y, sb.width, sb.height, "->", crop)
    return 0.5


@step
def s_quit():
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_wait = [0.0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        r = 0.5
    if r == "wait":
        if not _wait[0]:
            _wait[0] = time.time()
        if time.time() - _wait[0] > float(os.environ.get("UISHOT_WAIT", "120")):
            log(fn.__name__, "timeout")
            _i[0] += 1
            _wait[0] = 0.0
        return 1.0
    _wait[0] = 0.0
    _i[0] += 1
    return r if r is not None else None


bpy.context.preferences.view.ui_scale = float(os.environ.get("UISHOT_SCALE", "1.5"))
open_all_panels()
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
