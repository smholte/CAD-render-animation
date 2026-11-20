"""Automatic backups (task 0246): Fresing > Restore a backup…, the question at the start, Restore, Show in folder."""

from __future__ import annotations

import os
from datetime import date, datetime

import bpy
from bpy.props import StringProperty

from ..core import backups as core
from . import backups


def _when_text(b) -> str:
    at = datetime.fromtimestamp(b.mtime)
    if at.date() == date.today():
        return "Today " + at.strftime("%H:%M")
    return at.strftime("%a %d %b %H:%M")


class FRESING_OT_backups_window(bpy.types.Operator):
    """Shows this project's automatic backups (made every few minutes while you work) with their time and size.
    Restore puts one back: your work as it is now is kept as a backup first, so nothing is lost"""

    bl_idname = "fresing.backups_window"
    bl_label = "Restore a backup…"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=640, title="Restore a backup",
                                                          confirm_text="Close")

    def draw(self, context):
        col = self.layout.column()
        project = bpy.data.filepath
        found = backups.project_backups(project)
        on, minutes, keep_last, days = backups.settings()
        if project:
            col.label(text=f"Backups of {os.path.basename(project)}", icon="FILE_BACKUP")
        else:
            col.label(text="Backups of projects that were never saved", icon="FILE_BACKUP")
        state = (f"every {minutes} min while something changes; the last {keep_last} and one a day for {days} days "
                 "are kept" if on else "automatic backups are switched off (Edit > Preferences > Add-ons > Fresing "
                 "Render)")
        col.label(text=state.capitalize() if not on else "Made " + state)
        if not found:
            col.separator()
            col.label(text="No backups yet.", icon="INFO")
            return
        mt = backups.saved_mtime(project)
        col.label(text=f"{len(found)} files, {core.size_text(core.total_size(found))} together")
        col.separator()
        for b in found[:40]:
            row = col.row(align=True)
            split = row.split(factor=0.3, align=True)
            newer = mt is not None and core.newer_than_saved(b, mt)
            split.label(text=_when_text(b), icon="TIME")
            split.label(text=core.size_text(b.size) + ("  ·  newer than the saved project" if newer else ""))
            op = row.operator(FRESING_OT_backup_restore.bl_idname, text="Restore", icon="RECOVER_LAST")
            op.path = b.path
            op = row.operator(FRESING_OT_backup_show.bl_idname, text="", icon="FILE_FOLDER")
            op.path = b.path
        if len(found) > 40:
            col.label(text=f"… and {len(found) - 40} older ones in the folder")

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_backup_restore(bpy.types.Operator):
    """Puts this backup back: your work as it is now is first kept as a backup itself, then the backup replaces the
    project file and opens. A project that was never saved opens as a new file in Documents\\Fresing Render\\Recovered
    projects: save it where you want with File > Save As"""

    bl_idname = "fresing.backup_restore"
    bl_label = "Restore this backup"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"HIDDEN", "SKIP_SAVE"}, subtype="FILE_PATH",
                         description="The backup file to put back")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title="Restore this backup?",
            message="Your work as it is now is kept as a backup first.", confirm_text="Restore")

    def execute(self, context):
        try:
            target = backups.restore(self.path)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not restore the backup: {exc}")
            return {"CANCELLED"}
        when = datetime.fromtimestamp(os.path.getmtime(self.path)).strftime("%H:%M") if os.path.isfile(self.path) \
            else ""
        text = f"Restored the backup from {when}" if when else "Restored the backup"
        if core.RECOVERED in target:
            text += ": save it with File > Save As"
        try:
            bpy.context.scene.fresing.last_message = text
        except Exception:  # noqa: BLE001
            pass
        self.report({"INFO"}, text)
        return {"FINISHED"}


class FRESING_OT_backup_show(bpy.types.Operator):
    """Opens the folder with this project's backups in File Explorer, the backup selected"""

    bl_idname = "fresing.backup_show"
    bl_label = "Show in folder"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"HIDDEN", "SKIP_SAVE"}, subtype="FILE_PATH",
                         description="The backup to show")

    def execute(self, context):
        from . import files
        if not os.path.exists(self.path):
            self.report({"WARNING"}, "That backup is no longer there")
            return {"CANCELLED"}
        files.show_in_folder(self.path)
        return {"FINISHED"}


class FRESING_OT_backup_offer(bpy.types.Operator):
    """Asked when a project opens and one of its backups is newer than the saved file (Blender or the PC stopped
    before you saved), or at the start for work that was never saved. Open the backup puts it back; Cancel keeps the
    saved project (the backup stays in Fresing > Restore a backup…)"""

    bl_idname = "fresing.backup_offer"
    bl_label = "A newer backup"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"HIDDEN", "SKIP_SAVE"}, subtype="FILE_PATH",
                         description="The backup this question is about")

    def _backup(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        when = core.parse(os.path.basename(self.path), core.project_name(bpy.data.filepath)) or \
            datetime.fromtimestamp(st.st_mtime)
        return core.Backup(self.path, when, st.st_size, st.st_mtime)

    def invoke(self, context, event):
        if self._backup() is None:
            return {"CANCELLED"}
        title = "A newer backup" if bpy.data.filepath else "Work that was never saved"
        return context.window_manager.invoke_props_dialog(self, width=520, title=title,
                                                          confirm_text="Open the backup")

    def draw(self, context):
        b = self._backup()
        col = self.layout.column()
        if b is None:
            col.label(text="The backup is no longer there.")
            return
        project = bpy.data.filepath
        col.label(text=core.offer_text(b, backups.saved_mtime(project) if project else None), icon="FILE_BACKUP")
        if project:
            col.label(text="Open the backup: it replaces the saved project (the saved one is kept as a backup).")
            col.label(text="Cancel: keep the saved project. The backup stays in Fresing > Restore a backup…")
        else:
            col.label(text="Open the backup: it opens as a new file; save it with File > Save As.")
            col.label(text="Cancel: not now. It stays in Fresing > Restore a backup… while no project is open.")

    def execute(self, context):
        try:
            backups.restore(self.path)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not open the backup: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}

    def cancel(self, context):
        if not bpy.data.filepath:
            try:
                core.mark_handled(backups.state_path(), [self.path])
            except OSError:
                pass


CLASSES = (FRESING_OT_backups_window, FRESING_OT_backup_restore, FRESING_OT_backup_show, FRESING_OT_backup_offer)


def register() -> None:
    backups.register()


def unregister() -> None:
    backups.unregister()
