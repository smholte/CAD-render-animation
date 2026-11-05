"""Help > Fresing Render PC check… in the app, and the Start-menu shortcuts on Windows.

The check runs in a second Blender in the background (``launcher.py``), like the self-test: the app
stays free, and the report opens in the web browser when it is done.

The installer makes the shortcuts "Fresing Render - PC check (quick)" and "(full)". A PC that got this
version through Update now never ran the new installer, so the app makes them itself at start (Windows,
only when the installer's Start-menu folder is there and a shortcut is missing).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import core

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, "launcher.py")
START_MENU_FOLDER = "Fresing Render"
SHORTCUTS = {"quick": "Fresing Render - PC check (quick).lnk", "full": "Fresing Render - PC check (full).lnk"}
SHORTCUT_TEXT = {"quick": "Check every main function quickly (about 3 minutes). Drop a STEP file on it to test "
                          "your own model too",
                 "full": "Check every function of the app on this PC (about 15 minutes). Drop a STEP file on it "
                         "to test your own model too"}
RUNNING_FILE = "running.json"


def launch_command(exe: str, desktop: str, mode: str, model: str = "") -> list[str]:
    """The command line of a PC check (the same one the shortcuts hold)."""
    cmd = [exe, "--background", "--python", LAUNCHER, "--", desktop, mode]
    if model:
        cmd.append(model)
    return cmd


def shortcut_arguments(desktop: str, mode: str) -> str:
    """The shortcut's arguments; Windows adds a dropped file at the end."""
    return f'--background --python "{LAUNCHER}" -- "{desktop}" {mode}'


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
                                   "in about 15 minutes",
                       items=[("quick", "Quick (about 3 minutes)", "Import, a joint, a picture on the graphics card "
                                                                   "and a short EEVEE video"),
                              ("full", "Full (about 15 minutes)", "Every function of the app, with pictures")])
    use_model: BoolProperty(name="Also test my own STEP file",
                            description="Also import one of your own STEP files and measure it: import time, parts, "
                                        "share sorted, a picture and the time per frame. The report stays on this "
                                        "PC; the text for the lead chat holds numbers only")
    filepath: StringProperty(name="STEP file", subtype="FILE_PATH",
                             description="Your STEP file to measure. Click the folder icon to pick it")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = _model_of_project(context)
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "mode", expand=True)
        col.separator()
        col.prop(self, "use_model")
        sub = col.column()
        sub.enabled = self.use_model
        sub.prop(self, "filepath", text="")
        col.separator()
        col.label(text="Runs in the background; you can keep working.", icon="INFO")
        col.label(text="The report opens in your web browser at the end.")

    def execute(self, context):
        from . import runner
        hist = runner.history_dir()
        if running_pid(hist):
            self.report({"WARNING"}, "A PC check is still running: wait for its report")
            return {"CANCELLED"}
        model = ""
        if self.use_model:
            model = bpy.path.abspath(self.filepath)
            if not (os.path.isfile(model) and model.lower().endswith((".step", ".stp"))):
                self.report({"ERROR"}, "Pick a STEP file (.step or .stp) first")
                return {"CANCELLED"}
        exe = bpy.app.binary_path
        if not exe:
            self.report({"ERROR"}, "Blender's program was not found: start the PC check from the Start menu")
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
        minutes = "3" if self.mode == "quick" else "15"
        self.report({"INFO"}, f"PC check started ({core.MODE_TITLES[self.mode]}): the report opens in your web "
                              f"browser in about {minutes} minutes")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Start-menu shortcuts (Windows)
# ---------------------------------------------------------------------------

def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def shortcut_script(folder: str, exe: str, desktop: str, missing: list[str]) -> str:
    """PowerShell that makes the missing PC-check shortcuts in the Start-menu folder."""
    lines = ["$s = New-Object -ComObject WScript.Shell"]
    for mode in missing:
        lines += [f"$l = $s.CreateShortcut({_ps_quote(os.path.join(folder, SHORTCUTS[mode]))})",
                  f"$l.TargetPath = {_ps_quote(exe)}",
                  f"$l.Arguments = {_ps_quote(shortcut_arguments(desktop, mode))}",
                  f"$l.WorkingDirectory = {_ps_quote(os.path.dirname(exe))}",
                  f"$l.IconLocation = {_ps_quote(exe + ',0')}",
                  f"$l.Description = {_ps_quote(SHORTCUT_TEXT[mode])}",
                  "$l.Save()"]
    return "\n".join(lines)


def missing_shortcuts(folder: str) -> list[str]:
    return [m for m, name in SHORTCUTS.items() if not os.path.isfile(os.path.join(folder, name))]


def ensure_shortcuts() -> str:
    """Windows: make the PC-check shortcuts when the installer's Start-menu folder has none (an update
    through the app). Returns what was done (for the console)."""
    if sys.platform != "win32" or bpy.app.background:
        return ""
    from . import runner
    programs = runner._known_folder("A77F5D77-2E2B-44C3-A6A2-ABA601054A51")       # FOLDERID_Programs
    folder = os.path.join(programs, START_MENU_FOLDER) if programs else ""
    if not folder or not os.path.isdir(folder):
        return ""                                        # not installed with Install.bat: leave the menu alone
    missing = missing_shortcuts(folder)
    exe = bpy.app.binary_path
    if not missing or not exe or not os.path.isfile(exe):
        return ""
    script = shortcut_script(folder, exe, runner.desktop_dir(), missing)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-EncodedCommand", encoded]

    def work():
        try:
            subprocess.run(cmd, capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError) as exc:
            print("Fresing Render: could not make the PC check shortcuts:", exc)

    threading.Thread(target=work, daemon=True).start()
    return "making " + ", ".join(SHORTCUTS[m] for m in missing)


# ---------------------------------------------------------------------------
# Help menu: under "Check for Fresing Render updates"
# ---------------------------------------------------------------------------

def _draw_help(self, context):
    self.layout.operator(FRESING_OT_pc_check.bl_idname, icon="CHECKMARK")


def _add_help_entry() -> None:
    menu = bpy.types.TOPBAR_MT_help
    menu.remove(_draw_help)
    try:
        funcs = menu._dyn_ui_initialize()
        names = [getattr(f, "__name__", "") for f in funcs]
        # after the update check (blender/updates.py), else after the user guide (app template)
        at = next((i for i in range(len(funcs)) if names[i] == "_draw_help"
                   and getattr(funcs[i], "__module__", "").endswith("updates")), None)
        if at is None:
            at = next((i for i, n in enumerate(names) if n == "_draw_help_menu"), -1)
        funcs.insert(at + 1, _draw_help)
    except (AttributeError, TypeError):
        menu.prepend(_draw_help)


CLASSES = (FRESING_OT_pc_check,)


def register():
    for cls in CLASSES:
        if cls.__doc__ and "\n" in cls.__doc__:
            cls.__doc__ = " ".join(cls.__doc__.split())
        bpy.utils.register_class(cls)
    _add_help_entry()
    try:
        done = ensure_shortcuts()
        if done:
            print("Fresing Render:", done)
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render: could not check the PC check shortcuts:", exc)


def unregister():
    bpy.types.TOPBAR_MT_help.remove(_draw_help)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
