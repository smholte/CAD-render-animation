"""Task 0041: tool changes planned without Blender (core/toolchange.py and core/gcode.Schedule)."""

import math

import pytest

from fresing_render.core import gcode as G
from fresing_render.core import toolchange as TC

PROG = "G21 G90\nG0 X10 Y0 Z5\nT2 M6\nG0 X10 Y0 Z5\nG1 X20 F600\nT3 M6\nG0 X30\nM30\n"


def sched(**kw):
    return G.Schedule(G.read(PROG), G.Timing(**kw))


def test_without_changer_as_before():
    """No changer given (Timing of 0.2.43): a pause of 'tool_change' s, the swap at 'swap'."""
    s = sched(tool_change=2.0, swap=0.5)
    assert [(c.length, c.swap - c.start) for c in s.changes] == [(2.0, 0.5), (2.0, 0.5)]
    assert [e[3] for e in s.tool_events] == [2.0, 2.0]


def test_manual_pause_and_swap_half_way():
    s = sched(changer=TC.Changer(pause=1.0))
    assert all(c.length == pytest.approx(1.0) and c.swap - c.start == pytest.approx(0.5) for c in s.changes)
    assert not any(c.moves for c in s.changes)
    s = sched(changer=TC.Changer(pause=0.0))
    assert all(c.length == 0 for c in s.changes)


def test_manual_change_position_z_first_and_back():
    ch = TC.Changer(position=(100.0, 50.0, 80.0), pause=1.0, rapid=(6000.0, 6000.0, 6000.0))
    s = sched(changer=ch)
    c = s.changes[0]
    k = c.knots()
    pts = [p for _t, p in k]
    assert pts[0] == (10.0, 0.0, 5.0)
    assert pts[1] == (10.0, 0.0, 80.0)                  # up first
    assert pts[2] == (100.0, 50.0, 80.0)
    assert pts[-2] == (10.0, 0.0, 80.0) and pts[-1] == (10.0, 0.0, 5.0)    # over, then down
    up = 75 / 6000 * 60
    assert k[1][0] - k[0][0] == pytest.approx(up)
    assert c.length == pytest.approx(2 * up + 2 * (90 / 6000 * 60) + 1.0)
    assert c.out_end == pytest.approx(c.start + up + 0.9) and c.back_start == pytest.approx(c.out_end + 1.0)
    # the samples carry the travel; the tip is at the program again when the change ends
    assert s.point_at(c.start + c.length) == pytest.approx((10.0, 0.0, 5.0))
    assert s.point_at(c.out_end + 0.5) == pytest.approx((100.0, 50.0, 80.0))
    times = [t for t, _p in s.samples(25)]
    assert all(any(abs(t - tk) < 1e-9 for t in times) for tk, _p in k)
    # "Rapids faster" also makes the travel faster
    s2 = sched(changer=ch, rapid_factor=3.0)
    assert s2.changes[0].length == pytest.approx(1.0 + (c.length - 1.0) / 3)


def test_z_only_and_stay():
    s = sched(changer=TC.Changer(position=(None, None, 60.0), pause=0.5))
    pts = [p for _t, p in s.changes[0].knots()]
    assert pts == [(10.0, 0.0, 5.0), (10.0, 0.0, 60.0), (10.0, 0.0, 60.0), (10.0, 0.0, 5.0)]


def test_hand_minimum_and_events():
    s = sched(changer=TC.Changer(pause=1.0, hand=True))
    c = s.changes[0]
    assert c.length == pytest.approx(TC.HAND_MIN) and c.hand == (c.start, pytest.approx(TC.HAND_MIN))
    out_t, in_t = TC.hand_events(*c.hand)
    assert c.drop == pytest.approx(out_t) and c.swap == pytest.approx(in_t) and out_t < in_t
    keys = TC.hand_keys(0.0, 4.0)                       # longer pause: the hand waits outside, its moves keep pace
    assert keys[0] == (0.0, "out") and keys[-1] == (pytest.approx(4.0), "out")
    assert keys[1] == (0.5, "grip")
    assert [p for _t, p in keys] == ["out", "grip", "below", "out", "out", "below", "grip", "out"]
    assert keys[4][0] - keys[3][0] == pytest.approx(4.0 - TC.HAND_MIN)


def test_same_tool_is_no_change():
    prog = G.read("T1 M6\nG0 X10\nT2 M6\nG0 X20\nM30\n")
    s = G.Schedule(prog, G.Timing(changer=TC.Changer(pause=1.0, start_tool=1)))
    assert [c.length for c in s.changes] == [0.0, 1.0]
    s = G.Schedule(prog, G.Timing(changer=TC.Changer(pause=1.0)))      # nothing known in the spindle: it plays
    assert [c.length for c in s.changes] == [1.0, 1.0]


def test_nearest_turn():
    assert TC.nearest_turn(0.0, math.radians(270)) == pytest.approx(math.radians(-90))
    assert TC.nearest_turn(math.radians(350), 0.0) == pytest.approx(math.radians(360))
    lim = (0.0, math.radians(300))
    assert TC.nearest_turn(math.radians(10), math.radians(-60), lim) == pytest.approx(math.radians(300))


def carousel(**kw):
    return TC.Changer(atc=True, pockets={1: 7, 2: 1, 3: 3}, stations={n: (500.0, 0.0, 30.0) for n in range(1, 9)},
                      carousel={n: -(n - 1) * TC.TURN / 8 for n in range(1, 9)}, approach=100.0, start_tool=1,
                      rapid=(6000.0, 6000.0, 6000.0), turn_time=0.5, pitch=TC.TURN / 8, **kw)


def test_atc_order_of_a_change():
    s = sched(changer=carousel())
    c = s.changes[0]
    assert (c.old, c.tool, c.old_pocket, c.new_pocket) == (1, 2, 7, 1)
    kinds = [(ph.kind, ph.after) for ph in c.phases]
    # up, over (the carousel brings pocket 7 meanwhile), down: drop, up, turn to 1, down: swap, up, over, down
    assert kinds == [("move", ""), ("move", ""), ("move", "drop"), ("move", ""), ("turn", ""), ("move", "swap"),
                     ("move", ""), ("move", ""), ("move", "")]
    assert c.point_at(c.drop, None) == pytest.approx((500.0, 0.0, 30.0))
    assert c.point_at(c.swap, None) == pytest.approx((500.0, 0.0, 30.0))
    t = c.turns()
    assert len(t) == 2 and t[0][3] == pytest.approx(TC.TURN / 4) and t[1][3] == pytest.approx(0.0)
    assert t[0][0] == pytest.approx(c.start)            # turns while the head travels
    assert t[1][0] >= c.drop                            # turns after the old tool is in its pocket
    assert t[1][1] <= c.swap
    # the next change starts where the carousel stopped
    c2 = s.changes[1]
    assert c2.turns()[0][2] == pytest.approx(0.0) and c2.turns()[0][3] == pytest.approx(-TC.TURN / 4)


def test_atc_changer_speed_and_animation_split():
    real = sched(changer=carousel(seq=2.0, seq_swap=0.5))
    fast = sched(changer=carousel(seq=2.0, seq_swap=0.5, speed=2.0))
    c, f = real.changes[0], fast.changes[0]
    assert [(s0, s1) for _t, s0, s1, _k in c.seq_parts()] == [(0.0, 0.5), (0.5, 2.0)]
    assert [k for *_x, k in c.seq_parts()] == [pytest.approx(1.0)] * 2
    assert [k for *_x, k in f.seq_parts()] == [pytest.approx(0.5)] * 2
    assert c.seq_parts()[0][0] + 0.5 <= c.drop and c.seq_parts()[1][0] >= c.swap
    assert f.length < c.length


def test_fit_into_squeezes_changes_to_half_with_minimum():
    ch = carousel()
    long = sched(changer=ch)
    total = sum(c.length for c in long.changes)
    s = sched(changer=carousel(), speed="FIT", fit_seconds=total)       # changes would be all of it: half now
    assert s.duration == pytest.approx(total)
    assert sum(c.length for c in s.changes) == pytest.approx(total / 2, rel=1e-6)
    assert s.change_scale < 1.0
    for c in s.changes:                                  # the turns keep their minimum
        for t0, t1, _a, _b in c.turns():
            assert t1 - t0 >= TC.MIN_TURN - 1e-9
    # changes that fit already are not touched
    s = sched(changer=carousel(), speed="FIT", fit_seconds=total * 3)
    assert s.change_scale == 1.0 and s.duration == pytest.approx(total * 3)


def test_rack_and_bench_tool():
    st = {1: (500.0, 0.0, 30.0), 3: (500.0, 60.0, 30.0), 7: (440.0, 0.0, 30.0)}
    ch = TC.Changer(atc=True, pockets={1: 7, 2: 1}, stations=st, approach=50.0, start_tool=1, pause=1.0)
    s = sched(changer=ch)
    c1, c2 = s.changes
    assert c1.point_at(c1.drop, None) == pytest.approx((440.0, 0.0, 30.0))
    assert c1.point_at(c1.swap, None) == pytest.approx((500.0, 0.0, 30.0))
    assert c2.new_pocket is None and "put in by hand" in c2.note        # T3 has no pocket
    assert any(ph.kind == "pause" for ph in c2.phases)
