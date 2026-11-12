"""Operators of panel 5 Scene & Render added by task 0017: light looks, the sharp spot, the
turntable video. (Background, camera and render buttons of earlier versions: ops_main.py.)"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..core import studio
from ..core import surroundings as env
from . import build, cameras, hover, turntable, world


def _redraw(context) -> None:
    for area in getattr(context.screen, "areas", []) if context.screen else []:
        area.tag_redraw()


class FRESING_OT_light_look(bpy.types.Operator):
    """Sets light, background and floor to a ready-made look in one click. Fine-tune it below
    (Turn light, Brightness, colour)"""

    bl_idname = "fresing.light_look"
    bl_label = "Light look"
    bl_options = {"REGISTER", "UNDO"}

    look: EnumProperty(items=[(k, v[0], v[2]) for k, v in studio.LOOKS.items()], default="PRODUCT",
                       options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return studio.LOOKS.get(properties.look, ("", "", cls.__doc__))[2]

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        values = studio.look_settings(self.look, s.background, env.SEA_KINDS)
        live = s.live_update
        s.live_update = False                    # one rebuild, not one per setting
        try:
            for k, v in values.items():
                setattr(s, k, v)
        finally:
            s.live_update = live
        world.apply(scene, s)
        s.last_message = f"Light look: {studio.LOOKS[self.look][0]}"
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_focus_pick(bpy.types.Operator):
    """Click the spot on the machine that should be sharp; what is far in front of or behind it gets
    blurred. In pictures the spot moves with its part. Esc cancels"""

    bl_idname = "fresing.focus_pick"
    bl_label = "Pick the sharp spot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return cameras.can_blur(context.scene.camera)

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        cam = context.scene.camera
        if cam is not None and cam.get("fr_anim_camera"):
            self.report({"WARNING"}, "This is the animation's own camera: pick one of your cameras above first")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, "Click the spot on the machine that should be sharp.  Esc / right-click: cancel.  "
                                   "Middle mouse / scroll: move the view", point=True,
                    note=lambda ob, name, *_a: f"Sharp spot here – {name}")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

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
        if res is None or res[0].get(build.PROP_KIND) != "part":
            hover.prompt(context, "Missed the machine: click a part. Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        scene = context.scene
        cameras.set_focus(scene.camera, scene, ob, loc)
        msg = f"Sharp at '{cameras.focus_label(scene.camera)}' ({scene.camera.data.dof.focus_distance:.2f} m " \
              f"from '{scene.camera.name}')"
        scene.fresing.last_message = msg
        self.report({"INFO"}, msg)
        _redraw(context)
        return {"FINISHED"}

    def execute(self, context):              # scripts and tests: the middle of the machine
        scene = context.scene
        if not cameras.can_blur(scene.camera):
            return {"CANCELLED"}
        mid = cameras._model_middle(scene)
        cameras.set_focus(scene.camera, scene, None, mid)
        return {"FINISHED"}


class FRESING_OT_focus_clear(bpy.types.Operator):
    """Makes the middle of the machine the sharp spot again (instead of the spot you clicked)"""

    bl_idname = "fresing.focus_clear"
    bl_label = "Sharp in the middle"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cam = context.scene.camera
        if cameras.focus_marker(cam) is None:
            return {"CANCELLED"}
        cameras.clear_focus(cam, context.scene)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_env_simple(bpy.types.Operator):
    """Builds the surroundings with fewer things around the machine (Detail: Simple): renders
    faster, which counts in a video with hundreds of frames"""

    bl_idname = "fresing.env_simple"
    bl_label = "Use Simple (faster)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.fresing.env_detail = "SIMPLE"
        return {"FINISHED"}


class FRESING_OT_turntable(bpy.types.Operator):
    """Makes a video of the camera going once round the machine and renders it in the background
    (7 Render queue). The machine looks as it does now. Click it again after changing the machine, or
    the size, shape or frame rate in 6 Animation, 'Turntable'"""

    bl_idname = "fresing.turntable"
    bl_label = "Make turntable video"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def execute(self, context):
        from . import queue
        scene = context.scene
        s = scene.fresing
        if turntable.is_turntable_running(scene):
            self.report({"WARNING"}, "A turntable video is already in the queue: wait for it, or remove it in "
                                     "7 Render queue")
            return {"CANCELLED"}
        info = turntable.make(scene)
        a = info["animation"]
        turntable.drop_unfinished_jobs(scene, a)     # else Start queue would render an old one again
        job_id = queue.add_job(scene, "ANIMATION", animation=a.name).job_id
        msg = (f"Turntable video in 7 Render queue: {info['seconds']:.0f} s, {info['frames']} frames, "
               f"{info['size'].width} × {info['size'].height}")
        note = turntable.slow_note(s)
        if queue.is_running(scene):
            msg += ". It starts when you press Start queue (another render is running)"
        else:
            try:                             # a delayed start keeps the other jobs for later (0068 row 5)
                queue.start(context, only={job_id} if queue.delay_pending() else None)
            except (RuntimeError, OSError) as exc:
                for i in reversed(range(len(s.queue))):     # nothing started: no job left waiting
                    if s.queue[i].job_id == job_id:
                        s.queue.remove(i)
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        s.last_message = msg
        self.report({"WARNING"} if note else {"INFO"}, msg + (f". {note}" if note else ""))
        _redraw(context)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# camera steps that ride along, fly a path or keep a part in the middle (task 0087)
# ---------------------------------------------------------------------------

def _path_step(context):
    """The selected step of the animation when it is a Fly a path camera step, else None."""
    from .ops_motion import _active_block
    b = _active_block(context)
    if b is None or b.kind != "CAMERA" or b.camera_mode != "PATH":
        return None
    return b


def _after_path_change(context, b) -> None:
    from . import animation, camera_path
    camera_path.show_path(context.scene, b)
    if context.scene.fresing.anim_baked:
        animation.clear_keys(context.scene)          # the built camera no longer matches: build again
    _redraw(context)


class FRESING_OT_path_from_cameras(bpy.types.Operator):
    """Makes the path go through every saved camera (5 Scene & Render > Cameras), in the order of that list. The
    camera flies through their places; where it looks is set by Look"""

    bl_idname = "fresing.path_from_cameras"
    bl_label = "Make path from saved cameras"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _path_step(context) is not None

    def execute(self, context):
        from . import camera_path
        b = _path_step(context)
        pts = camera_path.from_cameras(context.scene)
        if len(pts) < 2:
            self.report({"WARNING"}, "Save at least two cameras first (5 Scene & Render > Cameras)")
            return {"CANCELLED"}
        b.path_points.clear()
        for p in pts:
            b.path_points.add().co = p
        _after_path_change(context, b)
        self.report({"INFO"}, f"Path through {len(pts)} cameras")
        return {"FINISHED"}


class FRESING_OT_path_add_view(bpy.types.Operator):
    """Adds the place you look from in the 3D view as the next point of the path. Move the view to the next spot
    (or look through a camera) and click again"""

    bl_idname = "fresing.path_add_view"
    bl_label = "Add this view"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _path_step(context) is not None

    def execute(self, context):
        from . import camera_path
        b = _path_step(context)
        p = camera_path.view_point(context)
        if p is None:
            self.report({"WARNING"}, "No 3D view found")
            return {"CANCELLED"}
        b.path_points.add().co = tuple(p)
        _after_path_change(context, b)
        return {"FINISHED"}


class FRESING_OT_path_remove_point(bpy.types.Operator):
    """Removes the last point of the path"""

    bl_idname = "fresing.path_remove_point"
    bl_label = "Remove last point"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        b = _path_step(context)
        return b is not None and len(b.path_points) > 0

    def execute(self, context):
        b = _path_step(context)
        b.path_points.remove(len(b.path_points) - 1)
        _after_path_change(context, b)
        return {"FINISHED"}


class FRESING_OT_path_clear(bpy.types.Operator):
    """Removes every point of the path, to start it again"""

    bl_idname = "fresing.path_clear"
    bl_label = "Clear path"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        b = _path_step(context)
        return b is not None and len(b.path_points) > 0

    def execute(self, context):
        b = _path_step(context)
        b.path_points.clear()
        _after_path_change(context, b)
        return {"FINISHED"}


class FRESING_OT_aim_target(bpy.types.Operator):
    """Uses the selected part or subassembly as the part the camera keeps in the middle of the picture. Click it in
    the view (or pick it in 2 Structure) first"""

    bl_idname = "fresing.aim_target"
    bl_label = "Use selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .ops_motion import _active_block, _target_subassembly
        b = _active_block(context)
        ob = _target_subassembly(context)
        if b is None or ob is None:
            return {"CANCELLED"}
        b.aim_uid = ob.get(build.PROP_UID, ob.name)
        b.aim_name = ob.get(build.PROP_NAME, ob.name)
        return {"FINISHED"}


CLASSES = (FRESING_OT_light_look, FRESING_OT_focus_pick, FRESING_OT_focus_clear, FRESING_OT_env_simple,
           FRESING_OT_turntable, FRESING_OT_path_from_cameras, FRESING_OT_path_add_view, FRESING_OT_path_remove_point,
           FRESING_OT_path_clear, FRESING_OT_aim_target)
