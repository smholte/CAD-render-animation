"""Task 0039: air blast without Blender (core/air.py, the air in core/chips.py and core/gcode.py).

The chips scene is the one of tests/test_chips_core.py: a 200 x 200 mm block (top at z = 70 mm) on a table, a
flat end mill Ø10 that plunges 5 mm at frames 1..25, cuts a 50 mm slot along X until frame 75 and goes up.
"""

import math

import numpy as np
import pytest

from fresing_render.core import air as A
from fresing_render.core import chips as C
from fresing_render.core import gcode as G

from test_chips_core import FRAMES, TOP, scene, slot_bits


def on_block(bk, f) -> int:
    p = bk.at(f)[0]["pos"]
    return int(((abs(p[:, 0]) < 0.1) & (abs(p[:, 1]) < 0.1) & (p[:, 2] > TOP - 0.006)).sum())


def spindle_air(bits, spans, **kw):
    b = bits[0]
    return A.AirIn(spans, b.t, b.o, -b.d, **kw)


# ---------------------------------------------------------------------------
# the air itself


def test_the_jet_blows_along_its_line_and_falls_off():
    o, d = np.zeros(3), np.array([1.0, 0, 0])
    pts = np.array([[0.01, 0, 0], [0.05, 0, 0], [0.2, 0, 0], [0.3, 0, 0], [-0.05, 0, 0], [0.05, 0.05, 0]])
    U = A.velocity(pts, o, d, 18.0, math.radians(15), 0.25)
    m = np.linalg.norm(U, axis=1)
    assert m[0] == pytest.approx(18.0, rel=0.05)              # full speed near the nozzle
    assert m[0] > m[1] > m[2] > 0                              # slower further away
    assert m[3] == 0 and m[4] == 0                             # beyond its reach, behind the nozzle
    assert m[5] < 0.05 * m[1]                                  # outside the cone
    assert U[1, 0] > 0.9 * m[1]                                # along the jet


def test_the_wall_jet_blows_outwards_from_where_the_jet_hits():
    o, d = np.array([0, 0, 0.05]), np.array([0, 0, -1.0])
    hit = A.hit(o, d, 0.25, lambda x, y: np.zeros(len(x)))
    assert hit is not None and hit[1] == pytest.approx(0.05, abs=0.006) and abs(hit[0][2]) < 0.006
    pts = np.array([[0.03, 0, 0.002], [0, -0.06, 0.002], [0.2, 0, 0.002], [0.03, 0, 0.08]])
    U = A.velocity(pts, o, d, 18.0, math.radians(15), 0.25, wall=hit)
    assert U[0, 0] > 1.0 and abs(U[0, 1]) < 1e-6              # outwards in +X at +X
    assert U[1, 1] < -1.0                                      # outwards in -Y at -Y
    assert np.linalg.norm(U[0]) > np.linalg.norm(U[2])         # slower further out
    assert np.linalg.norm(U[3]) < 0.05 * np.linalg.norm(U[0])  # only close over the surface
    assert A.hit(o, d, 0.03, lambda x, y: np.zeros(len(x))) is None        # out of reach: no wall jet


def test_air_state_and_nozzle():
    air = A.AirIn([[10, 20, 0], [40, 50, 1]], [1, 100], [[0, 0, 0], [0.99, 0, 0]], [[0, 0, -1], [0, 0, -1]])
    assert air.state(5) == (False, False) and air.state(10) == (True, False) and air.state(20) == (False, False)
    assert air.state(45) == (True, True)
    assert air.next_on(1) == 10 and air.next_on(15) == 15 and air.next_on(30) == 40 and air.next_on(60) == math.inf
    o, d = air.nozzle(50.5)
    assert o[0] == pytest.approx(0.495) and d[2] == pytest.approx(-1.0)
    assert air.settings(True) == (air.speed * A.CLEAN_BOOST, A.CLEAN_CONE)
    assert air.seconds_on(25.0) == pytest.approx(0.8)
    assert A.spans_text(air.spans, 25.0) == "on 1 time, 0.4 s in all; blows the part clean for 0.4 s at the end"


def test_nozzle_from_world_into_riding_space():
    carry = np.tile(np.eye(4), (3, 1, 1))
    carry[:, 1, 3] = [0.0, 0.1, 0.2]                           # the table moves +Y
    o, d = A.nozzle_from_poses([[0, 0.5, 0]] * 3, [[0, 0, -1]] * 3, carry)
    assert np.allclose(o[:, 1], [0.5, 0.4, 0.3]) and np.allclose(d, [[0, 0, -1]] * 3)


# ---------------------------------------------------------------------------
# chips with air


def test_air_through_the_spindle_keeps_the_block_clear():
    bits = [slot_bits()]
    off = C.simulate(scene(bits))
    bits = [slot_bits()]
    inp = scene(bits)
    inp.air = spindle_air(bits, [[1, 88, 0]])
    on = C.simulate(inp)
    n_off, n_on = on_block(off, FRAMES), on_block(on, FRAMES)
    assert n_off > 100 and n_on < 0.1 * n_off, (n_off, n_on)
    assert on.stats["chips"] == off.stats["chips"]             # the same chips are made; they only fly elsewhere
    assert on.stats["air_s"] == pytest.approx(87 / 25)
    # (no air before frame 1 or after 88: the result before the cut is the same)
    a, b = on.at(1), off.at(1)
    assert np.array_equal(a[0]["pos"], b[0]["pos"])


def test_soft_air_far_away_does_less_than_strong_air():
    def run(strength, x=-0.08, h=0.04):
        bits = [slot_bits()]
        inp = scene(bits)
        t = np.arange(1, FRAMES + 1.0)
        dd = np.array([-x, 0, -h]) / math.hypot(x, h)
        inp.air = A.AirIn([[1, 88, 0]], t, np.tile([x, 0, TOP + h], (len(t), 1)), np.tile(dd, (len(t), 1)),
                          speed=A.STRENGTHS[strength])
        return on_block(C.simulate(inp), FRAMES)

    soft, strong = run("SOFT"), run("STRONG")
    assert strong < soft and strong < 20


def test_lying_chips_are_blown_off_at_the_end():
    bits = [slot_bits()]
    inp = scene(bits)
    o = bits[0].o.copy()
    o[:, 2] = np.maximum(o[:, 2], TOP + 0.015)
    inp.air = A.AirIn([[89, 100, 1]], bits[0].t, o, -bits[0].d)       # only "Blow the part clean"
    bk = C.simulate(inp)
    assert on_block(bk, 88) > 100                              # lying there before
    assert on_block(bk, FRAMES) <= 3                           # gone at the end
    assert bk.stats["blown"] > 100
    # a chip blown away is a new chip: the lying one ends, the copy flies on from the same spot
    woken = np.nonzero(np.isfinite(bk.end_t[:bk.stats["chips"]]) & (bk.end_t[:bk.stats["chips"]] > 89))[0]
    assert len(woken)
    assert len(bk.born) > bk.stats["chips"] and bk.born[bk.stats["chips"]:].min() >= 89
    assert "blown away" in C.describe(bk)


def test_air_gives_the_same_chips_every_time():
    def run():
        bits = [slot_bits()]
        inp = scene(bits)
        inp.air = spindle_air(bits, [[20, 60, 0], [89, 100, 1]])
        return C.simulate(inp)

    a, b = run(), run()
    assert a.stats["blown"] == b.stats["blown"]
    for f in (30, 70, 95, FRAMES):
        x, y = a.at(f), b.at(f)
        for sp in (0, 1):
            assert np.array_equal(x[sp]["pos"], y[sp]["pos"]) and np.array_equal(x[sp]["id"], y[sp]["id"])


def test_air_blows_fallen_chips_on_the_bed_too():
    bits = [slot_bits()]
    inp = scene(bits, flat_bed=True)
    t = np.arange(1, FRAMES + 1.0)
    # a strong nozzle low over the bed, in front of the table, blowing along +Y over the chips that fell there
    inp.air = A.AirIn([[89, 100, 1]], t, np.tile([0.3, -0.45, 0.01], (len(t), 1)), np.tile([0, 1.0, 0], (len(t), 1)),
                      speed=A.STRENGTHS["STRONG"], reach=0.6)
    bk = C.simulate(inp)
    ref = C.simulate(scene([slot_bits()], flat_bed=True))
    w0, w1 = ref.at(FRAMES)[1]["pos"], bk.at(FRAMES)[1]["pos"]

    def strip(w):
        return int(((w[:, 0] > 0.22) & (w[:, 0] < 0.38) & (w[:, 1] > -0.35) & (w[:, 1] < -0.1)).sum())
    assert strip(w0) > 50
    assert strip(w1) < 0.5 * strip(w0)


# ---------------------------------------------------------------------------
# when air blows: the program


PROG = """G21 G90 G17
S8000 M3
G0 X0 Y0 Z5
M7
G1 Z-2 F600
G1 X50 F1200
M9
G1 X60
M8
G1 X70
M9
M5
G0 Z20
M30
"""


def test_air_spans_from_the_codes():
    sch = G.Schedule(G.read(PROG), G.Timing())
    times = sch.m_times()
    assert [m for _t, m in times] == [7, 9, 8, 9]
    plunge = next(p for p in sch.pieces if p.move.kind == "FEED")
    x50 = next(p for p in sch.pieces if p.move.kind == "FEED" and p.move.b[0] == 50)
    assert times[0][0] == pytest.approx(plunge.v0) and times[1][0] == pytest.approx(x50.v0 + x50.vd)
    assert sch.air_spans() == [(pytest.approx(plunge.v0), pytest.approx(x50.v0 + x50.vd))]
    spans8 = sch.air_spans(8, 9)                               # M8 … M9
    assert len(spans8) == 1 and spans8[0][0] == pytest.approx(times[2][0])
    # always while the spindle turns: from S8000 M3 to M5
    on = sch.air_spans(150, 151, always=True)
    keys = sch.spindle_keys()
    assert len(on) == 1 and on[0][0] == pytest.approx(0.0)
    assert on[0][1] == pytest.approx(next(t for t, r in keys if r == 0 and t > 0))


def test_air_code_before_the_lines_shown_counts_from_the_start():
    prog = G.read(PROG)
    sch = G.Schedule(prog, G.Timing(line_from=6, line_to=6))         # only "G1 X50"
    assert sch.air_spans() == [(0.0, pytest.approx(sch.program_end))]


def test_user_codes_are_read_and_air_off_without_off_code_lasts_to_the_end():
    prog = G.read("G21 G90\nG0 X0 Y0 Z5\nM120\nG1 X10 F600\nG1 X20\nM30\n")
    assert [m for _k, m, _l in prog.m_events] == [120]
    assert any(p.code == "M120" for p in prog.problems)       # (the step leaves it out when it is the air code)
    sch = G.Schedule(prog, G.Timing())
    assert sch.air_spans(120, 121) == [(pytest.approx(sch.pieces[0].v0 + sch.pieces[0].vd), sch.program_end)]


def test_merge_spans():
    assert G.merge_spans([(3, 4), (0, 1), (1, 2), (5, 5)]) == [(0, 2), (3, 4)]


def test_clean_moves_go_over_the_cut_area():
    prog = G.read("G21 G90\nG0 X0 Y0 Z5\nG1 Z-2 F600\nG1 X100 F1200\nG1 Y60\nG0 Z30\nM30\n")
    moves = G.clean_moves(prog, (100, 60, 30), 2.0, True)
    assert sum(d for _m, d in moves) == pytest.approx(2.0)
    pts = [m.b for m, _d in moves]
    assert {round(p[2], 6) for p in pts} == {5 + G.CLEAN_LIFT}
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert min(xs) == 0 and max(xs) == 100 and min(ys) == 0 and max(ys) == 60
    assert moves[-1][0].kind == "DWELL" and moves[-1][1] == pytest.approx(2.0 * (1 - G.CLEAN_SWEEP))
    still = G.clean_moves(prog, (100, 60, 30), 2.0, False)
    assert len(still) == 1 and still[0][0].kind == "DWELL"   # already high enough: it stays there
    low = G.clean_moves(prog, (100, 60, 1), 2.0, False)
    assert low[0][0].b == (100, 60, 5 + G.CLEAN_LIFT)          # up to the blowing height, then still
