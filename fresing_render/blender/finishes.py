"""The finishes of task 0274 (study 0270): knurls, spun and faced ends, honed bores, moulded textures, fabric, plate
patterns, blasted metal, paints and grains – the shader nodes.

``core/finishes.py`` has each finish's numbers and settings; ``materials.build_nodes`` calls ``apply`` for a library
material with a ``finish`` key. Every pattern is procedural and needs no UV map. Where it has a direction it takes it
from the part itself:

* **The CAD face's own axis** (knurls, spun, faced, honed, the rubber grip): four FACE attributes on the mesh –
  ``fr_fx_o`` a point of the face's axis, ``fr_fx_d`` its direction, ``fr_fx_r`` the face's own radius, ``fr_fx_k`` its
  kind (1 round outside, -1 bore, 2 end face, 0 other) – written by ``prepare_faces`` from the importer's round-face
  axes (``core.finishes.face_frames``). ``materials.assign`` writes them when a part gets such a finish, and again
  when its mesh changed (a model update). Read with an Attribute node (Geometry), Cycles and EEVEE.
* **The part's own box axes** (cross-hatch, fabric, grille, tread plate, perforated, expanded, scraped ways): a box
  projection in object space; flat sheet patterns take the face's main direction only (one projection: a third of
  the work), shell patterns blend the three on curved faces.
* **Nothing** (blasted, hammertone, wrinkle, anti-skid, VDI, leather, spangle, as-cast, soft-touch): a 3-D grain in
  object space. Grains finer than ~0.3 mm use noise (cheap); Voronoi only where its cells are big enough to see.

Every copy of a part shares its mesh and its object space, so every copy looks the same (turned, mirrored).

**Far away** a pattern fades to its average (``F.lod``): one pixel on the part = distance from the camera x the
picture's pixel angle; a pattern whose period covers fewer than ~2 pixels is drawn flat with the roughness / colour /
open share it averages to, so it cannot shimmer. The pixel angle is the scene's ``fr_pixel_angle`` (kept up by
``cameras.update_pixel_angle``), read with an Attribute node of type View Layer: nothing is rebuilt when the camera or
the picture size changes.

Units: metres in object space."""

from __future__ import annotations

import json
import math

import bpy

from ..core import finishes as core
from ..core import ral
from .materials import _Nodes

#: what the mesh's face data was written from (``signature``: a model update that changes the part: written again)
FX_COUNT = "fr_fx_n"
FX_NAMES = ("fr_fx_o", "fr_fx_d", "fr_fx_r", "fr_fx_k", "fr_cw_a", "fr_cw_b")
#: FACE attributes read as vectors (the others as numbers)
FX_VECTORS = ("fr_fx_o", "fr_fx_d", "fr_cw_a", "fr_cw_b")
#: on a finish material: the finish id, its settings key and its numbers for the web model (JSON)
PROP_FINISH, PROP_WEB = "fr_finish", "fr_finish_web"


def lin(c):
    return tuple(ral.srgb_to_linear(x) for x in c)


# ---------------------------------------------------------------------------------------------------------------
# face data
# ---------------------------------------------------------------------------------------------------------------

def prepare_faces(me) -> dict:
    """Write ``fr_fx_o/d/r/k`` (FACE domain) on a mesh from the importer's axes. Returns counts per kind."""
    import numpy as np

    from . import materials
    materials.ensure_axes(me)
    P = len(me.polygons)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tri = np.zeros((P, 3), np.int64)
    if P:
        n_loops = np.empty(P, np.int64)
        me.polygons.foreach_get("loop_total", n_loops)
        ls = np.empty(P, np.int64)
        me.polygons.foreach_get("loop_start", ls)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        tri = lv[np.add.outer(ls, np.arange(3))]          # the importer's meshes are triangles; an n-gon: its first
    o, d, r, k = core.face_frames(co, tri, me.get("fr_axes", []), me.get("fr_axis_faces", []),
                                  list(me.get("fr_face_starts", [])), me.get(materials.AX_CENTRE),
                                  me.get(materials.AX_ROUND))
    wa, wb = core.weave_frames(co, tri, o, d, r, k, list(me.get("fr_face_starts", [])))     # task 0318: carbon
    for name, arr, kind in (("fr_fx_o", o, "FLOAT_VECTOR"), ("fr_fx_d", d, "FLOAT_VECTOR"), ("fr_fx_r", r, "FLOAT"),
                            ("fr_fx_k", k, "FLOAT"), ("fr_cw_a", wa, "FLOAT_VECTOR"), ("fr_cw_b", wb, "FLOAT_VECTOR")):
        at = me.attributes.get(name)
        if at is not None and (at.domain != "FACE" or at.data_type != kind):
            me.attributes.remove(at)
            at = None
        if at is None:
            at = me.attributes.new(name, kind, "FACE")
        at.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", arr.astype(np.float32).ravel())
    me[FX_COUNT] = signature(me)
    return {"round": int((k == 1).sum()), "bore": int((k == -1).sum()), "end": int((k == 2).sum()),
            "sphere": int((np.abs(k) == 3).sum()), "other": int((k == 0).sum())}


def signature(me) -> str:
    """What the face data was written from: the counts, the sum of the points and the CAD axes (a model update that
    changes the part changes it)."""
    import numpy as np
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    axes = me.get("fr_axes", [])
    return f"{len(me.polygons)}:{len(me.vertices)}:{float(co.sum()):.6g}:{len(axes)}:{float(sum(axes)):.6g}"


def has_faces(me) -> bool:
    return (me is not None and all(n in me.attributes for n in FX_NAMES)
            and me.get(FX_COUNT) == signature(me))


def ensure_faces(me) -> bool:
    """Write the face data when the mesh has none or changed. True when it was written."""
    if me is None or has_faces(me):
        return False
    prepare_faces(me)
    return True


def needs_faces(mat) -> bool:
    """The material is a finish that reads the CAD faces' own axes."""
    return mat is not None and core.needs_faces(mat.get("fr_material", "")) and bool(mat.get(PROP_FINISH))


# ---------------------------------------------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------------------------------------------

class F(_Nodes):
    """``materials._Nodes`` + what the finishes share."""

    def __init__(self, nt):
        super().__init__(nt)
        self._geo = {}
        self._cyl = None
        self._mpp = None

    def p(self):
        return self.coord("Object")

    def n(self):
        return self.coord("Normal")              # object space

    def math(self, op, a, b=None, c=None, x=0.0, y=0.0, clamp=False):
        out = super().math(op, a, b, x=x, y=y, clamp=clamp)
        if c is not None:
            self.put(out.node.inputs[2], c)
        return out

    def mix(self, kind, fac, a, b, x=0.0, y=0.0):
        if kind != "VECTOR":
            return super().mix(kind, fac, a, b, x, y)
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = "VECTOR"
        n.clamp_factor = True
        self.put(n.inputs[0], fac)
        self.put(n.inputs[4], a)
        self.put(n.inputs[5], b)
        return n.outputs[1]

    def ncol(self, scale):
        """A noise's colour (a random vector field) in object space, centred on 0."""
        n = self.node("ShaderNodeTexNoise")
        self.put(n.inputs["Vector"], self.p())
        self.put(n.inputs["Scale"], scale)
        return self.vmath("SUBTRACT", n.outputs["Color"], (0.5, 0.5, 0.5))

    def gattr(self, name):
        if name not in self._geo:
            a = self.node("ShaderNodeAttribute", -2100, 400 - 150 * len(self._geo))
            a.attribute_type = "GEOMETRY"
            a.attribute_name = name
            self._geo[name] = a
        a = self._geo[name]
        return a.outputs["Vector"] if name in FX_VECTORS else a.outputs["Fac"]

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], v)
        return n.outputs

    def comb(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def tri(self, v):
        """Triangle wave 0 (at whole numbers) .. 1 (halfway)."""
        return self.math("MULTIPLY", self.math("PINGPONG", v, 0.5), 2.0)

    def smooth(self, v, a, b):
        n = self.node("ShaderNodeMapRange", From_Min=a, From_Max=b, To_Min=0.0, To_Max=1.0)
        n.interpolation_type = "SMOOTHSTEP"
        self.put(n.inputs["Value"], v)
        return n.outputs["Result"]

    def cmp(self, a, value):
        n = self.node("ShaderNodeMath")
        n.operation = "COMPARE"
        self.put(n.inputs[0], a)
        n.inputs[1].default_value = value
        n.inputs[2].default_value = 0.25
        return n.outputs[0]

    def cyl(self):
        """Per face: z along its axis, rho from it, theta 0..2pi round it, its own radius, its kind – metres."""
        if self._cyl is None:
            o, d = self.gattr("fr_fx_o"), self.gattr("fr_fx_d")
            pc = self.vmath("SUBTRACT", self.p(), o)
            z = self.vmath("DOT_PRODUCT", pc, d)
            rad = self.vmath("SUBTRACT", pc, self.vmath("SCALE", d, scale=z))
            rho = self.vmath("LENGTH", rad)
            dz = self.sep(d)[2]
            big = self.math("GREATER_THAN", self.math("ABSOLUTE", dz), 0.9)
            ref = self.mix("VECTOR", big, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
            u = self.vmath("NORMALIZE", self.vmath("CROSS_PRODUCT", d, ref))
            w = self.vmath("CROSS_PRODUCT", d, u)
            th = self.math("ARCTAN2", self.vmath("DOT_PRODUCT", rad, w), self.vmath("DOT_PRODUCT", rad, u))
            th = self.math("ADD", th, math.pi)
            tang = self.vmath("NORMALIZE", self.vmath("CROSS_PRODUCT", d, rad))       # round the axis
            r = self.gattr("fr_fx_r")
            k = self.gattr("fr_fx_k")
            sph = self.math("GREATER_THAN", self.math("ABSOLUTE", k), 2.5)              # task 0318: a sphere
            phi = self.math("ARCTAN2", rho, z)                                         # from its pole
            self._cyl = dict(z=z, rho=rho, th=th, r=r, k=k, d=d, tang=tang, rad=rad, u=u, w=w, sph=sph, phi=phi,
                             s=self.math("MULTIPLY", r, phi))
        return self._cyl

    def metres_per_pixel(self):
        """Distance from the camera x the scene's pixel angle (``core.PIXEL_PROP``; the default when it has none)."""
        if self._mpp is None:
            a = self.node("ShaderNodeAttribute", -2100, 800)
            a.attribute_type = "VIEW_LAYER"
            a.attribute_name = core.PIXEL_PROP
            a.name = a.label = "FR pixel angle"
            pix = a.outputs["Fac"]
            missing = self.math("LESS_THAN", pix, 1e-12)
            pix = self.math("ADD", pix, self.math("MULTIPLY", missing, core.PIXEL_ANGLE))
            cam = self.node("ShaderNodeCameraData", -2100, 1000)
            self._mpp = self.math("MAXIMUM", self.math("MULTIPLY", cam.outputs["View Distance"], pix), 1e-15)
        return self._mpp

    def lod(self, period_m: float, lo: float = core.FADE_LO, hi: float = core.FADE_HI):
        """1 where the pattern's period covers >= ``hi`` pixels, 0 below ``lo`` pixels (``core.shown``)."""
        px = self.math("DIVIDE", float(period_m), self.metres_per_pixel())
        return self.smooth(px, lo, hi)

    def box(self, fn, sharp: float = 8.0, blend: bool = True):
        """A pattern in the part's own box axes. ``fn(u, v)`` -> a socket for the projection with (u, v) the two axes
        across the face. ``blend``: the three projections weighted by |n_k|^sharp (curved shells); else the face's
        main axis only (flat sheet patterns: the pattern is worked out once)."""
        ps = self.sep(self.p())
        ns = self.sep(self.n())
        if not blend:
            ax = [self.math("ABSOLUTE", ns[k]) for k in range(3)]
            # ties (a face at exactly 45°) go to x, then y: a projection along the face would draw stripes
            not_gt = (lambda a, b: self.math("SUBTRACT", 1.0, self.math("GREATER_THAN", a, b)))
            is_x = self.math("MULTIPLY", not_gt(ax[1], ax[0]), not_gt(ax[2], ax[0]))
            is_y = self.math("MULTIPLY", self.math("GREATER_THAN", ax[1], ax[0]), not_gt(ax[2], ax[1]))
            u = self.mix("FLOAT", is_x, self.mix("FLOAT", is_y, ps[0], ps[0]), ps[1])   # x faces: (y, z)
            v = self.mix("FLOAT", is_x, self.mix("FLOAT", is_y, ps[1], ps[2]), ps[2])   # y: (x, z); z: (x, y)
            return fn(u, v)
        hs, ws = [], []
        for k in range(3):
            i, j = [a for a in range(3) if a != k]
            hs.append(fn(ps[i], ps[j]))
            ws.append(self.math("POWER", self.math("ABSOLUTE", ns[k]), sharp))
        tot = self.math("MAXIMUM", self.math("ADD", self.math("ADD", ws[0], ws[1]), ws[2]), 1e-9)
        out = None
        for h, w in zip(hs, ws):
            t = self.math("MULTIPLY", h, self.math("DIVIDE", w, tot))
            out = t if out is None else self.math("ADD", out, t)
        return out

    def bump(self, height, distance: float, strength=1.0, normal=None):
        n = self.node("ShaderNodeBump")
        self.put(n.inputs["Height"], height)
        self.put(n.inputs["Strength"], strength)
        self.put(n.inputs["Distance"], distance)
        if normal is not None:
            self.put(n.inputs["Normal"], normal)
        return n.outputs["Normal"]

    def world_tangent(self, t_obj):
        """The marks' direction (object space) -> world, then ACROSS it within the face: Blender stretches the
        highlight ALONG the tangent, a real part across its marks (task 0098)."""
        vt = self.node("ShaderNodeVectorTransform")
        vt.vector_type = "VECTOR"
        vt.convert_from, vt.convert_to = "OBJECT", "WORLD"
        self.put(vt.inputs[0], t_obj)
        geo = self.node("ShaderNodeNewGeometry")
        return self.vmath("NORMALIZE", self.vmath("CROSS_PRODUCT", geo.outputs["Normal"], vt.outputs[0]))

    def vor(self, vec, scale, feature="F1", rand=1.0):
        n = self.node("ShaderNodeTexVoronoi")
        n.voronoi_dimensions = "3D"
        n.feature = feature
        self.put(n.inputs["Vector"], vec if vec is not None else self.p())
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Randomness"], rand)
        return n.outputs

    def noise3(self, vec=None, scale=1.0, detail=2.0, rough=0.5, distortion=0.0):
        n = self.node("ShaderNodeTexNoise")
        self.put(n.inputs["Vector"], vec if vec is not None else self.p())
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Detail"], detail)
        self.put(n.inputs["Roughness"], rough)
        self.put(n.inputs["Distortion"], distortion)
        return n.outputs["Fac"]

    def cells(self, scale):
        """A random 0..1 per cube cell of 1/``scale`` (White Noise of the cell's corner): far cheaper than Voronoi
        for grains too small to show their shape."""
        q = self.vmath("FLOOR", self.vmath("SCALE", self.p(), scale=float(scale)))
        n = self.node("ShaderNodeTexWhiteNoise")
        n.noise_dimensions = "3D"
        self.put(n.inputs["Vector"], q)
        return n.outputs["Value"]


# ---------------------------------------------------------------------------------------------------------------
# the finishes: each builder returns the Principled inputs it sets (sockets or numbers)
#   s: core.finishes.pattern(...) + color (sRGB), roughness, metallic of the material
# ---------------------------------------------------------------------------------------------------------------

def _rings(b: F, s: dict, ring_k: float):
    """Spun / turned rings: fine 1-D noise of the distance from the face's axis (end faces) or of z (round faces).
    Returns (height 0..1, the tangent across the rings, 1 on faces that have an axis)."""
    c = b.cyl()
    end = b.cmp(c["k"], 2.0)
    w = b.mix("FLOAT", end, c["z"], c["rho"])
    w = b.mix("FLOAT", c["sph"], w, c["s"])          # a dome (task 0318): rings evenly along it from its middle
    f1 = b.noise(w=b.math("MULTIPLY", w, ring_k), scale=1.0, detail=3.0)
    f2 = b.noise(w=b.math("MULTIPLY", w, ring_k / 23.0), scale=1.0, detail=1.0)
    vis = b.lod(8.0 / ring_k)
    h = b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", f1, 0.7), b.math("MULTIPLY", f2, 0.3)), vis)
    any_axis = b.math("GREATER_THAN", b.math("ABSOLUTE", c["k"]), 0.5)
    return h, b.world_tangent(c["tang"]), any_axis


def knurl(b: F, s: dict):
    """Diamond (two groove families at +-angle to the axis) or straight knurl on the round faces (outside), a whole
    number of teeth round each face (no seam); spun rings on the end faces of a knurled knob."""
    c = b.cyl()
    p = s["pitch"]
    beta = math.radians(s.get("angle", 30.0) if s.get("diamond", True) else 0.0)
    vis = b.lod(p)
    on = b.math("MULTIPLY", b.cmp(c["k"], 1.0), vis)
    n_t = b.math("MAXIMUM", b.math("ROUND", b.math("MULTIPLY", c["r"], 2 * math.pi * math.cos(beta) / p)), 1.0)
    a = b.math("MULTIPLY", b.math("DIVIDE", c["th"], 2 * math.pi), n_t)
    if s.get("diamond", True):
        zz = b.math("MULTIPLY", c["z"], math.sin(beta) / p if beta else 1.0 / p)
        h = b.math("MINIMUM", b.tri(b.math("ADD", a, zz)), b.tri(b.math("SUBTRACT", a, zz)))
    else:
        h = b.tri(a)
    h = b.math("MINIMUM", b.math("MULTIPLY", h, s.get("flat_tops", 1.3)), 1.0)      # the tips are a little flat
    h = b.math("MULTIPLY", h, on)
    valley = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, h), on)
    far = b.math("MULTIPLY", b.cmp(c["k"], 1.0), b.math("SUBTRACT", 1.0, vis))
    far_r = core.FINISHES["knurl_diamond"]["far_rough"] if s.get("spun_ends", True) else 0.06
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", valley, 0.12),
                                                  b.math("MULTIPLY", far, far_r)), clamp=True)
    dark = 0.35 if s.get("metallic", 0.0) > 0.5 else 0.2
    col = b.mix("RGBA", b.math("MULTIPLY", valley, dark), (*lin(s["color"]), 1), (0.05, 0.05, 0.05, 1))
    normal = b.bump(h, 0.35 * p)
    if s.get("spun_ends", True):            # the end faces of a knurled knob are faced / spun: rings round the axis
        hr, tangent, _on = _rings(b, s, 20000.0)
        end = b.cmp(c["k"], 2.0)
        normal = b.bump(b.math("MULTIPLY", hr, end), 0.00004, 1.0, normal)
        return dict(color=col, roughness=rough, normal=normal, tangent=tangent,
                    anisotropic=b.math("MULTIPLY", end, 0.7))
    return dict(color=col, roughness=rough, normal=normal)


def spun(b: F, s: dict):
    h, tangent, on = _rings(b, s, s.get("ring_k", 20000.0))
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", h, 0.5), 0.08), clamp=True)
    return dict(roughness=rough, normal=b.bump(b.math("MULTIPLY", h, on), 0.00004), tangent=tangent,
                anisotropic=b.math("MULTIPLY", on, s.get("anisotropic", 0.8)))


def faced(b: F, s: dict):
    """The faced end of a turned part: one spiral groove per feed round the face's own centre; rings elsewhere."""
    c = b.cyl()
    f = s["feed"]
    end = b.cmp(c["k"], 2.0)
    sp = b.math("ADD", b.math("DIVIDE", c["rho"], f), b.math("DIVIDE", c["th"], 2 * math.pi))
    vis = b.lod(f)
    h = b.math("MULTIPLY", b.math("MULTIPLY", b.tri(sp), end), vis)
    _hr, tangent, on = _rings(b, s, 0.7 / f)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, 0.06),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1.0, vis), 0.03)), clamp=True)
    return dict(roughness=rough, normal=b.bump(h, 0.25 * f), tangent=tangent,
                anisotropic=b.math("MULTIPLY", on, s.get("anisotropic", 0.6)))


def honed(b: F, s: dict):
    """Honing cross-hatch in a bore: two families of fine helical scratches; turned rings on the outside."""
    c = b.cyl()
    A = math.radians(s["angle"] / 2)                 # half the included angle, from the circumferential direction
    arc = b.math("MULTIPLY", c["th"], c["r"])
    s1 = b.math("ADD", b.math("MULTIPLY", arc, math.sin(A)), b.math("MULTIPLY", c["z"], math.cos(A)))
    s2 = b.math("SUBTRACT", b.math("MULTIPLY", arc, math.sin(A)), b.math("MULTIPLY", c["z"], math.cos(A)))
    k = s["k"]
    l1 = b.noise(w=b.math("MULTIPLY", s1, k), scale=1.0, detail=4.0)
    l2 = b.noise(w=b.math("MULTIPLY", s2, k), scale=1.0, detail=4.0)
    sc1 = b.smooth(l1, 0.62, 0.72)
    sc2 = b.smooth(l2, 0.62, 0.72)
    inside = b.cmp(c["k"], -1.0)
    vis = b.lod(4.0 / k)
    h = b.math("MULTIPLY", b.math("MULTIPLY", b.math("MAXIMUM", sc1, sc2), inside), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, 0.15), b.math(
        "MULTIPLY", inside, b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.08))), clamp=True)
    hr, tangent, _on = _rings(b, s, 5000.0)
    outside = b.cmp(c["k"], 1.0)
    return dict(roughness=rough, normal=b.bump(b.math("SUBTRACT", b.math("MULTIPLY", hr, outside), h), 0.00003),
                tangent=tangent, anisotropic=b.math("MULTIPLY", outside, 0.5))


def crosshatch(b: F, s: dict):
    """A fine raised grid moulded into a (double-)curved plastic shell: a blend of the three box projections."""
    p, wl = s["pitch"], s["line"]
    a = math.radians(s.get("angle", 45.0))
    ca, sa = math.cos(a), math.sin(a)

    def grid(u, v):
        su = b.math("ADD", b.math("MULTIPLY", u, ca), b.math("MULTIPLY", v, sa))
        sv = b.math("SUBTRACT", b.math("MULTIPLY", v, ca), b.math("MULTIPLY", u, sa))
        gu = b.smooth(b.math("MULTIPLY", b.tri(b.math("DIVIDE", su, p)), p / 2), 0.0, wl)
        gv = b.smooth(b.math("MULTIPLY", b.tri(b.math("DIVIDE", sv, p)), p / 2), 0.0, wl)
        return b.math("SUBTRACT", 1.0, b.math("MULTIPLY", gu, gv))          # 1 on the raised lines
    vis = b.lod(p)
    h = b.math("MULTIPLY", b.box(grid, 8.0), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, -0.08),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.06)), clamp=True)
    return dict(roughness=rough, normal=b.bump(h, s["height"]))


def fabric(b: F, s: dict):
    """A plain weave of threads ``pitch`` apart (box projection, blended), a fabric sheen."""
    p = s["pitch"]

    def weave(u, v):
        iu = b.math("FLOOR", b.math("DIVIDE", u, p))
        iv = b.math("FLOOR", b.math("DIVIDE", v, p))
        par = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 2.0)
        au = b.tri(b.math("DIVIDE", u, p))
        av = b.tri(b.math("DIVIDE", v, p))
        thr_u = b.math("SQRT", b.math("MAXIMUM", av, 0.0))
        thr_v = b.math("SQRT", b.math("MAXIMUM", au, 0.0))
        bend_u = b.math("SINE", b.math("MULTIPLY", au, math.pi / 2))
        bend_v = b.math("SINE", b.math("MULTIPLY", av, math.pi / 2))
        top_u = b.math("MULTIPLY", thr_u, b.mix("FLOAT", par, bend_v, b.math("SUBTRACT", 1.0, bend_v)))
        top_v = b.math("MULTIPLY", thr_v, b.mix("FLOAT", par, b.math("SUBTRACT", 1.0, bend_u), bend_u))
        return b.math("MAXIMUM", top_u, top_v)
    vis = b.lod(p)
    h = b.math("MULTIPLY", b.box(weave, 8.0), vis)
    fib = b.noise3(scale=1.0 / p * 6, detail=2.0)
    base = lin(s["color"])
    shade = b.math("MULTIPLY", b.mix("FLOAT", vis, 0.3, b.math("SUBTRACT", 1.0, h)), 0.6)   # far: the average
    col = b.mix("RGBA", shade, (*base, 1), (*[x * 0.25 for x in base], 1))
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", fib, 0.05), clamp=True)
    return dict(color=col, roughness=rough, normal=b.bump(h, 0.45 * p))


def _hex_dist(b: F, u, v, p: float):
    """Distance to the nearest hole centre of a 60° grid (rows p sqrt(3)/2 apart, every second row shifted)."""
    rowh = p * math.sqrt(3) / 2
    row = b.math("FLOOR", b.math("DIVIDE", v, rowh))
    shift = b.math("MULTIPLY", b.math("FLOORED_MODULO", row, 2.0), p / 2)
    uu = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, shift), p, 0.0), p / 2)
    vv = b.math("SUBTRACT", b.math("WRAP", v, rowh, 0.0), rowh / 2)
    dd = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu, uu), b.math("MULTIPLY", vv, vv)))
    # the next row's holes: half a pitch to the side, a whole row up or down (the study had them half a row away:
    # twice the holes, found by the independent tester of task 0274)
    uu2 = b.math("SUBTRACT", b.math("ABSOLUTE", uu), p / 2)
    vv2 = b.math("SUBTRACT", b.math("ABSOLUTE", vv), rowh)
    d2 = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu2, uu2), b.math("MULTIPLY", vv2, vv2)))
    return b.math("MINIMUM", dd, d2)


def grille(b: F, s: dict):
    """A fine plastic grille: round holes on a 60° grid, see-through; far away its open share."""
    p, rh = s["pitch"], s["hole"] / 2
    dist = b.box(lambda u, v: _hex_dist(b, u, v, p), blend=False)
    vis = b.lod(p, 2.0, 5.0)
    solid = b.smooth(dist, rh * 0.92, rh * 1.08)                   # 0 in a hole
    alpha = b.mix("FLOAT", vis, 1.0 - core.open_share("grille", {"size": s["hole"]}), solid)
    return dict(alpha=alpha, normal=b.bump(b.math("MULTIPLY", solid, vis), 0.0003))


def perforated(b: F, s: dict):
    """Round holes on a 60° grid or slots in staggered rows, see-through (sheet: the face's main axis only)."""
    p, rh = s["pitch"], s["hole"] / 2
    slot = float(s.get("slot", 0.0))

    def holes(u, v):
        if not slot:
            return _hex_dist(b, u, v, p)
        rowh, per = p, slot + p
        row = b.math("FLOOR", b.math("DIVIDE", v, rowh))
        shift = b.math("MULTIPLY", b.math("FLOORED_MODULO", row, 2.0), per / 2)
        uu = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, shift), per, 0.0), per / 2)
        vv = b.math("SUBTRACT", b.math("WRAP", v, rowh, 0.0), rowh / 2)
        uu = b.math("MAXIMUM", b.math("SUBTRACT", b.math("ABSOLUTE", uu), slot / 2 - rh), 0.0)   # round ends
        return b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu, uu), b.math("MULTIPLY", vv, vv)))
    dist = b.box(holes, blend=False)
    vis = b.lod(p, 2.0, 5.0)
    solid = b.smooth(dist, rh * 0.96, rh * 1.04)
    share = (math.pi * rh * rh + (slot - 2 * rh) * 2 * rh) / ((slot + p) * p) if slot else \
        math.pi * rh * rh / (p * p * math.sqrt(3) / 2)
    alpha = b.mix("FLOAT", vis, 1.0 - share, solid)
    return dict(alpha=alpha, normal=b.bump(b.math("MULTIPLY", solid, vis), rh * 0.15))


def expanded(b: F, s: dict):
    """Expanded metal: diamond openings LWD x SWD in a staggered grid, strands that lean (a slope across them)."""
    LW, SW, st = s["lwd"], s["swd"], s["strand"]

    def rh(u, v, ou, ov):
        a = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, ou), LW, 0.0), LW / 2)
        c = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", v, ov), SW, 0.0), SW / 2)
        return b.math("ADD", b.math("DIVIDE", b.math("ABSOLUTE", a), LW / 2), b.math("DIVIDE", b.math("ABSOLUTE", c),
                                                                                       SW / 2))

    def mesh(u, v):
        return b.math("MINIMUM", rh(u, v, 0.0, 0.0), rh(u, v, LW / 2, SW / 2))
    m = b.box(mesh, blend=False)
    share = 2.0 * st / SW
    edge = b.smooth(m, 1.0 - share - 0.03, 1.0 - share + 0.03)            # 1 on metal
    vis = b.lod(SW, 2.0, 5.0)
    alpha = b.mix("FLOAT", vis, 1.0 - (1.0 - share) ** 2, edge)
    slope = b.math("MULTIPLY", b.math("MULTIPLY", b.math("DIVIDE", b.math("SUBTRACT", m, 1.0 - share), share), edge),
                   vis)
    return dict(alpha=alpha, normal=b.bump(slope, st * 0.8))


def tread(b: F, s: dict):
    """Tread plate: raised lenses on a square grid, each at 90° to its neighbours (the face's main axis only)."""
    P, L, W = s["pitch"], s["length"], s["width"]
    c45 = math.cos(math.radians(45))

    def lens(u, v):
        iu = b.math("FLOOR", b.math("DIVIDE", u, P))
        iv = b.math("FLOOR", b.math("DIVIDE", v, P))
        par = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 2.0)
        lu = b.math("SUBTRACT", b.math("WRAP", u, P, 0.0), P / 2)
        lv = b.math("SUBTRACT", b.math("WRAP", v, P, 0.0), P / 2)
        ru = b.math("MULTIPLY", b.math("ADD", lu, lv), c45)
        rv = b.math("MULTIPLY", b.math("SUBTRACT", lv, lu), c45)
        a_ = b.mix("FLOAT", par, ru, rv)
        b_ = b.mix("FLOAT", par, rv, ru)
        e = b.math("ADD", b.math("POWER", b.math("ABSOLUTE", b.math("DIVIDE", a_, L / 2)), 2.0),
                   b.math("POWER", b.math("ABSOLUTE", b.math("DIVIDE", b_, W / 2)), 2.0))
        return b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", 1.0, e), 0.0))
    vis = b.lod(P)
    h = b.math("MULTIPLY", b.box(lens, blend=False), vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", h, -0.06), clamp=True)
    return dict(roughness=rough, normal=b.bump(h, s["height"]))


def scraped(b: F, s: dict):
    """Scraped / flaked ways: half-moon marks in a checker of cells, every second cell turned 90°."""
    P = s["cell"]

    def flakes(u, v):
        iu = b.math("FLOOR", b.math("DIVIDE", u, P))
        iv = b.math("FLOOR", b.math("DIVIDE", v, P))
        par = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 2.0)
        lu = b.math("SUBTRACT", b.math("WRAP", u, P, 0.0), P / 2)
        lv = b.math("SUBTRACT", b.math("WRAP", v, P, 0.0), P / 2)
        a_ = b.mix("FLOAT", par, lu, lv)
        b_ = b.mix("FLOAT", par, lv, b.math("MULTIPLY", lu, -1.0))
        R = P * 0.42
        d1 = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", a_, a_), b.math("MULTIPLY", b_, b_)))
        a2 = b.math("SUBTRACT", a_, R * 0.45)
        d2 = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", a2, a2), b.math("MULTIPLY", b_, b_)))
        return b.math("MULTIPLY", b.smooth(b.math("SUBTRACT", R, d1), 0.0, P * 0.01),
                      b.smooth(b.math("SUBTRACT", d2, R * 0.95), 0.0, P * 0.01))
    vis = b.lod(P)
    m = b.math("MULTIPLY", b.box(flakes, blend=False), vis)
    soft = b.math("MULTIPLY", m, b.noise3(scale=1.0 / 0.002, detail=2.0))
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", m, 0.14),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.05)), clamp=True)
    col = b.mix("RGBA", b.math("MULTIPLY", m, 0.15), (*lin(s["color"]), 1), (1.0, 1.0, 1.0, 1))
    return dict(color=col, roughness=rough, normal=b.bump(soft, 0.00002))


def soft_touch(b: F, s: dict):
    vis = b.lod(3.0 / s["grain"])
    h = b.math("MULTIPLY", b.noise3(scale=s["grain"], detail=3.0), vis)
    return dict(normal=b.bump(h, 0.00002, 1.0))


def blasted(b: F, s: dict):
    """Bead / shot blasted: isotropic dimples, a little colour from the grain. The study built the dimples from
    Voronoi cells (+40 / +69 %); under ~0.3 mm their shape cannot be seen, so this uses noise (cheaper)."""
    g = s["grain"]
    vis = b.lod(2.0 / g)
    d = b.noise3(scale=g, detail=1.0, rough=0.5)
    h = b.math("MULTIPLY", b.math("POWER", b.math("ABSOLUTE", b.math("SUBTRACT", d, 0.5)), 0.7), vis)
    n2 = b.noise3(scale=g / 6, detail=2.0)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", n2, 0.5), s.get("rough_var", 0.08)),
                   clamp=True)
    col = b.mix("RGBA", b.math("MULTIPLY", n2, s.get("color_var", 0.1)), (*lin(s["color"]), 1), (0.1, 0.1, 0.1, 1))
    return dict(color=col, roughness=rough, normal=b.bump(h, s["depth"]))


def hammertone(b: F, s: dict):
    """Hammer marks (Voronoi dents round a warped grid) and tiny metal flakes (a random value per 0.15 mm cell: the
    study's second Voronoi for the flakes cost more than all the rest)."""
    cell = s["cell"]
    # F1, not the study's Smooth F1 (which looks at 125 cells instead of 27): the squared map below rounds the dents
    v = b.vor(b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(60.0), scale=cell * 0.5)), 1.0 / cell, "F1", 0.9)
    vis = b.lod(cell)
    h = b.math("MULTIPLY", b.math("POWER", b.map(v[0], 0.0, 0.75, 0.0, 1.0), 2.0), vis)   # a round dimple per cell
    fl = b.cells(1.0 / 0.00015)
    base = (*lin(s["color"]), 1)
    light = (*[min(1, x * 1.7 + 0.04) for x in lin(s["color"])], 1)
    col = b.mix("RGBA", b.map(h, 0.3, 1.0, 0.0, 0.8), base, light)          # rims catch more light
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", fl, 0.5), 0.12), clamp=True)
    return dict(color=col, roughness=rough, normal=b.bump(h, cell * 0.09))


def wrinkle(b: F, s: dict):
    """Wrinkle paint: worm-like ridges (the ridges of a warped noise: 1 - |2n - 1|, sharpened)."""
    sc = 0.9 / s["size"]
    vis = b.lod(1.5 / sc)
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(sc / 3), scale=3.0 / sc))
    n = b.noise3(warp, sc, 2.0, 0.5)
    ridge = b.math("SUBTRACT", 1.0, b.math("ABSOLUTE", b.math("SUBTRACT", b.math("MULTIPLY", n, 2.0), 1.0)))
    h = b.math("MULTIPLY", b.math("POWER", ridge, 4.0), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, -0.12),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1.0, vis), -0.04)), clamp=True)
    return dict(roughness=rough, normal=b.bump(h, 0.6 / sc))


def antiskid(b: F, s: dict):
    g = s["grit"]
    v = b.vor(None, 1.0 / g, "F1", 1.0)
    keep = b.math("GREATER_THAN", b.sep(v[1])[0], 1.0 - s.get("cover", 0.5))
    bump_h = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.smooth(v[0], 0.05, 0.45)), keep)
    vis = b.lod(g)
    h = b.math("MULTIPLY", bump_h, vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.08), clamp=True)
    col = b.mix("RGBA", b.math("MULTIPLY", h, 0.25), (*lin(s["color"]), 1), (0.9, 0.9, 0.9, 1))
    return dict(color=col, roughness=rough, normal=b.bump(h, g * 0.5))


def vdi(b: F, s: dict):
    """Spark-eroded VDI 3400 texture: fine random craters (noise: the craters are 0.05 - 0.15 mm, a Voronoi cost
    +32 … +41 % in the study and its cell shape cannot be seen); the class sets their size and the roughness."""
    g = s["grain"]
    vis = b.lod(2.0 / g)
    n = b.noise3(scale=g, detail=2.0, rough=0.55)
    h = b.math("MULTIPLY", b.smooth(n, 0.35, 0.65), vis)
    return dict(normal=b.bump(h, 0.5 / g))


def leather(b: F, s: dict):
    c = s["cell"]
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(1.0 / c / 3), scale=c * 1.6))
    e = b.vor(warp, 1.0 / c, "DISTANCE_TO_EDGE", 1.0)[0]
    vis = b.lod(c)
    crease = b.math("SUBTRACT", 1.0, b.smooth(e, 0.0, 0.07))
    pores = b.noise3(scale=1.0 / c * 8, detail=2.0)
    h = b.math("MULTIPLY", b.math("SUBTRACT", b.math("SUBTRACT", 1.0, crease), b.math("MULTIPLY", pores, 0.15)), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", crease, 0.1),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1.0, vis), 0.05)), clamp=True)
    return dict(roughness=rough, normal=b.bump(h, c * 0.07))


def spangle(b: F, s: dict):
    """Hot-dip galvanized spangle: crystals (Voronoi cells) each with its own brightness, roughness and grain."""
    cell = s["cell"]
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(1.0 / cell), scale=cell * 0.6))
    v = b.vor(warp, 1.0 / cell, "F1", 1.0)
    rnd = b.sep(v[1])
    dirv = b.vmath("SUBTRACT", v[1], (0.5, 0.5, 0.5))
    feather = b.noise(w=b.math("MULTIPLY", b.vmath("DOT_PRODUCT", b.p(), dirv), 4.0 / 0.0006), scale=1.0, detail=1.0)
    vis = b.lod(cell, 1.0, 3.0)
    lo, hi = s["rough_min"], s["rough_max"]
    rough = b.math("ADD", b.map(rnd[0], 0.0, 1.0, lo, hi), b.math("MULTIPLY", b.math("SUBTRACT", feather, 0.5), 0.1))
    rough = b.mix("FLOAT", vis, (lo + hi) / 2 + 0.03, rough)
    bright = b.map(rnd[1], 0.0, 1.0, 0.75, 1.05)
    col = b.vmath("SCALE", lin(s["color"]), scale=b.mix("FLOAT", vis, 0.92, bright))
    # the crystal edges from the same cells (the study's second Voronoi for the edges: dropped – the brightness steps
    # between crystals draw the edges already)
    h = b.math("MULTIPLY", b.math("MULTIPLY", feather, 0.3), vis)
    tang = b.world_tangent(dirv)
    return dict(color=col, roughness=rough, normal=b.bump(h, 0.00003), tangent=tang,
                anisotropic=b.math("MULTIPLY", vis, 0.5))


def as_cast(b: F, s: dict):
    """Sand-cast: a sand grain (noise: 0.5 mm cells, the study's Voronoi cost +41 %), a soft waviness, blotches."""
    g = s["grain"]
    vis = b.lod(g)
    grain = b.noise3(scale=1.0 / g, detail=2.0, rough=0.6)
    wav = b.noise3(scale=1.0 / s["wave"], detail=2.0)
    h = b.math("ADD", b.math("MULTIPLY", b.math("MULTIPLY", grain, 0.6), vis), b.math("MULTIPLY", wav, 1.5))
    blot = b.noise3(scale=1.0 / 0.015, detail=3.0)
    col = b.mix("RGBA", b.map(blot, 0.3, 0.8, 0.0, 0.35), (*lin(s["color"]), 1), (0.2, 0.2, 0.2, 1))
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", blot, 0.5), 0.15), clamp=True)
    return dict(color=col, roughness=rough, normal=b.bump(h, g * 0.35))


def weave_coords(b: F, closed_count: float = 4.0, tow=None):
    """Task 0318: every CAD face's weave coordinates (metres) and the two fibre directions (object space).

    The face's own coordinates (``core.finishes._native``): its plane (k 0, 2), (theta r, z) round its axis (k +-1;
    a closed ring is stretched to a whole multiple of ``closed_count`` tows round it, so the weave meets itself) or
    the dome draped from its pole (k +-3); then turned / mirrored and shifted by ``fr_cw_a`` / ``fr_cw_b``
    (``core.finishes.weave_frames``) so that it continues its neighbour across a fold. Returns (U, V, dirU, dirV)."""
    c = b.cyl()
    p = b.p()
    wa, wb = b.sep(b.gattr("fr_cw_a")), b.sep(b.gattr("fr_cw_b"))
    cs, sn, det = wa[0], wa[1], wa[2]
    th0 = wb[2]
    absk = b.math("ABSOLUTE", c["k"])
    rnd = b.cmp(absk, 1.0)
    sph = c["sph"]
    # plane
    up, vp = b.vmath("DOT_PRODUCT", p, c["u"]), b.vmath("DOT_PRODUCT", p, c["w"])
    # round: theta from the middle of the face's gap; a closed ring (theta0 < 0): a whole number of tows round
    closed = b.math("LESS_THAN", th0, -0.5)
    th = b.math("WRAP", b.math("SUBTRACT", c["th"], b.math("MAXIMUM", th0, 0.0)), 2 * math.pi, 0.0)
    circ = b.math("MULTIPLY", c["r"], 2 * math.pi)
    if tow is not None:
        per = float(tow) * closed_count
        n = b.math("MAXIMUM", b.math("ROUND", b.math("DIVIDE", circ, per)), 1.0)
        snap = b.math("DIVIDE", b.math("MULTIPLY", n, per), b.math("MAXIMUM", circ, 1e-9))
        snap = b.mix("FLOAT", closed, 1.0, snap)
    else:
        snap = 1.0
    ur = b.math("MULTIPLY", b.math("MULTIPLY", th, c["r"]), snap)
    vr = c["z"]
    # sphere: (s cos theta, s sin theta)
    cth, sth = b.math("COSINE", c["th"]), b.math("SINE", c["th"])
    us, vs = b.math("MULTIPLY", c["s"], cth), b.math("MULTIPLY", c["s"], sth)
    un = b.mix("FLOAT", sph, b.mix("FLOAT", rnd, up, ur), us)
    vn = b.mix("FLOAT", sph, b.mix("FLOAT", rnd, vp, vr), vs)
    vn = b.math("MULTIPLY", vn, det)
    U = b.math("ADD", b.math("SUBTRACT", b.math("MULTIPLY", cs, un), b.math("MULTIPLY", sn, vn)), wb[0])
    V = b.math("ADD", b.math("ADD", b.math("MULTIPLY", sn, un), b.math("MULTIPLY", cs, vn)), wb[1])
    # the native directions: plane (u, w); round (round the axis, along it); sphere (along U, along V of the drape)
    rhat = b.vmath("NORMALIZE", c["rad"])
    shat = b.vmath("SUBTRACT", b.vmath("SCALE", rhat, scale=b.math("COSINE", c["phi"])),
                   b.vmath("SCALE", c["d"], scale=b.math("SINE", c["phi"])))
    tus = b.vmath("SUBTRACT", b.vmath("SCALE", shat, scale=cth), b.vmath("SCALE", c["tang"], scale=sth))
    tvs = b.vmath("ADD", b.vmath("SCALE", shat, scale=sth), b.vmath("SCALE", c["tang"], scale=cth))
    tu = b.mix("VECTOR", sph, b.mix("VECTOR", rnd, c["u"], c["tang"]), tus)
    tv = b.mix("VECTOR", sph, b.mix("VECTOR", rnd, c["w"], c["d"]), tvs)
    tv = b.vmath("SCALE", tv, scale=det)
    du = b.vmath("SUBTRACT", b.vmath("SCALE", tu, scale=cs), b.vmath("SCALE", tv, scale=sn))
    dv = b.vmath("ADD", b.vmath("SCALE", tu, scale=sn), b.vmath("SCALE", tv, scale=cs))
    return U, V, du, dv


def carbon(b: F, s: dict):
    """Carbon fibre (task 0318): a 2x2 twill or a plain weave of tows ``tow`` wide in every CAD face's own weave
    coordinates (``weave_coords``: no switch between projections, so no 45° seam); each tow's highlight runs along its
    fibres (the alternating sheen), fine fibre streaks, a little brightness per tow; under a smooth clear coat
    (``gloss``: 1 = glossy, 0 = matte). Far away: an even dark grey with a soft sheen."""
    t = float(s["tow"])
    twill = s.get("twill", 1.0) > 0.5
    U, V, du, dv = weave_coords(b, 4.0 if twill else 2.0, tow=t)
    u, v = b.math("DIVIDE", U, t), b.math("DIVIDE", V, t)
    iu, iv = b.math("FLOOR", u), b.math("FLOOR", v)
    per = 4.0 if twill else 2.0   # twill: a tow goes over two, under two, one tow on per row; plain: over one
    m = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), per)
    warp = b.math("LESS_THAN", m, per / 2)
    au = b.tri(u)                                                 # 0 at a tow's edge, 1 in its middle
    av = b.tri(v)
    across = b.mix("FLOAT", warp, av, au)                         # the warp runs along V: across it is U
    # where along its float (the cells it lies on top of: two in a twill) a point is: it dips only at the float's ends
    fu = b.math("SUBTRACT", u, iu)
    fv = b.math("SUBTRACT", v, iv)
    fl = b.mix("FLOAT", warp, b.math("ADD", b.math("SUBTRACT", m, per / 2), fu), b.math("ADD", m, fv))
    along = b.tri(b.math("DIVIDE", fl, per / 2))
    h = b.math("MULTIPLY", b.math("SQRT", across), b.math("ADD", 0.7, b.math("MULTIPLY", b.math("SQRT", along),
                                                                               0.3)))
    vis = b.lod(t)
    fib_w = b.mix("FLOAT", warp, V, U)                            # fibre streaks: a noise across the fibres
    fib = b.noise(w=b.math("MULTIPLY", fib_w, 3500.0), scale=1.0, detail=2.0)
    n = b.node("ShaderNodeTexWhiteNoise")
    n.noise_dimensions = "3D"
    b.put(n.inputs["Vector"], b.comb(iu, iv, warp))
    tone = b.math("MULTIPLY", b.math("SUBTRACT", n.outputs["Value"], 0.5), 0.5)    # each tow a little different
    base = lin(s["color"])
    lite = (*[min(1.0, x * 2.6 + 0.012) for x in base], 1.0)
    shade = b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", fib, 0.55), b.math("MULTIPLY", tone, 0.45)), vis)
    col = b.mix("RGBA", b.math("ADD", shade, 0.2), (*base, 1.0), lite)
    tang = b.world_tangent(b.mix("VECTOR", warp, du, dv))
    gloss = float(s.get("gloss", 1.0))
    rough = b.math("ADD", s["roughness"] + (1.0 - gloss) * 0.12,
                   b.math("MULTIPLY", b.math("SUBTRACT", fib, 0.5), 0.08), clamp=True)
    return dict(color=col, roughness=rough, normal=b.bump(b.math("MULTIPLY", h, vis), t * 0.05),
                tangent=tang, anisotropic=b.math("MULTIPLY", vis, s.get("anisotropic", 0.75)),
                coat_roughness=0.03 + (1.0 - gloss) * 0.32, coat_normal=False)


def perlage(b: F, s: dict):
    """Perlage / engine turning (task 0318): a brushed circle every ``spacing`` in rows on each CAD face (its own weave
    coordinates: flat on a plate, round a shaft, draped over a dome); a later spot covers the earlier ones (along the
    row, then the next row), so every spot shows a whole edge on one side and is cut by its neighbours on the other.
    Each spot: fine circular scratches round its own centre, the highlight stretched across them (a radial streak
    that turns from spot to spot), its own shade, a faint step at its edge."""
    S = float(s["spacing"])
    R = 0.8 * S
    U, V, du, dv = weave_coords(b)
    iu = b.math("FLOOR", b.math("DIVIDE", U, S))
    iv = b.math("FLOOR", b.math("DIVIDE", V, S))
    fu = b.math("SUBTRACT", U, b.math("MULTIPLY", iu, S))
    fv = b.math("SUBTRACT", V, b.math("MULTIPLY", iv, S))
    bu, bv, bid = None, None, None
    for cu, cv in ((0, 0), (1, 0), (0, 1), (1, 1)):         # in the order they were made: the last one on top
        ou = b.math("SUBTRACT", fu, cu * S)
        ov = b.math("SUBTRACT", fv, cv * S)
        inside = b.math("LESS_THAN", b.math("ADD", b.math("MULTIPLY", ou, ou), b.math("MULTIPLY", ov, ov)), R * R)
        sid = b.comb(b.math("ADD", iu, float(cu)), b.math("ADD", iv, float(cv)), 0.0)
        if bu is None:
            bu, bv, bid = ou, ov, sid
        else:
            bu = b.mix("FLOAT", inside, bu, ou)
            bv = b.mix("FLOAT", inside, bv, ov)
            bid = b.mix("VECTOR", inside, bid, sid)
    rr = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", bu, bu), b.math("MULTIPLY", bv, bv)))
    wn = b.node("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    b.put(wn.inputs["Vector"], bid)
    rnd = wn.outputs["Value"]
    # the scratches: rings round the spot's centre, each spot's own (its random number shifts the noise)
    rings = b.noise(w=b.math("ADD", b.math("MULTIPLY", rr, 14000.0), b.math("MULTIPLY", rnd, 97.0)), scale=1.0,
                    detail=3.0)
    vis = b.lod(S)
    edge = b.smooth(rr, R * 0.9, R)                                # the spot's rim, just inside it
    h = b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", rings, 0.6), b.math("MULTIPLY", edge, -0.5)), vis)
    t_obj = b.vmath("ADD", b.vmath("SCALE", du, scale=b.math("MULTIPLY", bv, -1.0)), b.vmath("SCALE", dv, scale=bu))
    tang = b.world_tangent(t_obj)                                  # round the spot: its highlight runs out from it
    shade = b.math("MULTIPLY", b.math("SUBTRACT", rnd, 0.5), b.math("MULTIPLY", vis, 0.18))
    col = b.vmath("SCALE", lin(s["color"]), scale=b.math("ADD", 1.0, shade))
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", b.math("SUBTRACT", rings, 0.5), 0.06),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1.0, vis), 0.06)), clamp=True)
    return dict(color=col, roughness=rough, normal=b.bump(h, 0.000015), tangent=tang,
                anisotropic=b.math("MULTIPLY", vis, s.get("anisotropic", 0.85)))


BUILDERS = {"knurl": knurl, "spun": spun, "faced": faced, "honed": honed, "crosshatch": crosshatch, "fabric": fabric,
            "grille": grille, "perforated": perforated, "expanded": expanded, "tread": tread, "scraped": scraped,
            "soft_touch": soft_touch, "blasted": blasted, "hammertone": hammertone, "wrinkle": wrinkle,
            "antiskid": antiskid, "vdi": vdi, "leather": leather, "spangle": spangle, "as_cast": as_cast,
            "carbon": carbon, "perlage": perlage}


# ---------------------------------------------------------------------------------------------------------------
# into a material
# ---------------------------------------------------------------------------------------------------------------

def apply(b: _Nodes, mat, bsdf, material_id: str, spec: dict, settings: dict, srgb, color, metallic, rough,
          normal):
    """Build the finish of ``material_id`` (``spec`` = the library entry with ``core.finishes.base`` applied) into the
    material. Returns (color, metallic, roughness, normal) for the rest of ``materials.build_nodes`` (wear); sets
    Tangent, Anisotropic and Alpha itself."""
    f = core.get(material_id)
    if f is None:
        return color, metallic, rough, normal
    fb = b if isinstance(b, F) else F(b.nt)
    if fb is not b:
        fb._coord, fb._attrs = b._coord, b._attrs
    s = core.pattern(material_id, settings)
    s.update(color=tuple(srgb), roughness=float(spec.get("roughness", 0.4)), metallic=float(spec.get("metallic", 0.0)))
    got = BUILDERS[f["kind"]](fb, s)
    if got.get("color") is not None:
        color = got["color"]
    if got.get("metallic") is not None:
        metallic = got["metallic"]
    if got.get("roughness") is not None:
        rough = got["roughness"]
    if got.get("normal") is not None:
        normal = got["normal"]
        if spec.get("coat") and got.get("coat_normal", True):    # carbon: its clear coat lies smooth over the weave
            fb.nt.links.new(got["normal"], bsdf.inputs["Coat Normal"])
    if got.get("coat_roughness") is not None:
        fb.put(bsdf.inputs["Coat Roughness"], got["coat_roughness"])
    if got.get("tangent") is not None:
        fb.nt.links.new(got["tangent"], bsdf.inputs["Tangent"])
    if got.get("anisotropic") is not None:
        fb.put(bsdf.inputs["Anisotropic"], got["anisotropic"])
    if got.get("alpha") is not None:
        fb.put(bsdf.inputs["Alpha"], got["alpha"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
    far = core.far(material_id, settings)
    if spec.get("needs_color"):
        far["color"] = tuple(srgb)
        if f.get("far_color"):
            far["color"] = tuple(c * f["far_color"] for c in srgb)
    mat[PROP_FINISH] = material_id
    mat[PROP_WEB] = json.dumps({"mode": f["web"], **{k: (list(v) if isinstance(v, tuple) else v)
                                                      for k, v in far.items()}})
    return color, metallic, rough, normal


def web_numbers(mat) -> dict | None:
    """A finish material's numbers for the web 3D model: {mode, roughness, metallic, color (sRGB), alpha} or None."""
    if mat is None or not mat.get(PROP_WEB):
        return None
    try:
        return json.loads(mat[PROP_WEB])
    except (TypeError, ValueError):
        return None


def node_count(mat) -> int:
    return len(mat.node_tree.nodes) if mat is not None and mat.node_tree is not None else 0


def register() -> None:
    from . import cameras
    cameras.register_pixel_angle()


def unregister() -> None:
    from . import cameras
    cameras.unregister_pixel_angle()
