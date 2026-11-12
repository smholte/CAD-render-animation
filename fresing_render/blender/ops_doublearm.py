"""Operators of the double-arm tool changer (task 0064): 4 Motion > CNC machine > Tool changes."""

from __future__ import annotations

import time

import bpy
from mathutils import Vector

from . import build, doublearm, gcode, hover, joints


class _ArmOp:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and hasattr(context.scene, "fresing")


def _arm_objects(context, part):
    """The arm: the selected subassembly (or parts) the clicked part belongs to, else the clicked part."""
    sel = [o for o in context.selected_objects if o.get(build.PROP_KIND) in build.MODEL_KINDS]
    hits = []
    for o in sel:
        p = part
        while p is not None:
            if p is o:
                hits.append(o)
                break
            p = p.parent
    if not hits:
        return [part]
    top = [o for o in hits if not any(x is not o and o in x.children_recursive for x in hits)]
    return top


def hub_refused(scene, direction) -> str:
    """What ``doublearm.make_arm`` would refuse about a hub axis, for the hover highlight ('' = fine)."""
    import math
    d = Vector(direction).normalized()
    up = doublearm.spindle_axis(scene)
    if up is None or up.length < 1e-9:
        return ""
    if d.dot(up) < 0:
        d = -d
    if d.angle(up) > math.radians(5):
        return "not parallel with the spindle: click a round face of the hub"
    return ""


def hinge_refused(scene, pot) -> str:
    """What ``doublearm.make_pots`` would refuse about a clicked pot, for the hover highlight ('' = fine)."""
    from . import toolchange
    car = toolchange.carousel(scene)
    if car is None:
        return "pick the magazine's rotate joint (Carousel) first"
    if doublearm.arm_joints(scene)[1] is None:
        return "make the arm first ('Click the arm's hub')"
    if not gcode._carries(car, pot):
        return f"not turned by '{car.name}': click the hinge of a pot on the magazine"
    return ""


class _Click:
    """A one-click eyedropper on a round face: ``picked(context, part, origin, direction)`` returns '' or why not."""

    prompt = ""

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, self.prompt + "  Esc / right-click: cancel.  Middle mouse / scroll: move the view",
                    refuse=lambda ob, o, d: self.refuse(context, ob, o, d))
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def refuse(self, context, ob, origin, direction) -> str:
        """Why a click here would be refused, worked out while the mouse moves ('' = fine)."""
        return ""

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
            hover.prompt(context, "Missed: " + self.prompt + "  Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        origin, direction, _desc = joints.axis_from_hit(ob, index, loc, normal)
        self._end(context)
        why = self.picked(context, ob, origin, direction)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_cnc_arm_hub(_Click, _ArmOp, bpy.types.Operator):
    """Click a round face of the arm's hub (where it turns): the app makes the arm's turn and pull-out stroke about
    that axis and reads the grip angle from the arm's claws. Select the arm's subassembly first if the arm is more
    than one part"""

    bl_idname = "fresing.cnc_arm_hub"
    bl_label = "Click the arm's hub"
    prompt = "Click a round face of the arm's hub (the arm turns about it)."

    def refuse(self, context, ob, origin, direction) -> str:
        return hub_refused(context.scene, direction)

    def picked(self, context, ob, origin, direction):
        objs = _arm_objects(context, ob)
        why = doublearm.make_arm(context.scene, objs, origin, direction, ref=ob)
        if not why:
            c = gcode.settings(context.scene)
            self.report({"INFO"}, f"Arm made: grip angle {c.arm_grip * 57.29578:.1f}°, stroke "
                                  f"{c.arm_stroke * 1000:.0f} mm. Press Check")
        return why


class FRESING_OT_cnc_arm_hinge(_Click, _ArmOp, bpy.types.Operator):
    """Click the hinge (its round pin or bore) of the pot at the change station, the pot the arm's second claw reaches:
    the app puts a pocket in every pot round the magazine ('Pockets' of them) and makes the joints that tip the pots"""

    bl_idname = "fresing.cnc_arm_hinge"
    bl_label = "Click the hinge"
    prompt = "Click the hinge pin of the pot at the change station."

    def refuse(self, context, ob, origin, direction) -> str:
        return hinge_refused(context.scene, ob)

    def picked(self, context, ob, origin, direction):
        why = doublearm.make_pots(context.scene, ob, origin, direction)
        if not why:
            c = gcode.settings(context.scene)
            self.report({"INFO"}, f"{len(c.pockets)} pots, each tips about its hinge. Press Check")
        return why


class FRESING_OT_cnc_arm_read(_ArmOp, bpy.types.Operator):
    """Reads the grip angle from the arm's claws again (the turn that puts a claw on the spindle's axis at the change
    position) and sets the pull-out stroke for the spindle tool's holder"""

    bl_idname = "fresing.cnc_arm_read"
    bl_label = "Read from the model"

    def execute(self, context):
        sc = context.scene
        c = gcode.settings(sc)
        try:
            mach = gcode.Machine(sc)
        except gcode.SetupError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        g, note = doublearm.read_grip(sc, mach)
        c.arm_stroke = doublearm.default_stroke(sc)
        if g is None:
            self.report({"WARNING"}, note)
            return {"CANCELLED"}
        c.arm_grip = g
        self.report({"INFO"}, f"Grip angle {g * 57.29578:.1f}°, stroke {c.arm_stroke * 1000:.0f} mm")
        return {"FINISHED"}


class FRESING_OT_cnc_arm_remove(_ArmOp, bpy.types.Operator):
    """Removes the arm's joints and the pots' tip joints the app made (the parts go back to where they were in the
    CAD model). Then click the hub again"""

    bl_idname = "fresing.cnc_arm_remove"
    bl_label = "Remove the arm"

    def execute(self, context):
        doublearm.remove_pots(context.scene)
        doublearm.remove_arm(context.scene)
        gcode.setup_changed(context.scene)
        return {"FINISHED"}


class FRESING_OT_cnc_arm_check(_ArmOp, bpy.types.Operator):
    """Plays one tool change in the view (pot down, grip, pull, half turn, push, back) and says in words what does
    not fit: the claw not on the spindle's axis, the station pot not under the second claw, a stroke too short for the
    holder's taper"""

    bl_idname = "fresing.cnc_arm_check"
    bl_label = "Check"

    def _report(self, context):
        lines = doublearm.check(context.scene)
        bad = [t for ok, t in lines if not ok]
        doublearm.LAST_CHECK[:] = lines
        if bad:
            self.report({"WARNING"}, "; ".join(bad[:3]))
        else:
            self.report({"INFO"}, "The arm fits: " + "; ".join(t for _ok, t in lines[:3]))
        return {"FINISHED"}

    def execute(self, context):
        return self._report(context)

    def invoke(self, context, event):
        sc = context.scene
        self.poses = doublearm.check_poses(sc)
        if not self.poses or context.area is None:
            return self._report(context)
        from . import animation
        animation.clear_keys(sc)
        self.keep = {name: joints.get_value(sc.fresing.joints[name]) for name in self.poses[0][1]}
        self.t0 = time.time()
        self.timer = context.window_manager.event_timer_add(1 / 30, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _pose(self, context, values):
        for name, v in values.items():
            j = context.scene.fresing.joints.get(name)
            if j is not None:
                joints.set_value(j, v, use_limits=False)
        context.view_layer.update()
        for area in context.screen.areas if context.screen else []:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == "ESC":
            return self._finish(context)
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        t = time.time() - self.t0
        poses = self.poses
        if t >= poses[-1][0]:
            return self._finish(context)
        for (ta, va), (tb, vb) in zip(poses, poses[1:]):
            if ta <= t <= tb:
                u = 0.0 if tb <= ta else (t - ta) / (tb - ta)
                u = u * u * (3 - 2 * u)
                self._pose(context, {k: va[k] + (vb[k] - va[k]) * u for k in va})
                break
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        context.window_manager.event_timer_remove(self.timer)
        self._pose(context, self.keep)
        return self._report(context)


CLASSES = (FRESING_OT_cnc_arm_hub, FRESING_OT_cnc_arm_hinge, FRESING_OT_cnc_arm_read, FRESING_OT_cnc_arm_remove,
           FRESING_OT_cnc_arm_check)
