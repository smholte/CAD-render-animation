"""Task 0014: mechanisms on the generic test model (tools/make_test_linkage.py), against hand calculations.

All three mechanisms move in the XZ plane (pins along Y); positions read from the parts' own round-face axes.
Scissor lift: arms L = 1 m, 15° in the CAD pose, 3 stages; fixed pin (0, 0.1); platform pin at 0.1 + 3 L sin(phi);
the roller of the bottom outer arm at x = L cos(phi), z = 0.1. Four-bar: A (2, 0.3), D (2.4, 0.3), crank 0.12,
coupler 0.35, rocker 0.25 (Freudenstein's equation). Slider-crank: O (3.2, 0.3), crank 0.1, rod 0.3, piston pin
0.02 above O: x = 3.2 + 0.1 cos t + sqrt(0.3^2 - (0.1 sin t - 0.02)^2).
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, cylinders, joints, linkages, states  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL_A = os.path.join(HERE, "data", "test_linkage_a.step")
MODEL_B = os.path.join(HERE, "data", "test_linkage_b.step")
L, PHI0, Z0 = 1.0, math.radians(15.0), 0.1
TOL = 2e-5                  # 0.02 mm (Blender keeps positions in single precision)


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
    assert bpy.ops.fresing.import_step(filepath=MODEL_A, quality="draft") == {"FINISHED"}
    return sc


def update():
    """What the 3D view does: evaluate, the handler places the links, evaluate again."""
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def axis_xz(part, k=0):
    """(x, z) of a part's k-th round-face axis, world space (the axis runs along Y)."""
    a = part.data["fr_axes"]
    p = part.matrix_world @ Vector(a[7 * k:7 * k + 3])
    return (p.x, p.z)


def axes_xz(part):
    return [axis_xz(part, k) for k in range(len(part.data["fr_axes"]) // 7)]


def scissor(sc, base=True):
    arms = [ob(sc, f"LIFT.ARM.{s}.{i}") for i in (1, 2, 3) for s in ("IN", "OUT")]
    plat = ob(sc, "LIFT.PLATFORM.ASM")
    return linkages.create(sc, "SCISSOR", [[a] for a in arms] + [[plat]],
                           base=ob(sc, "LIFT.BASE.ASM") if base else None)


def four_bar(sc):
    crank = ob(sc, "FOURBAR.CRANK.ASM")
    return linkages.create(sc, "FOURBAR", [[ob(sc, "FOURBAR.COUPLER.ASM")], [ob(sc, "FOURBAR.ROCKER.ASM")], [crank]],
                           base=ob(sc, "FOURBAR.BASE.ASM"), drive=crank)


def slider(sc):
    return linkages.create(sc, "SLIDER", [[ob(sc, n)] for n in ("CRANK.CRANK.ASM", "CRANK.ROD.ASM", "CRANK.PISTON.ASM")],
                           base=ob(sc, "CRANK.BASE.ASM"))


def platform_z(sc):
    return axis_xz(ob(sc, "LIFT.PLATFORM.PIN"))[1]


def set_drive(sc, m, value):
    joints.set_value(linkages.input_joint(sc, m), value)
    update()


# ---------------------------------------------------------------------------
# scissor lift
# ---------------------------------------------------------------------------

def test_scissor_heights_roller_and_level_platform(scene):
    m = scissor(scene)
    d = linkages.setup(m)
    assert m.kind == "SCISSOR" and len(m.links) == 8 and len(d["pins"]) == 9 and len(d["slots"]) == 2
    j = linkages.input_joint(scene, m)
    assert j.kind == "ROTATE" and m.own_joint
    roller = ob(scene, "LIFT.ROLLER")            # on the bottom outer arm
    plate = ob(scene, "LIFT.PLATFORM")
    for deg in (0, 20, 45, -10, 70, 5):
        set_drive(scene, m, math.radians(deg))
        phi = PHI0 + math.radians(deg)              # a positive drive angle raises it
        assert platform_z(scene) == pytest.approx(Z0 + 3 * L * math.sin(phi), abs=TOL)
        assert axis_xz(ob(scene, "LIFT.PLATFORM.PIN"))[0] == pytest.approx(0.0, abs=TOL)
        x, z = axis_xz(roller)
        assert (x, z) == pytest.approx((L * math.cos(phi), Z0), abs=TOL)
        assert plate.matrix_world.to_euler().y == pytest.approx(0.0, abs=1e-6)          # stays level
        assert m.height == pytest.approx(3 * L * math.sin(phi), abs=TOL)
        assert not m.status


def test_scissor_limits_and_height_input(scene):
    m = scissor(scene)
    j = linkages.input_joint(scene, m)
    lo, hi = joints.limits(j)
    # from 2 % of the highest height (3 m) up to arms standing straight (90°)
    assert PHI0 + lo == pytest.approx(math.asin(0.02), abs=1e-4)
    assert PHI0 + hi == pytest.approx(math.radians(90), abs=1e-3)
    m.height = 1.2
    update()
    assert PHI0 + joints.get_value(j) == pytest.approx(math.asin(0.4), abs=1e-6)
    assert platform_z(scene) == pytest.approx(Z0 + 1.2, abs=TOL)
    m.height = 5.0                                 # higher than it goes: stops at its highest
    update()
    assert m.height == pytest.approx(3 * L * math.sin(PHI0 + hi), abs=1e-4)
    assert bpy.ops.fresing.mechanism_height(target="LOW") == {"FINISHED"}
    assert m.height == pytest.approx(0.06, abs=5e-4)               # (the limit keeps 1e-4 rad inside)


def test_scissor_never_folds_on_a_long_walk(scene):
    m = scissor(scene)
    for deg in (60, -13, 70, -12, 40, 2, -13.5, 74, 0):
        set_drive(scene, m, math.radians(deg))
        assert m.height == pytest.approx(3 * L * math.sin(PHI0 + math.radians(deg)), abs=TOL)
        assert platform_z(scene) == pytest.approx(Z0 + m.height, abs=TOL)


def test_default_base_with_a_cylinder_in_it_points_to_the_base_button(scene):
    with pytest.raises(RuntimeError, match="Base"):
        scissor(scene, base=False)


# ---------------------------------------------------------------------------
# four-bar and slider-crank
# ---------------------------------------------------------------------------

def freudenstein(th2, branch=-1, a=0.12, b=0.35, c=0.25, d=0.40):
    k1, k2, k3 = d / a, d / c, (a * a - b * b + c * c + d * d) / (2 * a * c)
    aa = math.cos(th2) - k1 - k2 * math.cos(th2) + k3
    bb = -2 * math.sin(th2)
    cc = k1 - (k2 + 1) * math.cos(th2) + k3
    return 2 * math.atan((-bb + branch * math.sqrt(bb * bb - 4 * aa * cc)) / (2 * aa))


def test_four_bar_matches_freudenstein_through_two_turns(scene):
    m = four_bar(scene)
    j = linkages.input_joint(scene, m)
    assert {o.get(build.PROP_NAME) for o in joints.members(j)} == {"FOURBAR.CRANK.ASM"}
    assert not j.use_limits                      # a Grashof crank turns all the way round
    crank_pin = ob(scene, "FOURBAR.CRANK.PIN")
    rocker_pin = ob(scene, "FOURBAR.ROCKER.PIN")
    coupler_pin = ob(scene, "FOURBAR.COUPLER.PIN")
    for deg in range(0, 721, 45):
        set_drive(scene, m, math.radians(deg))
        bx, bz = axis_xz(crank_pin)
        cx, cz = axis_xz(rocker_pin)
        assert axis_xz(coupler_pin) == pytest.approx((cx, cz), abs=TOL)       # the coupler's pin on the rocker's
        assert math.hypot(bx - 2.0, bz - 0.3) == pytest.approx(0.12, abs=TOL)
        assert math.hypot(cx - bx, cz - bz) == pytest.approx(0.35, abs=TOL)
        th2 = math.atan2(bz - 0.3, bx - 2.0)
        th4 = math.atan2(cz - 0.3, cx - 2.4)
        assert math.remainder(th4 - freudenstein(th2), 2 * math.pi) == pytest.approx(0.0, abs=1e-4)


def test_slider_crank_matches_the_formula(scene):
    m = slider(scene)
    assert len(linkages.setup(m)["slides"]) == 1
    rod_pin = ob(scene, "CRANK.ROD.PIN")
    crank_pin = ob(scene, "CRANK.CRANK.PIN")
    piston = ob(scene, "CRANK.PISTON")
    for deg in range(0, 361, 30):
        set_drive(scene, m, math.radians(deg))
        bx, bz = axis_xz(crank_pin)
        t = math.atan2(bz - 0.3, bx - 3.2)
        x = 3.2 + 0.1 * math.cos(t) + math.sqrt(0.09 - (0.1 * math.sin(t) - 0.02) ** 2)
        assert axis_xz(rod_pin) == pytest.approx((x, 0.32), abs=TOL)
        assert piston.matrix_world.to_euler().y == pytest.approx(0.0, abs=1e-6)       # the piston never turns


def test_links_cannot_get_a_joint_and_the_drive_joint_is_locked(scene):
    m = scissor(scene)
    arm = ob(scene, "LIFT.ARM.OUT.2")
    with pytest.raises(RuntimeError, match="mechanism"):
        joints.create(scene, "ROTATE", [arm], Vector((0, 0, 0)), Vector((0, 1, 0)))
    lamp_parent = ob(scene, "LIFT.PLATFORM")          # a part inside a link may ride on it
    assert linkages.joint_conflict(scene, [lamp_parent], ob(scene, "LIFT.PLATFORM.ASM")) == ""
    j = linkages.input_joint(scene, m)
    scene.fresing.joints_index = next(i for i, x in enumerate(scene.fresing.joints) if x.name == j.name)
    assert bpy.ops.fresing.joint_remove() == {"CANCELLED"}
    assert bpy.ops.fresing.joint_flip() == {"CANCELLED"}
    with pytest.raises(RuntimeError, match="already a link"):
        scissor(scene)


# ---------------------------------------------------------------------------
# poses, animation, files, model updates
# ---------------------------------------------------------------------------

def test_pose_and_cad_pose(scene):
    m = scissor(scene)
    set_drive(scene, m, math.radians(30))
    states.save_pose(scene, "Up")
    set_drive(scene, m, 0.0)
    assert states.apply_pose(scene, "Up")
    bpy.context.view_layer.update()                  # (no second update: the pose places the links itself)
    assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0 + math.radians(30)), abs=TOL)
    with joints.cad_pose(scene):
        assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0), abs=TOL)
    update()
    assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0 + math.radians(30)), abs=TOL)


def _anim(sc, kind="JOINT"):
    s = sc.fresing
    a = s.animations.add()
    a.name = "Lift"
    b = a.blocks.add()
    b.kind = kind
    b.start, b.duration, b.easing = 0.0, 2.0, "LINEAR"
    return a, b


def test_animation_keys_every_link_and_needs_no_drivers(scene):
    m = scissor(scene)
    j = linkages.input_joint(scene, m)
    a, b = _anim(scene)
    b.joint = j.name
    b.use_from = False
    b.from_angle, b.to_angle = 0.0, math.radians(40)
    res = animation.bake(scene, a)
    assert not [w for w in res["warnings"] if "Mechanism" in w]
    for ln in m.links:
        if ln.empty is not None:
            assert ln.empty.animation_data.action is not None
            assert not ln.empty.animation_data.drivers        # keys only: plays with scripts off
    f0, f1 = animation.frame_of(a, 0.0), animation.frame_of(a, 2.0)
    for f in (f0, (f0 + f1) // 2, f1):
        scene.frame_set(f)
        v = math.radians(40) * (f - f0) / (f1 - f0)
        assert joints.get_value(j) == pytest.approx(v, abs=1e-6)
        assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0 + v), abs=TOL), f
    animation.clear_keys(scene)
    update()
    assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0), abs=TOL)


def test_lift_height_step(scene):
    m = scissor(scene)
    a, b = _anim(scene, "MECHANISM")
    b.mechanism = m.name
    b.use_from = False
    b.from_height, b.to_height = 0.5, 2.0
    res = animation.bake(scene, a)
    assert not res["warnings"]
    f0, f1 = animation.frame_of(a, 0.0), animation.frame_of(a, 2.0)
    for f in (f0, (f0 + f1) // 2, f1):
        scene.frame_set(f)
        want = 0.5 + 1.5 * (f - f0) / (f1 - f0)                  # the height goes up at a constant speed
        assert platform_z(scene) - Z0 == pytest.approx(want, abs=TOL)
    b.to_height = 9.0
    res = animation.bake(scene, a)
    assert any("cannot reach" in w for w in res["warnings"])
    animation.clear_keys(scene)


def test_save_and_reopen(scene, tmp_path):
    m = scissor(scene)
    four_bar(scene)
    set_drive(scene, m, math.radians(25))
    path = str(tmp_path / "mech.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    update()
    m = sc.fresing.mechanisms[0]
    assert linkages.is_valid(m) and len(sc.fresing.mechanisms) == 2
    assert platform_z(sc) == pytest.approx(Z0 + 3 * math.sin(PHI0 + math.radians(25)), abs=TOL)
    set_drive(sc, m, math.radians(-5))
    assert platform_z(sc) == pytest.approx(Z0 + 3 * math.sin(PHI0 - math.radians(5)), abs=TOL)


def test_model_update_keeps_the_mechanisms(scene):
    m = scissor(scene)
    slider(scene)
    set_drive(scene, m, math.radians(20))
    jname = linkages.input_joint(scene, m).name
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=MODEL_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    s = scene.fresing
    assert [x.name for x in s.mechanisms] == ["Scissor lift", "Slider-crank"]
    m = s.mechanisms[0]
    assert linkages.is_valid(m) and linkages.input_joint(scene, m).name == jname
    assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0 + math.radians(20)), abs=TOL)
    lamp = ob(scene, "LIFT.PLATFORM.LAMP")               # new in revision B: rides on the platform
    z0 = lamp.matrix_world.translation.z
    set_drive(scene, m, math.radians(30))
    assert lamp.matrix_world.translation.z - z0 == pytest.approx(
        3 * (math.sin(PHI0 + math.radians(30)) - math.sin(PHI0 + math.radians(20))), abs=TOL)


def test_remove_puts_the_parts_back(scene):
    m = scissor(scene)
    set_drive(scene, m, math.radians(30))
    n_joints = len(scene.fresing.joints)
    linkages.remove(scene, m)
    update()
    assert not scene.fresing.mechanisms and len(scene.fresing.joints) == n_joints - 1
    assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(PHI0), abs=TOL)
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.LINKAGE_KINDS]


# ---------------------------------------------------------------------------
# a cylinder lifts the scissor
# ---------------------------------------------------------------------------

G = (0.45, 0.1)


def lift_cylinder(sc):
    barrel, rod = ob(sc, "LIFT.CYL.BARREL"), ob(sc, "LIFT.CYL.ROD")
    gx, gz = G
    rx, rz = 0.75 * L * math.cos(PHI0), Z0 + 0.75 * L * math.sin(PHI0)
    y = Vector((0, 1, 0))
    c, _notes = cylinders.create(sc, [barrel], [rod], (Vector((gx, -0.08, gz)), y, ob(sc, "LIFT.BASE.CYL.PIN")),
                                 (Vector((rx, -0.08, rz)), y, ob(sc, "LIFT.CYL.PIN")))
    c.closed_length, c.full_stroke = 0.30, 0.4
    return c


def test_cylinder_follows_and_drives_the_scissor(scene):
    m = scissor(scene)
    c = lift_cylinder(scene)
    # follow: the lift moves, the eyes stay on their pins
    set_drive(scene, m, math.radians(20))
    phi = PHI0 + math.radians(20)
    rx, rz = 0.75 * math.cos(phi), Z0 + 0.75 * math.sin(phi)
    assert cylinders.length_now(c) == pytest.approx(math.hypot(rx - G[0], rz - G[1]), abs=TOL)
    # drive: stroke -> the drive joint, by the law of cosines in the triangle fixed pin, G, rod pin
    assert cylinders.set_mode(scene, c, "DRIVE") is not None
    j, reason = cylinders.arm_joint(scene, c)
    assert j is not None and j.name == linkages.input_joint(scene, m).name, reason
    for stroke in (0.05, 0.2, 0.1):
        cylinders.set_stroke(scene, c, stroke)
        update()
        length = 0.30 + stroke
        cos_phi = (0.75 ** 2 + G[0] ** 2 - length ** 2) / (2 * 0.75 * G[0])     # fixed pin at the origin
        phi = math.acos(cos_phi)
        assert PHI0 + joints.get_value(j) == pytest.approx(phi, abs=1e-5)
        assert platform_z(scene) == pytest.approx(Z0 + 3 * math.sin(phi), abs=TOL)
        assert cylinders.stroke_now(scene, c) == pytest.approx(stroke, abs=TOL)


def test_move_cylinder_step_through_the_scissor(scene):
    m = scissor(scene)
    c = lift_cylinder(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    a, b = _anim(scene, "CYLINDER")
    b.cylinder = c.name
    b.use_from = False
    b.from_stroke, b.to_stroke = 0.05, 0.3
    res = animation.bake(scene, a)
    assert not res["warnings"], res["warnings"]
    f0, f1 = animation.frame_of(a, 0.0), animation.frame_of(a, 2.0)
    for f in (f0, (f0 + f1) // 2, f1):
        scene.frame_set(f)
        stroke = 0.05 + 0.25 * (f - f0) / (f1 - f0)
        assert cylinders.length_now(c) - 0.30 == pytest.approx(stroke, abs=TOL)
    animation.clear_keys(scene)
    del m


class _Texts:
    """Stands in for a panel layout and keeps every text the panel draws."""

    def __init__(self, out):
        self.__dict__["_out"] = out

    def __getattr__(self, name):
        def call(*a, **k):
            if k.get("text"):
                self._out.append(k["text"])
            if name == "panel":
                return _Texts(self._out), _Texts(self._out)
            return 0 if name == "icon" else _Texts(self._out)
        return call


def test_panels_draw(scene):
    from fresing_render.blender import ui_motion
    out = []
    fake = type("P", (), {"layout": _Texts(out)})()
    ui_motion.FRESING_PT_mechanisms.draw(fake, bpy.context)
    assert "Add mechanism" in out
    m = scissor(scene)
    out.clear()
    ui_motion.FRESING_PT_mechanisms.draw_header_preset(fake, bpy.context)
    ui_motion.FRESING_PT_mechanisms.draw(fake, bpy.context)
    text = " ".join(out)
    assert "1 mechanism" in text and m.name in text and "Height" in text and "Drive angle" in text
    assert "7 links, 9 pins, 2 rollers" in text


def test_joint_on_the_whole_model_or_on_what_carries_its_base_is_refused(scene):
    """0.2.25 skipped these checks (lines after a return); 0.2.24 had them."""
    root = build.model_roots(scene)[0]
    with pytest.raises(RuntimeError, match="whole model"):
        joints.create(scene, "ROTATE", [root], Vector((0, 0, 0)), Vector((0, 1, 0)))
    lift_asm = ob(scene, "LIFT.ASM")
    with pytest.raises(RuntimeError, match="carries the base"):
        joints.create(scene, "ROTATE", [lift_asm], Vector((0, 0, 0)), Vector((0, 1, 0)),
                      base=ob(scene, "LIFT.BASE.ASM"))


# ---------------------------------------------------------------------------
# found by the independent review
# ---------------------------------------------------------------------------

def test_solver_position_kept_in_double_precision(scene):
    """The stored position was single precision: it never matched the joint, so every update started the
    solver again without its history (a parallelogram dragged in small steps crossed over)."""
    m = scissor(scene)
    j = linkages.input_joint(scene, m)
    for deg in (20.0, 20.5, 21.0):
        set_drive(scene, m, math.radians(deg))
    _lk, _h, sign = linkages.linkage_of(m)
    assert linkages.solved(m) == sign * joints.get_value(j)          # exactly
    assert linkages.solver(m).hist                                    # the walk's history survives updates
    assert linkages.refresh(scene, m) == "" and linkages.solver(m).hist


def test_no_link_can_join_the_drive_joint(scene):
    m = four_bar(scene)
    j = linkages.input_joint(scene, m)
    with pytest.raises(RuntimeError, match="mechanism"):
        joints.add_members(scene, j, [ob(scene, "FOURBAR.COUPLER.ASM")])
    s = scene.fresing
    s.joints_index = next(i for i, x in enumerate(s.joints) if x.name == j.name)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob(scene, "CRANK.CRANK.ASM").select_set(True)
    assert bpy.ops.fresing.joint_members(action="ADD") == {"CANCELLED"}
    assert {o.get(build.PROP_NAME) for o in joints.members(j)} == {"FOURBAR.CRANK.ASM"}
    assert linkages.is_valid(m)


def test_a_joint_may_carry_the_whole_mechanism(scene):
    """A lift on a turntable: a joint on the subassembly that holds the base and every link, made after it."""
    m = scissor(scene)
    set_drive(scene, m, math.radians(15))
    slew = joints.create(scene, "ROTATE", [ob(scene, "LIFT.ASM")], Vector((0, 0, 0)), Vector((0, 0, 1)),
                         base=build.model_roots(scene)[0], name="Slew")
    joints.set_value(slew, math.radians(90))
    update()
    x, y, z = ob(scene, "LIFT.PLATFORM.PIN").matrix_world @ Vector(ob(scene, "LIFT.PLATFORM.PIN").data["fr_axes"][0:3])
    assert z == pytest.approx(Z0 + 3 * math.sin(math.radians(30)), abs=TOL)
    set_drive(scene, m, math.radians(30))
    p = ob(scene, "LIFT.PLATFORM.PIN").matrix_world @ Vector(ob(scene, "LIFT.PLATFORM.PIN").data["fr_axes"][0:3])
    assert p.z == pytest.approx(Z0 + 3 * math.sin(math.radians(45)), abs=TOL)
    roller = ob(scene, "LIFT.ROLLER")
    q = roller.matrix_world @ Vector(roller.data["fr_axes"][0:3])
    # turned 90° with the deck (its axis now runs along X): still on its line, at L cos(phi)
    assert (q.y, q.z) == pytest.approx((math.cos(math.radians(45)), Z0), abs=TOL)
    with pytest.raises(RuntimeError, match="tear"):          # the base alone, without the links: refused
        joints.create(scene, "ROTATE", [ob(scene, "LIFT.BASE.ASM")], Vector((0, 0, 0)), Vector((0, 0, 1)))


def test_removing_the_mechanism_lets_its_cylinder_follow(scene):
    m = scissor(scene)
    c = lift_cylinder(scene)
    cylinders.set_mode(scene, c, "DRIVE")
    linkages.remove(scene, m)
    assert c.mode == "FOLLOW"
