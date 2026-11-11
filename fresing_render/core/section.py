"""Cutaway / section view (task 0086): where a new cut goes, and the words the panel shows. No Blender here.

A cut is a plane (it takes away the side its arrow points to) or a box (it takes away what is inside it: a corner or
a quarter of the model). A new cut goes through the middle of what it cuts and takes away the side that faces the
camera, so the inside shows at once.
"""

from __future__ import annotations

from .words import plural

MARGIN = 0.05                 # a box reaches this far (share of the model's size) beyond the parts it cuts
DEFAULT_COLOR = (0.62, 0.012, 0.012)    # the cap colour: a strong red (linear RGB, about #CC1B1B on screen)
HATCH_SPACING = 0.01          # 10 mm between hatch lines


def horizontal_axis(view: tuple[float, float, float]) -> tuple[float, float, float]:
    """The world axis (±X or ±Y) nearest to the horizontal part of ``view`` (from the model towards the camera)."""
    x, y = float(view[0]), float(view[1])
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return (0.0, -1.0, 0.0)              # straight down from above: the front (Blender's front view looks along +Y)
    if abs(x) > abs(y):
        return (1.0 if x > 0 else -1.0, 0.0, 0.0)
    return (0.0, 1.0 if y > 0 else -1.0, 0.0)


def plane_default(bmin, bmax, view) -> tuple[tuple, tuple]:
    """(centre, normal) of a new plane cut: through the middle of the box ``bmin`` … ``bmax``, taking away the half
    that faces the camera (``view`` points from the model towards the camera)."""
    centre = tuple((float(a) + float(b)) / 2.0 for a, b in zip(bmin, bmax))
    return centre, horizontal_axis(view)


def box_default(bmin, bmax, view, margin: float = MARGIN) -> tuple[tuple, tuple]:
    """(centre, size) of a new box cut: the quarter of the model that faces the camera, the full height, reaching
    ``margin`` x the model's size beyond it on the three outer sides."""
    lo = [float(a) for a in bmin]
    hi = [float(b) for b in bmax]
    size = max(max(h - l for l, h in zip(lo, hi)), 1e-3)
    pad = margin * size
    mid = [(l + h) / 2.0 for l, h in zip(lo, hi)]
    x, y = float(view[0]), float(view[1])
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        x, y = 1.0, -1.0
    sx = 1.0 if x >= 0 else -1.0
    sy = 1.0 if y >= 0 else -1.0
    centre, extent = [], []
    for i, s in enumerate((sx, sy)):
        edge = (hi[i] + pad) if s > 0 else (lo[i] - pad)
        centre.append((mid[i] + edge) / 2.0)
        extent.append(abs(edge - mid[i]))
    centre.append(mid[2])
    extent.append(hi[2] - lo[2] + 2 * pad)
    return tuple(centre), tuple(max(e, 1e-3) for e in extent)


def status(total: int, on: int) -> str:
    """The panel header: '2 cuts · 1 on' ('' with no cuts)."""
    if total <= 0:
        return ""
    if on == 0:
        return f"{plural(total, 'cut')} · off"
    return f"{plural(total, 'cut')} · {on} on"


def target_label(kind: str, name: str) -> str:
    if kind == "MODEL":
        return f"Whole model {name}".strip()
    if kind == "GROUP":
        return f"Group {name}"
    return name
