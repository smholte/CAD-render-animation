"""Study 0311: the page's design sketch and the painted map (Pillow + the terrain arrays; no Blender).

    ~/venv/bin/python tools/surroundings_proto/sketch.py --out DIR --view RENDER.jpg

map.png     the prototype's terrain from above as the maker would show it in its Map view: the paint layers'
            colours, height lines every metre, the road, the pond, where trees / bushes / rocks are painted, the pad
mockup.png  the Surroundings maker window: a picture of the 3D view (a render) with the brush, and the tool panel
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

COLOURS = {"grass": (120, 150, 70), "gravel": (170, 165, 150), "sand": (225, 205, 150), "asphalt": (60, 60, 62),
           "concrete": (195, 195, 190), "rock": (120, 115, 110), "mud": (110, 80, 55), "snow": (245, 245, 250)}


def font(size, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def painted_map(out, px=900):
    import scene as SC     # noqa: needs bpy only for imports at module level
    T, line = SC.make_terrain(len(SC.STAGES) - 1)
    img = np.zeros(T.h.shape + (3,))
    for name, a in T.layers.items():
        img += a[..., None] * np.array(COLOURS[name])
    # hill shading
    gy, gx = np.gradient(T.h, T.step)
    shade = np.clip(0.85 + 0.35 * (-gx * 0.6 + gy * 0.6) / np.sqrt(1 + gx ** 2 + gy ** 2), 0.55, 1.15)
    img *= shade[..., None]
    dep = T.depth()
    wet = dep > 0
    water = np.array((40, 80, 110)) * (1 - np.clip(dep, 0, 2)[..., None] / 4)
    img = np.where(wet[..., None], water, img)
    # contour lines every metre
    c = np.floor(T.h)
    edge = (c[1:, :-1] != c[:-1, :-1]) | (c[:-1, 1:] != c[:-1, :-1])
    img[:-1, :-1][edge & ~wet[:-1, :-1]] *= 0.75
    im = Image.fromarray(np.clip(img[::-1], 0, 255).astype(np.uint8)).resize((px, px), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    s = px / (2 * T.half)

    def P(x, y):
        return ((x + T.half) * s, (T.half - y) * s)
    # painted scatter: dots where the density is high (a sample)
    rng = np.random.default_rng(2)
    for kind, col, r, dens in (("tree", (30, 80, 30, 230), 5, 0.006), ("bush", (60, 120, 40, 230), 3, 0.05),
                               ("rock", (90, 90, 90, 230), 2, 0.05)):
        D = T.density(kind)
        cells = np.argwhere(rng.random(D.shape) < D * dens)
        for i, j in cells:
            x, y = P(T.X[i, j], T.Y[i, j])
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    x0, x1, y0, y1 = T.pad
    d.rectangle((*P(x0, y1), *P(x1, y0)), outline=(220, 40, 40, 255), width=3)
    d.text(P(x0, y1 + 3), "machine's pad (kept flat and free)", fill=(140, 20, 20, 255), font=font(15, True))
    pts = [P(p[0], p[1]) for p in line[::4]]
    d.line(pts, fill=(255, 255, 255, 180), width=1)
    for (x, y), label in (((-42, 44), "hall"), ((44, 16), "office"), ((-58, 12), "workshop"), ((8, 92), "pond"),
                          ((-90, 104), "trees (painted)"), ((-55, 74), "rocks"), ((-24, 18), "sand"),
                          ((80, -50), "road (a line, cut / fill)")):
        d.text(P(x, y), label, fill=(20, 20, 20, 255), font=font(15, True), anchor="mm",
               stroke_width=3, stroke_fill=(255, 255, 255, 200))
    # legend
    lx, ly = 10, px - 10 - 22 * 8
    d.rectangle((lx - 4, ly - 6, lx + 150, px - 4), fill=(255, 255, 255, 210))
    for k, name in enumerate(("grass", "gravel", "sand", "asphalt", "concrete", "rock", "mud")):
        d.rectangle((lx, ly + 22 * k, lx + 18, ly + 22 * k + 16), fill=COLOURS[name] + (255,), outline=(0, 0, 0, 255))
        d.text((lx + 26, ly + 22 * k), name, fill=(0, 0, 0, 255), font=font(14))
    d.text((lx, ly + 22 * 7), "water", fill=(40, 80, 110, 255), font=font(14, True))
    d.text((px - 10, px - 10), "260 m x 260 m · lines every 1 m of height", fill=(0, 0, 0, 255), font=font(13), anchor="rb",
           stroke_width=2, stroke_fill=(255, 255, 255, 200))
    im.save(os.path.join(out, "map.png"))


def mockup(out, view):
    W, H = 1500, 880
    im = Image.new("RGB", (W, H), (38, 40, 44))
    d = ImageDraw.Draw(im, "RGBA")
    # title bar + tabs
    d.rectangle((0, 0, W, 36), fill=(28, 29, 32))
    d.text((14, 9), "Surroundings maker", fill=(235, 235, 235), font=font(16, True))
    tabs = ["Start", "Ground", "Paint", "Plants & rocks", "Buildings", "Roads", "Water", "Save as preset"]
    x = 230
    for k, t in enumerate(tabs):
        w = d.textlength(t, font=font(14)) + 24
        d.rounded_rectangle((x, 6, x + w, 31), 6, fill=(71, 155, 41) if k == 2 else (55, 57, 62))
        d.text((x + 12, 11), t, fill=(255, 255, 255), font=font(14))
        x += w + 6
    d.text((W - 16, 10), "Simple  |  More", fill=(200, 200, 200), font=font(14), anchor="ra")
    # the 3D view
    vw, vh = 1080, 608
    pic = Image.open(view).convert("RGB").resize((vw, vh), Image.LANCZOS)
    im.paste(pic, (10, 46))
    cx, cy, r = 10 + vw * 0.33, 46 + vh * 0.78, 60
    d.ellipse((cx - r, cy - r * 0.45, cx + r, cy + r * 0.45), outline=(255, 255, 255, 230), width=3)
    d.ellipse((cx - r * 0.6, cy - r * 0.27, cx + r * 0.6, cy + r * 0.27), outline=(255, 255, 255, 120), width=2)
    d.text((cx + r + 8, cy - 10), "brush: Gravel · 6 m · 80 %", fill=(255, 255, 255), font=font(14, True),
           stroke_width=2, stroke_fill=(0, 0, 0))
    # view buttons
    for k, t in enumerate(("3D", "Map", "Through the camera")):
        d.rounded_rectangle((20 + 150 * k, 56, 160 + 150 * k, 82), 5, fill=(0, 0, 0, 140))
        d.text((90 + 150 * k, 69), t, fill=(255, 255, 255), font=font(13), anchor="mm")
    # the panel
    px0 = 1100
    d.rectangle((px0, 46, W - 10, H - 10), fill=(48, 50, 55))
    y = 58

    def head(t):
        nonlocal y
        d.text((px0 + 14, y), t, fill=(235, 235, 235), font=font(15, True))
        y += 28

    def row(t, value=None, hi=False):
        nonlocal y
        d.rounded_rectangle((px0 + 14, y, W - 24, y + 26), 5, fill=(71, 155, 41) if hi else (62, 65, 71))
        d.text((px0 + 24, y + 5), t, fill=(255, 255, 255), font=font(13))
        if value:
            d.text((W - 34, y + 5), value, fill=(220, 220, 220), font=font(13), anchor="ra")
        y += 32
    head("Paint the ground")
    sw = [("grass", "Grass"), ("gravel", "Gravel"), ("sand", "Sand"), ("asphalt", "Asphalt"), ("concrete", "Concrete"),
          ("rock", "Rock"), ("mud", "Mud"), ("snow", "Snow")]
    for k, (key, label) in enumerate(sw):
        cx0 = px0 + 14 + (k % 4) * 94
        cy0 = y + (k // 4) * 64
        d.rounded_rectangle((cx0, cy0, cx0 + 86, cy0 + 56), 6, fill=COLOURS[key],
                            outline=(255, 255, 255) if key == "gravel" else (30, 30, 30), width=3 if key == "gravel" else 1)
        d.text((cx0 + 43, cy0 + 46), label, fill=(0, 0, 0) if key not in ("asphalt", "rock", "mud") else (255, 255, 255),
               font=font(12, True), anchor="mm")
    y += 136
    row("Brush size", "6 m")
    row("Strength", "80 %")
    row("Edge", "natural")
    row("Erase (back to grass)")
    y += 8
    head("What grows on it")
    row("Plants follow the ground", "on", True)
    row("Grass", "dense")
    row("Trees and bushes: paint them", "Plants & rocks ›")
    y += 8
    head("Look")
    row("Ground made by", "the app (no tiles)")
    row("or photo ground", "from the library")
    # status line
    d.rectangle((10, 46 + vh + 8, 10 + vw, H - 10), fill=(48, 50, 55))
    d.text((24, 46 + vh + 20), "Start: pick a preset, then change what you want.", fill=(235, 235, 235),
           font=font(15, True))
    pres = ["Building site", "Onshore wind farm", "Industrial yard", "Road & crossroads", "Harbour", "Beach at sunset",
            "Meadow", "Forest edge"]
    for k, t in enumerate(pres):
        x0 = 24 + (k % 4) * 262
        y0 = 46 + vh + 52 + (k // 4) * 82
        d.rounded_rectangle((x0, y0, x0 + 250, y0 + 72), 8, fill=(62, 65, 71), outline=(90, 92, 98))
        d.rounded_rectangle((x0 + 6, y0 + 6, x0 + 96, y0 + 66), 5, fill=(90 + 12 * k, 120, 90))
        d.text((x0 + 106, y0 + 26), t, fill=(255, 255, 255), font=font(13, True))
    im.save(os.path.join(out, "mockup.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--view", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    painted_map(a.out)
    mockup(a.out, a.view)


if __name__ == "__main__":
    main()
