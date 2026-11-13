"""Web 3D model with its surroundings (task 0106): the page's settings, pictures and HTML (no Blender).

Surroundings **None** keeps the model-viewer page of ``core/web3d.py``. With surroundings the page is plain three.js
(``fresing_render/web/three-viewer.min.js``, one global ``FRTHREE``) plus our own readable code (``fr_math.js``: the
sea's height and the vessel's motion, ``fr_page.js``: everything else). The page reads one JSON settings block
(``settings``), the model (base64 .glb) and up to two pictures (the sky's background JPEG and its light as a small
Radiance .hdr). Coordinates in the block are Blender's world (metres, z up); the page turns them into three's.

The sea and the vessel follow the app's own formulas (``sea_height``, ``vessel_matrix`` here; ``fr_math.js`` on the
page): tests compare all three.
"""

from __future__ import annotations

import base64
import glob
import html
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

from . import web3d

THREE_VERSION = "0.180.0"
THREE_FILE = "three-viewer.min.js"
MATH_FILE = "fr_math.js"
PAGE_FILE = "fr_page.js"
G = 9.81
SEA_RADIUS = 20000.0                 # m: the app's sea reaches this far (core/surroundings.SEA_RADIUS)
SEA_RIM = 400.0                      # m: ... and its edge rises this much (no gap under the horizon)

# Page quality: what the page does at each level. ``sky`` (px, width of the background picture) and ``light`` (px,
# width of the light picture) are written into the file; the rest the page sets itself, and Auto may step down.
QUALITY = {
    "PHONE": dict(seg=96, ripple=256, rain=1500, shadow=1024, pixel_ratio=1.0, sky=1024, light=128, spray=300),
    "BALANCED": dict(seg=192, ripple=512, rain=4000, shadow=2048, pixel_ratio=1.5, sky=2048, light=256, spray=600),
    "BEST": dict(seg=320, ripple=1024, rain=9000, shadow=4096, pixel_ratio=2.0, sky=4096, light=256, spray=1200),
}
LEVELS = ("PHONE", "BALANCED", "BEST")
CLOUDS = ("NONE", "SOME", "OVERCAST")
SKY_JPG_QUALITY = 84
AUTO_FPS = 30                        # Auto lowers the quality when the page cannot keep this many frames a second


# ---------------------------------------------------------------------------
# directions, the sea, the vessel (the same formulas as the app and fr_math.js)
# ---------------------------------------------------------------------------

def sun_vector(elevation_deg: float, rotation_deg: float) -> list[float]:
    """Direction towards the sun of the app's sky (Blender world, z up) for Sun height and Rotate light. Measured
    with Cycles (task 0106): rotation 0 puts the sun at +y, 90 at +x."""
    h, r = math.radians(elevation_deg), math.radians(rotation_deg)
    return [math.sin(r) * math.cos(h), math.cos(r) * math.cos(h), math.sin(h)]


def angles_of(v) -> tuple[float, float]:
    """(elevation, rotation) in degrees of a direction (the inverse of ``sun_vector``)."""
    x, y, z = (float(c) for c in v)
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    return math.degrees(math.asin(max(-1.0, min(1.0, z / n)))), math.degrees(math.atan2(x, y)) % 360.0


def _smoothstep01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def sea_fade(near: float, x, y):
    r = np.sqrt(np.asarray(x, float) ** 2 + np.asarray(y, float) ** 2)
    return 1.0 - _smoothstep01((r - near) / (0.6 * near))


def sea_height(sea: dict, x, y, t):
    """Height of the water above its level at (x, y) metres from the sea's origin, time ``t`` s (the app's waves)."""
    x, y, t = (np.asarray(v, float) for v in (x, y, t))
    h = np.zeros(np.broadcast(x, y, t).shape)
    fades = sea.get("fade") or [[0.0, 0.0]] * len(sea["waves"])
    for (a, dx, dy, k, ph), f in zip(sea["waves"], fades):
        h = h + a * np.sin(k * (dx * x + dy * y) + ph - math.sqrt(G * k) * t) * wave_fade(f, x, y)
    return h * sea_fade(sea["near"], x, y)


def wave_fade(f, x, y):
    """One wave's own fade (task 0109): 1 within f[0] m of the middle, 0 beyond f[1] (linear); [0, 0]: none."""
    if not f or f[1] <= 0.0:
        return 1.0
    r = np.sqrt(np.asarray(x, float) ** 2 + np.asarray(y, float) ** 2)
    return np.clip((f[1] - r) / (f[1] - f[0]), 0.0, 1.0)


def channel(ch, t):
    base, terms = ch
    t = np.asarray(t, float)
    v = np.full(t.shape, float(base))
    for a, w, p in terms:
        v = v + a * np.sin(p - w * t)
    return v


def vessel_matrix(v: dict, t: float, mode: str = "") -> np.ndarray:
    """4x4 (rows) of the vessel's motion at ``t``: T(p + heave z) Ry(pitch) Rx(roll) T(-p); LEVEL: heave only."""
    m = np.eye(4)
    if mode == "STILL":
        return m
    heave = float(channel(v["heave"], t))
    if mode == "LEVEL":
        m[2, 3] = heave
        return m
    r, q = float(channel(v["roll"], t)), float(channel(v["pitch"], t))
    rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    ry = np.array([[math.cos(q), 0, math.sin(q)], [0, 1, 0], [-math.sin(q), 0, math.cos(q)]])
    rot = ry @ rx
    p = np.asarray(v["pivot"], float)
    m[:3, :3] = rot
    m[:3, 3] = p + np.array([0.0, 0.0, heave]) - rot @ p
    return m


# ---------------------------------------------------------------------------
# what the owner picked -> the page's settings
# ---------------------------------------------------------------------------

def default_choice() -> dict:
    """Every item of the panel's fold, as a plain dict (the panel's ``env_*`` settings without the prefix)."""
    return dict(sea=False, sea_state="CALM", vessel=False, sky=True, sky_source="PROJECT", sun_height=45.0,
                sun_direction=0.0, clouds="NONE", haze=False, haze_strength=0.3, rain=False, rain_strength=0.5,
                shadows=True, quality="BALANCED", auto=True)


def haze_density(strength: float, size: float) -> float:
    """Exponential fog density (1/m): strength 0 … 1 brings the distance you see through from 20 km down to about
    four model sizes (at least 150 m)."""
    s = float(np.clip(strength, 0.0, 1.0))
    near = max(150.0, 4.0 * float(size))
    seen = math.exp(math.log(20000.0) * (1.0 - s) + math.log(near) * s)
    return 3.0 / seen


LIGHTS = ("SOFT", "ALL")             # baked light on the page (task 0107); "LIVE" = none
PLAIN_BG = "#F1F3F5"                 # the plain form's background: the model-viewer page's (core/web3d._PAGE)


def light_block(light: dict | None) -> dict | None:
    """The page's ``light`` entry: {light: SOFT | ALL, scale, curve, sun} (task 0107), None for no baked light.
    ``sun``: Cycles' sun / sky light on an open up-facing surface (ALL; 0 when the light has no separate sun)."""
    if not light or light.get("light", "LIVE") == "LIVE":
        return None
    kind = light["light"]
    if kind not in LIGHTS:
        raise ValueError(f"baked light must be one of {LIGHTS}, not {kind!r}")
    scale, curve = float(light.get("scale", 1.0)), float(light.get("curve", 2.0))
    if not (math.isfinite(scale) and scale > 0 and math.isfinite(curve) and curve > 0):
        raise ValueError(f"baked light: scale and curve must be above 0 (scale {scale}, curve {curve})")
    sun = float(light.get("sun", 0.0))
    if not (math.isfinite(sun) and sun >= 0):
        raise ValueError(f"baked light: sun must be 0 or more ({sun})")
    return {"light": kind, "scale": scale, "curve": curve, "sun": sun}


def settings(choice: dict, model_min, model_max, sea: dict | None = None, vessel: dict | None = None,
             sky: dict | None = None, time_start: float = 0.0, light: dict | None = None,
             plain: bool = False) -> dict:
    """The page's settings block. ``sea``: {state, level, origin, near, waves, own, bump, foam, moving} of the sea
    as the page should draw it (or None); ``vessel``: {pivot, heave, roll, pitch, bow, hull} (or None); ``sky``:
    {kind, sun, strength, exposure, photo, light, ...}.

    Task 0107: ``light`` = {light: SOFT | ALL, scale, curve} of the baked light in the model (the light factor is
    scale x texel ^ curve), None = nothing baked. ``plain``: Surroundings None with a baked choice – no sea, vessel
    motion, haze, rain or clouds, the model-viewer page's light background instead of the sky; the sky or the
    project's light picture still lights the model. Neither key is written when it is not asked for (the page of
    task 0106 stays as it was)."""
    q = choice.get("quality", "BALANCED")
    if q not in QUALITY:
        q = "BALANCED"
    mn, mx = [float(v) for v in model_min], [float(v) for v in model_max]
    size = max(mx[i] - mn[i] for i in range(3))
    sky = dict(sky or {})
    sky.setdefault("kind", "SKY")
    sky.setdefault("sun", sun_vector(45.0, 0.0))
    sky["clouds"] = choice.get("clouds", "NONE") if choice.get("clouds") in CLOUDS and not plain else "NONE"
    sky.setdefault("strength", 1.0)
    sky.setdefault("exposure", 0.0)
    el, az = angles_of(sky["sun"])
    sky["elevation"], sky["azimuth"] = el, az
    out = {
        "v": 1,
        "quality": q,
        "auto": bool(choice.get("auto", True)),
        "levels": {k: {n: v for n, v in QUALITY[k].items() if n not in ("sky", "light")} for k in LEVELS},
        "model": {"min": mn, "max": mx},
        "sea": None,
        "vessel": None,
        "sky": sky,
        "haze": ({"strength": float(choice.get("haze_strength", 0.3)),
                  "density": haze_density(choice.get("haze_strength", 0.3), size)} if choice.get("haze") else None),
        "rain": None,
        "shadows": bool(choice.get("shadows", True)),
        "time": {"start": float(time_start)},
    }
    if sea is not None:
        s = dict(sea)
        s["waves"] = [[float(v) for v in w] for w in s["waves"]]
        s.setdefault("own", len(s["waves"]))
        s.setdefault("radius", SEA_RADIUS)
        s.setdefault("rim", SEA_RIM)
        out["sea"] = s
        if vessel is not None:
            out["vessel"] = vessel
    if choice.get("rain"):
        out["rain"] = {"strength": float(choice.get("rain_strength", 0.5)),
                       "spray": bool(out["sea"] is not None and out["sea"].get("state") == "ROUGH")}
    block = light_block(light)
    if block is not None:
        out["light"] = block
    if plain:
        out.update(sea=None, vessel=None, haze=None, rain=None, plain=True)
    return out


def items_text(st: dict) -> str:
    """What is on the page, in words: 'sea (rough), vessel motion, sky, haze, rain, sun shadows'."""
    out = []
    if st.get("sea"):
        out.append(f"sea ({st['sea'].get('state', 'CALM').lower()})")
    if st.get("vessel"):
        out.append("vessel motion")
    sky = st.get("sky") or {}
    if sky.get("kind") == "PHOTO":
        out.append("the project's light")
    elif sky.get("kind") == "SKY":
        out.append("sky" + {"SOME": " with clouds", "OVERCAST": " (overcast)"}.get(sky.get("clouds"), ""))
    if st.get("haze"):
        out.append("haze")
    if st.get("rain"):
        out.append("rain and spray" if st["rain"].get("spray") else "rain")
    if st.get("shadows"):
        out.append("sun shadows")
    light = (st.get("light") or {}).get("light")
    if light in LIGHTS:
        out.append("baked light (soft)" if light == "SOFT" else "baked light (everything)")
    return ", ".join(out)


# ---------------------------------------------------------------------------
# pictures: 360° light and background
# ---------------------------------------------------------------------------

def equirect_for_page(pixels: np.ndarray, rotation_deg: float, width: int) -> np.ndarray:
    """A Blender equirectangular picture (rows bottom-up, as ``Image.pixels``; (h, w, >=3) linear floats) as the
    page reads it: rows top-down, columns in three.js's longitude, turned by ``rotation_deg`` (Rotate light, as the
    app's Mapping node). Bilinear, ``width`` x ``width/2``."""
    src = np.asarray(pixels, np.float32)[..., :3]
    h, w = src.shape[:2]
    ow, oh = int(width), int(width) // 2
    u = (np.arange(ow) + 0.5) / ow
    v = (np.arange(oh) + 0.5) / oh
    U, V = np.meshgrid(u, v)
    # three: u = atan2(dz, dx) / 2pi + 0.5, v (top row = up) = 0.5 - asin(dy) / pi; three (x, y, z) = Blender (x, z, -y)
    lon = (U - 0.5) * 2 * math.pi
    lat = (0.5 - V) * math.pi
    tx, ty, tz = np.cos(lat) * np.cos(lon), np.sin(lat), np.cos(lat) * np.sin(lon)
    bx, by, bz = tx, -tz, ty
    # the app's Mapping (POINT, rotation about z) turns the vector before the picture is read
    r = math.radians(rotation_deg)
    rx, ry = math.cos(r) * bx - math.sin(r) * by, math.sin(r) * bx + math.cos(r) * by
    # Blender's equirectangular: u = atan2(y, -x) / 2pi + 0.5, v = atan2(z, hypot(x, y)) / pi + 0.5 (row 0 bottom)
    su = (np.arctan2(ry, -rx) / (2 * math.pi) + 0.5) * w - 0.5
    sv = (np.arctan2(bz, np.hypot(rx, ry)) / math.pi + 0.5) * h - 0.5
    x0 = np.floor(su).astype(int)
    y0 = np.clip(np.floor(sv).astype(int), 0, h - 1)
    fx = (su - x0)[..., None]
    fy = np.clip(sv - np.floor(sv), 0, 1)[..., None]
    y1 = np.clip(y0 + 1, 0, h - 1)
    x0m, x1m = x0 % w, (x0 + 1) % w
    a = src[y0, x0m] * (1 - fx) + src[y0, x1m] * fx
    b = src[y1, x0m] * (1 - fx) + src[y1, x1m] * fx
    return (a * (1 - fy) + b * fy).astype(np.float32)


def shrink(pixels: np.ndarray, width: int) -> np.ndarray:
    """Box-average a (h, w, c) picture down to ``width`` (keeps bright suns in the light picture)."""
    h, w = pixels.shape[:2]
    f = max(1, w // int(width))
    if f == 1:
        return pixels
    h2, w2 = h // f, w // f
    return pixels[:h2 * f, :w2 * f].reshape(h2, f, w2, f, -1).mean(axis=(1, 3))


def brightest(page_pixels: np.ndarray) -> tuple[list[float], float]:
    """(direction in Blender world, share of the light) of the brightest spot of a page-layout picture: the sun of a
    360° photo or the main softbox of a studio look."""
    px = shrink(page_pixels, 64)
    lum = px[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    oh, ow = lum.shape
    v, u = np.unravel_index(int(np.argmax(lum)), lum.shape)
    lon = ((u + 0.5) / ow - 0.5) * 2 * math.pi
    lat = (0.5 - (v + 0.5) / oh) * math.pi
    lat = max(lat, math.radians(8.0))           # a light below the horizon would light the model from below
    tx, ty, tz = math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon)
    share = float(lum.max() / max(lum.mean(), 1e-6))
    return [tx, -tz, ty], share


_REC2020 = np.array([[0.6274, 0.0691, 0.0164], [0.3293, 0.9195, 0.0880], [0.0433, 0.0113, 0.8956]])
_REC2020_INV = np.array([[1.6605, -0.1246, -0.0182], [-0.5876, 1.1329, -0.1006], [-0.0728, -0.0083, 1.1187]])
_AGX_IN = np.array([[0.856627153315983, 0.137318972929847, 0.11189821299995],
                    [0.0951212405381588, 0.761241990602591, 0.0767994186031903],
                    [0.0482516061458583, 0.101439036467562, 0.811302368396859]])
_AGX_OUT = np.array([[1.1271005818144368, -0.1413297634984383, -0.14132976349843826],
                     [-0.11060664309660323, 1.157823702216272, -0.11060664309660294],
                     [-0.016493938717834573, -0.016493938717834257, 1.2519364065950405]])


def agx(rgb: np.ndarray, exposure: float = 1.0) -> np.ndarray:
    """three.js's AgX tone mapping (r180, the page's) on linear sRGB pixels -> linear sRGB 0 … 1. The page shows the
    background picture as it is (three does not tone-map an sRGB background), so it is tone-mapped here, the same
    way the page tone-maps the model."""
    c = np.asarray(rgb, np.float64)[..., :3] * exposure
    # GLSL mat3(a, b, c) has the columns a, b, c: M * v for row vectors is v @ [a, b, c]
    c = c @ _REC2020 @ _AGX_IN
    c = np.log2(np.maximum(c, 1e-10))
    c = np.clip((c + 12.47393) / (4.026069 + 12.47393), 0.0, 1.0)
    x2 = c * c
    x4 = x2 * x2
    c = 15.5 * x4 * x2 - 40.14 * x4 * c + 31.96 * x4 - 6.868 * x2 * c + 0.4298 * x2 + 0.1191 * c - 0.00232
    c = c @ _AGX_OUT
    c = np.power(np.maximum(c, 0.0), 2.2)
    c = c @ _REC2020_INV
    return np.clip(c, 0.0, 1.0).astype(np.float32)


def hdr_bytes(pixels: np.ndarray) -> bytes:
    """A Radiance .hdr (RGBE, flat scanlines) of (h, w, 3) linear floats, rows top-down. three's HDRLoader reads it."""
    px = np.maximum(np.asarray(pixels, np.float64)[..., :3], 0.0)
    h, w = px.shape[:2]
    m = px.max(axis=2)
    e = np.zeros(m.shape, np.int32)
    ok = m > 1e-32
    mant, ex = np.frexp(m[ok])
    e[ok] = ex
    scale = np.zeros(m.shape)
    scale[ok] = mant * 256.0 / m[ok]
    rgbe = np.zeros((h, w, 4), np.uint8)
    rgbe[..., :3] = np.clip(px * scale[..., None], 0, 255).astype(np.uint8)
    rgbe[..., 3] = np.where(ok, e + 128, 0).astype(np.uint8)
    head = f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {h} +X {w}\n".encode("ascii")
    return head + rgbe.tobytes()


def read_hdr(data: bytes) -> np.ndarray:
    """The pixels of ``hdr_bytes`` again (tests)."""
    end = data.index(b"\n\n") + 2
    line_end = data.index(b"\n", end)
    _y, h, _x, w = data[end:line_end].split()
    h, w = int(h), int(w)
    rgbe = np.frombuffer(data[line_end + 1:], np.uint8).reshape(h, w, 4).astype(np.float64)
    f = np.where(rgbe[..., 3] > 0, np.ldexp(1.0, rgbe[..., 3].astype(int) - 136), 0.0)
    return rgbe[..., :3] * f[..., None]


def sky_luminance(pixels: np.ndarray) -> float:
    """Mean brightness of the upper half of a page-layout picture (for the strength of the page's sun)."""
    px = np.asarray(pixels)[: pixels.shape[0] // 2, :, :3]
    return float((px @ np.array([0.2126, 0.7152, 0.0722])).mean())


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------

def _read(name: str) -> str:
    with open(os.path.join(web3d.WEB_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def _inline(text: str) -> str:
    return "<script>\n" + text.replace("</script", "<\\/script") + "\n</script>"


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --ink: #F4F6F8; --muted: #D5DBE0; --bg: #8FA6B5; }}
  html, body {{ margin: 0; height: 100%; overflow: hidden; background: var(--bg); color: var(--ink);
               font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; }}
  canvas#view {{ display: block; width: 100%; height: 100%; touch-action: none; }}
  header {{ position: absolute; left: 0; right: 0; top: 0; padding: 14px 18px; display: flex; flex-wrap: wrap;
            justify-content: space-between; align-items: baseline; gap: 4px 12px; pointer-events: none; z-index: 1;
            text-shadow: 0 1px 3px rgba(0,0,0,.55); }}
  h1 {{ margin: 0; font-size: 18px; font-weight: 600; }}
  .hint {{ font-size: 13px; color: var(--muted); }}
  .note {{ position: absolute; left: 18px; bottom: 12px; font-size: 12px; color: var(--muted);
          text-shadow: 0 1px 3px rgba(0,0,0,.55); }}
  #quality {{ position: absolute; right: 12px; bottom: 10px; font-size: 12px; color: var(--muted); display: none;
             background: rgba(20,28,34,.45); padding: 4px 8px; border-radius: 4px; }}
  #fail, #loading {{ display: none; position: absolute; inset: 0; align-items: center; justify-content: center;
                    padding: 24px; text-align: center; }}
  #loading {{ display: flex; pointer-events: none; }}
</style>
</head>
<body>
<canvas id="view"></canvas>
<header><h1>{title}</h1><span class="hint">Drag to turn · scroll or pinch to zoom · right-drag to move</span></header>
<div class="note">{note}</div>
<div id="quality"></div>
<div id="loading">Loading …</div>
<div id="fail">This page needs a browser with WebGL (Edge, Chrome, Firefox or Safari of the last few years).</div>
<script type="application/json" id="fr-env">{settings}</script>
{data}
{three}
{math}
{page}
</body>
</html>
"""


def page_html(title: str, glb: bytes, st: dict, pictures: dict | None = None, note: str = "",
              animated: bool = False) -> str:
    """The one-file page with surroundings: three.js, our code, the settings, the model and the pictures inline.
    ``pictures``: {id: (mime type, bytes)}, named by ``st['sky']['photo' / 'light']``."""
    title_h = html.escape(title or "3D model", quote=True)
    st = dict(st)
    st["animated"] = bool(animated)
    data = ['<script type="application/octet-stream" id="fr-glb">' + base64.b64encode(glb).decode("ascii") + "</script>"]
    for pid, (mime, raw) in (pictures or {}).items():
        data.append(f'<script type="application/octet-stream" id="fr-pic-{html.escape(pid, quote=True)}" '
                    f'data-type="{html.escape(mime, quote=True)}">' + base64.b64encode(raw).decode("ascii")
                    + "</script>")
    text = json.dumps(st, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return _PAGE.format(title=title_h, note=note, settings=text, data="\n".join(data),
                        three=_inline(_read(THREE_FILE)), math=_inline(_read(MATH_FILE)), page=_inline(_read(PAGE_FILE)))


def page_settings(page: str) -> dict:
    """The settings block of a page written by ``page_html`` (tests, PC check)."""
    start = page.index('id="fr-env">') + len('id="fr-env">')
    return json.loads(page[start:page.index("</script>", start)].replace("<\\/", "</"))


def cost(page_bytes: int, glb_bytes: int, plain_page_bytes: int) -> int:
    """Bytes the surroundings add to the page compared with the page without them (may be below 0: three.js is
    smaller than model-viewer)."""
    return int(page_bytes) - int(plain_page_bytes)


# ---------------------------------------------------------------------------
# opening a page in the PC's own browser, headless (PC check, tests)
# ---------------------------------------------------------------------------

def find_browser() -> str:
    """A Chromium-family browser on this PC (Edge or Chrome on Windows, Chromium/Chrome on Linux), '' when none.
    ``FRESING_BROWSER`` names one by hand."""
    own = os.environ.get("FRESING_BROWSER", "")
    if own and os.path.isfile(own):
        return own
    if sys.platform == "win32":
        roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        for root in roots:
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                path = os.path.join(root, rel) if root else ""
                if path and os.path.isfile(path):
                    return path
        return ""
    shells = sorted(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux*/"
                              "chrome-headless-shell"))
    if shells:                       # Playwright's headless shell (the web sessions): starts fastest
        return shells[-1]
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge"):
        path = shutil.which(name)
        if path:
            return path
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else ""


def open_headless(page_path: str, browser: str = "", query: str = "auto=0&frames=5", seconds: float = 120.0) -> str:
    """Open a page with surroundings in ``browser`` without a window, let it run and return the state it writes
    into its own HTML (``data-fr-state``): 'ready <level> frames <n>', 'error: …' or 'loading'. Software drawing
    (SwiftShader) is asked for, so it works without a graphics card too. Raises RuntimeError when the browser does
    not answer."""
    return read_page(page_path, browser, query, seconds)["state"]


def read_page(page_path: str, browser: str = "", query: str = "auto=0&frames=5", seconds: float = 120.0) -> dict:
    """As ``open_headless``, but everything the page writes into its own HTML: {"state": …, "light": {light,
    materials, meshes, plain, background} or None, "probe": [[r, g, b, a], …] or None} (task 0107; ``probe`` only
    with ``probe=x,y;x,y`` in ``query``, screen places 0 … 1 from the top left)."""
    browser = browser or find_browser()
    if not browser:
        raise RuntimeError("no Edge, Chrome or Chromium found")
    url = pathlib.Path(os.path.abspath(page_path)).as_uri() + ("?" + query if query else "")
    profile = tempfile.mkdtemp(prefix="fr_page_check_")        # its own profile: never the user's open browser
    head = [] if "headless-shell" in os.path.basename(browser) else ["--headless=new"]
    args = [browser, *head, f"--user-data-dir={profile}", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--virtual-time-budget=20000", "--dump-dom", url]
    flags = 0
    if sys.platform == "win32":
        flags = 0x08000000                                     # CREATE_NO_WINDOW: no console window pops up
    elif hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(1, "--no-sandbox")                         # Chromium refuses to run as root with its sandbox
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)
    except OSError as exc:                                      # blocked by policy or antivirus, gone meanwhile
        shutil.rmtree(profile, ignore_errors=True)
        raise RuntimeError(f"the browser could not be started ({exc})") from exc
    try:
        stdout, _ = proc.communicate(timeout=seconds)
    except subprocess.TimeoutExpired as exc:
        if sys.platform == "win32":                             # the browser's helper processes too
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=flags)
        proc.kill()
        proc.communicate()
        raise RuntimeError(f"the browser did not finish in {seconds:.0f} s") from exc
    finally:
        for _ in range(5):                                      # helpers may hold the profile for a moment
            shutil.rmtree(profile, ignore_errors=True)
            if not os.path.exists(profile):
                break
            time.sleep(0.5)
    dom = stdout.decode("utf-8", "replace")
    m = re.search(r'data-fr-state="([^"]*)"', dom)
    if m is None and "<html" not in dom:
        raise RuntimeError(f"the browser showed nothing (exit code {proc.returncode})")
    out = {"state": html.unescape(m.group(1)) if m else "loading", "light": None, "probe": None}
    for key, attr in (("light", "data-fr-light"), ("probe", "data-fr-probe")):
        m = re.search(attr + r'="([^"]*)"', dom)
        if m:
            try:
                out[key] = json.loads(html.unescape(m.group(1)))
            except ValueError:
                pass
    return out
