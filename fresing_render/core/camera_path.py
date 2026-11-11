"""Camera paths (task 0087): a smooth curve through points, flown at an even speed with a ramp up and down.

No Blender here: points are (x, y, z) in metres. ``Path`` goes through every point (a centripetal Catmull-Rom curve,
which never makes loops or overshoots between points that lie close together), measured along its length so the
camera can fly it at an even speed. ``ramped`` is the share of the way done at a moment of the step, with the speed
rising evenly at the start and falling evenly at the end (the even part in between).
"""

from __future__ import annotations

import math

import numpy as np

SAMPLES = 200            # points worked out per piece between two path points (the length is measured on them)
SAME = 1e-4              # path points closer than this (m) are one point


def clean(points) -> np.ndarray:
    """The points as an n x 3 array, without points that lie on the one before."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) < 2:
        return pts
    keep = [0]
    for i in range(1, len(pts)):
        if np.linalg.norm(pts[i] - pts[keep[-1]]) > SAME:
            keep.append(i)
    return pts[keep]


def _catmull_rom(p0, p1, p2, p3, n: int) -> np.ndarray:
    """``n`` + 1 points from p1 to p2 (both included) of a centripetal Catmull-Rom piece."""
    def knot(t, a, b):
        return t + max(np.linalg.norm(b - a), 1e-9) ** 0.5
    t0 = 0.0
    t1 = knot(t0, p0, p1)
    t2 = knot(t1, p1, p2)
    t3 = knot(t2, p2, p3)
    t = np.linspace(t1, t2, n + 1)[:, None]
    a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
    a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
    a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
    b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
    b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
    out = (t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2
    out[0], out[-1] = p1, p2                    # exactly through the points
    return out


class Path:
    """A smooth curve through ``points`` (at least two different ones), measured along its length."""

    def __init__(self, points, samples: int = SAMPLES):
        pts = clean(points)
        if len(pts) < 2:
            raise ValueError("a path needs at least two different points")
        self.points = pts
        # end points mirrored, so the curve leaves the first point and reaches the last one heading at the next
        ends = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
        pieces = [_catmull_rom(ends[i], ends[i + 1], ends[i + 2], ends[i + 3], samples) for i in range(len(pts) - 1)]
        self.dense = np.vstack([pieces[0]] + [p[1:] for p in pieces[1:]])
        seg = np.linalg.norm(np.diff(self.dense, axis=0), axis=1)
        self.along = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.along[-1])
        self.at_point = self.along[::samples].copy()      # the distance along the path of each path point

    def point(self, s: float) -> np.ndarray:
        """The place ``s`` metres along the path (clamped to its ends)."""
        s = min(max(float(s), 0.0), self.length)
        i = int(np.searchsorted(self.along, s, side="right")) - 1
        i = min(max(i, 0), len(self.dense) - 2)
        d = self.along[i + 1] - self.along[i]
        f = (s - self.along[i]) / d if d > 0 else 0.0
        return self.dense[i] + (self.dense[i + 1] - self.dense[i]) * f

    def locate(self, p) -> float:
        """How far along the path (m) the point of the path nearest to ``p`` lies (to measure speed along it)."""
        p = np.asarray(p, dtype=float)
        a, b = self.dense[:-1], self.dense[1:]
        ab = b - a
        n2 = np.einsum("ij,ij->i", ab, ab)
        t = np.clip(np.einsum("ij,ij->i", p - a, ab) / np.where(n2 > 0, n2, 1.0), 0.0, 1.0)
        d = np.linalg.norm(a + ab * t[:, None] - p, axis=1)
        i = int(np.argmin(d))
        return float(self.along[i] + t[i] * (self.along[i + 1] - self.along[i]))

    def direction(self, s: float) -> np.ndarray:
        """The way the path heads ``s`` metres along it (a unit vector), smoothed over a short stretch."""
        h = max(self.length * 0.01, 1e-4)
        a, b = self.point(max(0.0, s - h)), self.point(min(self.length, s + h))
        if s - h < 0.0:
            b = self.point(min(self.length, 2 * h))
        if s + h > self.length:
            a = self.point(max(0.0, self.length - 2 * h))
        v = b - a
        n = np.linalg.norm(v)
        return v / n if n > 0 else np.array([0.0, 1.0, 0.0])


def ramped(p: float, up: float, down: float) -> float:
    """The share of the way done at ``p`` (0 … 1 of the step's time): even speed, which rises evenly during the
    first ``up`` share of the time and falls evenly during the last ``down`` share."""
    p = min(max(float(p), 0.0), 1.0)
    up, down = max(0.0, up), max(0.0, down)
    if up + down > 1.0:
        k = 1.0 / (up + down)
        up, down = up * k, down * k
    v = 1.0 / (1.0 - (up + down) / 2.0)        # the top speed, in shares of the way per share of the time
    if p < up:
        return 0.5 * v * p * p / up
    done_up = 0.5 * v * up
    if p <= 1.0 - down:
        return done_up + v * (p - up)
    q = 1.0 - p
    return 1.0 - 0.5 * v * q * q / down


def ramp_shares(easing: str, ramp: float, duration: float) -> tuple[float, float]:
    """(up, down) shares of the step's time for a path flown with ``easing`` and a ramp of ``ramp`` seconds."""
    if duration <= 0.0:
        return 0.0, 0.0
    r = max(0.0, ramp) / duration
    up = r if easing in ("SMOOTH", "EASE_IN") else 0.0
    down = r if easing in ("SMOOTH", "EASE_OUT") else 0.0
    if up + down > 1.0:
        k = 1.0 / (up + down)
        up, down = up * k, down * k
    return up, down


def heading(rot3) -> float:
    """The turn about the vertical (radians) of a 3 x 3 rotation: where it takes the X axis, seen from above."""
    m = np.asarray(rot3, dtype=float)
    x = m[:, 0]
    if math.hypot(x[0], x[1]) < 1e-6:          # X points straight up or down: use Y instead
        y = m[:, 1]
        return math.atan2(y[1], y[0]) - math.pi / 2
    return math.atan2(x[1], x[0])
