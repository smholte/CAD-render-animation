"""Small pictures of the weather presets (task 0299): drawn from a preset's own channels, so a preset's picture
changes with its numbers and nothing is stored as a picture file.

Pure Python + NumPy (no Blender). ``draw`` gives an (h, w, 4) array of display values 0 … 1, rows top to bottom;
``blender/ui_weather.py`` hands it to Blender's preview icons (rows bottom to top there: ``for_blender``).

What a picture shows, from the channels of ``core.weather.derive``: the sky's colour by the sun's height and the
clouds (blue by day, golden at a low sun, dark blue at night), the sun's disc, cloud patches, the sea below the horizon,
haze and mist, rain streaks, snow flakes, hail stones, a lightning bolt, stars and the moon, floodlights, heat shimmer.
"""

from __future__ import annotations

import math

import numpy as np

from . import weather as W

SIZE = (96, 72)                     # (w, h) in pixels
HORIZON = 0.62                      # share of the height above the horizon


def _smooth(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _blobs(x, y, seed: int) -> np.ndarray:
    """A soft cloud-like field 0 … 1 from a few sines (no noise library needed; seeded so a preset never changes)."""
    rng = np.random.default_rng(seed)
    v = np.zeros_like(x)
    for k in range(6):
        fx, fy = rng.uniform(4.0, 11.0) * (1 + k * 0.35), rng.uniform(5.0, 14.0) * (1 + k * 0.35)
        px, py = rng.uniform(0, 2 * math.pi, 2)
        v += np.sin(x * fx + px) * np.sin(y * fy + py) / (1.0 + k * 0.6)
    v = (v - v.min()) / max(float(v.max() - v.min()), 1e-9)
    return v


def draw(st: "W.State", size=SIZE) -> np.ndarray:
    """The picture of the weather ``st`` (h, w, 4), display values, rows top to bottom."""
    w, h = size
    ch = W.derive(st)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    x = (xx + 0.5) / w
    y = 1.0 - (yy + 0.5) / h                          # 0 bottom … 1 top
    hz = 1.0 - HORIZON
    up = np.clip((y - hz) / HORIZON, 0.0, 1.0)        # 0 at the horizon … 1 at the top
    sky = y >= hz
    el = ch["sun_el"]
    day, night, sun = ch["day"], ch["night"], ch["sun"]
    clouds, low = ch["clouds"], ch["low"]
    warm = W.warmth(el, clouds)
    light = max(W.sky_light(el), 0.0)
    bright = 0.12 + 0.88 * max(light ** 0.6, 0.9 * warm)     # a low sun still lights a clear sky golden
    light = max(light, 0.5 * warm)

    # the clear sky: blue overhead, paler at the horizon; golden low down at a low sun; dark blue at night
    zen = np.array([0.22, 0.45, 0.86])
    hor = np.array([0.70, 0.82, 0.95])
    gold = np.array([1.00, 0.62, 0.30])
    hor = hor + (gold - hor) * warm
    zen = zen + (np.array([0.45, 0.40, 0.62]) - zen) * warm * 0.8
    nightc = np.array([0.03, 0.05, 0.14])
    f = up[..., None] ** 0.7
    col = (hor * (1 - f) + zen * f) * bright
    col = col * (1 - night) + nightc * night
    # the overcast and the clouds
    grey = np.array([0.62, 0.64, 0.68]) * (0.25 + 0.75 * light) * (1.0 - 0.55 * low)
    grey = grey * (1 - night) + np.array([0.06, 0.07, 0.10]) * night
    field = _blobs(x * 1.6, y * 2.4, 299)
    edge = 0.72 - 0.42 * clouds
    patch = _smooth(edge, edge + 0.12, field) * _smooth(0.0, 0.06, clouds)
    cover = np.maximum(patch, max(float(_smooth(0.72, 0.97, clouds)), float(_smooth(0.0, 0.6, low))))
    lit = np.array([1.0, 1.0, 1.0]) + (np.array([1.25, 0.85, 0.6]) - 1.0) * warm
    cloudc = grey * (1.0 + 0.6 * (1.0 - clouds) * day) * lit
    col = col * (1 - cover[..., None]) + cloudc * cover[..., None]
    # the sun's disc and its glow, when it shows
    if sun > 0.02 and el > -3.0:
        sx = 0.5 + 0.35 * math.sin(math.radians(ch["sun_az"] - 90.0))
        sy = hz + HORIZON * min(max(el, -2.0), 60.0) / 70.0
        d = np.hypot((x - sx) * w / h, y - sy)
        disc = _smooth(0.075, 0.055, d) * sun
        glow = np.exp(-d * 9.0) * sun * 0.6
        sunc = np.array([1.0, 0.95, 0.8]) + (np.array([1.0, 0.7, 0.35]) - np.array([1.0, 0.95, 0.8])) * warm
        col = col + sunc * (disc + glow)[..., None] * sky[..., None]
    # stars and the moon
    if ch["stars"] > 0.05:
        rng = np.random.default_rng(7)
        for _ in range(28):
            px, py = rng.integers(0, w), rng.integers(0, int(h * HORIZON * 0.9))
            col[py, px] += 0.8 * ch["stars"]
    if ch["moon"] > 0.05 and ch["moon_el"] > 0:
        d = np.hypot((x - 0.78) * w / h, y - (hz + HORIZON * 0.72))
        col = col + np.array([0.9, 0.9, 0.8]) * (_smooth(0.05, 0.035, d) * ch["moon"])[..., None]

    # the sea below the horizon: darker than the sky, a reflection of the sky's colour; a glitter under the sun
    below = ~sky
    depth = np.clip((hz - y) / hz, 0.0, 1.0)
    seac = np.array([0.10, 0.20, 0.28]) * (0.2 + 0.8 * light) + np.array([0.02, 0.03, 0.05]) * night
    wave = 0.5 + 0.5 * np.sin(xx * 0.9 + yy * yy * 0.08)
    seac = seac[None, None, :] * (0.85 + 0.3 * wave[..., None]) + hor * 0.25 * bright * (1 - depth[..., None])
    col = np.where(below[..., None], seac, col)
    # floodlights: warm spots on the horizon
    if ch["flood"] > 0.05:
        for fx in (0.2, 0.5, 0.8):
            d = np.hypot((x - fx) * w / h, y - hz - 0.03)
            col = col + np.array([1.0, 0.85, 0.6]) * (np.exp(-d * 30.0) * ch["flood"] * ch["night"])[..., None]

    # haze and fog: the far parts (near the horizon) turn to the fog's colour
    fogc = np.array([ch["fog_r"], ch["fog_g"], ch["fog_b"]])
    fogc = fogc / max(float(fogc.max()), 1e-6) * (0.15 + 0.75 * light ** 0.5) * (1 - 0.85 * night)
    km = 3.912 / max(ch["fog"], 1e-6)
    haze = 1.0 - math.exp(-6.0 / max(km, 0.05))      # how much of the far scene the fog hides
    near_h = np.exp(-np.abs(y - hz) * 7.0)
    a = np.clip(haze * (0.35 + 0.65 * near_h), 0.0, 0.97)
    col = col * (1 - a[..., None]) + fogc * a[..., None]
    if ch["mist"] > 0.1:                              # a white band lying on the water
        m = min(ch["mist"] / W.MIST_KM, 1.0) * np.exp(-np.abs(y - hz + 0.04) * 9.0)
        m = m * (0.75 + 0.25 * _blobs(x * 3.0, y, 11))
        col = col * (1 - m[..., None]) + fogc * 1.15 * m[..., None]
    if ch["heat"] > 0.05:                             # shimmer: the horizon wavers, the light is bright
        band = np.exp(-np.abs(y - hz) * 25.0) * ch["heat"]
        col = col + np.array([0.12, 0.10, 0.06]) * (band * (0.5 + 0.5 * np.sin(xx * 1.7)))[..., None]

    # lightning: a bright, jagged line and the clouds lit from inside
    if ch["lightning"] > 0.05:
        col = col * (1.0 + 0.25 * ch["lightning"])
        rng = np.random.default_rng(31)
        px, py = int(w * 0.62), 2
        while py < int(h * HORIZON):
            nx = int(np.clip(px + rng.integers(-3, 4), 2, w - 3))
            ny = py + int(rng.integers(2, 5))
            for t in np.linspace(0.0, 1.0, 8):
                cx, cy = int(round(px + (nx - px) * t)), int(round(py + (ny - py) * t))
                if 0 <= cy < h:
                    col[cy, cx] = (1.0, 1.0, 1.0)
                    col[cy, max(cx - 1, 0)] = np.maximum(col[cy, max(cx - 1, 0)], (0.7, 0.75, 1.0))
            px, py = nx, ny
    # rain, snow and hail in front of everything
    rng = np.random.default_rng(13)
    if ch["rain"] > 0.02:
        lean = float(np.clip(ch["wind_x"] * ch["wind"] / 20.0, -0.8, 0.8))
        for _ in range(int(10 + 120 * ch["rain"])):
            px, py = rng.uniform(0, w), rng.uniform(0, h)
            for t in np.linspace(0.0, 1.0, 6):
                cx, cy = int(px + lean * 6.0 * t) % w, int(py + 6.0 * t) % h
                col[cy, cx] = col[cy, cx] * 0.55 + np.array([0.78, 0.82, 0.88]) * 0.45 * (0.4 + 0.6 * light)
    for amount, n, r in ((ch["snow"], 90, 0.7), (ch["hail"], 70, 1.0)):
        if amount <= 0.02:
            continue
        for _ in range(int(n * amount) + 4):
            px, py = rng.uniform(0, w), rng.uniform(0, h)
            d = np.hypot(xx - px, yy - py)
            col = np.where((d < r)[..., None], np.array([0.95, 0.96, 1.0]) * (0.5 + 0.5 * light), col)
    rgb = np.clip(col, 0.0, 1.0)
    return np.concatenate([rgb, np.ones((h, w, 1))], axis=2)


def for_blender(img: np.ndarray) -> np.ndarray:
    """The picture's rows bottom to top, flat (Blender's ``ImagePreview.image_pixels_float``)."""
    return np.ascontiguousarray(img[::-1]).astype(np.float32).ravel()


def presets(size=SIZE) -> dict:
    """{preset id: picture} for every preset of the panel."""
    return {name: draw(W.preset(name), size) for name in W.PRESET_ORDER}
