"""Operators of 5 Scene & Render > Vessel at work (task 0154): the vessel's thrusters."""

from __future__ import annotations

import bpy

from ..core import vessel_work as core
from . import vessel_work


class FRESING_OT_vessel_thrusters_find(bpy.types.Operator):
    """Finds the vessel's propellers among the joints (names with propeller, screw, schroef or Schraube) and tells
    their kind from the joints: one riding on an upright joint is an azimuth that steers on it, one turning across
    the vessel a tunnel thruster. Check the list afterwards"""

    bl_idname = "fresing.vessel_thrusters_find"
    bl_label = "Find thrusters"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.fresing.joints) > 0

    def execute(self, context):
        scene = context.scene
        n = vessel_work.find(scene)
        vessel_work.changed(scene, layout=True)
        total = len(vessel_work.settings(scene).thrusters)
        if n:
            self.report({"INFO"}, f"Found {n} thruster{'s' if n != 1 else ''} ({total} in the list)")
        else:
            self.report({"WARNING"}, "No new propeller found among the joints: add one with + (pick its joint in "
                                     "4 Motion first)")
        return {"FINISHED"}


class FRESING_OT_vessel_thruster_add(bpy.types.Operator):
    """Adds the joint selected in 4 Motion > Joints as a thruster (its propeller's turn). The kind is read from the
    joint; change it below the list if it is wrong"""

    bl_idname = "fresing.vessel_thruster_add"
    bl_label = "Add thruster"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing if context.scene is not None else None
        return s is not None and 0 <= s.joints_index < len(s.joints) and \
            len(s.vessel_work.thrusters) < core.MAX_THRUSTERS

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        j = s.joints[s.joints_index]
        if j.kind != "ROTATE":
            self.report({"WARNING"}, f"'{j.name}' slides: a propeller turns (pick a rotate joint in 4 Motion)")
            return {"CANCELLED"}
        if any(r.joint == j.name for r in s.vessel_work.thrusters):
            self.report({"INFO"}, f"'{j.name}' is in the list already")
            return {"CANCELLED"}
        vessel_work.add(scene, j)
        vessel_work.changed(scene, layout=True)
        return {"FINISHED"}


class FRESING_OT_vessel_thruster_remove(bpy.types.Operator):
    """Takes the selected thruster off the list (its joints stay; they no longer follow the vessel's setting)"""

    bl_idname = "fresing.vessel_thruster_remove"
    bl_label = "Remove thruster"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        v = context.scene.fresing.vessel_work if context.scene is not None else None
        return v is not None and 0 <= v.thrusters_index < len(v.thrusters)

    def execute(self, context):
        v = context.scene.fresing.vessel_work
        v.thrusters.remove(v.thrusters_index)
        v.thrusters_index = max(0, min(v.thrusters_index, len(v.thrusters) - 1))
        vessel_work.changed(context.scene, layout=True)
        return {"FINISHED"}


CLASSES = (FRESING_OT_vessel_thrusters_find, FRESING_OT_vessel_thruster_add, FRESING_OT_vessel_thruster_remove)
