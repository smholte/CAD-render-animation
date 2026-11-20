"""Task 0229, stand-in for the demo vessel's carousel/drum (study 0226): two things only the private demo vessel proved
so far, proved here on made-up spools and the public spooling test model (tests/data/test_spool.step,
tools/make_test_spool.py).

1. A carousel's layers alternate (layer 1 from the core out, layer 2 from the rim in …). A partly paid-out top layer
   that the cable leaves at its innermost turn is an even layer – an odd number of full layers below it – and paying
   out moves the leave point outwards, towards the rim; with an even number of full layers the top layer leaves at
   its outermost turn and paying out moves it inwards (CLAUDE.md section 8). ``core/spool.py``, no Blender.
2. A Lebus drum whose climbs at the flanges are 7–8 mm of payout apart: its turn follows the cable "by table"
   (``joints.set_table``), and keys that close would be merged by Blender (closer than 0.01). The table is written at
   1000 x the leader's value (``joints.table_keys``), every key is kept, and after Build the drum's turn is within
   0.1° of the exact wound path at frames that run through two climbs. Blender as a Python module.
"""

import math
import os

import numpy as np
import pytest

from fresing_render.core import spool as S

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_spool.step")


# ---------------------------------------------------------------------------------------------------------------------
# 1. carousel: which way the leave point moves on a partly paid-out top layer
# ---------------------------------------------------------------------------------------------------------------------

D = 0.05                    # m: a made-up cable
R_IN, R_OUT = 1.0, 1.6      # m: a made-up carousel (core, rim)


def _carousel(layers, start=1):
    return S.Spool(kind="CAROUSEL", d=D, r_in=R_IN, r_out=R_OUT, a_bot=0.0, a_top=layers * D + 1e-6, start=start)


@pytest.mark.parametrize("full, start", [(3, 1), (2, 1), (1, 1), (3, -1), (2, -1)])
def test_carousel_top_layer_leaves_at_the_side_its_parity_says(full, start):
    """``full`` full layers + 60 % of the next one wound. From the core (start 1): an odd number of full layers puts
    the top layer rim -> core, so the cable leaves at its innermost turn and paying out moves the leave point outwards
    to the rim (the demo's case); an even number the other way. Wound from the rim (start -1): the reverse. The leave
    point's radius changes by one cable diameter per turn, and its height is the top layer's all the way."""
    path = S.wind(_carousel(full + 1, start))
    assert path.layer_count == full + 1
    top = full                                          # 0-based: the partly wound layer
    first = S._first_of_layer(path, top)                # (after the climb into it)
    end = S.layer_end(path, top)
    assert end == pytest.approx(path.total)
    W0 = first + 0.6 * (end - first)
    _phi, a, r, k = S.at(path, np.array([W0]))
    assert int(k[0]) == top and float(a[0]) == pytest.approx(float(S.layer_place(path, top)), abs=1e-9)
    r_a, r_b = R_IN + D / 2, R_OUT - D / 2              # the innermost and outermost rope middles
    climbed = D * path.spool.climb / (2.0 * math.pi)    # (the climb into the layer takes its first quarter turn)
    inwards = (top % 2 == 0) == (start < 0)             # this layer is wound rim -> core
    assert inwards == ((full % 2 == 1) == (start > 0))  # the rule: odd full layers from the core -> wound inwards
    # paying out the wound part of the top layer, back to where it began
    p = np.linspace(0.0, W0 - first, 400)
    phi, a, r, k = S.at(path, W0 - p)
    assert np.all(k == top) and np.allclose(a, a[0], atol=1e-12)
    dr = np.diff(r)
    if inwards:      # leaves at its innermost turn: paying out goes outwards, ending at the rim
        assert np.all(dr > 0.0)
        assert float(r[0]) == pytest.approx(float(r.min())) and float(r[-1]) == pytest.approx(r_b - climbed, abs=1e-6)
        assert float(r[0]) < r_b - 5 * D
    else:            # leaves at its outermost turn: paying out goes inwards, ending at the core
        assert np.all(dr < 0.0)
        assert float(r[0]) == pytest.approx(float(r.max())) and float(r[-1]) == pytest.approx(r_a + climbed, abs=1e-6)
        assert float(r[0]) > r_a + 5 * D
    # one cable diameter per turn (the turns touch)
    per_turn = np.abs(np.diff(r)) / np.abs(np.diff(phi)) * 2.0 * math.pi
    assert np.allclose(per_turn, D, rtol=1e-3)
    # past the top layer's start the leave point is on the full layer below, at the side the top layer began from
    _phi, _a, r_below, k_below = S.at(path, np.array([S.layer_start(path, top) - 0.5]))
    assert int(k_below[0]) == top - 1
    assert float(r_below[0]) == pytest.approx(r_b if inwards else r_a, abs=0.5 * D)


# ---------------------------------------------------------------------------------------------------------------------
# 2. Lebus drum: climbs 7–8 mm of payout apart, the table at 1000 x, the turn after Build
# ---------------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, paths, spool  # noqa: E402

R1 = 0.180                  # m: a made-up first-layer radius – the first climb's pieces 7–8 mm long
CLIMBS = (1, 2)             # the climbs the animation runs through (into layer 2 and layer 3)
MARGIN = 0.15               # m of payout before and after each climb
SECONDS = 4.0               # per climb: 25 fps, about 6 mm of payout per frame


def test_blender_merges_driver_keys_closer_than_a_hundredth():
    """The control: keys 7.7 mm apart on a driver's F-curve are merged by Blender – why the table is read x 1000."""
    ob = bpy.data.objects.new("FR test keys", None)
    try:
        ob["x"] = 0.0
        fc = ob.driver_add('["x"]')
        kp = fc.keyframe_points
        kp.clear()
        n = 20
        kp.add(n)
        co = np.empty(2 * n, dtype=np.float32)
        co[0::2] = 2.0 + 0.0077 * np.arange(n)
        co[1::2] = np.arange(n)
        kp.foreach_set("co", co)
        fc.update()
        assert len(fc.keyframe_points) < n
    finally:
        bpy.data.objects.remove(ob)


@pytest.fixture(scope="module")
def lebus(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("spool_standins"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    spool.set_up_test_model(sc)
    sp = spool.find(sc, "Drum")
    sp.groove = "LEBUS"
    sp = spool.find(sc, "Drum")
    sp.r1 = R1
    sp = spool.find(sc, "Drum")
    assert not sp.problem, sp.problem
    yield sc
    fresing_render.unregister()


def _drum_fcurve(j):
    path, index = joints._channel(j.kind)
    return j.motion.animation_data.drivers.find(path, index=index)


def test_lebus_climb_keys_are_read_at_1000_and_all_kept(lebus):
    sc = lebus
    sp = spool.find(sc, "Drum")
    assert sp.groove == "LEBUS" and sp.r1 == pytest.approx(R1, abs=1e-6)
    path = spool.path_of(sc, sp)
    assert path.spool.groove == S.LEBUS and np.any(path.kind == S.CROSSOVER)
    first_climb = np.nonzero((path.layer == 0) & (path.kind == S.CLIMB))[0]
    lengths = path.L1[first_climb] - path.L0[first_climb]
    assert len(first_climb) > 10 and 0.007 <= lengths.min() and lengths.max() <= 0.0085, lengths
    j = joints.find(sc, sp.joint)
    assert j.couple_table == "spool:Drum"
    xs, ys = joints.table_of(j)
    gaps = np.diff(xs)
    assert gaps.min() < joints.KEY_GAP                    # keys this close would be merged at 1 x …
    assert np.sum((gaps > 0.007) & (gaps < 0.0085)) >= len(first_climb) - 2
    kx, _ky, k = joints.table_keys(xs, ys)
    assert k == 1000.0 and len(kx) == len(xs)             # … so the leader is read x 1000, and no key is left out
    fc = _drum_fcurve(j)
    assert fc.driver.expression.startswith("a * 1000.0")
    fc.update()                                           # (Blender's merge pass: nothing to merge at 1000 x)
    assert len(fc.keyframe_points) == len(xs)
    co = np.empty(2 * len(xs), dtype=np.float32)
    fc.keyframe_points.foreach_get("co", co)
    assert np.allclose((co[0::2] - joints.BIAS) / 1000.0, xs, atol=1e-5)


def _value(sc, name):
    return joints.get_value(joints.find(sc, name))


def test_lebus_drum_turn_after_build_through_two_climbs(lebus):
    """An animation pays the wire out through the climbs into layers 2 and 3 (slowly: a frame every ~6 mm, about one
    per climb piece); after Build the drum's turn – its value and its motion as Blender moves it – is within 0.1° of
    the exact Lebus path at every frame."""
    sc = lebus
    sp = spool.find(sc, "Drum")
    path = spool.path_of(sc, sp)
    W0 = float(sp.wound)
    it = paths.find(sc, "Wire")
    sign = -1.0 if it.reverse else 1.0
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    a.blocks.clear()
    t = 0.0
    spans = []
    for c in CLIMBS:
        L_lo, L_hi = S.layer_start(path, c), S._first_of_layer(path, c)
        p_from, p_to = W0 - (L_lo - MARGIN), W0 - (L_hi + MARGIN)   # (paying in: the leave point climbs up)
        assert 0.0 < p_to < p_from < W0
        spans.append((p_to, p_from))
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", it.joint, t, SECONDS, "LINEAR"
        b.use_from = False                                          # (from the From value, not where it is)
        b.from_dist, b.to_dist = sign * p_from, sign * p_to
        t += SECONDS
    animation.bake(sc, a)
    q = np.array(sp.q)
    rho, alpha = math.hypot(q[0], q[1]), math.atan2(q[1], q[0])

    def psi(p):
        _phi, _a, r, _k = S.at(path, W0 - np.asarray(p, dtype=float))
        return np.unwrap(np.atleast_1d(S.tangency(rho, alpha, r, int(sp.hand))))

    psi0 = float(psi([0.0])[0])
    worst, in_climb, seen = 0.0, 0, set()
    try:
        for f in range(sc.frame_start, sc.frame_end + 1):
            sc.frame_set(f)
            p = spool.payout(sc, sp)
            got = _value(sc, sp.joint) * sp.zsign
            motion = joints.find(sc, sp.joint).motion.rotation_euler[2] * sp.zsign
            want = float(S.exact_angle(path, W0, np.array([p]), psi=psi, psi0=psi0)[0])
            worst = max(worst, abs(got - want), abs(motion - want))
            i, _L = S._index(path, np.array([W0 - p]))
            if path.kind[int(i[0])] == S.CLIMB:
                in_climb += 1
                seen.add(int(path.layer[int(i[0])]))
    finally:
        animation.clear_keys(sc)
        sc.frame_set(1)
    assert seen == {c - 1 for c in CLIMBS}, seen
    assert in_climb >= 40, in_climb
    assert math.degrees(worst) < 0.1, math.degrees(worst)
