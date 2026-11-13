"""Operators for drums and carousels (4 Motion > Drums and carousels, task 0080).

The work is in spool.py; here is what a button does with a click. Add drum / Add carousel start a click picker with
the hover highlight (hover.py, the picker of ops_paths): the barrel or turntable is clicked, its round face gives the
axis when the app must make the turning joint. The same buttons run without a mouse with ``"EXEC_DEFAULT"`` and
``part`` = the object's name (the test tour, the tests, scripts). A refusal changes nothing: its sentence is shown.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from . import hover, joints, paths, spool
from .ops_flex import _say, _select
from .ops_paths import _KEYS, _redraw, _refuse

WHAT = {"DRUM": "drum", "CAROUSEL": "carousel"}


def _item(context):
    return spool.active(context.scene)


def cable_for(context) -> str:
    """The cable a new spool is for: the one chosen in Cables and paths (else the only one)."""
    scene = context.scene
    it = paths.active(scene)
    if it is None and len(scene.fresing.cables) == 1:
        it = scene.fresing.cables[0]
    return it.name if it is not None else ""


class _Op:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene is not None and hasattr(scene, "fresing") and scene.fresing.model_count > 0


class _NeedsItem(_Op):
    @classmethod
    def poll(cls, context):
        return super().poll(context) and _item(context) is not None


class FRESING_OT_spool_add(_Op, bpy.types.Operator):
    """Makes the cable chosen in Cables and paths come off a drum or carousel: click the drum's barrel or the
    carousel's turntable. The app reads its size and how much cable is on it, makes it turn with the cable speed
    layer by layer and draws the cable on it"""

    bl_idname = "fresing.spool_add"
    bl_label = "Add drum or carousel"

    kind: EnumProperty(name="Kind", items=[("DRUM", "Drum", "A winch or reel drum"),
                                           ("CAROUSEL", "Carousel", "A turntable with a coil")], default="DRUM",
                       options={"SKIP_SAVE"})
    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"},
                         description="The barrel or turntable (the name of its object). Empty: a click in the 3D view")
    cable: StringProperty(name="Cable", options={"SKIP_SAVE", "HIDDEN"},
                          description="The cable that comes off it. Empty: the one chosen in Cables and paths")

    @classmethod
    def description(cls, context, props):
        if props is not None and props.kind == "CAROUSEL":
            return ("Makes the cable chosen in Cables and paths come off a carousel: click the turntable. The app "
                    "reads the coil, makes the carousel turn with the cable speed and draws the top layer getting "
                    "smaller turn by turn")
        return ("Makes the cable chosen in Cables and paths come off a winch or reel drum: click the drum's barrel. "
                "The app reads the drum and how much cable is on it, makes it turn with the cable speed and draws "
                "the wraps coming off layer by layer")

    def _cable(self, context) -> str:
        return self.cable or cable_for(context)

    def invoke(self, context, event):
        if self.part:
            return self.execute(context)
        if not self._cable(context):
            _say(context, self, "First add the cable in 4 Motion > Cables and paths and choose it in its list",
                 "WARNING")
            return {"CANCELLED"}
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        self.prompt = f"Click the {'turntable' if self.kind == 'CAROUSEL' else 'drum barrel'}."
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, self.prompt + " " + _KEYS, point=True,
                    note=lambda ob, name, *_a: f"{WHAT[self.kind].capitalize()}: {name}")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            hover.prompt(context, "Missed the model. " + self.prompt + "  Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        self._end(context)
        axis = None
        try:
            o, d, _desc = joints.axis_from_hit(ob, index, loc, normal)
            axis = (o, d)
        except Exception:                               # noqa: BLE001
            pass
        result = self.picked(context, ob, axis)
        _redraw(context)
        return result

    def execute(self, context):
        ob = bpy.data.objects.get(self.part) if self.part else None
        if ob is None:
            _say(context, self, f"There is no part '{self.part}'" if self.part else
                 f"Click the {WHAT[self.kind]} in the 3D view after pressing this", "WARNING")
            return {"CANCELLED"}
        return self.picked(context, ob, None)

    def picked(self, context, ob, axis):
        cable = self._cable(context)
        if not cable:
            _say(context, self, "First add the cable in 4 Motion > Cables and paths", "WARNING")
            return {"CANCELLED"}
        try:
            sp = spool.add(context.scene, self.kind, ob, cable, axis=axis)
        except (spool.SpoolError, RuntimeError) as exc:
            return _refuse(context, self, exc)
        text, _icon = spool.status(context.scene, sp, write=True)
        _say(context, self, f"'{spool.label(sp)}': {text}")
        return {"FINISHED"}


class FRESING_OT_spool_remove(_NeedsItem, bpy.types.Operator):
    """Takes the chosen drum or carousel off the list: the cable starts as drawn in the CAD file again, the coil
    shows its CAD shape and the joints that followed the layer move by themselves"""

    bl_idname = "fresing.spool_remove"
    bl_label = "Remove drum or carousel"

    def execute(self, context):
        scene = context.scene
        name = spool.label(_item(context))
        spool.remove(scene, scene.fresing.spools_index)
        _say(context, self, f"'{name}' removed")
        return {"FINISHED"}


class FRESING_OT_spool_select(_NeedsItem, bpy.types.Operator):
    """Selects the drum's barrel or the carousel's turntable in the 3D view"""

    bl_idname = "fresing.spool_select"
    bl_label = "Select its part"

    def execute(self, context):
        sp = _item(context)
        if sp.part is None:
            return {"CANCELLED"}
        _select(context, [sp.part])
        return {"FINISHED"}


_ITEMS: list = []           # the joint list's strings: Blender keeps no reference to a dynamic list of its own


def _joint_items(self, context):
    scene = context.scene
    sp = spool.active(scene) if scene is not None else None
    out = []
    if sp is not None:
        taken = {f.joint for f in sp.followers} | {sp.joint}
        it = paths.find(scene, sp.cable)
        if it is not None:
            taken.add(it.joint)
        for j in scene.fresing.joints:
            if j.name in taken or j.motion is None:
                continue
            kind = "slide" if j.kind == "SLIDE" else "turn"
            out.append((j.name, j.name, f"'{j.name}' ({kind}) follows where the cable leaves the "
                                        f"{sp.kind.lower()}"))
    if not out:
        out = [("", "No joint", "There is no other joint: make the level wind's or arm's joint first")]
    _ITEMS[:] = out
    return _ITEMS


class FRESING_OT_spool_follower_add(_NeedsItem, bpy.types.Operator):
    """Makes a joint follow where the cable leaves the drum or carousel: a level wind (a slide along the drum)
    goes back and forth with the wraps, a loading arm swings over the turn being paid out, a guide's swivel turns
    along it. Pick the joint from the list"""

    bl_idname = "fresing.spool_follower_add"
    bl_label = "This joint follows the layer"
    bl_property = "joint"

    joint: EnumProperty(name="Joint", items=_joint_items, description="The joint that follows the layer")

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        sp = _item(context)
        name = str(self.joint)                      # (read once: the list may be made again meanwhile)
        if not name:
            return {"CANCELLED"}
        try:
            mode = spool.add_follower(context.scene, sp, name)
        except (spool.SpoolError, RuntimeError) as exc:
            return _refuse(context, self, exc)
        words = {"ACROSS": "goes along the drum with the wraps", "ARM": "swings over the turn being paid out",
                 "ALONG": "turns along the turn being paid out"}
        _say(context, self, f"'{name}' {words.get(mode, 'follows the layer')}")
        return {"FINISHED"}


class FRESING_OT_spool_follower_remove(_NeedsItem, bpy.types.Operator):
    """The joint no longer follows the layer: it moves by itself again, where it is now"""

    bl_idname = "fresing.spool_follower_remove"
    bl_label = "Stop following"

    index: IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        sp = _item(context)
        k = self.index if self.index >= 0 else sp.followers_index
        if not 0 <= k < len(sp.followers):
            return {"CANCELLED"}
        name = sp.followers[k].joint
        try:
            spool.remove_follower(context.scene, sp, k)
        except (spool.SpoolError, RuntimeError) as exc:
            return _refuse(context, self, exc)
        _say(context, self, f"'{name}' moves by itself again")
        return {"FINISHED"}


class FRESING_OT_spool_read(_NeedsItem, bpy.types.Operator):
    """Reads the drum or carousel again from the model and the CAD cable: its size, its layers and how much cable
    is on it (a length you typed is kept)"""

    bl_idname = "fresing.spool_read"
    bl_label = "Read it again"

    def execute(self, context):
        scene = context.scene
        sp = _item(context)
        try:
            spool._setup(scene, sp, read=True)
        except (spool.SpoolError, RuntimeError) as exc:
            return _refuse(context, self, exc)
        text, _icon = spool.status(scene, spool.active(scene), write=True)
        _say(context, self, text)
        return {"FINISHED"}


CLASSES = (FRESING_OT_spool_add, FRESING_OT_spool_remove, FRESING_OT_spool_select, FRESING_OT_spool_follower_add,
           FRESING_OT_spool_follower_remove, FRESING_OT_spool_read)

