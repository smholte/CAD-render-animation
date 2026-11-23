"""Study 0306 – ground with height, and where a wheel sits on it. No Blender.

The ground is a **height grid** (``Grid``): heights on a regular x/y grid, read bilinearly, all points at once. Every
kind of ground ends up as one: a flat floor with a speed bump (``speed_bump``), an off-road track (``offroad``), or
any meshes of the scene (an imported terrain, a CAD kerb) sampled once by rays straight down over the strip the
vehicle drives through (``blender_bake.py`` measures that). The ride solve then never asks Blender again.

A wheel is not a point: on a step or a bump it touches the edge with its round front long before its lowest point
is over it. ``wheel_centre_z`` puts a rigid disc of radius r on the ground: over the stretch -r … r along the
wheel's heading (and a few lines across the tyre's width) each ground point g at distance dx along it lifts the
centre to g + sqrt(r² - dx²); the centre sits at the highest of these ("rolling envelope").
"""

from __future__ import annotations

import math

import numpy as np


class Grid:
    """Heights z[i, j] at x = x0 + i * step, y = y0 + j * step (metres). Outside the grid: ``outside``."""

    def __init__(self, x0: float, y0: float, step: float, z: np.ndarray, outside: float = 0.0):
        self.x0, self.y0, self.step = float(x0), float(y0), float(step)
        self.z = np.asarray(z, float)
        self.outside = float(outside)

    @property
    def shape(self):
        return self.z.shape

    def height(self, x, y) -> np.ndarray:
        """Bilinear height at the points (any shape)."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        fi = (x - self.x0) / self.step
        fj = (y - self.y0) / self.step
        ni, nj = self.z.shape
        i = np.floor(fi).astype(np.int64)
        j = np.floor(fj).astype(np.int64)
        inside = (i >= 0) & (j >= 0) & (i < ni - 1) & (j < nj - 1)
        i = np.clip(i, 0, ni - 2)
        j = np.clip(j, 0, nj - 2)
        u = np.clip(fi - i, 0.0, 1.0)
        v = np.clip(fj - j, 0.0, 1.0)
        z = self.z
        h = ((1 - u) * (1 - v) * z[i, j] + u * (1 - v) * z[i + 1, j]
             + (1 - u) * v * z[i, j + 1] + u * v * z[i + 1, j + 1])
        return np.where(inside, h, self.outside)


def flat(x0=-20.0, y0=-20.0, x1=80.0, y1=20.0, step=0.05) -> Grid:
    ni = int(round((x1 - x0) / step)) + 1
    nj = int(round((y1 - y0) / step)) + 1
    return Grid(x0, y0, step, np.zeros((ni, nj)))


def speed_bump(g: Grid, x_mid: float, height: float = 0.075, length: float = 3.7, kind: str = "sine") -> Grid:
    """A bump across the road (all y) at ``x_mid``.

    kind "sine"     a round-top hump (cosine squared), as the long 'speed cushions' in towns: 75 mm over 3.7 m.
    kind "short"    a short hump, 70 mm over 0.9 m (a car park's): a hard knock at speed.
    kind "plateau"  ramps of 1:12 up to a flat top 2.5 m long (a raised crossing), height ``height``.
    """
    xs = g.x0 + np.arange(g.z.shape[0]) * g.step
    d = xs - x_mid
    if kind == "sine":
        h = np.where(np.abs(d) < length / 2, height * np.cos(np.pi * d / length) ** 2, 0.0)
    elif kind == "short":
        L = 0.9
        h = np.where(np.abs(d) < L / 2, height * np.cos(np.pi * d / L) ** 2, 0.0)
    elif kind == "plateau":
        top, ramp = 2.5, 12.0 * height
        a = np.abs(d)
        h = np.where(a < top / 2, height, np.where(a < top / 2 + ramp, height * (1 - (a - top / 2) / ramp), 0.0))
    else:
        raise ValueError(kind)
    out = Grid(g.x0, g.y0, g.step, g.z + h[:, None], g.outside)
    return out


def offroad(g: Grid, seed: int = 3, roughness: float = 0.08, x_from: float = 0.0, ruts: bool = True,
            pothole_every: float = 9.0) -> Grid:
    """An unpaved track from ``x_from`` on: smooth waves of a few metres (``roughness`` m), stones of a few cm,
    two ruts along it (wheel tracks 0.06 m deep), and potholes (0.12 m) now and then. Deterministic by ``seed``."""
    rng = np.random.default_rng(seed)
    ni, nj = g.z.shape
    xs = g.x0 + np.arange(ni) * g.step
    ys = g.y0 + np.arange(nj) * g.step
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    z = np.zeros_like(X)
    # sum of a few long and short waves (a cheap "fractal" ground)
    for wl, amp in ((14.0, 1.0), (6.0, 0.55), (2.7, 0.3), (1.1, 0.12), (0.45, 0.05)):
        for _ in range(3):
            a = rng.uniform(0, 2 * np.pi)
            k = 2 * np.pi / wl * np.array([math.cos(a), math.sin(a)])
            z += amp * np.sin(k[0] * X + k[1] * Y + rng.uniform(0, 2 * np.pi)) / 3
    z *= roughness / 1.0
    if ruts:
        for yc in (-0.85, 0.85):
            z -= 0.06 * np.exp(-((Y - yc) / 0.18) ** 2)
    if pothole_every:
        for xc in np.arange(x_from + pothole_every / 2, xs[-1], pothole_every):
            yc = rng.choice([-0.85, 0.85]) + rng.uniform(-0.2, 0.2)
            r2 = (X - xc) ** 2 + (Y - yc) ** 2
            z -= 0.12 * np.clip(1 - r2 / 0.35 ** 2, 0, 1) ** 0.5
    ramp = np.clip((X - x_from) / 5.0, 0.0, 1.0)          # flat road before x_from, blend over 5 m
    return Grid(g.x0, g.y0, g.step, g.z + z * ramp, g.outside)


def wheel_centre_z(g: Grid, cx, cy, heading, r: float, width: float, n_along: int = 13, n_across: int = 3):
    """Height of a rigid wheel's centre resting on the ground (rolling envelope), for many wheels / moments at once.

    cx, cy, heading: arrays (same shape): where the wheel's centre is over the ground and which way it rolls.
    Returns (z_centre, z_contact_ground) – the centre height and the ground height right below it.
    """
    cx = np.asarray(cx, float)
    cy = np.asarray(cy, float)
    hd = np.asarray(heading, float)
    fwd = np.stack([np.cos(hd), np.sin(hd)], -1)
    side = np.stack([-np.sin(hd), np.cos(hd)], -1)
    dx = np.linspace(-r * 0.98, r * 0.98, n_along)
    dw = np.linspace(-width / 2, width / 2, n_across) if n_across > 1 else np.zeros(1)
    lift = np.sqrt(np.maximum(r * r - dx * dx, 0.0))                     # (A,)
    # points: (..., A, W, 2)
    px = (cx[..., None, None] + fwd[..., None, None, 0] * dx[:, None] + side[..., None, None, 0] * dw[None, :])
    py = (cy[..., None, None] + fwd[..., None, None, 1] * dx[:, None] + side[..., None, None, 1] * dw[None, :])
    h = g.height(px, py)                                                 # (..., A, W)
    zc = (h + lift[:, None]).max(axis=(-2, -1))
    return zc, g.height(cx, cy)
