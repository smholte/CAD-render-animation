"""Task 0040: the tool library in Blender, on the test gantry (tools/make_test_gantry.py) and the test tools
(tools/make_test_tools.py).

The main check: a program with four tools – face mill, flat end mill, drill, chamfer mill – cuts each feature with
its own tool; depths and widths in the milled block within 0.05 mm of the program.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, gcode, joints, machining, tools  # noqa: E402
from fresing_render.core import tools as tcore  # noqa: E402

HERE = os.path.dirname(__file__)
GANTRY = os.path.join(HERE, "data", "test_gantry.step")
ENDMILL = os.path.join(HERE, "data", "test_tool_endmill.step")
FACEMILL = os.path.join(HERE, "data", "test_tool_facemill.step")
MM = 0.001
STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"

FOUR_TOOLS = """%
(FOUR TOOLS)
G21 G90 G17 G54
T1 M6
S3000 M3
G0 X-180 Y-60 Z5
G1 Z-1 F3000
G1 X180
G0 Z10
T2 M6
S8000 M3
G0 X-50 Y20 Z5
G1 Z-3 F600
G1 X50
G0 Z10
T3 M6
G0 X60 Y60 Z5
G1 Z-10 F200
G0 Z10
T4 M6
G0 X-60 Y60 Z5
G1 Z-2 F200
G0 Z10
M5
M30
%
"""


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=GANTRY, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    return sc


def set_up_cnc(sc):
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    click(ob(sc, T1))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    assert gcode.problem(sc) == ""


def set_up_milling(sc):
    click(ob(sc, T1))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    sc.fresing.milling.detail = "FINE"


def step(sc, path, **kw):
    s = sc.fresing
    a = s.animations.get("Program") or s.animations.add()
    a.name, a.tail = "Program", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    for k, v in kw.items():
        setattr(b, k, v)
    b.gcode_file = path
    return a, b


def row(sc, n, kind, **sizes):
    r = tools.add_row(sc, kind, n)
    for k, v in sizes.items():
        setattr(r, k, v)
    return r


def spindle_tip(sc):
    """T1's tip through its parent (T1 itself is hidden while another tool is in: Blender does not update it)."""
    t1 = ob(sc, T1)
    m = t1.parent.matrix_world @ t1.matrix_parent_inverse @ t1.matrix_basis
    return m @ gcode._rest_tip(t1)[0]


class Block:
    """Ray casts on the milled workpiece, in world coordinates (mm)."""

    def __init__(self, sc):
        wp = ob(sc, STOCK)
        me = wp.data
        mw = wp.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        self.bvh = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons])

    def top(self, x, y):
        """Height (mm) of the first surface straight down at x, y."""
        hit = self.bvh.ray_cast(Vector((x * MM, y * MM, 0.2)), Vector((0, 0, -1)))
        assert hit[0] is not None, (x, y)
        return hit[0].z / MM


# ---------------------------------------------------------------------------


def test_four_tools_cut_each_feature_with_its_own_tool(scene, tmp_path):
    set_up_cnc(scene)
    set_up_milling(scene)
    row(scene, 1, "FACE", diameter=50 * MM, lead_angle=math.radians(90), insert_size=12 * MM)
    row(scene, 2, "FLAT", diameter=8 * MM)
    row(scene, 3, "DRILL", diameter=6 * MM)
    row(scene, 4, "VEE", diameter=10 * MM, angle=math.radians(90))
    p = tmp_path / "four.ngc"
    p.write_text(FOUR_TOOLS)
    a, _b = step(scene, str(p), gcode_tc_time=1.0, gcode_speed="FASTER", gcode_factor=4.0)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sched = gcode.schedule(scene)
    assert [n for _f, n in sched] == [0, 1, 2, 3, 4]
    machining.sample(scene)
    items = machining.cut_items(scene)
    assert [c.tool.kind for c in items] == ["FLAT", "FLAT", "FLAT", "DRILL", "VEE"]    # face mill cuts flat
    assert [round(c.tool.radius / MM, 3) for c in items[1:]] == [25.0, 4.0, 3.0, 5.0]
    scene.frame_set(scene.frame_end)
    assert machining.refresh(scene, force=True)
    blk = Block(scene)
    top = 30.0
    # face mill Ø50 at y = -60, 1 deep: a strip y -85 .. -35
    assert abs(blk.top(0, -60) - (top - 1)) < 0.05
    assert abs(blk.top(0, -84.96) - (top - 1)) < 0.05 and abs(blk.top(0, -85.04) - top) < 0.05
    assert abs(blk.top(0, -35.04) - (top - 1)) < 0.05 and abs(blk.top(0, -34.96) - top) < 0.05
    # end mill Ø8 at y = 20, 3 deep, x -50 .. 50
    assert abs(blk.top(0, 20) - (top - 3)) < 0.05
    assert abs(blk.top(0, 20 - 3.96) - (top - 3)) < 0.05 and abs(blk.top(0, 20 - 4.04) - top) < 0.05
    assert abs(blk.top(0, 20 + 3.96) - (top - 3)) < 0.05 and abs(blk.top(0, 20 + 4.04) - top) < 0.05
    assert abs(blk.top(53.96, 20) - (top - 3)) < 0.05 and abs(blk.top(54.04, 20) - top) < 0.05
    # drill Ø6 118° at (60, 60), tip 10 deep
    assert abs(blk.top(60, 60) - (top - 10)) < 0.05
    assert blk.top(60 + 2.96, 60) < top - 1 and abs(blk.top(60 + 3.04, 60) - top) < 0.05
    cone = (top - 10) + 2.9 / math.tan(math.radians(59))
    assert abs(blk.top(60 + 2.9, 60) - cone) < 0.05
    # chamfer mill 90° at (-60, 60), 2 deep: a cone Ø4 at the top
    assert abs(blk.top(-60, 60) - (top - 2)) < 0.05
    assert abs(blk.top(-60 + 1.5, 60) - (top - 0.5)) < 0.05
    assert abs(blk.top(-60 + 2.04, 60) - top) < 0.05
    # an earlier frame: before T2 cut, the slot is not there yet
    f_t2 = next(f for f, n in sched if n == 2)
    scene.frame_set(int(f_t2))
    machining.refresh(scene, force=True)
    blk = Block(scene)
    assert abs(blk.top(0, 20) - top) < 0.05 and abs(blk.top(0, -60) - (top - 1)) < 0.05


def test_tool_lengths_move_the_spindle(scene, tmp_path):
    set_up_cnc(scene)
    c = scene.fresing.cnc
    r1 = row(scene, 1, "FLAT", diameter=6 * MM)
    tools.use_part(scene, r1, ob(scene, T1))                     # T1 is the part in the spindle: 30 mm out
    assert abs(r1.length - 30 * MM) < 0.05 * MM and abs(r1.diameter - 6 * MM) < 0.05 * MM
    row(scene, 2, "DRILL", diameter=5 * MM, length=50 * MM)      # 20 mm longer
    p = tmp_path / "len.ngc"
    p.write_text("G21 G90 G54\nT1 M6\nG0 X0 Y0 Z20\nT2 M6\nG0 X0 Y0 Z20\nG1 Z10 F600\nM30\n")
    a, _b = step(scene, str(p), gcode_tc_time=1.0)
    assert not animation.bake(scene, a)["warnings"]
    copy = gcode.copies(scene)[2]
    zero = c.zero_empty.matrix_world.translation
    scene.frame_set(scene.frame_end)
    tip = copy.matrix_world @ Vector(copy["fr_tip"])
    assert abs((tip - zero).z - 10 * MM) < 0.01 * MM                # the drill's tip is where the program says
    assert abs((spindle_tip(scene) - tip).z - 20 * MM) < 0.01 * MM   # the spindle went up by 20 mm
    c.tool_lengths = False
    assert not animation.bake(scene, a)["warnings"]
    scene.frame_set(scene.frame_end)
    copy = gcode.copies(scene)[2]
    tip = copy.matrix_world @ Vector(copy["fr_tip"])
    assert (spindle_tip(scene) - tip).length < 0.01 * MM


def test_missing_tool_is_reported_with_its_line(scene, tmp_path):
    set_up_cnc(scene)
    row(scene, 1, "FLAT")
    p = tmp_path / "miss.ngc"
    p.write_text("G21 G90 G54\nT1 M6\nG0 Z20\nT7 M6\nG0 Z30\nM30\n")
    a, b = step(scene, str(p))
    w = animation.bake(scene, a)["warnings"]
    assert any("T7 (line 4) is not in the tool list" in x for x in w), w
    assert gcode.info(scene, b)["missing"] == [(7, 4)]
    gcode._INFO.clear()
    assert bpy.ops.fresing.cnc_tool_add_missing(number=7, kind="DRILL") == {"FINISHED"}
    assert tools.row_of(scene, 7).kind == "DRILL"
    assert gcode.info(scene, b)["missing"] == []


def test_old_project_without_a_list_cuts_as_before(scene):
    """Milling with a fixed bit and no tool list, no G-code: one cut item, the bit's own shape."""
    set_up_milling(scene)
    machining.sample(scene)
    items = machining.cut_items(scene)
    assert len(items) == 1 and items[0].ob is ob(scene, T1)
    assert items[0].tool.kind == "FLAT" and abs(items[0].tool.radius - 3 * MM) < 1e-6


def test_every_type_is_drawn_with_its_holder(scene, tmp_path):
    set_up_cnc(scene)
    kinds = list(tcore.KINDS)
    for n, k in enumerate(kinds, start=1):
        r = row(scene, n, k)
        r.holder = ["NONE", "ER", "SK40", "BT40", "HSK63"][n % 5]
    prog = "G21 G90 G54\n" + "".join(f"T{n} M6\nG0 Z{20 + n}\n" for n in range(1, len(kinds) + 1)) + "M30\n"
    p = tmp_path / "all.ngc"
    p.write_text(prog)
    a, _b = step(scene, str(p), gcode_tc_time=0.5)
    assert not animation.bake(scene, a)["warnings"]
    cps = gcode.copies(scene)
    assert sorted(cps) == list(range(1, len(kinds) + 1))
    for n, k in enumerate(kinds, start=1):
        me = cps[n].data
        spec = tools.spec_from_json(cps[n]["fr_spec"])
        assert spec.kind == k
        v = np.array([x.co for x in me.vertices])
        r = np.hypot(v[:, 0], v[:, 1])
        assert abs(v[:, 2].min()) < 1e-6                           # the tip at the origin
        cut_r = r[(v[:, 2] <= spec.flute_length + 1e-9) & (v[:, 2] < spec.stick_out - 1e-6)].max()
        want = spec.diameter / 2
        if k == "FACE" and spec.lead_angle < 89.9:                 # a 45° face mill widens over its inserts
            want += spec.flute_length / math.tan(math.radians(spec.lead_angle))
        assert abs(cut_r - want) < 0.002 * want + 1e-5, (k, cut_r, want)
        has_holder = spec.holder != "NONE"
        assert (len(me.materials) == 2) and (any(p.material_index == 1 for p in me.polygons) == has_holder)
    # sizes changed in the list: the copy follows at once
    tools.row_of(scene, 2).diameter = 9 * MM
    me = gcode.copies(scene)[2].data
    v = np.array([x.co for x in me.vertices])
    tool_part = v[:, 2] < tools.spec_of(tools.row_of(scene, 2)).stick_out - 1e-6     # (not its holder)
    assert abs(np.hypot(v[tool_part, 0], v[tool_part, 1]).max() - 4.5 * MM) < 1e-5


def test_fluted_end_mill_step_read_right(scene):
    """0037 problem 2: a fluted Ø12 end mill (end teeth, corner chamfer) was read as a smaller flat mill."""
    r = row(scene, 5, "FLAT")
    guess = tools.import_step(scene, r, ENDMILL)
    assert r.step_mesh is not None
    tip, axis = Vector(r.tip) / MM, Vector(r.axis)
    assert (tip - Vector((10, 20, 30))).length < 0.05
    assert (axis - Vector((0.6, 0, 0.8))).length < 0.001
    assert guess.kind == "FLAT" and r.kind == "FLAT"
    assert abs(r.diameter / MM - 12.0) < 0.1
    assert abs(r.length / MM - 72.0) < 0.1                          # no holder: all of it sticks out
    # flip and back: the same
    tools.flip_step(scene, r)
    tools.flip_step(scene, r)
    assert (Vector(r.tip) / MM - Vector((10, 20, 30))).length < 0.05


def test_fluted_end_mill_part_detected_right(scene):
    """The same end mill as a part of the model: milling's own detection reads Ø12 too."""
    assert bpy.ops.fresing.import_step(filepath=ENDMILL, quality="normal") == {"FINISHED"}
    part = ob(scene, "END MILL D12 Z3")
    info = machining.detect(part)
    assert info["tool"].kind == "FLAT" and abs(info["tool"].radius * 2 / MM - 12.0) < 0.1
    tip = part.matrix_world @ Vector(info["tip"])
    assert (tip / MM - Vector((10, 20, 30))).length < 0.05


def test_face_mill_with_holder_step(scene):
    r = row(scene, 3, "FLAT")
    tools.import_step(scene, r, FACEMILL)
    assert (Vector(r.tip) / MM).length < 0.05 and (Vector(r.axis) - Vector((0, 0, 1))).length < 1e-3
    assert r.kind == "FACE"
    assert abs(r.diameter / MM - 2 * math.hypot(25.0, 1.75)) < 0.1   # the inserts' outer corners
    assert abs(r.length / MM - 40.0) < 0.1                          # stick-out: up to the holder's nose
    assert abs(r.insert_size / MM - 12.0) < 0.2


def test_reading_tool_files_into_the_list(scene, tmp_path):
    p = tmp_path / "lib.json"
    p.write_text('{"data": [{"type": "flat end mill", "description": "EM 8", "unit": "millimeters", '
                 '"geometry": {"DC": 8, "LCF": 20, "LB": 35, "NOF": 3}, "post-process": {"number": 2}}, '
                 '{"type": "lollipop mill", "description": "LP 6", "geometry": {"DC": 6}, '
                 '"post-process": {"number": 9}}]}')
    res = tools.read_file(scene, str(p))
    assert res["added"] == 2
    assert tools.row_of(scene, 2).kind == "FLAT" and abs(tools.row_of(scene, 2).length - 35 * MM) < 1e-9
    assert tools.row_of(scene, 9).kind == "BALL" and "lollipop" in tools.row_of(scene, 9).note
    t = tmp_path / "tool.tbl"
    t.write_text("T2 P2 D8.5 Z+40.0 ;8.5 drill\nT3 P5 D10 Z+50 ;face mill\n")
    res = tools.read_file(scene, str(t))
    assert (res["added"], res["updated"]) == (1, 1)
    assert tools.row_of(scene, 2).kind == "DRILL" and abs(tools.row_of(scene, 2).diameter - 8.5 * MM) < 1e-9
    assert tools.row_of(scene, 3).pocket == 5
    assert [x.number for x in scene.fresing.cnc.tools] == [2, 3, 9]     # sorted by T


def test_list_saved_and_opened_again(scene, tmp_path):
    row(scene, 4, "SLOT", diameter=30 * MM)
    r = row(scene, 6, "FLAT")
    tools.import_step(scene, r, ENDMILL)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert tools.row_of(sc, 4).kind == "SLOT" and abs(tools.row_of(sc, 4).diameter - 30 * MM) < 1e-9
    r = tools.row_of(sc, 6)
    assert r.step_mesh is not None and len(r.step_mesh.vertices) > 1000


def test_copy_sort_and_remove(scene):
    row(scene, 5, "BALL")
    row(scene, 2, "DRILL")
    c = scene.fresing.cnc
    tools.copy_row(scene, 0)
    assert [t.number for t in c.tools] == [5, 2, 1]
    assert c.tools[2].kind == "BALL"
    tools.sort_rows(scene)
    assert [t.number for t in c.tools] == [1, 2, 5]
    tools.remove_row(scene, 0)
    assert [t.number for t in c.tools] == [2, 5]


def test_type_change_gives_that_types_sizes(scene):
    r = row(scene, 1, "FLAT")
    r.kind = "DRILL"
    assert abs(math.degrees(r.angle) - 118) < 1e-4
    r.kind = "VEE"
    assert abs(math.degrees(r.angle) - 90) < 1e-4
    r.kind = "FACE"
    assert abs(math.degrees(r.lead_angle) - 45) < 1e-4


def test_a_tool_too_big_for_the_machine_warns(scene):
    set_up_cnc(scene)
    z = scene.fresing.joints["Z"]
    z.use_limits, z.slide_min, z.slide_max = True, -0.1, 0.0           # 100 mm of Z travel
    row(scene, 1, "FLAT", length=150 * MM)
    w = tools.checks(scene)
    assert any("further than the machine's Z travel" in x for x in w), w
    assert len(scene.fresing.cnc.tools) == 1                          # a warning, nothing refused
