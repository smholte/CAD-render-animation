"""Fresing > Tools and checks (task 0212): the self-test, the PC check and the app's Tools folder from inside the app.

Since 0212 the Desktop and the Start menu hold only "Fresing Render"; the extras (self-test, PC check quick / full /
heavy, safe start, user guide) are shortcuts in the Tools folder of the install folder (``appicon.TOOLS``). This
submenu reaches the same things: the self-test in a second Blender with its own console window (the report lands on
the Desktop, as from its shortcut), the PC check (its own dialog, ``pccheck/ops.py``) and the folder itself.
"""

from __future__ import annotations

import os
import subprocess
import sys

import bpy

from .. import appicon

MENU = "TOPBAR_MT_fresing_tools"
SELFTEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "selftest.py")
REPORT = "Fresing Render self-test.txt"


def app_folder() -> str:
    """The Tools folder of this install ('' when Blender was not installed with Install.bat)."""
    return appicon.tools_dir(appicon.install_dir(bpy.app.binary_path))


def selftest_command(exe: str, desktop: str) -> list[str]:
    """The self-test's command line (as its shortcut runs it, with the extension's own selftest.py)."""
    return [exe, "--background", "--python", SELFTEST, "--", desktop]


class FRESING_OT_self_test(bpy.types.Operator):
    """Check this installation: start, import, a render on the graphics card and the files the app needs. Runs in its
    own window for a few minutes; you can keep working. The report "Fresing Render self-test.txt" lands on your
    Desktop"""

    bl_idname = "fresing.self_test"
    bl_label = "Run the self-test"

    def execute(self, context):
        from .. import winexe
        from ..pccheck import runner
        exe = winexe.console_exe(bpy.app.binary_path)          # its own console window: blender.exe (task 0177)
        if not exe or not os.path.isfile(SELFTEST):
            self.report({"ERROR"}, "Blender's program or the self-test was not found: run Install.bat again")
            return {"CANCELLED"}
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen(selftest_command(exe, runner.desktop_dir()), cwd=os.path.dirname(exe), **kwargs)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start the self-test: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Self-test started: in a few minutes the report \"{REPORT}\" is on your Desktop")
        return {"FINISHED"}


class FRESING_OT_open_app_folder(bpy.types.Operator):
    """Open the app's Tools folder in Explorer: the self-test, the PC checks (quick, full, heavy), the safe start and
    the user guide as shortcuts. Drop a STEP file on a PC check shortcut to test your own model too"""

    bl_idname = "fresing.open_app_folder"
    bl_label = "Open the app folder"

    @classmethod
    def poll(cls, context):
        if not appicon.install_dir(bpy.app.binary_path):
            cls.poll_message_set("Only in Fresing Render installed with Install.bat")
            return False
        return True

    def execute(self, context):
        from . import files
        folder = app_folder()
        try:
            os.makedirs(folder, exist_ok=True)
            files.open_path(folder)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open {folder}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class TOPBAR_MT_fresing_tools(bpy.types.Menu):
    bl_label = "Tools and checks"
    bl_idname = MENU

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("fresing.self_test", icon="CHECKBOX_HLT")
        layout.operator("fresing.pc_check", text="PC check…", icon="CHECKMARK")
        layout.separator()
        layout.operator("fresing.open_app_folder", icon="FILE_FOLDER")


def entries() -> list:
    """The submenu's operator ids in order (tests, the PC check)."""
    return ["fresing.self_test", "fresing.pc_check", "fresing.open_app_folder"]


CLASSES = (FRESING_OT_self_test, FRESING_OT_open_app_folder, TOPBAR_MT_fresing_tools)
