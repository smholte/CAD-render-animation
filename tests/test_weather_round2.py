"""Weather round 2 (task 0299): the six new presets, lightning, sea mist, hail, heat, the pictures of the presets,
Change to ▸ a preset at the playhead, and smooth blending in a Weather & time step (no jumps, sampled per frame)."""

from __future__ import annotations

import math
import os
from dataclasses import replace

import numpy as np
import pytest

from fresing_render.core import weather as core
from fresing_render.core import weather_fx as fx
from fresing_render.core import weather_thumbs as thumbs

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
NEW = ("THUNDERSTORM", "SEA_MIST", "SUNRISE", "SUNSET", "HAIL", "HOT_CALM")
STEP_KEYS = ("hour", "clouds", "low_clouds", "visibility", "rain", "wet", "snow", "snow_cover", "wind", "wind_from",
             "drop_size", "lightning", "mist", "hail", "heat")


# ---------------------------------------------------------------------------
# the presets
# ---------------------------------------------------------------------------

def test_every_preset_is_listed_once_with_a_fixed_number():
    assert set(core.PRESET_ORDER) == set(core.PRESETS) and len(core.PRESET_ORDER) == 11
    assert set(NEW) <= set(core.PRESETS)
    # the numbers saved in project files: the five of 0.2.88 keep theirs, no number twice
    assert [core.PRESET_NUMBER[k] for k in ("CLEAR_DAY", "GREY_NORTH_SEA", "STORM", "SNOW_QUAY", "NIGHT_SHIFT")] == \
        [1, 2, 3, 4, 5]
    assert sorted(core.PRESET_NUMBER.values()) == list(range(1, 12))


def test_the_new_presets_values():
    ch = {k: core.derive(core.preset(k)) for k in NEW}
    st = {k: core.preset(k) for k in NEW}
    # thunderstorm: dark, a downpour, lightning
    assert ch["THUNDERSTORM"]["lightning"] > 0.5 and ch["THUNDERSTORM"]["rain"] == 1.0
    assert st["THUNDERSTORM"].low_clouds > 0.9 and ch["THUNDERSTORM"]["sun"] < 0.01
    # sea mist: 50–300 m at the water, calm
    at_water = 3.912 / ch["SEA_MIST"]["mist"] * 1000.0
    assert 50.0 <= at_water <= 300.0 and st["SEA_MIST"].wind <= 2.0
    # sunrise / sunset: a low sun (0–8°) in the morning / evening, golden light, no floodlights
    for k, morning in (("SUNRISE", True), ("SUNSET", False)):
        assert 0.0 < ch[k]["sun_el"] < 8.0 and (st[k].hour < 12.0) == morning
        assert core.warmth(ch[k]["sun_el"], st[k].clouds) > 0.4 and ch[k]["flood"] == 0.0
    # hail / sleet: hail, some rain, wet
    assert ch["HAIL"]["hail"] > 0.5 and ch["HAIL"]["rain"] > 0.0 and ch["HAIL"]["wet"] >= 0.8
    # hot and calm: heat, no wind to speak of, no rain
    assert ch["HOT_CALM"]["heat"] == 1.0 and st["HOT_CALM"].wind < 1.0 and ch["HOT_CALM"]["rain"] == 0.0
    # nothing new in the old presets
    for k in ("CLEAR_DAY", "GREY_NORTH_SEA", "STORM", "SNOW_QUAY", "NIGHT_SHIFT"):
        c = core.derive(core.preset(k))
        assert c["lightning"] == c["mist"] == c["hail"] == c["heat"] == 0.0


def test_a_preset_resets_what_another_preset_set():
    st = core.preset("THUNDERSTORM", core.preset("SEA_MIST", core.preset("HAIL")))
    assert st.mist == 0.0 and st.hail == 0.0 and st.lightning > 0.0
    assert core.preset("CLEAR_DAY", st).lightning == 0.0


def test_indoors_and_a_photo_show_no_new_sky_weather():
    st = replace(core.preset("THUNDERSTORM"), mist=1.0, heat=1.0, hail=1.0)
    for place in ("indoor", "photo"):
        c = core.derive(st, place)
        assert c["lightning"] == c["mist"] == c["heat"] == 0.0
    assert core.derive(st, "photo")["hail"] == 1.0           # hail falls in front of a photo, as rain does
    assert core.derive(st, "indoor")["hail"] == 0.0


def test_words_name_the_new_weather():
    assert "lightning" in core.words(core.preset("THUNDERSTORM"))
    assert "sea mist" in core.words(core.preset("SEA_MIST"))
    assert "hail" in core.words(core.preset("HAIL"))
    assert "heat haze" in core.words(core.preset("HOT_CALM"))


# ---------------------------------------------------------------------------
# smooth: the clock and the blend
# ---------------------------------------------------------------------------

def test_the_clock_goes_the_shorter_way_round():
    assert core.clock_at(22.0, 2.0, 0.5) == pytest.approx(0.0, abs=1e-6)       # forward through midnight
    assert 14.0 < core.clock_at(15.0, 14.0, 0.5) < 15.0                       # back an hour, not on through the night
    assert core.clock_at(1.0, 23.0, 0.5) in (pytest.approx(0.0, abs=1e-6), pytest.approx(24.0, abs=1e-6))
    for a, b in ((11.0, 23.0), (6.35, 17.65), (15.0, 14.0), (22.0, 2.0)):
        assert core.clock_at(a, b, 0.0) == pytest.approx(a % 24.0)
        assert core.clock_at(a, b, 1.0) == pytest.approx(b % 24.0)
    # twelve hours apart: forward
    assert 11.0 < core.clock_at(11.0, 23.0, 0.3) < 23.0


def test_the_clock_slows_down_through_sunset():
    """11:00 → 23:00 in 125 frames: the sun goes down over many frames, not in 1–3 as before task 0299."""
    hours = [core.clock_at(11.0, 23.0, i / 125.0) for i in range(126)]
    assert all(b > a for a, b in zip(hours, hours[1:]))                        # always forward
    rs = core.sunrise_sunset()
    sunset = [i for i, h in enumerate(hours) if rs[1] - 0.5 <= h <= rs[1] + 0.5]
    noon = [i for i, h in enumerate(hours) if 12.0 <= h <= 13.0]
    assert len(sunset) > 2.5 * len(noon)              # an hour round sunset gets far more frames than one at noon


def _sample(a: core.State, b: core.State, frames: int = 125):
    target = replace(a, **{k: getattr(b, k) for k in STEP_KEYS})
    ease = (lambda p: 0.5 - 0.5 * math.cos(math.pi * p))
    return [core.derive(core.mix(a, target, ease(i / frames))) for i in range(frames + 1)]


@pytest.mark.parametrize("start", core.PRESET_ORDER)
def test_a_change_between_any_two_presets_never_jumps(start):
    """Every channel sampled per frame, 5 s at 25 fps: no frame carries more than 12 % of the whole change (before
    task 0299 the direct sun went off in one frame: 60 %)."""
    for end in core.PRESET_ORDER:
        if end == start:
            continue
        rows = _sample(core.preset(start), core.preset(end))
        for name in rows[0]:
            if name in ("flash", "bolt"):
                continue
            v = np.array([r[name] for r in rows])
            d = np.diff(v)
            if name.endswith("_az"):
                d = (d + 180.0) % 360.0 - 180.0
            total = float(np.abs(d).sum())
            lo, hi, _ = core.CHANNELS[name]
            if total < 1e-6 or total < 0.002 * (hi - lo):
                continue
            assert float(np.abs(d).max()) <= 0.12 * total + 1e-9, (start, end, name, float(np.abs(d).max()), total)


def test_the_white_caps_number_is_exact_on_half_beaufort_and_straight_between():
    from fresing_render.core import sea
    for b in (0.0, 3.0, 5.5, 9.0):
        assert core._foam_threshold(b) == pytest.approx(sea.foam_threshold(b), abs=1e-12)
    lo, hi = sea.foam_threshold(5.0), sea.foam_threshold(5.5)
    assert core._foam_threshold(5.2) == pytest.approx(lo + (hi - lo) * 0.4, abs=1e-9)


# ---------------------------------------------------------------------------
# lightning, hail
# ---------------------------------------------------------------------------

def test_flashes_only_where_there_is_lightning():
    rate = np.r_[np.zeros(100), np.full(500, 0.8), np.zeros(200)]
    flash, bolt = fx.flash_track(rate, 25)
    on = np.nonzero(flash > 0.0)[0]
    assert len(on) and on.min() >= 100 and on.max() < 600 + int(fx.FLASH_LIFE * 25) + 1
    starts = [i for i, _a in fx.flash_moments(rate, 25)]
    assert all(b - a >= fx.FLASH_MIN_GAP * 25 for a, b in zip(starts, starts[1:]))
    assert set(np.unique(bolt).astype(int)) <= set(range(fx.N_BOLTS))
    assert not fx.flash_track(np.zeros(300), 25)[0].any()


def test_flashes_are_the_same_every_time_and_more_with_more_lightning():
    rate = np.full(25 * 60, 0.4)
    assert np.array_equal(fx.flash_track(rate, 25)[0], fx.flash_track(rate, 25)[0])
    few = len(fx.flash_moments(np.full(25 * 600, 0.2), 25))
    many = len(fx.flash_moments(np.full(25 * 600, 1.0), 25))
    assert many > 3 * few
    # about one flash every LIGHTNING_GAP s at lightning 1 (the minimum gap thins it a little)
    assert 0.6 * 600 / fx.LIGHTNING_GAP < many < 1.1 * 600 / fx.LIGHTNING_GAP


def test_a_flash_at_a_set_moment_and_its_flicker():
    flash, bolt = fx.flash_track(np.zeros(100), 25, fixed=(40,))
    assert flash[40] == pytest.approx(1.0) and flash[39] == 0.0
    assert flash[41] < flash[42]                       # a second stroke after the first dims
    assert flash[40 + int(round(fx.FLASH_LIFE * 25)) + 1:].max() == 0.0
    assert fx.flash_track(np.zeros(100), 50, fixed=(40,))[0][40:52].max() == pytest.approx(1.0)


def test_bolts_go_down_to_the_ground_and_stand_round_the_view():
    for seed in range(fx.SEED_BOLT, fx.SEED_BOLT + 4):
        lines = fx.bolt_path(seed)
        main = lines[0]
        assert main[0][2] == pytest.approx(fx.BOLT_TOP) and main[-1][2] == pytest.approx(0.0)
        assert np.all(np.diff(main[:, 2]) < 0.0) and 2 <= len(lines) - 1 <= 4
    places = fx.bolt_places((0.0, 0.0), 90.0, 0.0)
    assert len(places) == fx.N_BOLTS
    for x, y, z, az in places:
        assert abs(az - 90.0) <= fx.BOLT_SPREAD + 1e-9 and 0.8 * fx.BOLT_DISTANCE < math.hypot(x, y)


def test_hail_falls_at_its_speed_and_hops_once():
    assert fx.hail_speed(6.0) == pytest.approx(11.45 * math.sqrt(0.6))
    assert 8.0 < fx.hail_speed() < 12.0
    t = np.linspace(-0.1, fx.BOUNCE_LIFE + 0.1, 200)
    z = fx.bounce_z(t)
    assert z.max() == pytest.approx(fx.bounce_height(), rel=1e-3)
    assert z[t < 0].max() == 0.0 and z[t > fx.BOUNCE_LIFE].max() == 0.0


# ---------------------------------------------------------------------------
# the pictures of the presets
# ---------------------------------------------------------------------------

def test_every_preset_has_its_own_picture():
    pics = thumbs.presets()
    assert list(pics) == list(core.PRESET_ORDER)
    w, h = thumbs.SIZE
    for img in pics.values():
        assert img.shape == (h, w, 4) and img.min() >= 0.0 and img.max() <= 1.0
    keys = list(pics)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert np.abs(pics[a] - pics[b]).mean() > 0.01, (a, b)
    assert np.array_equal(thumbs.draw(core.preset("STORM")), pics["STORM"])        # the same every time
    # night is dark, clear day bright, sunset warm (red over blue in the sky)
    lum = {k: float(v[..., :3].mean()) for k, v in pics.items()}
    assert lum["NIGHT_SHIFT"] < 0.25 < lum["CLEAR_DAY"]
    glow = pics["SUNSET"][int(h * thumbs.HORIZON * 0.6): int(h * thumbs.HORIZON)]      # the sky over the horizon
    assert glow[..., 0].mean() > glow[..., 2].mean()
    assert thumbs.for_blender(pics["STORM"]).shape == (w * h * 4,)


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, states, weather, weather_sky  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(background="QUAY"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.env_detail = "SIMPLE"
    sc.fresing.background = background
    return sc


def chan(sc, name):
    return float(sc.get(core.prop(name), 0.0))


def frames_of(sc, names):
    out = []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        out.append([chan(sc, n) for n in names])
    return np.array(out)


def roles(sc):
    return [o.get("fr_weather") for o in sc.objects if o.get("fr_weather")]


def test_a_preset_from_its_button_sets_everything():
    sc = fresh()
    assert bpy.ops.fresing.weather_preset(name="HAIL") == {"FINISHED"}       # switches Weather & time on
    w = sc.fresing.weather
    assert w.enabled and w.preset == "HAIL" and w.hail == pytest.approx(0.8)
    assert "hail" in roles(sc) and "bounce" in roles(sc)
    bpy.ops.fresing.weather_preset(name="THUNDERSTORM")
    assert w.hail == 0.0 and "hail" not in roles(sc)
    assert roles(sc).count("bolt") == 4 and "lightning" in roles(sc)
    bpy.ops.fresing.weather_preset(name="SEA_MIST")
    assert "bolt" not in roles(sc)
    assert sc.compositing_node_group.name == weather_sky.FOG_GROUP and sc.view_layers[0].use_pass_position
    w.enabled = False
    assert not roles(sc) and sc.compositing_node_group is None and not sc.view_layers[0].use_pass_position


def test_change_to_at_the_playhead_adds_then_edits_a_step():
    sc = fresh()
    s = sc.fresing
    bpy.ops.fresing.weather_preset(name="CLEAR_DAY")
    sc.frame_set(1)
    s.weather.change_to, s.weather.change_seconds = "THUNDERSTORM", 3.0
    assert bpy.ops.fresing.weather_change() == {"FINISHED"}
    assert len(s.animations) == 1 and s.animations[0].name == weather.CHANGE_ANIM
    a = s.animations[0]
    b = a.blocks[0]
    assert (b.kind, b.start, b.duration, b.easing) == ("WEATHER", 0.0, 3.0, "SMOOTH")
    assert b.wx_lightning == pytest.approx(core.PRESETS["THUNDERSTORM"][2]["lightning"])
    assert animation.block_label(b) == "Weather to Thunderstorm (16:00)"
    assert weather.flash_times(b) == [pytest.approx(2.4)]                # one flash for sure, at 80 %
    s.weather.change_to = "SEA_MIST"                                      # the same playhead: that step changes
    bpy.ops.fresing.weather_change()
    assert len(a.blocks) == 1 and a.blocks[0].wx_mist > 0.5 and a.blocks[0].wx_lightning == 0.0
    sc.frame_set(1 + 25 * 6)                                              # later: a second step
    s.weather.change_to = "CLEAR_DAY"
    bpy.ops.fresing.weather_change()
    assert [round(x.start, 2) for x in a.blocks] == [0.0, 6.0]


def _storm_animation(sc):
    """Clear day → Thunderstorm at 0 s (2 s), → Clear day at 4 s (2 s): lightning only from 0 to 6 s."""
    s = sc.fresing
    bpy.ops.fresing.weather_preset(name="CLEAR_DAY")
    s.weather.change_seconds = 2.0
    sc.frame_set(1)
    s.weather.change_to = "THUNDERSTORM"
    bpy.ops.fresing.weather_change()
    sc.frame_set(1 + 25 * 4)
    s.weather.change_to = "CLEAR_DAY"
    bpy.ops.fresing.weather_change()
    a = s.animations[0]
    a.tail = 3.0
    animation.bake(sc, a)
    s.anim_baked = a.name
    return a


def test_lightning_only_within_its_steps_and_every_value_smooth():
    sc = fresh()
    _storm_animation(sc)
    names = [n for n in core.CHANNEL_NAMES if n not in ("flash", "bolt")]
    rows = frames_of(sc, names + ["flash"])
    lt, flash = rows[:, names.index("lightning")], rows[:, -1]
    on = np.nonzero(flash > 0.0)[0] + 1
    assert len(on), "no flash"
    assert on.min() > 1 and on.max() <= 1 + 25 * 6                       # within the two steps
    assert all(lt[f - 1] > 0.0 for f in on)                               # never before the storm or after it
    assert flash[1 + int(round(25 * 1.6)) - 1] > 0.5                       # the set flash of Change to (80 % of 2 s)
    assert lt[-1] == 0.0 and flash[-1] == 0.0
    # every channel per frame: no jump (a frame carries at most a fifth of a step's change)
    for k, name in enumerate(names):
        d = np.abs(np.diff(rows[:, k]))
        if name.endswith("_az"):
            d = np.abs((np.diff(rows[:, k]) + 180.0) % 360.0 - 180.0)
        total = d.sum()
        if total > 1e-6:
            assert d.max() <= 0.2 * total + 1e-6, (name, d.max(), total)
    assert {"bolt", "lightning", "rain"} <= set(roles(sc))


def test_save_and_reopen_keep_the_weather_and_its_keys(tmp_path):
    sc = fresh()
    _storm_animation(sc)
    w = sc.fresing.weather
    w.mist, w.heat, w.hail = 0.3, 0.2, 0.1
    before = frames_of(sc, ["lightning", "flash", "rain", "sun_el"])
    path = str(tmp_path / "storm.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    w = sc.fresing.weather
    assert (w.mist, w.heat, w.hail) == (pytest.approx(0.3), pytest.approx(0.2), pytest.approx(0.1))
    b = sc.fresing.animations[0].blocks[0]
    assert b.wx_preset == "THUNDERSTORM" and b.get(weather.STEP_VERSION) == 2
    after = frames_of(sc, ["lightning", "flash", "rain", "sun_el"])
    assert np.allclose(before, after, atol=1e-5)
    assert roles(sc).count("bolt") == 4


def test_a_still_picture_can_show_a_flash():
    sc = fresh("SEA")
    bpy.ops.fresing.weather_preset(name="THUNDERSTORM")
    assert chan(sc, "flash") == 0.0
    sc.fresing.weather.flash_still = True
    assert chan(sc, "flash") == pytest.approx(weather.STILL_FLASH)
    lamp = next(o for o in sc.objects if o.get("fr_weather") == "lightning")
    sc.update_tag()
    bpy.context.view_layer.update()
    assert lamp.data.energy == pytest.approx(weather.STILL_FLASH * weather_sky.LIGHTNING_W, rel=1e-4)
    sc.fresing.weather.lightning = 0.0                                    # no lightning: no flash, whatever the tick
    assert chan(sc, "flash") == 0.0


def test_a_step_from_before_keeps_the_weather_before_it_for_the_new_values():
    sc = fresh()
    s = sc.fresing
    bpy.ops.fresing.weather_preset(name="SEA_MIST")
    a = s.animations.add()
    b = a.blocks.add()
    b.kind, b.start, b.duration = "WEATHER", 0.0, 2.0
    weather.step_init(sc, a, b)
    del b[weather.STEP_VERSION]                                           # as saved by 0.2.88 … 0.2.221
    b.wx_mist, b.wx_drop_size = 0.0, 2.0                                  # (their defaults)
    end = weather.step_state(weather.state(sc), b)
    assert end.mist == pytest.approx(s.weather.mist) and end.drop_size == pytest.approx(s.weather.drop_size)
    b.wx_hail = 0.5                                                       # a new value set by hand: it counts now
    assert b.get(weather.STEP_VERSION) == 2
    end = weather.step_state(weather.state(sc), b)
    assert end.hail == 0.5 and end.mist == pytest.approx(s.weather.mist)


def test_a_start_scene_from_before_puts_the_new_values_back_to_none():
    sc = fresh()
    s = sc.fresing
    bpy.ops.fresing.weather_preset(name="CLEAR_DAY")
    shot = states.save_shot(sc, "Old")
    import json
    data = json.loads(shot.world)
    for k in states.WEATHER_LATER:
        data["weather"].pop(k, None)                                      # a scene saved before task 0299
    shot.world = json.dumps(data)
    s.weather.mist, s.weather.lightning = 0.6, 0.5
    changes = states.start_scene_changes(sc, "Old", ["weather"])
    assert {c[0] for c in changes} >= {"weather.mist", "weather.lightning"}
    states.apply_settings_json(sc, shot.world)
    assert s.weather.mist == 0.0 and s.weather.lightning == 0.0


def test_the_panel_draws_the_pictures_and_change_to():
    from fresing_render.blender import ui_weather
    sc = fresh()
    bpy.ops.fresing.weather_preset(name="SUNSET")
    assert ui_weather.thumb("SUNSET") >= 0                                # 0 without a window: never an error
    assert set(ui_weather.SHORT) == set(core.PRESET_ORDER)
    assert all(len(t) <= 12 for t in ui_weather.SHORT.values())           # fits a third of the side panel
    for op in ("weather_preset", "weather_change"):
        assert getattr(bpy.ops.fresing, op).get_rna_type().description
