"""Demo project buttons (task 0077): Help > Make demo project…, Cancel, Open demo project. The build is ``demo.py``.

Task 0228: Make demo project… lists the app's own demo (while ``demo.PUBLIC``) and every demo kit the user added
(``core/demo_kits.py``): **Add a demo kit…** (a .zip) and **Remove** sit under the list; Make / Cancel / Open work for the
chosen entry. A kit's demo is made by the same background run with ``--kit <id>`` and goes to ``demo.kit_folder``.

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
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import demo

_BUILD: dict = {}           # the running build: {"proc", "folder", "version", "log", "fh", "cancel_at", "title", "kit"}
PUBLIC_ID = "APP"           # the app's own demo in the Make list (kit ids are lower-case slugs)
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
    what = f"Making {_BUILD['title']}" if _BUILD.get("title") else "Making the demo project"
    return what + (f": {shown}" if shown else "") + " …"


def kits() -> list:
    """The added demo kits (core/demo_kits.KitInfo), by title."""
    from ..core import demo_kits
    try:
        return demo_kits.list_kits(demo.kits_dir())
    except Exception:  # noqa: BLE001 - a broken folder never breaks the menu
        return []


def demos(base: str = "") -> list[tuple[str, str, str, str]]:
    """Every demo the Make list offers: (id, title, folder, kit label); the app's own first (while it has one)."""
    base = base or demo.default_folder()
    out = [(PUBLIC_ID, demo.TITLE, base, "")] if demo.PUBLIC else []
    out += [(k.id, k.title, demo.kit_folder(base, k.id), k.label) for k in kits()]
    return out


_ITEMS: list = []           # Blender needs the enum's strings kept alive


def _which_items(self, context):
    _ITEMS.clear()
    for i, (kid, title, _folder, label) in enumerate(demos()):
        tip = ("The app's own demo project" if kid == PUBLIC_ID else
               f"A demo kit you added ({label}): its own model and animation")
        _ITEMS.append((kid, label or title, tip, "MOD_OCEAN" if kid == PUBLIC_ID else "PACKAGE", i))
    if not _ITEMS:
        _ITEMS.append(("NONE", "No demo yet: add a demo kit", "Add a demo kit… below", "INFO", 0))
    return _ITEMS


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
    """Make the demo project: an invented ship in a wind park with her joints, her deck crane, the open sea, saved
    cameras and a video of what the app can do today – or the demo of a demo kit you added. Made in the background (a
    few minutes); you can keep working. Then open it with Help > Open demo project"""

    bl_idname = "fresing.demo_make"
    bl_label = "Make demo project…"

    folder: StringProperty(name="Folder", subtype="DIR_PATH",
                           description="Where the demo project goes. Default: Documents\\Fresing Render\\Demo")
    which: EnumProperty(name="Demo", items=_which_items,
                        description="Which demo to make: the app's own, or one of the demo kits you added")
    in_place: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})   # tests: build in this Blender

    _timer = None

    def invoke(self, context, event):
        if running():
            self.report({"WARNING"}, "The demo project is being made: wait for it, or Help > Cancel demo project")
            return {"CANCELLED"}
        self.folder = self.folder or demo.default_folder()
        return context.window_manager.invoke_props_dialog(self, width=460, confirm_text="Make it")

    def _target(self):
        """(kit info or None, title, folder) of the chosen demo; kit info None + title '' = nothing to make."""
        base = bpy.path.abspath(self.folder) if self.folder else demo.default_folder()
        if self.which == PUBLIC_ID and demo.PUBLIC:
            return None, demo.TITLE, base
        info = next((k for k in kits() if k.id == self.which), None)
        if info is None:
            return None, "", base
        return info, info.title, demo.kit_folder(base, info.id)

    def draw(self, context):
        from ..core import demo_kits
        col = self.layout.column()
        col.label(text=f"Demo projects for Fresing Render {_version()}:")
        col.prop(self, "which", expand=True)
        row = col.row(align=True)
        row.operator(FRESING_OT_demo_kit_add.bl_idname, icon="IMPORT")
        info, title, folder = self._target()
        if info is not None:
            op = row.operator(FRESING_OT_demo_kit_remove.bl_idname, text="Remove", icon="TRASH")
            op.kit = info.id
        col.separator()
        if info is None and title:
            col.label(text="An invented ship in a wind park: her joints and deck crane, the open sea, the cable")
            col.label(text="on the seabed and a video of what the app can do.")
        elif info is not None:
            col.label(text=f"{info.title}, kit version {info.kit_version}, made for {info.made_for()}.")
            why = demo_kits.version_message(info, _version())
            if why:
                col.label(text=why, icon="ERROR")
        if title:
            col.label(text="It is made in the background (a few minutes); you can keep working.")
            if demo.exists(folder, _version(), title if info is not None else ""):
                col.label(text="A demo of this version is there already: it is replaced.", icon="INFO")
        col.separator()
        col.prop(self, "folder")

    def execute(self, context):
        from ..core import demo_kits
        info, title, folder = self._target()
        version = _version()
        if not title:
            self.report({"ERROR"}, "No demo to make: add a demo kit first (Add a demo kit… in this window)")
            return {"CANCELLED"}
        if info is not None:
            why = demo_kits.version_message(info, version)
            if why:
                self.report({"ERROR"}, why)
                return {"CANCELLED"}
        kit_title = title if info is not None else ""
        if self.in_place or bpy.app.background:
            try:
                out = demo.build_project(folder, version, kit=info)
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
            cmd = [exe, "--background", "--python", pc_ops.LAUNCHER, "--", "demobuild", folder]
            if info is not None:
                cmd += ["--kit", info.id]                                      # task 0228
            proc = subprocess.Popen(cmd, cwd=os.path.dirname(exe), stdout=fh, stderr=subprocess.STDOUT, **kwargs)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start making the demo project: {exc}")
            return {"CANCELLED"}
        _BUILD.clear()
        _BUILD.update(proc=proc, folder=folder, version=version, log=log, fh=fh, started=time.time(),
                      title=kit_title, kit=info.id if info is not None else "")
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
        title = _BUILD.get("title", "")
        cancelled = bool(_BUILD.get("cancel_at"))
        try:
            _BUILD["fh"].close()
        except (KeyError, OSError):
            pass
        log = _BUILD.get("log", "")
        _BUILD.clear()
        res = _read_result(folder)
        if res.get("finished") and demo.exists(folder, version, title):
            _ready_popup(context, demo.project_path(folder, version, title))
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


class FRESING_OT_demo_kit_add(bpy.types.Operator):
    """Add a demo kit: pick its .zip. A kit is a demo project's model and animation made by someone else – Python code
    that runs in the app, so add only kits you made yourself. Then pick it in Help > Make demo project… and Make it"""

    bl_idname = "fresing.demo_kit_add"
    bl_label = "Add a demo kit…"

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default="*.zip", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..core import demo_kits
        try:
            info = demo_kits.add(bpy.path.abspath(self.filepath), demo.kits_dir(), _version())
        except demo_kits.KitError as exc:
            self.report({"ERROR"}, f"The demo kit was not added: {exc}"[:300])
            return {"CANCELLED"}
        self.report({"INFO"}, f"Demo kit added: {info.label}. Make it with Help > Make demo project…")
        return {"FINISHED"}


class FRESING_OT_demo_kit_remove(bpy.types.Operator):
    """Remove this demo kit from the list. A demo project already made from it stays where it is"""

    bl_idname = "fresing.demo_kit_remove"
    bl_label = "Remove demo kit"

    kit: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title="Remove this demo kit?", confirm_text="Remove",
            message="The kit leaves the list (add its zip again to get it back). Demo projects made from it stay.")

    def execute(self, context):
        from ..core import demo_kits
        if running() and _BUILD.get("kit") == self.kit:
            self.report({"WARNING"}, "This kit's demo is being made: cancel it first (Help > Cancel demo project)")
            return {"CANCELLED"}
        try:
            gone = demo_kits.remove(demo.kits_dir(), self.kit)
        except demo_kits.KitError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if not gone:
            self.report({"WARNING"}, f"There is no demo kit '{self.kit}'")
            return {"CANCELLED"}
        self.report({"INFO"}, "Demo kit removed")
        return {"FINISHED"}


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
        if not self.filepath and not demo.PUBLIC:
            made = [p for p in _made() if p[1]]
            if not made:
                self.report({"ERROR"}, "No demo project for this version: Help > Make demo project… first")
                return {"CANCELLED"}
            self.filepath = made[0][1]
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
    for title, path in _made():
        op = layout.operator(FRESING_OT_demo_open.bl_idname, icon="FILE_BLEND",
                             text="Open demo project" if title == demo.TITLE else f"Open {title}")
        op.filepath = path


def _made() -> list[tuple[str, str]]:
    """(title, project file) of every demo of this version that is made: the app's own first, then the kits'."""
    out = []
    for kid, title, folder, _label in demos():
        t = "" if kid == PUBLIC_ID else title
        if demo.exists(folder, _version(), t):
            out.append((title, demo.project_path(folder, _version(), t)))
    return out


CLASSES = (FRESING_OT_demo_make, FRESING_OT_demo_kit_add, FRESING_OT_demo_kit_remove, FRESING_OT_demo_cancel,
           FRESING_OT_demo_open)
