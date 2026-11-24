"""Marine weathering looks (task 0116): steel at sea, drawn over the marine paint system. Shader nodes only: no
pictures, no scripts, no drivers, so they work with "Auto Run Python Scripts" off, in Cycles and EEVEE, and in the
render queue. ``materials.build_nodes`` calls ``apply`` for a library entry with a ``marine`` dict; the per-group
wear and the weather wrap (task 0109) come after it as for every other look.

Two kinds
---------
**GROWTH** (``paint_marine_growth``): below the waterline marine growth – dark green-brown, rough, bumpy, with a few
pale barnacle spots – whose upper edge is patchy (it wanders ``edge_jitter`` m up and down round ``edge`` m from the
waterline); above it the splash zone, ``splash`` m high: a slime / algae tint and thin vertical rust streaks, both
fading upwards.

**EROSION** (``paint_blade_eroded``, task 0128): a worn leading edge for a wind turbine blade – a strip along the edge
that faces ``edge_dir``, from ``span_from`` to the tip, where the paint is gone in patches: grey laminate, dull, with
small chips and a rough relief; ``erosion`` is its formula in plain Python.

**STREAKS** (``paint_marine_streaks``): light run-down streaks of dirt and rust, thin and vertical in the world,
stronger in some places than in others, never on faces that face up or down.

The waterline
-------------
A **world** height: the scene's custom property ``fr_waterline_z`` (metres), read by an Attribute node of type View
Layer (no driver: a stored number, so scripts may be off). A scene without it gives 0: the waterline is world z 0.
``sync(scene)`` writes it from the surroundings' sea (its world height; without a sea it leaves the scene as it is);
``build_nodes`` calls it for every scene when it builds a growth look, and whatever builds or moves the surroundings
may call it too (the material then follows at once: it reads the property at render time).

The patterns (growth edge, mottling, barnacles, streaks) use the object's own coordinates, so they stay on a part
that moves; only the band's height is the world's. The streaks run along the world's "up" turned into the object's
coordinates. ``growth``, ``splash`` and ``edge_shift`` below are the nodes' formula in plain Python (the tests
compare renders with them).
"""

from __future__ import annotations

import numpy as np

# no ``import bpy`` at the top: the formula works without Blender; ``apply`` gets the node builder

WATERLINE = "fr_waterline_z"           # scene custom property: world z of the water surface, metres
KINDS = ("GROWTH", "STREAKS", "EROSION")
MATERIALS = {"GROWTH": "paint_marine_growth", "STREAKS": "paint_marine_streaks", "EROSION": "paint_blade_eroded"}

#: names of the nodes in a material (tests and tools look them up)
NODE_WATERLINE = "FR marine waterline"     # the View Layer attribute: output "Fac" = the waterline
NODE_HEIGHT = "FR marine height"           # output 0: height above the waterline (m, world)
NODE_GROWTH = "FR marine growth"           # output 0: what ``growth`` gives (1 = covered)
NODE_SPLASH = "FR marine splash"           # output 0: what ``splash`` gives (1 at and below the waterline)
NODE_STREAKS = "FR marine streaks"         # output 0: how much streak colour a point gets, 0 … 1
NODE_EROSION = "FR blade erosion"          # output 0: how worn a point is, 0 … 1 (what ``erosion`` gives)

#: Blender's noise lies mostly between these two: the edge's wander is mapped from them to −1 … +1
NOISE_LO, NOISE_HI = 0.3, 0.7

#: what a library entry's ``marine`` dict may hold, with the values used when it does not (colours sRGB, lengths m)
DEFAULTS = {
    "GROWTH": dict(edge=-0.35,                        # the growth's upper edge, on average, from the waterline
                   edge_jitter=0.6,                   # it wanders this much up and down (patchy)
                   edge_soft=0.25,                    # the edge's soft width
                   edge_scale=2.2,                    # patches of the edge per metre
                   growth=(0.15, 0.16, 0.085),        # dark olive green
                   growth2=(0.30, 0.25, 0.15),        # brown
                   growth_roughness=0.88,
                   growth_bump=0.5,                   # strength of its relief
                   relief=0.008,                      # its relief, m
                   barnacle=(0.46, 0.44, 0.38),       # pale spots in the growth
                   barnacle_scale=45.0,               # spots per metre
                   barnacle_size=0.2,                 # share of a cell
                   splash=2.5,                        # height of the splash zone above the waterline
                   slime=(0.24, 0.25, 0.14),          # slime / algae tint
                   slime_amount=0.55,
                   slime_roughness=0.42,
                   rust=(0.34, 0.15, 0.06),
                   rust_amount=0.6,
                   rust_height=3.0,                   # rust streaks fade out this high above the waterline
                   streak_scale=30.0,                 # streak lines per metre across them
                   streak_along=0.7),                 # how fast they change along their length, per metre
    "STREAKS": dict(dirt=(0.20, 0.17, 0.12),
                    dirt_amount=0.42,
                    dirt_scale=18.0,
                    dirt_along=0.4,
                    rust=(0.36, 0.17, 0.07),
                    rust_amount=0.38,
                    rust_scale=40.0,
                    rust_along=0.8,
                    strength_scale=0.6,               # stronger and weaker places, per metre
                    roughness=0.12),                  # added to the roughness on a streak
    # EROSION (task 0128): a worn leading edge, for a wind turbine blade. In the part's own coordinates the blade runs
    # along z (metres, root 0) and its leading edge faces ``edge_dir`` (the importer keeps the CAD part's axes; the
    # IEA 15 MW blades of the site's model are drawn that way, the leading edge towards -y after mirroring)
    "EROSION": dict(edge_dir=(0.0, -1.0, 0.0),        # the way the leading edge faces, in the part's coordinates
                    edge_lo=0.55,                     # worn from here (cosine of the angle to edge_dir) …
                    edge_hi=0.86,                     # … fully worn from here: a strip ~40 degrees each side
                    span_from=70.0,                   # along the blade (m): no wear before this, …
                    span_full=108.0,                  # … full wear from here (the outer third and the tip)
                    patches=1.1,                      # wear patches per metre
                    patch_lo=0.45,                    # noise value where a patch begins (a lower value: more worn)
                    patch_hi=0.60,
                    laminate=(0.36, 0.38, 0.40),      # the grey glass-fibre laminate where the paint is gone
                    chips=40.0,                       # small chips per metre
                    chip_size=0.2,                    # share of a cell
                    paint_roughness=0.75,             # worn paint is duller
                    laminate_roughness=0.88,
                    bump=0.6,
                    relief=0.004),                    # m
}


def kind_name(kind) -> str:
    k = str(kind).upper()
    if k not in KINDS:
        raise ValueError(f"unknown marine look {kind!r}")
    return k


def defaults(kind) -> dict:
    return dict(DEFAULTS[kind_name(kind)])


# ---- the formula in plain Python ----------------------------------------------------------------------------------

def edge_shift(n, look: dict | None = None):
    """How far the growth's edge lies above its mean, for a noise value ``n`` (0 … 1), metres."""
    d = {**DEFAULTS["GROWTH"], **(look or {})}
    t = np.clip((np.asarray(n, float) - NOISE_LO) / (NOISE_HI - NOISE_LO), 0.0, 1.0)
    return d["edge_jitter"] * (2.0 * t - 1.0)


def growth(h, n=0.5, look: dict | None = None):
    """How covered a point ``h`` m above the waterline is (1 = all growth), its edge noise ``n`` (0 … 1)."""
    d = {**DEFAULTS["GROWTH"], **(look or {})}
    edge = d["edge"] + edge_shift(n, d)
    return np.clip((edge - np.asarray(h, float)) / d["edge_soft"] + 0.5, 0.0, 1.0)


def splash(h, look: dict | None = None):
    """The splash zone's weight at ``h`` m above the waterline: 1 at and below it, 0 from ``splash`` m up."""
    d = {**DEFAULTS["GROWTH"], **(look or {})}
    s = np.clip(1.0 - np.asarray(h, float) / d["splash"], 0.0, 1.0)
    return s * s


def growth_band(look: dict | None = None) -> tuple[float, float]:
    """(lowest, highest) height above the waterline where the growth's edge can lie: below the first everything
    is covered, above the second nothing."""
    d = {**DEFAULTS["GROWTH"], **(look or {})}
    return (d["edge"] - d["edge_jitter"] - d["edge_soft"] / 2, d["edge"] + d["edge_jitter"] + d["edge_soft"] / 2)


def erosion(cos_edge, span, n=0.5, look: dict | None = None):
    """How worn a point is (0 = paint as new … 1 = laminate showing): ``cos_edge`` = how squarely its surface faces
    ``edge_dir`` (cosine, -1 … 1), ``span`` = its distance along the blade (m), ``n`` = the patch noise (0 … 1)."""
    d = {**DEFAULTS["EROSION"], **(look or {})}
    t = lambda v, a, b: np.clip((np.asarray(v, float) - a) / (b - a), 0.0, 1.0)      # noqa: E731
    return (t(cos_edge, d["edge_lo"], d["edge_hi"]) * t(span, d["span_from"], d["span_full"])
            * t(1.0 - np.asarray(n, float), 1.0 - d["patch_hi"], 1.0 - d["patch_lo"]))


# ---- the waterline -----------------------------------------------------------------------------------------------

def _world(ob):
    """An object's world matrix from its parents' own transforms (a new object's ``matrix_world`` is stale until the
    next update)."""
    m = ob.matrix_basis.copy()
    while ob.parent is not None:
        m = ob.parent.matrix_basis @ ob.matrix_parent_inverse @ m
        ob = ob.parent
    return m


def sea_z(scene) -> float | None:
    """World z of the surroundings' sea in this scene (None: no sea)."""
    from . import surroundings
    for ob in scene.objects:
        if ob.get(surroundings.TAG) == "sea":
            return float(_world(ob).translation.z)
    return None


def waterline(scene) -> float:
    """The waterline the growth look draws in this scene (world z, m)."""
    try:
        return float(scene.get(WATERLINE, 0.0))
    except (TypeError, ValueError):
        return 0.0


def sync(scene) -> float:
    """Write the scene's waterline from its sea and return the waterline. Without a sea the scene keeps what it has
    (none: world z 0; a sea taken away: the growth stays where that sea was, as on a real structure). Changes the
    scene only when the value changes."""
    z = sea_z(scene)
    if z is None:
        return waterline(scene)
    try:
        if WATERLINE not in scene or abs(waterline(scene) - z) > 1e-6:
            scene[WATERLINE] = z
    except (AttributeError, RuntimeError, TypeError):      # e.g. while Blender draws: nothing may be written then
        pass
    return z


# ---- the nodes -----------------------------------------------------------------------------------------------------

#: the streak colours the looks had before task 0318 (a look that still has one gets the shared rust instead)
DEFAULT_RUSTS = {(0.34, 0.15, 0.06), (0.36, 0.17, 0.07)}


def _linear(srgb) -> tuple:
    from ..core import ral
    return (*(ral.srgb_to_linear(c) for c in srgb), 1.0)


def _named(sock, name: str, label: str = ""):
    sock.node.name = name
    sock.node.label = label or name
    return sock


def _up(b, x: float, y: float):
    """The world's up, in the object's coordinates (unit)."""
    vt = b.node("ShaderNodeVectorTransform", x, y)
    vt.vector_type = "VECTOR"
    vt.convert_from, vt.convert_to = "WORLD", "OBJECT"
    vt.inputs[0].default_value = (0.0, 0.0, 1.0)
    return b.vmath("NORMALIZE", vt.outputs[0], x=x + 150, y=y)


def _upright(b, x: float, y: float):
    """1 on upright faces, 0 on faces that face up or down (streaks run down walls, not across a deck)."""
    geo = b.node("ShaderNodeNewGeometry", x, y)
    nz = b.node("ShaderNodeSeparateXYZ", x + 150, y)
    b.put(nz.inputs[0], geo.outputs["Normal"])
    return b.map(b.math("ABSOLUTE", nz.outputs[2], x=x + 300, y=y), 0.55, 0.9, 1.0, 0.0, x=x + 450, y=y)


def _lines(b, up, k: float, along: float, lo: float, hi: float, x: float, y: float):
    """Thin lines along ``up``: a noise squeezed ``k`` per metre across and ``along`` per metre along them, its
    values from ``lo`` to ``hi`` mapped to 0 … 1 (only the high ridges are lines)."""
    p = b.coord()
    v = b.vmath("DOT_PRODUCT", p, up, x=x, y=y)
    q = b.vmath("SUBTRACT", b.vmath("SCALE", p, scale=k, x=x + 150, y=y + 100),
                b.vmath("SCALE", up, scale=b.math("MULTIPLY", v, k - along, x=x + 150, y=y - 200), x=x + 300,
                        y=y - 100), x=x + 450, y=y)
    n = b.noise(q, 1.0, 3.0, x=x + 600, y=y)
    return b.map(n, lo, hi, 0.0, 1.0, x=x + 750, y=y)


def _rust(b, d: dict, x: float, y: float):
    """The streaks' rust: the app's one rust look (``blender/rust.py``, task 0318) – the same as a group's Rust slider
    and the welds'. A look whose ``rust`` colour was set to something else keeps that colour."""
    from . import rust as rs
    if tuple(d.get("rust", ())) not in DEFAULT_RUSTS:
        return _linear(d["rust"])
    return rs.color(b, 600.0, x=x, y=y)


def _height(b, y: float):
    """Height above the waterline (m, world)."""
    geo = b.node("ShaderNodeNewGeometry", -3300, y)
    z = b.node("ShaderNodeSeparateXYZ", -3150, y)
    b.put(z.inputs[0], geo.outputs["Position"])
    wl = b.node("ShaderNodeAttribute", -3300, y - 250)
    wl.attribute_type, wl.attribute_name = "VIEW_LAYER", WATERLINE
    wl.name = wl.label = NODE_WATERLINE
    return _named(b.math("SUBTRACT", z.outputs[2], wl.outputs["Fac"], x=-3000, y=y), NODE_HEIGHT, "Height")


def _growth(b, bsdf, d: dict, coat: float, color, metallic, rough, normal):
    m = b.math
    y = 3400
    x0 = -2800
    h = _height(b, y)

    # the splash zone: slime and rust streaks fading upwards
    s = m("SUBTRACT", 1.0, m("DIVIDE", h, float(d["splash"]), x=x0, y=y - 300), x=x0 + 150, y=y - 300, clamp=True)
    s = _named(m("MULTIPLY", s, s, x=x0 + 300, y=y - 300), NODE_SPLASH, "Splash zone")
    mottle = b.map(b.noise(None, 2.5, 3.0, x=x0, y=y - 550), 0.35, 0.65, 0.35, 1.0, x=x0 + 150, y=y - 550)
    slime = m("MULTIPLY", m("MULTIPLY", s, mottle, x=x0 + 450, y=y - 450), float(d["slime_amount"]),
              x=x0 + 600, y=y - 450, clamp=True)
    up = _up(b, x0 - 300, y - 900)
    lines = _lines(b, up, float(d["streak_scale"]), float(d["streak_along"]), 0.58, 0.72, x0, y - 900)
    rust_fade = m("SUBTRACT", 1.0, m("DIVIDE", h, float(d["rust_height"]), x=x0 + 900, y=y - 1100),
                  x=x0 + 1050, y=y - 1100, clamp=True)
    rust = _named(m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", lines, rust_fade, x=x0 + 1200, y=y - 900),
                                  _upright(b, x0 + 600, y - 1300), x=x0 + 1350, y=y - 900),
                    float(d["rust_amount"]), x=x0 + 1500, y=y - 900, clamp=True), NODE_STREAKS, "Rust streaks")
    color = b.mix("RGBA", slime, color, _linear(d["slime"]), x=x0 + 1700, y=y - 400)
    color = b.mix("RGBA", rust, color, _rust(b, d, x0 + 1600, y - 1300), x=x0 + 1850, y=y - 600)
    rough = b.mix("FLOAT", slime, rough, float(d["slime_roughness"]), x=x0 + 1700, y=y - 700)

    # the growth: a patchy upper edge, two colours, pale barnacles, a rough bumpy relief
    jitter = float(d["edge_jitter"])
    shift = b.map(b.noise(None, float(d["edge_scale"]), 6.0, x=x0, y=y + 400), NOISE_LO, NOISE_HI, -jitter, jitter,
                  x=x0 + 150, y=y + 400)
    edge = m("ADD", shift, float(d["edge"]), x=x0 + 300, y=y + 400)
    g = m("ADD", m("DIVIDE", m("SUBTRACT", edge, h, x=x0 + 450, y=y + 300), float(d["edge_soft"]),
                   x=x0 + 600, y=y + 300), 0.5, x=x0 + 750, y=y + 300, clamp=True)
    g = _named(g, NODE_GROWTH, "Growth")
    tone = b.map(b.noise(None, 12.0, 5.0, x=x0, y=y + 700), 0.35, 0.65, 0.0, 1.0, x=x0 + 150, y=y + 700)
    gcol = b.mix("RGBA", tone, _linear(d["growth"]), _linear(d["growth2"]), x=x0 + 900, y=y + 700)
    vor = b.node("ShaderNodeTexVoronoi", x0, y + 1000)
    b.put(vor.inputs["Vector"], b.coord())
    b.put(vor.inputs["Scale"], float(d["barnacle_scale"]))
    size = float(d["barnacle_size"])
    spot = b.map(vor.outputs["Distance"], size, size * 0.6, 0.0, 1.0, x=x0 + 150, y=y + 1000)
    gcol = b.mix("RGBA", m("MULTIPLY", spot, 0.8, x=x0 + 900, y=y + 1000), gcol, _linear(d["barnacle"]),
                 x=x0 + 1100, y=y + 850)
    color = b.mix("RGBA", g, color, gcol, x=x0 + 2050, y=y)
    metallic = b.mix("FLOAT", g, metallic, 0.0, x=x0 + 2050, y=y - 250)
    rough = b.mix("FLOAT", g, rough, float(d["growth_roughness"]), x=x0 + 2050, y=y - 450)
    if coat:                                       # the growth is not under the clear coat
        b.put(bsdf.inputs["Coat Weight"], m("MULTIPLY", m("SUBTRACT", 1.0, g, x=x0 + 2050, y=y - 650), float(coat),
                                            x=x0 + 2200, y=y - 650))
    lumps = b.noise(None, 30.0, 6.0, x=x0 + 900, y=y + 1300)
    height = m("MULTIPLY", g, m("ADD", lumps, spot, x=x0 + 1100, y=y + 1300), x=x0 + 1250, y=y + 1300)
    bump = b.node("ShaderNodeBump", x0 + 1450, y + 1300, Strength=float(d["growth_bump"]),
                  Distance=float(d["relief"]))
    b.put(bump.inputs["Height"], height)
    if normal is not None:
        b.put(bump.inputs["Normal"], normal)
    return color, metallic, rough, bump.outputs["Normal"]


def _streaks(b, d: dict, color, metallic, rough, normal):
    m = b.math
    y = 3400
    x0 = -2800
    up = _up(b, x0 - 300, y)
    upright = _upright(b, x0, y - 900)
    strong = b.map(b.noise(None, float(d["strength_scale"]), 2.0, x=x0, y=y + 400), 0.4, 0.62, 0.15, 1.0,
                   x=x0 + 150, y=y + 400)
    rusty = b.map(b.noise(None, float(d["strength_scale"]) * 2.0, 2.0, w=None, x=x0, y=y + 700), 0.5, 0.68, 0.0,
                  1.0, x=x0 + 150, y=y + 700)
    dirt = _lines(b, up, float(d["dirt_scale"]), float(d["dirt_along"]), 0.55, 0.72, x0, y)
    rust = _lines(b, up, float(d["rust_scale"]), float(d["rust_along"]), 0.66, 0.76, x0, y - 400)
    dirt = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", dirt, strong, x=x0 + 900, y=y), upright, x=x0 + 1050, y=y),
             float(d["dirt_amount"]), x=x0 + 1200, y=y, clamp=True)
    rust = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", rust, rusty, x=x0 + 900, y=y - 400), upright,
                           x=x0 + 1050, y=y - 400), float(d["rust_amount"]), x=x0 + 1200, y=y - 400, clamp=True)
    both = _named(m("MAXIMUM", dirt, rust, x=x0 + 1350, y=y - 200), NODE_STREAKS, "Streaks")
    color = b.mix("RGBA", dirt, color, _linear(d["dirt"]), x=x0 + 1500, y=y)
    color = b.mix("RGBA", rust, color, _rust(b, d, x0 + 1400, y - 700), x=x0 + 1650, y=y - 200)
    rough = m("ADD", rough, m("MULTIPLY", both, float(d["roughness"]) / max(float(d["dirt_amount"]), 1e-6),
                              x=x0 + 1500, y=y - 500), x=x0 + 1650, y=y - 500, clamp=True)
    return color, metallic, rough, normal


def _erosion(b, d: dict, color, metallic, rough, normal):
    m = b.math
    x0, y = -2800, 3400
    geo = b.node("ShaderNodeNewGeometry", x0 - 300, y)
    vt = b.node("ShaderNodeVectorTransform", x0 - 150, y)
    vt.vector_type = "NORMAL"
    vt.convert_from, vt.convert_to = "WORLD", "OBJECT"
    b.put(vt.inputs[0], geo.outputs["Normal"])
    face = b.vmath("DOT_PRODUCT", b.vmath("NORMALIZE", vt.outputs[0], x=x0, y=y),
                   tuple(float(v) for v in d["edge_dir"]), x=x0 + 150, y=y)
    strip = b.map(face, float(d["edge_lo"]), float(d["edge_hi"]), 0.0, 1.0, x=x0 + 300, y=y)
    z = b.node("ShaderNodeSeparateXYZ", x0, y - 300)
    b.put(z.inputs[0], b.coord())
    ramp = b.map(z.outputs[2], float(d["span_from"]), float(d["span_full"]), 0.0, 1.0, x=x0 + 300, y=y - 300)
    patch = b.map(b.noise(None, float(d["patches"]), 4.0, x=x0, y=y - 600), float(d["patch_lo"]),
                  float(d["patch_hi"]), 1.0, 0.0, x=x0 + 300, y=y - 600)
    # map's To range 1 … 0 on the noise's low end: more worn where the noise is low (as ``erosion`` has it)
    worn = _named(m("MULTIPLY", m("MULTIPLY", strip, ramp, x=x0 + 600, y=y - 150), patch, x=x0 + 750, y=y - 300,
                    clamp=True), NODE_EROSION, "Blade erosion")
    vor = b.node("ShaderNodeTexVoronoi", x0, y - 900)
    b.put(vor.inputs["Vector"], b.coord())
    b.put(vor.inputs["Scale"], float(d["chips"]))
    size = float(d["chip_size"])
    chip = b.map(vor.outputs["Distance"], size, size * 0.5, 0.0, 1.0, x=x0 + 300, y=y - 900)
    # a few chips in the paint round the worn strip too (the strip's wider neighbourhood)
    near = b.map(strip, 0.0, 0.6, 0.0, 1.0, x=x0 + 450, y=y - 1050)
    show = m("MAXIMUM", worn, m("MULTIPLY", chip, m("MULTIPLY", near, ramp, x=x0 + 600, y=y - 1050),
                                x=x0 + 750, y=y - 1050), x=x0 + 900, y=y - 700, clamp=True)
    color = b.mix("RGBA", show, color, _linear(d["laminate"]), x=x0 + 1100, y=y)
    metallic = b.mix("FLOAT", show, metallic, 0.0, x=x0 + 1100, y=y - 250)
    rough = b.mix("FLOAT", show, rough, float(d["laminate_roughness"]), x=x0 + 1100, y=y - 450)
    rough = b.mix("FLOAT", b.map(worn, 0.0, 0.2, 0.0, 0.5, x=x0 + 900, y=y - 500), rough,
                  float(d["paint_roughness"]), x=x0 + 1250, y=y - 450)
    lumps = b.noise(None, 25.0, 5.0, x=x0 + 900, y=y - 1300)
    bump = b.node("ShaderNodeBump", x0 + 1450, y - 1300, Strength=float(d["bump"]), Distance=float(d["relief"]))
    b.put(bump.inputs["Height"], m("MULTIPLY", show, lumps, x=x0 + 1250, y=y - 1300))
    if normal is not None:
        b.put(bump.inputs["Normal"], normal)
    return color, metallic, rough, bump.outputs["Normal"]


def apply(b, bsdf, spec: dict, color, metallic, rough, normal, coat: float = 0.0):
    """Put a marine look into a material that ``materials.build_nodes`` is building. ``spec``: the library entry's
    ``marine`` dict (``kind`` "GROWTH" | "STREAKS" and any key of ``DEFAULTS``); ``color``, ``metallic``, ``rough``,
    ``normal``: the material's look so far (sockets, values or None); ``coat``: the paint's clear coat (the growth
    takes it off). Returns the four the builder carries on with."""
    kind = kind_name(spec.get("kind", "GROWTH"))
    d = {**DEFAULTS[kind], **{k: v for k, v in spec.items() if k != "kind"}}
    if kind == "GROWTH":
        return _growth(b, bsdf, d, coat, color, metallic, rough, normal)
    if kind == "EROSION":
        return _erosion(b, d, color, metallic, rough, normal)
    return _streaks(b, d, color, metallic, rough, normal)


def nodes_of(mat) -> dict:
    """The look's named nodes in a material: {name: node} (empty when the material has no marine look)."""
    nt = getattr(mat, "node_tree", None)
    if nt is None:
        return {}
    return {name: nt.nodes[name] for name in (NODE_WATERLINE, NODE_HEIGHT, NODE_GROWTH, NODE_SPLASH, NODE_STREAKS, NODE_EROSION)
            if name in nt.nodes}
