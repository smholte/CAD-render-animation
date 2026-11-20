"""The "Fresing" menu in Blender's top bar (task 0199): the one place to find the app's own things.

It sits after Help. Both drawings of the top bar's left part – Blender's own (Full access) and lock.py's without the
workspace tabs (every other workspace, the Client view) – draw ``TOPBAR_MT_editor_menus``, so one line appended to that
menu shows it everywhere without replacing either drawing. The Help menu keeps its Fresing lines: these are only menu
lines for the same operators.
"""

from __future__ import annotations

import bpy

MENU = "TOPBAR_MT_fresing"


def _has(idname: str) -> bool:
    """Is this operator registered? (``bpy.ops`` makes a wrapper for any name; its type says.)"""
    area, _, name = idname.partition(".")
    try:
        getattr(getattr(bpy.ops, area), name).get_rna_type()
        return True
    except (AttributeError, KeyError, RuntimeError):
        return False


def _op(layout, idname: str, **kw):
    """An operator line; a line whose operator is not there (the user guide without the app template) is left out."""
    try:
        return layout.operator(idname, **kw)
    except Exception:  # noqa: BLE001
        return None


class TOPBAR_MT_fresing(bpy.types.Menu):
    bl_label = "Fresing"
    bl_idname = MENU

    def draw(self, context):
        from . import ops_demo, ops_tour, welcome
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        text = ops_tour.progress_text()
        if text:
            layout.label(text=text, icon="TIME")
            _op(layout, "fresing.tour_cancel", icon="CANCEL")
        else:
            _op(layout, "fresing.tour_take", text="Take the test tour", icon="VIEW_CAMERA")
        _op(layout, "fresing.learn_lessons", text="Learn…", icon="LIGHT")    # task 0230: View / Show me / Build        state = welcome.load()
        pending = welcome.core.whats_new_pending(state)
        _op(layout, "fresing.whats_new", text=f"What's new in {welcome.version()}" + ("  •" if pending else ""),
            icon="INFO")
        _op(layout, "fresing.show_panel", text="Show the Fresing panel", icon="PREFERENCES")
        from . import editors                  # task 0221: Blender's Outliner and Properties, hidden by default
        _op(layout, "fresing.blender_editors", text=editors.menu_text(), icon="PROPERTIES")
        layout.separator()
        ops_demo.draw_help(layout)
        if _has("fresing.user_guide"):
            _op(layout, "fresing.user_guide", text="User guide", icon="HELP")
        layout.menu("TOPBAR_MT_fresing_tools", icon="TOOL_SETTINGS")    # task 0212: self-test, PC check, app folder
        _op(layout, "fresing.update_check", text="Check for updates", icon="FILE_REFRESH")
        _op(layout, "fresing.usage_window", text="My usage…", icon="TIME")
        _op(layout, "fresing.learn_window", text="My learning list…", icon="BOOKMARKS")
        layout.separator()
        _op(layout, "fresing.welcome", text="Welcome screen…", icon="HEART")
        _op(layout, "fresing.about", text="About Fresing Render…", icon="INFO")


def _draw_in_editor_menus(self, context):
    self.layout.menu(MENU)


CLASSES = (TOPBAR_MT_fresing,)


def register_handlers() -> None:
    menu = bpy.types.TOPBAR_MT_editor_menus
    menu.remove(_draw_in_editor_menus)
    menu.append(_draw_in_editor_menus)


def unregister_handlers() -> None:
    bpy.types.TOPBAR_MT_editor_menus.remove(_draw_in_editor_menus)


def entries() -> list:
    """The menu's operator ids in order (tests, the PC check)."""
    return ["fresing.tour_take", "fresing.learn_lessons", "fresing.whats_new", "fresing.show_panel", "fresing.blender_editors", "fresing.demo_make", "fresing.user_guide",
            "fresing.self_test", "fresing.pc_check", "fresing.open_app_folder", "fresing.update_check", "fresing.usage_window", "fresing.learn_window", "fresing.welcome",
            "fresing.about"]

