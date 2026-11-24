"""Task 0290: several parts or subassemblies per cylinder item, the Joints fold, what a clicked joint shows.

Test model: the luffer's revision C (tools/make_test_cylinder.py C): the cylinder at y = 0.96 is SPLIT.ASM, whose
barrel is 3 parts in 2 subassemblies (SPLIT.BARREL = BARREL.CAP + BARREL.TUBE, SPLIT.HEAD = BARREL.GLAND) and whose
rod is 2 loose parts (SPLIT.ROD = piston + rod, ROD.EYE). Its geometry is that of revision A's cylinders, so the hand
calculation of tests/test_cylinders.py holds: closed length 1.09279 m, full stroke 0.570 m.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

HERE = os.path.dirname(__file__)
LUFFER_C = os.path.join(HERE, "data", "test_cylinder_c.step")
Y = Vector((0, 1, 0))
P0 = Vector((0.3, 0.6, 1.8))
B0 = Vector((1.5, 0.0, 0.45))
R00 = Vector((2.4, 0.0, 1.35))
SPLIT_Y = 0.96
L0 = math.hypot(0.9, 0.9)
CLOSED, FULL = L0 - 0.18, 0.57

import fresing_render  # noqa: E402
from fresing_render.blender import build, cylinders, joint_show, joints, ops_cylinders  # noqa: E402


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
    assert bpy.ops.fresing.import_step(filepath=LUFFER_C, quality="draft") == {"FINISHED"}
    return sc


def update():
    bpy.context.view_layer.update()


def one(sc, name, y=None):
    """The object with this CAD name (in the cylinder at ``y`` when there are several)."""
    found = []
    for o in sc.objects:
        if o.get(build.PROP_NAME) != name:
            continue
        parts = [o] if o.type == "MESH" else [d for d in o.children_recursive if d.type == "MESH"]
        ys = [(d.matrix_world @ Vector(c)).y for d in parts for c in d.bound_box]
        if y is None or min(ys) - 1e-4 <= y <= max(ys) + 1e-4:
            found.append(o)
    assert len(found) == 1, (name, y, [o.name for o in found])
    return found[0]


def select(sc, *objs):
    for o in sc.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = None    # (an active part would select its whole subassembly)
    for o in objs:
        o.select_set(True)


def picks(coll):
    return [r.obj.get(build.PROP_NAME) for r in coll if r.obj is not None]


def pick(sc, role, *objs, action="ADD", index=-1):
    select(sc, *objs)
    return bpy.ops.fresing.cylinder_pick_parts(role=role, action=action, index=index)


def at(v, y):
    return Vector((v.x, y, v.z))


def split_cylinder(sc, name="Split"):
    barrel = [one(sc, "SPLIT.BARREL"), one(sc, "SPLIT.HEAD")]
    rod = [one(sc, "SPLIT.ROD"), one(sc, "ROD.EYE", SPLIT_Y)]
    c, notes = cylinders.create(sc, barrel, rod, (at(B0, 0.0), Y, one(sc, "BASE.PIN")),
                                (at(R00, 1.2), -Y, one(sc, "ARM.ROD.PIN")), name=name)
    update()
    return c


# ---------------------------------------------------------------------------------------------------------------
# picking before Add cylinder
# ---------------------------------------------------------------------------------------------------------------

def test_add_selected_keeps_the_picks_and_adds(scene):
    s = scene.fresing
    assert pick(scene, "BARREL", one(scene, "SPLIT.BARREL")) == {"FINISHED"}
    assert pick(scene, "BARREL", one(scene, "SPLIT.HEAD")) == {"FINISHED"}
    assert picks(s.cyl_pick_barrel) == ["SPLIT.BARREL", "SPLIT.HEAD"]        # added, not replaced
    # Shift+click: two selected at once, one already there -> only the new one is added
    assert pick(scene, "ROD", one(scene, "SPLIT.ROD"), one(scene, "ROD.EYE", SPLIT_Y)) == {"FINISHED"}
    assert pick(scene, "ROD", one(scene, "SPLIT.ROD")) == {"FINISHED"}
    assert picks(s.cyl_pick_rod) == ["SPLIT.ROD", "ROD.EYE"]


def test_a_part_inside_a_picked_subassembly_is_not_picked_twice(scene):
    s = scene.fresing
    pick(scene, "BARREL", one(scene, "BARREL.CAP", SPLIT_Y))
    pick(scene, "BARREL", one(scene, "SPLIT.BARREL"))                         # the subassembly takes its place
    assert picks(s.cyl_pick_barrel) == ["SPLIT.BARREL"]
    pick(scene, "BARREL", one(scene, "BARREL.TUBE", SPLIT_Y))                 # inside it already: skipped
    assert picks(s.cyl_pick_barrel) == ["SPLIT.BARREL"]


def test_x_drops_one_and_clear_empties(scene):
    s = scene.fresing
    pick(scene, "BARREL", one(scene, "SPLIT.BARREL"), one(scene, "SPLIT.HEAD"))
    assert len(picks(s.cyl_pick_barrel)) == 2
    assert pick(scene, "BARREL", action="DROP", index=0) == {"FINISHED"}
    assert picks(s.cyl_pick_barrel) == ["SPLIT.HEAD"]
    assert pick(scene, "BARREL", action="DROP", index=5) == {"CANCELLED"}
    assert pick(scene, "BARREL", action="CLEAR") == {"FINISHED"}
    assert picks(s.cyl_pick_barrel) == []


def test_a_part_is_never_in_both_items(scene):
    """Adding a part to the rod takes it (or the subassembly holding it) off the barrel."""
    s = scene.fresing
    pick(scene, "BARREL", one(scene, "SPLIT.BARREL"), one(scene, "SPLIT.HEAD"))
    pick(scene, "ROD", one(scene, "BARREL.CAP", SPLIT_Y))
    assert picks(s.cyl_pick_barrel) == ["SPLIT.HEAD"]
    assert picks(s.cyl_pick_rod) == ["BARREL.CAP"]
    assert "taken off the barrel" in s.last_message


def test_nothing_selected_says_so(scene):
    select(scene)
    assert bpy.ops.fresing.cylinder_pick_parts(role="ROD") == {"CANCELLED"}


# ---------------------------------------------------------------------------------------------------------------
# a cylinder made of several parts per item
# ---------------------------------------------------------------------------------------------------------------

def test_travel_read_from_all_picked_parts(scene):
    """The gland (in its own subassembly) and the piston (in the loose rod part) set the stroke: both are read."""
    c = split_cylinder(scene)
    assert len(cylinders.barrel_objs(c)) == 2 and len(cylinders.rod_objs(c)) == 2
    assert c.measured
    assert c.closed_length == pytest.approx(CLOSED, abs=2e-4)
    assert c.full_stroke == pytest.approx(FULL, abs=2e-4)


def test_all_picked_parts_move_with_the_cylinder(scene):
    j = joints.create(scene, "ROTATE", [one(scene, "ARM.ASM")], P0, Y, name="Luff")
    c = split_cylinder(scene)
    parts = {n: one(scene, n, SPLIT_Y) for n in ("BARREL.CAP", "BARREL.TUBE", "BARREL.GLAND", "SPLIT.ROD",
                                                 "ROD.EYE")}
    before = {n: o.matrix_world.copy() for n, o in parts.items()}
    corner = {n: Vector(o.bound_box[6]) for n, o in parts.items()}
    joints.set_value(j, math.radians(15), use_limits=False)
    update()
    moved = {n: (o.matrix_world @ corner[n] - before[n] @ corner[n]).length for n, o in parts.items()}
    assert all(v > 1e-3 for v in moved.values()), moved
    # the barrel's three parts turn together (one rigid body), the rod's two parts slide together
    rel = before["BARREL.CAP"].inverted() @ before["BARREL.GLAND"]
    assert (parts["BARREL.CAP"].matrix_world @ rel - parts["BARREL.GLAND"].matrix_world).to_translation().length < 1e-5
    rel = before["SPLIT.ROD"].inverted() @ before["ROD.EYE"]
    assert (parts["SPLIT.ROD"].matrix_world @ rel - parts["ROD.EYE"].matrix_world).to_translation().length < 1e-5
    # and the stroke shortened as the hand calculation says
    r = P0 + Matrix.Rotation(math.radians(15), 3, "Y") @ (at(R00, 0.6) - P0)
    assert cylinders.length_now(c) == pytest.approx((Vector((r.x, 0, r.z)) - at(B0, 0)).length, abs=1e-5)


def test_add_cylinder_button_uses_every_pick(scene):
    """The picks go to Add cylinder; after it the lists are empty again."""
    s = scene.fresing
    pick(scene, "BARREL", one(scene, "SPLIT.BARREL"), one(scene, "SPLIT.HEAD"))
    pick(scene, "ROD", one(scene, "SPLIT.ROD"), one(scene, "ROD.EYE", SPLIT_Y))
    barrel = [r.obj for r in s.cyl_pick_barrel]
    rod = [r.obj for r in s.cyl_pick_rod]
    assert cylinders.check_parts(scene, barrel, rod) == ""


def test_set_up_fold_adds_and_drops_and_reads_the_travel_again(scene):
    """4 Motion > Cylinders > Set-up: Add selected adds to an item, × drops one, the travel is read again."""
    s = scene.fresing
    barrel = [one(scene, "SPLIT.BARREL")]
    rod = [one(scene, "SPLIT.ROD"), one(scene, "ROD.EYE", SPLIT_Y)]
    c, _n = cylinders.create(scene, barrel, rod, (at(B0, 0.0), Y, one(scene, "BASE.PIN")),
                             (at(R00, 1.2), -Y, one(scene, "ARM.ROD.PIN")), name="Split")
    update()
    s.cylinders_index = 0
    full_without_gland = c.full_stroke
    select(scene, one(scene, "SPLIT.HEAD"))
    assert bpy.ops.fresing.cylinder_parts(action="BARREL") == {"FINISHED"}
    c = cylinders.find(scene, "Split")
    assert [o.get(build.PROP_NAME) for o in cylinders.barrel_objs(c)] == ["SPLIT.BARREL", "SPLIT.HEAD"]
    assert c.full_stroke == pytest.approx(FULL, abs=2e-4)                    # the gland stops the piston now
    assert abs(full_without_gland - FULL) > 1e-3
    # × on the rod's eye
    assert bpy.ops.fresing.cylinder_parts(action="DROP", role="ROD", index=1) == {"FINISHED"}
    c = cylinders.find(scene, "Split")
    assert [o.get(build.PROP_NAME) for o in cylinders.rod_objs(c)] == ["SPLIT.ROD"]
    # the last one of an item stays: a rod needs a part
    assert bpy.ops.fresing.cylinder_parts(action="DROP", role="ROD", index=0) == {"CANCELLED"}
    # a part of the rod cannot go into the barrel too
    select(scene, one(scene, "SPLIT.ROD"))
    assert bpy.ops.fresing.cylinder_parts(action="BARREL") == {"CANCELLED"}


def test_pins_again_and_remove_still_work(scene):
    c = split_cylinder(scene)
    name = c.name
    c2 = ops_cylinders.repin(scene, c, (at(B0, 0.1), Y, one(scene, "BASE.PIN")),
                             (at(R00, 1.0), Y, one(scene, "ARM.ROD.PIN")))
    c2 = cylinders.find(scene, name)
    assert c2 is not None and len(cylinders.barrel_objs(c2)) == 2 and len(cylinders.rod_objs(c2)) == 2
    cap = one(scene, "BARREL.CAP", SPLIT_Y)
    cylinders.remove(scene, c2)
    update()
    assert not len(scene.fresing.cylinders)
    assert cylinders.cylinder_of_object(scene, cap) is None


def test_crane_set_up_step_takes_the_lists(scene, monkeypatch):
    """The Set-up window's cylinder step (Set up a crane): the barrel and rod lists go to make_cylinder whole."""
    from fresing_render.blender import setup_crane
    got = {}

    def fake(sc, role, barrel, rod):
        got.update(role=role, barrel=[o.name for o in barrel], rod=[o.name for o in rod])
        return "X"
    monkeypatch.setattr(setup_crane, "make_cylinder", fake)
    pick(scene, "BARREL", one(scene, "SPLIT.BARREL"), one(scene, "SPLIT.HEAD"))
    pick(scene, "ROD", one(scene, "SPLIT.ROD"), one(scene, "ROD.EYE", SPLIT_Y))
    assert bpy.ops.fresing.crane_cylinder(role="luff") == {"FINISHED"}
    assert len(got["barrel"]) == 2 and len(got["rod"]) == 2
    assert not len(scene.fresing.cyl_pick_barrel) and not len(scene.fresing.cyl_pick_rod)


def test_make_cylinder_with_several_parts_per_item(scene):
    """setup_crane.make_cylinder with lists: the pins are the eyes' round faces of all the picked parts."""
    from fresing_render.blender import setup_crane
    j = joints.create(scene, "ROTATE", [one(scene, "ARM.ASM")], P0, Y, name="Luff")
    j.role = "luff"
    name = setup_crane.make_cylinder(scene, "luff", [one(scene, "SPLIT.BARREL"), one(scene, "SPLIT.HEAD")],
                                     [one(scene, "SPLIT.ROD"), one(scene, "ROD.EYE", SPLIT_Y)])
    c = cylinders.find(scene, name)
    update()
    assert len(cylinders.barrel_objs(c)) == 2 and len(cylinders.rod_objs(c)) == 2
    assert cylinders.length_now(c) == pytest.approx(L0, abs=1e-3)


# ---------------------------------------------------------------------------------------------------------------
# the Joints fold, what a clicked joint shows
# ---------------------------------------------------------------------------------------------------------------

def test_joints_fold_is_a_sub_panel_of_4_motion():
    from fresing_render.core import functions, places
    assert places.where("joints") == "4 Motion > Joints"
    assert places.children("FRESING_PT_motion")[0] == "FRESING_PT_joints"
    assert functions.FUNCTIONS["joints.rotate"].panel == "FRESING_PT_joints"
    assert hasattr(bpy.types, "FRESING_PT_joints")


def test_clicking_a_joint_shows_what_it_moves(scene):
    s = scene.fresing
    luff = joints.create(scene, "ROTATE", [one(scene, "ARM.ASM"), one(scene, "SPLIT.ASM")], P0, Y, name="Luff")
    rider = joints.create(scene, "SLIDE", [one(scene, "SPLIT.ASM")], P0, Vector((1, 0, 0)), name="Slide")
    assert joints.rides_on(scene, rider) is not None
    luff = s.joints["Luff"]
    s.joints_index = 0                                       # a click on "Luff" in the list
    shown = joint_show.active()
    assert shown["kind"] == "joint" and shown["name"] == "Luff"
    arm_parts = {o.name for o in one(scene, "ARM.ASM").children_recursive if o.type == "MESH"}
    split_parts = {o.name for o in one(scene, "SPLIT.ASM").children_recursive if o.type == "MESH"}
    assert set(shown["main"]) == arm_parts and set(shown["riders"]) == split_parts   # the rider lighter
    # nothing is selected by it: a following G acts on what the user picked
    assert not [o for o in scene.objects if o.select_get()]
    # a hidden part stays hidden and is counted
    one(scene, "ARM.BRACKET").hide_set(True)
    assert joint_show.hidden_count(scene, luff) == 1
    # another joint replaces it; clear() ends it
    s.joints_index = 1
    assert joint_show.active()["name"] == "Slide"
    joint_show.clear()
    assert joint_show.active()["kind"] == ""


def test_the_show_ends_when_the_selection_changes(scene):
    s = scene.fresing
    joints.create(scene, "ROTATE", [one(scene, "ARM.ASM")], P0, Y, name="Luff")
    from fresing_render.blender import panels
    panels.open_to("FRESING_PT_joints")
    s.joints_index = 0
    assert joint_show.still_wanted()
    one(scene, "POST").select_set(True)                       # a click elsewhere
    assert not joint_show.still_wanted()
    joint_show.clear()


def test_arrow_lines():
    lines = joint_show.axis_lines(Vector((0, 0, 0)), Vector((0, 0, 2)), 1.0, rotate=True)
    assert len(lines) % 2 == 0 and len(lines) == 2 + 8 + 64
    tip = max(lines, key=lambda p: p.z)
    assert tip.z == pytest.approx(1.0)
    assert len(joint_show.axis_lines(Vector((0, 0, 0)), Vector((1, 0, 0)), 1.0, rotate=False)) == 10


def test_list_rows_have_a_tooltip():
    s = bpy.types.FRSceneSettings if hasattr(bpy.types, "FRSceneSettings") else None
    props = bpy.context.scene.fresing.bl_rna.properties
    assert "light up" in props["joints_index"].description
    assert "light up" in props["mechanisms_index"].description
    assert s is None or s


# ---------------------------------------------------------------------------------------------------------------
# the panel stays still (owner 23 Nov 2026)
# ---------------------------------------------------------------------------------------------------------------

class _Rec:
    """A stand-in layout: records each row drawn (label / operator / prop texts) in order."""

    def __init__(self, out=None, depth=0):
        self.out = out if out is not None else []
        self.depth = depth
        self.alert = False
        self.enabled = True
        self.scale_y = 1.0
        self.ui_units_x = 0
        self.alignment = "EXPAND"
        self.active = True
        self.use_property_split = False
        self.use_property_decorate = False
        self.scale_x = 1.0
        self.emboss = "NORMAL"

    def _child(self):
        self.out.append(("row", self.depth))
        return _Rec(self.out, self.depth + 1)

    def row(self, **k):
        return self._child()

    column = box = split = row

    def column_flow(self, **k):
        return self._child()

    grid_flow = column_flow

    def label(self, text="", **k):
        self.out.append(("label", text))

    def operator(self, idname, text="", **k):
        self.out.append(("op", idname, text))

        class _P:
            pass
        return _P()

    def prop(self, data, prop, text="", **k):
        self.out.append(("prop", prop, text))

    def prop_search(self, data, prop, *a, text="", **k):
        self.out.append(("prop", prop, text))

    def separator(self, **k):
        self.out.append(("sep",))

    def template_list(self, *a, **k):
        self.out.append(("list",))

    def panel(self, *a, **k):
        return self._child(), self._child()

    def progress(self, **k):
        self.out.append(("progress",))

    def operator_menu_enum(self, *a, **k):
        self.out.append(("menu",))

    def menu(self, *a, **k):
        self.out.append(("menu",))

    def popover(self, *a, **k):
        self.out.append(("popover",))

    def context_pointer_set(self, *a):
        pass


def _rows(scene):
    from fresing_render.blender import ui_motion
    rec = _Rec()
    ui_motion._draw_joints(bpy.context, rec, scene.fresing)
    return rec.out


def test_beyond_limits_stays_on_the_value_row(scene):
    """A follower past its limits: the warning sits on the value row; the rows under it keep their place."""
    s = scene.fresing
    lead = joints.create(scene, "ROTATE", [one(scene, "ARM.ASM")], P0, Y, name="Lead")
    fol = joints.create(scene, "SLIDE", [one(scene, "SPLIT.ASM")], Vector((0, 0, 0)), Vector((1, 0, 0)),
                        name="Follower")
    joints.set_follows(scene, fol, lead.name, ratio=200.0)       # 200 mm per turn
    fol = s.joints["Follower"]
    fol.use_limits = True
    fol.slide_min, fol.slide_max = 0.0, 0.05
    s.joints_index = list(s.joints).index(fol)
    lead = s.joints["Lead"]
    joints.set_value(lead, math.radians(10), use_limits=False)
    update()
    inside = _rows(scene)
    assert not joints.outside_limits(fol, joints.get_value(fol))
    joints.set_value(lead, math.radians(300), use_limits=False)
    update()
    assert joints.outside_limits(fol, joints.get_value(fol))
    beyond = _rows(scene)
    assert ("op", "fresing.limits_note", "Beyond limits") in beyond
    assert not any(e[0] == "label" and "Beyond its limits" in e[1] for e in beyond)
    # the same rows in the same order: nothing came in between, nothing moved down

    def shape(rows):
        return ["item" if e[0] in ("label", "op") else e[0] for e in rows]
    assert shape(inside) == shape(beyond), (len(inside), len(beyond))
    joint_show.clear()
