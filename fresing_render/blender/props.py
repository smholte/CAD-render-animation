"""Settings stored in the .blend file (scene.fresing)."""

from __future__ import annotations

import math

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)

from ..core import materials_lib, presets
from ..core import rules as R
from ..core import studio
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
    materials.ensure_material(self.name, self.material, self.color, self.wear)
    if context is not None and context.scene is not None:
        from . import machining                  # the milled workpiece's cut faces follow its look (task 0051)
        try:
            machining.cut_look_changed(context.scene)
        except Exception as exc:
            print("Fresing Render: cut faces' look not updated:", exc)


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


# ---- the active camera's lens and blur, shown in panel 5 (task 0017): read from and written to the
#      camera itself, so every camera keeps its own; nothing extra is stored in the scene

def _active_camera(self):
    cam = self.id_data.camera
    return cam if cam is not None and cam.type == "CAMERA" else None


def _lens_get(self):
    cam = _active_camera(self)
    return float(cam.data.lens) if cam is not None else 50.0


def _lens_set(self, value):
    cam = _active_camera(self)
    if cam is None:
        return
    cam.data.lens = value
    from . import cameras
    cameras.update_blur(cam, self.id_data)


_BLUR_NUMBER = {item[0]: item[3] for item in studio.BLUR_ITEMS}


def _blur_get(self):
    from . import cameras
    return _BLUR_NUMBER[cameras.blur_level(_active_camera(self))]


def _blur_set(self, value):
    cam = _active_camera(self)
    if cam is None:
        return
    from . import cameras
    level = next(k for k, n in _BLUR_NUMBER.items() if n == value)
    cameras.set_blur(cam, self.id_data, level)


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
    wear: FloatProperty(name="Wear", default=0.0, min=0.0, max=1.0, subtype="FACTOR", update=_group_look_changed,
                        description="How used the parts of this group look: 0 = new (clean, for marketing), "
                                    "1 = used. Sharp edges turn lighter or bare metal and corners get a little "
                                    "dirt. Shows in Cycles renders; Fast preview (EEVEE) shows only the dirt")
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
            for a in s.animations:                  # G-code steps play another animation at tool changes
                for b in a.blocks:
                    if b.gcode_atc == old:
                        b.gcode_atc = new

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
    new = self.name.strip()
    # animation steps, poses and couplings find a joint by its name: never empty, never twice
    taken = sum(1 for j in context.scene.fresing.joints if j.name == new) > 1
    if old and (not new or taken):
        self["name"] = old
        return
    if new != self.name:
        self["name"] = new
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


def _joint_follows_changed(self, context):
    """The leader picked in the joint details: check it, then build the coupling."""
    from . import joints
    key = ("follows", self.as_pointer())
    if key in _BUSY:
        return
    _BUSY.add(key)
    try:
        new = self.follows
        old = self.get("_old_follows", "")
        self["follows"] = old                        # set_follows decides; back to the old one if refused
        try:
            joints.set_follows(context.scene, self, new)
            self["_old_follows"] = new
            self["_follow_error"] = ""
        except RuntimeError as exc:
            self["_follow_error"] = str(exc)            # shown in red under the field
    finally:
        _BUSY.discard(key)


def _joint_coupling_changed(self, context):
    from . import joints
    joints.write_coupling(context.scene, self)


def _joint_motor_changed(self, context):
    from . import joints
    key = ("motor", self.as_pointer())
    if key in _BUSY:
        return
    _BUSY.add(key)
    try:
        if self.is_motor and self.kind != "ROTATE":
            self.is_motor = False
        joints.set_motor(context.scene, self, self.is_motor)
    finally:
        _BUSY.discard(key)


class FRJoint(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_joint_renamed,
                         description="Name of the joint, used in animation steps and couplings. Double-click to "
                                     "rename")
    kind: EnumProperty(name="Type", items=[("ROTATE", "Rotate", "Turns about the axis"),
                                           ("SLIDE", "Slide", "Moves along the axis")], default="ROTATE")
    frame: PointerProperty(type=bpy.types.Object)
    motion: PointerProperty(type=bpy.types.Object)
    base: PointerProperty(type=bpy.types.Object, name="Sits on", poll=_model_object_poll,
                          update=_joint_base_changed,
                          description="The subassembly this joint is mounted on; the joint moves along with it. "
                                      "Pick another one to make it move with that one")
    members: CollectionProperty(type=FRObjectRef)
    use_limits: BoolProperty(name="Limits", default=False, update=_joint_limits_changed,
                             description="Keeps the joint between a lowest and a highest value. Set them in the two "
                                         "fields next to it; Min and Max above jump there")
    rot_min: FloatProperty(name="Min", subtype="ANGLE", default=-math.pi / 2, update=_joint_limits_changed,
                           description="Lowest angle this joint can turn to, in degrees (CAD position = 0°)")
    rot_max: FloatProperty(name="Max", subtype="ANGLE", default=math.pi / 2, update=_joint_limits_changed,
                           description="Highest angle this joint can turn to, in degrees (CAD position = 0°)")
    slide_min: FloatProperty(name="Min", unit="LENGTH", default=0.0, update=_joint_limits_changed,
                             description="Shortest position this joint can slide to, in mm (CAD position = 0)")
    slide_max: FloatProperty(name="Max", unit="LENGTH", default=1.0, update=_joint_limits_changed,
                             description="Furthest position this joint can slide to, in mm (CAD position = 0)")
    # couplings and motors (task 0012); old projects: '' / 1 / 0 / off = moves by itself, as before
    follows: StringProperty(
        name="Follows", update=_joint_follows_changed,
        description="The joint this one follows: when that joint moves, this one moves with it at the ratio "
                    "below. Pick it from the list")
    couple_ratio: FloatProperty(
        name="Ratio", default=1.0, soft_min=-1000.0, soft_max=1000.0, precision=4, step=10,
        update=_joint_coupling_changed,
        description="How far this joint moves for each turn or mm of the joint it follows (the unit is its "
                    "label). Negative: the other way round, like two gears or two gripper jaws")
    couple_offset_angle: FloatProperty(
        name="Offset", subtype="ANGLE", default=0.0, update=_joint_coupling_changed,
        description="Angle this joint is at when the joint it follows is at 0, in degrees. Usually 0")
    couple_offset_dist: FloatProperty(
        name="Offset", unit="LENGTH", default=0.0, update=_joint_coupling_changed,
        description="Position this joint is at when the joint it follows is at 0, in mm. Usually 0")
    is_motor: BoolProperty(
        name="Motor (turns without end)", default=False, update=_joint_motor_changed,
        description="A motor has no limits and turns as far as you like; its angle is also shown in turns. "
                    "In 6 Animation, the step Run motor turns it at a set speed")


class FRPoseJoint(bpy.types.PropertyGroup):
    joint: StringProperty()
    value: FloatProperty()


class FRPlace(bpy.types.PropertyGroup):
    uid: StringProperty()
    matrix: FloatVectorProperty(size=16)


class FRPose(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Pose", update=_renamer("pose"),
                         description="Name of the pose, used in saved scenes and animations. Double-click to rename")
    joints: CollectionProperty(type=FRPoseJoint)
    places: CollectionProperty(type=FRPlace)


# ---- cylinders (task 0013) ----

def _cylinder_renamed(self, context):
    from . import cylinders
    old = self.get("_old_name", "")
    new = self.name.strip()
    # animation steps find a cylinder by its name: never empty, never twice
    taken = sum(1 for c in context.scene.fresing.cylinders if c.name == new) > 1
    if old and (not new or taken):
        self["name"] = old
        return
    if new != self.name:
        self["name"] = new
    if old and old != self.name:
        cylinders.rename(context.scene, self, old)
    self["_old_name"] = self.name


def _cylinder_lengths_changed(self, context):
    from . import cylinders
    msg = cylinders.sync_limits(context.scene, self)
    if msg:
        context.scene.fresing.last_message = msg


def _stroke_get(self):
    from . import cylinders
    try:
        return cylinders.stroke_now(self.id_data, self)
    except Exception:
        return 0.0


def _stroke_set(self, value):
    from . import cylinders
    try:
        cylinders.set_stroke(self.id_data, self, value)
    except RuntimeError as exc:
        self.id_data.fresing.last_message = str(exc)


class FRCylinder(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_cylinder_renamed,
                         description="Name of the cylinder, used in Move cylinder animation steps. Double-click to "
                                     "rename")
    mode: EnumProperty(name="Moves", default="FOLLOW", items=[
        ("FOLLOW", "Follows the arm", "The arm's joint moves it; the barrel turns and the rod slides along"),
        ("DRIVE", "Drives the arm", "You set the stroke; the arm's joint turns to match")])
    frame: PointerProperty(type=bpy.types.Object)
    pin: PointerProperty(type=bpy.types.Object)
    barrel_empty: PointerProperty(type=bpy.types.Object)
    rod_empty: PointerProperty(type=bpy.types.Object)
    barrel: CollectionProperty(type=FRObjectRef)
    rod: CollectionProperty(type=FRObjectRef)
    stages: CollectionProperty(type=FRObjectRef)
    stage_empties: CollectionProperty(type=FRObjectRef)
    closed_length: FloatProperty(
        name="Closed length", unit="LENGTH", default=0.5, min=0.0, update=_cylinder_lengths_changed,
        description="Distance between the two pin centres with the rod fully in, in mm (the catalogue's "
                    "installation length). From the model fills it in from the parts")
    full_stroke: FloatProperty(
        name="Full stroke", unit="LENGTH", default=0.2, min=0.0, update=_cylinder_lengths_changed,
        description="How far the rod can come out, in mm (the catalogue's stroke). From the model fills it in "
                    "from the parts")
    measured: BoolProperty(default=False)
    stroke: FloatProperty(
        name="Stroke", unit="LENGTH", get=_stroke_get, set=_stroke_set, soft_min=0.0,
        description="How far the rod is out, in mm (0 = fully in). Drag it or type a number: the arm moves to "
                    "match, within the cylinder's stroke")


# ---- mechanisms (task 0014) ----

def _mechanism_renamed(self, context):
    from . import linkages
    old = self.get("_old_name", "")
    new = self.name.strip()
    taken = sum(1 for m in context.scene.fresing.mechanisms if m.name == new) > 1
    if old and (not new or taken):
        self["name"] = old
        return
    if new != self.name:
        self["name"] = new
    if old and old != self.name:
        linkages.rename(context.scene, self, old)
    self["_old_name"] = self.name


def _height_get(self):
    from . import linkages
    try:
        return linkages.height_now(self.id_data, self)
    except Exception:
        return 0.0


def _height_set(self, value):
    from . import linkages
    try:
        reason = linkages.set_height(self.id_data, self, value)
        if reason:
            self.id_data.fresing.last_message = f"{self.name}: {reason}"
    except RuntimeError as exc:
        self.id_data.fresing.last_message = str(exc)


MECHANISM_KINDS = [
    ("SCISSOR", "Scissor lift", "Arms crossing in pairs (stages) between a base and a platform; rollers run on "
     "the base and under the platform. Driven by its bottom pin, its height or a cylinder"),
    ("FOURBAR", "Four-bar or parallel arm", "Three moving links and four pins: a crank and a rocker on the base, "
     "a coupler between them (also a parallel arm, a toggle clamp)"),
    ("SLIDER", "Slider-crank", "A crank on the base, a rod, and a slider or piston that slides along a guide"),
    ("OTHER", "Other linkage", "Any mechanism in one plane: links joined by pins (found from the holes), sliders "
     "found from their round faces"),
]


class FRMechLink(bpy.types.PropertyGroup):
    name: StringProperty()
    objs: CollectionProperty(type=FRObjectRef)
    empty: PointerProperty(type=bpy.types.Object)


class FRMechanism(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", update=_mechanism_renamed,
                         description="Name of the mechanism, used in Lift height animation steps. Double-click to "
                                     "rename")
    kind: EnumProperty(name="Type", items=MECHANISM_KINDS, default="OTHER")
    frame: PointerProperty(type=bpy.types.Object)
    base: PointerProperty(type=bpy.types.Object)
    links: CollectionProperty(type=FRMechLink)
    joint_motion: PointerProperty(type=bpy.types.Object)
    own_joint: BoolProperty(default=False)
    setup: StringProperty()
    signs: StringProperty()
    status: StringProperty()
    height: FloatProperty(
        name="Height", unit="LENGTH", get=_height_get, set=_height_set,
        description="Height of the platform's pin above the base's fixed pin, in mm. Drag it or type a number: "
                    "the arms move to match, within the drive joint's limits")


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
    name: StringProperty(name="Name", default="Scene", update=_renamer("shot"),
                         description="Name of the scene, used in the queue and as an animation's start. "
                                     "Double-click to rename")
    scheme: StringProperty()
    pose: StringProperty()
    visibility: StringProperty()
    camera: PointerProperty(type=bpy.types.Object, poll=_camera_poll,
                            description="The camera this scene renders from. Pick another one to change it")
    own_scheme: PointerProperty(type=FRScheme)
    own_pose: PointerProperty(type=FRPose)
    own_visibility: PointerProperty(type=FRVisSet)
    world: StringProperty()
    output: StringProperty()


EASE_ITEMS = [("SMOOTH", "Smooth", "Slow start and slow stop (a motor speeds up and slows down: Ramp)"),
              ("LINEAR", "Constant speed", "The same speed from start to end, no slowing down"),
              ("EASE_IN", "Slow start", "Starts slowly, stops at full speed"),
              ("EASE_OUT", "Slow stop", "Starts at full speed, slows down to a stop")]

BLOCK_KINDS = [
    ("JOINT", "Move joint", "Moves one joint from where it is (or a set value) to a value", "CON_PIVOT", 0),
    ("POSE", "Go to pose", "Moves every joint and moved subassembly to a saved pose (e.g. an exploded view)",
     "ARMATURE_DATA", 1),
    ("CAMERA", "Camera", "Cuts to a camera, flies to it, or turns around the model", "VIEW_CAMERA", 2),
    ("SHOW", "Show", "A subassembly appears", "HIDE_OFF", 3),
    ("HIDE", "Hide", "A subassembly disappears", "HIDE_ON", 4),
    ("MOTOR", "Run motor", "Turns a motor (or slides a joint) at a set speed for a while; joints that follow it "
     "move along", "FORCE_VORTEX", 5),
    ("CYLINDER", "Move cylinder", "Moves a cylinder's rod in or out (stroke from - to); the arm moves with it",
     "CON_STRETCHTO", 6),
    ("MECHANISM", "Lift height", "Raises or lowers a scissor lift's platform (height from - to); every arm "
     "follows", "SORT_DESC", 7),
    ("GCODE", "Run G-code program", "Moves the CNC machine's X, Y and Z joints (and its spindle) exactly as a "
     "CNC program would (set the machine up in 4 Motion > CNC machine)", "FILE_SCRIPT", 8),
]


def _gcode_step_changed(self, context):
    """A G-code step's file or speed changed: its length follows from the program."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode
    gcode.step_changed(context.scene, self)


def _cnc_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode
    gcode.setup_changed(context.scene)


def _air_changed(self, context):
    """An air-blast setting changed (task 0039): the chips are worked out again (and the motion read again for a
    nozzle of its own)."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import air
    air.settings_changed(context.scene)


AIR_SOURCE_ITEMS = [("SPINDLE", "Through the spindle", "The air comes out at the tool's tip and blows down along the "
                     "tool; it moves with the tool"),
                    ("NOZZLE", "External nozzle", "A nozzle part of the model (on the head or the frame) blows "
                     "where it points; it moves with the part it is fixed to")]


GCODE_SPEED_ITEMS = [("REAL", "Real time", "As long as the program takes on the machine"),
                     ("FASTER", "Faster", "A number of times faster than the machine"),
                     ("FIT", "Fit into", "The whole program fills a set number of seconds")]


class FRPictureCard(bpy.types.PropertyGroup):
    """A picture shown during an animation (task 0025)."""
    name: StringProperty(name="Name", description="Shown in the list: the picture's file name unless you type "
                                                  "something else")
    enabled: BoolProperty(name="On", default=True,
                          description="Switches this picture on or off in the video")
    path: StringProperty(name="Picture", subtype="FILE_PATH",
                         description="The photo or diagram to show (PNG, JPG, TIF, BMP or WebP). It must be there "
                                     "when the video is made")
    start: FloatProperty(name="Start (s)", default=0.0, min=0.0, soft_max=120.0, step=10, precision=2,
                         description="When the picture appears, in seconds from the start of the animation. To "
                                     "show it between two steps, leave a gap between those steps and start it there")
    duration: FloatProperty(name="Seconds", default=3.0, min=0.2, soft_max=30.0, step=10, precision=1,
                            description="How long the picture stays on screen, fades included")
    mode: EnumProperty(name="Shown", default="FULL",
                       description="Whole picture over the animation, or a small picture in one corner",
                       items=[("FULL", "Full screen", "The picture fills the video (the animation is hidden "
                                                      "behind it)"),
                              ("CORNER", "In a corner", "A small picture in one corner, the animation goes on")])
    corner: EnumProperty(name="Corner", default="BR", description="Which corner the small picture sits in",
                         items=[("TL", "Top left", ""), ("TR", "Top right", ""), ("BL", "Bottom left", ""),
                                ("BR", "Bottom right", "")])
    caption: StringProperty(name="Caption", description="A line of text under the picture (optional)")


class FRCallout(bpy.types.PropertyGroup):
    """A label with a line to a point on a part (task 0025)."""
    text: StringProperty(name="Text", default="Label",
                         description="The words in the label, e.g. Gripper or Max. 25 t")
    enabled: BoolProperty(name="On", default=True, description="Switches this label on or off in the renders")
    part: PointerProperty(type=bpy.types.Object, name="Part",
                          description="The part the line points at. The point moves with the part")
    local: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    step: StringProperty(name="Only during step", default="",
                         description="Show this label only while this animation step happens (it fades in and "
                                     "out). Empty: all the time. Stills always show every label that is on")


class FRAnimBlock(bpy.types.PropertyGroup):
    name: StringProperty(name="Label", description="Shown in the list and as a marker on the timeline. Empty: a "
                                                   "name made from the step")
    enabled: BoolProperty(name="On", default=True,
                          description="Switches this step on or off. A step that is off is left out of Build & play "
                                      "and the video")
    kind: EnumProperty(name="Type", default="JOINT", items=BLOCK_KINDS)
    start: FloatProperty(name="Start (s)", default=0.0, min=0.0, soft_max=120.0, step=10, precision=2,
                         description="When this step starts, in seconds from the beginning of the video")
    duration: FloatProperty(name="Duration (s)", default=2.0, min=0.0, soft_max=60.0, step=10, precision=2,
                            description="How long this step takes, in seconds")
    easing: EnumProperty(name="Motion", items=EASE_ITEMS, default="SMOOTH",
                         description="How the motion starts and stops: smooth (slow start and stop), constant "
                                     "speed, slow start or slow stop")
    joint: StringProperty(name="Joint", description="The joint this step moves (made in 4 Motion)")
    pose: StringProperty(name="Pose", description="The saved pose everything moves to (made in 4 Motion)")
    use_from: BoolProperty(name="From where it is", default=True,
                           description="Starts from where the joint is when this step begins. Off: from the value "
                                       "you set in From")
    from_angle: FloatProperty(name="From", subtype="ANGLE", default=0.0,
                              description="The angle the joint starts at, in degrees (0 = CAD position)")
    to_angle: FloatProperty(name="To", subtype="ANGLE", default=math.radians(45),
                            description="The angle the joint moves to, in degrees (0 = CAD position)")
    from_dist: FloatProperty(name="From", unit="LENGTH", default=0.0,
                             description="The position the joint starts at, in mm (0 = CAD position)")
    to_dist: FloatProperty(name="To", unit="LENGTH", default=0.5,
                           description="The position the joint moves to, in mm (0 = CAD position)")
    camera_mode: EnumProperty(name="Camera", default="MOVE", items=[
        ("CUT", "Cut to", "Switches to a saved camera at once"),
        ("MOVE", "Move to", "Flies smoothly to a saved camera"),
        ("ORBIT", "Orbit", "Turns around the model")],
        description="Cut to: switch to a camera at once. Move to: fly smoothly to a camera. Orbit: turn around "
                    "the model")
    camera: PointerProperty(type=bpy.types.Object, name="Camera", poll=_camera_poll,
                            description="The camera to cut or fly to (cameras are made in 5 Scene & Render)")
    orbit_angle: FloatProperty(name="Angle", subtype="ANGLE", default=math.radians(90),
                               description="How far the camera turns around the model, in degrees (360 = once "
                                           "round; negative: the other way)")
    target_uid: StringProperty()
    target_name: StringProperty(name="Subassembly")
    # Run motor (task 0012)
    speed_rpm: FloatProperty(name="Speed (rpm)", default=12.0, soft_min=-3000.0, soft_max=3000.0, precision=2,
                             step=100,
                             description="How fast the motor turns, in turns per minute (rpm). Negative: the other "
                                         "way round")
    speed_mms: FloatProperty(name="Speed (mm/s)", default=100.0, soft_min=-5000.0, soft_max=5000.0, precision=1,
                             step=100,
                             description="How fast the joint slides, in mm per second. Negative: the other way")
    # Move cylinder (task 0013)
    cylinder: StringProperty(name="Cylinder", description="The cylinder this step moves (made in 4 Motion > "
                                                          "Cylinders); the arm moves with it")
    from_stroke: FloatProperty(name="From", unit="LENGTH", default=0.0, min=0.0,
                               description="The stroke the rod starts at, in mm (0 = fully in)")
    to_stroke: FloatProperty(name="To", unit="LENGTH", default=0.1, min=0.0,
                             description="The stroke the rod moves to, in mm (0 = fully in)")
    # Lift height (task 0014)
    mechanism: StringProperty(name="Mechanism", description="The scissor lift this step raises or lowers (made in "
                                                            "4 Motion > Mechanisms)")
    from_height: FloatProperty(name="From", unit="LENGTH", default=0.5,
                               description="The platform's height the step starts at, in mm (pin to pin)")
    to_height: FloatProperty(name="To", unit="LENGTH", default=1.0,
                             description="The platform's height the step moves to, in mm (pin to pin)")
    ramp: FloatProperty(name="Ramp (s)", default=0.5, min=0.0, soft_max=10.0, step=10, precision=2,
                        description="How long the motor takes to get up to speed and to stop, in seconds (with "
                                    "Motion set to Smooth, Slow start or Slow stop)")
    # Run G-code program (task 0026)
    gcode_file: StringProperty(
        name="Program", subtype="FILE_PATH", update=_gcode_step_changed,
        description="The CNC program (.ngc, .nc, .tap, .gcode): the one your CAM writes for the machine. A copy is "
                    "kept in the project, so the render queue and other PCs have it too")
    gcode_from: IntProperty(
        name="From line", default=0, min=0, update=_gcode_step_changed,
        description="Plays the program from this line on (0 = from the start). The machine starts where the "
                    "program would be at that line")
    gcode_to: IntProperty(
        name="To line", default=0, min=0, update=_gcode_step_changed,
        description="Plays the program up to and including this line (0 = to the end)")
    gcode_speed: EnumProperty(
        name="Speed", items=GCODE_SPEED_ITEMS, default="REAL", update=_gcode_step_changed,
        description="Real time: as long as on the machine. Faster: a number of times faster. Fit into: the whole "
                    "program fills a set number of seconds")
    gcode_factor: FloatProperty(
        name="Times faster", default=10.0, min=0.01, soft_max=1000.0, update=_gcode_step_changed,
        description="How many times faster than the machine the program plays (10 = a 10-minute program takes "
                    "1 minute)")
    gcode_fit: FloatProperty(
        name="Seconds", default=30.0, min=0.1, soft_max=600.0, update=_gcode_step_changed,
        description="How long the whole program takes in the video, in seconds (tool changes included)")
    gcode_rapid: FloatProperty(
        name="Rapids faster", default=1.0, min=1.0, soft_max=20.0, update=_gcode_step_changed,
        description="Rapid moves (G0, the tool moving through the air) play this many times faster again, so the "
                    "video spends its time on the cutting. 1 = at the machine's own rapid speed")
    gcode_tc_time: FloatProperty(
        name="Tool change (s)", default=2.0, min=0.0, soft_max=30.0, update=_gcode_step_changed,
        description="How long each tool change (M6) takes in the video, in seconds, when no tool-changer "
                    "animation plays. The new tool shows half way")
    gcode_atc: StringProperty(
        name="Tool changer", update=_gcode_step_changed,
        description="An animation of the tool changer (arm, carousel, cover) that plays at every tool change "
                    "(M6); the program waits for it. Make it as an animation of its own with the tool changer's "
                    "joints. Empty: the tool just swaps")
    gcode_atc_swap: FloatProperty(
        name="Swap at (s)", default=1.0, min=0.0, soft_max=30.0, update=_gcode_step_changed,
        description="When in the tool-changer animation the new tool appears in the spindle, in seconds from its "
                    "start")
    gcode_spindle: EnumProperty(
        name="Spindle", default="SLOW", update=_gcode_step_changed,
        description="How fast the spindle turns in the video. A real 10,000 rpm spindle looks still or turning "
                    "backwards in a video (25 pictures per second), so by default it is slowed down",
        items=[("SLOW", "Looks right (slowed)", "Turns at most 1/7 turn per picture: clearly turning, in the "
                                                "right direction"),
               ("REAL", "Real speed", "The program's S rpm (fast spindles look still or turning backwards)")])
    gcode_path: BoolProperty(
        name="Show toolpath", default=True, update=_gcode_step_changed,
        description="Shows the program's path as a line on the workpiece: cutting moves solid, rapid moves dashed; "
                    "the part already cut changes colour as the program plays")
    gcode_clean: BoolProperty(
        name="Blow the part clean at the end", default=False, update=_gcode_step_changed,
        description="Makes the step longer by 'Time at end': the tool goes up and air blows the chips off the "
                    "workpiece, so the last frames show the clean part. Set the air up in 4 Motion > CNC machine > "
                    "Air blast; works with or without air codes in the program")
    gcode_clean_time: FloatProperty(
        name="Time at end", default=2.0, min=0.5, max=10.0, unit="TIME_ABSOLUTE", update=_gcode_step_changed,
        description="How many seconds the air blows the part clean at the end of the step (0.5 to 10 s). Through "
                    "the spindle the tool goes over the part in that time; then it stays still")
    gcode_path_render: BoolProperty(
        name="Toolpath in renders", default=False, update=_gcode_step_changed,
        description="Also shows the toolpath in pictures and videos (for presentations). Off: only in the view")


class FRAnimation(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Animation", update=_renamer("animation"),
                         description="Name of the animation, shown in the queue and the video's file name. "
                                     "Double-click to rename")
    fps: EnumProperty(name="Frame rate", default="25",
                      items=[(v, f"{v} fps", "") for v in ("24", "25", "30", "50", "60")],
                      description="Pictures per second: 25 is usual in Europe, 30 in the US. 50 or 60 moves more "
                                  "smoothly but has twice as many frames to render")
    start_shot: StringProperty(name="Start from scene",
                               description="The saved scene (colours, pose, visibility, camera, background) the video "
                                           "starts from. Empty: as the model is now")
    tail: FloatProperty(name="Hold at end (s)", default=1.0, min=0.0, soft_max=10.0,
                        description="How many seconds the last picture stays at the end of the video")
    blocks: CollectionProperty(type=FRAnimBlock)
    blocks_index: IntProperty(default=0)
    out_resolution: EnumProperty(
        name="Video size", default="hd",
        description="Size of the video in pixels: HD for screens and presentations, Small for quick checks, 4K "
                    "for big screens",
        items=[("preview", "Small (960 × 540)", "Quick checks; renders fastest"),
               ("hd", "HD (1920 × 1080)", "Screens and presentations"),
               ("qhd", "QHD (2560 × 1440)", "Sharper on big monitors"),
               ("4k", "4K (3840 × 2160)", "Big screens and trade fairs; four times the work of HD")])
    out_format: EnumProperty(
        name="Shape", default="presentation",
        description="Shape of the video: 16:9 for screens, 1:1 for posts, 9:16 upright for phones",
        items=[("presentation", "16:9", "Wide: screens, presentations, YouTube"),
               ("square", "1:1", "Square: social media posts"),
               ("social", "9:16 (phone, upright)", "Upright: phone stories and reels")])
    video: EnumProperty(name="Save as", default="MP4",
                        description="MP4: a video file (the single frames are kept too). PNG frames only: numbered "
                                    "pictures, transparency kept",
                        items=[("MP4", "MP4 video", "Video file (plus the single frames)"),
                               ("PNG", "PNG frames only", "Numbered images, keeps transparency")])
    quality: EnumProperty(name="Quality", default="preview",
                          description="Fast preview (EEVEE) checks the motion in minutes. Draft to Best: real light, "
                                      "cleaner but slower. Try Time test first",
                          items=[("eevee", "Fast preview (EEVEE)", "Real-time engine: quick check of the motion"),
                                 ("draft", "Draft", "Cycles, low samples"), ("preview", "Preview", "Cycles"),
                                 ("final", "Final", "Cycles, clean"), ("best", "Best", "Cycles, very clean (slow)")])

    # ---- finishing (task 0018): logo, title card, end card, captions, shape ----
    fin_logo: EnumProperty(
        name="Logo", default="NONE",
        description="Puts the brand kit's logo in one corner of the whole video. Needs a logo in the brand kit "
                    "(5 Scene & Render > Brand kit)",
        items=[("NONE", "No logo", "No logo in the picture"), ("TL", "Top left", "Logo in the top left corner"),
               ("TR", "Top right", "Logo in the top right corner"),
               ("BL", "Bottom left", "Logo in the bottom left corner"),
               ("BR", "Bottom right", "Logo in the bottom right corner")])
    fin_logo_size: FloatProperty(name="Logo size", default=0.12, min=0.03, max=0.4, precision=2, step=1,
                                 description="How wide the logo is, as a part of the picture width (0.12 = about "
                                             "an eighth)")
    fin_title_on: BoolProperty(name="Title card", default=False,
                               description="Puts a card with a title and a subtitle in front of the video, in the "
                                           "brand kit's colours")
    fin_title: StringProperty(name="Title", description="The big text on the title card, e.g. the machine's name")
    fin_subtitle: StringProperty(name="Subtitle", description="The smaller line under the title, e.g. the version or "
                                                              "the client")
    fin_title_seconds: FloatProperty(name="Title card (s)", default=3.0, min=0.5, soft_max=10.0, precision=1,
                                     description="How long the title card stays, in seconds")
    fin_end_on: BoolProperty(name="End card", default=False,
                             description="Puts a card with the logo and the contact line at the end of the video")
    fin_end_seconds: FloatProperty(name="End card (s)", default=3.0, min=0.5, soft_max=10.0, precision=1,
                                   description="How long the end card stays, in seconds")
    fin_captions: BoolProperty(name="Captions", default=False,
                               description="Shows the label of each animation step as a caption at the bottom, "
                                           "while that step happens. Only steps that have a label typed in get "
                                           "a caption")
    shape_fit: EnumProperty(
        name="Framing", default="EXTEND",
        description="What happens to the framing when the video is square (1:1) or upright (9:16): Extend keeps "
                    "everything you see from side to side, Crop keeps what you see from top to bottom",
        items=[("EXTEND", "Extend", "Keeps the width of the 16:9 picture and shows more above and below"),
               ("CROP", "Crop", "Keeps the height of the 16:9 picture and cuts the sides")])

    # ---- picture cards and music (task 0025) ----
    cards: CollectionProperty(type=FRPictureCard)
    cards_index: IntProperty(default=0)
    music_on: BoolProperty(name="Music", default=False,
                           description="Puts the music file under the whole video. Only for MP4 videos. Use music "
                                       "you have the rights to")
    music_file: StringProperty(name="Music file", subtype="FILE_PATH",
                               description="Your own music or sound (WAV, MP3, OGG, FLAC or M4A). You need the "
                                           "rights to use it in your videos")
    music_start: FloatProperty(name="Starts at (s)", default=0.0, min=0.0, soft_max=60.0, step=10, precision=1,
                               description="Where in the video the music begins, in seconds. 0: from the very first "
                                           "picture, title card included")
    music_volume: FloatProperty(name="Volume", default=0.8, min=0.0, max=1.0, precision=2, step=5,
                                description="How loud the music is: 1 is the file as it is")
    music_fade_in: FloatProperty(name="Fade in (s)", default=1.0, min=0.0, soft_max=10.0, precision=1, step=10,
                                 description="How long the music takes to rise to full volume")
    music_fade_out: FloatProperty(name="Fade out (s)", default=2.0, min=0.0, soft_max=10.0, precision=1, step=10,
                                  description="How long the music takes to fade away at the end of the video")


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
    watermark: BoolProperty(default=False)


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


def _mill_cut_look_changed(self, context):
    if context is None or context.scene is None:
        return
    from . import machining
    machining.cut_look_changed(context.scene)


def _chips_changed(self, context):
    if context is None or context.scene is None:
        return
    from . import chips
    chips.settings_changed(context.scene)


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
    # ---- the look of cut faces (task 0051) ----
    cut_look: EnumProperty(
        name="Cut faces", default="AUTO", update=_mill_cut_look_changed,
        description="What the faces the bit cuts look like. The block keeps its own look outside. Automatic "
                    "gives freshly cut metal or plastic made from the block's material in 3 Looks",
        items=[("AUTO", "Automatic (fresh cut)", "Bright machined metal (or matte plastic) of the block's material "
                                                 "in 3 Looks: raw steel and cast iron cut bright, aluminium "
                                                 "plate cut machined. Paint and other looks stay as the block", 0),
               ("SAME", "Same as the block", "Cut faces look like the rest of the block", 1),
               ("PICK", "Pick a material…", "Cut faces get the ready-made material picked below", 2)])
    cut_material: EnumProperty(
        name="Cut material", items=material_items, default=materials_lib.UIDS["aluminium_machined"],
        update=_mill_cut_look_changed,
        description="The ready-made material of the faces the bit cuts. A material that takes a colour uses the "
                    "colour of the block's group in 3 Looks")

    # ---- chips (task 0028) ----
    chips: EnumProperty(
        name="Chips", default="NONE", update=_chips_changed,
        description="Chips fly off the bit while it cuts, land on the workpiece, the table and the machine bed, "
                    "and pile up. Few is quick; Realistic makes as many as the removed material would. Both "
                    "make renders slower (see the user guide for measured times)",
        items=[("NONE", "None", "No chips"),
               ("FEW", "Few", "A sprinkle of chips (at most 3,000 at a time): quick to work out and to render"),
               ("REALISTIC", "Realistic", "As many chips as the removed material makes (at most 25,000 at a "
                                          "time, the oldest fade away): they pile up; slower to render")])
    chip_material: EnumProperty(
        name="Chip material", default="AUTO", update=_chips_changed,
        description="What the chips look like. 'From the workpiece' reads it from the workpiece's name, its "
                    "group name and its material in 3 Looks (aluminium, steel, POM …); pick one to override it",
        items=[("AUTO", "From the workpiece", "Read from the workpiece's name, group and material in 3 Looks")]
              + [(k, v, f"{v} chips") for k, v in (("ALU", "Aluminium"), ("STEEL", "Steel"),
                                                   ("STAINLESS", "Stainless steel"),
                                                   ("BRASS", "Brass / bronze / copper"), ("CAST_IRON", "Cast iron"),
                                                   ("PLASTIC", "Plastic (POM, PE, nylon, acrylic)"),
                                                   ("WOOD", "Wood / MDF"))])
    chip_spindle: EnumProperty(
        name="Spindle turns", default="CW", update=_chips_changed,
        description="Which way the spindle turns, seen from above: the chips are thrown off in that direction",
        items=[("CW", "Clockwise (M3)", "The usual direction for right-hand cutters"),
               ("CCW", "Counter-clockwise (M4)", "Left-hand cutters, tapping back out")])
    chip_mist: BoolProperty(
        name="Coolant mist", default=False, update=_chips_changed,
        description="A fine mist of coolant drops around the bit while it cuts. The drops fade after a moment")


def _cnc_tool_changed(self, context):
    """A size or the type of a tool list row changed (task 0040): its shape and its cut follow."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import tools
    tools.row_changed(context.scene, self)


def _cnc_tool_number_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode, tools
    gcode.setup_changed(context.scene)
    tools.row_changed(context.scene, self)


#: the tool types (task 0040). The first five keep their places: rows saved before 0.2.36 read them unchanged.
TOOL_KIND_ITEMS = [
    ("FLAT", "Flat end mill", "Square slots, pockets with flat floors, outlines"),
    ("BALL", "Ball end mill", "A round tip: rounded slots, 3D surfaces"),
    ("BULL", "Bull-nose end mill", "A flat bottom with rounded corners (corner radius)"),
    ("VEE", "Spot drill / chamfer mill", "A pointed tip: spot drilling, chamfers, V-grooves, engraving"),
    ("DRILL", "Drill", "A drill with its point (118° by default)"),
    ("FACE", "Face mill", "A wide cutter with inserts round its rim, for facing the top of the part"),
    ("THREAD", "Thread mill", "Mills threads on a helix; cuts the thread's outer diameter"),
    ("SLOT", "Slot / T-slot cutter", "A disc on a narrow neck: T-slots, grooves in a wall"),
]
HOLDER_ITEMS = [
    ("NONE", "None", "No holder is drawn: the spindle of your model holds the tool"),
    ("ER", "ER collet", "A collet nut (ER32 by default), as on router spindles"),
    ("SK40", "SK40", "A steep-taper holder to DIN 69871 (SK40): nose, flange with a groove, 7:24 taper, pull stud"),
    ("BT30", "BT30", "A steep-taper BT30 holder, as on smaller machining centres: nose, flange Ø46 with a groove, "
             "7:24 taper, pull stud"),
    ("BT40", "BT40", "A steep-taper BT40 holder: nose, flange with a groove, 7:24 taper, pull stud"),
    ("HSK63", "HSK63", "A hollow short taper holder HSK63: nose, flange with a groove, short taper"),
]


class FRCncTool(bpy.types.PropertyGroup):
    """A row of the tool list (task 0026, a full tool library since task 0040). ``length`` is the stick-out."""
    number: IntProperty(name="T", default=1, min=0, update=_cnc_tool_number_changed,
                        description="The tool number (T) the program uses for this tool")
    name: StringProperty(name="Name", update=_cnc_tool_changed,
                         description="A name for the tool, for example the manufacturer's order code. Empty: the "
                                     "type and size are shown")
    obj: PointerProperty(type=bpy.types.Object)
    uid: StringProperty()
    diameter: FloatProperty(name="Diameter", unit="LENGTH", default=0.006, min=1e-5, soft_max=0.2,
                            update=_cnc_tool_changed,
                            description="Cutting diameter: slots and holes come out this wide (a face mill: the "
                                        "diameter at its tip)")
    length: FloatProperty(name="Stick-out", unit="LENGTH", default=0.03, min=1e-4, soft_max=0.3,
                          update=_cnc_tool_changed,
                          description="How far the tool sticks out of its holder, from the tip to the holder's "
                                      "nose. With the holder's length it gives the tool's length for the tool "
                                      "length offset (G43)")
    gauge_length: FloatProperty(name="Gauge length", unit="LENGTH", default=0.0, min=0.0, soft_max=0.4,
                                update=_cnc_tool_changed,
                                description="From the tip up to the holder's gauge line (where it meets the spindle). "
                                            "A tool that is longer than the one in the spindle moves the spindle up "
                                            "by the difference, like G43. Type it in for a part or STEP model with "
                                            "its holder inside. 0: the stick-out plus the holder's length")
    kind: EnumProperty(name="Type", default="FLAT", update=_cnc_tool_changed, items=TOOL_KIND_ITEMS,
                       description="The type of tool: it sets the sizes below, the shape that cuts, the shape "
                                   "that is shown and the kind of chips")
    corner: FloatProperty(name="Corner radius", unit="LENGTH", default=0.001, min=0.0, soft_max=0.02,
                          update=_cnc_tool_changed,
                          description="Radius of the rounded corners at the bottom of a bull-nose end mill")
    angle: FloatProperty(name="Tip angle", subtype="ANGLE", default=math.radians(118), min=math.radians(10),
                         max=math.radians(175), update=_cnc_tool_changed,
                         description="Included angle of the point: 118° or 135° for a drill, 90° for a spot drill or "
                                     "chamfer mill")
    flute_length: FloatProperty(name="Flute length", unit="LENGTH", default=0.0, min=0.0, soft_max=0.2,
                                update=_cnc_tool_changed,
                                description="How far up from the tip the tool cuts. Material higher up than this is "
                                            "not removed. 0: what the type usually has (2.5 × the diameter)")
    flutes: IntProperty(name="Flutes", default=0, min=0, max=24, update=_cnc_tool_changed,
                        description="Number of flutes (cutting edges), for the shape that is shown. 0: what the "
                                    "type usually has")
    inserts: IntProperty(name="Inserts", default=0, min=0, max=40, update=_cnc_tool_changed,
                         description="Number of inserts round the face mill's rim, for the shape that is shown. 0: "
                                     "one per 10 mm of diameter")
    insert_size: FloatProperty(name="Insert size", unit="LENGTH", default=0.0, min=0.0, soft_max=0.03,
                               update=_cnc_tool_changed,
                               description="Edge length of a face mill's inserts: half of it is the deepest cut "
                                           "the face mill takes. 0: from the diameter")
    lead_angle: FloatProperty(name="Lead angle", subtype="ANGLE", default=math.radians(90), min=math.radians(10),
                              max=math.radians(90), update=_cnc_tool_changed,
                              description="Angle of the face mill's cutting edge to the surface it cuts: 90° for a "
                                          "square shoulder, 45° for a 45° face mill (the wall it leaves slopes)")
    pitch: FloatProperty(name="Pitch", unit="LENGTH", default=0.0, min=0.0, soft_max=0.006,
                         update=_cnc_tool_changed,
                         description="Thread pitch of a thread mill (the distance between its teeth). 0: from the "
                                     "diameter")
    width: FloatProperty(name="Cutting width", unit="LENGTH", default=0.0, min=0.0, soft_max=0.05,
                         update=_cnc_tool_changed,
                         description="Height of a slot cutter's disc: the slot comes out this wide. 0: a quarter "
                                     "of the diameter")
    neck: FloatProperty(name="Neck diameter", unit="LENGTH", default=0.0, min=0.0, soft_max=0.05,
                        update=_cnc_tool_changed,
                        description="Diameter of the slot cutter's neck above the disc (it must fit through the "
                                    "slot's opening). 0: from the diameter")
    shank: FloatProperty(name="Shank diameter", unit="LENGTH", default=0.0, min=0.0, soft_max=0.05,
                         update=_cnc_tool_changed,
                         description="Diameter of the shank above the flutes, for the shape that is shown. 0: as "
                                     "the cutting diameter")
    holder: EnumProperty(name="Holder", items=HOLDER_ITEMS, default="NONE", update=_cnc_tool_changed,
                         description="A simple holder drawn above the tool. None when the spindle of your model "
                                     "already has one")
    holder_diameter: FloatProperty(name="Holder nose Ø", unit="LENGTH", default=0.0, min=0.0, soft_max=0.1,
                                   update=_cnc_tool_changed,
                                   description="Diameter of the holder's nose, where the tool comes out. 0: what "
                                               "the holder type usually has")
    holder_length: FloatProperty(name="Holder length", unit="LENGTH", default=0.0, min=0.0, soft_max=0.2,
                                 update=_cnc_tool_changed,
                                 description="From the holder's nose up to its gauge line, where it meets the spindle "
                                             "(the holder's gauge length). 0: what the holder type usually has")
    place: EnumProperty(
        name="Place", default="POCKET", update=_cnc_tool_changed,
        items=[("SPINDLE", "Spindle", "In the spindle when the program starts"),
               ("POCKET", "Changer pocket", "In a pocket of the tool changer (the pocket number is used by the "
                                            "tool changer)"),
               ("BENCH", "Bench", "On the bench: put in by hand at a tool change")],
        description="Where the tool is when the program starts")
    pocket: IntProperty(name="Pocket", default=0, min=0, max=999, update=_cnc_tool_changed,
                        description="The tool changer's pocket this tool stands in (0: as the T number)")
    step_file: StringProperty(name="STEP file", subtype="FILE_PATH",
                              description="The manufacturer's STEP model of the tool (or tool with holder) that "
                                          "is shown for this tool")
    step_mesh: PointerProperty(type=bpy.types.Mesh)           # the STEP model, read into the project
    tip: FloatVectorProperty(size=3)                           # STEP model: tip in its own space
    axis: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))  # STEP model: from the tip into the holder
    note: StringProperty()            # e.g. "Fusion type 'lollipop mill' read as a ball end mill"
    source: StringProperty()          # where the sizes came from: "program comment", "tool table", "typed", ...


ZERO_ITEMS = [("TOP_CENTRE", "Top, centre", "The middle of the workpiece's top face"),
              ("TOP_FL", "Top, front left corner", "Smallest X and Y, on top"),
              ("TOP_FR", "Top, front right corner", "Largest X, smallest Y, on top"),
              ("TOP_BL", "Top, back left corner", "Smallest X, largest Y, on top"),
              ("TOP_BR", "Top, back right corner", "Largest X and Y, on top"),
              ("BOTTOM_CENTRE", "Bottom, centre", "The middle of the workpiece's bottom face"),
              ("POINT", "Clicked point", "The point you clicked on the workpiece (snaps to a corner near it)")]


class FRCnc(bpy.types.PropertyGroup):
    x_joint: StringProperty(name="X", update=_cnc_changed,
                            description="The slide joint that moves the machine's X axis (made in 4 Motion)")
    y_joint: StringProperty(name="Y", update=_cnc_changed,
                            description="The slide joint that moves the machine's Y axis (made in 4 Motion)")
    z_joint: StringProperty(name="Z", update=_cnc_changed,
                            description="The slide joint that moves the machine's Z axis (made in 4 Motion)")
    x_reverse: BoolProperty(name="Reverse X", default=False, update=_cnc_changed,
                            description="Tick when the program's +X moves the tool the other way than the app "
                                        "thinks (the tool should go towards the model's +X for +X)")
    y_reverse: BoolProperty(name="Reverse Y", default=False, update=_cnc_changed,
                            description="Tick when the program's +Y moves the tool the other way than the app "
                                        "thinks (the tool should go towards the model's +Y for +Y)")
    z_reverse: BoolProperty(name="Reverse Z", default=False, update=_cnc_changed,
                            description="Tick when the program's +Z moves the tool the other way than the app "
                                        "thinks (+Z should lift the tool off the workpiece)")
    rapid_x: FloatProperty(name="X rapid (mm/min)", default=5000.0, min=1.0, soft_max=60000.0, precision=0,
                           step=10000, update=_cnc_changed,
                           description="The machine's rapid speed on X in mm per minute (MAX_VELOCITY of the "
                                       "axis in LinuxCNC's .ini × 60). Sets how long G0 moves take")
    rapid_y: FloatProperty(name="Y rapid (mm/min)", default=5000.0, min=1.0, soft_max=60000.0, precision=0,
                           step=10000, update=_cnc_changed,
                           description="The machine's rapid speed on Y in mm per minute")
    rapid_z: FloatProperty(name="Z rapid (mm/min)", default=3000.0, min=1.0, soft_max=60000.0, precision=0,
                           step=10000, update=_cnc_changed,
                           description="The machine's rapid speed on Z in mm per minute")
    spindle_joint: StringProperty(name="Spindle", update=_cnc_changed,
                                  description="The rotate joint of the spindle (tick Motor on it). It turns as the "
                                              "program's S and M3 / M4 / M5 say. Empty: the spindle does not turn")
    tool: PointerProperty(type=bpy.types.Object, update=_cnc_changed)
    tool_uid: StringProperty()
    workpiece: PointerProperty(type=bpy.types.Object, update=_cnc_changed)
    workpiece_uid: StringProperty()
    zero_mode: EnumProperty(name="Work zero", items=ZERO_ITEMS, default="TOP_CENTRE", update=_cnc_changed,
                            description="Where the program's zero (X0 Y0 Z0) is on the workpiece: the same point "
                                        "as in the CAM set-up (Fusion: Setup > WCS)")
    zero_point: FloatVectorProperty(size=3, update=_cnc_changed)        # clicked, in the workpiece's own space
    zero_shift: FloatVectorProperty(
        name="Shift", size=3, unit="LENGTH", subtype="TRANSLATION", update=_cnc_changed,
        description="Moves the work zero by this much along the machine's X, Y and Z (in mm), for a zero that is "
                    "not on a corner or the centre")
    home: FloatVectorProperty(size=3)              # the X/Y/Z joint values at machine zero (G53 X0 Y0 Z0, G28)
    home_set: BoolProperty(default=False)
    tools: CollectionProperty(type=FRCncTool)
    tools_index: IntProperty(default=0)
    add_kind: EnumProperty(name="Type", items=TOOL_KIND_ITEMS, default="FLAT",
                           description="The type a tool the program uses but the list does not have is added as")
    tool_lengths: BoolProperty(
        name="Tool lengths move the spindle", default=True, update=_cnc_changed,
        description="Like a tool length offset (G43): a tool that sticks out further than the one in the spindle "
                    "moves the spindle up by the difference, so every tool's tip is where the program says. Off: "
                    "every tool is shown with its tip where the spindle's tool has its tip")
    tool_table: StringProperty(
        name="Tool table", subtype="FILE_PATH", update=_cnc_changed,
        description="LinuxCNC's tool table (tool.tbl), optional: tool numbers, diameters and lengths. Without it "
                    "the sizes come from the tool comments at the top of the program (Fusion writes them)")
    zero_empty: PointerProperty(type=bpy.types.Object)       # the work zero marker (child of the workpiece)

    # ---- air blast (task 0039) ----
    air_on_code: IntProperty(
        name="Air on code", default=7, min=7, max=199, update=_air_changed,
        description="The M-code that switches the air on in your programs: M7 (mist) on most machines, M8 if "
                    "your machine blows air on flood, or a user code M100 to M199. The air blows from this code "
                    "to the air-off code")
    air_off_code: IntProperty(
        name="Air off code", default=9, min=7, max=199, update=_air_changed,
        description="The M-code that switches the air off: M9 on most machines (M9 always stops M7 and M8), or "
                    "a user code M100 to M199")
    air_always: BoolProperty(
        name="Air always on while the spindle turns", default=False, update=_air_changed,
        description="For programs without an air code: the air blows whenever the spindle turns (M3 / M4 until "
                    "M5)")
    air_source: EnumProperty(
        name="Air from", items=AIR_SOURCE_ITEMS, default="SPINDLE", update=_air_changed,
        description="Where the air comes out: through the spindle at the tool's tip, or from an external nozzle "
                    "part of the model")
    air_nozzle: PointerProperty(type=bpy.types.Object, update=_air_changed)
    air_nozzle_uid: StringProperty()
    air_tip: FloatVectorProperty(
        name="Nozzle tip", size=3, unit="LENGTH", subtype="TRANSLATION", update=_air_changed,
        description="Where the air comes out, in the nozzle part's own space (found from its shape or the "
                    "clicked point; change it here to move it)")
    air_dir: FloatVectorProperty(
        name="Blows towards", size=3, subtype="DIRECTION", default=(0.0, 0.0, -1.0), update=_air_changed,
        description="The way the nozzle blows, in the nozzle part's own space. Drag the ball to aim it, or press "
                    "'Aim at the workpiece'")
    air_strength: EnumProperty(
        name="Strength", items=[("SOFT", "Soft", "A light blow: dust and light chips fly, heavy ones are only "
                                                 "pushed"),
                                ("NORMAL", "Normal", "Shop air: most chips are blown off the part (nozzle within "
                                                     "about 10 cm of the cut)"),
                                ("STRONG", "Strong", "A strong blast: chips fly off the part even from a nozzle "
                                                     "15 cm away")],
        default="NORMAL", update=_air_changed,
        description="How hard the air blows. Soft moves light chips, Normal blows most chips off the part, "
                    "Strong clears it also from further away")
    air_cone: FloatProperty(
        name="Cone angle", subtype="ANGLE", default=math.radians(15), min=math.radians(3), max=math.radians(45),
        update=_air_changed,
        description="How wide the jet spreads (half of the cone's opening angle): narrow blows hard on one spot, "
                    "wide blows softer over a larger area")
    air_reach: FloatProperty(
        name="Reach", unit="LENGTH", default=0.25, min=0.02, soft_max=1.0, update=_air_changed,
        description="How far the air reaches from the nozzle. Chips further away than this are not moved")
    air_show: BoolProperty(
        name="Show air", default=False, update=_air_changed,
        description="Shows the jet as a faint cone while the air blows (in the view and in renders). Off by "
                    "default: real air cannot be seen")


def _show_joints_changed(self, context):
    """Show or hide the joints' arrows and the cylinders' pin markers. (Defined above the class that uses it:
    Blender reads the property definitions while this file is read, so a function further down is not
    there yet – that was the NameError of 0.2.19.)"""
    from . import cylinders
    show = self.show_joints
    for j in self.joints:
        if j.frame is not None:
            try:
                j.frame.hide_set(not show)
            except RuntimeError:
                pass
    cylinders.show(context.scene, show)
    from . import linkages
    linkages.show(context.scene, show)


# ---------------------------------------------------------------------------
# way covers (task 0034): telescopic covers follow one slide axis
# ---------------------------------------------------------------------------

def _waycover_changed(self, context):
    """Travel, direction, counting or the axis changed: made sections get their new shares at once."""
    if context is None or context.scene is None:
        return
    from . import waycover
    waycover.refresh(context.scene)


class FRWayCoverSection(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", description="Name of this way cover section. Double-click to rename it")
    joint: StringProperty()                                # the slide joint made for it ('' until Make it)
    parts: CollectionProperty(type=FRObjectRef)            # chosen parts, until the section is made


class FRWayCover(bpy.types.PropertyGroup):
    axis: StringProperty(
        name="Axis", update=_waycover_changed,
        description="The slide joint (the machine axis) the covers follow. Pick it from the list, or make one "
                    "from the selected parts with 'Make one from the selection'")
    sections: CollectionProperty(type=FRWayCoverSection)
    sections_index: IntProperty(default=0)
    total: FloatProperty(
        name="Total length of movement", unit="LENGTH", default=0.5, min=0.0, soft_max=5.0, update=_waycover_changed,
        description="How far the axis moves in all, in mm. The sections share it out. 'Read from the axis' "
                    "takes it from the axis limits")
    flip: BoolProperty(
        name="Flip", default=False, update=_waycover_changed,
        description="The covers open the other way round: use this when they slide against the axis' direction")
    housing_counts: BoolProperty(
        name="Fixed housing counts as a section", default=False, update=_waycover_changed,
        description="Tick this when the first section is the housing on the fixed side (it never moves): the "
                    "others then share the travel in one step less. Off: the sections are the moving covers")


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

    # ---- brand kit and finishing (task 0018) ----
    brand_name: StringProperty(name="Brand kit", default="",
                               description="The name of the brand kit this project uses (the company: logo, "
                                           "colours, font and contact line)")
    brand_logo: StringProperty(name="Logo", subtype="FILE_PATH",
                               description="The company logo as a PNG or JPG picture (a PNG with a see-through "
                                           "background is best)")
    brand_color1: FloatVectorProperty(name="Card colour", subtype="COLOR", size=3, min=0.0, max=1.0,
                                      default=(0.0075, 0.0144, 0.0273),
                                      description="The background of the title card and the end card")
    brand_color2: FloatVectorProperty(name="Text colour", subtype="COLOR", size=3, min=0.0, max=1.0,
                                      default=(1.0, 1.0, 1.0),
                                      description="The colour of the text on the title card and the end card")
    brand_font: StringProperty(name="Font", subtype="FILE_PATH",
                               description="A font file (.ttf or .otf) for the cards, captions and watermark. "
                                           "Empty: Blender's own font")
    brand_contact: StringProperty(name="Contact line", description="The line under the logo on the end card, e.g. "
                                                                   "the website and e-mail address")
    still_logo: EnumProperty(
        name="Logo on images", default="NONE",
        description="Puts the brand kit's logo in a corner of every still image you render",
        items=[("NONE", "No logo", "No logo on images"), ("TL", "Top left", "Logo in the top left corner"),
               ("TR", "Top right", "Logo in the top right corner"),
               ("BL", "Bottom left", "Logo in the bottom left corner"),
               ("BR", "Bottom right", "Logo in the bottom right corner")])
    still_logo_size: FloatProperty(name="Logo size", default=0.12, min=0.03, max=0.4, precision=2, step=1,
                                   description="How wide the logo is on images, as a part of the picture width")
    wm_on: BoolProperty(name="Watermark on the next renders", default=False,
                        description="Puts the watermark across images and videos you render or add to the queue "
                                    "while this is on. Each queued job remembers it, so you can send a draft and "
                                    "render the final without watermark")
    wm_kind: EnumProperty(name="Watermark", default="DRAFT",
                          description="The words across the picture: DRAFT, CONFIDENTIAL or your own text",
                          items=[("DRAFT", "DRAFT", "The word DRAFT"),
                                 ("CONFIDENTIAL", "CONFIDENTIAL", "The word CONFIDENTIAL"),
                                 ("CUSTOM", "Own text", "Your own words")])
    wm_text: StringProperty(name="Own text", default="PREVIEW",
                            description="Your own watermark words (used when Watermark is set to Own text)")
    wm_size: FloatProperty(name="Size", default=0.12, min=0.03, max=0.4, precision=2, step=1,
                           description="How tall the watermark letters are, as a part of the picture height")
    wm_opacity: FloatProperty(name="See-through", default=0.25, min=0.05, max=1.0, precision=2, step=5,
                              description="How strong the watermark is: 1 = solid, 0.25 = see-through (the default)")

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
        description="What lights the machine. The background you see stays as it is. The light looks at the "
                    "top of this panel set it for you",
        items=studio.LIGHT_ITEMS)              # stored by number: old projects keep Studio, 360° photo, Sky
    sky_weather: EnumProperty(
        name="Weather", default="SUN", update=_world_changed, items=studio.WEATHER_ITEMS,
        description="Sun or overcast, wherever the sky gives the light (Sky, the sea, the deck, the quay)")
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

    # ---- camera (task 0017) ----
    view_frame: EnumProperty(
        name="Frame", default="MODEL",
        description="What the view buttons and Fit fill the picture with",
        items=[("MODEL", "Whole model", "The whole visible machine fills the picture", 0),
               ("SELECTION", "Selection", "Only what is selected fills the picture (click a subassembly "
                                          "first). Nothing selected: the whole machine", 1)])
    view_space: EnumProperty(
        name="Space around", default="NORMAL",
        description="How much room the view buttons and Fit leave around the machine (or the selection)",
        items=[("TIGHT", "Tight", "The machine just fits: almost no space around it", 0),
               ("NORMAL", "Normal", "A little space around the machine", 1),
               ("ROOMY", "Roomy", "Clear space around the machine, for text or a logo next to it", 2)])
    camera_lens: FloatProperty(
        name="Lens", min=8.0, max=600.0, soft_min=14.0, soft_max=300.0, step=100, precision=0,
        get=_lens_get, set=_lens_set,
        description="Lens of the active camera in mm. 50 looks natural; 24-35 shows more and looks wider; "
                    "85-135 makes the machine look flatter. Press Fit after changing it")
    camera_blur: EnumProperty(
        name="Background blur", items=studio.BLUR_ITEMS, get=_blur_get, set=_blur_set,
        description="Blurs what is far in front of or behind the sharp spot, like a photo camera. The same "
                    "look on a small and a big machine. Each camera keeps its own")

    # ---- turntable video (task 0017) ----
    turntable_seconds: FloatProperty(
        name="Length (s)", default=10.0, min=2.0, max=600.0, soft_max=60.0, step=100, precision=0,
        description="How long one full turn around the machine takes, in seconds. The video loops: its end "
                    "joins its start without a jump")
    turntable_height: EnumProperty(
        name="Camera height", default="MIDDLE", items=studio.TURNTABLE_HEIGHT_ITEMS,
        description="How high the camera is while it goes round the machine")
    turntable_quality: EnumProperty(
        name="Quality", default="preview",
        description="Fast preview (EEVEE) shows the turn in minutes. Draft to Best: real light, cleaner but "
                    "slower. A turntable has many frames: try Fast preview first",
        items=[("eevee", "Fast preview (EEVEE)", "Real-time engine: a quick look at the turn, in minutes"),
               ("draft", "Draft", "Real light, grainy, quick"), ("preview", "Preview", "Real light, a bit grainy"),
               ("final", "Final", "Real light, clean"), ("best", "Best", "Real light, very clean (slow)")])

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
    show_joints: BoolProperty(name="Show joint axes", default=True, update=_show_joints_changed,
                              description="Shows or hides the joints' arrows and the cylinders' pin markers in the "
                                          "view. They never show in renders")
    cylinders: CollectionProperty(type=FRCylinder)
    cylinders_index: IntProperty(default=0)
    cyl_pick_barrel: CollectionProperty(type=FRObjectRef)       # what Add cylinder will use
    cyl_pick_rod: CollectionProperty(type=FRObjectRef)
    mechanisms: CollectionProperty(type=FRMechanism)
    mechanisms_index: IntProperty(default=0)
    mech_base: PointerProperty(type=bpy.types.Object)          # what Add mechanism stands on ('' = the parent)
    mech_kind: EnumProperty(name="Type", items=MECHANISM_KINDS, default="SCISSOR",
                            description="What kind of mechanism to add; the steps below change with it")
    poses: CollectionProperty(type=FRPose)
    poses_index: IntProperty(default=0)
    explode_factor: FloatProperty(name="Distance", default=0.5, min=0.0, soft_max=3.0,
                                  description="How far the pieces move apart (0.5 = half their distance from the "
                                              "centre). Then press Explode")
    explode_direction: EnumProperty(name="Direction", default="RADIAL",
                                    description="Which way the pieces move: outwards from the centre, along X, "
                                                "along Y, or up and down", items=[
        ("RADIAL", "Outwards", ""), ("X", "Along X", ""), ("Y", "Along Y", ""), ("Z", "Up / down", "")])
    explode_level: EnumProperty(name="Pieces", default="CHILDREN",
                                description="What moves apart: the subassemblies directly inside the selected one, "
                                            "or every single part", items=[
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

    # ---- labels pointing at parts (task 0025) ----
    callouts: CollectionProperty(type=FRCallout)
    callouts_index: IntProperty(default=0)
    callouts_on: BoolProperty(name="Labels in renders", default=True,
                              description="Draws the labels (with their lines) in stills and in MP4 videos. Off: "
                                          "none of them is drawn")
    callout_size: EnumProperty(name="Text size", default="MEDIUM",
                               description="How big the words in the labels are",
                               items=[("SMALL", "Small", "Fine print"), ("MEDIUM", "Medium", "Normal"),
                                      ("LARGE", "Large", "Easy to read on a phone")])

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
    # ---- CNC machine for G-code programs (task 0026) ----
    cnc: PointerProperty(type=FRCnc)

    # ---- way covers (task 0034) ----
    waycover: PointerProperty(type=FRWayCover)

    last_message: StringProperty(default="")
    # cached so panels and sliders don't scan thousands of objects on every redraw
    model_count: IntProperty(default=0)
    bounds_valid: BoolProperty(default=False)
    bounds_min: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    bounds_max: FloatVectorProperty(size=3, default=(1.0, 1.0, 1.0))


CLASSES = (FRMaterialGroup, FRSchemeLook, FRScheme, FRRule, FRGroupAlias, FRTreeItem, FRFoundPart,
           FRObjectRef, FRJoint, FRPoseJoint, FRPlace, FRPose, FRCylinder, FRMechLink, FRMechanism, FRUid, FRVisSet,
           FRShot, FRPictureCard, FRCallout, FRAnimBlock,
           FRAnimation, FRQueueJob, FRReportLine, FRMillBit, FRMilling, FRWayCoverSection, FRWayCover, FRCncTool, FRCnc,
           FRSceneSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing = PointerProperty(type=FRSceneSettings)


def unregister():
    del bpy.types.Scene.fresing
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
