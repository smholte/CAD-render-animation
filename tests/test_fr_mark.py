"""Task 0279: the Fr mark stands in place of Blender's logo at the left of the top bar, with its own menu."""

from __future__ import annotations

import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import ui_topbar  # noqa: E402


class _Rec:
    def __init__(self):
        self.calls = []
        self.operator_context = ""

    def menu(self, menu, **kw):
        self.calls.append(("menu", menu, kw))

    def operator(self, idname, **kw):
        self.calls.append(("op", idname, kw))

    def separator(self, **kw):
        self.calls.append(("sep",))

    def popover(self, panel="", **kw):                 # task 0309: Lead motions, right of the Fresing menu
        self.calls.append(("popover", panel, kw))


class _Area:
    show_menus = True


class _Ctx:
    area = _Area()


def _draw_top(ctx=None):
    rec = _Rec()
    self = type("M", (), {"layout": rec})()
    for f in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize():
        f(self, ctx or _Ctx())
    return rec.calls


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_the_mark_picture_ships_inside_the_extension():
    assert os.path.isfile(ui_topbar.MARK_FILE)


def test_the_first_item_is_the_fr_mark_and_the_rest_stay_blenders():
    assert ui_topbar.mark_shown()
    calls = _draw_top()
    menus = [c[1] for c in calls if c[0] == "menu"]
    assert menus[0] == ui_topbar.MARK_MENU and calls[0][2].get("text") in ("", "Fr")   # "Fr" only where no preview loads
    assert menus[1:] == ["TOPBAR_MT_file", "TOPBAR_MT_edit", "TOPBAR_MT_render", "TOPBAR_MT_window",
                         "TOPBAR_MT_help", ui_topbar.MENU]
    assert "TOPBAR_MT_blender" not in menus
    i = next(k for k, c in enumerate(calls) if c[0] == "menu" and c[1] == ui_topbar.MENU)
    assert calls[i + 1][:2] == ("popover", "TOPBAR_PT_fresing_lead")      # task 0309: Lead motions right after it


def test_without_header_menus_the_mark_menu_has_a_name():
    class A:
        show_menus = False

    class C:
        area = A()
    calls = _draw_top(C())
    assert calls[0][1] == ui_topbar.MARK_MENU and calls[0][2]["text"] == "Fresing Render"


def test_the_mark_menu_lines():
    rec = _Rec()
    self = type("M", (), {"layout": rec})()
    ui_topbar.TOPBAR_MT_fresing_mark.draw(self, None)
    ids = [c[1] for c in rec.calls if c[0] in ("op", "menu")]
    assert ids == ui_topbar.mark_entries() == ["fresing.about", "fresing.settings", "TOPBAR_MT_blender"]
    texts = [c[2].get("text") for c in rec.calls if c[0] in ("op", "menu")]
    assert texts == ["About Fresing Render…", "Fresing Settings…", "Blender"]
    assert ("sep",) in rec.calls
    for idname in ("fresing.about", "fresing.settings"):
        area, name = idname.split(".")
        assert getattr(getattr(bpy.ops, area), name).get_rna_type().description


def test_turned_off_gives_blenders_logo_back_and_on_again_the_mark():
    ui_topbar.unregister_handlers()
    try:
        assert not ui_topbar.mark_shown()
        calls = _draw_top()
        assert calls[0][1] == "TOPBAR_MT_blender" and calls[0][2].get("icon") == "BLENDER"
        assert ui_topbar.MENU not in [c[1] for c in calls]
    finally:
        ui_topbar.register_handlers()
    assert ui_topbar.mark_shown()
    ui_topbar.register_handlers()                       # twice: still one swap
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    assert funcs.count(ui_topbar._draw_editor_menus) == 1
