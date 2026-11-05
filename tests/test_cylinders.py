"""Task 0013: hydraulic / electric cylinders on the generic test luffer (tools/make_test_cylinder.py).

Hand calculation (metres, pins along Y): arm pivot P = (0.1, y, 0.6), barrel pin B = (0.5, y, 0.15), rod pin
R0 = (0.8, y, 0.45) in the CAD pose. The arm joint turns about +Y through P, so with the arm at angle a the
rod pin is at R(a) = P + RotY(a) (R0 - P). Cylinders: pin to pin 0.42426 in the CAD pose, closed length
0.36426 (the piston can go 60 mm back), full stroke 0.190 (130 mm out to the gland).
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
LUFFER_A = os.path.join(HERE, "data", "test_cylinder_a.step")
LUFFER_B = os.path.join(HERE, "data", "test_cylinder_b.step")
Y = Vector((0, 1, 0))
P0 = Vector((0.1, 0.0, 0.6))
B0 = Vector((0.5, 0.0, 0.15))
R00 = Vector((0.8, 0.0, 0.45))
L0 = math.hypot(0.3, 0.3)
CLOSED, FULL = L0 - 0.060, 0.190
EYE_TOL = 1e-5                 # 0.01 mm: the eyes stay on their pins
TOL = 1e-5

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, cylinders, joints, states  # noqa: E402


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
    assert bpy.ops.fresing.import_step(filepath=LUFFER_A, quality="draft") == {"FINISHED"}
    return sc


def update():
    bpy.context.view_layer.update()


def obs(sc, name):
    """Objects with this CAD name, from low Y to high Y (the two cylinders side by side: y = 0.08, 0.32)."""
    return sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name),
                  key=lambda o: (o.matrix_world @ Vector(o.bound_box[0])).y if o.type == "MESH"
                  else o.matrix_world.translation.y)


def first_of(sc, name, y):
    """The object with this name in the cylinder at ``y`` (its parts' world box spans that y)."""
    for o in sc.objects:
        if o.get(build.PROP_NAME) != name:
            continue
        parts = [o] if o.type == "MESH" else [d for d in o.children_recursive if d.type == "MESH"]
        ys = [(d.matrix_world @ Vector(c)).y for d in parts for c in d.bound_box]
        if min(ys) - 1e-4 <= y <= max(ys) + 1e-4:
            return o
    raise KeyError(name)


def at(v, y):
    return Vector((v.x, y, v.z))


def rod_pin(angle, y):
    """Hand calculation: where the arm carries the rod pin."""
    return at(P0, y) + Matrix.Rotation(angle, 3, "Y") @ (at(R00, y) - at(P0, y))


def arm(sc):
    return joints.create(sc, "ROTATE", obs(sc, "ARM.ASM"), at(P0, 0.2), Y, name="Luff")


def make(sc, y=0.08, refs=None, name=""):
    """A cylinder at ``y``: the clicks on BASE.PIN and ARM.ROD.PIN (the pins themselves)."""
    rb, rr = refs or (obs(sc, "BASE.PIN")[0], obs(sc, "ARM.ROD.PIN")[0])
    c, notes = cylinders.create(sc, [first_of(sc, "CYL.BARREL", y)], [first_of(sc, "CYL.ROD", y)],
                                (at(B0, 0.0), Y, rb), (at(R00, 0.4), -Y, rr), name=name)
    update()
    return c, notes


def local_point(ob, world):
    """``world`` (CAD pose) in ``ob``'s own coordinates: follows the part wherever it goes."""
    return ob.matrix_world.inverted() @ world


def solve_angle(length, y=0.08):
    """Independent of the app's formula: bisection on the hand-calculated geometry, on the CAD side."""
    lo, hi = math.radians(-60), math.radians(40)          # the cylinder gets shorter as the angle grows
    f = (lambda a: (rod_pin(a, y) - at(B0, y)).length - length)
    assert f(lo) > 0 > f(hi)
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return lo


def check_eyes(sc, c, angle, y=0.08, eyes=None):
    """Both eyes on their pins, the rod on the barrel's line."""
    eye, cap, rod_pt, tube_pt = eyes
    r = rod_pin(angle, y)
    b = at(B0, y)
    u = (r - b).normalized()
    assert (eye[0].matrix_world @ eye[1] - r).length < EYE_TOL
    assert (cap[0].matrix_world @ cap[1] - b).length < EYE_TOL
    # a point on the rod 0.2 m behind its eye and one on the tube 0.15 m in front of the barrel pin
    assert (rod_pt[0].matrix_world @ rod_pt[1] - (r - u * 0.2)).length < EYE_TOL
    assert (tube_pt[0].matrix_world @ tube_pt[1] - (b + u * 0.15)).length < EYE_TOL
    assert cylinders.length_now(c) == pytest.approx((r - b).length, abs=EYE_TOL)


def eye_points(sc, y=0.08):
    """In the CAD pose: the rod eye's and the end cap's eye centres, a rod point and a tube point."""
    b, r = at(B0, y), at(R00, y)
    u = (r - b).normalized()
    eye = first_of(sc, "ROD.EYE", y)
    cap = first_of(sc, "BARREL.CAP", y)
    rod = first_of(sc, "ROD", y)
    tube = first_of(sc, "BARREL.TUBE", y)
    return ((eye, local_point(eye, r)), (cap, local_point(cap, b)), (rod, local_point(rod, r - u * 0.2)),
            (tube, local_point(tube, b + u * 0.15)))


def set_arm(sc, j, deg):
    joints.set_value(j, math.radians(deg), use_limits=False)
    update()


# ---------------------------------------------------------------------------------------------------------
# follow mode
# ---------------------------------------------------------------------------------------------------------

def test_follow_mode_eyes_stay_on_their_pins(scene):
    pts = eye_points(scene)
    j = arm(scene)
    c, notes = make(scene)
    assert notes == []
    assert c.frame.parent.get(build.PROP_NAME) == "BASE.PIN" and c.pin.parent.get(build.PROP_NAME) == "ARM.ROD.PIN"
    assert cylinders.length_cad(c) == pytest.approx(L0, abs=TOL)
    for deg in (-25, -10, 0, 7.5, 20, 40):
        set_arm(scene, j, deg)
        check_eyes(scene, c, math.radians(deg), eyes=pts)
        r = rod_pin(math.radians(deg), 0.08)
        assert cylinders.stroke_now(scene, c) == pytest.approx((r - at(B0, 0.08)).length - c.closed_length,
                                                               abs=EYE_TOL)


def test_travel_read_from_the_parts(scene):
    c, _notes = make(scene)
    assert c.measured
    assert c.closed_length == pytest.approx(CLOSED, abs=2e-4)       # (draft meshes: flat faces are exact)
    assert c.full_stroke == pytest.approx(FULL, abs=2e-4)


def test_two_cylinders_side_by_side(scene):
    near, far = eye_points(scene, 0.08), eye_points(scene, 0.32)
    j = arm(scene)
    c1, _ = make(scene, 0.08)
    c2, _ = make(scene, 0.32)
    assert [c.name for c in scene.fresing.cylinders] == ["CYL.BARREL cylinder", "CYL.BARREL cylinder 2"]
    for deg in (-15, 0, 25):
        set_arm(scene, j, deg)
        check_eyes(scene, c1, math.radians(deg), 0.08, near)
        check_eyes(scene, cylinders.find(scene, "CYL.BARREL cylinder 2"), math.radians(deg), 0.32, far)


def test_pins_found_when_the_cylinders_own_eyes_are_clicked(scene):
    """A click on the barrel's or rod's own eye: the pin sits in a part around it that is not the cylinder
    (the biggest one with a hole or shaft on that axis)."""
    j = arm(scene)
    c, _notes = cylinders.create(scene, [first_of(scene, "CYL.BARREL", 0.08)], [first_of(scene, "CYL.ROD", 0.08)],
                                 (at(B0, 0.09), Y, first_of(scene, "BARREL.CAP", 0.08)),
                                 (at(R00, 0.07), Y, first_of(scene, "ROD.EYE", 0.08)))
    update()
    assert c.frame.parent.get(build.PROP_NAME) == "BASE.BRACKET"
    assert c.pin.parent.get(build.PROP_NAME) == "ARM.BRACKET"
    pts = eye_points(scene)
    set_arm(scene, j, 15)
    check_eyes(scene, c, math.radians(15), eyes=pts)


def test_follows_when_the_whole_machine_turns(scene):
    """The whole machine turned 30° about Z (the cylinders no longer in an XZ plane): still exact in 3D."""
    luff = arm(scene)
    c, _ = make(scene)
    pts = eye_points(scene)
    root = build.model_roots(scene)[0]
    turn = Matrix.Translation((0.6, 0.2, 0.0)) @ Matrix.Rotation(math.radians(30), 4, "Z") @ \
        Matrix.Translation((-0.6, -0.2, 0.0))
    root.matrix_basis = turn @ root.matrix_basis
    set_arm(scene, luff, 20)
    eye, cap = pts[0], pts[1]
    assert (eye[0].matrix_world @ eye[1] - turn @ rod_pin(math.radians(20), 0.08)).length < EYE_TOL
    assert (cap[0].matrix_world @ cap[1] - turn @ at(B0, 0.08)).length < EYE_TOL
    assert cylinders.arm_joint(scene, c)[0].name == "Luff"


def test_refused_set_ups(scene):
    arm(scene)
    barrel, rod = first_of(scene, "CYL.BARREL", 0.08), first_of(scene, "CYL.ROD", 0.08)
    pins = ((at(B0, 0), Y, obs(scene, "BASE.PIN")[0]), (at(R00, 0), Y, obs(scene, "ARM.ROD.PIN")[0]))
    with pytest.raises(RuntimeError, match="as barrel and as rod"):
        cylinders.create(scene, [barrel], [barrel], *pins)
    cyl_asm = first_of(scene, "CYL.ASM", 0.08)
    with pytest.raises(RuntimeError, match="is inside"):
        cylinders.create(scene, [cyl_asm], [rod], *pins)
    with pytest.raises(RuntimeError, match="moves with joint"):
        cylinders.create(scene, [barrel], obs(scene, "ARM.ASM"), *pins)
    with pytest.raises(RuntimeError, match="same place"):
        cylinders.create(scene, [barrel], [rod], pins[0], pins[0])
    c, _ = cylinders.create(scene, [barrel], [rod], *pins)
    # a joint cannot take a cylinder's part: the cylinder moves it
    with pytest.raises(RuntimeError, match="part of cylinder"):
        joints.create(scene, "ROTATE", [rod], at(R00, 0.08), Y)
    with pytest.raises(RuntimeError, match="already part of cylinder"):
        cylinders.create(scene, [barrel], [first_of(scene, "CYL.ROD", 0.32)], *pins)


def test_nothing_moves_it_yet(scene):
    c, notes = make(scene)
    assert any("Nothing moves it yet" in n for n in notes)
    j, reason = cylinders.arm_joint(scene, c)
    assert j is None and "add a joint for the arm" in reason
    with pytest.raises(RuntimeError):
        cylinders.set_mode(scene, c, "DRIVE")


# ---------------------------------------------------------------------------------------------------------
# drive mode
# ---------------------------------------------------------------------------------------------------------

def law_of_cosines_angle(length, y=0.08):
    """The arm angle for a pin-to-pin length, written out by hand: the angle at the pivot between the barrel
    pin and the rod pin follows from the three sides; the arm turns by the change of that angle. Turning
    about +Y lowers the arm (the angle at the pivot gets smaller, the cylinder shorter)."""
    a = (at(B0, y) - at(P0, y)).length
    c = (at(R00, y) - at(P0, y)).length
    gamma0 = math.acos((a * a + c * c - L0 * L0) / (2 * a * c))
    gamma = math.acos((a * a + c * c - length * length) / (2 * a * c))
    return gamma0 - gamma


def test_drive_mode_stroke_to_arm_angle_by_hand(scene):
    pts = eye_points(scene)
    j = arm(scene)
    c, _ = make(scene)
    msg = cylinders.set_mode(scene, c, "DRIVE")
    assert c.mode == "DRIVE" and "Luff" in msg
    # the arm's limits become the cylinder's: fully out (longest) is the lowest angle
    assert j.use_limits
    assert j.rot_min == pytest.approx(law_of_cosines_angle(CLOSED + FULL), abs=2e-5)
    assert j.rot_max == pytest.approx(law_of_cosines_angle(CLOSED), abs=2e-5)
    for stroke in (0.0, 0.03, 0.06, 0.1, 0.19):
        got = cylinders.set_stroke(scene, c, stroke)
        angle = joints.get_value(j)
        assert angle == pytest.approx(law_of_cosines_angle(c.closed_length + stroke), abs=1e-6)
        assert angle == pytest.approx(solve_angle(c.closed_length + stroke), abs=1e-6)
        assert got == pytest.approx(stroke, abs=TOL)
        assert c.stroke == pytest.approx(stroke, abs=TOL)            # the panel's field reads it back
        check_eyes(scene, c, angle, eyes=pts)
    c.stroke = 0.05                                                    # the panel's field sets it
    update()
    assert joints.get_value(j) == pytest.approx(law_of_cosines_angle(c.closed_length + 0.05), abs=1e-6)
    cylinders.set_stroke(scene, c, 0.5)                                # beyond the stroke: stops at the limit
    assert cylinders.stroke_now(scene, c) == pytest.approx(FULL, abs=2e-4)


def test_drive_mode_needs_the_arm_on_the_pins_direction(scene):
    j = joints.create(scene, "ROTATE", obs(scene, "ARM.ASM"), at(P0, 0.2), Vector((0, 0, 1)), name="Wrong")
    c, _ = make(scene)
    jj, reason = cylinders.arm_joint(scene, c)
    assert jj is None and "does not turn about the pins' direction" in reason
    assert j is not None


def test_drive_mode_with_a_slide(scene):
    """A cylinder pushing a carriage: the arm is a slide joint along X here (the rod pin moves along X)."""
    pts = eye_points(scene)
    j = joints.create(scene, "SLIDE", obs(scene, "ARM.ASM"), at(P0, 0.2), Vector((1, 0, 0)), name="Carriage")
    c, _ = make(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    for stroke in (0.0, 0.08, 0.19):
        cylinders.set_stroke(scene, c, stroke)
        t = joints.get_value(j)
        r = at(R00, 0.08) + Vector((t, 0, 0))
        assert (r - at(B0, 0.08)).length == pytest.approx(c.closed_length + stroke, abs=TOL)
        eye = pts[0]
        assert (eye[0].matrix_world @ eye[1] - r).length < EYE_TOL


def test_move_cylinder_animation_step(scene):
    """Stroke 0 -> full stroke at constant speed: on every frame the rod is out by its share of the way, and the
    arm's angle is the hand-calculated one for that stroke (not a straight line between the two angles)."""
    j = arm(scene)
    c, _ = make(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    s = scene.fresing
    anim = s.animations.add()
    anim.name = "Lift"
    anim.fps = "25"
    anim.tail = 0.0
    b = anim.blocks.add()
    b.kind, b.cylinder, b.use_from, b.from_stroke, b.to_stroke = "CYLINDER", c.name, False, 0.0, FULL
    b.start, b.duration, b.easing = 0.0, 2.0, "LINEAR"
    res = animation.bake(scene, anim)
    assert not res["warnings"], res["warnings"]
    f0, f1 = animation.frame_of(anim, 0.0), animation.frame_of(anim, 2.0)
    for f in (f0, (f0 + f1) // 2, f0 + 7, f1):
        scene.frame_set(f)
        stroke = FULL * (f - f0) / (f1 - f0)
        assert joints.get_value(j) == pytest.approx(law_of_cosines_angle(c.closed_length + stroke), abs=2e-5)
        assert cylinders.length_now(c) - c.closed_length == pytest.approx(stroke, abs=5e-5)
    assert animation.block_label(b) == f"Move {c.name}"


def test_move_cylinder_step_says_why_not(scene):
    c, _ = make(scene)                         # nothing moves it
    s = scene.fresing
    anim = s.animations.add()
    b = anim.blocks.add()
    b.kind, b.cylinder = "CYLINDER", c.name
    res = animation.bake(scene, anim)
    assert any("add a joint for the arm" in w for w in res["warnings"]), res["warnings"]
    b.cylinder = "Nope"
    res = animation.bake(scene, anim)
    assert any("not found" in w for w in res["warnings"])


def test_pose_keeps_the_stroke(scene):
    j = arm(scene)
    c, _ = make(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    cylinders.set_stroke(scene, c, 0.12)
    pose = scene.fresing.poses.add()
    pose.name = "Up"
    states.capture_pose(scene, pose)
    cylinders.set_stroke(scene, c, 0.01)
    states.apply_pose(scene, "Up")
    update()
    assert cylinders.stroke_now(scene, c) == pytest.approx(0.12, abs=TOL)
    assert j is not None


# ---------------------------------------------------------------------------------------------------------
# telescopic, saved files, model updates, removing
# ---------------------------------------------------------------------------------------------------------

def test_telescopic_stage_slides_half_the_rod_travel(scene):
    j = arm(scene)
    y = 0.2
    stage = first_of(scene, "TELE.STAGE", y)
    c, _ = cylinders.create(scene, [first_of(scene, "TELE.BARREL", y)], [first_of(scene, "TELE.ROD", y)],
                            (at(B0, 0), Y, obs(scene, "BASE.PIN")[0]), (at(R00, 0), Y, obs(scene, "ARM.ROD.PIN")[0]),
                            stages=[stage])
    update()
    b = at(B0, y)
    p_stage = local_point(stage, b + (at(R00, y) - b).normalized() * 0.2)        # a point on the stage
    for deg in (-20, 0, 15):
        set_arm(scene, j, deg)
        r = rod_pin(math.radians(deg), y)
        u = (r - b).normalized()
        out = (r - b).length - L0                                               # the rod's travel
        assert (stage.matrix_world @ p_stage - (b + u * (0.2 + out / 2))).length < EYE_TOL
    for e in cylinders._objs(c.stage_empties):
        assert e.animation_data.drivers[0].driver.is_simple_expression      # works with scripts off


def test_save_and_reopen(scene, tmp_path):
    arm(scene)
    c, _ = make(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    cylinders.set_stroke(scene, c, 0.07)
    path = str(tmp_path / "cyl.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    update()
    c = sc.fresing.cylinders[0]
    j = joints.find(sc, "Luff")
    assert c.mode == "DRIVE" and cylinders.is_valid(c)
    assert cylinders.stroke_now(sc, c) == pytest.approx(0.07, abs=TOL)
    pts = eye_points_after_cad(sc)
    for stroke in (0.0, 0.15):
        cylinders.set_stroke(sc, c, stroke)
        angle = joints.get_value(j)
        assert angle == pytest.approx(law_of_cosines_angle(c.closed_length + stroke), abs=1e-6)
        check_eyes(sc, c, angle, eyes=pts)


def eye_points_after_cad(sc, y=0.08):
    """eye_points() for a scene whose arm is not in the CAD pose: worked out with every joint at 0."""
    with joints.cad_pose(sc):
        update()
        pts = eye_points(sc, y)
    update()
    return pts


def test_model_update_keeps_cylinders(scene):
    j = arm(scene)
    c1, _ = make(scene, 0.08)
    make(scene, 0.32)
    cylinders.set_mode(scene, c1, "DRIVE")
    c1.closed_length = CLOSED + 0.001                           # typed by the owner: kept
    cylinders.set_stroke(scene, c1, 0.09)
    angle = joints.get_value(j)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=LUFFER_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    s = scene.fresing
    assert [c.name for c in s.cylinders] == ["CYL.BARREL cylinder", "CYL.BARREL cylinder 2"]
    assert not len(s.report_notes), [n.text for n in s.report_notes]
    j = joints.find(scene, "Luff")
    c1, c2 = s.cylinders[0], s.cylinders[1]
    assert c1.frame.matrix_world.translation.y == pytest.approx(0.08, abs=TOL)       # the same cylinder again
    assert c1.mode == "DRIVE" and c2.mode == "FOLLOW"
    assert c1.closed_length == pytest.approx(CLOSED + 0.001, abs=1e-6)
    assert joints.get_value(j) == pytest.approx(angle, abs=1e-6)
    assert any(o.get(build.PROP_NAME) == "ARM.LAMP" for o in scene.objects)
    pts = {y: eye_points_after_cad(scene, y) for y in (0.08, 0.32)}
    cylinders.set_stroke(scene, c1, 0.04)
    a = joints.get_value(j)
    assert a == pytest.approx(law_of_cosines_angle(c1.closed_length + 0.04), abs=1e-6)
    check_eyes(scene, s.cylinders[0], a, 0.08, pts[0.08])
    check_eyes(scene, s.cylinders[1], a, 0.32, pts[0.32])


def test_model_update_when_the_rod_is_gone(scene):
    arm(scene)
    make(scene)
    specs = cylinders.before_model_update(scene)
    assert specs[0]["mode"] == "FOLLOW" and len(specs[0]["rod"]) == 1
    by_uid = {o.get(build.PROP_UID): o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS}
    del by_uid[specs[0]["rod"][0]]
    notes = cylinders.rebuild_from_specs(scene, specs, by_uid)
    assert not scene.fresing.cylinders and any("no longer in the model" in n for n in notes)


def test_remove_puts_the_parts_back(scene):
    j = arm(scene)
    rod = first_of(scene, "CYL.ROD", 0.08)
    before = rod.matrix_world.copy()
    c, _ = make(scene)
    set_arm(scene, j, 20)
    cylinders.remove(scene, c)
    update()
    assert not scene.fresing.cylinders
    assert rod.parent.get(build.PROP_NAME) == "CYL.ASM"
    assert all(abs(a - b) < 1e-6 for ra, rb in zip(rod.matrix_world, before) for a, b in zip(ra, rb))
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.CYLINDER_KINDS]


def test_rename_follows_animation_steps(scene):
    c, _ = make(scene)
    anim = scene.fresing.animations.add()
    b = anim.blocks.add()
    b.kind, b.cylinder = "CYLINDER", c.name
    c.name = "Luffing cylinder"
    assert b.cylinder == "Luffing cylinder" and c.frame.name == "Cylinder Luffing cylinder"
    c.name = ""                                             # never empty
    assert c.name == "Luffing cylinder"


def test_change_parts_and_stages(scene):
    """Set-up: other parts, telescopic stages on and off, another part for a pin – rebuilt in place."""
    j = arm(scene)
    y = 0.2
    c, _ = cylinders.create(scene, [first_of(scene, "TELE.BARREL", y)], [first_of(scene, "TELE.ROD", y)],
                            (at(B0, 0), Y, obs(scene, "BASE.PIN")[0]), (at(R00, 0), Y, obs(scene, "ARM.ROD.PIN")[0]))
    cylinders.set_mode(scene, c, "DRIVE")
    c = cylinders.rebuild(scene, c, stages=[first_of(scene, "TELE.STAGE", y)])
    assert len(c.stages) == 1 and c.mode == "DRIVE"
    c = cylinders.rebuild(scene, c, barrel_carrier=obs(scene, "BASE.BRACKET")[0])
    assert c.frame.parent.get(build.PROP_NAME) == "BASE.BRACKET"
    with pytest.raises(RuntimeError, match="outside the cylinder"):
        cylinders.rebuild(scene, c, rod_carrier=first_of(scene, "TELE.ROD", y))
    c = cylinders.rebuild(scene, cylinders.find(scene, c.name), stages=[])
    assert not len(c.stages) and len(scene.fresing.cylinders) == 1
    assert j is not None


def test_show_joint_arrows_toggle(scene):
    """The tick box raised NameError before 0.2.20 (the function it called was not visible to Blender)."""
    j = arm(scene)
    c, _ = make(scene)
    scene.fresing.show_joints = False
    assert j.frame.hide_get() and c.frame.hide_get() and c.pin.hide_get()
    scene.fresing.show_joints = True
    assert not j.frame.hide_get() and not c.frame.hide_get()


def test_cylinder_constraints_only(scene):
    """Everything that moves a cylinder is a constraint or a simple expression: nothing needs Python
    (background renders, files opened with scripts disabled)."""
    arm(scene)
    c, _ = make(scene)
    assert c.barrel_empty.constraints[0].type == "LOCKED_TRACK" and c.barrel_empty.constraints[0].target == c.pin
    assert c.rod_empty.constraints[0].type == "COPY_LOCATION"
    assert c.barrel_empty.animation_data is None and c.rod_empty.animation_data is None
