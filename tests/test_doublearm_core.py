"""Task 0064: the double-arm tool changer's plan (core/toolchange.py, core/gcode.py Schedule) – no Blender.

A magazine of 12 pots (carousel values: pot k at the station at (k - 1) * 30°), the head goes up to Z 200 for a change,
the arm grips, pulls, turns 180°, pushes and turns back; the old tool lands in the pot the new one came from.
"""

import math

import pytest

from fresing_render.core import gcode as core
from fresing_render.core import toolchange as TC

PITCH = TC.TURN / 12


def changer(**kw) -> TC.Changer:
    base = dict(atc=True, arm=True, position=(None, None, 200.0), pockets={1: 1, 2: 2, 3: 5, 4: 9},
                stations={k: (None, None, None) for k in range(1, 13)},
                carousel={k: (k - 1) * PITCH for k in range(1, 13)}, pitch=PITCH, turn_time=0.4, tip=TC.TIP_TIME,
                start_tool=1, rapid=(6000.0, 6000.0, 6000.0))
    base.update(kw)
    return TC.Changer(**base)


def program(text: str) -> core.Program:
    return core.read(text)


PROG = """G21 G90
G0 X0 Y0 Z10
G1 X50 F600
T2 M6
G0 X0 Y0 Z10
G1 X50 F600
T3 M6
G0 X10 Y0 Z10
G1 X60 F600
T4 M6
G0 X0 Y0 Z10
G1 X50 F600
T1 M6
G0 X0 Y0 Z10
G1 X50 F600
T3 M6
G0 X0 Y0 Z10
M30
"""


def schedule(text=PROG, **kw):
    timing_kw = {k: kw.pop(k) for k in ("speed", "fit_seconds", "factor") if k in kw}
    ch = changer(**kw)
    return core.Schedule(program(text), core.Timing(changer=ch, **timing_kw)), ch


def test_phases_and_times():
    sch, ch = schedule()
    c = sch.changes[0]
    assert c.kind == "arm" and c.old == 1 and c.tool == 2 and c.new_pocket == 2
    names = [ph.name for ph in c.phases if ph.kind == "arm"]
    assert names == list(TC.ARM_PHASES)
    t = c.arm_times()
    # the arm phases one after the other, at their default lengths
    for a, b in zip(TC.ARM_PHASES, TC.ARM_PHASES[1:]):
        assert t[a][1] == pytest.approx(t[b][0])
    for n in TC.ARM_PHASES:
        assert t[n][1] - t[n][0] == pytest.approx(TC.ARM_TIMES[n])
    # the arm starts once the head is up, the spindle oriented and the pot tipped down
    head_up = max(ph.t0 + ph.dur for ph in c.phases if ph.role == "out")
    o0, o1 = c.orient_span()
    tips = c.tips()
    down = [x for x in tips if x[3]]
    up = [x for x in tips if not x[3]]
    assert t["grip"][0] == pytest.approx(max(head_up, o1, down[0][1]))
    assert o0 == pytest.approx(c.start)
    # hand-overs: the old tool leaves the spindle at the grip's end, the new one is in at the push's end
    assert c.drop == pytest.approx(t["grip"][1]) and c.swap == pytest.approx(t["push"][1])
    # the pot tips up after the arm is back, while the head goes back; the change ends when both are done
    assert up[0][0] == pytest.approx(t["back"][1])
    back_end = max(ph.t0 + ph.dur for ph in c.phases if ph.role == "back")
    assert c.start + c.length == pytest.approx(max(back_end, up[0][1]))
    # the head travel: up to Z 200 and back to the program's point
    assert c.point_at(t["swap"][0], (50, 0, 10)) == pytest.approx((50.0, 0.0, 200.0))
    assert c.point_at(c.start + c.length, (50, 0, 10)) == pytest.approx((50.0, 0.0, 10.0))
    # tool-to-tool time (arm + orient) about 1.5–2.5 s at speed 1
    arm = t["back"][1] - t["grip"][0]
    assert 1.4 <= arm <= 2.5


def test_random_pockets_over_five_changes():
    sch, ch = schedule()
    assert [c.tool for c in sch.changes] == [2, 3, 4, 1, 3]
    # T2 from pot 2: T1 lands in pot 2. T3 from pot 5: T2 lands in 5. T4 from 9: T3 in 9. T1 from 2: T4 in 2.
    # T3 from 9: T1 in 9.
    assert [c.new_pocket for c in sch.changes] == [2, 5, 9, 2, 9]
    assert [c.old for c in sch.changes] == [1, 2, 3, 4, 1]
    # the table at the start is untouched (frame 1)
    assert sch.pocket_table == {1: 1, 2: 2, 3: 5, 4: 9}
    # every change brings its pot to the station: carousel at that pot's value at the arm's grip
    v = ch.carousel_start
    for c in sch.changes:
        for t0, t1, v0, v1 in c.turns():
            assert abs(v0 - v) < 1e-9
            v = v1
        assert math.isclose((v - ch.carousel[c.new_pocket] + math.pi) % TC.TURN - math.pi, 0.0, abs_tol=1e-9)


def test_shortest_turns():
    sch, _ch = schedule()
    for c in sch.changes:
        for _t0, _t1, v0, v1 in c.turns():
            assert abs(v1 - v0) <= math.pi + 1e-9


def test_never_turns_a_tipped_pot():
    sch, _ch = schedule()
    tips = sorted(x for c in sch.changes for x in c.tips())
    turns = [x for c in sch.changes for x in c.turns()]
    # spans where a pot is down: from a tip-down's start to the next tip-up's end
    down = []
    start = None
    for t0, t1, _pk, is_down in tips:
        if is_down:
            start = t0
        else:
            down.append((start, t1))
    for t0, t1, _v0, _v1 in turns:
        for a, b in down:
            assert t1 <= a + 1e-9 or t0 >= b - 1e-9


def test_pot_tip_off():
    sch, _ch = schedule(tip=0.0)
    assert all(not c.tips() for c in sch.changes)
    sch2, _ = schedule()
    assert sch.duration < sch2.duration


PRE = """G21 G90
G0 X0 Y0 Z10
T2
G1 X200 F600
T2 M6
T3
G0 X0 Y0 Z10
G1 X200 F600
T3 M6
G0 X0 Y0 Z10
M30
"""


def test_tn_pre_indexes_the_magazine():
    near = (None, None, 30.0)                          # a short way up: the magazine would hold the arm back
    sch, ch = schedule(PRE, position=near)
    plain, _ = schedule(PRE.replace("T2\n", "").replace("T3\n", ""), position=near)
    a, b = sch.changes
    assert a.prep and b.prep and a.pre_at is not None
    # the magazine works while the machine cuts: its turn and tip are done before the M6
    assert a.prep[-1].t0 + a.prep[-1].dur <= a.start + 1e-9
    assert a.prep[0].t0 == pytest.approx(a.pre_at)
    # T3's turn waits for the pot of the change before to tip up
    up = [x for x in a.tips() if not x[3]][0]
    assert b.prep[0].t0 >= up[1] - 1e-9
    # the changes are shorter: the arm starts as soon as the head is up
    assert a.length < plain.changes[0].length - 0.3
    assert sch.duration < plain.duration
    # the same pots and turns either way
    assert [c.new_pocket for c in sch.changes] == [c.new_pocket for c in plain.changes]


def test_tn_too_late_does_it_at_the_m6():
    text = PRE.replace("T2\nG1 X200 F600\nT2 M6", "G1 X200 F600\nT2\nT2 M6")
    sch, _ = schedule(text, position=(None, None, 30.0))
    a = sch.changes[0]
    assert not a.prep                                  # done in the change, as without a Tn
    assert any(ph.kind == "tip" and ph.name == "down" for ph in a.phases)


def test_tn_on_the_m6_line_is_no_pre_index():
    sch, _ = schedule(PRE.replace("T2\n", "", 1).replace("T3\n", "", 1))
    assert all(not c.prep for c in sch.changes)


def test_fit_into_squeezes_each_phase_to_its_minimum():
    sch, ch = schedule(speed="FIT", fit_seconds=10.0)
    assert sch.duration == pytest.approx(10.0, abs=1e-6)
    assert sum(c.length for c in sch.changes) == pytest.approx(5.0, abs=1e-6)
    assert sch.change_scale < 1.0
    for c in sch.changes:
        for ph in c.phases:
            if ph.kind == "arm":
                assert ph.dur >= TC.ARM_MIN - 1e-9
            if ph.kind == "tip":
                assert ph.dur >= TC.TIP_MIN - 1e-9
    # very tight: each phase at its minimum
    tight, _ = schedule(speed="FIT", fit_seconds=0.5)
    for c in tight.changes:
        for ph in c.phases:
            if ph.kind == "arm":
                assert ph.dur == pytest.approx(TC.ARM_MIN)


def test_atc_speed():
    slow, _ = schedule()
    quick = core.Schedule(program(PROG), core.Timing(changer=changer(speed=2.0)))
    a, b = slow.changes[0].arm_times(), quick.changes[0].arm_times()
    for n in TC.ARM_PHASES:
        assert b[n][1] - b[n][0] == pytest.approx((a[n][1] - a[n][0]) / 2)


def test_tool_without_pot_is_put_in_by_hand():
    sch, _ = schedule(pockets={1: 1, 2: 2})
    c = sch.changes[1]                                 # T3 has no pot
    assert c.kind != "arm" and "by hand" in c.note
    assert sch.changes[2].kind != "arm"                # T4 neither
    # T1 went into pot 2 at the first change; it comes back from there
    assert sch.changes[3].new_pocket == 2 and sch.changes[3].kind == "arm"


def test_same_tool_no_change():
    sch, _ = schedule("G21 G90\nT1 M6\nG0 X1 Y1 Z10\nM30\n")
    assert sch.changes[0].length == 0


def test_old_atc_unchanged():
    ch = changer(arm=False, tip=0.0)
    sch = core.Schedule(program(PROG), core.Timing(changer=ch))
    assert all(c.kind == "" for c in sch.changes)
    assert all(ph.group == -1 for c in sch.changes for ph in c.phases)
