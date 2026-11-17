"""Task 0173, independent tester (did not write the code): points 2 and 6.

Point 2 – a cable's weight in water: ``core/catenary.WET_200`` is 38 kg/m (was 51), ``wet_weight`` scales with Ø².
In ``blender/paths_sea.py`` mode LAYBACK fixes the shape by the layback (the tensions follow from the weight), mode
TENSION fixes it by the bottom tension and the weight. Checked on the sea test model (tests/data/test_sea.step,
``paths_sea.set_up_test_model``: 15 m of water, layback 20 m) and in plain Python.

Point 6 – Build's last step for cables (``paths._bake``): the cables kept tight by their winch go first and write
their speed joint's keys; a cable whose speed follows one of those joints (directly or down a chain) has its places
read again afterwards, so it is drawn from the payouts at the FIRST Build. Checked on the spooling test model
(tests/data/test_spool.step, ``spool.set_up_test_model``): the wire on the drum is kept tight while a weight it
hangs is lowered 0.3 m; the carousel's power cable follows the wire's speed joint.
"""

import math
import os
import re

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
SEA = os.path.join(HERE, "data", "test_sea.step")
SPOOL = os.path.join(HERE, "data", "test_spool.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, flex, joints, paths, paths_sea, spool  # noqa: E402
from fresing_render.core import catenary as C  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("tightfollow"))


def load(folder, model):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    paths_sea.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    return sc


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


# ===========================================================================
# Point 2: the weight in water
# ===========================================================================

def test_wet_weight_is_38_at_200_and_scales_with_the_square():
    assert C.WET_200 == pytest.approx(38.0)
    for d in (0.05, 0.1, 0.2, 0.3, 0.45):
        assert C.wet_weight(d) == pytest.approx(38.0 * (d / 0.2) ** 2, rel=1e-12)
    assert C.wet_weight(0.4) == pytest.approx(4 * C.wet_weight(0.2))


def test_tensions_top_is_bottom_plus_weight_times_height_for_any_weight():
    rng = np.random.default_rng(7)
    for _ in range(50):
        a, h, w = rng.uniform(1, 200), rng.uniform(1, 300), rng.uniform(1, 200)
        bt, tp = C.tensions(a, h, w)
        assert float(bt) == pytest.approx(a * w * C.G / 1000.0, rel=1e-12)
        assert float(tp - bt) == pytest.approx(w * C.G * h / 1000.0, rel=1e-9)
        # the shape (a) fixed: both tensions are linear in the weight
        bt2, tp2 = C.tensions(a, h, 2 * w)
        assert float(bt2) == pytest.approx(2 * float(bt)) and float(tp2) == pytest.approx(2 * float(tp))


def test_lead_numbers_of_the_demo_lay_with_38():
    """The brief: layback kept at 32 m, ~30 m from the hang-off to the seabed: bottom ≈ 7.7 kN, top ≈ 18.9 kN, 66°.
    Checked with an independent closed form (a from X = a acosh(1 + h/a) by Newton, not the app's bisection)."""
    h, X, w = 30.0, 32.0, C.wet_weight(0.2)
    a = 20.0
    for _ in range(100):                                    # Newton on f(a) = a acosh(1 + h/a) - X
        f = a * math.acosh(1 + h / a) - X
        q = h / a
        df = math.acosh(1 + q) - q / math.sqrt(q * (q + 2))
        a -= f / df
    assert float(C.a_for_span(X, h)) == pytest.approx(a, rel=1e-9)
    bottom, top = a * w * C.G / 1000, (a + h) * w * C.G / 1000
    assert bottom == pytest.approx(7.7, abs=0.15) and top == pytest.approx(18.9, abs=0.2)
    s = math.sqrt(h * h + 2 * a * h)
    assert math.degrees(math.atan2(s, a)) == pytest.approx(66.0, abs=1.0)


def test_no_text_still_says_51_kg_or_500_N_per_m():
    """Panel tooltip, guide and code: the default weight is 38 kg/m at Ø 200 everywhere. (History comments that say
    what it *was* are fine.)"""
    desc = bpy.context.scene.fresing.bl_rna.properties["cables"].fixed_type.properties["sea_weight"].description
    assert "38 kg/m" in desc and "51" not in desc
    guide = open(os.path.join(ROOT, "docs", "USER-GUIDE.md"), encoding="utf-8").read()
    assert "about 38 kg/m for a 200 mm power cable" in guide
    bad = []
    pat = re.compile(r"(\b51(\.0)?\s*kg)|(\b500\s*N\s*/\s*m)|(\b490\s*N\s*/\s*m)")
    for base, _dirs, files in os.walk(os.path.join(ROOT, "fresing_render")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(base, fn)
            for k, line in enumerate(open(p, encoding="utf-8"), 1):
                if pat.search(line) and "was" not in line:
                    bad.append(f"{os.path.relpath(p, ROOT)}:{k}: {line.strip()}")
    for line in guide.splitlines():
        if pat.search(line):
            bad.append(f"docs/USER-GUIDE.md: {line.strip()}")
    assert not bad, "still the old weight:\n" + "\n".join(bad)


# ---------------------------------------------------------------------------
# the sea test model
# ---------------------------------------------------------------------------

@pytest.fixture()
def sea(folder):
    sc = load(folder, SEA)
    paths_sea.set_up_test_model(sc)
    return sc


def sea_cable(sc):
    return paths.find(sc, paths_sea.TEST_CABLE)


def state(sc):
    it = sea_cable(sc)
    n = paths_sea.numbers(sc, it)
    line = paths.shape_now(sc, it).copy()
    assert len(line) > 10 and np.isfinite(line).all()
    return n, line, np.array(it.sea_start), float(it.sea_mark)


def seg_dist(points, line):
    """Distance of each point to the polyline."""
    a, b = line[:-1], line[1:]
    ab = b - a
    t = np.clip(((points[:, None, :] - a[None]) * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-18)[None],
                0.0, 1.0)
    q = a[None] + t[..., None] * ab[None]
    return np.linalg.norm(points[:, None, :] - q, axis=-1).min(1)


def test_default_weight_is_from_the_diameter(sea):
    it = sea_cable(sea)
    assert it.sea_weight == 0.0 and it.sea_mode == "LAYBACK"
    n = paths_sea.numbers(sea, it)
    assert n["weight"] == pytest.approx(C.wet_weight(float(it.diameter)), rel=1e-9)
    assert n["weight"] == pytest.approx(38.0 * (float(it.diameter) / 0.2) ** 2, rel=1e-9)
    # the tensions shown are those of that weight
    assert n["bottom"] == pytest.approx(n["a"] * n["weight"] * C.G / 1000.0, rel=1e-6)
    assert n["top"] - n["bottom"] == pytest.approx(n["weight"] * C.G * n["height"] / 1000.0, rel=1e-6)


def test_layback_mode_keeps_the_shape_whatever_the_weight(sea):
    sc = sea
    n0, line0, start0, mark0 = state(sc)
    assert n0["layback"] == pytest.approx(20.0, abs=0.01)
    w0 = n0["weight"]
    for w in (w0 * 2.0, 1.0, 500.0, 0.0):
        sea_cable(sc).sea_weight = w
        n, line, start, mark = state(sc)
        ww = w if w > 0 else w0
        assert n["weight"] == pytest.approx(ww)
        assert line.shape == line0.shape and float(np.abs(line - line0).max()) < 1e-4, w
        assert float(np.abs(start - start0).max()) < 1e-6 and mark == pytest.approx(mark0, abs=1e-6)
        for k in ("layback", "angle", "laid", "hanging", "a", "height"):
            assert n[k] == pytest.approx(n0[k], rel=1e-6, abs=1e-6), (w, k)
        assert n["bottom"] == pytest.approx(n0["bottom"] * ww / w0, rel=1e-6)
        assert n["top"] == pytest.approx(n0["top"] * ww / w0, rel=1e-6)
        assert n["top"] - n["bottom"] == pytest.approx(ww * C.G * n["height"] / 1000.0, rel=1e-6)


def test_tension_mode_with_the_default_weight(sea):
    """Bottom tension typed, weight from the Ø: a = T / (w g); typing that same weight changes nothing; doubling
    tension and weight together keeps the shape; doubling only the weight shortens the layback."""
    sc = sea
    it = sea_cable(sc)
    it.sea_mode = "TENSION"
    it = sea_cable(sc)
    it.sea_tension = 3.0
    n1, line1, start1, _m = state(sc)
    w0 = C.wet_weight(float(sea_cable(sc).diameter))
    assert n1["weight"] == pytest.approx(w0)
    assert n1["bottom"] == pytest.approx(3.0, rel=1e-5)      # (the solve along reads a back: ~2e-6)
    assert n1["a"] == pytest.approx(3000.0 / (w0 * C.G), rel=1e-5)
    assert n1["layback"] == pytest.approx(float(C.span(n1["a"], n1["height"])), abs=1e-3)
    assert n1["top"] - n1["bottom"] == pytest.approx(w0 * C.G * n1["height"] / 1000.0, rel=1e-6)
    sea_cable(sc).sea_weight = w0                           # the same weight, typed
    n2, line2, start2, _m = state(sc)
    assert float(np.abs(line2 - line1).max()) < 1e-4 and n2["layback"] == pytest.approx(n1["layback"], abs=1e-6)
    it = sea_cable(sc)
    it.sea_weight = 2 * w0
    sea_cable(sc).sea_tension = 6.0
    n3, line3, start3, _m = state(sc)
    assert n3["a"] == pytest.approx(n1["a"], rel=1e-5)
    for k in ("layback", "angle", "hanging", "laid"):
        assert n3[k] == pytest.approx(n1[k], rel=1e-5, abs=1e-5), k
    assert float(np.abs(start3 - start1).max()) < 1e-4
    assert seg_dist(line3, line1).max() < 2e-3 and seg_dist(line1, line3).max() < 2e-3
    assert n3["bottom"] == pytest.approx(6.0, rel=1e-5) and n3["top"] == pytest.approx(2 * n1["top"], rel=1e-5)
    sea_cable(sc).sea_tension = 3.0                         # heavier at the same tension: steeper, nearer
    n4, _l, _s, _m = state(sc)
    assert n4["a"] == pytest.approx(n1["a"] / 2, rel=1e-5) and n4["layback"] < n1["layback"] - 0.5
    assert n4["angle"] > n1["angle"]
    # back to LAYBACK: the typed layback holds again, whatever the weight
    sea_cable(sc).sea_mode = "LAYBACK"
    n5, _l, _s, _m = state(sc)
    assert n5["layback"] == pytest.approx(20.0, abs=0.01)
    assert n5["bottom"] == pytest.approx(n5["a"] * 2 * w0 * C.G / 1000.0, rel=1e-6)


def test_built_layback_animation_tensions_follow_a_weight_typed_after_build(sea):
    """Built, LAYBACK: the numbers along the animation have the shape of the layback; a weight typed after the Build
    changes only the tensions shown – at every frame – never the shape."""
    sc = sea
    a = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    r = animation.bake(sc, a)
    assert not [t for t in r["warnings"] if "sea" in t.lower()], r["warnings"]
    frames = (sc.frame_start, (sc.frame_start + sc.frame_end) // 2, sc.frame_end)
    before = {}
    for f in frames:
        sc.frame_set(f)
        before[f] = state(sc)
    w0 = before[frames[0]][0]["weight"]
    sea_cable(sc).sea_weight = 3 * w0
    for f in frames:
        sc.frame_set(f)
        n, line, _s, _m = state(sc)
        n0, line0 = before[f][0], before[f][1]
        assert n["weight"] == pytest.approx(3 * w0)
        assert n["layback"] == pytest.approx(n0["layback"], abs=1e-4), f
        assert float(np.abs(line - line0).max()) < 1e-3, f
        assert n["bottom"] == pytest.approx(3 * n0["bottom"], rel=1e-4), (f, n["bottom"], n0["bottom"])
        assert n["top"] == pytest.approx(3 * n0["top"], rel=1e-4), (f, n["top"], n0["top"])


# ===========================================================================
# Point 6: cables that follow a kept-tight winch
# ===========================================================================

DROP = 0.3                                                  # m the weight is lowered: the wire pays out as much


def spool_model(folder, follow=True, ratio=1.0, chain=False, follower_tight=False, step_on_wire=False,
                frame_shown=None, drop=DROP):
    """The spool model with the wire kept tight while the weight is lowered ``drop`` m in 2 s; the power cable's
    speed follows the wire's (``ratio``), or down a chain through an extra joint that moves nothing (``chain``).
    Returns (scene, animation) – not built."""
    sc = load(folder, SPOOL)
    spool.set_up_test_model(sc)
    sc.fresing.animations.remove(sc.fresing.animations.find(spool.TEST_ANIMATION))
    weight = named(sc, "WEIGHT")
    m = build.model_root_of(weight).matrix_world
    from mathutils import Vector
    joints.create(sc, "SLIDE", [weight], m @ Vector((0.9, 0.0, 0.2)), (m.to_3x3() @ Vector((0, 0, -1))).normalized(),
                  name="Weight down")
    update()
    assert not paths.set_keep_tight(sc, paths.find(sc, "Wire"), True)
    wire_joint = paths.find(sc, "Wire").joint
    pc_joint = joints.find(sc, paths.find(sc, "Power cable").joint)
    if chain:
        mid = joints.create(sc, "SLIDE", [], m @ Vector((0.0, 0.0, 0.0)), (m.to_3x3() @ Vector((1, 0, 0))).normalized(),
                            name="Middle", base=build.model_root_of(weight), allow_empty=True)
        mid = joints.find(sc, "Middle")
        mid.use_limits = False
        joints.set_follows(sc, joints.find(sc, mid.name), wire_joint, ratio=1.0)
        joints.set_follows(sc, joints.find(sc, paths.find(sc, "Power cable").joint), "Middle", ratio=ratio)
    elif follow:
        joints.set_follows(sc, pc_joint, wire_joint, ratio=ratio)
    if follower_tight:
        paths.set_keep_tight(sc, paths.find(sc, "Power cable"), True)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Lower the weight", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Weight down", 0.0, 2.0, "LINEAR"
    b.use_from = True
    b.to_dist = drop
    if step_on_wire:                                        # a step moves the wire's speed: the winch is skipped
        b2 = a.blocks.add()
        b2.kind, b2.joint, b2.start, b2.duration, b2.easing = "JOINT", wire_joint, 0.0, 2.0, "LINEAR"
        b2.use_from = True
        b2.to_dist = drop
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    if frame_shown is not None:
        sc.frame_set(frame_shown)
    return sc, a


def build_spool(sc, a):
    for k in ("steps",):
        paths._STATE[k] = 0
        flex._STATE[k] = 0
    r = animation.bake(sc, a)
    bad = [t for t in r["warnings"] if "cable" in t.lower() or "Wire" in t]
    return bad, paths._STATE["steps"], flex._STATE["steps"]


def stored(sc, name):
    got = paths._arrays(sc, paths.find(sc, name))
    assert got is not None, f"{name}: no shapes"
    return got[0].astype(float).copy(), got[1].astype(float).copy()


def payout_of(sc, name):
    """Metres paid out at the frame shown (the cable's own speed joint, through its chain)."""
    return paths_sea.payout(sc, paths.find(sc, name))


def coil_length(sc, name):
    """The power cable's drawn length from its first point (on the coil) to its last: changes with the payout."""
    co, s = stored(sc, name)
    return s[:, -1] - s[:, 0], co


def assert_moves_with_payout(sc, name, expect_pay):
    """The follower is drawn from the payout at every frame: its first point (where it leaves the carousel) moves
    between the first and the last frame, and the shapes mesh has one shape per frame."""
    co, s = stored(sc, name)
    frames = sc.frame_end - sc.frame_start + 1
    assert co.shape[0] == frames, (co.shape, frames)
    assert paths.find(sc, name).moving
    sc.frame_set(sc.frame_end)
    assert payout_of(sc, name) == pytest.approx(expect_pay, abs=0.01)
    moved = float(np.abs(co[-1, 0] - co[0, 0]).max())
    dlen = abs(float((s[-1, -1] - s[-1, 0]) - (s[0, -1] - s[0, 0])))
    assert moved > 0.01 or dlen > 0.05, (moved, dlen)
    return co, s


def rebake_same(sc, name, first):
    paths._motion_bake(sc)
    again = stored(sc, name)
    assert again[0].shape == first[0].shape
    d = float(np.abs(again[0] - first[0]).max())
    assert d < 1e-4, f"{name}: the re-bake differs from the first Build by {d * 1000:.2f} mm"
    return again


def test_follower_reference_and_pass_count(folder):
    """The plain case (as the author's test) + how many passes through the frames it costs: one more than without
    the follower, never more."""
    sc, a = spool_model(folder, follow=False)
    bad, steps_free, _fs = build_spool(sc, a)
    assert not bad, bad
    pc_free = stored(sc, "Power cable")
    frames = sc.frame_end - sc.frame_start + 1
    sc, a = spool_model(folder)
    bad, steps, _fs = build_spool(sc, a)
    assert not bad, bad
    first = assert_moves_with_payout(sc, "Power cable", DROP)
    assert steps == steps_free + frames, (steps, steps_free, frames)
    rebake_same(sc, "Power cable", first)
    # not following, it stood still (the shapes of one frame or a standing shape)
    assert pc_free[0].shape[0] == 1 or float(np.abs(pc_free[0][-1] - pc_free[0][0]).max()) < 1e-6


def test_no_extra_pass_when_nothing_follows(folder, monkeypatch):
    """Nothing follows the kept-tight wire: the Build passes through the frames exactly as often as with the old order
    (``_after_tight`` switched off), and draws the same."""
    sc, a = spool_model(folder, follow=False)
    bad, steps_new, fsteps_new = build_spool(sc, a)
    assert not bad
    wire_new = stored(sc, "Wire")
    sc, a = spool_model(folder, follow=False)
    monkeypatch.setattr(paths, "_after_tight", lambda *a_, **k_: ())
    bad, steps_old, fsteps_old = build_spool(sc, a)
    assert not bad
    assert (steps_new, fsteps_new) == (steps_old, fsteps_old)
    assert float(np.abs(stored(sc, "Wire")[0] - wire_new[0]).max()) < 1e-6


def test_no_extra_pass_when_nothing_is_kept_tight(folder):
    sc, a = spool_model(folder, follow=True)
    paths.set_keep_tight(sc, paths.find(sc, "Wire"), False)
    called = []
    real = paths._after_tight

    def spy(*args, **kw):
        out = real(*args, **kw)
        called.append(out)
        return out
    paths._after_tight = spy
    try:
        _bad, steps, _fs = build_spool(sc, a)
    finally:
        paths._after_tight = real
    frames = sc.frame_end - sc.frame_start + 1
    assert all(c == () for c in called)
    assert steps <= frames, steps                         # one pass at most


def test_chain_of_followers(folder):
    """Power cable follows "Middle" (a joint that moves nothing) which follows the wire."""
    sc, a = spool_model(folder, chain=True)
    assert paths.follows_one_of(sc, paths.find(sc, "Power cable"), {paths.find(sc, "Wire").joint})
    bad, _st, _fs = build_spool(sc, a)
    assert not bad, bad
    first = assert_moves_with_payout(sc, "Power cable", DROP)
    rebake_same(sc, "Power cable", first)


def test_ratio_minus_one(folder):
    """Ratio -1: the carousel hauls in as much as the drum pays out."""
    sc, a = spool_model(folder, ratio=-1.0)
    bad, _st, _fs = build_spool(sc, a)
    assert not bad, bad
    first = assert_moves_with_payout(sc, "Power cable", -DROP)
    rebake_same(sc, "Power cable", first)


def test_the_same_at_any_frame_shown(folder):
    sc, a = spool_model(folder)
    build_spool(sc, a)
    at_start = stored(sc, "Power cable"), stored(sc, "Wire")
    sc, a = spool_model(folder, frame_shown=37)
    assert sc.frame_current == 37
    build_spool(sc, a)
    at_37 = stored(sc, "Power cable"), stored(sc, "Wire")
    for x, y in zip(at_start, at_37):
        assert x[0].shape == y[0].shape and float(np.abs(x[0] - y[0]).max()) < 1e-5


def test_skipped_winch_the_step_decides(folder):
    """A step moves the wire's speed: the winch is skipped (``tight_skipped``) and the step's keys are there before
    the first pass – the follower moves with them, no extra pass is made."""
    sc, a = spool_model(folder, step_on_wire=True)
    assert paths.tight_skipped(sc, paths.find(sc, "Wire"))
    called = []
    real = paths._after_tight

    def spy(*args, **kw):
        out = real(*args, **kw)
        called.append(out)
        return out
    paths._after_tight = spy
    try:
        _bad, steps, _fs = build_spool(sc, a)
    finally:
        paths._after_tight = real
    assert all(c == () for c in called)                    # nothing was written by a winch: nothing read again
    first = assert_moves_with_payout(sc, "Power cable", DROP)
    rebake_same(sc, "Power cable", first)


def test_clear_keys_puts_the_follower_back(folder):
    sc, a = spool_model(folder)
    sc.frame_set(sc.frame_start)
    pc0 = paths.shape_now(sc, paths.find(sc, "Power cable")).copy()
    build_spool(sc, a)
    sc.frame_set(sc.frame_end)
    assert payout_of(sc, "Power cable") == pytest.approx(DROP, abs=0.01)
    animation.clear_keys(sc)
    update()
    for f in (sc.frame_start, sc.frame_end):
        sc.frame_set(f)
        assert payout_of(sc, "Power cable") == pytest.approx(0.0, abs=paths.TIGHT_TOL)    # (live: kept tight
        assert payout_of(sc, "Wire") == pytest.approx(0.0, abs=paths.TIGHT_TOL)           # to TIGHT_TOL)
        now = paths.shape_now(sc, paths.find(sc, "Power cable"))
        assert now.shape == pc0.shape and float(np.abs(now - pc0).max()) < 1e-4
    j = joints.find(sc, paths.find(sc, "Wire").joint)
    assert paths.TIGHT not in j.motion
    # building again gives the first Build's shapes
    sc, a = spool_model(folder)
    build_spool(sc, a)
    ref = stored(sc, "Power cable")
    build_spool(sc, a)
    assert float(np.abs(stored(sc, "Power cable")[0] - ref[0]).max()) < 1e-4


def test_cable_carried_by_a_part_that_follows_the_kept_tight_winch(folder):
    """Not the cable's speed but a carrier of the cable follows the kept-tight wire: the carousel's arm (with the power
    cable's guide sheave) slews with the wire's payout. Its places too are only right once the wire's keys are
    written: the first Build must draw what a re-bake draws."""
    sc, a = spool_model(folder, follow=False)
    sp = spool.find(sc, "Carousel")
    spool.remove_follower(sc, sp, [f.joint for f in sp.followers].index("Arm slew"))
    arm = joints.find(sc, "Arm slew")
    if arm.follows:
        joints.set_follows(sc, arm, "")
    arm = joints.find(sc, "Arm slew")
    arm.use_limits = False
    joints.set_follows(sc, arm, paths.find(sc, "Wire").joint, ratio=0.03)     # 0.03 °/mm: 9° for 0.3 m
    assert not paths.follows_one_of(sc, paths.find(sc, "Power cable"), {paths.find(sc, "Wire").joint})
    _bad, _st, _fs = build_spool(sc, a)
    sc.frame_set(sc.frame_end)
    turned = math.degrees(joints.get_value(joints.find(sc, "Arm slew")))
    assert abs(turned) > 5.0, turned
    first = stored(sc, "Power cable")
    paths._motion_bake(sc)
    again = stored(sc, "Power cable")
    assert again[0].shape[0] == sc.frame_end - sc.frame_start + 1          # the re-bake draws it moving …
    assert first[0].shape == again[0].shape and float(np.abs(first[0] - again[0]).max()) < 1e-4, \
        f"first Build: {first[0].shape[0]} shape(s), re-bake: {again[0].shape[0]}"


def test_follower_with_keep_tight_ticked_too(folder):
    """The power cable follows the wire AND has "Winch keeps it tight" ticked (the panel says it cannot be: its speed
    follows another joint). It is then a plain follower and must still be drawn from the wire's payout at the first
    Build – it is not: it is in the kept-tight list, so ``_after_tight`` leaves it out and it keeps the places read
    before the wire's keys were written."""
    sc, a = spool_model(folder, follower_tight=True)
    assert paths.tight_skipped(sc, paths.find(sc, "Power cable"))
    _bad, _st, _fs = build_spool(sc, a)
    first = stored(sc, "Power cable")
    paths._motion_bake(sc)                                  # (a re-bake reads with the wire's keys already there)
    again = stored(sc, "Power cable")
    frames = sc.frame_end - sc.frame_start + 1
    assert again[0].shape[0] == frames                      # the re-bake draws it moving …
    assert first[0].shape == again[0].shape, \
        f"first Build: {first[0].shape[0]} shape(s), re-bake: {again[0].shape[0]} – it stood still at the first Build"


# ---------------------------------------------------------------------------
# two kept-tight wires, each with a follower; one follower not spooled (a cable into the sea) and listed BEFORE its
# leader: the moving-part model (tests/data/test_moving.step) and the spool model imported into one scene
# ---------------------------------------------------------------------------

MOVING = os.path.join(HERE, "data", "test_moving.step")
NAMES = ("Cable end", "Lift wire", "Wire", "Power cable")


def two_models(folder, tight=True, frame_shown=None):
    from mathutils import Vector
    sc = load(folder, MOVING)
    paths.set_up_moving_model(sc, with_let_go=False)
    assert bpy.ops.fresing.import_step(filepath=SPOOL, quality="draft") == {"FINISHED"}
    spool.set_up_test_model(sc)
    sc.fresing.animations.remove(sc.fresing.animations.find(spool.TEST_ANIMATION))
    assert [c.name for c in sc.fresing.cables] == list(NAMES)
    weight = named(sc, "WEIGHT")
    m = build.model_root_of(weight).matrix_world
    joints.create(sc, "SLIDE", [weight], m @ Vector((0.9, 0.0, 0.2)), (m.to_3x3() @ Vector((0, 0, -1))).normalized(),
                  name="Weight down")
    update()
    for n in ("Wire", "Lift wire"):
        paths.set_keep_tight(sc, paths.find(sc, n), tight)
    for f, lead in (("Power cable", "Wire"), ("Cable end", "Lift wire")):
        joints.find(sc, paths.find(sc, f).joint).use_limits = False
        joints.set_follows(sc, joints.find(sc, paths.find(sc, f).joint), paths.find(sc, lead).joint, ratio=1.0)
    a = sc.fresing.animations[paths.MOVING_ANIMATION]
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Weight down", 0.0, 2.0, "LINEAR"
    b.use_from = True
    b.to_dist = DROP
    sc.fresing.animations_index = sc.fresing.animations.find(paths.MOVING_ANIMATION)
    if frame_shown is not None:
        sc.frame_set(frame_shown)
    return sc, a


def test_two_kept_tight_wires_each_with_a_follower(folder):
    sc, a = two_models(folder)
    bad, steps, _fs = build_spool(sc, a)
    assert not [t for t in bad if "piles up" not in t], bad          # (the sea cable is paid out fast: it piles up)
    frames = sc.frame_end - sc.frame_start + 1
    assert steps == 2 * frames, (steps, frames)                      # ONE extra pass for both followers
    sc.frame_set(sc.frame_end)
    lift = paths.tight_payout(sc, paths.find(sc, "Lift wire"))
    assert lift > 5.0
    assert payout_of(sc, "Cable end") == pytest.approx(lift, abs=1e-4)
    assert payout_of(sc, "Power cable") == pytest.approx(DROP, abs=0.01)
    first = {n: stored(sc, n) for n in NAMES}
    for n in NAMES:
        assert first[n][0].shape[0] == frames, n
    # the sea cable is drawn from its payout: the cable from the hang-off to its end on the seabed grows with it
    got = {}
    for f in (sc.frame_start, sc.frame_end):
        sc.frame_set(f)
        got[f] = paths_sea.numbers(sc, paths.find(sc, "Cable end"))
    s, e = got[sc.frame_start], got[sc.frame_end]
    assert e["laid"] + e["hanging"] > s["laid"] + s["hanging"] + 5.0, (s, e)
    paths._motion_bake(sc)
    for n in NAMES:
        again = stored(sc, n)
        assert again[0].shape == first[n][0].shape and float(np.abs(again[0] - first[n][0]).max()) < 1e-4, n


def test_two_models_the_same_at_any_frame_shown(folder):
    sc, a = two_models(folder)
    build_spool(sc, a)
    ref = {n: stored(sc, n) for n in NAMES}
    sc, a = two_models(folder, frame_shown=150)
    assert sc.frame_current == 150
    build_spool(sc, a)
    for n in NAMES:
        got = stored(sc, n)
        assert got[0].shape == ref[n][0].shape and float(np.abs(got[0] - ref[n][0]).max()) < 1e-4, n


def test_two_models_nothing_kept_tight_one_pass(folder):
    sc, a = two_models(folder, tight=False)
    _bad, steps, _fs = build_spool(sc, a)
    frames = sc.frame_end - sc.frame_start + 1
    assert steps == frames, (steps, frames)
