"""Operators for a house from House Planner (task 0114): File > Import > House Planner scene, Preview a moment,
Bake and export (progress + Cancel), Show the package in Explorer."""

from __future__ import annotations

import os
import time

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..core import house_scene as hs
from ..core import words
from . import longjob
from . import files, house_bake, house_import

TICK = 0.1                     # s of work between two redraws of the panel
_RUN: dict = {}
# task 0217: called when a bake ends – f(scene, outcome, info, filepath); outcome "done" (info = HouseBake.result),
# "cancelled" (info = None) or "failed" (info = the message). The Toolbox inbox sends the package back from here.
ENDED: list = []


def _ended(scene, outcome: str, info, filepath: str) -> None:
    for f in list(ENDED):
        try:
            f(scene, outcome, info, filepath)
        except Exception as exc:  # noqa: BLE001 - a listener never breaks the bake's own ending
            print("Fresing Render: after the house bake:", exc)


def runtime(scene) -> dict:
    return _RUN.setdefault(scene.name, {})


def _redraw(context) -> None:
    wm = getattr(context, "window_manager", None)
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            area.tag_redraw()


class FRESING_OT_house_import(bpy.types.Operator, ImportHelper):
    """Brings in a house exported from House Planner (.hpscene): the house with its light-map layout, the moments
    to bake (morning, evening, night …), the seasons and the photos it asks for. Importing again replaces the
    house. Then use 5 Scene & Render > House from House Planner"""

    bl_idname = "fresing.house_import"
    bl_label = "Import House Planner scene"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = house_import.EXT
    filter_glob: StringProperty(default="*.hpscene", options={"HIDDEN"})

    def execute(self, context):
        try:
            out = house_import.import_scene(context.scene, self.filepath)
        except hs.FormatError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:  # noqa: BLE001 - say what went wrong
            self.report({"ERROR"}, f"The house could not be imported: {exc}")
            return {"CANCELLED"}
        h = out["house"]
        msg = (f"House imported: {h.title or h.id} – {words.plural(len(h.surfaces), 'surface')}, "
               f"{words.plural(len(h.recipe.moments), 'moment')} to bake")
        context.scene.fresing.last_message = msg
        for note in out["notes"]:
            self.report({"WARNING"}, note)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class FRESING_OT_house_preview(bpy.types.Operator):
    """Shows this moment in the view: its sun and sky (the weather and time of day), the season's wet and snow look,
    the lamps it switches on and bare trees in winter. Switch the view to Rendered to see the light"""

    bl_idname = "fresing.house_preview"
    bl_label = "Preview a moment"
    bl_options = {"REGISTER", "UNDO"}

    moment: StringProperty(name="Moment", description="The id of the moment to show")

    @classmethod
    def poll(cls, context):
        return house_import.has_house(context.scene) and not runtime(context.scene).get("running")

    def execute(self, context):
        try:
            text = house_import.preview(context.scene, self.moment)
        except Exception as exc:  # noqa: BLE001 - say what went wrong
            self.report({"ERROR"}, f"The moment could not be shown: {exc}")
            return {"CANCELLED"}
        if not text:
            self.report({"WARNING"}, f"The house has no moment '{self.moment}'")
            return {"CANCELLED"}
        self.report({"INFO"}, text)
        return {"FINISHED"}


def _done(scene, out: dict) -> str:
    h = house_import.settings(scene)
    h.last_bake = out["path"]
    h.last_seconds = float(out["seconds"])
    h.last_problems = "\n".join(out["problems"])
    size = os.path.getsize(out["path"]) if os.path.exists(out["path"]) else 0
    h.last_text = (f"{words.plural(out['moments'], 'moment')} baked in {out['seconds'] / 60:.1f} min, "
                   f"{size / 2**20:.1f} MB")
    msg = f"Bake package saved: {os.path.basename(out['path'])} ({h.last_text})"
    scene.fresing.last_message = msg
    return msg


def bake_options(scene, samples: int = 0, photo_samples: int = 0, quick: bool = False) -> dict:
    """HouseBake's keywords (task 0217): 0 = the recipe's samples; ``quick`` = the first moment only, no photo or video
    (tests, the PC check, the test tour)."""
    kw = {"samples": samples or None, "photo_samples": photo_samples or None}
    if quick:
        from . import house_import
        moments = house_import.house(scene).recipe.moments
        kw.update(moments=[moments[0].id] if moments else [], photos=False, videos=False)
    return kw


def run_at_once(job) -> str:
    """The bake without a window (scripts, background, the Toolbox inbox in Blender as a module): all of it now, the
    end told to ``ENDED`` as the modal tells it. Raises with the message when it fails."""
    try:
        out = job.run()
    except Exception as exc:  # noqa: BLE001
        _ended(job.scene, "failed", f"The bake failed: {exc}", job.path)
        raise RuntimeError(f"The bake failed: {exc}") from exc
    msg = _done(job.scene, out)
    _ended(job.scene, "done", out, job.path)
    return msg


class FRESING_OT_house_bake(bpy.types.Operator):
    """Bakes the light of every moment the house asks for (sun, sky, lamps, snow) with Cycles, renders its photos
    and videos, and saves it all as one bake package (.hpbake) next to the project. Open that file in House Planner.
    The project itself does not change; Cancel stops it without writing a file"""

    bl_idname = "fresing.house_bake"
    bl_label = "Bake and export"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE", "HIDDEN"})
    # task 0217: the samples of the light and of the photos (0 = the recipe's); tests and the PC check bake small
    samples: IntProperty(default=0, min=0, options={"SKIP_SAVE", "HIDDEN"})
    photo_samples: IntProperty(default=0, min=0, options={"SKIP_SAVE", "HIDDEN"})
    quick: BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})     # the first moment only, no photo / video

    _timer = None
    _gen = None
    _job = None

    @classmethod
    def poll(cls, context):
        return house_import.has_house(context.scene) and not runtime(context.scene).get("running")

    def execute(self, context):
        scene = context.scene
        try:
            self._job = house_bake.HouseBake(scene, self.filepath or None, **bake_options(
                scene, self.samples, self.photo_samples, self.quick))
        except Exception as exc:  # noqa: BLE001 - say what went wrong
            self.report({"ERROR"}, f"The bake could not start: {exc}")
            _ended(scene, "failed", f"The bake could not start: {exc}", self.filepath)
            return {"CANCELLED"}
        if context.window is None:                      # scripts, background: at once
            try:
                msg = run_at_once(self._job)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, msg)
            return {"FINISHED"}
        self._gen = self._job.steps()
        rt = runtime(scene)
        rt.update(running=True, cancel=False, progress=0.0, text="Starting", t0=time.time())
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop(self, context) -> None:
        rt = runtime(context.scene)
        rt["running"] = False
        rt.pop("progress", None)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _redraw(context)

    def modal(self, context, event):
        rt = runtime(context.scene)
        if longjob.swallow_undo(self, context, event, "house bake"):   # bug hunt 0118 row 13
            return {"RUNNING_MODAL"}
        if event.type == "ESC" or rt.get("cancel"):
            self._gen.close()                           # puts the project back (HouseBake's finally)
            self._stop(context)
            context.scene.fresing.last_message = "The house bake was cancelled: no file was written"
            self.report({"INFO"}, "House bake cancelled")
            _ended(self._job.scene, "cancelled", None, self._job.path)
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        t0 = time.perf_counter()
        try:
            while time.perf_counter() - t0 < TICK:
                rt["progress"] = next(self._gen)
                rt["text"] = self._job.text
        except StopIteration:
            self._stop(context)
            self.report({"INFO"}, _done(context.scene, self._job.result))
            _ended(self._job.scene, "done", self._job.result, self._job.path)
            return {"FINISHED"}
        except Exception as exc:  # noqa: BLE001 - never leave the panel "running"
            self._gen.close()
            self._stop(context)
            self.report({"ERROR"}, f"The house bake failed: {exc}")
            _ended(self._job.scene, "failed", f"The house bake failed: {exc}", self._job.path)
            return {"CANCELLED"}
        _redraw(context)
        return {"RUNNING_MODAL"}


class FRESING_OT_house_cancel(bpy.types.Operator):
    """Stops the house bake. No file is written; the project does not change"""

    bl_idname = "fresing.house_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        runtime(context.scene)["cancel"] = True
        return {"FINISHED"}


class FRESING_OT_house_show(bpy.types.Operator):
    """Opens the folder of the last bake package in Explorer, with the file selected – to send it to House
    Planner"""

    bl_idname = "fresing.house_show"
    bl_label = "Show in folder"

    @classmethod
    def poll(cls, context):
        p = house_import.settings(context.scene).last_bake
        return bool(p) and os.path.exists(p)

    def execute(self, context):
        files.show_in_folder(house_import.settings(context.scene).last_bake)
        return {"FINISHED"}


def menu_import(self, context):
    self.layout.operator(FRESING_OT_house_import.bl_idname, text="House Planner scene (.hpscene)…")


CLASSES = (FRESING_OT_house_import, FRESING_OT_house_preview, FRESING_OT_house_bake, FRESING_OT_house_cancel,
           FRESING_OT_house_show)


def register_menu() -> None:
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister_menu() -> None:
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    except (ValueError, RuntimeError):
        pass
