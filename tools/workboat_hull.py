"""An invented workboat hull for the test models (task 0234; generic, made up – never the demo ship's hull).

    Hull(...).solid()  one solid: transom at x = 0, a parallel body with a flat bottom and round bilges, a bow that
                    narrows and whose forefoot rises towards the stem; optionally a forecastle (the bow part's top
                    higher than the main deck) and a small deckhouse on it with a window band.

Used by tools/make_test_thrusters.py (a whole workboat), tools/make_test_sea.py and tools/make_test_moving.py (the
stern deck of a workboat, the bow and its deckhouse forward of the working deck). mm, Z up, x towards the bow.
The parallel body is a prism of one section, the bow a smooth loft through polygon sections (a ruled loft of the same
sections made the STEP file 3.5 x bigger; the smooth one meshes to ~29,000 triangles at Normal). The hull never goes
below ``bottom`` (the sets' water level is measured from the lowest point).
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from fresing_render.demo_model import geom as G  # noqa: E402

BILGE_STEPS = 4                     # straight pieces round each bilge
BOW_STATIONS = 7                    # sections from the end of the parallel body to the stem


def section(x: float, half: float, bottom: float, top: float, bilge: float, flare: float = 0.0) -> list:
    """A closed hull section at ``x``: (x, y, z) points, the same count for every section. ``half``: half breadth at
    the top; ``flare``: how much narrower the hull is at the bilge's top than at its top (sides lean out)."""
    hb = max(half - flare, 1.0)
    r = max(min(bilge, 0.95 * hb, 0.95 * (top - bottom)), 1.0)
    pts = [(x, -half, top)]
    for k in range(BILGE_STEPS + 1):            # port side: from the side down round the bilge to the bottom
        a = math.pi / 2 * k / BILGE_STEPS
        pts.append((x, -(hb - r) - r * math.cos(a), bottom + r - r * math.sin(a)))
    for k in range(BILGE_STEPS + 1):            # starboard: from the bottom up round the bilge
        a = math.pi / 2 * k / BILGE_STEPS
        pts.append((x, (hb - r) + r * math.sin(a), bottom + r - r * math.cos(a)))
    pts.append((x, half, top))
    return pts


def station(t: float, half: float, bottom: float, top: float, bilge: float, flare: float, stem_half: float,
            stem_rise: float) -> tuple:
    """The bow's section at ``t`` (0: end of the parallel body, 1: the stem) as (half breadth at the top, bottom,
    bilge radius, flare)."""
    h = stem_half + (half - stem_half) * math.sqrt(max(0.0, 1.0 - t ** 2.2))          # waterlines: full, then fine
    z0 = bottom + stem_rise * (top - bottom) * t ** 2.4                               # the forefoot rises
    return h, z0, bilge * (1.0 - 0.7 * t), flare * (1.0 - t) + 0.25 * h * t


class Hull:
    """The numbers of one hull (mm); ``solid()`` makes it, ``half_at(x, z)`` is its half breadth there."""

    def __init__(self, length: float, half: float, bottom: float, top: float, bow_start: float,
                 bilge: float = 800.0, flare: float = 150.0, stem_half: float = 120.0, stem_rise: float = 0.82,
                 bow_top: float | None = None):
        self.length, self.half, self.bottom, self.top, self.bow_start = length, half, bottom, top, bow_start
        self.bilge, self.flare, self.stem_half, self.stem_rise = bilge, flare, stem_half, stem_rise
        self.bow_top = top if bow_top is None else bow_top

    def _at(self, x: float) -> tuple:
        """(half breadth at the top, bottom, top, bilge radius, flare) of the section at ``x``."""
        if x <= self.bow_start:
            return self.half, self.bottom, self.top, self.bilge, self.flare
        t = min(1.0, (x - self.bow_start) / (self.length - self.bow_start))
        h, z0, r, fl = station(t, self.half, self.bottom, self.bow_top, self.bilge, self.flare, self.stem_half,
                               self.stem_rise)
        return h, z0, self.bow_top, r, fl

    def half_at(self, x: float, z: float) -> float:
        """The hull's half breadth at (x, z) (0 outside it): the side, or the bilge circle, of the section there."""
        h, z0, z1, bilge, flare = self._at(x)
        if not z0 <= z <= z1:
            return 0.0
        hb = max(h - flare, 1.0)
        r = max(min(bilge, 0.95 * hb, 0.95 * (z1 - z0)), 1.0)
        if z >= z0 + r:
            return hb + (h - hb) * (z - z0 - r) / max(z1 - z0 - r, 1e-9)
        dz = z0 + r - z
        return hb - r + math.sqrt(max(0.0, r * r - dz * dz))

    def solid(self):
        """One solid: transom at x = 0, the parallel body to ``bow_start``, the bow to the stem at ``length``; the bow
        part's top is ``bow_top`` (a forecastle when it is higher than the main deck ``top``)."""
        aft = G.loft([section(x, self.half, self.bottom, self.top, self.bilge, self.flare)
                      for x in (0.0, self.bow_start)])
        bow = []
        for i in range(BOW_STATIONS + 1):
            x = self.bow_start + i / BOW_STATIONS * (self.length - self.bow_start)
            h, z0, z1, r, fl = self._at(x if i else self.bow_start + 1e-9)
            bow.append(section(x, h, z0, z1, r, fl))
        return G.fuse(aft, G.loft(bow, ruled=False))


def deckhouse(x0: float, x1: float, half: float, z0: float, height: float, sill: float = 0.62, band: float = 0.24):
    """A deckhouse box x0..x1, y ±half, z0..z0 + height with a window band (``band`` of its height, its sill at
    ``sill``) set 80 into its front and sides, and a roof slightly wider than the house."""
    house = G.box(x0, -half, z0, x1 - x0, 2 * half, height)
    roof = G.box(x0 - 100.0, -half - 100.0, z0 + height, x1 - x0 + 200.0, 2 * half + 200.0, 120.0)
    zs, h = z0 + sill * height, band * height
    windows = [G.box(x1 - 80.0, -half + 300.0, zs, 200.0, 2 * half - 600.0, h)]
    for s in (1.0, -1.0):
        y = s * half - (80.0 if s > 0 else -80.0)
        windows.append(G.box(x0 + 400.0, min(y, s * half + 120.0 * s), zs, x1 - x0 - 800.0, 200.0, h))
    return G.cut(G.fuse(house, roof), *windows)
