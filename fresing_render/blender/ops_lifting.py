"""Operators of 8 Lifting plan (task 0201): first use, the library, placing and moving a crane, its pose and set-up,
the load and its CoG marker, Hook to here."""

from __future__ import annotations

import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from mathutils import Vector

from ..core import lifting as core
from . import build, lifting, logic


def _redraw(context=None) -> None:
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", []):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _ok(context) -> bool:
    return context.scene is not None and lifting.understood()


def _status(context, text) -> None:
    try:
        context.workspace.status_text_set(text)
    except Exception:  # noqa: BLE001
        pass
    if context.area is not None:
        try:
            context.area.header_text_set(text)
        except Exception:  # noqa: BLE001
            pass


def _region_ray(context, event):
    from bpy_extras import view3d_utils
    from .ops_motion import _inside, over_panel
    area = context.area
    if area is None or area.type != "VIEW_3D" or over_panel(context, event):
        return None
    region = next((r for r in area.regions if r.type == "WINDOW" and _inside(r, event)), None)
    if region is None or region.data is None:
        return None
    co = (event.mouse_x - region.x, event.mouse_y - region.y)
    return (view3d_utils.region_2d_to_origin_3d(region, region.data, co),
            view3d_utils.region_2d_to_vector_3d(region, region.data, co))


def surface_hit(context, origin, direction, ignore=frozenset(), ground_z: float = 0.0):
    """Where a ray meets the first surface that is not in ``ignore`` (object names) – a part, the floor, a deck – or
    else the level plane at ``ground_z``: (point, what) or None."""
    scene = context.scene
    dg = context.evaluated_depsgraph_get()
    o, d = Vector(origin), Vector(direction).normalized()
    for _ in range(64):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, o, d)
        if not hit:
            break
        ob = getattr(ob, "original", ob)
        if ob.name in ignore or ob.get("fr_cog"):
            o = loc + d * 1e-4
            continue
        return np.array(loc), str(ob.get(build.PROP_NAME, ob.name))
    if abs(d.z) > 1e-9:
        t = (ground_z - o.z) / d.z
        if t > 0:
            return np.array(o + d * t), "the ground"
    return None


# ---------------------------------------------------------------------------------------------------------------------
# first use, library

class FRESING_OT_lifting_understand(bpy.types.Operator):
    """Shows the planning-aid line once: tick I understand to use the Lifting plan (asked once per user)"""
    bl_idname = "fresing.lifting_understand"
    bl_label = "Lifting plans – planning aid"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520, confirm_text="I understand")

    def draw(self, context):
        import textwrap
        col = self.layout.column(align=True)
        for i, line in enumerate(textwrap.wrap(core.PLANNING_AID, 80)):
            col.label(text=line, icon="INFO" if i == 0 else "BLANK1")
        col.separator()
        for i, line in enumerate(textwrap.wrap(core.SAMPLE_MARK, 80)):
            col.label(text=line, icon="ERROR" if i == 0 else "BLANK1")

    def execute(self, context):
        lifting.set_understood(True)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_library(bpy.types.Operator):
    """Reads the lifting equipment library again (the built-in samples and your own items in your Lifting equipment folders
    'Lifting equipment')"""
    bl_idname = "fresing.lifting_library"
    bl_label = "Refresh the library"

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def execute(self, context):
        from . import locations
        locations.look_again()                    # task 0272: the folders looked at again
        items = lifting.library(force=True)
        self.report({"INFO"}, f"{len(items)} items in the lifting library")
        return {"FINISHED"}


class FRESING_OT_lifting_pick(bpy.types.Operator):
    """Picks this item: Place… below places it"""
    bl_idname = "fresing.lifting_pick"
    bl_label = "Pick equipment"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def execute(self, context):
        lifting.plan(context.scene).pick = self.path
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# placing and moving

class _Placer:
    """The modal part shared by Place… and Move…: the crane follows the mouse over the ground (or any surface), the
    mouse wheel turns it, a click puts it down, Esc cancels."""

    STEP = math.radians(15.0)

    def _start_placing(self, context, crane):
        self._crane = crane.name
        self._ignore = frozenset([crane.root.name] + [o.name for o in logic.descendants(crane.root)])
        self._ignore = self._ignore | {o.name for o in bpy.data.objects
                                       if o.name.startswith(("Joint " + crane.name, "Cylinder " + crane.name))}
        self._heading = lifting.heading_of(crane)
        self._ground = float(crane.root.matrix_world.translation.z)
        self._words = (f"{crane.name}: click where its slew axis stands (ground, deck or any surface) · mouse wheel: "
                       "turn · Esc: cancel")
        _status(context, self._words)

    def _crane_item(self, context):
        return lifting.plan(context.scene).cranes.get(self._crane)

    def _follow(self, context, event) -> None:
        ray = _region_ray(context, event)
        crane = self._crane_item(context)
        if ray is None or crane is None:
            return
        hit = surface_hit(context, ray[0], ray[1], self._ignore, self._ground)
        if hit is None:
            return
        self._spot = hit
        lifting.place_at(crane, lifting.rest_point(context.scene, hit[0]), self._heading)
        _status(context, f"{self._words} – on {hit[1]}")

    def _placing_event(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return "cancel"
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and event.value == "PRESS":
            from .ops_motion import over_panel
            if over_panel(context, event):
                return "pass"
            self._heading += self.STEP if event.type == "WHEELUPMOUSE" else -self.STEP
            crane = self._crane_item(context)
            if crane is not None:
                lifting.place_at(crane, lifting.location_of(crane), self._heading)
            return "run"
        if event.type == "MOUSEMOVE":
            self._follow(context, event)
            return "run"
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if _region_ray(context, event) is None:
                return "pass"
            self._follow(context, event)
            return "done"
        return "pass"

    def _end(self, context):
        _status(context, None)
        try:
            context.window.cursor_modal_restore()
        except Exception:  # noqa: BLE001
            pass
        _redraw()


class FRESING_OT_lifting_place(_Placer, bpy.types.Operator):
    """Places the picked crane: its model comes into the project, is rigged (joints, cylinders, poses) and follows
    the mouse – click where it stands, the mouse wheel turns it, Esc cancels"""
    bl_idname = "fresing.lifting_place"
    bl_label = "Place…"
    bl_options = {"REGISTER", "UNDO"}

    path: StringProperty(options={"SKIP_SAVE"}, description="The equipment item ('' = the picked one)")
    location: FloatVectorProperty(size=3, options={"SKIP_SAVE"})
    heading: FloatProperty(options={"SKIP_SAVE"}, subtype="ANGLE")
    name: StringProperty(options={"SKIP_SAVE"})

    _timer = None
    _job = None

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def _item(self, context):
        path = self.path or lifting.plan(context.scene).pick
        if not path:
            self.report({"WARNING"}, "Pick a crane in the list first")
            return None
        item = lifting.item_at(path)
        if not item.ok:
            self.report({"ERROR"}, item.problems[0])
            return None
        if not item.model or not item.model.lower().endswith((".step", ".stp")):
            self.report({"ERROR"}, f"{item.name}: no STEP model next to its file")
            return None
        return item

    def execute(self, context):
        item = self._item(context)
        if item is None:
            return {"CANCELLED"}
        try:
            c = lifting.place(context, item.path, tuple(self.location), self.heading, self.name)
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        lifting.plan(context.scene).message = f"Placed {c.name}."
        self.report({"INFO"}, f"Placed {c.name}")
        return {"FINISHED"}

    def invoke(self, context, event):
        item = self._item(context)
        if item is None:
            return {"CANCELLED"}
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)
        from ..importer.runner import ImportJob
        from .ops_import import cache_root
        self._itempath = item.path
        self._first = not build.model_roots(context.scene)
        self._job = ImportJob(item.model, "normal", cache_root())
        self._spot = None
        if not self._job.cached:
            self._job.start()
        self._phase = "import"
        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        context.window_manager.modal_handler_add(self)
        _status(context, f"Reading {item.name}… Esc: cancel")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if self._phase == "import":
            if event.type == "ESC" and event.value == "PRESS":
                self._job.cancel()
                self._stop_timer(context)
                self._end(context)
                return {"CANCELLED"}
            if event.type != "TIMER":
                return {"PASS_THROUGH"}
            try:
                done = self._job.cached or self._job.poll()
            except Exception as exc:  # noqa: BLE001
                self._job.error = self._job.error or str(exc)
                done = True
            if not done:
                _status(context, f"Reading the crane: {self._job.message} ({self._job.pct:.0f}%) – Esc: cancel")
                return {"PASS_THROUGH"}
            self._stop_timer(context)
            if self._job.error:
                self._end(context)
                self.report({"ERROR"}, f"The crane's model could not be read: {self._job.error}")
                return {"CANCELLED"}
            try:
                item = lifting.item_at(self._itempath)
                up = str((item.data.get("rig") or {}).get("up_axis", "Z"))
                root = lifting.finish_cache(context, self._job.cache_dir, self._first, up)
                c = lifting.rig_model(context, root, item, self.name)
            except Exception as exc:  # noqa: BLE001
                self._end(context)
                self.report({"ERROR"}, f"The crane could not be rigged: {exc}")
                return {"CANCELLED"}
            self._phase = "place"
            self._start_placing(context, c)
            context.window.cursor_modal_set("CROSSHAIR")
            self._follow(context, event)
            return {"RUNNING_MODAL"}
        what = self._placing_event(context, event)
        if what == "cancel":
            crane = self._crane_item(context)
            if crane is not None:
                lifting.remove(context.scene, crane)
            self._end(context)
            self.report({"INFO"}, "Placing cancelled")
            return {"CANCELLED"}
        if what == "done":
            self._end(context)
            crane = self._crane_item(context)
            lifting.plan(context.scene).message = f"Placed {crane.name}." if crane else ""
            return {"FINISHED"}
        return {"RUNNING_MODAL"} if what == "run" else {"PASS_THROUGH"}

    def _stop_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class FRESING_OT_lifting_move(_Placer, bpy.types.Operator):
    """Places the crane again: it follows the mouse – click where it stands, the mouse wheel turns it, Esc puts it
    back"""
    bl_idname = "fresing.lifting_move"
    bl_label = "Move…"
    bl_options = {"REGISTER", "UNDO"}

    location: FloatVectorProperty(size=3, options={"SKIP_SAVE"})
    heading: FloatProperty(options={"SKIP_SAVE"}, subtype="ANGLE")

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_crane(context.scene) is not None

    def execute(self, context):
        c = lifting.active_crane(context.scene)
        lifting.place_at(c, tuple(self.location), self.heading)
        return {"FINISHED"}

    def invoke(self, context, event):
        c = lifting.active_crane(context.scene)
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)
        self._was = (lifting.location_of(c), lifting.heading_of(c))
        self._spot = None
        self._start_placing(context, c)
        context.window.cursor_modal_set("CROSSHAIR")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        what = self._placing_event(context, event)
        if what == "cancel":
            c = self._crane_item(context)
            if c is not None:
                lifting.place_at(c, self._was[0], self._was[1])
            self._end(context)
            return {"CANCELLED"}
        if what == "done":
            self._end(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"} if what == "run" else {"PASS_THROUGH"}


class FRESING_OT_lifting_remove(bpy.types.Operator):
    """Takes the crane out of the project: its model, joints, cylinders, poses and its place in the plan (also when
    its model was deleted)"""
    bl_idname = "fresing.lifting_remove"
    bl_label = "Remove the crane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.picked_crane(context.scene) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        c = lifting.picked_crane(context.scene)
        name = c.name
        lifting.remove(context.scene, c)
        lifting.plan(context.scene).message = f"Removed {name}."
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_select(bpy.types.Operator):
    """Makes this crane the one the panel shows and Hook to here moves"""
    bl_idname = "fresing.lifting_select"
    bl_label = "Use this crane"
    bl_options = {"INTERNAL"}

    index: IntProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def execute(self, context):
        lifting.plan(context.scene).crane_index = self.index
        return {"FINISHED"}


class FRESING_OT_lifting_load_select(bpy.types.Operator):
    """Makes this load the one the panel shows and Above the load uses"""
    bl_idname = "fresing.lifting_load_select"
    bl_label = "Use this load"
    bl_options = {"INTERNAL"}

    index: IntProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def execute(self, context):
        lifting.plan(context.scene).load_index = self.index
        return {"FINISHED"}


class FRESING_OT_lifting_pose(bpy.types.Operator):
    """Puts the crane in this pose of its file (only this crane moves)"""
    bl_idname = "fresing.lifting_pose"
    bl_label = "Crane pose"
    bl_options = {"REGISTER", "UNDO"}

    pose: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_crane(context.scene) is not None

    def execute(self, context):
        c = lifting.active_crane(context.scene)
        if not lifting.apply_pose(context.scene, c, self.pose):
            self.report({"WARNING"}, f"{c.name} has no pose '{self.pose}'")
            return {"CANCELLED"}
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_setup_value(bpy.types.Operator):
    """Sets the crane's counterweight or outrigger spread to one of its charts' values"""
    bl_idname = "fresing.lifting_setup_value"
    bl_label = "Set-up value"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    key: StringProperty(options={"SKIP_SAVE"})
    value: FloatProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_crane(context.scene) is not None

    def execute(self, context):
        c = lifting.active_crane(context.scene)
        if self.key == "counterweight":
            c.counterweight = self.value
        elif self.key == "outriggers":
            c.spread_from_pose = False
            c.outriggers = self.value
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# the load

class FRESING_OT_lifting_load_selected(bpy.types.Operator):
    """Makes the selected parts or sub-assemblies the load: its mass, volume and centre of gravity are worked out
    (a part can be in one load only)"""
    bl_idname = "fresing.lifting_load_selected"
    bl_label = "Use selected parts"
    bl_options = {"REGISTER", "UNDO"}

    names: StringProperty(options={"SKIP_SAVE", "HIDDEN"}, description="Object names, one per line ('' = selected)")

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def execute(self, context):
        if self.names:
            objs = [bpy.data.objects.get(n) for n in self.names.splitlines() if n]
        else:
            objs = list(context.selected_objects)
        try:
            ld = lifting.new_load(context.scene, objs)
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        if ld.open_parts:
            self.report({"WARNING"}, f"Not closed solids (their box was used): {ld.open_parts}")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_box(bpy.types.Operator):
    """Adds a box load at the 3D cursor: type its length, width, height and mass"""
    bl_idname = "fresing.lifting_box"
    bl_label = "Box…"
    bl_options = {"REGISTER", "UNDO"}

    size: FloatVectorProperty(name="Size", size=3, default=(2.0, 1.0, 1.0), min=0.01, subtype="XYZ_LENGTH",
                              unit="LENGTH", description="Length x width x height of the box, m")
    mass: FloatProperty(name="Mass (t)", default=1.0, min=0.0, precision=3, description="The box load's mass, t")

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def invoke(self, context, event):
        L = lifting.plan(context.scene)
        self.size, self.mass = tuple(L.box_size), L.box_mass
        from . import form_window
        return form_window.open(self, context, width=340, height=190, title="Box load", confirm="Add",
                                icon="MESH_CUBE")

    def execute(self, context):
        L = lifting.plan(context.scene)
        L.box_size, L.box_mass = tuple(self.size), self.mass
        lifting.new_box(context.scene, tuple(self.size), self.mass)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_load_remove(bpy.types.Operator):
    """Takes the load out of the plan (its parts stay in the project; a box load's box goes)"""
    bl_idname = "fresing.lifting_load_remove"
    bl_label = "Remove the load"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_load(context.scene) is not None

    def execute(self, context):
        lifting.remove_load(context.scene, lifting.active_load(context.scene))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_load_refresh(bpy.types.Operator):
    """Works the load's volume, mass and centre of gravity out again (after the parts or their groups changed)"""
    bl_idname = "fresing.lifting_load_refresh"
    bl_label = "Work out again"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_load(context.scene) is not None

    def execute(self, context):
        lifting._SOLID.clear()                     # the parts' meshes read again (a mesh edited in place)
        lifting.refresh_load(context.scene, lifting.active_load(context.scene))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_cog_move(bpy.types.Operator):
    """Moves the CoG marker by hand (G to move, click to drop): the CoG is then marked 'set by hand'"""
    bl_idname = "fresing.lifting_cog_move"
    bl_label = "Move"
    bl_options = {"REGISTER", "UNDO"}

    offset: FloatVectorProperty(size=3, options={"SKIP_SAVE"}, description="A move in m (scripts and tests)")

    @classmethod
    def poll(cls, context):
        ld = lifting.active_load(context.scene) if _ok(context) else None
        return ld is not None and ld.marker is not None

    def execute(self, context):
        ld = lifting.active_load(context.scene)
        mk = ld.marker
        M = mk.matrix_world.copy()
        M.translation = M.translation + Vector(self.offset)
        mk.matrix_world = M
        _redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        ld = lifting.active_load(context.scene)
        mk = ld.marker
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)
        for o in context.selected_objects:
            o.select_set(False)
        mk.hide_set(False)
        mk.hide_select = False
        mk.select_set(True)
        context.view_layer.objects.active = mk
        try:
            bpy.ops.transform.translate("INVOKE_DEFAULT")
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_lifting_cog_back(bpy.types.Operator):
    """Puts the CoG marker back where it was worked out from the parts' volumes"""
    bl_idname = "fresing.lifting_cog_back"
    bl_label = "Back to computed"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ld = lifting.active_load(context.scene) if _ok(context) else None
        return ld is not None and lifting.cog_by_hand(ld)

    def execute(self, context):
        lifting.back_to_computed(context.scene, lifting.active_load(context.scene))
        _redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# Hook to here

def _hook(op, context, point) -> set:
    scene = context.scene
    c = lifting.active_crane(scene)
    try:
        a = lifting.hook_to(scene, c, point, lifting.active_load(scene))
    except lifting.LR.ReachError as exc:
        lifting.plan(scene).message = str(exc)
        op.report({"WARNING"}, str(exc))
        return {"CANCELLED"}
    _redraw()
    if not a.ok:
        op.report({"WARNING"}, a.reason)
        return {"CANCELLED"}
    op.report({"WARNING"} if a.warning else {"INFO"}, lifting.plan(scene).message)
    return {"FINISHED"}


class FRESING_OT_lifting_hook_here(bpy.types.Operator):
    """Click a point: the crane slews, luffs and telescopes (or folds its knuckle) and pays out the hoist so the hook
    hangs plumb on it, inside its joints' limits. Out of reach: it says by how much and stays as it was"""
    bl_idname = "fresing.lifting_hook_here"
    bl_label = "Hook to here"
    bl_options = {"REGISTER", "UNDO"}

    point: FloatVectorProperty(size=3, options={"SKIP_SAVE"}, description="The point (world, m) for scripts")

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_crane(context.scene) is not None

    def execute(self, context):
        return _hook(self, context, tuple(self.point))

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)
        c = lifting.active_crane(context.scene)
        self._ignore = frozenset([c.root.name] + [o.name for o in logic.descendants(c.root)])
        self._ground = float(c.root.matrix_world.translation.z)
        context.window.cursor_modal_set("CROSSHAIR")
        _status(context, f"{c.name}: click where the hook should be · Esc: cancel")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        _status(context, None)
        context.window.cursor_modal_restore()

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            ray = _region_ray(context, event)
            if ray is None:
                return {"PASS_THROUGH"}
            hit = surface_hit(context, ray[0], ray[1], self._ignore, self._ground)
            if hit is None:
                return {"RUNNING_MODAL"}
            self._end(context)
            return _hook(self, context, tuple(hit[0]))
        return {"PASS_THROUGH"}


class FRESING_OT_lifting_hook_above(bpy.types.Operator):
    """Puts the hook plumb above the load's centre of gravity, the set clearance above the load's top"""
    bl_idname = "fresing.lifting_hook_above"
    bl_label = "Above the load"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not _ok(context):
            return False
        return lifting.active_crane(context.scene) is not None and lifting.active_load(context.scene) is not None

    def execute(self, context):
        p = lifting.above_load(context.scene, lifting.active_load(context.scene))
        if p is None:
            self.report({"WARNING"}, "The load has no parts")
            return {"CANCELLED"}
        return _hook(self, context, tuple(p))


# ---------------------------------------------------------------------------------------------------------------------
# the lift path and its checks (task 0348)

def _path_ok(context) -> bool:
    return _ok(context) and lifting.active_crane(context.scene) is not None


def _propose(op, context, point=None) -> set:
    from . import lifting_path
    scene = context.scene
    try:
        pr = lifting_path.propose(scene, point=point)
    except lifting.LR.ReachError as exc:
        lifting.plan(scene).message = str(exc)
        op.report({"WARNING"}, str(exc))
        return {"CANCELLED"}
    _redraw()
    if not pr.ok:
        op.report({"WARNING"}, pr.reason)
        return {"CANCELLED"}
    op.report({"INFO"}, lifting.plan(scene).message)
    return {"FINISHED"}


class FRESING_OT_lifting_set_down_point(bpy.types.Operator):
    """Click where the load is set down (ground, deck, a truck bed): the app proposes the lift from where the load hangs
    now – hoist clear, slew, luff / telescope, travel, lower – as steps of an animation you can change"""
    bl_idname = "fresing.lifting_set_down_point"
    bl_label = "Set-down point"
    bl_options = {"REGISTER", "UNDO"}

    point: FloatVectorProperty(size=3, options={"SKIP_SAVE"}, description="The point (world, m) for scripts")

    @classmethod
    def poll(cls, context):
        return _path_ok(context)

    def execute(self, context):
        return _propose(self, context, tuple(self.point))

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            return self.execute(context)
        c = lifting.active_crane(context.scene)
        ld = lifting.active_load(context.scene)
        names = [c.root.name] + [o.name for o in logic.descendants(c.root)]
        if ld is not None:
            names += [o.name for o in lifting.load_parts(ld)]
            from . import lifting_rig
            names += [o.name for o in context.scene.objects if o.get(lifting_rig.TAG) == ld.name]
        self._ignore = frozenset(names)
        self._ground = float(c.root.matrix_world.translation.z)
        context.window.cursor_modal_set("CROSSHAIR")
        _status(context, "Click where the load is set down · Esc: cancel")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        _status(context, None)
        context.window.cursor_modal_restore()

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            ray = _region_ray(context, event)
            if ray is None:
                return {"PASS_THROUGH"}
            hit = surface_hit(context, ray[0], ray[1], self._ignore, self._ground)
            if hit is None:
                return {"RUNNING_MODAL"}
            self._end(context)
            return _propose(self, context, tuple(hit[0]))
        return {"PASS_THROUGH"}


class FRESING_OT_lifting_path_propose(bpy.types.Operator):
    """Works out the lift again from where the load hangs now to the set-down point (after a change of the hoist
    clearance, the crane's pose or the load): the steps of the lift path's animation are replaced"""
    bl_idname = "fresing.lifting_path_propose"
    bl_label = "Propose the steps"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not _path_ok(context):
            return False
        if not lifting.plan(context.scene).has_set_down:
            cls.poll_message_set("Click a set-down point first")
            return False
        return True

    def execute(self, context):
        return _propose(self, context)


def _anim_items(self, context):
    if context is None or context.scene is None:
        return [("", "(none)", "")]
    out = [(a.name, a.name, "Check the lift along this animation's steps and poses")
           for a in context.scene.fresing.animations]
    return out or [("", "(no animations)", "Make one in 6 Animation")]


class FRESING_OT_lifting_path_use(bpy.types.Operator):
    """Check the lift along one of your own animations instead: its poses and steps (6 Animation) are the path"""
    bl_idname = "fresing.lifting_path_use"
    bl_label = "Use an animation"
    bl_options = {"REGISTER", "UNDO"}

    anim: bpy.props.EnumProperty(items=_anim_items, name="Animation",
                                 description="The animation whose steps and poses are the lift path")

    @classmethod
    def poll(cls, context):
        return _path_ok(context) and len(context.scene.fresing.animations) > 0

    def execute(self, context):
        from . import lifting_path
        if not self.anim:
            return {"CANCELLED"}
        lifting_path.use_animation(context.scene, self.anim)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_path_check(bpy.types.Operator):
    """Builds the lift path and works out every check along it – at the keys and between them – with each check's
    worst moment: the table shows the worst value, the limit, the status and the frame. Go there shows that moment"""
    bl_idname = "fresing.lifting_path_check"
    bl_label = "Check along the path"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from . import lifting_path
        if not _path_ok(context):
            return False
        if lifting_path.path_anim(context.scene) is None:
            cls.poll_message_set("Propose the steps or pick one of your animations first")
            return False
        return True

    def execute(self, context):
        from . import lifting_path
        try:
            lifting_path.check(context.scene)
        except (ValueError, lifting.LR.ReachError) as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        _redraw()
        self.report({"INFO"}, lifting.plan(context.scene).message)
        return {"FINISHED"}


class FRESING_OT_lifting_path_go(bpy.types.Operator):
    """Shows the worst moment of this check: the timeline goes to its frame, the crane and the load stand there"""
    bl_idname = "fresing.lifting_path_go"
    bl_label = "Go there"
    bl_options = {"REGISTER"}

    check: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        from . import lifting_path
        t = lifting_path.go_to(context.scene, self.check)
        if t is None:
            self.report({"WARNING"}, "Check along the path first")
            return {"CANCELLED"}
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_plan_sheet(bpy.types.Operator):
    """Writes the lift's plan sheet and opens it in your browser to print: the plan view (exclusion zone, reach
    rings, the ground footprint coloured by pressure, the load's path), the range diagram and every check with its
    worst moment. It goes to the project's outputs folder"""
    bl_idname = "fresing.lifting_plan_sheet"
    bl_label = "Plan sheet…"
    bl_options = {"REGISTER"}

    show: BoolProperty(default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        from . import files, lifting_zones
        try:
            path = lifting_zones.plan_sheet(context.scene)
        except (ValueError, OSError, lifting.LR.ReachError) as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        lifting.plan(context.scene).message = f"Plan sheet: {path}"
        if self.show and not bpy.app.background:
            files.open_path(path)
        self.report({"INFO"}, f"Plan sheet written: {os.path.basename(path)}")
        return {"FINISHED"}


CLASSES = (FRESING_OT_lifting_understand, FRESING_OT_lifting_library, FRESING_OT_lifting_pick,
           FRESING_OT_lifting_place, FRESING_OT_lifting_move, FRESING_OT_lifting_remove, FRESING_OT_lifting_select,
           FRESING_OT_lifting_load_select, FRESING_OT_lifting_pose, FRESING_OT_lifting_setup_value, FRESING_OT_lifting_load_selected,
           FRESING_OT_lifting_box, FRESING_OT_lifting_load_remove, FRESING_OT_lifting_load_refresh,
           FRESING_OT_lifting_cog_move, FRESING_OT_lifting_cog_back, FRESING_OT_lifting_hook_here,
           FRESING_OT_lifting_hook_above, FRESING_OT_lifting_set_down_point, FRESING_OT_lifting_path_propose,
           FRESING_OT_lifting_path_use, FRESING_OT_lifting_path_check, FRESING_OT_lifting_path_go,
           FRESING_OT_lifting_plan_sheet)
