"""Task 0125: a cable into the sea that is let go settles onto the seabed (``FRCable.sea_settle``, blender/paths.py
``settle``). The moving-part test model (tools/make_test_moving.py, ``paths.set_up_moving_model``): the block is
lowered near the seabed (15 m of water), the cable's start and its turn round the SHEAVE are let go at 9.2 s and the
block lifts 5 m again; in 2 s (the set-up's; 4 s is the default) what was let go sinks onto the seabed and lies there.
Blender as a module.
"""

import json
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


# --- task 0248: the cable on the seabed stays put, the freed stretch lies down in line -----------------------------

def _line(sc):
    return np.array([_bed(sc, p) for p in paths.shape_now(sc, _cable(sc))])


def _to_polyline(pts, line):
    """Each point's distance to the polyline ``line``."""
    a, b = line[:-1], line[1:]
    ab = b - a
    l2 = np.maximum((ab * ab).sum(1), 1e-30)
    out = np.empty(len(pts))
    for i, p in enumerate(pts):
        t = np.clip(((p - a) * ab).sum(1) / l2, 0.0, 1.0)
        out[i] = np.linalg.norm(a + ab * t[:, None] - p, axis=1).min()
    return out


def _from_end(line):
    """Each point's length along the cable from its end S (the last point)."""
    d = np.linalg.norm(np.diff(line[::-1], axis=0), axis=1)
    return np.concatenate([np.cumsum(d)[::-1], [0.0]])


def _length(line):
    return float(np.linalg.norm(np.diff(line, axis=0), axis=1).sum())


@pytest.fixture(scope="module")
def let_go_frames(built):
    """The cable at every frame from the let-go to the end (seabed coordinates), and its numbers at the let-go."""
    sc, _w = built
    animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])      # (as built: an earlier test changed it)
    f0 = _let_go(sc)
    lines = {}
    for f in range(f0, sc.frame_end + 1):
        sc.frame_set(f)
        lines[f] = _line(sc)
    sc.frame_set(f0)
    lay = json.loads(_cable(sc).get(paths.LAY, "{}"))[str(f0)]
    return sc, f0, lines, lay


def test_the_cable_on_the_seabed_stays_where_it_lay(let_go_frames):
    """Before 0248 the whole laid cable turned into a snake of 4 m waves (0.50 m sideways at the let-go's end)."""
    sc, f0, lines, lay = let_go_frames
    laid0 = lay[3]                                          # (metres from S that lay straight at the let-go)
    assert laid0 > 50.0
    p0 = lines[f0]
    kept = p0[_from_end(p0) <= laid0 - 0.01]
    assert np.abs(kept[:, 1]).max() < 1e-3                  # (the lay line is the seabed's x axis: straight on it)
    worst = max(float(_to_polyline(kept, line).max()) for line in lines.values())
    assert worst < 1e-3, worst
    lengths = [_length(line) for line in lines.values()]
    assert max(lengths) - min(lengths) < 1e-3


def test_the_freed_cable_lies_down_in_line(let_go_frames):
    """Settled, the cable that hung lies in line with the laid cable (no kink at the old touch-down), its extra length
    taken up by the end going forward along the lay line, the rest in one gentle bight not tighter than the cable's
    smallest bend (here none is set: 10 x its Ø)."""
    sc, f0, lines, lay = let_go_frames
    it = _cable(sc)
    aft = np.array(it.sea_dir, dtype=float)
    assert float(np.dot(lay[:3], aft)) < -1.0 and abs(float(np.cross(lay[:3], aft)[2])) < 1e-6   # (forward: −lay)
    end = lines[sc.frame_end]
    sc.frame_set(sc.frame_end)
    laid = paths_sea.numbers(sc, it)["laid"]               # (on the seabed now, from S to the touch-down)
    back = _from_end(end)
    on = back <= laid - 0.01                                # (the touch-down itself and the turn round the sheave,
    bed, bb = end[on][::-1], back[on][::-1]                 # which lies flat beside it, are the end's: left out)
    freed = bed[bb >= lay[3] - 1.0]                         # from a metre before the old touch-down on
    d = np.diff(freed[:, :2], axis=0)
    ln = np.linalg.norm(d, axis=1)
    d, ln = d[ln > 1e-6], ln[ln > 1e-6]
    ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.angle(np.exp(1j * np.diff(ang)))
    # in line where the old touch-down was (no kink there): the piece of the cable that passes it lies on the line
    j = int(np.searchsorted(bb, lay[3]))
    assert 0 < j < len(bb) and abs(bed[j - 1, 1]) < 1e-3 and abs(bed[j, 1]) < 1e-3
    assert np.abs(turn).max() < paths_sea.BIGHT_STEP * 1.2  # … nor anywhere (a point per 3° of the bight)
    # one bight: the line turns one way, back, and one way again (four arcs), never tighter than 10 x Ø
    k = np.abs(turn[:-1]) / np.maximum(0.5 * (ln[:-2] + ln[1:-1]), 1e-9)
    assert 1.0 / k.max() >= paths_sea.min_bend(it) * 0.99, (1.0 / k.max(), paths_sea.min_bend(it))
    side = freed[:, 1]
    assert (side <= 1e-6).all() or (side >= -1e-6).all()    # all to one side
    assert np.abs(side).max() < 3.0                         # a gentle bight, not a loop across the seabed


def test_the_let_go_settles_without_a_jump(let_go_frames):
    """From frame to frame during the settle the cable moves no further than its end does (the end goes down and
    forward together over Settles in, smoothstep: at most 1.5 x the even speed)."""
    sc, f0, lines, lay = let_go_frames
    it = _cable(sc)
    frames = sorted(lines)
    fps = sc.render.fps
    reach = math.hypot(math.hypot(lay[0], lay[1]), 15.0) * 1.5 / (it.sea_settle * fps)
    worst = 0.0
    for a, b in zip(frames, frames[1:]):
        worst = max(worst, float(_to_polyline(lines[b], lines[a]).max()), float(_to_polyline(lines[a], lines[b]).max()))
    assert worst < 2.0 * reach, (worst, reach)


def test_every_way_to_a_frame_gives_the_same_shape(let_go_frames, tmp_path):
    """Played in order, jumped to, solved again as Build solves it, posed live and after opening the saved project:
    the same cable after the let-go."""
    sc, f0, lines, lay = let_go_frames
    after = (f0 + 20, f0 + 45, sc.frame_end)
    sc.frame_set(sc.frame_start)
    for f in after:                                         # jumped to
        sc.frame_set(f)
        assert np.abs(_line(sc) - lines[f]).max() < 1e-4, f
    it = _cable(sc)
    slots = paths._inputs_of(it)[1]
    rel, first = paths._stored_places(sc, it, slots)
    for f in after:                                         # Build's one-moment solve, and the pose shown
        sc.frame_set(f)
        it = _cable(sc)
        for res in (paths._solve_item(sc, it, rel[f - first:f - first + 1], first=f),
                    paths._solve_item(sc, it, rel[f - first:f - first + 1])):
            want = paths._at(paths._world(it.part), res["points"][0])
            got = np.array(paths.shape_now(sc, it))
            # (a moment solved alone may spread its points otherwise: compared as lines, both ways)
            assert max(_to_polyline(got, want).max(), _to_polyline(want, got).max()) < 1e-3, f
    path = str(tmp_path / "settle.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    for f in after:                                         # after opening the project
        sc.frame_set(f)
        assert np.abs(_line(sc) - lines[f]).max() < 1e-4, f
