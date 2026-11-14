"""Import operators: STEP file (or a mesh model, task 0117) -> background reader -> Blender objects."""

from __future__ import annotations

import os

import bpy
from bpy.props import CollectionProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..importer.runner import ImportJob
from ..core.words import plural
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
    if template and not s.rule_set and len(s.rules) == 0:     # a new project: the template sets it up
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
        try:                                  # 0055: stored imports of older cache versions are never used again
            from ..importer.runner import prune_old_caches
            prune_old_caches(cache_root())
        except Exception as exc:
            print("Fresing Render: pruning old caches failed:", exc)
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
            try:
                res = reimport.update_model(context, old_root, job.cache_dir)
            except reimport.UpdateFailed as exc:          # the project is as it was (task 0052)
                s.last_message = f"Model update failed: {exc}"
                self.report({"ERROR"}, s.last_message)
                return {"CANCELLED"}
            res["root"]["fr_quality"] = self.quality
            s.last_message = s.report_title
            self.report({"INFO"}, s.last_message)
            return {"FINISHED"}
        root = finish_import(context, job.cache_dir, self.up_axis)
        root["fr_quality"] = self.quality
        s.last_message = f"Imported {os.path.basename(job.step_path)}" + (
            " (from cache: file unchanged since last import)" if cached else "")
        self.report({"INFO"}, s.last_message)
        from . import rule_sets
        notice = rule_sets.take_notice()           # e.g. the default rule set is not in the library
        if notice:
            s.last_message += f". {notice}"
            self.report({"WARNING"}, notice)
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


# ---------------------------------------------------------------------------
# mesh models: glTF / GLB, OBJ, FBX (task 0117)
# ---------------------------------------------------------------------------

MESH_GLOB = "*.glb;*.gltf;*.obj;*.fbx;*.GLB;*.GLTF;*.OBJ;*.FBX"


def converter() -> str:
    """The program that reads FBX (and compressed glTF) for the mesh reader: this Blender, run in the background;
    Blender as a Python module (tests): this Python, which has bpy."""
    import sys
    exe = bpy.app.binary_path or ""
    if exe and os.path.basename(exe).lower().startswith("blender") and os.path.isfile(exe):
        return exe
    return sys.executable


class FRESING_OT_import_mesh(bpy.types.Operator, ImportHelper):
    """Import a mesh model (glTF / GLB, OBJ or FBX, e.g. a model downloaded from Sketchfab): it is read in the
    background and comes in like a STEP model – parts, groups and looks, round faces to click for joints"""

    bl_idname = "fresing.import_mesh"
    bl_label = "Import mesh model"
    bl_options = {"UNDO"}

    filename_ext = ".glb"
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE", "HIDDEN"})
    filter_glob: StringProperty(default=MESH_GLOB, options={"HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"})
    units: EnumProperty(
        name="Units", default="auto",
        description="The length of one unit in the file. glTF is always in metres and FBX says its own units; an OBJ "
                    "file does not, so pick them here (Auto guesses from the model's size and says what it guessed)",
        items=[("auto", "Auto", "glTF and FBX: as the file says. OBJ: millimetres when the model is 500 units or "
                                "more across, else metres"),
               ("m", "Metres", "One unit is a metre"), ("cm", "Centimetres", "One unit is a centimetre"),
               ("mm", "Millimetres", "One unit is a millimetre"), ("in", "Inches", "One unit is an inch"),
               ("ft", "Feet", "One unit is a foot")])
    up_axis: EnumProperty(
        name="Up axis", default="auto",
        description="Which axis points up in the file. glTF and FBX say it themselves; most OBJ files are Y up",
        items=[("auto", "Auto", "glTF and FBX as the file says; OBJ Y up"), ("y", "Y up", "The file's Y axis is up"),
               ("z", "Z up", "The file's Z axis is up (as in the app)")])
    split: EnumProperty(
        name="Split by loose parts", default="auto",
        description="Make every separate piece of a mesh a part of its own, so it can be moved and given a look. "
                    "Use it for a model that comes as one big mesh",
        items=[("auto", "Auto", "On when the file has fewer than 5 meshes (one big mesh), off otherwise"),
               ("on", "On", "Every loose piece becomes a part"),
               ("off", "Off", "Each mesh of the file stays one part")])
    update_root: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if properties.update_root:
            return ("Read a new revision of this mesh model's file. Parts are matched with the old ones by their "
                    "names (a renamed part by its place and shape) and keep their groups, painted faces, joints, "
                    "poses and scenes; a report lists what is new, renamed or missing")
        return " ".join(cls.__doc__.split())

    _timer = None
    _job: ImportJob | None = None

    def invoke(self, context, event):
        root = bpy.data.objects.get(self.update_root) if self.update_root else None
        if root is not None:
            from . import mesh_import
            opts = mesh_import.options(root)
            self.units = opts.get("units", "auto") if opts.get("format") == "obj" else "auto"
            self.up_axis = opts.get("up", "auto") if opts.get("format") == "obj" else "auto"
            self.split = "on" if opts.get("split") else "off"
            src = root.get(build.PROP_SOURCE, "")
            if src:
                self.filepath = src
        if self.directory and self.files and self.files[0].name:   # drag & drop
            if len(self.files) > 1:
                self.report({"WARNING"}, "Several files dropped: importing the first one")
            return self.execute(context)
        return ImportHelper.invoke(self, context, event)

    _path = FRESING_OT_import_step._path
    modal = FRESING_OT_import_step.modal
    _cleanup = FRESING_OT_import_step._cleanup

    def execute(self, context):
        global _ACTIVE_JOB
        path = self._path()
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"File not found: {path}")
            return {"CANCELLED"}
        from ..importer.runner import is_mesh
        if not is_mesh(path):
            self.report({"ERROR"}, "Not a mesh file: glTF (.glb, .gltf), OBJ and FBX can be read here "
                                   "(STEP files with Import STEP)")
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
        try:
            from ..importer.runner import prune_old_caches
            prune_old_caches(cache_root())
        except Exception as exc:
            print("Fresing Render: pruning old caches failed:", exc)
        job = ImportJob(path, "mesh", cache_root(), {"units": self.units, "up": self.up_axis, "split": self.split},
                        converter=converter())
        self._job = job
        if job.cached:
            return self._finish(context, cached=True)
        job.start()
        _ACTIVE_JOB = job
        wm = context.window_manager
        if bpy.app.background or context.window is None:
            import time
            while not job.poll():
                time.sleep(0.2)
            return self._finish(context)
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        context.scene.fresing.last_message = "Import started"
        return {"RUNNING_MODAL"}

    def _finish(self, context, cached: bool = False):
        from . import mesh_import
        job = self._job
        s = context.scene.fresing
        if job.error:
            self.report({"ERROR"}, f"Import failed: {job.error}")
            s.last_message = f"Import failed: {job.error}"
            return {"CANCELLED"}
        before = {g.name for g in s.groups}
        old_root = bpy.data.objects.get(self.update_root) if self.update_root else None
        if old_root is not None:
            from . import reimport
            try:
                res = reimport.update_model(context, old_root, job.cache_dir)
            except reimport.UpdateFailed as exc:
                s.last_message = f"Model update failed: {exc}"
                self.report({"ERROR"}, s.last_message)
                return {"CANCELLED"}
            mesh_import.start_from_file(context.scene, before)
            mesh_import.write_credits(context.scene)
            s.last_message = s.report_title
            self.report({"INFO"}, s.last_message)
            return {"FINISHED"}
        root = finish_import(context, job.cache_dir, "Z")
        root["fr_quality"] = "mesh"
        mesh_import.start_from_file(context.scene, before)
        mesh_import.write_credits(context.scene)
        s.last_message = f"Imported {os.path.basename(job.step_path)}" + (
            " (from cache: file unchanged since last import)" if cached else "")
        notes = mesh_import.notes(root)
        if notes:
            s.last_message += ". " + "; ".join(notes)
        self.report({"INFO"}, s.last_message)
        from . import rule_sets
        notice = rule_sets.take_notice()
        if notice:
            s.last_message += f". {notice}"
            self.report({"WARNING"}, notice)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "units")
        layout.prop(self, "up_axis")
        layout.prop(self, "split")


class FRESING_FH_mesh(bpy.types.FileHandler):
    bl_idname = "FRESING_FH_mesh"
    bl_label = "Fresing mesh model import"
    bl_import_operator = "fresing.import_mesh"
    bl_file_extensions = ".glb;.gltf;.obj;.fbx"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type in ("VIEW_3D", "OUTLINER")


def menu_import(self, context):
    self.layout.operator(FRESING_OT_import_mesh.bl_idname, text="Mesh model (glTF, OBJ, FBX)…")


def register_menu() -> None:
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister_menu() -> None:
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    except (ValueError, RuntimeError):
        pass


class FRESING_OT_clear_cache(bpy.types.Operator):
    """Deletes the stored copies of earlier imports to free disk space. The next import of a file reads it
    in full again"""

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
        self.report({"INFO"}, f"Removed {plural(n, 'stored import')}")
        return {"FINISHED"}


def cancel_running_job(*_args) -> None:
    """Stop a running import (file closed, new file opened, Blender quitting)."""
    if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
        _ACTIVE_JOB.cancel()


CLASSES = (FRESING_OT_import_step, FRESING_FH_step, FRESING_OT_import_mesh, FRESING_FH_mesh, FRESING_OT_clear_cache)
