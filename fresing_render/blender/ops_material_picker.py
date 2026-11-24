"""The Materials window's buttons (task 0273): open / close it, pick, use for the group, add to this project, save a
group's look or a Blender material as an own material, make a picture again, show a material's folder.

**The window** is made like Fresing Settings (task 0271): ``ops_setup.open_window`` copies a piece of the main 3D view
into a window of its own and marks its screen ``fr_materials``; its page is drawn in the toolbar region
(``ui_material_picker.FRESING_PT_materials_window``), made as wide as the window by ``ops_settings._opened``. One at a
time: opening it again brings it to the front. Its size (and on Windows its place) is kept (``ops_make.remember``).

**A click on a name picks** the material (it shows large on the right); **a second click on it within
``DOUBLE`` seconds uses it** for the group picked in 3 Looks – the window follows that group, so it can stay open while
the user walks through the groups.
"""

from __future__ import annotations

import os
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ..core import material_files as F
from . import locations, material_picker as MP, ops_setup, panels, ui_material_picker as UI
from .ops_setup import MATERIALS_MARK

KEY = "materials"
SIZE = (980, 640)                 # the window, px at UI scale 1
DOUBLE = 1.0                      # seconds: a second click on the same name uses it
_LAST = {"key": "", "time": 0.0}


def materials_windows() -> list:
    wm = getattr(bpy.context, "window_manager", None)
    out = []
    for win in (wm.windows if wm is not None else ()):
        try:
            if win.screen.get(MATERIALS_MARK):
                out.append(win)
        except (AttributeError, ReferenceError):
            continue
    return out


def _report_error(op, exc) -> set:
    op.report({"ERROR"}, " ".join(str(exc).split()) or type(exc).__name__)
    return {"CANCELLED"}


def _group(context):
    return MP.current_group(context)


class FRESING_OT_materials(bpy.types.Operator):
    """Opens the Materials window: pictures of every material – built-in, this project's, your company's,
    department's and your own –, filters by material, colour and look, and a search. Click a name to see it large,
    click it again to use it for the group picked in 3 Looks. The window stays open while you work"""

    bl_idname = "fresing.materials"
    bl_label = "Materials"
    bl_options = set()

    def execute(self, context):
        st = UI.state(context)
        g = _group(context)
        if st is not None and g is not None:
            st.picked = MP.group_key(g)
        MP.refresh_own()
        if bpy.app.background:
            self.report({"INFO"}, "The Materials window opens only in the app's own window, not in a background run")
            return {"CANCELLED"}
        there = materials_windows()
        if there:
            from .. import winplace
            ops_setup.restore_tabs()
            ops_setup.redraw_all()
            winplace.raise_window(there[0], KEY)
            return {"FINISHED"}
        if ops_setup.busy():
            self.report({"INFO"}, "A window is opening: a moment, then press again")
            return {"CANCELLED"}
        win, area, _region = ops_setup.main_view(context)
        if area is None:
            self.report({"WARNING"}, "The Materials window needs a 3D view in the main window")
            return {"CANCELLED"}
        if win.screen.show_fullscreen:
            self.report({"WARNING"}, "The 3D view fills the whole window: go back to the normal layout first "
                                     "(Ctrl+Space), then open Materials again")
            return {"CANCELLED"}
        from . import ops_make, ops_settings
        size = ops_make.kept_size(KEY) or SIZE
        ops_setup.open_window(win, area, mark=MATERIALS_MARK, value=KEY, done=ops_settings._opened, size=size)
        return {"FINISHED"}


class FRESING_OT_materials_close(bpy.types.Operator):
    """Closes the Materials window. It opens again where it was"""

    bl_idname = "fresing.materials_close"
    bl_label = "Close"
    bl_options = set()

    def execute(self, context):
        from . import ops_make
        wins = materials_windows()
        for win in wins:
            try:
                ops_make.remember(win)
            except Exception:  # noqa: BLE001
                pass
        if context.window in wins:
            bpy.app.timers.register(close_all, first_interval=0.01)
        else:
            close_all()
        return {"FINISHED"}


def close_all():
    for win in materials_windows():
        with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
            bpy.ops.wm.window_close()
    panels.redraw()
    return None


class FRESING_OT_mat_pick(bpy.types.Operator):
    """Shows this material large on the right with what it is. Click it a second time to use it for the group"""

    bl_idname = "fresing.mat_pick"
    bl_label = "Pick material"
    bl_options = {"UNDO"}         # (the second click changes the group: one undo step, the button's own)

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        e = MP.find(context.scene, properties.key) if context.scene is not None else None
        if e is None:
            return cls.__doc__
        text = f"{e.name} ({e.badge}): {e.description or UI.tag_line(e)}"
        if e.problems:
            return text + ". Cannot be used: " + "; ".join(e.problems)
        return text + ". Click again to use it for the group picked in 3 Looks"

    def execute(self, context):
        st = UI.state(context)
        now = time.monotonic()
        again = _LAST["key"] == self.key and now - _LAST["time"] < DOUBLE
        _LAST.update(key=self.key, time=now)
        if st is not None:
            st.picked = self.key
        if again:
            _LAST["key"] = ""
            return use(self, context, self.key)
        return {"FINISHED"}


class FRESING_OT_mat_use(bpy.types.Operator):
    """Gives the group picked in 3 Looks this material (its parts and painted faces change at once). A paint keeps the
    group's colour; your own material brings its own colour, wear and settings"""

    bl_idname = "fresing.mat_use"
    bl_label = "Use for the group"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    group: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        e = MP.find(context.scene, properties.key) if context.scene is not None else None
        if e is None:
            return cls.__doc__
        g = _group(context)
        who = f"'{g.name}'" if g is not None else "the group picked in 3 Looks"
        return f"Gives {who} the material {e.name} ({e.badge}). " + (e.description or "")

    def execute(self, context):
        return use(self, context, self.key, self.group)


def use(op, context, key: str, group: str = "") -> set:
    """Give the group (picked in 3 Looks, or ``group``) the entry ``key`` – the work of Use and of a second click
    (an operator called from an operator gets no undo step of its own: CLAUDE.md)."""
    s = context.scene.fresing
    g = s.groups.get(group) if group else _group(context)
    if g is None:
        op.report({"WARNING"}, "Pick a group in 3 Looks first")
        return {"CANCELLED"}
    e = MP.find(context.scene, key)
    if e is None:
        op.report({"WARNING"}, "That material is not there any more")
        return {"CANCELLED"}
    try:
        MP.apply(context, g, e)
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        return _report_error(op, exc)
    op.report({"INFO"}, f"{g.name}: {e.name}")
    MP.redraw()
    return {"FINISHED"}


class FRESING_OT_mat_star(bpy.types.Operator):
    """Puts this material on this project's list (3 Looks, above Material), so it is one click away for any group.
    Press again to take it off the list"""

    bl_idname = "fresing.mat_star"
    bl_label = "This project's materials"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        scene = context.scene
        if MP.is_listed(scene, self.key):
            MP.remove_from_project(scene, self.key)
            self.report({"INFO"}, "Taken off this project's list")
            MP.redraw()
            return {"FINISHED"}
        e = MP.find(scene, self.key)
        if e is None or not e.ok:
            self.report({"WARNING"}, "That material cannot be used" + (": " + "; ".join(e.problems) if e else ""))
            return {"CANCELLED"}
        try:
            MP.add_to_project(scene, e)
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            return _report_error(self, exc)
        self.report({"INFO"}, f"{e.name} is on this project's list (3 Looks)")
        MP.redraw()
        return {"FINISHED"}


class FRESING_OT_mat_unlist(bpy.types.Operator):
    """Takes this material off this project's list. Groups that use it keep it"""

    bl_idname = "fresing.mat_unlist"
    bl_label = "Off the list"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        MP.remove_from_project(context.scene, self.key)
        MP.redraw()
        return {"FINISHED"}


_MATS: list = []


def _material_items(self, context):
    _MATS.clear()
    for m in MP.blender_materials():
        _MATS.append((m.name, m.name, f"The material '{m.name}' of this project"))
    if not _MATS:
        _MATS.append(("NONE", "No material of your own in this project",
                      "Make one in Blender's shader editor first (Fresing > Show all of Blender)"))
    return _MATS


class FRESING_OT_mat_save(bpy.types.Operator):
    """Saves what the group picked in 3 Looks shows now – its material, colour, wear, rust and the finish's settings –
    as a material of your own: a folder in your Materials folder (Fresing Settings > Locations), with a picture.
    The group then uses it, and it is listed under Mine in the Materials window of every project"""

    bl_idname = "fresing.mat_save"
    bl_label = "Save as my material"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", description="The material's name, for example \"Machine blue, satin\"")
    description: StringProperty(name="Description", description="One line: what it is and where it is used")
    where: EnumProperty(name="Save in", items=locations.where_items(MP.KIND),
                        description="The folder it goes into: your own folders first, then the company's or "
                                    "department's folders you may write to (Fresing Settings > Locations)")

    @classmethod
    def poll(cls, context):
        if _group(context) is None:
            cls.poll_message_set("Pick a group in 3 Looks first")
            return False
        return True

    def invoke(self, context, event):
        g = _group(context)
        e = MP.find(context.scene, MP.group_key(g)) if g is not None else None
        self.name = (g.color + " " if g is not None and g.color and e is not None and e.takes_colour else "") + \
            (e.name if e is not None else (g.name if g is not None else ""))
        from . import form_window
        return form_window.open(self, context, width=460, height=300, title="Save as my material", confirm="Save",
                                icon="FILE_TICK")

    def draw(self, context):
        layout = self.layout
        g = _group(context)
        if g is not None:
            layout.label(text=f"From the group: {g.name}", icon="MATERIAL")
        layout.prop(self, "name")
        layout.prop(self, "description")
        if len(locations.save_choices(MP.KIND)) > 1:
            layout.prop(self, "where")
        else:
            path = locations.save_folder(MP.KIND, make=False)
            layout.label(text=("It goes into: " + path) if path else locations.no_folder_text(MP.KIND),
                         icon="FILE_FOLDER" if path else "ERROR")

    def execute(self, context):
        g = _group(context)
        root = locations.where_value(self.where) or locations.save_folder(MP.KIND)
        if not root:
            self.report({"ERROR"}, locations.no_folder_text(MP.KIND))
            return {"CANCELLED"}
        try:
            e = MP.save_from_group(context, g, self.name, self.description, root)
        except (F.MaterialError, ValueError, OSError, RuntimeError) as exc:
            return _report_error(self, exc)
        st = UI.state(context)
        if st is not None:
            st.picked = e.key
        self.report({"INFO"}, f"Saved '{e.name}' in {os.path.dirname(e.folder)} – its picture is being made")
        return {"FINISHED"}


class FRESING_OT_mat_from_blender(bpy.types.Operator):
    """For users who build materials in Blender's own shader editor: keeps a material of this project as a material
    of your own – a folder with a Blender file (material.blend) holding it, and a picture. Using it later copies it
    into that project (appended, not linked: the project then renders without the folder)"""

    bl_idname = "fresing.mat_from_blender"
    bl_label = "From a Blender material"
    bl_options = {"REGISTER", "UNDO"}

    material: EnumProperty(name="Material", items=_material_items,
                           description="A material of this project made in Blender's shader editor (not the app's "
                                       "own group materials)")
    name: StringProperty(name="Name", description="The name it gets in the Materials window (empty: its own name)")
    description: StringProperty(name="Description", description="One line: what it is and where it is used")
    use: BoolProperty(name="Use it for the group", default=True,
                      description="The group picked in 3 Looks gets this material at once")
    where: EnumProperty(name="Save in", items=locations.where_items(MP.KIND),
                        description="The folder it goes into: your own folders first, then the company's or "
                                    "department's folders you may write to (Fresing Settings > Locations)")

    def invoke(self, context, event):
        from . import form_window
        return form_window.open(self, context, width=480, height=340, title="From a Blender material",
                                confirm="Save", icon="NODE_MATERIAL")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "material")
        layout.prop(self, "name")
        layout.prop(self, "description")
        if _group(context) is not None:
            layout.prop(self, "use", text=f"Use it for '{_group(context).name}'")
        if len(locations.save_choices(MP.KIND)) > 1:
            layout.prop(self, "where")
        mat = bpy.data.materials.get(self.material) if self.material not in ("", "NONE") else None
        if mat is not None:
            outside = MP.images_outside(mat, os.path.join(os.sep, "nowhere"))
            if outside:
                col = layout.column()
                col.alert = True
                col.label(text=f"It uses {len(outside)} picture file(s) that are not packed into the project:",
                          icon="ERROR")
                for p in outside[:3]:
                    col.label(text=os.path.basename(p))
                col.label(text="On another PC they are missing. File > External Data > Pack Resources packs them")

    def execute(self, context):
        mat = bpy.data.materials.get(self.material) if self.material not in ("", "NONE") else None
        if mat is None:
            self.report({"WARNING"}, "Pick a material of this project first")
            return {"CANCELLED"}
        root = locations.where_value(self.where) or locations.save_folder(MP.KIND)
        if not root:
            self.report({"ERROR"}, locations.no_folder_text(MP.KIND))
            return {"CANCELLED"}
        g = _group(context) if self.use else None
        try:
            e = MP.save_from_blender(context, mat, self.name.strip() or mat.name, self.description, root, group=g)
        except (F.MaterialError, ValueError, OSError, RuntimeError) as exc:
            return _report_error(self, exc)
        st = UI.state(context)
        if st is not None:
            st.picked = e.key
        msg = f"Saved '{e.name}'"
        if e.images_outside:
            msg += f" – it uses {len(e.images_outside)} picture file(s) outside its folder"
            self.report({"WARNING"}, msg)
        else:
            self.report({"INFO"}, msg + " – its picture is being made")
        return {"FINISHED"}


class FRESING_OT_mat_picture(bpy.types.Operator):
    """Makes this material's picture again (in the background: the app does not wait)"""

    bl_idname = "fresing.mat_picture"
    bl_label = "Make the picture again"
    bl_options = set()

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        e = MP.find(context.scene, self.key)
        if e is None or not e.folder:
            self.report({"WARNING"}, "Only a material in a folder has a picture to make")
            return {"CANCELLED"}
        if not MP.make_picture(e):
            self.report({"WARNING"}, f"The picture of '{e.name}' could not be started")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Making the picture of '{e.name}'…")
        return {"FINISHED"}


class FRESING_OT_mat_show(bpy.types.Operator):
    """Shows this material's folder in Explorer (copy the folder to give the material to someone)"""

    bl_idname = "fresing.mat_show"
    bl_label = "Show in folder"
    bl_options = set()

    key: StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        e = MP.find(context.scene, self.key)
        if e is None or not e.folder or not os.path.isdir(e.folder):
            self.report({"WARNING"}, "This material's folder is not there")
            return {"CANCELLED"}
        from . import files
        files.show_in_folder(os.path.join(e.folder, F.JSON_NAME))
        return {"FINISHED"}


class FRESING_OT_mat_refresh(bpy.types.Operator):
    """Looks in the Materials folders again (a material a colleague just put there shows up)"""

    bl_idname = "fresing.mat_refresh"
    bl_label = "Look again"
    bl_options = set()

    def execute(self, context):
        locations.look_again()
        MP.refresh_own(force=True)
        return {"FINISHED"}


class FRESING_OT_mat_filters_clear(bpy.types.Operator):
    """Clears the search and every filter: all materials show"""

    bl_idname = "fresing.mat_filters_clear"
    bl_label = "Show all"
    bl_options = set()

    def execute(self, context):
        st = UI.state(context)
        if st is not None:
            st.search = ""
            for name in ("source", "kind", "colour", "look"):
                setattr(st, name, UI.ALL)
        return {"FINISHED"}


CLASSES = (FRESING_OT_materials, FRESING_OT_materials_close, FRESING_OT_mat_pick, FRESING_OT_mat_use,
           FRESING_OT_mat_star, FRESING_OT_mat_unlist, FRESING_OT_mat_save, FRESING_OT_mat_from_blender,
           FRESING_OT_mat_picture, FRESING_OT_mat_show, FRESING_OT_mat_refresh, FRESING_OT_mat_filters_clear)
