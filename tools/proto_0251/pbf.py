"""Prototype 0251, method b: particles baked at Build – Position Based Fluids (Macklin & Mueller 2013) in NumPy.

Each particle is a parcel of liquid ``s`` mm across. Collision with the moving plate/block and the fixed tray uses their
height maps (a particle that comes from above lands on the surface, one that moves sideways into a step is put back).
Drawn as a surface by Geometry Nodes (Points to Volume -> Volume to Mesh). Deterministic: no random numbers.

    ~/venv/bin/python tools/proto_0251/pbf.py /tmp/p251/s_pbf.npz [spacing_mm]
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import scene_s as S  # noqa: E402

MM = 1e-3
G = 9.81


class HField:
    """Height map lookup for collisions: bed (ny, nx), cell, x0, y0; NaN = no surface (a hole)."""

    def __init__(self, bed, cell, x0, y0, walls=False):
        self.bed, self.cell, self.x0, self.y0, self.walls = bed, cell, x0, y0, walls
        self.ny, self.nx = bed.shape

    def lookup(self, x, y):
        i = np.round((x - self.x0) / self.cell).astype(np.int64)
        j = np.round((y - self.y0) / self.cell).astype(np.int64)
        ok = (i >= 0) & (j >= 0) & (i < self.nx) & (j < self.ny)
        b = np.full(x.shape, -np.inf)
        b[ok] = self.bed[j[ok], i[ok]]
        b[np.isnan(b)] = -np.inf
        return b, ok

    def collide(self, p, p_old):
        """p, p_old in this field's frame; returns p moved out of the surface, and a contact mask."""
        b, ok = self.lookup(p[:, 0], p[:, 1])
        if self.walls:
            lo = (self.x0 - self.cell / 2, self.y0 - self.cell / 2)
            hi = (self.x0 + (self.nx - 0.5) * self.cell, self.y0 + (self.ny - 0.5) * self.cell)
            inside_old = ((p_old[:, 0] > lo[0]) & (p_old[:, 0] < hi[0]) & (p_old[:, 1] > lo[1]) &
                          (p_old[:, 1] < hi[1]) & (p_old[:, 2] < self.top))
            for k in (0, 1):
                p[:, k] = np.where(inside_old, np.clip(p[:, k], lo[k] + 1e-4, hi[k] - 1e-4), p[:, k])
            b, ok = self.lookup(p[:, 0], p[:, 1])
        below = ok & (p[:, 2] < b)
        if not below.any():
            return p, below
        bo, _ = self.lookup(p_old[:, 0], p_old[:, 1])
        b_new_at_old, _ = b, None
        # came from above (it was above this cell's surface before): land on it
        from_above = below & (p_old[:, 2] >= b - 0.6 * self.cell)
        p[from_above, 2] = b[from_above]
        # moved sideways into a step: go back to the old x, y (and keep above the old cell)
        side = below & ~from_above
        p[side, 0] = p_old[side, 0]
        p[side, 1] = p_old[side, 1]
        bo2, ok2 = self.lookup(p[side, 0], p[side, 1])
        z = p[side, 2]
        p[side, 2] = np.where(ok2 & (z < bo2), bo2, z)
        return p, below


def kernels(h):
    poly6 = 315.0 / (64.0 * math.pi * h ** 9)
    spiky = -45.0 / (math.pi * h ** 6)
    return poly6, spiky


def neighbours(p, h):
    """All pairs (i, j), i != j, closer than h: cell hashing + sorting (NumPy only)."""
    c = np.floor(p / h).astype(np.int64)
    c -= c.min(0)
    dims = c.max(0) + 3
    key = (c[:, 0] + 1) + dims[0] * ((c[:, 1] + 1) + dims[1] * (c[:, 2] + 1))
    order = np.argsort(key, kind="stable")
    ks = key[order]
    I, J = [], []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                k2 = key + dx + dims[0] * (dy + dims[1] * dz)
                a = np.searchsorted(ks, k2, "left")
                b = np.searchsorted(ks, k2, "right")
                n = b - a
                if not n.any():
                    continue
                ii = np.repeat(np.arange(len(p)), n)
                start = np.repeat(a, n)
                off = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
                jj = order[start + off]
                I.append(ii)
                J.append(jj)
    I = np.concatenate(I)
    J = np.concatenate(J)
    m = I != J
    I, J = I[m], J[m]
    d = p[I] - p[J]
    r2 = (d * d).sum(1)
    m = r2 < h * h
    return I[m], J[m]


class PBF:
    def __init__(self, spacing, fields, mats, fps, drain=None, floor_z=-0.05, iters=3, sub=8):
        self.s = spacing
        self.h = 2.1 * spacing
        self.fields = fields          # list of HField
        self.mats = mats              # list of (frames, 4, 4) world-from-field
        self.fps = fps
        self.drain = drain            # (x, y, r, z_top) world
        self.floor_z = floor_z
        self.iters, self.sub = iters, sub
        self.p = np.zeros((0, 3))
        self.v = np.zeros((0, 3))
        self.poly6, self.spiky = kernels(self.h)
        # rest density from a full lattice
        g = np.arange(-3, 4) * spacing
        X, Y, Z = np.meshgrid(g, g, g)
        r2 = X ** 2 + Y ** 2 + Z ** 2
        self.rho0 = float((self.poly6 * np.maximum(self.h ** 2 - r2, 0) ** 3).sum())
        self.drained = 0
        self.lost = 0
        self.emitted = 0
        self._acc = 0.0

    def emit(self, p, q, dt, t, radius=3.2e-3):
        """A jet at p, q m^3/s: layers of particles on a disc (spacing s) moving down at the speed that gives q."""
        if not hasattr(self, "_disc"):
            g = np.arange(-6, 7) * self.s
            X, Y = np.meshgrid(g, g)
            m = X ** 2 + Y ** 2 <= radius ** 2
            self._disc = np.stack([X[m], Y[m]], 1)
        nd = len(self._disc)
        speed = q / (nd * self.s ** 2)
        self._acc += speed * dt / self.s
        n = int(self._acc)
        if n <= 0:
            return
        self._acc -= n
        pts = []
        for k in range(n):
            z = p[2] - k * self.s
            pts.append(np.column_stack([p[0] + self._disc[:, 0], p[1] + self._disc[:, 1], np.full(nd, z)]))
        pts = np.vstack(pts)
        self.p = np.vstack([self.p, pts])
        self.v = np.vstack([self.v, np.tile([0.0, 0.0, -speed], (len(pts), 1))])
        self.emitted += len(pts)

    def _mat(self, k, t):
        m = self.mats[k]
        x = t * self.fps
        f0 = int(min(max(math.floor(x), 0), len(m) - 2))
        a = x - f0
        return m[f0] * (1 - a) + m[f0 + 1] * a

    def step(self, t, dt):
        p_old = self.p.copy()
        self.v[:, 2] -= G * dt
        p = self.p + self.v * dt
        n = len(p)
        if n:
            I, J = neighbours(p, self.h)
            h2 = self.h * self.h
            for _ in range(self.iters):
                d = p[I] - p[J]
                r2 = (d * d).sum(1)
                r = np.sqrt(np.maximum(r2, 1e-18))
                w = self.poly6 * np.maximum(h2 - r2, 0) ** 3
                rho = np.bincount(I, w, n) + self.poly6 * h2 ** 3
                C = rho / self.rho0 - 1.0
                gr = (self.spiky * (self.h - r) ** 2 / r)[:, None] * d / self.rho0
                sum_g2 = np.bincount(I, (gr * gr).sum(1), n)
                gi = np.zeros((n, 3))
                for k in range(3):
                    gi[:, k] = np.bincount(I, gr[:, k], n)
                lam = -np.maximum(C, 0) / (sum_g2 + (gi * gi).sum(1) + 200.0)
                # artificial pressure against clumping (tensile instability)
                wq = self.poly6 * (h2 - (0.2 * self.h) ** 2) ** 3
                scorr = -0.001 * (w / wq) ** 4
                coef = (lam[I] + lam[J] + scorr)[:, None] * gr
                dp = np.zeros((n, 3))
                for k in range(3):
                    dp[:, k] = np.bincount(I, coef[:, k], n)
                lim = 0.4 * self.s
                mag = np.linalg.norm(dp, axis=1, keepdims=True)
                dp *= np.minimum(1.0, lim / np.maximum(mag, 1e-12))
                p = p + dp
                p = self._collide(p, p_old, t + dt)
            # velocity, XSPH viscosity
            v = (p - p_old) / dt
            d = p[I] - p[J]
            r2 = (d * d).sum(1)
            w = self.poly6 * np.maximum(h2 - r2, 0) ** 3 / self.rho0
            dv = np.zeros((n, 3))
            for k in range(3):
                dv[:, k] = np.bincount(I, (v[J, k] - v[I, k]) * w, n)
            v = v + 0.05 * dv
            sp = np.linalg.norm(v, axis=1, keepdims=True)
            v *= np.minimum(1.0, 3.0 / np.maximum(sp, 1e-12))     # no particle faster than 3 m/s
            self.p, self.v = p, v
        # drain, floor
        keep = np.ones(len(self.p), bool)
        if self.drain is not None:
            dx, dy, rr, zt = self.drain
            inn = ((self.p[:, 0] - dx) ** 2 + (self.p[:, 1] - dy) ** 2 < rr * rr) & (self.p[:, 2] < zt + self.s)
            self.drained += int(inn.sum())
            keep &= ~inn
        low = self.p[:, 2] < self.floor_z
        self.lost += int((low & keep).sum())
        keep &= ~low
        self.p, self.v = self.p[keep], self.v[keep]

    def _collide(self, p, p_old, t):
        for k, fld in enumerate(self.fields):
            M = self._mat(k, t)
            Mi = np.linalg.inv(M)
            q = p @ Mi[:3, :3].T + Mi[:3, 3]
            # the old position as it sat on the surface (the surface moved under it: carry it along)
            Mo = self._mat(k, t - 1.0 / (self.fps * self.sub))
            qo = p_old @ np.linalg.inv(Mo)[:3, :3].T + np.linalg.inv(Mo)[:3, 3]
            q, hit = fld.collide(q, qo)
            if hit.any():
                # friction: what touches the surface moves with it (sliding damped)
                q[hit, :2] = qo[hit, :2] + 0.8 * (q[hit, :2] - qo[hit, :2])
            p = q @ M[:3, :3].T + M[:3, 3]
        return p


def bake_s(spacing=2.0 * MM, out=None):
    cell = 1.0 * MM
    bed, x0, y0 = S.plate_bed(cell)
    plate = HField(bed, cell, x0, y0)
    tb, tx0, ty0, drain = S.tray_bed(2 * MM)
    tray = HField(tb, 2 * MM, tx0, ty0, walls=True)
    tray.top = S.TRAY[5]
    dx, dy, r = S.DRAIN
    sim = PBF(spacing, [plate, tray], [S.plate_mats(), np.repeat(np.eye(4)[None], S.FRAMES + 2, 0)], S.FPS,
              drain=(dx, dy, r, float(tb.min()) + 0.002))
    P, n, counts = [], [], []
    t0 = time.perf_counter()
    T = 1.0 / S.FPS
    for f in range(S.FRAMES):
        P.append(sim.p.astype(np.float32))
        counts.append(len(sim.p))
        for k in range(sim.sub):
            t = f * T + k * T / sim.sub
            for src in S.jet_sources(f):
                sim.emit(np.array(src[0]), src[1], T / sim.sub, t)
            sim.step(t, T / sim.sub)
        if f % 24 == 0:
            print(f, len(sim.p), round(time.perf_counter() - t0, 1), flush=True)
    secs = time.perf_counter() - t0
    if out:
        np.savez_compressed(out, pos=np.concatenate(P), counts=np.array(counts), spacing=spacing, seconds=secs,
                            emitted=sim.emitted, drained=sim.drained, lost=sim.lost)
    return sim, secs, counts


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/p251/s_pbf.npz"
    sp = float(sys.argv[2]) * MM if len(sys.argv) > 2 else 2.0 * MM
    sim, secs, counts = bake_s(sp, out)
    print("bake s", round(secs, 1), "per frame ms", round(1000 * secs / S.FRAMES), "max particles", max(counts),
          "emitted", sim.emitted, "drained", sim.drained, "lost", sim.lost)
