"""Task 0011: several joints on one subassembly, the moves add up (stacks).

All positions are checked against hand-calculated ones on the test crane (tests/data):
TROLLEY.ASM is a direct child of the model root, so its joints sit on the root.
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
P = Vector((0.75, 0.25, 0.45))            # a pivot point on the trolley (TROLLEY.ASM sits at 0.7, 0.225, 0.45)
TOL = 1e-5                                # 0.01 mm: Blender keeps matrices in single precision

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, logic, states  # noqa: E402


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
    return sc


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def update():
    bpy.context.view_layer.update()


def J(sc, name):
    """Look a joint up again (list items are only valid until the list changes)."""
    return joints.find(sc, name)


def wheel_point(sc):
    """A point on the trolley (the second wheel's origin) in world space."""
    return ob(sc, "WHEEL", 1).matrix_world.translation.copy()


def trolley_point(sc):
    return ob(sc, "TROLLEY").matrix_world.translation.copy()


def close(a, b, tol=TOL):
    return (Vector(a) - Vector(b)).length < tol


def rot_z(angle, v):
    return Matrix.Rotation(angle, 3, "Z") @ Vector(v)


def two_slides(sc, y_first=1.0):
    """Owner's example: slide 1 along Y, then slide 2 along X on the same subassembly."""
    tr = ob(sc, "TROLLEY.ASM")
    j1 = joints.create(sc, "SLIDE", [tr], tr.matrix_world.translation, Y, name="Lift Y")
    joints.set_value(J(sc, "Lift Y"), y_first)
    update()
    j2 = joints.create(sc, "SLIDE", [tr], tr.matrix_world.translation, X, name="Travel X")
    _ = (j1, j2)
    return J(sc, "Lift Y"), J(sc, "Travel X")


# ---------------------------------------------------------------------------
# the stack itself
# ---------------------------------------------------------------------------


def test_owner_example_moves_add_up(scene):
    """Joint 1: Y +1000 mm, joint 2: X +500 mm -> the subassembly sits at X +500 / Y +1000."""
    q0 = trolley_point(scene)
    root = build.model_roots(scene)[0]
    a, b = two_slides(scene)                     # joint 2 is added while joint 1 stands at 1000 mm
    assert joints.rides_on(scene, b).name == "Lift Y" and joints.rides_on(scene, a) is None
    assert joints.members(a) == [] and joints.members(b) == [ob(scene, "TROLLEY.ASM")]
    assert [r.name for r in joints.riders(scene, a)] == ["Travel X"]
    assert a.base is root and b.base is None     # the top joint sits on no part: it rides on 'Lift Y'
    assert joints.depth(scene, a) == 0 and joints.depth(scene, b) == 1
    assert [o.name for o in joints.moved_objects(scene, a)] == [ob(scene, "TROLLEY.ASM").name]
    assert build.logical_parent(ob(scene, "TROLLEY.ASM")) is root    # the structure list is unchanged
    joints.set_value(b, 0.5)
    update()
    off = trolley_point(scene) - q0
    assert close(off, (0.5, 1.0, 0.0)), off
    mm = [round(v * 1000, 2) for v in off]
    assert mm == [500.0, 1000.0, 0.0], mm
    # each joint alone
    joints.set_value(a, 0.0)
    update()
    assert close(trolley_point(scene) - q0, (0.5, 0, 0))
    joints.set_value(a, 1.0)
    joints.set_value(b, 0.0)
    update()
    assert close(trolley_point(scene) - q0, (0, 1.0, 0))
    # the rest of the crane did not move
    assert close(ob(scene, "BOOM").matrix_world.translation, (0.1, 0.3, 0.4))


def test_same_result_when_added_at_zero(scene):
    a, b = two_slides(scene, y_first=0.0)
    q0 = trolley_point(scene)
    joints.set_value(a, 1.0)
    joints.set_value(b, 0.5)
    update()
    assert close(trolley_point(scene) - q0, (0.5, 1.0, 0.0))


def test_rotate_on_slide(scene):
    """Bottom: slide X 300 mm. On top: turn 40° about a vertical axis through P (the axis rides along)."""
    tr = ob(scene, "TROLLEY.ASM")
    q = wheel_point(scene)
    joints.create(scene, "SLIDE", [tr], P, X, name="Slide")
    joints.set_value(J(scene, "Slide"), 0.3)
    update()
    # the axis is picked in the current pose (the slide is out by 300 mm): it is stored on the slide
    joints.create(scene, "ROTATE", [tr], P + Vector((0.3, 0, 0)), Z, name="Turn")
    a, b = J(scene, "Slide"), J(scene, "Turn")
    assert joints.rides_on(scene, b).name == "Slide"
    assert close(joints.axis_world(b)[0], P + Vector((0.3, 0, 0)))
    joints.set_value(b, math.radians(40))
    update()
    expect = P + rot_z(math.radians(40), q - P) + Vector((0.3, 0, 0))
    assert close(wheel_point(scene), expect), (wheel_point(scene), expect)
    # in the CAD position of the slide the axis goes through P
    joints.set_value(a, 0.0)
    update()
    assert close(joints.axis_world(b)[0], P)
    assert close(wheel_point(scene), P + rot_z(math.radians(40), q - P))


def test_slide_on_rotate_and_swap(scene):
    """Bottom: turn 30° about Z through P. On top: slide 200 mm along the turned X. Then swap the order."""
    tr = ob(scene, "TROLLEY.ASM")
    q = wheel_point(scene)
    th, d = math.radians(30), 0.2
    joints.create(scene, "ROTATE", [tr], P, Z, name="Turn")
    joints.set_value(J(scene, "Turn"), th)
    update()
    joints.create(scene, "SLIDE", [tr], wheel_point(scene), rot_z(th, X), name="Slide")
    joints.set_value(J(scene, "Slide"), d)
    update()
    expect = P + rot_z(th, q + d * X - P)            # slide along X, then everything turns
    assert close(wheel_point(scene), expect), (wheel_point(scene), expect)

    assert joints.swap_check(scene, J(scene, "Slide")) == ""
    joints.swap(scene, J(scene, "Slide"))             # now the turn rides on the slide
    update()
    a, b = J(scene, "Turn"), J(scene, "Slide")
    assert joints.rides_on(scene, a).name == "Slide" and joints.rides_on(scene, b) is None
    assert joints.members(a) == [tr] and joints.members(b) == []
    assert abs(joints.get_value(a) - th) < 1e-9 and abs(joints.get_value(b) - d) < 1e-9
    expect = d * X + P + rot_z(th, q - P)             # turn about P, then everything slides along X
    assert close(wheel_point(scene), expect), (wheel_point(scene), expect)
    assert b.base is build.model_roots(scene)[0] and a.base is None
    # back again
    joints.swap(scene, J(scene, "Turn"))
    update()
    assert joints.rides_on(scene, J(scene, "Slide")).name == "Turn"
    assert close(wheel_point(scene), P + rot_z(th, q + d * X - P))
    # all at 0: the CAD position
    states.reset_pose(scene)
    update()
    assert close(wheel_point(scene), q)


def test_two_slides_swap_changes_nothing(scene):
    a, b = two_slides(scene)
    joints.set_value(b, 0.5)
    update()
    before = trolley_point(scene)
    joints.swap(scene, b)
    update()
    assert joints.rides_on(scene, J(scene, "Lift Y")).name == "Travel X"
    assert close(trolley_point(scene), before)


def test_mixed_selection_and_swap_refused(scene):
    tr, cover, boom = ob(scene, "TROLLEY.ASM"), ob(scene, "COVER"), ob(scene, "BOOM.ASM")
    joints.create(scene, "ROTATE", [tr, cover], P, Z, name="Both")
    # one moves with a joint, the other does not: no guessing
    with pytest.raises(RuntimeError, match="one at a time"):
        joints.create(scene, "SLIDE", [tr, boom], P, X)
    below, reason = joints.stack_info(scene, [tr, boom])
    assert below is None and "'Both'" in reason
    # a joint on the trolley alone rides on 'Both'; the cover stays on 'Both' only
    joints.create(scene, "SLIDE", [tr], P, X, name="Trolley only")
    assert joints.rides_on(scene, J(scene, "Trolley only")).name == "Both"
    assert joints.members(J(scene, "Both")) == [cover]
    # swapping would make the cover slide too: refused, with the reason
    reason = joints.swap_check(scene, J(scene, "Trolley only"))
    assert "COVER" in reason
    with pytest.raises(RuntimeError):
        joints.swap(scene, J(scene, "Trolley only"))
    # members of two different joints: also refused
    joints.create(scene, "ROTATE", [boom], P, Y, name="Boom")
    with pytest.raises(RuntimeError, match="one at a time"):
        joints.create(scene, "SLIDE", [tr, boom], P, X)


def _three(scene):
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], P, Y, name="A")
    joints.create(scene, "SLIDE", [tr], P, X, name="B")
    joints.create(scene, "ROTATE", [tr], P, Z, name="C")
    joints.set_value(J(scene, "A"), 0.2)
    joints.set_value(J(scene, "B"), 0.1)
    joints.set_value(J(scene, "C"), math.radians(30))
    update()
    assert [joints.depth(scene, J(scene, n)) for n in "ABC"] == [0, 1, 2]
    order, depths = joints.tree_order(scene)
    assert [scene.fresing.joints[i].name for i in order] == ["A", "B", "C"]


def test_remove_middle_of_three(scene):
    q = wheel_point(scene)
    _three(scene)
    th = math.radians(30)
    assert close(wheel_point(scene), P + rot_z(th, q - P) + Vector((0.1, 0.2, 0)))
    joints.remove(scene, J(scene, "B"))
    update()
    a, c = J(scene, "A"), J(scene, "C")
    assert joints.rides_on(scene, c).name == "A" and len(scene.fresing.joints) == 2
    assert abs(joints.get_value(a) - 0.2) < 1e-9 and abs(joints.get_value(c) - th) < 1e-9
    assert close(wheel_point(scene), P + rot_z(th, q - P) + Vector((0, 0.2, 0)))
    # the bottom one goes too: the turn now sits on what A sat on
    joints.remove(scene, J(scene, "A"))
    update()
    c = J(scene, "C")
    assert joints.rides_on(scene, c) is None and c.base is build.model_roots(scene)[0]
    assert close(wheel_point(scene), P + rot_z(th, q - P))
    joints.remove(scene, J(scene, "C"))
    update()
    tr = ob(scene, "TROLLEY.ASM")
    assert tr.parent is build.model_roots(scene)[0] and close(wheel_point(scene), q)
    assert not [o for o in scene.objects if o.get(build.PROP_KIND) in build.JOINT_KINDS]


def test_remove_top_goes_back_to_the_joint_below(scene):
    q = wheel_point(scene)
    _three(scene)
    joints.remove(scene, J(scene, "C"))
    update()
    tr = ob(scene, "TROLLEY.ASM")
    assert joints.members(J(scene, "B")) == [tr]
    assert close(wheel_point(scene), q + Vector((0.1, 0.2, 0)))
    # taking the trolley out of B puts it on A (A's move stays)
    joints.remove_members(scene, J(scene, "B"), [tr])
    update()
    assert joints.members(J(scene, "A")) == [tr] and joints.members(J(scene, "B")) == []
    assert close(wheel_point(scene), q + Vector((0, 0.2, 0)))


def test_flip_and_axis_keep_the_stack(scene):
    a, b = two_slides(scene)
    joints.set_value(b, 0.5)
    update()
    q0 = trolley_point(scene) - Vector((0.5, 1.0, 0))
    joints.flip(scene, a)                            # the bottom slide now runs along -Y
    update()
    assert abs(joints.get_value(J(scene, "Lift Y")) - 1.0) < 1e-9
    assert close(trolley_point(scene) - q0, (0.5, -1.0, 0.0))
    joints.set_kind(scene, J(scene, "Lift Y"), "ROTATE")   # type change keeps the joint on top in place
    update()
    assert joints.rides_on(scene, J(scene, "Travel X")).name == "Lift Y"
    assert close(trolley_point(scene) - q0, (0.5, 0, 0))
    j = J(scene, "Lift Y")
    j.use_limits = True
    j.rot_min, j.rot_max = 0.0, math.radians(10)
    assert abs(joints.set_value(j, math.radians(45)) - math.radians(10)) < 1e-6


# ---------------------------------------------------------------------------
# everything else keeps working with stacks
# ---------------------------------------------------------------------------


def test_pose_reset_and_explode(scene):
    q0 = trolley_point(scene)
    a, b = two_slides(scene)
    joints.set_value(b, 0.5)
    update()
    states.save_pose(scene, "Out")
    states.reset_pose(scene)                          # "Everything back to CAD position"
    update()
    assert close(trolley_point(scene), q0)
    assert states.apply_pose(scene, "Out")
    update()
    assert close(trolley_point(scene) - q0, (0.5, 1.0, 0))
    root = build.model_roots(scene)[0]
    assert states.explode(scene, root, 0.5) >= 5
    update()
    assert not close(trolley_point(scene) - q0, (0.5, 1.0, 0), 1e-3)
    states.apply_pose(scene, "Out")                   # the pose puts the exploded pieces back
    update()
    assert close(trolley_point(scene) - q0, (0.5, 1.0, 0))
    # a free move of the trolley survives adding a third joint on top
    tr = ob(scene, "TROLLEY.ASM")
    tr.matrix_basis = Matrix.Translation((0, 0, 0.05)) @ tr.matrix_basis
    update()
    want = trolley_point(scene).copy()
    joints.create(scene, "ROTATE", [tr], P, Z, name="Turn")
    update()
    assert joints.rides_on(scene, J(scene, "Turn")).name == "Travel X"
    assert close(trolley_point(scene), want)


def test_animation_steps_in_sequence_and_together(scene):
    q0 = trolley_point(scene)
    a, b = two_slides(scene, y_first=0.0)
    s = scene.fresing
    anim = s.animations.add()
    anim.name, anim.fps, anim.tail = "Stack", "25", 0.0
    st = anim.blocks.add()                              # Y 0 -> 1000 mm in 0-2 s
    st.kind, st.joint, st.start, st.duration, st.easing = "JOINT", "Lift Y", 0.0, 2.0, "LINEAR"
    st.use_from, st.from_dist, st.to_dist = False, 0.0, 1.0
    st = anim.blocks.add()                              # X 0 -> 500 mm in 1-3 s (overlaps: together)
    st.kind, st.joint, st.start, st.duration, st.easing = "JOINT", "Travel X", 1.0, 2.0, "LINEAR"
    st.use_from, st.from_dist, st.to_dist = False, 0.0, 0.5
    st = anim.blocks.add()                              # then X back to 0 in 3-4 s (in sequence)
    st.kind, st.joint, st.start, st.duration, st.easing = "JOINT", "Travel X", 3.0, 1.0, "LINEAR"
    st.use_from, st.to_dist = True, 0.0
    info = animation.bake(scene, anim)
    assert info["frames"] == 101 and not info["warnings"], info
    for frame, want in ((1, (0, 0, 0)), (26, (0, 0.5, 0)), (51, (0.25, 1.0, 0)), (76, (0.5, 1.0, 0)),
                        (101, (0, 1.0, 0))):
        scene.frame_set(frame)
        update()
        assert close(trolley_point(scene) - q0, want, 1e-4), (frame, trolley_point(scene) - q0, want)
    animation.clear_keys(scene)
    update()
    assert close(trolley_point(scene), q0)


def test_saved_file_keeps_the_stack(scene, tmp_path):
    q0 = trolley_point(scene)
    _a, b = two_slides(scene)
    joints.set_value(b, 0.5)
    path = str(tmp_path / "stack.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    update()
    assert joints.rides_on(sc, J(sc, "Travel X")).name == "Lift Y"
    assert close(trolley_point(sc) - q0, (0.5, 1.0, 0))
    joints.set_value(J(sc, "Travel X"), 0.25)
    update()
    assert close(trolley_point(sc) - q0, (0.25, 1.0, 0))


def _boom_luff(sc):
    pin = ob(sc, "BOOM.PIN")
    origin, direction, _desc = joints.axis_from_hit(pin, 0, Vector((0.1, 0.3, 0.42)), Z)
    return joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], origin, direction, ref=pin, name="Luff")


@pytest.mark.parametrize("swapped", [False, True])
def test_model_update_rebuilds_stacks(scene, swapped):
    """Update to crane revision B: stacks come back in the right order, with their values.

    ``swapped``: the bottom joint is the newer one in the list (made with Swap order)."""
    s = scene.fresing
    _boom_luff(scene)
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "ROTATE", [tr], P, Z, name="Turn")
    joints.create(scene, "SLIDE", [tr], P, X, name="Slide")
    joints.create(scene, "SLIDE", [tr], P, Y, name="Lift")
    if swapped:
        joints.swap(scene, J(scene, "Slide"))             # Slide at the bottom, Turn on it, Lift on top
    joints.set_value(J(scene, "Luff"), math.radians(15))
    joints.set_value(J(scene, "Turn"), math.radians(25))
    joints.set_value(J(scene, "Slide"), 0.15)
    joints.set_value(J(scene, "Lift"), 0.05)
    update()
    before = {n: joints.get_value(J(scene, n)) for n in ("Luff", "Turn", "Slide", "Lift")}
    stack = {n: (joints.rides_on(scene, J(scene, n)) or type("N", (), {"name": None})).name
             for n in ("Luff", "Turn", "Slide", "Lift")}
    names = [j.name for j in s.joints]
    wheel = wheel_point(scene)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert [j.name for j in s.joints] == names, "the joint list keeps its order"
    assert all(joints.is_valid(j) for j in s.joints) and not len(s.report_notes)
    for n in before:
        assert abs(joints.get_value(J(scene, n)) - before[n]) < 1e-9, n
        below = joints.rides_on(scene, J(scene, n))
        assert (below.name if below else None) == stack[n], n
    assert close(wheel_point(scene), wheel)
    bottom = "Slide" if swapped else "Turn"
    assert joints.members(J(scene, bottom)) == [] and joints.members(J(scene, "Lift")) == [ob(scene, "TROLLEY.ASM")]


def test_model_update_when_the_stack_lost_its_parts(scene):
    """The trolley is gone in the new revision -> the whole stack goes, with one note per joint."""
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], P, Y, name="A")
    joints.create(scene, "SLIDE", [tr], P, X, name="B")
    specs = joints.dissolve_all(scene)
    assert [sp["base_joint"] for sp in specs] == [None, "A"]
    by_uid = {o.get(build.PROP_UID): o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS}
    del by_uid[tr.get(build.PROP_UID)]
    notes = joints.rebuild_from_specs(scene, specs, by_uid)
    assert len(scene.fresing.joints) == 0 and len(notes) == 2, notes
    # and when only the joint below is gone, the top one sits on its CAD parent
    by_uid[tr.get(build.PROP_UID)] = tr
    bad = [dict(specs[1])]
    notes = joints.rebuild_from_specs(scene, bad, by_uid)
    assert len(scene.fresing.joints) == 1 and "rode on" in notes[0], notes
    assert J(scene, "B").base is build.model_roots(scene)[0]


# ---------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------


def test_motion_panel_shows_the_stack(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_motion
    s = scene.fresing
    tr = ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], P, Y, name="Lift Y")
    joints.create(scene, "ROTATE", [ob(scene, "BOOM.ASM")], P, Y, name="Luff")
    joints.create(scene, "SLIDE", [tr], P, X, name="Travel X")
    icons = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys()
    texts, errors = [], []

    class FL(FakeLayout):
        def label(self, *a, text="", icon="NONE", **k):
            texts.append(text)
            if icon not in icons:
                errors.append(f"unknown icon {icon}")

        def operator(self, idname, *a, text="", **k):
            texts.append(text)
            return super().operator(idname, *a, **k)

        def prop(self, data, name, *a, **k):
            if name.startswith('["'):
                return
            super().prop(data, name, *a, **k)

        def _child(self, *a, **k):
            return FL(self.errors)

        row = column = box = split = _child

        def panel(self, idname, default_closed=False):
            return FL(self.errors), FL(self.errors)      # the folded part is drawn too

    def draw():
        texts.clear()
        fake = type("P", (), {"layout": FL(errors)})()
        ui_motion.FRESING_PT_motion.draw(fake, bpy.context)
        return " ".join(texts)                          # wrapped lines read as one sentence again

    # selection that already moves with a joint: Add says it goes on top
    for o in bpy.context.selected_objects:
        o.select_set(False)
    tr.select_set(True)
    assert "Adds a joint on top of 'Travel X'" in draw()
    ob(scene, "COVER").select_set(True)
    assert "one at a time" in draw()
    # the joint list: the stack under its bottom joint, indented
    order, depths = joints.tree_order(scene)
    assert [s.joints[i].name for i in order] == ["Lift Y", "Travel X", "Luff"]
    assert [depths[i] for i in order] == [0, 1, 0]
    flags, neworder = ui_motion.FRESING_UL_joints.filter_items(
        type("L", (), {"bitflag_filter_item": 1 << 30, "filter_name": ""})(), bpy.context, s, "joints")
    assert neworder == [0, 2, 1] and all(flags)
    for item in s.joints:
        ui_motion.FRESING_UL_joints.draw_item(None, bpy.context, FL(errors), s, item, 0, s, "", 0)
    # the top joint's details: rides on, swap
    s.joints_index = 2
    text = draw()
    assert "Rides on 'Lift Y'" in text and "Swap order" in text, text
    s.joints_index = 0
    text = draw()
    assert "Carries: 'Travel X'" in text and "Moves: TROLLEY.ASM" in text, text
    assert not errors, errors


def test_swap_and_remove_buttons(scene):
    tr = ob(scene, "TROLLEY.ASM")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    tr.select_set(True)
    bpy.context.view_layer.objects.active = tr
    s = scene.fresing
    assert bpy.ops.fresing.joint_add(kind="SLIDE", axis="Y", origin="CENTER") == {"FINISHED"}
    assert bpy.ops.fresing.joint_add(kind="ROTATE", axis="Z", origin="CENTER") == {"FINISHED"}
    assert len(s.joints) == 2 and joints.rides_on(scene, s.joints[1]).name == s.joints[0].name
    s.joints_index = 0
    assert not bpy.ops.fresing.joint_swap.poll()           # the bottom joint has nothing to swap with
    s.joints_index = 1
    assert bpy.ops.fresing.joint_swap() == {"FINISHED"}
    assert joints.rides_on(scene, s.joints[0]).name == s.joints[1].name
    assert bpy.ops.fresing.joint_members(action="SELECT") == {"FINISHED"}
    assert tr.select_get()
    s.joints_index = 1                                     # the bottom one now: its rider moves down
    assert bpy.ops.fresing.joint_remove() == {"FINISHED"}
    assert len(s.joints) == 1 and joints.rides_on(scene, s.joints[0]) is None
    assert "now rides on what it sat on" in s.last_message
    assert logic.part_count(build.model_roots(scene)[0]) == 12


# ---------------------------------------------------------------------------
# found in the independent review
# ---------------------------------------------------------------------------


def test_update_keeps_a_stack_whose_bottom_sits_on_nothing(scene):
    """The bottom joint moves nothing itself; with its 'Sits on' cleared, a model update left it
    out and the joint on top lost the bottom joint's move."""
    q0 = trolley_point(scene)
    two_slides(scene, y_first=0.2)
    joints.set_base(scene, J(scene, "Lift Y"), None)
    joints.set_value(J(scene, "Travel X"), 0.1)
    update()
    assert close(trolley_point(scene) - q0, (0.1, 0.2, 0))
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    s = scene.fresing
    assert len(s.joints) == 2 and not len(s.report_notes), [n.text for n in s.report_notes]
    assert joints.rides_on(scene, J(scene, "Travel X")).name == "Lift Y"
    assert joints.members(J(scene, "Travel X")) == [ob(scene, "TROLLEY.ASM")]
    assert close(trolley_point(scene) - q0, (0.1, 0.2, 0))


def test_broken_bottom_joint(scene):
    """The bottom joint's arrow is deleted: Swap order says so (no crash), and removing it puts
    the joint on top where its parts belong."""
    q0 = trolley_point(scene)
    two_slides(scene, y_first=0.2)
    joints.set_value(J(scene, "Travel X"), 0.1)
    update()
    bpy.data.objects.remove(J(scene, "Lift Y").frame, do_unlink=True)      # the user deletes the arrow
    update()
    s = scene.fresing
    top = J(scene, "Travel X")
    assert "broken" in joints.swap_check(scene, top)
    s.joints_index = list(s.joints).index(top)
    with pytest.raises(RuntimeError, match="broken"):     # the error message (a report in the app)
        bpy.ops.fresing.joint_swap()
    joints.remove(scene, J(scene, "Lift Y"))
    update()
    top = J(scene, "Travel X")
    assert joints.is_valid(top) and joints.rides_on(scene, top) is None
    assert top.frame.parent is build.model_roots(scene)[0]
    assert close(trolley_point(scene) - q0, (0.1, 0, 0)), trolley_point(scene) - q0
    joints.set_value(top, 0.0)
    update()
    assert close(trolley_point(scene), q0)


def test_add_and_remove_on_the_bottom_joint(scene):
    """Add on the bottom joint must not take the part off the joint on top (that move would be
    lost); Remove there says where the part really is."""
    tr = ob(scene, "TROLLEY.ASM")
    two_slides(scene)
    with pytest.raises(RuntimeError, match="through 'Travel X'"):
        joints.add_members(scene, J(scene, "Lift Y"), [tr])
    assert joints.members(J(scene, "Travel X")) == [tr]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    tr.select_set(True)
    s = scene.fresing
    s.joints_index = list(s.joints).index(J(scene, "Lift Y"))
    assert bpy.ops.fresing.joint_members(action="REMOVE") == {"CANCELLED"}
    assert "remove it there" in s.last_message and joints.members(J(scene, "Travel X")) == [tr]
