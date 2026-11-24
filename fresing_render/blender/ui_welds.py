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
        row.prop(item, "name", text="", emboss=False)
        on = sum(1 for s in item.seams if s.enabled)
        row.label(text=plural(on, "seam"))
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
    if item.lost:
        wrap(box, context, item.note or "Weld lost its faces – pick again", icon="ERROR", inset=12, alert=True)
        row = box.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.weld_add", text="Pick again", icon="RESTRICT_SELECT_OFF").key = item.key
        row.operator("fresing.weld_remove", text="Remove", icon="X").key = item.key
        return
    body = fold(box, "fr_weld_seams", "Seams", "IPO_LINEAR", state=plural(len(item.seams), "seam"))
    if body is not None:
        _seam_rows(body, item.seams, key=item.key)
        col = split_props(body)
        col.prop(item, "gap")
        row = body.row(align=True)
        row.operator("fresing.weld_refind", text="Find seams again", icon="FILE_REFRESH").key = item.key
        row.operator("fresing.weld_add", text="Pick again", icon="RESTRICT_SELECT_OFF").key = item.key
    gap(box)
    col = split_props(box)
    col.prop(item, "kind")
    col.prop(item, "size")
    if item.kind != "FILLET" and any(s.kind == "BUTT" for s in item.seams) or item.kind == "BUTT":
        col.prop(item, "butt_width")
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
                                "Choose the size, the metal and the finish below"],
              key="fr_how_welds", used=bool(len(s.items)))
        gap(layout)
        big(layout, "fresing.weld_add", "Add weld…", "MOD_BEVEL")
        row = layout.row(align=True)
        row.operator("fresing.weld_parts", text="Weld two parts", icon="SNAP_FACE")
        if len(s.items):
            gap(layout)
            layout.template_list("FRESING_UL_welds", "", s, "items", s, "index", rows=3)
            it = welds.active(context.scene)
            if it is not None:
                draw_details(layout, context, it)
        else:
            hint(layout, context, "Weld two parts: select them first (click one, Shift-click the other)")


PANELS = (FRESING_PT_welds,)
CLASSES = (FRESING_UL_welds,)
