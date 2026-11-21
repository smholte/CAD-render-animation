"""Shared route geometry of the demo model (tasks 0076, 0084; task 0247: only what the ship and the park need): pure
Python + NumPy, no OpenCascade.

A route is a chain of straights (``Line``) and circular arcs (``Arc``) that meet with the same direction (G1). The
ship's crane hoist wire (``vessel.hoist``) is a rope round sheaves (``rope_route``), the park's cable a route bent
onto the scour rock (``park.first_end``). Millimetres, model coordinates (x to the bow, y to port, z up, waterline 0).
"""

from __future__ import annotations

import math

import numpy as np


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("zero vector")
    return v / n


def rotate(v, axis, ang: float) -> np.ndarray:
    """Rodrigues: v turned by ``ang`` (rad) about the unit ``axis`` (right hand)."""
    v = np.asarray(v, float)
    k = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(k, v) * s + k * np.dot(k, v) * (1.0 - c)


def _r(v) -> list:
    return [round(float(x), 4) for x in v]


class Line:
    kind = "line"

    def __init__(self, p0, p1):
        self.p0 = np.asarray(p0, float)
        self.p1 = np.asarray(p1, float)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.p1 - self.p0))

    @property
    def start(self):
        return self.p0

    @property
    def end(self):
        return self.p1

    def tangent(self, s: float = 0.0):
        return unit(self.p1 - self.p0)

    start_tangent = property(lambda self: self.tangent())
    end_tangent = property(lambda self: self.tangent())

    def point(self, s: float):
        return self.p0 + self.tangent() * s

    def distance(self, pts: np.ndarray) -> np.ndarray:
        d = self.p1 - self.p0
        t = np.clip(((pts - self.p0) @ d) / max(float(d @ d), 1e-12), 0.0, 1.0)
        return np.linalg.norm(pts - (self.p0 + t[:, None] * d), axis=1)

    def to_dict(self) -> dict:
        return {"type": "line", "start": _r(self.p0), "end": _r(self.p1), "direction": _r(self.tangent()),
                "length": round(self.length, 4)}


class Arc:
    """Circle arc: ``start`` turned about the axis (``centre``, unit ``normal``) by ``angle`` rad, right hand."""
    kind = "arc"

    def __init__(self, centre, normal, start, angle: float):
        self.centre = np.asarray(centre, float)
        self.normal = unit(normal)
        self.p0 = np.asarray(start, float)
        self.angle = float(angle)
        u = self.p0 - self.centre
        if abs(float(u @ self.normal)) > 1e-6 * max(1.0, np.linalg.norm(u)):
            raise ValueError("arc start not in the arc's plane")
        self.radius = float(np.linalg.norm(u))

    @classmethod
    def from_tangent(cls, start, tangent, bend, radius: float, angle_deg: float) -> "Arc":
        """Arc that leaves ``start`` along ``tangent`` and bends towards ``bend`` (unit, square to the tangent)."""
        t, b = unit(tangent), unit(bend)
        if abs(float(t @ b)) > 1e-9:
            raise ValueError("bend direction must be square to the tangent")
        start = np.asarray(start, float)
        return cls(start + radius * b, np.cross(t, b), start, math.radians(angle_deg))

    @property
    def length(self) -> float:
        return self.radius * self.angle

    @property
    def start(self):
        return self.p0

    def point(self, s: float):
        return self.centre + rotate(self.p0 - self.centre, self.normal, s / self.radius)

    @property
    def end(self):
        return self.point(self.length)

    def tangent(self, s: float):
        return unit(np.cross(self.normal, self.point(s) - self.centre))

    start_tangent = property(lambda self: self.tangent(0.0))
    end_tangent = property(lambda self: self.tangent(self.length))

    def distance(self, pts: np.ndarray) -> np.ndarray:
        q = pts - self.centre
        h = q @ self.normal
        qp = q - h[:, None] * self.normal
        u0 = (self.p0 - self.centre) / self.radius
        v0 = np.cross(self.normal, u0)
        phi = np.arctan2(qp @ v0, qp @ u0)
        phi = np.where(phi < -1e-9, phi + 2 * math.pi, phi)
        rho = np.linalg.norm(qp, axis=1)
        on = (phi >= 0.0) & (phi <= self.angle)
        d_arc = np.sqrt((rho - self.radius) ** 2 + h ** 2)
        d_end = np.minimum(np.linalg.norm(pts - self.p0, axis=1), np.linalg.norm(pts - self.end, axis=1))
        return np.where(on, d_arc, d_end)

    def to_dict(self) -> dict:
        return {"type": "arc", "start": _r(self.p0), "end": _r(self.end), "centre": _r(self.centre),
                "normal": _r(self.normal), "radius": round(self.radius, 4),
                "angle_deg": round(math.degrees(self.angle), 4), "length": round(self.length, 4),
                "start_tangent": _r(self.start_tangent), "end_tangent": _r(self.end_tangent)}


class Route:
    """A chain of segments; ``info[i]`` says what segment i lies on (free span, coil, a wheel, rollers …)."""

    def __init__(self, name: str, diameter: float):
        self.name = name
        self.diameter = float(diameter)
        self.segments: list = []
        self.info: list[dict] = []

    def add(self, seg, **info):
        if self.segments:
            gap = float(np.linalg.norm(seg.start - self.segments[-1].end))
            if gap > 1e-6:
                raise ValueError(f"{self.name}: segment {len(self.segments)} starts {gap:.3f} mm off the last end")
        self.segments.append(seg)
        self.info.append(info)
        return seg

    def line_to(self, p, **info):
        return self.add(Line(self.end, p), **info)

    def arc(self, bend, radius: float, angle_deg: float, **info):
        return self.add(Arc.from_tangent(self.end, self.end_tangent, bend, radius, angle_deg), **info)

    @property
    def end(self):
        return self.segments[-1].end

    @property
    def end_tangent(self):
        return self.segments[-1].end_tangent

    @property
    def length(self) -> float:
        return sum(s.length for s in self.segments)

    def sample(self, step: float = 50.0) -> np.ndarray:
        pts = []
        for seg in self.segments:
            n = max(2, int(math.ceil(seg.length / step)) + 1)
            pts += [seg.point(s) for s in np.linspace(0.0, seg.length, n)]
        return np.array(pts)

    def distance(self, pts) -> np.ndarray:
        """Distance of each point to the route's centreline."""
        pts = np.atleast_2d(np.asarray(pts, float))
        return np.min(np.stack([seg.distance(pts) for seg in self.segments]), axis=0)

    def joins(self) -> list[tuple[float, float]]:
        """(gap mm, direction change °) where each segment meets the next: both 0 for a smooth route."""
        out = []
        for a, b in zip(self.segments, self.segments[1:]):
            gap = float(np.linalg.norm(b.start - a.end))
            c = float(np.clip(a.end_tangent @ b.start_tangent, -1.0, 1.0))
            out.append((gap, math.degrees(math.acos(c))))
        return out

    def min_radius(self) -> float:
        return min((s.radius for s in self.segments if s.kind == "arc"), default=math.inf)

    def to_dict(self) -> dict:
        segs = []
        s0 = 0.0
        for seg, info in zip(self.segments, self.info):
            d = seg.to_dict()
            d["s_start"] = round(s0, 4)
            s0 += seg.length
            d.update(info)
            segs.append(d)
        return {"name": self.name, "diameter": self.diameter, "length": round(self.length, 4),
                "min_bend_radius_used": round(self.min_radius(), 4), "segments": segs}


# ---------------------------------------------------------------------------------------------------------
# Where things go (task 0084: the owner's deck layout)
# ---------------------------------------------------------------------------------------------------------



def turn(r: Route, side: int, radius: float, deg: float, **info):
    """Horizontal bend: side +1 turns left (seen from above), -1 right."""
    t = r.end_tangent
    left = unit(np.cross([0.0, 0.0, 1.0], t))
    return r.arc(side * left, radius, deg, **info)


def pitch(r: Route, up: int, radius: float, deg: float, **info):
    """Vertical bend in the plane of the tangent and z: up +1 bends upwards, -1 downwards."""
    t = r.end_tangent
    z = np.array([0.0, 0.0, 1.0])
    b = z - t * float(t @ z)
    return r.arc(up * unit(b), radius, deg, **info)


def s_bend_angle(offset: float, radius: float) -> float:
    """Each arc's angle (deg) of an S-bend of two arcs (radius) that shifts the line sideways by ``offset``."""
    if offset > 2 * radius:
        raise ValueError("S-bend offset larger than 2 x the radius")
    return math.degrees(math.acos(1.0 - offset / (2.0 * radius)))



def s_bend(r: Route, offset, radius: float, **info) -> None:
    """Two arcs of ``radius`` that shift the route by ``offset`` (square to its tangent) and go on in its direction."""
    off = np.asarray(offset, float)
    d = float(np.linalg.norm(off))
    if d < 1e-6:
        return
    u = off / d
    ang = s_bend_angle(d, radius)
    t0 = r.end_tangent
    r.arc(u, radius, ang, **info)
    t = r.end_tangent
    b = -(u - t * float(t @ u))
    r.arc(unit(b), radius, ang, **info)
    if float(np.linalg.norm(r.end_tangent - t0)) > 1e-6:
        raise ValueError("S-bend: the route does not go on in its direction")




# ---------------------------------------------------------------------------------------------------------
# Ropes round sheaves, in one vertical plane (x, z)
# ---------------------------------------------------------------------------------------------------------

def _perp(v):
    """Unit direction of travel on a circle at offset v from the centre, turning anticlockwise in (x, z)."""
    return np.array([-v[1], v[0]]) / np.linalg.norm(v)


def tangent_from_point(P, c, r: float, wrap: int):
    """Point where a rope coming from P meets circle (c, r) and goes on round it (wrap +1 anticlockwise in the
    (x, z) plane, -1 clockwise)."""
    P, c = np.asarray(P, float), np.asarray(c, float)
    d = P - c
    L = float(np.linalg.norm(d))
    if L <= r:
        raise ValueError("point inside the circle")
    a = math.atan2(d[1], d[0])
    b = math.acos(r / L)
    for ang in (a + b, a - b):
        T = c + r * np.array([math.cos(ang), math.sin(ang)])
        if float((T - P) @ (wrap * _perp(T - c))) > 0:
            return T
    raise ValueError("no tangent")


def tangent_to_point(c, r: float, wrap: int, Q):
    """Point where a rope going round circle (c, r) with ``wrap`` leaves it towards Q."""
    Q, c = np.asarray(Q, float), np.asarray(c, float)
    d = Q - c
    L = float(np.linalg.norm(d))
    a = math.atan2(d[1], d[0])
    b = math.acos(r / L)
    for ang in (a + b, a - b):
        T = c + r * np.array([math.cos(ang), math.sin(ang)])
        if float((Q - T) @ (wrap * _perp(T - c))) > 0:
            return T
    raise ValueError("no tangent")


def tangent_circles(c1, r1: float, w1: int, c2, r2: float, w2: int):
    """Rope leaving circle 1 (wrap w1) to circle 2 (wrap w2): the two tangent points (fixed-point iteration)."""
    c1, c2 = np.asarray(c1, float), np.asarray(c2, float)
    T2 = c2.copy()
    for _ in range(60):
        T1 = tangent_to_point(c1, r1, w1, T2)
        T2n = tangent_from_point(T1, c2, r2, w2)
        if np.linalg.norm(T2n - T2) < 1e-9:
            T2 = T2n
            break
        T2 = T2n
    return tangent_to_point(c1, r1, w1, T2), T2


def rope_route(name: str, d: float, y: float, items: list, origin=None, udir=None) -> Route:
    """A rope in the vertical plane at ``y`` (x, z), or – with ``origin`` (x, y) and a horizontal ``udir`` – in the
    vertical plane through origin along udir (u, z): items are ("point", (x, z)) or ("sheave", (x, z), radius, wrap, info)
    with radius = the rope centre's radius on that sheave or drum. The first and last item are points or the
    first item a drum (the rope leaves it)."""
    pts2 = []                                  # list of (kind, data) resolved to 2D tangent points
    n = len(items)
    entry = [None] * n
    leave = [None] * n
    for i in range(n - 1):
        a, b = items[i], items[i + 1]
        if a[0] == "point" and b[0] == "point":
            leave[i], entry[i + 1] = np.asarray(a[1], float), np.asarray(b[1], float)
        elif a[0] == "point":
            leave[i] = np.asarray(a[1], float)
            entry[i + 1] = tangent_from_point(a[1], b[1], b[2], b[3])
        elif b[0] == "point":
            leave[i] = tangent_to_point(a[1], a[2], a[3], b[1])
            entry[i + 1] = np.asarray(b[1], float)
        else:
            leave[i], entry[i + 1] = tangent_circles(a[1], a[2], a[3], b[1], b[2], b[3])
    if udir is None:
        o3, u3 = np.array([0.0, y, 0.0]), np.array([1.0, 0.0, 0.0])
    else:
        o3, u3 = np.array([origin[0], origin[1], 0.0]), unit([udir[0], udir[1], 0.0])
    to3 = lambda q: o3 + q[0] * u3 + np.array([0.0, 0.0, q[1]])  # noqa: E731
    axis = np.cross(u3, [0.0, 0.0, 1.0])            # (u, z) anticlockwise turns about u x z
    r = Route(name, d)
    for i in range(n - 1):
        a = items[i]
        if a[0] == "sheave" and entry[i] is not None:
            c = np.asarray(a[1], float)
            u0, u1 = entry[i] - c, leave[i] - c
            ang = math.atan2(u0[0] * u1[1] - u0[1] * u1[0], u0 @ u1)
            if a[3] > 0 and ang < 0:
                ang += 2 * math.pi
            if a[3] < 0 and ang > 0:
                ang -= 2 * math.pi
            r.add(Arc(to3(c), a[3] * axis, to3(entry[i]), abs(ang)), support="sheave", **a[4])
        seg = Line(to3(leave[i]), to3(entry[i + 1]))
        if r.segments:
            r.add(seg, support="free")
        else:
            info = dict(items[0][4]) if items[0][0] == "sheave" else {}
            r.add(seg, support="free", **({"from": info.get("name")} if info else {}))
    return r
