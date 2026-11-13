"""Task 0109, the sky part: time of day, clouds, haze and fog, night lamps, floodlights and work lights
(``blender/weather_sky.py``, ``blender/world.py``)."""

from __future__ import annotations

import json
import math

import pytest

bpy = pytest.importorskip("bpy")


def _r(v):
    if isinstance(v, float):
        return round(v, 6)
    if hasattr(v, "__len__") and not isinstance(v, str):
        return [_r(x) for x in v]
    return v


def world_fingerprint(world) -> str:
    """Everything that decides how a world renders: nodes (type, place, settings, input values), links, drivers,
    plus the scene's exposure and film transparency."""
    nt = world.node_tree
    nodes = sorted(nt.nodes, key=lambda n: (n.bl_idname, tuple(n.location)))
    index = {n.name: i for i, n in enumerate(nodes)}
    rows = []
    for n in nodes:
        row = [n.bl_idname, _r(tuple(n.location))]
        for p in ("sky_type", "sun_elevation", "sun_rotation", "sun_intensity", "sun_disc", "operation", "data_type",
                  "blend_type", "air_density", "aerosol_density", "ozone_density", "altitude"):
            if hasattr(n, p):
                row.append([p, _r(getattr(n, p))])
        if getattr(n, "image", None) is not None:
            row.append(["image", n.image.name])
        for s in n.inputs:
            if s.enabled and not s.is_linked and hasattr(s, "default_value"):
                row.append([s.identifier, _r(s.default_value)])
        rows.append(row)
    links = sorted([index[l.from_node.name], l.from_socket.identifier, index[l.to_node.name], l.to_socket.identifier]
                   for l in nt.links)
    ad = nt.animation_data
    drivers = sorted(fc.data_path for fc in ad.drivers) if ad is not None else []
    sc = bpy.context.scene
    return json.dumps([rows, links, drivers, _r(sc.view_settings.exposure), sc.render.film_transparent])


# settings of older projects (weather off): their world must stay exactly as it was before task 0109
OLD_CASES = {
    "sky_sun": dict(background="SKY", sky_weather="SUN", sun_elevation=35.0, light_rotation=40.0, exposure=-1.0),
    "sky_overcast": dict(background="SKY", sky_weather="OVERCAST", light_rotation=0.0, exposure=0.0),
    "studio": dict(background="COLOR", lighting="STUDIO", light_rotation=20.0, light_strength=1.5),
    "product": dict(background="COLOR", lighting="PRODUCT", light_rotation=0.0, light_strength=1.0),
    "sea_sun": dict(background="SEA", sky_weather="SUN", sun_elevation=50.0, light_rotation=-60.0),
    "quay_overcast": dict(background="QUAY", sky_weather="OVERCAST", exposure=0.5),
    "transparent": dict(background="TRANSPARENT", lighting="DARK"),
}

GOLDEN = {                 # world_fingerprint of OLD_CASES, applied in this order, with the world.py of before 0109
    "sky_sun": "6b68c6cf3bd906a3",
    "sky_overcast": "6423eb7273d46765",
    "studio": "92ca1e7258cca6b3",
    "product": "133842cc2e7efb2a",
    "sea_sun": "5632c1ed0df41a35",
    "quay_overcast": "b74caa9f690918fa",
    "transparent": "41a686cae4f69bc4",
}

import hashlib  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import types  # noqa: E402

import addon_utils  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
import fresing_render.blender  # noqa: E402
from fresing_render.core import weather as W  # noqa: E402

from fresing_render.blender import build, weather, weather_sky as WS, world  # noqa: E402

CRANE = os.path.join(os.path.dirname(__file__), "..", "fresing_render", "data", "test_crane_a.step")


def _stubs() -> list:
    """The other agents' parts (looks, rain and snow) while they are not there yet: do-nothing stand-ins, taken
    away again after this file's tests."""
    made = []
    for name in ("weather_look", "weather_fx"):
        full = "fresing_render.blender." + name
        try:
            __import__(full)
        except ImportError:
            m = types.ModuleType(full)
            m.apply = lambda *a, **k: None
            m.remove = lambda *a, **k: None
            sys.modules[full] = m
            setattr(fresing_render.blender, name, m)
            made.append(name)
    return made


@pytest.fixture(scope="module", autouse=True)
def addon():
    stubs = _stubs()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()
    for name in stubs:
        sys.modules.pop("fresing_render.blender." + name, None)
        delattr(fresing_render.blender, name)


def fresh(background="QUAY", model=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    if model:
        assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.background = background
    return sc


def weather_on(sc, **kw):
    w = sc.fresing.weather
    w.enabled = True
    if kw:
        w["_busy"] = True
        for k, v in kw.items():
            setattr(w, k, v)
        del w["_busy"]
        weather.changed(sc)
    update(sc)
    return w


def update(sc):
    """Channels written from Python: tag the scene so the drivers read them (frames and keys do it by themselves)."""
    sc.update_tag()
    bpy.context.view_layer.update()


def made(role=None):
    return [o for o in bpy.data.objects if o.get(WS.TAG) and (role is None or o.get(WS.TAG) == role)]


def all_drivers(sc):
    """Every driver the weather's sky made: on the world tree, the scene, lamps, objects and the fog."""
    owners = [sc.world.node_tree, sc] + made() + [o.data for o in made() if o.data is not None]
    ng = bpy.data.node_groups.get(WS.FOG_GROUP)
    if ng is not None:
        owners.append(ng)
    for ow in owners:
        ad = getattr(ow, "animation_data", None)
        for fc in (ad.drivers if ad is not None else ()):
            yield ow, fc


def _render(sc, w, h, name="fr_sky_test.png"):
    p = os.path.join(bpy.app.tempdir or "/tmp", name)
    r = sc.render
    r.filepath = p
    r.image_settings.file_format = "PNG"
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p, check_existing=False)
    a = np.array(img.pixels[:]).reshape(h, w, 4)[:, :, :3]
    bpy.data.images.remove(img)
    return a


# ---------------------------------------------------------------------------

def test_weather_off_world_is_exactly_as_before():
    """Old projects (weather off): the world tree, exposure and film are the same as with the world.py of before
    this task – and the same again after the weather was switched on and off."""
    sc = fresh(model=False)
    s = sc.fresing
    s.live_update = False
    got = {}
    for name, settings in OLD_CASES.items():
        for k, v in settings.items():
            setattr(s, k, v)
        world.apply(sc, s)
        got[name] = hashlib.sha256(world_fingerprint(sc.world).encode()).hexdigest()[:16]
    assert got == GOLDEN
    s.live_update = True
    for name, settings in OLD_CASES.items():
        for k, v in settings.items():
            setattr(s, k, v)
        world.apply(sc, s)
        before = world_fingerprint(sc.world)
        s.weather.enabled = True
        s.weather.enabled = False
        assert world_fingerprint(sc.world) == before, name


def test_sun_rotation_zero_measured():
    """The sky texture's sun at sun_rotation 0 stands at the back (+Y), and rotation r puts it at 90 - r: a
    diffuse ball seen from the top is brightest towards the sun."""
    import bmesh
    sc = fresh(model=False)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 8
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    w = bpy.data.worlds.new("probe")
    sc.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = 0.08
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    me = bpy.data.meshes.new("ball")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    sc.collection.objects.link(bpy.data.objects.new("ball", me))
    cd = bpy.data.cameras.new("top")
    cd.type = "ORTHO"
    cd.ortho_scale = 2.2
    cam = bpy.data.objects.new("top", cd)
    cam.location = (0, 0, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sky.sun_elevation = math.radians(20.0)
    for want in (90.0, 0.0, -150.0):
        sky.sun_rotation = math.radians(WS.SUN_ROTATION_ZERO_AZ - want)
        a = _render(sc, 48, 48).sum(axis=2)
        ys, xs = np.nonzero(a >= np.quantile(a, 0.97))                    # the brightest spot's middle
        az = math.degrees(math.atan2(ys.mean() + 0.5 - 24, xs.mean() + 0.5 - 24))   # rows bottom-up: +Y
        assert abs((az - want + 180.0) % 360.0 - 180.0) < 6.0, (want, az)


def test_channels_drive_the_sky_by_simple_expressions():
    sc = fresh("SEA")
    weather_on(sc, visibility=400.0, floodlights="ON", hour=23.0)
    fcs = list(all_drivers(sc))
    assert len(fcs) > 20
    for ow, fc in fcs:
        assert fc.driver.is_simple_expression, (ow, fc.data_path, fc.driver.expression)
        assert fc.driver.is_valid, (ow, fc.data_path)
    sky = sc.world.node_tree.nodes["wx sky"]
    sc[W.prop("sun_el")] = 10.0
    sc[W.prop("sun_az")] = -30.0
    sc[W.prop("sun")] = 0.25
    update(sc)
    assert sky.sun_elevation == pytest.approx(math.radians(10.0), abs=1e-5)
    assert sky.sun_rotation == pytest.approx(math.radians(WS.SUN_ROTATION_ZERO_AZ + 30.0), abs=1e-5)
    assert sky.sun_intensity == pytest.approx(0.25, abs=1e-5)
    moon = made("moon")[0]
    sc[W.prop("moon")] = 1.0
    sc[W.prop("moon_el")] = 30.0
    sc[W.prop("moon_az")] = 45.0
    update(sc)
    assert moon.data.energy == pytest.approx(W.MOON_W, rel=1e-4)
    toward = -(moon.matrix_world.to_3x3() @ Vector((0, 0, -1)))     # from the scene to the moon
    e, a = math.radians(30.0), math.radians(45.0)
    assert (toward - Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))).length < 1e-4
    flood = made("flood")[0]
    sc[W.prop("flood")] = 0.0
    update(sc)
    assert flood.data.energy == 0.0
    sc[W.prop("flood")] = 1.0
    update(sc)
    assert flood.data.energy > 1.0


def test_old_projects_sun_stays_when_switched_on():
    """Switching the weather on the first time: the sky texture gets the same sun as before, at full strength."""
    sc = fresh("SKY", model=False)
    s = sc.fresing
    s.sky_weather = "SUN"
    s.sun_elevation = 30.0
    s.light_rotation = 40.0
    weather_on(sc)
    sky = sc.world.node_tree.nodes["wx sky"]
    assert sky.sun_elevation == pytest.approx(math.radians(30.0), abs=2e-3)
    assert sky.sun_rotation == pytest.approx(math.radians(40.0), abs=2e-3)
    assert sky.sun_intensity == pytest.approx(1.0)


def test_exposure_is_added_and_restored():
    sc = fresh("SKY", model=False)
    sc.fresing.exposure = -1.0
    weather_on(sc, hour=23.0)
    assert sc.view_settings.exposure == pytest.approx(-1.0 + 2.0 + W.NIGHT_EV, abs=1e-4)
    weather_on(sc, hour=12.0)
    assert sc.view_settings.exposure == pytest.approx(-1.0 + W.derive(weather.state(sc))["exposure"], abs=1e-4)
    sc.fresing.weather.enabled = False
    assert sc.view_settings.exposure == pytest.approx(-1.0)
    assert sc.animation_data is None or not len(sc.animation_data.drivers)


def test_fog_on_and_off():
    sc = fresh("SEA")
    vl = sc.view_layers[0]
    assert not vl.use_pass_z
    weather_on(sc, visibility=40000.0)
    assert sc.compositing_node_group is None                    # clear air: nothing over the picture
    weather_on(sc, visibility=400.0)
    assert sc.compositing_node_group is not None and sc.compositing_node_group.name == WS.FOG_GROUP
    assert vl.use_pass_z
    weather_on(sc, visibility=20000.0)
    assert sc.compositing_node_group is not None
    weather_on(sc, visibility=40000.0)
    assert sc.compositing_node_group is None and not vl.use_pass_z
    assert bpy.data.node_groups.get(WS.FOG_GROUP) is None


def test_fog_hides_the_far_sea():
    """A render: below the horizon the far sea turns into one grey at 400 m; the model close by stays."""
    sc = fresh("SEA")
    cd = bpy.data.cameras.new("T")
    cd.clip_end = 30000.0
    cam = bpy.data.objects.new("T", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.matrix_world = Matrix.Translation((0, -30, 4)) @ Matrix.Rotation(math.radians(86), 4, "X")
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.cycles.device = "CPU"
    weather_on(sc, visibility=40000.0, hour=13.0, clouds=0.0)
    clear = _render(sc, 48, 27)
    weather_on(sc, visibility=400.0)
    fog = _render(sc, 48, 27)
    near, far = slice(0, 5), slice(10, 13)          # rows bottom-up: sea tens of metres away / kilometres away
    assert np.abs(fog[:13] - clear[:13]).mean() > 0.03
    contrast = (lambda a: abs(a[near].mean() - a[far].mean()))
    assert contrast(fog) < 0.7 * contrast(clear)     # the sea fades into one grey


def test_floodlights_only_outdoors_by_the_water():
    for bgk, masts in (("QUAY", 3), ("DECK", 3), ("SEA", 0)):
        sc = fresh(bgk)
        weather_on(sc, hour=23.0)
        floods = made("flood")
        assert len(floods) == 4, bgk
        assert len(made("mast")) == masts, bgk
        assert all(o.get("fr_kind") == WS.HELPER_KIND for o in made())
        bpy.context.view_layer.update()
        assert all(f.data.energy > 1.0 for f in floods)
        parts = [o for o in sc.objects if o.get(build.PROP_KIND) == "part"]
        centre = sum((o.matrix_world.translation for o in parts), Vector()) / len(parts)
        for f in floods:                                     # each lamp aims at the model
            aim = f.matrix_world.to_3x3() @ Vector((0, 0, -1))
            assert aim.dot((centre - f.matrix_world.translation).normalized()) > 0.8, bgk
        weather_on(sc, hour=12.0)                            # Auto by day: no floodlights at all
        assert not made("flood") and not made("mast")
    for bgk in ("SKY", "COLOR"):
        sc = fresh(bgk)
        weather_on(sc, hour=23.0, floodlights="ON")
        assert not made("flood") and not made("mast"), bgk
        assert bool(made("moon")) == (bgk == "SKY")


def test_cheap_when_nothing_changed():
    sc = fresh("QUAY")
    weather_on(sc, hour=23.0, visibility=3000.0)
    names = sorted(o.name for o in made())
    for o in made():
        o["fr_test_mark"] = True
    weather_on(sc, hour=22.0, clouds=0.4)                  # only the channels change
    assert sorted(o.name for o in made()) == names
    assert all(o.get("fr_test_mark") for o in made())


def test_remove_leaves_nothing():
    sc = fresh("DECK")
    sc.fresing.exposure = 0.3
    vl = sc.view_layers[0]
    weather_on(sc, hour=23.0, visibility=400.0)
    assert made()
    sc.fresing.weather.enabled = False
    assert not made()
    assert bpy.data.collections.get(WS.COLLECTION) is None
    assert bpy.data.node_groups.get(WS.FOG_GROUP) is None and sc.compositing_node_group is None
    assert not vl.use_pass_z
    assert sc.world.node_tree.animation_data is None
    assert sc.view_settings.exposure == pytest.approx(0.3)
    assert sc.animation_data is None or not len(sc.animation_data.drivers)
    assert not [k for k in sc.keys() if k.startswith(W.PREFIX) or k.startswith("fr_weather")]
    assert not [m for m in bpy.data.materials if m.name.startswith("FR weather")]
    assert not [x for x in bpy.data.lights if x.name.startswith("FR weather")]
    assert not [m for m in bpy.data.meshes if m.name.startswith("FR weather")]


def _a_part(sc):
    parts = [o for o in sc.objects if o.get(build.PROP_KIND) == "part" and o.type == "MESH"]
    return max(parts, key=lambda o: (o.matrix_world.translation.z, o.name))


def _close(m1, m2, tol=1e-4):
    return max(abs(a - b) for ra, rb in zip(m1, m2) for a, b in zip(ra, rb)) < tol


def test_work_light_on_a_part():
    sc = fresh("COLOR")                                     # works with the weather off
    part = _a_part(sc)
    ob = WS.add_work_light(sc, part, "SPOT")
    bpy.context.view_layer.update()
    assert ob.parent == part and ob.type == "LIGHT" and ob.data.type == "SPOT"
    assert ob[WS.WORK_TAG] == part[build.PROP_UID] and ob.get("fr_kind") == WS.HELPER_KIND
    assert WS.work_lights(sc) == [ob]
    assert (ob.matrix_world.to_3x3() @ Vector((0, 0, -1))).z < 0.0     # lights the model, not the sky
    flood = WS.add_work_light(sc, part, "FLOOD")
    assert flood.data.spot_size > ob.data.spot_size
    before = ob.matrix_world.translation.copy()
    part.location.x += 1.0                                  # the part moves: the light with it
    bpy.context.view_layer.update()
    assert (ob.matrix_world.translation - before).length == pytest.approx(1.0, abs=1e-4)
    sc.fresing.background = "QUAY"                          # the weather on and off: the work lights stay
    weather_on(sc, hour=23.0)
    sc.fresing.weather.enabled = False
    assert set(WS.work_lights(sc)) == {ob, flood}
    WS.remove_work_light(sc, flood)
    assert WS.work_lights(sc) == [ob]


def test_work_light_follows_a_model_update():
    """With the mapping a model update gives, the lamp moves to the new copy of its part, at the same place on it
    (also when the old part was deleted first); a part that is gone leaves the lamp where it was."""
    sc = fresh("COLOR")
    part = _a_part(sc)
    ob = WS.add_work_light(sc, part)
    bpy.context.view_layer.update()
    local = part.matrix_world.inverted() @ ob.matrix_world
    uid = part[build.PROP_UID]
    new = part.copy()                                        # the new revision's part, moved a little
    new[build.PROP_UID] = uid + "-r2"
    sc.collection.objects.link(new)
    new.matrix_world = Matrix.Translation((0.3, -0.2, 0.1)) @ part.matrix_world
    bpy.context.view_layer.update()
    assert WS.after_model_update(sc, {uid: uid + "-r2"}) == []
    bpy.context.view_layer.update()
    assert ob.parent == new and ob[WS.WORK_TAG] == uid + "-r2"
    assert _close(new.matrix_world.inverted() @ ob.matrix_world, local)
    bpy.data.objects.remove(new)                             # parent deleted first
    newer = part.copy()
    newer[build.PROP_UID] = uid + "-r3"
    sc.collection.objects.link(newer)
    bpy.context.view_layer.update()
    WS.after_model_update(sc, {uid + "-r2": uid + "-r3"})
    bpy.context.view_layer.update()
    assert ob.parent == newer and _close(newer.matrix_world.inverted() @ ob.matrix_world, local)
    where = ob.matrix_world.translation.copy()
    notes = WS.after_model_update(sc, {uid + "-r3": "gone:" + uid + "-r3"})
    bpy.context.view_layer.update()
    assert notes and ob.parent is None and (ob.matrix_world.translation - where).length < 1e-5


def test_sky_light_curve_is_shared():
    assert WS.SKY_LIGHT == "pow(smoothstep(-9, 30, sun_el), 1.5)"      # = core.weather.sky_light
