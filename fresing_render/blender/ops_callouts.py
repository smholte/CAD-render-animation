"""Operators for labels pointing at parts, picture cards (task 0025)."""

from __future__ import annotations

import os

import bpy
from bpy.props import FloatVectorProperty, StringProperty

from ..core import callouts as C
from . import animation, build, callouts, hover


def _redraw(context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


class _PickPart:
    """Shared by the two operators that ask for a click on a part."""

    _NOTE = "Point here"            # what the click does, for the hover note; "{name}" is the part's name

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def _start(self, context, text: str):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, text, point=True, note=lambda ob, name, *_a: self._NOTE.format(name=name))
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None or res[0].get(build.PROP_KIND) != "part":
            hover.prompt(context, "Missed the machine: click a part. Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        self.picked(context, ob, loc)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_callout_add(_PickPart, bpy.types.Operator):
    """Adds a label: click the spot on a part that it should point at. Then type its words below"""
    bl_idname = "fresing.callout_add"
    bl_label = "Add a label"
    bl_options = {"REGISTER", "UNDO"}
    _NOTE = "Label points at {name}"

    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"})
    point: FloatVectorProperty(size=3, subtype="XYZ", options={"SKIP_SAVE", "HIDDEN"})
    text: StringProperty(name="Text", default="Label", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        return self._start(context, "Click the spot on the machine that the label should point at.  "
                                    "Esc / right-click: cancel.  Middle mouse / scroll: move the view")

    def picked(self, context, ob, loc):
        c = callouts.add(context.scene, ob, loc, self.text)
        context.scene.fresing.last_message = f"Label added on '{ob.name}'"
        self.report({"INFO"}, f"Label added: type its words below ({c.text})")

    def execute(self, context):                 # scripts and tests
        ob = bpy.data.objects.get(self.part)
        if ob is None:
            self.report({"WARNING"}, "Click a part in the 3D view (or give the part's name)")
            return {"CANCELLED"}
        callouts.add(context.scene, ob, self.point if any(self.point) else ob.matrix_world.translation, self.text)
        return {"FINISHED"}


class FRESING_OT_callout_move(_PickPart, bpy.types.Operator):
    """Moves the point of the selected label: click a new spot on a part"""
    bl_idname = "fresing.callout_move"
    bl_label = "Move the point"
    bl_options = {"REGISTER", "UNDO"}
    _NOTE = "Label point moves to {name}"

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return 0 <= s.callouts_index < len(s.callouts)

    def invoke(self, context, event):
        return self._start(context, "Click the new spot for the selected label.  Esc / right-click: cancel")

    def picked(self, context, ob, loc):
        s = context.scene.fresing
        callouts.move_point(s.callouts[s.callouts_index], ob, loc)

    def execute(self, context):
        return {"CANCELLED"}


class FRESING_OT_callout_remove(bpy.types.Operator):
    """Deletes the selected label"""
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


class FRESING_OT_callout_show_part(bpy.types.Operator):
    """Selects the part that the selected label points at, so you can see which one it is"""
    bl_idname = "fresing.callout_show_part"
    bl_label = "Select its part"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return 0 <= s.callouts_index < len(s.callouts) and s.callouts[s.callouts_index].part is not None

    def execute(self, context):
        s = context.scene.fresing
        ob = s.callouts[s.callouts_index].part
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


class FRESING_OT_card_add(bpy.types.Operator):
    """Adds a picture to show in the selected animation: pick a photo or diagram. It appears for a few seconds
    over the animation, in the whole picture or in a corner"""
    bl_idname = "fresing.card_add"
    bl_label = "Add a picture"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.webp", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return animation.active(context.scene) is not None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        a = animation.active(context.scene)
        path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(path) or not C.is_picture(path):
            self.report({"ERROR"}, "Pick a picture file (PNG, JPG, TIF, BMP or WebP)")
            return {"CANCELLED"}
        c = a.cards.add()
        c.path = self.filepath
        c.name = os.path.splitext(os.path.basename(path))[0]
        a.cards_index = len(a.cards) - 1
        return {"FINISHED"}


class FRESING_OT_card_remove(bpy.types.Operator):
    """Takes the selected picture out of the animation (the file stays where it is)"""
    bl_idname = "fresing.card_remove"
    bl_label = "Remove picture"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        a = animation.active(context.scene)
        return a is not None and 0 <= a.cards_index < len(a.cards)

    def execute(self, context):
        a = animation.active(context.scene)
        a.cards.remove(a.cards_index)
        a.cards_index = max(0, min(a.cards_index, len(a.cards) - 1))
        return {"FINISHED"}


CLASSES = (FRESING_OT_callout_add, FRESING_OT_callout_move, FRESING_OT_callout_remove,
           FRESING_OT_callout_show_part, FRESING_OT_card_add, FRESING_OT_card_remove)
