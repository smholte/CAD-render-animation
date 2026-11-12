"""Task 0093: joints made in a batch (the demo's 415, model updates) – one scene update for the whole batch, and a
joint stacked on one made a moment ago in the same batch lands on the right axis; a model moved by its root keeps
its place (Build, poses, saved scenes, the start scene, a model update), while a part moved by hand inside it still
goes back.

Test crane (tests/data), Blender as a Python module.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
P = Vector((0.75, 0.25, 0.45))            # a pivot point on the trolley
TOL = 1e-5                                # 0.01 mm
ANG = math.radians(0.01)

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, states  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(tmp_path, copies=1):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    for _ in range(copies):
        assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name, root=None, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name
                   and (root is None or _root(o) is root)), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def _root(o):
    while o.parent is not None:
        o = o.parent
    return o


def update():
    bpy.context.view_layer.update()


def same_frame(a: Matrix, b: Matrix):
    """Places within 0.01 mm and axes within 0.01°."""
    assert (a.translation - b.translation).length < TOL, (a.translation, b.translation)
    for k in range(3):
        ca, cb = a.col[k].xyz.normalized(), b.col[k].xyz.normalized()
        assert ca.angle(cb, 0.0) < ANG, (k, ca, cb)


def moved_root(sc, root=None):
    """Turn the model 30° about Z and move it 2 m in X and 0.5 m up, by hand (matrix_basis), as in the view."""
    root = root or build.model_roots(sc)[0]
    m = Matrix.Translation((2.0, 0.3, 0.5)) @ Matrix.Rotation(math.radians(30), 4, "Z") @ root.matrix_basis
    root.matrix_basis = m
    update()
    return root, m.copy()


# ---------------------------------------------------------------------------
# joints in a batch
# ---------------------------------------------------------------------------

def _stack(sc, batch: bool, base_explicit: bool):
    """Turn (rotate about Z at P) with Slide (along X) stacked on it, the trolley moving."""
    tr = ob(sc, "TROLLEY.ASM")
    if batch:
        with joints._batch(sc):
            a = joints.create(sc, "ROTATE", [tr], P, Z, name="Turn")
            base = a.motion if base_explicit else None
            joints.create(sc, "SLIDE", [tr], P + Vector((0, 0.1, 0)), X, name="Slide", base=base)
    else:
        joints.create(sc, "ROTATE", [tr], P, Z, name="Turn")
        update()
        base = joints.find(sc, "Turn").motion if base_explicit else None
        joints.create(sc, "SLIDE", [tr], P + Vector((0, 0.1, 0)), X, name="Slide", base=base)
    update()
    return joints.find(sc, "Slide")


@pytest.mark.parametrize("base_explicit", [False, True])
def test_stacked_joint_in_one_batch_lands_where_two_steps_put_it(tmp_path, base_explicit):
    want = {}
    for batch in (False, True):
        sc = fresh(tmp_path)
        moved_root(sc)                                  # the base's frame far from the world origin
        j = _stack(sc, batch, base_explicit)
        assert joints.rides_on(sc, j).name == "Turn"
        want[batch] = (j.frame.matrix_world.copy(), joints.axis_world(j))
        # and it moves right: turn 90° then slide 0.2 m along the turned X
        tr = ob(sc, "TROLLEY.ASM")
        q0 = tr.matrix_world.translation.copy()
        joints.set_value(joints.find(sc, "Turn"), math.radians(90))
        joints.set_value(joints.find(sc, "Slide"), 0.2)
        update()
        want[batch] += (tr.matrix_world.translation - q0,)
    same_frame(want[True][0], want[False][0])
    assert (want[True][1][0] - want[False][1][0]).length < TOL
    assert want[True][1][1].angle(want[False][1][1], 0.0) < ANG
    assert (want[True][2] - want[False][2]).length < TOL


def test_a_batch_updates_the_scene_once(tmp_path, monkeypatch):
    """One update on the way in (the CAD pose) and one on the way out, however many joints and couplings."""
    sc = fresh(tmp_path)
    calls = []
    real = joints._update
    monkeypatch.setattr(joints, "_update", lambda scene: (calls.append(1), real(scene)))
    bolt = "ISO 4017 M12 x 40 - 8.8 HDG"
    with joints._batch(sc):
        before = len(calls)
        made = []
        for n in range(4):
            w = ob(sc, bolt, n=n)
            j = joints.create(sc, "ROTATE", [w], w.matrix_world.translation, X, name=f"Wheel {n}")
            made.append(j.name)
        for name in made[1:]:
            joints.set_follows(sc, joints.find(sc, name), made[0], ratio=1.0)
        inside = len(calls) - before
    assert inside == 0, f"{inside} scene updates inside the batch"
    assert len(calls) <= 2
    update()
    w0, w3 = ob(sc, bolt, n=0), ob(sc, bolt, n=3)
    r0, r3 = w0.matrix_world.to_3x3().copy(), w3.matrix_world.to_3x3().copy()
    joints.set_value(joints.find(sc, made[0]), math.radians(40))
    update()
    a0 = (r0.inverted() @ w0.matrix_world.to_3x3()).to_quaternion().angle
    a3 = (r3.inverted() @ w3.matrix_world.to_3x3()).to_quaternion().angle
    assert abs(a0 - math.radians(40)) < 1e-4 and abs(a3 - math.radians(40)) < 1e-4


def test_model_update_rebuilds_a_stack_on_a_moved_model(tmp_path):
    """rebuild_from_specs makes a stack in one batch: the stacked axis comes back where it was."""
    sc = fresh(tmp_path)
    root, _m = moved_root(sc)
    j = _stack(sc, batch=False, base_explicit=False)
    before = j.frame.matrix_world.copy()
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    j = joints.find(sc, "Slide")
    assert joints.rides_on(sc, j).name == "Turn"
    same_frame(j.frame.matrix_world, before)


# ---------------------------------------------------------------------------
# a model moved by its root keeps its place
# ---------------------------------------------------------------------------

def _check_stays(sc, root, m, part, part_rest_world, what):
    update()
    same_frame(root.matrix_basis, m)
    assert (part.matrix_world.translation - part_rest_world.translation).length < TOL, what


def test_a_moved_root_stays_and_a_moved_part_goes_back(tmp_path):
    sc = fresh(tmp_path)
    s = sc.fresing
    joints.create(sc, "ROTATE", [ob(sc, "TROLLEY.ASM")], P, Z, name="Turn")
    states.save_pose(sc, "Home")
    states.save_shot(sc, "Start")
    root, m = moved_root(sc)
    boom = ob(sc, "BOOM.ASM")
    boom_rest = boom.matrix_world.copy()                # its place on the moved model
    assert root.name not in joints.free_moves(sc)
    boom.matrix_basis = Matrix.Translation((0, 0, 0.3)) @ boom.matrix_basis      # a part moved by hand
    update()
    assert list(joints.free_moves(sc)) == [boom.name]

    states.reset_pose(sc)                               # "Everything back to CAD position"
    _check_stays(sc, root, m, boom, boom_rest, "reset")
    boom.matrix_basis = Matrix.Translation((0, 0, 0.3)) @ boom.matrix_basis
    assert states.apply_pose(sc, "Home")
    _check_stays(sc, root, m, boom, boom_rest, "pose")
    boom.matrix_basis = Matrix.Translation((0, 0, 0.3)) @ boom.matrix_basis
    states.apply_shot(sc, "Start")
    _check_stays(sc, root, m, boom, boom_rest, "saved scene")
    with joints.cad_pose(sc):
        update()
        same_frame(root.matrix_basis, m)

    # Build an animation with the start scene, then take it off again
    anim = s.animations.add()
    anim.name, anim.fps, anim.tail = "Turn", "25", 0.0
    anim.start_shot = "Start"
    st = anim.blocks.add()
    st.kind, st.joint, st.start, st.duration, st.easing = "JOINT", "Turn", 0.0, 1.0, "LINEAR"
    st.use_from, st.from_angle, st.to_angle = False, 0.0, math.radians(30)
    info = animation.bake(sc, anim)
    assert not info["warnings"], info
    for f in (1, info["frames"]):
        sc.frame_set(f)
        _check_stays(sc, root, m, boom, boom_rest, f"frame {f}")
    animation.clear_keys(sc)
    _check_stays(sc, root, m, boom, boom_rest, "keys off")

    # a model update keeps the moved root
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    root = build.model_roots(sc)[0]
    same_frame(root.matrix_basis, m)
    states.reset_pose(sc)
    update()
    same_frame(root.matrix_basis, m)


def test_two_copies_placed_apart_stay_apart(tmp_path):
    sc = fresh(tmp_path, copies=2)
    r1, r2 = sorted(build.model_roots(sc), key=lambda r: r.name)
    _r2, m2 = moved_root(sc, r2)
    m1 = r1.matrix_basis.copy()
    joints.create(sc, "ROTATE", [ob(sc, "TROLLEY.ASM", root=r2)], r2.matrix_world @ P, Z, name="Turn 2")
    states.save_pose(sc, "Home")
    for step in (lambda: states.reset_pose(sc), lambda: states.apply_pose(sc, "Home")):
        step()
        update()
        same_frame(r1.matrix_basis, m1)
        same_frame(r2.matrix_basis, m2)
    gap = (ob(sc, "BOOM.ASM", root=r2).matrix_world.translation - ob(sc, "BOOM.ASM", root=r1).matrix_world.translation)
    assert gap.length > 1.0


def test_an_old_saved_delta_on_the_root_does_nothing(tmp_path):
    """A pose saved by an older version may hold a delta for the root: applying it leaves the root where it is."""
    sc = fresh(tmp_path)
    root, m = moved_root(sc)
    joints.apply_free_moves(sc, {root.name: Matrix.Translation((5, 0, 0))}, reset_others=True)
    update()
    same_frame(root.matrix_basis, m)
