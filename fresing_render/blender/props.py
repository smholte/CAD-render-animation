"""Settings stored in the .blend file (scene.fresing)."""

from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)

from ..core import materials_lib, presets
from ..core import rules as R


# ---------------------------------------------------------------------------
# enum item builders
# ---------------------------------------------------------------------------

def _material_items(self, context):
    items = []
    n = 0
    for cat, mats in materials_lib.items_by_category():
        items.append(("", cat, ""))
        for key, label in mats:
            items.append((key, label, materials_lib.MATERIALS[key]["category"], n))
            n += 1
    return items


_MATERIAL_ITEMS_CACHE = None


def material_items(self, context):
    global _MATERIAL_ITEMS_CACHE
    if _MATERIAL_ITEMS_CACHE is None:
        _MATERIAL_ITEMS_CACHE = _material_items(self, context)
    return _MATERIAL_ITEMS_CACHE


FIELD_ITEMS = [(k, v, "") for k, v in R.FIELDS.items()]
OP_ITEMS = [(k, v, "") for k, v in R.OPS.items()]
FORMAT_ITEMS = [(k, v["label"], "") for k, v in presets.FORMATS.items()]
RES_ITEMS = [(k, v["label"], "") for k, v in presets.RESOLUTIONS.items()]


# ---------------------------------------------------------------------------
# update callbacks
# ---------------------------------------------------------------------------

def _group_look_changed(self, context):
    from . import materials
    mat = materials.ensure_material(self.name, self.material, self.color)
    if self.material and materials_lib.needs_color(self.material) and not self.color:
        pass
    _ = mat


def _group_renamed(self, context):
    from . import materials
    old = self.get("_old_name", "")
    if old and old != self.name:
        mat = bpy.data.materials.get(materials.material_name(old))
        if mat is not None:
            mat.name = materials.material_name(self.name)
        for ob in context.scene.objects:
            if ob.get("fr_group") == old:
                ob["fr_group"] = self.name
            if ob.get("fr_group_manual") == old:
                ob["fr_group_manual"] = self.name
    self["_old_name"] = self.name


def _world_changed(self, context):
    if self.live_update:
        from . import world
        try:
            world.apply(context.scene, self)
        except Exception as exc:  # never break the UI over a preview update
            print("Fresing Render: background update failed:", exc)


def _output_changed(self, context):
    from . import render
    render.apply_output(context.scene, self)


# ---------------------------------------------------------------------------
# property groups
# ---------------------------------------------------------------------------

class FRMaterialGroup(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_group_renamed)
    material: EnumProperty(name="Material", items=material_items, update=_group_look_changed)
    color: StringProperty(name="Colour", description="RAL code (e.g. RAL 5010) or hex (#13447C)",
                          update=_group_look_changed)
    count: IntProperty(name="Parts", default=0)


class FRSchemeLook(bpy.types.PropertyGroup):
    group: StringProperty()
    material: StringProperty()
    color: StringProperty()


class FRScheme(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Scheme")
    looks: CollectionProperty(type=FRSchemeLook)


class FRRule(bpy.types.PropertyGroup):
    target: StringProperty(name="Group", description="Material group; may use {color}, {finish}, {kind}")
    field: EnumProperty(name="If", items=FIELD_ITEMS, default="name")
    op: EnumProperty(name="Test", items=OP_ITEMS, default="contains")
    value: StringProperty(name="Value")
    enabled: BoolProperty(name="On", default=True)
    note: StringProperty(name="Note")
    count: IntProperty(name="Matches", default=0)


class FRTreeItem(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)
    depth: IntProperty()
    parts: IntProperty()


class FRSceneSettings(bpy.types.PropertyGroup):
    # ---- import ----
    import_quality: EnumProperty(
        name="Quality", default="normal",
        items=[("draft", "Draft", "Fast, coarse curves"),
               ("normal", "Normal", "Good for most renders"),
               ("fine", "Fine", "Smooth curves for close-ups (slower, more memory)")])
    import_up_axis: EnumProperty(
        name="Up axis", default="Z",
        items=[("Z", "Z up", "Most STEP files"), ("Y", "Y up", "Inventor parts drawn with Y up")])

    # ---- structure ----
    tree: CollectionProperty(type=FRTreeItem)
    tree_index: IntProperty(default=0)
    pick_mode: EnumProperty(
        name="Click selects", default="SUBASSEMBLY",
        items=[("SUBASSEMBLY", "Subassembly", "A click selects the whole subassembly"),
               ("PART", "Part", "A click selects one part")])
    small_part_mm: FloatProperty(name="Smaller than", default=6.0, min=0.1, soft_max=100.0, unit="NONE",
                                 description="Size in mm")

    # ---- looks ----
    groups: CollectionProperty(type=FRMaterialGroup)
    groups_index: IntProperty(default=0)
    rules: CollectionProperty(type=FRRule)
    rules_index: IntProperty(default=0)
    schemes: CollectionProperty(type=FRScheme)
    schemes_index: IntProperty(default=0)
    unmatched: IntProperty(default=0)

    # ---- background & light ----
    live_update: BoolProperty(name="Live update", default=True)
    background: EnumProperty(
        name="Background", default="COLOR", update=_world_changed,
        items=[("COLOR", "Solid colour", "One flat colour behind the model"),
               ("HDRI", "360° photo", "An HDRI photo is both the background and the light"),
               ("SKY", "Sky", "Procedural sky with sun"),
               ("TRANSPARENT", "None (transparent)", "Transparent PNG for presentations")])
    background_color: FloatVectorProperty(name="Colour", subtype="COLOR", size=3, min=0, max=1,
                                          default=(1.0, 1.0, 1.0), update=_world_changed)
    lighting: EnumProperty(
        name="Lighting", default="STUDIO", update=_world_changed,
        items=[("STUDIO", "Studio", "Soft studio softboxes (built in)"),
               ("HDRI", "360° photo", "Light from an HDRI file"),
               ("SKY", "Sky", "Daylight with sun")])
    hdri_path: StringProperty(name="360° photo", subtype="FILE_PATH", update=_world_changed)
    light_hdri_path: StringProperty(name="Light from", subtype="FILE_PATH", update=_world_changed)
    light_rotation: FloatProperty(name="Rotate light", default=0.0, min=-360, max=360, update=_world_changed,
                                  description="Turn the light / 360° photo around the model (degrees)")
    light_strength: FloatProperty(name="Light strength", default=1.0, min=0.0, soft_max=5.0, update=_world_changed)
    sun_elevation: FloatProperty(name="Sun height", default=35.0, min=0.0, max=90.0, update=_world_changed)
    exposure: FloatProperty(name="Exposure", default=0.0, soft_min=-3, soft_max=3, update=_world_changed)
    floor: EnumProperty(
        name="Floor", default="SHADOW", update=_world_changed,
        items=[("NONE", "None", "Model floats"),
               ("SHADOW", "Shadow only", "Invisible floor that only catches shadows"),
               ("VISIBLE", "Visible floor", "Solid floor in the background colour")])
    floor_offset: FloatProperty(name="Floor gap", default=0.0, unit="LENGTH", update=_world_changed)
    floor_use_own_color: BoolProperty(name="Own floor colour", default=False, update=_world_changed)
    floor_color: FloatVectorProperty(name="Floor colour", subtype="COLOR", size=3, min=0, max=1,
                                     default=(0.6, 0.6, 0.6), update=_world_changed)

    # ---- output ----
    out_format: EnumProperty(name="Format", items=FORMAT_ITEMS, default="presentation", update=_output_changed)
    out_resolution: EnumProperty(name="Resolution", items=RES_ITEMS, default="hd", update=_output_changed)
    out_orientation: EnumProperty(
        name="Orientation", default="auto", update=_output_changed,
        items=[("auto", "Default", ""), ("landscape", "Landscape", ""), ("portrait", "Portrait", "")])
    out_dpi: EnumProperty(name="DPI", items=[(str(d), f"{d} dpi", "") for d in presets.DPI_CHOICES],
                          default="300", update=_output_changed)
    out_use_bleed: BoolProperty(name="Bleed", default=False, update=_output_changed,
                                description="Add bleed around print formats")
    out_bleed_mm: FloatProperty(name="Bleed (mm)", default=3.0, min=0.0, max=20.0, update=_output_changed)
    out_custom_w: IntProperty(name="Width", default=1920, min=16, max=16384, update=_output_changed)
    out_custom_h: IntProperty(name="Height", default=1080, min=16, max=16384, update=_output_changed)
    out_folder: StringProperty(name="Folder", subtype="DIR_PATH", description="Empty = 'Renders' next to the project")
    out_file_type: EnumProperty(name="File", default="PNG",
                                items=[("PNG", "PNG", "Lossless, supports transparency"), ("JPEG", "JPEG", "Small files")])
    quality: EnumProperty(
        name="Quality", default="final",
        items=[("draft", "Draft", "Fast check, half size"), ("preview", "Preview", "Full size, fewer samples"),
               ("final", "Final", "Clean result"), ("best", "Best", "Very clean, slow")])
    use_gpu: BoolProperty(name="Use graphics card", default=True)

    last_message: StringProperty(default="")


CLASSES = (FRMaterialGroup, FRSchemeLook, FRScheme, FRRule, FRTreeItem, FRSceneSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing = PointerProperty(type=FRSceneSettings)


def unregister():
    del bpy.types.Scene.fresing
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
