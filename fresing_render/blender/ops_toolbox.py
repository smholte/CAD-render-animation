"""Operators of the Toolbox inbox (task 0217): Bake now / Import now, Not now, and the status-bar line the inbox's
timer reports through."""

from __future__ import annotations

import bpy
from bpy.props import StringProperty

from . import toolbox_inbox


class FRESING_OT_toolbox_start(bpy.types.Operator):
    """Starts the job another tool sent: a house from House Planner is imported into a scene of its own, baked with
    its own settings and sent back to House Planner by itself; your project does not change. Progress and Cancel show
    below while it runs"""

    bl_idname = "fresing.toolbox_start"
    bl_label = "Bake now"
    bl_options = {"REGISTER"}

    job: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        ib = toolbox_inbox.inbox()
        j = ib.jobs.get(properties.job) if ib else None
        if j is not None and j.action == "import-step":
            return ("Imports the STEP file another tool sent into this project, the same as File > Import > STEP. "
                    "A copy of the file is kept in Documents > Fresing Render > From the Toolbox")
        return cls.__doc__.replace("\n    ", " ")

    @classmethod
    def poll(cls, context):
        return toolbox_inbox.running() is None

    def execute(self, context):
        why = toolbox_inbox.start(context, self.job)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        toolbox_inbox.redraw()
        return {"FINISHED"}


class FRESING_OT_toolbox_not_now(bpy.types.Operator):
    """Turns the job down: the tool that sent it reads "You said not now in Fresing Render" and can send it again
    later. Nothing is imported"""

    bl_idname = "fresing.toolbox_not_now"
    bl_label = "Not now"
    bl_options = {"REGISTER"}

    job: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        toolbox_inbox.not_now(self.job)
        toolbox_inbox.redraw()
        return {"FINISHED"}


class FRESING_OT_toolbox_cancel(bpy.types.Operator):
    """Stops the house bake for House Planner. Nothing is sent back; House Planner reads "Cancelled in Fresing
    Render". Your project does not change"""

    bl_idname = "fresing.toolbox_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        toolbox_inbox.cancel()
        return {"FINISHED"}


class FRESING_OT_toolbox_report(bpy.types.Operator):
    """Shows a line about the Toolbox inbox in the status bar"""

    bl_idname = "fresing.toolbox_report"
    bl_label = "Toolbox"
    bl_options = {"INTERNAL"}

    text: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        self.report({"INFO"}, self.text)
        return {"FINISHED"}


CLASSES = (FRESING_OT_toolbox_start, FRESING_OT_toolbox_not_now, FRESING_OT_toolbox_cancel, FRESING_OT_toolbox_report)
