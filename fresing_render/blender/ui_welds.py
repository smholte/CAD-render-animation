"""3 Looks > Welds (task 0319): add welds by picking faces (like Inventor) or two parts, shape and look them."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import welds
from .ui import MEDIUM, _Panel, big, fold, gap, header_status, hint, split_props, steps, wrap


class FRESING_UL_welds(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        row = layout.row(align=True)
        if item.lost:
            sub = row.row(align=True)
            sub.alert = True
            sub.label(text="", icon="ERROR")
        elif item.from_cad:                          # task 0323: from the CAD file
            row.label(text="", icon="IMPORT")
        row.prop(item, "name", text="", emboss=False)
        row.prop(item, "hidden", text="", icon="HIDE_ON" if item.hidden else "HIDE_OFF", emboss=False)


def _seam_rows(layout, coll, key: str = "", preview: bool = False) -> None:
    col = layout.column(align=True)
    for i, s in enumerate(coll):
        row = col.row(align=True)
        kind = "all round" if s.closed else ("butt" if s.kind == "BUTT" else "fillet")
        row.prop(s, "enabled", text=f"{i + 1}.  {s.length * 1000:.0f} mm  ·  {kind}  ·  {s.angle:.0f}°")
    row = layout.row(align=True)
    for on, text in ((True, "Tick all"), (False, "Untick all")):
        op = row.operator("fresing.weld_ticks", text=text)
        op.on, op.key, op.preview = on, key, preview


def draw_details(layout, context, item) -> None:
    box = layout.box()
    wrap(box, context, welds.describe(item), icon="MOD_BEVEL", inset=12)
    if item.from_cad:                                # task 0323: what came from the CAD file, and its shape switch
        from . import weld_cad
        wrap(box, context, weld_cad.describe(item), icon="IMPORT", inset=12)
    if item.lost:
        wrap(box, context, item.note or "Weld lost its faces – pick again", icon="ERROR", inset=12, alert=True)
        row = box.row(align=True)
        row.scale_y = MEDIUM
        if not item.from_cad:
            row.operator("fresing.weld_add", text="Pick again", icon="RESTRICT_SELECT_OFF").key = item.key
        row.operator("fresing.weld_remove", text="Remove", icon="X").key = item.key
        return
    if item.from_cad and item.cad_kind != "OTHER":
        row = box.row(align=True)
        row.operator("fresing.weld_cad_shape", icon="MOD_BEVEL" if item.cad_shape else "IMPORT",
                     text="Use the app's bead instead" if item.cad_shape else "Use the CAD shape again").key = item.key
    body = fold(box, "fr_weld_seams", "Seams", "IPO_LINEAR", state=plural(len(item.seams), "seam"))
    if body is not None:
        _seam_rows(body, item.seams, key=item.key)
        if not item.from_cad:
            col = split_props(body)
            col.prop(item, "gap")
            row = body.row(align=True)
            row.operator("fresing.weld_refind", text="Find seams again", icon="FILE_REFRESH").key = item.key
            row.operator("fresing.weld_add", text="Pick again", icon="RESTRICT_SELECT_OFF").key = item.key
    gap(box)
    col = split_props(box)
    sizes = col.column(align=True)
    # a CAD shape keeps its own size: the settings stay in their place, greyed (the app's bead uses them)
    sizes.active = not (item.from_cad and item.cad_shape)
    sizes.prop(item, "kind")
    sizes.prop(item, "size")
    if item.kind != "FILLET" and any(s.kind == "BUTT" for s in item.seams) or item.kind == "BUTT":
        sizes.prop(item, "butt_width")
    col.prop(item, "craters")
    col.prop(item, "intermittent")
    if item.intermittent:
        col.prop(item, "length")
        col.prop(item, "pitch")
    gap(box)
    r = welds.resolved(item)
    col = split_props(box)
    col.prop(item, "metal", text=f"Metal ({r['metal'].lower()})" if item.metal == "AUTO" else "Metal")
    col.prop(item, "process", text=f"Process ({r['process']})" if item.process == "AUTO" else "Process")
    col.prop(item, "finish")
    if item.finish == "PAINTED":
        col.prop(item, "paint_from")
    if r["metal"] == "STAINLESS":
        col.prop(item, "pickled")
    if item.finish != "PAINTED":
        col.prop(item, "heat_tint")
    if r["metal"] == "STEEL" and r["process"] in ("MAG", "STICK") and item.finish == "AS_WELDED":
        col.prop(item, "spatter")
    col.prop(item, "rust")
    if r["zinc"]:
        col.prop(item, "zinc_sprayed")
    gap(box)
    row = box.row(align=True)
    row.operator("fresing.weld_remove", text="Remove", icon="X").key = item.key
    # notes at the bottom of the box: they never push the settings above down
    warn = welds.warning(item)
    if warn:
        wrap(box, context, warn, icon="INFO", inset=12)
    if welds.moves_apart(item):
        wrap(box, context, "These parts are welded but move apart (a joint moves one of them)", icon="ERROR",
             inset=12, alert=True)
        box.operator("fresing.weld_move_as_one", text="Make them move as one", icon="LINKED").key = item.key


def draw_cad_all(layout, context, s) -> None:
    """Task 0323: the welds from the CAD file all at once – their shape, painted or bare, back to the CAD part."""
    n = sum(1 for it in s.items if it.from_cad)
    if not n:
        return
    body = fold(layout, "fr_weld_cad_all", "From the CAD file", "IMPORT", state=plural(n, "weld"))
    if body is None:
        return
    shape = sum(1 for it in s.items if it.from_cad and it.cad_shape)
    painted = sum(1 for it in s.items if it.from_cad and it.finish == "PAINTED")
    hint(body, context, f"{shape} with their CAD shape, {painted} painted. Cosmetic welds are not in a STEP file")
    row = body.row(align=True)
    row.operator("fresing.weld_cad_all", text="CAD shape").what = "CAD"
    row.operator("fresing.weld_cad_all", text="App's bead").what = "APP"
    row = body.row(align=True)
    row.operator("fresing.weld_cad_all", text="Painted").what = "PAINTED"
    row.operator("fresing.weld_cad_all", text="Bare").what = "BARE"
    body.operator("fresing.weld_cad_put_back", text="Back to the CAD part", icon="LOOP_BACK")


def draw_symbols(layout, s) -> None:
    """Task 0320: the weld symbols' switch (off by default), Show in renders under it, and the weld list."""
    row = layout.row(align=True)
    row.prop(s, "symbols", text="Weld symbols", icon="FONT_DATA")
    sub = row.row(align=True)
    sub.active = s.symbols
    sub.prop(s, "symbols_render", text="Show in renders", icon="RENDER_STILL")
    layout.operator("fresing.weld_list", text="Weld list…", icon="PRESET")


class FRESING_PT_welds(_Panel, bpy.types.Panel):
    bl_label = "Welds"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="MOD_BEVEL")

    def draw_header_preset(self, context):
        s = welds.settings(context.scene)
        if s.picking:
            header_status(self.layout, "pick faces…", alert=True)
        else:
            n = len(s.items)
            lost = sum(1 for it in s.items if it.lost)
            header_status(self.layout, (f"{lost} lost" if lost else plural(n, "weld")) if n else "none",
                          alert=bool(lost))

    def draw(self, context):
        layout = self.layout
        s = welds.settings(context.scene)
        if s.picking:
            from . import ops_welds
            pk = ops_welds.picker()
            box = layout.box()
            if s.picking == "A":
                text = ("1 of 2: click the faces of the first part (Shift-click: more faces). The bead moves with "
                        "this part")
                n = len(pk.faces_a) if pk else 0
                done = f"Next ({plural(n, 'face')})"
            else:
                text = "2 of 2: click the faces of the part it is welded to. The seams where they meet show in green"
                n = len(pk.seams) if pk else 0
                done = f"Done ({plural(n, 'seam')})"
            wrap(box, context, text + ". Esc or right-click: cancel", icon="RESTRICT_SELECT_OFF", alert=True)
            if s.picking == "B" and len(s.preview):
                _seam_rows(box, s.preview, preview=True)
            elif s.picking == "B" and pk is not None and pk.note:
                wrap(box, context, pk.note, icon="INFO", inset=12)
            row = layout.row(align=True)
            row.scale_y = MEDIUM
            row.operator("fresing.weld_next", text=done, icon="FORWARD" if s.picking == "A" else "CHECKMARK")
            row.operator("fresing.weld_cancel", text="Cancel", icon="X")
            return
        steps(layout, context, ["Press 'Add weld…' and click the faces of the first part (Shift-click: more)",
                                "Press Enter, then click the faces of the part it is welded to",
                                "Untick the seams you do not want and press Done – or select two parts and press "
                                "'Weld two parts'",
                                "Choose the size, the metal and the finish below",
                                "A STEP file with solid welds (Inventor, Creo) brings them along: they are in the "
                                "list after the import (Find in CAD file: look again)"],
              key="fr_how_welds", used=bool(len(s.items)))
        gap(layout)
        big(layout, "fresing.weld_add", "Add weld…", "MOD_BEVEL")
        row = layout.row(align=True)
        row.operator("fresing.weld_parts", text="Weld two parts", icon="LINKED")
        row.operator("fresing.weld_cad_find", text="Find in CAD file", icon="IMPORT")
        draw_cad_all(layout, context, s)             # task 0323: every weld from the CAD file at once
        if len(s.items):
            gap(layout)
            draw_symbols(layout, s)                      # task 0320: symbols switch, Show in renders, Weld list
            gap(layout)
            layout.template_list("FRESING_UL_welds", "", s, "items", s, "index", rows=3)
            it = welds.active(context.scene)
            if it is not None:
                draw_details(layout, context, it)
        else:
            hint(layout, context, "Weld two parts: select them first (click one, Shift-click the other)")


PANELS = (FRESING_PT_welds,)
CLASSES = (FRESING_UL_welds,)
