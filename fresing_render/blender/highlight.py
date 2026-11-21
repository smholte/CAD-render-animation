"""Lesson highlight: shows a button, a folded section or a part "this one" (task 0062).

The lessons themselves (Show me / Build it yourself, study 0123) come in a later task. This module is only what lets
a lesson **point**:

    highlight.point(panel="FRESING_PT_import", button="fresing.import_step")     # a button or a setting
    highlight.point_function("joints.rotate", parts=("BOOM",))                   # an entry of core/functions.py
    highlight.clear()

How it works. Blender's Python cannot ask where a button is. While something is pointed at, the target panel's
``draw`` (whatever it is then: the title row and body of ``panels.py``) gets a stand-in for ``self.layout`` (``_L``)
that passes every call through, except the target: a button's icon becomes a small *marker* icon of one exact
colour, a setting gets the marker in front of it. A draw handler of the side panel then reads the side panel's own
pixels, finds that colour, paints the marker over and draws the look round the button it sits on (``button_box``
finds the button's own edges, so of two joined buttons only the target is marked; a greyed-out button is found
too). The title rows of the target panel and of the panels it sits in carry a second marker, put in by their
``draw_header``, right after the fold arrow: while the button is not on screen (its section is folded), the lowest
marked title row on screen gets the section look. A fold (``ui.fold``) that holds the target opens by itself
(``fold_open``, asked by ``ui.HOOKS["fold"]``). Parts are drawn again in the 3D view by a second draw handler.
Scrolling the side panel to the target is the lesson's job: ``found()`` says what is on screen and where.

Six looks, two of each kind, the first the default (the owner's picks from studies 0168 and 0185; he settles each
pair on his own PC):

* button **C** – spotlight: the rest of the side panel dimmed, the button clear with a thin outline; panels named
  with ``keep_clear`` (a Lesson panel) keep their full brightness · **D** – a bar on the button's left edge, the
  button tinted (its label is left as it is, so it stays readable), breathing;
* section **5** – the header in the colour, a fold arrow that nods slowly · **4** – a bar on the header's left edge;
* part **3** – everything else faded, the part clear in its own colour · **1** – a see-through glow that breathes.

One colour (``set_colour``, default Fresing Green). A breath takes ``BEAT`` = 1.5 s, so loops join after 3 s.

Nothing here runs unless something is pointed at: no draw handler, no wrapped draw, no timer, no app handler.
"""

from __future__ import annotations

import math
import os
import sys
import time
import types

import bpy
from bpy.app.handlers import persistent

from ..core import functions

GREEN = (0.278, 0.608, 0.161)               # Fresing Green #479B29 (site/style.css)
CHARCOAL = (0.102, 0.125, 0.153)            # Deep Charcoal #1A2027: what dims
BEAT = 1.5                                  # seconds for one breath or nod: never faster than one per second
LOOP = 3.0                                  # every movement joins up after this many seconds (clips)
LOOKS = {                                   # kind -> its two looks, the default first
    "button": {"C": "Spotlight: the rest of the side panel dimmed, the button clear with a thin outline",
               "D": "A bar on the button's left edge, the button tinted, breathing"},
    "section": {"5": "The header in the colour, a fold arrow that nods slowly",
                "4": "A bar on the header's left edge"},
    "part": {"3": "The rest faded: everything else greyed, the part clear in its own colour",
             "1": "Glow: the part covered in the colour, see-through, breathing"},
}
# The marker icons' exact colours (channels full or empty, at least one empty): found again in the side panel's pixels.
# button: the target button's icon · field: a label in front of the target setting · header: a panel's title row ·
# top / end: the title row and the last row of a panel that look C keeps clear.
MARKS = {"button": (255, 0, 255), "field": (255, 255, 0), "header": (0, 255, 255), "top": (0, 0, 255),
         "end": (0, 255, 0)}
NEAR = 0x00F8F8F8                           # a pixel has a marker's colour when these bits of r, g, b agree
TICK = 0.05                                 # seconds between two redraws while a look moves

_S: dict = {"target": None, "wrapped": [], "handles": [], "timer": False, "icons": None, "looks": {}, "pref": {},
            "colour": None, "pref_colour": None, "clear": (), "t": 0.0, "clock": None, "seen": {}, "note": "",
            "parts": [], "part_obs": None, "marked": False, "fold_next": False, "outside": False, "anywhere": False, "again": False,
            "lit": None,
            "stats": {"side": [0, 0.0], "read": [0, 0.0], "parts": [0, 0.0]}}
_HOOKED: set = set()                        # panels whose header marker is drawn through mark_header()
_GEO: dict = {}                             # per mesh: its triangles as GPU batches


# ---------------------------------------------------------------------------
# looks, colour, clock
# ---------------------------------------------------------------------------

def set_look(kind: str, key: str = "") -> None:
    """Picks a look: set_look("button", "D"), set_look("section", "4"), set_look("part", "1").
    An empty key goes back to the choice in the app's preferences."""
    if kind not in LOOKS:
        raise KeyError(f"kind {kind!r}: one of {', '.join(LOOKS)}")
    key = str(key or "")
    if key and key not in LOOKS[kind]:
        raise KeyError(f"{kind} look {key!r}: one of {', '.join(LOOKS[kind])}")
    if key:
        _S["looks"][kind] = key
    else:
        _S["looks"].pop(kind, None)
    _S["t"] = _now()                                    # a fade starts again
    redraw()


def look(kind: str) -> str:
    """The look in use: what ``set_look`` said, else the preference read at ``point()``, else the default."""
    key = _S["looks"].get(kind) or _S["pref"].get(kind)
    return key if key in LOOKS[kind] else next(iter(LOOKS[kind]))


def set_colour(c=None) -> None:
    """The one colour of every look: "#479B29" or (r, g, b) 0 … 1. None goes back to the preferences."""
    if c is None:
        _S["colour"] = None
    elif isinstance(c, str):
        h = c.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"colour {c!r}: write it as #rrggbb")
        _S["colour"] = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    else:
        _S["colour"] = tuple(float(v) for v in tuple(c)[:3])
    redraw()


def colour() -> tuple:
    return _S["colour"] or _S["pref_colour"] or GREEN


def keep_clear(names=()) -> None:
    """Panels (class names) that look C never dims: a Lesson panel stays readable while the rest goes dark."""
    _S["clear"] = tuple(names or ())
    if active():
        _unwrap()
        _wrap()
        redraw()


def breath(t: float) -> float:
    """0 … 1 … 0, one slow breath in ``BEAT`` seconds; ``t`` = seconds since the target was pointed at."""
    return 0.5 + 0.5 * math.sin(t * 2.0 * math.pi / BEAT)


def _now() -> float:
    c = _S["clock"]
    return time.time() if c is None else c


def begin_clip() -> None:
    """From now on the looks' clock is the one ``set_clock`` sets (seconds from 0): pictures are made one by one."""
    _S.update(clock=0.0, t=0.0)


def set_clock(t: float) -> None:
    _S["clock"] = float(t)


def end_clip() -> None:
    _S["clock"] = None
    _S["t"] = time.time()


def _pulse() -> float:
    return breath(_now() - _S["t"])


def _age() -> float:
    """Seconds since the target or the look last changed (for what happens once: a fade in)."""
    return _now() - _S["t"]


def _out() -> float:
    """1, but in a clip the last 0.4 s fade a once-only movement out, so the clip's end joins its start."""
    c = _S["clock"]
    return 1.0 if c is None else min(1.0, (LOOP - c % LOOP) / 0.4)


# ---------------------------------------------------------------------------
# pointing
# ---------------------------------------------------------------------------

def active() -> bool:
    return _S["target"] is not None


def point(panel: str = "", button: str = "", text: str = "", prop: str = "", fold: str = "", parts=(),
          open_panels: bool = False) -> None:
    """From now on the side panel shows the target: the button (operator id; with ``text`` only the one with that
    button text) or the setting (``prop``, the property's name) drawn by ``panel`` (a panel's class name) – inside
    the fold ``fold`` (a ``ui.fold`` id) when given, which then opens by itself. ``parts``: names of objects to
    show in the 3D view (an assembly's parts come with it). While the target is in a folded section, that
    section's header is shown instead; ``open_panels`` lets the app open the section itself where it can."""
    _unwrap()
    cls = getattr(bpy.types, panel, None) if panel else None
    chain, c = [], cls
    while c is not None and c.__name__ not in chain:        # the panel and the panels it sits in
        chain.append(c.__name__)
        c = getattr(bpy.types, getattr(c, "bl_parent_id", "") or "-", None)
    _S["target"] = {"panel": panel, "button": button, "text": text, "prop": prop, "fold": fold, "chain": chain}
    _S["parts"] = _part_names(parts)
    _S["part_obs"] = None
    _S["seen"] = {}
    _S["anywhere"] = _S["again"] = False
    _S["t"] = _now()
    _read_prefs()
    _icons()
    _wrap()
    _add_handlers()
    wm = bpy.context.window_manager
    if hasattr(wm, "fresing_fold_open"):
        wm.fresing_fold_open = True
    if open_panels and panel:
        try:
            from . import panels
            panels.open_to(panel)
        except Exception:  # noqa: BLE001 - no panels module, or it cannot: the header shows the way instead
            pass
    if panel:
        _show_tab()
    redraw()


def point_function(fid: str, parts=(), open_panels: bool = False) -> bool:
    """Points at a function of the function list (``core/functions.py``): its panel, fold and button or setting.
    False when it has no place in the side panel (a menu entry): then only ``parts`` are shown."""
    f = functions.FUNCTIONS[fid]
    side = hasattr(bpy.types, f.panel) and f.panel.startswith("FRESING_PT_")
    if side:
        point(panel=f.panel, button=f.button, text=f.text, prop=f.prop, fold=f.fold, parts=parts,
              open_panels=open_panels)
    else:
        point(parts=parts)
    return side


def clear() -> None:
    """Everything back as it was: the panels' own draws, no draw handler, no timer."""
    _clear(in_load=False)


def _clear(in_load: bool) -> None:
    _S["target"] = None
    _S["parts"] = []
    _S["part_obs"] = None
    _S["seen"] = {}
    _unwrap()
    _remove_handlers(in_load)
    _GEO.clear()
    try:
        redraw()
    except Exception:  # noqa: BLE001 - no window (background, closing)
        pass


def found() -> dict:
    """What the side panel's last redraw saw, in the side panel's pixels (y up): ``region`` (x, y, width, height),
    ``button`` (the target's rectangle) or None, ``header`` (the folded section's header) or None, ``bands`` (the
    panels kept clear). Empty until the side panel was drawn. A lesson scrolls by it."""
    return dict(_S["seen"])


def stats(reset: bool = False) -> dict:
    """Milliseconds per redraw the highlight itself took: {"side": (redraws, ms each), "read": (…), "parts": (…)}
    – side = all of its work in the side panel, read = of that, reading the pixels and finding the markers."""
    out = {k: (n, 1000.0 * s / n if n else 0.0) for k, (n, s) in _S["stats"].items()}
    if reset:
        _S["stats"] = {"side": [0, 0.0], "read": [0, 0.0], "parts": [0, 0.0]}
    return out


def fold_open(idname: str) -> bool:
    """``ui.fold`` asks: must this fold be open now? True for the fold the target sits in."""
    t = _S["target"]
    if t is None or not t["fold"] or idname != t["fold"]:
        return False
    _S["fold_next"] = True                              # the fold drawn next is the target's (see _L._folded)
    return True


def mark_header(layout, panel_name: str) -> None:
    """For a title row that does not call the panel's ``draw_header``: call this where the panel's icon goes,
    right after the fold arrow (section look 5 draws its nodding arrow one icon left of the marker). Draws the
    header marker for the target panel and the panels it sits in, nothing else. A panel marked this way is not
    marked a second time through its ``draw_header``. (``panels.py`` calls ``draw_header`` itself, at that very
    place: nothing has to call this today.)"""
    _HOOKED.add(panel_name)
    t = _S["target"]
    if t is not None and panel_name in t["chain"] and _S["icons"] is not None:
        layout.label(text="", icon_value=_S["icons"]["header"].icon_id)


def _read_prefs() -> None:
    p = None
    try:
        from . import prefs
        p = prefs.get()
    except Exception:  # noqa: BLE001 - no preferences (Blender as a module)
        pass
    _S["pref"] = {k: str(getattr(p, "lesson_" + k, "") or "") for k in LOOKS} if p is not None else {}
    c = getattr(p, "lesson_colour", None)
    _S["pref_colour"] = tuple(c[:3]) if c is not None else None


def _show_tab() -> None:
    """The side panel is there and shows the Fresing tab. Not while Blender's column is being closed after a load:
    a 3D view's setting set then crashes Blender 5.2.3 (task 0221; found again by task 0230's lesson start)."""
    try:
        from . import editors
        if editors.busy():
            return
    except Exception:  # noqa: BLE001 - no editors module: nothing is closed
        pass
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            try:
                area.spaces.active.show_region_ui = True
                for r in area.regions:
                    if r.type == "UI":
                        r.active_panel_category = "Fresing"
            except (TypeError, AttributeError):
                pass


def redraw(regions=("UI", "WINDOW")) -> None:
    if "UI" in regions:
        regions = tuple(regions) + ("TOOLS",)            # task 0260: the left panel is a side panel too
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm else ()):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for r in area.regions:
                    if r.type in regions:
                        r.tag_redraw()


# ---------------------------------------------------------------------------
# the stand-in layout: passes everything through, marks the target
# ---------------------------------------------------------------------------

_SUB = ("row", "column", "box", "split", "column_flow", "grid_flow")


class _L:
    """A layout that marks the target and is otherwise the real one. ``_in``: inside the target's fold."""
    __slots__ = ("_l", "_in")

    def __init__(self, layout, inside=False):
        object.__setattr__(self, "_l", layout)
        object.__setattr__(self, "_in", inside)

    def __getattr__(self, name):
        real = getattr(self._l, name)
        if name in _SUB:
            return lambda *a, **k: _L(real(*a, **k), self._in)
        if name == "operator":
            return self._operator
        if name == "operator_menu_enum":
            return self._menu
        if name == "prop":
            return self._prop
        if name == "panel":
            return self._panel
        if name == "panel_prop":
            return self._panel_prop
        return real

    def __setattr__(self, name, value):
        setattr(self._l, name, value)

    def _is_target(self, **what) -> bool:
        t = _S["target"]
        if t is None or _S["marked"]:
            return False
        if "idname" in what:
            hit = bool(t["button"]) and what["idname"] == t["button"] and (not t["text"] or what["text"] == t["text"])
        else:
            hit = bool(t["prop"]) and not t["button"] and what["prop"] == t["prop"]
        if hit and t["fold"] and not self._in and not _S["anywhere"]:
            _S["outside"] = True                        # drawn beside its fold, not in it: marked at the next draw
            return False                                # unless one inside the fold turns up in this one
        return hit

    @staticmethod
    def _marked(k: dict) -> dict:
        """The target keeps its place and size: only its icon becomes the marker (no row added, nothing moves)."""
        k = dict(k)
        k.pop("icon", None)
        k["icon_value"] = _S["icons"]["button"].icon_id
        _S["marked"] = True                             # the first one drawn is the target, no second
        return k

    def _operator(self, idname, *a, **k):
        if self._is_target(idname=idname, text=k.get("text")):
            k = self._marked(k)
        return self._l.operator(idname, *a, **k)

    def _menu(self, idname, prop, *a, **k):
        """A drop-down button of an operator (the animation's + for a step, task 0230): it takes no icon of ours,
        so it gets the marker in front of it, as a setting does."""
        if self._is_target(idname=idname, text=k.get("text")):
            row = self._l.row(align=True)
            row.label(text="", icon_value=_S["icons"]["field"].icon_id)
            _S["marked"] = _S["menu"] = True
            return row.operator_menu_enum(idname, prop, *a, **k)
        return self._l.operator_menu_enum(idname, prop, *a, **k)

    def _prop(self, data, prop, *a, **k):
        if self._is_target(prop=prop):                  # a setting keeps its own look: the marker stands in front
            row = self._l.row(align=True)               # (a number or text field shows no icon of its own)
            row.label(text="", icon_value=_S["icons"]["field"].icon_id)
            _S["marked"] = True
            return row.prop(data, prop, *a, **k)
        return self._l.prop(data, prop, *a, **k)

    def _folded(self, pair, inside):
        header, body = pair
        return _L(header, self._in), (_L(body, inside) if body is not None else None)

    def _panel(self, idname, *a, **k):
        t = _S["target"]
        if t is not None and t["fold"] and idname == t["fold"]:           # a fold drawn without ui.fold: open
            return self._folded(self._l.panel_prop(bpy.context.window_manager, "fresing_fold_open"), True)
        return self._folded(self._l.panel(idname, *a, **k), self._in)

    def _panel_prop(self, *a, **k):
        inside, _S["fold_next"] = self._in or _S["fold_next"], False      # ui.fold just asked fold_open()
        return self._folded(self._l.panel_prop(*a, **k), inside)


class _Self:
    """What a wrapped draw gets as ``self``: the panel, with the stand-in layout."""
    __slots__ = ("_p",)

    def __init__(self, panel):
        object.__setattr__(self, "_p", panel)

    def __getattr__(self, name):
        if name == "layout":
            return _L(self._p.layout)
        f = getattr(type(self._p), name, None)
        if isinstance(f, types.FunctionType):           # the panel's own helper methods get the stand-in too
            return f.__get__(self)
        return getattr(self._p, name)

    @property
    def __class__(self):                                # a draw that asks type(self) or isinstance still works
        return type(self._p)


def _swap(cls, attr: str) -> None:
    """Puts our draw (or draw_header) round whatever the class has now; ``_unwrap`` puts exactly that back."""
    own = cls.__dict__.get(attr)                        # None: the class has none of its own – it gets one
    inner = getattr(cls, attr, None)
    name = cls.__name__

    if attr == "draw":
        def wrapped(self, context):
            t = _S["target"]
            if t is not None and name == t["panel"]:
                _S["marked"] = _S["fold_next"] = _S["outside"] = _S["menu"] = False
                inner(_Self(self), context)
                if _S["outside"] and not _S["marked"]:
                    _S["anywhere"] = _S["again"] = True
            else:
                inner(self, context)
            if name in _S["clear"]:                     # the end of a panel that look C keeps clear
                row = self.layout.row()
                row.scale_y = 0.5
                row.label(text="", icon_value=_S["icons"]["end"].icon_id)
    else:
        def wrapped(self, context):
            t = _S["target"]
            if t is not None and name in t["chain"] and name not in _HOOKED:
                self.layout.label(text="", icon_value=_S["icons"]["header"].icon_id)
            if inner is not None:
                inner(self, context)
            if name in _S["clear"]:
                self.layout.label(text="", icon_value=_S["icons"]["top"].icon_id)

    if hasattr(inner, "_fr_body"):                      # panels.body_of() still finds the panel's own body
        wrapped._fr_body = inner._fr_body
    setattr(cls, attr, wrapped)
    _S["wrapped"].append((cls, attr, own))


def _wrap() -> None:
    """The target panel's draw goes through the stand-in; its header and its parents' headers get the marker."""
    t = _S["target"]
    if t is None or _S["wrapped"]:
        return
    for i, name in enumerate(t["chain"]):
        cls = getattr(bpy.types, name)
        _swap(cls, "draw_header")
        if i == 0 and getattr(cls, "draw", None) is not None:
            _swap(cls, "draw")
    for name in _S["clear"]:
        cls = getattr(bpy.types, name, None)
        if cls is None:
            continue
        done = {(c, a) for c, a, _o in _S["wrapped"]}
        for attr in ("draw_header", "draw"):
            if (cls, attr) not in done and (attr == "draw_header" or getattr(cls, attr, None) is not None):
                _swap(cls, attr)


def _unwrap() -> None:
    for cls, attr, own in reversed(_S["wrapped"]):
        if own is None:
            try:
                delattr(cls, attr)
            except AttributeError:
                pass
        else:
            setattr(cls, attr, own)
    _S["wrapped"] = []


# ---------------------------------------------------------------------------
# marker icons (made once, a few hundred bytes each)
# ---------------------------------------------------------------------------

def _png(path: str, rgb, shape: str) -> None:
    import struct
    import zlib
    w = 32
    px = bytearray(w * w * 4)
    for y in range(w):
        for x in range(w):
            inside = (4 <= x <= 28 and abs(y - 16) <= (28 - x) * 0.6) if shape == "arrow" else \
                ((x - 16) ** 2 + (y - 16) ** 2 <= 100)
            if inside:
                px[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes((*rgb, 255))
    raw = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(w))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, w, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _icons():
    if _S["icons"] is None:
        import tempfile

        import bpy.utils.previews
        pc = bpy.utils.previews.new()
        d = bpy.app.tempdir or tempfile.gettempdir()
        for key, rgb in MARKS.items():
            path = os.path.join(d, f"fr_highlight_{key}.png")
            _png(path, rgb, "arrow" if key in ("button", "field") else "dot")
            pc.load(key, path, "IMAGE")
        _S["icons"] = pc
    return _S["icons"]


def _free_icons() -> None:
    if _S["icons"] is not None:
        import bpy.utils.previews
        try:
            bpy.utils.previews.remove(_S["icons"])
        except Exception:  # noqa: BLE001
            pass
        _S["icons"] = None


# ---------------------------------------------------------------------------
# reading the side panel's pixels (pure NumPy: pixels[y, x] = r, g, b, a as bytes, y up)
# ---------------------------------------------------------------------------

def find_marks(px, rgb, greyed: bool = False) -> list:
    """Every spot of a marker's colour as (x0, y0, x1, y1), the highest on screen first. Spots are told apart by
    the rows between them (two headers, one above the other). ``greyed``: when there is none, look for the marker
    of a greyed-out button – Blender draws its icon at a quarter strength over the button, so the colour is
    gone but its two full channels still stand equally far above the third."""
    import numpy as np
    if px.shape[2] == 4 and px.flags.c_contiguous and sys.byteorder == "little":
        whole = px.view(np.uint32)[:, :, 0]             # a pixel as one number: one pass instead of three
    else:
        whole = px[:, :, 0].astype(np.uint32) | (px[:, :, 1].astype(np.uint32) << 8) | \
            (px[:, :, 2].astype(np.uint32) << 16)
    code = rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)
    w = px.shape[1]                                     # (flatnonzero: np.nonzero of a 2-D picture is 25 x slower)
    ys, xs = np.divmod(np.flatnonzero(((whole & np.uint32(NEAR)) == np.uint32(code & NEAR)).ravel()), w)
    if len(ys) < 6 and greyed:
        k = rgb.index(0)
        hi = [c for c in range(3) if rgb[c] == 255]     # only what has colour: little in a grey panel
        ys, xs = np.divmod(np.flatnonzero((px[:, :, hi[0]] > px[:, :, k]).ravel()), w)
        a, b, low = (px[ys, xs, c].astype(np.int16) for c in (*hi, k))
        keep = (np.abs(a - b) <= 6) & (np.minimum(a, b) - low >= 40)
        ys, xs = ys[keep], xs[keep]
        if len(ys) < 30:
            return []
    if len(ys) < 6:
        return []
    cuts = np.nonzero(np.diff(ys) > 2)[0] + 1           # (the pixels come row by row: ys is in order)
    out = []
    for a, b in zip([0, *cuts], [*cuts, len(ys)]):
        if b - a >= 6:
            out.append((int(xs[a:b].min()), int(ys[a]), int(xs[a:b].max()), int(ys[b - 1])))
    return out[::-1]


def _walk(line, start: int, step: int, own) -> int:
    """From ``start`` along a line of pixels, the last index that still has the colour ``own`` (one pixel that
    differs ends it: the line between two joined buttons is one pixel wide)."""
    import numpy as np
    seg = line[start::step] if step > 0 else line[start::-1]
    off = np.nonzero(np.abs(seg - own).max(axis=1) > 8)[0]
    n = (off[0] - 1) if len(off) else len(seg) - 1
    return start + step * int(n)


def button_box(px, mark) -> tuple:
    """The marked button's own rectangle (x0, y0, x1, y1) in the region's pixels, y up.

    From the button's own colour just left of the marker icon, walk down and up (the button's bottom and top
    edge), then left and right along a row just above the bottom edge (no text there – a descender of 'j' or 'p'
    reaches the row below the icon), then on along the middle row where it still has the button's colour (round
    corners make the bottom rows shorter). Joined buttons are separated by a one-pixel line: the walk stops
    there, so only the target is marked."""
    import numpy as np
    x0, y0, x1, y1 = mark
    h, w = px.shape[:2]
    cx, cy = max(x0 - 3, 0), min(max((y0 + y1) // 2, 0), h - 1)
    col = px[:, cx, :3].astype(np.int16)                # only the lines walked: the whole picture as int16 is slow
    own = col[cy]
    bottom = _walk(col, cy, -1, own)
    top = _walk(col, cy, 1, own)
    low = px[min(bottom + 2, top), :, :3].astype(np.int16)
    mid = px[cy, :, :3].astype(np.int16)
    left = _walk(mid, _walk(low, cx, -1, own), -1, own)
    right = _walk(low, min(x1 + 3, w - 1), 1, own)
    if np.abs(mid[right] - own).max() <= 8:
        right = _walk(mid, right, 1, own)
    if right - left < (x1 - x0) or not (y1 - y0) <= top - bottom <= 4 * (y1 - y0 + 4):
        return max(x0 - 4, 0), max(y0 - 4, 0), min(x1 + 80, w - 1), min(y1 + 4, h - 1)    # no plain button round
    return int(left), int(bottom), int(right), int(top)                                   # the icon: the icon


def field_box(px, mark) -> tuple:
    """The setting that stands right of a field marker: from the marker to the last thing drawn in its row
    (a split setting's name and its field together) before the panel's own ground ends, as high as a button."""
    import numpy as np
    x0, y0, x1, y1 = mark
    h, w = px.shape[:2]
    cy = min(max((y0 + y1) // 2, 0), h - 1)
    pad = round(0.2 * (y1 - y0 + 1)) + 1
    rows = px[max(y0, 0):y1 + 1, :, :3].astype(np.int16)
    ground = px[cy, max(x0 - 3, 0), :3].astype(np.int16)           # what the row stands on: the panel
    off = (np.abs(rows - ground).max(axis=2) > 8)
    plain = np.nonzero(~off.any(axis=0))[0]                         # columns of nothing but ground
    drawn = np.nonzero(off.any(axis=0))[0]
    drawn = drawn[(drawn > x1 + 2) & (drawn < (plain[-1] if len(plain) else w))]
    right = int(drawn[-1]) if len(drawn) else min(x1 + 80, w - 1)
    return min(x1 + 3, w - 1), max(y0 - pad, 0), right, min(y1 + pad, h - 1)


def header_box(px, mark) -> tuple:
    """The header row round a header marker: its bottom and top from the colour beside the marker, its left and
    right end along its lowest row."""
    import numpy as np
    x0, y0, x1, y1 = mark
    h, w = px.shape[:2]
    cx, cy = max(x0 - 2, 0), (y0 + y1) // 2
    col = px[:, cx, :3].astype(np.int16)
    own = col[cy]
    bottom, top = _walk(col, cy, -1, own), _walk(col, cy, 1, own)
    if top - bottom < (y1 - y0):
        bottom, top = max(y0 - 5, 0), min(y1 + 5, h - 1)
    row = px[min(bottom + 1, top), :, :3].astype(np.int16)
    left, right = _walk(row, cx, -1, own), _walk(row, cx, 1, own)
    return int(left), int(bottom), int(right if right > x1 + 20 else w - 8), int(top)


def locate(px, kind: str = "button", clear: bool = False) -> dict:
    """What a picture of the side panel shows. ``kind`` "button" or "field" (a setting; "" = neither is looked
    for): ``mark`` + ``button`` = the marker and the button or setting it belongs to, ``own`` = that button's
    own colour. ``hmark`` + ``header`` = the lowest marked header and its row. ``bands`` [(bottom, top)] = the
    height each kept-clear panel takes (``clear``: look for them). ``cover`` = the other markers to paint over."""
    import numpy as np
    out = {"mark": None, "button": None, "own": None, "hmark": None, "header": None, "bands": [], "cover": []}
    marks = find_marks(px, MARKS[kind], greyed=True) if kind else []
    if marks:
        m = marks[0]
        if kind == "button":                            # the button's own colour: just left of its icon
            box = button_box(px, m)
            own = px[(m[1] + m[3]) // 2, max(m[0] - 3, box[0]), :3]
        else:                                           # a setting's: the colour most of it has
            box = field_box(px, m)
            sub = np.ascontiguousarray(px[box[1]:box[3] + 1, box[0]:box[2] + 1, :3]).reshape(-1, 3)
            vals, n = np.unique(sub, axis=0, return_counts=True)
            own = vals[n.argmax()]
        out.update(mark=m, button=box, own=tuple(int(v) for v in own))
    heads = find_marks(px, MARKS["header"])
    if heads:
        out.update(hmark=heads[-1], header=header_box(px, heads[-1]))     # the lowest: the deepest one drawn
        out["cover"] += heads
    if clear:
        tops, ends = find_marks(px, MARKS["top"]), find_marks(px, MARKS["end"])
        for i, top in enumerate(tops):                  # a panel's end marker lies below its top, above the next top
            floor = tops[i + 1][3] if i + 1 < len(tops) else -1
            end = next((e for e in ends if floor < e[1] < top[1]), None)
            hb = header_box(px, top)
            out["bands"].append(((end[1] - 2) if end else hb[1] - 2, hb[3] + 2))
        out["cover"] += tops + ends
    return out


# ---------------------------------------------------------------------------
# drawing in the side panel (region pixels, y up)
# ---------------------------------------------------------------------------

def _rect(x0, y0, x1, y1, rgba) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]}).draw(sh)


def _tris2d(pts, rgba) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, "TRIS", {"pos": pts}).draw(sh)


def _frame(x0, y0, x1, y1, rgba, width) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader
    vp = gpu.state.viewport_get()
    sh = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    sh.uniform_float("viewportSize", (vp[2], vp[3]))
    sh.uniform_float("lineWidth", width)
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, "LINE_STRIP", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]}).draw(sh)


def _disc(cx, cy, r, rgba, n=24) -> None:
    pts = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        pts += [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a1), cy + r * math.sin(a1))]
    _tris2d(pts, rgba)


def _cover(px, mark) -> None:
    """A marker is only for finding its place: paint it over with the colour just left of it."""
    x0, y0, x1, y1 = mark
    c = px[min(max((y0 + y1) // 2, 0), px.shape[0] - 1), max(x0 - 3, 0), :3] / 255.0
    _rect(x0 - 1, y0 - 1, x1 + 2, y1 + 2, (*c, 1.0))


def _sign(mark, col) -> None:
    """A small calm arrow in the marker's place (the same for both looks: seen without telling colours apart)."""
    x0, y0, x1, y1 = mark
    cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0) * 0.38
    _tris2d([(cx - s * 0.8, cy - s), (cx - s * 0.8, cy + s), (cx + s * 0.9, cy)], (*col, 1.0))


def _dim_except(rw, rh, holes, rgba) -> None:
    """A see-through sheet over the whole region except the rectangles in ``holes`` (x0, y0, x1, y1)."""
    for x0, y0, x1, y1 in dim_rects(rw, rh, holes):
        _rect(x0, y0, x1, y1, rgba)


def dim_rects(rw, rh, holes) -> list:
    """The rectangles that cover a region of rw x rh except ``holes`` (pure: the tests add them up)."""
    out = []
    ys = sorted({0, rh, *[min(max(v, 0), rh) for h in holes for v in (h[1], h[3])]})
    for ya, yb in zip(ys, ys[1:]):
        mid = (ya + yb) / 2
        x = 0
        for hx0, hx1 in sorted((h[0], h[2]) for h in holes if h[1] < mid < h[3]):
            if hx0 > x:
                out.append((x, ya, min(hx0, rw), yb))
            x = max(x, hx1)
        if x < rw:
            out.append((x, ya, rw, yb))
    return out


def _button_c(px, seen, rw, rh, col, s) -> None:
    x0, y0, x1, y1 = seen["button"]
    a = 0.62 * min(1.0, _age() / 0.4) * _out()          # fades in over 0.4 s, then steady
    holes = [(x0 - 3, y0 - 3, x1 + 4, y1 + 4)] + [(0, b, rw, t) for b, t in seen["bands"]]
    _dim_except(rw, rh, holes, (*CHARCOAL, a))
    _frame(x0 - 2, y0 - 2, x1 + 3, y1 + 3, (*col, 0.9), 1.3 * s)


def _button_d(px, seen, rw, rh, col, s) -> None:
    x0, y0, x1, y1 = seen["button"]
    _tint(px, seen, (*col, 0.18 + 0.20 * _pulse()))
    _rect(x0, y0, x0 + round(4 * s), y1 + 1, (*col, 1.0))


def tint_mask(px, box, mark, own):
    """0 … 1 per pixel of a button's rectangle: 1 where the pixel has the button's own colour, 0 on its label
    (and outside its round corners). Look D tints by it, so the label keeps its colour and stays readable."""
    import numpy as np
    x0, y0, x1, y1 = box
    sub = px[y0:y1 + 1, x0:x1 + 1, :3].astype(np.int16)
    a = np.clip(1.0 - (np.abs(sub - np.asarray(own, np.int16)).max(axis=2) - 6) / 30.0, 0.0, 1.0).astype(np.float32)
    if mark[0] >= x0:                                   # the marker icon inside the button is painted over
        a[max(mark[1] - 1 - y0, 0):mark[3] + 2 - y0, mark[0] - 1 - x0:mark[2] + 2 - x0] = 1.0
    return a


def _tint(px, seen, rgba) -> None:
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    box = seen["button"]
    a = tint_mask(px, box, seen["mark"], seen["own"])
    h, w = a.shape
    img = np.empty((h, w, 4), np.float32)
    img[:, :, :3] = rgba[:3]
    img[:, :, 3] = a * rgba[3]
    tex = gpu.types.GPUTexture((w, h), format="RGBA16F", data=gpu.types.Buffer("FLOAT", w * h * 4, img.ravel()))
    x0, y0 = box[0], box[1]
    sh = gpu.shader.from_builtin("IMAGE")
    batch = batch_for_shader(sh, "TRI_FAN", {"pos": [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
                                             "texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]})
    sh.uniform_sampler("image", tex)
    batch.draw(sh)


def _arrow_place(seen):
    """Where the header's fold arrow is: one icon left of the marker (the marker is the first thing a header
    draws after its arrow), and how big an icon is."""
    x0, y0, x1, y1 = seen["hmark"]
    d = max(x1 - x0, y1 - y0) + 1                       # the marker dot: 10/16 of an icon
    l, b, r, t = seen["header"]
    return max((x0 + x1) / 2 - 2.0 * d, l + d), (b + t) / 2, d


def _section_4(px, seen, rw, rh, col, s) -> None:
    l, b, r, t = seen["header"]
    _rect(l, b, r, t + 1, (*col, 0.07 + 0.06 * _pulse()))
    _rect(l, b, l + round(6 * s), t + 1, (*col, 1.0))


def _section_5(px, seen, rw, rh, col, s) -> None:
    l, b, r, t = seen["header"]
    _rect(l, b, r, t + 1, (*col, 0.24 + 0.08 * _pulse()))       # the header in the colour
    _rect(l, b, r, b + round(2 * s), (*col, 1.0))
    cx, cy, d = _arrow_place(seen)
    rad = min(0.72 * d, (t - b) * 0.42)
    _disc(cx, cy, rad, (*col, 1.0))
    ang = -(0.5 - 0.5 * math.cos(2 * math.pi * _age() / BEAT)) * (math.pi / 2)        # nods: right -> down -> right
    k = rad * 0.62
    ca, sa = math.cos(ang), math.sin(ang)
    _tris2d([(cx + x * ca - y * sa, cy + x * sa + y * ca)
             for x, y in ((k * 0.9, 0), (-k * 0.6, k * 0.8), (-k * 0.6, -k * 0.8))], (1, 1, 1, 1))


_BUTTON = {"C": _button_c, "D": _button_d}
_SECTION = {"5": _section_5, "4": _section_4}


def _target_region() -> str:
    """The region the target's panel is drawn in: "TOOLS" for a panel of the left panel (task 0260), else "UI"."""
    t = _S["target"] or {}
    chain = t.get("chain") or [t.get("panel", "")]
    try:
        from . import panels
        return "TOOLS" if chain and chain[-1] in panels.LEFT else "UI"
    except Exception:  # noqa: BLE001
        return "UI"


def _draw_side() -> None:
    """Side panel (region UI), after Blender drew it: find the markers in its pixels, draw the look."""
    if _S["target"] is None or not _S["target"]["panel"]:
        return
    region = bpy.context.region
    if region is None or region.type != _target_region():     # task 0260: the left panel draws here too
        return
    t0 = time.perf_counter()
    try:
        import gpu
        import numpy as np
        region = bpy.context.region
        fb = gpu.state.active_framebuffer_get()
        vp = gpu.state.viewport_get()
        buf = fb.read_color(vp[0], vp[1], vp[2], vp[3], 4, 0, "UBYTE")
        buf.dimensions = vp[2] * vp[3] * 4
        px = np.frombuffer(buf, dtype=np.uint8).reshape(vp[3], vp[2], 4)
        t = _S["target"]
        kind = "field" if t["prop"] or _S.get("menu") else "button" if t["button"] else ""
        seen = locate(px, kind, clear=bool(_S["clear"]))
        seen["region"] = (region.x, region.y, region.width, region.height)
        st = _S["stats"]["read"]
        st[0] += 1
        st[1] += time.perf_counter() - t0
        _S["seen"] = seen
        col = colour()
        s = bpy.context.preferences.system.ui_scale or 1.0
        gpu.state.blend_set("ALPHA")
        for m in seen["cover"]:
            _cover(px, m)
        if seen["button"] is not None:
            _cover(px, seen["mark"])
            _BUTTON[look("button")](px, seen, region.width, region.height, col, s)
            _sign(seen["mark"], col)
        elif seen["header"] is not None:                # the section is folded: its header shows the way
            _SECTION[look("section")](px, seen, region.width, region.height, col, s)
        gpu.state.blend_set("NONE")
        if _S.get("probe"):                             # tests: the same pixels after the look was drawn
            buf = fb.read_color(vp[0], vp[1], vp[2], vp[3], 4, 0, "UBYTE")
            buf.dimensions = vp[2] * vp[3] * 4
            _S["shot"] = (px.copy(), np.frombuffer(buf, dtype=np.uint8).reshape(vp[3], vp[2], 4).copy())
    except Exception as e:  # noqa: BLE001 - drawing must never break the panel
        import traceback
        _S["note"] = f"side panel: {e} {traceback.format_exc(limit=3)}"
    st = _S["stats"]["side"]
    st[0] += 1
    st[1] += time.perf_counter() - t0


# ---------------------------------------------------------------------------
# drawing the parts in the 3D view
# ---------------------------------------------------------------------------

def _part_names(parts) -> list:
    """The names of the mesh objects to show: each named object and everything that hangs on it."""
    out = []
    for p in parts or ():
        ob = bpy.data.objects.get(p) if isinstance(p, str) else p
        if ob is not None:
            out.append(ob)
            out.extend(ob.children_recursive)
    return list(dict.fromkeys(o.name for o in out if o.type == "MESH"))


def _part_objects() -> list:
    """The parts to draw now: those of the names that are shown and have faces. The objects are looked up by name
    once, and again after undo or when one is gone (looked up at every redraw, the 264 parts of a machine on the
    demo vessel cost 34 ms: Blender walks its list of objects for each name)."""
    for again in (False, True):
        obs = _S["part_obs"]
        if obs is None or again:
            get = bpy.data.objects.get
            obs = _S["part_obs"] = [o for o in map(get, _S["parts"]) if o is not None and o.type == "MESH"]
        try:
            return [o for o in obs if o.visible_get() and len(o.data.polygons)]
        except ReferenceError:                          # an object was deleted while it was pointed at
            continue
    return []


_LIT_VERT = """
void main()
{
  shade = 0.30 + 0.45 * abs(dot(nor, light)) + 0.25 * abs(dot(nor, view));
  gl_Position = mvp * vec4(pos, 1.0);
}
"""
_LIT_FRAG = """
void main()
{
  /* The 3D view's picture is kept sRGB-encoded and Blender's own shaders turn their colours linear for it
     (measured in 5.2.3: the same colour through UNIFORM_COLOR came out darker than through a plain shader). */
  vec3 c = clamp(colour * shade, 0.0, 1.0);
  frag = vec4(mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)), 1.0);
}
"""


def _lit():
    """The shader of part look 3: a part in its own colour with simple light (flat faces; light and view come in
    the part's own coordinates, so a mesh is sent to the graphics card once). None when it cannot be made."""
    if _S["lit"] is None:
        import gpu
        try:
            info = gpu.types.GPUShaderCreateInfo()
            info.push_constant("MAT4", "mvp")
            info.push_constant("VEC3", "light")
            info.push_constant("VEC3", "view")
            info.push_constant("VEC3", "colour")
            info.vertex_in(0, "VEC3", "pos")
            info.vertex_in(1, "VEC3", "nor")
            iface = gpu.types.GPUStageInterfaceInfo("fr_highlight_iface")
            iface.flat("FLOAT", "shade")
            info.vertex_out(iface)
            info.fragment_out(0, "VEC4", "frag")
            info.vertex_source(_LIT_VERT)
            info.fragment_source(_LIT_FRAG)
            _S["lit"] = gpu.shader.create_from_info(info)
        except Exception as e:  # noqa: BLE001 - then the part is drawn in its plain colour
            _S["lit"] = False
            _S["note"] = f"part shader: {e}"
    return _S["lit"] or None


def _geo(ob, lit: bool):
    """Once per mesh: its triangles as a batch on the graphics card ("fill": corners; "lit": with normals).
    False for a mesh that cannot be drawn (one such part must not take the others with it)."""
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    me = ob.data
    key = (me.name, len(me.polygons), len(me.vertices), lit)
    hit = _GEO.get(key)
    if hit is None:
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        pos = co.reshape(-1, 3)[tri]
        try:
            if lit:
                c = pos.reshape(-1, 3, 3)
                n = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
                n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
                hit = batch_for_shader(_lit(), "TRIS", {"pos": pos, "nor": np.repeat(n, 3, axis=0).astype(np.float32)})
            else:
                hit = batch_for_shader(gpu.shader.from_builtin("UNIFORM_COLOR"), "TRIS", {"pos": pos})
        except Exception as e:  # noqa: BLE001
            hit = False
            _S["note"] = f"part {ob.name!r} ({len(tri) // 3} triangles) cannot be drawn: {e}"
        _GEO[key] = hit
    return hit


def _part_colour(ob) -> tuple:
    """The part's own colour as the screen shows it (a material keeps its colour linear)."""
    m = ob.active_material
    c = tuple(m.diffuse_color[:3]) if m is not None else (0.45, 0.45, 0.45)
    return tuple(12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in (min(max(v, 0.0), 1.0) for v in c))


def _fill(obs, rgba) -> None:
    import gpu
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    for ob in obs:
        batch = _geo(ob, False)
        if not batch:
            continue
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(ob.matrix_world)
        sh.uniform_float("color", rgba)
        batch.draw(sh)
        gpu.matrix.pop()


def _part_1(obs, col) -> None:
    import gpu
    gpu.state.depth_test_set("NONE")
    _fill(obs, (*col, 0.14 + 0.24 * _pulse()))


def _part_3(obs, col) -> None:
    """Everything greyed by a see-through sheet over the whole view, then the parts drawn again on top in their
    own colour with simple light (their depth starts afresh: the sheet hides the rest, a part hides only parts)."""
    import gpu
    from mathutils import Matrix, Vector
    a = 0.68 * min(1.0, _age() / 0.4) * _out()
    gpu.state.depth_test_set("NONE")
    gpu.matrix.push()
    gpu.matrix.push_projection()
    gpu.matrix.load_identity()
    gpu.matrix.load_projection_matrix(Matrix.Identity(4))
    _rect(-1, -1, 1, 1, (0.23, 0.24, 0.25, a))
    gpu.matrix.pop_projection()
    gpu.matrix.pop()
    if a < 0.05:
        return
    gpu.state.active_framebuffer_get().clear(depth=1.0)
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(True)
    gpu.state.blend_set("NONE")
    sh = _lit()
    if sh is None:
        for ob in obs:
            _fill([ob], (*_part_colour(ob), 1.0))
    else:
        vp = gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix()
        view = bpy.context.region_data.view_rotation @ Vector((0.0, 0.0, 1.0))
        light = Vector((0.35, -0.55, 0.76))
        sh.bind()
        for ob in obs:
            batch = _geo(ob, True)
            if not batch:
                continue
            mw = ob.matrix_world
            back = mw.to_3x3().normalized().transposed()        # world -> the part's own directions
            sh.uniform_float("mvp", vp @ mw)
            sh.uniform_float("light", back @ light)
            sh.uniform_float("view", back @ view)
            sh.uniform_float("colour", _part_colour(ob))
            batch.draw(sh)
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("ALPHA")


_PART = {"3": _part_3, "1": _part_1}


def _draw_parts() -> None:
    if _S["target"] is None or not _S["parts"]:
        return
    t0 = time.perf_counter()
    try:
        import gpu
        obs = _part_objects()
        if obs:
            gpu.state.blend_set("ALPHA")
            _PART[look("part")](obs, colour())
            gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 - drawing must never break the view
        import traceback
        _S["note"] = f"parts: {e} {traceback.format_exc(limit=3)}"
    st = _S["stats"]["parts"]
    st[0] += 1
    st[1] += time.perf_counter() - t0


# ---------------------------------------------------------------------------
# handlers and the timer: there only while something is pointed at
# ---------------------------------------------------------------------------

def moving() -> tuple:
    """The regions that must be drawn again and again right now: "UI" while the side panel's look moves (a fade
    in, look D's breath, a header's breath), "WINDOW" while the part look does (its fade in, look 1's breath)."""
    if _S["target"] is None:
        return ()
    fresh = _age() < 0.6 or _S["clock"] is not None
    seen = _S["seen"]
    out = []
    again, _S["again"] = _S["again"], False
    if fresh or again or (seen.get("button") is not None and look("button") == "D") or \
            (seen.get("button") is None and seen.get("header") is not None):
        out.append("UI")
    if _S["parts"] and (fresh or look("part") == "1"):
        out.append("WINDOW")
    return tuple(out)


def _tick():
    if _S["target"] is None:
        _S["timer"] = False
        return None
    try:
        redraw(moving())
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"tick: {e}"
    return TICK


@persistent
def _before_load(_dummy=None):
    """Another project opens: nothing is pointed at any more. (This handler takes itself off a moment later:
    a handler must not leave Blender's list while Blender walks it.)"""
    _clear(in_load=True)
    bpy.app.timers.register(_drop_load_handler, first_interval=0.0, persistent=True)


def _drop_load_handler():
    if _S["target"] is None and _before_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_before_load)
    return None


@persistent
def _after_undo(_dummy=None):
    """Undo may have changed meshes and replaces the objects: both are read again."""
    _GEO.clear()
    _S["part_obs"] = None
    redraw()


def _app_handlers() -> tuple:
    h = bpy.app.handlers
    return (h.load_pre, _before_load), (h.undo_post, _after_undo), (h.redo_post, _after_undo)


def _add_handlers() -> None:
    if not _S["handles"]:
        sv = bpy.types.SpaceView3D
        _S["handles"] = [(sv.draw_handler_add(_draw_side, (), "UI", "POST_PIXEL"), "UI"),
                         (sv.draw_handler_add(_draw_side, (), "TOOLS", "POST_PIXEL"), "TOOLS"),     # task 0260
                         (sv.draw_handler_add(_draw_parts, (), "WINDOW", "POST_VIEW"), "WINDOW")]
    for lst, fn in _app_handlers():
        if fn not in lst:
            lst.append(fn)
    if not _S["timer"]:
        bpy.app.timers.register(_tick, first_interval=TICK)
        _S["timer"] = True


def _remove_handlers(in_load: bool = False) -> None:
    for h, region in _S["handles"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, region)
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []
    for lst, fn in _app_handlers():
        if fn in lst and not (in_load and fn is _before_load):
            lst.remove(fn)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    _S["timer"] = False


def handlers_left() -> list:
    """What of this module is still hooked into Blender (empty when nothing is pointed at): the tests' check."""
    out = [f"draw handler {r}" for _h, r in _S["handles"]]
    out += [f"app handler {fn.__name__}" for lst, fn in _app_handlers() if fn in lst]
    out += ["timer"] if bpy.app.timers.is_registered(_tick) else []
    out += [f"wrapped {c.__name__}.{a}" for c, a, _o in _S["wrapped"]]
    return out


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

def register():
    from . import ui
    if not hasattr(bpy.types.WindowManager, "fresing_fold_open"):
        bpy.types.WindowManager.fresing_fold_open = bpy.props.BoolProperty(default=True)
        _S["own_prop"] = True
    ui.HOOKS["fold"] = fold_open                        # (the header marker goes through draw_header, not through
                                                        # HOOKS["header"]: it must stand right after the fold arrow)


def unregister():
    from . import ui
    _clear(in_load=False)
    if _before_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_before_load)
    if ui.HOOKS.get("fold") is fold_open:
        ui.HOOKS["fold"] = None
    if _S.pop("own_prop", False):
        del bpy.types.WindowManager.fresing_fold_open
    _free_icons()
    _HOOKED.clear()
    _S.update(looks={}, pref={}, colour=None, pref_colour=None, clear=(), clock=None, lit=None, note="")
