"""Operators of 5 Scene & Render > Web 3D model (task 0099)."""

from __future__ import annotations

import os
import time

import bpy
from bpy.props import BoolProperty, StringProperty

from . import web3d

TICK = 0.1                     # s of work between two redraws of the panel


def _redraw(context) -> None:
    wm = getattr(context, "window_manager", None)
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            area.tag_redraw()


def _done(scene, out: dict) -> str:
    web3d.remember(scene, out)
    msg = f"Web 3D model saved: {os.path.basename(out['path'])} ({out['text']})"
    scene.fresing.last_message = msg
    return msg


class FRESING_OT_web3d_export(bpy.types.Operator):
    """Saves the machine as it is shown now as one 3D file (.glb) with its looks baked into pictures, and a page
    (.html) that shows it in any web browser: drag to turn, scroll to zoom. Pick where to save; the page is one file
    you can e-mail or put on a website"""

    bl_idname = "fresing.web3d_export"
    bl_label = "Export web 3D model"
    bl_options = {"REGISTER"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default="*.glb", options={"HIDDEN", "SKIP_SAVE"})
    modal_run: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    _timer = None
    _gen = None
    _job = None

    @classmethod
    def poll(cls, context):
        return context.scene is not None and not web3d.runtime(context.scene).get("running")

    @classmethod
    def description(cls, context, props):
        why = web3d.can_export(context.scene) if context is not None and context.scene is not None else ""
        doc = " ".join(cls.__doc__.split())
        return doc + (f". Now: {why}" if why else "")

    def invoke(self, context, event):
        why = web3d.can_export(context.scene)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        self.modal_run = True
        self.filepath = web3d.settings(context.scene).last_path or web3d.default_path(context.scene)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        scene = context.scene
        why = web3d.can_export(scene)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        w = web3d.settings(scene)
        path = self.filepath or web3d.default_path(scene)
        self._job = web3d.Job(scene, path, size=int(w.texture_size), hide_names=w.hide_names,
                              animation=w.animation)
        if not self.modal_run or context.window is None:
            try:
                out = self._job.run()
            except Exception as exc:  # noqa: BLE001 - say what went wrong
                self.report({"ERROR"}, f"The web 3D model could not be saved: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, _done(scene, out))
            return {"FINISHED"}
        self._gen = self._job.steps()
        rt = web3d.runtime(scene)
        rt.update(running=True, cancel=False, progress=0.0, text="Starting")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop(self, context) -> None:
        rt = web3d.runtime(context.scene)
        rt["running"] = False
        rt.pop("progress", None)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _redraw(context)

    def modal(self, context, event):
        rt = web3d.runtime(context.scene)
        if event.type == "ESC" or rt.get("cancel"):
            self._gen.close()
            self._stop(context)
            context.scene.fresing.last_message = "The web 3D export was cancelled: no file was written"
            self.report({"INFO"}, "Web 3D export cancelled")
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
            try:
                out = self._job.finish()
            except Exception as exc:  # noqa: BLE001 - say what went wrong
                self.report({"ERROR"}, f"The web 3D model could not be written: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, _done(context.scene, out))
            return {"FINISHED"}
        except Exception as exc:  # noqa: BLE001 - never leave the panel "running"
            self._gen.close()
            self._stop(context)
            self.report({"ERROR"}, f"The web 3D export failed: {exc}")
            return {"CANCELLED"}
        _redraw(context)
        return {"RUNNING_MODAL"}


class FRESING_OT_web3d_cancel(bpy.types.Operator):
    """Stops the web 3D export. No file is written; the project does not change"""

    bl_idname = "fresing.web3d_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        web3d.runtime(context.scene)["cancel"] = True
        return {"FINISHED"}


CLASSES = (FRESING_OT_web3d_export, FRESING_OT_web3d_cancel)
