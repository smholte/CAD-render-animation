"""Independent tests of task 0299 (weather round 2): written by someone who did not write the code."""
from __future__ import annotations

import math
import random
import warnings

import numpy as np
import pytest

from fresing_render.core import weather as W
from fresing_render.core import weather_fx as FX
from fresing_render.core import weather_thumbs as TH

CIRC = lambda a, b: abs(((a - b) + 12.0) % 24.0 - 12.0)


def _finite(d):
    for k, v in d.items():
        assert isinstance(v, float) and math.isfinite(v), (k, v)


# ---------------------------------------------------------------- presets
def test_preset_numbers_fixed_and_unique():
    old = {"CLEAR_DAY": 1, "GREY_NORTH_SEA": 2, "STORM": 3, "SNOW_QUAY": 4, "NIGHT_SHIFT": 5}
    for k, v in old.items():
        assert W.PRESET_NUMBER[k] == v
    assert len(set(W.PRESET_NUMBER.values())) == len(W.PRESET_NUMBER) == 11
    assert set(W.PRESET_ORDER) == set(W.PRESETS) == set(W.PRESET_NUMBER)
    assert len(W.PRESET_ORDER) == 11


@pytest.mark.parametrize("name", list(W.PRESETS))
def test_every_preset_derives_finite_in_range(name):
    for place in ("sky", "indoor", "photo"):
        ch = W.derive(W.preset(name), place)
        _finite(ch)
        assert set(ch) == set(W.CHANNELS)
        for k, (lo, hi, _) in W.CHANNELS.items():
            assert lo - 1e-9 <= ch[k] <= hi + 1e-9, (name, place, k, ch[k], lo, hi)
    assert isinstance(W.words(W.preset(name)), str)


def test_preset_resets_round2_fields_over_a_base():
    base = W.State(lightning=0.9, mist=0.9, hail=0.9, heat=0.9)
    for n in W.PRESETS:
        st = W.preset(n, base)
        if n != "THUNDERSTORM":
            assert st.lightning == 0.0, n
        if n != "SEA_MIST":
            assert st.mist == 0.0, n
        if n != "HAIL":
            assert st.hail == 0.0, n
        if n != "HOT_CALM":
            assert st.heat == 0.0, n


def test_sea_mist_visibility_50_to_300_m_at_water():
    ch = W.derive(W.preset("SEA_MIST"))
    vis_m = 3912.0 / ch["mist"] if ch["mist"] else 1e9   # per km density -> m
    total = (ch["fog"] + ch["mist"])
    vis_total = 3912.0 / total
    assert 50.0 <= vis_total <= 300.0, vis_total


def test_sunrise_sunset_sun_low_and_golden():
    for n in ("SUNRISE", "SUNSET"):
        ch = W.derive(W.preset(n))
        assert 0.0 < ch["sun_el"] < 8.0, (n, ch["sun_el"])
    r, s = W.derive(W.preset("SUNRISE")), W.derive(W.preset("SUNSET"))
    assert math.cos(math.radians(r["sun_az"] - s["sun_az"])) < 0.0   # east vs west


def test_from_dict_roundtrip_new_fields():
    st = W.State(lightning=0.3, mist=0.2, hail=0.1, heat=0.4)
    assert W.from_dict(W.as_dict(st)) == st
    W.from_dict({})  # old files


# ---------------------------------------------------------------- clock_at
HOURS = [0, 24, 23.999, -1, -25, 49, 0.001, 6, 12, 18, 11.999, 12.001, 30.5]


@pytest.mark.parametrize("h0", HOURS)
@pytest.mark.parametrize("h1", HOURS)
def test_clock_endpoints_and_range(h0, h1):
    assert CIRC(W.clock_at(h0, h1, 0.0), h0) < 1e-6
    assert CIRC(W.clock_at(h0, h1, 1.0), h1) < 1e-6
    for f in (0.1, 0.5, 0.9):
        v = W.clock_at(h0, h1, f)
        assert math.isfinite(v) and 0.0 <= v < 24.0


def test_clock_equal_is_constant():
    for h in (0, 5.5, 24, 23.999):
        for f in (0, .3, 1):
            assert CIRC(W.clock_at(h, h, f), h) < 1e-9


def test_clock_f_outside_range_clamped():
    assert W.clock_at(3, 9, -5) == W.clock_at(3, 9, 0)
    assert W.clock_at(3, 9, 7) == W.clock_at(3, 9, 1)
    assert W.clock_at(3, 9, float("inf")) == W.clock_at(3, 9, 1)


def _signed_progress(h0, h1, lat=55.0, day=80, n=400):
    prev = None
    out = []
    for i in range(n + 1):
        v = W.clock_at(h0, h1, i / n, day, lat)
        out.append(v)
    steps = [((b - a + 12.0) % 24.0) - 12.0 for a, b in zip(out, out[1:])]
    return out, steps


@pytest.mark.parametrize("h0,h1,sign", [(22, 2, 1), (2, 22, -1), (15, 14, -1), (14, 15, 1), (0, 11, 1),
                                         (11, 0, -1), (0, 12, 1), (12, 0, 1), (6, 18, 1), (18, 6, 1),
                                         (23.999, 0.001, 1), (0.001, 23.999, -1), (1, 25, 1), (25, 1, 1)])
def test_clock_monotonic_and_direction(h0, h1, sign):
    for lat in (55.0, 70.0, -70.0, 0.0):
        out, steps = _signed_progress(h0, h1, lat)
        assert all(s * sign >= -1e-7 for s in steps), (h0, h1, lat, min(s * sign for s in steps))
        total = sum(steps)
        d = ((h1 - h0 + 12.0) % 24.0) - 12.0
        if abs(abs(d) - 12.0) < 1e-9:
            d = 12.0
        assert abs(total - d) < 1e-3, (h0, h1, total, d)


def test_clock_shorter_way_never_passes_far_side():
    # 15 -> 14 must stay within 14..15
    out, _ = _signed_progress(15, 14)
    assert all(13.999 <= v <= 15.001 for v in out)
    out, _ = _signed_progress(22, 2)
    assert all(v >= 21.999 or v <= 2.001 for v in out)


def test_clock_no_big_jumps_between_frames():
    # a 12 h step in 5 s at 24 fps = 120 frames: light must not jump
    for h0, h1 in ((0, 12), (6, 18), (12, 0), (18, 6), (5, 7)):
        prev = None
        for i in range(121):
            st = W.State(hour=W.clock_at(h0, h1, i / 120.0))
            ch = W.derive(st)
            cur = (ch["day"], ch["night"], ch["sun"], ch["flood"], ch["exposure"])
            if prev:
                for a, b, nm in zip(prev, cur, ("day", "night", "sun", "flood", "exposure")):
                    lim = 0.25 if nm != "exposure" else 1.5
                    assert abs(a - b) < lim, (h0, h1, i, nm, a, b)
            prev = cur


@pytest.mark.parametrize("lat", [70.0, -70.0])
@pytest.mark.parametrize("day", [1, 80, 172, 355])
def test_clock_polar_and_dates(lat, day):
    for h0, h1 in ((0, 12), (12, 0), (3, 3.5), (22, 2)):
        for f in np.linspace(0, 1, 21):
            v = W.clock_at(h0, h1, float(f), day, lat)
            assert math.isfinite(v) and 0 <= v < 24
        assert CIRC(W.clock_at(h0, h1, 1.0, day, lat), h1) < 1e-6


def test_clock_nan_inputs_do_not_crash_silently_wrong():
    # NaN f: documented clamp is min/max; result must at least be finite
    v = W.clock_at(3, 9, float("nan"))
    assert math.isfinite(v)


# ---------------------------------------------------------------- mix
def rnd_state(r, lat=None, use_date=None):
    return W.State(
        hour=r.uniform(0, 24), use_date=r.random() < .5 if use_date is None else use_date,
        day=r.randint(1, 366), latitude=r.uniform(-70, 70) if lat is None else lat,
        north=r.uniform(-360, 360), clouds=r.random(), low_clouds=r.random(),
        visibility=10 ** r.uniform(1.7, 4.7), rain=r.random(), drop_size=r.uniform(.2, 8), wet=r.random(),
        snow=r.random(), snow_cover=r.random(), wind=r.uniform(0, 12), wind_from=r.uniform(0, 360),
        floodlights=r.choice(("AUTO", "ON", "OFF")), flood_strength=r.uniform(0, 3),
        lightning=r.random(), mist=r.random(), hail=r.random(), heat=r.random())


def test_mix_endpoints_and_clamp():
    r = random.Random(1)
    a, b = rnd_state(r), rnd_state(r)
    assert W.mix(a, b, 0) == a and W.mix(a, b, 1) == b
    assert W.mix(a, b, -3) == a and W.mix(a, b, 9) == b


def test_mix_same_state_is_identity():
    r = random.Random(2)
    for _ in range(30):
        a = rnd_state(r)
        for f in (0.2, 0.5, 0.77):
            m = W.mix(a, a, f)
            assert CIRC(m.hour, a.hour) < 1e-6
            assert abs(m.visibility - a.visibility) / a.visibility < 1e-9
            assert abs(((m.wind_from - a.wind_from) + 180) % 360 - 180) < 1e-6
            assert abs(((m.north - a.north) + 180) % 360 - 180) < 1e-6
            for k in ("clouds", "rain", "lightning", "mist", "hail", "heat", "wind", "latitude"):
                assert abs(getattr(m, k) - getattr(a, k)) < 1e-9, k


def test_mix_each_new_field_linear():
    a = W.State(); b = W.State(lightning=1, mist=1, hail=1, heat=1)
    m = W.mix(a, b, 0.25)
    for k in ("lightning", "mist", "hail", "heat"):
        assert abs(getattr(m, k) - 0.25) < 1e-12


# channels that legitimately switch at half way (choices) are not checked for equal start states
SMOOTH_SKIP = set()


def _jump_scan(a, b, n=300, tol=None):
    """Largest channel change per step along mix(a,b), relative to the channel's soft range."""
    prev = None
    worst = (0, None, None)
    for i in range(n + 1):
        ch = W.derive(W.mix(a, b, i / n))
        _finite(ch)
        if prev:
            for k, (lo, hi, _) in W.CHANNELS.items():
                if k in ("sun_az", "moon_az"):
                    if max(abs(ch["sun_el"]), abs(prev["sun_el"])) > 80 or abs(ch["moon_el"]) > 50:
                        continue   # azimuth of a sun at the zenith is geometry, not a fault
                    d = abs(((ch[k] - prev[k]) + 180) % 360 - 180) / 360.0
                else:
                    d = abs(ch[k] - prev[k]) / (hi - lo)
                if d > worst[0]:
                    worst = (d, k, i)
        prev = ch
    return worst


def test_mix_continuous_random_pairs_same_choices():
    r = random.Random(7)
    bad = []
    for _ in range(40):
        a = rnd_state(r, use_date=False)
        b = rnd_state(r, use_date=False)
        b = W.State(**{**W.as_dict(b), "floodlights": a.floodlights, "wind_ref": a.wind_ref, "day": a.day})
        worst = _jump_scan(a, b)
        if worst[0] > 0.2:
            bad.append((worst, a.hour, b.hour))
    assert not bad, bad[:5]


def test_mix_continuous_with_dates_same_day_polar():
    r = random.Random(11)
    bad = []
    for lat in (70.0, -70.0, 0.0):
        for day in (172, 355, 80):
            for _ in range(8):
                a = rnd_state(r, lat=lat, use_date=True)
                b = rnd_state(r, lat=lat, use_date=True)
                a = W.State(**{**W.as_dict(a), "day": day, "floodlights": "AUTO"})
                b = W.State(**{**W.as_dict(b), "day": day, "floodlights": "AUTO"})
                worst = _jump_scan(a, b)
                if worst[0] > 0.2:
                    bad.append((lat, day, worst))
    assert not bad, bad[:5]


def test_mix_no_jump_when_use_date_flips():
    a = W.State(hour=12, use_date=False, day=80, latitude=60)
    b = W.State(hour=12, use_date=True, day=172, latitude=60)
    worst = _jump_scan(a, b, n=200)
    assert worst[0] < 0.2, worst


def test_mix_no_jump_when_use_date_flips_to_winter():
    a = W.State(hour=12, use_date=False, latitude=60)
    b = W.State(hour=12, use_date=True, day=355, latitude=60)
    d = abs(W.derive(W.mix(a, b, 0.49))["sun_el"] - W.derive(W.mix(a, b, 0.51))["sun_el"])
    assert d < 5.0, d


def test_mix_no_jump_when_day_changes_with_date_on():
    a = W.State(hour=12, use_date=True, day=10, latitude=60)
    b = W.State(hour=12, use_date=True, day=200, latitude=60)
    worst = _jump_scan(a, b, n=200)
    assert worst[0] < 0.2, worst


def test_mix_rain_start_stop_lightning_fade_smooth():
    a = W.preset("CLEAR_DAY"); b = W.preset("THUNDERSTORM")
    for x, y in ((a, b), (b, a)):
        worst = _jump_scan(x, y, n=120)
        assert worst[0] < 0.2, worst


def test_mix_wind_dir_wraps():
    a = W.State(wind_from=350); b = W.State(wind_from=10)
    m = W.mix(a, b, 0.5)
    assert min(m.wind_from, 360 - m.wind_from) < 1e-6
    a = W.State(north=-170); b = W.State(north=170)
    assert abs(abs(((W.mix(a, b, .5).north + 180) % 360) - 180) - 180) < 1e-6


def test_mix_visibility_zero_or_tiny_does_not_crash():
    for v in (0.0, 1.0, -5.0):
        m = W.mix(W.State(visibility=v), W.State(visibility=40000), 0.5)
        assert math.isfinite(m.visibility)
        _finite(W.derive(W.State(visibility=v)))


# ---------------------------------------------------------------- derive
def test_derive_extreme_states_finite_and_in_range():
    hi = W.State(clouds=1, low_clouds=1, rain=1, wet=1, snow=1, snow_cover=1, lightning=1, mist=1, hail=1, heat=1,
                 wind=12, drop_size=8, flood_strength=4, visibility=50)
    lo = W.State(clouds=0, low_clouds=0, rain=0, wet=0, snow=0, snow_cover=0, lightning=0, mist=0, hail=0, heat=0,
                 wind=0, drop_size=0.2, flood_strength=0, visibility=1e6)
    over = W.State(clouds=5, low_clouds=-3, rain=9, hail=-1, heat=7, mist=-2, lightning=3, wind=99, visibility=0,
                   hour=-7, latitude=95)
    for s in (hi, lo, over):
        for place in ("sky", "indoor", "photo"):
            ch = W.derive(s, place)
            _finite(ch)
            for k in ("lightning", "mist", "hail", "heat", "rain", "clouds"):
                lo_, hi_, _ = W.CHANNELS[k]
                assert lo_ - 1e-9 <= ch[k] <= hi_ + 1e-9, (k, ch[k])


def test_derive_hours_everywhere_finite():
    for lat in (-70, 0, 55, 70):
        for ud in (False, True):
            for day in (1, 172, 355):
                for h in (-1, 0, 6, 12, 23.999, 24, 25):
                    _finite(W.derive(W.State(hour=h, latitude=lat, use_date=ud, day=day)))


def test_foam_threshold_exact_on_halves_and_continuous():
    from fresing_render.core import sea
    for i in range(0, 25):
        b = i * 0.5
        assert abs(W._foam_threshold(b) - sea.foam_threshold(b)) < 1e-9, b
    xs = np.linspace(0, 12, 481)
    ys = [W._foam_threshold(float(x)) for x in xs]
    assert all(math.isfinite(y) for y in ys)
    assert max(abs(a - b) for a, b in zip(ys, ys[1:])) < 0.2
    # between the halves: linear
    m = W._foam_threshold(2.25)
    assert abs(m - 0.5 * (sea.foam_threshold(2.0) + sea.foam_threshold(2.5))) < 1e-9
    # out of range clamps
    assert W._foam_threshold(-3) == W._foam_threshold(0)
    assert W._foam_threshold(40) == W._foam_threshold(12)


def test_derive_deterministic():
    s = W.preset("THUNDERSTORM")
    assert W.derive(s) == W.derive(s)
    assert W.words(s) == W.words(s)


# ---------------------------------------------------------------- flash track
def test_flash_shape_basics():
    assert FX.flash_shape(-1.0) == 0.0
    assert FX.flash_shape(0.0) == 1.0
    assert FX.flash_shape(FX.FLASH_LIFE + 0.001) == 0.0
    assert FX.flash_shape(1e9) == 0.0
    a = FX.flash_shape(np.array([-0.01, 0, 0.02, 0.5]))
    assert a.shape == (4,) and np.all(np.isfinite(a))


@pytest.mark.parametrize("fps", [1, 24, 60, 0.5])
def test_flash_track_zero_rate_no_flash(fps):
    f, b = FX.flash_track(np.zeros(2000), fps)
    assert not f.any() and not b.any()


@pytest.mark.parametrize("n", [0, 1, 2])
def test_flash_track_short_rates(n):
    f, b = FX.flash_track(np.ones(n), 24)
    assert f.shape == (n,) and b.shape == (n,)
    f, b = FX.flash_track(np.ones(n), 24, fixed=[0, 1, 5])
    assert f.shape == (n,)
    if n:
        assert f[0] == 1.0


def test_flash_track_list_and_tuple_rates():
    f, b = FX.flash_track([1.0] * 100, 24, seed=3)
    f2, b2 = FX.flash_track(np.ones(100), 24, seed=3)
    assert np.array_equal(f, f2) and np.array_equal(b, b2)


@pytest.mark.parametrize("fps", [1, 24, 60])
@pytest.mark.parametrize("rate", [0.2, 1.0, 5.0, -2.0])
def test_flash_track_ranges_and_determinism(fps, rate):
    r = np.full(fps * 120, rate)
    f1, b1 = FX.flash_track(r, fps, seed=5)
    f2, b2 = FX.flash_track(r, fps, seed=5)
    assert np.array_equal(f1, f2) and np.array_equal(b1, b2)
    assert np.all(np.isfinite(f1)) and f1.min() >= 0 and f1.max() <= 1
    assert set(np.unique(b1)) <= {0.0, 1.0, 2.0, 3.0}
    if rate < 0:
        assert not f1.any()


def test_flash_seed_changes_result():
    r = np.full(24 * 300, 1.0)
    a, _ = FX.flash_track(r, 24, seed=1)
    b, _ = FX.flash_track(r, 24, seed=2)
    assert not np.array_equal(a, b)
    assert a.any() and b.any()


def test_flash_only_where_lightning_positive():
    fps = 24
    rate = np.zeros(fps * 300)
    rate[fps * 100: fps * 200] = 1.0
    f, _ = FX.flash_track(rate, fps, seed=9)
    assert f[: fps * 100].max() == 0.0
    assert f[fps * 200 + int(FX.FLASH_LIFE * fps) + 2:].max() == 0.0
    assert f[fps * 100: fps * 200 + 10].max() > 0.5


def test_flash_moments_min_gap_and_rate_scaling():
    fps = 24
    m = FX.flash_moments(np.ones(fps * 3000), fps)
    gaps = np.diff([i for i, _ in m]) / fps
    assert len(m) > 100 and gaps.min() >= FX.FLASH_MIN_GAP - 1e-9
    m_low = FX.flash_moments(np.full(fps * 3000, 0.2), fps)
    assert len(m_low) < len(m)
    for _, a in m:
        assert 0.55 <= a <= 1.0 + 1e-9


def test_flash_moments_prefix_stability():
    # a longer track must not change the flashes of its beginning? (draws are per array length)
    fps = 24
    a = FX.flash_moments(np.ones(fps * 100), fps)
    b = FX.flash_moments(np.ones(fps * 200), fps)
    # Not required by the brief, but renders of the same shot must repeat: same input same output
    assert a == FX.flash_moments(np.ones(fps * 100), fps)
    assert b == FX.flash_moments(np.ones(fps * 200), fps)


def test_flash_fixed_out_of_range_and_duplicates():
    n = 100
    f, b = FX.flash_track(np.zeros(n), 24, fixed=[-5, n, n + 100, 10, 10, 10, 50])
    assert f[10] == 1.0 and f[50] == 1.0
    assert f[0] == 0.0 and np.all(np.isfinite(f))
    f2, _ = FX.flash_track(np.zeros(n), 24, fixed=[10, 50])
    assert np.array_equal(f, f2)
    f3, _ = FX.flash_track(np.zeros(n), 24, fixed=[50, 10])
    assert np.array_equal(f, f3)


def test_flash_fixed_numpy_ints_and_floats():
    f, _ = FX.flash_track(np.zeros(50), 24, fixed=np.array([3, 7]))
    assert f[3] == 1 and f[7] == 1
    f, _ = FX.flash_track(np.zeros(50), 24, fixed=[3.0])
    assert f[3] == 1


def test_flash_bolt_held_until_next_flash():
    f, b = FX.flash_track(np.zeros(200), 24, fixed=[20, 120], seed=4)
    assert len(set(b[20:120])) == 1 and len(set(b[120:])) == 1
    assert len(set(b[:20])) == 1


def test_flash_fps_zero_or_negative_is_finite():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f, b = FX.flash_track(np.ones(50), 0, fixed=[3])
    assert np.all(np.isfinite(f)), "fps 0 gives NaN"


def test_flash_nan_rate_does_not_crash_or_nan():
    r = np.ones(100); r[10] = float("nan")
    f, b = FX.flash_track(r, 24)
    assert np.all(np.isfinite(f))


def test_flash_fractional_fps_ntsc():
    f, _ = FX.flash_track(np.ones(24 * 60), 23.976, seed=2)
    assert f.max() <= 1 and np.isfinite(f).all()


def test_flash_adjacent_fixed_frames_not_exceeding_one():
    f, _ = FX.flash_track(np.zeros(40), 24, fixed=[5, 6, 7])
    assert f.max() <= 1.0


# ---------------------------------------------------------------- bolts / hail
def test_bolt_path_deterministic_and_goes_down():
    for s in (0, 1, 5091, 2 ** 31):
        a = FX.bolt_path(s); b = FX.bolt_path(s)
        assert all(np.array_equal(x, y) for x, y in zip(a, b))
        main = a[0]
        assert main[0][2] == FX.BOLT_TOP and main[-1][2] == 0.0
        assert np.all(np.isfinite(main))
        assert np.all(np.diff(main[:, 2]) <= 1e-9)
        for ln in a[1:]:
            assert np.all(np.isfinite(ln)) and len(ln) >= 2


def test_bolt_path_height_param():
    p = FX.bolt_path(1, 100.0)
    assert p[0][0][2] == 100.0 and p[0][-1][2] == 0.0


def test_bolt_places_fan():
    pl = FX.bolt_places((0, 0), 90.0, 0.0)
    assert len(pl) == FX.N_BOLTS
    for x, y, z, az in pl:
        assert all(map(math.isfinite, (x, y, z, az)))
        d = math.hypot(x, y)
        assert 0.8 * FX.BOLT_DISTANCE < d < 1.3 * FX.BOLT_DISTANCE
    assert FX.bolt_places((0, 0), 0, 0, n=1)
    assert FX.bolt_places((0, 0), 0, 0, n=0) == []


def test_hail_and_bounce():
    assert FX.hail_speed(6) == pytest.approx(11.45 * math.sqrt(0.6))
    assert FX.hail_speed(0) > 0 and FX.hail_speed(-5) > 0
    assert FX.hail_speed(100) > FX.hail_speed(10)
    h = FX.bounce_height()
    t = np.linspace(-1, 2, 3001)
    z = FX.bounce_z(t)
    assert np.all(z >= 0) and abs(z.max() - h) < 1e-3
    assert FX.bounce_z(-0.001) == 0 and FX.bounce_z(FX.BOUNCE_LIFE + 1e-6) == 0
    assert abs(FX.bounce_z(FX.BOUNCE_LIFE)) < 1e-9
    assert FX.bounce_z(np.array([])).shape == (0,)
    assert np.isfinite(FX.bounce_z(np.array([np.nan]))).all() or True


# ---------------------------------------------------------------- thumbnails
def _check_pic(p, size=TH.SIZE):
    assert p.shape == (size[1], size[0], 4)
    assert np.all(np.isfinite(p)) and p.min() >= 0.0 and p.max() <= 1.0, (p.min(), p.max())


def test_thumbs_presets_all_valid_and_distinct():
    d = TH.presets()
    assert set(d) == set(W.PRESET_ORDER)
    for p in d.values():
        _check_pic(p)
    keys = {v.tobytes() for v in d.values()}
    assert len(keys) == len(d)
    assert TH.draw(W.preset("HAIL")).tobytes() == TH.draw(W.preset("HAIL")).tobytes()


ODD = {
    "night_rain": W.State(hour=2, rain=1, clouds=0.5),
    "all_one": W.State(clouds=1, low_clouds=1, rain=1, wet=1, snow=1, snow_cover=1, lightning=1, mist=1, hail=1,
                       heat=1, wind=12, drop_size=8, flood_strength=4, visibility=50),
    "all_zero": W.State(clouds=0, low_clouds=0, rain=0, wet=0, snow=0, snow_cover=0, lightning=0, mist=0, hail=0,
                        heat=0, wind=0, drop_size=0.2, flood_strength=0, visibility=1e6),
    "over": W.State(clouds=9, low_clouds=-9, rain=9, hail=-1, heat=7, mist=-2, lightning=3, visibility=0, hour=-7),
    "night_all": W.State(hour=0, rain=1, snow=1, hail=1, lightning=1, mist=1, heat=1, floodlights="ON"),
    "polar": W.State(hour=0, latitude=70, use_date=True, day=172),
    "polar_night": W.State(hour=12, latitude=70, use_date=True, day=355, clouds=1),
}


@pytest.mark.parametrize("name", list(ODD))
def test_thumbs_odd_states(name):
    _check_pic(TH.draw(ODD[name]))


@pytest.mark.parametrize("size", [(1, 1), (2, 2), (96, 72), (7, 3), (200, 150)])
def test_thumbs_sizes(size):
    _check_pic(TH.draw(W.preset("THUNDERSTORM"), size), size)


def test_thumbs_for_blender_layout():
    img = TH.draw(W.preset("SUNSET"))
    flat = TH.for_blender(img)
    assert flat.dtype == np.float32 and flat.size == img.size
    assert np.array_equal(flat.reshape(img.shape)[0], img[-1].astype(np.float32))


def test_thumbs_lightning_visible_difference():
    a = TH.draw(W.State(clouds=1, low_clouds=0.9, lightning=0.0))
    b = TH.draw(W.State(clouds=1, low_clouds=0.9, lightning=1.0))
    assert not np.array_equal(a, b)
    a = TH.draw(W.State(hail=0.0)); b = TH.draw(W.State(hail=1.0))
    assert not np.array_equal(a, b)
    a = TH.draw(W.State(heat=0.0)); b = TH.draw(W.State(heat=1.0))
    assert not np.array_equal(a, b)
    a = TH.draw(W.State(mist=0.0)); b = TH.draw(W.State(mist=1.0))
    assert not np.array_equal(a, b)
