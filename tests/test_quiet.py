"""A quiet window (task 0241): Blender's own entry in a draw list swapped for the quiet one, appended / prepended
functions of other add-ons kept in place (also through patch / unpatch / patch), Show all of Blender / Back to the
Fresing window with the workspace it came from, greyed in the Client view, and nothing patched in a background
Blender. The drawing itself in a window: tools/ui_test_quiet.py."""

import json

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import lock, quiet, ui_topbar, workspaces  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture
def menu():
    """A menu of Blender's kind (its own draw) with a prepended and an appended add-on item."""
    class FR_MT_quiet_dummy(bpy.types.Menu):
        bl_label = "Dummy"

        def draw(self, context):
            pass

    bpy.utils.register_class(FR_MT_quiet_dummy)

    def first(self, context):
        pass

    def last(self, context):
        pass

    FR_MT_quiet_dummy.prepend(first)
    FR_MT_quiet_dummy.append(last)
    yield FR_MT_quiet_dummy, first, last
    quiet.unswap(FR_MT_quiet_dummy)
    bpy.utils.unregister_class(FR_MT_quiet_dummy)


def _quiet(self, context):
    pass


def test_only_blenders_own_entry_is_swapped(menu):
    cls, first, last = menu
    funcs = quiet.draw_funcs(cls)
    own = funcs[1]
    assert own.__qualname__.endswith("FR_MT_quiet_dummy.draw")
    assert quiet.swap(cls, _quiet)
    assert quiet.draw_funcs(cls) == [first, _quiet, last]
    assert quiet.blender_draw(cls) is own
    assert quiet.swap(cls, _quiet)                     # twice: nothing more happens
    assert quiet.draw_funcs(cls) == [first, _quiet, last]
    quiet.unswap(cls)
    assert quiet.draw_funcs(cls) == [first, own, last]
    assert quiet.blender_draw(cls) is None


def test_patch_unpatch_patch_keeps_items_added_meanwhile(menu):
    cls, first, last = menu
    own = quiet.draw_funcs(cls)[1]
    quiet.swap(cls, _quiet)

    def later(self, context):                          # an add-on switched on while the window is quiet
        pass

    cls.append(later)
    quiet.unswap(cls)
    assert quiet.draw_funcs(cls) == [first, own, last, later]
    quiet.swap(cls, _quiet)
    assert quiet.draw_funcs(cls) == [first, _quiet, last, later]
    cls.remove(later)
    quiet.unswap(cls)
    assert quiet.draw_funcs(cls) == [first, own, last]


def test_a_class_without_its_own_draw_is_left_alone(menu):
    cls, first, last = menu
    funcs = quiet.draw_funcs(cls)
    own = funcs.pop(1)                                  # some other add-on took Blender's part away
    try:
        assert not quiet.swap(cls, _quiet)
        assert quiet.draw_funcs(cls) == [first, last]
    finally:
        funcs.insert(1, own)


def test_the_real_classes_have_blenders_own_draw_in_their_list():
    for cls in (bpy.types.VIEW3D_HT_header, bpy.types.WM_MT_splash, bpy.types.TOPBAR_MT_file_new):
        funcs = quiet.draw_funcs(cls)
        assert quiet._own(cls, funcs) >= 0, cls.__name__


def test_nothing_is_patched_in_a_background_blender():
    assert bpy.app.background
    assert quiet.apply(True) is False
    assert not quiet.ON[0]
    for cls in (bpy.types.VIEW3D_HT_header, bpy.types.WM_MT_splash, bpy.types.TOPBAR_MT_file_new):
        assert quiet._header not in quiet.draw_funcs(cls)
        assert quiet._splash not in quiet.draw_funcs(cls)
        assert quiet._file_new not in quiet.draw_funcs(cls)
    assert bpy.types.TOPBAR_HT_upper_bar.draw_right is not quiet._draw_right
    lock.blender_ui(False)                              # the workspace switch in the background: still nothing
    assert not quiet.ON[0] and not quiet._SWAPPED and not quiet._PATCHED


def test_the_menu_entry_sits_right_below_blenders_editors():
    e = ui_topbar.entries()
    assert e.index("fresing.blender_all") == e.index("fresing.blender_editors") + 1
    assert not lock.allowed("fresing.blender_all")      # the Client view's lock greys it (and says why)


def test_splash_lines_are_fresings():
    lines = quiet.splash_lines()
    assert lines[:3] == ["wm.read_homefile", "wm.open_mainfile", "wm.recover_last_session"]
    assert "fresing.demo_make" in lines and "fresing.tour_take" in lines


def _scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    workspaces.switch(scene, "CNC & machining")
    return scene


def test_show_all_and_back_to_the_workspace_it_came_from():
    scene = _scene()
    workspaces.set_tick(scene, "offshore", True)
    ticks = scene.fresing.ws_ticks
    assert quiet.menu_text(scene) == quiet.SHOW_TEXT
    assert bpy.ops.fresing.blender_all() == {"FINISHED"}
    assert workspaces.name_of(scene) == "Full access" and workspaces.blender_ui(scene)
    assert json.loads(scene[quiet.KEEP])["name"] == "CNC & machining"
    assert quiet.menu_text(scene) == quiet.BACK_TEXT
    assert bpy.ops.fresing.blender_all() == {"FINISHED"}
    assert workspaces.name_of(scene) == "CNC & machining" and not workspaces.blender_ui(scene)
    assert scene.fresing.ws_ticks == ticks                  # the family ticks of before, too
    assert quiet.KEEP not in scene
    for _ in range(3):                                       # repeatedly
        bpy.ops.fresing.blender_all()
        assert workspaces.name_of(scene) == "Full access"
        bpy.ops.fresing.blender_all()
        assert workspaces.name_of(scene) == "CNC & machining"


def test_back_without_a_remembered_workspace_goes_to_the_default():
    scene = _scene()
    workspaces.switch(scene, "Full access")                  # picked in the panel: nothing remembered
    assert bpy.ops.fresing.blender_all() == {"FINISHED"}
    assert workspaces.name_of(scene) == workspaces.default_name()
    assert not workspaces.blender_ui(scene)


def test_greyed_in_the_client_view_with_the_reason():
    scene = _scene()
    workspaces.switch(scene, "Client view")
    try:
        assert not bpy.ops.fresing.blender_all.poll()
        text = quiet.FRESING_OT_blender_all.description(bpy.context, None)
        assert text.startswith(quiet.LOCKED_TEXT)
    finally:
        workspaces.switch(scene, "Full access")
        workspaces.switch(scene, "All functions")


def test_the_tooltips_say_what_comes_back_and_how_to_go_back():
    scene = _scene()
    doc = quiet.FRESING_OT_blender_all.description(bpy.context, None)
    assert "Full access" in doc and "not" in doc and "Back to the Fresing window" in doc
    bpy.ops.fresing.blender_all()
    back = quiet.FRESING_OT_blender_all.description(bpy.context, None)
    assert back.startswith("Back to the Fresing window") and "not changed" in back
    bpy.ops.fresing.blender_all()
    assert workspaces.name_of(scene) == "CNC & machining"
