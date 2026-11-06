"""Side panel: 4 Motion > CNC machine, and the "Run G-code program" step in 6 Animation (task 0026).
Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import gcode
from .ops_machining import clicked_part
from .ui import MEDIUM, _has_model, _Panel, fold, header_status, list_rows, primary, split_props, steps, wrap


class FRESING_UL_cnc_tools(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.ui_units_x = 2.4
        sub.prop(item, "number", text="T", emboss=False)
        if item.obj is not None:
            row.label(text=gcode.label(item.obj), icon="MOD_SCREW")
        else:
            row.label(text=f"Ø{item.diameter * 1000:.1f} {item.kind.lower()} (drawn)", icon="MESH_CYLINDER")


class FRESING_PT_cnc(_Panel, bpy.types.Panel):
    bl_label = "CNC machine"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="FILE_SCRIPT")

    def draw_header_preset(self, context):
        cnc = gcode.settings(context.scene)
        if not (cnc.x_joint or cnc.y_joint or cnc.z_joint or cnc.tool or cnc.workpiece):
            return
        if gcode.problem(context.scene):
            header_status(self.layout, "not ready", icon="ERROR", alert=True)
        else:
            header_status(self.layout, "ready")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        cnc = gcode.settings(scene)
        why = gcode.problem(scene)
        if why:
            steps(layout, context, ["Make slide joints for X, Y and Z (and a rotate joint with Motor ticked for "
                                    "the spindle) above",
                                    "Find the axes (or pick them below)",
                                    "Click the tool in the spindle, press Tool; click the workpiece, press "
                                    "Workpiece",
                                    "Pick the work zero, as in your CAM set-up",
                                    "In 6 Animation add the step 'Run G-code program' and pick the program file"])
        primary(layout, "fresing.cnc_find_axes", "Find the axes", "VIEWZOOM", MEDIUM)

        # -- axes
        box = layout.box()
        row = box.row(align=True)
        row.prop_search(cnc, "x_joint", s, "joints", text="X", icon="CON_LOCLIKE")
        row.prop(cnc, "x_reverse", text="", icon="ARROW_LEFTRIGHT", toggle=True)
        row = box.row(align=True)
        row.prop_search(cnc, "y_joint", s, "joints", text="Y", icon="CON_LOCLIKE")
        row.prop(cnc, "y_reverse", text="", icon="ARROW_LEFTRIGHT", toggle=True)
        row = box.row(align=True)
        row.prop_search(cnc, "z_joint", s, "joints", text="Z", icon="CON_LOCLIKE")
        row.prop(cnc, "z_reverse", text="", icon="ARROW_LEFTRIGHT", toggle=True)
        box.prop_search(cnc, "spindle_joint", s, "joints", text="Spindle", icon="FORCE_VORTEX")

        # -- tool and workpiece
        ob = clicked_part(context)
        if ob is not None:
            wrap(layout, context, f"Clicked: {gcode.label(ob)}", icon="RESTRICT_SELECT_OFF")
        else:
            wrap(layout, context, "Nothing clicked: click a part in the view", icon="RESTRICT_SELECT_ON")
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.ui_units_x = 5.4
        sub.operator("fresing.cnc_use_tool", text="Tool", icon="RESTRICT_SELECT_OFF")
        row.label(text=gcode.label(cnc.tool) if cnc.tool else "not picked yet",
                  icon="CHECKMARK" if cnc.tool else "BLANK1")
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.ui_units_x = 5.4
        sub.operator("fresing.cnc_use_workpiece", text="Workpiece", icon="RESTRICT_SELECT_OFF")
        row.label(text=gcode.label(cnc.workpiece) if cnc.workpiece else "not picked yet",
                  icon="CHECKMARK" if cnc.workpiece else "BLANK1")

        # -- work zero
        col = split_props(layout)
        col.prop(cnc, "zero_mode", text="Work zero")
        if cnc.zero_mode == "POINT":
            layout.operator("fresing.cnc_zero_click", text="Click the zero point", icon="EYEDROPPER")
        if why:
            wrap(layout, context, why, icon="ERROR", alert=True)
        else:
            try:
                m = gcode.Machine(scene)
                for line in m.describe_axes():
                    wrap(layout, context, line, icon="CHECKMARK", inset=12)
                wrap(layout, context, "The work zero shows as arrows on the workpiece ('FR work zero')",
                     icon="EMPTY_ARROWS", inset=12)
            except gcode.SetupError as exc:
                wrap(layout, context, str(exc), icon="ERROR", alert=True)

        body = fold(layout, "fr_cnc_machine", "Machine: speeds, zero, shift", icon="PREFERENCES")
        if body:
            wrap(body, context, "Rapid speeds (G0), mm per minute:", icon="FF", inset=12)
            col = split_props(body)
            col.prop(cnc, "rapid_x", text="X rapid")
            col.prop(cnc, "rapid_y", text="Y rapid")
            col.prop(cnc, "rapid_z", text="Z rapid")
            col.prop(cnc, "zero_shift", text="Shift zero")
            wrap(body, context, "Machine zero (G53, G28): " + ("set to a position of the axes" if cnc.home_set
                                                              else "the CAD position"), icon="HOME", inset=12)
            row = body.row(align=True)
            row.operator("fresing.cnc_home", text="Axes now", icon="HOME")
            row.operator("fresing.cnc_home", text="CAD position").clear = True

        body = fold(layout, "fr_cnc_tools", f"Tools for tool changes ({len(cnc.tools)})", icon="TOOL_SETTINGS")
        if body:
            wrap(body, context, "Only needed when the program changes tools (M6). A tool without a part is drawn "
                                "from its sizes", icon="INFO", inset=12)
            body.operator("fresing.cnc_tools_from_program", text="Tools from the program", icon="IMPORT")
            row = body.row()
            row.template_list("FRESING_UL_cnc_tools", "", cnc, "tools", cnc, "tools_index",
                              rows=list_rows(len(cnc.tools), 2, 6))
            col = row.column(align=True)
            col.operator("fresing.cnc_tool_add", text="", icon="ADD")
            col.operator("fresing.cnc_tool_remove", text="", icon="REMOVE")
            if 0 <= cnc.tools_index < len(cnc.tools):
                tl = cnc.tools[cnc.tools_index]
                box = body.box()
                row = box.row(align=True)
                row.operator("fresing.cnc_tool_part", text="Use clicked part", icon="RESTRICT_SELECT_OFF")
                if tl.obj is not None:
                    row.operator("fresing.cnc_tool_part", text="", icon="X").clear = True
                if tl.obj is None:
                    col = split_props(box)
                    col.prop(tl, "kind", text="Shape")
                    col.prop(tl, "diameter", text="Diameter")
                    col.prop(tl, "length", text="Length")
                    if tl.kind == "BULL":
                        col.prop(tl, "corner", text="Corner radius")
                    if tl.kind in ("VEE", "DRILL"):
                        col.prop(tl, "angle", text="Tip angle")
                    if tl.source and tl.source != "typed":
                        wrap(box, context, f"Sizes from the {tl.source}", icon="INFO", inset=12)
            body.prop(cnc, "tool_table", text="Tool table")


def draw_step(context, box, scene, anim, b) -> None:
    """The settings of a Run G-code program step (6 Animation)."""
    s = scene.fresing
    box.prop(b, "gcode_file", text="")
    why = gcode.problem(scene)
    if why:
        wrap(box, context, f"CNC machine: {why} (4 Motion > CNC machine)", icon="ERROR", alert=True, inset=12)
    if not b.gcode_file:
        wrap(box, context, "Pick the program your CAM wrote for the machine (LinuxCNC: .ngc)", icon="INFO", inset=12)
        return
    info = gcode.info(scene, b)
    if info.get("error"):
        wrap(box, context, info["error"], icon="ERROR", alert=True, inset=12)
        box.operator("fresing.gcode_reload", text="Read again", icon="FILE_REFRESH")
        return
    text = (f"{plural(info['lines'], 'line')}, {plural(info['moves'], 'move')}: "
            f"{gcode.fmt_time(info['machine_s'])} on the machine")
    if info["tools"]:
        text += f", {plural(len(info['tools']), 'tool')} (" + ", ".join(f"T{n}" for n in info["tools"][:6]) + ")"
    wrap(box, context, text, icon="FILE_SCRIPT", inset=12)
    if info.get("note"):
        wrap(box, context, info["note"], icon="INFO", inset=12)
    probs = info.get("problems", [])
    if probs:
        wrap(box, context, f"Not shown: {probs[0]}", icon="ERROR", inset=12)
        if len(probs) > 1:
            wrap(box, context, f"… and {plural(len(probs) - 1, 'more thing')} (Details)", inset=12)
    row = box.row(align=True)
    row.operator("fresing.gcode_report", text="Details", icon="TEXT")
    row.operator("fresing.gcode_reload", text="Read again", icon="FILE_REFRESH")

    box.row(align=True).prop(b, "gcode_speed", expand=True)
    col = split_props(box)
    if b.gcode_speed == "FASTER":
        col.prop(b, "gcode_factor", text="Times faster")
    elif b.gcode_speed == "FIT":
        col.prop(b, "gcode_fit", text="Seconds")
    col.prop(b, "gcode_rapid", text="Rapids faster")
    wrap(box, context, f"In the video: {gcode.fmt_time(info['video_s'])}", icon="TIME", inset=12)

    body = fold(box, "fr_gcode_more", "Lines, tool changes, spindle, toolpath", icon="PREFERENCES")
    if body:
        col = split_props(body)
        col.prop(b, "gcode_from", text="From line")
        col.prop(b, "gcode_to", text="To line")
        col.prop_search(b, "gcode_atc", s, "animations", text="Tool changer", icon="RENDER_ANIMATION")
        if b.gcode_atc:
            col.prop(b, "gcode_atc_swap", text="Swap at (s)")
        else:
            col.prop(b, "gcode_tc_time", text="Tool change (s)")
        col.prop(b, "gcode_spindle", text="Spindle")
        col.prop(b, "gcode_path", text="Show toolpath")
        if b.gcode_path:
            col.prop(b, "gcode_path_render", text="Toolpath in renders")
        row = body.row(align=True)
        row.operator("fresing.gcode_toolpath", text="Show toolpath now", icon="CURVE_PATH")
        if gcode.path_object() is not None:
            row.operator("fresing.gcode_toolpath", text="", icon="X").remove = True
        body.operator("fresing.gcode_go_line", text="Go to line …", icon="NEXT_KEYFRAME")


CLASSES = (FRESING_UL_cnc_tools, FRESING_PT_cnc)
