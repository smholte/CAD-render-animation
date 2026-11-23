"""Study 0311 prototype: procedural plants, rocks, buildings – meshes in plain Python + NumPy (no Blender).

Every maker returns a :class:`MeshBuf` (vertices, faces of any size, a material name per face) in metres, standing
on z = 0 at the origin. Each scatter kind has a **detailed** and a **light** version (0155's rule for props: the light
one is used beyond a distance from the camera). Same seed, same mesh.
"""

from __future__ import annotations

import math

import numpy as np

from terrain import fbm


class MeshBuf:
    def __init__(self):
        self.v: list = []
        self.f: list = []
        self.m: list = []
        self.n = 0

    def add(self, verts, faces, mat: str):
        verts = np.asarray(verts, float)
        base = self.n
        self.v.append(verts)
        self.n += len(verts)
        for f in faces:
            self.f.append(tuple(int(base + i) for i in f))
            self.m.append(mat)
        return base

    def extend(self, other: "MeshBuf", offset=(0, 0, 0), rot: float = 0.0, scale: float = 1.0):
        c, s = math.cos(rot), math.sin(rot)
        V = other.verts() * scale
        V = np.column_stack([V[:, 0] * c - V[:, 1] * s, V[:, 0] * s + V[:, 1] * c, V[:, 2]]) + np.asarray(offset)
        base = self.n
        self.v.append(V)
        self.n += len(V)
        self.f.extend(tuple(base + i for i in f) for f in other.f)
        self.m.extend(other.m)

    def verts(self) -> np.ndarray:
        return np.concatenate(self.v) if self.v else np.zeros((0, 3))

    @property
    def tris(self) -> int:
        return sum(len(f) - 2 for f in self.f)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _frame(d):
    d = d / np.linalg.norm(d)
    a = np.array((1.0, 0, 0)) if abs(d[2]) > 0.9 else np.array((0, 0, 1.0))
    s = np.cross(d, a)
    s /= np.linalg.norm(s)
    return s, np.cross(s, d)


def tube(buf: MeshBuf, pts, radii, mat: str, sides: int = 6, cap_end: bool = True):
    """A tapered tube along points (rings at each point)."""
    pts = np.asarray(pts, float)
    ang = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    rings = []
    for i, p in enumerate(pts):
        d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        s, u = _frame(d)
        rings.append(p + radii[i] * (np.outer(np.cos(ang), s) + np.outer(np.sin(ang), u)))
    V = np.concatenate(rings + [pts[-1:]])
    F = [(j * sides + i, j * sides + (i + 1) % sides, (j + 1) * sides + (i + 1) % sides, (j + 1) * sides + i)
         for j in range(len(pts) - 1) for i in range(sides)]
    if cap_end:
        tip = len(V) - 1
        last = (len(pts) - 1) * sides
        F += [(last + i, last + (i + 1) % sides, tip) for i in range(sides)]
    buf.add(V, F, mat)


def icosphere(level: int = 2):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(level):
        cache, F2 = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = F2
    return np.array(V), F


def _noise3(p, scale, seed, octaves=4):
    return (fbm(p[:, 0], p[:, 1], scale, octaves, seed) + fbm(p[:, 1], p[:, 2], scale, octaves, seed + 7)
            + fbm(p[:, 2], p[:, 0], scale, octaves, seed + 13)) / 3


def blob(buf: MeshBuf, centre, radii, mat: str, seed: int, rough: float = 0.25, level: int = 2):
    V, F = icosphere(level)
    V = V * (1 + rough * _noise3(V * 3, 1.0, seed))[:, None] * np.asarray(radii)
    buf.add(V + np.asarray(centre), F, mat)


def leaf_cards(buf: MeshBuf, centres, normals, size, rng, mat: str = "leaf"):
    """Diamond-shaped leaves (4 corners, no alpha: no transparency cost in Cycles)."""
    V, F = [], []
    for c, n in zip(centres, normals):
        s, u = _frame(n)
        a = rng.uniform(0, math.pi)
        d1 = (math.cos(a) * s + math.sin(a) * u)
        d2 = (-math.sin(a) * s + math.cos(a) * u)
        sz = size * rng.uniform(0.7, 1.3)
        k = len(V)
        V += [c - d1 * sz, c - d2 * sz * 0.45, c + d1 * sz, c + d2 * sz * 0.45]
        F.append((k, k + 1, k + 2, k + 3))
    buf.add(np.array(V), F, mat)


# ---------------------------------------------------------------------------
# plants and rocks
# ---------------------------------------------------------------------------


def tree(seed: int = 1, height: float = 12.0, lod: str = "DETAILED") -> MeshBuf:
    """A broad-leaved tree: trunk, two levels of branches, leaf clusters round the twigs. The light version keeps the
    same trunk, main branches and crown outline with a tenth of the leaves, each three times as big (it must look the
    same at 70 m: a blob crown read as a cartoon in the first try)."""
    rng = np.random.default_rng(seed)
    b = MeshBuf()
    detailed = lod == "DETAILED"
    trunk_h = height * rng.uniform(0.32, 0.4)
    r0 = height * 0.022
    crown_r = (height - trunk_h) * 0.6
    tube(b, [(0, 0, -0.3), (0, 0, trunk_h * 0.5), (rng.normal(0, 0.1), rng.normal(0, 0.1), trunk_h)],
         [r0 * 1.3, r0, r0 * 0.8], "bark", 8 if detailed else 5, False)
    tips = []
    n_main = int(rng.integers(5, 8))
    for k in range(n_main):
        az = 2 * math.pi * k / n_main + rng.normal(0, 0.3)
        up = rng.uniform(0.6, 1.3)
        start = np.array((0, 0, trunk_h * rng.uniform(0.8, 1.0)))
        d = np.array((math.cos(az), math.sin(az), up))
        d /= np.linalg.norm(d)
        L = (height - trunk_h) * rng.uniform(0.5, 0.7)
        pts = [start + d * L * t + np.array((0, 0, -0.08 * L * t * t)) for t in (0, 0.5, 1.0)]
        tube(b, pts, [r0 * 0.6, r0 * 0.4, r0 * 0.15], "bark", 5 if detailed else 3)
        tips.append(pts[-1])
        for j in range(int(rng.integers(4, 7))):
            t = rng.uniform(0.3, 1.0)
            p = start + d * L * t
            az2 = az + rng.normal(0, 0.9)
            d2 = np.array((math.cos(az2), math.sin(az2), rng.uniform(0.2, 1.2)))
            d2 /= np.linalg.norm(d2)
            L2 = L * rng.uniform(0.3, 0.5)
            if detailed:
                tube(b, [p, p + d2 * L2], [r0 * 0.15, r0 * 0.05], "bark", 4)
            tips.append(p + d2 * L2 * 0.8)
    tips.append(np.array((0, 0, height * 0.9)))
    # leaves: clusters round the twigs, inside an ellipsoid crown
    per = 260 if detailed else 26
    size = (0.16 if detailed else 0.5) * height / 12
    cen, nor = [], []
    centre = np.array((0, 0, trunk_h + (height - trunk_h) * 0.5))
    for p in tips:
        q = p + rng.normal(0, 1, (per, 3)) * crown_r * 0.22
        rel = (q - centre) / np.array((crown_r, crown_r, (height - trunk_h) * 0.55))
        q = np.where((np.linalg.norm(rel, axis=1) > 1.0)[:, None], centre + (q - centre) * 0.85, q)
        cen.append(q)
        nor.append(rng.normal(0, 1, (per, 3)) + (q - centre) * 0.6 + np.array((0, 0, 1.0)))
    leaf_cards(b, np.concatenate(cen), np.concatenate(nor), size, rng)
    return b


def conifer(seed: int = 1, height: float = 14.0, lod: str = "DETAILED") -> MeshBuf:
    rng = np.random.default_rng(seed)
    b = MeshBuf()
    r0 = height * 0.02
    tube(b, [(0, 0, -0.3), (0, 0, height)], [r0, r0 * 0.1], "bark", 6 if lod == "DETAILED" else 4)
    detailed = lod == "DETAILED"
    for z in np.linspace(height * 0.18, height * 0.97, 16 if detailed else 8):
        r = height * 0.24 * (1 - (z - height * 0.18) / (height * 0.85)) + 0.2
        for k in range(int(rng.integers(5, 8)) if detailed else 4):
            az = rng.uniform(0, 2 * math.pi)
            d = np.array((math.cos(az), math.sin(az), -0.25))
            p = np.array((0, 0, z))
            if detailed:
                tube(b, [p, p + d * r], [0.03, 0.01], "bark", 3, False)
            m = 40 if detailed else 8
            cen = p + d[None, :] * rng.uniform(0.2, 1.0, (m, 1)) * r + rng.normal(0, 0.15, (m, 3))
            leaf_cards(b, cen, rng.normal(0, 1, (m, 3)) + np.array((0, 0, 1.2)), 0.2 if detailed else 0.55, rng,
                       "needles")
    return b


def bush(seed: int = 1, size: float = 1.4, lod: str = "DETAILED") -> MeshBuf:
    rng = np.random.default_rng(seed)
    b = MeshBuf()
    if lod != "DETAILED":
        blob(b, (0, 0, size * 0.4), (size * 0.6, size * 0.6, size * 0.45), "leaf_crown", seed, 0.3, 1)
        return b
    cen, nor = [], []
    for k in range(6):
        az = rng.uniform(0, 2 * math.pi)
        d = np.array((math.cos(az) * 0.5, math.sin(az) * 0.5, 1.0))
        tube(b, [(0, 0, 0), d * size * 0.6], [0.02, 0.006], "bark", 3)
        for _ in range(140):
            q = d * size * rng.uniform(0.2, 0.65) + rng.normal(0, size * 0.18, 3)
            q[2] = max(q[2], 0.05)
            cen.append(q)
            nor.append(rng.normal(0, 1, 3) + np.array((0, 0, 1.0)))
    leaf_cards(b, np.array(cen), np.array(nor), 0.05 * size, rng, "leaf_bush")
    return b


def grass_clump(seed: int = 1, blades: int = 16, height: float = 0.28, spread: float = 0.1) -> MeshBuf:
    """``blades`` bent blades from one spot (each 3 segments, 6 triangles)."""
    rng = np.random.default_rng(seed)
    b = MeshBuf()
    V, F = [], []
    for k in range(blades):
        base = rng.normal(0, spread, 2)
        az = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.1, 0.6)
        h = height * rng.uniform(0.6, 1.3)
        w = rng.uniform(0.006, 0.011)
        side = np.array((-math.sin(az), math.cos(az), 0)) * w
        k0 = len(V)
        for i, t in enumerate((0, 0.4, 0.75, 1.0)):
            c = np.array((base[0] + math.cos(az) * lean * h * t * t, base[1] + math.sin(az) * lean * h * t * t,
                          h * (t - 0.35 * lean * t * t)))
            ww = 1.0 - t * 0.9
            V += [c - side * ww, c + side * ww]
        F += [(k0 + 2 * i, k0 + 2 * i + 1, k0 + 2 * i + 3, k0 + 2 * i + 2) for i in range(3)]
    b.add(np.array(V), F, "grass_blade")
    return b


def rock(seed: int = 1, size: float = 1.0, lod: str = "DETAILED") -> MeshBuf:
    rng = np.random.default_rng(seed)
    b = MeshBuf()
    V, F = icosphere(3 if lod == "DETAILED" else 1)
    stretch = np.array((1.0, rng.uniform(0.6, 0.9), rng.uniform(0.45, 0.7)))
    V = V * (1 + 0.35 * _noise3(V * 2.0, 1.0, seed, 5))[:, None] * stretch * size * 0.5
    V[:, 2] = np.maximum(V[:, 2], -0.2 * size)        # sunk a little, flat underneath
    b.add(V, F, "rock")
    return b


# ---------------------------------------------------------------------------
# buildings
# ---------------------------------------------------------------------------


def _box(b: MeshBuf, x0, y0, z0, x1, y1, z1, mat):
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    b.add(V, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], mat)


def building(kind: str = "HALL", width: float = 40.0, depth: float = 24.0, floors: int = 1,
             roof: str = "PITCHED", windows: bool = True) -> MeshBuf:
    """A building from a few settings. ``kind`` HALL (steel cladding, roller doors, a window band, roof lights),
    OFFICE (floors of 3.4 m, window strips, flat roof with a parapet), HOUSE (steep roof). ``roof`` PITCHED, FLAT or
    SAWTOOTH. Materials: walls ``facade`` (its colour is a setting per building), ``roof``, ``window``, ``door``,
    ``plinth``."""
    b = MeshBuf()
    hx, hy = width / 2, depth / 2
    if kind == "HALL":
        eaves = max(6.0, 4.5 * floors + 3.0)
    elif kind == "OFFICE":
        eaves = 3.4 * floors + 0.8
    else:
        eaves = 2.8 * floors
    _box(b, -hx - 0.1, -hy - 0.1, -0.5, hx + 0.1, hy + 0.1, 0.5, "plinth")
    _box(b, -hx, -hy, 0.5, hx, hy, eaves, "facade")
    # roof
    if roof == "FLAT":
        _box(b, -hx, -hy, eaves, hx, hy, eaves + 0.05, "roof")
        for x0, y0, x1, y1 in ((-hx, -hy, hx, -hy + 0.25), (-hx, hy - 0.25, hx, hy), (-hx, -hy, -hx + 0.25, hy),
                               (hx - 0.25, -hy, hx, hy)):
            _box(b, x0, y0, eaves, x1, y1, eaves + 0.9, "facade")
    elif roof == "SAWTOOTH":
        n = max(2, int(width / 10))
        for i in range(n):
            xa, xb = -hx + width * i / n, -hx + width * (i + 1) / n
            top = eaves + 3.0
            V = [(xa, -hy, eaves), (xb, -hy, eaves), (xb, -hy, top), (xa, hy, eaves), (xb, hy, eaves), (xb, hy, top)]
            b.add(V, [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1)], "facade")
            b.add(V, [(0, 2, 5, 3)], "roof")
            b.add([(xb - 0.05, -hy + 0.5, eaves + 0.2), (xb - 0.05, hy - 0.5, eaves + 0.2),
                   (xb - 0.05, hy - 0.5, top - 0.2), (xb - 0.05, -hy + 0.5, top - 0.2)], [(0, 1, 2, 3)], "window")
    else:
        pitch = 0.18 if kind == "HALL" else 0.75
        top = eaves + hy * pitch
        o = 0.4
        V = [(-hx - o, -hy - o, eaves - o * pitch), (hx + o, -hy - o, eaves - o * pitch), (hx + o, 0, top),
             (-hx - o, 0, top), (-hx - o, hy + o, eaves - o * pitch), (hx + o, hy + o, eaves - o * pitch)]
        b.add(V, [(0, 1, 2, 3), (3, 2, 5, 4)], "roof")
        b.add([(-hx, -hy, eaves), (-hx, hy, eaves), (-hx, 0, top)], [(0, 2, 1)], "facade")
        b.add([(hx, -hy, eaves), (hx, hy, eaves), (hx, 0, top)], [(0, 1, 2)], "facade")
        if kind == "HALL":
            for x in np.arange(-hx + 4, hx - 3, 6.0):
                b.add([(x, -hy * 0.75, eaves + hy * 0.25 * pitch + 0.05), (x + 2, -hy * 0.75, eaves + hy * 0.25 * pitch + 0.05),
                       (x + 2, -hy * 0.35, eaves + hy * 0.65 * pitch + 0.05), (x, -hy * 0.35, eaves + hy * 0.65 * pitch + 0.05)],
                      [(0, 1, 2, 3)], "skylight")
    # windows and doors on the front (-y) and the sides
    if windows:
        if kind == "HALL":
            _box(b, -hx + 1, -hy - 0.06, eaves - 2.2, hx - 1, -hy + 0.01, eaves - 1.2, "window")
            _box(b, -hx + 1, hy - 0.01, eaves - 2.2, hx - 1, hy + 0.06, eaves - 1.2, "window")
            n_doors = max(1, int(width / 18))
            for i in range(n_doors):
                x = -hx + width * (i + 0.5) / n_doors
                _box(b, x - 2.5, -hy - 0.08, 0.5, x + 2.5, -hy + 0.01, min(5.5, eaves - 2.6), "door")
            _box(b, hx - 4, -hy - 0.06, 0.5, hx - 3, -hy + 0.01, 2.6, "door")
        else:
            fh = 3.4 if kind == "OFFICE" else 2.8
            for f in range(floors):
                z0 = 0.5 + f * fh + (1.0 if kind == "OFFICE" else 0.9)
                z1 = z0 + (1.7 if kind == "OFFICE" else 1.2)
                if kind == "OFFICE":
                    for y0, y1 in ((-hy - 0.06, -hy + 0.01), (hy - 0.01, hy + 0.06)):
                        _box(b, -hx + 0.6, y0, z0, hx - 0.6, y1, z1, "window")
                    for x0, x1 in ((-hx - 0.06, -hx + 0.01), (hx - 0.01, hx + 0.06)):
                        _box(b, x0, -hy + 0.6, z0, x1, hy - 0.6, z1, "window")
                else:
                    for x in np.linspace(-hx + 1.5, hx - 1.5, max(2, int(width / 3.5))):
                        _box(b, x - 0.6, -hy - 0.06, z0, x + 0.6, -hy + 0.01, z1, "window")
            _box(b, -1.0, -hy - 0.1, 0.5, 1.0, -hy + 0.01, 2.7, "door")
    return b
