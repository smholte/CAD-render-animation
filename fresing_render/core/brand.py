"""Brand kits and video finishing: what goes on top of the rendered pictures (no Blender here).

A *brand kit* is a company's logo, two colours, a font and a contact line. Kits are stored one per
company in the shared library (folder "Brand kits": ``<name>.json`` plus the logo picture next to it);
every project keeps its own copy of the kit it uses, so it opens the same without the library.

The finishing plan turns the settings of an animation into a time line (title card, the animation,
end card) and a list of captions, all in frames, so the numbers can be tested on their own.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

FOLDER = "Brand kits"
LOGO_TYPES = (".png", ".jpg", ".jpeg")          # Blender cannot read SVG: export the logo as PNG
CORNERS = ("TL", "TR", "BL", "BR")

DEFAULT_COLOR_1 = "#14202E"                      # card background
DEFAULT_COLOR_2 = "#FFFFFF"                      # card text

CAPTION_MIN_SECONDS = 1.5
CAPTION_FADE_SECONDS = 0.3
CARD_FADE_SECONDS = 0.4


# ---------------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------------


def hex_to_rgb(text: str, default: str = DEFAULT_COLOR_1) -> tuple[float, float, float]:
    """'#RRGGBB' (or 'RRGGBB', '#RGB') as three values 0..1 (screen values). Bad text gives the default."""
    t = (text or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", t):
        t = "".join(ch * 2 for ch in t)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", t):
        t = default.lstrip("#")
    return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(float(c) * 255))):02X}" for c in rgb[:3])


# ---------------------------------------------------------------------------
# brand kits
# ---------------------------------------------------------------------------


@dataclass
class BrandKit:
    name: str
    logo: str = ""                  # file name of the logo picture in the kit's folder ("" = no logo)
    color1: str = DEFAULT_COLOR_1
    color2: str = DEFAULT_COLOR_2
    font: str = ""                  # path of a font file, "" = Blender's own
    contact: str = ""               # e.g. "fresing.nl · info@fresing.nl"

    def to_dict(self) -> dict:
        return {"name": self.name, "logo": self.logo, "color1": self.color1, "color2": self.color2,
                "font": self.font, "contact": self.contact}

    @classmethod
    def from_dict(cls, d: dict) -> "BrandKit":
        return cls(name=str(d.get("name", "")).strip() or "Brand kit", logo=str(d.get("logo", "")),
                   color1=str(d.get("color1", DEFAULT_COLOR_1)), color2=str(d.get("color2", DEFAULT_COLOR_2)),
                   font=str(d.get("font", "")), contact=str(d.get("contact", "")))


def safe_name(name: str) -> str:
    """A file name made from a kit name ('Fresing B.V.' -> 'Fresing_B.V')."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_.") or "kit"


def kit_files(folder: str, name: str) -> tuple[str, str]:
    """(json file, logo file stem) of a kit in a folder."""
    base = safe_name(name)
    return os.path.join(folder, base + ".json"), os.path.join(folder, base + "_logo")


def save_kit(folder: str, kit: BrandKit, logo_source: str = "") -> BrandKit:
    """Write a kit into the folder. ``logo_source``: a logo picture to copy in (else the old logo stays).
    Returns the kit as stored (``logo`` = the copied file's name)."""
    import shutil
    os.makedirs(folder, exist_ok=True)
    path, stem = kit_files(folder, kit.name)
    stored = BrandKit.from_dict(kit.to_dict())
    if logo_source:
        ext = os.path.splitext(logo_source)[1].lower()
        if ext not in LOGO_TYPES:
            raise ValueError("The logo must be a PNG or JPG picture (export SVG logos as PNG first)")
        if not os.path.isfile(logo_source):
            raise ValueError("The logo file cannot be found")
        target = stem + ext
        if os.path.abspath(logo_source) != os.path.abspath(target):
            shutil.copyfile(logo_source, target)
        for other in LOGO_TYPES:                      # one logo per kit
            if other != ext and os.path.exists(stem + other):
                os.remove(stem + other)
        stored.logo = os.path.basename(target)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(stored.to_dict(), fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return stored


def load_kit(folder: str, name: str) -> BrandKit | None:
    path, _ = kit_files(folder, name)
    try:
        with open(path, encoding="utf-8") as fh:
            return BrandKit.from_dict(json.load(fh))
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def list_kits(folder: str) -> list[BrandKit]:
    """All readable kits in the folder, by name. Damaged files are skipped."""
    kits = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return kits
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                kits.append(BrandKit.from_dict(json.load(fh)))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return sorted(kits, key=lambda k: k.name.lower())


def delete_kit(folder: str, name: str) -> bool:
    path, stem = kit_files(folder, name)
    gone = False
    for p in [path] + [stem + e for e in LOGO_TYPES]:
        if os.path.exists(p):
            os.remove(p)
            gone = True
    return gone


def logo_path(folder: str, kit: BrandKit) -> str:
    """Full path of the kit's logo, '' when it has none or the file is missing."""
    if not kit.logo:
        return ""
    p = os.path.join(folder, kit.logo)
    return p if os.path.isfile(p) else ""


# ---------------------------------------------------------------------------
# finishing: time line and captions
# ---------------------------------------------------------------------------


@dataclass
class Caption:
    text: str
    start: int          # first frame, counted from the first frame of the finished video (1-based)
    end: int            # last frame (inclusive)


@dataclass
class Finishing:
    """The finishing settings of one render (an animation or a still), already read from the scene."""
    logo_corner: str = "NONE"             # NONE / TL / TR / BL / BR
    logo_file: str = ""                   # full path of the logo picture
    logo_size: float = 0.12               # logo width as a part of the picture width
    title_on: bool = False
    title: str = ""
    subtitle: str = ""
    title_seconds: float = 3.0
    end_on: bool = False
    end_seconds: float = 3.0
    end_text: str = ""                    # contact line
    captions_on: bool = False
    color1: str = DEFAULT_COLOR_1
    color2: str = DEFAULT_COLOR_2
    font: str = ""
    watermark: str = ""                   # "" = no watermark
    watermark_size: float = 0.12          # text height as a part of the picture height
    watermark_opacity: float = 0.25
    # task 0025: labels pointing at parts, picture cards, music
    label_track: dict = field(default_factory=dict)   # {frame of the animation (1-based): [LabelDraw]}
    label_px: int = 0                     # text size of the labels in pixels
    label_dir: str = ""                   # folder for the line pictures (made when the video is built)
    cards: list = field(default_factory=list)         # [core.callouts.CardSpec]
    music: object = None                  # core.callouts.MusicSpec or None

    @property
    def active(self) -> bool:
        return bool(self.logo_corner in CORNERS and self.logo_file) or self.title_on or self.end_on \
            or self.captions_on or bool(self.watermark) or bool(self.label_track) or bool(self.cards) \
            or self.music is not None

    @property
    def logo_on(self) -> bool:
        return self.logo_corner in CORNERS and bool(self.logo_file)


@dataclass
class Plan:
    title_frames: int
    body_frames: int
    end_frames: int
    captions: list[Caption] = field(default_factory=list)
    music: object = None            # core.callouts.MusicPlan when the video has music (set when it is built)

    @property
    def total(self) -> int:
        return self.title_frames + self.body_frames + self.end_frames

    @property
    def body_start(self) -> int:
        return self.title_frames + 1

    @property
    def end_start(self) -> int:
        return self.title_frames + self.body_frames + 1


def seconds_to_frames(seconds: float, fps: int) -> int:
    return max(0, int(round(max(0.0, seconds) * fps)))


def caption_list(steps: list[tuple[str, float, float]], fps: int, offset_frames: int, body_frames: int,
                 ) -> list[Caption]:
    """Captions from animation steps.

    ``steps``: (label, start seconds, end seconds) of the steps that have a label, in any order.
    Each caption starts with its step and stays at least CAPTION_MIN_SECONDS (until the step ends,
    whichever is longer), but never into the next caption and never beyond the animation.
    Frames are counted from the first frame of the finished video: ``offset_frames`` is the title card.
    """
    items = sorted(((t.strip(), a, b) for t, a, b in steps if t and t.strip()), key=lambda x: (x[1], x[2]))
    out: list[Caption] = []
    min_frames = max(1, seconds_to_frames(CAPTION_MIN_SECONDS, fps))
    for i, (text, a, b) in enumerate(items):
        first = offset_frames + 1 + seconds_to_frames(a, fps)
        last = offset_frames + max(seconds_to_frames(b, fps), seconds_to_frames(a, fps) + min_frames)
        if i + 1 < len(items):
            nxt = offset_frames + 1 + seconds_to_frames(items[i + 1][1], fps)
            last = min(last, nxt - 1)
        last = min(last, offset_frames + body_frames)
        if first > offset_frames + body_frames or last < first:
            continue
        out.append(Caption(text, first, last))
    return out


def plan(fin: Finishing, body_frames: int, fps: int, steps: list[tuple[str, float, float]] | None = None) -> Plan:
    """Frames of the title card, the animation and the end card, and the captions."""
    title = seconds_to_frames(fin.title_seconds, fps) if fin.title_on else 0
    end = seconds_to_frames(fin.end_seconds, fps) if fin.end_on else 0
    caps = caption_list(steps or [], fps, title, body_frames) if fin.captions_on else []
    return Plan(title, body_frames, end, caps)


# ---------------------------------------------------------------------------
# finishing: where things go in the picture
# ---------------------------------------------------------------------------


def logo_box(corner: str, width: int, height: int, logo_w: int, logo_h: int, size: float = 0.12,
             margin: float = 0.03) -> tuple[int, int, int, int]:
    """(x, y, w, h) in pixels of the logo in a picture, y from the BOTTOM (Blender's way).

    The logo is ``size`` of the picture width wide (kept in proportion, and no taller than a quarter of
    the picture height), ``margin`` of the shorter side away from the edge."""
    logo_w = max(1, logo_w)
    logo_h = max(1, logo_h)
    w = size * width
    h = w * logo_h / logo_w
    limit = 0.25 * height
    if h > limit:
        h, w = limit, limit * logo_w / logo_h
    w, h = max(1, round(w)), max(1, round(h))
    m = round(margin * min(width, height))
    x = m if corner in ("TL", "BL") else width - m - w
    y = m if corner in ("BL", "BR") else height - m - h
    return x, y, w, h


def fit_logo(width: int, height: int, logo_w: int, logo_h: int, fraction: float) -> tuple[int, int, int, int]:
    """A logo centred in the picture, at most ``fraction`` of the width and of the height (x, y, w, h)."""
    logo_w = max(1, logo_w)
    logo_h = max(1, logo_h)
    scale = min(fraction * width / logo_w, fraction * height / logo_h)
    w, h = max(1, round(logo_w * scale)), max(1, round(logo_h * scale))
    return (width - w) // 2, (height - h) // 2, w, h


def card_font_size(height: int, factor: float) -> int:
    """Text size in pixels for a card: ``factor`` of the picture height."""
    return max(8, round(height * factor))


# ---------------------------------------------------------------------------
# framing when the shape changes
# ---------------------------------------------------------------------------

FIT_CROP = "CROP"          # keep what the 16:9 picture shows from top to bottom; narrower shapes lose the sides
FIT_EXTEND = "EXTEND"      # keep what the 16:9 picture shows from side to side; taller shapes show more above/below


def sensor_fit_for(mode: str) -> str:
    """Blender's camera sensor fit for the framing choice."""
    return "VERTICAL" if mode == FIT_CROP else "HORIZONTAL"


CROP_ASPECT = 9.0 / 16.0           # the 16:9 picture's height as a part of its width: what "Crop" keeps


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_linear(hex_color: str, default: str = DEFAULT_COLOR_1) -> tuple[float, float, float]:
    """A '#RRGGBB' colour as the scene-linear values Blender's strips want."""
    return tuple(srgb_to_linear(c) for c in hex_to_rgb(hex_color, default))


WATERMARK_WORDS = {"DRAFT": "DRAFT", "CONFIDENTIAL": "CONFIDENTIAL"}


def watermark_text(kind: str, custom: str) -> str:
    """The words of the watermark for the choice in the panel ('' = no text, so no watermark)."""
    if kind == "CUSTOM":
        return (custom or "").strip()
    return WATERMARK_WORDS.get(kind, "")


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def linear_to_hex(rgb) -> str:
    """Blender's colour boxes hold scene-linear values: '#RRGGBB' of what the box shows on screen."""
    return rgb_to_hex(tuple(linear_to_srgb(c) for c in rgb[:3]))
