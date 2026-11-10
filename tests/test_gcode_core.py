"""Task 0026: the G-code reader (LinuxCNC / RS274NGC) without Blender.

Every expected point below is worked out by hand (comments say how), not by the reader itself.
"""

import math
import time

import pytest

from fresing_render.core import gcode as G

RAPID = (6000.0, 6000.0, 3000.0)          # mm/min: X, Y fast, Z slower


def run(text, **kw):
    kw.setdefault("rapid", RAPID)
    return G.read(text, **kw)


def motions(p):
    return [m for m in p.moves if m.moving]


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# straight moves, units, distance modes
# ---------------------------------------------------------------------------

def test_rapid_and_feed_positions_and_times():
    p = run("G21 G90\nG0 X60 Y0 Z0\nG1 X60 Y30 F600\nG1 Z-10\n")
    m = motions(p)
    assert [x.kind for x in m] == ["RAPID", "FEED", "FEED"]
    assert close(m[0].b, (60, 0, 0)) and close(m[1].b, (60, 30, 0)) and close(m[2].b, (60, 30, -10))
    assert m[0].dur == pytest.approx(60 / 6000 * 60)        # 0.6 s: X at 6000 mm/min
    assert m[1].dur == pytest.approx(30 / 600 * 60)         # 3 s at F600
    assert m[2].dur == pytest.approx(10 / 600 * 60)         # F is modal: 1 s
    assert m[1].t0 == pytest.approx(0.6) and p.duration == pytest.approx(4.6)
    assert not p.problems


def test_rapid_time_is_the_slowest_axis():
    p = run("G0 X30 Z30\n")                                 # X needs 0.3 s, Z (3000 mm/min) 0.6 s
    assert motions(p)[0].dur == pytest.approx(0.6)


def test_feed_never_faster_than_the_axes():
    p = run("G1 Z-30 F99999\n")                             # Z can only do 3000 mm/min: 0.6 s
    assert motions(p)[0].dur == pytest.approx(0.6)


def test_inch_mode():
    p = run("G20\nG1 X1 Y2 F10\n")
    m = motions(p)[0]
    assert close(m.b, (25.4, 50.8, 0))
    assert m.feed == pytest.approx(254.0)
    assert m.dur == pytest.approx(math.hypot(25.4, 50.8) / 254 * 60)


def test_incremental_mode():
    p = run("G90 G0 X10 Y10\nG91\nG1 X5 F100\nY-3\nG90\nX0\n")
    pts = [m.b for m in motions(p)]
    assert close(pts[1], (15, 10, 0)) and close(pts[2], (15, 7, 0)) and close(pts[3], (0, 7, 0))


def test_work_offset_g54_from_the_app_and_g53_machine_coordinates():
    p = run("G54 G0 X0 Y0 Z5\nG53 G0 Z0\nG0 X10\n", g54=(100.0, 50.0, -200.0))
    pts = [m.b for m in motions(p)]
    assert close(pts[0], (100, 50, -195))                   # program (0, 0, 5) + G54
    assert close(pts[1], (100, 50, 0))                      # machine Z0, X/Y stay
    assert close(pts[2], (110, 50, 0))                      # back in G54 for X


def test_g10_sets_g55_and_g92_shifts():
    text = "G10 L2 P2 X200 Y0 Z0\nG55 G0 X0 Y0\nG54 G0 X0 Y0\nG92 X50\nG0 X60\nG92.1\nG0 X60\n"
    p = run(text)
    pts = [m.b for m in motions(p)]
    assert close(pts[0], (200, 0, 0))
    assert close(pts[1], (0, 0, 0))
    # G92 X50 at machine X0: the current point becomes X50, so X60 is machine X10
    assert close(pts[2], (10, 0, 0))
    assert close(pts[3], (60, 0, 0))
    assert not p.problems


def test_g10_l20_sets_the_current_point():
    p = run("G0 X30 Y40\nG10 L20 P1 X0 Y0\nG0 X5 Y5\n")
    assert close(motions(p)[-1].b, (35, 45, 0))


def test_g55_without_g10_is_reported_and_taken_as_g54():
    p = run("G55\nG0 X1\n", g54=(10.0, 0.0, 0.0))
    assert close(motions(p)[0].b, (11, 0, 0))
    assert any("G55" in t and "line 1" in t for t in p.problem_lines())


def test_g28_with_intermediate_point_and_g28_1():
    # G91 G28 Z0: straight up to the home Z (the usual CAM line), X/Y stay
    p = run("G0 X10 Y10 Z-20\nG91 G28 Z0\nG90\n", home=(0.0, 0.0, 0.0))
    assert close(motions(p)[-1].b, (10, 10, 0))
    p = run("G0 X10 Y10 Z5\nG28.1\nG0 X0 Y0 Z0\nG28 X3\n")
    pts = [m.b for m in motions(p)]
    assert close(pts[-2], (3, 0, 0))                        # through X3 (intermediate) ...
    assert close(pts[-1], (10, 0, 0))                       # ... to the stored home X only


# ---------------------------------------------------------------------------
# arcs
# ---------------------------------------------------------------------------

def test_g2_quarter_circle_xy_by_hand():
    # from (10, 0) clockwise about (0, 0) to (0, -10): the middle is at -45 degrees
    p = run("G0 X10 Y0\nG17 G2 X0 Y-10 I-10 J0 F600\n")
    a = motions(p)[-1]
    assert a.kind == "ARC" and a.sweep == pytest.approx(-math.pi / 2)
    s = 10 / math.sqrt(2)
    assert close(a.at(0.5), (s, -s, 0), 1e-9)
    assert a.length == pytest.approx(10 * math.pi / 2)
    assert a.dur == pytest.approx(a.length / 600 * 60)


def test_g3_half_circle_xy():
    p = run("G0 X0 Y0\nG3 X20 Y0 I10 J0 F100\n")            # counter-clockwise from 180 deg to 0 through 270
    a = motions(p)[-1]
    assert close(a.at(0.5), (10, -10, 0), 1e-9)


def test_full_circle():
    p = run("G0 X10 Y0\nG2 X10 Y0 I-10 J0 F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(-2 * math.pi)
    assert close(a.at(0.25), (0, -10, 0), 1e-9)             # clockwise: 0 deg -> -90 deg
    assert close(a.at(0.5), (-10, 0, 0), 1e-9)


def test_arc_in_xz_plane_g18():
    # G18: I (X) and K (Z). From (10, 0, 0) about (0, 0, 0) G2 to (0, 0, 10)?
    # Clockwise seen from +Y. In the XZ plane seen from +Y, X points left... worked out with the
    # right-hand rule: positive turn about +Y takes +Z to +X. Clockwise (negative about +Y) takes +X to +Z.
    p = run("G0 X10 Y0 Z0\nG18 G2 X0 Z10 I-10 K0 F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(-math.pi / 2)
    s = 10 / math.sqrt(2)
    assert close(a.at(0.5), (s, 0, s), 1e-9)


def test_arc_in_yz_plane_g19():
    # G19: J (Y) and K (Z), clockwise seen from +X: negative turn about +X takes +Y to -Z
    p = run("G0 X0 Y10 Z0\nG19 G2 Y0 Z-10 J-10 K0 F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(-math.pi / 2)
    s = 10 / math.sqrt(2)
    assert close(a.at(0.5), (0, s, -s), 1e-9)


def test_helical_arc():
    p = run("G0 X10 Y0 Z0\nG3 X-10 Y0 Z-4 I-10 J0 F100\n")
    a = motions(p)[-1]
    assert close(a.at(0.5), (0, 10, -2), 1e-9)              # half way round: top of the circle, half the depth
    assert a.length == pytest.approx(math.hypot(10 * math.pi, 4))


def test_arc_with_turns_p():
    p = run("G0 X10 Y0\nG3 X10 Y0 I-10 J0 P3 F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(6 * math.pi)


def test_arc_radius_format_short_and_long():
    # from (0, 0) to (10, 0), R 5: a half circle; clockwise goes over the top (centre (5, 0))
    p = run("G0 X0 Y0\nG2 X10 Y0 R5 F100\n")
    assert close(motions(p)[-1].at(0.5), (5, 5, 0), 1e-9)
    # R = 10 / sqrt(2): centre (5, -5) for the short clockwise arc, which passes (5, -5 + 7.07)
    r = 10 / math.sqrt(2)
    p = run(f"G0 X0 Y0\nG2 X10 Y0 R{r:.9f} F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(-math.pi / 2)
    assert close(a.at(0.5), (5, -5 + r, 0), 1e-6)
    # negative R: the long way round (270 deg), centre on the other side (5, 5)
    p = run(f"G0 X0 Y0\nG2 X10 Y0 R-{r:.9f} F100\n")
    a = motions(p)[-1]
    assert a.sweep == pytest.approx(-1.5 * math.pi)
    assert close(a.centre[:2], (5, 5), 1e-6)
    assert close(a.at(0.5), (5, 5 + r, 0), 1e-6)            # starts at 225 deg, 135 deg clockwise: 90 deg


def test_absolute_arc_centres_g90_1():
    p = run("G90.1\nG0 X20 Y10\nG2 X10 Y0 I10 J10 F100\n")     # centre (10, 10) absolute
    a = motions(p)[-1]
    assert close(a.centre[:2], (10, 10))
    assert a.sweep == pytest.approx(-math.pi / 2)


def test_arc_centres_with_a_work_offset():
    p = run("G90.1\nG0 X20 Y10\nG2 X10 Y0 I10 J10 F100\n", g54=(100.0, 0.0, 0.0))
    assert close(motions(p)[-1].centre[:2], (110, 10))


def test_arc_whose_end_is_off_the_circle_is_reported():
    p = run("G0 X10 Y0\nG2 X0 Y-12 I-10 J0 F100\n")
    assert any("not on its circle" in t and "line 2" in t for t in p.problem_lines())


# ---------------------------------------------------------------------------
# feed modes, spindle, tools, end
# ---------------------------------------------------------------------------

def test_inverse_time_and_feed_per_turn():
    p = run("G93\nG1 X10 F30\n")                            # F30: the move takes 1/30 min = 2 s
    assert motions(p)[0].dur == pytest.approx(2.0)
    p = run("G95 S1000 M3\nG1 X10 F0.1\n")                  # 0.1 mm/turn x 1000 rpm = 100 mm/min -> 6 s
    assert motions(p)[0].dur == pytest.approx(6.0)


def test_spindle_and_tool_changes():
    text = "T1 M6\nS8000 M3\nG0 X10\nM4 S500\nG0 X20\nM5\nG0 X30\nT2\nG0 X40\nM6\nG0 X50\nM30\nG0 X99\n"
    p = run(text)
    tools = [m for m in p.moves if m.kind == "TOOL"]
    assert [(m.tool, m.line) for m in tools] == [(1, 1), (2, 10)]
    m = motions(p)
    assert [x.spindle for x in m] == [8000, -500, 0, 0, 0]
    assert [x.tool for x in m] == [1, 1, 1, 1, 2]          # T2 only selects; M6 changes
    assert p.ended and close(m[-1].b, (50, 0, 0))          # nothing after M30
    assert any("M2/M30 on line 12" in n for n in p.notes)


def test_dwell():
    p = run("G0 X1\nG4 P2.5\nG0 X2\n")
    d = [m for m in p.moves if m.kind == "DWELL"][0]
    assert d.dur == 2.5 and d.line == 2


# ---------------------------------------------------------------------------
# drilling cycles
# ---------------------------------------------------------------------------

def _pts(p):
    return [tuple(round(c, 6) for c in m.b) for m in motions(p)]


def test_g81_g98_and_g99():
    # start at Z10; R2; Z-5. G98: back up to Z10; G99: back to R
    p = run("G0 X0 Y0 Z10\nG98 G81 X5 Y5 Z-5 R2 F100\nX15\nG80\n")
    assert _pts(p)[1:] == [(5, 5, 10), (5, 5, 2), (5, 5, -5), (5, 5, 10),
                           (15, 5, 10), (15, 5, 2), (15, 5, -5), (15, 5, 10)]
    p = run("G0 X0 Y0 Z10\nG99 G81 X5 Y5 Z-5 R2 F100\nX15\n")
    assert _pts(p)[1:] == [(5, 5, 10), (5, 5, 2), (5, 5, -5), (5, 5, 2),
                           (15, 5, 2), (15, 5, -5), (15, 5, 2)]
    assert all(m.cycle == "G81" for m in motions(p)[1:])


def test_g82_dwells_at_the_bottom():
    p = run("G0 Z10\nG82 X0 Y0 Z-3 R1 P0.5 F60\n")
    kinds = [m.kind for m in p.moves]
    assert kinds == ["RAPID", "RAPID", "FEED", "DWELL", "RAPID"]
    assert p.moves[3].dur == 0.5


def test_g83_pecks_by_hand():
    # R1, Z-5, Q2.5: down to -1.5, out to R, back down to -1.5 + 0.254, on to -4, out, back down, on to -5
    c = G.PECK_CLEAR
    p = run("G0 X0 Y0 Z5\nG99 G83 X0 Y0 Z-5 R1 Q2.5 F100\n")
    assert _pts(p)[1:] == [(0, 0, 1), (0, 0, -1.5), (0, 0, 1), (0, 0, round(-1.5 + c, 6)),
                           (0, 0, -4), (0, 0, 1), (0, 0, round(-4 + c, 6)), (0, 0, -5), (0, 0, 1)]


def test_g73_chip_break():
    c = G.PECK_CLEAR
    p = run("G0 X0 Y0 Z1\nG98 G73 X0 Y0 Z-3 R1 Q2 F100\n")
    assert _pts(p)[1:] == [(0, 0, -1), (0, 0, round(-1 + c, 6)), (0, 0, -3), (0, 0, 1)]


def test_g85_feeds_out():
    p = run("G0 X0 Y0 Z5\nG99 G85 X0 Y0 Z-2 R1 F100\n")
    kinds = [m.kind for m in motions(p)]
    assert kinds == ["RAPID", "RAPID", "FEED", "FEED"] and _pts(p)[-1] == (0, 0, 1)


def test_cycle_incremental_with_repeats():
    # G91: X/Y steps of 10 from the start, R 2 below the start Z (R-2 -> Z3), Z-4 below R -> Z-1; L3 holes
    p = run("G0 X0 Y0 Z5\nG91 G99 G81 X10 Y0 Z-4 R-2 L3 F100\nG90\n")
    holes = [m.b for m in motions(p) if m.kind == "FEED"]
    assert [tuple(round(c, 6) for c in h) for h in holes] == [(10, 0, -1), (20, 0, -1), (30, 0, -1)]


def test_cycle_in_g18_plane_drills_along_y():
    p = run("G0 X0 Y10 Z0\nG18 G98 G81 X5 Z5 Y-3 R2 F100\n")
    assert _pts(p)[1:] == [(5, 10, 5), (5, 2, 5), (5, -3, 5), (5, 10, 5)]


# ---------------------------------------------------------------------------
# comments, tools, problems
# ---------------------------------------------------------------------------

FUSION_HEAD = """%
(1001)
(Machine)
(  vendor: generic)
(T1  D=6. CR=0. - ZMIN=-10. - flat end mill)
(T2  D=4. CR=2. - ZMIN=-3. - ball end mill)
(T3  D=6. CR=1. - ZMIN=-3. - bullnose end mill)
(T4  D=5. CR=0. TAPER=118deg - ZMIN=-12. - drill)
(T5  D=10. CR=0. TAPER=45deg - ZMIN=-1. - chamfer mill)
G90 G94 G17 G91.1
G21
"""


def test_fusion_tool_comments():
    p = run(FUSION_HEAD + "M30\n%\n")
    t = p.tools
    assert (t[1].kind, t[1].diameter) == ("FLAT", 6.0)
    assert (t[2].kind, t[2].corner) == ("BALL", 2.0)
    assert (t[3].kind, t[3].corner) == ("BULL", 1.0)
    assert (t[4].kind, t[4].angle) == ("DRILL", 118.0)
    assert (t[5].kind, t[5].angle) == ("VEE", 90.0)
    assert p.name == "1001"
    assert not p.problems


def test_tool_table():
    table = G.read_tool_table("T1 P1 D6.000 Z+42.5 ;6 mm flat end mill\nT7 P7 D3.0 Z+30 ;ball nose\n"
                              ";comment line\n")
    assert table[1].diameter == 6.0 and table[1].length == 42.5 and table[1].kind == "FLAT"
    assert table[7].kind == "BALL" and table[7].corner == 1.5
    p = run("(T1 D=8. CR=0. - flat end mill)\nT1 M6\n", tools=table)
    assert p.tools[1].diameter == 6.0 and p.tools[1].length == 42.5     # the table's sizes win
    assert p.tools[7].diameter == 3.0


def test_comments_semicolons_line_numbers_and_block_delete():
    p = run("N10 G0 X1 (go) Y2 ; rest ignored X99\n/N20 G0 X3\n% \n")
    assert _pts(p) == [(1, 2, 0), (3, 2, 0)]


def test_unknown_codes_reported_with_line_numbers():
    text = "G0 X1\nG12 X2\nM123\nG41 D1\nG1 X3 U45 F100\nG1 X4 U90\nM77\n"
    p = run(text)
    lines = p.problem_lines()
    assert any("G12" in t and "line 2" in t for t in lines)
    assert any("M123" in t and "line 3" in t for t in lines)
    assert any("G41" in t and "line 4" in t for t in lines)
    assert any("U axis" in t and "lines 5, 6" in t for t in lines)    # (A/B/C are read since task 0066)
    assert any("M77" in t and "line 7" in t for t in lines)
    assert close(motions(p)[-1].b, (4, 0, 0))              # the rest of those lines still ran


def test_a_broken_line_is_reported_and_the_rest_runs():
    p = run("G0 X1\nG1 X[1 + ] F100\nG0 X2\nG0 X1 X2\n")
    lines = p.problem_lines()
    assert any("line 2" in t for t in lines) and any("line 4" in t and "twice" in t for t in lines)
    assert close(motions(p)[-1].b, (2, 0, 0))


def test_many_lines_of_one_problem_are_summed_up():
    p = run("".join(f"G1 X{i} V{i} F100\n" for i in range(1, 21)))
    t = [x for x in p.problem_lines() if "V axis" in x][0]
    assert "lines 1, 2, 3, 4, 5 and 15 more" in t


# ---------------------------------------------------------------------------
# parameters, expressions, o-words
# ---------------------------------------------------------------------------

def test_expressions_and_functions():
    text = ("#1 = 2\n#<w> = [#1 * 3 + 2 ** 3 / 4]\nG0 X#<w>\n"          # 6 + 2 = 8
            "G0 X[SIN[30] * 10]\n"                                     # 5
            "G0 X[ATAN[1]/[1]]\n"                                      # 45
            "G0 X[ABS[-3] + SQRT[16] + FIX[2.7] + FUP[2.1] + ROUND[2.5]]\n"   # 3+4+2+3+3 = 15
            "G0 X[7 MOD 3 + [1 LT 2] + [2 EQ 3] + [1 AND 0] + [1 OR 0]]\n"   # 1+1+0+0+1 = 3
            "G0 X[-#1 - -1]\n"                                         # -1
            "G0 X[EXISTS[#<w>] + EXISTS[#<nope>]]\n")                  # 1
    xs = [round(m.b[0], 9) for m in motions(run(text))]
    assert xs == [8, 5, 45, 15, 3, -1, 1]


def test_parameters_are_set_after_the_line():
    p = run("#1 = 5\n#1 = 7 G0 X#1\nG0 X#1\n")
    assert [m.b[0] for m in motions(p)] == [5, 7]


def test_if_elseif_else():
    text = ("#1 = 2\no10 if [#1 EQ 1]\nG0 X1\no10 elseif [#1 EQ 2]\nG0 X2\no10 else\nG0 X3\no10 endif\n"
            "#1 = 9\no11 if [#1 EQ 1]\nG0 Y1\no11 else\nG0 Y3\no11 endif\n")
    assert _pts(run(text)) == [(2, 0, 0), (2, 3, 0)]


def test_while_do_repeat_break_continue():
    text = ("#1 = 0\no1 while [#1 LT 5]\n#1 = [#1 + 1]\no2 if [#1 EQ 2]\no1 continue\no2 endif\n"
            "o3 if [#1 EQ 4]\no1 break\no3 endif\nG0 X#1\no1 endwhile\n"     # X1, X3 (2 skipped, stops at 4)
            "#2 = 0\no4 do\n#2 = [#2 + 1]\nG0 Y#2\no4 while [#2 LT 3]\n"       # Y1 Y2 Y3
            "o5 repeat [2]\nG91 G0 Z-1\nG90\no5 endrepeat\n")                 # Z-1, Z-2
    assert _pts(run(text)) == [(1, 0, 0), (3, 0, 0), (3, 1, 0), (3, 2, 0), (3, 3, 0), (3, 3, -1), (3, 3, -2)]


def test_subroutines_with_arguments_locals_and_return_values():
    text = ("o100 sub\n#<x> = [#1 * 2]\nG0 X#<x> Y#2\no100 return [#1 + #2]\no100 endsub\n"
            "o100 call [3] [4]\nG0 Z#<_value>\no100 call [1] [0]\n"
            "G0 Y[1 + EXISTS[#<x>]]\nM2\n")
    p = run(text)
    assert _pts(p) == [(6, 4, 0), (6, 4, 7), (2, 0, 7), (2, 1, 7)]   # #<x> was local: gone after the call
    assert [m.top for m in motions(p)] == [6, 7, 8, 9]               # moves inside a sub count for its call line


def test_subroutine_file_next_to_the_program(tmp_path):
    (tmp_path / "pocket.ngc").write_text("o<pocket> sub\nG0 X#1\no<pocket> endsub\n")
    p = run("o<pocket> call [12]\nM30\n", base_dir=str(tmp_path))
    assert _pts(p) == [(12, 0, 0)]
    p = run("o<missing> call [12]\nM30\n", base_dir=str(tmp_path))
    assert any("o<missing>" in t and "line 1" in t for t in p.problem_lines())


def test_endless_loop_is_stopped(monkeypatch):
    monkeypatch.setattr(G, "MAX_STEPS", 2000)
    p = run("o1 while [1]\nG0 X1\no1 endwhile\n")
    assert any("never ends" in t for t in p.problem_lines())


def test_system_parameters():
    p = run("T3 M6\nG0 X10 Y20\nG0 Z#5400\nG0 X[#5420 + 1]\n")
    assert _pts(p)[-2:] == [(10, 20, 3), (11, 20, 3)]


# ---------------------------------------------------------------------------
# timing in the video
# ---------------------------------------------------------------------------

PROG = "T1 M6\nS1000 M3\nG0 X60\nG1 X120 F600\nT2 M6\nG1 X180\nM5\n"    # rapid 0.6 s, feed 6 s, feed 6 s


def test_schedule_real_faster_fit_and_rapids():
    p = run(PROG)
    s = G.Schedule(p, G.Timing(tool_change=2.0))
    assert s.duration == pytest.approx(2 + 0.6 + 6 + 2 + 6)
    s = G.Schedule(p, G.Timing(speed="FASTER", factor=2.0, tool_change=2.0))
    assert s.duration == pytest.approx(4 + 12.6 / 2)
    s = G.Schedule(p, G.Timing(speed="FIT", fit_seconds=10.0, tool_change=2.0))
    assert s.duration == pytest.approx(10.0)
    s = G.Schedule(p, G.Timing(rapid_factor=3.0, tool_change=0.0))
    assert s.duration == pytest.approx(0.2 + 12)
    assert [(round(t, 6), n) for t, n, _s, _d in G.Schedule(p, G.Timing(tool_change=2, swap=0.5)).tool_events] \
        == [(0.5, 1), (8.6 + 0.5, 2)]


def test_schedule_points_and_line_range():
    p = run(PROG)
    s = G.Schedule(p, G.Timing(tool_change=0.0))
    assert close(s.point_at(0.3), (30, 0, 0)) and close(s.point_at(0.6 + 3), (90, 0, 0))
    assert close(s.point_at(999), (180, 0, 0))
    s = G.Schedule(p, G.Timing(line_from=4, line_to=4))
    assert s.duration == pytest.approx(6.0) and close(s.start_point, (60, 0, 0))
    assert s.first_tool == 1 and s.start_spindle == 1000


def test_samples_follow_arcs_within_the_tolerance():
    p = run("G0 X50 Y0\nG3 X50 Y0 I-50 J0 F3000\n")
    s = G.Schedule(p, G.Timing())
    keys = s.samples(25.0, tol=0.002)
    arc = motions(p)[-1]
    # between two keys, the straight line's middle must be within 0.002 mm of the circle
    worst = 0.0
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if t0 < 0.6:
            continue
        mid = [(x + y) / 2 for x, y in zip(a, b)]
        worst = max(worst, abs(math.hypot(mid[0], mid[1]) - 50))
    assert worst <= 0.002 + 1e-9
    # every frame inside the arc has a key
    f = 0.6 + 0.4
    assert any(abs(t - f) < 1e-9 for t, _p in keys)
    assert arc.dur > 0


def test_spindle_keys():
    s = G.Schedule(run(PROG), G.Timing(tool_change=2.0))
    # on with the first move after the tool change, off at the end
    assert [(round(t, 6), r) for t, r in s.spindle_keys()] == [(0.0, 0.0), (2.0, 1000.0), (16.6, 0.0)]


def test_path_polylines():
    p = run("G0 X10\nG1 X20 F600\nG1 Y10\nG0 Z5\n")
    lines = G.Schedule(p, G.Timing()).path()
    assert [(r, len(pts)) for r, pts in lines] == [(True, 2), (False, 3), (True, 2)]


# ---------------------------------------------------------------------------
# speed
# ---------------------------------------------------------------------------

def test_a_long_program_reads_quickly():
    """About 60,000 lines (a 3D finishing pass of short moves and arcs): measured, must stay quick."""
    rows = ["G21 G90 G94 G17", "T1 M6", "S12000 M3", "G0 X0 Y0 Z5", "G1 Z-1 F1200"]
    for i in range(30000):
        x = (i % 200) * 0.5
        rows.append(f"G1 X{x:.3f} Y{(i // 200) * 0.5:.3f} Z{-1 - 0.001 * (i % 7):.4f}")
        rows.append(f"G2 X{x + 0.25:.3f} Y{(i // 200) * 0.5:.3f} R0.125")
    rows.append("M30")
    t0 = time.perf_counter()
    p = run("\n".join(rows))
    dt = time.perf_counter() - t0
    assert len(p.moves) > 59000 and not p.problems
    assert dt < 15.0, dt
