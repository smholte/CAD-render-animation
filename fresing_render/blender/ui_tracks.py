"""Side panel: 4 Motion > Tracks and belts (task 0079). Same layout rules as ui.py."""

from __future__ import annotations

import math

import bpy

from ..core.words import plural
from . import joints, tracks
from .ui import _has_model, _Panel, header_status, list_rows, primary, big_row, MEDIUM, split_props, steps, wrap

ICON = "MOD_ARRAY"
LEVEL_ICONS = {"OK": "CHECKMARK", "WARN": "ERROR", "ERROR": "ERROR", "OFF": "INFO"}


def counts(scene) -> tuple[str, bool]:
    its = list(tracks.items(scene))
    if not its:
        return "–", False
    bad = sum(1 for it in its if tracks.status(scene, it)[1] in ("WARN", "ERROR"))
    return (plural(bad, "warning"), True) if bad else (plural(len(its), "track"), False)


def wheel_text(w) -> str:
    """'Ø 785, 180°' for a wheel the chain bends round, 'Ø 120, touches' for one it runs past."""
    d = f"Ø {2000.0 * w.radius:.0f}"
    return f"{d}, {math.degrees(w.wrap):.0f}°" if w.wrapped else f"{d}, touches"


class FRESING_UL_tracks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        text, level = tracks.status(context.scene, item)
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon=ICON)
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        if level == "OFF":
            sub.label(text="off")
        elif level in ("WARN", "ERROR"):
            sub.alert = True
            sub.label(text="check", icon="ERROR")
        else:
            sub.label(text=f"{item.parts}", icon="CHECKMARK")


class FRESING_UL_track_wheels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.55, align=True)
        split.label(text=item.name, icon="MESH_CYLINDER", translate=False)
        sub = split.row(align=True)
        sub.alignment = "RIGHT"
        sub.alert = bool(item.note)
        sub.label(text=wheel_text(item))


class FRESING_PT_tracks(_Panel, bpy.types.Panel):
    bl_label = "Tracks and belts"
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
        if not len(s.tracks):
            steps(layout, context, ["Press 'Add track', then click the wheels round the loop and press Enter",
                                    "Click one link of the chain, then a pad or plate if it has them, and press "
                                    "Enter",
                                    "The pads run with the cable through the track; else give its speed joint a "
                                    "Run motor step in 6 Animation"])
            primary(layout, "fresing.track_add", "Add track", "ADD")
            return

        row = layout.row()
        row.template_list("FRESING_UL_tracks", "", s, "tracks", s, "tracks_index",
                          rows=list_rows(len(s.tracks), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.track_remove", text="", icon="REMOVE")
        col.operator("fresing.track_select", text="", icon="RESTRICT_SELECT_OFF")
        big_row(layout, MEDIUM).operator("fresing.track_add", text="Add track", icon="ADD")

        it = tracks.active(scene)
        if it is None:
            return
        layout.separator()
        layout.label(text=tracks.label(it), icon=ICON)
        text, level = tracks.status(scene, it)
        if level == "OFF":
            wrap(layout, context, "Off: it shows as in the CAD file and stands still. Tick it in the list to "
                 "switch it on.", icon="INFO")
        else:
            wrap(layout, context, text[:1].upper() + text[1:], icon=LEVEL_ICONS[level],
                 alert=level in ("WARN", "ERROR"))
        col = layout.column(align=True)
        col.label(text=f"{plural(it.links, 'link')} of {it.pitch * 1000.0:.0f} mm, "
                       f"{plural(it.parts - it.links, "pad or plate", "pads and plates")} on them")
        col.label(text=f"Loop {it.length:.3f} m, chain {it.chain_length:.3f} m")
        # -- its speed
        col = split_props(layout)
        col.prop_search(it, "joint", s, "joints", text="Speed")
        layout.prop(it, "reverse", text="Runs the other way")
        if it.joint and joints.find(scene, it.joint) is not None:
            layout.operator("fresing.track_motor_step", text="Add a Run motor step", icon="ADD")
        # -- its wheels
        layout.separator()
        layout.label(text=f"Wheels ({len(it.wheels)})", icon="MESH_CYLINDER")
        layout.template_list("FRESING_UL_track_wheels", "", it, "wheels", it, "wheels_index",
                             rows=list_rows(len(it.wheels), 2, 6))
        if 0 <= it.wheels_index < len(it.wheels):
            w = it.wheels[it.wheels_index]
            box = layout.box()
            box.label(text=w.name, icon="MESH_CYLINDER", translate=False)
            c = box.column(align=True)
            c.label(text="The chain bends round it: one tooth per link" if w.wrapped else
                    "The chain runs past it: it turns with the chain's speed")
            if w.joint:
                wrap(c, context, f"Turns on '{w.joint}'" + (" (made by the app)" if w.made_joint else ""), inset=12)
            if w.ratio:
                c.label(text=f"{abs(w.ratio):.4f}° per mm" if joints.find(scene, it.joint) is not None
                        and joints.find(scene, it.joint).kind == "SLIDE" else f"{abs(w.ratio):.4f} turns per turn")
            if w.note:
                wrap(box, context, w.note, icon="ERROR", inset=12, alert=True)
        for note in [n for n in it.notes.split("\n") if n][:3]:
            wrap(layout, context, note, icon="INFO")


PANELS = (FRESING_PT_tracks,)
CLASSES = (FRESING_UL_tracks, FRESING_UL_track_wheels) + PANELS
