"""Operators for the surroundings and the props for scale (panel 5 Scene & Render, task 0016)."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..core import surroundings as env
from ..core.words import plural
from . import surroundings, world

PROP_ITEMS = [(k, label, desc) for k, (label, desc) in env.PROPS.items()]


class FRESING_OT_env_place(bpy.types.Operator):
    """Puts the surroundings under the machine again: its lowest point on the floor, centred.
    Use it after the machine changed size or place (another model, parts hidden for good)"""

    bl_idname = "fresing.env_place"
    bl_label = "Put on the floor again"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        s.bounds_valid = False
        surroundings.ensure(scene, s, replace=True)
        world.update_floor(scene, s)
        surroundings.put_props_on_floor(scene)
        return {"FINISHED"}


class FRESING_OT_prop_add(bpy.types.Operator):
    """Puts a prop for scale next to the machine, on the floor, and selects it.
    Move it with the arrows in the view (or press G); delete it with X"""

    bl_idname = "fresing.prop_add"
    bl_label = "Add prop"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(name="Prop", items=PROP_ITEMS, default="PERSON")

    @classmethod
    def description(cls, context, properties):
        label, desc = env.PROPS.get(properties.kind, ("", ""))
        detail = desc[:1].lower() + desc[1:]
        return (f"Puts a {label.lower()} next to the machine, on the floor ({detail}). It is selected: move it "
                "with the arrows in the view (or press G), delete it with X")

    def execute(self, context):
        scene = context.scene
        if not scene.fresing.props_visible:
            scene.fresing.props_visible = True
        ob = surroundings.add_prop(scene, self.kind)
        for other in context.selected_objects:
            other.select_set(False)
        try:
            ob.select_set(True)
            context.view_layer.objects.active = ob
        except RuntimeError:
            pass
        return {"FINISHED"}


class FRESING_OT_props_remove(bpy.types.Operator):
    """Deletes every prop for scale (person, container, pallet, barrier). To keep them but not
    show them, untick 'Show props' instead"""

    bl_idname = "fresing.props_remove"
    bl_label = "Delete all props"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(surroundings.props(context.scene))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        n = surroundings.remove_props(context.scene)
        self.report({"INFO"}, f"{plural(n, 'prop')} deleted")
        return {"FINISHED"}


CLASSES = (FRESING_OT_env_place, FRESING_OT_prop_add, FRESING_OT_props_remove)
