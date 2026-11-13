"""Side panel: 5 Scene & Render > Web 3D model (task 0099). Same layout rules as ui.py."""

from __future__ import annotations

import os

import bpy

from ..core import web3d as core
from . import animation, ui, vessel_motion, web3d, web3d_env
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
        self.draw_surroundings(context, layout, w)

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
                              "the cutaway" + (", the halls and the quay." if w.env_mode == "PROJECT" else
                                               ", the surroundings (see Surroundings on the page)."), icon="INFO")

    def draw_surroundings(self, context, layout, w):
        """The fold "Surroundings on the page" (task 0106): folded, its state in the header."""
        scene = context.scene
        head, body = layout.panel("fr_web3d_env", default_closed=not ui._OPEN_FOLDS)
        head.label(text="Surroundings on the page")
        if body is None:
            return
        body.row().prop(w, "env_mode", expand=True)
        if w.env_mode != "PROJECT":
            wrap(body, context, "The machine alone on a light background, as before.", inset=12)
            return
        col = split_props(body)
        col.prop(w, "env_sea", text="Sea")
        sub = col.row(align=True)
        sub.enabled = w.env_sea
        sub.prop(w, "env_sea_state", expand=True)
        sub = col.row()
        sub.enabled = w.env_sea and vessel_motion.effective(scene)
        sub.prop(w, "env_vessel", text="Vessel motion")
        col.prop(w, "env_sky", text="Sky")
        if w.env_sky:
            col.prop(w, "env_sky_source", text="Sky from")
            photo = web3d_env.light_kind(scene.fresing) not in ("SKY", "OVERCAST")
            if w.env_sky_source == "TIME" or not photo:
                sub = col.column(align=True)
                sub.enabled = w.env_sky_source == "TIME"
                sub.prop(w, "env_sun_height", text="Sun height")
                sub.prop(w, "env_sun_direction", text="Sun direction")
                col.prop(w, "env_clouds", text="Clouds")
        row = col.row(align=True)
        row.prop(w, "env_haze", text="Haze")
        sub = row.row(align=True)
        sub.enabled = w.env_haze
        sub.prop(w, "env_haze_strength", text="")
        row = col.row(align=True)
        row.prop(w, "env_rain", text="Rain")
        sub = row.row(align=True)
        sub.enabled = w.env_rain
        sub.prop(w, "env_rain_strength", text="")
        col.prop(w, "env_shadows", text="Live sun shadows")
        body.label(text="Page quality")
        body.row(align=True).prop(w, "env_quality", expand=True)
        col = split_props(body)
        col.prop(w, "env_auto", text="Auto quality")
        body.operator("fresing.web3d_env_from_project", text="Take from the project", icon="FILE_REFRESH")


PANELS = (FRESING_PT_web3d,)
CLASSES = PANELS
