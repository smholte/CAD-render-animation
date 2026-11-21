"""The Lesson panel (task 0230): at the top of the Fresing tab while a lesson runs – the step's text, More, Back,
Next / Do it for me, Play on, Stop. In a project that followed a lesson and was opened again it offers to go on.

The lesson itself is ``lesson.py``; the Learn window and the learning list's buttons are in ``ops_learning.py``.
"""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..core import functions
from . import lesson, ui
from .ui_left import LeftPanel


def _guide(layout, fid: str) -> None:
    f = functions.FUNCTIONS.get(fid)
    if f is not None and f.guide:
        try:
            op = layout.operator("fresing.learn_show", text="This in the user guide", icon="HELP")
            op.fid, op.how = fid, "GUIDE"
        except Exception:  # noqa: BLE001 - the operator is not there (the guide without the app)
            pass


class FRESING_PT_lesson(LeftPanel, bpy.types.Panel):  # task 0260: on the left panel
    bl_label = "Lesson"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return lesson.running() or context.scene.get(lesson.KEY, "") in lesson.LESSONS

    def draw_header(self, context):
        self.layout.label(icon="LIGHT")

    def draw_header_preset(self, context):
        les = lesson.current()
        if les is None:
            ui.header_status(self.layout, "paused")
            return
        k = min(lesson._S["step"] + 1, len(les.steps))
        ui.header_status(self.layout, "done" if lesson.step() is None else f"{k} of {len(les.steps)}")

    def draw(self, context):
        layout = self.layout
        les = lesson.current()
        if les is None:                                   # a project that followed a lesson, opened again
            saved = lesson.LESSONS[context.scene[lesson.KEY]]
            k = lesson.first_not_done(context.scene, saved)
            ui.wrap(layout, context, f"{saved.title}: {k} of {len(saved.steps)} steps done.", icon="INFO")
            row = ui.big_row(layout, ui.MEDIUM)
            for mode, text in lesson.MODES.items():
                op = row.operator("fresing.lesson_resume", text=text)
                op.mode = mode
            layout.operator("fresing.lesson_stop", text="Forget the lesson", icon="X")
            return
        st = lesson.step()
        ui.wrap(layout, context, f"{les.title} – {lesson.MODES[lesson._S['mode']]}")
        if st is None:
            ui.wrap(layout, context, "Lesson finished: everything you made stays in the project. Save it to keep it.",
                    icon="CHECKMARK")
            layout.operator("fresing.lesson_stop", text="Close the lesson", icon="X")
            return
        box = layout.box()
        done = lesson._S["phase"] == "done"
        box.label(text=st.title, icon="CHECKMARK" if done else "RIGHTARROW")
        ui.wrap(box, context, st.say)
        if st.more:
            box.operator("fresing.lesson_more", text="Less" if lesson._S["more"] else "More …", emboss=False,
                         icon="DISCLOSURE_TRI_DOWN" if lesson._S["more"] else "DISCLOSURE_TRI_RIGHT")
            if lesson._S["more"]:
                ui.wrap(box, context, st.more)
        if lesson._S["failed"]:
            ui.wrap(box, context, "Did not work: " + lesson._S["failed"], icon="ERROR", alert=True)
        _guide(box, st.function)
        ui.gap(layout)
        row = ui.big_row(layout, ui.MEDIUM)
        row.operator("fresing.lesson_back", text="Back", icon="TRIA_LEFT")
        if lesson._S["mode"] == "BUILD" and not done:
            row.operator("fresing.lesson_do", text="Do it for me", icon="PLAY")
        else:
            row.operator("fresing.lesson_next", text="Next", icon="TRIA_RIGHT")
        if lesson._S["mode"] == "SHOW":
            try:
                from . import prefs
                p = prefs.get()
                if p is not None:
                    layout.prop(p, "lesson_play_on")
            except Exception:  # noqa: BLE001
                pass
        ui.gap(layout)
        col = layout.column(align=True)
        other = "BUILD" if lesson._S["mode"] == "SHOW" else "SHOW"
        col.operator("fresing.lesson_mode", text=f"Go on as {lesson.MODES[other]}",
                     icon="TOOL_SETTINGS" if other == "BUILD" else "PLAY").mode = other
        col.operator("fresing.lesson_stop", text="Stop the lesson", icon="X")


class FRESING_OT_lesson_next(bpy.types.Operator):
    """Goes to the next step of the lesson. In Show me before the app did this step: it does it first"""

    bl_idname = "fresing.lesson_next"
    bl_label = "Next"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return lesson.running()

    def execute(self, context):
        st = lesson.step()
        if lesson._S["phase"] in ("point", "wait") and st is not None and not lesson.is_done(context.scene, st):
            if not lesson.do_step(context.scene):
                return {"CANCELLED"}
        lesson.next_step(context.scene)
        return {"FINISHED"}


class FRESING_OT_lesson_do(bpy.types.Operator):
    """Does this step for you – the same as the button that glows – and goes on to the next one"""

    bl_idname = "fresing.lesson_do"
    bl_label = "Do it for me"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return lesson.running() and lesson.step() is not None

    def execute(self, context):
        return {"FINISHED"} if lesson.do_step(context.scene) else {"CANCELLED"}


class FRESING_OT_lesson_back(bpy.types.Operator):
    """Takes the last step back (as Undo, Ctrl+Z) and shows it again"""

    bl_idname = "fresing.lesson_back"
    bl_label = "Back"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return lesson.running()

    def execute(self, context):
        lesson.back()
        return {"FINISHED"}


class FRESING_OT_lesson_more(bpy.types.Operator):
    """Shows more about this step, or less"""

    bl_idname = "fresing.lesson_more"
    bl_label = "More"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        lesson._S["more"] = not lesson._S["more"]
        lesson._redraw()
        return {"FINISHED"}


class FRESING_OT_lesson_mode(bpy.types.Operator):
    """Show me: the app does each step while you watch. Build it yourself: you do each step where it glows, the
    lesson goes on when the project shows it done"""

    bl_idname = "fresing.lesson_mode"
    bl_label = "Lesson mode"
    bl_options = {"INTERNAL"}

    mode: EnumProperty(items=[(k, v, "") for k, v in lesson.MODES.items()], options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return lesson.running()

    def execute(self, context):
        lesson.set_mode(self.mode)
        return {"FINISHED"}


class FRESING_OT_lesson_resume(bpy.types.Operator):
    """Goes on with the lesson this project followed, at the first step it does not show done yet"""

    bl_idname = "fresing.lesson_resume"
    bl_label = "Go on with the lesson"
    bl_options = {"INTERNAL"}

    mode: EnumProperty(items=[(k, v, "") for k, v in lesson.MODES.items()], options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return context.scene.get(lesson.KEY, "") in lesson.LESSONS

    def execute(self, context):
        lesson.start(context.scene, context.scene[lesson.KEY], self.mode)
        return {"FINISHED"}


class FRESING_OT_lesson_stop(bpy.types.Operator):
    """Ends the lesson. Everything you made stays in the project"""

    bl_idname = "fresing.lesson_stop"
    bl_label = "Stop the lesson"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        lesson.stop(forget=True)
        return {"FINISHED"}


CLASSES = (FRESING_PT_lesson, FRESING_OT_lesson_next, FRESING_OT_lesson_do, FRESING_OT_lesson_back,
           FRESING_OT_lesson_more, FRESING_OT_lesson_mode, FRESING_OT_lesson_resume, FRESING_OT_lesson_stop)
