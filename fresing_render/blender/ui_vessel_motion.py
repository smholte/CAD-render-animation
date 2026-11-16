"""Side panel: 5 Scene & Render > Vessel motion (task 0085) and Vessel at work (task 0154). Same layout rules as
ui.py."""

from __future__ import annotations

import bpy

from . import vessel_motion, vessel_work
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

        wrap(layout, context, "Camera on board: in 6 Animation add a Camera step, Ride along, and pick any part of "
             "the machine (Keep level: the horizon stays still).", icon="CAMERA_DATA")

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


class FRESING_UL_vessel_thrusters(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon = {"AZIMUTH": "ORIENTATION_GIMBAL", "TUNNEL": "ARROW_LEFTRIGHT", "SHAFT": "FORWARD"}.get(item.kind,
                                                                                                    "BLANK1")
        row = layout.row(align=True)
        ok = bool(item.joint) and context.scene.fresing.joints.get(item.joint) is not None
        row.label(text=item.name or item.joint or "?", icon=icon if ok else "ERROR")
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        sub.label(text=item.bl_rna.properties["kind"].enum_items[item.kind].name)


class FRESING_PT_vessel_work(_Panel, bpy.types.Panel):
    bl_label = "Vessel at work"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_OCEAN")

    def draw_header_preset(self, context):
        if context.scene.fresing.background in vessel_motion.KINDS:
            header_status(self.layout, vessel_work.header(context.scene), limit=14)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        vw = s.vessel_work
        if s.background not in vessel_motion.KINDS:
            wrap(layout, context, "The vessel works on the Open sea or the Vessel deck: pick one under Background & "
                 "surroundings above.", icon="INFO")
            return
        if not len(vw.thrusters):
            steps(layout, context, ["Find thrusters: the propellers among the joints",
                                    "Pick what the vessel does: Ahead, Sideways or Turning",
                                    "A Vessel at work step in 6 Animation changes it during a video"])
        # -- what the vessel does
        layout.row(align=True).prop(vw, "mode", expand=True)
        col = split_props(layout)
        if vw.mode == "AHEAD":
            col.prop(s.weather, "vessel_speed", text="Speed (kn)")
        elif vw.mode in ("DP", "TURN"):
            col.row(align=True).prop(vw, "side", text="Bow to" if vw.mode == "TURN" else "Push to", expand=True)
            col.prop(vw, "thrust", text="Thrust", slider=True)
        wrap(layout, context, vessel_work.words(scene), icon="INFO")
        if not s.sea_foam:
            wrap(layout, context, "Tick 'Foam' (Background & surroundings) to see the wake and the jets.",
                 icon="ERROR")

        # -- the thrusters
        n = len(vw.thrusters)
        body = fold(layout, "fr_vessel_thrusters", f"Thrusters ({n})" if n else "Thrusters", "FORCE_VORTEX")
        if body:
            row = body.row(align=True)
            row.operator("fresing.vessel_thrusters_find", text="Find thrusters", icon="VIEWZOOM")
            row.operator("fresing.vessel_thruster_add", text="", icon="ADD")
            row.operator("fresing.vessel_thruster_remove", text="", icon="REMOVE")
            if n:
                body.template_list("FRESING_UL_vessel_thrusters", "", v, "thrusters", vw, "thrusters_index",
                                   rows=list_rows(n, 2, 6))
                if 0 <= vw.thrusters_index < n:
                    th = vw.thrusters[vw.thrusters_index]
                    col = split_props(body)
                    col.prop_search(th, "joint", s, "joints", text="Propeller")
                    col.prop(th, "kind", text="Kind")
                    if th.kind == "AZIMUTH":
                        col.prop_search(th, "steer", s, "joints", text="Steer joint")
                    col.prop(th, "rpm", text="Full speed (rpm)")
                    col.prop(th, "reverse", text="Turns the other way")
            else:
                wrap(body, context, "Or pick a propeller's joint in 4 Motion > Joints and press +.", icon="INFO")


PANELS = (FRESING_PT_vessel_motion, FRESING_PT_vessel_work)
CLASSES = (FRESING_UL_vessel_still, FRESING_UL_vessel_thrusters) + PANELS
