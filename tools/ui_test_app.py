"""Drive the real Fresing Render app (Blender with a window, on a virtual screen) with simulated input.

The extension must be installed and enabled in that Blender (Install.bat does this; on Linux:
blender -b --command extension install-file -r user_default -e <zip>, then enable it), and the
app template copied to <user scripts>/startup/bl_app_templates_user/fresing_render.

Run:  xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \
          --python tools/ui_test_app.py
      UITEST_QUICK=1 skips the slow renders. Screenshots and ui_test.log go to $UITEST_OUT (default ~/fresing_ui_test).
"""

import math
import os
import subprocess
import sys
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test.log"), "w")
RESULTS = []


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
    for m in addon_utils.modules():
        if m.__name__.endswith("fresing_render"):
            return m.__name__
    return None


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region,
                                     scene=win.scene)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    env = dict(os.environ)
    subprocess.run(["import", "-window", "root", path], env=env, check=False)
    log("screenshot", path)


def to_window(world_pt):
    win, area, region = ui()
    rv3d = region.data
    co = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(world_pt))
    return int(region.x + co.x), int(region.y + co.y)


def click(x, y, shift=False):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y, shift=shift)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y, shift=shift)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)    # people move the mouse after a click


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n]


# ---------------------------------------------------------------------------
# steps: each returns the delay before the next step, or None to wait for a condition
# ---------------------------------------------------------------------------

STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("add-on enabled", pkg() is not None and pkg() in bpy.context.preferences.addons, pkg())
    check("app template: units mm", bpy.context.scene.unit_settings.length_unit == "MILLIMETERS")
    win, area, region = ui()
    sidebar = next((r for r in area.regions if r.type == "UI"), None)
    check("side panel open", sidebar is not None and sidebar.width > 50, f"width {sidebar.width if sidebar else 0}")
    shot("01_start")
    sidebar = next((r for r in area.regions if r.type == "UI"), None)
    check("side panel shows the Fresing tab", getattr(sidebar, "active_panel_category", "") == "Fresing",
          getattr(sidebar, "active_panel_category", "?"))
    # close the splash (a real user's first click does that) and widen the side panel
    win.event_simulate(type="ESC", value="PRESS", x=900, y=1300)
    win.event_simulate(type="ESC", value="RELEASE", x=900, y=1300)
    if sidebar is not None:
        x0, y0 = sidebar.x + 2, sidebar.y + sidebar.height // 3
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x0, y=y0)
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x0, y=y0)
        for k in range(1, 11):
            win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x0 - 25 * k, y=y0)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x0 - 250, y=y0)
    return 1.0


@step
def s_import():
    # A step of its own: simulated events are queued, so an Esc sent in the same step reaches the
    # import's modal handler and cancels it (only an import from the cache escaped that).
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    return 1.0


@step
def s_wait_import():
    s = bpy.context.scene.fresing
    if s.model_count == 0:
        if _wait_start[0] and time.time() - _wait_start[0] > 300:      # the crane takes seconds
            check("import in the app (background reader + modal)", False,
                  "not finished after 5 minutes: " + s.last_message)
            return 0.5
        return "wait"
    check("import in the app (background reader + modal)", s.model_count == 1, s.last_message)
    win, area, region = ui()
    d = region.data.view_location
    check("view framed on the model", abs(d.x - 0.8) < 0.3 and abs(d.y - 0.3) < 0.3, tuple(round(v, 2) for v in d))
    return 1.0


@step
def s_panels():
    shot("02_imported")
    s = bpy.context.scene.fresing
    # click the boom in the viewport: subassembly selection
    boom = find("BOOM")
    x, y = to_window(boom.matrix_world @ Vector((1.0, 0, 0.05)))
    click(x, y)
    return 0.8


@step
def s_wiggle():
    # a person's hand keeps moving the mouse a little after a click
    win, area, region = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 400, y=region.y + 400)
    return 0.8


@step
def s_after_click():
    sel = {o.get("fr_name") for o in bpy.context.selected_objects}
    check("click selects the whole subassembly", {"BOOM", "BOOM.PIN", "BOOM.ASM"} <= sel, sorted(sel))
    check("selection list follows the click", bpy.context.scene.fresing.tree[bpy.context.scene.fresing.tree_index].obj.get("fr_name") == "BOOM.ASM")
    shot("03_boom_selected")
    # Add rotate joint (the button's operator) and click the pin
    with override():
        res = bpy.ops.fresing.joint_pick_axis("INVOKE_DEFAULT", mode="NEW", kind="ROTATE")
    check("pick tool starts", "RUNNING_MODAL" in res, res)
    return 0.5


def first_header():
    """Window position of the title row of the first side-panel section (1 Import).

    A click there only folds that section, whatever the panels below look like; a click in the
    middle of the side panel lands on whatever button the layout puts there (a drop-down opened
    by it takes the next click in the view)."""
    win, area, region = ui()
    sidebar = next(r for r in area.regions if r.type == "UI")
    px = bpy.context.preferences.system.pixel_size
    return sidebar.x + sidebar.width // 2, sidebar.y + sidebar.height - int(19 * px)


@step
def s_click_sidebar_during_pick():
    # a click on the side panel must not create a joint behind it (the side panel lies over the view)
    click(*first_header())
    return 0.5


@step
def s_click_pin():
    s = bpy.context.scene.fresing
    check("side-panel click ignored by the pick tool", len(s.joints) == 0)
    pin = find("BOOM.PIN")
    # a point on top of the pin's round face (Ø40 along Y), in front of the pedestal
    x, y = to_window(pin.matrix_world @ Vector((0, -0.085, 0.0199)))
    click(x, y)
    return 0.8


@step
def s_joint_made():
    s = bpy.context.scene.fresing
    ok = len(s.joints) == 1
    detail = ""
    if ok:
        joints = mod("blender.joints")
        o, d = joints.axis_world(s.joints[0])
        detail = f"axis through {tuple(round(v, 3) for v in o)} dir {tuple(round(v, 3) for v in d)}"
        ok = abs(abs(d.y) - 1) < 1e-3 and abs(o.x - 0.1) < 1e-3 and abs(o.z - 0.4) < 1e-3
    check("click on the pin hole gives the pin axis", ok, detail + " | " + s.last_message)
    click(*first_header())                 # unfold section 1 again
    if len(s.joints):
        joints = mod("blender.joints")
        joints.set_value(s.joints[0], math.radians(-30) * (1 if joints.axis_world(s.joints[0])[1].y > 0 else -1))
    return 0.8


@step
def s_trolley():
    s = bpy.context.scene.fresing
    joints = mod("blender.joints")
    tr = find("TROLLEY.ASM")
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        tr.select_set(True)
        bpy.context.view_layer.objects.active = tr
    try:
        j = joints.create(bpy.context.scene, "SLIDE", [tr], tr.matrix_world.translation, Vector((1, 0, 0)),
                          base=find("BOOM.ASM"))
        joints.set_value(j, 0.4)
        check("slide joint on the boom", True)
    except Exception as exc:
        check("slide joint on the boom", False, str(exc))
    bpy.context.view_layer.update()
    shot("04_joints")
    with override():
        bpy.ops.fresing.pose_save(name="Raised")
        bpy.ops.fresing.pose_reset()
        bpy.ops.fresing.shot_save(name="Hero", scheme="__current__", pose="Raised", visibility="__current__")
        bpy.ops.fresing.anim_add()
        a = s.animations[0]
        a.tail = 0.0
        bpy.ops.fresing.block_add(kind="POSE")
        a.blocks[0].pose = "Raised"
        a.blocks[0].duration = 0.3
        bpy.ops.fresing.block_add(kind="CAMERA")
        a.blocks[1].camera_mode = "ORBIT"
        a.blocks[1].start = 0.0
        a.blocks[1].duration = 0.3
        bpy.ops.fresing.anim_build(play=True)
    check("Build & play starts playback", bpy.context.screen.is_animation_playing if bpy.context.screen else
          bpy.context.window_manager.windows[0].screen.is_animation_playing)
    return 0.7


@step
def s_playing():
    sc = bpy.context.scene
    check("animation advances in the viewport", sc.frame_current > 1, f"frame {sc.frame_current}")
    shot("05_playing")
    with override():
        bpy.ops.screen.animation_cancel(restore_frame=False)
        sc.frame_set(20)
    return 0.5


QUICK = bool(os.environ.get("UITEST_QUICK"))


@step
def s_queue():
    if QUICK:
        return 0.1
    sc = bpy.context.scene
    s = sc.fresing
    shot("06_frame20")
    s.out_folder = os.path.join(OUT, "renders")
    a = s.animations[0]
    a.out_resolution = "preview"
    a.quality = "eevee"                   # also tests the EEVEE path of the queue
    with override():
        bpy.ops.fresing.queue_add(kind="SHOT", name="Hero")
        s.queue[-1].quality = "draft"
        s.out_resolution = "preview"
        bpy.ops.fresing.queue_add(kind="ANIMATION", name=a.name)
        res = bpy.ops.fresing.queue_start()
    check("queue starts a background Blender", res == {"FINISHED"} and s.queue_pid > 0,
          f"{res} pid {s.queue_pid} cmd binary {bpy.app.binary_path}")
    globals()["_qt0"] = time.time()
    return 2.0


@step
def s_queue_wait():
    if QUICK:
        return 0.1
    sc = bpy.context.scene
    q = mod("blender.queue")
    if q.is_running(sc) and time.time() - globals()["_qt0"] < 1500:
        return "wait"
    q.sync(sc)
    jobs = [(j.label, j.status, j.message, j.output) for j in sc.fresing.queue]
    check("queue: image + animation rendered", all(j[1] == "DONE" for j in jobs), jobs)
    mp4 = sc.fresing.queue[-1].output
    check("MP4 written", mp4.endswith(".mp4") and os.path.isfile(mp4), mp4)
    shot("07_queue_done")
    # undo after the queue: the queue state survives
    return 0.5


@step
def s_render_image():
    if QUICK:
        return 0.1
    s = bpy.context.scene.fresing
    s.quality = "draft"
    s.use_gpu = False
    with override():
        res = bpy.ops.fresing.render("EXEC_DEFAULT", quality="draft")
    check("Render image starts (modal, render window)", "RUNNING_MODAL" in res or res == {"FINISHED"}, res)
    globals()["_rt0"] = time.time()
    return 2.0


@step
def s_render_wait():
    if QUICK:
        return 0.1
    s = bpy.context.scene.fresing
    if not s.last_message.startswith(("Saved", "Render cancelled", "Could not")) and time.time() - globals()["_rt0"] < 900:
        return "wait"
    path = s.last_message.replace("Saved ", "")
    check("Render image saves the picture", s.last_message.startswith("Saved") and os.path.isfile(path),
          s.last_message)
    shot("07b_render_window")
    return 0.5


@step
def s_save_reload():
    path = os.path.join(OUT, "crane_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    lock = path + ".inuse"
    check("in-use lock written next to the project", os.path.isfile(lock))
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_after_reload():
    sc = bpy.context.scene
    s = sc.fresing
    joints = mod("blender.joints")
    check("joints survive save + reopen", len(s.joints) == 2 and all(joints.is_valid(j) for j in s.joints))
    with override():
        bpy.ops.fresing.shot_apply(name="Hero")
    bpy.context.view_layer.update()
    tip = find("BOOM").matrix_world @ Vector((1.5, 0, 0))
    check("saved scene puts the boom up", tip.z > 0.9, f"tip z {tip.z:.3f}")
    shot("08_scene_hero")
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_wait_start = [0.0]


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
        if not _wait_start[0]:
            _wait_start[0] = time.time()
        if time.time() - _wait_start[0] > 1800:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _wait_start[0] = 0.0
        return 1.0
    _wait_start[0] = 0.0
    _i[0] += 1
    return r if r is not None else None


# open the panels that start closed, so the screenshots show everything
try:
    for name in ("FRESING_PT_animation", "FRESING_PT_queue"):
        cls = getattr(bpy.types, name)
        bpy.utils.unregister_class(cls)
        cls.bl_options = set()
        bpy.utils.register_class(cls)
except Exception:
    log("could not reopen panels", traceback.format_exc())

bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
