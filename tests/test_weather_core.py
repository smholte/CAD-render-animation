"""Task 0109: core/weather.py – the sun's path, presets, old projects, the channels (no Blender)."""

from __future__ import annotations

import math

import pytest

from fresing_render.core import studio
from fresing_render.core import weather as W


def test_equinox_sunrise_noon_sunset():
    """Without a date the sun rises at 6:00 due east, stands highest at 12:00 due south, sets at 18:00 due west."""
    el, az = W.sun_position(6.0)
    assert abs(el) < 0.6 and abs(az - 90.0) < 1.0
    el, az = W.sun_position(12.0)
    assert el == pytest.approx(90.0 - W.DEFAULT_LATITUDE + W.declination(W.EQUINOX_DAY), abs=1e-6)
    assert az == pytest.approx(180.0, abs=1e-6)
    el, az = W.sun_position(18.0)
    assert abs(el) < 0.6 and abs(az - 270.0) < 1.0
    assert W.sun_position(23.0)[0] < -25.0                    # deep night
    assert W.sun_position(9.0)[1] == pytest.approx(360.0 - W.sun_position(15.0)[1], abs=1e-6)   # symmetric


def test_a_summer_day_in_the_north_sea():
    """21 June at 55° N: noon sun 58.4° high, the sun up from about 3:20 to 20:40 solar time (published day length
    at 55° N on the solstice: about 17 h 20 min)."""
    el, _ = W.sun_position(12.0, 172, 55.0)
    assert el == pytest.approx(90.0 - 55.0 + 23.44, abs=0.5)
    rise, sets = W.sunrise_sunset(172, 55.0)
    assert 16.9 < sets - rise < 17.6
    assert W.sun_position(rise, 172, 55.0)[0] == pytest.approx(0.0, abs=0.3)
    assert 30.0 < W.sun_position(rise, 172, 55.0)[1] < 60.0  # rises in the north-east
    assert W.sunrise_sunset(172, 75.0) is None                  # midnight sun
    st = W.State(hour=12.0, use_date=True, day=355, latitude=55.0)
    assert W.sun_of(st)[0] == pytest.approx(90.0 - 55.0 - 23.44, abs=0.6)   # winter: 11.6°


def test_scene_directions():
    """North at the back (+Y, scene azimuth 90), seen from above: the noon sun (south) stands in front (-90), the
    morning sun (east, clockwise from north) on the right (0), the evening sun (west) on the left (180)."""
    assert W.to_scene_az(180.0, 90.0) == pytest.approx(-90.0)
    assert W.to_scene_az(90.0, 90.0) == pytest.approx(0.0)
    assert abs(W.to_scene_az(270.0, 90.0)) == pytest.approx(180.0)
    for b in (0.0, 45.0, 200.0, 359.0):
        assert W.from_scene_az(W.to_scene_az(b, 33.0), 33.0) == pytest.approx(b % 360.0)


def test_twilight_and_night_channels():
    ch = {h: W.derive(W.State(hour=h, clouds=0.0)) for h in (7.0, 12.0, 17.5, 19.0, 23.0)}
    assert ch[12.0]["day"] == 1.0 and ch[12.0]["night"] == 0.0 and ch[12.0]["exposure"] == pytest.approx(0.0)
    assert ch[12.0]["sun"] == 1.0 and ch[12.0]["flood"] == 0.0
    assert 0.0 < ch[17.5]["exposure"] < 2.5                       # the eye opens up at sunset
    assert ch[19.0]["flood"] == 1.0 and ch[19.0]["sun"] == 0.0     # dusk: floodlights on (Auto)
    assert ch[23.0]["night"] == 1.0 and ch[23.0]["stars"] == 1.0 and ch[23.0]["moon"] > 0.9
    assert ch[23.0]["exposure"] == pytest.approx(2.0 + W.NIGHT_EV)
    assert ch[23.0]["moon_el"] > 20.0                             # the moon is up at night
    # the haze is dark at night and warm at a low sun
    assert sum(ch[23.0][c] for c in ("fog_r", "fog_g", "fog_b")) < 0.01
    assert ch[17.5]["fog_r"] > ch[17.5]["fog_b"] and ch[12.0]["fog_b"] > ch[12.0]["fog_r"]


def test_clouds_take_the_sun_away():
    clear, half, full = (W.derive(W.State(clouds=c)) for c in (0.0, 0.5, 1.0))
    assert clear["sun"] == 1.0 and half["sun"] == 1.0 and full["sun"] == 0.0
    assert W.derive(W.State(clouds=0.3, low_clouds=1.0))["sun"] == 0.0
    assert full["exposure"] == pytest.approx(0.5)


def test_visibility_is_the_fog_density():
    """Koschmieder: 3.912 / visibility; 40 km is today's clear air (nothing is added)."""
    for v in (40000.0, 5000.0, 400.0):
        assert W.derive(W.State(visibility=v))["fog"] == pytest.approx(3.912 / (v / 1000.0))
    assert W.derive(W.State(visibility=40000.0))["fog"] == pytest.approx(W.CLEAR_FOG)


@pytest.mark.parametrize("name", W.PRESET_ORDER)
def test_presets_give_channels_in_range(name):
    st = W.preset(name)
    ch = W.derive(st)
    assert set(ch) == set(W.CHANNEL_NAMES)
    for k, v in ch.items():
        lo, hi, _ = W.CHANNELS[k]
        assert lo - 1e-9 <= v <= hi + 1e-9, (name, k, v)
        assert not (0.0 < abs(v) < 1e-12)


def test_presets_look_like_their_names():
    night = W.derive(W.preset("NIGHT_SHIFT"))
    assert night["night"] == 1.0 and night["flood"] == 1.0 and night["stars"] > 0.3 and night["moon"] > 0.5
    storm = W.derive(W.preset("STORM"))
    assert storm["sun"] == 0.0 and storm["fog"] > 1.0 and storm["rain"] > 0.5
    clear = W.derive(W.preset("CLEAR_DAY"))
    assert clear["sun"] == 1.0 and clear["flood"] == 0.0 and clear["exposure"] < 0.1
    grey = W.derive(W.preset("GREY_NORTH_SEA"))
    assert grey["sun"] < 0.05 and grey["wet"] > 0.5
    snow = W.derive(W.preset("SNOW_QUAY"))
    assert snow["cover"] > 0.5 and snow["snow"] > 0.3
    base = W.State(north=10.0, latitude=60.0, wind_from=90.0)
    st = W.preset("STORM", base)
    assert (st.north, st.latitude, st.wind_from) == (10.0, 60.0, 90.0)       # a preset keeps the place


@pytest.mark.parametrize("el,rot", [(45.0, 0.0), (35.0, 40.0), (12.0, -115.0), (80.0, 170.0), (5.0, 300.0)])
def test_an_old_projects_sun_stays_where_it_was(el, rot):
    """Switching the weather on the first time keeps the sun of the old sky: same height, same direction (the
    direction the studio module gives for the old 'Rotate light', measured in Blender), a clear sky, no extra
    exposure."""
    st = W.from_old(el, rot, False, studio.SUN_AZ_AT_ZERO)
    ch = W.derive(st)
    assert ch["sun_el"] == pytest.approx(el, abs=0.05)
    want, _ = studio.main_light("SKY", "SUN", rot, el)
    assert ((ch["sun_az"] - want + 180.0) % 360.0 - 180.0) == pytest.approx(0.0, abs=1e-6)
    assert st.clouds == 0.0 and st.low_clouds == 0.0 and st.visibility == W.State().visibility
    if el >= 8.0:
        assert ch["exposure"] == pytest.approx(0.0, abs=1e-9)
        assert ch["sun"] == 1.0
    over = W.from_old(el, rot, True)
    assert over.clouds == 1.0 and over.low_clouds == 0.0


def test_fog_colour_is_the_horizon():
    """The haze radiance: the clear sky's horizon at a high sun (MULTIPLE_SCATTERING x 0.08, measured 0.8–1.4),
    dimmer under cloud, nearly black at night, smooth through the day."""
    hi = W.fog_level(45.0, 0.0, 0.0)
    assert 0.8 < hi < 1.4
    assert W.fog_level(45.0, 1.0, 0.0) < hi
    assert W.fog_level(45.0, 1.0, 1.0) < W.fog_level(45.0, 1.0, 0.0)
    assert W.fog_level(-30.0, 0.0, 0.0, night=1.0, moon=1.0) < 0.005
    prev = None
    for h in [x * 0.25 for x in range(97)]:
        ch = W.derive(W.State(hour=h, clouds=0.3))
        v = ch["fog_r"] + ch["fog_g"] + ch["fog_b"]
        if prev is not None:
            assert abs(v - prev) < 0.3                  # no jumps over a day
        prev = v


def test_sky_light_matches_the_world_expression():
    """The world shader and the fog use the same brightness curve (the driver text in weather_sky.SKY_LIGHT)."""
    for el in (-20.0, -9.0, 0.0, 10.0, 30.0, 60.0):
        t = min(max((el + 9.0) / 39.0, 0.0), 1.0)
        assert W.sky_light(el) == pytest.approx((t * t * (3 - 2 * t)) ** 1.5)


def test_mix_runs_the_clock_forward_and_fog_evenly():
    a, b = W.State(hour=22.0, visibility=40000.0), W.State(hour=2.0, visibility=400.0)
    m = W.mix(a, b, 0.5)
    assert m.hour == pytest.approx(0.0)
    assert m.visibility == pytest.approx(math.sqrt(40000.0 * 400.0))
    assert W.mix(a, b, 1.0) == b


def test_beaufort_round_trip():
    for b in (0.0, 3.0, 5.5, 9.0, 12.0):
        assert W.ms_to_bft(W.bft_to_ms(b)) == pytest.approx(b)
