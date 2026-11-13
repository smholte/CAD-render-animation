"""Weather & time (task 0109): tests written from the brief by an agent that did not write the code (CLAUDE.md
section 2, "Subagents"). They try to break it: Off = today, scripts off, the same every time, the step, saved
scenes, the material hook, snow on any mesh, work lights, indoors / photo, extreme values. The sea is left out
(another agent writes it). Made-up geometry and the test cranes only."""

from __future__ import annotations

import json
import math
import os

import pytest

from fresing_render.core import weather as core

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")


# ---------------------------------------------------------------------------
# pure Python: core/weather.py
# ---------------------------------------------------------------------------

EXTREMES = [
    core.State(),
    core.State(hour=0.0), core.State(hour=24.0), core.State(hour=23.999),
    core.State(visibility=50.0), core.State(visibility=100000.0), core.State(visibility=0.0),
    core.State(wind=0.0), core.State(wind=12.0), core.State(wind=12.0, wind_ref="BOW", wind_from=-360.0),
    core.State(clouds=1.0, low_clouds=1.0, rain=1.0, snow=1.0, snow_cover=1.0, wet=1.0, drop_size=6.0),
    core.State(flood_strength=4.0, floodlights="ON"), core.State(floodlights="OFF", hour=0.0),
] + [core.State(use_date=True, day=d, latitude=lat, hour=h)
     for d in (1, 80, 172, 355, 366) for lat in (-70.0, 0.0, 70.0) for h in (0.0, 6.0, 12.0, 24.0)]


@pytest.mark.parametrize("place", ["sky", "photo", "indoor"])
def test_derive_gives_every_channel_finite_for_extremes(place):
    for st in EXTREMES:
        ch = core.derive(st, place)
        assert set(ch) == set(core.CHANNELS), st
        for k, v in ch.items():
            assert isinstance(v, float) and math.isfinite(v), (st, k, v)
        for k in ("day", "night", "sun", "clouds", "low", "stars", "moon", "rain", "wet", "snow", "cover"):
            assert 0.0 <= ch[k] <= 1.0, (st, k, ch[k])
        assert -90.0 <= ch["sun_el"] <= 90.0 and -180.0 <= ch["sun_az"] <= 180.0
        assert -180.0 <= ch["moon_az"] <= 180.0
        assert abs(math.hypot(ch["wind_x"], ch["wind_y"]) - 1.0) < 1e-9
        assert ch["fog"] >= 0.0 and ch["wind"] >= 0.0
        # a driver result between 0 and ~1e-4 is written as 0 by Blender 5.2.3: the fog must not live there
        assert ch["fog"] == 0.0 or ch["fog"] > 1e-3


def test_hour_0_and_24_are_the_same_sky():
    for lat in (-70.0, 0.0, 55.0, 70.0):
        for day in (1, 172):
            a = core.derive(core.State(hour=0.0, use_date=True, day=day, latitude=lat))
            b = core.derive(core.State(hour=24.0, use_date=True, day=day, latitude=lat))
            for k in a:
                if k.endswith("_az"):
                    assert abs(((a[k] - b[k]) + 180.0) % 360.0 - 180.0) < 1e-6, (lat, day, k)
                else:
                    assert a[k] == pytest.approx(b[k], abs=1e-9), (lat, day, k)


def test_midnight_sun_and_polar_night():
    assert core.sunrise_sunset(172, 70.0) is None and core.sunrise_sunset(355, 70.0) is None
    assert core.sunrise_sunset(172, -70.0) is None
    summer_midnight = core.derive(core.State(hour=0.0, use_date=True, day=172, latitude=70.0))
    assert summer_midnight["sun_el"] > 0.0 and summer_midnight["night"] == 0.0
    winter_noon = core.derive(core.State(hour=12.0, use_date=True, day=355, latitude=70.0))
    assert winter_noon["sun_el"] < 0.0 and winter_noon["day"] < 0.5
    # south of the equator the noon sun stands in the north (bearing 0), north of the tropics in the south
    el, bearing = core.sun_position(12.0, 80, -40.0)
    assert el > 40.0 and min(bearing, 360.0 - bearing) < 1e-6
    el, bearing = core.sun_position(12.0, 80, 40.0)
    assert bearing == pytest.approx(180.0)
    # morning in the east, evening in the west, both hemispheres
    for lat in (-40.0, 40.0):
        assert 0.0 < core.sun_position(8.0, 80, lat)[1] < 180.0
        assert 180.0 < core.sun_position(16.0, 80, lat)[1] < 360.0


def test_sun_by_the_clock_is_symmetric_about_noon():
    for lat in (-60.0, 10.0, 55.0):
        for d in (1, 172):
            for dh in (1.0, 3.5, 7.0):
                e1, b1 = core.sun_position(12.0 - dh, d, lat)
                e2, b2 = core.sun_position(12.0 + dh, d, lat)
                assert e1 == pytest.approx(e2, abs=1e-9)
                assert (b1 + b2) % 360.0 == pytest.approx(0.0, abs=1e-6) or \
                    (b1 + b2) % 360.0 == pytest.approx(360.0, abs=1e-6)


def test_beaufort_round_trip_and_ends():
    for i in range(0, 121):
        b = i / 10.0
        assert core.ms_to_bft(core.bft_to_ms(b)) == pytest.approx(b, abs=1e-9)
    assert core.bft_to_ms(-3) == 0.0 and core.bft_to_ms(40) == core.BEAUFORT_MS[-1]
    assert core.ms_to_bft(500.0) == 12.0
    assert all(core.BEAUFORT_MS[i] < core.BEAUFORT_MS[i + 1] for i in range(12))


def test_wind_directions_compass_and_bow():
    # compass: the wind FROM the north blows towards the south; north is +Y by default
    x, y = core.wind_vector(core.State(wind_from=0.0, north=90.0))
    assert (x, y) == pytest.approx((0.0, -1.0), abs=1e-9)
    # from the east (bearing 90, clockwise from north seen from above: +X) it blows towards -X
    x, y = core.wind_vector(core.State(wind_from=90.0, north=90.0))
    assert (x, y) == pytest.approx((-1.0, 0.0), abs=1e-9)
    # from the bow (bow at -X): blows towards the stern, +X; from starboard (+Y) towards -Y
    assert core.wind_vector(core.State(wind_ref="BOW", wind_from=0.0)) == pytest.approx((1.0, 0.0), abs=1e-9)
    assert core.wind_vector(core.State(wind_ref="BOW", wind_from=90.0)) == pytest.approx((0.0, -1.0), abs=1e-9)
    # -360 … 360 all work and agree mod 360
    for f in (-360.0, -270.0, -90.0, 0.0, 90.0, 270.0, 360.0):
        a = core.wind_vector(core.State(wind_from=f))
        b = core.wind_vector(core.State(wind_from=f % 360.0))
        assert a == pytest.approx(b, abs=1e-9)


def test_mix_ends_and_short_ways():
    a = core.State(hour=10.0, wind_from=350.0, north=170.0, visibility=40000.0, rain=0.0)
    b = core.State(hour=9.0, wind_from=10.0, north=-170.0, visibility=40.0, rain=1.0, floodlights="ON")
    assert core.mix(a, b, 0.0) == a and core.mix(a, b, 1.0) == b
    assert core.mix(a, b, -2.0) == a and core.mix(a, b, 7.0) == b
    m = core.mix(a, b, 0.5)
    assert m.hour == pytest.approx(21.5)               # 10:00 -> 09:00 runs forward 23 h
    assert m.wind_from % 360.0 == pytest.approx(0.0, abs=1e-9) or m.wind_from % 360.0 == pytest.approx(360.0)
    assert abs(((m.north - 180.0) + 180.0) % 360.0 - 180.0) < 1e-9     # 170 -> -170 through 180
    assert m.floodlights == "ON" and core.mix(a, b, 0.49).floodlights == "AUTO"
    # the same hour: the clock does not run a whole day
    assert core.mix(core.State(hour=12.0), core.State(hour=12.0), 0.5).hour == pytest.approx(12.0)
    # continuity of the derived channels along a mix through midnight
    a, b = core.State(hour=22.0), core.State(hour=2.0)
    prev = None
    for i in range(101):
        ch = core.derive(core.mix(a, b, i / 100.0))
        if prev is not None:
            assert abs(ch["sun_el"] - prev["sun_el"]) < 2.0
        assert ch["sun_el"] <= core.derive(a)["sun_el"] + 1e-6         # never daylight between 22 and 2
        prev = ch


def test_presets_fit_the_panel_ranges():
    lim = dict(hour=(0, 24), clouds=(0, 1), low_clouds=(0, 1), visibility=(50, 100000), rain=(0, 1),
               drop_size=(0.5, 6), wet=(0, 1), snow=(0, 1), snow_cover=(0, 1), wind=(0, 12), flood_strength=(0, 4))
    for name in core.PRESET_ORDER:
        st = core.preset(name)
        for k, (lo, hi) in lim.items():
            assert lo <= getattr(st, k) <= hi, (name, k)
        assert st.floodlights in ("AUTO", "ON", "OFF")
        assert core.from_dict(core.as_dict(st)) == st
    assert core.from_dict({"hour": 3.0, "nonsense": 1}) == core.State(hour=3.0)


def test_from_old_keeps_the_sun_where_it_was_for_usual_heights():
    for el in (20.0, 30.0, 45.0, 60.0, 80.0):
        for rot in (-170.0, -90.0, 0.0, 40.0, 180.0):
            st = core.from_old(el, rot, False, 90.0)
            ch = core.derive(st)
            assert ch["sun_el"] == pytest.approx(el, abs=0.6), (el, rot)
            want = (90.0 - rot + 180.0) % 360.0 - 180.0
            assert abs(((ch["sun_az"] - want) + 180.0) % 360.0 - 180.0) < 0.01, (el, rot, ch["sun_az"])


@pytest.mark.xfail(reason="FOUND: core.from_old picks latitude 90 - sun height (up to 89), but the panel's "
                          "latitude is limited to -70 … 70 (props.FRWeather.latitude): an old project with a low "
                          "sun (height < ~19.5°) gets the sun at 19.5° when Weather & time is switched on",
                   strict=True)
def test_from_old_low_sun_fits_the_panel_latitude():
    for el in (5.0, 10.0, 15.0):
        st = core.from_old(el, 0.0, False, 90.0)
        assert -70.0 <= st.latitude <= 70.0, (el, st.latitude)


def test_words_never_fail():
    for st in EXTREMES:
        for place in ("sky", "photo", "indoor"):
            assert isinstance(core.words(st, place), str)
    assert core.clock(24.0) == "00:00" and core.clock(23.9999) == "00:00" and core.clock(-1.0) == "23:00"
    assert core.words(core.State(), "indoor") == "indoors"


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, fade, materials, queue, section, states,  # noqa: E402
                                    weather, weather_fx, weather_look, weather_sky, world)


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
    return sc.get(core.prop(name))


def update(sc):
    sc.update_tag()
    bpy.context.view_layer.update()


def _r(v):
    if isinstance(v, float):
        return round(v, 5)
    try:
        return tuple(_r(x) for x in v)
    except TypeError:
        return v if isinstance(v, (int, str, bool, type(None))) else str(type(v).__name__)


def _tree(nt):
    """A node tree as plain data (nodes by kind, place and inputs; links)."""
    if nt is None:
        return None
    nodes = []
    for n in nt.nodes:
        ins = tuple((i.identifier, _r(getattr(i, "default_value", None)), i.is_linked) for i in n.inputs)
        nodes.append((n.bl_idname, _r(tuple(n.location)), getattr(getattr(n, "node_tree", None), "name", None), ins))
    links = sorted((lk.from_node.bl_idname, _r(tuple(lk.from_node.location)), lk.from_socket.identifier,
                    lk.to_node.bl_idname, _r(tuple(lk.to_node.location)), lk.to_socket.identifier)
                   for lk in nt.links)
    drivers = sorted(fc.data_path for fc in nt.animation_data.drivers) if nt.animation_data else []
    return sorted(nodes), links, drivers


def fingerprint(sc):
    """Everything 'Off = today' must give back: world, view, compositor, materials, objects, collections, groups,
    lights, the scene's own properties and drivers."""
    sc.frame_set(1)                            # (the water's noise runs with the frame)
    bpy.context.view_layer.update()
    vl = sc.view_layers[0]
    ad = sc.animation_data
    out = {
        "world": (sc.world.name if sc.world else None, _tree(sc.world.node_tree if sc.world else None)),
        "view": (_r(sc.view_settings.exposure), sc.view_settings.look, sc.view_settings.view_transform,
                 _r(sc.view_settings.gamma)),
        # (render.use_compositing: its own test below, a fault found)
        "compositor": (getattr(sc.compositing_node_group, "name", None),
                       vl.use_pass_z, vl.use_pass_mist, sc.render.film_transparent),
        "scene_keys": sorted(k for k in sc.keys()),
        "scene_anim": None if ad is None else (getattr(ad.action, "name", None),
                                               sorted(fc.data_path for fc in ad.drivers)),
        "objects": sorted((o.name, o.type, getattr(o.parent, "name", None), o.hide_render, o.hide_viewport,
                           _r([x for row in o.matrix_world for x in row]),
                           tuple(getattr(s.material, "name", None) for s in o.material_slots),
                           tuple(m.name for m in o.modifiers), getattr(o.data, "name", None),
                           sorted(k for k in o.keys()))
                          for o in sc.objects),
        "collections": sorted((c.name, sorted(o.name for o in c.objects)) for c in bpy.data.collections if c.users),
        "node_groups": sorted(g.name for g in bpy.data.node_groups if g.users),
        "materials": sorted((m.name, _tree(m.node_tree), sorted(k for k in m.keys()))
                            for m in bpy.data.materials if m.users),
        "lights": sorted((l.name, _r(l.energy)) for l in bpy.data.lights if l.users),
        "meshes": sorted(m.name for m in bpy.data.meshes if m.users),
    }
    return out


def diff(a, b):
    return {k: (a[k], b[k]) for k in a if a[k] != b[k]}


def everything_on(sc):
    w = sc.fresing.weather
    w.enabled = True
    for name in core.PRESET_ORDER:
        weather.use_preset(sc, name)
    w.hour = 2.0
    w.rain = 0.6
    w.snow = 0.5
    w.snow_cover = 0.6
    w.wet = 0.8
    w.visibility = 300.0
    w.wind = 11.0
    w.flag = True
    w.floodlights = "ON"
    update(sc)
    return w


# ---------------------------------------------------------------------------
# Off = today, exactly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("background", ["QUAY", "SKY", "DECK"])
def test_off_after_everything_is_exactly_today(background):
    sc = fresh(background)
    sc.render.use_compositing = False          # the user's own choices the weather must give back
    sc.view_layers[0].use_pass_z = False
    sc.fresing.exposure = 0.7
    before = fingerprint(sc)
    everything_on(sc)
    assert sc.view_settings.exposure != pytest.approx(0.7)       # the night opens the camera up
    sc.fresing.weather.enabled = False
    after = fingerprint(sc)
    assert not diff(before, after), diff(before, after)


def test_off_after_changing_the_background_while_on_is_today():
    sc = fresh("QUAY")
    before = fingerprint(sc)
    everything_on(sc)
    for bg in ("SKY", "COLOR", "HDRI", "DECK", "QUAY"):
        sc.fresing.background = bg
    sc.fresing.weather.enabled = False
    after = fingerprint(sc)
    assert not diff(before, after), diff(before, after)


def test_off_after_a_built_and_cleared_step_is_today():
    sc = fresh("QUAY")
    before = fingerprint(sc)
    everything_on(sc)
    a, b = step_anim(sc, hour=18.0, rain=0.9)
    animation.bake(sc, a)
    animation.clear_keys(sc)
    sc.fresing.weather.enabled = False
    after = fingerprint(sc)
    d = diff(before, after)
    # (the scene's own animation tag of 'Build animation' is not the weather's: leave it out)
    if "scene_keys" in d:
        extra = set(after["scene_keys"]) - set(before["scene_keys"])
        assert not [k for k in extra if k.startswith(("fr_wx", "fr_weather"))], extra
        d.pop("scene_keys")
    if "materials" in d:                     # the sea's water runs with the time: Build set the animation's fps
        drop = lambda rows: [m for m in rows if "water" not in m[0]]   # noqa: E731
        assert drop(before["materials"]) == drop(after["materials"])
        d.pop("materials")
    if "scene_anim" in d:
        got = after["scene_anim"]
        assert got is None or (got[0] is None and not got[1]), got
        d.pop("scene_anim")
    assert not d, d


def test_exposure_follows_the_users_own_while_on_and_after():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")
    update(sc)
    sc.fresing.exposure = -1.0
    update(sc)
    assert sc.view_settings.exposure == pytest.approx(-1.0 + chan(sc, "exposure"), abs=1e-4)
    w.enabled = False
    update(sc)
    assert sc.view_settings.exposure == pytest.approx(-1.0, abs=1e-6)


@pytest.mark.xfail(reason="FOUND: weather_sky.fog_on sets scene.render.use_compositing = True and fog_off never "
                          "gives the user's own setting back (it does for the Z pass, FOG_PASS_Z): Off is not today",
                   strict=True)
def test_fog_off_gives_compositing_switch_back():
    sc = fresh("QUAY")
    sc.render.use_compositing = False
    sc.view_layers[0].use_pass_z = False
    weather_sky.fog_on(sc)                    # (straight: the panel loses the fog, the fault below)
    assert sc.compositing_node_group is not None and sc.view_layers[0].use_pass_z
    weather_sky.fog_off(sc)
    assert sc.view_layers[0].use_pass_z is False
    assert sc.render.use_compositing is False


@pytest.mark.xfail(reason="FOUND: the fog's compositor group is tagged 'fr_weather' (weather_sky._fog_nodes) and "
                          "weather_fx.remove deletes every node group with that tag; after_world runs fx after sky, "
                          "so the fog / mist / haze over the picture never exists (from the panel or a step)",
                   strict=True)
def test_fog_from_the_panel_is_laid_over_the_picture():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    w.visibility = 300.0
    assert sc.compositing_node_group is not None and sc.compositing_node_group.name == weather_sky.FOG_GROUP


def test_user_compositor_is_left_alone_by_the_fog():
    sc = fresh("QUAY")
    ng = bpy.data.node_groups.new("My compositor", "CompositorNodeTree")
    sc.compositing_node_group = ng
    w = sc.fresing.weather
    w.enabled = True
    w.visibility = 200.0
    assert sc.compositing_node_group == ng
    w.enabled = False
    assert sc.compositing_node_group == ng and bpy.data.node_groups.get("My compositor") is not None


# ---------------------------------------------------------------------------
# the parts work together: the night's lamps survive the rain/snow/flag part
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="FOUND: weather_fx.remove deletes every object tagged 'fr_weather' and the 'FR Weather' "
                          "collection - the same tag and collection weather_sky uses for the moonlight and the "
                          "floodlights. after_world runs sky.apply then fx.apply: with no rain/snow/flag "
                          "fx.apply -> remove() deletes the moon and the floodlights (Night shift has no lamps)",
                   strict=True)
def test_night_shift_has_moonlight_and_floodlights():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")
    roles = {o.get(weather_sky.TAG) for o in bpy.data.objects if o.get(weather_sky.TAG)}
    assert {"moon", "flood"} <= roles, roles


@pytest.mark.xfail(reason="FOUND: same fault as above - with rain the sky's lamps are deleted too "
                          "(weather_fx.remove(keep_collection=True) before rebuilding the rain)", strict=True)
def test_rainy_night_keeps_its_lamps():
    sc = fresh("DECK")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")
    w.rain = 0.5
    roles = {o.get(weather_sky.TAG) for o in bpy.data.objects if o.get(weather_sky.TAG)}
    assert {"moon", "flood", "rain"} <= roles, roles


def test_sky_lamps_alone_are_made_and_fx_alone_leaves_them_if_called_first():
    """The two parts on their own work (what their own tests see): the fault above is only in the order."""
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")
    st = weather.state(sc)
    weather_fx.apply(sc, st, "sky")
    weather_sky.apply(sc, st, "sky")
    roles = {o.get(weather_sky.TAG) for o in bpy.data.objects if o.get(weather_sky.TAG)}
    assert {"moon", "flood"} <= roles, roles


# ---------------------------------------------------------------------------
# scripts off: every driver is a simple expression on the scene's channels
# ---------------------------------------------------------------------------

def _all_owners():
    for coll in (bpy.data.objects, bpy.data.lights, bpy.data.worlds, bpy.data.node_groups, bpy.data.materials,
                 bpy.data.scenes, bpy.data.meshes, bpy.data.cameras):
        for idb in coll:
            yield idb
            nt = getattr(idb, "node_tree", None)
            if nt is not None:
                yield nt


def weather_drivers():
    out = []
    for idb in _all_owners():
        ad = getattr(idb, "animation_data", None)
        if ad is None:
            continue
        for fc in ad.drivers:
            paths = [t.data_path for v in fc.driver.variables for t in v.targets]
            if any("fr_wx_" in p or "fr_weather" in p for p in paths):
                out.append((idb, fc))
    return out


def test_every_weather_driver_is_a_simple_expression_on_the_scene():
    sc = fresh("QUAY")
    everything_on(sc)
    st = weather.state(sc)
    weather_sky.apply(sc, st, "sky")          # (the lamps, also while the fault above deletes them)
    drivers = weather_drivers()
    assert len(drivers) >= 5
    for idb, fc in drivers:
        d = fc.driver
        assert d.type in ("SCRIPTED", "AVERAGE", "SUM", "MIN", "MAX"), (idb.name, fc.data_path)
        if d.type == "SCRIPTED":
            assert d.is_simple_expression, (idb.name, fc.data_path, d.expression)
        assert d.is_valid, (idb.name, fc.data_path, d.expression)
        for v in d.variables:
            assert v.type == "SINGLE_PROP"
            t = v.targets[0]
            assert t.id_type == "SCENE" and t.id == sc, (idb.name, fc.data_path)


def test_render_does_not_need_python_handlers_after_reopening(tmp_path):
    """A background Blender opens the saved file: the channels, the drivers and the rain at a frame come from
    keys and simple expressions only - nothing may need a Python handler."""
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    a, b = step_anim(sc, hour=19.0, rain=0.8, start=0.2, seconds=2.0)
    res = animation.bake(sc, a)
    f = res["frames"] - 3
    sc.frame_set(f)
    want = {n: chan(sc, n) for n in core.CHANNEL_NAMES}
    want_exp = sc.view_settings.exposure
    rain_ob = weather_fx.find("rain")
    assert rain_ob is not None
    want_rain = _instances("rain")
    path = os.path.join(str(tmp_path), "wx.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    saved = {}
    for name in ("frame_change_pre", "frame_change_post", "depsgraph_update_pre", "depsgraph_update_post",
                 "load_post"):
        lst = getattr(bpy.app.handlers, name)
        saved[name] = list(lst)
        lst.clear()
    try:
        sc = bpy.context.scene
        sc.frame_set(1)
        sc.frame_set(f)
        got = {n: chan(sc, n) for n in core.CHANNEL_NAMES}
        for n in want:
            assert got[n] == pytest.approx(want[n], abs=1e-5), n
        assert sc.view_settings.exposure == pytest.approx(want_exp, abs=1e-5)
        got_rain = _instances("rain")
        assert len(got_rain) == len(want_rain) and np.allclose(got_rain, want_rain, atol=1e-6)
    finally:
        for name, lst in saved.items():
            getattr(bpy.app.handlers, name)[:] = lst


# ---------------------------------------------------------------------------
# the same every time
# ---------------------------------------------------------------------------

def _instances(role):
    ob = weather_fx.find(role)
    if ob is None:
        return np.zeros((0, 4, 4))
    dg = bpy.context.evaluated_depsgraph_get()
    out = [np.array(i.matrix_world) for i in dg.object_instances
           if i.is_instance and i.parent is not None and i.parent.original == ob]
    return np.array(out) if out else np.zeros((0, 4, 4))


def _points(role):
    ob = weather_fx.find(role)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        co = np.empty(3 * len(me.vertices), dtype=np.float32)
        me.vertices.foreach_get("co", co)
    finally:
        ev.to_mesh_clear()
    return co.reshape(-1, 3)


def test_rain_snow_flag_same_after_jumping_and_after_a_new_build():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    w.rain, w.snow, w.wind, w.flag = 0.7, 0.4, 7.0, True
    roles = {o.get(weather_fx.TAG) for o in weather_fx.objects(sc)}
    assert {"rain", "snow", "flag"} <= roles, roles
    shots = {}
    for f in (40, 3, 117, 40, 1, 40):
        sc.frame_set(f)
        got = (_instances("rain"), _instances("snow"), _points("flag"))
        if f in shots:
            for x, y in zip(shots[f], got):
                assert x.shape == y.shape and np.array_equal(x, y), f
        shots[f] = got
    first = shots[40]
    weather_fx.remove(sc)
    assert not weather_fx.objects(sc)
    weather.after_world(sc)
    sc.frame_set(40)
    again = (_instances("rain"), _instances("snow"), _points("flag"))
    for x, y in zip(first, again):
        assert x.shape == y.shape and np.allclose(x, y, atol=1e-6)
    # rain moves between frames (it is not standing still)
    sc.frame_set(41)
    assert not np.array_equal(_instances("rain"), first[0])


# ---------------------------------------------------------------------------
# the Weather & time step
# ---------------------------------------------------------------------------

def step_anim(sc, hour=18.5, rain=0.6, start=0.5, seconds=2.0, anim=None, easing="LINEAR"):
    s = sc.fresing
    if anim is None:
        anim = s.animations.add()
        anim.name, anim.tail, anim.quality, anim.fps = "Weather", 0.0, "draft", "25"
    b = anim.blocks.add()
    b.kind, b.start, b.duration, b.easing = "WEATHER", start, seconds, easing
    weather.step_init(sc, anim, b)
    b.wx_hour, b.wx_rain = hour, rain
    return anim, b


def series(sc, name, frames):
    out = []
    for f in frames:
        sc.frame_set(f)
        out.append(chan(sc, name))
    return out


def test_two_steps_in_a_row_chain_and_hold():
    sc = fresh("QUAY")
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")                       # 11:00
    a, b1 = step_anim(sc, hour=15.0, rain=0.0, start=0.0, seconds=1.0)
    _, b2 = step_anim(sc, hour=19.0, rain=0.5, start=2.0, seconds=1.0, anim=a)
    assert b2.wx_hour == pytest.approx(19.0)
    res = animation.bake(sc, a)
    st0 = weather.state(sc)
    end1 = weather.step_state(st0, b1)
    end2 = weather.step_state(end1, b2)
    f_end1, f_start2 = animation.frame_of(a, 1.0), animation.frame_of(a, 2.0)
    sc.frame_set(1)
    assert chan(sc, "sun_el") == pytest.approx(core.derive(st0)["sun_el"], abs=0.01)
    for f in (f_end1, (f_end1 + f_start2) // 2, f_start2):
        sc.frame_set(f)
        assert chan(sc, "sun_el") == pytest.approx(core.derive(end1)["sun_el"], abs=0.01), f
        assert chan(sc, "rain") == pytest.approx(0.0, abs=1e-6)
    sc.frame_set(res["frames"])
    assert chan(sc, "sun_el") == pytest.approx(core.derive(end2)["sun_el"], abs=0.01)
    assert chan(sc, "rain") == pytest.approx(0.5, abs=1e-6)
    sc.frame_set(res["frames"] + 30)                           # after the end: holds
    assert chan(sc, "rain") == pytest.approx(0.5, abs=1e-6)


def test_step_crossing_midnight_stays_dark():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    w.hour = 22.0
    a, b = step_anim(sc, hour=2.0, rain=0.0, start=0.0, seconds=2.0)
    res = animation.bake(sc, a)
    els = series(sc, "sun_el", range(1, res["frames"] + 1))
    start_el = core.derive(core.State(hour=22.0, latitude=w.latitude, north=w.north))["sun_el"]
    assert max(els) <= start_el + 0.01
    assert min(els) == pytest.approx(core.sun_position(0.0, core.EQUINOX_DAY, w.latitude)[0], abs=1.0)
    assert all(abs(x - y) < 3.0 for x, y in zip(els, els[1:]))
    assert all(v > 0.99 for v in series(sc, "night", range(1, res["frames"] + 1)))


def test_shortest_step_and_disabled_step():
    sc = fresh("QUAY")
    sc.fresing.weather.enabled = True
    a, b = step_anim(sc, hour=12.0, rain=1.0, start=0.0, seconds=0.0)       # clamped to the shortest step
    _, off = step_anim(sc, hour=12.0, rain=0.0, start=1.0, seconds=1.0, anim=a)
    _, fog = step_anim(sc, hour=12.0, rain=1.0, start=1.0, seconds=1.0, anim=a)
    fog.wx_visibility = 100.0
    fog.enabled = False
    off.enabled = False
    res = animation.bake(sc, a)
    sc.frame_set(1)
    assert chan(sc, "rain") == pytest.approx(0.0)
    sc.frame_set(res["frames"])
    assert chan(sc, "rain") == pytest.approx(1.0)                            # the disabled one did not stop it
    assert "fog" not in weather.keyed(sc)                                    # nor did the disabled fog step
    assert chan(sc, "fog") == pytest.approx(core.derive(weather.state(sc))["fog"])


@pytest.mark.xfail(reason="FOUND: weather.bake keys every frame of every step in start order; when two Weather & "
                          "time steps overlap, the frames of the overlap get two keys each (the first step's mix and "
                          "the second's, which starts from the first's END state): the sun jumps ~35° back and forth "
                          "frame by frame and no warning is given (joint steps warn about overlaps)", strict=True)
def test_overlapping_steps_never_jump_or_warn():
    """Two Weather & time steps that overlap: the channels must not jump about frame by frame (or the user is
    told the steps overlap)."""
    sc = fresh("QUAY")
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    a, b1 = step_anim(sc, hour=18.0, rain=0.0, start=0.0, seconds=2.0)
    _, b2 = step_anim(sc, hour=20.0, rain=0.0, start=1.0, seconds=2.0, anim=a)
    res = animation.bake(sc, a)
    warned = any("overlap" in x.lower() for x in res["warnings"])
    els = series(sc, "sun_el", range(1, res["frames"] + 1))
    jumps = max(abs(x - y) for x, y in zip(els, els[1:]))
    # one frame of the sun going from 11:00 to 18:00 over 2 s is ~1.3°; a jump to the first step's end is ~10°
    assert warned or jumps < 3.0, (jumps, res["warnings"])


def test_build_twice_gives_the_same_keys_and_clear_gives_the_panel_back():
    sc = fresh("QUAY")
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "GREY_NORTH_SEA")
    a, b = step_anim(sc, hour=21.0, rain=0.0)
    b.wx_visibility, b.wx_snow, b.wx_snow_cover = 900.0, 0.6, 0.7
    animation.bake(sc, a)
    k1 = _keys(sc)
    animation.bake(sc, a)
    k2 = _keys(sc)
    assert k1 == k2 and k1
    n_actions = len([x for x in bpy.data.actions if x.users])
    animation.bake(sc, a)
    assert len([x for x in bpy.data.actions if x.users]) == n_actions
    animation.clear_keys(sc)
    assert not weather.keyed(sc)
    want = core.derive(weather.state(sc))
    for n in core.CHANNEL_NAMES:
        assert chan(sc, n) == pytest.approx(want[n], abs=1e-6), n
    # snow and its look follow the panel again (no snow there)
    assert weather_fx.find("snow") is None


def _keys(sc):
    out = {}
    for fc in weather._scene_curves(sc):
        co = [0.0] * (2 * len(fc.keyframe_points))
        fc.keyframe_points.foreach_get("co", co)
        out[fc.data_path] = [round(x, 5) for x in co]
    return out


def test_snow_keyed_by_a_step_makes_flakes_and_the_snow_look():
    sc = fresh("QUAY")
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    assert weather_fx.find("snow") is None
    a, b = step_anim(sc, hour=12.0, rain=0.0)
    b.wx_snow, b.wx_snow_cover = 0.8, 0.9
    res = animation.bake(sc, a)
    sc.frame_set(1)
    assert chan(sc, "snow") == pytest.approx(0.0) and chan(sc, "cover") == pytest.approx(0.0)
    assert weather_fx.find("snow") is not None                   # snow falls in later frames
    ng = bpy.data.node_groups.get(weather_look.GROUP)
    assert ng is not None and str(ng.get("fr_sig", "")).endswith("1"), ng and ng.get("fr_sig")   # snow part built
    sc.frame_set(res["frames"])
    assert chan(sc, "cover") == pytest.approx(0.9)
    sc.frame_set(1)
    assert len(_instances("snow")) == 0
    sc.frame_set(res["frames"])
    assert len(_instances("snow")) > 50


def test_step_while_weather_is_off_starts_from_the_old_sky():
    sc = fresh("SKY")
    s = sc.fresing
    s.sun_elevation, s.light_rotation = 35.0, 10.0
    a, b = step_anim(sc, hour=17.0, rain=0.0, start=1.0, seconds=1.0)
    res = animation.bake(sc, a)
    assert s.weather.enabled
    sc.frame_set(1)
    assert chan(sc, "sun_el") == pytest.approx(35.0, abs=0.6)          # the project's own sun before the step


# ---------------------------------------------------------------------------
# saved scenes and the render queue
# ---------------------------------------------------------------------------

def test_saved_scenes_switch_weather_on_and_off_cleanly():
    sc = fresh("QUAY")
    before = fingerprint(sc)
    states.save_shot(sc, "Dry")                     # saved with the weather off
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "STORM")
    w.flag = True
    states.save_shot(sc, "Storm")
    states.apply_shot(sc, "Dry")
    assert not w.enabled
    after = fingerprint(sc)
    assert not diff(before, after), diff(before, after)
    states.apply_shot(sc, "Storm")
    assert w.enabled and w.flag and w.wind == pytest.approx(9.0)
    assert chan(sc, "rain") == pytest.approx(0.85)
    assert weather_fx.find("rain") is not None and weather_fx.find("flag") is not None
    assert any(weather_look.is_wrapped(m) for m in bpy.data.materials)


def test_saved_scene_with_broken_weather_data_does_not_fail():
    sc = fresh("QUAY")
    states.save_shot(sc, "X")
    shot = sc.fresing.shots["X"]
    data = json.loads(shot.world)
    data["weather"] = {"enabled": True, "hour": "noon", "wind_ref": "NOWHERE", "rain": 7.0, "unknown": 1}
    shot.world = json.dumps(data)
    states.apply_shot(sc, "X")
    w = sc.fresing.weather
    assert w.enabled and 0.0 <= w.rain <= 1.0 and w.wind_ref in ("NORTH", "BOW")
    data["weather"] = "garbage"
    shot.world = json.dumps(data)
    states.apply_shot(sc, "X")                      # (no exception)


def test_queue_fingerprint_is_stable_and_follows_the_weather():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "SNOW_QUAY")
    rows = list(queue._scene_settings(sc.fresing))
    text = repr(rows)
    assert "0x" not in text and "bpy" not in text and "<" not in text, text[:400]
    assert rows == list(queue._scene_settings(sc.fresing))
    a, b = step_anim(sc, hour=16.0, rain=0.3)
    animation.bake(sc, a)
    setup = {"frames": 10, "quality": "draft"}
    f1 = queue.fingerprint(sc, setup)
    assert f1 == queue.fingerprint(sc, setup)
    w.wind = 9.0
    assert queue.fingerprint(sc, setup) != f1


# ---------------------------------------------------------------------------
# the material hook
# ---------------------------------------------------------------------------

def _mat(name, mid="paint_gloss", colour="RAL 5010"):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    materials.build_nodes(m, mid, colour)
    return m


def _chain(mat):
    out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    sock, kinds = out.inputs["Surface"], []
    while sock.is_linked:
        node = sock.links[0].from_node
        kinds.append(node.node_tree.name if node.bl_idname == "ShaderNodeGroup" else node.bl_idname)
        if node.bl_idname != "ShaderNodeGroup":
            break
        sock = node.inputs[0]
    return kinds


@pytest.mark.parametrize("order", ["wfs", "wsf", "fws", "fsw", "swf", "sfw"])
def test_rebuild_keeps_fade_section_and_weather_in_every_order(order):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sng = section.node_group(sc)
    m = _mat("FR order " + order)
    for c in order:
        {"w": lambda: weather_look.wrap(m), "s": lambda: section.wrap(m, sng), "f": lambda: fade.wrap(m)}[c]()
    want = [fade.GROUP, section.GROUP, weather_look.GROUP]
    assert _chain(m)[:3] == want
    for mid in ("steel_machined", "paint_matte", "glass_clear"):        # a paint scheme: another look
        materials.build_nodes(m, mid, "RAL 1003")
        assert _chain(m)[:3] == want, (mid, _chain(m))
        outs = sum(1 for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"
                   and n.inputs["Surface"].is_linked)         # (glass has a second output: one group each)
        assert sum(1 for n in m.node_tree.nodes if weather_look._is(n, weather_look.GROUP)) == outs
    weather_look.unwrap(m)
    assert _chain(m)[:2] == [fade.GROUP, section.GROUP] and not weather_look.is_wrapped(m)
    materials.build_nodes(m, "paint_gloss", "RAL 5010")                 # unwrapped stays unwrapped
    assert not weather_look.is_wrapped(m)


def test_wrap_on_odd_materials_does_not_fail():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    odd = []
    m = bpy.data.materials.new("no output")
    m.use_nodes = True
    for n in list(m.node_tree.nodes):
        if n.bl_idname == "ShaderNodeOutputMaterial":
            m.node_tree.nodes.remove(n)
    odd.append(m)
    m = bpy.data.materials.new("unlinked output")
    m.use_nodes = True
    for lk in list(m.node_tree.links):
        m.node_tree.links.remove(lk)
    odd.append(m)
    m = bpy.data.materials.new("two outputs")
    m.use_nodes = True
    o2 = m.node_tree.nodes.new("ShaderNodeOutputMaterial")
    o2.target = "EEVEE"
    m.node_tree.links.new(m.node_tree.nodes["Principled BSDF"].outputs[0], o2.inputs["Surface"])
    odd.append(m)
    odd.append(None)
    for m in odd:
        weather_look.wrap(m)
        weather_look.wrap(m)
        weather_look.unwrap(m)
        assert m is None or not weather_look.is_wrapped(m)
    two = odd[2]
    weather_look.wrap(two)
    assert sum(1 for n in two.node_tree.nodes if weather_look._is(n, weather_look.GROUP)) == 2
    weather_look.unwrap(two)
    assert all(o.inputs["Surface"].links[0].from_node.bl_idname == "ShaderNodeBsdfPrincipled"
               for o in two.node_tree.nodes if o.bl_idname == "ShaderNodeOutputMaterial")


def test_wrapped_at_zero_renders_the_same_with_fade_and_section(tmp_path):
    """wet = cover = 0: a fade + section + weather material renders exactly as fade + section alone."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.7, 0.8, 1.0, 1.0)
    sc.world = w
    m = _mat("FR plate", "paint_gloss", "RAL 3000")
    fade.wrap(m)
    section.wrap(m, section.node_group(sc))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
    ob = bpy.context.active_object
    ob.data.materials.append(m)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.rotation_euler = (0.6, 0.3, 0.0)
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    sc.collection.objects.link(cam)
    cam.location = (0.0, -4.0, 1.0)
    cam.rotation_euler = (math.radians(80), 0.0, 0.0)
    sc.camera = cam
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x = r.resolution_y = 32
    r.resolution_percentage = 100
    sc.cycles.samples, sc.cycles.device, sc.cycles.use_denoising, sc.cycles.seed = 8, "CPU", False, 3

    def shot(name):
        r.filepath = os.path.join(str(tmp_path), name)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(r.filepath)
        px = np.array(img.pixels[:], dtype=np.float32)
        bpy.data.images.remove(img)
        return px
    plain = shot("plain.png")
    weather_look.node_group(True, True)
    weather_look.wrap(m)
    sc["fr_wx_wet"] = 0.0
    sc["fr_wx_cover"] = 0.0
    zero = shot("zero.png")
    assert np.abs(plain - zero).max() < 1.5 / 255.0
    sc["fr_wx_wet"] = 1.0
    wet = shot("wet.png")
    assert np.abs(plain - wet).max() > 0.02


# ---------------------------------------------------------------------------
# snow on any mesh
# ---------------------------------------------------------------------------

def _mesh(name, mats=(), slots=0, z=0.0, scale=(1, 1, 1), rot=(0, 0, 0), data=None):
    if data is None:
        data = bpy.data.meshes.new(name)
        data.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
        for m in mats:
            data.materials.append(m)
        for _ in range(slots):
            data.materials.append(None)
    ob = bpy.data.objects.new(name, data)
    ob.location.z = z
    ob.scale = scale
    ob.rotation_euler = rot
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _yard():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    return sc


def test_snow_targets_edge_cases():
    sc = _yard()
    shared = bpy.data.materials.new("shared")
    shared.use_nodes = True
    bare = _mesh("bare")
    empty_slot = _mesh("empty slot", slots=1)
    target = _mesh("target", mats=[shared])
    bystander = _mesh("bystander", mats=[shared], z=3.0)                 # not added: shares the material
    mirrored = _mesh("mirrored", mats=[shared], scale=(1, 1, -1), rot=(0.3, 0, 0))
    twin_data = _mesh("twin a").data
    twin_b = _mesh("twin b", data=twin_data)                              # a linked copy, not added
    empty = bpy.data.objects.new("an empty", None)
    sc.collection.objects.link(empty)
    curve = bpy.data.objects.new("a curve", bpy.data.curves.new("c", "CURVE"))
    sc.collection.objects.link(curve)
    twin_a = bpy.data.objects["twin a"]
    obs = [bare, empty_slot, target, mirrored, twin_a, empty, curve, None]
    assert weather_look.add_objects(sc, obs) == 5
    assert weather_look.add_objects(sc, obs) == 5                        # twice: the same
    assert set(weather_look.targets(sc)) == {bare, empty_slot, target, mirrored, twin_a}
    assert empty_slot.material_slots[0].material.get(weather_look.MADE)
    assert len(empty_slot.data.materials) == 1 and empty_slot.data.materials[0] is None   # mesh untouched
    assert weather_look.remove_objects(sc, [bystander, empty, None]) == 0  # never added: nothing
    sc["fr_wx_cover"] = 0.5
    weather_look.apply(sc, True)
    assert weather_look.is_wrapped(shared)
    assert sum(1 for n in shared.node_tree.nodes if weather_look._is(n, weather_look.GROUP)) == 1
    neutral = bpy.data.materials.get(weather_look.NEUTRAL)
    assert weather_look.is_wrapped(neutral)
    # a target object deleted, then apply on and off again
    bpy.data.objects.remove(mirrored)
    weather_look.apply(sc, True)
    weather_look.apply(sc, False)
    assert not any(weather_look.is_wrapped(m) for m in bpy.data.materials)
    weather_look.apply(sc, True)
    n = weather_look.remove_objects(sc, [bare, empty_slot, target, twin_a])
    assert n == 4 and not weather_look.targets(sc)
    assert not weather_look.is_wrapped(shared)                           # nobody needs it now
    assert len(bare.data.materials) == 0
    assert empty_slot.material_slots[0].material is None and empty_slot.material_slots[0].link == "DATA"
    assert len(twin_data.materials) == 0 and all(sl.material is None for sl in twin_b.material_slots)
    assert bpy.data.materials.get(weather_look.NEUTRAL) is None
    assert bystander.material_slots[0].material == shared


def test_snow_target_survives_weather_on_off_and_off_is_today():
    sc = fresh("QUAY")
    house = _mesh("house", z=2.0)
    weather_look.add_objects(sc, [house])
    before = fingerprint(sc)
    w = sc.fresing.weather
    w.enabled = True
    w.snow_cover = 0.8
    assert weather_look.is_wrapped(house.material_slots[0].material)
    assert house in weather_look.targets(sc)
    w.enabled = False
    after = fingerprint(sc)
    assert not diff(before, after), diff(before, after)
    assert house in weather_look.targets(sc)


# ---------------------------------------------------------------------------
# work lights
# ---------------------------------------------------------------------------

def _part(sc, i=0):
    parts = sorted((o for o in sc.objects if o.type == "MESH" and o.get(build.PROP_UID)
                    and o.get(build.PROP_KIND) == "part"), key=lambda o: o.name)
    return parts[i]


def test_work_lights_with_weather_off_on_and_removed():
    sc = fresh("COLOR")
    p = _part(sc)
    lamp = weather_sky.add_work_light(sc, p, kind="flood")          # lower case: still a flood
    spot = weather_sky.add_work_light(sc, _part(sc, 1), kind="nonsense")
    assert lamp[weather_sky.WORK_KIND] == "FLOOD" and spot[weather_sky.WORK_KIND] == "SPOT"
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "STORM")
    w.enabled = False
    assert set(weather_sky.work_lights(sc)) == {lamp, spot}
    name, data = spot.name, spot.data.name
    weather_sky.remove_work_light(sc, spot)
    assert bpy.data.objects.get(name) is None and bpy.data.lights.get(data) is None
    weather_sky.remove_work_light(sc, None)
    weather_sky.remove_work_light(sc, p)                             # a part, not a lamp: nothing happens
    assert p.name in sc.objects
    weather_sky.remove_work_light(sc, lamp)
    assert bpy.data.collections.get(weather_sky.WORK_COLLECTION) is None


def test_work_light_whose_part_was_deleted_then_a_model_update():
    sc = fresh("COLOR")
    p = _part(sc, 2)
    lamp = weather_sky.add_work_light(sc, p)
    name = lamp.name
    bpy.data.objects.remove(p)
    lamp = bpy.data.objects[name]
    assert lamp in weather_sky.work_lights(sc)
    assert weather.header(sc) == "Off"
    root = build.model_roots(sc)[0]
    res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name)
    assert res == {"FINISHED"}
    lamp = bpy.data.objects.get(name)
    assert lamp is not None and lamp in weather_sky.work_lights(sc)
    assert lamp.data is not None


def test_work_light_on_a_part_kept_through_two_updates():
    sc = fresh("COLOR")
    p = _part(sc, 0)
    lamp = weather_sky.add_work_light(sc, p)
    bpy.context.view_layer.update()
    world_before = lamp.matrix_world.copy()
    name = lamp.name
    for path in (CRANE_B, CRANE_A):
        root = build.model_roots(sc)[0]
        assert bpy.ops.fresing.import_step(filepath=path, quality="draft", update_root=root.name) == {"FINISHED"}
        bpy.context.view_layer.update()
        lamp = bpy.data.objects[name]
        assert lamp.parent is not None and lamp.parent.name in sc.objects
    # back on crane A: the lamp is where it was
    got = lamp.matrix_world
    assert max(abs(got[r][c] - world_before[r][c]) for r in range(4) for c in range(4)) < 1e-3
    assert len(weather_sky.work_lights(sc)) == 1


# ---------------------------------------------------------------------------
# indoors and the 360° photo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("background", ["COLOR", "HDRI"])
def test_indoor_and_photo_keep_their_own_light(background):
    sc = fresh(background)
    sc.fresing.exposure = 0.3
    world_before = _tree(sc.world.node_tree)
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")              # night: indoors and in a photo it must not get dark
    w.rain, w.snow = 0.8, 0.5
    update(sc)
    assert _tree(sc.world.node_tree) == world_before
    assert sc.view_settings.exposure == pytest.approx(0.3, abs=1e-5)
    roles = {o.get(weather_fx.TAG) for o in weather_fx.objects(sc)}
    if background == "COLOR":
        assert not roles & {"rain", "snow", "splash"}
        assert chan(sc, "wet") == 0.0 and chan(sc, "cover") == 0.0
    else:
        assert {"rain", "snow"} <= roles
    assert not {o.get(weather_sky.TAG) for o in bpy.data.objects if o.get(weather_sky.TAG)} & {"moon", "flood"}
    assert sc.compositing_node_group is None or sc.compositing_node_group.name != weather_sky.FOG_GROUP


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------

def test_extreme_settings_never_print_a_failure(capsys):
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    capsys.readouterr()
    for k, v in (("visibility", 50.0), ("wind", 12.0), ("hour", 0.0), ("hour", 24.0), ("use_date", True),
                 ("latitude", 70.0), ("day", 172), ("hour", 0.0), ("latitude", -70.0), ("day", 355),
                 ("hour", 12.0), ("day", 366), ("wind_ref", "BOW"), ("wind_from", -360.0), ("drop_size", 6.0),
                 ("rain", 1.0), ("snow", 1.0), ("snow_cover", 1.0), ("clouds", 1.0), ("low_clouds", 1.0),
                 ("flood_strength", 4.0), ("floodlights", "ON"), ("flag", True), ("visibility", 100000.0),
                 ("north", -360.0), ("wind", 0.0), ("flag", False), ("rain", 0.0), ("snow", 0.0)):
        setattr(w, k, v)
        for n in core.CHANNEL_NAMES:
            assert math.isfinite(chan(sc, n)), (k, v, n)
        assert isinstance(weather.header(sc), str)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "failed" not in text and "not set up" not in text and "Traceback" not in text, text[-2000:]


def test_world_apply_with_live_update_off():
    sc = fresh("QUAY")
    s = sc.fresing
    s.live_update = False
    w = s.weather
    w.enabled = True
    w.rain = 0.5
    world.apply(sc, s)
    assert chan(sc, "rain") == pytest.approx(0.5)
    assert weather_fx.find("rain") is not None
    w.enabled = False
    assert chan(sc, "rain") is None and weather_fx.find("rain") is None
    s.live_update = True


def test_weather_on_with_no_model_and_no_world():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.world = None
    sc.fresing.background = "QUAY"
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "STORM")
    weather.use_preset(sc, "NIGHT_SHIFT")
    w.flag = True
    assert isinstance(weather.header(sc), str)
    w.enabled = False
    assert not any(k.startswith(core.PREFIX) for k in sc.keys())


class _Any:
    """A stand-in for a UILayout that accepts every call (the panel's draw code runs through)."""

    def __init__(self):
        self.calls = 0

    def __getattr__(self, name):
        return self

    def __call__(self, *a, **k):
        self.calls += 1
        return self

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    def __bool__(self):
        return True

    def __iter__(self):                         # (header, body = layout.panel(...))
        return iter((self, self))


def test_panel_draw_runs_for_every_place():
    from types import SimpleNamespace
    from fresing_render.blender import ui_weather
    sc = fresh("QUAY")
    lamp = weather_sky.add_work_light(sc, _part(sc))
    assert lamp is not None
    errors = []
    for on in (False, True):
        sc.fresing.weather.enabled = on
        for bg in ("QUAY", "SEA", "SKY", "HDRI", "COLOR"):
            sc.fresing.background = bg
            lay = _Any()
            panel = SimpleNamespace(layout=lay)
            ctx = SimpleNamespace(scene=sc, region=SimpleNamespace(width=300), preferences=bpy.context.preferences,
                                  window_manager=bpy.context.window_manager, object=_part(sc),
                                  active_object=_part(sc), selected_objects=[_part(sc)],
                                  view_layer=bpy.context.view_layer)
            try:
                ui_weather.FRESING_PT_weather.draw(panel, ctx)
                ui_weather.FRESING_PT_weather.draw_header_preset(panel, ctx)
            except Exception as exc:            # (only a fault of the panel's own code counts: see the report)
                import traceback
                errors.append((on, bg, "".join(traceback.format_exception(exc))[-800:]))
            else:
                assert lay.calls > 3
    assert not errors, errors[0]


# ---------------------------------------------------------------------------
# a model update while the weather is on
# ---------------------------------------------------------------------------

def test_model_update_with_weather_on_keeps_everything_wet_and_the_rain_follows():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "GREY_NORTH_SEA")
    w.snow_cover = 0.5
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    bpy.context.view_layer.update()
    parts = [o for o in sc.objects if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    dry = sorted({m.name for o in parts for m in weather_look._materials(o)
                  if weather_look.wanted(m) and not weather_look.is_wrapped(m)})
    assert not dry, dry
    # the rain's 'tops' (where drops stop) were worked out for the model as it is now
    col = bpy.data.collections.get(weather_fx.COLLECTION)
    assert col is not None and weather_fx.find("rain") is not None
    assert col.get("fr_key") == weather_fx._key(sc, weather_fx.needs(sc, "sky"))
    assert chan(sc, "rain") == pytest.approx(0.15)


def test_dragging_a_weather_slider_stays_quick():
    """Live preview: one change of the clock rebuilds the world; it must not rebuild rain, lamps or looks."""
    import time
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    w.rain = 0.5
    rain = weather_fx.find("rain").name
    t = time.perf_counter()
    for i in range(10):
        w.hour = 8.0 + i * 0.5
    per = (time.perf_counter() - t) / 10
    assert weather_fx.find("rain").name == rain               # the same rain object: not made again
    assert per < 0.5, per                                     # (seconds per change, crane A, 4-core web machine)


def _fog_step(sc):
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    assert sc.compositing_node_group is None
    a, b = step_anim(sc, hour=11.0, rain=0.0)
    b.wx_visibility = 50.0
    return a, animation.bake(sc, a)


def test_fog_keyed_by_a_step_is_not_clamped():
    sc = fresh("QUAY")
    a, res = _fog_step(sc)
    assert weather_sky._fog_wanted(sc, "sky")                             # wanted: some frame has fog
    sc.frame_set(res["frames"])
    assert chan(sc, "fog") == pytest.approx(3.912 / 0.05, rel=1e-4)      # 78 per km: past the soft max 40


@pytest.mark.xfail(reason="FOUND: the same 'fr_weather' tag fault - a step that brings fog builds the fog group "
                          "(weather_sky) and weather_fx.remove deletes it in the same after_world", strict=True)
def test_fog_keyed_by_a_step_sets_up_the_fog():
    sc = fresh("QUAY")
    a, res = _fog_step(sc)
    assert sc.compositing_node_group is not None and sc.compositing_node_group.name == weather_sky.FOG_GROUP


def test_rain_object_deleted_by_hand_comes_back():
    sc = fresh("QUAY")
    w = sc.fresing.weather
    w.enabled = True
    w.rain = 0.4
    bpy.data.objects.remove(weather_fx.find("rain"))
    w.rain = 0.5
    assert weather_fx.find("rain") is not None
    col = bpy.data.collections.get(weather_fx.COLLECTION)
    bpy.data.collections.remove(col)
    w.rain = 0.6
    assert weather_fx.find("rain") is not None
    assert bpy.data.collections.get(weather_fx.COLLECTION).name in sc.collection.children


@pytest.mark.xfail(reason="FOUND (minor): weather_fx parents 'tops', 'splash', 'pole' and 'flag' to the model root "
                          "without fr_kind 'cnc' (weather_fx._new_object / _flag), so logic.Tree counts them inside "
                          "the model: a Hide / Fade step on the whole model keys and fades them, and those keys are "
                          "lost when the rain or flag is made again", strict=True)
def test_rain_and_flag_are_not_parts_of_the_model_tree():
    """weather_sky marks its helpers fr_kind 'cnc' so logic.Tree leaves them out; the rain's and the flag's objects
    ride on the model root too."""
    from fresing_render.blender import logic
    sc = fresh("QUAY")
    root = build.model_roots(sc)[0]
    n_parts = logic.part_count(root, logic.Tree(sc))
    w = sc.fresing.weather
    w.enabled = True
    w.rain, w.flag = 0.5, True
    tree = logic.Tree(sc)
    assert logic.part_count(root, tree) == n_parts
    inside = sorted(o.name for o in tree.descendants(root) if o.get(weather_fx.TAG) is not None)
    assert not inside, inside


@pytest.mark.xfail(reason="FOUND: switching Weather & time on in an old project with a low sun (Sun height 10°) "
                          "puts the sun at ~19.5°: core.from_old asks for latitude 79.5, props.FRWeather.latitude "
                          "clamps it to 70", strict=True)
def test_first_switch_keeps_a_low_old_sun():
    sc = fresh("SKY")
    s = sc.fresing
    s.sun_elevation, s.light_rotation = 10.0, 0.0
    s.weather.enabled = True
    assert chan(sc, "sun_el") == pytest.approx(10.0, abs=0.5)
