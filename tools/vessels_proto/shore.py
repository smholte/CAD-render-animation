"""Waves that feel the depth and break on a beach (study 0312). No Blender.

The open sea of ``core/sea.py`` is deep water: omega^2 = g k. Near a shore each wave component feels the bottom:

* **dispersion** omega^2 = g k tanh(k h): the same wave gets shorter and slower in shallow water;
* **refraction** (straight, parallel depth lines – a plain beach): the wave number along the shore stays the same
  (Snell), so a wave turns towards the beach as it slows;
* **shoaling**: the energy flux a^2 c_g cos(theta) stays the same: the wave grows as c_g drops;
* **breaking**: a wave can be at most ``GAMMA`` x the depth high (0.78, McCowan 1894); in the surf zone the height is
  held to it and the energy goes into foam (the share breaking: Battjes & Janssen 1978, simplified);
* **shape**: in shallow water crests sharpen and lean forward – a Gerstner (trochoidal) sideways move of the points
  whose strength grows from the open sea's to ``Q_SURF`` at breaking.

Everything depends on the distance across the shore only, so each component gets **two small tables** along that
distance (its phase so far, its amplitude factor) – ``Shore.tables`` – and the height at any point and moment stays a
sum of sines of the same components: ``core/sea.py``'s "one place" rule holds (the shader and the Geometry Nodes read
the same tables: an image 256 x 2N px in the shader, a hidden mesh's points in the nodes).

Coordinates: the beach runs along y, the land at +x. Depth h(x) = ``h0`` out at sea, then a plain slope up to the
waterline at ``x_shore``, dry land beyond.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

G = 9.81
GAMMA = 0.78
Q_OPEN, Q_SURF = 0.25, 0.85


def wavenumber(omega: float, h):
    """k of omega^2 = g k tanh(k h) (Newton, from the deep-water k), h > 0."""
    h = np.maximum(np.asarray(h, float), 1e-3)
    k0 = omega * omega / G
    k = np.maximum(k0, omega / np.sqrt(G * h))           # shallow-water guess
    for _ in range(30):
        th = np.tanh(k * h)
        f = G * k * th - omega * omega
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def group_speed(omega: float, k, h):
    kh = np.minimum(k * h, 50.0)
    return 0.5 * omega / k * (1 + 2 * kh / np.sinh(2 * kh))


@dataclass
class Shore:
    comps: list                  # core/sea components (amp, dx, dy, k, phase), dx toward the shore = +x
    h0: float = 30.0
    slope: float = 1 / 30
    x_shore: float = 0.0
    n: int = 512
    x_far: float = -600.0

    def depth(self, x):
        x = np.asarray(x, float)
        return np.clip((self.x_shore - x) * self.slope, 0.0, self.h0)

    def tables(self):
        """Per component: x samples, phase Phi(x) = int kx dx (zero at x_far), amplitude factor A(x), the
        component's own k(x) and the share of energy left after breaking; plus the foam share per x."""
        xs = np.linspace(self.x_far, self.x_shore + 2.0, self.n)
        h = self.depth(xs)
        wet = h > 0.02
        phase, amp, kx_all = [], [], []
        for (a, dx, dy, k_d, ph) in self.comps:
            w = math.sqrt(G * k_d)
            k_far = float(wavenumber(w, self.h0))
            ky = k_far * dy                                      # constant along the shore (Snell)
            k = wavenumber(w, np.where(wet, h, 1e-3))
            kx2 = k * k - ky * ky
            turned = kx2 <= 0
            kx = np.sqrt(np.maximum(kx2, 1e-12))
            cg = group_speed(w, k, np.where(wet, h, 1e-3))
            cg_far = float(group_speed(w, k_far, self.h0))
            cos0 = max(abs(k_far * dx) / k_far, 1e-3)
            cos = kx / k
            ks = np.sqrt(cg_far / cg)                            # shoaling
            kr = np.sqrt(cos0 / np.maximum(cos, 1e-3))           # refraction
            A = np.where(wet & ~turned, ks * kr, 0.0) * (dx > 0.05)     # waves running out to sea: none
            # the open sea (h0) is the reference: the far-field amplitude a was made for deep water; at h0 its
            # factor is the deep -> h0 shoaling, which we keep
            Phi = np.concatenate([[0.0], np.cumsum((kx[1:] + kx[:-1]) / 2 * np.diff(xs))])
            phase.append(Phi)
            amp.append(A)
            kx_all.append(kx)
        amp = np.array(amp)
        a0 = np.array([c[0] for c in self.comps])[:, None]
        hs = 4.0 * np.sqrt(0.5 * ((a0 * amp) ** 2).sum(axis=0))   # significant height per x
        limit = GAMMA * h
        sat = np.where(hs > limit, limit / np.maximum(hs, 1e-9), 1.0)
        # the share of breaking waves (Battjes–Janssen flavour): rises as Hs nears the limit
        r = np.clip(hs / np.maximum(limit, 1e-6), 0, 3)
        foam = np.clip((r - 0.55) / 0.45, 0, 1) ** 1.5 * wet
        q = Q_OPEN + (Q_SURF - Q_OPEN) * np.clip((r - 0.3) / 0.7, 0, 1)
        return xs, np.array(phase), amp * sat[None, :], np.array(kx_all), foam, q, hs * sat

    def surface(self, X, Y, t, tables=None):
        """Points of the surface (Gerstner: x, y moved, z the height) and the foam 0..1 at (X, Y) and time t."""
        xs, Phi, A, KX, foam, q, hs = tables if tables is not None else self.tables()
        Xc = np.clip(X, xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, Xc) - 1, 0, len(xs) - 2)
        f = (Xc - xs[i]) / (xs[i + 1] - xs[i])
        lerp = lambda arr: arr[..., i] * (1 - f) + arr[..., i + 1] * f   # noqa: E731
        Z = np.zeros_like(X)
        DX = np.zeros_like(X)
        DY = np.zeros_like(X)
        crest = np.zeros_like(X)
        qq = lerp(q)
        a_sum = 0.0
        for c, (a, dx, dy, k_d, ph) in enumerate(self.comps):
            w = math.sqrt(G * k_d)
            k_far = float(wavenumber(w, self.h0))
            ky = k_far * dy
            p = lerp(Phi[c]) + (X - Xc) * KX[c, -1] + ky * Y + ph - w * t
            amp = a * lerp(A[c])
            Z += amp * np.sin(p)
            kxx = lerp(KX[c])
            kk = np.sqrt(kxx * kxx + ky * ky) + 1e-9
            # Gerstner: points move towards the crest (sin peak at p = pi/2): forward lean in the surf
            DX += qq * amp * kxx / kk * np.cos(p) * -1.0
            DY += qq * amp * ky / kk * np.cos(p) * -1.0
            crest += amp * np.sin(p)
            a_sum += a
        fz = lerp(foam)
        hl = np.maximum(lerp(hs), 1e-3)
        white = fz * np.clip((crest / (0.3 * hl) - 0.1), 0, 1)        # foam on the crests in the surf zone
        white = np.maximum(white, fz * 0.18)                            # and the spent foam between them
        return X + DX, Y + DY, Z, np.clip(white, 0, 1)


def flux_check(sh: Shore):
    """a^2 c_g cos(theta) along x for every component, outside the surf zone: should stay constant."""
    xs, Phi, A, KX, foam, q, hs = sh.tables()
    h = sh.depth(xs)
    worst = 0.0
    for c, (a, dx, dy, k_d, ph) in enumerate(sh.comps):
        w = math.sqrt(G * k_d)
        k = wavenumber(w, np.maximum(h, 1e-3))
        cg = group_speed(w, k, np.maximum(h, 1e-3))
        cos = KX[c] / k
        fl = (a * A[c]) ** 2 * cg * cos
        ok = (foam == 0) & (h > 0.5) & (A[c] > 0)
        if ok.sum() > 2:
            worst = max(worst, float(np.ptp(fl[ok]) / max(fl[ok].mean(), 1e-12)))
    return worst
