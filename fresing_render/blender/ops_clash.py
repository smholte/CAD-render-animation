"""Operators of 6 Animation > Clash check (task 0065)."""

from __future__ import annotations

import time

import bpy
from bpy.props import IntProperty

from . import longjob
from . import clash

TICK = 0.12                    # s of checking between two redraws of the panel


def _redraw(context) -> None:
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type in ("VIEW_3D", "TIMELINE", "DOPESHEET_EDITOR"):
                area.tag_redraw()


class FRESING_OT_clash_check(bpy.types.Operator):
    """Goes through the built animation and lists every two parts that run into each other, with the frames and
    how deep. Parts that move together and parts that touch in the CAD model are left alone. Click a row of the list
    to see the clash"""

    bl_idname = "fresing.clash_check"
    bl_label = "Check for clashes"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None
    _gen = None
    _run = None

    @classmethod
    def poll(cls, context):
        return context.scene is not None and not clash.runtime(context.scene).get("running")

    def _finish(self, context) -> set:
        scene = context.scene
        run = self._run
        if not clash.save(scene, run):
            scene.fresing.last_message = clash.STALE_RUN
            self.report({"WARNING"}, clash.STALE_RUN)
            return {"CANCELLED"}
        st = clash.state(scene)
        secs = run.stats.get("seconds", 0.0)
        msg = (f"Clash check: {st['text'].lower() if st['clashes'] else st['text']} in "
               f"'{scene.fresing.clash.anim}' ({secs:.1f} s)")
        scene.fresing.last_message = msg
        self.report({"WARNING"} if st["clashes"] else {"INFO"}, msg)
        return {"FINISHED"}

    def execute(self, context):
        try:
            self._run = clash.Check(context.scene)
            for _p in self._run.steps():
                pass
        except clash.ClashError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        return self._finish(context)

    def invoke(self, context, event):
        scene = context.scene
        try:
            self._run = clash.Check(scene)
            self._gen = self._run.steps()
            next(self._gen)                     # the set-up: a missing build shows at once
        except clash.ClashError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        rt = clash.runtime(scene)
        rt.update(running=True, cancel=False, progress=0.0)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop(self, context) -> None:
        rt = clash.runtime(context.scene)
        rt["running"] = False
        rt.pop("progress", None)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        _redraw(context)

    def modal(self, context, event):
        rt = clash.runtime(context.scene)
        if longjob.swallow_undo(self, context, event, "clash check"):   # bug hunt 0118 row 13
            return {"RUNNING_MODAL"}
        if event.type == "ESC" or rt.get("cancel"):
            self._gen.close()
            self._stop(context)
            context.scene.fresing.last_message = "Clash check cancelled"
            self.report({"INFO"}, "Clash check cancelled")
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        t0 = time.perf_counter()
        try:
            while time.perf_counter() - t0 < TICK:
                rt["progress"] = next(self._gen)
        except StopIteration:
            self._stop(context)
            return self._finish(context)
        except Exception as exc:  # noqa: BLE001 - say what went wrong, never leave the panel "running"
            self._stop(context)
            self.report({"ERROR"}, f"Clash check failed: {exc}")
            return {"CANCELLED"}
        _redraw(context)
        return {"RUNNING_MODAL"}


class FRESING_OT_clash_cancel(bpy.types.Operator):
    """Stops the clash check that is running. The list keeps the result of the check before"""

    bl_idname = "fresing.clash_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        clash.runtime(context.scene)["cancel"] = True
        return {"FINISHED"}


class FRESING_OT_clash_show(bpy.types.Operator):
    """Goes to the moment the two parts of the selected row are deepest in each other, selects them, shows them red
    and zooms the view to them"""

    bl_idname = "fresing.clash_show"
    bl_label = "Show clash"
    bl_options = {"REGISTER"}

    index: IntProperty(default=-1, options={"SKIP_SAVE"})

    def execute(self, context):
        c = clash.settings(context.scene)
        i = self.index if self.index >= 0 else c.rows_index
        msg = clash.show_row(context, context.scene, i)
        if msg:
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_clash_red_off(bpy.types.Operator):
    """Takes the red off the two parts (it is only drawn in the 3D view: their materials never change)"""

    bl_idname = "fresing.clash_red_off"
    bl_label = "No red"

    def execute(self, context):
        clash.hide_red()
        return {"FINISHED"}


class FRESING_OT_clash_clear(bpy.types.Operator):
    """Forgets the result of the clash check: empties the list and removes its markers from the time line"""

    bl_idname = "fresing.clash_clear"
    bl_label = "Clear the result"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        clash.clear(context.scene)
        return {"FINISHED"}


CLASSES = (FRESING_OT_clash_check, FRESING_OT_clash_cancel, FRESING_OT_clash_show, FRESING_OT_clash_red_off,
           FRESING_OT_clash_clear)
