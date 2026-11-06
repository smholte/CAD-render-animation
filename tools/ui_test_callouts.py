"""Real-app test of labels, picture cards and music (task 0025).

In the real Fresing Render app with simulated input: a label is added on a part of the crane (the button's
script path), its words and step are set, the animation gets a picture card and a music file, the background
queue renders a short MP4 and the video is checked (size, length, sound track as long as the video, the
picture in its corner); a still goes through the queue with the label. Save + reopen keeps labels, cards and
music. Then screenshots of the Labels, Pictures and Music sub-panels (callouts_panel_5.png, _6.png).

Install the extension and the app template first (see tools/ci_real_app.py). Run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render \
        --enable-event-simulate --python tools/ui_test_callouts.py
UITEST_QUICK=1 skips the queue. Log and pictures go to $UITEST_OUT (default ~/fresing_ui_callouts).
"""

import math
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_callouts"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
QUICK = bool(os.environ.get("UITEST_QUICK"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_callouts.log"), "w")
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




def make_wav(path, seconds=3.0, rate=22050):
    import wave

    import numpy as np
    data = (np.sin(np.arange(int(rate * seconds)) * 0.12) * 12000).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return path


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
def s_labels():
    s = bpy.context.scene.fresing
    build = mod("blender.build")
    parts = [o for o in bpy.context.scene.objects if o.get(build.PROP_KIND) == "part"]
    boom = next(o for o in parts if o.get(build.PROP_NAME) == "BOOM")
    check("Add a label needs a model", bpy.ops.fresing.callout_add.poll())
    r = op("fresing.callout_add", part=boom.name, text="Boom")
    r2 = op("fresing.callout_add", part=parts[0].name, text="Second label")
    check("two labels added", r == {"FINISHED"} and r2 == {"FINISHED"} and len(s.callouts) == 2)
    s.callouts[0].text = "Boom, Ø40"
    check("label keeps its part", s.callouts[0].part == boom and s.callouts_index == 1)
    check("Move the point and Remove are available", bpy.ops.fresing.callout_move.poll()
          and bpy.ops.fresing.callout_remove.poll())
    op("fresing.callout_remove")
    check("a label removed", len(s.callouts) == 1)
    check("label panels registered", all(hasattr(bpy.types, n) for n in (
        "FRESING_PT_labels", "FRESING_PT_cards", "FRESING_PT_music")))
    return 0.5


@step
def s_animation():
    s = bpy.context.scene.fresing
    op("fresing.anim_add")
    a = s.animations[s.animations_index]
    a.fps, a.quality, a.out_resolution, a.tail = "24", "draft", "preview", 0.0
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Slow orbit", 0.0, 0.2
    b.camera_mode, b.orbit_angle = "ORBIT", math.radians(10)
    s.callouts[0].step = "Slow orbit"
    card = make_logo(os.path.join(OUT, "card.png"), (20, 200, 40))
    r = op("fresing.card_add", filepath=card)
    check("picture added", r == {"FINISHED"} and len(a.cards) == 1 and a.cards[0].enabled)
    c = a.cards[0]
    c.mode, c.corner, c.start, c.duration, c.caption = "CORNER", "BL", 0.0, 0.2, "Hydraulics"
    a.music_on, a.music_file = True, make_wav(os.path.join(OUT, "music.wav"))
    a.music_fade_in, a.music_fade_out = 0.1, 0.1
    a.fin_title_on, a.fin_title, a.fin_title_seconds = True, "Test crane", 0.5
    STATE["anim"] = a.name
    return 0.5


@step
def s_queue_start():
    if QUICK:
        return 0.2
    s = bpy.context.scene.fresing
    op("fresing.queue_add", kind="ANIMATION")
    op("fresing.queue_add", kind="STILL")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "callouts.blend"))
    queue = mod("blender.queue")
    with override():
        STATE["qdir"] = queue.start(bpy.context)
    check("two jobs in the queue", len(s.queue) == 2)
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
    jobs = list(sc.fresing.queue)
    check("animation and still done", all(j.status == "DONE" for j in jobs),
          [(j.status, j.message) for j in jobs] + [queue.log_tail(STATE["qdir"], 20)])
    STATE["mp4"] = jobs[0].output
    STATE["still"] = jobs[1].output
    log("queue log: " + queue.log_tail(STATE["qdir"], 30).replace("\n", " | "))
    return 0.5


@step
def s_check_video():
    if QUICK:
        return 0.2
    import numpy as np
    mp4 = STATE.get("mp4", "")
    frames = [f for f in os.listdir(mp4[:-4]) if f.startswith("frame_") and f.endswith(".png")]
    clip = bpy.data.movieclips.load(mp4)
    try:
        size, dur = tuple(clip.size), clip.frame_duration
    finally:
        bpy.data.movieclips.remove(clip)
    total = 12 + len(frames)
    check("MP4 has the title card and the animation", size == (960, 540) and dur == total, (size, dur, len(frames)))
    import aud
    sound = aud.Sound(mp4)
    seconds = sound.length / sound.specs[0]
    check("MP4 has a sound track as long as the video", abs(seconds - total / 24.0) < 0.15, (seconds, total / 24.0))
    check("the queue log mentions the labels", "labels" in queue_log())
    still = pixels(STATE["still"])
    check("the still has the label's box (dark patch on the grey)", (still.sum(axis=2) < 200).mean() > 0.002,
          float((still.sum(axis=2) < 200).mean()))
    return 0.5


def queue_log():
    queue = mod("blender.queue")
    return queue.log_tail(STATE.get("qdir", ""), 400)


@step
def s_save_reopen():
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "callouts2.blend"))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "callouts2.blend"))
    return 2.0


@step
def s_reopened():
    s = bpy.context.scene.fresing
    a = s.animations[0]
    check("labels, picture and music survive save + reopen",
          len(s.callouts) == 1 and s.callouts[0].part is not None and s.callouts[0].step == "Slow orbit"
          and len(a.cards) == 1 and a.music_on and a.music_file.endswith("music.wav"))
    return 0.5


COPIES = ("FRESING_PT_labels",)


def _open_copy(name, parent=None, cls=None):
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
    for cls in sorted(drop, key=lambda c: 0 if getattr(c, "bl_parent_id", "") else 1):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            log("could not hide", cls.__name__)


@step
def s_panel_only_5():
    _hide({"FRESING_PT_scene", "FRESING_PT_animation", "FRESING_PT_cards", "FRESING_PT_music", *COPIES})
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
    sidebar_shot("callouts_panel_5", 3000)
    log("screenshot callouts_panel_5")
    return 0.3


@step
def s_panel_only_6():
    bpy.utils.unregister_class(bpy.types.FRESING_PT_labels_open)
    bpy.utils.unregister_class(bpy.types.FRESING_PT_scene)
    cards, music = bpy.types.FRESING_PT_cards, bpy.types.FRESING_PT_music
    bpy.utils.unregister_class(cards)
    bpy.utils.unregister_class(music)
    _open_copy("FRESING_PT_animation")
    _open_copy("FRESING_PT_cards", parent="FRESING_PT_animation_open", cls=cards)
    _open_copy("FRESING_PT_music", parent="FRESING_PT_animation_open", cls=music)
    redraw()
    return 1.5


@step
def s_shot_6():
    redraw()
    wiggle()
    return 2.0


@step
def s_shot_6b():
    sidebar_shot("callouts_panel_6", 3000)
    log("screenshot callouts_panel_6")
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
