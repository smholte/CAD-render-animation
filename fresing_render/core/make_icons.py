"""The large icons of Make (task 0308): one drawing per output, as triangles – no Blender here.

**Why triangles.** Blender 5.2.3 draws every ordinary icon at 16 px, however tall or wide its button is (measured in
task 0308: ``scale_y`` 1.0 / 1.5 / 2.0, ``scale_x``, picture icons from ``bpy.utils.previews`` and expanded enum
rows all gave the same 16 px; ``template_icon(scale=)`` and ``template_icon_view`` draw larger but are a label and a
drop-down, not a button). Only a **geometry icon** – triangles handed to ``bpy.app.icons.new_triangles``, the kind
Blender's own toolbar uses – is drawn larger in a button. So each output's icon is drawn here from simple shapes
(rectangles, rings, polygons, thick lines) on a grid of 0 … 255, y up, and ``blender/make_icons.py`` hands the
triangles to Blender.

``icon(key)`` -> (coords, colours): ``coords`` = bytes, 6 per triangle (x, y of each corner), ``colours`` = bytes,
12 per triangle (RGBA of each corner). ``KEYS`` = the drawings there are.
"""

from __future__ import annotations

import math

SIZE = 255                     # the grid: 0 … 255 both ways, y up
INK = (225, 225, 225, 255)     # Blender's icon grey on the dark theme
ACCENT = (98, 160, 230, 255)   # one blue detail per icon (Fresing's blue, lighter for the dark panel)
FILL = 0.74                    # the drawings are shrunk to this share (towards the left edge, where Blender starts the
LEFT = 6                       # icon, and round the middle upwards): a button about as wide as the icon – a narrow
#                                side panel, a large UI scale – still shows it whole (measured in task 0308)

Tri = tuple  # ((x, y), (x, y), (x, y), rgba)


# ---------------------------------------------------------------------------
# shapes -> triangles
# ---------------------------------------------------------------------------

def rect(x0, y0, x1, y1, col=INK) -> list:
    return [((x0, y0), (x1, y0), (x1, y1), col), ((x0, y0), (x1, y1), (x0, y1), col)]


def frame(x0, y0, x1, y1, t, col=INK) -> list:
    """A rectangle's outline, ``t`` thick (inside the rectangle)."""
    return (rect(x0, y0, x1, y0 + t, col) + rect(x0, y1 - t, x1, y1, col)
            + rect(x0, y0 + t, x0 + t, y1 - t, col) + rect(x1 - t, y0 + t, x1, y1 - t, col))


def poly(points, col=INK) -> list:
    """A convex polygon (a fan from its first corner)."""
    return [(points[0], points[i], points[i + 1], col) for i in range(1, len(points) - 1)]


def circle_points(cx, cy, rx, ry=None, n=24, a0=0.0, a1=2 * math.pi) -> list:
    ry = rx if ry is None else ry
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def disc(cx, cy, r, col=INK, n=24) -> list:
    return poly(circle_points(cx, cy, r, n=n)[:-1], col)


def ring(cx, cy, r, t, col=INK, ry=None, n=32, a0=0.0, a1=2 * math.pi) -> list:
    """A ring (or an arc of one from ``a0`` to ``a1``), ``t`` thick inwards; ``ry`` for an ellipse."""
    ry = r if ry is None else ry
    outer = circle_points(cx, cy, r, ry, n, a0, a1)
    inner = circle_points(cx, cy, r - t, ry - t * ry / r, n, a0, a1)
    out = []
    for i in range(n):
        out += [(outer[i], outer[i + 1], inner[i + 1], col), (outer[i], inner[i + 1], inner[i], col)]
    return out


def line(p, q, t, col=INK) -> list:
    """A thick straight line from ``p`` to ``q``."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1.0
    ox, oy = -dy / n * t / 2, dx / n * t / 2
    return poly([(p[0] + ox, p[1] + oy), (q[0] + ox, q[1] + oy), (q[0] - ox, q[1] - oy), (p[0] - ox, p[1] - oy)], col)


# ---------------------------------------------------------------------------
# the drawings
# ---------------------------------------------------------------------------

def _still() -> list:
    """Picture: a framed photo – hills and a sun."""
    out = frame(20, 46, 235, 210, 18)
    out += poly([(38, 64), (105, 150), (150, 96), (172, 120), (217, 64)])
    out += disc(178, 168, 18, ACCENT)
    return out


def _product() -> list:
    """Product video: a film strip with a play mark."""
    out = frame(20, 40, 235, 216, 16)
    for x in range(42, 222, 34):                                     # the sprocket holes, top and bottom
        out += rect(x, 56, x + 18, 72) + rect(x, 184, x + 18, 200)
    out += poly([(104, 92), (104, 164), (164, 128)], ACCENT)
    return out


def _turn() -> list:
    """Turntable: a box on a round plate, an arrow going round it."""
    out = ring(128, 64, 100, 16, ry=38, a0=math.radians(200), a1=math.radians(330 + 360), n=40)
    out += rect(92, 90, 164, 170)
    out += poly([(92, 170), (164, 170), (186, 190), (114, 190)])
    out += poly([(164, 90), (186, 110), (186, 190), (164, 170)])
    a = math.radians(330)                                            # the arrow head at the arc's end
    tip = (128 + 100 * math.cos(a), 64 + 38 * math.sin(a))
    out += poly([(tip[0] + 22, tip[1] + 28), (tip[0] - 24, tip[1] + 6), (tip[0] + 14, tip[1] - 26)], ACCENT)
    return out


def _web() -> list:
    """3D page: a browser window with a cube in it."""
    out = frame(16, 30, 239, 222, 16)
    out += rect(16, 182, 239, 222)
    for x in (40, 66, 92):
        out += disc(x, 202, 8, (40, 40, 40, 255), n=12)
    c = (128, 104)                                                   # the cube, seen from a corner
    top = [(c[0], c[1] + 52), (c[0] + 52, c[1] + 26), (c[0], c[1]), (c[0] - 52, c[1] + 26)]
    out += poly(top, ACCENT)
    out += poly([(c[0] - 52, c[1] + 26), (c[0], c[1]), (c[0], c[1] - 58), (c[0] - 52, c[1] - 32)])
    out += poly([(c[0], c[1]), (c[0] + 52, c[1] + 26), (c[0] + 52, c[1] - 32), (c[0], c[1] - 58)],
                (170, 170, 170, 255))
    return out


def _anim() -> list:
    """Animation: a clapperboard."""
    out = rect(28, 30, 228, 150)
    out += rect(46, 48, 210, 132, (40, 40, 40, 255))
    out += poly([(28, 160), (228, 160), (228, 196), (28, 196)])
    for x in (52, 112, 172):                                         # the stripes of the clapper
        out += poly([(x, 160), (x + 30, 160), (x + 48, 196), (x + 18, 196)], (40, 40, 40, 255))
    out += poly([(28, 204), (220, 236), (226, 206), (34, 174)], ACCENT)
    out += poly([(100, 66), (100, 116), (146, 91)])
    return out


def _queue() -> list:
    """Queue: a list of three waiting jobs, the first one running."""
    out = []
    for i, y in enumerate((178, 118, 58)):
        out += rect(26, y, 66, y + 40, ACCENT if i == 0 else INK)
        out += rect(84, y + 8, 230, y + 32)
    return out


_DRAWINGS = {"still": _still, "product": _product, "turn": _turn, "web": _web, "anim": _anim, "queue": _queue}
KEYS = tuple(_DRAWINGS)


def triangles(key: str) -> list:
    return _DRAWINGS[key]()


def _clamp(v: float) -> int:
    return max(0, min(SIZE, int(round(v))))


def icon(key: str) -> tuple:
    """(coords, colours) of the drawing ``key`` as bytes for ``bpy.app.icons.new_triangles((0, 255), …)``."""
    coords, cols = bytearray(), bytearray()
    for a, b, c, col in triangles(key):
        for x, y in (a, b, c):
            mid = SIZE / 2
            coords += bytes((_clamp(LEFT + x * FILL), _clamp(mid + (y - mid) * FILL)))
            cols += bytes(col)
    return bytes(coords), bytes(cols)
