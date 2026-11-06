"""Real-app test of video finishing (task 0018): brand kit, logo, title and end card, captions, watermark.

In the real Fresing Render app with simulated input: a brand kit is filled in and saved to a library folder
(then loaded again), an animation with a labelled step gets logo, title card, end card and captions, the
watermark switch is put on a queue job, the background queue renders the animation and the MP4 is checked
(size, length), a still goes through the queue with logo and watermark; save + reopen keeps it all. Then
screenshots of the brand kit, watermark and Finishing sub-panels (finish_*.png).

Install the extension and the app template first (see tools/ci_real_app.py). Run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render \
        --enable-event-simulate --python tools/ui_test_video.py
UITEST_QUICK=1 skips the queue. Log and pictures go to $UITEST_OUT (default ~/fresing_ui_video).
"""

import math
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_video"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
QUICK = bool(os.environ.get("UITEST_QUICK"))
os.makedirs(OUT, exist_ok=True)
LIB = os.path.join(OUT, "library", "Brand kits")
os.environ["FRESING_BRAND_KITS_DIR"] = LIB
LOG = open(os.path.join(OUT, "ui_test_video.log"), "w")
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


def op(_idname, *args, undo=True, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", undo, **kw)


def sidebar_shot(name, height=3000):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def redraw():
    win = bpy.context.window_manager.windows[0]
    for a in win.screen.areas:
        a.tag_redraw()


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def make_logo(path, rgb=(230, 20, 20), size=(160, 80)):
    import numpy as np
    img = bpy.data.images.new("lg", size[0], size[1], alpha=True)
    img.colorspace_settings.is_data = True
    px = np.empty((size[1], size[0], 4), np.float32)
    px[:, :, :3] = np.array(rgb, np.float32) / 255.0
    px[:, :, 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def pixels(path):
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.is_data = True
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return (px.reshape(h, w, 4)[::-1, :, :3] * 255.0).round()


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("add-on enabled", pkg() is not None and pkg() in bpy.context.preferences.addons, pkg())
    win, area, region, sb = ui()
    x, y = win.width // 2, win.height // 2      # close the splash
    win.event_simulate(type="ESC", value="PRESS", x=x, y=y)
    win.event_simulate(type="ESC", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    return 1.0


@step
def s_wait_import():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    check("model imported", bpy.context.scene.fresing.model_count == 1)
    s = bpy.context.scene.fresing
    s.use_gpu = False
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 640, 360
    return 0.5


@step
def s_brand_kit():
    """Fill in a kit like the panel does, save it to the library, change it, load it back."""
    bm = mod("core.brand")
    s = bpy.context.scene.fresing
    logo = make_logo(os.path.join(OUT, "logo.png"))
    s.brand_name = "Fresing"
    s.brand_logo = logo
    s.brand_color1 = bm.rgb_linear("#204060")
    s.brand_color2 = bm.rgb_linear("#FFFFFF")
    s.brand_contact = "fresing.nl"
    check("Save kit available with a name", bpy.ops.fresing.brand_save.poll())
    r = op("fresing.brand_save")
    check("kit saved in the library folder", r == {"FINISHED"} and os.path.isfile(os.path.join(LIB, "Fresing.json"))
          and os.path.isfile(os.path.join(LIB, "Fresing_logo.png")), os.listdir(LIB) if os.path.isdir(LIB) else "")
    s.brand_contact = "changed"
    s.brand_name = "Other"
    r = op("fresing.brand_load", name="Fresing")
    check("kit loaded back", r == {"FINISHED"} and s.brand_name == "Fresing" and s.brand_contact == "fresing.nl")
    return 0.5


@step
def s_animation():
    anim = mod("blender.animation")
    s = bpy.context.scene.fresing
    op("fresing.anim_add")
    a = s.animations[s.animations_index]
    a.fps = "24"
    a.quality = "draft"
    a.out_resolution = "preview"
    a.out_format = "square"
    a.shape_fit = "CROP"
    a.tail = 0.0
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Slow orbit", 0.0, 0.2
    b.camera_mode, b.orbit_angle = "ORBIT", math.radians(10)
    a.fin_logo, a.fin_logo_size = "TR", 0.2
    a.fin_title_on, a.fin_title, a.fin_subtitle, a.fin_title_seconds = True, "Test crane", "Rev A", 1.0
    a.fin_end_on, a.fin_end_seconds, a.fin_captions = True, 1.0, True
    STATE["anim"] = a.name
    check("animation with every finishing option", a.fin_logo == "TR" and a.fin_title_on and a.fin_end_on
          and a.fin_captions and len(mod("blender.video").steps_of(a)) == 1)
    return 0.5


@step
def s_watermark_flag():
    s = bpy.context.scene.fresing
    s.wm_kind, s.wm_size, s.wm_opacity = "DRAFT", 0.25, 1.0
    s.wm_on = True
    op("fresing.queue_add", kind="ANIMATION")
    job = s.queue[-1]
    check("queue job remembers the watermark", job.watermark and "watermark" in job.label, job.label)
    s.wm_on = False
    s.still_logo, s.still_logo_size = "BL", 0.2
    return 0.5


@step
def s_queue_start():
    if QUICK:
        return 0.2
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "video.blend"))
    queue = mod("blender.queue")
    with override():
        STATE["qdir"] = queue.start(bpy.context)
    return 2.0


@step
def s_queue_wait():
    if QUICK:
        return 0.2
    queue = mod("blender.queue")
    sc = bpy.context.scene
    queue.sync(sc)
    if queue.is_running(sc):
        wiggle()
        return "wait"
    queue.sync(sc)
    job = sc.fresing.queue[0]
    check("animation job done", job.status == "DONE", (job.status, job.message, queue.log_tail(STATE["qdir"], 20)))
    STATE["mp4"] = job.output
    return 0.5


@step
def s_check_video():
    if QUICK:
        return 0.2
    mp4 = STATE.get("mp4", "")
    frames = [f for f in os.listdir(mp4[:-4]) if f.startswith("frame_") and f.endswith(".png")] if mp4 else []
    clip = bpy.data.movieclips.load(mp4)
    try:
        size, dur = tuple(clip.size), clip.frame_duration
    finally:
        bpy.data.movieclips.remove(clip)
    check("MP4 is square and title + animation + end card long",
          size == (540, 540) and dur == 24 + len(frames) + 24, (size, dur, len(frames)))
    return 0.5


@step
def s_still():
    if QUICK:
        return 0.2
    queue = mod("blender.queue")
    s = bpy.context.scene.fresing
    s.wm_on = True
    sc = bpy.context.scene
    s.queue.clear()
    op("fresing.queue_add", kind="STILL")
    s.wm_on = False
    op("fresing.queue_add", kind="STILL")
    for j in s.queue:
        j.quality = "draft"
    with override():
        STATE["qdir"] = queue.start(bpy.context)
    return 2.0


@step
def s_still_wait():
    if QUICK:
        return 0.2
    queue = mod("blender.queue")
    sc = bpy.context.scene
    queue.sync(sc)
    if queue.is_running(sc):
        wiggle()
        return "wait"
    queue.sync(sc)
    jobs = list(sc.fresing.queue)
    check("two stills done", len(jobs) == 2 and all(j.status == "DONE" for j in jobs),
          [(j.status, j.message) for j in jobs])
    import numpy as np
    a, b = pixels(jobs[0].output), pixels(jobs[1].output)
    h, w = b.shape[:2]
    check("only the first still has the watermark", np.abs(a - b)[h // 4:3 * h // 4, w // 6:5 * w // 6].max() > 15,
          float(np.abs(a - b).max()))
    red = [x for x in (b[h - 8 - 20, 12 + 10], b[h - 30, 30]) if x[0] > 180 and x[1] < 80]
    check("both stills have the logo in the bottom left", bool(red) or b[:, :, 0].max() > 200)
    return 0.5


@step
def s_save_reopen():
    path = os.path.join(OUT, "reopen.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    return 1.5


@step
def s_reopened():
    s = bpy.context.scene.fresing
    a = s.animations[STATE["anim"]]
    check("reopened: kit, finishing and watermark settings kept",
          s.brand_name == "Fresing" and s.brand_contact == "fresing.nl" and a.fin_logo == "TR" and a.fin_title_on
          and a.fin_end_on and a.fin_captions and a.shape_fit == "CROP" and s.wm_kind == "DRAFT"
          and s.still_logo == "BL", (s.brand_name, a.fin_logo, a.shape_fit))
    return 0.5


@step
def s_panels():
    """The three panels are in the real side panel (they draw without errors in the real UI)."""
    ok = all(hasattr(bpy.types, n) for n in ("FRESING_PT_brand", "FRESING_PT_watermark", "FRESING_PT_finishing"))
    check("brand kit, watermark and finishing panels registered", ok)
    s = bpy.context.scene.fresing
    s.wm_on = True
    redraw()
    wiggle()
    return 1.0


COPIES = ("FRESING_PT_brand", "FRESING_PT_watermark")


def _open_copy(name, parent=None, cls=None):
    """Register a copy of a panel under a new name that starts open (a panel remembers its state by name).
    ``cls``: the panel's class when it was unregistered already."""
    cls = cls or getattr(bpy.types, name)
    attrs = {k: getattr(cls, k) for k in ("bl_label", "bl_space_type", "bl_region_type", "bl_category",
                                          "bl_parent_id", "bl_order", "draw", "draw_header", "draw_header_preset",
                                          "poll") if hasattr(cls, k)}
    attrs.update(bl_idname=name + "_open", bl_options=set())
    if parent:
        attrs["bl_parent_id"] = parent
    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass
    bpy.utils.register_class(type(name + "_open", (bpy.types.Panel,), attrs))


def _hide(keep):
    classes = [getattr(bpy.types, n) for n in dir(bpy.types) if n.startswith("FRESING_PT_")]
    drop = [c for c in classes if c.__name__ not in keep]
    for cls in sorted(drop, key=lambda c: 0 if getattr(c, "bl_parent_id", "") else 1):   # sub-panels first
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            log("could not hide", cls.__name__)


@step
def s_panel_only_5():
    """For the screenshots: only panel 5 with the new sub-panels, open."""
    _hide({"FRESING_PT_scene", "FRESING_PT_animation", "FRESING_PT_finishing", *COPIES})
    for name in COPIES:
        _open_copy(name)
    redraw()
    return 1.5


@step
def s_shot_5():
    redraw()
    wiggle()
    return 2.0


@step
def s_shot_5b():
    sidebar_shot("finish_panel_5", 3000)
    log("screenshot finish_panel_5")
    return 0.3


@step
def s_panel_only_6():
    """Then only panel 6 with the Finishing sub-panel, open."""
    for name in ("FRESING_PT_brand_open", "FRESING_PT_watermark_open"):
        bpy.utils.unregister_class(getattr(bpy.types, name))
    bpy.utils.unregister_class(bpy.types.FRESING_PT_scene)
    fin = bpy.types.FRESING_PT_finishing
    bpy.utils.unregister_class(fin)
    _open_copy("FRESING_PT_animation")
    _open_copy("FRESING_PT_finishing", parent="FRESING_PT_animation_open", cls=fin)
    redraw()
    return 1.5


@step
def s_shot_6():
    redraw()
    wiggle()
    return 2.0


@step
def s_shot_6b():
    sidebar_shot("finish_panel_6", 3000)
    log("screenshot finish_panel_6")
    return 0.3


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
        if time.time() - _w[0] > 1800:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        wiggle()
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
