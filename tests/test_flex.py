"""Task 0058: hoses, cables and drag chains that follow the motion – the Blender side (blender/flex.py).

Two generic test models (tools/make_test_flex.py, whose numbers these tests use): a luffing arm with three
hydraulic hoses and a cable, and a gantry with a drag chain on each axis. "The drawn tube" is what Blender
evaluates for the hose part (its modifier applied), in world coordinates: rings of ``flex.SIDES`` points.
"""

import math
import os
import random
import sys
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")
HOSES_B = os.path.join(HERE, "data", "test_flex_hoses_b.step")
CHAINS = os.path.join(HERE, "data", "test_flex_chains_a.step")
CRANE = os.path.join(HERE, "data", "test_crane_a.step")
MM = 0.001
END_TOL = 0.1 * MM             # an end on its fitting
PIN_TOL = 1e-6                 # a chain's pins (metres)

import fresing_render  # noqa: E402
import make_test_flex as maker  # noqa: E402
from fresing_render.blender import (animation, build, clash, cylinders, flex, joints, states,  # noqa: E402
                                    turntable)

HOSE_NAMES = ("HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B", "CABLE")
LENGTHS = {"HYDRAULIC HOSE ARM": 1008.54, "HYDRAULIC HOSE CYL A": 450.40, "HYDRAULIC HOSE CYL B": 551.52,
           "CABLE": 1062.59}                                # mm, from the maker's docstring


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    """One output folder for the whole file: the second import of a model comes from its cache."""
    return str(tmp_path_factory.mktemp("flex"))


def load(folder, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture()
def hoses(folder):
    sc = load(folder, HOSES_A)
    made = flex.set_up_test_hoses(sc)
    assert made["items"] == list(HOSE_NAMES) and made["joints"] == ["Luff", "Slide"]
    return sc


@pytest.fixture()
def chains(folder):
    sc = load(folder, CHAINS)
    made = flex.set_up_test_chains(sc)
    assert made["items"] == ["CHAIN X.ASM", "CHAIN Y.ASM", "CHAIN Z.ASM"]
    return sc


def update():
    bpy.context.view_layer.update()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def drawn(part):
    """The part as Blender draws it: (world points (V, 3), the evaluated object's material slots, mesh slots)."""
    e = part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    w = np.array(e.matrix_world, dtype=float)
    return co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3], list(e.material_slots), len(me.materials)


def rings(part):
    """(ring centres (n, 3), smallest and largest distance of a ring's points to its centre)."""
    co = drawn(part)[0]
    assert len(co) and len(co) % flex.SIDES == 0, f"{part.name}: {len(co)} points is no tube"
    r = co.reshape(-1, flex.SIDES, 3)
    c = r.mean(axis=1)
    d = np.linalg.norm(r - c[:, None], axis=2)
    return c, float(d.min()), float(d.max())


def set_joint(sc, name, value):
    joints.set_value(joints.find(sc, name), value)


def arm_deg(sc) -> float:
    """The arm's angle, + = tip up, read from where the arm is."""
    m = ob(sc, "ARM.ASM").matrix_world
    return math.degrees(math.atan2(m[2][0], m[0][0]))


def slide_mm(sc) -> float:
    return (ob(sc, "SLIDE.ASM").matrix_world.translation.x - maker.SLIDE_AT[0] * MM) / MM


def end_errors(sc, names=HOSE_NAMES) -> float:
    """The furthest a drawn tube's end is from where the maker's formulas put its fitting (metres), for the
    pose the model is in."""
    want = maker.hose_ends(arm_deg(sc), slide_mm(sc))
    worst = 0.0
    for name in names:
        it = flex.find(sc, name)
        c, _lo, _hi = rings(it.part)
        for got, end in ((c[0], want[name][0]), (c[-1], want[name][1])):
            worst = max(worst, float(np.linalg.norm(got - np.array(end) * MM)))
    return worst


def angle_deg(a, b) -> float:
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b))))))


def steps(sc, rows, name="Move"):
    """An animation of joint steps: rows of (joint, start s, seconds, to)."""
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = name, 0.0, "25"
    for joint, start, seconds, to in rows:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", joint, start, seconds, "LINEAR"
        b.use_from = True
        if joints.find(sc, joint).kind == "SLIDE":
            b.to_dist = to
        else:
            b.to_angle = to
    return a


def built(sc, rows, name="Move"):
    a = steps(sc, rows, name)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    return a, r


# ---------------------------------------------------------------------------
# hoses: reading them
# ---------------------------------------------------------------------------

def test_a_hose_is_read_from_its_cad_shape(hoses):
    sc = hoses
    ends = maker.hose_ends()
    for name in HOSE_NAMES:
        it = flex.find(sc, name)
        assert it.kind == "HOSE" and it.part is ob(sc, name) and it.part_uid == it.part[build.PROP_UID]
        assert it.diameter == pytest.approx(maker.HOSE_DIAMETER[name] * MM, abs=0.02 * MM)
        assert it.length == pytest.approx(LENGTHS[name] * MM, rel=0.003) and it.cad_length == it.length
        assert it.length >= LENGTHS[name] * MM * 0.9995              # never shorter than drawn
        first, second = maker.HOSE_TOUCHES[name]
        assert (it.a_part.get(build.PROP_NAME), it.b_part.get(build.PROP_NAME)) == (first, second)
        assert it.a_uid == it.a_part[build.PROP_UID] and it.b_uid == it.b_part[build.PROP_UID]
        out_a, out_b = maker.HOSE_OUT[name]
        for part, point, along, end, out in ((it.a_part, it.a_point, it.a_dir, ends[name][0], out_a),
                                             (it.b_part, it.b_point, it.b_dir, ends[name][1], -np.array(out_b))):
            assert (part.matrix_world @ Vector(point) - Vector(end) * MM).length < END_TOL
            assert angle_deg(part.matrix_world.to_3x3() @ Vector(along), out) < 0.5     # both run from A to B
        assert flex.status(sc, it) == ("follows the motion", "OK")
    hose, cable = flex.find(sc, "HYDRAULIC HOSE ARM"), flex.find(sc, "CABLE")
    assert (hose.stiffness, hose.sag) == pytest.approx((0.6, 0.5)) and hose.min_radius == 0.0
    assert (cable.stiffness, cable.sag) == pytest.approx((0.2, 0.8))                    # a soft cable
    assert [flex.label(it) for it in flex.items(sc)] == list(HOSE_NAMES)
    assert flex.active(sc) == cable and flex.parts_of(sc, hose) == [hose.part]


def test_a_part_that_is_no_hose_is_refused(hoses):
    sc = hoses
    for name, why in (("BASE", "not long and thin"), ("VALVE BLOCK", "is not a hose")):
        with pytest.raises(flex.FlexError) as exc:
            flex.add_hose(sc, ob(sc, name))
        assert f"'{name}' is not a hose" in str(exc.value) and why in str(exc.value)
    with pytest.raises(flex.FlexError) as exc:
        flex.add_hose(sc, ob(sc, "CABLE"))
    assert "already follows the motion" in str(exc.value)
    assert len(flex.items(sc)) == 4


def test_a_hose_added_in_another_pose_reads_the_same(folder):
    """The hose is read in the CAD pose, whatever pose the model is in when it is added."""
    sc = load(folder, HOSES_A)
    made = flex.set_up_test_hoses(sc)
    want = {}
    for it in flex.items(sc):
        want[it.name] = (it.length, it.diameter, it.a_part.name, tuple(it.a_point), tuple(it.a_dir), it.b_part.name,
                         tuple(it.b_point), tuple(it.b_dir))
    while len(flex.items(sc)):
        flex.remove(sc, 0)
    set_joint(sc, "Luff", math.radians(17))
    set_joint(sc, "Slide", -0.12)
    update()
    update()
    for name in made["items"]:
        it, notes = flex.add_hose(sc, ob(sc, name), soft=name == "CABLE")
        assert notes == []
        got = (it.length, it.diameter, it.a_part.name, tuple(it.a_point), tuple(it.a_dir), it.b_part.name,
               tuple(it.b_point), tuple(it.b_dir))
        assert got[2] == want[name][2] and got[5] == want[name][5]
        for a, b in zip(got, want[name]):
            if not isinstance(a, str):
                assert a == pytest.approx(b, abs=1e-6), name
    assert arm_deg(sc) == pytest.approx(17, abs=1e-3) and end_errors(sc) < END_TOL      # and bends for this pose
    it = flex.find(sc, "HYDRAULIC HOSE CYL B")
    it.length *= 1.2
    assert flex.fit_to_cad(sc, it) == [] and it.length == pytest.approx(want[it.name][0], abs=1e-6)


def test_a_model_moved_by_its_root_and_a_hose_part_that_moves(folder):
    """The model stands somewhere else, turned (its root moved); and one hose part itself rides on the arm's joint:
    the tube is still drawn between its two fittings (the nodes bring the world points into the part's own space)."""
    sc = load(folder, HOSES_A)
    root = build.model_roots(sc)[0]
    root.matrix_basis = Matrix.Translation((0.7, -0.4, 0.25)) @ Matrix.Rotation(math.radians(35), 4, "Z")
    update()
    arm = ob(sc, "ARM.ASM")
    pivot = root.matrix_world @ Vector((0.1, 0.2, 0.6))
    axis = root.matrix_world.to_3x3() @ Vector((0, -1, 0))
    j = joints.create(sc, "ROTATE", [arm, ob(sc, "HYDRAULIC HOSE ARM")], pivot, axis, name="Luff")
    assert len(joints.members(j)) == 2
    update()
    for name in ("HYDRAULIC HOSE ARM", "CABLE"):
        it, notes = flex.add_hose(sc, ob(sc, name))
        assert notes == []
    it = flex.find(sc, "HYDRAULIC HOSE ARM")
    assert (it.a_part.get(build.PROP_NAME), it.b_part.get(build.PROP_NAME)) == ("FITTING VALVE C", "FITTING ARM")
    m = np.array(root.matrix_world, dtype=float)
    for angle in (0.0, 16.0, -14.0):
        joints.set_value(joints.find(sc, "Luff"), math.radians(angle))
        update()
        want = maker.hose_ends(angle, 0.0)
        for name in ("HYDRAULIC HOSE ARM", "CABLE"):
            c, _lo, _hi = rings(flex.find(sc, name).part)
            for got, end in ((c[0], want[name][0]), (c[-1], want[name][1])):
                assert np.linalg.norm(got - (m[:3, :3] @ (np.array(end) * MM) + m[:3, 3])) < END_TOL, (name, angle)
        assert flex.find(sc, "CABLE").problem == ""
    # it hangs down in the world, whatever way the model is turned
    cable = flex.shape_now(sc, flex.find(sc, "CABLE"))
    assert cable[:, 2].min() < min(cable[0, 2], cable[-1, 2]) - 0.1


def test_an_end_pushed_into_a_block_sits_on_that_block():
    """Hoses are often drawn with their end deep inside the block they are plugged into: no surface is near the end
    point, but the hose's last piece goes in through one."""
    import bench_flex
    bpy.ops.wm.read_factory_settings(use_empty=True)
    flex.forget()
    sc = bpy.context.scene
    root = bpy.data.objects.new("TEST.PLUG", None)
    sc.collection.objects.link(root)
    bench_flex.tagged(root, "assembly", "TEST.PLUG", None, "TEST.PLUG#1")
    root[build.PROP_ROOT] = True
    solid = bpy.data.meshes.new("BLOCK")                            # a block 100 x 100 x 100 round the origin
    solid.from_pydata([(x, y, z) for x in (-0.05, 0.05) for y in (-0.05, 0.05) for z in (-0.05, 0.05)], [],
                      [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    solid.update()
    block = bench_flex.new_part(sc, "BLOCK", solid, root, Matrix.Identity(4))
    path = bench_flex.hose_path(np.array([0.0, 0.0, 0.0]), np.array([0.5, 0.0, 0.3]))
    hose = bench_flex.new_part(sc, "HOSE", bench_flex.tube_mesh("HOSE", path, 0.012), root, Matrix.Identity(4))
    update()
    it, notes = flex.add_hose(sc, hose)
    assert it.a_part is block and it.b_part is root                 # end A 50 mm inside the block; end B in the air
    assert len(notes) == 1 and notes[0].startswith("End B of 'HOSE' touches no part: it stays with 'TEST.PLUG'")
    assert it.diameter == pytest.approx(0.024, abs=1e-4)
    assert np.abs(np.array(it.a_point)).max() < 1e-4 and flex.status(sc, it)[1] == "OK"
    block.matrix_basis = Matrix.Translation((0.05, 0.02, -0.03))    # the block moves: the end goes with it
    update()
    c, _lo, _hi = rings(hose)
    assert np.linalg.norm(c[0] - (0.05, 0.02, -0.03)) < END_TOL and np.linalg.norm(c[-1] - (0.5, 0.0, 0.3)) < END_TOL


def test_an_older_node_tree_is_made_again(hoses):
    sc = hoses
    old = bpy.data.node_groups["FR flex hose"]
    old[flex.TAG] = flex.VERSION - 1                          # as a project made by an older version has it
    flex.refresh(sc, force=True)
    new = bpy.data.node_groups["FR flex hose"]
    assert new[flex.TAG] == flex.VERSION and len([g for g in bpy.data.node_groups if g.name.startswith("FR flex")]) == 1
    for name in HOSE_NAMES:
        assert ob(sc, name).modifiers[flex.MOD].node_group == new
    assert end_errors(sc) < END_TOL


# ---------------------------------------------------------------------------
# hoses: the drawn tube
# ---------------------------------------------------------------------------

def test_the_tube_ends_on_its_fittings(hoses):
    sc = hoses
    cad_dir = {}
    for name in HOSE_NAMES:
        it = flex.find(sc, name)
        cad_dir[name] = (it.a_part.matrix_world.to_3x3().copy(), it.b_part.matrix_world.to_3x3().copy())
    for arm, slide in ((0.0, 0.0), (20.0, 0.0), (-20.0, 0.0), (8.0, 0.12), (-10.0, -0.15), (0.0, 0.15)):
        set_joint(sc, "Luff", math.radians(arm))
        set_joint(sc, "Slide", slide)
        update()
        assert arm_deg(sc) == pytest.approx(arm, abs=1e-3) and slide_mm(sc) == pytest.approx(slide / MM, abs=1e-3)
        assert end_errors(sc) < END_TOL, (arm, slide)
        for name in HOSE_NAMES:
            it = flex.find(sc, name)
            c, lo, hi = rings(it.part)
            assert lo == pytest.approx(it.diameter / 2, abs=1e-6) and hi == pytest.approx(it.diameter / 2, abs=1e-6)
            length = float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum())
            assert length == pytest.approx(it.length, rel=0.005), name
            # the direction it leaves its fittings in: the CAD one, turned along with the fitting
            out_a, out_b = maker.HOSE_OUT[name]
            now_a = it.a_part.matrix_world.to_3x3() @ cad_dir[name][0].inverted() @ Vector(out_a)
            now_b = it.b_part.matrix_world.to_3x3() @ cad_dir[name][1].inverted() @ Vector(out_b)
            assert angle_deg(c[1] - c[0], now_a) < 1.0, (name, arm)
            assert angle_deg(c[-2] - c[-1], now_b) < 1.0, (name, arm)
            assert not it.problem, (name, arm, slide, it.problem)


def test_the_tube_takes_the_parts_material(hoses):
    sc = hoses
    for name in HOSE_NAMES:
        part = ob(sc, name)
        _co, slots, mesh_slots = drawn(part)
        assert mesh_slots == 1                                   # a shape without a slot renders without a material
        assert slots[0].link == "OBJECT" and slots[0].material is not None
        assert slots[0].material.original == part.material_slots[0].material
    sh = bpy.data.objects[flex.SHAPES]
    assert sh.hide_render and sh.hide_viewport and sh.hide_select and sh.users_collection[0].name == flex.COLLECTION
    assert [g.name for g in bpy.data.node_groups if g.name.startswith("FR flex")] == ["FR flex hose"]
    for name in HOSE_NAMES:                                      # the modifier comes first on its part
        assert ob(sc, name).modifiers[0].name == flex.MOD


# ---------------------------------------------------------------------------
# hoses: live, poses, on and off
# ---------------------------------------------------------------------------

def test_hoses_follow_live_without_a_build(hoses):
    sc = hoses
    before = flex.shape_now(sc, flex.find(sc, "HYDRAULIC HOSE ARM")).copy()
    assert before.shape == (flex.POINTS, 3)
    set_joint(sc, "Luff", math.radians(15))
    update()                                     # the handler solves here; nothing was built
    assert not sc.fresing.anim_baked and end_errors(sc) < END_TOL
    after = flex.shape_now(sc, flex.find(sc, "HYDRAULIC HOSE ARM"))
    assert np.abs(after[-1] - before[-1]).max() > 0.05 and np.abs(after[0] - before[0]).max() < 1e-7
    # a pose applied by a script (the model is not updated in between: flex.refresh sees to it)
    states.save_pose(sc, "Up")
    set_joint(sc, "Luff", math.radians(-12))
    set_joint(sc, "Slide", 0.1)
    update()
    assert end_errors(sc) < END_TOL and arm_deg(sc) == pytest.approx(-12, abs=1e-3)
    states.apply_pose(sc, "Up")
    tip = flex.shape_now(sc, flex.find(sc, "HYDRAULIC HOSE ARM"))[-1]
    assert np.abs(tip - after[-1]).max() < 1e-6              # already solved, before anything else updates
    assert end_errors(sc) < END_TOL and arm_deg(sc) == pytest.approx(15, abs=1e-3)
    states.reset_pose(sc)
    assert np.abs(flex.shape_now(sc, flex.find(sc, "HYDRAULIC HOSE ARM")) - before).max() < 1e-6
    assert end_errors(sc) < END_TOL
    # a fitting switched off in the view (Blender no longer works out its place) still carries its end
    ob(sc, "FITTING ARM").hide_viewport = True
    set_joint(sc, "Luff", math.radians(11))
    update()
    assert end_errors(sc) < END_TOL
    ob(sc, "FITTING ARM").hide_viewport = False
    set_joint(sc, "Luff", 0.0)
    update()
    # only what moved is solved again: the slide carries one end of the cable and nothing else
    update()
    n = flex._STATE["solves"]
    set_joint(sc, "Slide", -0.05)
    update()
    assert flex._STATE["solves"] - n == 1
    update()
    assert flex._STATE["solves"] - n == 1                    # nothing moved: nothing solved


def test_off_shows_the_cad_shape_again(hoses):
    sc = hoses
    it = flex.find(sc, "CABLE")
    part = it.part
    cad = len(part.data.vertices)
    tube = len(drawn(part)[0])
    assert tube % flex.SIDES == 0 and tube != cad
    it.enabled = False
    assert len(drawn(part)[0]) == cad and flex.status(sc, it) == ("off", "OFF")
    set_joint(sc, "Luff", math.radians(10))
    update()
    assert len(drawn(part)[0]) == cad                        # stiff, as in the CAD file
    it.enabled = True
    assert len(drawn(part)[0]) == tube and end_errors(sc) < END_TOL
    # removed: the CAD shape, no modifier, and the other hoses carry on
    flex.remove(sc, flex.index_of(sc, it))
    assert len(flex.items(sc)) == 3 and flex.find(sc, "CABLE") is None
    assert part.modifiers.get(flex.MOD) is None and flex.TAG not in part and len(drawn(part)[0]) == cad
    set_joint(sc, "Luff", math.radians(-5))
    update()
    for name in HOSE_NAMES[:3]:
        c, _lo, _hi = rings(flex.find(sc, name).part)
        want = maker.hose_ends(arm_deg(sc), slide_mm(sc))[name]
        assert np.linalg.norm(c[-1] - np.array(want[1]) * MM) < END_TOL
    while len(flex.items(sc)):
        flex.remove(sc, 0)
    assert flex.SHAPES not in bpy.data.objects and flex.COLLECTION not in bpy.data.collections
    assert not [g for g in bpy.data.node_groups if g.name.startswith("FR flex")]
    assert not [o for o in sc.objects if o.modifiers.get(flex.MOD)]


def test_settings_reshape_the_hose_and_fit_to_cad_resets(hoses):
    sc = hoses
    it = flex.find(sc, "CABLE")
    before = flex.shape_now(sc, it).copy()
    low = before[:, 2].min()
    it.sag = 0.0                                             # no weight: another shape, between the same ends
    light = flex.shape_now(sc, it)
    assert np.abs(light - before).max() > 0.005 and np.abs(light[[0, -1]] - before[[0, -1]]).max() < 1e-7
    assert light[:, 2].min() > low + 0.002                   # … that does not hang as low
    it.sag = 0.8
    assert np.abs(flex.shape_now(sc, it) - before).max() < 1e-6
    it.stiffness = 0.9                                       # stiff as a hydraulic hose: another shape again
    assert np.abs(flex.shape_now(sc, it) - before).max() > 0.005
    it.stiffness = 0.2
    assert np.abs(flex.shape_now(sc, it) - before).max() < 1e-6
    it.length = it.cad_length * 1.1                          # longer: it hangs lower
    assert flex.shape_now(sc, it)[:, 2].min() < low - 0.02
    it.diameter = 0.02
    _c, lo, hi = rings(it.part)
    assert lo == pytest.approx(0.01, abs=1e-6) and hi == pytest.approx(0.01, abs=1e-6)
    # the end on another part: it stays where it is and moves with that part from now on
    arm = ob(sc, "ARM")
    flex.set_end_part(sc, it, "B", arm)
    assert it.b_part is arm and end_errors(sc) < END_TOL
    set_joint(sc, "Luff", math.radians(12))
    update()
    assert end_errors(sc) < END_TOL                          # (the gland sits on the arm: the same motion)
    notes = flex.fit_to_cad(sc, it)
    assert notes == [] and it.length == it.cad_length and it.diameter == pytest.approx(0.01, abs=2e-5)
    assert it.b_part.get(build.PROP_NAME) == "CABLE GLAND ARM" and it.sag == pytest.approx(0.8)
    assert end_errors(sc) < END_TOL


# ---------------------------------------------------------------------------
# hoses: Build animation
# ---------------------------------------------------------------------------

def test_a_built_animation_shows_every_frame(hoses):
    sc = hoses
    solves = flex._STATE["solves"]
    t = time.perf_counter()
    a, r = built(sc, (("Luff", 0.0, 2.0, math.radians(20)), ("Slide", 2.0, 2.0, 0.12)))
    took = time.perf_counter() - t
    assert r["frames"] == 101 and sc.fresing.anim_baked == a.name
    assert took < 15.0                                       # 4 hoses x 101 frames (0.2 s on the web machine)
    sh = bpy.data.objects[flex.SHAPES]
    assert len(sh.data.vertices) == 101 * 4 * flex.DRAWN
    solves = flex._STATE["solves"]
    for f in range(1, 102):                                  # at every frame the ends are on their fittings
        sc.frame_set(f)
        assert end_errors(sc) < END_TOL, f
    sc.frame_set(101)
    assert arm_deg(sc) == pytest.approx(20, abs=1e-3) and slide_mm(sc) == pytest.approx(120, abs=1e-3)
    # the same frame gives the same shape whatever was shown before
    part = flex.find(sc, "HYDRAULIC HOSE ARM").part
    sc.frame_set(10)
    drawn(part)
    sc.frame_set(50)
    one = drawn(part)[0]
    sc.frame_set(90)
    drawn(part)
    sc.frame_set(50)
    two = drawn(part)[0]
    assert np.array_equal(one, two)
    # playing costs no Python: nothing was solved since the Build
    update()
    assert flex._STATE["solves"] == solves
    # Clear keys: live again, in the pose the model is back in
    animation.clear_keys(sc)
    update()
    assert len(sh.data.vertices) == 4 * flex.DRAWN and arm_deg(sc) == pytest.approx(0, abs=1e-3)
    assert end_errors(sc) < END_TOL
    set_joint(sc, "Luff", math.radians(-15))
    update()
    assert end_errors(sc) < END_TOL


def test_adding_and_removing_while_an_animation_is_built(folder):
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    flex.remove(sc, flex.index_of(sc, flex.find(sc, "CABLE")))
    flex.remove(sc, flex.index_of(sc, flex.find(sc, "HYDRAULIC HOSE CYL B")))
    built(sc, (("Luff", 0.0, 1.0, math.radians(18)), ("Slide", 0.0, 1.0, 0.1)))
    sh = bpy.data.objects[flex.SHAPES]
    assert len(sh.data.vertices) == 26 * 2 * flex.DRAWN
    stepped = flex._STATE["steps"]
    # added: every frame of it at once (its end parts' places are read: one pass through the frames)
    flex.add_hose(sc, ob(sc, "CABLE"), soft=True)
    assert flex._STATE["steps"] == stepped + 26 and len(sh.data.vertices) == 26 * 3 * flex.DRAWN
    flex.add_hose(sc, ob(sc, "HYDRAULIC HOSE CYL B"))
    assert flex._STATE["steps"] == stepped + 52 and len(sh.data.vertices) == 26 * 4 * flex.DRAWN
    names = ("HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "CABLE", "HYDRAULIC HOSE CYL B")
    for f in (1, 9, 18, 26):
        sc.frame_set(f)
        assert end_errors(sc, names) < END_TOL, f
    # off and on again, removed: the others keep their frames, nothing is stepped through
    cable = flex.find(sc, "CABLE")
    cable.enabled = False
    sc.frame_set(13)
    assert len(drawn(cable.part)[0]) == len(cable.part.data.vertices)
    assert end_errors(sc, ("HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B")) < END_TOL
    cable.enabled = True
    assert end_errors(sc, names) < END_TOL
    flex.remove(sc, 0)
    assert flex._STATE["steps"] == stepped + 52 and len(sh.data.vertices) == 26 * 3 * flex.DRAWN
    for f in (2, 26):
        sc.frame_set(f)
        assert end_errors(sc, names[1:]) < END_TOL, f
    # the end on another part while built: that part's places are read along the frames; on one that was read
    # already (the arm hose's fitting, also on the arm): no stepping
    flex.set_end_part(sc, flex.find(sc, "CABLE"), "B", ob(sc, "ARM.PIN"))
    assert flex._STATE["steps"] == stepped + 78
    flex.set_end_part(sc, flex.find(sc, "CABLE"), "B", ob(sc, "FITTING BARREL A"))
    flex.set_end_part(sc, flex.find(sc, "CABLE"), "B", ob(sc, "ARM.PIN"))
    assert flex._STATE["steps"] == stepped + 78
    sc.frame_set(20)
    assert end_errors(sc, names[1:]) < END_TOL


def first_short_frame(sc, name, length):
    """The first frame at which the hose's ends (each with its first piece held by its fitting) are further apart
    than the hose can reach: worked out from the maker's formulas."""
    piece = length / (flex.POINTS - 1)
    out_a, out_b = maker.HOSE_OUT[name]                      # (both fittings of the arm hose keep their direction)
    for f in range(int(sc.frame_start), int(sc.frame_end) + 1):
        sc.frame_set(f)
        a, b = maker.hose_ends(arm_deg(sc), slide_mm(sc))[name]
        inner = np.linalg.norm((np.array(b) * MM + piece * np.array(out_b)) -
                               (np.array(a) * MM + piece * np.array(out_a)))
        if inner > length - 2 * piece:
            return f, float(inner + 2 * piece - length)
    return 0, 0.0


def test_a_hose_that_is_too_short_says_so(hoses):
    sc = hoses
    it = flex.find(sc, "HYDRAULIC HOSE ARM")
    a, _r = built(sc, (("Luff", 0.0, 2.0, math.radians(20)),))
    assert it.problem == "" and flex.status(sc, it)[1] == "OK"
    stepped = flex._STATE["steps"]
    it.length = it.cad_length * 0.8                          # a setting changed after the Build
    assert flex._STATE["steps"] == stepped                   # … is solved again without stepping through the frames
    short = it.length
    frame, _need = first_short_frame(sc, it.name, short)
    assert 5 < frame < 45 and it.problem_frame == frame
    text, level = flex.status(sc, it)
    assert level == "WARN" and text.startswith(f"too short at frame {frame}: needs ") and text.endswith(" mm more")
    sc.frame_set(51)                                         # the stretched hose still ends on its fittings
    assert end_errors(sc) < END_TOL
    # how much is missing at the worst frame (the last: the arm is furthest up there)
    sc.frame_set(int(sc.frame_end))
    a_end, b_end = maker.hose_ends(arm_deg(sc), slide_mm(sc))[it.name]
    out_a, out_b = maker.HOSE_OUT[it.name]
    reach = short                                            # the shortest hose that reaches: its own first and
    for _ in range(40):                                      # last piece (1/32 of it) held by the fittings
        piece = reach / (flex.POINTS - 1)
        reach = np.linalg.norm((np.array(b_end) * MM + piece * np.array(out_b)) -
                               (np.array(a_end) * MM + piece * np.array(out_a))) + 2 * piece
    need = reach - short
    assert float(text.split("needs ")[1].split(" mm")[0]) == pytest.approx(need / MM, abs=1.0)
    # the Build says it too, once
    r = animation.bake(sc, sc.fresing.animations[a.name])
    hits = [w for w in r["warnings"] if "HYDRAULIC HOSE ARM" in w]
    assert len(hits) == 1 and hits[0].startswith(f"Hose 'HYDRAULIC HOSE ARM' is too short at frame {frame} (it needs ")
    it = flex.find(sc, "HYDRAULIC HOSE ARM")
    it.length = it.cad_length
    assert it.problem == "" and flex.status(sc, it) == ("follows the motion", "OK")
    assert not animation.bake(sc, sc.fresing.animations[a.name])["warnings"]
    # a bend limit the motion cannot keep: a warning with the limit
    it = flex.find(sc, "HYDRAULIC HOSE CYL A")
    it.min_radius = 0.5
    assert it.problem.startswith("bends tighter than 500 mm at frame ") and flex.status(sc, it)[1] == "WARN"
    it.min_radius = 0.0
    assert it.problem == ""
    # live: in the pose shown
    animation.clear_keys(sc)
    update()
    it = flex.find(sc, "HYDRAULIC HOSE ARM")
    it.length = it.cad_length * 0.6
    assert it.problem.startswith("too short in this pose: needs ") and it.problem_frame == 0


def test_the_cylinders_hoses_follow_its_barrel(hoses):
    sc = hoses
    c = cylinders.find(sc, "Luff cylinder")
    # live, the arm moved by its joint: the cylinder follows the arm, the two hoses the barrel
    for arm in (15.0, -18.0):
        set_joint(sc, "Luff", math.radians(arm))
        update()
        update()
        assert end_errors(sc) < END_TOL, arm
    set_joint(sc, "Luff", 0.0)
    update()
    # built, the arm moved by the cylinder's stroke
    cylinders.set_mode(sc, c, "DRIVE")
    c = cylinders.find(sc, "Luff cylinder")
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Stroke", 0.0, "25"
    for start, stroke in ((0.0, 0.32), (1.5, 0.03)):         # out (the arm goes up), then nearly all the way in
        b = a.blocks.add()
        b.kind, b.cylinder, b.start, b.duration = "CYLINDER", c.name, start, 1.5
        b.use_from, b.to_stroke = False, stroke
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    seen = []
    barrel_fitting = ob(sc, "FITTING BARREL B")
    for f in range(1, int(sc.frame_end) + 1, 5):
        sc.frame_set(f)
        seen.append(arm_deg(sc))
        assert end_errors(sc) < END_TOL, f
        it = flex.find(sc, "HYDRAULIC HOSE CYL B")
        tip = rings(it.part)[0][-1]
        assert (barrel_fitting.matrix_world @ Vector(it.b_point) - Vector(tip)).length < END_TOL
    assert min(seen) < -15 and max(seen) > 15                # the stroke swung the arm through its range


def test_a_still_in_a_saved_scene(hoses):
    """What the queue's background Blender does for a still: apply the saved scene, render."""
    sc = hoses
    set_joint(sc, "Luff", math.radians(18))
    set_joint(sc, "Slide", -0.1)
    update()
    states.save_shot(sc, "Arm up")
    want = {name: flex.shape_now(sc, flex.find(sc, name)).copy() for name in HOSE_NAMES}
    set_joint(sc, "Luff", math.radians(-15))
    set_joint(sc, "Slide", 0.1)
    update()
    assert np.abs(flex.shape_now(sc, flex.find(sc, "CABLE")) - want["CABLE"]).max() > 0.05
    states.apply_shot(sc, "Arm up")
    for name in HOSE_NAMES:                                  # solved by the time apply_shot returns
        assert np.abs(flex.shape_now(sc, flex.find(sc, name)) - want[name]).max() < 1e-6, name
    assert arm_deg(sc) == pytest.approx(18, abs=1e-3) and end_errors(sc) < END_TOL


def test_the_turntable_shows_the_hoses_unchanged(hoses):
    sc = hoses
    set_joint(sc, "Luff", math.radians(10))
    update()
    before = {name: drawn(ob(sc, name))[0] for name in HOSE_NAMES}
    made = turntable.make(sc)
    r = animation.bake(sc, made["animation"])
    assert not r["warnings"], r["warnings"]
    assert sc.fresing.anim_baked and len(bpy.data.objects[flex.SHAPES].data.vertices) == r["frames"] * 4 * flex.DRAWN
    for f in (1, r["frames"] // 2, r["frames"]):
        sc.frame_set(f)
        for name in HOSE_NAMES:
            assert np.abs(drawn(ob(sc, name))[0] - before[name]).max() < 1e-6, (name, f)


# ---------------------------------------------------------------------------
# hoses: the project file, model update, projects without flex parts
# ---------------------------------------------------------------------------

def test_save_and_open_again(hoses, tmp_path):
    sc = hoses
    flex.find(sc, "CABLE").stiffness = 0.35
    set_joint(sc, "Luff", math.radians(7))
    update()
    path = str(tmp_path / "hoses.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert [it.name for it in flex.items(sc)] == list(HOSE_NAMES)
    assert flex.find(sc, "CABLE").stiffness == pytest.approx(0.35)
    for name in HOSE_NAMES:
        it = flex.find(sc, name)
        mod = it.part.modifiers.get(flex.MOD)
        assert mod is not None and mod.node_group.name == "FR flex hose" and mod.show_viewport and mod.show_render
    assert end_errors(sc) < END_TOL and arm_deg(sc) == pytest.approx(7, abs=1e-3)       # as saved
    set_joint(sc, "Luff", math.radians(-9))
    update()
    assert end_errors(sc) < END_TOL                          # live again after loading
    # a built animation: saved, opened, its frames show; a slider moved then solves every frame again
    built(sc, (("Luff", 0.0, 1.0, math.radians(20)),))
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.fresing.anim_baked == "Move"
    solves, stepped = flex._STATE["solves"], flex._STATE["steps"]
    for f in (1, 13, 26):
        sc.frame_set(f)
        assert end_errors(sc) < END_TOL, f
    assert flex._STATE["solves"] == solves
    sc.frame_set(26)
    it = flex.find(sc, "CABLE")
    low = flex.shape_now(sc, it)[:, 2].min()
    it.sag = 0.0
    assert flex._STATE["steps"] == stepped and flex._STATE["solves"] == solves + 26     # its 26 frames, no stepping
    assert flex.shape_now(sc, it)[:, 2].min() > low + 0.01
    for f in (1, 26):
        sc.frame_set(f)
        assert end_errors(sc) < END_TOL, f


def test_model_update_keeps_the_hoses(hoses):
    sc = hoses
    arm, cable, cyl = (flex.find(sc, n) for n in ("HYDRAULIC HOSE ARM", "CABLE", "HYDRAULIC HOSE CYL B"))
    arm.stiffness, arm.sag, arm.min_radius = 0.85, 0.3, 0.05
    cable.length = cable.cad_length * 1.04                   # set by hand: stays
    cable.name = "Lamp cable"
    cyl.enabled = False
    old = {it.name: it.cad_length for it in flex.items(sc)}
    old_parts = {it.part.name for it in flex.items(sc)}
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=HOSES_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert not [n.text for n in sc.fresing.report_notes if "ose" in n.text or "able" in n.text]
    assert [it.name for it in flex.items(sc)] == ["HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B",
                                                  "Lamp cable"]
    arm, cable, cyl = (flex.find(sc, n) for n in ("HYDRAULIC HOSE ARM", "Lamp cable", "HYDRAULIC HOSE CYL B"))
    assert (arm.stiffness, arm.sag, arm.min_radius) == pytest.approx((0.85, 0.3, 0.05))
    assert arm.cad_length == pytest.approx(old["HYDRAULIC HOSE ARM"] * 1.05, rel=0.002)     # the wider path of B
    assert arm.length == arm.cad_length
    assert cable.cad_length == pytest.approx(old["Lamp cable"], rel=1e-4)
    assert cable.length == pytest.approx(old["Lamp cable"] * 1.04, rel=1e-5)
    mod = cyl.part.modifiers.get(flex.MOD)
    assert not cyl.enabled and (mod is None or not mod.show_viewport)       # off: its new CAD shape shows
    cyl.enabled = True
    for it in flex.items(sc):                                # on the new parts, with their modifiers
        assert it.part is not None and it.part.name in sc.objects and it.part.name not in old_parts
        assert it.part.get(build.PROP_NAME) in HOSE_NAMES and it.part.modifiers.get(flex.MOD) is not None
        assert it.a_part.name in sc.objects and it.b_part.name in sc.objects
        assert flex.status(sc, it) == ("follows the motion", "OK")
    cable.name = "CABLE"
    assert end_errors(sc) < END_TOL
    set_joint(sc, "Luff", math.radians(14))
    set_joint(sc, "Slide", 0.08)
    update()
    assert end_errors(sc) < END_TOL


def test_a_part_gone_in_the_new_revision(hoses, folder):
    """Updating the hoses model to another model altogether: the items stay, say what is missing, and nothing
    breaks."""
    sc = hoses
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    notes = [n.text for n in sc.fresing.report_notes]
    assert "Hose 'CABLE': its part is gone in the new revision" in notes
    assert len(flex.items(sc)) == 4
    for it in flex.items(sc):
        assert it.part is None and flex.status(sc, it) == ("its part is gone", "ERROR")
    update()
    a = steps(sc, ())
    assert any("its part is gone" in w for w in flex.bake(sc, a))


def test_a_project_without_flex_parts_gets_nothing(folder):
    sc = load(folder, HOSES_A)
    joints.create(sc, "ROTATE", [ob(sc, "ARM.ASM")], Vector((0.1, 0.2, 0.6)), Vector((0, -1, 0)), name="Luff")
    solves = flex._STATE["solves"]
    a, _r = built(sc, (("Luff", 0.0, 1.0, math.radians(20)),))
    assert flex.bake(sc, a) == [] and flex.after_model_update(sc, {}, {}) == []
    flex.refresh(sc)
    flex.after_clear(sc)
    sc.frame_set(10)
    update()
    assert flex.COLLECTION not in bpy.data.collections and flex.SHAPES not in bpy.data.objects
    assert not [g for g in bpy.data.node_groups if g.name.startswith("FR flex")]
    assert not [o for o in sc.objects if o.modifiers.get(flex.MOD) or flex.TAG in o]
    assert flex._STATE["solves"] == solves and flex.candidates(sc)


def test_candidates_are_found_by_name_and_type(hoses, folder):
    sc = hoses
    assert flex.candidates(sc) == []                         # the four are flex parts already
    while len(flex.items(sc)):
        flex.remove(sc, 0)
    found = {o.get(build.PROP_NAME): kind for o, kind in flex.candidates(sc)}
    assert found == {name: "HOSE" for name in HOSE_NAMES}
    sc = load(folder, CHAINS)
    found = flex.candidates(sc)
    assert len(found) == 47 and {kind for _o, kind in found} == {"CHAIN"}
    assert {o.get(build.PROP_NAME) for o, _k in found} == {"CHAIN LINK"}
    row = flex.siblings(sc, next(o for o, _k in found if build.logical_parent(o).get(build.PROP_NAME) == "CHAIN Z.ASM"))
    assert len(row) == 13


# ---------------------------------------------------------------------------
# drag chains
# ---------------------------------------------------------------------------

CHAIN_ENDS = {"CHAIN X.ASM": ("CHAIN BRACKET X FIXED", "CHAIN BRACKET X MOVING", 18),
              "CHAIN Y.ASM": ("CHAIN BRACKET Y FIXED", "CHAIN BRACKET Y MOVING", 16),
              "CHAIN Z.ASM": ("CHAIN BRACKET Z FIXED", "CHAIN BRACKET Z MOVING", 13)}
AXIS_OF = {"CHAIN X.ASM": ("X", 0), "CHAIN Y.ASM": ("Y", 1), "CHAIN Z.ASM": ("Z", 2)}


def links_of(sc, asm):
    home = ob(sc, asm)
    return [o for o in build.iter_parts(sc) if build.logical_parent(o) == home]


def own_points(o):
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(float)


def chain_numbers(sc, it):
    """The chain as drawn now, in its own coordinates (u along the fixed run, v towards the moving run):
    (pins (n, 3), how far the last pin is from its place on the moving part)."""
    pins = flex.pins_now(sc, it)
    frame = np.array(it.a_part.matrix_world, dtype=float) @ np.array(it.frame, dtype=float).reshape(4, 4)
    inv = np.linalg.inv(frame)
    end = np.array(it.b_part.matrix_world @ Vector(it.b_point))
    return pins @ inv[:3, :3].T + inv[:3, 3], float(np.linalg.norm(pins[-1] - end))


def check_pins(sc, it, where=""):
    """Pins one pitch apart, the first at the chain's start, the last on its part, all in the chain's plane."""
    pins, off = chain_numbers(sc, it)
    assert off < PIN_TOL, (it.name, where, off)
    chords = np.linalg.norm(np.diff(pins, axis=0), axis=1)
    assert np.abs(chords - it.pitch).max() < PIN_TOL, (it.name, where)
    assert np.abs(pins[0]).max() < PIN_TOL and np.abs(pins[:, 2]).max() < 1e-5        # in its plane
    return pins


def check_chain(sc, it, where=""):
    """``check_pins``, and: the bend on its circle, the runs at v = 0 and v = 2 r, no link through another.
    Returns the u of the bend's centre."""
    pins = check_pins(sc, it, where)
    u, v = pins[:, 0], pins[:, 1]
    r = it.radius
    on_bend = (v > 1e-5) & (v < 2 * r - 1e-5)
    assert on_bend.sum() >= 5, (it.name, where)
    centre = u[on_bend] - np.sqrt(np.maximum(r * r - (v[on_bend] - r) ** 2, 0.0))      # the bend is at the +u side
    mids = (v[on_bend] > 0.2 * r) & (v[on_bend] < 1.8 * r)                             # (well conditioned there)
    assert np.ptp(centre[mids]) < 2e-6, (it.name, where, np.ptp(centre[mids]))
    assert np.abs(v[~on_bend & (u < centre[mids].mean())]).min() < 1e-5               # a run at v = 0 …
    assert np.abs(v[-1] - 2 * r) < 1e-5                                                # … and one at v = 2 r
    d = np.linalg.norm(pins[:, None] - pins[None], axis=2)
    apart = np.abs(np.arange(len(pins))[:, None] - np.arange(len(pins))[None]) >= 2
    assert d[apart].min() > 1.5 * it.pitch, (it.name, where)                           # no link through another
    assert it.problem == "", (it.name, where, it.problem)
    return float(centre[mids].mean())


def test_a_chain_is_read_from_its_links(folder):
    sc = load(folder, CHAINS)
    cad = {o.name: np.array(o.matrix_world, dtype=float) for o in sc.objects}
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        joints.create(sc, "SLIDE", [ob(sc, asm)], ob(sc, asm).matrix_world.translation.copy(), Vector(d), name=name)
    update()
    rng = random.Random(58)
    for asm, (fixed, moving, count) in CHAIN_ENDS.items():
        links = links_of(sc, asm)
        order = sorted(links, key=lambda o: int(o[build.PROP_UID].rsplit("#", 1)[1]))   # as placed: fixed end first
        rng.shuffle(links)
        fit = flex._read_chain(sc, links)["fit"]
        assert fit.ok and fit.pose_error < 1e-6 and fit.residual < 1e-6
        it, notes = flex.add_chain(sc, links)
        assert notes == [] and it.name == asm and it.kind == "CHAIN" and not it.made_links
        assert it.pitch == pytest.approx(0.040, abs=1e-6) and it.radius == pytest.approx(0.080, abs=1e-6)
        assert it.count == count == len(it.links) and it.mode == "STRAIGHT"
        assert (it.a_part.get(build.PROP_NAME), it.b_part.get(build.PROP_NAME)) == (fixed, moving)
        assert [r.obj for r in it.links] == order and flex.parts_of(sc, it) == order
        assert it.link_uids.split("\n") == [o[build.PROP_UID] for o in order]
        # the maker's pins: the first on the fixed bracket's side, the last on the moving one
        pins = flex.pins_now(sc, it)
        want = maker.chain_pins(asm.replace(".ASM", ""))
        assert np.abs(pins - np.array(want) * MM).max() < 2e-6
    update()
    # in the CAD pose every link is drawn where the CAD file put it
    assert [g.name for g in bpy.data.node_groups if g.name.startswith("FR flex")] == ["FR flex link"]
    for it in flex.items(sc):
        for o in flex.parts_of(sc, it):
            want = own_points(o) @ cad[o.name][:3, :3].T + cad[o.name][:3, 3]
            assert np.abs(drawn(o)[0] - want).max() < 0.05 * MM, o.name
            assert o.modifiers[0].name == flex.MOD and flex.status(sc, it) == ("follows the motion", "OK")
    with pytest.raises(flex.FlexError) as exc:
        flex.add_chain(sc, [ob(sc, "BED"), ob(sc, "BEAM"), ob(sc, "SPINDLE")])
    assert "cannot be read as a drag chain" in str(exc.value)
    with pytest.raises(flex.FlexError):
        flex.add_chain(sc, links_of(sc, "CHAIN X.ASM"))                     # they are a chain already


def test_chains_roll_over_their_whole_travel(chains):
    sc = chains
    rest = {it.name: check_chain(sc, it, "CAD") for it in flex.items(sc)}
    travel = {"X": (-0.15, 0.15), "Y": (-0.10, 0.10), "Z": (-0.06, 0.06)}
    for it_name, (axis, _k) in AXIS_OF.items():
        lo, hi = travel[axis]
        for value in np.linspace(lo, hi, 13):
            set_joint(sc, axis, float(value))
            update()
            it = flex.find(sc, it_name)
            centre = check_chain(sc, it, f"{axis} = {value:.3f}")
            # the bend moves half as far as the axis (+X and +Z along the fixed run, +Y against it)
            sign = maker.CHAIN_SIGN[it_name.replace(".ASM", "")]
            # (to a few hundredths of a mm: links are straight pieces, the bend's place wobbles a little as
            # each pin goes onto the circle)
            assert centre - rest[it_name] == pytest.approx(sign * value / 2, abs=5e-5), (it_name, value)
        set_joint(sc, axis, 0.0)
        update()
    # all three axes at once, and what is drawn: a link in the middle of the X chain lies between its pins
    for axis, value in (("X", 0.12), ("Y", -0.08), ("Z", 0.05)):
        set_joint(sc, axis, value)
    update()
    for it in flex.items(sc):
        check_chain(sc, it, "all three")
    it = flex.find(sc, "CHAIN X.ASM")
    pins = flex.pins_now(sc, it)
    for k in (0, 7, 9, 17):
        pts = drawn(it.links[k].obj)[0]
        mid = 0.5 * (pts.min(axis=0) + pts.max(axis=0))
        assert np.linalg.norm(mid - 0.5 * (pins[k] + pins[k + 1])) < 0.012   # (the link's body is not centred on them)
        along = (pins[k + 1] - pins[k]) / it.pitch
        size = np.ptp(pts @ along)
        assert size == pytest.approx(0.032, abs=1e-5), k                     # 32 mm long along its pins: turned right
    # beyond its length the chain cannot reach: a warning, no error
    set_joint(sc, "X", 0.9)
    update()
    it = flex.find(sc, "CHAIN X.ASM")
    assert it.problem == "cannot reach in this pose" and flex.status(sc, it)[1] == "WARN"
    set_joint(sc, "X", 0.0)
    update()
    assert flex.find(sc, "CHAIN X.ASM").problem == ""


PROGRAM = """%
G90 G94 G17 G21
G54
G0 X20 Y20 Z20
G1 X120 Y-40 Z5 F3000
G1 X-100 Y60 Z30
G2 X-60 Y60 I20 J0
G0 X0 Y0 Z40
M30
%
"""


def test_chains_follow_a_built_animation_and_a_g_code_program(chains, tmp_path):
    sc = chains
    _a, r = built(sc, (("X", 0.0, 1.0, 0.15), ("Y", 0.5, 1.0, -0.1), ("Z", 1.0, 1.0, 0.06)))
    solves = flex._STATE["solves"]
    assert len(bpy.data.objects[flex.SHAPES].data.vertices) == r["frames"] * 47
    seen = set()
    for f in range(1, r["frames"] + 1, 3):
        sc.frame_set(f)
        for it in flex.items(sc):
            check_chain(sc, it, f"frame {f}")
        seen.add(round(joints.get_value(joints.find(sc, "X")), 3))
    assert len(seen) > 5 and flex._STATE["solves"] == solves             # it moved; nothing was solved while playing
    sc.frame_set(20)
    one = drawn(flex.find(sc, "CHAIN X.ASM").links[9].obj)[0]
    sc.frame_set(48)
    sc.frame_set(20)
    assert np.array_equal(one, drawn(flex.find(sc, "CHAIN X.ASM").links[9].obj)[0])
    animation.clear_keys(sc)
    update()
    for it in flex.items(sc):
        check_chain(sc, it, "cleared")
    # the CNC machine runs a short program: the chains follow the three axes
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    for name, op in (("TOOL T1 FLAT D6", bpy.ops.fresing.cnc_use_tool),
                     ("STOCK 300x200x30", bpy.ops.fresing.cnc_use_workpiece)):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ob(sc, name).select_set(True)
        bpy.context.view_layer.objects.active = ob(sc, name)
        assert op() == {"FINISHED"}
    path = tmp_path / "part.ngc"
    path.write_text(PROGRAM)
    g = sc.fresing.animations.add()
    g.name, g.tail = "Program", 0.0
    b = g.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = str(path)
    r = animation.bake(sc, g)
    assert not r["warnings"], r["warnings"]
    moved = {axis: set() for axis in "XYZ"}
    for f in range(1, r["frames"] + 1, max(1, r["frames"] // 40)):
        sc.frame_set(f)
        for it in flex.items(sc):
            check_chain(sc, it, f"program frame {f}")
        for axis in "XYZ":
            moved[axis].add(round(joints.get_value(joints.find(sc, axis)), 3))
    assert all(len(v) > 3 for v in moved.values()), moved                 # the program drove all three axes


def test_swap_ends_and_remove(chains):
    sc = chains
    it = flex.find(sc, "CHAIN X.ASM")
    cad = {o.name: drawn(o)[0] for o in flex.parts_of(sc, it)}
    first = [r.obj.name for r in it.links]
    flex.swap_ends(sc, it)
    it = flex.find(sc, "CHAIN X.ASM")
    assert (it.a_part.get(build.PROP_NAME), it.b_part.get(build.PROP_NAME)) == ("CHAIN BRACKET X MOVING",
                                                                                 "CHAIN BRACKET X FIXED")
    assert [r.obj.name for r in it.links] == first[::-1] and it.count == 18
    for o in flex.parts_of(sc, it):                          # the same chain in the CAD pose
        assert np.abs(drawn(o)[0] - cad[o.name]).max() < 0.05 * MM
    check_chain(sc, it, "swapped")
    set_joint(sc, "X", 0.1)                                  # its fixed end now rides on the carriage
    update()
    pins = flex.pins_now(sc, it)
    assert np.linalg.norm(pins[0] - (np.array(maker.chain_pins("CHAIN X")[-1]) * MM + (0.1, 0, 0))) < 2e-6
    assert np.linalg.norm(pins[-1] - np.array(maker.chain_pins("CHAIN X")[0]) * MM) < 2e-6
    check_chain(sc, it, "swapped, X = 100")
    flex.swap_ends(sc, it)
    it = flex.find(sc, "CHAIN X.ASM")
    assert it.a_part.get(build.PROP_NAME) == "CHAIN BRACKET X FIXED" and [r.obj.name for r in it.links] == first
    # numbers set by hand: a wider bend
    it.radius = 0.09
    pins = check_pins(sc, it, "radius 90")                   # (the moving run now leaves the bend as a tangent)
    on_bend = pins[(pins[:, 1] > 0.02) & (pins[:, 1] < 0.12)]
    centre = on_bend[:, 0] - np.sqrt(0.09 ** 2 - (on_bend[:, 1] - 0.09) ** 2)
    assert len(on_bend) >= 3 and np.ptp(centre) < 2e-6 and it.radius == pytest.approx(0.09)
    it.count = 25                                            # CAD links: as many as there are
    assert it.count == 18
    it.radius = 0.08
    it.mode = "GLIDE"                                        # the other way to draw the upper run: still a chain
    check_pins(sc, it, "glide")
    it.mode = "STRAIGHT"
    check_chain(sc, it, "straight again")
    it.radius = 0.09
    # removed: the links back where the CAD file has them (the carriage is still at X = 100)
    parts = flex.parts_of(sc, it)
    flex.remove(sc, flex.index_of(sc, it))
    assert [i.name for i in flex.items(sc)] == ["CHAIN Y.ASM", "CHAIN Z.ASM"]
    for o in parts:
        assert o.modifiers.get(flex.MOD) is None and flex.LOCAL not in o and flex.TAG not in o
        assert np.abs(drawn(o)[0] - cad[o.name]).max() < 1e-6
    for it in flex.items(sc):
        check_chain(sc, it, "after remove")


def u_band_part(sc, run_low=0.5, run_high=0.3, radius=0.08, height=0.02, width=0.05, at=(0.0, -0.6, 0.5)):
    """A drag chain drawn as one solid (a band bent into a U in the X-Z plane), added to the model as a part."""
    arc = np.linspace(-0.5 * math.pi, 0.5 * math.pi, 25)
    outer, inner = radius + height / 2, radius - height / 2
    flat = [(-run_low, -height / 2)] + [(outer * math.cos(t), radius + outer * math.sin(t)) for t in arc]
    flat += [(-run_high, 2 * radius + height / 2), (-run_high, 2 * radius - height / 2)]
    flat += [(inner * math.cos(t), radius + inner * math.sin(t)) for t in arc[::-1]] + [(-run_low, height / 2)]
    pts, faces = flex._prism(np.array(flat), -width / 2, width / 2)
    me = bpy.data.meshes.new("ENERGY CHAIN")
    me.from_pydata([(x, z, y) for x, y, z in pts], [], faces)            # the band's plane upright: X-Z
    me.update()
    me.materials.append(None)
    root = build.model_roots(sc)[0]
    part = bpy.data.objects.new("ENERGY CHAIN", me)
    root.users_collection[0].objects.link(part)
    part.parent = root
    part.matrix_basis = Matrix.Translation(at)
    part[build.PROP_KIND], part[build.PROP_NAME] = "part", "ENERGY CHAIN"
    part[build.PROP_UID] = root[build.PROP_UID] + "/ENERGY CHAIN#1"
    build.set_mat(part, build.PROP_CAD_BASIS, part.matrix_basis)
    build.set_mat(part, build.PROP_REST_BASIS, part.matrix_basis)
    update()
    return part


def test_a_chain_drawn_as_one_solid_gets_links(chains):
    sc = chains
    part = u_band_part(sc)
    assert (part, "CHAIN") in flex.candidates(sc)
    it, notes = flex.add_chain(sc, [], part=part)
    assert it.made_links and it.part is part and len(it.links) == 0 and len(notes) == 2      # it touches nothing
    assert it.radius == pytest.approx(0.08, abs=1e-5) and it.height == pytest.approx(0.02, abs=1e-5)
    assert it.width == pytest.approx(0.05, abs=1e-5) and it.pitch == pytest.approx(0.032, abs=1e-5)
    assert it.count == round((0.5 + 0.3 + math.pi * 0.08) / it.pitch)
    link = bpy.data.objects[f"{flex.MADE_LINK} ENERGY CHAIN"]
    assert link.hide_render and link.hide_viewport
    pts, slots, mesh_slots = drawn(part)
    assert len(pts) == it.count * len(link.data.vertices) and mesh_slots == 1 and len(slots) == 1
    # the links lie along the band: every drawn point within the band's reach of its outline
    band = own_points(part) @ np.array(part.matrix_world.to_3x3()).T + np.array(part.matrix_world.translation)
    assert pts.min(axis=0) == pytest.approx(band.min(axis=0), abs=0.012)
    assert pts.max(axis=0) == pytest.approx(band.max(axis=0), abs=0.012)
    pins = flex.pins_now(sc, it)
    assert np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max() < PIN_TOL
    # its moving end on the carriage: it rolls with the X axis
    flex.set_end_part(sc, it, "B", ob(sc, "CARRIAGE"))
    it = flex.find(sc, "ENERGY CHAIN")
    end = pins[-1].copy()
    set_joint(sc, "X", 0.1)
    update()
    pins = flex.pins_now(sc, it)
    assert np.linalg.norm(pins[-1] - (end + (0.1, 0, 0))) < 2e-6
    assert np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max() < PIN_TOL and it.problem == ""
    assert len(drawn(part)[0]) == it.count * len(link.data.vertices)
    # more links, wider links: drawn at once
    it.count += 3
    assert len(drawn(part)[0]) == it.count * len(link.data.vertices) and it.points == it.count
    it.width = 0.08
    link = bpy.data.objects[f"{flex.MADE_LINK} ENERGY CHAIN"]
    assert np.ptp(own_points(link)[:, 2]) == pytest.approx(0.08, abs=1e-6)
    _a, r = built(sc, (("X", 0.0, 1.0, -0.1),))
    sc.frame_set(r["frames"])
    assert np.linalg.norm(flex.pins_now(sc, it)[-1] - (end + (-0.1, 0, 0))) < 2e-6
    animation.clear_keys(sc)
    flex.remove(sc, flex.index_of(sc, flex.find(sc, "ENERGY CHAIN")))
    assert f"{flex.MADE_LINK} ENERGY CHAIN" not in bpy.data.objects
    assert len(drawn(part)[0]) == len(part.data.vertices)


def test_the_clash_check_leaves_flex_parts_out(chains):
    sc = chains
    flexed = {o.name for o in flex.flex_parts(sc)}
    assert len(flexed) == 47
    checked = {o.name for o in clash.objects(sc)}
    assert not (checked & flexed) and "CHAIN BRACKET X FIXED" in checked and "BEAM" in checked
    while len(flex.items(sc)):
        flex.remove(sc, 0)
    assert flexed <= {o.name for o in clash.objects(sc)}


def test_model_update_keeps_the_chains(chains):
    sc = chains
    it = flex.find(sc, "CHAIN Z.ASM")
    it.radius = 0.085                                        # set by hand: stays
    flex.swap_ends(sc, flex.find(sc, "CHAIN Y.ASM"))
    old_parts = {o.name for o in flex.flex_parts(sc)}
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=CHAINS, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert [i.name for i in flex.items(sc)] == ["CHAIN X.ASM", "CHAIN Y.ASM", "CHAIN Z.ASM"]
    assert not (old_parts & {o.name for o in flex.flex_parts(sc)}) and len(flex.flex_parts(sc)) == 47
    x, y, z = flex.items(sc)
    assert z.radius == pytest.approx(0.085) and x.radius == pytest.approx(0.08, abs=1e-6)
    assert y.a_part.get(build.PROP_NAME) == "CHAIN BRACKET Y MOVING"       # still swapped
    assert x.a_part.get(build.PROP_NAME) == "CHAIN BRACKET X FIXED" and x.a_part.name in sc.objects
    for it in (x, z):
        assert flex.status(sc, it)[1] == "OK"
    set_joint(sc, "X", -0.1)
    update()
    check_chain(sc, flex.find(sc, "CHAIN X.ASM"), "updated")
    for o in flex.parts_of(sc, flex.find(sc, "CHAIN X.ASM")):
        assert o.modifiers.get(flex.MOD) is not None and flex.LOCAL in o


def test_a_chain_running_round_in_a_loop_is_no_drag_chain_candidate():
    """Found by the panel's review: a tensioner's track or a roller chain (links in a closed loop) was offered by
    'Find hoses and chains'. A drag chain's links lie in an open row with two ends."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("link")
    me.from_pydata([(-0.01, -0.01, -0.01), (0.01, -0.01, -0.01), (0.01, 0.01, 0.01), (-0.01, 0.01, 0.01)], [],
                   [(0, 1, 2, 3)])

    def row(places):
        obs = []
        for p, turn in places:
            o = bpy.data.objects.new("link", me)
            o.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(turn, 4, "Z")
            bpy.context.scene.collection.objects.link(o)
            obs.append(o)
        bpy.context.view_layer.update()
        return obs

    loop = row([((math.cos(a), math.sin(a), 0.0), a) for a in (k * math.tau / 24 for k in range(24))])
    # a drag chain: 9 links on each run 0.16 apart, 5 round the bend between them
    u_shape = row([((0.04 * k, 0.0, 2.0), 0.0) for k in range(9)]
                  + [((0.32 + 0.08 * math.sin(a), 0.08 - 0.08 * math.cos(a), 2.0), a)
                     for a in (math.pi * k / 6 for k in range(1, 6))]
                  + [((0.04 * k, 0.16, 2.0), math.pi) for k in range(8, -1, -1)])
    assert not flex._open_row(loop)
    assert flex._open_row(u_shape)


def test_the_queue_copy_shows_and_renders_the_same_hoses(hoses, tmp_path):
    """The render queue's background Blender opens a copy of the project, builds the animation again and renders:
    the copy shows the same hoses at every frame, built again too, and a render sees the bent hose (not the stiff
    CAD part)."""
    from fresing_render.blender import cameras
    sc = hoses
    built(sc, (("Luff", 0.0, 2.0, math.radians(18)), ("Slide", 0.5, 1.5, 0.1)), "Queue")
    frames = (1, 20, 37, 51)

    def shapes(scene):
        out = []
        for f in frames:
            scene.frame_set(f)
            out.append(np.array([flex.shape_now(scene, it) for it in flex.items(scene)]))
        return np.array(out)

    want = shapes(sc)
    assert np.abs(want[0] - want[-1]).max() > 0.05                       # they do move
    path = str(tmp_path / "queue copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)                              # as the queue runner: open, build, render
    sc = bpy.context.scene
    assert np.array_equal(shapes(sc), want)                              # the saved shapes play the same
    r = animation.bake(sc, sc.fresing.animations["Queue"])
    assert not r["warnings"], r["warnings"]
    assert np.abs(shapes(sc) - want).max() < 1e-6                        # built again on the copy: the same

    sc.camera = cameras.add_camera(sc, "ISO", 50.0, "Queue view")
    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = 1, False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 96, 54, 100
    sc.render.image_settings.file_format = "PNG"
    sc.frame_set(51)

    def picture(name):
        sc.render.filepath = str(tmp_path / name)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath if sc.render.filepath.endswith(".png")
                                   else sc.render.filepath + ".png")
        px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
        bpy.data.images.remove(img)
        return px

    bent = picture("bent.png")
    again = picture("bent again.png")
    for it in flex.items(sc):
        it.enabled = False
    stiff = picture("stiff.png")
    noise = float(np.abs(bent - again).mean())
    assert float(np.abs(bent - stiff).mean()) > 5.0 * noise + 1e-4       # the render shows the hoses bent along
