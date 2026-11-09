"""Build Blender materials from the material library.

One Blender material per material group ("FR <group>"). Switching a paint
scheme or changing a group's look rebuilds that material's nodes, so every
part in the group updates at once.
"""

from __future__ import annotations

import bpy

from ..core import materials_lib, ral

PREFIX = "FR "


def material_name(group: str) -> str:
    return PREFIX + group


def color_to_linear(color_text: str, fallback=(0.8, 0.8, 0.8)):
    parsed = ral.parse_colour(color_text) if color_text else None
    srgb = parsed[1] if parsed else fallback
    return tuple(ral.srgb_to_linear(c) for c in srgb), srgb


def _set(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        try:
            sock.default_value = value
        except (TypeError, ValueError):
            pass


# Raise when the node trees change: materials built by an older version are rebuilt (also on load), keeping
# every group's material, colour and wear. 1 = up to 0.2.38, 2 = task 0046 (marks, peel, sheen, wear).
LOOK_VERSION = 2
PROP_LOOK = "fr_look_version"
# a part's own axes, stored on its mesh (every copy shares it): read by the shader's machining marks
AX_LONG, AX_ROUND, AX_CENTRE, AX_COUNT = "fr_ax_long", "fr_ax_round", "fr_ax_centre", "fr_ax_n"


def part_axes(me) -> None:
    """Store the part's longest side, its round axis and the centre of its box on the mesh.

    Longest side: the box side that is longest. Round axis: the box axis whose two other sides are most
    alike (a shaft, a disc, a bolt), the longest side when nothing is round. Units: object space."""
    import numpy as np
    n = len(me.vertices)
    if n == 0:
        lo = hi = np.zeros(3)
    else:
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(0), co.max(0)
    ext = np.maximum(hi - lo, 1e-9)
    long_k = int(np.argmax(ext))
    ratios = []
    for k in range(3):
        i, j = [a for a in range(3) if a != k]
        ratios.append(min(ext[i], ext[j]) / max(ext[i], ext[j]))
    round_k = int(np.argmax(ratios))
    if ratios[long_k] >= ratios[round_k] - 0.02 or ratios[round_k] < 0.9:   # a shaft, or nothing round
        round_k = long_k
    me[AX_LONG] = [float(k == long_k) for k in range(3)]
    me[AX_ROUND] = [float(k == round_k) for k in range(3)]
    me[AX_CENTRE] = [float(v) for v in (lo + hi) / 2]
    me[AX_COUNT] = n


def ensure_axes(me) -> None:
    if me is not None and me.get(AX_COUNT) != len(me.vertices):
        part_axes(me)


class _Nodes:
    """Small helpers to wire a node tree."""

    def __init__(self, nt):
        self.nt = nt
        self._coord = None
        self._attrs = {}

    def node(self, kind, x=0.0, y=0.0, **inputs):
        n = self.nt.nodes.new(kind)
        n.location = (x, y)
        for k, v in inputs.items():
            self.put(n.inputs[k.replace("_", " ")], v)
        return n

    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            try:
                sock.default_value = v
            except (TypeError, ValueError):
                pass

    def coord(self, name="Object"):
        if self._coord is None:
            self._coord = self.node("ShaderNodeTexCoord", -1900, 0)
        return self._coord.outputs[name]

    def attr(self, name):
        if name not in self._attrs:
            a = self.node("ShaderNodeAttribute", -1900, -300 - 150 * len(self._attrs))
            a.attribute_type = "OBJECT"
            a.attribute_name = name
            self._attrs[name] = a
        return self._attrs[name].outputs["Vector"]

    def vmath(self, op, a, b=None, scale=None, x=0.0, y=0.0):
        n = self.node("ShaderNodeVectorMath", x, y)
        n.operation = op
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs["Scale"], scale)
        return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]

    def math(self, op, a, b=None, x=0.0, y=0.0, clamp=False):
        n = self.node("ShaderNodeMath", x, y)
        n.operation = op
        n.use_clamp = clamp
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return n.outputs[0]

    def map(self, v, a, b, c, d, x=0.0, y=0.0):
        n = self.node("ShaderNodeMapRange", x, y, From_Min=a, From_Max=b, To_Min=c, To_Max=d)
        self.put(n.inputs["Value"], v)
        return n.outputs["Result"]

    def mix(self, kind, fac, a, b, x=0.0, y=0.0):
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = kind
        n.clamp_factor = True
        if kind == "RGBA":
            self.put(n.inputs[0], fac)
            self.put(n.inputs[6], a)
            self.put(n.inputs[7], b)
            return n.outputs[2]
        self.put(n.inputs[0], fac)
        self.put(n.inputs[2], a)
        self.put(n.inputs[3], b)
        return n.outputs[0]

    def noise(self, vector=None, scale=1.0, detail=2.0, w=None, x=0.0, y=0.0):
        n = self.node("ShaderNodeTexNoise", x, y)
        if w is not None:
            n.noise_dimensions = "1D"
            self.put(n.inputs["W"], w)
        else:
            self.put(n.inputs["Vector"], vector if vector is not None else self.coord())
        self.put(n.inputs["Scale"], scale)
        self.put(n.inputs["Detail"], detail)
        return n.outputs["Fac"]


def _marks(b: _Nodes, m: dict):
    """Machining marks: (a 0..1 pattern, the tangent the anisotropy follows, or None)."""
    kind = m.get("kind", "ground")
    k = float(m.get("scale", 4000.0))
    p = b.coord()
    y = 600
    if kind in ("ground", "brushed"):
        a = b.attr(AX_LONG)
        d = b.vmath("DOT_PRODUCT", p, a, x=-1700, y=y)
        ad = b.vmath("SCALE", a, scale=d, x=-1550, y=y)
        along = float(m.get("along", 10.0))
        q = b.vmath("SUBTRACT", b.vmath("SCALE", p, scale=k, x=-1400, y=y + 100),
                    b.vmath("SCALE", ad, scale=k - along, x=-1400, y=y - 100), x=-1250, y=y)
        fac = b.noise(q, 1.0, 2.0, x=-1100, y=y)
        tangent = b.attr(AX_LONG)
    elif kind == "turned":
        ax, c = b.attr(AX_ROUND), b.attr(AX_CENTRE)
        pc = b.vmath("SUBTRACT", p, c, x=-1700, y=y)
        d = b.vmath("DOT_PRODUCT", pc, ax, x=-1550, y=y + 100)
        r = b.vmath("LENGTH", b.vmath("SUBTRACT", pc, b.vmath("SCALE", ax, scale=d, x=-1550, y=y - 100),
                                      x=-1400, y=y - 100), x=-1250, y=y - 100)
        # one number that runs along the axis on the round side and outwards on the end faces: rings on both
        w = b.math("MULTIPLY", b.math("ADD", d, r, x=-1100, y=y), k, x=-950, y=y)
        fac = b.noise(w=w, scale=1.0, detail=2.0, x=-800, y=y)
        tangent = b.vmath("CROSS_PRODUCT", ax, pc, x=-1250, y=y + 200)        # round the axis
    else:                                                                         # milled: face-mill arcs
        cell = 0.06
        vor = b.node("ShaderNodeTexVoronoi", -1700, y)
        b.put(vor.inputs["Vector"], p)
        b.put(vor.inputs["Scale"], 1.0 / cell)
        b.put(vor.inputs["Randomness"], 0.8)
        w = b.math("MULTIPLY", vor.outputs["Distance"], cell * k, x=-1500, y=y)
        fac = b.noise(w=w, scale=1.0, detail=1.0, x=-1300, y=y)
        tangent = None
    if tangent is not None:
        vt = b.node("ShaderNodeVectorTransform", -650, y + 200)
        vt.vector_type = "VECTOR"
        vt.convert_from, vt.convert_to = "OBJECT", "WORLD"
        b.put(vt.inputs[0], tangent)
        tangent = b.vmath("NORMALIZE", vt.outputs[0], x=-500, y=y + 200)
    return fac, tangent


def _wear(b: _Nodes, wear: float, spec: dict, color, metallic, rough):
    """Edge wear and corner dirt (Cycles: bevel + ambient occlusion; EEVEE shows the dirt only).
    Returns (colour, metallic, roughness) sockets or values."""
    y = -900
    bev = b.node("ShaderNodeBevel", -1700, y, Radius=0.0015 + 0.005 * wear)   # wider with more wear
    bev.samples = 4
    geo = b.node("ShaderNodeNewGeometry", -1700, y - 250)
    edge = b.math("SUBTRACT", 1.0, b.vmath("DOT_PRODUCT", bev.outputs["Normal"], geo.outputs["Normal"],
                                         x=-1500, y=y), x=-1350, y=y)
    edge = b.map(edge, 0.004, 0.06, 0.0, 1.0, x=-1200, y=y)
    brk = b.noise(None, 120.0, 4.0, x=-1350, y=y - 250)      # worn in places, not a drawn outline
    brk = b.map(brk, 0.62 - 0.2 * wear, 0.72 - 0.15 * wear, 0.0, 1.0, x=-1200, y=y - 250)
    edge = b.math("MULTIPLY", b.math("MULTIPLY", edge, brk, x=-1050, y=y), min(1.0, wear * 1.6), x=-900, y=y,
                  clamp=True)
    if spec.get("category") in ("Plastic & rubber", "Glass", "Light", "Other"):
        edge = 0.0                                           # no bare metal under rubber or plastic
    ao = b.node("ShaderNodeAmbientOcclusion", -1700, y - 500, Distance=0.03)
    ao.samples = 8
    ao.only_local = True
    dirt = b.math("MULTIPLY", b.map(ao.outputs["AO"], 0.35, 0.95, 1.0, 0.0, x=-1500, y=y - 500), wear * 0.7,
                  x=-1350, y=y - 500, clamp=True)
    painted = spec.get("metallic", 0.0) < 0.5
    if painted:          # paint wears through to bare steel
        bare, bare_rough, bare_metal = (0.42, 0.42, 0.43, 1.0), 0.32, 1.0
    else:                # metal edges get polished brighter
        bare, bare_rough, bare_metal = (0.85, 0.85, 0.86, 1.0), 0.15, spec.get("metallic", 1.0)
    color = b.mix("RGBA", edge, color, bare, x=-700, y=y)
    color = b.mix("RGBA", dirt, color, (0.045, 0.04, 0.035, 1.0), x=-550, y=y)
    metallic = b.mix("FLOAT", edge, metallic, bare_metal, x=-700, y=y - 250)
    metallic = b.mix("FLOAT", dirt, metallic, 0.0, x=-550, y=y - 250)
    rough = b.mix("FLOAT", edge, rough, bare_rough, x=-700, y=y - 400)
    rough = b.mix("FLOAT", dirt, rough, 0.85, x=-550, y=y - 400)
    return color, metallic, rough


def _bump(b: _Nodes, height, strength: float, distance: float, normal, x: float, y: float):
    n = b.node("ShaderNodeBump", x, y, Strength=strength, Distance=distance)
    b.put(n.inputs["Height"], height)
    if normal is not None:
        b.put(n.inputs["Normal"], normal)
    return n.outputs["Normal"]


def _eevee_glass(b: _Nodes, out, spec: dict, lin) -> None:
    """EEVEE shows refraction only with screen-space ray tracing, so glass there came out dark grey. EEVEE
    gets its own output instead: see-through (tinted) plus reflections that grow towards grazing angles,
    as thin glass looks; Cycles keeps the real glass."""
    out.target = "CYCLES"
    rough = float(spec.get("roughness", 0.0))
    eo = b.node("ShaderNodeOutputMaterial", 600, -1300)
    eo.target = "EEVEE"
    lw = b.node("ShaderNodeLayerWeight", -300, -1250, Blend=0.12)
    fac = b.math("ADD", lw.outputs["Fresnel"], 0.04, x=-100, y=-1250, clamp=True)
    clear = b.node("ShaderNodeBsdfTransparent", -300, -1450, Color=(*lin, 1.0))
    see = clear.outputs[0]
    if rough > 0.2:          # frosted: part of the light is scattered
        diff = b.node("ShaderNodeBsdfDiffuse", -300, -1600, Color=(*lin, 1.0))
        m = b.node("ShaderNodeMixShader", -100, -1500, Fac=0.45)
        b.put(m.inputs[1], see)
        b.put(m.inputs[2], diff.outputs[0])
        see = m.outputs[0]
    gloss = b.node("ShaderNodeBsdfGlossy", -300, -1750, Roughness=rough, Color=(1.0, 1.0, 1.0, 1.0))
    mix = b.node("ShaderNodeMixShader", 250, -1300)
    b.put(mix.inputs[0], fac)
    b.put(mix.inputs[1], see)
    b.put(mix.inputs[2], gloss.outputs[0])
    b.put(eo.inputs["Surface"], mix.outputs[0])


def build_nodes(mat: bpy.types.Material, material_id: str, color_text: str = "", wear: float = 0.0) -> None:
    spec = materials_lib.get(material_id)
    if spec.get("needs_color"):
        lin, srgb = color_to_linear(color_text or materials_lib.DEFAULT_COLOR)
    else:
        srgb = spec.get("base_color", (0.8, 0.8, 0.8))
        lin = tuple(ral.srgb_to_linear(c) for c in srgb)

    nt = mat.node_tree
    nt.nodes.clear()
    b = _Nodes(nt)
    out = b.node("ShaderNodeOutputMaterial", 600, 0)
    bsdf = b.node("ShaderNodeBsdfPrincipled", 250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    _set(bsdf, "Specular IOR Level", spec.get("specular", 0.5))
    if spec.get("coat"):
        _set(bsdf, "Coat Weight", spec["coat"])
        _set(bsdf, "Coat Roughness", spec.get("coat_roughness", 0.1))
    if spec.get("transmission"):
        _set(bsdf, "Transmission Weight", spec["transmission"])
        _set(bsdf, "IOR", spec.get("ior", 1.5))
    if spec.get("anisotropic"):
        _set(bsdf, "Anisotropic", spec["anisotropic"])
    if spec.get("sheen"):
        _set(bsdf, "Sheen Weight", spec["sheen"])
        _set(bsdf, "Sheen Roughness", spec.get("sheen_roughness", 0.5))
    if spec.get("emission"):
        _set(bsdf, "Emission Color", (*lin, 1.0))
        _set(bsdf, "Emission Strength", spec.get("emission_strength", 5.0))

    color = (*lin, 1.0)
    metallic = float(spec.get("metallic", 0.0))
    rough = float(spec.get("roughness", 0.4))
    normal = None

    var = spec.get("variation")
    if var:
        fac = b.noise(None, var.get("scale", 20.0), 4.0, x=-500, y=150)
        rough = b.map(fac, 0.0, 1.0, var.get("roughness_min", 0.3), var.get("roughness_max", 0.5), x=-250, y=0)
        amount = var.get("color_amount", 0.0)
        if amount:
            f = b.map(fac, 0.0, 1.0, 0.0, amount * 2, x=-450, y=350)
            mix = b.node("ShaderNodeMix", -250, 250)
            mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
            b.put(mix.inputs["Factor"], f)
            mix.inputs["A"].default_value = (*lin, 1.0)
            mix.inputs["B"].default_value = (0.55, 0.55, 0.56, 1.0)
            color = mix.outputs["Result"]

    marks = spec.get("marks")
    if marks:
        fac, tangent = _marks(b, marks)
        amt = float(marks.get("rough", 0.05))
        base_r = rough
        mr = b.map(fac, 0.3, 0.7, -amt, amt, x=-500, y=600)
        rough = b.math("ADD", base_r, mr, x=-300, y=600, clamp=True)
        if marks.get("bump"):
            normal = _bump(b, fac, float(marks["bump"]), 0.0002, normal, -100, -500)
        if tangent is not None and spec.get("anisotropic"):
            nt.links.new(tangent, bsdf.inputs["Tangent"])

    bump = spec.get("bump")
    if bump:
        h = b.noise(None, bump.get("scale", 500.0), 3.0, x=-500, y=-250)
        normal = _bump(b, h, bump.get("strength", 0.05), 0.0005, normal, 0, -250)

    peel = spec.get("peel")
    if peel:        # orange peel: soft, wide waves in the sprayed paint, seen in the reflections
        h = b.noise(None, peel.get("scale", 600.0), 1.0, x=-500, y=-700)
        pn = _bump(b, h, peel.get("strength", 0.04), 0.0003, None, 0, -700)
        if spec.get("coat"):
            nt.links.new(pn, bsdf.inputs["Coat Normal"])
        normal = pn if normal is None else normal

    if wear > 0.0 and not spec.get("transmission") and not spec.get("emission"):
        color, metallic, rough = _wear(b, float(wear), spec, color, metallic, rough)

    b.put(bsdf.inputs["Base Color"], color)
    b.put(bsdf.inputs["Metallic"], metallic)
    b.put(bsdf.inputs["Roughness"], rough)
    if normal is not None:
        nt.links.new(normal, bsdf.inputs["Normal"])

    grid = spec.get("grid")
    if grid:
        _grid_holes(nt, bsdf, grid)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"

    # viewport (solid mode) look
    mat.diffuse_color = (*lin, 1.0)
    mat.metallic = float(spec.get("metallic", 0.0))
    mat.roughness = float(spec.get("roughness", 0.4))
    if spec.get("transmission"):
        mat.diffuse_color = (*lin, 0.35)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        _eevee_glass(b, out, spec, lin)
    mat["fr_material"] = material_id
    mat["fr_color"] = color_text
    mat["fr_wear"] = float(wear)
    mat[PROP_LOOK] = LOOK_VERSION


def _math(nt, op: str, a, b=None, x: float = 0.0, y: float = 0.0):
    """A Math node; ``a``/``b`` are sockets or numbers."""
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    node.location = (x, y)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            node.inputs[i].default_value = v
        else:
            nt.links.new(v, node.inputs[i])
    return node.outputs[0]


def _grid_holes(nt, bsdf, grid: dict) -> None:
    """Holes of a wire mesh in a plate: Alpha = 1 on the wires, 0 in between.

    The wires run along the two object axes that lie in the face (picked from the face normal),
    every ``spacing`` metres, ``wire`` thick; object coordinates, so every copy looks the same."""
    spacing, wire = grid.get("spacing", 0.025), grid.get("wire", 0.003)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-1600, -500)
    pos = nt.nodes.new("ShaderNodeSeparateXYZ")
    pos.location = (-1400, -450)
    nt.links.new(coord.outputs["Object"], pos.inputs[0])
    nrm = nt.nodes.new("ShaderNodeSeparateXYZ")
    nrm.location = (-1400, -750)
    nt.links.new(coord.outputs["Normal"], nrm.inputs[0])
    near, along = [], []
    for k in range(3):
        y = -400 - 120 * k
        wrapped = nt.nodes.new("ShaderNodeMath")
        wrapped.operation = "WRAP"
        wrapped.location = (-1200, y)
        nt.links.new(pos.outputs[k], wrapped.inputs[0])
        wrapped.inputs[1].default_value = spacing
        wrapped.inputs[2].default_value = 0.0
        near.append(_math(nt, "LESS_THAN", wrapped.outputs[0], wire, -1000, y))        # on a wire of this axis
        absn = _math(nt, "ABSOLUTE", nrm.outputs[k], None, -1200, y - 400)
        along.append(_math(nt, "GREATER_THAN", absn, 0.577, -1000, y - 400))         # the face looks along it
    total = None
    for k in range(3):
        i, j = [a for a in range(3) if a != k]
        either = _math(nt, "MAXIMUM", near[i], near[j], -800, -400 - 120 * k)
        term = _math(nt, "MULTIPLY", along[k], either, -600, -400 - 120 * k)
        total = term if total is None else _math(nt, "ADD", total, term, -400, -400 - 120 * k)
    alpha = _math(nt, "MINIMUM", total, 1.0, -200, -500)
    nt.links.new(alpha, bsdf.inputs["Alpha"])


def is_current(mat, material_id: str, color_text: str = "", wear: float = 0.0) -> bool:
    """The material already shows this look, built by this version."""
    return (mat.get("fr_material") == material_id and mat.get("fr_color") == color_text
            and abs(float(mat.get("fr_wear", 0.0)) - float(wear)) < 1e-4
            and int(mat.get(PROP_LOOK, 1)) >= LOOK_VERSION
            and mat.node_tree is not None and bool(mat.node_tree.nodes))


def ensure_material(group: str, material_id: str, color_text: str = "", wear: float = 0.0) -> bpy.types.Material:
    name = material_name(group)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        try:
            mat.use_nodes = True
        except Exception:
            pass
    if mat.node_tree is None:
        mat.use_nodes = True
    if not is_current(mat, material_id, color_text, wear):
        build_nodes(mat, material_id, color_text, wear)
    return mat


def assign(ob: bpy.types.Object, mat: bpy.types.Material) -> None:
    if ob.type != "MESH" or ob.data is None:
        return
    ensure_axes(ob.data)
    if not ob.material_slots:
        ob.data.materials.append(None)
    slot = ob.material_slots[0]
    if slot.link != "OBJECT":
        slot.link = "OBJECT"
    if slot.material is not mat:
        slot.material = mat


def preview_rgb(material_id: str, color_text: str = ""):
    """sRGB colour for UI swatches."""
    spec = materials_lib.get(material_id)
    if spec.get("needs_color"):
        return color_to_linear(color_text or materials_lib.DEFAULT_COLOR)[1]
    return spec.get("base_color", (0.8, 0.8, 0.8))
