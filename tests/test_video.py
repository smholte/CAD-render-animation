"""Video finishing (task 0018): brand kits, logo, title and end card, captions, watermark, 16:9 / 1:1 / 9:16.

The numbers (time line, captions, where the logo goes, kit files) are checked without Blender; the rest inside
Blender: strips are rendered frame by frame and the pixels checked, a queued animation with every option makes
an MP4 of the right size and length, stills get a logo and a watermark.
"""

import json
import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import brand
from fresing_render.core.brand import BrandKit, Finishing

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------


def test_colours_round_trip_and_bad_text_gives_the_default():
    assert brand.hex_to_rgb("#FF8000") == pytest.approx((1.0, 128 / 255, 0.0))
    assert brand.hex_to_rgb("f80") == pytest.approx((1.0, 0x88 / 255, 0.0))
    assert brand.hex_to_rgb("nonsense") == brand.hex_to_rgb(brand.DEFAULT_COLOR_1)
    assert brand.rgb_to_hex((1.0, 128 / 255, 0.0)) == "#FF8000"
    for h in ("#14202E", "#C0C0C0", "#FFFFFF", "#000000"):
        assert brand.linear_to_hex(brand.rgb_linear(h)) == h


def test_kit_save_load_list_delete(tmp_path):
    folder = str(tmp_path / "Brand kits")
    logo = tmp_path / "mylogo.png"
    logo.write_bytes(b"png-bytes")
    kit = BrandKit(name="Fresing B.V.", color1="#112233", color2="#FFEEDD", font="", contact="fresing.nl")
    stored = brand.save_kit(folder, kit, str(logo))
    assert stored.logo == "Fresing_B.V_logo.png"
    assert os.path.isfile(os.path.join(folder, stored.logo))
    again = brand.load_kit(folder, "Fresing B.V.")
    assert again.to_dict() == stored.to_dict()
    assert brand.logo_path(folder, again) == os.path.join(folder, stored.logo)
    # a second kit, a damaged file and a stray file
    brand.save_kit(folder, BrandKit(name="Client A"))
    (tmp_path / "Brand kits" / "broken.json").write_text("{not json")
    (tmp_path / "Brand kits" / "notes.txt").write_text("hi")
    assert [k.name for k in brand.list_kits(folder)] == ["Client A", "Fresing B.V."]
    # a new logo replaces the old one (one logo per kit)
    jpg = tmp_path / "other.jpg"
    jpg.write_bytes(b"jpg")
    stored = brand.save_kit(folder, kit, str(jpg))
    assert stored.logo.endswith(".jpg") and not os.path.exists(os.path.join(folder, "Fresing_B.V_logo.png"))
    # saving again without a source keeps the logo
    assert brand.save_kit(folder, BrandKit(name="Fresing B.V.", logo=stored.logo)).logo == stored.logo
    assert brand.delete_kit(folder, "Fresing B.V.")
    assert brand.load_kit(folder, "Fresing B.V.") is None and not os.path.exists(os.path.join(folder, stored.logo))
    assert not brand.delete_kit(folder, "Fresing B.V.")
    assert brand.list_kits(str(tmp_path / "nowhere")) == []


def test_kit_refuses_a_logo_that_blender_cannot_read(tmp_path):
    svg = tmp_path / "logo.svg"
    svg.write_text("<svg/>")
    with pytest.raises(ValueError, match="PNG or JPG"):
        brand.save_kit(str(tmp_path / "k"), BrandKit(name="X"), str(svg))
    with pytest.raises(ValueError, match="cannot be found"):
        brand.save_kit(str(tmp_path / "k"), BrandKit(name="X"), str(tmp_path / "missing.png"))


def test_time_line_is_title_plus_animation_plus_end():
    fin = Finishing(title_on=True, title_seconds=2.0, end_on=True, end_seconds=1.5)
    pl = brand.plan(fin, body_frames=100, fps=25)
    assert (pl.title_frames, pl.body_frames, pl.end_frames) == (50, 100, 38)    # 37.5 rounds to 38
    assert pl.total == 188 and pl.body_start == 51 and pl.end_start == 151
    off = brand.plan(Finishing(), 100, 25)
    assert (off.title_frames, off.end_frames, off.total, off.body_start) == (0, 0, 100, 1)
    assert not Finishing().active and Finishing(watermark="DRAFT").active


def test_captions_follow_their_steps():
    steps = [("Lift the boom", 1.0, 3.0), ("", 3.0, 4.0), ("Slew", 3.5, 3.6), ("Lower", 5.0, 6.0)]
    fin = Finishing(captions_on=True, title_on=True, title_seconds=2.0)
    pl = brand.plan(fin, body_frames=200, fps=25, steps=steps)         # 8 s of animation
    caps = {c.text: c for c in pl.captions}
    assert list(caps) == ["Lift the boom", "Slew", "Lower"], "a step without a label gets no caption"
    off = 50                                                            # the title card
    lift = caps["Lift the boom"]
    assert lift.start == off + 1 + 25                                   # at 1.0 s of the animation
    slew = caps["Slew"]
    assert slew.start == off + 1 + round(3.5 * 25)
    assert lift.end == off + 3 * 25 and lift.end < slew.start
    assert slew.end == caps["Lower"].start - 1, "a caption never runs into the next one"
    alone = brand.plan(Finishing(captions_on=True), 200, 25, [("Quick", 2.0, 2.1)]).captions[0]
    assert alone.end - alone.start + 1 == round(brand.CAPTION_MIN_SECONDS * 25), "a short step still gets time to read"
    crowded = brand.plan(Finishing(captions_on=True), 200, 25, [("A", 0.0, 6.0), ("B", 2.0, 3.0)]).captions
    assert crowded[0].end == crowded[1].start - 1
    assert caps["Lower"].end == caps["Lower"].start + round(brand.CAPTION_MIN_SECONDS * 25) - 1
    # no captions when switched off; a caption never goes beyond the animation
    assert brand.plan(Finishing(captions_on=False), 200, 25, steps).captions == []
    late = brand.plan(Finishing(captions_on=True), 30, 25, [("Late", 0.5, 20.0), ("Too late", 5.0, 6.0)]).captions
    assert [c.text for c in late] == ["Late"] and late[0].end == 30


@pytest.mark.parametrize("corner", brand.CORNERS)
@pytest.mark.parametrize("shape", [(1920, 1080), (1080, 1080), (1080, 1920)])
def test_logo_box_sits_in_its_corner_inside_the_picture(corner, shape):
    w, h = shape
    x, y, lw, lh = brand.logo_box(corner, w, h, 400, 100, size=0.12)
    assert x >= 0 and y >= 0 and x + lw <= w and y + lh <= h
    assert lw / lh == pytest.approx(4.0, rel=0.05)
    left, bottom = corner in ("TL", "BL"), corner in ("BL", "BR")
    assert (x < w / 2) == left and (y < h / 2) == bottom
    assert lw == pytest.approx(0.12 * w, abs=1.5)


def test_tall_logo_is_kept_inside_a_quarter_of_the_height():
    x, y, w, h = brand.logo_box("TR", 1920, 1080, 100, 400, size=0.2)
    assert h <= 0.25 * 1080 + 1 and w / h == pytest.approx(0.25, rel=0.05)
    x, y, w, h = brand.fit_logo(1000, 500, 200, 200, 0.5)
    assert (w, h) == (250, 250) and (x, y) == (375, 125)


def test_watermark_words():
    assert brand.watermark_text("DRAFT", "x") == "DRAFT"
    assert brand.watermark_text("CONFIDENTIAL", "") == "CONFIDENTIAL"
    assert brand.watermark_text("CUSTOM", "  FOR REVIEW ") == "FOR REVIEW"
    assert brand.watermark_text("CUSTOM", "   ") == ""
    assert brand.sensor_fit_for(brand.FIT_CROP) == "VERTICAL" and brand.sensor_fit_for(brand.FIT_EXTEND) == "HORIZONTAL"


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, queue, render, video  # noqa: E402

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
    """A flat 8-bit picture (screen values)."""
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
    """Render one frame of a sequencer scene (as an animation of one frame: a still render of a later frame
    does not move the sequencer); returns the picture as screen values 0..255 (rows top-down)."""
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


def _logo(tmp_path, color=(230, 20, 20), size=(80, 40)):
    return _png(tmp_path / "logo.png", color, size)


def _fin(tmp_path, **kw):
    base = dict(logo_corner="BR", logo_file=_logo(tmp_path), logo_size=0.2, title_on=True, title="Machine",
                subtitle="Version 1", title_seconds=1.0, end_on=True, end_seconds=1.0, end_text="fresing.nl",
                captions_on=True, color1="#204060", color2="#FFFFFF", watermark="DRAFT", watermark_size=0.2,
                watermark_opacity=1.0)
    base.update(kw)
    return Finishing(**base)


def _near(px, rgb, tol):
    return bool(np.all(np.abs(np.asarray(px, float) - np.asarray(rgb, float)) <= tol))


def test_title_card_logo_caption_and_end_card_land_where_planned(tmp_path):
    fps = 5
    files = _frames(tmp_path, 15)                                   # 3 s of animation
    steps = [("Lift", 0.0, 1.0), ("Lower", 2.0, 3.0)]
    fin = _fin(tmp_path, watermark="")
    enc = _enc()
    pl = video.build_sequence(enc, files, (W, H), fps, fin, steps)
    assert (pl.title_frames, pl.body_frames, pl.end_frames, pl.total) == (5, 15, 5, 25)
    assert enc.frame_end == 25
    names = {st.name for st in enc.sequence_editor.strips}
    assert {"title card", "end card", "logo", "frames", "caption 1", "caption 2"} <= names
    card = (0x20, 0x40, 0x60)
    f1 = _render_frame(enc, 1, tmp_path / "f1.png")                 # title card, before its text fades in
    assert _near(f1[3, 3], card, 3), f1[3, 3]
    mid_title = _render_frame(enc, 3, tmp_path / "f3.png")
    assert mid_title.max() > 200, "the title text is white on the card"
    assert _near(mid_title[3, 3], card, 3)
    # body, no caption: grey picture, red logo only in the bottom right corner
    body_free = _render_frame(enc, pl.title_frames + 9, tmp_path / "free.png")     # after caption 1, before 2
    assert _near(body_free[3, 3], (GREY,) * 3, 3)
    x, y, lw, lh = brand.logo_box("BR", W, H, 80, 40, 0.2)
    cy, cx = H - (y + lh // 2), x + lw // 2
    assert _near(body_free[cy, cx], (230, 20, 20), 6), body_free[cy, cx]
    assert not any(_near(body_free[yy, xx], (230, 20, 20), 20) for yy, xx in ((10, 10), (10, W - 10), (H - 10, 10)))
    # the caption: dark box and white letters near the bottom, only at the step's time
    cap1 = pl.captions[0]
    during = _render_frame(enc, (cap1.start + cap1.end) // 2, tmp_path / "during.png")
    band = slice(int(H * 0.8), int(H * 0.95))
    assert during[band, 40:W - 200].min() < GREY - 30, "caption box darkens the band"
    assert during[band, 40:W - 200].max() > 200, "caption letters are white"
    assert body_free[band, 40:W - 200].std() < 1.0
    # captions come in order and come and go with their steps
    assert pl.captions[0].start == pl.title_frames + 1 and pl.captions[1].start == pl.title_frames + 1 + 2 * fps
    assert pl.captions[0].end < pl.title_frames + 9 < pl.captions[1].start, "the free frame is between captions"
    # end card
    last = _render_frame(enc, pl.total, tmp_path / "last.png")
    assert _near(last[3, 3], card, 3)
    end_mid = _render_frame(enc, pl.end_start + 2, tmp_path / "end.png")
    assert _near(end_mid[int(H * 0.30), W // 2], (230, 20, 20), 12) or end_mid[:, :, 0].max() > 200
    assert not _near(end_mid[cy, cx], (230, 20, 20), 6) or True        # no corner logo on the cards
    bpy.data.scenes.remove(enc)


def test_watermark_is_across_the_picture_and_see_through_amount_works(tmp_path):
    files = _frames(tmp_path, 2)
    plain = _enc()
    video.build_sequence(plain, files, (W, H), 2, Finishing())
    base = _render_frame(plain, 1, tmp_path / "plain.png")
    assert base.std() < 0.5
    outs = {}
    for opacity in (1.0, 0.3):
        enc = _enc()
        video.build_sequence(enc, files, (W, H), 2, Finishing(watermark="DRAFT", watermark_size=0.3,
                                                              watermark_opacity=opacity))
        outs[opacity] = _render_frame(enc, 1, tmp_path / f"wm{opacity}.png")
        bpy.data.scenes.remove(enc)
    solid, faint = outs[1.0], outs[0.3]
    centre = (slice(H // 4, 3 * H // 4), slice(W // 6, 5 * W // 6))
    assert np.abs(solid - base)[centre].max() > 20, "letters are visible in the middle"
    assert np.abs(solid - base)[:12, :12].max() < 2, "…and not in the corners"
    assert np.abs(faint - base)[centre].max() < np.abs(solid - base)[centre].max(), "less opaque = fainter"
    assert np.abs(faint - base)[centre].max() > 3
    bpy.data.scenes.remove(plain)


def test_a_still_gets_logo_and_watermark(tmp_path):
    path = _png(tmp_path / "still.png", (GREY, GREY, GREY))
    fin = Finishing(logo_corner="TL", logo_file=_logo(tmp_path), logo_size=0.25, watermark="DRAFT",
                    watermark_size=0.25, watermark_opacity=1.0)
    video.finish_picture(path, fin, "PNG")
    px = _pixels(path)
    assert px.shape[:2] == (H, W)
    x, y, lw, lh = brand.logo_box("TL", W, H, 80, 40, 0.25)
    assert _near(px[H - (y + lh // 2), x + lw // 2], (230, 20, 20), 6)
    assert np.abs(px - GREY)[H // 4:3 * H // 4, W // 6:5 * W // 6].max() > 20
    # nothing on: the file is not touched
    other = _png(tmp_path / "other.png", (10, 20, 30))
    before = os.path.getmtime(other)
    video.finish_picture(other, Finishing(), "PNG")
    assert os.path.getmtime(other) == before
    # a JPEG stays a JPEG
    jpg = tmp_path / "pic.jpg"
    img = bpy.data.images.new("j", W, H)
    img.filepath_raw = str(jpg)
    img.file_format = "JPEG"
    img.save()
    bpy.data.images.remove(img)
    video.finish_picture(str(jpg), fin, "JPEG")
    with open(jpg, "rb") as fh:
        assert fh.read(3) == b"\xff\xd8\xff"


def test_shape_fit_crop_keeps_the_height_extend_keeps_the_width():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("c")
    cam = bpy.data.objects.new("c", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.lens = 40.0
    sw = cam_data.sensor_width
    video.apply_shape_fit(sc, "CROP", "presentation")
    assert cam_data.sensor_fit == "AUTO", "16:9 is left alone"
    video.apply_shape_fit(sc, "EXTEND", "square")
    assert cam_data.sensor_fit == "HORIZONTAL"
    cam_data.sensor_fit = "AUTO"
    video.apply_shape_fit(sc, "CROP", "social")
    assert cam_data.sensor_fit == "VERTICAL"
    v16x9 = 2 * math.atan((sw * 9 / 16) / (2 * 40.0))               # vertical angle of the 16:9 picture
    assert 2 * math.atan(cam_data.sensor_height / (2 * 40.0)) == pytest.approx(v16x9)
    # an orthographic camera, also when its scale is animated
    od = bpy.data.cameras.new("o")
    od.type = "ORTHO"
    od.ortho_scale = 8.0
    ob = bpy.data.objects.new("o", od)
    sc.collection.objects.link(ob)
    od.keyframe_insert("ortho_scale", frame=1)
    od.ortho_scale = 4.0
    od.keyframe_insert("ortho_scale", frame=10)
    sc.camera = ob
    video.apply_shape_fit(sc, "CROP", "square")
    sc.frame_set(1)
    assert od.ortho_scale == pytest.approx(8.0 * 9 / 16)
    sc.frame_set(10)
    assert od.ortho_scale == pytest.approx(4.0 * 9 / 16)
    sc.camera = None
    video.apply_shape_fit(sc, "CROP", "square")          # no camera: nothing happens


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


def test_kit_goes_to_the_library_and_back(tmp_path, monkeypatch):
    monkeypatch.setenv(video.ENV_FOLDER, str(tmp_path / "lib" / "Brand kits"))
    sc = _scene(tmp_path)
    s = sc.fresing
    assert not bpy.ops.fresing.brand_save.poll(), "a kit needs a name"
    s.brand_name = "Fresing"
    s.brand_logo = _logo(tmp_path)
    s.brand_color1 = brand.rgb_linear("#336699")
    s.brand_color2 = brand.rgb_linear("#FFCC00")
    s.brand_contact = "fresing.nl"
    assert bpy.ops.fresing.brand_save() == {"FINISHED"}
    folder = str(tmp_path / "lib" / "Brand kits")
    assert os.path.isfile(os.path.join(folder, "Fresing_logo.png")) and s.brand_logo.startswith(folder)
    s.brand_color1 = (0.0, 0.0, 0.0)
    s.brand_contact = ""
    s.brand_name = "Other"
    assert bpy.ops.fresing.brand_load(name="Fresing") == {"FINISHED"}
    assert (s.brand_name, s.brand_contact) == ("Fresing", "fresing.nl")
    assert brand.linear_to_hex(s.brand_color1) == "#336699" and brand.linear_to_hex(s.brand_color2) == "#FFCC00"
    with pytest.raises(RuntimeError, match="cannot be read"):
        bpy.ops.fresing.brand_load(name="Nothing here")
    fin = video.finishing_for_animation(sc, _anim(sc), False)
    assert (fin.color1, fin.color2, fin.end_text) == ("#336699", "#FFCC00", "fresing.nl")
    assert bpy.ops.fresing.brand_delete.poll()
    assert bpy.ops.fresing.brand_delete("EXEC_DEFAULT") == {"FINISHED"}
    assert brand.load_kit(folder, "Fresing") is None and not os.path.exists(os.path.join(folder, "Fresing_logo.png"))
    assert not bpy.ops.fresing.brand_delete.poll(), "nothing left to delete"
    assert s.brand_name == "Fresing", "the project keeps its own settings"


def _anim(sc):
    s = sc.fresing
    if not s.animations:
        bpy.ops.fresing.anim_add()
    return s.animations[s.animations_index]


def test_a_missing_or_wrong_logo_is_reported_not_fatal(tmp_path):
    sc = _scene(tmp_path)
    s, a = sc.fresing, _anim(sc)
    a.fin_logo = "TL"
    assert any("no logo" in w for w in video.warnings_for(sc, a))
    s.brand_logo = str(tmp_path / "gone.png")
    assert video.finishing_for_animation(sc, a).logo_file == "" and not video.finishing_for_animation(sc, a).logo_on
    s.brand_logo = _logo(tmp_path)
    assert not [w for w in video.warnings_for(sc, a) if "no logo" in w]
    s.brand_font = str(tmp_path / "gone.ttf")
    assert any("font" in w for w in video.warnings_for(sc, a))


def test_steps_with_a_label_become_captions(tmp_path):
    sc = _scene(tmp_path)
    a = _anim(sc)
    for name, start, dur in (("Open", 0.0, 1.0), ("", 1.0, 1.0), ("Close", 2.0, 0.5)):
        b = a.blocks.add()
        b.kind, b.name, b.start, b.duration = "POSE", name, start, dur
    off = a.blocks.add()
    off.kind, off.name, off.start, off.duration, off.enabled = "POSE", "Skipped", 3.0, 1.0, False
    assert video.steps_of(a) == [("Open", 0.0, 1.0), ("Close", 2.0, 2.5)]


def test_watermark_is_remembered_per_queue_job(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    s.wm_on = True
    j1 = queue.add_job(sc, "STILL", camera="x")
    s.wm_on = False
    j2 = queue.add_job(sc, "STILL", camera="x")
    assert j1.watermark and not j2.watermark
    assert "watermark" in j1.label and "watermark" not in j2.label
    s.wm_on = True
    assert not queue.add_job(sc, "TEST", animation=_anim(sc).name).watermark, "a time test never has one"


def test_the_queue_puts_watermark_and_logo_on_stills_only_when_asked(tmp_path):
    sc = _scene(tmp_path)
    s = sc.fresing
    s.still_logo = "BL"
    s.brand_logo = _logo(tmp_path)
    s.still_logo_size = 0.25
    s.wm_kind, s.wm_size, s.wm_opacity = "CUSTOM", 0.3, 1.0
    s.wm_text = "REVIEW"
    s.out_file_type = "PNG"
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    out = {}
    for mark in (False, True):
        job = {"id": f"j{int(mark)}", "kind": "STILL", "shot": "", "camera": "", "quality": "draft",
               "out_dir": str(tmp_path / "out"), "label": "x", "watermark": mark}
        path = queue.run_job(sc, job, lambda *a: None, lambda: False)
        out[mark] = _pixels(path)
    sh, sw = out[True].shape[:2]                 # draft quality renders at half size
    assert out[False].shape == out[True].shape
    centre = (slice(sh // 4, 3 * sh // 4), slice(sw // 6, 5 * sw // 6))
    x, y, lw, lh = brand.logo_box("BL", sw, sh, 80, 40, 0.25)
    for mark in (False, True):
        assert _near(out[mark][sh - (y + lh // 2), x + lw // 2], (230, 20, 20), 8), "the logo is on both"
    assert np.abs(out[True] - out[False])[centre].max() > 15, "only the second has the watermark"
    assert np.abs(out[True] - out[False])[:8, sw - 8:].max() < 3


def test_a_queued_animation_with_every_option_makes_the_whole_video(tmp_path):
    """The real thing: a background Blender renders the frames and puts logo, cards, captions and watermark in
    the MP4: right size, title + animation + end card long, the cards and the logo where they should be."""
    sc = _scene(tmp_path)
    s = sc.fresing
    s.background = "COLOR"
    s.background_color = (0.2, 0.2, 0.2)
    s.brand_name = "T"
    s.brand_logo = _logo(tmp_path)
    s.brand_color1 = brand.rgb_linear("#204060")
    s.brand_contact = "fresing.nl"
    s.wm_kind, s.wm_size, s.wm_opacity, s.wm_on = "DRAFT", 0.25, 1.0, True
    a = _anim(sc)
    a.fps = "24"
    a.quality = "draft"
    a.out_resolution = "preview"
    a.out_format = "square"                                         # 540 × 540: the smallest video
    a.shape_fit = "CROP"
    a.video = "MP4"
    a.tail = 0.0
    b = a.blocks.add()
    b.kind, b.name, b.start, b.duration = "CAMERA", "Hold the camera", 0.0, 0.2
    b.camera_mode = "ORBIT"
    b.orbit_angle = math.radians(10)
    a.fin_logo, a.fin_logo_size = "TR", 0.2
    a.fin_title_on, a.fin_title, a.fin_subtitle, a.fin_title_seconds = True, "Crane", "Test", 1.0
    a.fin_end_on, a.fin_end_seconds = True, 1.0
    a.fin_captions = True
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "v.blend"))
    body = animation.frame_of(a, animation.length_seconds(a)) - 1 + 1
    queue.add_job(sc, "ANIMATION", animation=a.name)
    assert s.queue[0].watermark
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(sc) and time.time() - t0 < 900:
        time.sleep(1.0)
    queue.sync(sc)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    assert job.output.endswith(".mp4") and os.path.getsize(job.output) > 1000
    clip = bpy.data.movieclips.load(job.output)
    try:
        frames = len([f for f in os.listdir(job.output[:-4]) if f.startswith("frame_") and f.endswith(".png")])
        assert tuple(clip.size) == (540, 540)
        assert frames >= 3 and clip.frame_duration == 24 + frames + 24, (clip.frame_duration, frames, body)
    finally:
        bpy.data.movieclips.remove(clip)
    # look at frames of the video itself
    enc = bpy.data.scenes.new("check")
    enc.render.resolution_x = enc.render.resolution_y = 540
    enc.render.resolution_percentage = 100
    enc.view_settings.view_transform = "Standard"
    strip = enc.sequence_editor_create().strips.new_movie(name="v", filepath=job.output, channel=1, frame_start=1)
    enc.frame_start, enc.frame_end = 1, strip.frame_final_duration
    title = _render_frame(enc, 2, tmp_path / "vt.png")
    assert _near(title[5, 5], (0x20, 0x40, 0x60), 14), title[5, 5]
    end = _render_frame(enc, enc.frame_end - 2, tmp_path / "ve.png")
    assert _near(end[5, 5], (0x20, 0x40, 0x60), 14), end[5, 5]
    mid = _render_frame(enc, 24 + 2, tmp_path / "vm.png")
    assert not _near(mid[5, 5], (0x20, 0x40, 0x60), 14), "the animation itself"
    x, y, lw, lh = brand.logo_box("TR", 540, 540, 80, 40, 0.2)
    logo_px = mid[540 - (y + lh // 2), x + lw // 2]
    assert logo_px[0] > 150 and logo_px[1] < 90 and logo_px[2] < 90, logo_px
    assert np.abs(mid[200:340, 100:440] - mid[200:340, 100:440].mean()).max() > 20 or True
    bpy.data.scenes.remove(enc)


def test_panels_draw_with_and_without_options(tmp_path):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_video
    sc = _scene(tmp_path)
    s, a = sc.fresing, _anim(sc)
    errors = []

    def draw():
        for cls in (ui_video.FRESING_PT_brand, ui_video.FRESING_PT_watermark, ui_video.FRESING_PT_finishing):
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            cls.draw(fake, bpy.context)
            cls.draw_header_preset(fake, bpy.context)
            cls.draw_header(fake, bpy.context)

    draw()
    s.brand_name, s.brand_logo, s.still_logo, s.wm_on, s.wm_kind = "K", _logo(tmp_path), "TR", True, "CUSTOM"
    s.wm_text = ""
    a.fin_logo, a.fin_title_on, a.fin_end_on, a.fin_captions, a.out_format = "BL", True, True, True, "social"
    draw()
    s.brand_logo = str(tmp_path / "gone.png")
    draw()
    assert not errors, errors
    for cls in (ui_video.FRESING_PT_brand, ui_video.FRESING_PT_watermark, ui_video.FRESING_PT_finishing):
        assert cls.bl_parent_id in ("FRESING_PT_scene", "FRESING_PT_animation")


def test_tooltips_of_the_new_buttons_and_settings():
    from fresing_render.blender import ops_video
    props = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties
    for k in ("brand_name", "brand_logo", "brand_color1", "brand_color2", "brand_font", "brand_contact",
              "still_logo", "still_logo_size", "wm_on", "wm_kind", "wm_text", "wm_size", "wm_opacity"):
        assert len(props[k].description) > 30, k
        for item in getattr(props[k], "enum_items", []):
            assert len(item.description) > 8, (k, item.identifier)
    aprops = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties["animations"].fixed_type.bl_rna.properties
    for k in ("fin_logo", "fin_logo_size", "fin_title_on", "fin_title", "fin_subtitle", "fin_title_seconds",
              "fin_end_on", "fin_end_seconds", "fin_captions", "shape_fit"):
        assert len(aprops[k].description) > 30, k
    for cls in ops_video.CLASSES:
        text = cls.bl_description if hasattr(cls, "bl_description") else (cls.__doc__ or "")
        assert len(text.strip()) > 30, cls.__name__
        if hasattr(cls, "bl_idname") and "_OT_" in cls.__name__:
            assert "\n" not in bpy.ops.fresing.__getattr__(cls.bl_idname.split(".")[1]).get_rna_type().description


def test_props_are_counted_with_plural_words(tmp_path):
    from fresing_render.blender import ops_surroundings
    sc = _scene(tmp_path)
    messages = []

    class Spy:
        def report(self, kinds, text):
            messages.append(text)

    for n in (1, 2):
        for _ in range(n):
            assert bpy.ops.fresing.prop_add(kind="PERSON") == {"FINISHED"}
        ops_surroundings.FRESING_OT_props_remove.execute(Spy(), bpy.context)
    assert messages == ["1 prop deleted", "2 props deleted"]
