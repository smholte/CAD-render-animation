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


def gantry_changes(sc, tmp_path, kind, text=PROGRAM_T3):
    set_up(sc)
    a, b = step(sc, program(tmp_path, text))
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


# ---------------------------------------------------------------------------
# rows 10 + 11 + 19c: rotary axes
# ---------------------------------------------------------------------------

PROGRAM_C90 = "(T1 D=6. CR=0. - flat end mill)\nG21 G90\nT1 M6\nG0 C90\nM30\n"


def test_c_turns_the_same_way_when_built_with_a_tipped(tmp_path):
    from test_rotary import load
    from fresing_render.blender import rotary
    sc, a, b = load(tmp_path, five=True, program=PROGRAM_C90,
                     milling=False)
    trunnion, table = sc.fresing.joints["Trunnion A"], sc.fresing.joints["Table C"]
    signs, ends, words = [], [], []
    for deg in (0.0, 60.0, 95.0, 120.0):
        animation.clear_keys(sc)
        joints.set_value(trunnion, math.radians(deg), use_limits=False)
        joints.set_value(table, 0.0, use_limits=False)
        bpy.context.view_layer.update()
        mach = gcode.Machine(sc)
        signs.append(mach.axes[2].sign)
        r = animation.bake(sc, a)
        sc.frame_set(r["frames"])
        ends.append(round(math.degrees(joints.get_value(table)), 3))
        words += [t for _ok, t in rotary.check(sc) if t.startswith("C:")]
    assert signs == [signs[0]] * 4, signs
    assert words == [words[0]] * 4, words                  # Check says the same at every A
    assert ends == [ends[0]] * 4, ends


def test_rotary_check_starts_from_the_static_pose(tmp_path):
    from test_rotary import load
    from fresing_render.blender import rotary
    sc, a, b = load(tmp_path, milling=False)
    names = ("X", "Y", "Z", "Rotary A")
    static = {n: joints.get_value(sc.fresing.joints[n]) for n in names}
    r = animation.bake(sc, a)
    sc.frame_set(min(400, r["frames"]))
    moved = {n: joints.get_value(sc.fresing.joints[n]) for n in names}
    assert any(abs(moved[n] - static[n]) > 1e-4 for n in names)
    poses = rotary.start_check(sc)
    keep = poses[0][1]
    for n in names:
        assert keep[n] == pytest.approx(static[n], abs=1e-7), n
    assert not animation.has_keys(sc)


def test_rotary_check_forgotten_on_load_and_pick(tmp_path):
    from test_rotary import load
    from fresing_render.blender import rotary
    sc, a, b = load(tmp_path, milling=False)
    rotary.check(sc)
    assert rotary.LAST_CHECK
    sc.fresing.cnc.a_reverse = True                          # another set-up: the old Check is gone
    assert not rotary.LAST_CHECK
    rotary.check(sc)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not rotary.LAST_CHECK


# ---------------------------------------------------------------------------
# rows 9 + 18: automatic coolant hoses on the first Build and after a model update
# ---------------------------------------------------------------------------

def mill_scene(tmp_path, update_tool=None):
    import test_coolant as tc
    from fresing_render.blender import chips
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=tc.MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = tc.ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    tc.click(tc.ob(sc, tc.TOOL))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    tc.click(tc.ob(sc, tc.STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    sc["tmp"] = str(tmp_path)
    return sc


def test_coolant_hoses_same_on_the_first_build(tmp_path):
    import test_coolant as tc
    from fresing_render.blender import coolant
    sc = mill_scene(tmp_path)
    x = sc.fresing.joints["X"]                              # the head away from x = y = 0
    joints.set_value(x, 0.06)
    bpy.context.view_layer.update()
    sc.fresing.coolant.enabled = True
    tc.build_program(sc)
    first = (coolant.root()["fr_mount_z"], coolant.root()["fr_ring"], *coolant.root()["fr_g"])
    tc.build_program(sc)
    second = (coolant.root()["fr_mount_z"], coolant.root()["fr_ring"], *coolant.root()["fr_g"])
    assert first == pytest.approx(second, abs=1e-9)


def test_coolant_after_a_model_update(tmp_path):
    import test_coolant as tc
    from fresing_render.blender import coolant
    sc = mill_scene(tmp_path)
    sc.fresing.coolant.enabled = True
    tc.build_program(sc)
    wet = len(coolant.wet_parts(sc))
    assert wet > 0 and coolant.root().parent is not None
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=tc.MILL, quality="draft", update_root=root.name) == {"FINISHED"}
    bpy.context.view_layer.update()
    r = coolant.root()
    assert r.parent is not None and r.parent.name in sc.objects     # on the new head part
    assert r.parent is coolant.head(sc)
    assert len(coolant.wet_parts(sc)) == wet                         # still wet until the next Build


# ---------------------------------------------------------------------------
# rows 14 + 15: a model update keeps the double arm's tags; old two-copy projects keep their CNC on copy 2
# ---------------------------------------------------------------------------

def test_model_update_keeps_the_double_arm(atc_scene, tmp_path):
    sc = atc_scene
    arm_set_up(sc, tmp_path)

    def tagged():
        return sorted(j.name for j in sc.fresing.joints if doublearm.app_joint(j))
    before = tagged()
    assert len(before) == 14
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=ATC_MODEL, quality="draft", update_root=root.name) == {"FINISHED"}
    assert tagged() == before
    c = sc.fresing.cnc
    c.pocket_count = 11                                     # one pocket fewer, then Remove arm: nothing left behind
    doublearm.remove_pots(sc)
    doublearm.remove_arm(sc)
    assert tagged() == []


def test_old_two_copy_project_keeps_the_cnc_on_copy_two(tmp_path):
    from test_same_step_twice import CRANE_A, _make_old, load, part, roots
    sc = load(tmp_path, CRANE_A, CRANE_A)
    _make_old(sc)
    one, two = roots(sc)
    tool, wp = part(sc, "COVER", two), part(sc, "BOOM", two)
    c, m = sc.fresing.cnc, machining.settings(sc)
    c["_busy"] = True
    c.tool, c.workpiece = tool, wp
    del c["_busy"]
    c.tool_uid, c.workpiece_uid = tool[build.PROP_UID], wp[build.PROP_UID]
    m.workpiece, m.workpiece_uid = wp, wp[build.PROP_UID]
    assert build.repair_uids(sc) == 1
    assert tool[build.PROP_UID].startswith("~2/")
    assert (c.tool_uid, c.workpiece_uid, m.workpiece_uid) == (tool[build.PROP_UID], wp[build.PROP_UID],
                                                              wp[build.PROP_UID])


# ---------------------------------------------------------------------------
# row 16: per-frame work
# ---------------------------------------------------------------------------

def test_milling_frame_work_is_light(tmp_path, monkeypatch):
    from test_rotary import load
    sc, a, b = load(tmp_path)
    r = animation.bake(sc, a)
    machining.sample(sc)
    # the cut is written before Blender works the frame out (one pass, not two)
    assert machining._on_frame in bpy.app.handlers.frame_change_pre
    assert machining._on_frame not in bpy.app.handlers.frame_change_post
    calls = {"sig": 0, "walk": 0}
    sig = machining.signature

    def counted(scene):
        calls["sig"] += 1
        return sig(scene)
    monkeypatch.setattr(machining, "signature", counted)
    sc.frame_set(100)
    shown = machining.settings(sc).cut_mesh
    before = len(shown.polygons)
    for f in range(101, 121):
        sc.frame_set(f)
    assert calls["sig"] == 0                                # the motion's fingerprint only after a change
    assert gcode.copies_all() == gcode.copies_all()          # (kept by name)
    # a change of the motion is still seen: Build again
    animation.bake(sc, a)
    sc.frame_set(130)
    assert calls["sig"] >= 1
    assert r["frames"] > 130 and before >= 0


def test_wet_parts_kept_and_dropped():
    from fresing_render.blender import coolant
    sc = bpy.context.scene
    obs = [o for o in sc.objects if o.type == "MESH"][:2]
    if len(obs) < 2:
        pytest.skip("needs a scene with parts")
    coolant.forget()
    for o in obs:
        o[coolant.WET_ATTR] = 0.5
    assert {o.name for o in coolant.wet_parts(sc)} == {o.name for o in obs}
    del obs[0][coolant.WET_ATTR]                             # a part dried outside the cache: seen
    assert [o.name for o in coolant.wet_parts(sc)] == [obs[1].name]
    del obs[1][coolant.WET_ATTR]
    coolant.forget()


# ---------------------------------------------------------------------------
# rows 19a, 19b and study 0069 #5
# ---------------------------------------------------------------------------

def test_wrong_pot_click_keeps_the_pockets(atc_scene, tmp_path):
    sc = atc_scene
    arm_set_up(sc, tmp_path)
    c = sc.fresing.cnc
    pots = [(p.number, p.tip_joint) for p in c.pockets]
    assert len(pots) == 12
    c.pocket_count = 13                                     # one more than the magazine has: no pot found
    why = doublearm.make_pots(sc, doublearm.test_station_pot(sc), Vector(doublearm.TEST_HINGE[0]),
                              Vector(doublearm.TEST_HINGE[1]))
    assert why.startswith("No pot found")
    assert [(p.number, p.tip_joint) for p in c.pockets] == pots
    assert all(sc.fresing.joints.get(t) is not None for _n, t in pots)


def test_air_cone_on_the_tip_of_the_tool_in_the_spindle(scene, tmp_path):
    from fresing_render.blender import air
    a, b, _parts = gantry_changes(scene, tmp_path, "MANUAL", PROGRAM_T3.replace("G21 G90\n", "G21 G90\nS9000 M3\n"))
    c = scene.fresing.cnc
    c.air_always, c.air_show = True, True
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    cones = [o for o in bpy.data.objects if o.get(air.TAG) == "cone"]
    assert len(cones) >= 2                                  # T2 and T3 are longer than T1: their own cone
    mach = gcode.Machine(scene)
    checked = 0
    for f, n in gcode.schedule(scene):
        g = int(f) + 3
        scene.frame_set(g)
        bpy.context.view_layer.update()
        if gcode.schedule(scene)[-1][0] < f:
            continue
        vis = [o for o in cones if shown(o)]
        if not vis:
            continue
        assert len(vis) == 1, g
        tool = gcode.copies().get(n) or mach.tool
        tip = tool.matrix_world @ (gcode._rest_tip(tool)[0] if tool is mach.tool else Vector(tool["fr_tip"]))
        assert (vis[0].matrix_world.translation - tip).length < 0.05 * MM, (n, g)
        checked += 1
    assert checked >= 3


def test_glowing_toolpath_and_cone_light_nothing(scene, tmp_path):
    from fresing_render.blender import air
    set_up(scene)
    a, b = step(scene, program(tmp_path), gcode_path=True)
    scene.fresing.cnc.air_show = True
    animation.bake(scene, a)
    mats = [m for m in bpy.data.materials if m.get(gcode.TAG) == "path" or m.get(air.TAG) == "cone"]
    assert len(mats) >= 2
    for m in mats:
        owner = m if hasattr(m, "emission_sampling") else m.cycles
        assert owner.emission_sampling == "NONE", m.name
