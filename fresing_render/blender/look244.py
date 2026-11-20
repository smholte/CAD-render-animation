"""PROTOTYPE of task 0244 (findings only, never merged): steps and their functions look different in the side panel.

Only steps 4 Motion and 5 Scene & Render. Everything is switched by ``S`` (the shot script and the timing script set
it; ``FR244_LOOK`` etc. for a start by hand):

* ``look``     "old" (today) · "new" (the owner's pick, with the green-line overlay) · "fallback" (no overlay)
* ``how``      "sub" (functions stay Blender sub-panels, the app draws them) · "fold" (drawn inside the step's body
               with the app's own fold rows) · "lpanel" (inside the body with Blender's ``layout.panel()``)
* ``arrow``    "light" (#8cc46f) or "brand" (#479B29)
* ``one_open`` one function open at a time in a step
* ``overlay``  "full" (read the whole side panel's pixels) or "strip" (only a narrow strip on its left)

The theme part (``theme(True)``) changes Blender's own colour settings of the running app; the full change would put
them into the app's own Blender config only.
"""

from __future__ import annotations

import os
import struct
import tempfile
import time
import zlib

import bpy

S = {
    "look": os.environ.get("FR244_LOOK", "old"),
    "how": os.environ.get("FR244_HOW", "sub"),
    "arrow": os.environ.get("FR244_ARROW", "light"),
    "one_open": bool(os.environ.get("FR244_ONE_OPEN")),
    "overlay": os.environ.get("FR244_OVERLAY", "full"),
}
STEPS = ("FRESING_PT_motion", "FRESING_PT_scene")
GREEN = (71, 155, 41)                 # #479B29 Fresing Green
LIGHT = (140, 196, 111)               # #8cc46f
MARK_STEP = (255, 0, 128)             # the markers: a bar on the arrow icon's left edge, one colour each, painted over
MARK_FN = (0, 128, 255)               # (other colours than highlight.MARKS: a lesson can point at the same time)
MARK_FOLD = (128, 255, 0)
FRAME = (0x57, 0x57, 0x57)            # the open function's frame (buttons are #545454: not the same, the walk tells)
LIGHTER = 13 / 255                    # the step bar: added over today's ground #303030 -> #3d3d3d
DARKER = 10 / 255                     # a closed function row: taken off -> #262626
FOLDS: set = set()                    # the app's own folds inside a function (``ui.fold``) that are open
CURRENT = [""]                        # the step or function being drawn (folds inside it get the new look)
STATS = {"n": 0, "t": 0.0, "found": 0}
_ICONS = {"pc": None}
_HANDLE = {"h": None}
_THEME_WAS: dict = {}


def new() -> bool:
    return S["look"] in ("new", "fallback")


def in_steps(name: str) -> bool:
    from . import panels
    return name in STEPS or panels.PARENT.get(name) in STEPS


def function_of_step(name: str) -> bool:
    from . import panels
    return panels.PARENT.get(name) in STEPS


# ---------------------------------------------------------------------------
# icons: green arrows, the markers (drawn as PNGs, 32 px – Blender scales them to the UI)
# ---------------------------------------------------------------------------

def _png(path, w, fn):
    px = bytearray(w * w * 4)
    for y in range(w):
        for x in range(w):
            c = fn(x + 0.5, y + 0.5)
            if c is not None:
                px[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes(c)
    raw = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(w))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, w, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _chevron(rgb, down: bool, w: int = 32):
    """A › (or ⌄) of two strokes, 3.2 px thick at 32 px, edges smoothed (4 x 4 samples per pixel)."""
    import math

    def seg_d(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)
    s = w / 32.0
    if down:                                   # PNG rows go down: y grows downwards here
        a, b, c = (7 * s, 11 * s), (16 * s, 20.5 * s), (25 * s, 11 * s)
    else:
        a, b, c = (12 * s, 7 * s), (21.5 * s, 16 * s), (12 * s, 25 * s)
    half = 2.1 * s

    def fn(x, y):
        hit = 0
        for i in range(4):
            for j in range(4):
                qx, qy = x - 0.5 + (i + 0.5) / 4, y - 0.5 + (j + 0.5) / 4
                if min(seg_d(qx, qy, *a, *b), seg_d(qx, qy, *b, *c)) <= half:
                    hit += 1
        return None if not hit else (*rgb, int(255 * hit / 16))
    return fn


def _marked(rgb, chevron):
    """An arrow with the marker: a bar on the icon's left edge, 6 px of 32, full height, one exact colour."""
    def fn(x, y):
        return (*rgb, 255) if x < 6 else chevron(x, y)
    return fn


def icons():
    if _ICONS["pc"] is None:
        from bpy.utils import previews
        pc = previews.new()
        dd = d = tempfile.mkdtemp(prefix="fr244_")
        for key, fn in (("r_light", _chevron(LIGHT, False)), ("d_light", _chevron(LIGHT, True)),
                        ("r_brand", _chevron(GREEN, False)), ("d_brand", _chevron(GREEN, True)),
                        ("r_white", _chevron((230, 230, 230), False)), ("d_white", _chevron((230, 230, 230), True)),
                        ):
            path = os.path.join(d, key + ".png")
            _png(path, 32, fn)
            pc.load(key, path, "IMAGE")
        for shade, rgb in (("light", LIGHT), ("brand", GREEN)):
            for kind, mark in (("step", MARK_STEP), ("fn", MARK_FN), ("fold", MARK_FOLD)):
                for d in ("r", "d"):
                    key = f"{d}_{shade}_{kind}"
                    path = os.path.join(dd, key + ".png")
                    _png(path, 32, _marked(mark, _chevron(rgb, d == "d")))
                    pc.load(key, path, "IMAGE")
        _ICONS["pc"] = pc
    return _ICONS["pc"]


def icon(key: str) -> int:
    return icons()[key].icon_id


def arrow(opened: bool, kind: str = "") -> int:
    """The green arrow; with ``kind`` (step / fn / fold) and the overlay on, the one that carries its marker."""
    key = ("d_" if opened else "r_") + S["arrow"]
    if kind and S["look"] == "new" and S["overlay"] != "off":
        key += "_" + kind
    return icon(key)


# ---------------------------------------------------------------------------
# the theme: greys from Blender's colour settings
# ---------------------------------------------------------------------------

THEME = {   # field -> value. The app's panels draw no backdrop (HIDE_HEADER): panel_back / panel_sub_back show
    # nothing in the Fresing tab (measured), only in Blender's own panels. The one field that matters: every box's
    # outline, so an open function's frame shows (#3d3d3d today, hardly seen on #303030).
    ("user_interface", "wcol_box", "outline"): (FRAME[0] / 255, FRAME[1] / 255, FRAME[2] / 255, 1.0),
}
PROBE = {   # tests what the panel colours do (pictures "probe"): loud colours
    ("user_interface", "panel_back"): (0.8, 0.1, 0.1, 1.0),
    ("user_interface", "panel_sub_back"): (0.1, 0.1, 0.8, 0.5),
    ("user_interface", "panel_header"): (0.1, 0.7, 0.1, 1.0),
}


def _field(path):
    o = bpy.context.preferences.themes[0]
    for p in path[:-1]:
        o = getattr(o, p)
    return o, path[-1]


def theme(on: bool) -> None:
    for path, val in _THEME_WAS.items():               # back to Blender's own first
        o, f = _field(path)
        setattr(o, f, val)
    _THEME_WAS.clear()
    if not on:
        return
    for path, val in (THEME | (PROBE if S.get("probe") else {})).items():
        o, f = _field(path)
        _THEME_WAS[path] = tuple(getattr(o, f))
        setattr(o, f, val)


# ---------------------------------------------------------------------------
# drawing: the step's title row, a function's row, an open function's frame
# ---------------------------------------------------------------------------

def draw_title(self, context, cls, layout) -> bool:
    """The new title row of a step or of a function in it; True when its body is to be drawn."""
    from . import panels
    name = cls.__name__
    step = name in STEPS
    opened = panels.is_open(name)
    fixed = step and name == panels.tab_section()
    row = layout.row(align=True)
    if step:
        row.scale_y = 1.15
    left = row.row(align=True)
    left.alignment = "LEFT"
    if not step:
        left.separator(factor=1.0)             # the indent of a function row
    if fixed:
        left.label(text="", icon="BLANK1")
    else:                                      # the arrow carries the marker the overlay finds (and paints over)
        op = left.operator("fresing.panel_toggle", text="", emboss=False,
                           icon_value=arrow(opened, "step" if step else "fn"))
        op.name = name
    head = getattr(cls, "draw_header", None)
    if head is not None:
        head(panels._Stand(self, left), context)
    title = panels.TITLE.get(name, getattr(cls, "bl_label", name))
    if fixed:
        left.label(text=title)
    else:
        op = left.operator("fresing.panel_toggle", text=title, emboss=False)
        op.name = name
    right = row.row(align=True)
    right.alignment = "RIGHT"
    preset = getattr(cls, "draw_header_preset", None)
    if preset is not None:
        preset(panels._Stand(self, right), context)
    return opened


def draw_panel(self, context, cls, body):
    """A step or one of its functions, new look. A function that is open sits in a frame (a box)."""
    from . import panels
    name = cls.__name__
    layout = self.layout
    if name in STEPS:
        bar = layout.box() if S["look"] == "fallback" else layout
        if draw_title(self, context, cls, bar):
            body(self, context)
            if S["how"] in ("fold", "lpanel"):
                _inside(self, context, cls)
        return
    opened = panels.is_open(name)
    outer = layout
    if opened:
        outer = layout.box()
    draw_title(self, context, cls, outer)
    if opened:
        col = outer.column()
        body(panels._Stand(self, col), context)


# --- functions drawn inside the step's body (how = fold / lpanel) ---------------------------------------------------

def hidden_sub(name: str) -> bool:
    """With how = fold / lpanel the functions of steps 4 and 5 are no sub-panels any more: Blender's are hidden."""
    return new() and S["how"] in ("fold", "lpanel") and function_of_step(name)


def _inside(self, context, cls):
    from . import panels
    step = cls.__name__
    kids = [c for c in _classes() if panels.PARENT.get(c.__name__) == step]
    self.layout.separator()
    for k in kids:
        name = k.__name__
        own = getattr(k, "_fr_own_poll", None)
        if own is not None and not own(context):
            continue
        if S["how"] == "lpanel":
            header, body = self.layout.panel("fr244_" + name, default_closed=True)
            head = getattr(k, "draw_header", None)
            hrow = header.row(align=True)
            if head is not None:
                head(panels._Stand(self, hrow), context)
            hrow.label(text=panels.TITLE.get(name, name))
            preset = getattr(k, "draw_header_preset", None)
            if preset is not None:
                r = header.row(align=True)
                r.alignment = "RIGHT"
                preset(panels._Stand(self, r), context)
            if body is not None:
                panels.body_of(k)(panels._Stand(self, body.column()), context)
        else:
            opened = panels.is_open(name)
            outer = self.layout.box() if opened else self.layout.column()
            draw_title(panels._Stand(self, outer), context, k, outer)
            if opened:
                panels.body_of(k)(panels._Stand(self, outer.column()), context)


def _classes():
    import sys
    pkg = sys.modules[__name__.rsplit(".", 2)[0]]
    return [c for c in pkg._all_classes() if isinstance(c, type) and issubclass(c, bpy.types.Panel)]


# --- a fold inside a function (``ui.fold``): green arrow, no frame, body indented ----------------------------------

def fold(layout, idname: str, title: str, icon_name: str = "NONE", closed: bool = True):
    key = idname
    if key not in FOLDS and not closed and key + "!" not in FOLDS:
        FOLDS.add(key)
    opened = key in FOLDS
    row = layout.row(align=True)
    row.alignment = "LEFT"
    op = row.operator("fresing.fold244", text="", emboss=False, icon_value=arrow(opened, "fold" if opened else ""))
    op.key = key
    op = row.operator("fresing.fold244", text=title, emboss=False, icon=icon_name)
    op.key = key
    if not opened:
        return None
    split = layout.split(factor=0.06)
    split.label(text="")
    return split.column()


class FRESING_OT_fold244(bpy.types.Operator):
    """Opens or folds this part (prototype 0244)"""

    bl_idname = "fresing.fold244"
    bl_label = "Open or fold"
    bl_options = {"INTERNAL"}

    key: bpy.props.StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        if self.key in FOLDS:
            FOLDS.discard(self.key)
            FOLDS.add(self.key + "!")
        else:
            FOLDS.add(self.key)
            FOLDS.discard(self.key + "!")
        from . import panels
        panels.redraw()
        return {"FINISHED"}


def one_open(name: str) -> None:
    """One function open at a time: opening one in step 4 or 5 folds the others of that step."""
    from . import panels
    if not (new() and S["one_open"] and function_of_step(name)):
        return
    parent = panels.PARENT[name]
    for other, p in panels.PARENT.items():
        if p == parent and other != name:
            panels.OPEN.discard(other)


# ---------------------------------------------------------------------------
# the overlay: the step's green edge and the open function's green line, drawn over the side panel
# ---------------------------------------------------------------------------

def find(px, rgb, tol: int = 4):
    """Spots of one colour (each channel within ``tol``) as (x0, y0, x1, y1), highest on screen first."""
    import numpy as np
    m = (np.abs(px[:, :, 0].astype(np.int16) - rgb[0]) <= tol) & (np.abs(px[:, :, 1].astype(np.int16) - rgb[1]) <= tol) \
        & (np.abs(px[:, :, 2].astype(np.int16) - rgb[2]) <= tol)
    w = px.shape[1]
    ys, xs = np.divmod(np.flatnonzero(m.ravel()), w)
    if len(ys) < 3:
        return []
    cuts = np.nonzero(np.diff(ys) > 2)[0] + 1
    out = []
    for a, b in zip([0, *cuts], [*cuts, len(ys)]):
        if b - a >= 3:
            out.append((int(xs[a:b].min()), int(ys[a]), int(xs[a:b].max()), int(ys[b - 1])))
    return out[::-1]


def _rect(x0, y0, x1, y1, rgba):
    import gpu
    from gpu_extras.batch import batch_for_shader
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    sh.uniform_float("color", rgba)
    batch_for_shader(sh, "TRIS", {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]}).draw(sh)


def _frame_of(px, x, y):
    """The frame (box outline) round a function's title row: walk left from the marker to the frame's left edge,
    then down that edge while it has the frame's colour. Returns (edge x, bottom y) or None (no frame: closed)."""
    import numpy as np
    row = px[y, :max(x, 1), :3].astype(np.int16)
    hit = np.nonzero(np.abs(row - np.array(FRAME)).max(axis=1) <= 1)[0]
    if not len(hit):
        return None
    ex = int(hit[-1])
    col = px[:y + 1, ex, :3].astype(np.int16)
    on = np.abs(col - np.array(FRAME)).max(axis=1) <= 1
    off = np.nonzero(~on[::-1])[0]
    n = int(off[0]) if len(off) else y + 1
    return ex, y - n + 1


def _draw():
    if not (S["look"] == "new" and S["overlay"] != "off"):
        return
    t0 = time.perf_counter()
    try:
        import gpu
        import numpy as np
        region = bpy.context.region
        fb = gpu.state.active_framebuffer_get()
        vp = gpu.state.viewport_get()
        s = bpy.context.preferences.system.ui_scale or 1.0
        strip = vp[2] if S["overlay"] == "full" else min(vp[2], int(80 * s))
        buf = fb.read_color(vp[0], vp[1], strip, vp[3], 4, 0, "UBYTE")
        buf.dimensions = strip * vp[3] * 4
        px = np.frombuffer(buf, dtype=np.uint8).reshape(vp[3], strip, 4)
        rw = region.width
        right = rw - round(30 * s)                       # the panels' right edge (the tab column beside it)
        g = tuple(c / 255 for c in GREEN) + (1.0,)
        lw = max(2, round(3 * s))
        half = round(10 * s)                             # half a row
        steps, fns, folds = find(px, MARK_STEP), find(px, MARK_FN), find(px, MARK_FOLD)
        STATS["found"] = len(steps) + len(fns) + len(folds)
        frames = []
        for (x0, y0, x1, y1) in fns:
            frames.append(_frame_of(px, x0, (y0 + y1) // 2))
        # 1. tints: under-the-text colours are moved by adding / taking off a little everywhere in the row
        gpu.state.blend_set("ADDITIVE")
        for (x0, y0, x1, y1) in steps:
            cy = (y0 + y1) // 2
            _rect(round(8 * s), cy - round(11.5 * s), right, cy + round(11.5 * s), (LIGHTER, LIGHTER, LIGHTER, 1.0))
        gpu.state.blend_set("SUBTRACT")
        for (x0, y0, x1, y1), fr in zip(fns, frames):
            if fr is None:                                # closed: the darker, indented row
                cy = (y0 + y1) // 2
                _rect(x0 - round(4 * s), cy - half, right, cy + half, (DARKER, DARKER, DARKER, 1.0))
        # 2. markers painted over, green lines
        gpu.state.blend_set("ALPHA")
        for spots, tint in ((steps, LIGHTER), (fns, None), (folds, None)):
            for (x0, y0, x1, y1), fr in zip(spots, frames if spots is fns else [None] * len(spots)):
                ground = px[(y0 + y1) // 2, min(x1 + 2, strip - 1), :3] / 255.0
                if tint:
                    ground = np.minimum(ground + tint, 1.0)
                elif spots is fns and fr is None:
                    ground = np.maximum(ground - DARKER, 0.0)
                _rect(x0 - 1, y0 - 1, x1 + 2 + round(s), y1 + 2, (*ground, 1.0))
        for (x0, y0, x1, y1) in steps:
            cy = (y0 + y1) // 2
            _rect(round(8 * s), cy - round(11.5 * s), round(8 * s) + lw, cy + round(11.5 * s), g)
        for (x0, y0, x1, y1), fr in zip(fns, frames):
            if fr is not None:
                ex, bottom = fr
                _rect(ex, bottom + round(3 * s), ex + lw, (y0 + y1) // 2 + half, g)
        dash = (0.45, 0.45, 0.45, 1.0)
        for (x0, y0, x1, y1) in folds:                    # a fold inside a function: a dashed line down its body,
            fr = next((f for f, (_a, fy0, _b, fy1) in zip(frames, fns) if f is not None and f[1] < y0 < fy1), None)
            if fr is None:                                # to the bottom of the function's frame (prototype)
                continue
            x = (x0 + x1) // 2 + round(1 * s)
            y = y0 - round(4 * s)
            while y > fr[1] + round(8 * s):
                _rect(x, max(y - round(4 * s), fr[1] + round(8 * s)), x + 1, y, dash)
                y -= round(8 * s)
        gpu.state.blend_set("NONE")
    except Exception as e:  # noqa: BLE001
        print("[0244] overlay:", e)
    STATS["n"] += 1
    STATS["t"] += time.perf_counter() - t0


def overlay(on: bool) -> None:
    if on and _HANDLE["h"] is None:
        _HANDLE["h"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "UI", "POST_PIXEL")
    elif not on and _HANDLE["h"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_HANDLE["h"], "UI")
        _HANDLE["h"] = None


def set(**kw) -> None:  # noqa: A001
    S.update(kw)
    theme(new())
    overlay(S["look"] == "new" and S["overlay"] != "off")
    from . import panels
    panels.redraw()


def register():
    bpy.utils.register_class(FRESING_OT_fold244)
    if new():
        set()


def unregister():
    overlay(False)
    theme(False)
    try:
        bpy.utils.unregister_class(FRESING_OT_fold244)
    except RuntimeError:
        pass
    if _ICONS["pc"] is not None:
        from bpy.utils import previews
        previews.remove(_ICONS["pc"])
        _ICONS["pc"] = None
