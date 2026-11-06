"""Video finishing (task 0018): logo in a corner, title card, end card, captions, watermark.

Everything is put on top of the rendered pictures with Blender's Video Sequencer in a throw-away scene:
the finished video needs no Python to play. The numbers (time line, captions, where the logo goes) come
from ``core/brand.py``; here they are turned into strips.
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile

import bpy

from ..core import brand
from ..core import callouts as C
from ..core.brand import Finishing

# channels, bottom to top
CH_UNDER, CH_FRAMES, CH_CARD, CH_LOGO, CH_CAPTION = 1, 2, 3, 5, 7
CH_LABEL_LINE, CH_LABEL_TEXT = 10, 11          # labels (task 0025): lines, then one channel per label (11..)
CH_PICTURE = 100                               # picture cards: three channels each (background, picture, caption)
CH_MUSIC = 124
CH_WATERMARK = 127                             # on top of everything (Blender has 128 channels)

WATERMARK_ANGLE = math.radians(25)


# ---------------------------------------------------------------------------
# reading the settings
# ---------------------------------------------------------------------------


def watermark_words(s) -> str:
    return brand.watermark_text(s.wm_kind, s.wm_text)


def _logo_path(s) -> str:
    p = bpy.path.abspath(s.brand_logo) if s.brand_logo else ""
    return p if p and os.path.isfile(p) and p.lower().endswith(brand.LOGO_TYPES) else ""


def _kit_fields(s) -> dict:
    return {"color1": brand.linear_to_hex(s.brand_color1), "color2": brand.linear_to_hex(s.brand_color2),
            "font": bpy.path.abspath(s.brand_font) if s.brand_font else "", "end_text": s.brand_contact}


def _cards_of(anim) -> list:
    out = []
    for c in anim.cards:
        path = bpy.path.abspath(c.path) if c.path else ""
        if c.enabled and path and os.path.isfile(path) and C.is_picture(path):
            out.append(C.CardSpec(file=path, start=c.start, seconds=c.duration, mode=c.mode, corner=c.corner,
                                  caption=c.caption.strip()))
    return out


def music_path(anim) -> str:
    p = bpy.path.abspath(anim.music_file) if anim.music_file else ""
    return p if p and os.path.isfile(p) and C.is_audio(p) else ""


def _music_of(anim):
    if not anim.music_on or not music_path(anim):
        return None
    return C.MusicSpec(file=music_path(anim), start=anim.music_start, volume=anim.music_volume,
                       fade_in=anim.music_fade_in, fade_out=anim.music_fade_out)


def finishing_for_animation(scene, anim, watermark: bool = False) -> Finishing:
    s = scene.fresing
    logo = _logo_path(s)
    return Finishing(cards=_cards_of(anim), music=_music_of(anim),

        logo_corner=anim.fin_logo, logo_file=logo, logo_size=anim.fin_logo_size,
        title_on=anim.fin_title_on, title=anim.fin_title, subtitle=anim.fin_subtitle,
        title_seconds=anim.fin_title_seconds, end_on=anim.fin_end_on, end_seconds=anim.fin_end_seconds,
        captions_on=anim.fin_captions, watermark=watermark_words(s) if watermark else "",
        watermark_size=s.wm_size, watermark_opacity=s.wm_opacity, **_kit_fields(s))


def finishing_for_still(scene, watermark: bool = False) -> Finishing:
    """The finishing of a still, with the labels as the camera sees them now."""
    s = scene.fresing
    from . import callouts
    size = callouts.picture_size(scene)
    kit = _kit_fields(s)
    draws = callouts.draws_at(scene, size, None, None, kit["font"]) if s.callouts_on else []
    return Finishing(label_track={1: draws} if draws else {}, label_px=C.font_px(size[1], s.callout_size),
                     logo_corner=s.still_logo, logo_file=_logo_path(s), logo_size=s.still_logo_size,
                     watermark=watermark_words(s) if watermark else "", watermark_size=s.wm_size,
                     watermark_opacity=s.wm_opacity, **_kit_fields(s))


def steps_of(anim) -> list[tuple[str, float, float]]:
    """(label, start, end) in seconds of the steps that have a label typed in: those become captions."""
    from . import animation
    return [(b.name.strip(), b.start, animation.block_end(b)) for b in anim.blocks
            if b.enabled and b.name.strip()]


def warnings_for(scene, anim=None) -> list[str]:
    """Things that are switched on but cannot work (shown in the queue log)."""
    s = scene.fresing
    out = []
    corner = anim.fin_logo if anim is not None else s.still_logo
    needs_logo = corner in brand.CORNERS or (anim is not None and anim.fin_end_on)
    if needs_logo and not _logo_path(s) and (corner in brand.CORNERS):
        out.append("A logo corner is on, but the brand kit has no logo (PNG or JPG): no logo in the picture")
    if s.brand_font and not os.path.isfile(bpy.path.abspath(s.brand_font)):
        out.append("The brand font file cannot be found: Blender's own font is used")
    if anim is not None:
        for c in anim.cards:
            if c.enabled and c.path and not _cards_of_one(c):
                out.append(f"Picture '{card_name(c)}' cannot be read (PNG, JPG, TIF, BMP or WebP): left out")
        if anim.music_on and not music_path(anim):
            out.append("The music file cannot be found or is not a sound file (WAV, MP3, OGG, FLAC, M4A): no music")
        if anim.music_on and anim.video != "MP4":
            out.append("Music only goes into MP4 videos, not into PNG frames")
    for c in s.callouts:
        if c.enabled and c.part is None:
            out.append(f"The part of the label '{c.text}' is gone: label left out")
    return out


def card_name(c) -> str:
    return c.name.strip() or (os.path.basename(c.path) if c.path else "picture")


def _cards_of_one(c) -> bool:
    path = bpy.path.abspath(c.path) if c.path else ""
    return bool(path and os.path.isfile(path) and C.is_picture(path))


# ---------------------------------------------------------------------------
# strips
# ---------------------------------------------------------------------------


def _font(path: str):
    if not path or not os.path.isfile(path):
        return None
    try:
        return bpy.data.fonts.load(path, check_existing=True)
    except RuntimeError:
        return None


def _image_size(path: str) -> tuple[int, int]:
    img = bpy.data.images.load(path, check_existing=False)
    try:
        return int(img.size[0]), int(img.size[1])
    except Exception:
        return 1, 1
    finally:
        bpy.data.images.remove(img)


FADE_STEPS = 3


def fade_segments(first: int, last: int, fade_frames: int, alpha: float = 1.0,
                  steps: int = FADE_STEPS) -> list[tuple[int, int, float]]:
    """(first frame, last frame, opacity) pieces that fade something in at ``first`` and out at ``last``.

    Blender does not evaluate animated strip properties when it renders without a window, so a fade is made
    of a few strips of their own, each with a fixed opacity: in (rising), the middle, out (falling).
    The pieces cover first..last without gaps or overlaps."""
    total = last - first + 1
    n = max(0, min(fade_frames, total // 2))
    if n == 0:
        return [(first, last, alpha)]
    k = max(1, min(steps, n))
    out = []
    for i in range(k):
        a, b = first + round(i * n / k), first + round((i + 1) * n / k) - 1
        if b >= a:
            out.append((a, b, alpha * (i + 1) / (k + 1)))
    if last - n >= first + n:
        out.append((first + n, last - n, alpha))
    for i in range(k):
        a, b = last - n + 1 + round(i * n / k), last - n + round((i + 1) * n / k)
        if b >= a:
            out.append((a, b, alpha * (k - i) / (k + 1)))
    return out


def _faded(make, first: int, last: int, fade_frames: int, alpha: float = 1.0) -> list:
    """``make(frames, index)`` builds one strip for the frames it is given; this fades the whole thing."""
    strips = []
    for i, (a, b, opacity) in enumerate(fade_segments(first, last, fade_frames, alpha)):
        st = make((a, b), i)
        st.blend_alpha = opacity
        strips.append(st)
    return strips


def _fcurves(action):
    try:
        return list(action.fcurves)
    except AttributeError:           # Blender 5: layered actions
        out = []
        for layer in action.layers:
            for st in layer.strips:
                for bag in st.channelbags:
                    out.extend(bag.fcurves)
        return out


def _text(strips, name: str, text: str, frames: tuple[int, int], channel: int, size_px: int, color,
          location, font=None, wrap: float = 0.0, shadow: bool = False):
    first, last = frames
    st = strips.new_effect(name=name, type="TEXT", channel=channel, frame_start=first, length=last - first + 1)
    st.text = text
    st.font_size = size_px
    st.color = (*color[:3], 1.0)
    st.location = location
    st.anchor_x, st.anchor_y = "CENTER", "CENTER"
    st.alignment_x = "CENTER"
    st.use_shadow = shadow
    if wrap:
        st.wrap_width = wrap
    if font is not None:
        st.font = font
    return st


def _image(strips, name: str, path: str, frames: tuple[int, int], channel: int, box, canvas):
    """A picture of its own size scaled into ``box`` (x, y from the bottom-left, w, h) of the canvas."""
    first, last = frames
    pw, ph = _image_size(path)
    st = strips.new_image(name=name, filepath=path, channel=channel, frame_start=first, fit_method="ORIGINAL")
    st.duration = last - first + 1
    st.blend_type = "ALPHA_OVER"
    x, y, w, h = box
    st.transform.scale_x = w / pw
    st.transform.scale_y = h / ph
    st.transform.offset_x = x + w / 2 - canvas[0] / 2
    st.transform.offset_y = y + h / 2 - canvas[1] / 2
    return st, (pw, ph)


def _card(strips, tag: str, frames: tuple[int, int], fin: Finishing, size, fps: int, font, lines, logo_box=None):
    """A full-picture card: background colour, a logo (end card), and lines of text
    [(text, size factor of the height, y 0..1 from the bottom)]."""
    width, height = size
    first, last = frames
    bg = strips.new_effect(name=f"{tag} card", type="COLOR", channel=CH_CARD, frame_start=first,
                           length=last - first + 1)
    bg.color = brand.hex_to_rgb(fin.color1)
    fade = brand.seconds_to_frames(brand.CARD_FADE_SECONDS, fps)
    fg = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2)
    if logo_box and fin.logo_file:
        _faded(lambda fr, k: _image(strips, f"{tag} logo {k}", fin.logo_file, fr, CH_CARD + 1, logo_box, size)[0],
               first, last, fade)
    for i, (text, factor, y) in enumerate(lines):
        if not text:
            continue
        _faded(lambda fr, k, i=i, text=text, factor=factor, y=y: _text(
            strips, f"{tag} text {i + 1}.{k}", text, fr, CH_CARD + 2 + i, brand.card_font_size(height, factor), fg,
            (0.5, y), font=font, wrap=0.85), first, last, fade)


# ---------------------------------------------------------------------------
# labels, picture cards, music (task 0025)
# ---------------------------------------------------------------------------


def _save_rgba(path: str, arr) -> None:
    """Write a (height, width, 4) float picture (row 0 = bottom, screen values, straight alpha) as PNG."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new("fr_lines", w, h, alpha=True)
    try:
        img.colorspace_settings.is_data = True            # keep the numbers as they are
        img.alpha_mode = "STRAIGHT"
        img.pixels.foreach_set(arr.astype("float32").ravel())
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def _label_runs(track: dict) -> list[tuple[int, int, tuple]]:
    """(first, last, key) of stretches of frames where the labels look exactly the same: one strip each."""
    runs: list[tuple[int, int, tuple]] = []
    for f in sorted(track):
        key = tuple(d.key() for d in track[f] if d.alpha > 0.001)
        if not key:
            continue
        if runs and runs[-1][2] == key and runs[-1][1] == f - 1:
            runs[-1] = (runs[-1][0], f, key)
        else:
            runs.append((f, f, key))
    return runs


def _add_labels(strips, fin: Finishing, pl: brand.Plan, size, font, work_dir: str) -> int:
    """Lines and boxes of the labels. Returns the number of strips made."""
    width, height = size
    box_rgb = brand.hex_to_rgb(fin.color1)
    text_rgb = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2)
    px = fin.label_px or C.font_px(height, "MEDIUM")
    line_w = max(1.5, height * 0.0028)
    made = 0
    os.makedirs(work_dir, exist_ok=True)
    for n, (a, b, _key) in enumerate(_label_runs(fin.label_track)):
        draws = [d for d in fin.label_track[a] if d.alpha > 0.001]
        frames = (pl.body_start - 1 + a, pl.body_start - 1 + b)
        path = os.path.join(work_dir, f"lines_{n:05d}.png")
        _save_rgba(path, C.draw_labels(size, draws, box_rgb, text_rgb, line_w))
        _image(strips, f"label lines {n}", path, frames, CH_LABEL_LINE, (0, 0, width, height), size)
        for j, d in enumerate(draws):
            st = _text(strips, f"label {n}.{j}", d.text, frames, CH_LABEL_TEXT + j % 80, px, text_rgb,
                       (d.box.cx / width, d.box.cy / height), font=font)
            st.use_box = True
            st.box_color = (*box_rgb, 0.88)
            st.box_margin = 0.45 * px / width
            st.blend_alpha = d.alpha
            made += 1
    return made


def _add_cards(strips, fin: Finishing, pl: brand.Plan, size, fps: int, font) -> None:
    width, height = size
    fg = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2)
    for i, card in enumerate(fin.cards):
        frames = C.card_frames(card, fps, pl.title_frames, pl.body_frames)
        if frames is None:
            continue
        ch = CH_PICTURE + 3 * (i % 8)
        fade = brand.seconds_to_frames(card.fade, fps)
        pw, ph = _image_size(card.file)
        x, y, w, h = C.picture_box(card.mode, card.corner, size, pw, ph)
        if card.mode == "FULL":
            def bg(fr, k, ch=ch):
                st = strips.new_effect(name=f"picture {i + 1} background.{k}", type="COLOR", channel=ch,
                                       frame_start=fr[0], length=fr[1] - fr[0] + 1)
                st.color = brand.hex_to_rgb(fin.color1)
                return st
            _faded(bg, frames[0], frames[1], fade)
            if card.caption:                       # leave room for the caption under the picture
                x, y, w, h = C.picture_box("FULL", "BR", (width, int(height * 0.88)), pw, ph)
                y += int(height * 0.12)
        _faded(lambda fr, k, ch=ch: _image(strips, f"picture {i + 1}.{k}", card.file, fr, ch + 1, (x, y, w, h),
                                            size)[0], frames[0], frames[1], fade)
        if card.caption:
            if card.mode == "FULL":
                loc, wrap = (0.5, 0.06), 0.9
            else:                                   # next to the small picture, on the side facing the middle
                above = card.corner in ("BL", "BR")
                loc = ((x + w / 2) / width, ((y + h + 0.04 * height) if above else (y - 0.04 * height)) / height)
                wrap = min(0.9, max(0.2, 1.6 * w / width))
            _faded(lambda fr, k, ch=ch, loc=loc, wrap=wrap: _text(
                strips, f"picture {i + 1} caption.{k}", card.caption, fr, ch + 2, brand.card_font_size(height, 0.04),
                fg, loc, font=font, wrap=wrap, shadow=True), frames[0], frames[1], fade)


def _add_music(enc, strips, fin: Finishing, pl: brand.Plan, fps: int):
    """The sound strip: starts ``start`` s into the video, is cut at the video's end, fades in and out. Returns
    the plan (or None when there is no music in this video)."""
    spec = fin.music
    if spec is None:
        return None
    first = 1 + max(0, int(round(spec.start * fps)))
    if first > pl.total:
        return None
    st = strips.new_sound(name="music", filepath=spec.file, channel=CH_MUSIC, frame_start=first)
    in_frames = int(st.frame_final_duration)
    spec.length = in_frames / float(fps) if in_frames > 0 else 0.0
    plan = C.music_plan(spec, pl.total, fps)
    if plan is None:
        strips.remove(st)
        return None
    st.frame_final_end = plan.last + 1
    st.volume = plan.volume
    keys = [(plan.first, 0.0 if plan.fade_in else plan.volume)]
    if plan.fade_in:
        keys.append((plan.first + plan.fade_in, plan.volume))
    if plan.fade_out:
        keys.append((plan.last - plan.fade_out + 1, plan.volume))
        keys.append((plan.last + 1, 0.0))
    if len(keys) > 1:
        for f, v in keys:
            st.volume = v
            st.keyframe_insert("volume", frame=f)
        try:
            for fc in _fcurves(enc.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        except Exception:
            pass
    return plan


def build_sequence(enc, files: list[str], size: tuple[int, int], fps: int, fin: Finishing | None,
                   steps: list[tuple[str, float, float]] | None = None, white_under: bool = False,
                   solid_under: bool = False) -> brand.Plan:
    """Put the pictures and the finishing on the sequencer of the scene ``enc``. Returns the plan
    (frames of title card, animation, end card). The scene's frame range is set to the whole film."""
    width, height = size
    fin = fin or Finishing()
    body = len(files)
    pl = brand.plan(fin, body, fps, steps)
    se = enc.sequence_editor_create()
    strips = se.strips
    enc.frame_start, enc.frame_end = 1, max(1, pl.total)
    if white_under:
        bg = strips.new_effect(name="white", type="COLOR", channel=CH_UNDER, frame_start=1, length=pl.total)
        bg.color = (1.0, 1.0, 1.0)
    font = _font(fin.font)

    # the pictures
    img = strips.new_image(name="frames", filepath=files[0], channel=CH_FRAMES, frame_start=pl.body_start)
    for f in files[1:]:
        img.elements.append(os.path.basename(f))
    img.blend_type = "ALPHA_OVER"

    body_frames = (pl.body_start, pl.body_start + body - 1)
    if fin.logo_on:
        lw, lh = _image_size(fin.logo_file)
        box = brand.logo_box(fin.logo_corner, width, height, lw, lh, fin.logo_size)
        _image(strips, "logo", fin.logo_file, body_frames, CH_LOGO, box, size)

    fade = brand.seconds_to_frames(brand.CAPTION_FADE_SECONDS, fps)
    for i, cap in enumerate(pl.captions):
        def make(fr, k, i=i, cap=cap):
            st = _text(strips, f"caption {i + 1}" if k == 0 else f"caption {i + 1}.{k}", cap.text, fr, CH_CAPTION,
                       brand.card_font_size(height, 0.05), (1.0, 1.0, 1.0), (0.5, 0.09), font=font, wrap=0.9,
                       shadow=True)
            st.use_box = True
            st.box_color = (0.0, 0.0, 0.0, 0.45)
            st.box_margin = 0.012
            return st
        _faded(make, cap.start, cap.end, fade)

    if pl.title_frames:
        _card(strips, "title", (1, pl.title_frames), fin, size, fps, font,
              [(fin.title, 0.09, 0.56), (fin.subtitle, 0.045, 0.40)])
    if pl.end_frames:
        lw, lh = _image_size(fin.logo_file) if fin.logo_file else (1, 1)
        box = brand.fit_logo(width, height, lw, lh, 0.35)
        if fin.logo_file:                      # logo above the middle, the contact line under it
            box = (box[0], int(height * 0.5), box[2], min(box[3], int(height * 0.35)))
        _card(strips, "end", (pl.end_start, pl.total), fin, size, fps, font,
              [(fin.end_text, 0.04, 0.34 if fin.logo_file else 0.5)],
              logo_box=box if fin.logo_file else None)

    if fin.label_track:
        _add_labels(strips, fin, pl, size, font, fin.label_dir or tempfile.mkdtemp(prefix="fr_labels_"))
    if fin.cards:
        _add_cards(strips, fin, pl, size, fps, font)
    pl.music = _add_music(enc, strips, fin, pl, fps)

    if fin.watermark:
        px = brand.card_font_size(height, fin.watermark_size)
        st = _text(strips, "watermark", fin.watermark, (1, pl.total), CH_WATERMARK, px, (0.55, 0.55, 0.55),
                   (0.5, 0.5), font=font, shadow=True)
        st.blend_alpha = max(0.0, min(1.0, fin.watermark_opacity))
        try:
            st.transform.rotation = WATERMARK_ANGLE
        except (AttributeError, TypeError):
            pass
    return pl


# ---------------------------------------------------------------------------
# stills
# ---------------------------------------------------------------------------


def finish_picture(path: str, fin: Finishing, file_type: str = "PNG") -> None:
    """Put the logo and the watermark on a finished picture file (in place)."""
    if not (fin.logo_on or fin.watermark or fin.label_track):
        return
    img = bpy.data.images.load(path, check_existing=False)
    try:
        size = (int(img.size[0]), int(img.size[1]))
    finally:
        bpy.data.images.remove(img)
    enc = bpy.data.scenes.new("FR finish")
    work = tempfile.mkdtemp(prefix="fr_finish_")
    try:
        r = enc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = size[0], size[1], 100
        enc.view_settings.view_transform = "Standard"
        try:
            enc.view_settings.look = "None"
        except TypeError:
            pass
        only = Finishing(logo_corner=fin.logo_corner, logo_file=fin.logo_file, logo_size=fin.logo_size,
                         color1=fin.color1, color2=fin.color2, font=fin.font, watermark=fin.watermark,
                         watermark_size=fin.watermark_size, watermark_opacity=fin.watermark_opacity,
                         label_track=fin.label_track, label_px=fin.label_px, label_dir=work)
        build_sequence(enc, [path], size, 1, only)
        enc.frame_start = enc.frame_end = 1
        im = r.image_settings
        try:
            im.media_type = "IMAGE"
        except (AttributeError, TypeError):
            pass
        jpeg = file_type == "JPEG"
        im.file_format = "JPEG" if jpeg else "PNG"
        im.color_mode = "RGB" if jpeg else "RGBA"
        if not jpeg:
            im.color_depth = "8"
        else:
            im.quality = 95
        tmp = path + ".fin.png" if not jpeg else path + ".fin.jpg"
        r.use_file_extension = False
        r.filepath = tmp
        bpy.ops.render.render(write_still=True, scene=enc.name)
        os.replace(tmp, path)
    finally:
        bpy.data.scenes.remove(enc)
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------
# shape: crop or extend
# ---------------------------------------------------------------------------


def apply_shape_fit(scene, mode: str, shape: str) -> None:
    """Frame the camera for a 1:1 or 9:16 video. ``mode`` Crop keeps what the 16:9 picture shows from top to
    bottom (the sides are cut), Extend keeps what it shows from side to side (more above and below).
    16:9 is left as it is. Only meant for the copy of the project the queue renders."""
    cam = scene.camera
    if cam is None or cam.type != "CAMERA" or shape == "presentation":
        return
    d = cam.data
    if mode == brand.FIT_CROP:
        d.sensor_fit = "VERTICAL"
        d.sensor_height = d.sensor_width * brand.CROP_ASPECT
        _scale_ortho(d, brand.CROP_ASPECT)
    else:
        d.sensor_fit = "HORIZONTAL"


def _scale_ortho(cam_data, factor: float) -> None:
    cam_data.ortho_scale *= factor
    ad = cam_data.animation_data
    if ad and ad.action:
        for fc in _fcurves(ad.action):
            if fc.data_path == "ortho_scale":
                for kp in fc.keyframe_points:
                    kp.co.y *= factor
                    kp.handle_left.y *= factor
                    kp.handle_right.y *= factor
                fc.update()


# ---------------------------------------------------------------------------
# brand kits in the library
# ---------------------------------------------------------------------------

ENV_FOLDER = "FRESING_BRAND_KITS_DIR"        # tests: use this folder instead of the library


def kit_folder() -> tuple[str, bool, str]:
    """(folder, shared, problem): the "Brand kits" folder, whether it is in the shared library, and why it
    cannot be used right now ('' = fine). Same place logic as the rule sets."""
    override = os.environ.get(ENV_FOLDER)
    if override:
        return override, True, ""
    from . import prefs, rule_sets
    p = prefs.get()
    lib = bpy.path.abspath(p.library_path) if p is not None and p.library_path else ""
    if not lib:
        return os.path.join(rule_sets.documents_dir(), "Fresing Render", brand.FOLDER), False, ""
    path = os.path.join(lib, brand.FOLDER)
    if not os.path.isdir(lib):
        return path, True, f"The shared library cannot be reached ({lib})"
    return path, True, ""


def kit_from_settings(s) -> brand.BrandKit:
    return brand.BrandKit(name=s.brand_name.strip(), logo=os.path.basename(s.brand_logo) if s.brand_logo else "",
                          color1=brand.linear_to_hex(s.brand_color1), color2=brand.linear_to_hex(s.brand_color2),
                          font=bpy.path.abspath(s.brand_font) if s.brand_font else "", contact=s.brand_contact)


def load_into_settings(s, folder: str, kit: brand.BrandKit) -> None:
    s.brand_name = kit.name
    s.brand_logo = brand.logo_path(folder, kit)
    s.brand_color1 = brand.rgb_linear(kit.color1)
    s.brand_color2 = brand.rgb_linear(kit.color2, brand.DEFAULT_COLOR_2)
    s.brand_font = kit.font
    s.brand_contact = kit.contact
