"""Labels pointing at parts, picture cards and music (task 0025).

Numbers (card time line, music pieces, label boxes, the drawn line) are checked without Blender; the rest inside
Blender: the clicked point is projected for every frame of an animation, a hidden part drops its label, pictures
and labels are rendered through the sequencer and the pixels checked, an MP4 gets an audio track of the right
length, stills get their labels.

NOTE: this file is named so that it runs after tests/test_video.py. Blender as a Python module keeps font data
across read_factory_settings(): text drawn here before test_video's first (watermark) test made that test draw
no text.
"""

import math
import os
import wave

import numpy as np
import pytest

from fresing_render.core import brand
from fresing_render.core import callouts as C
from fresing_render.core import mp4
from fresing_render.core.brand import Finishing

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------


def test_a_full_card_stops_the_animation_and_moves_everything_after_it():
    card = C.PictureCard("p.png", C.FULL, seconds=2.0, at=1.0)
    fin = Finishing(title_on=True, title_seconds=1.0, end_on=True, end_seconds=1.0, captions_on=True, cards=[card])
    steps = [("First", 0.0, 1.0), ("Second", 1.0, 2.0)]
    pl = brand.plan(fin, body_frames=50, fps=25, steps=steps)           # 2 s of animation
    assert pl.inserts == [(25, 50)] and pl.inserted == 50
    assert pl.total == 25 + 50 + 50 + 25
    assert pl.video_frame(25) == 50 and pl.video_frame(26) == 25 + 26 + 50
    placed = pl.placed[0]
    assert (placed.first, placed.last) == (51, 100), "right after frame 25 of the animation"
    assert pl.end_start == pl.total - 25 + 1
    first, second = pl.captions
    assert first.start == 26 and first.end <= 50, "the first caption is over before the card"
    assert second.start == pl.video_frame(26), "the second one starts after the card"


def test_cards_at_one_moment_follow_each_other_and_a_corner_card_does_not_stop_anything():
    cards = [C.PictureCard("a.png", C.FULL, seconds=1.0, at=0.0), C.PictureCard("b.png", C.FULL, seconds=1.0, at=0.0),
             C.PictureCard("c.png", C.CORNER, seconds=1.0, at=1.0)]
    pl = brand.plan(Finishing(cards=cards), body_frames=75, fps=25)
    assert pl.inserts == [(0, 25), (0, 25)] and pl.total == 75 + 50
    full = [p for p in pl.placed if p.card.mode == C.FULL]
    assert [(p.first, p.last) for p in full] == [(1, 25), (26, 50)]
    corner = [p for p in pl.placed if p.card.mode == C.CORNER][0]
    assert (corner.first, corner.last) == (pl.video_frame(26), pl.video_frame(50))
    late = brand.plan(Finishing(cards=[C.PictureCard("a.png", C.FULL, seconds=1.0, at=99.0)]), 75, 25)
    assert late.inserts == [(75, 25)], "a card after the end sits at the end of the animation"


def test_music_is_cut_to_the_video_and_fades_in_and_out_smoothly():
    assert C.music_span(250, 25, 0.0, 1000) == (1, 250), "long music is cut at the end of the video"
    assert C.music_span(250, 25, 2.0, 100) == (51, 150), "short music plays once, from its start"
    assert C.music_span(250, 25, 20.0, 100) is None, "music that starts after the video ends is dropped"
    g = C.gain_curve(48000 * 4, 48000, 0.8, 1.0, 2.0)
    assert len(g) == 48000 * 4 and g.max() == pytest.approx(0.8)
    assert g[0] == 0.0 and g[24000] == pytest.approx(0.4, abs=0.01), "half way up the fade in"
    assert g[48000 * 2 - 1] == pytest.approx(0.8) and g[48000 * 2 + 5] == pytest.approx(0.8, abs=0.01)
    assert g[48000 * 3] == pytest.approx(0.4, abs=0.01) and g[-1] < 0.001, "down to nothing at the very end"
    assert np.all(np.abs(np.diff(g)) < 0.001), "no jumps: no clicks"
    both = C.gain_curve(1000, 1000, 1.0, 5.0, 5.0)
    assert both.max() <= 1.0 and both[-1] < 0.01 and both[0] == 0.0 and both[499] > 0.99, "fades longer than the music are squeezed in"


def test_boxes_do_not_overlap_stay_in_the_picture_and_keep_off_the_machine():
    W, H = 1280, 720
    outline = (400, 150, 880, 600)
    anchors = [(450, 500), (460, 480), (470, 460), (800, 300), (810, 320), (420, 200)]
    sizes = [C.box_size("Gripper", 30), C.box_size("Cylinder Ø63", 30), C.box_size("Max. 25 t", 30)] * 2
    boxes = C.place_boxes(sizes, anchors, (W, H), outline)
    for i, b in enumerate(boxes):
        assert b[0] >= 0 and b[1] >= 0 and b[0] + b[2] <= W and b[1] + b[3] <= H
        assert b[0] + b[2] <= outline[0] or b[0] >= outline[2], f"box {i} is beside the machine, not on it"
        for j in range(i):
            assert not C._overlap(b, boxes[j]), (i, j)
    left = [b for b, a in zip(boxes, anchors) if a[0] < 640]
    assert all(b[0] < outline[0] for b in left), "a point on the left half gets a box on the left"
    kept = C.place_boxes(sizes[:1], anchors[:1], (W, H), outline, manual=[(100, 100)])
    assert kept[0][:2] == (100, 100)


def test_the_line_runs_from_the_box_to_the_point_and_leaves_the_rest_clear():
    buf = np.zeros((100, 200, 4), np.float32)
    C.draw_line(buf, (20, 50), (180, 50), 4, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), alpha=1.0, dot=5)
    assert buf[50, 100, 3] > 0.99 and np.allclose(buf[50, 100, :3], 1.0, atol=0.02), "white in the middle"
    assert 0.5 < buf[52, 100, 3] and buf[52, 100, :3].max() < 0.9, "dark edge around it"
    assert buf[50, 180, 3] > 0.99 and buf[50, 183, 3] > 0.5, "a dot at the part"
    assert buf[10, 100, 3] == 0 and buf[90, 30, 3] == 0
    faint = np.zeros((100, 200, 4), np.float32)
    C.draw_line(faint, (20, 50), (180, 50), 4, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), alpha=0.25)
    assert faint[50, 100, 3] == pytest.approx(0.25, abs=0.02)
    assert C.runs([1, 2, 3, 7, 8, 10]) == [(1, 3), (7, 8), (10, 10)]


def test_line_end_touches_the_side_of_the_box_that_faces_the_point():
    box = (100, 100, 200, 60)
    assert C.line_end(box, (600, 130))[0] == 300 and C.line_end(box, (0, 130))[0] == 100
    assert C.line_end(box, (200, 600))[1] == 160 and C.line_end(box, (200, 0))[1] == 100


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, callouts, queue, render, video  # noqa: E402

W, H = 640, 360
GREY = 128


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _png(path, rgb, size=(W, H), alpha=255):
    img = bpy.data.images.new("t", size[0], size[1], alpha=True)
    img.colorspace_settings.is_data = True
    px = np.empty((size[1], size[0], 4), np.float32)
    px[:, :, :3] = np.array(rgb, np.float32) / 255.0
    px[:, :, 3] = alpha / 255.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return str(path)


def _frames(tmp_path, n, name="frames"):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    return [_png(folder / f"frame_{i:04d}.png", (GREY, GREY, GREY)) for i in range(1, n + 1)]


def _enc():
    enc = bpy.data.scenes.new("T enc")
    enc.render.resolution_x, enc.render.resolution_y, enc.render.resolution_percentage = W, H, 100
    enc.view_settings.view_transform = "Standard"
    try:
        enc.view_settings.look = "None"
    except TypeError:
        pass
    return enc


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


def _pixels(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.is_data = True
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return (px.reshape(h, w, 4)[::-1, :, :3] * 255.0).round()      # row 0 = top


def _near(px, rgb, tol):
    return bool(np.all(np.abs(np.asarray(px, float) - np.asarray(rgb, float)) <= tol))


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


def _anim(sc):
    s = sc.fresing
    if not s.animations:
        bpy.ops.fresing.anim_add()
    return s.animations[s.animations_index]


def _parts(sc):
    from fresing_render.blender import build
    return [o for o in sc.objects if o.type == "MESH" and o.get(build.PROP_KIND) == "part"]


def _project_by_hand(sc, p):
    """The picture position of a world point, worked out with the camera matrices (not Blender's helper)."""
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    r = sc.render
    w, h = r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100
    proj = cam.calc_matrix_camera(dg, x=w, y=h)
    v = proj @ cam.matrix_world.inverted() @ p.to_4d()
    return (v.x / v.w * 0.5 + 0.5) * w, (v.y / v.w * 0.5 + 0.5) * h


def test_the_label_line_stays_on_its_moving_part_in_every_frame(tmp_path):
    from mathutils import Vector
    sc = _scene(tmp_path)
    part = _parts(sc)[0]
    local = tuple(part.bound_box[0])
    item = callouts.add(sc, part, local, "Gripper")
    assert item.text == "Gripper" and sc.fresing.callouts_index == 0
    part.location.x += 0.0
    start = part.location.copy()
    for f, dx in ((1, 0.0), (12, 0.4)):
        part.location = start + Vector((dx, 0.0, 0.0))
        part.keyframe_insert("location", frame=f)
    seen = []
    for f in range(1, 13):
        sc.frame_set(f)
        got = callouts.anchor_at(sc, item, (W, H))
        want_world = part.matrix_world @ Vector(local)
        want = _project_by_hand(sc, want_world)
        if got is None:                      # the model may be partly outside the picture: skip those
            continue
        assert abs(got[0] - want[0]) <= 2 and abs(got[1] - want[1]) <= 2, (f, got, want)
        seen.append(got)
    assert len(seen) >= 6
    assert max(abs(a[0] - seen[0][0]) + abs(a[1] - seen[0][1]) for a in seen) > 3, "the point moves with the part"


def test_labels_of_hidden_parts_and_of_other_steps_are_hidden(tmp_path):
    sc = _scene(tmp_path)
    a = _anim(sc)
    a.fps = "24"
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Lift", 0.0, 1.0
    b2 = a.blocks.add()
    b2.kind, b2.name, b2.start, b2.duration = "CAMERA", "Lower", 1.0, 1.0
    p1, p2 = _parts(sc)[:2]
    callouts.add(sc, p1, tuple(p1.bound_box[0]), "A")
    two = callouts.add(sc, p2, tuple(p2.bound_box[0]), "B")
    two.step = "Lower"
    p1.hide_render = False
    p1.keyframe_insert("hide_render", frame=1)
    p1.hide_render = True
    p1.keyframe_insert("hide_render", frame=30)
    for fc in video._fcurves(p1.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    plans, lines = callouts.plan_video(sc, a, 48, 24, (W, H), str(tmp_path / "lines"))
    by = {pl.text: pl for pl in plans}
    assert "A" in by and "B" in by
    assert max(by["A"].anchors) < 30 and max(by["A"].anchors) >= 20, "no line once its part is hidden"
    assert (by["B"].first, by["B"].last) == (25, 48) and min(by["B"].anchors) >= 25, "only while 'Lower' runs"
    assert set(lines) == {f for pl in plans for f in pl.anchors}
    assert all(os.path.isfile(p) for p in lines.values())
    # a part hidden through its parent counts as hidden
    child = _parts(sc)[2]
    assert not callouts.is_hidden(child)
    root = child
    while root.parent is not None:
        root = root.parent
    root.hide_render = True
    assert callouts.is_hidden(child)


def test_labels_do_not_overlap_in_a_planned_animation(tmp_path):
    sc = _scene(tmp_path)
    a = _anim(sc)
    for i, part in enumerate(_parts(sc)[:5]):
        callouts.add(sc, part, tuple(part.bound_box[i % 8]), f"Label number {i + 1}")
    plans, _lines = callouts.plan_video(sc, a, 6, 24, (W, H), str(tmp_path / "lines"))
    assert len(plans) >= 2
    for i, p in enumerate(plans):
        x, y, w, h = p.box
        assert x >= 0 and y >= 0 and x + w <= W and y + h <= H
        for q in plans[:i]:
            assert not C._overlap(p.box, q.box), (p.text, q.text)


def _fin(**kw):
    base = dict(color1="#204060", color2="#FFFFFF")
    base.update(kw)
    return Finishing(**base)


def test_picture_cards_come_at_their_time_and_not_before_or_after(tmp_path):
    fps = 5
    files = _frames(tmp_path, 15)
    full = _png(tmp_path / "full.png", (230, 20, 20), (320, 180))
    small = _png(tmp_path / "small.png", (20, 200, 40), (160, 90))
    cards = [C.PictureCard(full, C.FULL, seconds=1.0, at=1.0, caption="Photo of the machine"),
             C.PictureCard(small, C.CORNER, corner="TL", seconds=1.0, at=1.5, size=0.25)]
    enc = _enc()
    pl = video.build_sequence(enc, files, (W, H), fps, _fin(cards=cards), [])
    assert pl.total == 15 + 5 and enc.frame_end == 20
    full_p = [p for p in pl.placed if p.card.mode == C.FULL][0]
    assert (full_p.first, full_p.last) == (6, 10)
    mid = _render_frame(enc, 8, tmp_path / "mid.png")
    assert _near(mid[H // 2, W // 2], (230, 20, 20), 8), "the full picture fills the middle"
    assert mid[10:H - 10, 10:W - 10].std() > 5
    before = _render_frame(enc, 5, tmp_path / "before.png")
    after = _render_frame(enc, 11, tmp_path / "after.png")
    assert _near(before[H // 2, W // 2], (GREY,) * 3, 3) and _near(after[H // 2, W // 2], (GREY,) * 3, 3)
    corner_p = [p for p in pl.placed if p.card.mode == C.CORNER][0]
    during = _render_frame(enc, (corner_p.first + corner_p.last) // 2, tmp_path / "corner.png")
    x, y, w, h = brand.logo_box("TL", W, H, 160, 90, 0.25)
    assert _near(during[H - (y + h // 2), x + w // 2], (20, 200, 40), 10)
    assert _near(during[H - 20, W - 20], (GREY,) * 3, 3), "only in its corner"
    outside = _render_frame(enc, corner_p.last + 1, tmp_path / "gone.png")
    assert _near(outside[H - (y + h // 2), x + w // 2], (GREY,) * 3, 3)
    bpy.data.scenes.remove(enc)


def _lines_for(tmp_path, anchors, box, fade=0):
    plan = C.LabelPlan("Gripper", 1, len(anchors), {i + 1: a for i, a in enumerate(anchors)}, box)
    s = bpy.context.scene.fresing
    lines = callouts.write_lines([plan], (W, H), str(tmp_path / "lines"), fade, s)
    return plan, lines


def test_labels_and_lines_are_rendered_and_follow_the_point(tmp_path):
    files = _frames(tmp_path, 8)
    box = (40, 250, 150, 50)
    anchors = [(300 + 20 * i, 120) for i in range(8)]
    plan, lines = _lines_for(tmp_path, anchors, box)
    assert sorted(lines) == list(range(1, 9))
    enc = _enc()
    fin = _fin(labels=[plan], label_lines=lines, label_font_px=24)
    pl = video.build_sequence(enc, files, (W, H), 5, fin, [])
    assert pl.total == 8
    for f in (2, 6):
        pic = _render_frame(enc, f, tmp_path / f"l{f}.png")
        ax, ay = anchors[f - 1]
        assert pic[H - ay, ax][0] > 200, "the white dot of the line is at the part"
        x, y, w, h = box
        inside = pic[H - (y + h):H - y, x:x + w]
        assert inside.min() < GREY - 40, "the dark label box"
        far = pic[H - 20, W - 20]
        assert _near(far, (GREY,) * 3, 3)
    a2 = _render_frame(enc, 2, tmp_path / "a2.png")
    a6 = _render_frame(enc, 6, tmp_path / "a6.png")
    assert not (a2[H - 120, 300 + 20 * 5] > 200).all() or True
    assert a6[H - 120, 300 + 20 * 5][0] > 200 and not a2[H - 120, 300 + 20 * 5][0] > 200, \
        "the dot has moved between frames 2 and 6"
    bpy.data.scenes.remove(enc)


def test_label_text_is_drawn_in_the_box():
    """In a Python of its own: after resets, Blender as a module draws no text any more (see the note above)."""
    import subprocess
    import sys
    code = """
import numpy as np
import bpy
from fresing_render.blender import video
from fresing_render.core import callouts as C
from fresing_render.core.brand import Finishing
W, H = 640, 360
img = bpy.data.images.new("t", W, H, alpha=True)
img.colorspace_settings.is_data = True
px = np.full((H, W, 4), 0.5, np.float32)
px[..., 3] = 1.0
img.pixels.foreach_set(px.ravel())
img.filepath_raw = "FRAME"
img.file_format = "PNG"
img.save()
enc = bpy.data.scenes.new("e")
enc.render.resolution_x, enc.render.resolution_y, enc.render.resolution_percentage = W, H, 100
enc.view_settings.view_transform = "Standard"
box = (40, 250, 150, 50)
fin = Finishing(color1="#204060", color2="#FFFFFF", label_font_px=24,
                labels=[C.LabelPlan("Gripper", 1, 1, {1: (300, 120)}, box)])
video.build_sequence(enc, ["FRAME"], (W, H), 1, fin, [])
enc.frame_start = enc.frame_end = 1
im = enc.render.image_settings
im.media_type = "IMAGE"
im.file_format, im.color_mode, im.color_depth = "PNG", "RGB", "8"
enc.render.use_file_extension = False
enc.render.filepath = "OUT"
bpy.ops.render.render(write_still=True, scene=enc.name)
out = bpy.data.images.load("OUT")
out.colorspace_settings.is_data = True
a = np.empty(W * H * 4, np.float32)
out.pixels.foreach_get(a)
a = a.reshape(H, W, 4)[::-1, :, :3] * 255
inside = a[H - 300:H - 250, 40:190]
print("RESULT", float(inside.min()), float(inside.max()))
"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        code = code.replace("FRAME", os.path.join(tmp, "frame.png").replace("\\", "/")).replace(
            "OUT", os.path.join(tmp, "out.png").replace("\\", "/"))
        env = dict(os.environ, PYTHONPATH=os.path.dirname(HERE))
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=300)
    line = [ln for ln in res.stdout.splitlines() if ln.startswith("RESULT")]
    assert line, res.stdout[-800:] + res.stderr[-800:]
    low, high = (float(v) for v in line[0].split()[1:])
    assert low < GREY - 40, "the dark label box"
    assert high > 200, "the white letters in it"


def test_a_label_is_cut_where_a_full_card_stops_the_animation(tmp_path):
    files = _frames(tmp_path, 10)
    plan, lines = _lines_for(tmp_path, [(300, 150)] * 10, (40, 250, 150, 50))
    full = _png(tmp_path / "full.png", (230, 20, 20), (320, 180))
    fin = _fin(labels=[plan], label_lines=lines, label_font_px=24,
               cards=[C.PictureCard(full, C.FULL, seconds=1.0, at=1.0)])
    enc = _enc()
    pl = video.build_sequence(enc, files, (W, H), 5, fin, [])
    assert pl.total == 15
    card_frame = _render_frame(enc, 8, tmp_path / "card.png")
    assert _near(card_frame[H - 150, 300], (230, 20, 20), 8), "no line or box on top of the card"
    assert card_frame[H - 275, 100].max() < 255 and _near(card_frame[H - 275, 60], (230, 20, 20), 12)
    bpy.data.scenes.remove(enc)


def _tone(path, seconds=6, rate=22050, level=12000):
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(rate * seconds)
        t = np.arange(n)
        mono = (level * np.sin(2 * math.pi * 440 * t / rate)).astype("<i2")
        w.writeframes(np.repeat(mono, 2).tobytes())
    return str(path)


def test_music_goes_under_the_video_cut_to_its_length_with_fades(tmp_path):
    fps = 10
    files = _frames(tmp_path, 30, "mframes")                       # 3 s of video
    tone = _tone(tmp_path / "tone.wav", seconds=8)                  # longer than the video
    fin = _fin(music_file=tone, music_volume=0.8, music_start=0.0, music_fade_in=0.5, music_fade_out=1.0,
               title_on=True, title_seconds=1.0)
    out = queue.encode_mp4(str(tmp_path / "mframes"), str(tmp_path / "m.mp4"), W, H, fps, finishing=fin)
    tracks = mp4.track_seconds(out)
    assert "vide" in tracks and "soun" in tracks, tracks
    assert tracks["vide"] == pytest.approx(4.0, abs=0.15)
    assert tracks["soun"] == pytest.approx(4.0, abs=0.15), "the 8 s of music are cut to the 4 s video"
    # no music: no audio track
    plain = queue.encode_mp4(str(tmp_path / "mframes"), str(tmp_path / "p.mp4"), W, H, fps, finishing=_fin())
    assert "soun" not in mp4.track_seconds(plain)
    assert len(files) == 30


def test_music_volume_follows_the_fades(tmp_path):
    fps = 10
    tone = _tone(tmp_path / "tone.wav", seconds=8, rate=48000)
    enc = _enc()
    enc.render.fps = fps
    fin = _fin(music_file=tone, music_volume=0.6, music_fade_in=1.0, music_fade_out=1.0)
    pl = video.build_sequence(enc, _frames(tmp_path, 40, "vframes"), (W, H), fps, fin, [])
    assert pl.total == 40
    sounds = [st for st in enc.sequence_editor.strips if st.type == "SOUND"]
    assert len(sounds) == 1 and sounds[0].left_handle == 1 and sounds[0].right_handle == 41
    wav = str(tmp_path / "mix.wav")
    with bpy.context.temp_override(scene=enc):
        bpy.ops.sound.mixdown(filepath=wav, container="WAV", codec="PCM")
    w = wave.open(wav)
    rate, ch = w.getframerate(), w.getnchannels()
    data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch).astype(float)
    assert w.getnframes() / rate == pytest.approx(4.0, abs=0.15)
    full = 0.6 * 12000 / 32768

    def level(t):
        seg = np.abs(data[int(t * rate):int(t * rate) + 2400, 0])
        return seg.max() / 32768.0

    assert level(2.0) == pytest.approx(full, rel=0.08)
    assert level(0.5) == pytest.approx(full * 0.5, rel=0.15), "half way up the fade in"
    assert level(3.5) == pytest.approx(full * 0.5, rel=0.15), "half way down the fade out"
    assert level(0.02) < 0.1 * full and level(3.97) < 0.1 * full
    video.cleanup()
    bpy.data.scenes.remove(enc)


def test_still_with_labels_has_a_box_and_a_line(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    s.out_file_type = "PNG"
    part = _parts(sc)[0]
    item = callouts.add(sc, part, tuple(part.bound_box[0]), "Gripper")
    sc.frame_set(1)
    a = callouts.anchor_at(sc, item, callouts.render_size(sc))
    assert a is not None, "the corner of the first part is in the picture"
    item.on_still = False
    plain = _pixels(render.render_still(sc, s, "draft", filepath=str(tmp_path / "plain.png"))["path"])
    item.on_still = True
    labelled = _pixels(render.render_still(sc, s, "draft", filepath=str(tmp_path / "lab.png"))["path"])
    assert not os.path.exists(str(tmp_path / "lab.png.lines"))
    diff = np.abs(labelled - plain).max(axis=2)
    assert diff.max() > 60, "something was drawn"
    sh, sw = labelled.shape[:2]
    ratio = sh / H
    ax, ay = a[0] * ratio, a[1] * ratio
    near = diff[max(0, int(sh - ay) - 6):int(sh - ay) + 6, max(0, int(ax) - 6):int(ax) + 6]
    assert near.max() > 60, "the dot sits on the part"
    item.on_still = False
    again = _pixels(render.render_still(sc, s, "draft", filepath=str(tmp_path / "off.png"))["path"])
    assert np.abs(again - plain).max() < 3, "a label that is not for images stays off"


def test_missing_files_are_reported_not_fatal(tmp_path):
    sc = _scene(tmp_path)
    a = _anim(sc)
    c = a.cards.add()
    c.file = str(tmp_path / "gone.png")
    a.music_file = str(tmp_path / "gone.wav")
    fin = video.finishing_for_animation(sc, a)
    assert fin.cards == [] and fin.music_file == ""
    warns = video.warnings_for(sc, a)
    assert any("picture card" in w for w in warns) and any("music" in w for w in warns)
    c.file = _png(tmp_path / "ok.png", (1, 2, 3), (10, 10))
    a.music_file = _tone(tmp_path / "ok.wav", seconds=1)
    fin = video.finishing_for_animation(sc, a)
    assert len(fin.cards) == 1 and fin.music_file.endswith("ok.wav") and fin.active
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Lift", 0.0, 2.0
    c.after_step = "Lift"
    assert video.finishing_for_animation(sc, a).cards[0].at == pytest.approx(2.0)


def test_panels_draw_and_buttons_work(tmp_path):
    from fresing_render.blender import ui_callouts
    sc = _scene(tmp_path)
    a = _anim(sc)
    assert bpy.ops.fresing.card_add() == {"FINISHED"} and len(a.cards) == 1
    assert bpy.ops.fresing.card_remove() == {"FINISHED"} and len(a.cards) == 0
    part = _parts(sc)[0]
    callouts.add(sc, part, (0, 0, 0))
    assert bpy.ops.fresing.callout_show() == {"FINISHED"}
    assert bpy.ops.fresing.callout_remove() == {"FINISHED"} and len(sc.fresing.callouts) == 0
    assert not bpy.ops.fresing.callout_remove.poll()
    for cls in (ui_callouts.FRESING_PT_labels, ui_callouts.FRESING_PT_pictures):
        assert cls.poll(bpy.context)


def test_tooltips_of_the_new_buttons_and_settings():
    from fresing_render.blender import ops_callouts
    sprops = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties
    for k in ("callout_size",):
        assert len(sprops[k].description) > 15, k
    for group, keys in (("callouts", ("text", "obj", "local", "step", "on_still", "on_video", "manual", "box_x", "box_y")),
                        ("animations", ("music_file", "music_start", "music_volume", "music_fade_in",
                                        "music_fade_out"))):
        props = sprops[group].fixed_type.bl_rna.properties
        for k in keys:
            assert len(props[k].description) > 30, (group, k)
    cprops = sprops["animations"].fixed_type.bl_rna.properties["cards"].fixed_type.bl_rna.properties
    for k in ("file", "mode", "corner", "size", "seconds", "after_step", "at", "caption"):
        assert len(cprops[k].description) > 15, k
    for cls in ops_callouts.CLASSES:
        assert len((cls.__doc__ or "").strip()) > 30, cls.__name__
        text = getattr(bpy.ops.fresing, cls.bl_idname.split(".")[1]).get_rna_type().description
        assert "\n" not in text and len(text) > 30
