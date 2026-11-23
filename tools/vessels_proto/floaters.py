"""Anything floats and can be hit (study 0312). No Blender.

A floating thing is a rigid body with a box-like shape (``Floater``: size, mass; a few columns under it measure how
deep each part of it lies in the water). At every step (``DT``):

* **buoyancy** = rho g x the submerged volume of each column (``NX`` x ``NY`` columns over its footprint), at the
  column's place: a column deeper in a crest pushes harder, so the thing heaves, pitches and rolls with the waves;
* **water drag** on the relative velocity of the water (the waves' orbital motion, ``core/sea``'s components) and the
  body: the waves carry it a little (Stokes drift), the current carries it, it stops drifting when the water does;
* **wind drag** on the part above the water;
* **hits**: a vessel's hull is a convex outline at the waterline (``Hull``), moving and turning with the vessel; a
  floater inside it is pushed out along the outline's normal with a bounce (restitution) and friction. The vessel is
  much heavier: it does not feel the hit (a RIB would: two-way, by mass ratio – ``two_way``). Floaters hit each
  other as circles of their half-diagonal (cheap: a container rarely meets a container).

Everything is worked out once at Build, a step at a time from the animation's first frame, and keyed: playing and
rendering need no Python (scripts off), and the same Build gives the same keys.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from fresing_render.core import sea as sea_core  # noqa: E402

RHO = 1025.0
G = 9.81
DT = 1.0 / 60.0
NX, NY, NZ = 4, 3, 3


def _rot(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


@dataclass
class Floater:
    name: str
    size: tuple            # (sx, sy, sz) m
    mass: float            # kg
    pos: np.ndarray        # centre (m)
    rpy: np.ndarray        # roll, pitch, yaw (rad)
    vel: np.ndarray = field(default_factory=lambda: np.zeros(3))
    w: np.ndarray = field(default_factory=lambda: np.zeros(3))     # roll, pitch, yaw rates
    cd: float = 1.0        # drag coefficient in water
    windage: float = 1.0
    cg: float = 0.0        # centre of gravity above the box's middle (m; cargo on the floor: negative)

    def __post_init__(self):
        sx, sy, sz = self.size
        self.inertia = self.mass / 12.0 * np.array([sy * sy + sz * sz, sx * sx + sz * sz, sx * sx + sy * sy])
        gx = (np.arange(NX) + 0.5) / NX - 0.5
        gy = (np.arange(NY) + 0.5) / NY - 0.5
        gz = (np.arange(NZ) + 0.5) / NZ - 0.5
        X, Y, Z = np.meshgrid(gx * sx, gy * sy, gz * sz, indexing="ij")
        self.cells = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])      # cell middles (body frame)
        self.cell_size = np.array([sx / NX, sy / NY, sz / NZ])
        self.cell_vol = sx * sy * sz / (NX * NY * NZ)
        self.cells[:, 2] -= self.cg                       # cells measured from the centre of gravity
        self.R = _rot(self.rpy)

    @property
    def floats(self) -> bool:
        return self.mass < RHO * np.prod(self.size)

    def draught_still(self) -> float:
        return self.mass / (RHO * self.size[0] * self.size[1])


@dataclass
class Hull:
    """A vessel's waterline outline (convex, body frame, anticlockwise) and its place per moment."""
    outline: np.ndarray            # n x 2
    draught: float
    track: np.ndarray              # recorded (t, x, y, heading, ...) samples
    mass: float = 1e6

    def at(self, t: float):
        tr = self.track
        i = int(np.clip(np.searchsorted(tr[:, 0], t), 1, len(tr) - 1))
        f = (t - tr[i - 1, 0]) / max(tr[i, 0] - tr[i - 1, 0], 1e-9)
        f = min(max(f, 0.0), 1.0)
        x = tr[i - 1, 1] + f * (tr[i, 1] - tr[i - 1, 1])
        y = tr[i - 1, 2] + f * (tr[i, 2] - tr[i - 1, 2])
        h = tr[i - 1, 3] + f * (tr[i, 3] - tr[i - 1, 3])
        dt = max(tr[i, 0] - tr[i - 1, 0], 1e-9)
        vx, vy, r = (tr[i, 1] - tr[i - 1, 1]) / dt, (tr[i, 2] - tr[i - 1, 2]) / dt, (tr[i, 3] - tr[i - 1, 3]) / dt
        return np.array([x, y]), h, np.array([vx, vy]), r


def hull_outline(length: float, beam: float, bow_share: float = 0.3, n: int = 24) -> np.ndarray:
    """A convex waterline: parallel sides and a rounded bow (x to the bow)."""
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((length / 2 - bow_share * length + bow_share * length * math.cos(a), beam / 2 * math.sin(a)))
    pts = [(-length / 2, -beam / 2)] + pts + [(-length / 2, beam / 2)]
    return np.array(pts, float)


def water(comps, x, y, z, t):
    """Height of the sea and the water's velocity (deep-water orbital motion) at points (x, y, z)."""
    h = np.zeros_like(x)
    u = np.zeros((len(x), 3))
    for (a, dx, dy, k, ph) in comps:
        w = math.sqrt(G * k)
        p = k * (dx * x + dy * y) + ph - w * t
        h += a * np.sin(p)
        dec = a * w * np.exp(np.minimum(k * z, 0.0))
        s = np.sin(p)
        u[:, 0] += dec * dx * s
        u[:, 1] += dec * dy * s
        u[:, 2] += -dec * np.cos(p)
    return h, u


class World:
    def __init__(self, comps, floaters, hulls=(), current=(0.0, 0.0), wind=(0.0, 0.0), restitution=0.2,
                 friction=0.4, extra_height=None):
        self.comps = comps
        self.f = floaters
        self.hulls = list(hulls)
        self.current = np.array([*current, 0.0])
        self.wind = np.array([*wind, 0.0])
        self.e, self.mu = restitution, friction
        self.t = 0.0
        self.hits = []
        self.extra = extra_height        # f(x, y, t) -> extra height (a vessel's own waves), or None

    def step(self, dt=DT):
        for b in self.f:
            self._float(b, dt)
        for hl in self.hulls:
            for b in self.f:
                self._hit_hull(b, hl)
        for i in range(len(self.f)):
            for j in range(i + 1, len(self.f)):
                self._hit_pair(self.f[i], self.f[j])
        self.t += dt

    def _float(self, b: Floater, dt: float):
        R = b.R
        sx, sy, sz = b.size
        wp = b.pos + b.cells @ R.T                            # cell middles in the world: any way up
        h, uw = water(self.comps, wp[:, 0], wp[:, 1], wp[:, 2], self.t)
        if self.extra is not None:
            h = h + self.extra(wp[:, 0], wp[:, 1], self.t)
        tall = np.abs(R[2, :]) @ b.cell_size                  # each cell's height seen in the world
        frac = np.clip((h - wp[:, 2]) / tall + 0.5, 0.0, 1.0)
        fb = RHO * G * b.cell_vol * frac
        F = np.array([0.0, 0.0, -b.mass * G + fb.sum()])
        arm = wp - b.pos
        M = np.cross(arm, np.column_stack([np.zeros_like(fb), np.zeros_like(fb), fb])).sum(axis=0)
        depth = frac
        sub = float(frac.mean())                              # share under water
        # water drag on the relative velocity (horizontal: the side area, vertical: the bottom)
        urel = uw.mean(axis=0) + self.current - b.vel
        area_h = max(sx, sy) * sz * sub
        F[:2] += 0.5 * RHO * b.cd * area_h * np.abs(urel[:2]) * urel[:2]
        F[2] += 0.5 * RHO * 1.2 * sx * sy * abs(urel[2]) * urel[2] * (sub > 0)
        # wind on the part above water
        wrel = self.wind - b.vel
        F[:2] += 0.5 * 1.225 * 1.1 * b.windage * max(sx, sy) * sz * (1 - sub) * np.abs(wrel[:2]) * wrel[:2]
        # rotational damping (water) – a floating box rolls a few times and settles
        Iw = R @ np.diag(b.inertia) @ R.T                     # inertia in the world
        M -= 0.4 * (2 * math.pi / 3.0) * (0.2 + sub) * (Iw @ b.w)
        b.vel = b.vel + F / b.mass * dt
        b.w = b.w + np.linalg.solve(Iw, M) * dt
        b.pos = b.pos + b.vel * dt
        ang = float(np.linalg.norm(b.w)) * dt
        if ang > 1e-12:
            k = b.w / np.linalg.norm(b.w)
            K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            b.R = (np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K) @ R
            u, _, vt = np.linalg.svd(b.R)
            b.R = u @ vt
        b.rpy = np.array([math.atan2(b.R[2, 1], b.R[2, 2]), -math.asin(max(-1.0, min(1.0, b.R[2, 0]))),
                          math.atan2(b.R[1, 0], b.R[0, 0])])

    def _hit_hull(self, b: Floater, hl: Hull):
        c, psi, v_h, r_h = hl.at(self.t)
        ca, sa = math.cos(psi), math.sin(psi)
        rel = b.pos[:2] - c
        p = np.array([ca * rel[0] + sa * rel[1], -sa * rel[0] + ca * rel[1]])       # body frame of the hull
        rad = 0.5 * min(b.size[0], b.size[1])
        tilt_up = b.pos[2]
        ol = hl.outline
        e = np.roll(ol, -1, axis=0) - ol
        nrm = np.column_stack([e[:, 1], -e[:, 0]])
        nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        d = ((p - ol) * nrm).sum(axis=1)                      # signed distance to each edge's line (out > 0)
        k = int(np.argmax(d))
        if d[k] > rad or b.pos[2] - b.size[2] / 2 > 1.5:      # outside (or above the hull's rail)
            return
        n_b = nrm[k]
        n_w = np.array([ca * n_b[0] - sa * n_b[1], sa * n_b[0] + ca * n_b[1]])
        push = rad - d[k]
        b.pos[:2] += n_w * push
        # the hull's velocity at the contact point
        cp = b.pos[:2] - c
        v_c = v_h + r_h * np.array([-cp[1], cp[0]])
        vr = b.vel[:2] - v_c
        vn = float(vr @ n_w)
        if vn < 0:
            jn = -(1 + self.e) * vn
            b.vel[:2] += jn * n_w
            vt = vr - vn * n_w
            tl = np.linalg.norm(vt)
            if tl > 1e-6:
                b.vel[:2] -= min(self.mu * jn, tl) * vt / tl
            b.w[2] += 0.3 * float(n_w[0] * vt[1] - n_w[1] * vt[0]) / max(rad, 0.5)
            self.hits.append((round(self.t, 2), b.name, round(-vn, 2)))

    def _hit_pair(self, a: Floater, b: Floater):
        ra = 0.5 * math.hypot(a.size[0], a.size[1]) * 0.8
        rb = 0.5 * math.hypot(b.size[0], b.size[1]) * 0.8
        d = b.pos[:2] - a.pos[:2]
        L = float(np.linalg.norm(d))
        if L >= ra + rb or L < 1e-9:
            return
        n = d / L
        over = ra + rb - L
        wa, wb = b.mass / (a.mass + b.mass), a.mass / (a.mass + b.mass)
        a.pos[:2] -= n * over * wa
        b.pos[:2] += n * over * wb
        vn = float((b.vel[:2] - a.vel[:2]) @ n)
        if vn < 0:
            j = -(1 + self.e) * vn / (1 / a.mass + 1 / b.mass)
            a.vel[:2] -= j / a.mass * n
            b.vel[:2] += j / b.mass * n
