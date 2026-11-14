"""Task 0080: "follows by table" – a joint follows another by a piecewise-straight table (a spool's turn against the
metres of cable paid out: one straight piece per layer). On the test crane (tests/data), like test_couplings.py.

Joint values are internal units: radians and metres.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
TOL = 2e-5

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints  # noqa: E402

# trolley (slide, m) -> wheel 1 (rad): three straight pieces with different slopes, like three layers on a drum
XS = np.array([-0.05, 0.0, 0.03, 0.07, 0.12])
YS = np.array([-1.0, 0.0, 1.2, 2.0, 4.5])


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    tr = ob(sc, "TROLLEY.ASM")
    joints.create(sc, "SLIDE", [tr], tr.matrix_world.translation.copy(), X, name="Trolley")
    for n in (0, 1):
        w = ob(sc, "WHEEL", n)
        joints.create(sc, "ROTATE", [w], w.matrix_world.translation.copy(), Y, name=f"Wheel {n + 1}")
    return sc


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def update():
    bpy.context.view_layer.update()


def J(sc, name):
    return joints.find(sc, name)


def angle_of(sc, name):
    """The turn the wheel's motion empty really has (what moves the part): its driven rotation."""
    return J(sc, name).motion.rotation_euler[2]


def test_interp_is_straight_beyond_the_ends():
    assert joints.interp(XS, YS, 0.015) == pytest.approx(0.6)
    assert joints.interp(XS, YS, 0.2) == pytest.approx(4.5 + 0.08 * 2.5 / 0.05)
    assert joints.interp(XS, YS, -0.1) == pytest.approx(-1.0 - 0.05 * 1.0 / 0.05)
    assert np.allclose(joints.interp(XS, YS, XS), YS)


def test_table_moves_the_follower(scene):
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    j = J(scene, "Wheel 1")
    assert j.follows == "Trolley" and j.couple_table == "test:drum"
    for x in (0.0, 0.01, 0.03, 0.05, 0.1, 0.15, -0.02, -0.08):
        joints.set_value(J(scene, "Trolley"), x)
        update()
        want = joints.interp(XS, YS, x)
        assert joints.get_value(J(scene, "Wheel 1")) == pytest.approx(want, abs=1e-9)
        assert angle_of(scene, "Wheel 1") == pytest.approx(want, abs=TOL), x
        # (not the copy a driver writes into the motion's own value: Blender runs drivers on several threads and that
        # copy can be a step behind – CLAUDE.md section 8; it failed 1 run in 5 on main's run 43517923768)


def test_table_drivers_need_no_python(scene):
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    assert joints.couplings_simple(scene)
    for fc in joints._coupling_fcurves(J(scene, "Wheel 1")):
        assert fc.driver.is_simple_expression and len(fc.keyframe_points) == len(XS)
        assert fc.extrapolation == "LINEAR"


def test_ratio_on_top_of_a_table_reads_the_top(scene):
    """Wheel 2 follows wheel 1 (ratio -2), which follows the trolley by table: wheel 2's drivers read the trolley and
    carry the combined table (never a driven value)."""
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    joints.set_follows(scene, J(scene, "Wheel 2"), "Wheel 1", ratio=-2.0)
    top, m = joints.chain_map(scene, J(scene, "Wheel 2"))
    assert top.name == "Trolley" and m.is_table
    for fc in joints._coupling_fcurves(J(scene, "Wheel 2")):
        assert fc.driver.variables[0].targets[0].id == J(scene, "Trolley").motion
    for x in (0.02, 0.09):
        joints.set_value(J(scene, "Trolley"), x)
        update()
        assert angle_of(scene, "Wheel 2") == pytest.approx(-2.0 * joints.interp(XS, YS, x), abs=TOL)
    assert joints.chain_affine(scene, J(scene, "Wheel 2"))[0] is None       # no straight line through a table


def test_table_in_a_chain_twice_refused(scene):
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    with pytest.raises(RuntimeError):
        joints.set_table(scene, J(scene, "Wheel 2"), "Wheel 1", XS, YS, "test:other")
    with pytest.raises(RuntimeError):
        joints.set_table(scene, J(scene, "Wheel 2"), "Trolley", XS[::-1], YS, "test:bad")      # keys must rise


def test_picking_a_ratio_drops_the_table(scene):
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    joints.set_follows(scene, J(scene, "Wheel 1"), "Trolley", ratio=10.0)
    j = J(scene, "Wheel 1")
    assert not j.couple_table and joints.TABLE not in j.motion and joints.table_of(j) is None
    joints.set_value(J(scene, "Trolley"), 0.05)
    update()
    assert joints.get_value(j) == pytest.approx(math.radians(10.0) * 1000.0 * 0.05, abs=1e-6)
    joints.set_table(scene, j, "Trolley", XS, YS, "test:drum")
    joints.set_follows(scene, j, "")                                         # moves by itself again
    assert not j.couple_table and not j.follows


def test_animation_and_model_specs_keep_the_table(scene):
    joints.set_table(scene, J(scene, "Wheel 1"), "Trolley", XS, YS, "test:drum")
    a = scene.fresing.animations.add()
    a.fps = "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from, b.to_dist, b.easing = "JOINT", "Trolley", 0, 2, False, 0.1, \
        "LINEAR"
    animation.bake(scene, a)
    for f in (1, 14, 26, 40, 51):
        scene.frame_set(f)
        x = joints.get_value(J(scene, "Trolley"))
        assert angle_of(scene, "Wheel 1") == pytest.approx(joints.interp(XS, YS, x), abs=TOL), f
    animation.clear_keys(scene)
    with joints.cad_pose(scene):
        specs = joints.to_specs(scene)
    sp = next(s for s in specs if s["name"] == "Wheel 1")
    assert sp["table_owner"] == "test:drum" and np.allclose(sp["table"][0::2], XS)
