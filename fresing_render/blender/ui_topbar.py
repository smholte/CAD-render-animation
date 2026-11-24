"""The "Fresing" menu in Blender's top bar (task 0199): the one place to find the app's own things.

It sits after Help. Both drawings of the top bar's left part – Blender's own (Full access) and lock.py's without the
workspace tabs (every other workspace, the Client view) – draw ``TOPBAR_MT_editor_menus``, so one line appended to that
menu shows it everywhere without replacing either drawing. The Help menu keeps its Fresing lines: these are only menu
lines for the same operators.

Task 0279: the Fr mark stands in place of Blender's logo at the very left. Blender's ``TOPBAR_MT_editor_menus.draw``
draws its logo menu first; only that entry of the menu's draw list is swapped (appended functions such as the Fresing
menu stay) for ``_draw_editor_menus``, which runs Blender's own draw through a layout that turns its one
``TOPBAR_MT_blender`` line into the Fr mark's menu – so File, Edit, Render, Window, Help stay Blender's. Blender's logo
menu itself is the "Blender" submenu, unchanged. Unregister puts Blender's draw back.
"""

from __future__ import annotations

import os

import bpy

MENU = "TOPBAR_MT_fresing"
MARK_MENU = "TOPBAR_MT_fresing_mark"
MARK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brand",
                         "fresing-render-mark_reversed_128px.png")
_PREVIEWS: dict = {}
_SWAP: list = []            # [(Blender's own draw, ours)] while swapped
DRAWN = {"mark": 0, "icon": 0, "menu": 0}   # how often the Fr mark was drawn, and with which icon (tests)


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
            _op(layout, "fresing.tour_take", text="Open the Learning hub", icon="VIEW_CAMERA")
        _op(layout, "fresing.learn_lessons", text="Learn…", icon="LIGHT")    # task 0230: View / Show me / Build
        state = welcome.load()
        pending = welcome.core.whats_new_pending(state)
        _op(layout, "fresing.whats_new", text=f"What's new in {welcome.version()}" + ("  •" if pending else ""),
            icon="INFO")
        _op(layout, "fresing.settings", text="Settings…", icon="PREFERENCES")     # task 0271: Fresing Settings
        _op(layout, "fresing.first_setup", text="Set up again…", icon="TOOL_SETTINGS")  # task 0276
        _op(layout, "fresing.show_panel", text="Show the Fresing panel", icon="MENU_PANEL")
        from . import editors                  # task 0221: Blender's Outliner and Properties, hidden by default
        _op(layout, "fresing.blender_editors", text=editors.menu_text(), icon="PROPERTIES")
        from . import quiet                    # task 0241: Full access in one click, and back
        _op(layout, "fresing.blender_all", text=quiet.menu_text(context.scene), icon="BLENDER")
        layout.separator()
        ops_demo.draw_help(layout)
        if _has("fresing.user_guide"):
            _op(layout, "fresing.user_guide", text="User guide", icon="HELP")
        layout.menu("TOPBAR_MT_fresing_tools", icon="TOOL_SETTINGS")    # task 0212: self-test, PC check, app folder
        _op(layout, "fresing.update_check", text="Check for updates", icon="FILE_REFRESH")
        _op(layout, "fresing.backups_window", text="Restore a backup…", icon="FILE_BACKUP")   # task 0246
        _op(layout, "fresing.usage_window", text="My usage…", icon="TIME")
        _op(layout, "fresing.learn_window", text="My learning list…", icon="BOOKMARKS")
        layout.separator()
        _op(layout, "fresing.welcome", text="Welcome screen…", icon="HEART")
        _op(layout, "fresing.about", text="About Fresing Render…", icon="INFO")


def _draw_in_editor_menus(self, context):
    self.layout.menu(MENU)
    from . import ui_lead_motions                  # task 0309: the Lead motions drop-down, right of the Fresing menu
    ui_lead_motions.draw_button(self.layout, context)
    from . import ui_measure                       # task 0322: the Measure drop-down, right of Lead motions
    ui_measure.draw_button(self.layout, context)


def mark_icon() -> int:
    """The icon number of the Fr mark (a preview of the reversed mark that reads on the dark top bar); 0 if missing."""
    try:
        coll = _PREVIEWS.get("mark")
        if coll is None:
            from bpy.utils import previews
            coll = previews.new()
            if os.path.isfile(MARK_FILE):
                coll.load("mark", MARK_FILE, "IMAGE")
            _PREVIEWS["mark"] = coll
        return coll["mark"].icon_id if "mark" in coll else 0
    except Exception:  # noqa: BLE001
        return 0


class TOPBAR_MT_fresing_mark(bpy.types.Menu):
    """Fresing Render"""

    bl_label = "Fresing Render"
    bl_idname = MARK_MENU
    bl_description = "Fresing Render: About, Fresing Settings, and Blender's own menu"

    def draw(self, context):
        DRAWN["menu"] += 1
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        _op(layout, "fresing.about", text="About Fresing Render…", icon="INFO")
        _op(layout, "fresing.settings", text="Fresing Settings…", icon="PREFERENCES")
        layout.separator()
        layout.menu("TOPBAR_MT_blender", text="Blender", icon="BLENDER")


class _MarkLayout:
    """Blender's top-bar layout, but its logo-menu line becomes the Fr mark's menu (every other call passes through)."""

    def __init__(self, layout):
        self._layout = layout

    def menu(self, menu, **kw):
        if menu == "TOPBAR_MT_blender":
            if kw.get("text", None) == "":
                icon = mark_icon()
                DRAWN["mark"] += 1
                DRAWN["icon"] = icon
                if icon:
                    return self._layout.menu(MARK_MENU, text="", icon_value=icon)
                return self._layout.menu(MARK_MENU, text="Fr")
            return self._layout.menu(MARK_MENU, text="Fresing Render")
        return self._layout.menu(menu, **kw)

    def __getattr__(self, name):
        return getattr(self._layout, name)


class _Self:
    """``self`` for Blender's draw with the wrapped layout."""

    def __init__(self, real, layout):
        self._real = real
        self.layout = layout

    def __getattr__(self, name):
        return getattr(self._real, name)


def _draw_editor_menus(self, context):
    orig = _SWAP[0][0] if _SWAP else None
    if orig is None:
        return
    orig(_Self(self, _MarkLayout(self.layout)), context)


def _own_index(funcs) -> int:
    return next((i for i, f in enumerate(funcs)
                 if getattr(f, "__qualname__", "") == "TOPBAR_MT_editor_menus.draw"), -1)


def mark_shown() -> bool:
    """Is the Fr mark drawn in place of Blender's logo? (tests, the PC check, the tour)"""
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    return bool(_SWAP) and _SWAP[0][1] in funcs and _own_index(funcs) < 0


def _swap_mark() -> None:
    if _SWAP:
        return
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    i = _own_index(funcs)
    if i < 0:
        print("Fresing Render: Blender's top-bar draw not found; its logo stays")
        return
    _SWAP.append((funcs[i], _draw_editor_menus))
    funcs[i] = _draw_editor_menus
    _redraw()


def _unswap_mark() -> None:
    if not _SWAP:
        return
    orig, ours = _SWAP.pop()
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    for i, f in enumerate(funcs):
        if f is ours:
            funcs[i] = orig
    _redraw()


def _redraw() -> None:
    try:
        from . import lock
        lock._topbar_redraw()
    except Exception:  # noqa: BLE001
        pass


CLASSES = (TOPBAR_MT_fresing, TOPBAR_MT_fresing_mark)


def register_handlers() -> None:
    menu = bpy.types.TOPBAR_MT_editor_menus
    menu.remove(_draw_in_editor_menus)
    menu.append(_draw_in_editor_menus)
    _swap_mark()                                  # task 0279: the Fr mark in place of Blender's logo


def unregister_handlers() -> None:
    bpy.types.TOPBAR_MT_editor_menus.remove(_draw_in_editor_menus)
    _unswap_mark()
    coll = _PREVIEWS.pop("mark", None)
    if coll is not None:
        from bpy.utils import previews
        previews.remove(coll)


def mark_entries() -> list:
    """The Fr mark menu's lines in order (tests, the PC check)."""
    return ["fresing.about", "fresing.settings", "TOPBAR_MT_blender"]


def entries() -> list:
    """The menu's operator ids in order (tests, the PC check)."""
    return ["fresing.tour_take", "fresing.learn_lessons", "fresing.whats_new", "fresing.settings", "fresing.first_setup", "fresing.show_panel", "fresing.blender_editors", "fresing.blender_all",
            "fresing.demo_make", "fresing.user_guide",
            "fresing.self_test", "fresing.pc_check", "fresing.open_app_folder", "fresing.update_check", "fresing.backups_window", "fresing.usage_window", "fresing.learn_window", "fresing.welcome",
            "fresing.about"]

