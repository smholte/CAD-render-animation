"""Tool marks on cut faces (task 0061): the node group "FR tool marks" in the cut-face material.

The milled mesh carries four per-face attributes (``core/toolmarks.py``: which move made the face, with which tool).
The group reads them and gives the material the marks of that move: ridges (the normal leans over each mark, worked
out exactly – no Bump node, which turns to noise when the marks are finer than a pixel), a small change of the
roughness, and the sheen across the grooves (anisotropy). Shader nodes only: no drivers, no scripts, no pictures, so
it works with "Auto Run Python Scripts" off, in Cycles and EEVEE, and in the render queue.

Where a face has no move (kind 0) the group passes the material's own look through unchanged.

**Which way the sheen goes (measured, Blender 5.2.3, Cycles; a flat metal plane, a small light above it,
Anisotropic 0.8):** with the Tangent along X the highlight was 16.2 px wide along X and 6.0 px along Y, with the
Tangent along Y the other way round. Blender stretches the highlight *along* the tangent. A milled or brushed face
stretches it *across* its grooves (the tiny grooves scatter the light sideways), so the group feeds the direction
across the grooves as the tangent. On a face-milled top that gives the swirl: the bright streak follows the arcs'
centres as the light moves.

``core/toolmarks.py`` has the same formula in plain Python (``pattern``, ``shade``); ``tests/test_toolmarks.py``
compares a render with it.
"""

from __future__ import annotations

import bpy

from ..core import toolmarks as core

GROUP = "FR tool marks"
#: raise when the nodes inside the group change: an older group is built again in place (materials keep their link)
GROUP_VERSION = 2
PROP_VERSION = "fr_toolmarks_version"
#: the name of the group's node in a material
NODE = "FR tool marks"

# (name, socket type, default, min, max)
_F, _V = "NodeSocketFloat", "NodeSocketVector"
INPUTS = (
    ("Size", _F, 1.0, 0.01, 100.0),              # Mark size: 1 = the real spacing … 10
    ("Strength", _F, 1.0, 0.0, 10.0),            # 0 … 2, 1 = normal
    ("Roughness", _F, 0.2, 0.0, 1.0),            # the material's own (with its own marks): kept where no move is known
    ("Marks roughness", _F, 0.2, 0.0, 1.0),      # the plain roughness the tool marks start from
    ("Normal", _V, None, None, None),            # the material's own normal: kept where no move is known
    ("Tangent", _V, None, None, None),           # … and its own tangent
    ("Anisotropic", _F, 0.0, 0.0, 1.0),          # … and its own anisotropy
    ("Ridge tilt", _F, 0.05, 0.0, 1.0),          # the four numbers of core.toolmarks.look()
    ("Rough change", _F, 0.03, 0.0, 1.0),
    ("Sheen", _F, 0.4, 0.0, 1.0),
    ("Hatch", _F, 0.25, 0.0, 1.0),
    ("Pixel angle", _F, core.PIXEL_ANGLE, 1e-6, 0.1),      # the ridges fade below about two of these per mark
)
OUTPUTS = (
    ("Has marks", _F),       # 1 where the face has a move (kind > 0.5), else 0
    ("Ridge", _F),           # 0 … 1 across one mark (core.toolmarks.profile), 0 without marks; never faded
    ("Roughness", _F),
    ("Normal", _V),          # world space
    ("Tangent", _V),         # world space, unit: across the grooves
    ("Anisotropic", _F),
    ("Fade", _F),            # how much of the ridges shows at this distance (core.toolmarks.fade)
)
#: look() key -> input
LOOK_INPUTS = {"ridge": "Ridge tilt", "rough": "Rough change", "anisotropic": "Sheen", "hatch": "Hatch"}


def _interface(nt) -> None:
    """Add the sockets that are missing (never remove one: the materials' links hang on them)."""
    have = {(it.in_out, it.name) for it in nt.interface.items_tree if it.item_type == "SOCKET"}
    for name, kind in OUTPUTS:
        if ("OUTPUT", name) not in have:
            nt.interface.new_socket(name=name, in_out="OUTPUT", socket_type=kind)
    for name, kind, default, lo, hi in INPUTS:
        if ("INPUT", name) in have:
            continue
        s = nt.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
        if kind == _F:
            s.default_value, s.min_value, s.max_value = default, lo, hi
        else:
            s.hide_value = True


def _build(nt) -> None:
    """The nodes inside the group. Names follow the table at the top of core/toolmarks.py."""
    from .materials import _Nodes
    nt.nodes.clear()
    b = _Nodes(nt)
    m, v = b.math, b.vmath
    gi = b.node("NodeGroupInput", -2600, 400).outputs
    go = b.node("NodeGroupOutput", 1800, 0).inputs

    def attribute(name, y):
        n = b.node("ShaderNodeAttribute", -2600, y)
        n.attribute_type = "GEOMETRY"
        n.attribute_name = name
        return n.outputs["Vector"]

    def transform(vec, kind, src, dst, x, y):
        n = b.node("ShaderNodeVectorTransform", x, y)
        n.vector_type, n.convert_from, n.convert_to = kind, src, dst
        b.put(n.inputs[0], vec)
        return n.outputs[0]

    def dot(p, q, x, y):
        return v("DOT_PRODUCT", p, q, x=x, y=y)

    def scaled(vec, s, x, y):
        return v("SCALE", vec, scale=s, x=x, y=y)

    def pick(fac, p, q, x, y):                        # a vector: p where fac is 0, q where it is 1
        n = b.node("ShaderNodeMix", x, y)
        n.data_type, n.clamp_factor = "VECTOR", True
        b.put(n.inputs[0], fac)
        b.put(n.inputs[4], p)
        b.put(n.inputs[5], q)
        return n.outputs[1]

    def in_face(vec, x, y):                           # vec without its part along the normal
        return v("SUBTRACT", vec, scaled(N, dot(vec, N, x, y), x + 150, y), x=x + 300, y=y)

    def tilt_of(u, x, y):                             # (tilt, ridge) of core.toolmarks.profile
        f = m("FRACT", m("DIVIDE", u, period, x=x, y=y), x=x + 150, y=y)
        t = m("SUBTRACT", 1.0, m("MULTIPLY", f, 2.0, x=x + 300, y=y), x=x + 450, y=y)
        return t, m("MULTIPLY", t, t, x=x + 600, y=y)

    # ---- what the face knows, and where we are on it (the milled mesh's own space, metres) -----------------
    o, d, a, p = (attribute(name, -200 * i) for i, name in enumerate(core.ATTRS))
    sep = b.node("ShaderNodeSeparateXYZ", -2400, -600)
    b.put(sep.inputs[0], p)
    kind, R, spacing = sep.outputs
    q = v("SUBTRACT", b.node("ShaderNodeTexCoord", -2600, 200).outputs["Object"], o, x=-2400, y=200)
    w = v("CROSS_PRODUCT", a, d, x=-2400, y=-200)
    along, side, qa = dot(q, d, -2200, 300), dot(q, w, -2200, 100), dot(q, a, -2200, -100)
    root = m("SQRT", m("MAXIMUM", m("SUBTRACT", m("MULTIPLY", R, R, x=-2200, y=-500),
                                    m("MULTIPLY", side, side, x=-2200, y=-650), x=-2050, y=-550), 0.0,
                       x=-1900, y=-550), x=-1750, y=-550)
    radial = v("SUBTRACT", q, scaled(a, qa, -2050, -100), x=-1900, y=-100)
    geo = b.node("ShaderNodeNewGeometry", -2600, 900)
    N = v("NORMALIZE", transform(geo.outputs["Normal"], "NORMAL", "WORLD", "OBJECT", -2400, 900), x=-2200, y=900)

    def is_kind(k, y):
        n = b.node("ShaderNodeMath", -2200, y)
        n.operation = "COMPARE"
        b.put(n.inputs[0], kind)
        n.inputs[1].default_value, n.inputs[2].default_value = float(k), 0.25
        return n.outputs[0]

    k1, k2, k3, k4, k5, k6 = (is_kind(k, -900 - 160 * k) for k in (core.ARCS, core.FLANK, core.ALONG, core.RINGS,
                                                                    core.RINGS_WALL, core.ACROSS))
    has = m("GREATER_THAN", kind, 0.5, x=-2200, y=-800)
    k_feed = m("ADD", k2, k6, x=-2000, y=-1300)                    # the kinds that count along the feed
    k_axis = m("ADD", k3, k5, x=-2000, y=-1500)                    # … and along the tool's axis

    # ---- u, the number the ridges count, and the direction it grows in ------------------------------------
    u = m("ADD", m("ADD", m("MULTIPLY", m("ADD", k_feed, k1, x=-1800, y=-1300), along, x=-1650, y=-1300),
                   m("MULTIPLY", k_axis, qa, x=-1650, y=-1450), x=-1500, y=-1350),
          m("SUBTRACT", m("MULTIPLY", k4, v("LENGTH", radial, x=-1750, y=-200), x=-1650, y=-1600),
            m("MULTIPLY", k1, root, x=-1650, y=-1750), x=-1500, y=-1650), x=-1350, y=-1450)
    grow = v("ADD", v("ADD", scaled(d, m("ADD", k_feed, m("MULTIPLY", k1, root, x=-1650, y=-1900), x=-1500, y=-1900),
                                    -1350, -1900),
                      scaled(w, m("MULTIPLY", k1, side, x=-1500, y=-2050), -1350, -2050), x=-1200, y=-1950),
             v("ADD", scaled(a, k_axis, -1350, -2200), scaled(radial, k4, -1350, -2350), x=-1200, y=-2250),
             x=-1050, y=-2050)
    E = in_face(v("NORMALIZE", grow, x=-900, y=-2050), -750, -2050)
    # it stands on the face (a ball pass on a face that looks along the feed): the grooves run along the axis
    lost = m("LESS_THAN", dot(E, E, -300, -2050), core.TINY * core.TINY, x=-150, y=-2050)
    e = v("NORMALIZE", pick(lost, E, v("CROSS_PRODUCT", a, N, x=-300, y=-2250), 0, -2050),
          x=150, y=-2050)
    known = m("GREATER_THAN", dot(e, e, 300, -2200), 0.5, x=450, y=-2200)

    # ---- one mark: the surface is a shallow scallop, so its normal leans from +1 to -1 across it -----------
    period = m("MULTIPLY", m("MAXIMUM", spacing, core.SPACING_MIN, x=-2200, y=-2500), gi["Size"], x=-2050, y=-2500)
    t1, ridge = tilt_of(u, -1200, -1450)
    # the back of the tool leaves arcs the other way round on a floor: a faint cross-hatch
    grow2 = v("SUBTRACT", scaled(d, root, -1350, -2700), scaled(w, side, -1350, -2850), x=-1200, y=-2750)
    e2 = v("NORMALIZE", in_face(v("NORMALIZE", grow2, x=-1050, y=-2750), -900, -2750), x=-450, y=-2750)
    t2, ridge2 = tilt_of(m("ADD", along, root, x=-1350, y=-3000), -1200, -3000)
    h = m("MULTIPLY", gi["Hatch"], k1, x=-450, y=-3000)
    # a wall: weaker lines (core.FLANK_TILT), and the line where two depths meet (core.step_line): on a wall the
    # second number of fr_mk_p is the step-down, a line lies at every multiple of it above the tip
    t1 = m("MULTIPLY", t1, m("SUBTRACT", 1.0, m("MULTIPLY", k2, 1.0 - core.FLANK_TILT, x=-600, y=-3300),
                             x=-450, y=-3300), x=-300, y=-3300)
    g = m("DIVIDE", qa, m("MAXIMUM", R, 1e-9, x=-1350, y=-3500), x=-1200, y=-3500)
    near = m("MULTIPLY", m("ABSOLUTE", m("SUBTRACT", m("FRACT", m("ADD", g, 0.5, x=-1050, y=-3500), x=-900, y=-3500),
                                         0.5, x=-750, y=-3500), x=-600, y=-3500), R, x=-450, y=-3500)
    line = m("SUBTRACT", 1.0, m("DIVIDE", near, m("MULTIPLY", gi["Size"], 0.5 * core.STEP_WIDTH, x=-600, y=-3650),
                                x=-300, y=-3500), x=-150, y=-3500, clamp=True)
    stepped = m("MULTIPLY", m("MULTIPLY", k2, m("GREATER_THAN", R, 1e-6, x=-1200, y=-3700), x=-1050, y=-3700),
                m("GREATER_THAN", g, 0.5, x=-1050, y=-3850), x=-900, y=-3700)
    step = m("MULTIPLY", m("MULTIPLY", line, stepped, x=0, y=-3500), core.STEP_TILT, x=150, y=-3500)
    lean = v("ADD", v("ADD", scaled(e, t1, 300, -1900),
                      scaled(e2, m("MULTIPLY", h, t2, x=-300, y=-3000), -150, -2850), x=450, y=-1900),
             scaled(in_face(a, 300, -3500), step, 750, -3500), x=900, y=-1900)
    wave = m("ADD", m("SUBTRACT", ridge, core.RIDGE_MEAN, x=-300, y=-1450),
             m("MULTIPLY", h, m("SUBTRACT", ridge2, core.RIDGE_MEAN, x=-450, y=-3150), x=-300, y=-3150),
             x=-150, y=-1450)

    # ---- the ridges fade when a mark gets smaller than about two pixels (core.toolmarks.PIXEL_ANGLE) -------
    e_world = transform(e, "VECTOR", "OBJECT", "WORLD", 300, -2400)          # its length = the object's scale
    cam = b.node("ShaderNodeCameraData", -300, -3400)
    pixels = m("DIVIDE", m("MULTIPLY", period, v("LENGTH", e_world, x=450, y=-2500), x=600, y=-2500),
               m("MULTIPLY", cam.outputs["View Distance"], gi["Pixel angle"], x=450, y=-3400), x=750, y=-2500)
    mr = b.node("ShaderNodeMapRange", 900, -2500, From_Min=core.FADE_FROM, From_Max=core.FADE_TO, To_Min=0.0,
                To_Max=1.0)
    mr.interpolation_type = "SMOOTHSTEP"
    b.put(mr.inputs["Value"], pixels)
    fade = mr.outputs["Result"]
    amount = m("MULTIPLY", m("MULTIPLY", gi["Strength"], fade, x=1050, y=-2400), known, x=1200, y=-2400)

    # ---- what the material gets ----------------------------------------------------------------------------
    leaning = v("ADD", N, scaled(lean, m("MULTIPLY", amount, gi["Ridge tilt"], x=1050, y=-1900), 1200, -1900),
                x=1350, y=-1900)
    normal = v("NORMALIZE", transform(leaning, "NORMAL", "OBJECT", "WORLD", 1350, -1700), x=1500, y=-1700)
    rough = m("ADD", gi["Marks roughness"],
              m("MULTIPLY", m("MULTIPLY", gi["Rough change"], amount, x=1050, y=-1300), wave, x=1200, y=-1300),
              x=1350, y=-1300, clamp=True)
    sheen = m("MULTIPLY", m("MULTIPLY", gi["Sheen"], gi["Strength"], x=1050, y=-900, clamp=True), known,
              x=1200, y=-900)
    b.put(go["Has marks"], has)
    b.put(go["Ridge"], m("MULTIPLY", ridge, has, x=1500, y=300))
    b.put(go["Roughness"], b.mix("FLOAT", has, gi["Roughness"], rough, x=1500, y=100))
    b.put(go["Normal"], pick(has, gi["Normal"], normal, 1500, -100))
    b.put(go["Tangent"], pick(has, gi["Tangent"], v("NORMALIZE", e_world, x=1350, y=-500), 1500, -300))
    b.put(go["Anisotropic"], b.mix("FLOAT", has, gi["Anisotropic"], sheen, x=1500, y=-500))
    b.put(go["Fade"], fade)


def ensure_group() -> bpy.types.NodeTree:
    """The node group "FR tool marks": made once, built again in place when it comes from an older version."""
    nt = bpy.data.node_groups.get(GROUP)
    if nt is not None and nt.bl_idname != "ShaderNodeTree":         # somebody else's group of that name
        nt.name = GROUP + " (other)"
        nt = None
    if nt is None:
        nt = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
    if int(nt.get(PROP_VERSION, 0)) < GROUP_VERSION or not nt.nodes:
        _interface(nt)
        _build(nt)
        nt[PROP_VERSION] = GROUP_VERSION
    return nt


def group_node(mat):
    """The tool-marks node of a material, or None."""
    nt = getattr(mat, "node_tree", None)
    if nt is None:
        return None
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeGroup" and n.node_tree is not None and PROP_VERSION in n.node_tree:
            return n
    return None


def apply(b, bsdf, tm: dict, rough, normal=None, plain_rough=None, tangent=None):
    """Put the tool marks into a material that ``materials.build_nodes`` is building; returns the new
    ``(roughness, normal)`` sockets the builder carries on with. It links the BSDF's Tangent and Anisotropic.

    ``b``: the builder's ``_Nodes``; ``tm``: ``dict(size=1.0, strength=1.0, ridge=…, rough=…, anisotropic=…,
    hatch=…, pixel_angle=…)`` (ridge … hatch: ``core.toolmarks.look``; all may be missing); ``rough``, ``normal``,
    ``tangent``: the material's own look so far (a socket, a number or None) – it stays where a face has no
    move; ``plain_rough``: the roughness before the material's own marks – the tool marks start from it."""
    g = b.node("ShaderNodeGroup", -100, 1000)
    g.node_tree = ensure_group()
    g.name, g.label = NODE, "Tool marks"
    g.width = 220
    ins = g.inputs
    lk = {**core.LOOK_DEFAULT, **{k: tm[k] for k in core.LOOK_KEYS if tm.get(k) is not None}}
    ins["Size"].default_value = float(tm.get("size", 1.0))
    ins["Strength"].default_value = float(tm.get("strength", 1.0))
    for key, name in LOOK_INPUTS.items():
        ins[name].default_value = float(lk[key])
    ins["Pixel angle"].default_value = float(tm.get("pixel_angle") or core.PIXEL_ANGLE)
    b.put(ins["Roughness"], rough)
    b.put(ins["Marks roughness"], rough if plain_rough is None else plain_rough)
    if normal is None:                                   # the mesh's own (smooth) normal, as an unlinked BSDF takes
        normal = b.node("ShaderNodeNewGeometry", -400, 800).outputs["Normal"]
    b.put(ins["Normal"], normal)
    own = bsdf.inputs["Anisotropic"]
    if own.is_linked:
        b.put(ins["Anisotropic"], own.links[0].from_socket)
    else:
        ins["Anisotropic"].default_value = own.default_value
        if own.default_value and tangent is None:        # what an unlinked BSDF takes: round the part's Z axis
            tn = b.node("ShaderNodeTangent", -400, 1100)
            tn.direction_type, tn.axis = "RADIAL", "Z"
            tangent = tn.outputs[0]
    if tangent is not None:
        b.put(ins["Tangent"], tangent)
    b.nt.links.new(g.outputs["Anisotropic"], own)
    b.nt.links.new(g.outputs["Tangent"], bsdf.inputs["Tangent"])
    return g.outputs["Roughness"], g.outputs["Normal"]


def set_inputs(mat, size: float | None = None, strength: float | None = None,
               pixel_angle: float | None = None) -> bool:
    """Set Mark size and Strength (and the angle of a pixel, ``core.toolmarks.pixel_angle``) on a material that
    has tool marks: no rebuild. Only a value that differs is written, because writing an unchanged value
    restarts a viewport render. True when the material has tool marks."""
    g = group_node(mat)
    if g is None:
        return False
    for name, value in (("Size", size), ("Strength", strength), ("Pixel angle", pixel_angle)):
        sock = g.inputs.get(name)
        if value is not None and sock is not None and abs(sock.default_value - float(value)) > 1e-7:
            sock.default_value = float(value)
    return True
