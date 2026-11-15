"""Task 0125: a sheave on a swivel follows its wire (blender/paths_swivel.py), in Blender (as a Python module).

The scene is made here, tagged like an imported model: a post's foot (BASE), a swivel head (HEAD, an assembly 3 m
up the post's axis) carrying a sheave (SHEAVE, Ø 800 mm, its axis along y, its centre one wire radius off the post's
axis), a pad eye (PAD) 4 m out and 2 m down, and the wire (WIRE, Ø 40 mm) drawn up the post's axis, over the sheave
and down to the pad. Joints: "Swivel" (HEAD about the post's axis), "Side" (PAD sideways), the sheave's own turn
joint (made by 'From CAD cable', riding on the swivel through HEAD).
"""

import inspect
import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, flex, joints, paths, paths_swivel  # noqa: E402

import bench_flex as bf  # noqa: E402

H, RS, RW = 3.0, 0.40, 0.02             # the sheave's height on the post, its surface radius, the wire's radius (m)
R = RS + RW
END = np.array([4.0, 0.0, 1.0])         # where the wire ends on the pad (its top face)
ANIM = "Pad swings"
TOL_DEG = 1.0


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def _box(name, lo, hi):
    v = np.array([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], np.float32)
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    n = v - v.mean(axis=0)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return build._new_mesh(name, v, n.astype(np.float32), np.array(t, np.int32))


def _sheave(name, r, width, n=48):
    """A round disc about the y axis, with its round face's axis as the importer stores it (``fr_axes``)."""
    a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    ring = np.stack([r * np.cos(a), np.zeros(n), r * np.sin(a)], axis=1)
    pos = np.concatenate([ring + (0.0, -width / 2, 0.0), ring + (0.0, width / 2, 0.0),
                          [(0.0, -width / 2, 0.0), (0.0, width / 2, 0.0)]]).astype(np.float32)
    tri = []
    for i in range(n):
        k = (i + 1) % n
        tri += [(i, k, n + k), (i, n + k, n + i), (2 * n, k, i), (2 * n + 1, n + i, n + k)]
    nrm = pos.copy()
    nrm[:, 1] = 0.0
    length = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(length > 1e-9, nrm / np.maximum(length, 1e-9), (0.0, 1.0, 0.0))
    me = build._new_mesh(name, pos, nrm.astype(np.float32), np.array(tri, np.int32))
    me["fr_axes"] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, r]
    return me


def _wire_path() -> np.ndarray:
    """Up the post's axis to the sheave, over its top, straight down to the pad."""
    c = np.array([R, 0.0, H])
    d = END - c
    dist, toward = math.hypot(d[0], d[2]), math.atan2(d[2], d[0])
    leave = None
    for s in (1.0, -1.0):
        th = toward + s * math.acos(R / dist)
        t = c + R * np.array([math.cos(th), 0.0, math.sin(th)])
        if np.dot((math.sin(th), 0.0, -math.cos(th)), (END - t) / np.linalg.norm(END - t)) > 0.999:
            leave = th
    up = np.stack([np.zeros(40), np.zeros(40), np.linspace(0.0, H, 40)], axis=1)
    ang = np.linspace(math.pi, leave, 40)[1:]
    arc = c + R * np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], axis=1)
    run = arc[-1] + np.linspace(0.0, 1.0, 40)[1:, None] * (END - arc[-1])
    return np.concatenate([up, arc, run])


def make_scene(swivel: bool = True):
    """The scene above, the cable read; ``swivel``: the sheave's contact names the swivel joint."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    root = bpy.data.objects.new("SWIVEL.TEST", None)
    sc.collection.objects.link(root)
    bf.tagged(root, "assembly", "SWIVEL.TEST", None, "SWIVEL.TEST#1")
    root[build.PROP_ROOT] = True
    bf.new_part(sc, "BASE", _box("BASE", (-0.3, -0.3, -0.3), (0.3, 0.3, 0.0)), root, Matrix.Identity(4))
    head = bpy.data.objects.new("HEAD", None)
    root.users_collection[0].objects.link(head)
    head.matrix_basis = Matrix.Translation((0.0, 0.0, H))
    bf.tagged(head, "assembly", "HEAD", root, "SWIVEL.TEST#1/HEAD#1")
    bf.new_part(sc, "SHEAVE", _sheave("SHEAVE", RS, 0.08), head, Matrix.Translation((R, 0.0, 0.0)))
    pad = bf.new_part(sc, "PAD", _box("PAD", (-0.2, -0.2, -0.4), (0.2, 0.2, 0.0)), root,
                      Matrix.Translation(tuple(END)))
    knob = bf.new_part(sc, "KNOB", _box("KNOB", (-0.1, -0.1, -0.1), (0.1, 0.1, 0.1)), root,
                       Matrix.Translation((-2.0, 0.0, 0.0)))
    wire = bf.new_part(sc, "WIRE", bf.tube_mesh("WIRE", _wire_path(), RW), root, Matrix.Identity(4))
    update()
    joints.create(sc, "ROTATE", [head], Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)), name="Swivel")
    joints.create(sc, "SLIDE", [pad], Vector(tuple(END)), Vector((0.0, 1.0, 0.0)), name="Side")
    joints.create(sc, "ROTATE", [knob], Vector((-2.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)), name="Lead")
    update()
    paths.add_cable(sc, "Wire")
    paths.read_cad(sc, paths.find(sc, "Wire"), wire)
    it = paths.find(sc, "Wire")
    assert [(c.name, c.kind) for c in it.contacts] == [("SHEAVE", "SHEAVE")]
    assert it.a_part.name == "BASE" and it.b_part.name == "PAD" and it.contacts[0].joint
    if swivel:
        it.contacts[0].swivel = "Swivel"
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = ANIM, 0.0, "25"
    for start, to in ((0.0, 2.5), (1.2, -1.5)):          # sideways one way, then back past the middle
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Side", start, 1.2, "SMOOTH"
        b.use_from = True
        b.to_dist = to
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    update()
    return sc


def swivel(sc):
    return joints.find(sc, "Swivel")


def tilt(sc) -> float:
    """Degrees between the wire's last run (the drawn centreline's last piece: a straight run is one piece) and the
    sheave's plane."""
    it = paths.find(sc, "Wire")
    pts = paths.shape_now(sc, it)
    assert paths.lengths_now(sc, it)[-1] - paths.lengths_now(sc, it)[-2] > 1.0     # (the free run to the pad)
    run = pts[-1] - pts[-2]
    run /= np.linalg.norm(run)
    axis = paths.wheels_now(sc, it)[0].axis
    return math.degrees(math.asin(min(1.0, abs(float(run @ axis)))))


def set_side(sc, y):
    joints.set_value(joints.find(sc, "Side"), y, use_limits=False)
    update()
    paths.refresh(sc)                   # (the handler does this after a change in the app)
    update()
    paths.refresh(sc)
    update()


def bake(sc, anim) -> dict:
    """Build animation. Until paths._bake reads ``paths_swivel.objects`` in its own pass and calls ``after_read``
    (task 0125, wired by the lead worker), the same is done here before its read: one extra pass, same result."""
    if "after_read" in inspect.getsource(paths._bake):
        return animation.bake(sc, anim)
    was = paths_swivel.before_read

    def shim(scene, first, frames):
        mats = flex.read_places(scene, paths_swivel.objects(scene), first, frames, keep_shown=False)
        return paths_swivel.after_read(scene, mats, first, frames)
    paths_swivel.before_read = shim
    try:
        return animation.bake(sc, anim)
    finally:
        paths_swivel.before_read = was


def riders(sc) -> list:
    """The objects that ride on the swivel and that a cable reads: the head, the sheave, its joint's arrow and
    motion."""
    sheave = joints.find(sc, paths.find(sc, "Wire").contacts[0].joint)
    return [o for o in sc.objects if o.name in ("HEAD", "SHEAVE")] + [sheave.frame, sheave.motion, swivel(sc).motion]


def test_after_read_corrects_the_places_read():
    """The places read before the swivel was keyed, corrected by ``after_read``, equal those read with the keys."""
    sc = make_scene(swivel=False)
    animation.bake(sc, sc.fresing.animations[ANIM])        # the pad's keys; the swivel not keyed yet
    paths.find(sc, "Wire").contacts[0]["swivel"] = "Swivel"     # (no update: the built animation stays)
    first, frames = sc.frame_start, sc.frame_end - sc.frame_start + 1
    objs = list({o.name: o for o in paths_swivel.objects(sc) + riders(sc)}.values())
    assert {swivel(sc).frame.name, swivel(sc).motion.name, "PAD"} <= {o.name for o in paths_swivel.objects(sc)}
    flex.drop_read()
    mats = {k: v.copy() for k, v in flex.read_places(sc, objs, first, frames, keep_shown=False).items()}
    before = {k: v.copy() for k, v in mats.items()}
    assert paths_swivel.after_read(sc, mats, first, frames) == []
    assert swivel(sc).motion[paths_swivel.TAG] == "Wire"
    flex.drop_read()
    fresh = flex.read_places(sc, objs, first, frames, keep_shown=False)
    worst = max(float(np.abs(mats[o.name] - fresh[o.name]).max()) for o in riders(sc))
    assert worst < 1e-4                                             # (float32 matrices)
    assert max(float(np.abs(before[o.name] - fresh[o.name]).max()) for o in riders(sc)) > 0.1    # (it did move)
    assert float(np.abs(mats["PAD"] - before["PAD"]).max()) == 0.0   # what does not ride on it stays as read
    animation.clear_keys(sc)
    assert paths_swivel.TAG not in swivel(sc).motion


def test_after_read_with_one_moment_sets_the_value():
    """No cable read per frame (F == 1, or nothing read at all): the swivel is set for the pose, no keys."""
    sc = make_scene()
    joints.set_value(joints.find(sc, "Side"), 2.0, use_limits=False)
    update()
    assert paths_swivel.after_read(sc, {}, sc.frame_start, 1) == []
    assert joints.get_value(swivel(sc)) == pytest.approx(math.atan2(2.0, END[0]), abs=1e-5)
    assert not paths._fcurves(swivel(sc).motion) and swivel(sc).motion[paths_swivel.TAG] == "Wire"
    paths_swivel.after_clear(sc)
    assert paths_swivel.TAG not in swivel(sc).motion


def test_the_sign_of_the_swivel():
    """A positive value turns the head anticlockwise seen from above (about +z): what the closed form assumes."""
    sc = make_scene(swivel=False)
    c = paths.find(sc, "Wire").contacts[0]
    before = np.array(c.carrier.matrix_world) @ np.append(np.array(c.centre), 1.0)
    joints.set_value(swivel(sc), 0.1, use_limits=False)
    update()
    after = np.array(c.carrier.matrix_world) @ np.append(np.array(c.centre), 1.0)
    assert math.atan2(after[1], after[0]) - math.atan2(before[1], before[0]) == pytest.approx(0.1, abs=1e-5)


def test_values_closed_form():
    """``values`` in plain numbers: a sheave whose plane holds the axis turns C's angle onto P's; a sheave whose
    plane lies beside the axis puts P exactly in its plane; P on the axis or a flat sheave: NaN."""
    cm, nm = np.array([0.42, 0.0, 3.0]), np.array([0.0, 1.0, 0.0])
    p = np.array([[4.0, 1.5, 1.0], [-1.0, -1.0, 0.0], [0.0, 0.0, 5.0]])
    v = paths_swivel.values(cm, nm, p)
    assert v[0] == pytest.approx(math.atan2(1.5, 4.0), abs=1e-9)
    assert v[1] == pytest.approx(math.atan2(-1.0, -1.0), abs=1e-9)
    assert math.isnan(v[2])
    cm2 = np.array([0.42, 0.10, 3.0])            # the sheave's plane 100 mm beside the axis
    for q in ([4.0, 1.5, 1.0], [2.0, -3.0, 0.0], [-3.0, 0.5, 2.0]):
        w = float(paths_swivel.values(cm2, nm, np.array([q]))[0])
        rz = np.array([[math.cos(-w), -math.sin(-w), 0.0], [math.sin(-w), math.cos(-w), 0.0], [0.0, 0.0, 1.0]])
        local = rz @ np.array(q)
        assert local[1] == pytest.approx(0.10, abs=1e-9)        # P in the plane y = 0.10 of the turned sheave
        assert local[0] > 0.0                                   # on the sheave's side of the axis
    assert math.isnan(paths_swivel.values(cm, np.array([0.0, 0.0, 1.0]), p[:1])[0])


def test_live_the_swivel_follows_the_pad():
    sc = make_scene()
    for y in (1.5, -2.0, 3.0, 0.0):
        set_side(sc, y)
        assert math.degrees(joints.get_value(swivel(sc))) == pytest.approx(math.degrees(math.atan2(y, END[0])),
                                                                            abs=0.05)
        assert tilt(sc) < TOL_DEG, y
    assert not paths_swivel.live(sc)            # set already: nothing more to do


def test_no_swivel_set_changes_nothing():
    sc = make_scene(swivel=False)
    set_side(sc, 2.0)
    assert joints.get_value(swivel(sc)) == 0.0 and not paths_swivel.live(sc)
    assert tilt(sc) > 10.0                      # (the wire leaves the sheave's plane: what the swivel is for)
    r = bake(sc, sc.fresing.animations[ANIM])
    assert not any("wivel" in w for w in r["warnings"])
    assert paths_swivel.TAG not in swivel(sc).motion and not paths._fcurves(swivel(sc).motion)
    animation.clear_keys(sc)


def test_build_keys_the_swivel_and_a_coupling_is_put_aside():
    sc = make_scene()
    joints.set_follows(sc, swivel(sc), "Lead", ratio=1.0, offset_value=0.05)
    update()
    r = bake(sc, sc.fresing.animations[ANIM])
    assert not any("wivel" in w for w in r["warnings"]), r["warnings"]
    j = swivel(sc)
    assert j.follows == "" and paths_swivel.WAS in j.motion and j.motion[paths_swivel.TAG] == "Wire"
    fcs = [fc for fc in paths._fcurves(j.motion) if fc.data_path == joints.COUPLING_PATH]
    assert len(fcs) == 1 and len(fcs[0].keyframe_points) == sc.frame_end - sc.frame_start + 1
    worst, turned = 0.0, []
    for f in range(sc.frame_start, sc.frame_end + 1, 3):
        sc.frame_set(f)
        update(1)
        worst = max(worst, tilt(sc))
        turned.append(joints.get_value(swivel(sc)))
    assert worst < TOL_DEG
    assert max(turned) > math.radians(25.0) and min(turned) < math.radians(-15.0)     # it did swing both ways
    animation.clear_keys(sc)
    j = swivel(sc)
    assert j.follows == "Lead" and j.couple_ratio == pytest.approx(1.0) and joints.offset(j) == pytest.approx(0.05)
    assert paths_swivel.WAS not in j.motion and paths_swivel.TAG not in j.motion
    paths_swivel.after_clear(sc)                # twice is harmless
    assert swivel(sc).follows == "Lead"


def test_build_without_a_coupling_and_live_again_after():
    sc = make_scene()
    r = bake(sc, sc.fresing.animations[ANIM])
    assert not any("wivel" in w for w in r["warnings"]), r["warnings"]
    sc.frame_set(sc.frame_end)
    update(1)
    assert tilt(sc) < TOL_DEG
    animation.clear_keys(sc)
    assert paths_swivel.TAG not in swivel(sc).motion and swivel(sc).follows == ""
    set_side(sc, -2.5)                          # live again
    assert tilt(sc) < TOL_DEG


def test_a_step_that_moves_the_swivel_wins():
    sc = make_scene()
    a = sc.fresing.animations[ANIM]
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Swivel", 0.0, 1.0, "SMOOTH"
    b.use_from = True
    b.to_angle = math.radians(10.0)
    r = bake(sc, a)
    assert any("Swivel 'Swivel'" in w and "moved by the animation" in w for w in r["warnings"]), r["warnings"]
    assert paths_swivel.TAG not in swivel(sc).motion
    sc.frame_set(sc.frame_end)
    update(1)
    assert math.degrees(joints.get_value(swivel(sc))) == pytest.approx(10.0, abs=1e-3)
    animation.clear_keys(sc)
