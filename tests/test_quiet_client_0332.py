"""Task 0332 (0328 F3): the quiet window and the Client view lock.

Row 5: Back to the Fresing window puts the main window back on the app's Blender workspace (``quiet.back_workspace``).
Row 7: F2 / Ctrl+F2 / Ctrl+, are swallowed outside Full access (the Client view's message there); the quiet Edit and
F4 menus have no Rename, Batch Rename or Preferences.
Row 13: the image editor's header of a render says what was saved – Open, Show in folder, Close.
Row 27: Blender's side-panel tabs hide in the main window while it is quiet.
Row 28: no redo panel – the workspace operators have no REGISTER; the quiet window switches the 3D views' redo panel off.
The drawing in a window: tools/ui_test_quiet.py."""

from types import SimpleNamespace

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import keys, lock, ops_settings, ops_workspace, quiet, workspaces  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


class _Rec:
    """A layout that writes down what is put in it."""

    def __init__(self, out=None):
        self.out = [] if out is None else out
        self.operator_context = "EXEC_DEFAULT"

    def operator(self, idname, text="", icon="NONE", **_kw):
        self.out.append(("op", idname, text))
        return SimpleNamespace(path="", fit_view=False)

    def menu(self, idname, text="", **_kw):
        self.out.append(("menu", idname, text))

    def prop(self, _data, name, **_kw):
        self.out.append(("prop", name, ""))

    def label(self, text="", icon="NONE"):
        self.out.append(("label", text, icon))

    def separator(self, **_kw):
        pass

    def separator_spacer(self):
        pass

    def row(self, **_kw):
        return _Rec(self.out)


def _drawn(fn, context=None):
    me = SimpleNamespace(layout=_Rec())
    fn(me, context or bpy.context)
    return me.layout.out


# --- row 7: the Client view lock -----------------------------------------------------------------------------------

def test_rename_and_preferences_keys_are_swallowed_outside_full_access():
    keys_ = {(km, lock.key_label(k, m)) for km, _sp, k, m, _w in lock.BLENDER_KEYS}
    assert ("Window", "F2") in keys_ and ("Window", "Ctrl+F2") in keys_ and ("Screen", "Ctrl+,") in keys_
    # the same keymap and key as Blender's own (Window: wm.call_panel / wm.batch_rename; Screen: screen.userpref_show)
    wanted = {(w[0], w[2], tuple(sorted(w[3])), w[4]) for w in lock._wanted()}
    for km, k, mods in (("Window", "F2", ()), ("Window", "F2", ("ctrl",)), ("Screen", "COMMA", ("ctrl",))):
        assert (km, k, mods, "fresing.blender_key") in wanted, (km, k)


def test_the_keys_tab_lists_them_as_everywhere():
    off = {r.key: r for r in keys.off_rows()}
    for k in ("F2", "Ctrl+F2", "Ctrl+,"):
        assert k in off and off[k].where == "everywhere", k
    assert off["Ctrl+,"].what == "Blender's Preferences"


def test_in_the_client_view_rename_and_preferences_get_the_locks_message():
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    workspaces.switch(scene, "Client view")
    try:
        sw = lock.SWALLOWED[0]
        for k in ("F2", "Ctrl+F2", "Ctrl+,"):
            assert bpy.ops.fresing.blender_key(key=k) == {"FINISHED"}
        assert lock.SWALLOWED[0] == sw + 3
    finally:
        workspaces.switch(scene, "Full access")
        workspaces.switch(scene, "All functions")


def test_the_quiet_edit_menu_has_no_rename_and_no_preferences():
    ids = [i for _kind, i, _t in _drawn(quiet._edit)]
    assert ids[:3] == ["ed.undo", "ed.redo", "TOPBAR_MT_undo_history"]
    assert "wm.search_menu" in ids and "fresing.settings" in ids
    for gone in quiet.EDIT_DROPS:
        assert gone not in ids, gone
    assert set(ids) <= set(quiet.EDIT_KEEPS)
    f4 = [i for _kind, i, _t in _drawn(quiet._file_context)]
    assert f4 == ["TOPBAR_MT_file_new", "wm.open_mainfile", "TOPBAR_MT_file_open_recent"]


def test_the_new_swapped_classes_have_blenders_own_draw():
    for cls in (bpy.types.TOPBAR_MT_edit, bpy.types.TOPBAR_MT_file_context_menu, bpy.types.IMAGE_HT_header):
        assert quiet._own(cls, quiet.draw_funcs(cls)) >= 0, cls.__name__
    swapped = {c.__name__ for c, _fn in quiet._classes() if c is not None}
    assert {"TOPBAR_MT_edit", "TOPBAR_MT_file_context_menu", "IMAGE_HT_header"} <= swapped


# --- row 13: the picture after a render ----------------------------------------------------------------------------

def test_the_render_header_speaks_the_apps_words(tmp_path):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.fresing.last_render = ""
    assert quiet.render_words(scene) == ("The rendered picture", "IMAGE", "")
    pic = tmp_path / "crane é.png"
    pic.write_bytes(b"x")
    scene.fresing.last_render = str(pic)
    text, icon, path = quiet.render_words(scene)
    assert text == "Saved: crane é.png" and icon == "CHECKMARK" and path == str(pic)
    img = SimpleNamespace(type="RENDER_RESULT")
    ctx = SimpleNamespace(space_data=SimpleNamespace(image=img, mode="VIEW"), scene=scene)
    out = _drawn(quiet._image_header, ctx)
    ops = [(i, t) for kind, i, t in out if kind == "op"]
    assert ("fresing.open_file", "Open") in ops and ("fresing.show_in_folder", "Show in folder") in ops
    assert ("render.view_cancel", "Close") in ops and ("image.view_all", "Fit") in ops
    assert ("label", "Saved: crane é.png", "CHECKMARK") in out
    assert not any("slot" in str(x).lower() or "layer" in str(x).lower() for x in out)
    # Open / Show in folder / Close's own operators work in the Client view
    assert lock.allowed("fresing.open_file") and lock.allowed("fresing.show_in_folder")


def test_another_image_keeps_blenders_header():
    ctx = SimpleNamespace(space_data=SimpleNamespace(image=SimpleNamespace(type="IMAGE"), mode="VIEW"),
                          scene=bpy.context.scene)
    assert quiet.blender_draw(bpy.types.IMAGE_HT_header) is None      # background: nothing swapped
    assert _drawn(quiet._image_header, ctx) == []


# --- row 5: back to the app's Blender workspace --------------------------------------------------------------------

def test_back_goes_to_the_workspace_full_access_began_in_else_layout():
    bpy.ops.wm.read_homefile()                       # Blender's workspaces: Layout, Animation …
    assert bpy.data.workspaces.get("Layout") is not None
    quiet.LOUD_WS[0] = ""
    assert quiet.back_workspace() == "Layout"
    quiet.LOUD_WS[0] = "Animation"
    assert quiet.back_workspace() == "Animation"
    quiet.LOUD_WS[0] = "Gone"                         # not in this file: the app's own
    assert quiet.back_workspace() == "Layout"
    quiet.LOUD_WS[0] = ""


# --- row 27: Blender's side-panel tabs -----------------------------------------------------------------------------

def test_blenders_tabs_hide_in_the_quiet_main_window():
    props = bpy.types.VIEW3D_PT_view3d_properties
    assert props.__name__ in ops_settings._QUIET
    main = SimpleNamespace(window=None, mode="OBJECT")
    was = quiet.ON[0]
    try:
        quiet.ON[0] = True
        assert props.poll(main) is False
        assert props.poll(SimpleNamespace(window=None, mode="EDIT_MESH")) is True   # another mode: Blender's
        quiet.ON[0] = False                                                          # Full access
        assert props.poll(main) is True
    finally:
        quiet.ON[0] = was
    # Blender's tool buttons keep their own rule (quiet.py draws nothing there in Object Mode)
    tools = bpy.types.VIEW3D_PT_tools_active
    assert tools.__name__ in ops_settings._QUIET


# --- row 28: no redo panel -----------------------------------------------------------------------------------------

def test_the_workspace_buttons_offer_no_redo_panel():
    for cls in (ops_workspace.FRESING_OT_workspace_pick, ops_workspace.FRESING_OT_family_toggle,
                ops_workspace.FRESING_OT_workspace_show_used, ops_workspace.FRESING_OT_workspace_all):
        assert "REGISTER" not in cls.bl_options and "UNDO" in cls.bl_options, cls.__name__


def test_a_workspace_pick_is_still_one_undo_step():
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    workspaces.switch(scene, "All functions")
    assert bpy.ops.fresing.workspace_pick(name="CNC & machining") == {"FINISHED"}
    assert workspaces.name_of(bpy.context.scene) == "CNC & machining"
