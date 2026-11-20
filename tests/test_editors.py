"""Blender's right-hand column hidden, Show / Hide in the Fresing menu, a solid side panel (task 0221).

What can run without a window: which areas are the column (plain numbers, measured in Blender 5.2.3's factory layout),
the width of the split, the settings file, the menu entry and its place, the Client view's grey, and that a
background Blender touches neither screens nor preferences. The window itself: tools/ui_test_layout.py."""

import json
import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import editors  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Blender 5.2.3, --factory-startup, a 1920 x 1080 window (measured): (type, x, y, width, height)
FACTORY_1920 = [("PROPERTIES", 1579, 24, 339, 837), ("OUTLINER", 1579, 864, 339, 189),
                ("DOPESHEET_EDITOR", 2, 24, 1574, 74), ("VIEW_3D", 2, 101, 1574, 952)]
# ... after Show: the column split off the 3D view, the timeline below both (measured, 1920 x 1080)
SHOWN_1920 = [("DOPESHEET_EDITOR", 2, 24, 1916, 74), ("VIEW_3D", 2, 101, 1577, 952),
              ("PROPERTIES", 1582, 101, 336, 761), ("OUTLINER", 1582, 865, 336, 188)]


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_the_factory_column_is_found():
    m = editors.main_index(FACTORY_1920)
    assert FACTORY_1920[m][0] == "VIEW_3D"
    assert sorted(editors.column_indices(FACTORY_1920, m)) == [0, 1]
    m = editors.main_index(SHOWN_1920)
    assert sorted(editors.column_indices(SHOWN_1920, m)) == [2, 3]


def test_other_layouts_are_left_alone():
    # an Outliner at the LEFT of the 3D view, a Properties editor below it, an Image editor on the right
    rects = [("OUTLINER", 2, 101, 300, 952), ("VIEW_3D", 305, 101, 1270, 952), ("IMAGE_EDITOR", 1579, 24, 339, 1029),
             ("PROPERTIES", 2, 24, 1916, 74)]
    assert editors.column_indices(rects, editors.main_index(rects)) == []
    # a second, small 3D view right of the main one: not Blender's column
    rects = [("VIEW_3D", 2, 101, 1400, 952), ("VIEW_3D", 1405, 101, 513, 952)]
    assert editors.column_indices(rects, editors.main_index(rects)) == []
    # an Outliner above the main view (a column right of a smaller area only)
    rects = [("VIEW_3D", 2, 24, 1500, 700), ("OUTLINER", 1505, 730, 413, 323), ("DOPESHEET_EDITOR", 2, 730, 1500, 323)]
    assert editors.column_indices(rects, editors.main_index(rects)) == []
    # no 3D view, or one not drawn yet
    assert editors.column_indices([("OUTLINER", 0, 0, 10, 10)], editors.main_index([("OUTLINER", 0, 0, 10, 10)])) == []
    rects = [("VIEW_3D", 0, 0, 0, 0), ("OUTLINER", 0, 0, 0, 0)]
    assert editors.column_indices(rects, editors.main_index(rects)) == []


def test_an_outliner_the_client_view_turned_into_info_counts():
    rects = [("PROPERTIES", 1579, 24, 339, 837), ("INFO", 1579, 864, 339, 189),
             ("DOPESHEET_EDITOR", 2, 24, 1574, 74), ("VIEW_3D", 2, 101, 1574, 952)]
    m = editors.main_index(rects)
    assert editors.column_indices(rects, m) == [0]                 # an Info editor of the user's own stays
    assert sorted(editors.column_indices(rects, m, swapped=(1,))) == [0, 1]


def test_the_split_gives_blenders_default_width():
    for win, view in ((1920, 1916), (2560, 2556), (1800, 1796)):
        f = editors.split_factor(win, view)
        assert abs((1 - f) * view - editors.WIDTH * win) < 1.0
    assert abs(339 / 1920 - editors.WIDTH) < 0.002 and abs(453 / 2560 - editors.WIDTH) < 0.002   # factory, measured
    assert editors.split_factor(1920, 400) == 0.5 and editors.split_factor(1920, 0) == 0.8      # a narrow view


def test_the_choice_file(tmp_path):
    path = str(tmp_path / "Ünïcode folder" / editors.FILE_NAME)
    assert editors.read(path) == {"editors": "hidden", "overlap_off": False}          # a new settings folder: hidden
    editors.write(path, {"editors": "shown", "overlap_off": True})
    assert editors.read(path) == {"editors": "shown", "overlap_off": True}
    for junk in ("", "[1, 2]", "{\"editors\": \"maybe\", \"overlap_off\": 1}", "not json"):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(junk)
        assert editors.read(path) == editors.fresh()
    assert not os.path.exists(path + ".tmp")


def test_the_choice_is_kept_in_blenders_settings_folder(tmp_path, monkeypatch):
    assert os.path.dirname(editors.state_path()) == bpy.utils.user_resource("CONFIG")
    path = str(tmp_path / editors.FILE_NAME)
    monkeypatch.setattr(editors, "state_path", lambda: path)
    assert not editors.chosen_shown()
    editors.choose(True)
    assert editors.chosen_shown() and json.load(open(path, encoding="utf-8"))["editors"] == "shown"
    assert editors.menu_text() == "Hide Blender's editors"
    editors.choose(False)
    assert not editors.chosen_shown() and editors.menu_text() == "Show Blender's editors"


def test_the_menu_entry():
    from fresing_render.blender import lock, ui_topbar
    assert ui_topbar._has("fresing.blender_editors")
    e = ui_topbar.entries()
    assert e.index("fresing.blender_editors") == e.index("fresing.show_panel") + 1      # next to Show the Fresing panel
    assert "fresing.blender_editors" in lock.ALLOWED          # its own poll greys it, with its own reason
    tip = bpy.ops.fresing.blender_editors.get_rna_type().description
    for words in ("Outliner", "Properties", "does not need", "know Blender", "kept"):
        assert words in tip


def test_greyed_in_the_client_view(monkeypatch):
    from fresing_render.blender import lock
    monkeypatch.setattr(lock, "ON", [True])
    assert not editors.FRESING_OT_blender_editors.poll(bpy.context)
    assert editors.FRESING_OT_blender_editors.description(bpy.context, None).startswith(editors.LOCKED_TEXT)
    assert not editors.wanted()
    monkeypatch.setattr(lock, "ON", [False])
    assert editors.FRESING_OT_blender_editors.description(bpy.context, None).startswith("Shows or hides")


def test_a_background_blender_touches_nothing(tmp_path, monkeypatch):
    """Queue, PC check, self-test and the kit run Blender in the background: no screens, no preferences."""
    assert bpy.app.background
    path = str(tmp_path / editors.FILE_NAME)
    monkeypatch.setattr(editors, "state_path", lambda: path)
    before = bpy.context.preferences.system.use_region_overlap
    assert editors.solid_side_panel() is False and editors.solid_side_panel(force=True) is False
    assert editors.apply(True) is True and editors.apply(False) is True and editors.on_load() is True
    editors.request(True)
    assert not bpy.app.timers.is_registered(editors._run_request) and not editors.busy() and editors.settled()
    assert bpy.context.preferences.system.use_region_overlap == before
    assert not os.path.exists(path)


def test_the_app_template_switches_region_overlap_off():
    """Whenever Blender's preferences are reset (and only in the app, not in a background run)."""
    src = open(os.path.join(ROOT, "app_template", "fresing_render", "__init__.py"), encoding="utf-8").read()
    body = src[src.index("def _set_preferences"):src.index("def _enable_fresing_render")]
    assert "use_region_overlap = False" in body and "bpy.app.background" in body


def test_the_layout_follows_on_every_load():
    from fresing_render.blender import ui_header
    src = open(ui_header.__file__, encoding="utf-8").read()
    assert "editors.on_load()" in src and "editors.settled()" in src
    from fresing_render.blender import lock
    assert "editors.request(" in open(lock.__file__, encoding="utf-8").read()
    from fresing_render.blender import ops_setup, ops_tour      # the timers that touch the view after a load wait
    assert "editors.busy()" in open(ops_tour.__file__, encoding="utf-8").read()
    assert "editors.busy()" in open(ops_setup.__file__, encoding="utf-8").read()


def test_closing_an_area_keeps_the_client_views_list(monkeypatch):
    from fresing_render.blender import lock

    class Screen(dict):
        pass

    s = Screen({lock.SCREEN_MARK: [1, 3, 4]})
    editors._forget_swapped(s, 3)
    assert s[lock.SCREEN_MARK] == [1, 3]                 # 3 closed, 4 moved down to 3
    editors._forget_swapped(s, 0)
    assert s[lock.SCREEN_MARK] == [0, 2]
    editors._forget_swapped(s, 0)
    editors._forget_swapped(s, 1)
    assert lock.SCREEN_MARK not in s
