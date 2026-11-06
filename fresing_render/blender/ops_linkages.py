"""Operators for mechanisms (task 0014): pick the base, add a mechanism from the selected links, set the height,
select its parts, remove it."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..core.words import plural
from . import build, joints, linkages
from .ops_motion import selected_movers


def _active(context):
    s = context.scene.fresing
    if 0 <= s.mechanisms_index < len(s.mechanisms):
        return s.mechanisms[s.mechanisms_index]
    return None


def _valid(context) -> bool:
    m = _active(context)
    return m is not None and linkages.is_valid(m)


def _say(context, op, text: str, level: str = "INFO") -> None:
    context.scene.fresing.last_message = text
    op.report({level}, text)


def picked_links(context) -> list:
    """The selected subassemblies that would become the links (the picked base left out)."""
    base = context.scene.fresing.mech_base
    return [o for o in selected_movers(context) if base is None or (o is not base
                                                                    and not joints._is_cad_ancestor(o, base))]


class FRESING_OT_mechanism_pick_base(bpy.types.Operator):
    """Takes the selected subassembly as the base the mechanism stands on (the frame or chassis that does not
    move with it). Click it in the view or in 2 Structure first. Without a base picked, the rest of the
    subassembly the links are in is the base"""

    bl_idname = "fresing.mechanism_pick_base"
    bl_label = "Base"
    bl_options = {"REGISTER", "UNDO"}

    clear: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.clear:
            return "Forgets the picked base: the rest of the subassembly the links are in is the base again"
        return cls.__doc__

    def execute(self, context):
        s = context.scene.fresing
        if self.clear:
            s.mech_base = None
            return {"FINISHED"}
        movers = selected_movers(context)
        if len(movers) != 1:
            _say(context, self, "Select the base only (one subassembly), then press Base", "WARNING")
            return {"CANCELLED"}
        s.mech_base = movers[0]
        _say(context, self, f"Base: {linkages.label(movers[0])}. Now select the moving links")
        return {"FINISHED"}


class FRESING_OT_mechanism_add(bpy.types.Operator):
    """Makes a mechanism from the selected links: the pins are found where two links share a hole or shaft,
    tracks and sliders from the type. Then move it with its drive joint (or the height of a scissor lift)"""

    bl_idname = "fresing.mechanism_add"
    bl_label = "Add mechanism"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(picked_links(context))

    @classmethod
    def description(cls, context, properties):
        kind = context.scene.fresing.mech_kind if context else "OTHER"
        what = {"SCISSOR": "the arms and the platform: each pair of crossing arms is a stage; the rollers run on "
                           "the base and under the platform",
                "FOURBAR": "the crank, the coupler and the rocker (the four pins are found by themselves)",
                "SLIDER": "the crank, the rod and the slider (it slides along its own round face)",
                "OTHER": "every moving link (pins where two links share a hole)"}.get(kind, "the links")
        return (f"Makes a mechanism from the selected subassemblies – {what}. The one clicked last is moved by the "
                "drive joint. Select them first (Ctrl+click)")

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        links = picked_links(context)
        active = context.view_layer.objects.active
        drive = None
        if active is not None:
            for o in links:
                if o is active or joints._is_cad_ancestor(o, active):
                    drive = o
        try:
            m = linkages.create(scene, s.mech_kind, [[o] for o in links], base=s.mech_base, drive=drive)
        except RuntimeError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        j = linkages.input_joint(scene, m)
        n = len(m.links) - 1
        msg = (f"'{m.name}' added: {plural(n, 'link')}, {plural(len(linkages.setup(m)['pins']), 'pin')}. "
               f"Move it with '{j.name}'" + (" or its height" if linkages.has_height(m) else ""))
        extra = m.get("_limits_msg", "")
        if extra:
            msg += f". {extra}"
        s.mech_base = None
        for o in context.selected_objects:
            o.select_set(False)
        _say(context, self, msg)
        return {"FINISHED"}


class FRESING_OT_mechanism_remove(bpy.types.Operator):
    """Removes the mechanism: its links go back to their CAD place. The drive joint goes too when the mechanism
    made it"""

    bl_idname = "fresing.mechanism_remove"
    bl_label = "Remove mechanism"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def execute(self, context):
        m = _active(context)
        if linkages.is_valid(m):
            msg = linkages.remove(context.scene, m)
        else:
            name = m.name
            with joints.cad_pose(context.scene):
                m = linkages.find(context.scene, name)
                for o in linkages.members(m):
                    joints._detach(o)
                for e in linkages.empties(m):
                    bpy.data.objects.remove(e, do_unlink=True)
                s = context.scene.fresing
                s.mechanisms.remove(next(i for i, x in enumerate(s.mechanisms) if x.name == name))
                s.mechanisms_index = max(0, min(s.mechanisms_index, len(s.mechanisms) - 1))
            msg = f"Mechanism '{name}' removed; its parts are back in their place"
        _say(context, self, msg)
        return {"FINISHED"}


class FRESING_OT_mechanism_height(bpy.types.Operator):
    """Puts the scissor lift's platform at its lowest or highest height (the drive joint's limits)"""

    bl_idname = "fresing.mechanism_height"
    bl_label = "Lift height"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(items=[("LOW", "Lowest", "Lowest height"), ("CAD", "CAD", "As in the CAD model"),
                                ("HIGH", "Highest", "Highest height")], default="HIGH", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {"LOW": "Lowers the platform as far as the drive joint's limits allow",
                "CAD": "Puts the lift back at the height of the CAD model (drive joint at 0)",
                "HIGH": "Raises the platform as far as the drive joint's limits allow"}[properties.target]

    @classmethod
    def poll(cls, context):
        return _valid(context) and linkages.has_height(_active(context))

    def execute(self, context):
        scene = context.scene
        m = _active(context)
        j = linkages.input_joint(scene, m)
        if self.target == "CAD":
            joints.set_value(j, 0.0)
        else:
            lo, hi = joints.limits(j)
            sol = linkages.solver(m).copy()
            _lk, h, sign = linkages.linkage_of(m)
            heights = {}
            for v in (lo, hi):
                t = sol.copy()
                try:
                    t.solve(sign * v)
                except Exception:
                    pass
                heights[v] = h.of(t.poses)
            pick = (max if self.target == "HIGH" else min)(heights, key=heights.get)
            joints.set_value(j, pick)
        linkages.refresh(scene, m)
        bpy.context.view_layer.update()
        return {"FINISHED"}


class FRESING_OT_mechanism_select(bpy.types.Operator):
    """Selects every link of the mechanism in the view"""

    bl_idname = "fresing.mechanism_select"
    bl_label = "Select parts"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def execute(self, context):
        m = _active(context)
        for o in context.selected_objects:
            o.select_set(False)
        objs = linkages.all_link_objs(m)
        for o in objs:
            for d in [o] + list(o.children_recursive):
                if d.get(build.PROP_KIND) in build.MODEL_KINDS and d.visible_get():
                    d.select_set(True)
        if objs:
            context.view_layer.objects.active = objs[0]
        return {"FINISHED"}


class FRESING_OT_mechanism_drive_joint(bpy.types.Operator):
    """Shows the mechanism's drive joint in the joint list above (its limits, its name, couplings)"""

    bl_idname = "fresing.mechanism_drive_joint"
    bl_label = "Show drive joint"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def execute(self, context):
        s = context.scene.fresing
        j = linkages.input_joint(context.scene, _active(context))
        s.joints_index = next(i for i, x in enumerate(s.joints) if x.name == j.name)
        return {"FINISHED"}


CLASSES = (FRESING_OT_mechanism_pick_base, FRESING_OT_mechanism_add, FRESING_OT_mechanism_remove,
           FRESING_OT_mechanism_height, FRESING_OT_mechanism_select, FRESING_OT_mechanism_drive_joint)
