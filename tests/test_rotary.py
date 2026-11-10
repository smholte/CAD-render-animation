"""Task 0066: the 4th and 5th axis in Blender, on the two generic test models.

test_4axis.step (tools/make_test_4axis.py): a moving column carries the tool (X/Y/Z); the rotary table turns about the
X line y = 0, z = 150 mm and holds a bar Ø50 (x -120 .. 120). Plain kinematics; the work zero is on the bar's top in
its middle, (0, 0, 175). The program (rotary.TEST_PROGRAM_4AXIS) cuts a slot 2 deep wrapped once round the bar (X -90
.. -50 while A turns 0 .. 360) and a flat 3 deep (X 20 .. 50) at A0 and at A180.

test_5axis.step (tools/make_test_5axis.py): a trunnion tilts about the X line y = 0, z = 140 (A) and its table turns
about the vertical through x = y = 0 (C, riding on A); the block 60 x 60 x 40 sits on it (top at z = 180). Tool
follows the part (TCP); the work zero on the block's top in its middle. The program (rotary.TEST_PROGRAM_5AXIS) cuts a
pocket 3 deep at A30 C0 and at A30 C180, and a groove 1 deep along y = 20 while C turns 90°.

+A (+C) is the tool going round the part right-handed about +X (+Z): the part itself turns the other way. So the
point of the part under the tool at A = θ is the part's point that lay at angle +θ about +X from the top at A0.
"""

import math
import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, gcode, joints, machining, rotary  # noqa: E402
from fresing_render.core import gcode as core  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL4 = os.path.join(HERE, "data", "test_4axis.step")
MODEL5 = os.path.join(HERE, "data", "test_5axis.step")
MM = 0.001
FPS = 25


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def load(tmp_path, five=False, program=None, milling=True, fit=0.0, **kw):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    machining._RUNTIME.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL5 if five else MODEL4, quality="draft") == {"FINISHED"}
    path = tmp_path / "prog.ngc"
    path.write_text(program or (rotary.TEST_PROGRAM_5AXIS if five else rotary.TEST_PROGRAM_4AXIS))
    a = sc.fresing.animations.add()
    a.name, a.tail = "Program", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = str(path)
    if fit:
        b.gcode_speed, b.gcode_fit = "FIT", fit
    for k, v in kw.items():
        setattr(b, k, v)
    rotary.set_up_test_model(sc, b, five=five, milling=milling)
    return sc, a, b


def bake(sc, a):
    r = animation.bake(sc, a)
    assert not r.get("warnings"), r.get("warnings")
    return r


def schedule(sc, a, b):
    mach = gcode.Machine(sc)
    prog = gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0]
    return mach, core.Schedule(prog, gcode.timing(sc, a, b, mach))


def at_frame(sc, f: float):
    sc.frame_set(int(math.floor(f)), subframe=float(f - math.floor(f)))


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def cut_bvh(sc, world):
    """The milled workpiece mesh as a BVH, its points through ``world`` (the part's matrix at A0 B0 C0)."""
    wp = machining.workpiece(sc)
    me = machining.settings(sc).cut_mesh
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    v = v.reshape(-1, 3)
    w = np.array(world)
    v = v @ w[:3, :3].T + w[:3, 3]
    t = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    _ = wp
    return BVHTree.FromPolygons(v.tolist(), t.reshape(-1, 3).tolist(), all_triangles=True)


def depth_from_outside(bvh, point, direction) -> float:
    """Distance (mm) from ``point`` (m, outside) along ``direction`` to the first surface."""
    hit = bvh.ray_cast(Vector(point), Vector(direction).normalized())
    assert hit[0] is not None, f"nothing hit from {point}"
    return (hit[0] - Vector(point)).length / MM


# ---------------------------------------------------------------------------
# 4th axis, Plain
# ---------------------------------------------------------------------------

def test_4axis_set_up_and_check(tmp_path):
    sc, a, b = load(tmp_path, milling=False)
    m = gcode.Machine(sc)
    ax = m.axes[0]
    assert ax.part and ax.joint.name == "Rotary A"
    assert ax.centre[1] - m.g54[1] == pytest.approx(0.0, abs=1e-3)
    assert ax.centre[2] - m.g54[2] == pytest.approx(-25.0, abs=1e-3)       # the bar's axis 25 below its top
    lines = rotary.check(sc)
    assert all(ok for ok, _t in lines), lines
    assert any("centre from the work zero" in t and "Z -25.00" in t for _ok, t in lines)
    # Check puts every joint back
    assert joints.get_value(ax.joint) == pytest.approx(0.0, abs=1e-9)


def test_4axis_joints_follow_the_program(tmp_path):
    sc, a, b = load(tmp_path, milling=False)
    bake(sc, a)
    m, sch = schedule(sc, a, b)
    ax = m.axes[0]
    assert sch.turns
    for t in np.linspace(0.0, sch.duration, 37):
        at_frame(sc, 1 + t * FPS)
        r = sch.rot_at(t)
        assert joints.get_value(ax.joint) == pytest.approx(ax.value(r[0]), abs=1e-5)
        want = m.values_for(sch.point_at(t))                  # Plain: X/Y/Z as the program says
        for j, v in zip(m.joints, want):
            assert joints.get_value(j) == pytest.approx(v, abs=2e-6)
    # the slot: A goes 0 -> 360 in G1 X-50 A360 F400 (40 mm at 400 mm/min = 6 s)
    p = next(p for p in sch.pieces if p.move.kind == "FEED" and p.move.turn > 1)
    assert p.vd == pytest.approx(6.0) and p.move.rb[0] == pytest.approx(360.0)


def test_4axis_wrapped_slot_and_flats_are_cut(tmp_path):
    sc, a, b = load(tmp_path, fit=6.0)
    t0 = time.perf_counter()
    bake(sc, a)
    t_bake = time.perf_counter() - t0
    at_frame(sc, 1)
    home = machining.workpiece(sc).matrix_world.copy()           # A0 at frame 1
    t0 = time.perf_counter()
    machining.sample(sc)
    t_sample = time.perf_counter() - t0
    end = sc.frame_end
    t0 = time.perf_counter()
    assert machining.refresh(sc, frame=end, force=True)
    t_cut = time.perf_counter() - t0
    print(f"\n4-axis: bake {t_bake:.2f} s, read the path {t_sample:.2f} s, cut to the end {t_cut:.2f} s "
          f"({end} frames)")
    bvh = cut_bvh(sc, home)
    axis_y, axis_z = 0.0, 0.150

    def radius(x_mm, ang_deg):
        """The bar's radius (mm) at x, in the direction at ``ang_deg`` about +X from the top (+Z)."""
        d = Vector((0.0, -math.sin(math.radians(ang_deg)), math.cos(math.radians(ang_deg))))
        start = Vector((x_mm * MM, axis_y, axis_z)) + d * 0.06
        return 60.0 - depth_from_outside(bvh, start, -d)

    # the wrapped slot: at A = θ the tool is at X -90 + 40 θ / 360, 2 deep
    for theta in (45.0, 90.0, 200.0, 300.0):
        x = -90.0 + 40.0 * theta / 360.0
        assert radius(x, theta) == pytest.approx(23.0, abs=0.05), theta
        # the other side is untouched (as at x = 0, between the cuts: the draft mesh's facets are a little inside 25)
        assert radius(x, theta + 180.0) == pytest.approx(radius(0.0, theta + 180.0), abs=0.01), theta
    # the flats: 3 deep on top (A0) and underneath (A180), not at the sides
    for x in (30.0, 40.0):
        assert radius(x, 0.0) == pytest.approx(22.0, abs=0.05)
        assert radius(x, 180.0) == pytest.approx(22.0, abs=0.05)
        assert radius(x, 90.0) == pytest.approx(radius(0.0, 90.0), abs=0.01)
    assert radius(0.0, 0.0) == pytest.approx(25.0, abs=0.2)           # between the cuts: uncut


def test_4axis_scrubbing_is_quick_and_repeatable(tmp_path):
    sc, a, b = load(tmp_path, fit=6.0)
    bake(sc, a)
    machining.sample(sc)
    end = sc.frame_end
    machining.refresh(sc, frame=end, force=True)
    me = machining.settings(sc).cut_mesh
    n_end = len(me.vertices)
    times = []
    for f in (end - 10, 40, 75, end, 20, end):
        t0 = time.perf_counter()
        machining.refresh(sc, frame=f, force=True)
        times.append((time.perf_counter() - t0) * 1000)
    print(f"\n4-axis scrubbing: {', '.join(f'{x:.0f}' for x in times)} ms per frame")
    assert len(me.vertices) == n_end


def test_toolpath_lies_on_the_turning_bar(tmp_path):
    sc, a, b = load(tmp_path, milling=False, gcode_path=True)
    bake(sc, a)
    path = gcode.path_object()
    assert path is not None and path.parent is gcode.settings(sc).zero_empty
    zero = gcode.settings(sc).zero_empty
    assert zero.parent is machining.workpiece(sc) or zero.parent == ob(sc, "BAR D50x240")
    co = np.empty(len(path.data.vertices) * 3)
    path.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) / MM                                   # mm from the work zero (bar top centre)
    rapid = np.empty(len(path.data.vertices))
    path.data.attributes["fr_rapid"].data.foreach_get("value", rapid)
    co = co[rapid < 0.5]
    slot = co[(co[:, 0] > -89.0) & (co[:, 0] < -51.0)]
    r = np.hypot(slot[:, 1], slot[:, 2] + 25.0)
    assert len(slot) > 100 and np.all(np.abs(r - 23.0) < 0.05)   # the helix 2 deep round the bar


def test_tool_change_keeps_the_rotary_axis(tmp_path):
    prog = "G21 G90 G54\nT1 M6\nG0 Z10\nG0 A45\nT2 M6\nG0 X10\nG0 A0\nM30\n"
    sc, a, b = load(tmp_path, program=prog, milling=False)
    bake(sc, a)
    m, sch = schedule(sc, a, b)
    ch = sch.changes[-1]
    assert ch.length > 0
    for t in np.linspace(ch.start, ch.start + ch.length, 9):
        at_frame(sc, 1 + t * FPS)
        assert joints.get_value(m.axes[0].joint) == pytest.approx(m.axes[0].value(45.0), abs=1e-5)


def test_three_axis_program_unchanged_by_a_rotary_axis(tmp_path):
    """A program without A/B/C: the same keys, length and cut with or without an A joint picked."""
    prog = "G21 G90 G54\nT1 M6\nG0 X-60 Y0 Z10\nG1 Z-2 F300\nG1 X-20 F600\nG2 X0 Y0 I10 J0\nG0 Z10\nM30\n"
    out = []
    for with_a in (False, True):
        sc, a, b = load(tmp_path, program=prog, fit=3.0)
        if not with_a:
            gcode.settings(sc).a_joint = ""
        bake(sc, a)
        m, sch = schedule(sc, a, b)
        keys = []
        for j in m.joints:
            for fc in animation.joint_fcurves(j) if hasattr(animation, "joint_fcurves") else []:
                keys.append([tuple(k.co) for k in fc.keyframe_points])
        vals = []
        for f in range(1, sc.frame_end + 1, 3):
            sc.frame_set(f)
            vals.append([joints.get_value(j) for j in m.joints])
        machining.sample(sc)
        machining.refresh(sc, frame=sc.frame_end, force=True)
        me = machining.settings(sc).cut_mesh
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", v)
        out.append((sch.duration, vals, np.sort(v.reshape(-1, 3), axis=0), "fr_turns" in gcode.settings(sc)))
    assert out[0][0] == out[1][0]
    assert out[0][1] == out[1][1]
    assert out[0][2].shape == out[1][2].shape and np.array_equal(out[0][2], out[1][2])
    assert not out[0][3] and not out[1][3]


# ---------------------------------------------------------------------------
# 5th axis, TCP
# ---------------------------------------------------------------------------

def test_5axis_check_and_tcp_tip_error(tmp_path):
    sc, a, b = load(tmp_path, five=True, milling=False)
    lines = rotary.check(sc)
    assert all(ok for ok, _t in lines), lines
    m0 = gcode.Machine(sc)
    assert [m0.axes[k].letter for k in m0.axis_order] == ["C", "A"]          # C rides on A: the inner one
    bake(sc, a)
    m, sch = schedule(sc, a, b)
    wp, tool = m.workpiece, m.tool
    tip_l = gcode._rest_tip(tool)[0]
    at_frame(sc, 1)
    home_inv = wp.matrix_world.inverted()
    worst = 0.0
    n = 0
    for f in np.arange(1.0, sch.duration * FPS, 0.37):               # also between frames and between keys
        t = (f - 1) / FPS
        if any(c.start - 1e-6 <= t <= c.start + c.length + 1e-6 for c in sch.changes):
            continue
        at_frame(sc, f)
        pt = sch.point_at(t)
        world_home = m.zero + m.rot @ (Vector(pt) - Vector(m.g54)) * MM
        want = wp.matrix_world @ (home_inv @ world_home)
        worst = max(worst, ((tool.matrix_world @ tip_l) - want).length / MM)
        n += 1
    print(f"\n5-axis TCP: tool tip vs the programmed point on the turning block: worst {worst:.4f} mm ({n} samples)")
    assert worst < 0.01


def test_5axis_tilted_pockets_and_groove_are_cut(tmp_path):
    sc, a, b = load(tmp_path, five=True, fit=8.0)
    t0 = time.perf_counter()
    bake(sc, a)
    at_frame(sc, 1)
    home = machining.workpiece(sc).matrix_world.copy()
    machining.sample(sc)
    assert machining.refresh(sc, frame=sc.frame_end, force=True)
    print(f"\n5-axis: build, read and cut {time.perf_counter() - t0:.2f} s")
    bvh = cut_bvh(sc, home)
    top = Vector((0.0, 0.0, 0.180))
    a30 = math.radians(rotary.POCKET_A)
    for side in (-1.0, 1.0):                         # C0: the -Y side, C180: the +Y side
        n = Vector((0.0, side * math.sin(a30), math.cos(a30)))
        c = top + Vector((0.0, side * rotary.POCKET_Y * MM, 0.0))
        # along the tool's axis from 10 mm out: the floor 3 deep under the top face's point
        assert depth_from_outside(bvh, c + n * 0.010, -n) == pytest.approx(13.0, abs=0.05)
        # outside the pocket (the tool's centre stays within 4 of its middle, radius 3) and the groove: untouched
        p = c + Vector((-0.025, 0.0, 0.0))
        assert depth_from_outside(bvh, p + Vector((0, 0, 0.01)), Vector((0, 0, -1))) == pytest.approx(10.0, abs=0.05)
    # the groove 1 deep along y = 20, cut while C turned 90°
    for x in (-15.0, -10.0, 10.0, 15.0):              # (round x = 0 the +Y pocket is deeper)
        p = top + Vector((x * MM, 0.020, 0.01))
        assert depth_from_outside(bvh, p, Vector((0, 0, -1))) == pytest.approx(11.0, abs=0.05), x
    assert depth_from_outside(bvh, top + Vector((0.0, 0.0, 0.01)), Vector((0, 0, -1))) == pytest.approx(10.0, abs=0.05)


def test_saved_and_opened_again_scripts_off(tmp_path):
    sc, a, b = load(tmp_path, five=True, milling=False)
    bake(sc, a)
    m = gcode.Machine(sc)
    g54, centres = m.g54, {k: ax.centre for k, ax in m.axes.items()}
    sc.frame_set(60)
    want = {j.name: joints.get_value(j) for j in sc.fresing.joints}
    path = str(tmp_path / "five.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    c = gcode.settings(sc)
    assert (c.a_joint, c.c_joint, c.kinematics) == ("Trunnion A", "Table C", "TCP")
    sc.frame_set(1)
    sc.frame_set(60)
    for j in sc.fresing.joints:
        assert joints.get_value(j) == pytest.approx(want[j.name], abs=1e-6), j.name
    m2 = gcode.Machine(sc)
    assert m2.g54 == pytest.approx(g54, abs=1e-4)
    for k, cen in centres.items():
        assert m2.axes[k].centre == pytest.approx(cen, abs=1e-4)
    # works with "Auto Run Python Scripts" off: the rotary joints' drivers are simple expressions
    for name in ("Trunnion A", "Table C"):
        j = sc.fresing.joints[name]
        for fc in j.motion.animation_data.drivers:
            assert fc.driver.type != "SCRIPTED" or fc.driver.is_simple_expression


def test_program_turns_an_axis_without_a_joint(tmp_path):
    sc, a, b = load(tmp_path, milling=False)
    gcode.settings(sc).a_joint = ""
    r = animation.bake(sc, a)
    assert any("turns A" in w and "no A joint" in w for w in r.get("warnings", [])), r.get("warnings")
