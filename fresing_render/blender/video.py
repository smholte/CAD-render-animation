"""Video finishing (task 0018): logo in a corner, title card, end card, captions, watermark.

Everything is put on top of the rendered pictures with Blender's Video Sequencer in a throw-away scene:
the finished video needs no Python to play. The numbers (time line, captions, where the logo goes) come
from ``core/brand.py``; here they are turned into strips.
"""

from __future__ import annotations

import math
import os

import bpy
import numpy as np

from ..core import brand
from ..core import callouts as callouts_core
from ..core.brand import Finishing

# channels, bottom to top
CH_UNDER, CH_FRAMES, CH_CARD, CH_LOGO, CH_CAPTION, CH_WATERMARK = 1, 2, 3, 5, 7, 9
CH_LINES, CH_PICTURE, CH_LABEL, CH_CORNER, CH_MUSIC = 4, 6, 8, 12, 30      # task 0025

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


def _cards_of(scene, anim) -> list:
    """The picture cards of an animation that can be shown (the file exists)."""
    from . import animation
    steps = {b.name.strip(): animation.block_end(b) for b in anim.blocks if b.enabled and b.name.strip()}
    out = []
    for c in anim.cards:
        path = bpy.path.abspath(c.file) if c.file else ""
        if not path or not os.path.isfile(path) or not path.lower().endswith(brand.LOGO_TYPES):
            continue
        at = steps.get(c.after_step.strip(), c.at) if c.after_step.strip() else c.at
        out.append(callouts_core.PictureCard(path, c.mode, c.corner, c.seconds, at, c.caption.strip(), c.size))
    return out


def _music_path(anim) -> str:
    p = bpy.path.abspath(anim.music_file) if anim.music_file else ""
    return p if p and os.path.isfile(p) and p.lower().endswith(MUSIC_TYPES) else ""


MUSIC_TYPES = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")


def finishing_for_animation(scene, anim, watermark: bool = False) -> Finishing:
    s = scene.fresing
    logo = _logo_path(s)
    return Finishing(
        music_file=_music_path(anim), music_start=anim.music_start, music_volume=anim.music_volume,
        music_fade_in=anim.music_fade_in, music_fade_out=anim.music_fade_out, cards=_cards_of(scene, anim),
        logo_corner=anim.fin_logo, logo_file=logo, logo_size=anim.fin_logo_size,
        title_on=anim.fin_title_on, title=anim.fin_title, subtitle=anim.fin_subtitle,
        title_seconds=anim.fin_title_seconds, end_on=anim.fin_end_on, end_seconds=anim.fin_end_seconds,
        captions_on=anim.fin_captions, watermark=watermark_words(s) if watermark else "",
        watermark_size=s.wm_size, watermark_opacity=s.wm_opacity, **_kit_fields(s))


def finishing_for_still(scene, watermark: bool = False) -> Finishing:
    s = scene.fresing
    return Finishing(logo_corner=s.still_logo, logo_file=_logo_path(s), logo_size=s.still_logo_size,
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
    if anim is not None:
        for c in anim.cards:
            if not c.file or not os.path.isfile(bpy.path.abspath(c.file)):
                out.append(f"The picture card '{c.name or c.file or 'without a file'}' has no picture file: left out")
        if anim.music_file and not _music_path(anim):
            out.append("The music file cannot be found or is not WAV, MP3, OGG, FLAC or M4A: no music")
    if s.brand_font and not os.path.isfile(bpy.path.abspath(s.brand_font)):
        out.append("The brand font file cannot be found: Blender's own font is used")
    return out


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

    # the pictures: one strip, or several when a full-picture card is put in between
    cuts = [0] + sorted({a for a, _n in pl.inserts if 0 < a < body}) + [body]
    for k in range(len(cuts) - 1):
        part = files[cuts[k]:cuts[k + 1]]
        if not part:
            continue
        img = strips.new_image(name="frames" if k == 0 else f"frames {k + 1}", filepath=part[0], channel=CH_FRAMES,
                               frame_start=pl.video_frame(cuts[k] + 1))
        for f in part[1:]:
            img.elements.append(os.path.basename(f))
        img.blend_type = "ALPHA_OVER"

    body_frames = (pl.body_start, pl.video_frame(body))
    if fin.logo_on:
        lw, lh = _image_size(fin.logo_file)
        box = brand.logo_box(fin.logo_corner, width, height, lw, lh, fin.logo_size)
        _image(strips, "logo", fin.logo_file, body_frames, CH_LOGO, box, size)
    _labels(strips, pl, fin, size, fps, font)
    _picture_cards(strips, pl, fin, size, fps, font)

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

    if fin.music_file:
        add_music(enc, pl, fin, fps)
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
# labels, picture cards, music (task 0025)
# ---------------------------------------------------------------------------


def _pieces(pl: brand.Plan, frames) -> list[tuple[int, int]]:
    """Runs of body frames that are also consecutive in the video (a full-picture card in between splits a run)."""
    out = []
    for a, b in callouts_core.runs(frames):
        start = a
        for i in range(a, b + 1):
            if i == b or pl.video_frame(i + 1) != pl.video_frame(i) + 1:
                out.append((start, i))
                start = i + 1
    return out


def _video_runs(pl: brand.Plan, frames) -> list[tuple[int, int]]:
    return [(pl.video_frame(a), pl.video_frame(b)) for a, b in _pieces(pl, frames)]


def _labels(strips, pl: brand.Plan, fin: Finishing, size, fps: int, font) -> None:
    """Lines (one transparent picture per frame, under the boxes) and the label boxes with their text."""
    width, height = size
    for a, b in _pieces(pl, [f for f in fin.label_lines if 1 <= f <= pl.body_frames]):
        files = [fin.label_lines[j] for j in range(a, b + 1)]
        st = strips.new_image(name=f"lines {a}", filepath=files[0], channel=CH_LINES, frame_start=pl.video_frame(a))
        for f in files[1:]:
            st.elements.append(os.path.basename(f))
        st.blend_type = "ALPHA_OVER"
    fade = brand.seconds_to_frames(brand.CAPTION_FADE_SECONDS, fps)
    bg = brand.hex_to_rgb(fin.color1)
    fg = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2)
    px = fin.label_font_px or brand.card_font_size(height, callouts_core.SIZE_FACTORS["MEDIUM"])
    for n, lab in enumerate(fin.labels):
        x, y, w, h = lab.box
        for r, (first, last) in enumerate(_video_runs(pl, lab.frames())):
            def make(fr, k, n=n, r=r, lab=lab, x=x, y=y, w=w, h=h):
                st = _text(strips, f"label {n + 1}.{r}.{k}", lab.text, fr, CH_LABEL, px, fg,
                           ((x + w / 2) / width, (y + h / 2) / height), font=font, wrap=0.0)
                st.use_box = True
                st.box_color = (*bg, 0.92)
                st.box_margin = 0.45 * px / height
                return st
            _faded(make, first, last, fade)


def _picture_cards(strips, pl: brand.Plan, fin: Finishing, size, fps: int, font) -> None:
    width, height = size
    fade = brand.seconds_to_frames(brand.CARD_FADE_SECONDS, fps)
    fg = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2)
    corner_n = 0
    for i, placed in enumerate(pl.placed):
        c = placed.card
        pw, ph = _image_size(c.file)
        frames = (placed.first, placed.last)
        if c.mode == callouts_core.FULL:
            bg = strips.new_effect(name=f"picture {i + 1} background", type="COLOR", channel=CH_CARD,
                                   frame_start=placed.first, length=placed.last - placed.first + 1)
            bg.color = brand.hex_to_rgb(fin.color1)
            box = brand.fit_logo(width, height, pw, ph, 1.0)
            _faded(lambda fr, k, i=i, box=box: _image(strips, f"picture {i + 1}.{k}", c.file, fr, CH_CARD + 1, box,
                                                      size)[0], *frames, fade)
            if c.caption:
                _faded(lambda fr, k, i=i, c=c: _text(
                    strips, f"picture {i + 1} caption.{k}", c.caption, fr, CH_CARD + 2,
                    brand.card_font_size(height, 0.045), fg, (0.5, 0.07), font=font, wrap=0.9, shadow=True),
                    *frames, fade)
        else:
            box = brand.logo_box(c.corner, width, height, pw, ph, c.size)
            channel = CH_CORNER + corner_n
            corner_n += 2
            _faded(lambda fr, k, i=i, box=box, channel=channel: _image(
                strips, f"picture {i + 1}.{k}", c.file, fr, channel, box, size)[0], *frames, fade)
            if c.caption:
                cx = (box[0] + box[2] / 2) / width
                cy = min(0.97, (box[1] + box[3]) / height + 0.04) if c.corner in ("BL", "BR") else \
                    max(0.03, box[1] / height - 0.04)
                _faded(lambda fr, k, i=i, c=c, cx=cx, cy=cy, channel=channel: _text(
                    strips, f"picture {i + 1} caption.{k}", c.caption, fr, channel + 1,
                    brand.card_font_size(height, 0.03), fg, (cx, cy), font=font, wrap=0.45, shadow=True),
                    *frames, fade)


def sound_frames(strips, path: str) -> int:
    """How long a sound file is, in frames of the scene."""
    probe = strips.new_sound(name="probe", filepath=path, channel=CH_MUSIC + 1, frame_start=1)
    try:
        return int(probe.duration)
    finally:
        strips.remove(probe)


_TEMP_DIRS: list[str] = []


def cleanup() -> None:
    """Delete the sound files made for a video (call when the video is written)."""
    import shutil
    while _TEMP_DIRS:
        shutil.rmtree(_TEMP_DIRS.pop(), ignore_errors=True)


def _mixdown(path: str, first_frame: int, frames: int, fps: int, out: str, rate: int = 48000) -> None:
    """Decode ``frames`` frames of a sound file (from its beginning) into a WAV file."""
    tmp = bpy.data.scenes.new("FR music")
    try:
        tmp.render.fps, tmp.render.fps_base = fps, 1.0
        st = tmp.sequence_editor_create().strips.new_sound(name="m", filepath=path, channel=1, frame_start=1)
        st.left_handle, st.right_handle = 1, 1 + frames
        tmp.frame_start, tmp.frame_end = 1, frames
        with bpy.context.temp_override(scene=tmp):
            bpy.ops.sound.mixdown(filepath=out, container="WAV", codec="PCM", format="S16", mixrate=rate)
    finally:
        bpy.data.scenes.remove(tmp)


def add_music(enc, pl: brand.Plan, fin: Finishing, fps: int):
    """The music as one sound strip: cut to the video's length and faded by working out the volume of every
    sample (Blender does not evaluate animated strip volumes without a window). Returns the strip or None."""
    import tempfile
    import wave
    probe = bpy.data.scenes.new("FR music")
    try:
        probe.render.fps, probe.render.fps_base = fps, 1.0
        n = sound_frames(probe.sequence_editor_create().strips, fin.music_file)
    finally:
        bpy.data.scenes.remove(probe)
    span = callouts_core.music_span(pl.total, fps, fin.music_start, n)
    if span is None or fin.music_volume <= 0:
        return None
    first, last = span
    folder = tempfile.mkdtemp(prefix="fr_music_")
    _TEMP_DIRS.append(folder)
    raw, done = os.path.join(folder, "raw.wav"), os.path.join(folder, "music.wav")
    _mixdown(fin.music_file, 1, last - first + 1, fps, raw)
    with wave.open(raw) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch).astype(np.float32)
    gain = callouts_core.gain_curve(len(data), rate, fin.music_volume, fin.music_fade_in, fin.music_fade_out)
    out = np.clip(data * gain[:, None], -32768, 32767).astype("<i2")
    with wave.open(done, "w") as w:
        w.setnchannels(ch)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(out.tobytes())
    st = enc.sequence_editor.strips.new_sound(name="music", filepath=done, channel=CH_MUSIC, frame_start=first)
    st.right_handle = last + 1
    enc.use_audio = True
    return st


# ---------------------------------------------------------------------------
# stills
# ---------------------------------------------------------------------------


def finish_picture(path: str, fin: Finishing, file_type: str = "PNG") -> None:
    """Put the logo and the watermark on a finished picture file (in place)."""
    if not (fin.logo_on or fin.watermark or fin.labels):
        return
    img = bpy.data.images.load(path, check_existing=False)
    try:
        size = (int(img.size[0]), int(img.size[1]))
    finally:
        bpy.data.images.remove(img)
    enc = bpy.data.scenes.new("FR finish")
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
                         labels=fin.labels, label_lines=fin.label_lines, label_font_px=fin.label_font_px)
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
