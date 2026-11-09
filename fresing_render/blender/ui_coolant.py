"""Side panel: 4 Motion > CNC machine > Coolant (task 0042). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import coolant, gcode
from .ops_machining import clicked_part
from .ui import _has_model, _Panel, fold, header_status, list_rows, split_props, steps, wrap


class FRESING_UL_coolant_nozzles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item.obj is None:
            layout.label(text="part gone", icon="ERROR")
        else:
            layout.label(text=gcode.label(item.obj), icon="MOD_FLUIDSIM")


class FRESING_PT_cnc_coolant(_Panel, bpy.types.Panel):
    """4 Motion > CNC machine > Coolant: flood and mist from nozzles onto the tool, wet parts, wet chips."""
    bl_label = "Coolant"
    bl_parent_id = "FRESING_PT_cnc"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.prop(coolant.settings(context.scene), "enabled", text="")

    def draw_header_preset(self, context):
        s = coolant.settings(context.scene)
        if not s.enabled:
            header_status(self.layout, "off")
        elif coolant.problem(context.scene):
            header_status(self.layout, "not ready", icon="ERROR", alert=True)
        else:
            header_status(self.layout, ("hoses" if s.source == "AUTO" else plural(len(s.nozzles), "nozzle"))
                          + (", draft" if s.draft else ""))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = coolant.settings(scene)
        if not s.enabled:
            steps(layout, context, ["Tick Coolant in this panel's title",
                                    "Pick where it comes from: the app's hoses (Automatic) or your nozzle parts",
                                    "In 6 Animation, each Run G-code program step says when it flows (from the "
                                    "program's M8 / M7 / M9, always, or off); press Build & play"])
            return
        why = coolant.problem(scene)
        if why:
            wrap(layout, context, why, icon="ERROR", alert=True)
        # -- where from
        layout.row(align=True).prop(s, "source", expand=True)
        if s.source == "AUTO":
            col = split_props(layout)
            col.prop(s, "auto_count", text="Hoses")
            col.prop(s, "auto_turn", text="Turn hoses")
            layout.prop(s, "show_hoses", text="Show hoses")
            wrap(layout, context, "The hoses sit on a ring round the spindle and bend to the tool in the spindle "
                                  "(also after each tool change)", icon="INFO", inset=12)
        else:
            ob = clicked_part(context)
            wrap(layout, context, f"Clicked: {gcode.label(ob)}" if ob is not None else
                 "Nothing clicked: click a nozzle part in the view",
                 icon="RESTRICT_SELECT_OFF" if ob is not None else "RESTRICT_SELECT_ON")
            row = layout.row(align=True)
            row.operator("fresing.cnc_coolant_nozzle", text="Use clicked part", icon="ADD")
            row.operator("fresing.cnc_coolant_click", text="Click point", icon="EYEDROPPER")
            row = layout.row()
            row.template_list("FRESING_UL_coolant_nozzles", "", s, "nozzles", s, "nozzles_index",
                              rows=list_rows(len(s.nozzles), 2, 6))
            col = row.column(align=True)
            col.operator("fresing.cnc_coolant_remove", text="", icon="REMOVE")
            if 0 <= s.nozzles_index < len(s.nozzles):
                it = s.nozzles[s.nozzles_index]
                row = layout.row(align=True)
                row.operator("fresing.cnc_coolant_aim", text="Aim at the tool", icon="PIVOT_CURSOR")
                row.operator("fresing.cnc_coolant_aim", text="", icon="ARROW_LEFTRIGHT").flip = True
                fb = fold(layout, "fr_coolant_aim", "Nozzle tip and aim", icon="ORIENTATION_GIMBAL")
                if fb:
                    fb.prop(it, "tip", text="Tip")
                    fb.prop(it, "dir", text="")
        # -- the look
        col = split_props(layout)
        col.prop(s, "liquid", text="Liquid")
        col.prop(s, "flow", text="Flow", slider=True)
        layout.prop(s, "wet_parts", text="Wet sheen on block, table and vise")
        if s.wet_parts:
            split_props(layout).prop(s, "dry_time", text="Dries in")
            n = len(coolant.wet_parts(scene))
            if n:
                wrap(layout, context, f"{plural(n, 'part')} get wet (marked at Build & play)", icon="CHECKMARK",
                     inset=12)
        layout.prop(s, "draft", text="Draft (quick view: no splash, no drops)")
        # -- the codes
        body = fold(layout, "fr_coolant_codes", f"Codes: M{s.flood_code} flood, M{s.mist_code} mist, "
                                                f"M{s.off_code} off", icon="FILE_SCRIPT")
        if body:
            col = split_props(body)
            col.prop(s, "flood_code", text="Flood code (M)")
            col.prop(s, "mist_code", text="Mist code (M)")
            col.prop(s, "off_code", text="Off code (M)")
            cnc = gcode.settings(scene)
            if s.mist_code and s.mist_code == cnc.air_on_code:
                wrap(body, context, f"M{s.mist_code} also switches the air blast on (mist is air with drops). Give "
                                    "Air blast another code, or set Mist code to 0, to keep them apart",
                     icon="FORCE_WIND", inset=12)
            wrap(body, context, "M9 always stops flood and mist (and the air, as on LinuxCNC)", icon="INFO",
                 inset=12)


def draw_step(context, box, scene, b, info) -> None:
    """The coolant line of a Run G-code program step (6 Animation)."""
    if not coolant.is_on(scene):
        return
    split_props(box).prop(b, "gcode_coolant", text="Coolant")
    if info.get("coolant"):
        wrap(box, context, info["coolant"], icon="MOD_FLUIDSIM", inset=12)


CLASSES = (FRESING_UL_coolant_nozzles, FRESING_PT_cnc_coolant)
