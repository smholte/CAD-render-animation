"""Side panel: 4 Motion > Way covers (task 0034). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import waycover as core
from ..core.words import plural
from . import waycover
from .ui import _has_model, _Panel, big, gap, header_status, list_rows, missing, split_props, steps, wrap


class FRESING_UL_waycovers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = context.scene
        row = layout.split(factor=0.55, align=True)
        n, made = waycover.state_counts(scene, item)
        row.prop(item, "name", text="", emboss=False, icon="CHECKMARK" if n and made == n else "MOD_ARRAY")
        row.label(text=plural(n, "section") if item.axis else "no axis yet")


class FRESING_UL_waycover_sections(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = context.scene
        row = layout.split(factor=0.62, align=True)
        made = waycover.is_made(scene, item)
        parts = waycover.parts_of(scene, item)
        row.prop(item, "name", text="", emboss=False,
                 icon="PINNED" if item.carriage else ("CHECKMARK" if made else "DOT"))
        c = data
        n = len(c.sections)
        share = waycover.shares(scene, c)[index] if index < n else 0.0
        mm = abs(share) * c.total * 1000.0
        row.label(text="carriage" if item.carriage else (f"{mm:g} mm" if parts else "no parts"))


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
        scene = context.scene
        n, made = waycover.state_counts(scene)
        k = len(waycover.covers(scene))
        if n or k:
            text = plural(n, "section") if k < 2 else plural(k, "cover")
            header_status(self.layout, text, icon="NONE" if made == n else "ERROR", alert=made < n)
        else:
            header_status(self.layout, "none")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        none = not waycover.covers(scene) and not len(s.waycovers)
        if none and not any(j.kind == "SLIDE" for j in s.joints):      # nothing a cover could follow
            missing(layout, context, "A way cover follows a slide joint (the machine's axis) and this project has "
                                     "none yet. Click the carriage (the part the axis moves), then:",
                    op="fresing.waycover_axis_from_selection", op_text="Add the axis joint", op_icon="ADD")
            return
        steps(layout, context, ["Add a way cover (one for each cover of the machine: a cover on each side of "
                                "the table is two)",
                                "Pick the slide joint it follows (the machine axis)",
                                "Click the parts of one cover section, then 'Add section' – "
                                "from the fixed end to the moving end",
                                "Check the total length of movement, then 'Make it'"],
              key="fr_how_waycover", used=waycover.state_counts(scene)[0] > 0)
        gap(layout)
        if none:
            big(layout, "fresing.waycover_cover_add", "Add way cover", "ADD")
            return
        c = waycover.settings(scene)

        # -- covers
        if len(s.waycovers):
            layout.label(text="Covers", icon="MOD_ARRAY")
            row = layout.row()
            row.template_list("FRESING_UL_waycovers", "", s, "waycovers", s, "waycovers_index",
                              rows=list_rows(len(s.waycovers), 1, 4))
            col = row.column(align=True)
            col.operator("fresing.waycover_cover_add", text="", icon="ADD")
            col.operator("fresing.waycover_remove_all", text="", icon="REMOVE")
            gap(layout)

        # -- 1 axis
        layout.label(text="1  Axis", icon="DRIVER")
        row = layout.row(align=True)
        row.prop_search(c, "axis", scene.fresing, "joints", text="", icon="DRIVER")
        problem = waycover.axis_problem(scene, c) if c.axis else ""
        if problem:
            wrap(layout, context, problem, icon="ERROR", alert=True)
        elif not c.axis:
            layout.operator("fresing.waycover_axis_from_selection", icon="ADD")

        # -- 2 sections
        gap(layout)
        layout.label(text="2  Sections (fixed end first)", icon="MOD_ARRAY")
        if c.sections:
            row = layout.row()
            row.template_list("FRESING_UL_waycover_sections", "", c, "sections", c, "sections_index",
                              rows=list_rows(len(c.sections), 2, 7))
            col = row.column(align=True)
            col.operator("fresing.waycover_remove", text="", icon="REMOVE")
            col.operator("fresing.waycover_move", text="", icon="TRIA_UP").direction = -1
            col.operator("fresing.waycover_move", text="", icon="TRIA_DOWN").direction = 1
            if 0 <= c.sections_index < len(c.sections) and c.sections[c.sections_index].carriage:
                sec = c.sections[c.sections_index]
                wrap(layout, context, f"{sec.name} – on the carriage: the axis '{c.axis}' moves it itself, so it "
                     "needs no joint of its own. It stays the last section", icon="PINNED")
            layout.operator("fresing.waycover_select", icon="RESTRICT_SELECT_OFF")
        big(layout, "fresing.waycover_add", "Add section", "ADD")

        # -- 3 travel
        gap(layout)
        layout.label(text="3  Travel", icon="ARROW_LEFTRIGHT")
        col = split_props(layout)
        col.prop(c, "total", text="Total movement")
        col.prop(c, "flip", text="Flip direction")
        col.prop(c, "housing_counts", text="Housing counts")
        layout.operator("fresing.waycover_read_total", icon="IMPORT")
        col = split_props(layout)
        col.prop(c, "drawn_at", text="Drawn at")
        layout.operator("fresing.waycover_read_drawn", text="Drawn at: read from the axis", icon="IMPORT")
        if c.sections:
            wrap(layout, context, waycover.check_line(scene, c), icon="INFO")
        if c.sections:
            wrap(layout, context, core.summary(len(c.sections), c.total * 1000.0, c.housing_counts), icon="INFO")

        # -- 4 make
        gap(layout)
        n, made = waycover.state_counts(scene, c)
        label = "Make it" if not made else ("Make it (new sections)" if made < n else "Make it again")
        big(layout, "fresing.waycover_make", label, "CHECKMARK")
        if n and made == n and not problem:
            wrap(layout, context, waycover.status(scene, c), icon="CHECKMARK")
        if not len(s.waycovers):
            gap(layout)
            layout.operator("fresing.waycover_cover_add", text="Add another way cover", icon="ADD")


CLASSES = (FRESING_UL_waycovers, FRESING_UL_waycover_sections, FRESING_PT_waycover)
