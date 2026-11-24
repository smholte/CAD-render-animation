"""Render this view (task 0308): the camera that sees what a 3D view shows – no Blender here.

A 3D view's projection (``RegionView3D.window_matrix``) says how wide it looks: for a perspective view
``P[0][0] = 1 / tan(half the horizontal angle)`` and ``P[1][1]`` the same upwards; for an orthographic one
``P[0][0] = 2 / width`` and ``P[1][1] = 2 / height`` (metres). Reading the angle from the matrix, not from the view's
lens setting, gives exactly what is on screen (Blender's view doubles the lens' sensor and fits it to the longer side
of the view – the matrix already holds all that).

**The picture's frame** (the rule of this task): the same centre and the same zoom as the view; the picture's own
shape (the Picture's format) is fitted **around** the view, so nothing the view shows is cut off. A picture wider than
the view shows a little more at the sides, a taller one a little more above and below; a picture of the view's own
shape shows exactly the view.

``fit(window_matrix, perspective, width, height)`` -> the camera: ``{"type": "PERSP", "lens": mm}`` (36 mm sensor
fitted to the width) or ``{"type": "ORTHO", "ortho_scale": m}`` (fitted to the width), plus ``"tan"`` / ``"half"``
(the picture's half-angles as tangents, or half-sizes in metres: x, y) for the tests.
"""

from __future__ import annotations

SENSOR = 36.0           # mm: the camera's sensor width (fitted to the picture's width)


def fit_halves(view_x: float, view_y: float, aspect: float) -> tuple:
    """The picture's half-extents (x, y) round a view of half-extents ``view_x``, ``view_y``: the picture's shape
    ``aspect`` (width / height), as small as possible while it holds the whole view."""
    if view_x <= 0 or view_y <= 0 or aspect <= 0:
        raise ValueError("the view and the picture need a size")
    y = max(view_y, view_x / aspect)
    return aspect * y, y


def fit(window_matrix, perspective: bool, width: int, height: int) -> dict:
    """The camera for a picture ``width`` x ``height`` px that holds what a view with this projection shows."""
    p00, p11 = float(window_matrix[0][0]), float(window_matrix[1][1])
    if p00 <= 0 or p11 <= 0:
        raise ValueError("the view's projection has no size")
    aspect = width / height
    if perspective:
        tx, ty = fit_halves(1.0 / p00, 1.0 / p11, aspect)
        return {"type": "PERSP", "lens": SENSOR / 2.0 / tx, "tan": (tx, ty)}
    hx, hy = fit_halves(1.0 / p00, 1.0 / p11, aspect)
    return {"type": "ORTHO", "ortho_scale": 2.0 * hx, "half": (hx, hy)}


def ortho_back(clip_end: float) -> float:
    """How far behind the view's eye an orthographic camera stands: Blender's orthographic view sees from half its
    clip distance in front of the eye to half behind it; the camera then sees from 0 to the whole clip distance."""
    return 0.5 * clip_end
