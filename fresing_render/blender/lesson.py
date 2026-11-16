"""Lessons: Show me / Build it yourself on a test model (task 0123 – PROTOTYPE, branch task/0123-learning-study).

What the prototype proves (the study's report has the numbers):

* **The button glows.** Blender's Python cannot ask where a button is. While a lesson runs, every Fresing panel's
  ``draw`` gets a stand-in for ``self.layout`` (``_L``) that passes every call through, except the lesson's target
  button: it is drawn after a small magenta arrow icon (the *marker*). A draw handler of the side panel then reads the
  side panel's own pixels, finds the marker's colour and draws a soft pulsing frame round that row. The panel header of
  the target section gets the marker too, so a closed section glows at its header ("open me").
* **The fold opens.** A fold (``layout.panel``) that holds the target is drawn as ``panel_prop`` on a property that is
  True, so it opens by itself – only while the lesson points into it.
* **The part glows**, with a text card beside it that never covers it (placed right of the part's box on screen, else
  left, else above) and a "More" text that unfolds.
* **One recipe.** A lesson step's ``do`` is the call the test tour's set build makes; ``done`` is a check on the scene.
  Show me runs ``do`` after the highlight has been seen; Build it yourself waits for ``done``. Where the lesson is is
  worked out from the scene (the first step not done), so undo, Back, saving half-way and reopening need no own state.

**Task 0133 – looks to compare.** The magenta frame is gone. One switch, ``set_look(kind, key)`` (or the environment
variables ``FR_LESSON_LOOK`` / ``FR_LESSON_SECTION`` / ``FR_LESSON_PART``), picks one of six button looks A–F
(``BUTTON_LOOKS``), three closed-section markers 1–3 (``SECTION_LOOKS``) and three part looks 1–3 (``PART_LOOKS``),
in the Fresing palette (and Blender's blue for F). The marker icons are painted over with the button's own colour;
``button_box`` finds the button's own edges, so of two aligned buttons only the target is marked.
``tools/lesson_looks_app.py`` pictures them all.

Nothing here runs unless a lesson is started: no handler, no wrapped draw, no timer.
"""

from __future__ import annotations

import math
import os
import textwrap
import time
from dataclasses import dataclass, field
from typing import Callable

import bpy
from bpy.app.handlers import persistent

from ..core import functions

MAGENTA = (1.0, 0.10, 0.80)                 # hover.py's highlight colour: one colour for "this one"
OK = (0.25, 0.85, 0.35)
DARK = (0.05, 0.05, 0.05, 0.88)
MARK_BUTTON = (255, 0, 255)                 # the marker icons' exact colours, found again in the side panel's pixels
MARK_HEADER = (0, 255, 255)
SHOW_DELAY = 1.6                            # Show me: seconds the highlight is seen before the app does the step
DONE_PAUSE = 1.4                            # Build it yourself: seconds the "Well done" stays before the next step
PULSE_HZ = 20.0

# --- task 0133: highlight looks to compare (the owner picks one; the build task keeps only that one) ---
GREEN = (0.278, 0.608, 0.161)               # Fresing Green #479B29 (site/style.css)
BRIGHT = (0.361, 0.749, 0.216)              # Fresing Green Bright #5CBF37
CHARCOAL = (0.102, 0.125, 0.153)            # Deep Charcoal #1A2027
BLUE = (0.278, 0.447, 0.702)                # Blender's selection blue (default dark theme, #4772B3)
BUTTON_LOOKS = {
    "A": "Soft green glow round the button, breathes slowly (one breath in 2 s)",
    "B": "Thin steady green outline, an arrow at the panel's edge that moves gently, the step's number on the button",
    "C": "Spotlight: the rest of the side panel dimmed, the button clear with a thin outline",
    "D": "Green bar on the button's left edge, the button tinted green, breathing",
    "E": "Corner brackets that close in once, then stay",
    "F": "Blender-blue outline with a light that runs round it (once in 2 s)",
}
SECTION_LOOKS = {
    "1": "A green dot in the header with a ring that grows from it",
    "2": "The whole header tinted green, breathing",
    "3": "A ring round the fold triangle and the word 'Open' at the header's end",
}
PART_LOOKS = {
    "1": "Glow: the part covered in see-through green, breathing",
    "2": "Outline: the part's edges drawn in green, seen through other parts",
    "3": "The rest faded: everything else greyed, the part clear on top",
}
BUTTON_LOOKS.update({
    "G": "An underline that fills left to right once and then stays",
    "H": "A soft light sweeps across the button every 3 s",
    "I": "A ring ripples outward from the button and fades (every 1.5 s)",
    "J": "A small pointing hand taps the button slowly",
    "K": "Steady outline with a soft outer glow, no arrow",
    "L": "A slowly marching dashed outline",
    "M": "Softer spotlight: the rest of the panel dimmed about 30 %, the Lesson panel left clear",
    "N": "A tag with the step number joined to the button by a short line",
})
SECTION_LOOKS.update({
    "4": "A bar on the header's left edge",
    "5": "The header tinted in the colour, a fold arrow that nods slowly",
    "6": "The header outlined, with a breathing glow",
    "7": "A small arrow with the step number at the panel's edge, pointing at the header",
})
PART_LOOKS.update({
    "4": "The part filled in the colour, half see-through, edges in the colour",
    "5": "A glow that breathes slowly (soft halo round the edges)",
    "6": "X-ray: the rest as faint ghost lines, the part solid in its own colour with an outline",
    "7": "The part outlined, and a bold leader line with a moving dot from the text card to the part",
    "8": "Outline and the rest faded, together",
})
# task 0168: one colour setting for every look; the clip clock (the looks' time can be set per picture)
COLOURS = {"Fresing Green": "#479B29", "Green Bright": "#5CBF37", "Amber": "#F5B700", "Hi-vis orange": "#FF6A13",
           "Cyan": "#1FB5D6", "White": "#F2F2F2"}
LOOP = 3.0                                  # a clip's length: every look's movement joins up after 3 s (1.5 s breaths)
BEAT = 1.5                                  # one breath / ripple / nod
MARK_LESSON_TOP = (0, 128, 255)             # the Lesson panel's header and its last button carry markers too (look M)
MARK_LESSON_END = (0, 255, 128)
LOOKS = {"button": os.environ.get("FR_LESSON_LOOK", "A"), "section": os.environ.get("FR_LESSON_SECTION", "1"),
         "part": os.environ.get("FR_LESSON_PART", "1")}


def _hex(c):
    c = COLOURS.get(c, c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def set_colour(c) -> None:
    """The colour every look is drawn in: a name of ``COLOURS`` or "#rrggbb" (look F stays Blender's blue)."""
    _S["colour"] = _hex(c)
    try:
        redraw()
    except Exception:  # noqa: BLE001
        pass


def colour():
    return _S.get("colour") or GREEN


def _now() -> float:
    c = _S.get("clock")
    return time.time() if c is None else c


def begin_clip() -> None:
    """From now on the looks' clock is the one ``set_clock`` sets (seconds from 0): clips are made picture by picture."""
    _S.update(clock=0.0, t=0.0, t_look=0.0, t_phase=0.0)


def set_clock(t: float) -> None:
    _S["clock"] = float(t)


def end_clip() -> None:
    _S["clock"] = None
    _S.update(t=time.time(), t_look=time.time())


def _out() -> float:
    """1, but in a clip the last 0.4 s fade the look out, so a once-only movement (a fill, a closing in) joins the start."""
    c = _S.get("clock")
    if c is None:
        return 1.0
    return min(1.0, (LOOP - c % LOOP) / 0.4)


def set_look(kind: str, key: str) -> None:
    """The one switch: set_look("button", "C"), set_look("section", "2"), set_look("part", "3")."""
    table = {"button": BUTTON_LOOKS, "section": SECTION_LOOKS, "part": PART_LOOKS}[kind]
    if key not in table:
        raise KeyError(f"{kind} look {key!r}: one of {', '.join(table)}")
    LOOKS[kind] = key
    _S["t_look"] = _now()                  # E's brackets close in again, fades start again
    try:
        redraw()
    except Exception:  # noqa: BLE001
        pass

_S: dict = {"lesson": None, "mode": "SHOW", "step": 0, "phase": "", "t": 0.0, "more": False, "handles": [],
            "wrapped": [], "icons": None, "found": None, "found_header": None, "timer": False, "note": "",
            "scrolls": 0, "t_look": 0.0, "box": None, "hbox": None,
            "stats": {"reads": 0, "read_s": 0.0, "draws": 0, "draw_s": 0.0, "look": {}}}


# ---------------------------------------------------------------------------
# lessons
# ---------------------------------------------------------------------------

@dataclass
class Step:
    function: str                                  # functions.FUNCTIONS id: where the lesson points
    title: str
    say: str                                       # the short text (one or two lines)
    more: str = ""                                 # the text behind "More"
    parts: tuple = ()                              # part names (fr_name) that glow
    do: Callable | None = None                     # do(scene): Show me and "Do it for me" – the tour's own call
    done: Callable | None = None                   # done(scene) -> bool: Build it yourself sees that you did it
    show: Callable | None = None                   # show(scene, t 0..1): a short move after Show me did it
    select: tuple = ()                             # parts selected before the button (what the button acts on)


@dataclass
class Lesson:
    id: str
    title: str
    model: str                                     # file in fresing_render/data/
    steps: list = field(default_factory=list)


LESSONS: dict[str, Lesson] = {}


def lesson(les: Lesson) -> Lesson:
    LESSONS[les.id] = les
    return les


def current() -> Lesson | None:
    return LESSONS.get(_S["lesson"]) if _S["lesson"] else None


def step() -> Step | None:
    les = current()
    if les is None or _S["step"] >= len(les.steps):
        return None
    return les.steps[_S["step"]]


def target():
    st = step()
    return functions.FUNCTIONS.get(st.function) if st else None


def first_not_done(scene, les: Lesson) -> int:
    """Where the lesson is, read from the scene: undo, Back, a saved half-way project all land right."""
    for i, st in enumerate(les.steps):
        try:
            if not (st.done and st.done(scene)):
                return i
        except Exception:  # noqa: BLE001 - a check that cannot run counts as not done
            return i
    return len(les.steps)


# ---------------------------------------------------------------------------
# the stand-in layout: passes everything through, marks the target
# ---------------------------------------------------------------------------

_SUB = ("row", "column", "box", "split", "column_flow", "grid_flow")


class _L:
    __slots__ = ("_l",)

    def __init__(self, layout):
        object.__setattr__(self, "_l", layout)

    def __getattr__(self, name):
        real = getattr(self._l, name)
        if name in _SUB:
            return lambda *a, **k: _L(real(*a, **k))
        if name == "operator":
            return self._operator
        if name == "prop":
            return self._prop
        if name == "panel":
            return self._panel
        return real

    def __setattr__(self, name, value):
        setattr(self._l, name, value)

    @staticmethod
    def _marked(k: dict) -> dict:
        """The target keeps its place and size: only its icon becomes the marker (no row added, nothing moves)."""
        k = dict(k)
        k.pop("icon", None)
        k["icon_value"] = _S["icons"]["button"].icon_id
        return k

    def _operator(self, idname, *a, **k):
        f = target()
        if f is not None and idname == f.button and (not f.text or k.get("text") == f.text):
            return self._l.operator(idname, *a, **self._marked(k))
        return self._l.operator(idname, *a, **k)

    def _prop(self, data, prop, *a, **k):
        f = target()
        if f is not None and f.prop and prop == f.prop:
            return self._l.prop(data, prop, *a, **self._marked(k))
        return self._l.prop(data, prop, *a, **k)

    def _panel(self, idname, *a, **k):
        f = target()
        if f is not None and f.fold and idname == f.fold:     # the target's fold opens by itself
            header, body = self._l.panel_prop(bpy.context.window_manager, "fresing_lesson_fold")
            return _L(header), (_L(body) if body is not None else None)
        header, body = self._l.panel(idname, *a, **k)
        return _L(header), (_L(body) if body is not None else None)


class _Self:
    """What a wrapped draw gets as ``self``: the panel, with the stand-in layout."""
    __slots__ = ("_p",)

    def __init__(self, panel):
        object.__setattr__(self, "_p", panel)

    def __getattr__(self, name):
        if name == "layout":
            return _L(self._p.layout)
        return getattr(self._p, name)


def _wrap_draws() -> None:
    """Every Fresing panel's draw and draw_header go through the stand-in while the lesson runs (task 0062 puts this
    in the shared panel class once, so nothing is swapped at run time)."""
    if _S["wrapped"]:
        return
    for name in dir(bpy.types):
        if not name.startswith("FRESING_PT_") or name == "FRESING_PT_lesson":
            continue
        cls = getattr(bpy.types, name)
        for attr in ("draw", "draw_header"):
            orig = cls.__dict__.get(attr)
            if orig is None:
                continue

            def make(orig, attr, cls):
                def wrapped(self, context):
                    t = time.perf_counter()
                    if attr == "draw":
                        orig(_Self(self), context)
                    else:
                        orig(self, context)
                        f = target()
                        if f is not None and cls.__name__ == f.panel:
                            self.layout.label(text="", icon_value=_S["icons"]["header"].icon_id)
                    _S["stats"]["draws"] += 1
                    _S["stats"]["draw_s"] += time.perf_counter() - t
                return wrapped

            setattr(cls, attr, make(orig, attr, cls))
            _S["wrapped"].append((cls, attr, orig))


def _unwrap_draws() -> None:
    for cls, attr, orig in _S["wrapped"]:
        setattr(cls, attr, orig)
    _S["wrapped"] = []


# ---------------------------------------------------------------------------
# marker icons (made once, a few hundred bytes each)
# ---------------------------------------------------------------------------

def _png(path: str, colour, shape: str) -> None:
    import struct
    import zlib
    w = 32
    px = bytearray(w * w * 4)
    for y in range(w):
        for x in range(w):
            inside = (4 <= x <= 28 and abs(y - 16) <= (28 - x) * 0.6) if shape == "arrow" else \
                ((x - 16) ** 2 + (y - 16) ** 2 <= 100)
            if inside:
                px[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes((*colour, 255))
    raw = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(w))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, w, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _icons():
    if _S["icons"] is None:
        import bpy.utils.previews
        pc = bpy.utils.previews.new()
        d = bpy.app.tempdir or "/tmp"
        for key, colour, shape in (("button", MARK_BUTTON, "arrow"), ("header", MARK_HEADER, "dot"),
                                  ("lesson_top", MARK_LESSON_TOP, "dot"), ("lesson_end", MARK_LESSON_END, "dot")):
            path = os.path.join(d, f"fr_lesson_{key}.png")
            _png(path, colour, shape)
            pc.load(key, path, "IMAGE")
        _S["icons"] = pc
    return _S["icons"]


# ---------------------------------------------------------------------------
# drawing: the glow in the side panel, the part and its card in the view
# ---------------------------------------------------------------------------

def _pulse(hz: float = 1 / BEAT) -> float:
    """0 … 1, a slow breath (0.5 Hz: one in 2 s – calm, never faster than 1 per second)."""
    return 0.5 + 0.5 * math.sin((_now() - _S["t"]) * 2.0 * math.pi * hz)


def _age() -> float:
    """Seconds since the target or the look last changed (for things that happen once: E's brackets, C's fade)."""
    return _now() - max(_S.get("t_look", 0.0), _S.get("t_phase", 0.0), _S["t"])


def _find(pixels, colour):
    import numpy as np
    m = (np.abs(pixels[:, :, 0].astype(np.int16) - colour[0]) < 24) & \
        (np.abs(pixels[:, :, 1].astype(np.int16) - colour[1]) < 24) & \
        (np.abs(pixels[:, :, 2].astype(np.int16) - colour[2]) < 24)
    ys, xs = np.nonzero(m)
    if len(xs) < 6:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _walk(line, start: int, step: int, own) -> int:
    """From ``start`` along a line of pixels, the last index that still has the colour ``own`` (one pixel that
    differs ends it: the line between two aligned buttons is one pixel wide)."""
    import numpy as np
    seg = line[start::step] if step > 0 else line[start::-1]
    off = np.nonzero(np.abs(seg - own).max(axis=1) > 8)[0]
    n = (off[0] - 1) if len(off) else len(seg) - 1
    return start + step * int(n)


def button_box(px, found):
    """The marked button's own rectangle (x0, y0, x1, y1) in the region's pixels, y up.

    From the button's background just left of the marker icon, walk down and up (the button's bottom and top edge),
    then left and right along a row just above the bottom edge (no text there – a descender of 'j' or 'p' reaches
    the row below the icon). Aligned buttons are separated by a one-pixel line: the walk stops there (task 0123's
    frame covered *Add rotate joint* and *Add slide joint* together, it needed two pixels)."""
    import numpy as np
    x0, y0, x1, y1 = found
    h, w = px.shape[:2]
    cx, cy = max(x0 - 3, 0), min(max((y0 + y1) // 2, 0), h - 1)
    col = px[:, cx, :3].astype(np.int16)            # only the column and the row walked: the whole picture as
    own = col[cy]                                   # int16 cost 2.5 ms
    bottom = _walk(col, cy, -1, own)
    top = _walk(col, cy, 1, own)
    row = px[min(bottom + 2, top), :, :3].astype(np.int16)
    left = _walk(row, cx, -1, own)
    right = _walk(row, min(x1 + 3, w - 1), 1, own)
    if right - left < (x1 - x0) or top - bottom < (y1 - y0):      # not a plain button round the icon: the icon
        return x0 - 4, y0 - 4, x1 + 80, y1 + 4
    return int(left), int(bottom), int(right), int(top)


def _button_right(px, y, x):
    """Kept for the 0123 script: the button's right edge (now from ``button_box``)."""
    return _S["box"][2] if _S.get("box") else x + 80


# --- small drawing helpers (region pixels, y up) ---

def _shader(name="UNIFORM_COLOR"):
    import gpu
    return gpu.shader.from_builtin(name)


def _tris2d(pts, rgba, kind="TRIS"):
    from gpu_extras.batch import batch_for_shader
    sh = _shader()
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, kind, {"pos": pts}).draw(sh)


def _rect(x0, y0, x1, y1, rgba):
    _tris2d([(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)], rgba)


def _lines(pts, rgba, width, kind="LINE_STRIP"):
    import gpu
    from gpu_extras.batch import batch_for_shader
    vp = gpu.state.viewport_get()
    sh = _shader("POLYLINE_UNIFORM_COLOR")
    sh.uniform_float("viewportSize", (vp[2], vp[3]))
    sh.uniform_float("lineWidth", width)
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, kind, {"pos": pts}).draw(sh)


def _frame(x0, y0, x1, y1, colour, alpha, width):
    _lines([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], (*colour, alpha), width)


def _disc(cx, cy, r, rgba, n=24):
    pts = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        pts += [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a1), cy + r * math.sin(a1))]
    _tris2d(pts, rgba)


def _ring(cx, cy, r, rgba, width, n=32):
    _lines([(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)],
           rgba, width)


def _text(x, y, text, size, rgba, centre=False):
    import blf
    scale = bpy.context.preferences.system.ui_scale or 1.0
    blf.size(0, size * scale)
    w, h = blf.dimensions(0, text)
    blf.color(0, *rgba)
    blf.position(0, x - (w / 2 if centre else 0), y - (h / 2 if centre else 0), 0)
    blf.draw(0, text)
    return w


def _cover_marker(px, found, box) -> None:
    """The marker icon is only for finding the button: paint it over with the button's own colour and put a small
    calm sign in its place (the same for every look, so a colour-blind user still sees "this one")."""
    x0, y0, x1, y1 = found
    bx = max(box[0] + 2, x0 - 3)
    c = px[min(max((y0 + y1) // 2, 0), px.shape[0] - 1), bx, :3] / 255.0
    _rect(x0 - 1, y0 - 1, x1 + 2, y1 + 2, (*c, 1.0))


def _sign(found, colour) -> None:
    x0, y0, x1, y1 = found
    cy, s = (y0 + y1) / 2, (y1 - y0) * 0.38
    cx = (x0 + x1) / 2
    _tris2d([(cx - s * 0.8, cy - s), (cx - s * 0.8, cy + s), (cx + s * 0.9, cy)], (*colour, 1.0))


# --- the six button looks: draw(box, region width, region height, colour while pointing) ---

def _look_a(box, rw, rh, col):
    x0, y0, x1, y1 = box
    p = _pulse()
    for d in range(1, 9):                          # a soft halo: rings fading outwards, breathing together
        a = (0.55 * (1 - d / 9) ** 1.6) * (0.35 + 0.65 * p)
        _frame(x0 - d, y0 - d, x1 + d, y1 + d, col, a, 1.6)
    _rect(x0, y0, x1, y1, (*col, 0.06 + 0.08 * p))


def _look_b(box, rw, rh, col):
    x0, y0, x1, y1 = box
    _frame(x0 - 2, y0 - 2, x1 + 2, y1 + 2, col, 1.0, 1.6)
    cy = (y0 + y1) / 2
    off = 2.5 * math.sin((_now() - _S["t"]) * 2 * math.pi / BEAT)       # moves 2.5 px, 0.8 times a second
    tip = max(x0 - 4 + off, 6)
    hs = 6
    _tris2d([(tip, cy), (tip - 9, cy + hs), (tip - 9, cy - hs)], (*col, 1.0))
    if tip - 9 > 1:
        _rect(1, cy - 2, tip - 8, cy + 2, (*col, 1.0))
    k = _S["step"] + 1                             # the step's number on a badge in the icon's place
    f = _S.get("found") or box
    r = min((y1 - y0) * 0.40, 9.0)
    bx, by = (f[0] + f[2]) / 2, (f[1] + f[3]) / 2
    _disc(bx, by, r + 1.2, (*CHARCOAL, 1.0))
    _disc(bx, by, r, (*col, 1.0))
    _text(bx, by, str(k), 10, (1, 1, 1, 1), centre=True)
    _S["no_sign"] = True


def _look_c(box, rw, rh, col):
    x0, y0, x1, y1 = box
    a = 0.62 * min(1.0, _age() / 0.4) * _out()      # fades in over 0.4 s, then steady
    m = 3
    dim = (*CHARCOAL, a)
    _rect(0, 0, rw, y0 - m, dim)                   # below, above, left, right of the button
    _rect(0, y1 + m, rw, rh, dim)
    _rect(0, y0 - m, x0 - m, y1 + m, dim)
    _rect(x1 + m, y0 - m, rw, y1 + m, dim)
    _frame(x0 - 2, y0 - 2, x1 + 2, y1 + 2, col, 0.9, 1.3)


def _look_d(box, rw, rh, col):
    x0, y0, x1, y1 = box
    p = _pulse()
    _rect(x0, y0, x1, y1, (*col, 0.18 + 0.20 * p))
    _rect(x0, y0, x0 + 4, y1, (*col, 1.0))


def _look_e(box, rw, rh, col):
    x0, y0, x1, y1 = box
    t = min(1.0, _age() / 0.7)                     # closes in once over 0.7 s, then stays
    ease = 1 - (1 - t) ** 3
    d = 3 + 22 * (1 - ease)
    a = (0.25 + 0.75 * ease) * (0.8 + 0.2 * _pulse()) * _out()
    L = min(10.0, (y1 - y0) * 0.6)
    for cx, cy, sx, sy in ((x0 - d, y0 - d, 1, 1), (x1 + d, y0 - d, -1, 1), (x1 + d, y1 + d, -1, -1),
                           (x0 - d, y1 + d, 1, -1)):
        _lines([(cx + sx * L, cy), (cx, cy), (cx, cy + sy * L)], (*col, a), 2.6)


def _look_f(box, rw, rh, col):
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 - 2, y0 - 2, x1 + 2, y1 + 2
    _frame(x0, y0, x1, y1, BLUE, 0.85, 1.4)
    per = 2 * ((x1 - x0) + (y1 - y0))
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]

    def at(s):
        s %= per
        for (ax, ay), (bx, by) in zip(corners, corners[1:]):
            seg = abs(bx - ax) + abs(by - ay)
            if s <= seg:
                f = s / seg if seg else 0
                return ax + (bx - ax) * f, ay + (by - ay) * f
            s -= seg
        return corners[0]
    head = ((_now() - _S["t"]) / LOOP % 1.0) * per          # once round in 3 s
    n = 14
    pts = [at(head - per * 0.16 * i / n) for i in range(n + 1)]
    for i in range(n):                               # a bright head with a fading tail
        _lines([pts[i], pts[i + 1]], (0.55, 0.75, 1.0, 1.0 - i / n), 3.0, "LINES")



def _rect_path(x0, y0, x1, y1):
    """(perimeter length, at(s)): a point walking round a rectangle, for the running light and the dashes."""
    per = 2 * ((x1 - x0) + (y1 - y0))
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]

    def at(s):
        s %= per
        for (ax, ay), (bx, by) in zip(corners, corners[1:]):
            seg = abs(bx - ax) + abs(by - ay)
            if s <= seg:
                f = s / seg if seg else 0
                return ax + (bx - ax) * f, ay + (by - ay) * f
            s -= seg
        return corners[0]
    return per, at


def _halo(x0, y0, x1, y1, col, depth, strength):
    for d in range(1, depth + 1):
        a = strength * (1 - d / (depth + 1)) ** 1.6
        _frame(x0 - d, y0 - d, x1 + d, y1 + d, col, a, 1.6)


def _look_g(box, rw, rh, col):
    x0, y0, x1, y1 = box
    f = 1 - (1 - min(1.0, _age() / 1.0)) ** 3            # fills once in 1 s, then stays
    o = _out()
    _rect(x0, y0, x1, y0 + 3, (*col, 0.25 * o))
    _rect(x0, y0, x0 + (x1 - x0) * f, y0 + 3, (*col, o))


def _look_h(box, rw, rh, col):
    x0, y0, x1, y1 = box
    _frame(x0 - 1, y0 - 1, x1 + 1, y1 + 1, col, 0.9, 1.3)
    t = (_now() - _S["t"]) % LOOP
    s = t / 1.4                                        # the light crosses in 1.4 s, then rests until the next 3 s
    if s > 1.0:
        return
    w = x1 - x0
    bw = 0.2 * w
    cx = x0 - bw + (w + 2 * bw) * s
    n = 14
    light = tuple(0.4 * c + 0.6 for c in col)
    for i in range(-n, n):
        xa, xb = cx + i * bw / n, cx + (i + 1) * bw / n
        xa, xb = max(xa, x0), min(xb, x1)
        if xb > xa:
            _rect(xa, y0, xb, y1, (*light, 0.34 * (1 - abs(i + 0.5) / n) ** 1.5))


def _look_i(box, rw, rh, col):
    x0, y0, x1, y1 = box
    _frame(x0 - 1, y0 - 1, x1 + 1, y1 + 1, col, 0.9, 1.3)
    ph = ((_now() - _S["t"]) / BEAT) % 1.0
    d = 2 + 16 * ph
    _frame(x0 - d, y0 - d, x1 + d, y1 + d, col, 0.85 * (1 - ph) ** 1.3, 2.0)


def _look_j(box, rw, rh, col):
    x0, y0, x1, y1 = box
    _frame(x0 - 1, y0 - 1, x1 + 1, y1 + 1, col, 0.9, 1.3)
    cy = (y0 + y1) / 2
    u = (y1 - y0) / 22.0
    tap = 0.5 - 0.5 * math.cos(2 * math.pi * (_now() - _S["t"]) / BEAT)   # 0 = lifted, 1 = touching
    tip = x1 - 44 * u - 4 + 6 * u * tap

    def hand(grow, rgba):
        g = grow
        _rect(tip - g, cy - 3.5 * u - g, tip + 20 * u + g, cy + 3.5 * u + g, rgba)          # the pointing finger
        _disc(tip, cy, 3.5 * u + g, rgba, 12)
        _rect(tip + 20 * u - g, cy - 9 * u - g, tip + 38 * u + g, cy + 8 * u + g, rgba)     # the palm
        _rect(tip + 22 * u - g, cy + 7 * u, tip + 32 * u + g, cy + 13 * u + g, rgba)         # the thumb
    hand(1.6, (*CHARCOAL, 1.0))
    hand(0.0, (0.96, 0.96, 0.96, 1.0))


def _look_k(box, rw, rh, col):
    x0, y0, x1, y1 = box
    p = _pulse()
    _halo(x0 - 2, y0 - 2, x1 + 2, y1 + 2, col, 7, 0.38 * (0.7 + 0.3 * p))
    _frame(x0 - 2, y0 - 2, x1 + 2, y1 + 2, col, 1.0, 1.6)


def _look_l(box, rw, rh, col):
    x0, y0, x1, y1 = box
    per, at = _rect_path(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    dash, gap = 8.0, 6.0
    off = ((_now() - _S["t"]) / BEAT % 1.0) * (dash + gap)          # one dash period per 1.5 s
    s = -off
    while s < per:
        a, b = max(s, 0.0), min(s + dash, per)
        if b > a:
            pts = [at(a + (b - a) * i / 4) for i in range(5)]
            _lines(pts, (*col, 1.0), 2.2)
        s += dash + gap


def _dim_except(rw, rh, holes, rgba):
    """A see-through sheet over the whole region except the rectangles in ``holes`` (x0, y0, x1, y1)."""
    ys = sorted({0, rh, *[min(max(v, 0), rh) for h in holes for v in (h[1], h[3])]})
    for ya, yb in zip(ys, ys[1:]):
        if yb <= ya:
            continue
        mid = (ya + yb) / 2
        cut = sorted((h[0], h[2]) for h in holes if h[1] < mid < h[3])
        x = 0
        for hx0, hx1 in cut:
            if hx0 > x:
                _rect(x, ya, hx0, yb, rgba)
            x = max(x, hx1)
        if x < rw:
            _rect(x, ya, rw, yb, rgba)


def _look_m(box, rw, rh, col):
    x0, y0, x1, y1 = box
    a = 0.30 * min(1.0, _age() / 0.4) * _out()
    holes = [(x0 - 3, y0 - 3, x1 + 3, y1 + 3)]
    lb = _S.get("lesson_band")
    if lb:
        holes.append((0, lb[0], rw, lb[1]))
    _dim_except(rw, rh, holes, (*CHARCOAL, a))
    _frame(x0 - 2, y0 - 2, x1 + 2, y1 + 2, col, 0.9, 1.3)


def _look_n(box, rw, rh, col):
    x0, y0, x1, y1 = box
    _frame(x0 - 1, y0 - 1, x1 + 1, y1 + 1, col, 0.9, 1.3)
    w, h, gap = 38.0, 18.0, 7.0
    up = y1 + gap + h < rh
    by = y1 + gap if up else y0 - gap - h
    bx = max(min(x1 - 14 - w, rw - w - 4), 4)
    cx = bx + w / 2
    _lines([(cx, y1 if up else y0), (cx, by if up else by + h)], (*col, 1.0), 2.0, "LINES")
    _rect(bx - 1.5, by - 1.5, bx + w + 1.5, by + h + 1.5, (*CHARCOAL, 1.0))
    _rect(bx, by, bx + w, by + h, (*col, 1.0))
    ty = by + h / 2
    _tris2d([(bx + 6, ty - 5), (bx + 6, ty + 5), (bx + 15, ty)], (1, 1, 1, 1))
    _text(bx + 26, ty, str(_S["step"] + 1), 11, (1, 1, 1, 1), centre=True)

_BUTTON_DRAW = {"A": _look_a, "B": _look_b, "C": _look_c, "D": _look_d, "E": _look_e, "F": _look_f,
                "G": _look_g, "H": _look_h, "I": _look_i, "J": _look_j, "K": _look_k, "L": _look_l, "M": _look_m,
                "N": _look_n}


# --- the three closed-section markers ---

def _header_box(px, header, rw):
    """The header row round the header marker: its bottom and top from the colour above and below the marker."""
    import numpy as np
    x0, y0, x1, y1 = header
    cx, cy = max(x0 - 2, 0), (y0 + y1) // 2
    col = px[:, cx, :3].astype(np.int16)
    own = col[cy]
    bottom, top = _walk(col, cy, -1, own), _walk(col, cy, 1, own)
    row = px[min(bottom + 1, top), :, :3].astype(np.int16)
    left = _walk(row, cx, -1, own)
    right = _walk(row, cx, 1, own)
    if top - bottom < (y1 - y0):
        bottom, top = y0 - 5, y1 + 5
    return int(left), int(bottom), int(right if right > x1 + 20 else rw - 8), int(top)


def _section_1(hb, marker, rw, rh, col):
    x0, y0, x1, y1 = marker
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ph = ((_now() - _S["t"]) / BEAT) % 1.0         # a ring grows from the dot every 1.5 s
    _ring(cx, cy, 5 + 9 * ph, (*col, 0.8 * (1 - ph)), 2.0)
    _disc(cx, cy, 5, (*col, 1.0))


def _section_2(hb, marker, rw, rh, col):
    l, b, r, t = hb
    p = _pulse()
    _rect(l, b, r, t, (*col, 0.22 + 0.22 * p))
    _frame(l, b, r, t, col, 0.9, 1.3)


def _section_3(hb, marker, rw, rh, col):
    l, b, r, t = hb
    h = t - b
    cx, cy = l + h * 0.55, (b + t) / 2              # Blender's fold triangle sits about half a row in
    p = _pulse()
    _ring(cx, cy, h * 0.42 + 1.5 * p, (*col, 0.7 + 0.3 * p), 2.2)
    w = _text(0, -100, "Open", 11, (0, 0, 0, 0))
    tx = r - w - 30
    _rect(tx - 6, b + 3, tx + w + 6, t - 3, (*col, 0.9))
    _text(tx, cy - 4, "Open", 11, (1, 1, 1, 1))



def _section_4(hb, marker, rw, rh, col):
    l, b, r, t = hb
    p = _pulse()
    _rect(l, b, r, t, (*col, 0.07 + 0.06 * p))
    _rect(l, b, l + 6, t, (*col, 1.0))


def _section_5(hb, marker, rw, rh, col):
    l, b, r, t = hb
    h = t - b
    p = _pulse()
    _rect(l, b, r, t, (*col, 0.24 + 0.08 * p))               # the header and its label in the colour
    _rect(l, b, r, b + 2, (*col, 1.0))
    cx, cy, rad = l + h * 0.55, (b + t) / 2, h * 0.36
    _disc(cx, cy, rad, (*col, 1.0))
    ang = -(0.5 - 0.5 * math.cos(2 * math.pi * (_now() - _S["t"]) / BEAT)) * (math.pi / 2)   # nods: right -> down
    s = rad * 0.62
    pts = [(s * 0.9, 0), (-s * 0.6, s * 0.8), (-s * 0.6, -s * 0.8)]
    ca, sa = math.cos(ang), math.sin(ang)
    _tris2d([(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts], (1, 1, 1, 1))


def _section_6(hb, marker, rw, rh, col):
    l, b, r, t = hb
    p = _pulse()
    _halo(l, b, r, t, col, 6, 0.42 * (0.45 + 0.55 * p))
    _rect(l, b, r, t, (*col, 0.06))
    _frame(l, b, r, t, col, 1.0, 1.6)


def _section_7(hb, marker, rw, rh, col):
    l, b, r, t = hb
    cy = (b + t) / 2
    h = min(t - b, 26.0)
    off = 2.5 * math.sin((_now() - _S["t"]) * 2 * math.pi / BEAT)
    tip = 36 + off
    pts = [(2, cy - h / 2), (tip - h * 0.45, cy - h / 2), (tip, cy), (tip - h * 0.45, cy + h / 2), (2, cy + h / 2)]
    _tris2d([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3], pts[0], pts[3], pts[4]], (*col, 1.0))
    _text(13, cy, str(_S["step"] + 1), 11, (1, 1, 1, 1), centre=True)

_SECTION_DRAW = {"1": _section_1, "2": _section_2, "3": _section_3, "4": _section_4, "5": _section_5,
                 "6": _section_6, "7": _section_7}


def _cover_header_marker(px, header):
    x0, y0, x1, y1 = header
    c = px[(y0 + y1) // 2, max(x0 - 2, 0), :3] / 255.0
    _rect(x0 - 1, y0 - 1, x1 + 2, y1 + 2, (*c, 1.0))


def _timed(key, fn, *a):
    t = time.perf_counter()
    fn(*a)
    st = _S["stats"]["look"].setdefault(key, [0, 0.0])
    st[0] += 1
    st[1] += time.perf_counter() - t


def _draw_sidebar() -> None:
    """Side panel (region UI), after Blender drew it: find the markers in its pixels, draw the chosen look."""
    if current() is None or step() is None:
        return
    try:
        import gpu
        import numpy as np
        region = bpy.context.region
        t = time.perf_counter()
        fb = gpu.state.active_framebuffer_get()
        vp = gpu.state.viewport_get()
        buf = fb.read_color(vp[0], vp[1], vp[2], vp[3], 4, 0, "UBYTE")
        buf.dimensions = vp[2] * vp[3] * 4
        px = np.array(buf, dtype=np.uint8).reshape(vp[3], vp[2], 4)
        found = _find(px, MARK_BUTTON)
        header = _find(px, MARK_HEADER)
        box = button_box(px, found) if found is not None else None
        hbox = _header_box(px, header, region.width) if header is not None else None
        lt, le = _find(px, MARK_LESSON_TOP), _find(px, MARK_LESSON_END)
        _S["lesson_band"] = (le[1] - 6, lt[3] + 8) if (lt is not None and le is not None) else None
        _S["stats"]["reads"] += 1
        _S["stats"]["read_s"] += time.perf_counter() - t
        _S["found"], _S["found_header"], _S["box"], _S["hbox"] = found, header, box, hbox
        if box is not None:
            _S["found_right"] = box[2]
        if os.environ.get("FR_LESSON_DUMP"):
            np.save(os.environ["FR_LESSON_DUMP"], px)
        _S["region"] = (region.x, region.y, region.width, region.height)
        _S["drawn"] = True
        col = OK if _S["phase"] == "done" else colour()
        gpu.state.blend_set("ALPHA")
        if header is not None:
            _cover_header_marker(px, header)
        if lt is not None:
            _cover_header_marker(px, lt)
        if le is not None:
            _cover_header_marker(px, le)
        if found is not None:
            _cover_marker(px, found, box)
            look = LOOKS["button"]
            if look == "F" and _S["phase"] != "done":
                col = BLUE
            _S["no_sign"] = False
            _timed("button " + look, _BUTTON_DRAW[look], box, region.width, region.height, col)
            if not _S["no_sign"]:
                _sign(found, col)
        elif header is not None:                     # the section is closed: its header shows the way
            look = LOOKS["section"]
            _timed("section " + look, _SECTION_DRAW[look], hbox, header, region.width, region.height, col)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 - drawing must never break the panel
        import traceback
        _S["note"] = f"sidebar draw: {e} {traceback.format_exc(limit=2)}"


_BATCH: dict = {}


def _part_objects(scene, names):
    from . import build
    out = []
    for o in scene.objects:
        if o.get(build.PROP_NAME) in names:
            out.append(o)
            out.extend(c for c in o.children_recursive if c.type == "MESH")
    return [o for o in dict.fromkeys(out) if o.type == "MESH" and o.visible_get()]


def _mesh(ob):
    """Once per mesh: its triangles' corners, each triangle's normal and its outline edges (object space)."""
    import numpy as np
    me = ob.data
    key = (me.name, len(me.polygons))
    hit = _BATCH.get(key)
    if hit is None:
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        corners = co[tri]
        n = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        # outline: edges with one triangle (open border) or whose two triangles meet at more than 30 degrees
        e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
        owner = np.tile(np.arange(len(tri)), 3)
        order = np.lexsort((e[:, 1], e[:, 0]))
        e, owner = e[order], owner[order]
        same = np.all(e[1:] == e[:-1], axis=1)
        keep = np.ones(len(e), bool)
        pair = np.nonzero(same)[0]                    # e[i] and e[i+1] are one edge of two triangles
        sharp = np.einsum("ij,ij->i", n[owner[pair]], n[owner[pair + 1]]) < math.cos(math.radians(30))
        keep[pair + 1] = False
        keep[pair[~sharp]] = False
        edges = co[e[keep]].reshape(-1, 3)
        hit = {"tris": corners.reshape(-1, 3), "n": n, "edges": edges}
        _BATCH[key] = hit
    return hit


def _tris(ob):
    return _mesh(ob)["tris"]


def _part_colour(ob):
    m = ob.active_material
    if m is not None:
        return tuple(m.diffuse_color[:3])
    return (0.7, 0.7, 0.7)


def _fill(obs, col, alpha):
    from gpu_extras.batch import batch_for_shader
    import gpu
    sh = _shader()
    gpu.state.depth_test_set("NONE")
    for ob in obs:
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(ob.matrix_world)
        sh.uniform_float("color", (*col, alpha))
        batch_for_shader(sh, "TRIS", {"pos": _tris(ob)}).draw(sh)
        gpu.matrix.pop()


def _edge_passes(obs, passes):
    """passes: (depth test, line width, rgba) – the parts' outline edges drawn once for each."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    vp = gpu.state.viewport_get()
    sh = _shader("POLYLINE_UNIFORM_COLOR")
    sh.uniform_float("viewportSize", (vp[2], vp[3]))
    for depth, width, rgba in passes:
        gpu.state.depth_test_set(depth)
        sh.uniform_float("lineWidth", width)
        sh.uniform_float("color", rgba)
        for ob in obs:
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(ob.matrix_world)
            batch_for_shader(sh, "LINES", {"pos": _mesh(ob)["edges"]}).draw(sh)
            gpu.matrix.pop()
    gpu.state.depth_test_set("NONE")


def _part_1(obs, col):
    _fill(obs, col, 0.14 + 0.24 * _pulse())


def _part_2(obs, col):
    p = _pulse()
    _edge_passes(obs, (("NONE", 1.5, (*col, 0.45 + 0.2 * p)), ("LESS_EQUAL", 3.0, (*col, 1.0))))


def _part_3(obs, col):
    _faded(obs, col, 0.68)


def _part_4(obs, col):
    _fill(obs, col, 0.42)
    _edge_passes(obs, (("NONE", 3.0, (*col, 1.0)),))


def _part_5(obs, col):
    p = 0.35 + 0.65 * _pulse()
    _fill(obs, col, 0.05 + 0.10 * p)
    _edge_passes(obs, (("NONE", 11.0, (*col, 0.07 * p)), ("NONE", 6.0, (*col, 0.16 * p)),
                       ("NONE", 3.0, (*col, 0.45 * p + 0.2)), ("NONE", 1.5, (*col, 1.0))))


def _part_6(obs, col):
    _faded(obs, col, 0.80, ghost=True, outline=True)


def _part_7(obs, col):
    _part_2(obs, col)
    _S["leader"] = True


def _part_8(obs, col):
    _faded(obs, col, 0.68, outline=True)


def _faded(obs, col, alpha, ghost=False, outline=False):
    """Everything greyed by a see-through sheet over the whole view (the rest optionally as faint ghost lines), then
    the parts drawn again on top in their own colour with simple light (their depth starts afresh: the sheet hides
    the rest, the part hides only itself), optionally with an outline in the colour."""
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    a = alpha * min(1.0, _age() / 0.4) * _out()
    gpu.state.depth_test_set("NONE")
    gpu.matrix.push()
    gpu.matrix.push_projection()
    from mathutils import Matrix
    gpu.matrix.load_identity()
    gpu.matrix.load_projection_matrix(Matrix.Identity(4))
    _rect(-1, -1, 1, 1, (0.23, 0.24, 0.25, a))
    gpu.matrix.pop_projection()
    gpu.matrix.pop()
    if a < 0.05:
        return
    if ghost:
        mine = {o.name for o in obs}
        rest = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.visible_get() and o.name not in mine
                and not o.name.startswith("FR ")]
        _edge_passes(rest, (("NONE", 1.0, (0.85, 0.88, 0.92, 0.28 * min(1.0, a / alpha))),))
    fb = gpu.state.active_framebuffer_get()
    fb.clear(depth=1.0)
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(True)
    sh = _shader("SMOOTH_COLOR")
    light = np.array([0.35, -0.55, 0.76])
    rv3d = bpy.context.region_data
    view = np.array(rv3d.view_rotation @ __import__("mathutils").Vector((0, 0, 1)))
    for ob in obs:
        m = _mesh(ob)
        rot = np.array(ob.matrix_world.to_3x3().normalized())
        nw = m["n"] @ rot.T
        if np.isfinite(nw).all():
            shade = 0.30 + 0.45 * np.abs(nw @ light) + 0.25 * np.abs(nw @ view)
        else:
            shade = np.ones(len(nw))
        c = np.clip(np.outer(shade, _part_colour(ob)), 0, 1)
        rgba = np.repeat(np.hstack([c, np.ones((len(c), 1))]), 3, axis=0).astype(np.float32)
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(ob.matrix_world)
        batch_for_shader(sh, "TRIS", {"pos": m["tris"], "color": rgba}).draw(sh)
        gpu.matrix.pop()
    gpu.state.depth_mask_set(False)
    if outline:
        _edge_passes(obs, (("NONE", 3.0, (*col, 1.0)),))
    gpu.state.depth_test_set("NONE")


_PART_DRAW = {"1": _part_1, "2": _part_2, "3": _part_3, "4": _part_4, "5": _part_5, "6": _part_6, "7": _part_7,
              "8": _part_8}


def _draw_parts() -> None:
    st = step()
    if st is None or not st.parts:
        return
    try:
        import gpu
        col = OK if _S["phase"] == "done" else colour()
        gpu.state.blend_set("ALPHA")
        obs = _part_objects(bpy.context.scene, st.parts)
        look = LOOKS["part"]
        _S["leader"] = False
        _timed("part " + look, _PART_DRAW[look], obs, col)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001
        import traceback
        _S["note"] = f"part draw: {e} {traceback.format_exc(limit=2)}"


def card_lines(st: Step, more: bool, phase: str, width: int = 44) -> list:
    """The card's lines: (text, kind) with kind title / text / more / hint."""
    les = current()
    k, n = _S["step"] + 1, len(les.steps) if les else 0
    head = ("Done: " if phase == "done" else "") + st.title
    lines = [(f"{head}   ({k} of {n})", "title")]
    lines += [(t, "text") for t in textwrap.wrap(st.say, width)]
    if more and st.more:
        lines += [(t, "more") for t in textwrap.wrap(st.more, width)]
    hint = {"SHOW": "Next in the Lesson panel", "BUILD": "Do it in the glowing place, or 'Do it for me'"}[_S["mode"]]
    if phase == "done":
        hint = "Next in the Lesson panel" if _S["mode"] == "SHOW" else "Well done – the next step follows"
    lines.append((("More: M  ·  " if st.more and not more else "") + hint, "hint"))
    return lines


def place_card(box, size, region_size, gap=40):
    """Where the card goes: right of the part's box on screen, else left, else above, else below – never on it.

    box: (x0, y0, x1, y1) of the part on screen; size: (w, h); returns (x, y) of the card's lower left corner."""
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


def _free_width(area, region) -> int:
    """The view's width that the side panel does not cover (with region overlap it is drawn over the view)."""
    w = region.width
    for r in area.regions:
        if r.type == "UI" and r.width > 1 and r.x + r.width >= region.x + region.width - 2:
            w = min(w, r.x - region.x)
    return max(200, w)


def _draw_card() -> None:
    st = step()
    if st is None:
        return
    try:
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        region, rv3d = bpy.context.region, bpy.context.region_data
        scale = bpy.context.preferences.system.ui_scale or 1.0
        lines = card_lines(st, _S["more"], _S["phase"])
        font = 0
        sizes = {"title": 15, "text": 13, "more": 12, "hint": 11}
        lh = {k: v * 1.45 * scale for k, v in sizes.items()}
        wmax = 0
        for text, kind in lines:
            blf.size(font, sizes[kind] * scale)
            wmax = max(wmax, blf.dimensions(font, text)[0])
        pad = 10 * scale
        w, h = wmax + 2 * pad, sum(lh[k] for _t, k in lines) + 2 * pad
        obs = _part_objects(bpy.context.scene, st.parts) if st.parts else []
        box = _screen_box(region, rv3d, obs) if obs else None
        if box is None:
            box = (region.width * 0.5, region.height * 0.5, region.width * 0.5, region.height * 0.5)
        x, y = place_card(box, (w, h), (_free_width(bpy.context.area, region), region.height))
        _S["card"] = (x, y, w, h, box)
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        col = OK if _S["phase"] == "done" else (BLUE if LOOKS["button"] == "F" else colour())
        if obs:                                       # the line from the card to the part
            bx = box[2] if x > box[2] else (box[0] if x + w < box[0] else (box[0] + box[2]) / 2)
            by = (box[1] + box[3]) / 2 if (x > box[2] or x + w < box[0]) else (box[3] if y > box[3] else box[1])
            ax = x if x > box[2] else (x + w if x + w < box[0] else x + w / 2)
            ay = y + h / 2 if (x > box[2] or x + w < box[0]) else (y if y > box[3] else y + h)
            line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
            vp = gpu.state.viewport_get()
            line.uniform_float("viewportSize", (vp[2], vp[3]))
            for width, c in ((4.0, DARK), (2.0, (*col, 1.0))):
                line.uniform_float("lineWidth", width)
                line.uniform_float("color", c)
                batch_for_shader(line, "LINES", {"pos": [(ax, ay), (bx, by)]}).draw(line)
        if obs and _S.get("leader"):                  # part look 7: a bold leader with a dot that travels to the part
            u = ((_now() - _S["t"]) / BEAT) % 1.0
            for width, c in ((7.0, DARK), (4.0, (*col, 1.0))):
                line.uniform_float("lineWidth", width)
                line.uniform_float("color", c)
                batch_for_shader(line, "LINES", {"pos": [(ax, ay), (bx, by)]}).draw(line)
            _disc(bx, by, 7, (*col, 1.0))
            _disc(ax + (bx - ax) * u, ay + (by - ay) * u, 5, (1, 1, 1, 1))
        quad = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        flat.uniform_float("color", DARK)
        batch_for_shader(flat, "TRI_FAN", {"pos": quad}).draw(flat)
        flat.uniform_float("color", (*col, 1.0))
        batch_for_shader(flat, "TRI_FAN", {"pos": [(x, y), (x + 4 * scale, y), (x + 4 * scale, y + h),
                                                   (x, y + h)]}).draw(flat)
        ty = y + h - pad
        for text, kind in lines:
            blf.size(font, sizes[kind] * scale)
            ty -= lh[kind]
            c = {"title": (*col, 1.0), "text": (0.95, 0.95, 0.95, 1.0), "more": (0.80, 0.85, 0.95, 1.0),
                 "hint": (0.6, 0.6, 0.6, 1.0)}[kind]
            blf.color(font, *c)
            blf.position(font, x + pad, ty + 0.3 * lh[kind], 0)
            blf.draw(font, text)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"card draw: {e}"


def _add_handlers() -> None:
    if _S["handles"]:
        return
    sv = bpy.types.SpaceView3D
    _S["handles"] = [(sv.draw_handler_add(_draw_sidebar, (), "UI", "POST_PIXEL"), "UI"),
                     (sv.draw_handler_add(_draw_parts, (), "WINDOW", "POST_VIEW"), "WINDOW"),
                     (sv.draw_handler_add(_draw_card, (), "WINDOW", "POST_PIXEL"), "WINDOW")]


def _remove_handlers() -> None:
    for h, region in _S["handles"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, region)
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []


def redraw() -> None:
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---------------------------------------------------------------------------
# the flow
# ---------------------------------------------------------------------------

def _set_phase(phase: str) -> None:
    _S["phase"], _S["t_phase"] = phase, time.time()
    _S.setdefault("history", []).append((_S["t_phase"], _S["mode"], _S["step"], phase))
    _S["target_at"] = None


def _point(scene) -> None:
    """Point at the current step: select what it acts on, show the side panel's Fresing tab."""
    st = step()
    _S["more"] = False
    _S["scrolls"] = 0
    bpy.context.window_manager.fresing_lesson_fold = True
    if st is None:
        _set_phase("end")
        return
    if st.select:
        from . import build
        for o in scene.objects:
            o.select_set(o.get(build.PROP_NAME) in st.select)
        for o in scene.objects:
            if o.get(build.PROP_NAME) == st.select[0]:
                bpy.context.view_layer.objects.active = o
                break
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for r in area.regions:
                    if r.type == "UI":
                        try:
                            r.active_panel_category = "Fresing"
                        except TypeError:
                            pass
    _set_phase("point" if _S["mode"] == "SHOW" else "wait")


def do_step(scene) -> None:
    """Show me / Do it for me: the tour's own call, one undo step."""
    st = step()
    if st is None or st.do is None:
        return
    st.do(scene)
    bpy.context.view_layer.update()
    try:
        bpy.ops.ed.undo_push(message=f"Lesson: {st.title}")
    except RuntimeError:
        pass
    _set_phase("done")


def _tick():
    """20 times a second while a lesson runs: the pulse, Show me's timing, Build it yourself's check."""
    if current() is None:
        _S["timer"] = False
        return None
    scene = bpy.context.scene
    now = time.time()
    st = step()
    ph = _S["phase"]
    _S["ticks"] = _S.get("ticks", 0) + 1
    try:
        if st is not None and ph == "point" and _S["found"] is not None and _S.get("target_at") is None:
            _S["target_at"] = now                   # the glow is on screen from now on
            _S["target_seen"] = now
        if st is not None and ph == "point" and (now - (_S.get("target_at") or now) > SHOW_DELAY
                                                 or now - _S["t_phase"] > SHOW_DELAY + 3.0):
            do_step(scene)                          # seen for SHOW_DELAY s (or the target never came into view)
        elif st is not None and ph == "wait" and st.done and st.done(scene):
            _set_phase("done")
            _S["seen_at"] = now
        elif st is not None and ph == "done":
            age = now - _S["t_phase"]
            if st.show and age < 1.5:
                st.show(scene, age / 1.5)
            elif st.show and not _S.get("shown"):
                st.show(scene, 1.0)
                _S["shown"] = True
            if _S["mode"] == "BUILD" and age > DONE_PAUSE:
                next_step(scene)
        if ph in ("point", "wait") and _S.get("drawn"):
            _S["drawn"] = False
            if _S["found"] is None and _S["found_header"] is None and _S["scrolls"] < 30:
                _scroll_towards()
            elif _S["found"] is not None:
                _nudge()
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"tick: {e}"
    redraw()
    return 1.0 / PULSE_HZ


def _scroll_towards() -> None:
    """Neither marker is on screen: the side panel scrolls – first to the top, then about 60 % of its height per
    redraw, so nothing is jumped over (a whole page skipped the camera buttons in the first try)."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            sb = next(r for r in area.regions if r.type == "UI")
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb):
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


def _nudge() -> None:
    """The target is on screen but at an edge (half hidden): scroll a little to bring it in."""
    x0, y0, x1, y1 = _S["found"]
    h = _S.get("region", (0, 0, 0, 0))[3]
    margin = 60
    if y1 > h - margin:
        _scroll("scroll_up")
    elif y0 < margin:
        _scroll("scroll_down")


def _scroll(op: str) -> None:
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                sb = next(r for r in area.regions if r.type == "UI")
                with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb):
                    getattr(bpy.ops.view2d, op)()


def next_step(scene) -> None:
    les = current()
    _S["shown"] = False
    _S["step"] = min(_S["step"] + 1, len(les.steps))
    _point(scene)


def start(scene, lesson_id: str, mode: str = "SHOW") -> None:
    les = LESSONS[lesson_id]
    _icons()
    _S.update(lesson=lesson_id, mode=mode, t=time.time(), note="", shown=False)
    _S["step"] = first_not_done(scene, les)
    scene["fr_lesson"] = lesson_id                 # reopening the project offers to go on
    _wrap_draws()
    _add_handlers()
    _point(scene)
    if not _S["timer"]:
        bpy.app.timers.register(_tick, first_interval=0.0)
        _S["timer"] = True


def stop() -> None:
    _S["lesson"] = None
    _unwrap_draws()
    _remove_handlers()
    _BATCH.clear()
    try:
        redraw()
    except Exception:  # noqa: BLE001
        pass


@persistent
def _after_undo(_dummy=None):
    les = current()
    if les is not None:
        _S["step"] = first_not_done(bpy.context.scene, les)
        _point(bpy.context.scene)


@persistent
def _before_load(_dummy=None):
    stop()


# ---------------------------------------------------------------------------
# the Lesson panel and its buttons
# ---------------------------------------------------------------------------

class FRESING_OT_lesson_start(bpy.types.Operator):
    """Starts a lesson on this test model. Show me: the app does each step while you watch. Build it yourself: the
    app shows where to click and goes on when you did it"""
    bl_idname = "fresing.lesson_start"
    bl_label = "Start lesson"
    lesson: bpy.props.StringProperty(default="crane")
    mode: bpy.props.EnumProperty(items=[("SHOW", "Show me", ""), ("BUILD", "Build it yourself", "")])

    def execute(self, context):
        start(context.scene, self.lesson, self.mode)
        return {"FINISHED"}


class FRESING_OT_lesson_next(bpy.types.Operator):
    """Goes to the next step of the lesson"""
    bl_idname = "fresing.lesson_next"
    bl_label = "Next"

    def execute(self, context):
        if _S["phase"] in ("point", "wait"):
            do_step(context.scene)                  # Next before it was done: do it first
        else:
            next_step(context.scene)
        return {"FINISHED"}


class FRESING_OT_lesson_do(bpy.types.Operator):
    """Does this step for you (the same as the button that glows), then goes on"""
    bl_idname = "fresing.lesson_do"
    bl_label = "Do it for me"

    def execute(self, context):
        do_step(context.scene)
        return {"FINISHED"}


class FRESING_OT_lesson_back(bpy.types.Operator):
    """Takes the last step back (undo) and shows it again"""
    bl_idname = "fresing.lesson_back"
    bl_label = "Back"

    def execute(self, context):
        bpy.ops.ed.undo()
        return {"FINISHED"}


class FRESING_OT_lesson_more(bpy.types.Operator):
    """Shows more text about this step, or less"""
    bl_idname = "fresing.lesson_more"
    bl_label = "More"

    def execute(self, context):
        _S["more"] = not _S["more"]
        redraw()
        return {"FINISHED"}


class FRESING_OT_lesson_stop(bpy.types.Operator):
    """Ends the lesson; the project stays as it is"""
    bl_idname = "fresing.lesson_stop"
    bl_label = "Stop lesson"

    def execute(self, context):
        stop()
        return {"FINISHED"}


class FRESING_PT_lesson(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fresing"
    bl_label = "Lesson"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return current() is not None

    def draw_header_preset(self, context):
        les = current()
        self.layout.label(text=f"{min(_S['step'] + 1, len(les.steps))} of {len(les.steps)}")
        if _S.get("icons") is not None:
            self.layout.label(text="", icon_value=_S["icons"]["lesson_top"].icon_id)

    def draw(self, context):
        from .ui import big_row, wrap
        layout = self.layout
        les, st = current(), step()
        layout.label(text=f"{les.title} – {'Show me' if _S['mode'] == 'SHOW' else 'Build it yourself'}",
                     icon="HELP")
        if st is None:
            wrap(layout, context, "Lesson finished. Everything you made stays in the project.", icon="CHECKMARK")
            layout.operator("fresing.lesson_stop", icon="X")
            return
        box = layout.box()
        box.label(text=st.title, icon="CHECKMARK" if _S["phase"] == "done" else "RIGHTARROW")
        wrap(box, context, st.say)
        if st.more:
            box.operator("fresing.lesson_more", text="Less" if _S["more"] else "More …", emboss=False,
                         icon="DISCLOSURE_TRI_DOWN" if _S["more"] else "DISCLOSURE_TRI_RIGHT")
            if _S["more"]:
                wrap(box, context, st.more)
        f = functions.FUNCTIONS.get(st.function)
        if f is not None and f.guide:
            box.operator("wm.url_open", text="This in the user guide", icon="HELP").url = f"guide#{f.guide}"
        row = big_row(layout)
        row.operator("fresing.lesson_back", text="Back", icon="TRIA_LEFT")
        if _S["mode"] == "BUILD" and _S["phase"] == "wait":
            row.operator("fresing.lesson_do", icon="PLAY")
        else:
            row.operator("fresing.lesson_next", text="Next", icon="TRIA_RIGHT")
        layout.operator("fresing.lesson_stop", icon_value=_S["icons"]["lesson_end"].icon_id)


CLASSES = (FRESING_OT_lesson_start, FRESING_OT_lesson_next, FRESING_OT_lesson_do, FRESING_OT_lesson_back,
           FRESING_OT_lesson_more, FRESING_OT_lesson_stop, FRESING_PT_lesson)


def register():
    bpy.types.WindowManager.fresing_lesson_fold = bpy.props.BoolProperty(default=True)
    for c in CLASSES:
        bpy.utils.register_class(c)
    for lst, fn in ((bpy.app.handlers.undo_post, _after_undo), (bpy.app.handlers.redo_post, _after_undo),
                    (bpy.app.handlers.load_pre, _before_load)):
        if fn not in lst:
            lst.append(fn)
    from . import lesson_crane  # noqa: F401 - the crane lesson registers itself


def unregister():
    stop()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
