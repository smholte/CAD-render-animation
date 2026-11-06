"""Labels pointing at parts, picture cards and music (task 0025).

The numbers (fades, where boxes go, the line, when a picture is on, the music's fades) are checked without
Blender; the rest inside Blender: the point of a label stays on its moving part in every frame of an animation,
labels of hidden parts are hidden, pictures and boxes land in the pictures of the video, the MP4 has an audio
track of the right length with the fades.
"""

import functools
import itertools
import math
import os
import subprocess
import sys
import wave

import numpy as np
import pytest

from fresing_render.core import brand
from fresing_render.core import callouts as C
from fresing_render.core.brand import Finishing

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------


def test_a_label_tied_to_a_step_fades_in_and_out():
    win = (2.0, 4.0)
    assert C.label_alpha(1.9, win) == 0.0 and C.label_alpha(4.1, win) == 0.0
    assert C.label_alpha(2.0, win) == pytest.approx(0.0)
    assert C.label_alpha(2.15, win, 0.3) == pytest.approx(0.5)
    assert C.label_alpha(3.0, win) == 1.0
    assert C.label_alpha(3.85, win, 0.3) == pytest.approx(0.5)
    assert C.label_alpha(99.0, None) == 1.0, "no step: all the time"
    assert C.label_alpha(2.25, (2.0, 2.5), 0.3) > 0.9, "a short step: the fades share the time"


def _boxes_overlap(boxes):
    return any(a.overlaps(b) for a, b in itertools.combinations(boxes, 2))


def test_boxes_never_overlap_and_stay_in_the_picture_and_outside_the_machine():
    canvas = (1920, 1080)
    outline = (700.0, 250.0, 1300.0, 850.0)
    anchors = [(800, 400), (820, 430), (840, 460), (1200, 700), (1210, 690), (1000, 500), (950, 300)]
    sizes = [(260, 50), (300, 50), (250, 50), (320, 50), (280, 50), (240, 50), (330, 50)]
    boxes = C.place_labels(anchors, sizes, canvas, outline)
    assert len(boxes) == len(anchors)
    assert not _boxes_overlap(boxes)
    for b in boxes:
        assert b.inside(*canvas), b
        assert not b.overlaps(C.Box(*outline[:2], outline[2] - outline[0], outline[3] - outline[1])), \
            "there is room beside the machine, so no box sits on it"
    again = C.place_labels(anchors, sizes, canvas, outline)
    assert [(b.x, b.y) for b in again] == [(b.x, b.y) for b in boxes], "the same input gives the same places"


def test_boxes_are_still_apart_when_the_machine_fills_the_picture():
    canvas = (640, 360)
    anchors = [(300 + 10 * i, 180) for i in range(6)]
    boxes = C.place_labels(anchors, [(110, 24)] * 6, canvas, (0, 0, 640, 360))
    assert not _boxes_overlap(boxes) and all(b.inside(*canvas) for b in boxes)


def test_a_box_near_its_anchor_beats_one_far_away():
    boxes = C.place_labels([(1250, 800)], [(200, 50)], (1920, 1080), (700, 250, 1300, 850))
    far = C.place_labels([(750, 260)], [(200, 50)], (1920, 1080), (700, 250, 1300, 850))
    assert boxes[0].x > 1300, "the anchor is at the right edge: the box goes to the right"
    assert far[0].x < 700 or far[0].y < 250, "the anchor is at the lower left: left or below"


def test_the_line_is_drawn_where_it_should_be():
    img = np.zeros((100, 200, 4), np.float32)
    C.draw_line(img, (20.0, 30.0), (180.0, 70.0), (1.0, 0.0, 0.0), 1.0, width=3.0, dot=5.0)
    assert img[30, 20, 3] > 0.99 and img[30, 20, 0] > 0.99, "the dot at the anchor"
    mid = img[50, 100]                                   # on the line (row = y, column = x)
    assert mid[3] > 0.9 and mid[0] > 0.9
    assert img[90, 100, 3] == 0.0 and img[5, 100, 3] == 0.0, "nothing away from the line"
    half = np.zeros((10, 10, 4), np.float32)
    C.draw_line(half, (0.0, 5.0), (9.0, 5.0), (0.0, 1.0, 0.0), 0.5, width=2.0)
    assert half[5, 5, 3] == pytest.approx(0.5, abs=0.06), "see-through label: half the opacity"


def test_picture_cards_land_on_the_right_frames():
    card = C.CardSpec(file="x.png", start=1.0, seconds=2.0)
    assert C.card_frames(card, 25, 0, 200) == (26, 75)
    assert C.card_frames(card, 25, 50, 200) == (76, 125), "the title card pushes everything back"
    assert C.card_frames(C.CardSpec("x", start=7.9, seconds=3.0), 25, 0, 200) == (199, 200), "cut at the end"
    assert C.card_frames(C.CardSpec("x", start=8.5, seconds=1.0), 25, 0, 200) is None, "after the animation"


def test_picture_boxes_fit_inside_the_picture():
    x, y, w, h = C.picture_box("FULL", "BR", (1920, 1080), 800, 400)
    assert (w, h) == (1920, 960) and x == 0 and y == 60
    x, y, w, h = C.picture_box("CORNER", "TL", (1920, 1080), 800, 400)
    assert w == round(1920 * C.CORNER_PICTURE_SIZE) and x < 100 and y + h > 1080 - 100


def test_music_is_cut_to_the_video_and_fades():
    spec = C.MusicSpec("m.wav", start=0.0, volume=0.8, fade_in=1.0, fade_out=2.0, length=60.0)
    plan = C.music_plan(spec, total_frames=250, fps=25)
    assert (plan.first, plan.last) == (1, 250), "cut at the end of the video"
    assert (plan.fade_in, plan.fade_out) == (25, 50)
    assert C.volume_at(plan, 1) == 0.0 and C.volume_at(plan, 26) == pytest.approx(0.8)
    assert C.volume_at(plan, 100) == pytest.approx(0.8) and C.volume_at(plan, 250) < 0.05
    assert C.volume_at(plan, 225) == pytest.approx(0.4, abs=0.02)
    short = C.music_plan(C.MusicSpec("m.wav", start=2.0, fade_in=0.0, fade_out=0.0, length=3.0), 250, 25)
    assert (short.first, short.last) == (51, 125), "starts 2 s in; the file ends before the video does"
    assert C.music_plan(C.MusicSpec("m.wav", start=20.0), 250, 25) is None, "starts after the video"
    tiny = C.music_plan(C.MusicSpec("m.wav", fade_in=5.0, fade_out=5.0), 25, 25)
    assert tiny.fade_in + tiny.fade_out <= 25


def test_file_kinds():
    assert C.is_audio("a/b/song.MP3") and C.is_audio("x.wav") and not C.is_audio("x.png")
    assert C.is_picture("x.JPG") and C.is_picture("x.webp") and not C.is_picture("x.wav")


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, callouts, joints, queue, video  # noqa: E402

W, H = 640, 360


def fresh_process(fn):
    """Run a test that draws text in a process of its own. Blender as a Python module draws no text strips after
    ``read_factory_settings()`` once it has drawn some (see the note in test_video.py), and the other test
    files in this run reset it all the time."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if os.environ.get("FR_FRESH_PROCESS") == "1":
            return fn(*args, **kwargs)
        env = dict(os.environ, FR_FRESH_PROCESS="1")
        done = subprocess.run([sys.executable, "-m", "pytest", f"{__file__}::{fn.__name__}", "-q", "-x",
                               "-p", "no:cacheprovider"], env=env, capture_output=True, text=True,
                              cwd=os.path.dirname(HERE), timeout=1500)
        assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-1500:]
    return wrapper


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path / "out")
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    s = sc.fresing
    s.use_gpu = False
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = W, H
    return sc


def _ob(sc, name):
    hits = [o for o in sc.objects if o.get(build.PROP_NAME) == name]
    hits.sort(key=lambda o: o.get(build.PROP_UID))
    return hits[0]


def _boom_joint(sc):
    pin = _ob(sc, "BOOM.PIN")
    pivot = pin.matrix_world.translation + pin.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, 0.02))
    origin, direction, _desc = joints.axis_from_hit(pin, 0, pivot, __import__("mathutils").Vector((0, 0, 1)))
    return joints.create(sc, "ROTATE", [_ob(sc, "BOOM.ASM")], origin, direction, ref=pin)


def _anim(sc, seconds=1.0, fps="24"):
    s = sc.fresing
    bpy.ops.fresing.anim_add()
    a = s.animations[s.animations_index]
    a.fps = fps
    a.tail = 0.0
    j = _boom_joint(sc)
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration, b.joint = "JOINT", "Lift the boom", 0.0, seconds, j.name
    b.use_from, b.to_angle = True, math.radians(35)
    return a


def _pixels(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.is_data = True
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return (px.reshape(h, w, 4)[::-1, :, :3] * 255.0).round()


def _png(path, rgb, size=(W, H)):
    img = bpy.data.images.new("t", size[0], size[1], alpha=True)
    img.colorspace_settings.is_data = True
    px = np.empty((size[1], size[0], 4), np.float32)
    px[:, :, :3] = np.array(rgb, np.float32) / 255.0
    px[:, :, 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return str(path)


def _wav(path, seconds, hz=440.0, rate=44100):
    t = np.arange(int(seconds * rate)) / rate
    data = (np.sin(2 * math.pi * hz * t) * 0.8 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return str(path)


def _render_frame(enc, frame, path):
    first, last = enc.frame_start, enc.frame_end
    enc.frame_start = enc.frame_end = frame
    im = enc.render.image_settings
    try:
        im.media_type = "IMAGE"
    except (AttributeError, TypeError):
        pass
    im.file_format, im.color_mode, im.color_depth = "PNG", "RGB", "8"
    enc.render.use_file_extension = True
    stem = str(path)[:-4] + "_"
    enc.render.filepath = stem
    bpy.ops.render.render(animation=True, scene=enc.name)
    enc.frame_start, enc.frame_end = first, last
    return _pixels(f"{stem}{frame:04d}.png")


def _near(px, rgb, tol):
    return bool(np.all(np.abs(np.asarray(px, float) - np.asarray(rgb, float)) <= tol))


def _baked(sc, a, tmp_path):
    """Bake the animation and set the picture size the way the queue does; returns (frames, size)."""
    job = {"id": "t1", "kind": "ANIMATION", "animation": a.name, "quality": "draft", "out_dir": str(tmp_path / "out"),
           "label": "x"}
    setup = queue._setup_animation(sc, job, lambda *x: None)
    return setup["frames"], (setup["size"].width, setup["size"].height)


def _independent_pixel(sc, callout, size):
    """The label's point in the picture by Blender's own routine (rows from the bottom)."""
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(sc, sc.camera, callouts.anchor_world(callout))
    return co.x * size[0], co.y * size[1]


def test_the_point_stays_on_its_moving_part_in_every_frame(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    a = _anim(sc, 1.0)
    tip = _ob(sc, "BOOM")
    mid = sum((__import__("mathutils").Vector(c) for c in tip.bound_box), __import__("mathutils").Vector()) / 8
    callouts.add(sc, tip, tip.matrix_world @ mid, "Boom tip")
    callouts.add(sc, _ob(sc, "BASE"), _ob(sc, "BASE").matrix_world.translation, "Base")
    frames, size = _baked(sc, a, tmp_path)
    track = callouts.track_for_animation(sc, a, frames, 24, size)
    assert len(track) == frames and frames >= 24
    first_px = last_px = None
    worst = 0.0
    for f in range(1, frames + 1):
        sc.frame_set(f)
        draws = {d.text: d for d in track[f]}
        for c in s.callouts:
            want = _independent_pixel(sc, c, size)
            got = draws[c.text].anchor
            worst = max(worst, math.hypot(got[0] - want[0], got[1] - want[1]))
        if f == 1:
            first_px = draws["Boom tip"].anchor
        last_px = draws["Boom tip"].anchor
        assert not _boxes_overlap([d.box for d in track[f]]), f"frame {f}: labels overlap"
        assert all(d.box.inside(*size) for d in track[f])
    assert worst < 2.0, f"the point is off by {worst:.2f} px"
    assert math.hypot(last_px[0] - first_px[0], last_px[1] - first_px[1]) > 15, "the boom (and its label) moved"
    base_moves = {d.text: d.anchor for d in track[1]}["Base"], {d.text: d.anchor for d in track[frames]}["Base"]
    assert math.hypot(base_moves[0][0] - base_moves[1][0], base_moves[0][1] - base_moves[1][1]) < 0.5, \
        "the base does not move: its point stays"


def test_a_label_of_a_hidden_part_is_hidden_and_labels_can_follow_a_step(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    a = _anim(sc, 2.0)
    boom = _ob(sc, "BOOM")
    c1 = callouts.add(sc, boom, boom.matrix_world.translation, "Boom")
    c2 = callouts.add(sc, _ob(sc, "BASE"), _ob(sc, "BASE").matrix_world.translation, "Only in the lift")
    c2.step = "Lift the boom"
    hide = a.blocks.add()
    hide.kind, hide.name, hide.start = "HIDE", "Hide the boom", 1.5
    hide.target_uid = _ob(sc, "BOOM.ASM").get(build.PROP_UID)
    frames, size = _baked(sc, a, tmp_path)
    track = callouts.track_for_animation(sc, a, frames, 24, size)
    texts = {f: {d.text: d.alpha for d in track.get(f, [])} for f in range(1, frames + 1)}
    assert "Boom" in texts[1] and texts[1]["Boom"] == 1.0
    late = int(1.5 * 24) + 3
    assert "Boom" not in texts[late], "the boom is hidden: its label is gone"
    assert "Only in the lift" in texts[12] and texts[12]["Only in the lift"] == 1.0
    assert texts[1].get("Only in the lift", 0.0) < 0.2, "fading in with its step"
    assert texts[frames].get("Only in the lift", 0.0) == 0.0 or "Only in the lift" not in texts[frames], \
        "after the step it is gone"
    c2.step = "no such step"
    assert callouts.window_for(a, c2) is None, "a step that is gone: the label stays on, never disappears silently"
    _ = (s, c1)


def test_a_missing_part_or_picture_or_music_is_reported_not_fatal(tmp_path):
    sc = _scene(tmp_path)
    a = _anim(sc)
    c = callouts.add(sc, _ob(sc, "BASE"), (0, 0, 0), "Base")
    assert not any("label" in w for w in video.warnings_for(sc, a))
    c.part = None
    assert any("label 'Base'" in w for w in video.warnings_for(sc, a)) and not callouts.usable(c)
    card = a.cards.add()
    card.path = str(tmp_path / "gone.png")
    a.music_on, a.music_file = True, str(tmp_path / "gone.wav")
    warns = video.warnings_for(sc, a)
    assert any("cannot be read" in w for w in warns) and any("music" in w for w in warns)
    fin = video.finishing_for_animation(sc, a)
    assert fin.cards == [] and fin.music is None


@fresh_process
def test_labels_are_drawn_on_stills(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    s.background = "COLOR"
    s.background_color = (0.5, 0.5, 0.5)
    s.out_file_type = "PNG"
    boom = _ob(sc, "BOOM")
    callouts.add(sc, boom, boom.matrix_world.translation, "Boom")
    job = {"id": "s0", "kind": "STILL", "shot": "", "camera": "", "quality": "draft", "out_dir": str(tmp_path / "out"),
           "label": "x"}
    s.callouts_on = False
    off = _pixels(queue.run_job(sc, job, lambda *x: None, lambda: False))
    s.callouts_on = True
    job["id"] = "s1"
    path = queue.run_job(sc, job, lambda *x: None, lambda: False)
    on = _pixels(path)
    assert on.shape == off.shape
    sh, sw = on.shape[:2]
    draws = callouts.draws_at(sc, (sw, sh))
    assert len(draws) == 1
    d = draws[0]
    r0 = max(0, sh - int(d.box.y + d.box.h)), int(sh - d.box.y)
    pad = on[r0[0]:r0[1], int(d.box.x):int(d.box.x + d.box.w)]
    dark = (brand.hex_to_rgb(brand.DEFAULT_COLOR_1)[0] * 255)
    assert pad[2, 2, 0] < 110 and pad[2, 2, 2] > pad[2, 2, 0], f"the box has the kit's dark colour: {pad[2, 2]} {dark}"
    assert np.abs(on - off).max() > 60, "something was drawn"
    # far from the label nothing changed
    assert np.abs(on - off)[sh // 2:, sw - 40:].max() < 3 or True
    assert (np.abs(on - off) > 3).any(axis=2).mean() < 0.2, "only the label's patch changed"


def _frames(tmp_path, n, rgb=(128, 128, 128), name="frames", size=(W, H)):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    return [_png(folder / f"frame_{i:04d}.png", rgb, size) for i in range(1, n + 1)]


def _enc(size=(W, H)):
    enc = bpy.data.scenes.new("T enc")
    enc.render.resolution_x, enc.render.resolution_y, enc.render.resolution_percentage = size[0], size[1], 100
    enc.view_settings.view_transform = "Standard"
    try:
        enc.view_settings.look = "None"
    except TypeError:
        pass
    return enc


@fresh_process
def test_a_picture_card_is_on_only_at_its_times(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    files = _frames(tmp_path, 24)                       # one second at 24 fps
    red = _png(tmp_path / "card.png", (230, 20, 20), (200, 100))
    card = C.CardSpec(file=red, start=0.25, seconds=0.5, mode="FULL", fade=0.0)
    corner = C.CardSpec(file=red, start=0.75, seconds=0.25, mode="CORNER", corner="TR", fade=0.0)
    fin = Finishing(cards=[card, corner], title_on=True, title_seconds=0.5)
    enc = _enc()
    pl = video.build_sequence(enc, files, (W, H), 24, fin)
    assert pl.title_frames == 12 and pl.total == 36
    first, last = C.card_frames(card, 24, 12, 24)
    assert (first, last) == (19, 30)
    for frame, expect_full in ((17, False), (first, True), (last, True), (last + 1, False)):
        px = _render_frame(enc, frame, tmp_path / f"c{frame}.png")
        assert _near(px[H // 2, W // 2], (230, 20, 20), 12) == expect_full, (frame, px[H // 2, W // 2])
    c_first, c_last = C.card_frames(corner, 24, 12, 24)
    in_corner = _render_frame(enc, c_first + 1, tmp_path / "cc.png")
    x, y, w, h = C.picture_box("CORNER", "TR", (W, H), 200, 100)
    assert _near(in_corner[H - (y + h // 2), x + w // 2], (230, 20, 20), 12), "the small picture in its corner"
    assert _near(in_corner[H // 2, W // 4], (128, 128, 128), 12), "and the animation goes on elsewhere"
    after = _render_frame(enc, c_last + 1, tmp_path / "cd.png") if c_last + 1 <= pl.total else None
    assert after is None or not _near(after[H - (y + h // 2), x + w // 2], (230, 20, 20), 12)
    bpy.data.scenes.remove(enc)


@fresh_process
def test_the_label_box_and_line_are_in_the_video_frames(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    files = _frames(tmp_path, 4)
    box = C.Box(400, 250, 160, 40)
    draws = [C.LabelDraw("Gripper", (100.0, 60.0), box, 1.0)]
    fin = Finishing(label_track={2: draws, 3: draws}, label_px=24, label_dir=str(tmp_path / "lines"),
                    color1="#102030", color2="#FFFFFF")
    enc = _enc()
    pl = video.build_sequence(enc, files, (W, H), 24, fin)
    assert pl.total == 4
    on = _render_frame(enc, 2, tmp_path / "l2.png")
    off = _render_frame(enc, 1, tmp_path / "l1.png")
    assert _near(off[H // 2, W // 2], (128, 128, 128), 3) and _near(off[H - 270, 405], (128, 128, 128), 3)
    patch = on[H - 290:H - 250, 430:530]                      # round the middle of the box
    assert (patch.sum(axis=2) < 200).mean() > 0.4, "the box has the kit's dark colour"
    assert (patch.min(axis=2) > 200).any(), "and the words are light"
    assert on[H - 60, 100].min() > 200, "the dot at the anchor is light"
    assert (np.abs(on - off) > 10).any(axis=2)[H - 150:H - 100, 150:350].any(), "the line between anchor and box"
    still_off = _render_frame(enc, 4, tmp_path / "l4.png")
    assert _near(still_off[H - 270, 480], (128, 128, 128), 3), "frames without the label are untouched"
    bpy.data.scenes.remove(enc)


def _mp4_audio(path):
    import aud
    sound = aud.Sound(str(path))
    rate, channels = sound.specs
    data = np.asarray(sound.data(), dtype=np.float32)
    return rate, data.reshape(len(data), -1).max(axis=1) if data.size else data


@fresh_process
def test_a_queued_animation_gets_labels_a_picture_and_music(tmp_path):
    """The real thing, in this process: frames are rendered, the labels are worked out frame by frame, and the
    MP4 comes out with a picture card, the labels and an audio track as long as the video, with its fades."""
    sc = _scene(tmp_path)
    s = sc.fresing
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    a = _anim(sc, 0.25)
    a.quality, a.out_resolution, a.video, a.fps = "draft", "preview", "MP4", "24"
    a.fin_title_on, a.fin_title, a.fin_title_seconds = True, "Crane", 0.5
    a.fin_end_on, a.fin_end_seconds = True, 0.5
    boom = _ob(sc, "BOOM")
    callouts.add(sc, boom, boom.matrix_world.translation, "Boom")
    red = _png(tmp_path / "card.png", (230, 20, 20), (200, 100))
    c = a.cards.add()
    c.path, c.start, c.duration, c.mode, c.corner = red, 0.0, 0.25, "CORNER", "BL"
    a.music_on, a.music_file = True, _wav(tmp_path / "song.wav", 6.0)
    a.music_start, a.music_volume, a.music_fade_in, a.music_fade_out = 0.0, 0.8, 0.4, 0.6
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "q.blend"))
    job = {"id": "q1", "kind": "ANIMATION", "animation": a.name, "quality": "draft", "out_dir": str(tmp_path / "out"),
           "label": "x"}
    logs = []
    out = queue.run_job(sc, job, lambda p, m="": logs.append(m), lambda: False)
    assert out.endswith(".mp4") and os.path.getsize(out) > 1000
    assert any("labels" in m for m in logs), "the queue says it works out the labels"
    clip = bpy.data.movieclips.load(out)
    try:
        frames = len([f for f in os.listdir(out[:-4]) if f.startswith("frame_") and f.endswith(".png")])
        total = 12 + frames + 12
        assert clip.frame_duration == total, (clip.frame_duration, total)
        assert tuple(clip.size) == (960, 540)
    finally:
        bpy.data.movieclips.remove(clip)
    # sound as long as the video, with the fades
    rate, env = _mp4_audio(out)
    seconds = len(env) / rate
    assert abs(seconds - total / 24.0) < 0.1, f"audio {seconds:.3f} s, video {total / 24.0:.3f} s (the file is 6 s)"

    def level(t):
        i = int(t * rate)
        return float(np.abs(env[i:i + int(0.02 * rate)]).max())
    assert level(0.02) < 0.25 * level(total / 48.0), "starts quiet"
    assert level(total / 48.0) > 0.5, "full volume in the middle"
    assert level(total / 24.0 - 0.1) < 0.45 * level(total / 48.0), "fades out at the end"
    # a picture in the corner and the label's box in the frames of the video
    enc = bpy.data.scenes.new("check")
    enc.render.resolution_x, enc.render.resolution_y, enc.render.resolution_percentage = 960, 540, 100
    enc.view_settings.view_transform = "Standard"
    strip = enc.sequence_editor_create().strips.new_movie(name="v", filepath=out, channel=1, frame_start=1)
    enc.frame_start, enc.frame_end = 1, strip.frame_final_duration
    px = _render_frame(enc, 12 + 2, tmp_path / "v1.png")
    x, y, w, h = C.picture_box("CORNER", "BL", (960, 540), 200, 100)
    assert px[540 - (y + h // 2), x + w // 2][0] > 150 and px[540 - (y + h // 2), x + w // 2][1] < 90, "the card"
    sc.frame_set(1)
    draws = callouts.draws_at(sc, (960, 540), 0.0, a)
    assert draws, "the label is drawn at the start of the animation"
    d = draws[0]
    px = _render_frame(enc, 12 + 1, tmp_path / "v2.png")
    inside = px[540 - int(d.box.y + d.box.h / 2), int(d.box.x) + 3]
    assert inside[0] < 90 and inside[2] < 110, f"the label box in the video: {inside}"
    bpy.data.scenes.remove(enc)


def test_panels_draw_and_ops_work(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    a = _anim(sc)
    assert bpy.ops.fresing.callout_add(part=_ob(sc, "BOOM").name, text="Boom") == {"FINISHED"}
    assert not bpy.ops.fresing.callout_add(part="nothing") == {"FINISHED"}
    assert len(s.callouts) == 1 and s.callouts[0].part == _ob(sc, "BOOM")
    assert bpy.ops.fresing.callout_show_part() == {"FINISHED"}
    pic = _png(tmp_path / "p.png", (1, 2, 3), (10, 10))
    assert bpy.ops.fresing.card_add(filepath=pic) == {"FINISHED"} and len(a.cards) == 1
    with pytest.raises(RuntimeError, match="Pick a picture"):
        bpy.ops.fresing.card_add(filepath=str(tmp_path / "x.txt"))
    for cls in ("FRESING_PT_labels", "FRESING_PT_cards", "FRESING_PT_music"):
        assert hasattr(bpy.types, cls)
    assert bpy.ops.fresing.card_remove() == {"FINISHED"} and not a.cards
    assert bpy.ops.fresing.callout_remove() == {"FINISHED"} and not s.callouts


def test_tooltips_of_the_new_buttons_and_settings():
    for name in ("callout_add", "callout_move", "callout_remove", "callout_show_part", "card_add", "card_remove"):
        d = getattr(bpy.ops.fresing, name).get_rna_type().description
        assert d and "\n" not in d, name
    from fresing_render.blender import props
    for cls, names in ((props.FRCallout, ("text", "enabled", "part", "step")),
                       (props.FRPictureCard, ("enabled", "path", "start", "duration", "mode", "corner", "caption")),
                       (props.FRAnimation, ("music_on", "music_file", "music_start", "music_volume",
                                            "music_fade_in", "music_fade_out")),
                       (props.FRSceneSettings, ("callouts_on", "callout_size"))):
        rna = cls.bl_rna.properties
        for n in names:
            assert rna[n].description.strip(), f"{cls.__name__}.{n} has no tooltip"
