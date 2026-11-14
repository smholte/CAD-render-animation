"""Task 0082: independent tests of the three cable abilities – "Winch keeps it tight" (A1), the sea hang-off that
moves to the last contact the cable still bends round (A2) and "Let go" (A3) – written from the task's Design by an
agent that wrote none of the code and did not read the author's tests.

Expected values come from geometry worked out here (the lift wire of tools/make_test_moving.py as a tangent from a
point to a circle, with the carriers' places read from Blender's objects), from the test models' makers and from the
spec's own invariants (a cable kept tight keeps its CAD free length; a cable into the sea from a fixed start keeps its
length; a place let go stays put in the seabed's coordinates). Metres unless a name says otherwise.

Tests marked ``FAULT`` fail today on purpose: each documents a fault (or a question for the lead) found by this file.
"""

import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, paths_sea, spool, ui_paths  # noqa: E402

MOVING = os.path.join(HERE, "data", "test_moving.step")
SPOOL = os.path.join(HERE, "data", "test_spool.step")
PATHS_A = os.path.join(HERE, "data", "test_paths_a.step")
MM = 1e-3
WIRE, CABLE = "Lift wire", "Cable end"
LET_GO_FRAME = 231                      # 9.2 s at 25 fps + 1 (set_up_moving_model)

# tools/make_test_moving.py (mm): the lift wire in the plane y = 300
FAIRLEAD = np.array([13800.0, 300.0, 7750.0]) * MM
HEAD_C = np.array([8000.0, 300.0, 7600.0]) * MM
HEAD_R = 150.0 * MM
EYE = np.array([7850.0, 300.0, 5250.0]) * MM
SHEAVE_C = np.array([8000.0, 0.0, 4300.0]) * MM
SHEAVE_R = 500.0 * MM
CLAMP = np.array([6800.0, 0.0, 4800.0]) * MM
DECK = (np.array([0.0, -3000.0, -2000.0]) * MM, np.array([14000.0, 3000.0, 2500.0]) * MM)
CABLE_R = 60.0 * MM


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("paths_moving_independent"))


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def load(folder, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    paths_sea.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="normal") == {"FINISHED"}
    return sc


def part(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def mat(ob):
    return np.array(ob.matrix_world, dtype=float)


def at(m, p):
    return m[:3, :3] @ np.asarray(p, dtype=float) + m[:3, 3]


class Moving:
    """The moving-part test model, set up; the CAD world matrices of the parts the tests follow."""

    def __init__(self, folder, with_let_go=True):
        self.sc = load(folder, MOVING)
        self.made = paths.set_up_moving_model(self.sc, with_let_go=with_let_go)
        update()
        self.cad = {n: mat(part(self.sc, n)) for n in ("HEAD SHEAVE", "BLOCK", "SHEAVE", "CLAMP", "HORN")}

    def delta(self, name):
        """How far the part has moved from its CAD place (world)."""
        return mat(part(self.sc, name)) @ np.linalg.inv(self.cad[name])

    def anim(self):
        return self.sc.fresing.animations[self.made["animation"]]


def bake(sc, anim):
    res = animation.bake(sc, anim)
    return res["warnings"] if isinstance(res, dict) else list(res)


def show(sc, frame):
    sc.frame_set(frame)
    update()


def wire_free_mine(m: Moving) -> float:
    """My lift wire's free length: the straight from the fairlead to the head sheave's top (the start is at the
    sheave's top height and the trolley only travels), a turn round the sheave's aft side, the tangent down to the
    eye – all in the plane y = 0.3."""
    c = at(m.delta("HEAD SHEAVE"), HEAD_C)
    e = at(m.delta("BLOCK"), EYE)
    s = FAIRLEAD
    assert abs(s[2] - (c[2] + HEAD_R)) < 5e-5 and abs(c[1] - 0.3) < 5e-5 and abs(e[1] - 0.3) < 5e-5   # (float32)
    first = s[0] - c[0]
    d = np.array([e[0] - c[0], e[2] - c[2]])
    D = float(np.linalg.norm(d))
    best = None
    for sgn in (1.0, -1.0):
        alpha = math.atan2(d[1], d[0]) + sgn * math.acos(HEAD_R / D)
        t = np.array([-math.sin(alpha), math.cos(alpha)])          # going round counter-clockwise (x right, z up)
        tp = np.array([math.cos(alpha), math.sin(alpha)]) * HEAD_R
        if (d - tp) @ t > 0:
            best = alpha
    assert best is not None
    arc = HEAD_R * ((best - math.pi / 2) % (2 * math.pi))
    return first + arc + math.sqrt(D * D - HEAD_R * HEAD_R)


def drawn(sc, name):
    """(world points, metres along) of the cable at the frame shown."""
    it = paths.find(sc, name)
    return np.asarray(paths.shape_now(sc, it), dtype=float), np.asarray(paths.lengths_now(sc, it), dtype=float)


def speed_value(sc, name):
    it = paths.find(sc, name)
    return joints.get_value(joints.find(sc, it.joint))


def pose(m, travel=0.0, tilt_deg=0.0, lower=0.0):
    for n, v in (("Travel", travel), ("Tilt", math.radians(tilt_deg)), ("Lower", lower)):
        joints.set_value(joints.find(m.sc, n), v)
    update()
    paths.refresh(m.sc)
    update()


def bed_m(sc):
    return mat(paths_sea.bed(sc))


def key_count(sc, name):
    j = joints.find(sc, paths.find(sc, name).joint)
    ad = j.motion.animation_data
    if ad is None or ad.action is None:
        return 0, j
    n = 0
    for fc in paths._fcurves(j.motion):
        if fc.data_path == joints.COUPLING_PATH:
            n += len(fc.keyframe_points)
    return n, j


# =====================================================================================================================
# A1  Winch keeps it tight
# =====================================================================================================================

@pytest.fixture()
def moving(folder):
    return Moving(folder)


@pytest.fixture()
def plain(folder):
    return Moving(folder, with_let_go=False)


def test_cad_free_length_of_the_wire_is_the_makers(plain):
    m = plain
    w = paths.find(m.sc, WIRE)
    mine = wire_free_mine(m)
    assert abs(mine - (5.8 + math.pi / 2 * HEAD_R + 2.35)) < 1e-9
    assert abs(paths.free_length(m.sc, w, cad=True) - mine) < 0.5 * MM
    assert abs(paths.free_length(m.sc, w) - mine) < 0.5 * MM
    assert abs(paths.tight_payout(m.sc, w)) < 0.5 * MM


@pytest.mark.parametrize("travel,tilt,lower", [(3.0, 0.0, 0.0), (10.5, 0.0, 0.0), (10.5, 30.0, 0.0),
                                               (10.5, 30.0, 9.0), (6.0, 15.0, 4.0), (0.0, 40.0, 12.0)])
def test_live_payout_keeps_my_free_length(plain, travel, tilt, lower):
    """Live (no Build): the speed joint goes where the free length is the CAD one; the drawn wire agrees."""
    m = plain
    L0 = wire_free_mine(m)
    pose(m, travel, tilt, lower)
    w = paths.find(m.sc, WIRE)
    mine = wire_free_mine(m)
    pay = mine - L0
    assert abs(paths.free_length(m.sc, w) - mine) < 1 * MM, (paths.free_length(m.sc, w), mine)
    assert abs(paths.tight_payout(m.sc, w) - pay) < 1 * MM, (paths.tight_payout(m.sc, w), pay)
    assert abs(speed_value(m.sc, WIRE) - pay) < 1 * MM
    pts, s = drawn(m.sc, WIRE)
    assert np.isfinite(pts).all() and len(pts) > 2
    ends = sorted([pts[0], pts[-1]], key=lambda p: -p[0])               # (drawn from either end)
    assert float(np.linalg.norm(ends[0] - FAIRLEAD)) < 2 * MM
    assert float(np.linalg.norm(ends[1] - at(m.delta("BLOCK"), EYE))) < 2 * MM
    poly = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    assert abs(poly - mine) < 2 * MM, (poly, mine)            # (chords round the sheave are a hair short)


def test_build_keys_the_payout_at_every_frame(plain):
    """Build: one key per frame on the wire's speed; at every frame the payout is my free length - CAD's."""
    m = plain
    sc = m.sc
    L0 = wire_free_mine(m)
    warns = bake(sc, m.anim())
    assert not [w for w in warns if WIRE in w], warns
    first, last = sc.frame_start, sc.frame_end
    n, j = key_count(sc, WIRE)
    assert n == last - first + 1, (n, first, last)
    assert j.motion.get(paths.TIGHT) == paths.find(sc, WIRE).name
    worst, worst_len = 0.0, 0.0
    for f in range(first, last + 1, 3):
        show(sc, f)
        mine = wire_free_mine(m)
        worst = max(worst, abs(speed_value(sc, WIRE) - (mine - L0)))
        pts, _s = drawn(sc, WIRE)
        worst_len = max(worst_len, abs(float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) - mine))
    assert worst < 1 * MM, worst
    assert worst_len < 2 * MM, worst_len


def test_build_twice_then_clear_keys_leaves_nothing_behind(plain):
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    n1, _ = key_count(sc, WIRE)
    show(sc, 200)
    v1 = speed_value(sc, WIRE)
    bake(sc, m.anim())
    n2, j = key_count(sc, WIRE)
    show(sc, 200)
    assert n1 == n2 == sc.frame_end - sc.frame_start + 1
    assert abs(speed_value(sc, WIRE) - v1) < 1e-6
    animation.clear_keys(sc)
    update()
    paths.refresh(sc)
    n3, j = key_count(sc, WIRE)
    assert n3 == 0
    assert paths.TIGHT not in j.motion
    # the pose before Build (CAD) is back, and the winch has wound the wire back to its CAD length
    assert abs(joints.get_value(joints.find(sc, "Travel"))) < 1e-9
    assert abs(speed_value(sc, WIRE)) < 1 * MM, speed_value(sc, WIRE)


def test_switching_keep_tight_off_takes_the_build_off_and_the_next_build_keys_nothing(plain):
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    assert sc.fresing.anim_baked
    paths.set_keep_tight(sc, paths.find(sc, WIRE), False)
    assert not sc.fresing.anim_baked                    # "A built animation is taken off first"
    n, j = key_count(sc, WIRE)
    assert n == 0 and paths.TIGHT not in j.motion
    bake(sc, m.anim())
    n, j = key_count(sc, WIRE)
    assert n == 0
    vals = []
    for f in (1, 100, 200, 289):
        show(sc, f)
        vals.append(speed_value(sc, WIRE))
    assert max(vals) - min(vals) < 1e-9, vals          # no stale winch keys: the speed stands still
    assert abs(paths.tight_payout(sc, paths.find(sc, WIRE))) == 0.0


def test_a_step_that_moves_the_speed_wins_after_an_earlier_tight_build(plain):
    """A Build with keep tight writes the winch's keys and its tag; a Run motor step on the speed joint added later
    must win (with a warning), not be overwritten because the old tag is still there."""
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    a = m.anim()
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", paths.find(sc, WIRE).joint, 0.0, 4.0, "LINEAR"
    b.speed_mmin = 30.0                                 # 2 m in 4 s
    warns = bake(sc, a)
    assert any(WIRE in w and "tight" in w for w in warns), warns
    show(sc, 101)                                       # 4 s
    assert abs(abs(speed_value(sc, WIRE)) - 2.0) < 0.01, speed_value(sc, WIRE)
    show(sc, 289)
    assert abs(abs(speed_value(sc, WIRE)) - 2.0) < 0.01, speed_value(sc, WIRE)


def test_settings_land_on_the_right_cable_when_there_are_several(plain):
    """Names, not stale collection items: keep tight and let go on one cable never touch the other."""
    m = plain
    sc = m.sc
    w = paths.find(sc, WIRE)
    paths.add_cable(sc, "Extra")                        # (the collection grows: references held before go stale)
    paths.set_keep_tight(sc, paths.find(sc, WIRE), False)
    assert not paths.find(sc, WIRE).keep_tight and not paths.find(sc, CABLE).keep_tight
    paths.let_go(sc, paths.find(sc, CABLE), "a", 50)
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == 50
    assert paths.let_go_frame(paths.find(sc, WIRE), "a") == -1
    paths.let_go(sc, paths.find(sc, WIRE), "b", 60)
    assert paths.let_go_frame(paths.find(sc, WIRE), "b") == 60
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == 50
    paths.hold(sc, paths.find(sc, CABLE), "a")
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == -1
    assert paths.let_go_frame(paths.find(sc, WIRE), "b") == 60
    del w


# =====================================================================================================================
# A2  the hang-off moves to the last contact the cable still bends round
# =====================================================================================================================

def test_sea_cable_keeps_its_length_and_points_at_every_frame(plain):
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    counts, total, poly = set(), [], []
    for f in range(sc.frame_start, sc.frame_end + 1, 2):
        show(sc, f)
        pts, s = drawn(sc, CABLE)
        assert np.isfinite(pts).all() and np.isfinite(s).all(), f
        counts.add(len(pts))
        total.append(s[-1] - s[0])
        poly.append(float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()))
    assert len(counts) == 1, counts
    total, poly = np.array(total), np.array(poly)
    assert float(total.max() - total.min()) < 1 * MM, (total.min(), total.max())
    # the drawn points really are that long (chords on arcs and the catenary are a little short)
    assert float(np.abs(poly - total).max()) < 0.01, float(np.abs(poly - total).max())
    assert float(poly.max() - poly.min()) < 0.01, (poly.min(), poly.max())


def test_hang_off_moves_from_the_horn_to_the_sheave_once(plain):
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    names, lefts = {}, {}
    for f in range(sc.frame_start, sc.frame_end + 1):
        show(sc, f)
        n = paths_sea.numbers(sc, paths.find(sc, CABLE))
        names[f] = n["hang_off"]
        lefts[f] = (n.get("left"), n.get("left_frame"))
    assert names[sc.frame_start] == "HORN" and names[sc.frame_end] == "SHEAVE", (names[1], names[289])
    switch = [f for f in range(sc.frame_start + 1, sc.frame_end + 1) if names[f] != names[f - 1]]
    assert len(switch) == 1, switch                     # once released, released for good
    f0 = switch[0]
    assert all(lefts[f] == (None, None) for f in range(sc.frame_start, f0))
    assert all(lefts[f] == ("HORN", f0) for f in range(f0, sc.frame_end + 1)), lefts[sc.frame_end]
    # it is released where the sheave's hanging point has gone aft of the horn's (or the cable lifts off it)
    show(sc, f0)
    sheave_x = at(m.delta("SHEAVE"), SHEAVE_C)[0] - SHEAVE_R
    assert sheave_x < -1.5 + 0.05, sheave_x            # the horn's vertical at x = -1.5 m
    show(sc, f0 - 1)
    pts, _s = drawn(sc, CABLE)
    assert np.isfinite(pts).all()


def test_live_pose_agrees_with_the_built_frame(plain):
    """The shape at a built frame and the live solve of the same pose at the same frame (seabed in the same
    place) are the same cable."""
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    frames = (60, 140, 200, 240)               # (289: see test_FAULT_live_hang_off_arc_is_drawn_as_a_chord)
    built, values, hang = {}, {}, {}
    for f in frames:
        show(sc, f)
        built[f] = drawn(sc, CABLE)[0]
        values[f] = {n: joints.get_value(joints.find(sc, n)) for n in ("Travel", "Tilt", "Lower")}
        hang[f] = paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"]
    animation.clear_keys(sc)
    worst = {}
    for f in frames:
        show(sc, f)
        for n, v in values[f].items():
            joints.set_value(joints.find(sc, n), v)
        update()
        paths.refresh(sc, force=True)
        update()
        live = drawn(sc, CABLE)[0]
        # (a Build has one point layout for all its frames, the pose shown its own: compare the curves)
        worst[f] = max(off_curve(live, built[f]), off_curve(built[f], live))
        assert paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"] == hang[f], f
    assert max(worst.values()) < 5 * MM, worst


def off_curve(pts, curve) -> float:
    """The farthest any of ``pts`` lies from the polyline ``curve``."""
    a, b = curve[:-1], curve[1:]
    ab = b - a
    ll = np.maximum((ab * ab).sum(1), 1e-18)
    worst = 0.0
    for p in pts:
        t = np.clip(((p - a) * ab).sum(1) / ll, 0.0, 1.0)
        worst = max(worst, float(np.linalg.norm(a + t[:, None] * ab - p, axis=1).min()))
    return worst


def dense(pts, n=20):
    t = np.linspace(0.0, 1.0, n, endpoint=False)
    out = (pts[:-1, None, :] + (pts[1:] - pts[:-1])[:, None, :] * t[None, :, None]).reshape(-1, 3)
    return np.vstack([out, pts[-1:]])


def inside_sheave(m, pts) -> float:
    """How far the drawn cable's middle cuts inside the SHEAVE's rope circle (m; 0 when it does not), along every
    drawn segment, near the sheave."""
    d = m.delta("SHEAVE")
    c, ax = at(d, SHEAVE_C), d[:3, :3] @ np.array([0.0, 1.0, 0.0])
    q = dense(pts) - c
    along = q @ ax
    r = np.linalg.norm(q - along[:, None] * ax, axis=1)
    near = np.abs(along) < 0.05
    return float(max(0.0, SHEAVE_R - r[near].min())) if near.any() else 0.0


def test_FAULT_live_hang_off_arc_is_drawn_as_a_chord(plain):
    """FAULT: the pose shown (no Build) hanging from the SHEAVE after the HORN was released (travel 10.5 m aft,
    tilt 30°, lowered 4 m: frame 289's pose) draws the cable's ~107° round the sheave with two points – a chord
    that cuts ~0.2 m into the sheave. A Build of the same frame draws the arc round it. The arc on the wheel it
    hangs from keeps the point count of the wheel's wrap in the CAD pose (a few degrees)."""
    m = plain
    sc = m.sc
    bake(sc, m.anim())
    show(sc, 289)
    built = inside_sheave(m, drawn(sc, CABLE)[0])
    assert built < 2 * MM, built
    animation.clear_keys(sc)
    show(sc, 289)
    pose(m, 10.5, 30.0, 4.0)
    assert paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"] == "SHEAVE"
    live = inside_sheave(m, drawn(sc, CABLE)[0])
    assert live < 2 * MM, f"live, the drawn cable cuts {live * 1000:.0f} mm into the sheave it hangs from"


def inside_deck(pts, margin=0.02):
    lo, hi = DECK
    return ((pts > lo + margin) & (pts < hi - margin)).all(axis=1)


def test_FAULT_a_motion_that_comes_back_hangs_the_cable_through_the_deck(plain):
    """FAULT (or a question for the lead): the spec keeps a released wheel released "for the later frames". A motion
    that brings the quadrant back over the horn (travel aft, tilt, lower, then all back) then hangs the cable from
    the sheave straight down through the deck at the end, where everything stands in its CAD place; the live pose of
    that same frame hangs it from the horn. Expected here: the built cable never passes through the deck, and the
    last frame (the CAD pose) is the live one."""
    m = plain
    sc = m.sc
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "There and back", 0.0, "25"
    for jname, start, dur, to in (("Travel", 0.0, 4.0, 10.5), ("Tilt", 4.0, 1.0, math.radians(30.0)),
                                  ("Lower", 5.0, 3.0, 6.0), ("Lower", 8.0, 2.0, 0.0),
                                  ("Tilt", 10.0, 1.0, 0.0), ("Travel", 11.0, 4.0, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", jname, start, dur, "SMOOTH"
        b.use_from = True
        if jname == "Tilt":
            b.to_angle = to
        else:
            b.to_dist = to
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    bake(sc, a)
    last = sc.frame_end
    show(sc, last)
    assert abs(joints.get_value(joints.find(sc, "Travel"))) < 1e-6
    built_hang = paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"]
    pts_end = drawn(sc, CABLE)[0]
    through = []
    for f in range(sc.frame_start, last + 1, 5):
        show(sc, f)
        if inside_deck(drawn(sc, CABLE)[0]).any():
            through.append(f)
    animation.clear_keys(sc)
    show(sc, last)
    paths.refresh(sc, force=True)
    update()
    live_hang = paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"]
    live = drawn(sc, CABLE)[0]
    gap = float(np.linalg.norm(live - pts_end, axis=1).max()) if live.shape == pts_end.shape else float("inf")
    assert not through and built_hang == live_hang == "HORN" and gap < 0.01, \
        (f"frames with the cable inside the deck: {through[:3]}…{through[-3:]} ({len(through)}); "
         f"last frame hangs from {built_hang!r} built, {live_hang!r} live; shapes {gap:.2f} m apart")


# =====================================================================================================================
# A3  Let go
# =====================================================================================================================

# FROZEN: a start let go at frame 0 or 1 is carried aft with the seabed at 3 kn faster than the block travels; at frame
# 207 it has passed the sheave and the app reports "cannot go round 'SHEAVE' at frame 207" and shows the last shape.
# That is the app being honest about an impossible set-up, so these tests look at frames 1 … 200 only.

def start_in_bed(sc):
    pts, _s = drawn(sc, CABLE)
    return at(np.linalg.inv(bed_m(sc)), pts[0])


def test_let_go_start_stays_on_the_seabed_and_follows_the_clamp_before(moving):
    """The model's own let-go (start + SHEAVE at frame 231): before it the start is on the clamp; from it on it is
    fixed in the seabed's coordinates (it passes aft with the seabed) – whatever the block does next."""
    m = moving
    sc = m.sc
    bake(sc, m.anim())
    before, after = 0.0, []
    for f in range(sc.frame_start, sc.frame_end + 1):
        show(sc, f)
        if f < LET_GO_FRAME:
            before = max(before, float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))))
        else:
            after.append(start_in_bed(sc))
    assert before < 1 * MM, before
    after = np.array(after)
    spread = float(np.linalg.norm(after - after[0], axis=1).max())
    assert spread < 1 * MM, spread
    # it is where the clamp was at that frame
    show(sc, LET_GO_FRAME)
    assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) < 1 * MM
    # and the block lifts 5 m away from it afterwards: the clamp is far from the start at the end
    show(sc, sc.frame_end)
    assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) > 3.0


def test_let_go_sheave_stays_on_the_seabed(moving):
    """The cable keeps going round the sheave's place at frame 231 (moving with the seabed), not round the sheave
    the block lifts away."""
    m = moving
    sc = m.sc
    bake(sc, m.anim())
    show(sc, LET_GO_FRAME)
    b0 = bed_m(sc)
    c0 = at(m.delta("SHEAVE"), SHEAVE_C)
    ax0 = m.delta("SHEAVE")[:3, :3] @ np.array([0.0, 1.0, 0.0])
    held_c, held_a = at(np.linalg.inv(b0), c0), np.linalg.inv(b0)[:3, :3] @ ax0
    for f in range(LET_GO_FRAME, sc.frame_end + 1, 4):
        show(sc, f)
        bm = bed_m(sc)
        c, a = at(bm, held_c), bm[:3, :3] @ held_a
        pts = drawn(sc, CABLE)[0]
        rel = pts - c
        along = rel @ a
        r = np.linalg.norm(rel - along[:, None] * a, axis=1)
        on = (np.abs(r - SHEAVE_R) < 2 * MM) & (np.abs(along) < 2 * MM)
        assert on.sum() >= 3, (f, int(on.sum()), float(np.abs(r - SHEAVE_R).min()))
    show(sc, sc.frame_end)
    real = at(m.delta("SHEAVE"), SHEAVE_C)
    pts = drawn(sc, CABLE)[0]
    d = np.linalg.norm(pts - real, axis=1)
    assert (np.abs(d - SHEAVE_R) > 0.5).all() or d.min() > SHEAVE_R + 0.5


def test_FAULT_let_go_at_frame_0_before_the_animation_starts_lets_go_from_its_first_frame(plain):
    """FAULT: let go at frame 0 (shown frame 1, not built) – "from that frame on" includes the whole animation, so
    the start must stay put in seabed coordinates from the first frame. Today nothing is stored for a frame before
    the frames Build reads, and the start silently stays on its clamp at every frame."""
    m = plain
    sc = m.sc
    show(sc, 1)
    paths.let_go(sc, paths.find(sc, CABLE), "a", 0)
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == 0
    bake(sc, m.anim())
    got = []
    for f in (1, 60, 120, 200):                         # (see FROZEN)
        show(sc, f)
        got.append(start_in_bed(sc))
    got = np.array(got)
    spread = float(np.linalg.norm(got - got[0], axis=1).max())
    on_clamp = float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP)))
    assert spread < 1 * MM, (f"the start let go at frame 0 moved {spread:.2f} m in the seabed's coordinates; at "
                             f"frame 200 it is {on_clamp * 1000:.1f} mm from its clamp")


def test_let_go_on_the_first_frame_and_after_the_last(plain):
    m = plain
    sc = m.sc
    show(sc, 1)
    paths.let_go(sc, paths.find(sc, CABLE), "a", sc.frame_start)       # the shown frame: read now
    bake(sc, m.anim())
    got = []
    for f in (1, 60, 120, 200):                         # (see FROZEN)
        show(sc, f)
        got.append(start_in_bed(sc))
    assert float(np.linalg.norm(np.array(got) - got[0], axis=1).max()) < 1 * MM
    # after the last frame: nothing changes along the animation
    paths.let_go(sc, paths.find(sc, CABLE), "a", 10_000)
    bake(sc, m.anim())
    for f in (1, 150, 289):
        show(sc, f)
        assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) < 1 * MM, f


def test_changing_the_frame_and_holding_again(moving):
    m = moving
    sc = m.sc
    bake(sc, m.anim())
    paths.let_go(sc, paths.find(sc, CABLE), "a", 150)
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == 150
    bake(sc, m.anim())
    got = []
    for f in range(150, 290, 10):
        show(sc, f)
        got.append(start_in_bed(sc))
    assert float(np.linalg.norm(np.array(got) - got[0], axis=1).max()) < 1 * MM
    show(sc, 149)
    assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) < 1 * MM
    # hold again: on its clamp at every frame
    paths.hold(sc, paths.find(sc, CABLE), "a")
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == -1
    bake(sc, m.anim())
    for f in (1, 150, 240, 289):
        show(sc, f)
        assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) < 1 * MM, f


def test_live_let_go_at_the_frame_shown_keeps_the_place(plain):
    """Not built: let go the start at the frame shown, then move the block – the start stays (it stays in seabed
    coordinates, and the seabed does not move while the frame stays)."""
    m = plain
    sc = m.sc
    show(sc, 120)
    pose(m, 10.5, 30.0, 4.0)
    p0 = drawn(sc, CABLE)[0][0].copy()
    assert float(np.linalg.norm(p0 - at(m.delta("CLAMP"), CLAMP))) < 1 * MM
    paths.let_go(sc, paths.find(sc, CABLE), "a")
    assert paths.let_go_frame(paths.find(sc, CABLE), "a") == 120
    pose(m, 10.5, 30.0, 0.0)
    p1 = drawn(sc, CABLE)[0][0]
    assert float(np.linalg.norm(p1 - p0)) < 1 * MM, float(np.linalg.norm(p1 - p0))
    # before the frame let go it is on the clamp again
    show(sc, 100)
    paths.refresh(sc, force=True)
    update()
    assert float(np.linalg.norm(drawn(sc, CABLE)[0][0] - at(m.delta("CLAMP"), CLAMP))) < 1 * MM


def test_wire_eye_end_let_go_stops_the_winch_and_stays_in_the_cable_parts_place(plain):
    """A1 + A3 on a cable that is not into the sea: the lift wire's end (on the eye) let go at frame 150, while
    the block is being lowered (5 … 9 s). From then on the end stays where it was (the cable part stands still: so
    in the world) and, the head sheave standing still too, the winch pays out nothing more."""
    m = plain
    sc = m.sc
    pts = drawn(sc, WIRE)[0]                            # (which end is on the eye: the CAD reading decides)
    which = "a" if np.linalg.norm(pts[0] - EYE) < np.linalg.norm(pts[-1] - EYE) else "b"
    paths.let_go(sc, paths.find(sc, WIRE), which, 150)
    bake(sc, m.anim())
    ends, pays = [], []
    for f in range(150, sc.frame_end + 1, 7):
        show(sc, f)
        pts = drawn(sc, WIRE)[0]
        ends.append(min((pts[0], pts[-1]), key=lambda p: p[0]))       # (the eye's end is the aft one)
        pays.append(speed_value(sc, WIRE))
    ends = np.array(ends)
    assert float(np.linalg.norm(ends - ends[0], axis=1).max()) < 1 * MM
    show(sc, 150)
    assert float(np.linalg.norm(ends[0] - at(m.delta("BLOCK"), EYE))) < 1 * MM
    assert max(pays) - min(pays) < 1 * MM, (min(pays), max(pays))
    show(sc, sc.frame_end)
    assert float(np.linalg.norm(at(m.delta("BLOCK"), EYE) - ends[0])) > 1.0       # the eye went on without it


def test_save_and_reopen_keeps_let_go_and_keep_tight(moving, tmp_path):
    m = moving
    sc = m.sc
    bake(sc, m.anim())
    show(sc, 260)
    before = drawn(sc, CABLE)[0].copy()
    hang = paths_sea.numbers(sc, paths.find(sc, CABLE))["hang_off"]
    wire_v = speed_value(sc, WIRE)
    path = str(tmp_path / "moving.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    show(sc, 260)
    it = paths.find(sc, CABLE)
    assert paths.let_go_frame(it, "a") == LET_GO_FRAME
    assert paths.find(sc, WIRE).keep_tight
    after = drawn(sc, CABLE)[0]
    assert after.shape == before.shape
    assert float(np.linalg.norm(after - before, axis=1).max()) < 1 * MM
    assert paths_sea.numbers(sc, it)["hang_off"] == hang
    assert abs(speed_value(sc, WIRE) - wire_v) < 1e-6
    # Build again after reopening: the same cable
    bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    show(sc, 260)
    again = drawn(sc, CABLE)[0]
    assert float(np.linalg.norm(again - before, axis=1).max()) < 1 * MM


# =====================================================================================================================
# refusals, in plain words
# =====================================================================================================================

def test_refusals_on_the_moving_model(plain):
    sc = plain.sc
    it = paths.find(sc, CABLE)
    with pytest.raises(paths.PathError, match="(?i)sea"):
        paths.let_go(sc, it, "b", 10)
    with pytest.raises(paths.PathError, match="(?i)no contact number 9"):
        paths.let_go(sc, paths.find(sc, CABLE), "8", 10)
    with pytest.raises(paths.PathError, match="(?i)no end or contact"):
        paths.let_go(sc, paths.find(sc, CABLE), "middle", 10)
    assert paths.let_go_frame(paths.find(sc, CABLE), "b") == -1
    paths.hold(sc, paths.find(sc, CABLE), "a")          # holding what is held: nothing happens, no error


def test_refusals_spool_start_and_roller(folder):
    sc = load(folder, SPOOL)
    spool.set_up_test_model(sc)
    update()
    with pytest.raises(paths.PathError, match="(?i)drum or carousel"):
        paths.let_go(sc, paths.find(sc, "Wire"), "a", 10)
    assert paths.let_go_frame(paths.find(sc, "Wire"), "a") == -1
    sc = load(folder, PATHS_A)
    paths.set_up_test_model(sc)
    update()
    it = paths.find(sc, "Wire rope")
    rollers = [i for i, c in enumerate(it.contacts) if c.kind == "ROLLER"]
    assert rollers
    with pytest.raises(paths.PathError, match="(?i)roller"):
        paths.let_go(sc, it, str(rollers[0]), 10)
    # keep tight while a Run motor step moves the speed: said at Build, and the motor's keys stay
    notes = paths.set_keep_tight(sc, paths.find(sc, "Wire rope"), True)
    assert isinstance(notes, list)
    warns = bake(sc, sc.fresing.animations[paths.TEST_ANIMATION])
    assert any("Wire rope" in w and "step" in w for w in warns), warns
    sc.frame_set(sc.frame_end)
    update()
    v = abs(speed_value(sc, "Wire rope"))
    assert abs(v - 1.0) < 0.01, v                      # 10 m/min for 6 s


def test_keep_tight_on_a_following_speed_joint_is_refused(plain):
    sc = plain.sc
    w = paths.find(sc, WIRE)
    j = joints.find(sc, w.joint)
    jname = j.name
    joints.set_follows(sc, j, "Travel", 1.0)
    notes = paths.set_keep_tight(sc, paths.find(sc, WIRE), True)
    assert any("follows" in n and jname in n for n in notes), notes


# =====================================================================================================================
# a spool cable kept tight over a long motion
# =====================================================================================================================

def spool_scene(folder):
    """The spool model's wire with its end (on the WEIGHT) moved by a joint of mine, "Weight down": lowered 15 m
    (0 … 8 s) and raised 5 m (8 … 11 s); the winch keeps it tight. Not built."""
    sc = load(folder, SPOOL)
    spool.set_up_test_model(sc)
    update()
    weight = part(sc, "WEIGHT")
    joints.create(sc, "SLIDE", [weight], weight.matrix_world.translation.copy(), Vector((0.0, 0.0, -1.0)),
                  name="Weight down")
    joints.find(sc, "Weight down").use_limits = False
    update()
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    while len(a.blocks):
        a.blocks.remove(0)
    for start, dur, to in ((0.0, 8.0, 15.0), (8.0, 3.0, 10.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Weight down", start, dur, "SMOOTH"
        b.use_from = True
        b.to_dist = to
    notes = paths.set_keep_tight(sc, paths.find(sc, "Wire"), True)
    assert not notes, notes
    return sc, a


def spool_rows(sc, step=6):
    """Per frame: (frame, payout, drum turn, level wind, drawn free span, the app's free length)."""
    drum_j = joints.find(sc, spool.find(sc, "Drum").joint)
    rows = []
    for f in range(sc.frame_start, sc.frame_end + 1, step):
        show(sc, f)
        pts, _s = drawn(sc, "Wire")
        rows.append((f, speed_value(sc, "Wire"), joints.get_value(drum_j),
                     joints.get_value(joints.find(sc, "Level wind")),
                     float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()),
                     paths.free_length(sc, paths.find(sc, "Wire"))))
    return np.array(rows)


def test_spool_wire_kept_tight_turns_the_drum_by_its_table(folder):
    """Over 15 m: the drum and the level wind stand where the same payout puts them with nothing animated."""
    sc, a = spool_scene(folder)
    L0 = paths.free_length(sc, paths.find(sc, "Wire"), cad=True)
    assert abs(L0 - (800.0 + math.pi / 2 * 100.0 + 344.641) * MM) < 2 * MM, L0      # tools/make_test_spool.py
    warns = bake(sc, a)
    assert not [w for w in warns if "Wire" in w], warns
    rows = spool_rows(sc)
    assert rows[:, 1].max() > 14.0, rows[:, 1].max()   # it really paid out about 15 m (and went over a layer)
    assert (np.diff(rows[:, 2]) * np.diff(rows[:, 1]) >= -1e-9).all()      # the drum turns the way the wire pays
    paths.set_keep_tight(sc, paths.find(sc, "Wire"), False)      # (takes the Build off; the winch lets go of it)
    assert not sc.fresing.anim_baked
    drum_j = joints.find(sc, spool.find(sc, "Drum").joint)
    worst_drum, worst_lw = 0.0, 0.0
    for _f, pay, drum, lw, _free, _app in rows[::3]:
        joints.set_value(joints.find(sc, paths.find(sc, "Wire").joint), pay, use_limits=False)
        update()
        worst_drum = max(worst_drum, abs(joints.get_value(drum_j) - drum))
        worst_lw = max(worst_lw, abs(joints.get_value(joints.find(sc, "Level wind")) - lw))
    assert worst_drum < 1e-4, worst_drum
    assert worst_lw < 0.1 * MM, worst_lw


def test_FAULT_spool_wire_kept_tight_is_off_by_the_level_winds_fleet(folder):
    """FAULT: "pay = L_free(now) - L_free(CAD)" to 0.5 mm (A1). With the spool model's level wind (a layer follower
    that moves the fairlead sheave along the drum) the Build's payout is worked out with the sheave where it was
    before the payout moved it; the places are then read again but the payout is not worked out again. Measured on
    the web machine: free span - payout - CAD free span up to ~18 mm (frame 141, level wind 0.18 m off centre) – the
    extra of sqrt(0.8**2 + dy**2) - 0.8 over the 0.8 m run to the sheave. The app's own free_length agrees with
    the drawn span, so it is the payout that is off."""
    sc, a = spool_scene(folder)
    L0 = paths.free_length(sc, paths.find(sc, "Wire"), cad=True)
    bake(sc, a)
    rows = spool_rows(sc)
    assert float(np.abs(rows[:, 4] - rows[:, 5]).max()) < 3 * MM      # the app measures what it draws
    off = rows[:, 5] - rows[:, 1] - L0
    k = int(np.argmax(np.abs(off)))
    assert abs(off[k]) < 1 * MM, (f"frame {int(rows[k, 0])}: free {rows[k, 5]:.4f} m - payout {rows[k, 1]:.4f} m - "
                                  f"CAD {L0:.4f} m = {off[k] * 1000:.1f} mm (level wind {rows[k, 3] * 1000:.0f} mm)")


def test_spool_wire_kept_tight_live_settles(folder):
    """The same, live (no Build): the weight lowered 12 m by hand; after the updates settle the payout must be the
    free length's growth to 0.5 mm."""
    sc, _a = spool_scene(folder)
    L0 = paths.free_length(sc, paths.find(sc, "Wire"), cad=True)
    joints.set_value(joints.find(sc, "Weight down"), 12.0, use_limits=False)
    for _ in range(4):
        update()
        paths.refresh(sc)
    update()
    pay = speed_value(sc, "Wire")
    free = paths.free_length(sc, paths.find(sc, "Wire"))
    assert pay > 11.0, pay
    assert abs(free - pay - L0) < 1 * MM, (f"free {free:.4f} - payout {pay:.4f} - CAD {L0:.4f} = "
                                           f"{(free - pay - L0) * 1000:.1f} mm (level wind "
                                           f"{joints.get_value(joints.find(sc, 'Level wind')) * 1000:.0f} mm)")


# =====================================================================================================================
# the panel
# =====================================================================================================================

def test_the_panel_draws_every_new_setting(moving):
    from test_paths_panel import draw_panel
    sc = moving.sc
    s = sc.fresing
    texts_all = []
    for i, it in enumerate(s.cables):
        s.cables_index = i
        for k in range(-1, len(it.contacts)):
            paths.find(sc, it.name).contacts_index = k
            texts_all += draw_panel()[0]
    joined = " ".join(texts_all)                       # (long lines are wrapped into several labels)
    assert "Winch keeps it tight" in joined
    assert "pays out" in joined
    assert f"stays where it was from frame {LET_GO_FRAME} on" in joined
    bake(sc, moving.anim())
    show(sc, sc.frame_end)
    s.cables_index = [c.name for c in s.cables].index(paths.find(sc, CABLE).name)
    texts = " ".join(draw_panel()[0])
    assert "Hangs from 'SHEAVE'" in texts and "left 'HORN'" in texts, texts
    paths.hold(sc, paths.find(sc, CABLE), "a")
    paths.set_keep_tight(sc, paths.find(sc, WIRE), False)
    for i in range(len(s.cables)):
        s.cables_index = i
        draw_panel()
