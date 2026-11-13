"""Side panel: 5 Scene & Render > Web 3D model (task 0099). Same layout rules as ui.py."""

from __future__ import annotations

import os

import bpy

from ..core import web3d as core
from . import animation, web3d
from .ui import MEDIUM, _has_model, _Panel, big_row, header_status, primary, split_props, wrap


class FRESING_PT_web3d(_Panel, bpy.types.Panel):
    bl_label = "Web 3D model"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="WORLD")

    def draw_header_preset(self, context):
        w = web3d.settings(context.scene)
        if web3d.runtime(context.scene).get("running"):
            header_status(self.layout, "exporting")
        elif w.last_size and os.path.exists(w.last_path):
            header_status(self.layout, core.header(w.last_size))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        w = web3d.settings(scene)
        rt = web3d.runtime(scene)
        wrap(layout, context, "One 3D file of the machine as it is shown now, with its looks, and a page that shows "
                              "it in any web browser: drag to turn, scroll to zoom.")
        col = split_props(layout)
        row = col.row(align=True)
        row.prop(w, "texture_size", text="Texture size", expand=True)
        col.prop(w, "hide_names", text="Hide part names")
        col.prop(w, "compress", text="Smaller file")
        sub = col.row()
        sub.enabled = animation.has_keys(scene)
        sub.prop(w, "animation", text="Include animation")

        layout.separator()
        if rt.get("running"):
            row = big_row(layout, MEDIUM)
            row.label(text=f"{rt.get('text', 'Working')} … {rt.get('progress', 0.0) * 100:.0f}%", icon="SORTTIME")
            row.operator("fresing.web3d_cancel", text="Cancel", icon="CANCEL")
            return
        primary(layout, "fresing.web3d_export", "Export…", "EXPORT")
        if w.last_text and os.path.exists(w.last_path):
            box = layout.box()
            box.label(text=os.path.basename(w.last_path), icon="FILE_3D")
            wrap(box, context, w.last_text, inset=12)
            row = box.row(align=True)
            if w.last_html and os.path.exists(w.last_html):
                op = row.operator("fresing.open_file", text="Open page", icon="URL")
                op.path = w.last_html
            op = row.operator("fresing.show_in_folder", text="Show in folder", icon="FILE_FOLDER")
            op.path = w.last_path
        wrap(layout, context, "Not in the web model: edge wear, the shine along brushed or turned metal, tool marks, "
                              "the cutaway, the surroundings.", icon="INFO")


PANELS = (FRESING_PT_web3d,)
CLASSES = PANELS
