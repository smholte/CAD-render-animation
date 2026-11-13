"""Operators for cables and paths (4 Motion > Cables and paths, task 0078).

The work is in paths.py; here is what a button does with the selection or with a click. Three things to know:

* **A button that needs a part asks for a click.** Add cable, Add (+) under "What it touches" and the two end
  buttons start a click picker with the hover highlight (hover.py): the status bar says what to click, Esc cancels.
  Add cable skips the click when the part that is selected is named like a cable (``cable_target``).
* **The same buttons without a mouse.** Each picker also runs with ``"EXEC_DEFAULT"`` and ``part`` = the object's
  name (the test tour, the tests, scripts); the contact picker takes the clicked point in ``point`` (world).
* **A refusal changes nothing.** What paths.py refuses (``PathError``) is shown as an error with its sentence. A
  cable whose part cannot be read is taken off the list again, with the joint that was made for it.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, StringProperty

from ..core.words import plural
from . import animation, flex, hover, joints, paths
from .ops_flex import _name, _say, _select, clicked, selected_parts

KIND_WORDS = {"SHEAVE": "sheave", "ROLLER": "roller", "CHUTE": "chute", "BEND": "bend"}
FLIPS = ("SHEAVE", "CHUTE", "BEND")       # the kinds whose side can be flipped with the button
ROPE_WORDS = ("ROPE", "ROPES", "WIREROPE", "SEIL", "DRAHTSEIL", "STAHLSEIL", "STAALKABEL", "STAALDRAAD", "TROS",
              "TROSSEN", "HAWSER")        # a part named so starts with the steel wire rope look
MOTOR_SPEED = 10.0                        # m/min: the speed of a new Run motor step (a usual lay speed)
MOTOR_TIME = 5.0                          # s
_KEYS = " Esc / right-click: cancel.  Middle mouse / scroll: move the view"


# ---------------------------------------------------------------------------
# what the buttons work on
# ---------------------------------------------------------------------------

def _item(context):
    return paths.active(context.scene)


def chosen_contact(context):
    """(the chosen cable, the place of the contact chosen under "What it touches") or (cable or None, -1)."""
    item = _item(context)
    if item is None or not 0 <= item.contacts_index < len(item.contacts):
        return item, -1
    return item, item.contacts_index


def meant(context):
    """The one part the selection means: the part that was clicked (a click may select its whole subassembly),
    else the active one of the selected parts. None when no part is selected."""
    one = clicked(context)
    if one is not None:
        return one
    parts = selected_parts(context)
    return parts[0] if parts else None


def cable_target(context):
    """The part "Add cable" takes without asking for a click: the part the selection means, when its name or
    material group says cable or wire rope and it is no cable yet. None: the button asks for a click."""
    ob = meant(context)
    if ob is None:
        return None
    return ob if any(o == ob for o in paths.candidates(context.scene)) else None


def rope_named(ob) -> bool:
    """The part's name says steel wire rope (not an electric cable)."""
    words = _name(ob).upper().replace(".", " ").replace("_", " ").replace("-", " ").split()
    return any(w in ROPE_WORDS for w in words)


def add_from(scene, part) -> tuple:
    """A new cable read from ``part``: (its name, the notes of the reading). Raises paths.PathError with a plain
    reason and leaves nothing behind then: no line in the list, no joint."""
    s = scene.fresing
    was, count = s.cables_index, len(s.cables)
    try:
        item = paths.add_cable(scene, _name(part) if part is not None else "")
        notes = paths.read_cad(scene, item, part)
    except Exception as exc:                      # noqa: BLE001 - nothing half made stays, whatever went wrong
        while len(s.cables) > count:
            paths.remove(scene, len(s.cables) - 1)
        s.cables_index = was
        if isinstance(exc, paths.PathError):
            raise
        import traceback
        traceback.print_exc()                     # a fault in the app: named with the part, in full on the console
        raise paths.PathError(f"'{_name(part)}' could not be read (a fault in the app: {type(exc).__name__}: "
                              f"{exc})") from exc
    item = s.cables[len(s.cables) - 1]
    if rope_named(part) and item.look != "ROPE":
        item.look = "ROPE"                        # (its update gives it a rope's lay length)
    return s.cables[len(s.cables) - 1].name, notes


def _tell(context, op, notes: list) -> None:
    """The notes of a reading: the first one is the message, the others are listed before it."""
    for note in notes[1:5]:
        op.report({"INFO"}, note)
    _say(context, op, notes[0] if notes else "Done")


def _refuse(context, op, exc) -> set:
    _say(context, op, str(exc), "ERROR")
    return {"CANCELLED"}


def _redraw(context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def add_motor_step(scene, item):
    """A Run motor step on the cable's speed joint at the end of the selected animation (a new animation when
    there is none): 10 m/min for 5 s, at a steady speed. Returns (animation, step)."""
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


class _Op:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene is not None and hasattr(scene, "fresing") and scene.fresing.model_count > 0


class _NeedsItem(_Op):
    """A button that works on the cable chosen in the list."""

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _item(context) is not None


class _NeedsOn(_NeedsItem):
    """A button that changes the path of the chosen cable: grey while that cable is switched off (it then shows
    as in the CAD file, and the panel says how to switch it on)."""

    @classmethod
    def poll(cls, context):
        return super().poll(context) and bool(_item(context).enabled)


class _NeedsContact(_NeedsOn):
    """A button that works on the contact chosen under "What it touches"."""

    @classmethod
    def poll(cls, context):
        return super().poll(context) and chosen_contact(context)[1] >= 0


class _Pick:
    """A click picker with the hover highlight. ``prompt`` is shown in the status bar, ``note`` beside the mouse,
    ``refuse`` (why this part will not do) in red; ``picked(context, part, point)`` does the work and returns the
    operator's result (``point``: where the click landed, world; None without a click)."""

    prompt = ""

    def note(self, context, ob, name: str) -> str:
        return name

    def refuse(self, context, ob) -> str:
        return ""

    def begin(self, context):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, self.prompt + " " + _KEYS, point=True,
                    note=lambda ob, name, *_a: self.note(context, ob, name),
                    refuse=lambda ob, *_a: self.refuse(context, ob))
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
        ob, _index, loc, _normal = res
        self._end(context)
        result = self.picked(context, ob, tuple(loc))
        _redraw(context)
        return result

    def named(self):
        """The object ``part`` names (scripts, tests, the test tour), or None."""
        return bpy.data.objects.get(self.part) if self.part else None


# ---------------------------------------------------------------------------
# the list of cables
# ---------------------------------------------------------------------------

class FRESING_OT_cable_add(_Pick, _Op, bpy.types.Operator):
    """Makes a cable or wire rope run over its rollers, sheaves and chutes: the app reads its route and diameter
    from the CAD part, lays it on everything it touches and makes all of that turn with it. Click the cable in
    the 3D view first, or press this and click it then. Then give it a speed in 6 Animation"""

    bl_idname = "fresing.cable_add"
    bl_label = "Add cable"
    prompt = "Click the cable or wire rope."

    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"},
                         description="The cable's part (the name of its object). Empty: the selected part, or a "
                                     "click in the 3D view")

    def note(self, context, ob, name):
        return f"Cable: {name}"

    def refuse(self, context, ob):
        scene = context.scene
        for it in paths.items(scene):
            if it.part == ob:
                return f"is cable '{paths.label(it)}' already"
        if any(o == ob for o in flex.flex_parts(scene)):
            return "follows the motion as a hose already"
        return ""

    def invoke(self, context, event):
        if self.part or cable_target(context) is not None:
            return self.execute(context)
        return self.begin(context)

    def execute(self, context):
        ob = self.named() if self.part else (cable_target(context) or meant(context))
        if ob is None:
            _say(context, self, f"There is no part '{self.part}'" if self.part else
                 "First click the cable in the 3D view, then press this", "WARNING")
            return {"CANCELLED"}
        return self.picked(context, ob, None)

    def picked(self, context, ob, _point):
        try:
            _name_, notes = add_from(context.scene, ob)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        _tell(context, self, notes)
        return {"FINISHED"}


class FRESING_OT_cable_add_all(_Op, bpy.types.Operator):
    """Looks for the parts that are named like a cable or a wire rope and adds them all at once, each read from
    its own CAD part. Parts that turn out to be something else are left as they are and named in the message. A
    cable with another name is not found: click it yourself and press Add cable"""

    bl_idname = "fresing.cable_add_all"
    bl_label = "Find cables and add all"

    def execute(self, context):
        scene = context.scene
        found = [ob.name for ob in paths.candidates(scene)]
        if not found:
            _say(context, self, "No part is named like a cable or a wire rope. Click the cable yourself, then "
                 "press Add cable", "WARNING")
            return {"CANCELLED"}
        added, refused = [], []
        for name in found:                        # by name: adding one makes joints, which re-parents parts
            ob = bpy.data.objects.get(name)
            try:
                added.append(add_from(scene, ob)[0])
            except paths.PathError as exc:
                why = str(exc)
                refused.append(why if f"'{_name(ob)}'" in why else f"'{_name(ob)}': {why}")
        left = ""
        if refused:
            left = refused[0] if len(refused) == 1 else \
                f"{plural(len(refused), 'part')} left out (the first: {refused[0]})"
        if not added:
            _say(context, self, left, "ERROR")
            return {"CANCELLED"}
        names = ", ".join(f"'{n}'" for n in added[:4]) + (" …" if len(added) > 4 else "")
        _say(context, self, f"{plural(len(added), 'cable')} added: {names}" + (f". {left}" if left else ""),
             "WARNING" if refused else "INFO")
        return {"FINISHED"}


class FRESING_OT_cable_remove(_NeedsItem, bpy.types.Operator):
    """Takes the chosen cable off the list. Its part shows exactly as in the CAD file again and the joints the
    app made for it go; joints you made yourself stay. Nothing is deleted from the model"""

    bl_idname = "fresing.cable_remove"
    bl_label = "Remove cable"

    def execute(self, context):
        scene = context.scene
        name = paths.label(_item(context))
        paths.remove(scene, scene.fresing.cables_index)
        _say(context, self, f"Cable '{name}' removed from the list: it shows as in the CAD file again")
        return {"FINISHED"}


class FRESING_OT_cable_read(_NeedsItem, bpy.types.Operator):
    """Reads the chosen cable from its CAD part again: its route, its diameter and everything it touches. Use it
    after the model was changed, or to get back a contact you removed. What you added or flipped by hand
    stays"""

    bl_idname = "fresing.cable_read"
    bl_label = "From CAD cable again"

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        if item.part is None or item.part.name not in scene.objects:
            _say(context, self, f"Cable '{paths.label(item)}': its part is gone from the model. Remove it from the "
                 "list and add the cable again", "ERROR")
            return {"CANCELLED"}
        try:
            notes = paths.read_cad(scene, item, item.part)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        _tell(context, self, notes)
        return {"FINISHED"}


class FRESING_OT_cable_select(_NeedsItem, bpy.types.Operator):
    """Selects the chosen cable's part in the 3D view. So you can see which cable of the machine this line of the
    list is"""

    bl_idname = "fresing.cable_select"
    bl_label = "Select"
    bl_options = {"REGISTER"}

    def execute(self, context):
        item = _item(context)
        if not _select(context, paths.parts_of(context.scene, item)):
            _say(context, self, f"'{paths.label(item)}' is hidden or its part is gone: nothing to select", "WARNING")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_cable_motor_step(_NeedsItem, bpy.types.Operator):
    """Adds a step 'Run motor' on this cable's speed to the selected animation: 10 m/min for 5 seconds. Then set
    the speed and the time in 6 Animation and press Build animation: the cable runs and everything it touches
    turns"""

    bl_idname = "fresing.cable_motor_step"
    bl_label = "Add a Run motor step"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        item = _item(context)
        return bool(item.joint) and joints.find(context.scene, item.joint) is not None

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        a, b = add_motor_step(scene, item)
        _say(context, self, f"Step 'Run motor' added to animation '{a.name}': '{paths.label(item)}' runs at "
             f"{MOTOR_SPEED:.0f} m/min for {b.duration:.0f} s. Set it in 6 Animation, then press Build animation")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# what the chosen cable touches
# ---------------------------------------------------------------------------

class FRESING_OT_cable_contact_add(_Pick, _NeedsOn, bpy.types.Operator):
    """Adds a part to what the cable runs over. Press this, then click the roller, sheave or chute in the 3D view,
    at the place where the cable should lie on it: the app puts it at its place along the cable and makes it
    turn with the cable. Esc cancels"""

    bl_idname = "fresing.cable_contact_add"
    bl_label = "Add what the cable touches"
    prompt = "Click a roller, sheave or chute, where the cable should lie on it."

    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"},
                         description="The roller, sheave or chute (the name of its object). Empty: a click in "
                                     "the 3D view")
    point: FloatVectorProperty(name="Point", size=3, subtype="XYZ", options={"SKIP_SAVE", "HIDDEN"},
                               description="Where on the part the cable should lie, in world coordinates. All "
                                           "zero: where the cable passes nearest")

    def note(self, context, ob, name):
        return f"Cable over {name}"

    def refuse(self, context, ob):
        item = _item(context)
        if item is not None and ob == item.part:
            return "is the cable itself: click a roller, sheave or chute"
        if ob.type != "MESH" or ob.data is None or "fr_axes" not in ob.data:
            return "has no round face: click a roller, sheave or round chute"
        return ""

    def invoke(self, context, event):
        return self.execute(context) if self.part else self.begin(context)

    def execute(self, context):
        ob = self.named()
        if ob is None:
            _say(context, self, f"There is no part '{self.part}'" if self.part else
                 "Press this in the 3D view, then click a roller, sheave or chute", "WARNING")
            return {"CANCELLED"}
        return self.picked(context, ob, tuple(self.point) if any(self.point) else None)

    def picked(self, context, ob, point):
        scene = context.scene
        try:
            at = paths.add_contact(scene, _item(context), ob, hit=point)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        item = _item(context)
        c = item.contacts[at]
        _say(context, self, f"'{c.name}' added as a {KIND_WORDS[c.kind]}: number {at + 1} of "
             f"{len(item.contacts)} along '{paths.label(item)}'")
        return {"FINISHED"}


class FRESING_OT_cable_contact_remove(_NeedsContact, bpy.types.Operator):
    """Takes the chosen part off the cable's list: the cable no longer runs over it and it stops turning with the
    cable. A joint the app made for it goes, one you made yourself stays. The app says so when the cable has no
    path without it"""

    bl_idname = "fresing.cable_contact_remove"
    bl_label = "Remove from the cable"

    def execute(self, context):
        scene = context.scene
        item, index = chosen_contact(context)
        name = item.contacts[index].name
        try:
            paths.remove_contact(scene, item, index)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        _say(context, self, f"'{name}' removed: cable '{paths.label(_item(context))}' no longer runs over it")
        return {"FINISHED"}


class FRESING_OT_cable_contact_flip(_NeedsContact, bpy.types.Operator):
    """Lays the cable round the other side of the chosen sheave, chute or bend. Use it when the app laid the
    cable over a wheel it should run under, or the other way round. The app says so when the cable cannot go
    round that side"""

    bl_idname = "fresing.cable_contact_flip"
    bl_label = "Flip side"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        item, index = chosen_contact(context)
        return item.contacts[index].kind in FLIPS

    def execute(self, context):
        scene = context.scene
        item, index = chosen_contact(context)
        name = item.contacts[index].name
        try:
            paths.flip_contact(scene, item, index)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        _say(context, self, f"Cable '{paths.label(_item(context))}' now goes round the other side of '{name}'")
        return {"FINISHED"}


def end_word(end: str) -> str:
    """What the panel calls an end: 'start' (A) or 'end' (B)."""
    return "start" if str(end).upper() == "A" else "end"


class FRESING_OT_cable_end(_Pick, _NeedsOn, bpy.types.Operator):
    """Fixes this end of the cable to a part: press this, then click the part in the 3D view. From then on the
    end moves with that part; it stays where it is now. Esc cancels"""

    bl_idname = "fresing.cable_end"
    bl_label = "End on a part"

    end: EnumProperty(name="End", default="B", options={"SKIP_SAVE"},
                      description="Which end of the cable this is about",
                      items=[("A", "Start", "The start of the cable: where the paid-out cable comes from"),
                             ("B", "End", "The end of the cable: where the paid-out cable goes to")])
    free: BoolProperty(name="Free end", default=False, options={"SKIP_SAVE"},
                       description="Make it a free end that touches no part, instead of fixing it to a part")
    part: StringProperty(name="Part", options={"SKIP_SAVE", "HIDDEN"},
                         description="The part the end is fixed to (the name of its object). Empty: a click in the "
                                     "3D view")

    @classmethod
    def description(cls, context, properties):
        word = end_word(properties.end)
        if properties.free:
            return (f"Makes the cable's {word} a free end again: it touches no part and runs straight on from the "
                    f"nearest thing the cable bends round. Set how far it runs on under More, Free at {word}")
        return (f"Fixes the cable's {word} to a part: press this, then click the part in the 3D view. From then on "
                f"the {word} moves with that part; it stays where it is now. Esc cancels")

    @property
    def prompt(self):
        return f"Click the part the cable's {end_word(self.end)} is fixed to."

    def note(self, context, ob, name):
        return f"The {end_word(self.end)} moves with {name}"

    def refuse(self, context, ob):
        item = _item(context)
        return "is the cable itself: click the part its end is fixed to" if item is not None and ob == item.part \
            else ""

    def invoke(self, context, event):
        return self.execute(context) if self.free or self.part else self.begin(context)

    def execute(self, context):
        if self.free:
            return self.picked(context, None, None)
        ob = self.named()
        if ob is None:
            _say(context, self, f"There is no part '{self.part}'" if self.part else
                 "Press this in the 3D view, then click the part the end is fixed to", "WARNING")
            return {"CANCELLED"}
        return self.picked(context, ob, None)

    def picked(self, context, ob, _point):
        scene = context.scene
        word = end_word(self.end)
        try:
            paths.set_end(scene, _item(context), self.end, ob)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        name = paths.label(_item(context))
        _say(context, self, f"The {word} of '{name}' is a free end again" if ob is None else
             f"The {word} of '{name}' now moves with '{_name(ob)}'")
        return {"FINISHED"}


CLASSES = (FRESING_OT_cable_add, FRESING_OT_cable_add_all, FRESING_OT_cable_remove, FRESING_OT_cable_read,
           FRESING_OT_cable_select, FRESING_OT_cable_motor_step, FRESING_OT_cable_contact_add,
           FRESING_OT_cable_contact_remove, FRESING_OT_cable_contact_flip, FRESING_OT_cable_end)
