"""Operators for cylinders (task 0013): pick barrel and rod, click the two pins, follow or drive the arm."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from ..core.words import plural
from . import build, cylinders, hover, joints, logic
from .ops_motion import _redraw, over_panel, selected_movers


def _active(context):
    s = context.scene.fresing
    if 0 <= s.cylinders_index < len(s.cylinders):
        return s.cylinders[s.cylinders_index]
    return None


def _valid(context) -> bool:
    c = _active(context)
    return c is not None and cylinders.is_valid(c)


def _names(objs, n: int = 2) -> str:
    names = [o.get(build.PROP_NAME, o.name) for o in objs]
    return ", ".join(names[:n]) + (f" +{len(names) - n}" if len(names) > n else "")


def _say(context, op, text: str, level: str = "INFO") -> None:
    context.scene.fresing.last_message = text
    op.report({level}, text)


def _overlaps(a, b) -> bool:
    """The same object, or one inside the other (a subassembly and one of its parts)."""
    return a is b or joints._is_cad_ancestor(a, b) or joints._is_cad_ancestor(b, a)


def add_picks(target: list, other: list, movers: list) -> tuple[list, list, list]:
    """Task 0290: several parts or subassemblies per item. ``movers`` added to ``target`` (objects): a pick that is
    already there, or inside one that is, is skipped; a subassembly takes the place of picks inside it. Picks of
    ``other`` that overlap a new one leave it (a part may not be in two items). Returns (target, other, taken from
    other)."""
    target, other = list(target), list(other)
    for ob in movers:
        if any(t is ob or joints._is_cad_ancestor(t, ob) for t in target):
            continue
        target = [t for t in target if not joints._is_cad_ancestor(ob, t)] + [ob]
    taken = [o for o in other if any(_overlaps(o, ob) for ob in movers)]
    other = [o for o in other if o not in taken]
    return target, other, taken


def _fill(coll, objs) -> None:
    coll.clear()
    for ob in objs:
        coll.add().obj = ob


SEVERAL = "Shift+click or Ctrl+click (in the view or in 2 Structure) selects several"


class FRESING_OT_cylinder_pick_parts(bpy.types.Operator):
    """Adds the selected subassemblies or parts to the cylinder's barrel or rod (each can be several). Click them in
    the view or in 2 Structure first; Shift+click or Ctrl+click selects several"""

    bl_idname = "fresing.cylinder_pick_parts"
    bl_label = "Add selected"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(items=[("BARREL", "Barrel", ""), ("ROD", "Rod", "")], default="BARREL",
                       options={"SKIP_SAVE"})
    action: EnumProperty(items=[("ADD", "Add selected", ""), ("DROP", "Drop", ""), ("CLEAR", "Clear", "")],
                         default="ADD", options={"SKIP_SAVE"})
    index: IntProperty(default=-1, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        what = "rod" if properties.role == "ROD" else "barrel"
        if properties.action == "DROP":
            return f"Takes this one off the {what}: it stays where it is and does not move with the cylinder"
        if properties.action == "CLEAR":
            return f"Empties the {what}: pick its parts again with Add selected"
        if properties.role == "ROD":
            return ("Adds the selected subassemblies or parts to the cylinder's rod: the part that slides out, with "
                    f"its piston and eye. {SEVERAL}; press again to add more")
        return ("Adds the selected subassemblies or parts to the cylinder's barrel: the tube with its end cap, "
                f"gland and eye. {SEVERAL}; press again to add more")

    def execute(self, context):
        s = context.scene.fresing
        word = "Rod" if self.role == "ROD" else "Barrel"
        target, other = (s.cyl_pick_rod, s.cyl_pick_barrel) if self.role == "ROD" else (s.cyl_pick_barrel,
                                                                                         s.cyl_pick_rod)
        if self.action == "CLEAR":
            target.clear()
            _say(context, self, f"{word}: cleared")
            return {"FINISHED"}
        if self.action == "DROP":
            objs = cylinders._objs(target)
            if not 0 <= self.index < len(objs):
                return {"CANCELLED"}
            del objs[self.index]
            _fill(target, objs)
            _redraw(context)
            return {"FINISHED"}
        movers = selected_movers(context)
        if not movers:
            _say(context, self, f"Nothing selected: click the {word.lower()} first", "WARNING")
            return {"CANCELLED"}
        objs, rest, taken = add_picks(cylinders._objs(target), cylinders._objs(other), movers)
        _fill(target, objs)
        if taken:
            _fill(other, rest)                          # the same parts cannot be both
        text = f"{word}: {_names(objs, 3)}"
        if taken:
            text += f" (taken off the {'barrel' if self.role == 'ROD' else 'rod'}: {_names(taken)})"
        _say(context, self, text)
        return {"FINISHED"}


class FRESING_OT_cylinder_add(bpy.types.Operator):
    """Adds a cylinder made of the barrel and rod picked above. Then click the barrel's pin (on the machine side),
    then the rod's pin (on the moving part): a hole or the pin itself. Esc cancels"""

    bl_idname = "fresing.cylinder_add"
    bl_label = "Add cylinder"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return any(r.obj for r in s.cyl_pick_barrel) and any(r.obj for r in s.cyl_pick_rod)

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        s = context.scene.fresing
        barrel = [r.obj for r in s.cyl_pick_barrel if r.obj is not None]
        rod = [r.obj for r in s.cyl_pick_rod if r.obj is not None]
        reason = cylinders.check_parts(context.scene, barrel, rod)
        if reason:                                   # say so before the clicks, not after
            _say(context, self, reason, "WARNING")
            return {"CANCELLED"}
        self._first = None
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, "")
        self._status(context, "1 of 2: click the BARREL's pin (on the machine side): the pin, or the hole it is in")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _status(self, context, text):
        hover.prompt(context, f"{text}.  Esc / right-click: cancel.  Middle mouse / scroll: move the view")

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            self._status(context, "Missed the model: click a pin or the hole it is in")
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        origin, direction, desc = joints.axis_from_hit(ob, index, loc, normal)
        if self._first is None:
            self._first = (origin, direction, ob, desc)
            self._status(context, "2 of 2: now click the ROD's pin (on the moving part): the pin, or the hole it is in")
            return {"RUNNING_MODAL"}
        self._end(context)
        return self._make(context, (origin, direction, ob, desc))

    def _make(self, context, second):
        scene = context.scene
        s = scene.fresing
        (ob_, db_, ref_b, desc_b), (or_, dr_, ref_r, desc_r) = self._first, second
        barrel = [r.obj for r in s.cyl_pick_barrel if r.obj is not None]
        rod = [r.obj for r in s.cyl_pick_rod if r.obj is not None]
        try:
            c, notes = cylinders.create(scene, barrel, rod, (ob_, db_, ref_b), (or_, dr_, ref_r))
        except RuntimeError as exc:
            _say(context, self, str(exc), "ERROR")
            return {"CANCELLED"}
        s.cyl_pick_barrel.clear()
        s.cyl_pick_rod.clear()
        flat = [d for d in (desc_b, desc_r) if not d.startswith("round")]
        if flat:
            notes.insert(0, "A pin was clicked on a flat face: click the pin itself or its hole for its exact centre "
                            "(Set-up > Pins again)")
        msg = f"Cylinder '{c.name}' added"
        if notes:
            msg += ". " + " ".join(notes)
        _say(context, self, msg)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_cylinder_pins(bpy.types.Operator):
    """Click the two pins again: first the barrel's pin (machine side), then the rod's pin (moving part). The parts,
    stroke and mode stay. Esc cancels"""

    bl_idname = "fresing.cylinder_pins"
    bl_label = "Pins again"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        self._first = None
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, "")
        FRESING_OT_cylinder_add._status(self, context, "1 of 2: click the BARREL's pin (on the machine side)")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            FRESING_OT_cylinder_add._end(self, context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        origin, direction, _desc = joints.axis_from_hit(ob, index, loc, normal)
        if self._first is None:
            self._first = (origin, direction, ob)
            FRESING_OT_cylinder_add._status(self, context, "2 of 2: now click the ROD's pin (on the moving part)")
            return {"RUNNING_MODAL"}
        FRESING_OT_cylinder_add._end(self, context)
        scene = context.scene
        try:
            c = repin(scene, _active(context), self._first, (origin, direction, ob))
        except RuntimeError as exc:
            _say(context, self, str(exc), "ERROR")
            return {"CANCELLED"}
        notes = c.get("_notes", "")
        _say(context, self, f"Pins of '{c.name}' set" + (f". {notes}" if notes else ""))
        return {"FINISHED"}


def repin(scene, c, barrel_click, rod_click):
    """Give a cylinder new pins (clicks as (origin, direction, clicked part) in the current pose). The parts,
    lengths, mode and place in the list stay. When the new pins do not work the cylinder stays as it was."""
    # the clicks kept on the parts that were clicked, before anything moves (the arm may be turned)
    pin_b = cylinders.pin_click(*barrel_click)
    pin_r = cylinders.pin_click(*rod_click)
    name, mode, idx = c.name, c.mode, scene.fresing.cylinders_index
    lengths = (c.closed_length, c.full_stroke, c.measured)
    parts = (cylinders.barrel_objs(c), cylinders.rod_objs(c), cylinders.stage_objs(c))
    with joints.cad_pose(scene):
        spec = cylinders.to_spec(cylinders.find(scene, name))
    cylinders.remove(scene, cylinders.find(scene, name))
    s = scene.fresing
    try:
        c, notes = cylinders.create_local(scene, parts[0], parts[1], pin_b, pin_r, name=name, stages=parts[2])
    except RuntimeError as exc:
        by_uid = {o.get(build.PROP_UID): o for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS}
        cylinders.rebuild_from_specs(scene, [spec], by_uid)          # back as it was
        s.cylinders.move(len(s.cylinders) - 1, idx)
        s.cylinders_index = idx
        raise RuntimeError(f"{exc} The cylinder keeps its old pins") from exc
    c["closed_length"], c["full_stroke"], c["measured"] = lengths
    s.cylinders.move(len(s.cylinders) - 1, idx)
    s.cylinders_index = idx
    c = s.cylinders[idx]
    if mode == "DRIVE":
        try:
            cylinders.set_mode(scene, c, "DRIVE")
        except RuntimeError as exc:
            notes.append(f"It follows its arm now: {exc}")
    c["_notes"] = " ".join(notes)
    return c


class FRESING_OT_cylinder_remove(bpy.types.Operator):
    """Removes the cylinder: its barrel and rod go back to their CAD place. The arm and its joint stay"""

    bl_idname = "fresing.cylinder_remove"
    bl_label = "Remove cylinder"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def execute(self, context):
        c = _active(context)
        name = c.name
        cylinders.remove(context.scene, c)
        _say(context, self, f"Cylinder '{name}' removed")
        return {"FINISHED"}


class FRESING_OT_cylinder_mode(bpy.types.Operator):
    """Follows the arm: the cylinder goes along with the arm. Drives the arm: you set the stroke and the arm's
    joint turns to match"""

    bl_idname = "fresing.cylinder_mode"
    bl_label = "Cylinder moves"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("FOLLOW", "Follows the arm", ""), ("DRIVE", "Drives the arm", "")],
                       default="FOLLOW", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.mode == "DRIVE":
            text = ("You set the stroke (how far the rod is out) and the arm's joint turns to match. The joint's limits "
                    "become the cylinder's: fully in … fully out")
            c = _active(context)
            if c is not None:
                j, reason = cylinders.arm_joint(context.scene, c)
                if j is None:
                    text += f". Not possible now: {reason}"
            return text
        return ("The cylinder goes along with whatever moves the arm (its joint, a pose, an animation step): the "
                "barrel turns about its pin, the rod slides so its eye stays on its pin")

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def execute(self, context):
        c = _active(context)
        try:
            msg = cylinders.set_mode(context.scene, c, self.mode)
        except RuntimeError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        if msg:
            _say(context, self, msg)
        return {"FINISHED"}


class FRESING_OT_cylinder_stroke(bpy.types.Operator):
    """Moves the rod fully in, fully out, or back to where it is in the CAD model; the arm moves to match"""

    bl_idname = "fresing.cylinder_stroke"
    bl_label = "Set stroke"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(items=[("IN", "Fully in", ""), ("CAD", "CAD", ""), ("OUT", "Fully out", "")],
                         default="CAD", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {"IN": "Moves the rod fully in (stroke 0); the arm moves to match",
                "OUT": "Moves the rod fully out (the full stroke); the arm moves to match",
                "CAD": "Puts the arm back where it is in the CAD model, with the rod as drawn there"}[properties.target]

    @classmethod
    def poll(cls, context):
        c = _active(context)
        return c is not None and cylinders.is_valid(c) and c.mode == "DRIVE"

    def execute(self, context):
        scene = context.scene
        c = _active(context)
        try:
            if self.target == "CAD":
                j, reason = cylinders.arm_joint(scene, c)
                if j is None:
                    raise RuntimeError(reason)
                joints.set_value(j, 0.0)
                cylinders._update(scene)
            else:
                cylinders.set_stroke(scene, c, 0.0 if self.target == "IN" else c.full_stroke)
        except RuntimeError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_cylinder_estimate(bpy.types.Operator):
    """Reads the closed length and the full stroke from the parts again: how far the piston can go back to the end
    cap and out to the gland. Check them against the cylinder's data sheet"""

    bl_idname = "fresing.cylinder_estimate"
    bl_label = "From the model"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def execute(self, context):
        scene = context.scene
        name = _active(context).name
        with joints.cad_pose(scene):
            measured = cylinders.estimate(scene, cylinders.find(scene, name))
        c = cylinders.find(scene, name)
        msg = cylinders.sync_limits(scene, c)
        how = ("measured from the piston, end cap and gland" if measured else
               "a rough guess (no piston or gland found): please type the data sheet's values")
        _say(context, self, f"Closed {c.closed_length * 1000:.0f} mm, stroke {c.full_stroke * 1000:.0f} mm: {how}"
             + (f". {msg}" if msg else ""))
        return {"FINISHED"}


class FRESING_OT_cylinder_parts(bpy.types.Operator):
    """Changes what the cylinder is made of, or which part holds a pin, using the selected parts; or selects the
    cylinder's parts"""

    bl_idname = "fresing.cylinder_parts"
    bl_label = "Cylinder parts"
    bl_options = {"REGISTER", "UNDO"}

    action: EnumProperty(items=[("BARREL", "Barrel", ""), ("ROD", "Rod", ""), ("STAGES", "Stages", ""),
                                ("NO_STAGES", "No stages", ""), ("BARREL_PIN", "Barrel pin on", ""),
                                ("ROD_PIN", "Rod pin on", ""), ("SELECT", "Select", ""), ("DROP", "Drop", "")],
                         default="SELECT", options={"SKIP_SAVE"})
    role: EnumProperty(items=[("BARREL", "Barrel", ""), ("ROD", "Rod", ""), ("STAGES", "Stages", "")],
                       default="BARREL", options={"SKIP_SAVE"})
    index: IntProperty(default=-1, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.action == "DROP":
            what = {"BARREL": "barrel", "ROD": "rod", "STAGES": "stages"}[properties.role]
            return (f"Takes this one off the cylinder's {what}: it goes back to its CAD place and no longer moves "
                    "with the cylinder (the barrel and the rod keep at least one)")
        return {
            "BARREL": f"Adds the selected subassemblies or parts to this cylinder's barrel ({SEVERAL}). The travel "
                      "is read again from all its parts",
            "ROD": f"Adds the selected subassemblies or parts to this cylinder's rod ({SEVERAL}). The travel is read "
                   "again from all its parts",
            "STAGES": "Telescopic cylinder: adds the selected sections between the barrel and the rod; each slides out "
                      f"the same share of the rod's travel ({SEVERAL})",
            "NO_STAGES": "No telescopic sections: they go back to their CAD place",
            "BARREL_PIN": "The barrel's pin sits in the selected part instead (a part on the machine side that does "
                          "not move with the arm)",
            "ROD_PIN": "The rod's pin sits in the selected part instead (a part that moves with the arm)",
            "SELECT": "Selects the cylinder's parts in the view",
        }[properties.action]

    @classmethod
    def poll(cls, context):
        return _valid(context)

    def execute(self, context):
        scene = context.scene
        c = _active(context)
        if self.action == "SELECT":
            for ob in context.selected_objects:
                ob.select_set(False)
            tree = logic.Tree(scene)
            for m in cylinders.members(c):
                for d in [m] + tree.descendants(m):
                    if d.visible_get() and not d.hide_select:
                        d.select_set(True)
            return {"FINISHED"}
        now = {"barrel": cylinders.barrel_objs(c), "rod": cylinders.rod_objs(c), "stages": cylinders.stage_objs(c)}
        movers = selected_movers(context)
        if self.action == "DROP":
            key = self.role.lower()
            objs = now[key]
            if not 0 <= self.index < len(objs):
                return {"CANCELLED"}
            if key != "stages" and len(objs) == 1:
                _say(context, self, f"The {key} needs at least one part: add the new one first", "WARNING")
                return {"CANCELLED"}
            value = [o for i, o in enumerate(objs) if i != self.index]
        else:
            key = {"BARREL": "barrel", "ROD": "rod", "STAGES": "stages", "NO_STAGES": "stages",
                   "BARREL_PIN": "barrel_carrier", "ROD_PIN": "rod_carrier"}[self.action]
            if self.action == "NO_STAGES":
                value = []
            elif not movers:
                _say(context, self, "Nothing selected: click the part(s) first", "WARNING")
                return {"CANCELLED"}
            elif key.endswith("carrier"):
                ob = context.active_object if context.active_object in movers else movers[0]
                value = ob
            else:
                value, _rest, _taken = add_picks(now[key], [], movers)
        try:
            c = cylinders.rebuild(scene, c, **{key: value})
        except RuntimeError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        if key in ("barrel", "rod"):
            # the travel read again from all its parts – unless it was typed (not measured) and still cannot be read
            name, was = c.name, (c.closed_length, c.full_stroke, c.measured)
            with joints.cad_pose(scene):
                now = cylinders.estimate(scene, cylinders.find(scene, name))
            c = cylinders.find(scene, name)
            if not (now or was[2]):
                c["closed_length"], c["full_stroke"], c["measured"] = was
            cylinders.sync_limits(scene, c)
        if self.action == "STAGES":
            _say(context, self, f"{plural(len(value), 'stage')}: each slides out "
                                "the same share of the rod's travel")
        elif key in ("barrel", "rod", "stages") and self.action != "NO_STAGES":
            _say(context, self, f"{key.capitalize()}: {_names(value, 3)}" if value else "No stages")
        return {"FINISHED"}


CLASSES = (FRESING_OT_cylinder_pick_parts, FRESING_OT_cylinder_add, FRESING_OT_cylinder_pins,
           FRESING_OT_cylinder_remove, FRESING_OT_cylinder_mode, FRESING_OT_cylinder_stroke,
           FRESING_OT_cylinder_estimate, FRESING_OT_cylinder_parts)
