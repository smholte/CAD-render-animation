"""Task 0041: tool changes in Blender, on the test gantry (tools/make_test_gantry.py, see tests/test_gcode.py).

The carousel beside the bed turns about x = 500, y = 0; its disc's underside is at z = 140. T2 (ball Ø4, 30 long)
hangs from it with its tip at (560, 0, 110), T3 (drill Ø5, 40 long) at (500, 60, 100). T1 (flat Ø6, 30 long) is in
the spindle with its tip at (0, 0, 80); the spindle's nose (its gauge line) is at z = 110.

The ATC here: 8 pockets round the carousel from pocket 1 at (560, 0, 140), counter-clockwise (pocket 3 is T3's place);
T1 stands in pocket 7, T2 and T3 in their CAD places (pockets 1 and 3), T4 (drawn) in pocket 4.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
from mathutils import Matrix, Vector  # noqa: E402

from fresing_render.blender import animation, gcode, joints, toolchange, video  # noqa: E402
from fresing_render.core import gcode as core  # noqa: E402
from fresing_render.core import toolchange as TC  # noqa: E402

from test_gcode import MM, T1, addon, click, ob, program, scene, set_up, step  # noqa: E402,F401

T2, T3 = "TOOL T2 BALL D4", "TOOL T3 DRILL D5"
DISC = "CAROUSEL DISC"
FPS = 25
STATION = Vector((560 * MM, 0, 140 * MM))

PROGRAM = """(T1 D=6. CR=0. - flat end mill)
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
T4 M6
G0 X40 Y20 Z5
T1 M6
G0 X0 Y0 Z5
M30
"""


def tools(sc, lengths=True):
    assert bpy.ops.fresing.cnc_tools_from_program() == {"FINISHED"}
    c = sc.fresing.cnc
    rows = {t.number: t for t in c.tools}
    rows[1].obj = ob(sc, T1)
    rows[2].obj = ob(sc, T2)
    rows[3].obj = ob(sc, T3)
    for n, length in ((1, 30), (2, 30), (3, 40), (4, 30)):
        rows[n].length = length * MM
    c.tool_lengths = lengths
    return rows


def manual(sc, tmp_path, **kw):
    set_up(sc)
    a, b = step(sc, program(tmp_path, PROGRAM), **kw)
    tools(sc)
    return a, b


def schedule(sc, a, b):
    mach = gcode.Machine(sc)
    prog = gcode.read_program(sc, b, mach, start=gcode.start_point(mach))[0]
    return core.Schedule(prog, gcode.timing(sc, a, b, mach))


def frame(a, b, t):
    return animation.frame_of(a, b.start) + t * FPS


def shown(o):
    return not o.hide_render


def at(sc, f):
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))


def tip_world(sc, name=T1):
    t = ob(sc, name)
    return t.matrix_world @ gcode._rest_tip(t)[0]


# ---------------------------------------------------------------------------
# manual changes
# ---------------------------------------------------------------------------

def test_manual_pause_default_and_slider(scene, tmp_path):
    a, b = manual(scene, tmp_path)
    assert b.gcode_tc_time == pytest.approx(1.0)                 # short by default (owner, 7 Nov)
    sch = schedule(scene, a, b)
    changes = [c for c in sch.changes if c.length > 0]
    assert len(changes) == 4
    assert all(c.length == pytest.approx(1.0) for c in changes)   # the head stays: only the pause
    assert all(c.swap == pytest.approx(c.start + 0.5) for c in changes)
    b.gcode_tc_time = 5.0
    assert b.gcode_tc_time == 5.0
    b.gcode_tc_time = 9.0                                         # the slider ends at 5 s
    assert b.gcode_tc_time == 5.0
    b.gcode_tc_time = 0.0
    sch = schedule(scene, a, b)
    assert all(c.length == 0 for c in sch.changes)


def test_manual_change_position_and_swap_frame(scene, tmp_path):
    a, b = manual(scene, tmp_path)
    c = scene.fresing.cnc
    c.change_mode = "Z"
    c.change_pos = (0, 0, 60 * MM)
    a.fps = str(FPS)
    r = animation.bake(scene, a)
    assert not [w for w in r["warnings"] if "T" in w and "list" in w], r["warnings"]
    sch = schedule(scene, a, b)
    ch = sch.changes[0]
    assert ch.tool == 2 and ch.moves
    copies = gcode.copies()
    t1 = ob(scene, T1)
    # the head goes up to Z 60 for the pause and back down to Z 5 afterwards
    mach = gcode.Machine(scene)
    at(scene, frame(a, b, ch.out_end + 0.01))
    z = mach.machine_of([joints.get_value(j) for j in mach.joints])[2]
    assert z == pytest.approx(60.0, abs=0.01)
    # the tool is swapped at the right frame: T1 before, the copy of T2 after
    at(scene, frame(a, b, ch.swap) - 0.5)
    assert shown(t1) and not shown(copies[2])
    at(scene, frame(a, b, ch.swap) + 0.5)
    assert not shown(t1) and shown(copies[2])
    at(scene, frame(a, b, ch.start + ch.length) + 0.01)
    z = mach.machine_of([joints.get_value(j) for j in mach.joints])[2]
    assert z == pytest.approx(5.0 + mach.g54[2], abs=0.01)          # Z5 of the program (G54) again


def test_manual_tip_on_program_between_changes(scene, tmp_path):
    """Between the changes the tool's tip is on the program's path within 0.01 mm (also with "Fit into")."""
    a, b = manual(scene, tmp_path, gcode_speed="FIT", gcode_fit=12.0)
    c = scene.fresing.cnc
    c.change_mode = "XYZ"
    c.change_pos = (100 * MM, 50 * MM, 60 * MM)
    c.tool_lengths = False
    r = animation.bake(scene, a)
    assert r["frames"] == animation.frame_of(a, 12.0)              # "Fit into" still exact
    sch = schedule(scene, a, b)
    assert sch.duration == pytest.approx(12.0, abs=1e-6)
    mach = gcode.Machine(scene)
    z = scene.fresing.cnc.zero_empty
    worst = 0.0
    spans = [(c_.start, c_.start + c_.length) for c_ in sch.changes if c_.length > 0]
    copies = gcode.copies()
    for p in sch.pieces:
        if p.move.kind not in ("FEED", "RAPID") or p.vd <= 0:
            continue
        for u in (0.25, 0.5, 0.75):
            t = p.v0 + u * p.vd
            if any(s0 - 1e-6 <= t <= s1 + 1e-6 for s0, s1 in spans):
                continue
            at(scene, frame(a, b, t))
            n = next((n for f, n in reversed(gcode.schedule(scene)) if f <= frame(a, b, t) + 1e-6), 0)
            o = copies.get(n) if n in copies else ob(scene, T1)
            tip = o.matrix_world @ Vector(o["fr_tip"]) if "fr_tip" in o else tip_world(scene)
            got = z.matrix_world.inverted() @ tip
            want = Vector(sch.point_at(t)) - Vector(mach.g54)
            worst = max(worst, (got / MM - want).length)
    assert worst < 0.01, worst


def test_hand_is_optional_and_lengthens_the_pause(scene, tmp_path):
    a, b = manual(scene, tmp_path)
    assert not b.gcode_hand                                       # off by default
    animation.bake(scene, a)
    assert not [o for o in bpy.data.objects if o.name.startswith(toolchange.HAND_NAME)]
    b.gcode_hand = True
    info = gcode.info(scene, b)
    assert any("2.8 s" in x and "hand" in x for x in info["tool_changes"]), info["tool_changes"]
    sch = schedule(scene, a, b)
    assert all(c.length == pytest.approx(TC.HAND_MIN) for c in sch.changes if c.length > 0)
    b.gcode_tc_time = 4.0                                         # a longer pause: no note, the hand waits outside
    assert not gcode.info(scene, b)["tool_changes"]
    b.gcode_tc_time = 1.0
    r = animation.bake(scene, a)
    assert not [w for w in r["warnings"] if "hand" in w.lower()], r["warnings"]
    hand = bpy.data.objects[toolchange.HAND_NAME]
    carried = {o["fr_cnc_carry"]: o for o in bpy.data.objects if "fr_cnc_carry" in o}
    assert sorted(carried) == [1, 2, 3, 4]
    ch = sch.changes[0]
    keys = TC.hand_keys(*ch.hand)
    grip0 = next(t for t, p in keys if p == "grip")
    at(scene, frame(a, b, ch.start) - 2)
    assert not shown(hand)
    # gripping the old tool (T1): the hand is round it, T1 itself has gone into the hand
    at(scene, frame(a, b, grip0) + 0.2)
    assert shown(hand) and shown(carried[1]) and not shown(ob(scene, T1))
    grip = hand.matrix_world.translation
    tip = tip_world(scene)
    assert abs((grip - tip).dot(Vector((0, 0, 1)))) < 0.05      # at the holder, just above the tip
    assert (Vector((grip.x, grip.y, 0)) - Vector((tip.x, tip.y, 0))).length < 1e-3
    # the copy in the hand is where T1 was
    held = carried[1].matrix_world @ gcode._rest_tip(ob(scene, T1))[0]
    assert (held - tip).length < 0.02
    # at the end: the hand gone, T2 in the spindle
    at(scene, frame(a, b, ch.start + ch.length) + 1)
    assert not shown(hand) and not shown(carried[2]) and shown(gcode.copies()[2])
    # Clear keys removes it
    animation.clear_keys(scene)
    assert not [o for o in bpy.data.objects if o.name.startswith(toolchange.HAND_NAME)]
    assert not [o for o in bpy.data.objects if "fr_cnc_carry" in o]


def test_hand_shape_is_clean():
    me = toolchange.hand_mesh()
    try:
        assert len(me.polygons) > 300
        co = [v.co for v in me.vertices]
        xs, ys, zs = ([c[i] for c in co] for i in range(3))
        assert 0.07 < max(xs) - min(xs) < 0.14                  # a hand's width, in m
        assert max(ys) - min(ys) < 0.25
        # every edge shared by two faces: closed pieces (no holes to see through)
        from collections import Counter
        edges = Counter(tuple(sorted(e)) for p in me.polygons for e in p.edge_keys)
        assert all(n == 2 for n in edges.values())
    finally:
        bpy.data.meshes.remove(me)


def test_caption_at_tool_changes(scene, tmp_path):
    a, b = manual(scene, tmp_path)
    assert video.change_captions(a, scene) == []
    b.gcode_tc_caption = True
    caps = video.change_captions(a, scene)
    assert [c[0] for c in caps] == ["Tool change: T2 Ø4 ball end mill", "Tool change: T3 Ø5 drill",
                                    "Tool change: T4 Ø8 bull-nose end mill", "Tool change: T1 Ø6 flat end mill"]
    sch = schedule(scene, a, b)
    assert caps[0][1] == pytest.approx(b.start + sch.changes[0].start)
    rows = {t.number: t for t in scene.fresing.cnc.tools}
    rows[3].name = "Gühring 5 mm"
    assert video.change_captions(a, scene)[1][0] == "Tool change: T3 Ø5 drill (Gühring 5 mm)"
    # captions show even with step-label captions off; with them on, both kinds
    assert not a.fin_captions
    fin = video.finishing_for_animation(scene, a)
    assert fin.captions_on
    assert len(video.captions_of(a, scene)) == 4


# ---------------------------------------------------------------------------
# the tool changer
# ---------------------------------------------------------------------------

def atc(sc, tmp_path, **kw):
    set_up(sc)
    car = ob(sc, "CAROUSEL.ASM")
    joints.create(sc, "ROTATE", [car], Vector((500 * MM, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    a, b = step(sc, program(tmp_path, PROGRAM), **kw)
    a.fps = str(FPS)
    rows = tools(sc)
    rows[1].pocket = 7
    c = sc.fresing.cnc
    c.changer = "ATC"
    c.carousel_joint = "Carousel"
    toolchange.add_pocket(sc, ob(sc, DISC), STATION)
    c.pocket_count = 8
    assert toolchange.fill_carousel(sc) == ""
    assert not toolchange.problems(sc), toolchange.problems(sc)
    return a, b


def pocket(sc, n):
    return next(p for p in sc.fresing.cnc.pockets if p.number == n)


def test_pockets_round_the_carousel(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    c = scene.fresing.cnc
    assert [p.number for p in c.pockets] == list(range(1, 9))
    w3 = toolchange.pocket_world(pocket(scene, 3))[0]
    assert (w3 - Vector((500 * MM, 60 * MM, 140 * MM))).length < 1e-6       # counter-clockwise: T3's place
    markers = [o for o in bpy.data.objects if o.get(gcode.TAG) == toolchange.POCKET_TAG]
    assert len(markers) == 8 and all(m.parent is ob(scene, DISC) for m in markers)
    assert toolchange.tool_pockets(scene, [1, 2, 3, 4]) == {1: 7, 2: 1, 3: 3, 4: 4}
    c.pockets_reverse = True
    assert toolchange.fill_carousel(scene) == ""
    w3 = toolchange.pocket_world(pocket(scene, 3))[0]
    assert (w3 - Vector((500 * MM, -60 * MM, 140 * MM))).length < 1e-6
    # the carousel turned: pockets go with it, the stations stay
    j = scene.fresing.joints["Carousel"]
    joints.set_value(j, math.radians(90))
    bpy.context.view_layer.update()
    w1 = toolchange.pocket_world(pocket(scene, 1))[0]
    assert (w1 - Vector((500 * MM, 60 * MM, 140 * MM))).length < 1e-6
    st, values, _notes = toolchange.stations(scene, gcode.Machine(scene))
    assert st[1] == pytest.approx((560.0, 0.0, 30.0), abs=1e-3)          # (Blender's float32 matrices)
    assert math.remainder(values[1], TC.TURN) == pytest.approx(0.0, abs=1e-6)
    assert math.remainder(values[3], TC.TURN) == pytest.approx(math.radians(90), abs=1e-6)   # clockwise now


def test_atc_every_change_frame_by_frame(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sch = schedule(scene, a, b)
    changes = [c for c in sch.changes if c.length > 0]
    assert [(c.old, c.tool, c.old_pocket, c.new_pocket) for c in changes] == [
        (1, 2, 7, 1), (2, 3, 1, 3), (3, 4, 3, 4), (4, 1, 4, 7)]
    copies = gcode.copies()
    in_pocket = {o["fr_cnc_pocket"]: o for o in bpy.data.objects if "fr_cnc_pocket" in o}
    assert sorted(in_pocket) == [1, 4]                       # T2, T3 are CAD parts in the carousel already
    t1, t2, t3 = ob(scene, T1), ob(scene, T2), ob(scene, T3)
    shown_in_pocket = {1: in_pocket[1], 2: t2, 3: t3, 4: in_pocket[4]}
    shown_in_spindle = {1: t1, 2: copies[2], 3: copies[3], 4: copies[4]}

    # frame 1: every tool in its pocket, the spindle's tool not also in its pocket
    at(scene, 1)
    assert shown(t1) and not shown(in_pocket[1])
    assert shown(t2) and shown(t3) and shown(in_pocket[4])
    assert not any(shown(copies[n]) for n in (2, 3, 4))
    # T4's copy hangs in pocket 4 with its gauge line on the pocket's point
    p4 = toolchange.pocket_world(pocket(scene, 4))[0]
    tip4 = in_pocket[4].matrix_world @ Vector(copies[4]["fr_tip"])
    assert (tip4 + Vector((0, 0, 30 * MM)) - p4).length < 1e-5

    mach = gcode.Machine(scene)
    for c in changes:
        for when, pk in ((c.drop, c.old_pocket), (c.swap, c.new_pocket)):
            at(scene, frame(a, b, when))
            # the right pocket has come round to the station, and the spindle's gauge line is in it
            got = toolchange.pocket_world(pocket(scene, pk))[0]
            assert (got - STATION).length < 0.01 * MM, (c.tool, pk, got)
            m = mach.machine_of([joints.get_value(j) for j in mach.joints])
            assert m == pytest.approx((560.0, 0.0, 30.0), abs=0.01)     # tool lengths: 0 in the pocket
        # just after the drop: the old tool is back in its own pocket, the spindle is empty
        at(scene, frame(a, b, c.drop) + 0.5)
        assert shown(shown_in_pocket[c.old]) and not shown(shown_in_spindle[c.old])
        assert not any(shown(o) for o in shown_in_spindle.values())
        # just after the swap: the new tool in the spindle and not in its pocket
        at(scene, frame(a, b, c.swap) + 0.5)
        assert shown(shown_in_spindle[c.tool]) and not shown(shown_in_pocket[c.tool])
        assert shown(shown_in_pocket[c.old])
        assert sum(shown(o) for o in shown_in_spindle.values()) == 1
    # T3 went back to the pocket it came from: where the CAD put it, turned with the carousel
    at(scene, frame(a, b, changes[2].drop) + 0.5)
    v = joints.get_value(scene.fresing.joints["Carousel"])
    want = Vector((500 * MM, 0, 100 * MM)) + Matrix.Rotation(v, 3, "Z") @ Vector((0, 60 * MM, 0))
    assert (tip_world(scene, T3) - want).length < 1e-6


def test_atc_two_program_steps_share_the_pocket_tools(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    b2 = a.blocks.add()
    b2.kind = "GCODE"
    b2.gcode_file = b.gcode_file
    b2.start = b.duration + 1.0
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    in_pocket = {o["fr_cnc_pocket"]: o for o in bpy.data.objects if "fr_cnc_pocket" in o}
    assert sorted(in_pocket) == [1, 4]                    # one copy per tool, not one per step
    in_pocket[2], in_pocket[3] = ob(scene, T2), ob(scene, T3)
    spindle = {n: [o for o in bpy.data.objects if o.get("fr_cnc_t") == n] for n in (2, 3, 4)}
    spindle[1] = [ob(scene, T1)]
    seen = set()
    for f in range(1, r["frames"] + 1, 7):                # never in its pocket and in the spindle at once
        scene.frame_set(f)
        for n in (1, 2, 3, 4):
            in_sp = any(shown(o) for o in spindle[n])
            assert not (in_sp and shown(in_pocket[n])), (f, n)
            if in_sp:
                seen.add(n)
    assert seen == {1, 2, 3, 4}


def test_atc_carousel_turns_the_shortest_way(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    sch = schedule(scene, a, b)
    turns = [x for c in sch.changes for x in c.turns()]
    for _t0, _t1, v0, v1 in turns:
        assert abs(v1 - v0) <= math.pi + 1e-9
    # T1 -> T2: pocket 7 (at -90°) to the station first: +90°, not -270°; then pocket 1 back: -90°
    t = sch.changes[0].turns()
    assert [round(math.degrees(v1 - v0)) for _a, _b, v0, v1 in t] == [90, -90]
    # time per change from the motion's own speeds; "Changer speed" makes the turns faster
    t_real = sum(t1 - t0 for t0, t1, _v0, _v1 in turns)
    b.gcode_changer_speed = 2.0
    sch2 = schedule(scene, a, b)
    t_fast = sum(t1 - t0 for c in sch2.changes for t0, t1, _v0, _v1 in c.turns())
    assert t_fast < t_real


def test_atc_fit_into_and_tip_on_program(scene, tmp_path):
    a, b = atc(scene, tmp_path, gcode_speed="FIT", gcode_fit=20.0)
    scene.fresing.cnc.tool_lengths = False
    sch = schedule(scene, a, b)
    assert sch.duration == pytest.approx(20.0, abs=1e-6)
    assert sch.change_scale < 1.0                               # the changes were shortened
    assert sum(c.length for c in sch.changes) == pytest.approx(10.0, abs=1e-3)
    r = animation.bake(scene, a)
    assert r["frames"] == animation.frame_of(a, 20.0)
    mach = gcode.Machine(scene)
    worst = 0.0
    for p in sch.pieces:
        if p.move.kind not in ("FEED", "RAPID") or p.vd <= 0:
            continue
        t = p.v0 + 0.5 * p.vd
        at(scene, frame(a, b, t))
        m = mach.machine_of([joints.get_value(j) for j in mach.joints])
        want = sch.point_at(t)
        worst = max(worst, max(abs(x - y) for x, y in zip(m, want)))
    assert worst < 0.01, worst


def test_atc_with_changer_animation(scene, tmp_path):
    """The changer's own animation plays split at its swap: before the drop, and after the new tool is in."""
    a, b = atc(scene, tmp_path)
    s = scene.fresing
    seq = s.animations.add()
    seq.name = "Cover"
    x = seq.blocks.add()                          # a step on the carousel itself is left out (the app turns it)
    x.kind, x.joint, x.start, x.duration = "JOINT", "Carousel", 0.0, 1.0
    b.gcode_atc = "Cover"
    b.gcode_atc_swap = 0.5
    s.animations_index = list(s.animations).index(a)
    r = animation.bake(scene, a)
    assert any("turns the carousel" in w for w in r["warnings"]), r["warnings"]
    sch = schedule(scene, a, b)
    parts = sch.changes[1].seq_parts()
    assert [(s0, s1) for _t, s0, s1, _k in parts] == [(0.0, 0.5), (0.5, 1.0)]
    assert parts[0][0] < sch.changes[1].drop and parts[1][0] >= sch.changes[1].swap - 1e-9


def test_old_project_with_changer_animation_plays_as_before(scene, tmp_path):
    """A project of 0.2.43 with a tool-changer animation: opened, the machine is an ATC; no pockets: the animation
    plays at every M6 for its own length, the swap where it was, the head does not move."""
    set_up(scene)
    s = scene.fresing
    seq = s.animations.add()
    seq.name = "ATC"
    x = seq.blocks.add()
    x.kind, x.joint, x.start, x.duration = "JOINT", "X", 0.0, 3.0      # (an axis: left out, as before)
    a, b = step(scene, program(tmp_path, "G0 X10\nT2 M6\nG0 X20\nT3 M6\nG0 X30\nM30\n"))
    b.gcode_atc = "ATC"
    b.gcode_atc_swap = 1.5
    s.cnc.pop("changer", None)
    toolchange.upgrade(scene)
    assert s.cnc.changer == "ATC"
    sch = schedule(scene, a, b)
    assert [c.length for c in sch.changes] == [pytest.approx(3.0)] * 2
    assert [c.swap - c.start for c in sch.changes] == [pytest.approx(1.5)] * 2
    assert not any(c.moves for c in sch.changes)
    # a project that chose Manual is left alone
    s.cnc.changer = "MANUAL"
    toolchange.upgrade(scene)
    assert s.cnc.changer == "MANUAL"


def test_rack_head_goes_to_each_pocket(scene, tmp_path):
    """No carousel joint: a rack; the head goes to each tool's pocket."""
    set_up(scene)
    a, b = step(scene, program(tmp_path, PROGRAM))
    a.fps = str(FPS)
    rows = tools(scene)
    rows[1].pocket, rows[4].pocket = 7, 8
    c = scene.fresing.cnc
    c.changer = "ATC"
    disc = ob(scene, DISC)
    toolchange.add_pocket(scene, disc, STATION)                    # 1: T2's place
    toolchange.add_pocket(scene, disc, Vector((500 * MM, 60 * MM, 140 * MM)), 3)    # T3's place
    toolchange.add_pocket(scene, disc, Vector((440 * MM, 0, 140 * MM)), 7)
    toolchange.add_pocket(scene, disc, Vector((500 * MM, -60 * MM, 140 * MM)), 8)
    sch = schedule(scene, a, b)
    ch = [x for x in sch.changes if x.length > 0]
    assert [(x.old_pocket, x.new_pocket) for x in ch] == [(7, 1), (1, 3), (3, 8), (8, 7)]
    assert not any(x.turns() for x in ch)
    k = ch[1]                                            # T2 into pocket 1 at x 560, T3 from pocket 3 at y 60
    assert k.point_at(k.drop, None) == pytest.approx((560.0, 0.0, 30.0), abs=1e-3)
    assert k.point_at(k.swap, None) == pytest.approx((500.0, 60.0, 30.0), abs=1e-3)


def test_bench_tool_on_atc_is_put_in_by_hand(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    rows = {t.number: t for t in scene.fresing.cnc.tools}
    rows[4].place = "BENCH"
    info = gcode.info(scene, b)
    assert "T4 has no pocket: it is put in by hand" in info["tool_changes"]
    sch = schedule(scene, a, b)
    c4 = sch.changes[2]
    assert c4.tool == 4 and c4.new_pocket is None and any(ph.kind == "pause" for ph in c4.phases)


def test_two_tools_in_one_pocket_warns(scene, tmp_path):
    atc(scene, tmp_path)
    rows = {t.number: t for t in scene.fresing.cnc.tools}
    rows[4].pocket = 1                                   # where T2's part already stands
    assert any("T2 and T4 all stand in pocket 1" in w for w in toolchange.problems(scene)), toolchange.problems(scene)


def test_pockets_survive_saving_and_model_update(scene, tmp_path):
    a, b = atc(scene, tmp_path)
    path = os.path.join(str(tmp_path), "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    c = sc.fresing.cnc
    assert c.changer == "ATC" and len(c.pockets) == 8 and c.carousel_joint == "Carousel"
    assert all(p.obj is not None and p.uid for p in c.pockets)
    gcode.before_model_update(sc)
    assert not [o for o in bpy.data.objects if o.get(gcode.TAG) == toolchange.POCKET_TAG]
    gcode.after_model_update(sc, {}, {})
    assert len([o for o in bpy.data.objects if o.get(gcode.TAG) == toolchange.POCKET_TAG]) == 8


def test_joint_rename_follows(scene, tmp_path):
    atc(scene, tmp_path)
    j = scene.fresing.joints["Carousel"]
    j.name = "Tool carousel"
    assert scene.fresing.cnc.carousel_joint == "Tool carousel"


# ---------------------------------------------------------------------------
# task 0096: no dive after a tool change; an M6 without G43
# ---------------------------------------------------------------------------

def _spindle_tool(sc, n):
    """The object that shows tool n in the spindle and its tip in its own space."""
    if n == 1:
        o = ob(sc, T1)
        return o, gcode._rest_tip(o)[0]
    o = gcode.copies()[n]
    return o, Vector(o["fr_tip"])


def _lowest_tip_in_changes(sc, a, b, sch, spans=None):
    """The lowest tip of the tool in the spindle in the work zero's frame, minus the program's point, over every
    change (mm), read from the built animation frame by frame (not near a swap, where the copies are switched)."""
    z = sc.fresing.cnc.zero_empty
    mach = gcode.Machine(sc)
    worst = math.inf
    for p in sch.pieces:
        c = p.change
        if c is None or c.length <= 0:
            continue
        want = (Vector(p.move.b) - Vector(mach.g54)).z
        for t0, t1 in (spans(c) if spans else [(c.start, c.start + c.length)]):
            for k in range(41):
                t = t0 + (t1 - t0) * k / 40
                if min(abs(t - c.swap), abs(t - c.drop)) * FPS < 0.6 or c.drop < t < c.swap:
                    continue                        # (between them the spindle is empty: the hand has the tool)
                at(sc, frame(a, b, t))
                o, tip = _spindle_tool(sc, c.old if t < c.swap else c.tool)
                assert shown(o), (c.old, c.tool, t, c.start, c.drop, c.swap, c.start + c.length)
                got = (z.matrix_world.inverted() @ (o.matrix_world @ tip)).z / MM
                worst = min(worst, got - want)
    return worst


@pytest.mark.parametrize("mode", ["STAY", "Z", "XYZ"])
def test_longer_tool_never_dives_after_a_manual_change(scene, tmp_path, mode):
    """T3 is 10 mm longer than T2. Its tip never goes below the program's point while the tool is changed (before
    0.2.74 the head stayed with the old tool's lift at the swap: T3 went 10 mm below Z5), and lands on it."""
    a, b = manual(scene, tmp_path, gcode_hand=(mode == "STAY"))
    a.fps = str(FPS)
    c = scene.fresing.cnc
    c.change_mode = mode
    c.change_pos = (100 * MM, 50 * MM, -40 * MM)            # 5 mm above the program's Z5 (the zero is 50 mm lower)
    r = animation.bake(scene, a)
    assert not [w for w in r["warnings"] if "G43" in w], r["warnings"]
    sch = schedule(scene, a, b)
    assert [(ch.old, ch.tool) for ch in sch.changes if ch.length > 0] == [(1, 2), (2, 3), (3, 4), (4, 1)]
    assert _lowest_tip_in_changes(scene, a, b, sch) >= -0.01


def test_longer_tool_never_dives_after_an_atc_change(scene, tmp_path):
    """ATC: on the first leg out and the last leg back (where the tool lengths fade) the tip stays at or above the
    program's point; the hand-overs at the pockets are as before (the frame-by-frame test above)."""
    a, b = atc(scene, tmp_path)
    r = animation.bake(scene, a)
    assert not r["warnings"], r["warnings"]
    sch = schedule(scene, a, b)
    worst = _lowest_tip_in_changes(scene, a, b, sch, lambda c: [(c.start, c.lift_end),
                                                                (c.lift_start, c.start + c.length)])
    assert worst >= -0.01


NO_G43 = """(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
(T3 D=5. CR=0. TAPER=118deg - drill)
(T4 D=8. CR=1. - bullnose end mill)
G21 G90
T1 M6 G43 H1
G0 X10 Y0 Z5
T3 M6
G0 X30 Y10 Z5
G1 X40 F600
M30
"""


def test_m6_without_g43_keeps_the_old_offset_warns_and_clashes(scene, tmp_path):
    """T3 (10 mm longer than T1) put in without a G43 H3: as on the machine T1's offset stays and T3's tip runs 10 mm
    below the program. The Build says so with the depth, the step's summary too, and the clash check shows a row."""
    set_up(scene)
    a, b = step(scene, program(tmp_path, NO_G43))
    a.fps = str(FPS)
    tools(scene)
    r = animation.bake(scene, a)
    lines = [w for w in r["warnings"] if "G43" in w]
    assert len(lines) == 1 and "T3 (M6 on line 8) is 10.0 mm longer than T1 and has no G43 H3" in lines[0], lines
    assert "10.0 mm below" in lines[0]
    sch = schedule(scene, a, b)
    assert any("no G43 H3" in x for x in toolchange.notes(scene, sch))
    mach = gcode.Machine(scene)
    z = scene.fresing.cnc.zero_empty
    feed = next(p for p in sch.pieces if p.move.kind == "FEED")
    at(scene, frame(a, b, feed.v0 + feed.vd / 2))
    o, tip = _spindle_tool(scene, 3)
    got = z.matrix_world.inverted() @ (o.matrix_world @ tip) / MM
    want = Vector(sch.point_at(feed.v0 + feed.vd / 2)) - Vector(mach.g54)
    assert got.z == pytest.approx(want.z - 10.0, abs=0.01)
    rows = gcode.g43_rows(scene)
    assert len(rows) == 1 and rows[0][2] == pytest.approx(10 * MM) and rows[0][3] == 3
    from fresing_render.blender import clash
    run = clash.check(scene)
    mine = [x for x in run.rows if "no G43 H3" in x.a]
    assert len(mine) == 1 and mine[0].kind == "CLASH" and mine[0].depth == pytest.approx(10 * MM)
    assert scene.fresing.clash.clashes >= 1
    # with G43 H3 after the M6: nothing to say, the tip on the program
    b.gcode_file = program(tmp_path, NO_G43.replace("T3 M6\n", "T3 M6\nG43 H3\n"), "fixed.ngc")
    r = animation.bake(scene, a)
    assert not [w for w in r["warnings"] if "G43" in w]
    assert gcode.g43_rows(scene) == []
