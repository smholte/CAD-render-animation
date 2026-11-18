"""The load of a lifting plan (task 0201, Lifting lane L4): mass and centre of gravity – plain Python, no Blender.

* ``solid(points, triangles)``: a closed surface's volume and centroid (signed tetrahedra from the origin). Whether it
  is closed is tested by moving the origin: a closed surface gives the same volume from any point, an open one does
  not. A part that is not closed falls back to its box (the Blender side names it).
* ``DENSITY``: kg/m³ per material of the app's looks (``core/materials_lib``): a first guess, marked "estimate".
* ``combine``: masses and centroids -> the whole load's mass and CoG.
* ``gross``: the gross load as the panel sums it – load x contingency + rigging + hook block (unless the chart
  includes it).

Units: m, kg, m³ (the scene's units).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

STEEL = 7850.0
# kg/m³ by the look's material id; a look not named here counts as steel (most painted parts are)
DENSITY = {
    "aluminium_machined": 2700.0, "aluminium_anodized": 2700.0, "aluminium_anodized_color": 2700.0,
    "aluminium_anodized_black": 2700.0, "aluminium_profile": 2700.0, "aluminium_sawn": 2700.0,
    "cast_iron": 7200.0, "cast_iron_painted": 7200.0, "copper": 8960.0, "brass": 8500.0, "bronze": 8800.0,
    "zinc_diecast": 6700.0, "rubber_black": 1200.0, "belt_rubber": 1200.0, "plastic_gloss": 1200.0,
    "plastic_matte": 1200.0, "pom_white": 1410.0, "pom_black": 1410.0, "glass_clear": 2500.0, "glass_tinted": 2500.0,
    "polycarbonate_clear": 1200.0, "acrylic_frosted": 1190.0, "foam": 30.0, "felt": 300.0, "wood": 600.0,
    "concrete": 2400.0, "cable_power": 2500.0, "cable_black": 2500.0, "cable_served": 2500.0, "wire_rope": 5500.0,
    "mannequin_matte": 1000.0, "emission_light": 2500.0,
}
CONTINGENCY = (1.0, 1.3)        # the study's range of a weight contingency factor (0180 section 3, C1)
SOURCES = {"WEIGHED": "weighed", "DRAWING": "from the drawing", "ESTIMATE": "estimate"}
CLOSED_TOL = 1e-4               # relative change of the volume when the origin moves: above it, not closed


def density_of(material: str) -> float:
    return DENSITY.get(material or "", STEEL)


@dataclass
class Solid:
    volume: float                 # m³ (> 0)
    centroid: np.ndarray          # (3,) in the points' frame
    closed: bool


def solid(points, triangles) -> Solid:
    """Volume and centroid of a triangle surface (points (n, 3), triangles (m, 3) indices). The sign of the faces'
    winding does not matter (a mesh turned inside out gives the same). ``closed`` False: an open surface – the
    numbers are not a volume."""
    P = np.asarray(points, float).reshape(-1, 3)
    T = np.asarray(triangles, np.int64).reshape(-1, 3)
    if len(P) == 0 or len(T) == 0:
        return Solid(0.0, np.zeros(3), False)
    lo, hi = P.min(axis=0), P.max(axis=0)
    o = 0.5 * (lo + hi)
    size = float(np.linalg.norm(hi - lo)) or 1.0

    def signed(origin):
        a, b, c = P[T[:, 0]] - origin, P[T[:, 1]] - origin, P[T[:, 2]] - origin
        v6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        vol = float(v6.sum()) / 6.0
        cen = ((a + b + c) * v6[:, None]).sum(axis=0) / 24.0
        return vol, cen

    vol, cen = signed(o)
    vol2, _ = signed(o + np.array([0.37, -0.61, 0.73]) * size)
    closed = abs(vol) > 0 and abs(vol2 - vol) <= CLOSED_TOL * abs(vol)
    if abs(vol) < 1e-18:
        return Solid(0.0, o, False)
    return Solid(abs(vol), o + cen / vol, bool(closed))


def box_solid(lo, hi) -> Solid:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    d = np.maximum(hi - lo, 0.0)
    return Solid(float(d[0] * d[1] * d[2]), 0.5 * (lo + hi), True)


def combine(items) -> tuple[float, np.ndarray]:
    """(total mass, CoG) of (mass, point) items. No mass: (0, the points' mean)."""
    items = [(float(m), np.asarray(p, float)) for m, p in items]
    if not items:
        return 0.0, np.zeros(3)
    total = sum(m for m, _ in items)
    if total <= 0:
        return 0.0, np.mean([p for _, p in items], axis=0)
    return total, sum(m * p for m, p in items) / total


@dataclass
class Gross:
    load: float           # kg, as entered / worked out
    contingency: float
    factored: float       # load x contingency
    rigging: float        # kg (0 until the rigging task, L5)
    hook_block: float     # kg, added (0 when the chart includes it)
    total: float          # kg


def gross(load: float, contingency: float = 1.0, hook_block: float = 0.0, chart_includes_block: bool = False,
          rigging: float = 0.0) -> Gross:
    """The gross load the crane use is worked out with: load x contingency + rigging + hook block (unless the chart
    includes it) – the same sum as ``lifting.crane_use`` (with the factored load as its load)."""
    f = max(0.0, load) * max(0.0, contingency)
    hb = 0.0 if chart_includes_block else max(0.0, hook_block)
    return Gross(load=load, contingency=contingency, factored=f, rigging=rigging, hook_block=hb,
                 total=f + rigging + hb)
