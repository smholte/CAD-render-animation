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
    with pytest.raises(RuntimeError, match="axis joint 'X axis' itself"):        # carriage mixed with a cover: no
        waycover.add_section(scene, [ob(scene, "CARRIAGE"), ob(scene, "COVER.5")])


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



# ---------------------------------------------------------------------------
# task 0035: several covers, the carriage as the last section, 8 sections, old projects
# ---------------------------------------------------------------------------

TWO = os.path.join(HERE, "data", "test_waycover_c.step")       # a cover each side of the carriage (5 + 5 sections)


def make_tool_model(tmp_path, **kw):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mtw", os.path.join(HERE, "..", "tools", "make_test_waycover.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    path = str(tmp_path / "wc.step")
    m.build(path, **kw)
    return path


def bake_out_and_back(sc, total=0.5):
    a = sc.fresing.animations.add()
    a.fps = "25"
    for start, to in ((0, total), (2.5, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.use_from, b.to_dist, b.easing = (
            "JOINT", "X axis", start, 2, False, to, "LINEAR")
    return animation.bake(sc, a)


def two_covers(sc, carriage=False):
    """Axis X (0 … 500 mm) on the carriage; 'X left' and 'X right' with five sections each. ``carriage``: the
    sections next to the carriage are bolted to it (members of the axis) and become the carriage sections."""
    members = [ob(sc, "CARRIAGE")] + ([ob(sc, "COVER.L.5"), ob(sc, "COVER.R.5")] if carriage else [])
    j = joints.create(sc, "SLIDE", members, Vector((0.2, 0.15, 0.1)), Vector((1, 0, 0)), name="X axis")
    j.use_limits = True
    j.slide_min, j.slide_max = 0.0, 0.5
    for side in ("L", "R"):
        c = waycover.add_cover(sc, "X left" if side == "L" else "X right")
        c.axis = "X axis"
        assert waycover.read_total(sc) == ""
        for k in range(1, 6):
            waycover.add_section(sc, [ob(sc, f"COVER.{side}.{k}")])
        built, problems = waycover.make(sc)
        assert built == (4 if carriage else 5) and not problems, problems
    return [c for c in sc.fresing.waycovers]


def cover_x(sc, side):
    return [min_x(ob(sc, f"COVER.{side}.{k}")) for k in range(1, 6)]


def check_two_covers(sc, rest_l, rest_r):
    for a in (0.0, 0.13, 0.5, 0.31):
        axis_to(sc, a)
        for side, rest in (("L", rest_l), ("R", rest_r)):
            for k, (got, r) in enumerate(zip(cover_x(sc, side), rest), start=1):
                assert abs((got - r) - a * k / 5) < TOL, (side, k, a, got - r)


def test_two_covers_on_one_axis_build_without_warnings(tmp_path):
    sc = load(TWO, tmp_path)
    rest_l, rest_r = cover_x(sc, "L"), cover_x(sc, "R")
    cs = two_covers(sc)
    assert [c.name for c in cs] == ["X left", "X right"] and len(waycover.covers(sc)) == 2
    assert len([j for j in sc.fresing.joints if j.follows == "X axis"]) == 10
    check_two_covers(sc, rest_l, rest_r)
    # fully over: the left cover is open, the right one closed against the carriage (sections 20 mm apart)
    axis_to(sc, 0.5)
    r = cover_x(sc, "R")
    assert all(abs((r[k] - r[k + 1]) - 0.02) < TOL for k in range(4))
    assert abs(r[4] - (min_x(ob(sc, "CARRIAGE")) + 0.2)) < TOL
    res = bake_out_and_back(sc)
    assert not res["warnings"], res["warnings"]
    for f, a in ((1, 0.0), (26, 0.25), (51, 0.5), (114, 0.0)):
        sc.frame_set(f)
        update()
        for k, (got, rr) in enumerate(zip(cover_x(sc, "R"), rest_r), start=1):
            assert abs((got - rr) - a * k / 5) < 1e-4, (f, k)
    assert joints.couplings_simple(sc)
    for c in cs:
        assert waycover.status(sc, c) == "5 sections · 100 mm each · follows 'X axis'"


def test_a_part_belongs_to_one_cover_only(tmp_path):
    sc = load(TWO, tmp_path)
    two_covers(sc)
    c = waycover.add_cover(sc, "Extra")
    c.axis = "X axis"
    with pytest.raises(RuntimeError, match="already"):
        waycover.add_section(sc, [ob(sc, "COVER.L.2")])


def test_remove_one_cover_leaves_the_other_and_the_axis(tmp_path):
    sc = load(TWO, tmp_path)
    rest_l, rest_r = cover_x(sc, "L"), cover_x(sc, "R")
    two_covers(sc)
    sc.fresing.waycovers_index = 0
    assert waycover.remove_cover(sc) == 5
    assert [c.name for c in sc.fresing.waycovers] == ["X right"]
    assert sorted(j.name for j in sc.fresing.joints if not j.follows) == ["X axis"]
    axis_to(sc, 0.5)
    assert all(abs(g - r) < TOL for g, r in zip(cover_x(sc, "L"), rest_l))
    assert all(abs((g - r) - 0.1 * k) < TOL for k, (g, r) in enumerate(zip(cover_x(sc, "R"), rest_r), start=1))


def test_carriage_as_the_last_section(scene):
    rest = positions(scene)
    axis = joints.create(scene, "SLIDE", [ob(scene, "CARRIAGE"), ob(scene, "COVER.5")], Vector((0.1, 0.15, 0.1)),
                         Vector((1, 0, 0)), name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, 0.5
    c = waycover.ensure_cover(scene)
    c.axis, c.total = "X axis", 0.5
    with pytest.raises(RuntimeError, match="axis joint 'X axis' itself"):      # mixed: refused with the reason
        waycover.add_section(scene, [ob(scene, "COVER.5"), ob(scene, "COVER.4")])
    add_sections(scene, SECTIONS[:4])
    sec = waycover.add_section(scene, [ob(scene, "COVER.5")])
    assert sec.carriage and sec.name == "Section 5"
    n_joints = len(scene.fresing.joints)
    built, problems = waycover.make(scene)
    assert built == 4 and not problems, problems
    assert len(scene.fresing.joints) == n_joints + 4                          # no joint for the carriage section
    assert waycover.is_made(scene, waycover.settings(scene).sections[4])
    axis_to(scene, 0.5)
    for got, r, e in zip(positions(scene), rest, [100, 200, 300, 400, 500]):
        assert abs((got - r) - e / 1000) < TOL
    axis_to(scene, 0.2)
    for got, r, e in zip(positions(scene), rest, [40, 80, 120, 160, 200]):
        assert abs((got - r) - e / 1000) < TOL
    # the refusals: nothing after the carriage, the carriage stays last, one carriage section
    with pytest.raises(RuntimeError, match="must stay the last section"):
        waycover.add_section(scene, [ob(scene, "BASE")])
    with pytest.raises(RuntimeError, match="is the carriage already"):
        waycover.add_section(scene, [ob(scene, "CARRIAGE")])
    assert "stays the last section" in waycover.move_section(scene, 4, -1)
    assert "stays the last section" in waycover.move_section(scene, 3, 1)
    assert waycover.move_section(scene, 0, 1) == ""                            # the others still move
    # remove the cover: the axis and the carriage stay
    assert waycover.remove_cover(scene) == 5
    assert not len(scene.fresing.waycovers)
    ax = joints.find(scene, "X axis")
    assert ax is not None and len(joints.members(ax)) == 2
    axis_to(scene, 0.5)
    assert abs(min_x(ob(scene, "COVER.5")) - rest[4] - 0.5) < TOL
    assert abs(min_x(ob(scene, "COVER.4")) - rest[3]) < TOL


def test_carriage_section_removed_keeps_the_carriage(scene):
    axis = joints.create(scene, "SLIDE", [ob(scene, "CARRIAGE"), ob(scene, "COVER.5")], Vector((0.1, 0.15, 0.1)),
                         Vector((1, 0, 0)), name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, 0.5
    c = waycover.ensure_cover(scene)
    c.axis, c.total = "X axis", 0.5
    add_sections(scene, SECTIONS[:3])
    waycover.add_section(scene, [ob(scene, "COVER.5")])
    waycover.make(scene)
    assert c.sections[3].carriage
    waycover.remove_section(scene, 1)
    assert c.sections[2].carriage and not any(x.carriage for x in list(c.sections)[:2])
    waycover.remove_section(scene, 2)
    assert len(joints.members(joints.find(scene, "X axis"))) == 2


def test_eight_sections(tmp_path):
    sc = load(make_tool_model(tmp_path, sections=8), tmp_path)
    names = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"]] + \
        [[f"COVER.{k}"] for k in range(4, 9)]
    rest = [min_x(ob(sc, g[0])) for g in names]
    make_axis(sc)
    c = waycover.settings(sc)
    c.total = 0.5
    add_sections(sc, names)
    built, problems = waycover.make(sc)
    assert built == 8 and not problems, problems
    assert waycover.status(sc) == "8 sections · 62.5 mm each · follows 'X axis'"
    for a in (0.5, 0.37, 0.1, 0.0):
        axis_to(sc, a)
        for k, (g, r) in enumerate(zip([min_x(ob(sc, n[0])) for n in names], rest), start=1):
            assert abs((g - r) - a * k / 8) < TOL, (a, k)
    res = bake_out_and_back(sc)
    assert not res["warnings"], res["warnings"]


def test_old_one_cover_project_opens_as_the_first_cover(scene, tmp_path):
    """A project saved before task 0035 keeps its cover in ``scene.fresing.waycover``: it opens as the first item of
    the list, with the same joints, ratios, limits and motion."""
    rest = positions(scene)
    set_up(scene)                                   # no list yet: written to the single cover, as 0.2.28 … did
    assert not len(scene.fresing.waycovers) and scene.fresing.waycover.axis == "X axis"
    before = {j.name: (j.follows, round(j.couple_ratio, 6), j.use_limits, round(j.slide_min, 6),
                       round(j.slide_max, 6)) for j in scene.fresing.joints}
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert len(sc.fresing.waycovers) == 1 and not sc.fresing.waycover.axis and not len(sc.fresing.waycover.sections)
    c = sc.fresing.waycovers[0]
    assert c.axis == "X axis" and abs(c.total - 0.5) < 1e-6 and len(c.sections) == 5
    after = {j.name: (j.follows, round(j.couple_ratio, 6), j.use_limits, round(j.slide_min, 6),
                      round(j.slide_max, 6)) for j in sc.fresing.joints}
    assert after == before
    axis_to(sc, 0.5)
    for k, (got, r) in enumerate(zip(positions(sc), rest), start=1):
        assert abs((got - r) - 0.1 * k) < TOL
    res = bake_out_and_back(sc)
    assert not res["warnings"], res["warnings"]
    c2 = waycover.add_cover(sc)                      # and more covers can be added next to it
    assert c2.name == "Way cover 2" and len(waycover.covers(sc)) == 2


def test_two_covers_with_carriage_survive_save_and_model_update(tmp_path):
    sc = load(TWO, tmp_path)
    rest_l, rest_r = cover_x(sc, "L"), cover_x(sc, "R")
    two_covers(sc, carriage=True)
    path = str(tmp_path / "two.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert [c.name for c in sc.fresing.waycovers] == ["X left", "X right"]
    assert all(waycover.is_made(sc, s) for c in waycover.covers(sc) for s in c.sections)
    check_two_covers(sc, rest_l, rest_r)
    axis_to(sc, 0.2)
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=TWO, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert not [n.text for n in sc.fresing.report_notes if "Way cover" in n.text]
    cs = waycover.covers(sc)
    assert len(cs) == 2 and all(waycover.is_made(sc, s) for c in cs for s in c.sections)
    assert all(c.sections[4].carriage for c in cs)
    check_two_covers(sc, rest_l, rest_r)
    res = bake_out_and_back(sc)
    assert not res["warnings"], res["warnings"]


def test_panel_draws_with_several_covers(tmp_path):
    import sys
    sys.path.insert(0, HERE)
    from test_blender import FakeLayout
    from fresing_render.blender import ui_waycover
    errors = []
    sc = load(TWO, tmp_path)

    def draw_all():
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        for extra in ("draw", "draw_header", "draw_header_preset"):
            getattr(ui_waycover.FRESING_PT_waycover, extra)(fake, bpy.context)
    draw_all()                                       # empty: the steps and 'Add way cover'
    two_covers(sc, carriage=True)
    draw_all()
    assert not errors, errors


# ---------------------------------------------------------------------------
# task 0090: the cover drawn at any axis position
# ---------------------------------------------------------------------------

DRAWN = os.path.join(HERE, "data", "test_waycover_d.step")     # make_test_waycover.py --drawn-at 250
MID = 0.25


def test_drawn_at_mid_travel_builds_clean_and_fits_at_the_drawn_position(tmp_path):
    sc = load(DRAWN, tmp_path)
    cad = positions(sc)
    make_axis(sc)
    c = waycover.settings(sc)
    c.total = 0.5
    c.drawn_at = MID
    add_sections(sc)
    built, problems = waycover.make(sc)
    assert built == 5 and not problems, problems
    assert waycover.check_line(sc, c).startswith("At 0 mm: section 1 … 5 at -50 / -100 / -150 / -200 / -250 mm")
    for a in (0.0, 0.1, MID, 0.4, 0.5):
        axis_to(sc, a)
        for k, (got, r) in enumerate(zip(positions(sc), cad), start=1):
            assert abs((got - r) - (a - MID) * k / 5) < TOL, (a, k, got - r)
    axis_to(sc, MID)                                       # at "Drawn at" every section is on its CAD place
    assert all(abs(g - r) < 1e-5 for g, r in zip(positions(sc), cad))
    res = bake_out_and_back(sc)
    assert not res["warnings"], res["warnings"]
    assert joints.couplings_simple(sc)
    # the setting changes at once, and Read takes the axis' value
    c.drawn_at = 0.0
    update()
    axis_to(sc, 0.5)
    assert all(abs((g - r) - 0.1 * k) < TOL for k, (g, r) in enumerate(zip(positions(sc), cad), start=1))
    axis_to(sc, MID)
    assert waycover.read_drawn(sc) == "" and abs(c.drawn_at - MID) < 1e-6
    # save + reopen + model update keep it
    path = str(tmp_path / "drawn.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert abs(waycover.settings(sc).drawn_at - MID) < 1e-6
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=DRAWN, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert abs(waycover.settings(sc).drawn_at - MID) < 1e-6
    axis_to(sc, 0.5)
    for k, (g, r) in enumerate(zip(positions(sc), cad), start=1):
        assert abs((g - r) - (0.5 - MID) * k / 5) < TOL


def test_drawn_at_outside_the_limits_warns(scene):
    c = set_up(scene)
    c.drawn_at = 0.8
    assert "Warning" in waycover.check_line(scene, c)
    c.drawn_at = 0.1
    assert "Warning" not in waycover.check_line(scene, c)


def test_covers_have_their_own_drawn_at(tmp_path):
    sc = load(TWO, tmp_path)
    rest_l, rest_r = cover_x(sc, "L"), cover_x(sc, "R")
    cs = two_covers(sc)
    cs[0].drawn_at = 0.1
    cs[1].drawn_at = 0.0
    update()
    for a in (0.0, 0.3, 0.5):
        axis_to(sc, a)
        for k, (g, r) in enumerate(zip(cover_x(sc, "L"), rest_l), start=1):
            assert abs((g - r) - (a - 0.1) * k / 5) < TOL
        for k, (g, r) in enumerate(zip(cover_x(sc, "R"), rest_r), start=1):
            assert abs((g - r) - a * k / 5) < TOL


def test_old_project_has_drawn_at_zero(scene, tmp_path):
    set_up(scene)
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert waycover.settings(sc).drawn_at == 0.0
    assert all(abs(j.couple_offset_dist) < 1e-9 for j in sc.fresing.joints if j.follows)
