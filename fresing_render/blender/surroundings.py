"""Surroundings around the machine and props for scale (task 0016).

Built-in surroundings (sea, vessel deck, quayside, factory halls, warehouse) and the ground of a
360° photo live in the collection "FR Surroundings", under one empty that sits under the model:
the floor is at the model's lowest point (minus the floor gap), centred on it. The model itself is
never moved, so joints, poses, cameras and animations stay exactly as they are.

The layouts come from ``core/surroundings.py``; everything is made in code (no image files).
A surrounding is rebuilt only when its settings change, so a render in the background queue uses
what was saved with the project.

Halls are seen from inside: walls and the roof are see-through from outside (a camera outside the
hall looks in), do not block the light and cast no shadows, so a hall renders about as fast as
the studio. The sea has moving waves (geometry near the machine in "Detailed", ripples in the
material everywhere).

Props for scale (person, container, pallet, barrier) are ordinary objects in "FR Props": they can
be moved and are hidden or shown in one click.
"""

from __future__ import annotations

import json
import math
import os
import random

import bpy
import numpy as np

from ..core import ral
from ..core import surroundings as S

COLLECTION = "FR Surroundings"
ROOT = "FR Surroundings"
PROPS_COLLECTION = "FR Props"
MAT_PREFIX = "FR_env "
TAG = "fr_env"                     # on every object made here (value: its role)
PROP_TAG = "fr_prop"               # on props (value: prop kind)
MAT_VERSION = 1
WAVES_GROUP = "FR_env waves"
PHOTO_DEFAULT_HEIGHT = 1.7

# ray visibility per role: camera, diffuse, glossy, transmission, shadow
_VISIBILITY = {
    "shell": (True, False, True, True, False),
    "lights": (True, False, True, True, False),
    "high": (True, True, True, True, False),
    "photo_dome": (True, False, True, True, False),
    "photo_ground": (True, True, True, True, False),
    "sea": (True, True, True, True, False),
}


# =============================================================================
# what is wanted now
# =============================================================================


def wanted(s) -> str:
    """'' (nothing), a built-in kind, or 'PHOTO' (the ground of a 360° photo)."""
    if s.background in S.BUILT:
        return s.background
    if s.background == "HDRI" and s.photo_ground and _photo_path(s):
        return "PHOTO"
    return ""


def _photo_path(s) -> str:
    path = bpy.path.abspath(s.hdri_path) if s.hdri_path else ""
    return path if path and os.path.isfile(path) else ""


def _settings_key(s, kind: str) -> dict:
    key = {"kind": kind, "v": MAT_VERSION}
    if kind in S.BUILT:
        key["detail"] = s.env_detail
    if kind in S.SEA_KINDS:
        key.update(sea=s.sea_state, foam=bool(s.sea_foam), moving=bool(s.sea_moving))
    if kind == "SEA":
        key["water"] = round(s.water_level, 3)
    if kind == "PHOTO":
        key.update(photo=_photo_path(s), height=round(s.photo_height, 3))
    return key


def _models_key(scene) -> list:
    from . import build
    return [[r.name, r.get("fr_stats", "")] for r in build.model_roots(scene)]


def root_object():
    ob = bpy.data.objects.get(ROOT)
    return ob if ob is not None and ob.get(TAG) == "root" else None


def floor_height(scene) -> float:
    """World z of the floor the machine stands on (surroundings, else the model's lowest point)."""
    root = root_object()
    if root is not None and root.get("fr_kind"):
        return float(root.location.z)
    from . import logic
    mn, _mx = logic.cached_bounds(scene)
    return float(mn[2]) - scene.fresing.floor_offset


def far_clip(scene) -> float:
    """Camera clip distance the surroundings need (0 = nothing special)."""
    root = root_object()
    return float(root.get("fr_far", 0.0)) if root is not None and root.get("fr_kind") else 0.0


# =============================================================================
# entry point (called from world.apply)
# =============================================================================


def ensure(scene, s, replace: bool = False) -> None:
    """Make the surroundings match the settings. Cheap when nothing changed.

    ``replace``: read the model's size and position again (button 'Put on the floor again')."""
    kind = wanted(s)
    root = root_object()
    if not kind:
        if root is not None and root.get("fr_kind"):
            clear(scene)
        return
    key = json.dumps(_settings_key(s, kind), sort_keys=True)
    models = json.dumps(_models_key(scene))
    stale = (root is None or root.get("fr_key") != key or root.get("fr_models") != models or replace
             or not _objects(scene))
    if stale:
        _build(scene, s, kind, key, models)
        root = root_object()
    _update_live(scene, s, root)


def clear(scene) -> None:
    """Remove the surroundings (props stay)."""
    objs = [ob for ob in bpy.data.objects if ob.get(TAG) and ob.get(TAG) != "root"]
    meshes = {ob.data for ob in objs if ob.type == "MESH" and ob.data is not None}
    if objs:
        bpy.data.batch_remove(objs)
    orphans = [m for m in meshes if m.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    root = root_object()
    if root is not None:
        for k in ("fr_kind", "fr_key", "fr_models", "fr_far"):
            if k in root:
                del root[k]


def _objects(scene) -> list:
    col = bpy.data.collections.get(COLLECTION)
    return [ob for ob in col.objects if ob.get(TAG) and ob.get(TAG) != "root"] if col is not None else []


def _collection(scene, name: str = COLLECTION) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _root(scene) -> bpy.types.Object:
    root = root_object()
    if root is None:
        root = bpy.data.objects.new(ROOT, None)
        root[TAG] = "root"
        root.empty_display_size = 0.3
        root.hide_select = True
    col = _collection(scene)
    if root.name not in col.objects:
        col.objects.link(root)
    return root


def _model_box(scene) -> tuple[np.ndarray, np.ndarray]:
    from . import logic
    scene.fresing.bounds_valid = False
    return logic.cached_bounds(scene)


def _build(scene, s, kind: str, key: str, models: str) -> None:
    clear(scene)
    mn, mx = _model_box(scene)
    size = np.maximum(mx - mn, 0.05)
    root = _root(scene)
    root["fr_min"] = [float(v) for v in mn]
    root["fr_max"] = [float(v) for v in mx]
    root.location = (float(mn[0] + mx[0]) / 2, float(mn[1] + mx[1]) / 2, float(mn[2]) - s.floor_offset)
    col = _collection(scene)
    if kind == "PHOTO":
        far = _build_photo(scene, s, root, col, size)
    else:
        lay = S.build(kind, tuple(float(v) for v in size), s.env_detail, s.water_level)
        for role, shapes in lay.parts.items():
            if shapes:
                _shapes_object(f"FR {S.KIND[kind].label}: {role}", role, shapes, col, root)
        if lay.water_level is not None:
            _build_sea(s, col, root, lay.water_level, float(max(size[0], size[1])), kind)
        far = lay.extent * 1.3
    root["fr_kind"] = kind
    root["fr_key"] = key
    root["fr_models"] = models
    root["fr_far"] = far
    _show_in_view(scene, s)


def _update_live(scene, s, root) -> None:
    """Settings that need no rebuild: floor gap, photo turn and strength, cameras' clip distance."""
    if root is None:
        return
    mn = root.get("fr_min")
    if mn is not None:
        z = float(mn[2]) - s.floor_offset
        if abs(root.location.z - z) > 1e-6:
            root.location.z = z
    if root.get("fr_kind") == "PHOTO":
        _photo_update(s)
    far = float(root.get("fr_far", 0.0))
    if far > 0:
        fix_clip(scene, far)
    _show_in_view(scene, s)


def fix_clip(scene, far: float | None = None) -> None:
    """Cameras must see as far as the surroundings reach (the sea goes to the horizon)."""
    far = far_clip(scene) if far is None else far
    if far <= 0:
        return
    cams = [ob for ob in scene.objects if ob.type == "CAMERA"]
    for ob in cams:
        if ob.data.clip_end < far:
            ob.data.clip_end = far


def _show_in_view(scene, s) -> None:
    hide = not s.env_show_in_view
    for ob in _objects(scene):
        if ob.hide_viewport != hide:
            ob.hide_viewport = hide


# =============================================================================
# meshes from shapes
# =============================================================================


def _frame(p0, p1):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    a = p1 - p0
    n = np.linalg.norm(a)
    a = a / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])
    up = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    side = np.cross(a, up)
    side /= np.linalg.norm(side)
    u = np.cross(a, side)                  # (side, u, a) is right-handed
    return p0, p1, side, u


_BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


class _Mesh:
    def __init__(self):
        self.verts: list = []
        self.faces: list = []
        self.mats: list[int] = []
        self.smooth: list[bool] = []
        self.n = 0

    def _add(self, pts, faces, mat, smooth=False):
        base = self.n
        self.verts.append(np.asarray(pts, float))
        self.n += len(pts)
        for f in faces:
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(mat)
            self.smooth.append(smooth)

    def box8(self, corners, mat):
        self._add(corners, _BOX_FACES, mat)

    def shape(self, sh, mat):
        if isinstance(sh, S.Box):
            c, sn = math.cos(sh.rot), math.sin(sh.rot)
            pts = []
            for z in (0.0, sh.sz):
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    lx, ly = x * sh.sx / 2, y * sh.sy / 2
                    pts.append((sh.x + lx * c - ly * sn, sh.y + lx * sn + ly * c, sh.z + z))
            self.box8(pts, mat)
        elif isinstance(sh, S.Beam):
            p0, p1, side, u = _frame(sh.p0, sh.p1)
            pts = []
            for p in (p0, p1):
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    pts.append(p + side * x * sh.w / 2 + u * y * sh.h / 2)
            self.box8(pts, mat)
        elif isinstance(sh, S.Tube):
            p0, p1, side, u = _frame(sh.p0, sh.p1)
            n = max(3, sh.seg)
            ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
            ring = np.outer(np.cos(ang), side) + np.outer(np.sin(ang), u)
            pts = np.concatenate([p0 + ring * sh.r, p1 + ring * sh.r])
            faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
            self._add(pts, faces, mat, smooth=True)
            base = self.n - 2 * n
            for f in (tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))):     # caps: flat
                self.faces.append(tuple(base + i for i in f))
                self.mats.append(mat)
                self.smooth.append(False)
        elif isinstance(sh, S.Sphere):
            n, m = max(6, sh.seg), max(4, sh.seg // 2)
            c = np.asarray(sh.c, float)
            pts = [c + (0, 0, -sh.r)]
            for j in range(1, m):
                lat = -math.pi / 2 + math.pi * j / m
                for i in range(n):
                    lon = 2 * math.pi * i / n
                    pts.append(c + sh.r * np.array((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                                                     math.sin(lat))))
            pts.append(c + (0, 0, sh.r))
            top = len(pts) - 1
            faces = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
            for j in range(m - 2):
                a, b = 1 + j * n, 1 + (j + 1) * n
                faces += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
            a = 1 + (m - 2) * n
            faces += [(a + i, a + (i + 1) % n, top) for i in range(n)]
            self._add(pts, faces, mat, smooth=True)
        elif isinstance(sh, S.Quad):
            self._add(sh.pts, [(0, 1, 2, 3)], mat)

    def to_mesh(self, name: str) -> bpy.types.Mesh:
        me = bpy.data.meshes.new(name)
        verts = np.concatenate(self.verts) if self.verts else np.zeros((0, 3))
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
        sizes = np.array([len(f) for f in self.faces], dtype=np.int32)
        loops = np.fromiter((i for f in self.faces for i in f), dtype=np.int32, count=int(sizes.sum()))
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(self.faces))
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
        me.polygons.foreach_set("loop_start", starts)
        me.polygons.foreach_set("material_index", np.array(self.mats, dtype=np.int32))
        me.update(calc_edges=True)
        me.polygons.foreach_set("use_smooth", np.array(self.smooth, dtype=bool))
        me.validate(clean_customdata=False)
        return me


def _new_object(name: str, me, role: str, col, parent) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.parent = parent
    ob[TAG] = role
    ob.hide_select = True
    vis = _VISIBILITY.get(role)
    if vis is not None:
        (ob.visible_camera, ob.visible_diffuse, ob.visible_glossy, ob.visible_transmission,
         ob.visible_shadow) = vis
    if role in ("shell", "photo_dome"):
        ob.display_type = "WIRE"           # the view stays clear when you look from outside
    return ob


def _shapes_object(name, role, shapes, col, parent) -> bpy.types.Object:
    keys = sorted({sh.mat for sh in shapes})
    index = {k: i for i, k in enumerate(keys)}
    m = _Mesh()
    for sh in shapes:
        m.shape(sh, index[sh.mat])
    me = m.to_mesh(name)
    for k in keys:
        me.materials.append(material(k))
    return _new_object(name, me, role, col, parent)


# =============================================================================
# materials (procedural)
# =============================================================================


def _ral(code: str):
    parsed = ral.parse_colour(code)
    srgb = parsed[1] if parsed else (0.7, 0.7, 0.7)
    return tuple(ral.srgb_to_linear(c) for c in srgb)


def _srgb(*rgb):
    return tuple(ral.srgb_to_linear(c) for c in rgb)


class _NT:
    """Small helper to write node trees."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = -1200

    def node(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(n, k[1:], v)
            else:
                self.set(n, k, v)
        return n

    def set(self, n, name, v):
        if hasattr(v, "bl_idname") or isinstance(v, bpy.types.NodeSocket):
            self.link(v, n.inputs[name])
        else:
            n.inputs[name].default_value = v

    def link(self, a, b):
        self.nt.links.new(a, b)


def _coords(t: _NT, scale=1.0):
    tc = t.node("ShaderNodeTexCoord")
    if scale == 1.0:
        return tc.outputs["Object"]
    vm = t.node("ShaderNodeVectorMath", _operation="SCALE", Vector=tc.outputs["Object"], Scale=scale)
    return vm.outputs["Vector"]


def _noise(t: _NT, scale, detail=4.0, roughness=0.55, vec=None):
    n = t.node("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=roughness)
    if vec is not None:
        t.link(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _ramp(t: _NT, fac, a, b, pa=0.3, pb=0.7):
    r = t.node("ShaderNodeMapRange", Value=fac, **{"From Min": pa, "From Max": pb, "To Min": a, "To Max": b})
    return r.outputs["Result"]


def _mix_color(t: _NT, fac, a, b):
    """Colour a where fac = 0, b where fac = 1 (a and b: colours or colour sockets)."""
    m = t.node("ShaderNodeMix", _data_type="RGBA")
    for i, v in ((0, fac), (6, a), (7, b)):            # 0 factor, 6 colour A, 7 colour B
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, m.inputs[i])
        elif isinstance(v, tuple):
            m.inputs[i].default_value = (*v[:3], 1.0)
        else:
            m.inputs[i].default_value = v
    return m.outputs[2]


def _lines(t: _NT, pitch_x=0.0, pitch_y=0.0, width=0.01, axis_z=0.0):
    """1 on thin lines every ``pitch`` metres (seams, joints) along object x and/or y, else 0."""
    tc = t.node("ShaderNodeTexCoord")
    sep = t.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    result = None
    for comp, pitch in (("X", pitch_x), ("Y", pitch_y), ("Z", axis_z)):
        if pitch <= 0:
            continue
        d = t.node("ShaderNodeMath", _operation="DIVIDE", Value=sep.outputs[comp])
        d.inputs[1].default_value = pitch
        f = t.node("ShaderNodeMath", _operation="FRACT", Value=d.outputs[0])
        c = t.node("ShaderNodeMath", _operation="PINGPONG", Value=f.outputs[0])
        c.inputs[1].default_value = 0.5
        lt = t.node("ShaderNodeMath", _operation="LESS_THAN", Value=c.outputs[0])
        lt.inputs[1].default_value = width / pitch / 2
        if result is None:
            result = lt.outputs[0]
        else:
            mx = t.node("ShaderNodeMath", _operation="MAXIMUM", Value=result)
            t.link(lt.outputs[0], mx.inputs[1])
            result = mx.outputs[0]
    return result


def _bump(t: _NT, height, strength=0.3, distance=0.02):
    b = t.node("ShaderNodeBump", Strength=strength, Distance=distance, Height=height)
    return b.outputs["Normal"]


def _principled(t: _NT, color, rough, metal=0.0, normal=None, **extra):
    p = t.node("ShaderNodeBsdfPrincipled")
    t.set(p, "Base Color", color if not isinstance(color, tuple) else (*color[:3], 1.0))
    t.set(p, "Roughness", rough)
    p.inputs["Metallic"].default_value = metal
    if normal is not None:
        t.link(normal, p.inputs["Normal"])
    for k, v in extra.items():
        t.set(p, k.replace("_", " "), v)
    return p.outputs["BSDF"]


def _emission(t: _NT, color, strength):
    e = t.node("ShaderNodeEmission", Color=(*color, 1.0), Strength=strength)
    return e.outputs["Emission"]


def _output(t: _NT, shader, one_sided: bool = False):
    if one_sided:                   # seen from behind: see-through (halls seen from outside)
        geo = t.node("ShaderNodeNewGeometry")
        tr = t.node("ShaderNodeBsdfTransparent")
        mix = t.node("ShaderNodeMixShader", Fac=geo.outputs["Backfacing"])
        t.link(shader, mix.inputs[1])
        t.link(tr.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])


def _paint(t, color, rough=0.45, var=0.04, scale=3.0, normal=None):
    """Painted surface with a little colour and gloss variation."""
    n = _noise(t, scale, 3.0, 0.5, _coords(t))
    col = _mix_color(t, _ramp(t, n, 0.0, 1.0), tuple(c * (1 - var) for c in color), tuple(min(1.0, c * (1 + var)) for c in color))
    return _principled(t, col, _ramp(t, n, rough * 0.85, rough * 1.15), normal=normal)


def _make(key: str, mat) -> None:
    t = _NT(mat)
    one_sided = False
    emission = False
    if key in ("floor_epoxy", "floor_epoxy_green"):
        base = _srgb(0.70, 0.71, 0.70) if key == "floor_epoxy" else _srgb(0.42, 0.52, 0.47)
        n = _noise(t, 0.6, 4.0, 0.6, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1), tuple(c * 0.93 for c in base), base)
        shader = _principled(t, col, _ramp(t, _noise(t, 2.0, 3.0, 0.5, _coords(t)), 0.14, 0.32),
                             Coat_Weight=0.3, Coat_Roughness=0.08)
    elif key in ("floor_concrete", "concrete"):
        base = _srgb(0.62, 0.61, 0.58) if key == "floor_concrete" else _srgb(0.6, 0.59, 0.56)
        n = _noise(t, 0.35, 6.0, 0.65, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1, 0.35, 0.65), tuple(c * 0.78 for c in base), base)
        joints = _lines(t, 6.0, 6.0, 0.012)
        col = _mix_color(t, joints, col, (0.12, 0.12, 0.12))
        if key == "concrete":            # wet and darker towards the water line
            sep = t.node("ShaderNodeSeparateXYZ", Vector=t.node("ShaderNodeTexCoord").outputs["Object"])
            wet = t.node("ShaderNodeMapRange", Value=sep.outputs["Z"], **{"From Min": -0.3, "From Max": -1.5,
                                                                          "To Min": 0.0, "To Max": 0.7})
            col = _mix_color(t, wet.outputs[0], col, (0.08, 0.085, 0.08))
        shader = _principled(t, col, _ramp(t, n, 0.55, 0.85), normal=_bump(t, joints, 0.4, 0.01))
    elif key == "deck":
        base = _srgb(0.33, 0.38, 0.36)
        n = _noise(t, 0.25, 6.0, 0.6, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1, 0.3, 0.75), tuple(c * 0.75 for c in base), base)
        seams = _lines(t, 6.0, 1.8, 0.02)
        grit = _noise(t, 60.0, 2.0, 0.5, _coords(t))
        h = t.node("ShaderNodeMath", _operation="MULTIPLY_ADD", Value=seams)
        h.inputs[1].default_value = 1.0
        t.link(grit, h.inputs[2])
        shader = _principled(t, col, 0.75, normal=_bump(t, h.outputs[0], 0.25, 0.01))
    elif key == "water":
        shader = _water_shader(t, mat)
    elif key in ("wall_panel", "wall_panel_out"):
        seams = _lines(t, 1.0, 1.0, 0.012)
        shader = _principled(t, _srgb(0.86, 0.87, 0.86), 0.5, normal=_bump(t, seams, 0.4, 0.01))
        one_sided = key == "wall_panel"
    elif key == "wall_dado":
        shader = _principled(t, _ral("RAL 7016"), 0.45)
        one_sided = True
    elif key == "roof":
        ribs = _lines(t, 0.0, 0.33, 0.06)
        shader = _principled(t, _srgb(0.7, 0.71, 0.71), 0.5, metal=0.5, normal=_bump(t, ribs, 0.5, 0.02))
        one_sided = True
    elif key == "door":
        slats = _lines(t, 0.0, 0.0, 0.015, axis_z=0.12)
        shader = _principled(t, _ral("RAL 9006"), 0.4, metal=0.6, normal=_bump(t, slats, 0.5, 0.01))
        one_sided = True
    elif key == "window":
        shader = _emission(t, (0.85, 0.92, 1.0), 1.6)
        one_sided = emission = True
    elif key == "skylight":
        shader = _emission(t, (0.95, 0.97, 1.0), 2.5)
        one_sided = emission = True
    elif key == "light":
        shader = _emission(t, (1.0, 0.97, 0.92), 6.0)
        emission = True
    elif key in ("galvanized", "rail_steel", "light_housing"):
        base = {"galvanized": (0.62, 0.64, 0.65), "rail_steel": (0.42, 0.42, 0.42),
                "light_housing": (0.8, 0.8, 0.8)}[key]
        n = _noise(t, 4.0, 4.0, 0.6, _coords(t))
        shader = _principled(t, base, _ramp(t, n, 0.25, 0.45), metal=1.0)
    elif key in ("container_blue", "container_red", "container_green", "container_white", "container_grey"):
        colour = {"container_blue": "RAL 5010", "container_red": "RAL 3009", "container_green": "RAL 6005",
                  "container_white": "RAL 9002", "container_grey": "RAL 7037"}[key]
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", _wave_profile="SIN",
                      Scale=3.6, Vector=_coords(t))
        shader = _paint(t, _ral(colour), 0.5, 0.06, 1.5, normal=_bump(t, wave.outputs["Fac"], 0.6, 0.03))
    elif key == "kerb" or key == "barrier":
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS",
                      _bands_direction="X" if key == "kerb" else "DIAGONAL", _wave_profile="SAW",
                      Scale=0.6 if key == "kerb" else 1.5, Vector=_coords(t))
        stripe = t.node("ShaderNodeMath", _operation="GREATER_THAN", Value=wave.outputs["Fac"])
        stripe.inputs[1].default_value = 0.5
        other = (0.02, 0.02, 0.02) if key == "kerb" else (0.85, 0.85, 0.85)
        first = _ral("RAL 1023") if key == "kerb" else _ral("RAL 3020")
        shader = _principled(t, _mix_color(t, stripe.outputs[0], first, other), 0.45)
    elif key == "wood":
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", Scale=6.0, Distortion=6.0,
                      Detail=3.0, Vector=_coords(t))
        col = _mix_color(t, _ramp(t, wave.outputs["Fac"], 0, 1, 0.2, 0.9), _srgb(0.56, 0.42, 0.26), _srgb(0.74, 0.6, 0.4))
        shader = _principled(t, col, 0.75)
    elif key == "hull":
        shader = _paint(t, _ral("RAL 5011"), 0.35)
    elif key == "hull_red":
        shader = _paint(t, _ral("RAL 3011"), 0.4)
    elif key == "glass_dark":
        shader = _principled(t, (0.01, 0.012, 0.014), 0.04, Specular_IOR_Level=0.6)
    elif key == "mannequin":
        shader = _principled(t, _srgb(0.68, 0.68, 0.69), 0.55)
    else:
        colours = {
            "steel_column": ("RAL 7035", 0.45), "crane_yellow": ("RAL 1003", 0.4), "rail_yellow": ("RAL 1003", 0.4),
            "line_yellow": ("RAL 1023", 0.5), "line_white": ("RAL 9016", 0.5), "bollard": ("RAL 9005", 0.5),
            "rubber": ("#1A1A1A", 0.85), "machine_body": ("RAL 7035", 0.35), "machine_dark": ("RAL 7016", 0.4),
            "machine_blue": ("RAL 5015", 0.35), "cabinet_grey": ("RAL 7035", 0.4), "cabinet_red": ("RAL 3000", 0.35),
            "rack_blue": ("RAL 5010", 0.4), "rack_orange": ("RAL 2004", 0.4), "cardboard": ("#A07A4E", 0.85),
            "wrap": ("#D8DCDF", 0.2), "bin_blue": ("RAL 5015", 0.35), "bench_top": ("#B08A5E", 0.5),
            "primer": ("RAL 3009", 0.6), "deckhouse": ("RAL 9010", 0.4), "lamp_head": ("RAL 7037", 0.45),
            "container_frame": ("RAL 7021", 0.5), "barrier_frame": ("RAL 1023", 0.4),
        }
        colour, rough = colours.get(key, ("RAL 7035", 0.5))
        shader = _paint(t, _ral(colour), rough)
    _output(t, shader, one_sided)
    mat.use_backface_culling = one_sided
    if emission:
        for owner in (mat, getattr(mat, "cycles", None)):
            if owner is not None and hasattr(owner, "emission_sampling"):
                owner.emission_sampling = "NONE"     # looks bright, but does not light the scene (no extra noise)
                break


def material(key: str) -> bpy.types.Material:
    name = MAT_PREFIX + key
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    _make(key, mat)
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = key
    return mat


# =============================================================================
# the sea
# =============================================================================

SEA = {
    # swell amplitude (m, sum of the waves), wavelengths (m), ripple bump strength, foam threshold
    "CALM": dict(amp=0.25, lengths=(55.0, 38.0, 27.0, 19.0, 13.0), bump=0.12, chop=0.6, foam=0.82),
    "ROUGH": dict(amp=1.6, lengths=(70.0, 48.0, 33.0, 22.0, 15.0, 9.0), bump=0.35, chop=1.6, foam=0.55),
}


def _waves(state: str) -> list[tuple[float, float, float, float, float]]:
    """(amplitude, direction x, direction y, wave number, phase) of each swell component."""
    p = SEA[state]
    rng = random.Random(42)
    total = sum(1.0 / i for i in range(1, len(p["lengths"]) + 1))
    out = []
    for i, length in enumerate(p["lengths"], 1):
        ang = math.radians(25.0 + rng.uniform(-35.0, 35.0))
        out.append((p["amp"] / i / total, math.cos(ang), math.sin(ang), 2 * math.pi / length, rng.uniform(0, 6.28)))
    return out


def _sea_rings(detailed: bool, near: float) -> tuple[int, list[float]]:
    n = 256 if detailed else 48
    rings = []
    if detailed:
        r = 0.4
        step = 1 + 2 * math.pi / n
        while r < near * 1.6:
            rings.append(r)
            r *= step
    else:
        rings = [0.5]
    r = rings[-1]
    while r < S.SEA_RADIUS:
        r = min(S.SEA_RADIUS, r * 1.45)
        rings.append(r)
    return n, rings


def _sea_mesh(name: str, detailed: bool, near: float) -> bpy.types.Mesh:
    n, rings = _sea_rings(detailed, near)
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    R = np.array(rings)
    rim = np.clip((R - 0.75 * S.SEA_RADIUS) / (0.25 * S.SEA_RADIUS), 0, 1)
    z = S.SEA_RIM * rim * rim                     # the far edge rises: no gap below the horizon
    verts = [np.zeros((1, 3))]
    for r, zz in zip(R, z):
        verts.append(np.stack([r * np.cos(ang), r * np.sin(ang), np.full(n, zz)], axis=1))
    verts = np.concatenate(verts)
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    for j in range(len(rings) - 1):
        a, b = 1 + j * n, 1 + (j + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]
    m = _Mesh()
    m._add(verts, faces, 0, smooth=True)
    return m.to_mesh(name)


def _time_driver(owner, path: str, scene, speed: float, index: int = -1) -> None:
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    d = fc.driver
    d.type = "SCRIPTED"
    while d.variables:
        d.variables.remove(d.variables[0])
    v = d.variables.new()
    v.name = "fps"
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = "SCENE"
    v.targets[0].id = scene
    v.targets[0].data_path = "render.fps"
    d.expression = f"frame / max(fps, 1) * {speed:.5f}"


def _waves_group(state: str, moving: bool, near: float) -> bpy.types.NodeTree:
    """Geometry nodes: swell (a sum of travelling sine waves) near the machine, flat far away."""
    name = f"{WAVES_GROUP} {state.lower()}{' moving' if moving else ''} {near:.0f}"
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng["fr_env"] = "waves"
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = ng.nodes, ng.links
    gin = nodes.new("NodeGroupInput")
    gout = nodes.new("NodeGroupOutput")
    pos = nodes.new("GeometryNodeInputPosition")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(pos.outputs[0], sep.inputs[0])
    if moving:
        tnode = nodes.new("GeometryNodeInputSceneTime")
        t = tnode.outputs["Seconds"]
    else:
        tnode = nodes.new("ShaderNodeValue")
        tnode.outputs[0].default_value = 0.0
        t = tnode.outputs[0]

    def math_node(op, a, b=None, c=None):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                links.new(v, n.inputs[i])
        return n.outputs[0]

    total = None
    amp_sum = 0.0
    for a, dx, dy, k, ph in _waves(state):
        omega = math.sqrt(9.81 * k)
        along = math_node("MULTIPLY_ADD", sep.outputs["X"], dx * k, math_node("MULTIPLY", sep.outputs["Y"], dy * k))
        phase = math_node("MULTIPLY_ADD", t, -omega, math_node("ADD", along, ph))
        h = math_node("MULTIPLY", math_node("SINE", phase), a)
        total = h if total is None else math_node("ADD", total, h)
        amp_sum += a
    # fade out between 'near' and 1.6 x near: far away the material's ripples take over
    r = math_node("SQRT", math_node("MULTIPLY_ADD", sep.outputs["X"], sep.outputs["X"],
                                    math_node("MULTIPLY", sep.outputs["Y"], sep.outputs["Y"])))
    fade = nodes.new("ShaderNodeMapRange")
    fade.interpolation_type = "SMOOTHSTEP"
    links.new(r, fade.inputs["Value"])
    fade.inputs["From Min"].default_value = near
    fade.inputs["From Max"].default_value = near * 1.6
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.0
    height = math_node("MULTIPLY", total, fade.outputs["Result"])
    off = nodes.new("ShaderNodeCombineXYZ")
    links.new(height, off.inputs["Z"])
    setp = nodes.new("GeometryNodeSetPosition")
    links.new(gin.outputs[0], setp.inputs["Geometry"])
    links.new(off.outputs[0], setp.inputs["Offset"])
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT"
    store.domain = "POINT"
    store.inputs["Name"].default_value = "fr_crest"
    links.new(setp.outputs[0], store.inputs["Geometry"])
    links.new(math_node("DIVIDE", height, max(amp_sum, 1e-3)), store.inputs["Value"])
    links.new(store.outputs[0], gout.inputs[0])
    return ng


def _water_shader(t: _NT, mat):
    p = SEA.get(mat.get("fr_sea_state", "CALM"), SEA["CALM"])
    tc = t.node("ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    ripple = t.node("ShaderNodeTexNoise", _noise_dimensions="4D", Scale=0.35, Detail=6.0, Roughness=0.62,
                    Vector=co)
    ripple.name = "fr_ripple"
    swell = t.node("ShaderNodeTexNoise", _noise_dimensions="4D", Scale=0.03, Detail=2.0, Roughness=0.5, Vector=co)
    swell.name = "fr_swell"
    h = t.node("ShaderNodeMath", _operation="MULTIPLY_ADD", Value=swell.outputs["Fac"])
    h.inputs[1].default_value = p["chop"] * 2.0
    t.link(ripple.outputs["Fac"], h.inputs[2])
    normal = _bump(t, h.outputs[0], p["bump"], 0.5)
    base = (0.006, 0.03, 0.035)
    foam = None
    if mat.get("fr_foam"):
        crest = t.node("ShaderNodeAttribute", _attribute_name="fr_crest")
        f_noise = t.node("ShaderNodeTexNoise", _noise_dimensions="4D", Scale=0.25, Detail=8.0, Roughness=0.7,
                         Vector=co)
        f_noise.name = "fr_foam"
        mix = t.node("ShaderNodeMath", _operation="MULTIPLY_ADD", Value=crest.outputs["Fac"])
        mix.inputs[1].default_value = 0.35
        t.link(f_noise.outputs["Fac"], mix.inputs[2])
        foam_r = t.node("ShaderNodeMapRange", Value=mix.outputs[0],
                        **{"From Min": p["foam"], "From Max": p["foam"] + 0.12, "To Min": 0.0, "To Max": 1.0})
        foam = foam_r.outputs["Result"]
    if foam is not None:
        col = _mix_color(t, foam, base, (0.75, 0.78, 0.8))
        rough = t.node("ShaderNodeMapRange", Value=foam, **{"To Min": 0.03, "To Max": 0.6}).outputs["Result"]
    else:
        col, rough = base, 0.03
    return _principled(t, col, rough, normal=normal, IOR=1.333)


def _water_material(scene, state: str, foam: bool, moving: bool) -> bpy.types.Material:
    name = f"{MAT_PREFIX}water {state.lower()}{' foam' if foam else ''}{' moving' if moving else ''}"
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat["fr_sea_state"] = state
    mat["fr_foam"] = foam
    try:
        mat.use_nodes = True
    except Exception:
        pass
    _make("water", mat)
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "water"
    nodes = mat.node_tree.nodes
    for node_name, speed in (("fr_ripple", 0.35), ("fr_swell", 0.08), ("fr_foam", 0.3)):
        node = nodes.get(node_name)
        if node is None:
            continue
        if moving:
            _time_driver(node.inputs["W"], "default_value", scene, speed)
        else:
            node.inputs["W"].default_value = 0.0
    return mat


def _build_sea(s, col, root, level: float, machine_size: float, kind: str) -> bpy.types.Object:
    detailed = s.env_detail == "DETAILED"
    near = max(40.0, 5.0 * machine_size)
    me = _sea_mesh("FR Sea", detailed, near)
    me.materials.append(_water_material(bpy.context.scene, s.sea_state, bool(s.sea_foam), bool(s.sea_moving)))
    ob = _new_object("FR Sea", me, "sea", col, root)
    ob.location.z = level
    if kind == "QUAY":
        ob.location.y = 0.0
    if detailed:
        mod = ob.modifiers.new("Waves", "NODES")
        mod.node_group = _waves_group(s.sea_state, bool(s.sea_moving), near)
    return ob


# =============================================================================
# the ground of a 360° photo
# =============================================================================


def _irradiance(img) -> tuple[float, float, float]:
    """Light falling on flat ground from the photo's upper half (per colour), at strength 1.

    The photo's ground is shown as a matte floor whose colour is photo × π / this, so where no
    shadow falls it looks exactly like the photo, and the machine's shadow darkens it."""
    key = f"{bpy.path.abspath(img.filepath)}|{img.size[0]}x{img.size[1]}"
    if img.get("fr_irr_key") == key:
        return tuple(img["fr_irr"])
    w, h = img.size
    work = img
    if w > 1024:
        work = img.copy()
        work.scale(1024, 512)
        w, h = 1024, 512
    px = np.empty(w * h * 4, dtype=np.float32)
    work.pixels.foreach_get(px)
    if work is not img:
        bpy.data.images.remove(work)
    px = px.reshape(h, w, 4)[:, :, :3].astype(np.float64)
    v = (np.arange(h) + 0.5) / h
    lat = (v - 0.5) * math.pi
    weight = np.where(lat > 0, np.sin(lat) * np.cos(lat), 0.0) * (math.pi / h) * (2 * math.pi / w)
    e = (px * weight[:, None, None]).sum(axis=(0, 1))
    e = tuple(float(max(x, 1e-4)) for x in e)
    img["fr_irr"] = e
    img["fr_irr_key"] = key
    return e


def _photo_direction(t: _NT, origin_z: float):
    """Direction from the photo's camera point (above the floor centre) to the shaded point."""
    geo = t.node("ShaderNodeNewGeometry")
    sub = t.node("ShaderNodeVectorMath", _operation="SUBTRACT", Vector=geo.outputs["Position"])
    sub.name = "fr_origin"
    sub.inputs[1].default_value = (0.0, 0.0, origin_z)
    norm = t.node("ShaderNodeVectorMath", _operation="NORMALIZE", Vector=sub.outputs["Vector"])
    mapping = t.node("ShaderNodeMapping", Vector=norm.outputs["Vector"])
    mapping.name = "fr_turn"
    env = t.node("ShaderNodeTexEnvironment")
    env.name = "fr_photo"
    t.link(mapping.outputs["Vector"], env.inputs["Vector"])
    return env


def _photo_materials(s, img):
    dome = bpy.data.materials.get(MAT_PREFIX + "photo dome") or bpy.data.materials.new(MAT_PREFIX + "photo dome")
    ground = bpy.data.materials.get(MAT_PREFIX + "photo ground") or bpy.data.materials.new(MAT_PREFIX + "photo ground")
    for mat in (dome, ground):
        try:
            mat.use_nodes = True
        except Exception:
            pass
    t = _NT(dome)
    env = _photo_direction(t, 0.0)
    em = t.node("ShaderNodeEmission")
    em.name = "fr_strength"
    t.link(env.outputs["Color"], em.inputs["Color"])
    _output(t, em.outputs[0], one_sided=True)
    dome.use_backface_culling = True
    t = _NT(ground)
    env = _photo_direction(t, 0.0)
    scale = t.node("ShaderNodeVectorMath", _operation="MULTIPLY", Vector=env.outputs["Color"])
    scale.name = "fr_albedo"
    diff = t.node("ShaderNodeBsdfDiffuse")
    t.link(scale.outputs["Vector"], diff.inputs["Color"])
    _output(t, diff.outputs[0])
    for mat in (dome, ground):
        mat["fr_env"] = "photo"
    return dome, ground


def _photo_update(s) -> None:
    """Photo, turn, strength and height in the dome and ground materials (no rebuild)."""
    path = _photo_path(s)
    if not path:
        return
    from . import world
    img = world._load_hdri(path)
    if img is None:
        return
    e = _irradiance(img)
    for name in ("photo dome", "photo ground"):
        mat = bpy.data.materials.get(MAT_PREFIX + name)
        if mat is None:
            continue
        nodes = mat.node_tree.nodes
        if nodes["fr_photo"].image != img:
            nodes["fr_photo"].image = img
        turn = (0.0, 0.0, math.radians(s.light_rotation))
        if tuple(nodes["fr_turn"].inputs["Rotation"].default_value) != turn:
            nodes["fr_turn"].inputs["Rotation"].default_value = turn
        origin = (0.0, 0.0, s.photo_height)
        if tuple(nodes["fr_origin"].inputs[1].default_value) != origin:
            nodes["fr_origin"].inputs[1].default_value = origin
        if "fr_strength" in nodes and nodes["fr_strength"].inputs["Strength"].default_value != s.light_strength:
            nodes["fr_strength"].inputs["Strength"].default_value = s.light_strength
        if "fr_albedo" in nodes:
            alb = tuple(math.pi / x for x in e)
            if tuple(nodes["fr_albedo"].inputs[1].default_value) != alb:
                nodes["fr_albedo"].inputs[1].default_value = alb


def _build_photo(scene, s, root, col, size) -> float:
    """A dome around the scene with the photo on it, its lower part flattened onto the floor."""
    from . import world
    img = world._load_hdri(_photo_path(s))
    radius = max(40.0, 3.0 * float(max(size)))
    h = max(0.05, s.photo_height)
    dome_mat, ground_mat = _photo_materials(s, img)
    # dome: the part of a sphere around the photo's camera point that is above the floor
    n, m = 64, 24
    c = np.array([0.0, 0.0, h])
    lat0 = math.asin(-h / radius)
    pts, faces = [], []
    for j in range(m + 1):
        lat = lat0 + (math.pi / 2 - lat0) * j / m
        for i in range(n):
            lon = 2 * math.pi * i / n
            pts.append(c + radius * np.array((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                                               math.sin(lat))))
    for j in range(m):
        a, b = j * n, (j + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]   # normals inwards
    mesh = _Mesh()
    mesh._add(pts, faces, 0, smooth=True)
    me = mesh.to_mesh("FR Photo dome")
    me.materials.append(dome_mat)
    _new_object("FR Photo dome", me, "photo_dome", col, root)
    # ground: a disc on the floor, out to where the dome meets it
    rg = radius * math.cos(lat0)
    rings = [0.0] + list(np.geomspace(0.5, rg, 24))
    pts = [np.zeros(3)]
    for r in rings[1:]:
        for i in range(n):
            lon = 2 * math.pi * i / n
            pts.append(np.array((r * math.cos(lon), r * math.sin(lon), 0.0)))
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    for j in range(len(rings) - 2):
        a, b = 1 + j * n, 1 + (j + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]
    mesh = _Mesh()
    mesh._add(pts, faces, 0)
    me = mesh.to_mesh("FR Photo ground")
    me.materials.append(ground_mat)
    _new_object("FR Photo ground", me, "photo_ground", col, root)
    _photo_update(s)
    return radius * 2.5


# =============================================================================
# props for scale
# =============================================================================


def props(scene=None) -> list:
    col = bpy.data.collections.get(PROPS_COLLECTION)
    if col is None:
        return []
    return [ob for ob in col.objects if ob.get(PROP_TAG)]


def add_prop(scene, kind: str) -> bpy.types.Object:
    """Put a prop next to the machine (in a row along its right-hand side, on the floor)."""
    from . import logic
    shapes = S.prop_shapes(kind)
    keys = sorted({sh.mat for sh in shapes})
    index = {k: i for i, k in enumerate(keys)}
    m = _Mesh()
    for sh in shapes:
        m.shape(sh, index[sh.mat])
    label = S.PROPS[kind][0]
    me = m.to_mesh(label)
    for k in keys:
        me.materials.append(material(k))
    ob = bpy.data.objects.new(label, me)
    _collection(scene, PROPS_COLLECTION).objects.link(ob)
    ob[PROP_TAG] = kind
    mn, mx = logic.cached_bounds(scene)
    existing = props(scene)
    sizes = []
    for p in existing:
        sx, sy, _sz = S.prop_size(p[PROP_TAG]) if p.get(PROP_TAG) in S.PROPS else (1.0, 1.0, 1.0)
        sizes.append((sx, sy))
    index_new = existing.index(ob)
    x, y = S.prop_spot(index_new, (float(mn[0]), float(mx[0]), float(mn[1]), float(mx[1])), sizes)
    ob.location = (x, y, floor_height(scene))
    show = scene.fresing.props_visible
    ob.hide_render = not show
    ob.hide_viewport = not show
    return ob


def set_props_visible(scene, visible: bool) -> None:
    for ob in props(scene):
        if ob.hide_render == visible:
            ob.hide_render = not visible
        if ob.hide_viewport == visible:
            ob.hide_viewport = not visible


def remove_props(scene) -> int:
    objs = props(scene)
    meshes = {ob.data for ob in objs if ob.data is not None}
    n = len(objs)
    if objs:
        bpy.data.batch_remove(objs)
    orphans = [me for me in meshes if me.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    return n


def put_props_on_floor(scene) -> None:
    z = floor_height(scene)
    for ob in props(scene):
        ob.location.z = z
