"""Operators of the X-ray look (3 Looks > X-ray look) and trail lines (6 Animation > Trail lines), task 0073."""

from __future__ import annotations

import bpy
from bpy.props import FloatVectorProperty, StringProperty

from . import build, fade, logic, trails
from .ops_callouts import _PickPart, _redraw


def _parts_under(scene, ob) -> list:
    tree = logic.Tree(scene)
    out = [o for o in [ob] + tree.descendants(ob) if o.type == "MESH" and o.get(build.PROP_KIND) == "part"]
    return out


def _picked(context):
    """The selected subassembly (as Show/Hide steps pick it) and its parts."""
    from .ops_motion import _target_subassembly
    ob = _target_subassembly(context)
    return ob, (_parts_under(context.scene, ob) if ob is not None else [])


class FRESING_OT_xray_selected(bpy.types.Operator):
    """Gives the selected subassembly (or part) the X-ray look: see-through with glowing edges, so what is inside
    or behind shows. Colour and strength are set above. Shows in rendered view, pictures and videos"""
    bl_idname = "fresing.xray_selected"
    bl_label = "X-ray the selected"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def execute(self, context):
        ob, parts = _picked(context)
        if not parts:
            self.report({"WARNING"}, "Select a part or a subassembly first")
            return {"CANCELLED"}
        n = fade.apply_look(context.scene, parts)
        name = ob.get(build.PROP_NAME, ob.name)
        context.scene.fresing.last_message = f"X-ray: {name} ({n} parts)"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_xray_group(bpy.types.Operator):
    """Gives every part of the material group selected above the X-ray look (the parts in it now)"""
    bl_idname = "fresing.xray_group"
    bl_label = "X-ray this group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return 0 <= s.groups_index < len(s.groups)

    def execute(self, context):
        s = context.scene.fresing
        g = s.groups[s.groups_index].name
        parts = [o for o in context.scene.objects if o.get(build.PROP_KIND) == "part" and o.type == "MESH"
                 and o.get(build.PROP_GROUP, "") == g]
        if not parts:
            self.report({"WARNING"}, f"The group '{g}' has no parts")
            return {"CANCELLED"}
        n = fade.apply_look(context.scene, parts)
        s.last_message = f"X-ray: group {g} ({n} parts)"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_xray_clear(bpy.types.Operator):
    """Takes the X-ray look off the selected subassembly (or part): it looks as before"""
    bl_idname = "fresing.xray_clear"
    bl_label = "Back to normal"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ob, parts = _picked(context)
        n = fade.remove_look(context.scene, parts)
        context.scene.fresing.last_message = f"X-ray taken off {n} parts"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_xray_clear_all(bpy.types.Operator):
    """Takes the X-ray look off every part"""
    bl_idname = "fresing.xray_clear_all"
    bl_label = "All back to normal"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = fade.remove_look(context.scene, fade.xray_parts(context.scene))
        context.scene.fresing.last_message = f"X-ray taken off {n} parts"
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# trail lines
# ---------------------------------------------------------------------------

class FRESING_OT_trail_add(bpy.types.Operator):
    """Adds a trail line on the selected part: the path of its origin is drawn as a line at the next Build. A milling
    bit or CNC tool draws from its tip. Pick another point below"""
    bl_idname = "fresing.trail_add"
    bl_label = "Add a trail line"
    bl_options = {"REGISTER", "UNDO"}

    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def execute(self, context):
        ob = bpy.data.objects.get(self.part) if self.part else context.active_object
        if ob is None or ob.get(build.PROP_KIND) != "part":
            self.report({"WARNING"}, "Select a part first (the hook, the tool, the carriage)")
            return {"CANCELLED"}
        t = trails.add(context.scene, ob, "TIP" if trails.tip_of(context.scene, ob) is not None else "ORIGIN")
        context.scene.fresing.last_message = f"Trail line on '{trails.label(t)}': Build to draw it"
        return {"FINISHED"}


class FRESING_OT_trail_remove(bpy.types.Operator):
    """Deletes the selected trail line"""
    bl_idname = "fresing.trail_remove"
    bl_label = "Remove trail line"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return trails.active(context.scene) is not None

    def execute(self, context):
        trails.remove(context.scene, context.scene.fresing.trails_index)
        return {"FINISHED"}


class FRESING_OT_trail_pick_point(_PickPart, bpy.types.Operator):
    """Click the spot on the part that should draw the line (e.g. the hook's eye). It moves with the part"""
    bl_idname = "fresing.trail_pick_point"
    bl_label = "Click the point"
    bl_options = {"REGISTER", "UNDO"}

    point: FloatVectorProperty(size=3, subtype="XYZ", options={"SKIP_SAVE", "HIDDEN"})
    part: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return trails.active(context.scene) is not None

    def invoke(self, context, event):
        return self._start(context, "Click the point on the part that draws the line.  Esc / right-click: cancel")

    def picked(self, context, ob, loc):
        t = trails.active(context.scene)
        if t.part is not ob:
            t.part = ob
            t.part_uid = ob.get(build.PROP_UID, "")
        t.local = tuple(ob.matrix_world.inverted() @ loc)
        t.point = "CLICKED"
        context.scene.fresing.last_message = f"Trail point set on '{ob.get(build.PROP_NAME, ob.name)}': Build again"

    def execute(self, context):                 # scripts and tests: a point in the world on the trail's part
        t = trails.active(context.scene)
        ob = bpy.data.objects.get(self.part) if self.part else t.part
        if ob is None:
            return {"CANCELLED"}
        from mathutils import Vector
        self.picked(context, ob, Vector(self.point))
        return {"FINISHED"}


class FRESING_OT_trail_use_selected(bpy.types.Operator):
    """Uses the selected part for this trail line"""
    bl_idname = "fresing.trail_use_selected"
    bl_label = "Use selected"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return trails.active(context.scene) is not None and ob is not None and ob.get(build.PROP_KIND) == "part"

    def execute(self, context):
        t = trails.active(context.scene)
        ob = context.active_object
        t.part = ob
        t.part_uid = ob.get(build.PROP_UID, "")
        return {"FINISHED"}


CLASSES = (FRESING_OT_xray_selected, FRESING_OT_xray_group, FRESING_OT_xray_clear, FRESING_OT_xray_clear_all,
           FRESING_OT_trail_add, FRESING_OT_trail_remove, FRESING_OT_trail_pick_point, FRESING_OT_trail_use_selected)
