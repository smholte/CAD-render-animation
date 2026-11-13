"""Weather and time of day (task 0109): the settings, the presets, the sun's path and the numbers the scene reads.

Pure Python (no Blender), so it can be tested alone. ``blender/weather.py`` turns a :class:`State` into the scene's
**channels** – custom properties ``scene["fr_wx_<name>"]`` (see :data:`CHANNELS`) – and everything that shows weather
reads only those: the sky and the night lamps (``blender/weather_sky.py``), the wet and snow look of the materials
(``blender/weather_look.py``), rain, snow and flags (``blender/weather_fx.py``) and the sea's white caps
(``blender/surroundings.py``). A *Weather & time* animation step keys the channels (they are plain custom
properties: keys work with scripts off and in the render queue); the readers use View Layer attributes in shaders
and simple-expression drivers elsewhere.

Directions in the scene follow ``core/studio.py``: azimuth 0° = +X (right), 90° = +Y (back), 180° = -X (left),
-90° = -Y (front, where the Front camera stands). Compass directions (wind from, the sun's bearing) are degrees from
north, clockwise; ``north`` says which scene azimuth north is (default 90°: the back).

Time is **local solar time**: 12:00 is the moment the sun stands highest, whatever the time zone or summer time –
so a clock time means the same light everywhere and no time zone is needed. Without a date the sun follows the
equinox (sunrise 6:00, sunset 18:00); with a date and a latitude it follows that day's real path.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields, replace

# ---------------------------------------------------------------------------
# wind: the Beaufort scale (WMO mean wind speed at 10 m, m/s, the middle of each force's band)
# ---------------------------------------------------------------------------

BEAUFORT_MS = (0.0, 0.9, 2.4, 4.4, 6.7, 9.3, 12.3, 15.5, 18.9, 22.6, 26.4, 30.5, 34.0)
BEAUFORT_NAMES = ("Calm", "Light air", "Light breeze", "Gentle breeze", "Moderate breeze", "Fresh breeze",
                  "Strong breeze", "Near gale", "Gale", "Strong gale", "Storm", "Violent storm", "Hurricane force")


def bft_to_ms(bft: float) -> float:
    """Wind speed (m/s) of a Beaufort force; fractions are interpolated (5.5 = between 5 and 6)."""
    b = min(max(float(bft), 0.0), 12.0)
    i = min(int(b), 11)
    f = b - i
    return BEAUFORT_MS[i] + (BEAUFORT_MS[i + 1] - BEAUFORT_MS[i]) * f


def ms_to_bft(ms: float) -> float:
    """The inverse of :func:`bft_to_ms` (a fractional force)."""
    v = max(float(ms), 0.0)
    for i in range(12):
        lo, hi = BEAUFORT_MS[i], BEAUFORT_MS[i + 1]
        if v <= hi:
            return i + (v - lo) / (hi - lo)
    return 12.0


def bft_name(bft: float) -> str:
    return BEAUFORT_NAMES[int(round(min(max(bft, 0.0), 12.0)))]


# ---------------------------------------------------------------------------
# the settings
# ---------------------------------------------------------------------------

EQUINOX_DAY = 80            # 21 March: day and night 12 h everywhere
DEFAULT_LATITUDE = 55.0     # the southern North Sea


@dataclass(frozen=True)
class State:
    """One weather and time of day. Numbers are stored in project files (``props.FRWeather``)."""
    hour: float = 12.0              # local solar time, 0 … 24
    use_date: bool = False          # False: the equinox (the sun rises at 6, sets at 18)
    day: int = EQUINOX_DAY          # day of the year, 1 … 366
    latitude: float = DEFAULT_LATITUDE
    north: float = 90.0             # scene azimuth of north (degrees)
    clouds: float = 0.1             # cloud cover 0 (clear) … 1 (overcast)
    low_clouds: float = 0.0         # low cloud / a cloud ceiling 0 … 1 (dark, hides the sky's top)
    visibility: float = 40000.0     # metres: 40 km clear, 10 km haze, 2 km mist, < 1 km fog
    rain: float = 0.0               # falling rain 0 … 1 (1 = a downpour, ~20 mm/h)
    drop_size: float = 2.0          # mm
    wet: float = 0.0                # how wet the machine and the deck are, 0 … 1 (also without rain)
    snow: float = 0.0               # falling snow 0 … 1
    snow_cover: float = 0.0         # the snow layer on upward faces 0 … 1 (1 ≈ 10 cm)
    wind: float = 3.0               # Beaufort
    wind_from: float = 225.0        # degrees: compass bearing the wind comes from, or from the bow (wind_ref)
    wind_ref: str = "NORTH"         # NORTH: wind_from is a compass bearing; BOW: degrees from the vessel's bow
    floodlights: str = "AUTO"       # AUTO (on from dusk), ON, OFF
    flood_strength: float = 1.0     # x the floodlights' own power


# the presets of the panel: (id, label, tooltip, what differs from State())
PRESETS = {
    "CLEAR_DAY": ("Clear day", "Late morning sun, a few clouds, a light breeze: clear air to the horizon",
                  dict(hour=11.0, clouds=0.1, low_clouds=0.0, visibility=40000.0, wind=3.0)),
    "GREY_NORTH_SEA": ("Grey North Sea", "Overcast early afternoon, a strong breeze (Bft 6), drizzle and haze; "
                       "the machine is wet",
                       dict(hour=13.0, clouds=0.9, low_clouds=0.35, visibility=8000.0, rain=0.15, drop_size=1.0,
                            wet=0.7, wind=6.0)),
    "STORM": ("Storm", "A gale (Bft 9): heavy rain driven by the wind, low clouds, white water and spray; the "
              "air closes in at 2.5 km",
              dict(hour=15.0, clouds=1.0, low_clouds=0.8, visibility=2500.0, rain=0.85, drop_size=3.0, wet=1.0,
                   wind=9.0)),
    "SNOW_QUAY": ("Snow at the quay", "Grey winter morning, snow falling in a light wind; a snow layer lies on "
                  "everything under the open sky",
                  dict(hour=10.0, clouds=0.95, low_clouds=0.5, visibility=3000.0, snow=0.55, snow_cover=0.7,
                       wind=3.0, wet=0.2)),
    "NIGHT_SHIFT": ("Night shift", "Late evening in the dark: stars and the moon, floodlights on the deck or "
                    "the quay, a damp sheen",
                    dict(hour=23.0, clouds=0.25, visibility=15000.0, wet=0.35, wind=3.0, floodlights="ON")),
}
PRESET_ORDER = ("CLEAR_DAY", "GREY_NORTH_SEA", "STORM", "SNOW_QUAY", "NIGHT_SHIFT")


def preset(name: str, base: State | None = None) -> State:
    """The preset's weather. ``base`` keeps what a preset does not set (north, date, latitude, wind direction)."""
    base = base or State()
    keep = dict(hour=State.hour, clouds=State.clouds, low_clouds=State.low_clouds, visibility=State.visibility,
                rain=0.0, drop_size=State.drop_size, wet=0.0, snow=0.0, snow_cover=0.0, wind=State.wind,
                floodlights="AUTO", flood_strength=State.flood_strength)
    keep.update(PRESETS[name][2])
    return replace(base, **keep)


def as_dict(st: State) -> dict:
    return asdict(st)


def from_dict(d: dict) -> State:
    names = {f.name for f in fields(State)}
    return State(**{k: v for k, v in d.items() if k in names})


# ---------------------------------------------------------------------------
# outdoor or indoor
# ---------------------------------------------------------------------------

SKY_BACKGROUNDS = ("SKY", "SEA", "DECK", "QUAY")       # the sky is drawn by the app: time of day, clouds
OUTDOOR = SKY_BACKGROUNDS + ("HDRI",)                  # rain, snow and wind fall here too (a 360° photo outside)


def where(background: str) -> str:
    """'sky' (time, clouds, rain, snow, wind), 'photo' (rain, snow, wind, wet; the photo keeps its own light) or
    'indoor' (halls, studios, plain colours: only work lights; nothing falls)."""
    if background in SKY_BACKGROUNDS:
        return "sky"
    if background == "HDRI":
        return "photo"
    return "indoor"


# ---------------------------------------------------------------------------
# the sun and the moon
# ---------------------------------------------------------------------------

def declination(day: int) -> float:
    """The sun's declination (degrees) on a day of the year (Cooper's approximation, ±0.5°)."""
    return -23.44 * math.cos(2.0 * math.pi * (int(day) + 10) / 365.0)


def sun_position(hour: float, day: int = EQUINOX_DAY, latitude: float = DEFAULT_LATITUDE) -> tuple[float, float]:
    """(elevation, compass bearing) of the sun in degrees at a local solar time. Bearing: 0 = north, 90 = east,
    180 = south (where the sun stands at noon north of the tropics)."""
    phi = math.radians(latitude)
    dec = math.radians(declination(day))
    h = math.radians(15.0 * (float(hour) - 12.0))
    sin_el = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h)
    el = math.degrees(math.asin(max(-1.0, min(1.0, sin_el))))
    az = math.degrees(math.atan2(math.sin(h), math.cos(h) * math.sin(phi) - math.tan(dec) * math.cos(phi))) + 180.0
    return el, az % 360.0


def sun_of(st: State) -> tuple[float, float]:
    return sun_position(st.hour, st.day if st.use_date else EQUINOX_DAY, st.latitude)


def to_scene_az(bearing: float, north: float) -> float:
    """A compass bearing as a scene azimuth (studio convention); bearings turn clockwise seen from above."""
    return (north - bearing + 180.0) % 360.0 - 180.0


def from_scene_az(az: float, north: float) -> float:
    return (north - az) % 360.0


def daylight(sun_el: float) -> float:
    """0 at night … 1 in daylight: civil twilight (-6° … +6°) in between."""
    return smoothstep(-6.0, 6.0, sun_el)


def darkness(sun_el: float) -> float:
    """0 by day … 1 in the dark (the sun more than 12° below the horizon: nautical twilight over)."""
    return 1.0 - smoothstep(-12.0, -1.0, sun_el)


def sunrise_sunset(day: int = EQUINOX_DAY, latitude: float = DEFAULT_LATITUDE) -> tuple[float, float] | None:
    """Solar times the sun's middle crosses the horizon; None for midnight sun or polar night."""
    x = -math.tan(math.radians(latitude)) * math.tan(math.radians(declination(day)))
    if abs(x) > 1.0:
        return None
    h = math.degrees(math.acos(x)) / 15.0
    return 12.0 - h, 12.0 + h


def from_old(sun_elevation: float, light_rotation: float, overcast: bool, sun_rotation_zero_az: float = 90.0) -> State:
    """The weather that looks like an older project's sky (Sun / Overcast, sun height, light rotation): solar noon
    at the equinox on the latitude where the noon sun stands that high, north turned so the sun stands where it
    did. ``sun_rotation_zero_az``: the scene azimuth of the sun at 'Rotate light' 0 (the sky texture's own zero,
    ``weather_sky.SUN_ROTATION_ZERO_AZ``); turning the light by +r puts the sun at ``zero - r`` (measured, as in
    ``core/studio.main_light``). Sun: a clear sky without cloud patches; Overcast: full cover without a low cloud
    deck – the soft grey sky of before."""
    lat = min(max(90.0 - float(sun_elevation) + declination(EQUINOX_DAY), 0.0), 89.0)
    el, bearing = sun_position(12.0, EQUINOX_DAY, lat)          # bearing 180 (south)
    want_az = sun_rotation_zero_az - float(light_rotation)
    north = (want_az + bearing) % 360.0
    north = (north + 180.0) % 360.0 - 180.0
    return State(hour=12.0, latitude=lat, north=north, clouds=1.0 if overcast else 0.0, low_clouds=0.0)


# ---------------------------------------------------------------------------
# wind
# ---------------------------------------------------------------------------

BOW_AZ = 180.0          # the vessel lies along x, bow at -x (core/vessel_motion.py, the Vessel deck)


def wind_from_az(st: State) -> float:
    """Scene azimuth the wind comes from."""
    if st.wind_ref == "BOW":
        # 0 = from ahead, 90 = from starboard (the right side looking forward: +Y with the bow at -X)
        return (BOW_AZ - st.wind_from + 180.0) % 360.0 - 180.0
    return to_scene_az(st.wind_from, st.north)


def wind_vector(st: State) -> tuple[float, float]:
    """Unit vector (x, y) the wind blows *towards*, in the scene."""
    a = math.radians(wind_from_az(st) + 180.0)
    return math.cos(a), math.sin(a)


# ---------------------------------------------------------------------------
# mixing two weathers (the Weather & time step)
# ---------------------------------------------------------------------------

def smoothstep(a: float, b: float, x: float) -> float:
    if b == a:
        return 1.0 if x >= b else 0.0
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _lerp(a, b, f):
    return a + (b - a) * f


def mix(a: State, b: State, f: float) -> State:
    """The weather a fraction ``f`` of the way from ``a`` to ``b``. The clock runs forward (22:00 → 02:00 goes
    through midnight); visibility changes evenly in log scale (the fog closes in evenly); the wind direction turns
    the short way; choices switch half way."""
    f = min(max(float(f), 0.0), 1.0)
    if f <= 0.0:
        return a
    if f >= 1.0:
        return b
    h1 = b.hour if b.hour >= a.hour else b.hour + 24.0
    d_dir = ((b.wind_from - a.wind_from + 180.0) % 360.0) - 180.0
    pick = (lambda x, y: y if f >= 0.5 else x)
    return State(
        hour=_lerp(a.hour, h1, f) % 24.0 if f < 1.0 else b.hour,
        use_date=pick(a.use_date, b.use_date), day=pick(a.day, b.day),
        latitude=_lerp(a.latitude, b.latitude, f), north=a.north + ((b.north - a.north + 180.0) % 360.0 - 180.0) * f,
        clouds=_lerp(a.clouds, b.clouds, f), low_clouds=_lerp(a.low_clouds, b.low_clouds, f),
        visibility=math.exp(_lerp(math.log(max(a.visibility, 1.0)), math.log(max(b.visibility, 1.0)), f)),
        rain=_lerp(a.rain, b.rain, f), drop_size=_lerp(a.drop_size, b.drop_size, f), wet=_lerp(a.wet, b.wet, f),
        snow=_lerp(a.snow, b.snow, f), snow_cover=_lerp(a.snow_cover, b.snow_cover, f),
        wind=_lerp(a.wind, b.wind, f), wind_from=(a.wind_from + d_dir * f) % 360.0,
        wind_ref=pick(a.wind_ref, b.wind_ref), floodlights=pick(a.floodlights, b.floodlights),
        flood_strength=_lerp(a.flood_strength, b.flood_strength, f))


# ---------------------------------------------------------------------------
# the channels: what the scene reads
# ---------------------------------------------------------------------------

PREFIX = "fr_wx_"

# name: (soft min, soft max, what it is). Kept away from tiny positive numbers (a driver result below ~1e-4 is
# written as 0 by Blender 5.2.3, CLAUDE.md section 8): densities per km, not per m.
CHANNELS = {
    "sun_el": (-90.0, 90.0, "the sun's height above the horizon, degrees"),
    "sun_az": (-180.0, 180.0, "scene azimuth of the sun, degrees (studio convention)"),
    "moon_el": (-90.0, 90.0, "the moon's height, degrees"),
    "moon_az": (-180.0, 180.0, "scene azimuth of the moon, degrees"),
    "day": (0.0, 1.0, "daylight 0 (night) … 1 (day); civil twilight between"),
    "night": (0.0, 1.0, "darkness 0 (day) … 1 (dark night)"),
    "sun": (0.0, 1.0, "how much direct sun gets through the clouds"),
    "clouds": (0.0, 1.0, "cloud cover"),
    "low": (0.0, 1.0, "low clouds / ceiling"),
    "fog": (0.0, 40.0, "fog density, per km (Koschmieder: 3.912 / visibility in km)"),
    "fog_r": (0.0, 2.0, "fog colour: radiance, linear red (core.weather.fog_level; dark at night)"),
    "fog_g": (0.0, 2.0, "fog colour: radiance, linear green"),
    "fog_b": (0.0, 2.0, "fog colour: radiance, linear blue"),
    "stars": (0.0, 1.0, "how much the stars show"),
    "moon": (0.0, 1.0, "moonlight"),
    "exposure": (-2.0, 8.0, "EV added to the user's exposure (a camera opens up at dusk and night)"),
    "flood": (0.0, 1.0, "floodlights 0 (off) … 1 (on)"),
    "rain": (0.0, 1.0, "falling rain"),
    "drop": (0.2, 8.0, "rain drop size, mm"),
    "wet": (0.0, 1.0, "wet look on the machine and the ground"),
    "snow": (0.0, 1.0, "falling snow"),
    "cover": (0.0, 1.0, "snow layer on upward faces under the open sky"),
    "wind": (0.0, 40.0, "wind speed, m/s"),
    "wind_x": (-1.0, 1.0, "direction the wind blows towards, x"),
    "wind_y": (-1.0, 1.0, "direction the wind blows towards, y"),
    "foam": (0.0, 1.0, "white-cap threshold of the sea's foam field (core/sea.foam_threshold): lower = more foam"),
}
CHANNEL_NAMES = tuple(CHANNELS)


def prop(name: str) -> str:
    """The scene custom property of a channel: ``fr_wx_<name>``."""
    return PREFIX + name


def _foam_threshold(bft: float) -> float:
    try:
        from . import sea
        return float(sea.foam_threshold(bft))
    except (ImportError, AttributeError):          # (before core/sea.py exists)
        return 1.0 - 0.1 * min(max(bft, 0.0), 10.0)


# The haze's colour (normalised to brightness about 1) by day, at a low sun and at night. The channels fog_r/g/b
# are *radiance* (scene-linear, at light strength 1): the colour times :func:`fog_level` – so the sky's haze
# (``weather_sky.world_branch``) and the fog laid over the picture (the compositor) are one grey at the horizon.
FOG_DAY = (0.88, 0.98, 1.12)
FOG_DUSK = (1.30, 0.86, 0.62)
FOG_NIGHT = (0.70, 0.90, 1.50)
CLEAR_FOG = 3.912 / 40.0     # per km: 40 km visibility is clear air, the sky texture's own; only more haze is added
CLEAR_SKY_HORIZON = 1.05     # radiance of the clear sky at the horizon at a high sun (MULTIPLE_SCATTERING x 0.08)
OVERCAST_ZENITH = 1.34       # radiance straight up under full cloud at a high sun; with exposure_for's +0.5 EV it
#                              matches the old Overcast light picture (core/studio.OVERCAST_ZENITH 1.9, exposure 0)
NIGHT_SKY = 0.0004           # the dark night sky (airglow), radiance
MOON_SKY = 0.002              # what a full moon adds to the night sky
SUN_W = 13.0                 # the sky texture's sun overhead in Sun-lamp units (W/m², measured on a white plane)
MOON_W = 0.03                # moonlight (Sun lamp, W/m²) at moon 1: with the night's +4 EV a dim blue light
NIGHT_EV = 2.0               # EV added in the dark on top of the +2 of dusk (+4 in all)


def sky_light(sun_el: float) -> float:
    """How bright the sky is for a sun height, 0 … 1 (1 from 30° up). The world shader uses the same curve,
    ``pow(smoothstep(-9, 30, sun_el), 1.5)``; the clear sky texture follows it within a factor 2 down to 0°."""
    return smoothstep(-9.0, 30.0, sun_el) ** 1.5


def warmth(sun_el: float, clouds: float) -> float:
    """0 … 1: how golden the light and the haze are (a low sun in a clear sky)."""
    return (1.0 - smoothstep(1.0, 18.0, sun_el)) * smoothstep(-6.0, 0.0, sun_el) * (1.0 - 0.7 * clouds)


def fog_level(sun_el: float, clouds: float, low: float, night: float = 0.0, moon: float = 0.0) -> float:
    """Brightness (radiance) of haze and fog: the clear sky's horizon, or the cloud's, plus the night sky."""
    lvl = sky_light(sun_el)
    clear = CLEAR_SKY_HORIZON * lvl
    grey = OVERCAST_ZENITH * 0.6 * (1.0 - 0.55 * low) * lvl
    return clear + (grey - clear) * clouds + NIGHT_SKY * night + MOON_SKY * moon


def exposure_for(sun_el: float, clouds: float) -> float:
    """EV a camera (or the eye) adds as the light fades: 0 in daylight, about +2 at sunset, +4 at night (the
    floodlights and the moon then look as they do to the eye: concrete in moonlight dark grey, floodlit parts bright,
    tried on the quay and the open sea)."""
    dusk = 1.0 - smoothstep(-4.0, 8.0, sun_el)
    dark = darkness(sun_el)
    return 2.0 * dusk + NIGHT_EV * dark + 0.5 * clouds * (1.0 - dark)


def derive(st: State, place: str = "sky") -> dict:
    """The channel values of a weather. ``place`` from :func:`where`: indoors nothing falls and the sky is not
    drawn; with a 360° photo the photo keeps its light (no time of day)."""
    el, bearing = sun_of(st)
    sun_az = to_scene_az(bearing, st.north)
    moon_az = ((sun_az + 180.0 + 25.0) + 180.0) % 360.0 - 180.0
    moon_el = min(max(-el * 0.8 + 8.0, -30.0), 55.0)
    day = daylight(el)
    night = darkness(el)
    clouds = min(max(st.clouds, 0.0), 1.0)
    low = min(max(st.low_clouds, 0.0), 1.0)
    sun = (1.0 - smoothstep(0.55, 0.95, clouds)) * (1.0 - low) * smoothstep(-1.0, 2.0, el)
    km = max(st.visibility, 50.0) / 1000.0
    moon = night * (1.0 - 0.8 * clouds)
    warm = warmth(el, clouds)
    lit = fog_level(el, clouds, low)
    dark = NIGHT_SKY * night + MOON_SKY * moon
    fog_col = tuple((FOG_DAY[i] + (FOG_DUSK[i] - FOG_DAY[i]) * warm) * lit + FOG_NIGHT[i] * dark for i in range(3))
    flood = {"ON": 1.0, "OFF": 0.0}.get(st.floodlights, 1.0 - smoothstep(-2.0, 6.0, el))
    wx, wy = wind_vector(st)
    ch = {
        "sun_el": el, "sun_az": sun_az, "moon_el": moon_el, "moon_az": moon_az,
        "day": day, "night": night, "sun": sun, "clouds": clouds, "low": low,
        "fog": 3.912 / km, "fog_r": fog_col[0], "fog_g": fog_col[1], "fog_b": fog_col[2],
        "stars": night * (1.0 - smoothstep(0.3, 0.9, clouds)) * (1.0 - low),
        "moon": moon,
        "exposure": exposure_for(el, clouds),
        "flood": flood * min(max(st.flood_strength, 0.0), 4.0),
        "rain": min(max(st.rain, 0.0), 1.0), "drop": min(max(st.drop_size, 0.2), 8.0),
        "wet": min(max(max(st.wet, st.rain), 0.0), 1.0),
        "snow": min(max(st.snow, 0.0), 1.0), "cover": min(max(st.snow_cover, 0.0), 1.0),
        "wind": bft_to_ms(st.wind), "wind_x": wx, "wind_y": wy,
        "foam": _foam_threshold(st.wind),
    }
    if place == "photo":                     # the photo keeps its own sky and light
        ch.update(sun_el=45.0, day=1.0, night=0.0, sun=1.0, stars=0.0, moon=0.0, exposure=0.0, flood=0.0)
    elif place == "indoor":
        ch.update(sun_el=45.0, day=1.0, night=0.0, sun=1.0, stars=0.0, moon=0.0, exposure=0.0, flood=0.0,
                  fog=0.0, rain=0.0, wet=0.0, snow=0.0, cover=0.0, wind=0.0)
    return {k: float(v) for k, v in ch.items()}


# ---------------------------------------------------------------------------
# plain words for the panel
# ---------------------------------------------------------------------------

def clock(hour: float) -> str:
    h = float(hour) % 24.0
    m = int(round(h * 60.0)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def part_of_day(sun_el: float, hour: float) -> str:
    if sun_el < -12.0:
        return "night"
    if sun_el < -1.0:
        return "dusk" if hour >= 12.0 else "dawn"
    if sun_el < 8.0:
        return "sunset" if hour >= 12.0 else "sunrise"
    if sun_el < 20.0:
        return "golden hour" if hour >= 12.0 else "early morning"
    return "day"


def visibility_words(m: float) -> str:
    if m < 1000.0:
        return f"fog, {m:.0f} m"
    if m < 4000.0:
        return f"mist, {m / 1000:.1f} km"
    if m < 15000.0:
        return f"haze, {m / 1000:.0f} km"
    return "clear air"


def words(st: State, place: str = "sky") -> str:
    """One line for the panel header and the tour, e.g. '13:00 day · overcast · Bft 6 · rain · haze, 8 km'."""
    el, _ = sun_of(st)
    bits = []
    if place == "sky":
        bits.append(f"{clock(st.hour)} {part_of_day(el, st.hour)}")
        bits.append("overcast" if st.clouds >= 0.8 else "cloudy" if st.clouds >= 0.4 else "clear")
    if place != "indoor":
        bits.append(f"Bft {st.wind:.0f}")
        if st.rain > 0.01:
            bits.append("rain")
        if st.snow > 0.01:
            bits.append("snow")
        elif st.snow_cover > 0.01:
            bits.append("snow on the ground")
        if st.wet > 0.01 and st.rain <= 0.01:
            bits.append("wet")
        if place == "sky" and st.visibility < 15000.0:
            bits.append(visibility_words(st.visibility))
    return " · ".join(bits) if bits else "indoors"
