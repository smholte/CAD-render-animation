"""Operators of 5 Scene & Render > Vessel motion (task 0085)."""

from __future__ import annotations

import bpy
from mathutils import Vector

from . import build, vessel_motion


def _redraw(context) -> None:
    for area in getattr(context.screen, "areas", []) if context.screen else []:
        area.tag_redraw()


class FRESING_OT_vessel_pivot_pick(bpy.types.Operator):
    """Click the point the vessel should turn about (on the deck, the machine or the water). Most vessels turn
    about a point at the waterline near their middle. Esc cancels"""

    bl_idname = "fresing.vessel_pivot_pick"
    bl_label = "Pick the pivot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return vessel_motion.effective(context.scene)

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        context.workspace.status_text_set(
            "Click the point the vessel turns about.  Esc / right-click: cancel.  Middle mouse / scroll: move the view")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from .ops_motion import _raycast, over_panel
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = _raycast(context, event)
        if res is None:
            context.workspace.status_text_set("Missed: click the deck, the machine or the water. Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        scene = context.scene
        moving = any(c.name in vessel_motion.CONSTRAINTS for p in _chain(ob) for c in p.constraints)
        point = vessel_motion.to_rest(scene, loc) if moving else Vector(loc)
        _set_pivot(scene, point)
        self.report({"INFO"}, f"The vessel turns about {_where(point)}")
        _redraw(context)
        return {"FINISHED"}

    def execute(self, context):              # scripts and tests: the automatic point
        scene = context.scene
        v = vessel_motion.settings(scene)
        v.pivot_mode = "AUTO"
        p = vessel_motion.pivot(scene)
        if p is None:
            return {"CANCELLED"}
        _set_pivot(scene, p)
        return {"FINISHED"}


def _chain(ob):
    while ob is not None:
        yield ob
        ob = ob.parent


def _where(p) -> str:
    return f"x {p.x:.1f} m, y {p.y:.1f} m, z {p.z:.1f} m"


def _set_pivot(scene, point) -> None:
    v = vessel_motion.settings(scene)
    v.pivot = tuple(point)
    v.pivot_mode = "PICK"
    scene.fresing.last_message = f"Vessel motion: turns about {_where(Vector(point))}"


def _picked(context) -> list:
    objs = [ob for ob in context.selected_objects if ob.get(build.PROP_KIND) in build.MODEL_KINDS]
    ob = context.active_object
    if ob is not None and ob.get(build.PROP_KIND) in build.MODEL_KINDS and ob not in objs:
        objs.append(ob)
    return objs


class FRESING_OT_vessel_still_add(bpy.types.Operator):
    """The selected subassemblies (or parts) keep their place while the vessel moves. Select them in the view or in
    2 Structure first. Still: no motion at all. Level: no roll or pitch, but it rises and falls with the vessel"""

    bl_idname = "fresing.vessel_still_add"
    bl_label = "Keep the selection still"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(items=vessel_motion.MODES, default="STILL",
                                 description="How the selection keeps its place")

    @classmethod
    def description(cls, context, props):
        if props is not None and props.mode == "LEVEL":
            return ("The selected subassemblies (or parts) stay level while the vessel rolls and pitches; they still "
                    "rise and fall with it (heave). Select them in the view or in 2 Structure first")
        return ("The selected subassemblies (or parts) stay where they are in the world while the vessel moves (a "
                "motion-compensated gangway, a hook that holds its place). Select them in the view or in 2 "
                "Structure first")

    @classmethod
    def poll(cls, context):
        return vessel_motion.effective(context.scene)

    def execute(self, context):
        objs = _picked(context)
        if not objs:
            self.report({"WARNING"}, "Select a subassembly first: click it in the view or in 2 Structure")
            return {"CANCELLED"}
        n = vessel_motion.add_marks(context.scene, objs, self.mode)
        what = "still" if self.mode == "STILL" else "level"
        names = ", ".join(ob.get(build.PROP_NAME, ob.name) for ob in objs[:3])
        self.report({"INFO"}, f"Stays {what}: {names}" + (" …" if len(objs) > 3 else "") if n else "Nothing changed")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_vessel_still_remove(bpy.types.Operator):
    """The subassembly picked in the list moves with the vessel again"""

    bl_idname = "fresing.vessel_still_remove"
    bl_label = "Move with the vessel again"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        v = vessel_motion.settings(context.scene)
        return 0 <= v.still_index < len(v.still)

    def execute(self, context):
        scene = context.scene
        v = vessel_motion.settings(scene)
        v.still.remove(v.still_index)
        v.still_index = min(v.still_index, len(v.still) - 1)
        vessel_motion.sync(scene)
        _redraw(context)
        return {"FINISHED"}


CLASSES = (FRESING_OT_vessel_pivot_pick, FRESING_OT_vessel_still_add, FRESING_OT_vessel_still_remove)
