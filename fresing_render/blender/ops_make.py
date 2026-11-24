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
(``winplace.py``); every PC opens it at the size it had (task 0282: sizes and places are kept in the settings file,
``prefs.window_places``; the old ``<config>/fresing_make_windows.json`` is read once). A window left open is saved
with the project like the Set-up window and comes back with it; another project brings its own windows.

**The outputs strip** (task 0308): the window's toolbar region (left, no tab strip there) holds
``FRESING_PT_make_strip`` – one button per output, the window's own pressed; a click switches THIS window to that
output (``switch``: the screen's mark changes, its size is kept under the new key). One icon wide when the window opens
(``settle_strip``: the region was copied with the left panel's 240 px, so the side panel is off while it is made
narrow); dragged wider than ``NAMES_FROM`` the names show, and the settings shrink to the room left (``keep_filled`` →
``fill``; a side panel that does not fit is drawn empty by Blender). Blender's tool buttons and the panels of its tabs
Item / Tool / View / Animation hide in output windows (``ops_settings.quiet_panels``); Blender's Transform panel is no
Python class, so "Item" stays while an object is active.

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
from .ops_setup import FIRST_SETUP_MARK, FORM_MARK, OUTPUT_MARK, OUTPUT_TAB, SETTINGS_MARK, STRIP, STRIP_SETTLE

PLACES_FILE = "fresing_make_windows.json"
NAMES_FROM = 100              # task 0308: a strip at least this wide (px at UI scale 1) shows the outputs' names
WATCH_SECONDS = 2.0           # how often the sizes (and on Windows the places) of open app windows are read


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
# the places and sizes (task 0282: in the settings file)
# ---------------------------------------------------------------------------

def places_path() -> str:
    """The file the places were kept in before task 0282 (read once, then they live in the settings file)."""
    return os.path.join(bpy.utils.user_resource("CONFIG"), PLACES_FILE)


def _rects(data, n: int) -> dict:
    if not isinstance(data, dict):
        return {}
    return {k: [int(v) for v in r] for k, r in data.items()
            if isinstance(k, str) and isinstance(r, list) and len(r) == n
            and all(isinstance(v, int) and not isinstance(v, bool) for v in r)}


def read_places(path: str) -> dict:
    """The old file of 0260 / 0271: {key: [left, top, right, bottom]}."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return _rects(data, 4)


def write_places(path: str, places: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(places, fh, indent=1)
    os.replace(tmp, path)


def parse(text: str) -> tuple:
    """(places, sizes) from the preference's text: {"places": {key: [l, t, r, b]}, "sizes": {key: [w, h]}};
    anything odd is left out."""
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    return _rects(data.get("places"), 4), _rects(data.get("sizes"), 2)


def dump(places: dict, sizes: dict) -> str:
    return json.dumps({"places": dict(sorted(places.items())), "sizes": dict(sorted(sizes.items()))},
                      separators=(",", ":"))


_KEPT: dict = {"read": False, "places": {}, "sizes": {}}


def _kept() -> dict:
    """What is kept (read once from the preference – the settings file –, or moved over from the old file)."""
    if not _KEPT["read"]:
        from . import prefs
        p = prefs.get()
        text = getattr(p, "window_places", "") if p is not None else ""
        places, sizes = parse(text)
        if not text:
            places = read_places(places_path())          # task 0282: the old file's places move over once
        _KEPT.update(read=True, places=places, sizes=sizes)
    return _KEPT


def _store() -> None:
    from . import prefs
    p = prefs.get()
    if p is None:
        return
    text = dump(_KEPT["places"], _KEPT["sizes"])
    if p.window_places != text:
        p.window_places = text                            # settings_store writes the file within a second


def kept_place(key: str):
    return _kept()["places"].get(key)


def kept_size(key: str):
    """(width, height) at UI scale 1 the window had when it was last seen open, or None."""
    r = _kept()["sizes"].get(key)
    return tuple(r) if r else None


def forget_places() -> None:
    """Tests: read the kept places again."""
    _KEPT.update(read=False, places={}, sizes={})


def place_key(win) -> str:
    """The key a window's place is kept under: the output's key, "settings" for the Settings window (task 0271),
    "form:<operator id>" for a function window (task 0282)."""
    try:
        screen = win.screen
        if screen.get(SETTINGS_MARK):
            return "settings"
        if screen.get(FORM_MARK):
            return "form:" + str(screen.get(FORM_MARK))
        if screen.get(FIRST_SETUP_MARK):
            return "first_setup"                        # task 0276: the first-start set-up
        return str(screen.get(OUTPUT_MARK) or "")
    except (AttributeError, ReferenceError):
        return ""


def placed_windows() -> list:
    """The windows whose place is kept: the output windows, the Settings window and the function windows."""
    wm = getattr(bpy.context, "window_manager", None)
    return [w for w in (wm.windows if wm is not None else ()) if place_key(w)]


def remember(win) -> None:
    """Keep this window's size (every PC) and place (Windows) for the next time it opens."""
    from .. import winplace
    key = place_key(win)
    if not key:
        return
    kept = _kept()
    changed = False
    try:
        scale = bpy.context.preferences.system.ui_scale or 1.0
        size = [int(round(win.width / scale)), int(round(win.height / scale))]
    except (AttributeError, ReferenceError):
        size = None
    if size and min(size) >= 100 and kept["sizes"].get(key) != size:
        kept["sizes"][key] = size
        changed = True
    if winplace.available():
        r = winplace.rect(win, key)
        if r is not None and winplace.usable(r) and kept["places"].get(key) != list(r):
            kept["places"][key] = list(r)
            changed = True
    if changed:
        _store()


def _watch():
    """Read the sizes (and on Windows the places) of the open app windows now and then: a window closed with its own
    X is then still reopened as it was."""
    wins = placed_windows()
    if not wins:
        return None
    for win in wins:
        try:
            remember(win)
        except Exception:  # noqa: BLE001
            pass
    return WATCH_SECONDS


def _placed(win) -> None:
    """A new app window is open: where it was last time (Windows), and its size and place watched from now on."""
    from .. import winplace
    if ops_setup._is_output(win):
        settle_strip(win)
    if winplace.available():
        key = place_key(win)
        winplace.find(win, key)               # the handle, while the window is new and stands where Blender put it
        r = kept_place(key)
        if r is not None:
            winplace.place(win, r, key)
    watch()


def watch() -> None:
    """Keep reading the sizes and places of the open app windows – also of those a project brought back."""
    if placed_windows() and not bpy.app.timers.is_registered(_watch):
        bpy.app.timers.register(_watch, first_interval=WATCH_SECONDS)


# ---------------------------------------------------------------------------
# the outputs strip (task 0308)
# ---------------------------------------------------------------------------

def _view_area(win):
    try:
        return next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    except (AttributeError, ReferenceError):
        return None


def _region(area, kind: str):
    return next((r for r in area.regions if r.type == kind), None) if area is not None else None


def strip_width(win) -> float:
    """The strip's width in px at UI scale 1 (0 when it is not shown)."""
    area = _view_area(win)
    tools = _region(area, "TOOLS")
    if area is None or tools is None or not area.spaces.active.show_region_toolbar or tools.width <= 1:
        return 0.0
    return tools.width / (bpy.context.preferences.system.ui_scale or 1.0)


def settle_strip(win) -> None:
    """A new output window: its toolbar region – the strip – one icon wide. The region was copied from the main view
    with the left panel's width (240 px) and would squeeze the settings, so the side panel is off while the strip is
    shown and made narrow (``ui_left.set_width``, the only way a script can set a region's width), then back on. Each
    step waits for a redraw (CLAUDE.md, 0221: nothing set on a 3D view before it was drawn)."""
    if bpy.app.background:
        return
    job = {"step": 0, "tries": 0}
    try:
        win.screen[STRIP_SETTLE] = 1          # (ops_setup._finish set it already, before the window was dressed)
    except (AttributeError, ReferenceError):
        return

    def tick():
        return _settle_tick(win, job)

    bpy.app.timers.register(tick, first_interval=0.2)


def _settle_tick(win, job):
    from . import editors, ui_left
    job["tries"] += 1
    try:
        if not any(w == win for w in bpy.context.window_manager.windows):
            return None
        area = _view_area(win)
        if area is None:
            return None
        sp = area.spaces.active
        tools = _region(area, "TOOLS")
        if job["tries"] > 100:
            raise RuntimeError("the window was not drawn in time")
        if not editors.settled():
            return 0.1
        if job["step"] == 0:                      # the side panel off, the strip on
            if sp.show_region_ui:
                sp.show_region_ui = False
            if not sp.show_region_toolbar:
                sp.show_region_toolbar = True
            job["step"] = 1
            return 0.1
        if job["step"] == 1:                      # the strip drawn: make it narrow
            if tools is None or tools.width <= 1:
                return 0.1
            scale = bpy.context.preferences.system.ui_scale or 1.0
            if abs(tools.width / scale - STRIP) > 4 and not ui_left.set_width(area, STRIP):
                print("Fresing Render: the outputs strip keeps its width (its width was not found)")
            job["step"] = 2
            return 0.1
        if not sp.show_region_ui:
            sp.show_region_ui = True              # the settings back
            return 0.1
        fill(win)                                 # … filling what the strip leaves (no empty view beside them)
    except Exception as exc:  # noqa: BLE001 - the window works with any strip
        print("Fresing Render: the outputs strip was not made narrow:", exc)
        try:
            area = _view_area(win)
            if area is not None:
                area.spaces.active.show_region_ui = True
        except Exception:  # noqa: BLE001
            pass
    try:
        if STRIP_SETTLE in win.screen:
            del win.screen[STRIP_SETTLE]
    except (AttributeError, ReferenceError, KeyError):
        pass
    ops_setup.restore_tabs()
    return None


FILL_SLACK = 6                 # px the settings may be off the room the strip leaves before they are fitted again
FILL_GAP = ops_setup.STRIP_GAP # … and leave this many px: a side panel that only just fits is drawn empty (measured)
_FILL = {"pending": set()}


def fill(win) -> bool:
    """The settings fill the room the strip leaves (the user dragged the strip wider or narrower). False when there
    is nothing to change or it cannot be done."""
    from . import ui_left
    area = _view_area(win)
    tools, side = _region(area, "TOOLS"), _region(area, "UI")
    if area is None or tools is None or side is None or not area.spaces.active.show_region_ui:
        return False
    strip = tools.width if area.spaces.active.show_region_toolbar and tools.width > 1 else 0
    want = area.width - strip - FILL_GAP
    if abs(side.width - want) <= FILL_SLACK:
        return False
    return ui_left.fit_side(area, want)


def keep_filled(win) -> None:
    """Called while the strip draws: fit the settings a moment later (never while Blender draws)."""
    key = win.as_pointer() if win is not None else 0
    if not key or key in _FILL["pending"] or win.screen.get(STRIP_SETTLE):
        return
    area = _view_area(win)
    tools, side = _region(area, "TOOLS"), _region(area, "UI")
    if area is None or tools is None or side is None:
        return
    strip = tools.width if tools.width > 1 else 0
    if abs(side.width - (area.width - strip - FILL_GAP)) <= FILL_SLACK:
        return
    _FILL["pending"].add(key)

    def later():
        _FILL["pending"].discard(key)
        for w in output_windows():
            if w.as_pointer() == key:
                try:
                    fill(w)
                except Exception as exc:  # noqa: BLE001
                    print("Fresing Render: the output window's settings not fitted:", exc)
        return None

    bpy.app.timers.register(later, first_interval=0.25)


def switch(win, key: str) -> str:
    """Show output ``key`` in this output window (the strip's buttons). Returns "" when switched, else why not."""
    if key not in outputs():
        return f"No output is called '{key}'"
    try:
        now = win.screen.get(OUTPUT_MARK)
    except (AttributeError, ReferenceError):
        return "This is no output window"
    if not now:
        return "This is no output window"
    if now == key:
        return ""
    other = [w for w in output_windows(key) if w != win]
    if other:
        from .. import winplace
        winplace.raise_window(other[0], key)
        return f"The {title(key)} window is open already"
    try:
        remember(win)                             # the size under the output it showed until now
    except Exception:  # noqa: BLE001
        pass
    win.screen[OUTPUT_MARK] = key
    from .. import winplace
    winplace.rekey(str(now), key)
    for area in win.screen.areas:
        area.tag_redraw()
    return ""


class FRESING_OT_make_switch(bpy.types.Operator):
    """Shows another output in this window: its settings and its Make button. The strip on the left lists every
    output; drag the strip wider to see their names"""

    bl_idname = "fresing.make_switch"
    bl_label = "Show this output"
    bl_options = set()

    key: StringProperty(name="Output", default="", options={"SKIP_SAVE"},
                        description="Which output: still, product, turn, web, anim or queue")

    @classmethod
    def description(cls, context, properties):
        key = getattr(properties, "key", "") or ""
        o = outputs().get(key)
        if o is None:
            return " ".join(cls.__doc__.split())
        return f"{o[0]}: {ui_top.MAKE_LINES.get(key, '')}. Shows its settings in this window"

    def execute(self, context):
        why = switch(context.window, self.key)
        if why:
            self.report({"INFO" if "open already" in why else "WARNING"}, why)
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_PT_make_strip(bpy.types.Panel):
    """Task 0308: every output of Make on the left of an output window – icons; names too when dragged wider."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_label = "Outputs"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return ops_setup._is_output(getattr(context, "window", None))

    def draw(self, context):
        from . import make_icons
        key = context.window.screen.get(OUTPUT_MARK)
        region = context.region
        scale = context.preferences.system.ui_scale or 1.0
        wide = region is not None and region.width / scale >= NAMES_FROM
        if not bpy.app.background:
            keep_filled(context.window)
        col = self.layout.column(align=True)
        col.scale_y = ui_top.ROW_SCALE
        for k, text, icon, *_rest in ui_top._outputs(context.scene):
            op = make_icons.icon_button(col, "fresing.make_switch", k, icon, text=text if wide else "",
                                        depress=(k == key))
            op.key = k


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


CLASSES = (FRESING_OT_make_window, FRESING_OT_make_close, FRESING_OT_make_fold, FRESING_OT_make_switch,
           FRESING_PT_make_window, FRESING_PT_make_strip)
