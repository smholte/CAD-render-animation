"""The output windows of Make (task 0260): one small window per output, that can be dragged anywhere (also onto a second
monitor) and stays open while you click elsewhere – until you close it.

Make (the top of the Fresing panel, and the 3D view header's Make list) lists six outputs: Picture, Product video,
Turntable, 3D page, Animation, Queue. Each button opens that output's own window with the app's own settings and its
Make button – nothing is copied: it draws the same settings panel as 5 Scene & Render, 6 Animation and 7 Render
queue, so a change in one shows in the other.

**The window** is made like the Set-up window (``ops_setup.open_window``: a piece of the main 3D view copied into a
window of its own, the piece closed again). Its screen is marked ``fr_output = <key>``; its side panel shows the tab
"Make", where ``FRESING_PT_make_window`` draws the output of that key. Opening the same output again brings its
window to the front (Windows) instead of a second one. On Windows the window also opens where it was last time
(``winplace.py``; the places are kept per user in ``<config>/fresing_make_windows.json``). A window left open is saved
with the project like the Set-up window and comes back with it; another project brings its own windows.

Client view: the windows open (``lock.ALLOWED_PREFIXES`` has ``fresing.make_``); the buttons in them follow the lock as
they do in the side panel.
"""

from __future__ import annotations

import json
import os

import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty

from . import ops_setup, panels, ui, ui_top
from .ops_setup import OUTPUT_MARK, OUTPUT_TAB

PLACES_FILE = "fresing_make_windows.json"
WATCH_SECONDS = 2.0           # Windows: how often the places of open output windows are read (to reopen them there)


def outputs() -> dict:
    """key -> (button text, icon, popover panel class name, function id, main operator, its text)."""
    return {o[0]: o[1:] for o in ui_top.OUTPUTS}


def title(key: str) -> str:
    o = outputs().get(key)
    return o[0] if o else key


def output_windows(key: str | None = None) -> list:
    wm = getattr(bpy.context, "window_manager", None)
    out = []
    for win in (wm.windows if wm is not None else ()):
        try:
            k = win.screen.get(OUTPUT_MARK)
        except (AttributeError, ReferenceError):
            continue
        if k and (key is None or k == key):
            out.append(win)
    return out


# ---------------------------------------------------------------------------
# the places (Windows)
# ---------------------------------------------------------------------------

def places_path() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), PLACES_FILE)


def read_places(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: [int(v) for v in r] for k, r in data.items()
            if isinstance(k, str) and isinstance(r, list) and len(r) == 4 and all(isinstance(v, int) for v in r)}


def write_places(path: str, places: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(places, fh, indent=1)
    os.replace(tmp, path)


_PLACES: dict = {}            # what was read last (key -> [left, top, right, bottom])


def remember(win) -> None:
    """Keep this output window's place for the next time it opens (Windows only)."""
    from .. import winplace
    if not winplace.available():
        return
    key = win.screen.get(OUTPUT_MARK)
    r = winplace.rect(win, key)
    if not key or r is None or not winplace.usable(r):
        return
    if not _PLACES:
        _PLACES.update(read_places(places_path()))
    if _PLACES.get(key) == list(r):
        return
    _PLACES[key] = list(r)
    try:
        write_places(places_path(), _PLACES)
    except OSError as exc:
        print("Fresing Render: the output window's place was not kept:", exc)


def _watch():
    """Windows: read the places of the open output windows now and then (a window closed with its own X is then
    still reopened where it was)."""
    wins = output_windows()
    if not wins:
        return None
    for win in wins:
        try:
            remember(win)
        except Exception:  # noqa: BLE001
            pass
    return WATCH_SECONDS


def _placed(win) -> None:
    """A new output window is open: where it was last time (Windows), and its place watched from now on."""
    from .. import winplace
    if not winplace.available():
        return
    key = win.screen.get(OUTPUT_MARK)
    winplace.find(win, key)                   # the handle, while the window is new and stands where Blender put it
    r = read_places(places_path()).get(key)
    if r is not None:
        winplace.place(win, r, key)
    watch()


def watch() -> None:
    """Keep reading the places of the open output windows (Windows) – also of those a project brought back."""
    from .. import winplace
    if winplace.available() and output_windows() and not bpy.app.timers.is_registered(_watch):
        bpy.app.timers.register(_watch, first_interval=WATCH_SECONDS)


@persistent
def _on_load(_dummy=None):
    from .. import winplace
    winplace.forget()
    if not bpy.app.background:
        bpy.app.timers.register(lambda: (watch(), None)[1], first_interval=1.0)


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

class FRESING_OT_make_window(bpy.types.Operator):
    """Opens this output's settings in a window of its own, with its own Make button. Drag the window anywhere – also
    onto a second screen; it stays open while you work elsewhere, until you close it"""

    bl_idname = "fresing.make_window"
    bl_label = "Make"
    bl_options = set()         # (not REGISTER: no "adjust last operation" box for a window button)

    key: StringProperty(name="Output", default="", options={"SKIP_SAVE"},
                        description="Which output: still, product, turn, web, anim or queue")

    @classmethod
    def register(cls):
        if _on_load not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_on_load)

    @classmethod
    def unregister(cls):
        while _on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load)
        if bpy.app.timers.is_registered(_watch):
            bpy.app.timers.unregister(_watch)

    @classmethod
    def description(cls, context, properties):
        key = getattr(properties, "key", "") or ""
        o = outputs().get(key)
        if o is None:
            return " ".join(cls.__doc__.split())
        line = ui_top.MAKE_LINES.get(key, "")
        return (f"{o[0]}: {line}. Opens its settings in a window of its own with its Make button – drag it anywhere, "
                "it stays open until you close it")

    def execute(self, context):
        if self.key not in outputs():
            self.report({"ERROR"}, f"No output is called '{self.key}'")
            return {"CANCELLED"}
        if bpy.app.background:
            self.report({"INFO"}, "Output windows open only in the app's own window, not in a background run")
            return {"CANCELLED"}
        there = output_windows(self.key)
        if there:
            from .. import winplace
            ops_setup.restore_tabs()
            ops_setup.redraw_all()
            winplace.raise_window(there[0], self.key)
            self.report({"INFO"}, f"The {title(self.key)} window is open already")
            return {"FINISHED"}
        if ops_setup.busy():
            self.report({"INFO"}, "A window is opening: a moment, then press again")
            return {"CANCELLED"}
        win, area, _region = ops_setup.main_view(context)
        if area is None:
            self.report({"WARNING"}, "The output windows need a 3D view in the main window")
            return {"CANCELLED"}
        if win.screen.show_fullscreen:
            self.report({"WARNING"}, "The 3D view fills the whole window: go back to the normal layout first "
                                     "(Ctrl+Space), then press it again")
            return {"CANCELLED"}
        ops_setup.open_window(win, area, mark=OUTPUT_MARK, value=self.key, done=_placed)
        return {"FINISHED"}


class FRESING_OT_make_close(bpy.types.Operator):
    """Closes this output window. Make opens it again, on Windows where it was"""

    bl_idname = "fresing.make_close"
    bl_label = "Close"
    bl_options = set()

    key: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        wins = output_windows(self.key or None)
        for win in wins:
            try:
                remember(win)
            except Exception:  # noqa: BLE001
                pass

        key = self.key
        if context.window in wins:      # pressed in the window itself: Blender still needs it until the button is done
            bpy.app.timers.register(lambda: _close_later(key), first_interval=0.01)
        else:
            _close_later(key)
        return {"FINISHED"}


def _close_later(key: str):
    for win in output_windows(key or None):
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.wm.window_close()
    panels.redraw()
    return None


def close_all() -> None:
    _close_later("")


class FRESING_OT_make_fold(bpy.types.Operator):
    """Shows Make as a labelled list, or folds it to one row of icons again. Every button opens that output's window.
    Your choice is kept for every project"""

    bl_idname = "fresing.make_fold"
    bl_label = "Make"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import prefs
        p = prefs.get()
        if p is None:
            return {"CANCELLED"}
        p.make_open = not p.make_open
        panels.redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# the window's panel
# ---------------------------------------------------------------------------

def draw_output(self, context, key: str) -> None:
    """The output's own settings, exactly as the side panel draws them (wrapped at this window's width)."""
    from . import ui_motion
    o = outputs().get(key)
    if o is None:
        self.layout.label(text="Not available", icon="ERROR")
        return
    pop = getattr(ui_top, o[2], None)
    region = getattr(context, "region", None)
    scale = context.preferences.system.ui_scale or 1.0
    units = max(12, int((getattr(region, "width", 300) or 300) / scale / 20))
    with ui.popover_width(units):
        target = getattr(pop, "target", "")
        if target:
            cls = getattr(bpy.types, target, None)
            if cls is None:
                self.layout.label(text="Not available", icon="ERROR")
                return
            panels.body_of(cls)(self, context)
        elif key == "product":
            ui_motion._draw_product_video(self.layout, context)
        else:
            ui_top.draw_anim(self.layout, context)


class FRESING_PT_make_window(bpy.types.Panel):
    """The settings of one output in its own window (task 0260)."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = OUTPUT_TAB
    bl_label = "Make"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        win = getattr(context, "window", None)
        try:
            return bool(win is not None and win.screen.get(OUTPUT_MARK))
        except (AttributeError, ReferenceError):
            return False

    def draw(self, context):
        key = context.window.screen.get(OUTPUT_MARK)
        o = outputs().get(key)
        row = self.layout.row(align=True)
        row.scale_y = 1.2
        row.label(text=o[0] if o else str(key), icon=o[1] if o else "ERROR")
        right = row.row(align=True)
        right.alignment = "RIGHT"
        right.operator("fresing.make_close", text="", icon="X", emboss=False).key = key
        ui.gap(self.layout)
        if getattr(context.scene, "fresing", None) is None or context.scene.fresing.model_count == 0:
            ui.wrap(self.layout, context, "Import a model first (1 Import).", icon="INFO")
            return
        draw_output(self, context, key)


CLASSES = (FRESING_OT_make_window, FRESING_OT_make_close, FRESING_OT_make_fold, FRESING_PT_make_window)
