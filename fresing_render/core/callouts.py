"""Labels pointing at parts, picture cards and music (task 0025). No Blender here.

* **Labels (callouts):** where the text boxes go (outside the machine's outline where possible, never over
  each other), the line from the part's point to its box, when a label is shown (always, or during one
  animation step, fading in and out) and the numbers that draw the line.
* **Picture cards:** when a picture is on screen (frames of the finished video) and its fade.
* **Music:** where the sound starts, how long it plays (cut to the video), its fade in and out.

Picture positions are in pixels of the finished picture, ``y`` counted from the BOTTOM (Blender's way).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

SIZES = {"SMALL": 0.026, "MEDIUM": 0.036, "LARGE": 0.05}       # text height as a part of the picture height
LABEL_FADE_SECONDS = 0.3
AUDIO_TYPES = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
CARD_FADE_SECONDS = 0.4
CORNER_PICTURE_SIZE = 0.28            # a picture in a corner: this part of the picture width


# ---------------------------------------------------------------------------
# when is a label shown
# ---------------------------------------------------------------------------


def label_alpha(t: float, window: tuple[float, float] | None, fade: float = LABEL_FADE_SECONDS) -> float:
    """How visible a label is at second ``t`` (0..1). ``window`` None = always; else (start, end) seconds of the
    animation step it belongs to: it fades in over ``fade`` s from the start and out to the end."""
    if window is None:
        return 1.0
    a, b = window
    if t < a or t > b:
        return 0.0
    fade = max(0.0, min(fade, (b - a) / 2.0))
    if fade <= 1e-9:
        return 1.0
    return max(0.0, min(1.0, (t - a) / fade, (b - t) / fade))


# ---------------------------------------------------------------------------
# where the boxes go
# ---------------------------------------------------------------------------


@dataclass
class Box:
    x: float          # left
    y: float          # bottom
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def overlaps(self, o: "Box", gap: float = 0.0) -> bool:
        return not (self.x + self.w + gap <= o.x or o.x + o.w + gap <= self.x
                    or self.y + self.h + gap <= o.y or o.y + o.h + gap <= self.y)

    def overlap_area(self, o: "Box") -> float:
        dx = min(self.x + self.w, o.x + o.w) - max(self.x, o.x)
        dy = min(self.y + self.h, o.y + o.h) - max(self.y, o.y)
        return max(0.0, dx) * max(0.0, dy)

    def distance_to(self, px: float, py: float) -> float:
        dx = max(self.x - px, 0.0, px - (self.x + self.w))
        dy = max(self.y - py, 0.0, py - (self.y + self.h))
        return math.hypot(dx, dy)

    def inside(self, width: float, height: float, margin: float = 0.0) -> bool:
        return (self.x >= margin - 1e-6 and self.y >= margin - 1e-6 and self.x + self.w <= width - margin + 1e-6
                and self.y + self.h <= height - margin + 1e-6)


@dataclass
class LabelDraw:
    """One label ready to be drawn in one picture."""
    text: str
    anchor: tuple[float, float]       # the point on the part, in pixels
    box: Box
    alpha: float = 1.0

    def key(self) -> tuple:
        return (self.text, round(self.anchor[0]), round(self.anchor[1]), round(self.box.x), round(self.box.y),
                round(self.alpha, 2))


def place_labels(anchors: list[tuple[float, float]], sizes: list[tuple[float, float]], canvas: tuple[int, int],
                 outline: tuple[float, float, float, float] | None = None, gap: float | None = None,
                 margin: float | None = None) -> list[Box]:
    """Boxes for labels, one per anchor, in the order given.

    The boxes try to sit in the free space beside the machine's ``outline`` (x0, y0, x1, y1): left or right
    of it, or above or below, as near to the anchor as they can, in a column along that side. They stay
    inside the picture and never overlap each other. Where there is no room at all, the least bad place
    (smallest overlap) is taken."""
    width, height = canvas
    short = min(width, height)
    gap = 0.012 * short if gap is None else gap
    margin = 0.02 * short if margin is None else margin
    if outline is None:
        outline = (width * 0.25, height * 0.2, width * 0.75, height * 0.8)
    ox0, oy0, ox1, oy1 = outline
    taken: list[Box] = []
    out: list[Box] = []
    # labels nearest to the outline's edge first would be neater, but a fixed order keeps frames stable
    for (ax, ay), (w, h) in zip(anchors, sizes):
        cands: list[tuple[float, Box, float]] = []          # (score, box, overlap)
        side_x = {"L": ox0 - gap - w, "R": ox1 + gap}
        side_y = {"T": oy1 + gap, "B": oy0 - gap - h}
        slide = h + gap
        for side in ("L", "R", "T", "B"):
            for k in range(0, 12):
                for sign in ((1,) if k == 0 else (1, -1)):
                    off = sign * k * slide
                    if side in side_x:
                        x = side_x[side]
                        y = ay - h / 2 + off
                    else:
                        x = ax - w / 2 + off
                        y = side_y[side]
                    x = min(max(x, margin), max(margin, width - margin - w))
                    y = min(max(y, margin), max(margin, height - margin - h))
                    b = Box(x, y, w, h)
                    ov = sum(b.overlap_area(t) for t in taken)
                    out_of_picture = 0.0 if b.inside(width, height, margin / 2) else 1e9
                    # inside the machine's outline is allowed only when nothing else is free
                    over_machine = b.overlap_area(Box(ox0, oy0, ox1 - ox0, oy1 - oy0)) > 0
                    score = b.distance_to(ax, ay) + (0.35 * short if over_machine else 0.0) + out_of_picture
                    cands.append((score + 1e7 * (ov > 0), b, ov))
        best = min(cands, key=lambda c: (c[2] > 0, c[2], c[0]))
        taken.append(best[1])
        out.append(best[1])
    return out


def box_size(text_width: float, text_height: float, font_px: float) -> tuple[float, float]:
    """Size of a label box around a text of the given size (a little padding all round)."""
    pad = 0.45 * font_px
    return text_width + 2 * pad, text_height + 2 * pad * 0.8


def estimate_text_width(text: str, font_px: float) -> float:
    """A rough width when Blender cannot measure the font (tests without a font): about 0.55 em per letter."""
    return 0.55 * font_px * len(text)


def font_px(height: int, size: str) -> int:
    return max(8, round(height * SIZES.get(size, SIZES["MEDIUM"])))


# ---------------------------------------------------------------------------
# the line (drawn into a picture)
# ---------------------------------------------------------------------------


def draw_line(img: np.ndarray, p0: tuple[float, float], p1: tuple[float, float], rgb, alpha: float = 1.0,
              width: float = 2.0, dot: float = 0.0) -> None:
    """Draw an anti-aliased line (and a round dot of radius ``dot`` at ``p0``) into ``img`` (height, width, 4)
    float 0..1. Points are in pixels, y from the BOTTOM; the array's row 0 is the BOTTOM row too (Blender's
    image order). Colours are blended over what is there (straight alpha)."""
    h, w = img.shape[:2]
    x0, y0 = p0
    x1, y1 = p1
    pad = width + dot + 2
    xa, xb = int(max(0, math.floor(min(x0, x1) - pad))), int(min(w, math.ceil(max(x0, x1) + pad) + 1))
    ya, yb = int(max(0, math.floor(min(y0, y1) - pad))), int(min(h, math.ceil(max(y0, y1) + pad) + 1))
    if xb <= xa or yb <= ya:
        return
    ys, xs = np.mgrid[ya:yb, xa:xb]
    px, py = xs + 0.5, ys + 0.5
    dx, dy = x1 - x0, y1 - y0
    ln = dx * dx + dy * dy
    if ln < 1e-9:
        d = np.hypot(px - x0, py - y0)
    else:
        t = np.clip(((px - x0) * dx + (py - y0) * dy) / ln, 0.0, 1.0)
        d = np.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
    cover = np.clip(width / 2 + 0.5 - d, 0.0, 1.0)
    if dot > 0:
        cover = np.maximum(cover, np.clip(dot + 0.5 - np.hypot(px - x0, py - y0), 0.0, 1.0))
    a = cover * alpha
    region = img[ya:yb, xa:xb]
    out_a = a + region[..., 3] * (1 - a)
    safe = np.where(out_a > 1e-6, out_a, 1.0)
    for c in range(3):
        region[..., c] = (rgb[c] * a + region[..., c] * region[..., 3] * (1 - a)) / safe
    region[..., 3] = out_a


def draw_labels(size: tuple[int, int], draws: list[LabelDraw], outline_rgb, line_rgb, width_px: float) -> np.ndarray:
    """The lines (with a dark edge so they show on any background) and anchor dots of all labels in one
    transparent picture, (height, width, 4) float, row 0 = bottom. The text boxes are drawn by the video."""
    w, h = size
    img = np.zeros((h, w, 4), np.float32)
    for d in draws:
        if d.alpha <= 0.001:
            continue
        end = nearest_edge_point(d.box, d.anchor)
        draw_line(img, d.anchor, end, outline_rgb, d.alpha, width_px * 2.2, dot=width_px * 2.6)
    for d in draws:
        if d.alpha <= 0.001:
            continue
        end = nearest_edge_point(d.box, d.anchor)
        draw_line(img, d.anchor, end, line_rgb, d.alpha, width_px, dot=width_px * 1.7)
    return img


def nearest_edge_point(box: Box, p: tuple[float, float]) -> tuple[float, float]:
    """Where the line meets the box: the middle of the box (the box is drawn over the end of the line)."""
    return box.cx, box.cy


# ---------------------------------------------------------------------------
# picture cards
# ---------------------------------------------------------------------------


@dataclass
class CardSpec:
    """A picture shown during the animation."""
    file: str                   # full path of the picture
    start: float                # seconds from the start of the animation
    seconds: float
    mode: str = "FULL"          # FULL = whole picture, CORNER = small picture in a corner
    corner: str = "BR"
    caption: str = ""
    fade: float = CARD_FADE_SECONDS


def card_frames(card: CardSpec, fps: int, title_frames: int, body_frames: int) -> tuple[int, int] | None:
    """(first, last) frame of the finished video a card is on screen, or None when it falls outside the
    animation. Counted from the first frame of the video (the title card is in front of the animation)."""
    first = title_frames + 1 + max(0, int(round(card.start * fps)))
    last = first + max(1, int(round(card.seconds * fps))) - 1
    end_of_body = title_frames + body_frames
    if first > end_of_body:
        return None
    return first, min(last, end_of_body)


def picture_box(mode: str, corner: str, canvas: tuple[int, int], pw: int, ph: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) of a card's picture. FULL: as large as fits inside the picture, centred. CORNER: a small
    picture (a quarter of the width) in the corner, with a margin."""
    from .brand import fit_logo, logo_box
    width, height = canvas
    if mode == "CORNER":
        return logo_box(corner, width, height, pw, ph, CORNER_PICTURE_SIZE)
    return fit_logo(width, height, pw, ph, 1.0)


# ---------------------------------------------------------------------------
# music
# ---------------------------------------------------------------------------


@dataclass
class MusicSpec:
    file: str
    start: float = 0.0          # seconds from the start of the video where the music begins
    volume: float = 0.8
    fade_in: float = 1.0
    fade_out: float = 2.0
    length: float = 0.0         # length of the audio file in seconds (0 = unknown)


@dataclass
class MusicPlan:
    first: int                  # first frame of the video with sound
    last: int                   # last frame (the music is cut here)
    fade_in: int                # frames
    fade_out: int
    volume: float


def music_plan(music: MusicSpec, total_frames: int, fps: int) -> MusicPlan | None:
    """When the music plays. It starts ``start`` seconds into the video and is cut at the end of the video (or
    at the end of the file when that is shorter)."""
    first = 1 + max(0, int(round(music.start * fps)))
    if first > total_frames:
        return None
    last = total_frames
    if music.length > 0:
        last = min(last, first + max(1, int(round(music.length * fps))) - 1)
    vol = max(0.0, min(1.0, music.volume))
    n = last - first + 1
    fi = max(0, min(int(round(music.fade_in * fps)), n))
    fo = max(0, min(int(round(music.fade_out * fps)), n))
    if fi + fo > n:                                   # short: share the time
        fi = (n * fi) // max(1, fi + fo)
        fo = n - fi
    return MusicPlan(first, last, fi, fo, vol)


def volume_at(plan: MusicPlan, frame: int) -> float:
    """The music's volume at a frame of the video (0 outside the music)."""
    if frame < plan.first or frame > plan.last:
        return 0.0
    v = plan.volume
    if plan.fade_in > 0 and frame < plan.first + plan.fade_in:
        v *= (frame - plan.first) / plan.fade_in
    if plan.fade_out > 0 and frame > plan.last - plan.fade_out:
        v *= (plan.last - frame + 1) / plan.fade_out
    return max(0.0, min(plan.volume, v))


def is_audio(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_TYPES


def is_picture(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in PICTURE_TYPES
