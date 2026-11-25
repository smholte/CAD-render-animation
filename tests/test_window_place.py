"""Task 0331 (0328 row 12): where an app window opens the first time – core/window_place.py, plain numbers.

Blender put every app window at the main view's top-left corner, over the left panel and over each other. The first
place is now beside the side panel (the next one offset), or over the view's middle when it does not fit there. On
Windows ``ops_setup.first_place`` moves the window there (winplace.py); the real-app test ``ui_test_setup.py`` checks
the place it works out for a real Set-up window.
"""

import pytest

from fresing_render.core import window_place as P

VIEW = (100, 50, 1600, 900)                       # x, y (bottom), width, height – Blender's coordinates
SIDE, LEFT = 300, 220


def right_edge(x, size):
    return x + size[0]


def test_the_first_window_stands_beside_the_side_panel_under_the_header():
    x, top = P.first_place(VIEW, (400, 500), SIDE, LEFT)
    assert right_edge(x, (400, 500)) == 100 + 1600 - SIDE - P.MARGIN
    assert x >= 100 + LEFT + P.MARGIN, "not over the left panel"
    assert top == 50 + 900 - P.TOP and top - 500 >= 50, "under the view's top edge, inside the view"


def test_the_next_ones_are_offset_left_and_down_and_start_again():
    places = [P.first_place(VIEW, (400, 500), SIDE, LEFT, n) for n in range(P.CYCLE + 1)]
    for (x0, t0), (x1, t1) in zip(places, places[1:P.CYCLE]):
        assert x1 == x0 - P.STEP and t1 == t0 - P.STEP
    assert len(set(places[:P.CYCLE])) == P.CYCLE, "no two on top of each other"
    assert places[P.CYCLE] == places[0]
    assert all(right_edge(x, (400, 500)) <= 100 + 1600 - SIDE for x, _t in places), "never over the side panel"


def test_a_window_too_wide_for_the_gap_goes_over_the_middle():
    x, _top = P.first_place(VIEW, (1200, 500), SIDE, LEFT)
    assert x == 100 + (1600 - 1200) // 2
    x, _top = P.first_place(VIEW, (2000, 500), SIDE, LEFT)
    assert x == 100, "wider than the view: at its left edge, not off the screen"


def test_a_window_taller_than_the_room_under_the_header_stays_inside_the_view():
    _x, top = P.first_place(VIEW, (400, 880), SIDE, LEFT)
    assert top - 880 >= 50 and top <= 50 + 900
    _x, top = P.first_place(VIEW, (400, 1200), SIDE, LEFT)
    assert top == 50 + 900, "taller than the view: its top at the view's top"


def test_ui_scale_scales_the_gaps():
    x1, t1 = P.first_place(VIEW, (400, 500), SIDE, LEFT, 1, scale=2.0)
    x0, t0 = P.first_place(VIEW, (400, 500), SIDE, LEFT, 0, scale=2.0)
    assert x0 - x1 == 2 * P.STEP and t0 - t1 == 2 * P.STEP


@pytest.mark.parametrize("win, at, want", [
    ((10, 700, 400, 500), (10, 1200), (0, 0)),           # already there
    ((10, 700, 400, 500), (60, 1200), (50, 0)),          # 50 px right
    ((10, 700, 400, 500), (10, 1100), (0, 100)),         # Blender's top 100 px lower = the screen's top 100 px lower
])
def test_moved_turns_blenders_place_into_the_outer_rectangle(win, at, want):
    outer = (2, 300, 418, 840)                           # frame and title bar round the client area
    got = P.moved(outer, win, *at)
    assert got == (outer[0] + want[0], outer[1] + want[1], outer[2] + want[0], outer[3] + want[1])
    assert got[2] - got[0] == outer[2] - outer[0] and got[3] - got[1] == outer[3] - outer[1], "same size"
