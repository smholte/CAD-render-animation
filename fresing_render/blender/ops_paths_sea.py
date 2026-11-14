"""Operators for a cable into the sea and things on the cable (4 Motion > Cables and paths > Into the sea,
task 0081). The work is in paths_sea.py and paths_riders.py."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty

from . import paths, paths_riders, paths_sea
from .ops_flex import _say, selected_parts
from .ops_paths import _NeedsItem, _NeedsOn, _item, _refuse, _tell


class _NeedsSea(_NeedsOn):
    @classmethod
    def poll(cls, context):
        return super().poll(context) and _item(context).b_kind == "SEA"


class FRESING_OT_cable_sea_add(_NeedsOn, bpy.types.Operator):
    """Lets the chosen cable hang from its last contact (horn, chute or sheave) into the sea: it hangs in a curve
    down to the seabed and lies on the seabed behind it. Then set the layback or the bottom tension below"""

    bl_idname = "fresing.cable_sea_add"
    bl_label = "Into the sea"

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        try:
            notes = paths_sea.add_sea_end(scene, item)
        except paths.PathError as exc:
            return _refuse(context, self, exc)
        item = _item(context)
        _tell(context, self, notes + [p for p in (item.problem,) if p])
        if not notes and not item.problem:
            n = paths_sea.numbers(scene, item)
            _say(context, self, f"'{paths.label(item)}' hangs into the sea: it touches the seabed "
                 f"{n.get('layback', 0.0):.1f} m behind '{_hang_name(item)}'")
        return {"FINISHED"}


class FRESING_OT_cable_sea_remove(_NeedsSea, bpy.types.Operator):
    """The cable no longer goes into the sea: its end is where it was before (as drawn in the CAD file)"""

    bl_idname = "fresing.cable_sea_remove"
    bl_label = "Not into the sea"

    def execute(self, context):
        paths_sea.remove_sea_end(context.scene, _item(context))
        _say(context, self, f"'{paths.label(_item(context))}' ends as drawn in the CAD file again")
        return {"FINISHED"}


class FRESING_OT_cable_sea_reset(_NeedsSea, bpy.types.Operator):
    """Sets the touch-down again in the pose shown: from the layback or the bottom tension you typed. Use it after
    you paid out cable or moved the vessel's machines by hand and want the numbers to hold here"""

    bl_idname = "fresing.cable_sea_reset"
    bl_label = "Set the touch-down here"

    def execute(self, context):
        paths_sea.changed(context.scene, _item(context))
        _say(context, self, "Touch-down set again in the pose shown")
        return {"FINISHED"}


def _hang_name(item) -> str:
    return next((c.name for c in reversed(item.contacts) if c.kind in paths.SHAPING), "its last contact")


class FRESING_OT_cable_rider_add(_NeedsOn, bpy.types.Operator):
    """Puts the selected parts (or a whole assembly, such as a CPS set or a bend restrictor) on the chosen cable:
    they ride along with it over the rollers and down into the sea. Select them in the 3D view first, then set
    where they sit on the cable"""

    bl_idname = "fresing.cable_rider_add"
    bl_label = "Put on the cable"

    names: StringProperty(default="", options={"SKIP_SAVE"},
                          description="Names of the objects, separated by '|' (instead of the selection)")
    where: EnumProperty(name="Place", default="END", items=[("END", "From the cable's end", ""),
                                                            ("MARK", "At a payout mark", "")],
                        options={"SKIP_SAVE"})
    at: FloatProperty(name="Metres", default=5.0, options={"SKIP_SAVE"})

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        if self.names:
            obs = [scene.objects.get(n) for n in self.names.split("|")]
            obs = [o for o in obs if o is not None]
        else:
            obs = list(context.selected_objects) or selected_parts(context)
        try:
            r = paths_riders.add(scene, item, obs, self.where, self.at)
        except paths_riders.RiderError as exc:
            _say(context, self, str(exc), "ERROR")
            return {"CANCELLED"}
        _say(context, self, f"'{r.name}' rides on '{paths.label(item)}': {paths_riders.describe(scene, item, r)}")
        return {"FINISHED"}


class FRESING_OT_cable_rider_remove(_NeedsItem, bpy.types.Operator):
    """Takes the chosen thing off the cable: its parts show where the CAD file has them again"""

    bl_idname = "fresing.cable_rider_remove"
    bl_label = "Take off the cable"

    @classmethod
    def poll(cls, context):
        it = _item(context) if super().poll(context) else None
        return it is not None and 0 <= it.riders_index < len(it.riders)

    def execute(self, context):
        item = _item(context)
        name = item.riders[item.riders_index].name
        paths_riders.remove(context.scene, item, item.riders_index)
        _say(context, self, f"'{name}' is off the cable: its parts are where the CAD file has them")
        return {"FINISHED"}


CLASSES = (FRESING_OT_cable_sea_add, FRESING_OT_cable_sea_remove, FRESING_OT_cable_sea_reset,
           FRESING_OT_cable_rider_add, FRESING_OT_cable_rider_remove)
