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
    if _ROOT_OVERRIDE:
        os.makedirs(_ROOT_OVERRIDE[0], exist_ok=True)
        return _ROOT_OVERRIDE[0]
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
    from . import weld_cad
    weld_cad.after_import(scene, root)             # task 0323: solid weld beads in the file become welds
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
    try:
        from . import surroundings
        surroundings.fix_view_clip(scene)      # task 0193: the sea and park reach further than the model
    except Exception:
        pass


def _locked(op) -> bool:
    """The Client view lets a model in but never replaces one: a model update is a change of the project."""
    from . import lock
    if not lock.ON[0]:
        return False
    op.report({"WARNING"}, lock.MESSAGE)
    return True


PANEL = "FRESING_PT_import"
_ROOT_OVERRIDE: list = []      # tests: a cache folder of their own (``use_cache_root``)


def use_cache_root(path: str | None) -> None:
    """Tests: keep the stored imports in ``path`` (None: the app's own folder again)."""
    _ROOT_OVERRIDE[:] = [path] if path else []


def show_import_panel(context) -> None:
    """A drop (or Import again) shows what the Import STEP… button shows (task 0289): 1 Import opened in the side
    panel, the section tab on All when another section's tab was chosen, the side panel shown on the Fresing tab."""
    from . import panels
    panels.open_to(PANEL)
    sec = panels.tab_section()
    if sec and sec != PANEL:
        panels._TAB["v"] = "ALL"
        wm = getattr(context, "window_manager", None)
        if wm is not None and getattr(wm, "fresing_tab", "ALL") != "ALL":
            wm.fresing_tab = "ALL"
    if bpy.app.background:
        return
    from . import editors
    if not editors.settled():                 # never set a 3D view's settings before it was drawn (CLAUDE.md 8)
        return
    win = getattr(context, "window", None)
    if win is None or panels.side_window(win):
        return
    for area in win.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        try:
            if not space.show_region_ui:
                space.show_region_ui = True
            for region in area.regions:
                if region.type == "UI":
                    try:
                        region.active_panel_category = panels.CATEGORY
                    except (TypeError, AttributeError, ValueError):
                        pass
        except (AttributeError, RuntimeError):
            pass
        area.tag_redraw()


def _redraw_panel() -> None:
    try:
        from . import panels
        panels.redraw()
    except Exception:  # noqa: BLE001 – a redraw never stops an import
        pass


class _Stored:
    """Stands in for an ImportJob when Import again takes a stored import as it is (nothing to read)."""

    def __init__(self, entry):
        self.cache_dir = entry.folder
        self.step_path = entry.source or entry.name
        self.error = None
        self.done = True


def _again_entry(op):
    from ..core import import_cache
    e = import_cache.find(cache_root(), op.again)
    if e is None:
        op.report({"WARNING"}, "That stored import is no longer in the cache")
    elif e.state == import_cache.OLD:
        op.report({"ERROR"}, "That stored import was made by an older version of the app: import the file itself")
        e = None
    return e


AGAIN_TIP = ("Import this model again into this project. An unchanged file comes from the stored copy in seconds, "
             "a changed file is read again; a file that was moved comes from the stored copy")


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
    # task 0289: Import again – the folder name of a stored import (the Imported models fold)
    again: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if properties.again:
            return AGAIN_TIP
        if properties.update_root:
            return ("Read a new revision of this model's STEP file. Parts are matched with the old ones and keep "
                    "their groups, painted faces, joints, poses and scenes; a report lists what is new or missing")
        return cls.__doc__.replace("\n    ", " ")

    _timer = None
    _job: ImportJob | None = None

    def invoke(self, context, event):
        if self.update_root and _locked(self):
            return {"CANCELLED"}
        s = context.scene.fresing
        self.quality = s.import_quality
        self.up_axis = s.import_up_axis
        if self.again:                                              # task 0289: the Imported models fold
            return self.execute(context)
        if self.directory and self.files and self.files[0].name:   # drag & drop: as the button (task 0289)
            return _dropped(self, context)
        root = bpy.data.objects.get(self.update_root) if self.update_root else None
        if root is not None:
            src = root.get(build.PROP_SOURCE, "")
            self.quality = root.get("fr_quality", self.quality)
            if src:
                self.filepath = src            # the file browser opens on the current file
        elif not self.filepath:                # task 0272: opens in the first STEP models folder (all on its left)
            from . import locations
            first = locations.first_path("step")
            if first:
                self.filepath = os.path.join(first, "")
        return ImportHelper.invoke(self, context, event)

    _note = ""

    def _path(self) -> str:
        if self.again and self.filepath:
            return self.filepath
        if self.files and self.directory and self.files[0].name:
            return os.path.join(self.directory, self.files[0].name)
        return self.filepath

    def execute(self, context):
        if self.update_root and _locked(self):
            return {"CANCELLED"}
        global _ACTIVE_JOB
        self._note = ""
        if self.again:
            entry = _again_entry(self)
            if entry is None:
                return {"CANCELLED"}
            if _busy(self):
                return {"CANCELLED"}
            show_import_panel(context)
            if entry.state != "changed":                 # unchanged or moved: the stored copy, nothing is read
                self._job = _Stored(entry)
                self.quality = entry.quality if entry.quality in ("draft", "normal", "fine") else self.quality
                if entry.state == "moved":
                    self._note = " (from the stored copy: the file was moved)"
                return self._finish(context, cached=True)
            self.filepath = entry.source
            self.quality = entry.quality if entry.quality in ("draft", "normal", "fine") else self.quality
            self._note = " (the file had changed since it was stored: read again)"
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
        reuse = None
        if self.update_root:                  # task 0324: unchanged parts' meshes come from the old revision's cache
            from ..importer.runner import reuse_dir_for
            old = bpy.data.objects.get(self.update_root)
            reuse = reuse_dir_for(str(old.get("fr_cache", "") or ""), self.quality) if old is not None else None
        job = ImportJob(path, self.quality, cache_root(), reuse=reuse)
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
        _redraw_panel()
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
            _redraw_panel()
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
            _redraw_panel()
            return {"FINISHED"}
        root = finish_import(context, job.cache_dir, self.up_axis)
        root["fr_quality"] = self.quality
        s.last_message = f"Imported {os.path.basename(job.step_path)}" + (
            self._note or (" (from cache: file unchanged since last import)" if cached else ""))
        _redraw_panel()
        self.report({"INFO"}, s.last_message)
        from . import rule_sets
        notice = rule_sets.take_notice()           # e.g. the default rule set is not in the library
        if notice:
            s.last_message += f". {notice}"
            self.report({"WARNING"}, notice)
        from . import weld_cad
        found = weld_cad.take_notice()             # task 0323: "6 welds from the CAD file …"
        if found:
            s.last_message += f". {found}"
            self.report({"INFO"}, found)
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


def _busy(op) -> bool:
    if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
        try:
            _ACTIVE_JOB.poll()
        except Exception:
            _ACTIVE_JOB.done = True
        if not _ACTIVE_JOB.done:
            op.report({"WARNING"}, "An import is already running")
            return True
    return False


def _dropped(op, context):
    """A file dropped on the 3D view or the Outliner (task 0289): the same as Import STEP… – 1 Import opens, the
    panel's Detail and Up axis are used, the progress with Esc to cancel, the model's line, the same message and the
    same undo step. Several files at once: the first one is imported, and the panel says so."""
    show_import_panel(context)
    names = [f.name for f in op.files if f.name]
    res = op.execute(context)
    if len(names) > 1:
        note = (f"{plural(len(names), 'file')} dropped: {names[0]} is imported – drop the others one at a time, "
                "after this one is in")
        op.report({"WARNING"}, note)
        s = context.scene.fresing
        s.last_message = (s.last_message + ". " if s.last_message else "") + note
        _redraw_panel()
    return res


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
    from .. import winexe
    if exe and winexe.is_blender_program(exe) and os.path.isfile(exe):
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
    again: StringProperty(options={"SKIP_SAVE", "HIDDEN"})        # task 0289, as Import STEP's
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
        if properties.again:
            return AGAIN_TIP
        if properties.update_root:
            return ("Read a new revision of this mesh model's file. Parts are matched with the old ones by their "
                    "names (a renamed part by its place and shape) and keep their groups, painted faces, joints, "
                    "poses and scenes; a report lists what is new, renamed or missing")
        return " ".join(cls.__doc__.split())

    _timer = None
    _job: ImportJob | None = None

    def invoke(self, context, event):
        if self.update_root and _locked(self):
            return {"CANCELLED"}
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
        if self.again:
            return self.execute(context)
        if self.directory and self.files and self.files[0].name:   # drag & drop: as the button (task 0289)
            return _dropped(self, context)
        return ImportHelper.invoke(self, context, event)

    _note = ""
    _path = FRESING_OT_import_step._path
    modal = FRESING_OT_import_step.modal
    _cleanup = FRESING_OT_import_step._cleanup

    def execute(self, context):
        if self.update_root and _locked(self):
            return {"CANCELLED"}
        global _ACTIVE_JOB
        self._note = ""
        if self.again:
            entry = _again_entry(self)
            if entry is None:
                return {"CANCELLED"}
            if _busy(self):
                return {"CANCELLED"}
            show_import_panel(context)
            if entry.state != "changed":
                self._job = _Stored(entry)
                if entry.state == "moved":
                    self._note = " (from the stored copy: the file was moved)"
                return self._finish(context, cached=True)
            self.filepath = entry.source            # read again with the choices it was read with
            opts = entry.options
            self.units = opts.get("units", "auto") if opts.get("units") in ("m", "cm", "mm", "in", "ft") else "auto"
            self.up_axis = opts.get("up", "auto") if opts.get("up") in ("y", "z") else "auto"
            self.split = "on" if opts.get("split") else "off"
            self._note = " (the file had changed since it was stored: read again)"
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
            self._note or (" (from cache: file unchanged since last import)" if cached else ""))
        _redraw_panel()
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
    """Clears the stored copies of earlier imports to free disk space. The next import of a file reads it
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


class FRESING_OT_cache_remove(bpy.types.Operator):
    """Removes this stored import from the cache to free its disk space (asks first). Models already in a project
    stay as they are; the next import of the file reads it in full again"""

    bl_idname = "fresing.cache_remove"
    bl_label = "Remove from cache"

    entry: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        from ..core import import_cache
        e = import_cache.find(cache_root(), self.entry)
        if e is None:
            self.report({"WARNING"}, "That stored import is no longer in the cache")
            return {"CANCELLED"}
        return context.window_manager.invoke_confirm(
            self, event, title=f"Remove {e.name} from the cache?",
            message=f"Frees {import_cache.size_text(e.size)}. The next import of this file reads it in full again.",
            confirm_text="Remove")

    def execute(self, context):
        from ..core import import_cache
        if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
            self.report({"WARNING"}, "Wait until the import has finished")
            return {"CANCELLED"}
        e = import_cache.find(cache_root(), self.entry)
        if e is None:
            self.report({"WARNING"}, "That stored import is no longer in the cache")
            return {"CANCELLED"}
        if not import_cache.remove(e, cache_root()):
            self.report({"ERROR"}, f"Could not remove {e.name} from the cache (a file in it is in use?)")
            return {"CANCELLED"}
        msg = f"Removed {e.name} from the cache: {import_cache.size_text(e.size)} freed"
        context.scene.fresing.last_message = msg
        self.report({"INFO"}, msg)
        _redraw_panel()
        return {"FINISHED"}


class FRESING_OT_cache_show(bpy.types.Operator):
    """Shows the model's file in Explorer. When the file was moved, shows the stored copy's folder in the cache
    instead"""

    bl_idname = "fresing.cache_show"
    bl_label = "Show in folder"

    entry: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        from ..core import import_cache
        from . import files
        e = import_cache.find(cache_root(), self.entry)
        if e is None:
            self.report({"WARNING"}, "That stored import is no longer in the cache")
            return {"CANCELLED"}
        path = e.source if e.source and os.path.isfile(e.source) else e.folder
        files.show_in_folder(path)
        return {"FINISHED"}


class FRESING_OT_model_up_axis(bpy.types.Operator):
    """Turns this model so the chosen axis of its file points up, as Up axis does at the import. Joints, cylinders,
    poses, saved scenes and labels keep working; a built animation is taken off: Build again"""

    bl_idname = "fresing.model_up_axis"
    bl_label = "Up axis of this model"
    bl_options = {"REGISTER", "UNDO"}

    root: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    axis: EnumProperty(name="Up axis", default="Z",
                       items=[("Z", "Z up", "The file's Z axis points up (most CAD programs, Inventor's default)"),
                              ("Y", "Y up", "The file's Y axis points up (some CAD programs and many mesh models)")])

    @classmethod
    def description(cls, context, properties):
        return ("Turns this model so its file's Z axis points up" if properties.axis == "Z" else
                "Turns this model so its file's Y axis points up") + (
            ", as Up axis does at the import. Joints, poses, saved scenes and labels keep working; a built "
            "animation is taken off: Build again")

    def execute(self, context):
        if _locked(self):
            return {"CANCELLED"}
        scene = context.scene
        root = bpy.data.objects.get(self.root)
        if root is None or root.name not in scene.objects:
            self.report({"ERROR"}, "That model is no longer in the project")
            return {"CANCELLED"}
        if root.get("fr_lifting"):
            self.report({"WARNING"}, "A crane of the lifting plan keeps its own up axis")
            return {"CANCELLED"}
        from . import animation
        built = animation.has_keys(scene)
        if not logic.change_up_axis(scene, root, self.axis):
            return {"CANCELLED"}
        world.apply(scene, scene.fresing)           # floor, lights and surroundings fit the turned model
        frame_views(context, scene)
        msg = f"{root.name}: {self.axis} up"
        if built:
            msg += ". The built animation was taken off: Build again"
        scene.fresing.last_message = msg
        self.report({"INFO"}, msg)
        _redraw_panel()
        return {"FINISHED"}


def cancel_running_job(*_args) -> None:
    """Stop a running import (file closed, new file opened, Blender quitting)."""
    if _ACTIVE_JOB is not None and not _ACTIVE_JOB.done:
        _ACTIVE_JOB.cancel()


CLASSES = (FRESING_OT_import_step, FRESING_FH_step, FRESING_OT_import_mesh, FRESING_FH_mesh, FRESING_OT_clear_cache,
           FRESING_OT_cache_remove, FRESING_OT_cache_show, FRESING_OT_model_up_axis)
