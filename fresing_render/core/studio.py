"""Studio light looks, light in plain words, background blur and the turntable (task 0017).

Pure Python + numpy (no Blender), so it can be tested alone. ``blender/world.py`` turns the light
designs into 360° light pictures, ``blender/cameras.py`` uses the blur and turntable numbers.

Directions are given as seen from above, around the machine: azimuth 0° = from the right (+X),
90° = from the back (+Y), 180° = from the left (-X), -90° = from the front (-Y, where the Front
camera stands). Elevation 0° = level with the machine, 90° = straight overhead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# the Light choices (numbers are stored in project files: never change or reuse them)
# ---------------------------------------------------------------------------

LIGHT_ITEMS = [
    ("PRODUCT", "Product studio", "Classic product photo light: a big soft main light from the front left, a "
                                  "soft fill from the right and two rim lights behind that outline the edges", 3),
    ("WHITE", "White studio", "Bright, soft light from all round and from above, like a white photo studio. "
                              "With a white background: the machine on an endless white", 4),
    ("DARK", "Dark studio", "Dark room with a side light and two bright rim lights behind: shiny edges against "
                            "black, for dramatic pictures", 5),
    ("STUDIO", "Soft studio", "Soft, even studio light (the studio light of earlier versions): softboxes all "
                              "round, the strongest from the back right", 0),
    ("HDRI", "360° photo", "Light from a 360° photo: real reflections of a real place. Pick the photo below", 1),
    ("SKY", "Sky", "Daylight: sun or overcast (Weather below)", 2),
]

WEATHER_ITEMS = [
    ("SUN", "Sun", "A sunny sky: sharp shadows. Set the sun height and turn the sun below", 0),
    ("OVERCAST", "Overcast", "A grey, cloudy sky without sun: soft light from everywhere, soft shadows", 1),
]


@dataclass(frozen=True)
class Softbox:
    az: float        # degrees, see the module text
    el: float        # degrees above the horizon (centre of the box)
    w: float         # width, degrees
    h: float         # height, degrees
    power: float     # brightness on top of the room
    tint: tuple = (1.0, 1.0, 1.0)


@dataclass(frozen=True)
class EnvDesign:
    sky: float            # brightness of the room above the horizon (at the horizon)
    sky_top: float        # added towards the top
    ground: float         # brightness below the horizon (floor bounce)
    boxes: tuple          # Softbox, ...
    key: tuple | None     # (az, el) of the main light, for the words; None: no main light
    tint: tuple = (1.0, 1.0, 1.0)


# The designs. Rotation 0 is the good default for the cameras the app makes (front right, 3/4 hero).
DESIGNS = {
    "PRODUCT": EnvDesign(
        sky=0.07, sky_top=0.16, ground=0.035,
        boxes=(Softbox(-115, 32, 42, 32, 9.0, (1.0, 0.97, 0.93)),       # main light, front left
               Softbox(-15, 12, 46, 22, 1.8, (0.95, 0.97, 1.0)),        # fill, front right, low
               Softbox(100, 22, 12, 46, 7.5),                          # rim, back
               Softbox(170, 22, 12, 46, 6.0),                          # rim, back left
               Softbox(0, 82, 110, 10, 2.5)),                          # top strip
        key=(-115, 32)),
    "WHITE": EnvDesign(
        sky=0.80, sky_top=0.12, ground=0.62,
        boxes=(Softbox(0, 76, 180, 28, 3.2),                           # the whole ceiling is light
               Softbox(-120, 35, 60, 40, 2.2, (1.0, 0.99, 0.97))),       # big soft main light, front left
        key=(-120, 35)),
    "DARK": EnvDesign(
        sky=0.006, sky_top=0.01, ground=0.002,
        boxes=(Softbox(-140, 35, 26, 36, 6.0, (1.0, 0.98, 0.95)),       # main light, front left
               Softbox(-20, 10, 40, 25, 0.35),                         # a trace of fill: shadows not pitch black
               Softbox(65, 22, 7, 60, 16.0),                           # rim strip, back right
               Softbox(150, 22, 7, 60, 16.0),                          # rim strip, back left
               Softbox(0, 84, 90, 6, 1.2)),                            # thin top strip
        key=(-140, 35)),
}
# Soft studio (STUDIO) is the picture of versions before task 0017, made in blender/world.py
# (_studio_pixels). Its main light, measured with a panoramic render: from the back right, high.
STUDIO_KEY = (50.0, 35.0)
SUN_AZ_AT_ZERO = 90.0          # Blender's sky puts the sun at the back (+Y) at rotation 0 (measured)
OVERCAST_ZENITH = 1.9          # brightness straight up; the horizon is a third of it (CIE overcast sky)


def _grid(width: int, height: int):
    v = (np.arange(height) + 0.5) / height          # 0 bottom .. 1 top (Blender image rows go bottom-up)
    u = (np.arange(width) + 0.5) / width
    lat = (v - 0.5) * math.pi
    lon = (u - 0.5) * 2 * math.pi
    return np.meshgrid(lon, lat)


def env_pixels(kind: str, width: int = 2048, height: int = 1024) -> np.ndarray:
    """RGBA float pixels (rows bottom-up) of the 360° light picture of a look.

    Blender maps picture column ``lon`` to azimuth ``-lon`` (measured), so a box at azimuth
    ``az`` is drawn at ``lon = -az``."""
    LON, LAT = _grid(width, height)
    if kind == "OVERCAST":
        up = np.clip(np.sin(LAT), 0.0, 1.0)
        sky = OVERCAST_ZENITH * (1.0 + 2.0 * up) / 3.0
        ground = 0.30 * OVERCAST_ZENITH * 0.6 * np.ones_like(LAT)
        img = np.zeros(LAT.shape + (3,), np.float32)
        for c, (ts, tg) in enumerate(zip((0.93, 0.96, 1.0), (0.95, 0.93, 0.88))):
            img[:, :, c] = np.where(LAT >= 0, sky * ts, ground * tg)
    else:
        d = DESIGNS[kind]
        base = np.where(LAT >= 0, d.sky + d.sky_top * np.clip(np.sin(LAT), 0, 1) ** 0.6, d.ground)
        img = np.repeat(base[:, :, None], 3, axis=2).astype(np.float32)
        for b in d.boxes:
            dlon = np.angle(np.exp(1j * (LON - math.radians(-b.az))))
            dlat = LAT - math.radians(b.el)
            edge = 0.02
            fx = np.clip((math.radians(b.w) / 2 - np.abs(dlon)) / edge, 0, 1)
            fy = np.clip((math.radians(b.h) / 2 - np.abs(dlat)) / edge, 0, 1)
            mask = fx * fy
            for c in range(3):
                img[:, :, c] += mask * b.power * b.tint[c]
    alpha = np.ones(img.shape[:2] + (1,), np.float32)
    return np.concatenate([img, alpha], axis=2).astype(np.float32)


# ---------------------------------------------------------------------------
# light in plain words
# ---------------------------------------------------------------------------

_SIDES = ("right", "back right", "back", "back left", "left", "front left", "front", "front right")


def side_words(az: float) -> str:
    """'front left', 'back'... for an azimuth (see the module text)."""
    k = int(math.floor(((az % 360.0) + 22.5) / 45.0)) % 8
    return _SIDES[k]


def height_words(el: float) -> str:
    if el < 12:
        return "low"
    if el < 50:
        return "high"
    if el < 75:
        return "steep from above"
    return "from straight above"


def brightness_words(strength: float) -> str:
    if strength < 0.45:
        return "dim"
    if strength < 0.85:
        return "soft"
    if strength <= 1.25:
        return "normal brightness"
    if strength <= 2.0:
        return "bright"
    return "very bright"


def main_light(lighting: str, weather: str, rotation: float, sun_elevation: float):
    """(azimuth, elevation) of the main light or the sun, or None (no single main light)."""
    if lighting == "SKY":
        if weather == "OVERCAST":
            return None
        return SUN_AZ_AT_ZERO - rotation, sun_elevation
    if lighting == "STUDIO":
        return STUDIO_KEY[0] - rotation, STUDIO_KEY[1]
    d = DESIGNS.get(lighting)
    if d is None or d.key is None:
        return None
    return d.key[0] - rotation, d.key[1]


def light_words(lighting: str, weather: str = "SUN", rotation: float = 0.0, strength: float = 1.0,
                sun_elevation: float = 45.0) -> str:
    """One line for the panel, e.g. 'Main light from the front left, high · normal brightness'."""
    bright = brightness_words(strength)
    if lighting == "HDRI":
        return f"Light from the 360° photo · {bright}"
    if lighting == "SKY" and weather == "OVERCAST":
        return f"Soft light from the whole sky, no sun · {bright}"
    ml = main_light(lighting, weather, rotation, sun_elevation)
    if ml is None:
        return f"Soft light all round · {bright}"
    az, el = ml
    where = side_words(az)
    if lighting == "SKY":
        return f"Sun from the {where}, {height_words(el)} · {bright}"
    if lighting == "DARK":
        return f"Rim lights behind, main light from the {where} · {bright}"
    if lighting == "WHITE":
        return f"Soft light all round, main light from the {where} · {bright}"
    return f"Main light from the {where}, {height_words(el)} · {bright}"


def rotation_for(lighting: str, az_wanted: float) -> float:
    """The 'Turn light' value that puts the main light (or the sun) at azimuth ``az_wanted``."""
    if lighting == "SKY":
        az0 = SUN_AZ_AT_ZERO
    elif lighting == "STUDIO":
        az0 = STUDIO_KEY[0]
    else:
        az0 = DESIGNS[lighting].key[0]
    r = (az0 - az_wanted) % 360.0
    return r - 360.0 if r > 180.0 else r


# ---------------------------------------------------------------------------
# looks: one click sets light, background and floor
# ---------------------------------------------------------------------------

SUN_FROM = -115.0      # the sun of 'Outdoor sun' comes from the front left, like the studio main light
SUN_EXPOSURE = -1.0

LOOKS = {
    # id: (label, icon, tooltip)
    "PRODUCT": ("Product studio", "LIGHT_AREA",
                "Classic product photo: soft main light from the front left, fill from the right, rim lights "
                "behind, on a light grey background with a soft shadow. Change the colour below if you like"),
    "WHITE": ("White, endless", "SHADING_SOLID",
              "The machine on an endless pure-white background with a soft shadow under it, in bright soft "
              "light (like a white photo studio). The picture's background is exactly white"),
    "DARK": ("Dark studio", "SHADING_RENDERED",
             "Black background, a side light and bright rim lights behind: shiny edges and a dramatic look"),
    "SUN": ("Outdoor sun", "LIGHT_SUN",
            "Blue sky with the sun from the front left and sharp shadows. On the sea, the deck or the quay "
            "only the weather changes"),
    "OVERCAST": ("Overcast", "OUTLINER_DATA_LIGHTPROBE",
                 "Grey, cloudy sky without sun: soft light and soft shadows, colours look calm and true. On the "
                 "sea, the deck or the quay only the weather changes"),
}


def look_settings(look: str, background: str, sea_kinds=("SEA", "DECK", "QUAY")) -> dict:
    """The settings a look sets (names of the scene's Fresing settings)."""
    if look in ("PRODUCT", "WHITE", "DARK"):
        colour = {"PRODUCT": (0.80, 0.80, 0.80), "WHITE": (1.0, 1.0, 1.0), "DARK": (0.0, 0.0, 0.0)}[look]
        return {"background": "COLOR", "background_color": colour, "lighting": look, "floor": "SHADOW",
                "light_rotation": 0.0, "light_strength": 1.0, "exposure": 0.0}
    out = {"sky_weather": "SUN" if look == "SUN" else "OVERCAST", "light_strength": 1.0, "exposure": 0.0}
    if background not in sea_kinds:            # offshore keeps its sea; anything else becomes the sky
        out["background"] = "SKY"
    if look == "SUN":       # the bright sun washes light colours out at exposure 0
        out.update(sun_elevation=35.0, light_rotation=rotation_for("SKY", SUN_FROM), exposure=SUN_EXPOSURE)
    return out


def look_matches(look: str, s) -> bool:
    """Is this look what the settings show now (the button stays pressed)?"""
    bg = s.background
    if look in ("PRODUCT", "WHITE", "DARK"):
        return bg in ("COLOR", "TRANSPARENT") and s.lighting == look
    sky = bg in ("SKY", "SEA", "DECK", "QUAY")
    return sky and s.sky_weather == ("SUN" if look == "SUN" else "OVERCAST")


# ---------------------------------------------------------------------------
# background blur
# ---------------------------------------------------------------------------

# How big a far-away point's blur circle is, as a share of the picture's width. The same look on
# a 1 m gearbox and a 25 m crane: the f-stop follows the size (a 25 m crane needs an f-stop no real
# lens has, which is fine in a render).
BLUR = {"NONE": 0.0, "LITTLE": 0.004, "STRONG": 0.012}
BLUR_ITEMS = [
    ("NONE", "None", "Everything sharp", 0),
    ("LITTLE", "A little", "The background goes soft; the machine stays sharp", 1),
    ("STRONG", "Strong", "A clearly blurred background, like a product photo; parts far from the sharp spot "
                         "go soft too", 2),
]
FSTOP_MIN, FSTOP_MAX = 0.05, 128.0


def blur_fstop(level: str, lens_mm: float, sensor_mm: float, focus_m: float) -> float:
    """f-stop that gives the blur of ``level`` with this lens, sensor and focus distance.

    Thin lens: a point far behind the sharp spot makes a circle of f² / (N (S - f)) on the sensor;
    solved for N with that circle = share × sensor width."""
    share = BLUR.get(level, 0.0)
    if share <= 0:
        return FSTOP_MAX
    f = max(1.0, lens_mm)
    s = max(focus_m * 1000.0, f * 1.5)
    n = f * f / (share * max(1.0, sensor_mm) * (s - f))
    return float(min(FSTOP_MAX, max(FSTOP_MIN, n)))


def blur_share(fstop: float, lens_mm: float, sensor_mm: float, focus_m: float, distance_m: float) -> float:
    """Blur circle of a point at ``distance_m`` as a share of the picture's width (for the tests)."""
    f = lens_mm
    s = focus_m * 1000.0
    d = distance_m * 1000.0
    return f * f * abs(d - s) / (fstop * d * (s - f)) / sensor_mm


# ---------------------------------------------------------------------------
# turntable
# ---------------------------------------------------------------------------

TURNTABLE_HEIGHTS = {"LOW": 8.0, "MIDDLE": 22.0, "HIGH": 40.0}     # camera elevation, degrees
TURNTABLE_HEIGHT_ITEMS = [
    ("LOW", "Low", "Camera a little above the floor: the machine looks big and impressive", 0),
    ("MIDDLE", "Middle", "Camera a little higher than the machine: the usual turntable", 1),
    ("HIGH", "High", "Camera well above the machine: you see the top and the layout", 2),
]


def turntable_timing(seconds: float, fps: int) -> tuple[int, float, float]:
    """(frames, step duration in s, orbit angle in degrees) for a turntable that loops without a
    jump: N frames, frame N+1 would be frame 1 again, so the last frame stands one step short of 360°.

    The animation's step runs from frame 1 to frame 1 + round(duration × fps) = N."""
    n = max(8, int(round(seconds * fps)))
    duration = (n - 1) / fps
    angle = 360.0 * (n - 1) / n
    return n, duration, angle
