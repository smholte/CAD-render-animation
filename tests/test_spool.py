"""Task 0080: drums and carousels on the test model (tests/data/test_spool.step, tools/make_test_spool.py).

Blender as a Python module. Numbers from the maker (mm there, metres here)."""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import make_test_spool as M  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, paths, spool  # noqa: E402
from fresing_render.core import spool as S  # noqa: E402

MODEL = os.path.join(HERE, "data", "test_spool.step")


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("spool"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    out = spool.set_up_test_model(sc)
    yield out
    fresing_render.unregister()


def _sc():
    return bpy.context.scene


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def pay(cable: str, metres: float):
    sc = _sc()
    joints.set_value(joints.find(sc, paths.find(sc, cable).joint), metres)
    update()
    paths.refresh(sc)
    update()


def test_set_up(made):
    sc = _sc()
    for name in ("Drum", "Carousel"):
        sp = spool.find(sc, name)
        assert sp is not None and sp.enabled and not sp.problem, (name, sp.problem if sp else None)
    d = spool.find(sc, "Drum")
    w = M.NUMBERS["winch"]
    assert d.r1 == pytest.approx(0.160, abs=1e-3)
    assert abs(d.a_hi - d.a_lo) == pytest.approx(0.4, abs=1e-3)
    c = spool.find(sc, "Carousel")
    assert c.r_in == pytest.approx(0.34, abs=2e-3) and c.r_out == pytest.approx(0.84, abs=2e-3)
    assert paths.find(sc, "Wire").a_kind == "SPOOL" and paths.find(sc, "Power cable").a_kind == "SPOOL"


def test_drum_turns_by_table_and_leave_point_on_its_layer(made):
    sc = _sc()
    sp = spool.find(sc, "Drum")
    j = joints.find(sc, sp.joint)
    assert j.couple_table == "spool:Drum"
    path = spool.path_of(sc, sp)
    for p in (0.0, 0.5, 2.0, 7.3):
        pay("Wire", p)
        it = paths.find(sc, "Wire")
        start = paths.shape_now(sc, it)[0]
        # the leave point in the spool frame: on its layer's rope circle
        fr = spool.frame_cad(sc, sp, {})
        loc = np.linalg.inv(fr) @ np.r_[start, 1.0]
        phi, a, r, _k = S.at(path, np.array([sp.wound - p]))
        assert math.hypot(loc[0], loc[1]) == pytest.approx(float(r[0]), abs=5e-4), p
    pay("Wire", 0.0)


def test_wound_lengths_read_from_the_cad(made):
    """Wound at the start, read from where the CAD cable leaves: the maker's plain estimate + the climbs."""
    sc = _sc()
    d, c = spool.find(sc, "Drum"), spool.find(sc, "Carousel")
    assert d.wound == pytest.approx(M.wound_estimate("wire")["total"] / 1000.0, rel=0.02)
    assert c.wound == pytest.approx(M.wound_estimate("cable")["total"] / 1000.0, rel=0.01)


def _value(sc, name):
    return joints.get_value(joints.find(sc, name))


def test_drum_angle_within_a_hundredth_of_a_degree_over_100_m(made):
    """The drum's turn (the driver, as Blender writes it) against the exact helix: 100 m from 50 m wound on to
    50 m paid out, over three and more layers; the tangent to the fairlead worked out here on its own."""
    sc = _sc()
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    q = np.array(sp.q)
    rho, alpha = math.hypot(q[0], q[1]), math.atan2(q[1], q[0])

    def psi(p):
        _phi, _a, r, _k = S.at(path, W0 - np.asarray(p, dtype=float))
        return np.unwrap(np.atleast_1d(S.tangency(rho, alpha, r, int(sp.hand))))

    ps = np.linspace(-50.0, 49.0, 23)
    layers = set()
    worst = 0.0
    for p in ps:
        pay("Wire", float(p))
        got = _value(sc, sp.joint) * sp.zsign
        motion = joints.find(sc, sp.joint).motion.rotation_euler[2] * sp.zsign
        want = float(S.exact_angle(path, W0, np.array([p]), psi=lambda x: psi(x), psi0=float(psi([0.0])[0]))[0])
        worst = max(worst, abs(got - want), abs(motion - want))
        layers.add(int(S.at(path, np.array([W0 - p]))[3][0]))
    pay("Wire", 0.0)
    assert len(layers) >= 3, layers
    assert math.degrees(worst) < 0.01, math.degrees(worst)


def test_rope_on_the_drum_plus_paid_out_is_what_was_wound(made):
    """The drawn rope ends (Trim Curve) at W0 - p within 1 mm, and the free cable starts where it ends."""
    sc = _sc()
    sp = spool.find(sc, "Drum")
    rope = sp.owner
    mod = rope.modifiers[spool.MOD]
    ins = spool._inputs(mod.node_group)
    for p in (0.0, 3.0, 20.0):
        pay("Wire", p)
        end = getattr(mod.properties.inputs, ins["End"]).value
        assert end + p == pytest.approx(sp.wound, abs=1e-3)
        dg = bpy.context.evaluated_depsgraph_get()
        me = rope.evaluated_get(dg).data
        co = np.array([rope.matrix_world @ v.co for v in me.vertices])
        start = paths.shape_now(sc, paths.find(sc, "Wire"))[0]
        gap = np.linalg.norm(co - start, axis=1).min()
        assert gap < 0.5 * 0.020 + 1e-3, (p, gap)
    pay("Wire", 0.0)


def test_level_wind_follows_the_wrap(made):
    sc = _sc()
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    _phi, a0, _r, _k = S.at(path, np.array([W0]))
    seen = []
    for p in (0.0, 0.5, 1.0, 5.0, 12.0):
        pay("Wire", p)
        _phi, a, _r, _k = S.at(path, np.array([W0 - p]))
        want = float(a[0] - a0[0])
        got = _value(sc, "Level wind")
        assert abs(abs(got) - abs(want)) < 1e-4, (p, got, want)
        seen.append(got)
    pay("Wire", 0.0)
    assert np.ptp(seen) > 0.05                                         # it really goes along
    lo, hi = spool.fleet(sc, sp)
    assert max(lo, hi) < math.radians(1.5)                             # with the level wind: no fleet angle


def test_fleet_angle_warning_without_the_level_wind(made):
    sc = _sc()
    sp = spool.find(sc, "Drum")
    spool.remove_follower(sc, sp, 0)
    sp = spool.find(sc, "Drum")
    text, icon = spool.status(sc, sp)
    assert icon == "ERROR" and "fleet angle" in text.lower() and "flange" in text, text
    deg = math.degrees(math.atan2(0.19, 0.8))
    assert math.degrees(max(sp.fleet_lo, sp.fleet_hi)) == pytest.approx(deg, abs=1.5)
    spool.add_follower(sc, spool.find(sc, "Drum"), "Level wind")
    assert not spool.find(sc, "Drum").problem


def test_carousel_turn_per_metre_and_arm_over_the_turn(made):
    sc = _sc()
    sp = spool.find(sc, "Carousel")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    prev = None
    kp, psi = spool.tables(sc, sp)["psi"]
    for p in (0.0, 1.0, 2.0, 5.0, 9.0, 14.0):
        pay("Power cable", p)
        # the carousel's turn less the leave point's own move round (the arm swings out with the layer)
        th = _value(sc, sp.joint) * sp.zsign - (np.interp(p, kp, psi) - np.interp(0.0, kp, psi))
        if prev is not None:
            # turn per metre between two payouts: the mean of 1/r over the rope between them
            Ls = np.linspace(W0 - p, W0 - prev[0], 400)
            want = np.trapezoid(np.abs(S.turn_per_metre(path, Ls)), Ls) / (p - prev[0])
            assert abs(th - prev[1]) / (p - prev[0]) == pytest.approx(want, rel=1e-3)
        prev = (p, th)
        # the guide (the cable's point after the leave point) stays over the turn being paid out
        it = paths.find(sc, "Power cable")
        start = paths.shape_now(sc, it)[0]
        fr = spool.frame_cad(sc, sp, {})
        loc = np.linalg.inv(fr) @ np.r_[start, 1.0]
        _phi, _a, r, _k = S.at(path, np.array([W0 - p]))
        assert math.hypot(loc[0], loc[1]) == pytest.approx(float(r[0]), abs=5e-4)
        # the arm keeps its guide over the turn being paid out: the guide sheave's middle (where the cable comes
        # onto it, straight above the coil in this model) lies on that turn's circle
        from fresing_render.blender import build
        gs = next(o for o in sc.objects if o.get(build.PROP_NAME) == "GUIDE SHEAVE")
        g = np.linalg.inv(fr) @ np.r_[np.array(gs.matrix_world.translation), 1.0]
        assert math.hypot(g[0], g[1]) == pytest.approx(float(r[0]), abs=2e-3), p
    pay("Power cable", 0.0)


def test_drivers_need_no_python(made):
    sc = _sc()
    assert joints.couplings_simple(sc)
    for name in ("Drum", "Carousel"):
        sp = spool.find(sc, name)
        for ob in (sp.owner, spool._made(sc, sp, "solid")):
            for fc in ob.animation_data.drivers:
                assert fc.driver.type in ("MAX", "AVERAGE") or fc.driver.is_simple_expression, fc.data_path


def test_build_animation_and_no_clash(made):
    from fresing_render.blender import clash
    from fresing_render.core import clash as core
    sc = _sc()
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    animation.bake(sc, a)
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    for f in (1, 100, 201):
        sc.frame_set(f)
        update()
        p = spool.payout(sc, sp)
        start = paths.shape_now(sc, paths.find(sc, "Wire"))[0]
        fr = spool.frame_cad(sc, sp, {})
        loc = np.linalg.inv(fr) @ np.r_[start, 1.0]
        _phi, _a, r, _k = S.at(path, np.array([sp.wound - p]))
        assert math.hypot(loc[0], loc[1]) == pytest.approx(float(r[0]), abs=5e-4), f
    run = clash.check(sc, store=False)
    assert not run.rows, [core.row_text(r) for r in run.rows[:5]]
    animation.clear_keys(sc)
    sc.frame_set(1)


def test_off_shows_the_cad_and_on_again(made):
    sc = _sc()
    sp = spool.find(sc, "Carousel")
    coil = sp.coil
    sp.enabled = False
    it = paths.find(sc, "Power cable")
    assert it.a_kind != "SPOOL" and spool._made(sc, spool.find(sc, "Carousel"), "rope") is None
    assert spool.HIDE not in coil.modifiers
    assert not joints.find(sc, "Carousel turn").couple_table
    spool.find(sc, "Carousel").enabled = True
    sp = spool.find(sc, "Carousel")
    assert paths.find(sc, "Power cable").a_kind == "SPOOL" and sp.owner is not None and not sp.problem
    assert joints.find(sc, "Arm slew").couple_table == "spool:Carousel"
