"""Task 0064: the double-arm tool changer in Blender, on the test mill with an arm and a magazine
(tools/make_test_atc.py).

The spindle's gauge line is at (0, 0, 300) mm in the CAD pose (the change position); the arm turns about x = -130,
y = 0 and its claws reach x = 0 and x = -260 at +90°; the magazine (12 pots, one every 30° counter-clockwise, pot 1
towards the arm) turns about x = -460, y = 0; a pot tips down 90° about its hinge, the station pot's mouth then at
(-260, 0, 300). T1 (BT30 flat Ø10, gauge length 85) is in the spindle, T2 (BT30 ball Ø8, gauge length 80) in pot 2,
T3 (BT30 drill Ø6, drawn from its sizes) in pot 5.

The check of every hand-over: at the moment a tool goes from one holder to the next, the two copies' world matrices
(evaluated by Blender at that sub-frame) agree within 0.01 mm everywhere on the tool.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, doublearm, gcode, joints, toolchange, tools  # noqa: E402
from fresing_render.core import gcode as core  # noqa: E402

HERE = os.path.dirname(__file__)
ATC = os.path.join(HERE, "data", "test_atc.step")
MM = 0.001
FPS = 25
T1, T2 = "TOOL T1 BT30 FLAT D10", "TOOL T2 BT30 BALL D8"

PROGRAM = doublearm.TEST_PROGRAM


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def set_up(sc, tmp_path, tip=True, spindle=True, program=PROGRAM, **kw):
    """The machine, the arm, the magazine with 12 pots, the tools and a program step (doublearm.set_up_test_model)."""
    path = tmp_path / "atc.ngc"
    path.write_text(program)
    a = sc.fresing.animations.add()
    a.name, a.tail = "Program", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    for k, v in kw.items():
        setattr(b, k, v)
    b.gcode_file = str(path)
    doublearm.set_up_test_model(sc, b, tip=tip, spindle=spindle)
    return a, b


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=ATC, quality="draft") == {"FINISHED"}
    return sc


def schedule(sc, a, b):
    mach = gcode.Machine(sc)
    prog = gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0]
    return core.Schedule(prog, gcode.timing(sc, a, b, mach))


def at(sc, a, b, t):
    f = animation.frame_of(a, b.start) + t * FPS
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    bpy.context.view_layer.update()


def world(o):
    """An object's world matrix from its parent's (evaluated) one: a hidden object is not evaluated by Blender."""
    return o.parent.matrix_world @ o.matrix_parent_inverse @ o.matrix_basis


def tool_points(o):
    """A few points spread over the tool's shape (world)."""
    me = o.data
    n = len(me.vertices)
    idx = [0, n // 5, 2 * n // 5, 3 * n // 5, 4 * n // 5, n - 1]
    mw = world(o)
    return [mw @ me.vertices[i].co for i in idx]


def gap(a_ob, b_ob):
    return max((p - q).length for p, q in zip(tool_points(a_ob), tool_points(b_ob))) / MM


def copies(tag, n):
    return [o for o in bpy.data.objects if o.get(tag) == n]


def visible_holders(sc, n):
    """Every object showing tool ``n`` now (spindle, arm, pot, CAD part)."""
    out = []
    for o in sc.objects:
        if o.hide_render or o.type != "MESH":
            continue
        if o.get("fr_cnc_t") == n or o.get("fr_cnc_pocket") == n or o.get("fr_cnc_carry") == n:
            out.append(o)
    return out


# ---------------------------------------------------------------------------
# set-up
# ---------------------------------------------------------------------------

def test_set_up_reads_the_arm_and_the_pots(scene, tmp_path):
    a, b = set_up(scene, tmp_path)
    c = scene.fresing.cnc
    slide, turn = doublearm.arm_joints(scene)
    assert slide is not None and turn is not None
    assert math.degrees(c.arm_grip) == pytest.approx(90.0, abs=0.05)
    assert c.arm_stroke == pytest.approx(76 * MM)
    assert len(c.pockets) == 12 and all(p.tip_joint for p in c.pockets)
    assert len({p.obj.name for p in c.pockets}) == 12
    # the arm and pot joints are never taken for an axis or the spindle
    gcode.find_axes(scene)
    assert (c.x_joint, c.y_joint, c.z_joint, c.spindle_joint) == ("X", "Y", "Z", "Spindle")
    assert not toolchange.problems(scene)
    lines = doublearm.check(scene)
    assert all(ok for ok, _t in lines), lines
    claw = next(t for _ok, t in lines if t.startswith("Claw"))
    pot = next(t for _ok, t in lines if t.startswith("Pot 1"))
    assert "0.00 mm" in claw and "0.00 mm" in pot
    # T2 stands in pot 2 (its CAD place), T3 in pot 5 (its row)
    ch = toolchange.changer(scene, a, b)
    assert ch.arm and ch.pockets == {2: 2, 3: 5}
    assert ch.tip > 0 and ch.orient > 0


def test_check_finds_what_does_not_fit(scene, tmp_path):
    set_up(scene, tmp_path)
    c = scene.fresing.cnc
    c.arm_grip = math.radians(80)
    c.arm_stroke = 40 * MM
    bad = [t for ok, t in doublearm.check(scene) if not ok]
    assert any(t.startswith("Claw") for t in bad)
    assert any("stroke" in t for t in bad)
    c.change_mode = "STAY"
    assert any("change position" in p for p in doublearm.problems(scene))


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

def test_change_plays_with_every_tool_held(scene, tmp_path):
    a, b = set_up(scene, tmp_path)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sch = schedule(scene, a, b)
    arm = [c for c in sch.changes if c.kind == "arm"]
    assert [c.tool for c in arm] == [2, 3, 1]
    assert [c.new_pocket for c in arm] == [2, 5, 2]     # T1 went into pot 2 and comes back from there
    assert all(c.prep for c in arm)                     # every change pre-indexed by its Tn
    worst = 0.0
    for c in arm:
        times = c.arm_times()
        g1, p1 = times["grip"][1], times["push"][1]
        old, new = c.old, c.tool
        # just before the grip ends: the old tool in the spindle, the new one in its pot
        at(scene, a, b, g1 - 0.02)
        assert [o.get("fr_cnc_pocket") for o in visible_holders(scene, new)] == [new]
        at(scene, a, b, g1)                             # the claws close: spindle -> arm, pot -> arm
        spin_old = gcode.copies().get(old) if old != 1 else ob(scene, T1)
        arm_old = [o for o in copies("fr_cnc_carry", old) if not o.hide_render]
        arm_new = [o for o in copies("fr_cnc_carry", new) if not o.hide_render]
        assert len(arm_old) == 1 and len(arm_new) == 1
        pot_new = next(o for o in copies("fr_cnc_pocket", new) if o.parent is next(
            p.obj for p in scene.fresing.cnc.pockets if p.number == c.new_pocket))
        worst = max(worst, gap(spin_old, arm_old[0]), gap(pot_new, arm_new[0]))
        # the swap: half a turn, pulled out
        at(scene, a, b, (times["swap"][0] + times["swap"][1]) / 2)
        assert len(visible_holders(scene, old)) == 1 and len(visible_holders(scene, new)) == 1
        at(scene, a, b, p1)                             # pushed in: arm -> spindle, arm -> pot
        spin_new = gcode.copies().get(new) if new != 1 else ob(scene, T1)
        pot_old = next(o for o in copies("fr_cnc_pocket", old) if o.parent is next(
            p.obj for p in scene.fresing.cnc.pockets if p.number == c.new_pocket))
        worst = max(worst, gap(arm_new[0], spin_new), gap(arm_old[0], pot_old))
        at(scene, a, b, p1 + 0.02)
        assert visible_holders(scene, new) == [spin_new] or (new == 1 and not ob(scene, T1).hide_render)
        assert [o for o in visible_holders(scene, old)] == [pot_old]
    assert worst < 0.01, worst
    test_change_plays_with_every_tool_held.worst = worst


def test_pot_down_at_grip_and_magazine_still(scene, tmp_path):
    a, b = set_up(scene, tmp_path)
    animation.bake(scene, a)
    sch = schedule(scene, a, b)
    c = scene.fresing.cnc
    car = scene.fresing.joints["Magazine"]
    for ch in (x for x in sch.changes if x.kind == "arm"):
        times = ch.arm_times()
        tj = scene.fresing.joints[next(p.tip_joint for p in c.pockets if p.number == ch.new_pocket)]
        v0 = None
        for t in (times["grip"][0], times["swap"][0], times["back"][1]):
            at(scene, a, b, t)
            assert abs(joints.get_value(tj)) == pytest.approx(math.pi / 2, abs=1e-4)
            v = joints.get_value(car)
            assert v0 is None or v == pytest.approx(v0, abs=1e-6)
            v0 = v
        at(scene, a, b, ch.start + ch.length + 0.01)
        assert joints.get_value(tj) == pytest.approx(0.0, abs=1e-6)
    # the spindle stands at its orient angle while the arm works
    sp = scene.fresing.joints["Spindle"]
    for ch in (x for x in sch.changes if x.kind == "arm"):
        at(scene, a, b, ch.arm_times()["swap"][0])
        v = joints.get_value(sp)
        assert math.remainder(v - c.orient_angle, math.tau) == pytest.approx(0.0, abs=1e-4)


def test_without_pot_tip_and_without_spindle_joint(scene, tmp_path):
    a, b = set_up(scene, tmp_path, tip=False, spindle=False)
    c = scene.fresing.cnc
    assert not c.pot_tip
    ch = toolchange.changer(scene, a, b)
    assert ch.tip == 0 and ch.orient == 0
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sch = schedule(scene, a, b)
    arm = [x for x in sch.changes if x.kind == "arm"]
    assert len(arm) == 3 and all(not x.tips() for x in arm)
    x = arm[0]
    at(scene, a, b, x.arm_times()["grip"][1])
    spin = ob(scene, T1)
    held = [o for o in copies("fr_cnc_carry", 1) if not o.hide_render]
    assert gap(spin, held[0]) < 0.01


def test_fit_into(scene, tmp_path):
    a, b = set_up(scene, tmp_path, gcode_speed="FIT", gcode_fit=12.0)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sch = schedule(scene, a, b)
    assert sch.duration == pytest.approx(12.0, abs=1e-6)
    assert sch.change_scale < 1.0
    assert b.duration == pytest.approx(12.0, abs=1e-6)


def test_save_reopen_and_queue_keys(scene, tmp_path):
    a, b = set_up(scene, tmp_path)
    animation.bake(scene, a)
    sch = schedule(scene, a, b)
    x = next(c for c in sch.changes if c.kind == "arm")
    path = str(tmp_path / "atc.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    a, b = sc.fresing.animations["Program"], sc.fresing.animations["Program"].blocks[0]
    at(sc, a, b, x.arm_times()["swap"][0] + 0.01)
    held = [o for o in bpy.data.objects if o.get("fr_cnc_carry") and not o.hide_render]
    assert sorted(o["fr_cnc_carry"] for o in held) == [1, 2]
    # the drivers of the app's joints are simple: they play with scripts off
    for name in (sc.fresing.cnc.arm_turn, sc.fresing.cnc.arm_slide, sc.fresing.cnc.pockets[0].tip_joint):
        j = sc.fresing.joints[name]
        for fc in j.motion.animation_data.drivers:
            assert fc.driver.type != "SCRIPTED" or fc.driver.is_simple_expression


def test_old_atc_project_unchanged(scene, tmp_path):
    """A carousel ATC (0.2.45) on the same model plays as before: no arm keys, tools stay in their own pockets."""
    a, b = set_up(scene, tmp_path, tip=False)
    c = scene.fresing.cnc
    c.changer = "ATC"
    sch = schedule(scene, a, b)
    assert all(x.kind == "" for x in sch.changes)
    assert all(not x.prep for x in sch.changes)
    animation.bake(scene, a)
    assert not [o for o in bpy.data.objects if o.name.startswith("FR tool") and "on arm" in o.name]


def test_remove_the_arm_removes_every_joint_it_made(scene, tmp_path):
    set_up(scene, tmp_path)
    c = scene.fresing.cnc
    n_before = len(scene.fresing.joints)
    c.pockets.remove(3)                                # a pocket removed: its pot's joint stays until the arm goes
    assert bpy.ops.fresing.cnc_arm_remove() == {"FINISHED"}
    assert not [j for j in scene.fresing.joints if doublearm.app_joint(j)]
    assert len(scene.fresing.joints) == n_before - 14      # the arm's two joints and twelve pots
    assert doublearm.arm_joints(scene) == (None, None)
    arm = ob(scene, "CHANGER ARM")
    assert arm.parent is ob(scene, "ARM.ASM")            # back under its CAD parent
