"""Real-app test of labels, picture cards and music (task 0025).

In the real Fresing Render app with simulated input: "Add label" waits for a click, a click on a part puts a
label on it (a click on the side panel does not); a second label is added; an animation gets a picture card
and a music file; the background queue renders it and the MP4 is checked (size, length, an audio track of the
video's length); a still through the queue has the label; save + reopen keeps it all. Then screenshots of the
Labels and Pictures & music sub-panels (callout_*.png).

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
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_callouts"))
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_decals_a.step")
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


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name and o.get("fr_kind") == "part"),
                  key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def to_window(p):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(p))
    return int(region.x + co.x), int(region.y + co.y)


def top_of(name, n=0, dx=0.0, dy=0.0):
    lo, hi = mod("blender.build").world_bounds([find(name, n)])
    return to_window(((lo[0] + hi[0]) / 2 + dx, (lo[1] + hi[1]) / 2 + dy, hi[2]))


def event(kind, x, y, value="PRESS"):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=kind, value=value, x=x, y=y)


def click(x, y):
    event("LEFTMOUSE", x, y)
    event("LEFTMOUSE", x, y, value="RELEASE")


def make_tone(path, seconds=6, rate=22050):
    import wave

    import numpy as np
    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        t = np.arange(int(rate * seconds))
        mono = (9000 * np.sin(2 * math.pi * 440 * t / rate)).astype("<i2")
        w.writeframes(np.repeat(mono, 2).tobytes())
    return path


def mp4_tracks(path):
    """{handler: seconds} of the tracks of an MP4 file (no ffmpeg needed)."""
    import struct
    data = open(path, "rb").read()

    def boxes(start, end):
        i = start
        while i + 8 <= end:
            size, kind = struct.unpack(">I4s", data[i:i + 8])
            hdr = 8
            if size == 1:
                size, hdr = struct.unpack(">Q", data[i + 8:i + 16])[0], 16
            if size == 0:
                size = end - i
            yield kind.decode("latin1"), i + hdr, i + size
            i += size

    out = {}
    for kind, a, b in boxes(0, len(data)):
        if kind != "moov":
            continue
        for k2, a2, b2 in boxes(a, b):
            if k2 != "trak":
                continue
            handler, secs = "", 0.0
            for k3, a3, b3 in boxes(a2, b2):
                if k3 != "mdia":
                    continue
                for k4, a4, b4 in boxes(a3, b3):
                    if k4 == "hdlr":
                        handler = data[a4 + 8:a4 + 12].decode("latin1")
                    if k4 == "mdhd":
                        if data[a4] == 1:
                            scale, dur = struct.unpack(">IQ", data[a4 + 20:a4 + 32])
                        else:
                            scale, dur = struct.unpack(">II", data[a4 + 12:a4 + 20])
                        secs = dur / scale
            out[handler] = secs
    return out


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("add-on enabled", pkg() is not None and pkg() in bpy.context.preferences.addons, pkg())
    win, area, region, sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
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
    s = bpy.context.scene.fresing
    check("model imported", s.model_count == 1)
    s.use_gpu = False
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 640, 360
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d                 # straight down on the panel and the barrels
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((1, 0, 0, 0))
    r3d.view_location = Vector((0.55, 0.15, 0.0))
    r3d.view_distance = 1.6
    area.spaces.active.shading.type = "SOLID"
    return 1.0


@step
def s_add_start():
    with override():
        res = bpy.ops.fresing.callout_add("INVOKE_DEFAULT")
    s = bpy.context.scene.fresing
    check("'Add label' waits for a click", res == {"RUNNING_MODAL"} and s.callout_picking, res)
    return 0.5


@step
def s_side_panel_click():
    win, area, region, sb = ui()
    click(sb.x + sb.width // 2, sb.y + 40)
    return 0.5


@step
def s_click_part():
    s = bpy.context.scene.fresing
    check("a click on the side panel adds no label", len(s.callouts) == 0 and s.callout_picking)
    click(*top_of("PANEL", dx=-0.08, dy=0.03))
    return 0.8


@step
def s_label_added():
    s = bpy.context.scene.fresing
    ok = len(s.callouts) == 1 and not s.callout_picking and s.callouts[0].obj is not None
    check("a click on a part puts a label on it", ok, [(c.text, c.obj) for c in s.callouts])
    if ok:
        c = s.callouts[0]
        lo, hi = mod("blender.build").world_bounds([c.obj])
        p = c.obj.matrix_world @ Vector(c.local)
        check("the label's point is on the clicked part", all(lo[i] - 1e-3 <= p[i] <= hi[i] + 1e-3 for i in range(3)))
        c.text = "Control panel"
    # a second label on a barrel, then Esc cancels a third
    callouts = mod("blender.callouts")
    b = find("BARREL", 0)
    c2 = callouts.add(bpy.context.scene, b, tuple(b.bound_box[6]), "Barrel")
    c2.on_still = False
    with override():
        bpy.ops.fresing.callout_add("INVOKE_DEFAULT")
    win, area, region, sb = ui()
    event("ESC", region.x + 200, region.y + 200)
    event("ESC", region.x + 200, region.y + 200, value="RELEASE")
    return 0.8


@step
def s_esc():
    s = bpy.context.scene.fresing
    check("Esc cancels adding a label", not s.callout_picking and len(s.callouts) == 2)
    return 0.3


@step
def s_animation():
    s = bpy.context.scene.fresing
    op("fresing.anim_add")
    a = s.animations[s.animations_index]
    a.fps = "24"
    a.quality = "draft"
    a.out_resolution = "preview"
    a.out_format = "presentation"
    a.tail = 0.0
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Slow orbit", 0.0, 0.25
    b.camera_mode, b.orbit_angle = "ORBIT", math.radians(10)
    s.callouts[1].step = "Slow orbit"
    card = os.path.join(OUT, "photo.png")
    make_logo(card, (20, 160, 60), (320, 180))
    op("fresing.card_add")
    c = a.cards[0]
    c.file, c.mode, c.seconds, c.at, c.caption = card, "FULL", 1.0, 0.0, "Photo of the machine"
    a.music_file = make_tone(os.path.join(OUT, "tone.wav"))
    a.music_volume, a.music_fade_in, a.music_fade_out = 0.7, 0.5, 0.5
    STATE["anim"] = a.name
    fin = mod("blender.video").finishing_for_animation(bpy.context.scene, a)
    check("animation has a picture card and music", len(fin.cards) == 1 and fin.music_file.endswith("tone.wav")
          and len(a.cards) == 1)
    op("fresing.queue_add", kind="ANIMATION")
    return 0.5


@step
def s_queue_start():
    if QUICK:
        return 0.2
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "callouts.blend"))
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
    folder = mp4[:-4]
    frames = [f for f in os.listdir(folder) if f.startswith("frame_") and f.endswith(".png")]
    clip = bpy.data.movieclips.load(mp4)
    try:
        size, dur = tuple(clip.size), clip.frame_duration
    finally:
        bpy.data.movieclips.remove(clip)
    check("MP4 is the animation plus the 1 s picture card", size == (960, 540) and dur == len(frames) + 24,
          (size, dur, len(frames)))
    tracks = mp4_tracks(mp4)
    check("MP4 has sound as long as the video", "soun" in tracks and abs(tracks["soun"] - dur / 24) < 0.2, tracks)
    lines = os.path.join(folder, "_lines")
    check("label lines were drawn for the frames", os.path.isdir(lines) and len(os.listdir(lines)) >= 3)
    return 0.5


@step
def s_still():
    if QUICK:
        return 0.2
    queue = mod("blender.queue")
    s = bpy.context.scene.fresing
    s.queue.clear()
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
    job = sc.fresing.queue[0]
    check("still done", job.status == "DONE", (job.status, job.message))
    img = pixels(job.output)
    h, w = img.shape[:2]
    a = mod("blender.callouts").anchor_at(sc, sc.fresing.callouts[0], (640, 360))
    ratio = w / 640.0
    spot = img[max(0, int(h - a[1] * ratio) - 1):int(h - a[1] * ratio) + 2,
               max(0, int(a[0] * ratio) - 1):int(a[0] * ratio) + 2] if a else None
    check("the still has the white dot of the label's line on its part", spot is not None and spot.min() > 200,
          None if spot is None else float(spot.min()))
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
    check("reopened: labels, picture card and music kept",
          len(s.callouts) == 2 and s.callouts[0].obj is not None and s.callouts[0].text == "Control panel"
          and s.callouts[1].step == "Slow orbit" and len(a.cards) == 1 and a.music_file.endswith("tone.wav")
          and abs(a.music_volume - 0.7) < 1e-6, (len(s.callouts), len(a.cards)))
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
    check("labels and pictures panels registered", hasattr(bpy.types, "FRESING_PT_labels")
          and hasattr(bpy.types, "FRESING_PT_pictures"))
    _hide({"FRESING_PT_scene", "FRESING_PT_animation", "FRESING_PT_pictures", *COPIES})
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
    sidebar_shot("callout_panel_5", 2200)
    return 0.3


@step
def s_panel_only_6():
    bpy.utils.unregister_class(bpy.types.FRESING_PT_labels_open)
    bpy.utils.unregister_class(bpy.types.FRESING_PT_scene)
    pic = bpy.types.FRESING_PT_pictures
    bpy.utils.unregister_class(pic)
    _open_copy("FRESING_PT_animation")
    _open_copy("FRESING_PT_pictures", parent="FRESING_PT_animation_open", cls=pic)
    redraw()
    return 1.5


@step
def s_shot_6():
    redraw()
    wiggle()
    return 2.0


@step
def s_shot_6b():
    sidebar_shot("callout_panel_6", 2600)
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
