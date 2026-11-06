"""Task 0026: G-code programs drive the machine, in Blender, on the test gantry (tools/make_test_gantry.py).

The gantry: Y moves the gantry, X the carriage on it, Z the head; all three move the tool. The flat Ø6 tool
T1 has its tip at (0, 0, 80) mm; the stock is x -150..150, y -100..100, z 0..30. The carousel (beside the
bed, turning about x = 500, y = 0) holds T2 (ball Ø4, tip (560, 0, 110)) and T3 (drill Ø5, tip (500, 60, 100)).

The check of every motion test: the tool's tip, measured in the work zero's frame from the evaluated
objects, against the program's point at that moment (worked out by the reader), within 0.01 mm.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, gcode, joints  # noqa: E402
from fresing_render.core import gcode as core  # noqa: E402

HERE = os.path.dirname(__file__)
GANTRY = os.path.join(HERE, "data", "test_gantry.step")
MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"

PROGRAM = """%
(TEST PART)
(T1  D=6. CR=0. - ZMIN=-3. - flat end mill)
G90 G94 G17 G91.1 G21
G54
S10000 M3
G0 X-50 Y-40 Z5
G1 Z-2 F600
G1 X40 F1200
G2 X60 Y-20 I0 J20
G3 X40 Y0 R20
G18 G2 X20 Z-2 I-10 K0
G19 G3 Y20 Z-2 J10 K0
G17
G91 G1 X-10 Y-10
G90
G3 X10 Y10 Z-3 I0 J10 P2
G0 Z10
G98 G81 X-100 Y60 Z-5 R2 F300
X-80
G80
G53 G0 Z0
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


def set_up(sc):
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    click(ob(sc, T1))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    assert gcode.problem(sc) == ""


def program(tmp_path, text=PROGRAM, name="part.ngc"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


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


def near(a, b, tol) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(tuple(a), tuple(b)))


def tip_in_zero(sc, tool=T1):
    t = ob(sc, tool)
    tip = gcode._rest_tip(t)[0]
    z = sc.fresing.cnc.zero_empty
    return z.matrix_world.inverted() @ (t.matrix_world @ tip)


def check_path(sc, a, b, frames, subframes=False, tool=T1):
    """Worst distance (mm) between the tip and the program's point over the given frames."""
    sc.frame_set(1)
    mach = gcode.Machine(sc)
    sch = core.Schedule(gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0], gcode.timing(sc, a, b))
    f0 = animation.frame_of(a, b.start)
    fps = animation.fps_of(a)
    worst = 0.0
    for f in frames:
        for sub in ((0.0, 0.37, 0.5) if subframes else (0.0,)):
            sc.frame_set(f, subframe=sub)
            got = tip_in_zero(sc, tool) / MM
            want = Vector(sch.point_at((f + sub - f0) / fps)) - Vector(mach.g54)
            if (got - want).length > worst:
                worst = (got - want).length
                check_path.where = (f, sub, tuple(got), tuple(want))
    return worst


# ---------------------------------------------------------------------------
# the set-up
# ---------------------------------------------------------------------------

def test_axes_found_and_the_work_zero(scene):
    set_up(scene)
    c = scene.fresing.cnc
    assert (c.x_joint, c.y_joint, c.z_joint) == ("X", "Y", "Z")
    m = gcode.Machine(scene)
    assert m.moves_tool == [True, True, True] and m.sign == [1.0, 1.0, 1.0]
    # top centre of the stock is (0, 0, 30); the tip at (0, 0, 80) mm: the machine is 50 mm above the zero
    assert near(Vector(m.g54), (0, 0, -50), 1e-3)
    assert near(Vector(c.zero_empty.matrix_world.translation) / MM, (0, 0, 30), 1e-3)
    c.zero_mode = "TOP_FL"
    m = gcode.Machine(scene)
    assert near(Vector(m.g54), (-150, -100, -50), 1e-3)
    c.zero_mode = "BOTTOM_CENTRE"
    c.zero_shift = (10 * MM, 0, 0)
    assert near(Vector(gcode.Machine(scene).g54), (10, 0, -80), 1e-3)


def test_clicked_zero_snaps_to_a_corner(scene):
    set_up(scene)
    stock = ob(scene, STOCK)
    gcode.set_zero_point(scene, stock, Vector((148 * MM, 98.5 * MM, 30 * MM)))   # 2 mm from the corner
    c = scene.fresing.cnc
    assert c.zero_mode == "POINT"
    assert near(Vector(c.zero_point) / MM, (150, 100, 30), 1e-3)
    gcode.set_zero_point(scene, stock, Vector((20 * MM, 10 * MM, 30 * MM)))      # mid face: stays as clicked
    assert near(Vector(c.zero_point) / MM, (20, 10, 30), 1e-3)


def test_missing_set_up_says_what_to_do(scene):
    assert "X joint" in gcode.problem(scene)
    bpy.ops.fresing.cnc_find_axes()
    assert "tool" in gcode.problem(scene).lower()
    click(ob(scene, T1))
    bpy.ops.fresing.cnc_use_tool()
    assert "workpiece" in gcode.problem(scene).lower()


def test_reverse_flips_an_axis(scene, tmp_path):
    set_up(scene)
    scene.fresing.cnc.x_reverse = True
    a, b = step(scene, program(tmp_path, "G0 X20 Y0 Z0\nM30\n"))
    animation.bake(scene, a)
    scene.frame_set(scene.frame_end)
    assert joints.get_value(scene.fresing.joints["X"]) == pytest.approx(-20 * MM, abs=1e-7)


# ---------------------------------------------------------------------------
# motion
# ---------------------------------------------------------------------------

def test_the_tool_tip_follows_the_program(scene, tmp_path):
    set_up(scene)
    a, b = step(scene, program(tmp_path))
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    assert r["frames"] == math.ceil(1 + b.duration * 25 - 1e-3)       # the last move ends inside this frame
    worst = check_path(scene, a, b, range(1, r["frames"] + 1))
    assert worst < 0.01, worst
    # hand-picked points: the end of the first arc (60, -20, -2) and the drilled hole's bottom (-100, 60, -5)
    sch = core.Schedule(gcode.read_program(scene, b, gcode.Machine(scene),
                                           start=gcode.start_point(gcode.Machine(scene)))[0], gcode.timing(scene, a, b))
    for line, want in ((10, (60, -20, -2)), (19, (-100, 60, -5))):
        piece = next(p for p in sch.pieces if p.move.line == line and p.move.kind in ("ARC", "FEED")
                     and abs(p.move.b[2] - (want[2] - 50)) < 1e-3)
        f = 1 + (piece.v0 + piece.vd) * animation.fps_of(a)
        scene.frame_set(int(f), subframe=f - int(f))
        assert near(tip_in_zero(scene) / MM, want, 0.01)


def test_between_frames_too(scene, tmp_path):
    """Keys sit on every move's ends and along arcs: sub-frames (milling reads them) follow the program too."""
    set_up(scene)
    a, b = step(scene, program(tmp_path))
    r = animation.bake(scene, a)
    assert check_path(scene, a, b, range(1, r["frames"], 7), subframes=True) < 0.01, check_path.where


def test_the_workpiece_moving_on_a_table(tmp_path):
    """The test mill: the table (with the workpiece) moves along Y, so the program's +Y moves the table -Y."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    bpy.ops.fresing.cnc_find_axes()
    click(ob(sc, "END MILL D10"))
    bpy.ops.fresing.cnc_use_tool()
    click(ob(sc, "STOCK 200x200x40"))
    bpy.ops.fresing.cnc_use_workpiece()
    m = gcode.Machine(sc)
    assert m.moves_tool == [True, False, True] and m.sign[1] == -1.0
    a, b = step(sc, program(tmp_path, "G0 X10 Y30 Z5\nG1 Z-1 F300\nG2 X10 Y30 I0 J-20 F900\nG0 Z20\nM30\n"))
    r = animation.bake(sc, a)
    assert check_path(sc, a, b, range(1, r["frames"] + 1), tool="END MILL D10") < 0.01, check_path.where
    sc.frame_set(r["frames"])
    assert joints.get_value(sc.fresing.joints["Y"]) == pytest.approx(-30 * MM, abs=1e-6)


def test_speed_settings(scene, tmp_path):
    set_up(scene)
    path = program(tmp_path)
    a, b = step(scene, path)
    real = b.duration
    prog = gcode.read_program(scene, b, gcode.Machine(scene), start=gcode.start_point(gcode.Machine(scene)))[0]
    assert real == pytest.approx(prog.duration, rel=1e-6)
    b.gcode_speed = "FASTER"
    b.gcode_factor = 4.0
    assert b.duration == pytest.approx(real / 4, rel=1e-6)
    b.gcode_speed = "FIT"
    b.gcode_fit = 12.0
    assert b.duration == pytest.approx(12.0)
    r = animation.bake(scene, a)
    assert r["frames"] == 1 + 12 * 25
    assert check_path(scene, a, b, range(1, r["frames"] + 1, 3)) < 0.01
    b.gcode_speed = "REAL"
    b.gcode_rapid = 5.0
    assert b.duration < real
    b.gcode_rapid = 1.0
    b.gcode_from, b.gcode_to = 8, 9                        # G1 Z-2, G1 X40: 7 mm at 600 + 90 mm at 1200
    assert b.duration == pytest.approx(7 / 600 * 60 + 90 / 1200 * 60, rel=1e-6)


def test_spindle_turns(scene, tmp_path):
    set_up(scene)
    head = [ob(scene, "SPINDLE"), ob(scene, T1)]
    joints.create(scene, "ROTATE", head, head[0].matrix_world.translation, Vector((0, 0, 1)), name="Spindle")
    j = scene.fresing.joints["Spindle"]
    j.is_motor = True
    scene.fresing.cnc.spindle_joint = "Spindle"
    a, b = step(scene, program(tmp_path, "S600 M3\nG4 P2\nM5\nG4 P1\nM30\n"))
    b.gcode_spindle = "REAL"
    animation.bake(scene, a)
    scene.frame_set(1 + 25)                                 # 1 s at 600 rpm = 10 turns, clockwise from above
    assert joints.get_value(j) == pytest.approx(-10 * 2 * math.pi, abs=1e-4)
    scene.frame_set(1 + 75)
    assert joints.get_value(j) == pytest.approx(-20 * 2 * math.pi, abs=1e-4)
    b.gcode_spindle = "SLOW"
    animation.bake(scene, a)
    scene.frame_set(1 + 25)                                 # at most 1/7 turn per frame: 25/7 turns
    assert joints.get_value(j) == pytest.approx(-25 / 7 * 2 * math.pi, abs=1e-4)


def test_limits_and_unknown_codes_are_reported(scene, tmp_path):
    set_up(scene)
    j = scene.fresing.joints["X"]
    j.use_limits = True
    j.slide_min, j.slide_max = -0.2, 0.2
    a, b = step(scene, program(tmp_path, "G0 X0 Y0\nG1 X250 F3000\nG41 D1\nG12 X3\nM30\n"))
    r = animation.bake(scene, a)
    text = " | ".join(r["warnings"])
    assert "'X' goes beyond its limits (first at line 2)" in text
    assert "G41" in text and "line 3" in text and "G12" in text and "line 4" in text


# ---------------------------------------------------------------------------
# tool changes
# ---------------------------------------------------------------------------

TOOLS = """(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
(T3 D=5. CR=0. TAPER=118deg - drill)
(T4 D=8. CR=1. - bullnose end mill)
G21 G90
T2 M6
G0 X10 Y0 Z5
T3 M6
G0 X20
T4 M6
G0 X30
M30
"""


def test_tool_changes_show_the_right_tool(scene, tmp_path):
    set_up(scene)
    a, b = step(scene, program(tmp_path, TOOLS))
    b.gcode_tc_time = 2.0
    assert bpy.ops.fresing.cnc_tools_from_program() == {"FINISHED"}
    c = scene.fresing.cnc
    assert sorted(t.number for t in c.tools) == [1, 2, 3, 4]
    t2 = next(t for t in c.tools if t.number == 2)
    c.tools_index = list(c.tools).index(t2)
    click(ob(scene, "TOOL T2 BALL D4"))
    assert bpy.ops.fresing.cnc_tool_part() == {"FINISHED"}
    next(t for t in c.tools if t.number == 1).obj = ob(scene, T1)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    copies = {o["fr_cnc_t"]: o for o in bpy.data.objects if o.get(gcode.TAG) == "tool"}
    assert sorted(copies) == [2, 3, 4]                      # T1 is the part in the spindle itself
    assert copies[3].data.get(gcode.TAG) == "tool"         # drawn from the program's comment
    t1, carousel_t2 = ob(scene, T1), ob(scene, "TOOL T2 BALL D4")

    def shown(o):
        return not o.hide_render

    # tool changes at 0-2 s (swap at 1 s), after the rapid, at ...: frame 10 = before the first swap
    scene.frame_set(10)
    assert shown(t1) and not shown(copies[2]) and shown(carousel_t2)
    scene.frame_set(1 + 30)                                 # 1.2 s: T2 in the spindle
    assert not shown(t1) and shown(copies[2]) and not shown(carousel_t2) and not shown(copies[3])
    # its tip is where T1's tip was
    tip2 = copies[2].matrix_world @ gcode._rest_tip(carousel_t2)[0]
    tip1 = t1.matrix_world @ gcode._rest_tip(t1)[0]
    assert (tip2 - tip1).length < 0.01 * MM
    scene.frame_set(scene.frame_end)
    assert shown(copies[4]) and not shown(copies[3]) and not shown(copies[2]) and shown(carousel_t2)
    # Clear keys: the copies go, T1 is back
    animation.clear_keys(scene)
    assert not [o for o in bpy.data.objects if o.get(gcode.TAG) == "tool"]
    assert shown(t1) and shown(carousel_t2)


def test_tool_changer_animation_plays_at_each_m6(scene, tmp_path):
    set_up(scene)
    car = ob(scene, "CAROUSEL.ASM")
    joints.create(scene, "ROTATE", [car], Vector((500 * MM, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    s = scene.fresing
    atc = s.animations.add()
    atc.name = "ATC"
    x = atc.blocks.add()
    x.kind, x.joint, x.start, x.duration, x.easing = "JOINT", "Carousel", 0.0, 3.0, "LINEAR"
    x.use_from, x.to_angle = True, math.radians(90)
    a, b = step(scene, program(tmp_path, "G0 X10\nT2 M6\nG0 X20\nT3 M6\nG0 X30\nM30\n"))
    b.gcode_atc = "ATC"
    b.gcode_atc_swap = 1.5
    prog_s = gcode.read_program(scene, b, gcode.Machine(scene), start=gcode.start_point(gcode.Machine(scene)))[0].duration
    assert b.duration == pytest.approx(prog_s + 2 * 3.0, rel=1e-6)
    s.animations_index = list(s.animations).index(a)
    r = animation.bake(scene, a)
    car_j = s.joints["Carousel"]
    sch = core.Schedule(gcode.read_program(scene, b, gcode.Machine(scene),
                                           start=gcode.start_point(gcode.Machine(scene)))[0], gcode.timing(scene, a, b))
    (_s1, _n1, start1, _d1), (_s2, _n2, start2, _d2) = sch.tool_events
    scene.frame_set(int(1 + (start1 + 3.0) * 25) + 1)
    assert joints.get_value(car_j) == pytest.approx(math.radians(90), abs=1e-4)
    scene.frame_set(r["frames"])
    assert joints.get_value(car_j) == pytest.approx(math.radians(90), abs=1e-4)   # "from where it is": 90 again
    # the program waits: X does not move while the carousel turns
    xj = s.joints["X"]
    scene.frame_set(int(1 + (start2 + 0.5) * 25))
    v = joints.get_value(xj)
    scene.frame_set(int(1 + (start2 + 2.5) * 25))
    assert joints.get_value(xj) == pytest.approx(v, abs=1e-9)
    # renamed: the step follows
    atc.name = "Tool changer"
    assert b.gcode_atc == "Tool changer"


# ---------------------------------------------------------------------------
# toolpath, saving, model update, panels
# ---------------------------------------------------------------------------

def test_toolpath_preview(scene, tmp_path):
    set_up(scene)
    a, b = step(scene, program(tmp_path))
    r = animation.bake(scene, a)
    path = gcode.path_object()
    assert path is not None and path.parent is scene.fresing.cnc.zero_empty and path.hide_render
    me = path.data
    fr = [v.value for v in me.attributes["fr_frame"].data]
    rp = [v.value for v in me.attributes["fr_rapid"].data]
    assert min(fr) >= 1 and max(fr) <= r["frames"] + 1e-3 and 0 < sum(rp) < len(rp)
    # the path's points are the program's points (in the work zero's frame)
    pts = [Vector(v.co) / MM for v in me.vertices]
    assert any((p - Vector((60, -20, -2))).length < 1e-3 for p in pts)
    # the evaluated tubes have the three materials
    dg = bpy.context.evaluated_depsgraph_get()
    ev = path.evaluated_get(dg)
    names = {m.name for m in ev.data.materials if m is not None}
    assert {"FR toolpath to cut", "FR toolpath cut", "FR toolpath rapid"} <= names
    b.gcode_path_render = True
    animation.bake(scene, a)
    assert not gcode.path_object().hide_render
    b.gcode_path = False
    assert bpy.ops.fresing.gcode_toolpath(remove=True) == {"FINISHED"}
    assert gcode.path_object() is None


def test_saved_and_opened_again_and_the_file_gone(scene, tmp_path):
    set_up(scene)
    path = program(tmp_path)
    a, b = step(scene, path)
    r = animation.bake(scene, a)
    blend = str(tmp_path / "cnc.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    os.remove(path)
    bpy.ops.wm.open_mainfile(filepath=blend)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    assert gcode.problem(sc) == ""
    a = sc.fresing.animations["Program"]
    b = a.blocks[0]
    r2 = animation.bake(sc, a)
    assert r2["frames"] == r["frames"]
    assert any("copy saved in the project" in w for w in r2["warnings"])
    assert check_path(sc, a, b, range(1, r2["frames"] + 1, 5)) < 0.01


def test_model_update_keeps_the_set_up(scene, tmp_path):
    set_up(scene)
    a, b = step(scene, program(tmp_path))
    animation.bake(scene, a)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=GANTRY, quality="draft", update_root=root.name) == {"FINISHED"}
    c = scene.fresing.cnc
    assert c.tool is ob(scene, T1) and c.workpiece is ob(scene, STOCK)
    assert gcode.problem(scene) == "" and c.zero_empty is not None
    r = animation.bake(scene, scene.fresing.animations["Program"])
    assert check_path(scene, a, scene.fresing.animations["Program"].blocks[0], range(1, r["frames"] + 1, 9)) < 0.01


def test_joint_rename_follows(scene):
    set_up(scene)
    scene.fresing.joints["X"].name = "Carriage"
    assert scene.fresing.cnc.x_joint == "Carriage" and gcode.problem(scene) == ""


def test_panels_draw(scene, tmp_path):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_gcode, ui_motion
    errors = []

    def draw_all():
        for cls in ui_gcode.CLASSES:
            if issubclass(cls, bpy.types.Panel):
                fake = type("P", (), {"layout": FakeLayout(errors)})()
                cls.draw(fake, bpy.context)
                for extra in ("draw_header", "draw_header_preset"):
                    getattr(cls, extra)(fake, bpy.context)
        c = gcode.settings(bpy.context.scene)
        for item in c.tools:
            ui_gcode.FRESING_UL_cnc_tools.draw_item(None, bpy.context, FakeLayout(errors), c, item, 0, c, "", 0)
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        ui_motion.FRESING_PT_animation.draw(fake, bpy.context)

    draw_all()
    set_up(scene)
    a, b = step(scene, program(tmp_path, TOOLS))
    bpy.ops.fresing.cnc_tools_from_program()
    for speed in ("REAL", "FASTER", "FIT"):
        b.gcode_speed = speed
        draw_all()
    b.gcode_atc = "nothing"
    scene.fresing.cnc.zero_mode = "POINT"
    draw_all()
    b.gcode_file = str(tmp_path / "missing.ngc")
    draw_all()
    assert not errors, errors


def test_cnc_tooltips_are_written():
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import tooltip_report as t
    fresing_render.unregister()                # the check registers the extension itself
    try:
        items = [i for i in t.collect() if i.panel == "CNC machine"]
    finally:
        fresing_render.register()
    assert len(items) >= 15
    bad = [(i.label or i.ident, i.verdict, i.tooltip) for i in items if i.verdict != "ok"]
    assert not bad, bad


def test_bake_time_of_a_long_program(scene, tmp_path, capsys):
    """A program of 20,000 short moves and arcs (about 30 minutes on the machine) at 25 fps."""
    import time
    set_up(scene)
    rows = ["G21 G90 G17", "S12000 M3", "G0 X-100 Y-80 Z2", "G1 Z-1 F600"]
    for i in range(10000):
        x = -100 + (i % 100) * 2.0
        y = -80 + (i // 100) * 1.6
        rows.append(f"G1 X{x:.3f} Y{y:.3f} F1500")
        rows.append(f"G2 X{x + 1:.3f} Y{y:.3f} R0.5")
    rows.append("M30")
    a, b = step(scene, program(tmp_path, "\n".join(rows)))
    gcode._CACHE.clear()
    t0 = time.perf_counter()
    r = animation.bake(scene, a)
    dt = time.perf_counter() - t0
    with capsys.disabled():
        print(f"\nbake: {len(rows)} lines, {r['frames']} frames, {dt:.1f} s")
    assert dt < 60
    assert check_path(scene, a, b, range(1, r["frames"] + 1, 997)) < 0.01


# ---------------------------------------------------------------------------
# joints: Blender drops small driver results (found by this task)
# ---------------------------------------------------------------------------

def test_a_joint_close_to_its_cad_position_is_not_snapped_to_it(scene):
    j = scene.fresing.joints["X"]
    for v in (0.05 * MM, 0.01 * MM, 0.0999 * MM, -0.03 * MM, 0.0, 0.2 * MM):
        joints.set_value(j, v)
        bpy.context.view_layer.update()
        assert j.motion.matrix_world.translation.x - j.frame.matrix_world.translation.x == pytest.approx(v, abs=1e-7)


def test_old_joint_drivers_are_upgraded(scene):
    j = scene.fresing.joints["X"]
    fc = j.motion.animation_data.drivers.find("location", index=2)
    fc.driver.variables.remove(fc.driver.variables["b"])        # as made before 0.2.27
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    assert not joints.driver_biased(j)
    joints.set_value(j, 0.05 * MM)
    bpy.context.view_layer.update()
    assert j.motion.location.z == 0.0                            # Blender's small-number problem
    assert joints.upgrade_drivers(scene) == 1 and joints.driver_biased(j)
    bpy.context.view_layer.update()
    assert j.motion.location.z == pytest.approx(0.05 * MM, abs=1e-8)
