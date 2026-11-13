"""Cable looks whose pattern moves along the cable (task 0078): a power cable (black, yellow stripes at an angle)
and a steel wire rope (strands with their lay). Shader nodes only: no pictures, no scripts, no drivers inside the
material, so they work with "Auto Run Python Scripts" off, in Cycles and EEVEE, and in the render queue.

The contract with the geometry side (``blender/paths.py``)
---------------------------------------------------------
``fr_cable``       POINT attribute (FLOAT_VECTOR) on the cable's tube: ``(cos φ, sin φ, s)`` – φ the angle round the
                   cable, s the metres along the path from its start. A mesh without it gives (0, 0, 0): where the
                   length of (x, y) is below 0.5 the material shows its **plain base** (black sheath / plain steel),
                   so the look may be given to a whole group of parts.
``fr_cable_pay``   custom property of the cable *object* (float): metres paid out x direction + ``PAY_BIAS`` (2.0;
                   a driver's result is never near 0, CLAUDE.md section 8). The nodes take the bias off.
``fr_cable_look``  custom property of the cable object (4 floats): ``[pitch m, starts, width share, kind]``.
                   ``starts`` is a signed whole number (the nodes round it): how many stripes / strands go round the
                   cable, the sign is the hand. ``kind`` 1 = power cable, 2 = wire rope (the material itself decides
                   what it draws; the number is there for the geometry side). An object without it gives zeros:
                   a pitch of 0 means "no look given" and the library entry's own pitch, starts and width are drawn.

What is drawn (``phase``, ``pattern``, ``wires`` below are the nodes' formula in plain Python; the tests compare
renders with them). With ``u = (s − paid out) / pitch`` and ``θ = φ / 2π``:

**Power cable**  ``phase = u + starts · θ``; yellow where ``fract(phase) < width``, else the sheath. ``pitch`` is
the distance between two stripes along the cable; starts 0 = rings. A mark at s₀ with nothing paid out is at
s₀ + paid out later.

**Steel wire rope**  ``pitch`` is the **lay length** (one full turn of a strand), so with n = |starts| strands
``phase = n · u + starts · θ`` (n crowns round the rope, n crowns per lay length along it). Across one strand
``x = 2 · fract(phase) − 1`` runs from valley (−1) over the crown (0) to the next valley (+1); its height is the
round ``sqrt(1 − x²)``. The single wires of a strand are finer lines laid the other way (regular lay):
``wire phase = wires · (fract(phase) − (1 + slant) · n · u)``, lines that lean ``slant`` of the strands' lean to the
other side. Steel on the crowns, dark and a little greasy in the valleys, a bump from the height. The bump and the
wire lines fade with the distance (a strand or a wire smaller than a few pixels would only give noise).

Which hand a positive ``starts`` gives depends on which way the geometry's φ turns: along a stripe φ gets *smaller*
as s grows (``starts > 0``). With φ turning right-handed about the direction of growing s that is a left-hand
helix; give −6 for the usual right-hand lay then.
"""

from __future__ import annotations

import math

import numpy as np

from ..core import materials_lib

# no ``import bpy`` here: ``look_values`` and ``pattern`` work without Blender; ``apply`` gets the node builder

PAY = "fr_cable_pay"
LOOK = "fr_cable_look"
ATTR = "fr_cable"
PAY_BIAS = 2.0
KINDS = {"POWER": 1.0, "ROPE": 2.0}
MATERIALS = {"POWER": "cable_power", "ROPE": "wire_rope"}

#: most stripes round a cable (a stripe almost along the cable would need endlessly many)
STARTS_MAX = 64
#: strands of a wire rope
STRANDS = 6
#: names of the nodes in a material (tests and tools look them up)
NODE_ATTR, NODE_PAY, NODE_LOOK = "FR cable attr", "FR cable pay", "FR cable look"
NODE_PATTERN = "FR cable pattern"          # output 0: what ``pattern`` gives (power: the stripe 0 … 1; rope: height)
NODE_WIRES = "FR cable wires"              # rope only, output 0: what ``wires`` gives
NODE_HAS = "FR cable has"                  # output 0: 1 where the mesh has the attribute
#: the angle one pixel covers (1920 px wide, 50 mm lens): the rope's bump and wires fade by it
PIXEL_ANGLE = 36.0 / 50.0 / 1920.0
#: (from, to) pixels per strand / per wire between which the relief fades in
FADE_STRAND = (1.5, 4.0)
FADE_WIRE = (1.5, 4.0)

#: what a library entry's ``cable`` dict may hold, with the values used when it does not
DEFAULTS = {
    "POWER": dict(pitch=0.5, starts=1, width=0.25,
                  stripe=(0.945, 0.765, 0.0),        # traffic yellow (RAL 1023; tables give #F7B500 … #F0CA00), sRGB
                  stripe_roughness=0.4,              # painted stripes: a little glossier than the sheath
                  edge=0.01),                        # softened edge, share of a period (its 50 % point stays)
    "ROPE": dict(pitch=0.16, starts=STRANDS, width=0.0,
                 wires=6,                            # wires seen across one strand
                 slant=0.2,                          # the wires lean this share of the strands' lean, the other way
                 grease=(0.045, 0.04, 0.035),        # sRGB, in the valleys between strands
                 grease_amount=0.9, grease_metallic=0.25, grease_roughness=0.5,
                 wire_dark=0.3,                      # how much darker the line between two wires is
                 strand_radius=0.025,                # strand radius as a share of the lay length (bump height)
                 wire_height=0.1,                    # relief of a wire as a share of the strand radius
                 bump=0.7),                          # strength of the Bump node
}


# ---------------------------------------------------------------------------------------------------------------
# the formula in plain Python (no bpy)
# ---------------------------------------------------------------------------------------------------------------

def kind_name(kind) -> str:
    """"POWER" / "ROPE" from the name or the number stored in ``fr_cable_look``."""
    if isinstance(kind, str):
        k = kind.upper()
        if k not in KINDS:
            raise ValueError(f"unknown cable look {kind!r}")
        return k
    return "ROPE" if float(kind) > 1.5 else "POWER"


def defaults(kind) -> dict:
    """The settings of a kind: ``DEFAULTS`` with what the library entry's ``cable`` dict says on top."""
    k = kind_name(kind)
    lib = materials_lib.MATERIALS.get(MATERIALS[k], {}).get("cable") or {}
    return {**DEFAULTS[k], **{key: v for key, v in lib.items() if key != "kind"}}


def stripes(diameter: float, pitch: float, angle: float) -> int:
    """How many stripes go round a cable (signed): ``round(π · d / (pitch · tan(angle)))``; ``angle`` (rad) between
    a stripe and the cable, 90° = rings (0), a negative angle = the other hand."""
    if pitch <= 0.0 or diameter <= 0.0:
        return 0
    t = math.tan(angle)
    if abs(t) < 1e-9:                                 # a stripe along the cable: as many as we draw
        return -STARTS_MAX if angle < 0.0 else STARTS_MAX
    n = math.floor(math.pi * diameter / (pitch * t) + 0.5)
    return int(max(-STARTS_MAX, min(STARTS_MAX, n)))


def look_values(kind, diameter: float = 0.0, pitch: float = 0.0, angle: float = math.pi / 4,
                width: float | None = None) -> list[float]:
    """The 4 numbers of ``fr_cable_look``: ``[pitch m, starts, width share, kind]``.

    Power cable: ``pitch`` = the distance between two stripes along the cable, ``angle`` (rad) between a stripe and
    the cable (90° = rings, negative = the other hand), ``width`` = the yellow share of a period (0 … 1).
    Wire rope: ``pitch`` = the lay length (one full turn of a strand), 6 strands, a negative ``angle`` = the other
    hand; ``diameter`` and ``width`` are not used. A pitch of 0 (or less) takes the library entry's."""
    k = kind_name(kind)
    d = defaults(k)
    pitch = float(pitch) if pitch and pitch > 0.0 else float(d["pitch"])
    if k == "ROPE":
        starts = -STRANDS if angle < 0.0 else STRANDS
        w = 0.0 if width is None else width
    else:
        starts = stripes(float(diameter), pitch, float(angle))
        w = d["width"] if width is None else width
    return [pitch, float(starts), float(min(1.0, max(0.0, w))), KINDS[k]]


def _look(kind, look):
    """(pitch, starts, width) the nodes use: the look's, or the library's when the look has no pitch."""
    d = defaults(kind)
    if look is None or len(look) < 3 or not float(look[0]) > 1e-6:
        return float(d["pitch"]), int(d["starts"]), float(d["width"])
    return float(look[0]), int(math.floor(float(look[1]) + 0.5)), min(1.0, max(0.0, float(look[2])))


def phase(kind, s, phi, paid_out, look=None):
    """The number whose whole part counts the stripes (strands): see the module's docstring. ``s`` and ``phi`` may
    be NumPy arrays; ``look`` the 4 numbers (None, or a pitch of 0: the library's look)."""
    k = kind_name(kind)
    pitch, starts, _w = _look(k, look)
    u = (np.asarray(s, float) - paid_out) / pitch
    turns = np.asarray(phi, float) / (2.0 * math.pi)
    n = max(abs(starts), 1) if k == "ROPE" else 1
    return n * u + starts * turns


def pattern(kind, s, phi, paid_out, look=None, edge: float = 0.0):
    """What the nodes draw at ``s`` metres along the cable and the angle ``phi`` round it, ``paid_out`` metres paid
    out. Power cable: 1.0 = yellow, 0.0 = the black sheath (``edge`` > 0: the softened edge the nodes draw, as a
    share of a period – its 50 % point is where the hard edge is). Wire rope: the height 0 … 1 of the strand
    surface (1 on a crown, 0 in the valley between two strands)."""
    k = kind_name(kind)
    f = phase(k, s, phi, paid_out, look)
    f = f - np.floor(f)
    if k == "ROPE":
        out = np.sqrt(np.maximum(1.0 - (2.0 * f - 1.0) ** 2, 0.0))
    else:
        w = _look(k, look)[2]
        if edge > 0.0:
            d = f - 0.5 * w + 0.5
            d = np.abs(d - np.floor(d) - 0.5)
            e = max(min(edge, w, 1.0 - w), 1e-6)
            out = np.clip((0.5 * w - d) / e + 0.5, 0.0, 1.0)
        else:
            out = (f < w).astype(float)
    return float(out) if np.ndim(out) == 0 else out


def wires(s, phi, paid_out, look=None, count: float | None = None, slant: float | None = None):
    """The wires of a rope's strands: 0 on the line between two wires … 1 on a wire's back (``|sin(π · wire
    phase)|``). ``count`` wires across a strand, leaning ``slant`` of the strands' lean the other way."""
    d = defaults("ROPE")
    count = float(d["wires"] if count is None else count)
    slant = float(d["slant"] if slant is None else slant)
    pitch, starts, _w = _look("ROPE", look)
    n = max(abs(starts), 1)
    u = (np.asarray(s, float) - paid_out) / pitch
    f = n * u + starts * np.asarray(phi, float) / (2.0 * math.pi)
    f = f - np.floor(f)
    out = np.abs(np.sin(math.pi * count * (f - (1.0 + slant) * n * u)))
    return float(out) if np.ndim(out) == 0 else out


# ---------------------------------------------------------------------------------------------------------------
# the nodes
# ---------------------------------------------------------------------------------------------------------------

def _named(sock, name: str, label: str = ""):
    sock.node.name = name
    sock.node.label = label or name
    return sock


def _inputs(b, d: dict, y: float) -> dict:
    """The nodes both looks share: the attribute, the two properties, the look with its fall-backs.
    Returns sockets: has, s, turns (φ / 2π), u ((s − paid out) / pitch), pitch, starts, width."""
    m = b.math
    x0 = -3300

    def attribute(name, kind, node_name, yy):
        n = b.node("ShaderNodeAttribute", x0, yy)
        n.attribute_type, n.attribute_name = kind, name
        n.name = n.label = node_name
        return n

    geo = b.node("ShaderNodeSeparateXYZ", x0 + 200, y)
    b.put(geo.inputs[0], attribute(ATTR, "GEOMETRY", NODE_ATTR, y).outputs["Vector"])
    cx, sy, s = geo.outputs
    has = _named(m("GREATER_THAN", m("ADD", m("MULTIPLY", cx, cx, x=x0 + 400, y=y + 150),
                                     m("MULTIPLY", sy, sy, x=x0 + 400, y=y), x=x0 + 550, y=y + 100), 0.25,
                   x=x0 + 700, y=y + 100), NODE_HAS)
    turns = m("DIVIDE", m("ARCTAN2", sy, cx, x=x0 + 400, y=y - 150), 2.0 * math.pi, x=x0 + 550, y=y - 150)
    paid = m("SUBTRACT", attribute(PAY, "OBJECT", NODE_PAY, y - 400).outputs["Fac"], PAY_BIAS, x=x0 + 200, y=y - 400)
    look = b.node("ShaderNodeSeparateXYZ", x0 + 200, y - 650)
    b.put(look.inputs[0], attribute(LOOK, "OBJECT", NODE_LOOK, y - 650).outputs["Vector"])
    given = m("GREATER_THAN", look.outputs[0], 1e-6, x=x0 + 400, y=y - 550)      # an object without a look: zeros
    pitch = b.mix("FLOAT", given, float(d["pitch"]), look.outputs[0], x=x0 + 550, y=y - 500)
    starts = m("ROUND", b.mix("FLOAT", given, float(d["starts"]), look.outputs[1], x=x0 + 550, y=y - 700),
               x=x0 + 700, y=y - 700)
    width = b.mix("FLOAT", given, float(d["width"]), look.outputs[2], x=x0 + 550, y=y - 900)
    width = m("MAXIMUM", m("MINIMUM", width, 1.0, x=x0 + 700, y=y - 900), 0.0, x=x0 + 850, y=y - 900)
    u = m("DIVIDE", m("SUBTRACT", s, paid, x=x0 + 400, y=y - 350), pitch, x=x0 + 850, y=y - 350)
    return dict(has=has, s=s, turns=turns, u=u, pitch=pitch, starts=starts, width=width)


def _linear(srgb) -> tuple:
    from ..core import ral
    return (*(ral.srgb_to_linear(c) for c in srgb), 1.0)


def _power(b, d: dict, color, metallic, rough, normal):
    m = b.math
    y = 2200
    i = _inputs(b, d, y)
    x0 = -2300
    ph = m("ADD", i["u"], m("MULTIPLY", i["starts"], i["turns"], x=x0, y=y - 150), x=x0 + 150, y=y)
    half = m("MULTIPLY", i["width"], 0.5, x=x0, y=y - 400)
    # the distance (in periods) from the middle of the stripe: yellow where it is below half the width
    f = m("FRACT", m("ADD", m("SUBTRACT", ph, half, x=x0 + 300, y=y), 0.5, x=x0 + 450, y=y), x=x0 + 600, y=y)
    dist = m("ABSOLUTE", m("SUBTRACT", f, 0.5, x=x0 + 750, y=y), x=x0 + 900, y=y)
    edge = m("MAXIMUM", m("MINIMUM", float(d["edge"]),
                          m("MINIMUM", i["width"], m("SUBTRACT", 1.0, i["width"], x=x0, y=y - 600),
                            x=x0 + 150, y=y - 600), x=x0 + 300, y=y - 600), 1e-6, x=x0 + 450, y=y - 600)
    soft = m("ADD", m("DIVIDE", m("SUBTRACT", half, dist, x=x0 + 1050, y=y), edge, x=x0 + 1200, y=y), 0.5,
             x=x0 + 1350, y=y, clamp=True)
    fac = _named(m("MULTIPLY", soft, i["has"], x=x0 + 1500, y=y), NODE_PATTERN, "Stripe")
    color = b.mix("RGBA", fac, color, _linear(d["stripe"]), x=x0 + 1700, y=y)
    rough = b.mix("FLOAT", fac, rough, float(d["stripe_roughness"]), x=x0 + 1700, y=y - 250)
    return color, metallic, rough, normal


def _fade(b, pixels, limits, x: float, y: float):
    n = b.node("ShaderNodeMapRange", x, y, From_Min=limits[0], From_Max=limits[1], To_Min=0.0, To_Max=1.0)
    n.interpolation_type = "SMOOTHSTEP"
    b.put(n.inputs["Value"], pixels)
    return n.outputs["Result"]


def _rope(b, d: dict, color, metallic, rough, normal):
    m = b.math
    y = 2200
    i = _inputs(b, d, y)
    has = i["has"]
    x0 = -2300
    n = m("MAXIMUM", m("ABSOLUTE", i["starts"], x=x0, y=y - 300), 1.0, x=x0 + 150, y=y - 300)      # strands
    nu = m("MULTIPLY", n, i["u"], x=x0 + 300, y=y)
    f = m("FRACT", m("ADD", nu, m("MULTIPLY", i["starts"], i["turns"], x=x0, y=y - 150), x=x0 + 450, y=y),
          x=x0 + 600, y=y)
    xs = m("SUBTRACT", m("MULTIPLY", f, 2.0, x=x0 + 750, y=y), 1.0, x=x0 + 900, y=y)      # −1 valley, 0 crown
    height = _named(m("SQRT", m("MAXIMUM", m("SUBTRACT", 1.0, m("MULTIPLY", xs, xs, x=x0 + 1050, y=y),
                                             x=x0 + 1200, y=y), 0.0, x=x0 + 1350, y=y), x=x0 + 1500, y=y),
                    NODE_PATTERN, "Strand height")
    # the wires of a strand: finer lines that lean the other way
    count, slant = float(d["wires"]), float(d["slant"])
    wp = m("MULTIPLY", m("SUBTRACT", f, m("MULTIPLY", nu, 1.0 + slant, x=x0 + 600, y=y - 300), x=x0 + 750, y=y - 300),
           count * math.pi, x=x0 + 900, y=y - 300)
    wire = _named(m("ABSOLUTE", m("SINE", wp, x=x0 + 1050, y=y - 300), x=x0 + 1200, y=y - 300), NODE_WIRES, "Wires")

    # how many pixels a strand and a wire cover: below a few, their relief would only be noise
    cam = b.node("ShaderNodeCameraData", x0, y - 900)
    pixel = m("MAXIMUM", m("MULTIPLY", cam.outputs["View Distance"], PIXEL_ANGLE, x=x0 + 200, y=y - 900), 1e-9,
              x=x0 + 350, y=y - 900)
    strand_px = m("DIVIDE", m("DIVIDE", m("MULTIPLY", i["pitch"], 0.9, x=x0 + 200, y=y - 1100), n,
                              x=x0 + 350, y=y - 1100), pixel, x=x0 + 500, y=y - 1000)
    fade_s = _fade(b, strand_px, FADE_STRAND, x0 + 700, y - 900)
    fade_w = _fade(b, m("DIVIDE", strand_px, max(count, 1.0), x=x0 + 700, y=y - 1200), FADE_WIRE, x0 + 900, y - 1200)

    # colour: steel on the crowns, grease in the valleys, a faint dark line between two wires
    valley = b.map(height, 0.2, 0.7, 1.0, 0.0, x=x0 + 1700, y=y + 300)
    grease = m("MULTIPLY", m("MULTIPLY", valley, float(d["grease_amount"]), x=x0 + 1900, y=y + 300), has,
               x=x0 + 2050, y=y + 300, clamp=True)
    line = m("MULTIPLY", m("MULTIPLY", m("SUBTRACT", 1.0, wire, x=x0 + 1350, y=y - 300), fade_w,
                           x=x0 + 1500, y=y - 300),
             m("MULTIPLY", has, float(d["wire_dark"]), x=x0 + 1500, y=y - 500), x=x0 + 1700, y=y - 300, clamp=True)
    steel = b.mix("RGBA", line, color, (0.0, 0.0, 0.0, 1.0), x=x0 + 1900, y=y - 100)
    color = b.mix("RGBA", grease, steel, _linear(d["grease"]), x=x0 + 2250, y=y)
    metallic = b.mix("FLOAT", grease, metallic, float(d["grease_metallic"]), x=x0 + 2250, y=y - 250)
    rough = b.mix("FLOAT", grease, rough, float(d["grease_roughness"]), x=x0 + 2250, y=y - 450)

    # the relief: the strands' round backs with the wires on them, in metres
    radius = m("MULTIPLY", i["pitch"], float(d["strand_radius"]), x=x0 + 1500, y=y - 1100)
    relief = m("ADD", m("MULTIPLY", height, fade_s, x=x0 + 1700, y=y - 700),
               m("MULTIPLY", m("MULTIPLY", wire, fade_w, x=x0 + 1700, y=y - 900), float(d["wire_height"]),
                 x=x0 + 1850, y=y - 900), x=x0 + 2000, y=y - 800)
    metres = m("MULTIPLY", m("MULTIPLY", relief, radius, x=x0 + 2150, y=y - 800), has, x=x0 + 2300, y=y - 800)
    bump = b.node("ShaderNodeBump", x0 + 2500, y - 800, Strength=float(d["bump"]), Distance=1.0)
    b.put(bump.inputs["Height"], metres)
    if normal is not None:
        b.put(bump.inputs["Normal"], normal)
    return color, metallic, rough, bump.outputs["Normal"]


def apply(b, bsdf, spec: dict, color, metallic, rough, normal):
    """Put a cable look into a material that ``materials.build_nodes`` is building. ``spec``: the library entry's
    ``cable`` dict (``kind`` "POWER" | "ROPE" and any key of ``DEFAULTS``); ``color``, ``metallic``, ``rough``,
    ``normal``: the material's look so far (sockets, values or None) – it stays where a mesh has no ``fr_cable``
    attribute. Returns the four the builder carries on with."""
    kind = kind_name(spec.get("kind", "POWER"))
    d = {**DEFAULTS[kind], **{k: v for k, v in spec.items() if k != "kind"}}
    if kind == "ROPE":
        return _rope(b, d, color, metallic, rough, normal)
    return _power(b, d, color, metallic, rough, normal)


def nodes_of(mat) -> dict:
    """The look's named nodes in a material: {name: node} (empty when the material has no cable look)."""
    nt = getattr(mat, "node_tree", None)
    if nt is None:
        return {}
    return {name: nt.nodes[name] for name in (NODE_ATTR, NODE_PAY, NODE_LOOK, NODE_PATTERN, NODE_WIRES, NODE_HAS)
            if name in nt.nodes}
