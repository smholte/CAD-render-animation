"""The "Making the Learning hub" card (task 0275): a card in the middle of the main 3D view that says the hub is being
made, how far it is, the time left, that the user may keep working – and, when it is done, that it is ready (Open it
now / Later) or what failed (Try again).

**Why a drawn card with its own clicks** (not an app window like 0260's, not a popup): a popup blocks Blender while it
is open and cannot refresh; an app window needs a split of the 3D view and a settle timer (``ops_setup.open_window``) –
a second of work during which nothing shows, and the hub is made while the user is just starting. A draw handler
(POST_PIXEL) shows the card at the first redraw, refreshes on the build's own timer and never takes Blender's thread;
its buttons are hit-tested by ``FRESING_OT_tour_make``'s modal, which already runs for the whole build and passes
every other event on.

States (``STATE["mode"]``): ``progress`` · ``confirm`` (Stop making it – asked once) · ``ready`` · ``failed`` · None.
Hide only hides the card (the left panel's line + Show progress and the bottom-left status stay); a result pops it up
again. The words are in ``core/hub_progress.py``.
"""

from __future__ import annotations

import time

import bpy
from bpy.app.handlers import persistent

from ..core import hub_progress as words

STATE: dict = {"mode": None, "hidden": False, "gen": 0, "handle": None, "start": 0.0, "expected": 120.0, "left": None,
               "hub": "", "why": "", "log": "", "folder": "", "only": "", "hover": "", "note": ""}

PAD = 18
WIDTH = 520
BG = (0.12, 0.12, 0.13, 0.96)
EDGE = (0.30, 0.30, 0.32, 1.0)
TEXT = (0.92, 0.92, 0.92, 1.0)
GREY = (0.68, 0.68, 0.70, 1.0)
BAR_BG = (0.24, 0.24, 0.26, 1.0)
BAR = (0.20, 0.52, 0.92, 1.0)
BTN = (0.30, 0.30, 0.33, 1.0)
BTN_HOVER = (0.38, 0.38, 0.43, 1.0)
BTN_MAIN = (0.18, 0.46, 0.84, 1.0)
RED = (0.95, 0.45, 0.40, 1.0)


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def active() -> bool:
    return STATE["mode"] is not None


def visible() -> bool:
    return STATE["mode"] is not None and not STATE["hidden"]


def begin(folder: str, only: str, expected_s: float) -> int:
    """The build started: show the card. Returns this card's generation (the modal ends when it changes)."""
    STATE["gen"] += 1
    STATE.update(mode="progress", hidden=False, start=time.time(), expected=max(30.0, expected_s), left=None, hub="",
                 why="", log="", folder=folder, only=only, hover="", note="")
    _add_handler()
    redraw()
    return STATE["gen"]


def dismiss() -> None:
    STATE.update(mode=None, hidden=False, hover="")
    STATE["gen"] += 1
    _remove_handler()
    redraw()


def finish(mode: str, hub: str = "", why: str = "", log: str = "", note: str = "") -> None:
    """The build ended: ``ready`` or ``failed``. The card pops up even when it was hidden."""
    STATE.update(mode=mode, hidden=False, hub=hub, why=why, log=log, note=note, hover="")
    redraw()


def show() -> None:
    if active():
        STATE["hidden"] = False
        redraw()


def numbers(data: dict) -> dict:
    """What the card shows for the build's progress data (``ops_tour.building()``)."""
    from . import tour
    total = int(data.get("total") or len([k for k in STATE["only"].split(",") if k in tour.SETS]) or len(tour.SETS))
    done = int(data.get("done", 0))
    elapsed = max(0.0, time.time() - STATE["start"])
    left = words.settle(words.seconds_left(done, total, elapsed, STATE["expected"]), STATE["left"])
    STATE["left"] = left
    return {"total": total, "done": done, "fraction": words.fraction(done, total),
            "project": words.project_line(done, total, data.get("step", "")), "left": words.left_text(left)}


def line(data: dict) -> str:
    n = numbers(data)
    return f"Making the Learning hub: {n['project']} – {n['left']}"


def redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        for area in win.screen.areas:
            if area.type in {"VIEW_3D", "TOOLS"}:
                area.tag_redraw()


# ---------------------------------------------------------------------------
# the card: contents, geometry
# ---------------------------------------------------------------------------

def _wrap(text: str, chars: int) -> list:
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > chars:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return out + ([cur] if cur else [])


def contents(data: dict) -> dict:
    """{"title", "body": [(text, colour)], "bar": 0..1 or None, "bar_text", "buttons": [(key, label, main)]}"""
    mode = STATE["mode"]
    if mode == "progress":
        n = numbers(data)
        return {"title": "Making the Learning hub",
                "body": [(t, TEXT) for t in _wrap(words.intro(round(STATE["expected"] / 60)), 62)] + [("", TEXT)]
                        + [(f"{n['project']}   ·   {n['left']}", TEXT)],
                "bar": n["fraction"], "foot": [(t, GREY) for t in _wrap(words.KEEP_WORKING, 62)],
                "buttons": [("hide", "Hide", False), ("stop", "Stop making it", False)]}
    if mode == "confirm":
        return {"title": "Stop making the Learning hub?", "body": [(t, TEXT) for t in _wrap(words.STOP_ASK, 62)],
                "bar": None, "foot": [], "buttons": [("stop_yes", "Yes, stop", True), ("stop_no", "Keep making it", False)]}
    if mode == "ready":
        body = [("It is made. Open it now, or later from the Fresing menu > Learning hub.", TEXT)]
        if STATE["note"]:
            body += [(t, RED) for t in _wrap(STATE["note"], 62)]
        return {"title": "The Learning hub is ready", "body": [(t, c) for t, c in body], "bar": None, "foot": [],
                "buttons": [("open", "Open it now", True), ("later", "Later", False)]}
    if mode == "failed":
        body = [(t, RED) for t in _wrap("The Learning hub could not be made: " + STATE["why"], 62)[:5]]
        if STATE["log"]:
            body += [(t, GREY) for t in _wrap("What happened is in this file: " + STATE["log"], 62)[:3]]
        return {"title": "The Learning hub was not made", "body": body, "bar": None, "foot": [],
                "buttons": [("again", "Try again", True), ("close", "Close", False)]}
    return {}


def _geometry(data: dict) -> dict | None:
    """The card in the main 3D view, in window pixels: {"area", "region", "x", "y", "w", "h", "rows", "buttons", ...}."""
    from . import ops_setup
    win, area, region = ops_setup.main_view()
    if area is None or region is None:
        return None
    c = contents(data)
    if not c:
        return None
    scale = bpy.context.preferences.system.ui_scale or 1.0
    lh = 20 * scale
    pad = PAD * scale
    w = min(WIDTH * scale, region.width - 20)
    rows = len(c["body"]) + len(c["foot"])
    h = pad * 2 + 34 * scale + rows * lh + (30 * scale if c["bar"] is not None else 0) + 52 * scale
    x = region.x + (region.width - w) / 2
    y = region.y + (region.height - h) / 2
    gap = 10 * scale
    bw = (w - 2 * pad - gap * (len(c["buttons"]) - 1)) / len(c["buttons"])
    bh = 32 * scale
    buttons = []
    for i, (key, label, main) in enumerate(c["buttons"]):
        bx = x + pad + i * (bw + gap)
        buttons.append({"key": key, "label": label, "main": main, "x": bx, "y": y + pad, "w": bw, "h": bh})
    return {"area": area, "region": region, "x": x, "y": y, "w": w, "h": h, "c": c, "scale": scale, "lh": lh,
            "pad": pad, "buttons": buttons}


def button_at(mx: float, my: float, data: dict) -> str:
    g = _geometry(data)
    if g is None or not (g["x"] <= mx <= g["x"] + g["w"] and g["y"] <= my <= g["y"] + g["h"]):
        return ""
    for b in g["buttons"]:
        if b["x"] <= mx <= b["x"] + b["w"] and b["y"] <= my <= b["y"] + b["h"]:
            return b["key"]
    return "card"


def button_point(key: str, data: dict) -> tuple | None:
    """Window pixels of a button's middle (the real-app test clicks there)."""
    g = _geometry(data)
    for b in (g["buttons"] if g else ()):
        if b["key"] == key:
            return int(b["x"] + b["w"] / 2), int(b["y"] + b["h"] / 2)
    return None


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _rect(shader, batch_for_shader, x, y, w, h, col) -> None:
    shader.uniform_float("color", col)
    batch_for_shader(shader, "TRI_FAN", {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]}).draw(shader)


def _draw() -> None:
    try:
        if not visible():
            return
        from . import ops_tour
        g = _geometry(ops_tour.building())
        area = bpy.context.area
        if g is None or area is None or area.as_pointer() != g["area"].as_pointer():
            return
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        region = bpy.context.region
        ox, oy = region.x, region.y                       # the handler draws in region pixels
        s, c = g["scale"], g["c"]
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        x, y, w, h = g["x"] - ox, g["y"] - oy, g["w"], g["h"]
        _rect(flat, batch_for_shader, x - 2, y - 2, w + 4, h + 4, EDGE)
        _rect(flat, batch_for_shader, x, y, w, h, BG)
        font = 0
        top = y + h - g["pad"]
        blf.size(font, 20 * s)
        blf.color(font, *TEXT)
        blf.position(font, x + g["pad"], top - 22 * s, 0)
        blf.draw(font, c["title"])
        cur = top - 34 * s - g["lh"]
        blf.size(font, 14 * s)
        for text, col in c["body"]:
            blf.color(font, *col)
            blf.position(font, x + g["pad"], cur, 0)
            blf.draw(font, text)
            cur -= g["lh"]
        if c["bar"] is not None:
            bx, bw, bh = x + g["pad"], w - 2 * g["pad"], 12 * s
            _rect(flat, batch_for_shader, bx, cur - 4 * s, bw, bh, BAR_BG)
            if c["bar"] > 0:
                _rect(flat, batch_for_shader, bx, cur - 4 * s, bw * c["bar"], bh, BAR)
            cur -= 30 * s
        for text, col in c["foot"]:
            blf.color(font, *col)
            blf.position(font, x + g["pad"], cur, 0)
            blf.draw(font, text)
            cur -= g["lh"]
        for b in g["buttons"]:
            col = BTN_MAIN if b["main"] else BTN
            if STATE["hover"] == b["key"]:
                col = BTN_HOVER if not b["main"] else (0.26, 0.54, 0.92, 1.0)
            _rect(flat, batch_for_shader, b["x"] - ox, b["y"] - oy, b["w"], b["h"], col)
            tw, th = blf.dimensions(font, b["label"])
            blf.color(font, *TEXT)
            blf.position(font, b["x"] - ox + (b["w"] - tw) / 2, b["y"] - oy + (b["h"] - th) / 2, 0)
            blf.draw(font, b["label"])
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001 - a card that cannot draw must never break the 3D view
        pass


def _add_handler() -> None:
    if STATE["handle"] is None:
        STATE["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL")


def _remove_handler() -> None:
    if STATE["handle"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(STATE["handle"], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        STATE["handle"] = None


# ---------------------------------------------------------------------------
# clicks (called by the build's modal)
# ---------------------------------------------------------------------------

def press(key: str) -> None:
    """A button of the card was pressed."""
    mode = STATE["mode"]
    if key == "hide" and mode == "progress":
        STATE["hidden"] = True
    elif key == "stop" and mode == "progress":
        STATE["mode"] = "confirm"
    elif key == "stop_no" and mode == "confirm":
        STATE["mode"] = "progress"
    elif key == "stop_yes" and mode == "confirm":
        STATE["mode"] = "progress"
        try:
            bpy.ops.fresing.tour_cancel()
        except RuntimeError:
            pass
    elif key == "open" and mode == "ready":
        hub = STATE["hub"]
        dismiss()
        if hub:
            bpy.ops.fresing.tour_open("INVOKE_DEFAULT", filepath=hub)
        return
    elif key in ("later", "close"):
        dismiss()
        return
    elif key == "again" and mode == "failed":
        folder, only = STATE["folder"], STATE["only"]
        dismiss()
        bpy.ops.fresing.tour_make("EXEC_DEFAULT", folder=folder, only=only)
        return
    redraw()


def handle_event(context, event) -> bool:
    """True when the event belongs to the card (a click on it): the modal then swallows it. Hover is tracked."""
    if not visible():
        return False
    from . import ops_tour
    data = ops_tour.building()
    hit = button_at(event.mouse_x, event.mouse_y, data)
    if event.type == "MOUSEMOVE":
        key = hit if hit != "card" else ""
        if key != STATE["hover"]:
            STATE["hover"] = key
            redraw()
        return False
    if event.type == "LEFTMOUSE" and hit:
        if event.value == "PRESS" and hit != "card":
            press(hit)
        return True
    return False


@persistent
def _after_load(_dummy=None):
    """Opening another file ends the build's modal: the card goes with it (the build itself goes on)."""
    if active():
        dismiss()


def register_handlers() -> None:
    if _after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_after_load)


def unregister_handlers() -> None:
    while _after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_after_load)
    _remove_handler()
