"""Independent tests for the coolant liquid solver (task 0255), written from the brief and the public API only."""
import math
import os

import numpy as np
import pytest

from fresing_render.core import liquid as L
from fresing_render.core import liquid_cache as C
from fresing_render.core import liquid_pool as LP

FPS = 24


def gap(sim):
    t = sim.totals()
    return t["poured"] - (t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"])


def run_checked(sim, n, pours=None, tool=None, push=None, tol=1e-9, f0=0):
    """Run n frames, check bookkeeping and non-negativity at every frame; returns the frames."""
    out = []
    for fr in sim.run(f0, f0 + n, pours, tool, push):
        assert abs(gap(sim)) < tol, (fr.frame, gap(sim))
        for c in range(len(sim.charts)):
            d = sim.depth(c)
            assert np.all(np.isfinite(d))
            assert d.min() >= 0.0
            bed = sim.charts[c].bed
            assert np.all(d[np.isnan(bed)] == 0.0)
        out.append(fr)
    return out


def flat(ny, nx, cell=0.004, **kw):
    return L.Chart("c", np.zeros((ny, nx)), cell, **kw)


def mk(charts, mats, **kw):
    return L.Liquid(charts, mats, FPS, -1.0, **kw)


# ---------------------------------------------------------------- bookkeeping -------------------------------------

def test_nan_hole_inside_chart_up_and_down():
    bed = np.zeros((20, 20))
    bed[8:12, 8:12] = np.nan
    for M in (L.still(30), np.array([L.rot_x(math.pi)] * 30)):
        sim = mk([L.Chart("a", bed, 0.005)], [M])
        sim.fill(0, np.full((20, 20), 0.003))
        run_checked(sim, 20, pours=lambda f: [L.Pour((0.05, 0.05), 2.0, chart=0)])
        assert sim.totals()["poured"] > 0.0


@pytest.mark.parametrize("shape", [(1, 1), (1, 7), (7, 1), (2, 2)])
def test_tiny_charts(shape):
    sim = mk([L.Chart("t", np.zeros(shape), 0.004)], [L.still(30)])
    sim.fill(0, np.full(shape, 0.002))
    run_checked(sim, 15, pours=lambda f: [L.Pour((0.002, 0.002), 3.0, chart=0)])


def test_closed_tray_keeps_liquid_one_cell_chart():
    sim = mk([L.Chart("t", np.zeros((1, 1)), 0.004, open_edges=False)], [L.still(30)])
    sim.fill(0, np.full((1, 1), 0.002))
    v0 = sim.volume(0)
    run_checked(sim, 20)
    assert sim.volume(0) == pytest.approx(v0, rel=1e-9)


def test_rotating_carrier_rot_z_per_frame():
    n = 40
    mats = np.array([L.rot_z(0.15 * f) for f in range(n)])
    sim = mk([flat(30, 30, 0.005, open_edges=True)], [mats])
    sim.fill(0, np.full((30, 30), 0.003))
    run_checked(sim, n - 2, pours=lambda f: [L.Pour((0.07, 0.07), 3.0, chart=0)])
    t = sim.totals()
    assert t["on_charts"] < t["poured"]       # a turning table flings liquid out


def test_stacked_charts_drops_fall_onto_lower():
    c_top = L.Chart("top", np.zeros((10, 10)), 0.004, x0=0.0, y0=0.0)
    c_low = L.Chart("low", np.zeros((40, 40)), 0.004, x0=-0.02, y0=-0.02, open_edges=False)
    mats = [L.translate(40, (0, 0, 0.1)), L.still(40)]
    sim = mk([c_top, c_low], mats)
    sim.fill(0, np.full((10, 10), 0.004))
    run_checked(sim, 36)
    t = sim.totals()
    assert sim.volume(1) > 0.0, t
    assert t["floor"] < 0.2 * t["poured"]


def test_pour_misses_everything():
    sim = mk([flat(10, 10)], [L.still(20)])
    run_checked(sim, 10, pours=lambda f: [L.Pour((5.0, 5.0, 1.0), 6.0)])
    t = sim.totals()
    assert t["poured"] == pytest.approx(6.0 / 60.0 * 10 / FPS, rel=1e-9)
    assert t["floor"] == pytest.approx(t["poured"], rel=1e-9)
    assert t["on_charts"] == 0.0


def test_world_jet_lands_on_chart():
    sim = mk([flat(20, 20, open_edges=False)], [L.still(30)])
    run_checked(sim, 10, pours=lambda f: [L.Pour((0.04, 0.04, 0.3), 6.0)])
    assert sim.totals()["on_charts"] > 0.9 * sim.totals()["poured"]
    sim = mk([flat(20, 20, open_edges=False)], [L.still(30)])
    run_checked(sim, 2, pours=lambda f: [L.Pour((0.04, 0.04, 0.3), 6.0)])
    d = sim.depth(0)
    yy, xx = np.mgrid[0:20, 0:20]
    e = np.maximum(d - L.FILM, 0.0)
    assert (e * yy).sum() / e.sum() == pytest.approx(10.0, abs=0.3)
    assert (e * xx).sum() / e.sum() == pytest.approx(10.0, abs=0.3)


def test_pour_on_nan_cell_goes_to_floor():
    bed = np.zeros((10, 10))
    bed[5, 5] = np.nan
    sim = mk([L.Chart("a", bed, 0.004)], [L.still(10)])
    run_checked(sim, 5, pours=lambda f: [L.Pour((5.5 * 0.004, 5.5 * 0.004), 6.0, chart=0)])
    assert sim.depth(0)[5, 5] == 0.0


def test_pour_outside_chart_area_goes_to_floor():
    sim = mk([flat(10, 10)], [L.still(10)])
    run_checked(sim, 5, pours=lambda f: [L.Pour((10.0, 10.0), 6.0, chart=0)])
    t = sim.totals()
    assert t["floor"] == pytest.approx(t["poured"], rel=1e-9)


def test_drain_on_edge_cells_and_corner():
    drain = np.zeros((12, 12))
    drain[0, 0] = 2e-5
    drain[0, 5] = 2e-5
    drain[11, 11] = 2e-5
    ch = L.Chart("d", np.zeros((12, 12)), 0.004, open_edges=False, drain=drain)
    sim = mk([ch], [L.still(400)])
    sim.fill(0, np.full((12, 12), 0.004))
    v0 = sim.volume(0)
    run_checked(sim, 300)
    t = sim.totals()
    assert t["drained"] > 0.9 * v0
    assert t["floor"] == 0.0


def test_drain_zero_area_does_nothing():
    ch = L.Chart("d", np.zeros((8, 8)), 0.004, open_edges=False, drain=np.zeros((8, 8)))
    sim = mk([ch], [L.still(60)])
    sim.fill(0, np.full((8, 8), 0.004))
    run_checked(sim, 50)
    assert sim.totals()["drained"] == 0.0


def test_set_bed_removes_surface_under_liquid():
    sim = mk([flat(20, 20, 0.004, open_edges=False)], [L.still(30)])
    sim.fill(0, np.full((20, 20), 0.003))
    run_checked(sim, 3)
    bed = np.zeros((20, 20))
    bed[5:10, 5:10] = np.nan
    spill = sim.set_bed(0, bed)
    assert spill == pytest.approx(25 * 0.003 * 0.004 ** 2 * 1e3, rel=0.2)
    assert abs(gap(sim)) < 1e-9
    assert np.all(sim.depth(0)[5:10, 5:10] == 0.0)
    run_checked(sim, 20, f0=3)


def test_set_bed_raise_bed_keeps_nothing_negative():
    sim = mk([flat(16, 16, 0.004)], [L.still(30)])
    sim.fill(0, np.full((16, 16), 0.002))
    bed = np.zeros((16, 16))
    bed[:, :8] = 0.01
    sim.set_bed(0, bed)
    assert abs(gap(sim)) < 1e-9
    run_checked(sim, 10)


def test_fill_on_nan_cells_is_ignored():
    bed = np.zeros((6, 6))
    bed[2, 2] = np.nan
    sim = mk([L.Chart("a", bed, 0.004)], [L.still(10)])
    sim.fill(0, np.full((6, 6), 0.002))
    assert sim.depth(0)[2, 2] == 0.0
    assert abs(gap(sim)) < 1e-12


def test_fill_negative_depth_clamped():
    sim = mk([flat(6, 6)], [L.still(10)])
    sim.fill(0, np.full((6, 6), -0.01))
    assert sim.depth(0).min() >= 0
    assert sim.totals()["poured"] == 0.0


def test_long_run_bookkeeping():
    n = 200
    mats = L.translate(n, (0, 0, 0)).copy()
    mats[:, 0, 3] = 0.02 * np.sin(np.arange(n) * 0.3)
    ch = L.Chart("t", np.zeros((24, 24)), 0.004, open_edges=False)
    sim = mk([ch], [mats])
    sim.fill(0, np.full((24, 24), 0.003))
    run_checked(sim, n - 2, tol=1e-9)


# ---------------------------------------------------------------- determinism -------------------------------------

def _scenario(helpers=0, hold=True, n=30):
    bed = np.zeros((70, 70))
    bed[20:40, 20:40] = -0.003
    mats = L.translate(n + 2, (0, 0, 0)).copy()
    mats[:, 0, 3] = 0.01 * np.sin(np.arange(n + 2) * 0.5)
    ch = L.Chart("a", bed, 0.004, open_edges=True)
    sim = mk([ch], [mats], helpers=helpers, hold=hold)
    sim.fill(0, np.full((70, 70), 0.0005))
    hist = []
    try:
        for fr in sim.run(0, n, pours=lambda f: [L.Pour((0.14, 0.14), 4.0, chart=0)]):
            hist.append((sim.depth(0).copy(), dict(fr.totals), fr.drops.copy()))
    finally:
        sim.close()
    return hist


def test_same_run_twice_bit_for_bit():
    a, b = _scenario(), _scenario()
    for (da, ta, pa), (db, tb, pb) in zip(a, b):
        assert np.array_equal(da, db) and ta == tb and np.array_equal(pa, pb)


def test_helpers_equal_no_helpers(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    a = _scenario(0)
    b = _scenario(2)
    for (da, ta, pa), (db, tb, pb) in zip(a, b):
        assert np.array_equal(da, db)
        assert ta == tb
        assert np.array_equal(pa, pb)


def test_hold_false_close_to_hold_true():
    a = _scenario(0, hold=True)
    b = _scenario(0, hold=False)
    da, db = a[-1][0], b[-1][0]
    assert np.abs(da - db).max() < 5e-4
    assert a[-1][1]["poured"] == b[-1][1]["poured"]


# ---------------------------------------------------------------- physics -----------------------------------------

def test_no_liquid_far_from_pour():
    sim = mk([flat(100, 100)], [L.still(40)])
    run_checked(sim, 10, pours=lambda f: [L.Pour((0.01, 0.01), 2.0, chart=0)])
    assert sim.depth(0)[60:, 60:].max() == 0.0


def test_runs_downhill_on_tilted_plate():
    bed = np.zeros((20, 40))
    sim = mk([L.Chart("p", bed, 0.004, open_edges=False)], [np.array([L.rot_y(0.2)] * 80)])
    sim.fill(0, np.where(np.arange(40)[None, :] < 20, 0.004, 0.0) * np.ones((20, 40)))
    run_checked(sim, 60)
    d = sim.depth(0)
    # rot_y(+0.2): world z of chart point (x,0,0) = -x sin(a): the +x side is low
    com = float((d.sum(0) * np.arange(40)).sum() / d.sum())
    assert com > 22


def test_closed_tray_holds_liquid_still_in_gravity():
    sim = mk([L.Chart("t", np.zeros((16, 16)), 0.004, open_edges=False)], [L.still(100)])
    sim.fill(0, np.full((16, 16), 0.003))
    run_checked(sim, 90)
    assert sim.volume(0) == pytest.approx(16 * 16 * 0.003 * 0.004 ** 2 * 1e3, rel=1e-9)
    assert sim.totals()["floor"] == 0.0


def test_open_flat_plate_loses_liquid_at_edges():
    sim = mk([flat(12, 12, 0.004)], [L.still(200)])
    sim.fill(0, np.full((12, 12), 0.004))
    run_checked(sim, 150)
    assert sim.totals()["on_charts"] < 0.3 * sim.totals()["poured"]


def test_push_moves_pool_expected_way():
    def com(sim):
        return float((sim.depth(0).sum(0) * np.arange(60)).sum() / sim.depth(0).sum())
    d = np.zeros((20, 60))
    d[:, 25:35] = 0.004
    sims = []
    for ax in (3.0, -3.0):
        s = mk([L.Chart("t", np.zeros((20, 60)), 0.004, open_edges=False)], [L.still(60)])
        s.fill(0, d)
        run_checked(s, 30, push=lambda f, ax=ax: {0: (ax, 0.0)})
        sims.append(com(s))
    assert sims[0] > 30 + 3
    assert sims[1] < 30 - 3


def test_push_array_form_and_wrong_shape():
    sim = mk([flat(8, 8, open_edges=False)], [L.still(10)])
    sim.fill(0, np.full((8, 8), 0.004))
    run_checked(sim, 3, push=lambda f: {0: (np.ones((8, 8)), np.zeros((8, 8)))})
    with pytest.raises(Exception):
        list(sim.run(0, 1, push=lambda f: {0: (np.ones((3, 3)), 0.0)}))


def test_velocity_matches_flux_over_depth():
    sim = mk([L.Chart("t", np.zeros((20, 40)), 0.004, open_edges=False)], [np.array([L.rot_y(0.1)] * 60)])
    d = np.zeros((20, 40))
    d[:, :10] = 0.006
    sim.fill(0, d)
    run_checked(sim, 8)
    vel = sim.velocity(0)
    assert vel.shape == (20, 40, 2)
    qx, qy = sim.flux(0)
    assert qx.shape == (20, 41) and qy.shape == (21, 40)
    dep = sim.depth(0)
    i = int(np.argmax(np.abs(qx[10, 1:40]))) + 1
    i = min(max(i, 1), 38)
    he = dep[10, i] - L.FILM
    assert he > 0
    expect = 0.5 * (qx[10, i] + qx[10, i + 1]) / (0.004 * he)
    assert vel[10, i, 0] == pytest.approx(expect, rel=1e-6, abs=1e-12)
    assert np.all(vel[dep <= L.FILM] == 0.0)


def test_velocity_dry_chart_zero():
    sim = mk([flat(5, 5)], [L.still(5)])
    assert np.all(sim.velocity(0) == 0)


def test_stress_push():
    a = L.stress_push(2.0, np.array([0.0, 0.001, 0.002]))
    assert a[0] == 0.0
    assert a[1] == pytest.approx(2.0 / (1000 * 0.001))
    assert a[2] == pytest.approx(1.0)


# ---------------------------------------------------------------- the tool ----------------------------------------

def _tool_sim(rpm, tip=(0.1, 0.1, 0.003), axis=(0, 0, 1), n=10, depth=0.004, radius=0.005):
    sim = mk([L.Chart("t", np.zeros((50, 50)), 0.004, open_edges=False)], [L.still(60)])
    sim.fill(0, np.full((50, 50), depth))
    fr = run_checked(sim, n, tool=lambda f: L.Tool(tip, axis, radius, 0.02, rpm))
    return sim, fr


def test_spinning_tool_throws_drops_with_exact_bookkeeping():
    sim, fr = _tool_sim(8000)
    assert fr[0].thrown > 0
    assert sum(f.thrown for f in fr) > 0


def test_tool_rpm_zero_nothing():
    sim, fr = _tool_sim(0)
    assert sum(f.thrown for f in fr) == 0
    assert all(len(f.drops) == 0 for f in fr)
    assert sim.volume(0) == pytest.approx(50 * 50 * 0.004 * 0.004 ** 2 * 1e3, rel=1e-9)


def test_tool_far_from_liquid_nothing():
    sim = mk([L.Chart("t", np.zeros((50, 50)), 0.004, open_edges=False)], [L.still(30)])
    d = np.zeros((50, 50))
    d[:10, :10] = 0.004
    sim.fill(0, d)
    fr = run_checked(sim, 8, tool=lambda f: L.Tool((0.17, 0.17, 0.003), (0, 0, 1), 0.005, 0.02, 10000))
    assert sum(f.thrown for f in fr) == 0


def test_tool_above_the_liquid_nothing():
    sim = mk([L.Chart("t", np.zeros((30, 30)), 0.004, open_edges=False)], [L.still(30)])
    sim.fill(0, np.full((30, 30), 0.002))
    fr = run_checked(sim, 6, tool=lambda f: L.Tool((0.06, 0.06, 0.05), (0, 0, 1), 0.005, 0.02, 10000))
    assert sum(f.thrown for f in fr) == 0


def _ang_mom(rpm):
    _, fr = _tool_sim(rpm, n=3)
    f0 = next(f for f in fr if len(f.drops))
    r = f0.drops[:, :2] - np.array([0.1, 0.1])
    return float(np.sum(r[:, 0] * f0.drop_v[:, 1] - r[:, 1] * f0.drop_v[:, 0]))


def test_tool_m3_vs_m4_drops_turn_opposite_ways():
    a, b = _ang_mom(8000), _ang_mom(-8000)
    assert a < 0 < b            # M3 = clockwise seen from the spindle (looking down): negative z angular momentum


def test_tool_drop_speed_about_surface_speed():
    _, fr = _tool_sim(8000, n=1)
    sp = np.linalg.norm(fr[0].drop_v[:, :2], axis=1)
    w = 8000 * 2 * math.pi / 60 * 0.005          # 4.19 m/s
    assert sp.max() < 1.6 * w
    assert np.median(sp) > 0.5 * w


def test_tool_speed_capped():
    _, fr = _tool_sim(60000, n=1)
    sp = np.linalg.norm(fr[0].drop_v, axis=1)
    assert sp.max() < L.TOOL_VMAX * 1.4


def test_tool_tilted_axis_and_chart_edge():
    sim = mk([L.Chart("t", np.zeros((30, 30)), 0.004, open_edges=True)], [L.still(30)])
    sim.fill(0, np.full((30, 30), 0.004))
    run_checked(sim, 8, tool=lambda f: L.Tool((0.002, 0.06, 0.003), (0.5, 0.2, 1.0), 0.005, 0.02, 9000))
    run_checked(sim, 4, tool=lambda f: L.Tool((-0.1, 0.06, 0.003), (0, 0, 1), 0.005, 0.02, 9000), f0=8)


def test_tool_axis_zero_vector_is_survived_or_refused():
    sim = mk([flat(10, 10, open_edges=False)], [L.still(10)])
    sim.fill(0, np.full((10, 10), 0.004))
    try:
        run_checked(sim, 2, tool=lambda f: L.Tool((0.02, 0.02, 0.0), (0, 0, 0), 0.005, 0.02, 9000))
    except ValueError:
        pass


def test_swirl_turns_pool_the_right_way():
    def spin(rpm):
        sim = mk([L.Chart("t", np.zeros((60, 60)), 0.004, open_edges=False)], [L.still(40)])
        sim.fill(0, np.full((60, 60), 0.0015))
        run_checked(sim, 25, tool=lambda f: L.Tool((0.12, 0.12, 0.0), (0, 0, 1), 0.005, 0.02, rpm))
        v = sim.velocity(0)
        yy, xx = np.mgrid[0:60, 0:60]
        rx, ry = (xx + 0.5) * 0.004 - 0.12, (yy + 0.5) * 0.004 - 0.12
        r = np.hypot(rx, ry)
        ring = (r > 0.012) & (r < 0.04)
        return float(np.sum((rx * v[..., 1] - ry * v[..., 0])[ring]))
    m3, m4 = spin(10000), spin(-10000)
    assert m3 < 0 < m4


# ---------------------------------------------------------------- bad input ---------------------------------------

def test_bad_inputs():
    with pytest.raises(ValueError):
        L.Chart("a", np.zeros(5), 0.004)
    with pytest.raises(ValueError):
        L.Chart("a", np.zeros((0, 4)), 0.004)
    with pytest.raises(ValueError):
        L.Chart("a", np.zeros((3, 3)), 0.0)
    with pytest.raises(ValueError):
        L.Chart("a", np.zeros((3, 3)), -1.0)
    with pytest.raises(ValueError):
        L.Chart("a", np.zeros((3, 3)), 0.004, drain=np.zeros((2, 2)))
    with pytest.raises(ValueError):
        mk([flat(3, 3)], [])


def test_nan_everywhere_chart():
    sim = mk([L.Chart("n", np.full((8, 8), np.nan), 0.004)], [L.still(10)])
    sim.fill(0, np.full((8, 8), 0.01))
    assert sim.totals()["poured"] == 0.0
    run_checked(sim, 5, pours=lambda f: [L.Pour((0.01, 0.01), 3.0, chart=0)])
    t = sim.totals()
    assert t["floor"] == pytest.approx(t["poured"], rel=1e-9)


@pytest.mark.parametrize("cell", [0.0013, 0.00377, 0.02])
def test_odd_cell_sizes_and_origin(cell):
    sim = mk([L.Chart("o", np.zeros((17, 23)), cell, x0=-0.37, y0=1.1, open_edges=False)],
             [L.translate(20, (0.3, -2.0, 0.5))])
    sim.fill(0, np.full((17, 23), 0.002))
    run_checked(sim, 10, pours=lambda f: [L.Pour((-0.3, 1.15), 1.0, chart=0)])


def test_wide_chart_not_multiple_of_tile():
    sim = mk([L.Chart("o", np.zeros((33, 97)), 0.004, open_edges=False)], [L.still(30)])
    d = np.zeros((33, 97))
    d[:, 31:34] = 0.005
    sim.fill(0, d)
    run_checked(sim, 25)


def test_fewer_mat_frames_than_run():
    sim = mk([flat(8, 8, open_edges=False)], [L.still(3)])
    sim.fill(0, np.full((8, 8), 0.003))
    run_checked(sim, 8)


def test_close_twice_and_state_readable():
    sim = mk([flat(8, 8, open_edges=False)], [L.still(10)])
    sim.fill(0, np.full((8, 8), 0.003))
    sim.close()
    sim.close()
    assert sim.depth(0).shape == (8, 8)


# ---------------------------------------------------------------- the cache ---------------------------------------

def test_encode_decode_round_trip():
    rng = np.random.default_rng(1)
    d = rng.random((13, 17)) * 0.01
    d[d < 0.003] = 0.0
    buf = C.encode_depth(d)
    out, pos = C.decode_depth(buf, d.shape)
    assert pos == len(buf)
    assert np.abs(out - d).max() <= 0.025e-3 + 1e-9
    assert np.all(out[d == 0] == 0)


def test_encode_overflow_and_extremes():
    d = np.array([[0.0, 0.0127, 0.01275, 0.0128, 0.5, 3.2]])
    out, _ = C.decode_depth(C.encode_depth(d), d.shape)
    assert np.abs(out[0, :5] - d[0, :5]).max() <= 0.025e-3 + 1e-6
    assert abs(out[0, 5] - 3.2) < 0.01
    big = np.array([[10.0]])
    o2, _ = C.decode_depth(C.encode_depth(big), big.shape)
    assert o2[0, 0] > 3.0       # saturates, but must not wrap to a small number


def test_encode_empty_and_tiny_values():
    d = np.zeros((5, 5))
    out, _ = C.decode_depth(C.encode_depth(d), d.shape)
    assert not out.any()
    d[2, 2] = 1e-6
    out, _ = C.decode_depth(C.encode_depth(d), d.shape)
    assert out[2, 2] == 0.0


def test_negative_depth_encodes_as_dry():
    out, _ = C.decode_depth(C.encode_depth(np.array([[-0.001]])), (1, 1))
    assert out[0, 0] == 0.0


def test_nan_depth_encodes_as_dry():
    d = np.array([[np.nan, 0.001]])
    out, _ = C.decode_depth(C.encode_depth(d), d.shape)
    assert out[0, 0] == 0.0
    assert out[0, 1] == pytest.approx(0.001, abs=0.03e-3)


def test_writer_reader_round_trip_out_of_order(tmp_path):
    p = str(tmp_path / "b.frlq")
    rng = np.random.default_rng(2)
    frames = {f: [rng.random((6, 7)) * 0.02, rng.random((3, 3)) * 0.001] for f in (5, 1, 9, 3)}
    with C.Writer(p, "fp-1", [("a", (6, 7)), ("b", (3, 3))], 24.0) as w:
        for f in (5, 1, 9, 3):
            n = f % 3
            w.add(f, frames[f], np.arange(3 * n).reshape(n, 3) * 0.1, np.arange(n) * 0.5,
                  {"poured": f, "floor": 2.0})
    with C.Reader.open(p, "fp-1") as r:
        assert r.frames == [1, 3, 5, 9]
        assert r.names == ["a", "b"]
        for f in (9, 1, 5):
            dep, P, V, t = r.read(f)
            for a, b in zip(dep, frames[f]):
                assert np.abs(a - b).max() <= 0.025e-3 + 1e-9
            assert P.shape == (f % 3, 3) and V.shape == (f % 3,)
            assert t["poured"] == f and t["floor"] == 2.0 and t["drained"] == 0.0


def test_writer_zero_drops_and_empty_frames(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "x", [("a", (4, 4))], 24.0) as w:
        w.add(0, [np.zeros((4, 4))])
        w.add(1, [np.zeros((4, 4))], np.zeros((0, 3)), np.zeros(0))
    with C.Reader.open(p, "x") as r:
        d, P, V, t = r.read(0)
        assert not d[0].any() and len(P) == 0 and len(V) == 0
        d, P, V, t = r.read(1)
        assert len(P) == 0


def test_reader_wrong_fingerprint_and_garbage(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "good", [("a", (4, 4))], 24.0) as w:
        w.add(0, [np.full((4, 4), 0.001)])
    assert C.Reader.open(p, "other") is None
    assert C.Reader.open(str(tmp_path / "nope")) is None
    raw = open(p, "rb").read()
    for cut in (0, 3, 8, 20, len(raw) // 2, len(raw) - 1, len(raw) - 5):
        q = str(tmp_path / f"t{cut}")
        open(q, "wb").write(raw[:cut])
        assert C.Reader.open(q, "good") is None, cut
    g = str(tmp_path / "g")
    open(g, "wb").write(os.urandom(500))
    assert C.Reader.open(g, "good") is None
    g2 = str(tmp_path / "g2")
    open(g2, "wb").write(b"FRLQ" + b"\x01\x00\x00\x00" + b"\xff\xff\xff\x7f" + b"x" * 100)
    assert C.Reader.open(g2, "good") is None


def test_reader_bad_index_offset(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "good", [("a", (4, 4))], 24.0) as w:
        w.add(0, [np.full((4, 4), 0.001)])
    raw = bytearray(open(p, "rb").read())
    raw[-16:-8] = (10 ** 12).to_bytes(8, "little")
    q = str(tmp_path / "x")
    open(q, "wb").write(bytes(raw))
    assert C.Reader.open(q, "good") is None


def test_reader_flipped_byte_never_returns_garbage_silently(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "good", [("a", (4, 4))], 24.0) as w:
        w.add(0, [np.full((4, 4), 0.001)])
    raw = bytearray(open(p, "rb").read())
    raw[len(raw) // 2] ^= 0xFF
    q = str(tmp_path / "flip")
    open(q, "wb").write(bytes(raw))
    r = C.Reader.open(q, "good")
    if r is not None:
        try:
            d = r.read(0)[0][0]
            assert np.isfinite(d).all()
        except Exception:
            pass
        r.close()


def test_writer_abort_leaves_no_file(tmp_path):
    p = str(tmp_path / "b.frlq")
    w = C.Writer(p, "x", [("a", (2, 2))], 24.0)
    w.add(0, [np.zeros((2, 2))])
    w.abort()
    assert not os.path.exists(p) and not os.path.exists(p + ".part")
    with pytest.raises(RuntimeError):
        with C.Writer(p, "x", [("a", (2, 2))], 24.0):
            raise RuntimeError("boom")
    assert not os.path.exists(p)


def test_writer_wrong_shapes_rejected(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "x", [("a", (2, 2))], 24.0) as w:
        with pytest.raises(ValueError):
            w.add(0, [np.zeros((3, 3))])
        with pytest.raises(ValueError):
            w.add(0, [np.zeros((2, 2)), np.zeros((2, 2))])
        with pytest.raises(ValueError):
            w.add(0, [np.zeros((2, 2))], np.zeros((2, 3)), np.zeros(5))


def test_reader_missing_frame_keyerror(tmp_path):
    p = str(tmp_path / "b.frlq")
    with C.Writer(p, "x", [("a", (2, 2))], 24.0) as w:
        w.add(0, [np.zeros((2, 2))])
    with C.Reader.open(p) as r:
        with pytest.raises(KeyError):
            r.read(7)


def test_cache_from_real_run(tmp_path):
    sim = mk([flat(20, 20, open_edges=False)], [L.still(20)])
    sim.fill(0, np.full((20, 20), 0.003))
    p = str(tmp_path / "r.frlq")
    with C.Writer(p, "run", [("c", (20, 20))], FPS) as w:
        for fr in sim.run(0, 10, pours=lambda f: [L.Pour((0.04, 0.04), 3.0, chart=0)]):
            w.add(fr.frame, [sim.depth(0)], fr.drops, fr.drop_vol, fr.totals)
    with C.Reader.open(p, "run") as r:
        d, P, V, t = r.read(10)
        assert np.abs(d[0] - sim.depth(0)).max() <= 0.025e-3 + 1e-9
        assert t["poured"] == pytest.approx(sim.totals()["poured"])


# ---------------------------------------------------------------- pool --------------------------------------------

def test_pool_helpers_with_drops_and_tool(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)

    def go(h):
        sim = mk([L.Chart("a", np.zeros((70, 70)), 0.004), L.Chart("b", np.zeros((40, 40)), 0.004, x0=0.05, y0=0.05)],
                 [L.translate(30, (0, 0, 0.05)), L.still(30)], helpers=h)
        sim.fill(0, np.full((70, 70), 0.003))
        out = []
        try:
            for fr in sim.run(0, 20, tool=lambda f: L.Tool((0.14, 0.14, 0.05), (0, 0, 1), 0.006, 0.02, 7000)):
                out.append((sim.depth(0).copy(), sim.depth(1).copy(), fr.drops.copy(), dict(fr.totals)))
        finally:
            sim.close()
        return out
    a, b = go(0), go(3)
    for x, y in zip(a, b):
        assert np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1])
        assert np.array_equal(x[2], y[2]) and x[3] == y[3]


def test_pool_close_idempotent_and_context(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    with mk([flat(60, 60)], [L.still(5)], helpers=2) as sim:
        sim.fill(0, np.full((60, 60), 0.002))
        sim.step(0)
    sim.close()
    assert sim.depth(0).shape == (60, 60)


# ---------------------------------------------------------------- fuzz, helpers dying, waking ----------------------

def test_fuzz_extreme_inputs_stay_finite_and_exact(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    rng = np.random.default_rng(11)
    for trial in range(8):
        ny, nx = (int(v) for v in rng.integers(3, 70, 2))
        bed = rng.random((ny, nx)) * 0.2 * rng.random()
        if rng.random() < .4:
            bed[rng.random((ny, nx)) < .1] = np.nan
        n = 14
        mats = np.array([L.rot_x(rng.normal() * 1.5) @ L.rot_y(rng.normal()) for _ in range(n)])
        mats[:, :3, 3] = rng.normal(size=(n, 3)) * rng.choice([0.0, 0.05, 1.0])
        sim = L.Liquid([L.Chart("a", bed, 0.001 + 0.01 * rng.random(), open_edges=bool(rng.random() < .5))], [mats],
                       FPS, -3.0, helpers=int(rng.integers(0, 3)))
        sim.fill(0, rng.random((ny, nx)) * rng.choice([0.001, 0.05, 0.3]))
        try:
            for fr in run_checked(sim, n - 2, pours=lambda f: [L.Pour((0.01, 0.01), 50.0, chart=0)],
                                  tool=lambda f: L.Tool((0.02, 0.02, 0.1), (0, 0, 1), 0.01, 0.05, 60000.0),
                                  push=lambda f: {0: (float(rng.normal() * 100), 0.0)}):
                assert np.isfinite(fr.drops).all() and np.isfinite(fr.drop_v).all()
                assert fr.drop_vol.sum() == pytest.approx(fr.totals["in_flight"], abs=1e-12)
        finally:
            sim.close()


def test_fuzz_helpers_bit_for_bit_two_charts_tool_push_drain(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 150)
    rng = np.random.default_rng(21)
    for trial in range(3):
        ny, nx = (int(v) for v in rng.integers(40, 110, 2))
        bed = rng.random((ny, nx)) * 0.02
        bed[rng.random((ny, nx)) < .05] = np.nan
        n = 14
        mats = np.array([L.rot_x(0.3 * math.sin(f * .5)) @ L.rot_z(0.1 * f) for f in range(n)])
        drain = np.zeros((ny, nx))
        drain[rng.random((ny, nx)) < .01] = 3e-5
        seed = int(rng.integers(1 << 30))
        res = []
        for h in (0, 3):
            r2 = np.random.default_rng(seed)
            sim = L.Liquid([L.Chart("a", bed, 0.003, open_edges=bool(seed % 2), drain=drain),
                            L.Chart("b", np.zeros((30, 30)), 0.004)], [mats, L.still(n)], FPS, -1.0, helpers=h)
            sim.fill(0, r2.random((ny, nx)) * 0.004)
            out = []
            try:
                for fr in sim.run(0, n - 2, pours=lambda f: [L.Pour((0.05, 0.05), 20.0, chart=0)],
                                  tool=lambda f: L.Tool((0.1, 0.1, 0.02), (0.1, 0, 1), 0.005, 0.03, 8000.0),
                                  push=lambda f: {0: (1.0, -0.5)}):
                    out.append((sim.depth(0).copy(), sim.depth(1).copy(), fr.drops.copy(), fr.drop_v.copy(),
                                dict(fr.totals), sim.velocity(0).copy()))
            finally:
                sim.close()
            res.append(out)
        for a, b in zip(*res):
            assert all(np.array_equal(x, y) for x, y in zip(a[:4], b[:4]))
            assert a[4] == b[4] and np.array_equal(a[5], b[5])


def test_killed_helper_raises_helper_error_quickly_and_frees_memory(monkeypatch):
    import time
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    before = set(os.listdir("/dev/shm")) if os.path.isdir("/dev/shm") else set()
    sim = mk([flat(80, 80)], [L.still(30)], helpers=2)
    sim.fill(0, np.full((80, 80), 0.003))
    sim.step(0)
    sim.pool.procs[0].kill()
    time.sleep(0.3)
    t0 = time.time()
    with pytest.raises(LP.HelperError):
        sim.step(1)
    assert time.time() - t0 < 10
    sim.close()
    if os.path.isdir("/dev/shm"):
        assert set(os.listdir("/dev/shm")) - before == set()


def test_bad_python_falls_back_to_no_helpers(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    sim = mk([flat(80, 80)], [L.still(30)], helpers=2, python="/nonexistent/python")
    sim.fill(0, np.full((80, 80), 0.003))
    run_checked(sim, 3)
    sim.close()


def test_after_helper_error_next_step_does_not_silently_continue(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 200)
    sim = mk([flat(80, 80)], [L.still(30)], helpers=2)
    sim.fill(0, np.full((80, 80), 0.003))
    sim.step(0)
    sim.pool.procs[0].kill()
    import time
    time.sleep(0.3)
    with pytest.raises(LP.HelperError):
        sim.step(1)
    try:
        with pytest.raises(Exception):
            sim.step(2)          # a broken solver should refuse (or redo frame 1), not go on with a mixed state
    finally:
        sim.close()


def test_settled_pool_wakes_on_tilt_pour_push_tool():
    n = 1000

    def scen(hold, what):
        mats = np.array([L.rot_y(0.3 if (what == "tilt" and f >= 880) else 0.0) for f in range(n)])
        sim = mk([L.Chart("a", np.zeros((40, 40)), 0.004, open_edges=False)], [mats], hold=hold)
        d = np.zeros((40, 40))
        d[10:20, 10:20] = 0.003
        sim.fill(0, d)
        for f in range(860):
            fr = sim.step(f)
        assert fr.settled or not hold
        for f in range(860, 960):
            sim.step(f, [L.Pour((0.08, 0.08), 6.0, chart=0)] if what == "pour" else None,
                     L.Tool((0.08, 0.08, 0.0), (0, 0, 1), 0.005, 0.02, 9000) if what == "tool" else None,
                     {0: (1.0, 0.0)} if what == "push" else None)
        return sim.depth(0).copy(), sim.totals()
    for what in ("tilt", "pour", "push", "tool"):
        a, ta = scen(True, what)
        b, tb = scen(False, what)
        assert np.abs(a - b).max() < 3e-4, what
        assert abs(ta["poured"] - ta["on_charts"] - ta["in_flight"] - ta["floor"]) < 1e-9


def test_cache_writer_add_after_close_is_an_error(tmp_path):
    w = C.Writer(str(tmp_path / "a"), "x", [("a", (2, 2))], 24.0)
    w.close()
    with pytest.raises(Exception):
        w.add(0, [np.zeros((2, 2))])


# --- the tester's minor findings, fixed by the author afterwards ---------------------------------------------------

def test_bad_inputs_are_refused_or_ignored_plainly(tmp_path):
    from fresing_render.core import liquid_cache as C
    with pytest.raises(ValueError):
        L.Liquid([flat(4, 4)], [L.still(3)], 0, floor_z=-1)
    sim = mk([flat(10, 10)], [L.still(5)])
    with pytest.raises(ValueError):
        sim.step(0, pours=[L.Pour((0.0, 0.0), 1.0, chart=-1)])
    sim = mk([flat(10, 10)], [L.still(5)])
    sim.step(0, pours=[L.Pour((0.0, 0.0, 1.0), 1.0, direction=(np.nan, 0, -1))],
             tool=L.Tool((np.nan, 0, 0), (0, 0, 1), 0.005, 0.02, 10000))
    t = sim.totals()
    assert t["floor"] == pytest.approx(t["poured"])
    w = C.Writer(str(tmp_path / "x.bin"), "x", [("p", (2, 2))], 24)
    w.close()
    with pytest.raises(ValueError):
        w.add(0, [np.zeros((2, 2))])
