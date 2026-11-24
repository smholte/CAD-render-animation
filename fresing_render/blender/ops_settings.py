"""Fresing Settings (task 0271): one window with all of the app's own settings, a row of tabs along its top.

**The window** is made like an output window of Make (task 0260): ``ops_setup.open_window`` copies a piece of the main
3D view into a window of its own and marks its screen ``fr_settings``. Its page is drawn in the **toolbar region** (the
region of 0260's left panel), not the side panel: a side panel always draws a tab strip – Blender's Tool / View /
Animation beside ours, and even one tab for a single panel (measured, 21 Nov: "Misc") – which the owner's check of
21 Nov ruled out. ``ops_setup._dress`` switches the window's side panel, header, gizmos and overlays off and its
toolbar on; ``_settle`` makes the toolbar as wide as the window (``ui_left.fit_width``), so no view shows beside it;
Blender's tool buttons, the toolbar's only panel of Blender's, hide in this window (``quiet_panels``: a ``poll``,
registered again). A Text editor's sidebar was tried first: it too draws its tab strip.

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
SIZE = (440, 640)              # the window, px at UI scale 1 (the Set-up and Make windows: ~280 x 560)


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
    from . import ops_make
    size = ops_make.kept_size(KEY) or SIZE            # task 0282: the size it had last time
    ops_setup.open_window(win, area, mark=SETTINGS_MARK, value=KEY, done=_opened, size=size)
    return {"FINISHED"}


def _opened(win) -> None:
    """The window is open: where it was last time (Windows), then its page made as wide as the window."""
    from . import ops_make
    try:
        ops_make._placed(win)
    finally:
        tries = [0]

        def settle():
            tries[0] += 1
            return _settle(win, tries[0])

        bpy.app.timers.register(settle, first_interval=0.2)


def settings_area(win):
    return next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)


def _region(area, kind: str):
    return next((r for r in area.regions if r.type == kind), None) if area is not None else None


def _settle(win, tries: int):
    """One timer step of tidying the new window: once it was drawn (CLAUDE.md, 0221), its toolbar region – the page –
    is made as wide as the window (a script cannot set a region's width: ``ui_left.fit_width``)."""
    from . import editors, ui_left
    try:
        if not any(w == win for w in bpy.context.window_manager.windows) or tries > 80:
            return None
        area = settings_area(win)
        tools = _region(area, "TOOLS")
        if area is None:
            return None
        if tools is None or tools.width <= 1 or not editors.settled():
            if area.spaces.active.show_region_ui or not area.spaces.active.show_region_toolbar:
                ops_setup.restore_tabs()             # (dresses the window: side panel off, toolbar on)
            return 0.1
        want = area.width - 4                        # real pixels: the page fills the window
        if abs(tools.width - want) > 6 and not ui_left.fit_width(area, want):
            print("Fresing Render: the Settings window keeps its page's width (its width was not found)")
    except Exception as exc:  # noqa: BLE001 - the window works at any width
        print("Fresing Render: the Settings window was not tidied:", exc)
    return None


def shows_only_the_page(win) -> tuple:
    """(ok, what else shows) – the owner's rule of 21 Nov (Settings; task 0282: every function window too): no tabs,
    no view, no headers, only the page. The page is in
    the toolbar region (no tab strip there), which fills the window; the side panel, header, tool header, overlays and
    gizmos are off; no other panel of the toolbar region shows in this window."""
    area = settings_area(win)
    if area is None:
        return False, "no 3D view to draw in"
    sp = area.spaces.active
    other = [name for name, on in (("side panel with its tabs", sp.show_region_ui), ("header", sp.show_region_header),
                                   ("tool header", sp.show_region_tool_header), ("overlays", sp.overlay.show_overlays),
                                   ("gizmos", sp.show_gizmo)) if on]
    tools = _region(area, "TOOLS")
    if not sp.show_region_toolbar or tools is None or tools.width <= 1:
        other.append("no page")
    elif area.width - tools.width > 24:
        other.append(f"{area.width - tools.width} px of 3D view beside the page")
    shown = []
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=tools):
        for cls in bpy.types.Panel.__subclasses__():
            if getattr(cls, "bl_space_type", "") != "VIEW_3D" or getattr(cls, "bl_region_type", "") != "TOOLS":
                continue
            if getattr(cls, "bl_parent_id", "") or cls.__name__ in PAGES:
                continue
            if not getattr(cls, "is_registered", False):
                continue
            try:
                ok = cls.poll(bpy.context) if hasattr(cls, "poll") else True
            except Exception:  # noqa: BLE001
                ok = True
            if ok:
                shown.append(cls.__name__)
    if shown:
        other.append("panels " + ", ".join(shown))
    return not other, ", ".join(other)


PAGES = ("FRESING_PT_settings_window", "FRESING_PT_form_window",     # the pages of the page windows (0271, 0282,
         "FRESING_PT_first_setup", "FRESING_PT_materials_window")       # 0276, 0273)

# Blender's own panel of the 3D view's toolbar region (its tool buttons): hidden in the Settings window, the function
# windows and (task 0308) the output windows, whose toolbar region holds the outputs strip
QUIET_PANELS = ("VIEW3D_PT_tools_active",)
# task 0308: the side-panel tabs of Blender's own an output window shows beside "Make" – their Python panels hide there.
# (Blender's Transform panel of the tab Item is not a Python class: with an active object that tab stays.)
QUIET_TABS = ("Item", "Tool", "View", "Animation")
_QUIET: dict = {}                 # class name -> (class, its own poll in its __dict__ or None, its children)


def _in_settings(context) -> bool:
    """In Fresing Settings, a function window (task 0282) or an output window (task 0308): no Blender panels there."""
    win = getattr(context, "window", None)
    return ops_setup.is_page_window(win) or ops_setup._is_output(win)


def _hiding_poll(inherited):
    def poll(cls, context):
        if _in_settings(context):
            return False
        return inherited(context) if inherited is not None else True
    return poll


def tab_panels() -> list:
    """The top-level Python panels of the 3D view's side panel in Blender's tabs Item, Tool, View and Animation."""
    out = []
    for cls in bpy.types.Panel.__subclasses__():
        if (getattr(cls, "bl_space_type", "") == "VIEW_3D" and getattr(cls, "bl_region_type", "") == "UI"
                and getattr(cls, "bl_category", "") in QUIET_TABS and not getattr(cls, "bl_parent_id", "")
                and getattr(cls, "is_registered", False) and not cls.__name__.startswith("FRESING_")):
            out.append(cls)
    return out


def _children(cls) -> list:
    """The registered panels under ``cls``, parents before children (they are registered again in that order)."""
    ident = getattr(cls, "bl_idname", "") or cls.__name__
    out = []
    for sub in bpy.types.Panel.__subclasses__():
        if getattr(sub, "bl_parent_id", "") == ident and getattr(sub, "is_registered", False):
            out.append(sub)
            out += _children(sub)
    return out


def _quiet_one(cls) -> None:
    name = cls.__name__
    if name in _QUIET:
        return
    own = cls.__dict__.get("poll")
    inherited = getattr(cls, "poll", None)
    kids = _children(cls)
    try:
        for kid in reversed(kids):            # children first: a parent taken away leaves its children loose
            bpy.utils.unregister_class(kid)
        bpy.utils.unregister_class(cls)
        cls.poll = classmethod(_hiding_poll(inherited))     # Blender checks it takes (cls, context) only
        bpy.utils.register_class(cls)
        _QUIET[name] = (cls, own, kids)
    except Exception as exc:  # noqa: BLE001 - the window still works, with Blender's panel in it
        print(f"Fresing Render: {name} not hidden in the app's windows:", exc)
        try:
            if own is None and "poll" in cls.__dict__:
                del cls.poll
            elif own is not None:
                cls.poll = own
            if not getattr(cls, "is_registered", True):
                bpy.utils.register_class(cls)
        except Exception:  # noqa: BLE001
            pass
    for kid in kids:
        if not getattr(kid, "is_registered", True):
            try:
                bpy.utils.register_class(kid)
            except Exception as exc:  # noqa: BLE001
                print(f"Fresing Render: {kid.__name__} not registered again:", exc)


def quiet_panels() -> None:
    """Give Blender's tool buttons, and the panels of its side-panel tabs, a ``poll`` that hides them in the app's own
    windows. A ``poll`` added to a registered class is ignored, so the class is registered again with it (its draw –
    and quiet.py's swap of it – stays; its sub-panels are registered again after it)."""
    for name in QUIET_PANELS:
        cls = getattr(bpy.types, name, None)
        if cls is not None:
            _quiet_one(cls)
    for cls in tab_panels():
        _quiet_one(cls)


def loud_panels() -> None:
    for name, (cls, own, kids) in list(_QUIET.items()):
        try:
            for kid in reversed(kids):
                if getattr(kid, "is_registered", False):
                    bpy.utils.unregister_class(kid)
            bpy.utils.unregister_class(cls)
            if own is None:
                del cls.poll
            else:
                cls.poll = own
            bpy.utils.register_class(cls)
            for kid in kids:
                if not getattr(kid, "is_registered", True):
                    bpy.utils.register_class(kid)
        except Exception as exc:  # noqa: BLE001
            print(f"Fresing Render: {name} not put back:", exc)
        _QUIET.pop(name, None)


class FRESING_OT_settings(bpy.types.Operator):
    """Opens Fresing Settings: all of the app's own settings in one window, with a tab for each page (General,
    Locations, Exports, Side panel, Lessons, Backups, Updates, My usage, About). Drag it anywhere; it stays open until you close it"""

    bl_idname = "fresing.settings"
    bl_label = "Fresing Settings"
    bl_options = set()         # (not REGISTER: no "adjust last operation" box for a window button)

    tab: StringProperty(name="Tab", default="", options={"SKIP_SAVE"},
                        description="The page to open on (general, locations, exports, panel, lessons, backups, "
                                    "updates, usage, about). "
                                    "Empty: the page you had open last")

    def execute(self, context):
        return open_settings(self, context, self.tab)


class FRESING_OT_settings_tab(bpy.types.Operator):
    """Shows this page of Fresing Settings. The window opens on it again next time"""

    bl_idname = "fresing.settings_tab"
    bl_label = "Settings page"
    bl_options = {"INTERNAL"}

    tab: StringProperty(name="Page", default="general", options={"SKIP_SAVE"},
                        description="The page to show (general, locations, exports, panel, lessons, backups, updates, "
                                    "usage, about)")

    @classmethod
    def description(cls, context, properties):
        entry = ui_settings.tab(getattr(properties, "tab", "") or "")
        if entry is None:
            return " ".join(cls.__doc__.split())
        return {"general": "General: the default template and rule set, the workspace for new "
                           "projects, the highlight while picking",
                "panel": "Side panel: how sections and How it works open, the favourites bar, the questions "
                         "about unused panels and what to learn next",
                "locations": "Locations: the folders the app reads from (models, logos, materials, rule sets …) – "
                             "Company, Department and your own –, set-up files",
                "exports": "Exports: where pictures, videos and 3D pages go – the default place, also a copy to "
                           "another place",
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
    quiet_panels()


def unregister() -> None:
    remove_keys()
    loud_panels()
