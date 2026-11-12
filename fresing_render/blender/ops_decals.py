"""Buttons of 3 Looks > Logos & stickers (task 0024): add a decal with a click, move it with the
mouse, fit, upright, remove, every copy / this copy, fonts and the logo library."""

from __future__ import annotations

import math
import os

import bpy
from bpy.props import EnumProperty, StringProperty
from mathutils import Vector

from . import build, decals, files, hover
from .ops_panels import _region_under_mouse


def _ray(context, event):
    """(object, polygon, location, normal, region data) under the mouse in a 3D view, or None."""
    from bpy_extras import view3d_utils
    region, rv3d = _region_under_mouse(context, event)
    if region is None:
        return None
    coord = (event.mouse_x - region.x, event.mouse_y - region.y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    depsgraph = context.evaluated_depsgraph_get()
    hit, loc, normal, index, ob, _m = context.scene.ray_cast(depsgraph, origin, direction)
    if not hit or ob is None:
        return None
    return getattr(ob, "original", ob), index, loc, normal, rv3d


def _view_up(rv3d):
    return tuple(rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))) if rv3d is not None else None


def _redraw(context):
    for area in context.window.screen.areas:
        if area.type in ("VIEW_3D", "PROPERTIES"):
            area.tag_redraw()


def _status(context, text):
    try:
        context.workspace.status_text_set(text)
    except Exception:
        pass


def _show_part(context, part) -> None:
    """Make the part the clicked one, so the list shows its decals."""
    try:
        for ob in context.selected_objects:
            ob.select_set(False)
        part.select_set(True)
        context.view_layer.objects.active = part
    except RuntimeError:
        pass


def _item(key: str):
    return decals.find(key)


# =============================================================================
# adding
# =============================================================================


def settings_problem(d) -> str:
    """Why 'Add decal' cannot start yet ('' = it can)."""
    if d.kind == "PICTURE":
        path = bpy.path.abspath(d.picture) if d.picture else ""
        if not path:
            return "Pick a picture file first (or a logo from the library)"
        if not os.path.isfile(path):
            return f"The picture file was not found: {path}"
    if d.kind == "TEXT" and not d.text.strip():
        return "Type the text first"
    return ""


def _decal_note(part, name, face, _loc, _normal) -> str:
    """The hover note of Add decal: which part, and whether the decal lies flat or wraps round the face."""
    how = "wraps round" if face >= 0 and decals.wraps_round(part, face) else "lies flat"
    return f"Decal on {name} – {how}"


class FRESING_OT_decal_add(bpy.types.Operator):
    """Puts the picture, text or sticker chosen above on the model: after pressing, click the spot on a part
    where its centre should be. It lands flat on that face, upright. Esc or right-click cancels"""

    bl_idname = "fresing.decal_add"
    bl_label = "Add decal"
    bl_options = {"REGISTER", "UNDO"}

    _HINT = "Add decal: click the spot on the model for its centre  ·  Esc / right-click: cancel"

    @classmethod
    def poll(cls, context):
        return context.window is not None and context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        d = context.scene.fresing_decal
        problem = settings_problem(d)
        if problem:
            self.report({"WARNING"}, problem)
            return {"CANCELLED"}
        if d.placing:                                   # pressed again: stop
            d.placing = False
            return {"CANCELLED"}
        d.placing = True
        context.window_manager.modal_handler_add(self)
        hover.start(context, self, self._HINT, point=True, note=_decal_note)
        context.window.cursor_modal_set("CROSSHAIR")
        _redraw(context)
        return {"RUNNING_MODAL"}

    def _end(self, context, result):
        context.scene.fresing_decal.placing = False
        hover.end(self, context)
        _status(context, None)
        context.window.cursor_modal_restore()
        _redraw(context)
        return result

    def modal(self, context, event):
        d = context.scene.fresing_decal
        hover.on_event(self, context, event)
        if not d.placing:
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
            if spot is None or spot[1] < 0:
                self.report({"WARNING"}, "Click on a part of the model")
                return {"RUNNING_MODAL"}
            part, face, point, normal = spot
            try:
                item = decals.add(part, face, point, normal, d.kind, picture=d.picture, text=d.text,
                                  sticker=d.sticker, only_copy=d.only_copy, view_up=_view_up(hit[4]))
            except Exception as exc:                  # e.g. a picture file Blender cannot read
                self.report({"ERROR"}, f"Could not add the decal: {exc}")
                return self._end(context, {"CANCELLED"})
            d.active = item.key
            _show_part(context, part)
            where = "this copy of " if d.only_copy else ""
            self.report({"INFO"}, f"'{item.name}' put on {where}{part.get(build.PROP_NAME, part.name)} "
                                  f"({decals.size_text(item)}): move, turn and size it below")
            return self._end(context, {"FINISHED"})
        return {"PASS_THROUGH"}                         # turn, pan and zoom the view as usual


class FRESING_OT_decal_add_cancel(bpy.types.Operator):
    """Stop adding a decal (Esc or right-click in the view does the same)"""

    bl_idname = "fresing.decal_add_cancel"
    bl_label = "Cancel"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        context.scene.fresing_decal.placing = False
        return {"FINISHED"}


# =============================================================================
# moving with the mouse
# =============================================================================

_KEEP = ("face", "anchor", "normal", "up", "offset_x", "offset_y", "angle", "width", "height", "lost")


class FRESING_OT_decal_move(bpy.types.Operator):
    """Moves this decal with the mouse: it follows the mouse over its part (also onto another face of it).
    Mouse wheel turns it, Ctrl+wheel makes it bigger or smaller. Click to put it down; Esc puts it back"""

    bl_idname = "fresing.decal_move"
    bl_label = "Move with the mouse"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    _HINT = ("Move decal: move the mouse over its part  ·  wheel: turn  ·  Ctrl+wheel: size  ·  click: done  ·  "
             "Esc: put it back")

    def invoke(self, context, event):
        item = _item(self.key)
        if item is None or context.area is None:
            return {"CANCELLED"}
        self.saved = {k: (tuple(getattr(item, k)) if k in ("anchor", "normal", "up") else getattr(item, k))
                      for k in _KEEP}
        self.parts = {p.name for p in decals.users(item)}
        self.last = None
        context.window_manager.modal_handler_add(self)
        _status(context, self._HINT)
        context.window.cursor_modal_set("HAND")
        return {"RUNNING_MODAL"}

    def _end(self, context, result):
        _status(context, None)
        context.window.cursor_modal_restore()
        _redraw(context)
        return result

    def _put_back(self, item):
        for k, v in self.saved.items():
            decals._set_quiet(item, k, v)
        decals.rebuild(item)
        decals.sync_item(item)

    def modal(self, context, event):
        item = _item(self.key)
        if item is None:
            return self._end(context, {"CANCELLED"})
        if event.value == "PRESS" and event.type in {"ESC", "RIGHTMOUSE"}:
            self._put_back(item)
            return self._end(context, {"CANCELLED"})
        if event.value == "PRESS" and event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            return self._end(context, {"FINISHED"})
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and event.value == "PRESS":
            sign = 1.0 if event.type == "WHEELUPMOUSE" else -1.0
            if event.ctrl:
                f = 1.1 if sign > 0 else 1 / 1.1
                decals._set_quiet(item, "width", max(decals.MIN_SIZE, item.width * f))
                decals._set_quiet(item, "height", max(decals.MIN_SIZE, item.height * f))
            else:
                decals._set_quiet(item, "angle", item.angle + sign * math.radians(5.0 if event.shift else 15.0))
            decals.rebuild(item)
            _redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE":
            hit = _ray(context, event)
            spot = decals.surface_hit(*hit[:4]) if hit else None
            if spot is not None and spot[0].name in self.parts and spot[1] >= 0:
                part, face, point, normal = spot
                if self.last is None or face != self.last[0] or (Vector(point) - Vector(self.last[1])).length > 2e-5:
                    self.last = (face, point)
                    decals.place(item, part, face, point, normal)
                    _redraw(context)
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}


# =============================================================================
# small buttons on one decal
# =============================================================================


class _OnDecal:
    bl_options = {"REGISTER", "UNDO"}
    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def item(self):
        return _item(self.key)


class FRESING_OT_decal_fit(_OnDecal, bpy.types.Operator):
    """Makes the decal as big as fits on its face (with a little room round it) and centres it there.
    Its turn and proportions stay"""

    bl_idname = "fresing.decal_fit"
    bl_label = "Fit to face"

    def execute(self, context):
        item = self.item()
        if item is None:
            return {"CANCELLED"}
        decals.fit(item)
        return {"FINISHED"}


class FRESING_OT_decal_upright(_OnDecal, bpy.types.Operator):
    """Turns the decal upright again: its top points up (on a face that looks up or down: away from you
    in the view)"""

    bl_idname = "fresing.decal_upright"
    bl_label = "Upright"

    def execute(self, context):
        item = self.item()
        if item is None:
            return {"CANCELLED"}
        rv3d = getattr(context, "region_data", None)
        if rv3d is None:
            for area in context.window.screen.areas if context.window else []:
                if area.type == "VIEW_3D":
                    rv3d = area.spaces.active.region_3d
                    break
        decals.make_upright(item, _view_up(rv3d))
        return {"FINISHED"}


class FRESING_OT_decal_remove(_OnDecal, bpy.types.Operator):
    """Removes this decal from the part (from every copy when it is on every copy). Ctrl+Z brings it back"""

    bl_idname = "fresing.decal_remove"
    bl_label = "Remove decal"

    def execute(self, context):
        item = self.item()
        if item is None:
            return {"CANCELLED"}
        name = item.name
        decals.remove(item)
        self.report({"INFO"}, f"'{name}' removed")
        return {"FINISHED"}


class FRESING_OT_decal_select(_OnDecal, bpy.types.Operator):
    """Opens this decal's settings in the box below the list"""

    bl_idname = "fresing.decal_select"
    bl_label = "Show this decal"
    bl_options = {"INTERNAL"}

    part: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if properties.part:
            return ("Clicks the part this decal is on, so its decals are listed above with this one's settings "
                    "open below them")
        return "Opens this decal's settings in the box below the list: size, place, turn, colours"

    def execute(self, context):
        context.scene.fresing_decal.active = self.key
        part = bpy.data.objects.get(self.part) if self.part else None
        if part is not None:
            _show_part(context, part)
        return {"FINISHED"}


class FRESING_OT_decal_scope(_OnDecal, bpy.types.Operator):
    """On every copy of the part, or on the clicked copy only (e.g. a serial number differs per copy)"""

    bl_idname = "fresing.decal_scope"
    bl_label = "Every copy / this copy"

    def execute(self, context):
        item = self.item()
        part = context.active_object
        if item is None or part is None or part.get(build.PROP_KIND) != "part":
            return {"CANCELLED"}
        new = decals.set_scope(item, part, decals.on_all_copies(item))
        context.scene.fresing_decal.active = new.key
        self.report({"INFO"}, f"'{new.name}' is now on " + ("every copy" if decals.on_all_copies(new) else
                                                            "this copy only"))
        return {"FINISHED"}


_FONT_ITEMS: list = []


def _font_items(self, context):
    _FONT_ITEMS.clear()
    _FONT_ITEMS.append(("", "The app's own font", "The font that comes with the app"))
    for label, path in decals.fonts_on_this_pc():
        _FONT_ITEMS.append((path, label, path))
    return _FONT_ITEMS


class FRESING_OT_decal_font(_OnDecal, bpy.types.Operator):
    """Choose a font found on this PC for the text of this decal (or pick any font file in the field)"""

    bl_idname = "fresing.decal_font"
    bl_label = "Font"
    bl_property = "font"

    font: EnumProperty(name="Font", items=_font_items)

    def execute(self, context):
        item = self.item()
        if item is None:
            return {"CANCELLED"}
        item.font = self.font
        return {"FINISHED"}


_LIB_ITEMS: list = []


def _library_items(self, context):
    _LIB_ITEMS.clear()
    for label, path in decals.library_pictures():
        _LIB_ITEMS.append((path, label, path))
    if not _LIB_ITEMS:
        _LIB_ITEMS.append(("", "The library has no logos yet", "Put PNG files in the Logos or Stickers folder "
                                                                "of the library (Open the logos folder, below)"))
    return _LIB_ITEMS


class FRESING_OT_decal_library(bpy.types.Operator):
    """Pick a logo or sticker from the library (the Logos and Stickers folders) for the next decal"""

    bl_idname = "fresing.decal_library"
    bl_label = "From the library"
    bl_options = {"INTERNAL"}
    bl_property = "picture"

    picture: EnumProperty(name="Picture", items=_library_items)
    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        if not self.picture:
            return {"CANCELLED"}
        item = _item(self.key) if self.key else None
        if item is not None:
            item.source = self.picture
        else:
            context.scene.fresing_decal.picture = self.picture
        return {"FINISHED"}


class FRESING_OT_decal_open_library(bpy.types.Operator):
    """Opens the library folder for logos in the file manager (made when it is not there yet)"""

    bl_idname = "fresing.decal_open_library"
    bl_label = "Open the logos folder"
    bl_options = {"INTERNAL"}

    which: StringProperty(default="Logos", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.which == "Stickers":
            return ("Opens the library folder for stickers in the file manager (made when it is not there yet). "
                    "Put your own stickers in it as PNG files: they show in the list next to Picture")
        return ("Opens the library folder for logos in the file manager (made when it is not there yet). Put your "
                "company logos in it as PNG files with a see-through background: they show in the list next to "
                "Picture")

    def execute(self, context):
        folder = next((f for f in decals.library_folders() if os.path.basename(f) == self.which),
                      decals.library_folders()[0])
        try:
            os.makedirs(folder, exist_ok=True)
            files.open_path(folder)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open {folder}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, folder)
        return {"FINISHED"}


CLASSES = (FRESING_OT_decal_add, FRESING_OT_decal_add_cancel, FRESING_OT_decal_move, FRESING_OT_decal_fit,
           FRESING_OT_decal_upright, FRESING_OT_decal_remove, FRESING_OT_decal_select, FRESING_OT_decal_scope,
           FRESING_OT_decal_font, FRESING_OT_decal_library, FRESING_OT_decal_open_library)
