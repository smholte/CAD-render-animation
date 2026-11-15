"""Task 0125: a cable into the sea that is let go settles onto the seabed (``FRCable.sea_settle``, blender/paths.py
``settle``). The moving-part test model (tools/make_test_moving.py, ``paths.set_up_moving_model``): the block is
lowered near the seabed (15 m of water), the cable's start and its turn round the SHEAVE are let go at 9.2 s and the
block lifts 5 m again; in 2 s (the set-up's; 4 s is the default) what was let go sinks onto the seabed and lies there.
Blender as a module.
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_moving.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea  # noqa: E402

sys.path.insert(0, os.path.dirname(HERE))


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The model set up as the tour does (settling in 2 s) and built once."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("settle"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    assert paths.add_cable(sc, "x").sea_settle == pytest.approx(4.0)                  # (the default)
    paths.remove(sc, paths.index_of(sc, paths.find(sc, "x")))
    paths.set_up_moving_model(sc)
    assert paths.find(sc, paths.MOVING_CABLE).sea_settle == pytest.approx(paths.MOVING_SETTLE)
    r = animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    return sc, r["warnings"]


def _cable(sc):
    return paths.find(sc, paths.MOVING_CABLE)


def _bed(sc, p):
    """A world point in the seabed's coordinates (z: metres from the waterline)."""
    m = np.linalg.inv(np.array(paths_sea.bed(sc).matrix_world))
    return m[:3, :3] @ np.asarray(p, dtype=float) + m[:3, 3]


def _let_go(sc):
    return int(round(paths.MOVING_LET_GO * 25)) + 1


def test_settle_share_is_a_smooth_ramp():
    t = np.array([-1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 9.0])
    e = paths.settle_share(t, 4.0)
    assert e[0] == 0.0 and e[1] == 0.0 and e[-1] == 1.0 and e[-2] == 1.0
    assert np.all(np.diff(e) >= 0.0) and e[3] == pytest.approx(0.5)


def test_settle_lays_a_wheel_flat_and_its_ends_go_along():
    """A tilted gutter (axis 30° off vertical) with the cable's start on it: turned flat about its centre and lowered
    until its circle lies at the bottom; the start stays on the circle at every share."""
    c = np.array([2.0, 1.0, -10.0])
    n = np.array([math.sin(math.radians(30.0)), 0.0, math.cos(math.radians(30.0))])
    r = 3.0
    side = np.cross(n, [0.0, 1.0, 0.0])
    side /= np.linalg.norm(side)
    start = c + r * side
    wheel = np.concatenate([c, n])
    group = {"0": wheel, "a": start}
    share = np.linspace(0.0, 1.0, 11)
    w = paths.settle(wheel, group, -15.0, share)
    a = paths.settle(start, group, -15.0, share)
    assert np.allclose(w[0], wheel) and np.allclose(a[0], start)
    assert np.allclose(w[-1, 3:], [0.0, 0.0, 1.0], atol=1e-9) and w[-1, 2] == pytest.approx(-15.0)
    assert a[-1, 2] == pytest.approx(-15.0)                                  # the start lies on the seabed too
    for k in range(len(share)):                                              # … and on the wheel's circle all the way
        d = a[k] - w[k, :3]
        assert abs(float(d @ w[k, 3:])) < 1e-9 and float(np.linalg.norm(d)) == pytest.approx(r)
    # without a wheel an end sinks straight down
    alone = paths.settle(start, {"a": start}, -15.0, share)
    assert np.allclose(alone[:, :2], start[:2]) and alone[-1, 2] == pytest.approx(-15.0)


def test_what_is_let_go_sinks_onto_the_seabed_and_lies_there(built):
    sc, warnings = built
    assert not [t for t in warnings if paths.MOVING_CABLE in t], warnings        # (no "piles up" once it lies)
    it = _cable(sc)
    f0 = _let_go(sc)
    bottom = paths_sea.bottom_z(sc, it)
    settled = f0 + int(math.ceil(it.sea_settle * 25))
    zs = []
    for f in range(f0, sc.frame_end + 1, 5):
        sc.frame_set(f)
        line = paths.shape_now(sc, _cable(sc))
        zs.append(float(_bed(sc, line[0])[2]))
        if f >= settled:
            # the start and the turn round the sheave lie on the seabed: no point of the cable lower, none of the
            # first metres higher than its diameter
            bed = np.array([_bed(sc, p) for p in line])
            assert bed[:, 2].min() > bottom - 0.01, (f, bed[:, 2].min(), bottom)
            assert abs(bed[0, 2] - bottom) < 0.01
    assert zs[0] > bottom + 1.0                     # let go above the seabed …
    assert np.all(np.diff(zs) <= 1e-6)              # … it only goes down …
    assert zs[-1] == pytest.approx(bottom, abs=0.01)     # … and lies on it


def test_settle_zero_keeps_it_where_it_was(built):
    sc, _w = built
    it = _cable(sc)
    f0 = _let_go(sc)
    it.sea_settle = 0.0
    try:
        animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
        sc.frame_set(f0)
        p0 = _bed(sc, paths.shape_now(sc, _cable(sc))[0])
        sc.frame_set(sc.frame_end)
        p1 = _bed(sc, paths.shape_now(sc, _cable(sc))[0])
        assert np.linalg.norm(p1 - p0) < 1e-3
    finally:
        _cable(sc).sea_settle = paths.MOVING_SETTLE


def test_keep_tight_payout_has_no_step_where_the_hang_off_changes():
    """Task 0125: a keep-tight sea cable's free length jumps where it leaves the horn for the quadrant; its winch
    takes that up over ``paths.RAMP`` (here 25 frames) instead of in one frame. Before and after the ramp the payout
    is what keeping it tight needs; the trend through the change is kept."""
    F = 200
    trend = 0.01 * np.arange(F)
    hang = np.where(np.arange(F) < 80, 1, 0)
    v = trend + np.where(np.arange(F) < 80, 0.0, -2.5)          # 2.5 m less free length from frame 80 on
    out = paths.ramp_steps(v, hang, 25)
    steps = np.abs(np.diff(out))
    assert steps.max() < 0.2                                     # no jump: about 2.5 m / 25 frames x 1.5 at most
    assert np.allclose(out[:80], v[:80]) and np.allclose(out[105:], v[105:])
    assert np.all(np.diff(out[80:105]) <= 0.01 + 1e-12)          # it goes one way through the ramp
    same = paths.ramp_steps(trend, np.zeros(F, dtype=int), 25)   # no change of hang-off: nothing changes
    assert np.allclose(same, trend)
