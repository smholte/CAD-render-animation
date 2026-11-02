"""Output size presets: format by use x resolution, and paper sizes by DPI."""

from __future__ import annotations

from dataclasses import dataclass

# Formats named by use. kind "screen": aspect ratio (landscape, w:h);
# kind "paper": ISO paper size in mm (portrait w x h).
FORMATS: dict[str, dict] = {
    "presentation": dict(label="Presentation 16:9", kind="screen", aspect=(16, 9)),
    "widescreen": dict(label="Widescreen 21:9", kind="screen", aspect=(21, 9)),
    "classic": dict(label="Classic 4:3", kind="screen", aspect=(4, 3)),
    "photo": dict(label="Photo 3:2", kind="screen", aspect=(3, 2)),
    "square": dict(label="Website square 1:1", kind="screen", aspect=(1, 1)),
    "social": dict(label="Social story 9:16", kind="screen", aspect=(9, 16)),
    "web_banner": dict(label="Web banner 3:1", kind="screen", aspect=(3, 1)),
    "brochure_a4": dict(label="Brochure A4", kind="paper", paper=(210, 297)),
    "flyer_a5": dict(label="Flyer A5", kind="paper", paper=(148, 210)),
    "poster_a3": dict(label="Poster A3", kind="paper", paper=(297, 420)),
    "poster_a2": dict(label="Poster A2", kind="paper", paper=(420, 594)),
    "letter": dict(label="US Letter", kind="paper", paper=(215.9, 279.4)),
    "custom": dict(label="Custom size", kind="custom"),
}

# Resolution classes for screen formats: pixels on the SHORT edge.
RESOLUTIONS: dict[str, dict] = {
    "preview": dict(label="Preview (540p)", short=540),
    "hd": dict(label="HD (1080p)", short=1080),
    "qhd": dict(label="QHD (1440p)", short=1440),
    "4k": dict(label="4K (2160p)", short=2160),
    "8k": dict(label="8K (4320p)", short=4320),
}

DPI_CHOICES = (150, 300)


@dataclass
class OutputSize:
    width: int
    height: int
    note: str

    @property
    def megapixels(self) -> float:
        return self.width * self.height / 1e6


def _even(x: float) -> int:
    """Round to an even number (video encoders like even sizes)."""
    n = int(round(x))
    return n + (n % 2)


def compute(fmt: str, resolution: str = "hd", orientation: str = "auto", dpi: int = 300,
            bleed_mm: float = 0.0, custom_w: int = 1920, custom_h: int = 1080) -> OutputSize:
    """Pixel size for a format.

    orientation: "auto" (format default), "landscape" or "portrait".
    For paper formats the size is paper (+ bleed on every side) at ``dpi``.
    """
    spec = FORMATS.get(fmt, FORMATS["presentation"])
    kind = spec["kind"]
    if kind == "custom":
        return OutputSize(max(16, int(custom_w)), max(16, int(custom_h)), "Custom size")

    if kind == "paper":
        w_mm, h_mm = spec["paper"]
        if orientation == "landscape":
            w_mm, h_mm = h_mm, w_mm
        w_mm += 2 * bleed_mm
        h_mm += 2 * bleed_mm
        w = round(w_mm / 25.4 * dpi)
        h = round(h_mm / 25.4 * dpi)
        note = f"{spec['label']} at {dpi} dpi"
        if bleed_mm:
            note += f", {bleed_mm:g} mm bleed"
        return OutputSize(w, h, note)

    aw, ah = spec["aspect"]
    if orientation == "portrait" and aw > ah or orientation == "landscape" and aw < ah:
        aw, ah = ah, aw
    short = RESOLUTIONS.get(resolution, RESOLUTIONS["hd"])["short"]
    if aw >= ah:
        h = short
        w = _even(short * aw / ah)
    else:
        w = short
        h = _even(short * ah / aw)
    return OutputSize(w, h, f"{spec['label']}, {RESOLUTIONS.get(resolution, RESOLUTIONS['hd'])['label']}")


def bleed_fraction(fmt: str, orientation: str, bleed_mm: float) -> tuple[float, float]:
    """Fraction of width/height that is bleed on each side (for frame guides)."""
    spec = FORMATS.get(fmt)
    if not spec or spec["kind"] != "paper" or not bleed_mm:
        return 0.0, 0.0
    w_mm, h_mm = spec["paper"]
    if orientation == "landscape":
        w_mm, h_mm = h_mm, w_mm
    return bleed_mm / (w_mm + 2 * bleed_mm), bleed_mm / (h_mm + 2 * bleed_mm)
