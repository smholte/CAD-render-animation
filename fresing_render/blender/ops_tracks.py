"""Operators for tracks and belts (4 Motion > Tracks and belts, task 0079).

The work is in tracks.py; here is what a button does with clicks. **Add track** starts a click picker with the hover
highlight (hover.py) that takes three kinds of click in turn, the status bar saying which: the wheels round the loop
(Enter when all are clicked), one link of the chain, then a pad or plate if the links carry them (Enter: done). The
same button runs without a mouse with ``"EXEC_DEFAULT"`` and the parts' object names in ``wheels``, ``chain`` and
``riders`` (the test tour, the tests, the demo). A refusal changes nothing: what tracks.py refuses is shown as an
error with its sentence.
"""

from __future__ import annotations

import bpy
from bpy.props import StringProperty

from ..core.words import plural
from . import hover, joints, tracks
from .ops_flex import _name, _say, _select
from .ops_paths import MOTOR_SPEED, MOTOR_TIME, _redraw

_KEYS = "  Esc / right-click: cancel.  Middle mouse / scroll: move the view"
SEP = ";"


def _item(context):
    return tracks.active(context.scene)


def _names(text: str) -> list:
    return [t.strip() for t in str(text).split(SEP) if t.strip()]


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


def add_motor_step(scene, item):
    """A Run motor step on the track's speed joint at the end of the selected animation (a new one when there is
    none): 10 m/min for 5 s. Returns (animation, step)."""
    from . import animation
    s = scene.fresing
    a = animation.active(scene)
    if a is None:
        name = animation.unique_name(scene)
        a = s.animations.add()
        a.name = name
        s.animations_index = len(s.animations) - 1
    start = max((animation.block_end(b) for b in a.blocks), default=0.0)
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", item.joint, round(start, 2), MOTOR_TIME, "LINEAR"
    b.speed_mmin = MOTOR_SPEED
    a.blocks_index = len(a.blocks) - 1
    return a, b


class FRESING_OT_track_add(_Op, bpy.types.Operator):
    """Makes a track or belt run: its links, pads and plates go round its wheels with the cable (or a joint you
    pick) and the wheels turn with them. Press this, then click the wheels round the loop and press Enter, then
    click one link of the chain, then a pad or plate if it has them, and press Enter. Esc cancels"""

    bl_idname = "fresing.track_add"
    bl_label = "Add track"

    wheels: StringProperty(name="Wheels", options={"SKIP_SAVE", "HIDDEN"},
                           description="The wheels' object names, separated by ';' (scripts and tests). Empty: "
                                       "clicks in the 3D view")
    chain: StringProperty(name="Link", options={"SKIP_SAVE", "HIDDEN"},
                          description="One link of the chain (its object name)")
    riders: StringProperty(name="Pads and plates", options={"SKIP_SAVE", "HIDDEN"},
                           description="One pad, one plate … (object names separated by ';'); their copies ride "
                                       "along")
    joint: StringProperty(name="Speed", options={"SKIP_SAVE", "HIDDEN"},
                          description="The joint the track runs with. Empty: the cable that runs nearest it, else "
                                      "a new joint")

    # ---- the click picker -------------------------------------------------------------------------------------
    def _prompt(self) -> str:
        if self._phase == "WHEELS":
            n = len(self._wheels)
            if n < 2:
                return f"Click the wheels round the loop: sprockets, idlers, rollers ({n} so far)."
            return f"{plural(n, 'wheel')} clicked: click the next one, or press Enter when all are clicked."
        if self._phase == "LINK":
            return "Click one link of the chain (a part with a pin or hole at each end)."
        n = len(self._riders)
        return (f"Click a pad or plate that rides on the links ({n} so far), or press Enter: done." if n else
                "Click a pad or plate that rides on the links, or press Enter if it has none.")

    def _note(self, ob, name):
        if self._phase == "WHEELS":
            return f"Wheel {len(self._wheels) + 1}: {name}"
        if self._phase == "LINK":
            return f"Link: {name}"
        return f"Rides on the links: {name}"

    def _refuse(self, ob):
        taken = {o.name for o in tracks.track_parts(bpy.context.scene)}
        if ob.name in taken:
            return "is part of a track already"
        if ob.name in self._wheels or ob.name == self._chain or ob.name in self._riders:
            return "was clicked already"
        if self._phase == "WHEELS" and tracks.wheel_axis(ob) is None:
            return "has no round face: click a sprocket, idler or roller"
        if self._phase == "LINK" and tracks.link_hinges(ob) is None:
            return "has no pin or hole at each end: click a link of the chain"
        return ""

    def invoke(self, context, event):
        if self.chain:
            return self.execute(context)
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        self._phase, self._wheels, self._chain, self._riders = "WHEELS", [], "", []
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, self._prompt() + _KEYS, point=True,
                    note=lambda ob, name, *_a: self._note(ob, name),
                    refuse=lambda ob, *_a: self._refuse(ob))
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def _next(self, context):
        hover.prompt(context, self._prompt() + _KEYS)
        _redraw(context)

    def modal(self, context, event):
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type in {"RET", "NUMPAD_ENTER", "SPACE"} and event.value == "PRESS":
            if self._phase == "WHEELS":
                if len(self._wheels) < 2:
                    hover.prompt(context, "A track needs at least 2 wheels. " + self._prompt() + _KEYS)
                    return {"RUNNING_MODAL"}
                self._phase = "LINK"
                self._next(context)
                return {"RUNNING_MODAL"}
            if self._phase == "RIDERS":
                self._end(context)
                return self._make(context)
            return {"RUNNING_MODAL"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            hover.prompt(context, "Missed the model. " + self._prompt() + _KEYS)
            return {"RUNNING_MODAL"}
        ob = res[0]
        why = self._refuse(ob)
        if why:
            hover.prompt(context, f"'{_name(ob)}' {why}. " + self._prompt() + _KEYS)
            return {"RUNNING_MODAL"}
        if self._phase == "WHEELS":
            self._wheels.append(ob.name)
        elif self._phase == "LINK":
            self._chain = ob.name
            self._phase = "RIDERS"
        else:
            self._riders.append(ob.name)
        self._next(context)
        return {"RUNNING_MODAL"}

    def _make(self, context):
        self.wheels = SEP.join(self._wheels)
        self.chain = self._chain
        self.riders = SEP.join(self._riders)
        result = self.execute(context)
        _redraw(context)
        return result

    # ---- the work ---------------------------------------------------------------------------------------------
    def execute(self, context):
        scene = context.scene
        objs = bpy.data.objects
        wheels = [objs.get(n) for n in _names(self.wheels)]
        chain = objs.get(self.chain) if self.chain else None
        riders = [objs.get(n) for n in _names(self.riders)]
        missing = [n for n, o in zip(_names(self.wheels), wheels) if o is None]
        missing += [self.chain] if self.chain and chain is None else []
        missing += [n for n, o in zip(_names(self.riders), riders) if o is None]
        if missing:
            _say(context, self, f"There is no part '{missing[0]}'", "ERROR")
            return {"CANCELLED"}
        if chain is None:
            _say(context, self, "Press this in the 3D view, then click the wheels, a link and the pads", "WARNING")
            return {"CANCELLED"}
        try:
            item = tracks.add(scene, wheels, chain, riders, joint=self.joint)
        except tracks.TrackError as exc:
            _say(context, self, str(exc), "ERROR")
            return {"CANCELLED"}
        except Exception as exc:                      # noqa: BLE001 - a fault in the app: named, in full on the console
            import traceback
            traceback.print_exc()
            _say(context, self, f"The track could not be made (a fault in the app: {type(exc).__name__}: {exc})",
                 "ERROR")
            return {"CANCELLED"}
        notes = [n for n in item.notes.split("\n") if n]
        for n in notes[1:4]:
            self.report({"INFO"}, n)
        text = (f"Track '{tracks.label(item)}': {plural(item.links, 'link')} and {plural(item.parts - item.links, 'part')}"
                f" riding on them run round {plural(len(item.wheels), 'wheel')} with '{item.joint}'")
        _say(context, self, text + (f". {notes[0]}" if notes else ""))
        return {"FINISHED"}


class FRESING_OT_track_remove(_NeedsItem, bpy.types.Operator):
    """Takes the chosen track off the list. Its links, pads and plates show exactly as in the CAD file again and
    the joints the app made for it go; joints you made yourself stay. Nothing is deleted from the model"""

    bl_idname = "fresing.track_remove"
    bl_label = "Remove track"

    def execute(self, context):
        scene = context.scene
        name = tracks.label(_item(context))
        tracks.remove(scene, scene.fresing.tracks_index)
        _say(context, self, f"Track '{name}' removed from the list: it shows as in the CAD file again")
        return {"FINISHED"}


class FRESING_OT_track_select(_NeedsItem, bpy.types.Operator):
    """Selects the chosen track's links, pads and plates in the 3D view. So you can see which track of the machine
    this line of the list is"""

    bl_idname = "fresing.track_select"
    bl_label = "Select"
    bl_options = {"REGISTER"}

    def execute(self, context):
        item = _item(context)
        if not _select(context, tracks.parts_of(context.scene, item)):
            _say(context, self, f"'{tracks.label(item)}' is hidden or its parts are gone: nothing to select",
                 "WARNING")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_track_motor_step(_NeedsItem, bpy.types.Operator):
    """Adds a step 'Run motor' on this track's speed joint to the selected animation: 10 m/min for 5 seconds.
    Then set the speed and the time in 6 Animation and press Build animation: the pads run round and the wheels
    turn"""

    bl_idname = "fresing.track_motor_step"
    bl_label = "Add a Run motor step"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        item = _item(context)
        return bool(item.joint) and joints.find(context.scene, item.joint) is not None

    def execute(self, context):
        item = _item(context)
        a, b = add_motor_step(context.scene, item)
        _say(context, self, f"Step 'Run motor' added to animation '{a.name}': '{item.joint}' runs at "
             f"{MOTOR_SPEED:.0f} m/min for {b.duration:.0f} s. Set it in 6 Animation, then press Build animation")
        return {"FINISHED"}


CLASSES = (FRESING_OT_track_add, FRESING_OT_track_remove, FRESING_OT_track_select, FRESING_OT_track_motor_step)
