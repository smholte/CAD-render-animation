"""Operators of 8 Lifting plan > Rigging (task 0232): lift points, gear, Hang on the hook, Set down, Remove, go to a
leg, and Reeve the rope (8 Lifting plan > Equipment)."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatVectorProperty, IntProperty, StringProperty

from . import build, hover, lifting, lifting_rig as RG, lifting_rope as RP
from .ops_lifting import _ok, _redraw

_ITEMS: dict = {}          # kind -> the enum items (kept alive: Blender holds only pointers to their strings)


def _load(context):
    return lifting.active_load(context.scene)


def _items(kind: str) -> list:
    got = [(p, n, n) for p, n in RG.gear_choices(kind)]
    if kind == "spreader":
        got = [("NONE", "No spreader", "The legs run from the hook to the lift points")] + got
    if not got:
        got = [("NONE", "(none)", "")]
    _ITEMS[kind] = got
    return got


class FRESING_OT_lifting_point_add(bpy.types.Operator):
    """Click on the load where a sling leg is fixed (a padeye's hole, a lug, a casting): a lift point. A click in a
    hole puts the point on the hole's axis, where the shackle's pin goes. Esc: done"""
    bl_idname = "fresing.lifting_point_add"
    bl_label = "Add lift point"
    bl_options = {"REGISTER", "UNDO"}

    part: StringProperty(options={"SKIP_SAVE"}, description="For scripts: the part's object name")
    point: FloatVectorProperty(size=3, options={"SKIP_SAVE"}, description="For scripts: the point (world, m)")

    @classmethod
    def poll(cls, context):
        return _ok(context) and _load(context) is not None

    def execute(self, context):
        ob = bpy.data.objects.get(self.part)
        try:
            RG.add_point(context.scene, _load(context), ob, tuple(self.point))
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        _redraw()
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        ld = _load(context)
        self._mine = {o.name for o in lifting.load_parts(ld)}

        def refuse(ob, *_a):
            return "" if ob.name in self._mine else "not part of the load"

        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, f"{ld.name}: click a lift point (a padeye's hole, a lug, a casting). Esc: done",
                    point=True, refuse=refuse,
                    note=lambda ob, name, *_a: f"Lift point on {name}")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        hover.end(self, context)
        context.window.cursor_modal_restore()

    def modal(self, context, event):
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"FINISHED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None or res[0].name not in self._mine:
            hover.prompt(context, "Not the load: click on one of its parts. Esc: done")
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        try:
            p = RG.add_point(context.scene, _load(context), ob, RG.point_of_click(ob, index, loc, normal))
            hover.prompt(context, f"Lift point {p.name} on {ob.get(build.PROP_NAME, ob.name)}. Click the next one; "
                                  "Esc: done")
        except ValueError as exc:
            hover.prompt(context, f"{exc} Esc: done")
        _redraw()
        return {"RUNNING_MODAL"}


class FRESING_OT_lifting_points_find(bpy.types.Operator):
    """Finds the load's lift points by their parts' names – padeyes, lifting lugs and eyes, a container's top corner
    castings – and puts one on each (in a padeye's hole, on a casting's top)"""
    bl_idname = "fresing.lifting_points_find"
    bl_label = "Find lift points"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _ok(context) and _load(context) is not None

    def execute(self, context):
        n = RG.find_named(context.scene, _load(context))
        if not n:
            self.report({"WARNING"}, "No parts named like a lift point (padeye, lifting lug, corner casting …): use "
                                     "Add lift point and click them")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{n} lift point{'s' if n != 1 else ''} found")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_point_remove(bpy.types.Operator):
    """Removes this lift point (the others are lettered again: A, B, C …)"""
    bl_idname = "fresing.lifting_point_remove"
    bl_label = "Remove lift point"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        ld = _load(context)
        return _ok(context) and ld is not None and ld.rig_state != "HUNG"

    def execute(self, context):
        RG.remove_point(context.scene, _load(context), self.index)
        _redraw()
        return {"FINISHED"}


def _sling_items(self, context):
    return _items("sling")


def _shackle_items(self, context):
    return _items("shackle")


def _spreader_items(self, context):
    return _items("spreader")


class _GearPick:
    bl_options = {"REGISTER", "UNDO"}
    _field = ""

    @classmethod
    def poll(cls, context):
        return _ok(context) and _load(context) is not None

    def execute(self, context):
        ld = _load(context)
        setattr(ld, self._field, "" if self.item == "NONE" else self.item)
        lifting._READ.clear()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_sling(_GearPick, bpy.types.Operator):
    """Picks the sling set the load hangs on: chain (grade 8), wire rope or round slings, 1, 2 or 4 legs, its WLL per
    leg. Your own sling files in 'Lifting equipment' come first. Hang on the hook again after a change"""
    bl_idname = "fresing.lifting_sling"
    bl_label = "Sling set"
    bl_property = "item"
    _field = "sling"
    item: EnumProperty(items=_sling_items, name="Sling set")


class FRESING_OT_lifting_shackle(_GearPick, bpy.types.Operator):
    """Picks the shackle at each lift point (bow shackles 2–150 t). Hang on the hook again after a change"""
    bl_idname = "fresing.lifting_shackle"
    bl_label = "Shackle"
    bl_property = "item"
    _field = "shackle"
    item: EnumProperty(items=_shackle_items, name="Shackle")


class FRESING_OT_lifting_spreader(_GearPick, bpy.types.Operator):
    """Picks a spreader beam or lifting frame between the hook and the load (or none): top legs from the hook to it,
    a leg from each of its bottom padeyes straight down to a lift point"""
    bl_idname = "fresing.lifting_spreader"
    bl_label = "Spreader"
    bl_property = "item"
    _field = "spreader"
    item: EnumProperty(items=_spreader_items, name="Spreader")


class FRESING_OT_lifting_hang(bpy.types.Operator):
    """Hangs the load on the active crane's hook: it comes to rest with its centre of gravity straight under the hook
    and tilts as its lift points make it; each leg's angle and force are worked out and checked (C2–C4). It then
    follows the hook (Hook to here, poses, joint steps, Build)"""
    bl_idname = "fresing.lifting_hang"
    bl_label = "Hang on the hook"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ld = _load(context)
        return _ok(context) and ld is not None and len(ld.points) > 0 and \
            lifting.active_crane(context.scene) is not None

    def execute(self, context):
        scene = context.scene
        try:
            h = RG.hang(scene, lifting.active_crane(scene), _load(context))
        except (ValueError, RuntimeError, lifting.LR.ReachError) as exc:
            lifting.plan(scene).message = str(exc)
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        lifting.plan(scene).message = (f"{_load(context).name} hangs on the hook, tilted {h.tilts[0]:.1f}°"
                                       + (": " + h.notes[0] if h.notes else "."))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_set_down(bpy.types.Operator):
    """Takes the load off the hook where it is now: it stays there (lower the hook onto the ground first); the slings
    and the spreader are taken off"""
    bl_idname = "fresing.lifting_set_down"
    bl_label = "Set down"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ld = _load(context)
        return _ok(context) and ld is not None and ld.rig_state == "HUNG"

    def execute(self, context):
        RG.set_down(context.scene, _load(context))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_rig_remove(bpy.types.Operator):
    """Takes the rigging off the load: its parts stand where they stood before it was hung; the lift points stay"""
    bl_idname = "fresing.lifting_rig_remove"
    bl_label = "Remove rigging"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ld = _load(context)
        return _ok(context) and ld is not None and ld.rig_state != "NONE"

    def execute(self, context):
        RG.remove(context.scene, _load(context))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_lifting_leg_go(bpy.types.Operator):
    """Shows this sling leg: selects it and turns the view to it"""
    bl_idname = "fresing.lifting_leg_go"
    bl_label = "Go to the leg"
    bl_options = {"REGISTER"}

    leg: StringProperty()

    @classmethod
    def poll(cls, context):
        ld = _load(context)
        return _ok(context) and ld is not None and ld.rig_state == "HUNG"

    def execute(self, context):
        ld = _load(context)
        ob = next((r.obj for r in ld.rig_objects if r.obj is not None
                   and r.obj.name == f"{RG.SLING}{ld.name} {self.leg}"), None)
        if ob is None:
            return {"CANCELLED"}
        for o in context.view_layer.objects.selected:
            o.select_set(False)
        was = ob.hide_select
        ob.hide_select = False
        ob.select_set(True)
        context.view_layer.objects.active = ob
        if context.area is not None and context.area.type == "VIEW_3D":
            try:
                bpy.ops.view3d.view_selected()
            except RuntimeError:
                pass
        ob.hide_select = was
        return {"FINISHED"}


class FRESING_OT_lifting_reeve(bpy.types.Operator):
    """Reeves the crane's hoist rope in its falls: from the winch drum over the head's sheaves and down and up through
    the hook block's (8 falls over 4 + 4 sheaves on the AT-100). The drum then winds falls x the hook's travel and the
    line pull is checked (C10). New cranes are reeved when placed"""
    bl_idname = "fresing.lifting_reeve"
    bl_label = "Reeve the rope"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _ok(context) and lifting.active_crane(context.scene) is not None

    def execute(self, context):
        scene = context.scene
        c = lifting.active_crane(scene)
        try:
            r = RP.reeve(scene, c)
        except (ValueError, RuntimeError, KeyError, lifting.LR.ReachError) as exc:
            self.report({"WARNING"}, f"The rope cannot be reeved: {exc}")
            return {"CANCELLED"}
        msg = (f"{c.name}: rope reeved in {r['falls']} falls over {r['head']} + {r['block']} sheaves, dead end on "
               f"the {r['dead_end']}")
        if r["guessed"]:
            msg += " (sheave and drum sizes guessed: the crane's file has none)"
        lifting.plan(scene).message = msg + "."
        self.report({"INFO"}, msg)
        _redraw()
        return {"FINISHED"}


CLASSES = (FRESING_OT_lifting_point_add, FRESING_OT_lifting_points_find, FRESING_OT_lifting_point_remove,
           FRESING_OT_lifting_sling, FRESING_OT_lifting_shackle, FRESING_OT_lifting_spreader,
           FRESING_OT_lifting_hang, FRESING_OT_lifting_set_down, FRESING_OT_lifting_rig_remove,
           FRESING_OT_lifting_leg_go, FRESING_OT_lifting_reeve)
