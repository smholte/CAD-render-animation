"""3 Looks > Logos & stickers (task 0024): put logos, text, type plates and stickers on the model."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import build, decals
from .ui import MEDIUM, _Panel, big, fold, gap, header_status, hint, split_props, steps, wrap


def _clicked_part(context):
    ob = context.active_object
    if ob is not None and ob.get(build.PROP_KIND) == "part" and ob.type == "MESH" and ob.data is not None:
        return ob
    return None


def draw_details(layout, context, item, part) -> None:
    """Settings of one decal, in the box under the list."""
    box = layout.box()
    scope = "every copy" if decals.on_all_copies(item) else "this copy only"
    wrap(box, context, f"{decals.describe(item)}  ·  {decals.size_text(item)}  ·  {scope}", icon="IMAGE_DATA",
         inset=12)
    if item.lost:
        wrap(box, context, "Its face changed in a model update: press 'Move with the mouse' and click its new spot",
             icon="ERROR", inset=12, alert=True)
    row = box.row(align=True)
    row.scale_y = MEDIUM
    row.operator("fresing.decal_move", text="Move with the mouse", icon="VIEW_PAN").key = item.key
    row = box.row(align=True)
    row.operator("fresing.decal_fit", text="Fit to face", icon="FULLSCREEN_ENTER").key = item.key
    row.operator("fresing.decal_upright", text="Upright", icon="EMPTY_SINGLE_ARROW").key = item.key
    gap(box)
    col = split_props(box)
    col.prop(item, "width")
    col.prop(item, "height")
    col.prop(item, "keep_ratio")
    col.separator()
    col.prop(item, "offset_x")
    col.prop(item, "offset_y")
    col.prop(item, "angle")
    col.prop(item, "mirror")
    col.separator()
    col.prop(item, "see_through")
    col.prop(item, "finish")
    gap(box)
    if item.kind == "PICTURE":
        col = split_props(box)
        row = col.row(align=True)
        row.prop(item, "source")
        row.operator_menu_enum("fresing.decal_library", "picture", text="", icon="ASSET_MANAGER").key = item.key
        box.prop(item, "clear_white")
    else:
        col = split_props(box)
        if item.kind == "TEXT":
            col.prop(item, "text")
            hint(box, context, "Type | where a new line should start", inset=12)
            col = split_props(box)
        else:
            col.prop(item, "sticker")
        if item.kind == "TEXT" or item.sticker == "TYPE_PLATE":
            row = col.row(align=True)
            row.prop(item, "font")
            row.operator_menu_enum("fresing.decal_font", "font", text="", icon="FILE_FONT").key = item.key
        if item.kind == "STICKER" and item.sticker == "TYPE_PLATE":
            col.prop(item, "plate_company")
            col.prop(item, "plate_type")
            col.prop(item, "plate_serial")
            col.prop(item, "plate_year")
            col.prop(item, "plate_weight")
            col.prop(item, "plate_ce")
        col = split_props(box)
        col.prop(item, "ink_color", text="Colour")
        split = box.split(factor=0.42, align=True)
        split.prop(item, "use_field")
        sub = split.row(align=True)
        sub.active = item.use_field
        sub.prop(item, "field_color", text="")
        split = box.split(factor=0.42, align=True)
        split.prop(item, "use_edge")
        sub = split.row(align=True)
        sub.active = item.use_edge
        sub.prop(item, "edge_color", text="")
    gap(box)
    row = box.row(align=True)
    if decals.on_all_copies(item):
        row.operator("fresing.decal_scope", text="Put it on this copy only", icon="OBJECT_DATA").key = item.key
    else:
        row.operator("fresing.decal_scope", text="Put it on every copy", icon="DUPLICATE").key = item.key


class FRESING_PT_decals(_Panel, bpy.types.Panel):
    bl_label = "Logos & stickers"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="IMAGE_DATA")

    def draw_header_preset(self, context):
        d = context.scene.fresing_decal
        if d.placing:
            header_status(self.layout, "click a spot…", alert=True)
        else:
            header_status(self.layout, plural(d.count, "decal") if d.count else "none")

    def draw(self, context):
        layout = self.layout
        d = context.scene.fresing_decal
        if d.placing:
            box = layout.box()
            wrap(box, context, "Click the spot on the model where the decal's centre goes. Esc or right-click: "
                               "cancel.", icon="IMAGE_DATA", alert=True)
            big(layout, "fresing.decal_add_cancel", "Cancel", "X")
        else:
            steps(layout, context, ["Choose what goes on: a picture (logo), text or a ready-made sticker",
                                    "Press 'Add decal…' and click the spot on the model",
                                    "Move, turn and size it in the box that opens below"],
                  key="fr_how_decals", used=bool(d.count))
            gap(layout)
            row = layout.row(align=True)
            row.prop(d, "kind", expand=True)
            col = split_props(layout)
            if d.kind == "PICTURE":
                row = col.row(align=True)
                row.prop(d, "picture")
                row.operator_menu_enum("fresing.decal_library", "picture", text="", icon="ASSET_MANAGER")
                if not d.picture:
                    hint(layout, context, "A PNG with a see-through background looks best. The button on the "
                                          "right lists the logos in the library")
            elif d.kind == "TEXT":
                col.prop(d, "text")
                hint(layout, context, "Type | where a new line should start. Font and colours: after placing it")
            else:
                col.prop(d, "sticker")
            layout.prop(d, "only_copy")
            gap(layout)
            big(layout, "fresing.decal_add", "Add decal…", "IMAGE_DATA")

        part = _clicked_part(context)
        if part is not None:
            gap(layout)
            items = decals.items_of(part)
            name = part.get(build.PROP_NAME, part.name)
            if not items:
                layout.label(text=f"{name}: no decals", icon="OBJECT_DATA")
            else:
                layout.label(text=f"Decals on {name}:", icon="OBJECT_DATA")
                active = next((it for it in items if it.key == d.active), items[0])
                col = layout.column(align=True)
                for it in items:
                    row = col.row(align=True)
                    op = row.operator("fresing.decal_select", text="", depress=it.key == active.key,
                                      icon="RADIOBUT_ON" if it.key == active.key else "RADIOBUT_OFF")
                    op.key = it.key
                    row.prop(it, "name", text="")
                    if it.lost:
                        sub = row.row(align=True)
                        sub.alert = True
                        sub.label(text="", icon="ERROR")
                    row.prop(it, "hidden", text="", icon="HIDE_ON" if it.hidden else "HIDE_OFF", emboss=False)
                    row.operator("fresing.decal_remove", text="", icon="X", emboss=False).key = it.key
                draw_details(layout, context, active, part)

        gap(layout)
        if d.count:
            body = fold(layout, "fr_decals_all", f"All decals in this project ({d.count})", "OUTLINER")
            if body is not None:
                col = body.column(align=True)
                rows = decals.all_decals()
                for owner, it in rows[:60]:
                    row = col.row(align=True)
                    who = owner.get(build.PROP_NAME, owner.name) if owner is not None else "?"
                    op = row.operator("fresing.decal_select", text=f"{who}  ·  {it.name}", icon="RESTRICT_SELECT_OFF",
                                      emboss=False)
                    op.key = it.key
                    op.part = owner.name if owner is not None else ""
                    if it.hidden:
                        row.label(text="", icon="HIDE_ON")
                if len(rows) > 60:
                    col.label(text=f"… and {len(rows) - 60} more")
        body = fold(layout, "fr_decals_library", "Library of logos and stickers", "ASSET_MANAGER")
        if body is not None:
            hint(body, context, "Put your logos and stickers as PNG files in these folders: they show in the "
                                "list next to Picture. Set the shared library folder in the Preferences.")
            col = body.column(align=True)
            for which in ("Logos", "Stickers"):                 # one folder per row: nothing cut off
                row = col.split(factor=0.36, align=True)
                row.label(text=which, icon="FILE_FOLDER")
                row.operator("fresing.decal_open_library", text="Show in folder").which = which


PANELS = (FRESING_PT_decals,)
