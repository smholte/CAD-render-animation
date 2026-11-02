"""Side panel in the 3D viewport: 1 Import, 2 Structure, 3 Looks, 4 Scene & Render."""

from __future__ import annotations

import json

import bpy

from ..core import fasteners, materials_lib, presets
from . import build, cameras, materials

CATEGORY = "Fresing"


class _Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY


def _has_model(context) -> bool:
    return bool(build.model_roots(context.scene))


# =============================================================================
# 1 Import
# =============================================================================


class FRESING_PT_import(_Panel, bpy.types.Panel):
    bl_label = "1  Import"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        col = layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("fresing.import_step", text="Import STEP…", icon="IMPORT")
        col.label(text="Or drag a .step file onto the viewport", icon="INFO")
        row = layout.row(align=True)
        row.prop(s, "import_quality", expand=True)
        layout.prop(s, "import_up_axis")
        for root in build.model_roots(context.scene):
            box = layout.box()
            box.label(text=root.name, icon="OUTLINER_OB_GROUP_INSTANCE")
            try:
                st = json.loads(root.get("fr_stats", "{}"))
            except ValueError:
                st = {}
            if st:
                box.label(text=f"{st.get('placed_parts', 0)} parts ({st.get('unique_parts', 0)} different), "
                               f"{st.get('triangles_unique', 0) / 1e6:.1f} M triangles")
                box.label(text=f"Read in {st.get('seconds_total', 0):.0f} s")
        if s.last_message:
            layout.label(text=s.last_message)


# =============================================================================
# 2 Structure
# =============================================================================


class FRESING_UL_tree(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        ob = item.obj
        if ob is None:
            layout.label(text="(deleted)")
            return
        row = layout.row(align=True)
        for _ in range(item.depth):
            row.separator(factor=1.2)
        row.label(text=ob.get(build.PROP_NAME, ob.name), icon="OUTLINER_COLLECTION" if item.depth == 0 else "MESH_CUBE")
        row.label(text=str(item.parts))
        locked = ob.get(build.PROP_LOCKED, True)
        op = row.operator("fresing.toggle_lock", text="", icon="LOCKED" if locked else "UNLOCKED", emboss=False)
        op.name = ob.name
        hidden = ob.get("fr_hidden", False)
        op = row.operator("fresing.toggle_hide", text="", icon="HIDE_ON" if hidden else "HIDE_OFF", emboss=False)
        op.name = ob.name
        op = row.operator("fresing.select_subassembly", text="", icon="RESTRICT_SELECT_OFF", emboss=False)
        op.name = ob.name

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [self.bitflag_filter_item] * len(items)
        if self.filter_name:
            needle = self.filter_name.lower()
            for i, it in enumerate(items):
                if it.obj is None or needle not in it.obj.name.lower():
                    flags[i] = 0
        return flags, []


class FRESING_PT_structure(_Panel, bpy.types.Panel):
    bl_label = "2  Structure"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        row = layout.row(align=True)
        row.label(text="Click selects:")
        row.prop(s, "pick_mode", expand=True)
        row = layout.row()
        row.template_list("FRESING_UL_tree", "", s, "tree", s, "tree_index", rows=8)
        col = row.column(align=True)
        col.operator("fresing.tree_refresh", text="", icon="FILE_REFRESH")
        layout.label(text="Unlock a subassembly to move it on its own", icon="INFO")
        row = layout.row(align=True)
        row.operator("fresing.hide_selected", icon="HIDE_ON")
        row.operator("fresing.show_all", icon="HIDE_OFF")


class FRESING_PT_cleanup(_Panel, bpy.types.Panel):
    bl_label = "Clean-up"
    bl_parent_id = "FRESING_PT_structure"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="Remove parts that never show (faster renders)")
        row = layout.row(align=True)
        row.prop(s, "small_part_mm", text="Smaller than (mm)")
        row.operator("fresing.select_small", text="Select", icon="RESTRICT_SELECT_OFF")
        row = layout.row(align=True)
        row.operator("fresing.exclude_selected", icon="TRASH")
        row.operator("fresing.restore_excluded", icon="LOOP_BACK")


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
        label = materials_lib.get(item.material)["label"]
        if materials_lib.needs_color(item.material) and item.color:
            label += f"  {item.color}"
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=label)
        sub.label(text=str(item.count))


class FRESING_UL_rules(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        from ..core.rules import FIELDS, OPS
        f = FIELDS.get(item.field, item.field)
        o = OPS.get(item.op, item.op)
        text = f"{f} {o}" if item.op in ("any", "none") else f"{f} {o} '{item.value}'"
        row.label(text=text)
        row.label(text=f"→ {item.target}")
        row.label(text=str(item.count))


class FRESING_UL_schemes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="COLOR")
        op = row.operator("fresing.scheme_apply", text="Use", icon="CHECKMARK")
        op.name = item.name


class FRESING_PT_looks(_Panel, bpy.types.Panel):
    bl_label = "3  Looks"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("fresing.apply_rules", icon="SORTALPHA")
        if s.unmatched:
            layout.label(text=f"{s.unmatched} parts unsorted (no rule matched)", icon="ERROR")
        layout.label(text="Material groups")
        row = layout.row()
        row.template_list("FRESING_UL_groups", "", s, "groups", s, "groups_index", rows=6)
        col = row.column(align=True)
        col.operator("fresing.group_add", text="", icon="ADD")
        col.operator("fresing.group_remove", text="", icon="REMOVE")
        if 0 <= s.groups_index < len(s.groups):
            g = s.groups[s.groups_index]
            box = layout.box()
            box.prop(g, "material")
            if materials_lib.needs_color(g.material):
                row = box.row(align=True)
                row.prop(g, "color")
                row.operator("fresing.pick_ral", text="", icon="VIEWZOOM")
            row = box.row(align=True)
            row.operator("fresing.group_select", icon="RESTRICT_SELECT_OFF")
            row.operator("fresing.group_assign", icon="CHECKMARK")
            box.operator("fresing.group_unassign", icon="LOOP_BACK")
        ob = context.active_object
        if ob is not None and ob.get(build.PROP_KIND) == "part":
            box = layout.box()
            box.label(text=ob.get(build.PROP_NAME, ob.name), icon="OBJECT_DATA")
            info = fasteners.parse(ob.get(build.PROP_NAME, ""))
            if info:
                box.label(text=fasteners.describe(info), icon="TOOL_SETTINGS")
            g = ob.get(build.PROP_GROUP, "")
            manual = " (manual)" if ob.get("fr_group_manual") else ""
            box.label(text=f"Group: {g}{manual}")
            if ob.get(build.PROP_COLOR):
                box.label(text=f"CAD colour: {ob[build.PROP_COLOR]}")


class FRESING_PT_rules(_Panel, bpy.types.Panel):
    bl_label = "Sorting rules"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        layout.label(text="Checked top to bottom; first match wins", icon="INFO")
        row = layout.row()
        row.template_list("FRESING_UL_rules", "", s, "rules", s, "rules_index", rows=6)
        col = row.column(align=True)
        col.operator("fresing.rule_add", text="", icon="ADD")
        col.operator("fresing.rule_remove", text="", icon="REMOVE")
        col.separator()
        col.operator("fresing.rule_move", text="", icon="TRIA_UP").direction = "UP"
        col.operator("fresing.rule_move", text="", icon="TRIA_DOWN").direction = "DOWN"
        if 0 <= s.rules_index < len(s.rules):
            r = s.rules[s.rules_index]
            box = layout.box()
            box.prop(r, "field")
            box.prop(r, "op")
            if r.op not in ("any", "none"):
                box.prop(r, "value")
            box.prop(r, "target")
            box.prop(r, "note")
        row = layout.row(align=True)
        row.operator("fresing.rule_add", text="Rule from active part", icon="EYEDROPPER").from_selection = True
        row.operator("fresing.rules_reset", text="Defaults", icon="LOOP_BACK")


class FRESING_PT_schemes(_Panel, bpy.types.Panel):
    bl_label = "Paint schemes & templates"
    bl_parent_id = "FRESING_PT_looks"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        row = layout.row()
        row.template_list("FRESING_UL_schemes", "", s, "schemes", s, "schemes_index", rows=3)
        col = row.column(align=True)
        col.operator("fresing.scheme_save", text="", icon="ADD")
        col.operator("fresing.scheme_remove", text="", icon="REMOVE")
        layout.label(text="Template = rules + groups + schemes + background")
        row = layout.row(align=True)
        row.operator("fresing.template_import", icon="FILE_FOLDER")
        row.operator("fresing.template_export", icon="FILE_TICK")


# =============================================================================
# 4 Scene & Render
# =============================================================================


class FRESING_PT_scene(_Panel, bpy.types.Panel):
    bl_label = "4  Scene & Render"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        scene = context.scene
        col = layout.column(align=True)
        col.label(text="Background")
        col.prop(s, "background", text="")
        if s.background == "COLOR":
            col.prop(s, "background_color", text="")
        elif s.background == "HDRI":
            row = col.row(align=True)
            row.prop(s, "hdri_path", text="")
            row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "BACKGROUND"
        if s.background in ("COLOR", "TRANSPARENT"):
            col.separator()
            col.label(text="Lighting")
            col.prop(s, "lighting", text="")
            if s.lighting == "HDRI":
                row = col.row(align=True)
                row.prop(s, "light_hdri_path", text="")
                row.operator("fresing.pick_hdri", text="", icon="ASSET_MANAGER").target = "LIGHT"
        col.separator()
        col.prop(s, "light_rotation")
        col.prop(s, "light_strength")
        if s.background == "SKY" or (s.background in ("COLOR", "TRANSPARENT") and s.lighting == "SKY"):
            col.prop(s, "sun_elevation")
        col.prop(s, "exposure")
        col.separator()
        col.prop(s, "floor")
        if s.floor == "VISIBLE":
            col.prop(s, "floor_use_own_color")
            if s.floor_use_own_color:
                col.prop(s, "floor_color", text="")
        if s.floor != "NONE":
            col.prop(s, "floor_offset")

        layout.separator()
        layout.label(text="Cameras")
        cams = cameras.fr_cameras(scene)
        box = layout.box()
        for cam in cams:
            row = box.row(align=True)
            active = scene.camera == cam
            op = row.operator("fresing.camera_activate", text=cam.name,
                              icon="RADIOBUT_ON" if active else "RADIOBUT_OFF", depress=active)
            op.name = cam.name
            op = row.operator("fresing.camera_remove", text="", icon="X")
            op.name = cam.name
        if not cams:
            box.label(text="No cameras yet")
        row = layout.row(align=True)
        row.operator_menu_enum("fresing.camera_add", "view", text="Add camera", icon="ADD")
        row.operator("fresing.camera_fit", text="Fit", icon="FULLSCREEN_ENTER")
        if scene.camera is not None and scene.camera.type == "CAMERA":
            row = layout.row(align=True)
            row.prop(scene.camera.data, "lens", text="Lens")
            row.operator("fresing.camera_dof", text="Blur", icon="CAMERA_DATA",
                         depress=scene.camera.data.dof.use_dof)
            if scene.camera.data.dof.use_dof:
                layout.prop(scene.camera.data.dof, "aperture_fstop", text="Blur f-stop (lower = more)")


class FRESING_PT_output(_Panel, bpy.types.Panel):
    bl_label = "Image size & render"
    bl_parent_id = "FRESING_PT_scene"

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        col = layout.column(align=True)
        col.prop(s, "out_format")
        kind = presets.FORMATS.get(s.out_format, {}).get("kind")
        if kind == "screen":
            col.prop(s, "out_resolution")
            col.prop(s, "out_orientation")
        elif kind == "paper":
            col.prop(s, "out_dpi")
            col.prop(s, "out_orientation")
            row = col.row(align=True)
            row.prop(s, "out_use_bleed")
            sub = row.row(align=True)
            sub.active = s.out_use_bleed
            sub.prop(s, "out_bleed_mm", text="mm")
        else:
            row = col.row(align=True)
            row.prop(s, "out_custom_w")
            row.prop(s, "out_custom_h")
        size = presets.compute(s.out_format, s.out_resolution, s.out_orientation, int(s.out_dpi),
                               s.out_bleed_mm if s.out_use_bleed else 0.0, s.out_custom_w, s.out_custom_h)
        layout.label(text=f"{size.width} × {size.height} px ({size.megapixels:.1f} MP)", icon="IMAGE_DATA")
        col = layout.column(align=True)
        col.prop(s, "quality")
        col.prop(s, "out_file_type")
        col.prop(s, "out_folder")
        col.prop(s, "use_gpu")
        row = layout.row(align=True)
        row.operator("fresing.preview", icon="SHADING_RENDERED")
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("fresing.render", icon="RENDER_STILL")
        layout.operator("fresing.open_folder", icon="FILE_FOLDER")


CLASSES = (
    FRESING_UL_tree, FRESING_UL_groups, FRESING_UL_rules, FRESING_UL_schemes,
    FRESING_PT_import, FRESING_PT_structure, FRESING_PT_cleanup, FRESING_PT_looks, FRESING_PT_rules,
    FRESING_PT_schemes, FRESING_PT_scene, FRESING_PT_output,
)
