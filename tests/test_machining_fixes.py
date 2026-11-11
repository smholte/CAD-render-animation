"""Task 0071: machining fixes from bug hunt 0068 (rows 6-11, 14-16, 18, 19a-c) and study 0069 #5.

Each test failed on 0.2.55 and passes now. The scenes: the test gantry (tests/test_gcode.py, tool changes as in
tests/test_toolchange.py), the double-arm mill (tests/test_doublearm.py) and the 4- and 5-axis models
(tests/test_rotary.py).
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

from fresing_render.blender import animation, build, doublearm, gcode, joints, machining, toolchange  # noqa: E402

from test_gcode import MM, STOCK, T1, addon, click, ob, program, scene, set_up, step  # noqa: E402,F401
from test_toolchange import DISC, STATION, T2, T3, tools  # noqa: E402

HERE = os.path.dirname(__file__)
ATC_MODEL = os.path.join(HERE, "data", "test_atc.step")
FPS = 25

# the program of tests/test_toolchange.py, ending with T3 in the spindle (bug hunt 0068 row 6)
PROGRAM_T3 = """(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
(T3 D=5. CR=0. TAPER=118deg - drill)
(T4 D=8. CR=1. - bullnose end mill)
G21 G90
G0 X10 Y0 Z5
T2 M6
G0 X10 Y0 Z5
G1 X20 F600
T3 M6
G0 X30 Y10 Z5
G1 X40 F600
M30
"""


def shown(o):
    return not o.hide_render


def holders(sc, n, rows=None):
    """Every object showing tool ``n`` now: its spindle copy, pocket copy, arm or hand copy, or its CAD part."""
    out = [o for o in sc.objects if o.type == "MESH" and shown(o) and n in
           (o.get("fr_cnc_t"), o.get("fr_cnc_pocket"), o.get("fr_cnc_carry"))]
    part = rows.get(n) if rows else None
    if part is not None and part.name in sc.objects and shown(part):
        out.append(part)
    return out


def in_spindle(sc):
    """The tools shown in the spindle now: the spindle's part and the spindle copies."""
    spindle = sc.fresing.cnc.tool
    out = [o for o in sc.objects if o.get("fr_cnc_t") and shown(o)]
    if shown(spindle):
        out.append(spindle)
    return out


def two_steps(sc, a, b, gap=1.0):
    b2 = a.blocks.add()
    b2.kind = "GCODE"
    b2.gcode_file = b.gcode_file
    b2.start = b.start + b.duration + gap
    return b2


def gantry_changes(sc, tmp_path, kind):
    set_up(sc)
    a, b = step(sc, program(tmp_path, PROGRAM_T3))
    a.fps = str(FPS)
    rows = tools(sc)
    c = sc.fresing.cnc
    if kind == "ATC":
        car = ob(sc, "CAROUSEL.ASM")
        joints.create(sc, "ROTATE", [car], Vector((500 * MM, 0, 0)), Vector((0, 0, 1)), name="Carousel")
        rows[1].pocket = 7
        c.changer = "ATC"
        c.carousel_joint = "Carousel"
        toolchange.add_pocket(sc, ob(sc, DISC), STATION)
        c.pocket_count = 8
        assert toolchange.fill_carousel(sc) == ""
    return a, b, {n: r.obj for n, r in rows.items() if r.obj is not None and r.obj is not c.tool}


# ---------------------------------------------------------------------------
# rows 6 + 7: two G-code steps in one animation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["MANUAL", "ATC"])
def test_two_program_steps_show_each_tool_once(scene, tmp_path, kind):
    a, b, parts = gantry_changes(scene, tmp_path, kind)
    b2 = two_steps(scene, a, b)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    for n in (2, 3):                                        # one spindle copy per tool and build
        assert len([o for o in bpy.data.objects if o.get("fr_cnc_t") == n]) == 1, n
    f2 = animation.frame_of(a, b2.start)
    seen2 = set()
    for f in range(1, r["frames"] + 1):
        scene.frame_set(f)
        sp = in_spindle(scene)
        assert len(sp) <= 1, (f, [o.name for o in sp])       # never two tools in the spindle
        for n in (1, 2, 3):
            assert len(holders(scene, n, parts)) <= 1, (f, n, [o.name for o in holders(scene, n, parts)])
        if f >= f2 and sp:
            seen2.add(sp[0].get("fr_cnc_t", 1))
    assert seen2 == {1, 2, 3}                               # step 2 starts with T1 again and changes to T2, T3


def test_two_program_steps_mill_with_the_copy_in_the_spindle(scene, tmp_path):
    a, b, _parts = gantry_changes(scene, tmp_path, "MANUAL")
    two_steps(scene, a, b)
    m = machining.settings(scene)
    m.enabled = True
    machining.add_bit(scene, ob(scene, T1))
    machining.set_workpiece(scene, ob(scene, STOCK))
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    machining.sample(scene)
    items = [c for c in machining.cut_items(scene) if c.spindle is not None and c.ob.get("fr_cnc_t")]
    assert {c.ob["fr_cnc_t"] for c in items} == {2, 3}
    assert len(items) == 4                                  # T2 and T3, in each step
    for c in items:                                         # the copy cutting is the one shown then
        t = c.path.t
        mid = 0.5 * (float(t[0]) + float(t[-1]))
        scene.frame_set(int(mid), subframe=mid - int(mid))
        assert shown(c.ob), (c.name, mid)


# ---------------------------------------------------------------------------
# the double arm, two steps
# ---------------------------------------------------------------------------

@pytest.fixture()
def atc_scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=ATC_MODEL, quality="draft") == {"FINISHED"}
    return sc


def arm_set_up(sc, tmp_path, **kw):
    path = tmp_path / "atc.ngc"
    path.write_text(doublearm.TEST_PROGRAM)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Program", 0.0, str(FPS)
    b = a.blocks.add()
    b.kind = "GCODE"
    for k, v in kw.items():
        setattr(b, k, v)
    b.gcode_file = str(path)
    doublearm.set_up_test_model(sc, b)
    return a, b


def test_double_arm_two_program_steps(atc_scene, tmp_path):
    sc = atc_scene
    a, b = arm_set_up(sc, tmp_path)
    b2 = two_steps(sc, a, b)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    pots = [(o["fr_cnc_pocket"], o.parent.name) for o in bpy.data.objects if "fr_cnc_pocket" in o]
    assert len(pots) == len(set(pots))                       # one copy per tool and pot
    for n in (2, 3):
        assert len([o for o in bpy.data.objects if o.get("fr_cnc_t") == n]) == 1, n
    rows = {t.number: t.obj for t in sc.fresing.cnc.tools if t.obj is not None and t.obj is not sc.fresing.cnc.tool}
    f2 = animation.frame_of(a, b2.start)
    for f in range(1, r["frames"] + 1, 2):
        sc.frame_set(f)
        for n in (1, 2, 3):
            h = holders(sc, n, rows)
            if n == 1 and shown(sc.fresing.cnc.tool):
                h.append(sc.fresing.cnc.tool)
            assert len(h) <= 1, (f, f >= f2, n, [o.name for o in h])
        assert len(in_spindle(sc)) <= 1, f


# ---------------------------------------------------------------------------
# row 8: the changer's own animation in step with M6 when the program does not start at the animation's start
# ---------------------------------------------------------------------------

def _keys(j):
    fcs = machining._fcurves(j.motion)
    fc = next(fc for fc in fcs if fc.data_path == f'["{joints.VALUE}"]')
    return [k.co[0] for k in fc.keyframe_points]


def test_changer_animation_in_step_after_a_joint_step(scene, tmp_path):
    a, b, _parts = gantry_changes(scene, tmp_path, "ATC")
    s = scene.fresing
    joints.create(scene, "ROTATE", [ob(scene, "BED")], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Door")
    door = s.joints["Door"]
    door.use_limits = False
    seq = s.animations.add()
    seq.name = "Cover"
    x = seq.blocks.add()
    x.kind, x.joint, x.start, x.duration = "JOINT", "Door", 0.0, 1.0
    x.from_angle, x.to_angle = 0.0, 0.3
    b.gcode_atc = "Cover"
    b.gcode_atc_swap = 0.5
    y = a.blocks.add()                                     # Y moves 100 mm before the program starts
    y.kind, y.joint, y.start, y.duration = "JOINT", "Y", 0.0, 1.0
    y.from_dist, y.to_dist = 0.0, 0.1
    b.start = 1.0
    s.animations_index = list(s.animations).index(a)
    r = animation.bake(scene, a)
    assert not [w for w in r["warnings"] if "same time" in w], r["warnings"]
    # the program as the bake reads it: from Y = 100 mm
    mach = gcode.Machine(scene)
    js = {j.name: joints.get_value(j) for j in s.joints}
    js["Y"] = 0.1
    st = mach.machine_of([js[j.name] for j in mach.joints])
    from fresing_render.core import gcode as core
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=st)[0], gcode.timing(scene, a, b, mach))
    assert b.duration == pytest.approx(sch.duration, abs=1e-4)        # the step's length from where it starts
    want = []
    for ch in sch.changes:
        for t, s0, _s1, scale in ch.seq_parts():
            if s0 < 1e-9:
                want.append(animation.frame_of(a, b.start + t))       # the door opens with each change's first part
    have = _keys(door)
    for f in want:
        assert any(abs(k - f) < 0.51 for k in have), (f, have)
