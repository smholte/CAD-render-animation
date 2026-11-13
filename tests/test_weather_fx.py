"""Rain, snow, splashes and the flag (task 0109): core/weather_fx.py and blender/weather_fx.py."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import weather as wcore
from fresing_render.core import weather_fx as core

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# core (no Blender)
# ---------------------------------------------------------------------------

def test_layout_is_the_same_every_time():
    a, b = core.layout(7, 500), core.layout(7, 500)
    for k in a:
        assert np.array_equal(a[k], b[k])
    c = core.layout(8, 500)
    assert not np.array_equal(a["u"], c["u"])
    assert a["u"].shape == (500, 3) and 0.0 <= a["u"].min() and a["u"].max() < 1.0
    assert 0.6 <= a["s"].min() and a["s"].max() <= 1.4


def test_fall_speed_follows_atlas():
    assert core.fall_speed(2.0) == pytest.approx(6.55, abs=0.05)
    assert core.fall_speed(5.0) == pytest.approx(9.13, abs=0.05)
    assert core.fall_speed(0.5) < core.fall_speed(1.0) < core.fall_speed(3.0) < 9.65
    r, length = core.streak(2.0)
    assert 1e-3 <= r <= 2e-3 and length == pytest.approx(6.55 / 50.0, abs=0.01)


def test_positions_stay_in_the_box_and_repeat_in_the_world():
    lay = core.layout(1, 2000)
    box = (10.0, 8.0, 6.0)
    o = core.box_origin((5.0, -3.0, 2.0), (0.0, 1.0, 0.0), box)
    v = core.rain_velocity(2.0, 10.0, 0.6, 0.8)
    p = core.positions(lay["u"], box, o, v, 3.7)
    assert np.all(p >= o - 1e-9) and np.all(p < o + np.array(box) + 1e-9)
    # the same frame twice: the same places; a drop moves with its velocity between two close frames
    assert np.array_equal(p, core.positions(lay["u"], box, o, v, 3.7))
    q = core.positions(lay["u"], box, o, v, 3.7 + 0.01)
    step = q - p
    ok = np.all(np.abs(step - np.array(v) * 0.01) < 1e-6, axis=1)
    assert ok.mean() > 0.95                                    # (the rest wrapped round)
    # moving the box does not move the drops in the world (only which copy shows)
    o2 = o + np.array([2.5, 0.0, 0.0])
    p2 = core.positions(lay["u"], box, o2, v, 3.7)
    both = (p[:, 0] >= o2[0]) & (p2[:, 0] < o[0] + box[0])
    assert np.allclose(p[both], p2[both])


def test_top_heights_see_a_roof_and_the_floor():
    floor = [[(0, 0, 0), (10, 0, 0), (10, 10, 0)], [(0, 0, 0), (10, 10, 0), (0, 10, 0)]]
    roof_down = [[(4, 4, 3), (6, 6, 3), (6, 4, 3)], [(4, 4, 3), (4, 6, 3), (6, 6, 3)]]        # faces down
    big = [[(-50, -50, -1), (50, -50, -1), (50, 50, -1)]]                                    # one huge triangle
    h, up = core.top_heights(floor + roof_down + big, 0.0, 0.0, 0.5, 20, 20)
    assert h[10, 10] == 3.0 and up[10, 10] == pytest.approx(-1.0)
    assert h[2, 2] == 0.0 and up[2, 2] == pytest.approx(1.0)
    assert np.isfinite(h).all()
    sp = core.splash_spots(h, up, 0.0, 0.0, 0.5, None)
    assert len(sp["p"]) == 400 - 16                            # none under the roof
    sp2 = core.splash_spots(h, up, 0.0, 0.0, 0.5, None)
    assert np.array_equal(sp["p"], sp2["p"])                   # seeded
    # water where nothing is above it
    h3, up3 = core.top_heights(floor, -5.0, 0.0, 0.5, 20, 20)
    sw = core.splash_spots(h3, up3, -5.0, 0.0, 0.5, water_z=-2.0)
    assert sw["water"].sum() == 200 and np.all(sw["p"][sw["water"] > 0.5][:, 2] == -2.0)


def test_top_heights_agree_with_a_brute_force_on_random_triangles():
    rng = np.random.default_rng(3)
    a = rng.random((300, 3)) * [10, 10, 2]
    tris = a[:, None, :] + (rng.random((300, 3, 3)) - 0.5) * [3, 3, 1]
    h, _up = core.top_heights(tris, 0.0, 0.0, 0.4, 25, 25, )
    for (j, i) in [(3, 4), (12, 12), (20, 7), (0, 24), (24, 0)]:
        px, py = 0.4 * (i + 0.5), 0.4 * (j + 0.5)
        best = -np.inf
        for t in tris:
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
            den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(den) < 1e-12:
                continue
            l1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / den
            l2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / den
            l3 = 1 - l1 - l2
            n = np.cross(t[1] - t[0], t[2] - t[0])
            if min(l1, l2, l3) >= 0 and abs(n[2] / np.linalg.norm(n)) > 1e-4:
                best = max(best, l1 * z1 + l2 * z2 + l3 * z3)
        assert h[j, i] == pytest.approx(best, abs=1e-9) or (np.isinf(best) and np.isinf(h[j, i]))


def test_flag_hangs_in_calm_and_flies_in_wind():
    u, v, faces = core.flag_grid()
    L, H = 1.2, 0.8
    for t in (0.0, 1.3):
        for w in (0.0, 12.0):
            p = core.flag_points(u, v, t, w, L, H)
            hoist = u == 0.0
            assert np.allclose(p[hoist, 0], 0.0) and np.allclose(p[hoist, 1], 0.0)
            assert np.allclose(p[hoist, 2], (v[hoist] - 1.0) * H)
    calm = core.flag_points(u, v, 0.0, 0.0, L, H)
    windy = core.flag_points(u, v, 0.0, 12.0, L, H)
    fly = u == 1.0
    assert calm[fly, 2].max() < -0.9 * L                       # limp: the fly end hangs down
    assert windy[fly, 0].min() > 0.9 * L                        # flies straight out
    assert np.allclose(windy[fly & (v == 1.0), 2], 0.0, atol=1e-9)
    # it waves: the same moment twice is the same, another moment differs
    assert np.array_equal(windy, core.flag_points(u, v, 0.0, 12.0, L, H))
    assert np.abs(core.flag_points(u, v, 0.4, 12.0, L, H) - windy).max() > 0.05
    assert core.flag_frequency(12.0, L) > core.flag_frequency(3.0, L)
    assert core.flag_heading(0.0, 1.0) == pytest.approx(math.pi / 2)


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import cameras, weather, weather_fx, world  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh(background="QUAY", flag=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.background = background
    world.apply(sc, sc.fresing)
    sc.camera = cameras.add_camera(sc, "ISO", 50.0, "T")
    w = sc.fresing.weather
    w["_busy"] = True
    w.flag = flag
    del w["_busy"]
    return sc


def _weather(sc, **kw):
    st = wcore.State(**kw)
    weather.write_channels(sc, wcore.derive(st, wcore.where(sc.fresing.background)))
    weather_fx.apply(sc, st, wcore.where(sc.fresing.background))
    return st


def _instances(sc, role):
    ob = weather_fx.find(role)
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob:
            out.append(np.array(inst.matrix_world))
    return np.array(out)


def _full(ob):
    """Render counts in the 3D view too (the view shows only a share)."""
    mod = ob.modifiers[weather_fx.MOD]
    weather_fx._set_input(mod, mod.node_group, "Viewport", 1.0)


def test_nothing_without_rain_snow_or_flag_and_nothing_indoors():
    sc = _fresh()
    _weather(sc, rain=0.0, snow=0.0)
    assert not weather_fx.objects(sc) and bpy.data.collections.get(weather_fx.COLLECTION) is None
    sc.fresing.background = "FACTORY"
    weather.write_channels(sc, wcore.derive(wcore.State(rain=1.0), "indoor"))
    weather_fx.apply(sc, wcore.State(rain=1.0), "indoor")
    assert not weather_fx.objects(sc)


def test_rain_comes_when_a_step_keys_it_and_remove_leaves_nothing():
    sc = _fresh(flag=True)
    _weather(sc, rain=0.0)
    assert {o.get(weather_fx.TAG) for o in weather_fx.objects(sc)} == {"pole", "flag"}
    # a Weather & time step keys the rain from 0 to 0.5: rain is needed although it is 0 now
    sc.keyframe_insert('["fr_wx_rain"]', frame=1)
    sc["fr_wx_rain"] = 0.5
    sc.keyframe_insert('["fr_wx_rain"]', frame=50)
    sc.frame_set(1)
    assert sc["fr_wx_rain"] == 0.0
    weather_fx.apply(sc, wcore.State(), "sky")
    roles = {o.get(weather_fx.TAG) for o in weather_fx.objects(sc)}
    assert {"rain", "splash", "tops", "pole", "flag"} <= roles, roles
    assert len(_instances(sc, "rain")) == 0                       # frame 1: no rain yet
    sc.frame_set(50)
    assert len(_instances(sc, "rain")) > 100
    # every driver is a simple expression on the scene's channels (scripts off)
    for ob in weather_fx.objects(sc):
        for d in (ob.animation_data.drivers if ob.animation_data else ()):
            assert d.driver.is_simple_expression and d.driver.is_valid, (ob.name, d.data_path)
    weather_fx.remove(sc)
    assert not [o for o in bpy.data.objects if o.get(weather_fx.TAG) is not None]
    assert not [m for m in bpy.data.meshes if m.get(weather_fx.TAG) is not None]
    assert not [g for g in bpy.data.node_groups if g.name.startswith(weather_fx.PREFIX)]
    assert not [m for m in bpy.data.materials if m.name.startswith(weather_fx.PREFIX)]
    assert bpy.data.collections.get(weather_fx.COLLECTION) is None


def test_apply_again_is_cheap_and_keeps_the_objects():
    import time
    sc = _fresh()
    _weather(sc, rain=0.6, snow=0.4)
    names = sorted(o.name for o in weather_fx.objects(sc))
    t = time.perf_counter()
    weather_fx.apply(sc, wcore.State(rain=0.6, snow=0.4), "sky")
    assert time.perf_counter() - t < 0.02
    assert sorted(o.name for o in weather_fx.objects(sc)) == names


def test_rain_in_nodes_is_the_core_formula_and_the_same_every_time():
    sc = _fresh()
    _weather(sc, rain=0.7, wind=6.0, drop_size=3.0)
    ob = weather_fx.find("rain")
    _full(ob)
    sc.frame_set(17)
    m1 = _instances(sc, "rain")
    sc.frame_set(30)
    sc.frame_set(17)
    m2 = _instances(sc, "rain")
    assert len(m1) > 1000 and np.array_equal(m1, m2)              # the same frame twice: the same rain
    # each streak sits where core.positions puts a drop (some are dropped under the quay or the crane)
    ch = {k: sc[wcore.prop(k)] for k in ("wind", "wind_x", "wind_y", "drop")}
    v = core.rain_velocity(ch["drop"], ch["wind"], ch["wind_x"], ch["wind_y"])
    p, r = _core_points(sc, ob, core.RAIN_BOX, v, 17)
    p = p[r < 0.7]
    got = m1[:, :3, 3]
    assert _far(p, got[::7]) < 2e-3
    assert 0.3 * len(p) < len(got) <= len(p)
    # the streak points along the drop's velocity
    z = m1[0, :3, 2] / np.linalg.norm(m1[0, :3, 2])
    vv = np.array(v) / np.linalg.norm(v)
    assert abs(abs(float(z @ vv)) - 1.0) < 1e-3


def test_no_rain_under_a_roof():
    sc = _fresh()
    # a roof 3 m above the quay over the crane
    me = bpy.data.meshes.new("roof")
    me.from_pydata([(-3, -3, 3), (5, -3, 3), (5, 4, 3), (-3, 4, 3)], [], [(0, 1, 2, 3)])
    roof = bpy.data.objects.new("roof", me)
    roof["fr_kind"] = "part"
    sc.collection.objects.link(roof)
    _weather(sc, rain=1.0, wind=0.0)
    _full(weather_fx.find("rain"))
    for f in (5, 25):
        sc.frame_set(f)
        p = _instances(sc, "rain")[:, :3, 3]
        under = (p[:, 0] > -2.5) & (p[:, 0] < 4.5) & (p[:, 1] > -2.5) & (p[:, 1] < 3.5) & (p[:, 2] < 2.9)
        above = (p[:, 0] > -2.5) & (p[:, 0] < 4.5) & (p[:, 1] > -2.5) & (p[:, 1] < 3.5) & (p[:, 2] > 3.1)
        assert under.sum() == 0 and above.sum() > 10, (under.sum(), above.sum())


def test_splashes_live_briefly_on_the_ground_and_the_sea():
    sc = _fresh()
    _weather(sc, rain=1.0)
    solid = weather_fx.find("splash")
    _full(solid)
    me = solid.data
    n = len(me.vertices)
    ph = np.empty(n, np.float32)
    me.attributes["fr_ph"].data.foreach_get("value", ph)
    sc.frame_set(12)
    got = len(_instances(sc, "splash"))
    want = int((core.splash_age(12 / sc.render.fps, ph) < core.SPLASH_LIFE / core.SPLASH_PERIOD).sum())
    assert want > 50 and abs(got - want) <= max(2, want // 100), (got, want)
    # on Open sea: on the water round the model, at sea level
    sc.fresing.background = "SEA"
    world.apply(sc, sc.fresing)
    _weather(sc, rain=1.0)
    sea = weather_fx.find("splash_sea")
    assert sea is not None
    _full(sea)
    z = _instances(sc, "splash_sea")[:, 2, 3]
    assert len(z) > 50
    assert np.allclose(z, weather_fx._world(weather_fx._sea()).translation.z, atol=1e-3)


def _core_points(sc, ob, box, velocity, frame, sway=False):
    me = ob.data
    n = len(me.vertices)
    u = np.empty(3 * n, np.float32)
    me.attributes["fr_u"].data.foreach_get("vector", u)
    r = np.empty(n, np.float32)
    me.attributes["fr_r"].data.foreach_get("value", r)
    ph = np.empty(n, np.float32)
    me.attributes["fr_ph"].data.foreach_get("value", ph)
    from mathutils import Vector
    cam = sc.camera.matrix_world
    o = core.box_origin(cam.translation, cam.to_3x3() @ Vector((0, 0, -1)), box)
    t = frame / sc.render.fps
    sw = core.wobble(t, ph.astype(float)) if sway else None
    return core.positions(u.reshape(-1, 3).astype(float), box, o, velocity, t, sw), r


def _far(points, got):
    from mathutils.kdtree import KDTree
    kd = KDTree(len(points))
    for i, x in enumerate(points):
        kd.insert(x, i)
    kd.balance()
    return max(kd.find(x)[2] for x in got)


def test_snow_drifts_with_the_wind():
    sc = _fresh()
    _weather(sc, snow=1.0, wind=5.0, wind_from=270.0)            # from the west: blows towards the east
    assert sc["fr_wx_wind_x"] == pytest.approx(1.0, abs=1e-6)   # (north = +y: east = +x)
    ob = weather_fx.find("snow")
    _full(ob)
    v = core.snow_velocity(sc["fr_wx_wind"], sc["fr_wx_wind_x"], sc["fr_wx_wind_y"])
    for f in (10, 40):
        sc.frame_set(f)
        got = _instances(sc, "snow")[:, :3, 3]
        p, r = _core_points(sc, ob, core.SNOW_BOX, v, f, sway=True)
        p = p[r < 1.0]
        assert len(got) > 1000 and _far(p, got[::5]) < 2e-3


def test_flag_in_nodes_is_the_core_formula():
    sc = _fresh(flag=True)
    _weather(sc, wind=6.0, wind_from=180.0)                       # from the south: flies north
    fob = weather_fx.find("flag")
    pole = weather_fx.find("pole")
    assert pole is not None and fob is not None
    info = __import__("json").loads(fob["fr_flag"])
    sc.frame_set(33)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = fob.evaluated_get(dg)
    me = ev.to_mesh()
    got = np.array([v.co[:] for v in me.vertices])
    ev.to_mesh_clear()
    u, v, _f = core.flag_grid()
    p = core.flag_points(u, v, 33 / sc.render.fps, sc["fr_wx_wind"], info["length"], info["height"])
    h = core.flag_heading(sc["fr_wx_wind_x"], sc["fr_wx_wind_y"])
    c, s = math.cos(h), math.sin(h)
    want = np.stack([c * p[:, 0] - s * p[:, 1], s * p[:, 0] + c * p[:, 1], p[:, 2]], 1)
    assert np.abs(got - want).max() < 1e-4
    # the wind's direction in the scene: north is +y by default (north = 90)
    fly = got[u == 1.0].mean(axis=0)
    assert fly[1] > 0.5 * info["length"]
