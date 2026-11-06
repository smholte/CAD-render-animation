"""Buttons for labels pointing at parts, picture cards and music (task 0025)."""

from __future__ import annotations

import bpy

from . import animation, build, callouts, decals
from .ops_decals import _ray, _redraw, _status
from .ops_panels import _region_under_mouse


class FRESING_OT_callout_add(bpy.types.Operator):
    """Puts a label on the model: after pressing, click the spot on a part where the line should end. The label
    gets the part's name; change the words below. The line stays on that spot of the part when it moves in an
    animation. Esc or right-click cancels"""
    bl_idname = "fresing.callout_add"
    bl_label = "Add label"
    bl_options = {"REGISTER", "UNDO"}

    _HINT = "Add label: click the spot on a part where the line ends  ·  Esc / right-click: cancel"

    @classmethod
    def poll(cls, context):
        return context.window is not None and context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        s = context.scene.fresing
        if s.callout_picking:
            s.callout_picking = False
            return {"CANCELLED"}
        s.callout_picking = True
        context.window_manager.modal_handler_add(self)
        _status(context, self._HINT)
        context.window.cursor_modal_set("CROSSHAIR")
        _redraw(context)
        return {"RUNNING_MODAL"}

    def _end(self, context, result):
        context.scene.fresing.callout_picking = False
        _status(context, None)
        context.window.cursor_modal_restore()
        _redraw(context)
        return result

    def modal(self, context, event):
        s = context.scene.fresing
        if not s.callout_picking:
            return self._end(context, {"CANCELLED"})
        if event.value == "PRESS" and event.type in {"ESC", "RIGHTMOUSE"}:
            region, _rv3d = _region_under_mouse(context, event)
            if event.type == "ESC" or region is not None:
                return self._end(context, {"CANCELLED"})
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            region, _rv3d = _region_under_mouse(context, event)
            if region is None:
                return {"PASS_THROUGH"}                  # buttons in the side panel keep working
            hit = _ray(context, event)
            spot = decals.surface_hit(*hit[:4]) if hit else None
            if spot is None:
                self.report({"WARNING"}, "Click on a part of the model")
                return {"RUNNING_MODAL"}
            part, _face, point, _normal = spot
            item = callouts.add(context.scene, part, point)
            self.report({"INFO"}, f"Label '{item.text}' added: change its words below")
            return self._end(context, {"FINISHED"})
        return {"PASS_THROUGH"}


class FRESING_OT_callout_remove(bpy.types.Operator):
    """Deletes the selected label from the list"""
    bl_idname = "fresing.callout_remove"
    bl_label = "Remove label"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return 0 <= s.callouts_index < len(s.callouts)

    def execute(self, context):
        s = context.scene.fresing
        s.callouts.remove(s.callouts_index)
        s.callouts_index = max(0, min(s.callouts_index, len(s.callouts) - 1))
        return {"FINISHED"}


class FRESING_OT_callout_show(bpy.types.Operator):
    """Selects the part the selected label points at, so you can see where it is in the 3D view"""
    bl_idname = "fresing.callout_show"
    bl_label = "Show the part"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return 0 <= s.callouts_index < len(s.callouts) and s.callouts[s.callouts_index].obj is not None

    def execute(self, context):
        s = context.scene.fresing
        part = s.callouts[s.callouts_index].obj
        try:
            for ob in context.selected_objects:
                ob.select_set(False)
            part.select_set(True)
            context.view_layer.objects.active = part
        except RuntimeError:
            self.report({"WARNING"}, "The part is hidden: show it first")
            return {"CANCELLED"}
        return {"FINISHED"}


def _anim(context):
    return animation.active(context.scene)


class FRESING_OT_card_add(bpy.types.Operator):
    """Adds a picture card to this animation: a photo or diagram shown for a few seconds. Pick its file and
    time below"""
    bl_idname = "fresing.card_add"
    bl_label = "Add picture"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _anim(context) is not None

    def execute(self, context):
        a = _anim(context)
        c = a.cards.add()
        c.name = f"Picture {len(a.cards)}"
        a.cards_index = len(a.cards) - 1
        return {"FINISHED"}


class FRESING_OT_card_remove(bpy.types.Operator):
    """Deletes the selected picture card from this animation"""
    bl_idname = "fresing.card_remove"
    bl_label = "Remove picture"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        a = _anim(context)
        return a is not None and 0 <= a.cards_index < len(a.cards)

    def execute(self, context):
        a = _anim(context)
        a.cards.remove(a.cards_index)
        a.cards_index = max(0, min(a.cards_index, len(a.cards) - 1))
        return {"FINISHED"}


CLASSES = (FRESING_OT_callout_add, FRESING_OT_callout_remove, FRESING_OT_callout_show, FRESING_OT_card_add,
           FRESING_OT_card_remove)
