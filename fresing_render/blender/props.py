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
from ..core import vessel_motion as vessel_core

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
        s = context.scene.fresing
        if any(g.name == self.name and g != self for g in s.groups):   # 0055: no two groups with one name
            taken = self.name
            self.name = old                      # runs this update again; old == name then, nothing to do
            s.last_message = f"A group named '{taken}' already exists - pick another name"
            return
        _remember_rename(context.scene, old, self.name)
        for sch in list(s.schemes) + [sh.own_scheme for sh in s.shots]:   # 0055: schemes and scenes follow
            for look in sch.looks:
                if look.group == old:
                    look.group = self.name
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
            from . import queue
            for j in s.queue:
                if j.shot == old:
                    j.shot = new
                    queue.relabel(j)
            if s.active_shot == old:
                s.active_shot = new
        elif kind == "animation":
            from . import queue
            for j in s.queue:
                if j.animation == old:
                    j.animation = new
                    queue.relabel(j)         # keeps "Time test" and "(with watermark)" (bug hunt row 17c)
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
    queue_on: BoolProperty(name="Queue in this scheme", default=True,
                           description="Ticked: the buttons under Every paint scheme (7 Render queue) render in "
                                       "this scheme too. Untick a scheme to leave it out")


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
    return ob.type == "CAMERA" and not ob.get("fr_anim_camera") and not ob.get("fr_queue_only")


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
    # follows by a table (task 0080): '' = by the ratio above; else who wrote the table ("spool:Drum"), the keys are
    # on the motion empty (joints.TABLE)
    couple_table: StringProperty(default="")
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
    cuts: StringProperty()         # which cuts are on (task 0086); '' = saved before cuts


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
    ("FADE_OUT", "Fade out", "A subassembly fades away (or turns X-ray) over the step's duration, e.g. a housing that "
     "shows the mechanism inside", "MOD_OPACITY", 9),
    ("FADE_IN", "Fade in", "A subassembly fades back in over the step's duration", "MATSHADERBALL", 10),
    ("SEQUENCE", "Assembly sequence", "Takes a subassembly apart part by part (or puts it together): the parts fly "
     "out one after another, fasteners first", "MOD_EXPLODE", 11),
]


def _seq_timing_changed(self, context):
    """An Assembly sequence step's time per part or overlap changed: its length follows (task 0100)."""
    from . import sequence
    sequence.sync_duration(self)


def _seq_preview_changed(self, context):
    if context is None or context.scene is None:
        return
    from . import sequence
    sequence.preview(context.scene, self, self.seq_preview / 100.0)


def _gcode_step_changed(self, context):
    """A G-code step's file or speed changed: its length follows from the program."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode
    gcode.keep_path(self, "gcode_file", gcode.PROGRAM_ABS)     # '//' next to the project (task 0051)
    gcode.step_changed(context.scene, self)


def _cnc_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode
    gcode.setup_changed(context.scene)


def _rotary_changed(self, context):
    """A, B or C picked (or reversed) again: the last Check is of another set-up (task 0071, bug hunt 0068 row 19c)."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode, rotary
    rotary.LAST_CHECK.clear()
    gcode.setup_changed(context.scene)


def _cnc_table_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import gcode
    gcode.keep_path(self, "tool_table", gcode.TABLE_ABS)       # '//' next to the project (task 0051)
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


def _xray_style(self, context):
    if context is not None and context.scene is not None:
        from . import fade
        fade.restyle(context.scene)


def _trail_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import trails
    trails.style(context.scene, self)


class FRTrail(bpy.types.PropertyGroup):
    """A line that draws the path of a point of a part (task 0073)."""
    name: StringProperty(name="Name", description="Shown in the list: the part's name unless you type something else")
    enabled: BoolProperty(name="On", default=True, update=_trail_changed,
                          description="Switches this trail line on or off (in the view and in renders)")
    part: PointerProperty(type=bpy.types.Object, name="Part",
                          description="The part whose point the line follows (a hook, a tool, a carriage)")
    part_uid: StringProperty()
    point: EnumProperty(name="Point", default="ORIGIN",
                        description="Which point of the part draws the line",
                        items=[("ORIGIN", "Part's origin", "The part's own origin (its zero point from CAD)"),
                               ("CLICKED", "Clicked point", "A point you click on the part"),
                               ("TIP", "Tool tip", "The tip of the milling bit or CNC tool this part is")])
    local: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    animation: StringProperty(name="Animation", update=_trail_changed,
                              description="The animation whose Build draws this line. Empty: every animation")
    color: FloatVectorProperty(name="Colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=(1.0, 0.35, 0.05),
                               update=_trail_changed, description="The colour of the line")
    thickness: FloatProperty(name="Thickness", unit="LENGTH", default=0.004, min=0.0002, soft_max=0.05,
                             precision=4, update=_trail_changed,
                             description="How thick the line is drawn, in mm")
    grow: BoolProperty(name="Draw as it goes", default=True, update=_trail_changed,
                       description="On: the line grows behind the point as the animation plays. Off: the whole path "
                                   "shows from the first frame")
    in_render: BoolProperty(name="In renders", default=True, update=_trail_changed,
                            description="Also shows the line in pictures and videos. Off: only in the 3D view")
    obj: PointerProperty(type=bpy.types.Object)
    count: IntProperty(default=0)
    seq_owner: StringProperty()          # made by an Assembly sequence step (task 0100): its seq_id


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


class FRCamPathPoint(bpy.types.PropertyGroup):
    """One point of a Fly a path camera step (task 0087), in world metres."""
    co: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0), subtype="XYZ", unit="LENGTH")


def _speed_mmin_get(self):
    """A Run motor step's slide speed in m/min (kept in mm/s)."""
    return float(self.speed_mms) * 0.06


def _speed_mmin_set(self, value):
    self.speed_mms = float(value) / 0.06


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
        ("ORBIT", "Orbit", "Turns around the model"),
        ("RIDE", "Ride along", "The camera rides on a part: it keeps its place and view on the part while the part "
                               "moves (on the carriage, the boom tip, a vessel)"),
        ("PATH", "Fly a path", "The camera flies along a smooth path through points, at an even speed. Make the "
                               "path from saved cameras or add points from the view"),
        ("AIM", "Watch part", "Keeps a part in the middle: the camera stays where it is and turns, so a part you "
                              "pick stays in the middle of the picture (a hook, the tool, the carriage)")],
        description="Cut to: switch to a camera at once. Move to: fly smoothly to a camera. Orbit: turn around "
                    "the model. Ride along: ride on a moving part. Fly a path: fly through points. Watch part: "
                    "turn so a part stays in the middle")
    camera: PointerProperty(type=bpy.types.Object, name="Camera", poll=_camera_poll,
                            description="The camera to cut or fly to (cameras are made in 5 Scene & Render)")
    # camera rides along / flies a path / keeps a part in the middle (task 0087)
    ride_camera: PointerProperty(
        type=bpy.types.Object, name="Seat", poll=_camera_poll,
        description="A saved camera that shows where the camera sits on the part and how it looks (place it with "
                    "the model as it stands at the start). Empty: it rides from where the camera is when the step "
                    "starts")
    ride_level: BoolProperty(
        name="Keep level", default=False,
        description="The riding camera stays upright when its part tilts or rolls (on a vessel at sea, a boom that "
                    "lifts): it follows the part's place and its turn seen from above, not its tilt")
    ride_look: EnumProperty(
        name="Look", default="WITH",
        items=[("WITH", "With the part", "Keeps its view on the part: it turns when the part turns"),
               ("PART", "At a part", "Turns so the part you pick below stays in the middle of the picture")],
        description="With the part: the camera keeps its view on the part it rides. At a part: it turns so another "
                    "part (or the same one) stays in the middle of the picture")
    path_look: EnumProperty(
        name="Look", default="AHEAD",
        items=[("AHEAD", "Ahead", "Looks where the path goes, like from a drone"),
               ("MODEL", "At the model", "Looks at the middle of the model all the way"),
               ("PART", "At a part", "Turns so the part you pick below stays in the middle of the picture")],
        description="Where the camera looks while it flies: ahead along the path, at the middle of the model, or "
                    "at a part you pick (it stays in the middle of the picture)")
    aim_uid: StringProperty()
    aim_name: StringProperty(name="Part to keep in the middle")
    cam_blend: FloatProperty(
        name="Blend in (s)", default=1.0, min=0.0, soft_max=10.0, step=10, precision=2,
        description="How long the camera takes to glide from where it was into this step's view, in seconds (0: it "
                    "jumps there at once)")
    path_from_here: BoolProperty(
        name="Start where the camera is", default=True,
        description="The path starts where the camera is when this step begins, so it never jumps. Off: it starts "
                    "at the path's first point (it glides there during Blend in)")
    path_points: CollectionProperty(type=FRCamPathPoint)
    path_obj: PointerProperty(type=bpy.types.Object)
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
    # the same speed in m/min, shown for a cable's joint (task 0078): 10 m/min = 166.7 mm/s
    speed_mmin: FloatProperty(name="Cable speed (m/min)", soft_min=-300.0, soft_max=300.0, precision=2, step=100,
                              get=_speed_mmin_get, set=_speed_mmin_set,
                              description="How fast the cable runs, in metres per minute (laying a power cable: "
                                          "about 10 m/min). Negative: the cable is hauled back in")
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
                        description="How long the motor (or the camera flying a path) takes to get up to speed and "
                                    "to stop, in seconds (with Motion set to Smooth, Slow start or Slow stop)")
    # Run G-code program (task 0026)
    gcode_file: StringProperty(
        name="Program", subtype="FILE_PATH", update=_gcode_step_changed, options={"PATH_SUPPORTS_BLEND_RELATIVE"},
        description="The CNC program (.ngc, .nc, .tap, .gcode): the one your CAM writes for the machine. A program "
                    "next to the saved project is found there on another PC too; a copy is also kept in the project")
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
        name="Tool change pause", default=1.0, min=0.0, max=5.0, unit="TIME_ABSOLUTE", update=_gcode_step_changed,
        description="How long the machine pauses at each manual tool change (M6), 0 to 5 seconds; the head's "
                    "travel to the change position comes on top. Short looks best in a video. The new tool shows "
                    "half way (with the hand: when the hand has put it in)")
    gcode_hand: BoolProperty(
        name="Show hand", default=False, update=_gcode_step_changed,
        description="At a manual tool change a gloved hand reaches in, takes the old tool out of the spindle, "
                    "puts the new one in and leaves. It needs 2.8 seconds: a shorter pause grows to that (the "
                    "step's Details say so)")
    gcode_tc_caption: BoolProperty(
        name="Caption at tool changes", default=False, update=_gcode_step_changed,
        description="Shows a caption such as 'Tool change: T3 Ø50 face mill' at every tool change of a video, in "
                    "the brand kit's caption look (6 Animation > Video finishing)")
    gcode_changer_speed: FloatProperty(
        name="Changer speed", default=1.0, min=0.25, max=4.0, update=_gcode_step_changed,
        description="How fast the tool changer works in the video: 1 = real (its turns and its animation as set "
                    "up), 2 = twice as fast, 0.5 = half as fast. The head's travel follows 'Rapids faster'")
    gcode_atc: StringProperty(
        name="Changer animation", update=_gcode_step_changed,
        description="An animation of the tool changer (arm, cover, the carousel moving in) that plays at every tool "
                    "change (M6); the program waits for it. Make it as an animation of its own with the tool "
                    "changer's joints. The carousel's turn to the right pocket is made by the app. Empty: none")
    gcode_atc_swap: FloatProperty(
        name="Swap at (s)", default=1.0, min=0.0, soft_max=30.0, update=_gcode_step_changed,
        description="When in the changer animation the tools swap, in seconds from its start: up to here it plays "
                    "before the old tool goes into its pocket, the rest after the new one is in the spindle")
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
    # Fade out / Fade in (task 0073)
    fade_stop: FloatProperty(name="Stop at", subtype="PERCENTAGE", default=0.0, min=0.0, max=95.0, precision=0,
                             description="How much of the part stays visible at the faded end, in %: 0 = gone "
                                         "(then hidden, it costs nothing), 20 = a faint ghost stays")
    fade_xray: BoolProperty(name="Fade to X-ray", default=False,
                            description="The parts turn see-through with glowing edges (X-ray) instead of vanishing, "
                                        "so the mechanism inside shows and the housing's outline stays")
    fade_color: FloatVectorProperty(name="X-ray colour", subtype="COLOR", size=3, min=0.0, max=1.0,
                                    default=(0.35, 0.65, 1.0),
                                    description="The colour of the X-ray look of this step")
    fade_strength: FloatProperty(name="X-ray strength", default=0.7, min=0.0, max=1.0, subtype="FACTOR",
                                 description="How strongly the X-ray look shows: 0 = almost invisible, 1 = clearly "
                                             "drawn edges and a coloured haze")
    # Assembly sequence (task 0100)
    seq_id: StringProperty()
    seq_mode: EnumProperty(
        name="Way", default="APART",
        items=[("APART", "Take apart", "The parts fly out one after another, to an exploded place"),
               ("TOGETHER", "Put together", "The parts come in one after another and end exactly at their places "
                                            "(the exact reverse of Take apart)")],
        description="Take apart: the parts fly out of the subassembly one after another. Put together: they come in "
                    "from the exploded places and end exactly where they belong")
    seq_order: EnumProperty(
        name="Order", default="OUTSIDE_IN",
        items=[("OUTSIDE_IN", "Outside in", "Fasteners first, then the parts nearest the outside (seen along the way "
                                            "each part leaves)"),
               ("TREE", "Tree order", "In the order of the model tree"),
               ("REVERSE", "Reverse", "The model tree from the bottom up")],
        description="Which part goes first when taken apart (put together plays it backwards). Outside in: bolts, "
                    "nuts and washers first, then the parts nearest the outside")
    seq_direction: EnumProperty(
        name="Direction", default="AXIS",
        items=[("CENTRE", "Away from the centre", "Each part flies straight away from the middle of the "
                                                  "subassembly"),
               ("AXIS", "Along an axis", "Along one axis of the subassembly, all the same way (it turns with the "
                                         "subassembly)"),
               ("UP", "Up", "Straight up")],
        description="Which way the parts fly. Along an axis or up, parts that would end in each other's way are "
                    "stacked one beyond the other")
    seq_axis: EnumProperty(name="Axis", default="Z",
                           items=[("X", "+X", "Along the subassembly's own X axis"),
                                  ("Y", "+Y", "Along the subassembly's own Y axis"),
                                  ("Z", "+Z", "Along the subassembly's own Z axis"),
                                  ("-X", "-X", "Against the subassembly's own X axis"),
                                  ("-Y", "-Y", "Against the subassembly's own Y axis"),
                                  ("-Z", "-Z", "Against the subassembly's own Z axis")],
                           description="The axis of the subassembly the parts fly along, and which way (its own axes "
                                       "from CAD, also when a joint has turned it)")
    seq_by_size: BoolProperty(
        name="By size", default=True,
        description="On: each part flies far enough to clear the whole subassembly. Off: the distance you set")
    seq_distance: FloatProperty(name="Distance", unit="LENGTH", default=0.2, min=0.0, soft_max=5.0,
                                description="How far each part flies out, in mm (parts stacked beyond others go "
                                            "further)")
    seq_part_time: FloatProperty(name="Time per part (s)", default=1.0, min=0.05, soft_max=10.0, step=10,
                                 precision=2, update=_seq_timing_changed,
                                 description="How long each part takes to fly out (or in), in seconds. The step's "
                                             "length follows from this, the overlap and the number of parts")
    seq_overlap: FloatProperty(name="Overlap", subtype="PERCENTAGE", default=50.0, min=0.0, max=90.0, precision=0,
                               update=_seq_timing_changed,
                               description="How much the parts overlap in time: 0 % = one after the other, 50 % = "
                                           "the next starts half way through the one before")
    seq_end: EnumProperty(
        name="At the end", default="STAY",
        items=[("STAY", "Stay", "The parts stay where they flew to (put together: they wait out there)"),
               ("HIDE", "Hide", "Each part disappears when it is out (put together: it appears as it starts to "
                                "come in)"),
               ("FADE", "Fade", "Each part fades away as it flies out (put together: fades in as it comes)")],
        description="What happens to a part once it is out: it stays, it disappears, or it fades away while it "
                    "flies (Put together: the same backwards)")
    seq_trails: BoolProperty(
        name="Trail lines", default=False,
        description="Draws the path of every part as a line (a trail line per part, made at Build; they show in "
                    "6 Animation > Trail lines, where you can change their look)")
    seq_preview: FloatProperty(
        name="Preview", subtype="PERCENTAGE", default=0.0, min=0.0, max=100.0, precision=0,
        update=_seq_preview_changed,
        description="Drag to see the step in the view without building: 0 % = the start, 100 % = the end. Back to "
                    "0 % (or Build) puts the parts back")
    seq_count: IntProperty(default=0)
    seq_fasteners: IntProperty(default=0)
    seq_left_out: IntProperty(default=0)
    seq_riders: IntProperty(default=0)
    gcode_path_render: BoolProperty(
        name="Toolpath in renders", default=False, update=_gcode_step_changed,
        description="Also shows the toolpath in pictures and videos (for presentations). Off: only in the view")
    gcode_coolant: EnumProperty(
        name="Coolant", default="PROGRAM", update=_gcode_step_changed,
        items=[("PROGRAM", "From the program", "Coolant flows as the program says: the flood code (M8) floods, the "
                                               "mist code (M7) mists, M9 stops both"),
               ("FLOOD", "Flood while cutting", "Flood coolant whenever the spindle turns (for programs without "
                                                "coolant codes)"),
               ("MIST", "Mist while cutting", "Mist whenever the spindle turns (for programs without coolant codes)"),
               ("OFF", "Off", "No coolant in this step, whatever the program says")],
        description="When coolant flows in this step (task 0042). Switch coolant on first in 4 Motion > CNC machine "
                    "> Coolant")


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
    scheme: StringProperty()           # task 0074: the paint scheme this job renders in ("" = as the project is)


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


def _mill_marks_changed(self, context):
    if context is None or context.scene is None:
        return
    from . import machining
    machining.marks_changed(context.scene)


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
    # ---- tool marks on cut faces (task 0061) ----
    marks: BoolProperty(
        name="Tool marks", default=True, update=_mill_marks_changed,
        description="Cut faces show the marks of the tool that made them, in the direction it went: the arcs of a "
                    "face mill or end mill on a floor, fine lines on walls, rings in a drilled hole, and the sheen "
                    "that follows them. Off: every cut face gets the same plain machined look")
    marks_size: FloatProperty(
        name="Mark size", default=1.0, min=1.0, max=10.0, step=10, precision=1, update=_mill_cut_look_changed,
        description="How far apart the tool marks are drawn. 1 is real: the feed per tooth of the program, often "
                    "0.05 to 0.3 mm, so in a shot of the whole machine you only see the sheen. For a close-up, "
                    "raise it (up to 10 times wider) until the arcs show")
    marks_strength: FloatProperty(
        name="Strength", default=1.0, min=0.0, max=2.0, step=10, precision=2, update=_mill_cut_look_changed,
        description="How deep the tool marks look. 1 is a normal fresh cut; lower for a fine finishing cut, "
                    "higher for a rough one. The marks also depend on the cut faces' material: crisp on "
                    "aluminium, finer on steel, faint on plastic")

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


def _pockets_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import toolchange
    toolchange.pockets_changed(context.scene)


class FRCncPocket(bpy.types.PropertyGroup):
    """A pocket of the tool changer (task 0041): a point on a part (it follows the part, e.g. a turning carousel)
    where a tool's gauge line sits, and the way the tool points from its tip into its holder."""
    number: IntProperty(name="Pocket", default=1, min=1, max=999, update=_pockets_changed,
                        description="The pocket's number: a tool stands in the pocket its tool list row names "
                                    "(Pocket, under 'Shank, holder sizes, place'), or the pocket with its T number")
    obj: PointerProperty(type=bpy.types.Object)
    uid: StringProperty()
    loc: FloatVectorProperty(size=3)                 # where the tool's gauge line sits, in the part's own space
    dir: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))   # from the tool's tip into its holder, part's space
    tip_joint: StringProperty()                      # double-arm changer (task 0064): the joint that tips this pot


# ---------------------------------------------------------------------------
# coolant (task 0042): flood and mist while milling
# ---------------------------------------------------------------------------

def _coolant_changed(self, context):
    """A coolant setting changed: the view shows it at once, the steps' summaries and the chips follow."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import coolant
    coolant.settings_changed(context.scene)


def _coolant_look_changed(self, context):
    """A look-only coolant setting changed (flow, liquid, draft): the current frame is drawn again."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import coolant
    coolant.look_changed(context.scene)


class FRCoolantNozzle(bpy.types.PropertyGroup):
    """A coolant nozzle that is a part of the model (on the spindle head): where the liquid comes out and which
    way, in the part's own space."""
    obj: PointerProperty(type=bpy.types.Object)
    uid: StringProperty()
    tip: FloatVectorProperty(
        name="Nozzle tip", size=3, unit="LENGTH", subtype="TRANSLATION", update=_coolant_look_changed,
        description="Where the coolant comes out, in the nozzle part's own space (found from its shape or the "
                    "clicked point; change it here to move it)")
    dir: FloatVectorProperty(
        name="Points towards", size=3, subtype="DIRECTION", default=(0.0, 0.0, -1.0), update=_coolant_look_changed,
        description="The way the nozzle squirts, in the nozzle part's own space. Drag the ball to aim it, or press "
                    "'Aim at the tool'")


class FRCoolant(bpy.types.PropertyGroup):
    enabled: BoolProperty(
        name="Coolant", default=False, update=_coolant_changed,
        description="The machine has coolant: liquid jets from the nozzles onto the tool, splash where it cuts, a "
                    "wet sheen on the block, table and vise, wet chips. When it flows is set per G-code step "
                    "(6 Animation); press Build & play after switching it on")
    flood_code: IntProperty(
        name="Flood code", default=8, min=0, max=199, update=_coolant_changed,
        description="The M-code that switches flood coolant on in your programs: M8 on most machines. 0: none")
    mist_code: IntProperty(
        name="Mist code", default=7, min=0, max=199, update=_coolant_changed,
        description="The M-code that switches mist on: M7 on most machines. When the air-on code (Air blast) is "
                    "M7 too, M7 also blows air (mist is air with drops). 0: M7 is not mist")
    off_code: IntProperty(
        name="Off code", default=9, min=0, max=199, update=_coolant_changed,
        description="The M-code that stops the coolant: M9 on most machines (M9 always stops flood and mist)")
    source: EnumProperty(
        name="Nozzles", default="AUTO", update=_coolant_changed,
        items=[("AUTO", "Automatic", "The app adds flexible coolant hoses (Loc-Line look) on a ring round the "
                                     "spindle, aimed at the tool; they follow the tool's length after each tool "
                                     "change"),
               ("PARTS", "Parts of the model", "Nozzles of your model: click each nozzle part (or the spot where "
                                               "the coolant comes out)")],
        description="Where the coolant comes from: hoses the app adds, or nozzle parts of your model")
    auto_count: IntProperty(
        name="Hoses", default=2, min=1, max=4, update=_coolant_look_changed,
        description="How many flexible hoses the app puts round the spindle (2 to 4 on most machines)")
    auto_turn: FloatProperty(
        name="Turn hoses", subtype="ANGLE", default=0.0, min=-math.pi, max=math.pi, update=_coolant_look_changed,
        description="Turns the hoses round the spindle, e.g. so they do not hide the tool from the camera")
    show_hoses: BoolProperty(
        name="Show hoses", default=True, update=_coolant_look_changed,
        description="Shows the app's hoses and their ring on the spindle. Off: only the liquid shows (when your "
                    "model has its own hoses in about the same place)")
    nozzles: CollectionProperty(type=FRCoolantNozzle)
    nozzles_index: IntProperty(default=0)
    liquid: EnumProperty(
        name="Liquid", default="EMULSION", update=_coolant_look_changed,
        items=[("EMULSION", "Emulsion", "Water-mixed coolant: milky white and see-through (most machines)"),
               ("OIL", "Cutting oil", "Neat cutting oil: clear, slightly yellow")],
        description="What the coolant looks like: milky emulsion or clear cutting oil")
    flow: FloatProperty(
        name="Flow", default=0.7, min=0.1, max=1.0, subtype="FACTOR", update=_coolant_look_changed,
        description="How much coolant flows: low gives thin streams and few drops, full flood thick streams and "
                    "a lot of splash")
    dry_time: FloatProperty(
        name="Dries in", default=4.0, min=0.5, max=30.0, unit="TIME_ABSOLUTE", update=_coolant_changed,
        description="How many seconds the block, table and vise stay wet after the coolant stops (M9)")
    wet_parts: BoolProperty(
        name="Wet sheen", default=True, update=_coolant_changed,
        description="The block, the table and the vise look wet while coolant flows: darker, glossier, drops on "
                    "the sides; they dry after it stops")
    draft: BoolProperty(
        name="Draft", default=False, update=_coolant_look_changed,
        description="Quick look for the view: plain streams, no splash or drops. Switch off for the final video")


CHANGE_MODE_ITEMS = [("STAY", "Where it is", "The head stays where the program left it; the tool is swapped there"),
                     ("Z", "Z up only", "Only Z goes to the change position's Z (machine coordinates); X and Y stay"),
                     ("XYZ", "Change position", "The head goes to the change position (machine coordinates) and "
                                                "comes back")]


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
    # ---- acceleration (task 0103) ----
    use_accel: BoolProperty(
        name="Speed up and slow down (acceleration)", default=True, update=_cnc_changed,
        description="Times every G-code move as the machine runs it: each axis speeds up and slows down with its "
                    "maximum acceleration, slows at corners (G64) or stops at them (G61), so short moves take "
                    "longer, as on the machine. Off: every move runs at full speed from start to end (projects "
                    "made before this setting came keep it off until you tick it)")
    accel_x: FloatProperty(
        name="X accel. (mm/s²)", default=1000.0, min=1.0, soft_max=20000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The X axis' maximum acceleration in mm per second² (MAX_ACCELERATION of the axis in "
                    "LinuxCNC's .ini). Bigger: short moves are quicker. Read from LinuxCNC INI fills it in")
    accel_y: FloatProperty(
        name="Y accel. (mm/s²)", default=1000.0, min=1.0, soft_max=20000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The Y axis' maximum acceleration in mm per second² (MAX_ACCELERATION in LinuxCNC's .ini)")
    accel_z: FloatProperty(
        name="Z accel. (mm/s²)", default=1000.0, min=1.0, soft_max=20000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The Z axis' maximum acceleration in mm per second² (MAX_ACCELERATION in LinuxCNC's .ini)")
    accel_a: FloatProperty(
        name="A accel. (°/s²)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The A axis' maximum acceleration in degrees per second² (MAX_ACCELERATION in LinuxCNC's .ini)")
    accel_b: FloatProperty(
        name="B accel. (°/s²)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The B axis' maximum acceleration in degrees per second² (MAX_ACCELERATION in LinuxCNC's .ini)")
    accel_c: FloatProperty(
        name="C accel. (°/s²)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The C axis' maximum acceleration in degrees per second² (MAX_ACCELERATION in LinuxCNC's .ini)")
    spindle_joint: StringProperty(name="Spindle", update=_cnc_changed,
                                  description="The rotate joint of the spindle. Picking it ticks Motor on it, so it turns "
                                              "without end, as the program's S and M3 / M4 / M5 say. Empty: the "
                                              "spindle does not turn")
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

    # ---- rotary axes A, B, C (task 0066) ----
    a_joint: StringProperty(
        name="A", update=_rotary_changed,
        description="The rotate joint the program's A turns (4th / 5th axis, about +X), made in 4 Motion. "
                    "Empty: the machine has no A axis")
    a_reverse: BoolProperty(
        name="Reverse A", default=False, update=_rotary_changed,
        description="Tick when the program's +A turns the axis the other way than the app thinks. The app "
                    "takes + as the tool going round the part right-handed about +X (the table turns the other way). "
                    "Check shows which way it turns")
    rapid_a: FloatProperty(
        name="A rapid (°/min)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The A axis' rapid speed in degrees per minute (MAX_VELOCITY in LinuxCNC's .ini × 60). "
                    "Sets how long G0 turns take; a feed move never turns faster")
    a_wrapped: BoolProperty(
        name="Wrapped", default=False, update=_cnc_changed,
        description="The A axis counts 0 … 360° and keeps turning (LinuxCNC WRAPPED_ROTARY): A90 turns "
                    "the + way to 90°, A-90 the - way to 90°. Off: plain degrees (A0 after A720 "
                    "turns back two turns)")
    b_joint: StringProperty(
        name="B", update=_rotary_changed,
        description="The rotate joint the program's B turns (4th / 5th axis, about +Y), made in 4 Motion. "
                    "Empty: the machine has no B axis")
    b_reverse: BoolProperty(
        name="Reverse B", default=False, update=_rotary_changed,
        description="Tick when the program's +B turns the axis the other way than the app thinks. The app "
                    "takes + as the tool going round the part right-handed about +Y (the table turns the other way). "
                    "Check shows which way it turns")
    rapid_b: FloatProperty(
        name="B rapid (°/min)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The B axis' rapid speed in degrees per minute (MAX_VELOCITY in LinuxCNC's .ini × 60). "
                    "Sets how long G0 turns take; a feed move never turns faster")
    b_wrapped: BoolProperty(
        name="Wrapped", default=False, update=_cnc_changed,
        description="The B axis counts 0 … 360° and keeps turning (LinuxCNC WRAPPED_ROTARY): B90 turns "
                    "the + way to 90°, B-90 the - way to 90°. Off: plain degrees (B0 after B720 "
                    "turns back two turns)")
    c_joint: StringProperty(
        name="C", update=_rotary_changed,
        description="The rotate joint the program's C turns (4th / 5th axis, about +Z), made in 4 Motion. "
                    "Empty: the machine has no C axis")
    c_reverse: BoolProperty(
        name="Reverse C", default=False, update=_rotary_changed,
        description="Tick when the program's +C turns the axis the other way than the app thinks. The app "
                    "takes + as the tool going round the part right-handed about +Z (the table turns the other way). "
                    "Check shows which way it turns")
    rapid_c: FloatProperty(
        name="C rapid (°/min)", default=3600.0, min=1.0, soft_max=100000.0, precision=0, step=10000,
        update=_cnc_changed,
        description="The C axis' rapid speed in degrees per minute (MAX_VELOCITY in LinuxCNC's .ini × 60). "
                    "Sets how long G0 turns take; a feed move never turns faster")
    c_wrapped: BoolProperty(
        name="Wrapped", default=False, update=_cnc_changed,
        description="The C axis counts 0 … 360° and keeps turning (LinuxCNC WRAPPED_ROTARY): C90 turns "
                    "the + way to 90°, C-90 the - way to 90°. Off: plain degrees (C0 after C720 "
                    "turns back two turns)")
    home_rot: FloatVectorProperty(size=3)          # the A/B/C joint values (rad) at machine zero (A0 B0 C0, G28)
    kinematics: EnumProperty(
        name="Kinematics", default="PLAIN", update=_cnc_changed,
        items=[("PLAIN", "Plain", "A, B and C are just angles of the joints; the CAM post worked out X, Y and Z for the "
                                  "turned part (LinuxCNC trivkins, most 4th-axis set-ups)"),
               ("TCP", "Follows part (TCP)", "Tool follows the part: the program is written for the part as it lies at A0 B0 C0; "
                                                      "the app moves X, Y and Z so the tool tip stays on that point "
                                                      "while the table turns (LinuxCNC TCP kinematics, table side "
                                                      "only)")],
        description="How X, Y and Z go with the rotary axes: Plain (the CAM post did the maths) or Tool follows the "
                    "part (TCP) for a rotary table or trunnion")
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
        name="Tool table", subtype="FILE_PATH", update=_cnc_table_changed, options={"PATH_SUPPORTS_BLEND_RELATIVE"},
        description="LinuxCNC's tool table (tool.tbl), optional: tool numbers, diameters and lengths. Without it "
                    "the sizes come from the tool comments at the top of the program (Fusion writes them)")
    zero_empty: PointerProperty(type=bpy.types.Object)       # the work zero marker (child of the workpiece)

    # ---- tool changes (task 0041) ----
    changer: EnumProperty(
        name="Tool change", default="MANUAL", update=_cnc_changed,
        items=[("MANUAL", "Manual", "No tool changer: at each M6 the head goes to the change position, pauses and the "
                                    "tool is swapped (optionally by a hand)"),
               ("ATC", "Carousel / umbrella", "A carousel or umbrella tool changer: the tools stand in pockets, the "
                                              "carousel turns to the right pocket, the spindle leaves the old tool "
                                              "and takes the new one"),
               ("ARM", "Double-arm", "A double-arm tool changer: the magazine turns the new tool's pot to the change "
                                     "station and tips it down, the arm grips both tools, pulls them out, turns "
                                     "180° and pushes them in. The old tool goes into the pot the new one came "
                                     "from")],
        description="How the machine changes tools at M6: by hand, with a carousel or umbrella tool changer, or with "
                    "a double-arm tool changer")
    change_mode: EnumProperty(
        name="Change position", items=CHANGE_MODE_ITEMS, default="STAY", update=_cnc_changed,
        description="Where the head goes for a manual tool change (and an ATC change without pockets): stay, lift "
                    "Z only, or go to the change position")
    change_pos: FloatVectorProperty(
        name="Change position", size=3, unit="LENGTH", subtype="TRANSLATION", update=_cnc_changed,
        description="The change position in machine coordinates (G53), like TOOL_CHANGE_POSITION in LinuxCNC's .ini. "
                    "'Axes now' takes the position the axes are at")
    carousel_joint: StringProperty(
        name="Carousel", update=_pockets_changed,
        description="The rotate joint that turns the tool carousel (made in 4 Motion). The app turns it the shortest "
                    "way to the pocket it needs. Empty: a rack, the head goes to each pocket")
    pockets: CollectionProperty(type=FRCncPocket)
    pockets_index: IntProperty(default=0)
    pocket_count: IntProperty(
        name="Pockets", default=8, min=2, max=120,
        description="How many pockets the carousel has: 'Fill the carousel' puts them evenly round its axis, "
                    "starting at pocket 1")
    pockets_reverse: BoolProperty(
        name="Number the other way", default=False,
        description="'Fill the carousel' numbers the pockets clockwise instead of counter-clockwise (seen from the "
                    "carousel's axis arrow)")
    station: IntProperty(
        name="Change station", default=1, min=1, max=999, update=_pockets_changed,
        description="The pocket that is at the spindle (where tools are swapped) when the carousel is as in the CAD "
                    "model. Usually pocket 1")
    pocket_time: FloatProperty(
        name="Turn per pocket", default=0.5, min=0.05, soft_max=3.0, unit="TIME_ABSOLUTE", update=_cnc_changed,
        description="How long the carousel takes to turn from one pocket to the next, in seconds (as on the "
                    "machine). 'Changer speed' in the step makes it faster or slower in the video")
    atc_lift: FloatProperty(
        name="Lift above pocket", default=0.1, min=0.0, soft_max=0.5, unit="LENGTH", update=_cnc_changed,
        description="How far the spindle goes up out of a pocket after leaving a tool, and comes down from to take "
                    "one")

    # ---- double-arm tool changer (task 0064) ----
    arm_slide: StringProperty()                      # the joints the app made for the arm (stroke, turn)
    arm_turn: StringProperty()
    arm_rest: FloatProperty(
        name="Rest angle", subtype="ANGLE", default=0.0, soft_min=-math.pi, soft_max=math.pi, update=_cnc_changed,
        description="Where the arm waits between tool changes, as its turn from the CAD model (0°: as in the CAD "
                    "model). After each change it waits half a turn further on, which looks the same")
    arm_grip: FloatProperty(
        name="Grip angle", subtype="ANGLE", default=math.radians(90.0), soft_min=-math.pi, soft_max=math.pi,
        update=_cnc_changed,
        description="Where the arm grips the tools, as its turn from the CAD model: one claw round the spindle's "
                    "tool, the other round the tool in the tipped pot. Read from the arm's claws when the arm is "
                    "made; type another value if it turns the wrong way")
    arm_stroke: FloatProperty(
        name="Pull-out stroke", unit="LENGTH", default=0.076, min=0.005, soft_max=0.2, update=_cnc_changed,
        description="How far the arm moves down to pull both tools out (and up to push them in). It must clear "
                    "the holder's taper and pull stud: 76 mm for BT30, 95 to 100 mm for BT40 or SK40")
    orient_angle: FloatProperty(
        name="Orient angle", subtype="ANGLE", default=0.0, update=_cnc_changed,
        description="The spindle's angle when it stops for a tool change (M19), so the holder's drive keys line up "
                    "with the arm: 0° = as in the CAD model. Only with a spindle joint")
    arm_grip_time: FloatProperty(
        name="Grip", default=0.3, min=0.02, soft_max=2.0, unit="TIME_ABSOLUTE", update=_cnc_changed,
        description="Seconds the arm takes to turn from rest onto both tools (and back after the change), as on "
                    "the machine. 'ATC speed' in the step makes it faster or slower in the video")
    arm_stroke_time: FloatProperty(
        name="Pull out", default=0.25, min=0.02, soft_max=2.0, unit="TIME_ABSOLUTE", update=_cnc_changed,
        description="Seconds the arm takes to pull both tools out (and to push them in), as on the machine")
    arm_swap_time: FloatProperty(
        name="Half turn", default=0.5, min=0.02, soft_max=3.0, unit="TIME_ABSOLUTE", update=_cnc_changed,
        description="Seconds the arm takes for its 180° turn that swaps the tools, as on the machine")
    pot_tip: BoolProperty(
        name="Pots tip down", default=False, update=_cnc_changed,
        description="Tick when the magazine's pots lie at an angle and the pot at the change station tips down "
                    "so the tool hangs parallel with the spindle. Then press 'Click the hinge'")
    pot_tip_angle: FloatProperty(
        name="Tip angle", subtype="ANGLE", default=math.radians(90.0), min=math.radians(5.0), max=math.radians(180.0),
        update=_cnc_changed,
        description="How far a pot tips down at the change station (usually 90°)")
    pot_tip_sign: FloatProperty(default=1.0)         # which way the pot joints turn to tip down (worked out)
    pot_tip_time: FloatProperty(
        name="Pot tips", default=0.4, min=0.02, soft_max=2.0, unit="TIME_ABSOLUTE", update=_cnc_changed,
        description="Seconds a pot takes to tip down (and up again), as on the machine")

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
# hoses, cables and drag chains (task 0058): parts that bend along with the motion
# ---------------------------------------------------------------------------

def _flex_changed(self, context):
    """A setting of a hose or drag chain changed: its shape is worked out again (also along a built animation)."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import flex
    flex.changed(context.scene, self)


class FRFlex(bpy.types.PropertyGroup):
    """A hose, a cable or a drag chain that follows the motion (task 0058). See blender/flex.py."""
    name: StringProperty(name="Name", description="Name of this hose, cable or drag chain. Double-click to rename it")
    kind: EnumProperty(name="Kind", default="HOSE",
                       items=[("HOSE", "Hose or cable", "One bendable part between two ends"),
                              ("CHAIN", "Drag chain", "An energy chain: two straight runs and a bend that rolls")])
    enabled: BoolProperty(
        name="On", default=True, update=_flex_changed,
        description="On: the part bends along with the motion. Off: it shows stiff, exactly as in the CAD file")
    part: PointerProperty(type=bpy.types.Object)           # the hose part; a chain drawn as one solid: that solid
    part_uid: StringProperty()
    links: CollectionProperty(type=FRObjectRef)            # a chain's CAD link parts, fixed end first
    link_uids: StringProperty()                            # their part IDs, one per line (model update)
    made_links: BoolProperty(default=False)                # the app draws the links (the CAD chain is one solid)
    # the two ends: the part each end sits on, and where on it (in that part's own coordinates). Hose: the point the
    # centreline ends at and the direction the hose runs there (from end A towards end B). Chain: A = the fixed end,
    # B = the moving end (its last pin).
    a_part: PointerProperty(type=bpy.types.Object)
    a_uid: StringProperty()
    a_point: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    a_dir: FloatVectorProperty(size=3, default=(1.0, 0.0, 0.0))
    b_part: PointerProperty(type=bpy.types.Object)
    b_uid: StringProperty()
    b_point: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    b_dir: FloatVectorProperty(size=3, default=(1.0, 0.0, 0.0))
    # chain: its own frame in a_part's coordinates (4 x 4, row by row): origin = the fixed end's pin, x = along the
    # fixed run towards the bend, y = from the fixed run to the moving run, z = across the chain
    frame: FloatVectorProperty(size=16, default=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))
    # ---- hose / cable ----
    length: FloatProperty(
        name="Length", unit="LENGTH", default=0.5, min=0.001, soft_max=20.0, precision=4, update=_flex_changed,
        description="How long the hose is, in mm, measured along its middle. It stays this long while the machine "
                    "moves. 'Fit to the CAD pose' puts back the length drawn in the CAD file")
    cad_length: FloatProperty(default=0.0)
    diameter: FloatProperty(
        name="Diameter", unit="LENGTH", default=0.02, min=0.0005, soft_max=0.5, precision=4, update=_flex_changed,
        description="The outside diameter of the hose, in mm. It is read from the CAD part; change it to draw a "
                    "thicker or thinner hose")
    stiffness: FloatProperty(
        name="Stiffness", default=0.6, min=0.0, max=1.0, subtype="FACTOR", update=_flex_changed,
        description="How stiff the hose is. 0 = a soft cable that hangs down, 1 = a stiff hydraulic hose that "
                    "keeps wide bends. Move it until the hose looks like the real one")
    sag: FloatProperty(
        name="Sag", default=0.5, min=0.0, max=1.0, subtype="FACTOR", update=_flex_changed,
        description="How much the hose hangs down under its own weight. 0 = no weight at all (it only bends), "
                    "1 = a heavy hose. A stiff hose sags less")
    min_radius: FloatProperty(
        name="Smallest bend", unit="LENGTH", default=0.0, min=0.0, soft_max=2.0, precision=4, update=_flex_changed,
        description="The tightest bend the hose may make, as a radius in mm (from the hose maker's data sheet). "
                    "The hose keeps to it where it can; you get a warning when the motion forces a tighter bend. "
                    "0 = no limit")
    # ---- drag chain ----
    pitch: FloatProperty(
        name="Link length", unit="LENGTH", default=0.04, min=0.001, soft_max=0.5, precision=4, update=_flex_changed,
        description="The length of one chain link from pin to pin, in mm. It is read from the CAD links")
    radius: FloatProperty(
        name="Bend radius", unit="LENGTH", default=0.08, min=0.001, soft_max=2.0, precision=4, update=_flex_changed,
        description="The radius of the chain's bend, in mm, measured to the links' pins. It is read from the CAD "
                    "pose; the bend keeps exactly this radius while it rolls")
    count: IntProperty(
        name="Links", default=20, min=2, soft_max=400, update=_flex_changed,
        description="How many links the chain has. Its length is this number times the link length")
    mode: EnumProperty(
        name="Upper run", default="STRAIGHT", update=_flex_changed,
        description="How the run between the bend and the moving end is drawn",
        items=[("STRAIGHT", "Straight", "The run goes straight from the bend to the moving end: a chain that "
                                         "carries itself, hangs, stands or lies on its side"),
               ("GLIDE", "Lies on the lower run", "A long chain: after the bend the run comes down and slides on "
                                                  "the run below it")])
    width: FloatProperty(
        name="Width", unit="LENGTH", default=0.06, min=0.001, soft_max=1.0, precision=4, update=_flex_changed,
        description="The width of the links the app draws, in mm (across the chain)")
    height: FloatProperty(
        name="Height", unit="LENGTH", default=0.025, min=0.001, soft_max=0.5, precision=4, update=_flex_changed,
        description="The height of the links the app draws, in mm (the thickness of one run)")
    # ---- state (written by blender/flex.py) ----
    problem: StringProperty(default="")                    # '' or the warning shown in the panel
    problem_frame: IntProperty(default=0)                  # the first frame it happens at (0 = in the pose shown)
    offset: IntProperty(default=0)                         # its first point in a frame of the shapes mesh
    points: IntProperty(default=0)                         # how many points it has there


# ---------------------------------------------------------------------------
# cables and paths (task 0078): a cable laid over rollers, sheaves and chutes, moved by one cable speed
# ---------------------------------------------------------------------------

def _cable_changed(self, context):
    """A setting of a cable changed: its path, its look and what it turns are brought up to date."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import paths
    paths.changed(context.scene, self)


def _cable_contact_changed(self, context):
    """A setting of one contact changed (turns or not): the cable it belongs to is brought up to date."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import paths
    paths.contact_changed(context.scene, self)


class FRCableContact(bpy.types.PropertyGroup):
    """One thing a cable touches: a sheave, a roller, a chute or a bend. See blender/paths.py."""
    name: StringProperty(name="Name", description="The part the cable touches here")
    kind: EnumProperty(
        name="Kind", default="ROLLER",
        items=[("SHEAVE", "Sheave", "The cable bends round it and turns it"),
               ("ROLLER", "Roller", "The cable rests on it or runs past it and turns it"),
               ("CHUTE", "Chute", "The cable bends round it and slides over it: it does not turn"),
               ("BEND", "Bend", "A bend the cable was drawn with where no single part carries it")])
    part: PointerProperty(type=bpy.types.Object)           # the round part or the chute (none for a bend)
    part_uid: StringProperty()
    carrier: PointerProperty(type=bpy.types.Object)        # centre and axis are in this object's coordinates
    carrier_uid: StringProperty()                          # (a part's ID; '' when the carrier is a joint's arrow)
    centre: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))     # a point on the axis, in the cable's plane
    axis: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))       # unit
    radius: FloatProperty(default=0.1)                     # from the axis to the cable's middle (m)
    surface: FloatProperty(default=0.1)                    # from the axis to the surface the cable lies on (m)
    side: IntProperty(default=1)                           # +1: the cable goes round it turning about +axis; -1: about -axis
    wrap: FloatProperty(default=0.0)                       # rad, as drawn now (written by paths.py)
    wrap_cad: FloatProperty(default=-1.0)                  # rad, in the CAD pose (-1: not known): a lifted wheel and
    #                                                        a loop are measured against it
    gap: FloatProperty(default=0.0)                        # m: how far the CAD cable was drawn off the surface
    s: FloatProperty(default=0.0)                          # m along the cable from its start: where the contact is
    full: BoolProperty(default=True)                       # the part is round all the way (it may turn)
    turns: BoolProperty(
        name="Turns with the cable", default=True, update=_cable_contact_changed,
        description="On: this roller or sheave turns as fast as the cable runs over it. Off: it stands still "
                    "(a fixed guide, a seized roller)")
    joint: StringProperty()                                # the rotate joint that turns it ('' = none)
    made_joint: BoolProperty(default=False)                # the app made that joint (removed with the contact)
    coupled: BoolProperty(default=False)                   # the app made that joint follow the cable
    ratio: FloatProperty(default=0.0)                      # degrees per mm of cable, with its sign
    user: BoolProperty(default=False)                      # added or changed by the user: a new reading keeps it
    note: StringProperty(default="")                       # '' or what the user should know (its own joint, a gap)


class FRCable(bpy.types.PropertyGroup):
    """A cable or wire rope on its path (task 0078). See blender/paths.py."""
    name: StringProperty(name="Name", description="Name of this cable. Double-click to rename it")
    enabled: BoolProperty(
        name="On", default=True, update=_cable_changed,
        description="On: the app draws the cable on its path and it moves with the cable speed. Off: the cable "
                    "shows exactly as in the CAD file and nothing turns with it")
    part: PointerProperty(type=bpy.types.Object)           # the CAD cable (its shape is replaced by the drawn one)
    part_uid: StringProperty()
    joint: StringProperty()                                # the slide joint whose value is the metres paid out
    made_joint: BoolProperty(default=False)                # the app made that joint (removed with the cable)
    diameter: FloatProperty(
        name="Diameter", unit="LENGTH", default=0.05, min=0.001, soft_max=0.6, precision=4, update=_cable_changed,
        description="The outside diameter of the cable, in mm. It is read from the CAD cable; change it to draw a "
                    "thicker or thinner cable (it then lies higher or lower on its rollers)")
    cad_diameter: FloatProperty(default=0.0)
    look: EnumProperty(
        name="Look", default="POWER", update=_cable_changed,
        description="How the cable looks. The pattern runs along with the cable, so you see it move",
        items=[("POWER", "Power cable", "Black with yellow stripes at an angle"),
               ("ROPE", "Steel wire rope", "Twisted steel strands, as on a winch"),
               ("PLAIN", "Plain", "The look the part has in 3 Looks: nothing shows the cable moving")])
    pitch: FloatProperty(
        name="Stripe distance", unit="LENGTH", default=0.5, min=0.005, soft_max=5.0, precision=4,
        update=_cable_changed,
        description="Power cable: the distance from one yellow stripe to the next along the cable, in mm. Steel "
                    "wire rope: the length of one full twist of a strand (about 6 to 7 times the diameter)")
    angle: FloatProperty(
        name="Stripe angle", subtype="ANGLE", default=math.radians(45.0), min=math.radians(5.0),
        max=math.radians(90.0), update=_cable_changed,
        description="The angle between a stripe and the cable. 90° gives rings straight round the cable. The app "
                    "takes the nearest angle that closes up round the cable")
    stripe: FloatProperty(
        name="Stripe width", subtype="FACTOR", default=0.3, min=0.05, max=0.95, update=_cable_changed,
        description="How much of the cable is yellow: 0.3 = stripes a bit under a third of the distance wide")
    mbr: FloatProperty(
        name="Smallest bend", unit="LENGTH", default=0.0, min=0.0, soft_max=10.0, precision=4, update=_cable_changed,
        description="The tightest bend the cable may make (its minimum bend radius, MBR), in mm, measured to the "
                    "middle of the cable. You get a warning naming the sheave or bend that is tighter. 0 = no check")
    still: BoolProperty(
        name="Stays as drawn", default=False, update=_cable_changed,
        description="Off: the cable follows the sheaves and chutes it lies on when they move against each other "
                    "(a sheave on a luffing frame, a chute on a tilting arm). On: it keeps the path it has in the "
                    "CAD pose whatever moves – it still runs and turns its rollers, and costs no time per frame")
    reverse: BoolProperty(
        name="Runs the other way", default=False, update=_cable_changed,
        description="Off: paying out moves the cable from its start to its end. On: from its end to its start. "
                    "Tick it when the rollers and the stripes run the wrong way")
    # the two ends. FIXED: a point on a part (``a_part``, in its coordinates). WHEEL: the cable starts on its first
    # contact (the point is in that contact's carrier's coordinates). A free end is a FIXED point on the last
    # contact's carrier, ``a_free`` metres straight on from where the cable leaves it (0 = as drawn in CAD).
    a_kind: EnumProperty(default="FIXED", items=[("FIXED", "Fixed point", ""), ("WHEEL", "On its first contact", ""),
                                                 ("SPOOL", "Comes off a drum or carousel", "")])     # (task 0080)
    a_part: PointerProperty(type=bpy.types.Object)
    a_uid: StringProperty()
    a_point: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    a_free_end: BoolProperty(default=False)                # a free end: the start touches no part
    a_free: FloatProperty(
        name="Free length at the start", unit="LENGTH", default=0.0, min=0.0, soft_max=100.0, precision=3,
        update=_cable_changed,
        description="How far the cable runs straight on before its first contact, in mm. 0 = as drawn in the CAD "
                    "file")
    b_kind: EnumProperty(default="FIXED", items=[("FIXED", "Fixed point", ""), ("WHEEL", "On its last contact", "")])
    b_part: PointerProperty(type=bpy.types.Object)
    b_uid: StringProperty()
    b_point: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    b_free_end: BoolProperty(default=False)                # a free end: the end touches no part
    b_free: FloatProperty(
        name="Free length at the end", unit="LENGTH", default=0.0, min=0.0, soft_max=100.0, precision=3,
        update=_cable_changed,
        description="How far the cable runs straight on after its last contact, in mm. 0 = as drawn in the CAD "
                    "file")
    contacts: CollectionProperty(type=FRCableContact)      # in order along the cable, from its start
    contacts_index: IntProperty(default=0)
    # ---- state (written by blender/paths.py) ----
    problem: StringProperty(default="")                    # '' or the warning shown in the panel
    problem_frame: IntProperty(default=0)                  # the first frame it happens at (0 = in the pose shown)
    length: FloatProperty(default=0.0)                     # of the drawn path, m
    moving: BoolProperty(default=False)                    # its contacts move against each other: a shape per frame
    shapes: PointerProperty(type=bpy.types.Object)         # the hidden mesh holding its points (frames x points)


# ---------------------------------------------------------------------------
# drums and carousels (task 0080): the cable comes off a spool layer by layer. See blender/spool.py.
# ---------------------------------------------------------------------------

def _spool_changed(self, context):
    """A setting of a drum or carousel changed: its tables, its drawn rope and the cable's start follow."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import spool
    spool.changed(context.scene, self)


class FRSpoolFollower(bpy.types.PropertyGroup):
    """A joint that follows where the cable leaves the spool (a level wind, a loading arm, a guide swivel)."""
    joint: StringProperty(name="Joint", description="The joint that follows the layer")
    mode: EnumProperty(
        name="Follows", default="ACROSS", update=_spool_changed,
        description="How this joint follows where the cable leaves the drum or carousel: along the drum (a level "
                    "wind), an arm swinging over the coil, or a guide turning along the turn",
        items=[("ACROSS", "Across the drum", "A slide along the drum: it keeps in line with the wrap being paid out "
                                             "(a level wind), going back and forth layer by layer"),
               ("ARM", "Arm over the coil", "A turn about an axis beside the spool: the arm swings so its guide stays "
                                            "over the turn being paid out (a loading arm or arch)"),
               ("ALONG", "Along the turn", "A turn about an upright axis at the guide: it keeps the guide lined up "
                                           "with the turn the cable lifts off (a guide's swivel)")])
    point: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))     # ARM: the point kept over the turn (spool frame)
    note: StringProperty(default="")


class FRSpool(bpy.types.PropertyGroup):
    """A drum or carousel the cable comes off (task 0080). See blender/spool.py."""
    name: StringProperty(name="Name", description="Name of this drum or carousel. Double-click to rename it")
    enabled: BoolProperty(
        name="On", default=True, update=_spool_changed,
        description="On: the cable comes off the drum or carousel layer by layer, and the drum or carousel turns "
                    "with the cable speed. Off: the coil shows as in the CAD file and nothing turns with it")
    kind: EnumProperty(name="Kind", default="DRUM",
                       items=[("DRUM", "Drum", "A winch or reel drum: the wraps lie side by side along it"),
                              ("CAROUSEL", "Carousel", "A turntable with a coil: flat layers, one on top of the other")])
    cable: StringProperty(name="Cable", description="The cable that comes off it (4 Motion > Cables and paths)")
    part: PointerProperty(type=bpy.types.Object)           # the part clicked (barrel / turntable)
    part_uid: StringProperty()
    coil: PointerProperty(type=bpy.types.Object)           # the CAD coil or wire on the drum (its shape is replaced)
    coil_uid: StringProperty()
    owner: PointerProperty(type=bpy.types.Object)          # what the rope is drawn on: the coil, or one the app made
    joint: StringProperty()                                # the rotate joint that turns it
    made_joint: BoolProperty(default=False)
    # the spool's numbers in its joint's arrow coordinates (z = the turning axis), metres
    r1: FloatProperty(name="First layer radius", unit="LENGTH", default=0.1, min=0.001, precision=4,
                      update=_spool_changed,
                      description="Drum: from the axis to the middle of the cable on the first layer, in mm. Read "
                                  "from the barrel")
    a_lo: FloatProperty(default=-0.2)
    a_hi: FloatProperty(default=0.2)
    r_max: FloatProperty(default=1.0)
    pitch: FloatProperty(name="Groove pitch", unit="LENGTH", default=0.0, min=0.0, precision=4,
                         update=_spool_changed,
                         description="Drum: the distance from one wrap to the next along the drum, in mm. 0 = the cable's "
                                     "diameter x 1.06 (a usual spiral groove)")
    r_in: FloatProperty(name="Inner radius", unit="LENGTH", default=0.3, min=0.001, precision=4, update=_spool_changed,
                        description="Carousel: from the axis to the middle of the innermost turn, in mm")
    r_out: FloatProperty(name="Outer radius", unit="LENGTH", default=0.8, min=0.001, precision=4,
                         update=_spool_changed,
                         description="Carousel: from the axis to the middle of the outermost turn, in mm")
    a_bot: FloatProperty(default=0.0)
    a_top: FloatProperty(default=1.0)
    other_side: BoolProperty(
        name="First layer from the other side", default=False, update=_spool_changed,
        description="Drum: off = the first layer starts at the flange the arrow points away from, on = at the other "
                    "flange. Carousel: off = the first layer starts at the core, on = at the rim")
    hand: IntProperty(default=1)                           # +1: the wraps turn about +axis from the anchor outwards
    zsign: IntProperty(default=1)                          # -1: the spool frame's z is the joint arrow's -z
    leave: FloatVectorProperty(size=3, default=(1.0, 0.0, 0.0))   # where the CAD cable leaves it (spool frame)
    phase: FloatProperty(default=0.0)                      # rad: the wound path's turn so it leaves where CAD drew it
    wound: FloatProperty(
        name="Wound at the start", default=10.0, min=0.0, soft_max=100000.0, precision=1, step=100,
        update=_spool_changed,
        description="How much cable is on the drum or carousel when the cable speed's joint is at 0, in m. Read from "
                    "where the CAD cable leaves it; type another length to start with more or less")
    wound_user: BoolProperty(default=False)                # typed: a new reading keeps it
    groove: EnumProperty(
        name="Grooves", default="SPIRAL", update=_spool_changed,
        description="How the drum is grooved: Spiral – one helical groove, the wraps side by side; Lebus – parallel "
                    "grooves with two crossovers per turn. The wraps follow the grooves",
        items=[("SPIRAL", "Spiral groove", "One helical groove: each wrap a little further along than the last"),
               ("LEBUS", "Lebus", "Parallel grooves with two crossovers per turn: the wraps step half a groove there")])
    crossover: FloatProperty(name="Crossover", subtype="ANGLE", default=0.6108652, min=0.05, max=1.5,
                             update=_spool_changed,
                             description="Lebus: how much of a turn one crossover takes (usually 30° to 40°)")
    fleet_limit: FloatProperty(
        name="Fleet angle warning", subtype="ANGLE", default=0.02617994, min=0.0, max=0.5, update=_spool_changed,
        description="A warning when the cable runs to its first sheave at more than this angle from square to the "
                    "drum, at either flange (1.5° is a usual limit for grooved drums)")
    followers: CollectionProperty(type=FRSpoolFollower)
    followers_index: IntProperty(default=0)
    q: FloatVectorProperty(size=3, default=(1.0, 0.0, 0.0))  # where the cable runs to from the spool (spool frame,
    #                                                        CAD pose): its first contact's far end, or its end
    q_on: StringProperty(default="")                       # the object that carries that point
    removed: StringProperty(default="")                    # JSON: the cable's contacts on the spool, taken off
    group_was: StringProperty(default="")                  # the coil part's manual group before the look's
    # ---- state (written by blender/spool.py) ----
    problem: StringProperty(default="")
    layer: IntProperty(default=0)                          # the layer the cable leaves from (1 = the first)
    layers: IntProperty(default=0)                         # how many layers it holds
    on_spool: FloatProperty(default=0.0)                   # m on it now
    capacity: FloatProperty(default=0.0)                   # m it holds when full
    fleet_lo: FloatProperty(default=0.0)
    fleet_hi: FloatProperty(default=0.0)


# ---------------------------------------------------------------------------
# tracks and belts (task 0079): a chain of CAD links, pads and plates runs round its wheels. See blender/tracks.py.
# ---------------------------------------------------------------------------

def _track_changed(self, context):
    """A setting of a track changed (on/off, speed, direction): its parts and wheels follow at once."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import tracks
    tracks.changed(context.scene, self)


def _track_joints(self, context, edit_text):
    """The joints a track can run on: slide joints, and the rotate joints of its own wheels."""
    scene = context.scene if context is not None else None
    if scene is None:
        return []
    own = {w.joint for w in self.wheels}
    out = []
    for j in scene.fresing.joints:
        if j.kind == "SLIDE" or j.name in own:
            if not edit_text or edit_text.lower() in j.name.lower():
                out.append(j.name)
    return out


class FRTrackWheel(bpy.types.PropertyGroup):
    """One wheel of a track: a sprocket, idler or roller. See blender/tracks.py."""
    name: StringProperty(name="Name", description="The wheel's part")
    part: PointerProperty(type=bpy.types.Object)
    part_uid: StringProperty()
    joint: StringProperty()                                # the rotate joint that turns it
    made_joint: BoolProperty(default=False)                # the app made that joint (removed with the track)
    coupled: BoolProperty(default=False)                   # the app made that joint follow the track's speed
    radius: FloatProperty(default=0.0)                     # m: the chain's pitch line round it (or to the run it touches)
    side: IntProperty(default=1)                           # +1: inside the loop
    wrapped: BoolProperty(default=True)                    # the chain bends round it (False: it only touches)
    wrap: FloatProperty(default=0.0)                       # rad the chain lies on it
    rate: FloatProperty(default=0.0)                       # rad about the loop's normal per metre of chain
    ratio: FloatProperty(default=0.0)                      # as its coupling has it: ° per mm (or turns per turn)
    note: StringProperty(default="")


class FRTrack(bpy.types.PropertyGroup):
    """A track or belt: a chain of CAD links (with pads, plates) running round its wheels (task 0079)."""
    name: StringProperty(name="Name", description="Name of this track. Double-click to rename it")
    enabled: BoolProperty(
        name="On", default=True, update=_track_changed,
        description="On: the links, pads and plates run round the wheels with the speed joint and the wheels turn "
                    "with them. Off: they show exactly as in the CAD file and stand still")
    joint: StringProperty(
        name="Speed", update=_track_changed, search=_track_joints,
        description="The joint the track runs with: a cable's joint (metres of cable), any slide joint (metres of "
                    "chain) or the joint of one of its own wheels (the chain runs as that wheel turns). Animate that "
                    "joint, for example with a Run motor step in 6 Animation")
    made_joint: BoolProperty(default=False)                # the app made the speed joint (removed with the track)
    flip: FloatProperty(default=1.0)                       # +1 / -1: the way that moves the pads with the cable (found)
    reverse: BoolProperty(
        name="Runs the other way", default=False, update=_track_changed,
        description="Off: the pads on the run nearest the cable move with the cable (or along the slide joint). "
                    "On: the other way round. Tick it when the pads run the wrong way")
    wheels: CollectionProperty(type=FRTrackWheel)
    wheels_index: IntProperty(default=0)
    key: StringProperty()                                  # what its parts and app-made joints are tagged with
    chain_uid: StringProperty()                            # the link that was clicked
    rider_uids: StringProperty()                           # the pads / plates that were clicked, one per line
    # ---- state (written by blender/tracks.py) ----
    carrier: PointerProperty(type=bpy.types.Object)        # the loop's coordinates: the first wheel's joint arrow
    loop: PointerProperty(type=bpy.types.Object)           # the hidden loop table "FR track loop <name>"
    run: PointerProperty(type=bpy.types.Object)            # "FR track run <name>": one point per part, its place now
    normal: FloatVectorProperty(size=3, default=(0.0, 1.0, 0.0))  # the loop's normal, carrier coordinates
    pitch: FloatProperty(default=0.0)                      # m
    links: IntProperty(default=0)
    parts: IntProperty(default=0)                          # links + riders that move
    length: FloatProperty(default=0.0)                     # of the loop in metres of chain
    chain_length: FloatProperty(default=0.0)               # links x pitch
    data: StringProperty(default="")                       # JSON: each part's name, ID, phase c0, local matrix
    problem: StringProperty(default="")
    notes: StringProperty(default="")                      # what Add track had to say, one per line


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
    carriage: BoolProperty(default=False)                  # task 0035: parts of the carriage itself (last section,
    #                                                        share 1, no joint of its own; ``parts`` stay)
    uids: StringProperty()                                 # the carriage parts' IDs, one per line (model update)


class FRWayCover(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Way cover",
                         description="Name of this way cover, for example 'X left' and 'X right'. Double-click to "
                                     "rename it")
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
    drawn_at: FloatProperty(
        name="Drawn at", unit="LENGTH", default=0.0, soft_min=-5.0, soft_max=5.0, update=_waycover_changed,
        description="The axis position the covers were drawn at in the CAD file, in mm (0 = the axis zero). At this "
                    "position every section stays exactly where CAD put it. 'Read from the axis' takes the "
                    "axis' current value")
    flip: BoolProperty(
        name="Flip", default=False, update=_waycover_changed,
        description="The covers open the other way round: use this when they slide against the axis' direction")
    housing_counts: BoolProperty(
        name="Fixed housing counts as a section", default=False, update=_waycover_changed,
        description="Tick this when the first section is the housing on the fixed side (it never moves): the "
                    "others then share the travel in one step less. Off: the sections are the moving covers")


def _clash_row_picked(self, context):
    """Click a row of 6 Animation > Clash check: go to its deepest frame, select both parts, show them red."""
    if self.get("_quiet") or context is None or context.scene is None:
        return
    from . import clash
    clash.show_row(context, context.scene, self.rows_index)


class FRClashRow(bpy.types.PropertyGroup):
    """One clash (or near miss) the clash check found (task 0065)."""
    kind: EnumProperty(items=[("CLASH", "Clash", ""), ("NEAR", "Near miss", "")], default="CLASH")
    part_a: StringProperty()             # object names
    part_b: StringProperty()
    label_a: StringProperty()            # the names as the tree shows them
    label_b: StringProperty()
    frame_from: IntProperty()
    frame_to: IntProperty()
    deep: FloatProperty()                # the moment of the deepest overlap (a frame, maybe between two)
    depth: FloatProperty()               # m inside each other (a near miss: the gap)


class FRClash(bpy.types.PropertyGroup):
    """6 Animation > Clash check (task 0065): settings and the last result (kept with the project)."""
    depth: FloatProperty(
        name="Clash depth", unit="LENGTH", default=0.0005, min=0.00001, soft_max=0.01, precision=2,
        description="Two parts count as a clash when they go further into each other than this. Parts that "
                    "already touch or overlap in the CAD model (a pin in its bore) only count when they go this "
                    "much deeper than at the first frame")
    use_near: BoolProperty(
        name="Warn about near misses", default=False,
        description="Also list parts that come closer than the distance on the right without touching (they were "
                    "further apart at the first frame). Then press Check for clashes again")
    near_distance: FloatProperty(
        name="Closer than", unit="LENGTH", default=0.005, min=0.0001, soft_max=0.05, precision=1,
        description="A near miss: two parts come closer than this without touching. Used when 'Warn about near "
                    "misses' is ticked")
    rows: CollectionProperty(type=FRClashRow)
    rows_index: IntProperty(
        default=-1, update=_clash_row_picked,
        description="Click a row: the time line goes to the moment the two parts are deepest in each other, both "
                    "are selected and shown red, and the view zooms to them")
    checked: BoolProperty(default=False)
    clashes: IntProperty(default=0)      # all clashes found (the list keeps the first 200)
    near_misses: IntProperty(default=0)
    anim: StringProperty()               # the animation that was checked
    signature: StringProperty()          # fingerprint of its built keys (clash.build_signature)
    seconds: FloatProperty()             # how long the check took
    moments: IntProperty()               # frames and moments between frames looked at


def _vessel_changed(self, context):
    """5 Scene & Render > Vessel motion (task 0085): the rig follows (cheap when nothing changed)."""
    if context is None or context.scene is None:
        return
    from . import vessel_motion
    try:
        vessel_motion.changed(context.scene)
    except Exception as exc:                 # never break the UI over a preview update
        print("Fresing Render: vessel motion update failed:", exc)


def _vessel_sea_changed(self, context):
    """On/off and the heading change the swell: the sea is built again (then the rig follows)."""
    if context is None or context.scene is None:
        return
    from . import vessel_motion
    try:
        vessel_motion.changed(context.scene, sea=True)
    except Exception as exc:
        print("Fresing Render: vessel motion update failed:", exc)


class FRVesselStill(bpy.types.PropertyGroup):
    """A subassembly that keeps its place while the vessel moves (task 0085)."""
    uid: StringProperty()                # part ID (stays right through a model update)
    label: StringProperty()              # its name, as the tree shows it
    mode: EnumProperty(
        name="Keeps", default="STILL", update=_vessel_changed,
        description="How this subassembly keeps its place while the vessel moves",
        items=[("STILL", "Still", "Stays where it is in the world: no heave, pitch or roll (a motion-compensated "
                                  "gangway, or a hook that holds its place)"),
               ("LEVEL", "Level", "Stays level: roll and pitch are taken out, it still rises and falls with the "
                                  "vessel")])


class FRVessel(bpy.types.PropertyGroup):
    """5 Scene & Render > Vessel motion (task 0085): the model and the deck move with the sea."""
    enabled: BoolProperty(
        name="Vessel motion", default=False, update=_vessel_sea_changed,
        description="The machine, the vessel deck and the props heave, pitch and roll gently with the sea, while "
                    "the sea, the sky and the camera stay put. Play the time line to see it. Works with the Open sea "
                    "and the Vessel deck")
    strength: FloatProperty(
        name="Strength", default=100.0, min=0.0, max=200.0, subtype="PERCENTAGE", precision=0,
        update=_vessel_changed,
        description="How much the vessel moves: 100% is the sea state's own motion, 0% holds it still, 200% "
                    "doubles it")
    heading: EnumProperty(
        name="Heading", default="BOW", update=_vessel_sea_changed,
        description="Where the waves come from, seen from the vessel. Beam seas roll it the most, head and "
                    "following seas make it pitch",
        items=[(k, v[0], v[2]) for k, v in vessel_core.HEADINGS.items()])
    auto_size: BoolProperty(
        name="Size from the model", default=True, update=_vessel_changed,
        description="On: the vessel's length and beam come from the Vessel deck (or, on the Open sea, from the "
                    "model's size). Off: type them in. A long vessel ignores short waves")
    length: FloatProperty(
        name="Length", default=124.0, min=5.0, soft_max=300.0, unit="LENGTH", precision=0, update=_vessel_changed,
        description="Length of the vessel, bow to stern. Used when 'Size from the model' is off")
    beam: FloatProperty(
        name="Beam", default=28.0, min=2.0, soft_max=60.0, unit="LENGTH", precision=0, update=_vessel_changed,
        description="Width of the vessel. Used when 'Size from the model' is off")
    roll_period: FloatProperty(
        name="Roll period", default=11.0, min=5.0, max=25.0, precision=1, update=_vessel_changed,
        description="Seconds the vessel takes to roll from one side to the other and back. Most work vessels: "
                    "10 to 12 s. A longer period rolls slower")
    pivot_mode: EnumProperty(
        name="Turns about", default="AUTO", update=_vessel_changed,
        description="The point the vessel turns about",
        items=[("AUTO", "Auto", "At the waterline under the middle of the vessel (on the Open sea: under the "
                                "middle of the model)"),
               ("PICK", "Picked point", "A point you clicked with 'Pick'")])
    pivot: FloatVectorProperty(name="Pivot", size=3, unit="LENGTH", default=(0.0, 0.0, 0.0), update=_vessel_changed,
                               description="The point the vessel turns about (picked in the view)")
    still: CollectionProperty(type=FRVesselStill)
    still_index: IntProperty(default=0, description="Subassemblies that keep their place while the vessel moves")


_TP_TOOL_ITEMS = []                      # kept: Blender needs the strings of dynamic items to stay alive


def _toolpath_tool_items(self, context):
    """The tool list's rows a toolpath can be made with (task 0029), as menu items; '0' = none."""
    from ..core import toolpath as tp_core
    out = [("0", "None", "No tool: this pass is left out", 0)]
    scene = getattr(context, "scene", None) if context is not None else None
    rows = list(scene.fresing.cnc.tools) if scene is not None and hasattr(scene, "fresing") else []
    seen = set()
    for r in rows:
        if r.number <= 0 or r.number in seen or r.kind not in tp_core.KINDS:
            continue
        seen.add(r.number)
        d = r.diameter * 1000
        kind = {"FLAT": "flat", "BALL": "ball", "BULL": "bull-nose", "FACE": "face mill"}[r.kind]
        text = f"T{r.number} {r.name or ''}".strip() if r.name else f"T{r.number} Ø{d:g} {kind}"
        out.append((str(r.number), text, f"T{r.number}: {kind} Ø{d:g} mm", r.number))
    _TP_TOOL_ITEMS[:] = out
    return _TP_TOOL_ITEMS


class FRToolpath(bpy.types.PropertyGroup):
    """4 Motion > Milling > Make a toolpath (task 0029): the settings and the last result."""
    rough_tool: EnumProperty(
        name="Roughing tool", items=_toolpath_tool_items,
        description="The tool that takes most of the block away, level by level (a flat or bull-nose end mill, or a "
                    "face mill). Pick it from the tool list (4 Motion > CNC machine > Tools). None: no roughing")
    finish_tool: EnumProperty(
        name="Finishing tool", items=_toolpath_tool_items,
        description="The tool that cuts the part to size in parallel lines over its whole top (a ball or bull-nose "
                    "end mill gives smooth slopes and domes; a flat end mill flat faces). None: no finishing")
    leave: FloatProperty(
        name="Leave stock", unit="LENGTH", default=0.0003, min=0.0, soft_max=0.003, precision=2,
        description="How much material roughing leaves on the part for the finishing tool to take off")
    step_down: FloatProperty(
        name="Step-down", unit="LENGTH", default=0.003, min=0.0001, soft_max=0.02, precision=1,
        description="How deep the roughing tool cuts in one level. The flat faces of the part get a level of "
                    "their own, so pocket floors and the tops of bosses are roughed evenly")
    stepover: FloatProperty(
        name="Stepover", subtype="PERCENTAGE", default=50.0, min=5.0, max=95.0,
        description="Roughing: how far apart the lines are, as a share of the tool's diameter. A flat finishing "
                    "tool uses it too")
    scallop: FloatProperty(
        name="Scallop height", unit="LENGTH", default=0.00001, min=0.000001, soft_max=0.0005, precision=3,
        description="Finishing with a ball or bull-nose end mill: how high the ridges between two lines may be. "
                    "The lines are set this close together. Smaller is smoother and takes longer")
    angle: FloatProperty(
        name="Pass direction", subtype="ANGLE", default=0.0, min=-math.pi, max=math.pi,
        description="The direction of the lines, from the program's +X axis (0° = along X, 90° = along Y)")
    detail: EnumProperty(
        name="Detail", default="NORMAL",
        description="How closely the finishing lines follow the part. Fewer moves cut faster in the view; the "
                    "tool never goes into the part at any of them",
        items=[("DRAFT", "Draft", "Quickest: finishing lines at least as far apart as a 0.04 mm scallop, points 0.5 mm "
                                  "apart along them, kept within 0.05 mm"),
               ("NORMAL", "Normal", "Points 0.25 mm apart along the finishing lines, kept within 0.03 mm"),
               ("FINE", "Fine", "Points 0.12 mm apart along the finishing lines, kept within 0.01 mm: smoothest, most "
                                "moves")])
    material: EnumProperty(
        name="Stock material", default="AUTO",
        description="Sets the spindle speeds and feeds when they are left at 0",
        items=[("AUTO", "From the stock", "Read from the stock's material in 3 Looks and its name"),
               ("ALU", "Aluminium", "300 m/min, a chip of 0.6 % of the diameter per tooth"),
               ("STEEL", "Steel", "120 m/min, a chip of 0.4 % of the diameter per tooth"),
               ("POM", "POM / plastic", "250 m/min, a chip of 0.8 % of the diameter per tooth")])
    rough_rpm: FloatProperty(
        name="Roughing speed (rpm)", default=0.0, min=0.0, soft_max=40000.0, precision=0, step=10000,
        description="Spindle speed of the roughing tool in turns per minute. 0: worked out from the stock material "
                    "and the tool's diameter")
    rough_feed: FloatProperty(
        name="Roughing feed (mm/min)", default=0.0, min=0.0, soft_max=20000.0, precision=0, step=10000,
        description="Feed of the roughing tool in mm per minute (ramps go at half of it). 0: worked out from the "
                    "speed, the flutes and the stock material")
    finish_rpm: FloatProperty(
        name="Finishing speed (rpm)", default=0.0, min=0.0, soft_max=40000.0, precision=0, step=10000,
        description="Spindle speed of the finishing tool in turns per minute. 0: worked out")
    finish_feed: FloatProperty(
        name="Finishing feed (mm/min)", default=0.0, min=0.0, soft_max=20000.0, precision=0, step=10000,
        description="Feed of the finishing tool in mm per minute. 0: worked out")
    coolant: EnumProperty(
        name="Coolant", default="FLOOD",
        description="What the program switches on while the tools cut. The coolant and air blast settings of 4 "
                    "Motion > CNC machine show it",
        items=[("NONE", "None", "No coolant code in the program"),
               ("FLOOD", "Flood (M8)", "M8: coolant floods the tool"),
               ("MIST", "Mist (M7)", "M7: a mist of coolant"),
               ("AIR", "Air blast", "The air-on code set in 4 Motion > CNC machine > Air blast")])
    # the last result (shown in the panel)
    result: StringProperty()             # JSON: moves, lengths, times, undercut …
    program_sig: StringProperty()        # fingerprint of the program as written: an edit by hand is noticed


# ---- cutaway / section view (task 0086) ----

def _cut_changed(self, context):
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import section
    section.changed(context.scene, self)


def _cut_renamed(self, context):
    """The cut's slide joint takes the same name (steps and poses follow the joint's own rename)."""
    if context is None or context.scene is None or self.get("_busy"):
        return
    from . import section
    j = section.joint_of(context.scene, self)
    if j is not None and self.name and j.name != self.name and context.scene.fresing.joints.get(self.name) is None:
        j.name = self.name
    if j is not None:
        self["joint"] = j.name


def _cut_place_get(self):
    from . import section
    return section.get_place(self)[0]


def _cut_place_set(self, value):
    from . import section
    section.set_place(bpy.context.scene, self, location=tuple(value))


def _cut_turn_get(self):
    from . import section
    return section.get_place(self)[1]


def _cut_turn_set(self, value):
    from . import section
    section.set_place(bpy.context.scene, self, rotation=tuple(value))


class FRCutTarget(bpy.types.PropertyGroup):
    """What a cut cuts: the whole model, a subassembly or part, or a material group (task 0086)."""
    kind: EnumProperty(items=[("MODEL", "Whole model", ""), ("PART", "Subassembly or part", ""),
                              ("GROUP", "Group", "")], default="PART")
    name: StringProperty()
    obj: PointerProperty(type=bpy.types.Object)
    uid: StringProperty()


class FRCut(bpy.types.PropertyGroup):
    """A cutaway: a plane or box that takes part of the chosen parts away; the cut faces show a cap colour."""
    name: StringProperty(name="Name", update=_cut_renamed,
                         description="The cut's name. Its slide joint (to move it in a Move joint step) has the same "
                                     "name")
    key: StringProperty()
    enabled: BoolProperty(name="On", default=True, update=_cut_changed,
                          description="Switches this cut on or off. Off: the parts look whole again (in the view, "
                                      "pictures and videos)")
    shape_kind: EnumProperty(name="Shape", default="PLANE", update=_cut_changed,
                             description="A plane takes away one side of the parts; a box takes away what is inside "
                                         "it (a corner or a quarter)",
                             items=[("PLANE", "Plane", "Takes away the side the arrow points to (Flip: the other side)",
                                     "MESH_PLANE", 0),
                                    ("BOX", "Box", "Takes away what is inside the box (Flip: everything outside it)",
                                     "MESH_CUBE", 1)])
    flip: BoolProperty(name="Flip", default=False, update=_cut_changed,
                       description="Takes away the other side: for a plane the side behind the arrow, for a box "
                                   "everything outside it")
    color: FloatVectorProperty(name="Cap colour", subtype="COLOR", size=3, min=0.0, max=1.0,
                               default=(0.62, 0.012, 0.012), update=_cut_changed,
                               description="The colour of the cut faces (where the material was cut through)")
    hatch: BoolProperty(name="Hatch lines", default=False, update=_cut_changed,
                        description="Draws diagonal lines on the cut faces, as on a section drawing")
    hatch_spacing: FloatProperty(name="Line spacing", unit="LENGTH", default=0.01, min=0.0005, soft_max=0.1,
                                 update=_cut_changed, description="The distance between the hatch lines, in mm")
    size: FloatVectorProperty(name="Box size", subtype="XYZ", unit="LENGTH", size=3, min=0.001,
                              default=(1.0, 1.0, 1.0), update=_cut_changed,
                              description="Length, width and height of the box, in mm (along its own X, Y and Z)")
    plane_size: FloatProperty(name="Plane size", unit="LENGTH", default=1.0, min=0.001, update=_cut_changed,
                              description="How big the plane is drawn in the view (it always cuts through "
                                          "everything)")
    place: FloatVectorProperty(name="Position", subtype="TRANSLATION", unit="LENGTH", size=3,
                               get=_cut_place_get, set=_cut_place_set,
                               description="Where the cut's handle (the arrow) is, in the model's coordinates (mm). "
                                           "You can also move the arrow in the view (G)")
    turn: FloatVectorProperty(name="Turn", subtype="EULER", unit="ROTATION", size=3,
                              get=_cut_turn_get, set=_cut_turn_set,
                              description="How the cut is turned about the model's X, Y and Z axes (degrees). You "
                                          "can also turn the arrow in the view (R)")
    targets: CollectionProperty(type=FRCutTarget)
    shape: PointerProperty(type=bpy.types.Object)
    joint: StringProperty()
    root_uid: StringProperty()


def _web3d_env_mode(self, context):
    """Surroundings switched on: the ticks start from the project (task 0106)."""
    if self.env_mode == "PROJECT" and context is not None and context.scene is not None:
        from . import web3d_env
        web3d_env.fill_from_project(context.scene)


class FRWeb3D(bpy.types.PropertyGroup):
    """Web 3D model (task 0099): settings of 5 Scene & Render > Web 3D model and the last export."""

    texture_size: EnumProperty(
        name="Texture size", default="1024",
        description="Sharpness of the baked looks: pixels per 20 cm tile of each look. Bigger is sharper close up "
                    "but makes the file bigger and the export slower",
        items=[("512", "512", "Small file, for phones and e-mail"),
               ("1024", "1024", "Sharp enough for most screens (the default)"),
               ("2048", "2048", "Sharpest close up; bigger file and slower export")])
    hide_names: BoolProperty(
        name="Hide part names", default=True,
        description="On: the parts are called Part 1, Part 2 … in the file, so a customer does not see your part "
                    "numbers. Off: the parts keep the names they have in the app")
    animation: BoolProperty(
        name="Include animation", default=False,
        description="Puts the motion of the built animation into the file: the page plays it in a loop. Only "
                    "parts that move as a whole (no milling, chips, coolant or hoses). Makes the export slower")
    compress: BoolProperty(
        name="Smaller file", default=True,
        description="Compresses a big model (200,000 triangles or more) with meshopt: about half the file; its "
                    "page opens it as before, offline too. Some older 3D viewers cannot open such a .glb on its own "
                    "(Blender 5.2, Chrome, Edge, Firefox and Safari can). Off: the plain file, about twice as big")
    # ---- baked light (task 0107): a choice per export; the names are fixed (the house format uses them)
    light: EnumProperty(
        name="Light", default="LIVE",
        description="How the light gets onto the parts in the web model. Live only: the page lights them itself "
                    "(smallest file, fastest export). Soft light baked: shadows from the sky, light in corners and "
                    "bounce light come from a Cycles bake; the sun stays live. Everything baked: the sun's shadows "
                    "too, closest to a render, but they do not move with the parts",
        items=[("LIVE", "Live only", "The page lights the parts itself, as before: smallest file, fastest export"),
               ("SOFT", "Soft light baked, sun live",
                "Shadows from the sky, light in corners and bounce light are baked with Cycles; the sun's sharp "
                "shadows stay live and move with the parts, the vessel and the sea. The choice for animations"),
               ("ALL", "Everything baked",
                "The sun's shadows are baked too: closest to the render, but right only for a machine that stands "
                "still – baked shadows do not move with the parts")])
    light_quality: EnumProperty(
        name="Bake quality", default="NORMAL",
        description="How fine and how clean the baked light is. Draft is quick for a first look; Fine takes about "
                    "four times as long as Normal",
        items=[("DRAFT", "Draft", "16 samples, about 1 million light points: quick, a little blotchy"),
               ("NORMAL", "Normal", "64 samples, about 4 million light points: clean on most screens"),
               ("FINE", "Fine", "256 samples, about 16 million light points: sharpest shadows, slow")])
    light_texels: FloatProperty(
        name="Light points per metre", default=0.0, min=0.0, max=400.0, soft_max=200.0, precision=0,
        description="How many baked light points per metre of surface. 0 = Auto: worked out from the bake quality "
                    "and the size of the model. More gives sharper shadow edges but a bigger file and a longer bake")
    # ---- surroundings on the page (task 0106): set for one export, the project itself never changes
    env_mode: EnumProperty(
        name="Surroundings", default="NONE", update=_web3d_env_mode,
        description="What the page shows around the machine. None: the machine alone on a light background (as "
                    "before). As in the project: the sea, the sky, the light and the weather; the ticks below start "
                    "from the project and change only this export",
        items=[("NONE", "None", "The machine alone, as before: the smallest page"),
               ("PROJECT", "As in the project", "The surroundings the ticks below pick, starting from the project's")])
    env_sea: BoolProperty(
        name="Sea", default=False,
        description="An endless moving sea to the horizon with the app's own waves, the water at the project's "
                    "level. Without a sea in the project it goes under the model at its water level")
    env_sea_state: EnumProperty(
        name="Sea state", default="CALM",
        description="How rough the sea on the page is. Starts as the project's",
        items=[("CALM", "Calm", "A gentle swell and small ripples"),
               ("ROUGH", "Rough", "Higher waves, more ripples and white caps")])
    env_vessel: BoolProperty(
        name="Vessel motion", default=False,
        description="The model (and the vessel deck) heave, pitch and roll on the page with the app's numbers, in "
                    "step with the waves; Still and Level parts stay as in the app. Only when the project has "
                    "vessel motion on and the page has a sea")
    env_sky: BoolProperty(
        name="Sky", default=True,
        description="The page's background and light from the project's sky, 360° photo or studio look, so metal "
                    "mirrors what the app shows. Off: a plain light background with the app's soft studio light")
    env_sky_source: EnumProperty(
        name="Sky from", default="PROJECT",
        description="Where the sky on the page comes from",
        items=[("PROJECT", "The project", "The project's sky and sun, or its 360° photo or studio look"),
               ("TIME", "Time of day", "A sky with the sun at the height and direction set below")])
    env_sun_height: FloatProperty(
        name="Sun height", default=45.0, min=0.0, max=90.0,
        description="Height of the sun above the horizon on the page (degrees): low gives long shadows and warm "
                    "light at sunrise or sunset, 90 is noon in the tropics")
    env_sun_direction: FloatProperty(
        name="Sun direction", default=0.0, min=0.0, max=360.0,
        description="Where the sun stands round the machine (degrees, as Rotate light in 5 Scene & Render): turn it "
                    "to move the shadows")
    env_clouds: EnumProperty(
        name="Clouds", default="NONE",
        description="Clouds in the page's sky. They drift slowly",
        items=[("NONE", "None", "A clear sky"),
               ("SOME", "Some", "Scattered clouds; the sun still shines"),
               ("OVERCAST", "Overcast", "A grey sky: soft light, faint shadows")])
    env_haze: BoolProperty(
        name="Haze", default=False,
        description="The distance fades into a colour that matches the sky, as on a hazy or misty day")
    env_haze_strength: FloatProperty(
        name="Haze strength", default=30.0, min=0.0, max=100.0, subtype="PERCENTAGE", precision=0,
        description="How thick the haze is: low only softens the horizon, 100 % hides what is a few model sizes away")
    env_rain: BoolProperty(
        name="Rain and spray", default=False,
        description="Falling rain and a wet look of the machine; on a rough sea also spray at the bow when it dips "
                    "into a wave. The drops move on the graphics card, so they cost little")
    env_rain_strength: FloatProperty(
        name="Rain strength", default=50.0, min=0.0, max=100.0, subtype="PERCENTAGE", precision=0,
        description="How hard it rains: more drops and a wetter look")
    env_shadows: BoolProperty(
        name="Live sun shadows", default=True,
        description="The sun casts sharp shadows on the model, the deck and the sea that move with the parts and the "
                    "rolling vessel. Off: a little faster on old phones")
    env_quality: EnumProperty(
        name="Page quality", default="BALANCED",
        description="How much the page draws: the wave grid, ripple detail, rain drops, the sharpness of the shadows, "
                    "the size of the sky picture and the screen resolution",
        items=[("PHONE", "Phone", "Light: smooth on phones and old laptops; the smallest sky picture"),
               ("BALANCED", "Balanced", "Good on most laptops and PCs (the default)"),
               ("BEST", "Best", "The finest waves, shadows and sky for a big screen with a good graphics card; the "
                                "biggest sky picture")])
    env_auto: BoolProperty(
        name="Auto", default=True,
        description="The page lowers its quality by itself when it cannot draw about 30 pictures a second, and says "
                    "so in a small note in its corner: one page works on a phone and on a PC")
    last_path: StringProperty(default="")
    last_html: StringProperty(default="")
    last_text: StringProperty(default="")
    last_size: IntProperty(default=0)


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

    # ---- one-click product video (task 0101) ----
    pv_seconds: EnumProperty(
        name="Length", default="60",
        items=[("30", "About 30 s", "A short video: one turn, a few motions, a quick take-apart"),
               ("60", "About 60 s", "A full first video"), ("90", "About 90 s", "A long video with time for each piece")],
        description="About how long the video is, cards included. The steps share the time between them")
    pv_sub: EnumProperty(
        name="Take apart", default="AUTO",
        items=[("AUTO", "The biggest subassembly", "The subassembly with the most parts (at least 5) that is not "
                                                   "the whole model"),
               ("SELECTED", "The selected one", "The subassembly selected in the structure list (3 Structure)"),
               ("NONE", "None", "No take-apart in the video")],
        description="Which subassembly flies apart and together again in the video")
    pv_motions: IntProperty(
        name="Motions", default=3, min=0, max=8,
        description="How many of the machine's motions to show: the joints with the longest travel first (each goes "
                    "to its far limit and back), then the saved poses. 0 = none")
    pv_title_on: BoolProperty(name="Title card", default=True,
                              description="Starts the video with a title card in the brand kit's colours (3 s)")
    pv_end_on: BoolProperty(name="End card", default=True,
                            description="Ends the video with the brand kit's end card (3 s)")
    pv_title: StringProperty(name="Title", description="The big text on the title card. Empty: the project's name")
    pv_captions: BoolProperty(name="Captions", default=False,
                              description="Shows the name of each step as a caption while it plays")

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
    # ---- X-ray look and trail lines (task 0073) ----
    xray_color: FloatVectorProperty(name="X-ray colour", subtype="COLOR", size=3, min=0.0, max=1.0,
                                    default=(0.35, 0.65, 1.0), update=_xray_style,
                                    description="The colour of the X-ray look (every X-ray part follows it)")
    xray_strength: FloatProperty(name="Strength", default=0.7, min=0.0, max=1.0, subtype="FACTOR",
                                 update=_xray_style,
                                 description="How strongly the X-ray look shows: 0 = almost invisible, 1 = clearly "
                                             "drawn edges and a coloured haze")
    trails: CollectionProperty(type=FRTrail)
    trails_index: IntProperty(default=0)
    # ---- cutaway / section view (task 0086) ----
    cuts: CollectionProperty(type=FRCut)
    cuts_index: IntProperty(default=0)
    cut_new_shape: EnumProperty(name="Shape", default="PLANE",
                                description="The shape of the next cut you add",
                                items=[("PLANE", "Plane", "Cuts the parts in two and takes away the half facing "
                                        "you", "MESH_PLANE", 0),
                                       ("BOX", "Box", "Takes away the quarter of the parts that faces you",
                                        "MESH_CUBE", 1)])
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
    queue_delay_mode: EnumProperty(
        name="Start", default="IN",
        description="When the queue starts by itself: a number of hours and minutes from now, or at a clock time",
        items=[("IN", "In …", "Starts after the hours and minutes you set"),
               ("AT", "At …", "Starts at the clock time you set, today or tomorrow")])
    queue_delay_hours: IntProperty(name="Hours", default=1, min=0, max=12,
                                   description="Hours to wait before the queue starts (0–12)")
    queue_delay_minutes: IntProperty(name="Minutes", default=0, min=0, max=59,
                                     description="Minutes to wait before the queue starts (0–59)")
    queue_at_hour: IntProperty(name="Hour", default=18, min=0, max=23,
                               description="Hour of the clock time the queue starts (0–23)")
    queue_at_minute: IntProperty(name="Minute", default=0, min=0, max=59,
                                 description="Minute of the clock time the queue starts (0–59)")

    # ---- model update report ----
    report_new: CollectionProperty(type=FRReportLine)
    report_missing: CollectionProperty(type=FRReportLine)
    report_notes: CollectionProperty(type=FRReportLine)
    report_title: StringProperty()

    # ---- milling (task 0027) ----
    milling: PointerProperty(type=FRMilling)
    # ---- CNC machine for G-code programs (task 0026) ----
    cnc: PointerProperty(type=FRCnc)
    # ---- coolant (task 0042) ----
    coolant: PointerProperty(type=FRCoolant)

    # ---- way covers (task 0034) ----
    waycover: PointerProperty(type=FRWayCover)           # one cover per project (0.2.28 …): moved into the list on load
    waycovers: CollectionProperty(type=FRWayCover)       # task 0035: several covers (one each side, several axes)
    waycovers_index: IntProperty(default=0)
    # ---- clash check (task 0065) ----
    clash: PointerProperty(type=FRClash)
    # ---- the app makes the toolpath (task 0029) ----
    toolpath: PointerProperty(type=FRToolpath)
    # ---- vessel motion at sea (task 0085) ----
    vessel: PointerProperty(type=FRVessel)
    # ---- hoses, cables and drag chains (task 0058) ----
    flex: CollectionProperty(type=FRFlex)
    flex_index: IntProperty(default=0)
    # ---- cables and paths (task 0078) ----
    cables: CollectionProperty(type=FRCable)
    cables_index: IntProperty(default=0)
    spools: CollectionProperty(type=FRSpool)               # drums and carousels the cables come off (task 0080)
    spools_index: IntProperty(default=0)
    # ---- tracks and belts (task 0079) ----
    tracks: CollectionProperty(type=FRTrack)
    tracks_index: IntProperty(default=0)
    cable_speed: StringProperty(
        name="Speed from joint", default="",
        description="Add cable gives the new cable this slide joint as its speed (its value is the metres of cable "
                    "paid out), for example a joint that already turns rollers. Empty: the app makes a new joint")
    # ---- web 3D model (task 0099) ----
    web3d: PointerProperty(type=FRWeb3D)

    last_message: StringProperty(default="")
    # cached so panels and sliders don't scan thousands of objects on every redraw
    model_count: IntProperty(default=0)
    bounds_valid: BoolProperty(default=False)
    bounds_min: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0))
    bounds_max: FloatVectorProperty(size=3, default=(1.0, 1.0, 1.0))


CLASSES = (FRMaterialGroup, FRSchemeLook, FRScheme, FRRule, FRGroupAlias, FRTreeItem, FRFoundPart,
           FRObjectRef, FRJoint, FRPoseJoint, FRPlace, FRPose, FRCylinder, FRMechLink, FRMechanism, FRUid, FRVisSet,
           FRShot, FRPictureCard, FRCallout, FRTrail, FRCamPathPoint, FRAnimBlock,
           FRAnimation, FRQueueJob, FRReportLine, FRMillBit, FRMilling, FRWayCoverSection, FRWayCover, FRCncTool,
           FRCncPocket, FRCoolantNozzle, FRCoolant, FRCnc, FRClashRow, FRClash, FRToolpath, FRVesselStill, FRVessel, FRWeb3D,
           FRCutTarget, FRCut, FRFlex, FRCableContact, FRCable, FRSpoolFollower, FRSpool,
           FRTrackWheel, FRTrack,
           FRSceneSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing = PointerProperty(type=FRSceneSettings)


def unregister():
    del bpy.types.Scene.fresing
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
