"""The words and numbers of the "Making the Learning hub" card (task 0275)."""

from fresing_render.core import hub_progress as hp


def test_fraction_and_project_line():
    assert hp.fraction(0, 23) == 0.0 and hp.fraction(23, 23) == 1.0 and hp.fraction(5, 0) == 0.0
    assert hp.project_line(3, 23, "Crane") == "project 4 of 23 – Crane"
    assert hp.project_line(23, 23) == "project 23 of 23"


def test_time_left_from_the_time_per_project():
    assert hp.seconds_left(4, 20, 80.0, 600.0) == 320.0
    assert hp.seconds_left(0, 20, 5.0, 600.0) == 595.0        # before the first project: the expectation
    assert hp.seconds_left(0, 20, 900.0, 600.0) == 0.0


def test_shown_time_moves_in_steps_and_never_jumps_up():
    assert hp.settle(100.0, None) == 120.0
    assert hp.settle(100.0, 150.0) == 120.0                    # falls freely
    assert hp.settle(400.0, 120.0) == 150.0                    # rises by one step only
    assert hp.settle(0.0, 60.0) == 0.0


def test_texts():
    assert hp.left_text(20) == "less than a minute left"
    assert hp.left_text(120) == "about 2 min left"
    assert "keep working" in hp.KEEP_WORKING and "bottom-left" in hp.KEEP_WORKING
    assert "about 3 minutes" in hp.intro(3) and "about 1 minute on" in hp.intro(0)
