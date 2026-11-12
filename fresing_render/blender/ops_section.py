"""Operators of 3 Looks > Cutaway (task 0086)."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty

from ..core.words import plural
from . import build, section
from .ops_callouts import _redraw


def _selected_target(context):
    """The selected subassembly or part (as the X-ray look picks it), or None."""
    from .ops_motion import _target_subassembly
    ob = context.active_object
    if ob is None or not ob.select_get() or ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
        s = context.scene.fresing
        if not (0 <= s.tree_index < len(s.tree) and s.tree[s.tree_index].obj is not None):
            return None
    return _target_subassembly(context)


def _group(context):
    s = context.scene.fresing
    return s.groups[s.groups_index].name if 0 <= s.groups_index < len(s.groups) else ""


def _targets(context, what: str) -> tuple[list, str]:
    """([(kind, object, group name)], label) for 'SELECTED', 'GROUP' or 'MODEL'; ([], reason) when there is none."""
    scene = context.scene
    if what == "SELECTED":
        ob = _selected_target(context)
        if ob is None:
            return [], "Select a subassembly or a part first (in the view or in 2 Structure)"
        kind = "MODEL" if ob.get(build.PROP_ROOT) else "PART"
        return [(kind, ob, "")], ob.get(build.PROP_NAME, ob.name)
    if what == "GROUP":
        g = _group(context)
        if not g:
            return [], "Pick a group in the list above first"
        if not any(o.get(build.PROP_GROUP, "") == g for o in build.iter_parts(scene)):
            return [], f"The group '{g}' has no parts"
        return [("GROUP", None, g)], f"group {g}"
    roots = build.model_roots(scene)
    if not roots:
        return [], "Import a model first"
    return [("MODEL", r, "") for r in roots], "the whole model"


WHAT_ITEMS = [("SELECTED", "The selected", "The selected subassembly or part"),
              ("GROUP", "This group", "Every part of the group selected in the list above"),
              ("MODEL", "Whole model", "Every part of the model")]


class FRESING_OT_cut_add(bpy.types.Operator):
    """Adds a cut through the selected subassembly (or the group picked above, or the whole model): the side facing
    you is taken away and the cut faces show the cap colour. Then move its arrow, or set its place below"""
    bl_idname = "fresing.cut_add"
    bl_label = "Add cut"
    bl_options = {"REGISTER", "UNDO"}

    what: EnumProperty(name="What it cuts", items=WHAT_ITEMS, default="SELECTED")

    @classmethod
    def description(cls, context, properties):
        if properties.what == "GROUP":
            return ("Adds a cut through every part of the group picked in the list above: the side facing you is "
                    "taken away and the cut faces show the cap colour")
        if properties.what == "MODEL":
            return ("Adds a cut through the whole model: the side facing you is taken away and the cut faces "
                    "show the cap colour")
        return " ".join(cls.__doc__.split())

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def execute(self, context):
        scene = context.scene
        targets, label = _targets(context, self.what)
        if not targets:
            self.report({"WARNING"}, label)
            return {"CANCELLED"}
        section.view_from(context)                   # the side that faces you in the view goes
        try:
            cut = section.add(scene, targets, scene.fresing.cut_new_shape)
        finally:
            section.VIEW.clear()
        n = len(section.cut_parts(scene, cut))
        scene.fresing.last_message = f"{cut.name}: cuts {label} ({plural(n, 'part')})"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cut_remove(bpy.types.Operator):
    """Removes the cut selected in the list (and its slide joint): its parts look whole again"""
    bl_idname = "fresing.cut_remove"
    bl_label = "Remove cut"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return section.active(context.scene) is not None

    def execute(self, context):
        cut = section.active(context.scene)
        name = cut.name
        section.remove(context.scene, cut)
        context.scene.fresing.last_message = f"{name} removed"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cut_target_add(bpy.types.Operator):
    """Adds the selected subassembly (or the group picked above) to what this cut cuts"""
    bl_idname = "fresing.cut_target_add"
    bl_label = "Cut this too"
    bl_options = {"REGISTER", "UNDO"}

    what: EnumProperty(name="What", items=WHAT_ITEMS[:2], default="SELECTED")

    @classmethod
    def description(cls, context, properties):
        if properties.what == "GROUP":
            return "Adds every part of the group picked in the list above to what this cut cuts"
        return "Adds the selected subassembly or part to what this cut cuts"

    @classmethod
    def poll(cls, context):
        return section.active(context.scene) is not None

    def execute(self, context):
        cut = section.active(context.scene)
        targets, label = _targets(context, self.what)
        if not targets:
            self.report({"WARNING"}, label)
            return {"CANCELLED"}
        for kind, ob, g in targets:
            section.add_target(cut, kind, ob, g)
        section.targets_changed(context.scene)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cut_target_remove(bpy.types.Operator):
    """Takes this one out of what the cut cuts: its parts look whole again"""
    bl_idname = "fresing.cut_target_remove"
    bl_label = "Do not cut this"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        cut = section.active(context.scene)
        if cut is None or not 0 <= self.index < len(cut.targets):
            return {"CANCELLED"}
        cut.targets.remove(self.index)
        section.targets_changed(context.scene)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cut_select_handle(bpy.types.Operator):
    """Selects the cut's arrow in the view, so you can move it (G) or turn it (R) with the mouse. The arrow points to
    the side a plane takes away"""
    bl_idname = "fresing.cut_select_handle"
    bl_label = "Select the arrow"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return section.active(context.scene) is not None

    def execute(self, context):
        scene = context.scene
        cut = section.active(scene)
        section.ensure(scene, cut)
        fr = section.handle(scene, cut)
        if fr is None:
            return {"CANCELLED"}
        for ob in context.selected_objects:
            ob.select_set(False)
        fr.hide_viewport = False
        try:
            fr.hide_set(False)
            fr.select_set(True)
        except RuntimeError:
            self.report({"WARNING"}, "The arrow is in a hidden collection")
            return {"CANCELLED"}
        context.view_layer.objects.active = fr
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cut_replace(bpy.types.Operator):
    """Puts the cut back through the middle of what it cuts, taking away the side that faces you"""
    bl_idname = "fresing.cut_replace"
    bl_label = "To the middle"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return section.active(context.scene) is not None

    def execute(self, context):
        section.view_from(context)
        try:
            section.place_default(context.scene, section.active(context.scene))
        finally:
            section.VIEW.clear()
        _redraw(context)
        return {"FINISHED"}


CLASSES = (FRESING_OT_cut_add, FRESING_OT_cut_remove, FRESING_OT_cut_target_add, FRESING_OT_cut_target_remove,
           FRESING_OT_cut_select_handle, FRESING_OT_cut_replace)
