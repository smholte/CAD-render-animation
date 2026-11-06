"""Labels pointing at parts, picture cards and music (task 0025) - the numbers, no Blender here.

* **Labels:** a text box beside the model with a thin line to a point on a part. The point is projected
  into the picture for every frame (``blender/callouts.py``); here the boxes are placed so that none
  overlap and they stay outside the machine's outline where there is room, and the line is drawn into
  a transparent picture (numpy).
* **Picture cards:** a photo or diagram shown full screen (the animation waits) or in a corner (the
  animation goes on) for some seconds.
* **Music:** a sound file under the whole video: start, volume, fade in/out, cut to the video's length,
  made of pieces with a fixed volume each (Blender does not evaluate animated strip properties when it
  renders without a window).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

FULL, CORNER = "FULL", "CORNER"
CARD_CORNERS = ("TL", "TR", "BL", "BR")
SIZE_FACTORS = {"SMALL": 0.032, "MEDIUM": 0.042, "LARGE": 0.058}     # label text height / picture height
LINE_WIDTH = 0.0022                                                   # line width / picture height


# ---------------------------------------------------------------------------
# picture cards
# ---------------------------------------------------------------------------


@dataclass
class PictureCard:
    file: str                      # full path of the picture
    mode: str = FULL               # FULL: the animation waits; CORNER: a picture over the animation
    corner: str = "BR"
    seconds: float = 3.0
    at: float = 0.0                # seconds from the start of the animation (not counting the title card)
    caption: str = ""
    size: float = 0.3              # CORNER: width as a part of the picture width


@dataclass
class PlacedCard:
    card: PictureCard
    first: int                     # first and last frame in the finished video
    last: int


def place_cards(cards: list[PictureCard], title_frames: int, body_frames: int, fps: int):
    """([(after body frame, number of frames)] for full cards, [PlacedCard] for all)."""
    from .brand import seconds_to_frames
    full = []
    for c in cards:
        at = min(max(0, seconds_to_frames(c.at, fps)), body_frames)
        n = max(1, seconds_to_frames(c.seconds, fps))
        if c.mode == FULL:
            full.append((at, n, c))
    full.sort(key=lambda t: t[0])                         # stable: cards at one moment keep their order
    inserts = [(a, n) for a, n, _c in full]

    def video_frame(b: int) -> int:                       # as Plan.video_frame
        return title_frames + b + sum(n for a, n in inserts if a < b)

    placed = []
    done = 0
    for a, n, c in full:
        first = title_frames + a + sum(m for x, m in inserts[:done]) + 1
        placed.append(PlacedCard(c, first, first + n - 1))
        done += 1
    for c in cards:
        if c.mode == CORNER and body_frames > 0:
            at = min(max(0, seconds_to_frames(c.at, fps)), body_frames - 1)
            first = video_frame(at + 1)
            last = min(first + max(1, seconds_to_frames(c.seconds, fps)) - 1, video_frame(body_frames))
            placed.append(PlacedCard(c, first, last))
    return inserts, sorted(placed, key=lambda p: p.first)


# ---------------------------------------------------------------------------
# music
# ---------------------------------------------------------------------------


def music_span(total_frames: int, fps: int, start_seconds: float, music_frames: int):
    """(first, last) video frames the music plays: from ``start_seconds`` into the video, cut at the end of
    the video, or at the end of the sound file when that is shorter. None when nothing is left to play."""
    from .brand import seconds_to_frames
    first = 1 + max(0, seconds_to_frames(start_seconds, fps))
    last = min(total_frames, first + max(0, music_frames) - 1)
    return (first, last) if last >= first else None


def gain_curve(samples: int, rate: int, volume: float, fade_in: float, fade_out: float) -> np.ndarray:
    """The volume of every sample: ``volume``, rising linearly over ``fade_in`` seconds at the start and falling
    to nothing over ``fade_out`` seconds at the end (together never longer than the music)."""
    g = np.full(samples, max(0.0, volume), dtype=np.float32)
    n_in, n_out = max(0, round(fade_in * rate)), max(0, round(fade_out * rate))
    if n_in + n_out > samples:                      # too long together: both shrink in proportion
        scale = samples / (n_in + n_out)
        n_in, n_out = int(n_in * scale), int(n_out * scale)
    if n_in:
        g[:n_in] *= np.linspace(0.0, 1.0, n_in, endpoint=False, dtype=np.float32)
    if n_out:
        g[samples - n_out:] *= np.linspace(1.0, 0.0, n_out, endpoint=False, dtype=np.float32)
    return g


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------


@dataclass
class LabelPlan:
    text: str
    first: int                                  # first and last frame of the animation (body frames) it is shown
    last: int
    anchors: dict = field(default_factory=dict)  # body frame -> (x, y) pixels from the bottom-left; missing = hidden
    box: tuple = (0, 0, 0, 0)                   # x, y, width, height in pixels from the bottom-left

    def frames(self) -> list[int]:
        return sorted(f for f in self.anchors if self.first <= f <= self.last)


def runs(frames) -> list[tuple[int, int]]:
    """Runs of consecutive numbers: [1, 2, 3, 7, 8] -> [(1, 3), (7, 8)]."""
    out = []
    for f in sorted(set(frames)):
        if out and f == out[-1][1] + 1:
            out[-1] = (out[-1][0], f)
        else:
            out.append((f, f))
    return out


def box_size(text: str, px: int) -> tuple[int, int]:
    """Estimated size in pixels of a label box for the text at ``px`` letter height."""
    lines = [ln for ln in text.split("\n")] or [""]
    width = max(len(ln) for ln in lines) * 0.58 * px
    pad = 0.55 * px
    return max(8, round(width + 2 * pad)), max(8, round(len(lines) * 1.25 * px + 2 * pad))


def _overlap(a, b, gap: float = 0.0) -> bool:
    return not (a[0] + a[2] + gap <= b[0] or b[0] + b[2] + gap <= a[0] or a[1] + a[3] + gap <= b[1]
                or b[1] + b[3] + gap <= a[1])


def _overlap_area(a, b) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def place_boxes(sizes, anchors, canvas, outline=None, manual=None, margin: float = 0.03):
    """Boxes (x, y, w, h from the bottom-left) for labels with the given ``sizes`` [(w, h)] and anchor
    points [(x, y)]: beside the model (``outline`` = (x0, y0, x1, y1) of the machine in the picture),
    on the side of the anchor, as near as possible to its height and never overlapping each other.
    ``manual``: per label None or a box position (x, y) to keep. Labels are placed from the top down."""
    W, H = canvas
    m = round(margin * min(W, H))
    n = len(sizes)
    manual = manual or [None] * n
    boxes: list = [None] * n
    for i in range(n):
        if manual[i] is not None:
            w, h = sizes[i]
            boxes[i] = (round(max(0, min(W - w, manual[i][0]))), round(max(0, min(H - h, manual[i][1]))), w, h)
    order = sorted((i for i in range(n) if boxes[i] is None), key=lambda i: -anchors[i][1])
    gap = 0.02 * min(W, H)
    rect_outline = None if outline is None else (outline[0], outline[1], outline[2] - outline[0],
                                                 outline[3] - outline[1])
    for i in order:
        w, h = sizes[i]
        ax, ay = anchors[i]
        if outline is not None:
            centre = (outline[0] + outline[2]) / 2
            left_x = max(m, outline[0] - gap - w)
            right_x = min(W - m - w, outline[2] + gap)
        else:
            centre = W / 2
            left_x, right_x = m, W - m - w
        prefer_left = ax < centre
        xs = [(left_x, 0 if prefer_left else 1), (right_x, 1 if prefer_left else 0)]
        xs += [(ax - w - gap, 2), (ax + gap, 2), (ax - w / 2, 3)]         # next to the point, when there is no room
        step = h * 1.15
        wanted = ay - h / 2
        best = None
        for x, kind in xs:
            x = max(m, min(W - m - w, x))
            for k in range(0, int((H - 2 * m) / step) + 2):
                for sign in ((0,) if k == 0 else (1, -1)):
                    y = max(m, min(H - m - h, wanted + sign * k * step))
                    box = (round(x), round(y), w, h)
                    if any(b is not None and _overlap(box, b, 0.04 * h) for b in boxes):
                        continue
                    if _overlap(box, (ax - gap / 2, ay - gap / 2, gap, gap)):
                        continue                                          # never on top of its own point
                    cost = abs(y - wanted) + kind * H * 0.25
                    if kind >= 2:
                        cost += abs(x + w / 2 - ax) * 0.5
                    if rect_outline is not None:
                        cost += _overlap_area(box, rect_outline) / max(1.0, w) * 4
                    if best is None or cost < best[0]:
                        best = (cost, box)
        boxes[i] = best[1] if best else (round(max(0, min(W - w, ax + gap))), round(max(0, min(H - h, ay))), w, h)
    return boxes


def line_end(box, anchor):
    """Where the line touches the box: the middle of the side that faces the anchor."""
    x, y, w, h = box
    ax, ay = anchor
    cx, cy = x + w / 2, y + h / 2
    dx, dy = ax - cx, ay - cy
    if abs(dx) * h >= abs(dy) * w:               # the anchor is more to the side than above or below
        return (x + w if dx > 0 else x), min(max(ay, y + h * 0.2), y + h * 0.8)
    return min(max(ax, x + w * 0.2), x + w * 0.8), (y + h if dy > 0 else y)


# ---------------------------------------------------------------------------
# drawing the lines
# ---------------------------------------------------------------------------


def _over(buf: np.ndarray, cover: np.ndarray, rgb, alpha: float, window) -> None:
    """Source-over of a colour with the coverage ``cover`` (0..1) onto the straight-alpha RGBA ``buf``."""
    y0, y1, x0, x1 = window
    region = buf[y0:y1, x0:x1]
    a_src = cover * alpha
    a_dst = region[..., 3]
    a_out = a_src + a_dst * (1 - a_src)
    safe = np.where(a_out > 1e-6, a_out, 1.0)
    for c in range(3):
        region[..., c] = (np.broadcast_to(rgb[c], a_src.shape) * a_src
                          + region[..., c] * a_dst * (1 - a_src)) / safe
    region[..., 3] = a_out


def draw_line(buf: np.ndarray, p0, p1, width: float, rgb, outline_rgb, alpha: float = 1.0,
              dot: float = 0.0) -> None:
    """A line from ``p0`` (the box) to ``p1`` (the part) with a dark outline, and a dot at ``p1``.
    ``buf``: float RGBA (height, width, 4), straight alpha, y from the bottom; drawn in place.
    ``alpha`` fades the whole drawing (line and outline together)."""
    H, W = buf.shape[:2]
    pad = width * 2 + dot + 3
    x0, x1 = int(max(0, math.floor(min(p0[0], p1[0]) - pad))), int(min(W, math.ceil(max(p0[0], p1[0]) + pad)))
    y0, y1 = int(max(0, math.floor(min(p0[1], p1[1]) - pad))), int(min(H, math.ceil(max(p0[1], p1[1]) + pad)))
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1]
    px, py = xs + 0.5, ys + 0.5
    ax, ay = p0
    bx, by = p1
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / length2, 0, 1) if length2 > 0 else np.zeros_like(px)
    d_line = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
    d_dot = np.hypot(px - bx, py - by)
    patch = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.float32)
    for rgb_c, extra in ((outline_rgb, 1.2), (rgb, 0.0)):
        cover = np.clip(width / 2 + extra + 0.5 - d_line, 0, 1)
        if dot > 0:
            cover = np.maximum(cover, np.clip(dot + extra + 0.5 - d_dot, 0, 1))
        _over(patch, cover, rgb_c, 1.0, (0, y1 - y0, 0, x1 - x0))
    _over_patch(buf, patch, alpha, (y0, y1, x0, x1))


def _over_patch(buf: np.ndarray, patch: np.ndarray, alpha: float, window) -> None:
    y0, y1, x0, x1 = window
    region = buf[y0:y1, x0:x1]
    a_src = patch[..., 3] * alpha
    a_dst = region[..., 3]
    a_out = a_src + a_dst * (1 - a_src)
    safe = np.where(a_out > 1e-6, a_out, 1.0)
    for c in range(3):
        region[..., c] = (patch[..., c] * a_src + region[..., c] * a_dst * (1 - a_src)) / safe
    region[..., 3] = a_out
