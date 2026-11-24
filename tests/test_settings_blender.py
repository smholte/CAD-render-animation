"""Fresing Settings (task 0271): the window's tabs, the ways in, the preferences kept, and My usage counting only the
user's own input (no time while the app plays or renders by itself)."""

import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import usage as U  # noqa: E402

# the add-on preferences of 0.2.198 (the version before Fresing Settings) with their defaults: an update keeps every
# one of them, so the values saved in a user's preferences come back
PREFS_0_2_198 = {
    "library_path": "", "default_template": "", "default_rule_set": "Standard", "check_updates": True,
    "default_workspace": "All functions", "keep_sections": False, "keep_howto": False, "knows_ctrl_click": False,
    "lesson_button": "C", "lesson_section": "5", "lesson_part": "3", "lesson_play_on": False,
    "lesson_colour": (0.278, 0.608, 0.161), "hover_highlight": True, "lifting_understood": False, "backups_on": True,
    "backup_minutes": 5, "backup_keep": 5, "backup_days": 7, "left_folded": False, "left_width": 240,
    "next_folded": False, "make_open": False, "live_preview": False,
}


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("settings")
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_USAGE_FILE"] = str(d / U.FILE_NAME)
    os.environ[U.TEST_ENV] = "1"
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:                        # the preferences exist only for an enabled add-on: make its entry
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()
    for k in ("FRESING_WORKSPACES_DIR", "FRESING_USAGE_FILE", U.TEST_ENV):
        os.environ.pop(k, None)


@pytest.fixture()
def usage():
    from fresing_render.blender import usage as mod
    path = os.environ["FRESING_USAGE_FILE"]
    if os.path.exists(path):
        os.remove(path)
    mod.forget()
    bpy.ops.wm.read_homefile(use_empty=True)
    yield mod
    mod.forget()


def test_the_tabs_in_order_with_room_for_locations_exports_and_materials():
    from fresing_render.blender import ui_settings
    assert [t[1] for t in ui_settings.TABS] == ["General", "Locations", "Exports", "Side panel", "Lessons", "Backups",
                                               "Updates", "My usage", "About"]      # task 0272: Locations, Exports
    assert ui_settings.LATER == ("materials",)                                  # task 0273 adds this page
    assert not set(ui_settings.LATER) & set(ui_settings.KEYS)
    assert ui_settings.DEFAULT in ui_settings.KEYS


def test_every_tab_draws(usage):
    from fresing_render.blender import ui_settings
    assert ui_settings.draw_all(bpy.context) == list(ui_settings.KEYS)


def test_the_tab_row_wraps_only_when_narrow():
    from fresing_render.blender import ui_settings
    n = len(ui_settings.TABS)
    assert ui_settings.per_row(1000, 1.0) == n
    assert ui_settings.per_row(300, 1.0) < n
    assert ui_settings.per_row(300, 2.0) < ui_settings.per_row(300, 1.0)
    assert ui_settings.per_row(10, 1.0) == 2


def test_a_tab_is_kept_and_a_wrong_one_refused():
    from fresing_render.blender import prefs, ui_settings
    p = prefs.get()
    was = p.settings_tab
    try:
        assert bpy.ops.fresing.settings_tab(tab="lessons") == {"FINISHED"}
        assert p.settings_tab == "lessons" and ui_settings.current() == "lessons"
        with pytest.raises(RuntimeError):
            bpy.ops.fresing.settings_tab(tab="nothing")
        assert ui_settings.current() == "lessons"
        p.settings_tab = "gone"                  # a page a later version dropped: General
        assert ui_settings.current() == "general"
    finally:
        p.settings_tab = was


def test_the_ways_in():
    from fresing_render.blender import lock, ui_topbar
    assert "fresing.settings" in ui_topbar.entries()
    assert ui_topbar.entries().index("fresing.settings") < ui_topbar.entries().index("fresing.show_panel")
    for idname in ("fresing.settings", "fresing.settings_tab", "fresing.settings_close", "fresing.presence"):
        assert lock.allowed(idname), idname                 # the Client view opens the window
    # a background run cannot open a window: it says so, nothing else happens; My usage opens the same window
    assert bpy.ops.fresing.settings(tab="about") == {"CANCELLED"}
    from fresing_render.blender import prefs
    assert prefs.get().settings_tab == "about"
    assert bpy.ops.fresing.usage_window() == {"CANCELLED"}
    assert prefs.get().settings_tab == "usage"
    prefs.get().settings_tab = "general"


def test_the_add_ons_page_points_to_the_window():
    from fresing_render.blender import prefs

    class Rec:
        def __init__(self):
            self.ops, self.props = [], []

        def __getattr__(self, name):
            if name == "operator":
                return lambda op, **k: (self.ops.append(op), self)[1]
            if name == "prop":
                return lambda data, prop, **k: (self.props.append(prop), self)[1]
            return lambda *a, **k: self

        def __setattr__(self, name, value):
            if name in ("ops", "props"):
                object.__setattr__(self, name, value)

    rec = Rec()
    p = prefs.get()
    prefs.FRESING_AP_prefs.draw(type("P", (), {"layout": rec})(), bpy.context)
    assert rec.ops == ["fresing.settings"] and rec.props == []


def test_the_preferences_of_0_2_198_are_all_still_there_with_their_defaults():
    from fresing_render.blender import prefs
    props = prefs.FRESING_AP_prefs.bl_rna.properties
    for name, default in PREFS_0_2_198.items():
        assert name in props, name
        d = props[name]
        got = tuple(d.default_array) if getattr(d, "is_array", False) else d.default
        if isinstance(default, tuple):
            assert got == pytest.approx(default, abs=1e-6), name
        elif name == "default_workspace":     # task 0294: '' = not chosen (Essentials); an existing user is moved
            assert got == "", name           # to All functions once at the start (workspaces.keep_for_existing_user)
        else:
            assert got == default, name
    # values a user had saved keep their meaning: set, read back through the same names
    p = prefs.get()
    p.backup_minutes, p.lesson_part, p.keep_sections = 12, "1", True
    assert (p.backup_minutes, p.lesson_part, p.keep_sections) == (12, "1", True)
    p.backup_minutes, p.lesson_part, p.keep_sections = 5, "3", False


# ---------------------------------------------------------------------------
# My usage: only the user's own input counts (step 4)
# ---------------------------------------------------------------------------

class FakeTime:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_playback_with_no_input_adds_no_time(usage, monkeypatch):
    clock = FakeTime()
    monkeypatch.setattr(time, "monotonic", clock)
    scene = bpy.context.scene
    ob = bpy.data.objects.new("Moving", None)
    scene.collection.objects.link(ob)
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 5.0
    ob.keyframe_insert("location", frame=250)
    try:
        usage.record("fresing.render")               # the user clicks Render image, then walks away
        stage = usage.CLOCK.stage
        assert stage
        for i in range(600):                         # 10 minutes of playback, a frame a second, no input
            clock.t += 1.0
            scene.frame_set(1 + i % 250)
            ob.location.y = i * 0.01                 # … and the app changes the project by itself (a render, a
            usage._on_change(scene, None)            # re-bake, the queue): a change of the project each second
        clock.t += 1.0
        usage.presence("MOUSEMOVE", 10, 10)          # back at the PC
    finally:
        pass
    assert usage.state()["stages"].get(stage, 0.0) == 0.0     # none of it counts as the user


def test_input_every_second_counts(usage, monkeypatch):
    clock = FakeTime()
    monkeypatch.setattr(time, "monotonic", clock)
    usage.record("fresing.render")
    stage = usage.CLOCK.stage
    for i in range(300):                             # 5 minutes of mouse moves
        clock.t += 1.0
        usage.presence("MOUSEMOVE", i, 20)
    assert usage.state()["stages"][stage] == pytest.approx(300.0, abs=1.5)


def test_a_mouse_move_at_the_same_spot_is_not_the_user(usage, monkeypatch):
    clock = FakeTime()
    monkeypatch.setattr(time, "monotonic", clock)
    usage.record("fresing.render")
    stage = usage.CLOCK.stage
    assert usage.presence("MOUSEMOVE", 50, 50)
    for _ in range(300):                             # Blender's own moves: same place, 5 minutes
        clock.t += 1.0
        assert not usage.presence("MOUSEMOVE", 50, 50)
    clock.t += 1.0
    usage.presence("LEFTMOUSE", 50, 50)              # a click after 5 minutes: the user was away
    assert usage.state()["stages"].get(stage, 0.0) == pytest.approx(0.0, abs=1.5)


def test_a_redraw_of_the_favourites_bar_is_not_the_user(usage, monkeypatch):
    from fresing_render.blender import ui_usage
    src = ui_usage.FRESING_PT_favourites.draw.__code__.co_names
    assert "activity" not in src and "presence" not in src
    assert "activity" not in usage._on_change.__code__.co_names


def test_the_presence_keys_pass_every_event_on():
    from fresing_render.blender import ops_settings
    keys = {k for k, _v in ops_settings.PRESENCE_KEYS}
    assert {"MOUSEMOVE", "LEFTMOUSE", "RIGHTMOUSE"} <= keys
    assert "fresing.presence" in U.NOT_COUNTED
    op = ops_settings.FRESING_OT_presence

    class Ev:
        type, mouse_x, mouse_y = "MOUSEMOVE", 3, 4

    assert op.invoke(None, bpy.context, Ev()) == {"PASS_THROUGH"}


def test_blenders_tool_buttons_hide_only_in_the_settings_window():
    """The owner's check of 21 Nov: the window shows only the page. Its region (the 3D view's toolbar) has one panel of
    Blender's, the tool buttons: they get a poll that hides them there and nowhere else."""
    from fresing_render.blender import ops_settings, ui_settings
    assert ui_settings.FRESING_PT_settings_window.bl_region_type == "TOOLS"     # a region without a tab strip
    assert "VIEW3D_PT_tools_active" in ops_settings._QUIET
    cls = bpy.types.VIEW3D_PT_tools_active
    assert cls.is_registered and cls.poll(bpy.context)                          # elsewhere: as before
    assert not ui_settings.FRESING_PT_settings_window.poll(bpy.context)          # the page: only in its window

    class Screen(dict):
        pass

    class Win:
        screen = Screen(fr_settings="settings")

    class Ctx:
        window = Win()

    assert not cls.poll(Ctx())
    assert ui_settings.FRESING_PT_settings_window.poll(Ctx())
