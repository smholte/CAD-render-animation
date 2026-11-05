"""Pictures for decals made in code (task 0024): text, the CE mark, warning stickers, arrows and a
type plate. Pure numpy, no Blender, no downloaded artwork.

Every picture is made as three *masks* (0..1 per pixel) instead of colours:

* ``INK``   – letters, the CE mark, a warning sign's border and symbol, an arrow;
* ``FIELD`` – the background behind it (a warning sign's yellow, a type plate);
* ``EDGE``  – a border round the background (and a type plate's rivets and line).

The decal's material paints each mask with a colour of its own (and leaves the field or edge out
when they are switched off), so colours, background and border change at once in the side panel,
without making the picture again.

Text comes from a *glyph source*: a function that turns one line of text into filled triangles
(font units, baseline at y=0, y up, a capital letter about 0.7 high). Blender gives them from its
own fonts (``blender/decals.py``); the tests use a simple stand-in.

Drawing is done with a small scan-line filler (non-zero rule, 4x4 samples per pixel for smooth
edges) in pixel coordinates: x to the right, y down, (0, 0) the top-left corner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

INK, FIELD, EDGE = 0, 1, 2
SAMPLES = 4

GlyphSource = Callable[[str], np.ndarray]        # text -> triangles (N, 3, 2), font units, y up

YELLOW = "#F9A800"            # RAL 1003 signal yellow: the colour of warning signs
BLACK = "#1A1A1A"
WHITE = "#FFFFFF"
PLATE = "#C8CBCE"             # brushed aluminium grey


@dataclass
class Art:
    """A picture made in code: the masks, and the colours it starts with."""
    masks: np.ndarray                         # (height, width, 3) float32, row 0 at the top
    ink: str = BLACK
    field: str = WHITE
    edge: str = BLACK
    use_field: bool = False
    use_edge: bool = False

    @property
    def width(self) -> int:
        return int(self.masks.shape[1])

    @property
    def height(self) -> int:
        return int(self.masks.shape[0])

    @property
    def aspect(self) -> float:
        """Height / width."""
        return self.height / max(1, self.width)


# ---------------------------------------------------------------------------
# filling shapes
# ---------------------------------------------------------------------------


def _signed_area(p: np.ndarray) -> float:
    q = np.roll(p, -1, axis=0)
    return 0.5 * float((p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]).sum())


def coverage(polys, width: int, height: int, ss: int = SAMPLES) -> np.ndarray:
    """How much of every pixel (0..1) the union of the polygons covers. Polygons: (K, 2) arrays in
    pixel coordinates; each is filled whichever way round its corners go.

    Each pixel row is sampled ``ss`` times; along a row the covered part of each pixel is worked out
    exactly (where an edge crosses the row)."""
    w, h = int(width), int(height)
    out = np.zeros((h, w), dtype=np.float32)
    parts = []
    for p in polys:
        p = np.asarray(p, dtype=np.float64).reshape(-1, 2)
        if len(p) < 3:
            continue
        if _signed_area(p) < 0:
            p = p[::-1]
        parts.append(np.concatenate([p, np.roll(p, -1, axis=0)], axis=1))
    if not parts:
        return out
    e = np.concatenate(parts, axis=0)
    x0, y0, x1, y1 = e[:, 0], e[:, 1] * ss, e[:, 2], e[:, 3] * ss
    keep = y0 != y1
    x0, y0, x1, y1 = x0[keep], y0[keep], x1[keep], y1[keep]
    direction = np.where(y1 > y0, 1.0, -1.0)
    down = y1 > y0
    ya, yb = np.where(down, y0, y1), np.where(down, y1, y0)
    xa, xb = np.where(down, x0, x1), np.where(down, x1, x0)
    hs = h * ss
    j0 = np.clip(np.ceil(ya - 0.5), 0, hs).astype(np.int64)        # sample rows whose centre lies in [ya, yb)
    j1 = np.clip(np.ceil(yb - 0.5), 0, hs).astype(np.int64)
    slope = (xb - xa) / (yb - ya)
    strip = max(1, min(h, 2_000_000 // max(1, (w + 2) * ss)))       # pixel rows per pass (memory)
    for py0 in range(0, h, strip):
        py1 = min(h, py0 + strip)
        r0, r1 = py0 * ss, py1 * ss
        sel = np.flatnonzero((j1 > r0) & (j0 < r1))
        if not len(sel):
            continue
        a = np.maximum(j0[sel], r0)
        n = np.minimum(j1[sel], r1) - a
        good = n > 0
        sel, a, n = sel[good], a[good], n[good]
        if not len(sel):
            continue
        idx = np.repeat(sel, n)
        start = np.repeat(np.cumsum(n) - n, n)
        rows = np.repeat(a, n) + (np.arange(int(n.sum())) - start)
        x = xa[idx] + (rows + 0.5 - ya[idx]) * slope[idx]
        d = direction[idx]
        inside = x < w
        x, d, rows = x[inside], d[inside], rows[inside]
        col = np.floor(x).astype(np.int64)
        frac = x - col
        left = col < 0
        col = np.where(left, 0, col)
        frac = np.where(left, 0.0, frac)
        base = (rows - r0) * (w + 1)
        size = (r1 - r0) * (w + 1)
        delta = np.bincount(base + col, weights=d * (1.0 - frac), minlength=size)
        delta += np.bincount(base + col + 1, weights=d * frac, minlength=size)
        cov = np.clip(np.abs(np.cumsum(delta.reshape(r1 - r0, w + 1)[:, :w], axis=1)), 0.0, 1.0)
        out[py0:py1] = cov.reshape(py1 - py0, ss, w).mean(axis=1)
    return out


def paint(masks: np.ndarray, channel: int, polys, erase: bool = False) -> None:
    """Add the shapes to a mask (or cut them out of it)."""
    cov = coverage(polys, masks.shape[1], masks.shape[0])
    if erase:
        masks[..., channel] *= 1.0 - cov
    else:
        np.maximum(masks[..., channel], cov, out=masks[..., channel])


def canvas(width: int, height: int) -> np.ndarray:
    return np.zeros((int(height), int(width), 3), dtype=np.float32)


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------


def rect(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    return np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], dtype=np.float64)


def circle(cx: float, cy: float, r: float, n: int = 0) -> np.ndarray:
    n = n or max(24, min(256, int(r * 0.8)))
    a = np.linspace(0.0, 2 * math.pi, n, endpoint=False)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], axis=1)


def arc_band(cx: float, cy: float, r_out: float, r_in: float, a0: float, a1: float, n: int = 96) -> np.ndarray:
    """A curved band between two radii, from angle a0 to a1 (degrees, counter-clockwise as seen on
    the picture: 0 = right, 90 = up)."""
    a = np.radians(np.linspace(a0, a1, n))
    outer = np.stack([cx + r_out * np.cos(a), cy - r_out * np.sin(a)], axis=1)
    inner = np.stack([cx + r_in * np.cos(a[::-1]), cy - r_in * np.sin(a[::-1])], axis=1)
    return np.concatenate([outer, inner], axis=0)


def rounded(pts, r: float, n_arc: int = 12) -> np.ndarray:
    """A convex polygon with its corners rounded (radius ``r``)."""
    p = np.asarray(pts, dtype=np.float64)
    c = p.mean(axis=0)
    out = []
    k = len(p)
    for i in range(k):
        prev, cur, nxt = p[i - 1], p[i], p[(i + 1) % k]
        normals = []
        for a, b in ((prev, cur), (cur, nxt)):
            d = (b - a) / np.linalg.norm(b - a)
            nrm = np.array([-d[1], d[0]])
            if np.dot(c - a, nrm) < 0:
                nrm = -nrm
            normals.append(nrm)                      # pointing into the polygon
        n1, n2 = normals
        bis = n1 + n2
        cos_turn = max(-1.0, min(1.0, float(np.dot(n1, n2))))
        dist = r / max(math.cos(math.acos(cos_turn) / 2), 1e-6)
        centre = cur + bis / np.linalg.norm(bis) * dist
        a0 = math.atan2(-n1[1], -n1[0])
        a1 = math.atan2(-n2[1], -n2[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for t in np.linspace(a0, a0 + da, n_arc):
            out.append(centre + r * np.array([math.cos(t), math.sin(t)]))
    return np.asarray(out)


def inset(pts, d: float) -> np.ndarray:
    """A convex polygon moved inwards by ``d`` on every side."""
    p = np.asarray(pts, dtype=np.float64)
    c = p.mean(axis=0)
    k = len(p)
    lines = []
    for i in range(k):
        a, b = p[i], p[(i + 1) % k]
        dd = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-dd[1], dd[0]])
        if np.dot(c - a, nrm) < 0:
            nrm = -nrm
        lines.append((a + nrm * d, dd))
    out = []
    for i in range(k):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        m = np.array([d1, -d2]).T
        t = np.linalg.solve(m, p2 - p1)
        out.append(p1 + d1 * t[0])
    return np.asarray(out)


def stroke(points, width: float, closed: bool = False) -> list[np.ndarray]:
    """A line of this width along the points (round joints and ends), as polygons."""
    p = np.asarray(points, dtype=np.float64)
    if closed:
        p = np.concatenate([p, p[:1]], axis=0)
    r = width / 2
    out = []
    for a, b in zip(p[:-1], p[1:]):
        d = b - a
        ln = np.linalg.norm(d)
        if ln < 1e-9:
            continue
        nrm = np.array([-d[1], d[0]]) / ln * r
        out.append(np.array([a + nrm, b + nrm, b - nrm, a - nrm]))
    for q in p:
        out.append(circle(q[0], q[1], r, 20))
    return out


def _box(cx: float, cy: float, half: float):
    """Map a pictogram drawn in -1..1 (y down) into a square on the picture."""
    def f(pts):
        return np.asarray(pts, dtype=np.float64) * half + np.array([cx, cy])
    return f


def _wave(x: float, y0: float, y1: float, amp: float, waves: float = 1.5, n: int = 40) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)
    return np.stack([x + amp * np.sin(t * waves * 2 * math.pi), y0 + (y1 - y0) * t], axis=1)


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------


def text_triangles(glyphs: GlyphSource, text: str, x: float, baseline: float, size: float,
                   max_width: float = 0.0, align: str = "LEFT") -> tuple[list[np.ndarray], float]:
    """Triangles (pixel coordinates) of one line of text, and its width. ``size``: pixels per font
    unit (a capital letter is about 0.7 × size high). ``max_width``: made smaller to fit."""
    tris = np.asarray(glyphs(text), dtype=np.float64).reshape(-1, 3, 2) if text.strip() else np.zeros((0, 3, 2))
    if not len(tris):
        return [], 0.0
    lo, hi = tris[..., 0].min(), tris[..., 0].max()
    width = (hi - lo) * size
    if max_width and width > max_width:
        size *= max_width / width
        width = max_width
    if align == "CENTER":
        x -= width / 2
    elif align == "RIGHT":
        x -= width
    px = np.empty_like(tris)
    px[..., 0] = x + (tris[..., 0] - lo) * size
    px[..., 1] = baseline - tris[..., 1] * size
    return list(px), width


def text_art(glyphs: GlyphSource, text: str, line_px: int = 220, max_px: int = 4096) -> Art:
    """Text on its own decal: one or more lines (``|`` starts a new line), centred, with a field
    behind it and a border round it (both off at first)."""
    lines = [t.strip() for t in (text or "").split("|")]
    lines = [t for t in lines if t] or ["Text"]
    size = float(line_px)
    widths = []
    for line in lines:
        tris = np.asarray(glyphs(line), dtype=np.float64).reshape(-1, 3, 2)
        widths.append((tris[..., 0].max() - tris[..., 0].min()) * size if len(tris) else 0.0)
    size *= min(1.0, (max_px - 0.9 * size) / max(max(widths), 1.0))     # very long text: smaller letters
    gap = 1.3 * size
    polys = []
    for i, line in enumerate(lines):
        polys += text_triangles(glyphs, line, 0.0, i * gap, size, align="CENTER")[0]
    if polys:
        pts = np.concatenate(polys, axis=0)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
    else:
        lo, hi = np.array([-size, -0.7 * size]), np.array([size, 0.0])
    lo[1] = min(lo[1], -0.72 * size)                  # room for capitals even in "ace"
    pad = 0.4 * size
    w, h = int(math.ceil(hi[0] - lo[0] + 2 * pad)), int(math.ceil(hi[1] - lo[1] + 2 * pad))
    shift = np.array([pad - lo[0], pad - lo[1]])
    m = canvas(w, h)
    paint(m, INK, [p + shift for p in polys])
    _plate(m, radius=0.18 * size, border=0.06 * size, inset_by=0.05 * size)
    return Art(m)


def _plate(m: np.ndarray, radius: float, border: float, inset_by: float = 0.0) -> None:
    """The field (rounded rectangle over the whole picture) and a border just inside its edge."""
    h, w = m.shape[:2]
    outer = rounded(rect(0, 0, w, h), min(radius, w / 2.1, h / 2.1))
    paint(m, FIELD, [outer])
    if border > 0:
        e0 = inset_by
        ring_out = rounded(rect(e0, e0, w - e0, h - e0), max(1.0, min(radius - e0, w / 2.1, h / 2.1)))
        e1 = inset_by + border
        ring_in = rounded(rect(e1, e1, w - e1, h - e1), max(1.0, min(radius - e1, w / 2.1, h / 2.1)))
        band = canvas(w, h)
        paint(band, 0, [ring_out])
        paint(band, 0, [ring_in], erase=True)
        np.maximum(m[..., EDGE], band[..., 0], out=m[..., EDGE])


# ---------------------------------------------------------------------------
# ready-made stickers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sticker:
    key: str
    label: str
    description: str
    width_mm: float                  # a sensible first size


STICKERS = (
    Sticker("CE", "CE mark", "The CE marking, drawn as two letters on the circles they are made of", 60),
    Sticker("TYPE_PLATE", "Type plate", "A type plate with your company, type, serial number, year and weight", 120),
    Sticker("WARN_GENERAL", "Warning: general", "Yellow warning triangle with an exclamation mark", 100),
    Sticker("WARN_HAND", "Warning: hand crush", "Yellow warning triangle: hands can be crushed here", 100),
    Sticker("WARN_ELECTRIC", "Warning: electricity", "Yellow warning triangle: electrical voltage", 100),
    Sticker("WARN_HOT", "Warning: hot surface", "Yellow warning triangle: hot surface", 100),
    Sticker("WARN_LOAD", "Warning: hanging load", "Yellow warning triangle: suspended load overhead", 100),
    Sticker("ARROW", "Arrow", "A straight arrow, e.g. the way something moves (turn it with Turn)", 80),
    Sticker("ARROW_TURN", "Turning arrow", "A curved arrow showing which way something turns", 80),
)
STICKER_KEYS = tuple(s.key for s in STICKERS)


def sticker(key: str) -> Sticker:
    for s in STICKERS:
        if s.key == key:
            return s
    return STICKERS[0]


def ce_mark(scale: float = 1.0) -> np.ndarray:
    """The CE mark: each letter is part of a ring (the C open on the right, the E the same with a
    middle bar), the two rings side by side."""
    r = 400.0 * scale
    stroke_w = 0.2 * r
    pad = 0.35 * r
    cx_c = pad + r
    cx_e = cx_c + 2.06 * r
    w = int(cx_e + r * math.cos(math.radians(45)) + pad)
    h = int(2 * r + 2 * pad)
    cy = h / 2
    m = canvas(w, h)
    c = arc_band(cx_c, cy, r, r - stroke_w, 45, 315)
    e = arc_band(cx_e, cy, r, r - stroke_w, 45, 315)
    bar = rect(cx_e - r + stroke_w * 0.5, cy - stroke_w * 0.45, cx_e + r * math.cos(math.radians(45)) - 0.08 * r,
               cy + stroke_w * 0.45)
    paint(m, INK, [c, e, bar])
    return m


def _warning(symbol: str) -> np.ndarray:
    w, h = 1100, 980
    tri = np.array([(w / 2, 40.0), (40.0, h - 40.0), (w - 40.0, h - 40.0)])
    outer = rounded(tri, 60.0)
    inner_tri = inset(tri, 82.0)
    inner = rounded(inner_tri, 18.0)
    m = canvas(w, h)
    paint(m, INK, [outer])
    paint(m, INK, [inner], erase=True)
    paint(m, FIELD, [inner])
    # the symbol sits in the triangle's incircle, a little low
    cy = (tri[0][1] + 2 * tri[1][1]) / 3 + 10
    half = 0.27 * (tri[2][0] - tri[1][0]) / 2 * 1.3
    b = _box(w / 2, cy, half)
    shapes: list = []
    if symbol == "WARN_GENERAL":
        shapes = [rounded(b([(-0.13, -0.95), (0.13, -0.95), (0.08, 0.38), (-0.08, 0.38)]), 0.04 * half),
                  b(circle(0.0, 0.72, 0.16))]
    elif symbol == "WARN_ELECTRIC":
        shapes = [b([(0.05, -1.0), (0.48, -1.0), (0.12, -0.12), (0.45, -0.12), (-0.32, 1.0), (-0.08, 0.15),
                     (-0.42, 0.15)])]
    elif symbol == "WARN_HOT":
        shapes = [b(rect(-0.95, 0.72, 0.95, 0.92))]
        for x in (-0.5, 0.0, 0.5):
            shapes += stroke(b(_wave(x, -0.95, 0.5, 0.12)), 0.13 * half)
    elif symbol == "WARN_LOAD":
        shapes = stroke(b([(0.0, -1.0), (0.0, -0.58)]), 0.12 * half)                   # the rope
        shapes.append(b(arc_band(0.0, -0.38, 0.22, 0.1, 90, 390)))                       # the hook
        shapes += stroke(b([(0.0, -0.18), (-0.62, 0.18)]), 0.09 * half)                  # the slings
        shapes += stroke(b([(0.0, -0.18), (0.62, 0.18)]), 0.09 * half)
        shapes.append(b(rect(-0.8, 0.18, 0.8, 0.95)))                                    # the load
    elif symbol == "WARN_HAND":
        shapes = [b(rect(-0.85, -1.0, 0.85, -0.55))]                                    # the block coming down
        shapes.append(b([(-0.14, -0.5), (0.14, -0.5), (0.14, -0.3), (0.3, -0.3), (0.0, -0.05), (-0.3, -0.3),
                         (-0.14, -0.3)]))                                               # arrow down
        shapes.append(b(rect(-0.95, 0.82, 0.95, 0.97)))                                 # what it presses on
        shapes.append(rounded(b(rect(-0.05, 0.28, 0.75, 0.78)), 0.12 * half))           # palm
        for i, (y, length) in enumerate(((0.32, 0.62), (0.45, 0.72), (0.58, 0.7), (0.71, 0.58))):
            shapes.append(rounded(b(rect(-0.05 - length, y - 0.055, 0.0, y + 0.055)), 0.05 * half))
        shapes.append(rounded(b([(0.15, 0.3), (0.32, 0.3), (0.02, 0.0), (-0.12, 0.08)]), 0.03 * half))   # thumb
    paint(m, INK, shapes)
    return m


def _arrow(turning: bool) -> np.ndarray:
    w = h = 1000
    m = canvas(w, h)
    if turning:
        cx, cy, r_mid = 500.0, 520.0, 330.0
        a1 = math.radians(400.0)
        band = arc_band(cx, cy, r_mid + 50, r_mid - 50, 120, 400)
        base = np.array([cx + r_mid * math.cos(a1), cy - r_mid * math.sin(a1)])
        radial = np.array([math.cos(a1), -math.sin(a1)])
        ahead = np.array([-math.sin(a1), -math.cos(a1)])          # the way the band runs at its end
        head = np.array([base + radial * 150, base - radial * 150, base + ahead * 200])
        paint(m, INK, [band, head])
    else:
        paint(m, INK, [np.array([(500, 60), (860, 470), (630, 470), (630, 940), (370, 940), (370, 470), (140, 470)],
                                dtype=np.float64)])
    return m


def type_plate(glyphs: GlyphSource, company: str, type_name: str, serial: str, year: str, weight: str,
               ce: bool = True) -> np.ndarray:
    w, h = 1600, 900
    m = canvas(w, h)
    _plate(m, radius=50.0, border=12.0, inset_by=34.0)
    holes = [circle(x, y, 20.0) for x in (90.0, w - 90.0) for y in (90.0, h - 90.0)]
    paint(m, EDGE, holes)
    paint(m, FIELD, holes, erase=True)
    paint(m, EDGE, [rect(150, 262, w - 150, 272)])
    tris, _ = text_triangles(glyphs, company or " ", 150, 225, 150, max_width=w - 300)
    polys = list(tris)
    rows = (("Type", type_name), ("Serial no.", serial), ("Year", year), ("Weight", weight))
    right = w - 150 - (300 if ce else 0)
    for i, (label, value) in enumerate(rows):
        base = 390 + i * 120
        polys += text_triangles(glyphs, label, 150, base, 95, max_width=400)[0]
        polys += text_triangles(glyphs, value or "", 600, base, 95, max_width=right - 600)[0]
    paint(m, INK, polys)
    if ce:
        mark = ce_mark(0.12)                       # small CE in the lower right corner
        mh, mw = mark.shape[:2]
        y0, x0 = h - 120 - mh, w - 140 - mw
        np.maximum(m[y0:y0 + mh, x0:x0 + mw, INK], mark[..., INK], out=m[y0:y0 + mh, x0:x0 + mw, INK])
    return m


def sticker_colours(key: str) -> tuple[str, str, str, bool, bool]:
    """(ink, field, edge, field on, edge on) a sticker starts with."""
    if key.startswith("WARN_"):
        return BLACK, YELLOW, BLACK, True, False
    if key == "TYPE_PLATE":
        return BLACK, PLATE, BLACK, True, True
    return BLACK, WHITE, BLACK, False, False


def sticker_art(key: str, glyphs: GlyphSource | None = None, fields: dict | None = None) -> Art:
    """The picture of a ready-made sticker, with the colours it starts with."""
    fields = fields or {}
    if key == "CE":
        m = ce_mark()
        _plate(m, radius=60.0, border=10.0, inset_by=20.0)
    elif key.startswith("WARN_") and key in STICKER_KEYS:
        m = _warning(key)
    elif key in ("ARROW", "ARROW_TURN"):
        m = _arrow(key == "ARROW_TURN")
        _plate(m, radius=120.0, border=16.0, inset_by=20.0)
    elif key == "TYPE_PLATE":
        if glyphs is None:
            raise ValueError("the type plate needs a glyph source for its text")
        m = type_plate(glyphs, fields.get("company", ""), fields.get("type", ""), fields.get("serial", ""),
                       fields.get("year", ""), fields.get("weight", ""), bool(fields.get("ce", True)))
    else:
        raise ValueError(f"unknown sticker {key!r}")
    ink, fld, edge, use_field, use_edge = sticker_colours(key)
    return Art(m, ink=ink, field=fld, edge=edge, use_field=use_field, use_edge=use_edge)


# ---------------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------------


def hex_to_linear(text: str) -> tuple[float, float, float]:
    """'#RRGGBB' (as on screen) -> linear RGB for the material."""
    t = text.lstrip("#")
    rgb = [int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
