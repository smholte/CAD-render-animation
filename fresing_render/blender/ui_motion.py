"""Side panel, phase 2: 4 Motion, saved scenes, 6 Animation, 7 Render queue.

Same layout rules as ui.py: steps top to bottom, the main button big, details of the
selected list item right under the list, rarely used settings folded away.
"""

from __future__ import annotations

import bpy

from . import animation, build, joints, queue
from .ui import (BIG, MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, primary, split_props,
                 steps, use_button, wrap)

# =============================================================================
# 4 Motion
# =============================================================================


class FRESING_UL_joints(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False,
                 icon="CON_ROTLIKE" if item.kind == "ROTATE" else "CON_LOCLIKE")
        if item.motion is not None:
            row.prop(item.motion, f'["{joints.VALUE}"]', text="")
        else:
            row.label(text="(broken)", icon="ERROR")


def _names(objs, n: int = 2) -> str:
    names = [o.get(build.PROP_NAME, o.name) for o in objs]
    return ", ".join(names[:n]) + (f" +{len(names) - n}" if len(names) > n else "")


class FRESING_PT_motion(_Panel, bpy.types.Panel):
    bl_label = "4  Motion"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="CON_ROTLIKE")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.joints)
        header_status(self.layout, f"{n} joint{'s' if n != 1 else ''}" if n else "no joints")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        from .ops_motion import selected_movers
        if animation.has_keys(scene):
            box = layout.box()
            box.alert = True
            wrap(box, context, f"Animation '{s.anim_baked}' is built: the joints follow it.", icon="INFO", inset=12)
            box.operator("fresing.anim_clear", text="Stop it to move joints by hand", icon="CANCEL")

        # -- adding a joint: what moves, then the button, then a click on the pivot
        if not s.joints:
            steps(layout, context, ["Click what should move (subassembly or part)",
                                    "Add rotate joint or Add slide joint",
                                    "Click its pivot hole or shaft in the view"])
        movers = selected_movers(context)
        if movers:
            wrap(layout, context, f"Selected: {_names(movers)}", icon="RESTRICT_SELECT_OFF")
        else:
            wrap(layout, context, "Nothing selected: click what should move", icon="RESTRICT_SELECT_ON", alert=True)
        row = big_row(layout, MEDIUM)
        op = row.operator("fresing.joint_pick_axis", text="Add rotate joint", icon="CON_ROTLIKE")
        op.mode, op.kind = "NEW", "ROTATE"
        op = row.operator("fresing.joint_pick_axis", text="Add slide joint", icon="CON_LOCLIKE")
        op.mode, op.kind = "NEW", "SLIDE"

        if s.joints:
            _draw_joints(context, layout, s)
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.pose_reset", text="Everything back to CAD position", icon="LOOP_BACK")


def _draw_joints(context, layout, s):
    layout.separator()
    row = layout.row()
    row.template_list("FRESING_UL_joints", "", s, "joints", s, "joints_index", rows=list_rows(len(s.joints), 2, 8))
    side = row.column(align=True)
    side.operator("fresing.joint_remove", text="", icon="REMOVE")
    layout.prop(s, "show_joints", text="Show joint arrows in the view")

    j = s.joints[s.joints_index] if 0 <= s.joints_index < len(s.joints) else None
    if j is not None and not joints.is_valid(j):
        box = layout.box()
        box.alert = True
        box.label(text="This joint is broken (its arrow was deleted)", icon="ERROR")
        box.operator("fresing.joint_remove", text="Remove it (parts go back to their place)")
    elif j is not None:
        box = layout.box()
        box.label(text=j.name, icon="CON_ROTLIKE" if j.kind == "ROTATE" else "CON_LOCLIKE")
        row = box.row(align=True)
        row.scale_y = BIG
        row.prop(j.motion, f'["{joints.VALUE}"]', text="Angle" if j.kind == "ROTATE" else "Distance")
        row = box.row(align=True)
        for t, label in (("ZERO", "CAD (0)"), ("MIN", "Min"), ("MAX", "Max")):
            sub = row.row(align=True)
            sub.enabled = t == "ZERO" or j.use_limits
            sub.operator("fresing.joint_value", text=label).target = t
        row = box.row(align=True)
        row.prop(j, "use_limits", text="Limits")
        if j.use_limits:
            if j.kind == "ROTATE":
                row.prop(j, "rot_min", text="")
                row.prop(j, "rot_max", text="")
            else:
                row.prop(j, "slide_min", text="")
                row.prop(j, "slide_max", text="")

        # a fold needs the full panel width, so it sits right under the box
        body = fold(layout, "fr_joint_setup", "Set-up: what moves, axis, type", icon="PREFERENCES")
        if body:
            mem = joints.members(j)
            body.label(text=f"Moves: {_names(mem, 3) or 'nothing'}", icon="OBJECT_DATA")
            row = body.row(align=True)
            row.operator("fresing.joint_members", text="Add", icon="ADD").action = "ADD"
            row.operator("fresing.joint_members", text="Remove", icon="REMOVE").action = "REMOVE"
            row.operator("fresing.joint_members", text="Select", icon="RESTRICT_SELECT_OFF").action = "SELECT"
            body.label(text="(Add / Remove use the selected parts)")
            row = body.row(align=True)
            row.label(text="Axis")
            op = row.operator("fresing.joint_pick_axis", text="", icon="EYEDROPPER")
            op.mode = "EDIT"
            row.operator("fresing.joint_flip", text="", icon="ARROW_LEFTRIGHT")
            for ax in ("X", "Y", "Z"):
                row.operator("fresing.joint_axis_preset", text=ax).axis = ax
            row = body.row(align=True)
            row.label(text="Type")
            for kind, label in (("ROTATE", "Rotate"), ("SLIDE", "Slide")):
                op = row.operator("fresing.joint_kind", text=label, depress=j.kind == kind)
                op.kind = kind
            col = split_props(body)
            col.prop(j, "base", text="Sits on")


class FRESING_UL_poses(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")
        use_button(row, "fresing.pose_apply", item.name)


class FRESING_PT_poses(_Panel, bpy.types.Panel):
    bl_label = "Poses & exploded views"
    bl_parent_id = "FRESING_PT_motion"

    def draw_header(self, context):
        self.layout.label(icon="ARMATURE_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "A pose keeps every joint position and moved part. + saves the model as it is now.")
        row = layout.row()
        row.template_list("FRESING_UL_poses", "", s, "poses", s, "poses_index", rows=list_rows(len(s.poses), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.pose_save", text="", icon="ADD")
        col.operator("fresing.pose_remove", text="", icon="REMOVE")
        col.operator("fresing.pose_update", text="", icon="FILE_REFRESH")

        layout.separator()
        layout.label(text="Exploded view", icon="FULLSCREEN_EXIT")
        box = layout.box()
        from .ops_motion import _target_subassembly
        target = _target_subassembly(context)
        box.label(text=f"Explodes: {target.get(build.PROP_NAME, target.name) if target else '-'}",
                  icon="OUTLINER_OB_GROUP_INSTANCE")
        col = split_props(box)
        col.prop(s, "explode_level", text="Pieces")
        col.prop(s, "explode_direction", text="Direction")
        col.prop(s, "explode_factor", text="Distance")
        row = big_row(box, MEDIUM)
        row.operator("fresing.explode", text="Explode", icon="FULLSCREEN_EXIT")
        box.label(text="Keep it: + above saves it as a pose")


# =============================================================================
# saved scenes (under 5 Scene & Render)
# =============================================================================


class FRESING_UL_shots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        active = context.scene.fresing.active_shot == item.name
        row.prop(item, "name", text="", emboss=False, icon="RADIOBUT_ON" if active else "RADIOBUT_OFF")
        use_button(row, "fresing.shot_apply", item.name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [0 if it.get("fr_queue_only") else self.bitflag_filter_item for it in items]
        if self.filter_name:
            needle = self.filter_name.lower()
            flags = [f if needle in it.name.lower() else 0 for f, it in zip(flags, items)]
        return flags, []


class FRESING_PT_shots(_Panel, bpy.types.Panel):
    bl_label = "Saved scenes"
    bl_parent_id = "FRESING_PT_scene"

    def draw_header(self, context):
        self.layout.label(icon="SCENE_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Colours, pose, visibility, camera and background under one name. "
                              "+ saves how it looks now.")
        n = sum(1 for sh in s.shots if not sh.get("fr_queue_only"))
        row = layout.row()
        row.template_list("FRESING_UL_shots", "", s, "shots", s, "shots_index", rows=list_rows(n, 2, 6))
        col = row.column(align=True)
        col.operator("fresing.shot_save", text="", icon="ADD")
        col.operator("fresing.shot_remove", text="", icon="REMOVE")
        col.operator("fresing.shot_update", text="", icon="FILE_REFRESH")
        if 0 <= s.shots_index < len(s.shots) and not s.shots[s.shots_index].get("fr_queue_only"):
            shot = s.shots[s.shots_index]
            box = layout.box()

            def what(v):
                return "as saved" if v == "__current__" else (v or "left as it is")

            col = split_props(box)
            col.prop(shot, "camera", text="Camera")
            info = box.column(align=True)
            info.label(text=f"Colours: {what(shot.scheme)}")
            info.label(text=f"Pose: {what(shot.pose)}")
            info.label(text=f"Visibility: {what(shot.visibility)}")
        row = big_row(layout, MEDIUM)
        op = row.operator("fresing.queue_add", text="Queue this", icon="ADD")
        op.kind = "SHOT"
        op = row.operator("fresing.queue_add", text="Queue all", icon="DOCUMENTS")
        op.kind = "ALL_SHOTS"


# =============================================================================
# 6 Animation
# =============================================================================

_KIND_ICON = {"JOINT": "CON_PIVOT", "POSE": "ARMATURE_DATA", "CAMERA": "VIEW_CAMERA", "SHOW": "HIDE_OFF",
              "HIDE": "HIDE_ON"}


class FRESING_UL_anims(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="RENDER_ANIMATION")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=f"{animation.length_seconds(item):.1f} s")


class FRESING_UL_blocks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=animation.block_label(item), icon=_KIND_ICON.get(item.kind, "DOT"))
        sub = row.row()
        sub.alignment = "RIGHT"
        if not animation.is_instant(item):
            sub.label(text=f"{item.start:.1f}–{item.start + item.duration:.1f} s")
        else:
            sub.label(text=f"at {item.start:.1f} s")


class FRESING_PT_animation(_Panel, bpy.types.Panel):
    bl_label = "6  Animation"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="RENDER_ANIMATION")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        if a is not None:
            header_status(self.layout, f"{animation.length_seconds(a):.1f} s")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not s.animations:
            steps(layout, context, ["Make joints and poses in 4 Motion",
                                    "+ below adds an animation",
                                    "Add steps: joint moves, poses, camera, show/hide",
                                    "Build & play, then Render animation"])
        row = layout.row()
        row.template_list("FRESING_UL_anims", "", s, "animations", s, "animations_index",
                          rows=list_rows(len(s.animations), 1, 4))
        col = row.column(align=True)
        col.operator("fresing.anim_add", text="", icon="ADD")
        col.operator("fresing.anim_remove", text="", icon="REMOVE")
        a = animation.active(scene)
        if a is None:
            return
        col = split_props(layout)
        col.prop_search(a, "start_shot", s, "shots", text="Start from", icon="SCENE_DATA")
        col.prop(a, "fps", text="Frame rate")
        col.prop(a, "tail", text="Hold at end (s)")

        # -- steps and the selected step
        layout.label(text="Steps (overlapping steps play together)", icon="SEQ_STRIP_DUPLICATE")
        row = layout.row()
        row.template_list("FRESING_UL_blocks", "", a, "blocks", a, "blocks_index",
                          rows=list_rows(len(a.blocks), 3, 8))
        col = row.column(align=True)
        col.operator_menu_enum("fresing.block_add", "kind", text="", icon="ADD")
        col.operator("fresing.block_remove", text="", icon="REMOVE")
        col.separator()
        col.operator("fresing.block_move", text="", icon="TRIA_UP").direction = "UP"
        col.operator("fresing.block_move", text="", icon="TRIA_DOWN").direction = "DOWN"
        col.operator("fresing.block_duplicate", text="", icon="DUPLICATE")

        if 0 <= a.blocks_index < len(a.blocks):
            b = a.blocks[a.blocks_index]
            box = layout.box()
            box.label(text=animation.block_label(b), icon=_KIND_ICON.get(b.kind, "DOT"))
            col = split_props(box)
            if b.kind == "JOINT":
                col.prop_search(b, "joint", s, "joints", text="Joint", icon="CON_PIVOT")
                j = s.joints.get(b.joint)
                if j is not None:
                    col.prop(b, "use_from", text="From where it is")
                    if j.kind == "ROTATE":
                        if not b.use_from:
                            col.prop(b, "from_angle", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_angle", text="To")
                    else:
                        if not b.use_from:
                            col.prop(b, "from_dist", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_dist", text="To")
                    if j.use_limits:
                        lo, hi = joints.limits(j)
                        box.label(text=f"Limits {joints.to_display(j.kind, lo):.0f} … "
                                       f"{joints.to_display(j.kind, hi):.0f} {joints.unit_label(j.kind)}")
            elif b.kind == "POSE":
                col.prop_search(b, "pose", s, "poses", text="Pose", icon="ARMATURE_DATA")
            elif b.kind == "CAMERA":
                box.row(align=True).prop(b, "camera_mode", expand=True)
                col = split_props(box)
                if b.camera_mode == "ORBIT":
                    col.prop(b, "orbit_angle", text="Turn")
                else:
                    col.prop(b, "camera", text="To camera")
            else:
                row = box.row(align=True)
                row.label(text=b.target_name or "Nothing picked", icon="OBJECT_DATA")
                row.operator("fresing.block_target", text="Use selected", icon="EYEDROPPER")
            col = split_props(box)
            col.prop(b, "start", text="Start (s)")
            if b.kind not in ("SHOW", "HIDE") and not (b.kind == "CAMERA" and b.camera_mode == "CUT"):
                col.prop(b, "duration", text="Duration (s)")
                col.prop(b, "easing", text="Motion")
            col.prop(b, "name", text="Label")

        # -- check it
        layout.separator()
        row = big_row(layout, MEDIUM)
        row.operator("fresing.anim_build", text="Build & play", icon="PLAY").play = True
        row.operator("fresing.anim_clear", text="", icon="CANCEL")
        if s.anim_baked:
            layout.label(text="Built · Space plays it again", icon="CHECKMARK")
        layout.operator("fresing.anim_fit_camera", text="Fit camera to the whole motion", icon="FULLSCREEN_ENTER")

        # -- the video
        layout.separator()
        layout.label(text="Video", icon="FILE_MOVIE")
        box = layout.box()
        col = split_props(box)
        col.prop(a, "out_resolution", text="Size")
        col.prop(a, "out_format", text="Shape")
        col.prop(a, "video", text="File")
        col.prop(a, "quality", text="Quality")
        secs = animation.length_seconds(a)
        frames = animation.frame_of(a, secs)
        box.label(text=f"{secs:.1f} s · {frames} frames", icon="TIME")
        test = queue.last_time_test(scene, a.name)
        if test is not None:
            if test.status == "DONE":
                wrap(box, context, test.message, icon="CHECKMARK", inset=12)
            elif test.status in ("WAITING", "RUNNING"):
                wrap(box, context, "Time test: " + (test.message or "waiting in the queue"), icon="SORTTIME",
                     inset=12)
        op = box.operator("fresing.queue_add", text="Time test (2 frames)", icon="SORTTIME")
        op.kind, op.name, op.start = "TEST", a.name, True
        op = primary(box, "fresing.queue_add", "Render animation", "RENDER_ANIMATION")
        op.kind, op.name, op.start = "ANIMATION", a.name, True


# =============================================================================
# 7 Render queue
# =============================================================================

_STATUS_ICON = {"WAITING": "TIME", "RUNNING": "RENDER_ANIMATION", "DONE": "CHECKMARK", "FAILED": "ERROR",
                "STOPPED": "CANCEL"}


class FRESING_UL_queue(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.alert = item.status == "FAILED"
        row.label(text=item.label, icon=_STATUS_ICON.get(item.status, "DOT"))
        sub = row.row()
        sub.alignment = "RIGHT"
        if item.status == "RUNNING":
            sub.label(text=f"{item.progress:.0f}%")
        else:
            sub.label(text=item.bl_rna.properties["status"].enum_items[item.status].name)


def _queue_status(scene) -> tuple[str, str, bool]:
    s = scene.fresing
    run = [j for j in s.queue if j.status == "RUNNING"]
    if run:
        return f"{run[0].progress:.0f}% done", "NONE", False
    wait = sum(1 for j in s.queue if j.status in ("WAITING", "STOPPED"))
    failed = sum(1 for j in s.queue if j.status == "FAILED")
    if failed:
        return f"{failed} failed", "NONE", True
    if wait:
        return f"{wait} waiting", "NONE", False
    if s.queue:
        return "all done", "NONE", False
    return "", "NONE", False


class FRESING_PT_queue(_Panel, bpy.types.Panel):
    bl_label = "7  Render queue"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="SEQUENCE")

    def draw_header_preset(self, context):
        text, icon, alert = _queue_status(context.scene)
        if text:
            header_status(self.layout, text, icon=icon, alert=alert)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        running = queue.is_running(scene)
        row = layout.row(align=True)
        op = row.operator("fresing.queue_add", text="Current view", icon="ADD")
        op.kind = "STILL"
        op = row.operator("fresing.queue_add", text="All scenes", icon="DOCUMENTS")
        op.kind = "ALL_SHOTS"
        layout.label(text="Animations: Render animation in 6", icon="INFO")
        row = layout.row()
        row.template_list("FRESING_UL_queue", "", s, "queue", s, "queue_index", rows=list_rows(len(s.queue), 3, 8))
        col = row.column(align=True)
        col.operator("fresing.queue_remove", text="", icon="REMOVE")
        col.operator("fresing.queue_remove", text="", icon="BRUSH_DATA").finished = True
        if 0 <= s.queue_index < len(s.queue):
            job = s.queue[s.queue_index]
            box = layout.box()
            box.alert = job.status == "FAILED"
            box.label(text=job.label, icon=_STATUS_ICON.get(job.status, "DOT"))
            if job.status == "RUNNING":
                box.progress(factor=job.progress / 100.0, text=f"{job.progress:.0f}%")
            if job.message:
                wrap(box, context, job.message, inset=12)
            if job.output:
                row = box.row(align=True)
                row.scale_y = MEDIUM
                row.operator("fresing.queue_open", text="Open", icon="PLAY" if job.kind == "ANIMATION" else "IMAGE")
                row.operator("fresing.show_in_folder", text="Show in folder", icon="FILE_FOLDER").path = job.output
        layout.separator()
        if running:
            row = big_row(layout, MEDIUM)
            row.operator("fresing.queue_stop", text="Stop after this frame", icon="PAUSE")
            sub = row.row(align=True)
            sub.alert = True
            sub.operator("fresing.queue_stop", text="Stop now", icon="CANCEL").now = True
            layout.label(text="Keeps going if you close the app", icon="INFO")
        elif any(j.status in ("WAITING", "STOPPED", "FAILED") for j in s.queue):
            primary(layout, "fresing.queue_start", "Start queue", "PLAY")
        else:
            row = big_row(layout)
            row.operator("fresing.queue_start", text="Start queue", icon="PLAY")
        if s.queue_dir:
            layout.operator("fresing.queue_log", text="Open log (time per frame, errors)", icon="TEXT")


CLASSES = (
    FRESING_UL_joints, FRESING_UL_poses, FRESING_UL_shots, FRESING_UL_anims, FRESING_UL_blocks, FRESING_UL_queue,
    FRESING_PT_motion, FRESING_PT_poses, FRESING_PT_shots, FRESING_PT_animation, FRESING_PT_queue,
)
