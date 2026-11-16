"""The gloved hand that changes a tool by hand (task 0156; the hand of task 0041 made realistic). No Blender.

``glove(holder_r, curl)`` gives the hand's mesh as points and faces in the hand's own space (metres): the grip's
centre at the origin on the tool's axis, z along the tool (into the spindle), the palm on the -y side (towards the
operator), a right hand. Its fingers are stacked along z and wrap round the holder: ``curl`` 1 = closed round a holder
of radius ``holder_r`` (each finger on a circle round the axis), 0 = open (the fingers straight, a little spread).
The same points in the same order for every ``curl``: the open hand is a shape key of the closed one.

Parts: a palm (a rounded slab with the knuckles' bumps and a heel), four fingers of three phalanges each (slightly
thicker at the joints, round tips), a thumb of two phalanges from the palm's heel going the other way round, and a
gauntlet cuff with a rolled rim and a seam band. Light: about 3,000 triangles.
"""

from __future__ import annotations

import math

import numpy as np

RING = 12                     # points round a finger
CUFF_RING = 20
FINGERS = (                   # (z of the finger, length, base radius) – index at the top (nearest the spindle)
    (0.0285, 0.083, 0.0098),
    (0.0095, 0.092, 0.0102),
    (-0.0095, 0.087, 0.0099),
    (-0.0275, 0.070, 0.0090),
)
PHALANX = (0.46, 0.31, 0.23)  # share of a finger's length per phalanx
PALM_W, PALM_T = 0.084, 0.027  # palm width (along z) and thickness
OPEN_SPREAD = 0.06            # rad: how far the open fingers fan out


def _frame(t):
    n = float(np.linalg.norm(t))
    t = t / n if n > 1e-12 else np.array((1.0, 0.0, 0.0))
    a = np.array((0.0, 0.0, 1.0)) if abs(t[2]) < 0.9 else np.array((1.0, 0.0, 0.0))
    x = np.cross(t, a)
    x /= np.linalg.norm(x)
    return x, np.cross(t, x)


def tube(pts, radii, ring: int = RING, caps: bool = True, flat: float = 1.0):
    """A tube along ``pts`` with ``radii`` (rounded caps when ``caps``); ``flat`` squashes it across (1 = round).
    Returns (points (n, 3), faces). The frames are carried along the line (no twist)."""
    pts = [np.asarray(p, float) for p in pts]
    n = len(pts)
    verts, faces, rings = [], [], []
    prev = None
    for k in range(n):
        t = pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]
        t = t / (np.linalg.norm(t) or 1.0)
        if prev is None:
            x, y = _frame(t)
        else:
            x = prev - t * float(np.dot(prev, t))
            x /= np.linalg.norm(x) or 1.0
            y = np.cross(t, x)
        prev = x
        idx = []
        for i in range(ring):
            a = 2 * math.pi * i / ring
            verts.append(pts[k] + (x * math.cos(a) * flat + y * math.sin(a)) * radii[k])
            idx.append(len(verts) - 1)
        rings.append(idx)
    for k in range(n - 1):
        for i in range(ring):
            j = (i + 1) % ring
            faces.append((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    if caps:
        for end, sign in ((0, -1.0), (n - 1, 1.0)):
            t = pts[min(end + 1, n - 1)] - pts[max(end - 1, 0)]
            t = t / (np.linalg.norm(t) or 1.0) * sign
            tip = pts[end] + t * radii[end] * 0.85
            verts.append(tip)
            c = len(verts) - 1
            r = rings[end]
            for i in range(ring):
                j = (i + 1) % ring
                faces.append((r[i], r[j], c) if sign > 0 else (r[j], r[i], c))
    return np.asarray(verts), faces


def blob(centre, half, ring: int = 16, rows: int = 10, power: float = 2.6):
    """A rounded box (a superellipsoid) round ``centre`` with half sizes ``half``: closed (one point at each pole)."""
    c = np.asarray(centre, float)
    h = np.asarray(half, float)
    e = 2.0 / power

    def sp(v, ex):
        return math.copysign(abs(v) ** ex, v)

    verts = [c + h * np.array((0.0, 0.0, -1.0))]
    for r in range(1, rows):
        v = -math.pi / 2 + math.pi * r / rows
        for i in range(ring):
            u = 2 * math.pi * i / ring
            verts.append(c + h * np.array((sp(math.cos(v), e) * sp(math.cos(u), e),
                                           sp(math.cos(v), e) * sp(math.sin(u), e), sp(math.sin(v), e))))
    verts.append(c + h * np.array((0.0, 0.0, 1.0)))
    top = len(verts) - 1
    faces = []

    def at(r, i):
        return 1 + (r - 1) * ring + (i % ring)

    for i in range(ring):
        faces.append((0, at(1, i + 1), at(1, i)))
    for r in range(1, rows - 1):
        for i in range(ring):
            faces.append((at(r, i), at(r, i + 1), at(r + 1, i + 1), at(r + 1, i)))
    for i in range(ring):
        faces.append((at(rows - 1, i), at(rows - 1, i + 1), top))
    return np.asarray(verts), faces


def _finger_line(p0, t0, n0, length, curvature, steps: int = 9):
    """Points along a finger from its knuckle ``p0``: it starts along ``t0`` and bends towards ``n0`` with the given
    curvature (1/m; 0 = straight)."""
    out = []
    for i in range(steps + 1):
        s = length * i / steps
        if abs(curvature) < 1e-6:
            out.append(p0 + t0 * s)
        else:
            k = curvature
            out.append(p0 + t0 * (math.sin(k * s) / k) + n0 * ((1 - math.cos(k * s)) / k))
    return out


def _finger_radii(r0: float, steps: int = 9) -> list:
    """Thicker at the knuckle and the two joints, thinner at the tip."""
    out = []
    joints = (PHALANX[0], PHALANX[0] + PHALANX[1])
    for i in range(steps + 1):
        s = i / steps
        r = r0 * (1.0 - 0.2 * s)
        bump = max(0.0, 1.0 - min(abs(s - j) for j in joints) / 0.07) * 0.06 * r0
        out.append(r + bump)
    return out


def glove(holder_r: float = 0.025, curl: float = 1.0) -> tuple:
    """(points (n, 3), faces) of the gloved right hand round a holder of radius ``holder_r`` (see the module)."""
    r = float(holder_r)
    c = min(1.0, max(0.0, float(curl)))
    parts = []
    palm_y = -(r + 0.017)
    # the palm: a rounded slab in front of the holder, a little wider at the knuckles, its heel lower down
    parts.append(blob((0.004, palm_y, -0.002), (0.048, PALM_T / 2, PALM_W / 2 + 0.002)))
    parts.append(blob((-0.026, palm_y - 0.004, -0.032), (0.026, 0.016, 0.02)))           # the heel (thenar side)
    # the fingers: from the knuckles at the palm's +x edge, round the holder (closed) or out straight (open)
    for k, (z, length, r0) in enumerate(FINGERS):
        rr = r + r0 + 0.0008                          # the finger's middle line round the holder
        a0 = math.radians(-62)
        p0 = np.array((rr * math.cos(a0), rr * math.sin(a0), z))
        knuckle = np.array((0.04, palm_y + 0.003, z))
        t_closed = np.array((-math.sin(a0), math.cos(a0), 0.0))
        spread = (k - 1.5) * OPEN_SPREAD * (1 - c)
        t_open = np.array((math.cos(math.radians(-25)), math.sin(math.radians(-25)), 0.0))
        t0 = t_closed * c + t_open * (1 - c)
        t0 = t0 + np.array((0.0, 0.0, spread))
        t0 /= np.linalg.norm(t0)
        n0 = np.cross(np.array((0.0, 0.0, 1.0)), t0)
        start = knuckle * (1 - c) + p0 * c
        line = [start - t0 * 0.007] + _finger_line(start, t0, n0, length, c / rr)
        radii = [r0 * 1.08] + _finger_radii(r0)
        parts.append(tube(line, radii, flat=0.92))
        parts.append(blob(knuckle + np.array((0.0, -0.004, 0.0)), (0.011, 0.009, r0 * 0.95), ring=10, rows=6))
    # the thumb: from the heel round the other side of the holder, a little lower
    rt = r + 0.0115
    a_t = math.radians(-118)
    base = np.array((-0.034, palm_y - 0.006, -0.036))
    p1 = np.array((rt * math.cos(a_t), rt * math.sin(a_t), -0.026))
    t_c = np.array((math.sin(a_t), -math.cos(a_t), 0.12))
    t_o = np.array((-0.55, 0.45, 0.7))
    t1 = t_c * c + t_o * (1 - c)
    t1 /= np.linalg.norm(t1)
    n1 = np.cross(t1, np.array((0.0, 0.0, 1.0)))
    n1 /= np.linalg.norm(n1) or 1.0
    line = [base] + _finger_line(p1 * c + (base + np.array((-0.006, 0.012, 0.012))) * (1 - c), t1, -n1, 0.058,
                                 c / rt, steps=7)
    parts.append(tube(line, [0.013, 0.0125, 0.012, 0.0118, 0.0114, 0.011, 0.0106, 0.0102, 0.0096], flat=0.9))
    # wrist and gauntlet cuff, back towards the operator and a little down; a rolled rim and a seam band
    w0 = np.array((0.0, palm_y - 0.012, -0.012))
    w1 = np.array((0.0, palm_y - 0.065, -0.026))
    w2 = np.array((0.0, palm_y - 0.122, -0.038))
    cuff = [w0, w0 + (w1 - w0) * 0.5, w1, w1 + (w2 - w1) * 0.45, w1 + (w2 - w1) * 0.5, w2, w2 + (w2 - w1) * 0.06]
    parts.append(tube(cuff, [0.029, 0.03, 0.033, 0.035, 0.0375, 0.039, 0.036], ring=CUFF_RING, caps=True,
                      flat=0.82))
    verts, faces = [], []
    for v, f in parts:
        base_i = len(verts)
        verts += [tuple(p) for p in v]
        faces += [tuple(i + base_i for i in face) for face in f]
    return np.asarray(verts, float), faces


def fingertips(holder_r: float = 0.025, curl: float = 1.0) -> np.ndarray:
    """The four fingertips' middle lines' ends (for the tests: closed, they lie round the holder)."""
    r = float(holder_r)
    c = min(1.0, max(0.0, float(curl)))
    out = []
    for k, (z, length, r0) in enumerate(FINGERS):
        rr = r + r0 + 0.0008
        a0 = math.radians(-62)
        p0 = np.array((rr * math.cos(a0), rr * math.sin(a0), z))
        t0 = np.array((-math.sin(a0), math.cos(a0), 0.0))
        n0 = np.cross(np.array((0.0, 0.0, 1.0)), t0)
        if c >= 1.0:
            out.append(_finger_line(p0, t0, n0, length, 1.0 / rr)[-1])
    return np.asarray(out)
