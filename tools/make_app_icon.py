"""Makes the Fresing Render app icon and the splash screen from the owner's logo pack (task 0169).

    python tools/make_app_icon.py           # writes both files
    python tools/make_app_icon.py --check   # exit 1 when a written file differs from what this script makes

Inputs (copied from the owner's logo pack "Logo.zip", 16 Nov 2026; the logo is public on the site already):
    tools/brand/fresing-app-icon_512px.png          dark rounded square, green + white F
    tools/brand/fresing-logo_full_reversed_2400px.png   the word mark with its green line, for a dark ground
    site/fonts/IBMPlexSans-*.woff2                  the site's font (OFL)

Outputs:
    fresing_render/brand/fresing-render.ico   16, 20, 24, 32, 40, 48, 64, 256 px. 32 px and up are the pack's
        512 px icon scaled down; 16, 20 and 24 px are drawn on whole pixels (the F's stem, its green bar and its
        middle bar at least 2 px thick, a gap of at least 1 px under the bar) so the F stays sharp. 256 is stored
        as PNG, the others as 32-bit bitmaps (every Windows version and LoadImage read those).
    app_template/fresing_render/splash.png    1000 x 500 (Blender 5.2.3 reads only splash.png, no _2x)

Only Pillow and NumPy (tools/requirements-dev.txt).
"""

from __future__ import annotations

import io
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = os.path.join(ROOT, "tools", "brand")
ICON_SRC = os.path.join(BRAND, "fresing-app-icon_512px.png")
LOGO_SRC = os.path.join(BRAND, "fresing-logo_full_reversed_2400px.png")
FONTS = os.path.join(ROOT, "site", "fonts")
ICO_OUT = os.path.join(ROOT, "fresing_render", "brand", "fresing-render.ico")
SPLASH_OUT = os.path.join(ROOT, "app_template", "fresing_render", "splash.png")

SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
SMALL = (16, 20, 24)                    # drawn on whole pixels
DARK = (0x1A, 0x20, 0x27)
GREEN = (0x47, 0x9B, 0x29)
WHITE = (0xFF, 0xFF, 0xFF)
CORNER = 112 / 512                      # the rounded square's corner radius (site/brand/fresing-app-icon.svg)

# The F in the 512 px icon (site/brand/fresing-app-icon.svg: the symbol scaled by 1.23967 and moved by
# (79.66, 94.84)): x0, x1, y0, y1 of the green bar, the stem and the middle bar.
F_BAR = (138.6, 373.5, 106.0, 166.7)
F_STEM = (138.5, 186.3, 180.4, 406.0)
F_MID = (186.3, 345.0, 232.4, 275.8)


def _square(size: int) -> Image.Image:
    """The dark rounded square, smoothed edges (drawn 8 x larger, scaled down)."""
    big = size * 8
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=CORNER * big, fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    img = Image.new("RGBA", (size, size), DARK + (0,))
    img.putalpha(mask)
    return img


def _snap(a: float, b: float, scale: float, least: int = 2) -> tuple[int, int]:
    """An edge pair on whole pixels: the start rounded, the thickness rounded but at least ``least``."""
    start = round(a * scale)
    return start, start + max(least, round((b - a) * scale))


def small_icon(size: int) -> Image.Image:
    """16 / 20 / 24 px: the F drawn on whole pixels so it does not blur into the square."""
    s = size / 512
    img = _square(size)
    d = ImageDraw.Draw(img)
    sx0, sx1 = _snap(F_STEM[0], F_STEM[1], s)
    by0, by1 = _snap(F_BAR[2], F_BAR[3], s)
    bx1 = round(F_BAR[1] * s)
    sy0 = max(round(F_STEM[2] * s), by1 + 1)        # a gap of at least 1 px under the green bar
    sy1 = round(F_STEM[3] * s)
    my0, my1 = _snap(F_MID[2], F_MID[3], s)
    my0, my1 = max(my0, sy0), max(my1, sy0 + 2)
    mx1 = round(F_MID[1] * s)
    # PIL's rectangle includes its last pixel: x1 - 1, y1 - 1
    d.rectangle((sx0, by0, bx1 - 1, by1 - 1), fill=GREEN + (255,))
    d.rectangle((sx0, sy0, sx1 - 1, sy1 - 1), fill=WHITE + (255,))
    d.rectangle((sx1, my0, mx1 - 1, my1 - 1), fill=WHITE + (255,))
    return img


def icon_images() -> dict[int, Image.Image]:
    src = Image.open(ICON_SRC).convert("RGBA")
    out = {}
    for size in SIZES:
        out[size] = small_icon(size) if size in SMALL else src.resize((size, size), Image.BOX)
    return out


def _bmp_entry(img: Image.Image) -> bytes:
    """A 32-bit BGRA bitmap as an .ico entry: header (height doubled), rows bottom-up, the AND mask."""
    w, h = img.size
    a = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    bgra = a[::-1, :, [2, 1, 0, 3]].tobytes()
    row = ((w + 31) // 32) * 4
    mask = bytearray()
    for y in range(h - 1, -1, -1):
        bits = np.packbits(a[y, :, 3] == 0)          # 1 = see-through
        mask += bits.tobytes() + b"\0" * (row - len(bits))
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(bgra) + len(mask), 0, 0, 0, 0)
    return header + bgra + bytes(mask)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ico_bytes(images: dict[int, Image.Image]) -> bytes:
    sizes = sorted(images)
    blobs = [_png(images[s]) if s >= 256 else _bmp_entry(images[s]) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s, blob in zip(sizes, blobs):
        dim = 0 if s >= 256 else s
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    return out + b"".join(blobs)


def splash() -> Image.Image:
    """1000 x 500: the dark ground of the old splash, the full logo (its green line is the accent bar),
    "Fresing Render" and the subtitle."""
    w, h = 1000, 500
    top, bottom = np.array((0x18, 0x1C, 0x21), float), np.array((0x25, 0x2B, 0x33), float)
    t = np.linspace(0, 1, h)[:, None, None]
    ground = np.broadcast_to(top + (bottom - top) * t, (h, w, 3)).round().astype(np.uint8)
    img = Image.fromarray(np.ascontiguousarray(ground), "RGB").convert("RGBA")
    logo = Image.open(LOGO_SRC).convert("RGBA")
    lw = 420
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    x0, y0 = 64, 150
    img.alpha_composite(logo, (x0, y0))
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(os.path.join(FONTS, "IBMPlexSans-SemiBold-Latin1.woff2"), 50)
    sub = ImageFont.truetype(os.path.join(FONTS, "IBMPlexSans-Regular-Latin1.woff2"), 24)
    ty = y0 + logo.height + 34
    d.text((x0 - 3, ty), "Fresing Render", font=title, fill=(0xF2, 0xF2, 0xF2, 255))
    d.text((x0, ty + 70), "Photo-realistic renders of large STEP assemblies", font=sub,
           fill=(0xB4, 0xB9, 0xBF, 255))
    return img.convert("RGB")


def outputs() -> dict[str, bytes]:
    return {ICO_OUT: ico_bytes(icon_images()), SPLASH_OUT: _png(splash())}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = 0
    for path, data in outputs().items():
        rel = os.path.relpath(path, ROOT)
        old = open(path, "rb").read() if os.path.isfile(path) else b""
        if old == data:
            print("up to date:", rel)
        elif check:
            print("DIFFERS (run python tools/make_app_icon.py):", rel)
            bad += 1
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
            print(f"wrote {rel} ({len(data):,} bytes)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
