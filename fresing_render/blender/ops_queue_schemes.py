"""7 Render queue > Every paint scheme (task 0074): the same animation or picture once per paint scheme."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty

from ..core.words import plural
from . import animation, queue


class FRESING_OT_queue_schemes(bpy.types.Operator):
    """Adds this render to the queue once for every ticked paint scheme, each file named after its scheme. The
    project keeps its own colours: the scheme is only set in the background render. Then Start queue, or Start
    later for overnight"""

    bl_idname = "fresing.queue_schemes"
    bl_label = "Queue in every paint scheme"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(items=[("ANIMATION", "Animation", "The animation selected in 6 Animation"),
                              ("STILL", "Current view", "A picture of the view as it is now")],
                       default="ANIMATION", options={"SKIP_SAVE"})
    which: EnumProperty(items=[("TICKED", "Ticked schemes", "Only the ticked paint schemes"),
                               ("ALL", "Every scheme", "Every paint scheme, ticked or not")],
                        default="TICKED", options={"SKIP_SAVE"})
    name: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.kind == "STILL":
            return ("Adds a picture of the view as it is now to the queue once for every ticked paint scheme, each "
                    "file named after its scheme. Your colours stay as they are. Then Start queue")
        return ("Adds the animation selected in 6 Animation to the queue once for every ticked paint scheme, each "
                "video named after its scheme. Your colours stay as they are. Then Start queue, or Start later "
                "for overnight")

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        names = queue.schemes_to_queue(scene, self.which)
        if not names:
            self.report({"WARNING"}, "No paint scheme ticked: save or tick one in the list first")
            return {"CANCELLED"}
        if self.kind == "ANIMATION":
            a = s.animations.get(self.name) if self.name else animation.active(scene)
            if a is None:
                self.report({"WARNING"}, "Make an animation in 6 Animation first")
                return {"CANCELLED"}
            queue.add_in_schemes(scene, "ANIMATION", names, animation=a.name)
            what = f"'{a.name}'"
        else:
            before = len(s.queue)                # the current view, saved as a hidden scene, as "Current view" does
            if bpy.ops.fresing.queue_add(kind="STILL") != {"FINISHED"} or len(s.queue) != before + 1:
                return {"CANCELLED"}
            first = s.queue[-1]
            shot = first.shot
            first.scheme = names[0]
            queue.relabel(first)
            queue.add_in_schemes(scene, "STILL", names[1:], shot=shot)
            what = "the current view"
        msg = f"Queued {what} in {plural(len(names), 'paint scheme')}. Start queue (or Start later) renders them"
        s.last_message = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class FRESING_OT_queue_schemes_tick(bpy.types.Operator):
    """Ticks every paint scheme in the list, or none"""

    bl_idname = "fresing.queue_schemes_tick"
    bl_label = "Tick all or none"
    bl_options = {"REGISTER", "UNDO"}

    on: bpy.props.BoolProperty(default=True, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return ("Ticks every paint scheme: the buttons below render in all of them" if properties.on
                else "Unticks every paint scheme, so you can tick just the few you want")

    def execute(self, context):
        for sch in context.scene.fresing.schemes:
            sch.queue_on = self.on
        return {"FINISHED"}


CLASSES = (FRESING_OT_queue_schemes, FRESING_OT_queue_schemes_tick)
