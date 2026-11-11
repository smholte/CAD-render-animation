"""The app makes the toolpath (task 0029): stock + finished part + two tools -> a LinuxCNC program. No Blender here.

How it works
------------
Everything here is in **millimetres, in the program's own coordinates** (the work zero, +Z up = away from the
table). The part and the stock come in as triangles (``(n, 3, 3)`` arrays).

* **Drop-cutter** (``DropCutter``): for a point X/Y, the lowest height the tool's tip can have without the tool
  going into the part. The tool is a solid of revolution with a flat, ball or corner-radius (bull) end, open
  upwards (an endless cylinder above its end, so anything the tool's side could hit is felt too). Every triangle
  of the part is tested three ways - its face, its edges and its corners - and the highest answer wins (the way
  CAM programs do it; OpenCAMLib's drop-cutter). The work is done for many points at once with NumPy: the
  features are sorted into buckets on a grid, every point is paired with the features of its bucket.
  *Leave stock* is a bigger tool: radius and corner radius + the stock to leave, then the tip is put back up by it.
* **Roughing** (``rough``): Z levels by the step-down from the top of the stock (and one more at every flat face
  of the part, so pocket floors and the tops of bosses are roughed to the stock left there). At a level, the tool
  may go where the drop-cutter (with leave stock) lies at or below the level, and goes where there is still
  material it can reach. It clears that area **zigzag** - lines across at the stepover, each line from one side of
  the area to the other, alternate directions - and then goes once **round the edge** of the area (along the part's
  walls), so the walls carry even stock for the finish. Zigzag, not contour-parallel offset rings: it is simple,
  never leaves islands of uncut stock between rings, and works the same round pockets, bosses and holes; the
  contour pass round the walls gives the clean edge the rings would. Links between lines stay down when the way
  across is in the area; otherwise the tool lifts just above the material on the way (a map of the material left
  is kept), moves over, and goes into material on a **ramp** (never straight down).
* **Finishing** (``finish``): parallel lines (a raster) at the pass direction, the stepover worked out from the
  scallop height for a ball or bull tool. Along each line the drop-cutter is read every fraction of a millimetre;
  where it jumps (a wall) the samples are halved down to a few micrometres and the tool goes up or down at the
  wall (never across the corner). The points are then thinned to the detail's tolerance - but only ever upwards:
  a thinned line never lies more than 0.002 mm below the path it replaces.
* **Holes through the part** are left as they are: the tool goes over them as if they were closed at the height
  round them (no drilling). **Undercuts** (faces that look down) cannot be cut from the top: the stock under them
  stays, and they are reported.
* The **program** (``program_text``): G21 G90 G17 G54 G94, per tool ``T/M6`` with ``G43``, the next tool named on
  a ``Tn`` line straight after (so a double-arm changer turns its magazine while the first tool cuts), S/M3,
  M8 / M7 / the air code, ``G0`` at a safe height, ``G1`` with F, M5 M9 and M30 at the end, comments naming the
  passes. The app's own reader (``core/gcode.py``) reads it like any other program.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from . import tools as tools_core

MM = 0.001                    # metres per mm (the app's tool sizes are in metres)
NEG = -1e30                   # "nothing under the tool here"
RAMP_DEG = 3.0                # how steeply the tool goes into material (degrees)
CLEAR = 1.0                   # mm above the material for links
SAFE = 5.0                    # mm above the stock: the safe height
DOWN_TOL = 0.002              # mm: a thinned finishing line may lie at most this much below the samples
ROUGH_TOL = 0.1               # mm: the roughing pass round the walls is thinned to this
ROUGH_MARGIN = 0.12           # mm: roughing keeps this much more than leave stock (grid, thinning)
STEEP = math.tan(math.radians(60.0))   # finishing: a rise steeper than this between samples may be a wall
SAG = 0.004                   # mm: a chord between two finishing samples may lie this much below the curve
MAX_PAIRS = 2_500_000         # point x feature pairs worked on at once (memory)
MAX_RPM = 15000.0             # the fastest the default speeds turn the spindle

#: tools a toolpath can be made with
KINDS = ("FLAT", "BALL", "BULL", "FACE")
KIND_TEXT = "flat, ball or bull-nose end mills, and face mills (roughing)"

#: detail levels: roughing grid (mm), finishing samples along a line (mm), tolerance when thinning (mm), the smallest
#: scallop height the finishing lines are set for (mm; Draft: fewer lines)
DETAIL = {
    "DRAFT": dict(label="Draft", grid=1.0, sample=0.5, tol=0.05, scallop=0.04),
    "NORMAL": dict(label="Normal", grid=0.6, sample=0.25, tol=0.03, scallop=0.0),
    "FINE": dict(label="Fine", grid=0.4, sample=0.12, tol=0.01, scallop=0.0),
}

#: stock material -> (cutting speed m/min, chip load per tooth as a share of the diameter), carbide tools
MATERIALS = {
    "ALU": ("Aluminium", 300.0, 0.006),
    "STEEL": ("Steel", 120.0, 0.004),
    "POM": ("POM / plastic", 250.0, 0.008),
}


class ToolpathError(RuntimeError):
    """Something the owner has to change before a toolpath can be made (plain words)."""


class Cancelled(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# the tool's shape
# ---------------------------------------------------------------------------

@dataclass
class Shape:
    """A tool's cutting end: radius ``R`` and corner radius ``c`` (0 = flat, R = ball), in mm."""
    R: float
    c: float = 0.0

    @property
    def kind(self) -> str:
        if self.c <= 1e-9:
            return "FLAT"
        return "BALL" if self.c >= self.R - 1e-9 else "BULL"

    def t(self, r):
        """Height of the tool's lower surface above its tip at ``r`` from its axis (r <= R)."""
        r = np.asarray(r, dtype=float)
        if self.c <= 1e-9:
            return np.zeros_like(r)
        x = np.maximum(r - (self.R - self.c), 0.0)
        return self.c - np.sqrt(np.maximum(self.c * self.c - x * x, 0.0))

    def grown(self, d: float) -> "Shape":
        """The tool grown by ``d`` all round (its tip ``d`` lower): leave stock."""
        if d <= 0:
            return Shape(self.R, self.c)
        return Shape(self.R + d, self.c + d)


def shape_of(spec: tools_core.Spec) -> Shape:
    """The cutting end of a tool of the library. Face mills cut as a flat end of their widest radius."""
    s = tools_core.resolved(spec)
    if s.kind not in KINDS:
        raise ToolpathError(f"T{s.number} is a {tools_core.type_name(s.kind).lower()}: a toolpath needs "
                            f"{KIND_TEXT}")
    R = s.diameter / 2 / MM
    if s.kind == "BALL":
        return Shape(R, R)
    if s.kind == "BULL":
        return Shape(R, min(max(s.corner / MM, 0.0), R))
    if s.kind == "FACE":
        prof = tools_core.machining.tool_profile(tools_core.cutting_tool(s))
        return Shape(max(r for _z, r in prof) / MM, 0.0)
    return Shape(R, 0.0)


def chord_max(shape: Shape, sample: float) -> float:
    """The longest chord between two finishing samples: one on a curve of the corner radius lies at most SAG below
    it. A flat tool's path has no such curves (only jumps at walls)."""
    if shape.c <= 1e-6:
        return sample
    return min(sample, max(0.03, math.sqrt(8.0 * shape.c * SAG)))


def scallop_stepover(shape: Shape, height: float, fallback: float) -> float:
    """The stepover (mm) that leaves ridges ``height`` mm high between two passes of a ball or bull tool on a flat
    face: the flat of a bull's end plus what its corner radius leaves. A flat tool: ``fallback``."""
    c = shape.c
    if c <= 1e-6 or height <= 0:
        return fallback
    h = min(height, c)
    w = 2.0 * (shape.R - c) + 2.0 * math.sqrt(max(2.0 * c * h - h * h, 0.0))
    return max(w, 0.01)


# ---------------------------------------------------------------------------
# the part's features (faces, edges, corners) in buckets
# ---------------------------------------------------------------------------

def clean_tris(tris) -> np.ndarray:
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    return t[np.linalg.norm(n, axis=1) > 1e-12]


class _Buckets:
    """Features sorted into the cells of a grid by their (grown) X/Y box: a point finds its candidates in its cell."""

    def __init__(self, lo, hi, cell: float, boxes: np.ndarray):
        self.lo = np.asarray(lo, float)
        self.cell = float(cell)
        self.nx = max(1, int(math.ceil((hi[0] - lo[0]) / cell)) + 1)
        self.ny = max(1, int(math.ceil((hi[1] - lo[1]) / cell)) + 1)
        nb = self.nx * self.ny
        if len(boxes) == 0:
            self.feat = np.zeros(0, np.int64)
            self.ptr = np.zeros(nb + 1, np.int64)
            return
        i0 = np.clip(np.floor((boxes[:, 0] - self.lo[0]) / cell).astype(np.int64), 0, self.nx - 1)
        j0 = np.clip(np.floor((boxes[:, 1] - self.lo[1]) / cell).astype(np.int64), 0, self.ny - 1)
        i1 = np.clip(np.floor((boxes[:, 2] - self.lo[0]) / cell).astype(np.int64), 0, self.nx - 1)
        j1 = np.clip(np.floor((boxes[:, 3] - self.lo[1]) / cell).astype(np.int64), 0, self.ny - 1)
        w = i1 - i0 + 1
        cnt = w * (j1 - j0 + 1)
        tot = int(cnt.sum())
        feat = np.repeat(np.arange(len(boxes), dtype=np.int64), cnt)
        start = np.repeat(np.cumsum(cnt) - cnt, cnt)
        local = np.arange(tot, dtype=np.int64) - start
        ww = np.repeat(w, cnt)
        b = (np.repeat(j0, cnt) + local // ww) * self.nx + np.repeat(i0, cnt) + local % ww
        order = np.argsort(b, kind="stable")
        self.feat = feat[order]
        self.ptr = np.searchsorted(b[order], np.arange(nb + 1))

    def cell_of(self, pts: np.ndarray) -> np.ndarray:
        i = np.floor((pts[:, 0] - self.lo[0]) / self.cell).astype(np.int64)
        j = np.floor((pts[:, 1] - self.lo[1]) / self.cell).astype(np.int64)
        ok = (i >= 0) & (i < self.nx) & (j >= 0) & (j < self.ny)
        return np.where(ok, j * self.nx + i, -1)

    def pairs(self, pts: np.ndarray):
        """(point index, feature index) for every point and the features of its cell, in chunks."""
        b = self.cell_of(pts)
        has = b >= 0
        cnt = np.zeros(len(pts), np.int64)
        cnt[has] = self.ptr[b[has] + 1] - self.ptr[b[has]]
        first = np.zeros(len(pts), np.int64)
        first[has] = self.ptr[b[has]]
        csum = np.cumsum(cnt)
        k = 0
        n = len(pts)
        while k < n:
            base = csum[k - 1] if k else 0
            e = int(np.searchsorted(csum, base + MAX_PAIRS, side="right"))
            e = min(max(e, k + 1), n)
            c = cnt[k:e]
            tot = int(c.sum())
            if tot:
                pid = np.repeat(np.arange(k, e, dtype=np.int64), c)
                start = np.repeat(np.cumsum(c) - c, c)
                fid = self.feat[np.repeat(first[k:e], c) + np.arange(tot, dtype=np.int64) - start]
                yield pid, fid
            k = e


def _scatter_max(out: np.ndarray, pid: np.ndarray, z: np.ndarray) -> None:
    """out[pid] = max(out[pid], z) for sorted ``pid``."""
    if not len(pid):
        return
    starts = np.flatnonzero(np.r_[True, pid[1:] != pid[:-1]])
    m = np.maximum.reduceat(z, starts)
    idx = pid[starts]
    out[idx] = np.maximum(out[idx], m)


class Mesh:
    """The part as faces, edges and corners (shared corners and edges once)."""

    def __init__(self, tris):
        t = clean_tris(tris)
        self.tris = t
        if not len(t):
            raise ToolpathError("the finished part has no faces")
        v = t.reshape(-1, 3)
        key = np.round(v / 1e-5).astype(np.int64)
        _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        self.verts = v[first]
        f = inv.reshape(-1, 3)
        self.faces = f
        e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
        e = np.unique(e, axis=0)
        self.edges = e[e[:, 0] != e[:, 1]]
        p0, p1, p2 = t[:, 0], t[:, 1], t[:, 2]
        n = np.cross(p1 - p0, p2 - p0)
        n /= np.linalg.norm(n, axis=1)[:, None]
        self.normal = n
        self.lo = v.min(axis=0)
        self.hi = v.max(axis=0)


class DropCutter:
    """The lowest tip height of ``shape`` over points X/Y without going into ``mesh`` (see the module's docstring).
    ``leave``: stock to leave on the part (mm)."""

    def __init__(self, mesh: Mesh, shape: Shape, leave: float = 0.0):
        self.mesh = mesh
        self.leave = max(0.0, float(leave))
        self.shape = shape.grown(self.leave)
        R = self.shape.R
        t = mesh.tris
        cell = max(R * 0.75, 0.5)
        lo = mesh.lo[:2] - R - cell
        hi = mesh.hi[:2] + R + cell
        # faces: those that are not vertical (a face that looks down counts as looking up: a solid has a face
        # above it, so this never lowers the answer, and faces turned the wrong way in the mesh still count)
        n = mesh.normal.copy()
        n[n[:, 2] < 0] *= -1
        keep = n[:, 2] > 1e-6
        self.f_tri = t[keep]
        self.f_n = n[keep]
        self.f_d = np.einsum("ij,ij->i", self.f_n, self.f_tri[:, 0])
        a = self.f_tri[:, 0, :2]
        v0 = self.f_tri[:, 1, :2] - a
        v1 = self.f_tri[:, 2, :2] - a
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        good = np.abs(den) > 1e-14
        self.f_tri, self.f_n, self.f_d = self.f_tri[good], self.f_n[good], self.f_d[good]
        self.f_a, self.f_v0, self.f_v1, self.f_den = a[good], v0[good], v1[good], den[good]
        s = np.linalg.norm(self.f_n[:, :2], axis=1)
        self.f_dir = np.where(s[:, None] > 1e-12, self.f_n[:, :2] / np.maximum(s, 1e-12)[:, None], 0.0)
        fb = np.concatenate([self.f_tri[:, :, :2].min(axis=1) - R, self.f_tri[:, :, :2].max(axis=1) + R], axis=1)
        # edges
        e = mesh.edges
        self.e0 = mesh.verts[e[:, 0]]
        self.e1 = mesh.verts[e[:, 1]]
        d = self.e1[:, :2] - self.e0[:, :2]
        L = np.linalg.norm(d, axis=1)
        ok = L > 1e-7
        self.e0, self.e1, d, L = self.e0[ok], self.e1[ok], d[ok], L[ok]
        self.e_dir = d / L[:, None]
        self.e_len = L
        self.e_m = (self.e1[:, 2] - self.e0[:, 2]) / L
        eb = np.concatenate([np.minimum(self.e0[:, :2], self.e1[:, :2]) - R,
                             np.maximum(self.e0[:, :2], self.e1[:, :2]) + R], axis=1)
        vb = np.concatenate([mesh.verts[:, :2] - R, mesh.verts[:, :2] + R], axis=1)
        self.bf = _Buckets(lo, hi, cell, fb)
        self.be = _Buckets(lo, hi, cell, eb)
        self.bv = _Buckets(lo, hi, cell, vb)

    # -- the three tests -------------------------------------------------------------------------------------
    def _verts(self, pts, out):
        R, V = self.shape.R, self.mesh.verts
        for pid, fid in self.bv.pairs(pts):
            dx = V[fid, 0] - pts[pid, 0]
            dy = V[fid, 1] - pts[pid, 1]
            r = np.sqrt(dx * dx + dy * dy)
            ok = r <= R
            z = np.where(ok, V[fid, 2] - self.shape.t(np.minimum(r, R)), NEG)
            _scatter_max(out, pid, z)

    def _faces(self, pts, out):
        sh = self.shape
        a_ = sh.R - sh.c
        for pid, fid in self.bf.pairs(pts):
            n = self.f_n[fid]
            px = pts[pid, 0] - a_ * self.f_dir[fid, 0] - sh.c * n[:, 0]
            py = pts[pid, 1] - a_ * self.f_dir[fid, 1] - sh.c * n[:, 1]
            wx = px - self.f_a[fid, 0]
            wy = py - self.f_a[fid, 1]
            v0, v1, den = self.f_v0[fid], self.f_v1[fid], self.f_den[fid]
            u = (wx * v1[:, 1] - v1[:, 0] * wy) / den
            v = (v0[:, 0] * wy - wx * v0[:, 1]) / den
            inside = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
            zp = (self.f_d[fid] - n[:, 0] * px - n[:, 1] * py) / n[:, 2]
            z = np.where(inside, zp + sh.c * n[:, 2] - sh.c, NEG)
            _scatter_max(out, pid, z)

    def _edges(self, pts, out):
        sh = self.shape
        R = sh.R
        kind = sh.kind
        for pid, fid in self.be.pairs(pts):
            p0 = self.e0[fid]
            ed = self.e_dir[fid]
            L = self.e_len[fid]
            m = self.e_m[fid]
            wx = pts[pid, 0] - p0[:, 0]
            wy = pts[pid, 1] - p0[:, 1]
            u0 = wx * ed[:, 0] + wy * ed[:, 1]
            dd = wx * ed[:, 1] - wy * ed[:, 0]
            d2 = dd * dd
            ok = d2 < R * R
            h = np.sqrt(np.maximum(R * R - d2, 0.0))
            ulo = np.maximum(u0 - h, 0.0)
            uhi = np.minimum(u0 + h, L)
            ok &= uhi > ulo
            if kind == "FLAT":
                u = np.where(m > 0, uhi, ulo)
                z = p0[:, 2] + m * u
            elif kind == "BALL":
                sq = np.sqrt(1.0 + m * m)
                zc = p0[:, 2] + m * u0 + h * sq
                uc = u0 + h * m / sq
                ok &= (uc >= 0.0) & (uc <= L)
                z = zc - R
            else:                                     # bull: f(u) is concave, golden section to its top
                g = 0.6180339887498949
                a, b = ulo.copy(), uhi.copy()

                def f(u):
                    r = np.sqrt(d2 + (u - u0) ** 2)
                    return p0[:, 2] + m * u - sh.t(np.minimum(r, R))
                c1 = b - g * (b - a)
                c2 = a + g * (b - a)
                f1, f2 = f(c1), f(c2)
                for _k in range(36):
                    left = f1 > f2
                    b = np.where(left, c2, b)
                    a = np.where(left, a, c1)
                    nc1 = np.where(left, b - g * (b - a), c2)
                    nc2 = np.where(left, c1, a + g * (b - a))
                    nf1 = np.where(left, f(nc1), f2)
                    nf2 = np.where(left, f1, f(nc2))
                    c1, c2, f1, f2 = nc1, nc2, nf1, nf2
                z = np.maximum(f1, f2)
            _scatter_max(out, pid, np.where(ok, z, NEG))

    def z(self, pts) -> np.ndarray:
        """Tip heights over the points (``(n, 2)``); NEG where the tool reaches no part."""
        pts = np.asarray(pts, dtype=float).reshape(-1, 2)
        out = np.full(len(pts), NEG)
        if not len(pts):
            return out
        self._faces(pts, out)
        self._edges(pts, out)
        self._verts(pts, out)
        if self.leave > 0:
            out = np.where(out > NEG / 2, out + self.leave, NEG)
        return out


def heights(tris, pts) -> np.ndarray:
    """Where a vertical line through each point meets the triangles highest; NEG where it meets none."""
    t = clean_tris(tris)
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    out = np.full(len(pts), NEG)
    if not len(t) or not len(pts):
        return out
    a = t[:, 0, :2]
    v0 = t[:, 1, :2] - a
    v1 = t[:, 2, :2] - a
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    keep = np.abs(den) > 1e-14
    t, a, v0, v1, den = t[keep], a[keep], v0[keep], v1[keep], den[keep]
    lo, hi = t[:, :, :2].min(axis=1), t[:, :, :2].max(axis=1)
    plo, phi = pts.min(axis=0), pts.max(axis=0)
    span = float(max(np.max(phi - plo), 1.0))
    cell = max(span / 200.0, 0.5)
    bk = _Buckets(plo - cell, phi + cell, cell, np.concatenate([lo, hi], axis=1))
    for pid, fid in bk.pairs(pts):
        wx = pts[pid, 0] - a[fid, 0]
        wy = pts[pid, 1] - a[fid, 1]
        u = (wx * v1[fid, 1] - v1[fid, 0] * wy) / den[fid]
        v = (v0[fid, 0] * wy - wx * v0[fid, 1]) / den[fid]
        inside = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
        tt = t[fid]
        z = tt[:, 0, 2] + u * (tt[:, 1, 2] - tt[:, 0, 2]) + v * (tt[:, 2, 2] - tt[:, 0, 2])
        _scatter_max(out, pid, np.where(inside, z, NEG))
    return out


# ---------------------------------------------------------------------------
# grids
# ---------------------------------------------------------------------------

def _rot(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


def _shift(a: np.ndarray, dj: int, di: int, fill) -> np.ndarray:
    """``a`` moved by (dj rows, di columns); new places get ``fill``."""
    out = np.full_like(a, fill)
    ny, nx = a.shape
    js, jd = (slice(0, ny - dj), slice(dj, ny)) if dj >= 0 else (slice(-dj, ny), slice(0, ny + dj))
    is_, id_ = (slice(0, nx - di), slice(di, nx)) if di >= 0 else (slice(-di, nx), slice(0, nx + di))
    out[jd, id_] = a[js, is_]
    return out


def _disc(rx: float, ry: float, radius: float):
    """Offsets (dj, di, r) of the cells within ``radius`` of a grid with spacings rx (columns), ry (rows)."""
    ni, nj = int(radius / rx), int(radius / ry)
    out = []
    for dj in range(-nj, nj + 1):
        for di in range(-ni, ni + 1):
            r = math.hypot(di * rx, dj * ry)
            if r <= radius + 1e-9:
                out.append((dj, di, r))
    return out


def dilate(mask: np.ndarray, rx: float, ry: float, radius: float) -> np.ndarray:
    out = mask.copy()
    for dj, di, _r in _disc(rx, ry, radius):
        if dj or di:
            out |= _shift(mask, dj, di, False)
    return out


def max_filter(a: np.ndarray, rx: float, ry: float, radius: float, profile=None) -> np.ndarray:
    """The highest value within ``radius`` (minus ``profile(r)`` when given): material under a tool."""
    out = a.copy()
    for dj, di, r in _disc(rx, ry, radius):
        if dj or di:
            v = _shift(a, dj, di, NEG)
            if profile is not None:
                v = np.where(v > NEG / 2, v - profile(r), NEG)
            out = np.maximum(out, v)
    return out


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Connected areas (4-neighbours) of a boolean grid: (labels, count); 0 = not in the mask."""
    lab = np.zeros(mask.shape, np.int32)
    ny, nx = mask.shape
    n = 0
    for j0, i0 in zip(*np.nonzero(mask)):
        if lab[j0, i0]:
            continue
        n += 1
        lab[j0, i0] = n
        q = deque([(j0, i0)])
        while q:
            j, i = q.popleft()
            for jj, ii in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
                if 0 <= jj < ny and 0 <= ii < nx and mask[jj, ii] and not lab[jj, ii]:
                    lab[jj, ii] = n
                    q.append((jj, ii))
    return lab, n


# ---------------------------------------------------------------------------
# settings and results
# ---------------------------------------------------------------------------

@dataclass
class Cutting:
    """Speeds and feeds of one pass."""
    rpm: float
    feed: float                  # mm/min
    plunge: float                # mm/min (ramps, going down)


def cutting(spec: tools_core.Spec, material: str, finish: bool = False, rpm: float = 0.0, feed: float = 0.0,
            max_rpm: float = MAX_RPM) -> Cutting:
    """Spindle speed and feed: the ones given (> 0), else from the stock material and the tool's size."""
    s = tools_core.resolved(spec)
    _name, vc, k = MATERIALS.get(material, MATERIALS["ALU"])
    D = s.diameter / MM
    n = rpm if rpm > 0 else min(max_rpm, vc * 1000.0 / (math.pi * max(D, 0.5)))
    z = s.inserts if s.kind == "FACE" else (s.flutes or 2)
    fz = min(max(k * D, 0.01), 0.2) * (0.6 if finish else 1.0)
    f = feed if feed > 0 else n * z * fz
    n, f = round(n / 10) * 10, max(10.0, round(f / 10) * 10)
    return Cutting(rpm=n, feed=f, plunge=max(10.0, round(f * 0.5 / 10) * 10))


@dataclass
class Settings:
    leave: float = 0.3                 # mm left on the part by roughing
    step_down: float = 3.0             # mm
    stepover: float = 0.5              # roughing: share of the tool's diameter
    scallop: float = 0.01              # finishing: ridge height (mm), ball / bull
    angle: float = 0.0                 # pass direction, degrees from +X
    detail: str = "NORMAL"
    material: str = "ALU"
    rough_rpm: float = 0.0             # 0: worked out
    rough_feed: float = 0.0
    finish_rpm: float = 0.0
    finish_feed: float = 0.0
    coolant: str = "FLOOD"             # NONE, FLOOD (M8), MIST (M7), AIR (air_on code)
    air_on: int = 7
    air_off: int = 9
    rough: bool = True
    finish: bool = True
    name: str = ""                     # the program's title


@dataclass
class Move:
    rapid: bool
    p: tuple                           # (x, y, z) mm, program coordinates
    feed: float = 0.0


@dataclass
class Pass:
    title: str
    tool: tools_core.Spec
    cut: Cutting
    moves: list = field(default_factory=list)
    levels: list = field(default_factory=list)     # roughing: the Z levels


@dataclass
class Result:
    passes: list = field(default_factory=list)
    text: str = ""
    undercut: dict = field(default_factory=dict)   # {"faces": n, "area": mm², "text": ...}
    notes: list = field(default_factory=list)
    seconds: float = 0.0                           # how long making it took
    stats: dict = field(default_factory=dict)

    def moves(self) -> int:
        return sum(len(p.moves) for p in self.passes)


def detail(name: str) -> dict:
    return DETAIL.get(name, DETAIL["NORMAL"])


def undercut(mesh: Mesh) -> dict:
    """Faces that look down above the part's bottom: they cannot be reached from the top."""
    t, n = mesh.tris, mesh.normal
    zc = t[:, :, 2].mean(axis=1)
    area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    down = (n[:, 2] < -0.05) & (zc > mesh.lo[2] + 0.01)
    k = int(down.sum())
    a = float(area[down].sum())
    if not k or a < 0.01:
        return {"faces": 0, "area": 0.0, "text": ""}
    return {"faces": k, "area": a,
            "text": f"Undercut: {a:.0f} mm² of the part faces downwards - it cannot be cut from the top, the stock "
                    "under it stays"}


# ---------------------------------------------------------------------------
# the part and the stock on a grid
# ---------------------------------------------------------------------------

class Field:
    """The part and the stock read on a grid (rotated by the pass direction): heights, holes, the drop-cutter."""

    def __init__(self, part: Mesh, stock_tris, xs: np.ndarray, ys: np.ndarray):
        self.part = part
        self.xs, self.ys = xs, ys
        self.rx = float(xs[1] - xs[0]) if len(xs) > 1 else 1.0
        self.ry = float(ys[1] - ys[0]) if len(ys) > 1 else 1.0
        X, Y = np.meshgrid(xs, ys)
        self.pts = np.stack([X.ravel(), Y.ravel()], axis=1)
        sh = (len(ys), len(xs))
        self.shape = sh
        self.part_top = heights(part.tris, self.pts).reshape(sh)
        self.stock_top = heights(stock_tris, self.pts).reshape(sh)
        hit = self.part_top > NEG / 2
        # holes through the part: no part under the point, and not connected to the grid's border
        free = ~hit
        lab, n = _label(free)
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
        self.cap = np.full(sh, NEG)
        holes = 0
        for k in range(1, n + 1):
            if k in border:
                continue
            m = lab == k
            ring = dilate(m, 1.0, 1.0, 1.5) & hit
            if ring.any():
                self.cap[m] = self.part_top[ring].max()
                holes += 1
        self.holes = holes
        self.inside = hit | (self.cap > NEG / 2)
        self.top = np.maximum(self.part_top, self.cap)       # the part with its holes closed

    def capped(self, shape: Shape, leave: float) -> np.ndarray:
        """Tip heights the closed holes alone allow (NEG away from them)."""
        if not self.holes:
            return np.full(self.shape, NEG)
        g = shape.grown(leave)
        return max_filter(np.where(self.cap > NEG / 2, self.cap + leave, NEG), self.rx, self.ry, g.R,
                          profile=lambda r: float(g.t(min(r, g.R))))

    def lookup(self, grid: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Values of a grid at points (nearest cell)."""
        ii = np.clip(np.round((pts[:, 0] - self.xs[0]) / self.rx).astype(int), 0, len(self.xs) - 1)
        jj = np.clip(np.round((pts[:, 1] - self.ys[0]) / self.ry).astype(int), 0, len(self.ys) - 1)
        return grid[jj, ii]

    def drop(self, shape: Shape, leave: float, floor: float):
        """(tip heights on the grid, the holes' share of them, the drop-cutter)."""
        dcut = DropCutter(self.part, shape, leave)
        dc = dcut.z(self.pts).reshape(self.shape)
        capd = self.capped(shape, leave)
        return np.maximum(np.maximum(dc, capd), floor), capd, dcut


# ---------------------------------------------------------------------------
# roughing
# ---------------------------------------------------------------------------

def _ramp(path: list, z_from: float, z_to: float, feed: float) -> list:
    """Moves going down from ``z_from`` to ``z_to`` along ``path`` (X/Y points) at RAMP_DEG, forward and back along
    it as often as needed; they end at path[0] on ``z_to``. Empty when the path is too short to ramp on."""
    if z_from <= z_to + 1e-6:
        return []
    pts = [np.asarray(p, float) for p in path]
    total = sum(float(np.linalg.norm(b - a)) for a, b in zip(pts, pts[1:]))
    if total < 0.2:
        return []
    need = (z_from - z_to) / math.tan(math.radians(RAMP_DEG))
    rounds = max(1, int(math.ceil(need / (2.0 * total))))
    walk = []
    for _r in range(rounds):
        walk += pts[1:] + pts[-2::-1]
    out = []
    run = 0.0
    prev = pts[0]
    for q in walk:
        run += float(np.linalg.norm(q - prev))
        prev = q
        z = max(z_to, z_from - (z_from - z_to) * run / need)
        out.append(Move(False, (float(q[0]), float(q[1]), float(z)), feed))
    return out


def _march(f: np.ndarray, xs, ys, keep: np.ndarray):
    """Marching squares: the line where ``f`` = 0 (f >= 0 is inside), as segments between grid edges, only in the
    squares that ``keep`` marks. Returns (segments [(edge_a, edge_b)], edge -> ((ja, ia), (jb, ib)) with a inside)."""
    ny, nx = f.shape
    pos = f >= 0
    segs = []
    if ny < 2 or nx < 2:
        return segs
    a = pos[:-1, :-1]
    b = pos[:-1, 1:]
    c = pos[1:, 1:]
    d = pos[1:, :-1]
    case = a.astype(np.int8) | (b.astype(np.int8) << 1) | (c.astype(np.int8) << 2) | (d.astype(np.int8) << 3)
    sq = (case != 0) & (case != 15) & keep
    js, is_ = np.nonzero(sq)
    NH = ny * nx

    def H(j, i):
        return ("h", j, i)        # edge (j, i)-(j, i+1)

    def V(j, i):
        return ("v", j, i)        # edge (j, i)-(j+1, i)
    for j, i in zip(js.tolist(), is_.tolist()):
        k = int(case[j, i])
        bot, right, top, left = H(j, i), V(j, i + 1), H(j + 1, i), V(j, i)
        if k in (1, 14):
            segs.append((left, bot))
        elif k in (2, 13):
            segs.append((bot, right))
        elif k in (3, 12):
            segs.append((left, right))
        elif k in (4, 11):
            segs.append((right, top))
        elif k in (6, 9):
            segs.append((bot, top))
        elif k in (7, 8):
            segs.append((left, top))
        else:                                  # 5, 10: saddle, decided by the middle
            mid = (f[j, i] + f[j, i + 1] + f[j + 1, i + 1] + f[j + 1, i]) / 4 >= 0
            if (k == 5) == mid:
                segs += [(left, top), (bot, right)]
            else:
                segs += [(left, bot), (right, top)]
    del NH
    return segs


def _edge_ends(e, pos):
    kind, j, i = e
    p, q = (j, i), ((j, i + 1) if kind == "h" else (j + 1, i))
    return (p, q) if pos[p] else (q, p)


def _chains(segs: list) -> list:
    """Join segments sharing an edge into polylines (lists of edges); closed loops repeat their first edge."""
    adj = {}
    for k, (a, b) in enumerate(segs):
        adj.setdefault(a, []).append(k)
        adj.setdefault(b, []).append(k)
    used = [False] * len(segs)
    out = []
    # open chains first (start at an edge with one segment), then loops
    starts = [e for e, ks in adj.items() if len(ks) == 1] + list(adj)
    for s in starts:
        ks = [k for k in adj[s] if not used[k]]
        if not ks:
            continue
        chain = [s]
        cur = s
        while True:
            nxt = next((k for k in adj[cur] if not used[k]), None)
            if nxt is None:
                break
            used[nxt] = True
            a, b = segs[nxt]
            cur = b if a == cur else a
            chain.append(cur)
            if cur == s:
                break
        if len(chain) > 1:
            out.append(chain)
    return out


def _simplify2(pts: np.ndarray, tol: float) -> np.ndarray:
    """Douglas-Peucker on X/Y points."""
    n = len(pts)
    if n < 3:
        return pts
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        p, q = pts[a], pts[b]
        d = q - p
        L = float(np.hypot(d[0], d[1]))
        w = pts[a + 1:b] - p
        if L < 1e-12:
            dist = np.hypot(w[:, 0], w[:, 1])
        else:
            dist = np.abs(w[:, 0] * d[1] - w[:, 1] * d[0]) / L
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return pts[keep]


def rough(fld: Field, dc: np.ndarray, capd: np.ndarray, part_dc: DropCutter, shape: Shape, st: Settings,
          cut: Cutting, floor: float, safe: float):
    """Generator: the roughing pass on the field's grid (see the module's docstring); yields (fraction, text), returns
    the Pass. ``dc``: tip heights with leave stock; ``capd``: the closed holes' share of them."""
    xs, ys = fld.xs, fld.ys
    rx, ry = fld.rx, fld.ry
    ny, nx = fld.shape
    R = shape.R
    leave = st.leave + ROUGH_MARGIN
    keep_top = np.where(fld.top > NEG / 2, fld.top + leave, NEG)            # the part (+ leave) under each cell
    M = np.where(fld.stock_top > NEG / 2, fld.stock_top, NEG)               # material left: its top
    top = float(M.max()) if (M > NEG / 2).any() else floor
    so = max(0.05, min(st.stepover, 0.98)) * 2 * R
    sd = max(0.05, st.step_down)
    # the levels: by step-down, and every flat face of the part (+ leave)
    removable0 = (M > np.maximum(keep_top, floor) + 0.01)
    deepest = float(dc[dilate(removable0, rx, ry, R * 0.98)].min()) if removable0.any() else top
    deepest = max(deepest, floor)
    levels = list(np.arange(top - sd, deepest + 1e-6, -sd))
    if not levels or levels[-1] > deepest + 0.01:
        levels.append(deepest)
    n = fld.part.normal
    flat = n[:, 2] > 0.9999
    if flat.any():
        for z in np.unique(np.round(fld.part.tris[flat][:, :, 2].mean(axis=1), 4)):
            zz = float(z) + leave
            if deepest - 1e-6 <= zz < top - 0.05:
                levels.append(zz)
    levels = sorted(set(round(z, 4) for z in levels), reverse=True)
    lv = []
    for z in levels:
        if not lv or lv[-1] - z > 0.05:
            lv.append(z)
    levels = lv
    p = Pass("Roughing", None, cut, levels=levels)
    moves = p.moves
    cur = None                                   # where the tool is (x, y, z)
    k_rows = max(1, int(round(so / ry)))
    rows = list(range(0, ny, k_rows))
    if rows[-1] != ny - 1:
        rows.append(ny - 1)
    corner = shape.c

    def go_safe():
        nonlocal cur
        if cur is not None and cur[2] < safe - 1e-6:
            moves.append(Move(True, (cur[0], cur[1], safe)))
            cur = (cur[0], cur[1], safe)

    def link_height(a, b, Mdil, z):
        """Above the material (and the part) on the straight way from a to b."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(2, int(L / min(rx, ry)) + 2)
        t = np.linspace(0.0, 1.0, k)
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        ii = np.clip(np.round((px - xs[0]) / rx).astype(int), 0, nx - 1)
        jj = np.clip(np.round((py - ys[0]) / ry).astype(int), 0, ny - 1)
        h = max(float(Mdil[jj, ii].max()), float(dc[jj, ii].max()), z)
        return h + CLEAR

    def stays_in(a, b, allowed):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L > 2.5 * so + 1e-9:
            return False
        k = max(2, int(L / (0.5 * min(rx, ry))) + 2)
        t = np.linspace(0.0, 1.0, k)
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        fi = (px - xs[0]) / rx
        fj = (py - ys[0]) / ry
        i0 = np.clip(np.floor(fi).astype(int), 0, nx - 1)
        j0 = np.clip(np.floor(fj).astype(int), 0, ny - 1)
        i1 = np.clip(i0 + 1, 0, nx - 1)
        j1 = np.clip(j0 + 1, 0, ny - 1)
        return bool((allowed[j0, i0] & allowed[j0, i1] & allowed[j1, i0] & allowed[j1, i1]).all())

    def enter(path, z, Mdil, allowed):
        """Get to path[0] on level z: stay down, or lift over, and ramp into material."""
        nonlocal cur
        start = (float(path[0][0]), float(path[0][1]))
        if cur is not None and abs(cur[2] - z) < 1e-6 and stays_in(cur, start, allowed):
            moves.append(Move(False, (start[0], start[1], z), cut.feed))
            cur = (start[0], start[1], z)
            return
        if cur is None:
            moves.append(Move(True, (start[0], start[1], safe)))
            cur = (start[0], start[1], safe)
        else:
            h = link_height(cur, start, Mdil, z) if cur[2] < safe - 1e-6 else safe
            h = min(max(h, cur[2]), safe)
            if cur[2] < h - 1e-6:
                moves.append(Move(True, (cur[0], cur[1], h)))
            moves.append(Move(True, (start[0], start[1], h)))
            cur = (start[0], start[1], h)
        jj = int(np.clip(round((start[1] - ys[0]) / ry), 0, ny - 1))
        ii = int(np.clip(round((start[0] - xs[0]) / rx), 0, nx - 1))
        mat = float(Mdil[jj, ii])
        if mat <= z + 0.01:                     # air under the tool: straight down
            approach = z + CLEAR
            if cur[2] > approach:
                moves.append(Move(True, (start[0], start[1], approach)))
            moves.append(Move(False, (start[0], start[1], z), cut.plunge))
            cur = (start[0], start[1], z)
            return
        zr = mat + 0.2
        if cur[2] > zr + CLEAR:
            moves.append(Move(True, (start[0], start[1], zr + CLEAR)))
        moves.append(Move(False, (start[0], start[1], zr), cut.plunge))
        r = _ramp([start] + [(float(q[0]), float(q[1])) for q in path[1:]], zr, z, cut.plunge)
        if not r:                               # nowhere to ramp: down slowly
            r = [Move(False, (start[0], start[1], z), cut.plunge * 0.5)]
        moves.extend(r)
        cur = r[-1].p

    for li, z in enumerate(levels):
        yield li / max(len(levels), 1), f"Roughing level {li + 1} of {len(levels)}"
        allowed = dc <= z + 1e-9
        rem = M > np.maximum(np.maximum(keep_top, z), floor) + 0.01
        if not rem.any():
            continue
        reach = dilate(rem, rx, ry, R * 0.98)
        region = allowed & reach
        if not region.any():
            continue
        Mdil = max_filter(M, rx, ry, R)
        # -- zigzag
        ivs = []
        for r_ in rows:
            row = region[r_]
            if not row.any():
                continue
            d = np.diff(np.r_[0, row.astype(np.int8), 0])
            for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1):
                ivs.append((r_, int(s), int(e)))
        done = [False] * len(ivs)
        by_row = {}
        for k, (r_, s, e) in enumerate(ivs):
            by_row.setdefault(r_, []).append(k)
        ri = {r_: n_ for n_, r_ in enumerate(rows)}
        while not all(done):
            # start the next chain at the free line piece nearest to the tool
            free = [k for k in range(len(ivs)) if not done[k]]
            if cur is None:
                k = free[0]
            else:
                k = min(free, key=lambda q: min(
                    math.hypot(xs[ivs[q][1]] - cur[0], ys[ivs[q][0]] - cur[1]),
                    math.hypot(xs[ivs[q][2]] - cur[0], ys[ivs[q][0]] - cur[1])))
            r_, s, e = ivs[k]
            fwd = True
            if cur is not None and math.hypot(xs[e] - cur[0], ys[r_] - cur[1]) < \
                    math.hypot(xs[s] - cur[0], ys[r_] - cur[1]):
                fwd = False
            chain = []
            while True:
                done[k] = True
                r_, s, e = ivs[k]
                a, b = (s, e) if fwd else (e, s)
                chain.append(((float(xs[a]), float(ys[r_])), (float(xs[b]), float(ys[r_]))))
                # the next line: a free piece on the next row that overlaps, reachable staying down
                end = chain[-1][1]
                nxt = None
                n_ = ri[r_]
                for rr in (rows[n_ + 1],) if n_ + 1 < len(rows) else ():
                    cands = [q for q in by_row.get(rr, []) if not done[q]]
                    best = None
                    for q in cands:
                        _r2, s2, e2 = ivs[q]
                        st_ = (float(xs[e2] if fwd else xs[s2]), float(ys[rr]))
                        if stays_in(end, st_, allowed):
                            dist = math.hypot(st_[0] - end[0], st_[1] - end[1])
                            if best is None or dist < best[0]:
                                best = (dist, q)
                    if best is not None:
                        nxt = best[1]
                if nxt is None:
                    break
                k = nxt
                fwd = not fwd
            # cut the chain
            pts = [chain[0][0]]
            for a, b in chain:
                if math.hypot(a[0] - pts[-1][0], a[1] - pts[-1][1]) > 1e-9:
                    pts.append(a)
                pts.append(b)
            enter(pts, z, Mdil, allowed)
            for q in pts[1:]:
                if math.hypot(q[0] - cur[0], q[1] - cur[1]) > 1e-9:
                    moves.append(Move(False, (q[0], q[1], z), cut.feed))
                    cur = (q[0], q[1], z)
        # -- once round the edge of the area (the part's walls)
        f = z - dc
        keep_sq = region[:-1, :-1] | region[:-1, 1:] | region[1:, 1:] | region[1:, :-1]
        segs = _march(f, xs, ys, keep_sq)
        if segs:
            pos = f >= 0
            edges = sorted({e for sg in segs for e in sg})
            ins = np.array([_edge_ends(e, pos)[0] for e in edges])
            outs = np.array([_edge_ends(e, pos)[1] for e in edges])
            A = np.stack([xs[ins[:, 1]], ys[ins[:, 0]]], axis=1)
            B = np.stack([xs[outs[:, 1]], ys[outs[:, 0]]], axis=1)
            for _k in range(7):                  # halve towards the wall, keeping the inside end
                mid = (A + B) / 2
                okm = (part_dc.z(mid) <= z + 1e-9) & (fld.lookup(capd, mid) <= z + 1e-9)
                A = np.where(okm[:, None], mid, A)
                B = np.where(okm[:, None], B, mid)
            where = {e: (float(A[k_, 0]), float(A[k_, 1])) for k_, e in enumerate(edges)}
            for ch in _chains(segs):
                xy = np.array([where[e] for e in ch])
                closed = ch[0] == ch[-1] and len(ch) > 3
                xy = _simplify2(xy, ROUGH_TOL)
                if len(xy) < 2:
                    continue
                L = float(np.sum(np.hypot(*np.diff(xy, axis=0).T)))
                if L < 0.5:
                    continue
                path = [tuple(q) for q in xy]
                enter(path, z, Mdil, allowed)
                for q in path[1:]:
                    moves.append(Move(False, (q[0], q[1], z), cut.feed))
                    cur = (q[0], q[1], z)
                if closed and len(path) > 2:      # a little past the start, so the loop's join is cut cleanly
                    run = 0.0
                    for q in path[1:]:
                        run += math.hypot(q[0] - cur[0], q[1] - cur[1])
                        moves.append(Move(False, (q[0], q[1], z), cut.feed))
                        cur = (q[0], q[1], z)
                        if run > R:
                            break
        # the material left after this level
        swept = dilate(region, rx, ry, R)
        lower = np.maximum(np.maximum(keep_top, z + corner), floor)
        M = np.where(swept & (M > lower), lower, M)
    go_safe()
    return p


# ---------------------------------------------------------------------------
# finishing
# ---------------------------------------------------------------------------

def _lifted(u: np.ndarray, z: np.ndarray, up: float) -> tuple[np.ndarray, np.ndarray]:
    """Where the thinned line's corners go: on a crest (the line bends down there, so its chords sag below it) most
    of ``up`` away from the samples, square to the line and away from the part; elsewhere on the samples."""
    uu, zz = u.astype(float).copy(), z.astype(float).copy()
    if len(z) >= 3:
        du = np.diff(u)
        dz = np.diff(z)
        L = np.hypot(du, dz)
        ok = L > 1e-12
        tu = np.where(ok, du / np.where(ok, L, 1.0), 0.0)
        tz = np.where(ok, dz / np.where(ok, L, 1.0), 0.0)
        bend = tu[:-1] * tz[1:] - tz[:-1] * tu[1:]          # < 0: the line turns down (a crest)
        crest = (bend < -1e-9) & ok[:-1] & ok[1:]
        nu_ = -(tz[:-1] + tz[1:])                            # the line's normal there (up-side)
        nz_ = tu[:-1] + tu[1:]
        n = np.hypot(nu_, nz_)
        crest &= n > 1e-9
        d = 0.75 * up                                        # (not all of it: samples next to a corner stay inside)
        k = np.flatnonzero(crest) + 1
        uu[k] += d * nu_[crest] / n[crest]
        zz[k] += d * nz_[crest] / n[crest]
    return uu, zz


def _thin(u: np.ndarray, z: np.ndarray, up: float, down: float = DOWN_TOL) -> np.ndarray:
    """Indexes of the samples kept when thinning a line (u along it, z the tip's height): the thinned line, through
    the kept samples moved by ``_lifted``, passes at most ``down`` below and ``up`` above every sample it skips
    (measured square to the move: what the tool feels). Greedy: every move as long as that allows."""
    n = len(u)
    if n < 3:
        return np.arange(n)
    ul, zl = _lifted(u, z, up)

    def fits(a: int, b: int) -> bool:
        if b - a < 2:
            return True
        du = ul[b] - ul[a]
        dz = zl[b] - zl[a]
        L = math.hypot(du, dz)
        if L < 1e-12:
            diff = zl[a] - z[a + 1:b]
        else:
            diff = ((u[a + 1:b] - ul[a]) * dz - (z[a + 1:b] - zl[a]) * du) / L   # > 0: the move passes above
            if du < 0:
                diff = -diff
        return bool(np.all((diff >= -down) & (diff <= up)))

    keep = [0]
    a = 0
    while a < n - 1:
        step, good = 1, a + 1
        while good + step <= n - 1 and fits(a, good + step):     # gallop out …
            good += step
            step *= 2
        hi = min(good + step, n - 1)                             # … then halve back in
        if hi > good and fits(a, hi):
            good = hi
        else:
            lo_ = good
            while hi - lo_ > 1:
                mid = (lo_ + hi) // 2
                if fits(a, mid):
                    lo_ = mid
                else:
                    hi = mid
            good = lo_
        keep.append(good)
        a = good
    return np.array(keep)


def finish(part: Mesh, stock_tris, shape: Shape, st: Settings, cut: Cutting, floor: float, safe: float, lo, hi):
    """Generator: the finishing raster in the rotated frame (``lo``/``hi``: the area, X/Y); yields (fraction, text),
    returns (pass, stats)."""
    det = detail(st.detail)
    s = det["sample"]
    so = scallop_stepover(shape, max(st.scallop, det["scallop"]), max(0.05, min(st.stepover, 0.98)) * 2 * shape.R)
    ys = np.arange(lo[1], hi[1] + so * 0.5, so)
    if len(ys) and ys[-1] < hi[1] - 1e-6:
        ys = np.r_[ys, hi[1]]
    xs = np.arange(lo[0], hi[0] + s * 0.5, s)
    yield 0.02, "Finishing: reading the part"
    fld = Field(part, stock_tris, xs, ys)
    yield 0.1, "Finishing: where the tool may go"
    dc, capd, dcut = fld.drop(shape, 0.0, floor)
    inside = fld.inside & (fld.stock_top > NEG / 2)

    def exact(px, py):
        q = np.stack([px, py], axis=1)
        return np.maximum(np.maximum(dcut.z(q), fld.lookup(capd, q)), floor)

    # the lines' pieces inside the part
    pieces = []                                  # (row, i0, i1)
    for j in range(len(ys)):
        row = inside[j]
        if not row.any():
            continue
        d = np.diff(np.r_[0, row.astype(np.int8), 0])
        for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1):
            if b > a:
                pieces.append((j, int(a), int(b)))
    yield 0.4, "Finishing: walls"
    # samples per piece; where two samples lie far apart (a steep rise) the middle is read too, 7 times at most:
    # a smooth curve ends up in chords short enough to stay within SAG of it, a wall (a jump) stays a jump
    lmax = chord_max(shape, s)
    umin = s / 2 ** 7 * 1.01
    lines = []
    for (j, a, b) in pieces:
        lines.append([xs[a:b + 1].copy(), dc[j, a:b + 1].copy(), j])
    for _it in range(7):
        need_u, need_l = [], []
        for li, (u, z, j) in enumerate(lines):
            du = np.diff(u)
            dz = np.diff(z)
            far = (np.hypot(du, dz) > lmax) & (du > umin) & (np.abs(dz) > STEEP * du * 0.5)
            if far.any():
                k = np.flatnonzero(far)
                need_u.append((u[k] + u[k + 1]) / 2)
                need_l.append(np.full(len(k), li))
        if not need_u:
            break
        nu = np.concatenate(need_u)
        nl = np.concatenate(need_l)
        nz = exact(nu, ys[np.array([lines[q][2] for q in nl])])
        for li in np.unique(nl):
            m = nl == li
            u, z, j = lines[li]
            uu = np.r_[u, nu[m]]
            zz = np.r_[z, nz[m]]
            o = np.argsort(uu, kind="stable")
            lines[li] = [uu[o], zz[o], j]
    yield 0.7, "Finishing: thinning the lines"
    p = Pass("Finishing", None, cut)
    moves = p.moves
    tol = det["tol"]
    out_lines = []
    for u, z, j in lines:
        # staircase at walls: up first when climbing, over first when going down
        uu, zz = [u[0]], [z[0]]
        for k in range(1, len(u)):
            if math.hypot(u[k] - u[k - 1], z[k] - z[k - 1]) > lmax and abs(z[k] - z[k - 1]) > STEEP * (u[k] - u[k - 1]):
                if z[k] > z[k - 1]:
                    uu.append(u[k - 1])
                    zz.append(z[k])
                else:
                    uu.append(u[k])
                    zz.append(z[k - 1])
            uu.append(u[k])
            zz.append(z[k])
        uu, zz = np.array(uu), np.array(zz)
        keep = _thin(uu, zz, tol)
        ul, zl = _lifted(uu, zz, tol)
        out_lines.append((ul[keep], zl[keep], float(ys[j])))
    # one line after the other, alternate directions; links over the part
    cur = None
    for n_, (u, z, y) in enumerate(out_lines):
        if n_ % 2:
            u, z = u[::-1], z[::-1]
        pts = [(float(a), y, float(b)) for a, b in zip(u, z)]
        first = pts[0]
        if cur is None:
            moves.append(Move(True, (first[0], first[1], safe)))
            moves.append(Move(True, (first[0], first[1], first[2] + CLEAR)))
            moves.append(Move(False, first, cut.plunge))
        else:
            k = max(3, int(math.hypot(first[0] - cur[0], first[1] - cur[1]) / s) + 2)
            t = np.linspace(0, 1, k)
            lz = exact(cur[0] + (first[0] - cur[0]) * t, cur[1] + (first[1] - cur[1]) * t)
            h = float(lz.max())
            if h <= max(cur[2], first[2]) + 1e-6 and math.hypot(first[0] - cur[0], first[1] - cur[1]) < 3 * so:
                top_ = max(cur[2], first[2])
                if top_ > cur[2] + 1e-6:
                    moves.append(Move(False, (cur[0], cur[1], top_), cut.feed))
                moves.append(Move(False, (first[0], first[1], top_), cut.feed))
                if first[2] < top_ - 1e-6:
                    moves.append(Move(False, first, cut.feed))
            else:
                hz = min(safe, max(h, cur[2], first[2]) + CLEAR)
                moves.append(Move(True, (cur[0], cur[1], hz)))
                moves.append(Move(True, (first[0], first[1], hz)))
                moves.append(Move(False, first, cut.plunge))
        for q in pts[1:]:
            moves.append(Move(False, q, cut.feed))
        cur = pts[-1]
    if cur is not None:
        moves.append(Move(True, (cur[0], cur[1], safe)))
    return p, {"stepover": so, "lines": len(out_lines)}


# ---------------------------------------------------------------------------
# all of it
# ---------------------------------------------------------------------------

def _to_frame(tris, rot):
    t = clean_tris(tris)
    return (t.reshape(-1, 3) @ rot.T).reshape(-1, 3, 3)


def make(part_tris, stock_tris, rough_tool: tools_core.Spec | None, finish_tool: tools_core.Spec | None,
         st: Settings):
    """Generator: yields (fraction, text) while it works; its return value (StopIteration.value) is the Result.
    ``part_tris`` / ``stock_tris``: triangles in program coordinates, mm."""
    import time
    t0 = time.perf_counter()
    res = Result()
    if rough_tool is None and finish_tool is None:
        raise ToolpathError("Pick a roughing tool, a finishing tool or both")
    stock = clean_tris(stock_tris)
    if not len(stock):
        raise ToolpathError("the stock has no faces")
    theta = math.radians(st.angle)
    rot = _rot(theta)
    part_r = Mesh(_to_frame(part_tris, rot))
    stock_r = _to_frame(stock, rot)
    res.undercut = undercut(part_r)
    slo, shi = stock_r.reshape(-1, 3).min(axis=0), stock_r.reshape(-1, 3).max(axis=0)
    plo, phi = part_r.lo, part_r.hi
    if (plo[:2] > shi[:2]).any() or (phi[:2] < slo[:2]).any() or plo[2] > shi[2]:
        raise ToolpathError("the finished part is not inside the stock: pick the right parts, or move them")
    floor = float(plo[2])
    safe = float(shi[2]) + SAFE
    det = detail(st.detail)
    if rough_tool is not None and st.rough:
        shape = shape_of(rough_tool)
        cut = cutting(rough_tool, st.material, False, st.rough_rpm, st.rough_feed)
        h = min(det["grid"], max(shape.R / 6.0, 0.2))
        x0, x1 = max(slo[0], plo[0] - shape.R) - shape.R, min(shi[0], phi[0] + shape.R) + shape.R
        y0, y1 = max(slo[1], plo[1] - shape.R) - shape.R, min(shi[1], phi[1] + shape.R) + shape.R
        xs = np.arange(x0, x1 + h * 0.5, h)
        ys = np.arange(y0, y1 + h * 0.5, h)
        yield 0.01, "Roughing: reading the part"
        fld = Field(part_r, stock_r, xs, ys)
        yield 0.08, "Roughing: where the tool may go"
        dc, capd, part_dc = fld.drop(shape, st.leave + ROUGH_MARGIN, floor)
        g = rough(fld, dc, capd, part_dc, shape, st, cut, floor, safe)
        span = 0.4 if (finish_tool is not None and st.finish) else 0.85
        try:
            while True:
                fr, text = next(g)
                yield 0.12 + span * fr, text
        except StopIteration as stop:
            rp = stop.value
        rp.tool = rough_tool
        res.passes.append(rp)
        res.stats["rough_levels"] = len(rp.levels)
        res.stats["rough_grid"] = h
    if finish_tool is not None and st.finish:
        shape = shape_of(finish_tool)
        cut = cutting(finish_tool, st.material, True, st.finish_rpm, st.finish_feed)
        lo = (max(slo[0], plo[0]), max(slo[1], plo[1]))
        hi = (min(shi[0], phi[0]), min(shi[1], phi[1]))
        base = 0.55 if res.passes else 0.02
        g = finish(part_r, stock_r, shape, st, cut, floor, safe, lo, hi)
        try:
            while True:
                fr, text = next(g)
                yield base + (0.95 - base) * fr, text
        except StopIteration as stop:
            fp, fst = stop.value
        fp.tool = finish_tool
        res.passes.append(fp)
        res.stats.update({"finish_" + k: v for k, v in fst.items()})
    if not res.passes:
        raise ToolpathError("Nothing to make: tick Roughing or Finishing")
    # back to the program's own X/Y
    rinv = rot.T
    for p in res.passes:
        for m in p.moves:
            q = rinv @ np.array(m.p)
            m.p = (float(q[0]), float(q[1]), float(q[2]))
    yield 0.97, "Writing the program"
    res.text = program_text(res, st, safe)
    res.seconds = time.perf_counter() - t0
    res.stats["safe"] = safe
    return res


def run(part_tris, stock_tris, rough_tool, finish_tool, st: Settings, progress=None) -> Result:
    """``make`` to the end (tests, scripts)."""
    g = make(part_tris, stock_tris, rough_tool, finish_tool, st)
    try:
        while True:
            fr, text = next(g)
            if progress is not None:
                progress(fr, text)
    except StopIteration as stop:
        return stop.value


# ---------------------------------------------------------------------------
# the program
# ---------------------------------------------------------------------------

def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def tool_comment(spec: tools_core.Spec) -> str:
    s = tools_core.resolved(spec)
    D = s.diameter / MM
    cr = {"BALL": D / 2, "BULL": s.corner / MM}.get(s.kind, 0.0)
    word = {"FLAT": "flat end mill", "BALL": "ball end mill", "BULL": "bullnose end mill",
            "FACE": "face mill"}.get(s.kind, tools_core.type_name(s.kind).lower())
    return f"(T{s.number} D={_num(D)} CR={_num(cr)} - {word})"


def coolant_codes(st: Settings) -> tuple[str, str]:
    return {"FLOOD": ("M8", "M9"), "MIST": ("M7", "M9"), "AIR": (f"M{st.air_on}", f"M{st.air_off}")}.get(
        st.coolant, ("", ""))


def program_text(res: Result, st: Settings, safe: float) -> str:
    out = []
    title = st.name or "Toolpath made by Fresing Render"
    out.append(f"({title})")
    names = []
    for p in res.passes:
        if p.tool.number not in names:
            names.append(p.tool.number)
            out.append(tool_comment(p.tool))
    mat = MATERIALS.get(st.material, MATERIALS["ALU"])[0]
    out.append(f"(Stock: {mat.lower()}; leave stock {_num(st.leave)} mm, step-down {_num(st.step_down)} mm, "
               f"scallop {_num(st.scallop)} mm, pass direction {_num(st.angle)} deg)")
    if res.undercut.get("faces"):
        out.append(f"({res.undercut['text']})")
    out.append("G21 G90 G17 G54 G94")
    on, off = coolant_codes(st)
    current = None
    for k, p in enumerate(res.passes):
        out.append(f"({p.title}: {tools_core.resolved(p.tool).label()})")
        n = p.tool.number
        if n != current:
            out.append(f"T{n} M6")
            out.append(f"G43 H{n}")
            current = n
            nxt = next((q.tool.number for q in res.passes[k + 1:] if q.tool.number != n), None)
            if nxt is not None:
                out.append(f"T{nxt}")
        out.append(f"S{int(round(p.cut.rpm))} M3")
        if on:
            out.append(on)
        last = [None, None, None]
        f_last = None
        out.append(f"G0 Z{_num(safe)}")
        last[2] = round(safe, 3)
        for m in p.moves:
            words = []
            for i, ax in enumerate("XYZ"):
                v = round(m.p[i], 3)
                if last[i] is None or abs(v - last[i]) > 1e-9:
                    words.append(f"{ax}{_num(v)}")
                    last[i] = v
            if not words:
                continue
            if m.rapid:
                out.append("G0 " + " ".join(words))
            else:
                fw = ""
                if f_last is None or abs(m.feed - f_last) > 1e-6:
                    fw = f" F{int(round(m.feed))}"
                    f_last = m.feed
                out.append("G1 " + " ".join(words) + fw)
        out.append(f"G0 Z{_num(safe)}")
        if k + 1 < len(res.passes) and res.passes[k + 1].tool.number != n:
            out.append("M5")
            if off:
                out.append(off)
    out.append("M5")
    if off:
        out.append(off)
    out.append("M30")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# checks (tests, and the result line)
# ---------------------------------------------------------------------------

def path_length(moves) -> tuple[float, float]:
    """(feed length, rapid length) of the moves (mm)."""
    fl = rl = 0.0
    prev = None
    for m in moves:
        if prev is not None:
            d = math.dist(prev, m.p)
            if m.rapid:
                rl += d
            else:
                fl += d
        prev = m.p
    return fl, rl


def gouge(moves, mesh_tris, spec: tools_core.Spec, step: float = 0.05, leave: float = 0.0, feed_only: bool = True,
          worst: list | None = None) -> float:
    """How deep (mm) the tool goes into the part (+ ``leave``) anywhere along the moves (sampled every ``step``): the
    shortest move, up or sideways (8 directions), that frees it. 0 when it never does. ``worst``: gets
    (depth, point) of the deepest spots."""
    dcut = DropCutter(Mesh(mesh_tris), shape_of(spec), leave)
    prev = None
    pts = []
    for m in moves:
        if prev is not None and not (feed_only and m.rapid):
            d = math.dist(prev, m.p)
            k = max(2, int(d / step) + 2)
            t = np.linspace(0, 1, k)[:, None]
            pts.append(np.asarray(prev)[None, :] + (np.asarray(m.p) - np.asarray(prev))[None, :] * t)
        prev = m.p
    if not pts:
        return 0.0
    P = np.concatenate(pts)
    gap = np.concatenate([dcut.z(P[k:k + 200_000, :2]) - P[k:k + 200_000, 2] for k in range(0, len(P), 200_000)])
    bad = np.flatnonzero(gap > 1e-6)
    if not len(bad):
        return 0.0
    Q = P[bad]
    depth = gap[bad].copy()
    ang = np.linspace(0, 2 * math.pi, 8, endpoint=False)
    for r in (0.0005, 0.001, 0.002, 0.004, 0.006, 0.008, 0.01, 0.015, 0.02, 0.03, 0.05):
        open_ = np.zeros(len(Q), bool)
        for a in ang:
            q = Q[:, :2] + r * np.array([math.cos(a), math.sin(a)])
            open_ |= dcut.z(q) <= Q[:, 2]
        depth = np.where(open_, np.minimum(depth, r), depth)
    if worst is not None:
        o = np.argsort(-depth)[:10]
        worst.extend((float(depth[k]), tuple(float(v) for v in Q[k])) for k in o)
    return float(depth.max())
