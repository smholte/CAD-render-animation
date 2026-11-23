"""Study 0311 prototype: the terrain of a surroundings maker, in plain Python + NumPy (no Blender).

A candidate for ``core/terrain.py``. One terrain is a regular grid of heights (metres, z up, the machine's floor at
z = 0) plus **paint layers** (ground kinds, weights 0 … 1 per grid point, the first layer is the "rest") and
**scatter densities** (0 … 1 per grid point and scatter kind). Everything a brush does is a function on these arrays,
so it can be tested without Blender and the same strokes give the same terrain bit for bit.

Design points tried here (see the report of task 0311):
- the machine's pad is kept flat and free (``keep_pad``): nothing grows or is placed inside it;
- a road is a centre line; the terrain is cut / filled to the road's own smooth profile (``road``) and the road's
  corridor clears scatter;
- water is a level; depth per grid point = level - height, and the shore is where depth crosses 0;
- plants follow the ground layers unless painted by hand (``allowed``): grass only on grass, trees not on asphalt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

LAYERS = ("grass", "gravel", "sand", "asphalt", "concrete", "rock", "mud", "snow")
# which scatter kinds may stand on which ground (share of the density kept)
GROWS_ON = {
    "grass": {"grass": 1.0, "mud": 0.25, "sand": 0.1, "gravel": 0.05},
    "bush": {"grass": 1.0, "mud": 0.4, "sand": 0.3},
    "tree": {"grass": 1.0, "mud": 0.5, "sand": 0.2},
    "rock": {"grass": 0.6, "gravel": 1.0, "sand": 0.8, "rock": 1.0, "mud": 0.6},
}


# ---------------------------------------------------------------------------
# noise (value noise, fractal) – deterministic, no Blender
# ---------------------------------------------------------------------------


def _value_noise(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(256)
    vals = rng.random(256) * 2.0 - 1.0
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - xi, y - yi
    u, v = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def h(i, j):
        return vals[perm[(perm[i & 255] + j) & 255]]

    a, b = h(xi, yi), h(xi + 1, yi)
    c, d = h(xi, yi + 1), h(xi + 1, yi + 1)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def fbm(x, y, scale: float, octaves: int = 5, seed: int = 1, gain: float = 0.5) -> np.ndarray:
    """Fractal noise about -1 … 1, features about ``scale`` metres apart."""
    total = np.zeros(np.broadcast(x, y).shape)
    amp, f, norm = 1.0, 1.0 / scale, 0.0
    for o in range(octaves):
        total += amp * _value_noise(x * f, y * f, seed + 17 * o)
        norm += amp
        amp *= gain
        f *= 2.0
    return total / norm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# the terrain
# ---------------------------------------------------------------------------


@dataclass
class Terrain:
    half: float = 120.0            # m: the grid reaches -half … +half in x and y
    step: float = 0.5              # m between grid points
    h: np.ndarray = None
    layers: dict = field(default_factory=dict)
    scatter: dict = field(default_factory=dict)
    pad: tuple | None = None       # (x0, x1, y0, y1): the machine's flat, free pad
    water_level: float | None = None

    def __post_init__(self):
        n = int(round(2 * self.half / self.step)) + 1
        if self.h is None:
            self.h = np.zeros((n, n))
        self.xs = np.linspace(-self.half, self.half, n)
        self.X, self.Y = np.meshgrid(self.xs, self.xs)          # [row = y, col = x]
        if not self.layers:
            self.layers = {name: np.zeros_like(self.h) for name in LAYERS}
            self.layers["grass"][:] = 1.0
        if not self.scatter:
            self.scatter = {k: np.zeros_like(self.h) for k in GROWS_ON}

    @property
    def n(self) -> int:
        return self.h.shape[0]

    # ---- reading ------------------------------------------------------------
    def sample(self, x, y) -> np.ndarray:
        """Height at world (x, y), bilinear; outside the grid the edge value."""
        fx = np.clip((np.asarray(x, float) + self.half) / self.step, 0, self.n - 1.000001)
        fy = np.clip((np.asarray(y, float) + self.half) / self.step, 0, self.n - 1.000001)
        i, j = np.floor(fy).astype(int), np.floor(fx).astype(int)
        u, v = fx - j, fy - i
        h = self.h
        return (h[i, j] * (1 - u) + h[i, j + 1] * u) * (1 - v) + (h[i + 1, j] * (1 - u) + h[i + 1, j + 1] * u) * v

    water_seed: tuple | None = None    # (x, y): a lake fills the hollow round this point; None = everything below

    def depth(self) -> np.ndarray | None:
        """Water depth per grid point (m; < 0 = dry, the height above the water). With a seed only the water that
        connects to the seed point counts (a lake in its hollow, not every low spot of the terrain)."""
        if self.water_level is None:
            return None
        dep = self.water_level - self.h
        if self.water_seed is None:
            return dep
        wet = flood(dep > 0, *self._ij(*self.water_seed))
        return np.where(wet | (dep <= 0), dep, -5.0)       # cut-off low spots count as dry ground

    def _ij(self, x, y):
        return (int(round((y + self.half) / self.step)), int(round((x + self.half) / self.step)))

    # ---- brushes (one dab; a stroke = dabs along the mouse path) ---------------
    def window(self, x: float, y: float, r: float):
        """The rows / columns a brush of radius ``r`` at (x, y) can touch: every brush works on this window only, so
        a dab costs the same on a small or a big terrain (task 0311 measured 11.7 s for the prototype's strokes on
        the whole grid, 0.3 s on windows)."""
        j0 = max(0, int((x - r + self.half) / self.step))
        j1 = min(self.n, int((x + r + self.half) / self.step) + 2)
        i0 = max(0, int((y - r + self.half) / self.step))
        i1 = min(self.n, int((y + r + self.half) / self.step) + 2)
        return slice(i0, i1), slice(j0, j1)

    def _falloff(self, x, y, r, win=None):
        win = win or (slice(None), slice(None))
        d = np.hypot(self.X[win] - x, self.Y[win] - y) / r
        return smoothstep(1.0, 0.0, d)          # 1 in the middle, 0 at the rim, smooth

    def dab(self, kind: str, x: float, y: float, r: float, strength: float = 1.0, target: float = 0.0):
        win = self.window(x, y, r)
        w = self._falloff(x, y, r, win) * strength
        h = self.h[win]
        if kind == "raise":
            h += w
        elif kind == "lower":
            h -= w
        elif kind == "flatten":
            h += (target - h) * np.clip(w, 0, 1)
        elif kind == "smooth":
            k = h.copy()
            k[1:-1, 1:-1] = (h[:-2, 1:-1] + h[2:, 1:-1] + h[1:-1, :-2] + h[1:-1, 2:] + 4 * h[1:-1, 1:-1]) / 8.0
            h += (k - h) * np.clip(w, 0, 1)
        else:
            raise KeyError(kind)
        self.keep_pad(win)

    def paint(self, layer: str, x: float, y: float, r: float, strength: float = 1.0, edge_noise: float = 0.35,
              seed: int = 5):
        """Paint a ground layer; the other layers give way so the weights still add up to 1. ``edge_noise`` breaks
        the brush's round edge into a natural one (a brush that looks like a stamp is the first thing people see)."""
        win = self.window(x, y, r * (1 + edge_noise))
        X, Y = self.X[win], self.Y[win]
        d = np.hypot(X - x, Y - y) / r
        if edge_noise:
            d = d + edge_noise * fbm(X, Y, max(0.6, r * 0.35), 3, seed)
        w = smoothstep(1.0, 0.75, d) * strength
        self.set_weight(layer, w, win)

    def set_weight(self, layer: str, w: np.ndarray, win=None):
        win = win or (slice(None), slice(None))
        w = np.clip(w, 0.0, 1.0)
        for name, a in self.layers.items():
            a = a[win]
            if name == layer:
                a += (1.0 - a) * w
            else:
                a *= 1.0 - w

    def paint_scatter(self, kind: str, x: float, y: float, r: float, density: float = 1.0, erase: bool = False):
        win = self.window(x, y, r)
        w = self._falloff(x, y, r, win)
        a = self.scatter[kind][win]
        if erase:
            a *= 1.0 - w
        else:
            np.maximum(a, w * density, out=a)

    def stroke(self, fn, pts, spacing: float, **kw):
        """Dabs every ``spacing`` metres along a polyline (what a mouse drag gives)."""
        pts = np.asarray(pts, float)
        for a, b in zip(pts[:-1], pts[1:]):
            n = max(1, int(np.hypot(*(b - a)) / spacing))
            for t in np.linspace(0, 1, n, endpoint=False):
                p = a + (b - a) * t
                fn(p[0], p[1], **kw)
        fn(pts[-1][0], pts[-1][1], **kw)

    # ---- whole-terrain operations ----------------------------------------------
    def hills(self, amp: float = 6.0, scale: float = 70.0, seed: int = 3, flat_inside: float = 25.0):
        """Gentle hills, fading to 0 within ``flat_inside`` metres of the machine (the machine stands on its floor)."""
        r = np.hypot(self.X, self.Y)
        self.h += amp * fbm(self.X, self.Y, scale, 5, seed) * smoothstep(flat_inside, flat_inside * 2.5, r)

    def keep_pad(self, win=None, margin: float = 2.0):
        """The machine's pad: flat at 0 and blending into the terrain over ``margin`` + 6 metres."""
        if self.pad is None:
            return
        win = win or (slice(None), slice(None))
        X, Y = self.X[win], self.Y[win]
        x0, x1, y0, y1 = self.pad
        dx = np.maximum(np.maximum(x0 - X, X - x1), 0)
        dy = np.maximum(np.maximum(y0 - Y, Y - y1), 0)
        d = np.hypot(dx, dy)
        k = smoothstep(margin + 6.0, 0.0, d)      # 1 on the pad, 0 beyond margin + slope
        self.h[win] *= 1.0 - k

    def pad_mask(self, extra: float = 0.0) -> np.ndarray:
        if self.pad is None:
            return np.zeros_like(self.h, bool)
        x0, x1, y0, y1 = self.pad
        return (self.X > x0 - extra) & (self.X < x1 + extra) & (self.Y > y0 - extra) & (self.Y < y1 + extra)

    # ---- roads -----------------------------------------------------------------
    def road(self, ctrl, width: float, shoulder: float = 3.0, step: float = 1.0, max_grade: float = 0.06):
        """Cut / fill the terrain to a road along the control points; returns the centre line (N x 3) with z.

        The road's height is the terrain along its line, smoothed and limited to ``max_grade``; the terrain within
        width/2 is set to it (cross-fall 2 %), then blends back over ``shoulder`` metres."""
        line = catmull_rom(np.asarray(ctrl, float), step)
        z = self.sample(line[:, 0], line[:, 1])
        for _ in range(60):                           # smooth the profile
            z[1:-1] = 0.25 * z[:-2] + 0.5 * z[1:-1] + 0.25 * z[2:]
        seg = np.hypot(*np.diff(line, axis=0).T)
        for _ in range(4):                            # limit the grade both ways
            for i in range(1, len(z)):
                z[i] = np.clip(z[i], z[i - 1] - max_grade * seg[i - 1], z[i - 1] + max_grade * seg[i - 1])
            for i in range(len(z) - 2, -1, -1):
                z[i] = np.clip(z[i], z[i + 1] - max_grade * seg[i], z[i + 1] + max_grade * seg[i])
        # nearest centre-line point for every grid point (brute force in chunks: fine for a prototype)
        P = np.stack([self.X.ravel(), self.Y.ravel()], 1)
        best_d = np.full(len(P), np.inf)
        best_z = np.zeros(len(P))
        for a in range(0, len(line), 64):
            L = line[a:a + 64]
            d = np.hypot(P[:, None, 0] - L[None, :, 0], P[:, None, 1] - L[None, :, 1])
            k = d.argmin(1)
            dk = d[np.arange(len(P)), k]
            better = dk < best_d
            best_d[better] = dk[better]
            best_z[better] = z[a + k[better]]
        best_d = best_d.reshape(self.h.shape)
        best_z = best_z.reshape(self.h.shape) - 0.02 * np.minimum(best_d, width / 2)   # cross-fall
        k = smoothstep(width / 2 + shoulder, width / 2, best_d)
        self.h = self.h * (1 - k) + best_z * k
        w = smoothstep(width / 2 + 0.4, width / 2 - 0.1, best_d)
        self.set_weight("asphalt", w)
        self.set_weight("gravel", smoothstep(width / 2 + 1.2, width / 2 + 0.3, best_d) * (1 - w))
        for a in self.scatter.values():                 # the corridor stays clear
            a *= smoothstep(width / 2 + 0.5, width / 2 + 3.0, best_d)
        self.keep_pad()
        return np.column_stack([line, z])

    # ---- what grows where ---------------------------------------------------------
    def allowed(self, kind: str) -> np.ndarray:
        """Share of a scatter kind the ground allows (0 … 1), never on the pad, never under water."""
        a = np.zeros_like(self.h)
        for layer, share in GROWS_ON[kind].items():
            a += self.layers[layer] * share
        a[self.pad_mask(1.0)] = 0.0
        dep = self.depth()
        if dep is not None:
            a *= smoothstep(0.05, -0.3, dep)          # dry ground only (a little above the water line)
        return np.clip(a, 0, 1)

    def density(self, kind: str, painted_only: bool = False) -> np.ndarray:
        d = self.scatter[kind] if painted_only else np.maximum(self.scatter[kind], 0.0)
        return d * self.allowed(kind)

    # ---- the mesh ----------------------------------------------------------------
    def grid_faces(self) -> np.ndarray:
        n = self.n
        i = np.arange(n - 1)
        a = (i[:, None] * n + i[None, :]).ravel()
        return np.stack([a, a + 1, a + n + 1, a + n], 1)

    def verts(self) -> np.ndarray:
        return np.stack([self.X.ravel(), self.Y.ravel(), self.h.ravel()], 1)


# ---------------------------------------------------------------------------
# curves
# ---------------------------------------------------------------------------


def catmull_rom(ctrl: np.ndarray, step: float) -> np.ndarray:
    """A smooth line through the control points (x, y), points about ``step`` metres apart."""
    p = np.vstack([ctrl[0] * 2 - ctrl[1], ctrl, ctrl[-1] * 2 - ctrl[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        n = max(2, int(np.hypot(*(p2 - p1)) / step))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(ctrl[-1])
    return np.array(out)


def ribbon(line: np.ndarray, width: float, lift: float = 0.03):
    """The road's surface along a centre line (N x 3): vertices, quads, UVs (u across 0 … 1, v along in metres)."""
    d = np.gradient(line[:, :2], axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    along = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(line[:, :2], axis=0).T))])
    cols = np.linspace(-0.5, 0.5, 5)
    V, UV = [], []
    for k, c in enumerate(cols):
        xy = line[:, :2] + nrm * (c * width)
        z = line[:, 2] + lift - 0.02 * abs(c) * width
        V.append(np.column_stack([xy, z]))
        UV.append(np.column_stack([np.full(len(line), c + 0.5), along]))
    V = np.stack(V, 1).reshape(-1, 3)              # row i = point i, 5 columns
    UV = np.stack(UV, 1).reshape(-1, 2)
    m = len(cols)
    F = [(i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j) for i in range(len(line) - 1)
         for j in range(m - 1)]
    return V, np.array(F), UV, nrm, along


def kerb_profile(line: np.ndarray, nrm: np.ndarray, width: float, side: int, h=0.15, w=0.25, lift=0.03):
    """A kerb (box profile) along one side of a road."""
    prof = [(0.0, 0.0), (0.0, h), (w, h), (w, -0.05)]
    V = []
    for p, nv in zip(line, nrm):
        base = p[:2] + nv * side * width / 2
        for a, b in prof:
            xy = base + nv * side * a
            V.append((xy[0], xy[1], p[2] + lift - 0.01 * width + b))
    m = len(prof)
    F = [(i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j) if side > 0 else
         (i * m + j, (i + 1) * m + j, (i + 1) * m + j + 1, i * m + j + 1)
         for i in range(len(line) - 1) for j in range(m - 1)]
    return np.array(V), np.array(F)


def grow(mask: np.ndarray, cells: int) -> np.ndarray:
    """``mask`` grown by ``cells`` grid steps (4-neighbours)."""
    out = mask.copy()
    for _ in range(cells):
        g = out.copy()
        g[1:, :] |= out[:-1, :]
        g[:-1, :] |= out[1:, :]
        g[:, 1:] |= out[:, :-1]
        g[:, :-1] |= out[:, 1:]
        out = g
    return out


def flood(mask: np.ndarray, i: int, j: int) -> np.ndarray:
    """The cells of ``mask`` connected to (i, j) (4-neighbours), by growing a region with NumPy shifts."""
    out = np.zeros_like(mask)
    if not mask[i, j]:
        return out
    out[i, j] = True
    while True:
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        grown &= mask
        if (grown == out).all():
            return out
        out = grown


# ---------------------------------------------------------------------------
# water: the shore from the terrain
# ---------------------------------------------------------------------------


def shore_length(t: Terrain) -> float:
    """Length of the shore line (m): grid edges where depth changes sign, times the step (a rough measure)."""
    dep = t.depth()
    if dep is None:
        return 0.0
    wet = dep > 0
    edges = np.count_nonzero(wet[1:, :] != wet[:-1, :]) + np.count_nonzero(wet[:, 1:] != wet[:, :-1])
    return edges * t.step * math.pi / 4      # a staircase over-counts a curve by 4/pi
