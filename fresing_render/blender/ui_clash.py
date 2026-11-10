"""Side panel: 6 Animation > Clash check (task 0065). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core import clash as core
from . import clash
from .ui import MEDIUM, _has_model, _Panel, fold, header_status, list_rows, primary, split_props, steps, wrap


class FRESING_UL_clashes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        near = item.kind == "NEAR"
        row.label(text=f"{item.label_a} × {item.label_b}", icon="INFO" if near else "ERROR")
        sub = row.row(align=True)
        sub.alignment = "RIGHT"
        frames = str(item.frame_from) if item.frame_to <= item.frame_from else f"{item.frame_from}–{item.frame_to}"
        sub.label(text=f"{frames} · {core.mm(item.depth)}")


class FRESING_PT_clash(_Panel, bpy.types.Panel):
    bl_label = "Clash check"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_PHYSICS")

    def draw_header_preset(self, context):
        rt = clash.runtime(context.scene)
        if rt.get("running"):
            header_status(self.layout, f"{rt.get('progress', 0.0) * 100:.0f}%")
            return
        st = clash.state(context.scene)
        if not st["built"] and not st["checked"] and not st["stale"]:
            return
        header_status(self.layout, st["text"], alert=bool(st["clashes"]), limit=34)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        c = clash.settings(scene)
        st = clash.state(scene)
        rt = clash.runtime(scene)
        if not st["built"] and not c.checked:
            steps(layout, context, ["Build the animation above (Build & play)",
                                    "Check for clashes: parts that run into each other are listed",
                                    "Click a row: the view goes there and shows both parts red"])

        # -- what counts
        col = split_props(layout)
        col.prop(c, "depth", text="Clash depth")
        layout.prop(c, "use_near", text="Warn about near misses")
        if c.use_near:
            col = split_props(layout)
            col.prop(c, "near_distance", text="Closer than")

        # -- the check
        if rt.get("running"):
            row = layout.row(align=True)
            row.scale_y = MEDIUM
            row.label(text=f"Checking … {rt.get('progress', 0.0) * 100:.0f}%", icon="SORTTIME")
            row.operator("fresing.clash_cancel", text="Cancel", icon="CANCEL")
            return
        primary(layout, "fresing.clash_check", "Check for clashes", "VIEWZOOM")

        # -- the result
        if st["stale"]:
            wrap(layout, context, "Not checked since the last Build: check again", icon="INFO")
            return
        if not st["checked"]:
            return
        what = f"'{c.anim}': "
        if st["clashes"]:
            what += f"{core.plural(st['clashes'], 'clash')}, click one to see it"
        elif st["near"]:
            what += f"no clashes, {core.plural(st['near'], 'near miss')}"
        else:
            what += "no clashes"
        wrap(layout, context, f"{what} (checked in {c.seconds:.1f} s)",
             icon="ERROR" if st["clashes"] else "CHECKMARK", alert=bool(st["clashes"]))
        if not c.rows:
            return
        layout.template_list("FRESING_UL_clashes", "", c, "rows", c, "rows_index",
                             rows=list_rows(len(c.rows), 3, 8))
        if len(c.rows) < st["clashes"] + st["near"]:
            layout.label(text=f"The first {len(c.rows)} are listed (deepest first)")
        if 0 <= c.rows_index < len(c.rows):
            r = c.rows[c.rows_index]
            box = layout.box()
            wrap(box, context, f"{r.label_a} × {r.label_b}", icon="INFO" if r.kind == "NEAR" else "ERROR")
            frames = (f"frame {r.frame_from}" if r.frame_to <= r.frame_from
                      else f"frames {r.frame_from}–{r.frame_to}")
            at = f"{r.deep:.0f}" if abs(r.deep - round(r.deep)) < 1e-6 else f"{r.deep:.2f}"
            if r.kind == "NEAR":
                wrap(box, context, f"Closer than {core.mm(c.near_distance)} in {frames}: {core.mm(r.depth)} apart "
                                   f"at frame {at}", inset=12)
            else:
                wrap(box, context, f"Into each other in {frames}, deepest {core.mm(r.depth)} at frame {at}",
                     inset=12)
            row = box.row(align=True)
            row.operator("fresing.clash_show", text="Show again", icon="ZOOM_SELECTED").index = c.rows_index
            row.operator("fresing.clash_red_off", text="No red", icon="HIDE_ON")
        body = fold(layout, "fresing_clash_more", "More")
        if body is not None:
            body.operator("fresing.clash_clear", text="Clear the result", icon="TRASH")


CLASSES = (FRESING_UL_clashes, FRESING_PT_clash)
