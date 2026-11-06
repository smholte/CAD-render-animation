"""Side panel: 5 Scene & Render > Labels; 6 Animation > Pictures, Music (task 0025). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import animation, callouts, video
from .ui import _has_model, _Panel, big_row, header_status, list_rows, split_props, wrap


class FRESING_UL_callouts(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        sub = row.row(align=True)
        sub.alert = item.part is None
        sub.label(text=item.text or "(empty)", icon="FONT_DATA" if item.part is not None else "ERROR")
        if item.step:
            row.label(text=item.step, icon="SEQUENCE")


class FRESING_UL_cards(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=video.card_name(item), icon="IMAGE_DATA")
        row.label(text=f"{item.start:g}–{item.start + item.duration:g} s")


class FRESING_PT_labels(_Panel, bpy.types.Panel):
    bl_label = "Labels"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="FONT_DATA")

    def draw_header_preset(self, context):
        n = sum(1 for c in context.scene.fresing.callouts if c.enabled)
        if n:
            header_status(self.layout, plural(n, "label"))

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Words with a thin line to a spot on a part, in stills and MP4 videos. The line "
                              "stays on its part when the part moves. Look comes from the brand kit.")
        big_row(layout, 1.4).operator("fresing.callout_add", icon="EYEDROPPER")
        if s.callouts:
            layout.template_list("FRESING_UL_callouts", "", s, "callouts", s, "callouts_index",
                                 rows=list_rows(len(s.callouts), 2, 6))
            if 0 <= s.callouts_index < len(s.callouts):
                c = s.callouts[s.callouts_index]
                col = split_props(layout)
                col.prop(c, "text", text="Words")
                a = animation.active(context.scene)
                if a is not None and a.blocks:
                    col.prop_search(c, "step", a, "blocks", text="Only during")
                else:
                    col.prop(c, "step", text="Only during")
                if c.part is None:
                    wrap(layout, context, "The part of this label is gone. Press Move the point and click another "
                                          "part, or remove the label.", icon="ERROR", alert=True, inset=12)
                else:
                    layout.label(text=f"Points at {c.part.name}", icon="PIVOT_CURSOR")
                row = layout.row(align=True)
                row.operator("fresing.callout_move", icon="EYEDROPPER")
                row.operator("fresing.callout_show_part", text="Select part", icon="RESTRICT_SELECT_OFF")
                row.operator("fresing.callout_remove", text="", icon="TRASH")
        else:
            wrap(layout, context, "No labels yet. Press Add a label, then click a spot on the machine.", icon="INFO",
                 inset=12)
        layout.separator()
        col = split_props(layout)
        col.prop(s, "callouts_on", text="Draw labels in renders")
        col.prop(s, "callout_size", text="Text size")


class FRESING_PT_cards(_Panel, bpy.types.Panel):
    bl_label = "Pictures"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and animation.active(context.scene) is not None

    def draw_header(self, context):
        self.layout.label(icon="IMAGE_DATA")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        n = sum(1 for c in a.cards if c.enabled) if a else 0
        if n:
            header_status(self.layout, plural(n, "picture"))

    def draw(self, context):
        layout = self.layout
        a = animation.active(context.scene)
        wrap(layout, context, "A photo or diagram shown for a few seconds over the video, full screen or in a "
                              "corner. To show one between two steps, leave a gap between them and start it there. "
                              "Only in MP4 videos.")
        big_row(layout, 1.4).operator("fresing.card_add", icon="ADD")
        if a.cards:
            layout.template_list("FRESING_UL_cards", "", a, "cards", a, "cards_index",
                                 rows=list_rows(len(a.cards), 2, 5))
            if 0 <= a.cards_index < len(a.cards):
                c = a.cards[a.cards_index]
                col = split_props(layout)
                col.prop(c, "path", text="Picture")
                col.prop(c, "start", text="Starts at")
                col.prop(c, "duration", text="Seconds")
                col.prop(c, "mode", text="Shown")
                if c.mode == "CORNER":
                    col.prop(c, "corner", text="Corner")
                col.prop(c, "caption", text="Caption")
                if c.path and not video._cards_of_one(c):
                    wrap(layout, context, "This picture cannot be read: pick a PNG, JPG, TIF, BMP or WebP file.",
                         icon="ERROR", alert=True, inset=12)
                layout.operator("fresing.card_remove", icon="TRASH")


class FRESING_PT_music(_Panel, bpy.types.Panel):
    bl_label = "Music"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and animation.active(context.scene) is not None

    def draw_header(self, context):
        self.layout.label(icon="SOUND")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        if a is not None and a.music_on:
            header_status(self.layout, "on")

    def draw(self, context):
        layout = self.layout
        a = animation.active(context.scene)
        wrap(layout, context, "Music under the whole MP4 video, cut to its length. Use your own music, or music "
                              "you have the rights to.")
        layout.prop(a, "music_on", text="Music under the video", toggle=True, icon="SOUND")
        if a.music_on:
            col = split_props(layout)
            col.prop(a, "music_file", text="Sound file")
            col.prop(a, "music_start", text="Starts at")
            col.prop(a, "music_volume", text="Volume")
            col.prop(a, "music_fade_in", text="Fade in")
            col.prop(a, "music_fade_out", text="Fade out")
            if a.music_file and not video.music_path(a):
                wrap(layout, context, "This file cannot be read: pick a WAV, MP3, OGG, FLAC or M4A file.",
                     icon="ERROR", alert=True, inset=12)
            if a.video != "MP4":
                wrap(layout, context, "Music only goes into MP4 videos (6 Animation > Save as).", icon="INFO",
                     inset=12)


CLASSES = (FRESING_UL_callouts, FRESING_UL_cards, FRESING_PT_labels, FRESING_PT_cards, FRESING_PT_music)
