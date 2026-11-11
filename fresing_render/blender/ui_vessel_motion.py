"""Side panel: 5 Scene & Render > Vessel motion (task 0085). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from . import vessel_motion
from .ui import _has_model, _Panel, fold, header_status, list_rows, split_props, steps, wrap


class FRESING_UL_vessel_still(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.label or item.uid, icon="PINNED" if item.mode == "STILL" else "ORIENTATION_GLOBAL")
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        sub.prop(item, "mode", text="")


class FRESING_PT_vessel_motion(_Panel, bpy.types.Panel):
    bl_label = "Vessel motion"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="FORCE_HARMONIC")

    def draw_header_preset(self, context):
        header_status(self.layout, vessel_motion.header(context.scene), limit=20)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        v = s.vessel
        if s.background not in vessel_motion.KINDS:
            wrap(layout, context, "The vessel moves on the Open sea or the Vessel deck: pick one under Background & "
                 "surroundings above.", icon="INFO")
            return
        layout.prop(v, "enabled", text="Move with the sea")
        if not v.enabled:
            steps(layout, context, ["Tick 'Move with the sea': the machine and the deck heave, pitch and roll",
                                    "Pick the sea state and where the waves come from",
                                    "Play the time line: the sea and the camera stay put"])
            return

        # -- the sea and how much it moves the vessel
        col = split_props(layout)
        row = col.row(align=True)
        row.prop(s, "sea_state", text="Sea", expand=True)
        col.prop(v, "heading", text="Waves from")
        col.prop(v, "strength", text="Strength")
        text = vessel_motion.words(scene)
        if text:
            wrap(layout, context, text, icon="INFO")
        if s.env_detail != "DETAILED":
            wrap(layout, context, "Detail 'Detailed' (above) shows the long waves that move the vessel.",
                 icon="INFO")
        elif not s.sea_moving:
            wrap(layout, context, "The waves stand still ('Moving' is off above); the vessel moves all the same.",
                 icon="INFO")

        # -- the vessel
        body = fold(layout, "fr_vessel_size", "Vessel", "MOD_OCEAN")
        if body:
            col = split_props(body)
            col.prop(v, "auto_size", text="Size from the model")
            if v.auto_size:
                length, beam = vessel_motion.size(scene)
                body.label(text=f"Length {length:.0f} m, beam {beam:.0f} m", icon="BLANK1")
            else:
                col.prop(v, "length", text="Length")
                col.prop(v, "beam", text="Beam")
            col = split_props(body)
            col.prop(v, "roll_period", text="Roll period (s)")
            row = body.row(align=True)
            row.prop(v, "pivot_mode", text="Turns about", expand=True)
            row.operator("fresing.vessel_pivot_pick", text="", icon="EYEDROPPER")
            if v.pivot_mode == "PICK":
                p = v.pivot
                body.label(text=f"x {p[0]:.1f}  y {p[1]:.1f}  z {p[2]:.1f} m", icon="PIVOT_CURSOR")

        # -- parts that keep their place
        n = len(v.still)
        body = fold(layout, "fr_vessel_still", f"Stays still ({n})" if n else "Stays still", "PINNED")
        if body:
            wrap(body, context, "Select a subassembly (in the view or in 2 Structure), then:")
            row = body.row(align=True)
            row.operator("fresing.vessel_still_add", text="Still", icon="PINNED").mode = "STILL"
            row.operator("fresing.vessel_still_add", text="Level", icon="ORIENTATION_GLOBAL").mode = "LEVEL"
            if n:
                row = body.row()
                row.template_list("FRESING_UL_vessel_still", "", v, "still", v, "still_index", rows=list_rows(n, 2, 6))
                row.operator("fresing.vessel_still_remove", text="", icon="X")


PANELS = (FRESING_PT_vessel_motion,)
CLASSES = (FRESING_UL_vessel_still,) + PANELS
