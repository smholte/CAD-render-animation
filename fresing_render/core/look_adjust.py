"""Adjust a look (task 0314): a few plain sliders per ready-made material – plain Python, no Blender.

The sliders are the group's ``adj_*`` settings (``blender/props.py``); the node group "FR adjust" in
``blender/look_adjust.py`` does in shader nodes what the functions here do in plain numbers (the tests compare them).
Colour, Wear, Rust and a finish's pattern size / direction are the group's own older settings and are not here.

**Safe ranges**: a slider can never make a look black or glowing – roughness stays 0.03 … 0.9, metallic 0 … 1, dirt
darkens at most to a dark brown, relief is at most twice the look's own.

**The cost of a look** (``slower``): ``fresing_render/data/look_costs.json``, written by ``tools/look_costs.py`` – every
library material rendered on the picker's swatch with Cycles on the processor at fixed samples, its time divided by
plain satin paint's. A look at ``SLOWER`` x or more gets the picker's "slower" badge.
"""

from __future__ import annotations

import json
import math
import os

from . import materials_lib as ML

#: name -> (label, min, max, default, tooltip); the order is the order in the picker
SLIDERS = {
    "shine": ("Shine", -1.0, 1.0, 0.0,
              "Duller (left) or shinier (right) than the material as made. In the middle: as made. All the way "
              "right is a mirror-like shine, all the way left a dull, matte surface"),
    "metal": ("Metal ↔ paint", -1.0, 1.0, 0.0,
              "Left: more like paint or plastic (the colour shows, reflections stay white). Right: more like bare "
              "metal (reflections take the colour). In the middle: as made"),
    "dirt": ("Dirt", 0.0, 1.0, 0.0,
             "Dust and grime in soft patches: the surface turns darker and duller. 0 = clean (as made)"),
    "relief": ("Relief", 0.0, 2.0, 1.0,
               "How strongly the surface's texture shows (brushing, peel, knurls, grain, the pattern of a finish): "
               "0 = smooth, 1 = as made, 2 = twice as deep"),
    "coat": ("Clear coat", 0.0, 1.0, 0.0,
             "A clear lacquer on top: a second, sharp reflection over the material. 0 = only the material's own coat"),
}
NAMES = tuple(SLIDERS)
DEFAULTS = {k: v[3] for k, v in SLIDERS.items()}
EPS = 1e-4

ROUGH_SHINY, ROUGH_DULL = 0.03, 0.9           # where Shine +1 / -1 take the roughness
DIRT_RGB = (0.045, 0.036, 0.027)              # linear: a dark brown grime
DIRT_SHARE = 0.85                             # the most a patch of Dirt 1 covers the colour
DIRT_ROUGH = 0.85                             # the roughness a full patch goes towards
DIRT_SCALE = 6.0                              # the patches' size (noise scale on the object's coordinates)
COAT_ROUGH = 0.05

SLOWER = 1.5                                  # time / plain paint at which the picker says "slower"
COSTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "look_costs.json")


def clean(values) -> dict:
    """Every slider, clamped to its range (missing or not a number: its default)."""
    out = {}
    src = values if isinstance(values, dict) else {}
    for k, (_l, lo, hi, d, _t) in SLIDERS.items():
        v = src.get(k, d)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
            v = d
        out[k] = min(max(float(v), lo), hi)
    return out


def changed(values) -> dict:
    """Only the sliders that are not at their default (what an own material's file keeps), rounded."""
    c = clean(values)
    return {k: round(v, 4) for k, v in c.items() if abs(v - DEFAULTS[k]) > EPS}


def is_default(values) -> bool:
    return not changed(values)


def key(values) -> str:
    """The values as a short text ("" = all at their default): stored on a material, compared by ``is_current``."""
    ch = changed(values)
    return ";".join(f"{k}={ch[k]:.4f}" for k in NAMES if k in ch)


def parse(text: str) -> dict:
    out = dict(DEFAULTS)
    for part in str(text or "").split(";"):
        k, _, v = part.partition("=")
        if k in SLIDERS:
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return clean(out)


def has_relief(spec: dict) -> bool:
    """The look has a texture in its surface (a normal) that Relief can change."""
    if any(spec.get(k) for k in ("bump", "peel", "finish", "cable", "marine", "toolmarks")):
        return True
    m = spec.get("marks")
    return bool(m and m.get("bump"))


def applies(material_id: str) -> tuple:
    """The sliders that mean something for a library material (in the picker's order)."""
    spec = ML.get(material_id)
    if spec.get("emission") or material_id in ("from_file", "blender_material"):
        return ()
    if spec.get("transmission"):
        return ("shine",)
    out = ["shine", "metal", "dirt"]
    if has_relief(spec):
        out.append("relief")
    out.append("coat")
    return tuple(out)


def effective(material_id: str, values) -> dict:
    """The values a look uses: the sliders that do not apply to it at their defaults."""
    use = applies(material_id)
    return {k: (v if k in use else DEFAULTS[k]) for k, v in clean(values).items()}


# ----- the formulas (the node group does the same) -----

def _toward(x: float, s: float, up: float, down: float) -> float:
    """``s`` > 0 moves x towards ``up`` by s, ``s`` < 0 towards ``down`` by -s."""
    t, u = max(s, 0.0), max(-s, 0.0)
    return x * (1.0 - t - u) + up * t + down * u


def roughness(r: float, shine: float, dirt_fac: float = 0.0) -> float:
    """``dirt_fac``: Dirt x the patch at this point (0 … 1)."""
    r1 = _toward(r, shine, ROUGH_SHINY, ROUGH_DULL)
    r1 = r1 + dirt_fac * (DIRT_ROUGH - r1)
    return min(max(r1, ROUGH_SHINY), 1.0)


def metallic(m: float, metal: float, dirt_fac: float = 0.0) -> float:
    return min(max(_toward(m, metal, 1.0, 0.0) * (1.0 - dirt_fac), 0.0), 1.0)


def colour(rgb, dirt_fac: float) -> tuple:
    f = min(max(dirt_fac * DIRT_SHARE, 0.0), 1.0)
    return tuple(c * (1.0 - f) + d * f for c, d in zip(rgb, DIRT_RGB))


def coat(c0: float, c: float) -> float:
    return max(float(c0), float(c))


def viewport(spec_roughness: float, spec_metallic: float, values) -> tuple:
    """(roughness, metallic) for Blender's solid view of a group's material."""
    v = clean(values)
    return roughness(spec_roughness, v["shine"]), metallic(spec_metallic, v["metal"])


# ----- the cost of each look -----

_COSTS: dict = {}


def costs(path: str = COSTS) -> dict:
    """{"looks": {material id: time / plain paint}, "machine", "samples", "size", "base_seconds", "measured"}."""
    if path not in _COSTS:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        _COSTS[path] = data if isinstance(data, dict) else {}
    return _COSTS[path]


def cost(material_id: str) -> float | None:
    v = costs().get("looks", {}).get(material_id)
    return float(v) if isinstance(v, (int, float)) else None


def slower(material_id: str) -> bool:
    c = cost(material_id)
    return c is not None and c >= SLOWER


def cost_text(material_id: str) -> str:
    """A plain line for the picker: "" for a look about as fast as plain paint."""
    c = cost(material_id)
    if c is None or c < SLOWER:
        return ""
    return f"Slower to render: about {c:.1f} x the time of plain paint"
