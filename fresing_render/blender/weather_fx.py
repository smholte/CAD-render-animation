"""Falling rain and snow, splashes and the flag (task 0109).

Everything here is Geometry Nodes on point meshes made once (``core/weather_fx.py`` has the seeded layouts and the
formulas; the node trees evaluate the same formulas from **Scene Time**): every render of a frame is the same, the
render queue renders it, nothing runs in Python per frame. The amounts are modifier inputs driven by the scene's
weather channels with simple-expression drivers (scripts off), so a Weather & time step that keys ``fr_wx_rain``
starts the rain.

    FR weather rain        streaks in a box that travels with the active camera (the drops stay put in the world;
                           rain further away is the fog's job); thin as the drop, as long as it falls in 1/50 s,
                           slanting with the wind. None below a roof or inside the machine: the box's points are
                           dropped where they lie under the top surface seen from above ("FR weather tops").
    FR weather snow        flakes the same way, falling at 1 m/s, drifting with the wind and swaying.
    FR weather splashes    crowns that grow and vanish in 0.08 s on spots that face up (deck, ground, the machine's
                           top faces), worked out once by looking straight down; "… sea": on the water at sea level.
    FR weather pole/flag   a pole at the stern (Open sea) or beside the machine's back corner, and a flag that waves
                           with the wind by a travelling wave (no simulation); it flies towards where the wind blows.

Only outdoors ('sky' and 'photo'); indoors nothing falls. All objects are tagged ``fr_weather`` (value: their role)
and live in the collection "FR Weather"; ``remove`` takes every one of them, their meshes, node groups and
materials away again. Objects that sit on the model (the tops, the solid splashes, the flag) are children of the
model's root, so they ride along with vessel motion.
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np

from ..core import weather as wcore
from ..core import weather_fx as core

COLLECTION = "FR Weather"
TAG = "fr_weather"
VERSION = 1
PREFIX = "FR weather "
NG = {"rain": PREFIX + "rain", "snow": PREFIX + "snow", "splash": PREFIX + "splash", "flag": PREFIX + "flag"}
MOD = "FR weather"


# ---------------------------------------------------------------------------
# what is wanted
# ---------------------------------------------------------------------------

def scene_fcurves(scene) -> list:
    """The F-curves of the scene's own action (Blender 5 layered actions: the slot's channel bag)."""
    ad = scene.animation_data
    act = ad.action if ad is not None else None
    if act is None:
        return []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb is not None:
            return list(cb.fcurves)
    except Exception:
        pass
    return list(getattr(act, "fcurves", ()) or ())


def peak(scene, name: str) -> float:
    """The largest value a channel takes now or anywhere in a built animation (keys of a Weather & time step)."""
    v = float(scene.get(wcore.prop(name), 0.0))
    path = f'["{wcore.prop(name)}"]'
    for fc in scene_fcurves(scene):
        if fc.data_path == path and len(fc.keyframe_points):
            co = np.empty(2 * len(fc.keyframe_points), dtype=np.float32)
            fc.keyframe_points.foreach_get("co", co)
            v = max(v, float(co[1::2].max()))
    return v


def needs(scene, place: str) -> dict:
    w = scene.fresing.weather
    out = {"rain": False, "snow": False, "flag": False}
    if place not in ("sky", "photo"):
        return out
    out["rain"] = peak(scene, "rain") > 1e-4
    out["snow"] = peak(scene, "snow") > 1e-4
    out["flag"] = bool(getattr(w, "flag", False))
    return out


def _mine(x) -> bool:
    """Made here (weather_sky tags its moon, floodlights, masts and fog with the same tag: never touch those)."""
    from .weather_sky import ROLES as SKY_ROLES
    role = x.get(TAG)
    return isinstance(role, str) and role not in SKY_ROLES


def objects(scene=None) -> list:
    obs = scene.objects if scene is not None else bpy.data.objects
    return [o for o in obs if _mine(o)]


def find(role: str):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        return None
    return next((o for o in col.objects if o.get(TAG) == role), None)


# ---------------------------------------------------------------------------
# apply / remove
# ---------------------------------------------------------------------------

def apply(scene, st=None, place: str = "sky") -> None:
    """Make (or take away) rain, snow, splashes and the flag for the weather now. Cheap when nothing changed;
    never raises into the UI."""
    try:
        _apply(scene, place)
    except Exception as exc:                       # (a preview update must never break the panel)
        import traceback
        traceback.print_exc()
        print("Fresing Render: rain / snow / flag failed:", exc)


def _model_key(scene) -> list:
    from . import build, logic
    lo, hi = logic.cached_bounds(scene)
    return [[r.name, r.get("fr_stats", "")] for r in build.model_roots(scene)] + [
        [round(float(v), 3) for v in lo], [round(float(v), 3) for v in hi]]


def _key(scene, want: dict) -> str:
    s = scene.fresing
    sea = _sea()
    return json.dumps({"v": VERSION, "want": want, "model": _model_key(scene), "bg": s.background,
                       "sea": None if sea is None else round(float(_world(sea).translation.z), 3)},
                      sort_keys=True)


def _apply(scene, place: str) -> None:
    want = needs(scene, place)
    if not any(want.values()):
        remove(scene)
        return
    col = bpy.data.collections.get(COLLECTION)
    key = _key(scene, want)
    roles = _roles(want)
    if (col is not None and col.get("fr_key") == key and col.name in scene.collection.children
            and all(find(r) is not None for r in roles)):
        return
    remove(scene, keep_collection=True)
    col = _collection(scene)
    bpy.context.view_layer.update()                # (objects the surroundings have just made: their places)
    from . import vessel_motion
    with vessel_motion.at_rest(scene):
        root = _root(scene)
        grid = None
        if want["rain"] or want["snow"]:
            grid = _tops(scene)
            _tops_object(scene, col, grid, root)
        if want["rain"]:
            _rain(scene, col)
            _splashes(scene, col, grid, root)
        if want["snow"]:
            _snow(scene, col)
        if want["flag"]:
            _flag(scene, col, root)
    col["fr_key"] = key


def _roles(want: dict) -> list:
    out = []
    if want["rain"] or want["snow"]:
        out.append("tops")
    if want["rain"]:
        out += ["rain", "splash"]
    if want["snow"]:
        out.append("snow")
    if want["flag"]:
        out += ["pole", "flag"]
    return out


def remove(scene=None, keep_collection: bool = False) -> None:
    """Take away every object, mesh, node group and material made here."""
    col = bpy.data.collections.get(COLLECTION)
    meshes = set()
    for ob in [o for o in bpy.data.objects if _mine(o)]:
        if ob.type == "MESH" and ob.data is not None:
            meshes.add(ob.data.name)
        bpy.data.objects.remove(ob)
    for name in meshes:
        me = bpy.data.meshes.get(name)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for me in [m for m in bpy.data.meshes if _mine(m) and m.users == 0]:
        bpy.data.meshes.remove(me)
    for ng in [g for g in bpy.data.node_groups if _mine(g)]:
        bpy.data.node_groups.remove(ng)
    for m in [m for m in bpy.data.materials if _mine(m)]:
        bpy.data.materials.remove(m)
    if col is not None:
        if keep_collection:
            if "fr_key" in col:
                del col["fr_key"]
        else:
            bpy.data.collections.remove(col)


def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _root(scene):
    from . import build
    roots = build.model_roots(scene)
    return roots[0] if roots else None


def _sea():
    return next((o for o in bpy.data.objects if o.get("fr_env") == "sea"), None)


def _world(ob):
    """An object's world matrix from its own and its parents' settings (right also before the scene's next
    update: a sea the surroundings have just made still has the identity as its ``matrix_world``)."""
    m = ob.matrix_basis.copy()
    while ob.parent is not None:
        m = ob.parent.matrix_basis @ ob.matrix_parent_inverse @ m
        ob = ob.parent
    return m


def _new_object(col, name: str, role: str, me, parent=None, shadow: bool = False):
    me[TAG] = role
    ob = bpy.data.objects.new(name, me)
    ob[TAG] = role
    ob["fr_kind"] = "cnc"                    # not a part of the model's tree (logic.Tree leaves it out)
    col.objects.link(ob)
    ob.hide_select = True
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    if not shadow:          # seen by the camera only: no shadows, not in reflections (cheaper, no dark speckles)
        ob.visible_shadow = False
        ob.visible_diffuse = False
        ob.visible_glossy = False
        ob.visible_transmission = False
        ob.visible_volume_scatter = False
    return ob


def _points_mesh(name: str, p, attrs: dict, role: str):
    me = bpy.data.meshes.new(name)
    me[TAG] = role
    p = np.asarray(p, dtype=np.float32).reshape(-1, 3)
    me.vertices.add(len(p))
    me.vertices.foreach_set("co", p.ravel())
    for k, v in attrs.items():
        v = np.asarray(v, dtype=np.float32)
        if v.ndim == 2:
            a = me.attributes.new(k, "FLOAT_VECTOR", "POINT")
            a.data.foreach_set("vector", v.ravel())
        else:
            a = me.attributes.new(k, "FLOAT", "POINT")
            a.data.foreach_set("value", v)
    me.update()
    return me


# ---------------------------------------------------------------------------
# drivers on modifier inputs (simple expressions: scripts off)
# ---------------------------------------------------------------------------

def _drive(ob, mod, ident: str, expr: str, chans: dict, scene) -> None:
    path = f'modifiers["{mod.name}"].properties.inputs.{ident}.value'
    try:
        ob.driver_remove(path)
    except TypeError:
        pass
    fc = ob.driver_add(path)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for var_name, ch in chans.items():
        v = drv.variables.new()
        v.name = var_name
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "SCENE"
        v.targets[0].id = scene
        v.targets[0].data_path = f'["{wcore.prop(ch)}"]'
    drv.expression = expr


def _modifier(ob, ng):
    mod = ob.modifiers.new(MOD, "NODES")
    mod.node_group = ng
    return mod


def _ident(ng, name: str) -> str:
    return next(i.identifier for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"
                and i.name == name)


def _set_input(mod, ng, name: str, value) -> None:
    getattr(mod.properties.inputs, _ident(ng, name)).value = value


# ---------------------------------------------------------------------------
# node building
# ---------------------------------------------------------------------------

class _G:
    def __init__(self, ng):
        self.ng, self.n, self.L = ng, ng.nodes, ng.links
        self.col = 0

    def node(self, kind, **props):
        nd = self.n.new(kind)
        self.col += 1
        nd.location = (-1600 + 160 * (self.col % 20), -200 * (self.col // 20))
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        m = self.node("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(m.inputs[i], v)
        return m.outputs[0]

    def vmath(self, op, a, b=None, c=None, scale=None):
        m = self.node("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(m.inputs[i], v)
        if scale is not None:
            self.put(m.inputs["Scale"], scale)
        return m.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else m.outputs["Vector"]

    def xyz(self, x=0.0, y=0.0, z=0.0):
        c = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(c.inputs[i], v)
        return c.outputs[0]

    def sep(self, v):
        s = self.node("ShaderNodeSeparateXYZ")
        self.put(s.inputs[0], v)
        return s.outputs

    def attr(self, name, kind="FLOAT"):
        a = self.node("GeometryNodeInputNamedAttribute", data_type=kind)
        a.inputs["Name"].default_value = name
        return a.outputs["Attribute"]

    def less(self, a, b):
        c = self.node("FunctionNodeCompare", data_type="FLOAT", operation="LESS_THAN")
        self.put(c.inputs["A"], a)
        self.put(c.inputs["B"], b)
        return c.outputs["Result"]

    def time(self):
        return self.node("GeometryNodeInputSceneTime").outputs["Seconds"]

    def switch(self, kind, cond, a, b):
        s = self.node("GeometryNodeSwitch", input_type=kind)
        self.put(s.inputs["Switch"], cond)
        self.put(s.inputs["False"], a)
        self.put(s.inputs["True"], b)
        return s.outputs[0]


def _new_group(role: str, inputs) -> tuple:
    name = NG[role]
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng[TAG] = role
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for nm, kind, default in inputs:
        s = ng.interface.new_socket(nm, in_out="INPUT", socket_type=kind)
        if default is not None:
            s.default_value = default
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    g = _G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    return ng, g, gin, gout


def _under_roof(g, gin, pos):
    """True where ``pos`` lies below the top surface seen from above (the Tops object; points outside it: False)."""
    info = g.node("GeometryNodeObjectInfo", transform_space="RELATIVE")
    g.put(info.inputs["Object"], gin.outputs["Tops"])
    tops = info.outputs["Geometry"]
    flat = g.node("GeometryNodeSetPosition")
    g.put(flat.inputs["Geometry"], tops)
    tpos = g.node("GeometryNodeInputPosition").outputs[0]
    ts = g.sep(tpos)
    g.put(flat.inputs["Position"], g.xyz(ts[0], ts[1], 0.0))
    ps = g.sep(pos)
    near = g.node("GeometryNodeSampleNearest", domain="POINT")
    g.put(near.inputs["Geometry"], flat.outputs[0])
    g.put(near.inputs["Sample Position"], g.xyz(ps[0], ps[1], 0.0))
    smp = g.node("GeometryNodeSampleIndex", data_type="FLOAT_VECTOR", domain="POINT")
    g.put(smp.inputs["Geometry"], tops)
    g.put(smp.inputs["Value"], g.node("GeometryNodeInputPosition").outputs[0])
    g.put(smp.inputs["Index"], near.outputs["Index"])
    top = g.sep(smp.outputs[0])
    dx = g.math("SUBTRACT", ps[0], top[0])
    dy = g.math("SUBTRACT", ps[1], top[1])
    d2 = g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy))
    cell = gin.outputs["Cell"]
    inside = g.less(d2, g.math("MULTIPLY", g.math("MULTIPLY", cell, cell), 0.6))
    below = g.less(ps[2], top[2])
    both = g.node("FunctionNodeBooleanMath", operation="AND")
    g.put(both.inputs[0], inside)
    g.put(both.inputs[1], below)
    return both.outputs[0]


def _falling_group(role: str, snow: bool):
    """Rain or snow: the points of the unit box (``fr_u``, ``fr_r``, ``fr_ph``, ``fr_s``) moved by Scene Time,
    folded into the box in front of the active camera, the ones over the amount and under a roof dropped,
    instanced as streaks or flakes."""
    ins = [("Amount", "NodeSocketFloat", 0.0), ("Drop", "NodeSocketFloat", 2.0), ("Wind X", "NodeSocketFloat", 0.0),
           ("Wind Y", "NodeSocketFloat", 0.0), ("Box", "NodeSocketVector", None),
           ("Viewport", "NodeSocketFloat", core.VIEWPORT), ("Tops", "NodeSocketObject", None),
           ("Cell", "NodeSocketFloat", core.SPLASH_CELL), ("Material", "NodeSocketMaterial", None)]
    ng, g, gin, gout = _new_group(role, ins)
    t = g.time()
    u = g.attr("fr_u", "FLOAT_VECTOR")
    r = g.attr("fr_r")
    view = g.node("GeometryNodeIsViewport").outputs[0]
    amount = g.math("MULTIPLY", gin.outputs["Amount"], g.switch("FLOAT", view, 1.0, gin.outputs["Viewport"]))
    if snow:
        fall = core.SNOW_FALL
        vz = -fall
    else:   # Atlas et al. (1973): 9.65 - 10.3 exp(-0.6 D)
        d = g.math("MAXIMUM", gin.outputs["Drop"], 0.2)
        vz = g.math("SUBTRACT", g.math("MULTIPLY", g.math("EXPONENT", g.math("MULTIPLY", d, -0.6)), 10.3), 9.65)
        vz = g.math("MINIMUM", vz, -0.5)
    vel = g.xyz(gin.outputs["Wind X"], gin.outputs["Wind Y"], vz)
    raw = g.vmath("ADD", g.vmath("MULTIPLY", u, gin.outputs["Box"]), g.vmath("SCALE", vel, scale=t))
    if snow:
        ph = g.attr("fr_ph")
        a = g.math("MULTIPLY_ADD", t, core.SNOW_OMEGA, g.math("MULTIPLY", ph, 2.0 * math.pi))
        sway = g.xyz(g.math("MULTIPLY", g.math("SINE", a), core.SNOW_WOBBLE),
                     g.math("MULTIPLY", g.math("COSINE", g.math("MULTIPLY", a, 1.3)), core.SNOW_WOBBLE), 0.0)
        raw = g.vmath("ADD", raw, sway)
    cam = g.node("GeometryNodeInputActiveCamera").outputs[0]
    info = g.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    g.put(info.inputs["Object"], cam)
    rot = g.node("FunctionNodeRotateVector")
    g.put(rot.inputs["Vector"], (0.0, 0.0, -1.0))
    g.put(rot.inputs["Rotation"], info.outputs["Rotation"])
    bx = g.sep(gin.outputs["Box"])[0]
    centre = g.vmath("ADD", info.outputs["Location"], g.vmath("SCALE", rot.outputs[0],
                                                                scale=g.math("MULTIPLY", bx, core.AHEAD)))
    lo = g.vmath("SUBTRACT", centre, g.vmath("SCALE", gin.outputs["Box"], scale=0.5))
    hi = g.vmath("ADD", lo, gin.outputs["Box"])
    pos = g.vmath("WRAP", raw, hi, lo)
    setp = g.node("GeometryNodeSetPosition")
    g.put(setp.inputs["Geometry"], gin.outputs[0])
    g.put(setp.inputs["Position"], pos)
    # drop what is over the amount, then what lies under a roof (after the move: the test needs the place)
    dele = g.node("GeometryNodeDeleteGeometry", domain="POINT")
    g.put(dele.inputs["Geometry"], setp.outputs[0])
    g.put(dele.inputs["Selection"], g.math("GREATER_THAN", r, amount))     # r ≥ amount: not falling
    p2 = g.node("GeometryNodeInputPosition").outputs[0]
    roof = g.node("GeometryNodeDeleteGeometry", domain="POINT")
    g.put(roof.inputs["Geometry"], dele.outputs[0])
    g.put(roof.inputs["Selection"], _under_roof(g, gin, p2))
    inst = g.node("GeometryNodeInstanceOnPoints")
    g.put(inst.inputs["Points"], roof.outputs[0])
    if snow:
        ico = g.node("GeometryNodeMeshIcoSphere")
        ico.inputs["Radius"].default_value = 1.0
        ico.inputs["Subdivisions"].default_value = 1
        g.put(inst.inputs["Instance"], ico.outputs["Mesh"])
        size = g.math("MULTIPLY", g.attr("fr_s"), 0.5e-3 * core.FLAKE_MM)
        g.put(inst.inputs["Scale"], g.xyz(size, size, g.math("MULTIPLY", size, 0.45)))
    else:
        cyl = g.node("GeometryNodeMeshCylinder", fill_type="NONE")
        cyl.inputs["Vertices"].default_value = 3
        cyl.inputs["Radius"].default_value = 1.0
        cyl.inputs["Depth"].default_value = 1.0
        g.put(inst.inputs["Instance"], cyl.outputs["Mesh"])
        al = g.node("FunctionNodeAlignRotationToVector", axis="Z")
        g.put(al.inputs["Vector"], vel)
        g.put(inst.inputs["Rotation"], al.outputs["Rotation"])
        rad = g.math("MULTIPLY", g.math("MAXIMUM", gin.outputs["Drop"], 0.5), 0.75e-3)
        length = g.math("MAXIMUM", g.math("MULTIPLY", g.vmath("LENGTH", vel), core.EXPOSURE), 0.02)
        g.put(inst.inputs["Scale"], g.xyz(rad, rad, length))
    mat = g.node("GeometryNodeSetMaterial")
    g.put(mat.inputs["Geometry"], inst.outputs[0])
    g.put(mat.inputs["Material"], gin.outputs["Material"])
    g.put(gout.inputs[0], mat.outputs[0])
    return ng


def _splash_group():
    ins = [("Amount", "NodeSocketFloat", 0.0), ("Drop", "NodeSocketFloat", 2.0),
           ("Viewport", "NodeSocketFloat", core.VIEWPORT), ("Material", "NodeSocketMaterial", None)]
    ng, g, gin, gout = _new_group("splash", ins)
    t = g.time()
    r = g.attr("fr_r")
    ph = g.attr("fr_ph")
    view = g.node("GeometryNodeIsViewport").outputs[0]
    amount = g.math("MULTIPLY", gin.outputs["Amount"], g.switch("FLOAT", view, 1.0, gin.outputs["Viewport"]))
    age = g.math("FRACT", g.math("MULTIPLY_ADD", t, 1.0 / core.SPLASH_PERIOD, ph))
    life = core.SPLASH_LIFE / core.SPLASH_PERIOD
    dead = g.node("FunctionNodeBooleanMath", operation="OR")
    g.put(dead.inputs[0], g.math("GREATER_THAN", r, amount))
    g.put(dead.inputs[1], g.math("GREATER_THAN", age, life))
    dele = g.node("GeometryNodeDeleteGeometry", domain="POINT")
    g.put(dele.inputs["Geometry"], gin.outputs[0])
    g.put(dele.inputs["Selection"], dead.outputs[0])
    k = g.math("DIVIDE", age, life)                                   # 0 … 1 through the splash's life
    d = g.math("MAXIMUM", gin.outputs["Drop"], 0.5)
    rad = g.math("MULTIPLY", g.math("MULTIPLY", d, 0.004), g.math("MULTIPLY_ADD", k, 0.7, 0.3))
    hgt = g.math("MULTIPLY", g.math("MULTIPLY", d, 0.005), g.math("SUBTRACT", 1.05, k))
    cone = g.node("GeometryNodeMeshCone", fill_type="NONE")
    cone.inputs["Vertices"].default_value = 8
    cone.inputs["Radius Top"].default_value = 1.0
    cone.inputs["Radius Bottom"].default_value = 0.55
    cone.inputs["Depth"].default_value = 1.0
    tr = g.node("GeometryNodeTransform")
    g.put(tr.inputs["Geometry"], cone.outputs["Mesh"])
    g.put(tr.inputs["Translation"], (0.0, 0.0, 0.5))
    inst = g.node("GeometryNodeInstanceOnPoints")
    g.put(inst.inputs["Points"], dele.outputs[0])
    g.put(inst.inputs["Instance"], tr.outputs[0])
    g.put(inst.inputs["Scale"], g.xyz(rad, rad, hgt))
    mat = g.node("GeometryNodeSetMaterial")
    g.put(mat.inputs["Geometry"], inst.outputs[0])
    g.put(mat.inputs["Material"], gin.outputs["Material"])
    g.put(gout.inputs[0], mat.outputs[0])
    return ng


def _flag_group():
    """core.flag_points in nodes; then turned about z towards where the wind blows (in the flag's own frame, so a
    turned model or a rolling vessel keeps the flag flying with the world's wind)."""
    ins = [("Wind", "NodeSocketFloat", 0.0), ("Wind X", "NodeSocketFloat", 1.0), ("Wind Y", "NodeSocketFloat", 0.0),
           ("Length", "NodeSocketFloat", 1.0), ("Height", "NodeSocketFloat", 0.66),
           ("Material", "NodeSocketMaterial", None)]
    ng, g, gin, gout = _new_group("flag", ins)
    t = g.time()
    u, v = g.attr("fr_u"), g.attr("fr_v")
    w, L, H = gin.outputs["Wind"], gin.outputs["Length"], gin.outputs["Height"]
    mr = g.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
    g.put(mr.inputs["Value"], w)
    mr.inputs["From Min"].default_value = 0.5
    mr.inputs["From Max"].default_value = 9.0
    s = mr.outputs["Result"]
    theta = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, s), math.radians(78.0))
    f = g.math("MINIMUM", g.math("MAXIMUM", g.math("DIVIDE", g.math("MULTIPLY", w, 0.25),
                                                    g.math("MAXIMUM", L, 0.1)), 0.2), 4.0)
    amp = g.math("MULTIPLY", g.math("MULTIPLY_ADD", s, 0.10, 0.04), L)
    a = g.math("MULTIPLY", amp, g.math("POWER", u, 1.3))
    ft = g.math("MULTIPLY", f, t)
    phase = g.math("MULTIPLY_ADD", g.math("SUBTRACT", g.math("DIVIDE", u, 0.9), ft), 2.0 * math.pi,
                   g.math("MULTIPLY", v, 0.6))
    y = g.math("ADD", g.math("MULTIPLY", a, g.math("SINE", phase)),
               g.math("MULTIPLY", g.math("MULTIPLY", a, 0.3),
                      g.math("SINE", g.math("MULTIPLY_ADD", ft, 2.0 * math.pi * 0.37, g.math("MULTIPLY", u, 2.1)))))
    along = g.math("MULTIPLY", u, L)
    x = g.math("MULTIPLY", along, g.math("COSINE", theta))
    z = g.math("SUBTRACT", g.math("MULTIPLY", g.math("SUBTRACT", v, 1.0), H),
               g.math("MULTIPLY", along, g.math("SINE", theta)))
    # heading: the wind in the flag's own frame
    me = g.node("GeometryNodeSelfObject").outputs[0]
    info = g.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    g.put(info.inputs["Object"], me)
    inv = g.node("FunctionNodeInvertRotation")
    g.put(inv.inputs[0], info.outputs["Rotation"])
    rw = g.node("FunctionNodeRotateVector")
    g.put(rw.inputs["Vector"], g.xyz(gin.outputs["Wind X"], gin.outputs["Wind Y"], 0.0))
    g.put(rw.inputs["Rotation"], inv.outputs[0])
    wl = g.sep(rw.outputs[0])
    head = g.math("ARCTAN2", wl[1], wl[0])
    eul = g.node("FunctionNodeEulerToRotation")
    g.put(eul.inputs[0], g.xyz(0.0, 0.0, head))
    rv = g.node("FunctionNodeRotateVector")
    g.put(rv.inputs["Vector"], g.xyz(x, y, z))
    g.put(rv.inputs["Rotation"], eul.outputs[0])
    setp = g.node("GeometryNodeSetPosition")
    g.put(setp.inputs["Geometry"], gin.outputs[0])
    g.put(setp.inputs["Position"], rv.outputs[0])
    mat = g.node("GeometryNodeSetMaterial")
    g.put(mat.inputs["Geometry"], setp.outputs[0])
    g.put(mat.inputs["Material"], gin.outputs["Material"])
    g.put(gout.inputs[0], mat.outputs[0])
    return ng


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------

def _material(role: str, colour, alpha: float, rough: float = 0.3, sheen: float = 0.0):
    name = PREFIX + role
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new(name)
    mat[TAG] = role
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if sheen:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    mat.diffuse_color = (*colour, max(alpha, 0.2))
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(bsdf.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    else:
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# where rain lands: the top surface seen from above
# ---------------------------------------------------------------------------

def _solid_objects(scene) -> list:
    from . import build, surroundings
    out = []
    for ob in scene.objects:
        if ob.type != "MESH" or ob.hide_render or ob.get(TAG) is not None:
            continue
        env = ob.get(surroundings.TAG)
        if ob.get(build.PROP_KIND) == "part" or env in ("floor", "structure", "contents", "high", "photo_ground") \
                or ob.get(surroundings.PROP_TAG):
            out.append(ob)
    return out


def _triangles(scene, obs) -> np.ndarray:
    dg = bpy.context.evaluated_depsgraph_get()
    local = {}
    out = []
    for ob in obs:
        if ob.modifiers:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            tri = _mesh_tris(me)
            ev.to_mesh_clear()
        else:
            tri = local.get(ob.data.name)
            if tri is None:
                tri = local[ob.data.name] = _mesh_tris(ob.data)
        if not len(tri):
            continue
        m = np.array(ob.matrix_world, dtype=np.float64)
        w = tri.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        out.append(w.reshape(-1, 3, 3))
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def _mesh_tris(me) -> np.ndarray:
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    if not n:
        return np.zeros((0, 3, 3))
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    idx = np.empty(n * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", idx)
    return co.reshape(-1, 3)[idx].reshape(n, 3, 3).astype(np.float64)


def _area(scene) -> tuple:
    from . import logic
    lo, hi = logic.cached_bounds(scene)
    lo, hi = np.array(lo, dtype=float), np.array(hi, dtype=float)
    size = float(max(hi[0] - lo[0], hi[1] - lo[1], 1.0))
    m = max(4.0, 0.25 * size)
    return lo - m, hi + m


def _tops(scene) -> dict:
    lo, hi = _area(scene)
    x0, y0, cell, nx, ny = core.grid_for(lo, hi)
    tris = _triangles(scene, _solid_objects(scene))
    h, up = core.top_heights(tris, x0, y0, cell, nx, ny)
    sea = _sea()
    wz = float(sea.matrix_world.translation.z) if sea is not None else None
    return {"h": h, "up": up, "x0": x0, "y0": y0, "cell": cell, "water": wz}


def _tops_object(scene, col, grid, root):
    """Every covered cell's top as a point: rain and snow below these do not show (a roof, the machine)."""
    h = grid["h"]
    ny, nx = h.shape
    gy, gx = np.mgrid[0:ny, 0:nx]
    ok = np.isfinite(h)
    p = np.stack([grid["x0"] + (gx[ok] + 0.5) * grid["cell"], grid["y0"] + (gy[ok] + 0.5) * grid["cell"], h[ok]], 1)
    if not len(p):                                  # (nothing below: one point far away, so the sampling works)
        p = np.array([[0.0, 0.0, -1.0e6]])
    me = _points_mesh(PREFIX + "tops", p, {}, "tops")
    ob = _new_object(col, PREFIX + "tops", "tops", me, root)
    ob["fr_cell"] = float(grid["cell"])
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def _falling(scene, col, role: str, snow: bool):
    box = core.SNOW_BOX if snow else core.RAIN_BOX
    lay = core.layout(core.SEED_SNOW if snow else core.SEED_RAIN,
                      core.count(box, core.SNOW_DENSITY if snow else core.RAIN_DENSITY))
    me = _points_mesh(PREFIX + role, np.zeros((len(lay["r"]), 3)),
                      {"fr_u": lay["u"], "fr_r": lay["r"], "fr_ph": lay["ph"], "fr_s": lay["s"]}, role)
    ob = _new_object(col, PREFIX + role, role, me)
    ng = _falling_group(role, snow)
    mod = _modifier(ob, ng)
    _set_input(mod, ng, "Box", tuple(box))
    _set_input(mod, ng, "Tops", find("tops"))
    _set_input(mod, ng, "Cell", float(_tops_cell()))
    if snow:
        mat = _material("snow", (0.9, 0.9, 0.92), 1.0, 0.9, 0.3)
    else:
        mat = _material("rain", (0.75, 0.78, 0.8), 1.0, 0.2)
    _set_input(mod, ng, "Material", mat)
    ob.data.materials.append(mat)
    _drive(ob, mod, _ident(ng, "Amount"), "a", {"a": "snow" if snow else "rain"}, scene)
    _drive(ob, mod, _ident(ng, "Drop"), "d", {"d": "drop"}, scene)
    _drive(ob, mod, _ident(ng, "Wind X"), "w * x", {"w": "wind", "x": "wind_x"}, scene)
    _drive(ob, mod, _ident(ng, "Wind Y"), "w * y", {"w": "wind", "y": "wind_y"}, scene)
    return ob


def _tops_cell() -> float:
    ob = find("tops")
    return float(ob.get("fr_cell", core.SPLASH_CELL)) if ob is not None else core.SPLASH_CELL


def _rain(scene, col):
    return _falling(scene, col, "rain", False)


def _snow(scene, col):
    return _falling(scene, col, "snow", True)


def _splashes(scene, col, grid, root):
    sp = core.splash_spots(grid["h"], grid["up"], grid["x0"], grid["y0"], grid["cell"], grid["water"])
    mat = _material("splash", (0.7, 0.72, 0.75), 1.0, 0.2)
    ng = _splash_group()
    made = []
    for role, sel, parent in (("splash", sp["water"] < 0.5, root), ("splash_sea", sp["water"] >= 0.5, None)):
        if not np.any(sel):
            continue
        me = _points_mesh(PREFIX + role, sp["p"][sel], {"fr_r": sp["r"][sel], "fr_ph": sp["ph"][sel]}, role)
        ob = _new_object(col, PREFIX + role.replace("_", " "), role, me, parent)
        mod = _modifier(ob, ng)
        _set_input(mod, ng, "Material", mat)
        ob.data.materials.append(mat)
        _drive(ob, mod, _ident(ng, "Amount"), "a", {"a": "rain"}, scene)
        _drive(ob, mod, _ident(ng, "Drop"), "d", {"d": "drop"}, scene)
        made.append(ob)
    if not made:                       # (an empty marker, so the key's check finds the role)
        me = _points_mesh(PREFIX + "splash", np.zeros((0, 3)), {}, "splash")
        made.append(_new_object(col, PREFIX + "splash", "splash", me, root))
    return made


# ---------------------------------------------------------------------------
# the flag
# ---------------------------------------------------------------------------

def _pole_mesh(height: float, radius: float):
    me = bpy.data.meshes.new(PREFIX + "pole")
    n = 16
    a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    ring = np.stack([radius * np.cos(a), radius * np.sin(a)], 1)
    verts = [(x, y, 0.0) for x, y in ring] + [(x, y, height) for x, y in ring]
    faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    faces.append(tuple(range(2 * n - 1, n - 1, -1)))
    # a ball on top
    rb = radius * 1.8
    top = len(verts)
    rings, segs = 5, 12
    for j in range(1, rings):
        ph = math.pi * j / rings
        for i in range(segs):
            th = 2.0 * math.pi * i / segs
            verts.append((rb * math.sin(ph) * math.cos(th), rb * math.sin(ph) * math.sin(th),
                          height + rb + rb * math.cos(ph)))
    north, south = len(verts), len(verts) + 1
    verts += [(0.0, 0.0, height + 2.0 * rb), (0.0, 0.0, height)]
    for j in range(rings - 2):
        for i in range(segs):
            k0, k1 = top + j * segs, top + (j + 1) * segs
            faces.append((k0 + i, k1 + i, k1 + (i + 1) % segs, k0 + (i + 1) % segs))
    for i in range(segs):
        faces.append((north, top + i, top + (i + 1) % segs))
        last = top + (rings - 2) * segs
        faces.append((south, last + (i + 1) % segs, last + i))
    me.from_pydata(verts, [], faces)
    me.shade_smooth()
    return me


def _flag_mesh():
    u, v, faces = core.flag_grid()
    me = bpy.data.meshes.new(PREFIX + "flag")
    verts = np.stack([u, np.zeros_like(u), v - 1.0], 1)
    me.from_pydata(verts.tolist(), [], faces)
    for k, vals in (("fr_u", u), ("fr_v", v)):
        a = me.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", np.asarray(vals, dtype=np.float32))
    me.shade_smooth()
    return me


def flag_spot(scene) -> tuple:
    """(x, y, z, pole height, flag length, flag height) of the flag: at the stern of a vessel on Open sea (on what
    stands there), else on the floor just outside the back right corner of the model."""
    from . import logic, surroundings
    lo, hi = logic.cached_bounds(scene)
    lo, hi = np.array(lo, dtype=float), np.array(hi, dtype=float)
    size = float(max(hi - lo))
    pole, length, height = core.flag_size(size)
    if scene.fresing.background == "SEA":
        x, y = core.flag_place(lo, hi, True)
        tris = _triangles(scene, _solid_objects(scene))
        h, up = core.top_heights(tris, x - 0.5, y - 0.5, 0.25, 4, 4)
        z = float(np.max(h)) if np.isfinite(h).any() else float(lo[2])
    else:
        x, y = float(hi[0] + 0.6), float(hi[1] + 0.6)
        z = float(surroundings.floor_height(scene))
    return x, y, z, pole, length, height


def _flag(scene, col, root):
    x, y, z, pole, length, height = flag_spot(scene)
    pmat = _material("pole", (0.8, 0.8, 0.78), 1.0, 0.35)
    fmat = _material("flag", (0.62, 0.03, 0.03), 1.0, 0.6, 0.4)
    pme = _pole_mesh(pole, 0.01 + 0.006 * pole)
    pme.materials.append(pmat)
    pob = _new_object(col, PREFIX + "pole", "pole", pme, None, shadow=True)
    pob.location = (x, y, z)
    fme = _flag_mesh()
    fme.materials.append(fmat)
    fob = _new_object(col, PREFIX + "flag", "flag", fme, None, shadow=True)
    fob.location = (x, y, z + pole - 0.02)
    for ob in (pob, fob):
        if root is not None:
            ob.parent = root
            ob.matrix_parent_inverse = root.matrix_world.inverted()
    ng = _flag_group()
    mod = _modifier(fob, ng)
    _set_input(mod, ng, "Length", float(length))
    _set_input(mod, ng, "Height", float(height))
    _set_input(mod, ng, "Material", fmat)
    _drive(fob, mod, _ident(ng, "Wind"), "w", {"w": "wind"}, scene)
    _drive(fob, mod, _ident(ng, "Wind X"), "x", {"x": "wind_x"}, scene)
    _drive(fob, mod, _ident(ng, "Wind Y"), "y", {"y": "wind_y"}, scene)
    fob["fr_flag"] = json.dumps({"length": length, "height": height, "pole": pole})
    return pob, fob
