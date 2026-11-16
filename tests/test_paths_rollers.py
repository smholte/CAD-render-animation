"""Task 0125: rollers the cable has left stand still (``fresing_render/blender/paths_rollers.py``).

The touching test and the held values in plain NumPy; in Blender (as a Python module) the sea cable test model
(tests/data/test_sea.step, ``paths_sea.set_up_test_model``: the cable hangs into 15 m of water from its HORN, which it
leaves at about 63° instead of CAD's 90°) with two more rollers under the horn – copies of its ROLLER, one at 30°
(the cable stays on it) and one at 80° (the cable has left it) – and the animation that pays out 8 m.
"""

import json
import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, paths_rollers, paths_sea  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_sea.step")
HORN_AXIS = (0.5, 1.2)          # x, z of the horn's arc axis (m, along Y; tools/make_test_sea.py)
HORN_R = 2.0                    # the cable's middle round it
SEAT = 0.06 + 0.1 + 0.0002      # cable radius + roller radius + the 0.2 mm the model leaves


# ---------------------------------------------------------------------------
# plain NumPy
# ---------------------------------------------------------------------------

def _line(F, lift):
    """A straight cable along x from -2 to 2 m (41 points), at height lift[f] above z = 0."""
    x = np.linspace(-2.0, 2.0, 41)
    pts = np.zeros((F, len(x), 3))
    pts[:, :, 0] = x
    pts[:, :, 2] = np.asarray(lift, dtype=float)[:, None]
    return pts


def test_touching_follows_the_gap_and_the_width():
    lift = [0.0, 0.004, 0.02, 0.1, 0.0, -0.01]
    pts = _line(len(lift), lift)
    # roller 0 under the cable at x = 0.33 (between two points), roller 1 beside the cable's way (along its axis),
    # roller 2 far along x where no piece comes
    centres = [np.array([[0.33, 0.0, -0.16]]), np.array([[0.0, 0.6, -0.16]]), np.array([[9.0, 0.0, -0.16]])]
    axes = [np.array([[0.0, 1.0, 0.0]])] * 3
    seat = np.full(3, 0.16 + 0.006)
    lo, hi = np.full(3, -0.2), np.full(3, 0.2)
    got = paths_rollers.touching(pts, np.ones(len(lift), bool), centres, axes, seat, lo, hi)
    assert got[:, 0].tolist() == [True, True, False, False, True, True]     # (pressed into it counts as touched)
    assert not got[:, 1].any() and not got[:, 2].any()
    # a moment without a path takes the moment before's answer
    ok = np.array([True, True, False, True, False, True])
    got = paths_rollers.touching(pts, ok, centres, axes, seat, lo, hi)
    assert got[:, 0].tolist() == [True, True, True, False, False, True]


def test_touching_a_roller_that_moves_and_a_long_straight():
    F = 4
    pts = np.zeros((F, 2, 3))                     # one straight piece 40 m long, no point near the roller
    pts[:, 0, 0], pts[:, 1, 0] = -20.0, 20.0
    cen = np.zeros((F, 3))
    cen[:, 2] = [-0.16, -0.16, -0.3, -0.16]       # the roller drops away from the cable at moment 2
    got = paths_rollers.touching(pts, np.ones(F, bool), [cen], [np.array([[0.0, 1.0, 0.0]])], np.array([0.166]),
                                 np.array([-0.2]), np.array([0.2]))
    assert got[:, 0].tolist() == [True, True, False, True]


def test_held_values_and_keys():
    coupled = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    touched = np.array([True, True, False, False, True, True, False])
    v = paths_rollers.held_values(coupled, touched)
    assert v.tolist() == [0.0, 1.0, 1.0, 1.0, 2.0, 3.0, 3.0]
    keys = paths_rollers._keys(v, 10)
    assert [k[0] for k in keys] == [10, 11, 13, 14, 15, 16]          # the middle of the still run left out
    assert paths_rollers.held_values(coupled, np.zeros(7, bool)).tolist() == [0.0] * 7
    assert len(paths_rollers._keys(np.full(5, 2.5), 1)) == 1         # never touched: one key


# ---------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("rollers"))


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _horn_roller(sc, src, degrees: float) -> str:
    """A copy of ``src`` (a ROLLER, axis along Y) under the horn, ``degrees`` round it from its top, just under
    the cable as CAD drew it (its own place in the CAD model)."""
    bpy.context.view_layer.update()
    bb = np.array([src.matrix_world @ Vector(c) for c in src.bound_box])
    centre = 0.5 * (bb.min(axis=0) + bb.max(axis=0))
    th = math.radians(degrees)
    r = HORN_R - SEAT
    want = np.array([HORN_AXIS[0] - r * math.sin(th), centre[1], HORN_AXIS[1] + r * math.cos(th)])
    cp = src.copy()
    for col in src.users_collection:
        col.objects.link(cp)
    name = f"HORN ROLLER {int(degrees)}"
    cp[build.PROP_NAME] = name
    cp[build.PROP_UID] = src.get(build.PROP_UID, "") + f"/horn{int(degrees)}"
    cp.matrix_world = Matrix.Translation(Vector(tuple(want - centre))) @ src.matrix_world
    bpy.context.view_layer.update()
    flat = [v for row in cp.matrix_basis for v in row]
    cp[build.PROP_CAD_BASIS] = flat               # its own place in the CAD model (poses put parts there)
    cp[build.PROP_REST_BASIS] = flat
    return name


def load(folder, horn=()):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    src = named(sc, "ROLLER")
    for deg in horn:
        _horn_roller(sc, src, deg)
    made = paths_sea.set_up_test_model(sc)
    return sc, paths.find(sc, made["cable"])


def rollers(item) -> dict:
    """{joint name: contact name} of the cable's rollers (the model's three ROLLERs share a name, not a joint)."""
    return {c.joint: c.name for c in item.contacts if c.kind == "ROLLER"}


def values(sc, j, frames) -> list:
    out = []
    for f in frames:
        sc.frame_set(f)
        out.append(joints.get_value(j))
    return out


def coupled(sc, j, lead_value: float) -> float:
    """What the roller's coupling makes of the cable joint's value (degrees per mm -> rad per m)."""
    return joints.factor("SLIDE", "ROTATE", j.couple_ratio) * lead_value + joints.offset(j)


def test_a_roller_the_cable_has_left_stands_still(folder):
    sc, it = load(folder, horn=(30.0, 80.0))
    names = {n: j for j, n in rollers(it).items()}              # (one of the three ROLLERs as "ROLLER")
    assert {"HORN ROLLER 30", "HORN ROLLER 80"} <= set(names), names
    lead = joints.find(sc, it.joint)
    before = {n: (joints.find(sc, j).follows, joints.find(sc, j).couple_ratio) for n, j in names.items()}
    assert all(f == it.joint for f, _r in before.values())          # every roller turns with the cable
    anim = sc.fresing.animations[paths_sea.TEST_ANIMATION]
    first = int(sc.frame_start)

    for build_no in range(2):                     # (a second Build puts the coupling back first and does it again)
        animation.bake(sc, anim)
        last = int(sc.frame_end)
        frames = [first, (first + last) // 2, last]
        pay = values(sc, lead, frames)
        assert pay[-1] - pay[0] > 7.0             # 8 m paid out
        # the roller the cable has left: no turning at all, its coupling put aside
        j80 = joints.find(sc, names["HORN ROLLER 80"])
        assert j80.follows == "" and paths_rollers.WAS in j80.motion and paths_rollers.STILL in j80.motion
        was = json.loads(j80.motion[paths_rollers.WAS])
        assert was["follows"] == it.joint and was["ratio"] == pytest.approx(before["HORN ROLLER 80"][1], rel=1e-6)
        v80 = values(sc, j80, frames)
        assert max(v80) - min(v80) < 1e-9, v80
        assert v80[0] == pytest.approx(joints.factor("SLIDE", "ROTATE", was["ratio"]) * pay[0], abs=1e-6)
        fc = next(f for f in paths._fcurves(j80.motion) if f.data_path == joints.COUPLING_PATH)
        assert len(fc.keyframe_points) == 1       # never touched: one key
        # the rollers it runs over turn as before
        for n in ("HORN ROLLER 30", "ROLLER"):
            j = joints.find(sc, names[n])
            assert j.follows == it.joint and paths_rollers.WAS not in j.motion, n
            got = values(sc, j, frames)
            assert got == pytest.approx([coupled(sc, j, p) for p in pay], abs=1e-4), n
            assert abs(got[-1] - got[0]) > 10.0   # (turned many times over 8 m)

    # Clear keys: the coupling is back as it was
    animation.clear_keys(sc)
    j80 = joints.find(sc, names["HORN ROLLER 80"])
    assert j80.follows == it.joint
    assert j80.couple_ratio == pytest.approx(before["HORN ROLLER 80"][1], rel=1e-6)
    assert joints.offset(j80) == 0.0
    assert paths_rollers.WAS not in j80.motion and paths_rollers.STILL not in j80.motion
    joints.set_value(lead, 2.0, use_limits=False)
    bpy.context.view_layer.update()
    assert joints.get_value(j80) == pytest.approx(coupled(sc, j80, 2.0), abs=1e-6)
    paths_rollers.after_clear(sc)                 # (safe again)
    assert joints.find(sc, names["HORN ROLLER 80"]).follows == it.joint


def test_nothing_changes_when_the_cable_stays_on_every_roller(folder):
    sc, it = load(folder)
    names = {j: j for j in rollers(it)}
    assert len(names) == 3
    before = {n: (joints.find(sc, j).follows, joints.find(sc, j).couple_ratio) for n, j in names.items()}
    got = paths_rollers.after_bake(sc, 1, 1, {})                    # nothing drawn: nothing to do
    assert got == []
    animation.bake(sc, sc.fresing.animations[paths_sea.TEST_ANIMATION])
    for n, jn in names.items():
        j = joints.find(sc, jn)
        assert (j.follows, j.couple_ratio) == before[n]
        assert paths_rollers.WAS not in j.motion and paths_rollers.STILL not in j.motion
        assert not [f for f in paths._fcurves(j.motion) if f.data_path == joints.COUPLING_PATH]
    animation.clear_keys(sc)
    assert {n: (joints.find(sc, j).follows, joints.find(sc, j).couple_ratio) for n, j in names.items()} == before


# ---------------------------------------------------------------------------
# task 0172: a sheave the cable has left stands still too (0125's open point 5)
# ---------------------------------------------------------------------------

PATHS_MODEL = os.path.join(HERE, "data", "test_paths_a.step")


def _sheave_model(folder):
    """The cable paths test model (test_paths_a.step) with SHEAVE 2 on a slide joint of its own, "Away", that carries
    it up and forward out of the rope's way (as ``tests/test_paths.py`` ``lifting``); the rope runs at 10 m/min the
    whole time while "Away" lifts the sheave off (1 … 2.5 s), holds it there and brings it back (4 … 5.5 s): the rope
    leaves the sheave and comes onto it again."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import make_test_paths as maker
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=PATHS_MODEL, quality="draft") == {"FINISHED"}
    centre = np.array(maker.NUMBERS["contacts"]["SHEAVE 2"]["axis_point"]) * 0.001
    joints.create(sc, "SLIDE", [named(sc, "SHEAVE 2")], Vector(centre), Vector((0.8, 0.0, 0.6)), name="Away")
    made = paths.set_up_test_model(sc)
    it = paths.find(sc, made["cable"])
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Sheave away", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", it.joint, 0.0, 6.0, "LINEAR"
    b.speed_mmin = 10.0
    for start, to in ((1.0, 1.6), (4.0, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Away", start, 1.5, "SMOOTH"
        b.use_from, b.to_dist = True, to
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return sc, it, a


def test_a_sheave_the_cable_has_left_stands_still(folder):
    """While SHEAVE 2 is carried out of the rope's way it does not turn (before task 0172 it turned on with its
    coupling); before and after, touched again, it turns with the rope; SHEAVE 1 (always touched) keeps its coupling;
    'Clear keys' puts SHEAVE 2's coupling back."""
    sc, it, a = _sheave_model(folder)
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    c1 = next(c for c in it.contacts if c.name == "SHEAVE 1")
    j2, j1 = joints.find(sc, c2.joint), joints.find(sc, c1.joint)
    assert c2.kind == c1.kind == "SHEAVE" and j2.follows == it.joint and j1.follows == it.joint
    ratio2 = j2.couple_ratio
    lead = joints.find(sc, it.joint)
    r = animation.bake(sc, a)
    frames = list(range(1, r["frames"] + 1))
    pay = values(sc, lead, frames)
    v2 = values(sc, joints.find(sc, c2.joint), frames)
    v1 = values(sc, joints.find(sc, c1.joint), frames)
    # where the rope lies on SHEAVE 2 (the solver's wrap) at each frame, from the drawn shapes
    rel, first = paths._stored_places(sc, it, paths._inputs_of(it)[1])[:2]
    res = paths._solve_item(sc, it, rel, first=first)
    k2 = [c.name for c in paths._wheels(it)].index("SHEAVE 2")
    on = np.asarray(res["wrap"])[:, k2] > 1e-6
    assert on[0] and on[-1] and (~on).sum() > 25, on               # lifted off for over a second, on at both ends
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == "" and paths_rollers.WAS in j2.motion       # its coupling put aside
    step2, step1, steplead = np.diff(v2), np.diff(v1), np.diff(pay)
    off = ~on[1:] & ~on[:-1]                                         # both frames lifted off: stands still
    assert np.abs(step2[off]).max() < 1e-9, step2[off]
    both = on[1:] & on[:-1]                                          # both on: turns with the rope
    want = joints.factor("SLIDE", "ROTATE", ratio2) * steplead
    assert np.allclose(step2[both], want[both], atol=1e-5)
    assert abs(v2[-1] - v2[0]) > 1.0                                 # (it did turn, before and after)
    j1 = joints.find(sc, c1.joint)
    assert j1.follows == it.joint and paths_rollers.WAS not in j1.motion
    assert np.allclose(step1, joints.factor("SLIDE", "ROTATE", j1.couple_ratio) * steplead, atol=1e-5)
    print(f"\nSHEAVE 2 lifted off at {int((~on).sum())} of {len(on)} frames: stood still there")
    animation.clear_keys(sc)
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == it.joint and j2.couple_ratio == pytest.approx(ratio2, rel=1e-6)
    assert paths_rollers.WAS not in j2.motion and paths_rollers.STILL not in j2.motion
