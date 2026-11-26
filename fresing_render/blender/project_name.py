"""Project names (task 0291): a new project is named after its first model; Save as offers "<name> (1)".

* **Save** (Ctrl+S, File > Save, the Client view's File > Save) of a project never saved opens Blender's file browser
  with the name filled in: the first model imported (``core/project_name.proposal``), in the first model's STEP
  folder (Locations, task 0272, has no projects folder). Setting Settings > General "Name of a new project": First
  model's name / Leave empty. A saved project: Blender's own Save, unchanged.
* **Save as…** (Ctrl+Shift+S, File > Save As…) of a saved project opens a small box with "<name> (1)" – the next free
  number in the project's folder – already selected: type over it, Save. "Other folder…" opens Blender's browser with
  that name. A project never saved: as Save.
* Blender's File menu keeps all its entries: its own draw runs with a stand-in layout that hands its Save and Save As
  entries to the app's operators (``_file_menu``); every other entry and every appended function stay Blender's.
* **Any other way to the save browser** (the "Save changes?" question when closing, Save as and update …): a draw
  handler of the file browser fills in the proposal once when Blender's own name ("untitled.blend") is there.
* An already saved project is never renamed by the app (``wm.save_mainfile`` on a saved project is left alone).
"""

from __future__ import annotations

import os

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty

from ..core import project_name as core

BLENDER_DEFAULT = ("untitled.blend", "", ".blend")   # the names Blender puts in a new project's save browser (".blend":
                                                     # what it makes of an empty name)
_S: dict = {"handler": None, "done": set(), "keys": [], "menu": None}
FILLED = [0]                                  # browsers the fallback filled in (tests, the PC check)


# ---------------------------------------------------------------------------
# the first model and the proposal
# ---------------------------------------------------------------------------

def first_model(scene=None):
    """The model root imported first (``build.PROP_IMPORTED``; older projects: by name), or None."""
    from . import build
    scene = scene if scene is not None else bpy.context.scene
    try:
        roots = build.model_roots(scene)
    except Exception:  # noqa: BLE001
        return None
    if not roots:
        return None
    return min(roots, key=lambda r: (float(r.get(build.PROP_IMPORTED, 1e18)), r.name))


def model_name(scene=None) -> str:
    """The first model's name as a file name ("" when there is none): its CAD name, else its object name, else its
    STEP file's name."""
    from . import build
    root = first_model(scene)
    if root is None:
        return ""
    for raw in (root.get(build.PROP_NAME, ""), root.name,
                os.path.splitext(os.path.basename(str(root.get(build.PROP_SOURCE, ""))))[0]):
        name = core.clean(str(raw or ""))
        if name:
            return name
    return ""


def mode() -> str:
    from . import prefs
    try:
        m = prefs.get().new_project_name
    except Exception:  # noqa: BLE001
        return core.DEFAULT_MODE
    return m if m in core.MODES else core.DEFAULT_MODE


def proposal(scene=None) -> str:
    """The file name (without .blend) the first save proposes."""
    return core.proposal(model_name(scene), mode())


def folder(scene=None) -> tuple[str, str]:
    """(folder, where): the folder the first save opens in and in words which one it is. The first model's STEP
    folder when it is there; else Documents."""
    from . import build
    root = first_model(scene)
    src = str(root.get(build.PROP_SOURCE, "")) if root is not None else ""
    d = os.path.dirname(src) if src else ""
    if d and os.path.isdir(d):
        return d, "the first model's folder"
    try:
        from . import rule_sets
        docs = rule_sets.documents_dir()     # (Windows asks the system: OneDrive may have moved it)
    except Exception:  # noqa: BLE001
        docs = ""
    if docs and os.path.isdir(docs):
        return docs, "Documents"
    return "", "Blender's last folder"


def proposed_path(scene=None) -> str:
    """The path the first save's browser opens with: folder + proposal (+ .blend); a folder with a separator at its
    end when the proposal is empty ("Leave empty")."""
    d, _where = folder(scene)
    name = core.file_name(proposal(scene))
    if not d:
        return name
    return os.path.join(d, name) if name else d.rstrip("\\/") + os.sep


def save_as_proposal(project_path: str | None = None) -> str:
    """Save as on a saved project: "<name> (n)", the next free n in its folder."""
    p = project_path if project_path is not None else bpy.data.filepath
    return core.next_free_in(os.path.dirname(p), core.stem_of(p))


def _invoke_browser(filepath: str) -> set:
    if bpy.app.background:               # no browser there: Blender would save straight away, over a file too
        print("Fresing Render: no file browser in a background Blender:", filepath)
        return {"CANCELLED"}
    try:
        return bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT", filepath=filepath)
    except RuntimeError as exc:
        print("Fresing Render: the save browser could not open:", exc)
        return {"CANCELLED"}


def _locked() -> bool:
    try:
        from . import lock
        return bool(lock.ON[0])
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# the operators
# ---------------------------------------------------------------------------

class FRESING_OT_save(bpy.types.Operator):
    """Saves the project. A project never saved: the file browser opens with the first model's name filled in, in
    its STEP folder (Fresing Settings > General: Name of a new project). A saved project is saved under its own name"""

    bl_idname = "fresing.save"
    bl_label = "Save"
    bl_options = {"INTERNAL"}

    show_save_modified_images_dialog: BoolProperty(options={"HIDDEN", "SKIP_SAVE"}, default=False)

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        from . import compat
        if compat.refuse_save(self):         # task 0352: a project from a newer app is never saved over itself
            return {"CANCELLED"}
        if bpy.data.filepath:
            return bpy.ops.wm.save_mainfile("EXEC_DEFAULT")
        return _invoke_browser(proposed_path(context.scene))


class FRESING_OT_save_as(bpy.types.Operator):
    """Saves the project as a new project file. A saved project: proposes "name (1)" – the next free number in its
    folder – selected, so you can type another name before saving. A project never saved: as Save"""

    bl_idname = "fresing.save_as"
    bl_label = "Save As…"
    bl_options = {"INTERNAL"}

    name: StringProperty(name="Name", description="The new project's file name (.blend is added). It is saved in "
                                                  "the same folder as the project; Other folder… lets you pick one")
    show_save_modified_images_dialog: BoolProperty(options={"HIDDEN", "SKIP_SAVE"}, default=False)

    @classmethod
    def poll(cls, context):
        return not _locked()             # the Client view: Save As is off (lock.py)

    def invoke(self, context, event):
        if not bpy.data.filepath:
            return _invoke_browser(proposed_path(context.scene))
        self.name = save_as_proposal()
        return context.window_manager.invoke_props_dialog(self, width=460, title="Save as a new project",
                                                          confirm_text="Save")

    def draw(self, context):
        layout = self.layout
        layout.activate_init = True      # the name field opens in edit mode, all of it selected: type over it
        layout.prop(self, "name", text="")
        problem = core.typed_problem(self.name)
        row = layout.row()
        row.active = False
        row.label(text="In " + os.path.dirname(bpy.data.filepath), icon="FILE_FOLDER")
        if problem:
            row = layout.row()
            row.alert = True
            row.label(text=problem, icon="ERROR")
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("fresing.save_as_browse", text="Other folder…", icon="FILEBROWSER").filepath = \
            target(self.name) if not problem else ""

    def execute(self, context):
        if not bpy.data.filepath:
            return _invoke_browser(proposed_path(context.scene))
        problem = core.typed_problem(self.name)
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        path = target(self.name)
        if os.path.exists(path):         # never over another file without a question: Blender's browser asks
            self.report({"WARNING"}, f"{os.path.basename(path)} is there already: pick a name in the file browser")
            return _invoke_browser(path)
        try:
            bpy.ops.wm.save_as_mainfile("EXEC_DEFAULT", filepath=path)
        except RuntimeError as exc:
            self.report({"ERROR"}, f"Could not save {path}: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Saved as {os.path.basename(path)}")
        return {"FINISHED"}


def target(name: str, project_path: str | None = None) -> str:
    p = project_path if project_path is not None else bpy.data.filepath
    return os.path.join(os.path.dirname(p), core.file_name(name))


class FRESING_OT_save_as_browse(bpy.types.Operator):
    """Opens Blender's file browser to save the project as a new project file in another folder, with the name
    typed in the box"""

    bl_idname = "fresing.save_as_browse"
    bl_label = "Other folder…"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(options={"HIDDEN", "SKIP_SAVE"}, subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return not _locked()

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        if self.filepath:
            return _invoke_browser(self.filepath)
        if bpy.data.filepath:
            return _invoke_browser(target(save_as_proposal()))
        return _invoke_browser(proposed_path(context.scene))


# ---------------------------------------------------------------------------
# Blender's File menu: Save and Save As go to the app's operators
# ---------------------------------------------------------------------------

REDIRECT = {"wm.save_mainfile": "fresing.save", "wm.save_as_mainfile": "fresing.save_as"}


class _Layout:
    """A stand-in for the menu's layout: Blender's "Save" and "Save As…" (not Save Copy, Save Incremental) call the
    app's operators; everything else goes to the real layout."""

    def __init__(self, layout):
        object.__setattr__(self, "_real", layout)
        object.__setattr__(self, "_seen", set())

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)

    def operator(self, idname, *args, **kw):
        new = REDIRECT.get(idname)
        if new is not None and idname not in self._seen and _has(new):
            self._seen.add(idname)       # the first of each: "Save As…" – "Save Copy…" stays Blender's
            return self._real.operator(new, *args, **kw)
        return self._real.operator(idname, *args, **kw)


class _Menu:
    def __init__(self, menu):
        self.layout = _Layout(menu.layout)
        self._menu = menu

    def __getattr__(self, name):
        return getattr(self._menu, name)


def _has(idname: str) -> bool:
    cat, name = idname.split(".")
    return hasattr(getattr(bpy.types, f"{cat.upper()}_OT_{name}", None), "bl_idname")


def file_menu_draw(self, context):
    """Blender's own File menu, drawn with the stand-in layout."""
    orig = _S["menu"][0] if _S["menu"] else None
    if orig is None:
        return None
    try:
        return orig(_Menu(self), context)
    except Exception:  # noqa: BLE001 - never lose the File menu: Blender's own drawing then
        return orig(self, context)


def _swap_file_menu(on: bool) -> None:
    from . import quiet
    cls = getattr(bpy.types, "TOPBAR_MT_file", None)
    if cls is None:
        return
    funcs = quiet.draw_funcs(cls)
    if on and _S["menu"] is None:
        i = quiet._own(cls, funcs)
        if i >= 0:
            _S["menu"] = (funcs[i], file_menu_draw)
            funcs[i] = file_menu_draw
    elif not on and _S["menu"] is not None:
        orig, mine = _S["menu"]
        for i, f in enumerate(funcs):
            if f is mine:
                funcs[i] = orig
        _S["menu"] = None


def menu_swapped() -> bool:
    return _S["menu"] is not None


# ---------------------------------------------------------------------------
# any other way to the save browser: fill in the proposal once
# ---------------------------------------------------------------------------

def _save_browsers():
    wm = bpy.context.window_manager
    for win in (wm.windows if wm else ()):
        for area in (win.screen.areas if win.screen else ()):
            if area.type != "FILE_BROWSER":
                continue
            space = area.spaces.active
            op = getattr(space, "active_operator", None)
            idname = (getattr(op, "bl_idname", "") or "").lower()
            if "save_as_mainfile" in idname or "save_mainfile" in idname:
                yield space, op


def fill_browsers() -> int:
    """A never-saved project's save browser that shows Blender's own name gets the proposal (once per browser).
    Returns how many were filled."""
    n = 0
    if bpy.data.filepath:
        return 0
    for space, op in _save_browsers():
        key = space.as_pointer()
        if key in _S["done"]:
            continue
        _S["done"].add(key)
        params = space.params
        if params is None or getattr(getattr(op, "properties", None), "copy", False):
            continue
        if (params.filename or "").lower() not in BLENDER_DEFAULT:
            continue                     # the app's own operators already put a name in
        path = proposed_path(bpy.context.scene)
        d, name = os.path.split(path)
        if name == params.filename and (not d or os.path.normpath(d) == os.path.normpath(_dir(params))):
            continue
        try:
            if d:
                params.directory = d.encode("utf-8") if isinstance(params.directory, bytes) else d
            params.filename = name
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: could not fill in the project name:", exc)
            continue
        n += 1
        FILLED[0] += 1
    return n


def _dir(params) -> str:
    d = params.directory
    return d.decode("utf-8", "surrogateescape") if isinstance(d, bytes) else d


def _fill_timer():
    try:
        fill_browsers()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (project name):", exc)
    return None


def _on_browser_draw():
    """Draw handler of every file browser: cheap – a timer does the work once a save browser of a new project is
    seen."""
    if bpy.data.filepath:
        return
    space = bpy.context.space_data
    if space is None or space.as_pointer() in _S["done"]:
        return
    if not bpy.app.timers.is_registered(_fill_timer):
        bpy.app.timers.register(_fill_timer, first_interval=0.0)


@persistent
def _forget(_dummy=None):
    _S["done"].clear()


# ---------------------------------------------------------------------------
# keys: Ctrl+S / Ctrl+Shift+S
# ---------------------------------------------------------------------------

KEYS = (("fresing.save", {"ctrl": True}), ("fresing.save_as", {"ctrl": True, "shift": True}))


def _add_keys() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm is not None else None
    if kc is None:
        return
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    for idname, mods in KEYS:
        kmi = km.keymap_items.new(idname, "S", "PRESS", **mods)
        _S["keys"].append((km, kmi))


def _remove_keys() -> None:
    for km, kmi in _S["keys"]:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _S["keys"].clear()


CLASSES = (FRESING_OT_save, FRESING_OT_save_as, FRESING_OT_save_as_browse)


def register() -> None:
    """The keys, the File menu and the browser handler (the classes are registered with the app's others)."""
    if bpy.app.background:
        return
    _add_keys()
    _swap_file_menu(True)
    if _S["handler"] is None:
        _S["handler"] = bpy.types.SpaceFileBrowser.draw_handler_add(_on_browser_draw, (), "WINDOW", "POST_PIXEL")
    if _forget not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_forget)


def unregister() -> None:
    if _forget in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_forget)
    if _S["handler"] is not None:
        try:
            bpy.types.SpaceFileBrowser.draw_handler_remove(_S["handler"], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        _S["handler"] = None
    if bpy.app.timers.is_registered(_fill_timer):
        bpy.app.timers.unregister(_fill_timer)
    _swap_file_menu(False)
    _remove_keys()
