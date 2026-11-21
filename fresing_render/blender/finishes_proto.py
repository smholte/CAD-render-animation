"""Study 0270 – new finishes, prototype only (branch ``task/0270-study-finishes``, never merged).

Every finish is procedural and needs no UV map. Where a pattern has a direction it takes it from the part itself:

* **The CAD face's own axis** (knurl, spun rings, faced spiral, honed bore, grip pattern): the importer already keeps
  every round face's axis (``fr_axes`` + ``fr_axis_faces``, cache 3). ``prepare_faces`` turns them into four FACE
  attributes on the mesh (every copy shares them) – ``fr_fx_o`` a point of the axis, ``fr_fx_d`` its direction,
  ``fr_fx_r`` the face's own radius (median distance of its points, so a stepped shaft's faces each have theirs),
  ``fr_fx_k`` the kind: 1 round face (outside), -1 round face (inside: a bore), 2 a flat / domed face on an axis (an
  end face: its centre is on that axis), 0 anything else. Faces without an axis of their own (the cup's sphere faces:
  ``_face_axis`` knows no spheres) take the part's round axis (``materials.part_axes``) when they lie round it.
* **The part's own box axes** (tread plate, perforated, expanded metal, carbon, scraped ways, perlage, weave, the
  moulded grid): a triplanar projection in object space – on flat faces exactly one projection, on curved faces a
  blend of three (``_tri``).
* **Nothing at all** (blasted, hammertone, wrinkle, anti-skid, grain, galvanised spangle, as-cast, rust): 3-D noise in
  object space.
* **A seam the user points at** (weld bead + heat tint): a line kept as two OBJECT properties ``fr_weld_a/b`` (object
  space) on every part that touches it; the bead is a mesh of its own.

Far away a pattern fades to its average (``_lod``): the size of one pixel on the part is its distance from the camera
x ``PIXEL_ANGLE`` (a value node "FR pixel angle" in every material, set per camera by ``set_pixel_angle``); a pattern
whose period covers fewer than ~2 pixels is drawn flat with the roughness it averages to, so it cannot shimmer.

Units: metres in object space. Nothing here changes ``materials.py`` or ``materials_lib.py``."""

from __future__ import annotations

import math

import bpy
import numpy as np

from . import materials
from .materials import _Nodes

PIX = "FR pixel angle"


# ---------------------------------------------------------------------------------------------------------------
# face attributes from the importer's axes
# ---------------------------------------------------------------------------------------------------------------

def prepare_faces(me) -> dict:
    """Write ``fr_fx_o/d/r/k`` (FACE domain) on a mesh from its ``fr_axes``. Returns counts per kind."""
    materials.ensure_axes(me)
    P = len(me.polygons)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(P, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    tri = lv[np.add.outer(ls, np.arange(3))] if P else np.zeros((0, 3), np.int64)   # the importer's meshes: triangles
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    cen = (a + b + c) / 3
    cr = np.cross(b - a, c - a)
    area = np.linalg.norm(cr, axis=1) / 2
    nrm = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-20)

    o = np.zeros((P, 3))
    d = np.zeros((P, 3))
    r = np.zeros(P)
    k = np.zeros(P)
    axes = np.array(me.get("fr_axes", []), float).reshape(-1, 7)
    axf = np.array(me.get("fr_axis_faces", []), np.int64).reshape(-1, 3)
    starts = list(me.get("fr_face_starts", [])) or [0]
    bounds = list(starts) + [P]
    has_axis = np.zeros(P, bool)
    for t0, n, idx in axf:                      # round faces: their own axis, their own radius
        sl = slice(int(t0), int(t0 + n))
        ax = axes[idx]
        oo, dd = ax[:3], ax[3:6] / max(np.linalg.norm(ax[3:6]), 1e-12)
        vid = np.unique(tri[sl].ravel())
        pc = co[vid] - oo
        rad = pc - np.outer(pc @ dd, dd)
        rr = float(np.median(np.linalg.norm(rad, axis=1))) if len(vid) else 0.0
        pcf = cen[sl] - oo
        radf = pcf - np.outer(pcf @ dd, dd)
        inside = float(np.sum(np.einsum("ij,ij->i", nrm[sl], radf) * area[sl])) < 0
        o[sl], d[sl], r[sl], k[sl] = oo, dd, rr, (-1.0 if inside else 1.0)
        has_axis[sl] = True
    # the part's round axis (its box centre), for faces that have none of their own
    lo, hi = co.min(0) if len(co) else np.zeros(3), co.max(0) if len(co) else np.zeros(3)
    part_axis = (np.array(me[materials.AX_CENTRE]), np.array(me[materials.AX_ROUND]))
    across = (hi - lo)[np.array(me[materials.AX_ROUND]) < 0.5]          # the two sides square to the round axis
    part_round = len(across) == 2 and across.min() / max(across.max(), 1e-12) > 0.9
    cand = [(ax[:3], ax[3:6] / max(np.linalg.norm(ax[3:6]), 1e-12)) for ax in axes]
    if part_round:
        cand.append(part_axis)
    for f in range(len(bounds) - 1):            # every other CAD face: an end face on an axis?
        sl = slice(bounds[f], bounds[f + 1])
        if bounds[f + 1] <= bounds[f] or has_axis[sl].any():
            continue
        w = area[sl]
        if w.sum() <= 0:
            continue
        nm = (nrm[sl] * w[:, None]).sum(0)
        nm /= max(np.linalg.norm(nm), 1e-12)
        cm = (cen[sl] * w[:, None]).sum(0) / w.sum()
        span = float(np.linalg.norm(np.ptp(co[np.unique(tri[sl].ravel())], 0))) if bounds[f + 1] > bounds[f] else 0.0
        best = None
        for oo, dd in cand:
            if abs(float(nm @ dd)) < 0.9:
                continue
            pc = cm - oo
            off = float(np.linalg.norm(pc - dd * (pc @ dd)))
            if off < 0.15 * span + 1e-6 and (best is None or off < best[0]):
                best = (off, oo, dd)
        if best is not None:
            o[sl], d[sl], k[sl] = best[1], best[2] * np.sign(float(nm @ best[2]) or 1.0), 2.0
            vid = np.unique(tri[sl].ravel())
            pc = co[vid] - best[1]
            r[sl] = float(np.max(np.linalg.norm(pc - np.outer(pc @ best[2], best[2]), axis=1)))
        else:
            o[sl], d[sl], k[sl] = cm, nm, 0.0
    for name, arr, kind in (("fr_fx_o", o, "FLOAT_VECTOR"), ("fr_fx_d", d, "FLOAT_VECTOR"), ("fr_fx_r", r, "FLOAT"),
                            ("fr_fx_k", k, "FLOAT")):
        if name in me.attributes:
            me.attributes.remove(me.attributes[name])
        at = me.attributes.new(name, kind, "FACE")
        at.data.foreach_set("vector" if kind == "FLOAT_VECTOR" else "value", arr.astype(np.float32).ravel())
    return {"round": int((k == 1).sum()), "bore": int((k == -1).sum()), "end": int((k == 2).sum()),
            "other": int((k == 0).sum())}


def set_pixel_angle(scene, cam=None) -> float:
    """Radians per pixel of the scene's camera, into every material's "FR pixel angle" node."""
    cam = cam or scene.camera
    r = scene.render
    px = max(r.resolution_x * r.resolution_percentage / 100.0, 1.0)
    cd = cam.data
    fov = 2 * math.atan(cd.sensor_width / 2 / cd.lens) if cd.sensor_fit != "VERTICAL" else cd.angle
    ang = fov / px
    for m in bpy.data.materials:
        if m.node_tree is not None:
            n = m.node_tree.nodes.get(PIX)
            if n is not None:
                n.outputs[0].default_value = ang
    return ang


# ---------------------------------------------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------------------------------------------

class F(_Nodes):
    """``_Nodes`` + what the finishes share."""

    def __init__(self, nt):
        super().__init__(nt)
        self._geo = {}
        self._cyl = None
        self._pix = None
        self._cam = None

    def p(self):
        return self.coord("Object")

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
        """A noise's colour (a random vector field) in object space."""
        n = self.node("ShaderNodeTexNoise")
        self.put(n.inputs["Vector"], self.p())
        self.put(n.inputs["Scale"], scale)
        return self.vmath("SUBTRACT", n.outputs["Color"], (0.5, 0.5, 0.5))

    def n(self):
        return self.coord("Normal")              # object space

    def gattr(self, name):
        if name not in self._geo:
            a = self.node("ShaderNodeAttribute", -2100, 400 - 150 * len(self._geo))
            a.attribute_type = "GEOMETRY"
            a.attribute_name = name
            self._geo[name] = a
        a = self._geo[name]
        return a.outputs["Vector"] if name in ("fr_fx_o", "fr_fx_d") else a.outputs["Fac"]

    def oattr(self, name):
        a = self.node("ShaderNodeAttribute", -2100, -1600)
        a.attribute_type = "OBJECT"
        a.attribute_name = name
        return a.outputs["Vector"]

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

    def cyl(self):
        """Per face: (z along the axis, rho from the axis, theta 0..2pi round it, face radius, kind) – metres."""
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
            self._cyl = dict(z=z, rho=rho, th=th, r=self.gattr("fr_fx_r"), k=self.gattr("fr_fx_k"), d=d,
                             tang=tang, rad=rad)
        return self._cyl

    def _cmp(self, a, value):
        n = self.node("ShaderNodeMath")
        n.operation = "COMPARE"
        self.put(n.inputs[0], a)
        n.inputs[1].default_value = value
        n.inputs[2].default_value = 0.25
        return n.outputs[0]

    def lod(self, period_m: float, lo: float = 1.5, hi: float = 4.0):
        """1 where the pattern's period covers >= ``hi`` pixels, 0 below ``lo`` pixels."""
        if self._pix is None:
            v = self.node("ShaderNodeValue", -2100, 800)
            v.name = v.label = PIX
            v.outputs[0].default_value = 0.0006
            self._pix = v.outputs[0]
            cam = self.node("ShaderNodeCameraData", -2100, 1000)
            self._cam = self.math("MULTIPLY", cam.outputs["View Distance"], self._pix)    # metres per pixel
        px = self.math("DIVIDE", float(period_m), self._cam)
        return self.smooth(px, lo, hi)

    def tri_planar(self, fn, sharp: float = 8.0):
        """Triplanar in object space: ``fn(u, v, k)`` -> a height socket for the projection along axis k (u, v the
        two other axes). Weights |n_k|^sharp, normalised. Returns the blended height."""
        ps = self.sep(self.p())
        ns = self.sep(self.n())
        hs, ws = [], []
        for k in range(3):
            i, j = [a for a in range(3) if a != k]
            hs.append(fn(ps[i], ps[j], k))
            ws.append(self.math("POWER", self.math("ABSOLUTE", ns[k]), sharp))
        tot = self.math("ADD", self.math("ADD", ws[0], ws[1]), ws[2])
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

    def vor(self, vec, scale, feature="F1", rand=1.0, dims="3D", dist="EUCLIDEAN"):
        n = self.node("ShaderNodeTexVoronoi")
        n.voronoi_dimensions = dims
        n.feature = feature
        n.distance = dist
        self.put(n.inputs["Vector"], vec if vec is not None else self.p())
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Randomness"], rand)
        return n.outputs

    def noise3(self, vec=None, scale=1.0, detail=2.0, rough=0.5, kind="FBM", distortion=0.0):
        n = self.node("ShaderNodeTexNoise")
        try:
            n.noise_type = kind
        except Exception:
            pass
        self.put(n.inputs["Vector"], vec if vec is not None else self.p())
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Detail"], detail)
        self.put(n.inputs["Roughness"], rough)
        self.put(n.inputs["Distortion"], distortion)
        return n.outputs["Fac"]

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        cr = n.color_ramp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1.0)
        for pos, col in stops[1:]:
            e = cr.elements.new(pos)
            e.color = (*col, 1.0)
        self.put(n.inputs["Fac"], fac)
        return n.outputs["Color"]


def lin(c):
    from ..core import ral
    return tuple(ral.srgb_to_linear(x) for x in c)


# ---------------------------------------------------------------------------------------------------------------
# the finishes: each builder returns the Principled inputs it sets (sockets or numbers)
# ---------------------------------------------------------------------------------------------------------------

def _knurl(b: F, s: dict, diamond: bool):
    c = b.cyl()
    p = s["pitch"]
    beta = math.radians(s.get("angle", 30.0))
    vis = b.lod(p)
    on = b.math("MULTIPLY", b._cmp(c["k"], 1.0), vis)
    if diamond:
        # two families of grooves at +-angle to the axis; a whole number of teeth round the face: no seam
        n_t = b.math("ROUND", b.math("MULTIPLY", c["r"], 2 * math.pi * math.cos(beta) / p))
        a = b.math("MULTIPLY", b.math("DIVIDE", c["th"], 2 * math.pi), n_t)
        zz = b.math("MULTIPLY", c["z"], math.sin(beta) / p)
        h = b.math("MINIMUM", b.tri(b.math("ADD", a, zz)), b.tri(b.math("SUBTRACT", a, zz)))
    else:
        n_t = b.math("ROUND", b.math("MULTIPLY", c["r"], 2 * math.pi / p))
        h = b.tri(b.math("MULTIPLY", b.math("DIVIDE", c["th"], 2 * math.pi), n_t))
    h = b.math("MINIMUM", b.math("MULTIPLY", h, 1.3), 1.0)            # the tips are slightly flat
    h = b.math("MULTIPLY", h, on)
    valley = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, h), on)
    far = b.math("MULTIPLY", b._cmp(c["k"], 1.0), b.math("SUBTRACT", 1.0, vis))
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", valley, 0.12),
                                                  b.math("MULTIPLY", far, 0.14)))
    col = b.mix("RGBA", b.math("MULTIPLY", valley, 0.35), (*lin(s["color"]), 1), (0.05, 0.05, 0.05, 1))
    normal = b.bump(h, 0.35 * p)
    if s.get("spun_ends", True):            # the end faces of a knurled knob are faced / spun: rings round the axis
        hr, tangent, _on = _rings(b, {**s, "ring_k": 20000.0})
        end = b._cmp(c["k"], 2.0)
        normal = b.bump(b.math("MULTIPLY", hr, end), 0.00004, 1.0, normal)
        return dict(color=col, roughness=rough, normal=normal, tangent=tangent, anisotropic=b.math("MULTIPLY", end, 0.7))
    return dict(color=col, roughness=rough, normal=normal)


def knurl_diamond(b, s):
    return _knurl(b, s, True)


def knurl_straight(b, s):
    return _knurl(b, s, False)


def _rings(b: F, s: dict):
    """Spun / turned rings: fine noise of the distance from the face's axis (end faces) or of z (round faces)."""
    c = b.cyl()
    end = b._cmp(c["k"], 2.0)
    w = b.mix("FLOAT", end, c["z"], c["rho"])
    f1 = b.noise(w=b.math("MULTIPLY", w, s["ring_k"]), scale=1.0, detail=3.0)
    f2 = b.noise(w=b.math("MULTIPLY", w, s["ring_k"] / 23.0), scale=1.0, detail=1.0)
    vis = b.lod(1.0 / s["ring_k"] * 8)
    h = b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", f1, 0.7), b.math("MULTIPLY", f2, 0.3)), vis)
    any_axis = b.math("GREATER_THAN", b.math("ABSOLUTE", c["k"]), 0.5)
    return h, b.world_tangent(c["tang"]), any_axis


def spun(b: F, s: dict):
    h, tangent, on = _rings(b, s)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", h, 0.5), 0.08))
    return dict(roughness=rough, normal=b.bump(b.math("MULTIPLY", h, on), 0.00004), tangent=tangent,
                anisotropic=b.math("MULTIPLY", on, s["anisotropic"]))


def faced_spiral(b: F, s: dict):
    """The faced end of a turned part: one spiral groove per feed, round the face's own centre."""
    c = b.cyl()
    f = s["feed"]
    end = b._cmp(c["k"], 2.0)
    sp = b.math("ADD", b.math("DIVIDE", c["rho"], f), b.math("DIVIDE", c["th"], 2 * math.pi))
    vis = b.lod(f)
    h = b.math("MULTIPLY", b.math("MULTIPLY", b.tri(sp), end), vis)
    hr, tangent, on = _rings(b, {**s, "ring_k": 1.0 / f * 0.7})
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", h, 0.06))
    return dict(roughness=rough, normal=b.bump(h, 0.25 * f), tangent=tangent,
                anisotropic=b.math("MULTIPLY", on, s["anisotropic"]))


def crosshatch(b: F, s: dict):
    """Moulded fine raised grid on a (double-)curved plastic shell: triplanar in the part's own space."""
    p, wl = s["pitch"], s["line"]

    def grid(u, v, k):
        gu = b.smooth(b.math("MULTIPLY", b.tri(b.math("DIVIDE", b.math("ADD", u, v), p * math.sqrt(2))), p / 2), 0.0, wl)
        gv = b.smooth(b.math("MULTIPLY", b.tri(b.math("DIVIDE", b.math("SUBTRACT", u, v), p * math.sqrt(2))), p / 2), 0.0, wl)
        return b.math("SUBTRACT", 1.0, b.math("MULTIPLY", gu, gv))          # 1 on the raised lines
    vis = b.lod(p)
    h = b.math("MULTIPLY", b.tri_planar(grid, s.get("sharp", 8.0)), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, -0.08),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.06)))
    return dict(roughness=rough, normal=b.bump(h, s["height"]))


def fabric(b: F, s: dict):
    """Plain weave of threads ``pitch`` apart, triplanar; a fabric sheen."""
    p = s["pitch"]

    def weave(u, v, k):
        iu = b.math("FLOOR", b.math("DIVIDE", u, p))
        iv = b.math("FLOOR", b.math("DIVIDE", v, p))
        par = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 2.0)
        au = b.tri(b.math("DIVIDE", u, p))                     # across a weft thread: 0 at its edges
        av = b.tri(b.math("DIVIDE", v, p))
        thr_u = b.math("SQRT", b.math("MAXIMUM", av, 0.0))     # weft thread (along u) seen across v
        thr_v = b.math("SQRT", b.math("MAXIMUM", au, 0.0))
        bend_u = b.math("SINE", b.math("MULTIPLY", au, math.pi / 2))
        bend_v = b.math("SINE", b.math("MULTIPLY", av, math.pi / 2))
        top_u = b.math("MULTIPLY", thr_u, b.mix("FLOAT", par, bend_v, b.math("SUBTRACT", 1.0, bend_v)))
        top_v = b.math("MULTIPLY", thr_v, b.mix("FLOAT", par, b.math("SUBTRACT", 1.0, bend_u), bend_u))
        return b.math("MAXIMUM", top_u, top_v)
    vis = b.lod(p)
    h = b.math("MULTIPLY", b.tri_planar(weave, 8.0), vis)
    fib = b.noise3(scale=1.0 / p * 6, detail=2.0)
    col = b.mix("RGBA", b.math("MULTIPLY", b.math("SUBTRACT", 1.0, h), 0.6),
                (*lin(s["color"]), 1), (*[x * 0.25 for x in lin(s["color"])], 1))
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", fib, 0.05))
    return dict(color=col, roughness=rough, normal=b.bump(h, 0.45 * p))


def grille(b: F, s: dict):
    """Fine plastic grille: round holes on a 60° grid, see-through; far away the open area."""
    p, rh = s["pitch"], s["hole"] / 2

    def holes(u, v, k):
        # a hex grid: rows p*sqrt(3)/2 apart, every second row shifted by p/2
        rowh = p * math.sqrt(3) / 2
        row = b.math("FLOOR", b.math("DIVIDE", v, rowh))
        shift = b.math("MULTIPLY", b.math("FLOORED_MODULO", row, 2.0), p / 2)
        uu = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, shift), p, 0.0), p / 2)
        vv = b.math("SUBTRACT", b.math("WRAP", v, rowh, 0.0), rowh / 2)
        dd = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu, uu), b.math("MULTIPLY", vv, vv)))
        # the next row's holes at the cell's corners
        uu2 = b.math("SUBTRACT", b.math("ABSOLUTE", uu), p / 2)
        vv2 = b.math("SUBTRACT", b.math("ABSOLUTE", vv), rowh / 2)
        d2 = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu2, uu2), b.math("MULTIPLY", vv2, vv2)))
        return b.math("MINIMUM", dd, d2)
    dist = b.tri_planar(holes, 16.0)
    vis = b.lod(p, 2.0, 5.0)
    solid = b.smooth(dist, rh * 0.92, rh * 1.08)                   # 0 in a hole
    open_area = math.pi * rh * rh / (p * p * math.sqrt(3) / 2)
    alpha = b.mix("FLOAT", vis, 1.0 - open_area, solid)
    return dict(alpha=alpha, normal=b.bump(b.math("MULTIPLY", solid, vis), 0.0003))


def soft_touch(b: F, s: dict):
    vis = b.lod(1.0 / s["grain"] * 3)
    h = b.math("MULTIPLY", b.noise3(scale=s["grain"], detail=3.0), vis)
    return dict(normal=b.bump(h, 0.00002, 1.0))


def blasted(b: F, s: dict):
    """Bead / sand / shot blasted: isotropic dimples (3-D Voronoi), a little colour from the grain."""
    g = s["grain"]
    vis = b.lod(1.0 / g * 2)
    v = b.vor(None, g, "SMOOTH_F1")
    h = b.math("MULTIPLY", b.math("POWER", v[0], 0.7), vis)
    n2 = b.noise3(scale=g / 6, detail=4.0)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", n2, 0.5), s.get("rough_var", 0.08)))
    col = b.mix("RGBA", b.math("MULTIPLY", n2, s.get("color_var", 0.1)), (*lin(s["color"]), 1), (0.1, 0.1, 0.1, 1))
    return dict(color=col, roughness=rough, normal=b.bump(h, s["depth"]))


def hammertone(b: F, s: dict):
    cell = s["cell"]
    v = b.vor(b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(60.0), scale=cell * 0.5)), 1.0 / cell, "SMOOTH_F1", 0.9)
    vis = b.lod(cell)
    d = v[0]
    h = b.math("MULTIPLY", b.math("POWER", b.map(d, 0.0, 0.75, 0.0, 1.0), 2.0), vis)   # a round dimple per cell
    flake = b.vor(None, 1.0 / 0.00015, "F1")[1]                   # tiny metal flakes: a colour per flake
    fl = b.sep(flake)[0]
    base = (*lin(s["color"]), 1)
    light = (*[min(1, x * 1.7 + 0.04) for x in lin(s["color"])], 1)
    col = b.mix("RGBA", b.map(h, 0.3, 1.0, 0.0, 0.8), base, light)          # rims catch more light
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", fl, 0.5), 0.12))
    return dict(color=col, roughness=rough, metallic=s.get("metallic", 0.45), normal=b.bump(h, cell * 0.09))


def wrinkle(b: F, s: dict):
    """Wrinkle paint: worm-like ridges ~1 mm (the ridges of a distorted noise: 1 - |2n - 1|, sharpened)."""
    sc = s["scale"]
    vis = b.lod(1.0 / sc * 1.5)
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(sc / 3), scale=3.0 / sc))
    n = b.noise3(warp, sc, 2.0, 0.5)
    ridge = b.math("SUBTRACT", 1.0, b.math("ABSOLUTE", b.math("SUBTRACT", b.math("MULTIPLY", n, 2.0), 1.0)))
    h = b.math("MULTIPLY", b.math("POWER", ridge, 4.0), vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", h, -0.12))
    return dict(roughness=rough, normal=b.bump(h, 0.6 / sc))


def antiskid(b: F, s: dict):
    g = s["grit"]
    v = b.vor(None, 1.0 / g, "F1", 1.0)
    keep = b.math("GREATER_THAN", b.sep(v[1])[0], 1.0 - s.get("cover", 0.55))
    bump_h = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.smooth(v[0], 0.05, 0.45)), keep)
    vis = b.lod(g)
    h = b.math("MULTIPLY", bump_h, vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.08))
    col = b.mix("RGBA", b.math("MULTIPLY", h, 0.25), (*lin(s["color"]), 1), (0.9, 0.9, 0.9, 1))
    return dict(color=col, roughness=rough, normal=b.bump(h, g * 0.5))


def _uvk(b: F, fn, sharp=24.0):
    return b.tri_planar(fn, sharp)


def tread(b: F, s: dict):
    """Tread plate ("teardrop"/lens): raised lenses on a square grid, each at 90° to its neighbours. Box projection in
    the part's own axes; pitch chosen so it divides 200 mm (the web model's tile)."""
    P, L, W = s["pitch"], s["length"], s["width"]

    def lens(u, v, k):
        iu = b.math("FLOOR", b.math("DIVIDE", u, P))
        iv = b.math("FLOOR", b.math("DIVIDE", v, P))
        par = b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 2.0)
        lu = b.math("SUBTRACT", b.math("WRAP", u, P, 0.0), P / 2)
        lv = b.math("SUBTRACT", b.math("WRAP", v, P, 0.0), P / 2)
        c, sn = math.cos(math.radians(45)), math.sin(math.radians(45))
        ru = b.math("ADD", b.math("MULTIPLY", lu, c), b.math("MULTIPLY", lv, sn))
        rv = b.math("SUBTRACT", b.math("MULTIPLY", lv, c), b.math("MULTIPLY", lu, sn))
        a_ = b.mix("FLOAT", par, ru, rv)
        b_ = b.mix("FLOAT", par, rv, ru)
        e = b.math("ADD", b.math("POWER", b.math("ABSOLUTE", b.math("DIVIDE", a_, L / 2)), 2.0),
                   b.math("POWER", b.math("ABSOLUTE", b.math("DIVIDE", b_, W / 2)), 2.0))
        return b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", 1.0, e), 0.0))
    vis = b.lod(P)
    h = b.math("MULTIPLY", _uvk(b, lens), vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", h, -0.06))
    return dict(roughness=rough, normal=b.bump(h, s["height"]))


def perforated(b: F, s: dict):
    p, rh = s["pitch"], s["hole"] / 2
    slot = s.get("slot", 0.0)

    def holes(u, v, k):
        rowh = p * math.sqrt(3) / 2 if not slot else p
        row = b.math("FLOOR", b.math("DIVIDE", v, rowh))
        shift = b.math("MULTIPLY", b.math("FLOORED_MODULO", row, 2.0), (p if not slot else slot + p) / 2)
        per = p if not slot else slot + p
        uu = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, shift), per, 0.0), per / 2)
        vv = b.math("SUBTRACT", b.math("WRAP", v, rowh, 0.0), rowh / 2)
        if slot:      # a slot: a straight piece slot - 2 rh long with round ends
            uu = b.math("MAXIMUM", b.math("SUBTRACT", b.math("ABSOLUTE", uu), slot / 2 - rh), 0.0)
        return b.math("SQRT", b.math("ADD", b.math("MULTIPLY", uu, uu), b.math("MULTIPLY", vv, vv)))
    dist = _uvk(b, holes)
    vis = b.lod(p, 2.0, 5.0)
    solid = b.smooth(dist, rh * 0.96, rh * 1.04)
    if slot:
        open_area = (math.pi * rh * rh + (slot - 2 * rh) * 2 * rh) / ((slot + p) * p)
    else:
        open_area = math.pi * rh * rh / (p * p * math.sqrt(3) / 2)
    alpha = b.mix("FLOAT", vis, 1.0 - open_area, solid)
    return dict(alpha=alpha)


def expanded(b: F, s: dict):
    """Expanded metal: diamond openings LWD x SWD in a staggered grid, strands that lean (their facet seen as a
    slope of the height across the strand)."""
    LW, SW, st = s["lwd"], s["swd"], s["strand"]

    def rh(u, v, ou, ov):
        a = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", u, ou), LW, 0.0), LW / 2)
        c = b.math("SUBTRACT", b.math("WRAP", b.math("SUBTRACT", v, ov), SW, 0.0), SW / 2)
        return b.math("ADD", b.math("DIVIDE", b.math("ABSOLUTE", a), LW / 2), b.math("DIVIDE", b.math("ABSOLUTE", c), SW / 2))

    def mesh(u, v, k):
        # two staggered grids of diamonds LW x SW tile the plane; the nearer diamond's measure is 0 (centre) .. 1 (edge)
        return b.math("MINIMUM", rh(u, v, 0.0, 0.0), rh(u, v, LW / 2, SW / 2))
    m = _uvk(b, mesh)
    share = 2.0 * st / SW
    edge = b.smooth(m, 1.0 - share - 0.03, 1.0 - share + 0.03)            # 1 on metal
    vis = b.lod(SW, 2.0, 5.0)
    open_area = (1.0 - share) ** 2
    alpha = b.mix("FLOAT", vis, 1.0 - open_area, edge)
    slope = b.math("MULTIPLY", b.math("MULTIPLY", b.math("DIVIDE", b.math("SUBTRACT", m, 1.0 - share), share), edge), vis)
    return dict(alpha=alpha, normal=b.bump(slope, st * 0.8))


def carbon(b: F, s: dict):
    """2x2 twill, tows ``tow`` wide; each tow's highlight runs along its fibres (alternating tangent)."""
    t = s["tow"]
    ps = b.sep(b.p())
    ns = b.sep(b.n())
    # the box projection's dominant axis (no blend: tows must not mix)
    ax = [b.math("ABSOLUTE", ns[k]) for k in range(3)]
    is_x = b.math("MULTIPLY", b.math("GREATER_THAN", ax[0], ax[1]), b.math("GREATER_THAN", ax[0], ax[2]))
    is_y = b.math("MULTIPLY", b.math("GREATER_THAN", ax[1], ax[0]), b.math("GREATER_THAN", ax[1], ax[2]))
    # u, v: (y, z) on x faces, (x, z) on y faces, (x, y) on z faces
    u = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[0], ps[0]), ps[1])
    v = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[1], ps[2]), ps[2])
    du = b.mix("VECTOR", is_x, b.mix("VECTOR", is_y, (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)), (0.0, 1.0, 0.0))
    dv = b.mix("VECTOR", is_x, b.mix("VECTOR", is_y, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 1.0))
    iu = b.math("FLOOR", b.math("DIVIDE", u, t))
    iv = b.math("FLOOR", b.math("DIVIDE", v, t))
    warp_on_top = b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("ADD", iu, iv), 4.0), 2.0)
    au = b.tri(b.math("DIVIDE", u, t))
    av = b.tri(b.math("DIVIDE", v, t))
    h = b.mix("FLOAT", warp_on_top, b.math("SQRT", av), b.math("SQRT", au))
    vis = b.lod(t)
    fib = b.mix("FLOAT", warp_on_top, b.noise(w=b.math("MULTIPLY", v, 9000.0)), b.noise(w=b.math("MULTIPLY", u, 9000.0)))
    tan_obj = b.mix("VECTOR", warp_on_top, du, dv)
    tang = b.world_tangent(tan_obj)
    col = b.mix("RGBA", b.math("MULTIPLY", fib, 0.4), (*lin(s["color"]), 1), (0.06, 0.06, 0.065, 1))
    return dict(color=col, normal=b.bump(b.math("MULTIPLY", h, vis), t * 0.08), tangent=tang,
                anisotropic=b.math("MULTIPLY", vis, s["anisotropic"]),
                roughness=b.math("ADD", s["roughness"], b.math("MULTIPLY", fib, 0.06)))


def vdi(b: F, s: dict):
    """Spark-eroded VDI 3400 texture: fine random craters; the class sets the crater size and the roughness."""
    g = s["grain"]
    vis = b.lod(1.0 / g * 2)
    v = b.vor(None, g, "SMOOTH_F1", 1.0)
    h = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.math("POWER", v[0], 0.5)), vis)
    return dict(normal=b.bump(h, 0.5 / g))


def leather(b: F, s: dict):
    c = s["cell"]
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(1.0 / c / 3), scale=c * 1.6))
    e = b.vor(warp, 1.0 / c, "DISTANCE_TO_EDGE", 1.0)[0]
    vis = b.lod(c)
    crease = b.math("SUBTRACT", 1.0, b.smooth(e, 0.0, 0.12))
    pores = b.noise3(scale=1.0 / c * 8, detail=2.0)
    h = b.math("MULTIPLY", b.math("SUBTRACT", b.math("SUBTRACT", 1.0, crease), b.math("MULTIPLY", pores, 0.15)), vis)
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", crease, 0.1))
    return dict(roughness=rough, normal=b.bump(h, c * 0.15))


def spangle(b: F, s: dict):
    """Hot-dip galvanised spangle: crystals (Voronoi cells) each with its own brightness, roughness and grain."""
    cell = s["cell"]
    warp = b.vmath("ADD", b.p(), b.vmath("SCALE", b.ncol(1.0 / cell), scale=cell * 0.6))
    v = b.vor(warp, 1.0 / cell, "F1", 1.0)
    rnd = b.sep(v[1])
    # dendrites: a noise stretched along a random direction per crystal
    dirv = b.vmath("SUBTRACT", v[1], (0.5, 0.5, 0.5))
    feather = b.noise(w=b.math("MULTIPLY", b.vmath("DOT_PRODUCT", b.p(), dirv), 4.0 / 0.0006), scale=1.0, detail=2.0)
    vis = b.lod(cell, 1.0, 3.0)
    rough = b.math("ADD", b.map(rnd[0], 0.0, 1.0, s["rough_min"], s["rough_max"]),
                   b.math("MULTIPLY", b.math("SUBTRACT", feather, 0.5), 0.1))
    rough = b.mix("FLOAT", vis, (s["rough_min"] + s["rough_max"]) / 2 + 0.03, rough)
    bright = b.map(rnd[1], 0.0, 1.0, 0.75, 1.05)
    col = b.vmath("SCALE", (*lin(s["color"]),), scale=b.mix("FLOAT", vis, 0.92, bright))
    edge = b.vor(warp, 1.0 / cell, "DISTANCE_TO_EDGE", 1.0)[0]
    h = b.math("MULTIPLY", b.math("ADD", b.smooth(edge, 0.0, 0.06), b.math("MULTIPLY", feather, 0.2)), vis)
    tang = b.world_tangent(dirv)
    return dict(color=col, roughness=rough, normal=b.bump(h, 0.00003), tangent=tang,
                anisotropic=b.math("MULTIPLY", vis, 0.5))


def as_cast(b: F, s: dict):
    g = s["grain"]
    v = b.vor(None, 1.0 / g, "SMOOTH_F1", 1.0)
    wav = b.noise3(scale=1.0 / s["wave"], detail=2.0)
    vis = b.lod(g)
    h = b.math("ADD", b.math("MULTIPLY", b.math("MULTIPLY", b.math("POWER", v[0], 0.6), 0.5), vis),
               b.math("MULTIPLY", wav, 1.5))
    blot = b.noise3(scale=1.0 / 0.015, detail=3.0)
    col = b.mix("RGBA", b.map(blot, 0.3, 0.8, 0.0, 0.35), (*lin(s["color"]), 1), (0.2, 0.2, 0.2, 1))
    rough = b.math("ADD", s["roughness"], b.math("MULTIPLY", b.math("SUBTRACT", blot, 0.5), 0.15))
    return dict(color=col, roughness=rough, normal=b.bump(h, g * 0.35))


def rust(b: F, s: dict):
    """A rust LAYER over a metal (a wear-like slider ``amount``: 0.25 flash rust, 1 heavy)."""
    a = s["amount"]
    m = b.noise3(scale=1.0 / 0.04, detail=6.0, rough=0.65)
    ao = b.node("ShaderNodeAmbientOcclusion", Distance=0.02)
    ao.only_local = True
    ao.samples = 4
    mask = b.smooth(b.math("ADD", m, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, ao.outputs["AO"]), 0.4)),
                    0.75 - 0.4 * a, 0.80 - 0.35 * a)
    flake = b.vor(None, 1.0 / 0.003, "SMOOTH_F1", 1.0)[0]
    col_r = b.ramp(b.noise3(scale=1.0 / 0.006, detail=4.0), [(0.0, (0.10, 0.03, 0.01)), (0.5, (0.30, 0.10, 0.03)),
                                                               (1.0, (0.55, 0.25, 0.08))])
    col = b.mix("RGBA", mask, (*lin(s["color"]), 1), col_r)
    met = b.mix("FLOAT", mask, 1.0, 0.0)
    rough = b.mix("FLOAT", mask, s["roughness"], 0.85)
    h = b.math("MULTIPLY", mask, b.math("ADD", 0.3, b.math("MULTIPLY", flake, a)))
    return dict(color=col, metallic=met, roughness=rough, normal=b.bump(h, 0.0002 + 0.0006 * a))


def honed(b: F, s: dict):
    """Honing cross-hatch in a bore (and the turned rings outside): two families of fine helical scratches."""
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
    inside = b._cmp(c["k"], -1.0)
    vis = b.lod(4.0 / k)
    h = b.math("MULTIPLY", b.math("MULTIPLY", b.math("MAXIMUM", sc1, sc2), inside), vis)
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", h, 0.15),
                                                  b.math("MULTIPLY", inside, b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.08))))
    hr, tangent, on = _rings(b, {**s, "ring_k": 5000.0})
    outside = b._cmp(c["k"], 1.0)
    return dict(roughness=rough, normal=b.bump(b.math("SUBTRACT", b.math("MULTIPLY", hr, outside), h), 0.00003),
                tangent=tangent, anisotropic=b.math("MULTIPLY", outside, 0.5))


def scraped(b: F, s: dict):
    """Scraped / flaked ways: half-moon marks in a checker of cells, every second cell turned 90°."""
    P = s["cell"]

    def flakes(u, v, k):
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
        moon = b.math("MULTIPLY", b.math("LESS_THAN", d1, R), b.math("GREATER_THAN", d2, R * 0.95))
        return moon
    vis = b.lod(P)
    m = b.math("MULTIPLY", _uvk(b, flakes), vis)
    soft = b.math("MULTIPLY", m, b.noise3(scale=1.0 / 0.002, detail=2.0))
    rough = b.math("ADD", s["roughness"], b.math("ADD", b.math("MULTIPLY", m, 0.14),
                                                  b.math("MULTIPLY", b.math("SUBTRACT", 1, vis), 0.05)))
    col = b.mix("RGBA", b.math("MULTIPLY", m, 0.15), (*lin(s["color"]), 1), (1.0, 1.0, 1.0, 1))
    return dict(color=col, roughness=rough, normal=b.bump(soft, 0.00002))


def grip(b: F, s: dict):
    """Moulded grip: truncated pyramids round the handle's own axis (as the diamond knurl, bigger and rounder)."""
    out = _knurl(b, {**s, "angle": 45.0, "spun_ends": False}, True)
    return out


def perlage(b: F, s: dict):
    """Engine turning / perlage: overlapping brushed circles in rows; each later spot covers the earlier ones."""
    S, R = s["spacing"], s["spacing"] * 0.78
    ps = b.sep(b.p())
    ns = b.sep(b.n())
    ax = [b.math("ABSOLUTE", ns[k]) for k in range(3)]
    is_x = b.math("MULTIPLY", b.math("GREATER_THAN", ax[0], ax[1]), b.math("GREATER_THAN", ax[0], ax[2]))
    is_y = b.math("MULTIPLY", b.math("GREATER_THAN", ax[1], ax[0]), b.math("GREATER_THAN", ax[1], ax[2]))
    u = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[0], ps[0]), ps[1])
    v = b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, ps[1], ps[2]), ps[2])
    iu = b.math("FLOOR", b.math("DIVIDE", u, S))
    iv = b.math("FLOOR", b.math("DIVIDE", v, S))
    fu = b.math("SUBTRACT", u, b.math("MULTIPLY", iu, S))
    fv = b.math("SUBTRACT", v, b.math("MULTIPLY", iv, S))
    # candidates at the cell's corners; later (higher v, then higher u) covers earlier
    best_du, best_dv = None, None
    for cu, cv in ((0, 0), (1, 0), (0, 1), (1, 1)):
        du = b.math("SUBTRACT", fu, cu * S)
        dv = b.math("SUBTRACT", fv, cv * S)
        inside = b.math("LESS_THAN", b.math("SQRT", b.math("ADD", b.math("MULTIPLY", du, du),
                                                               b.math("MULTIPLY", dv, dv))), R)
        if best_du is None:
            best_du, best_dv = du, dv
        else:
            best_du = b.mix("FLOAT", inside, best_du, du)
            best_dv = b.mix("FLOAT", inside, best_dv, dv)
    rr = b.math("SQRT", b.math("ADD", b.math("MULTIPLY", best_du, best_du), b.math("MULTIPLY", best_dv, best_dv)))
    rings = b.noise(w=b.math("MULTIPLY", rr, 9000.0), scale=1.0, detail=3.0)
    vis = b.lod(S)
    # tangent round the spot's centre, in object space
    zero = 0.0
    tu = b.math("MULTIPLY", best_dv, -1.0)
    tv = best_du
    t_x = b.comb(b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, tu, tu), zero),
                 b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, tv, zero), tu),
                 b.mix("FLOAT", is_x, b.mix("FLOAT", is_y, zero, tv), tv))
    across = b.world_tangent(t_x)
    edge = b.math("SUBTRACT", 1.0, b.smooth(rr, R * 0.9, R))
    h = b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", rings, 0.3), b.math("MULTIPLY", edge, 0.0)), vis)
    return dict(roughness=b.math("ADD", s["roughness"], b.math("MULTIPLY", rings, 0.05)), tangent=across,
                anisotropic=b.math("MULTIPLY", vis, s["anisotropic"]), normal=b.bump(h, 0.00002))


def heat_tint(b: F, s: dict):
    """Weld heat tint on stainless round a seam line kept on the object (``fr_weld_a``, ``fr_weld_b``)."""
    a, e = b.oattr("fr_weld_a"), b.oattr("fr_weld_b")
    ab = b.vmath("SUBTRACT", e, a)
    t = b.math("DIVIDE", b.vmath("DOT_PRODUCT", b.vmath("SUBTRACT", b.p(), a), ab), b.vmath("DOT_PRODUCT", ab, ab))
    t = b.math("MINIMUM", b.math("MAXIMUM", t, 0.0), 1.0)
    foot = b.vmath("ADD", a, b.vmath("SCALE", ab, scale=t))
    dist = b.vmath("LENGTH", b.vmath("SUBTRACT", b.p(), foot))
    wob = b.math("MULTIPLY", b.noise3(scale=1.0 / 0.006, detail=3.0), 0.004)
    dd = b.math("ADD", dist, wob)
    W = s["width"]
    col = b.ramp(b.math("DIVIDE", dd, W), [(0.0, (0.12, 0.12, 0.13)), (0.12, (0.18, 0.22, 0.42)),
                                           (0.3, (0.35, 0.18, 0.38)), (0.5, (0.55, 0.32, 0.16)),
                                           (0.72, (0.78, 0.62, 0.33)), (1.0, lin(s["color"]))])
    rough = b.map(b.math("DIVIDE", dd, W), 0.0, 1.0, 0.45, s["roughness"])
    return dict(color=col, roughness=rough)


def weld_bead(b: F, s: dict):
    """The bead itself (its own object: a tube along the seam, x along it): ripples like stacked chevrons."""
    ps = b.sep(b.p())
    across = b.math("ABSOLUTE", b.math("ARCTAN2", ps[2], ps[1]))
    rip = b.tri(b.math("ADD", b.math("DIVIDE", ps[0], s["ripple"]), b.math("MULTIPLY", across, 0.6)))
    h = b.math("POWER", rip, 0.6)
    col = b.ramp(b.noise3(scale=1.0 / 0.004, detail=3.0), [(0.0, (0.10, 0.10, 0.11)), (0.6, (0.30, 0.24, 0.20)),
                                                          (1.0, (0.20, 0.25, 0.45))])
    return dict(color=col, roughness=0.35, metallic=1.0, normal=b.bump(h, s["ripple"] * 0.3))


def plain(b, s):
    return {}


# ---------------------------------------------------------------------------------------------------------------
# the list: id -> (label, builder, base Principled values, pattern settings, shapes, real size text, user settings,
#                   offered with, direction source)
# ---------------------------------------------------------------------------------------------------------------

STEEL = (0.63, 0.63, 0.64)
ALU = (0.91, 0.92, 0.93)
STAINLESS = (0.72, 0.72, 0.73)
BRASS = (0.91, 0.78, 0.42)

FINISHES: dict[str, dict] = {
    "knurl_diamond": dict(n=1, label="Diamond knurl", fn=knurl_diamond, shapes=["knob", "grip", "shaft"],
                          base=dict(color=ALU, metallic=1.0, roughness=0.28), pat=dict(pitch=0.0008, angle=30.0),
                          size="pitch 0.8 mm (DIN 82 RGE 0.8), 30°; whole number of teeth round each face",
                          settings="Pitch (0.5 · 0.8 · 1.0 · 1.2 · 1.6 mm), Angle (30° / 45°)",
                          offer="Steel machined, stainless, aluminium machined / anodized, brass",
                          source="the CAD face's own axis + its own radius (round faces only, outside)"),
    "knurl_straight": dict(n=2, label="Straight knurl", fn=knurl_straight, shapes=["knob", "shaft"],
                           base=dict(color=BRASS, metallic=1.0, roughness=0.26), pat=dict(pitch=0.001),
                           size="pitch 1.0 mm (DIN 82 RAA 1.0)", settings="Pitch",
                           offer="as diamond knurl", source="the CAD face's own axis + radius"),
    "spun": dict(n=3, label="Spun / concentric aluminium", fn=spun, shapes=["cap", "knob"],
                 base=dict(color=ALU, metallic=1.0, roughness=0.18), pat=dict(ring_k=20000.0, anisotropic=0.8),
                 size="rings ~0.05 mm (seen as one radial highlight), a faint wider ring every ~1 mm",
                 settings="Strength (how far the highlight stretches)",
                 offer="Aluminium machined / anodized, stainless polished, brass",
                 source="the axis of the face (end faces: the round face they close; else the part's round axis)"),
    "faced": dict(n=4, label="Faced end (spiral)", fn=faced_spiral, shapes=["cap", "shaft"],
                  base=dict(color=STEEL, metallic=1.0, roughness=0.22), pat=dict(feed=0.00025, anisotropic=0.6),
                  size="feed 0.25 mm per turn (one spiral groove)", settings="Feed",
                  offer="Steel turned, aluminium machined, brass", source="the face's axis (end faces)"),
    "crosshatch": dict(n=5, label="Moulded cross-hatch (shell)", fn=crosshatch, shapes=["cup", "block"],
                       base=dict(color=(0.12, 0.22, 0.48), roughness=0.42, specular=0.5), needs_color=True,
                       pat=dict(pitch=0.0009, line=0.00018, height=0.00012),
                       size="grid 0.9 mm at 45°, lines 0.2 mm, raised 0.1 mm",
                       settings="Pitch, Angle (0° / 45°)", offer="Plastic matte / gloss (colour from the group)",
                       source="triplanar in the part's own box axes (blended on curved faces)"),
    "fabric": dict(n=6, label="Woven fabric / speaker cloth", fn=fabric, shapes=["grille", "cushion"],
                   base=dict(color=(0.06, 0.06, 0.065), roughness=0.85, sheen=0.8, sheen_roughness=0.35, specular=0.3),
                   needs_color=True, pat=dict(pitch=0.0005, color=(0.13, 0.13, 0.14), roughness=0.85),
                   size="plain weave, threads 0.5 mm", settings="Thread size, colour from the group",
                   offer="new: Fabric (colour)", source="triplanar in the part's own axes"),
    "grille": dict(n=7, label="Fine plastic mesh grille", fn=grille, shapes=["grille", "plate"],
                   base=dict(color=(0.03, 0.03, 0.035), roughness=0.45, specular=0.5), needs_color=True,
                   pat=dict(pitch=0.0016, hole=0.0011), see_through=True,
                   size="holes Ø1.1 mm, 1.6 mm apart at 60° (43 % open)", settings="Hole size, Pitch",
                   offer="Plastic matte (colour)", source="triplanar in the part's own axes"),
    "soft_touch": dict(n=8, label="Soft-touch matte plastic / rubber", fn=soft_touch, shapes=["band", "cup", "grip"],
                       base=dict(color=(0.05, 0.05, 0.055), roughness=0.62, specular=0.32, sheen=0.45,
                                 sheen_roughness=0.3, coat=0.0), needs_color=True, pat=dict(grain=40000.0),
                       size="no pattern; micro grain 0.025 mm (only in a macro shot)", settings="none (colour)",
                       offer="Plastic & rubber, colour from the group", source="none (3-D noise)"),
    "bead_blasted": dict(n=9, label="Bead-blasted metal", fn=blasted, shapes=["block", "yoke", "cap"],
                         base=dict(color=ALU, metallic=1.0, roughness=0.46),
                         pat=dict(grain=9000.0, depth=0.00003, color=ALU, roughness=0.46, color_var=0.05),
                         size="dimples ~0.1 mm (glass beads)", settings="Coarseness (fine / medium / coarse)",
                         offer="Aluminium, stainless, steel, titanium", source="none (3-D Voronoi)"),
    "shot_blasted": dict(n=10, label="Shot-blasted steel (Sa 2½, before paint)", fn=blasted, shapes=["block", "plate"],
                         base=dict(color=(0.42, 0.42, 0.43), metallic=0.9, roughness=0.62),
                         pat=dict(grain=3500.0, depth=0.00008, color=(0.42, 0.42, 0.43), roughness=0.62,
                                  rough_var=0.12, color_var=0.25),
                         size="dimples ~0.3 mm (steel grit)", settings="none",
                         offer="Steel", source="none (3-D Voronoi)"),
    "hammertone": dict(n=11, label="Hammertone paint", fn=hammertone, shapes=["block", "plate"],
                       base=dict(color=(0.25, 0.33, 0.42), metallic=0.45, roughness=0.3, coat=0.3, coat_roughness=0.15),
                       needs_color=True, pat=dict(cell=0.005, color=(0.25, 0.33, 0.42), roughness=0.3),
                       size="hammer marks ~5 mm, metal flakes", settings="Mark size, colour from the group",
                       offer="new Paint: hammertone (colour)", source="none (3-D Voronoi)"),
    "wrinkle": dict(n=12, label="Wrinkle paint", fn=wrinkle, shapes=["block", "cap"],
                    base=dict(color=(0.03, 0.03, 0.033), roughness=0.55, specular=0.45), needs_color=True,
                    pat=dict(scale=900.0, roughness=0.55), size="wrinkles ~1 mm", settings="Size, colour",
                    offer="new Paint: wrinkle (colour)", source="none (3-D noise)"),
    "antiskid": dict(n=13, label="Anti-skid deck paint", fn=antiskid, shapes=["plate", "block"],
                     base=dict(color=(0.38, 0.42, 0.40), roughness=0.78, specular=0.4), needs_color=True,
                     pat=dict(grit=0.0012, color=(0.38, 0.42, 0.40), roughness=0.78, cover=0.5),
                     size="grit ~1 mm, about half covered", settings="Grit size, colour", offer="new Paint: anti-skid",
                     source="none (3-D Voronoi)"),
    "tread": dict(n=14, label="Tread plate (lens pattern)", fn=tread, shapes=["plate", "way"],
                  base=dict(color=ALU, metallic=1.0, roughness=0.34),
                  pat=dict(pitch=0.025, length=0.022, width=0.006, height=0.0012, roughness=0.34),
                  size="lenses 22 x 6 mm, 25 mm grid (8 per 200 mm), relief 1.2 mm (bump only)",
                  settings="Pitch, Angle of the pattern (0° / 90°)",
                  offer="Aluminium, galvanized, steel raw, painted", source="the part's own box axes (one projection on flat faces)"),
    "perforated": dict(n=15, label="Perforated sheet", fn=perforated, shapes=["plate", "block"],
                       base=dict(color=(0.75, 0.76, 0.77), metallic=1.0, roughness=0.36), see_through=True,
                       pat=dict(pitch=0.008, hole=0.005), size="Rv 5-8: Ø5 mm holes, 8 mm apart at 60° (35 % open); "
                       "also slotted Lv 4x20", settings="Hole Ø, Pitch, Round / Slotted",
                       offer="Galvanized, stainless, aluminium, powder coat", source="the part's own box axes"),
    "expanded": dict(n=16, label="Expanded metal", fn=expanded, shapes=["plate"],
                     base=dict(color=(0.6, 0.61, 0.62), metallic=1.0, roughness=0.42), see_through=True,
                     pat=dict(lwd=0.043, swd=0.0135, strand=0.0022),
                     size="43 x 13.5 mm openings, strands 2.2 mm", settings="Opening size", offer="Galvanized, steel",
                     source="the part's own box axes"),
    "carbon": dict(n=17, label="Carbon fibre twill 2x2", fn=carbon, shapes=["cup", "plate"],
                   base=dict(color=(0.025, 0.025, 0.028), roughness=0.3, specular=0.6, coat=1.0, coat_roughness=0.03),
                   pat=dict(tow=0.002, color=(0.025, 0.025, 0.028), roughness=0.3, anisotropic=0.75),
                   size="3K twill, tows 2 mm", settings="Tow width, Gloss / Matte clear coat",
                   offer="new: Carbon fibre", source="the part's own box axes (dominant projection, no blend)"),
    "vdi": dict(n=18, label="Spark-eroded texture VDI 3400 (24 / 30 / 36)", fn=vdi, shapes=["block", "cup"],
                base=dict(color=(0.04, 0.04, 0.045), roughness=0.5, specular=0.45), needs_color=True,
                pat=dict(grain=14000.0), size="VDI 24: Ra 1.6 µm, 30: 3.2 µm, 36: 6.3 µm; craters 0.05-0.15 mm",
                settings="Class (24 · 27 · 30 · 33 · 36)", offer="Plastic matte (colour)", source="none (3-D Voronoi)",
                variants={"VDI 24": dict(roughness=0.38, grain=22000.0), "VDI 30": dict(roughness=0.5, grain=14000.0),
                          "VDI 36": dict(roughness=0.64, grain=8000.0)}),
    "leather": dict(n=19, label="Moulded leather grain", fn=leather, shapes=["cup", "band", "cushion"],
                    base=dict(color=(0.05, 0.05, 0.055), roughness=0.5, specular=0.4, sheen=0.25), needs_color=True,
                    pat=dict(cell=0.0016, roughness=0.5), size="cells ~1.6 mm", settings="Grain size, colour",
                    offer="Plastic matte / rubber (colour)", source="none (3-D Voronoi)"),
    "spangle": dict(n=20, label="Hot-dip galvanised spangle", fn=spangle, shapes=["plate", "block"],
                    base=dict(color=(0.70, 0.71, 0.72), metallic=1.0, roughness=0.3),
                    pat=dict(cell=0.009, color=(0.70, 0.71, 0.72), rough_min=0.15, rough_max=0.45),
                    size="crystals ~9 mm with feathery grain", settings="Crystal size (small / large / none)",
                    offer="Hot-dip galvanized (a second look of it)", source="none (3-D Voronoi)"),
    "weld": dict(n=21, label="Weld bead + heat tint (stainless)", fn=heat_tint, shapes=["weld"],
                 base=dict(color=STAINLESS, metallic=1.0, roughness=0.3), pat=dict(width=0.016, color=STAINLESS,
                                                                                    roughness=0.3),
                 size="bead Ø8 mm, ripples 1.6 mm; tint bands to 16 mm", settings="Pick two faces (the seam), Bead size, Tint width",
                 offer="Stainless (tint), steel / aluminium (bead only)",
                 source="a line kept on each part that touches it (object property) + a bead object"),
    "as_cast": dict(n=22, label="As-cast (sand-cast aluminium / iron)", fn=as_cast, shapes=["block", "bushing"],
                    base=dict(color=(0.62, 0.62, 0.62), metallic=0.9, roughness=0.62),
                    pat=dict(grain=0.0006, wave=0.03, color=(0.62, 0.62, 0.62), roughness=0.62),
                    size="sand grain ~0.5 mm, waviness ~30 mm", settings="Aluminium / Iron",
                    offer="new Metal: sand-cast aluminium; cast iron gets the grain", source="none (3-D noise)"),
    "rust": dict(n=23, label="Rust layer (flash / heavy)", fn=rust, shapes=["block", "plate"],
                 base=dict(color=STEEL, metallic=1.0, roughness=0.3), pat=dict(amount=0.35, color=STEEL, roughness=0.3),
                 size="patches 10-40 mm, flakes ~3 mm", settings="a Rust slider 0…1 per group (like Wear)",
                 offer="every bare steel / cast iron (as a slider, not a material)", source="none (3-D noise + AO)",
                 variants={"flash": dict(amount=0.25), "heavy": dict(amount=1.0)}),
    "honed": dict(n=24, label="Honed cross-hatch in a bore", fn=honed, shapes=["bushing"],
                  base=dict(color=STEEL, metallic=1.0, roughness=0.18), pat=dict(angle=50.0, k=2500.0, roughness=0.18),
                  size="scratches ~0.4 mm apart, 50° included angle", settings="Angle", offer="Steel ground / machined, cast iron",
                  source="the bore's own axis + radius (round faces, inside)"),
    "scraped": dict(n=25, label="Scraped / flaked machine ways", fn=scraped, shapes=["way", "block"],
                    base=dict(color=(0.66, 0.66, 0.67), metallic=1.0, roughness=0.2),
                    pat=dict(cell=0.012, color=(0.66, 0.66, 0.67), roughness=0.2),
                    size="half-moons in 12 mm cells, turned 90° cell to cell", settings="Cell size",
                    offer="Steel ground, cast iron (ways)", source="the part's own box axes"),
    "grip": dict(n=26, label="Rubber with a moulded grip pattern", fn=grip, shapes=["grip", "knob"],
                 base=dict(color=(0.04, 0.04, 0.042), roughness=0.7, specular=0.35, sheen=0.35), needs_color=True,
                 pat=dict(pitch=0.003, color=(0.04, 0.04, 0.042), roughness=0.7),
                 size="truncated pyramids 3 mm at 45°", settings="Pitch, colour", offer="Rubber",
                 source="the CAD face's own axis (round faces); flat faces stay plain"),
    "perlage": dict(n=27, label="Perlage / engine-turned spots (extra)", fn=perlage, shapes=["block", "cap"],
                    base=dict(color=STAINLESS, metallic=1.0, roughness=0.2), pat=dict(spacing=0.006, anisotropic=0.75,
                                                                                       roughness=0.2),
                    size="spots Ø9 mm, 6 mm apart", settings="Spot size", offer="Stainless, aluminium",
                    source="the part's own box axes"),
}


def build(mat, fid: str, variant: str = "", color=None, pattern: bool = True) -> int:
    """Build finish ``fid`` into ``mat``. ``pattern`` False: the plain base only (the cost reference). Returns the
    node count."""
    spec = FINISHES[fid]
    base = dict(spec["base"])
    pat = dict(spec["pat"])
    if variant and spec.get("variants"):
        pat.update(spec["variants"][variant])
        if "roughness" in spec["variants"][variant]:
            base["roughness"] = spec["variants"][variant]["roughness"]
    if color is not None:
        base["color"] = color
        if "color" in pat:
            pat["color"] = color
    pat.setdefault("color", base["color"])
    pat.setdefault("roughness", base["roughness"])
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    b = F(nt)
    out = b.node("ShaderNodeOutputMaterial", 700, 0)
    bsdf = b.node("ShaderNodeBsdfPrincipled", 400, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    vals = {"Base Color": (*lin(base["color"]), 1.0), "Metallic": base.get("metallic", 0.0),
            "Roughness": base["roughness"], "Specular IOR Level": base.get("specular", 0.5),
            "Coat Weight": base.get("coat", 0.0), "Coat Roughness": base.get("coat_roughness", 0.03),
            "Sheen Weight": base.get("sheen", 0.0), "Sheen Roughness": base.get("sheen_roughness", 0.5)}
    got = spec["fn"](b, pat) if pattern else {}
    keymap = {"color": "Base Color", "metallic": "Metallic", "roughness": "Roughness", "alpha": "Alpha",
              "anisotropic": "Anisotropic"}
    for k, v in got.items():
        if k in keymap:
            vals[keymap[k]] = v
    for name, v in vals.items():
        b.put(bsdf.inputs[name], v)
    if got.get("normal") is not None:
        nt.links.new(got["normal"], bsdf.inputs["Normal"])
        if base.get("coat") and fid != "carbon":          # carbon: the clear coat stays smooth over the tows
            nt.links.new(got["normal"], bsdf.inputs["Coat Normal"])
    if got.get("tangent") is not None:
        nt.links.new(got["tangent"], bsdf.inputs["Tangent"])
    if spec.get("see_through") and pattern:
        mat.surface_render_method = "DITHERED"
    mat["fr_finish"] = fid
    return len(nt.nodes)
