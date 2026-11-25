"""Task 0367 (study 0222 package C): shorter top-bar menus and Blender's side-panel tabs hidden outside Full access.

File / Render / Window hold what the app uses; Help keeps Fresing's lines and Blender's in one sub-menu "Blender" at
the bottom; the glTF Variants tab joins the hidden tabs, another add-on's tab stays; Blender's Transform panel (tab
Item, C code) is hidden through its poll – the write logic is tested here on a stand-in struct, the walk through
Blender's real panel types in the window by tools/ui_test_menus.py; the Keys tab's Blender button is greyed in the
Client view."""

import ctypes
from types import SimpleNamespace

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import keys, ops_settings, panels, project_name, quiet, workspaces  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


def _ctx(**kw):
    base = dict(screen=SimpleNamespace(show_statusbar=True), scene=bpy.context.scene)
    base.update(kw)
    return SimpleNamespace(**base)


# --- the menus -----------------------------------------------------------------------------------------------------

def test_the_quiet_file_menu_keeps_open_save_import_quit_only():
    seen = quiet.lines(quiet._file, _ctx())
    assert seen == list(quiet.FILE_KEEPS)
    assert not set(seen) & set(quiet.FILE_DROPS)
    assert "fresing.save" in seen and "fresing.save_as" in seen        # task 0291's Save / Save As stay the app's
    assert "fresing.import_step" in seen and "fresing.import_mesh" in seen


def test_the_quiet_render_menu_is_the_apps():
    seen = quiet.lines(quiet._render, _ctx())
    assert seen == list(quiet.RENDER_KEEPS)
    assert "render.render" not in seen


def test_the_quiet_window_menu_has_no_new_windows_or_workspace_cycle():
    seen = quiet.lines(quiet._window, _ctx())
    assert seen == list(quiet.WINDOW_KEEPS)
    assert "screen.workspace_cycle" not in seen and "wm.window_new" not in seen
    assert quiet.lines(quiet._window, _ctx(screen=None)) == ["wm.window_fullscreen_toggle", "screen.screenshot"]


def test_blenders_own_menus_are_found_to_swap():
    for cls in (bpy.types.TOPBAR_MT_render, bpy.types.TOPBAR_MT_window, bpy.types.TOPBAR_MT_help):
        assert quiet._own(cls, quiet.draw_funcs(cls)) >= 0, cls.__name__
    swapped = {c.__name__ for c, _fn in quiet._classes() if c is not None}
    assert {"TOPBAR_MT_file", "TOPBAR_MT_render", "TOPBAR_MT_window", "TOPBAR_MT_help"} <= swapped


def test_the_file_menu_asks_the_quiet_window_first():
    """project_name.py swaps Blender's File entry (task 0291); while quiet it draws the quiet File menu."""
    me = SimpleNamespace(layout=quiet._Rec())
    was = quiet.ON[0]
    try:
        quiet.ON[0] = True
        n = quiet.DRAWN["file"]
        project_name.file_menu_draw(me, _ctx())
        assert quiet.DRAWN["file"] == n + 1
        assert me.layout.seen == list(quiet.FILE_KEEPS)
        quiet.ON[0] = False                                   # Full access: Blender's own, Save / Save As the app's
        me = SimpleNamespace(layout=quiet._Rec())
        assert quiet.file_menu(me, _ctx()) is False
    finally:
        quiet.ON[0] = was


def test_the_quiet_help_draws_none_of_blenders_lines_and_the_submenu_holds_them():
    assert quiet.lines(quiet._help) == []
    menu = getattr(bpy.types, quiet.HELP_MENU)
    seen = quiet.lines(menu.draw)
    assert "wm.sysinfo" in seen and "wm.url_open_preset" in seen and "wm.url_open" in seen


def test_the_blender_submenu_line_stays_last_and_goes_in_full_access():
    help_cls = bpy.types.TOPBAR_MT_help

    def late_addon(self, context):                           # an add-on appending after the app
        pass
    help_cls.append(late_addon)
    try:
        quiet._help_line(True)
        funcs = help_cls._dyn_ui_initialize()
        assert funcs[-1] is quiet._help_blender_line and late_addon in funcs
        quiet._help_line(True)                                # again: still once
        assert help_cls._dyn_ui_initialize().count(quiet._help_blender_line) == 1
        quiet._help_line(False)
        assert quiet._help_blender_line not in help_cls._dyn_ui_initialize()
        assert late_addon in help_cls._dyn_ui_initialize()
    finally:
        help_cls.remove(late_addon)
        quiet._help_line(False)


def test_swapping_help_keeps_fresings_lines():
    help_cls = bpy.types.TOPBAR_MT_help
    before = list(help_cls._dyn_ui_initialize())
    try:
        assert quiet.swap(help_cls, quiet._help)
        after = help_cls._dyn_ui_initialize()
        assert len(after) == len(before) and quiet._help in after
        assert [f for f in after if f is not quiet._help] == [f for f in before if f is not quiet.blender_draw(help_cls)]
    finally:
        quiet.unswap(help_cls)
    assert help_cls._dyn_ui_initialize() == before


# --- the side panel's tabs -------------------------------------------------------------------------------------------

def test_gltf_variants_joins_the_hidden_tabs_and_another_addons_tab_stays():
    assert {"Item", "Tool", "View", "Animation", "glTF Variants"} <= set(ops_settings.QUIET_TABS)

    class FR_TEST_PT_other_tab(bpy.types.Panel):
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Other add-on"
        bl_label = "Other"

        def draw(self, context):
            pass

    class FR_TEST_PT_gltf_like(bpy.types.Panel):
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "glTF Variants"
        bl_label = "Variants"

        def draw(self, context):
            pass

    bpy.utils.register_class(FR_TEST_PT_other_tab)
    bpy.utils.register_class(FR_TEST_PT_gltf_like)
    try:
        names = [c.__name__ for c in ops_settings.tab_panels()]
        assert "FR_TEST_PT_gltf_like" in names and "FR_TEST_PT_other_tab" not in names
        ops_settings.quiet_panels()                          # what quiet.apply runs: late panels too
        assert "FR_TEST_PT_gltf_like" in ops_settings._QUIET
        main = SimpleNamespace(window=None, mode="OBJECT")
        was = quiet.ON[0]
        try:
            quiet.ON[0] = True
            assert FR_TEST_PT_gltf_like.poll(main) is False
            assert "FR_TEST_PT_other_tab" not in ops_settings._QUIET
            quiet.ON[0] = False
            assert FR_TEST_PT_gltf_like.poll(main) is True
        finally:
            quiet.ON[0] = was
    finally:
        entry = ops_settings._QUIET.pop("FR_TEST_PT_gltf_like", None)
        for cls in (FR_TEST_PT_other_tab, FR_TEST_PT_gltf_like):
            if getattr(cls, "is_registered", False):
                bpy.utils.unregister_class(cls)
        assert entry is not None


class _FakeType(ctypes.Structure):
    _fields_ = [("raw", ctypes.c_char * 800)]


def test_the_transform_panels_poll_is_swapped_and_put_back():
    fake = _FakeType()
    addr = ctypes.addressof(fake)
    slot = ctypes.c_void_p.from_address(addr + panels.C_OFF["poll"])
    slot.value = 0x1000
    keep = dict(panels.C_PANEL)
    try:
        panels.C_PANEL.update(transform=addr, own=0x1000, other=0x2000, hidden=False)
        assert panels.hide_c_panels(True) and slot.value == 0x2000 and panels.c_panels_hidden()
        assert panels.hide_c_panels(True) and slot.value == 0x2000          # again: the same
        assert panels.hide_c_panels(False) and slot.value == 0x1000 and not panels.c_panels_hidden()
        slot.value = 0x3000                                                  # someone else changed it: left alone
        assert not panels.hide_c_panels(True) and slot.value == 0x3000
    finally:
        panels.C_PANEL.clear()
        panels.C_PANEL.update(keep)


def test_nothing_is_written_while_the_panel_type_is_not_found():
    keep = dict(panels.C_PANEL)
    try:
        panels.C_PANEL.update(transform=0, own=0, other=0, hidden=False, want=None)
        assert panels.hide_c_panels(True) is False
        assert panels.C_PANEL["want"] is True and not panels.c_panels_hidden()
    finally:
        panels.C_PANEL.clear()
        panels.C_PANEL.update(keep)


def test_the_search_refuses_what_does_not_match():
    """No address, the left panel's region, a panel whose type reads wrong: None, nothing touched."""
    cls = SimpleNamespace(bl_region_type="UI", bl_idname="FRESING_PT_x", __name__="FRESING_PT_x")
    assert panels._find_c_panels(0, cls) is None
    assert panels._find_c_panels(1234, SimpleNamespace(bl_region_type="TOOLS")) is None
    fake = _FakeType()                                       # a "Panel" whose type pointer points at a wrong name
    other = _FakeType()
    ctypes.c_void_p.from_address(ctypes.addressof(fake) + panels.C_OFF["panel_type"]).value = ctypes.addressof(other)
    ctypes.memmove(ctypes.addressof(other) + panels.C_OFF["idname"], b"SOMETHING_ELSE\0", 15)
    assert panels._find_c_panels(ctypes.addressof(fake), cls) is None


# --- the Keys tab's Blender button ---------------------------------------------------------------------------------

def test_blenders_key_settings_are_greyed_in_the_client_view():
    scene = bpy.context.scene
    before = workspaces.name_of(scene)
    try:
        workspaces.switch(scene, "Client view")
        assert keys.client_view(bpy.context)
        assert not bpy.ops.fresing.keys_blender.poll()
        assert keys.FRESING_OT_keys_blender.description(bpy.context, None).startswith(keys.CLIENT_TEXT)
        workspaces.switch(scene, "Full access")
        assert bpy.ops.fresing.keys_blender.poll()
        assert not keys.FRESING_OT_keys_blender.description(bpy.context, None).startswith(keys.CLIENT_TEXT)
    finally:
        workspaces.switch(scene, "Full access")
        workspaces.switch(scene, before if before != "Client view" else "All functions")
