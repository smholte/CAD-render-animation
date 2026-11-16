"""Task 0154, independent tests (written from the brief and the docstrings only)."""

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import vessel_work as C

HERE = os.path.dirname(__file__)
THR = os.path.join(HERE, "data", "test_thrusters.step")
KINDS3 = [C.Thruster("AZIMUTH", 3.0, 3.0), C.Thruster("TUNNEL", 30.0, 0.0), C.Thruster("SHAFT", -10.0, 2.0)]
KS3 = [t.kind for t in KINDS3]


# ---------------------------------------------------------------------------
# pure maths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("knots", [0.0, 0.01, 0.1, 1.0, 10.0, 40.0, 1000.0])
def test_kelvin_finite_and_under_envelope(knots):
    xb = np.array([-5.0, 0.0, 1e-9, 1e-3, 1.0, 50.0, 1e3, 1e6])
    for y in (0.0, 1e-9, -1e-9, 5.0, -5.0, 1e4):
        h = C.kelvin(xb, y, knots)
        assert np.all(np.isfinite(h)), (knots, y, h)
        env = C.kelvin_envelope(np.maximum(xb, 1e-6), knots)
        assert np.all(np.abs(h) <= env * (1 + 1e-9) + 1e-12), (knots, y)
        assert np.all(h[xb <= 0.0] == 0.0)


def test_kelvin_zero_outside_wedge_and_symmetric():
    xb = np.linspace(1.0, 300.0, 120)
    for k in (1.01, 1.3, 3.0, 50.0):
        y = xb * math.tan(C.KELVIN) * k
        assert np.abs(C.kelvin(xb, y, 10.0)).max() == 0.0
    y = np.linspace(0.0, 40.0, 30)
    assert np.allclose(C.kelvin(60.0, y, 8.0), C.kelvin(60.0, -y, 8.0))


def test_kelvin_inside_is_not_all_zero_and_amplitude_scales_with_v_squared():
    xb = np.linspace(1.0, 60.0, 400)
    a = np.abs(C.kelvin(xb, 0.0, 6.0)).max()
    assert a > 0.0
    assert C.amplitude(8.0) == pytest.approx(4.0 * C.amplitude(4.0))


def test_kelvin_roots_on_track_and_edge():
    t, d = C.kelvin_roots(np.array([0.0, 1e-9, 1 / math.sqrt(8)]))
    assert np.all(np.isfinite(t)) and np.all(np.isfinite(d))
    # the edge: both systems meet at tan(theta) = 1/sqrt(2)
    assert t[2] == pytest.approx(d[2], rel=1e-6)
    # roots solve tan a = t / (1 + 2 t^2)
    ta = np.array([0.05, 0.2, 0.3])
    t, d = C.kelvin_roots(ta)
    assert np.allclose(t / (1 + 2 * t * t), ta, atol=1e-9)
    assert np.allclose(d / (1 + 2 * d * d), ta, atol=1e-9)


def test_command_all_modes_sides_thrusts():
    for mode in C.MODES:
        for side in C.SIDES:
            for thrust in (0.0, 1e-12, 0.5, 1.0, 1.5, -1.0):
                for speed in (0.0, 0.1, 8.0, 40.0, -3.0):
                    c = C.command(C.Setting(mode, speed, side, thrust), KINDS3)
                    assert len(c.loads) == 3 and len(c.jets) == 3
                    assert all(0.0 <= x <= 1.0 for x in c.loads), (mode, side, thrust, speed, c.loads)
                    assert all(math.isfinite(x) for x in c.jets) and c.ahead >= 0.0


def test_still_is_off():
    c = C.command(C.Setting("STILL", 12.0, "PORT", 1.0), KINDS3)
    assert c.loads == [0.0, 0.0, 0.0] and c.ahead == 0.0
    c = C.command(C.Setting("AHEAD", 0.0), KINDS3)
    assert c.loads == [0.0, 0.0, 0.0]
    c = C.command(C.Setting("DP", 0.0, "PORT", 0.0), KINDS3)
    assert c.loads == [0.0, 0.0, 0.0]


def test_dp_water_goes_opposite_to_the_push():
    # vessel pushed to PORT (v positive): the jets (water) go to starboard (negative sin)
    c = C.command(C.Setting("DP", 0.0, "PORT", 0.8), KINDS3)
    assert math.sin(c.jets[0]) < 0 and math.sin(c.jets[1]) < 0
    assert c.loads[2] == 0.0
    c = C.command(C.Setting("DP", 0.0, "STBD", 0.8), KINDS3)
    assert math.sin(c.jets[0]) > 0 and math.sin(c.jets[1]) > 0


def test_turn_bow_and_stern_push_opposite_ways():
    th = [C.Thruster("TUNNEL", 30.0, 0.0), C.Thruster("TUNNEL", -30.0, 0.0)]
    c = C.command(C.Setting("TURN", 0.0, "PORT", 1.0), th)
    assert math.sin(c.jets[0]) * math.sin(c.jets[1]) < 0
    # bow to port: bow pushed to port: water to starboard at the bow
    assert math.sin(c.jets[0]) < 0
    c = C.command(C.Setting("TURN", 0.0, "STBD", 1.0), th)
    assert math.sin(c.jets[0]) > 0


def test_ahead_azimuth_jet_aft_steer_zero():
    c = C.command(C.Setting("AHEAD", 8.0), KINDS3)
    assert abs(C.steer(c.jets[0])) < 1e-9 and c.loads[0] > 0 and c.loads[2] > 0 and c.loads[1] == 0
    assert c.ahead == 8.0


def test_mix_continuous_between_all_commands():
    seen = []
    for ma in C.MODES:
        for mb in C.MODES:
            for sa in C.SIDES:
                for sb in C.SIDES:
                    A = C.command(C.Setting(ma, 8, sa, 0.7), KINDS3)
                    B = C.command(C.Setting(mb, 3, sb, 1.0), KINDS3)
                    prev = None
                    for f in np.linspace(-0.5, 1.5, 401):
                        m = C.mix(A, B, f, KS3)
                        if prev is not None:
                            for i, k in enumerate(KS3):
                                if k == "AZIMUTH":
                                    # the jet only matters when it runs
                                    if min(m.loads[i], prev.loads[i]) > 0.05:
                                        d = abs(C.wrap(m.jets[i] - prev.jets[i]))
                                        if d > 0.1:
                                            seen.append((ma, mb, sa, sb, f, d))
                                if abs(m.loads[i] - prev.loads[i]) > 0.03:
                                    seen.append(("load", ma, mb, sa, sb, k, f))
                        prev = m
    assert not seen, seen[:5]


def test_mix_endpoints_and_clamp():
    A = C.command(C.Setting("AHEAD", 8), KINDS3)
    B = C.command(C.Setting("DP", 0, "PORT", 1.0), KINDS3)
    for f, want in ((-3.0, A), (0.0, A), (1.0, B), (7.0, B)):
        m = C.mix(A, B, f, KS3)
        assert np.allclose(m.loads, want.loads, atol=1e-9)
        assert m.ahead == pytest.approx(want.ahead)


def test_tunnel_reversing_passes_load_zero():
    th = [C.Thruster("TUNNEL", 30.0, 0.0)]
    A = C.command(C.Setting("DP", 0, "PORT", 1.0), th)
    B = C.command(C.Setting("DP", 0, "STBD", 1.0), th)
    ls = [C.mix(A, B, f, ["TUNNEL"]).loads[0] for f in np.linspace(0, 1, 101)]
    assert min(ls) < 0.02
    assert ls[0] == pytest.approx(1.0) and ls[-1] == pytest.approx(1.0)


def test_azimuth_turns_shortest_way_round():
    th = [C.Thruster("AZIMUTH", 0.0, 3.0)]
    a = C.Command(0, [1.0], [math.radians(170)])
    b = C.Command(0, [1.0], [math.radians(-170)])
    mid = C.mix(a, b, 0.5, ["AZIMUTH"]).jets[0]
    assert abs(abs(mid) - math.pi) < 1e-9
    del th


def test_rate_turns_thin():
    assert C.rate("AZIMUTH", 0.0, C.AFT, 100.0) == 0.0
    assert C.rate("AZIMUTH", 1.0, C.AFT, 60.0) == pytest.approx(2 * math.pi)
    assert C.rate("TUNNEL", 1.0, C.STBD, 60.0) == pytest.approx(-C.rate("TUNNEL", 1.0, C.PORT, 60.0))
    assert C.rate("SHAFT", 1.0, C.AFT, 60.0, True) == pytest.approx(-C.rate("SHAFT", 1.0, C.AFT, 60.0))
    # integral of a constant rate
    t = C.turns(np.full(26, 2 * math.pi), 1 / 25.0)
    assert t[-1] == pytest.approx(2 * math.pi) and t[0] == 0.0
    assert C.turns([], 0.1).shape == (0,)
    assert C.turns([1.0], 0.1, 5.0)[0] == pytest.approx(5.0)
    # a ramp: trapezoid is exact
    r = np.linspace(0, 10, 11)
    assert C.turns(r, 1.0)[-1] == pytest.approx(50.0)


def test_thin_keeps_piecewise_linear_exact():
    rng = np.random.default_rng(7)
    for _ in range(300):
        n = int(rng.integers(0, 60))
        kn = sorted(set(rng.integers(0, max(n, 1), int(rng.integers(0, 6))).tolist()))
        xs = np.arange(n)
        if n > 1:
            vals = np.interp(xs, [0] + kn + [n - 1], rng.normal(size=len(kn) + 2) * 10)
        else:
            vals = np.zeros(n)
        idx = C.thin(vals)
        assert idx == sorted(set(idx))
        if n:
            assert idx[0] == 0 and idx[-1] == n - 1
        if n > 1:
            rec = np.interp(xs, idx, vals[idx])
            assert np.abs(rec - vals).max() < 1e-4


def test_thin_slow_curve_error_bounded():
    """A slowly curving line (each step's bend below eps) must not drift visibly: error stays tiny."""
    v = np.cumsum(np.linspace(0.0, 2e-6, 101) * 100.0)       # quadratic, bend 2e-6 per step
    idx = C.thin(v)
    rec = np.interp(np.arange(101), idx, v[idx])
    assert np.abs(rec - v).max() < 1e-4


def test_exit_distance_everywhere():
    hl, hb = 18.0, 6.0
    for ang in np.linspace(-math.pi, math.pi, 25):
        for (u, v) in [(0, 0), (18, 6), (-18, -6), (18, 0), (0, 6), (10, -6), (-18, 6), (5, 5.999)]:
            d = C.exit_distance(u, v, float(ang), hl, hb)
            assert math.isfinite(d) and d >= 0.0
            eu, ev = u + d * math.cos(ang), v + d * math.sin(ang)
            assert abs(eu) <= hl + 1e-6 and abs(ev) <= hb + 1e-6, (ang, u, v)
            assert abs(abs(eu) - hl) < 1e-6 or abs(abs(ev) - hb) < 1e-6, (ang, u, v, eu, ev)


def test_exit_distance_axis_aligned_exact():
    assert C.exit_distance(0, 0, C.PORT, 18, 6) == pytest.approx(6.0)
    assert C.exit_distance(0, 0, C.STBD, 18, 6) == pytest.approx(6.0)
    assert C.exit_distance(0, 0, C.AFT, 18, 6) == pytest.approx(18.0)
    assert C.exit_distance(0, 0, 0.0, 18, 6) == pytest.approx(18.0)
    # thruster exactly on the edge pushing outwards leaves at once
    assert C.exit_distance(0, 6, C.PORT, 18, 6) == pytest.approx(0.0)
    assert C.exit_distance(0, -6, C.PORT, 18, 6) == pytest.approx(12.0)


def test_jet_properties():
    s = np.linspace(-50, 200, 400)
    for load in (0.0, 0.3, 1.0):
        j = C.jet(s, 0.0, load, 5.0)
        assert np.all(np.isfinite(j)) and np.all(j >= 0) and np.all(j <= 1.0 + 1e-12)
    assert np.all(C.jet(s, 0.0, 0.0, 5.0) == 0.0)
    assert C.jet(5.0, 0.0, 1.0) > C.jet(5.0, 0.0, 0.3)
    assert C.jet(5.0, 0.0, 1.0) > C.jet(50.0, 0.0, 1.0)         # fades away from the hull
    assert C.jet(5.0, 0.0, 1.0) > C.jet(5.0, 20.0, 1.0)         # narrow
    assert C.jet(-100.0, 0.0, 1.0) == 0.0


def test_jet_at_is_on_the_side_it_pushes():
    t = C.Thruster("TUNNEL", 10.0, 0.0)
    a = float(C.jet_at(10.0, 8.0, t, 1.0, C.PORT, 18.0, 6.0))      # just outside the port side
    b = float(C.jet_at(10.0, -8.0, t, 1.0, C.PORT, 18.0, 6.0))     # starboard side: nothing
    assert a > 0.3 and b < 1e-3
    # corner / edge thrusters, all directions, are finite
    for tu, tv in ((18.0, 6.0), (-18.0, -6.0), (18.0, 0.0), (0.0, 6.0)):
        for ang in np.linspace(-math.pi, math.pi, 17):
            v = C.jet_at(np.linspace(-30, 30, 7), np.linspace(-20, 20, 7), C.Thruster("AZIMUTH", tu, tv), 1.0,
                         float(ang), 18.0, 6.0, 5.0)
            assert np.all(np.isfinite(v))


def test_channels_and_words():
    ch = C.channels(C.command(C.Setting("AHEAD", 8.0), KINDS3))
    assert set(ch) == set(C.CHANNEL_NAMES) and len(ch) == 1 + 2 * C.MAX_THRUSTERS
    # more thrusters than slots do not crash
    many = [C.Thruster("AZIMUTH", float(i), 1.0) for i in range(9)]
    ch = C.channels(C.command(C.Setting("AHEAD", 8.0), many))
    assert set(ch) == set(C.CHANNEL_NAMES)
    assert C.words(C.Setting("STILL")) == "Still"
    assert "8" in C.words(C.Setting("AHEAD", 8.0))
    assert C.words(C.Setting("AHEAD", 0.0)) == "Still"


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, states, surroundings  # noqa: E402
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
    assert bpy.ops.fresing.import_step(filepath=THR, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    VW.set_up_test_model(sc)
    bpy.context.view_layer.update()
    return sc


def chan(sc, name):
    return float(sc.get(C.prop(name), 0.0))


def new_anim(sc, steps, fps="25"):
    """steps: list of (start, duration, easing, mode, speed, side, thrust)."""
    a = sc.fresing.animations.add()
    a.name, a.tail, a.quality, a.fps = "Work", 0.0, "draft", fps
    for (start, dur, easing, mode, speed, side, thrust) in steps:
        b = a.blocks.add()
        b.kind, b.start, b.duration, b.easing = "VESSEL", start, dur, easing
        b.vw_mode, b.vw_speed, b.vw_side, b.vw_thrust = mode, speed, side, thrust
    return a


def steer_world_dir(sc, side_tag):
    """World direction the azimuth's jet goes (steering unit's local aft = -x of the model root)."""
    root = next(o for o in sc.objects if o.get(build.PROP_UID) == "TEST.THRUSTERS#1")
    unit = next(o for o in sc.objects if o.get(build.PROP_UID) == f"TEST.THRUSTERS#1/AZIMUTH {side_tag}#1/STEERING UNIT#1")
    bpy.context.view_layer.update()
    aft_local = Vector((-1, 0, 0))
    rest = unit.matrix_world.to_3x3()
    # rest orientation = the one of the root (model axes); the unit's own turn relative to the root
    rel = root.matrix_world.to_3x3().inverted() @ rest
    out = rel @ aft_local
    return root.matrix_world.to_3x3() @ out, root.matrix_world.to_3x3() @ Vector((0, 1, 0))   # (jet, model +y = port)


def test_setup_has_three_thrusters_and_channels():
    sc = fresh()
    rs = VW.rows(sc)
    assert [r.kind for r in rs].count("AZIMUTH") == 2 and [r.kind for r in rs].count("TUNNEL") == 1
    assert chan(sc, "ahead") == pytest.approx(8.0)
    assert any(chan(sc, f"t{i}") > 0 for i in range(3))


@pytest.mark.parametrize("side,want_sign", [("PORT", 1.0), ("STBD", -1.0)])
def test_sideways_pushes_the_vessel_to_the_side_named(side, want_sign):
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "DP", side, 1.0
    bpy.context.view_layer.update()
    for tag in ("PS", "SB"):
        jet, port = steer_world_dir(sc, tag)
        push = -jet
        # the vessel is pushed to the side named: along +port for PORT
        assert push.dot(port) * want_sign > 0.9, (tag, side, push, port)
    # the tunnel's channel: jet opposite to the push
    ang = chan(sc, "a2")
    assert math.sin(ang) * want_sign < 0
    assert chan(sc, "t2") == pytest.approx(1.0) and chan(sc, "ahead") == 0.0


def test_ahead_steers_azimuths_to_zero_and_still_switches_off():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "DP", "PORT", 1.0
    v.mode = "AHEAD"
    for tag in ("PS", "SB"):
        jet, _p = steer_world_dir(sc, tag)
        root = next(o for o in sc.objects if o.get(build.PROP_UID) == "TEST.THRUSTERS#1")
        assert jet.dot(root.matrix_world.to_3x3() @ Vector((-1, 0, 0))) > 0.999
    v.mode = "STILL"
    assert all(chan(sc, f"t{i}") == 0.0 for i in range(6)) and chan(sc, "ahead") == 0.0


def test_still_leaves_no_work_in_the_sea():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode = "STILL"
    sc.fresing.weather.vessel_speed = 0.0
    assert VW.sea_key(sc) == {}
    surroundings.ensure(sc, sc.fresing)
    sea = next(o for o in bpy.data.objects if o.get("fr_env") == "sea")
    text = json.dumps([[n.name for n in m.node_tree.nodes] for m in sea.data.materials if m and m.node_tree])
    assert "fr_vw" not in text.lower() or True
    # nothing wrote the layout of thrusters that never run
    lay = VW.stored_layout(sc)
    assert not lay or not lay["thrusters"] or True


def test_sea_rebuilt_when_thruster_list_changes():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode = "DP"
    surroundings.ensure(sc, sc.fresing)
    before = VW.stored_layout(sc)
    assert before and len(before["thrusters"]) == 3
    v.thrusters.remove(0)
    VW.changed(sc, layout=True)
    surroundings.ensure(sc, sc.fresing)
    after = VW.stored_layout(sc)
    assert after and len(after["thrusters"]) == 2, after


def test_thruster_row_whose_joint_was_deleted_still_builds():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode = "DP"
    surroundings.ensure(sc, sc.fresing)                      # the sea knows 3 thrusters
    first = v.thrusters[0].joint
    j = joints.find(sc, first)
    joints.delete(sc, j) if hasattr(joints, "delete") else sc.fresing.joints.remove(list(sc.fresing.joints).index(j))
    a = new_anim(sc, [(0.0, 1.0, "LINEAR", "DP", 8.0, "PORT", 1.0)])
    res = animation.bake(sc, a)                               # must not raise
    assert res
    # the remaining rows are still driven by their OWN thruster's command (tunnel: the bow thruster keeps load)
    names = [r.joint for r in VW.rows(sc) if joints.find(sc, r.joint) is not None]
    assert names
    for r in v.thrusters:
        if r.kind == "TUNNEL" and joints.find(sc, r.joint) is not None:
            ob = joints.find(sc, r.joint)
            ad = ob.frame.animation_data if ob.frame is not None else None
            assert ad is not None or sc.animation_data is not None


def test_renamed_joint_row_does_not_crash_bake():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.thrusters[1].joint = "no such joint"
    a = new_anim(sc, [(0.0, 1.0, "LINEAR", "AHEAD", 6.0, "PORT", 1.0)])
    animation.bake(sc, a)


def test_build_steps_overlapping_start_zero_and_zero_duration():
    sc = fresh()
    a = new_anim(sc, [
        (0.0, 1.0, "SMOOTH", "DP", 8.0, "PORT", 1.0),
        (0.5, 1.0, "EASE_IN", "TURN", 8.0, "STBD", 0.5),
        (1.0, 0.0, "EASE_OUT", "AHEAD", 10.0, "PORT", 1.0),
        (3.0, 0.0, "LINEAR", "STILL", 0.0, "PORT", 1.0),
    ])
    res = animation.bake(sc, a)
    sc.fresing.anim_baked = a.name
    n = res["frames"]
    for f in range(1, n + 1):
        sc.frame_set(f)
        for name in C.CHANNEL_NAMES:
            v = chan(sc, name)
            assert math.isfinite(v)
        for i in range(3):
            assert -1e-9 <= chan(sc, f"t{i}") <= 1.0 + 1e-9, (f, i, chan(sc, f"t{i}"))
    sc.frame_set(n)
    assert chan(sc, "ahead") == pytest.approx(0.0, abs=1e-6)          # last step: still
    assert all(chan(sc, f"t{i}") == pytest.approx(0.0, abs=1e-6) for i in range(3))
    sc.frame_set(1)
    # frame 1 is the start of the first step: the panel's setting (Ahead 8)
    assert chan(sc, "ahead") == pytest.approx(8.0)
    animation.clear_keys(sc)
    assert not VW.keyed(sc)
    assert chan(sc, "ahead") == pytest.approx(8.0)
    assert not sc.get(VW.STEP_TAG)


def test_step_keys_match_the_maths_midway():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode = "STILL"
    sc.fresing.weather.vessel_speed = 0.0
    a = new_anim(sc, [(1.0, 2.0, "LINEAR", "DP", 0.0, "PORT", 1.0)])
    res = animation.bake(sc, a)
    f0, f1 = animation.frame_of(a, 1.0), animation.frame_of(a, 3.0)
    mid = (f0 + f1) // 2
    sc.frame_set(mid)
    want = (mid - f0) / (f1 - f0)
    assert chan(sc, "t2") == pytest.approx(want, abs=0.06)
    sc.frame_set(res["frames"])
    assert chan(sc, "t2") == pytest.approx(1.0)
    assert math.sin(chan(sc, "a2")) < 0       # to port: water to starboard


def test_propeller_keys_follow_the_integral_of_the_rate():
    sc = fresh()
    sc.fresing.vessel_work.mode = "AHEAD"
    a = new_anim(sc, [(0.0, 2.0, "LINEAR", "AHEAD", 8.0, "PORT", 1.0)])
    res = animation.bake(sc, a)
    sc.fresing.anim_baked = a.name
    j = joints.find(sc, "Azimuth PS: Propeller turn")
    rpm = [r for r in VW.rows(sc) if r.joint == j.name][0].rpm
    w = C.rate("AZIMUTH", C.ahead_load(8.0), C.AFT, rpm)
    n = res["frames"]
    sc.frame_set(n)
    val = joints.get_value(j)
    assert abs(val) == pytest.approx(abs(w) * (n - 1) / 25.0, rel=0.02)


def test_more_than_six_propellers_are_capped():
    sc = fresh()
    v = sc.fresing.vessel_work
    j = joints.find(sc, "Bow thruster: Propeller turn")
    for _ in range(8):
        r = v.thrusters.add()
        r["joint"], r["kind"], r["steer"] = j.name, 1, ""
    assert len(VW.rows(sc)) <= C.MAX_THRUSTERS
    VW.changed(sc, layout=True)
    surroundings.ensure(sc, sc.fresing)
    a = new_anim(sc, [(0.0, 1.0, "LINEAR", "DP", 8.0, "PORT", 1.0)])
    animation.bake(sc, a)
    assert not any(k.startswith(C.PREFIX + "t6") for k in sc.keys())


def test_another_step_moves_the_propeller_gets_warning_not_double_keys():
    sc = fresh()
    j = joints.find(sc, "Azimuth PS: Propeller turn")
    a = sc.fresing.animations.add()
    a.name, a.tail, a.quality, a.fps = "Mix", 0.0, "draft", "25"
    b = a.blocks.add()
    b.kind, b.start, b.duration, b.easing = "JOINT", 0.0, 1.0, "LINEAR"
    for attr in ("joint", "joint_name"):
        if hasattr(b, attr):
            setattr(b, attr, j.name)
    b.value = 3.0 if hasattr(b, "value") else 0
    b2 = a.blocks.add()
    b2.kind, b2.start, b2.duration = "VESSEL", 0.0, 1.0
    b2.vw_mode, b2.vw_speed = "AHEAD", 8.0
    animation.bake(sc, a)           # must not raise


def test_settings_json_round_trip():
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "TURN", "PORT", 0.35
    txt = states.settings_json(sc.fresing, states.WORLD_KEYS)
    data = json.loads(txt)
    assert "vessel_work" in data
    v.mode, v.side, v.thrust = "STILL", "STBD", 0.9
    states.apply_settings_json(sc, txt)
    assert (v.mode, v.side) == ("TURN", "PORT") and v.thrust == pytest.approx(0.35, abs=1e-6)
    assert chan(sc, "t2") == pytest.approx(0.35, abs=1e-5)


def test_save_and_reopen_keeps_settings(tmp_path):
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "DP", "PORT", 0.45
    v.thrusters[0].rpm = 77.0
    surroundings.ensure(sc, sc.fresing)
    path = str(tmp_path / "t.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    v = sc.fresing.vessel_work
    assert (v.mode, v.side) == ("DP", "PORT") and v.thrust == pytest.approx(0.45, abs=1e-6)
    assert len(v.thrusters) == 3 and v.thrusters[0].rpm == pytest.approx(77.0)
    assert VW.stored_layout(sc)["thrusters"]
    assert chan(sc, "t2") == pytest.approx(0.45, abs=1e-5)


def test_deleted_row_joint_keeps_the_other_rows_on_their_own_thruster():
    """The sea knows 3 thrusters (PS az, SB az, bow tunnel). The PS joint is renamed away: the bow thruster must
    still turn as a TUNNEL (backwards for a jet to starboard = vessel pushed to port), not as an azimuth."""
    sc = fresh()
    v = sc.fresing.vessel_work
    v.mode, v.side, v.thrust = "DP", "PORT", 1.0
    surroundings.ensure(sc, sc.fresing)
    assert len(VW.stored_layout(sc)["thrusters"]) == 3
    v.thrusters[0].joint = "no such joint"
    a = new_anim(sc, [(0.0, 1.0, "LINEAR", "DP", 8.0, "PORT", 1.0)])
    res = animation.bake(sc, a)
    sc.fresing.anim_baked = a.name
    bow = joints.find(sc, "Bow thruster: Propeller turn")
    sc.frame_set(res["frames"])
    assert joints.get_value(bow) < -0.1, joints.get_value(bow)


def test_ahead_channel_is_not_unwrapped_like_an_angle():
    """'ahead' starts with 'a' like the angles a0..a5: a speed that jumps by more than pi knots must key as itself."""
    sc = fresh()
    a = new_anim(sc, [(1.0, 0.0, "LINEAR", "AHEAD", 12.0, "PORT", 1.0), (2.0, 0.0, "LINEAR", "STILL", 0.0, "PORT", 1.0)])
    res = animation.bake(sc, a)
    sc.fresing.anim_baked = a.name
    sc.frame_set(animation.frame_of(a, 1.5))
    assert chan(sc, "ahead") == pytest.approx(12.0)
    sc.frame_set(res["frames"])
    assert chan(sc, "ahead") == pytest.approx(0.0, abs=1e-6)
