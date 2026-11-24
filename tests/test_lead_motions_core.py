"""Task 0309: lead motions in plain Python (core/lead_motions.py) – values at 0 / 25 / 50 / 100 %, timing windows,
easing, stages, rows from two states, "moved by", play-throughs, the step's values and the plain data for the web page."""

import math

import pytest

from fresing_render.core import lead_motions as L


def lm(*rows, seconds=4.0):
    return L.LeadMotion("Test", list(rows), seconds)


def test_one_joint_linear_at_0_25_50_100():
    m = lm(L.Row("Boom", 0.0, 1.0, easing="LINEAR"))
    assert [L.values(m, p)["Boom"] for p in (0, 25, 50, 100)] == pytest.approx([0.0, 0.25, 0.5, 1.0])


def test_smooth_easing_is_half_way_at_50_and_slow_at_the_ends():
    r = L.Row("J", 0.0, 2.0)                       # SMOOTH by default
    assert L.value(r, 50) == pytest.approx(1.0)
    assert L.value(r, 25) == pytest.approx(2.0 * (0.5 - 0.5 * math.cos(math.pi * 0.25)))
    assert L.value(r, 25) < 0.5                     # slower than constant speed at the start


@pytest.mark.parametrize("kind,at25", [("LINEAR", 0.25), ("EASE_IN", 1 - math.cos(0.25 * math.pi / 2)),
                                       ("EASE_OUT", math.sin(0.25 * math.pi / 2))])
def test_each_easing(kind, at25):
    assert L.value(L.Row("J", 0.0, 1.0, easing=kind), 25) == pytest.approx(at25)


def test_windows_move_joints_one_after_another():
    m = lm(L.Row("Outrigger", 0.0, 0.8, 0, 40, "LINEAR"), L.Row("Boom", 0.0, 1.0, 30, 100, "LINEAR"))
    v = L.values(m, 0)
    assert v == pytest.approx({"Outrigger": 0.0, "Boom": 0.0})
    v = L.values(m, 25)                              # outrigger on its way, boom not started
    assert v["Outrigger"] == pytest.approx(0.8 * 25 / 40) and v["Boom"] == 0.0
    v = L.values(m, 50)                              # outrigger out, boom 20/70 of the way
    assert v["Outrigger"] == pytest.approx(0.8) and v["Boom"] == pytest.approx(20 / 70)
    assert L.values(m, 100) == pytest.approx({"Outrigger": 0.8, "Boom": 1.0})


def test_a_negative_or_turned_window_and_a_window_of_no_width():
    r = L.Row("J", 1.0, -1.0, 80, 20, "LINEAR")     # given back to front: read as 20 … 80
    assert L.window(r) == (20.0, 80.0)
    assert L.value(r, 50) == pytest.approx(0.0)
    jump = L.Row("J", 0.0, 1.0, 50, 50)
    assert L.value(jump, 49.9) == 0.0 and L.value(jump, 50) == 1.0
    assert L.value(L.Row("J", 0.0, 1.0, -10, 140, "LINEAR"), 50) == pytest.approx(0.5)


def test_one_joint_out_and_back_in_one_lead_motion():
    m = lm(L.Row("Door", 0.0, 1.0, 0, 40, "LINEAR"), L.Row("Door", 1.0, 0.0, 60, 100, "LINEAR"))
    assert L.values(m, 20)["Door"] == pytest.approx(0.5)
    assert L.values(m, 50)["Door"] == pytest.approx(1.0)     # between the windows: open
    assert L.values(m, 80)["Door"] == pytest.approx(0.5)
    assert L.values(m, 100)["Door"] == pytest.approx(0.0)
    assert L.joints_of(m) == ["Door"]


def test_stage_windows():
    assert L.stage_windows([1, 2], overlap=0) == [(0.0, 50.0), (50.0, 100.0)]
    w = L.stage_windows([2, 1, 3, 1], overlap=10)
    assert w[1] == w[3] == (0.0, 38.333) and w[0] == (28.333, 71.667) and w[2] == (61.667, 100.0)
    assert L.stage_windows([5, 5]) == [(0.0, 100.0), (0.0, 100.0)]        # one stage: the whole slider
    assert L.stage_windows([]) == []


def test_rows_between_two_states_keep_the_joint_order_and_skip_still_joints():
    a = {"A": 0.0, "B": 0.5, "C": 1.0}
    b = {"A": 0.3, "B": 0.5, "C": 0.0}
    rows = L.rows_between(a, b, order=["C", "B", "A"])
    assert [(r.joint, r.v0, r.v1) for r in rows] == [("C", 1.0, 0.0), ("A", 0.0, 0.3)]
    assert L.rows_between(a, dict(a)) == []


def test_position_of_finds_the_slider_from_the_joints():
    m = lm(L.Row("A", 0.0, 1.0, 0, 50), L.Row("B", 0.0, 2.0, 50, 100))
    for p in (0.0, 12.5, 37.0, 50.0, 81.0, 100.0):
        assert L.position_of(m, L.values(m, p)) == pytest.approx(p, abs=0.05)
    assert L.position_of(m, {"A": 0.9, "B": 1.5}) is None        # no position has these two together


def test_moved_by_names_the_newest_lead_motion_sharing_a_joint():
    last = [("Slew", ["S"]), ("Boom up", ["B", "T"]), ("Outriggers", ["O"])]
    assert L.moved_by("Outriggers", ["O", "B"], last) == "Boom up"
    assert L.moved_by("Boom up", ["B"], last) == ""                # moved itself since
    assert L.moved_by("Other", ["X"], last) == ""


def test_play_target_and_positions():
    assert L.play_target(0) == 100.0 and L.play_target(42) == 100.0 and L.play_target(100) == 0.0
    assert L.play_position(0, 100, 4.0, 2.0) == pytest.approx(50.0)
    assert L.play_position(50, 100, 4.0, 1.0) == pytest.approx(75.0)    # half the way: half the time
    assert L.play_position(50, 100, 4.0, 9.0) == pytest.approx(100.0)
    assert L.play_position(100, 0, 4.0, 1.0) == pytest.approx(75.0)


def test_step_values_equal_the_slider_values():
    m = lm(L.Row("A", 0.0, 1.0, 0, 60), L.Row("B", 0.2, -0.4, 40, 100, "EASE_IN"))
    for prog in (0.0, 0.3, 0.5, 1.0):
        p = L.step_position(0, 100, "SMOOTH", prog)
        assert L.step_values(m, 0, 100, "SMOOTH", prog) == pytest.approx(L.values(m, p))
    assert L.step_position(0, 100, "SMOOTH", 0.5) == pytest.approx(50.0)
    assert L.step_position(100, 20, "LINEAR", 0.25) == pytest.approx(80.0)


def test_show_every_function_plans_out_and_back_one_after_another():
    plan = L.show_every_function([("Boom up", 3.0), ("Slew", 0.0)], start=2.0, gap=0.5)
    assert plan == [("Boom up", 0.0, 100.0, 2.0, 3.0), ("Boom up", 100.0, 0.0, 5.0, 3.0),
                    ("Slew", 0.0, 100.0, 8.5, 4.0), ("Slew", 100.0, 0.0, 12.5, 4.0)]


def test_samples_and_data_round_trip():
    m = lm(L.Row("A", 0.0, 1.0, 0, 50, "LINEAR", 1), L.Row("B", 1.0, 0.0, 50, 100, "LINEAR", 2), seconds=6.0)
    s = L.samples(m, 5)
    assert s["A"] == pytest.approx([0, 0.5, 1, 1, 1]) and s["B"] == pytest.approx([1, 1, 1, 0.5, 0])
    back = L.from_data(L.to_data(m))
    assert back.seconds == 6.0 and [(r.joint, r.stage) for r in back.rows] == [("A", 1), ("B", 2)]
    assert L.values(back, 30) == pytest.approx(L.values(m, 30))


def test_end_labels():
    one = [L.Row("Boom", 0.0, 0.6)]
    assert L.end_labels(one, lambda j, v: f"{j}={v}") == ("Boom=0.0", "Boom=0.6")
    assert L.end_labels([L.Row("A", 0, 1), L.Row("B", 0, 1)], str) == ("0 %", "100 %")
