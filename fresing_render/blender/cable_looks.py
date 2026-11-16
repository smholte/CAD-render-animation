"""Cable looks whose pattern moves along the cable (task 0078): a power cable (black, yellow stripes at an angle),
a steel wire rope (strands with their lay) and (task 0158) a served cable (black yarn served round it, fibres, dust,
pairs of painted marker bands). Shader nodes only: no pictures, no scripts, no drivers inside the
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
                   cable, the sign is the hand. ``kind`` 1 = power cable, 2 = wire rope, 3 = served cable (the
                   material itself decides what it draws; the number is there for the geometry side). Served cable:
                   ``[band distance m, 0, band width m, 3]``.
``fr_cable_yarn``  served cable only (4 floats): ``[yarn pitch m, yarn starts, cable radius m, wear 0 … 1]``.
``fr_cable_band``  served cable only (4 floats): ``[bands in a group 1 | 2, gap m, paint wear 0 … 1, 0]``.
``fr_cable_yarn_rgb``, ``fr_cable_band_rgb``  served cable only: the yarn's and the paint's colour (scene linear).
                   Missing served-cable properties (zeros): the library entry's own settings. An object without it gives zeros:
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

**Served cable** (task 0158)  The yarn: ``g = (s − paid out) / yarn pitch + yarn starts · θ`` (yarn pitch = the
distance from one strand to the next along the cable; yarn starts from the lay angle as a power cable's stripes from
theirs). Across a strand ``x = 2 · fract(g) − 1``, its height ``sqrt(1 − x²)`` (``yarn``); each strand
(``floor(g)``) a little darker or lighter, fibres = noise stretched along the strand, dust in the grooves. The
marker bands: ``x = (s − paid out) mod distance``; the first band covers ``[0, w)``, the second (a pair)
``[w + gap, 2 w + gap)`` (``bands``: the clean bands). Drawn with ragged edges (noise, a few mm), the paint thinner
in the grooves and smudged black – both more with wear.

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
KINDS = {"POWER": 1.0, "ROPE": 2.0, "SERVED": 3.0}
MATERIALS = {"POWER": "cable_power", "ROPE": "wire_rope", "SERVED": "cable_served"}
YARN, BAND = "fr_cable_yarn", "fr_cable_band"                       # served cable (task 0158)
YARN_RGB, BAND_RGB = "fr_cable_yarn_rgb", "fr_cable_band_rgb"
#: every property a look writes on a cable object (a spool's rope copies them, a cable that stops being one loses them)
PROPS = (LOOK, YARN, BAND, YARN_RGB, BAND_RGB)

#: most stripes round a cable (a stripe almost along the cable would need endlessly many)
STARTS_MAX = 64
#: most yarn strands round a served cable (one lay of the serving)
YARN_STARTS_MAX = 4096
#: strands of a wire rope
STRANDS = 6
#: names of the nodes in a material (tests and tools look them up)
NODE_ATTR, NODE_PAY, NODE_LOOK = "FR cable attr", "FR cable pay", "FR cable look"
NODE_PATTERN = "FR cable pattern"          # output 0: what ``pattern`` gives (power: the stripe 0 … 1; rope: height)
NODE_WIRES = "FR cable wires"              # rope only, output 0: what ``wires`` gives
NODE_HAS = "FR cable has"                  # output 0: 1 where the mesh has the attribute
NODE_YARN = "FR cable yarn"                # served only, output 0: what ``yarn`` gives (the strand's height)
NODE_PAINT = "FR cable paint"              # served only, output 0: the paint as drawn (ragged, worn) 0 … 1
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
    # task 0158: black polypropylene yarn served almost square to the cable, pairs of yellow bands painted on it
    "SERVED": dict(pitch=1.25,                       # band distance: from one band group to the next, m
                   starts=0, width=0.035,            # (no stripes) the width of one band, m
                   count=2, gap=0.03,                # bands in a group, the gap between the two, m
                   yarn_pitch=0.0025,                # from one strand to the next along the cable, m
                   lay_angle=math.radians(82.0),     # between a strand and the cable (90° = rings)
                   diameter=0.3,                     # used for the fibres' scale when no cable gives its own
                   wear=0.35, band_wear=0.35,        # 0 = new, 1 = worn: dust and fuzz / ragged, smudged paint
                   yarn=(0.055, 0.055, 0.058),       # sRGB
                   band=(0.945, 0.765, 0.0),         # traffic yellow (RAL 1023), as the power cable's stripes
                   dust=(0.36, 0.34, 0.31),          # sRGB: light dust and lint caught between the strands
                   yarn_roughness=0.82, paint_roughness=0.6,
                   variation=0.6,                    # darker and lighter strands (share of the colour)
                   fibres=5.0,                       # fibre lines across one strand
                   rag=0.004,                        # ragged band edges: ± m at wear 1 (a third of it when new)
                   strand_height=0.35,               # the strand's relief as a share of the yarn pitch
                   bump=0.8),
}


# ---------------------------------------------------------------------------------------------------------------
# the formula in plain Python (no bpy)
# ---------------------------------------------------------------------------------------------------------------

def kind_name(kind) -> str:
    """"POWER" / "ROPE" / "SERVED" from the name or the number stored in ``fr_cable_look``."""
    if isinstance(kind, str):
        k = kind.upper()
        if k not in KINDS:
            raise ValueError(f"unknown cable look {kind!r}")
        return k
    k = float(kind)
    return "SERVED" if k > 2.5 else "ROPE" if k > 1.5 else "POWER"


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
    if k == "SERVED":                           # width: one band's, in metres
        w = float(d["width"]) if width is None else float(width)
        return [pitch, 0.0, float(min(pitch, max(0.0, w))), KINDS[k]]
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


def served_props(diameter: float = 0.0, distance: float = 0.0, width: float | None = None, count: int | None = None,
                 gap: float | None = None, yarn_pitch: float = 0.0, lay_angle: float | None = None,
                 wear: float | None = None, band_wear: float | None = None, yarn_rgb=None, band_rgb=None) -> dict:
    """Every property a served cable's object carries: {name: list of floats}. Lengths in metres, ``lay_angle``
    (rad) between a strand and the cable (negative = the other hand), colours scene linear (None: the library's).
    0 or None for a setting: the library entry's."""
    d = defaults("SERVED")
    pick = lambda v, key: float(d[key]) if v is None else float(v)        # noqa: E731
    dia = float(diameter) if diameter and diameter > 0.0 else float(d["diameter"])
    yp = float(yarn_pitch) if yarn_pitch and yarn_pitch > 0.0 else float(d["yarn_pitch"])
    look = look_values("SERVED", dia, distance, 0.0, width)
    n = yarn_starts(dia, yp, pick(lay_angle, "lay_angle"))
    cnt = int(d["count"] if count is None else count)
    lin = lambda c: [float(v) for v in c[:3]]                          # noqa: E731
    from ..core import ral
    return {LOOK: look,
            YARN: [yp, float(n), 0.5 * dia, min(1.0, max(0.0, pick(wear, "wear")))],
            BAND: [float(1 if cnt <= 1 else 2), max(0.0, pick(gap, "gap")),
                   min(1.0, max(0.0, pick(band_wear, "band_wear"))), 0.0],
            YARN_RGB: lin(yarn_rgb) if yarn_rgb is not None else [ral.srgb_to_linear(c) for c in d["yarn"]],
            BAND_RGB: lin(band_rgb) if band_rgb is not None else [ral.srgb_to_linear(c) for c in d["band"]]}


def yarn_starts(diameter: float, yarn_pitch: float, angle: float) -> int:
    """How many yarn strands go round a served cable (signed), as ``stripes`` but up to ``YARN_STARTS_MAX``."""
    t = math.tan(angle)
    if yarn_pitch <= 0.0 or diameter <= 0.0:
        return 0
    if abs(t) < 1e-9:                           # strands along the cable: as many as we draw
        return -YARN_STARTS_MAX if angle < 0.0 else YARN_STARTS_MAX
    return int(max(-YARN_STARTS_MAX, min(YARN_STARTS_MAX, math.floor(math.pi * diameter / (yarn_pitch * t) + 0.5))))


def _served(look=None, yarn=None, band=None) -> dict:
    """The served cable's numbers the nodes use, with the library's where a property is missing (zeros)."""
    d = defaults("SERVED")
    out = dict(distance=float(d["pitch"]), width=float(d["width"]), count=int(d["count"]), gap=float(d["gap"]),
               yarn_pitch=float(d["yarn_pitch"]), radius=0.5 * float(d["diameter"]),
               starts=yarn_starts(float(d["diameter"]), float(d["yarn_pitch"]), float(d["lay_angle"])),
               wear=float(d["wear"]), band_wear=float(d["band_wear"]))
    if look is not None and len(look) >= 3 and float(look[0]) > 1e-6:
        out["distance"] = float(look[0])
        out["width"] = min(out["distance"], max(0.0, float(look[2])))
    if yarn is not None and len(yarn) >= 4 and float(yarn[0]) > 1e-6:
        out.update(yarn_pitch=float(yarn[0]), starts=int(math.floor(float(yarn[1]) + 0.5)),
                   radius=float(yarn[2]) if float(yarn[2]) > 1e-6 else out["radius"],
                   wear=min(1.0, max(0.0, float(yarn[3]))))
    if band is not None and len(band) >= 3 and float(band[0]) > 0.5:
        out.update(count=1 if float(band[0]) < 1.5 else 2, gap=max(0.0, float(band[1])),
                   band_wear=min(1.0, max(0.0, float(band[2]))))
    return out


def yarn_phase(s, phi, paid_out, yarn=None):
    """The served cable's yarn phase ``g``: its whole part counts the strands (see the module's docstring)."""
    v = _served(yarn=yarn)
    return (np.asarray(s, float) - paid_out) / v["yarn_pitch"] + v["starts"] * np.asarray(phi, float) / (2.0 * math.pi)


def yarn(s, phi, paid_out, yarn=None):
    """The height 0 … 1 of the served cable's yarn surface: 1 on a strand's back, 0 in the groove between two."""
    f = yarn_phase(s, phi, paid_out, yarn)
    f = f - np.floor(f)
    out = np.sqrt(np.maximum(1.0 - (2.0 * f - 1.0) ** 2, 0.0))
    return float(out) if np.ndim(out) == 0 else out


def bands(s, paid_out, look=None, band=None, edge: float = 0.0):
    """The served cable's marker bands as clean rings: 1.0 on a band, 0.0 on the yarn (``edge`` > 0: the softened
    edge the nodes' ``FR cable pattern`` draws, in metres – its 50 % point is where the hard edge is). A mark at s₀
    with nothing paid out is at s₀ + paid out later."""
    v = _served(look=look, band=band)
    dist, w, gap = v["distance"], v["width"], v["gap"]
    x = np.mod(np.asarray(s, float) - paid_out, dist)
    starts = [0.0] if v["count"] == 1 else [0.0, w + gap]
    out = np.zeros(np.shape(x))
    for a in starts:
        for shift in (0.0, -dist, dist):            # the neighbouring periods' bands (and their soft edges)
            c = a + 0.5 * w + shift
            dd = np.abs(x - c)
            if edge > 0.0:
                e = max(min(edge, w), 1e-9)
                out = np.maximum(out, np.clip((0.5 * w - dd) / e + 0.5, 0.0, 1.0))
            else:                                  # [start, start + w): the left edge is paint
                out = np.maximum(out, ((x - (c - 0.5 * w) >= 0.0) & (x - (c - 0.5 * w) < w)).astype(float))
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
    return dict(has=has, s=s, turns=turns, u=u, pitch=pitch, starts=starts, width=width, cx=cx, sy=sy)


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


def _served_nodes(b, d: dict, color, metallic, rough, normal):
    """The served cable (task 0158): yarn grooves, strand shades, fibres, dust, the painted marker bands."""
    m = b.math
    y = 2200
    i = _inputs(b, d, y)
    has = i["has"]
    x0 = -3300

    def obj(name, yy):
        n = b.node("ShaderNodeAttribute", x0, yy)
        n.attribute_type, n.attribute_name = "OBJECT", name
        n.name = n.label = "FR cable property " + name[len("fr_cable_"):]
        return n

    v = _served()
    yn = obj(YARN, y - 1300)
    yv = b.node("ShaderNodeSeparateXYZ", x0 + 200, y - 1300)
    b.put(yv.inputs[0], yn.outputs["Vector"])
    y_given = m("GREATER_THAN", yv.outputs[0], 1e-6, x=x0 + 400, y=y - 1250)
    ypitch = b.mix("FLOAT", y_given, v["yarn_pitch"], yv.outputs[0], x=x0 + 550, y=y - 1200)
    ystarts = m("ROUND", b.mix("FLOAT", y_given, float(v["starts"]), yv.outputs[1], x=x0 + 550, y=y - 1350),
                x=x0 + 700, y=y - 1350)
    radius = b.mix("FLOAT", m("GREATER_THAN", yv.outputs[2], 1e-6, x=x0 + 400, y=y - 1500), v["radius"],
                   yv.outputs[2], x=x0 + 550, y=y - 1500)
    wear = b.mix("FLOAT", y_given, v["wear"], yn.outputs["Alpha"], x=x0 + 550, y=y - 1650)
    bn = obj(BAND, y - 1900)
    bv = b.node("ShaderNodeSeparateXYZ", x0 + 200, y - 1900)
    b.put(bv.inputs[0], bn.outputs["Vector"])
    b_given = m("GREATER_THAN", bv.outputs[0], 0.5, x=x0 + 400, y=y - 1850)
    pair = m("GREATER_THAN", b.mix("FLOAT", b_given, float(v["count"]), bv.outputs[0], x=x0 + 550, y=y - 1850), 1.5,
             x=x0 + 700, y=y - 1850)
    gap = b.mix("FLOAT", b_given, v["gap"], bv.outputs[1], x=x0 + 550, y=y - 2000)
    pwear = b.mix("FLOAT", b_given, v["band_wear"], bv.outputs[2], x=x0 + 550, y=y - 2150)
    # a colour property that is missing reads (0, 0, 0): the library's colour then (so pure black means "the library's")
    def colour(name, lib, yy):
        c = obj(name, yy).outputs
        given = m("GREATER_THAN", b.vmath("LENGTH", c["Vector"], x=x0 + 250, y=yy + 80), 1e-6, x=x0 + 400, y=yy + 80)
        return b.mix("RGBA", given, _linear(lib), c["Color"], x=x0 + 550, y=yy)

    yc = colour(YARN_RGB, d["yarn"], y - 2350)
    bc = colour(BAND_RGB, d["band"], y - 2550)

    x0 = -2400
    # ---- the yarn: g = (s − paid) / yarn pitch + starts · θ
    sp = m("MULTIPLY", i["u"], i["pitch"], x=x0, y=y)                                 # s − paid out, m
    g = m("ADD", m("DIVIDE", sp, ypitch, x=x0 + 150, y=y), m("MULTIPLY", ystarts, i["turns"], x=x0 + 150, y=y - 150),
          x=x0 + 300, y=y)
    xs = m("SUBTRACT", m("MULTIPLY", m("FRACT", g, x=x0 + 450, y=y), 2.0, x=x0 + 600, y=y), 1.0, x=x0 + 750, y=y)
    height = _named(m("SQRT", m("MAXIMUM", m("SUBTRACT", 1.0, m("MULTIPLY", xs, xs, x=x0 + 900, y=y),
                                             x=x0 + 1050, y=y), 0.0, x=x0 + 1200, y=y), x=x0 + 1350, y=y),
                    NODE_YARN, "Yarn height")
    valley = m("SUBTRACT", 1.0, height, x=x0 + 1500, y=y - 100)
    # which strand: floor(g) counted round the n strands of the serving (going once round the cable adds n to g, so
    # the same strand – no seam where the angle jumps); rings (n = 0) count on
    n_abs = m("ABSOLUTE", ystarts, x=x0 + 150, y=y + 450)
    period = m("ADD", n_abs, m("MULTIPLY", m("LESS_THAN", n_abs, 0.5, x=x0 + 150, y=y + 600), 1.0e7,
                                x=x0 + 300, y=y + 600), x=x0 + 450, y=y + 450)
    strand = m("FLOORED_MODULO", m("FLOOR", g, x=x0 + 450, y=y + 300), period, x=x0 + 600, y=y + 450)
    gm = m("ADD", m("FRACT", g, x=x0 + 450, y=y + 150), strand, x=x0 + 750, y=y + 450)     # g without the jump
    # each strand a little darker or lighter
    wn = b.node("ShaderNodeTexWhiteNoise", x0 + 600, y + 300)
    wn.noise_dimensions = "1D"
    b.put(wn.inputs["W"], strand)
    shade = m("ADD", m("MULTIPLY", m("SUBTRACT", wn.outputs["Value"], 0.5, x=x0 + 800, y=y + 300),
                       2.0 * float(d["variation"]), x=x0 + 950, y=y + 300), 1.0, x=x0 + 1100, y=y + 300)
    # the fibres: noise that changes fast across a strand and slowly along it; round the cable by (cos, sin) · r
    along = m("DIVIDE", radius, m("MULTIPLY", ypitch, 4.0, x=x0, y=y - 450), x=x0 + 150, y=y - 450)
    fv = b.node("ShaderNodeCombineXYZ", x0 + 450, y - 450)
    b.put(fv.inputs[0], m("MULTIPLY", gm, float(d["fibres"]), x=x0 + 300, y=y - 350))
    b.put(fv.inputs[1], m("MULTIPLY", i["cx"], along, x=x0 + 300, y=y - 500))
    b.put(fv.inputs[2], m("MULTIPLY", i["sy"], along, x=x0 + 300, y=y - 650))
    fibre = b.map(b.noise(fv.outputs[0], 1.0, 4.0, x=x0 + 650, y=y - 450), 0.3, 0.7, 0.0, 1.0, x=x0 + 850, y=y - 450)
    # where on the cable (metres along it, round it): dust blotches, paint smudges, ragged band edges
    dv = b.node("ShaderNodeCombineXYZ", x0 + 450, y - 800)
    b.put(dv.inputs[0], sp)
    b.put(dv.inputs[1], m("MULTIPLY", i["cx"], radius, x=x0 + 300, y=y - 850))
    b.put(dv.inputs[2], m("MULTIPLY", i["sy"], radius, x=x0 + 300, y=y - 1000))
    blot = b.noise(dv.outputs[0], 14.0, 6.0, x=x0 + 650, y=y - 800)
    lo = m("SUBTRACT", 0.75, m("MULTIPLY", wear, 0.3, x=x0 + 700, y=y - 1000), x=x0 + 850, y=y - 1000)
    dust = m("MULTIPLY", m("MULTIPLY", b.map(blot, lo, 0.8, 0.0, 1.0, x=x0 + 1000, y=y - 800),
                           m("ADD", valley, 0.2, x=x0 + 1650, y=y - 100), x=x0 + 1800, y=y - 800),
             m("ADD", m("MULTIPLY", wear, 0.8, x=x0 + 1650, y=y - 1000), 0.1, x=x0 + 1800, y=y - 1000),
             x=x0 + 1950, y=y - 800, clamp=True)

    # ---- the bands: x = (s − paid) mod distance; the first [0, w), the second [w + gap, 2w + gap)
    cam = b.node("ShaderNodeCameraData", x0, y - 2300)
    pixel = m("MAXIMUM", m("MULTIPLY", cam.outputs["View Distance"], PIXEL_ANGLE, x=x0 + 200, y=y - 2300), 1e-5,
              x=x0 + 350, y=y - 2300)
    half = m("MULTIPLY", i["width"], 0.5, x=x0, y=y - 1700)
    xb = m("FLOORED_MODULO", sp, i["pitch"], x=x0 + 150, y=y - 1800)
    centre2 = m("ADD", m("ADD", i["width"], gap, x=x0 + 150, y=y - 1950), half, x=x0 + 300, y=y - 1950)

    def ring(x, centre, xx, yy):
        """1 on a band round ``centre`` (m within a period, the neighbouring periods' too), a pixel's soft edge."""
        best = None
        for k, shift in enumerate((0.0, -1.0, 1.0)):
            c = centre if shift == 0.0 else m("ADD", centre, m("MULTIPLY", i["pitch"], shift, x=xx, y=yy - 120 * k),
                                              x=xx + 150, y=yy - 120 * k)
            dd = m("ABSOLUTE", m("SUBTRACT", x, c, x=xx + 300, y=yy - 120 * k), x=xx + 450, y=yy - 120 * k)
            one = m("ADD", m("DIVIDE", m("SUBTRACT", half, dd, x=xx + 600, y=yy - 120 * k), pixel,
                             x=xx + 750, y=yy - 120 * k), 0.5, x=xx + 900, y=yy - 120 * k, clamp=True)
            best = one if best is None else m("MAXIMUM", best, one, x=xx + 1050, y=yy - 120 * k)
        return best

    def both(x, yy):
        return m("MAXIMUM", ring(x, half, x0 + 300, yy),
                 m("MULTIPLY", ring(x, centre2, x0 + 300, yy - 400), pair, x=x0 + 1500, y=yy - 400),
                 x=x0 + 1650, y=yy - 100)

    _named(m("MULTIPLY", both(xb, y - 2000), has, x=x0 + 1800, y=y - 2100), NODE_PATTERN, "Bands")
    # drawn with ragged edges: the place along the cable moved by noise, more with wear
    rv = b.vmath("SCALE", dv.outputs[0], scale=40.0, x=x0 + 650, y=y - 1300)
    # (and a step per strand: the paint ends where a strand ends)
    wn2 = b.node("ShaderNodeTexWhiteNoise", x0 + 650, y - 1150)
    wn2.noise_dimensions = "1D"
    b.put(wn2.inputs["W"], m("ADD", strand, 0.5, x=x0 + 550, y=y - 1150))
    jag = m("ADD", m("MULTIPLY", m("SUBTRACT", b.noise(rv, 1.0, 3.0, x=x0 + 800, y=y - 1300), 0.5,
                                   x=x0 + 950, y=y - 1300), 1.4, x=x0 + 1050, y=y - 1300),
            m("MULTIPLY", m("SUBTRACT", wn2.outputs["Value"], 0.5, x=x0 + 800, y=y - 1150), 0.6,
              x=x0 + 950, y=y - 1150), x=x0 + 1100, y=y - 1250)
    rag = m("MULTIPLY", jag, m("ADD", m("MULTIPLY", pwear, 2.0 * float(d["rag"]) * 0.67, x=x0 + 800, y=y - 1500),
                               2.0 * float(d["rag"]) * 0.33, x=x0 + 950, y=y - 1500), x=x0 + 1150, y=y - 1300)
    drawn = both(m("ADD", xb, rag, x=x0 + 1250, y=y - 1300), y - 2800)
    # the paint is thinner in the grooves and smudged black: both with wear
    smear = b.noise(dv.outputs[0], 6.0, 5.0, x=x0 + 650, y=y - 3300)
    lo = m("SUBTRACT", 0.62, m("MULTIPLY", pwear, 0.18, x=x0 + 700, y=y - 3500), x=x0 + 850, y=y - 3500)
    smudge = m("MULTIPLY", b.map(smear, lo, m("ADD", lo, 0.12, x=x0 + 850, y=y - 3400), 0.0, 1.0,
                                 x=x0 + 1000, y=y - 3300),
               m("ADD", m("MULTIPLY", pwear, 0.8, x=x0 + 1000, y=y - 3600), 0.1, x=x0 + 1150, y=y - 3600),
               x=x0 + 1300, y=y - 3300, clamp=True)
    thin = m("MULTIPLY", m("MULTIPLY", valley, valley, x=x0 + 1650, y=y - 3000), pwear, x=x0 + 1800, y=y - 3000)
    keep = m("SUBTRACT", 1.0, m("MAXIMUM", smudge, thin, x=x0 + 1950, y=y - 3200), x=x0 + 2100, y=y - 3200)
    paint = _named(m("MULTIPLY", m("MULTIPLY", drawn, keep, x=x0 + 2250, y=y - 2900), has, x=x0 + 2400, y=y - 2900),
                   NODE_PAINT, "Paint")

    # ---- colour: the yarn (its strand's shade, the fibres light and dark, darker in the grooves), dust, the paint
    fib = m("ADD", m("MULTIPLY", m("SUBTRACT", fibre, 0.5, x=x0 + 1000, y=y - 450), 0.5, x=x0 + 1150, y=y - 450), 1.0,
            x=x0 + 1300, y=y - 450)
    groove = m("ADD", m("MULTIPLY", height, 0.45, x=x0 + 1650, y=y + 100), 0.55, x=x0 + 1800, y=y + 100)
    k = m("MULTIPLY", m("MULTIPLY", shade, fib, x=x0 + 1450, y=y + 300), groove, x=x0 + 1950, y=y + 200)
    yarn_c = b.vmath("SCALE", yc, scale=k, x=x0 + 2100, y=y + 200)
    yarn_col = b.mix("RGBA", dust, yarn_c, _linear(d["dust"]), x=x0 + 2300, y=y + 100)
    paint_c = b.vmath("SCALE", bc, scale=m("ADD", m("MULTIPLY", height, 0.25, x=x0 + 2100, y=y - 2700), 0.75,
                                           x=x0 + 2250, y=y - 2700), x=x0 + 2400, y=y - 2600)
    served = b.mix("RGBA", paint, yarn_col, paint_c, x=x0 + 2600, y=y)
    color = b.mix("RGBA", has, color, served, x=x0 + 2800, y=y)
    rough = b.mix("FLOAT", has, rough, b.mix("FLOAT", paint, float(d["yarn_roughness"]), float(d["paint_roughness"]),
                                             x=x0 + 2600, y=y - 250), x=x0 + 2800, y=y - 250)

    # ---- the relief: the strands' round backs and the fibres on them, in metres; faded below a few pixels
    fade = _fade(b, m("DIVIDE", ypitch, pixel, x=x0 + 1800, y=y - 1600), FADE_STRAND, x0 + 2000, y - 1600)
    relief = m("ADD", m("MULTIPLY", height, 0.85, x=x0 + 2000, y=y - 1400),
               m("MULTIPLY", fibre, 0.15, x=x0 + 2000, y=y - 1250), x=x0 + 2150, y=y - 1300)
    metres = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", relief, fade, x=x0 + 2300, y=y - 1300),
                             m("MULTIPLY", ypitch, float(d["strand_height"]), x=x0 + 2300, y=y - 1450),
                             x=x0 + 2450, y=y - 1300), has, x=x0 + 2600, y=y - 1300)
    bump = b.node("ShaderNodeBump", x0 + 2800, y - 1300, Strength=float(d["bump"]), Distance=1.0)
    b.put(bump.inputs["Height"], metres)
    if normal is not None:
        b.put(bump.inputs["Normal"], normal)
    return color, metallic, rough, bump.outputs["Normal"]


def apply(b, bsdf, spec: dict, color, metallic, rough, normal):
    """Put a cable look into a material that ``materials.build_nodes`` is building. ``spec``: the library entry's
    ``cable`` dict (``kind`` "POWER" | "ROPE" | "SERVED" and any key of ``DEFAULTS``); ``color``, ``metallic``, ``rough``,
    ``normal``: the material's look so far (sockets, values or None) – it stays where a mesh has no ``fr_cable``
    attribute. Returns the four the builder carries on with."""
    kind = kind_name(spec.get("kind", "POWER"))
    d = {**DEFAULTS[kind], **{k: v for k, v in spec.items() if k != "kind"}}
    if kind == "ROPE":
        return _rope(b, d, color, metallic, rough, normal)
    if kind == "SERVED":
        return _served_nodes(b, d, color, metallic, rough, normal)
    return _power(b, d, color, metallic, rough, normal)


def nodes_of(mat) -> dict:
    """The look's named nodes in a material: {name: node} (empty when the material has no cable look)."""
    nt = getattr(mat, "node_tree", None)
    if nt is None:
        return {}
    return {name: nt.nodes[name] for name in (NODE_ATTR, NODE_PAY, NODE_LOOK, NODE_PATTERN, NODE_WIRES, NODE_HAS,
                                                  NODE_YARN, NODE_PAINT)
            if name in nt.nodes}
