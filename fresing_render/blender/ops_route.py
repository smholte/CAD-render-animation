"""Shape the route of a hose or cable between its ends, in the 3D view (task 0298).

**Shape the route** (``fresing.flex_route``, 4 Motion > Hoses and drag chains, under the chosen hose): the hose's
middle line shows as a thin line with its via points as white dots (clips grey, ends as squares).

* drag a dot: the via point moves with the mouse (square to the view, at its own depth) and the hose follows;
* click on the line: a via point is added there – and can be dragged at once;
* X or Delete over a dot: that via point goes;
* Enter, Space or a right-click: done (one undo step); Esc: the route as it was.

The middle mouse and the wheel move the view meanwhile. The work is in ``flex_route.py``; what the mouse is over is
worked out by ``hot`` (pure, tested): the nearest dot within ``PICK`` pixels, else the nearest point of the line within
``PICK``.
"""

from __future__ import annotations

import bpy
import numpy as np

from ..core.words import plural
from . import flex, flex_route

PICK = 12.0                     # px: a dot or the line counts as under the mouse this close
HELP = ("Drag a white dot to move the hose.  Click on the line to add a via point.  X: remove the dot under the mouse."
        "  Enter: done.  Esc: as it was")
_DRAW = {"handlers": [], "item": None, "hot": None}


def _item(context):
    it = flex.active(context.scene)
    return it if it is not None and it.kind == "HOSE" else None


def screen(region, rv3d, pts: np.ndarray) -> np.ndarray:
    """World points (N, 3) -> region pixels (N, 2); NaN for points behind the view."""
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    out = np.full((len(pts), 2), np.nan)
    for k, p in enumerate(np.asarray(pts, dtype=float)):
        v = location_3d_to_region_2d(region, rv3d, tuple(p))
        if v is not None:
            out[k] = (v.x, v.y)
    return out


def hot(mouse, dots: np.ndarray, line: np.ndarray, pick: float = PICK) -> tuple:
    """What the mouse (x, y) is over: ("dot", k) for the nearest dot within ``pick`` px, else ("line", i, t) for the
    piece i of the line (t: 0 … 1 along it) nearest within ``pick``, else (None,). ``dots`` (K, 2), ``line`` (N, 2)
    in pixels (NaN rows: not on screen)."""
    m = np.asarray(mouse, dtype=float)
    if len(dots):
        d = np.linalg.norm(dots - m, axis=1)
        d = np.where(np.isfinite(d), d, np.inf)
        k = int(np.argmin(d))
        if d[k] <= pick:
            return ("dot", k)
    if len(line) >= 2:
        a, b = line[:-1], line[1:]
        ab = b - a
        ll = np.einsum("ij,ij->i", ab, ab)
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.clip(np.einsum("ij,ij->i", m - a, ab) / np.where(ll > 0.0, ll, 1.0), 0.0, 1.0)
        q = a + t[:, None] * ab
        d = np.linalg.norm(q - m, axis=1)
        d = np.where(np.isfinite(d), d, np.inf)
        i = int(np.argmin(d))
        if d[i] <= pick:
            return ("line", i, float(t[i]))
    return (None,)


def _draw_view():
    """The route: the middle line, the ends, clips and via points (the hot one orange)."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    st = _DRAW
    ctx = bpy.context
    item = flex.find(ctx.scene, st["item"]) if st["item"] else None
    if item is None or flex.broken(ctx.scene, item):
        return
    try:
        line = flex.shape_now(ctx.scene, item)
        stops = flex_route.stops_now(item)
    except Exception:                           # noqa: BLE001 - never break the drawing
        return
    sh = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("ALPHA")
    if len(line) >= 2:
        gpu.state.line_width_set(2.0)
        b = batch_for_shader(sh, "LINE_STRIP", {"pos": [tuple(p) for p in line]})
        sh.uniform_float("color", (1.0, 1.0, 1.0, 0.55))
        b.draw(sh)
    vias = flex_route.via_indices(item)
    kinds = [("end", stops[0][0])] + [("via" if k in vias else "clip", stops[k + 1][0])
                                      for k in range(len(item.clips))] + [("end", stops[-1][0])]
    for kind, colour, size in (("end", (0.6, 0.6, 0.6, 1.0), 9.0), ("clip", (0.6, 0.6, 0.6, 1.0), 9.0),
                               ("via", (1.0, 1.0, 1.0, 1.0), 12.0)):
        pts = [tuple(p) for kk, p in kinds if kk == kind]
        if not pts:
            continue
        gpu.state.point_size_set(size)
        b = batch_for_shader(sh, "POINTS", {"pos": pts})
        sh.uniform_float("color", colour)
        b.draw(sh)
    h = st["hot"]
    if h is not None and h[0] == "dot" and h[1] < len(vias):
        gpu.state.point_size_set(15.0)
        b = batch_for_shader(sh, "POINTS", {"pos": [tuple(stops[vias[h[1]] + 1][0])]})
        sh.uniform_float("color", (1.0, 0.55, 0.1, 1.0))
        b.draw(sh)
    gpu.state.point_size_set(1.0)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def _start_drawing(item_name: str) -> None:
    _stop_drawing()
    _DRAW["item"], _DRAW["hot"] = item_name, None
    _DRAW["handlers"].append(bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), "WINDOW", "POST_VIEW"))


def _stop_drawing() -> None:
    for h in _DRAW["handlers"]:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, "WINDOW")
        except (ValueError, RuntimeError):
            pass
    _DRAW["handlers"].clear()
    _DRAW["item"] = _DRAW["hot"] = None


def _redraw(context) -> None:
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class FRESING_OT_flex_route(bpy.types.Operator):
    """Shapes the route of the hose between its ends in the 3D view: drag a white dot (a via point) and the hose
    follows, click on the hose's line to add a via point there, X over a dot removes it. Enter: done, Esc: as it was.
    The via points move along with the parts the ends sit on"""

    bl_idname = "fresing.flex_route"
    bl_label = "Shape the route"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        it = _item(context)
        return it is not None and it.enabled and not flex.broken(context.scene, it)

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        item = _item(context)
        self._name = item.name
        self._snap = flex_route.snapshot(item)
        self._drag = None                       # (clip index, depth point) while a dot is dragged
        self._moved = False
        _start_drawing(item.name)
        self._say(context, HELP)
        context.window_manager.modal_handler_add(self)
        _redraw(context)
        return {"RUNNING_MODAL"}

    def _say(self, context, text: str) -> None:
        try:
            context.workspace.status_text_set(text)
        except Exception:                       # noqa: BLE001
            pass

    def _end(self, context) -> None:
        _stop_drawing()
        try:
            context.workspace.status_text_set(None)
        except Exception:                       # noqa: BLE001
            pass
        _redraw(context)

    def _what(self, context, event, item) -> tuple:
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None:
            return (None,), None
        vias = flex_route.via_indices(item)
        stops = flex_route.stops_now(item)
        dots = screen(region, rv3d, np.array([stops[k + 1][0] for k in vias])) if vias else np.zeros((0, 2))
        line = flex.shape_now(context.scene, item)
        h = hot((event.mouse_region_x, event.mouse_region_y), dots, screen(region, rv3d, line))
        return h, (vias, stops, line)

    def _to_world(self, context, event, depth) -> np.ndarray:
        from bpy_extras.view3d_utils import region_2d_to_location_3d
        p = region_2d_to_location_3d(context.region, context.region_data,
                                     (event.mouse_region_x, event.mouse_region_y), tuple(depth))
        return np.array(p, dtype=float)

    def modal(self, context, event):
        scene = context.scene
        item = flex.find(scene, self._name)
        if item is None or flex.broken(scene, item):
            self._end(context)
            return {"CANCELLED"}
        from .ops_motion import over_panel
        if event.type == "MOUSEMOVE":
            if self._drag is not None:
                k, depth = self._drag
                flex_route.move(scene, item, k, self._to_world(context, event, depth), solve=True)
                self._moved = True
                _redraw(context)
                return {"RUNNING_MODAL"}
            h, _info = self._what(context, event, item)
            if h != _DRAW["hot"]:
                _DRAW["hot"] = h
                _redraw(context)
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE" and self._drag is not None:
            self._drag = None
            flex_route.changed(scene, item)
            n = flex_route.count(item)
            self._say(context, f"{plural(n, 'via point')}.  " + HELP)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and not over_panel(context, event):
            h, info = self._what(context, event, item)
            if h[0] == "dot":
                vias, stops, _line = info
                k = vias[h[1]]
                self._drag = (k, stops[k + 1][0])
                return {"RUNNING_MODAL"}
            if h[0] == "line":
                _vias, _stops, line = info
                i, t = h[1], h[2]
                p = line[i] + t * (line[i + 1] - line[i])
                at, weight = flex_route.where_on(item, line, i + (1 if t > 0.5 else 0))
                k = flex_route.add(scene, item, p, at, weight)
                item = flex.find(scene, self._name)
                self._drag = (k, p)
                self._moved = True
                _DRAW["hot"] = None
                _redraw(context)
                return {"RUNNING_MODAL"}
            return {"RUNNING_MODAL"}            # (a click beside the hose selects nothing meanwhile)
        if event.value == "PRESS" and event.type in {"X", "DEL"}:
            h, info = self._what(context, event, item)
            if h[0] == "dot":
                flex_route.remove(scene, item, info[0][h[1]])
                self._moved = True
                _DRAW["hot"] = None
                _redraw(context)
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER", "SPACE", "RIGHTMOUSE"}:
            self._end(context)
            n = flex_route.count(item)
            scene.fresing.last_message = f"'{item.name}': its route runs through {plural(n, 'via point')}"
            return {"FINISHED"} if self._moved else {"CANCELLED"}
        if event.value == "PRESS" and event.type == "ESC":
            flex_route.restore(scene, item, self._snap)
            self._end(context)
            return {"CANCELLED"}
        return {"PASS_THROUGH"}


class FRESING_OT_flex_route_clear(bpy.types.Operator):
    """Takes every via point off the chosen hose: it runs straight from end to end again (clips stay)"""

    bl_idname = "fresing.flex_route_clear"
    bl_label = "Clear the route"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        it = _item(context)
        return it is not None and flex_route.count(it) > 0

    def execute(self, context):
        item = _item(context)
        n = flex_route.clear(context.scene, item)
        context.scene.fresing.last_message = f"'{item.name}': {plural(n, 'via point')} taken off"
        return {"FINISHED"}


CLASSES = (FRESING_OT_flex_route, FRESING_OT_flex_route_clear)
