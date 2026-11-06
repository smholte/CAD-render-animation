"""Task 0034: way covers (telescopic covers follow one slide axis), against hand calculations.

Generic model (tools/make_test_waycover.py): bed, carriage and five cover sections 20 mm thick, nested at
x = 0, 20 … 80 mm (sections 1 and 3 are two parts each). Axis 500 mm, 5 moving sections: section k stands
100 k mm from where it is in CAD. The owner's way-cover STEP (test_waycover_a.step, five sections, in the middle
of its travel: 376.5 mm long, 166.5 mm closed, 586.5 mm open) is set up with the housing counting as a section.
"""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, waycover  # noqa: E402
from fresing_render.core import waycover as core  # noqa: E402

HERE = os.path.dirname(__file__)
GENERIC = os.path.join(HERE, "data", "test_waycover_b.step")
OWNER = os.path.join(HERE, "data", "test_waycover_a.step")
TOL = 2e-5                    # 0.02 mm (Blender keeps positions in single precision)
SECTIONS = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
            ["COVER.5"]]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def load(path, tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture()
def scene(tmp_path):
    return load(GENERIC, tmp_path)


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME, "").split(" v")[0] == name or
                o.get(build.PROP_NAME) == name)


def min_x(o):
    return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)


def min_z(o):
    return min((o.matrix_world @ Vector(c)).z for c in o.bound_box)


def make_axis(sc, total=0.5):
    carriage = ob(sc, "CARRIAGE")
    j = joints.create(sc, "SLIDE", [carriage], Vector((0.1, 0.15, 0.1)), Vector((1, 0, 0)), name="X axis")
    j.use_limits = True
    j.slide_min, j.slide_max = 0.0, total
    waycover.settings(sc).axis = "X axis"
    return j


def add_sections(sc, groups=SECTIONS):
    for g in groups:
        waycover.add_section(sc, [ob(sc, n) for n in g])


def axis_to(sc, value):
    joints.set_value(joints.find(sc, "X axis"), value)
    update()


def set_up(sc, n=5, total=0.5, housing=False):
    make_axis(sc, total)
    c = waycover.settings(sc)
    c.total = total
    c.housing_counts = housing
    add_sections(sc, SECTIONS[:n])
    built, problems = waycover.make(sc)
    assert built == n and not problems, problems
    return c


def positions(sc, n=5):
    return [min_x(ob(sc, SECTIONS[k][0])) for k in range(n)]


# ---------------------------------------------------------------------------
# the numbers (no Blender needed, but fast to check here too)
# ---------------------------------------------------------------------------

def test_shares_core():
    assert core.positions_mm(500, 5) == pytest.approx([100, 200, 300, 400, 500])
    assert core.positions_mm(500, 5, housing_counts=True) == pytest.approx([0, 125, 250, 375, 500])
    assert core.positions_mm(500, 3) == pytest.approx([500 / 3, 1000 / 3, 500])
    assert core.positions_mm(500, 8)[:2] == pytest.approx([62.5, 125.0])
    assert core.positions_mm(500, 8)[-1] == pytest.approx(500)
    assert core.positions_mm(500, 5, flip=True) == pytest.approx([-100, -200, -300, -400, -500])
    assert core.shares(1) == [1.0] and core.shares(1, True) == [0.0] and core.shares(0) == []
    assert core.travel_each(500, 5) == 100 and core.travel_each(420, 5, True) == 105
    assert "5 sections × 100 mm" in core.summary(5, 500)
    assert "0, 125, 250, 375, 500" in core.summary(5, 500, True)


# ---------------------------------------------------------------------------
# the owner's example: 500 mm over 5 sections = 100 mm each
# ---------------------------------------------------------------------------

def test_five_sections_over_500_mm(scene):
    rest = positions(scene)
    set_up(scene)
    for a, expect in ((0.5, [100, 200, 300, 400, 500]), (0.25, [50, 100, 150, 200, 250]), (0.0, [0] * 5)):
        axis_to(scene, a)
        for got, r, e in zip(positions(scene), rest, expect):
            assert abs((got - r) - e / 1000) < TOL, (a, got - r, e)
    # the axis moves the carriage by itself as before
    c0 = min_x(ob(scene, "CARRIAGE"))
    axis_to(scene, 0.5)
    assert abs(min_x(ob(scene, "CARRIAGE")) - c0 - 0.5) < TOL


def test_housing_counts_gives_125_mm_steps(scene):
    rest = positions(scene)
    c = set_up(scene, housing=True)
    axis_to(scene, 0.5)
    for got, r, e in zip(positions(scene), rest, [0, 125, 250, 375, 500]):
        assert abs((got - r) - e / 1000) < TOL
    c.housing_counts = False                       # a switch re-shares at once, nothing left behind
    update()
    for got, r, e in zip(positions(scene), rest, [100, 200, 300, 400, 500]):
        assert abs((got - r) - e / 1000) < TOL
    assert len([j for j in scene.fresing.joints if j.follows]) == 5


@pytest.mark.parametrize("n", [3, 4])
def test_other_numbers_of_sections(scene, n):
    rest = positions(scene, n)
    set_up(scene, n=n)
    axis_to(scene, 0.5)
    for k, (got, r) in enumerate(zip(positions(scene, n), rest), start=1):
        assert abs((got - r) - 0.5 * k / n) < TOL


def test_adding_and_removing_sections_and_travel_update_shares(scene):
    rest = positions(scene)
    c = set_up(scene, n=4)
    axis_to(scene, 0.4)
    assert abs(positions(scene, 4)[0] - rest[0] - 0.1) < TOL
    waycover.add_section(scene, [ob(scene, "COVER.5")])         # a fifth section: 5 shares now
    built, problems = waycover.make(scene)
    assert built == 1 and not problems
    update()
    assert abs(positions(scene, 5)[0] - rest[0] - 0.08) < TOL and abs(positions(scene, 5)[4] - rest[4] - 0.4) < TOL
    waycover.remove_section(scene, 1)                             # take section 2 out: 4 shares
    update()
    assert abs(min_x(ob(scene, "COVER.2")) - rest[1]) < TOL      # its part is back in CAD
    assert abs(min_x(ob(scene, "COVER.1.PLATE")) - rest[0] - 0.1) < TOL
    waycover.move_section(scene, 0, 1)                            # order decides the share
    update()
    assert abs(min_x(ob(scene, "COVER.1.PLATE")) - rest[0] - 0.2) < TOL
    c.flip = True
    update()
    assert abs(min_x(ob(scene, "COVER.1.PLATE")) - rest[0] + 0.2) < TOL
    followers = [j for j in scene.fresing.joints if j.follows]
    assert len(followers) == 4 and len(c.sections) == 4


def test_section_of_several_parts_moves_as_one(scene):
    set_up(scene)
    axis_to(scene, 0.5)
    d1 = min_x(ob(scene, "COVER.1.PLATE")) - min_x(ob(scene, "COVER.1.FLANGE"))
    assert abs(d1) < TOL                       # both start at x = 0 and stay together
    j = waycover.section_joint(scene, waycover.settings(scene).sections[0])
    assert len(joints.members(j)) == 2


def test_two_sections_cannot_share_a_part_and_followers_are_refused(scene):
    make_axis(scene)
    add_sections(scene, SECTIONS[:2])
    with pytest.raises(RuntimeError, match="section 'Section 1' already"):
        waycover.add_section(scene, [ob(scene, "COVER.1.PLATE"), ob(scene, "COVER.3.PLATE")])
    assert len(waycover.settings(scene).sections) == 2
    waycover.make(scene)
    with pytest.raises(RuntimeError, match="already"):
        waycover.add_section(scene, [ob(scene, "COVER.2")])
    # a part that already follows something is refused with the reason
    other = joints.create(scene, "SLIDE", [ob(scene, "COVER.4")], Vector((0, 0, 0)), Vector((1, 0, 0)), name="Other")
    joints.set_follows(scene, other, "X axis", ratio=0.3)
    with pytest.raises(RuntimeError, match="follows 'X axis'"):
        waycover.add_section(scene, [ob(scene, "COVER.4")])
    with pytest.raises(RuntimeError, match="carriage|axis joint"):
        waycover.add_section(scene, [ob(scene, "CARRIAGE")])


def test_axis_must_be_a_slide_joint(scene):
    carriage = ob(scene, "CARRIAGE")
    joints.create(scene, "ROTATE", [carriage], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Turn")
    c = waycover.settings(scene)
    assert "Pick the axis" in waycover.axis_problem(scene)
    c.axis = "Turn"
    assert "slides" in waycover.axis_problem(scene)
    add_sections(scene, SECTIONS[:1])
    with pytest.raises(RuntimeError, match="slides"):
        waycover.make(scene)


# ---------------------------------------------------------------------------
# the wiring: scripts off, animation, save, update, removal
# ---------------------------------------------------------------------------

def test_couplings_are_simple_expressions(scene):
    set_up(scene)
    assert joints.couplings_simple(scene)
    for sec in waycover.settings(scene).sections:
        j = waycover.section_joint(scene, sec)
        assert j.follows == "X axis" and j.use_limits
    assert abs(waycover.section_joint(scene, waycover.settings(scene).sections[2]).couple_ratio - 0.6) < 1e-6


def test_animation_move_joint_step_moves_the_covers(scene):
    rest = positions(scene)
    set_up(scene)
    a = scene.fresing.animations.add()
    a.fps = "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from, b.to_dist, b.easing = "JOINT", "X axis", 0, 2, False, 0.5, "LINEAR"
    animation.bake(scene, a)
    for f, axis in ((1, 0.0), (26, 0.25), (51, 0.5)):
        scene.frame_set(f)
        for k, (got, r) in enumerate(zip(positions(scene), rest), start=1):
            assert abs((got - r) - axis * k / 5) < 1e-4, (f, k)


def test_save_and_reopen(scene, tmp_path):
    rest = positions(scene)
    set_up(scene)
    axis_to(scene, 0.3)
    path = str(tmp_path / "cover.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    c = waycover.settings(sc)
    assert c.axis == "X axis" and len(c.sections) == 5 and all(waycover.is_made(sc, s) for s in c.sections)
    assert waycover.status(sc) == "5 sections · 100 mm each · follows 'X axis'"
    axis_to(sc, 0.5)
    for k, (got, r) in enumerate(zip(positions(sc), rest), start=1):
        assert abs((got - r) - 0.1 * k) < TOL


def test_rename_of_the_axis_and_of_a_section_joint(scene):
    set_up(scene)
    c = waycover.settings(scene)
    j = joints.find(scene, "X axis")
    j.name = "Y axis"
    update()
    assert c.axis == "Y axis"
    sj = waycover.section_joint(scene, c.sections[1])
    old = sj.name
    sj.name = "Cover two"
    update()
    assert c.sections[1].joint == "Cover two" and old != "Cover two"
    assert waycover.is_made(scene, c.sections[1])


def test_model_update_keeps_the_way_cover(scene):
    rest = positions(scene)
    set_up(scene)
    axis_to(scene, 0.2)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=GENERIC, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    c = waycover.settings(scene)
    assert len(c.sections) == 5 and all(waycover.is_made(scene, s) for s in c.sections)
    assert not [n.text for n in scene.fresing.report_notes if "Way cover" in n.text]
    axis_to(scene, 0.5)
    for k, (got, r) in enumerate(zip(positions(scene), rest), start=1):
        assert abs((got - r) - 0.1 * k) < TOL
    assert joints.couplings_simple(scene)


def test_remove_the_way_cover_leaves_the_axis_as_before(scene):
    rest = positions(scene)
    make_axis(scene)
    before = sorted(j.name for j in scene.fresing.joints)
    c = waycover.settings(scene)
    c.total = 0.5
    add_sections(scene)
    waycover.make(scene)
    assert len(scene.fresing.joints) == 6
    assert waycover.remove_all(scene) == 5
    update()
    assert sorted(j.name for j in scene.fresing.joints) == before
    assert not len(c.sections)
    axis_to(scene, 0.5)
    assert all(abs(g - r) < TOL for g, r in zip(positions(scene), rest))
    assert abs(min_x(ob(scene, "CARRIAGE")) - min_x(ob(scene, "BASE")) - 0.06 - 0.5) < TOL


def test_read_total_from_the_axis_limits(scene):
    make_axis(scene, total=0.42)
    assert waycover.read_total(scene) == ""
    assert abs(waycover.settings(scene).total - 0.42) < 1e-6
    joints.find(scene, "X axis").use_limits = False
    assert "no limits" in waycover.read_total(scene)


# ---------------------------------------------------------------------------
# the owner's model
# ---------------------------------------------------------------------------

def test_owner_model_housing_counts_420_mm(tmp_path):
    sc = load(OWNER, tmp_path)
    plate = ob(sc, "Mounting plate")
    j = joints.create(sc, "SLIDE", [], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Axis", base=plate,
                      allow_empty=True)
    j.use_limits = True
    j.slide_min, j.slide_max = -0.21, 0.21                  # 166.5 mm closed … 586.5 mm open, CAD pose in the middle
    c = waycover.settings(sc)
    c.axis, c.housing_counts = "Axis", True
    assert waycover.read_total(sc) == "" and abs(c.total - 0.42) < 1e-6
    for k in range(1, 6):
        waycover.add_section(sc, [ob(sc, f"Section {k}")])
    built, problems = waycover.make(sc)
    assert built == 5 and not problems, problems
    assert waycover.status(sc) == "5 sections · 105 mm each · follows 'Axis'"
    start = [62.5 * (k - 1) / 1000 for k in range(1, 6)]
    for axis, in_mm in ((-0.21, 10), (0.0, 62.5), (0.21, 115)):
        joints.set_value(joints.find(sc, "Axis"), axis)
        update()
        z = [min_z(ob(sc, f"Section {k}")) for k in range(1, 6)]
        for k in range(1, 5):                              # gap between neighbouring sections
            assert abs((z[k] - z[k - 1]) - in_mm / 1000) < TOL, (axis, k)
        assert abs(z[0] - start[0]) < TOL                  # the housing never moves
    assert joints.couplings_simple(sc)
