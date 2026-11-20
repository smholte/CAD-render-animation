"""The quay the demo's ship moors at (task 0084; task 0247: the quay alone). Model coordinates: mm, x to the bow, y to
port, z up (waterline 0); the ship moors starboard side to.
"""

from __future__ import annotations

import numpy as np

from . import geom as g
from .geom import Asm, Part, T

CONCRETE = (0.62, 0.61, 0.58)
FENDER_BLACK = (0.06, 0.06, 0.06)
DARK = (0.13, 0.13, 0.14)


def quay(x0: float, x1: float, y_edge: float, depth: float, z_top: float) -> Asm:
    """A quay along x (model coordinates): concrete slab from y_edge outwards (-y) by ``depth``, top at z_top,
    fenders on its face, bollards near the edge."""
    a = Asm("QUAY")
    a.add(Part("QUAY SLAB", g.fuse(g.box(x0, y_edge - depth, -6000.0, x1 - x0, depth, z_top + 6000.0),
                                   g.box(x0, y_edge - 400.0, z_top, x1 - x0, 400.0, 250.0)), CONCRETE))
    fender = Part("QUAY FENDER", g.fuse(g.cyl(700.0, 2400.0, (0, 0, 0), (0, 0, 1)),
                                        g.box(-300, -900, 400, 600, 300, 1600)), FENDER_BLACK)
    bollard = Part("BOLLARD", g.fuse(g.cyl(220.0, 600.0, (0, 0, 0)), g.cyl(320.0, 120.0, (0, 0, 600)),
                                     g.box(-400, -400, 0, 800, 800, 40)), DARK)
    for x in np.arange(x0 + 6000.0, x1 - 3000.0, 16000.0):
        a.add(fender, T(x, y_edge + 700.0, z_top - 3200.0))
        a.add(bollard, T(x + 4000.0, y_edge - 1200.0, z_top))
    return a
