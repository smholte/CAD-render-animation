"""Fresing Settings (task 0271): one window with all of the app's own settings, a row of tabs along its top.

**The window** is made like an output window of Make (task 0260): ``ops_setup.open_window`` copies a piece of the main
3D view into a window of its own and marks its screen ``fr_settings``; its side panel shows the tab "Settings", where
``ui_settings.FRESING_PT_settings_window`` draws. It can be dragged anywhere (also onto a second screen) and stays open
while the user works in the main window. Opening it again brings it to the front (Windows) instead of a second one; on
Windows it opens where it was last time and as big (``ops_make`` keeps its place under the key "settings"). The last
tab is kept in the preferences (``prefs.settings_tab``): the window opens on it again, also after a restart.

**Ways in:** Fresing > Settings…, the gear on the left panel, Help / Fresing > My usage… (on the tab My usage), and
Edit > Preferences > Add-ons > Fresing Render > Open Fresing Settings.

**Presence** (task 0271, step 4): ``FRESING_OT_presence`` sits in the add-on keymap "Window" for mouse moves, clicks
and the wheel. It runs only for events no editor handled before it and always passes them on (``PASS_THROUGH``); it
tells the usage tracker that the user is at the app (``usage.presence``). A mouse move counts only when the mouse
really moved – Blender sends moves of its own, at the same spot.

Client view: the window opens (``lock.ALLOWED_PREFIXES`` has ``fresing.settings``); nothing in it is a model change.
"""

from __future__ import annotations

import bpy
from bpy.props import StringProperty

from . import ops_setup, panels, ui_settings
from .ops_setup import SETTINGS_MARK

KEY = "settings"
SIZE = (440, 640)              # the window's side panel, px at UI scale 1 (the Set-up and Make windows: ~280 x 560)


def settings_windows() -> list:
    wm = getattr(bpy.context, "window_manager", None)
    out = []
    for win in (wm.windows if wm is not None else ()):
        try:
            if win.screen.get(SETTINGS_MARK):
                out.append(win)
        except (AttributeError, ReferenceError):
            continue
    return out


def set_tab(key: str) -> bool:
    """Show this tab (kept for the next time the window opens). False for a tab that does not exist."""
    from . import prefs
    if key not in ui_settings.KEYS:
        return False
    p = prefs.get()
    if p is not None and p.settings_tab != key:
        p.settings_tab = key
    ops_setup.redraw_all()
    return True


def open_settings(op, context, tab: str = "") -> set:
    """Open the Settings window (on ``tab`` when given); used by the operators below and by My usage."""
    if tab and not set_tab(tab):
        op.report({"ERROR"}, f"Fresing Settings has no tab '{tab}'")
        return {"CANCELLED"}
    if bpy.app.background:
        op.report({"INFO"}, "Fresing Settings opens only in the app's own window, not in a background run")
        return {"CANCELLED"}
    there = settings_windows()
    if there:
        from .. import winplace
        ops_setup.restore_tabs()
        ops_setup.redraw_all()
        winplace.raise_window(there[0], KEY)
        return {"FINISHED"}
    if ops_setup.busy():
        op.report({"INFO"}, "A window is opening: a moment, then press again")
        return {"CANCELLED"}
    win, area, _region = ops_setup.main_view(context)
    if area is None:
        op.report({"WARNING"}, "Fresing Settings needs a 3D view in the main window")
        return {"CANCELLED"}
    if win.screen.show_fullscreen:
        op.report({"WARNING"}, "The 3D view fills the whole window: go back to the normal layout first "
                               "(Ctrl+Space), then open Fresing Settings again")
        return {"CANCELLED"}
    ops_setup.open_window(win, area, mark=SETTINGS_MARK, value=KEY, done=_opened, size=SIZE)
    return {"FINISHED"}


def _opened(win) -> None:
    """The window is open: where it was last time (Windows), and its side panel made as wide as the window."""
    from . import ops_make
    try:
        ops_make._placed(win)
    finally:
        tries = [0]

        def widen():
            tries[0] += 1
            return _widen(win, tries[0])

        bpy.app.timers.register(widen, first_interval=0.2)


def _widen(win, tries: int):
    """A script cannot set a side panel's width: the copy's panel is as wide as the main view's. Its stored width is
    written once the window was drawn (``ui_left.set_side_width``, the way the left panel gets its width). Nothing is
    set on the view before it was drawn (CLAUDE.md, 0221)."""
    from . import editors, ui_left
    try:
        if not any(w == win for w in bpy.context.window_manager.windows):
            return None
        area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
        region = next((r for r in area.regions if r.type == "UI"), None) if area is not None else None
        if region is None:
            return None
        if region.width <= 1 or not editors.settled():
            return 0.1 if tries < 50 else None
        scale = bpy.context.preferences.system.ui_scale or 1.0
        if abs(region.width / scale - SIZE[0]) > 6 and not ui_left.set_side_width(area, SIZE[0]):
            print("Fresing Render: the Settings window keeps its side panel's width (its width was not found)")
        ops_setup.restore_tabs()
    except Exception as exc:  # noqa: BLE001 - the window works at any width
        print("Fresing Render: the Settings window was not widened:", exc)
    return None


class FRESING_OT_settings(bpy.types.Operator):
    """Opens Fresing Settings: all of the app's own settings in one window, with a tab for each page (General, Side
    panel, Lessons, Backups, Updates, My usage, About). Drag it anywhere; it stays open until you close it"""

    bl_idname = "fresing.settings"
    bl_label = "Fresing Settings"
    bl_options = set()         # (not REGISTER: no "adjust last operation" box for a window button)

    tab: StringProperty(name="Tab", default="", options={"SKIP_SAVE"},
                        description="The page to open on (general, panel, lessons, backups, updates, usage, about). "
                                    "Empty: the page you had open last")

    def execute(self, context):
        return open_settings(self, context, self.tab)


class FRESING_OT_settings_tab(bpy.types.Operator):
    """Shows this page of Fresing Settings. The window opens on it again next time"""

    bl_idname = "fresing.settings_tab"
    bl_label = "Settings page"
    bl_options = {"INTERNAL"}

    tab: StringProperty(name="Page", default="general", options={"SKIP_SAVE"},
                        description="The page to show (general, panel, lessons, backups, updates, usage, about)")

    @classmethod
    def description(cls, context, properties):
        entry = ui_settings.tab(getattr(properties, "tab", "") or "")
        if entry is None:
            return " ".join(cls.__doc__.split())
        return {"general": "General: the library folder, default template and rule set, the workspace for new "
                           "projects, the highlight while picking",
                "panel": "Side panel: how sections and How it works open, the favourites bar, the questions "
                         "about unused panels and what to learn next",
                "lessons": "Lessons: how a lesson points at a button, a section and a part; its colour; Play on",
                "backups": "Backups: automatic backups of the open project – on or off, how often, how many",
                "updates": "Updates: the check at start-up, Check now, the installed version",
                "usage": "My usage: what you use, where your time goes, time saved, your profile, clearing your data",
                "about": "About: version, licence, third-party licences, using it in a company",
                }.get(entry[0], f"Shows the settings page {entry[1]}")

    def execute(self, context):
        if not set_tab(self.tab):
            self.report({"ERROR"}, f"Fresing Settings has no page '{self.tab}'")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_settings_close(bpy.types.Operator):
    """Closes Fresing Settings. It opens again on the same page (on Windows also where it was)"""

    bl_idname = "fresing.settings_close"
    bl_label = "Close"
    bl_options = set()

    def execute(self, context):
        from . import ops_make
        wins = settings_windows()
        for win in wins:
            try:
                ops_make.remember(win)
            except Exception:  # noqa: BLE001
                pass
        if context.window in wins:      # pressed in the window itself: Blender still needs it until the button is done
            bpy.app.timers.register(close_all, first_interval=0.01)
        else:
            close_all()
        return {"FINISHED"}


def close_all():
    for win in settings_windows():
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.wm.window_close()
    panels.redraw()
    return None


# ---------------------------------------------------------------------------
# presence: only the user's own input says "the user is here" (task 0271)
# ---------------------------------------------------------------------------

class FRESING_OT_presence(bpy.types.Operator):
    """Notes that you are at the app (a mouse move, a click), so My usage counts only the time you really work. Never
    stops the click or the move: it goes on to Blender as before"""

    bl_idname = "fresing.presence"
    bl_label = "You are here"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        try:
            from . import usage
            usage.presence(event.type, event.mouse_x, event.mouse_y)
        except Exception:  # noqa: BLE001 - never stop an event
            pass
        return {"PASS_THROUGH"}


PRESENCE_KEYS = (("MOUSEMOVE", "ANY"), ("LEFTMOUSE", "PRESS"), ("RIGHTMOUSE", "PRESS"), ("MIDDLEMOUSE", "PRESS"),
                 ("WHEELUPMOUSE", "ANY"), ("WHEELDOWNMOUSE", "ANY"), ("TRACKPADPAN", "ANY"))
_KEYMAPS: list = []


def add_keys() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm is not None else None
    if kc is None:                    # a background run: no input at all
        return
    remove_keys()
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    for key, value in PRESENCE_KEYS:
        kmi = km.keymap_items.new(FRESING_OT_presence.bl_idname, key, value, any=True)
        _KEYMAPS.append((km, kmi))


def remove_keys() -> None:
    for km, kmi in _KEYMAPS:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _KEYMAPS.clear()


CLASSES = (FRESING_OT_settings, FRESING_OT_settings_tab, FRESING_OT_settings_close, FRESING_OT_presence)


def register() -> None:
    add_keys()


def unregister() -> None:
    remove_keys()
