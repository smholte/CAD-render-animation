"""Props for scale in detail (task 0155): meshes with two levels of detail, their materials, the person's settings.

The shapes come from ``core/props_detail.py``. Each prop is ONE object with ONE mesh holding both levels: the face
attribute ``fr_lod`` is 1 on the detailed faces and 2 on the light ones. A Geometry Nodes modifier "FR prop detail"
deletes one of the two: by the distance from the active camera ("Auto": light beyond the scene's ``props_far``) or as
the scene's ``props_detail`` says. Nothing runs in Python while playing or rendering (no handler, no driver).

A person's pose, height, clothes, helmet, gloves and look are its object's ``fresing_person`` settings; changing one
builds its mesh again in place. Props of older projects (no ``fr_prop_ver`` or an older one) get the new mesh when
the project opens (``upgrade``): the object, its name, place, turn and scale stay.
"""

from __future__ import annotations

import bpy
import numpy as np

from ..core import props_detail as P
from ..core import surroundings as S
from . import surroundings as sur

VERSION = 1                       # fr_prop_ver: 1 = task 0155 (two levels of detail)
VER_KEY = "fr_prop_ver"
LOD_ATTR = "fr_lod"
GROUP = "FR prop detail"
GROUP_VERSION = 1
MODIFIER = "FR prop detail"
MAT_PREFIX = "FR_prop "
MAT_VERSION = 1
MODES = {"AUTO": 0, "DETAILED": 1, "LIGHT": 2}

# keys that keep the surroundings' own material
_SURROUNDINGS_KEYS = {"galvanized", "container_frame", "wood", "cardboard", "rubber", "barrier_frame", "barrier",
                      "wrap", "container_blue"}


# =============================================================================
# the mesh
# =============================================================================


def person_settings(ob) -> dict:
    """The person's settings as ``core/props_detail.person`` takes them (defaults for a prop without settings)."""
    out = dict(P.PERSON_DEFAULTS)
    st = getattr(ob, "fresing_person", None) if ob is not None else None
    if st is not None:
        out.update(height=float(st.height), pose=st.pose, outfit=st.outfit, helmet=bool(st.helmet),
                   gloves=bool(st.gloves), look=int(st.look))
    return out


def make_mesh(kind: str, name: str, settings: dict | None = None) -> bpy.types.Mesh:
    """Both levels of detail of a prop in one mesh (face attribute ``fr_lod``: 1 detailed, 2 light)."""
    settings = settings or {}
    levels = [(1, S.prop_shapes(kind, P.DETAILED, **settings)), (2, S.prop_shapes(kind, P.LIGHT, **settings))]
    keys = sorted({sh.mat for _lv, shapes in levels for sh in shapes})
    index = {k: i for i, k in enumerate(keys)}
    m = sur._Mesh()
    lods = []
    for lv, shapes in levels:
        before = len(m.faces)
        for sh in shapes:
            m.shape(sh, index[sh.mat])
        lods += [lv] * (len(m.faces) - before)
    me = m.to_mesh(name)
    att = me.attributes.new(LOD_ATTR, "INT", "FACE")
    att.data.foreach_set("value", np.asarray(lods, dtype=np.int32))
    for k in keys:
        me.materials.append(material(k))
    return me


def triangles(kind: str, lod: str, settings: dict | None = None) -> int:
    """How many triangles one level of a prop has (for the report and the tests; no Blender data made)."""
    m = sur._Mesh()
    for sh in S.prop_shapes(kind, lod, **(settings or {})):
        m.shape(sh, 0)
    return int(sum(len(f) - 2 for f in m.faces))


def rebuild(ob) -> None:
    """Build a prop's mesh again (new look, the person's new settings); the object keeps its name and place."""
    kind = ob.get(sur.PROP_TAG)
    if kind not in S.PROPS:
        return
    if kind == "PERSON" and ob.get("fr_rigged"):
        from . import person_rig                # task 0157: a person with a rig keeps it (pose on its bones)
        if person_rig.rig_of(ob) is not None:
            person_rig.rebuild(ob)
            return
    old = ob.data
    settings = person_settings(ob) if kind == "PERSON" else {}
    name = old.name if old is not None else S.PROPS[kind][0]
    if old is not None:
        old.name = name + " (old)"               # the new mesh keeps the name
    ob.data = make_mesh(kind, name, settings)
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    ensure_modifier(ob)
    ob[VER_KEY] = VERSION


def ensure_modifier(ob, scene=None) -> None:
    mod = ob.modifiers.get(MODIFIER)
    if mod is None:
        mod = ob.modifiers.new(MODIFIER, "NODES")
    ng = node_group()
    if mod.node_group is not ng:
        mod.node_group = ng
    s = (scene or bpy.context.scene).fresing if (scene or bpy.context.scene) is not None else None
    if s is not None:
        _set(mod, ng, "Mode", MODES.get(s.props_detail, 0))
        _set(mod, ng, "Distance", float(s.props_far))


def apply_detail(scene) -> None:
    """The scene's detail setting went to every prop's modifier."""
    for ob in sur.props(scene):
        ensure_modifier(ob, scene)


def upgrade(scene) -> int:
    """Props of an older project get the new look (task 0155). Returns how many were rebuilt."""
    n = 0
    for ob in sur.props(scene):
        if int(ob.get(VER_KEY, 0)) < VERSION and ob.get(sur.PROP_TAG) in S.PROPS:
            try:
                rebuild(ob)
                n += 1
            except Exception as exc:                 # one prop never stops the project from opening
                print(f"Fresing Render: prop '{ob.name}' kept its old look: {exc}")
    return n


def is_person(ob) -> bool:
    return ob is not None and ob.get(sur.PROP_TAG) == "PERSON"


def person_changed(settings, context) -> None:
    """Update of a person's setting: its mesh is built again."""
    ob = settings.id_data
    if is_person(ob):
        rebuild(ob)


def visible_level(ob, scene=None) -> str:
    """Which level the modifier keeps for this prop now (``DETAILED`` / ``LIGHT``), from the evaluated mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.data
    att = me.attributes.get(LOD_ATTR)
    if att is None or not len(att.data):
        return P.DETAILED
    vals = np.zeros(len(att.data), dtype=np.int32)
    att.data.foreach_get("value", vals)
    return P.LIGHT if (vals == 2).all() else P.DETAILED


# =============================================================================
# the level-of-detail node group
# =============================================================================


def _set(mod, ng, name, value) -> None:
    for item in ng.interface.items_tree:
        if getattr(item, "in_out", "") == "INPUT" and item.name == name:
            slot = getattr(mod.properties.inputs, item.identifier)
            if slot.value != value:
                slot.value = value
                mod.id_data.update_tag()          # a changed input alone does not evaluate the object again
            return


def node_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get("fr_version") == GROUP_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    mode = ng.interface.new_socket("Mode", in_out="INPUT", socket_type="NodeSocketInt")
    mode.min_value, mode.max_value, mode.default_value = 0, 2, 0
    dist = ng.interface.new_socket("Distance", in_out="INPUT", socket_type="NodeSocketFloat")
    dist.min_value, dist.default_value = 0.0, 30.0
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    cam = N.new("GeometryNodeInputActiveCamera")
    info = N.new("GeometryNodeObjectInfo")
    info.transform_space = "RELATIVE"               # the camera in the prop's own space: its length = the distance
    L.new(cam.outputs[0], info.inputs["Object"])
    length = N.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    L.new(info.outputs["Location"], length.inputs[0])
    far = N.new("FunctionNodeCompare")
    far.data_type, far.operation = "FLOAT", "GREATER_THAN"
    L.new(length.outputs["Value"], far.inputs["A"])
    L.new(gin.outputs["Distance"], far.inputs["B"])

    def int_eq(sock, value):
        c = N.new("FunctionNodeCompare")
        c.data_type, c.operation = "INT", "EQUAL"
        L.new(sock, c.inputs["A"])
        c.inputs["B"].default_value = value
        return c.outputs[0]

    def boolean(op, a, b=None):
        n = N.new("FunctionNodeBooleanMath")
        n.operation = op
        L.new(a, n.inputs[0])
        if b is not None:
            L.new(b, n.inputs[1])
        return n.outputs[0]

    auto = int_eq(gin.outputs["Mode"], 0)
    light_mode = int_eq(gin.outputs["Mode"], 2)
    use_light = boolean("OR", light_mode, boolean("AND", auto, far.outputs[0]))
    attr = N.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "INT"
    attr.inputs["Name"].default_value = LOD_ATTR
    is_det = int_eq(attr.outputs["Attribute"], 1)
    is_light = int_eq(attr.outputs["Attribute"], 2)
    drop = boolean("OR", boolean("AND", is_det, use_light), boolean("AND", is_light, boolean("NOT", use_light)))
    delete = N.new("GeometryNodeDeleteGeometry")
    delete.domain = "FACE"
    L.new(gin.outputs["Geometry"], delete.inputs["Geometry"])
    L.new(drop, delete.inputs["Selection"])
    L.new(delete.outputs[0], gout.inputs[0])
    for i, n in enumerate(N):
        n.location = (200 * (i % 8), -150 * (i // 8))
    ng["fr_version"] = GROUP_VERSION
    return ng


# =============================================================================
# materials (procedural: skin, cloth, wear; no pictures)
# =============================================================================

_SKIN = {"skin_1": (0.87, 0.69, 0.58), "skin_2": (0.76, 0.57, 0.44), "skin_3": (0.55, 0.38, 0.27),
         "skin_4": (0.36, 0.24, 0.17)}
_HAIR = {"hair_dark": (0.05, 0.035, 0.025), "hair_brown": (0.22, 0.13, 0.07), "hair_grey": (0.55, 0.54, 0.52)}
_CLOTH = {"cloth_navy": (0.13, 0.17, 0.27), "cloth_navy_dark": (0.1, 0.13, 0.21), "cloth_orange": (0.95, 0.4, 0.07),
          "cloth_orange_dark": (0.8, 0.33, 0.06), "cloth_shirt": (0.68, 0.78, 0.9), "cloth_trousers": (0.2, 0.2, 0.22),
          "glove_grey": (0.42, 0.43, 0.44), "glove_orange": (0.95, 0.55, 0.1), "belt": (0.06, 0.05, 0.045)}
_PLASTIC = {"helmet_white": ((0.92, 0.92, 0.9), 0.25), "helmet_yellow": ((0.98, 0.78, 0.06), 0.25),
            "ibc_cap": ((0.08, 0.2, 0.45), 0.35), "ibc_valve": ((0.06, 0.06, 0.06), 0.4),
            "tank_label": ((0.93, 0.93, 0.9), 0.6), "warning_yellow": ((0.98, 0.78, 0.06), 0.5),
            "eye_dark": ((0.04, 0.03, 0.03), 0.15), "lips": ((0.55, 0.32, 0.3), 0.45),
            "casting_hole": ((0.02, 0.02, 0.02), 0.8), "sole_rubber": ((0.03, 0.03, 0.03), 0.8),
            "boots_black": ((0.03, 0.03, 0.035), 0.42), "boots_brown": ((0.2, 0.11, 0.05), 0.45)}
_PAINT = {"prop_container_blue": ("RAL 5010", 0.5, 0.5), "trolley_red": ("RAL 3020", 0.3, 0.1),
          "trolley_grey": ("RAL 7016", 0.35, 0.05), "barrier_foot": ("RAL 1023", 0.4, 0.4),
          "bottle_grey": ("RAL 7037", 0.4, 0.25), "shoulder_white": ("RAL 9010", 0.35, 0.1),
          "shoulder_green": ("RAL 6001", 0.35, 0.1), "shoulder_maroon": ("RAL 3009", 0.35, 0.1),
          "shoulder_black": ("RAL 9005", 0.35, 0.1)}
_METAL = {"aluminium": ((0.85, 0.86, 0.87), 0.3), "brass": ((0.82, 0.62, 0.32), 0.3),
          "plate_grey": ((0.75, 0.76, 0.77), 0.35)}
_WOOD = {"wood_2": (0.62, 0.48, 0.31), "wood_block": (0.5, 0.38, 0.24)}


def material(key: str) -> bpy.types.Material:
    if key in _SURROUNDINGS_KEYS:
        return sur.material(key)
    name = MAT_PREFIX + key
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_prop_mat") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    _make(key, mat)
    mat["fr_prop_mat"] = MAT_VERSION
    mat["fr_env"] = key
    return mat


def _lin(rgb):
    return sur._srgb(*rgb)


def _make(key: str, mat) -> None:
    t = sur._NT(mat)
    co = sur._coords(t)
    if key in _SKIN:
        base = _lin(_SKIN[key])
        n = sur._noise(t, 60.0, 3.0, 0.6, co)
        col = sur._mix_color(t, sur._ramp(t, n, 0, 1), tuple(c * 0.94 for c in base), tuple(min(1, c * 1.04)
                                                                                           for c in base))
        shader = sur._principled(t, col, sur._ramp(t, n, 0.42, 0.55), normal=sur._bump(t, n, 0.05, 0.002),
                                 Subsurface_Weight=0.25, Subsurface_Scale=0.008)
    elif key in _HAIR:
        base = _lin(_HAIR[key])
        n = sur._noise(t, 400.0, 2.0, 0.5, co)
        shader = sur._principled(t, base, 0.5, normal=sur._bump(t, n, 0.4, 0.002), Sheen_Weight=0.3)
    elif key in _CLOTH:
        base = _lin(_CLOTH[key])
        weave = sur._noise(t, 900.0, 2.0, 0.5, co)
        folds = sur._noise(t, 9.0, 3.0, 0.55, co)
        col = sur._mix_color(t, sur._ramp(t, folds, 0, 1), tuple(c * 0.86 for c in base), base)
        mix = t.node("ShaderNodeMath", _operation="ADD", Value=weave)
        t.link(folds, mix.inputs[1])
        shader = sur._principled(t, col, 0.88, normal=sur._bump(t, mix.outputs[0], 0.12, 0.004), Sheen_Weight=0.4)
    elif key == "hivis_yellow":
        n = sur._noise(t, 900.0, 2.0, 0.5, co)
        col = _lin((0.86, 0.98, 0.08))
        shader = sur._principled(t, col, 0.75, normal=sur._bump(t, n, 0.1, 0.002), Emission_Color=(*col, 1.0),
                                 Emission_Strength=0.08)
    elif key == "reflective":
        n = sur._noise(t, 1500.0, 2.0, 0.5, co)
        shader = sur._principled(t, _lin((0.78, 0.79, 0.8)), 0.32, metal=0.55, normal=sur._bump(t, n, 0.2, 0.001))
    elif key in _PLASTIC:
        col, rough = _PLASTIC[key]
        n = sur._noise(t, 30.0, 3.0, 0.5, co)
        shader = sur._principled(t, _lin(col), sur._ramp(t, n, rough * 0.8, rough * 1.2),
                                 normal=sur._bump(t, n, 0.03, 0.002))
    elif key in _PAINT:
        code, rough, wear = _PAINT[key]
        shader = _worn(t, sur._ral(code), rough, wear, co)
    elif key in _METAL:
        col, rough = _METAL[key]
        n = sur._noise(t, 50.0, 4.0, 0.6, co)
        shader = sur._principled(t, _lin(col), sur._ramp(t, n, rough * 0.7, rough * 1.4), metal=1.0)
    elif key in _WOOD:
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", Scale=7.0, Distortion=7.0,
                      Detail=3.0, Vector=co)
        base = _lin(_WOOD[key])
        col = sur._mix_color(t, sur._ramp(t, wave.outputs["Fac"], 0, 1, 0.2, 0.9), tuple(c * 0.8 for c in base), base)
        shader = sur._principled(t, col, 0.8, normal=sur._bump(t, wave.outputs["Fac"], 0.08, 0.003))
    elif key == "ibc_tank":
        n = sur._noise(t, 6.0, 3.0, 0.5, co)
        col = sur._mix_color(t, sur._ramp(t, n, 0, 1, 0.45, 0.8), _lin((0.93, 0.93, 0.9)), _lin((0.8, 0.79, 0.72)))
        shader = sur._principled(t, col, 0.5, Subsurface_Weight=0.4, Subsurface_Scale=0.05)
    elif key == "tape":
        shader = sur._principled(t, _lin((0.7, 0.55, 0.33)), 0.3)
    else:
        shader = sur._paint(t, sur._ral("RAL 7035"), 0.5)
    sur._output(t, shader, False, False)


def _worn(t, colour, rough, wear, co):
    """Paint with wear: chipped edges and rust spots (``wear`` 0 … 1) and dirt towards the floor."""
    n = sur._noise(t, 3.0, 3.0, 0.5, co)
    col = sur._mix_color(t, sur._ramp(t, n, 0.0, 1.0), tuple(c * 0.95 for c in colour),
                         tuple(min(1.0, c * 1.05) for c in colour))
    if wear > 0:
        spots = sur._noise(t, 14.0, 6.0, 0.7, co)
        rust = t.node("ShaderNodeMapRange", Value=spots, **{"From Min": 0.72 - 0.08 * wear, "From Max": 0.8,
                                                            "To Min": 0.0, "To Max": 1.0})
        col = sur._mix_color(t, rust.outputs["Result"], col, _lin((0.32, 0.15, 0.07)))
        sep = t.node("ShaderNodeSeparateXYZ", Vector=t.node("ShaderNodeTexCoord").outputs["Object"])
        dirt = t.node("ShaderNodeMapRange", Value=sep.outputs["Z"], **{"From Min": 0.0, "From Max": 0.6,
                                                                       "To Min": 0.35 * wear, "To Max": 0.0})
        col = sur._mix_color(t, dirt.outputs["Result"], col, _lin((0.2, 0.18, 0.15)))
    return sur._principled(t, col, sur._ramp(t, n, rough * 0.85, rough * 1.3), normal=sur._bump(t, n, 0.04, 0.01))


# =============================================================================
# a line-up of every prop and three people (the test tour stop "props" and the PC check's "scene.props")
# =============================================================================

LINEUP_PEOPLE = (("STANDING", "WORKSHOP", "1.75", True, False), ("POINTING", "OFFSHORE", "1.85", True, True),
                 ("PANEL", "OFFICE", "1.65", False, False))


def line_up(scene) -> list:
    """Every prop once and three people (poses, clothes, heights), in a row beside the machine. Returns the props."""
    out = []
    for i, (pose, outfit, height, helmet, gloves) in enumerate(LINEUP_PEOPLE):
        ob = sur.add_prop(scene, "PERSON")
        ps = ob.fresing_person
        ps.pose, ps.outfit, ps.height_choice, ps.helmet, ps.gloves, ps.look = pose, outfit, height, helmet, gloves, i
        out.append(ob)
    for kind in S.PROPS:
        if kind != "PERSON":
            out.append(sur.add_prop(scene, kind))
    bpy.context.view_layer.update()
    return out


def corners(obs) -> np.ndarray:
    """World corners of the props' boxes, an (n, 3) array (``cameras.add_camera(points=…)`` fits a camera to them)."""
    from mathutils import Vector
    return np.array([tuple(ob.matrix_world @ Vector(c)) for ob in obs for c in ob.bound_box], float)


def check_line_up(scene) -> str:
    """What the tour and the PC check test on the line-up: every kind, the people's poses, detail near the camera,
    every prop on the floor."""
    obs = sur.props(scene)
    kinds = {ob.get(sur.PROP_TAG) for ob in obs}
    if kinds != set(S.PROPS):
        raise RuntimeError(f"missing props: {', '.join(sorted(set(S.PROPS) - kinds))}")
    people = [ob for ob in obs if is_person(ob)]
    poses = {ob.fresing_person.pose for ob in people}
    if len(poses) < 3:
        raise RuntimeError(f"the people should stand in three poses, found {len(poses)}")
    floor = sur.floor_height(scene)
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in obs:
        ev = ob.evaluated_get(dg)
        n = len(ev.data.vertices)
        co = np.zeros(n * 3, dtype=np.float32)
        ev.data.vertices.foreach_get("co", co)
        low = float((np.asarray(ob.matrix_world) @ np.c_[co.reshape(-1, 3), np.ones(n)].T)[2].min())
        if abs(low - floor) > 0.005:
            raise RuntimeError(f"{ob.name} stands {1000 * (low - floor):.0f} mm off the floor")
    cam = scene.camera
    near = min(obs, key=lambda o: (o.matrix_world.translation - cam.matrix_world.translation).length) if cam else None
    if near is not None and scene.fresing.props_detail != "LIGHT" and \
            (near.matrix_world.translation - cam.matrix_world.translation).length < scene.fresing.props_far and \
            visible_level(near) != P.DETAILED:
        raise RuntimeError(f"{near.name} is close to the camera but shows its light version")
    return f"{len(obs)} props ({len(people)} people: {', '.join(sorted(poses)).lower()}), all on the floor"
