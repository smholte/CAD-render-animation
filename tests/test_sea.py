"""The sea of task 0109 (``core/sea.py``, ``blender/surroundings.py``).

Without Blender: the spectrum's heights against the published formulas (Pierson–Moskowitz, JONSWAP), white-cap
coverage per wind strength against Monahan & O'Muircheartaigh (1980), white caps only on crests, patchy and short
lived (no stripes), streaks along the wind in a gale, the same sea every time, no visible repeat. Inside Blender (as
a Python module): the Detailed sea's geometry is ``core.sea.height``, the material carries the same waves, From the
wind follows the weather, hull foam sits on the water and rides with vessel motion, the wake and spray appear only
when asked for, every driver is a simple expression (scripts off).
"""

import math
import os

import numpy as np
import pytest

from fresing_render.core import sea
from fresing_render.core import weather as W

HERE = os.path.dirname(__file__)


def grid(size=600.0, step=1.5, t=10.0):
    v = np.arange(0.0, size, step)
    x, y = np.meshgrid(v, v)
    return x, y, np.full_like(x, t)


# ---------------------------------------------------------------------------
# waves
# ---------------------------------------------------------------------------

def test_two_quick_choices_are_wind_strengths():
    assert sea.STATES == {"CALM": 3.0, "ROUGH": 6.0}
    for state, bft in sea.STATES.items():
        comps = sea.of_state(state)
        assert comps == sea.components(bft, sea.DEFAULT_TOWARD)
        assert len(comps) >= 24
        assert all(len(c) == 5 and all(isinstance(v, float) for v in c) for c in comps)
        assert all(abs(math.hypot(c[1], c[2]) - 1.0) < 1e-9 for c in comps)


def test_same_sea_every_time():
    a, b = sea.components(6.0, 30.0), sea.components(6.0, 30.0)
    assert a == b
    assert sea.components(6.0, 30.0, seed=sea.SEED + 1) != a
    x, y, t = grid(100.0, 5.0)
    assert np.array_equal(sea.height(x, y, t, a), sea.height(x, y, t, b))
    assert sea.foam_threshold(6.0) == sea.foam_threshold(6.0)


@pytest.mark.parametrize("bft", [3.0, 6.0, 9.0])
def test_fully_developed_sea_has_the_pierson_moskowitz_height(bft):
    """Hs of the continuous spectrum and of the 28 components against Hs = 0.21 U19.5^2 / g."""
    u = sea.bft_to_ms(bft)
    pm = sea.hs_pm(u)
    assert abs(pm - 0.2093 * (sea.U195 * u) ** 2 / sea.G) < 1e-3 * pm
    assert abs(sea.hs_spectrum(u, None) - pm) < 0.01 * pm
    assert abs(sea.hs(sea.components(bft, fetch=None)) - pm) < 0.06 * pm


def test_heights_of_calm_rough_and_a_gale():
    """Calm (Bft 3) is fully developed (PM); Rough (Bft 6) fetch-limited (JONSWAP, 100 km) like today's Rough sea
    (Hs ~2.3 m, ~70 m waves); the components keep the spectrum's height."""
    for bft, lo, hi in ((3.0, 0.35, 0.55), (6.0, 2.0, 2.8), (9.0, 3.6, 4.8)):
        comps = sea.components(bft)
        hs = sea.hs(comps)
        assert lo <= hs <= hi, (bft, hs)
        assert abs(hs - sea.hs_spectrum(sea.bft_to_ms(bft))) < 0.06 * hs
    assert 55.0 <= sea.peak_wavelength(sea.components(6.0)) <= 80.0
    hs = [sea.hs(sea.components(b)) for b in range(1, 13)]
    assert all(b > a for a, b in zip(hs, hs[1:]))


def test_jonswap_peak_and_fully_developed_limit():
    u = sea.bft_to_ms(6.0)
    wp, alpha, gamma = sea.peak(u)
    x = sea.G * sea.FETCH / u ** 2
    assert abs(wp - 22.0 * sea.G / u * x ** -0.33) < 1e-9 and abs(alpha - 0.076 * x ** -0.22) < 1e-9
    assert 1.0 < gamma <= 3.3
    assert sea.peak(sea.bft_to_ms(3.0)) == (0.877 * sea.G / (sea.U195 * sea.bft_to_ms(3.0)), 0.0081, 1.0)


def test_waves_spread_round_the_wind():
    for toward in (0.0, 75.0, -140.0):
        comps = sea.components(6.0, toward)
        mx, my = sea.mean_direction(comps)
        d = (math.degrees(math.atan2(my, mx)) - toward + 180.0) % 360.0 - 180.0
        assert abs(d) < 15.0, (toward, d)
        dirs = {round(math.degrees(math.atan2(c[2], c[1]))) for c in comps}
        assert len(dirs) >= 20                                         # short-crested: many directions


def test_slope_is_the_heights_gradient():
    comps = sea.components(6.0)
    x, y, t = np.array([3.0, -40.0, 210.0]), np.array([1.0, 77.0, -15.0]), np.array([0.0, 12.5, 61.0])
    sx, sy = sea.slope(x, y, t, comps)
    e = 1e-4
    fx = (sea.height(x + e, y, t, comps) - sea.height(x - e, y, t, comps)) / (2 * e)
    fy = (sea.height(x, y + e, t, comps) - sea.height(x, y - e, t, comps)) / (2 * e)
    assert np.allclose(sx, fx, atol=1e-6) and np.allclose(sy, fy, atol=1e-6)


@pytest.mark.parametrize("bft", [3.0, 6.0, 9.0])
def test_no_visible_repeat(bft):
    """The sea 124 m (the vessel) and 1 km away is unrelated to the sea here: the height's correlation, averaged
    over all directions, stays low, and in no direction does the pattern come back (as it did with 5-6 waves)."""
    comps = sea.components(bft)
    a2 = np.array([c[0] ** 2 for c in comps])
    assert a2.sum() ** 2 / (a2 ** 2).sum() >= 12.0                      # no two or three waves carry the sea
    slope2 = np.array([(c[0] * c[3]) ** 2 for c in comps])
    assert slope2.max() < 0.15 * slope2.sum()                          # nor one short wave the sparkle
    for lag in (124.0, 1000.0):
        r = [sea.correlation(comps, lag * math.cos(a), lag * math.sin(a)) for a in np.radians(np.arange(0, 180, 3))]
        assert math.sqrt(np.mean(np.square(r))) < 0.3, (lag, r)
        assert max(abs(v) for v in r) < 0.75
    # measured on the surface itself: two 300 m patches 1 km apart
    x, y, t = grid(300.0, 3.0)
    h0 = sea.height(x, y, t, comps).ravel()
    for dx, dy in ((1000.0, 0.0), (0.0, 1000.0), (707.0, 707.0), (124.0, 0.0)):
        h1 = sea.height(x + dx, y + dy, t, comps).ravel()
        assert abs(np.corrcoef(h0, h1)[0, 1]) < 0.5, (dx, dy)


# ---------------------------------------------------------------------------
# white caps
# ---------------------------------------------------------------------------

def test_monahan_relation():
    """W = 3.84e-6 U10^3.41 (Monahan & O'Muircheartaigh 1980)."""
    for u in (4.0, 10.0, 20.0):
        assert abs(sea.whitecap_coverage(u) - 3.84e-6 * u ** 3.41) < 1e-12
    assert sea.whitecap_coverage(0.0) == 0.0 and sea.whitecap_coverage(60.0) == 1.0
    assert 0.0004 < sea.whitecap_coverage(sea.bft_to_ms(3)) < 0.001          # hardly any
    assert 0.015 < sea.whitecap_coverage(sea.bft_to_ms(6)) < 0.03            # a few per cent
    assert 0.12 < sea.whitecap_coverage(sea.bft_to_ms(9)) < 0.2              # much more


@pytest.mark.parametrize("bft", [3, 4, 5, 6, 7, 8, 9, 10])
def test_coverage_follows_monahan(bft):
    """The share of the sea with foam >= 0.5, measured on points the calibration never saw, is Monahan's W:
    within 20 % from Beaufort 5 (the relation's own scatter is a factor of 2-3), within 50 % below (W < 0.3 %,
    a few hundred white points in the sample)."""
    want = sea.whitecap_coverage(sea.bft_to_ms(bft))
    got = sea.coverage(bft, n=80_000, seed=1234)
    tol = 0.2 if bft >= 5 else 0.5
    assert abs(got - want) <= tol * want, (bft, got, want)


def test_foam_threshold_falls_with_the_wind():
    th = [sea.foam_threshold(b) for b in range(0, 13)]
    assert all(b < a for a, b in zip(th, th[1:]))
    assert th[0] == sea.THRESHOLD_MAX
    assert W.derive(W.State(wind=6.0))["foam"] == pytest.approx(sea.foam_threshold(6.0))


def test_foam_is_the_threshold_of_the_field():
    comps = sea.components(6.0)
    x, y, t = grid(200.0, 2.0)
    f = sea.foam(x, y, t, 6.0, comps)
    field = sea.foam_field(comps, 6.0)
    F = sea.foam_value(x, y, t, field)
    th = sea.foam_threshold(6.0)
    assert np.allclose(f, sea.smoothstep(th, th + sea.EDGE, F))
    assert f.min() >= 0.0 and f.max() <= 1.0
    assert abs(np.std(sea.foam_value(*sea._sample_points(40_000, 5), field)) - 1.0) < 0.1   # F ~ unit variance


@pytest.mark.parametrize("bft", [4.0, 6.0, 9.0])
def test_white_caps_only_on_crests(bft):
    comps = sea.components(bft)
    x, y, t = sea._sample_points(200_000, 9, 2000.0, 300.0)
    white = sea.foam(x, y, t, bft, comps) >= 0.5
    h = sea.height(x, y, t, comps) / (sea.hs(comps) / 4.0)
    assert white.sum() > 50
    assert np.mean(h[white] > 0.0) > 0.85, np.mean(h[white] > 0.0)          # on the upper half of the waves
    assert np.mean(h[white]) > 0.9                                         # well above the mean level


def _mask_corr(m, shift):
    dy, dx = shift
    a = m[max(dy, 0):m.shape[0] + min(dy, 0), max(dx, 0):m.shape[1] + min(dx, 0)].ravel().astype(float)
    b = m[max(-dy, 0):m.shape[0] + min(-dy, 0), max(-dx, 0):m.shape[1] + min(-dx, 0)].ravel().astype(float)
    return np.corrcoef(a, b)[0, 1]


def test_white_caps_are_patches_not_stripes():
    """At Rough the white seen from above lies in patches: no direction in which white continues 40 m on (the
    old sea's bands along every crest did); a top view of the whole vessel shows dozens of separate caps."""
    comps = sea.components(6.0)
    x, y, t = grid(700.0, 1.0, 37.0)
    m = sea.foam(x, y, t, 6.0, comps) >= 0.5
    assert 0.01 < m.mean() < 0.035
    for ang in np.radians(np.arange(0, 180, 15)):
        c = _mask_corr(m, (int(round(40 * math.sin(ang))), int(round(40 * math.cos(ang)))))
        assert c < 0.2, (math.degrees(ang), c)


def test_streaks_along_the_wind_in_a_gale():
    """White caps lie along the crests, across the wind; from Beaufort 6.5 streaks along the wind join them: at
    Beaufort 9 white 15 m downwind is much likelier, compared with 15 m across, than at Beaufort 6 (no streaks)."""
    assert sea.streak_weight(6.0) == 0.0 and sea.streak_weight(9.0) == pytest.approx(sea.STREAK_MAX)
    toward = 30.0
    a = math.radians(toward)
    x, y, t = grid(600.0, 1.0, 20.0)

    def ratio(bft):
        m = sea.foam(x, y, t, bft, sea.components(bft, toward)) >= 0.5
        along = _mask_corr(m, (int(round(15 * math.sin(a))), int(round(15 * math.cos(a)))))
        across = _mask_corr(m, (int(round(15 * math.cos(a))), -int(round(15 * math.sin(a)))))
        return along / across
    calm, gale = ratio(6.0), ratio(9.0)
    assert gale > calm + 0.3, (calm, gale)


def test_white_caps_live_a_few_seconds_and_drift():
    """A white cap rides on its crest for a moment and is gone a few seconds later (others break elsewhere): followed
    along the waves' direction, the white overlaps itself half a second later, hardly three seconds later."""
    comps = sea.components(6.0)
    x, y, t = grid(500.0, 1.0, 50.0)
    m0 = sea.foam(x, y, t, 6.0, comps) >= 0.5
    mx, my = sea.mean_direction(comps)

    def overlap(dt):
        m1 = sea.foam(x, y, t + dt, 6.0, comps) >= 0.5
        best = 0.0
        for d in np.arange(0.0, 16.0 * dt + 1.0, 1.0):                # the crest moves at up to ~10 m/s
            dx, dy = int(round(d * mx)), int(round(d * my))
            a = m0[max(-dy, 0):m0.shape[0] - max(dy, 0), max(-dx, 0):m0.shape[1] - max(dx, 0)]
            b = m1[max(dy, 0):, max(dx, 0):][:a.shape[0], :a.shape[1]]
            best = max(best, (a & b).sum() / max(a.sum(), 1))
        return best
    assert overlap(0.5) > 0.35
    assert overlap(3.0) < 0.25
    assert overlap(3.0) < 0.6 * overlap(0.5)


def test_wake_and_hull_foam_rules():
    xb = np.array([-5.0, 0.5, 30.0, 300.0])
    w = sea.wake(xb, np.zeros(4), 12.0, 8.0)
    assert w[0] == 0.0 and w[1] > 0.9 and 0.0 < w[3] < w[2]
    assert not np.any(sea.wake(xb, np.zeros(4), 12.0, 0.0))
    assert sea.wake(np.array([50.0]), np.array([30.0]), 12.0, 8.0)[0] < 0.4      # beside the wake: only the arms
    assert sea.hull_foam_width(3.0) < sea.hull_foam_width(6.0) < sea.hull_foam_width(6.0, 8.0)
    assert 0.0 < sea.hull_foam_strength(3.0) < sea.hull_foam_strength(7.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import surroundings, vessel_motion  # noqa: E402

@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _hull(name, L=60.0, B=14.0, depth=6.0):
    """An invented box hull, its bow pointed at -x."""
    me = bpy.data.meshes.new(name)
    x0, x1, y, z = -L / 2, L / 2, B / 2, depth
    v = [(x0, 0, 0), (x0 + 8, -y, 0), (x1, -y, 0), (x1, y, 0), (x0 + 8, y, 0),
         (x0, 0, z), (x0 + 8, -y, z), (x1, -y, z), (x1, y, z), (x0 + 8, y, z)]
    f = [(4, 3, 2, 1, 0), (5, 6, 7, 8, 9)] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
    me.from_pydata(v, [], f)
    me.update()
    return me


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    root = bpy.data.objects.new("Invented hull", None)
    sc.collection.objects.link(root)
    root["fr_root"] = True
    root["fr_kind"] = "assembly"
    ob = bpy.data.objects.new("Hull", _hull("Hull"))
    sc.collection.objects.link(ob)
    ob.parent = root
    ob["fr_kind"] = "part"
    ob["fr_uid"] = "hull"
    bpy.context.view_layer.update()
    s = sc.fresing
    s.background = "SEA"
    s.water_level = 3.0
    return sc


def _env(role):
    return [o for o in bpy.data.objects if o.get(surroundings.TAG) == role]


def _apply(sc):
    from fresing_render.blender import world
    world.apply(sc, sc.fresing)
    bpy.context.view_layer.update()


def _evaluated_points(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    e.to_mesh_clear()
    return co.reshape(-1, 3)


def test_detailed_geometry_is_the_core_height(scene):
    """Near the middle (where no wave is faded out) the Detailed sea's points lie at core.sea.height of the sea's own
    waves plus vessel motion's swell, at the scene's time."""
    s = scene.fresing
    s.env_detail = "DETAILED"
    s.sea_state = "ROUGH"
    s.vessel.enabled = True
    _apply(scene)
    sea_ob = _env("sea")[0]
    rows = surroundings._waves("ROUGH", vessel_motion.swell_rows(s))
    assert len(rows) == len(sea.of_state("ROUGH")) + 8
    for frame in (1, 37):
        scene.frame_set(frame)
        p = _evaluated_points(sea_ob)
        near = np.hypot(p[:, 0], p[:, 1]) < 3.5
        assert near.sum() > 100
        t = frame / (scene.render.fps / scene.render.fps_base)
        want = sea.height(p[near, 0], p[near, 1], t, rows)
        assert np.allclose(p[near, 2], want, atol=2e-3), np.abs(p[near, 2] - want).max()


def test_material_carries_the_waves_and_old_projects_rebuild(scene):
    s = scene.fresing
    s.sea_state = "CALM"
    _apply(scene)
    mat = _env("sea")[0].data.materials[0]
    import json
    assert json.loads(mat["fr_waves"]) == [[round(v, 7) for v in r] for r in sea.of_state("CALM")]
    assert mat["fr_env_version"] == surroundings.MAT_VERSION >= 4
    numbers = surroundings.SEA
    assert numbers["ROUGH"]["bft"] == 6.0 and numbers["CALM"]["foam"] > numbers["ROUGH"]["foam"]
    kinds = {n.attribute_type for n in mat.node_tree.nodes if n.type == "ATTRIBUTE"}
    assert "VIEW_LAYER" not in kinds                                   # weather off: the sea state's own threshold
    root = surroundings.root_object()
    key = root["fr_key"]
    root["fr_key"] = key.replace(f'"v": {surroundings.MAT_VERSION}', '"v": 3')      # a project saved before
    _apply(scene)
    assert surroundings.root_object()["fr_key"] == key                 # built again with the new sea


def test_from_the_wind_follows_the_weather(scene):
    s = scene.fresing
    s.weather.enabled = True
    s.weather.wind = 8.0
    s.weather.wind_ref = "NORTH"
    s.weather.wind_from = 270.0
    s.sea_state = "WIND"
    _apply(scene)
    bft, toward = surroundings.sea_wind(s)
    assert bft == 8.0
    wx, wy = W.wind_vector(W.State(wind=8.0, wind_from=270.0, north=s.weather.north))
    assert abs(toward - math.degrees(math.atan2(wy, wx))) < 1e-6
    assert surroundings._waves("WIND") == sea.components(8.0, toward)
    mat = _env("sea")[0].data.materials[0]
    names = {n.attribute_name for n in mat.node_tree.nodes
             if n.type == "ATTRIBUTE" and n.attribute_type == "VIEW_LAYER"}
    assert W.prop("foam") in names                                     # the weather's foam channel
    key = surroundings.root_object()["fr_key"]
    s.weather.wind = 5.0
    _apply(scene)
    assert surroundings.root_object()["fr_key"] != key                 # a new wind: a new sea
    st = vessel_motion.core_settings(scene)
    assert st is None or st.bft == 5.0


def test_hull_foam_on_the_water_and_with_the_vessel(scene):
    s = scene.fresing
    s.env_detail = "DETAILED"
    s.sea_state = "ROUGH"
    s.vessel.enabled = True
    _apply(scene)
    foam = _env("hull_foam")
    assert len(foam) == 1
    ob = foam[0]
    assert ob.constraints.get(vessel_motion.CON) is not None          # rides with heave, pitch and roll
    sea_ob = _env("sea")[0]
    scene.frame_set(30)
    bpy.context.view_layer.update()
    p = _evaluated_points(ob)
    world = np.array(ob.matrix_world) @ np.column_stack([p, np.ones(len(p))]).T
    local = (np.linalg.inv(np.array(sea_ob.matrix_world)) @ world).T[:, :3]
    rows = surroundings._waves("ROUGH", vessel_motion.swell_rows(s))
    t = 30 / (scene.render.fps / scene.render.fps_base)
    r = np.hypot(local[:, 0], local[:, 1])
    want = np.zeros(len(local))
    for row in rows:                       # the geometry's waves: 1 m and longer, short ones faded out at 5-8 lengths
        lam = 2 * math.pi / row[3]
        if lam >= 1.0:
            want += sea.height(local[:, 0], local[:, 1], t, [row]) * np.clip((8 * lam - r) / (3 * lam), 0.0, 1.0)
    want += surroundings.HULL_FOAM_LIFT
    assert np.allclose(local[:, 2], want, atol=0.02), np.abs(local[:, 2] - want).max()
    # the strip goes round the hull's waterline
    assert local[:, 0].min() < -30.0 and local[:, 0].max() > 30.0 and local[:, 1].max() > 7.0
    s.sea_foam = False
    _apply(scene)
    assert not _env("hull_foam")


def test_wake_and_spray_only_when_asked(scene):
    s = scene.fresing
    s.sea_state = "ROUGH"
    _apply(scene)
    assert not _env("spray")
    assert _env("sea")[0].get("fr_wake_v", 0.0) == 0.0
    s.weather.enabled = True
    s.weather.wind = 9.0
    s.weather.spray = True
    s.weather.vessel_speed = 8.0
    _apply(scene)
    sea_ob = _env("sea")[0]
    assert sea_ob["fr_wake_v"] == 8.0 and sea_ob["fr_wake"][0] == pytest.approx(30.0, abs=0.1)
    assert "wake" in sea_ob.data.materials[0].name
    spray = _env("spray")
    assert len(spray) == 1

    def drops(frame):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        out = [tuple(round(v, 4) for v in i.matrix_world.translation) for i in dg.object_instances
               if i.is_instance and i.parent and i.parent.original == spray[0]]
        return sorted(out)
    a = drops(40)
    assert len(a) > 20
    assert drops(41) != a and drops(40) == a                           # moves, and the same at the same frame
    s.weather.spray = False
    _apply(scene)
    assert not _env("spray")


def test_every_sea_driver_is_a_simple_expression(scene):
    """Scripts off and the render queue: the time in the materials is a simple expression."""
    s = scene.fresing
    s.env_detail = "DETAILED"
    s.weather.enabled = True
    s.weather.vessel_speed = 4.0
    s.sea_state = "ROUGH"
    _apply(scene)
    found = 0
    for mat in bpy.data.materials:
        ad = mat.node_tree.animation_data if mat.node_tree else None
        for fc in (ad.drivers if ad else ()):
            found += 1
            assert fc.driver.is_simple_expression, (mat.name, fc.driver.expression)
    assert found >= 2


def test_wake_follows_the_bow():
    """Task 0082: the wake trails behind the real stern. From the hull: the end where the waterline is wider is the
    stern (a bow narrows); a hull as wide at both ends keeps the old sides (stern at +x); +x / -x as set."""
    from types import SimpleNamespace

    from fresing_render.blender import surroundings as su
    box = np.array([(-40.0, -8.0), (40.0, -8.0), (40.0, 8.0), (-40.0, 8.0)])
    bow_plus = np.array([(0.0, -8.0), (60.0, -8.0), (75.0, -2.0), (78.0, 0.0), (75.0, 2.0), (60.0, 8.0), (0.0, 8.0)])
    s = lambda bow: SimpleNamespace(weather=SimpleNamespace(bow=bow))  # noqa: E731
    assert su.stern_side(s("AUTO"), box) == 1                   # old projects keep their look
    assert su.stern_side(s("AUTO"), bow_plus) == -1             # the demo: transom at x = 0, bow at +x
    assert su.stern_side(s("AUTO"), bow_plus * [-1, 1]) == 1
    assert su.stern_side(s("POS_X"), box) == -1 and su.stern_side(s("NEG_X"), bow_plus) == 1
    assert su.stern_side(s("AUTO"), None) == 1


def test_wake_behind_a_stern_at_low_x(scene):
    """Bow at +x: the sea object says so (fr_wake_flip 1) and the wake's stern is the waterline's lowest x."""
    s = scene.fresing
    s.sea_state = "ROUGH"
    s.weather.enabled = True
    s.weather.vessel_speed = 8.0
    s.weather.bow = "POS_X"
    _apply(scene)
    sea_ob = _env("sea")[0]
    assert sea_ob["fr_wake_flip"] == 1.0 and sea_ob["fr_wake"][0] == pytest.approx(30.0, abs=0.1)  # -(-30)
    s.weather.bow = "NEG_X"
    _apply(scene)
    sea_ob = _env("sea")[0]
    assert sea_ob["fr_wake_flip"] == 0.0 and sea_ob["fr_wake"][0] == pytest.approx(30.0, abs=0.1)
