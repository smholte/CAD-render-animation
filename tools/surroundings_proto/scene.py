"""Study 0311 prototype: the surroundings maker's scene in Blender (bpy as a module or real Blender).

    ~/venv/bin/python tools/surroundings_proto/scene.py --out DIR [--stage N] [--ground PROC|SCAN] [--shot NAME] ...

Builds: the terrain (heights + 8 paint layers as point attributes, one material that mixes them), a road (ribbon +
kerbs + markings in the material), a pond whose shore comes from the terrain, procedural buildings, and the scatter
(trees, conifers, bushes, grass, rocks) as Geometry Nodes instances with two levels of detail by camera distance and
nothing outside the camera's view. The machine is the Lifting lane's AT-100 in its "Working" pose (saved by
``crane.py``). Everything is made in code; the scanned ground option reads ambientCG CC0 maps (``--tex DIR``).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shapes as SH  # noqa: E402
import terrain as TR  # noqa: E402

GN_NAME = "FR scatter"
LAYER_ATTR = "fr_l_"
SCATTER_ATTR = "fr_s_"
STAGES = ("flat", "hills", "pad", "paint", "road", "buildings", "water", "trees", "grass")   # the maker, in order


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    return 0.0


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


# =============================================================================
# the layout of the prototype scene ("Building site at the edge of a wind farm")
# =============================================================================


PAD = (-9.0, 21.0, -8.0, 8.0)           # the crane's pad (its box -4.8 … 17.6 x, ±4.1 y), flat and free
ROAD = [(-125, -52), (-80, -42), (-40, -26), (-14, -18), (14, -16), (40, -24), (70, -40), (125, -48)]


def make_terrain(stage: int, seed: int = 3) -> tuple[TR.Terrain, np.ndarray | None]:
    """Run the maker's steps up to ``stage`` (the same strokes every time)."""
    t = TR.Terrain(half=130.0, step=0.5)
    line = None
    if stage >= STAGES.index("hills"):
        t.hills(amp=7.0, scale=75.0, seed=seed, flat_inside=22.0)
        t.stroke(lambda x, y: t.dab("raise", x, y, 22.0, 0.45), [(-120, 40), (-100, 80), (-70, 100)], 6.0)
        t.stroke(lambda x, y: t.dab("lower", x, y, 15.0, 0.45), [(-12, 70), (26, 74)], 4.0)   # the pond's hollow
    if stage >= STAGES.index("pad"):
        t.pad = PAD
        t.keep_pad()
    if stage >= STAGES.index("paint"):
        # gravel round the pad (the site), a sand heap, mud tracks, a rock outcrop, concrete for the buildings
        t.stroke(lambda x, y: t.paint("gravel", x, y, 9.0, 1.0, seed=11), [(-12, -8), (24, -8), (24, 10), (-12, 10),
                                                                              (-12, -8)], 3.0)
        for x in np.linspace(-6, 18, 5):
            for y in np.linspace(-4, 6, 3):
                t.paint("gravel", x, y, 8.0, 1.0, seed=12)
        t.paint("sand", -24, 14, 7.0, 1.0)
        t.stroke(lambda x, y: t.paint("mud", x, y, 2.2, 0.85, edge_noise=0.5), [(-10, -16), (-18, -4), (-16, 8),
                                                                                 (-30, 22)], 1.5)
        t.stroke(lambda x, y: t.paint("rock", x, y, 6.0, 1.0, edge_noise=0.6), [(-60, 60), (-50, 66)], 4.0)
        t.paint("concrete", -42, 30, 15.0, 1.0, edge_noise=0.05)
        t.paint("concrete", 44, 4, 13.0, 1.0, edge_noise=0.05)
    if stage >= STAGES.index("road"):
        line = t.road(ROAD, 7.0, shoulder=4.0)
    if stage >= STAGES.index("water"):
        t.water_level = -1.2
        t.water_seed = (8.0, 72.0)
        dep = t.depth()
        near = TR.grow(dep > 0, 8)                                           # within 4 m of this water only
        t.set_weight("sand", TR.smoothstep(-0.9, -0.2, dep) * near)          # the shore: sand above the water line
        t.set_weight("mud", TR.smoothstep(-0.15, 0.3, dep))                   # and mud under it
    if stage >= STAGES.index("trees"):
        t.stroke(lambda x, y: t.paint_scatter("tree", x, y, 14.0, 1.0), [(-125, 95), (-60, 110), (0, 100), (60, 112),
                                                                          (125, 100)], 6.0)
        t.stroke(lambda x, y: t.paint_scatter("tree", x, y, 10.0, 0.6), [(-110, 40), (-90, 62), (-80, 90)], 5.0)
        t.stroke(lambda x, y: t.paint_scatter("bush", x, y, 6.0, 1.0), [(-60, -12), (-30, -4), (-28, 20)], 3.0)
        t.stroke(lambda x, y: t.paint_scatter("bush", x, y, 7.0, 1.0), [(-22, 62), (8, 88), (36, 64)], 3.0)
        t.stroke(lambda x, y: t.paint_scatter("rock", x, y, 9.0, 1.0), [(-62, 58), (-48, 68)], 3.0)
        t.paint_scatter("rock", 30, 20, 6.0, 0.5)
    if stage >= STAGES.index("grass"):
        t.scatter["grass"][:] = 1.0          # "grass where the ground is grass": the layer decides
    return t, line


# =============================================================================
# meshes
# =============================================================================


def mesh_from(name: str, buf: SH.MeshBuf, mats: dict) -> bpy.types.Mesh:
    me = bpy.data.meshes.new(name)
    V = buf.verts().astype(np.float32)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.ravel())
    sizes = np.array([len(f) for f in buf.f], np.int32)
    loops = np.fromiter((i for f in buf.f for i in f), np.int32, int(sizes.sum()))
    me.loops.add(len(loops))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(sizes))
    me.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32))
    keys = sorted(set(buf.m))
    me.polygons.foreach_set("material_index", np.array([keys.index(k) for k in buf.m], np.int32))
    me.update(calc_edges=True)
    for k in keys:
        me.materials.append(mats[k]())
    return me


def grid_mesh(name, V, F, attrs: dict, uv=None) -> bpy.types.Mesh:
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    me.loops.add(F.size)
    me.loops.foreach_set("vertex_index", F.astype(np.int32).ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set("loop_start", (np.arange(len(F)) * F.shape[1]).astype(np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
    for k, a in attrs.items():
        at = me.attributes.new(k, "FLOAT", "POINT")
        at.data.foreach_set("value", a.astype(np.float32).ravel())
    if uv is not None:
        lay = me.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", uv[F.ravel()].astype(np.float32).ravel())
    return me


def new_ob(name, me, col=None):
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


# =============================================================================
# materials
# =============================================================================


class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()

    def n(self, kind, inputs=None, **props):
        node = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        for k, v in (inputs or {}).items():
            sock = node.inputs[k]
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, sock)
            else:
                sock.default_value = v
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)


def srgb(*c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


_MATS: dict = {}


def mat(name, build):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    build(NT(m), m)
    _MATS[name] = m
    return m


def principled(t, color, rough, normal=None, **kw):
    p = t.n("ShaderNodeBsdfPrincipled")
    for k, v in (("Base Color", color), ("Roughness", rough), ("Normal", normal)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, p.inputs[k])
        else:
            p.inputs[k].default_value = v
    for k, v in kw.items():
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, p.inputs[k])
        else:
            p.inputs[k].default_value = v
    out = t.n("ShaderNodeOutputMaterial")
    t.link(p.outputs[0], out.inputs[0])
    return p


def simple(name, color, rough=0.5, metal=0.0, **kw):
    return lambda: mat(name, lambda t, m: principled(t, srgb(*color), rough, Metallic=metal, **kw))


def _coords(t, scale=1.0):
    tc = t.n("ShaderNodeTexCoord")
    if scale == 1.0:
        return tc.outputs["Object"]
    return t.n("ShaderNodeVectorMath", {0: tc.outputs["Object"], 1: (scale, scale, scale)}, operation="MULTIPLY").outputs[0]


def _noise(t, vec, scale, detail=4.0, rough=0.55):
    return t.n("ShaderNodeTexNoise", {"Vector": vec, "Scale": scale, "Detail": detail, "Roughness": rough}).outputs["Fac"]


def _mix(t, fac, a, b, kind="RGBA"):
    m = t.n("ShaderNodeMix", data_type=kind)
    i = {"RGBA": (6, 7), "FLOAT": (2, 3), "VECTOR": (4, 5)}[kind]
    t.link(fac, m.inputs[0]) if isinstance(fac, bpy.types.NodeSocket) else setattr(m.inputs[0], "default_value", fac)
    for k, v in zip(i, (a, b)):
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, m.inputs[k])
        else:
            m.inputs[k].default_value = v
    o = {"RGBA": 2, "FLOAT": 0, "VECTOR": 1}[kind]
    return m.outputs[o]


def _maprange(t, v, a, b, c=0.0, d=1.0):
    return t.n("ShaderNodeMapRange", {"Value": v, "From Min": a, "From Max": b, "To Min": c, "To Max": d}).outputs[0]


def _math(t, op, a, b=0.0):
    return t.n("ShaderNodeMath", {0: a, 1: b}, operation=op).outputs[0]


# ---- the ground: one material mixing the painted layers -------------------------------------------------------


def layer_proc(t, name, co):
    """(colour, roughness, height) sockets of one ground layer, procedural."""
    if name == "grass":
        n1 = _noise(t, co, 0.35, 5)
        n2 = _noise(t, co, 6.0, 3)
        c = _mix(t, _maprange(t, n1, 0.35, 0.65), srgb(0.15, 0.22, 0.06), srgb(0.27, 0.32, 0.10))
        c = _mix(t, _maprange(t, n2, 0.55, 0.75, 0, 0.45), c, srgb(0.36, 0.30, 0.20))
        return c, 0.92, _math(t, "MULTIPLY", _noise(t, co, 25.0, 2), 0.6)
    if name == "gravel":
        # two sizes of stones: per-stone colour from the Voronoi cell, rounded tops from the distance to the cell's
        # edge, dark gaps between them
        def stones(scale, seed_shift):
            v = t.n("ShaderNodeVectorMath", {0: co, 1: (seed_shift, seed_shift * 0.7, 0)}, operation="ADD").outputs[0]
            f1 = t.n("ShaderNodeTexVoronoi", {"Vector": v, "Scale": scale, "Randomness": 1.0})
            edge = t.n("ShaderNodeTexVoronoi", {"Vector": v, "Scale": scale, "Randomness": 1.0},
                       feature="DISTANCE_TO_EDGE").outputs["Distance"]
            dome = _maprange(t, edge, 0.0, 0.22)
            tone = t.n("ShaderNodeSeparateColor", {0: f1.outputs["Color"]})
            c = _mix(t, tone.outputs[0], srgb(0.26, 0.25, 0.24), srgb(0.55, 0.52, 0.48))
            c = _mix(t, _maprange(t, tone.outputs[1], 0.7, 0.9), c, srgb(0.52, 0.42, 0.32))
            return c, dome
        c1, d1 = stones(9.0, 0.0)
        c2, d2 = stones(26.0, 13.7)
        big = _maprange(t, _math(t, "SUBTRACT", d1, _math(t, "MULTIPLY", d2, 0.6)), 0.25, 0.4)
        c = _mix(t, big, c2, c1)
        dome = _math(t, "MAXIMUM", d1, _math(t, "MULTIPLY", d2, 0.6))
        c = _mix(t, _maprange(t, dome, 0.0, 0.25), srgb(0.12, 0.11, 0.10), c)     # gaps
        c = _mix(t, _maprange(t, _noise(t, co, 0.4, 3), 0.4, 0.7, 0, 0.4), c, srgb(0.40, 0.35, 0.28))
        return c, 0.75, dome
    if name == "sand":
        w = t.n("ShaderNodeTexWave", {"Vector": co, "Scale": 1.8, "Distortion": 6.0}).outputs["Fac"]
        c = _mix(t, _maprange(t, _noise(t, co, 2.0, 4), 0.4, 0.6), srgb(0.70, 0.60, 0.43), srgb(0.80, 0.71, 0.53))
        return c, 0.9, _math(t, "MULTIPLY", w, 0.4)
    if name == "asphalt":
        c = _mix(t, _maprange(t, _noise(t, co, 80.0, 2), 0.3, 0.8), srgb(0.10, 0.10, 0.10), srgb(0.20, 0.20, 0.19))
        return c, 0.8, _math(t, "MULTIPLY", _noise(t, co, 120.0, 1), 0.3)
    if name == "concrete":
        c = _mix(t, _maprange(t, _noise(t, co, 1.5, 5), 0.3, 0.7), srgb(0.52, 0.51, 0.48), srgb(0.64, 0.63, 0.60))
        return c, 0.75, _math(t, "MULTIPLY", _noise(t, co, 40.0, 2), 0.15)
    if name == "rock":
        n = _noise(t, co, 1.2, 6, 0.65)
        c = _mix(t, _maprange(t, n, 0.3, 0.7), srgb(0.30, 0.29, 0.27), srgb(0.55, 0.53, 0.50))
        return c, 0.7, n
    if name == "mud":
        n = _noise(t, co, 3.0, 4)
        c = _mix(t, _maprange(t, n, 0.4, 0.6), srgb(0.17, 0.12, 0.08), srgb(0.26, 0.19, 0.12))
        return c, _maprange(t, n, 0.45, 0.6, 0.5, 0.85), _math(t, "MULTIPLY", n, 0.5)
    c = srgb(0.9, 0.92, 0.95)
    return c, 0.6, _noise(t, co, 3.0, 3)


def layer_scan(t, name, co, tex: dict):
    """(colour, roughness, height-ish, normal) from scanned maps (planar, metres → tiles)."""
    maps = tex[name]
    tile = maps["tile"]
    uv = t.n("ShaderNodeUVMap", uv_map="UVMap").outputs[0]
    uvs = t.n("ShaderNodeVectorMath", {0: uv, 1: (1 / tile, 1 / tile, 1.0)}, operation="MULTIPLY").outputs[0]

    def img(path, non_color):
        im = bpy.data.images.load(path, check_existing=True)
        if non_color:
            im.colorspace_settings.name = "Non-Color"
        return t.n("ShaderNodeTexImage", {"Vector": uvs}, image=im).outputs["Color"]
    col = img(maps["color"], False)
    rough = t.n("ShaderNodeSeparateColor", {0: img(maps["rough"], True)}).outputs[0]
    nrm = t.n("ShaderNodeNormalMap", {"Color": img(maps["normal"], True)}, uv_map="UVMap").outputs[0]
    return col, rough, nrm


def ground_material(used: list[str], mode: str = "PROC", tex: dict | None = None):
    def build(t, m):
        co = _coords(t)
        col = rough = height = normal = None
        for name in used:
            if mode == "SCAN" and tex and name in tex:
                c, r, nrm = layer_scan(t, name, co, tex)
                h = None
            else:
                c, r, h = layer_proc(t, name, co)
                nrm = None
            w = t.n("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=LAYER_ATTR + name).outputs["Fac"]
            # break the painted edge with noise: a soft, natural border
            edge = _math(t, "ADD", w, _math(t, "MULTIPLY", _math(t, "SUBTRACT", _noise(t, co, 1.3, 4), 0.5), 0.7))
            f = _maprange(t, edge, 0.42, 0.58)
            if col is None:
                col, rough, height, normal = c, r, h, nrm
                continue
            col = _mix(t, f, col, c)
            rough = _mix(t, f, rough, r, "FLOAT")
            if h is not None or height is not None:
                height = _mix(t, f, height if height is not None else 0.5, h if h is not None else 0.5, "FLOAT")
            if nrm is not None or normal is not None:
                geo = t.n("ShaderNodeNewGeometry").outputs["Normal"]
                normal = _mix(t, f, normal if normal is not None else geo, nrm if nrm is not None else geo, "VECTOR")
        nb = None
        if height is not None:
            nb = t.n("ShaderNodeBump", {"Height": height, "Strength": 0.6, "Distance": 0.02})
            if normal is not None:
                t.link(normal, nb.inputs["Normal"])
            nb = nb.outputs[0]
        principled(t, col, rough, nb if nb is not None else normal)
    return mat(f"FR ground {mode}", build)


def road_material():
    def build(t, m):
        uv = t.n("ShaderNodeUVMap", uv_map="UVMap").outputs[0]
        sep = t.n("ShaderNodeSeparateXYZ", {0: uv})
        u, v = sep.outputs[0], sep.outputs[1]
        co = _coords(t)
        c, r, h = layer_proc(t, "asphalt", co)
        centre = _math(t, "LESS_THAN", _math(t, "ABSOLUTE", _math(t, "SUBTRACT", u, 0.5)), 0.012)
        dash = _math(t, "LESS_THAN", _math(t, "FLOORED_MODULO", v, 9.0), 3.0)
        edge = _math(t, "GREATER_THAN", _math(t, "ABSOLUTE", _math(t, "SUBTRACT", u, 0.5)), 0.455)
        edge = _math(t, "MULTIPLY", edge, _math(t, "LESS_THAN", _math(t, "ABSOLUTE", _math(t, "SUBTRACT", u, 0.5)), 0.475))
        paint = _math(t, "MAXIMUM", _math(t, "MULTIPLY", centre, dash), edge)
        worn = _maprange(t, _noise(t, co, 3.0, 3), 0.35, 0.6)
        paint = _math(t, "MULTIPLY", paint, worn)
        col = _mix(t, paint, c, srgb(0.85, 0.85, 0.82))
        principled(t, col, _mix(t, paint, r, 0.5, "FLOAT"),
                   t.n("ShaderNodeBump", {"Height": h, "Strength": 0.2, "Distance": 0.01}).outputs[0])
    return mat("FR road", build)


def water_material():
    def build(t, m):
        d = t.n("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="fr_depth").outputs["Fac"]
        co = _coords(t)
        deep = _maprange(t, d, 0.0, 1.2)
        # shallow: clear, tinted (the bottom shows through); deep: almost no diffuse light (it is absorbed)
        col = _mix(t, deep, srgb(0.50, 0.55, 0.42), srgb(0.010, 0.022, 0.020))
        foam = _math(t, "MULTIPLY", _maprange(t, d, 0.07, 0.01), _maprange(t, _noise(t, co, 2.5, 4), 0.45, 0.6))
        n = t.n("ShaderNodeBump", {"Height": _noise(t, co, 6.0, 5), "Strength": 0.3, "Distance": 0.05}).outputs[0]
        water = t.n("ShaderNodeBsdfPrincipled", {"Base Color": col, "Roughness": 0.03, "IOR": 1.33, "Normal": n,
                                                 "Transmission Weight": _maprange(t, d, 0.0, 1.2, 1.0, 0.0)})
        white = t.n("ShaderNodeBsdfPrincipled", {"Base Color": (0.9, 0.9, 0.9, 1), "Roughness": 0.8})
        mix = t.n("ShaderNodeMixShader", {0: foam, 1: water.outputs[0], 2: white.outputs[0]})
        out = t.n("ShaderNodeOutputMaterial")
        t.link(mix.outputs[0], out.inputs[0])
    return mat("FR water", build)


def leaf_material(name, a, b, trans=0.35):
    def build(t, m):
        rnd = t.n("ShaderNodeObjectInfo").outputs["Random"]
        n = _noise(t, _coords(t), 8.0, 2)
        c = _mix(t, _math(t, "ADD", _math(t, "MULTIPLY", rnd, 0.7), _math(t, "MULTIPLY", n, 0.3)), srgb(*a), srgb(*b))
        principled(t, c, 0.55, **{"Subsurface Weight": 0.0, "Transmission Weight": 0.0})
        p = [nd for nd in t.nt.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled"][0]
        tr = t.n("ShaderNodeBsdfTranslucent", {"Color": c})
        mix = t.n("ShaderNodeMixShader", {0: trans, 1: p.outputs[0], 2: tr.outputs[0]})
        out = [nd for nd in t.nt.nodes if nd.bl_idname == "ShaderNodeOutputMaterial"][0]
        t.link(mix.outputs[0], out.inputs[0])
    return lambda: mat(name, build)


def bark_material():
    def build(t, m):
        co = _coords(t)
        w = t.n("ShaderNodeTexWave", {"Vector": co, "Scale": 6.0, "Distortion": 8.0},
                bands_direction="X").outputs["Fac"]
        c = _mix(t, w, srgb(0.16, 0.12, 0.09), srgb(0.30, 0.25, 0.20))
        principled(t, c, 0.85, t.n("ShaderNodeBump", {"Height": w, "Strength": 0.5}).outputs[0])
    return lambda: mat("FR bark", build)


def rock_material():
    def build(t, m):
        co = _coords(t)
        n = _noise(t, co, 2.0, 7, 0.65)
        c = _mix(t, _maprange(t, n, 0.3, 0.7), srgb(0.32, 0.31, 0.29), srgb(0.58, 0.56, 0.52))
        geo = t.n("ShaderNodeNewGeometry").outputs["Normal"]
        up = t.n("ShaderNodeSeparateXYZ", {0: geo}).outputs[2]
        c = _mix(t, _maprange(t, up, 0.6, 0.9, 0, 0.6), c, srgb(0.25, 0.30, 0.13))     # moss on top
        principled(t, c, 0.8, t.n("ShaderNodeBump", {"Height": n, "Strength": 0.6}).outputs[0])
    return lambda: mat("FR rock", build)


def facade_material():
    """One material for every building: its colour is the object's ``fr_colour`` (an OBJECT attribute), so a
    building's colour is a setting, not a new material; vertical cladding ribs as a bump."""
    def build(t, m):
        col = t.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_colour").outputs["Color"]
        co = _coords(t)
        sep = t.n("ShaderNodeSeparateXYZ", {0: co})
        ribs = _math(t, "SINE", _math(t, "MULTIPLY", _math(t, "ADD", sep.outputs[0], sep.outputs[1]), 2 * math.pi / 0.25))
        principled(t, col, 0.45, t.n("ShaderNodeBump", {"Height": ribs, "Strength": 0.15, "Distance": 0.01}).outputs[0])
    return lambda: mat("FR facade", build)


def scene_mats():
    return {
        "leaf": leaf_material("FR leaf", (0.12, 0.22, 0.05), (0.25, 0.36, 0.08)),
        "leaf_crown": leaf_material("FR leaf crown", (0.10, 0.19, 0.05), (0.20, 0.30, 0.07), 0.2),
        "leaf_bush": leaf_material("FR leaf bush", (0.13, 0.24, 0.07), (0.30, 0.38, 0.10)),
        "needles": leaf_material("FR needles", (0.05, 0.12, 0.06), (0.10, 0.20, 0.08), 0.15),
        "grass_blade": leaf_material("FR grass", (0.18, 0.28, 0.07), (0.42, 0.45, 0.16), 0.3),
        "bark": bark_material(),
        "rock": rock_material(),
        "facade": facade_material(),
        "roof": simple("FR roof", (0.30, 0.31, 0.32), 0.5, 0.6),
        "window": simple("FR window", (0.05, 0.07, 0.09), 0.05, 0.0, **{"Coat Weight": 1.0}),
        "skylight": simple("FR skylight", (0.75, 0.78, 0.8), 0.2),
        "door": simple("FR door", (0.62, 0.64, 0.66), 0.4, 0.5),
        "plinth": simple("FR plinth", (0.55, 0.54, 0.51), 0.8),
        "kerb": simple("FR kerb", (0.62, 0.61, 0.58), 0.75),
    }


# =============================================================================
# scatter: Geometry Nodes, two levels of detail, nothing outside the camera's view
# =============================================================================


def _sock(ng, name, io, kind, default=None):
    s = ng.interface.new_socket(name, in_out=io, socket_type=kind)
    if default is not None:
        s.default_value = default
    return s


def scatter_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(GN_NAME)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(GN_NAME, "GeometryNodeTree")
    ins = {}
    for name, kind, default in (("Geometry", "NodeSocketGeometry", None), ("Terrain", "NodeSocketObject", None),
                                ("Attribute", "NodeSocketString", "fr_s_grass"),
                                ("Density", "NodeSocketFloat", 1.0), ("Seed", "NodeSocketInt", 0),
                                ("Detailed", "NodeSocketCollection", None), ("Light", "NodeSocketCollection", None),
                                ("Variants", "NodeSocketInt", 1),
                                ("Scale min", "NodeSocketFloat", 0.8), ("Scale max", "NodeSocketFloat", 1.2),
                                ("Camera", "NodeSocketObject", None), ("Cull", "NodeSocketBool", True),
                                ("Tan x", "NodeSocketFloat", 0.6), ("Tan y", "NodeSocketFloat", 0.35),
                                ("Margin", "NodeSocketFloat", 2.0),
                                ("Detail distance", "NodeSocketFloat", 40.0),
                                ("Thin from", "NodeSocketFloat", 1e6), ("Thin to", "NodeSocketFloat", 2e6),
                                ("Tilt", "NodeSocketFloat", 0.0)):
        ins[name] = _sock(ng, name, "INPUT", kind, default)
    _sock(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    N, L = ng.nodes, ng.links

    def n(kind, inputs=None, **props):
        node = N.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        for k, v in (inputs or {}).items():
            if isinstance(v, bpy.types.NodeSocket):
                L.new(v, node.inputs[k])
            else:
                node.inputs[k].default_value = v
        return node
    gi = n("NodeGroupInput")
    go = n("NodeGroupOutput")
    G = gi.outputs
    terr = n("GeometryNodeObjectInfo", {"Object": G["Terrain"]}, transform_space="RELATIVE")
    dens = n("GeometryNodeInputNamedAttribute", {"Name": G["Attribute"]}, data_type="FLOAT")
    dval = n("ShaderNodeMath", {0: dens.outputs["Attribute"], 1: G["Density"]}, operation="MULTIPLY")
    dist = n("GeometryNodeDistributePointsOnFaces", {"Mesh": terr.outputs["Geometry"], "Density": dval.outputs[0],
                                                     "Seed": G["Seed"]}, distribute_method="RANDOM")
    pos = n("GeometryNodeInputPosition").outputs[0]
    cam = n("GeometryNodeObjectInfo", {"Object": G["Camera"]}, transform_space="ORIGINAL")
    inv = n("FunctionNodeInvertMatrix", {0: cam.outputs["Transform"]})
    pc = n("FunctionNodeTransformPoint", {"Vector": pos, "Transform": inv.outputs[0]})
    sx = n("ShaderNodeSeparateXYZ", {0: pc.outputs[0]})
    depth = n("ShaderNodeMath", {0: sx.outputs[2], 1: -1.0}, operation="MULTIPLY").outputs[0]    # in front: > 0

    def inside(coord, tan):
        lim = n("ShaderNodeMath", {0: depth, 1: tan, 2: G["Margin"]}, operation="MULTIPLY_ADD").outputs[0]
        a = n("ShaderNodeMath", {0: coord}, operation="ABSOLUTE").outputs[0]
        return n("ShaderNodeMath", {0: a, 1: lim}, operation="LESS_THAN").outputs[0]
    front = n("ShaderNodeMath", {0: depth, 1: G["Margin"]}, operation="GREATER_THAN").outputs[0]
    fx = n("FunctionNodeBooleanMath", {0: inside(sx.outputs[0], G["Tan x"]), 1: inside(sx.outputs[1], G["Tan y"])})
    vis = n("FunctionNodeBooleanMath", {0: fx.outputs[0], 1: front})
    keep_cull = n("FunctionNodeBooleanMath", {0: G["Cull"], 1: vis.outputs[0]}, operation="IMPLY")  # cull -> visible
    dcam = n("ShaderNodeVectorMath", {0: pos, 1: cam.outputs["Location"]}, operation="DISTANCE").outputs["Value"]
    # thinning with distance (grass): keep a point with probability falling from 1 to 0 between Thin from / to
    keep_p = n("ShaderNodeMapRange", {"Value": dcam, "From Min": G["Thin from"], "From Max": G["Thin to"],
                                      "To Min": 1.0, "To Max": 0.0}).outputs[0]
    rnd = n("FunctionNodeRandomValue", {"Min": 0.0, "Max": 1.0, "Seed": 7}, data_type="FLOAT").outputs[0]
    thin_ok = n("ShaderNodeMath", {0: rnd, 1: keep_p}, operation="LESS_THAN").outputs[0]
    keep = n("FunctionNodeBooleanMath", {0: keep_cull.outputs[0], 1: thin_ok})
    gone = n("FunctionNodeBooleanMath", {0: keep.outputs[0]}, operation="NOT")
    pts = n("GeometryNodeDeleteGeometry", {"Geometry": dist.outputs["Points"], "Selection": gone.outputs[0]},
            domain="POINT")
    near = n("ShaderNodeMath", {0: dcam, 1: G["Detail distance"]}, operation="LESS_THAN").outputs[0]
    far = n("FunctionNodeBooleanMath", {0: near}, operation="NOT").outputs[0]
    az = n("FunctionNodeRandomValue", {"Min": 0.0, "Max": 2 * math.pi, "Seed": 3}, data_type="FLOAT").outputs[0]
    tilt = n("FunctionNodeRandomValue", {"Min": -1.0, "Max": 1.0, "Seed": 9}, data_type="FLOAT").outputs[0]
    tx = n("ShaderNodeMath", {0: tilt, 1: G["Tilt"]}, operation="MULTIPLY").outputs[0]
    eul = n("ShaderNodeCombineXYZ", {"X": tx, "Y": tx, "Z": az})
    rot = n("FunctionNodeEulerToRotation", {0: eul.outputs[0]})
    sc = n("FunctionNodeRandomValue", {"Min": G["Scale min"], "Max": G["Scale max"], "Seed": 5},
           data_type="FLOAT").outputs[0]
    var = n("FunctionNodeRandomValue", {"Min": 0, "Max": 1000, "Seed": 11}, data_type="INT").outputs[0]
    vi = n("ShaderNodeMath", {0: var, 1: G["Variants"]}, operation="FLOORED_MODULO").outputs[0]
    outs = []
    for coll, sel in ((G["Detailed"], near), (G["Light"], far)):
        ci = n("GeometryNodeCollectionInfo", {"Collection": coll, "Separate Children": True, "Reset Children": True},
               transform_space="ORIGINAL")
        iop = n("GeometryNodeInstanceOnPoints", {"Points": pts.outputs[0], "Selection": sel,
                                                 "Instance": ci.outputs[0], "Pick Instance": True,
                                                 "Instance Index": vi, "Rotation": rot.outputs[0], "Scale": sc})
        outs.append(iop.outputs[0])
    join = n("GeometryNodeJoinGeometry")
    for o in outs:
        L.new(o, join.inputs[0])
    L.new(join.outputs[0], go.inputs[0])
    return ng


def set_input(mod, name, value):
    ng = mod.node_group
    item = next(i for i in ng.interface.items_tree if getattr(i, "in_out", "") == "INPUT" and i.name == name)
    getattr(mod.properties.inputs, item.identifier).value = value


SCATTER = {   # kind: density per m² at full paint, scale, LOD distance, variants, tilt, thinning
    "tree": dict(density=0.012, scale=(0.75, 1.25), lod=70.0, tilt=0.03),
    "conifer": dict(density=0.010, scale=(0.8, 1.2), lod=70.0, tilt=0.02, attr="tree", seed=4),
    "bush": dict(density=0.12, scale=(0.6, 1.4), lod=35.0, tilt=0.1),
    "rock": dict(density=0.08, scale=(0.3, 1.6), lod=30.0, tilt=0.4),
    "grass": dict(density=40.0, scale=(0.7, 1.3), lod=1e6, tilt=0.15, thin=(15.0, 45.0)),
}


def make_sources(variants: int = 3) -> dict:
    """The instanced objects: per kind a collection of detailed and one of light variants (excluded from view)."""
    mats = scene_mats()
    root = bpy.data.collections.new("FR scatter sources")
    bpy.context.scene.collection.children.link(root)
    out = {}
    makers = {"tree": SH.tree, "conifer": SH.conifer, "bush": SH.bush, "rock": SH.rock}
    for kind in SCATTER:
        pair = []
        for lod in ("DETAILED", "LIGHT"):
            col = bpy.data.collections.new(f"FR {kind} {lod.lower()}")
            root.children.link(col)
            for v in range(variants):
                if kind == "grass":
                    buf = SH.grass_clump(seed=v + 1, blades=16)
                else:
                    buf = makers[kind](seed=v + 1, lod=lod)
                me = mesh_from(f"{kind} {lod} {v}", buf, mats)
                if kind != "grass":
                    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
                new_ob(f"{kind} {lod.lower()} {v:02d}", me, col)
            pair.append(col)
        out[kind] = pair
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.collection == root:
            lc.exclude = True
    return out


def camera_tans(cam) -> tuple[float, float]:
    sc = bpy.context.scene
    ar = sc.render.resolution_x / sc.render.resolution_y
    tx = math.tan(cam.data.angle / 2) if ar >= 1 else math.tan(cam.data.angle / 2) * ar
    return tx, tx / ar


def add_scatter(terrain_ob, sources, cam, kinds=None, cull=True, lod=True, density_scale=1.0):
    ng = scatter_group()
    obs = {}
    for kind, cfg in SCATTER.items():
        if kinds is not None and kind not in kinds:
            continue
        ob = new_ob(f"FR scatter {kind}", bpy.data.meshes.new(f"scatter {kind}"))
        mod = ob.modifiers.new("FR scatter", "NODES")
        mod.node_group = ng
        tx, ty = camera_tans(cam)
        for k, v in (("Terrain", terrain_ob), ("Attribute", SCATTER_ATTR + cfg.get("attr", kind)),
                     ("Density", cfg["density"] * density_scale), ("Seed", cfg.get("seed", 1)),
                     ("Detailed", sources[kind][0]), ("Light", sources[kind][1]),
                     ("Variants", len(sources[kind][0].objects)),
                     ("Scale min", cfg["scale"][0]), ("Scale max", cfg["scale"][1]), ("Camera", cam), ("Cull", cull),
                     ("Tan x", tx), ("Tan y", ty), ("Margin", 8.0 if kind in ("tree", "conifer") else 2.0),
                     ("Detail distance", cfg["lod"] if lod else 1e6), ("Tilt", cfg["tilt"])):
            set_input(mod, k, v)
        if "thin" in cfg:
            set_input(mod, "Thin from", cfg["thin"][0])
            set_input(mod, "Thin to", cfg["thin"][1])
        obs[kind] = ob
    return obs


# =============================================================================
# the whole scene
# =============================================================================


def build(stage: int, ground: str = "PROC", tex: dict | None = None, crane_blend: str | None = None,
          scatter_kinds=None, cull=True, lod=True, density_scale=1.0, timings: dict | None = None):
    tm = timings if timings is not None else {}
    t0 = time.time()
    if crane_blend:
        bpy.ops.wm.open_mainfile(filepath=crane_blend)
        for ob in list(bpy.data.objects):
            if ob.name.startswith("FR Floor"):
                bpy.data.objects.remove(ob)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    sc = bpy.context.scene
    tm["open"] = time.time() - t0
    t1 = time.time()
    T, line = make_terrain(stage)
    tm["terrain_numpy"] = time.time() - t1
    if stage >= STAGES.index("trees"):
        # conifers share the tree paint: deciduous in front, conifers mixed in at the back (by a height rule)
        pass
    attrs = {LAYER_ATTR + k: a for k, a in T.layers.items() if a.max() > 0.01}
    for kind in ("tree", "bush", "rock", "grass"):
        attrs[SCATTER_ATTR + kind] = T.density(kind)
    uv = T.verts()[:, :2]
    t1 = time.time()
    me = grid_mesh("FR terrain", T.verts(), T.grid_faces(), attrs, uv)
    used = [k for k in TR.LAYERS if (LAYER_ATTR + k) in attrs]
    if "grass" in used:
        used.remove("grass")
        used.insert(0, "grass")
    me.materials.append(ground_material(used, ground, tex))
    terrain = new_ob("FR terrain", me)
    tm["terrain_mesh"] = time.time() - t1
    # a far ground to the horizon: a ring from the terrain's own border out to 3 km (no plane under the terrain:
    # a plane at -1 m first hid the pond, whose water lies at -1.2 m)
    hb = T.half
    k = np.arange(0, T.n - 1, 4)
    border = np.concatenate([np.stack([T.xs[k], np.full(len(k), -hb)], 1), np.stack([np.full(len(k), hb), T.xs[k]], 1),
                             np.stack([T.xs[::-1][k], np.full(len(k), hb)], 1),
                             np.stack([np.full(len(k), -hb), T.xs[::-1][k]], 1)])
    zb = T.sample(border[:, 0], border[:, 1])
    m = len(border)
    V = np.concatenate([np.column_stack([border, zb]), np.column_stack([border * (3000.0 / hb), np.zeros(m)])])
    F = np.array([(i, m + i, m + (i + 1) % m, (i + 1) % m) for i in range(m)])
    fm = grid_mesh("FR far ground", V, F, {LAYER_ATTR + "grass": np.ones(len(V))}, V[:, :2])
    fm.materials.append(ground_material(["grass"], ground, tex))
    new_ob("FR far ground", fm)
    mats = scene_mats()
    if line is not None:
        V, F, UV, nrm, along = TR.ribbon(line, 7.0)
        rme = grid_mesh("FR road", V, F, {}, UV)
        rme.materials.append(road_material())
        new_ob("FR road", rme)
        for side in (-1, 1):
            KV, KF = TR.kerb_profile(line, nrm, 7.0, side)
            kme = grid_mesh(f"FR kerb {side}", KV, KF, {})
            kme.polygons.foreach_set("use_smooth", np.zeros(len(KF), bool))
            kme.materials.append(mats["kerb"]())
            new_ob(f"FR kerb {side}", kme)
    if stage >= STAGES.index("buildings"):
        for name, kind, roof, w, d, fl, pos, rot, colour in (
                ("Hall", "HALL", "PITCHED", 36.0, 22.0, 1, (-42, 30), 0.1, (0.55, 0.60, 0.64)),
                ("Office", "OFFICE", "FLAT", 18.0, 12.0, 3, (44, 4), -0.25, (0.80, 0.78, 0.72)),
                ("Workshop", "HALL", "SAWTOOTH", 24.0, 16.0, 1, (-58, 0), 0.05, (0.42, 0.18, 0.12))):
            buf = SH.building(kind, w, d, fl, roof)
            ob = new_ob(f"FR building {name}", mesh_from(name, buf, mats))
            z = float(T.sample(pos[0], pos[1]))
            ob.location = (pos[0], pos[1], z)
            ob.rotation_euler = (0, 0, rot)
            ob["fr_colour"] = colour
        try:      # site huts: the app's own containers (core/surroundings.container)
            sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
            from fresing_render.core import surroundings as CS
            for k, (x, y, r) in enumerate(((-22, -2, 1.57), (-22, 5, 1.57), (-22, 1.5, 1.57))):
                shapes = CS.place(CS.container("container_white" if k < 2 else "container_blue"),
                                  x, y, float(T.sample(x, y)) + (2.6 if k == 2 else 0.0), r)
                buf = SH.MeshBuf()
                for sh in shapes:
                    if isinstance(sh, CS.Box):
                        c, s = math.cos(sh.rot), math.sin(sh.rot)
                        P = []
                        for zz in (0.0, sh.sz):
                            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                                lx, ly = a * sh.sx / 2, b * sh.sy / 2
                                P.append((sh.x + lx * c - ly * s, sh.y + lx * s + ly * c, sh.z + zz))
                        buf.add(P, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6),
                                    (3, 0, 4, 7)], "facade")
                ob = new_ob(f"FR site hut {k}", mesh_from(f"hut {k}", buf, mats))
                ob["fr_colour"] = (0.85, 0.85, 0.82) if k < 2 else (0.10, 0.25, 0.50)
        except Exception as exc:  # noqa: BLE001
            print("huts:", exc)
    if T.water_level is not None:
        dep = T.depth()
        wet = dep > -0.6
        rows = np.where(wet.any(1))[0]
        cols = np.where(wet.any(0))[0]
        if len(rows) and len(cols):
            r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
            X, Y = T.X[r0:r1, c0:c1], T.Y[r0:r1, c0:c1]
            n_r, n_c = X.shape
            V = np.stack([X.ravel(), Y.ravel(), np.full(X.size, T.water_level)], 1)
            i = np.arange(n_r - 1)[:, None] * n_c + np.arange(n_c - 1)[None, :]
            F = np.stack([i.ravel(), i.ravel() + 1, i.ravel() + n_c + 1, i.ravel() + n_c], 1)
            keep = wet[r0:r1, c0:c1][:-1, :-1].ravel() | wet[r0:r1, c0:c1][1:, 1:].ravel()
            F = F[keep]
            wme = grid_mesh("FR water", V, F, {"fr_depth": np.clip(dep[r0:r1, c0:c1], 0, None).ravel()})
            wme.materials.append(water_material())
            new_ob("FR water", wme)
    tm["objects"] = time.time() - t0
    return sc, T, terrain


def setup_render(sc, w=1280, h=720, samples=64, sun=(35.0, 25.0)):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.adaptive_threshold = 0.03
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    for kind in ("MULTIPLE_SCATTERING", "NISHITA"):
        try:
            sky.sky_type = kind
            break
        except TypeError:
            continue
    if hasattr(sky, "sun_disc"):
        sky.sun_disc = False          # the sun lamp is the sun (a second sun in the sky washed every picture out)
    sky.sun_elevation = math.radians(sun[0])
    sky.sun_rotation = math.radians(sun[1])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.35
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    sun_ob = bpy.data.objects.get("FR sun")
    if sun_ob is None:
        sun_ob = new_ob("FR sun", bpy.data.lights.new("FR sun", "SUN"))
    sun_ob.data.energy = 4.0
    sun_ob.data.angle = math.radians(1.0)
    el, az = math.radians(sun[0]), math.radians(sun[1])
    d = np.array((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))  # towards the sun
    sun_ob.rotation_euler = (0, 0, 0)
    sun_ob.rotation_mode = "QUATERNION"
    import mathutils
    sun_ob.rotation_quaternion = mathutils.Vector(-d).to_track_quat("-Z", "Y")


def camera(name, loc, target, lens=35.0):
    import mathutils
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = new_ob(name, bpy.data.cameras.new(name))
    cam.data.lens = lens
    cam.data.clip_end = 6000.0
    cam.data.clip_start = 0.1
    cam.location = loc
    d = mathutils.Vector(target) - mathutils.Vector(loc)
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = d.to_track_quat("-Z", "Y")
    bpy.context.scene.camera = cam
    return cam


SHOTS = {
    "overview": ((95.0, -95.0, 48.0), (-5.0, 15.0, 6.0), 28.0),
    "crane": ((34.0, -30.0, 4.0), (4.0, 2.0, 9.0), 26.0),
    "ground": ((-14.0, -10.0, 1.7), (-26.0, 6.0, -0.5), 30.0),
    "pond": ((32.0, 38.0, 6.0), (2.0, 74.0, -1.0), 30.0),
    "top": ((0.0, 0.0, 400.0), (0.0, 0.001, 0.0), 40.0),
}


def render(path, timings=None, key="render"):
    stats = {}

    def grab(st):
        st = str(st)
        stats["s"] = st
        if "Peak" in st or "Mem" in st:
            stats["mem"] = st
        import re
        for m in re.finditer(r"(?:Peak|Mem):? *([0-9.]+)([MG])", st):
            v = float(m.group(1)) * (1024 if m.group(2) == "G" else 1)
            stats["peak"] = max(stats.get("peak", 0.0), v)
        stats.setdefault("first", st)
    bpy.app.handlers.render_stats.append(grab)
    t = time.time()
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = "JPEG" if path.endswith(".jpg") else "PNG"
    if path.endswith(".jpg"):
        sc.render.image_settings.quality = 88
    bpy.ops.render.render(write_still=True)
    bpy.app.handlers.render_stats.remove(grab)
    dt = time.time() - t
    if timings is not None:
        timings[key] = round(dt, 2)
        timings[key + "_stats"] = stats.get("s", "")
        timings[key + "_mem"] = stats.get("mem", "")
        timings[key + "_peak_mb"] = stats.get("peak", 0.0)
        timings[key + "_first"] = stats.get("first", "")
    return dt


def instance_counts():
    dg = bpy.context.evaluated_depsgraph_get()
    counts = {}
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.name.startswith("FR scatter"):
            k = inst.parent.name[len("FR scatter "):]
            counts[k] = counts.get(k, 0) + 1
    return counts


def scanned(tex_dir: str) -> dict:
    g = os.path.join(tex_dir, "ambientcg-materials-grass", "Grass004", "2K-JPG")
    v = os.path.join(tex_dir, "ambientcg-materials-gravel", "Gravel017", "2K-JPG")
    return {
        "grass": dict(color=os.path.join(g, "Grass004_2K-JPG_Color.jpg"), rough=os.path.join(g, "Grass004_2K-JPG_Roughness.jpg"),
                      normal=os.path.join(g, "Grass004_2K-JPG_NormalGL.jpg"), tile=2.0),
        "gravel": dict(color=os.path.join(v, "Gravel017_2K-JPG_Color.jpg"), rough=os.path.join(v, "Gravel017_2K-JPG_Roughness.jpg"),
                       normal=os.path.join(v, "Gravel017_2K-JPG_NormalGL.jpg"), tile=2.0),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", type=int, default=len(STAGES) - 1)
    ap.add_argument("--ground", default="PROC")
    ap.add_argument("--tex", default=os.path.expanduser("~/dl"))
    ap.add_argument("--crane", default="/tmp/claude-0/p/crane.blend")
    ap.add_argument("--shots", default="overview")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--no-cull", action="store_true")
    ap.add_argument("--no-lod", action="store_true")
    ap.add_argument("--kinds", default="")
    ap.add_argument("--density", type=float, default=1.0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    tm: dict = {"rss_start": round(rss_mb())}
    w, h = (int(v) for v in a.size.split("x"))
    tex = scanned(a.tex) if a.ground == "SCAN" else None
    sc, T, terrain = build(a.stage, a.ground, tex, a.crane if os.path.exists(a.crane) else None, timings=tm)
    setup_render(sc, w, h, a.samples)
    shots = a.shots.split(",")
    first = SHOTS[shots[0]]
    cam = camera("FR shot", *first)
    if a.stage >= STAGES.index("trees"):
        t1 = time.time()
        src = make_sources()
        kinds = [k for k in a.kinds.split(",") if k] or None
        if a.stage < STAGES.index("grass"):
            kinds = [k for k in (kinds or SCATTER) if k != "grass"]
        add_scatter(terrain, src, cam, kinds, cull=not a.no_cull, lod=not a.no_lod, density_scale=a.density)
        tm["sources"] = round(time.time() - t1, 2)
        t1 = time.time()
        bpy.context.view_layer.update()
        tm["scatter_eval"] = round(time.time() - t1, 2)
        tm["instances"] = instance_counts()
    tm["rss_built"] = round(rss_mb())
    tm["verts_terrain"] = len(terrain.data.vertices)
    for shot in shots:
        loc, tgt, lens = SHOTS[shot]
        cam = camera("FR shot", loc, tgt, lens)
        if shot == "top":
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = 270.0
        else:
            cam.data.type = "PERSP"
        bpy.context.view_layer.update()
        if a.stage >= STAGES.index("trees"):
            tm[f"instances_{shot}"] = instance_counts()
        name = f"{a.tag or 'stage%d' % a.stage}_{shot}.jpg"
        render(os.path.join(a.out, name), tm, f"render_{shot}")
        print("rendered", name, tm[f"render_{shot}"], tm[f"render_{shot}_stats"][-160:], flush=True)
    tm["rss_end"] = round(rss_mb())
    tm["peak"] = round(peak_mb())
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=a.save)
    with open(os.path.join(a.out, f"{a.tag or 'stage%d' % a.stage}.json"), "w") as f:
        json.dump(tm, f, indent=1, default=str)
    print(json.dumps(tm, default=str))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
