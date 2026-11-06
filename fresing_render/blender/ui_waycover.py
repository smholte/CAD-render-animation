"""Side panel: 4 Motion > Way covers (task 0034). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import waycover as core
from . import waycover
from .ui import MEDIUM, _has_model, _Panel, big_row, header_status, list_rows, primary, split_props, steps, wrap


class FRESING_UL_waycover_sections(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = context.scene
        row = layout.row(align=True)
        made = waycover.is_made(scene, item)
        parts = waycover.parts_of(scene, item)
        row.prop(item, "name", text="", emboss=False, icon="CHECKMARK" if made else "DOT")
        sub = row.row(align=True)
        sub.ui_units_x = 5.2
        c = waycover.settings(scene)
        n = len(c.sections)
        share = waycover.shares(scene)[index] if index < n else 0.0
        mm = abs(share) * c.total * 1000.0
        word = "part" if len(parts) == 1 else "parts"
        sub.label(text=f"{len(parts)} {word} · {mm:g} mm")


class FRESING_PT_waycover(_Panel, bpy.types.Panel):
    bl_label = "Way covers"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_ARRAY")

    def draw_header_preset(self, context):
        n, made = waycover.state_counts(context.scene)
        if n:
            header_status(self.layout, f"{n} section{'s' if n != 1 else ''}",
                          icon="NONE" if made == n else "ERROR", alert=made < n)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        c = waycover.settings(scene)
        if not c.axis and not c.sections:
            steps(layout, context, ["Pick the slide joint the covers follow (the machine axis)",
                                    "Click the parts of one cover section, then 'Add section' – "
                                    "from the fixed end to the moving end",
                                    "Check the total length of movement, then 'Make it'"])

        # -- 1 axis
        layout.label(text="1  Axis", icon="DRIVER")
        row = layout.row(align=True)
        row.prop_search(c, "axis", scene.fresing, "joints", text="", icon="DRIVER")
        problem = waycover.axis_problem(scene) if c.axis else ""
        if problem:
            wrap(layout, context, problem, icon="ERROR", alert=True)
        elif not c.axis:
            layout.operator("fresing.waycover_axis_from_selection", icon="ADD")

        # -- 2 sections
        layout.separator()
        layout.label(text="2  Sections (fixed end first)", icon="MOD_ARRAY")
        if c.sections:
            row = layout.row()
            row.template_list("FRESING_UL_waycover_sections", "", c, "sections", c, "sections_index",
                              rows=list_rows(len(c.sections), 2, 7))
            col = row.column(align=True)
            col.operator("fresing.waycover_remove", text="", icon="REMOVE")
            col.operator("fresing.waycover_move", text="", icon="TRIA_UP").direction = -1
            col.operator("fresing.waycover_move", text="", icon="TRIA_DOWN").direction = 1
            layout.operator("fresing.waycover_select", icon="RESTRICT_SELECT_OFF")
        big_row(layout, MEDIUM).operator("fresing.waycover_add", text="Add section", icon="ADD")

        # -- 3 travel
        layout.separator()
        layout.label(text="3  Travel", icon="ARROW_LEFTRIGHT")
        col = split_props(layout)
        col.prop(c, "total", text="Total movement")
        col.prop(c, "flip", text="Flip direction")
        col.prop(c, "housing_counts", text="Housing counts")
        layout.operator("fresing.waycover_read_total", icon="IMPORT")
        if c.sections:
            wrap(layout, context, core.summary(len(c.sections), c.total * 1000.0, c.housing_counts), icon="INFO")

        # -- 4 make
        layout.separator()
        n, made = waycover.state_counts(scene)
        label = "Make it" if not made else ("Make it (new sections)" if made < n else "Make it again")
        if c.sections and made < n:
            primary(layout, "fresing.waycover_make", label, "CHECKMARK", MEDIUM)
        else:
            big_row(layout, MEDIUM).operator("fresing.waycover_make", text=label, icon="CHECKMARK")
        if n and made == n and not problem:
            wrap(layout, context, waycover.status(scene), icon="CHECKMARK")
        if c.sections:
            layout.operator("fresing.waycover_remove_all", icon="TRASH")


CLASSES = (FRESING_UL_waycover_sections, FRESING_PT_waycover)
