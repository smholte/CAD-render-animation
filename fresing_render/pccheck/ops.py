"""Help > Fresing Render PC check… in the app (and Fresing > Tools and checks, task 0212).

The check runs in a second Blender in the background (``launcher.py``), like the self-test: the app
stays free, and the report opens in the web browser when it is done.

The installer makes the shortcuts "PC check (quick)" / "(full)" / "(heavy)" in the Tools folder of the install
(task 0212; before it they were in the Start menu and on the Desktop). A PC that got this version through Update
now gets them from the app at start: ``appicon.refresh_installed`` (``appicon.ensure_tools``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import core

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, "launcher.py")
SHORTCUT_TEXT = core.SHORTCUT_TEXT
RUNNING_FILE = "running.json"


def launch_command(exe: str, desktop: str, mode: str, model: str = "") -> list[str]:
    """The command line of a PC check (the same one the shortcuts hold)."""
    cmd = [exe, "--background", "--python", LAUNCHER, "--", desktop, mode]
    if model:
        cmd.append(model)
    return cmd


def shortcut_arguments(desktop: str, mode: str) -> str:
    """The shortcut's arguments; Windows adds a dropped file at the end."""
    return core.shortcut_arguments(LAUNCHER, desktop, mode)


def running_pid(hist: str) -> int:
    """The process id of a PC check that is still running, else 0."""
    try:
        with open(os.path.join(hist, RUNNING_FILE), encoding="utf-8") as fh:
            pid = int(json.load(fh).get("pid", 0))
    except (OSError, ValueError, TypeError):
        return 0
    if pid <= 0 or pid == os.getpid():
        return 0
    from ..blender import queue
    return pid if queue._pid_alive_os(pid) else 0


def _model_of_project(context) -> str:
    from ..blender import build
    for root in build.model_roots(context.scene):
        src = bpy.path.abspath(root.get(build.PROP_SOURCE, "") or "")
        if src and os.path.isfile(src):
            return src
    return ""


class FRESING_OT_pc_check(bpy.types.Operator):
    """Test every main function of this version on this PC with the test models: import, joints, milling,
    surroundings, renders on the graphics card, videos and the queue. Runs in the background; a report
    with pictures and times opens in your web browser when it is done"""

    bl_idname = "fresing.pc_check"
    bl_label = "Fresing Render PC check…"

    mode: EnumProperty(name="Check", default="quick",
                       description="Quick tests the main functions in about 3 minutes; Full tests every function "
                                   "in about 15 minutes; Heavy loads the PC like real work (10 to 20 minutes); Test "
                                   "tour renders a picture of every stop of the Learning hub (10 to 15 minutes)",
                       items=[("quick", "Quick (about 3 minutes)", "Import, a joint, a picture on the graphics card "
                                                                   "and a short EEVEE video"),
                              ("full", "Full (about 15 minutes)", "Every function of the app, with pictures"),
                              ("heavy", "Heavy (10 to 20 minutes)", "A big generated machine, 4K pictures and a "
                                                                    "10 second video: shows how the PC copes "
                                                                    "with real load"),
                              ("tour", "Learning hub (10 to 15 minutes)", "Goes through every stop of the Learning hub by "
                                                                       "itself: a picture of each stop with what you "
                                                                       "should see, and the number checks")])
    use_model: BoolProperty(name="Also test my own STEP file",
                            description="Also import one of your own STEP files and measure it: import time, parts, "
                                        "share sorted, a picture and the time per frame. The report stays on this "
                                        "PC; the text for the lead chat holds numbers only")
    filepath: StringProperty(name="STEP file", subtype="FILE_PATH",
                             description="Your STEP file to measure. Click the folder icon to pick it")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = _model_of_project(context)
        from ..blender import form_window
        return form_window.open(self, context, width=480, height=380, title="Fresing Render PC check",
                                confirm="Start", icon="CHECKMARK")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "mode", expand=True)
        col.separator()
        col.prop(self, "use_model")
        sub = col.column()
        sub.enabled = self.use_model and self.mode != "tour"
        sub.prop(self, "filepath", text="")
        col.separator()
        col.label(text="Runs in the background; you can keep working.", icon="INFO")
        if self.mode == "tour":
            col.label(text="Makes a fresh Learning hub and renders every stop; your ticks stay.")
        if self.mode == "heavy":
            col.label(text="Heavy uses the whole PC for a while. Stop it any time:")
            col.label(text="Help > Cancel Fresing Render PC check.")
        col.label(text="The report opens in your web browser at the end.")

    def execute(self, context):
        from . import runner
        hist = runner.history_dir()
        if running_pid(hist):
            self.report({"WARNING"}, "A PC check is still running: wait for its report")
            return {"CANCELLED"}
        model = ""
        if self.use_model and self.mode != "tour":
            model = bpy.path.abspath(self.filepath)
            if not (os.path.isfile(model) and model.lower().endswith((".step", ".stp"))):
                self.report({"ERROR"}, "Pick a STEP file (.step or .stp) first")
                return {"CANCELLED"}
        from .. import winexe
        exe = winexe.console_exe(bpy.app.binary_path)      # its own console window: blender.exe (task 0177)
        if not exe:
            self.report({"ERROR"}, "Blender's program was not found: start the PC check from the Tools folder of the app (Fresing > Tools and checks > Open the app folder)")
            return {"CANCELLED"}
        cmd = launch_command(exe, runner.desktop_dir(), self.mode, model)
        kwargs = {}
        if sys.platform == "win32":
            # its own console window shows the progress; it closes when the check is done
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen(cmd, cwd=os.path.dirname(exe), **kwargs)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start the PC check: {exc}")
            return {"CANCELLED"}
        minutes = {"quick": "3", "full": "15", "heavy": "10 to 20", "tour": "10 to 15"}[self.mode]
        self.report({"INFO"}, f"PC check started ({core.MODE_TITLES[self.mode]}): the report opens in your web "
                              f"browser in about {minutes} minutes")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Help menu: under "Check for Fresing Render updates"
# ---------------------------------------------------------------------------

def _draw_pc_check_help(self, context):
    self.layout.operator(FRESING_OT_pc_check.bl_idname, icon="CHECKMARK")
    _draw_cancel_help(self, context)
    try:
        from ..blender import ops_tour                 # the test tour (task 0059)
        ops_tour.draw_help(self.layout)
    except Exception as exc:  # noqa: BLE001 - never break the Help menu
        print("Fresing Render: test tour menu:", exc)
    try:
        from ..blender import ops_demo                 # the demo project (task 0077)
        ops_demo.draw_help(self.layout)
    except Exception as exc:  # noqa: BLE001 - never break the Help menu
        print("Fresing Render: demo project menu:", exc)


def _add_help_entry() -> None:
    menu = bpy.types.TOPBAR_MT_help
    menu.remove(_draw_pc_check_help)
    try:
        funcs = menu._dyn_ui_initialize()
        names = [getattr(f, "__name__", "") for f in funcs]
        # after the update check (blender/updates.py), else after the user guide (app template)
        at = next((i for i in range(len(funcs)) if names[i] == "_draw_help"
                   and getattr(funcs[i], "__module__", "").endswith("updates")), None)
        if at is None:
            at = next((i for i, n in enumerate(names) if n == "_draw_help_menu"), -1)
        funcs.insert(at + 1, _draw_pc_check_help)
    except (AttributeError, TypeError):
        menu.prepend(_draw_pc_check_help)


class FRESING_OT_pc_check_cancel(bpy.types.Operator):
    """Stop the PC check that is running now. The lines it has finished stay in its report, which opens when it
    has stopped (this can take a moment: a picture that is being rendered is finished first)"""

    bl_idname = "fresing.pc_check_cancel"
    bl_label = "Cancel Fresing Render PC check"

    @classmethod
    def poll(cls, context):
        from . import runner
        return running_pid(runner.history_dir()) > 0

    def execute(self, context):
        from . import runner
        try:
            core.write_text(runner.cancel_path(), "cancel\n")
        except OSError as exc:
            self.report({"ERROR"}, f"Could not stop the PC check: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Stopping the PC check: its report opens when it has stopped")
        return {"FINISHED"}


def _draw_cancel_help(self, context):
    from . import runner
    if running_pid(runner.history_dir()) > 0:
        self.layout.operator(FRESING_OT_pc_check_cancel.bl_idname, icon="CANCEL")


CLASSES = (FRESING_OT_pc_check, FRESING_OT_pc_check_cancel)


def register():
    from ..blender import usage
    for cls in CLASSES:
        if cls.__doc__ and "\n" in cls.__doc__:
            cls.__doc__ = " ".join(cls.__doc__.split())
        usage.wrap(cls)                      # task 0181: its clicks count like every Fresing button's
        bpy.utils.register_class(cls)
    _add_help_entry()


def unregister():
    bpy.types.TOPBAR_MT_help.remove(_draw_pc_check_help)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
