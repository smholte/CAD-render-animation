"""Operators of the Workspace switcher, the function-family ticks, own workspaces and the What's next card
(task 0062)."""

from __future__ import annotations

import os
import textwrap

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ..core import functions as F
from ..core import workspaces as W
from ..core.words import plural
from . import locations, panels, workspaces

_ITEMS: list = []            # Blender needs the strings of a dynamic enum kept alive


def _workspace_items(self, context):
    _ITEMS[:] = [(name, name + ("  (your own)" if own else ""), note) for name, note, own in workspaces.names()]
    return _ITEMS


def _report_error(op, exc) -> set:
    op.report({"ERROR"}, str(exc))
    return {"CANCELLED"}


def _lines(layout, text: str, width: int = 58, icon: str = "NONE") -> None:
    col = layout.column(align=True)
    for i, line in enumerate(textwrap.wrap(text, width) or [""]):
        col.label(text=line, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))


class FRESING_OT_workspace_pick(bpy.types.Operator):
    """Picks the workspace of this project: which functions the side panel shows. Nothing is deleted or switched
    off – hidden functions keep their settings and keep working in renders. Tick single families on or off below"""

    bl_idname = "fresing.workspace_pick"
    bl_label = "Workspace"
    bl_property = "name"
    bl_options = {"REGISTER", "UNDO"}

    name: EnumProperty(name="Workspace", items=_workspace_items,
                       description="The workspace this project uses from now on")

    def execute(self, context):
        scene = context.scene
        before = workspaces.current(scene)
        try:
            ws = workspaces.switch(scene, self.name)
        except (KeyError, OSError) as exc:
            return _report_error(self, exc)
        if ws.blender_ui and not before.blender_ui:
            from . import lock
            lock.blender_ui(True, toolbar=True)
        hidden = workspaces.hidden_in_use(scene)
        note = f"Workspace: {ws.name}"
        if ws.lock:
            note += " – the project is locked against changes; Full access unlocks it"
        elif hidden:
            note += (f" – {plural(len(hidden), 'family', 'families')} this project uses "
                     f"{'is' if len(hidden) == 1 else 'are'} hidden (Workspace > Show what the project uses)")
        self.report({"INFO"}, note)
        return {"FINISHED"}


class FRESING_OT_workspace_default(bpy.types.Operator):
    """Sets the workspace every new project starts in (kept in the preferences). A project from before
    workspaces opens in it too, with everything it uses shown"""

    bl_idname = "fresing.workspace_default"
    bl_label = "Workspace for new projects"
    bl_property = "name"

    name: EnumProperty(name="Workspace", items=_workspace_items,
                       description="The workspace new projects start in")
    current: BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"},
                          description="Use the workspace of the open project")

    def execute(self, context):
        from . import prefs
        p = prefs.get()
        if p is None:
            self.report({"WARNING"}, "The Fresing Render preferences are not available")
            return {"CANCELLED"}
        name = workspaces.name_of(context.scene) if self.current else self.name
        p.default_workspace = name
        try:
            context.preferences.is_dirty = True          # saved with the preferences when the app closes
        except (AttributeError, TypeError):
            pass
        self.report({"INFO"}, f"New projects start in the workspace '{name}'")
        panels.redraw()
        return {"FINISHED"}


class FRESING_OT_workspace_star(bpy.types.Operator):
    """Stars this workspace: it moves to the top of the Workspace drop-down, above the line. Press the star again to
    take it away. Kept for you, also over a restart"""

    bl_idname = "fresing.workspace_star"
    bl_label = "Star a workspace"

    name: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        name = properties.name
        if workspaces.starred(name):
            return f"Takes the star away from '{name}': it goes back to its place under the line"
        return (f"Stars '{name}': it moves to the top of the Workspace drop-down, above the line. Kept for you, also "
                "over a restart")

    def execute(self, context):
        if not self.name:
            return {"CANCELLED"}
        on = workspaces.toggle_star(self.name)
        self.report({"INFO"}, f"'{self.name}' {'starred: on top of the list' if on else 'no longer starred'}")
        panels.redraw()
        return {"FINISHED"}


class FRESING_MT_workspaces(bpy.types.Menu):
    """The Workspace drop-down (task 0294): the workspace for new projects and the starred ones on top, a line, then
    the others; a star beside each"""

    bl_idname = "FRESING_MT_workspaces"
    bl_label = "Workspace"
    bl_description = ("Picks the workspace of this project: which functions the side panel shows. The star beside "
                      "a workspace puts it on top of this list")

    def draw(self, context):
        layout = self.layout
        cur = workspaces.name_of(context.scene)
        new = workspaces.default_name()
        top, rest = workspaces.menu()
        col = layout.column(align=True)
        for i, part in enumerate((top, rest)):
            if i and top and rest:
                col.separator()
            for name, _note, own in part:
                row = col.row(align=True)
                label = name + ("  (your own)" if own else "") + ("  · new projects" if name == new else "")
                # task 0321: each workspace its own icon; the one in use a tick
                op = row.operator("fresing.workspace_pick", text=label,
                                  icon="CHECKMARK" if name == cur else workspaces.icon_of(name))
                op.name = name
                star = row.operator("fresing.workspace_star", text="",
                                    icon="SOLO_ON" if workspaces.starred(name) else "SOLO_OFF", emboss=False)
                star.name = name


class FRESING_OT_family_toggle(bpy.types.Operator):
    """Shows or hides this family of functions in the side panel, for this project. Hiding never deletes or
    switches off anything: what is set up stays in the project and keeps working in renders. A family the
    project uses asks first"""

    bl_idname = "fresing.family_toggle"
    bl_label = "Show or hide a function family"
    bl_options = {"REGISTER", "UNDO"}

    family: StringProperty(options={"SKIP_SAVE"})
    warning: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        fam = properties.family
        if fam not in F.FAMILIES:
            return cls.__doc__
        on = workspaces.family_on(context.scene, fam)
        return (f"{'Hides' if on else 'Shows'} {W.family_title(fam)} in the side panel, for this project: "
                f"{W.family_note(fam)}. Hiding never deletes or switches off anything; a family the project "
                "uses asks first")

    def invoke(self, context, event):
        scene = context.scene
        if self.family not in F.FAMILIES or self.family in F.ALWAYS:
            return {"CANCELLED"}
        if workspaces.family_on(scene, self.family):
            uses = workspaces.in_use(scene).get(self.family, [])
            if uses:
                self.warning = W.hide_warning(self.family, uses)
                return context.window_manager.invoke_props_dialog(
                    self, width=440, title=f"Hide {W.family_title(self.family)}?", confirm_text="Hide anyway")
        return self.execute(context)

    def draw(self, context):
        _lines(self.layout, self.warning, icon="INFO")

    def execute(self, context):
        scene = context.scene
        if self.family not in F.FAMILIES or self.family in F.ALWAYS:
            return {"CANCELLED"}
        on = not workspaces.family_on(scene, self.family)
        workspaces.set_tick(scene, self.family, on)
        self.report({"INFO"}, f"{W.family_title(self.family)}: {'shown' if on else 'hidden (its work stays)'}")
        return {"FINISHED"}


class FRESING_OT_workspace_show_used(bpy.types.Operator):
    """Shows every family of functions this project uses but does not show now (joints, a CNC machine, cables
    … that are set up in it)"""

    bl_idname = "fresing.workspace_show_used"
    bl_label = "Show what the project uses"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        shown = workspaces.show_used(context.scene)
        if shown:
            self.report({"INFO"}, "Shown: " + ", ".join(W.family_title(f) for f in shown))
        else:
            self.report({"INFO"}, "Everything this project uses is shown already")
        return {"FINISHED"}


class FRESING_OT_workspace_all(bpy.types.Operator):
    """Shows every function again: switches this project to the workspace All functions"""

    bl_idname = "fresing.workspace_all"
    bl_label = "Show everything"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        workspaces.switch(context.scene, W.DEFAULT)
        self.report({"INFO"}, "Every function is shown (workspace All functions)")
        return {"FINISHED"}


class FRESING_OT_workspace_save(bpy.types.Operator):
    """Saves what the side panel shows now as a workspace of your own: one file in a Workspaces folder (Fresing
    Settings > Locations). A colleague gets it by copying that file into their own folder, or through a shared
    folder. Saving under the name of one of your own workspaces replaces it"""

    bl_idname = "fresing.workspace_save"
    bl_label = "Save as my own workspace"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", description="The name of your workspace, for example \"Offshore cranes\"")
    note: StringProperty(name="Note", description="A line that says what this workspace is for (optional)")
    where: EnumProperty(name="Save in", items=locations.where_items("workspaces"),
                        description="The folder the workspace goes into: your own folders first, then the company's "
                                    "or department's folders you may write to (Fresing Settings > Locations)")

    def invoke(self, context, event):
        cur = workspaces.name_of(context.scene)
        self.name = cur if workspaces.is_own(cur) else ""
        from . import form_window
        return form_window.open(self, context, width=440, height=280, title="Save as my own workspace",
                                confirm="Save", icon="WORKSPACE")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "note")
        name = W.clean_name(self.name)
        if name and workspaces.is_own(name):
            _lines(layout, f"You have a workspace called '{name}' already: saving replaces it.", icon="ERROR")
        elif name and W.key_of(name):
            _lines(layout, f"'{name}' is the name of a built-in workspace: yours will be used instead of it.",
                   icon="INFO")
        if len(locations.save_choices("workspaces")) > 1:
            layout.prop(self, "where")
        else:
            path, _shared, problem = workspaces.folder()
            _lines(layout, problem or "It goes into: " + path, icon="ERROR" if problem else "FILE_FOLDER")

    def execute(self, context):
        try:
            path = workspaces.save_own(context.scene, self.name, self.note, where=locations.where_value(self.where))
        except (ValueError, OSError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Workspace '{W.clean_name(self.name)}' saved: {os.path.basename(path)}")
        return {"FINISHED"}


class FRESING_OT_workspace_rename(bpy.types.Operator):
    """Gives your own workspace another name (its file in your Workspaces folder is renamed). Other projects that
    use it keep their own copy under the old name"""

    bl_idname = "fresing.workspace_rename"
    bl_label = "Rename my workspace"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="New name", description="The new name of this workspace")

    @classmethod
    def poll(cls, context):
        if not workspaces.is_own(workspaces.name_of(context.scene)):
            cls.poll_message_set("Only a workspace of your own can be renamed: the built-in ones are fixed")
            return False
        return True

    def invoke(self, context, event):
        self.name = workspaces.name_of(context.scene)
        from . import form_window
        return form_window.open(self, context, width=400, height=150, title="Rename my workspace",
                                confirm="Rename", icon="GREASEPENCIL")

    def execute(self, context):
        old = workspaces.name_of(context.scene)
        try:
            workspaces.rename_own(context.scene, old, self.name)
        except (ValueError, OSError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Workspace '{old}' is now '{W.clean_name(self.name)}'")
        return {"FINISHED"}


class FRESING_OT_workspace_delete(bpy.types.Operator):
    """Deletes the file of your own workspace from your Workspaces folder. This project keeps showing what it
    shows now until you pick another workspace; other projects that use it keep their own copy"""

    bl_idname = "fresing.workspace_delete"
    bl_label = "Delete my workspace"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not workspaces.is_own(workspaces.name_of(context.scene)):
            cls.poll_message_set("Only a workspace of your own can be deleted: the built-in ones are fixed")
            return False
        return True

    def invoke(self, context, event):
        name = workspaces.name_of(context.scene)
        return context.window_manager.invoke_confirm(
            self, event, title=f"Delete the workspace '{name}'?",
            message="Its file is deleted from your Workspaces folder. Projects keep their own copy.",
            confirm_text="Delete", icon="WARNING")

    def execute(self, context):
        name = workspaces.name_of(context.scene)
        try:
            workspaces.delete_own(context.scene, name)
        except OSError as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Workspace '{name}' deleted from your Workspaces folder")
        return {"FINISHED"}


class FRESING_OT_workspace_refresh(bpy.types.Operator):
    """Reads your Workspaces folders again (Fresing Settings > Locations): a workspace file a colleague sent you
    shows up in the list after you copied it there"""

    bl_idname = "fresing.workspace_refresh"
    bl_label = "Refresh"

    def execute(self, context):
        locations.look_again()                    # task 0272: a folder made or brought back meanwhile is seen
        found = workspaces.library(force=True)
        self.report({"INFO"}, f"{plural(len(found), 'workspace')} of your own in your Workspaces folders")
        panels.redraw()
        return {"FINISHED"}


class FRESING_OT_workspace_folder(bpy.types.Operator):
    """Opens the folder with your own workspace files in Explorer: one .json file per workspace. Copy a file
    to a colleague's folder to share it"""

    bl_idname = "fresing.workspace_folder"
    bl_label = "Show in folder"

    def execute(self, context):
        from . import files
        path, _shared, problem = workspaces.folder(fresh=True)
        if problem:
            self.report({"WARNING"}, problem)
            return {"CANCELLED"}
        try:
            os.makedirs(path, exist_ok=True)
            files.open_path(path)
        except OSError as exc:
            return _report_error(self, exc)
        return {"FINISHED"}


class FRESING_OT_next_hide(bpy.types.Operator):
    """Hides the What's next card in this project (it also goes away by itself after the first render)"""

    bl_idname = "fresing.next_hide"
    bl_label = "Hide What's next"

    def execute(self, context):
        context.scene.fresing.next_hidden = True
        panels.redraw()
        return {"FINISHED"}


class FRESING_OT_next_go(bpy.types.Operator):
    """Opens the section of the side panel where the next step is"""

    bl_idname = "fresing.next_go"
    bl_label = "Open that section"

    panel: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        from ..core import places
        try:
            return f"Opens {places.where(properties.panel)} in the side panel, with the sections above it"
        except KeyError:
            return "Opens the part of the side panel where the next step is"

    def execute(self, context):
        if self.panel not in panels.PARENT:
            return {"CANCELLED"}
        panels.open_to(self.panel)
        return {"FINISHED"}


CLASSES = (FRESING_OT_workspace_pick, FRESING_OT_workspace_default, FRESING_OT_workspace_star, FRESING_MT_workspaces,
           FRESING_OT_family_toggle,
           FRESING_OT_workspace_show_used, FRESING_OT_workspace_all, FRESING_OT_workspace_save,
           FRESING_OT_workspace_rename, FRESING_OT_workspace_delete, FRESING_OT_workspace_refresh,
           FRESING_OT_workspace_folder, FRESING_OT_next_hide, FRESING_OT_next_go)
