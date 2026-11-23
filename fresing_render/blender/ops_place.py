"""The buttons of 2 Structure > Place and Remove (task 0292): steps, Put on the floor, Back to the CAD place, the lock,
Move / Turn with the mouse, the Move / turn… window, Remove… (a window that lists what goes) and the Delete / X keys
outside Full access. The rules: the top of ``place.py`` and ``remove.py``."""

from __future__ import annotations

import math

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector, geometry

from ..core import place as core
from ..core.words import plural
from . import build, form_window, logic, place, remove


def _done(op, context, note: str, what: str) -> set:
    msg = note or what
    context.scene.fresing.last_message = msg
    place.NOTE[0] = msg
    op.report({"INFO"}, msg)
    return {"FINISHED"}


def _poll_place(cls, context) -> bool:
    if not getattr(context.scene, "fresing", None):
        return False
    why = place.refused(context)
    if why:
        cls.poll_message_set(why)
        return False
    return True


class FRESING_OT_place_step(bpy.types.Operator):
    """Moves what is selected one step along this axis, or turns it one step about it (the step size is chosen under
    the fields). It stays there: Build, poses and model updates keep it"""

    bl_idname = "fresing.place_step"
    bl_label = "Step"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(min=0, max=5, options={"SKIP_SAVE"})
    sign: IntProperty(default=1, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _poll_place(cls, context)

    @classmethod
    def description(cls, context, properties):
        axis = "XYZ"[properties.index % 3]
        if properties.index < 3:
            return (f"Moves it one step {'+' if properties.sign > 0 else '–'} along {axis} (the step under the "
                    "fields). It stays there: Build, poses and model updates keep it")
        return (f"Turns it one step {'+' if properties.sign > 0 else '–'} about {axis}, about the middle of its box "
                "(the step under the fields). It stays that way")

    def execute(self, context):
        scene = context.scene
        st = scene.fresing.place
        ob = place.target(context)
        turn = self.index >= 3
        amount = core.size_of(core.STEP_TURN if turn else core.STEP_MOVE, st.step_turn if turn else st.step_move)
        D = place.step_delta(scene, ob, st.space, self.index % 3, amount * (1 if self.sign >= 0 else -1), turn,
                             place.movers(context))
        try:
            note = place.apply(context, D)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return _done(self, context, note, f"'{place._name(ob)}' " + ("turned" if turn else "moved"))


class FRESING_OT_place_floor(bpy.types.Operator):
    """Puts what is selected on the floor: moves it straight up or down until its lowest point sits on the floor
    (the surroundings' floor when there are surroundings, else height 0). It stays there"""

    bl_idname = "fresing.place_floor"
    bl_label = "Put on the floor"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _poll_place(cls, context)

    def execute(self, context):
        objs = place.movers(context)
        note = "The built animation was taken off: Build again" if place._take_build_off(context.scene) else ""
        dz = place.put_on_floor(context.scene, objs)
        return _done(self, context, note, f"On the floor (moved {dz * 1000.0:+.1f} mm)")


class FRESING_OT_place_back(bpy.types.Operator):
    """Puts what is selected back where the CAD file has it (a model: back where it was imported). Its joints'
    axes go back with it; a move made by hand (G / R) is taken off too"""

    bl_idname = "fresing.place_back"
    bl_label = "Back to the CAD place"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _poll_place(cls, context)

    def execute(self, context):
        objs = place.movers(context)
        note = place.back_to_cad(context.scene, objs)
        what = ("Back where it was imported" if all(place.is_root(o) for o in objs)
                else "Back on its CAD place")
        return _done(self, context, note, what)


class FRESING_OT_place_lock(bpy.types.Operator):
    """Locked: it does not move by itself (G, Place and the arrows leave it); it still moves with the subassembly it
    is in and with its joints. Unlocked: Place, G and R move and turn it. Click to switch"""

    bl_idname = "fresing.place_lock"
    bl_label = "Locked in place"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        from . import lock
        if lock.ON[0]:
            cls.poll_message_set(lock.MESSAGE)
            return False
        return True

    def execute(self, context):
        ob = bpy.data.objects.get(self.name) if self.name else place.target(context)
        if ob is None:
            return {"CANCELLED"}
        set_lock(ob, not place.locked(ob))
        return {"FINISHED"}


def set_lock(ob, on: bool, tree=None) -> None:
    """Lock or unlock a subassembly (its own parts with it, as 2 Structure's Locked in place) or one part."""
    if ob.get(build.PROP_KIND) == "assembly":
        logic.set_locked(ob, on, tree)
    else:
        ob[build.PROP_LOCKED] = on
        ob.lock_location = (on,) * 3
        ob.lock_rotation = (on,) * 3
        ob.lock_scale = (True,) * 3


# ---------------------------------------------------------------------------
# Move / Turn with the mouse
# ---------------------------------------------------------------------------

HINT = {"MOVE": "Move: X / Y / Z locks the axis, type a number (mm), click to place, Esc cancels",
        "TURN": "Turn: X / Y / Z picks the axis (Z when none), type a number (degrees), click to place, Esc cancels"}
NUMBER_KEYS = {"ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5", "SIX": "6",
               "SEVEN": "7", "EIGHT": "8", "NINE": "9", "NUMPAD_0": "0", "NUMPAD_1": "1", "NUMPAD_2": "2",
               "NUMPAD_3": "3", "NUMPAD_4": "4", "NUMPAD_5": "5", "NUMPAD_6": "6", "NUMPAD_7": "7", "NUMPAD_8": "8",
               "NUMPAD_9": "9", "PERIOD": ".", "NUMPAD_PERIOD": ".", "MINUS": "-", "NUMPAD_MINUS": "-"}
RUNNING = [""]                     # "MOVE" / "TURN" while one runs (tests)


def _view(context):
    """(area, window region, region_3d) of the 3D view the button was pressed in (else the first one)."""
    areas = [context.area] if context.area is not None and context.area.type == "VIEW_3D" else []
    areas += [a for a in context.screen.areas if a.type == "VIEW_3D" and a not in areas]
    for area in areas:
        for region in area.regions:
            if region.type == "WINDOW":
                return area, region, area.spaces.active.region_3d
    return None, None, None


class FRESING_OT_place_mouse(bpy.types.Operator):
    """Move: drag what is selected with the mouse (X / Y / Z locks the axis, type a number in mm, click to place, Esc
    cancels). Turn: turn it with the mouse (X / Y / Z picks the axis, type degrees). Snap applies. It stays where you
    put it"""

    bl_idname = "fresing.place_mouse"
    bl_label = "Move with the mouse"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=(("MOVE", "Move", ""), ("TURN", "Turn", "")), default="MOVE",
                       options={"SKIP_SAVE"})
    # what the move ended at (also for scripts / tests: run it without the mouse)
    axis: IntProperty(default=-1, min=-1, max=2, options={"SKIP_SAVE"})
    value: FloatProperty(default=0.0, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.mode == "TURN":
            return ("Turns what is selected with the mouse about the middle of its box: X / Y / Z picks the axis "
                    "(Z when none), type a number in degrees, click to place, Esc cancels. Snap applies. It stays")
        return ("Moves what is selected with the mouse: X / Y / Z locks the axis, type a number in mm, click to place, "
                "Esc cancels. Snap applies. It stays where you put it")

    @classmethod
    def poll(cls, context):
        return _poll_place(cls, context)

    # ---- the move as a matrix ----
    def _axis_vec(self, i: int) -> Vector:
        a = Vector((0.0, 0.0, 0.0))
        a[i] = 1.0
        if self._space != "WORLD":
            a = self._axes @ a
        return a

    def _delta(self) -> Matrix:
        if self.mode == "MOVE":
            if self.axis >= 0:
                return Matrix.Translation(self._axis_vec(self.axis) * (self.value / 1000.0))
            return Matrix.Translation(self._free)
        a = self._axis_vec(self.axis if self.axis >= 0 else 2)
        p = self._pivot
        return Matrix.Translation(p) @ Matrix.Rotation(math.radians(self.value), 4, a) @ Matrix.Translation(-p)

    def execute(self, context):                     # scripts and tests: the move in one go
        if self.mode == "MOVE" and self.axis < 0:
            self.axis = 0
        self._prepare(context)
        try:
            note = place.apply(context, self._delta())
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return _done(self, context, note, "Moved" if self.mode == "MOVE" else "Turned")

    def _prepare(self, context) -> None:
        scene = context.scene
        self._objs = place.movers(context)
        self._space = scene.fresing.place.space
        ob = place.target(context)
        self._axes = place.axes(scene, ob) if ob is not None else Matrix.Identity(3)
        self._pivot = place.pivot(scene, self._objs) if self._objs else Vector()
        self._free = Vector()

    # ---- the modal ----
    def invoke(self, context, event):
        why = place.refused(context)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        self._area, self._region, self._rv3d = _view(context)
        if self._region is None:
            return self.execute(context)
        self._prepare(context)
        if place._take_build_off(context.scene):
            self.report({"INFO"}, "The built animation was taken off: Build again")
        self._start = {o.name: o.matrix_basis.copy() for o in self._objs}
        follow = place._follow_joints(context.scene, self._objs)
        self._frames = {j.frame.name: j.frame.matrix_basis.copy() for j in follow.values()}
        self._typed = ""
        self.axis, self.value = -1, 0.0
        self._mouse0 = self._mouse(event)
        self._angle0 = self._screen_angle(self._mouse0)
        self._hit0 = self._on_plane(self._mouse0)
        RUNNING[0] = self.mode
        context.window_manager.modal_handler_add(self)
        self._text(context)
        return {"RUNNING_MODAL"}

    def _mouse(self, event) -> Vector:
        return Vector((event.mouse_x - self._region.x, event.mouse_y - self._region.y))

    def _on_plane(self, m: Vector) -> Vector:
        return view3d_utils.region_2d_to_location_3d(self._region, self._rv3d, m, self._pivot)

    def _screen_angle(self, m: Vector) -> float:
        c = view3d_utils.location_3d_to_region_2d(self._region, self._rv3d, self._pivot) or Vector((0.0, 0.0))
        return math.atan2(m.y - c.y, m.x - c.x)

    def _follow_mouse(self, m: Vector) -> None:
        if self._typed:
            return
        snap = self._snap()
        if self.mode == "MOVE":
            if self.axis < 0:
                d = self._on_plane(m) - self._hit0
                self._free = Vector([core.snap(v * 1000.0, snap) / 1000.0 for v in d])
                self.value = d.length * 1000.0
                return
            a = self._axis_vec(self.axis)
            o = view3d_utils.region_2d_to_origin_3d(self._region, self._rv3d, m)
            v = view3d_utils.region_2d_to_vector_3d(self._region, self._rv3d, m)
            o0 = view3d_utils.region_2d_to_origin_3d(self._region, self._rv3d, self._mouse0)
            v0 = view3d_utils.region_2d_to_vector_3d(self._region, self._rv3d, self._mouse0)
            p = self._pivot
            now = geometry.intersect_line_line(p, p + a, o, o + v)
            start = geometry.intersect_line_line(p, p + a, o0, o0 + v0)
            if now is None or start is None:
                return
            self.value = core.snap((now[0] - start[0]).dot(a) * 1000.0, snap)
            return
        a = self._axis_vec(self.axis if self.axis >= 0 else 2)
        toward = self._rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))
        sign = 1.0 if a.dot(toward) >= 0 else -1.0
        ang = math.degrees(self._screen_angle(m) - self._angle0) * sign
        self.value = core.snap(core.wrap_degrees(ang), snap)

    def _snap(self) -> float:
        st = bpy.context.scene.fresing.place
        if self.mode == "MOVE":
            return core.size_of(core.SNAP_MOVE, st.snap_move)
        return core.size_of(core.SNAP_TURN, st.snap_turn)

    def _show(self, context) -> None:
        """The move as it would end, shown on the objects' own matrices (put right at the end)."""
        D = self._delta()
        for o in self._objs:
            o.matrix_basis = self._start[o.name]
        for n, m in self._frames.items():
            bpy.data.objects[n].matrix_basis = m
        context.view_layer.update()
        from . import joints
        follow = place._follow_joints(context.scene, self._objs)
        moved = set()
        for j in follow.values():
            f = j.frame
            f.matrix_basis = place._pw(f).inverted() @ D @ f.matrix_world
            moved.update(o.name for o in joints.members(j))
        for o in self._objs:
            if o.name not in moved:
                o.matrix_basis = place._pw(o).inverted() @ D @ o.matrix_world
        self._text(context)

    def _text(self, context) -> None:
        unit = "mm" if self.mode == "MOVE" else "°"
        axis = "XYZ"[self.axis] if self.axis >= 0 else ("free" if self.mode == "MOVE" else "Z")
        value = self._typed or f"{self.value:.1f}"
        head = f"{'Move' if self.mode == 'MOVE' else 'Turn'} {axis}: {value} {unit}"
        if self._area is not None:
            self._area.header_text_set(head)
        try:
            context.workspace.status_text_set(HINT[self.mode])
        except AttributeError:
            pass

    def _end(self, context) -> None:
        for o in self._objs:
            if o.name in bpy.data.objects:
                o.matrix_basis = self._start[o.name]
        for n, m in self._frames.items():
            if n in bpy.data.objects:
                bpy.data.objects[n].matrix_basis = m
        context.view_layer.update()
        if self._area is not None:
            self._area.header_text_set(None)
        try:
            context.workspace.status_text_set(None)
        except AttributeError:
            pass
        RUNNING[0] = ""

    def modal(self, context, event):
        t = event.type
        if t in ("MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN", "TRACKPADZOOM"):
            return {"PASS_THROUGH"}
        if t == "MOUSEMOVE":
            self._follow_mouse(self._mouse(event))
            self._show(context)
            return {"RUNNING_MODAL"}
        if event.value != "PRESS":
            return {"RUNNING_MODAL"}
        if t in ("ESC", "RIGHTMOUSE"):
            self._end(context)
            self.report({"INFO"}, "Cancelled: it is back where it was")
            return {"CANCELLED"}
        if t in ("LEFTMOUSE", "RET", "NUMPAD_ENTER"):
            if self.mode == "MOVE" and self.axis < 0 and self._typed:
                self.axis = 0
            D = self._delta()
            self._end(context)
            try:
                note = place.apply(context, D)
            except RuntimeError as exc:
                self.report({"WARNING"}, str(exc))
                return {"CANCELLED"}
            _done(self, context, note, "Moved" if self.mode == "MOVE" else "Turned")
            return {"FINISHED"}
        if t in ("X", "Y", "Z"):
            i = "XYZ".index(t)
            self.axis = -1 if self.axis == i and self.mode == "MOVE" else i
            self.value = 0.0
            self._free = Vector()
            self._follow_mouse(self._mouse(event))
            self._show(context)
            return {"RUNNING_MODAL"}
        if t in NUMBER_KEYS or t == "BACK_SPACE":
            self._typed = self._typed[:-1] if t == "BACK_SPACE" else self._typed + NUMBER_KEYS[t]
            try:
                self.value = float(self._typed) if self._typed not in ("", "-", ".", "-.") else 0.0
            except ValueError:
                self._typed = self._typed[:-1]
            if self.mode == "MOVE" and self.axis < 0:
                self.axis = 0
            if not self._typed:
                self._follow_mouse(self._mouse(event))
            self._show(context)
            return {"RUNNING_MODAL"}
        return {"RUNNING_MODAL"}


# ---------------------------------------------------------------------------
# the Move / turn… window (right-click) and Remove…
# ---------------------------------------------------------------------------

class FRESING_OT_place_window(bpy.types.Operator):
    """Opens Place in a window of its own: X / Y / Z and turns of what is selected, steps, snap, Put on the floor,
    Back to the CAD place. The window stays open while you click in the view (select something else: it follows)"""

    bl_idname = "fresing.place_window"
    bl_label = "Move / turn…"

    @classmethod
    def poll(cls, context):
        from . import lock
        return getattr(context.scene, "fresing", None) is not None and not lock.ON[0]

    def invoke(self, context, event):
        return form_window.open(self, context, width=360, height=470, title="Move / turn", confirm=None)

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        from . import ui_place
        ui_place.draw_place(self.layout, context, window=True)


class FRESING_OT_remove(bpy.types.Operator):
    """Removes the chosen model, subassembly or parts from the project with everything that lives on them: joints,
    cylinders, mechanisms, hoses, cables, labels, logos and steps that only move them. A window lists what goes
    first. Ctrl+Z brings it all back; the import stays (1 Import > Imported models). Clean-up only hides parts"""

    bl_idname = "fresing.remove"
    bl_label = "Remove…"
    bl_options = {"REGISTER", "UNDO"}

    names: StringProperty(options={"SKIP_SAVE", "HIDDEN"})          # object names, one per line

    @classmethod
    def poll(cls, context):
        from . import lock
        if getattr(context.scene, "fresing", None) is None:
            return False
        if lock.ON[0]:
            cls.poll_message_set(lock.MESSAGE)
            return False
        return True

    def _objs(self, context) -> list:
        if self.names:
            objs = [bpy.data.objects[n] for n in self.names.split("\n") if n in bpy.data.objects]
        else:
            objs = list(context.selected_objects)
        return remove.chosen(context.scene, objs)

    def invoke(self, context, event):
        objs = self._objs(context)
        if not objs:
            self.report({"WARNING"}, "Select a model, subassembly or part first: click it in the view or a row of "
                                     "2 Structure")
            return {"CANCELLED"}
        self.names = "\n".join(o.name for o in objs)
        p = remove.plan(context.scene, objs)
        return form_window.open(self, context, width=420, height=300, title=core.title(p), confirm="Remove",
                                extra={"plan": p})

    def draw(self, context):
        layout = self.layout
        objs = self._objs(context)
        p = remove.plan(context.scene, objs) if objs else {"names": []}
        col = layout.column(align=True)
        col.label(text=core.title(p), icon="TRASH")
        layout.separator()
        from .ui import wrap
        for line in remove.lines(p) if objs else ["It is not there any more: close this window"]:
            wrap(layout, context, line)

    def execute(self, context):
        objs = self._objs(context)
        if not objs:
            self.report({"WARNING"}, "Nothing to remove: it is not there any more")
            return {"CANCELLED"}
        p = remove.remove(context.scene, objs)
        msg = f"Removed {', '.join(p['names'][:2])}{' …' if len(p['names']) > 2 else ''} " \
              f"({plural(p['parts'], 'part')}). Ctrl+Z brings it back"
        context.scene.fresing.last_message = msg
        place.NOTE[0] = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class FRESING_OT_remove_key(bpy.types.Operator):
    """Delete or X in the 3D view: opens the Remove window for what is selected (it lists what goes; nothing is lost
    until you press Remove). In Full access the keys are Blender's own"""

    bl_idname = "fresing.remove_key"
    bl_label = "Remove (Delete)"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        from . import lock
        return (lock.keys_quiet() and context.mode == "OBJECT"
                and getattr(context.scene, "fresing", None) is not None)

    def invoke(self, context, event):
        if not remove.chosen(context.scene, list(context.selected_objects)):
            self.report({"INFO"}, "Select a model, subassembly or part first: Delete then opens the Remove window")
            return {"CANCELLED"}
        return bpy.ops.fresing.remove("INVOKE_DEFAULT")

    def execute(self, context):
        return self.invoke(context, None)


CLASSES = (FRESING_OT_place_step, FRESING_OT_place_floor, FRESING_OT_place_back, FRESING_OT_place_lock,
           FRESING_OT_place_mouse, FRESING_OT_place_window, FRESING_OT_remove, FRESING_OT_remove_key)
