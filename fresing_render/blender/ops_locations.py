"""Operators of Fresing Settings > Locations and Exports (task 0272), the project's "Save to", the set-up file
dropped on the window, and the STEP folders on the left of Import STEP's file browser.

All of them but ``fresing.out_place`` start with ``fresing.loc_`` (allowed in the Client view: nothing here changes the
model). The rules are in ``core/locations.py``, the state in ``locations.py``.
"""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, BoolVectorProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core import locations as L
from . import locations


def _redraw() -> None:
    try:
        from . import ops_setup
        ops_setup.redraw_all()
    except Exception:  # noqa: BLE001
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()


def _kind_items(_self, _context):
    return _KIND_ITEMS


_KIND_ITEMS = [(k.key, k.title, k.note) for k in L.KINDS]
_PLACE_ITEMS: list = []
_ALSO_ITEMS: list = []
_OUT_ITEMS: list = []


def _place_items(_self, _context):
    _PLACE_ITEMS[:] = [(p.key, p.name, f"{p.badge}: {p.path or p.name}") for p in locations.places()]
    return _PLACE_ITEMS


def _also_items(_self, _context):
    _ALSO_ITEMS[:] = [(p.key, p.name, f"{p.badge}: {p.path or p.name}") for p in locations.places()]
    return _ALSO_ITEMS


def _out_items(_self, context):
    d = L.find_place(locations.places(), locations.default_place())
    _OUT_ITEMS[:] = [("DEFAULT", f"Default ({d.name if d else '–'})", "Your default export place (Fresing Settings > "
                                                                       "Exports)")]
    _OUT_ITEMS.extend((p.key, p.name, f"{p.badge}: {p.path or p.name}") for p in locations.places())
    return _OUT_ITEMS


# ---------------------------------------------------------------------------------------------------------------------
# set-up files

_MODES = [("AUTO", "Link on a network, else copy", "A file on a server (\\\\server\\share) is linked, any other copied"),
          ("LINK", "Link to it where it lies", "The app reads the file where it is: when it changes there, the app "
                                               "takes the new version at its next start"),
          ("COPY", "Copy it into the app", "The app keeps a copy of its own: the file may be moved or deleted after")]


def _mode(value: str) -> str:
    return {"LINK": "link", "COPY": "copy"}.get(value, "")


class FRESING_OT_loc_setup_add(bpy.types.Operator, ImportHelper):
    """Brings in a set-up file (.frsetup) from your company or department: its folders for models, logos, materials,
    rule sets …, its export places and settings. A newer version of a set-up you have (same set-up, any file name)
    shows what changes first. You can also drop the file on the app's window"""

    bl_idname = "fresing.loc_setup_add"
    bl_label = "Add a set-up file…"
    bl_options = {"REGISTER"}

    filename_ext = L.SETUP_EXT
    filter_glob: StringProperty(default="*" + L.SETUP_EXT, options={"HIDDEN"})
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"},
                             description="The set-up file to bring in")
    directory: StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"})
    mode: EnumProperty(name="Keep it", items=_MODES, default="AUTO",
                       description="Link: the app reads the file where it lies and takes a changed one at its next "
                                   "start (good for a network folder). Copy: the app keeps its own copy")

    def invoke(self, context, event):
        if self.filepath and os.path.isfile(self.filepath):          # dropped on the window
            return self.execute(context)
        return ImportHelper.invoke(self, context, event)

    def draw(self, context):
        self.layout.prop(self, "mode")

    def execute(self, context):
        path = self.filepath
        try:
            new, old, lines = locations.check(path)
        except L.SetupError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if old is not None:
            if not lines:
                self.report({"INFO"}, f"{new.title()} is already in use: nothing changed")
                return {"CANCELLED"}
            bpy.ops.fresing.loc_setup_update("INVOKE_DEFAULT", filepath=path, mode=self.mode)
            return {"FINISHED"}
        try:
            s = locations.install(path, _mode(self.mode))
        except (L.SetupError, OSError) as exc:
            self.report({"ERROR"}, f"Not added: {exc}")
            return {"CANCELLED"}
        note = f"Set-up added: {s.name} ({s.title()})" + (" – " + "; ".join(s.notes) if s.notes else "")
        self.report({"INFO"}, note)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_setup_update(bpy.types.Operator):
    """Replaces a set-up you have by another file of the same set-up (newer, older or with other content), after
    showing what changes. Keep the old one: cancel"""

    bl_idname = "fresing.loc_setup_update"
    bl_label = "Update the set-up"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    mode: StringProperty(default="AUTO", options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        try:
            new, old, _lines = locations.check(self.filepath)
        except L.SetupError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        how = L.compare(old, new) if old else "newer"
        title = {"newer": f"Update {new.badge} from version {old.version if old else '–'} to {new.version}?",
                 "older": f"Go back to version {new.version} of {new.badge}?",
                 "same": f"{new.badge} v{new.version}: the same version with other content"}[how]
        return context.window_manager.invoke_props_dialog(self, width=520, title=title,
                                                          confirm_text="Go back" if how == "older" else "Update",
                                                          cancel_default=True)

    def draw(self, context):
        layout = self.layout
        try:
            new, old, lines = locations.check(self.filepath)
        except L.SetupError as exc:
            layout.label(text=str(exc), icon="ERROR")
            return
        if old is not None and L.compare(old, new) == "older":
            col = layout.column()
            col.alert = True
            col.label(text=f"This file is OLDER than the one in use (version {old.version}).", icon="ERROR")
        layout.label(text="What changes:")
        col = layout.column(align=True)
        for line in lines[:18]:
            col.label(text="•  " + line)
        if len(lines) > 18:
            col.label(text=f"… and {len(lines) - 18} more")
        layout.label(text="Cancel keeps the old one.", icon="INFO")

    def execute(self, context):
        try:
            new, old, lines = locations.check(self.filepath)
            was = old.version if old else None
            locations.install(self.filepath, _mode(self.mode))
        except (L.SetupError, OSError) as exc:
            self.report({"ERROR"}, f"Not updated: {exc}")
            return {"CANCELLED"}
        locations.state()["updated"].append({"id": new.id, "at": L.now_text(), "lines": lines,
                                             "text": f"{new.badge} set-up: version {was} → {new.version}"})
        locations.save_state()
        self.report({"INFO"}, f"{new.badge} set-up now at version {new.version}")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_setup_remove(bpy.types.Operator):
    """Takes this set-up out of the app: its folders, export places and content are no longer used (your own
    folders and settings stay). The file itself is not deleted"""

    bl_idname = "fresing.loc_setup_remove"
    bl_label = "Remove"
    bl_options = {"INTERNAL"}

    sid: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title="Remove this set-up?", confirm_text="Remove")

    def execute(self, context):
        if not locations.remove(self.sid):
            return {"CANCELLED"}
        self.report({"INFO"}, "Set-up removed")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_reload(bpy.types.Operator):
    """Looks at every folder again and reads linked set-up files again where they lie (a changed one is taken in,
    with its list of changes)"""

    bl_idname = "fresing.loc_reload"
    bl_label = "Look again"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        locations.look_again()
        out = locations.refresh(force=True)
        self.report({"INFO"}, "; ".join(out) if out else "Folders and set-ups looked at again")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_setup_changes(bpy.types.Operator):
    """Shows what the last update of this set-up changed"""

    bl_idname = "fresing.loc_setup_changes"
    bl_label = "Show changes"
    bl_options = {"INTERNAL"}

    sid: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        layout = self.layout
        ups = [u for u in locations.state()["updated"] if u.get("id") == self.sid]
        if not ups:
            layout.label(text="No update of this set-up yet")
            return
        u = ups[-1]
        layout.label(text=f"{u.get('text', '')}  ({u.get('at', '')})", icon="FILE_REFRESH")
        col = layout.column(align=True)
        for line in (u.get("lines") or [])[:20]:
            col.label(text="•  " + line)

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_loc_setup_save(bpy.types.Operator, ExportHelper):
    """Saves your settings, folders and export places as ONE set-up file (.frsetup) to hand to colleagues: they add
    it in Fresing Settings > Locations. Tick what goes in, and which of your folders' content is packed inside.
    Saving over a file of the same set-up raises its version by itself"""

    bl_idname = "fresing.loc_setup_save"
    bl_label = "Save as a set-up file…"
    bl_options = {"REGISTER"}

    filename_ext = L.SETUP_EXT
    filter_glob: StringProperty(default="*" + L.SETUP_EXT, options={"HIDDEN"})
    sid: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    name: StringProperty(name="Name", default="Our set-up",
                         description="What the set-up is called, e.g. \"Fresing standard\"")
    level: EnumProperty(name="Level", default="company",
                        items=[("company", "Company", "For everyone in the company"),
                               ("department", "Department", "For one department or team")],
                        description="Company or Department: the badge its folders and items show")
    label: StringProperty(name="Label", default="",
                          description="The badge shown next to its items, e.g. \"Offshore department\". Empty: "
                                      "Company or Department")
    with_settings: BoolProperty(name="Settings", default=True,
                                description="The Fresing Settings you changed (default template, rule set, workspace, "
                                            "lesson colours …)")
    with_folders: BoolProperty(name="My folders (as paths)", default=True,
                               description="Your own folders, by their path: good for folders on a network share every "
                                           "PC can reach. A folder whose content is packed below is not added twice")
    with_exports: BoolProperty(name="Export places", default=True,
                               description="Your own export places (Fresing Settings > Exports)")
    pack: BoolVectorProperty(name="Pack", size=len(L.KINDS), default=(False,) * len(L.KINDS),
                             description="Put the content of your first folder of this kind inside the file, so a "
                                         "colleague without the network share gets it too")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = os.path.join(locations.documents(), L.safe_folder(self.name) + L.SETUP_EXT)
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "level")
        layout.prop(self, "label")
        layout.label(text="Put in:")
        col = layout.column(align=True)
        col.prop(self, "with_settings")
        col.prop(self, "with_folders")
        col.prop(self, "with_exports")
        content = locations.user_content()
        layout.label(text="Pack the content of:")
        col = layout.column(align=True)
        for i, k in enumerate(L.KINDS):
            row = col.row()
            row.enabled = k.key in content
            row.prop(self, "pack", index=i, text=k.title)

    def execute(self, context):
        path = self.filepath if self.filepath.lower().endswith(L.SETUP_EXT) else self.filepath + L.SETUP_EXT
        try:
            s = build_setup(self, path)
            content = {k.key: locations.user_content().get(k.key) for i, k in enumerate(L.KINDS) if self.pack[i]}
            L.write_setup(path, s, {k: v for k, v in content.items() if v})
        except (L.SetupError, OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Not saved: {exc}")
            return {"CANCELLED"}
        e = locations.entry(s.id)
        if e is not None:                       # editing one in use: take the new version in
            try:
                locations.install(path, e.get("mode") or "", auto=e.get("auto", False))
            except (L.SetupError, OSError) as exc:
                self.report({"WARNING"}, f"Saved, but not taken in: {exc}")
        self.report({"INFO"}, f"Set-up saved: {os.path.basename(path)} ({s.title()})")
        _redraw()
        return {"FINISHED"}


def build_setup(op, path: str) -> L.Setup:
    """The Setup the Save dialog describes; its version one higher than a file of the same set-up already there."""
    from .. import __version__
    import getpass
    sid = op.sid or ""
    version = 1
    if os.path.isfile(path):
        try:
            there = L.read_setup(path)
            if not sid or there.id == sid:
                sid, version = there.id, there.version + 1
        except L.SetupError:
            pass
    inuse = locations.setup_of(sid) if sid else None
    if inuse is not None:
        version = max(version, inuse.version + 1)
    s = L.Setup(id=sid or L.new_id(), name=op.name.strip() or "Set-up", level=op.level, label=op.label.strip(),
                version=version, date=L.now_text(), app=__version__)
    try:
        s.made_by = getpass.getuser()
    except Exception:  # noqa: BLE001
        s.made_by = ""
    if inuse is not None:
        s.settings = dict(inuse.settings)
        s.locations = {k: list(v) for k, v in inuse.locations.items()}
        s.exports = [dict(e) for e in inuse.exports]
        s.first_start = dict(inuse.first_start)
    if op.with_settings:
        for row in locations.differences():
            if row.key.startswith("setting:"):
                name = row.key.split(":", 1)[1]
                p = locations._prefs()
                v = getattr(p, name)
                s.settings[name] = list(v) if not isinstance(v, (str, int, float, bool)) else v
    packed = {k.key for i, k in enumerate(L.KINDS) if op.pack[i]}
    if op.with_folders:
        for k in L.KINDS:
            for f in locations.mine_list(k.key):
                if f["on"] and not f.get("ready") and k.key not in packed and f["path"] not in s.locations.get(k.key, []):
                    s.locations.setdefault(k.key, []).append(f["path"])
    if op.with_exports:
        names = {e["name"] for e in s.exports}
        s.exports += [dict(e) for e in locations.state()["exports"]["own"] if e["name"] not in names]
    return s


class FRESING_OT_loc_setup_edit(bpy.types.Operator):
    """Edits this set-up file for everyone who uses it (for the one who looks after it): the same dialog as Save
    as a set-up file, writing the file back where it lies with its version raised. Windows' file rights decide
    who may do it"""

    bl_idname = "fresing.loc_setup_edit"
    bl_label = "Edit this set-up file…"
    bl_options = {"INTERNAL"}

    sid: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        e = locations.entry(self.sid)
        s = locations.setup_of(self.sid)
        if e is None or s is None:
            return {"CANCELLED"}
        target = e.get("source") if e.get("mode") == "link" else e.get("file")
        if not target or not L.writable(os.path.dirname(target)) or (os.path.exists(target)
                                                                     and not os.access(target, os.W_OK)):
            self.report({"ERROR"}, f"You may not change {target}: ask whoever looks after this set-up")
            return {"CANCELLED"}
        packed = [k.key in s.content for k in L.KINDS]
        bpy.ops.fresing.loc_setup_save("INVOKE_DEFAULT", filepath=target, sid=s.id, name=s.name, level=s.level,
                                       label=s.label, with_settings=False, with_folders=False, with_exports=False,
                                       pack=packed)
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# Mine folders

class FRESING_OT_loc_folder_add(bpy.types.Operator, ImportHelper):
    """Adds a folder of your own for this kind: what is in it shows in the app's lists next to the company's and
    department's, with the badge Mine"""

    bl_idname = "fresing.loc_folder_add"
    bl_label = "Add a folder…"
    bl_options = {"INTERNAL"}

    kind: EnumProperty(items=_kind_items, options={"SKIP_SAVE", "HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH")
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    filename_ext = ""

    def execute(self, context):
        folder = (self.directory or os.path.dirname(self.filepath)).rstrip("\\/")
        if not folder:
            return {"CANCELLED"}
        if not locations.add_mine(self.kind, folder):
            self.report({"INFO"}, "That folder is in the list already")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{L.kind(self.kind).title}: {folder} added")
        _redraw()
        return {"FINISHED"}


class _MineOp:
    kind: EnumProperty(items=_kind_items, options={"SKIP_SAVE", "HIDDEN"})
    index: IntProperty(options={"SKIP_SAVE", "HIDDEN"})


class FRESING_OT_loc_folder_remove(_MineOp, bpy.types.Operator):
    """Takes this folder out of the list (nothing in it is deleted)"""
    bl_idname = "fresing.loc_folder_remove"
    bl_label = "Remove folder"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        locations.remove_mine(self.kind, self.index)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_folder_move(_MineOp, bpy.types.Operator):
    """Moves this folder up or down: the top folder is the first choice (where new things are saved)"""
    bl_idname = "fresing.loc_folder_move"
    bl_label = "Move folder"
    bl_options = {"INTERNAL"}

    step: IntProperty(default=-1, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        locations.move_mine(self.kind, self.index, self.step)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_folder_on(_MineOp, bpy.types.Operator):
    """Switches this folder on or off: an off folder is not read and nothing is saved into it"""
    bl_idname = "fresing.loc_folder_on"
    bl_label = "On"
    bl_options = {"INTERNAL"}

    on: BoolProperty(default=True, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        locations.set_on(self.kind, self.index, self.on)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_mine_all_on(bpy.types.Operator):
    """Switches on all of your ready-made folders (Documents\\Fresing Render\\Library), next to the organisation's"""
    bl_idname = "fresing.loc_mine_all_on"
    bl_label = "Switch my folders on"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        for k in L.KIND_KEYS:
            for i, f in enumerate(locations.mine_list(k)):
                if f.get("ready") and not f["on"]:
                    locations.set_on(k, i, True)
        locations.state()["note_off"] = False
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_note_ok(bpy.types.Operator):
    """Hides this note (your own folders stay as they are)"""
    bl_idname = "fresing.loc_note_ok"
    bl_label = "OK"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        locations.state()["note_off"] = False
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_show(bpy.types.Operator):
    """Shows this folder in Explorer (made first when it is one of your own that is not there yet)"""
    bl_idname = "fresing.loc_show"
    bl_label = "Show in folder"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        from . import files
        try:
            if not os.path.isdir(self.path) and L.writable(self.path):
                os.makedirs(self.path, exist_ok=True)
            files.open_path(self.path)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open {self.path}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_loc_back(bpy.types.Operator):
    """Puts this one of your own choices back to the app's standard"""
    bl_idname = "fresing.loc_back"
    bl_label = "Back to standard"
    bl_options = {"INTERNAL"}

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        if not locations.back_to_standard(self.key):
            return {"CANCELLED"}
        _redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# export places

class FRESING_OT_loc_place_add(bpy.types.Operator, ImportHelper):
    """Adds an export place of your own (a folder, e.g. on the marketing share): outputs can go there with Save to"""
    bl_idname = "fresing.loc_place_add"
    bl_label = "Add an export place…"
    bl_options = {"INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    filename_ext = ""
    name: StringProperty(name="Name", default="", description="What the place is called in the lists, e.g. "
                                                              "\"Marketing share\". Empty: the folder's name")
    project_sub: BoolProperty(name="A folder per project", default=True,
                              description="Each project's outputs go into a sub-folder named after the project")

    def draw(self, context):
        self.layout.prop(self, "name")
        self.layout.prop(self, "project_sub")

    def execute(self, context):
        folder = (self.directory or os.path.dirname(self.filepath)).rstrip("\\/")
        if not folder:
            return {"CANCELLED"}
        name = self.name.strip() or os.path.basename(folder) or folder
        own = locations.state()["exports"]["own"]
        if any(e["name"] == name for e in own):
            self.report({"ERROR"}, f"There is a place called '{name}' already: give another name")
            return {"CANCELLED"}
        own.append({"name": name, "path": folder, "project_sub": bool(self.project_sub)})
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_place_remove(bpy.types.Operator):
    """Takes this export place of yours out of the list (nothing in its folder is deleted)"""
    bl_idname = "fresing.loc_place_remove"
    bl_label = "Remove place"
    bl_options = {"INTERNAL"}

    name: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        locations.back_to_standard("export:own:" + self.name)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_place_default(bpy.types.Operator):
    """Makes this the place where pictures, videos and 3D pages go unless a project picks another"""
    bl_idname = "fresing.loc_place_default"
    bl_label = "Default export place"
    bl_options = {"INTERNAL"}
    bl_property = "place"

    place: EnumProperty(items=_place_items, name="Place")

    def execute(self, context):
        locations.state()["exports"]["default"] = self.place
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_also(bpy.types.Operator):
    """Also saves a copy of every picture, video and 3D page into a second place (e.g. the company share), after
    it is saved in its own place"""
    bl_idname = "fresing.loc_also"
    bl_label = "Also save a copy"
    bl_options = {"INTERNAL"}

    on: BoolProperty(default=True, options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        ex = locations.state()["exports"]
        ex["also"] = bool(self.on)
        if self.on and not ex["also_to"]:
            others = [p for p in locations.places() if p.key != locations.default_place()]
            ex["also_to"] = others[0].key if others else ""
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_loc_also_to(bpy.types.Operator):
    """The place the extra copy goes to"""
    bl_idname = "fresing.loc_also_to"
    bl_label = "Copy to"
    bl_options = {"INTERNAL"}
    bl_property = "place"

    place: EnumProperty(items=_also_items, name="Place")

    def execute(self, context):
        ex = locations.state()["exports"]
        ex["also_to"], ex["also"] = self.place, True
        locations.save_state()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_out_place(bpy.types.Operator):
    """Where this project's pictures, videos and 3D pages go: one of the export places (Fresing Settings > Exports),
    or Default for your default place"""
    bl_idname = "fresing.out_place"
    bl_label = "Save to"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "place"

    place: EnumProperty(items=_out_items, name="Place")

    def execute(self, context):
        s = context.scene.fresing
        s.out_place = "" if self.place == "DEFAULT" else self.place
        _redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------------------------------------------------
# drop a set-up file on the window; the STEP folders beside Import STEP

class FRESING_FH_setup(bpy.types.FileHandler):
    """A .frsetup file dropped on the 3D view brings that set-up in (as Add a set-up file…)."""
    bl_idname = "FRESING_FH_setup"
    bl_label = "Fresing set-up file"
    bl_import_operator = "fresing.loc_setup_add"
    bl_file_extensions = L.SETUP_EXT

    @classmethod
    def poll_drop(cls, context):
        return getattr(context, "area", None) is not None and context.area.type in ("VIEW_3D", "OUTLINER")


class FRESING_OT_loc_browse(bpy.types.Operator):
    """Shows this STEP models folder in the file browser"""
    bl_idname = "fresing.loc_browse"
    bl_label = "Go to folder"
    bl_options = {"INTERNAL"}

    path: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        params = getattr(getattr(context, "space_data", None), "params", None)
        if params is None:
            return {"CANCELLED"}
        try:
            params.directory = self.path.encode("utf-8")
        except TypeError:
            params.directory = self.path
        return {"FINISHED"}


class FRESING_PT_step_locations(bpy.types.Panel):
    """The STEP models folders (Company, Department, Mine) on the left of Import STEP's file browser."""
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Bookmarks"
    bl_label = "STEP folders"

    @classmethod
    def poll(cls, context):
        op = getattr(getattr(context, "space_data", None), "active_operator", None)
        return op is not None and getattr(op, "bl_idname", "") == "FRESING_OT_import_step"

    def draw(self, context):
        col = self.layout.column(align=True)
        locs = locations.folders("step")
        if not locs:
            col.label(text="None yet: Fresing Settings > Locations")
        for loc in locs:
            row = col.row(align=True)
            row.enabled = bool(loc.reach)
            name = os.path.basename(loc.path.rstrip("\\/")) or loc.path
            row.operator("fresing.loc_browse", text=f"{name}  ·  {loc.badge}",
                         icon="FILE_FOLDER" if loc.reach else "ERROR").path = loc.path


CLASSES = (FRESING_OT_loc_setup_add, FRESING_OT_loc_setup_update, FRESING_OT_loc_setup_remove, FRESING_OT_loc_reload,
           FRESING_OT_loc_setup_changes, FRESING_OT_loc_setup_save, FRESING_OT_loc_setup_edit, FRESING_OT_loc_folder_add,
           FRESING_OT_loc_folder_remove, FRESING_OT_loc_folder_move, FRESING_OT_loc_folder_on,
           FRESING_OT_loc_mine_all_on, FRESING_OT_loc_note_ok, FRESING_OT_loc_show, FRESING_OT_loc_back,
           FRESING_OT_loc_place_add, FRESING_OT_loc_place_remove, FRESING_OT_loc_place_default, FRESING_OT_loc_also,
           FRESING_OT_loc_also_to, FRESING_OT_out_place, FRESING_FH_setup, FRESING_OT_loc_browse,
           FRESING_PT_step_locations)
