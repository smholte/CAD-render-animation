"""Operator of 6 Animation > Make a product video (task 0101)."""

from __future__ import annotations

import bpy

from . import product_video


class FRESING_OT_product_video(bpy.types.Operator):
    """Makes the animation 'Product video': title card, one turn round the machine, its motions, a subassembly taken
    apart and put together, close-ups and an end card. Then press Build & play, or add it to the render queue. Every
    step can be changed in the list afterwards. Pressing it again makes the video again"""

    bl_idname = "fresing.product_video"
    bl_label = "Make a product video"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        if product_video.changed(context.scene):
            return context.window_manager.invoke_confirm(
                self, event, title="Make the product video again?",
                message="You changed the steps of the Product video. Making it again replaces them.",
                confirm_text="Replace the steps")
        return self.execute(context)

    def execute(self, context):
        info = product_video.make(context.scene)
        msg = product_video.status(info)
        context.scene.fresing.last_message = msg
        self.report({"INFO"}, msg)
        for area in getattr(context.screen, "areas", []) if context.screen else []:
            area.tag_redraw()
        return {"FINISHED"}


CLASSES = (FRESING_OT_product_video,)
