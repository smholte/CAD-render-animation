"""Side panel, phase 2: 4 Motion, saved scenes, 6 Animation, 7 Render queue."""

from __future__ import annotations

import bpy

from . import animation, build, joints, queue
from .ui import _has_model, _Panel

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


class FRESING_PT_motion(_Panel, bpy.types.Panel):
    bl_label = "4  Motion"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if animation.has_keys(scene):
            box = layout.box()
            box.label(text=f"Animation '{s.anim_baked}' is playing back", icon="INFO")
            box.label(text="Joints follow its keys; stop it to pose by hand")
            box.operator("fresing.anim_clear", icon="CANCEL")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.3
        op = row.operator("fresing.joint_pick_axis", text="Add rotate joint", icon="CON_ROTLIKE")
        op.mode, op.kind = "NEW", "ROTATE"
        op = row.operator("fresing.joint_pick_axis", text="Add slide joint", icon="CON_LOCLIKE")
        op.mode, op.kind = "NEW", "SLIDE"
        col.label(text="Click what should move, then Add joint and click its pivot hole or shaft", icon="INFO")

        row = layout.row()
        row.template_list("FRESING_UL_joints", "", s, "joints", s, "joints_index", rows=4)
        side = row.column(align=True)
        side.operator("fresing.joint_remove", text="", icon="REMOVE")
        side.separator()
        side.prop(s, "show_joints", text="", icon="EMPTY_SINGLE_ARROW")

        j = s.joints[s.joints_index] if 0 <= s.joints_index < len(s.joints) else None
        if j is not None and j.motion is not None:
            box = layout.box()
            row = box.row(align=True)
            for kind, label in (("ROTATE", "Rotate"), ("SLIDE", "Slide")):
                op = row.operator("fresing.joint_kind", text=label, depress=j.kind == kind)
                op.kind = kind
            row = box.row(align=True)
            row.scale_y = 1.4
            row.prop(j.motion, f'["{joints.VALUE}"]', text="Angle" if j.kind == "ROTATE" else "Distance")
            row = box.row(align=True)
            for t, label in (("ZERO", "0 (CAD)"), ("MIN", "Min"), ("MAX", "Max")):
                sub = row.row(align=True)
                sub.enabled = t == "ZERO" or j.use_limits
                sub.operator("fresing.joint_value", text=label).target = t
            box.prop(j, "use_limits")
            if j.use_limits:
                row = box.row(align=True)
                if j.kind == "ROTATE":
                    row.prop(j, "rot_min")
                    row.prop(j, "rot_max")
                else:
                    row.prop(j, "slide_min")
                    row.prop(j, "slide_max")
            box.prop(j, "base")
            mem = joints.members(j)
            names = ", ".join(m.get(build.PROP_NAME, m.name) for m in mem[:3]) + (" …" if len(mem) > 3 else "")
            box.label(text=f"Moves: {names or 'nothing'}", icon="OBJECT_DATA")
            row = box.row(align=True)
            row.operator("fresing.joint_members", text="Add selected", icon="ADD").action = "ADD"
            row.operator("fresing.joint_members", text="Remove selected", icon="REMOVE").action = "REMOVE"
            row.operator("fresing.joint_members", text="", icon="RESTRICT_SELECT_OFF").action = "SELECT"
            row = box.row(align=True)
            row.label(text="Axis")
            op = row.operator("fresing.joint_pick_axis", text="Pick", icon="EYEDROPPER")
            op.mode = "EDIT"
            row.operator("fresing.joint_flip", text="Flip", icon="ARROW_LEFTRIGHT")
            for ax in ("X", "Y", "Z"):
                row.operator("fresing.joint_axis_preset", text=ax).axis = ax
        layout.operator("fresing.pose_reset", icon="LOOP_BACK")


class FRESING_UL_poses(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")
        row.operator("fresing.pose_apply", text="Use", icon="CHECKMARK").name = item.name


class FRESING_PT_poses(_Panel, bpy.types.Panel):
    bl_label = "Poses & exploded views"
    bl_parent_id = "FRESING_PT_motion"

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="A pose = all joint positions + moved subassemblies")
        row = layout.row()
        row.template_list("FRESING_UL_poses", "", s, "poses", s, "poses_index", rows=3)
        col = row.column(align=True)
        col.operator("fresing.pose_save", text="", icon="ADD")
        col.operator("fresing.pose_remove", text="", icon="REMOVE")
        col.operator("fresing.pose_update", text="", icon="FILE_REFRESH")
        box = layout.box()
        from .ops_motion import _target_subassembly
        target = _target_subassembly(context)
        box.label(text=f"Explode: {target.get(build.PROP_NAME, target.name) if target else '-'}", icon="FULLSCREEN_EXIT")
        box.prop(s, "explode_level")
        row = box.row(align=True)
        row.prop(s, "explode_direction", text="")
        row.prop(s, "explode_factor")
        box.operator("fresing.explode", icon="FULLSCREEN_EXIT")
        box.label(text="Then save it as a pose; 'Back to CAD position' undoes it")


# =============================================================================
# saved scenes (under 5 Scene & Render)
# =============================================================================


class FRESING_UL_shots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        active = context.scene.fresing.active_shot == item.name
        row.prop(item, "name", text="", emboss=False, icon="RADIOBUT_ON" if active else "RADIOBUT_OFF")
        row.label(text=item.camera.name if item.camera else "no camera")
        row.operator("fresing.shot_apply", text="Use", icon="CHECKMARK").name = item.name

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

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="Colours + pose + visibility + camera + background + size")
        row = layout.row()
        row.template_list("FRESING_UL_shots", "", s, "shots", s, "shots_index", rows=3)
        col = row.column(align=True)
        col.operator("fresing.shot_save", text="", icon="ADD")
        col.operator("fresing.shot_remove", text="", icon="REMOVE")
        col.operator("fresing.shot_update", text="", icon="FILE_REFRESH")
        if 0 <= s.shots_index < len(s.shots):
            shot = s.shots[s.shots_index]
            box = layout.box()

            def what(v):
                return "saved with the scene" if v == "__current__" else (v or "left as it is")

            box.label(text=f"Colours: {what(shot.scheme)}")
            box.label(text=f"Pose: {what(shot.pose)}")
            box.label(text=f"Visibility: {what(shot.visibility)}")
            box.prop(shot, "camera")
        row = layout.row(align=True)
        op = row.operator("fresing.queue_add", text="Queue this scene", icon="ADD")
        op.kind = "SHOT"
        op = row.operator("fresing.queue_add", text="Queue all scenes", icon="DOCUMENTS")
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
        row.label(text=f"{animation.length_seconds(item):.1f} s")


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

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        row = layout.row()
        row.template_list("FRESING_UL_anims", "", s, "animations", s, "animations_index", rows=2)
        col = row.column(align=True)
        col.operator("fresing.anim_add", text="", icon="ADD")
        col.operator("fresing.anim_remove", text="", icon="REMOVE")
        a = animation.active(scene)
        if a is None:
            layout.label(text="Make joints and poses first, then add an animation", icon="INFO")
            return
        col = layout.column(align=True)
        col.prop_search(a, "start_shot", s, "shots", text="Start from", icon="SCENE_DATA")
        row = col.row(align=True)
        row.prop(a, "fps", text="")
        row.prop(a, "tail")

        layout.label(text="Steps")
        row = layout.row()
        row.template_list("FRESING_UL_blocks", "", a, "blocks", a, "blocks_index", rows=5)
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
            box.prop(b, "name")
            row = box.row(align=True)
            row.prop(b, "start")
            if b.kind not in ("SHOW", "HIDE") and not (b.kind == "CAMERA" and b.camera_mode == "CUT"):
                row.prop(b, "duration")
                box.prop(b, "easing")
            if b.kind == "JOINT":
                box.prop_search(b, "joint", s, "joints", icon="CON_PIVOT")
                j = s.joints.get(b.joint)
                if j is not None:
                    box.prop(b, "use_from")
                    row = box.row(align=True)
                    if j.kind == "ROTATE":
                        if not b.use_from:
                            row.prop(b, "from_angle")
                        row.prop(b, "to_angle")
                    else:
                        if not b.use_from:
                            row.prop(b, "from_dist")
                        row.prop(b, "to_dist")
                    if j.use_limits:
                        lo, hi = joints.limits(j)
                        box.label(text=f"Limits {joints.to_display(j.kind, lo):.0f} … "
                                       f"{joints.to_display(j.kind, hi):.0f} {joints.unit_label(j.kind)}")
            elif b.kind == "POSE":
                box.prop_search(b, "pose", s, "poses", icon="ARMATURE_DATA")
            elif b.kind == "CAMERA":
                box.row(align=True).prop(b, "camera_mode", expand=True)
                if b.camera_mode == "ORBIT":
                    box.prop(b, "orbit_angle")
                else:
                    box.prop(b, "camera")
            else:
                row = box.row(align=True)
                row.label(text=b.target_name or "Nothing picked", icon="OBJECT_DATA")
                row.operator("fresing.block_target", icon="EYEDROPPER")

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("fresing.anim_build", text="Build & play", icon="PLAY").play = True
        row.operator("fresing.anim_clear", text="", icon="CANCEL")
        if s.anim_baked:
            layout.label(text=f"Keys built for '{s.anim_baked}' · Space plays · scrub the timeline", icon="CHECKMARK")

        box = layout.box()
        box.label(text="Video")
        row = box.row(align=True)
        row.prop(a, "out_resolution", text="")
        row.prop(a, "out_format", text="")
        row = box.row(align=True)
        row.prop(a, "video", text="")
        row.prop(a, "quality", text="")
        secs = animation.length_seconds(a)
        frames = animation.frame_of(a, secs)
        box.label(text=f"{secs:.1f} s · {frames} frames")
        row = box.row(align=True)
        row.scale_y = 1.3
        op = row.operator("fresing.queue_add", text="Render animation", icon="RENDER_ANIMATION")
        op.kind, op.name, op.start = "ANIMATION", a.name, True


# =============================================================================
# 7 Render queue
# =============================================================================

_STATUS_ICON = {"WAITING": "TIME", "RUNNING": "RENDER_ANIMATION", "DONE": "CHECKMARK", "FAILED": "ERROR",
                "STOPPED": "CANCEL"}


class FRESING_UL_queue(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.label, icon=_STATUS_ICON.get(item.status, "DOT"))
        sub = row.row()
        sub.alignment = "RIGHT"
        if item.status == "RUNNING":
            sub.label(text=f"{item.progress:.0f}%")
        else:
            sub.label(text=item.bl_rna.properties["status"].enum_items[item.status].name)


class FRESING_PT_queue(_Panel, bpy.types.Panel):
    bl_label = "7  Render queue"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

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
        row = layout.row()
        row.template_list("FRESING_UL_queue", "", s, "queue", s, "queue_index", rows=4)
        col = row.column(align=True)
        col.operator("fresing.queue_remove", text="", icon="REMOVE")
        col.operator("fresing.queue_remove", text="", icon="BRUSH_DATA").finished = True
        if 0 <= s.queue_index < len(s.queue):
            job = s.queue[s.queue_index]
            box = layout.box()
            if job.status == "RUNNING":
                box.progress(factor=job.progress / 100.0, text=f"{job.progress:.0f}%")
            if job.message:
                box.label(text=job.message)
            if job.output:
                box.operator("fresing.queue_open", icon="FILE_FOLDER")
        row = layout.row(align=True)
        row.scale_y = 1.3
        if running:
            row.operator("fresing.queue_stop", text="Stop after this frame", icon="PAUSE")
            row.operator("fresing.queue_stop", text="Stop now", icon="CANCEL").now = True
            layout.label(text="Renders in the background, also when the app is closed", icon="INFO")
        else:
            row.operator("fresing.queue_start", icon="PLAY")
        if s.queue_dir:
            layout.operator("fresing.queue_log", icon="TEXT")


CLASSES = (
    FRESING_UL_joints, FRESING_UL_poses, FRESING_UL_shots, FRESING_UL_anims, FRESING_UL_blocks, FRESING_UL_queue,
    FRESING_PT_motion, FRESING_PT_poses, FRESING_PT_shots, FRESING_PT_animation, FRESING_PT_queue,
)

