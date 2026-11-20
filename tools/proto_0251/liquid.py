"""Prototype 0251 (findings only): coolant liquid as a shallow-liquid height field. No Blender here.

The liquid lives on **charts**: a regular grid of cells laid over a surface, in the surface's own frame (a chart rides
with the part / table / tray that carries it). Each cell has a bed height (the surface, from a height map of the cut part
and the table) and a liquid depth. The flow between neighbouring cells is the *virtual pipe* model (O'Brien & Hodgins
1995, Mei et al. 2007) with the pipe's area = the liquid's depth on the face (so waves travel at sqrt(g h) as in the
shallow-water equations) and laminar wall friction 3 nu / h^2 (so a film on a slope runs off at the Nusselt rate
g sin(theta) h^3 / 3 nu and a slosh settles).

Moving with the machine: the chart's frame moves with its carrier; each frame the *effective gravity* of every cell is
g - a(cell) (a = the cell centre's world acceleration, from three places of the carrier's matrix), turned into the
chart's frame: its normal part presses the liquid onto the surface, its tangential part drives it along (a table that
stops hard throws the liquid forward; a tilted cradle runs it to the low side; a turning table flings it outwards).
Where the normal part points away from the surface (upside down) the liquid drips off.

Liquid that leaves a chart over an open edge or drips off becomes **drops** (ballistic, world space) that land on the
next chart below (a table, a tray) or the floor. A tray chart has **drain** cells (an orifice: Q = Cd a sqrt(2 g h)).

Everything is baked once over the whole animation (frame by frame, fixed sub-steps, no random numbers): frame f always
shows the same liquid whatever was shown before (0042's rule). Metres, seconds, m^3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

G = 9.81
NU = 1.0e-6          # kinematic viscosity of a water-based emulsion, m^2/s
FILM = 0.04e-3       # this much stays on a wetted surface (it does not flow; it dries)
SHOW = 0.06e-3       # thinner than this is drawn as dry (the wet sheen shows it)
STOKES = math.sqrt(NU * 2 * math.pi)   # oscillating flow: the wall's boundary layer (Stokes layer at ~1 Hz) brakes it
WEIR = 1.5          # critical flow factor (see step)
CD = 0.62            # orifice discharge coefficient (sharp-edged hole)


@dataclass
class Chart:
    """A grid of cells on one surface. ``bed``: (ny, nx) surface heights in the chart's frame (m), NaN = no surface
    there (outside the part: an open edge). Cell (j, i) has its centre at (x0 + i*cell, y0 + j*cell)."""
    name: str
    bed: np.ndarray
    cell: float
    x0: float = 0.0
    y0: float = 0.0
    open_edges: bool = True          # liquid runs off where the surface ends (False: a tray with walls)
    drain: np.ndarray | None = None  # (ny, nx) orifice area per cell (m^2)
    catches: bool = True             # drops landing on it stay on it
    depth: np.ndarray = field(init=False)

    def __post_init__(self):
        self.bed = np.asarray(self.bed, float)
        self.depth = np.zeros_like(self.bed)
        self.drained = 0.0
        self.edge_out = np.zeros_like(self.bed)   # volume that left over an open edge, per cell (reset by the caller)
        self.dripped = np.zeros_like(self.bed)    # volume that dripped off (upside down), per cell
        self.side = np.zeros(self.bed.shape, np.int8)   # the edge it left by (0..3) for the drop's direction
        ny, nx = self.bed.shape
        self.qx = np.zeros((ny, nx + 1))
        self.qy = np.zeros((ny + 1, nx))
        self._hole = np.isnan(self.bed)
        self.rain = np.zeros_like(self.bed)     # depth landing during the next frame, added evenly per sub-step

    # --- geometry --------------------------------------------------------------------------------------------
    @property
    def shape(self):
        return self.bed.shape

    def centres(self) -> np.ndarray:
        ny, nx = self.shape
        x = self.x0 + np.arange(nx) * self.cell
        y = self.y0 + np.arange(ny) * self.cell
        X, Y = np.meshgrid(x, y)
        B = np.where(np.isnan(self.bed), np.nanmin(self.bed) if np.isfinite(self.bed).any() else 0.0, self.bed)
        return np.stack([X, Y, B], -1)

    def index(self, x, y):
        i = np.round((np.asarray(x) - self.x0) / self.cell).astype(int)
        j = np.round((np.asarray(y) - self.y0) / self.cell).astype(int)
        ok = (i >= 0) & (j >= 0) & (i < self.shape[1]) & (j < self.shape[0])
        return j, i, ok

    def volume(self) -> float:
        return float(np.nansum(self.depth) * self.cell ** 2)

    def set_bed(self, bed):
        """The surface changed (the cut went deeper): keep the liquid's depth where there still is a surface."""
        bed = np.asarray(bed, float)
        lost = np.isnan(bed) & ~np.isnan(self.bed)
        spill = float(self.depth[lost].sum() * self.cell ** 2)
        self.depth[lost] = 0.0
        self.bed = bed
        self._hole = np.isnan(bed)
        return spill

    def add(self, x, y, vol, spread=1):
        """Pour ``vol`` m^3 at (x, y) (chart frame), spread over (2*spread+1)^2 cells. Returns what found no surface."""
        j, i, ok = self.index(x, y)
        if not ok:
            return vol
        js = slice(max(j - spread, 0), j + spread + 1)
        is_ = slice(max(i - spread, 0), i + spread + 1)
        m = ~np.isnan(self.bed[js, is_])
        n = int(m.sum())
        if n == 0:
            return vol
        self.depth[js, is_][m] += vol / n / self.cell ** 2
        return 0.0

    # --- one step ----------------------------------------------------------------------------------------------
    def step(self, dt, gx, gy, gn):
        """Advance by ``dt``. gx, gy: the effective gravity along the chart's x / y (m/s^2, scalar or per cell);
        gn: its part pressing onto the surface (> 0 = the surface faces up). Signed fluxes on the cell faces
        (a staggered grid): Qx[j, k] flows from cell k-1 to cell k (+x), k = 0 and nx are the grid's edges."""
        l = self.cell
        bed = self.bed
        hole = self._hole
        d = self.depth
        shp = d.shape
        gx = np.broadcast_to(np.asarray(gx, float), shp)
        gy = np.broadcast_to(np.asarray(gy, float), shp)
        gn = np.broadcast_to(np.asarray(gn, float), shp)
        gnp = np.maximum(gn, 0.0)
        he = np.maximum(d - FILM, 0.0)
        he[hole] = 0.0
        E = bed + d                              # NaN where there is no surface
        lost = np.zeros(shp)
        Qs = []
        for axis, gb, Q in ((1, gx, self.qx), (0, gy, self.qy)):
            pw = [(0, 0), (0, 0)]
            pw[axis] = (1, 1)
            Ep = np.pad(E, pw, constant_values=np.nan)
            hp = np.pad(he, pw)
            gnp_p = np.pad(gnp, pw, mode="edge")
            gb_p = np.pad(gb, pw, mode="edge")
            if axis == 1:
                A, B = (slice(None), slice(0, -1)), (slice(None), slice(1, None))
            else:
                A, B = (slice(0, -1), slice(None)), (slice(1, None), slice(None))
            EL, ER = Ep[A], Ep[B]
            hL, hR = hp[A], hp[B]
            vL, vR = ~np.isnan(EL), ~np.isnan(ER)
            both = vL & vR
            hf = np.where(both, 0.5 * (hL + hR), np.where(vL, hL, hR))
            dE = np.where(both, EL - ER, np.where(vL, hL, -hR))
            dE = np.nan_to_num(dE)
            acc = 0.5 * (gnp_p[A] + gnp_p[B]) * dE / l + 0.5 * (gb_p[A] + gb_p[B])
            Q += dt * l * hf * acc
            hh = np.maximum(hf, 2e-5)
            Q /= 1.0 + dt * (3.0 * NU / hh ** 2 + STOKES / hh)
            # never more than critical flow over a weir from the upstream cell (q = 1.5 l sqrt(g) h^1.5): over a step
            # down (a cliff, a pocket's rim) the top cell otherwise empties in one step and fills again (rings)
            gq = np.sqrt(0.5 * (gnp_p[A] + gnp_p[B]))
            Q[:] = np.clip(Q, -WEIR * l * gq * hR ** 1.5, WEIR * l * gq * hL ** 1.5)
            if self.open_edges:
                Q[:] = np.where(both, Q, np.where(vL & ~vR, np.maximum(Q, 0), np.where(~vL & vR, np.minimum(Q, 0), 0)))
            else:
                Q[~both] = 0.0
            Q[hf <= 0] = 0.0
            Qs.append((axis, Q, both))
        # never take more than a cell holds above its film
        out = np.zeros(shp)
        for axis, Q, _ in Qs:
            if axis == 1:
                out += np.maximum(Q[:, 1:], 0) + np.maximum(-Q[:, :-1], 0)
            else:
                out += np.maximum(Q[1:, :], 0) + np.maximum(-Q[:-1, :], 0)
        need = out * dt
        K = np.ones(shp)
        m = need > he * l * l
        K[m] = he[m] * l * l / need[m]
        for axis, Q, both in Qs:
            pw = [(0, 0), (0, 0)]
            pw[axis] = (1, 1)
            Kp = np.pad(K, pw, constant_values=1.0)
            if axis == 1:
                KL, KR = Kp[:, :-1], Kp[:, 1:]
            else:
                KL, KR = Kp[:-1, :], Kp[1:, :]
            Q *= np.where(Q > 0, KL, KR)
            # what crosses a face into no surface leaves the chart
            if axis == 1:
                to_right = np.maximum(Q[:, 1:], 0) * ~both[:, 1:]
                to_left = np.maximum(-Q[:, :-1], 0) * ~both[:, :-1]
                d -= dt * (Q[:, 1:] - Q[:, :-1]) / (l * l)
                self.side[to_right > 0] = 1
                self.side[to_left > 0] = 0
            else:
                to_right = np.maximum(Q[1:, :], 0) * ~both[1:, :]
                to_left = np.maximum(-Q[:-1, :], 0) * ~both[:-1, :]
                d -= dt * (Q[1:, :] - Q[:-1, :]) / (l * l)
                self.side[to_right > 0] = 3
                self.side[to_left > 0] = 2
            lost += (to_right + to_left) * dt
        d[hole] = 0.0
        self.edge_out += lost
        # upside down: it drips off within ~0.15 s (the film stays)
        down = (gn <= 0.05 * G) & ~hole
        if down.any():
            share = min(1.0, dt / 0.15)
            v = np.maximum(d - FILM, 0.0) * down * share
            d -= v
            self.dripped += v * l * l
        # drains
        if self.drain is not None:
            q = CD * self.drain * np.sqrt(2.0 * gnp * np.maximum(d, 0.0)) * dt
            q = np.minimum(q, d * l * l)
            d -= q / (l * l)
            self.drained += float(q.sum())
        np.maximum(d, 0.0, out=d)

    def max_dt(self, gn):
        h = float(np.nanmax(self.depth)) if self.depth.size else 0.0
        c = math.sqrt(max(float(np.max(gn)), 1.0) * max(h, 1e-4))
        return 0.45 * self.cell / c


# ---------------------------------------------------------------------------------------------------------------
# a whole set-up: charts that move, drops between them, sources (the jets)
# ---------------------------------------------------------------------------------------------------------------

class World:
    """Charts with their per-frame matrices (world from chart), a floor height, a frame rate.

    ``mats[c]``: (frames, 4, 4) world-from-chart matrices; ``fps``. ``sources(f)`` -> list of (world xyz, m^3/s).
    """

    def __init__(self, charts, mats, fps, floor_z, sources=None, substeps=None):
        self.charts = charts
        self.mats = [np.asarray(m, float) for m in mats]
        self.fps = float(fps)
        self.floor_z = floor_z
        self.sources = sources or (lambda f: [])
        self.P = np.zeros((0, 3)); self.V = np.zeros((0, 3)); self.vol = np.zeros(0); self.src = np.zeros(0, int)
        self.floor = 0.0
        self.poured = 0.0
        self.substeps = substeps
        self.frames = self.mats[0].shape[0]
        self._c = [c.centres().reshape(-1, 3) for c in charts]

    def mat(self, c, f):
        f = min(max(f, 0), self.frames - 1)
        return self.mats[c][f]

    def gravity(self, c, f):
        """Effective gravity of every cell of chart c at frame f, in the chart's frame: (gx, gy, gn)."""
        h = 1.0 / self.fps
        P = [self._c[c] @ self.mat(c, k)[:3, :3].T + self.mat(c, k)[:3, 3] for k in (f - 1, f, f + 1)]
        a = (P[2] - 2 * P[1] + P[0]) / (h * h)
        if f <= 0 or f >= self.frames - 1:
            a[:] = 0.0
        g = np.array([0.0, 0.0, -G]) - a
        R = self.mat(c, f)[:3, :3]
        gl = g @ R             # = R^T g per row
        shp = self.charts[c].shape
        return gl[:, 0].reshape(shp), gl[:, 1].reshape(shp), (-gl[:, 2]).reshape(shp)

    def velocity(self, c, f, pts_local):
        h = 1.0 / self.fps
        A, B = self.mat(c, f), self.mat(c, f + 1)
        pa = pts_local @ A[:3, :3].T + A[:3, 3]
        pb = pts_local @ B[:3, :3].T + B[:3, 3]
        return (pb - pa) / h

    def run_frame(self, f):
        """Advance from frame f to f+1."""
        T = 1.0 / self.fps
        grav = [self.gravity(c, f) for c in range(len(self.charts))]
        # sources: the jets pour onto whatever lies below them (a drop from the nozzle's tip that lands at once)
        for p, q in self.sources(f):
            self.poured += q * T
            self._pour(np.array(p, float), q * T, f)
        # charts, sub-stepped
        for c, ch in enumerate(self.charts):
            ch.edge_out[:] = 0.0
            ch.dripped[:] = 0.0
            gx, gy, gn = grav[c]
            n = self.substeps or max(1, math.ceil(T / ch.max_dt(gn)))
            rain = ch.rain / n
            ch.rain = np.zeros_like(ch.rain)
            for _ in range(n):
                ch.depth += rain
                ch.step(T / n, gx, gy, gn)
            # what left becomes drops (one per cell that lost liquid)
            lost = ch.edge_out + ch.dripped
            js, is_ = np.nonzero(lost > 0)
            if len(js):
                ctr = ch.centres()
                loc = ctr[js, is_].copy()
                loc[:, 2] += ch.depth[js, is_] * 0.5
                off = np.array([(-1, 0), (1, 0), (0, -1), (0, 1)], float)[ch.side[js, is_]] * ch.cell * 0.6
                drip = ch.dripped[js, is_] > ch.edge_out[js, is_]
                loc[~drip, :2] += off[~drip]
                M = self.mat(c, f + 1)
                wp = loc @ M[:3, :3].T + M[:3, 3]
                wv = self.velocity(c, f, loc)
                out_dir = np.zeros_like(loc)
                out_dir[:, :2] = off / (ch.cell * 0.6)
                wv += (out_dir @ M[:3, :3].T) * 0.05 * (~drip)[:, None]
                self._spawn(wp, wv, lost[js, is_], c)
        # drops fly for one frame (4 sub-steps) and land on the first chart they meet
        self._fly(f + 1, T)

    def _pour(self, p, vol, f):
        """A jet: a steady stream straight down from p – it lands (this frame) on the highest catching surface
        under it; none: on the floor."""
        best = None
        for c, ch in enumerate(self.charts):
            if not ch.catches:
                continue
            Mi = np.linalg.inv(self.mat(c, f))
            # where the vertical line through p meets the chart's surface: march down in 1 mm steps (prototype)
            for z in np.arange(p[2], self.floor_z, -1e-3):
                q = Mi[:3, :3] @ np.array([p[0], p[1], z]) + Mi[:3, 3]
                j, i, ok = ch.index(q[0], q[1])
                if ok and not np.isnan(ch.bed[j, i]) and q[2] <= ch.bed[j, i] + ch.depth[j, i]:
                    if best is None or z > best[0]:
                        best = (z, c, j, i)
                    break
        if best is None:
            self.floor += vol
            return
        _, c, j, i = best
        self._land(self.charts[c], np.array([j]), np.array([i]), np.array([vol]), np.array([True]))

    def _spawn(self, p, v, vol, src):
        self.P = np.vstack([self.P, p]); self.V = np.vstack([self.V, v])
        self.vol = np.concatenate([self.vol, vol]); self.src = np.concatenate([self.src, np.full(len(vol), src)])

    JET_R = 5e-3       # a jet spreads where it lands: the impact zone's radius (m)
    DROP_R = 1.5e-3

    def _land(self, ch, j, i, vol, jet):
        """Put landed volume onto chart ``ch`` spread over a disc (a jet's impact zone, a drop's splash), only on cells
        that have a surface; what finds none goes to the centre cell."""
        for r_m, sel in ((self.JET_R, jet), (self.DROP_R, ~jet)):
            if not sel.any():
                continue
            r = max(1, int(round(r_m / ch.cell)))
            dj, di = np.mgrid[-r:r + 1, -r:r + 1]
            k = (dj ** 2 + di ** 2) <= r * r + 0.5
            dj, di = dj[k], di[k]
            w = np.exp(-(dj ** 2 + di ** 2) / max(r * r / 2.0, 0.5))
            J = np.clip(j[sel, None] + dj[None], 0, ch.shape[0] - 1)
            I = np.clip(i[sel, None] + di[None], 0, ch.shape[1] - 1)
            W = w[None] * ~np.isnan(ch.bed[J, I])
            tot = W.sum(1, keepdims=True)
            W = np.where(tot > 0, W / np.maximum(tot, 1e-30), 0)
            W[tot[:, 0] == 0, 0] = 1.0
            np.add.at(ch.rain, (J.ravel(), I.ravel()), (W * vol[sel, None]).ravel() / ch.cell ** 2)

    def _fly(self, f, T, n=4):
        """All drops fly one frame (n sub-steps); a drop whose path crosses a catching chart's liquid top lands there."""
        if not len(self.vol):
            return
        alive = np.ones(len(self.vol), bool)
        inv = [np.linalg.inv(self.mat(c, f)) for c in range(len(self.charts))]
        for _ in range(n):
            h = T / n
            P0 = self.P.copy()
            self.V[:, 2] -= G * h
            self.P += self.V * h
            for c, ch in enumerate(self.charts):
                if not ch.catches:
                    continue
                Mi = inv[c]
                q0 = P0 @ Mi[:3, :3].T + Mi[:3, 3]
                q1 = self.P @ Mi[:3, :3].T + Mi[:3, 3]
                j, i, ok = ch.index(q1[:, 0], q1[:, 1])
                ok &= alive & (self.src != c)
                jj, ii = np.where(ok, j, 0), np.where(ok, i, 0)
                top = ch.bed[jj, ii] + ch.depth[jj, ii]
                hit = ok & np.isfinite(top) & (q0[:, 2] > top - 0.002) & (q1[:, 2] <= top)
                if hit.any():
                    self._land(ch, jj[hit], ii[hit], self.vol[hit], self.src[hit] < 0)
                    alive &= ~hit
            low = alive & (self.P[:, 2] < self.floor_z)
            self.floor += float(self.vol[low].sum())
            alive &= ~low
        self.P, self.V, self.vol, self.src = self.P[alive], self.V[alive], self.vol[alive], self.src[alive]

    # --- totals --------------------------------------------------------------------------------------------
    def totals(self):
        on = sum(c.volume() + float(c.rain.sum()) * c.cell ** 2 for c in self.charts)
        fly = float(self.vol.sum())
        drained = sum(c.drained for c in self.charts)
        return dict(poured=self.poured, on_charts=on, in_flight=fly, drained=drained, floor=self.floor)


def still(frames):
    """(frames, 4, 4) identity matrices."""
    return np.repeat(np.eye(4)[None], frames, 0)


def translate(frames, xyz):
    m = still(frames)
    m[:, :3, 3] = np.asarray(xyz, float)
    return m


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1.0]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1.0]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])
