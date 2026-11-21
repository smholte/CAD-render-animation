"""winplace.py (task 0260): the plain-number parts of finding and placing an output window on Windows."""

import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "winplace", os.path.join(os.path.dirname(__file__), "..", "fresing_render", "winplace.py"))
wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp)


def test_a_window_counted_from_the_top_or_from_any_desktop_bottom_matches():
    client = (100, 200, 300, 580)                  # x, y from the top, width, height
    assert wp.matches(client, 100, 200, 300, 580)
    assert wp.matches(client, 100, 1080 - 200 - 580, 300, 580, bottoms=(1080,))
    assert not wp.matches(client, 100, 1080 - 200 - 580, 300, 580, bottoms=(1440,))
    assert not wp.matches(client, 140, 200, 300, 580)            # another place
    assert not wp.matches(client, 100, 200, 320, 580)            # another size
    assert not wp.matches(None, 100, 200, 300, 580)


def test_a_monitor_above_the_main_one_still_finds_the_window():
    # a 1440 px screen beside a 1080 px main screen, bottoms aligned: the virtual screen starts at y = -360
    bs = wp.bottoms(1440, -360, 1080)
    assert set(bs) == {1440, 1080}
    client = (-2000, -300, 300, 580)               # on the taller monitor
    for b in (1440, 1080):                         # whichever height Blender counts from
        assert wp.matches(client, -2000, b - (-300) - 580, 300, 580, bottoms=bs)


def test_usable_rectangles():
    assert wp.usable((0, 0, 300, 580))
    assert not wp.usable((0, 0, 50, 580))          # too narrow to be a window someone placed
    assert not wp.usable((0, 0, 9000, 580))
    assert not wp.usable(("a", 0, 1, 2))
    assert not wp.usable((0, 0, 1))


def test_the_title_bar_points_lie_inside_the_window_top():
    pts = wp.title_points((1913, 100, 2213, 680))  # a window that hangs mostly on a monitor right of the main one
    assert pts == [(1973, 115), (2153, 115)]       # neither lies on a 1920 px main monitor: it is not placed there
    assert all(1913 < x < 2213 and 100 < y < 680 for x, y in pts)


def test_nothing_happens_without_windows():
    if wp.available():
        return
    assert wp.find(object(), "still") == 0
    assert wp.raise_window(object()) is False
    assert wp.rect(object()) is None
    assert wp.place(object(), (0, 0, 300, 580)) is False
