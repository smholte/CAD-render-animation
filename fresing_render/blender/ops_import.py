"""Import operators: STEP file -> background reader -> Blender objects."""

from __future__ import annotations

import os

import bpy
from bpy.props import CollectionProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..importer.runner import ImportJob
from . import build, cameras, logic, prefs, render, world

_ACTIVE_JOB: ImportJob | None = None


def cache_root() -> str:
    try:
        base = bpy.utils.extension_path_user(__package__.rsplit(".", 1)[0], path="cache", create=True)
    except Exception:
        base = os.path.join(bpy.utils.user_resource("DATAFILES", path="fresing_render", create=True), "cache")
    os.makedirs(base, exist_ok=True)
    return base


def finish_import(context, cache_dir: str, up_axis: str = "Z") -> bpy.types.Object:
    """Build objects from a finished cache and set up a ready-to-render scene."""
    scene = context.scene
    s = scene.fresing
    root = build.build(cache_dir)
    logic.set_up_axis(root, up_axis)
    logic.lock_all(scene)
    template = prefs.default_template_path()
    if template and len(s.rules) == 0:
        from ..core.template import Template
        from .ops_main import apply_template
        try:
            apply_template(scene, Template.load(template))
        except (OSError, ValueError) as exc:
            print("Fresing Render: default template not loaded:", exc)
    logic.apply_rules(scene)
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    render.apply_output(scene, s)
    scene.render.engine = "CYCLES"
    context.view_layer.update()
    if not cameras.fr_cameras(scene):
        cameras.add_camera(scene, "ISO")
    world.apply(scene, s)
    frame_views(context, scene)
    return root


def frame_views(context, scene) -> None:
    """Point every 3D view at the model (after an import the view may be anywhere)."""
    if bpy.app.background:
        return
    from mathutils import Vector
    mn, mx = logic.cached_bounds(scene)
    centre = Vector(((mn + mx) / 2).tolist())
    size = max((Vector(mx.tolist()) - Vector(mn.tolist())).length, 0.1)
    for win in getattr(context.window_manager, "windows", []):
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            r3d = area.spaces.active.region_3d
            if r3d is None or r3d.view_perspective == "CAMERA":
                continue
            r3d.view_location = centre
            r3d.view_distance = size * 1.2
            area.spaces.active.clip_end = max(area.spaces.active.clip_end, size * 20)
            area.tag_redraw()


class FRESING_OT_import_step(bpy.types.Operator, ImportHelper):
    """Import a STEP assembly: pick the file, it is read in the background (the app stays usable).
    Choose the detail and up axis above first"""

    bl_idname = "fresing.import_step"
    bl_label = "Import STEP"
    bl_options = {"UNDO"}   # no "Adjust last operation": re-running a background import is not supported

    filename_ext = ".step"
    # Not remembered between calls, so the button always opens the file browser.
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE", "HIDDEN"})
    filter_glob: StringProperty(default="*.step;*.stp;*.STEP;*.STP", options={"HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"})
    quality: EnumProperty(
        name="Quality", default="normal",
        items=[("draft", "Draft", "Fast, coarse curves"), ("normal", "Normal", "Good for most renders"),
               ("fine", "Fine", "Smooth curves for close-ups")])
    up_axis: EnumProperty(name="Up axis", default="Z", items=[("Z", "Z up", ""), ("Y", "Y up", "")])
    # UPDATE: replace this model by a new revision of the file and keep all work
    update_root: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if properties.update_root:
            return ("Read a new revision of this model's STEP file. Parts are matched with the old ones and keep "
                    "their groups, painted faces, joints, poses and scenes; a report lists what is new or missing")
        return cls.__doc__.replace("\n    ", " ")

    _timer = None
    _job: ImportJob | None = None

    def invoke(self, context, event):
        s = context.scene.fresing
        self.quality = s.import_quality
        self.up_axis = s.import_up_axis
        if self.directory and self.files and self.files[0].name:   # drag & drop
            if len(self.files) > 1:
                self.report({"WARNING"}, "Several files dropped: importing the first one")
            return self.execute(context)
        root = bpy.data.objects.get(self.update_root) if self.update_root else None
        if root is not None:
            src = root.get(build.PROP_SOURCE, "")
            self.quality = root.get("fr_quality", self.quality)
            if src:
                self.filepath = src            # the file browser opens on the current file
        return ImportHelper.invoke(self, context, event)

    def _path(self) -> str:
        if self.files and self.directory and self.files[0].name:
            return os.path.join(self.directory, self.files[0].name)
        return self.filepath

    def execute(self, context):
        global _ACTIVE_JOB
        path = self._path()
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"File not found: {path}")
            return {"CANCELLED"}
        if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
            try:
                _ACTIVE_JOB.poll()
            except Exception:
                _ACTIVE_JOB.done = True
            if not _ACTIVE_JOB.done:
                self.report({"WARNING"}, "An import is already running")
                return {"CANCELLED"}
        if self.update_root and bpy.data.objects.get(self.update_root) is None:
            self.report({"ERROR"}, "The model to update is no longer in the project")
            return {"CANCELLED"}
        job = ImportJob(path, self.quality, cache_root())
        if job.cached:
            self._job = job
            return self._finish(context, cached=True)
        job.start()
        self._job = job
        _ACTIVE_JOB = job
        wm = context.window_manager
        if bpy.app.background or context.window is None:  # no UI: wait for the job
            import time
            while not job.poll():
                time.sleep(0.2)
            return self._finish(context)
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        context.scene.fresing.last_message = "Import started"
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC" and event.value == "PRESS":
            self._job.cancel()
            self._cleanup(context)
            self.report({"WARNING"}, "Import cancelled")
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        try:
            finished = self._job.poll()
        except Exception as exc:   # never leave a stuck modal operator behind
            self._job.error = self._job.error or str(exc)
            self._job.done = True
            finished = True
        msg = f"Importing {os.path.basename(self._job.step_path)}: {self._job.message} ({self._job.pct:.0f}%) - Esc to cancel"
        context.workspace.status_text_set(msg)
        context.scene.fresing.last_message = msg
        if not finished:
            return {"PASS_THROUGH"}
        self._cleanup(context)
        return self._finish(context)

    def _finish(self, context, cached: bool = False):
        job = self._job
        s = context.scene.fresing
        if job.error:
            self.report({"ERROR"}, f"Import failed: {job.error}")
            s.last_message = f"Import failed: {job.error}"
            return {"CANCELLED"}
        old_root = bpy.data.objects.get(self.update_root) if self.update_root else None
        if old_root is not None:
            from . import reimport
            res = reimport.update_model(context, old_root, job.cache_dir)
            res["root"]["fr_quality"] = self.quality
            s.last_message = s.report_title
            self.report({"INFO"}, s.last_message)
            return {"FINISHED"}
        root = finish_import(context, job.cache_dir, self.up_axis)
        root["fr_quality"] = self.quality
        s.last_message = f"Imported {os.path.basename(job.step_path)}" + (
            " (from cache: file unchanged since last import)" if cached else "")
        self.report({"INFO"}, s.last_message)
        return {"FINISHED"}

    def _cleanup(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "quality")
        layout.prop(self, "up_axis")


class FRESING_FH_step(bpy.types.FileHandler):
    bl_idname = "FRESING_FH_step"
    bl_label = "Fresing STEP import"
    bl_import_operator = "fresing.import_step"
    bl_file_extensions = ".step;.stp"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type in ("VIEW_3D", "OUTLINER")


class FRESING_OT_clear_cache(bpy.types.Operator):
    """Delete cached imports (they are rebuilt the next time a file is imported)"""

    bl_idname = "fresing.clear_cache"
    bl_label = "Clear import cache"

    def execute(self, context):
        import shutil
        if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
            self.report({"WARNING"}, "Wait until the import has finished")
            return {"CANCELLED"}
        root = cache_root()
        n = 0
        for name in os.listdir(root):
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)
            n += 1
        self.report({"INFO"}, f"Removed {n} cached imports")
        return {"FINISHED"}


def cancel_running_job(*_args) -> None:
    """Stop a running import (file closed, new file opened, Blender quitting)."""
    if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
        _ACTIVE_JOB.cancel()


CLASSES = (FRESING_OT_import_step, FRESING_FH_step, FRESING_OT_clear_cache)
