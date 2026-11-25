"""The Fresing Settings window's panel (task 0271): a row of tabs along the top, one page of settings under it.

The window itself is ops_settings.py (made like an output window of Make: ``ops_setup.open_window`` with the screen
mark ``fr_settings``); ``FRESING_PT_settings_window`` draws in the window's **toolbar region** – the region of 0260's
left panel –, made as wide as the window, with the side panel, header, overlays and Blender's tool buttons off there
(the owner's check of 21 Nov: no tabs, no 3D view, no headers – a side panel always draws a tab strip, even for one
panel).

**The pages** are ``TABS`` in order: (key, title, icon, draw function). The properties stay where they always were
(``prefs.FRESING_AP_prefs``, the usage file's switches on the window manager): only their drawing moved here. A later
task adds its page by putting one entry into ``TABS`` at its place – ``LATER`` names the pages planned (task 0272:
Locations, Exports; task 0273: Materials), so a test can say where they go.
"""

from __future__ import annotations

import bpy

from . import ui
from .ops_setup import SETTINGS_MARK

LATER = ()                 # (0273 put Materials after Locations + Exports)


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
    layout.separator()
    from . import gpu_choice
    gpu_choice.draw_settings(layout)                # task 0296: which GPU draws, which renders


def draw_locations(layout, context) -> None:
    from . import ui_locations
    ui_locations.draw_locations(layout, context)


def draw_exports(layout, context) -> None:
    from . import ui_locations
    ui_locations.draw_exports(layout, context)


def draw_materials(layout, context) -> None:
    """Task 0273: where own materials are kept, what the Materials folders hold, the ones that cannot be used."""
    from . import locations
    from . import material_picker as MP
    layout.operator("fresing.materials", text="Open the Materials window", icon="MATERIAL")
    layout.separator()
    path = locations.save_folder(MP.KIND, make=False)
    ui.wrap(layout, context, ("Save as my material… saves into: " + path) if path
            else locations.no_folder_text(MP.KIND), icon="FILE_FOLDER" if path else "ERROR")
    own = MP.own_entries()
    counts: dict = {}
    for e in own:
        counts[e.badge] = counts.get(e.badge, 0) + 1
    for badge, n in sorted(counts.items()):
        layout.label(text=f"{badge}: {ui.plural(n, 'material')}", icon="FILE_FOLDER")
    if not own:
        ui.hint(layout, context, "No materials of your own yet. A material is a folder with material.json and a "
                                 "picture: copy one into a Materials folder to share it")
    broken = [e for e in own if not e.ok]
    for e in broken[:8]:
        ui.wrap(layout, context, f"{e.name}: {'; '.join(e.problems)}", icon="ERROR")
    layout.separator()
    ui.hint(layout, context, "More Materials folders (your company's, your department's): the Locations tab")
    layout.operator("fresing.mat_refresh", text="Look in the folders again", icon="FILE_REFRESH")


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


def draw_keys(layout, context) -> None:
    """Task 0295: every key of the app, Fresing's own changeable, the key sheet."""
    from . import keys
    keys.draw(layout, context)


def draw_about(layout, context) -> None:
    from . import about
    about.draw_about(layout, width=chars(context))


TABS = (
    ("general", "General", "PREFERENCES", draw_general),
    ("locations", "Locations", "FILE_FOLDER", draw_locations),       # task 0272
    ("exports", "Exports", "EXPORT", draw_exports),                  # task 0272
    ("materials", "Materials", "MATERIAL", draw_materials),          # task 0273
    ("panel", "Side panel", "MENU_PANEL", draw_side_panel),
    ("keys", "Keys", "KEYINGSET", draw_keys),                         # task 0295
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

    def __iter__(self):                    # ``header, body = layout.panel(...)`` (the folds of Locations)
        return iter((self, self))


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


REGION = "TOOLS"           # the page sits in the 3D view's toolbar region: Blender draws no tab strip there


class FRESING_PT_settings_window(bpy.types.Panel):
    """Fresing Settings: the tabs along the top, the open page under them (task 0271)."""
    bl_space_type = "VIEW_3D"
    bl_region_type = REGION
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
