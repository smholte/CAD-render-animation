"""Vessel at work (task 0154): what the vessel does and what the water shows of it.

The maths (``core/vessel_work.py``) without Blender: the Kelvin wedge's angle, the waves' length and their fade, the
commands per mode, blending, the propellers' turn, the jets. Inside Blender (as a Python module) on the test model
``test_thrusters.step``: the thrusters found with their kinds, channels and steer joints follow the setting, Build keys
the propellers and the steer joints, effects off when still, saved scenes keep the setting, a render shows the water.
"""

import math
import os

import numpy as np
import pytest

from fresing_render.core import vessel_work as W

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_thrusters.step")
TH = [W.Thruster("AZIMUTH", -16.0, 3.0), W.Thruster("AZIMUTH", -16.0, -3.0), W.Thruster("TUNNEL", 14.0, 0.0),
      W.Thruster("SHAFT", -17.0, 0.0)]
KINDS = [t.kind for t in TH]


# ---------------------------------------------------------------------------
# the water (no Blender)
# ---------------------------------------------------------------------------

def test_kelvin_wedge_is_19_47_degrees():
    """No waves outside tan α = 1/√8 (19.47°); waves inside, up to the cusp."""
    assert math.degrees(W.KELVIN) == pytest.approx(math.degrees(math.atan(1 / math.sqrt(8))), abs=0.01)
    x = np.linspace(5.0, 400.0, 4000)
    for deg in (19.6, 22.0, 30.0, 60.0):
        assert not np.any(W.kelvin(x, x * math.tan(math.radians(deg)), 10.0)), deg
    for deg in (2.0, 10.0, 17.0, 19.0):
        assert np.abs(W.kelvin(x, x * math.tan(math.radians(deg)), 10.0)).max() > 0.02, deg
    assert not np.any(W.kelvin(-x, 0 * x, 10.0))                     # nothing ahead of the bow


@pytest.mark.parametrize("knots", [4.0, 8.0, 12.0])
def test_transverse_waves_along_the_track(knots):
    """On the track only the transverse waves: their length is 2 pi V^2 / g."""
    lam = W.wavelength(knots)
    assert lam == pytest.approx(2 * math.pi * (knots * W.KNOT) ** 2 / 9.81, rel=1e-9)
    x = np.linspace(3 * lam, 30 * lam, 200_000)
    h = W.kelvin(x, 0 * x, knots)
    zero = x[np.nonzero(np.diff(np.sign(h)))[0]]
    assert np.median(np.diff(zero)) * 2 == pytest.approx(lam, rel=0.01)


def test_kelvin_roots_solve_the_stationary_phase():
    """Both answers t = tan θ solve tan α = t / (1 + 2 t²); they meet at the cusp."""
    for ta in (0.01, 0.1, 0.2, 0.3, 0.35):
        tt, td = W.kelvin_roots(ta)
        for t in (tt, td):
            assert t / (1 + 2 * t * t) == pytest.approx(ta, rel=1e-9)
        assert tt < td
    tt, td = W.kelvin_roots(1 / math.sqrt(8))
    assert tt == pytest.approx(td, rel=1e-6)


def test_waves_fade_with_distance_and_grow_with_speed():
    x = np.array([10.0, 50.0, 150.0, 400.0])
    env = W.kelvin_envelope(x, 10.0)
    assert np.all(np.diff(env) < 0)
    assert env[-1] < 0.25 * env[0]
    pts = np.linspace(1.0, 600.0, 3000)
    for deg in (0.0, 8.0, 15.0):
        h = W.kelvin(pts, pts * math.tan(math.radians(deg)), 10.0)
        assert np.all(np.abs(h) <= W.kelvin_envelope(pts, 10.0) + 1e-12)
    assert W.amplitude(0.0) == 0.0 and W.amplitude(4.0) < W.amplitude(8.0) < W.amplitude(12.0)
    assert not np.any(W.kelvin(pts, 0 * pts, 0.0))


def test_jet_is_strongest_where_it_leaves_the_hull():
    s = np.array([0.0, 5.0, 20.0, 60.0])
    j = W.jet(s, 0 * s, 0.8)
    assert np.all(np.diff(j) < 0) and j[0] == pytest.approx(0.8) and j[-1] < 0.05
    assert W.jet(10.0, 30.0, 1.0) == 0.0                                   # far beside it
    assert W.jet(-10.0, 0.0, 1.0) == 0.0                                   # not upstream
    assert W.jet(5.0, 0.0, 0.0) == 0.0                                     # off: nothing
    assert W.jet(10.0, 0.0, 1.0) > W.jet(10.0, 0.0, 0.3)


def test_jet_comes_up_beside_or_behind_the_hull():
    hl, hb = 18.0, 6.0
    t = W.Thruster("TUNNEL", 14.0, 0.0)
    assert W.exit_distance(14.0, 0.0, W.PORT, hl, hb) == pytest.approx(6.0)
    assert W.exit_distance(-16.0, 3.0, W.AFT, hl, hb) == pytest.approx(2.0)
    assert W.exit_distance(-16.0, 3.0, W.STBD, hl, hb) == pytest.approx(9.0)
    # the tunnel's jet to port is white beside the hull at port, nothing at starboard
    assert W.jet_at(14.0, 8.0, t, 1.0, W.PORT, hl, hb) > 0.8
    assert W.jet_at(14.0, -8.0, t, 1.0, W.PORT, hl, hb) == 0.0


def test_bow_wave_by_speed_and_place():
    s0, r0 = W.bow_wave(np.array([0.2, 1.0]), 0.0)
    assert np.all(s0 == 0.0) and np.all(r0 == 1.0)
    s, r = W.bow_wave(np.array([0.2, 1.0]), 10.0)
    assert s[1] > s[0] > 0.5 and r[1] > r[0] == 1.0
    assert W.bow_wave(1.0, 4.0)[0] < W.bow_wave(1.0, 10.0)[0]


def test_wake_trail_is_the_seas_wake():
    xb, y = np.array([5.0, 50.0]), np.zeros(2)
    assert np.allclose(W.trail(xb, y, 6.0, 8.0), W.sea_core.wake(xb, y, 6.0, 8.0))


# ---------------------------------------------------------------------------
# commands (no Blender)
# ---------------------------------------------------------------------------

def test_still_and_zero_are_still():
    for st in (W.Setting("STILL"), W.Setting("AHEAD", 0.0), W.Setting("DP", thrust=0.0)):
        c = W.command(st, TH)
        assert W.effective_mode(st) == "STILL" and c.ahead == 0.0 and not any(c.loads)
    assert W.words(W.Setting("AHEAD", 0.0)) == "Still"


def test_ahead_pushes_aft_with_the_propellers_only():
    c = W.command(W.Setting("AHEAD", 6.0), TH)
    assert c.ahead == 6.0
    assert c.loads[0] == c.loads[1] == c.loads[3] == pytest.approx(W.ahead_load(6.0)) and c.loads[2] == 0.0
    assert c.jets[0] == pytest.approx(W.AFT) and W.steer(c.jets[0]) == pytest.approx(0.0)
    assert W.ahead_load(1.0) < W.ahead_load(6.0) < W.ahead_load(12.0) == 1.0 == W.ahead_load(20.0)


@pytest.mark.parametrize("side,jet", [("STBD", W.PORT), ("PORT", W.STBD)])
def test_sideways_pushes_water_the_other_way(side, jet):
    """Pushed to starboard, the water goes to port: tunnels and azimuths; a shaft propeller cannot help."""
    c = W.command(W.Setting("DP", side=side, thrust=0.7), TH)
    assert c.ahead == 0.0 and c.loads[3] == 0.0
    for i in range(3):
        assert c.loads[i] == pytest.approx(0.7) and c.jets[i] == pytest.approx(jet)
    # the azimuths' thrust (opposite the jet) points where the vessel goes
    thrust = W.steer(c.jets[0])                          # steer 0 = thrust to the bow; +90° = thrust to port
    assert math.sin(thrust) == pytest.approx(-1.0 if side == "STBD" else 1.0)


@pytest.mark.parametrize("side", ["STBD", "PORT"])
def test_turning_bow_and_stern_push_opposite(side):
    """Turning the bow to starboard: forward thrusters push the bow to starboard, aft ones the stern to port – the
    turning moment's sign says clockwise (seen from above)."""
    c = W.command(W.Setting("TURN", side=side, thrust=0.5), TH)
    moment = sum(-c.loads[i] * math.sin(c.jets[i]) * TH[i].u for i in range(len(TH)))   # force = -jet
    assert (moment < 0) if side == "STBD" else (moment > 0)
    assert math.sin(c.jets[2]) * math.sin(c.jets[0]) < 0                               # bow and stern opposite


def test_mix_steers_the_short_way_and_reverses_a_tunnel_through_zero():
    a = W.command(W.Setting("AHEAD", 8.0), TH)
    b = W.command(W.Setting("DP", side="STBD", thrust=0.6), TH)
    jets = [W.mix(a, b, f, KINDS).jets[0] for f in np.linspace(0, 1, 21)]
    steps = np.abs(np.diff(np.unwrap(jets)))
    assert steps.max() < math.radians(10) and np.unwrap(jets)[-1] - np.unwrap(jets)[0] == pytest.approx(-math.pi / 2)
    p = W.command(W.Setting("DP", side="STBD", thrust=0.6), TH)
    q = W.command(W.Setting("DP", side="PORT", thrust=0.6), TH)
    mid = W.mix(p, q, 0.5, KINDS)
    assert mid.loads[2] == pytest.approx(0.0, abs=1e-12)
    assert W.mix(p, q, 0.75, KINDS).jets[2] == pytest.approx(W.STBD)
    half = W.mix(a, W.command(W.Setting("STILL"), TH), 0.5, KINDS)
    assert half.ahead == pytest.approx(4.0) and half.loads[0] == pytest.approx(a.loads[0] / 2)


def test_propeller_rate_and_its_turn():
    assert W.rate("AZIMUTH", 1.0, W.AFT, 60.0) == pytest.approx(2 * math.pi)
    assert W.rate("AZIMUTH", 1.0, W.AFT, 60.0, reverse=True) == pytest.approx(-2 * math.pi)
    assert W.rate("TUNNEL", 0.5, W.PORT, 60.0) == pytest.approx(math.pi)
    assert W.rate("TUNNEL", 0.5, W.STBD, 60.0) == pytest.approx(-math.pi)
    a = W.turns([2.0] * 26, 0.04, 1.0)
    assert a[-1] == pytest.approx(1.0 + 2.0 * 25 * 0.04) and W.thin(a) == [0, 25]
    ramp = W.turns(np.linspace(0, 2, 11), 0.1)
    assert ramp[-1] == pytest.approx(1.0)                 # the area under a ramp from 0 to 2 rad/s over 1 s
    assert len(W.thin(ramp)) == 11


def test_channels_have_every_slot():
    ch = W.channels(W.command(W.Setting("AHEAD", 5.0), TH))
    assert set(ch) == set(W.CHANNEL_NAMES) and len(ch) == 1 + 2 * W.MAX_THRUSTERS
    assert ch["ahead"] == 5.0 and ch["t5"] == 0.0


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, states, surroundings  # noqa: E402
from fresing_render.blender import vessel_work as VW  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    VW.set_up_test_model(sc)
    bpy.context.view_layer.update()
    return sc


def ch(sc, name):
    return float(sc.get(W.prop(name), -99.0))


def sea_material(sc):
    sea = next(o for o in bpy.data.objects if o.get("fr_env") == "sea")
    return sea.active_material


@pytest.fixture(scope="module")
def scene():
    return fresh()


def test_thrusters_found_with_their_kinds(scene):
    rows = list(scene.fresing.vessel_work.thrusters)
    assert [(r.kind, r.steer) for r in rows] == [("AZIMUTH", "Azimuth PS: Steer"), ("AZIMUTH", "Azimuth SB: Steer"),
                                                 ("TUNNEL", "")]
    lay = VW.stored_layout(scene)
    assert lay["sign"] == 1.0 and lay["hl"] == pytest.approx(18.0, abs=0.05)
    assert [t[0] for t in lay["thrusters"]] == ["AZIMUTH", "AZIMUTH", "TUNNEL"]
    assert lay["thrusters"][0][1:] == pytest.approx([-16.0, 3.0], abs=0.05)
    assert lay["thrusters"][2][1:] == pytest.approx([14.0, 0.0], abs=0.05)
    assert all(joints.is_motor(joints.find(scene, r.joint)) for r in rows)


def test_channels_and_steer_follow_the_setting(scene):
    v = scene.fresing.vessel_work
    v.mode = "AHEAD"
    assert ch(scene, "ahead") == pytest.approx(8.0) and ch(scene, "t0") > 0.5 and ch(scene, "t2") == 0.0
    v.side, v.thrust, v.mode = "STBD", 0.6, "DP"
    assert ch(scene, "ahead") == 0.0 and ch(scene, "t2") == pytest.approx(0.6)
    assert ch(scene, "a0") == pytest.approx(math.pi / 2) and ch(scene, "a2") == pytest.approx(math.pi / 2)
    steer = joints.find(scene, "Azimuth PS: Steer")
    assert joints.get_value(steer) == pytest.approx(-math.pi / 2)       # thrust to starboard
    v.mode = "STILL"
    assert all(ch(scene, f"t{i}") == 0.0 for i in range(W.MAX_THRUSTERS)) and ch(scene, "ahead") == 0.0
    v.mode = "AHEAD"
    assert joints.get_value(steer) == pytest.approx(0.0)


def test_effects_in_the_water_material_and_off_when_still():
    sc = fresh()
    mat = sea_material(sc)
    assert mat.get("fr_wake") and mat.get("fr_vw")
    names = {n.attribute_name for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeAttribute"}
    assert {W.prop("ahead"), W.prop("t0"), W.prop("a2")} <= names and W.prop("t3") not in names
    hull = next(o for o in bpy.data.objects if o.get("fr_env") == "hull_foam")
    assert hull.data.attributes.get("fr_u") is not None and hull["fr_foam_w"] > hull["fr_foam_w0"]
    # still, and nothing anywhere makes it sail or push: the sea is built without any of it (as before 0154)
    sc.fresing.vessel_work.mode = "STILL"
    mat = sea_material(sc)
    assert not mat.get("fr_wake") and not mat.get("fr_vw")
    assert "work" not in surroundings._settings_key(sc.fresing, "SEA")


def _add_step(sc, a, start, dur, mode, **kw):
    b = a.blocks.add()
    b.kind, b.start, b.duration, b.easing = "VESSEL", start, dur, "LINEAR"
    b.vw_mode = mode
    for k, v in kw.items():
        setattr(b, "vw_" + k, v)
    return b


def test_build_turns_the_propellers_and_steers():
    sc = fresh()
    s = sc.fresing
    a = s.animations.add()
    a.name = "Work"
    s.animations_index = len(s.animations) - 1
    j0 = _add_step(sc, a, 0.0, 0.1, "AHEAD", speed=8.0)      # (a step only to set the start)
    j0.enabled = False
    blk = a.blocks.add()
    blk.kind, blk.start, blk.duration = "JOINT", 0.0, 8.0     # something to last 8 s
    blk.joint = "Azimuth SB: Steer"
    blk.enabled = False
    _add_step(sc, a, 2.0, 2.0, "DP", side="STBD", thrust=0.6)
    s.vessel_work.mode = "AHEAD"
    s.weather.vessel_speed = 8.0
    _add_step(sc, a, 6.0, 0.5, "DP", side="STBD", thrust=0.6).duration = 2.0
    r = animation.bake(sc, a)
    assert not [w for w in r["warnings"] if "Vessel" in w], r["warnings"]
    fps = animation.fps_of(a)
    prop = joints.find(sc, "Azimuth PS: Propeller turn")
    steer = joints.find(sc, "Azimuth PS: Steer")
    tunnel = joints.find(sc, "Bow thruster: Propeller turn")

    def at(t):
        sc.frame_set(animation.frame_of(a, t))
        return joints.get_value(prop), joints.get_value(steer), joints.get_value(tunnel), ch(sc, "ahead")
    p0, s0, t0, v0 = at(0.0)
    p1, s1, t1, v1 = at(1.0)
    assert v0 == pytest.approx(8.0) and s0 == pytest.approx(0.0) and t1 == pytest.approx(t0)
    want = W.ahead_load(8.0) * 60.0 * 2 * math.pi / 60.0          # rad/s at full rpm 60
    assert (p1 - p0) == pytest.approx(want * (animation.frame_of(a, 1.0) - animation.frame_of(a, 0.0)) / fps,
                                      rel=1e-3)
    p5, s5, t5, v5 = at(5.0)
    assert v5 == pytest.approx(0.0) and s5 == pytest.approx(-math.pi / 2, abs=1e-3)
    p6, _s6, t6, _v6 = at(5.5)
    dt = (animation.frame_of(a, 5.5) - animation.frame_of(a, 5.0)) / fps
    assert (t6 - t5) == pytest.approx(0.6 * 2 * math.pi * dt, rel=1e-3)       # the tunnel runs at 0.6 x 60 rpm
    assert ch(sc, "t2") == pytest.approx(0.6) and ch(sc, "a0") == pytest.approx(math.pi / 2)
    # Clear keys: the panel's setting again
    animation.clear_keys(sc)
    assert ch(sc, "ahead") == pytest.approx(8.0) and ch(sc, "t2") == 0.0
    assert not VW.keyed(sc)


def test_a_joint_another_step_moves_is_left_alone():
    sc = fresh()
    s = sc.fresing
    a = s.animations.add()
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.speed_rpm = "MOTOR", "Bow thruster: Propeller turn", 0.0, 4.0, 10.0
    _add_step(sc, a, 0.5, 2.0, "DP", side="PORT", thrust=1.0)
    r = animation.bake(sc, a)
    assert any("Bow thruster: Propeller turn" in w and "another step" in w for w in r["warnings"]), r["warnings"]
    tunnel = joints.find(sc, "Bow thruster: Propeller turn")
    sc.frame_set(animation.frame_of(a, 4.0))
    assert 0.5 < joints.get_value(tunnel) <= 10.0 / 60.0 * 2 * math.pi * 4.0 + 1e-6   # the motor's, ramps and all


def test_saved_scene_keeps_the_setting():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "TURN", "PORT", 0.9
    text = states.settings_json(sc.fresing, states.WORLD_KEYS)
    v.mode = "STILL"
    states.apply_settings_json(sc, text)
    assert (v.mode, v.side) == ("TURN", "PORT") and v.thrust == pytest.approx(0.9)
    assert ch(sc, "t0") == pytest.approx(0.9)


def test_step_label_and_words():
    scene = fresh()
    a = scene.fresing.animations.add()
    b = _add_step(scene, a, 0.0, 2.0, "DP", side="PORT", thrust=0.5)
    assert animation.block_label(b) == "Vessel: sideways to port 50%"
    assert "19.5°" in VW.words(scene) and VW.header(scene) == "Ahead 8 kn"
    scene.fresing.vessel_work.mode = "DP"
    assert VW.header(scene) == "Sideways 60%"


def test_render_shows_the_wake_and_the_jets(tmp_path):
    """A small Cycles picture: the water behind and beside the vessel is whiter sailing ahead and pushing sideways
    than lying still."""
    sc = fresh()
    from mathutils import Vector
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = 160, 90
    cam = bpy.data.objects.new("top", bpy.data.cameras.new("top"))
    sc.collection.objects.link(cam)
    cam.location = (0.0, 0.0, 160.0)
    cam.data.clip_end = 1000.0
    sc.camera = cam
    v = sc.fresing.vessel_work
    means = {}
    for name, mode in (("still", "STILL"), ("ahead", "AHEAD"), ("dp", "DP")):
        v.mode = mode
        sc.render.filepath = str(tmp_path / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath)
        px = np.array(img.pixels[:]).reshape(90, 160, 4)[:, :, :3]
        means[name] = float(px.mean())
        bpy.data.images.remove(img)
    assert means["ahead"] > means["still"] * 1.15, means
    assert means["dp"] > means["still"] * 1.05, means
    del Vector


def test_build_says_when_the_start_scene_puts_the_setting_back():
    """Task 0160's warning covers what the vessel does: changed after the start scene was saved, Build puts it back
    and says so; 'Save into start scene' keeps it."""
    sc = fresh()
    s = sc.fresing
    shot = states.save_shot(sc, "Start")
    a = s.animations.add()
    a.start_shot = shot.name
    _add_step(sc, a, 0.0, 2.0, "STILL")
    s.vessel_work.mode = "DP"
    ch_ = states.start_scene_changes(sc, shot.name, ["vessel_work"])
    assert [(k, now, then) for k, _n, now, then in ch_] == [("vessel_work.mode", "DP", "AHEAD")]
    assert states.save_into_start_scene(sc, shot.name, ["vessel_work"]) == ["The vessel"]
    assert not states.start_scene_changes(sc, shot.name, ["vessel_work"])
    animation.bake(sc, a)
    assert s.vessel_work.mode == "DP"
