"""Task 0042: coolant without Blender - when it flows (M8 / M7 / M9), how wet the parts are, the liquid per frame."""

import math

import numpy as np

from fresing_render.core import coolant as c
from fresing_render.core import gcode

MM = 0.001
FPS = 25.0


def fr(sp):
    return [(a * FPS, b * FPS, k) for a, b, k in sp]


def test_flood_from_m8_to_m9():
    assert c.spans([(1.0, 8), (5.0, 9)], 10.0) == [(1.0, 5.0, c.FLOOD)]


def test_mist_from_m7_and_m9_stops_both():
    sp = c.spans([(1.0, 8), (2.0, 7), (5.0, 9)], 10.0)
    assert (1.0, 5.0, c.FLOOD) in sp and (2.0, 5.0, c.MIST) in sp and len(sp) == 2


def test_no_off_code_runs_to_the_end_of_the_program():
    assert c.spans([(3.0, 8)], 10.0) == [(3.0, 10.0, c.FLOOD)]


def test_repeated_on_codes_do_not_restart():
    assert c.spans([(1.0, 8), (2.0, 8), (4.0, 9), (6.0, 8), (7.0, 9)], 10.0) == [(1.0, 4.0, c.FLOOD),
                                                                               (6.0, 7.0, c.FLOOD)]


def test_own_codes_and_mist_off():
    # a machine with user codes: M101 flood, M102 off; mist code 0 = M7 is not mist (air only)
    sp = c.spans([(1.0, 101), (2.0, 7), (4.0, 102)], 10.0, flood_code=101, mist_code=0, off_code=102)
    assert sp == [(1.0, 4.0, c.FLOOD)]
    # M9 stops it too, whatever the off code
    assert c.spans([(1.0, 101), (3.0, 9)], 10.0, flood_code=101, off_code=102) == [(1.0, 3.0, c.FLOOD)]


def test_always_follows_the_spindle_and_off_is_off():
    keys = [(0.0, 0.0), (1.0, 9000.0), (6.0, 0.0), (7.0, -6000.0)]
    assert c.spans([], 9.0, keys, "FLOOD") == [(1.0, 6.0, c.FLOOD), (7.0, 9.0, c.FLOOD)]
    assert c.spans([], 9.0, keys, "MIST")[0][2] == c.MIST
    assert c.spans([(1.0, 8)], 9.0, keys, "OFF") == []


def test_flow_at_prefers_flood():
    sp = fr([(1.0, 5.0, c.FLOOD), (2.0, 8.0, c.MIST)])
    f = c.flow_at(np.array([0.5, 1.5, 3.0, 6.0, 9.0]) * FPS, sp)
    assert f.tolist() == [c.OFF, c.FLOOD, c.FLOOD, c.MIST, c.OFF]


def test_wetness_rises_and_dries():
    sp = fr([(1.0, 5.0, c.FLOOD)])
    w = c.wetness(np.array([0.5, 1.0, 1.6, 4.99, 5.0, 7.0, 9.0, 9.5]) * FPS, sp, FPS, rise=0.6, dry=4.0)
    assert w[0] == 0.0 and w[1] == 0.0
    assert abs(w[2] - (1 - math.exp(-1))) < 1e-6          # one time constant after M8: 63 %
    assert w[3] > 0.99 and abs(w[4] - w[3]) < 1e-3         # continuous where the coolant stops
    assert 0.3 < w[5] < 0.7                                 # half way through drying
    assert w[6] == 0.0 and w[7] == 0.0                      # dry 4 s after M9


def test_wetness_is_the_same_in_any_order():
    sp = fr([(1.0, 5.0, c.FLOOD), (6.0, 7.0, c.MIST)])
    T = np.arange(0, 300, 1.0)
    full = c.wetness(T, sp, FPS)
    rng = np.random.default_rng(3)
    for t in rng.permutation(T)[:40]:
        assert c.wetness([t], sp, FPS)[0] == full[int(t)]


def test_wet_again_before_dry_and_mist_is_less_wet():
    sp = fr([(1.0, 3.0, c.FLOOD), (4.0, 8.0, c.FLOOD)])
    w = c.wetness(np.array([4.0 * FPS - 1e-6, 4.0 * FPS, 4.2 * FPS]), sp, FPS)
    assert 0.0 < w[0] and abs(w[1] - w[0]) < 1e-6 and w[2] > w[1]   # no jump: it wets again from where it was
    m = c.wetness([7.9 * FPS], fr([(1.0, 8.0, c.MIST)]), FPS)[0]
    assert abs(m - c.MIST_WET) < 0.01


def test_wet_keys_follow_the_curve():
    sp = fr([(1.0, 5.0, c.FLOOD), (6.0, 7.5, c.MIST)])
    keys = c.wet_keys(sp, FPS, 1.0, 400.0, dry=4.0)
    f = np.array([k[0] for k in keys])
    v = np.array([k[1] for k in keys])
    assert np.all(np.diff(f) > 0) and f[0] == 1.0 and f[-1] == 400.0
    T = np.arange(1.0, 400.0)
    err = np.abs(np.interp(T, f, v) - c.wetness(T, sp, FPS, dry=4.0)).max()
    assert err < 0.05
    assert len(keys) < 120


def test_no_coolant_no_wetness():
    assert c.wet_keys([], FPS) == [(1.0, 0.0)]
    assert c.wetness([10.0], [], FPS)[0] == 0.0
    assert c.describe([]) == "no coolant"


def test_cutting_spans_from_the_program():
    text = """G21 G90
S9000 M3
G0 X0 Y0 Z5
M8
G1 Z-2 F600
G1 X20 F1200
G0 Z5
G0 X40
G1 Z-2
G1 X60
M9
G0 Z20
M30
"""
    prog = gcode.read(text)
    sch = gcode.Schedule(prog, gcode.Timing())
    cut = c.cutting_spans(sch.pieces, top_z=0.0)
    assert len(cut) == 2                                     # two cuts; the rapid between is not cutting
    sp = c.spans(sch.m_times(), sch.program_end, sch.spindle_keys())
    assert len(sp) == 1 and sp[0][0] <= cut[0][0] + 1e-9 and sp[0][1] >= cut[-1][1] - 1e-9
    # above the stock: feed moves in the air do not cut
    assert c.cutting_spans(sch.pieces, top_z=-10.0) == []
    lvl = c.splash_level(np.array([cut[0][0] + 0.01, (cut[0][1] + cut[1][0]) / 2]),
                         [(a, b, k) for a, b, k in sp], cut)
    assert lvl[0] == 1.0 and lvl[1] == c.AIR_SPLASH


def test_the_liquid_depends_only_on_the_frame():
    sp = fr([(1.0, 9.0, c.FLOOD)])
    cut = [(1.0 * FPS, 9.0 * FPS)]
    noz = c.auto_nozzles(3, 0.04, 0.05, np.array([0.0, 0.0, 0.004]))
    args = (sp, cut, noz, np.array([0, 0, 0.004]), np.zeros(3), 0.005, 0.7, np.array([0, 0, -9.81]))
    a = c.liquid_at(100.0, FPS, *args)
    c.liquid_at(10.0, FPS, *args)
    c.liquid_at(180.0, FPS, *args)
    b = c.liquid_at(100.0, FPS, *args)
    assert np.array_equal(a.verts, b.verts) and np.array_equal(a.drops, b.drops) and len(a.drops) > 50
    assert len(a.faces) > 3 * 40                              # three jets
    nxt = c.liquid_at(101.0, FPS, *args)
    assert not np.array_equal(a.drops, nxt.drops)          # it moves from frame to frame
    # off: nothing; mist: drops, no stream; draft: streams only
    off = c.liquid_at(240.0, FPS, *args)
    assert len(off.verts) == 0 and len(off.drops) == 0
    mist = c.liquid_at(100.0, FPS, fr([(1.0, 9.0, c.MIST)]), *args[1:])
    assert len(mist.verts) == 0 and len(mist.drops) > 200
    draft = c.liquid_at(100.0, FPS, *args, draft=True)
    assert len(draft.verts) > 0 and len(draft.drops) == 0


def test_splash_stays_near_the_tool_and_above_the_part():
    g = np.array([0, 0, -9.81])
    f = c.splash(np.zeros(3), 0.005, 0.008, 123.0, FPS, lambda t: np.ones_like(t), 1.0, g)
    d = np.linalg.norm(f.drops[:, :2], axis=1)
    assert len(f.drops) > 100
    assert d.min() >= 0.004 and np.percentile(d, 95) < 0.12
    assert f.drops[:, 2].min() > -0.0006
    assert f.sizes.max() < 1 * MM


def test_more_splash_while_cutting():
    g = np.array([0, 0, -9.81])
    sp = [(0.0, 500.0, c.FLOOD)]
    lv_cut = c.splash(np.zeros(3), 0.005, 0.008, 200.0, FPS, lambda t: c.splash_level(t, sp, [(0.0, 500.0)]), 0.7, g)
    lv_air = c.splash(np.zeros(3), 0.005, 0.008, 200.0, FPS, lambda t: c.splash_level(t, sp, []), 0.7, g)
    assert len(lv_cut.drops) > 2 * len(lv_air.drops) > 0


def test_automatic_nozzles_aim_at_the_tool():
    aim = np.array([0.0, 0.0, -0.02])                       # a tool 20 mm longer
    noz = c.auto_nozzles(4, 0.04, 0.05, aim)
    assert len(noz) == 4
    for nz in noz:
        to_aim = aim - nz.o
        assert abs(np.linalg.norm(to_aim) - c.STANDOFF) < 1e-9
        assert np.dot(to_aim / np.linalg.norm(to_aim), nz.d) > 0.9999
        v, f = c.hose_mesh(nz)
        assert len(v) > 100 and max(max(x) for x in f) < len(v)
        # the hose starts at the ring and ends at the nozzle's tip
        assert np.linalg.norm(v - nz.mount, axis=1).min() < c.HOSE_R * 1.01
        assert np.linalg.norm(v - nz.o, axis=1).min() < c.HOSE_R


def test_hash_is_repeatable():
    a = c.hash01(np.arange(10), 3, 1)
    assert np.array_equal(a, c.hash01(np.arange(10), 3, 1))
    assert not np.array_equal(a, c.hash01(np.arange(10), 4, 1))
    assert (a >= 0).all() and (a < 1).all()
