"""Operators of 5 Scene & Render > Weather & time (task 0109): work lights."""

from __future__ import annotations

import bpy

from . import build


def _part(context):
    ob = context.active_object
    if ob is None:
        return None
    if ob.type == "MESH" and ob.get(build.PROP_UID):
        return ob
    return None


class FRESING_OT_work_light_add(bpy.types.Operator):
    """Makes the selected part a lamp: a spot or a flood light shines from it, moves with it and stays through a
    model update. Click the lamp part in the view first; set its colour and power below"""

    bl_idname = "fresing.work_light_add"
    bl_label = "Make a work light"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        name="Kind", default="SPOT", description="A spot (a narrow beam) or a flood light (a wide, soft one)",
        items=[("SPOT", "Spot", "A narrow beam, like a searchlight or a work spot"),
               ("FLOOD", "Flood", "A wide, soft light, like a floodlight panel")])

    @classmethod
    def description(cls, context, props):
        if props is not None and props.kind == "FLOOD":
            return ("Makes the selected part a flood light: a wide, soft light shines from it, moves with it and stays "
                    "through a model update. Click the lamp part in the view first")
        return ("Makes the selected part a spot light: a narrow beam shines from it, moves with it and stays through "
                "a model update. Click the lamp part in the view first")

    @classmethod
    def poll(cls, context):
        return _part(context) is not None

    def execute(self, context):
        from . import weather_sky
        part = _part(context)
        if part is None:
            self.report({"WARNING"}, "Click a part (the lamp) in the view first")
            return {"CANCELLED"}
        ob = weather_sky.add_work_light(context.scene, part, kind=self.kind)
        self.report({"INFO"}, f"'{part.get(build.PROP_NAME) or part.name}' is now a work light ({ob.name})")
        return {"FINISHED"}


class FRESING_OT_work_light_remove(bpy.types.Operator):
    """Takes this work light away (the part itself stays)"""

    bl_idname = "fresing.work_light_remove"
    bl_label = "Remove the work light"
    bl_options = {"REGISTER", "UNDO"}

    light: bpy.props.StringProperty(name="Light", description="The work light to take away")

    def execute(self, context):
        from . import weather_sky
        ob = bpy.data.objects.get(self.light)
        if ob is None:
            return {"CANCELLED"}
        weather_sky.remove_work_light(context.scene, ob)
        return {"FINISHED"}


CLASSES = (FRESING_OT_work_light_add, FRESING_OT_work_light_remove)
