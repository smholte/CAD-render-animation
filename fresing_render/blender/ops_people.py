"""Operators of 6 Animation > People (task 0157): add a person, draw and edit its path, its list of actions, items,
the example. Each click tool also runs without a click (``execute`` with a location) for scripts and tests."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatVectorProperty, IntProperty, StringProperty
from mathutils import Vector

from ..core import people as core
from . import people


def _active_person(context):
    ob = context.view_layer.objects.active if context.view_layer else None
    return ob if people.is_person(ob) else None


def _select(context, ob) -> None:
    for o in context.view_layer.objects.selected:
        o.select_set(False)
    if ob is not None and ob.name in context.view_layer.objects:
        ob.hide_select = False
        ob.select_set(True)
        context.view_layer.objects.active = ob


def _floor_hit(context, event):
    """Where the mouse points on any surface (the floor plane when it points at nothing)."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    co = (event.mouse_region_x, event.mouse_region_y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    scene = context.scene
    dg = context.evaluated_depsgraph_get()
    o = origin
    for _ in range(6):
        ok, loc, _n, _i, ob, _m = scene.ray_cast(dg, o, direction)
        if not ok:
            break
        ob = getattr(ob, "original", ob)
        if people.is_person(ob) or people.is_item(ob) or ob.hide_render:
            o = loc + direction * 1e-3
            continue
        return loc
    z = people._sur().floor_height(scene)
    if abs(direction.z) > 1e-6:
        t = (z - origin.z) / direction.z
        if t > 0:
            return origin + direction * t
    return None


def _redraw(context) -> None:
    for area in context.screen.areas if context.screen else []:
        area.tag_redraw()


class _ClickTool:
    """A modal click in the 3D view: ``_clicked(context, location)`` for each click; Enter or right-click ends it
    when ``many`` (Esc too), else the first click does."""

    many = False
    prompt = ""

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        if not self._start(context):
            return {"CANCELLED"}
        context.window.cursor_modal_set("CROSSHAIR")
        context.workspace.status_text_set(self.prompt)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _start(self, context) -> bool:
        return True

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)
        _redraw(context)

    def modal(self, context, event):
        from .ops_motion import over_panel
        if event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"} or event.type.startswith("NDOF"):
            return {"PASS_THROUGH"}
        if event.type == "ESC" and event.value == "PRESS":
            self._end(context)
            self._cancel(context)
            return {"CANCELLED"}
        if self.many and event.type in {"RET", "NUMPAD_ENTER", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"FINISHED"}
        if self.many and event.type == "BACK_SPACE" and event.value == "PRESS":
            self._undo_one(context)
            _redraw(context)
            return {"RUNNING_MODAL"}
        if not self.many and event.type == "RIGHTMOUSE" and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        loc = _floor_hit(context, event)
        if loc is None:
            context.workspace.status_text_set("Missed: click on the floor or the deck. " + self.prompt)
            return {"RUNNING_MODAL"}
        self._clicked(context, Vector(loc))
        _redraw(context)
        if not self.many:
            self._end(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def _cancel(self, context):
        pass

    def _undo_one(self, context):
        pass


class FRESING_OT_person_add(_ClickTool, bpy.types.Operator):
    """Adds a person who can walk and act: click on the floor (or the deck) where the person stands. Then draw its
    path and add what it does below. Esc cancels"""

    bl_idname = "fresing.person_add"
    bl_label = "Add person"
    bl_options = {"REGISTER", "UNDO"}

    prompt = "Click on the floor where the person stands.  Esc / right-click: cancel"
    location: FloatVectorProperty(size=3, options={"HIDDEN", "SKIP_SAVE"})
    at: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    def _clicked(self, context, loc):
        self.location = loc
        self.at = True
        self.execute(context)

    def execute(self, context):
        scene = context.scene
        n = len(people.people(scene)) + 1
        ob = people.add_person(scene, tuple(self.location) if self.at else None, f"Person {n}")
        ob.fresing_person.look = (n - 1) % 4
        _select(context, ob)
        people.forget()
        self.report({"INFO"}, f"Added '{ob.name}': now draw its path and add what it does")
        return {"FINISHED"}


class FRESING_OT_person_select(bpy.types.Operator):
    """Selects this person: its settings, path and actions show below and its path in the view"""

    bl_idname = "fresing.person_select"
    bl_label = "Select person"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if not people.is_person(ob):
            return {"CANCELLED"}
        _select(context, ob)
        return {"FINISHED"}


class FRESING_OT_person_remove(bpy.types.Operator):
    """Deletes the selected person with its path (its items stay where they lie)"""

    bl_idname = "fresing.person_remove"
    bl_label = "Delete person"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_person(context) is not None

    def execute(self, context):
        ob = _active_person(context)
        name = ob.name
        people.remove_person(context.scene, ob)
        self.report({"INFO"}, f"Deleted '{name}'")
        return {"FINISHED"}


class FRESING_OT_person_path_draw(_ClickTool, bpy.types.Operator):
    """Draws the selected person's path: click point after point on the floor, then Enter (or right-click).
    Backspace takes the last point back, Esc cancels. Clicking again adds points at the end"""

    bl_idname = "fresing.person_path_draw"
    bl_label = "Draw path"
    bl_options = {"REGISTER", "UNDO"}

    many = True
    prompt = "Click the path's points on the floor.  Enter / right-click: done.  Backspace: take the last back.  " \
             "Esc: cancel"
    location: FloatVectorProperty(size=3, options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _active_person(context) is not None

    def _start(self, context):
        self._who = _active_person(context).name
        self._before = [tuple(p) for p in people.path_points(_active_person(context))]
        return True

    def _clicked(self, context, loc):
        ob = bpy.data.objects.get(self._who)
        if ob is not None:
            people.add_path_point(context.scene, ob, tuple(loc))

    def _undo_one(self, context):
        ob = bpy.data.objects.get(self._who)
        pts = people.path_points(ob)[:-1]
        if pts:
            people.set_path(context.scene, ob, [(x, y, z - 0.02) for x, y, z in pts])
        else:
            people.clear_path(ob)

    def _cancel(self, context):
        ob = bpy.data.objects.get(self._who)
        if ob is None:
            return
        if self._before:
            people.set_path(context.scene, ob, [(x, y, z - 0.02) for x, y, z in self._before])
        else:
            people.clear_path(ob)

    def execute(self, context):                # scripts and tests: one point at ``location``
        ob = _active_person(context)
        if ob is None:
            return {"CANCELLED"}
        n = people.add_path_point(context.scene, ob, tuple(self.location))
        self.report({"INFO"}, f"'{ob.name}': point {n} added")
        return {"FINISHED"}


class FRESING_OT_person_path_edit(bpy.types.Operator):
    """Edits the selected person's path in the view: drag points with G, add a point between two with Subdivide
    (right-click menu), delete one with X. Click again to finish"""

    bl_idname = "fresing.person_path_edit"
    bl_label = "Edit path points"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = _active_person(context)
        return (ob is not None and people.path_object(ob) is not None) or (
            context.mode == "EDIT_CURVE" and context.active_object is not None
            and context.active_object.get(people.PATH_TAG))

    def execute(self, context):
        if context.mode == "EDIT_CURVE":
            cu = context.active_object
            bpy.ops.object.mode_set(mode="OBJECT")
            person = bpy.data.objects.get(cu.get(people.PATH_TAG, ""))
            if person is not None:
                _select(context, person)
            people.forget()
            return {"FINISHED"}
        ob = _active_person(context)
        p = people.path_object(ob)
        _select(context, p)
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}


class FRESING_OT_person_path_clear(bpy.types.Operator):
    """Deletes the selected person's path (its actions stay)"""

    bl_idname = "fresing.person_path_clear"
    bl_label = "Delete path"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = _active_person(context)
        return ob is not None and people.path_object(ob) is not None

    def execute(self, context):
        people.clear_path(_active_person(context))
        return {"FINISHED"}


class FRESING_OT_person_action_add(bpy.types.Operator):
    """Adds a step to the selected person's list (after the selected step): walk, stop, turn, pick up, put down,
    wave, greet, talk, point, look, idle or operate"""

    bl_idname = "fresing.person_action_add"
    bl_label = "Add step"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(name="Action", items=[(i, n, d, k) for k, (i, n, d) in enumerate(core.ACTION_ITEMS)])

    @classmethod
    def poll(cls, context):
        return _active_person(context) is not None

    def execute(self, context):
        ob = _active_person(context)
        ps = ob.fresing_person
        a = ps.actions.add()
        a.kind = self.kind
        if self.kind == "WALK":
            a.place = "END" if people.path_points(ob) else "POINT"
        if self.kind in core.NEEDS_OTHER:
            others = [o for o in people.people(context.scene) if o != ob]
            if others:
                a.other = others[0]
        if self.kind == "PICK_UP":
            its = people.items(context.scene)
            if its:
                a.item = its[0]
        if self.kind == "OPERATE":
            a.target_kind = "POINT"
        at = min(ps.actions_index + 1, len(ps.actions) - 1) if len(ps.actions) > 1 else 0
        ps.actions.move(len(ps.actions) - 1, at)
        ps.actions_index = at
        people.forget()
        return {"FINISHED"}


class FRESING_OT_person_action_remove(bpy.types.Operator):
    """Deletes the selected step of the selected person"""

    bl_idname = "fresing.person_action_remove"
    bl_label = "Delete step"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = _active_person(context)
        return ob is not None and len(ob.fresing_person.actions) > 0

    def execute(self, context):
        ps = _active_person(context).fresing_person
        i = ps.actions_index
        if 0 <= i < len(ps.actions):
            ps.actions.remove(i)
            ps.actions_index = max(0, min(i, len(ps.actions) - 1))
        people.forget()
        return {"FINISHED"}


class FRESING_OT_person_action_move(bpy.types.Operator):
    """Moves the selected step up or down in the person's list (the person does its steps from top to bottom)"""

    bl_idname = "fresing.person_action_move"
    bl_label = "Move step"
    bl_options = {"REGISTER", "UNDO"}

    direction: IntProperty(default=-1, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        ob = _active_person(context)
        return ob is not None and len(ob.fresing_person.actions) > 1

    def execute(self, context):
        ps = _active_person(context).fresing_person
        i = ps.actions_index
        j = i + self.direction
        if 0 <= i < len(ps.actions) and 0 <= j < len(ps.actions):
            ps.actions.move(i, j)
            ps.actions_index = j
        people.forget()
        return {"FINISHED"}


class FRESING_OT_person_pick_point(_ClickTool, bpy.types.Operator):
    """Click the point the selected step is about: where the person looks, points, turns to or puts its hands
    (Operate: click on the panel or the part). Esc cancels"""

    bl_idname = "fresing.person_pick_point"
    bl_label = "Pick point"
    bl_options = {"REGISTER", "UNDO"}

    prompt = "Click the point (on a part, a panel or the floor).  Esc / right-click: cancel"
    location: FloatVectorProperty(size=3, options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        ob = _active_person(context)
        return ob is not None and len(ob.fresing_person.actions) > 0

    def _start(self, context):
        self._who = _active_person(context).name
        return True

    def _clicked(self, context, loc):
        self.location = loc
        ob = bpy.data.objects.get(self._who)
        _select(context, ob)
        self.execute(context)

    def execute(self, context):
        ob = _active_person(context)
        if ob is None:
            return {"CANCELLED"}
        ps = ob.fresing_person
        a = ps.actions[ps.actions_index]
        a.target_kind = "POINT"
        a.target_point = tuple(self.location)
        a.target_set = True
        people.forget()
        return {"FINISHED"}


class FRESING_OT_person_item_add(bpy.types.Operator):
    """Adds an item lying on the floor in front of the selected person (move it like any object). A person picks it
    up with a Pick up step, or holds it from the start (Holds, above)"""

    bl_idname = "fresing.person_item_add"
    bl_label = "Add item"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(name="Item", items=[(i, n, d, k) for k, (i, n, d) in enumerate(core.ITEM_ITEMS)])

    def execute(self, context):
        ob = people.add_item(context.scene, self.kind)
        people.forget()
        self.report({"INFO"}, f"Added '{ob.name}'")
        return {"FINISHED"}


class FRESING_OT_people_example(bpy.types.Operator):
    """Sets up an example beside the machine: Anna walks in with a toolbox, stops by Ben, puts the box down, they
    shake hands and talk. Then Build the animation to see it"""

    bl_idname = "fresing.people_example"
    bl_label = "Example: two people meet"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        anna, _ben, _box = people.set_up_example(context.scene)
        _select(context, anna)
        self.report({"INFO"}, "Anna and Ben are beside the machine: Build the animation to see them meet")
        return {"FINISHED"}


CLASSES = (FRESING_OT_person_add, FRESING_OT_person_select, FRESING_OT_person_remove, FRESING_OT_person_path_draw,
           FRESING_OT_person_path_edit, FRESING_OT_person_path_clear, FRESING_OT_person_action_add,
           FRESING_OT_person_action_remove, FRESING_OT_person_action_move, FRESING_OT_person_pick_point,
           FRESING_OT_person_item_add, FRESING_OT_people_example)
