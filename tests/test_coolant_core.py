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
    for rpm in (None, 1000, 6000, 15000):
        f = c.splash(np.zeros(3), 0.005, 0.008, 123.0, FPS, lambda t: np.ones_like(t), 1.0, g, rpm=rpm)
        d = np.linalg.norm(f.drops, axis=1)
        assert len(f.drops) > 100
        assert np.linalg.norm(f.drops[:, :2], axis=1).min() >= 0.004 and d.max() < c.FAR
        assert f.drops[:, 2].min() > -0.0006
        assert f.sizes.max() <= 0.7 * c.DROP_MAX


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


# ---------------------------------------------------------------------------
# task 0257: the spinning tool
# ---------------------------------------------------------------------------

G = np.array([0, 0, -9.81])


def _first_flight(rpm, radius=0.005, T=300.0, flow=1.0):
    """The drops thrown off the tool, and where each was a moment earlier and later (its velocity)."""
    on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    f = c.splash(np.zeros(3), radius, 0.008, T, FPS, on, flow, G, rpm=rpm)
    return f


def test_rim_speed_and_the_looks_it_gives():
    assert abs(c.rim_speed(10000, 0.005) - 5.236) < 1e-3          # D10 at 10,000 rpm
    assert abs(c.rim_speed(-3000, 0.025) - 7.854) < 1e-3          # D50 at 3,000 rpm, M4
    assert abs(c.rim_speed(1000, 0.005) - 0.524) < 1e-3
    assert [c.regime(v) for v in (0.5, 1.5, 5.0, 20.0)] == ["film", "streams", "spray", "mist"]


def test_drops_get_finer_the_faster_the_tool_turns():
    d = [float(c.drop_diameter(c.rim_speed(n, 0.005), 0.005)) for n in (1000, 3000, 6000, 15000, 60000)]
    assert d == sorted(d, reverse=True)
    assert d[0] == c.DROP_MAX and d[-1] == c.DROP_MIN                 # streams' beads … mist
    assert 0.45 * MM < d[2] < 0.65 * MM and 0.18 * MM < d[3] < 0.26 * MM
    # and the drawn drops follow it
    big = np.median(_first_flight(3000).sizes)
    fine = np.median(_first_flight(15000).sizes)
    assert fine < 0.6 * big and fine >= c.DRAWN_MIN               # (drawn at least a pixel wide in a close-up)


def test_fine_drops_are_slowed_by_the_air_sooner():
    assert c.drag_time(0.1 * MM, 20.0) < 0.01 < c.drag_time(0.5 * MM, 3.0)
    # a drop with no time to slow flies straight on; the air holds it back later
    p = c._fly(np.zeros((1, 3)), np.array([[5.0, 0.0, 0.0]]), np.array([0.001]), np.zeros(3), np.array([0.05]))
    assert abs(p[0, 0] - 0.005) < 1e-4
    p = c._fly(np.zeros((1, 3)), np.array([[5.0, 0.0, 0.0]]), np.array([1.0]), np.zeros(3), np.array([0.05]))
    assert abs(p[0, 0] - 0.25) < 1e-3                               # v0 * tau at most


def _speeds(rpm, radius=0.005):
    """How fast the thrown drops leave the tool: their speed between two moments very close together."""
    on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    out = []
    for T in (200.0, 260.0, 330.0):
        a = c.splash(np.zeros(3), radius, 0.008, T, FPS, on, 1.0, G, rpm=rpm, floor=-1.0)
        b = c.splash(np.zeros(3), radius, 0.008, T + 0.0025, FPS, on, 1.0, G, rpm=rpm, floor=-1.0)
        n = min(len(a.drops), len(b.drops))
        v = np.linalg.norm(b.drops[:n] - a.drops[:n], axis=1) / (0.0025 / FPS)
        just = np.linalg.norm(a.drops[:n, :2], axis=1) < radius + 6 * MM        # just thrown: not slowed yet
        out.append(v[(v < 100) & just])
    return np.concatenate(out)


def test_the_splash_leaves_at_the_rim_speed():
    for rpm, radius in ((6000, 0.005), (15000, 0.005), (3000, 0.025)):
        v = c.rim_speed(rpm, radius)
        sp = _speeds(rpm, radius)
        # just thrown drops fly at 0.85 … 1.15 x the rim speed; the air slows the others down
        assert 0.8 * v < np.percentile(sp, 95) < 1.2 * v, (rpm, radius, np.percentile(sp, 95), v)
    # a bigger tool at the same rpm throws faster
    assert np.percentile(_speeds(3000, 0.025), 95) > 3 * np.percentile(_speeds(3000, 0.005), 95)
    # capped where the picture stops reading
    assert np.percentile(_speeds(30000, 0.025), 99) < 1.05 * c.SPLASH_CAP


def test_the_splash_is_a_flat_band_where_the_jets_meet_the_tool():
    on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    for rpm in (6000, 15000):
        f = c.splash(np.zeros(3), 0.005, 0.015, 300.0, FPS, on, 1.0, G, rpm=rpm, band=0.006)
        near = np.linalg.norm(f.drops[:, :2], axis=1) < 0.02
        z = f.drops[near, 2]
        assert len(z) > 20
        assert 0.004 < np.median(z) < 0.008 and z.max() < 0.0095              # around 6 mm, not up the tool


def test_m3_and_m4_throw_the_other_way():
    for rpm, sign in ((6000, 1.0), (-6000, -1.0)):
        on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
        a = c.splash(np.zeros(3), 0.005, 0.008, 300.0, FPS, on, 1.0, G, rpm=rpm, floor=-1.0)
        b = c.splash(np.zeros(3), 0.005, 0.008, 300.0025, FPS, on, 1.0, G, rpm=rpm, floor=-1.0)
        n = min(len(a.drops), len(b.drops))
        v = b.drops[:n] - a.drops[:n]
        p = a.drops[:n]
        ok = np.linalg.norm(v, axis=1) < 0.01
        # turning about +Z: z component of p x v; M3 is clockwise seen from above (negative)
        lz = p[ok, 0] * v[ok, 1] - p[ok, 1] * v[ok, 0]
        assert np.mean(np.sign(lz) == -sign) > 0.9


def test_a_slow_tool_wears_a_film_and_sheds_streams():
    on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    assert c.film_share(0.4) == 1.0 and c.film_share(c.FILM_V) == 0.5 and c.film_share(2.0) == 0.0
    slow = c.splash(np.zeros(3), 0.005, 0.008, 300.0, FPS, on, 1.0, G, rpm=600)
    fast = c.splash(np.zeros(3), 0.005, 0.008, 300.0, FPS, on, 1.0, G, rpm=6000)
    r_slow = np.linalg.norm(slow.drops[:, :2], axis=1)
    r_fast = np.linalg.norm(fast.drops[:, :2], axis=1)
    on_tool = (r_slow < 0.0062)
    assert on_tool.sum() > 60 and (r_fast < 0.0062).sum() < 0.2 * len(r_fast)
    # the film covers the tool from the jets' height down to the tip, all round
    film = slow.drops[on_tool]
    assert film[:, 2].min() < 0.001 and film[:, 2].max() > 0.004
    ang = np.arctan2(film[:, 1], film[:, 0])
    assert np.histogram(ang, 6, (-np.pi, np.pi))[0].min() > 0
    # it turns with the tool: a film drop is at another angle a moment later, at the same radius
    later = c.splash(np.zeros(3), 0.005, 0.008, 300.0 + 0.1 * FPS, FPS, on, 1.0, G, rpm=600)
    assert not np.array_equal(slow.drops[on_tool][:5], later.drops[:5])
    # the shed drops leave from FLUTES points on the tool's rim (streams), not all round
    off = slow.drops[(r_slow > 0.0062) & (r_slow < 0.012)]
    ang = np.arctan2(off[:, 1], off[:, 0])
    hist = np.histogram(ang, 36, (-np.pi, np.pi))[0]
    assert (hist == 0).sum() >= 12                                 # gaps between the streams
    assert np.median(slow.sizes[~on_tool]) > 2 * np.median(fast.sizes)


def test_the_air_layer_deflects_the_jet_at_speed():
    assert c.deflect_share(c.rim_speed(9000, 0.005), 1.0) == 0.0           # 4.7 m/s: all of it reaches the tool
    a = c.deflect_share(c.rim_speed(15000, 0.005), 1.0)
    b = c.deflect_share(c.rim_speed(40000, 0.005), 1.0)
    assert 0.2 < a < 0.3 and 0.6 < b < 0.7
    assert c.deflect_share(c.rim_speed(15000, 0.005), 0.3) > a           # a weaker jet is deflected more
    assert c.deflect_share(1000.0, 1.0) == c.DEFLECT_MAX
    noz = c.auto_nozzles(2, 0.04, 0.05, np.array([0, 0, c.AIM_UP]))
    tgt = np.array([0, 0, c.AIM_UP])
    plain = c.jet(noz[0], tgt, 100.0, FPS, 1.0, G, deflect=0.0)
    bent = c.jet(noz[0], tgt, 100.0, FPS, 1.0, G, deflect=0.5, spin=1.0, tool_r=0.005, rim_v=12.0)
    back = c.jet(noz[0], tgt, 100.0, FPS, 1.0, G, deflect=0.5, spin=-1.0, tool_r=0.005, rim_v=12.0)
    shift = np.linalg.norm(bent.verts - plain.verts, axis=1)
    # the nozzle end stays, the end at the tool swings away a few mm, the other way for M4
    assert shift[:20].max() < 1e-9 and 1 * MM < shift.max() < 6 * MM
    assert np.linalg.norm(bent.verts - back.verts, axis=1).max() > 2 * MM
    # and the atomised share swirls round the tool as fine mist
    assert len(bent.drops) > len(plain.drops) + 60
    mist = bent.drops[len(plain.drops):]
    r = np.linalg.norm(mist[:, :2] - tgt[:2], axis=1)
    assert r.min() > 0.005 and r.max() < 0.03
    assert bent.sizes[len(plain.drops):].max() <= 1.2 * c.DRAWN_MIN + 1e-12


def test_less_splashes_when_the_air_layer_takes_part_of_the_jets():
    sp = fr([(0.0, 40.0, c.FLOOD)])
    cut = [(0.0, 1000.0)]
    noz = c.auto_nozzles(2, 0.04, 0.05, np.array([0, 0, c.AIM_UP]))
    on = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    n = {}
    for d in (0.0, 0.6):
        f = c.splash(np.zeros(3), 0.005, 0.008, 300.0, FPS, on, 1.0, G, rpm=30000, deflect=d, floor=-1.0)
        n[d] = len(f.drops)
    assert n[0.6] < 0.55 * n[0.0]
    whole = c.liquid_at(300.0, FPS, sp, cut, noz, np.array([0, 0, c.AIM_UP]), np.zeros(3), 0.005, 1.0, G, rpm=30000)
    assert len(whole.drops) > 0


def test_same_frame_same_drops_at_any_speed():
    sp = fr([(0.0, 40.0, c.FLOOD)])
    cut = [(0.0, 1000.0)]
    noz = c.auto_nozzles(2, 0.04, 0.05, np.array([0, 0, c.AIM_UP]))
    for rpm in (600, 6000, 20000, -6000):
        args = (sp, cut, noz, np.array([0, 0, c.AIM_UP]), np.zeros(3), 0.005, 0.8, G)
        a = c.liquid_at(222.0, FPS, *args, rpm=rpm)
        c.liquid_at(17.0, FPS, *args, rpm=rpm)
        b = c.liquid_at(222.0, FPS, *args, rpm=rpm)
        assert np.array_equal(a.drops, b.drops) and np.array_equal(a.verts, b.verts) and len(a.drops) > 50
        d = c.liquid_at(222.0, FPS, *args, rpm=rpm, draft=True)
        assert len(d.drops) == 0 and len(d.verts) > 0              # draft: the jets only, as before
