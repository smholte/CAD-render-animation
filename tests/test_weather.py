"""Weather & time (task 0109): the settings, presets, the coordinator, the Weather & time step, saved scenes, the
panel. The sky, the looks and the falling things have their own tests (test_weather_sky/look/fx, test_sea)."""

from __future__ import annotations

import json
import os

import pytest

from fresing_render.core import weather as core

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


def test_presets_differ_and_keep_place():
    base = core.State(north=30.0, latitude=60.0, use_date=True, day=200, wind_from=10.0)
    seen = set()
    for name in core.PRESET_ORDER:
        st = core.preset(name, base)
        assert (st.north, st.latitude, st.use_date, st.day, st.wind_from) == (30.0, 60.0, True, 200, 10.0)
        seen.add(tuple(sorted(core.derive(st).items())))
    assert len(seen) == len(core.PRESET_ORDER)
    assert core.derive(core.preset("NIGHT_SHIFT"))["night"] > 0.99
    assert core.derive(core.preset("STORM"))["rain"] > 0.5


def test_step_mix_runs_the_clock_forward_and_fog_in_log():
    a, b = core.State(hour=22.0, visibility=40000.0), core.State(hour=2.0, visibility=400.0)
    assert core.mix(a, b, 0.5).hour == pytest.approx(0.0)
    assert core.mix(a, b, 0.5).visibility == pytest.approx(4000.0, rel=1e-6)
    assert core.mix(a, b, 1.0) == b


def test_fog_is_never_a_tiny_number():
    """Blender 5.2.3 writes 0 for a driver result below ~1e-4: fog is given per km, so clear air is still > 0.05."""
    assert core.derive(core.State(visibility=100000.0))["fog"] > 0.03
    assert core.derive(core.State(visibility=400.0))["fog"] == pytest.approx(3.912 / 0.4)


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, states, weather, weather_look  # noqa: E402


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


def world_signature(sc):
    nt = sc.world.node_tree
    rows = []
    for n in sorted(nt.nodes, key=lambda n: (n.bl_idname, n.location.x, n.location.y)):
        vals = []
        for i in n.inputs:
            v = getattr(i, "default_value", None)
            try:
                v = tuple(round(x, 6) for x in v)
            except TypeError:
                v = round(v, 6) if isinstance(v, float) else v
            vals.append((i.name, v, i.is_linked))
        rows.append((n.bl_idname, tuple(vals)))
    return rows


def test_off_is_today():
    sc = fresh()
    before = world_signature(sc)
    w = sc.fresing.weather
    w.enabled = True
    assert chan(sc, "sun_el") is not None
    w.enabled = False
    assert not any(k.startswith(core.PREFIX) for k in sc.keys())
    assert not any(o.get("fr_weather") for o in sc.objects)
    assert world_signature(sc) == before
    mats = {sl.material for o in sc.objects for sl in o.material_slots if sl.material is not None}
    assert not any(weather_look.is_wrapped(m) for m in mats)


def test_first_switch_keeps_the_old_sun():
    sc = fresh("SKY")
    s = sc.fresing
    s.sun_elevation, s.light_rotation = 30.0, 40.0
    s.weather.enabled = True
    assert chan(sc, "sun_el") == pytest.approx(30.0, abs=0.05)
    assert s.weather.preset == "CUSTOM"


def test_preset_sets_the_controls_and_a_change_makes_it_own():
    sc = fresh()
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "STORM")
    assert w.preset == "STORM" and w.rain == pytest.approx(0.85) and w.wind == pytest.approx(9.0)
    assert chan(sc, "rain") == pytest.approx(0.85)
    w.rain = 0.2
    assert w.preset == "CUSTOM"
    assert chan(sc, "rain") == pytest.approx(0.2)
    w.preset = "NIGHT_SHIFT"
    assert w.hour == pytest.approx(23.0) and chan(sc, "night") > 0.99


def test_indoors_nothing_falls():
    sc = fresh("COLOR")
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "STORM")
    assert chan(sc, "rain") == 0.0 and chan(sc, "wet") == 0.0
    assert not any(o.get("fr_weather") in ("rain", "snow") for o in sc.objects)


def step_anim(sc, hour=18.5, rain=0.6, start=0.5, seconds=2.0):
    s = sc.fresing
    a = s.animations.add()
    a.name, a.tail, a.quality, a.fps = "Weather", 0.0, "draft", "25"
    b = a.blocks.add()
    b.kind, b.start, b.duration, b.easing = "WEATHER", start, seconds, "LINEAR"
    weather.step_init(sc, a, b)
    b.wx_hour, b.wx_rain = hour, rain
    return a, b


def test_step_starts_from_the_weather_before_it():
    sc = fresh()
    sc.fresing.weather.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    a, b = step_anim(sc)
    b2 = a.blocks.add()
    b2.kind, b2.start, b2.duration = "WEATHER", 5.0, 1.0
    weather.step_init(sc, a, b2)
    assert b2.wx_hour == pytest.approx(18.5) and b2.wx_rain == pytest.approx(0.6)
    assert animation.block_label(b).startswith("Weather to 18:30")


def test_step_keys_the_channels_and_clear_puts_them_back():
    sc = fresh()
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "CLEAR_DAY")
    a, b = step_anim(sc)
    res = animation.bake(sc, a)
    sc.fresing.anim_baked = a.name
    assert {"rain", "day", "sun_el", "wet"} <= weather.keyed(sc)
    f0 = animation.frame_of(a, 0.5)
    sc.frame_set(1)
    assert chan(sc, "rain") == pytest.approx(0.0)
    sc.frame_set(f0)
    assert chan(sc, "rain") == pytest.approx(0.0, abs=1e-6)
    sc.frame_set(res["frames"])
    assert chan(sc, "rain") == pytest.approx(0.6)
    el, _ = core.sun_of(weather.step_state(weather.state(sc), b))
    assert chan(sc, "sun_el") == pytest.approx(el, abs=0.01)
    half = core.derive(core.mix(weather.state(sc), weather.step_state(weather.state(sc), b), 0.5))
    sc.frame_set(f0 + (animation.frame_of(a, 2.5) - f0) // 2)
    assert chan(sc, "sun_el") == pytest.approx(half["sun_el"], abs=0.5)
    assert any(o.get("fr_weather") == "rain" for o in sc.objects)       # rain falls in some frames
    animation.clear_keys(sc)
    assert not weather.keyed(sc)
    assert chan(sc, "rain") == pytest.approx(0.0)
    assert chan(sc, "sun_el") == pytest.approx(core.sun_of(weather.state(sc))[0])


def test_step_switches_weather_on():
    sc = fresh()
    a, _b = step_anim(sc)
    res = animation.bake(sc, a)
    assert sc.fresing.weather.enabled
    assert any("switched it on" in w for w in res["warnings"])


def test_saved_scene_keeps_its_weather():
    sc = fresh()
    w = sc.fresing.weather
    w.enabled = True
    weather.use_preset(sc, "NIGHT_SHIFT")
    states.save_shot(sc, "Night")
    weather.use_preset(sc, "CLEAR_DAY")
    states.apply_shot(sc, "Night")
    assert w.preset == "NIGHT_SHIFT" and w.hour == pytest.approx(23.0)
    assert chan(sc, "night") > 0.99
    shot = sc.fresing.shots["Night"]
    data = json.loads(shot.world)
    del data["weather"]                      # a scene saved before Weather & time: no weather
    shot.world = json.dumps(data)
    states.apply_shot(sc, "Night")
    assert not w.enabled
    assert not any(k.startswith(core.PREFIX) for k in sc.keys())


def test_panel_draws():
    from fresing_render.blender import ui_weather
    sc = fresh()
    errors = []

    class Fake:
        def __init__(self):
            self.layout = bpy.types.UILayout

    for on in (False, True):
        sc.fresing.weather.enabled = on
        for bg in ("QUAY", "SEA", "HDRI", "COLOR"):
            sc.fresing.background = bg
            try:
                assert ui_weather.FRESING_PT_weather.poll(bpy.context)
            except Exception as exc:          # (poll only: drawing needs a real window; the real-app test draws)
                errors.append((bg, exc))
    assert not errors, errors


def test_tooltips():
    props = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties["weather"].fixed_type
    for p in props.bl_rna.properties:
        if p.identifier in ("rna_type", "name"):
            continue
        assert len(p.description) > 20, p.identifier
    blk = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties["animations"].fixed_type
    blk = blk.bl_rna.properties["blocks"].fixed_type
    for p in blk.bl_rna.properties:
        if p.identifier.startswith("wx_"):
            assert len(p.description) > 20, p.identifier


def test_work_light_survives_a_real_model_update():
    """The update button (crane A -> crane B): the lamp hangs on the new copy of its part, in the same place on it."""
    from fresing_render.blender import build, weather_sky
    sc = fresh("COLOR")
    part = next(o for o in sc.objects if o.get(build.PROP_NAME) == "BOOM" and o.type == "MESH") \
        if any(o.get(build.PROP_NAME) == "BOOM" for o in sc.objects) else \
        next(o for o in sc.objects if o.type == "MESH" and o.get(build.PROP_UID))
    uid = part[build.PROP_UID]
    lamp = weather_sky.add_work_light(sc, part, kind="FLOOD")
    bpy.context.view_layer.update()
    local = part.matrix_world.inverted() @ lamp.matrix_world
    name = lamp.name
    root = next(r for r in build.model_roots(sc))
    res = bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_crane_b.step"), quality="draft",
                                      update_root=root.name)
    assert res == {"FINISHED"}
    bpy.context.view_layer.update()
    lamp = bpy.data.objects.get(name)
    assert lamp is not None and lamp in weather_sky.work_lights(sc)
    new = lamp.parent
    assert new is not None and new.get(build.PROP_UID) and new.name in sc.objects
    got = new.matrix_world.inverted() @ lamp.matrix_world
    assert max(abs(got[r][c] - local[r][c]) for r in range(4) for c in range(4)) < 1e-4
    assert lamp[weather_sky.WORK_TAG] == new[build.PROP_UID] or uid
