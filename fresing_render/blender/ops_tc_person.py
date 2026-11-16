"""Operators of the operator at a manual tool change (task 0156): show or remove the two spots the owner moves."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty

from . import tc_person


class FRESING_OT_operator_spots(bpy.types.Operator):
    """Shows two markers you can move: the arrow where the operator stands at the machine and the circle it walks in
    from. Move them with G, then build the animation again. The X takes them away: the app picks the spots again"""
    bl_idname = "fresing.operator_spots"
    bl_label = "Show the spots"
    bl_options = {"REGISTER", "UNDO"}

    remove: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.remove:
            return ("Takes the two markers away: the app picks the operator's stand spot and start spot again at the "
                    "next Build")
        return " ".join(cls.__doc__.split())

    def execute(self, context):
        scene = context.scene
        if self.remove:
            tc_person.remove_spots(scene)
            self.report({"INFO"}, "The operator's spots are picked by the app again (build the animation)")
            return {"FINISHED"}
        stand, start = tc_person.show_spots(scene)
        if not tc_person.auto_spots(scene):
            self.report({"WARNING"}, "Build the animation once first: the markers are at the world's centre now")
        else:
            self.report({"INFO"}, "Move the arrow (where the operator stands) and the circle (where it comes from), "
                                  "then build the animation again")
        for ob in context.selected_objects:
            ob.select_set(False)
        stand.select_set(True)
        context.view_layer.objects.active = stand
        return {"FINISHED"}


CLASSES = (FRESING_OT_operator_spots,)
