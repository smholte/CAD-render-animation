"""Operators of the coolant liquid on the machine (task 0346): work it out (a long job with progress and Cancel, as
the cables' re-bake of task 0160), stop it."""

from __future__ import annotations

import time

import bpy

from . import liquid


def _redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:                                  # noqa: BLE001
        pass


class FRESING_OT_liquid_bake(bpy.types.Operator):
    """Works out how the coolant collects on the machine for the built animation: it fills the cut pockets, runs
    over the table into the chip tray and down the drain. It starts by itself after Build & play; you can keep
    working meanwhile. Press Cancel (or Esc) to stop it"""

    bl_idname = "fresing.liquid_bake"
    bl_label = "Work out the liquid"
    bl_options = {"REGISTER"}

    _timer = None
    _gen = None

    @classmethod
    def poll(cls, context):
        return context.scene is not None and liquid.wanted(context.scene) and not liquid.running()

    def execute(self, context):
        info = liquid.bake_now(context.scene)
        liquid.show(context.scene)
        if info and "seconds" in info:
            self.report({"INFO"}, f"Liquid worked out in {info['seconds']:.0f} s")
        return {"FINISHED"}

    def invoke(self, context, event):
        scene = context.scene
        if liquid.running():
            return {"CANCELLED"}
        if liquid.is_baked(scene):
            liquid.show(scene)
            return {"FINISHED"}
        self._notes = []
        self._gen = liquid.steps(scene, self._notes)
        liquid._STATE.update(running=True, cancel=False, progress=0.0, scene=scene.name)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        self._status(context)
        return {"RUNNING_MODAL"}

    def _status(self, context, text=None) -> None:
        try:
            context.workspace.status_text_set(
                text if text is not None else
                f"Working out the coolant liquid: {100.0 * liquid.progress():.0f} % – Esc or Cancel to stop")
        except Exception:                              # noqa: BLE001 - (no workspace: no status line)
            pass

    def _stop(self, context) -> None:
        liquid._STATE.update(running=False, cancel=False, progress=0.0)
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        try:
            context.workspace.status_text_set(None)
        except Exception:                              # noqa: BLE001
            pass
        _redraw()

    def modal(self, context, event):
        from . import longjob
        if longjob.swallow_undo(self, context, event, "liquid"):
            return {"RUNNING_MODAL"}
        if event.type == "ESC" or liquid._STATE["cancel"]:
            self._gen.close()                          # (the half-written file is thrown away)
            self._stop(context)
            liquid.cancelled(context.scene)
            self.report({"WARNING"}, "The liquid was not worked out (stopped)")
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        t0 = time.perf_counter()
        try:
            liquid._STATE["guard"] += 1
            try:
                while time.perf_counter() - t0 < liquid.TICK:
                    liquid._STATE["progress"] = next(self._gen)
            finally:
                liquid._STATE["guard"] -= 1
        except StopIteration:
            self._stop(context)
            liquid.show(context.scene)
            info = self._notes[0] if self._notes else {}
            msg = f"Coolant liquid worked out in {info.get('seconds', 0.0):.0f} s"
            context.scene.fresing.last_message = msg
            self.report({"INFO"}, msg)
            return {"FINISHED"}
        except Exception as exc:                       # noqa: BLE001 - say what went wrong, never leave it "running"
            self._stop(context)
            liquid.cancelled(context.scene)
            liquid.runtime(context.scene)["status"] = f"The liquid could not be worked out: {exc}"
            self.report({"ERROR"}, f"The liquid could not be worked out: {exc}")
            return {"CANCELLED"}
        self._status(context)
        _redraw()
        return {"RUNNING_MODAL"}


class FRESING_OT_liquid_cancel(bpy.types.Operator):
    """Stops working out the coolant liquid. It does not start again by itself until you build again or press Work
    out the liquid"""

    bl_idname = "fresing.liquid_cancel"
    bl_label = "Cancel"

    def execute(self, context):
        liquid._STATE["cancel"] = True
        return {"FINISHED"}


CLASSES = (FRESING_OT_liquid_bake, FRESING_OT_liquid_cancel)
