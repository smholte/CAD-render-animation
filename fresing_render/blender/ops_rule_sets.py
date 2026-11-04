"""Operators for rule sets (3 Looks, top): pick, switch, save, copy, start empty, rename, delete."""

from __future__ import annotations

import os
import textwrap

import bpy
from bpy.props import EnumProperty, StringProperty

from ..core import rule_sets as RS
from . import rule_sets

# Blender keeps only references to enum item strings: they live in module globals.
_ITEMS: dict[str, list] = {"all": [], "library": [], "editable": []}
_PREVIEW: dict[str, list[str]] = {"lines": [], "warning": []}


def _describe(rs: RS.RuleSet) -> str:
    n = len(rs.rules)
    text = f"{n} rule{'s' if n != 1 else ''}"
    own = len(rs.own_looks())
    if own:
        text += f", {own} own group look{'s' if own != 1 else ''}"
    return f"{rs.note} ({text})" if rs.note else text


def _all_items(self, context):
    """Standard, the rule sets in the library, and this project's own one if it is not in the library."""
    items = [(RS.STANDARD, RS.STANDARD, _describe(RS.standard()), "LOCKED", 0)]
    for i, (name, (_path, rs)) in enumerate(sorted(rule_sets.library().items(), key=lambda kv: kv[0].casefold())):
        items.append((name, name, _describe(rs), "FILE", i + 1))
    s = context.scene.fresing if context and context.scene else None
    if s is not None and s.rule_set and s.rule_set != RS.STANDARD and s.rule_set not in rule_sets.library():
        items.append((s.rule_set, f"{s.rule_set} (only in this project)",
                      "Not in the library: the project keeps its own copy", "FILE_BLEND", len(items)))
    _ITEMS["all"] = items
    return items


def _library_items(self, context):
    """Only the rule sets in the library (what can be deleted)."""
    items = [(name, name, _describe(rs), "FILE", i)
             for i, (name, (_p, rs)) in enumerate(sorted(rule_sets.library().items(), key=lambda kv: kv[0].casefold()))]
    _ITEMS["library"] = items or [("", "No rule sets in the library yet", "Copy Standard to make one", "INFO", 0)]
    return _ITEMS["library"]


def _editable_items(self, context):
    """Rule sets that can be renamed: those in the library, and this project's own one."""
    items = list(_library_items(self, context)) if rule_sets.library() else []
    s = context.scene.fresing if context and context.scene else None
    if s is not None and s.rule_set and s.rule_set != RS.STANDARD and s.rule_set not in rule_sets.library():
        items.append((s.rule_set, f"{s.rule_set} (only in this project)", "", "FILE_BLEND", len(items)))
    _ITEMS["editable"] = items or [("", "Nothing to rename: copy Standard first", "", "INFO", 0)]
    return _ITEMS["editable"]


def _dialog_lines(layout, lines: list[str], icon: str = "NONE", alert: bool = False, width: int = 64) -> None:
    col = layout.column(align=True)
    col.alert = alert
    for k, line in enumerate(lines):
        for j, part in enumerate(textwrap.wrap(line, width) or [""]):
            col.label(text=part, icon=(icon if j == 0 else "BLANK1") if icon != "NONE" else "NONE")


def _unsaved_warning(s, leaving: bool = True) -> list[str]:
    if not rule_sets.is_changed(s):
        return []
    what = RS.describe_differences(rule_sets.differences(s))
    return [f"Your changes to '{s.rule_set}' ({what}) are not saved in the library: "
            + ("they are gone after this (Undo brings them back)." if leaving else "they stay in this project.")]


def _redraw(context) -> None:
    """The side panel shows the rule set and its state: draw it again after a change."""
    screen = getattr(context, "screen", None)
    for area in (screen.areas if screen else []):
        if area.type == "VIEW_3D":
            area.tag_redraw()


def _report_error(op, exc: Exception) -> set:
    op.report({"ERROR"}, str(exc) or exc.__class__.__name__)
    return {"CANCELLED"}


class FRESING_OT_rule_set_switch(bpy.types.Operator):
    """Use another rule set for this project: its sorting rules, group names and materials. Shows first
    what will change. Parts you put in a group by hand stay there; Undo goes back"""

    bl_idname = "fresing.rule_set_switch"
    bl_label = "Switch rule set"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "name"

    name: EnumProperty(name="Rule set", items=_all_items,
                       description="The rule set to use: Standard (built in), one from the library, "
                                   "or this project's own")

    def _target(self, context):
        s = context.scene.fresing
        if self.name == s.rule_set and rule_sets.kind(s) == "project":
            return None
        return rule_sets.find(self.name)

    def invoke(self, context, event):
        s = context.scene.fresing
        rs = self._target(context)
        if rs is None:
            self.report({"INFO"}, f"'{self.name}' is only in this project: it is already in use")
            return {"CANCELLED"}
        _PREVIEW["lines"] = rule_sets.describe_preview(rule_sets.preview(context.scene, rs))
        _PREVIEW["warning"] = _unsaved_warning(s)
        same = self.name == s.rule_set
        title = (f"Load '{self.name}' again from the library?" if same
                 else f"Switch to rule set '{self.name}'?")
        return context.window_manager.invoke_props_dialog(self, width=420, title=title,
                                                          confirm_text="Load" if same else "Switch")

    def draw(self, context):
        layout = self.layout
        _dialog_lines(layout, _PREVIEW["lines"], icon="INFO")
        if _PREVIEW["warning"]:
            layout.separator()
            _dialog_lines(layout, _PREVIEW["warning"], icon="ERROR", alert=True)

    def execute(self, context):
        rs = self._target(context)
        if rs is None:
            self.report({"WARNING"}, f"Rule set '{self.name}' not found (is the library reachable?)")
            return {"CANCELLED"}
        res = rule_sets.switch(context.scene, rs)
        self.report({"INFO"}, f"Rule set '{rs.name}': {res['groups']} groups, {res['unsorted']} unsorted parts")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_save(bpy.types.Operator):
    """Save this project's changes (rules, group names and materials) into its rule set in the library.
    Other projects that use it get them when they load it again"""

    bl_idname = "fresing.rule_set_save"
    bl_label = "Save to rule set"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return bool(s.rule_set) and s.rule_set != RS.STANDARD

    def invoke(self, context, event):
        s = context.scene.fresing
        what = RS.describe_differences(rule_sets.differences(s)) or "no changes"
        return context.window_manager.invoke_confirm(
            self, event, title=f"Save to rule set '{s.rule_set}'?",
            message=f"Changes: {what}. Other projects that use '{s.rule_set}' keep their own copy until they "
                    "load it again.",
            confirm_text="Save")

    def execute(self, context):
        try:
            path = rule_sets.save_to_library(context.scene)
        except (OSError, ValueError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Rule set saved: {path}")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_save_as(bpy.types.Operator):
    """Save this project's rule set as it is now under a new name in the library (a copy you can change);
    the project uses the new one from now on"""

    bl_idname = "fresing.rule_set_save_as"
    bl_label = "Save as new rule set"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", description="Name of the new rule set, e.g. your company or client")

    def invoke(self, context, event):
        s = context.scene.fresing
        base = s.rule_set if s.rule_set and s.rule_set != RS.FROM_PROJECT else "My rule set"
        if base.startswith("From template"):
            base = "My rule set"
        names = set(rule_sets.library(force=True))
        name, i = (f"{base} copy" if base in names or base == RS.STANDARD else base), 2
        first = name
        while name in names:
            name = f"{first} {i}"
            i += 1
        self.name = name
        return context.window_manager.invoke_props_dialog(self, width=360, title="Save as new rule set",
                                                          confirm_text="Save")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        path, shared, _problem = rule_sets.folder()
        where = "the shared library" if shared else "this PC"
        _dialog_lines(layout, [f"Saved in {where}: {path}"], width=56)

    def execute(self, context):
        try:
            path = rule_sets.save_as(context.scene, self.name)
        except (OSError, ValueError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Rule set saved: {path}")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_new_empty(bpy.types.Operator):
    """Start a new rule set with no rules: every part goes to 'Unsorted', then you build it up with
    Find & sort parts and 'Make it a rule'. Parts you put in a group by hand stay there"""

    bl_idname = "fresing.rule_set_new_empty"
    bl_label = "New, empty rule set"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="New rule set",
                         description="Name of the new rule set, e.g. your company or client")

    def invoke(self, context, event):
        s = context.scene.fresing
        _PREVIEW["lines"] = rule_sets.describe_preview(rule_sets.preview(context.scene, RS.empty("")))
        _PREVIEW["warning"] = _unsaved_warning(s)
        names = set(rule_sets.library(force=True))
        name, i = "New rule set", 2
        while name in names:
            name = f"New rule set {i}"
            i += 1
        self.name = name
        return context.window_manager.invoke_props_dialog(self, width=420, title="New, empty rule set",
                                                          confirm_text="Start")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        _dialog_lines(layout, _PREVIEW["lines"], icon="INFO")
        if _PREVIEW["warning"]:
            _dialog_lines(layout, _PREVIEW["warning"], icon="ERROR", alert=True)

    def execute(self, context):
        try:
            rs = rule_sets.new_empty(self.name)
        except (OSError, ValueError) as exc:
            return _report_error(self, exc)
        res = rule_sets.switch(context.scene, rs)
        self.report({"INFO"}, f"Rule set '{rs.name}' started: {res['unsorted']} parts unsorted")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_rename(bpy.types.Operator):
    """Rename a rule set. Other projects that use it keep their own copy under the old name"""

    bl_idname = "fresing.rule_set_rename"
    bl_label = "Rename rule set"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "name"

    name: EnumProperty(name="Rule set", items=_editable_items, description="The rule set to rename")
    new_name: StringProperty(name="New name", description="The new name of the rule set")

    def invoke(self, context, event):
        if not self.name:
            self.report({"INFO"}, "Nothing to rename: copy Standard first")
            return {"CANCELLED"}
        self.new_name = self.name
        return context.window_manager.invoke_props_dialog(self, width=360, title=f"Rename '{self.name}'",
                                                          confirm_text="Rename")

    def draw(self, context):
        self.layout.prop(self, "new_name")

    def execute(self, context):
        if not self.name:
            return {"CANCELLED"}
        try:
            new = rule_sets.rename(context.scene, self.name, self.new_name)
        except (OSError, ValueError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Rule set '{self.name}' is now '{new}'")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_delete(bpy.types.Operator):
    """Delete a rule set from the library. Projects that use it keep their own copy"""

    bl_idname = "fresing.rule_set_delete"
    bl_label = "Delete rule set"
    bl_property = "name"

    name: EnumProperty(name="Rule set", items=_library_items, description="The rule set to delete")

    def invoke(self, context, event):
        if not self.name:
            self.report({"INFO"}, "There are no rule sets in the library")
            return {"CANCELLED"}
        return context.window_manager.invoke_confirm(
            self, event, title=f"Delete rule set '{self.name}'?",
            message="The file is removed from the library. Projects that use it keep their own copy.",
            confirm_text="Delete", icon="WARNING")

    def execute(self, context):
        if not self.name:
            return {"CANCELLED"}
        try:
            rule_sets.delete(self.name)
        except (OSError, ValueError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"Rule set '{self.name}' deleted")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_default(bpy.types.Operator):
    """The rule set every new project starts with (saved in the preferences)"""

    bl_idname = "fresing.rule_set_default"
    bl_label = "Default rule set"
    bl_property = "name"

    name: EnumProperty(name="Rule set", items=_all_items, description="The rule set new projects start with")

    def execute(self, context):
        from . import prefs
        p = prefs.get()
        if p is None:
            self.report({"WARNING"}, "The Fresing Render preferences are not available")
            return {"CANCELLED"}
        p.default_rule_set = self.name
        try:
            context.preferences.is_dirty = True          # saved with the preferences when the app closes
        except (AttributeError, TypeError):
            pass
        self.report({"INFO"}, f"New projects start with rule set '{self.name}'")
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_rule_set_folder(bpy.types.Operator):
    """Open the folder with the rule-set files (one .json file per rule set)"""

    bl_idname = "fresing.rule_set_folder"
    bl_label = "Show rule-set folder"

    def execute(self, context):
        from . import files
        path, _shared, problem = rule_sets.folder()
        if problem:
            self.report({"WARNING"}, problem)
            return {"CANCELLED"}
        try:
            os.makedirs(path, exist_ok=True)
            files.open_path(path)
        except OSError as exc:
            return _report_error(self, exc)
        return {"FINISHED"}


CLASSES = (FRESING_OT_rule_set_switch, FRESING_OT_rule_set_save, FRESING_OT_rule_set_save_as,
           FRESING_OT_rule_set_new_empty, FRESING_OT_rule_set_rename, FRESING_OT_rule_set_delete,
           FRESING_OT_rule_set_default, FRESING_OT_rule_set_folder)
