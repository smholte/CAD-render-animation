"""About Fresing Render (task 0206): version, who makes it, the licence, the third-party licences – offline.

One operator draws the window (Fresing menu and Help menu), one opens a licence file. The files are inside the extension
(``licenses/``, ``core/about.py``); an install made before 0.2.160 gets them with the update. The text files have no
program Windows would open (``LICENSE`` has no ending, ``.md`` has none either), so a copy with the ending ``.txt`` is
opened (Notepad).
"""

from __future__ import annotations

import os
import shutil
import tempfile

import bpy
from bpy.props import EnumProperty

from ..core import about as core
from . import updates, welcome

WHICH = (
    ("LICENCE", "Licence", "The licence of Fresing Render itself (GPL-3.0-or-later)"),
    ("NOTICES", "Third-party licences", "What others made that ships with the app, and their licences"),
    ("COMPANY", "Using it in a company", "For an IT or legal reader: what the app does on the network, what stays on "
                                         "the PC, the licence in plain words"),
    ("TEXTS", "Licence texts folder", "The full licence texts of the libraries that ship with the app"),
)
_FILES = {"LICENCE": core.LICENCE, "NOTICES": core.NOTICES, "COMPANY": core.COMPANY}
_PREVIEWS: dict = {}


def package_dir() -> str:
    return updates.PKG_DIR


def readable_copy(path: str, title: str) -> str:
    """A copy with the ending .txt in the temp folder: Windows opens it in Notepad (no ending or .md has no program)."""
    folder = os.path.join(tempfile.gettempdir(), "fresing_licences")
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, f"Fresing Render - {title}.txt")
    shutil.copyfile(path, target)
    return target


def _logo():
    """The icon number of the logo (a preview of the brand picture), or 0 when it cannot be made."""
    try:
        if "logo" not in _PREVIEWS:
            from bpy.utils import previews
            coll = previews.new()
            path = os.path.join(package_dir(), "brand", "fresing-logo_full_colour_2400px.png")
            if os.path.isfile(path):
                coll.load("logo", path, "IMAGE")
            _PREVIEWS["logo"] = coll
        coll = _PREVIEWS["logo"]
        return coll["logo"].icon_id if "logo" in coll else 0
    except Exception:  # noqa: BLE001
        return 0


class FRESING_OT_about_open(bpy.types.Operator):
    """Opens a licence file that is inside this install (works offline)"""

    bl_idname = "fresing.about_open"
    bl_label = "Open a licence file"
    bl_options = {"INTERNAL"}

    which: EnumProperty(items=WHICH, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        for key, _label, text in WHICH:
            if key == properties.which:
                return text + ". Opens in your text program (works offline)"
        return cls.__doc__

    def execute(self, context):
        from . import files
        pkg = package_dir()
        if self.which == "TEXTS":
            path = os.path.join(core.folder(pkg), core.THIRD_PARTY)
            if not os.path.isdir(path):
                self.report({"WARNING"}, "This install has no licence texts folder")
                return {"CANCELLED"}
            files.open_path(path)
            return {"FINISHED"}
        name = _FILES.get(self.which)
        path = core.find(pkg, name) if name else ""
        if not path:
            if self.which == "COMPANY":              # not inside this install: the page on GitHub
                bpy.ops.wm.url_open(url=core.COMPANY_URL)
                return {"FINISHED"}
            self.report({"ERROR"}, f"{name} is missing from this install. Reinstall or update Fresing Render")
            return {"CANCELLED"}
        title = dict((k, label) for k, label, _t in WHICH)[self.which]
        try:
            files.open_path(readable_copy(path, title))
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open {name}: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_about(bpy.types.Operator):
    """Shows the version, who makes Fresing Render and under which licence, with buttons for the licence files, the
    third-party licences and the page for companies. Works offline"""

    bl_idname = "fresing.about"
    bl_label = "About Fresing Render"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520, title="About Fresing Render",
                                                          confirm_text="Close")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        icon = _logo()
        if icon:
            layout.template_icon(icon_value=icon, scale=3.0)
        col = layout.column()
        col.label(text="Fresing Render")
        for line in core.lines(welcome.version(), bpy.app.version_string):
            welcome._lines(col, line, 72)
        layout.separator()
        row = layout.row(align=True)
        row.operator("fresing.about_open", text="Licence", icon="TEXT").which = "LICENCE"
        row.operator("fresing.about_open", text="Third-party licences", icon="TEXT").which = "NOTICES"
        row = layout.row(align=True)
        row.operator("fresing.about_open", text="Using it in a company", icon="HOME").which = "COMPANY"
        row.operator("fresing.about_open", text="Licence texts folder", icon="FILE_FOLDER").which = "TEXTS"
        gone = core.missing(package_dir())
        if gone:
            box = layout.box()
            box.alert = True
            welcome._lines(box, "Missing in this install: " + ", ".join(gone) + ". Update or reinstall.", 72,
                           icon="ERROR")


def _draw_help(self, context):
    self.layout.operator("fresing.about", text="About Fresing Render…", icon="INFO")


CLASSES = (FRESING_OT_about_open, FRESING_OT_about)


def register() -> None:
    try:
        from . import ext_sync
        ext_sync.switch_off_once()                   # Blender's own extension sync off, once (task 0206)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: could not switch Blender's extension sync off:", exc)
    menu = bpy.types.TOPBAR_MT_help
    menu.remove(_draw_help)
    menu.append(_draw_help)


def unregister() -> None:
    bpy.types.TOPBAR_MT_help.remove(_draw_help)
    coll = _PREVIEWS.pop("logo", None)
    if coll is not None:
        from bpy.utils import previews
        previews.remove(coll)
