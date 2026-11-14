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

_S: dict = {"lesson": None, "mode": "SHOW", "step": 0, "phase": "", "t": 0.0, "more": False, "handles": [],
            "wrapped": [], "icons": None, "found": None, "found_header": None, "timer": False, "note": "",
            "scrolls": 0, "stats": {"reads": 0, "read_s": 0.0, "draws": 0, "draw_s": 0.0}}


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
        for key, colour, shape in (("button", MARK_BUTTON, "arrow"), ("header", MARK_HEADER, "dot")):
            path = os.path.join(d, f"fr_lesson_{key}.png")
            _png(path, colour, shape)
            pc.load(key, path, "IMAGE")
        _S["icons"] = pc
    return _S["icons"]


# ---------------------------------------------------------------------------
# drawing: the glow in the side panel, the part and its card in the view
# ---------------------------------------------------------------------------

def _pulse() -> float:
    return 0.5 + 0.5 * math.sin((time.time() - _S["t"]) * 2.0 * math.pi * 0.9)


def _find(pixels, colour):
    import numpy as np
    m = (np.abs(pixels[:, :, 0].astype(np.int16) - colour[0]) < 24) & \
        (np.abs(pixels[:, :, 1].astype(np.int16) - colour[1]) < 24) & \
        (np.abs(pixels[:, :, 2].astype(np.int16) - colour[2]) < 24)
    ys, xs = np.nonzero(m)
    if len(xs) < 6:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _button_right(px, y, x):
    """The button's right edge: along a row of the button just below the marker icon (no text there), walk right from
    the icon until the colour changes – the panel's background or the thin line between two aligned buttons."""
    import numpy as np
    row = px[min(max(y, 0), px.shape[0] - 1), :, :3].astype(np.int16)
    own = row[min(x + 3, row.shape[0] - 1)]
    for i in range(x + 4, row.shape[0] - 2):
        if np.abs(row[i] - own).max() > 10 and np.abs(row[i + 1] - own).max() > 10:
            return i
    return row.shape[0] - 10


def _frame(x0, y0, x1, y1, colour, alpha, width):
    import gpu
    from gpu_extras.batch import batch_for_shader
    vp = gpu.state.viewport_get()
    sh = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    sh.uniform_float("viewportSize", (vp[2], vp[3]))
    sh.uniform_float("lineWidth", width)
    sh.uniform_float("color", (*colour, alpha))
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    batch_for_shader(sh, "LINE_STRIP", {"pos": pts}).draw(sh)


def _draw_sidebar() -> None:
    """Side panel (region UI), after Blender drew it: find the markers in its pixels, glow round them."""
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
        _S["stats"]["reads"] += 1
        _S["stats"]["read_s"] += time.perf_counter() - t
        _S["found"], _S["found_header"] = found, header
        _S["region"] = (region.x, region.y, region.width, region.height)
        _S["drawn"] = True
        p = _pulse()
        col = OK if _S["phase"] == "done" else MAGENTA
        gpu.state.blend_set("ALPHA")
        if found is not None:
            x0, y0, x1, y1 = found
            right = _button_right(px, y0 - 2, x1)             # y grows upwards: y0 - 2 is just below the icon
            _S["found_right"] = right
            pad = 5
            for w, a in ((9.0, 0.10 + 0.15 * p), (5.0, 0.25 + 0.25 * p), (2.0, 0.65 + 0.35 * p)):
                _frame(x0 - pad - 4, y0 - pad, right + 2, y1 + pad, col, a, w)
        elif header is not None:                     # the section is closed: its header glows
            x0, y0, x1, y1 = header
            _frame(6, y0 - 6, region.width - 10, y1 + 6, col, 0.35 + 0.65 * p, 2.0 + 3.0 * p)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001 - drawing must never break the panel
        _S["note"] = f"sidebar draw: {e}"


_BATCH: dict = {}


def _part_objects(scene, names):
    from . import build
    out = []
    for o in scene.objects:
        if o.get(build.PROP_NAME) in names:
            out.append(o)
            out.extend(c for c in o.children_recursive if c.type == "MESH")
    return [o for o in dict.fromkeys(out) if o.type == "MESH" and o.visible_get()]


def _tris(ob):
    import numpy as np
    me = ob.data
    key = (me.name, len(me.polygons))
    hit = _BATCH.get(key)
    if hit is None:
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        hit = co.reshape(-1, 3)[tri]
        _BATCH[key] = hit
    return hit


def _draw_parts() -> None:
    st = step()
    if st is None or not st.parts:
        return
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        sh = gpu.shader.from_builtin("UNIFORM_COLOR")
        p = _pulse()
        col = OK if _S["phase"] == "done" else MAGENTA
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")
        for ob in _part_objects(bpy.context.scene, st.parts):
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(ob.matrix_world)
            sh.uniform_float("color", (*col, 0.12 + 0.22 * p))
            batch_for_shader(sh, "TRIS", {"pos": _tris(ob)}).draw(sh)
            gpu.matrix.pop()
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001
        _S["note"] = f"part draw: {e}"


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
        col = OK if _S["phase"] == "done" else MAGENTA
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
        layout.operator("fresing.lesson_stop", icon="X")


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
