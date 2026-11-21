"""The Set-up window (task 0062, the owner's pick "float 2" of study 0200): the window and its step buttons.

What the window shows is ui_setup.py (the tab "Set-up": one step of a set-up at a time). This file opens it and
moves through the steps.

**How the window is made** (measured in study 0200 and again here, Blender 5.2.3): Blender gives a script no way
to open a window of a chosen size. ``screen.area_dupli`` copies an area into a window of its own, and that window
gets the area's size and place. So a piece of the main window's 3D view (top left) is split off, copied into a
window and closed again in the main window:

    split left  →  (the piece has its size only after a redraw: a timer waits for it)  →  split its top
    →  wait  →  ``area_dupli``  →  close the two pieces (the 3D view gets its space back, to the pixel)

**Its size.** A script cannot set a side panel's width either: the copy's side panel is as wide as the main
view's. So the window is made exactly that wide (292 px at UI scale 1.04 by default; wider when the user dragged
his side panel wider) and ``HEIGHT`` high: the panel fills the window, no strip of 3D view beside it. (The
prototype's 380 px left 100 px of empty view.) A side panel that does not fit its area is squeezed to it, never
hidden – measured with and without Preferences > Region Overlap.

The new window's screen is marked (``screen["fr_setup"] = 1``, saved with the project): ``is_setup_window`` reads
it, the panel's ``poll`` shows the tab only there, and code that puts every 3D view on the Fresing tab leaves such
a window alone. A side panel's tab can be set only after the panel has drawn its tabs once
(``Region.active_panel_category`` is read-only before): ``restore_tabs`` tries on a timer. Call it after a project
is loaded – Blender brings the window back with the project, the tab it was on too, but a handler that sets
"Fresing" everywhere would win.

The 3D view of the copy is switched to what costs nothing and shows nothing: solid shading (a copy of a view in
Rendered mode would start a second render), no overlays, no gizmos, no header, no toolbar, no "adjust last operation" box, looking at
an empty spot far from the model (with Region Overlap the view shows behind the panel). The tool header goes away only when it is
switched off while the header is still on (its setting reads "off" as soon as the header is hidden, but it stays).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from . import ui_setup
from .ui_setup import MARK, SETUPS, STEP_OF, TAB

HEIGHT = 560                   # the window's height, px at UI scale 1.0
SIDE = 280                     # its width when the main view's side panel is closed: Blender's own panel width
WIDEST = 520                   # … and at most this wide, however wide the user's side panel is (same unit)
KEEP = 60                      # what the main 3D view must keep beside / under the piece that is split off
SMALLEST = 150                 # a piece smaller than this is not worth a split: the window takes the view's size
EDGE = 7                       # px a split-off piece must be wider than its side panel (borders, the split's grid)
FAR = (1.0e5, 1.0e5, 1.0e5)    # where the copy's 3D view looks: nothing there
PICKERS = ("fresing.cnc_zero_click",)      # operators that wait for a click in the 3D view: run in the main window

_STATE = {"busy": False, "gen": 0}


# ---------------------------------------------------------------------------------------------------------------
# which window is which
# ---------------------------------------------------------------------------------------------------------------

def is_setup_window(window) -> bool:
    """True when ``window`` is a Set-up window (its screen carries the mark)."""
    try:
        return bool(window is not None and window.screen.get(MARK))
    except (AttributeError, ReferenceError):
        return False


def setup_windows() -> list:
    """Every open Set-up window."""
    wm = getattr(bpy.context, "window_manager", None)
    return [w for w in wm.windows if is_setup_window(w)] if wm is not None else []


def busy() -> bool:
    """A window (Set-up or output) is being opened."""
    return bool(_STATE["busy"])


def main_view(context=None) -> tuple:
    """(window, area, region) of the 3D view the user works in: the window the button was pressed in when that is
    not a Set-up window, else the first other window with a 3D view; its biggest 3D view. (None, None, None)
    without one."""
    context = context or bpy.context
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None, None, None
    wins = [w for w in wm.windows if not tab_of(w)]
    cur = getattr(context, "window", None)
    wins.sort(key=lambda w: w != cur)
    for win in wins:
        areas = [a for a in win.screen.areas if a.type == "VIEW_3D"]
        if not areas:
            continue
        here = getattr(context, "area", None)
        area = here if win == cur and here in areas else max(areas, key=lambda a: a.width * a.height)
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        return win, area, region
    return None, None, None


def redraw_all() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        for area in win.screen.areas:
            area.tag_redraw()


# ---------------------------------------------------------------------------------------------------------------
# the kind and the step (stored in the project)
# ---------------------------------------------------------------------------------------------------------------

def set_kind(scene, kind: str) -> None:
    """Shows another set-up, from its first step. The same kind again changes nothing."""
    s = scene.fresing
    was, _k, _steps = ui_setup.current(scene)
    if kind != s.setup_kind:
        s.setup_kind = kind
    if kind != was or scene.get(STEP_OF) != kind:
        go(scene, 0 if kind != was else ui_setup.current(scene)[1])
    _KEPT[scene.name] = (s.setup_kind, s.setup_step, scene.get(STEP_OF, ui_setup.current(scene)[0]))
    _watch_loads()


def go(scene, step: int) -> int:
    """Goes to a step of the scene's set-up, clamped to its steps; returns the step it went to."""
    kind, _k, steps = ui_setup.current(scene)
    step = max(0, min(int(step), len(steps) - 1))
    if scene.fresing.setup_step != step:
        scene.fresing.setup_step = step
    if scene.get(STEP_OF) != kind:
        scene[STEP_OF] = kind
    _KEPT[scene.name] = (scene.fresing.setup_kind, step, kind)
    _watch_loads()
    return step


# Task 0213: the kind and the step are saved with the project, but Ctrl+Z must not throw the window back (a memfile
# undo of any other action restored the step of that moment). The last ones picked are kept here, outside undo's
# reach, and put back after an undo or redo. A project that opens starts from what it saved.
_KEPT: dict = {}                          # scene name -> (setup_kind, setup_step, the kind the step counts in)


@persistent
def _after_undo(_dummy=None):
    for name, (kind, step, of) in list(_KEPT.items()):
        scene = bpy.data.scenes.get(name)
        if scene is None or getattr(scene, "fresing", None) is None:
            continue
        s = scene.fresing
        if (s.setup_kind, s.setup_step, scene.get(STEP_OF)) == (kind, step, of):
            continue
        try:
            if s.setup_kind != kind:
                s.setup_kind = kind
            if s.setup_step != step:
                s.setup_step = step
            if scene.get(STEP_OF) != of:
                scene[STEP_OF] = of
        except (TypeError, ValueError, AttributeError):     # a kind this version no longer has
            _KEPT.pop(name, None)
            continue
        redraw_all()


# ---------------------------------------------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------------------------------------------

@persistent
def _on_load(_dummy=None):
    _STATE["gen"] += 1                      # a window that was being opened belongs to the project before
    _STATE["busy"] = False
    _KEPT.clear()


_UNDO_LISTS = ("undo_post", "redo_post")


def _watch_loads() -> None:
    if _on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load)
    for name in _UNDO_LISTS:
        lst = getattr(bpy.app.handlers, name)
        if _after_undo not in lst:
            lst.append(_after_undo)


def _dress(window) -> None:
    """The Set-up window's 3D view shows the side panel and nothing that costs time or space. Sets only what is
    not so yet: it runs again whenever the tab is put back."""
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        tool_header = next((r for r in area.regions if r.type == "TOOL_HEADER"), None)
        if sp.show_region_header or (tool_header is not None and tool_header.height > 1):
            sp.show_region_header = True            # the tool header can only be switched off while this is on
            sp.show_region_tool_header = False
            sp.show_region_header = False
        for name, value in (("show_region_ui", True), ("show_region_toolbar", False),
                            ("show_region_asset_shelf", False), ("show_region_hud", False),
                            ("show_gizmo", False), ("lock_camera", False)):
            if getattr(sp, name, value) != value:
                setattr(sp, name, value)
        if sp.overlay.show_overlays:
            sp.overlay.show_overlays = False
        if sp.shading.type != "SOLID":
            sp.shading.type = "SOLID"
        rv = sp.region_3d
        if rv is not None and tuple(rv.view_location) != FAR:
            if rv.view_perspective == "CAMERA":
                rv.view_perspective = "ORTHO"
            rv.view_location = FAR
            rv.view_distance = 1.0


OUTPUT_MARK = "fr_output"      # task 0260: an output window of Make (ops_make.py): screen ID property = the output's key
OUTPUT_TAB = "Make"


def tab_of(window) -> str:
    """The side-panel tab of an app window: "Set-up" or "Make" ("" for any other window)."""
    try:
        screen = window.screen
        return TAB if screen.get(MARK) else (OUTPUT_TAB if screen.get(OUTPUT_MARK) else "")
    except (AttributeError, ReferenceError):
        return ""


def app_windows() -> list:
    """Every open Set-up window and output window."""
    wm = getattr(bpy.context, "window_manager", None)
    return [w for w in wm.windows if tab_of(w)] if wm is not None else []


def _show_tab(window) -> bool:
    """Puts the window's side panel on its tab (Set-up, or Make for an output window); False when the tabs are not
    drawn yet (try again)."""
    ok = True
    tab = tab_of(window) or TAB
    _dress(window)
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for region in area.regions:
            if region.type != "UI":
                continue
            try:
                if region.active_panel_category != tab:
                    region.active_panel_category = tab
            except (AttributeError, TypeError, ValueError):
                ok = False
        area.tag_redraw()
    return ok


def restore_tabs() -> None:
    """Puts every Set-up window's side panel (back) on the "Set-up" tab – after a project is loaded, and after the
    window opened. The tab can be set only once the panel has drawn: tried for up to 15 seconds on a timer."""
    if bpy.app.background:
        return
    tries = [0]

    def later():
        tries[0] += 1
        try:
            waiting = [w for w in app_windows() if not _show_tab(w)]
        except ReferenceError:
            return None
        return 0.25 if waiting and tries[0] < 60 else None       # a new window's first drawing can take seconds

    bpy.app.timers.register(later, first_interval=0.1)


def _alive(job) -> bool:
    """The main window and the pieces of this job still exist (no project was opened meanwhile)."""
    if job["gen"] != _STATE["gen"]:
        return False
    wm = bpy.context.window_manager
    win = job["win"]
    if not any(w == win for w in wm.windows):
        return False
    areas = win.screen.areas[:]
    return all(any(a == p for a in areas) for p in job["pieces"])


def _split(job, direction: str) -> bool:
    """Splits the piece the window is made from: its left part (VERTICAL) or its top part (HORIZONTAL), as big as
    wanted or as big as the 3D view allows. False when the view is too small to split at all – the window then
    takes the view's own width or height."""
    win, piece = job["win"], job["piece"]
    size, want = (piece.width, job["w"]) if direction == "VERTICAL" else (piece.height, job["h"])
    want = min(want, size - job["keep"])
    if want < job["smallest"]:
        return False
    factor = want / size if direction == "VERTICAL" else 1.0 - want / size
    before = win.screen.areas[:]
    try:
        with bpy.context.temp_override(window=win, screen=win.screen, area=piece):
            bpy.ops.screen.area_split(direction=direction, factor=factor)
    except RuntimeError:                       # Blender refuses (an area shown full screen …)
        return False
    new = [a for a in win.screen.areas if a not in before]
    if not new:
        return False
    job["pair"] = (piece, new[0], direction, size)
    job["pieces"].append(new[0])
    return True


def _settled(job) -> bool:
    """The two halves of the last split have their sizes (they get them at the redraw after the split)."""
    if not job["pair"]:
        return True
    a, b, direction, size = job["pair"]
    got = a.width + b.width if direction == "VERTICAL" else a.height + b.height
    return min(a.width, b.width, a.height, b.height) > 1 and abs(got - size) <= 16


def _take(job) -> None:
    """Of the two halves of the last split, the left / top one is the piece to go on with; both are closed later
    (the piece itself first, then the other half: each time the neighbour with the same edge gets the space)."""
    if not job["pair"]:
        return
    a, b, direction, _size = job["pair"]
    job["pair"] = None
    if direction == "VERTICAL":
        piece = a if a.x < b.x else b
        job["close"] = [piece]
    else:
        piece = a if a.y > b.y else b
        other = b if piece == a else a
        job["close"] = [piece] + ([other] if job["close"] else [])
    job["piece"] = piece


def _finish(job) -> None:
    """Copies the piece into a window of its own, closes the pieces in the main window, marks the new window."""
    wm = bpy.context.window_manager
    win = job["win"]
    before = wm.windows[:]
    with bpy.context.temp_override(window=win, screen=win.screen, area=job["piece"]):
        bpy.ops.screen.area_dupli("INVOKE_DEFAULT")
    _close(job)
    new = [w for w in wm.windows if w not in before]
    if not new:
        print("Fresing Render: the Set-up window did not open (Blender made no window)")
        return
    new[0].screen[job.get("mark", MARK)] = job.get("value", 1)
    _dress(new[0])
    restore_tabs()
    redraw_all()
    done = job.get("done")
    if done is not None:                     # task 0260: an output window is placed where it was last time
        try:
            done(new[0])
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: the window opened, not placed:", exc)


def _close(job) -> None:
    win = job["win"]
    for area in job["close"]:
        if not any(a == area for a in win.screen.areas) or len(win.screen.areas) < 2:
            continue
        with bpy.context.temp_override(window=win, screen=win.screen, area=area):
            bpy.ops.screen.area_close()
    job["close"] = []


def _run(job):
    """One timer step of opening the window; returns the wait to the next step, or None when done."""
    try:
        if not _alive(job):
            _STATE["busy"] = False
            return None
        from . import editors
        if not editors.settled():          # task 0221: an area was just closed or split – sizes are stale
            job["waits"] = job.get("waits", 0) + 1
            if job["waits"] < 100:
                return 0.05
        if not _settled(job):
            job["tries"] += 1
            if job["tries"] < 40:
                return 0.05
            raise RuntimeError("the split-off view did not get its size")
        job["tries"] = 0
        _take(job)
        if job["todo"]:
            _split(job, job["todo"].pop(0))
            return 0.1 if job["pair"] else 0.0
        _finish(job)
    except Exception as exc:  # noqa: BLE001 - never leave the main window split
        print("Fresing Render: the Set-up window did not open:", exc)
        try:
            if job["pair"]:
                job["close"] = [p for p in job["pieces"]][::-1]
            _close(job)
        except Exception:  # noqa: BLE001
            pass
    _STATE["busy"] = False
    return None


def window_size(area) -> tuple:
    """(width, height) in px of the piece of ``area`` the window is made from: as wide as the area's side panel
    (the copy's panel then fills the window), ``HEIGHT`` high."""
    scale = bpy.context.preferences.system.ui_scale or 1.0
    side = next((r.width for r in area.regions if r.type == "UI"), 0)
    if side < 150 * scale:                          # the side panel is closed: its width cannot be read
        side = int(SIDE * scale)
    return min(side, int(WIDEST * scale)) + EDGE, int(HEIGHT * scale)


def open_window(window, area, mark: str = MARK, value=1, done=None) -> None:
    """Starts opening the Set-up window from a piece of ``area`` (a 3D view of ``window``); it is there about a
    quarter of a second later (timers: see the top of this file). Task 0221: while Blender's right-hand column is
    being closed or opened (``editors.busy``, right after a project opened) the 3D view's size is about to change:
    the split waits for it."""
    from . import editors
    if not editors.busy():
        _open_window(window, area, mark, value, done)
        return
    _STATE["busy"] = True
    gen, tries = _STATE["gen"], [0]

    def later():
        tries[0] += 1
        if editors.busy() and tries[0] < 100:
            return 0.05
        _STATE["busy"] = False
        try:
            if gen == _STATE["gen"] and any(w == window for w in bpy.context.window_manager.windows):
                views = [a for a in window.screen.areas if a.type == "VIEW_3D"]     # found again: areas changed
                if views:
                    _open_window(window, max(views, key=lambda a: a.width * a.height), mark, value, done)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: the Set-up window did not open:", exc)
        return None

    bpy.app.timers.register(later, first_interval=0.05)


def _open_window(window, area, mark: str = MARK, value=1, done=None) -> None:
    scale = bpy.context.preferences.system.ui_scale or 1.0
    w, h = window_size(area)
    _watch_loads()
    _STATE["busy"] = True
    job = {"win": window, "piece": area, "pieces": [], "pair": None, "close": [], "tries": 0,
           "todo": ["VERTICAL", "HORIZONTAL"], "w": w, "h": h, "keep": int(KEEP * scale),
           "smallest": int(SMALLEST * scale), "gen": _STATE["gen"], "mark": mark, "value": value, "done": done}
    try:
        _split(job, job["todo"].pop(0))
        bpy.app.timers.register(lambda: _run(job), first_interval=0.1 if job["pair"] else 0.0)
    except Exception:
        _STATE["busy"] = False
        raise


# ---------------------------------------------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------------------------------------------

def _kind_items() -> list:
    return [(k, title, f"The steps of '{title}': " + ", ".join(t for t, _fn in steps),
             ui_setup.KIND_ICONS.get(k, "NONE"), i) for i, (k, (title, steps)) in enumerate(SETUPS.items())]


class FRESING_OT_setup_window(bpy.types.Operator):
    """Opens the Set-up window: a small window of its own that takes you through a set-up one step at a time, with
    the same buttons as the side panel. Drag it where it suits you, also onto a second screen, and click parts
    in the main window as usual"""

    bl_idname = "fresing.setup_window"
    bl_label = "Set-up window"
    bl_options = set()         # (not REGISTER: no "adjust last operation" box in the 3D view for a window button)

    kind: StringProperty(
        name="Set-up", default="", options={"SKIP_SAVE"},
        description="Which set-up the window shows: CNC (a CNC mill) or MECH (a mechanism). Empty: the one the "
                    "project was on")

    @classmethod
    def description(cls, context, properties):
        entry = SETUPS.get(getattr(properties, "kind", "") or "")
        if entry is None:
            return " ".join(cls.__doc__.split())
        title, steps = entry
        return (f"Opens the Set-up window on '{title}': " + ", ".join(t for t, _fn in steps) + ", one step at a "
                "time with the same buttons as the side panel. Drag the window where it suits you and click "
                "parts in the main window as usual")

    @classmethod
    def unregister(cls):
        while _on_load in bpy.app.handlers.load_pre:
            bpy.app.handlers.load_pre.remove(_on_load)
        for name in _UNDO_LISTS:
            lst = getattr(bpy.app.handlers, name)
            while _after_undo in lst:
                lst.remove(_after_undo)
        _STATE["busy"] = False
        _KEPT.clear()

    def execute(self, context):
        scene = context.scene
        if self.kind:
            if self.kind not in SETUPS:
                self.report({"ERROR"}, f"No set-up is called '{self.kind}'")
                return {"CANCELLED"}
            set_kind(scene, self.kind)
        if bpy.app.background:
            self.report({"INFO"}, "The Set-up window opens only in the app's own window, not in a background run")
            return {"CANCELLED"}
        if setup_windows():
            restore_tabs()
            redraw_all()
            self.report({"INFO"}, f"The Set-up window is open: it shows '{SETUPS[ui_setup.current(scene)[0]][0]}'")
            return {"FINISHED"}
        if _STATE["busy"]:
            return {"CANCELLED"}
        win, area, _region = main_view(context)
        if area is None:
            self.report({"WARNING"}, "The Set-up window needs a 3D view in the main window")
            return {"CANCELLED"}
        if win.screen.show_fullscreen:
            self.report({"WARNING"}, "The 3D view fills the whole window: go back to the normal layout first "
                                     "(Ctrl+Space), then open the Set-up window")
            return {"CANCELLED"}
        open_window(win, area)
        return {"FINISHED"}


class FRESING_OT_setup_kind(bpy.types.Operator):
    """Shows the steps of this set-up in the Set-up window, starting at its first step"""

    bl_idname = "fresing.setup_kind"
    bl_label = "Set-up"
    bl_options = {"INTERNAL"}

    kind: EnumProperty(name="Set-up", items=_kind_items(),
                       description="The set-up whose steps the Set-up window shows")

    def execute(self, context):
        set_kind(context.scene, self.kind)
        redraw_all()
        return {"FINISHED"}


class FRESING_OT_setup_go(bpy.types.Operator):
    """Goes to this step of the set-up. What you did in the other steps stays as it is"""

    bl_idname = "fresing.setup_go"
    bl_label = "Go to step"
    bl_options = {"INTERNAL"}

    step: IntProperty(name="Step", default=0, options={"SKIP_SAVE"},
                      description="The step to show, counted from 0. A number outside the set-up's steps goes to "
                                  "its first or last step")
    done: BoolProperty(name="Done", default=False, options={"SKIP_SAVE", "HIDDEN"},
                       description="The Done button of the last step: stays on the step and says in the status "
                                   "bar which steps are still open")

    @classmethod
    def description(cls, context, properties):
        scene = getattr(context, "scene", None)
        if scene is None or not hasattr(scene, "fresing"):
            return " ".join(cls.__doc__.split())
        _kind, k, steps = ui_setup.current(scene)
        if getattr(properties, "done", False):
            return ("The last step of this set-up. The window stays open: go back to any step with its number, or "
                    "pick another set-up at the top")
        to = max(0, min(int(getattr(properties, "step", 0) or 0), len(steps) - 1))
        name = f"step {to + 1} of {len(steps)}: {steps[to][0]}"
        if to == k:
            return f"This is {name}. The other numbers go to their steps; a tick marks a step that is done"
        word = "on" if to == k + 1 else ("back" if to == k - 1 else "straight")
        return f"Goes {word} to {name}. What you did in the other steps stays as it is"

    def execute(self, context):
        scene = context.scene
        go(scene, self.step)
        redraw_all()
        if self.done:
            kind, _k, steps = ui_setup.current(scene)
            left = [steps[i][0] for i in range(len(steps)) if ui_setup.CHECKS[kind][i] is not None
                    and not ui_setup.is_done(context, kind, i)]
            if left:
                self.report({"INFO"}, f"Still open in '{SETUPS[kind][0]}': " + ", ".join(left))
            else:
                self.report({"INFO"}, f"'{SETUPS[kind][0]}': every step is done")
        return {"FINISHED"}


class FRESING_OT_setup_in_view(bpy.types.Operator):
    """Starts this button in the main window's 3D view: click there, the Set-up window stays open. Esc cancels"""

    bl_idname = "fresing.setup_in_view"
    bl_label = "Click in the main window"
    bl_options = {"INTERNAL"}

    op: StringProperty(name="Button", default="", options={"SKIP_SAVE"},
                       description="The button to start in the main window's 3D view (one that waits for a click "
                                   "on the model)")

    @classmethod
    def description(cls, context, properties):
        name = getattr(properties, "op", "") or ""
        text = ""
        if name in PICKERS:
            group, _, op = name.partition(".")
            try:
                text = getattr(getattr(bpy.ops, group), op).get_rna_type().description
            except Exception:  # noqa: BLE001
                text = ""
        text = " ".join(text.split()).rstrip(".")
        return (text + ". Click in the main window: the Set-up window stays open") if text \
            else " ".join(cls.__doc__.split())

    def execute(self, context):
        if self.op not in PICKERS:
            self.report({"ERROR"}, f"'{self.op}' is not a button that picks in the 3D view")
            return {"CANCELLED"}
        win, area, region = main_view(context)
        if bpy.app.background or area is None or region is None:
            self.report({"WARNING"}, "This needs a 3D view in the main window")
            return {"CANCELLED"}
        group, _, op = self.op.partition(".")
        with context.temp_override(window=win, screen=win.screen, area=area, region=region):
            res = getattr(getattr(bpy.ops, group), op)("INVOKE_DEFAULT")
        if "CANCELLED" in res:
            return {"CANCELLED"}
        redraw_all()
        return {"FINISHED"}


class FRESING_OT_setup_close(bpy.types.Operator):
    """Closes the Set-up window. The step you were on is kept in the project: the window opens there again"""

    bl_idname = "fresing.setup_close"
    bl_label = "Close the Set-up window"
    bl_options = set()         # (not REGISTER: no "adjust last operation" box in the 3D view for a window button)

    @classmethod
    def poll(cls, context):
        return bool(setup_windows())

    def execute(self, context):
        if is_setup_window(context.window):
            # pressed in the Set-up window itself: Blender still needs this window until the button is done
            bpy.app.timers.register(close_windows, first_interval=0.01)
        else:
            close_windows()
        return {"FINISHED"}


def close_windows() -> None:
    """Closes every Set-up window (the main window stays as it is)."""
    for win in setup_windows():
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.wm.window_close()
    redraw_all()


CLASSES = (FRESING_OT_setup_window, FRESING_OT_setup_kind, FRESING_OT_setup_go, FRESING_OT_setup_in_view,
           FRESING_OT_setup_close)
