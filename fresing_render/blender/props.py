"""Settings stored in the .blend file (scene.fresing)."""

from __future__ import annotations

import math

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)

from ..core import materials_lib, presets
from ..core import rules as R
from ..core import surroundings as env

# Blender keeps only references to enum item strings: the list lives in a module global
BACKGROUND_ITEMS = env.enum_items()


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


# what each choice of a sorting rule means (shown in the drop-down lists of Sorting rules)
FIELD_HELP = {
    "name": "The part's name as in the CAD tree, for example 'BRACKET 40x40'",
    "path": "The names of every subassembly above the part, then the part's own name",
    "assembly": "The name of the subassembly the part sits in",
    "color": "The part's colour in the STEP file, as a hex code such as #F9A800",
    "is_standard": "'yes' for a bolt, nut, washer or pin the app recognised by its name (DIN/ISO number "
                   "or a word such as BOLT)",
    "family": "The kind of fastener: screw, nut, washer, pin or other",
    "kind": "The fastener type as a code: hex_bolt, socket_cap, hex_nut, washer…",
    "finish": "The fastener finish read from its name: galvanized, stainless, black, zinc…",
    "standard": "The DIN or ISO number of a fastener, for example ISO 4017",
    "size": "The thread size of a fastener, for example M12",
    "property_class": "The strength class of a fastener, for example 8.8 or 12.9",
    "part_type": "The part type the part-type library found in the name: profile, bearing, hose…",
    "cad_material": "The material or appearance name in the STEP file (Fusion writes it)",
}
OP_HELP = {
    "contains": "The text appears anywhere in it",
    "equals": "It is exactly this text (capitals do not matter)",
    "starts": "It starts with this text",
    "ends": "It ends with this text",
    "glob": "It fits a pattern: * is any text, ? is one character, for example M6*20",
    "regex": "It fits a regular expression (for experts)",
    "any": "It has any value at all, for example every part with a CAD colour",
    "none": "It is empty, for example every part without a CAD colour",
}
FIELD_ITEMS = [(k, v, FIELD_HELP.get(k, "")) for k, v in R.FIELDS.items()]
OP_ITEMS = [(k, v, OP_HELP.get(k, "")) for k, v in R.OPS.items()]
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
        from . import faces
        faces.rename_group(old, self.name)
    self["_old_name"] = self.name


def _world_changed(self, context):
    if self.live_update:
        from . import world
        try:
            world.apply(context.scene, self)
        except Exception as exc:  # never break the UI over a preview update
            print("Fresing Render: background update failed:", exc)


def _props_shown(self, context):
    from . import surroundings
    surroundings.set_props_visible(context.scene, self.props_visible)


def _env_view_changed(self, context):
    from . import surroundings
    surroundings._show_in_view(context.scene, self)


def _output_changed(self, context):
    from . import render
    render.apply_output(context.scene, self)


# ---------------------------------------------------------------------------
# property groups
# ---------------------------------------------------------------------------

class FRMaterialGroup(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_group_renamed,
                         description="Name of the group. Rename it freely: the rules keep sorting parts into it")
    material: EnumProperty(name="Material", items=material_items, update=_group_look_changed,
                           description="Material of every part (and painted face) in this group. "
                                       "All of them change at once")
    color: StringProperty(name="Colour", update=_group_look_changed,
                          description="Colour of the group: a RAL code (e.g. RAL 5010) or a hex colour (#13447C). "
                                      "The magnifier next to it opens the RAL list")
    count: IntProperty(name="Parts", default=0)
    faces: IntProperty(name="Face sets", default=0,
                       description="Painted faces of parts in this group (faces with a look of their own)")
    # the rules put parts or faces in this group (False: only parts put in by hand). Its look then
    # belongs to the rule set; a group that only holds hand-picked parts belongs to the project
    by_rules: BoolProperty(default=False)


def _renamer(kind: str):
    """Update callback: when a pose / visibility set / scene / animation / scheme is renamed,
    everything that refers to it by name follows."""

    def update(self, context):
        old = self.get("_old_name", "")
        new = self.name
        self["_old_name"] = new
        if not old or old == new or context is None or context.scene is None:
            return
        s = context.scene.fresing
        if kind == "pose":
            for shot in s.shots:
                if shot.pose == old:
                    shot.pose = new
            for a in s.animations:
                for b in a.blocks:
                    if b.pose == old:
                        b.pose = new
        elif kind == "visibility":
            for shot in s.shots:
                if shot.visibility == old:
                    shot.visibility = new
        elif kind == "scheme":
            for shot in s.shots:
                if shot.scheme == old:
                    shot.scheme = new
        elif kind == "shot":
            for a in s.animations:
                if a.start_shot == old:
                    a.start_shot = new
            for j in s.queue:
                if j.shot == old:
                    j.shot = new
            if s.active_shot == old:
                s.active_shot = new
        elif kind == "animation":
            for j in s.queue:
                if j.animation == old:
                    j.animation = new
                    j.label = f"Animation: {new}"
            if s.anim_baked == old:
                s.anim_baked = new

    return update


class FRSchemeLook(bpy.types.PropertyGroup):
    group: StringProperty()
    material: StringProperty()
    color: StringProperty()


class FRScheme(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Scheme", update=_renamer("scheme"),
                         description="Name of the paint scheme, also used in saved scenes. Double-click to rename")
    looks: CollectionProperty(type=FRSchemeLook)


class FRRule(bpy.types.PropertyGroup):
    target: StringProperty(name="Group",
                           description="The group the parts go to. {color}, {finish}, {kind}, {part_type} or "
                                       "{cad_material} in the name make one group per value")
    field: EnumProperty(name="If", items=FIELD_ITEMS, default="name",
                        description="What the rule looks at: the part name, its CAD colour, the fastener finish, "
                                    "the part type, the CAD material…")
    op: EnumProperty(name="Test", items=OP_ITEMS, default="contains",
                     description="How it is compared with the value ('contains', 'is', 'starts with'…)")
    value: StringProperty(name="Value",
                          description="The text to look for (capitals do not matter). Not used by "
                                      "'has any value' and 'is empty'")
    enabled: BoolProperty(name="On", default=True,
                          description="Switch the rule on or off. A rule that is off is skipped when sorting")
    note: StringProperty(name="Note", description="Your own note about this rule (not used for sorting)")
    count: IntProperty(name="Matches", default=0)


class FRGroupAlias(bpy.types.PropertyGroup):
    source: StringProperty()     # name the rules produce
    target: StringProperty()     # name the user gave the group


class FRTreeItem(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)
    depth: IntProperty()
    parts: IntProperty()                 # parts below an assembly
    parent_index: IntProperty(default=-1)
    is_part: BoolProperty()
    same: IntProperty(default=1)         # identical parts side by side shown as one row ("x 24")
    has_kids: BoolProperty()
    expanded: BoolProperty()
    label: StringProperty()              # name, with ":2" for the second of identical subassemblies


class FRFoundPart(bpy.types.PropertyGroup):
    """One part name found by the Looks search (all placed parts with that name)."""
    part_name: StringProperty()
    count: IntProperty()
    groups: StringProperty()             # the group(s) these parts are in now
    use: BoolProperty(name="Tick", default=True,
                      description="Ticked part names go into the group when you press one of the buttons below")


def _tree_index_changed(self, context):
    from . import tree as tree_mod
    tree_mod.on_index_changed(context)


def _find_changed(self, context):
    from . import finder
    finder.run_search(context.scene)


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
    name: StringProperty(name="Name", default="Pose", update=_renamer("pose"))
    joints: CollectionProperty(type=FRPoseJoint)
    places: CollectionProperty(type=FRPlace)


class FRUid(bpy.types.PropertyGroup):
    uid: StringProperty()


class FRVisSet(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Visibility", update=_renamer("visibility"),
                         description="Name of the visibility set, also used in saved scenes. Double-click to "
                                     "rename")
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
    name: StringProperty(name="Name", default="Scene", update=_renamer("shot"))
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
    name: StringProperty(name="Name", default="Animation", update=_renamer("animation"))
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
    kind: EnumProperty(items=[("STILL", "Image", ""), ("ANIMATION", "Animation", ""), ("TEST", "Time test", "")],
                       default="STILL")
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


# ---------------------------------------------------------------------------
# milling (task 0027): the bit takes material away from the workpiece
# ---------------------------------------------------------------------------

def _mill_tool_changed(self, context):
    if self.get("_busy") or context is None or context.scene is None:
        return
    from . import machining
    machining.tool_changed(context.scene)


def _mill_detail_changed(self, context):
    from . import machining
    machining.mark_stale(context.scene)


def _mill_enabled_changed(self, context):
    from . import machining
    machining.enabled_changed(context.scene)


MILL_SHAPE_ITEMS = [
    ("AUTO", "From its shape", "Read from the part itself: flat, ball, corner radius, V-bit and drill are "
                               "recognised, any other shape is used as it is"),
    ("FLAT", "Flat end mill", "A flat bottom: square slots and pockets with flat floors"),
    ("BALL", "Ball end mill", "A round tip: rounded slots, 3D surfaces"),
    ("BULL", "Corner radius", "A flat bottom with rounded corners (bull nose)"),
    ("VEE", "V-bit / chamfer", "A pointed tip: V-grooves, chamfers, engraving"),
    ("DRILL", "Drill", "A drill point (118° by default)"),
]


class FRMillBit(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)
    uid: StringProperty()
    shape: EnumProperty(
        name="Shape", items=MILL_SHAPE_ITEMS, default="AUTO", update=_mill_tool_changed,
        description="The shape the bit cuts with. 'From its shape' reads it from the part; pick a type to "
                    "type in the sizes yourself (when the part is drawn simplified, or with its holder)")
    diameter: FloatProperty(name="Diameter", unit="LENGTH", default=0.01, min=1e-5, soft_max=0.1,
                            update=_mill_tool_changed,
                            description="Cutting diameter of the bit. Slots come out this wide")
    corner: FloatProperty(name="Corner radius", unit="LENGTH", default=0.001, min=0.0, soft_max=0.02,
                          update=_mill_tool_changed,
                          description="Radius of the rounded corners at the bit's bottom edge")
    angle: FloatProperty(name="Tip angle", subtype="ANGLE", default=math.radians(90), min=math.radians(10),
                         max=math.radians(175), update=_mill_tool_changed,
                         description="Included angle of the point: 90° for a common V-bit, 118° for a drill")
    length: FloatProperty(name="Length", unit="LENGTH", default=0.04, min=1e-4, soft_max=0.3,
                          update=_mill_tool_changed,
                          description="How much of the bit cuts, measured from its tip. Material higher up "
                                      "than this is not touched by the bit")
    flipped: BoolProperty(default=False)
    detected: StringProperty()           # what was recognised, e.g. "Flat end mill Ø10.0 mm, 40 mm long"
    auto: StringProperty()               # JSON: the recognised shape
    tip: FloatVectorProperty(size=3)     # in the bit's own space
    axis: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))


class FRMilling(bpy.types.PropertyGroup):
    bits: CollectionProperty(type=FRMillBit)
    bits_index: IntProperty(default=0)
    workpiece: PointerProperty(type=bpy.types.Object)
    workpiece_uid: StringProperty()
    finished: PointerProperty(type=bpy.types.Object)
    finished_uid: StringProperty()
    stock_mesh: PointerProperty(type=bpy.types.Mesh)      # the workpiece's CAD mesh, untouched
    cut_mesh: PointerProperty(type=bpy.types.Mesh)        # what the workpiece shows: milled
    detail: EnumProperty(
        name="Detail", default="NORMAL", update=_mill_detail_changed,
        description="How finely the bit's round shape and curved moves are followed. Fine looks best in "
                    "close-ups; Fast keeps long programs quick in the view",
        items=[("FINE", "Fine", "64 corners on the bit's circle, follows curves to 0.002 mm"),
               ("NORMAL", "Normal", "40 corners on the bit's circle, follows curves to 0.005 mm"),
               ("FAST", "Fast", "24 corners on the bit's circle, follows curves to 0.01 mm")])
    enabled: BoolProperty(
        name="Cut material", default=True, update=_mill_enabled_changed,
        description="Material disappears where the bits cut. Off: the workpiece shows as it came from CAD "
                    "(the set-up is kept)")
    path_sig: StringProperty()           # fingerprint of the motion the stored paths were read from


class FRSceneSettings(bpy.types.PropertyGroup):
    # ---- import ----
    import_quality: EnumProperty(
        name="Quality", default="normal",
        description="How finely round shapes are made into triangles. Choose it before pressing Import STEP",
        items=[("draft", "Draft", "Fast, coarse curves"),
               ("normal", "Normal", "Good for most renders"),
               ("fine", "Fine", "Smooth curves for close-ups (slower, more memory)")])
    import_up_axis: EnumProperty(
        name="Up axis", default="Z",
        description="Which axis points up in the CAD file. Choose it before pressing Import STEP",
        items=[("Z", "Z up", "Most STEP files"), ("Y", "Y up", "Inventor parts drawn with Y up")])

    # ---- structure ----
    tree: CollectionProperty(type=FRTreeItem)
    tree_index: IntProperty(default=0, update=_tree_index_changed)
    tree_depth: IntProperty(name="Levels", default=3, min=1, max=20,
                            description="How many levels of the assembly tree to show (older versions)")
    tree_search: StringProperty(name="Find in the tree", options={"TEXTEDIT_UPDATE"},
                                description="Shows every subassembly and part whose name contains this text")
    isolated: StringProperty(description="What 'Show only' is showing now ('' = everything)")
    pick_mode: EnumProperty(
        name="Click selects", default="SUBASSEMBLY",
        description="What a click on the model selects: its whole subassembly (like Inventor) or one part",
        items=[("SUBASSEMBLY", "Subassembly", "A click selects the whole subassembly"),
               ("PART", "Part", "A click selects one part")])
    small_part_mm: FloatProperty(name="Smaller than", default=6.0, min=0.1, soft_max=100.0, unit="NONE",
                                 description="Parts whose biggest side is smaller than this (in mm) are selected "
                                             "by 'Select the small parts'")

    # ---- looks ----
    groups: CollectionProperty(type=FRMaterialGroup)
    groups_index: IntProperty(default=0)
    find_text: StringProperty(name="Find parts", update=_find_changed,
                              description="Part names containing all these words (* = any text)")
    find_in_selected: BoolProperty(name="Only in the selected subassembly", default=False,
                                   update=_find_changed,
                                   description="Search only inside the subassembly selected in 2 Structure")
    found: CollectionProperty(type=FRFoundPart)
    found_index: IntProperty(default=0)
    group_aliases: CollectionProperty(type=FRGroupAlias)
    rules: CollectionProperty(type=FRRule)
    rules_index: IntProperty(default=0)
    schemes: CollectionProperty(type=FRScheme)
    schemes_index: IntProperty(default=0)
    unmatched: IntProperty(default=0)
    face_group: StringProperty(
        name="Paint with",
        description="The group whose look the faces you click get. Pick a group, then press "
                    "'Paint faces' and click faces on the model. Empty: the group selected in the list above")
    face_only_copy: BoolProperty(
        name="Only this copy", default=False,
        description="Ticked: painting, Other group and Whole part change only the copy of the part you "
                    "click; the other copies keep their look. Unticked: every copy gets the same faces")
    face_painting: BoolProperty(default=False,
                                description="'Paint faces' is running in the view")
    # rule set (task 0015): the name of the rule set this project uses ('' = a project made before
    # 0.2.13, adopted on open) and the rule set as it was last loaded or saved (JSON), which is the
    # project's own copy: the project opens without the library, and "changed" compares with it
    rule_set: StringProperty(name="Rule set", description="The rule set this project uses")
    rule_set_data: StringProperty()

    # ---- background & light (and the surroundings: task 0016) ----
    live_update: BoolProperty(name="Live update", default=True)
    background: EnumProperty(
        name="Background", default="COLOR", update=_world_changed, items=BACKGROUND_ITEMS,
        description="Where the machine stands: a studio background, a 360° photo, or one of the built-in "
                    "surroundings (sea, vessel deck, quay, factory halls, warehouse). Its settings appear below")
    background_color: FloatVectorProperty(name="Colour", subtype="COLOR", size=3, min=0, max=1,
                                          default=(1.0, 1.0, 1.0), update=_world_changed,
                                          description="The background colour. Click the swatch to pick another one")
    lighting: EnumProperty(
        name="Lighting", default="STUDIO", update=_world_changed,
        description="What lights the machine. The background you see stays as it is",
        items=[("STUDIO", "Studio", "Soft studio softboxes (built in): even light that shows shapes well"),
               ("HDRI", "360° photo", "Light from a 360° photo: real reflections of a real place. Pick the photo below"),
               ("SKY", "Sky", "Daylight with a sun and sharp shadows. Set the sun height below")])
    hdri_path: StringProperty(name="360° photo", subtype="FILE_PATH", update=_world_changed,
                              description="The 360° photo (.hdr or .exr). The library button picks one from the "
                                          "shared library; the folder button any file on your PC")
    light_hdri_path: StringProperty(name="Light from", subtype="FILE_PATH", update=_world_changed,
                                    description="The 360° photo that gives the light (it is not seen). The library "
                                                "button picks one from the shared library")
    light_rotation: FloatProperty(name="Rotate light", default=0.0, min=-360, max=360, update=_world_changed,
                                  description="Turns the light, the sun or the 360° photo around the machine "
                                              "(degrees). Drag it and watch the shadows in Live preview")
    light_strength: FloatProperty(name="Light strength", default=1.0, min=0.0, soft_max=5.0, update=_world_changed,
                                  description="How bright the light is. 1 is normal; use Exposure to brighten the "
                                              "whole picture")
    sun_elevation: FloatProperty(name="Sun height", default=45.0, min=0.0, max=90.0, update=_world_changed,
                                 description="Height of the sun above the horizon (degrees): low gives long "
                                             "shadows and warm light, 90 is straight overhead")
    exposure: FloatProperty(name="Exposure", default=0.0, soft_min=-3, soft_max=3, update=_world_changed,
                            description="Makes the whole picture brighter (+) or darker (-), like a camera's "
                                        "exposure. +1 is twice as bright")
    floor: EnumProperty(
        name="Floor", default="SHADOW", update=_world_changed,
        description="What is under the machine",
        items=[("NONE", "None", "The machine floats: no floor and no shadow under it"),
               ("SHADOW", "Shadow only", "An invisible floor that only shows the machine's shadow"),
               ("VISIBLE", "Visible floor", "A solid floor in the background colour (or its own colour)")])
    floor_offset: FloatProperty(name="Floor gap", default=0.0, unit="LENGTH", update=_world_changed,
                                description="Lowers the floor under the machine by this much (0 = the machine "
                                            "stands on it). Also moves the surroundings")
    floor_use_own_color: BoolProperty(name="Own floor colour", default=False, update=_world_changed,
                                      description="Give the visible floor its own colour instead of the "
                                                  "background colour")
    floor_color: FloatVectorProperty(name="Floor colour", subtype="COLOR", size=3, min=0, max=1,
                                     default=(0.6, 0.6, 0.6), update=_world_changed,
                                     description="Colour of the visible floor")
    env_detail: EnumProperty(
        name="Detail", default="SIMPLE", update=_world_changed,
        description="How much is built around the machine",
        items=[("SIMPLE", "Simple", "Fewer things around the machine: renders fastest"),
               ("DETAILED", "Detailed", "More things around the machine and real waves on the sea: more "
                                        "believable, renders a little slower")])
    sea_state: EnumProperty(
        name="Sea", default="CALM", update=_world_changed,
        description="How rough the sea is: calm for a quiet day in the harbour, rough for open sea in wind",
        items=[("CALM", "Calm", "A gentle swell and small ripples"),
               ("ROUGH", "Rough", "Higher waves, more ripples and white caps")])
    sea_foam: BoolProperty(name="Foam", default=True, update=_world_changed,
                           description="White foam on the wave tops. Most visible on a rough sea")
    sea_moving: BoolProperty(name="Moving waves", default=True, update=_world_changed,
                             description="The waves move in animations. Off: the sea stands still (the same "
                                         "in every frame)")
    water_level: FloatProperty(name="Water level", default=0.0, unit="LENGTH", soft_min=-20.0, soft_max=20.0,
                               update=_world_changed,
                               description="Height of the water from the machine's lowest point. 0: the machine "
                                           "stands on the water; raise it to put the machine partly under water")
    photo_ground: BoolProperty(name="Stand on the photo's ground", default=True, update=_world_changed,
                               description="The ground of the 360° photo lies flat under the machine and catches "
                                           "its shadow, so the machine stands in the photo. Off: the photo stays "
                                           "far away and the Floor setting is used")
    photo_height: FloatProperty(name="Photo taken at", default=1.7, min=0.1, soft_max=10.0, unit="LENGTH",
                                update=_world_changed,
                                description="How high above the ground the 360° photo was taken (most are taken "
                                            "at 1.5-2 m). Change it until the machine stands on the photo's floor "
                                            "at the right size")
    env_show_in_view: BoolProperty(name="Show in the view", default=True, update=_env_view_changed,
                                   description="Show the surroundings in the 3D view while you work. Renders "
                                               "always include them")
    props_visible: BoolProperty(name="Show props", default=True, update=_props_shown,
                                description="Show or hide all props for scale (person, container, pallet, "
                                            "barrier) in the view and in renders")

    # ---- output ----
    out_format: EnumProperty(name="Format", items=FORMAT_ITEMS, default="presentation", update=_output_changed,
                             description="What the picture is for: sets its shape (16:9, A4...). The size in "
                                         "pixels is shown under Quality")
    out_resolution: EnumProperty(name="Resolution", items=RES_ITEMS, default="hd", update=_output_changed,
                                 description="How many pixels the picture has. Bigger is sharper and takes longer")
    out_orientation: EnumProperty(
        name="Orientation", default="auto", update=_output_changed,
        description="Picture lying (landscape) or standing (portrait)",
        items=[("auto", "Default", "The usual way round for this format"), ("landscape", "Landscape", "Lying"),
               ("portrait", "Portrait", "Standing")])
    out_dpi: EnumProperty(name="DPI", items=[(str(d), f"{d} dpi", "") for d in presets.DPI_CHOICES],
                          default="300", update=_output_changed,
                          description="Print sharpness: 300 dpi for brochures and posters, 150 dpi is enough "
                                      "for large posters seen from a distance")
    out_use_bleed: BoolProperty(name="Bleed", default=False, update=_output_changed,
                                description="Adds a strip around print formats that the printer cuts off, so no "
                                            "white edge shows. Ask your printer whether they want it")
    out_bleed_mm: FloatProperty(name="Bleed (mm)", default=3.0, min=0.0, max=20.0, update=_output_changed,
                                description="Width of the bleed strip in mm (usually 3)")
    out_custom_w: IntProperty(name="Width", default=1920, min=16, max=16384, update=_output_changed,
                              description="Width of the picture in pixels")
    out_custom_h: IntProperty(name="Height", default=1080, min=16, max=16384, update=_output_changed,
                              description="Height of the picture in pixels")
    out_folder: StringProperty(name="Folder", subtype="DIR_PATH",
                               description="Where renders are saved. Empty: a folder 'Renders' next to the saved "
                                           "project")
    out_file_type: EnumProperty(name="File", default="PNG",
                                description="File type of the saved picture",
                                items=[("PNG", "PNG", "Best quality, keeps a transparent background"),
                                       ("JPEG", "JPEG", "Small files for e-mail and web; no transparency")])
    quality: EnumProperty(
        name="Quality", default="final",
        description="How clean the render is. Higher is cleaner and takes longer",
        items=[("draft", "Draft", "A quick check at half size"), ("preview", "Preview", "Full size, a bit grainy"),
               ("final", "Final", "Clean: for most pictures"), ("best", "Best", "Very clean for big prints; slow")])
    use_gpu: BoolProperty(name="Use graphics card", default=True,
                          description="Render on the graphics card (much faster). Off: on the processor")
    last_render: StringProperty(name="Last render", description="The image saved by the last Render image")

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

    # ---- milling (task 0027) ----
    milling: PointerProperty(type=FRMilling)

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


CLASSES = (FRMaterialGroup, FRSchemeLook, FRScheme, FRRule, FRGroupAlias, FRTreeItem, FRFoundPart,
           FRObjectRef, FRJoint, FRPoseJoint, FRPlace, FRPose, FRUid, FRVisSet, FRShot, FRAnimBlock, FRAnimation,
           FRQueueJob, FRReportLine, FRMillBit, FRMilling, FRSceneSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing = PointerProperty(type=FRSceneSettings)


def unregister():
    del bpy.types.Scene.fresing
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
