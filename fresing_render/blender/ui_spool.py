"""Side panel: 4 Motion > Drums and carousels (task 0080). Same layout rules as ui.py."""

from __future__ import annotations

import math

import bpy

from ..core.words import plural
from . import paths, spool
from .ui import MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, split_props, steps, wrap

ICON = "MESH_CYLINDER"
MODE_ICONS = {"ACROSS": "ARROW_LEFTRIGHT", "ARM": "CON_ROTLIKE", "ALONG": "ORIENTATION_GIMBAL"}


def counts(scene) -> tuple[str, bool]:
    sps = list(spool.items(scene))
    if not sps:
        return "–", False
    bad = sum(1 for sp in sps if sp.enabled and sp.problem)
    return (plural(bad, "warning"), True) if bad else (plural(len(sps), "spool"), False)


class FRESING_UL_spools(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon="MESH_CIRCLE" if item.kind == "CAROUSEL" else ICON)
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        if not item.enabled:
            sub.label(text="off")
        elif item.problem:
            sub.alert = True
            sub.label(text="check", icon="ERROR")
        else:
            sub.label(text=f"layer {item.layer}" if item.layer else "", icon="CHECKMARK")


def _add_buttons(layout, first: bool) -> None:
    if first:
        row = big_row(layout)
        row.operator("fresing.spool_add", text="Add drum", icon="ADD", depress=True).kind = "DRUM"
        row.operator("fresing.spool_add", text="Add carousel", icon="ADD", depress=True).kind = "CAROUSEL"
    else:
        row = big_row(layout, MEDIUM)
        row.operator("fresing.spool_add", text="Add drum", icon="ADD").kind = "DRUM"
        row.operator("fresing.spool_add", text="Add carousel", icon="ADD").kind = "CAROUSEL"


class FRESING_PT_spools(_Panel, bpy.types.Panel):
    bl_label = "Drums and carousels"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon=ICON)

    def draw_header_preset(self, context):
        text, alert = counts(context.scene)
        header_status(self.layout, text, icon="ERROR" if alert else "NONE", alert=alert, limit=11)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not len(s.spools):
            steps(layout, context, ["Add the cable or wire rope in Cables and paths and choose it there",
                                    "Press 'Add drum' or 'Add carousel' and click the drum's barrel or the "
                                    "carousel's turntable",
                                    "It turns with the cable speed: the cable comes off layer by layer"])
            if not len(s.cables):
                wrap(layout, context, "There is no cable yet: add it in Cables and paths first", icon="INFO")
            _add_buttons(layout, first=True)
            return
        row = layout.row()
        row.template_list("FRESING_UL_spools", "", s, "spools", s, "spools_index", rows=list_rows(len(s.spools), 2, 5))
        col = row.column(align=True)
        col.operator("fresing.spool_remove", text="", icon="REMOVE")
        col.operator("fresing.spool_select", text="", icon="RESTRICT_SELECT_OFF")
        _add_buttons(layout, first=False)
        sp = spool.active(scene)
        if sp is None:
            return
        layout.separator()
        layout.label(text=spool.label(sp), icon="MESH_CIRCLE" if sp.kind == "CAROUSEL" else ICON)
        text, icon = spool.status(scene, sp)
        wrap(layout, context, text, icon=icon, alert=icon == "ERROR")
        if not sp.enabled:
            return
        wrap(layout, context, f"Cable: '{sp.cable}'", icon="CURVE_PATH")
        wrap(layout, context, f"Turns with joint '{sp.joint}' (follows the cable by table)", icon="LINKED")
        col = split_props(layout)
        col.prop(sp, "wound", text="On it at the start")
        if sp.kind == "DRUM":
            col.prop(sp, "groove", text="Grooves")
            col.prop(sp, "pitch", text="Groove pitch")
            if sp.fleet_lo or sp.fleet_hi:
                wrap(layout, context, f"Fleet angle {math.degrees(sp.fleet_lo):.1f}° / "
                                      f"{math.degrees(sp.fleet_hi):.1f}° at the two flanges", icon="DRIVER_ROTATIONAL_DIFFERENCE",
                     alert=max(sp.fleet_lo, sp.fleet_hi) > sp.fleet_limit + 1e-9)
        layout.prop(sp, "other_side", text="First layer from the rim" if sp.kind == "CAROUSEL"
                    else "First layer from the other flange")

        # -- followers of the layer
        layout.separator()
        n = len(sp.followers)
        layout.label(text=f"Follow the layer ({n})" if n else "Follow the layer", icon="CON_FOLLOWPATH")
        for k, f in enumerate(sp.followers):
            row = layout.row(align=True)
            row.label(text=f.joint, icon=MODE_ICONS.get(f.mode, "DOT"))
            row.prop(f, "mode", text="")
            row.operator("fresing.spool_follower_remove", text="", icon="X").index = k
        layout.operator("fresing.spool_follower_add", text="This joint follows the layer", icon="ADD")

        # -- rarely changed
        body = fold(layout, "fr_spools_more", "More", "PREFERENCES")
        if body:
            col = split_props(body)
            if sp.kind == "DRUM":
                col.prop(sp, "r1", text="First layer")
                if sp.groove == "LEBUS":
                    col.prop(sp, "crossover", text="Crossover")
                col.prop(sp, "fleet_limit", text="Fleet warning")
            else:
                col.prop(sp, "r_in", text="Inner radius")
                col.prop(sp, "r_out", text="Outer radius")
            body.operator("fresing.spool_read", text="Read it again", icon="FILE_REFRESH")
            if paths.find(scene, sp.cable) is None:
                wrap(body, context, f"Its cable '{sp.cable}' is gone", icon="ERROR", alert=True)


PANELS = (FRESING_PT_spools,)
CLASSES = (FRESING_UL_spools,) + PANELS

