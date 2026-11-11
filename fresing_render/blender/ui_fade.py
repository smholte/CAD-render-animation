"""Side panel: 3 Looks > X-ray look and 6 Animation > Trail lines (task 0073). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import animation, build, fade, trails
from .ui import _has_model, _Panel, header_status, list_rows, primary, split_props, steps, wrap


class FRESING_PT_xray(_Panel, bpy.types.Panel):
    bl_label = "X-ray look"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="XRAY")

    def draw_header_preset(self, context):
        n = len(fade.xray_parts(context.scene))
        if n:
            header_status(self.layout, plural(n, "part"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        n = len(fade.xray_parts(scene))
        if not n:
            steps(layout, context, ["Select a subassembly (or a part), or pick a group in the list above",
                                    "X-ray it: it turns see-through with glowing edges",
                                    "Shows in rendered view, pictures and videos"])
        col = split_props(layout)
        col.prop(s, "xray_color", text="Colour")
        col.prop(s, "xray_strength", text="Strength", slider=True)
        primary(layout, "fresing.xray_selected", "X-ray the selected", "XRAY", 1.25)
        row = layout.row(align=True)
        row.operator("fresing.xray_group", text="X-ray this group", icon="MATERIAL")
        row.operator("fresing.xray_clear", text="Back to normal", icon="LOOP_BACK")
        if n:
            row = layout.row(align=True)
            row.label(text=f"{plural(n, 'part')} in X-ray", icon="INFO")
            row.operator("fresing.xray_clear_all", text="All back", icon="X")
        hint = wrap(layout, context, "To make a housing turn X-ray during a video, use a Fade out step with 'Fade to "
                                     "X-ray' in 6 Animation", inset=12)
        hint.active = False


class FRESING_UL_trails(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=trails.label(item), icon="CURVE_PATH")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=item.animation or "all")


class FRESING_PT_trails(_Panel, bpy.types.Panel):
    bl_label = "Trail lines"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="CURVE_PATH")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.trails)
        if n:
            header_status(self.layout, plural(n, "line"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not s.trails:
            steps(layout, context, ["Select the part whose path you want to see (a hook, a tool, a carriage)",
                                    "Add a trail line, pick its point and colour",
                                    "Build the animation: the line draws the path"])
        row = layout.row()
        row.template_list("FRESING_UL_trails", "", s, "trails", s, "trails_index",
                          rows=list_rows(len(s.trails), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.trail_add", text="", icon="ADD")
        col.operator("fresing.trail_remove", text="", icon="REMOVE")
        t = trails.active(scene)
        if t is None:
            return
        box = layout.box()
        row = box.row(align=True)
        part = t.part.get(build.PROP_NAME, t.part.name) if t.part is not None else "No part"
        row.label(text=part, icon="OBJECT_DATA")
        row.operator("fresing.trail_use_selected", text="Use selected", icon="EYEDROPPER")
        col = split_props(box)
        col.prop(t, "point", text="Point")
        if t.point == "CLICKED":
            box.operator("fresing.trail_pick_point", text="Click the point…", icon="RESTRICT_SELECT_OFF")
        note = trails.point_text(scene, t)
        if note:
            wrap(box, context, note, icon="INFO", inset=12)
        col = split_props(box)
        col.prop_search(t, "animation", s, "animations", text="Animation", icon="RENDER_ANIMATION")
        col.prop(t, "color", text="Colour")
        col.prop(t, "thickness", text="Thickness")
        box.prop(t, "grow", text="Draw as it goes")
        box.prop(t, "in_render", text="In pictures and videos")
        box.prop(t, "name", text="Name")
        built = s.anim_baked
        if t.obj is None:
            wrap(box, context, "Build the animation (above) to draw it", icon="INFO", inset=12)
        elif built and (not t.animation or t.animation == built):
            wrap(box, context, f"Drawn at the last Build ({plural(t.count, 'point')})", icon="CHECKMARK", inset=12)
        elif t.animation and animation.active(scene) is not None and t.animation != built:
            hint = wrap(box, context, "Build its animation to update it", icon="INFO", inset=12)
            hint.active = False


PANELS = (FRESING_PT_xray,)
CLASSES = (FRESING_UL_trails, FRESING_PT_trails)
