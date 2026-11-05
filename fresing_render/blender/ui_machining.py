"""Side panel: 4 Motion > Milling (task 0027). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import machining as core
from . import machining
from .ops_machining import MISSING_LIBRARY, clicked_part
from .ui import MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, primary, split_props, steps, wrap


class FRESING_UL_mill_bits(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.obj is None:
            row.label(text="(part gone)", icon="ERROR")
            return
        row.label(text=machining.name_of(item.obj), icon="MOD_SCREW")
        sub = row.row(align=True)
        sub.ui_units_x = 3.4
        sub.label(text=f"Ø{item.diameter * 1000:.1f}" if item.shape != "AUTO" else _short(item))


def _short(item) -> str:
    try:
        t = machining.tool_of(item)
        return f"Ø{t.radius * 2000:.1f}"
    except Exception:
        return ""


class FRESING_PT_milling(_Panel, bpy.types.Panel):
    bl_label = "Milling"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_BOOLEAN")

    def draw_header_preset(self, context):
        m = machining.settings(context.scene)
        n = len(m.bits)
        if not n and m.workpiece is None:
            return
        if not m.enabled:
            header_status(self.layout, "off")
        elif machining.runtime(context.scene).get("error"):
            header_status(self.layout, "problem", icon="ERROR", alert=True)
        else:
            header_status(self.layout, f"{n} bit{'s' if n != 1 else ''}")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        m = machining.settings(scene)
        if not core.available():
            wrap(layout, context, MISSING_LIBRARY, icon="ERROR", alert=True)
            return
        if not m.bits and m.workpiece is None:
            steps(layout, context, ["Click the milling bit in the view, then 'Use as bit'",
                                    "Click the workpiece (the raw block), then 'Use as workpiece'",
                                    "Build an animation in 6 Animation that moves the bit through it: "
                                    "material disappears where the bit cuts"])
        ob = clicked_part(context)
        if ob is not None:
            wrap(layout, context, f"Clicked: {machining.name_of(ob)}", icon="RESTRICT_SELECT_OFF")
        else:
            wrap(layout, context, "Nothing clicked: click a part in the view", icon="RESTRICT_SELECT_ON",
                 alert=not (m.bits and m.workpiece))

        # -- bits
        layout.separator()
        layout.label(text="Bits", icon="MOD_SCREW")
        if m.bits:
            row = layout.row()
            row.template_list("FRESING_UL_mill_bits", "", m, "bits", m, "bits_index",
                              rows=list_rows(len(m.bits), 1, 4))
            row.column(align=True).operator("fresing.mill_remove_bit", text="", icon="REMOVE")
        if not m.bits:
            primary(layout, "fresing.mill_add_bit", "Use as bit", "ADD", MEDIUM)
        else:
            big_row(layout, MEDIUM).operator("fresing.mill_add_bit", text="Use as bit", icon="ADD")
        bit = m.bits[m.bits_index] if 0 <= m.bits_index < len(m.bits) else None
        if bit is not None and bit.obj is not None:
            box = layout.box()
            box.label(text=machining.name_of(bit.obj), icon="MOD_SCREW")
            if bit.detected:
                wrap(box, context, f"Read from the part: {bit.detected}", inset=12)
            col = split_props(box)
            col.prop(bit, "shape", text="Shape")
            if bit.shape != "AUTO":
                col.prop(bit, "diameter", text="Diameter")
                if bit.shape == "BULL":
                    col.prop(bit, "corner", text="Corner radius")
                if bit.shape in ("VEE", "DRILL"):
                    col.prop(bit, "angle", text="Tip angle")
                col.prop(bit, "length", text="Length")
            box.operator("fresing.mill_flip_bit", text="Tip at the other end", icon="ARROW_LEFTRIGHT")

        # -- workpiece
        layout.separator()
        layout.label(text="Workpiece", icon="MESH_CUBE")
        if m.workpiece is not None:
            wrap(layout, context, machining.name_of(m.workpiece), icon="CHECKMARK", inset=0)
        if m.workpiece is None and m.bits:
            primary(layout, "fresing.mill_set_workpiece", "Use as workpiece", "MESH_CUBE", MEDIUM)
        else:
            big_row(layout, MEDIUM).operator("fresing.mill_set_workpiece", text="Use as workpiece",
                                             icon="MESH_CUBE")

        # -- finished part (optional)
        layout.separator()
        layout.label(text="Finished part (optional)", icon="MOD_SOLIDIFY")
        if m.finished is not None:
            row = layout.row(align=True)
            row.label(text=machining.name_of(m.finished), icon="CHECKMARK")
            row.operator("fresing.mill_clear_finished", text="", icon="X")
            wrap(layout, context, "The bits never cut below it (it is hidden: only used as the limit)",
                 inset=0)
        else:
            layout.operator("fresing.mill_set_finished", text="Use as finished part", icon="MOD_SOLIDIFY")

        # -- how it runs
        if m.bits or m.workpiece is not None:
            layout.separator()
            col = split_props(layout)
            col.prop(m, "detail", text="Detail")
            col.prop(m, "enabled", text="Cut material")
            rt = machining.runtime(scene)
            if rt.get("error"):
                wrap(layout, context, rt["error"], icon="ERROR", alert=True)
            elif rt.get("note"):
                wrap(layout, context, rt["note"], icon="INFO")
            if m.enabled and machining.is_set_up(scene) and rt.get("status"):
                wrap(layout, context, rt["status"], icon="INFO")
            elif m.enabled and m.bits and m.workpiece is not None and not scene.fresing.anim_baked:
                wrap(layout, context, "Build an animation in 6 Animation: the bits cut while it plays",
                     icon="INFO")
            row = layout.row(align=True)
            row.operator("fresing.mill_reset", text="Reset workpiece", icon="FILE_REFRESH")
            body = fold(layout, "fr_mill_more", "More")
            if body:
                body.operator("fresing.mill_stop", text="Stop milling", icon="CANCEL")


CLASSES = (FRESING_UL_mill_bits, FRESING_PT_milling)
