"""Operators of 4 Motion > Milling > Make a toolpath (task 0029)."""

from __future__ import annotations

import time

import bpy
from bpy.props import BoolProperty

from ..core import toolpath as core
from . import toolpath

TICK = 0.1                     # s of work between two redraws of the panel


def _redraw(context) -> None:
    wm = getattr(context, "window_manager", None)
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            area.tag_redraw()


def _done_message(scene, out: dict) -> str:
    msg = f"Toolpath made: {out['moves']:,} moves in {out['seconds']:.1f} s, step in '{out['animation']}'"
    if out.get("undercut"):
        msg += ". " + out["undercut"]
    scene.fresing.last_message = msg
    return msg


class FRESING_OT_toolpath_make(bpy.types.Operator):
    """Works out a roughing and a finishing program that cut the workpiece into the finished part, never into the
    part, writes it next to the project and adds it as a 'Run G-code program' step to the animation shown in 6
    Animation (made again: that step gets the new program). Then press Build animation"""

    bl_idname = "fresing.toolpath_make"
    bl_label = "Make toolpath"
    bl_options = {"REGISTER", "UNDO"}

    modal_run: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    _timer = None
    _gen = None
    _job = None

    @classmethod
    def poll(cls, context):
        return context.scene is not None and not toolpath.runtime(context.scene).get("running")

    def invoke(self, context, event):
        self.modal_run = True
        path = toolpath.edited_by_hand(context.scene)
        if path:
            return context.window_manager.invoke_confirm(
                self, event, title="Replace the program?",
                message=f"The program was changed by hand since the app wrote it ({path}). Making the toolpath "
                        "again writes over it",
                confirm_text="Replace it", icon="WARNING")
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        try:
            self._job = toolpath.Job(scene)
        except (toolpath.NotReady, core.ToolpathError) as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        if not self.modal_run or context.window is None:
            try:
                out = self._job.run()
            except core.ToolpathError as exc:
                self.report({"WARNING"}, str(exc))
                return {"CANCELLED"}
            self.report({"WARNING"} if out.get("undercut") else {"INFO"}, _done_message(scene, out))
            return {"FINISHED"}
        self._gen = self._job.steps()
        rt = toolpath.runtime(scene)
        rt.update(running=True, cancel=False, progress=0.0, text="Starting")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop(self, context) -> None:
        rt = toolpath.runtime(context.scene)
        rt["running"] = False
        rt.pop("progress", None)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _redraw(context)

    def modal(self, context, event):
        rt = toolpath.runtime(context.scene)
        if event.type == "ESC" or rt.get("cancel"):
            self._gen.close()
            self._stop(context)
            context.scene.fresing.last_message = "Making the toolpath was cancelled: nothing changed"
            self.report({"INFO"}, "Making the toolpath was cancelled")
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
                self.report({"ERROR"}, f"The program could not be written: {exc}")
                return {"CANCELLED"}
            self.report({"WARNING"} if out.get("undercut") else {"INFO"}, _done_message(context.scene, out))
            return {"FINISHED"}
        except core.ToolpathError as exc:
            self._stop(context)
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:  # noqa: BLE001 - never leave the panel "running"
            self._stop(context)
            self.report({"ERROR"}, f"Making the toolpath failed: {exc}")
            return {"CANCELLED"}
        _redraw(context)
        return {"RUNNING_MODAL"}


class FRESING_OT_toolpath_cancel(bpy.types.Operator):
    """Stops making the toolpath. Nothing changes: the program and the step stay as they were"""

    bl_idname = "fresing.toolpath_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        toolpath.runtime(context.scene)["cancel"] = True
        return {"FINISHED"}


class FRESING_OT_toolpath_go_step(bpy.types.Operator):
    """Shows the step the toolpath went into in 6 Animation (its animation becomes the one shown)"""

    bl_idname = "fresing.toolpath_go_step"
    bl_label = "Show its step"

    def execute(self, context):
        s = context.scene.fresing
        a, b = toolpath.step(context.scene)
        if a is None:
            self.report({"INFO"}, "No step yet: press Make toolpath")
            return {"CANCELLED"}
        s.animations_index = list(s.animations).index(a)
        a.blocks_index = list(a.blocks).index(b)
        return {"FINISHED"}


CLASSES = (FRESING_OT_toolpath_make, FRESING_OT_toolpath_cancel, FRESING_OT_toolpath_go_step)
