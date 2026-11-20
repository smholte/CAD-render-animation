"""Lessons: Show me and Build it yourself on the sample projects (task 0230; design and prototype: study 0123).

A **lesson** is an ordered list of **steps** on one learning set of the test tour (``tour.SETS``). A step names the
function it teaches (``core/functions.py``: where the lesson points), a short text and a "More" text, the parts that
glow and the parts selected first, and three calls:

* ``do(scene)`` – what the button does (the button's own operator, or for a click on the model the function the click
  ends in). The test tour's set build runs the same steps (``run``): View, Show me and Build it yourself cannot drift.
* ``done(scene)`` – a check on the scene: false on the plain import, true however the step was done (the button, the
  list's +, a copy …). **Where the lesson is** = the first step whose ``done`` is false, so undo, Back, saving half-way
  and opening the project again all land right; ``scene["fr_lesson"]`` keeps only which lesson.
* ``show(scene, t)`` (optional) – a short move after Show me did the step (a new joint swings out and back once).

The two modes:

* **Show me** – the app points at the button and the parts (``highlight.py``: look C / D, section 5 / 4, part 3 / 1,
  the colour of Preferences > Lesson highlight), waits until the target has been on screen for ``SHOW_DELAY`` s, does the
  step itself, then waits for **Next** – or, with **Play on** (remembered in the preferences), goes on by itself after
  ``PLAY_PAUSE`` s.
* **Build it yourself** – the app points and checks ``done`` on a timer (only while a lesson runs); done → the card
  turns to "Done" for ``DONE_PAUSE`` s, then the next step. **Do it for me** runs ``do``; **Back** is undo.

A text card sits beside the parts in the 3D view (``place_card``: right of them, else left, above, below – never on them
and never under the side panel), with "More" for the longer text. Nothing of this module runs without a lesson: no draw
handler, no app handler, no timer (``handlers_left``).
"""

from __future__ import annotations

import textwrap
import time
from dataclasses import dataclass, field
from typing import Callable

import bpy
from bpy.app.handlers import persistent

from ..core import functions

SHOW_DELAY = 1.6            # Show me: seconds the target is seen on screen before the app does the step
SHOW_LATEST = 4.5           # ... or after this long when it never came into view (a menu, a hidden side panel)
SHOW_SECONDS = 1.5          # Show me: the length of a step's short move (``show``)
PLAY_PAUSE = 3.0            # Play on: seconds the done step stays before the next one
DONE_PAUSE = 1.4            # Build it yourself: seconds "Done" stays before the next step
TICK = 0.1                  # seconds between two looks of the timer while a lesson runs
PANEL = "FRESING_PT_lesson"
KEY = "fr_lesson"           # scene property: the id of the lesson this project follows
KEY_MODE = "fr_lesson_mode"
MODES = {"SHOW": "Show me", "BUILD": "Build it yourself"}

_S: dict = {"lesson": None, "mode": "SHOW", "step": 0, "phase": "", "t_phase": 0.0, "seen_at": None, "more": False,
            "shown": False, "scrolls": 0, "timer": False, "handles": [], "note": "", "history": [], "drawn": False,
            "card": None, "failed": "", "stats": {"card": [0, 0.0], "tick": [0, 0.0], "check": [0, 0.0]}}


# ---------------------------------------------------------------------------
# lessons and steps
# ---------------------------------------------------------------------------

@dataclass
class Step:
    function: str                                  # core/functions.py id: what the step teaches, where it points
    title: str                                     # a few words ("The boom turns: a rotate joint")
    say: str                                       # the short text: one or two lines
    more: str = ""                                 # the text behind "More"
    parts: tuple = ()                              # part names (fr_name) that glow
    select: object = ()                            # part names selected before the button, or fn(scene) -> objects
    do: Callable | None = None                     # do(scene): Show me, Do it for me and the tour's set build
    done: Callable | None = None                   # done(scene) -> bool: false on the plain import, true however done
    show: Callable | None = None                   # show(scene, t 0 … 1): a short move after Show me did it
    point: dict = field(default_factory=dict)      # where to point when it is not the function's own button:
                                                   # highlight.point() keywords (panel, button, text, prop, fold)


@dataclass
class Lesson:
    id: str                                        # the learning set's id (tour.SETS)
    title: str
    teaches: str                                   # one line: what it teaches (the Learn window)
    steps: list = field(default_factory=list)

    def index_of(self, fid: str) -> int:
        """The first step that teaches the function ``fid`` (0-based), -1 when none does."""
        return next((i for i, st in enumerate(self.steps) if st.function == fid), -1)


LESSONS: dict[str, Lesson] = {}


def lesson(les: Lesson) -> Lesson:
    LESSONS[les.id] = les
    return les


def of_function(fid: str) -> tuple:
    """(lesson, step index) of the function list's ``lesson="crane:3"`` link, or (None, -1)."""
    f = functions.FUNCTIONS.get(fid)
    if f is None or not f.lesson:
        return None, -1
    name, _, k = f.lesson.partition(":")
    les = LESSONS.get(name)
    if les is None or not k.isdigit() or not 1 <= int(k) <= len(les.steps):
        return None, -1
    return les, int(k) - 1


def is_done(scene, st: Step) -> bool:
    try:
        return bool(st.done and st.done(scene))
    except Exception:  # noqa: BLE001 - a check that cannot run (a part the update removed) counts as not done
        return False


def first_not_done(scene, les: Lesson) -> int:
    """Where the lesson is, read from the scene: undo, Back and a saved half-way project all land right."""
    for i, st in enumerate(les.steps):
        if not is_done(scene, st):
            return i
    return len(les.steps)


def _select(scene, st: Step) -> None:
    from . import build
    if not st.select:
        return
    if callable(st.select):
        obs = [o for o in st.select(scene) if o is not None]
    else:                                       # one object per name: the first copy (as the tour's _ob)
        obs = []
        for name in st.select:
            hits = sorted((o for o in scene.objects if o.get(build.PROP_NAME) == name),
                          key=lambda o: str(o.get(build.PROP_UID, o.name)))
            if hits:
                obs.append(hits[0])
    vl = bpy.context.view_layer
    for o in list(vl.objects.selected):
        o.select_set(False)
    for o in obs:
        try:
            o.select_set(True)
        except RuntimeError:                    # hidden / not in the view layer
            pass
    if obs:
        vl.objects.active = obs[0]


def do(scene, st: Step) -> None:
    """One step's ``do``, with its parts selected first (what the button acts on)."""
    if st.do is None:
        return
    _select(scene, st)
    from . import usage
    usage._DEPTH[0] += 1                        # the app's own clicks are not the user's use (My usage)
    try:
        st.do(scene)
    finally:
        usage._DEPTH[0] -= 1
    try:
        bpy.context.view_layer.update()
    except Exception:  # noqa: BLE001
        pass


def run(scene, lesson_id: str, until: int | None = None) -> int:
    """View's recipe (the test tour's set build): every step not yet done, in order, then its ``done`` must be true.
    ``until``: stop before that step (0-based). Returns the number of steps done here."""
    les = LESSONS[lesson_id]
    n = 0
    for i, st in enumerate(les.steps[:until] if until is not None else les.steps):
        if is_done(scene, st):
            continue
        if st.do is None:
            raise RuntimeError(f"lesson '{les.id}' step {i + 1} '{st.title}' is not done and has nothing to do it")
        do(scene, st)
        n += 1
        if not is_done(scene, st):
            raise RuntimeError(f"lesson '{les.id}' step {i + 1} '{st.title}': done() is still false after do()")
    return n


# ---------------------------------------------------------------------------
# the running lesson
# ---------------------------------------------------------------------------

def current() -> Lesson | None:
    return LESSONS.get(_S["lesson"]) if _S["lesson"] else None


def step() -> Step | None:
    les = current()
    if les is None or _S["step"] >= len(les.steps):
        return None
    return les.steps[_S["step"]]


def state() -> dict:
    """What the lesson shows now (tests, the PC check): lesson, mode, step (0-based), phase, note."""
    return {k: _S[k] for k in ("lesson", "mode", "step", "phase", "note", "failed")}


def running() -> bool:
    return _S["lesson"] is not None


def play_on() -> bool:
    try:
        from . import prefs
        p = prefs.get()
        return bool(p and p.lesson_play_on)
    except Exception:  # noqa: BLE001
        return False


def _set_phase(phase: str) -> None:
    _S["phase"], _S["t_phase"] = phase, time.time()
    _S["seen_at"] = None
    _S["history"].append((_S["t_phase"], _S["mode"], _S["step"], phase))
    del _S["history"][:-200]


def _point(scene) -> None:
    """Point at the current step: select what it acts on, the button and the parts glow (highlight.py)."""
    from . import highlight
    st = step()
    _S["more"] = False
    _S["scrolls"] = 0
    _S["shown"] = False
    _S["failed"] = ""
    if st is None:
        highlight.clear()
        _set_phase("end")
        _redraw()
        return
    try:
        _select(scene, st)
    except Exception as e:  # noqa: BLE001 - a part an update removed: the card says so
        _S["note"] = f"select: {e}"
    try:
        highlight.keep_clear((PANEL,))
        if st.point:
            highlight.point(parts=st.parts, open_panels=True, **st.point)
        else:
            highlight.point_function(st.function, parts=st.parts, open_panels=True)
    except Exception as e:  # noqa: BLE001 - the lesson goes on without the pointer
        _S["note"] = f"point: {e}"
    _set_phase("point" if _S["mode"] == "SHOW" else "wait")
    _redraw()


def start(scene, lesson_id: str, mode: str = "SHOW", at: int | None = None) -> None:
    """Start (or go on with) a lesson in this project. ``at``: start at that step (0-based) – the steps before it are
    done first (Show me's way), so a function of the learning list opens its lesson at its own step."""
    les = LESSONS[lesson_id]
    if mode not in MODES:
        raise ValueError(f"mode {mode!r}: one of {', '.join(MODES)}")
    if at is not None and at > 0:
        run(scene, lesson_id, until=at)
    _S.update(lesson=lesson_id, mode=mode, note="", history=[], failed="")
    _S["step"] = first_not_done(scene, les)
    scene[KEY] = lesson_id
    scene[KEY_MODE] = mode
    _add_handlers()
    _point(scene)


def stop(forget: bool = False) -> None:
    """End the lesson; the project stays as it is. ``forget``: the project no longer offers to go on with it."""
    from . import highlight
    if forget:
        try:
            for k in (KEY, KEY_MODE):
                if k in bpy.context.scene:
                    del bpy.context.scene[k]
        except Exception:  # noqa: BLE001
            pass
    was = _S["lesson"] is not None
    _S.update(lesson=None, phase="", card=None)
    _remove_handlers()
    if was:
        try:
            highlight.clear()
        except Exception:  # noqa: BLE001
            pass
    try:
        _redraw()
    except Exception:  # noqa: BLE001 - no window
        pass


def set_mode(mode: str) -> None:
    if mode in MODES and running():
        _S["mode"] = mode
        try:
            bpy.context.scene[KEY_MODE] = mode
        except Exception:  # noqa: BLE001
            pass
        if _S["phase"] in ("point", "wait"):
            _set_phase("point" if mode == "SHOW" else "wait")
        _redraw()


def do_step(scene) -> bool:
    """Show me / Do it for me: the step's own call, one undo step. False (and a note on the card) when it failed."""
    st = step()
    if st is None:
        return False
    try:
        do(scene, st)
    except Exception as e:  # noqa: BLE001 - the card says what went wrong, the lesson stays on this step
        _S["failed"] = f"{type(e).__name__}: {e}"
        _redraw()
        return False
    try:
        bpy.ops.ed.undo_push(message=f"Lesson: {st.title}")
    except RuntimeError:
        pass
    if not is_done(scene, st):
        _S["failed"] = "The step was done, but the project does not show it yet"
        _redraw()
        return False
    _set_phase("done")
    _redraw()
    return True


def next_step(scene) -> None:
    """On to the step the scene says is next (normally the one after this)."""
    les = current()
    if les is None:
        return
    st = step()
    if st is not None and st.show and _S["shown"] is False and _S["phase"] == "done":
        _finish_show(scene, st)
    _S["step"] = first_not_done(scene, les)
    _point(scene)


def back() -> None:
    """Back: undo the last step (the undo handler moves the lesson back)."""
    try:
        bpy.ops.ed.undo()
    except RuntimeError as e:
        _S["note"] = f"undo: {e}"


def advance(scene) -> bool:
    """One whole step without the timer (tests, the PC check, a background Blender): Show me does it and goes to the
    next; Build it yourself does it for you and goes on. False when the step failed or the lesson is at its end."""
    if step() is None:
        return False
    if not is_done(scene, step()) and not do_step(scene):
        return False
    if _S["phase"] != "done":
        _set_phase("done")
    next_step(scene)
    return True


def _finish_show(scene, st: Step) -> None:
    try:
        st.show(scene, 1.0)
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"show: {e}"
    _S["shown"] = True


def _seen() -> bool:
    """Is the target on screen (the button, or the header of its folded section)? A step without a place in the
    side panel (a menu) counts as seen."""
    from . import highlight
    st = step()
    f = functions.FUNCTIONS.get(st.function) if st else None
    if st is not None and not st.point and (f is None or not f.panel.startswith("FRESING_PT_")):
        return True
    seen = highlight.found()
    return bool(seen.get("button") or seen.get("header"))


def tick(scene=None, now: float | None = None) -> None:
    """The lesson's look at the world, ``TICK`` s apart while it runs: Show me's timing, Build it yourself's check,
    the scrolling to the target. (Tests call it with ``now``.)"""
    t0 = time.perf_counter()
    scene = scene or bpy.context.scene
    now = time.time() if now is None else now
    st = step()
    ph = _S["phase"]
    if st is None:
        return
    if ph == "point":
        if _S["seen_at"] is None and _seen():
            _S["seen_at"] = now
        age = now - _S["t_phase"]
        if not _S["failed"] and ((_S["seen_at"] is not None and now - _S["seen_at"] >= SHOW_DELAY)
                                 or age >= SHOW_LATEST):
            do_step(scene)
    elif ph == "wait":
        c0 = time.perf_counter()
        ok = is_done(scene, st)
        c = _S["stats"]["check"]
        c[0] += 1
        c[1] += time.perf_counter() - c0
        if ok:
            _set_phase("done")
            _redraw()
    elif ph == "done":
        age = now - _S["t_phase"]
        if _S["mode"] == "SHOW" and st.show and not _S["shown"]:
            if age < SHOW_SECONDS:
                try:
                    st.show(scene, age / SHOW_SECONDS)
                except Exception as e:  # noqa: BLE001
                    _S["note"] = f"show: {e}"
                    _S["shown"] = True
            else:
                _finish_show(scene, st)
        if (_S["mode"] == "BUILD" and age >= DONE_PAUSE) or (_S["mode"] == "SHOW" and play_on()
                                                              and age >= PLAY_PAUSE + (SHOW_SECONDS if st.show else 0)):
            next_step(scene)
    if ph in ("point", "wait") and _S["drawn"]:
        _S["drawn"] = False
        _scroll_to_target()
    s = _S["stats"]["tick"]
    s[0] += 1
    s[1] += time.perf_counter() - t0


def _timer():
    if not running():
        _S["timer"] = False
        return None
    try:
        tick()
    except Exception as e:  # noqa: BLE001 - a lesson must never stop the app
        _S["note"] = f"tick: {e}"
    return TICK


# ---------------------------------------------------------------------------
# the side panel follows the target
# ---------------------------------------------------------------------------

def _side_panels():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            sb = next((r for r in area.regions if r.type == "UI" and r.width > 1), None)
            if sb is not None:
                yield win, area, sb


def _scroll_to_target() -> None:
    """Neither the button nor its section's header on screen: scroll the side panel – first to the top, then about
    60 % of its height per redraw (a whole page jumped over the camera buttons, study 0123). On screen but at an edge:
    a little, to bring it in."""
    from . import highlight
    seen = highlight.found()
    if not seen.get("region"):
        return
    h = seen["region"][3]
    box = seen.get("button")
    try:
        for win, area, sb in _side_panels():
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb):
                head = seen.get("header")
                if box is not None:
                    y0, y1 = box[1], box[3]
                    if y1 > h - 40:
                        bpy.ops.view2d.scroll_up()
                    elif y0 < 40:
                        bpy.ops.view2d.scroll_down()
                elif head is not None and head[1] < 0.5 * h and _S["scrolls"] < 30:
                    for _ in range(8):                  # its section's title low down, the button under it: up with it
                        bpy.ops.view2d.scroll_down()
                    _S["scrolls"] += 1
                elif head is None and _S["scrolls"] < 30:
                    if _S["scrolls"] == 0:
                        for _ in range(20):
                            bpy.ops.view2d.scroll_up(page=True)
                    else:
                        y0 = sb.view2d.region_to_view(0, 0)[1]
                        for _ in range(60):
                            bpy.ops.view2d.scroll_down()
                            if y0 - sb.view2d.region_to_view(0, 0)[1] >= 0.6 * sb.height:
                                break
                    _S["scrolls"] += 1
            break                                   # the first 3D view's side panel
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"scroll: {e}"


# ---------------------------------------------------------------------------
# the text card in the 3D view
# ---------------------------------------------------------------------------

def card_lines(st: Step, more: bool, phase: str, mode: str, k: int, n: int, failed: str = "",
               width: int = 46) -> list:
    """The card's lines: (text, kind) with kind title / text / more / hint / problem."""
    head = ("Done: " if phase == "done" else "") + st.title
    lines = [(f"{head}   ({k} of {n})", "title")]
    lines += [(t, "text") for t in textwrap.wrap(st.say, width)]
    if more and st.more:
        lines += [(t, "more") for t in textwrap.wrap(st.more, width)]
    if failed:
        lines += [(t, "problem") for t in textwrap.wrap("Did not work: " + failed, width)]
    if phase == "done":
        hint = ("Well done – the next step follows" if mode == "BUILD" else
                "Next follows by itself (Play on)" if play_on() else "Next in the Lesson panel")
    elif mode == "SHOW":
        hint = "Watch: the app does this step"
    else:
        hint = "Do it where it glows – or Do it for me"
    lines.append(("More in the Lesson panel  ·  " + hint if st.more and not more else hint, "hint"))
    return lines


def place_card(box, size, region_size, gap=40):
    """Where the card goes: right of the part's box on screen, else left, else above, else below – never on it.

    box: (x0, y0, x1, y1) of the part on screen; size: (w, h); region_size: the free part of the view (w, h).
    Returns (x, y) of the card's lower left corner."""
    x0, y0, x1, y1 = box
    w, h = size
    rw, rh = region_size
    cy = min(max((y0 + y1) / 2 - h / 2, 10), rh - h - 10)
    if x1 + gap + w <= rw - 10:
        return x1 + gap, cy
    if x0 - gap - w >= 10:
        return x0 - gap - w, cy
    cx = min(max((x0 + x1) / 2 - w / 2, 10), rw - w - 10)
    if y1 + gap + h <= rh - 10:
        return cx, y1 + gap
    return cx, max(10, y0 - gap - h)


def _screen_box(region, rv3d, obs):
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector
    xs, ys = [], []
    for ob in obs:
        for c in ob.bound_box:
            p = location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
            if p is not None:
                xs.append(p.x)
                ys.append(p.y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def free_width(area, region) -> int:
    """The view's width that the side panel does not cover (with region overlap it is drawn over the view)."""
    w = region.width
    for r in area.regions:
        if r.type == "UI" and r.width > 1 and r.x + r.width >= region.x + region.width - 2:
            w = min(w, r.x - region.x)
    return max(200, w)


def _part_objects(scene, names) -> list:
    from . import build
    want = set(names)
    return [o for o in scene.objects if o.get(build.PROP_NAME) in want and o.type == "MESH"
            and o.visible_get()]


def _draw_card() -> None:
    st = step()
    if st is None:
        return
    t0 = time.perf_counter()
    try:
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader

        from . import highlight
        region, rv3d = bpy.context.region, bpy.context.region_data
        scale = bpy.context.preferences.system.ui_scale or 1.0
        les = current()
        lines = card_lines(st, _S["more"], _S["phase"], _S["mode"], _S["step"] + 1, len(les.steps), _S["failed"])
        font = 0
        sizes = {"title": 15, "text": 13, "more": 12, "hint": 11, "problem": 12}
        lh = {k: v * 1.45 * scale for k, v in sizes.items()}
        wmax = 0
        for text, kind in lines:
            blf.size(font, sizes[kind] * scale)
            wmax = max(wmax, blf.dimensions(font, text)[0])
        pad = 10 * scale
        w, h = wmax + 2 * pad, sum(lh[k] for _t, k in lines) + 2 * pad
        obs = _part_objects(bpy.context.scene, st.parts) if st.parts else []
        box = _screen_box(region, rv3d, obs) if obs else None
        fw = free_width(bpy.context.area, region)
        if box is None:                              # no part: the card sits in the free view's upper left corner
            x, y = 20 * scale, region.height - h - 60 * scale
        else:
            x, y = place_card(box, (w, h), (fw, region.height))
        _S["card"] = (x, y, w, h, box)
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        col = (0.35, 0.85, 0.4) if _S["phase"] == "done" else highlight.colour()
        dark = (0.07, 0.08, 0.09, 0.9)
        if box is not None:                          # the line from the card to the part
            right, left = x > box[2], x + w < box[0]
            bx = box[2] if right else (box[0] if left else (box[0] + box[2]) / 2)
            by = (box[1] + box[3]) / 2 if (right or left) else (box[3] if y > box[3] else box[1])
            ax = x if right else (x + w if left else x + w / 2)
            ay = y + h / 2 if (right or left) else (y if y > box[3] else y + h)
            line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
            vp = gpu.state.viewport_get()
            line.uniform_float("viewportSize", (vp[2], vp[3]))
            for width, c in ((4.0, dark), (2.0, (*col, 1.0))):
                line.uniform_float("lineWidth", width)
                line.uniform_float("color", c)
                batch_for_shader(line, "LINES", {"pos": [(ax, ay), (bx, by)]}).draw(line)
        quad = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        flat.uniform_float("color", dark)
        batch_for_shader(flat, "TRI_FAN", {"pos": quad}).draw(flat)
        flat.uniform_float("color", (*col, 1.0))
        batch_for_shader(flat, "TRI_FAN", {"pos": [(x, y), (x + 4 * scale, y), (x + 4 * scale, y + h),
                                                   (x, y + h)]}).draw(flat)
        ty = y + h - pad
        colours = {"title": (*col, 1.0), "text": (0.95, 0.95, 0.95, 1.0), "more": (0.82, 0.86, 0.92, 1.0),
                   "hint": (0.62, 0.62, 0.62, 1.0), "problem": (1.0, 0.45, 0.4, 1.0)}
        for text, kind in lines:
            blf.size(font, sizes[kind] * scale)
            ty -= lh[kind]
            blf.color(font, *colours[kind])
            blf.position(font, x + pad, ty + 0.3 * lh[kind], 0)
            blf.draw(font, text)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 - drawing must never break the view
        _S["note"] = f"card: {e}"
    c = _S["stats"]["card"]
    c[0] += 1
    c[1] += time.perf_counter() - t0


def _side_drawn() -> None:
    """The side panel was drawn (after highlight's own handler read it): the timer may scroll now."""
    _S["drawn"] = True


def stats(reset: bool = False) -> dict:
    """Milliseconds per call: {"card": (n, ms), "tick": (…), "check": (…)} – the card's draw, the timer's look, Build
    it yourself's check."""
    out = {k: (n, 1000.0 * s / n if n else 0.0) for k, (n, s) in _S["stats"].items()}
    if reset:
        _S["stats"] = {"card": [0, 0.0], "tick": [0, 0.0], "check": [0, 0.0]}
    return out


def _redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm else ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---------------------------------------------------------------------------
# handlers: only while a lesson runs
# ---------------------------------------------------------------------------

@persistent
def _after_undo(_dummy=None):
    les = current()
    if les is not None:
        _S["step"] = first_not_done(bpy.context.scene, les)
        _point(bpy.context.scene)


@persistent
def _before_load(_dummy=None):
    """Another project opens: the lesson ends (the project keeps ``fr_lesson``: its Lesson panel offers to go on).
    The handler takes itself off a moment later (not while Blender walks its list)."""
    _S.update(lesson=None, phase="", card=None)
    for h, region in _S["handles"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, region)
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []
    bpy.app.timers.register(_remove_handlers, first_interval=0.0, persistent=True)


def _app_handlers() -> tuple:
    h = bpy.app.handlers
    return (h.undo_post, _after_undo), (h.redo_post, _after_undo), (h.load_pre, _before_load)


def _add_handlers() -> None:
    if not _S["handles"]:
        sv = bpy.types.SpaceView3D
        _S["handles"] = [(sv.draw_handler_add(_draw_card, (), "WINDOW", "POST_PIXEL"), "WINDOW"),
                         (sv.draw_handler_add(_side_drawn, (), "UI", "POST_PIXEL"), "UI")]
    for lst, fn in _app_handlers():
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=TICK)
    _S["timer"] = True


def _remove_handlers():
    for h, region in _S["handles"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, region)
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []
    for lst, fn in _app_handlers():
        if fn in lst:
            lst.remove(fn)
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)
    _S["timer"] = False
    return None


def handlers_left() -> list:
    """What of this module is still hooked into Blender (empty without a lesson): the tests' check."""
    out = [f"draw handler {r}" for _h, r in _S["handles"]]
    out += [f"app handler {fn.__name__}" for lst, fn in _app_handlers() if fn in lst]
    out += ["timer"] if bpy.app.timers.is_registered(_timer) else []
    return out


# ---------------------------------------------------------------------------
# a new project for a lesson
# ---------------------------------------------------------------------------

def lessons_folder() -> str:
    import os

    from . import tour
    return os.path.join(tour.documents_dir(), "Fresing Render", "Lessons")


def new_project(lesson_id: str):
    """A new project with the learning set's plain import (its model, its environment): where Show me and Build it
    yourself start. Returns the scene."""
    import os

    from . import tour
    ts = tour.SETS[lesson_id]
    stop()
    scene = tour._fresh(ts.models, os.path.join(lessons_folder(), "Renders"))
    return scene


_PENDING: dict = {}


def open_lesson(lesson_id: str, mode: str, at: int | None = None) -> None:
    """Learn window / learning list: a new project with the plain import, then the lesson (at step ``at``). In the app
    the lesson starts once the window has settled after the new project (Blender's column is closed from a timer, and
    a 3D view's setting set before that crashes Blender 5.2.3)."""
    new_project(lesson_id)
    wm = getattr(bpy.context, "window_manager", None)
    if bpy.app.background or wm is None or not len(wm.windows):
        start(bpy.context.scene, lesson_id, mode, at=at)
        return
    _PENDING.update(lesson=lesson_id, mode=mode, at=at, waits=0)
    if not bpy.app.timers.is_registered(_start_when_settled):
        bpy.app.timers.register(_start_when_settled, first_interval=0.1)


def _start_when_settled():
    from . import editors
    if not _PENDING:
        return None
    if editors.busy() and _PENDING["waits"] < 200:
        _PENDING["waits"] += 1
        return 0.05
    p = dict(_PENDING)
    _PENDING.clear()
    try:
        start(bpy.context.scene, p["lesson"], p["mode"], at=p["at"])
        show_view()
    except Exception as e:  # noqa: BLE001 - said in the status bar; the project stays
        _S["note"] = f"start: {e}"
        try:
            bpy.context.scene.fresing.last_message = f"The lesson could not start: {e}"
        except Exception:  # noqa: BLE001
            pass
    return None


def pending() -> bool:
    """A lesson waits for the window to settle before it starts (tests)."""
    return bool(_PENDING)


def show_view() -> None:
    """The 3D view frames the model and the side panel shows the Fresing tab."""
    for win, area, _sb in list(_side_panels()) or []:
        try:
            region = next(r for r in area.regions if r.type == "WINDOW")
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                bpy.ops.view3d.view_all(center=False)
        except Exception:  # noqa: BLE001 - a nicety
            pass


def register():
    from . import lessons  # noqa: F401 - the lessons register themselves


def unregister():
    stop()
    _remove_handlers()
