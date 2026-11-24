"""The Materials window's page and 3 Looks' short list (task 0273).

The window (``ops_material_picker.py``) is made like Fresing Settings: its page is ``FRESING_PT_materials_window`` in
the toolbar region of a copied 3D view (screen mark ``fr_materials``). Three columns: the filters, the pictures, the
picked material. The window's choices live on the window manager (``WindowManager.fresing_matpick``), never in a
project. Pictures are drawn with ``template_icon`` (an icon in a button stays 16 px in Blender 5.2.3, CLAUDE.md):
a picture with its name as the button under it.
"""

from __future__ import annotations

import time

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty

from ..core import material_files as F
from ..core import materials_lib as ML
from . import material_picker as MP
from . import ui
from .ops_setup import MATERIALS_MARK

ALL = "ALL"
_ITEMS: dict = {}                 # Blender keeps only references to enum item strings: the lists live here


def _source_items(self, context):
    lst = [(ALL, "Everywhere", "Built-in materials, this project's, and every Materials folder", "WORLD", 0)]
    scene = getattr(context, "scene", None) if context is not None else None
    found = F.sources(MP.all_entries(scene)) if scene is not None and hasattr(scene, "fresing") else \
        [("Built-in", "builtin")]
    icons = {"builtin": "PACKAGE", "project": "FILE_BLEND", "company": "COMMUNITY", "department": "USER",
             "mine": "HOME"}
    for i, (badge, src) in enumerate(found, start=1):
        lst.append((badge, badge, f"Only materials from: {badge}", icons.get(src, "FILE_FOLDER"), i))
    key = tuple(x[0] for x in lst)
    _ITEMS["source"] = _ITEMS.get(key) or lst
    _ITEMS[key] = _ITEMS["source"]
    return _ITEMS["source"]


def _kind_items(self, context):
    if "kind" not in _ITEMS:
        _ITEMS["kind"] = [(ALL, "Any material", "Every kind of material", 0)] + \
            [(k, k, f"Only {k.lower()}", i) for i, k in enumerate(ML.KINDS, start=1)]
    return _ITEMS["kind"]


def _colour_items(self, context):
    if "colour" not in _ITEMS:
        _ITEMS["colour"] = [(ALL, "Any colour", "Every colour", 0)] + \
            [(k, ML.COLOUR_LABELS[k], "Materials that take the group's own colour (paints, coloured plastics)"
              if k == "any" else f"Only {ML.COLOUR_LABELS[k].lower()} materials", i)
             for i, k in enumerate(ML.COLOURS, start=1)]
    return _ITEMS["colour"]


def _look_items(self, context):
    if "look" not in _ITEMS:
        _ITEMS["look"] = [(ALL, "Any look", "Every look", 0)] + \
            [(k, ML.LOOK_LABELS[k], f"Only materials that look {ML.LOOK_LABELS[k].lower()}", i)
             for i, k in enumerate(ML.LOOKS, start=1)]
    return _ITEMS["look"]


def _redraw(self, context):
    MP.redraw()


class FRMatPickState(bpy.types.PropertyGroup):
    """The Materials window's choices (task 0273): kept while the app runs, never saved with a project."""
    search: StringProperty(name="Search", options={"TEXTEDIT_UPDATE"}, update=_redraw,
                           description="Words in the material's name, description or tags, for example \"blue "
                                       "gloss\" or \"knurl\". Every word must be found")
    source: EnumProperty(name="Source", items=_source_items, update=_redraw,
                         description="Where the materials come from: built-in, this project, your company's or "
                                     "department's folders, your own (Fresing Settings > Locations > Materials)")
    kind: EnumProperty(name="Material", items=_kind_items, update=_redraw,
                       description="The kind of material: paint, steel, stainless, aluminium, plastic, rubber …")
    colour: EnumProperty(name="Colour", items=_colour_items, update=_redraw,
                         description="Its colour. 'Any colour (the group's)': paints and coloured plastics that take "
                                     "the colour you give the group")
    look: EnumProperty(name="Look", items=_look_items, update=_redraw,
                       description="How it looks: gloss, satin, matte, brushed, machined, textured, see-through …")
    size: FloatProperty(name="Picture size", default=4.0, min=2.5, max=8.0, step=50, precision=1, update=_redraw,
                        description="How large the pictures are drawn")
    picked: StringProperty(name="Picked", update=_redraw,
                           description="The material picked in the window (shown large on the right)")


def state(context=None):
    wm = (context or bpy.context).window_manager
    return getattr(wm, "fresing_matpick", None)


def visible(context) -> list:
    """The entries the filters let through, in their order."""
    st = state(context)
    entries = MP.all_entries(context.scene)
    if st is None:
        return entries
    return F.filter_entries(entries, st.search, "" if st.source == ALL else st.source,
                            "" if st.kind == ALL else st.kind, "" if st.colour == ALL else st.colour,
                            "" if st.look == ALL else st.look)


def picked_entry(context):
    st = state(context)
    if st is None or not st.picked:
        g = MP.current_group(context)
        return MP.find(context.scene, MP.group_key(g)) if g is not None else None
    return MP.find(context.scene, st.picked) or next((e for e in MP.all_entries(context.scene)
                                                      if e.key == st.picked), None)


def entry_icon(e, g) -> int:
    return MP.chip_icon(e, g.color if g is not None else "") if e.takes_colour else MP.icon(e)


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[:max(1, n - 1)].rstrip(" ,") + "…"


def tag_line(e) -> str:
    if e.is_blend:
        return "Made in Blender's shader editor: its own colour and look"
    looks = ", ".join(ML.LOOK_LABELS.get(x, x).lower() for x in e.looks)
    return f"{e.kind} · {ML.COLOUR_LABELS.get(e.colour, e.colour)} · {looks}"


# ---------------------------------------------------------------------------------------------------------------------
# the window

def _filters(col, context, st) -> None:
    col.label(text="Find", icon="VIEWZOOM")
    col.prop(st, "search", text="", icon="VIEWZOOM")
    ui.gap(col)
    col.label(text="Source")
    col.prop(st, "source", text="")
    col.label(text="Material")
    col.prop(st, "kind", text="")
    col.label(text="Colour")
    col.prop(st, "colour", text="")
    col.label(text="Look")
    col.prop(st, "look", text="")
    ui.gap(col)
    col.operator("fresing.mat_filters_clear", text="Show all", icon="X")
    col.operator("fresing.mat_refresh", text="Look in the folders again", icon="FILE_REFRESH")
    busy = MP.busy_pictures()
    if busy:
        r = col.row()
        r.active = False
        r.label(text=f"Making the picture of {busy[0]}…", icon="RENDER_STILL")


def columns_for(width_px: float, size: float, scale: float) -> int:
    """How many pictures fit side by side in a column ``width_px`` wide (a picture of ``size`` is ~20 px per unit)."""
    each = (size * 20.0 + 14.0) * (scale or 1.0)
    return max(1, int(max(width_px, 1) // each))


def _grid(col, context, st, g, width: float) -> None:
    entries = visible(context)
    head = col.row(align=True)
    head.label(text=f"{ui.plural(len(entries), 'material')}", icon="MATERIAL")
    head.prop(st, "size", text="Size", slider=True)
    if not entries:
        ui.hint(col, context, "Nothing fits these filters: press Show all on the left")
        return
    scale = context.preferences.system.ui_scale or 1.0
    n = columns_for(width, st.size, scale)
    chars = max(6, int(width / n / scale / 7.0) - 3)          # what fits beside the star at about 7 px a character
    grid = col.grid_flow(row_major=True, columns=n, even_columns=True, even_rows=False, align=False)
    listed = {pm.name for pm in context.scene.fresing.project_materials if pm.listed}
    for e in entries:
        cell = grid.column(align=True)
        cell.template_icon(icon_value=entry_icon(e, g), scale=st.size)
        row = cell.row(align=True)
        row.active = e.ok
        op = row.operator("fresing.mat_pick", text=_short(e.name, chars), depress=(e.key == st.picked))
        op.key = e.key
        star = row.operator("fresing.mat_star", text="", icon="SOLO_ON" if e.key in listed else "SOLO_OFF",
                            emboss=False)
        star.key = e.key


def _details(col, context, st, g) -> None:
    e = picked_entry(context)
    if e is None:
        ui.hint(col, context, "Click a material's name to see it here; click it twice to use it")
        return
    col.template_icon(icon_value=entry_icon(e, g), scale=9.0)
    ui.wrap(col, context, e.name, icon="MATERIAL")
    r = col.row()
    r.active = False
    r.label(text=e.badge, icon="PACKAGE" if e.source == "builtin" else "FILE_FOLDER")
    r = col.row()
    r.active = False
    r.label(text=tag_line(e))
    if e.description:
        ui.wrap(col, context, e.description)
    if e.author:
        ui.hint(col, context, f"Made by {e.author}")
    for p in e.problems:
        ui.wrap(col, context, p, icon="ERROR", alert=True)
    for n in e.notes:
        ui.hint(col, context, n)
    if e.images_outside:
        ui.wrap(col, context, f"Uses {ui.plural(len(e.images_outside), 'picture file')} outside its folder: on "
                              "another PC they are missing", icon="ERROR")
    ui.gap(col)
    if g is None:
        ui.hint(col, context, "Pick a group in 3 Looks to give it a material")
    else:
        box = col.box()
        box.label(text=f"Group: {g.name}", icon="MATERIAL")
        if e.takes_colour:
            row = box.row(align=True)
            row.prop(g, "color", text="Colour")
            row.operator("fresing.pick_ral", text="", icon="VIEWZOOM")
        if not e.is_blend:
            box.prop(g, "wear", text="Wear", slider=True)
        b = box.row()
        b.scale_y = 1.4
        b.enabled = e.ok
        op = b.operator("fresing.mat_use", text=f"Use for {_short(g.name, 22)}", icon="CHECKMARK")
        op.key = e.key
        if MP.group_key(g) == e.key:
            r = box.row()
            r.active = False
            r.label(text="The group has this material", icon="CHECKMARK")
    listed = MP.is_listed(context.scene, e.key)
    op = col.operator("fresing.mat_star", text="Take off this project's list" if listed else "Add to this project",
                      icon="SOLO_ON" if listed else "SOLO_OFF")
    op.key = e.key
    ui.gap(col)
    col.operator("fresing.mat_save", text="Save as my material…", icon="FILE_TICK")
    col.operator("fresing.mat_from_blender", text="From a Blender material…", icon="NODE_MATERIAL")
    if e.folder:
        row = col.row(align=True)
        op = row.operator("fresing.mat_picture", text="Make the picture again", icon="RENDER_STILL")
        op.key = e.key
        from . import locations
        row.enabled = e.ok and not MP.picture_busy(e.key) and locations._can_write(e.folder)   # (a read-only share: no)
        op = col.operator("fresing.mat_show", text="Show in folder", icon="FILE_FOLDER")
        op.key = e.key


def draw_window(layout, context) -> None:
    st = state(context)
    if st is None or context.scene is None or not hasattr(context.scene, "fresing"):
        layout.label(text="Open a project first", icon="INFO")
        return
    g = MP.current_group(context)
    head = layout.row(align=True)
    head.scale_y = 1.2
    head.label(text="Materials" + (f"  ·  for {g.name}" if g is not None else ""), icon="MATERIAL")
    right = head.row(align=True)
    right.alignment = "RIGHT"
    right.operator("fresing.materials_close", text="", icon="X", emboss=False)
    region = getattr(context, "region", None)
    width = getattr(region, "width", 900) or 900
    split = layout.split(factor=0.2)
    _filters(split.column(), context, st)
    rest = split.split(factor=0.7)
    _grid(rest.column(), context, st, g, width * 0.8 * 0.7 - 20)
    _details(rest.column(), context, st, g)


class FRESING_PT_materials_window(bpy.types.Panel):
    """The Materials window: filters, pictures, the picked material (task 0273)."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_label = "Materials"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        win = getattr(context, "window", None)
        try:
            return bool(win is not None and win.screen.get(MATERIALS_MARK))
        except (AttributeError, ReferenceError):
            return False

    def draw(self, context):
        t0 = time.perf_counter()
        draw_window(self.layout, context)
        DRAW_TIMES.append(time.perf_counter() - t0)
        del DRAW_TIMES[:-50]
        if not FIRST_DRAW:
            FIRST_DRAW.append(time.time())


DRAW_TIMES: list = []          # the last draws' times (s): the real-app test reads them
FIRST_DRAW: list = []          # when the window's page was first drawn (the test measures the open)


# ---------------------------------------------------------------------------------------------------------------------
# 3 Looks: this project's materials

def draw_short_list(box, context, g) -> None:
    """Above the group's Material row: the project's short list as small pictures (click = use for the group,
    × = off the list), the picked group's own material when it is not on the list (marked with a link), how many
    other materials the groups use, and More materials… (the window)."""
    scene = context.scene
    mine = MP.group_key(g)
    items = MP.short_list(scene)
    shown = [(e, listed) for e, listed, _used in items if listed or e.key == mine]
    others = sum(1 for e, listed, _used in items if not listed and e.key != mine)
    box.label(text="This project's materials", icon="SOLO_ON")
    if not any(listed for _e, listed in shown):
        ui.hint(box, context, "None yet: press the star of a material in More materials…", inset=12)
    region = getattr(context, "region", None)
    scale = context.preferences.system.ui_scale or 1.0
    n = max(2, min(6, int((getattr(region, "width", 300) or 300) / (scale * 74))))
    if shown:
        grid = box.grid_flow(row_major=True, columns=n, even_columns=True, even_rows=False, align=True)
        for e, listed in shown:
            cell = grid.column(align=True)
            cell.template_icon(icon_value=entry_icon(e, g), scale=2.6)
            row = cell.row(align=True)
            op = row.operator("fresing.mat_use", text=_short(e.name, 9), depress=(e.key == mine))
            op.key = e.key
            if listed:
                x = row.operator("fresing.mat_unlist", text="", icon="X", emboss=False)
                x.key = e.key
            else:
                row.label(text="", icon="LINKED")          # the group's own, not on the list
    if others:
        ui.hint(box, context, f"The other groups use {ui.plural(others, 'more material')}: a star in More materials… "
                              "puts one on this list", inset=12)
    box.operator("fresing.materials", text="More materials…", icon="MATERIAL")


CLASSES = (FRMatPickState, FRESING_PT_materials_window)


def register() -> None:
    bpy.types.WindowManager.fresing_matpick = bpy.props.PointerProperty(type=FRMatPickState)


def unregister() -> None:
    try:
        del bpy.types.WindowManager.fresing_matpick
    except AttributeError:
        pass
    MP.unregister()
