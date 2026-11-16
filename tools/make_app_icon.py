"""Makes the Fresing Render app icon and the splash screen from the owner's logo pack (task 0169).

    python tools/make_app_icon.py           # writes both files
    python tools/make_app_icon.py --check   # exit 1 when a written file differs from what this script makes

Inputs (copied from the owner's logo pack "Logo.zip", 16 Nov 2026; the logo is public on the site already):
    tools/brand/fresing-logo_compact_reversed.svg   the word mark's outlines: the icon's "Fr" (F + swoosh, r)
    tools/brand/fresing-logo_full_reversed_2400px.png   the word mark with its green line, for a dark ground
    site/fonts/IBMPlexSans-*.woff2                  the site's font (OFL)

Outputs:
    fresing_render/brand/fresing-render.ico   16, 20, 24, 32, 40, 48, 64, 256 px: "Fr" for Fresing Render (the
        word mark's first two letters, green swoosh) on the app icon's dark rounded square. 32 px and up are a 512 px
        drawing averaged down; 16, 20 and 24 px are drawn on whole pixels (strokes at least 2 px, gaps 1 px). 256 is stored
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
LOGO_SVG = os.path.join(BRAND, "fresing-logo_compact_reversed.svg")
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

# "Fr" (owner, 16 Nov 2026): the first two letters of the word mark - the F with its green swoosh, and the r - read
# from the pack's compact reversed logo (its coordinates: x 0 .. 316.5, y 0 .. 242 for these two letters). They are
# scaled by FR_SCALE and moved by FR_AT into the 512 px square.
FR_WIDTH = 372.0                        # px of 512
FR_SCALE = FR_WIDTH / 316.5
FR_AT = ((512 - FR_WIDTH) / 2, (512 - 242 * FR_SCALE) / 2)
# the same letters as rectangles for 16 / 20 / 24 px (logo coordinates: x0, x1, y0, y1)
R_SWOOSH = (0.0, 181.0, 0.0, 49.0)      # the slanted end taken at its middle
R_F_STEM = (0.0, 38.5, 60.0, 242.0)
R_F_MID = (38.5, 159.0, 102.0, 137.0)
R_R_STEM = (193.5, 228.5, 71.0, 242.0)
R_R_TOP = (193.5, 310.0, 71.0, 101.0)


def _logo_paths() -> tuple[str, str, str]:
    """The swoosh, the F and the r: path data out of the pack's SVG (the F and r are the letters' first two parts)."""
    import re
    text = open(LOGO_SVG, encoding="utf-8").read()
    swoosh = re.search(r'id="swoosh"[^>]*\sd="([^"]+)"', text).group(1)
    letters = re.search(r'id="letters"[^>]*\sd="([^"]+)"', text).group(1)
    parts = ["M" + p.strip() for p in letters.split("M") if p.strip()]
    return swoosh, parts[0], parts[1]


def _arc(p0, rx, ry, rot, large, sweep, p1, steps=48):
    """Points of an SVG elliptic arc (endpoint form, W3C SVG appendix B.2.4)."""
    import math
    x1, y1 = p0
    x2, y2 = p1
    phi = math.radians(rot)
    c, s_ = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = c * dx + s_ * dy, -s_ * dx + c * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    k = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cxp, cyp = k * rx * yp / ry, -k * ry * xp / rx
    cx, cy = c * cxp - s_ * cyp + (x1 + x2) / 2, s_ * cxp + c * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, steps + 1):
        t = t1 + dt * i / steps
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        out.append((c * ex - s_ * ey + cx, s_ * ex + c * ey + cy))
    return out


def _polygon(d: str) -> list[tuple[float, float]]:
    """One closed SVG path of absolute M / L / H / V / A commands as a list of points."""
    import re
    tok = re.findall(r"[MLHVAZ]|-?[\d.]+", d)
    pts, i, cmd = [], 0, ""
    while i < len(tok):
        if tok[i].isalpha():
            cmd = tok[i]
            i += 1
            if cmd == "Z":
                continue
        if cmd in "ML":
            pts.append((float(tok[i]), float(tok[i + 1])))
            i += 2
        elif cmd == "H":
            pts.append((float(tok[i]), pts[-1][1]))
            i += 1
        elif cmd == "V":
            pts.append((pts[-1][0], float(tok[i])))
            i += 1
        elif cmd == "A":
            rx, ry, rot, large, sweep, x, y = (float(t) for t in tok[i:i + 7])
            pts += _arc(pts[-1], rx, ry, rot, int(large), int(sweep), (x, y))
            i += 7
        else:
            raise ValueError(f"path command {cmd!r} not handled")
    return pts


def _square(size: int) -> Image.Image:
    """The dark rounded square, smoothed edges (drawn 8 x larger, scaled down)."""
    big = size * 8
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=CORNER * big, fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    img = Image.new("RGBA", (size, size), DARK + (0,))
    img.putalpha(mask)
    return img


def master_icon() -> Image.Image:
    """The 512 px icon: the letters drawn 4 x larger from the logo's outlines, averaged down."""
    k = 4
    img = _square(512 * k)
    d = ImageDraw.Draw(img)
    swoosh, f, r = _logo_paths()
    ox, oy = FR_AT
    for path, colour in ((swoosh, GREEN), (f, WHITE), (r, WHITE)):
        pts = [((ox + x * FR_SCALE) * k, (oy + y * FR_SCALE) * k) for x, y in _polygon(path)]
        d.polygon(pts, fill=colour + (255,))
    return img.resize((512, 512), Image.BOX)


def _snap(a: float, b: float, scale: float, least: int = 2) -> tuple[int, int]:
    """An edge pair on whole pixels: the start rounded, the thickness rounded but at least ``least``."""
    start = round(a * scale)
    return start, start + max(least, round((b - a) * scale))


def small_icon(size: int) -> Image.Image:
    """16 / 20 / 24 px: the Fr drawn on whole pixels (strokes at least 2 px, 1 px gaps) so it stays sharp."""
    s = size / 512 * FR_SCALE
    ox, oy = FR_AT[0] * size / 512, FR_AT[1] * size / 512

    def box(rect, least=2):
        x0, x1 = _snap(rect[0] + ox / s, rect[1] + ox / s, s, least)
        y0, y1 = _snap(rect[2] + oy / s, rect[3] + oy / s, s, least)
        return [x0, x1, y0, y1]
    sw, fs, fm, rs, rt = (box(r) for r in (R_SWOOSH, R_F_STEM, R_F_MID, R_R_STEM, R_R_TOP))
    fs[2] = max(fs[2], sw[3] + 1)                    # a gap of at least 1 px under the swoosh
    fm[0] = fs[1]
    fm[2] = max(fm[2], fs[2] + 1)
    fm[3] = max(fm[3], fm[2] + 2)
    rs[0] = max(rs[0], fm[1] + 1)                    # the r stands apart from the F's middle bar
    rs[1] = max(rs[1], rs[0] + 2)
    rt[0] = rs[0]
    rt[2] = rs[2] = max(rs[2], sw[3] + 1)
    rt[3] = max(rt[3], rt[2] + 2)
    rt[1] = min(max(rt[1], rs[1] + 2), size - 2)
    rs[3] = fs[3]
    img = _square(size)
    d = ImageDraw.Draw(img)
    # PIL's rectangle includes its last pixel: x1 - 1, y1 - 1
    for (x0, x1, y0, y1), colour in ((sw, GREEN), (fs, WHITE), (fm, WHITE), (rs, WHITE), (rt, WHITE)):
        d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=colour + (255,))
    return img


def icon_images() -> dict[int, Image.Image]:
    master = master_icon()
    out = {}
    for size in SIZES:
        out[size] = small_icon(size) if size in SMALL else master.resize((size, size), Image.BOX)
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
