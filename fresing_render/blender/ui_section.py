"""Side panel: 3 Looks > Slice (task 0086). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import joints, section
from .ui import _Panel, big, fold, gap, header_status, hint, list_rows, split_props, steps


class FRESING_UL_cuts(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon="MESH_CUBE" if item.shape_kind == "BOX" else "MESH_PLANE")


class FRESING_PT_cutaway(_Panel, bpy.types.Panel):
    bl_label = "Slice"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="MOD_BOOLEAN")

    def draw_header_preset(self, context):
        header_status(self.layout, section.status(context.scene) or "none")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        steps(layout, context, ["Select a subassembly (or pick a group above), choose Plane or Box",
                                "Add the slice: the side facing you is taken away, the cut faces are red",
                                "Move its arrow, or set its place below; shows in rendered view and renders"],
              key="fr_how_cutaway", used=bool(s.cuts))
        gap(layout)
        layout.row().prop(s, "cut_new_shape", expand=True)
        big(layout, "fresing.cut_add", "Add slice: the selected", "MOD_BOOLEAN").what = "SELECTED"
        row = layout.row(align=True)
        row.operator("fresing.cut_add", text="This group", icon="MATERIAL").what = "GROUP"
        row.operator("fresing.cut_add", text="Whole model", icon="SCENE_DATA").what = "MODEL"
        if not s.cuts:
            return
        gap(layout)
        row = layout.row()
        row.template_list("FRESING_UL_cuts", "", s, "cuts", s, "cuts_index", rows=list_rows(len(s.cuts), 2, 5))
        col = row.column(align=True)
        col.operator("fresing.cut_remove", text="", icon="REMOVE")
        cut = section.active(scene)
        if cut is None:
            return
        box = layout.box()
        box.row().prop(cut, "shape_kind", expand=True)
        col = split_props(box)
        col.prop(cut, "flip", text="Flip")
        col.prop(cut, "color", text="Cap colour")
        col.prop(cut, "hatch", text="Hatch lines")
        if cut.hatch:
            col.prop(cut, "hatch_spacing", text="Line spacing")
        if cut.shape_kind == "BOX":
            col.prop(cut, "size", text="Box size")
        # what it cuts
        gap(box)
        n = section.cut_count(scene, cut)
        sub = box.column(align=True)
        sub.label(text=f"Cuts {plural(n, 'part')}:", icon="OBJECT_DATA")
        for i, t in enumerate(cut.targets):
            r = sub.row(align=True)
            r.label(text=section.target_label(t), icon="MATERIAL" if t.kind == "GROUP" else "OUTLINER_OB_EMPTY")
            r.operator("fresing.cut_target_remove", text="", icon="X").index = i
        r = box.row(align=True)
        r.operator("fresing.cut_target_add", text="Add selected", icon="ADD").what = "SELECTED"
        r.operator("fresing.cut_target_add", text="Add group", icon="ADD").what = "GROUP"
        # where it is
        gap(box)
        r = box.row(align=True)
        r.operator("fresing.cut_select_handle", text="Select the arrow", icon="RESTRICT_SELECT_OFF")
        r.operator("fresing.cut_replace", text="To the middle", icon="PIVOT_BOUNDBOX")
        j = section.joint_of(scene, cut)
        if j is not None:
            r = box.row(align=True)
            r.prop(j.motion, f'["{joints.VALUE}"]', text="Slide")
            hint(box, context, f"To move it in a video: a Move joint step with the joint '{j.name}' "
                               "(6 Animation)", inset=12)
        body = fold(box, "fresing_cut_place", "Place by numbers", "OBJECT_ORIGIN")
        if body is not None:
            col = split_props(body)
            col.prop(cut, "place", text="Position")
            col.prop(cut, "turn", text="Turn")
            if cut.shape_kind == "PLANE":
                col.prop(cut, "plane_size", text="Drawn size")
        gap(layout)
        hint(layout, context, "Slices show in rendered view (Z > Rendered), pictures and videos; the grey solid "
                              "view shows the parts whole", inset=12)


PANELS = (FRESING_PT_cutaway,)
CLASSES = (FRESING_UL_cuts,)
