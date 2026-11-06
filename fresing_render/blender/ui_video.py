"""Side panel: 5 Scene & Render > Brand kit & logo, Watermark; 6 Animation > Finishing (task 0018).
Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import brand
from ..core.words import plural
from . import animation, video
from .ui import _has_model, _Panel, big_row, header_status, split_props, wrap


class FRESING_PT_brand(_Panel, bpy.types.Panel):
    bl_label = "Brand kit & logo"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="BOOKMARKS")

    def draw_header_preset(self, context):
        s = context.scene.fresing
        if s.brand_name:
            header_status(self.layout, s.brand_name)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "One kit per company: logo, colours, font and contact line. The logo, title card, "
                              "end card and captions of your videos use it (6 Animation > Finishing).")
        row = layout.row(align=True)
        row.prop(s, "brand_name", text="Kit")
        row.menu("FRESING_MT_brand_kits", text="", icon="DOWNARROW_HLT")
        col = split_props(layout)
        col.prop(s, "brand_logo", text="Logo")
        col.prop(s, "brand_color1", text="Card colour")
        col.prop(s, "brand_color2", text="Text colour")
        col.prop(s, "brand_font", text="Font")
        col.prop(s, "brand_contact", text="Contact")
        if s.brand_logo and not video._logo_path(s):
            wrap(layout, context, "The logo cannot be read: pick a PNG or JPG picture.", icon="ERROR", alert=True,
                 inset=12)
        row = layout.row(align=True)
        row.operator("fresing.brand_save", icon="EXPORT")
        row.operator("fresing.brand_delete", text="Delete", icon="TRASH")
        folder, shared, problem = video.kit_folder()
        if problem:
            wrap(layout, context, problem + ".", icon="ERROR", alert=True, inset=12)
        layout.separator()
        wrap(layout, context, "Logo on still images:")
        col = split_props(layout)
        col.prop(s, "still_logo", text="Corner")
        if s.still_logo != "NONE":
            col.prop(s, "still_logo_size", text="Size")
            if not video._logo_path(s):
                wrap(layout, context, "Add a logo above first.", icon="INFO", inset=12)


class FRESING_PT_watermark(_Panel, bpy.types.Panel):
    bl_label = "Watermark"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_MASK")

    def draw_header_preset(self, context):
        if context.scene.fresing.wm_on:
            header_status(self.layout, "on", alert=True)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Words across the picture, for drafts you send before the final render. Every "
                              "queue job remembers whether it was added with the watermark on.")
        row = big_row(layout, 1.4)
        row.prop(s, "wm_on", text="Watermark on the next renders", toggle=True,
                 icon="CHECKBOX_HLT" if s.wm_on else "CHECKBOX_DEHLT")
        col = split_props(layout)
        col.prop(s, "wm_kind", text="Words")
        if s.wm_kind == "CUSTOM":
            col.prop(s, "wm_text", text="Own text")
        col.prop(s, "wm_size", text="Size")
        col.prop(s, "wm_opacity", text="See-through")
        if s.wm_on and not video.watermark_words(s):
            wrap(layout, context, "Type your own words above.", icon="ERROR", alert=True, inset=12)


class FRESING_PT_finishing(_Panel, bpy.types.Panel):
    bl_label = "Finishing"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and animation.active(context.scene) is not None

    def draw_header(self, context):
        self.layout.label(icon="SEQUENCE")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        if a is None:
            return
        n = sum((a.fin_logo != "NONE", a.fin_title_on, a.fin_end_on, a.fin_captions))
        if n:
            header_status(self.layout, f"{n} on")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        a = animation.active(scene)
        wrap(layout, context, "Makes the MP4 ready to post or send. The look comes from the brand kit (5 Scene & "
                              "Render). Not in PNG frames.")
        col = split_props(layout)
        col.prop(a, "out_format", text="Shape")
        if a.out_format != "presentation":
            col.prop(a, "shape_fit", text="Framing")
        col.prop(a, "fin_logo", text="Logo")
        if a.fin_logo != "NONE":
            col.prop(a, "fin_logo_size", text="Logo size")
            if not video._logo_path(s):
                wrap(layout, context, "No logo in the brand kit yet (5 Scene & Render > Brand kit & logo).",
                     icon="INFO", inset=12)
        layout.separator()
        col = layout.column(align=True)
        col.prop(a, "fin_title_on", text="Title card", toggle=True, icon="TEXT")
        if a.fin_title_on:
            sub = split_props(col)
            sub.prop(a, "fin_title", text="Title")
            sub.prop(a, "fin_subtitle", text="Subtitle")
            sub.prop(a, "fin_title_seconds", text="Seconds")
        col = layout.column(align=True)
        col.prop(a, "fin_end_on", text="End card", toggle=True, icon="IMAGE_RGB_ALPHA")
        if a.fin_end_on:
            sub = split_props(col)
            sub.prop(a, "fin_end_seconds", text="Seconds")
            if not s.brand_contact and not video._logo_path(s):
                wrap(col, context, "The end card shows the logo and the contact line of the brand kit; both are "
                                   "empty.", icon="INFO", inset=12)
        col = layout.column(align=True)
        col.prop(a, "fin_captions", text="Captions from the step labels", toggle=True, icon="ALIGN_CENTER")
        if a.fin_captions:
            n = len(video.steps_of(a))
            wrap(col, context, f"{plural(n, 'step')} with a label will get a caption. Type labels in 6 Animation "
                               "> the selected step.", icon="INFO", inset=12)
        fps = animation.fps_of(a)
        body = animation.frame_of(a, animation.length_seconds(a))      # the animation's own frames
        fin = video.finishing_for_animation(scene, a)
        pl = brand.plan(fin, body, fps)
        layout.label(text=f"Video: {pl.total / fps:.1f} s ({plural(pl.total, 'frame')})", icon="TIME")


CLASSES = (FRESING_PT_brand, FRESING_PT_watermark, FRESING_PT_finishing)
