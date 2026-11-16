"""hp-uv/1: how House Planner lays out a surface's light-map UVs (TEXCOORD_1) – the reference in Python
(FORMAT.md section 6). House Planner's JavaScript does the same; the checker only checks the rules, not this exact
layout, so a better packer in a later version stays within the format.

A surface is a list of **charts**; a chart is a flat, connected piece (a wall side with its window hole, a floor, one
roof face, one face of a step). Each chart is projected onto its plane in metres, made texels with ``texels_per_m``,
and the charts' rectangles are packed in rows: ``GAP`` texels between charts, ``BORDER`` texels to the map's edge.
"""
from __future__ import annotations

import math

GAP = 4
BORDER = 2


def project(points, normal):
    """2D coordinates (metres) of points on a plane. Faces looking mostly up or down: (x, z). Other faces: along the
    horizontal direction in the face, and down from the top (v grows downwards, like the picture's rows)."""
    nx, ny, nz = normal
    if abs(ny) >= 0.7:
        return [(p[0], p[2]) for p in points]
    hx, hz = -nz, nx  # horizontal, in the face: up x normal
    ln = math.hypot(hx, hz) or 1.0
    hx, hz = hx / ln, hz / ln
    return [(p[0] * hx + p[2] * hz, -p[1]) for p in points]


def layout(charts, texels_per_m: float):
    """charts: list of (points [(x, y, z) …], normal). Returns (uvs per chart [[(u, v) …] …], (W, H)) –
    the map size in texels and each point's UV in 0 … 1."""
    flat = [project(pts, n) for pts, n in charts]
    boxes = []
    for i, f in enumerate(flat):
        u0 = min(p[0] for p in f)
        v0 = min(p[1] for p in f)
        w = max(1, math.ceil((max(p[0] for p in f) - u0) * texels_per_m - 1e-6))
        h = max(1, math.ceil((max(p[1] for p in f) - v0) * texels_per_m - 1e-6))
        boxes.append((i, u0, v0, w, h))
    total = sum((b[3] + GAP) * (b[4] + GAP) for b in boxes)
    row_limit = max(max(b[3] for b in boxes), math.ceil(math.sqrt(total)))
    order = sorted(boxes, key=lambda b: (-b[4], -b[3], b[0]))
    place = {}
    x = y = BORDER
    row_h = 0
    width = 0
    for i, u0, v0, w, h in order:
        if x > BORDER and x + w > BORDER + row_limit:
            x = BORDER
            y += row_h + GAP
            row_h = 0
        place[i] = (x, y)
        width = max(width, x + w)
        x += w + GAP
        row_h = max(row_h, h)
    W, H = width + BORDER, y + row_h + BORDER
    uvs = []
    for i, u0, v0, w, h in boxes:
        px, py = place[i]
        uvs.append([((px + (p[0] - u0) * texels_per_m) / W, (py + (p[1] - v0) * texels_per_m) / H)
                    for p in flat[i]])
    return uvs, (W, H)
