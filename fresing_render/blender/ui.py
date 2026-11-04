"""Side panel in the 3D viewport: 1 Import, 2 Structure, 3 Looks, (4 Motion,) 5 Scene & Render.

Layout rules for every section (read top to bottom, no jumping back up):
* what you choose before an action sits above its button; the main button of a section is big;
* each list shows names only, the details of the selected item are in the box right under it;
* one-time and rarely used settings are in a closed "More" fold at the end;
* the panel header shows an icon and the state of the section, also when it is folded.
"""

from __future__ import annotations

import json
import os
import textwrap

import bpy

from ..core import fasteners, materials_lib, presets
from . import build, cameras, materials

CATEGORY = "Fresing"
BIG = 1.5            # height of the main button of a section
MEDIUM = 1.25


class _Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY


def _has_model(context) -> bool:
    return context.scene.fresing.model_count > 0


# ---------------------------------------------------------------------------
# helpers shared by all sections
# ---------------------------------------------------------------------------


def _chars_per_line(context, inset: int = 0) -> int:
    region = getattr(context, "region", None)
    width = getattr(region, "width", 0) or 300
    try:
        scale = context.preferences.system.ui_scale or 1.0
    except AttributeError:
        scale = 1.0
    return max(18, int((width / scale - 34 - inset) / 6.6))


def wrap(layout, context, text: str, icon: str = "NONE", inset: int = 0, alert: bool = False):
    """A message on as many lines as it needs (Blender cuts long labels off with '...')."""
    col = layout.column(align=True)
    col.alert = alert
    lines = textwrap.wrap(text, _chars_per_line(context, inset + (22 if icon != "NONE" else 0))) or [""]
    for i, line in enumerate(lines):
        col.label(text=line, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))
    return col


def steps(layout, context, lines: list[str]):
    """Numbered how-to lines in a box (shown where the steps start)."""
    box = layout.box()
    col = box.column(align=True)
    for i, line in enumerate(lines, 1):
        for k, part in enumerate(textwrap.wrap(line, _chars_per_line(context, 40)) or [""]):
            col.label(text=f"{i}.  {part}" if k == 0 else f"     {part}")
    return box


_OPEN_FOLDS = bool(os.environ.get("FRESING_UI_OPEN_FOLDS"))     # screenshots of everything


def fold(layout, idname: str, title: str, icon: str = "NONE", closed: bool = True):
    """A foldable part of a panel; returns its body layout or None when folded."""
    header, body = layout.panel(idname, default_closed=closed and not _OPEN_FOLDS)
    header.label(text=title, icon=icon)
    return body


def big_row(layout, scale: float = BIG):
    row = layout.row(align=True)
    row.scale_y = scale
    return row


def split_props(layout):
    """Label on the left, field on the right, labels never cut off."""
    col = layout.column(align=True)
    col.use_property_split = True
    col.use_property_decorate = False
    return col


def header_status(layout, text: str, icon: str = "NONE", alert: bool = False, limit: int = 14) -> None:
    """Short state text on the right of a panel header (kept short: the title must stay readable)."""
    if len(text) > limit:
        text = text[:limit - 1] + "…"
    row = layout.row(align=True)
    row.alert = alert
    row.label(text=text, icon=icon)


def use_button(row, idname: str, name: str) -> None:
    """The small 'Use' button at the end of a list row; the name gets the rest of the row."""
    sub = row.row(align=True)
    sub.ui_units_x = 2.6
    sub.operator(idname, text="Use").name = name


def primary(layout, idname: str, text: str, icon: str, scale: float = BIG):
    """The main button of a section: big and highlighted, so it is found at a glance."""
    row = big_row(layout, scale)
    return row.operator(idname, text=text, icon=icon, depress=True)


def list_rows(n: int, lo: int = 3, hi: int = 8) -> int:
    """List height that fits the items: no tall empty lists, no endless ones."""
    return max(lo, min(hi, n))


# =============================================================================
# 1 Import
# =============================================================================


class FRESING_PT_import(_Panel, bpy.types.Panel):
    bl_label = "1  Import"
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(icon="IMPORT")

    def draw_header_preset(self, context):
        roots = build.model_roots(context.scene)
        if roots:
            header_status(self.layout, roots[0].name if len(roots) == 1 else f"{len(roots)} models")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        from . import ops_import, project_lock
        busy = project_lock.warning()
        if busy:
            box = layout.box()
            box.alert = True
            box.label(text=f"In use by {busy}", icon="ERROR")
            wrap(box, context, "Save your changes under another name (File > Save As)", inset=12)

        job = ops_import._ACTIVE_JOB
        if job is not None and not job.done:
            box = layout.box()
            box.label(text="Importing…", icon="SORTTIME")
            box.progress(factor=max(0.0, min(1.0, job.pct / 100.0)), text=f"{job.pct:.0f}%")
            wrap(box, context, job.message, inset=12)
            box.label(text="Esc in the viewport cancels", icon="CANCEL")
        else:
            # choose first, then import
            col = split_props(layout)
            row = col.row(align=True)
            row.prop(s, "import_quality", text="Detail", expand=True)
            col.prop(s, "import_up_axis", text="Up axis")
            primary(layout, "fresing.import_step", "Import STEP…", "IMPORT")
            layout.label(text="or drag a .step file onto the view", icon="INFO")

        for root in build.model_roots(context.scene):
            box = layout.box()
            box.label(text=root.name, icon="OUTLINER_OB_GROUP_INSTANCE")
            try:
                st = json.loads(root.get("fr_stats", "{}"))
            except ValueError:
                st = {}
            if st:
                col = box.column(align=True)
                col.label(text=f"{st.get('placed_parts', 0)} parts, {st.get('unique_parts', 0)} different")
                helpers = st.get("mesh_helpers", 0)
                col.label(text=f"{st.get('triangles_unique', 0) / 1e6:.1f} M triangles · read in "
                               f"{st.get('seconds_total', 0):.0f} s" + (f" on {helpers} cores" if helpers else ""))
            op = box.operator("fresing.import_step", text="Update to new revision…", icon="FILE_REFRESH")
            op.update_root = root.name
        if s.report_title:
            box = layout.box()
            row = box.row()
            wrap(row.column(), context, s.report_title, icon="INFO", inset=40)
            row.operator("fresing.report_clear", text="", icon="X", emboss=False)
            if len(s.report_new):
                wrap(box, context, f"New ({len(s.report_new)}): "
                     + ", ".join(x.text for x in list(s.report_new)[:6]) + (" …" if len(s.report_new) > 6 else ""),
                     inset=12)
                box.operator("fresing.report_select_new", icon="RESTRICT_SELECT_OFF")
            if len(s.report_missing):
                wrap(box, context, f"Missing ({len(s.report_missing)}): "
                     + ", ".join(x.text for x in list(s.report_missing)[:6])
                     + (" …" if len(s.report_missing) > 6 else ""), inset=12)
            for note in s.report_notes:
                wrap(box, context, note.text, icon="ERROR", inset=12)
        if s.last_message and not (job is not None and not job.done):
            wrap(layout, context, s.last_message, icon="CHECKMARK" if s.last_message.startswith("Imported")
                 else "INFO")
        body = fold(layout, "fr_import_more", "More")
        if body:
            wrap(body, context, "Imports are stored, so an unchanged file opens again in seconds.")
            body.operator("fresing.clear_cache", icon="TRASH")


# =============================================================================
# 2 Structure
# =============================================================================


class FRESING_UL_tree(bpy.types.UIList):
    """Explorer-like tree: open/close per assembly, identical parts as one row, colour dot per part."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        ob = item.obj
        if ob is None:
            layout.label(text="(deleted)")
            return
        row = layout.row(align=True)
        for _ in range(item.depth):
            row.separator(factor=0.5)
        if item.has_kids:
            op = row.operator("fresing.tree_toggle", text="", emboss=False,
                              icon="DISCLOSURE_TRI_DOWN" if item.expanded else "DISCLOSURE_TRI_RIGHT")
            op.index = index
        else:
            row.label(text="", icon="BLANK1")
        # the name may be cut off at the end; what tells copies apart stays visible on the right
        name = ob.get(build.PROP_NAME, ob.name)
        if item.label.startswith(name):
            tag = item.label[len(name):].strip()            # ":2" of identical subassemblies
        else:
            name, tag = item.label, ""
        if item.is_part:
            mat = ob.active_material
            if mat is not None:
                row.label(text=name, icon_value=layout.icon(mat))
            else:
                row.label(text=name, icon="MESH_CUBE")
            if item.same > 1:
                tag = f"×{item.same}"
        else:
            row.label(text=name, icon="OUTLINER_COLLECTION" if item.depth == 0 else "FILE_FOLDER")
        # few buttons per row, so long names fit; zoom and lock are under the list
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        if tag:
            sub.label(text=tag)
        if not item.is_part and not ob.get(build.PROP_LOCKED, True):
            sub.label(text="", icon="UNLOCKED")
        hidden = ob.get("fr_hidden", False)
        op = sub.operator("fresing.tree_row", text="", icon="HIDE_ON" if hidden else "HIDE_OFF", emboss=False)
        op.index, op.action = index, "HIDE"
        op = sub.operator("fresing.tree_row", text="", icon="RESTRICT_SELECT_OFF", emboss=False)
        op.index, op.action = index, "ADD"

    def filter_items(self, context, data, propname):
        from . import tree as tree_mod
        vis = tree_mod.visible_rows(data, data.tree_search.strip())
        return [self.bitflag_filter_item if v else 0 for v in vis], []


class FRESING_PT_structure(_Panel, bpy.types.Panel):
    bl_label = "2  Structure"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="OUTLINER")

    def draw_header_preset(self, context):
        s = context.scene.fresing
        if s.isolated:
            header_status(self.layout, "showing a part", alert=True)
            return
        n = sum(1 for _ in build.iter_parts(context.scene))
        header_status(self.layout, f"{n} parts")

    def draw(self, context):
        from . import tree as tree_mod
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="A click in the view selects a:", icon="RESTRICT_SELECT_OFF")
        row = layout.row(align=True)
        row.prop(s, "pick_mode", expand=True)

        row = layout.row(align=True)
        row.prop(s, "tree_search", text="", icon="VIEWZOOM", placeholder="Find in the tree")
        row.operator("fresing.tree_open_all", text="", icon="DISCLOSURE_TRI_DOWN").open = True
        row.operator("fresing.tree_open_all", text="", icon="DISCLOSURE_TRI_RIGHT").open = False
        row.operator("fresing.tree_refresh", text="", icon="FILE_REFRESH")
        visible = sum(tree_mod.visible_rows(s, s.tree_search.strip()))
        layout.template_list("FRESING_UL_tree", "", s, "tree", s, "tree_index", rows=list_rows(visible, 5, 14))
        wrap(layout, context, "Click a row to select it in the view. The arrow at the end adds it to the "
                              "selection.", icon="INFO")
        if 0 <= s.tree_index < len(s.tree) and s.tree[s.tree_index].obj is not None:
            it = s.tree[s.tree_index]
            box = layout.box()
            text = it.label + (f"  ×{it.same}" if it.same > 1 else "") + ("" if it.is_part else f"  ({it.parts} parts)")
            box.label(text=text, icon="MESH_CUBE" if it.is_part else "FILE_FOLDER")
            row = box.row(align=True)
            op = row.operator("fresing.tree_row", text="Zoom to it", icon="ZOOM_SELECTED")
            op.index, op.action = s.tree_index, "FRAME"
            if not it.is_part:
                locked = it.obj.get(build.PROP_LOCKED, True)
                row.operator("fresing.toggle_lock", text="Locked in place" if locked else "Unlocked: can be moved",
                             icon="LOCKED" if locked else "UNLOCKED", depress=not locked).name = it.obj.name

        if s.isolated:
            box = layout.box()
            box.alert = True
            box.label(text=f"Showing only: {s.isolated}", icon="HIDE_ON")
            box.operator("fresing.show_only_end", text="Show everything again", icon="HIDE_OFF")
        row = layout.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.hide_selected", text="Hide", icon="HIDE_ON")
        row.operator("fresing.show_only_selected", text="Show only", icon="SELECT_SET")
        row.operator("fresing.show_all", text="Show all", icon="HIDE_OFF")


class FRESING_PT_cleanup(_Panel, bpy.types.Panel):
    bl_label = "Clean-up"
    bl_parent_id = "FRESING_PT_structure"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="BRUSH_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Remove parts that never show, for faster renders.")
        steps(layout, context, ["Select the parts (or small ones below)", "Remove selected"])
        col = split_props(layout)
        col.prop(s, "small_part_mm", text="Max size (mm)")
        layout.operator("fresing.select_small", text="Select the small parts", icon="RESTRICT_SELECT_OFF")
        row = layout.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.exclude_selected", text="Remove selected", icon="TRASH")
        row.operator("fresing.restore_excluded", text="Restore all", icon="LOOP_BACK")


class FRESING_UL_visibility(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="HIDE_OFF")
        use_button(row, "fresing.vis_apply", item.name)


class FRESING_PT_visibility(_Panel, bpy.types.Panel):
    bl_label = "Visibility sets"
    bl_parent_id = "FRESING_PT_structure"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="HIDE_OFF")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Which parts are hidden, saved under a name. + saves what is hidden now.")
        row = layout.row()
        row.template_list("FRESING_UL_visibility", "", s, "visibility_sets", s, "visibility_index",
                          rows=list_rows(len(s.visibility_sets), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.vis_save", text="", icon="ADD")
        col.operator("fresing.vis_remove", text="", icon="REMOVE")
        col.operator("fresing.vis_update", text="", icon="FILE_REFRESH")
        if 0 <= s.visibility_index < len(s.visibility_sets):
            v = s.visibility_sets[s.visibility_index]
            layout.label(text=f"{v.name}: {len(v.hidden)} parts hidden", icon="HIDE_ON")


# =============================================================================
# 3 Looks
# =============================================================================


class FRESING_UL_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        mat = bpy.data.materials.get(materials.material_name(item.name))
        if mat is not None:
            row.label(text="", icon_value=layout.icon(mat))
        row.prop(item, "name", text="", emboss=False)
        sub = row.row()
        sub.alignment = "RIGHT"
        if item.faces and not item.count:
            sub.label(text=str(item.faces), icon="BRUSH_DATA")        # used by painted faces only
        else:
            sub.label(text=str(item.count))


class FRESING_UL_rules(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.target or "(no group)")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=str(item.count))


class FRESING_UL_schemes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="COLOR")
        use_button(row, "fresing.scheme_apply", item.name)


_RULE_SET_ICON = {"builtin": "LOCKED", "library": "FILE", "project": "FILE_BLEND"}


def draw_rule_set(layout, context) -> None:
    """Top of 3 Looks: the rule set this project uses, its state, and a fold to manage rule sets."""
    from ..core import rule_sets as RS
    from . import rule_sets
    s = context.scene.fresing
    name = s.rule_set or RS.STANDARD
    kind = rule_sets.kind(s)
    split = layout.split(factor=0.3, align=True)
    split.label(text="Rule set")
    split.operator_menu_enum("fresing.rule_set_switch", "name", text=name, icon=_RULE_SET_ICON[kind])
    _path, _shared, problem = rule_sets.folder()
    if problem:
        wrap(layout, context, f"{problem}: the project uses its own copy of '{name}'.", icon="ERROR", alert=True)
    diff = rule_sets.differences(s)
    if any(diff.values()):
        box = layout.box()
        wrap(box, context, f"Changed in this project: {RS.describe_differences(diff)}", icon="MODIFIER",
             inset=12, alert=True)
        row = box.row(align=True)
        if kind == "builtin":
            row.operator("fresing.rule_set_save_as", text="Save as new rule set…", icon="DUPLICATE")
            hint = wrap(box, context, "Standard itself cannot be changed.", inset=12)
            hint.active = False
        elif kind == "project":
            row.operator("fresing.rule_set_save_as", text="Save to library…", icon="FILE_TICK")
        else:
            row.operator("fresing.rule_set_save", text="Save changes", icon="FILE_TICK")
            row.operator("fresing.rule_set_save_as", text="Save as new…", icon="DUPLICATE")
    elif kind == "project" and not problem:
        box = layout.box()
        wrap(box, context, "Only in this project: not in the library.", icon="INFO", inset=12)
        box.operator("fresing.rule_set_save_as", text="Save to library…", icon="FILE_TICK")
    if rule_sets.library_differs(s):
        box = layout.box()
        wrap(box, context, f"The library has a newer version of '{name}'.", icon="FILE_REFRESH", inset=12)
        box.operator("fresing.rule_set_switch", text="Load it…", icon="IMPORT").name = name
    body = fold(layout, "fresing_rule_sets_manage", "Manage rule sets", "FILTER")
    if body is not None:
        grid = body.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        grid.operator("fresing.rule_set_save_as", text="Copy…", icon="DUPLICATE")
        grid.operator("fresing.rule_set_new_empty", text="New, empty…", icon="FILE_NEW")
        grid.operator_menu_enum("fresing.rule_set_rename", "name", text="Rename…", icon="GREASEPENCIL")
        grid.operator_menu_enum("fresing.rule_set_delete", "name", text="Delete…", icon="TRASH")
        split = body.split(factor=0.4, align=True)
        split.label(text="New projects")
        split.operator_menu_enum("fresing.rule_set_default", "name", text=rule_sets.default_name(), icon="FILTER")
        path, shared, _problem = rule_sets.folder()
        where = "Kept in the shared library" if shared else "Kept on this PC (no shared library set)"
        info = wrap(body, context, f"{where}: {path}", icon="FILE_FOLDER")
        info.active = False
        body.operator("fresing.rule_set_folder", text="Show the folder", icon="FILE_FOLDER")
    layout.separator()


class FRESING_PT_looks(_Panel, bpy.types.Panel):
    bl_label = "3  Looks"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MATERIAL")

    def draw_header_preset(self, context):
        s = context.scene.fresing
        if s.unmatched:
            header_status(self.layout, f"{s.unmatched} unsorted", alert=True)
        else:
            header_status(self.layout, f"{len(s.groups)} groups")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        draw_rule_set(layout, context)
        row = big_row(layout, MEDIUM)
        row.operator("fresing.apply_rules", text="Sort parts into groups", icon="SORTALPHA")
        if s.unmatched:
            wrap(layout, context, f"{s.unmatched} parts match no rule: they are in 'Unsorted'. "
                                  "Find & sort parts (below) helps.", icon="ERROR", alert=True)
            layout.operator("fresing.show_only_group", text="Show only the unsorted parts",
                            icon="HIDE_OFF").group = ""
        wrap(layout, context, "Material groups: pick one, then set its material", icon="MATERIAL")
        row = layout.row()
        row.template_list("FRESING_UL_groups", "", s, "groups", s, "groups_index",
                          rows=list_rows(len(s.groups), 3, 10))
        col = row.column(align=True)
        col.operator("fresing.group_add", text="", icon="ADD")
        col.operator("fresing.group_remove", text="", icon="REMOVE")
        if 0 <= s.groups_index < len(s.groups):
            g = s.groups[s.groups_index]
            box = layout.box()
            parts_txt = f"{g.count} part{'s' if g.count != 1 else ''}"
            faces_txt = f" and {g.faces} painted face set{'s' if g.faces != 1 else ''}" if g.faces else ""
            wrap(box, context, f"{g.name}  ·  {parts_txt}{faces_txt}", icon="MATERIAL", inset=12)
            box.operator_menu_enum("fresing.group_preset", "preset", text="Ready-made material…",
                                   icon="PRESET")
            col = split_props(box)
            col.prop(g, "material", text="Material")
            if materials_lib.needs_color(g.material):
                row = col.row(align=True)
                row.prop(g, "color", text="Colour")
                row.operator("fresing.pick_ral", text="", icon="VIEWZOOM")
            row = box.row(align=True)
            row.operator("fresing.group_select", text="Select its parts", icon="RESTRICT_SELECT_OFF")
            row.operator("fresing.show_only_group", text="Show only these", icon="HIDE_OFF").group = g.name
            row = box.row(align=True)
            row.operator("fresing.group_assign", text="Put selected in", icon="IMPORT")
            row.operator("fresing.group_unassign", text="Back to the rules", icon="LOOP_BACK")
            if 0 <= s.tree_index < len(s.tree) and not s.tree[s.tree_index].is_part:
                sub = s.tree[s.tree_index]
                hint = wrap(box, context, f"Everything in {sub.label} to this group:", inset=12)
                hint.active = False
                box.operator("fresing.rule_from_subassembly", text="Make it a rule", icon="FILTER")
        ob = context.active_object
        if ob is not None and ob.get(build.PROP_KIND) == "part":
            box = layout.box()
            box.label(text=ob.get(build.PROP_NAME, ob.name), icon="OBJECT_DATA")
            col = box.column(align=True)
            info = fasteners.parse(ob.get(build.PROP_NAME, ""))
            if info:
                wrap(col, context, fasteners.describe(info), icon="TOOL_SETTINGS", inset=12)
            g = ob.get(build.PROP_GROUP, "")
            manual = " (put in by hand)" if ob.get("fr_group_manual") else ""
            wrap(col, context, f"Group: {g}{manual}", inset=12)
            if ob.get(build.PROP_COLOR):
                col.label(text=f"CAD colour: {ob[build.PROP_COLOR]}")
            if ob.get(build.PROP_CAD_MATERIAL):
                wrap(col, context, f"CAD material: {ob[build.PROP_CAD_MATERIAL]}", inset=12)
            box.operator_menu_enum("fresing.part_move_group", "group", text="Move selected to group…",
                                   icon="FORWARD")


class FRESING_PT_faces(_Panel, bpy.types.Panel):
    bl_label = "Paint faces"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="BRUSH_DATA")

    def draw_header_preset(self, context):
        s = context.scene.fresing
        if s.face_painting:
            header_status(self.layout, "painting…", alert=True)
        else:
            n = sum(g.faces for g in s.groups)
            if n:
                header_status(self.layout, f"{n} face sets")

    def draw(self, context):
        from . import faces
        from .ops_panels import paint_group
        layout = self.layout
        s = context.scene.fresing
        if s.face_painting:
            box = layout.box()
            wrap(box, context, f"Click faces in the view: they get the look of '{paint_group(s)}'. "
                               "Shift+click: back to the look of the part. Enter or right-click: done.",
                 icon="BRUSH_DATA", alert=True)
            primary(layout, "fresing.paint_faces_done", "Done", "CHECKMARK", MEDIUM)
        else:
            steps(layout, context, ["Pick the group whose look the faces get (or make one above)",
                                    "Press 'Paint faces' and click faces on the model",
                                    "Faces painted in CAD come in painted: they are listed below"])
            col = split_props(layout)
            col.prop_search(s, "face_group", s, "groups", text="Paint with",
                            results_are_suggestions=False)
            if not s.face_group and paint_group(s):
                hint = wrap(layout, context, f"Empty: paints with the group selected above, {paint_group(s)}")
                hint.active = False
            layout.prop(s, "face_only_copy")
            primary(layout, "fresing.paint_faces", "Paint faces…", "BRUSH_DATA", MEDIUM)
        ob = context.active_object
        if ob is None or ob.get(build.PROP_KIND) != "part" or ob.type != "MESH" or ob.data is None:
            return
        sets = faces.get_sets(ob.data)
        name = ob.get(build.PROP_NAME, ob.name)
        if not sets:
            layout.label(text=f"{name}: painted as a whole", icon="OBJECT_DATA")
            return
        layout.label(text=f"Painted faces of {name}:", icon="OBJECT_DATA")
        groups = faces.groups_on(ob)
        copy = faces.get_copy(ob)
        for k, st in enumerate(sets):
            box = layout.box()
            n = len(st.get("faces", []))
            icon = "COLOR" if st.get("kind") == "cad" else "BRUSH_DATA"
            wrap(box, context, f"{faces.label(st)}  ·  {n} face{'s' if n != 1 else ''}", icon=icon, inset=12)
            g = groups[k] if k < len(groups) else ""
            chosen = copy.get(st["key"]) or st.get("group") or ""
            text = "like the rest of the part" if chosen == faces.SAME_AS_PART else (g or "?")
            if st["key"] in copy:
                text += " (this copy only)"
            wrap(box, context, f"Look: {text}", icon="MATERIAL", inset=12)
            row = box.row(align=True)
            props = row.operator_menu_enum("fresing.face_set_group", "group", text="Other group…", icon="FORWARD")
            props.key = st["key"]
            row.operator("fresing.face_set_remove", text="Whole part", icon="X").key = st["key"]


class FRESING_UL_found(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "use", text="")
        row.label(text=item.part_name)
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=f"×{item.count}" if item.count > 1 else "")
        sub.label(text=item.groups)


class FRESING_PT_find(_Panel, bpy.types.Panel):
    bl_label = "Find & sort parts"
    bl_parent_id = "FRESING_PT_looks"

    def draw_header(self, context):
        self.layout.label(icon="VIEWZOOM")

    def draw(self, context):
        from . import finder
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if s.unmatched:
            words = finder.suggestions(scene)
            if words:
                layout.label(text="Common words in unsorted parts:", icon="LIGHT")
                grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
                for w, n in words:
                    grid.operator("fresing.find_word", text=f"{w}  {n}").word = w
        steps(layout, context, ["Type a word of the part name (all words must fit; * = any text)",
                                "Tick the parts you want",
                                "Put them in a group. 'Make it a rule' sorts them in new revisions too"])
        layout.prop(s, "find_text", text="", icon="VIEWZOOM", placeholder="e.g. seal, profile 40x40, M6*20")
        sub_row = finder.scope_row(s)
        if sub_row is not None and sub_row.depth > 0:
            layout.prop(s, "find_in_selected", text=f"Only inside {sub_row.label}")
        else:
            row = layout.row()
            row.active = False
            row.prop(s, "find_in_selected", text="Only inside a subassembly (pick it in 2)")
        if not s.find_text.strip():
            return
        if not s.found:
            layout.label(text="Nothing found", icon="INFO")
            return
        total = sum(it.count for it in s.found)
        ticked = sum(it.count for it in s.found if it.use)
        layout.label(text=f"{len(s.found)} names, {total} parts · {ticked} ticked", icon="CHECKBOX_HLT")
        row = layout.row()
        row.template_list("FRESING_UL_found", "", s, "found", s, "found_index", rows=list_rows(len(s.found), 3, 10))
        col = row.column(align=True)
        col.operator("fresing.find_tick", text="", icon="CHECKBOX_HLT").tick = True
        col.operator("fresing.find_tick", text="", icon="CHECKBOX_DEHLT").tick = False
        layout.operator("fresing.find_select", text="Select the ticked parts in the view",
                        icon="RESTRICT_SELECT_OFF")
        name = finder.group_name_for(s.find_text)
        primary(layout, "fresing.find_new_group", f"Put ticked in new group '{name}'", "ADD", MEDIUM)
        layout.operator_menu_enum("fresing.find_assign", "group", text="Put ticked in a group…", icon="IMPORT")
        if 0 <= s.groups_index < len(s.groups):
            layout.operator("fresing.find_rule", text=f"Make it a rule → {s.groups[s.groups_index].name}",
                            icon="FILTER")


class FRESING_PT_rules(_Panel, bpy.types.Panel):
    bl_label = "Sorting rules"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="FILTER")

    def draw_header_preset(self, context):
        from . import rule_sets
        if rule_sets.is_changed(context.scene.fresing):
            header_status(self.layout, "changed", alert=True)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, f"The rules of rule set '{s.rule_set or 'Standard'}' in this project. Checked from "
                              "the top; the first rule that fits a part decides its group.")
        row = layout.row()
        row.template_list("FRESING_UL_rules", "", s, "rules", s, "rules_index", rows=list_rows(len(s.rules), 4, 8))
        col = row.column(align=True)
        col.operator("fresing.rule_add", text="", icon="ADD")
        col.operator("fresing.rule_remove", text="", icon="REMOVE")
        col.separator()
        col.operator("fresing.rule_move", text="", icon="TRIA_UP").direction = "UP"
        col.operator("fresing.rule_move", text="", icon="TRIA_DOWN").direction = "DOWN"
        if 0 <= s.rules_index < len(s.rules):
            r = s.rules[s.rules_index]
            box = layout.box()
            box.label(text="If")
            row = box.row(align=True)
            row.prop(r, "field", text="")
            row.prop(r, "op", text="")
            if r.op not in ("any", "none"):
                box.prop(r, "value", text="")
            col = split_props(box)
            col.prop(r, "target", text="Group")
            col.prop(r, "note", text="Note")
        row = layout.row(align=True)
        row.operator("fresing.rule_add", text="From active part", icon="EYEDROPPER").from_selection = True
        row.operator("fresing.rules_reset", text="Defaults", icon="LOOP_BACK")


class FRESING_PT_schemes(_Panel, bpy.types.Panel):
    bl_label = "Paint schemes & templates"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="COLOR")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Paint schemes: all group colours at once", icon="COLOR")
        row = layout.row()
        row.template_list("FRESING_UL_schemes", "", s, "schemes", s, "schemes_index",
                          rows=list_rows(len(s.schemes), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.scheme_save", text="", icon="ADD")
        col.operator("fresing.scheme_remove", text="", icon="REMOVE")
        layout.separator()
        layout.label(text="Templates", icon="FILE_BLANK")
        wrap(layout, context, "A template keeps the rule set, paint schemes and background for the next project.")
        row = layout.row(align=True)
        row.operator("fresing.template_import", text="Load", icon="FILE_FOLDER")
        row.operator("fresing.template_export", text="Save", icon="FILE_TICK")
        row.operator("fresing.template_from_library", text="Library", icon="ASSET_MANAGER")


# =============================================================================
# 5 Scene & Render
# =============================================================================


class FRESING_PT_scene(_Panel, bpy.types.Panel):
    bl_label = "5  Scene & Render"
    bl_order = 4

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="RENDER_STILL")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        scene = context.scene

        # -- background and light
        layout.label(text="Background & light", icon="WORLD")
        col = split_props(layout)
        col.prop(s, "background", text="Background")
        if s.background == "COLOR":
            col.prop(s, "background_color", text="Colour")
        elif s.background == "HDRI":
            row = col.row(align=True)
            row.prop(s, "hdri_path", text="Photo")
            row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "BACKGROUND"
        if s.background in ("COLOR", "TRANSPARENT"):
            col.prop(s, "lighting", text="Light")
            if s.lighting == "HDRI":
                row = col.row(align=True)
                row.prop(s, "light_hdri_path", text="Light photo")
                row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "LIGHT"
        col = split_props(layout)
        col.prop(s, "light_rotation", text="Turn light")
        col.prop(s, "light_strength", text="Strength")
        if s.background == "SKY" or (s.background in ("COLOR", "TRANSPARENT") and s.lighting == "SKY"):
            col.prop(s, "sun_elevation", text="Sun height")
        col.prop(s, "exposure", text="Exposure")
        col = split_props(layout)
        col.prop(s, "floor", text="Floor")
        if s.floor == "VISIBLE":
            col.prop(s, "floor_use_own_color", text="Own colour")
            if s.floor_use_own_color:
                col.prop(s, "floor_color", text="Floor colour")
        if s.floor != "NONE":
            col.prop(s, "floor_offset", text="Gap")

        # -- camera
        layout.separator()
        layout.label(text="Camera", icon="CAMERA_DATA")
        cams = cameras.fr_cameras(scene)
        col = layout.column(align=True)
        for cam in cams:
            row = col.row(align=True)
            active = scene.camera == cam
            op = row.operator("fresing.camera_activate", text=cam.name,
                              icon="RADIOBUT_ON" if active else "RADIOBUT_OFF", depress=active)
            op.name = cam.name
            op = row.operator("fresing.camera_remove", text="", icon="X")
            op.name = cam.name
        if not cams:
            col.label(text="No camera yet: add one", icon="INFO")
        row = layout.row(align=True)
        row.operator_menu_enum("fresing.camera_add", "view", text="Add camera", icon="ADD")
        row.operator("fresing.camera_fit", text="Fit model", icon="FULLSCREEN_ENTER")
        if scene.camera is not None and scene.camera.type == "CAMERA":
            row = layout.row(align=True)
            row.prop(scene.camera.data, "lens", text="Lens")
            row.operator("fresing.camera_dof", text="Blur", icon="CAMERA_DATA",
                         depress=scene.camera.data.dof.use_dof)
            if scene.camera.data.dof.use_dof:
                layout.prop(scene.camera.data.dof, "aperture_fstop", text="Blur f-stop (lower = more)")


def _viewport_rendered(context) -> bool:
    for area in getattr(context.screen, "areas", []) if context.screen else []:
        if area.type == "VIEW_3D":
            return area.spaces.active.shading.type == "RENDERED"
    return False


class FRESING_PT_output(_Panel, bpy.types.Panel):
    bl_label = "Image size & render"
    bl_parent_id = "FRESING_PT_scene"

    def draw_header(self, context):
        self.layout.label(icon="IMAGE_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        col = split_props(layout)
        col.prop(s, "out_format", text="Format")
        kind = presets.FORMATS.get(s.out_format, {}).get("kind")
        if kind == "screen":
            col.prop(s, "out_resolution", text="Size")
            col.prop(s, "out_orientation", text="Orientation")
        elif kind == "paper":
            col.prop(s, "out_dpi", text="Resolution")
            col.prop(s, "out_orientation", text="Orientation")
            col.prop(s, "out_use_bleed", text="Bleed")
            if s.out_use_bleed:
                col.prop(s, "out_bleed_mm", text="Bleed (mm)")
        else:
            col.prop(s, "out_custom_w", text="Width")
            col.prop(s, "out_custom_h", text="Height")
        size = presets.compute(s.out_format, s.out_resolution, s.out_orientation, int(s.out_dpi),
                               s.out_bleed_mm if s.out_use_bleed else 0.0, s.out_custom_w, s.out_custom_h)
        col.prop(s, "quality", text="Quality")
        layout.label(text=f"{size.width} × {size.height} px  ({size.megapixels:.1f} MP)", icon="IMAGE_DATA")

        row = layout.row(align=True)
        live = _viewport_rendered(context)
        row.operator("fresing.preview", text="Live preview: on" if live else "Live preview",
                     icon="SHADING_RENDERED", depress=live)
        primary(layout, "fresing.render", "Render image", "RENDER_STILL")
        if s.last_render and os.path.exists(s.last_render):
            box = layout.box()
            box.label(text=os.path.basename(s.last_render), icon="CHECKMARK")
            row = box.row(align=True)
            row.operator("fresing.open_file", text="Open", icon="IMAGE").path = s.last_render
            row.operator("fresing.show_in_folder", text="Show in folder", icon="FILE_FOLDER").path = s.last_render

        body = fold(layout, "fr_output_more", "Files & graphics card")
        if body:
            col = split_props(body)
            col.prop(s, "out_file_type", text="File")
            col.prop(s, "out_folder", text="Folder")
            col.prop(s, "use_gpu", text="Graphics card")
            wrap(body, context, "Empty folder: 'Renders' next to the saved project "
                                "(Pictures\\Fresing Render before it is saved).")
            body.operator("fresing.open_folder", text="Open render folder", icon="FILE_FOLDER")


CLASSES = (
    FRESING_UL_tree, FRESING_UL_groups, FRESING_UL_rules, FRESING_UL_schemes, FRESING_UL_visibility,
    FRESING_UL_found,
    FRESING_PT_import, FRESING_PT_structure, FRESING_PT_cleanup, FRESING_PT_visibility, FRESING_PT_looks,
    FRESING_PT_faces, FRESING_PT_find, FRESING_PT_rules, FRESING_PT_schemes, FRESING_PT_scene, FRESING_PT_output,
)
