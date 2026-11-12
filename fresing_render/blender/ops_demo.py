"""Demo project buttons (task 0077): Help > Make demo project…, Cancel, Open demo project. The build is ``demo.py``.

Make starts a background Blender (``pccheck/launcher.py -- demobuild <folder>``) so the app stays usable; the status
bar shows its stage ("Writing the model 2/2", "Importing", "Joints 120/422", "Animation"). Cancel asks the build to
stop and, if it does not within a few seconds (it is inside the import or the model maker), stops it and every
program it started; either way the half-made demo folder is deleted.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

import bpy
from bpy.props import BoolProperty, StringProperty

from . import demo

_BUILD: dict = {}           # the running build: {"proc", "folder", "version", "log", "fh", "cancel_at"}
CANCEL_WAIT = 4.0           # s: how long Cancel lets the build stop by itself before it is stopped


def _version() -> str:
    from .. import __version__
    return __version__


def running() -> bool:
    proc = _BUILD.get("proc")
    return proc is not None and proc.poll() is None


def progress_text() -> str:
    if not running():
        return ""
    if _BUILD.get("cancel_at"):
        return "Stopping the demo project …"
    p = demo.read_progress(_BUILD["folder"], _BUILD["version"])
    stage, text = p.get("stage", ""), p.get("text", "")
    shown = text if text and text != stage else stage
    return "Making the demo project" + (f": {shown}" if shown else "") + " …"


def kill_tree(pid: int) -> None:
    """Stop a program and every program it started (the model maker, the STEP reader's helpers)."""
    if not pid:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass


def _read_result(folder: str) -> dict:
    try:
        with open(demo.result_path(folder), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class FRESING_OT_demo_make(bpy.types.Operator):
    """Make the demo project: an invented cable-lay vessel with its joints, cylinders, the open sea, saved cameras
    and a video of what the app can do today. Made in the background (a few minutes); you can keep working. Then
    open it with Help > Open demo project"""

    bl_idname = "fresing.demo_make"
    bl_label = "Make demo project…"

    folder: StringProperty(name="Folder", subtype="DIR_PATH",
                           description="Where the demo project goes. Default: Documents\\Fresing Render\\Demo")
    in_place: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})   # tests: build in this Blender

    _timer = None

    def invoke(self, context, event):
        if running():
            self.report({"WARNING"}, "The demo project is being made: wait for it, or Help > Cancel demo project")
            return {"CANCELLED"}
        self.folder = self.folder or demo.default_folder()
        return context.window_manager.invoke_props_dialog(self, width=460, confirm_text="Make it")

    def draw(self, context):
        col = self.layout.column()
        col.label(text=f"A demo project for Fresing Render {_version()}: an invented cable-lay vessel")
        col.label(text="with its joints, the open sea and a video of what the app can do.")
        col.label(text="It is made in the background (a few minutes); you can keep working.")
        if demo.exists(bpy.path.abspath(self.folder) or demo.default_folder(), _version()):
            col.label(text="A demo of this version is there already: it is replaced.", icon="INFO")
        col.separator()
        col.prop(self, "folder")

    def execute(self, context):
        folder = bpy.path.abspath(self.folder) if self.folder else demo.default_folder()
        version = _version()
        if self.in_place or bpy.app.background:
            try:
                out = demo.build_project(folder, version)
            except Exception as exc:  # noqa: BLE001 - said plainly
                self.report({"ERROR"}, f"The demo project could not be made: {exc}"[:300])
                return {"CANCELLED"}
            self.report({"INFO"}, f"Demo project made: {out['path']}")
            return {"FINISHED"}
        if bpy.data.filepath and os.path.normcase(os.path.dirname(bpy.data.filepath)) == \
                os.path.normcase(demo.project_dir(folder, version)):
            self.report({"ERROR"}, "The demo project is open: open another project first, then make it again")
            return {"CANCELLED"}
        exe = bpy.app.binary_path
        if not exe:
            self.report({"ERROR"}, "Blender's program was not found")
            return {"CANCELLED"}
        from ..pccheck import ops as pc_ops
        os.makedirs(folder, exist_ok=True)
        for f in (demo.result_path(folder),):
            try:
                os.remove(f)
            except OSError:
                pass
        log = os.path.join(folder, "Make demo log.txt")
        kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" \
            else {"start_new_session": True}
        try:
            fh = open(log, "w", encoding="utf-8", errors="replace")
            proc = subprocess.Popen([exe, "--background", "--python", pc_ops.LAUNCHER, "--", "demobuild", folder],
                                    cwd=os.path.dirname(exe), stdout=fh, stderr=subprocess.STDOUT, **kwargs)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start making the demo project: {exc}")
            return {"CANCELLED"}
        _BUILD.clear()
        _BUILD.update(proc=proc, folder=folder, version=version, log=log, fh=fh, started=time.time())
        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "Making the demo project in the background (a few minutes)")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        proc = _BUILD.get("proc")
        if proc is not None and proc.poll() is None:
            cancel_at = _BUILD.get("cancel_at")
            if cancel_at and time.time() - cancel_at > CANCEL_WAIT:
                kill_tree(proc.pid)
                p = demo.read_progress(_BUILD["folder"], _BUILD["version"])
                kill_tree(int(p.get("helper") or 0))
            context.workspace.status_text_set(progress_text())
            _redraw(context)
            return {"PASS_THROUGH"}
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        folder, version = _BUILD.get("folder", ""), _BUILD.get("version", _version())
        cancelled = bool(_BUILD.get("cancel_at"))
        try:
            _BUILD["fh"].close()
        except (KeyError, OSError):
            pass
        log = _BUILD.get("log", "")
        _BUILD.clear()
        res = _read_result(folder)
        if res.get("finished") and demo.exists(folder, version):
            _ready_popup(context, demo.project_path(folder, version))
            self.report({"INFO"}, f"Demo project ready ({res.get('seconds', 0):.0f} s): Help > Open demo project")
            return {"FINISHED"}
        left = demo.remove(folder, version)              # a stopped build leaves nothing behind
        if cancelled or res.get("cancelled"):
            self.report({"WARNING"}, "Demo project cancelled: nothing was left behind" if not left else
                        f"Demo project cancelled, but {left}")
            return {"FINISHED"}
        why = res.get("error") or "it stopped half-way"
        self.report({"ERROR"}, f"The demo project could not be made ({why[:200]}). Nothing was left behind "
                               f"except its log: {log}")
        return {"FINISHED"}


def _redraw(context) -> None:
    for area in context.screen.areas if context.screen else ():
        if area.type in ("VIEW_3D", "TOPBAR", "STATUSBAR"):
            area.tag_redraw()


def _ready_popup(context, path: str) -> None:
    def draw(menu, _context):
        menu.layout.label(text="The demo project is ready.")
        op = menu.layout.operator(FRESING_OT_demo_open.bl_idname, text="Open demo project", icon="FILE_BLEND")
        op.filepath = path

    try:
        context.window_manager.popup_menu(draw, title="Demo project", icon="CHECKMARK")
    except Exception:  # noqa: BLE001 - the report line says it too
        pass


class FRESING_OT_demo_cancel(bpy.types.Operator):
    """Stop making the demo project. What was made so far is deleted, so no half project is left"""

    bl_idname = "fresing.demo_cancel"
    bl_label = "Cancel demo project"

    @classmethod
    def poll(cls, context):
        return running()

    def execute(self, context):
        folder, version = _BUILD["folder"], _BUILD["version"]
        try:
            with open(demo.cancel_path(folder, version), "w", encoding="utf-8") as fh:
                fh.write("cancel\n")
        except OSError:
            pass                                    # the folder may not be there yet: it is stopped instead
        _BUILD["cancel_at"] = time.time()
        self.report({"INFO"}, "Stopping the demo project …")
        return {"FINISHED"}


class FRESING_OT_demo_open(bpy.types.Operator):
    """Open the demo project of this version (made with Make demo project…). Save your own project first:
    changes that are not saved are lost"""

    bl_idname = "fresing.demo_open"
    bl_label = "Open demo project"

    filepath: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        if bpy.data.is_dirty and not demo.is_demo(context.scene):
            return context.window_manager.invoke_confirm(
                self, event, title="Open the demo project?", confirm_text="Open",
                message="This project has changes that are not saved: they are lost. Open the demo anyway?")
        return self.execute(context)

    def execute(self, context):
        path = self.filepath or demo.project_path(demo.default_folder(), _version())
        if not os.path.isfile(path) or (not self.filepath and not demo.exists(demo.default_folder(), _version())):
            self.report({"ERROR"}, "No demo project for this version: Help > Make demo project… first")
            return {"CANCELLED"}
        bpy.ops.wm.open_mainfile(filepath=path)
        return {"FINISHED"}


def draw_help(layout) -> None:
    """Help menu entries under the test tour (pccheck/ops.py draws them)."""
    text = progress_text()
    if text:
        layout.label(text=text, icon="TIME")
        layout.operator(FRESING_OT_demo_cancel.bl_idname, icon="CANCEL")
    else:
        layout.operator(FRESING_OT_demo_make.bl_idname, icon="MOD_OCEAN")
    if demo.exists(demo.default_folder(), _version()):
        layout.operator(FRESING_OT_demo_open.bl_idname, icon="FILE_BLEND")


CLASSES = (FRESING_OT_demo_make, FRESING_OT_demo_cancel, FRESING_OT_demo_open)
