"""The looks of a weld (task 0319): the bead and its heat zone. Shader nodes only – no pictures, no scripts, no drivers –
so they work with "Auto Run Python Scripts" off, in Cycles and EEVEE and in the render queue.

The contract with the geometry side (``blender/welds.py``, ``core/welds.py``)
---------------------------------------------------------------------------
* The bead object's UV map ``fr_weld``: u = metres along the seam, v = 0 at the toe on the first part … 1 at the toe
  on the second.
* The heat-zone object's UV map ``fr_weld``: u = metres along the seam, v = metres from the bead's toe out over the part;
  its UV map ``fr_weld_end``: (start, end) of the bead piece in metres along the seam, so the tint fades out over its
  last ~0.6 × width at an open seam's ends (a closed seam: -1000, 1000).

What is drawn
-------------
* **Ripples**: ``phase = u / pitch − chevron · |2v − 1|²`` – lines across the bead bent back at its sides (the weld
  pool's trailing edge); the height ``(1 − fract(phase))^0.6`` is a bump. Pitch per process (``core.welds.RIPPLE``):
  TIG fine, MAG even, MIG aluminium wide with a strong bend ("stacked coins"), stick coarse. Ground flush: none.
* **Bead colour**: steel MAG grey-blue oxide, mottled; stick darker and rougher; stainless TIG silver in the middle,
  straw → purple → blue towards the toes (pickled: matt silver); aluminium bright, MIG a little greyer.
* **Heat zone** (a strip on each part beside the bead, see-through where nothing is drawn): stainless straw → purple →
  blue bands (study 0270 #21), steel a narrow blue-grey oxide, MIG aluminium its sooty band, TIG aluminium the white
  cleaned band; spatter (dots) for MAG / stick when asked; rust and paint wear (below).
* **Rust** (``core.welds.rust_of``): red-brown patches on a bare carbon-steel bead and heat zone; on painted welds only
  at the toes where wear took the paint off; a faint tea stain on unpickled stainless; never on aluminium.
* **Painted**: the bead takes a copy of the painted part's own material (colour, wear, the paint scheme) with the
  ripples put into its normal – they show through the paint – and bare / rusty spots at the toes with Wear
  (``painted``; ``welds.sync_paint`` makes the copy again when the part's look changes).
"""

from __future__ import annotations

import hashlib
import json

import bpy

from ..core import welds as core
from .materials import _Nodes

UV = "fr_weld"
UV_END = "fr_weld_end"
PREFIX = "FR weld "
TAG = "fr_weld_look"           # on a weld material: the JSON of its look (the same look = the same material)
SRC = "fr_weld_src"            # on a painted copy: the source material's name and what it looked like
LOOK_VERSION = 3                # 3: task 0318 – the app's one rust look (blender/rust.py)

CHEVRON = {"MAG": 0.8, "TIG": 0.55, "MIG": 1.4, "STICK": 0.9}


def _lin(c):
    return (*c, 1.0) if len(c) == 3 else tuple(c)


def _name(kind: str, look: dict) -> str:
    h = hashlib.md5(json.dumps(look, sort_keys=True).encode()).hexdigest()[:8]
    return f"{PREFIX}{kind} {h}"


def _new(name: str):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:  # noqa: BLE001 - always on in 5.x
        pass
    mat.node_tree.nodes.clear()
    return mat


def _uv(b: _Nodes, name: str = UV):
    n = b.node("ShaderNodeUVMap", -2000, 300 if name == UV else 0)
    n.uv_map = name
    s = b.node("ShaderNodeSeparateXYZ", -1850, 300 if name == UV else 0)
    b.put(s.inputs[0], n.outputs["UV"])
    return s.outputs[0], s.outputs[1]


def _ramp(b: _Nodes, fac, stops, x=-600.0, y=0.0):
    r = b.node("ShaderNodeValToRGB", x, y)
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0][0], _lin(stops[0][1])
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = _lin(col)
    b.put(r.inputs["Fac"], fac)
    return r.outputs["Color"]


def _rust_mask(b: _Nodes, amount: float, scale: float = 260.0, y: float = -900.0):
    """0 … 1 patches covering about ``amount`` of the surface (large blotches broken up by fine pits)."""
    n = b.noise(None, scale, 5.0, x=-1400, y=y)
    fine = b.noise(None, scale * 6.0, 3.0, x=-1400, y=y - 150)
    n = b.math("ADD", b.math("MULTIPLY", n, 0.75, x=-1300, y=y), b.math("MULTIPLY", fine, 0.25, x=-1300, y=y - 150),
               x=-1250, y=y)
    lo = 0.70 - 0.30 * amount
    return b.map(n, lo, lo + 0.06, 0.0, 0.92, x=-1200, y=y)


def _rust_color(b: _Nodes, y: float = -1050.0):
    """Rust is not one orange: the app's one rust look (``blender/rust.py``, task 0318), the same as the group's Rust
    slider and the marine streaks."""
    from . import rust as rs
    return rs.color(b, 900.0, x=-1100, y=y)


def _ripple_height(b: _Nodes, u, v, pitch: float, chevron: float):
    across = b.math("ABSOLUTE", b.math("SUBTRACT", b.math("MULTIPLY", v, 2.0, x=-1700, y=500), 1.0, x=-1600, y=500),
                    x=-1500, y=500)
    bend = b.math("MULTIPLY", b.math("MULTIPLY", across, across, x=-1400, y=500), chevron, x=-1300, y=500)
    phase = b.math("SUBTRACT", b.math("DIVIDE", u, pitch, x=-1400, y=650), bend, x=-1200, y=600)
    r = b.math("FRACT", phase, x=-1050, y=600)
    h = b.math("POWER", b.math("SUBTRACT", 1.0, r, x=-900, y=600), 0.6, x=-750, y=600)
    return h, across


# ---------------------------------------------------------------------------
# the bead
# ---------------------------------------------------------------------------

def bead_look(metal: str, process: str, finish: str, pickled: bool, heat_tint: bool, rust: dict) -> dict:
    return {"v": LOOK_VERSION, "metal": metal, "process": process, "finish": finish, "pickled": bool(pickled),
            "tint": bool(heat_tint), "rust": round(float(rust.get("bead", 0.0)), 3),
            "tea": round(float(rust.get("tea", 0.0)), 3)}


def bead_material(look: dict):
    """The bead's own material (bare: as welded or ground flush)."""
    name = _name("bead", look)
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == json.dumps(look, sort_keys=True):
        return mat
    mat = _new(name)
    b = _Nodes(mat.node_tree)
    out = b.node("ShaderNodeOutputMaterial", 600, 0)
    bsdf = b.node("ShaderNodeBsdfPrincipled", 250, 0)
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    metal, process, finish = look["metal"], look["process"], look["finish"]
    u, v = _uv(b)
    pitch = core.RIPPLE.get(process, 0.0016)
    h, across = _ripple_height(b, u, v, pitch, CHEVRON.get(process, 0.8))
    mottle = b.noise(None, 400.0, 4.0, x=-1400, y=200)
    if finish == "GROUND":
        base = {"STAINLESS": (0.70, 0.70, 0.71), "ALUMINIUM": (0.86, 0.87, 0.88)}.get(metal, (0.60, 0.60, 0.61))
        color = b.mix("RGBA", b.map(mottle, 0.3, 0.7, 0.0, 0.25, x=-900, y=200), _lin(base),
                      (0.5, 0.5, 0.52, 1.0), x=-600, y=200)
        metallic, rough = 1.0, b.map(mottle, 0.0, 1.0, 0.26, 0.38, x=-600, y=0)
        normal = None
    else:
        if metal == "STAINLESS":
            if look["pickled"] or not look["tint"]:
                color = _ramp(b, mottle, [(0.0, (0.50, 0.50, 0.51)), (1.0, (0.62, 0.62, 0.63))], y=200)
                rough = 0.42 if look["pickled"] else 0.32
            else:
                color = _ramp(b, b.math("ADD", across, b.math("MULTIPLY", mottle, 0.15, x=-900, y=50), x=-800, y=150),
                              [(0.0, (0.55, 0.55, 0.56)), (0.55, (0.60, 0.53, 0.36)), (0.78, (0.40, 0.22, 0.38)),
                               (0.95, (0.20, 0.24, 0.45))], y=200)
                rough = 0.3
            metallic = 1.0
        elif metal == "ALUMINIUM":
            c = (0.80, 0.81, 0.83) if process == "MIG" else (0.86, 0.87, 0.88)
            color = _ramp(b, mottle, [(0.0, tuple(x * 0.88 for x in c)), (1.0, c)], y=200)
            metallic, rough = 1.0, 0.33 if process == "MIG" else 0.26
        else:
            if process == "STICK":
                stops = [(0.0, (0.10, 0.10, 0.11)), (0.6, (0.17, 0.16, 0.16)), (1.0, (0.24, 0.22, 0.20))]
                rough = 0.62
            else:
                stops = [(0.0, (0.13, 0.14, 0.16)), (0.55, (0.24, 0.25, 0.28)), (1.0, (0.20, 0.24, 0.40))]
                rough = 0.45
            color = _ramp(b, mottle, stops, y=200)
            metallic = 0.7
        normal = b.node("ShaderNodeBump", 0, -400, Strength=0.55, Distance=pitch * 0.18)
        b.put(normal.inputs["Height"], h)
        normal = normal.outputs["Normal"]
    if look.get("tea", 0.0) > 0:
        m = _rust_mask(b, look["tea"], 120.0, y=-700)
        color = b.mix("RGBA", b.math("MULTIPLY", m, 0.5, x=-500, y=-700), color, (0.45, 0.33, 0.20, 1.0), x=-300,
                      y=-700)
    if look.get("rust", 0.0) > 0:
        m = _rust_mask(b, look["rust"])
        color = b.mix("RGBA", m, color, _rust_color(b), x=-300, y=-900)
        metallic = b.mix("FLOAT", m, metallic, 0.0, x=-300, y=-1050)
        rough = b.mix("FLOAT", m, rough, 0.88, x=-300, y=-1200)
    b.put(bsdf.inputs["Base Color"], color)
    b.put(bsdf.inputs["Metallic"], metallic)
    b.put(bsdf.inputs["Roughness"], rough)
    if normal is not None:
        mat.node_tree.links.new(normal, bsdf.inputs["Normal"])
    mat.diffuse_color = (0.3, 0.3, 0.32, 1.0) if metal == "STEEL" else (0.7, 0.7, 0.72, 1.0)
    mat.metallic, mat.roughness = 0.8, 0.4
    mat[TAG] = json.dumps(look, sort_keys=True)
    return mat


# ---------------------------------------------------------------------------
# the heat zone
# ---------------------------------------------------------------------------

def heat_look(metal: str, process: str, finish: str, pickled: bool, heat_tint: bool, spatter: bool, rust: dict,
              width: float, wear: float = 0.0) -> dict:
    return {"v": LOOK_VERSION, "metal": metal, "process": process, "finish": finish, "pickled": bool(pickled),
            "tint": bool(heat_tint), "spatter": bool(spatter), "rust": round(float(rust.get("heat", 0.0)), 3),
            "toes": round(float(rust.get("toes", 0.0)), 3), "wear": round(float(wear), 3),
            "w": round(float(width), 5)}


def heat_material(look: dict):
    name = _name("heat", look)
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == json.dumps(look, sort_keys=True):
        return mat
    mat = _new(name)
    nt = mat.node_tree
    b = _Nodes(nt)
    out = b.node("ShaderNodeOutputMaterial", 800, 0)
    bsdf = b.node("ShaderNodeBsdfPrincipled", 250, 0)
    clear = b.node("ShaderNodeBsdfTransparent", 250, -300)
    mix = b.node("ShaderNodeMixShader", 550, 0)
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    metal, process, finish = look["metal"], look["process"], look["finish"]
    W = max(look["w"], 1e-4)
    u, v = _uv(b)
    e0, e1 = _uv(b, UV_END)
    f = b.math("DIVIDE", v, W, x=-1600, y=300)
    wob = b.math("MULTIPLY", b.noise(None, 1.0 / 0.008, 3.0, x=-1700, y=100), 0.18, x=-1550, y=100)
    fw = b.math("ADD", f, wob, x=-1450, y=200)
    d_end = b.math("MINIMUM", b.math("SUBTRACT", u, e0, x=-1600, y=-100), b.math("SUBTRACT", e1, u, x=-1600, y=-200),
                   x=-1450, y=-150)
    fade = b.map(d_end, 0.0, 0.6 * W, 0.0, 1.0, x=-1300, y=-150)
    cover = 0.0
    color = (0.5, 0.5, 0.5, 1.0)
    metallic, rough = 1.0, 0.45
    if finish == "PAINTED":
        cover = 0.0                                        # the paint covers the zone: only worn toes show
    elif finish == "GROUND":
        cover = b.map(fw, 0.55, 0.85, 0.9, 0.0, x=-1100, y=300)
        color = (0.62, 0.62, 0.63, 1.0) if metal == "STEEL" else (0.75, 0.75, 0.76, 1.0)
        rough = 0.3
    elif look["tint"]:
        if metal == "STAINLESS" and not look["pickled"]:
            color = _ramp(b, fw, [(0.0, (0.12, 0.12, 0.13)), (0.12, (0.18, 0.22, 0.42)), (0.3, (0.35, 0.18, 0.38)),
                                  (0.5, (0.55, 0.32, 0.16)), (0.72, (0.78, 0.62, 0.33)), (1.0, (0.72, 0.72, 0.73))],
                          y=300)
            cover = b.map(fw, 0.7, 1.0, 1.0, 0.0, x=-1100, y=300)
            rough = b.map(fw, 0.0, 1.0, 0.45, 0.3, x=-800, y=0)
        elif metal == "STAINLESS":                         # pickled: a dull band only
            color, rough = (0.60, 0.60, 0.61, 1.0), 0.55
            cover = b.map(fw, 0.3, 0.7, 0.45, 0.0, x=-1100, y=300)
        elif metal == "ALUMINIUM" and process == "MIG":
            soot = b.noise(None, 90.0, 3.0, x=-1300, y=450)
            band = b.math("MULTIPLY", b.map(fw, 0.08, 0.25, 0.0, 1.0, x=-1100, y=450),
                          b.map(fw, 0.55, 0.85, 1.0, 0.0, x=-1100, y=350), x=-950, y=400)
            cover = b.math("MULTIPLY", band, b.map(soot, 0.35, 0.65, 0.4, 0.95, x=-950, y=500), x=-800, y=400)
            color, metallic, rough = (0.05, 0.05, 0.055, 1.0), 0.0, 0.85
        elif metal == "ALUMINIUM":                         # TIG: the white cleaned band
            color, metallic, rough = (0.86, 0.86, 0.87, 1.0), 0.6, 0.7
            cover = b.map(fw, 0.2, 0.5, 0.55, 0.0, x=-1100, y=300)
        else:                                              # steel: blue-grey oxide, a straw edge
            color = _ramp(b, fw, [(0.0, (0.10, 0.11, 0.13)), (0.35, (0.16, 0.20, 0.34)), (0.7, (0.42, 0.36, 0.24)),
                                  (1.0, (0.5, 0.5, 0.5))], y=300)
            cover = b.map(fw, 0.45, 0.9, 0.85, 0.0, x=-1100, y=300)
            metallic, rough = 0.6, 0.5
    if look["spatter"] and finish != "PAINTED" and metal != "STAINLESS":
        vor = b.node("ShaderNodeTexVoronoi", -1400, 700)
        b.put(vor.inputs["Vector"], b.coord())
        b.put(vor.inputs["Scale"], 520.0)
        dots = b.math("MULTIPLY", b.map(vor.outputs["Distance"], 0.12, 0.2, 1.0, 0.0, x=-1200, y=700),
                      b.map(fw, 0.0, 1.6, 1.0, 0.0, x=-1200, y=600), x=-1050, y=650)
        sel = b.map(b.noise(None, 50.0, 1.0, x=-1200, y=800), 0.45, 0.55, 0.0, 1.0, x=-1050, y=800)
        dots = b.math("MULTIPLY", dots, sel, x=-900, y=700)
        color = b.mix("RGBA", dots, color, (0.07, 0.07, 0.075, 1.0), x=-600, y=700)
        cover = b.math("MAXIMUM", cover, dots, x=-600, y=600)
    wear = look.get("toes", 0.0) if finish == "PAINTED" else look.get("rust", 0.0)
    if wear > 0:
        m = b.math("MULTIPLY", _rust_mask(b, wear), b.map(fw, 0.0, 0.6 if finish == "PAINTED" else 1.0, 1.0, 0.0,
                                                          x=-1100, y=-1000), x=-950, y=-950)
        color = b.mix("RGBA", m, color, _rust_color(b), x=-300, y=-900)
        metallic = b.mix("FLOAT", m, metallic, 0.0, x=-300, y=-1050)
        rough = b.mix("FLOAT", m, rough, 0.9, x=-300, y=-1200)
        cover = b.math("MAXIMUM", cover, m, x=-300, y=-750)
    alpha = b.math("MULTIPLY", cover, fade, x=300, y=200, clamp=True) if not isinstance(cover, float) else cover
    b.put(mix.inputs[0], alpha)
    b.put(bsdf.inputs["Base Color"], color)
    b.put(bsdf.inputs["Metallic"], metallic)
    b.put(bsdf.inputs["Roughness"], rough)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    mat.diffuse_color = (0.4, 0.4, 0.42, 0.0)
    mat[TAG] = json.dumps(look, sort_keys=True)
    return mat


# ---------------------------------------------------------------------------
# painted: the part's own paint over the bead
# ---------------------------------------------------------------------------

def source_signature(src) -> str:
    if src is None:
        return ""
    return json.dumps([src.name, src.get("fr_material", ""), src.get("fr_color", ""),
                       round(float(src.get("fr_wear", 0.0)), 4), int(src.get("fr_look_version", 0)),
                       bool(src.get("fr_weather_wrap")), bool(src.get("fr_section_wrap")),
                       bool(src.get("fr_fade_wrap")), len(src.node_tree.nodes) if src.node_tree else 0])


def _principled_of(nt):
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            return n
    return None


def painted(src, process: str, rust: dict):
    """A copy of the painted part's material with the ripples in its normal and worn, rusty toes."""
    look = {"v": LOOK_VERSION, "process": process, "toes": round(float(rust.get("toes", 0.0)), 3)}
    sig = source_signature(src)
    name = f"{PREFIX}paint {src.name if src is not None else 'none'} " + \
        hashlib.md5(json.dumps(look, sort_keys=True).encode()).hexdigest()[:6]
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(SRC) == sig and mat.get(TAG) == json.dumps(look, sort_keys=True):
        return mat
    if src is None or src.node_tree is None:
        return bead_material(bead_look("STEEL", process, "AS_WELDED", False, False, {}))
    new = src.copy()
    if mat is not None:
        mat.user_remap(new)
        bpy.data.materials.remove(mat)
    new.name = name
    for k in ("fr_material", "fr_color", "fr_wear"):     # the copy is not a group's material: never rebuilt as one
        if k in new:
            new["fr_src_" + k[3:]] = new[k]
            del new[k]
    nt = new.node_tree
    bsdf = _principled_of(nt)
    if bsdf is not None:
        b = _Nodes(nt)
        u, v = _uv(b)
        pitch = core.RIPPLE.get(process, 0.0016)
        h, across = _ripple_height(b, u, v, pitch, CHEVRON.get(process, 0.8))
        bump = b.node("ShaderNodeBump", -200, -600, Strength=0.45, Distance=pitch * 0.18)
        b.put(bump.inputs["Height"], h)
        sock = bsdf.inputs["Normal"]
        if sock.is_linked:
            nt.links.new(sock.links[0].from_socket, bump.inputs["Normal"])
        nt.links.new(bump.outputs["Normal"], sock)
        if look["toes"] > 0:
            toe = b.map(across, 0.72, 0.98, 0.0, 1.0, x=-900, y=-1300)
            m = b.math("MULTIPLY", toe, _rust_mask(b, look["toes"], 300.0, y=-1400), x=-700, y=-1300)
            for sname, val in (("Base Color", _rust_color(b, -1500)), ("Metallic", 0.0), ("Roughness", 0.85)):
                s = bsdf.inputs[sname]
                cur = s.links[0].from_socket if s.is_linked else (tuple(s.default_value) if sname == "Base Color"
                                                                  else float(s.default_value))
                kind = "RGBA" if sname == "Base Color" else "FLOAT"
                nt.links.new(b.mix(kind, m, cur, val, x=-100, y=-1300), s)
    new[SRC] = sig
    new[TAG] = json.dumps(look, sort_keys=True)
    return new


def is_weld_material(mat) -> bool:
    return mat is not None and mat.name.startswith(PREFIX)


def unused_cleanup() -> int:
    """Remove weld materials nothing uses any more. Returns how many."""
    gone = [m for m in bpy.data.materials if is_weld_material(m) and m.users == 0]
    for m in gone:
        bpy.data.materials.remove(m)
    return len(gone)
