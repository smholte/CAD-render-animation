"""The coolant liquid's solver (task 0255, ``fresing_render/core/liquid.py``): study 0251's six stand-alone tests with
their numbers, the same frame twice, the bookkeeping over a long run, the push, the velocities and the spinning tool."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

import liquid_scenes as S
from fresing_render.core import liquid as L

MM = 1e-3
FPS = 24


def _balance(sim):
    t = sim.totals()
    return abs(t["poured"] - t["on_charts"] - t["in_flight"] - t["drained"] - t["floor"])


# --- study 0251's six tests (numbers as on its page, section 4) --------------------------------------------------

def test_closed_pocket_fills_and_holds():
    res, frames, _ = S.t1_pocket()
    assert abs(res["error_pct"]) <= 2.0, res                     # 12.86 of 12.8 cm^3 on the page
    assert res["balance_l"] < 1e-12


def test_open_slot_drains_at_its_end():
    res = S.t2_slot()
    assert res["left_pct"] < 15.0, res                            # 8 % on the page (a 0.5 mm layer)
    assert res["half_s"] is not None and res["half_s"] < 1.0      # half gone in 0.33 s on the page
    assert res["balance_l"] < 1e-12


def test_tilted_plate_spills_at_the_right_angle():
    res = S.t3_tilt()
    assert res["spilled_at_deg"] is not None
    assert abs(res["error_deg"]) <= 1.5, res                      # 14.9 deg vs 14.0 on the page
    assert res["left_at_30deg_cm3"] == pytest.approx(res["expected_left_at_30deg_cm3"], rel=0.05)
    assert res["balance_l"] < 1e-12


def test_sloped_tray_empties_down_its_drain():
    res = S.t4_tray()
    assert res["empty_95pct_s_after_stop"] is not None and res["empty_95pct_s_after_stop"] <= 30.0, res
    assert res["drained_l"] > 0.9 * res["poured_l"]
    assert res["balance_l"] < 1e-12


def test_box_stopped_hard_sloshes_at_its_period():
    res = S.t5_slosh()
    assert abs(res["period_s"] - res["expected_period_s"]) < 0.1, res     # 1.25 s vs 2L/sqrt(gh) = 1.28 s
    assert res["after_5s_mm"] < res["first_wave_mm"]                       # it settles
    assert res["volume_change"] < 1e-12


def test_nothing_leaks_through_a_one_cell_wall():
    res = S.t6_wall()
    assert res["worst_behind_wall_cm3"] == 0.0, res
    assert res["volume_change"] < 1e-12


# --- the bake is the same every time -------------------------------------------------------------------------------

def _depths_of_slot_run():
    bed = np.zeros((40, 100))
    bed[15:25, 0:90] = -6 * MM
    ch = L.Chart("plate", bed, MM, -50 * MM, -20 * MM)
    sim = L.Liquid([ch], [L.still(4 * FPS + 2)], FPS, floor_z=-0.2)
    out = []
    for fr in sim.run(0, 4 * FPS, pours=lambda f: [L.Pour((30 * MM, 0.0, 0.03), 0.16)] if f < FPS else []):
        out.append((sim.depth(0).copy(), fr.drops.copy(), fr.drop_vol.copy(), fr.totals))
    return out


def test_same_frame_same_liquid():
    a = _depths_of_slot_run()
    b = _depths_of_slot_run()
    assert len(a) == len(b)
    for (da, pa, va, ta), (db, pb, vb, tb) in zip(a, b):
        assert np.array_equal(da, db) and np.array_equal(pa, pb) and np.array_equal(va, vb) and ta == tb


# --- bookkeeping over a long run with everything at once -----------------------------------------------------------

def _busy_scene(frames, helpers=0):
    """A table that moves (X back and forth, hard stops), a block with a pocket on it, a tray with a drain under
    it, a pour moving over the table, a spinning tool in the pocket for a while, a push on the table."""
    cell = 2 * MM
    X, Y = np.meshgrid(np.arange(100) * cell - 0.1, np.arange(60) * cell - 0.06)
    bed = np.zeros(X.shape)
    bed[(np.abs(X) < 0.04) & (np.abs(Y) < 0.03)] = 20 * MM
    bed[(np.abs(X) < 0.02) & (np.abs(Y) < 0.015)] = 10 * MM
    bed[np.abs(Y - 0.045) < 6 * MM] = -8 * MM                        # a groove open at both ends
    table = L.Chart("table", bed, cell, -0.1, -0.06)
    TX, TY = np.meshgrid(np.arange(160) * cell - 0.16, np.arange(80) * cell - 0.08)
    tbed = (TX + 0.16) * math.tan(math.radians(2)) + 0.3 * np.abs(TY) * math.tan(math.radians(2))
    drain = np.zeros(tbed.shape)
    hole = (TX + 0.15) ** 2 + TY ** 2 < 0.01 ** 2
    drain[hole] = math.pi * 0.01 ** 2 / hole.sum()
    tray = L.Chart("tray", tbed, cell, -0.16, -0.08, open_edges=False, drain=drain)
    t = np.arange(frames + 2) / FPS
    m = L.still(frames + 2)
    m[:, 0, 3] = 0.03 * np.sign(np.sin(t * 2 * math.pi / 3.0)) * np.minimum(1, np.abs(np.sin(t * 2 * math.pi / 3.0)) * 4)
    m[:, 2, 3] = 0.15
    pours = lambda f: [L.Pour((0.06 * math.sin(f / 30), 0.0, 0.4), 2.0)] if (f // 48) % 3 != 2 else []
    tool = lambda f: L.Tool((m[f, 0, 3], 0.0, 0.15 + 10.5 * MM), (0, 0, 1), 4 * MM, 15 * MM,
                            8000 if (f // 40) % 2 == 0 else -6000)
    push = lambda f: {0: (0.2, 0.0)} if (f // 60) % 2 == 1 else None
    sim = L.Liquid([table, tray], [m, L.still(frames + 2)], FPS, floor_z=-0.2, helpers=helpers)
    return sim, pours, tool, push


def test_bookkeeping_is_exact_over_a_long_run():
    frames = 1200
    sim, pours, tool, push = _busy_scene(frames)
    worst = 0.0
    thrown = 0.0
    for fr in sim.run(0, frames, pours=pours, tool=tool, push=push):
        t = fr.totals
        worst = max(worst, abs(t["poured"] - t["on_charts"] - t["in_flight"] - t["drained"] - t["floor"]))
        thrown += fr.thrown
    t = sim.totals()
    assert t["poured"] > 1.0 and t["drained"] > 0.1 and thrown > 0.0       # it all happened
    assert worst < 1e-9, worst                                              # litres


# --- the push (air blast later) and the velocities (chips later) ---------------------------------------------------

def test_a_constant_push_tilts_a_pool_the_expected_way():
    """A box 200 mm long, 5 mm of liquid, pushed with 0.1 m/s^2 along +x: at rest its top leans by a / g, so the far
    end is L a / g = 2.04 mm deeper than the near end."""
    cell = 2 * MM
    ch = L.Chart("box", np.zeros((10, 100)), cell, 0.0, 0.0, open_edges=False)
    sim = L.Liquid([ch], [L.still(20 * FPS + 2)], FPS, floor_z=-1)
    sim.fill(0, np.full((10, 100), 5 * MM))
    v0 = sim.volume(0)
    for fr in sim.run(0, 20 * FPS, push=lambda f: {0: (0.1, 0.0)}):
        pass
    d = sim.depth(0)
    lean = float(d[:, -1].mean() - d[:, 0].mean())
    expect = (99 * cell) * 0.1 / L.G
    assert lean == pytest.approx(expect, rel=0.1)
    assert abs(sim.volume(0) - v0) < 1e-12
    # the other way round
    sim2 = L.Liquid([ch], [L.still(20 * FPS + 2)], FPS, floor_z=-1)
    sim2.fill(0, np.full((10, 100), 5 * MM))
    for fr in sim2.run(0, 20 * FPS, push=lambda f: {0: (-0.1, np.zeros((10, 100)))}):
        pass
    d2 = sim2.depth(0)
    assert float(d2[:, 0].mean() - d2[:, -1].mean()) == pytest.approx(expect, rel=0.1)


def test_a_push_as_a_surface_stress():
    a = L.stress_push(np.array([2.0, 2.0, 2.0]), np.array([0.0, 1 * MM, 2 * MM]))
    assert a[0] == 0.0 and a[1] == pytest.approx(2.0) and a[2] == pytest.approx(1.0)


def test_velocities_are_flux_over_depth():
    cell = 2 * MM
    bed = np.zeros((20, 80))
    ch = L.Chart("box", bed, cell, 0.0, 0.0, open_edges=False)
    t = np.arange(2 * FPS + 2) / FPS
    m = L.still(len(t))
    m[:, 0, 3] = np.minimum(t, 0.3) * 0.3                    # stops hard at 0.3 s: the liquid runs on
    sim = L.Liquid([ch], [m], FPS, floor_z=-1)
    sim.fill(0, np.full(bed.shape, 6 * MM))
    for fr in sim.run(0, 9):
        pass
    vel = sim.velocity(0)
    qx, qy = sim.flux(0)
    d = sim.depth(0)
    he = np.maximum(d - L.FILM, 0.0)
    u = 0.5 * (qx[:, :-1] + qx[:, 1:]) / (cell * he)
    v = 0.5 * (qy[:-1, :] + qy[1:, :]) / (cell * he)
    assert np.allclose(vel[..., 0], u, rtol=1e-12, atol=1e-15)
    assert np.allclose(vel[..., 1], v, rtol=1e-12, atol=1e-15)
    assert float(vel[..., 0].mean()) > 0.01                  # the liquid runs on in +x after the stop


# --- the spinning tool ------------------------------------------------------------------------------------------------

def _tool_pool(rpm, frames=2 * FPS):
    bed = np.zeros((100, 100))
    ch = L.Chart("tray", bed, MM, -50 * MM, -50 * MM, open_edges=False)
    sim = L.Liquid([ch], [L.still(frames + 2)], FPS, floor_z=-0.5)
    sim.fill(0, np.full(bed.shape, 2 * MM))
    tool = L.Tool(tip=(0.0, 0.0, 0.5 * MM), axis=(0, 0, 1), radius=5 * MM, flute=20 * MM, rpm=rpm)
    thrown = 0.0
    worst = 0.0
    for fr in sim.run(0, frames, tool=lambda f: tool):
        thrown += fr.thrown
        worst = max(worst, _balance(sim))
    vel = sim.velocity(0)
    X, Y = np.meshgrid(np.arange(100) * MM - 50 * MM, np.arange(100) * MM - 50 * MM)
    r = np.hypot(X, Y)
    ring = (r > 5 * MM) & (r < 15 * MM)
    Lz = float(((X * vel[..., 1] - Y * vel[..., 0]) * sim.depth(0))[ring].sum())
    return sim, thrown, worst, Lz


def test_a_spinning_tool_throws_the_liquid_off_as_drops():
    sim, thrown, worst, _ = _tool_pool(10000)
    t = sim.totals()
    assert thrown > 0.5e-3                                    # litres thrown in 2 s
    assert t["floor"] + t["in_flight"] > 0.0
    assert t["on_charts"] < t["poured"]
    assert worst < 1e-12                                      # the bookkeeping is still exact


def test_thrown_drops_leave_in_the_turning_direction_at_the_tools_speed():
    bed = np.zeros((100, 100))
    ch = L.Chart("tray", bed, MM, -50 * MM, -50 * MM, open_edges=False)
    for rpm, sense in ((10000, 1.0), (-10000, -1.0)):
        sim = L.Liquid([ch], [L.still(4)], FPS, floor_z=-0.5)
        sim.fill(0, np.full(bed.shape, 2 * MM))
        tool = L.Tool((0.0, 0.0, 0.5 * MM), (0, 0, 1), 5 * MM, 20 * MM, rpm)
        sim._tool(tool, 0, 1 / FPS)                          # noqa: SLF001 – the drops as thrown, before flying
        P, V = sim.P, sim.V
        assert len(P) > 50
        rh = P[:, :2] / np.linalg.norm(P[:, :2], axis=1)[:, None]
        cw = np.stack([rh[:, 1], -rh[:, 0]], 1)               # clockwise seen from above = M3
        vt = np.sum(V[:, :2] * cw, 1) * sense
        wr = 10000 * 2 * math.pi / 60 * 5 * MM                 # 5.24 m/s
        assert np.allclose(vt, wr, rtol=0.01)
        assert np.all(np.sum(V[:, :2] * rh, 1) > 0)           # and a little outwards
        assert np.all(V[:, 2] > 0)                            # and up the flutes
        assert np.all(np.linalg.norm(P[:, :2], axis=1) >= 5 * MM)   # from the tool's surface


def test_the_thrown_speed_is_capped():
    t = L.Tool((0, 0, 0), (0, 0, 1), 25 * MM, 30 * MM, 12000)   # a D50 at 12,000 rpm: 31 m/s at its rim
    assert t.surface_speed() == L.TOOL_VMAX


def test_a_spinning_tool_turns_the_pool_its_way():
    _, _, _, lz3 = _tool_pool(10000)
    _, _, _, lz4 = _tool_pool(-10000)
    sim0, thrown0, _, lz0 = _tool_pool(0, frames=12)
    assert lz3 < 0 < lz4                                     # M3 clockwise seen from above, M4 the other way
    assert lz3 == pytest.approx(-lz4, rel=1e-6)
    assert thrown0 == 0.0 and lz0 == 0.0                     # a standing spindle does nothing


# --- holding still liquid, the cut going deeper, pours on a chart ------------------------------------------------------

def test_still_liquid_is_held_and_costs_nothing():
    """A 500 x 500 grid (250,000 cells) of liquid at rest: after a frame or two nothing is stepped; such a frame
    costs <= 1 ms (median)."""
    ch = L.Chart("tray", np.zeros((500, 500)), 2 * MM, 0, 0, open_edges=False)
    sim = L.Liquid([ch], [L.still(64)], FPS, floor_z=-1)
    sim.fill(0, np.full((500, 500), 3 * MM))
    times = []
    settled = []
    for f in range(60):
        t0 = time.perf_counter()
        fr = sim.step(f)
        times.append(time.perf_counter() - t0)
        settled.append(fr.settled)
    assert all(settled[5:])
    assert float(np.median(times[5:])) <= 1e-3, np.median(times[5:])
    assert abs(_balance(sim)) < 1e-12


def test_held_liquid_wakes_when_the_carrier_moves():
    ch = L.Chart("box", np.zeros((20, 100)), 2 * MM, 0, 0, open_edges=False)
    n = 3 * FPS
    m = L.still(n + 2)
    m[2 * FPS + 1:, 0, 3] = np.arange(n + 2 - 2 * FPS - 1) / FPS * 0.2     # starts moving at 2 s
    sim = L.Liquid([ch], [m], FPS, floor_z=-1)
    sim.fill(0, np.full((20, 100), 5 * MM))
    fr = list(sim.run(0, n))
    assert fr[FPS].settled                                   # at rest before
    assert not all(x.settled for x in fr[2 * FPS:2 * FPS + 3])   # the start wakes it
    d = sim.depth(0)
    assert d[:, 0].mean() > d[:, -1].mean()                  # it was thrown backwards


def test_holding_changes_little():
    a, _, da = S.t1_pocket(hold=True)
    b, _, db = S.t1_pocket(hold=False)
    assert abs(a["held_cm3"] - b["held_cm3"]) < 0.05
    assert float(np.abs(da - db).max()) < 0.2 * MM


def test_the_cut_going_deeper_keeps_the_liquid_and_counts_what_falls():
    bed = np.zeros((40, 40))
    ch = L.Chart("part", bed, MM, 0, 0)
    sim = L.Liquid([ch], [L.still(30)], FPS, floor_z=-1)
    fill = np.zeros_like(bed)
    fill[10:30, 10:30] = 1 * MM
    sim.fill(0, fill)
    sim.step(0)
    new = bed.copy()
    new[15:25, 15:25] = np.nan                                # a hole cut through
    spilled = sim.set_bed(0, new)
    assert spilled > 0
    for f in range(1, 20):
        sim.step(f)
    assert _balance(sim) < 1e-12
    assert np.all(sim.depth(0)[15:25, 15:25] == 0.0)


def test_a_pour_on_a_chart_and_one_that_misses():
    ch = L.Chart("p", np.zeros((20, 20)), MM, 0, 0, open_edges=False)
    sim = L.Liquid([ch], [L.still(10)], FPS, floor_z=-1)
    sim.step(0, pours=[L.Pour((10 * MM, 10 * MM), 1.2, chart=0), L.Pour((5.0, 5.0, 1.0), 0.6)])
    t = sim.totals()
    assert t["poured"] == pytest.approx(1.8 / 60 / FPS)
    assert t["floor"] == pytest.approx(0.6 / 60 / FPS)
    assert sim.volume(0) == pytest.approx(1.2 / 60 / FPS)


def test_bad_charts_are_refused():
    with pytest.raises(ValueError):
        L.Chart("x", np.zeros(5), MM)
    with pytest.raises(ValueError):
        L.Chart("x", np.zeros((3, 3)), 0.0)
    with pytest.raises(ValueError):
        L.Chart("x", np.zeros((3, 3)), MM, drain=np.zeros((2, 2)))
    with pytest.raises(ValueError):
        L.Liquid([L.Chart("x", np.zeros((3, 3)), MM)], [], FPS, floor_z=0)
