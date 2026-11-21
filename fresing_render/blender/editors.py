"""Blender's right-hand column hidden, Show / Hide in the Fresing menu, a solid side panel (task 0221).

* **The column.** Blender's default layout has the Outliner (top right) and the Properties editor (below it) in a
  column right of the 3D view. Fresing Render needs neither (the Fresing tab has its own parts tree and every setting
  the app uses), so the app closes them and the 3D view reaches the window's right edge. Only an Outliner or
  Properties area whose left edge touches the main 3D view's right edge is closed; any other layout is left alone.
  **Fresing > Show Blender's editors** splits the main 3D view at its right side again (Blender's default width,
  Outliner on top, Properties below); the same entry then says **Hide Blender's editors**.
* **The choice** is the user's, not the project's: one small file in Blender's settings folder
  (``<config>/fresing_layout.json``), default hidden. Every load the app tidies (``ui_header._on_load``) follows it,
  so a project saved with the column shown opens hidden for a user who chose hidden.
* **Client view** (``lock.py``): the column is hidden while the lock is on and the menu entry is greyed; the lock
  going off puts back what the user chose.
* **Solid side panel.** Blender's preference *Region Overlap* draws the side panel see-through over the 3D view. The
  app switches it off once (the first start of this version, remembered in the same file) and whenever Blender's
  preferences are reset (the app template's ``_set_preferences``); a user who turns it on again keeps it.

Nothing here runs in a background Blender (queue, PC check, self-test, kit): no screens there, preferences untouched.
"""

from __future__ import annotations

import json
import os

import bpy

FILE_NAME = "fresing_layout.json"
TYPES = ("OUTLINER", "PROPERTIES")      # the two editors of Blender's right-hand column
WIDTH = 0.177                # the column's width as a share of the window (Blender 5.2.3's factory layout, measured at
OUTLINER = 0.184             # 1920 and 2560 px: 339 / 1920, 453 / 2560); the Outliner's share of the column's height
EDGE = 12                    # px: an area whose left edge lies this close right of the 3D view's right edge touches it
SETUP_MARK = "fr_setup"      # the Set-up window's screen (task 0062): never touched


# ---------------------------------------------------------------------------
# the user's choice (a file in Blender's settings folder)
# ---------------------------------------------------------------------------

def fresh() -> dict:
    return {"editors": "hidden", "overlap_off": False}


def read(path: str) -> dict:
    """The state in ``path``; a missing or broken file gives the defaults."""
    out = fresh()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    if isinstance(data, dict):
        if data.get("editors") in ("hidden", "shown"):
            out["editors"] = data["editors"]
        if isinstance(data.get("overlap_off"), bool):
            out["overlap_off"] = data["overlap_off"]
    return out


def write(path: str, state: dict) -> None:
    """Write the state (a temporary file first, so a crash never leaves half a file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, path)


def state_path() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), FILE_NAME)


def load() -> dict:
    return read(state_path())


def save(state: dict) -> None:
    try:
        write(state_path(), state)
    except OSError as exc:
        print("Fresing Render: could not save the layout choice:", exc)


def chosen_shown() -> bool:
    """Has the user chosen to see Blender's editors?"""
    return load()["editors"] == "shown"


def choose(shown: bool) -> None:
    state = load()
    state["editors"] = "shown" if shown else "hidden"
    save(state)


def locked() -> bool:
    from . import lock
    return bool(lock.ON[0])


def wanted() -> bool:
    """Should the column be shown now? The user's choice, never in the Client view."""
    return chosen_shown() and not locked()


# ---------------------------------------------------------------------------
# which areas are the column (plain numbers: tested without windows)
# ---------------------------------------------------------------------------

def main_index(rects) -> int:
    """The main 3D view: the biggest one. ``rects`` = [(type, x, y, width, height), …]; -1 when there is none."""
    best, size = -1, -1
    for i, (kind, _x, _y, w, h) in enumerate(rects):
        if kind == "VIEW_3D" and w * h > size:
            best, size = i, w * h
    return best


def column_indices(rects, main: int, swapped=()) -> list:
    """The areas of Blender's right-hand column: an Outliner or a Properties editor (or an Outliner the Client view
    turned into Info: ``swapped``) whose left edge touches the main 3D view's right edge and that lies beside it."""
    if main < 0:
        return []
    _k, mx, my, mw, mh = rects[main]
    if mw <= 0 or mh <= 0:
        return []
    out = []
    for i, (kind, x, y, w, h) in enumerate(rects):
        if i == main or not (kind in TYPES or (kind == "INFO" and i in swapped)):
            continue
        if not (mx + mw - 2 <= x <= mx + mw + EDGE):
            continue
        if y < my + mh and y + h > my:            # beside the 3D view, not above or below it
            out.append(i)
    return out


def split_factor(window_width: int, view_width: int) -> float:
    """The 3D view's share that stays left when the column is split off it (Blender's default column width)."""
    if view_width <= 0:
        return 0.8
    return min(0.95, max(0.5, 1.0 - WIDTH * window_width / view_width))


def _rects(screen) -> list:
    return [(a.type, a.x, a.y, a.width, a.height) for a in screen.areas]


def _swapped(screen) -> tuple:
    from . import lock
    return tuple(screen.get(lock.SCREEN_MARK, ()))


def _windows():
    wm = bpy.context.window_manager
    if wm is None or bpy.app.background:
        return []
    from .panels import side_window
    return [w for w in wm.windows if w.screen is not None and not side_window(w)]   # task 0260: output windows too


def column(win) -> list:
    """The column's areas in this window."""
    rects = _rects(win.screen)
    return [win.screen.areas[i] for i in column_indices(rects, main_index(rects), _swapped(win.screen))]


def shown(win=None) -> bool:
    """Does this window (the first one) show Blender's column?"""
    wins = [win] if win is not None else _windows()[:1]
    return any(column(w) for w in wins)


# ---------------------------------------------------------------------------
# hide and show
# ---------------------------------------------------------------------------

def _forget_swapped(screen, i: int) -> None:
    """Area ``i`` is closed: the Client view's list of swapped Outliners (by index) follows."""
    from . import lock
    if lock.SCREEN_MARK not in screen:
        return
    marks = [j - (j > i) for j in screen[lock.SCREEN_MARK] if j != i]
    if marks:
        screen[lock.SCREEN_MARK] = marks
    else:
        del screen[lock.SCREEN_MARK]


# Blender 5.2.3 crashes when a 3D view's settings are set after an area beside it was closed and before the window
# was drawn again (measured: ``show_region_toolbar`` set right after ``area_close`` – also with the window drawn
# before, also after ``wm.redraw_timer``; reading is safe). So after a close or a split nothing sets a 3D view's
# settings until a 3D view was drawn: ``settled()`` (``ui_header.put_layout_right`` waits for it, so does ``apply``).
_SETTLING = [False]
_DRAW = [None]


def _drawn():
    _SETTLING[0] = False


def settled() -> bool:
    return not _SETTLING[0]


def busy() -> bool:
    """The column is about to be closed or opened (a request waits) or was just changed (not drawn yet): a 3D view's
    size is about to change. The Set-up window waits before it splits the view."""
    return _SETTLING[0] or bpy.app.timers.is_registered(_run_request)


def hide(win) -> int:
    """Close the column of this window. Returns how many areas were closed."""
    screen = win.screen
    n = 0
    for _ in range(8):
        rects = _rects(screen)
        idx = column_indices(rects, main_index(rects), _swapped(screen))
        if not idx:
            break
        i = idx[-1]
        area = screen.areas[i]
        with bpy.context.temp_override(window=win, screen=screen, area=area):
            if "FINISHED" not in bpy.ops.screen.area_close():
                break
        _forget_swapped(screen, i)
        _SETTLING[0] = True
        n += 1
    return n


def show(win) -> bool:
    """Bring the column back at the main 3D view's right side. False when it cannot be done yet (the window has not
    been drawn) or there is no 3D view."""
    screen = win.screen
    if column(win):
        return True
    rects = _rects(screen)
    m = main_index(rects)
    if m < 0 or rects[m][3] <= 0:
        return False
    view = screen.areas[m]
    n0 = len(screen.areas)
    with bpy.context.temp_override(window=win, screen=screen, area=view):
        if "FINISHED" not in bpy.ops.screen.area_split(direction="VERTICAL",
                                                        factor=split_factor(win.width, view.width)):
            return False
    _SETTLING[0] = True
    if len(screen.areas) <= n0:
        return False
    right = screen.areas[n0]
    right.ui_type = "PROPERTIES"
    with bpy.context.temp_override(window=win, screen=screen, area=right):
        bpy.ops.screen.area_split(direction="HORIZONTAL", factor=1.0 - OUTLINER)
    if len(screen.areas) > n0 + 1:
        screen.areas[n0 + 1].ui_type = "OUTLINER"
    return True


def apply(want: bool | None = None) -> bool:
    """Every window follows the choice (``want``; None = the user's choice, hidden in the Client view). True when every
    window is done (False: try again after a redraw)."""
    if bpy.app.background:
        return True
    if not settled():
        return False
    if want is None:
        want = wanted()
    done = True
    for win in _windows():
        try:
            if want:
                done = show(win) and done
            else:
                hide(win)
        except Exception as exc:  # noqa: BLE001 - never break loading or the lock over the layout
            print("Fresing Render: Blender's editors not", "shown:" if want else "hidden:", exc)
    for win in _windows():
        for area in win.screen.areas:
            area.tag_redraw()
    return done


_PENDING = {"want": None, "tries": 0}     # what the requested timer applies (None: the user's choice)


def _run_request():
    _PENDING["tries"] += 1
    if apply(_PENDING["want"]) or _PENDING["tries"] >= 100:
        return None
    return 0.05                      # a window not drawn yet (after a load, a close or a split): again after a redraw


def request(want: bool | None = None) -> None:
    """``apply`` a moment later, from a timer. Closing areas inside a load handler (the lock goes on or off while a
    project opens) crashed Blender 5.2.3: screens are changed only once the window is up."""
    if bpy.app.background:
        return
    _PENDING["want"], _PENDING["tries"] = want, 0
    if not bpy.app.timers.is_registered(_run_request):
        bpy.app.timers.register(_run_request, first_interval=0.0)


# ---------------------------------------------------------------------------
# the solid side panel
# ---------------------------------------------------------------------------

def solid_side_panel(force: bool = False) -> bool:
    """Region Overlap off – once (remembered), or ``force`` (Blender's preferences were reset). True when it was set."""
    if bpy.app.background:
        return False
    state = load()
    if state["overlap_off"] and not force:
        return False
    try:
        bpy.context.preferences.system.use_region_overlap = False
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: Region Overlap not switched off:", exc)
        return False
    state["overlap_off"] = True
    save(state)
    return True


def on_load() -> bool:
    """A project was opened (``ui_header._on_load``): the solid side panel, the column from a timer."""
    if bpy.app.background:
        return True
    solid_side_panel()
    request()
    return True


# ---------------------------------------------------------------------------
# the menu entry
# ---------------------------------------------------------------------------

LOCKED_TEXT = "Not in the Client view – Full access brings it back"


def menu_text() -> str:
    return "Hide Blender's editors" if chosen_shown() else "Show Blender's editors"


class FRESING_OT_blender_editors(bpy.types.Operator):
    """Shows or hides Blender's Outliner and Properties editor at the right of the window. Fresing Render does not
    need them – the Fresing panel has the parts and every setting – they are for users who know Blender. Your choice
    is kept for every project and the next start"""

    bl_idname = "fresing.blender_editors"
    bl_label = "Show Blender's editors"

    @classmethod
    def poll(cls, context):
        if locked():
            cls.poll_message_set(LOCKED_TEXT)
            return False
        return not bpy.app.background

    @classmethod
    def description(cls, context, props):
        doc = " ".join((cls.__doc__ or "").split())
        if locked():
            return LOCKED_TEXT + ". " + doc
        return doc

    def execute(self, context):
        want = not chosen_shown()
        choose(want)
        if not apply(want):
            request(want)                    # a window not drawn since the last change: after the next redraw
        self.report({"INFO"}, "Blender's Outliner and Properties shown" if want else
                    "Blender's Outliner and Properties hidden (Fresing > Show Blender's editors brings them back)")
        return {"FINISHED"}


CLASSES = (FRESING_OT_blender_editors,)


def register_handlers() -> None:
    if bpy.app.background or _DRAW[0] is not None:
        return
    _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_drawn, (), "WINDOW", "POST_PIXEL")


def unregister_handlers() -> None:
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    _SETTLING[0] = False
