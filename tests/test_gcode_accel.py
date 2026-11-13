"""Task 0103: G-code moves timed with acceleration (core/gcode.py, no Blender)."""

from __future__ import annotations

import math
import time

import pytest

from fresing_render.core import gcode as G

FAST = (60000.0, 60000.0, 60000.0)            # rapid speeds high enough not to limit the feeds
A = (1000.0, 1000.0, 1000.0)                  # mm/s²


def moving(prog):
    return [m for m in prog.moves if m.moving]


def test_a_single_long_move_takes_d_over_v_plus_v_over_a():
    prog = G.read("G21 G90\nG1 X200 F6000\n", rapid=FAST, accel=A)         # 100 mm/s, 200 mm
    (m,) = moving(prog)
    assert m.dur == pytest.approx(200 / 100 + 100 / 1000, abs=1e-3)
    assert m.dur0 == pytest.approx(2.0)
    assert prog.accel and prog.duration_without_accel == pytest.approx(2.0)


def test_a_short_move_never_reaches_its_feed():
    prog = G.read("G1 X1 F6000\n", rapid=FAST, accel=A)
    (m,) = moving(prog)
    assert m.dur == pytest.approx(2 * math.sqrt(1 / 1000), abs=1e-6)
    assert m.prof[1] < 100.0                                               # top speed below the feed


def test_rapids_speed_up_with_the_slowest_axis():
    # G0 along X and Y: X has the lower acceleration and the slower rapid: it sets the profile
    prog = G.read("G0 X100 Y100\n", rapid=(6000.0, 12000.0, 6000.0), accel=(500.0, 2000.0, 1000.0))
    (m,) = moving(prog)
    d = math.hypot(100, 100)
    v = 100.0 * math.sqrt(2)                       # X at 100 mm/s, Y as much, along the diagonal
    a = 500.0 * math.sqrt(2)
    assert m.dur == pytest.approx(d / v + v / a, abs=1e-6)


def test_without_acceleration_nothing_changes():
    text = "G1 X10 F600\nG1 Y10\nG2 X20 Y0 I5 J-5\nG4 P0.5\nG0 Z5\n"
    old = G.read(text, rapid=FAST)
    assert not old.accel and old.duration_without_accel == old.duration
    assert all(m.prof == () and m.dur0 == -1.0 for m in old.moves)
    new = G.read(text, rapid=FAST, accel=A)
    assert new.duration > old.duration
    assert new.duration_without_accel == pytest.approx(old.duration)
    for a, b in zip(old.moves, new.moves):
        assert b.dur >= a.dur - 1e-12
        if b.dur0 >= 0:
            assert b.dur0 == pytest.approx(a.dur)
    # the start times add up
    t = 0.0
    for m in new.moves:
        assert m.t0 == pytest.approx(t)
        t += m.dur


ZIGZAG = "".join((f"X{k // 2 + 1}\n" if k % 2 == 0 else f"Y{(k // 2 + 1) % 2}\n") for k in range(200))


def test_g61_stops_at_every_corner_g64_blends():
    plain = G.read("G1 F3000\n" + ZIGZAG, rapid=FAST).duration
    g61 = G.read("G61\nG1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    g64 = G.read("G64\nG1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    default = G.read("G1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    assert plain < g64 < g61
    assert default == pytest.approx(g64)                                   # G64 is the default
    # G61: every 1 mm move from standstill to standstill
    assert g61 == pytest.approx(200 * 2 * math.sqrt(1 / 1000), rel=1e-6)


def test_g64_p_tolerance_slows_the_corners():
    loose = G.read("G64\nG1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    tight = G.read("G64 P0.001\nG1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    exact = G.read("G61\nG1 F3000\n" + ZIGZAG, rapid=FAST, accel=A).duration
    assert loose < tight < exact
    prog = G.read("G64 P0.01\nG1 X1\n", rapid=FAST, accel=A)
    assert moving(prog)[0].blend == pytest.approx(0.01)
    prog = G.read("G20\nG64 P0.001\nG1 X1\n", rapid=FAST, accel=A)       # inch: the tolerance in mm
    assert moving(prog)[0].blend == pytest.approx(0.0254)
    prog = G.read("G61.1\nG1 X1\nG64\nG1 X2\n", rapid=FAST, accel=A)
    assert [m.blend for m in moving(prog)] == [-1.0, 0.0]


def test_a_line_cut_into_1000_pieces_runs_as_one_move():
    one = G.read("G1 X200 F6000\n", rapid=FAST, accel=A).duration
    text = "G1 F6000\n" + "".join(f"X{(k + 1) * 0.2:.3f}\n" for k in range(1000))
    many = G.read(text, rapid=FAST, accel=A).duration
    assert many == pytest.approx(one, rel=0.01)


def test_a_dwell_a_tool_change_and_a_reversal_stop_the_machine():
    two = G.read("G1 X100 F6000\nX200\n", rapid=FAST, accel=A).duration
    dwell = G.read("G1 X100 F6000\nG4 P0.5\nX200\n", rapid=FAST, accel=A).duration
    tool = G.read("G1 X100 F6000\nT2 M6\nX200\n", rapid=FAST, accel=A).duration
    back = G.read("G1 X100 F6000\nX0\n", rapid=FAST, accel=A).duration
    assert two == pytest.approx(2.1)
    assert dwell == pytest.approx(2.7) and tool == pytest.approx(2.2) and back == pytest.approx(2.2)


def test_an_arc_faster_than_root_a_r_is_slowed_to_it():
    r = 4.0                                         # √(1000 · 4) = 63.2 mm/s < 100 mm/s (F6000)
    prog = G.read(f"G1 X{r} F6000\nG3 X{r} Y0 I-{r} J0\n", rapid=FAST, accel=A)
    arc = [m for m in prog.moves if m.kind == "ARC"][0]
    assert arc.prof[1] == pytest.approx(math.sqrt(1000 * r))
    assert arc.dur > 2 * math.pi * r / math.sqrt(1000 * r)
    big = G.read("G1 X100 F6000\nG3 X100 Y0 I-100 J0\n", rapid=FAST, accel=A)   # √(1000 · 100) = 316 > 100
    arc = [m for m in big.moves if m.kind == "ARC"][0]
    assert arc.prof[1] == pytest.approx(100.0)
    # a line going on along the arc's tangent does not stop: tangent to the circle at its start
    on = G.read("G1 X100 F6000\nG3 X200 Y100 I0 J100\n", rapid=FAST, accel=A)
    j = [m for m in on.moves if m.moving]
    assert j[0].prof[2] == pytest.approx(100.0) and j[1].prof[0] == pytest.approx(100.0)


def test_rotary_axes_use_their_own_acceleration():
    prog = G.read("G0 A90\n", rapid=FAST, rot_rapid=(3600.0, 3600.0, 3600.0), accel=A,
                  rot_accel=(600.0, 600.0, 600.0))
    (m,) = moving(prog)
    assert m.dur == pytest.approx(90 / 60 + 60 / 600, abs=1e-6)


def test_the_place_follows_the_speed_profile():
    prog = G.read("G1 X200 F6000\n", rapid=FAST, accel=A)
    sch = G.Schedule(prog, G.Timing())
    for t in [0.0, 0.01, 0.05, 0.1, 0.5, 1.0, 1.5, 2.0, 2.05, 2.1]:
        if t <= 0.1:
            s = 0.5 * 1000 * t * t
        elif t <= 2.0:
            s = 5.0 + 100 * (t - 0.1)
        else:
            dt = t - 2.0
            s = 195.0 + 100 * dt - 0.5 * 1000 * dt * dt
        assert sch.point_at(t)[0] == pytest.approx(s, abs=1e-6)
    # u_of and tau_of are each other's inverse
    m = moving(prog)[0]
    for u in (0.0, 0.01, 0.025, 0.3, 0.97, 0.99, 1.0):
        assert m.u_of(m.tau_of(u)) == pytest.approx(u, abs=1e-12)
    # keys where speeding up ends and slowing down starts
    times = [t for t, _p in sch.samples(25.0)]
    assert any(abs(t - 0.1) < 1e-9 for t in times) and any(abs(t - 2.0) < 1e-9 for t in times)
    # the scaled video keeps the profile's shape
    fit = G.Schedule(prog, G.Timing(speed="FIT", fit_seconds=4.2))
    assert fit.point_at(0.2)[0] == pytest.approx(5.0, abs=1e-6)
    # the drawn path carries the profile's times
    pts = sch.path(max_step=0.05)[0][1]
    for x, _y, _z, t in pts:
        assert sch.point_at(t)[0] == pytest.approx(x, abs=1e-6)


def test_arc_and_rotary_places_follow_the_profile():
    prog = G.read("G1 X4 F6000\nG3 X4 Y0 I-4 J0 A90\n", rapid=FAST, accel=A, rot_accel=(600.0,) * 3)
    sch = G.Schedule(prog, G.Timing())
    arc = [p for p in sch.pieces if p.move.kind == "ARC"][0]
    m = arc.move
    for tau in (0.05, 0.3, 0.5, 0.9):
        t = arc.v0 + tau * arc.vd
        u = m.u_of(tau)
        assert sch.point_at(t) == pytest.approx(m.at(u), abs=1e-9)
        assert sch.rot_at(t)[0] == pytest.approx(90 * u, abs=1e-9)


def read_ini_text(text):
    return G.read_ini(text)


def test_read_linuxcnc_ini_axes():
    ini = """
[TRAJ]
COORDINATES = X Y Z A
LINEAR_UNITS = mm
[AXIS_X]
MAX_VELOCITY = 100   # mm/s
MAX_ACCELERATION = 1500
[AXIS_Y]
MAX_VELOCITY = 80
MAX_ACCELERATION = 1200
[AXIS_Z]
MAX_VELOCITY = #<_ini>z
MAX_ACCELERATION = 800
[AXIS_A]
MAX_VELOCITY = 90
MAX_ACCELERATION = 720
[JOINT_0]
MAX_VELOCITY = 1
"""
    res = G.read_ini(ini)
    assert res["x"] == {"velocity": 6000.0, "accel": 1500.0}
    assert res["y"] == {"velocity": 4800.0, "accel": 1200.0}
    assert res["z"] == {"accel": 800.0}                                     # a reference is left out
    assert res["a"] == {"velocity": 5400.0, "accel": 720.0}


def test_read_linuxcnc_ini_joints_inch_and_old_axes():
    ini = """[TRAJ]
COORDINATES = XYZ
LINEAR_UNITS = inch
[JOINT_0]
MAX_VELOCITY = 2
MAX_ACCELERATION = 20
[JOINT_2]
MAX_ACCELERATION = 10
"""
    res = G.read_ini(ini)
    assert res["x"]["velocity"] == pytest.approx(2 * 25.4 * 60) and res["x"]["accel"] == pytest.approx(508.0)
    assert res["z"] == {"accel": pytest.approx(254.0)} and "y" not in res
    old = G.read_ini("[AXIS_0]\nMAX_VELOCITY = 50\nMAX_ACCELERATION = 500\n[AXIS_1]\nMAX_ACCELERATION = 400\n")
    assert old["x"] == {"velocity": 3000.0, "accel": 500.0} and old["y"] == {"accel": 400.0}
    assert G.read_ini("nothing here") == {}


def big_program(n=40000):
    out = ["G21 G90 G17", "G0 X0 Y0 Z5", "G1 Z-1 F3000"]
    for k in range(n):
        out.append(f"G1 X{(k % 50) * 0.7:.3f} Y{(k // 50) * 0.3:.3f} Z{-1 - (k % 7) * 0.1:.2f}")
    return "\n".join(out) + "\nM30\n"


def test_timing_a_40000_line_program_stays_quick():
    text = big_program()
    t0 = time.perf_counter()
    plain = G.read(text, rapid=FAST)
    t1 = time.perf_counter()
    acc = G.read(text, rapid=FAST, accel=A)
    t2 = time.perf_counter()
    assert acc.duration > plain.duration
    # the planner (the difference) costs less than reading the program again
    assert (t2 - t1) - (t1 - t0) < max(1.0, 1.0 * (t1 - t0)), (t1 - t0, t2 - t1)
