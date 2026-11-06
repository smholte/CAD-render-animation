"""Operators for way covers (4 Motion > Way covers, task 0034)."""

from __future__ import annotations

import bpy
from bpy.props import IntProperty

from . import waycover
from .ops_motion import selected_movers


class _Op:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and hasattr(context.scene, "fresing")


class FRESING_OT_waycover_add(_Op, bpy.types.Operator):
    """Makes the parts you clicked one section of the way cover. Click all parts of the section (any number
    of parts or subassemblies), start at the fixed end and work towards the moving end. Then press Make it"""

    bl_idname = "fresing.waycover_add"
    bl_label = "Add section"

    def execute(self, context):
        movers = selected_movers(context)
        try:
            sec = waycover.add_section(context.scene, movers)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Section '{sec.name}' added: {len(movers)} part{'s' if len(movers) != 1 else ''}")
        return {"FINISHED"}


class FRESING_OT_waycover_remove(_Op, bpy.types.Operator):
    """Takes the chosen section out of the way cover. Its parts stay where they are; the other sections
    share the travel again"""

    bl_idname = "fresing.waycover_remove"
    bl_label = "Remove section"

    def execute(self, context):
        c = waycover.settings(context.scene)
        if not c.sections:
            return {"CANCELLED"}
        waycover.remove_section(context.scene, c.sections_index)
        return {"FINISHED"}


class FRESING_OT_waycover_move(_Op, bpy.types.Operator):
    """Moves the chosen section one place towards the fixed end or the moving end. The order decides how far
    each section slides"""

    bl_idname = "fresing.waycover_move"
    bl_label = "Move section"

    direction: IntProperty(default=1)

    def execute(self, context):
        c = waycover.settings(context.scene)
        waycover.move_section(context.scene, c.sections_index, self.direction)
        return {"FINISHED"}


class FRESING_OT_waycover_select(_Op, bpy.types.Operator):
    """Selects the parts of the chosen section in the view, so you can see which ones it holds"""

    bl_idname = "fresing.waycover_select"
    bl_label = "Select the section's parts"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        c = waycover.settings(scene)
        if not 0 <= c.sections_index < len(c.sections):
            return {"CANCELLED"}
        parts = waycover.parts_of(scene, c.sections[c.sections_index])
        for ob in context.selected_objects:
            ob.select_set(False)
        n = 0
        for ob in parts:
            try:
                ob.select_set(True)
                n += 1
            except RuntimeError:
                pass
        if parts:
            context.view_layer.objects.active = parts[0]
        return {"FINISHED"} if n else {"CANCELLED"}


class FRESING_OT_waycover_read_total(_Op, bpy.types.Operator):
    """Takes the total length of movement from the limits of the axis joint (its Min and Max)"""

    bl_idname = "fresing.waycover_read_total"
    bl_label = "Read from the axis"

    def execute(self, context):
        reason = waycover.read_total(context.scene)
        if reason:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_waycover_make(_Op, bpy.types.Operator):
    """Makes the sections follow the axis: each one slides its share of the travel, so the covers move
    with the axis by hand, in poses, in animation steps and in the render queue. Press it again after
    adding sections; changing the travel needs no new press"""

    bl_idname = "fresing.waycover_make"
    bl_label = "Make it"

    def execute(self, context):
        try:
            built, problems = waycover.make(context.scene)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        for p in problems:
            self.report({"WARNING"}, p)
        if built or not problems:
            self.report({"INFO"}, waycover.status(context.scene) or "Way cover made")
        return {"FINISHED"} if built or not problems else {"CANCELLED"}


class FRESING_OT_waycover_remove_all(_Op, bpy.types.Operator):
    """Removes the way cover: the section joints it made go and the parts return to their CAD place. The axis
    joint and everything else stay as they are"""

    bl_idname = "fresing.waycover_remove_all"
    bl_label = "Remove way cover"

    def execute(self, context):
        n = waycover.remove_all(context.scene)
        self.report({"INFO"}, f"Way cover removed ({n} section{'s' if n != 1 else ''})")
        return {"FINISHED"}


class FRESING_OT_waycover_axis_from_selection(_Op, bpy.types.Operator):
    """For a machine without a slide joint yet: click the carriage (the part that moves), then click a hole
    or face in the view to set the direction. The new slide joint becomes the axis"""

    bl_idname = "fresing.waycover_axis_from_selection"
    bl_label = "Make one from the selection"

    def execute(self, context):
        before = {j.name for j in context.scene.fresing.joints}
        if not selected_movers(context):
            self.report({"WARNING"}, "First click the carriage: the part that the axis moves")
            return {"CANCELLED"}
        bpy.ops.fresing.joint_add("INVOKE_DEFAULT", kind="SLIDE")
        _watch_new_joint(context.scene, before)
        return {"FINISHED"}


def _watch_new_joint(scene, before: set) -> None:
    """The pick tool makes the joint a moment later: make it the axis as soon as it exists."""
    name = scene.name

    def _check():
        sc = bpy.data.scenes.get(name)
        if sc is None:
            return None
        new = [j for j in sc.fresing.joints if j.name not in before and j.kind == "SLIDE"]
        if new:
            waycover.settings(sc).axis = new[-1].name
            return None
        _tries["n"] += 1
        return 0.5 if _tries["n"] < 240 else None

    _tries = {"n": 0}
    bpy.app.timers.register(_check, first_interval=0.5)


CLASSES = (FRESING_OT_waycover_add, FRESING_OT_waycover_remove, FRESING_OT_waycover_move,
           FRESING_OT_waycover_select, FRESING_OT_waycover_read_total, FRESING_OT_waycover_make,
           FRESING_OT_waycover_remove_all, FRESING_OT_waycover_axis_from_selection)
