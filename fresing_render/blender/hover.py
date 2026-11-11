"""Hover highlight while picking an axis (task 0088).

While a click picker waits for its click (Add joint, Set axis, a cylinder's pins, the double arm's hub and pot hinge),
the CAD face the click would use lights up under the mouse: the whole hole, shaft or flat face as a see-through magenta
fill with an outline, the axis the click would give (a line through a hole's or shaft's centre, past the part on both
ends, or an arrow square to a flat face) and a short text next to the mouse and in the status bar.

Only an overlay: two draw handlers of the 3D view, nothing in ``bpy.data``, never in a render or the saved file. Gone
after Esc, right-click, a finished or refused pick, an error, undo or opening another file.

One helper for every picker::

    hover.start(context, self, "Click a hole or shaft …", refuse=None)        # in invoke
    hover.on_event(self, context, event)                                      # first thing in modal (mouse moves)
    hover.prompt(context, "2 of 2: …")                                        # new words for the next click
    res = hover.pick(context, event)        # the click: the same ray, the same part, face and axis as the highlight
    hover.end(self, context)                                                    # every way out

``look(scene, depsgraph, origin, direction)`` is the work of one mouse move without a window (tests, PC check).

Speed: the ray is Blender's own (``scene.ray_cast``, its BVH trees are kept with the meshes). Per mesh the CAD face
starts, triangles and points are read once (``foreach_get``); per (mesh, CAD face) the fill and outline once. While the
mouse stays on one face only the axis point and the text are worked out again. Blender hands a modal operator only
the newest mouse position when it lags behind, so moves are never queued up.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Vector

from . import build

COLOUR = (1.0, 0.10, 0.80)          # the highlight: magenta. Not orange: Blender outlines the selection in orange, and
                                    # machines are often painted yellow or orange; no paint scheme uses magenta
NO = (0.90, 0.12, 0.10)             # a part this picker refuses
FILL_ALPHA = 0.35
DARK = (0.05, 0.05, 0.05, 0.85)     # under the outline and the axis: they read on any paint

_MESH: dict = {}                    # mesh name -> (polygon count, face starts, triangles, points)
_FACE: dict = {}                    # (mesh name, polygon count, face) -> (fill points, outline points), part coordinates
_S: dict = {"op": None, "prompt": "", "hover": None, "mouse": None, "area": 0, "handles": [], "batches": {},
            "status": None}


# ---------------------------------------------------------------------------
# the work of one mouse move (no window needed)
# ---------------------------------------------------------------------------

@dataclass
class Hover:
    """What is under the mouse. ``part`` is '' when no part is (``text`` says what is there)."""
    part: str = ""                  # object name
    face: int = -1                  # CAD face number on the part's mesh
    tris: tuple = (0, 0)            # its triangles: first, one past the last
    origin: Vector | None = None    # the axis the click would give (world), as ``joints.axis_from_hit``
    direction: Vector | None = None
    kind: str = ""                  # "hole", "shaft", "round", "flat", or "" (not a part)
    diameter: float = 0.0           # mm, round faces
    text: str = "Not a part"
    refused: str = ""               # why this picker does not take this spot
    ms: float = 0.0                 # time it took
    ends: tuple = field(default_factory=tuple)   # the axis line / arrow to draw: world points in pairs


def cast(scene, depsgraph, origin, direction):
    """The ray every axis picker uses: (part object, polygon, location, normal) or (hit object or None, -1, None,
    None) when no part is there. A sticker counts as the part under it (``decals.through``)."""
    hit, loc, normal, index, ob, _m = scene.ray_cast(depsgraph, Vector(origin), Vector(direction))
    if not hit or ob is None:
        return None, -1, None, None
    ob = getattr(ob, "original", ob)
    from . import decals
    ob, index, loc, normal = decals.through(ob, index, loc, normal)
    if ob.get(build.PROP_KIND) != "part":
        return ob, -1, None, None
    return ob, index, loc, normal


def _mesh(me):
    """(polygons, CAD face starts, triangles (n, 3), points (m, 3)) of a mesh, read once. Never writes the mesh."""
    from . import faces
    n = len(me.polygons)
    hit = _MESH.get(me.name)
    if hit is not None and hit[0] == n and len(hit[3]) == len(me.vertices):
        return hit
    starts = None
    if faces.PROP_STARTS in me:
        arr = np.asarray(me[faces.PROP_STARTS], dtype=np.int64)
        if len(arr) >= 2 and arr[-1] == n:
            starts = arr
    if starts is None:
        starts = faces._starts_from_shape(me)               # an old mesh: worked out, not stored (only a look)
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    hit = (n, starts, faces._triangles(me), co.reshape(-1, 3))
    _MESH[me.name] = hit
    return hit


def face_shape(me, face: int):
    """Fill (triangle corners) and outline (edge ends) of one CAD face, part coordinates, float32; cached."""
    n, starts, tris, co = _mesh(me)
    key = (me.name, n, face)
    hit = _FACE.get(key)
    if hit is not None:
        return hit
    t = tris[int(starts[face]):int(starts[face + 1])]
    fill = co[t.reshape(-1)]
    e = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    uniq, count = np.unique(e, axis=0, return_counts=True)
    edge = uniq[count == 1]                                  # used by one triangle only: the face's border
    outline = co[edge.reshape(-1)]
    if len(_FACE) > 400:
        _FACE.clear()
    _FACE[key] = (fill, outline)
    return fill, outline


def _size_text(mm: float) -> str:
    return f"{mm:.1f}".rstrip("0").rstrip(".")


def _axis_ends(ob, kind: str, o: Vector, d: Vector) -> tuple:
    """World points (in pairs) of the axis to draw: through the part and a little past it, or an arrow."""
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    size = max((corners[0] - c).length for c in corners) or 0.05
    if kind == "flat":
        length = min(max(0.2 * size, 0.03), 0.6)
        tip = o + d * length
        a = d.orthogonal().normalized()
        b = d.cross(a).normalized()
        h = length * 0.22
        pts = [o, tip]
        for side in (a, -a, b, -b):
            pts += [tip, tip - d * h + side * h * 0.45]
        return tuple(pts)
    ts = [(c - o).dot(d) for c in corners]
    extra = 0.12 * (max(ts) - min(ts)) + 0.01
    return (o + d * (min(ts) - extra), o + d * (max(ts) + extra))


def look(scene, depsgraph, origin, direction, refuse=None) -> Hover:
    """What a click along this ray would pick: the part, its CAD face, the axis (``joints.axis_from_hit``) and the text.
    ``refuse(part, origin, direction)`` returns why the picker would not take it ('' = fine)."""
    from . import joints
    t0 = time.perf_counter()
    ob, index, loc, normal = cast(scene, depsgraph, origin, direction)
    if index < 0:
        what = "empty space" if ob is None else "the floor, the surroundings or a helper"
        h = Hover(text=f"Not a part ({what})")
        h.ms = (time.perf_counter() - t0) * 1000.0
        return h
    o, d, desc = joints.axis_from_hit(ob, index, loc, normal)
    name = ob.get(build.PROP_NAME, ob.name)
    face, tris = -1, (index, index + 1)
    if ob.type == "MESH" and ob.data is not None:
        n, starts, _t, _c = _mesh(ob.data)
        if 0 <= index < n:
            face = int(np.searchsorted(starts, index, side="right") - 1)
            tris = (int(starts[face]), int(starts[face + 1]))
    m = re.search(r"Ø([\d.]+)", desc)
    dia = float(m.group(1)) if m else 0.0
    if desc.startswith("round"):
        radial = Vector(loc) - o
        radial -= d * radial.dot(d)
        if radial.length < 1e-9:
            kind = "round"
        else:
            kind = "hole" if Vector(normal).dot(radial) < 0 else "shaft"
        word = {"hole": "Hole", "shaft": "Shaft", "round": "Round face"}[kind]
        what = (f"{word} Ø{_size_text(dia)} mm" if dia else word) + " – axis through its centre"
    else:
        kind = "flat"
        what = "Flat face – axis at right angles to it"
    h = Hover(part=ob.name, face=face, tris=tris, origin=o, direction=d, kind=kind, diameter=dia,
              text=f"{name}: {what}")
    if refuse is not None:
        try:
            why = refuse(ob, o, d) or ""
        except Exception as exc:  # noqa: BLE001 - a check must never break the pick
            why = str(exc)
        if why:
            h.refused = why
            h.text = f"{name}: {why}"
    h.ends = _axis_ends(ob, kind, o, d)
    if face >= 0:
        face_shape(ob.data, face)                            # cached now: the draw only fetches it
    h.ms = (time.perf_counter() - t0) * 1000.0
    return h


# ---------------------------------------------------------------------------
# a running pick
# ---------------------------------------------------------------------------

def enabled() -> bool:
    from . import prefs
    p = prefs.get()
    return True if p is None else bool(getattr(p, "hover_highlight", True))


def _region_ray(context, event):
    """(region, origin, direction) of the 3D view under the mouse, or None (side panel, header, another editor)."""
    from bpy_extras import view3d_utils
    from .ops_motion import _inside, over_panel
    area = context.area
    if area is None or area.type != "VIEW_3D" or over_panel(context, event):
        return None
    region = next((r for r in area.regions if r.type == "WINDOW" and _inside(r, event)), None)
    if region is None or region.data is None:
        return None
    co = (event.mouse_x - region.x, event.mouse_y - region.y)
    return (region, view3d_utils.region_2d_to_origin_3d(region, region.data, co),
            view3d_utils.region_2d_to_vector_3d(region, region.data, co))


def pick(context, event):
    """The click: (part, polygon, location, normal) or None – the same ray and part as the highlight."""
    ray = _region_ray(context, event)
    if ray is None:
        return None
    ob, index, loc, normal = cast(context.scene, context.evaluated_depsgraph_get(), ray[1], ray[2])
    if index < 0:
        return None
    return ob, index, loc, normal


def start(context, op, prompt: str, refuse=None) -> None:
    """A pick starts (in its ``invoke``). ``refuse(part, origin, direction)``: '' or why this picker will not take
    that spot (drawn in red with the reason)."""
    end(None, context)                                       # one pick at a time
    _S.update(op=op, prompt=prompt, hover=None, mouse=None, area=0, batches={}, status=None, refuse=refuse)
    _add_handlers()
    _status(context)


def prompt(context, text: str) -> None:
    """New words for the status bar (the next click), the highlight stays."""
    _S["prompt"] = text
    _S["status"] = None
    _status(context)


def _status(context) -> None:
    h = _S.get("hover")
    text = _S.get("prompt") or ""
    if h is not None:
        text = f"{h.text}   ·   {text}"
    if text == _S.get("status"):
        return
    _S["status"] = text
    try:
        context.workspace.status_text_set(text)
    except Exception:  # noqa: BLE001
        pass


def on_event(op, context, event) -> None:
    """Call first in the picker's modal: a mouse move updates the highlight (the event still passes through)."""
    if _S.get("op") is not op or event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
        return
    move(context, event)


def move(context, event) -> Hover | None:
    """Work out what is under the mouse and redraw when it changed."""
    pos = (event.mouse_x, event.mouse_y)
    if pos == _S.get("mouse") and _S.get("hover") is not None:
        return _S["hover"]
    _S["mouse"] = pos
    old = _S.get("hover")
    ray = _region_ray(context, event) if enabled() else None
    if ray is None:
        h = None
    else:
        h = look(context.scene, context.evaluated_depsgraph_get(), ray[1], ray[2], _S.get("refuse"))
        _S["area"] = context.area.as_pointer()
    _S["hover"] = h
    _status(context)
    if old is not None or h is not None:
        _redraw()
    return h


def current() -> Hover | None:
    """The highlight now (None: nothing drawn)."""
    return _S.get("hover") if _S.get("op") is not None else None


def active() -> bool:
    return _S.get("op") is not None


def end(op, context=None) -> None:
    """The pick is over (or ``op`` None: whatever pick runs): nothing is drawn any more."""
    if op is not None and _S.get("op") is not op:
        return
    had = _S.get("op") is not None or _S.get("hover") is not None
    _S.update(op=None, hover=None, mouse=None, area=0, batches={}, status=None, refuse=None)
    _remove_handlers()
    if had:
        _redraw()


def clear() -> None:
    """Forget what is under the mouse (undo: the parts were made again); the next move works it out again."""
    _MESH.clear()
    _FACE.clear()
    _S.update(hover=None, mouse=None, batches={})
    _redraw()


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _add_handlers() -> None:
    if _S["handles"] or bpy.app.background:
        return
    try:
        _S["handles"] = [bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), "WINDOW", "POST_VIEW"),
                         bpy.types.SpaceView3D.draw_handler_add(_draw_text, (), "WINDOW", "POST_PIXEL")]
    except Exception:  # noqa: BLE001
        _S["handles"] = []


def _remove_handlers() -> None:
    for hnd in _S.get("handles") or []:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(hnd, "WINDOW")
        except Exception:  # noqa: BLE001
            pass
    _S["handles"] = []


def _alive() -> bool:
    """The pick still runs: a finished operator is freed, reading it then raises."""
    op = _S.get("op")
    if op is None:
        return False
    try:
        op.bl_idname
        return True
    except ReferenceError:
        return False


def _end_later():
    if not _alive():
        end(None)
    return None


def _lines(shader, pts, color, width):
    from gpu_extras.batch import batch_for_shader
    import gpu
    vp = gpu.state.viewport_get()
    shader.uniform_float("viewportSize", (vp[2], vp[3]))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch_for_shader(shader, "LINES", {"pos": pts}).draw(shader)


def _draw_view() -> None:
    h = _S.get("hover")
    if h is None or not h.part:
        return
    if not _alive():                                         # the pick ended without saying so (an error)
        if not bpy.app.timers.is_registered(_end_later):
            bpy.app.timers.register(_end_later, first_interval=0.0)
        return
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        ob = bpy.data.objects.get(h.part)
        if ob is None:
            return
        col = NO if h.refused else COLOUR
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")                     # on top of the model: the whole hole shows
        if h.face >= 0 and ob.type == "MESH":
            key = (ob.data.name, h.face)
            hit = _S["batches"].get(key)
            if hit is None:
                fill, outline = face_shape(ob.data, h.face)
                flat = gpu.shader.from_builtin("UNIFORM_COLOR")
                hit = (batch_for_shader(flat, "TRIS", {"pos": fill}), outline)
                _S["batches"] = {key: hit}                   # one face at a time
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(ob.matrix_world)
            flat = gpu.shader.from_builtin("UNIFORM_COLOR")
            flat.uniform_float("color", (*col, FILL_ALPHA))
            hit[0].draw(flat)
            if len(hit[1]):
                line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
                _lines(line, hit[1], DARK, 4.0)
                _lines(line, hit[1], (*col, 1.0), 2.0)
            gpu.matrix.pop()
        if h.ends:
            pts = [tuple(p) for p in h.ends]
            line = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
            _lines(line, pts, DARK, 5.0)
            _lines(line, pts, (*col, 1.0), 2.5)
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001 - drawing must never break the view
        pass


def _draw_text() -> None:
    h = _S.get("hover")
    if h is None or _S.get("mouse") is None:
        return
    try:
        area = bpy.context.area
        region = bpy.context.region
        if area is None or region is None or area.as_pointer() != _S.get("area"):
            return
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        scale = bpy.context.preferences.system.ui_scale or 1.0
        x = _S["mouse"][0] - region.x + int(18 * scale)
        y = _S["mouse"][1] - region.y - int(30 * scale)
        font = 0
        blf.size(font, 13 * scale)
        w, th = blf.dimensions(font, h.text)
        pad = 5 * scale
        x = min(x, region.width - w - 2 * pad)
        box = [(x - pad, y - pad), (x + w + pad, y - pad), (x + w + pad, y + th + pad), (x - pad, y + th + pad)]
        flat = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        flat.uniform_float("color", DARK)
        batch_for_shader(flat, "TRI_FAN", {"pos": box}).draw(flat)
        col = NO if h.refused else (COLOUR if h.part else (0.8, 0.8, 0.8))
        blf.color(font, *col, 1.0)
        blf.position(font, x, y, 0)
        blf.draw(font, h.text)
        gpu.state.blend_set("NONE")
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# undo, another file
# ---------------------------------------------------------------------------

@persistent
def _after_undo(_dummy=None):
    if _S.get("op") is not None or _S.get("hover") is not None:
        clear()


@persistent
def _before_load(_dummy=None):
    end(None)
    _MESH.clear()
    _FACE.clear()


def register():
    for lst, fn in ((bpy.app.handlers.undo_post, _after_undo), (bpy.app.handlers.redo_post, _after_undo),
                    (bpy.app.handlers.load_pre, _before_load)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    end(None)
    for lst, fn in ((bpy.app.handlers.undo_post, _after_undo), (bpy.app.handlers.redo_post, _after_undo),
                    (bpy.app.handlers.load_pre, _before_load)):
        while fn in lst:
            lst.remove(fn)
