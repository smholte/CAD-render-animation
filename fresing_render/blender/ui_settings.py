"""The Fresing Settings window's panel (task 0271): a row of tabs along the top, one page of settings under it.

The window itself is ops_settings.py (made like an output window of Make: ``ops_setup.open_window`` with the screen
mark ``fr_settings``); its side panel shows the tab "Settings", where ``FRESING_PT_settings_window`` draws.

**The pages** are ``TABS`` in order: (key, title, icon, draw function). The properties stay where they always were
(``prefs.FRESING_AP_prefs``, the usage file's switches on the window manager): only their drawing moved here. A later
task adds its page by putting one entry into ``TABS`` at its place – ``LATER`` names the pages planned (task 0272:
Locations, Exports; task 0273: Materials), so a test can say where they go.
"""

from __future__ import annotations

import bpy

from . import ui
from .ops_setup import SETTINGS_MARK, SETTINGS_TAB

LATER = ("locations", "exports", "materials")     # 0272 puts Locations + Exports after General, 0273 Materials after them


def _prefs():
    from . import prefs
    return prefs.get()


def _no_prefs(layout) -> None:
    layout.label(text="Fresing Render's settings are not there (is the extension switched on?)", icon="ERROR")


def draw_general(layout, context) -> None:
    from . import prefs
    p = _prefs()
    if p is None:
        return _no_prefs(layout)
    prefs.draw_general(layout, p)


def draw_side_panel(layout, context) -> None:
    from . import ops_usage, prefs
    p = _prefs()
    if p is None:
        return _no_prefs(layout)
    layout.label(text="Sections", icon="MENU_PANEL")
    prefs.draw_side_panel(layout, p)
    layout.separator()
    ops_usage.draw_panel_switches(layout, context)


def draw_lessons(layout, context) -> None:
    from . import prefs
    p = _prefs()
    if p is None:
        return _no_prefs(layout)
    prefs.draw_lessons(layout, p)


def draw_backups(layout, context) -> None:
    from . import prefs
    p = _prefs()
    if p is None:
        return _no_prefs(layout)
    prefs.draw_backups(layout, p)


def draw_updates(layout, context) -> None:
    from . import prefs
    p = _prefs()
    if p is None:
        return _no_prefs(layout)
    prefs.draw_updates(layout, p)


def draw_usage(layout, context) -> None:
    from . import ops_usage
    ops_usage.draw_window(layout, context)


def draw_about(layout, context) -> None:
    from . import about
    about.draw_about(layout, width=chars(context))


TABS = (
    ("general", "General", "PREFERENCES", draw_general),
    ("panel", "Side panel", "MENU_PANEL", draw_side_panel),
    ("lessons", "Lessons", "LIGHT", draw_lessons),
    ("backups", "Backups", "FILE_BACKUP", draw_backups),
    ("updates", "Updates", "FILE_REFRESH", draw_updates),
    ("usage", "My usage", "TIME", draw_usage),
    ("about", "About", "INFO", draw_about),
)
KEYS = tuple(t[0] for t in TABS)
DEFAULT = "general"


def tab(key: str):
    """The entry of a tab (key, title, icon, draw), or None."""
    return next((t for t in TABS if t[0] == key), None)


def current() -> str:
    """The tab the window shows: the last one picked (kept in the preferences), else General."""
    p = _prefs()
    key = getattr(p, "settings_tab", "") if p is not None else ""
    return key if key in KEYS else DEFAULT


def chars(context) -> int:
    """About how many characters fit on a line of the window's panel."""
    region = getattr(context, "region", None)
    scale = context.preferences.system.ui_scale or 1.0
    return max(30, int((getattr(region, "width", 300) or 300) / scale / 6.5))


def per_row(width_px: float, scale: float) -> int:
    """How many tab buttons fit on one row of a panel ``width_px`` wide: all of them when the window is wide enough
    (about 86 px each at UI scale 1), else fewer – the tabs then wrap to a second row."""
    each = 86 * (scale or 1.0)
    return max(2, min(len(TABS), int(max(width_px - 20 * (scale or 1.0), 0) // each)))


def draw_tab_row(layout, context, key: str) -> None:
    region = getattr(context, "region", None)
    n = per_row(getattr(region, "width", 600) or 600, context.preferences.system.ui_scale or 1.0)
    col = layout.column(align=True)
    for i, (k, title, icon, _draw) in enumerate(TABS):
        if i % n == 0:
            row = col.row(align=True)
            row.scale_y = 1.2
        row.operator("fresing.settings_tab", text=title, depress=(k == key)).tab = k
    if len(TABS) % n:
        for _ in range(n - len(TABS) % n):
            row.label(text="")


class _Any:
    """A layout stand-in that takes every call (no window in a check)."""

    def __getattr__(self, name):
        return lambda *a, **k: self

    def __setattr__(self, name, value):
        pass


def draw_all(context) -> list:
    """Draw every tab into a stand-in layout (the PC check, the tests); returns the keys of the tabs that drew."""
    out = []
    for key, _title, _icon, draw in TABS:
        try:
            draw(_Any(), context)
        except Exception as exc:  # noqa: BLE001 - the caller says which tab failed
            print(f"Fresing Render: the settings tab {key} does not draw:", exc)
            continue
        out.append(key)
    return out


class FRESING_PT_settings_window(bpy.types.Panel):
    """Fresing Settings: the tabs along the top, the open page under them (task 0271)."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = SETTINGS_TAB
    bl_label = "Fresing Settings"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        win = getattr(context, "window", None)
        try:
            return bool(win is not None and win.screen.get(SETTINGS_MARK))
        except (AttributeError, ReferenceError):
            return False

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.label(text="Fresing Settings", icon="PREFERENCES")
        right = row.row(align=True)
        right.alignment = "RIGHT"
        right.operator("fresing.settings_close", text="", icon="X", emboss=False)
        key = current()
        draw_tab_row(layout, context, key)
        ui.gap(layout)
        tab(key)[3](layout.column(), context)


CLASSES = (FRESING_PT_settings_window,)
