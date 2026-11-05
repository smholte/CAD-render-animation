"""Hydraulic and electric cylinders: the geometry, without Blender (task 0013).

A cylinder hangs between two pins. The barrel turns about the pin on the machine side and aims at
the pin on the moving part; the rod points back along the same line and slides in or out so its
eye stays on its pin. Both pins turn about the same direction (a planar mechanism).

Words used here and in the panel:
* length  – distance between the two pin centres (pin to pin), in metres;
* closed length – that distance with the rod fully in (catalogue: "installation length");
* stroke  – how far the rod is out: length − closed length (0 = fully in);
* full stroke – the stroke with the rod fully out.

Drive mode: the owner sets the stroke and the arm's joint follows. For an arm on one pivot that is a
triangle (pivot, barrel pin, rod pin) with two fixed sides, solved with the law of cosines; for a
carriage on a slide it is a quadratic. Of the two solutions the one on the CAD pose's side is kept
(the arm never swings through the line of the cylinder).

All vectors are plain 3-tuples (or anything indexable); no numpy needed except for the travel
estimate, which ray-casts against the parts' triangles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-9
PARALLEL_TOL = math.radians(1.0)       # pin axes this close count as parallel


# ---------------------------------------------------------------------------
# small vector helpers
# ---------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n < EPS:
        raise ValueError("zero-length direction")
    return (a[0] / n, a[1] / n, a[2] / n)


def angle_between_lines(d1, d2) -> float:
    """Angle between two axis lines (0 … 90°, in radians): the sign of a direction does not matter."""
    c = abs(_dot(_unit(d1), _unit(d2)))
    return math.acos(min(1.0, c))


def parallel(d1, d2, tol: float = PARALLEL_TOL) -> bool:
    return angle_between_lines(d1, d2) <= tol


def into_plane(point, plane_point, normal):
    """``point`` moved along ``normal`` into the plane through ``plane_point`` (a pin centre slides
    along its own pin axis: the rod pin is taken where the barrel's mid-plane cuts it)."""
    n = _unit(normal)
    t = _dot(_sub(point, plane_point), n)
    return (point[0] - n[0] * t, point[1] - n[1] * t, point[2] - n[2] * t)


def axis_frame(barrel_pin, rod_pin, pin_axis):
    """Columns (x, y, z) of the cylinder's frame: x from the barrel pin towards the rod pin (made at
    right angles to the pin axis), z along the pin axis, y completing a right-handed frame."""
    z = _unit(pin_axis)
    d = _sub(rod_pin, barrel_pin)
    d = _sub(d, tuple(c * _dot(d, z) for c in z))
    x = _unit(d)
    y = _cross(z, x)
    return x, y, z


# ---------------------------------------------------------------------------
# drive mode: the stroke moves the arm
# ---------------------------------------------------------------------------

@dataclass
class Drive:
    """How the pin-to-pin length depends on the arm joint's value.

    Coordinates are in the joint's frame (its Z = the joint axis, origin on the axis), in metres:
    ``b`` the barrel pin (it does not move with the joint), ``r0`` the rod pin with the joint at 0.
    """
    kind: str                 # "ROTATE" (radians) or "SLIDE" (metres along the joint's Z)
    b: tuple
    r0: tuple

    def __post_init__(self):
        b, r = self.b, self.r0
        if self.kind == "ROTATE":
            self.a = math.hypot(b[0], b[1])              # pivot to barrel pin (in the plane)
            self.c = math.hypot(r[0], r[1])              # pivot to rod pin
            self.dz = r[2] - b[2]                        # pins out of each other's plane: stays constant
            if self.a < 1e-6 or self.c < 1e-6:
                raise ValueError("a pin sits on the arm's pivot axis: the cylinder cannot turn the arm")
            psi = math.atan2(r[1], r[0]) - math.atan2(b[1], b[0])
            self.psi0 = math.atan2(math.sin(psi), math.cos(psi))       # (-pi, pi]
            if abs(math.sin(self.psi0)) < 1e-4:
                raise ValueError("the cylinder points straight at the arm's pivot: it cannot turn the arm")
            self.sign = 1.0 if self.psi0 > 0 else -1.0
        elif self.kind == "SLIDE":
            w = _sub(r, b)
            self.w = w
            self.side2 = w[0] * w[0] + w[1] * w[1]
            if abs(w[2]) < 1e-3 * max(_norm(w), EPS):
                raise ValueError("the cylinder stands at right angles to the slide: it cannot push it")
            self.sign = 1.0 if w[2] > 0 else -1.0
        else:
            raise ValueError(f"unknown joint type {self.kind}")

    def length_at(self, value: float) -> float:
        """Pin-to-pin length with the joint at ``value`` (rad / m)."""
        if self.kind == "ROTATE":
            d2 = self.a * self.a + self.c * self.c - 2.0 * self.a * self.c * math.cos(self.psi0 + value)
            return math.sqrt(max(0.0, d2) + self.dz * self.dz)
        z = self.w[2] + value
        return math.sqrt(self.side2 + z * z)

    def reach(self) -> tuple[float, float]:
        """Shortest and longest length the mechanism allows (the arm's geometry, not the cylinder)."""
        if self.kind == "ROTATE":
            lo, hi = abs(self.a - self.c), self.a + self.c
            return math.hypot(lo, self.dz), math.hypot(hi, self.dz)
        return math.sqrt(self.side2), math.inf

    def value_for(self, length: float) -> float:
        """The joint value that gives this pin-to-pin length, on the CAD pose's side (rad / m).
        A length the mechanism cannot reach gives the nearest value it can."""
        lo, hi = self.reach()
        length = min(max(length, lo), hi)
        if self.kind == "ROTATE":
            d2 = max(0.0, length * length - self.dz * self.dz)
            cos_psi = (self.a * self.a + self.c * self.c - d2) / (2.0 * self.a * self.c)
            psi = self.sign * math.acos(min(1.0, max(-1.0, cos_psi)))
            return psi - self.psi0
        root = math.sqrt(max(0.0, length * length - self.side2))
        return -self.w[2] + self.sign * root

    def values_for_range(self, lo_len: float, hi_len: float) -> tuple[float, float]:
        """Joint limits for lengths between ``lo_len`` and ``hi_len`` (sorted)."""
        a, b = self.value_for(lo_len), self.value_for(hi_len)
        return (min(a, b), max(a, b))


# ---------------------------------------------------------------------------
# telescopic stages
# ---------------------------------------------------------------------------

def stage_shares(n: int) -> list[float]:
    """Share of the rod's extension each of ``n`` stages between the barrel and the rod takes
    (outer stage first): with 2 stages and the rod, 1/3 and 2/3 – every section slides out by the same
    amount, the way a coupling of 1 mm per mm between the sections would move them."""
    return [(i + 1) / (n + 1) for i in range(n)]


# ---------------------------------------------------------------------------
# how far the rod can travel: read from the parts' shapes
# ---------------------------------------------------------------------------

def _ray_first(origin, direction, tris, min_t: float = 1e-7):
    """Distance along the ray to the nearest triangle (both sides count), or None.
    ``tris``: numpy array (n, 3, 3)."""
    import numpy as np
    if tris is None or len(tris) == 0:
        return None
    o = np.asarray(origin, dtype=float)
    d = np.asarray(direction, dtype=float)
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-14
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    s = o - v0
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = (q @ d) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > min_t)
    if not hit.any():
        return None
    return float(t[hit].min())


@dataclass
class Travel:
    closed: float          # pin-to-pin length with the rod fully in (m)
    full: float            # full stroke (m)
    measured: bool         # True: from the piston and the barrel's end faces; False: a rough guess


def estimate_travel(barrel_tris, rod_tris, length: float) -> Travel:
    """Closed length and full stroke from the shapes, in the cylinder's frame (x along the axis from the
    barrel pin, the rod pin at x = ``length``; numpy arrays (n, 3, 3) of triangle corners, metres).

    The rod's inner end (the piston) can go back until it meets the barrel's bottom and out until its
    front meets the gland: both are found with rays parallel to the axis, a little inside the piston's
    rim (clear of the rod, which passes through the gland). When the shapes do not show that (no piston,
    simplified parts) the rod's inner end may travel between the barrel pin and the barrel's front end."""
    import numpy as np
    rod = np.asarray(rod_tris, dtype=float).reshape(-1, 3, 3)
    barrel = np.asarray(barrel_tris, dtype=float).reshape(-1, 3, 3)
    if len(rod) == 0 or len(barrel) == 0:
        return Travel(length, 0.0, False)
    rv = rod.reshape(-1, 3)
    x_back = float(rv[:, 0].min())                            # the rod's inner end
    rod_len = max(EPS, length - x_back)
    near = rv[rv[:, 0] <= x_back + 0.1 * rod_len]
    rp = float(np.hypot(near[:, 1], near[:, 2]).max()) if len(near) else 0.0
    bx = barrel.reshape(-1, 3)[:, 0]
    guess_in = max(0.0, x_back - max(0.0, float(bx.min())))
    guess_out = max(0.0, float(bx.max()) - x_back)
    ins, outs = [], []
    if rp > 1e-6:
        r = 0.85 * rp
        for k in range(8):
            a = k * math.pi / 4
            y, z = r * math.cos(a), r * math.sin(a)
            back = _ray_first((x_back + 1e-6, y, z), (-1.0, 0.0, 0.0), barrel)
            front_face = _ray_first((x_back + 1e-6, y, z), (1.0, 0.0, 0.0), rod)
            x_front = x_back + 1e-6 + front_face if front_face is not None and front_face < 0.5 * rod_len \
                else x_back
            gland = _ray_first((x_front - 1e-7, y, z), (1.0, 0.0, 0.0), barrel)
            if back is not None:
                ins.append(back + 1e-6)
            if gland is not None:
                outs.append(gland - 1e-7)
    measured = bool(ins) and bool(outs)
    travel_in = min(ins) if ins else guess_in
    travel_out = min(outs) if outs else guess_out
    travel_in = min(travel_in, max(0.0, length - 1e-3))       # never a closed length of 0
    return Travel(length - travel_in, travel_in + travel_out, measured)
