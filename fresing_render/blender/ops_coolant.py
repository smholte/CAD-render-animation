"""Operators of 4 Motion > CNC machine > Coolant (task 0042): picking the coolant nozzles of the model."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty

from . import build, coolant, gcode, hover
from .ops_gcode import _CncOp
from .ops_machining import clicked_part


def _check_part(op, scene, ob) -> bool:
    c = gcode.settings(scene)
    if ob is c.workpiece or ob is c.tool:
        op.report({"WARNING"}, f"'{gcode.label(ob)}' is the {'workpiece' if ob is c.workpiece else 'tool'}: "
                               "click a nozzle")
        return False
    return True


class FRESING_OT_cnc_coolant_nozzle(_CncOp, bpy.types.Operator):
    """Adds the part you clicked last as a coolant nozzle: the coolant comes out of the end of it nearest the tool
    and squirts at the tool. Add each nozzle of the head this way; check the aim below"""

    bl_idname = "fresing.cnc_coolant_nozzle"
    bl_label = "Use clicked part"

    def execute(self, context):
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the nozzle in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        if not _check_part(self, context.scene, ob):
            return {"CANCELLED"}
        note = coolant.add_nozzle(context.scene, ob)
        self.report({"INFO"}, f"Coolant nozzle: {gcode.label(ob)} ({note})")
        return {"FINISHED"}


class FRESING_OT_cnc_coolant_click(_CncOp, bpy.types.Operator):
    """Click the spot on a part where the coolant comes out: that part becomes a nozzle and squirts from there
    at the tool. Esc cancels"""

    bl_idname = "fresing.cnc_coolant_click"
    bl_label = "Click the nozzle point"

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        c = gcode.settings(context.scene)
        hover.start(context, self, "Click the spot where the coolant comes out.  Esc / right-click: cancel.  "
                                   "Middle mouse / scroll: move the view", point=True,
                    note=lambda ob, name, *_a: f"Coolant nozzle here – {name}",
                    refuse=lambda ob, *_a: "that is the workpiece or the tool, not a nozzle"
                    if ob in (c.workpiece, c.tool) else "")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        c = gcode.settings(context.scene)
        if res is None or res[0].get(build.PROP_KIND) != "part" or res[0] in (c.workpiece, c.tool):
            hover.prompt(context, "Missed: click on the nozzle (not the workpiece or the tool). Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        coolant.add_nozzle(context.scene, ob, loc)
        self.report({"INFO"}, f"Coolant nozzle: {gcode.label(ob)}, squirting at the tool")
        return {"FINISHED"}


class FRESING_OT_cnc_coolant_remove(_CncOp, bpy.types.Operator):
    """Removes the selected nozzle from the list (the part stays in the model)"""

    bl_idname = "fresing.cnc_coolant_remove"
    bl_label = "Remove nozzle"

    @classmethod
    def poll(cls, context):
        s = coolant.settings(context.scene) if hasattr(context.scene, "fresing") else None
        return s is not None and 0 <= s.nozzles_index < len(s.nozzles)

    def execute(self, context):
        s = coolant.settings(context.scene)
        s.nozzles.remove(s.nozzles_index)
        s.nozzles_index = max(0, min(s.nozzles_index, len(s.nozzles) - 1))
        coolant.look_changed(context.scene)
        return {"FINISHED"}


class FRESING_OT_cnc_coolant_aim(_CncOp, bpy.types.Operator):
    """Aims the selected nozzle at the tool's cutting edges (just above its tip)"""

    bl_idname = "fresing.cnc_coolant_aim"
    bl_label = "Aim at the tool"

    flip: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.flip:
            return "Turns the nozzle round: it squirts the other way (when it was read from the wrong end)"
        return " ".join(cls.__doc__.split())

    @classmethod
    def poll(cls, context):
        s = coolant.settings(context.scene) if hasattr(context.scene, "fresing") else None
        return s is not None and 0 <= s.nozzles_index < len(s.nozzles)

    def execute(self, context):
        s = coolant.settings(context.scene)
        if not coolant.aim_nozzle(context.scene, s.nozzles[s.nozzles_index], self.flip):
            self.report({"WARNING"}, "Pick the tool first (4 Motion > CNC machine > Tool)")
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (FRESING_OT_cnc_coolant_nozzle, FRESING_OT_cnc_coolant_click, FRESING_OT_cnc_coolant_remove,
           FRESING_OT_cnc_coolant_aim)
