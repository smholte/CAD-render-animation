"""Operators for milling (4 Motion > Milling, task 0027)."""

from __future__ import annotations

import bpy

from ..core import machining as core
from . import build, machining

MISSING_LIBRARY = ("Milling needs the Manifold library, which comes with the installer: install this "
                   "version again with Install.bat")


def clicked_part(context):
    """The part clicked last (the active object), when it is a part with a shape."""
    ob = context.view_layer.objects.active if context.view_layer else None
    if ob is None or ob.get(build.PROP_KIND) != "part" or ob.type != "MESH" or not ob.select_get():
        return None
    return ob


def _role(scene, ob) -> str:
    s = machining.settings(scene)
    if ob is None:
        return ""
    if ob is s.workpiece:
        return "the workpiece"
    if ob is s.finished:
        return "the finished part"
    if any(b.obj is ob for b in s.bits):
        return "a bit"
    return ""


class _MillOp:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and hasattr(context.scene, "fresing")

    def need_library(self) -> bool:
        if not core.available():
            self.report({"ERROR"}, MISSING_LIBRARY)
            return False
        return True


class FRESING_OT_mill_add_bit(_MillOp, bpy.types.Operator):
    """Makes the part you clicked last a milling bit. Its shape is read from the part (flat, ball,
    corner radius, V-bit, drill); check it below the list. Click the bit itself, not its holder"""

    bl_idname = "fresing.mill_add_bit"
    bl_label = "Use as bit"

    def execute(self, context):
        if not self.need_library():
            return {"CANCELLED"}
        scene = context.scene
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the milling bit in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        role = _role(scene, ob)
        if role and role != "a bit":
            self.report({"WARNING"}, f"'{machining.name_of(ob)}' is {role} already")
            return {"CANCELLED"}
        try:
            item = machining.add_bit(scene, ob)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Bit: {machining.name_of(ob)} – {item.detected}")
        return {"FINISHED"}


class FRESING_OT_mill_remove_bit(_MillOp, bpy.types.Operator):
    """Takes the selected bit out of the list: it does not cut any more (the part itself stays)"""

    bl_idname = "fresing.mill_remove_bit"
    bl_label = "Remove bit"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and len(machining.settings(context.scene).bits) > 0

    def execute(self, context):
        s = machining.settings(context.scene)
        machining.remove_bit(context.scene, s.bits_index)
        return {"FINISHED"}


class FRESING_OT_mill_flip_bit(_MillOp, bpy.types.Operator):
    """The bit's tip is at the wrong end: use the other end of the part as its tip"""

    bl_idname = "fresing.mill_flip_bit"
    bl_label = "Tip at the other end"

    @classmethod
    def poll(cls, context):
        s = machining.settings(context.scene) if super().poll(context) else None
        return s is not None and 0 <= s.bits_index < len(s.bits) and s.bits[s.bits_index].obj is not None

    def execute(self, context):
        s = machining.settings(context.scene)
        item = s.bits[s.bits_index]
        try:
            machining.flip_bit(context.scene, item)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, item.detected)
        return {"FINISHED"}


class FRESING_OT_mill_set_workpiece(_MillOp, bpy.types.Operator):
    """Makes the part you clicked last the workpiece (the raw block or bar the bits cut into).
    From then on material disappears from it wherever a bit moves through it in the animation"""

    bl_idname = "fresing.mill_set_workpiece"
    bl_label = "Use as workpiece"

    def execute(self, context):
        if not self.need_library():
            return {"CANCELLED"}
        scene = context.scene
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the workpiece in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        role = _role(scene, ob)
        if role and role != "the workpiece":
            self.report({"WARNING"}, f"'{machining.name_of(ob)}' is {role} already")
            return {"CANCELLED"}
        machining.set_workpiece(scene, ob)
        machining.refresh(scene)
        self.report({"INFO"}, f"Workpiece: {machining.name_of(ob)}")
        return {"FINISHED"}


class FRESING_OT_mill_set_finished(_MillOp, bpy.types.Operator):
    """Makes the part you clicked last the finished part: the CAD model of the part as it should come
    off the machine. The bits never cut below its surface, so the result is exactly the CAD part even
    if the motion goes a little too deep. It is hidden: it is only used as the limit"""

    bl_idname = "fresing.mill_set_finished"
    bl_label = "Use as finished part"

    def execute(self, context):
        scene = context.scene
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the finished part in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        role = _role(scene, ob)
        if role and role != "the finished part":
            self.report({"WARNING"}, f"'{machining.name_of(ob)}' is {role} already")
            return {"CANCELLED"}
        machining.set_finished(scene, ob)
        self.report({"INFO"}, f"Finished part: {machining.name_of(ob)} (hidden; shown again when you clear it)")
        return {"FINISHED"}


class FRESING_OT_mill_clear_finished(_MillOp, bpy.types.Operator):
    """Stops using the finished part as a limit: the bits cut wherever they go. The part is shown again"""

    bl_idname = "fresing.mill_clear_finished"
    bl_label = "Clear finished part"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and machining.settings(context.scene).finished is not None

    def execute(self, context):
        machining.set_finished(context.scene, None)
        return {"FINISHED"}


class FRESING_OT_mill_reset(_MillOp, bpy.types.Operator):
    """Starts again from the uncut workpiece: reads the bits' motion from the animation again and cuts
    up to the current frame. Use it when the cut does not follow a change you made"""

    bl_idname = "fresing.mill_reset"
    bl_label = "Reset workpiece"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and machining.is_set_up(context.scene)

    def execute(self, context):
        if not self.need_library():
            return {"CANCELLED"}
        scene = context.scene
        machining.runtime(scene).clear()
        machining.settings(scene).path_sig = ""
        if machining.update_if_needed(scene):
            self.report({"INFO"}, machining.status(scene))
        return {"FINISHED"}


class FRESING_OT_mill_stop(_MillOp, bpy.types.Operator):
    """Removes the milling set-up: the workpiece is whole again, the finished part is shown again. The
    parts themselves stay where they are"""

    bl_idname = "fresing.mill_stop"
    bl_label = "Stop milling"

    @classmethod
    def poll(cls, context):
        s = machining.settings(context.scene) if super().poll(context) else None
        return s is not None and (s.workpiece is not None or len(s.bits) > 0 or s.finished is not None)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        machining.stop(context.scene)
        self.report({"INFO"}, "Milling removed: the workpiece is whole again")
        return {"FINISHED"}


CLASSES = (FRESING_OT_mill_add_bit, FRESING_OT_mill_remove_bit, FRESING_OT_mill_flip_bit,
           FRESING_OT_mill_set_workpiece, FRESING_OT_mill_set_finished, FRESING_OT_mill_clear_finished,
           FRESING_OT_mill_reset, FRESING_OT_mill_stop)
