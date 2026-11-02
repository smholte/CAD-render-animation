"""Settings stored in the .blend file (scene.fresing)."""

from __future__ import annotations

import math

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
    for cat, mats in materials_lib.items_by_category():
        items.append(("", cat, ""))
        for key, label in mats:
            # the 4th value is what Blender stores in the file: a fixed number per material
            items.append((key, label, materials_lib.MATERIALS[key]["category"], materials_lib.UIDS[key]))
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


def _remember_rename(scene, old: str, new: str) -> None:
    """Rules keep producing the old name; remember that it now means the new one."""
    s = scene.fresing
    found = False
    for a in s.group_aliases:
        if a.target == old:
            a.target = new
            found = True
    if not found:
        a = s.group_aliases.add()
        a.source, a.target = old, new
    for i in reversed(range(len(s.group_aliases))):   # renamed back: no alias needed
        if s.group_aliases[i].source == s.group_aliases[i].target:
            s.group_aliases.remove(i)


def _group_renamed(self, context):
    from . import materials
    old = self.get("_old_name", "")
    if old and old != self.name:
        _remember_rename(context.scene, old, self.name)
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


class FRGroupAlias(bpy.types.PropertyGroup):
    source: StringProperty()     # name the rules produce
    target: StringProperty()     # name the user gave the group


class FRTreeItem(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)
    depth: IntProperty()
    parts: IntProperty()


# ---------------------------------------------------------------------------
# phase 2: joints, poses, visibility, scenes, animation, queue
# ---------------------------------------------------------------------------

_BUSY: set = set()


def _model_object_poll(self, ob):
    from . import build
    return ob.get(build.PROP_KIND) in build.MODEL_KINDS


def _camera_poll(self, ob):
    return ob.type == "CAMERA" and not ob.get("fr_anim_camera")


def _joint_renamed(self, context):
    from . import joints
    old = self.get("_old_name", "")
    if old and old != self.name:
        joints.rename(context.scene, self, old)
    self["_old_name"] = self.name


def _joint_limits_changed(self, context):
    from . import joints
    joints.apply_limits(self, joints._model_size(context.scene))


def _joint_base_changed(self, context):
    from . import joints
    key = ("base", self.as_pointer())
    if key in _BUSY or self.frame is None:
        return
    _BUSY.add(key)
    try:
        if self.base is not self.frame.parent:
            try:
                joints.set_base(context.scene, self, self.base)
            except RuntimeError as exc:
                context.scene.fresing.last_message = str(exc)
                self.base = self.frame.parent
    finally:
        _BUSY.discard(key)


class FRObjectRef(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)


class FRJoint(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_joint_renamed)
    kind: EnumProperty(name="Type", items=[("ROTATE", "Rotate", "Turns about the axis"),
                                           ("SLIDE", "Slide", "Moves along the axis")], default="ROTATE")
    frame: PointerProperty(type=bpy.types.Object)
    motion: PointerProperty(type=bpy.types.Object)
    base: PointerProperty(type=bpy.types.Object, name="Sits on", poll=_model_object_poll,
                          update=_joint_base_changed,
                          description="The subassembly this joint is mounted on; the joint moves along with it")
    members: CollectionProperty(type=FRObjectRef)
    use_limits: BoolProperty(name="Limits", default=False, update=_joint_limits_changed,
                             description="Keep the joint between a minimum and maximum")
    rot_min: FloatProperty(name="Min", subtype="ANGLE", default=-math.pi / 2, update=_joint_limits_changed)
    rot_max: FloatProperty(name="Max", subtype="ANGLE", default=math.pi / 2, update=_joint_limits_changed)
    slide_min: FloatProperty(name="Min", unit="LENGTH", default=0.0, update=_joint_limits_changed)
    slide_max: FloatProperty(name="Max", unit="LENGTH", default=1.0, update=_joint_limits_changed)


class FRPoseJoint(bpy.types.PropertyGroup):
    joint: StringProperty()
    value: FloatProperty()


class FRPlace(bpy.types.PropertyGroup):
    uid: StringProperty()
    matrix: FloatVectorProperty(size=16)


class FRPose(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Pose")
    joints: CollectionProperty(type=FRPoseJoint)
    places: CollectionProperty(type=FRPlace)


class FRUid(bpy.types.PropertyGroup):
    uid: StringProperty()


class FRVisSet(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Visibility")
    hidden: CollectionProperty(type=FRUid)


def _pose_choices(self, context):
    global _POSE_CHOICES
    _POSE_CHOICES = _choices(context.scene.fresing.poses if context else [], "Pose")
    return _POSE_CHOICES


def _vis_choices(self, context):
    global _VIS_CHOICES
    _VIS_CHOICES = _choices(context.scene.fresing.visibility_sets if context else [], "Visibility")
    return _VIS_CHOICES


def _scheme_choices(self, context):
    global _SCHEME_CHOICES
    _SCHEME_CHOICES = _choices(context.scene.fresing.schemes if context else [], "Paint scheme")
    return _SCHEME_CHOICES


_POSE_CHOICES: list = []
_VIS_CHOICES: list = []
_SCHEME_CHOICES: list = []


def _choices(coll, what: str) -> list:
    # Blender keeps only references to these strings: they live in module globals
    items = [("__current__", "As it is now", f"Save the current {what.lower()} with this scene"),
             ("__keep__", "Leave as it is", f"Switching to this scene does not change the {what.lower()}")]
    items += [(x.name, x.name, "") for x in coll]
    return items


class FRShot(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Scene")
    scheme: StringProperty()
    pose: StringProperty()
    visibility: StringProperty()
    camera: PointerProperty(type=bpy.types.Object, poll=_camera_poll)
    own_scheme: PointerProperty(type=FRScheme)
    own_pose: PointerProperty(type=FRPose)
    own_visibility: PointerProperty(type=FRVisSet)
    world: StringProperty()
    output: StringProperty()


EASE_ITEMS = [("SMOOTH", "Smooth", "Slow start and slow stop"), ("LINEAR", "Constant speed", ""),
              ("EASE_IN", "Slow start", ""), ("EASE_OUT", "Slow stop", "")]


class FRAnimBlock(bpy.types.PropertyGroup):
    name: StringProperty(name="Label", description="Shown in the list and as a marker on the timeline")
    enabled: BoolProperty(name="On", default=True)
    kind: EnumProperty(name="Type", default="JOINT", items=[
        ("JOINT", "Move joint", "Move one joint between two values", "CON_PIVOT", 0),
        ("POSE", "Go to pose", "Move every joint and subassembly to a saved pose", "ARMATURE_DATA", 1),
        ("CAMERA", "Camera", "Cut, move or orbit the camera", "VIEW_CAMERA", 2),
        ("SHOW", "Show", "A subassembly appears", "HIDE_OFF", 3),
        ("HIDE", "Hide", "A subassembly disappears", "HIDE_ON", 4)])
    start: FloatProperty(name="Start (s)", default=0.0, min=0.0, soft_max=120.0, step=10, precision=2)
    duration: FloatProperty(name="Duration (s)", default=2.0, min=0.0, soft_max=60.0, step=10, precision=2)
    easing: EnumProperty(name="Motion", items=EASE_ITEMS, default="SMOOTH")
    joint: StringProperty(name="Joint")
    pose: StringProperty(name="Pose")
    use_from: BoolProperty(name="From where it is", default=True,
                           description="Start from the position at the start of this block")
    from_angle: FloatProperty(name="From", subtype="ANGLE", default=0.0)
    to_angle: FloatProperty(name="To", subtype="ANGLE", default=math.radians(45))
    from_dist: FloatProperty(name="From", unit="LENGTH", default=0.0)
    to_dist: FloatProperty(name="To", unit="LENGTH", default=0.5)
    camera_mode: EnumProperty(name="Camera", default="MOVE", items=[
        ("CUT", "Cut to", "Switch to a saved camera"),
        ("MOVE", "Move to", "Fly smoothly to a saved camera"),
        ("ORBIT", "Orbit", "Turn around the model")])
    camera: PointerProperty(type=bpy.types.Object, name="Camera", poll=_camera_poll)
    orbit_angle: FloatProperty(name="Angle", subtype="ANGLE", default=math.radians(90))
    target_uid: StringProperty()
    target_name: StringProperty(name="Subassembly")


class FRAnimation(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Animation")
    fps: EnumProperty(name="Frame rate", default="25", items=[(v, f"{v} fps", "") for v in ("24", "25", "30", "50", "60")])
    start_shot: StringProperty(name="Start from scene",
                               description="Scene (colours, pose, visibility, camera, background) at the first frame")
    tail: FloatProperty(name="Hold at end (s)", default=1.0, min=0.0, soft_max=10.0)
    blocks: CollectionProperty(type=FRAnimBlock)
    blocks_index: IntProperty(default=0)
    out_resolution: EnumProperty(name="Video size", default="hd", items=[
        ("preview", "Small (960 × 540)", ""), ("hd", "HD (1920 × 1080)", ""), ("qhd", "QHD (2560 × 1440)", ""),
        ("4k", "4K (3840 × 2160)", "")])
    out_format: EnumProperty(name="Shape", default="presentation", items=[
        ("presentation", "16:9", ""), ("square", "1:1", ""), ("social", "9:16 (phone, upright)", "")])
    video: EnumProperty(name="Save as", default="MP4", items=[
        ("MP4", "MP4 video", "Video file (plus the single frames)"),
        ("PNG", "PNG frames only", "Numbered images, keeps transparency")])
    quality: EnumProperty(name="Quality", default="preview", items=[
        ("eevee", "Fast preview (EEVEE)", "Real-time engine: quick check of the motion"),
        ("draft", "Draft", "Cycles, low samples"), ("preview", "Preview", "Cycles"),
        ("final", "Final", "Cycles, clean"), ("best", "Best", "Cycles, very clean (slow)")])


class FRQueueJob(bpy.types.PropertyGroup):
    job_id: StringProperty()
    label: StringProperty(name="Job")
    kind: EnumProperty(items=[("STILL", "Image", ""), ("ANIMATION", "Animation", "")], default="STILL")
    shot: StringProperty()
    camera: StringProperty()
    animation: StringProperty()
    quality: StringProperty(default="final")
    status: EnumProperty(default="WAITING", items=[
        ("WAITING", "Waiting", "", "TIME", 0), ("RUNNING", "Rendering", "", "RENDER_ANIMATION", 1),
        ("DONE", "Done", "", "CHECKMARK", 2), ("FAILED", "Failed", "", "ERROR", 3),
        ("STOPPED", "Stopped", "", "CANCEL", 4)])
    progress: FloatProperty(default=0.0)
    message: StringProperty()
    output: StringProperty()


class FRReportLine(bpy.types.PropertyGroup):
    text: StringProperty()
    uid: StringProperty()


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
    tree_depth: IntProperty(name="Levels", default=3, min=1, max=20,
                            description="How many levels of the assembly tree to show")
    pick_mode: EnumProperty(
        name="Click selects", default="SUBASSEMBLY",
        items=[("SUBASSEMBLY", "Subassembly", "A click selects the whole subassembly"),
               ("PART", "Part", "A click selects one part")])
    small_part_mm: FloatProperty(name="Smaller than", default=6.0, min=0.1, soft_max=100.0, unit="NONE",
                                 description="Size in mm")

    # ---- looks ----
    groups: CollectionProperty(type=FRMaterialGroup)
    groups_index: IntProperty(default=0)
    group_aliases: CollectionProperty(type=FRGroupAlias)
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
    sun_elevation: FloatProperty(name="Sun height", default=45.0, min=0.0, max=90.0, update=_world_changed)
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

    # ---- motion ----
    joints: CollectionProperty(type=FRJoint)
    joints_index: IntProperty(default=0)
    show_joints: BoolProperty(name="Show joint axes", default=True, update=lambda self, ctx: _show_joints(ctx))
    poses: CollectionProperty(type=FRPose)
    poses_index: IntProperty(default=0)
    explode_factor: FloatProperty(name="Distance", default=0.5, min=0.0, soft_max=3.0,
                                  description="How far the pieces move apart (0.5 = half their distance from the centre)")
    explode_direction: EnumProperty(name="Direction", default="RADIAL", items=[
        ("RADIAL", "Outwards", ""), ("X", "Along X", ""), ("Y", "Along Y", ""), ("Z", "Up / down", "")])
    explode_level: EnumProperty(name="Pieces", default="CHILDREN", items=[
        ("CHILDREN", "Subassemblies", "Move the subassemblies inside it"),
        ("PARTS", "Every part", "Move every single part")])

    # ---- visibility sets & scenes ----
    visibility_sets: CollectionProperty(type=FRVisSet)
    visibility_index: IntProperty(default=0)
    shots: CollectionProperty(type=FRShot)
    shots_index: IntProperty(default=0)
    active_shot: StringProperty()

    # ---- animation ----
    animations: CollectionProperty(type=FRAnimation)
    animations_index: IntProperty(default=0)
    anim_baked: StringProperty()
    anim_restore_saved: BoolProperty(default=False)
    anim_restore_pose: PointerProperty(type=FRPose)
    anim_restore_visibility: PointerProperty(type=FRVisSet)
    anim_restore_camera: StringProperty()

    # ---- render queue ----
    queue: CollectionProperty(type=FRQueueJob)
    queue_index: IntProperty(default=0)
    queue_dir: StringProperty()
    queue_pid: IntProperty(default=0)

    # ---- model update report ----
    report_new: CollectionProperty(type=FRReportLine)
    report_missing: CollectionProperty(type=FRReportLine)
    report_notes: CollectionProperty(type=FRReportLine)
    report_title: StringProperty()

    last_message: StringProperty(default="")
    # cached so panels and sliders don't scan thousands of objects on every redraw
    model_count: IntProperty(default=0)
    bounds_valid: BoolProperty(default=False)
    bounds_min: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    bounds_max: FloatVectorProperty(size=3, default=(1.0, 1.0, 1.0))


def _show_joints(context):
    from . import joints
    show = context.scene.fresing.show_joints
    for j in context.scene.fresing.joints:
        if j.frame is not None:
            try:
                j.frame.hide_set(not show)
            except RuntimeError:
                pass


CLASSES = (FRMaterialGroup, FRSchemeLook, FRScheme, FRRule, FRGroupAlias, FRTreeItem,
           FRObjectRef, FRJoint, FRPoseJoint, FRPlace, FRPose, FRUid, FRVisSet, FRShot, FRAnimBlock, FRAnimation,
           FRQueueJob, FRReportLine, FRSceneSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing = PointerProperty(type=FRSceneSettings)


def unregister():
    del bpy.types.Scene.fresing
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
