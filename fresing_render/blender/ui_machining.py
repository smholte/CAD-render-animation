"""Side panel: 4 Motion > Milling (task 0027). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import chips as chips_core
from ..core import machining as core
from . import chips, machining
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
            col.prop(m, "cut_look", text="Cut faces")
            if m.cut_look == "PICK":
                col.prop(m, "cut_material", text="Material")
            if m.workpiece is not None:
                wrap(layout, context, machining.cut_look_text(scene), icon="MATERIAL", inset=0)
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


class FRESING_PT_milling_chips(_Panel, bpy.types.Panel):
    bl_label = "Chips"
    bl_parent_id = "FRESING_PT_milling"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and core.available() and machining.is_set_up(context.scene)

    def draw_header(self, context):
        self.layout.label(icon="PARTICLES")

    def draw_header_preset(self, context):
        m = machining.settings(context.scene)
        header_status(self.layout, {"NONE": "none", "FEW": "few", "REALISTIC": "realistic"}.get(m.chips, ""))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        m = machining.settings(scene)
        col = split_props(layout)
        col.prop(m, "chips", text="Chips")
        if m.chips == "NONE":
            wrap(layout, context, "Pick Few or Realistic: chips fly off the bit while it cuts and pile up on the "
                                  "workpiece, the table and the machine bed", icon="INFO")
            return
        col.prop(m, "chip_material", text="Material")
        fam, _why = chips.family(scene)
        wrap(layout, context, chips.family_text(scene), icon="MATERIAL", inset=0)
        for item, ob in machining.bits(scene):
            t = machining.tool_of(item)
            p = chips_core.preset(fam, chips_core.bit_kind(t.kind, t.radius))
            wrap(layout, context, f"{machining.name_of(ob)}: {p.note or p.label}", icon="MOD_SCREW", inset=0)
        rt = chips.runtime(scene)
        if not m.enabled:
            wrap(layout, context, "Cut material is off: no chips", icon="INFO")
        elif rt.get("error") or machining.runtime(scene).get("chips_error"):
            wrap(layout, context, rt.get("error") or machining.runtime(scene)["chips_error"], icon="ERROR", alert=True)
        elif rt.get("status"):
            wrap(layout, context, rt["status"], icon="INFO")
        from . import air
        if len(air.spans(scene)):
            c = air.settings(scene)
            src = "through the spindle" if c.air_source == "SPINDLE" else "from the nozzle"
            wrap(layout, context, f"Air blast {src}: " + air.core.spans_text(air.spans(scene), scene.render.fps),
                 icon="FORCE_WIND")
        else:
            wrap(layout, context, "No air blast in this animation (4 Motion > CNC machine > Air blast, and the "
                                  "step's 'Blow the part clean')", icon="FORCE_WIND")
        layout.operator("fresing.chips_clear", text="Clear chips", icon="TRASH")
        body = fold(layout, "fr_chips_more", "More")
        if body:
            c = split_props(body)
            c.prop(m, "chip_spindle", text="Spindle turns")
            c.prop(m, "chip_mist", text="Coolant mist")


class FRESING_PT_milling_toolpath(_Panel, bpy.types.Panel):
    """Milling > Make a toolpath (task 0029): the app writes the program that cuts the block into the part."""
    bl_label = "Make a toolpath"
    bl_parent_id = "FRESING_PT_milling"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and core.available()

    def draw_header(self, context):
        self.layout.label(icon="IPO_EASE_IN_OUT")

    def draw_header_preset(self, context):
        from . import toolpath
        scene = context.scene
        rt = toolpath.runtime(scene)
        if rt.get("running"):
            header_status(self.layout, f"{rt.get('progress', 0.0) * 100:.0f}%")
            return
        r = toolpath.result(scene)
        if r and toolpath.step(scene)[1] is not None:
            header_status(self.layout, f"{r.get('moves', 0):,} moves")

    def draw(self, context):
        from ..core import toolpath as tp_core
        from . import toolpath
        layout = self.layout
        scene = context.scene
        tp = toolpath.settings(scene)
        rt = toolpath.runtime(scene)
        why = toolpath.problem(scene)
        r_row, f_row = toolpath.picked(scene)
        if why and not (r_row or f_row):
            steps(layout, context, ["Above: the raw block as workpiece and the finished part (the CAD part it "
                                    "becomes) as finished part",
                                    "4 Motion > CNC machine: the axes, the tool in the spindle, the workpiece and "
                                    "the work zero; and the tools in its tool list",
                                    "Pick a roughing and a finishing tool below and press Make toolpath"])
        m = machining.settings(scene)
        col = layout.column(align=True)
        col.label(text=f"Stock: {machining.name_of(m.workpiece) if m.workpiece else '–'}", icon="MESH_CUBE")
        col.label(text=f"Finished part: {machining.name_of(m.finished) if m.finished else '–'}",
                  icon="MOD_SOLIDIFY")

        layout.separator()
        layout.label(text="Tools", icon="MOD_SCREW")
        col = split_props(layout)
        col.prop(tp, "rough_tool", text="Roughing")
        col.prop(tp, "finish_tool", text="Finishing")
        wrap(layout, context, f"Allowed: {tp_core.KIND_TEXT}", icon="INFO", inset=0)

        layout.separator()
        col = split_props(layout)
        if r_row is not None:
            col.prop(tp, "leave", text="Leave stock")
            col.prop(tp, "step_down", text="Step-down")
            col.prop(tp, "stepover", text="Stepover")
        if f_row is not None:
            col.prop(tp, "scallop", text="Scallop height")
        col.prop(tp, "angle", text="Pass direction")
        col.prop(tp, "detail", text="Detail")
        col.prop(tp, "coolant", text="Coolant")

        body = fold(layout, "fr_toolpath_feeds", "Speeds and feeds")
        if body:
            c = split_props(body)
            c.prop(tp, "material", text="Stock material")
            mat, how = toolpath.material(scene)
            wrap(body, context, f"Speeds for {tp_core.MATERIALS[mat][0].lower()} ({how}); 0 = worked out",
                 icon="INFO", inset=0)
            c = split_props(body)
            if r_row is not None:
                c.prop(tp, "rough_rpm", text="Roughing rpm")
                c.prop(tp, "rough_feed", text="Roughing feed")
            if f_row is not None:
                c.prop(tp, "finish_rpm", text="Finishing rpm")
                c.prop(tp, "finish_feed", text="Finishing feed")

        layout.separator()
        if rt.get("running"):
            row = big_row(layout, MEDIUM)
            row.label(text=f"{rt.get('text', 'Working')} … {rt.get('progress', 0.0) * 100:.0f}%", icon="SORTTIME")
            row.operator("fresing.toolpath_cancel", text="Cancel", icon="CANCEL")
            return
        if why:
            wrap(layout, context, why, icon="ERROR", alert=bool(r_row or f_row))
        row = big_row(layout)
        row.enabled = not why
        row.operator("fresing.toolpath_make", text="Make toolpath", icon="PLAY", depress=not why)
        lines = toolpath.result_lines(scene)
        a, b = toolpath.step(scene)
        if lines and b is not None:
            box = layout.box()
            for k, line in enumerate(lines):
                wrap(box, context, line, icon="CHECKMARK" if k == 0 else "NONE", inset=12)
            res = toolpath.result(scene)
            if res.get("undercut"):
                wrap(box, context, res["undercut"], icon="ERROR", inset=12)
            wrap(box, context, f"Step '{b.name or 'Run G-code program'}' in the animation '{a.name}' (Fit into "
                               f"{b.gcode_fit:g} s: change it in 6 Animation)", icon="SEQUENCE", inset=12)
            box.operator("fresing.toolpath_go_step", text="Show its step", icon="SEQUENCE")


CLASSES = (FRESING_UL_mill_bits, FRESING_PT_milling, FRESING_PT_milling_chips, FRESING_PT_milling_toolpath)
