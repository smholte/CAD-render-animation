"""Task 0066: rotary axes A, B, C in the G-code reader (no Blender).

Every expected number is worked out by hand in the comment next to it, not by the reader itself.
"""

import pytest

from fresing_render.core import gcode as G

RAPID = (6000.0, 6000.0, 3000.0)          # mm/min
ROT_RAPID = (3600.0, 1800.0, 7200.0)      # degrees/min: A, B, C


def run(text, **kw):
    kw.setdefault("rapid", RAPID)
    kw.setdefault("rot_rapid", ROT_RAPID)
    return G.read(text, **kw)


def motions(p):
    return [m for m in p.moves if m.moving]


def close(a, b, tol=1e-6):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def test_abc_words_on_g0_and_g1():
    p = run("G0 A90\nG0 B-45 C30\nG1 X10 A100 F600\n")
    m = motions(p)
    assert not p.problems
    assert close(m[0].ra, (0, 0, 0)) and close(m[0].rb, (90, 0, 0))
    assert m[0].dur == pytest.approx(90 / 3600 * 60)              # 1.5 s at A's 3600 deg/min
    assert close(m[1].rb, (90, -45, 30))
    assert m[1].dur == pytest.approx(max(45 / 1800, 30 / 7200) * 60)   # B is the slow one: 1.5 s
    assert close(m[2].b, (10, 0, 0)) and close(m[2].rb, (100, -45, 30))
    assert p.rotary == {"a": 1, "b": 2, "c": 2}                  # first line of each axis
    assert m[0].turn == pytest.approx(90.0)
    assert close(m[1].rot_at(0.5), (90, -22.5, 15))              # evenly along the move


def test_mixed_feed_rule_xyz_length_wins():
    # X 30 mm at F600 = 3 s; the 90 degrees of A would take 1.5 s at its rapid: the feed decides
    p = run("G1 X30 A90 F600\n")
    assert motions(p)[0].dur == pytest.approx(3.0)
    # the rotary axis' own speed limits a short linear move: X 1 mm (0.1 s) with A 90 deg (1.5 s at 3600 deg/min)
    p = run("G1 X1 A90 F600\n")
    assert motions(p)[0].dur == pytest.approx(1.5)


def test_pure_rotary_feed_is_degrees_per_minute():
    p = run("G1 A90 F360\n")                                     # 90 deg at 360 deg/min: 15 s
    m = motions(p)[0]
    assert m.kind == "FEED" and m.length == 0.0
    assert m.dur == pytest.approx(15.0)
    p = run("G1 A30 C40 F100\n")                                 # combined angle sqrt(30² + 40²) = 50 deg: 30 s
    assert motions(p)[0].dur == pytest.approx(30.0)


def test_g93_inverse_time_and_back_to_g94():
    p = run("G93 G1 X10 A45 F2\nG1 A90 F0.5\nG94 G1 X20 F600\n")
    m = motions(p)
    assert m[0].dur == pytest.approx(30.0)                       # F2: the move takes 1/2 minute
    assert m[1].dur == pytest.approx(120.0)                      # F0.5: 2 minutes (pure rotary too)
    assert m[2].dur == pytest.approx(1.0)                        # G94: 10 mm at 600 mm/min
    assert not p.problems
    p = run("G93 G1 X10 A45 F2\nG1 X20 A50\n")                   # G93 needs F on every line
    assert any("G93" in x for x in p.problem_lines())


def test_wrapped_axis_goes_the_way_its_sign_says():
    p = run("G0 A350\nG0 A10\nG0 A-350\nG0 A-10\n", wrapped=(True, False, False))
    rb = [m.rb[0] for m in motions(p)]
    # 0 -> 350 the + way; 350 -> 10 the + way (+20, kept as 370); A-350: to 350 the - way (-20 -> 350);
    # A-10: to 10 the - way from 350 (-340 -> 10)
    assert rb == pytest.approx([350.0, 370.0, 350.0, 10.0])
    p = run("G0 A350\nG0 A10\n")                                 # not wrapped: plain degrees, back 340
    assert [m.rb[0] for m in motions(p)] == pytest.approx([350.0, 10.0])
    p = run("G0 A370\n#1 = #5423\nG0 X#1\n", wrapped=(True, False, False))
    assert motions(p)[0].rb[0] == pytest.approx(10.0)            # 370 is 10 on a wrapped axis, the + way
    assert motions(p)[-1].b[0] == pytest.approx(10.0)            # #5423 reads A in 0 … 360


def test_relative_moves_turn_by_the_number():
    p = run("G91 G0 A90\nG0 A90\nG0 A-45\n", wrapped=(True, False, False))
    assert [m.rb[0] for m in motions(p)] == pytest.approx([90.0, 180.0, 135.0])


def test_arc_with_a_rotary_word_turns_evenly_along_the_arc():
    p = run("G0 X10 Y0\nG3 X-10 Y0 I-10 J0 A180 F600\n")
    arc = motions(p)[-1]
    assert arc.kind == "ARC"
    assert arc.dur == pytest.approx(3.14159265 * 10 / 600 * 60)  # the half circle's length at F600
    assert close(arc.rot_at(0.5), (90, 0, 0))
    assert close(arc.at(0.5), (0, 10, 0), 1e-9)
    assert close(arc.rb, (180, 0, 0))


def test_g28_g30_g53_g92_g10_with_rotary_words():
    p = run("G0 X5 A90\nG28.1\nG0 X0 A0\nG28\n")
    m = motions(p)
    assert close(m[-1].b, (5, 0, 0)) and close(m[-1].rb, (90, 0, 0))   # home 28 stored with A
    p = run("G0 A90\nG28 A45\n")                                  # through A45, then A home (0)
    assert [x.rb[0] for x in motions(p)] == pytest.approx([90.0, 45.0, 0.0])
    p = run("G0 A90 X10\nG28 X5\n")                               # only X goes home: A stays
    assert motions(p)[-1].rb[0] == pytest.approx(90.0)
    p = run("G10 L2 P1 A30\nG54 G0 A10\nG53 G0 A10\n")
    assert [x.rb[0] for x in motions(p)] == pytest.approx([40.0, 10.0])  # G54 A zero at 30; G53 machine
    p = run("G0 A50\nG92 A0\nG0 A10\nG92.1\nG0 A10\n")
    assert [x.rb[0] for x in motions(p)] == pytest.approx([50.0, 60.0, 10.0])
    p = run("G0 A20\nG10 L20 P1 A0\nG0 A5\n")                     # L20: the current A (20) is 0
    assert motions(p)[-1].rb[0] == pytest.approx(25.0)


def test_uvw_are_still_reported_and_cycles_ignore_rotary_words():
    p = run("G0 U5\nG0 Z5\nG81 X1 Y1 Z-2 R1 A30 F100\nG80\n")
    lines = p.problem_lines()
    assert any("U axis" in t and "line 1" in t for t in lines)
    assert any("drilling cycle" in t and "line 3" in t for t in lines)
    assert all(abs(m.rb[0]) < 1e-12 for m in motions(p))


def test_start_rot_and_moves_that_do_not_turn():
    p = run("G1 X10 F600\nT2 M6\nG4 P1\n", start_rot=(15.0, 0.0, -5.0))
    for mv in p.moves:
        assert close(mv.ra, (15, 0, -5)) and close(mv.rb, (15, 0, -5))
        assert mv.turn == 0.0


def test_schedule_rot_at_samples_and_turn_spans():
    p = run("G1 X10 F600\nG1 A90 F360\nT2 M6\nG1 X0 F600\n")
    sch = G.Schedule(p, G.Timing(tool_change=2.0))
    # X 10 mm: 1 s; A 90 deg: 15 s (1 .. 16); the tool change 2 s (16 .. 18); X back 1 s
    assert sch.duration == pytest.approx(19.0)
    assert close(sch.rot_at(0.5), (0, 0, 0))
    assert close(sch.rot_at(1.0 + 7.5), (45, 0, 0))
    assert close(sch.rot_at(17.0), (90, 0, 0))                    # still during the tool change
    assert close(sch.rot_at(30.0), (90, 0, 0))
    assert sch.turns and sch.turn_spans() == [(pytest.approx(1.0), pytest.approx(16.0))]
    plain = sch.samples(25.0, per_frame=False)
    fine = sch.samples(25.0, per_frame=False, turn_step=10.0)
    # 90 degrees every 10 degrees: 8 more keys inside the turning move, at 1 + k * 15/9 s
    extra = sorted({round(t, 9) for t, _p in fine} - {round(t, 9) for t, _p in plain})
    assert len(extra) == 8
    assert extra[0] == pytest.approx(1.0 + 15.0 / 9.0)
    assert [sch.rot_at(t)[0] for t in extra] == pytest.approx([10.0 * k for k in range(1, 9)])
    # the toolpath: a turning move drawn every turn_step degrees
    lines = sch.path(turn_step=10.0)
    assert max(len(pts) for _r, pts in lines) >= 10


def test_three_axis_programs_unchanged():
    text = "G0 X10 Y10\nG1 Z-1 F100\nG2 X20 Y10 I5 J0 F300\nG0 Z5\n"
    p = run(text)
    sch = G.Schedule(p, G.Timing())
    assert not sch.turns and sch.turn_spans() == []
    # the samples are the same with or without turn_step when nothing turns
    assert sch.samples(25.0) == sch.samples(25.0, turn_step=1.0)
    assert all(close(m.rb, (0, 0, 0)) for m in p.moves)
