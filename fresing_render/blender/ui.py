"""Side panel in the 3D viewport: 1 Import, 2 Structure, 3 Looks, (4 Motion,) 5 Scene & Render.

Layout rules for every section (read top to bottom, no jumping back up):
* what you choose before an action sits above its button; the main button of a section is big;
* each list shows names only, the details of the selected item are in the box right under it;
* one-time and rarely used settings are in a closed "More" fold at the end;
* the panel header shows an icon and the state of the section, also when it is folded – every sub-panel too
  (``draw_header_preset`` + ``header_status``).
* **Separation (task 0062):** a panel is a row of steps (how-to · choices · main button · list · details · more) with
  a ``gap()`` between two steps; buttons of different steps never touch. The numbered how-to is ``steps(..., key=,
  used=)``: a fold "How it works" that closes once the project has the thing. A hint is grey (``hint()``, or
  ``wrap(icon="INFO")``); red (``alert=True``) only for a problem. ONE blue button per section (``primary()``): the
  one thing the section is for; a sub-panel's main button is ``big()`` – big, grey. When the thing a sub-panel needs
  is not there, its body is one ``missing()`` line with the button that gets it. Nothing is cut off with "…" at the
  default width. A text that names a place in the side panel asks ``where()``.
* The headers themselves (title row, fold arrow, open or folded) are drawn by ``panels.py`` for every panel class:
  a panel file only says ``draw_header`` (its icon), ``draw_header_preset`` (its state) and ``draw`` (its body).
* One word per action: Remove (out of the project) · Clear (a list, a cache, a result) · Delete (a file in the
  library) · Show in folder · Add (a new thing) · Use as (the clicked part) · Back to … (says where to) · Find ·
  Set-up (the noun), Set up (the verb).
"""

from __future__ import annotations

import contextlib
import json
import os
import textwrap

import bpy

from ..core import fasteners, materials_lib, presets, studio
from ..core.words import plural, verb
from ..core import surroundings as env
from . import build, cameras, materials

CATEGORY = "Fresing"
PHOTOS_URL = "https://github.com/smholte/CAD-render-animation/blob/main/docs/SURROUNDINGS.md#getting-360-photos"
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


_POPOVER = {"units": 0}      # > 0 while a panel's body is drawn in a popover of that width (Make, task 0062)


@contextlib.contextmanager
def popover_width(units: int):
    """While a side-panel body is drawn in a popover: texts wrap at the popover's width (not the side panel's)
    and the body's main button (``big()``) is blue – in a popover it is the one thing to press."""
    old = _POPOVER["units"]
    _POPOVER["units"] = units
    try:
        yield
    finally:
        _POPOVER["units"] = old


def _chars_per_line(context, inset: int = 0) -> int:
    if _POPOVER["units"]:
        return max(18, int((_POPOVER["units"] * 20 - 34 - inset) / 6.6))
    region = getattr(context, "region", None)
    width = getattr(region, "width", 0) or 300
    try:
        scale = context.preferences.system.ui_scale or 1.0
    except AttributeError:
        scale = 1.0
    return max(18, int((width / scale - 34 - inset) / 6.6))


def wrap(layout, context, text: str, icon: str = "NONE", inset: int = 0, alert: bool = False):
    """A message on as many lines as it needs (Blender cuts long labels off with '...'). A plain hint
    (``icon="INFO"``, no alert) is drawn grey, so the real warnings stand out."""
    col = layout.column(align=True)
    col.alert = alert
    if icon == "INFO" and not alert:
        col.active = False
    lines = textwrap.wrap(text, _chars_per_line(context, inset + (22 if icon != "NONE" else 0))) or [""]
    for i, line in enumerate(lines):
        col.label(text=line, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))
    return col


def hint(layout, context, text: str, inset: int = 0):
    """A grey hint without an icon, on as many lines as it needs."""
    col = wrap(layout, context, text, inset=inset)
    col.active = False
    return col


def gap(layout, line: bool = False, size: float = 1.0) -> None:
    """The space between two steps of a panel (the separation rule at the top of this file); ``line``: with a
    thin line, between two parts that have nothing to do with each other."""
    if line:
        layout.separator(factor=0.5 * size)
        layout.separator(type="LINE")
        layout.separator(factor=0.5 * size)
    else:
        layout.separator(factor=size)


def _keep_howto() -> bool:
    try:
        from . import prefs
        p = prefs.get()
        return bool(p is not None and p.keep_howto)
    except Exception:  # noqa: BLE001 - drawing never fails over a preference
        return False


def steps(layout, context, lines: list[str], key: str = "", used: bool = False):
    """The numbered how-to of a panel, in a fold "How it works" (task 0062, ``key`` = the fold's id, like
    "fr_how_cutaway"): open while the project does not have the thing yet, closed once it does (``used``); the
    user can open and close it, and Preferences > "Keep How it works open" keeps them all open. Without ``key``:
    a plain box (inside a box, where a fold cannot be drawn). Returns the box, or None when folded."""
    if key:
        closed = bool(used) and not _keep_howto()
        body = fold(layout, f"{key}_{'u' if closed else 'n'}", "How it works", icon="QUESTION", closed=closed)
        if body is None:
            return None
        box = body.box()
    else:
        box = layout.box()
    col = box.column(align=True)
    for i, line in enumerate(lines, 1):
        for k, part in enumerate(textwrap.wrap(line, _chars_per_line(context, 40)) or [""]):
            col.label(text=f"{i}.  {part}" if k == 0 else f"     {part}")
    return box


_OPEN_FOLDS = bool(os.environ.get("FRESING_UI_OPEN_FOLDS"))     # screenshots of everything

# What a lesson hooks in (blender/highlight.py, task 0062): "fold" = fn(idname) -> True when the fold must be open
# now (the lesson points into it); "header" = fn(layout, panel class name) draws the marker in a panel's title row.
HOOKS = {"fold": None, "header": None}


def fold(layout, idname: str, title: str, icon: str = "NONE", closed: bool = True):
    """A foldable part of a panel; returns its body layout or None when folded."""
    forced = HOOKS["fold"]
    if forced is not None and forced(idname):          # a lesson points into this fold: open, whatever it was
        header, body = layout.panel_prop(context_wm(), "fresing_fold_open")
    else:
        header, body = layout.panel(idname, default_closed=closed and not _OPEN_FOLDS)
    header.label(text=title, icon=icon)
    return body


def context_wm():
    return bpy.context.window_manager


def where(panel: str, fold: str = "") -> str:
    """Where a panel sits, for hints and messages: "6 Animation > Labels" (core/places.py)."""
    from ..core import places
    return places.where(panel, fold)


def missing(layout, context, text: str, op: str = "", op_text: str = "", icon: str = "INFO", op_icon: str = "NONE"):
    """The whole body of a sub-panel whose thing is not there (no sea, no vessel, no axis joint): ONE line that
    says what is missing and, with ``op``, the button that gets it. Returns that button's operator (or None)."""
    col = layout.column(align=True)
    wrap(col, context, text, icon=icon)
    if not op:
        return None
    return col.operator(op, text=op_text, icon=op_icon) if op_text else col.operator(op, icon=op_icon)


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
    row.alignment = "RIGHT"
    row.alert = alert
    row.label(text=text, icon=icon)


def use_button(row, idname: str, name: str) -> None:
    """The small 'Use' button at the end of a list row; the name gets the rest of the row."""
    sub = row.row(align=True)
    sub.ui_units_x = 2.6
    sub.operator(idname, text="Use").name = name


def primary(layout, idname: str, text: str, icon: str, scale: float = BIG):
    """The ONE main button of a section: big and blue, so it is found at a glance (Import STEP…, Sort parts into
    groups, Render image, Build & play, Start queue; the Make button of a Make popover). A sub-panel's main
    button is ``big()``."""
    row = big_row(layout, scale)
    return row.operator(idname, text=text, icon=icon, depress=True)


def big(layout, idname: str, text: str, icon: str = "NONE", scale: float = MEDIUM):
    """A sub-panel's main button: big, but grey – blue is kept for the section's one main button."""
    row = big_row(layout, scale)
    return row.operator(idname, text=text, icon=icon, depress=bool(_POPOVER["units"]))


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
            hint(layout, context, "or drag a .step file onto the view")
            layout.operator("fresing.import_mesh", text="Import mesh model…", icon="MESH_DATA")

        roots = build.model_roots(context.scene)
        if roots:
            gap(layout)
        for root in roots:
            box = layout.box()
            box.label(text=root.name, icon="OUTLINER_OB_GROUP_INSTANCE")
            try:
                st = json.loads(root.get("fr_stats", "{}"))
            except ValueError:
                st = {}
            if st:
                col = box.column(align=True)
                col.label(text=f"{plural(st.get('placed_parts', 0), 'part')}, {st.get('unique_parts', 0)} different")
                helpers = st.get("mesh_helpers", 0)
                col.label(text=f"{st.get('triangles_unique', 0) / 1e6:.1f} M triangles · read in "
                               f"{st.get('seconds_total', 0):.0f} s"
                               + (f" on {plural(helpers, 'core')}" if helpers else ""))
            from . import mesh_import
            if mesh_import.is_mesh_model(root):        # task 0117: where it came from and whom to credit
                col = box.column(align=True)
                col.label(text=f"Mesh model: {os.path.basename(root.get(build.PROP_SOURCE, '') or '')}",
                          icon="MESH_DATA")
                credit = root.get(mesh_import.PROP_CREDIT, "")
                wrap(col, context, f"Credit: {credit}" if credit else "No credit line in the file: check its licence",
                     icon="COPY_ID" if credit else "ERROR", inset=12)
                for note in mesh_import.notes(root)[:4]:
                    wrap(col, context, note, icon="INFO", inset=12)
                op_id = "fresing.import_mesh"
            else:
                op_id = "fresing.import_step"
            if not _client_locked(context):            # the Client view never replaces a model
                op = box.operator(op_id, text="Update to new revision…", icon="FILE_REFRESH")
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
        gap(layout)
        body = fold(layout, "fr_import_more", "More")
        if body:
            hint(body, context, "Imports are stored, so an unchanged file opens again in seconds.")
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
        header_status(self.layout, plural(n, "part"))

    def draw(self, context):
        from . import tree as tree_mod
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="A click in the view selects a:", icon="RESTRICT_SELECT_OFF")
        row = layout.row(align=True)
        row.prop(s, "pick_mode", expand=True)

        gap(layout)
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
            text = (it.label + (f"  ×{it.same}" if it.same > 1 else "")
                    + ("" if it.is_part else f"  ({plural(it.parts, 'part')})"))
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
        gap(layout)
        row = layout.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.hide_selected", text="Hide", icon="HIDE_ON")
        row.operator("fresing.show_only_selected", text="Show only", icon="SELECT_SET")
        row.operator("fresing.show_all", text="Show all", icon="HIDE_OFF")


_REMOVED = {"key": None, "n": 0}


def _removed_count(scene) -> int:
    """How many parts Clean-up took out (counted once per change of the scene's object list, not per redraw)."""
    key = (scene.name, len(scene.objects))
    if _REMOVED["key"] != key:
        _REMOVED.update(key=key, n=sum(1 for ob in scene.objects if ob.get(build.PROP_EXCLUDED)))
    return _REMOVED["n"]


class FRESING_PT_cleanup(_Panel, bpy.types.Panel):
    bl_label = "Clean-up"
    bl_parent_id = "FRESING_PT_structure"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="BRUSH_DATA")

    def draw_header_preset(self, context):
        n = _removed_count(context.scene)
        if n:
            header_status(self.layout, f"{n} removed")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        hint(layout, context, "Remove parts that never show, for faster renders.")
        steps(layout, context, ["Select the parts (or small ones below)", "Remove selected"],
              key="fr_how_cleanup", used=_removed_count(context.scene) > 0)
        gap(layout)
        col = split_props(layout)
        col.prop(s, "small_part_mm", text="Max size (mm)")
        layout.operator("fresing.select_small", text="Select the small parts", icon="RESTRICT_SELECT_OFF")
        gap(layout)
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

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.visibility_sets)
        if n:
            header_status(self.layout, plural(n, "set"))

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        hint(layout, context, "Which parts are hidden, saved under a name. + saves what is hidden now.")
        row = layout.row()
        row.template_list("FRESING_UL_visibility", "", s, "visibility_sets", s, "visibility_index",
                          rows=list_rows(len(s.visibility_sets), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.vis_save", text="", icon="ADD")
        col.operator("fresing.vis_remove", text="", icon="REMOVE")
        col.operator("fresing.vis_update", text="", icon="FILE_REFRESH")
        if 0 <= s.visibility_index < len(s.visibility_sets):
            v = s.visibility_sets[s.visibility_index]
            layout.label(text=f"{v.name}: {plural(len(v.hidden), 'part')} hidden", icon="HIDE_ON")


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
            hint(box, context, "Standard itself cannot be changed.", inset=12)
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
        op = box.operator("fresing.rule_set_switch", text="Load it…", icon="IMPORT")
        op.name, op.again = name, True
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
        body.operator("fresing.rule_set_folder", text="Show in folder", icon="FILE_FOLDER")
    gap(layout)


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
            header_status(self.layout, plural(len(s.groups), "group"))

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        draw_rule_set(layout, context)
        primary(layout, "fresing.apply_rules", "Sort parts into groups", "SORTALPHA", MEDIUM)
        if s.unmatched:
            wrap(layout, context, f"{plural(s.unmatched, 'part')} {verb(s.unmatched, 'matches', 'match')} no rule: "
                                  f"{verb(s.unmatched, 'it is', 'they are')} in 'Unsorted'. "
                                  "Find & sort parts (below) helps.", icon="ERROR", alert=True)
            layout.operator("fresing.show_only_group", text="Show only the unsorted parts",
                            icon="HIDE_OFF").group = ""
        gap(layout)
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
            parts_txt = plural(g.count, "part")
            faces_txt = f" and {plural(g.faces, 'painted face set')}" if g.faces else ""
            wrap(box, context, f"{g.name}  ·  {parts_txt}{faces_txt}", icon="MATERIAL", inset=12)
            box.operator_menu_enum("fresing.group_preset", "preset", text="Ready-made material…",
                                   icon="PRESET")
            col = split_props(box)
            col.prop(g, "material", text="Material")
            if materials_lib.needs_color(g.material):
                row = col.row(align=True)
                row.prop(g, "color", text="Colour")
                row.operator("fresing.pick_ral", text="", icon="VIEWZOOM")
            col.prop(g, "wear", text="Wear", slider=True)
            row = box.row(align=True)
            row.operator("fresing.group_select", text="Select its parts", icon="RESTRICT_SELECT_OFF")
            row.operator("fresing.show_only_group", text="Show only these", icon="HIDE_OFF").group = g.name
            row = box.row(align=True)
            row.operator("fresing.group_assign", text="Put selected in", icon="IMPORT")
            row.operator("fresing.group_unassign", text="Back to the rules", icon="LOOP_BACK")
            if 0 <= s.tree_index < len(s.tree) and not s.tree[s.tree_index].is_part:
                sub = s.tree[s.tree_index]
                hint(box, context, f"Everything in {sub.label} to this group:", inset=12)
                box.operator("fresing.rule_from_subassembly", text="Make it a rule", icon="FILTER")
        ob = context.active_object
        if ob is not None and ob.get(build.PROP_KIND) == "part":
            gap(layout)
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
                header_status(self.layout, plural(n, "face set"))

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
            big(layout, "fresing.paint_faces_done", "Done", "CHECKMARK")
        else:
            steps(layout, context, ["Pick the group whose look the faces get (or make one above)",
                                    "Press 'Paint faces' and click faces on the model",
                                    "Faces painted in CAD come in painted: they are listed below"],
                  key="fr_how_faces", used=any(g.faces for g in s.groups))
            gap(layout)
            col = split_props(layout)
            col.prop_search(s, "face_group", s, "groups", text="Paint with",
                            results_are_suggestions=False)
            if not s.face_group and paint_group(s):
                hint(layout, context, f"Empty: paints with the group selected above, {paint_group(s)}")
            layout.prop(s, "face_only_copy")
            gap(layout)
            big(layout, "fresing.paint_faces", "Paint faces…", "BRUSH_DATA")
        ob = context.active_object
        if ob is None or ob.get(build.PROP_KIND) != "part" or ob.type != "MESH" or ob.data is None:
            return
        gap(layout)
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
            wrap(box, context, f"{faces.label(st)}  ·  {plural(n, 'face')}", icon=icon, inset=12)
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

    def draw_header_preset(self, context):
        s = context.scene.fresing
        if s.find_text.strip():
            header_status(self.layout, f"{len(s.found)} found")
        elif s.unmatched:
            header_status(self.layout, f"{s.unmatched} unsorted", alert=True)

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
                gap(layout)
        steps(layout, context, ["Type a word of the part name (all words must fit; * = any text)",
                                "Tick the parts you want",
                                "Put them in a group. 'Make it a rule' sorts them in new revisions too"],
              key="fr_how_find", used=not s.unmatched)
        layout.prop(s, "find_text", text="", icon="VIEWZOOM", placeholder="e.g. seal, profile 40x40, M6*20")
        sub_row = finder.scope_row(s)
        if sub_row is not None and sub_row.depth > 0:
            layout.prop(s, "find_in_selected", text=f"Only inside {sub_row.label}")
        else:
            row = layout.row()
            row.active = False
            row.prop(s, "find_in_selected", text="Only inside a subassembly")
        if not s.find_text.strip():
            return
        if not s.found:
            hint(layout, context, "Nothing found")
            return
        total = sum(it.count for it in s.found)
        ticked = sum(it.count for it in s.found if it.use)
        layout.label(text=f"{plural(len(s.found), 'name')}, {plural(total, 'part')} · {ticked} ticked",
                     icon="CHECKBOX_HLT")
        row = layout.row()
        row.template_list("FRESING_UL_found", "", s, "found", s, "found_index", rows=list_rows(len(s.found), 3, 10))
        col = row.column(align=True)
        col.operator("fresing.find_tick", text="", icon="CHECKBOX_HLT").tick = True
        col.operator("fresing.find_tick", text="", icon="CHECKBOX_DEHLT").tick = False
        layout.operator("fresing.find_select", text="Select the ticked parts in the view",
                        icon="RESTRICT_SELECT_OFF")
        gap(layout)
        name = finder.group_name_for(s.find_text)
        if len(name) > 14:                         # the button stays readable at the default width
            big(layout, "fresing.find_new_group", "Put ticked in a new group", "ADD")
            hint(layout, context, f"It is called '{name}'.")
        else:
            big(layout, "fresing.find_new_group", f"Put ticked in new group '{name}'", "ADD")
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
        else:
            header_status(self.layout, plural(len(context.scene.fresing.rules), "rule"))

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        hint(layout, context, f"The rules of rule set '{s.rule_set or 'Standard'}' in this project. Checked from "
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
        gap(layout)
        col = layout.column(align=True)
        col.operator("fresing.rule_add", text="Add from the clicked part", icon="EYEDROPPER").from_selection = True
        col.operator("fresing.rules_reset", text="Back to the defaults", icon="LOOP_BACK")


class FRESING_PT_schemes(_Panel, bpy.types.Panel):
    bl_label = "Paint schemes & templates"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="COLOR")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.schemes)
        if n:
            header_status(self.layout, plural(n, "scheme"))

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
        gap(layout, line=True)
        layout.label(text="Templates", icon="FILE_BLANK")
        hint(layout, context, "A template keeps the rule set, paint schemes and background for the next project.")
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

    def draw_header_preset(self, context):
        kind = env.KIND.get(context.scene.fresing.background)
        if kind is not None:
            header_status(self.layout, env.SHORT.get(kind.id, kind.label), limit=12)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        bg = s.background
        offshore = bg in env.SEA_KINDS
        hall = bg in env.HALL_KINDS

        # -- a ready-made look first: it sets the background, the light and the floor below
        layout.label(text="Light look", icon="LIGHT")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for look, (label, icon, _tip) in studio.LOOKS.items():
            grid.operator("fresing.light_look", text=label, icon=icon,
                          depress=studio.look_matches(look, s)).look = look
        gap(layout)

        # -- where the machine stands (choice first, then its settings)
        layout.label(text="Background & surroundings", icon="WORLD")
        col = split_props(layout)
        col.prop(s, "background", text="Background")
        if bg == "COLOR":
            col.prop(s, "background_color", text="Colour")
        elif bg == "HDRI":
            row = col.row(align=True)
            row.prop(s, "hdri_path", text="Photo")
            row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "BACKGROUND"
            col.prop(s, "photo_ground", text="Stand on its ground")
            if s.photo_ground:
                col.prop(s, "photo_height", text="Photo taken at")
            if not s.hdri_path:
                wrap(layout, context, "Pick a 360° photo with the library button next to 'Photo'.", icon="INFO")
                layout.operator("wm.url_open", text="How to get free 360° photos", icon="URL").url = PHOTOS_URL
        if offshore:
            col.prop(s, "sea_state", text="Sea")              # a drop-down: "From the wind" was cut off as a button
            from .ops_scene import draw_start_scene         # Build puts the start scene's sea back (task 0160)
            draw_start_scene(col, context, ["sea_state", "water_level"])
            if bg == "SEA":
                col.prop(s, "water_level", text="Water level")
                col.prop(s, "sea_depth", text="Water depth")
                col.prop(s, "sea_clarity", text="Water clarity")
                col.prop(s, "sea_cutaway", text="Cut-away behind the stern")
                if s.sea_cutaway and _shows(context, "scene.sea_ground"):
                    col.prop(s, "sea_cut_ground", text="Show the ground in the cut-away")
            row = col.row(heading="Waves")
            row.prop(s, "sea_foam", text="Foam")
            row.prop(s, "sea_moving", text="Moving")
        if bg in env.BUILT:
            row = col.row(align=True)
            row.prop(s, "env_detail", text="Detail", expand=True)

        # -- light
        gap(layout)
        layout.label(text="Light", icon="LIGHT_SUN")
        col = split_props(layout)
        if bg in ("COLOR", "TRANSPARENT") or hall:
            col.prop(s, "lighting", text="Light")
            if s.lighting == "HDRI":
                row = col.row(align=True)
                row.prop(s, "light_hdri_path", text="Light photo")
                row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "LIGHT"
        light = effective_lighting(s)
        sky = light == "SKY"
        overcast = sky and s.sky_weather == "OVERCAST"
        from . import weather as weather_mod
        timed = sky and weather_mod.sky_on(context.scene)      # task 0109: the clock sets the sun and the clouds
        if sky and not timed:
            row = col.row(align=True)
            row.prop(s, "sky_weather", text="Weather", expand=True)
            if not overcast:
                col.prop(s, "sun_elevation", text="Sun height")
        if timed:
            pass
        elif not overcast:                     # an overcast sky looks the same from every side
            col.prop(s, "light_rotation",
                     text="Turn sun" if sky else ("Turn photo" if bg == "HDRI" else "Turn light"))
        col.prop(s, "light_strength", text="Brightness")
        col.prop(s, "exposure", text="Exposure")
        if timed:
            wrap(layout, context, f"The sun, the sky and the clouds follow {where('weather')}: "
                 + weather_mod.header(context.scene) + ".", icon="INFO")
        else:
            wrap(layout, context, studio.light_words(light, s.sky_weather, s.light_rotation, s.light_strength,
                                                     s.sun_elevation), icon="INFO")

        # -- floor (the surroundings and the photo's ground bring their own)
        own_floor = bg in env.BUILT or (bg == "HDRI" and s.photo_ground)
        gap(layout)
        if not own_floor:
            col = split_props(layout)
            col.prop(s, "floor", text="Floor")
            if s.floor == "VISIBLE":
                col.prop(s, "floor_use_own_color", text="Own colour")
                if s.floor_use_own_color:
                    col.prop(s, "floor_color", text="Floor colour")
            if s.floor != "NONE":
                col.prop(s, "floor_offset", text="Gap")
        else:
            body = fold(layout, "fr_scene_more", "More", "PREFERENCES")
            if body:
                col = split_props(body)
                col.prop(s, "floor_offset", text="Floor lower by")
                if bg in env.BUILT:
                    col.prop(s, "env_show_in_view", text="Show in the view")
                body.operator("fresing.env_place", icon="IMPORT")
            if bg in env.BUILT and surroundings_misfit(context.scene):
                wrap(layout, context, "The model you added sticks out of the surroundings. "
                     "Fit them to everything with the button below.", icon="ERROR")
                layout.operator("fresing.env_place", icon="IMPORT")


def _client_locked(context) -> bool:
    from . import lock
    return bool(lock.ON[0])


def _shows(context, fid: str) -> bool:
    """Does the project's workspace show this function (core/functions.py id)? For a setting that belongs to
    another kind of work than the rest of its panel."""
    from . import workspaces
    return workspaces.shows(context.scene, fid)


def surroundings_misfit(scene) -> bool:
    from . import surroundings
    return surroundings.misfit(scene)


def effective_lighting(s) -> str:
    """What really lights the machine: the photo, the sky (also on the sea) or the Light choice."""
    if s.background == "HDRI":
        return "HDRI"
    if s.background == "SKY" or s.background in env.SEA_KINDS:
        return "SKY"
    return s.lighting


VIEW_ICONS = {"ISOMETRIC": "VIEW_ORTHO", "FRONT": "AXIS_FRONT", "SIDE": "AXIS_SIDE", "TOP": "AXIS_TOP",
              "LOW": "CON_CAMERASOLVER", "HIGH": "VIEW_CAMERA"}


class FRESING_PT_camera(_Panel, bpy.types.Panel):
    bl_label = "Camera"
    bl_parent_id = "FRESING_PT_scene"

    def draw_header(self, context):
        self.layout.label(icon="CAMERA_DATA")

    def draw_header_preset(self, context):
        cam = context.scene.camera
        header_status(self.layout, cam.name if cam is not None else "none", alert=cam is None, limit=22)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
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
            hint(col, context, "No camera yet: add one below")

        # -- a new camera: what it frames first, then the view buttons
        gap(layout)
        layout.label(text="Add a camera", icon="ADD")
        row = layout.row(align=True)                 # full width: the choices are never cut off
        row.prop(s, "view_frame", expand=True)
        split_props(layout).prop(s, "view_space", text="Space around")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for view in cameras.STANDARD_VIEWS:
            grid.operator("fresing.camera_add", text=cameras.VIEWS[view][0], icon=VIEW_ICONS.get(view, "VIEW_CAMERA")
                          ).view = view
        row = layout.row(align=True)
        split = row.split(factor=0.66, align=True)
        split.operator("fresing.camera_add", text="Where I look now", icon="HIDE_OFF").view = "VIEW"
        split.operator_menu_enum("fresing.camera_add", "view", text="More")

        cam = scene.camera
        if cam is None or cam.type != "CAMERA":
            return
        # -- the active camera
        gap(layout, line=True)
        wrap(layout, context, f"Active: {cam.name}", icon="VIEW_CAMERA")
        layout.operator("fresing.camera_fit", text="Fit to the picture", icon="FULLSCREEN_ENTER")
        col = split_props(layout)
        if cam.data.type == "PERSP":
            col.prop(s, "camera_lens", text="Lens (mm)")
        if not cameras.can_blur(cam):
            wrap(layout, context, "No background blur in a view without perspective (Isometric).", icon="INFO")
            return
        gap(layout)
        layout.label(text="Background blur")
        row = layout.row(align=True)
        row.prop(s, "camera_blur", expand=True)
        if cameras.blur_level(cam) != "NONE":
            row = layout.row(align=True)
            split = row.split(factor=0.34, align=True)
            split.label(text="Sharp at")
            sub = split.row(align=True)
            sub.label(text=cameras.focus_label(cam), icon="PIVOT_CURSOR")
            sub.operator("fresing.focus_pick", text="", icon="EYEDROPPER")
            if cameras.focus_marker(cam) is not None:
                sub.operator("fresing.focus_clear", text="", icon="X")


_DETAIL_LABEL = {"AUTO": "auto", "DETAILED": "always detailed", "LIGHT": "always light"}


class FRESING_PT_props(_Panel, bpy.types.Panel):
    bl_label = "Props for scale"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="COMMUNITY")

    def draw_header_preset(self, context):
        from . import surroundings
        n = len(surroundings.props(context.scene))
        if n:
            header_status(self.layout, f"{n} shown" if context.scene.fresing.props_visible else f"{n} hidden")

    def draw(self, context):
        from . import surroundings
        layout = self.layout
        s = context.scene.fresing
        hint(layout, context, "Things everyone knows the size of, next to the machine. Click to add one:")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        icons = {"PERSON": "USER", "CONTAINER": "PACKAGE", "PALLET": "MESH_GRID", "BARRIER": "CON_TRACKTO",
                 "IBC": "MESH_CUBE", "GAS_RACK": "MOD_ARRAY", "TOOL_TROLLEY": "TOOL_SETTINGS"}
        for kind, (label, _desc) in env.PROPS.items():
            grid.operator("fresing.prop_add", text=label, icon=icons.get(kind, "ADD")).kind = kind
        if surroundings.props(context.scene):
            gap(layout)
            hint(layout, context, "Move a prop: click it in the view and drag the arrows (or press G).")
            row = layout.row(align=True)
            row.prop(s, "props_visible", text="Show props", toggle=True,
                     icon="HIDE_OFF" if s.props_visible else "HIDE_ON")
            row.operator("fresing.props_remove", text="Remove all", icon="TRASH")
            ob = context.active_object
            if ob is not None and ob.get(surroundings.PROP_TAG) == "PERSON" and hasattr(ob, "fresing_person"):
                person = ob.fresing_person         # task 0155: the selected person's pose and clothes
                box = layout.box()
                box.label(text=f"Selected person: {ob.name}", icon="USER")
                col = box.column(align=True)
                col.prop(person, "pose")
                col.prop(person, "height_choice")
                col.prop(person, "outfit")
                row = box.row(align=True)
                row.prop(person, "helmet", toggle=True)
                row.prop(person, "gloves", toggle=True)
                row.prop(person, "look")
            else:
                hint(layout, context, "Click a person in the view to choose its pose, height and clothes.")
            gap(layout)
            body = fold(layout, "fresing_props_detail", f"Detail: {_DETAIL_LABEL.get(s.props_detail, '')}",
                        "MOD_DECIM")
            if body is not None:
                body.prop(s, "props_detail", text="")
                if s.props_detail == "AUTO":
                    body.prop(s, "props_far")


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

    def draw_header_preset(self, context):
        s = context.scene.fresing
        size = presets.compute(s.out_format, s.out_resolution, s.out_orientation, int(s.out_dpi),
                               s.out_bleed_mm if s.out_use_bleed else 0.0, s.out_custom_w, s.out_custom_h)
        header_status(self.layout, f"{size.width} × {size.height}")

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

        gap(layout)
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

        gap(layout)
        body = fold(layout, "fr_output_more", "Files & graphics card")
        if body:
            col = split_props(body)
            col.prop(s, "out_file_type", text="File")
            col.prop(s, "out_folder", text="Folder")
            col.prop(s, "use_gpu", text="Graphics card")
            hint(body, context, "Empty folder: 'Renders' next to the saved project "
                                "(Pictures\\Fresing Render before it is saved).")
            body.operator("fresing.open_folder", text="Show in folder", icon="FILE_FOLDER")


class FRESING_PT_turntable(_Panel, bpy.types.Panel):
    bl_label = "Turntable video"
    bl_parent_id = "FRESING_PT_scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="FILE_MOVIE")

    def draw_header_preset(self, context):
        from . import turntable
        a = turntable.find_animation(context.scene)
        job = None if a is None else next((j for j in reversed(context.scene.fresing.queue)
                                           if j.animation == a.name), None)
        if job is not None and job.status in ("WAITING", "RUNNING"):
            header_status(self.layout, "in the queue")
        else:
            header_status(self.layout, f"{context.scene.fresing.turntable_seconds:g} s")

    def draw(self, context):
        from . import turntable
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        hint(layout, context, "A video of the camera going once round the machine, as it looks now. "
                              "The video loops: its end joins its start.")
        col = split_props(layout)
        col.prop(s, "turntable_seconds", text="Length (s)")
        row = col.row(align=True)
        row.prop(s, "turntable_height", text="Camera height", expand=True)
        col.prop(s, "turntable_quality", text="Quality")
        a = turntable.find_animation(scene)
        fps = int(a.fps) if a is not None else 25
        frames = studio.turntable_timing(s.turntable_seconds, fps)[0]
        layout.label(text=f"{frames} frames ({fps} per second)", icon="RENDER_ANIMATION")
        note = turntable.slow_note(s)
        if note:
            box = layout.box()
            wrap(box, context, note + ".", icon="INFO", inset=12)
            if s.env_detail == "DETAILED":
                box.operator("fresing.env_simple", icon="MOD_DECIM")
        gap(layout)
        big(layout, "fresing.turntable", "Make turntable video", "FILE_MOVIE", BIG)
        if a is not None:
            job = next((j for j in reversed(s.queue) if j.animation == a.name), None)
            if job is not None:
                state = {"WAITING": "waiting in the queue", "RUNNING": f"rendering, {job.progress:.0f}%",
                         "DONE": "done", "FAILED": "failed", "STOPPED": "stopped"}.get(job.status, job.status)
                wrap(layout, context, f"Last turntable: {state} (7 Render queue).",
                     icon="CHECKMARK" if job.status == "DONE" else "TIME", alert=job.status == "FAILED")
            wrap(layout, context, f"Size, shape and file: 6 Animation, '{a.name}'; then Make turntable "
                                  "video again.")


CLASSES = (
    FRESING_UL_tree, FRESING_UL_groups, FRESING_UL_rules, FRESING_UL_schemes, FRESING_UL_visibility,
    FRESING_UL_found,
    FRESING_PT_import, FRESING_PT_structure, FRESING_PT_cleanup, FRESING_PT_visibility, FRESING_PT_looks,
    FRESING_PT_faces, FRESING_PT_find, FRESING_PT_rules, FRESING_PT_schemes, FRESING_PT_scene, FRESING_PT_camera,
    FRESING_PT_props, FRESING_PT_output, FRESING_PT_turntable,
)
