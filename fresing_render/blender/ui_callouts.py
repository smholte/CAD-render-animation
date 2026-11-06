"""Side panel: 5 Scene & Render > Labels; 6 Animation > Pictures & music (task 0025). Layout rules as in ui.py."""

from __future__ import annotations

import os

import bpy

from ..core import brand
from ..core.words import plural
from . import animation, callouts, video
from .ui import _has_model, _Panel, big_row, header_status, primary, split_props, wrap


class FRESING_UL_callouts(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        ok = item.obj is not None
        row.label(text=item.text or "(no words)", icon="OUTLINER_OB_FORCE_FIELD" if ok else "ERROR")
        if item.step:
            row.label(text=item.step, icon="TIME")


class FRESING_UL_cards(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        name = item.name or os.path.basename(item.file) or "(no picture)"
        row.label(text=name, icon="IMAGE_DATA")
        row.label(text="full" if item.mode == "FULL" else "corner")


class FRESING_PT_labels(_Panel, bpy.types.Panel):
    bl_label = "Labels"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="OUTLINER_OB_FORCE_FIELD")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.callouts)
        if n:
            header_status(self.layout, plural(n, "label"))

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "A text box beside the model with a thin line to a spot on a part, in stills and in "
                              "videos. The line follows the part when it moves.")
        primary(layout, "fresing.callout_add", "Add label: click a spot on a part", "OUTLINER_OB_FORCE_FIELD")
        if s.callout_picking:
            wrap(layout, context, "Click the spot in the 3D view. Esc cancels.", icon="INFO", inset=12)
        if not s.callouts:
            return
        layout.template_list("FRESING_UL_callouts", "", s, "callouts", s, "callouts_index", rows=3)
        if 0 <= s.callouts_index < len(s.callouts):
            c = s.callouts[s.callouts_index]
            col = split_props(layout)
            col.prop(c, "text", text="Words")
            a = animation.active(context.scene)
            if a is not None:
                col.prop_search(c, "step", a, "blocks", text="Only with step")
            col.prop(c, "on_still", text="On images")
            col.prop(c, "on_video", text="In videos")
            col.prop(c, "manual", text="Place by hand")
            if c.manual:
                col.prop(c, "box_x", text="Box: left to right")
                col.prop(c, "box_y", text="Box: bottom to top")
            row = layout.row(align=True)
            row.operator("fresing.callout_show", icon="RESTRICT_SELECT_OFF")
            row.operator("fresing.callout_remove", text="Remove", icon="TRASH")
            if c.obj is None:
                wrap(layout, context, "The part of this label is gone: remove the label.", icon="ERROR", alert=True,
                     inset=12)
        col = split_props(layout)
        col.prop(s, "callout_size", text="Letter size")


class FRESING_PT_pictures(_Panel, bpy.types.Panel):
    bl_label = "Pictures & music"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and animation.active(context.scene) is not None

    def draw_header(self, context):
        self.layout.label(icon="SOUND")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        if a is None:
            return
        n = len(a.cards) + bool(a.music_file)
        if n:
            header_status(self.layout, f"{n} on")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        a = animation.active(scene)
        wrap(layout, context, "Photos or diagrams shown between the steps, and music under the whole video. "
                              "Only in MP4 videos. Labels on parts: 5 Scene & Render > Labels.")
        layout.label(text="Pictures", icon="IMAGE_DATA")
        layout.template_list("FRESING_UL_cards", "", a, "cards", a, "cards_index", rows=2)
        row = layout.row(align=True)
        row.operator("fresing.card_add", icon="ADD")
        row.operator("fresing.card_remove", text="Remove", icon="TRASH")
        if 0 <= a.cards_index < len(a.cards):
            c = a.cards[a.cards_index]
            col = split_props(layout)
            col.prop(c, "file", text="Picture")
            col.prop(c, "mode", text="Show")
            if c.mode == "CORNER":
                col.prop(c, "corner", text="Corner")
                col.prop(c, "size", text="Size")
            col.prop(c, "seconds", text="Seconds")
            col.prop_search(c, "after_step", a, "blocks", text="After step")
            if not c.after_step:
                col.prop(c, "at", text="At (s)")
            col.prop(c, "caption", text="Caption")
            if c.file and not os.path.isfile(bpy.path.abspath(c.file)):
                wrap(layout, context, "The picture file cannot be found.", icon="ERROR", alert=True, inset=12)
            elif c.file and not c.file.lower().endswith(brand.LOGO_TYPES):
                wrap(layout, context, "Use a PNG or JPG picture.", icon="ERROR", alert=True, inset=12)
        layout.separator()
        layout.label(text="Music", icon="SOUND")
        col = split_props(layout)
        col.prop(a, "music_file", text="Sound file")
        if a.music_file:
            col.prop(a, "music_volume", text="Volume")
            col.prop(a, "music_start", text="Starts at (s)")
            col.prop(a, "music_fade_in", text="Fade in (s)")
            col.prop(a, "music_fade_out", text="Fade out (s)")
            if not video._music_path(a):
                wrap(layout, context, "Pick a WAV, MP3, OGG, FLAC or M4A file that exists.", icon="ERROR",
                     alert=True, inset=12)
            else:
                wrap(layout, context, "Only use music you own or have the rights to.", icon="INFO", inset=12)


CLASSES = (FRESING_UL_callouts, FRESING_UL_cards, FRESING_PT_labels, FRESING_PT_pictures)
