"""Operators for phase 2: model update report, joints, poses, exploded views,
visibility sets, saved scenes, animation and the render queue."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from mathutils import Vector

from ..core.words import plural
from . import animation, build, files, joints, logic, props, queue, states

# =============================================================================
# helpers
# =============================================================================


def _redraw(context) -> None:
    for area in getattr(context.screen, "areas", []) if context.screen else []:
        area.tag_redraw()


def selected_movers(context) -> list:
    """Selected subassemblies/parts, reduced to the top-most ones (a selected subassembly
    selects all its parts too)."""
    sel = [ob for ob in context.selected_objects if ob.get(build.PROP_KIND) in build.MODEL_KINDS]
    names = {ob.name for ob in sel}
    out = []
    for ob in sel:
        p = build.logical_parent(ob)
        inside = False
        while p is not None:
            if p.name in names:
                inside = True
                break
            p = build.logical_parent(p)
        if not inside:
            out.append(ob)
    return out


SEP = "\x1f"          # between object names passed to the pick tool (names may contain commas)


def _active_joint(context):
    s = context.scene.fresing
    if 0 <= s.joints_index < len(s.joints):
        return s.joints[s.joints_index]
    return None


def _valid_joint(context) -> bool:
    j = _active_joint(context)
    return j is not None and joints.is_valid(j)


def _target_subassembly(context):
    """Active row of the structure list, else the active selection's subassembly, else the model."""
    s = context.scene.fresing
    ob = context.active_object
    if ob is not None and ob.get(build.PROP_KIND) in build.MODEL_KINDS and ob.select_get():
        if ob.get(build.PROP_KIND) == "part" and s.pick_mode == "SUBASSEMBLY":
            ob = logic.subassembly_for_pick(ob)
        return ob
    if 0 <= s.tree_index < len(s.tree) and s.tree[s.tree_index].obj is not None:
        return s.tree[s.tree_index].obj
    roots = build.model_roots(context.scene)
    return logic.top_level(roots[0]) if roots else None


def _has_model(context) -> bool:
    return context.scene.fresing.model_count > 0


def _open_path(path: str) -> None:
    files.open_path(path)


# =============================================================================
# model update report
# =============================================================================


class FRESING_OT_report_select_new(bpy.types.Operator):
    """Select the parts that are new in this revision"""

    bl_idname = "fresing.report_select_new"
    bl_label = "Select new parts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        uids = {line.uid for line in context.scene.fresing.report_new}
        for ob in context.selected_objects:
            ob.select_set(False)
        n = 0
        for ob in build.iter_parts(context.scene):
            if ob.get(build.PROP_UID) in uids and ob.visible_get():
                ob.select_set(True)
                n += 1
        self.report({"INFO"}, f"{n} new parts selected")
        return {"FINISHED"}


class FRESING_OT_report_clear(bpy.types.Operator):
    """Closes this model update report. The model and your work do not change"""

    bl_idname = "fresing.report_clear"
    bl_label = "Close report"

    def execute(self, context):
        s = context.scene.fresing
        s.report_new.clear()
        s.report_missing.clear()
        s.report_notes.clear()
        s.report_title = ""
        return {"FINISHED"}


# =============================================================================
# joints
# =============================================================================

AXIS_ITEMS = [("PICK", "Pick on the model", "Click a hole, shaft or flat face"),
              ("X", "X axis", ""), ("Y", "Y axis", ""), ("Z", "Z axis (up)", "")]
KIND_ITEMS = [("ROTATE", "Rotate", ""), ("SLIDE", "Slide", "")]


def _centre_of(objs) -> Vector:
    tree = logic.Tree()
    parts = []
    for ob in objs:
        if ob.get(build.PROP_KIND) == "part":
            parts.append(ob)
        else:
            parts += [d for d in tree.descendants(ob) if d.get(build.PROP_KIND) == "part"]
    mn, mx = build.world_bounds(parts)
    return Vector(((mn + mx) / 2).tolist())


def _axis_vector(key: str) -> Vector:
    return Vector({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[key])


class FRESING_OT_joint_add(bpy.types.Operator):
    """Make the selected subassemblies move: rotate about or slide along an axis"""

    bl_idname = "fresing.joint_add"
    bl_label = "Add joint"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(name="Type", items=KIND_ITEMS, default="ROTATE")
    axis: EnumProperty(name="Axis", items=AXIS_ITEMS, default="PICK")
    origin: EnumProperty(name="Through", default="CENTER", items=[
        ("CENTER", "Centre of the moving parts", ""), ("CURSOR", "3D cursor", "")])

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def invoke(self, context, event):
        movers = selected_movers(context)
        if not movers:
            self.report({"WARNING"}, "First click the subassembly (or subassemblies) that should move")
            return {"CANCELLED"}
        _below, reason = joints.stack_info(context.scene, movers)
        if reason:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}
        if self.axis == "PICK":
            names = SEP.join(ob.name for ob in movers)
            bpy.ops.fresing.joint_pick_axis("INVOKE_DEFAULT", mode="NEW", kind=self.kind, movers=names)
            return {"CANCELLED"}             # the pick tool finishes the job (and the undo step)
        return self.execute(context)

    def execute(self, context):
        movers = selected_movers(context)
        if not movers:
            self.report({"WARNING"}, "First click the subassembly that should move")
            return {"CANCELLED"}
        axis = "Z" if self.axis == "PICK" else self.axis
        origin = context.scene.cursor.location.copy() if self.origin == "CURSOR" else _centre_of(movers)
        try:
            j = joints.create(context.scene, self.kind, movers, origin, _axis_vector(axis))
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Joint '{j.name}' added")
        return {"FINISHED"}


def _inside(r, event) -> bool:
    return r.x <= event.mouse_x < r.x + r.width and r.y <= event.mouse_y < r.y + r.height


def over_panel(context, event) -> bool:
    """True when the mouse is over the side panel, header or toolbar (they overlap the 3D view)."""
    area = context.area
    if area is None:
        return False
    return any(r.type in ("UI", "HEADER", "TOOLS", "TOOL_HEADER", "ASSET_SHELF", "ASSET_SHELF_HEADER")
               and r.width > 1 and r.height > 1 and _inside(r, event) for r in area.regions)


def _raycast(context, event):
    """Ray-cast from the mouse into the scene. Returns (object, polygon, location, normal) or None."""
    from bpy_extras import view3d_utils
    area = context.area
    if area is None or area.type != "VIEW_3D":
        return None
    region = next((r for r in area.regions if r.type == "WINDOW" and _inside(r, event)), None)
    if region is None:
        return None
    rv3d = region.data
    coord = (event.mouse_x - region.x, event.mouse_y - region.y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    depsgraph = context.evaluated_depsgraph_get()
    hit, loc, normal, index, ob, _matrix = context.scene.ray_cast(depsgraph, origin, direction)
    if not hit or ob is None:
        return None
    ob = getattr(ob, "original", ob)
    return ob, index, loc, normal


class FRESING_OT_joint_pick_axis(bpy.types.Operator):
    """Click a hole, shaft or face on the model to set the joint axis"""

    bl_idname = "fresing.joint_pick_axis"
    bl_label = "Pick joint axis"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("NEW", "New", ""), ("EDIT", "Edit", "")], default="EDIT", options={"SKIP_SAVE"})
    kind: EnumProperty(items=KIND_ITEMS, default="ROTATE", options={"SKIP_SAVE"})
    movers: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if properties.mode == "EDIT":
            return ("Gives this joint a new axis: click a hole or shaft (axis through its centre) or a flat face "
                    "(axis at right angles to it). Esc cancels")
        if properties.kind == "SLIDE":
            return ("Adds a joint that slides the selected subassembly. Then click a hole, shaft or flat face that "
                    "points the way it slides. Esc cancels")
        return ("Adds a joint that turns the selected subassembly. Then click its pivot on the model: a hole or "
                "shaft, or a flat face. Esc cancels")

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        if self.mode == "EDIT" and not _valid_joint(context):
            self.report({"WARNING"}, "This joint is broken (its arrow was deleted): remove it and add it again")
            return {"CANCELLED"}
        if self.mode == "NEW" and not self.movers:
            movers = selected_movers(context)
            if not movers:
                self.report({"WARNING"}, "First click the subassembly (or subassemblies) that should move")
                return {"CANCELLED"}
            self.movers = SEP.join(ob.name for ob in movers)
        if self.mode == "NEW":
            movers = [bpy.data.objects.get(n) for n in self.movers.split(SEP) if n]
            _below, reason = joints.stack_info(context.scene, [m for m in movers if m])
            if reason:                               # say so before the click on the pivot, not after
                self.report({"WARNING"}, reason)
                return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        context.workspace.status_text_set(
            "Click a hole or shaft (axis through its centre) or a flat face (axis at right angles to it).  "
            "Esc / right-click: cancel.  Middle mouse / scroll: move the view")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = _raycast(context, event)
        if res is None or res[0].get(build.PROP_KIND) != "part":
            context.workspace.status_text_set("Missed the model (or hit the floor): click a part. Esc: cancel")
            return {"RUNNING_MODAL"}           # keep waiting
        ob, index, loc, normal = res
        origin, direction, desc = joints.axis_from_hit(ob, index, loc, normal)
        self._end(context)
        scene = context.scene
        try:
            if self.mode == "NEW":
                movers = [bpy.data.objects.get(n) for n in self.movers.split(SEP) if n]
                j = joints.create(scene, self.kind, [m for m in movers if m], origin, direction, ref=ob)
                msg = f"Joint '{j.name}' added on a {desc}"
            else:
                j = _active_joint(context)
                joints.set_axis(scene, j, origin, direction, ref=ob)
                msg = f"Axis of '{j.name}' set on a {desc}"
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        scene.fresing.last_message = msg
        self.report({"INFO"}, msg)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_joint_remove(bpy.types.Operator):
    """Remove the joint. Its parts go back to the joint it rode on, or to their CAD position;
    joints riding on it move down"""

    bl_idname = "fresing.joint_remove"
    bl_label = "Remove joint"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_joint(context) is not None

    def execute(self, context):
        scene = context.scene
        j = _active_joint(context)
        name = j.name
        below = joints.rides_on(scene, j)
        below = below.name if below is not None else ""      # names only: removing shifts the list items
        above = [r.name for r in joints.riders(scene, j)]
        freed = joints.remove(scene, j)
        msgs = []
        if above:
            onto = f"'{below}'" if below else "what it sat on"
            listed = ", ".join("'" + a + "'" for a in above)
            msgs.append(f"{listed} now ride{'s' if len(above) == 1 else ''} on {onto}")
        if freed:
            listed = ", ".join("'" + a + "'" for a in freed)
            msgs.append(f"{listed} followed it and now move{'s' if len(freed) == 1 else ''} by "
                        f"{'itself' if len(freed) == 1 else 'themselves'}")
        if msgs:
            msg = f"Joint '{name}' removed; " + "; ".join(msgs)
            scene.fresing.last_message = msg
            self.report({"INFO"}, msg)
        return {"FINISHED"}


class FRESING_OT_joint_swap(bpy.types.Operator):
    """Swap the order of this joint and the one it rides on: the other one then rides on this one.
    With two slides nothing changes; with a rotation it does (turn then slide, or slide then turn)"""

    bl_idname = "fresing.joint_swap"
    bl_label = "Swap order"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _valid_joint(context) and joints.rides_on(context.scene, _active_joint(context)) is not None

    @classmethod
    def description(cls, context, properties):
        j = _active_joint(context)
        reason = joints.swap_check(context.scene, j) if j is not None and joints.is_valid(j) else ""
        return reason or " ".join(cls.__doc__.split())

    def execute(self, context):
        scene = context.scene
        j = _active_joint(context)
        name, below = j.name, joints.rides_on(scene, j).name
        try:
            joints.swap(scene, j)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        msg = f"'{below}' now rides on '{name}'"
        scene.fresing.last_message = msg
        scene.fresing.bounds_valid = False
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class FRESING_OT_joint_flip(bpy.types.Operator):
    """Reverse the direction of the joint (positive values turn / slide the other way)"""

    bl_idname = "fresing.joint_flip"
    bl_label = "Flip direction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _valid_joint(context)

    def execute(self, context):
        joints.flip(context.scene, _active_joint(context))
        return {"FINISHED"}


class FRESING_OT_joint_axis_preset(bpy.types.Operator):
    """Point the joint axis along X, Y or Z (keeps the axis point)"""

    bl_idname = "fresing.joint_axis_preset"
    bl_label = "Axis direction"
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")], default="Z")

    @classmethod
    def poll(cls, context):
        return _valid_joint(context)

    def execute(self, context):
        j = _active_joint(context)
        o, _d = joints.axis_world(j)
        joints.set_axis(context.scene, j, o, _axis_vector(self.axis), ref=None)
        return {"FINISHED"}


class FRESING_OT_joint_kind(bpy.types.Operator):
    """Switch between rotating and sliding"""

    bl_idname = "fresing.joint_kind"
    bl_label = "Joint type"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(items=KIND_ITEMS)

    @classmethod
    def description(cls, context, properties):
        if properties.kind == "SLIDE":
            return "Makes this joint slide along its axis (the arrow). It goes back to its CAD position first"
        return "Makes this joint turn about its axis (the arrow). It goes back to its CAD position first"

    @classmethod
    def poll(cls, context):
        return _valid_joint(context)

    def execute(self, context):
        joints.set_kind(context.scene, _active_joint(context), self.kind)
        return {"FINISHED"}


class FRESING_OT_joint_members(bpy.types.Operator):
    """Add the selected subassemblies to the joint, or take them out"""

    bl_idname = "fresing.joint_members"
    bl_label = "Moving parts"
    bl_options = {"REGISTER", "UNDO"}

    action: EnumProperty(items=[("ADD", "Add selected", ""), ("REMOVE", "Remove selected", ""),
                                ("SELECT", "Select", "")], default="ADD")

    @classmethod
    def description(cls, context, properties):
        return {
            "ADD": "Adds the selected parts or subassemblies to what this joint moves. Click them in the view first",
            "REMOVE": "Takes the selected parts or subassemblies out of what this joint moves; they go back to "
                      "their place",
            "SELECT": "Selects everything this joint moves, so you can see it in the view",
        }.get(properties.action, "")

    @classmethod
    def poll(cls, context):
        return _valid_joint(context)

    def execute(self, context):
        j = _active_joint(context)
        scene = context.scene
        if self.action == "SELECT":
            for ob in context.selected_objects:
                ob.select_set(False)
            tree = logic.Tree(scene)
            for m in joints.moved_objects(scene, j):          # also what rides on it in a stack
                for d in [m] + tree.descendants(m):
                    if d.visible_get() and not d.hide_select:
                        d.select_set(True)
            return {"FINISHED"}
        movers = selected_movers(context)
        try:
            if self.action == "ADD":
                n = joints.add_members(scene, j, movers)
            else:
                # parts that ride on this joint through a joint on top are removed there, not here
                via = [(ob, joints.joint_of_object(scene, ob)) for ob in movers if ob not in joints.members(j)]
                via = [(ob, o) for ob, o in via if o is not None and o.name in
                       {r.name for r in joints.all_riders(scene, j)}]
                n = joints.remove_members(scene, j, movers)
                if n == 0 and via:
                    ob, o = via[0]
                    msg = (f"'{ob.get(build.PROP_NAME, ob.name)}' moves with '{o.name}' (on top of this joint): "
                           f"select '{o.name}' in the list and remove it there")
                    scene.fresing.last_message = msg
                    self.report({"WARNING"}, msg)
                    return {"CANCELLED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        done = "added" if self.action == "ADD" else "removed"
        self.report({"INFO"}, f"{plural(n, 'subassembly', 'subassemblies')} {done}")
        return {"FINISHED"}


class FRESING_OT_joint_value(bpy.types.Operator):
    """Set the joint to a value (0 = CAD position)"""

    bl_idname = "fresing.joint_value"
    bl_label = "Joint to value"
    bl_options = {"REGISTER", "UNDO"}

    target: EnumProperty(items=[("ZERO", "0", ""), ("MIN", "Min", ""), ("MAX", "Max", "")], default="ZERO")

    @classmethod
    def poll(cls, context):
        return _valid_joint(context) and not _active_joint(context).follows

    @classmethod
    def description(cls, context, properties):
        return {
            "ZERO": "Puts the joint back at 0: the position it has in the CAD file",
            "MIN": "Moves the joint to its lowest limit (switch Limits on below to set it)",
            "MAX": "Moves the joint to its highest limit (switch Limits on below to set it)",
        }.get(properties.target, "")

    def execute(self, context):
        j = _active_joint(context)
        lo, hi = joints.limits(j)
        joints.set_value(j, {"ZERO": 0.0, "MIN": lo, "MAX": hi}[self.target])
        context.scene.fresing.bounds_valid = False
        return {"FINISHED"}


class FRESING_OT_joint_follow(bpy.types.Operator):
    """Choose whether this joint moves by itself or follows another joint"""

    bl_idname = "fresing.joint_follow"
    bl_label = "How the joint moves"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("FREE", "By itself", ""), ("FOLLOW", "Follows a joint", "")], default="FREE")

    @classmethod
    def poll(cls, context):
        return _valid_joint(context)

    @classmethod
    def description(cls, context, properties):
        if properties.mode == "FOLLOW":
            return ("Makes this joint follow another joint: when that one moves, this one moves with it (gears, "
                    "telescope sections, gripper jaws, spindles, wheels). Then pick the joint and the ratio below")
        return ("This joint moves by itself: by hand, in poses and in animation steps. It stops following and "
                "stays where it is")

    def execute(self, context):
        scene = context.scene
        j = _active_joint(context)
        if self.mode == "FREE":
            if j.follows:
                joints.set_follows(scene, j, "")
                j["_follow_error"] = ""
            return {"FINISHED"}
        if j.follows:
            return {"FINISHED"}
        name = j.name
        ok = [x.name for x in scene.fresing.joints if x.name != name and not joints.follow_check(scene, j, x.name)]
        if not ok:
            self.report({"WARNING"}, "Add the joint it should follow first (in this list)")
            return {"CANCELLED"}
        below = joints.rides_on(scene, j)            # telescope: a section follows the one it rides on
        free = [n for n in ok if not joints.find(scene, n).follows]
        pick = below.name if below is not None and below.name in ok else (free or ok)[0]
        joints.set_follows(scene, joints.find(scene, name), pick)
        joints.find(scene, name)["_follow_error"] = ""
        self.report({"INFO"}, f"'{name}' follows '{pick}'")
        return {"FINISHED"}


# =============================================================================
# poses & exploded views
# =============================================================================


class FRESING_OT_pose_save(bpy.types.Operator):
    """Save the current joint positions and moved subassemblies as a pose"""

    bl_idname = "fresing.pose_save"
    bl_label = "Save pose"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        self.name = states.unique_pose_name(context.scene)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.name.strip() or states.unique_pose_name(context.scene)
        states.save_pose(context.scene, name)
        self.report({"INFO"}, f"Pose '{name}' saved")
        return {"FINISHED"}


class FRESING_OT_pose_apply(bpy.types.Operator):
    """Move everything to this pose"""

    bl_idname = "fresing.pose_apply"
    bl_label = "Use pose"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        if not states.apply_pose(context.scene, self.name):
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_pose_update(bpy.types.Operator):
    """Overwrite the selected pose with the current positions"""

    bl_idname = "fresing.pose_update"
    bl_label = "Update pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.poses_index < len(s.poses)):
            return {"CANCELLED"}
        states.capture_pose(context.scene, s.poses[s.poses_index])
        return {"FINISHED"}


class FRESING_OT_pose_remove(bpy.types.Operator):
    """Deletes the selected pose. The model does not move"""

    bl_idname = "fresing.pose_remove"
    bl_label = "Remove pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.poses_index < len(s.poses):
            s.poses.remove(s.poses_index)
            s.poses_index = max(0, s.poses_index - 1)
        return {"FINISHED"}


class FRESING_OT_pose_reset(bpy.types.Operator):
    """Put every joint and subassembly back where the CAD file has it"""

    bl_idname = "fresing.pose_reset"
    bl_label = "Back to CAD position"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        states.reset_pose(context.scene)
        return {"FINISHED"}


class FRESING_OT_explode(bpy.types.Operator):
    """Move the pieces of the selected subassembly apart (save it as a pose to keep it)"""

    bl_idname = "fresing.explode"
    bl_label = "Explode"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        s = context.scene.fresing
        target = _target_subassembly(context)
        if target is None:
            return {"CANCELLED"}
        n = states.explode(context.scene, target, s.explode_factor, s.explode_direction, s.explode_level)
        if n == 0:
            self.report({"WARNING"}, "Nothing to move apart: pick a subassembly with several pieces inside")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{plural(n, 'piece')} of {target.get(build.PROP_NAME, target.name)} moved apart")
        return {"FINISHED"}


# =============================================================================
# visibility sets
# =============================================================================


class FRESING_OT_vis_save(bpy.types.Operator):
    """Save which parts are hidden now as a visibility set"""

    bl_idname = "fresing.vis_save"
    bl_label = "Save visibility set"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        self.name = states.unique_visibility_name(context.scene)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.name.strip() or states.unique_visibility_name(context.scene)
        states.save_visibility(context.scene, name)
        return {"FINISHED"}


class FRESING_OT_vis_apply(bpy.types.Operator):
    """Show and hide parts as saved in this set"""

    bl_idname = "fresing.vis_apply"
    bl_label = "Use visibility set"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        return {"FINISHED"} if states.apply_visibility(context.scene, self.name) else {"CANCELLED"}


class FRESING_OT_vis_update(bpy.types.Operator):
    """Overwrite the selected visibility set with what is hidden now"""

    bl_idname = "fresing.vis_update"
    bl_label = "Update visibility set"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.visibility_index < len(s.visibility_sets):
            states.capture_visibility(context.scene, s.visibility_sets[s.visibility_index])
        return {"FINISHED"}


class FRESING_OT_vis_remove(bpy.types.Operator):
    """Delete the selected visibility set. What is hidden now stays hidden"""

    bl_idname = "fresing.vis_remove"
    bl_label = "Remove visibility set"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.visibility_index < len(s.visibility_sets):
            s.visibility_sets.remove(s.visibility_index)
            s.visibility_index = max(0, s.visibility_index - 1)
        return {"FINISHED"}


# =============================================================================
# saved scenes
# =============================================================================


class FRESING_OT_shot_save(bpy.types.Operator):
    """Save colours, pose, visibility, camera, background and image size together as a scene"""

    bl_idname = "fresing.shot_save"
    bl_label = "Save scene"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="")
    scheme: EnumProperty(name="Colours", items=props._scheme_choices)
    pose: EnumProperty(name="Pose", items=props._pose_choices)
    visibility: EnumProperty(name="Visibility", items=props._vis_choices)

    def invoke(self, context, event):
        self.name = states.unique_shot_name(context.scene, context.scene.camera.name if context.scene.camera
                                            else "Scene")
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "scheme")
        layout.prop(self, "pose")
        layout.prop(self, "visibility")
        cam = context.scene.camera
        layout.label(text=f"Camera: {cam.name if cam else 'none'} · background and image size: as now")

    def execute(self, context):
        scene = context.scene
        if scene.camera is None:
            self.report({"WARNING"}, "Add a camera first")
            return {"CANCELLED"}
        name = self.name.strip() or states.unique_shot_name(scene)
        keep = lambda v: "" if v in ("", "__keep__") else v   # noqa: E731
        states.save_shot(scene, name, keep(self.scheme), keep(self.pose), keep(self.visibility))
        self.report({"INFO"}, f"Scene '{name}' saved")
        return {"FINISHED"}


class FRESING_OT_shot_apply(bpy.types.Operator):
    """Switch to this scene: colours, pose, visibility, camera, background and image size"""

    bl_idname = "fresing.shot_apply"
    bl_label = "Use scene"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        warnings = states.apply_shot(context.scene, self.name)
        for w in warnings:
            self.report({"WARNING"}, w)
        return {"FINISHED"}


class FRESING_OT_shot_update(bpy.types.Operator):
    """Overwrite the selected scene with what is shown now (keeps its choice of pose/colours/visibility)"""

    bl_idname = "fresing.shot_update"
    bl_label = "Update scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.shots_index < len(s.shots)):
            return {"CANCELLED"}
        shot = s.shots[s.shots_index]
        states.save_shot(context.scene, shot.name, shot.scheme, shot.pose, shot.visibility)
        return {"FINISHED"}


class FRESING_OT_shot_remove(bpy.types.Operator):
    """Deletes the selected saved scene. The model and the cameras do not change"""

    bl_idname = "fresing.shot_remove"
    bl_label = "Remove scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.shots_index < len(s.shots):
            s.shots.remove(s.shots_index)
            s.shots_index = max(0, s.shots_index - 1)
        return {"FINISHED"}


# =============================================================================
# animation
# =============================================================================


def _active_anim(context):
    return animation.active(context.scene)


def _active_block(context):
    a = _active_anim(context)
    if a is not None and 0 <= a.blocks_index < len(a.blocks):
        return a.blocks[a.blocks_index]
    return None


class FRESING_OT_anim_add(bpy.types.Operator):
    """Adds a new, empty animation. Then add its steps below with the + next to the steps"""

    bl_idname = "fresing.anim_add"
    bl_label = "New animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        name = animation.unique_name(context.scene)     # before adding: the new item is called "Animation"
        a = s.animations.add()
        a.name = name
        if s.active_shot and s.active_shot in s.shots:
            a.start_shot = s.active_shot
        s.animations_index = len(s.animations) - 1
        return {"FINISHED"}


class FRESING_OT_anim_remove(bpy.types.Operator):
    """Deletes the selected animation and its steps. Joints, poses and scenes stay"""

    bl_idname = "fresing.anim_remove"
    bl_label = "Remove animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        a = _active_anim(context)
        if a is None:
            return {"CANCELLED"}
        if s.anim_baked == a.name:
            animation.clear_keys(context.scene)
        s.animations.remove(s.animations_index)
        s.animations_index = max(0, s.animations_index - 1)
        return {"FINISHED"}


class FRESING_OT_block_add(bpy.types.Operator):
    """Adds a step to the animation; it starts when the last step ends. Pick the kind of step in the list"""

    bl_idname = "fresing.block_add"
    bl_label = "Add step"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(items=[(k, {"SHOW": "Show subassembly", "HIDE": "Hide subassembly"}.get(k, label), desc,
                               icon, n) for k, label, desc, icon, n in props.BLOCK_KINDS])

    def execute(self, context):
        a = _active_anim(context)
        s = context.scene.fresing
        if a is None:
            bpy.ops.fresing.anim_add()
            a = _active_anim(context)
        prev_end = max((animation.block_end(b) for b in a.blocks), default=0.0)
        b = a.blocks.add()
        b.kind = self.kind
        b.start = round(prev_end, 2)
        b.duration = 0.0 if self.kind in ("SHOW", "HIDE") else 2.0
        if self.kind == "MOTOR":
            # the selected joint when it is a motor, else the first motor, else the selected joint
            j = _active_joint(context)
            if j is None or not joints.is_motor(j) or j.follows:
                motor = next((x for x in s.joints if joints.is_motor(x) and not x.follows), None)
                j = motor or (j if j is not None and not j.follows else None)
            if j is not None:
                b.joint = j.name
            b.duration = 5.0
            b.easing = "SMOOTH"
        elif self.kind == "JOINT":
            j = _active_joint(context)
            if j is not None:
                b.joint = j.name
                if j.kind == "ROTATE":
                    b.to_angle = joints.limits(j)[1] if j.use_limits else 0.785398
                else:
                    b.to_dist = joints.limits(j)[1] if j.use_limits else 0.5
        elif self.kind == "CYLINDER":
            from . import cylinders
            if 0 <= s.cylinders_index < len(s.cylinders):
                c = s.cylinders[s.cylinders_index]
                b.cylinder = c.name
                try:
                    now = cylinders.stroke_now(context.scene, c)
                except Exception:
                    now = 0.0
                b.from_stroke = min(max(now, 0.0), c.full_stroke)
                b.to_stroke = c.full_stroke if now < c.full_stroke / 2 else 0.0
        elif self.kind == "POSE" and len(s.poses):
            b.pose = s.poses[min(s.poses_index, len(s.poses) - 1)].name
        elif self.kind == "CAMERA":
            b.camera = context.scene.camera if context.scene.camera and not context.scene.camera.get(
                "fr_anim_camera") else None
        elif self.kind in ("SHOW", "HIDE"):
            ob = _target_subassembly(context)
            if ob is not None:
                b.target_uid = ob.get(build.PROP_UID, ob.name)
                b.target_name = ob.get(build.PROP_NAME, ob.name)
        a.blocks_index = len(a.blocks) - 1
        return {"FINISHED"}


class FRESING_OT_block_remove(bpy.types.Operator):
    """Deletes the selected step from this animation"""

    bl_idname = "fresing.block_remove"
    bl_label = "Remove step"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        a = _active_anim(context)
        if a is None or not (0 <= a.blocks_index < len(a.blocks)):
            return {"CANCELLED"}
        a.blocks.remove(a.blocks_index)
        a.blocks_index = max(0, a.blocks_index - 1)
        return {"FINISHED"}


class FRESING_OT_block_move(bpy.types.Operator):
    bl_idname = "fresing.block_move"
    bl_label = "Move step"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    @classmethod
    def description(cls, context, properties):
        way = "up" if properties.direction == "UP" else "down"
        return f"Moves the selected step {way} the list. When it plays is set by its Start time"

    def execute(self, context):
        a = _active_anim(context)
        if a is None:
            return {"CANCELLED"}
        i = a.blocks_index
        k = i - 1 if self.direction == "UP" else i + 1
        if 0 <= k < len(a.blocks):
            a.blocks.move(i, k)
            a.blocks_index = k
        return {"FINISHED"}


class FRESING_OT_block_duplicate(bpy.types.Operator):
    """Copy the step; the copy starts when the original ends"""

    bl_idname = "fresing.block_duplicate"
    bl_label = "Duplicate step"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        a = _active_anim(context)
        b = _active_block(context)
        if b is None:
            return {"CANCELLED"}
        nb = a.blocks.add()
        for key in b.bl_rna.properties.keys():
            if key in ("rna_type",):
                continue
            try:
                setattr(nb, key, getattr(b, key))
            except (AttributeError, TypeError):
                pass
        nb.start = animation.block_end(b)
        a.blocks_index = len(a.blocks) - 1
        return {"FINISHED"}


class FRESING_OT_block_target(bpy.types.Operator):
    """Use the selected subassembly for this step"""

    bl_idname = "fresing.block_target"
    bl_label = "Use selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        b = _active_block(context)
        ob = _target_subassembly(context)
        if b is None or ob is None:
            return {"CANCELLED"}
        b.target_uid = ob.get(build.PROP_UID, ob.name)
        b.target_name = ob.get(build.PROP_NAME, ob.name)
        return {"FINISHED"}


class FRESING_OT_anim_build(bpy.types.Operator):
    """Turn the steps into keyframes so the animation plays in the viewport (Space) and renders"""

    bl_idname = "fresing.anim_build"
    bl_label = "Build animation"
    bl_options = {"REGISTER", "UNDO"}

    play: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _active_anim(context) is not None

    def execute(self, context):
        a = _active_anim(context)
        info = animation.bake(context.scene, a)
        for w in info["warnings"]:
            self.report({"WARNING"}, w)
        context.scene.fresing.last_message = f"'{a.name}': {info['seconds']:.1f} s, {info['frames']} frames"
        if self.play and context.screen is not None and not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return {"FINISHED"}


class FRESING_OT_anim_fit_camera(bpy.types.Operator):
    """Zoom the start camera out so the model stays in view during the whole animation"""

    bl_idname = "fresing.anim_fit_camera"
    bl_label = "Fit camera to the whole motion"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_anim(context) is not None

    def execute(self, context):
        from . import cameras
        scene = context.scene
        a = _active_anim(context)
        info = animation.bake(scene, a)
        cam = bpy.data.objects.get(scene.fresing.anim_restore_camera)
        if a.start_shot and a.start_shot in scene.fresing.shots and scene.fresing.shots[a.start_shot].camera:
            cam = scene.fresing.shots[a.start_shot].camera
        if cam is None or cam.type != "CAMERA":
            animation.clear_keys(scene)
            self.report({"WARNING"}, "No start camera: pick a camera or a start scene first")
            return {"CANCELLED"}
        n = info["frames"]
        frames = sorted({1, n} | {1 + round(k * (n - 1) / 15) for k in range(16)})
        pts = cameras.points_over_frames(scene, frames)
        animation.clear_keys(scene)
        cameras.fit(cam, scene, points=pts)
        animation.bake(scene, a)
        self.report({"INFO"}, f"'{cam.name}' fitted on {len(frames)} moments of the animation")
        return {"FINISHED"}


class FRESING_OT_anim_clear(bpy.types.Operator):
    """Remove the animation keys and put the model back as it was before building"""

    bl_idname = "fresing.anim_clear"
    bl_label = "Stop animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.screen is not None and context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        animation.clear_keys(context.scene)
        context.scene.frame_set(1)
        return {"FINISHED"}


# =============================================================================
# render queue
# =============================================================================


class FRESING_OT_queue_add(bpy.types.Operator):
    """Add a render to the queue"""

    bl_idname = "fresing.queue_add"
    bl_label = "Add to queue"
    bl_options = {"REGISTER", "UNDO"}

    kind: EnumProperty(items=[("STILL", "Image", ""), ("ANIMATION", "Animation", ""),
                              ("SHOT", "Saved scene", ""), ("ALL_SHOTS", "Every saved scene", ""),
                              ("TEST", "Time test", "Render two frames of the animation to see how long "
                                                    "the whole animation will take")],
                       default="STILL")
    name: StringProperty(options={"SKIP_SAVE"})
    start: BoolProperty(name="Start now", default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {
            "STILL": "Adds a picture of the model as it is now, from the active camera, to the queue. Start "
                     "queue renders it in the background",
            "SHOT": "Adds a picture of the selected scene to 7 Render queue. Start queue there renders it in the "
                    "background",
            "ALL_SHOTS": "Adds a picture of every saved scene to 7 Render queue. Start queue there renders them in "
                         "the background",
            "ANIMATION": "Renders this animation in the background and starts the queue (7 Render queue). Keep "
                         "working, or close the app: it keeps going",
            "TEST": "Renders 2 frames of this animation in the queue, then shows how long the whole video will take "
                    "with these settings",
        }.get(properties.kind, "Adds a render to the queue")

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        if self.kind in ("ANIMATION", "TEST"):
            a = s.animations.get(self.name) if self.name else _active_anim(context)
            if a is None:
                return {"CANCELLED"}
            queue.add_job(scene, self.kind, animation=a.name)
        elif self.kind == "SHOT":
            name = self.name or (s.shots[s.shots_index].name if 0 <= s.shots_index < len(s.shots) else "")
            if not name:
                return {"CANCELLED"}
            queue.add_job(scene, "STILL", shot=name)
        elif self.kind == "ALL_SHOTS":
            for shot in s.shots:
                queue.add_job(scene, "STILL", shot=shot.name)
        else:
            if scene.camera is None:
                self.report({"WARNING"}, "Add a camera first")
                return {"CANCELLED"}
            # the current view: saved as a hidden scene so the queue renders exactly this
            name = states.unique_shot_name(scene, f"Queue {scene.camera.name}")
            keep_index = s.shots_index
            shot = states.save_shot(scene, name)
            shot["fr_queue_only"] = True          # hidden from the scene list
            s.shots_index = keep_index
            queue.add_job(scene, "STILL", shot=name)
        if self.start and not queue.is_running(scene):
            return bpy.ops.fresing.queue_start()
        return {"FINISHED"}


class FRESING_OT_queue_start(bpy.types.Operator):
    """Start rendering the queue in the background (keeps going when you close the app)"""

    bl_idname = "fresing.queue_start"
    bl_label = "Start queue"

    def execute(self, context):
        try:
            qdir = queue.start(context)
        except (RuntimeError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        context.scene.fresing.last_message = f"Queue started ({qdir})"
        return {"FINISHED"}


class FRESING_OT_queue_stop(bpy.types.Operator):
    """Stop after the current frame or image (start again later to continue an animation)"""

    bl_idname = "fresing.queue_stop"
    bl_label = "Stop queue"

    now: BoolProperty(name="Stop now", default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.now:
            return ("Stops the render at once; the frame being rendered is lost. Start queue continues an animation "
                    "where it stopped")
        return "Stops when the current frame or picture is done. Start queue continues an animation where it stopped"

    def execute(self, context):
        if self.now:
            queue.kill(context.scene)
        else:
            queue.stop(context.scene)
        return {"FINISHED"}


class FRESING_OT_queue_remove(bpy.types.Operator):
    bl_idname = "fresing.queue_remove"
    bl_label = "Remove from queue"
    bl_options = {"REGISTER", "UNDO"}

    finished: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.finished:
            return "Takes all finished jobs out of the list. Their files stay"
        return "Takes the selected job out of the queue. Files it already rendered stay"

    def execute(self, context):
        s = context.scene.fresing
        if self.finished:
            for i in reversed(range(len(s.queue))):
                if s.queue[i].status == "DONE":
                    s.queue.remove(i)
        elif 0 <= s.queue_index < len(s.queue):
            if s.queue[s.queue_index].status == "RUNNING":
                self.report({"WARNING"}, "Stop the queue first")
                return {"CANCELLED"}
            s.queue.remove(s.queue_index)
        s.queue_index = min(s.queue_index, max(0, len(s.queue) - 1))
        for shot in [x for x in s.shots if x.get("fr_queue_only")]:
            if not any(j.shot == shot.name for j in s.queue):
                s.shots.remove(list(s.shots).index(shot))
        return {"FINISHED"}


class FRESING_OT_queue_open(bpy.types.Operator):
    """Open the rendered file or folder"""

    bl_idname = "fresing.queue_open"
    bl_label = "Open result"

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.queue_index < len(s.queue)):
            return {"CANCELLED"}
        out = s.queue[s.queue_index].output
        if not out or not os.path.exists(out):
            self.report({"WARNING"}, "Not rendered yet")
            return {"CANCELLED"}
        _open_path(out)
        return {"FINISHED"}


class FRESING_OT_open_file(bpy.types.Operator):
    """Opens the rendered picture or video in the program Windows uses for that kind of file"""

    bl_idname = "fresing.open_file"
    bl_label = "Open"

    path: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        if not self.path or not os.path.exists(self.path):
            self.report({"WARNING"}, "The file is not there any more")
            return {"CANCELLED"}
        files.open_path(self.path)
        return {"FINISHED"}


class FRESING_OT_show_in_folder(bpy.types.Operator):
    """Open the folder of this render, with the file selected"""

    bl_idname = "fresing.show_in_folder"
    bl_label = "Show in folder"

    path: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        if not self.path or not os.path.exists(self.path):
            self.report({"WARNING"}, "The file is not there any more")
            return {"CANCELLED"}
        files.show_in_folder(self.path)
        return {"FINISHED"}


class FRESING_OT_queue_log(bpy.types.Operator):
    """Open the queue's log file (useful when a job failed)"""

    bl_idname = "fresing.queue_log"
    bl_label = "Open log"

    def execute(self, context):
        s = context.scene.fresing
        path = os.path.join(s.queue_dir, "log.txt") if s.queue_dir else ""
        if not path or not os.path.exists(path):
            return {"CANCELLED"}
        _open_path(path)
        return {"FINISHED"}


CLASSES = (
    FRESING_OT_report_select_new, FRESING_OT_report_clear,
    FRESING_OT_joint_add, FRESING_OT_joint_pick_axis, FRESING_OT_joint_remove, FRESING_OT_joint_swap,
    FRESING_OT_joint_flip,
    FRESING_OT_joint_axis_preset, FRESING_OT_joint_kind, FRESING_OT_joint_members, FRESING_OT_joint_value,
    FRESING_OT_joint_follow,
    FRESING_OT_pose_save, FRESING_OT_pose_apply, FRESING_OT_pose_update, FRESING_OT_pose_remove,
    FRESING_OT_pose_reset, FRESING_OT_explode,
    FRESING_OT_vis_save, FRESING_OT_vis_apply, FRESING_OT_vis_update, FRESING_OT_vis_remove,
    FRESING_OT_shot_save, FRESING_OT_shot_apply, FRESING_OT_shot_update, FRESING_OT_shot_remove,
    FRESING_OT_anim_add, FRESING_OT_anim_remove, FRESING_OT_block_add, FRESING_OT_block_remove,
    FRESING_OT_block_move, FRESING_OT_block_duplicate, FRESING_OT_block_target, FRESING_OT_anim_build,
    FRESING_OT_anim_fit_camera, FRESING_OT_anim_clear,
    FRESING_OT_queue_add, FRESING_OT_queue_start, FRESING_OT_queue_stop, FRESING_OT_queue_remove,
    FRESING_OT_queue_open, FRESING_OT_queue_log, FRESING_OT_open_file, FRESING_OT_show_in_folder,
)
