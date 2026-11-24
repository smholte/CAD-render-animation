"""Measure (task 0322): the tool you click with, and the buttons of the Measure drop-down.

``fresing.measure`` is the tool: a modal operator in the main 3D view. Each mouse move asks ``measure.look`` what a
click would take (the hovered face lights up, a dot sits on the snapped corner / middle / centre, an edge shows as a
line, and the value the next click gives is shown next to the mouse); a click takes it; when the measurement has its
clicks it is kept (``measure.add``) and the tool waits for the next one. Shift: no snapping. A click on a label copies
its value. Esc (or the right mouse) drops the clicks of an unfinished measurement, a second Esc leaves the tool.

The keys (lock.APP_KEYS): **M** outside Full access – where Blender's own M ("move to collection") was already off –
and **Alt+M** everywhere (Blender has nothing on Alt+M in Object Mode). Both start the kind last picked in the menu.
Every operator here works in the Client view (``lock.ALLOWED_PREFIXES`` "fresing.measure"): measuring changes nothing
of the model, and the Client view never saves the measurements.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty

from ..core import measure as core
from . import measure

KIND_ITEMS = [("", "Last used", "The kind of measurement last picked in the Measure menu")] + measure.KIND_ITEMS
NAV = {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE", "TRACKPADPAN",
       "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM", "NDOF_MOTION", "HOME", "TIMER", "TIMER_REPORT"}


def _view_under(context, event):
    """(area, region) of the 3D view's main region under the mouse, not over its side panel or header; or None."""
    win = context.window
    if win is None:
        return None
    from .ops_motion import _inside
    for area in win.screen.areas:
        if area.type != "VIEW_3D":
            continue
        if not (area.x <= event.mouse_x < area.x + area.width and area.y <= event.mouse_y < area.y + area.height):
            continue
        if any(r.type in ("UI", "HEADER", "TOOLS", "TOOL_HEADER", "ASSET_SHELF", "ASSET_SHELF_HEADER")
               and r.width > 1 and r.height > 1 and _inside(r, event) for r in area.regions):
            return None
        region = next((r for r in area.regions if r.type == "WINDOW" and _inside(r, event)), None)
        if region is None or region.data is None:
            return None
        return area, region
    return None


def _project(region, rv3d):
    from bpy_extras import view3d_utils
    from mathutils import Vector

    def f(p):
        xy = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(p))
        return None if xy is None else (float(xy[0]), float(xy[1]))
    return f


def start(context, kind: str = "") -> set:
    """Start the tool in the main 3D view (from the top bar, a menu or a key)."""
    from .ops_setup import main_view
    win, area, region = main_view(context)
    if area is None:
        return {"CANCELLED"}
    with context.temp_override(window=win, area=area, region=region):
        return bpy.ops.fresing.measure("INVOKE_DEFAULT", kind=kind)


class FRESING_OT_measure(bpy.types.Operator):
    """Measure in the 3D view: click faces, edges or points of the model and read the value. Corners, edge middles
    and centres snap (hold Shift for none); a click on a label copies its value; Esc leaves"""

    bl_idname = "fresing.measure"
    bl_label = "Measure"

    kind: EnumProperty(name="Measure", items=KIND_ITEMS, default="", options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return scene is not None and getattr(scene, "fresing_measure", None) is not None

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            return start(context, self.kind)
        st = measure.settings(context.scene)
        kind = self.kind or st.last
        if self.kind:
            st.last = self.kind
        self._kind = kind
        self._tool = measure.tool_start(kind, context.area.as_pointer())
        self._tool["prompt"] = measure.prompt_for(kind, [])
        self._status(context)
        context.window_manager.modal_handler_add(self)
        self._update(context, event)
        return {"RUNNING_MODAL"}

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _status(self, context, extra: str = "") -> None:
        try:
            context.workspace.status_text_set((extra + "   ·   " if extra else "") + self._tool.get("prompt", ""))
        except Exception:  # noqa: BLE001
            pass

    def _update(self, context, event) -> None:
        t = self._tool
        t["mouse"] = (event.mouse_x, event.mouse_y)
        got = _view_under(context, event)
        if got is None:
            t["look"] = None
            measure._redraw_views()
            return
        area, region = got
        t["area"] = area.as_pointer()
        from bpy_extras import view3d_utils
        rv3d = region.data
        co = (event.mouse_x - region.x, event.mouse_y - region.y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
        scale = context.preferences.system.ui_scale or 1.0
        t["look"] = measure.look(context.scene, context.evaluated_depsgraph_get(), origin, direction, co,
                                 _project(region, rv3d), self._kind, list(t["picks"]), no_snap=event.shift,
                                 scale=scale)
        self._status(context, t["look"].text)
        measure._redraw_views()

    def _finish(self, context) -> None:
        measure.tool_end()
        try:
            context.workspace.status_text_set(None)
        except Exception:  # noqa: BLE001
            pass

    def _take(self, context) -> None:
        t = self._tool
        lk = t.get("look")
        if lk is None or lk.pick is None:
            return
        if lk.refused:
            self.report({"WARNING"}, lk.refused)
            return
        t["picks"].append((lk.part, lk.pick))
        world = [p for _n, p in t["picks"]]
        if len(world) < core.needs(self._kind, world):
            t["prompt"] = measure.prompt_for(self._kind, world)
            return
        scene = context.scene
        parts = []
        for name, pk in t["picks"]:
            ob = bpy.data.objects.get(name)
            if ob is None:
                t["picks"].clear()
                self.report({"WARNING"}, "A part you clicked is gone: click again")
                return
            parts.append((ob, measure.to_local(ob, pk)))
        item = measure.add(scene, self._kind, parts)
        r = measure.result(scene, item)
        t["picks"].clear()
        t["prompt"] = measure.prompt_for(self._kind, [])
        if r is not None:
            self.report({"INFO"}, " · ".join(r.lines))
        if not bpy.app.background:
            try:
                bpy.ops.ed.undo_push(message="Measure")
            except Exception:  # noqa: BLE001
                pass

    def modal(self, context, event):
        if measure.tool_state() is not self._tool:      # another file was opened, or the tool was started again
            if measure.tool_state() is None:
                self._finish(context)
            return {"CANCELLED"}
        if event.type in ("MOUSEMOVE", "INBETWEEN_MOUSEMOVE"):
            self._update(context, event)
            return {"PASS_THROUGH"}
        if event.type in ("LEFT_SHIFT", "RIGHT_SHIFT"):
            self._update(context, event)
            return {"RUNNING_MODAL"}
        if event.type in NAV or event.type.startswith(("NDOF", "NUMPAD", "TRACKPAD")):
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            got = _view_under(context, event)
            if got is None:
                return {"PASS_THROUGH"}            # the side panel, a header, the top bar: their buttons work
            i = measure.label_at(got[0].as_pointer(), event.mouse_x, event.mouse_y)
            if i >= 0:
                copy(context, self, i)
                return {"RUNNING_MODAL"}
            self._update(context, event)
            self._take(context)
            self._update(context, event)
            return {"RUNNING_MODAL"}
        if event.type in ("ESC", "RIGHTMOUSE") and event.value == "PRESS":
            if self._tool["picks"]:
                self._tool["picks"].clear()
                self._tool["prompt"] = measure.prompt_for(self._kind, [])
                self._update(context, event)
                return {"RUNNING_MODAL"}
            self._finish(context)
            return {"FINISHED"}
        if event.type == "LEFTMOUSE":
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def cancel(self, context):
        self._finish(context)


COPIED = [""]                        # the last value copied (tests: Blender as a module has no clipboard)


def copy(context, op, index: int) -> bool:
    """Put measurement ``index``'s value on the clipboard (as it reads, in the unit chosen)."""
    st = measure.settings(context.scene)
    if not 0 <= index < len(st.items):
        return False
    r = measure.result(context.scene, st.items[index])
    if r is None:
        op.report({"WARNING"}, "A part of this measurement is gone")
        return False
    text = r.value_text(st.units) or r.lines[0]
    COPIED[0] = text
    context.window_manager.clipboard = text
    op.report({"INFO"}, f"Copied {text}")
    return True


class FRESING_OT_measure_key(bpy.types.Operator):
    """M: measure in the 3D view (the kind last picked in the Measure menu). In Full access M is Blender's own again:
    use Alt+M there"""

    bl_idname = "fresing.measure_key"
    bl_label = "Measure (M)"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        from . import lock
        scene = getattr(context, "scene", None)
        return lock.keys_quiet() and scene is not None and getattr(scene, "fresing_measure", None) is not None

    def invoke(self, context, event):
        if context.area is not None and context.area.type == "VIEW_3D":
            res = bpy.ops.fresing.measure("INVOKE_DEFAULT")
        else:
            res = start(context)
        return {"FINISHED"} if res & {"FINISHED", "RUNNING_MODAL"} else {"CANCELLED"}

    def execute(self, context):
        res = start(context)
        return {"FINISHED"} if res & {"FINISHED", "RUNNING_MODAL"} else {"CANCELLED"}


class FRESING_OT_measure_copy(bpy.types.Operator):
    """Copies this measurement's value (in the unit chosen below) so you can paste it anywhere"""

    bl_idname = "fresing.measure_copy"
    bl_label = "Copy"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=0, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        return {"FINISHED"} if copy(context, self, self.index) else {"CANCELLED"}


class FRESING_OT_measure_remove(bpy.types.Operator):
    """Removes this measurement from the view (and from the project)"""

    bl_idname = "fresing.measure_remove"
    bl_label = "Remove"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=0, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        measure.remove(context.scene, self.index)
        return {"FINISHED"}


class FRESING_OT_measure_clear(bpy.types.Operator):
    """Removes every measurement from the view (and from the project)"""

    bl_idname = "fresing.measure_clear"
    bl_label = "Clear all"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        st = getattr(context.scene, "fresing_measure", None)
        return st is not None and len(st.items) > 0

    def execute(self, context):
        from ..core.words import plural
        n = measure.clear(context.scene)
        self.report({"INFO"}, f"{plural(n, 'measurement')} cleared")
        return {"FINISHED"}


CLASSES = (FRESING_OT_measure, FRESING_OT_measure_key, FRESING_OT_measure_copy, FRESING_OT_measure_remove,
           FRESING_OT_measure_clear)
