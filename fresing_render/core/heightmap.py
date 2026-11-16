"""A height map for dense 3-axis milling programs (task 0146, study 0069 #8). NumPy only: no Manifold, no Blender.

Why
---
``core/machining.py`` takes material away with one mesh boolean per straight move. That is exact, but a finishing
program of ten thousand short moves costs 8 to 10 ms per move and more as the mesh grows (study 0069, M1: 2.4 min).
Seen along the tool, the bottom of such a cut is simply *the lowest point the tool reached* above every place of
the block: a height map. Stamping a move into a grid costs microseconds.

What is here
------------
* ``Shape``: a bit seen from below - the height ``f(r)`` of its surface above the tip at distance ``r`` from its
  axis (flat, ball, corner radius, cone, or a convex outline).
* ``sweep_height``: the bottom of the volume the bit sweeps along one straight move (tip from ``a`` to ``b``), at
  any points; ``inf`` outside the bit's footprint. Exact for level moves, plunges and sloped moves.
* ``HeightMap``: a grid of **nodes** in the map's own frame (``x``, ``y`` across the tool, ``z`` along it, from the
  tip up into the tool). Per node the lowest ``z`` a move reached (``h``) and which move (``owner``, the number of the
  move in the table given with ``set_moves``; -1 = not cut, ``h`` = the stock's top + ``PAD``). At equal heights the
  later move owns the node (its marks lie on top). A second number per node, ``shape``, names the move whose
  surface the node lies on *as a shape*: at equal heights (flat floors of passes that overlap) the move the node
  lies deepest inside - the wall next to the node is that move's edge, not the edge of whichever pass came by
  last. ``goto(k, partial)`` makes the map as it is after the first
  ``k`` moves plus the part of the move each bit is in; going back uses kept snapshots and stamps forward again,
  so a state never depends on how it was reached.
* ``mesh(J, I)``: the surface of one **tile** (``tile`` x ``tile`` cells) as a closed solid "everything below the
  surface inside the tile's box", with the move that made each top triangle:

  1. **Snap.** Between two neighbouring nodes that belong to different moves the true surface is often not the
     straight line between them: a wall (the lower move's footprint ends there), a rim, the edge of a chamfer. The
     place where the two surfaces meet is found on the grid edge by bisection on the exact heights, and the nodes
     next to it move there: at a wall both, one for the top and one for the foot, so walls are vertical and their
     outline is exact where the grid lines cross it; at a crease the nearer one. The same for a valley inside one
     move's surface (the bottom line of a V-groove). Nodes on a tile's border only move along it, so every tile
     stays inside its box and the tiles fit.
  2. **Thin out.** A hierarchy of right triangles (RTIN: every triangle splits at the middle of its long side)
     keeps a node only where leaving it out would move the surface by more than ``tol``, or would join nodes of
     different **mark classes** (``cls`` per move: faces whose tool marks may not run into each other). A node on
     the border between two tiles is kept when either tile needs it: the tiles meet vertex for vertex.
     The fine ridges between the passes of a finishing program (3.75 µm high for a Ø6 ball stepping over 0.3 mm)
     would keep nearly every node, for something nobody sees: ridges lower than ``RIDGE`` x ``tol`` do not count
     (a node's height minus the mean of the nodes a few cells round it is taken off before the nodes are judged,
     where that is so little). The nodes that are kept stay where they are, so the mesh is within ``tol`` + that.
  3. Each triangle belongs to the move of its lowest corner (a wall to the move whose flank cut it).

Tolerances: the nodes are exact; between nodes the surface is off by at most ``tol`` plus the sag of a chord of one
cell (cell² / 8 R: 1.7 µm for a Ø6 ball at 0.2 mm). Walls and rims are exact where grid lines cross them. A sharp
outside corner of a wall, and anything thinner than a cell, can be off by up to one cell.

Units: metres.
"""

from __future__ import annotations

import math

import numpy as np

from . import heightmesh as _hmesh

MM = 0.001

TILE = 32                         # cells along a tile's side (a power of two: the triangle hierarchy)
PAD = 0.02 * MM                   # a node nobody cut lies this far above the stock's top
TIE = 1e-9                        # heights closer than this are equal: the later move owns the node
EDGE = 5e-8                       # a bit's footprint is this much wider than the bit: a cut that ends exactly on
#                                   the block's side (CAM programs do) goes a hair past it and leaves no skin there
SNAP_STEPS = 8                    # halvings when looking for the place two surfaces meet (cell / 250)
SNAPSHOT_BYTES = 192e6            # memory for the kept states (going back in time)
SNAPSHOT_MIN = 64                 # ... never closer together than this many moves

# cell size and most nodes per detail level (the names of core/machining.DETAIL)
CELL = {"FINE": 0.1 * MM, "NORMAL": 0.2 * MM, "FAST": 0.4 * MM}
NODES = {"FINE": 8.0e6, "NORMAL": 3.0e6, "FAST": 1.2e6}
CELL_MIN = 0.02 * MM
CELLS_PER_RADIUS = 4.0            # the smallest bit's radius is at least this many cells
RIDGE = 2.5                       # ridges between passes lower than this x the tolerance are left out of the mesh
ROUNDED = 8.0                     # a node stays off a wall when a chord to it would miss a rounded strip by more
#                                   than this x the tolerance (0.04 mm at Normal; task 0167)
RIDGE_CELLS = 3                   # ... when they are narrower than about twice this many cells
REACH = RIDGE_CELLS               # a tile's mesh reads this many nodes past its border
PROBES = (0.125, 0.375, 0.625, 0.875)     # where on an edge the lowest move is looked for

FLAT, BALL, BULL, CONE, PROFILE = "FLAT", "BALL", "BULL", "CONE", "PROFILE"


# ---------------------------------------------------------------------------
# the bit seen from below
# ---------------------------------------------------------------------------

class Shape:
    """A bit as a height over the distance from its axis: ``f(r)`` above the tip for ``r <= R``; above ``R`` the
    bit does not reach. ``f`` is convex and never falls (a bit that cuts from above without undercut)."""

    def __init__(self, kind: str, R: float, length: float, b: float = 0.0, c: float = 0.0, k: float = 0.0,
                 rk=None, zk=None):
        self.kind, self.R, self.length = kind, float(R), float(length)
        self.b, self.c, self.k = float(b), float(c), float(k)       # BULL: flat radius, corner; CONE: dz / dr
        self.rk = None if rk is None else np.asarray(rk, float)     # PROFILE: radii (rising) and their heights
        self.zk = None if zk is None else np.asarray(zk, float)
        self.rim = float(self.f(np.array([self.R]))[0])             # the height of the widest ring

    def key(self) -> tuple:
        return (self.kind, round(self.R, 9), round(self.length, 9), round(self.b, 9), round(self.c, 9),
                round(self.k, 9), None if self.rk is None else (self.rk.tobytes(), self.zk.tobytes()))

    def f(self, r):
        if self.kind == FLAT:
            return np.zeros(np.shape(r))
        if self.kind == BALL:
            return self.R - np.sqrt(np.maximum(self.R * self.R - r * r, 0.0))
        if self.kind == BULL:
            t = np.maximum(r - self.b, 0.0)
            return self.c - np.sqrt(np.maximum(self.c * self.c - t * t, 0.0))
        if self.kind == CONE:
            return self.k * r
        return np.interp(r, self.rk, self.zk)

    def df(self, r):
        """d f / d r (for a sloped move's lowest point)."""
        if self.kind == FLAT:
            return np.zeros(np.shape(r))
        if self.kind == BALL:
            return r / np.sqrt(np.maximum(self.R * self.R - r * r, 1e-30))
        if self.kind == BULL:
            t = np.maximum(r - self.b, 0.0)
            return t / np.sqrt(np.maximum(self.c * self.c - t * t, 1e-30))
        if self.kind == CONE:
            return np.full(np.shape(r), self.k)
        j = np.clip(np.searchsorted(self.rk, r, side="right") - 1, 0, len(self.rk) - 2)
        s = (self.zk[j + 1] - self.zk[j]) / np.maximum(self.rk[j + 1] - self.rk[j], 1e-30)
        return np.where(r < self.rk[0], 0.0, s)


def shape_of(tool, profile=None) -> Shape | None:
    """The ``Shape`` of a ``core.machining.Tool`` (``profile``: its outline ``[(z, r), ...]`` from the tip up, as
    ``Cutter.profile``), or None when the map cannot hold what it cuts: an outline that gets narrower higher up
    (a T-slot cutter: undercuts) or bulges in (a shank wider than the cutter: two convex pieces)."""
    R, L = max(float(tool.radius), 1e-5), max(float(tool.length), 1e-4)
    kind = tool.kind
    if kind == "FLAT":
        return Shape(FLAT, R, L)
    if kind == "BALL" and L >= R:
        return Shape(BALL, R, L)
    if kind == "BULL":
        c = min(max(float(tool.corner), 0.0), R)
        if c <= 1e-7:
            return Shape(FLAT, R, L)
        if L >= c:
            return Shape(BULL, R, L, b=R - c, c=c)
    if kind in ("VEE", "DRILL"):
        half = math.radians(min(max(float(tool.angle), 1.0), 179.0)) / 2
        return Shape(CONE, min(R, L * math.tan(half)), L, k=1.0 / math.tan(half))
    if not profile or len(profile) < 2:
        return None
    z = np.array([p[0] for p in profile], float)
    r = np.array([p[1] for p in profile], float)
    z = z - z[0]
    dz, dr = np.diff(z), np.diff(r)
    if np.any(dz < -1e-9) or np.any(dr < -1e-9):
        return None                                    # narrower higher up: an undercut
    step = (np.abs(dz) > 1e-9) | (np.abs(dr) > 1e-9)
    dz, dr = dz[step], dr[step]
    # one convex piece: the outline never turns outwards on its way up (its slope dr / dz only falls). A step out
    # higher up (a shank wider than the cutter) would be a second piece
    slope = np.where(dz > 1e-9, dr / np.maximum(dz, 1e-30), np.inf)
    if np.any(np.diff(np.arctan(slope)) > 1e-7):
        return None
    keep = np.concatenate([[True], np.diff(r) > 1e-9])      # (a cylinder above: the lowest point of each radius)
    rk, zk = r[keep], z[keep]
    if len(rk) == 1:
        return Shape(FLAT, float(rk[0]), float(z.max()))
    return Shape(PROFILE, float(rk[-1]), float(z.max()), rk=rk, zk=zk)


def sweep_height(shape: Shape, ax, ay, bx, by, z0, z1, px, py, depth: bool = False):
    """The bottom of the bit swept straight from tip (ax, ay, z0) to (bx, by, z1), at the points (px, py);
    ``inf`` where the bit never is above the point. Every argument may be an array (they broadcast).

    With ``s`` the place of the tip along the move, the bit is above a point while the point is within ``R`` of
    the axis; the bottom there is the lowest ``z(s) + f(r(s))``. For a level move that is at the nearest place;
    on a slope a flat bit is lowest at the end of its stay, a ball where the tilted cylinder it sweeps is lowest,
    a cone on a line through its apex; other shapes are solved by halving (the height is convex in ``s``).

    ``depth=True``: also how far inside the bit's edge the point is at that lowest place (``R - r``)."""
    vx, vy = bx - ax, by - ay
    L = np.hypot(vx, vy)
    still = L < 1e-9                                   # straight down or up, or standing
    Ls = np.where(still, 1.0, L)
    ux, uy = vx / Ls, vy / Ls
    dx, dy = px - ax, py - ay
    u = np.where(still, 0.0, dx * ux + dy * uy)        # the point along the move ...
    w2 = np.maximum(dx * dx + dy * dy - u * u, 0.0)    # ... and beside it, squared
    R = shape.R
    Rf = R + EDGE
    e = np.sqrt(np.maximum(Rf * Rf - w2, 0.0))
    lo = np.maximum(-u, -e)                            # x = (the tip's place) - u, while the bit is above the point
    hi = np.minimum(np.where(still, 0.0, L) - u, e)
    ok = (w2 <= Rf * Rf) & (lo <= hi)
    m = np.where(still, 0.0, (z1 - z0) / Ls)           # the slope
    base = np.where(still, np.minimum(z0, z1), z0)
    level = not np.any(m != 0.0)
    if level or shape.kind == BALL:
        x = np.clip(-m * e / np.sqrt(1.0 + m * m), lo, hi) if not level else np.clip(0.0, lo, hi)
    elif shape.kind == FLAT:
        x = np.where(m < 0.0, hi, np.where(m > 0.0, lo, np.clip(0.0, lo, hi)))
    elif shape.kind == CONE:
        q = -m / shape.k
        steep = np.abs(q) >= 1.0
        xs = q * np.sqrt(w2) / np.sqrt(np.maximum(1.0 - q * q, 1e-30))
        x = np.clip(np.where(steep, np.where(q > 0, np.inf, -np.inf), xs), lo, hi)
    else:
        a, b = lo + np.zeros(np.shape(m)), hi + np.zeros(np.shape(m))
        for _k in range(34):                           # the slope of the height along the move changes sign once
            x = 0.5 * (a + b)
            r = np.sqrt(x * x + w2)
            up = m + shape.df(np.minimum(r, R)) * x / np.maximum(r, 1e-30) > 0.0
            b = np.where(up, x, b)
            a = np.where(up, a, x)
        x = 0.5 * (a + b)
    x = np.where(ok, x, 0.0)
    r = np.minimum(np.sqrt(x * x + w2), R)
    H = np.where(ok, base + m * (u + x) + shape.f(r), np.inf)
    return (H, Rf - np.sqrt(x * x + w2)) if depth else H


# (the hierarchy of right triangles and the strips that thin a tile: core/heightmesh.py)
_rtin = _hmesh.rtin
_needed = _hmesh.rtin_needed
_triangles = _hmesh.rtin_triangles
_PLAIN: dict = {}                 # n -> the thinning of a tile nobody cut (two triangles)


# ---------------------------------------------------------------------------
# the map
# ---------------------------------------------------------------------------

def cell_for(detail_name: str, size_x: float, size_y: float, smallest_radius: float) -> float:
    """The cell of a map over ``size_x`` x ``size_y`` metres: the detail level's, at most a quarter of the
    smallest bit's radius, grown until the grid has no more nodes than the level allows."""
    c = min(CELL.get(detail_name, CELL["NORMAL"]), max(smallest_radius, 1e-6) / CELLS_PER_RADIUS)
    c = max(c, CELL_MIN)
    most = NODES.get(detail_name, NODES["NORMAL"])
    if (size_x / c + 1) * (size_y / c + 1) > most:
        c = math.sqrt(max(size_x, c) * max(size_y, c) / most)
    return c


class HeightMap:
    """The lowest point every move reached, on a grid (see the top of this file).

    ``x0``, ``y0``: the first node; ``cell``; ``tiles_x`` x ``tiles_y`` tiles of ``tile`` cells; ``top``: the
    stock's highest point; ``bottom``: where the solids of ``mesh`` end (below the stock); ``tol``: the detail
    level's tolerance (where two surfaces meet, the fine ridges left out: ``RIDGE`` x ``tol``); ``thin``: how far
    the thinned-out mesh may leave the nodes (at least ``tol``)."""

    def __init__(self, x0: float, y0: float, cell: float, tiles_x: int, tiles_y: int, top: float, bottom: float,
                 tol: float, tile: int = TILE, thin: float | None = None):
        self.x0, self.y0, self.cell, self.tile = float(x0), float(y0), float(cell), int(tile)
        self.tx, self.ty = int(tiles_x), int(tiles_y)
        self.nx, self.ny = self.tx * self.tile + 1, self.ty * self.tile + 1
        self.top, self.bottom, self.tol = float(top), float(bottom), float(tol)
        self.thin = self.tol if thin is None else max(float(thin), self.tol)    # how far the thinning may go
        self.ridge = RIDGE * self.thin
        self.lift = RIDGE * self.tol                    # how far over the finished part a node on it goes ...
        self.deep = 2.0 * self.lift                     # ... from this far under it (deeper: the part shows)
        self.part = None                                # the finished part seen from above (``set_part``)
        self.uncut = self.top + PAD
        self.xs = self.x0 + np.arange(self.nx) * self.cell
        self.ys = self.y0 + np.arange(self.ny) * self.cell
        self.h = np.full((self.ny, self.nx), self.uncut)
        self.owner = np.full((self.ny, self.nx), -1, np.int32)
        self.shape = np.full((self.ny, self.nx), -1, np.int32)        # the move whose surface the node lies on
        self.inside = np.full((self.ny, self.nx), -np.inf, np.float32)    # ... and how deep inside its edge
        self.active = np.zeros((self.ty, self.tx), bool)              # tiles with a cut node on or next to them
        self.tab = _rtin(self.tile)
        self.k = 0                                      # moves stamped
        self.n = 0
        self.shapes: list = []
        self.snapshots: dict = {}
        self.every = SNAPSHOT_MIN
        self.dirty = np.zeros((self.ty, self.tx), bool)  # tiles whose nodes changed since their mesh was made
        self.last = np.full((self.ty, self.tx), -1, np.int64)   # the last move that can change each tile
        self._done = np.ones((self.ty, self.tx), bool)  # tiles no move to come can change: thinned with strips
        self._own: dict = {}                            # (J, I) -> what a tile knows without its neighbours
        self._mesh: dict = {}                           # (J, I) -> [signature, serial, verts, tris, move]
        self._serial = 0
        self._overlay: list = []                        # (i0, i1, j0, j1, h, owner) to put back
        self._slots: list = []                          # the half-done moves stamped now (their places in the table)
        self.stats = dict(stamped=0, meshed=0, seconds_stamp=0.0, seconds_mesh=0.0)

    # -- the moves ---------------------------------------------------------------

    def set_moves(self, shapes: list, shape_i, a, b, z0, z1, tag, cls, slots: int = 1) -> None:
        """The program: ``shapes`` and per move its shape's number, the tip's start ``a`` (n, 2) and end ``b``,
        the heights ``z0``, ``z1``, the number written on its faces (``tag``) and its mark class (``cls``).
        ``slots``: how many moves can be half done at one time (one per bit)."""
        n = len(shape_i)
        self.n, self.slots = n, int(slots)
        m = n + self.slots

        def col(v, dtype=float, width=None):
            out = np.zeros((m,) if width is None else (m, width), dtype)
            out[:n] = np.asarray(v, dtype).reshape((n,) if width is None else (n, width))
            return out
        self.shapes = list(shapes)
        self.shape_i = col(shape_i, np.int32)
        self.a, self.b = col(a, float, 2), col(b, float, 2)
        self.z0, self.z1 = col(z0), col(z1)
        self.tag, self.cls = col(tag, np.int64), col(cls, np.int64)
        self.patch = np.zeros((m, 4), np.int64)
        self._patches(np.arange(n))
        per = 20.0 * self.nx * self.ny                  # bytes of one kept state
        self.every = max(SNAPSHOT_MIN, int(math.ceil(n / max(1.0, SNAPSHOT_BYTES / per))))
        # the last move that can change each tile (task 0167: until then it is thinned the quick way)
        self.last = np.full((self.ty, self.tx), -1, np.int64)
        t, r = self.tile, REACH
        for q, (i0, i1, j0, j1) in enumerate(self.patch[:n].tolist()):
            if i1 > i0 and j1 > j0:
                self.last[max(0, (i0 - 1 - r) // t):min(self.ty, (i1 - 1 + r) // t + 1),
                          max(0, (j0 - 1 - r) // t):min(self.tx, (j1 - 1 + r) // t + 1)] = q
        self.reset()

    def _patches(self, q) -> None:
        """The nodes each move can reach: rows i0 .. i1 - 1, columns j0 .. j1 - 1 (empty: i1 <= i0)."""
        R = np.array([s.R for s in self.shapes])[self.shape_i[q]]
        c = self.cell
        xl = np.minimum(self.a[q, 0], self.b[q, 0]) - R
        xh = np.maximum(self.a[q, 0], self.b[q, 0]) + R
        yl = np.minimum(self.a[q, 1], self.b[q, 1]) - R
        yh = np.maximum(self.a[q, 1], self.b[q, 1]) + R
        j0 = np.clip(np.ceil((xl - self.x0) / c), 0, self.nx)
        j1 = np.clip(np.floor((xh - self.x0) / c) + 1, 0, self.nx)
        i0 = np.clip(np.ceil((yl - self.y0) / c), 0, self.ny)
        i1 = np.clip(np.floor((yh - self.y0) / c) + 1, 0, self.ny)
        high = np.minimum(self.z0[q], self.z1[q]) >= self.uncut           # all of it above the block
        i1 = np.where(high, i0, i1)
        self.patch[q] = np.stack([i0, i1, j0, j1], axis=-1).astype(np.int64)

    def _blank(self) -> None:
        self.h.fill(self.uncut)
        self.owner.fill(-1)
        self.shape.fill(-1)
        self.inside.fill(-np.inf)

    def reset(self) -> None:
        self._blank()
        self.k = 0
        self.snapshots = {}
        self._overlay = []
        self._slots = []
        self.dirty[:] = True
        self._own.clear()
        self._mesh.clear()

    # -- stamping ----------------------------------------------------------------

    def _mark(self, i0: int, i1: int, j0: int, j1: int) -> None:
        t, r = self.tile, REACH                         # (a tile's mesh reads a few nodes past its border)
        self.dirty[max(0, (i0 - 1 - r) // t):min(self.ty, (i1 - 1 + r) // t + 1),
                   max(0, (j0 - 1 - r) // t):min(self.tx, (j1 - 1 + r) // t + 1)] = True

    def _stamp(self, q: int, mark: bool = True) -> None:
        i0, i1, j0, j1 = self.patch[q]
        if i1 <= i0 or j1 <= j0:
            return
        H, D = sweep_height(self.shapes[self.shape_i[q]], self.a[q, 0], self.a[q, 1], self.b[q, 0], self.b[q, 1],
                            self.z0[q], self.z1[q], self.xs[None, j0:j1], self.ys[i0:i1, None], depth=True)
        sub = self.h[i0:i1, j0:j1]
        take = H <= sub + TIE
        if not take.any():
            return
        ins = self.inside[i0:i1, j0:j1]
        deeper = take & ((H < sub - TIE) | (D > ins))   # lower, or as low and deeper inside this move's edge
        np.minimum(sub, H, out=sub)
        self.owner[i0:i1, j0:j1][take] = q
        self.shape[i0:i1, j0:j1][deeper] = q
        ins[deeper] = D[deeper]
        if mark:                                        # only the tiles of the nodes that changed
            rows, cols = np.flatnonzero(take.any(axis=1)), np.flatnonzero(take.any(axis=0))
            self._mark(i0 + rows[0], i0 + rows[-1] + 1, j0 + cols[0], j0 + cols[-1] + 1)

    def _arrays(self) -> tuple:
        return self.h, self.owner, self.shape, self.inside

    def _mark_moves(self, k0: int, k1: int) -> None:
        """The tiles the moves k0 .. k1 - 1 can have changed."""
        t = self.tile
        p = self.patch[k0:k1]
        p = p[(p[:, 1] > p[:, 0]) & (p[:, 3] > p[:, 2])]
        if not len(p):
            return
        J0 = np.maximum(0, (p[:, 0] - 1 - REACH) // t)
        J1 = np.minimum(self.ty, (p[:, 1] - 1 + REACH) // t + 1)
        I0 = np.maximum(0, (p[:, 2] - 1 - REACH) // t)
        I1 = np.minimum(self.tx, (p[:, 3] - 1 + REACH) // t + 1)
        boxes = np.unique(np.stack([J0, J1, I0, I1], axis=1), axis=0)
        for a, b, c, d in boxes.tolist():
            self.dirty[a:b, c:d] = True

    def goto(self, k: int, partial=()) -> None:
        """Make the map as it is after the first ``k`` moves. ``partial``: (move, (x, y, z)) for every move that
        is under way - its bit has come from the move's start to that point."""
        import time
        t0 = time.perf_counter()
        for i0, i1, j0, j1, keep in reversed(self._overlay):          # take the half-done moves off again
            for arr, old in zip(self._arrays(), keep):
                arr[i0:i1, j0:j1] = old
            self._mark(i0, i1, j0, j1)
        self._overlay = []
        self._slots = []
        k = max(0, min(int(k), self.n))
        if k < self.k:
            self._mark_moves(k, self.k)
            keys = [s for s in self.snapshots if s <= k]
            if keys:
                s = max(keys)
                for arr, old in zip(self._arrays(), self.snapshots[s]):
                    arr[...] = old
            else:
                s = 0
                self._blank()
            for q in range(s, k):
                self._stamp(q, mark=False)
            self.stats["stamped"] += k - s
            self.k = k
        while self.k < k:
            self._stamp(self.k)
            self.k += 1
            self.stats["stamped"] += 1
            if self.k % self.every == 0 and self.k not in self.snapshots:
                self.snapshots[self.k] = tuple(arr.copy() for arr in self._arrays())
        for slot, (q, end) in enumerate(partial):
            s = self.n + (slot % self.slots)
            self.shape_i[s], self.tag[s], self.cls[s] = self.shape_i[q], self.tag[q], self.cls[q]
            self.a[s], self.z0[s] = self.a[q], self.z0[q]
            self.b[s], self.z1[s] = (float(end[0]), float(end[1])), float(end[2])
            self._patches(np.array([s]))
            i0, i1, j0, j1 = self.patch[s]
            if i1 <= i0 or j1 <= j0:
                continue
            keep = tuple(arr[i0:i1, j0:j1].copy() for arr in self._arrays())
            self._slots.append(s)
            self._stamp(s)
            diff = np.argwhere(keep[1] != self.owner[i0:i1, j0:j1])       # (a stamp that changes a node owns it)
            if len(diff):
                (r0, c0), (r1, c1) = diff.min(axis=0), diff.max(axis=0) + 1
                self._overlay.append((i0 + r0, i0 + r1, j0 + c0, j0 + c1, tuple(a[r0:r1, c0:c1] for a in keep)))
        done = self.last < self.k
        changed = done != self._done
        if changed.any():                               # (a tile that is finished, or no longer, is thinned anew)
            self.dirty |= changed
            self._done = done
        self.stats["seconds_stamp"] += time.perf_counter() - t0

    # -- heights of given moves at given points --------------------------------

    def height_of(self, q, x, y, rim: bool = False):
        """The surface move ``q`` cut at (x, y) (arrays of one shape; ``q`` = -1: the uncut top), ``inf`` outside
        the move's footprint. ``rim=True``: the height of the bit's widest ring there instead - what the surface
        comes to at the footprint's edge next to the point (a ball's surface is upright at its edge: a point a
        hair inside lies micrometres lower)."""
        q = np.asarray(q)
        out = np.full(q.shape, self.uncut)
        cut = np.nonzero(q >= 0)[0]
        if not len(cut):
            return out
        si = self.shape_i[q[cut]]
        kinds = np.unique(si) if len(self.shapes) > 1 else [si[0]]
        for s in kinds:
            sel = cut if len(kinds) == 1 else cut[si == s]
            g = q[sel]
            shape = self.shapes[int(s)]
            H = sweep_height(shape, self.a[g, 0], self.a[g, 1], self.b[g, 0], self.b[g, 1],
                             self.z0[g], self.z1[g], x[sel], y[sel], depth=rim)
            if rim:
                H, D = H
                H = H + shape.rim - shape.f(np.clip(shape.R + EDGE - D, 0.0, shape.R))
            out[sel] = H
        return out

    # -- one tile ----------------------------------------------------------------

    def cut_tiles(self) -> np.ndarray:
        """(ty, tx) bool: the tiles with a cut node on them or right next to them (a wall just past a tile's
        border moves that border's nodes). The tiles next to these are untouched: their borders are straight."""
        for J, I in np.argwhere(self.dirty):
            self._tile(int(J), int(I))
        return self.active

    def box(self, J: int, I: int) -> tuple:         # noqa: E741
        """The tile's box in the map's frame: (x0, y0, x1, y1)."""
        t, c = self.tile, self.cell
        return (float(self.xs[I * t]), float(self.ys[J * t]), float(self.xs[(I + 1) * t]), float(self.ys[(J + 1) * t]))

    def _window(self, J: int, I: int) -> tuple:     # noqa: E741
        """The tile's nodes and one more all round: heights, owners, and the rows / columns they come from."""
        t = self.tile
        gi = np.arange(J * t - 1, (J + 1) * t + 2)
        gj = np.arange(I * t - 1, (I + 1) * t + 2)
        ii, jj = np.clip(gi, 0, self.ny - 1), np.clip(gj, 0, self.nx - 1)
        ix = np.ix_(ii, jj)
        return self.h[ix], self.owner[ix], self.shape[ix], gi, gj

    def _snap(self, hw, ow, gi, gj, moves) -> tuple:
        """Step 1 of ``mesh``: the nodes of a window (a tile and one node round it; ``ow``: the move whose
        surface each lies on, ``self.shape``) moved onto the places where two surfaces meet. Returns (X, Y, Z).

        Every edge of the finest triangles is looked at: along x, along y, and the one diagonal each cell has in
        the hierarchy. So a triangle that reaches across a wall has all its corners on the wall and stands
        upright; with the grid's own edges alone every other cell kept a corner on the floor (a ramp).
        ``moves``: the moves stamped so far whose footprint reaches the window."""
        c, t, tol = self.cell, self.tile, self.tol
        X = np.broadcast_to((self.x0 + gj * c)[None, :], hw.shape).copy()
        Y = np.broadcast_to((self.y0 + gi * c)[:, None], hw.shape).copy()
        Z = hw.copy()
        gx, gy = X.copy(), Y.copy()                     # the nodes' own places
        best = np.full(hw.shape, np.inf)
        flank = np.full(hw.shape, -1, np.int64)         # for a node on a wall: the move whose flank the wall is
        foot = np.full(hw.shape, np.inf)                # ... and for the wall's top node the height of its foot
        mate = np.full(hw.shape + (2,), -9, np.int64)   # ... and the node at the other end of the wall (row, column)
        kinked = np.array([s.kind in (CONE, PROFILE) for s in self.shapes] + [False])
        # a cell's diagonal runs from its first corner up to the right where row + column is even, else from its
        # second corner up to the left (the hierarchy's finest triangles; the same in every tile)
        even = ((gi[:-1, None] + gj[None, :-1]) % 2 == 0)
        ni, nj = np.nonzero(np.ones((hw.shape[0] - 1, hw.shape[1] - 1), bool) & even)
        mi, mj = np.nonzero(~even)
        rows, cols = np.indices(hw.shape)
        families = (
            (rows[:, :-1].ravel(), cols[:, :-1].ravel(), rows[:, 1:].ravel(), cols[:, 1:].ravel(), c),
            (rows[:-1, :].ravel(), cols[:-1, :].ravel(), rows[1:, :].ravel(), cols[1:, :].ravel(), c),
            (ni, nj, ni + 1, nj + 1, c * math.sqrt(2.0)),
            (mi, mj + 1, mi + 1, mj, c * math.sqrt(2.0)),
        )

        def put(ni, nj, px, py, z, dist, take, wall=None):
            """A node goes to the nearest of the places found for it (a node of two tiles: the same in both)."""
            u = take & (dist < best[ni, nj])
            if u.any():
                ni, nj = ni[u], nj[u]
                X[ni, nj], Y[ni, nj], Z[ni, nj], best[ni, nj] = px[u], py[u], z[u], dist[u]
                flank[ni, nj] = -1 if wall is None else wall[0][u]
                foot[ni, nj] = np.inf if wall is None else wall[1][u]
                mate[ni, nj, 0] = -9 if wall is None else wall[2][u]
                mate[ni, nj, 1] = -9 if wall is None else wall[3][u]

        wtol = max(tol, 1e-6)
        places = []                                     # (task 0167) every place found on an edge, see the end
        for ei, ej, fi, fj, length in families:
            first, second = ow[ei, ej], ow[fi, fj]
            # -- two moves: a wall, a rim, a crease -------------------------------------------------------
            k = np.flatnonzero(first != second)
            if len(k):
                ai, aj, bi, bj = ei[k], ej[k], fi[k], fj[k]
                qa, qb = first[k], second[k]
                xa, ya, xb, yb = gx[ai, aj], gy[ai, aj], gx[bi, bj], gy[bi, bj]
                za, zb = hw[ai, aj], hw[bi, bj]
                ga = self.height_of(qb, xa, ya) - za        # B's surface above A's at A (inf: it ends before A)
                gb = self.height_of(qa, xb, yb) - zb        # A's surface above B's at B
                fa, fb = np.isfinite(ga), np.isfinite(gb)
                ga0, gb0 = np.maximum(ga, 0.0), np.maximum(gb, 0.0)
                # how far the true surface (the lower of the two) is from the straight line A - B where they meet
                with np.errstate(invalid="ignore"):
                    dev = np.where(fa & fb, ga0 * gb0 / np.maximum(ga0 + gb0, 1e-30), np.inf)
                # (a ridge between two passes of one mark class is left out up to ``ridge``: see ``_tile``)
                same = (self.cls[np.maximum(qa, 0)] == self.cls[np.maximum(qb, 0)]) & (qa >= 0) & (qb >= 0)
                crease = fa & fb & (dev > np.where(same, max(tol, self.ridge), tol))
                ridge = crease & same
                if ridge.any():                         # two passes side by side: where they cross (false position)
                    sel = ridge
                    A, B = (ai[sel], aj[sel]), (bi[sel], bj[sel])
                    pa, pb = qa[sel], qb[sel]
                    x0, y0 = xa[sel], ya[sel]
                    dx, dy = xb[sel] - x0, yb[sel] - y0
                    lo, hi = np.zeros(len(pa)), np.ones(len(pa))
                    glo, ghi = ga0[sel], -gb0[sel]      # g = B's surface - A's: >= 0 at A, <= 0 at B
                    s = glo / np.maximum(glo - ghi, 1e-30)
                    for _k in range(3):
                        g = self.height_of(pb, x0 + s * dx, y0 + s * dy) - self.height_of(pa, x0 + s * dx, y0 + s * dy)
                        g = np.where(np.isfinite(g), g, 0.0)
                        pos = g > 0.0
                        lo, glo = np.where(pos, s, lo), np.where(pos, g, glo)
                        hi, ghi = np.where(pos, hi, s), np.where(pos, ghi, g)
                        s = np.clip(lo + (hi - lo) * glo / np.maximum(glo - ghi, 1e-30), lo, hi)
                    px, py = x0 + s * dx, y0 + s * dy
                    z = self.height_of(pa, px, py)
                    z = np.where(np.isfinite(z), z, np.minimum(za[sel], zb[sel]))
                    # (task 0167: where the two passes would cross above the block's top, a strip of the top is
                    # left between them - two rims, below; else they cross at the ridge)
                    low_ = z < self.top
                    put(A[0], A[1], px, py, z, s * length, low_ & (s <= 0.5))
                    put(B[0], B[1], px, py, z, (1.0 - s) * length, low_ & (s > 0.5))
                    rimmed = np.zeros(len(k), bool)
                    rimmed[np.flatnonzero(ridge)[~low_]] = True
                else:
                    rimmed = np.zeros(len(k), bool)
                # (neither surface reaching the other node: something lies between them - the top, a rib)
                only_nn = (~fa & ~fb) & ~((fa ^ fb) | (crease & ~same) | rimmed)
                sel = np.flatnonzero((fa ^ fb) | (crease & ~same) | rimmed | (~fa & ~fb))
                if len(sel):
                    # A wall, a rim, the edge of another tool's cut. The surface between the two nodes is the lowest
                    # of ALL the moves that reach it - not only the two that own the nodes: the pass next door often
                    # cuts a little further (pass ends, overlapping passes). So: how far from A the surface stays
                    # A's move's, how far from B it stays B's, judged against every move that owns a node next to
                    # the edge. Where the two places are one, it is a wall (the two heights differ) or a crease;
                    # where a third move's surface lies between, each node goes to the end of its own.
                    Ai, Aj, Bi, Bj, pa, pb = ai[sel], aj[sel], bi[sel], bj[sel], qa[sel], qb[sel]
                    x0, y0 = xa[sel], ya[sel]
                    dx, dy = xb[sel] - x0, yb[sel] - y0
                    n = len(pa)

                    def heights(cols, u, rim=False):
                        """The candidates' surfaces at the places ``u`` (edges, places) along the edges:
                        (edges, places, candidates)."""
                        m, kk = u.shape[1], cols.shape[1]
                        x = np.repeat((x0[:, None] + u * dx[:, None]).ravel(), kk)
                        y = np.repeat((y0[:, None] + u * dy[:, None]).ravel(), kk)
                        q = np.repeat(cols[:, None, :], m, axis=1).ravel()
                        return self.height_of(q, x, y, rim=rim).reshape(n, m, kk)

                    # The candidates: A's and B's moves, and whichever move is the lowest at one of a few places
                    # on the edge - of all the moves whose footprint reaches the edge, also those that own no
                    # node (a step of a roughed wall is often narrower than a cell).
                    C = [pa, pb, np.full(n, -1, np.int64)]          # (-1: the block's top nobody cut)
                    if len(moves):
                        r0, r1 = np.minimum(gi[Ai], gi[Bi]), np.maximum(gi[Ai], gi[Bi])
                        c0, c1 = np.minimum(gj[Aj], gj[Bj]), np.maximum(gj[Aj], gj[Bj])
                        pm = self.patch[moves]
                        hit = (pm[None, :, 0] <= r1[:, None]) & (pm[None, :, 1] > r0[:, None]) & \
                            (pm[None, :, 2] <= c1[:, None]) & (pm[None, :, 3] > c0[:, None])
                        e, m_ = np.nonzero(hit)
                        if len(e):
                            q = moves[m_]
                            for u in PROBES:
                                h = self.height_of(q, x0[e] + u * dx[e], y0[e] + u * dy[e])
                                order = np.lexsort((h, e))              # per edge: the lowest first
                                se = e[order]
                                top = order[np.concatenate([[True], se[1:] != se[:-1]])]
                                ok = np.isfinite(h[top])
                                col = pa.copy()
                                col[e[top][ok]] = q[top][ok]
                                C.append(col)
                    C = np.stack(C, axis=1)             # (edges, candidates): columns 0 and 1 are A's and B's
                    lo, hi = np.zeros((n, 2)), np.ones((n, 2))       # for A (from A) and for B (from B)
                    for _k in range(SNAP_STEPS):
                        t = 0.5 * (lo + hi)
                        u = np.stack([t[:, 0], 1.0 - t[:, 1]], axis=1)
                        h = heights(C, u)
                        lowest = h.min(axis=2)
                        on = np.stack([h[:, 0, 0], h[:, 1, 1]], axis=1) <= lowest + TIE
                        lo = np.where(on, t, lo)
                        hi = np.where(on, hi, t)
                    ua, ua_off, ub, ub_off = lo[:, 0], hi[:, 0], 1.0 - lo[:, 1], 1.0 - hi[:, 1]
                    ends = heights(C[:, :2], np.stack([ua, ua_off, ub, ub_off], axis=1))
                    rims = heights(C[:, :2], np.stack([ua, ub], axis=1), rim=True)
                    # (a move's surface comes to its rim's height where its footprint ends)
                    zA = np.where(np.isfinite(ends[:, 1, 0]), ends[:, 0, 0], rims[:, 0, 0])
                    zB = np.where(np.isfinite(ends[:, 3, 1]), ends[:, 2, 1], rims[:, 1, 1])
                    zA = np.where(np.isfinite(zA), zA, za[sel])
                    zB = np.where(np.isfinite(zB), zB, zb[sel])
                    one = ub - ua < 0.05                # one place: a wall or a crease
                    mid = 0.5 * (ua + ub)
                    wall = np.abs(zA - zB) > wtol
                    low = np.minimum(zA, zB)
                    uA, uB = np.where(one, mid, ua), np.where(one, mid, ub)
                    hA = np.where(one & ~wall, low, zA)
                    hB = np.where(one & ~wall, low, zB)
                    there = (ua < 1.0 - 1e-3) | (ub > 1e-3)      # (else: nothing changes between the two)
                    # (task 0167: both lowest over a stretch - two passes on one floor, equally deep: nothing meets
                    # there; taken for a crease halfway, it pulled a node off its place with a wall on a grid line)
                    there &= ~(ub < ua - 0.02)
                    # (an edge whose surfaces both end before the other node is a rib only when something
                    # higher than both nodes lies between them - else two passes on one floor)
                    nn = only_nn[sel]
                    if nn.any():
                        hmid = heights(C, np.full((n, 1), 0.5)).min(axis=2)[:, 0]
                        there &= ~nn | (hmid > np.maximum(za[sel], zb[sel]) + tol)
                    # a crease takes one node: the higher one (at a rim: the node on the uncut top, which has
                    # nothing to lose; the node in the cut keeps its place on the steep face), unless the crease
                    # is right next to the lower one
                    a_goes = np.where(za[sel] >= zb[sel], mid <= 0.8, mid < 0.2)
                    # (a wall is the flank of the lower of the two moves)
                    whose = (np.where(one & wall, np.where(zA <= zB, pa, pb), -1), np.minimum(zA, zB))
                    # task 0167: a node stays where it is when its own surface is rounded between it and the
                    # place it would go to (a corner radius' fillet, the flank of a ball, under a wall or a rim) -
                    # also seen from the node before it on the same line: moved, it would cut the rounded strip
                    # off. The place then is a vertex of its own on the edge, with one halfway to it.
                    wantA = there & (~one | wall | a_goes)
                    wantB = there & (~one | wall | ~a_goes)
                    pxA, pyA, pxB, pyB = x0 + uA * dx, y0 + uA * dy, x0 + uB * dx, y0 + uB * dy
                    def lowest(x, y, cols=C):
                        """The lowest of the candidates' surfaces at points (one per edge)."""
                        kk = cols.shape[1]
                        hh = self.height_of(cols.reshape(-1), np.repeat(x, kk), np.repeat(y, kk)).reshape(n, kk)
                        return hh.min(axis=1)
                    rndA, hmA = self._rounded(pa, Ai, Aj, Bi, Bj, pxA, pyA, hA, hw, ow, gx, gy, ROUNDED * self.tol, lowest)
                    rndB, hmB = self._rounded(pb, Bi, Bj, Ai, Aj, pxB, pyB, hB, hw, ow, gx, gy, ROUNDED * self.tol, lowest)
                    rndA &= wantA
                    rndB &= wantB
                    # (task 0167: along a cell's diagonal a node does not go onto the other node itself - a wall
                    # exactly on a line of the grid: that node's neighbour along the line puts the wall there,
                    # and two nodes moved onto one place gave the wall's faces twice, some turned over)
                    if length > 1.2 * c:
                        wantA_ = wantA & (uA < 1.0 - 1e-3)
                        wantB_ = wantB & (uB > 1e-3)
                    else:
                        wantA_, wantB_ = wantA, wantB
                    put(Ai, Aj, pxA, pyA, hA, uA * length, wantA_ & ~rndA, whose + (Bi, Bj))
                    put(Bi, Bj, pxB, pyB, hB, (1.0 - uB) * length, wantB_ & ~rndB, whose + (Ai, Aj))
                    # the places wanted on this edge: each node's, and halfway to a place a node left alone
                    # (a place a node did not take is kept only when the node stayed because its surface is
                    # rounded, at a rim on the uncut top, or on an edge where neither surface reaches the other
                    # node - a rib of top between them; not elsewhere: at the corners of walls and at creases
                    # between two cuts more vertices folded the walls)
                    rib = (~fa & ~fb)[sel] | rimmed[sel] | (one & ~wall & ((pa < 0) | (pb < 0)))
                    no = np.zeros(len(pa), bool)
                    places.append((Ai, Aj, Bi, Bj, pxA, pyA, hA, np.where(wantA & (rndA | rib), pa, -9), uA,
                                   rndA, rib & ~rndA))
                    places.append((Ai, Aj, Bi, Bj, pxB, pyB, hB, np.where(wantB & (rndB | rib), pb, -9), uB,
                                   rndB, rib & ~rndB))
                    places.append((Ai, Aj, Bi, Bj, 0.5 * (x0 + pxA), 0.5 * (y0 + pyA), hmA,
                                   np.where(rndA, pa, -9), 0.5 * uA, no, no))
                    places.append((Ai, Aj, Bi, Bj, 0.5 * (x0 + dx + pxB), 0.5 * (y0 + dy + pyB), hmB,
                                   np.where(rndB, pb, -9), 0.5 * (1.0 + uB), no, no))
            # -- one move with a kink in its own surface (the bottom line of a V-groove) -----------------
            if not kinked.any():
                continue
            k = np.flatnonzero((first == second) & (first >= 0))
            k = k[kinked[self.shape_i[first[k]]]]
            if not len(k):
                continue
            ai, aj, bi, bj, qa = ei[k], ej[k], fi[k], fj[k], first[k]
            xa, ya, xb, yb = gx[ai, aj], gy[ai, aj], gx[bi, bj], gy[bi, bj]
            za, zb = hw[ai, aj], hw[bi, bj]
            mid = self.height_of(qa, 0.5 * (xa + xb), 0.5 * (ya + yb))
            sel = mid < 0.5 * (za + zb) - tol
            if not sel.any():
                continue
            ai, aj, bi, bj, qa = ai[sel], aj[sel], bi[sel], bj[sel], qa[sel]
            x0, y0, dx, dy = xa[sel], ya[sel], (xb - xa)[sel], (yb - ya)[sel]
            lo, hi = np.zeros(len(ai)), np.ones(len(ai))
            for _k in range(SNAP_STEPS + 6):            # the lowest point of the move's surface on this edge
                s1, s2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
                left = self.height_of(qa, x0 + s1 * dx, y0 + s1 * dy) < self.height_of(qa, x0 + s2 * dx, y0 + s2 * dy)
                hi = np.where(left, s2, hi)
                lo = np.where(left, lo, s1)
            s = 0.5 * (lo + hi)
            z = self.height_of(qa, x0 + s * dx, y0 + s * dy)
            ok = np.isfinite(z) & (s > 1e-3) & (s < 1.0 - 1e-3)
            px, py = x0 + s * dx, y0 + s * dy
            put(ai, aj, px, py, z, s * length, ok & (s <= 0.5))
            put(bi, bj, px, py, z, (1.0 - s) * length, ok & (s > 0.5))
        # (a wall whose other node is one of this tile's own is in the tile's surface; else it is the tile's side)
        last = self.tile + 1
        inner = (mate[:, :, 0] >= 1) & (mate[:, :, 0] <= last) & (mate[:, :, 1] >= 1) & (mate[:, :, 1] <= last)
        extra = self._lost(places, X, Y, Z, gx, gy)
        return X, Y, Z, flank, np.where(inner, np.inf, foot), extra

    def _rounded(self, q, Ai, Aj, Bi, Bj, px, py, pz, hw, ow, gx, gy, tol, lowest) -> tuple:
        """Whether node A's own surface (move ``q``) is rounded between A and the place (px, py, pz) it would go
        to on the edge A - B, or between the node before A on that line and the place: (bool, the height of the
        surface halfway from A to the place - ``lowest(x, y)``: of the moves that can reach the edge)."""
        xa, ya = gx[Ai, Aj], gy[Ai, Aj]
        mx, my = 0.5 * (xa + px), 0.5 * (ya + py)
        hown = self.height_of(q, mx, my)
        cut = q >= 0
        out = cut & np.isfinite(hown) & (np.abs(hown - 0.5 * (hw[Ai, Aj] + pz)) > tol)
        hm = np.minimum(hown, lowest(mx, my))
        Pi, Pj = 2 * Ai - Bi, 2 * Aj - Bj
        inw = (Pi >= 0) & (Pi < hw.shape[0]) & (Pj >= 0) & (Pj < hw.shape[1])
        Pi, Pj = np.clip(Pi, 0, hw.shape[0] - 1), np.clip(Pj, 0, hw.shape[1] - 1)
        h2 = self.height_of(q, 0.5 * (gx[Pi, Pj] + px), 0.5 * (gy[Pi, Pj] + py))
        out |= cut & inw & (ow[Pi, Pj] == q) & np.isfinite(h2) & (np.abs(h2 - 0.5 * (hw[Pi, Pj] + pz)) > tol)
        # (only where the place is not the node's own: a place on the node itself is nothing to keep; and not
        # on the finished part, where the map lies over it and the part's faces decide - ``_lift``)
        far = (np.abs(px - xa) + np.abs(py - ya)) > 1e-3 * self.cell
        if self.part is not None:
            pv = self._part_at(xa, ya)
            far &= ~(np.isfinite(pv) & (hw[Ai, Aj] < pv + 3.0 * self.lift))
        return out & far, hm

    @staticmethod
    def _lost(places, X, Y, Z, gx, gy) -> tuple:
        """The places found on edges that no node took (task 0167): the second rim of a strip of top narrower
        than two cells (each node went to one rim), the foot of a wall above a rounded strip (its node stayed).
        Each becomes a vertex of its own on its edge: (a, b, xyz, move, u, on_line) - the edge's two nodes
        (window row, column pairs), the place, the move whose surface it lies on, how far along from ``a``
        (0 .. 1), and whether both nodes still lie on the edge with the place between them."""
        if not places:
            return None
        cols = [np.concatenate(c) for c in zip(*places)]
        Ai, Aj, Bi, Bj, px, py, pz, q, u, foot, pin = cols
        want = (q > -9) & np.isfinite(pz)
        tiny = 1e-9
        # the foot of a wall over a rounded strip next to a node of its edge that stands on the wall over it
        # (moved there along another edge): right under that node, so the wall between them stands upright
        cell = float(np.hypot(gx[0, 1] - gx[0, 0], gy[1, 0] - gy[0, 0])) / math.sqrt(2.0)
        for i, j in ((Ai, Aj), (Bi, Bj)):
            d = np.hypot(X[i, j] - px, Y[i, j] - py)
            under = want & foot & (d > tiny) & (d < 0.1 * cell) & (Z[i, j] > pz + 1e-6)
            px = np.where(under, X[i, j], px)
            py = np.where(under, Y[i, j], py)
        for i, j in ((Ai, Aj), (Bi, Bj)):
            at = (np.abs(X[i, j] - px) < tiny) & (np.abs(Y[i, j] - py) < tiny) & (np.abs(Z[i, j] - pz) < 1e-8)
            want &= ~at
        # ... only where both nodes still lie on the edge, the place between them (a node moved off the edge
        # along another one would make the triangles round the vertex fold)
        ex, ey = gx[Bi, Bj] - gx[Ai, Aj], gy[Bi, Bj] - gy[Ai, Aj]
        L2 = ex * ex + ey * ey
        ua = ((X[Ai, Aj] - gx[Ai, Aj]) * ex + (Y[Ai, Aj] - gy[Ai, Aj]) * ey) / L2
        ub = ((X[Bi, Bj] - gx[Ai, Aj]) * ex + (Y[Bi, Bj] - gy[Ai, Aj]) * ey) / L2
        off_a = np.abs((X[Ai, Aj] - gx[Ai, Aj]) * ey - (Y[Ai, Aj] - gy[Ai, Aj]) * ex) / np.sqrt(L2)
        off_b = np.abs((X[Bi, Bj] - gx[Ai, Aj]) * ey - (Y[Bi, Bj] - gy[Ai, Aj]) * ex) / np.sqrt(L2)
        on_line = (off_a < tiny) & (off_b < tiny) & (ua <= u + 1e-6) & (u <= ub + 1e-6)
        if not want.any():
            return None
        k = np.flatnonzero(want)
        a = np.stack([Ai[k], Aj[k]], axis=1)
        b = np.stack([Bi[k], Bj[k]], axis=1)
        xyz = np.stack([px[k], py[k], pz[k]], axis=1)
        # the same place found twice (a node's edge seen from both families of a cell): once
        key = np.round(np.concatenate([np.minimum(a, b), np.maximum(a, b)], axis=1).astype(float), 0)
        key = np.concatenate([key, np.round(xyz / 1e-9)], axis=1)
        _u, first = np.unique(key, axis=0, return_index=True)
        first = np.sort(first)
        return a[first], b[first], xyz[first], q[k][first], u[k][first], on_line[k][first], pin[k][first]

    def set_part(self, top: np.ndarray) -> None:
        """The finished part seen from above (task 0167): per node the height of its highest point there (``-inf``
        where it is not), in the map's frame. See ``_lift``."""
        self.part = np.asarray(top, float).reshape(self.ny, self.nx)
        self.dirty[:] = True
        self._own.clear()
        self._mesh.clear()

    def _extras(self, extra, t: int) -> tuple:
        """The extra vertices ``_snap`` found (``_lost``) that belong to this tile (both ends of their edge in it):
        (edges (k, 2) node numbers of the tile - a vertex on an edge that already has one lies on the piece from
        the vertex before it, numbered ``(t + 1)² + j`` -, (xyz (k, 3), move (k,))) or (None, None)."""
        if extra is None:
            return None, None
        a, b, xyz, q, u, on_line, pin = extra
        a, b = a - 1, b - 1                             # (window -> tile)
        ok = (a >= 0).all(axis=1) & (a <= t).all(axis=1) & (b >= 0).all(axis=1) & (b <= t).all(axis=1)
        # (on the tile's border both tiles must decide alike: only where the nodes stayed on the edge)
        border = (((a[:, 0] == 0) & (b[:, 0] == 0)) | ((a[:, 0] == t) & (b[:, 0] == t)) |
                  ((a[:, 1] == 0) & (b[:, 1] == 0)) | ((a[:, 1] == t) & (b[:, 1] == t)))
        ok &= on_line | ~border
        if not ok.any():
            return None, None
        a, b, xyz, q, u = a[ok], b[ok], xyz[ok], q[ok], u[ok]
        border, pin = border[ok], pin[ok]
        n = t + 1
        na, nb = a[:, 0] * n + a[:, 1], b[:, 0] * n + b[:, 1]
        # one edge's vertices in order from its first node
        lo, hi = np.minimum(na, nb), np.maximum(na, nb)
        uu = np.where(na <= nb, u, 1.0 - u)
        order = np.lexsort((uu, hi, lo))
        lo, hi, xyz, q = lo[order], hi[order], xyz[order], q[order]
        # (a rim on the block's top lies where the uncut nodes lie, a hair over the top)
        on_top = xyz[:, 2] >= self.top - 1e-9
        xyz = np.column_stack([xyz[:, :2], np.where(on_top, self.uncut, xyz[:, 2])])
        q = np.where(on_top, -1, q)
        if self.part is not None:
            pv = self._part_at(xyz[:, 0], xyz[:, 1])
            z, _l = self._lifted(xyz[:, 2], pv, np.isfinite(pv) & (q >= 0))
            xyz = np.column_stack([xyz[:, :2], z])
        start = lo.copy()
        same = np.zeros(len(lo), bool)
        same[1:] = (lo[1:] == lo[:-1]) & (hi[1:] == hi[:-1])
        idx = n * n + np.arange(len(lo))
        start[same] = idx[np.flatnonzero(same) - 1]
        # (each one's place in the grid, for ``heightmesh.insert_points``)
        ra, rb = np.stack(np.divmod(lo, n), axis=1), np.stack(np.divmod(hi, n), axis=1)
        param = ra + uu[order][:, None] * (rb - ra)
        return np.stack([start, hi], axis=1), (xyz, q.astype(np.int64), border[order], param, pin[order])

    def _part_at(self, X, Y):
        """The finished part's height under places (the four nodes round each: the highest)."""
        c, part = self.cell, self.part
        j = np.clip(np.floor((X - self.x0) / c).astype(np.int64), 0, self.nx - 2)
        i = np.clip(np.floor((Y - self.y0) / c).astype(np.int64), 0, self.ny - 2)
        return np.maximum(np.maximum(part[i, j], part[i, j + 1]), np.maximum(part[i + 1, j], part[i + 1, j + 1]))

    def _lift(self, X, Y, Z, ow, foot) -> tuple:
        """Cut nodes that lie on the finished part, close over it or less than ``deep`` under it, go ``lift`` over
        it (task 0167; ``_lifted``). Where a finishing pass ran over the part, the map's surface and the
        part's lie within micrometres of each other - the thinned map a little under the part on every rounded
        face, a little over it at every crest between two passes - and joining two such surfaces ("Finish at the
        CAD part") made a mass of slivers: 34,000 triangles more on the toolpath test model. Lifted, the map lies
        over the part there and the part's faces stay inside; they show where the bit went clearly deeper. What
        the bit left thinner than ``lift`` (no more than the fine ridges left out anyway) shows as ``lift``.
        Returns (Z, foot, lifted)."""
        c, part = self.cell, self.part
        fj, fi = (X - self.x0) / c, (Y - self.y0) / c
        j = np.clip(np.floor(fj).astype(np.int64), 0, self.nx - 2)
        i = np.clip(np.floor(fi).astype(np.int64), 0, self.ny - 2)
        # the part under the node: at a node of the grid its own value, at a node moved onto a wall or a rim the
        # highest of the four round it (the part is never above the lifted surface)
        pv = np.maximum(np.maximum(part[i, j], part[i, j + 1]), np.maximum(part[i + 1, j], part[i + 1, j + 1]))
        on = (np.abs(fj - np.rint(fj)) < 1e-6) & (np.abs(fi - np.rint(fi)) < 1e-6)
        ri = np.clip(np.rint(fi).astype(np.int64), 0, self.ny - 1)
        rj = np.clip(np.rint(fj).astype(np.int64), 0, self.nx - 1)
        pv = np.where(on, part[ri, rj], pv)
        ok = np.isfinite(pv)
        Z, lifted = self._lifted(Z, pv, ok & (ow >= 0))
        foot, _l = self._lifted(foot, pv, ok & np.isfinite(foot))
        return Z, foot, lifted

    def _lifted(self, Z, pv, ok) -> tuple:
        """``Z`` over the part ``pv``: the part's height + ``lift`` where the map is less than ``lift`` over it or
        under it (but not ``deep`` under it). (Moving the map's own shape up by ``lift`` there instead kept 3 %
        more triangles on the toolpath test model.)"""
        up = self.lift
        d = Z - pv
        lifted = ok & (d < up) & (d > -self.deep)
        return np.where(lifted, pv + up, Z), lifted

    def _moves_at(self, r0: int, r1: int, c0: int, c1: int) -> np.ndarray:
        """The moves stamped so far (and the half-done ones) whose footprint reaches rows r0 .. r1, columns
        c0 .. c1."""
        live = np.concatenate([np.arange(self.k), np.array(self._slots, dtype=np.int64)]).astype(np.int64)
        p = self.patch[live]
        return live[(p[:, 0] <= r1) & (p[:, 1] > r0) & (p[:, 2] <= c1) & (p[:, 3] > c0) & (p[:, 1] > p[:, 0])]

    def _ridges(self, J: int, I: int) -> np.ndarray:     # noqa: E741
        """How far each node of the tile stands above (or below) the surface without its fine ridges: its height
        minus the mean of the nodes ``RIDGE_CELLS`` each way. A plane gives 0 whatever its slope; where the
        difference is more than ``self.ridge`` it is no fine ridge (a wall, a groove, a step) and 0 is given."""
        t, r = self.tile, RIDGE_CELLS
        ii = np.clip(np.arange(J * t - r, (J + 1) * t + r + 1), 0, self.ny - 1)
        jj = np.clip(np.arange(I * t - r, (I + 1) * t + r + 1), 0, self.nx - 1)
        h = self.h[np.ix_(ii, jj)]
        mean = h
        for axis in (0, 1):                             # (a square of nodes: one direction after the other)
            c = np.cumsum(mean, axis=axis)
            n = mean.shape[axis] - 2 * r
            upper = c.take(np.arange(2 * r, 2 * r + n), axis=axis)
            lower = c.take(np.arange(-1, n - 1), axis=axis, mode="clip")
            first = [slice(None)] * 2
            first[axis] = slice(0, 1)
            lower = lower.copy()
            lower[tuple(first)] = 0.0
            mean = (upper - lower) / (2 * r + 1)
        d = h[r:-r, r:-r] - mean
        return np.where(np.abs(d) <= self.ridge, d, 0.0)

    def _tile(self, J: int, I: int) -> dict:        # noqa: E741
        """What a tile knows without its neighbours: the nodes' places after snapping, their owners and mark
        classes, the nodes its own surface needs. Kept until a node of the tile changes."""
        key = (J, I)
        hit = self._own.get(key)
        if hit is not None and not self.dirty[J, I]:
            return hit
        self.dirty[J, I] = False
        t = self.tile
        hw, ow, sw, gi, gj = self._window(J, I)
        own = ow[1:-1, 1:-1]
        self._serial += 1
        self.active[J, I] = bool((ow >= 0).any())
        if not self.active[J, I]:                       # nothing cut here or next to it
            hit = dict(serial=self._serial, need=None)
        else:
            X, Y, Z, flank, foot, extra = self._snap(hw, sw, gi, gj, self._moves_at(gi[0], gi[-1], gj[0], gj[-1]))
            sunk = None
            if self.part is not None:
                Z, foot, sunk = self._lift(X, Y, Z, ow, foot)
            # (task 0167: nothing in the block's top plane itself - a face lying in it beside the block's own top
            # face got slivers of the top named after a move: what is on the top lies where the uncut nodes lie)
            Z = np.where(np.abs(Z - self.top) < 1e-9, self.uncut, Z)
            P = np.stack([X[1:-1, 1:-1], Y[1:-1, 1:-1], Z[1:-1, 1:-1]], axis=-1).reshape(-1, 3)
            o = own.reshape(-1)
            cls = np.where(o >= 0, self.cls[np.maximum(o, 0)], -1)
            edges, ex = self._extras(extra, t)
            Q = P.copy()                                # the nodes as they are judged: without the fine ridges
            ridges = self._ridges(J, I).reshape(-1)
            if sunk is not None:                        # (lifted over the part: its shape, no ridges)
                ridges = np.where(sunk[1:-1, 1:-1].reshape(-1), 0.0, ridges)
            Q[:, 2] -= ridges
            n = t + 1
            # (the ends of a rib's edge are kept, so the rib's second rim goes into that very edge; the other extra
            # vertices go into whatever triangle holds them - keeping all their edges cost 10,000 more triangles
            # on the toolpath test model)
            pins = _hmesh.pins_of(edges[ex[4]], n) if edges is not None and ex[4].any() else None
            strips = _hmesh.own(P.reshape(n, n, 3), Q.reshape(n, n, 3), cls.reshape(n, n), self.thin,
                                strips=bool(self._done[J, I]), pins=pins)
            need = strips["need"]
            flank, foot = flank[1:-1, 1:-1].reshape(-1).copy(), foot[1:-1, 1:-1].reshape(-1).copy()
            if edges is not None:                       # (the extra vertices after the nodes)
                strips["edges"] = edges
                exyz, eq, eborder, eparam, epin = ex
                strips["edges_border"] = eborder
                strips["eparam"] = eparam
                strips["einsert"] = exyz[:, 2] < self.top - 1e-7      # (into a triangle only under the top)
                o = np.concatenate([o, eq])
                cls = np.concatenate([cls, np.where(eq >= 0, self.cls[np.maximum(eq, 0)], -1)])
                P = np.concatenate([P, exyz])
                flank = np.concatenate([flank, np.full(len(eq), -1, flank.dtype)])
                foot = np.concatenate([foot, np.full(len(eq), np.inf)])
            hit = dict(serial=self._serial, need=need, strips=strips, P=P, Q=Q, owner=o.copy(), cls=cls,
                       flank=flank, foot=foot)
        self._own[key] = hit
        return hit

    def mesh(self, J: int, I: int) -> tuple:        # noqa: E741
        """The tile as a closed solid: ``(serial, verts, tris, move)``. ``verts`` float64 (n, 3) in the map's
        frame, ``tris`` int32 (m, 3) with the normals pointing out, ``move`` int64 (m,): the ``tag`` of the move
        that made a triangle of the top surface, -1 for the top where nobody cut, -2 for the sides and the
        bottom (seams inside the material) - but a piece of the side that is a wall (a wall that runs along the
        tile's border) carries the wall's move. ``serial`` changes whenever the mesh does."""
        import time
        t0 = time.perf_counter()
        me = self._tile(J, I)
        tab, n = self.tab, self.tile + 1
        sides = tab["sides"]
        # nodes on the border are kept when the tile on the other side needs them
        forced = None
        sig = [me["serial"]]
        for dj, di, mine, theirs in ((-1, 0, 0, 2), (0, 1, 1, 3), (1, 0, 2, 0), (0, -1, 3, 1)):
            JJ, II = J + dj, I + di
            want = None
            if 0 <= JJ < self.ty and 0 <= II < self.tx:
                other = self._tile(JJ, II)
                if other["need"] is not None:
                    want = other["need"][sides[theirs]]
                    if not want.any():
                        want = None
            if want is None:
                sig.append(b"")
                continue
            sig.append(want.tobytes())
            if forced is None:
                forced = np.zeros(n * n, bool)
            forced[sides[mine]] |= want
        sig = tuple(sig)
        hit = self._mesh.get((J, I))
        if hit is not None and hit[0] == sig:
            return tuple(hit[1:5])
        if me["need"] is None:                          # flat and uncut: the plain top
            P = np.zeros((n * n, 3))
            P[:, 0] = np.tile(self.xs[I * self.tile:I * self.tile + n], n)
            P[:, 1] = np.repeat(self.ys[J * self.tile:J * self.tile + n], n)
            P[:, 2] = self.uncut
            owner = np.full(n * n, -1, np.int64)
            cls = flank = owner
            wall_foot = np.full(n * n, np.inf)
            strips = _PLAIN.get(n)
            if strips is None:                          # (two triangles, the same in every such tile)
                strips = _PLAIN[n] = _hmesh.own(P.reshape(n, n, 3), P.reshape(n, n, 3), np.reshape(cls, (n, n)), 1.0)
        else:
            P, owner, cls, flank, wall_foot = me["P"], me["owner"], me["cls"], me["flank"], me["foot"]
            strips = me["strips"]
        tri, need = _hmesh.triangles(strips, forced, P)
        z = P[:, 2][tri]
        low = tri[np.arange(len(tri)), np.argmin(z, axis=1)]
        o = owner[low]
        # (a level triangle - a floor - can be long: it takes the move that owns the node under its middle)
        level = (z.max(axis=1) - z.min(axis=1)) < 1e-7
        if level.any():
            cen = P[tri[level]].mean(axis=1)
            ci = np.clip(np.rint((cen[:, 1] - self.ys[J * self.tile]) / self.cell), 0, n - 1).astype(np.int64)
            cj = np.clip(np.rint((cen[:, 0] - self.xs[I * self.tile]) / self.cell), 0, n - 1).astype(np.int64)
            oc = owner[ci * n + cj]
            o[level] = np.where(oc >= 0, oc, o[level])
        move = np.where(o >= 0, self.tag[np.maximum(o, 0)], -1)
        used = np.zeros(len(P), bool)
        used[tri.reshape(-1)] = True
        new = np.cumsum(used) - 1
        top = P[used]
        nt = len(top)
        ring = tab["ring"]
        ring = ring[used[ring]]                         # the border once round, the kept nodes only
        if strips.get("eparam") is not None and len(P) > n * n:    # (extra vertices on the border: in the ring)
            ring = self._ring_extras(ring, strips["eparam"], used, n)
        nb = len(ring)
        nxt = np.roll(np.arange(nb), -1)
        # Where a wall runs along the border, the border's nodes are on the wall and the tile's side there IS the
        # wall, from the nodes down to the wall's foot (the tile on the other side has nothing between the two):
        # that piece of the side carries the move whose flank the wall is. The rest of the side is a seam inside
        # the material.
        fz = np.maximum(wall_foot[ring], self.bottom)
        is_top = (flank[ring] >= 0) & (fz < P[ring, 2] - 1e-9)       # (its foot is a node of the next tile)
        walled = is_top & is_top[nxt]
        side = np.where(walled, self.tag[np.maximum(flank[ring], 0)], -2)
        ring = new[ring]
        base = top[ring].copy()
        base[:, 2] = self.bottom
        mid = top[ring].copy()                          # the wall's foot under each border node (else: the node)
        mid[:, 2] = np.where(is_top, fz, mid[:, 2])
        x0, y0, x1, y1 = self.box(J, I)
        verts = np.concatenate([top, mid, base, [[0.5 * (x0 + x1), 0.5 * (y0 + y1), self.bottom]]])
        fm, fb = nt + np.arange(nb), nt + nb + np.arange(nb)
        # (where no wall stands the foot is the node itself: the piece between them has no area and is left out)
        fm = np.where(is_top, fm, ring)
        upper = np.concatenate([np.stack([ring, fm, fm[nxt]], axis=1), np.stack([ring, fm[nxt], ring[nxt]], axis=1)])
        uside = np.concatenate([side, side])
        whole = (upper[:, 0] != upper[:, 1]) & (upper[:, 1] != upper[:, 2]) & (upper[:, 0] != upper[:, 2])
        upper, uside = upper[whole], uside[whole]
        lower = np.concatenate([np.stack([fm, fb, fb[nxt]], axis=1), np.stack([fm, fb[nxt], fm[nxt]], axis=1)])
        floor = np.stack([np.full(nb, nt + 2 * nb), fb[nxt], fb], axis=1)
        tris = np.concatenate([new[tri], upper, lower, floor]).astype(np.int32)
        move = np.concatenate([move, uside, np.full(2 * nb + len(floor), -2, np.int64)])
        self._serial += 1
        out = [sig, self._serial, verts, tris, move, len(tri)]
        self._mesh[(J, I)] = out
        self.stats["meshed"] += 1
        self.stats["seconds_mesh"] += time.perf_counter() - t0
        return tuple(out[1:5])

    @staticmethod
    def _ring_extras(ring: np.ndarray, eparam: np.ndarray, used: np.ndarray, n: int) -> np.ndarray:
        """The ring of border nodes with the extra vertices on the border put in, by their place along it."""
        nn, m = n * n, n - 1

        def along(r, c):
            """The place along the border, counter-clockwise from the corner (0, 0); nan off the border."""
            out = np.full(np.shape(r), np.nan)
            e = 1e-9
            out = np.where(np.abs(c - 0) < e, 3 * m + (m - r), out)
            out = np.where(np.abs(r - m) < e, 2 * m + (m - c), out)
            out = np.where(np.abs(c - m) < e, m + r, out)
            out = np.where(np.abs(r - 0) < e, c, out)
            return np.where(out >= 4 * m - 1e-9, out - 4 * m, out)
        rr, cc = np.divmod(ring, n)
        pos = along(rr.astype(float), cc.astype(float))
        ex = np.flatnonzero(used[nn:nn + len(eparam)])
        if not len(ex):
            return ring
        ep = along(eparam[ex, 0], eparam[ex, 1])
        on = np.isfinite(ep)
        if not on.any():
            return ring
        ids = np.concatenate([ring, nn + ex[on]])
        key = np.concatenate([pos, ep[on]])
        # (the ring starts at its first node: keep that start)
        key = np.where(key < pos[0] - 1e-9, key + 4 * m, key)
        return ids[np.argsort(key, kind="stable")]

    def surface(self, J: int, I: int) -> tuple:     # noqa: E741
        """Only the top of ``mesh``: (verts, tris, move)."""
        _s, v, t, m = self.mesh(J, I)
        keep = np.arange(len(t)) < self._mesh[(J, I)][5]
        return v, t[keep], m[keep]


def top_of(verts: np.ndarray, tris: np.ndarray, xs: np.ndarray, ys: np.ndarray, budget: int = 4_000_000):
    """The highest point of a triangle mesh above every node of a grid (``xs`` columns, ``ys`` rows; the mesh in
    the same frame, z up): (len(ys), len(xs)), ``-inf`` where it is not. Faces that stand upright are skipped
    (their neighbours give their edges)."""
    out = np.full(len(ys) * len(xs), -np.inf)
    p = np.asarray(verts, float)[np.asarray(tris, np.int64)]
    a, b, c = p[:, 0], p[:, 1], p[:, 2]
    den = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    ok = np.abs(den) > 1e-16
    p, a, b, c, den = p[ok], a[ok], b[ok], c[ok], den[ok]
    if not len(p):
        return out.reshape(len(ys), len(xs))
    x0, y0, cx, cy = xs[0], ys[0], xs[1] - xs[0], ys[1] - ys[0]
    j0 = np.clip(np.ceil((p[:, :, 0].min(axis=1) - x0) / cx - 1e-9), 0, len(xs)).astype(np.int64)
    j1 = np.clip(np.floor((p[:, :, 0].max(axis=1) - x0) / cx + 1e-9) + 1, 0, len(xs)).astype(np.int64)
    i0 = np.clip(np.ceil((p[:, :, 1].min(axis=1) - y0) / cy - 1e-9), 0, len(ys)).astype(np.int64)
    i1 = np.clip(np.floor((p[:, :, 1].max(axis=1) - y0) / cy + 1e-9) + 1, 0, len(ys)).astype(np.int64)
    nj, ni = np.maximum(j1 - j0, 0), np.maximum(i1 - i0, 0)
    cnt = nj * ni
    order = np.argsort(cnt)
    start = 0
    while start < len(order):                           # (in batches of at most ``budget`` node-triangle pairs)
        cum = np.cumsum(cnt[order[start:]])
        stop = start + max(1, int(np.searchsorted(cum, budget, side="right")))
        sel = order[start:stop]
        start = stop
        k = cnt[sel]
        if not k.sum():
            continue
        t = np.repeat(sel, k)
        r = np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k)
        jj = j0[t] + r % nj[t]
        ii = i0[t] + r // nj[t]
        x, y = xs[jj], ys[ii]
        l1 = ((x - a[t, 0]) * (c[t, 1] - a[t, 1]) - (c[t, 0] - a[t, 0]) * (y - a[t, 1])) / den[t]
        l2 = ((b[t, 0] - a[t, 0]) * (y - a[t, 1]) - (x - a[t, 0]) * (b[t, 1] - a[t, 1])) / den[t]
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1.0 + 1e-9)
        z = a[t, 2] + l1 * (b[t, 2] - a[t, 2]) + l2 * (c[t, 2] - a[t, 2])
        np.maximum.at(out, (ii * len(xs) + jj)[inside], z[inside])
    return out.reshape(len(ys), len(xs))


# ---------------------------------------------------------------------------
# normals of the map's faces
# ---------------------------------------------------------------------------

SHARP = math.radians(30.0)        # faces further apart than this do not shade into each other
THIN = 1e-4                       # a triangle lower than this x its longest edge has no say in its neighbours' normals
NEEDLE = 1e-6                     # ... and lower than this its own direction is rounding noise


def _fans(vid: np.ndarray) -> tuple:
    """Every pair of corners that share a vertex. ``vid``: the vertex of each corner. Returns (order, first,
    second, starts): ``order`` = the corners sorted by vertex; ``first`` / ``second`` = the pairs as places in
    ``order``; ``first`` is sorted and the pairs of place ``k`` start at ``starts[k]`` (for ``reduceat``)."""
    order = np.argsort(vid, kind="stable")
    v = vid[order]
    counts = np.bincount(v)
    start = np.cumsum(counts) - counts
    rep = counts[v]
    ends = np.cumsum(rep)
    first = np.repeat(np.arange(len(v)), rep)
    second = np.repeat(start[v], rep) + (np.arange(int(ends[-1]) if len(ends) else 0) - np.repeat(ends - rep, rep))
    return order, first, second, ends - rep


def _blend(vid, fn, share, trusted, angle: float) -> np.ndarray:
    """Per corner the sum of ``share`` (a face normal times its weight) of the corners at the same vertex whose
    face normal ``fn`` lies within ``angle`` of this corner's; a corner that is not ``trusted`` takes all."""
    order, first, second, starts = _fans(vid)
    a, b = order[first], order[second]
    near = (np.einsum("ij,ij->i", fn[a], fn[b]) >= math.cos(angle)) | ~trusted[a]
    acc = np.add.reduceat(share[b] * near[:, None], starts, axis=0)
    out = np.empty_like(acc)
    out[order] = acc
    return out


def corner_normals(verts, tris, use=None, angle: float = SHARP, parts: bool = False):
    """One normal per triangle corner, float32 (m * 3, 3): the triangles round the corner's vertex that lie within
    ``angle`` of the corner's own triangle, each weighted by its angle at the vertex (so the result does not
    depend on how a flat face is cut into triangles). ``use``: bool per triangle, False = takes no part (seams,
    faces of another kind); its corners come back as its own face normal. A triangle lower than ``THIN`` x its
    longest edge has no say in the others' normals; one lower than ``NEEDLE`` takes whatever is round it.

    ``parts=True``: also, per corner, the face normal, the share it gives (face normal x angle at the corner) and
    whether its direction is trusted - what ``weld`` adds up across the border between two tiles."""
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3)
    m = len(t)
    if m == 0:
        z = np.zeros((0, 3), np.float32)
        return (z, z, z, np.zeros(0, bool)) if parts else z
    p = v[t]
    e = np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 1], p[:, 0] - p[:, 2]], axis=1)       # edges 0-1, 1-2, 2-0
    fn = np.cross(e[:, 0], -e[:, 2])
    area2 = np.linalg.norm(fn, axis=1)
    longest2 = np.einsum("ijk,ijk->ij", e, e).max(axis=1)
    votes = area2 > THIN * longest2
    trusted = area2 > NEEDLE * longest2
    if use is not None:
        votes &= np.asarray(use, bool)
    fn = fn / np.maximum(area2, 1e-300)[:, None]
    # the angle of each corner: between the edge leaving it and the edge arriving, turned round
    un = e / np.maximum(np.linalg.norm(e, axis=2), 1e-300)[:, :, None]
    cosang = -np.einsum("ijk,ijk->ij", un, np.roll(un, 1, axis=1))
    w = (np.arccos(np.clip(cosang, -1.0, 1.0)) * votes[:, None]).reshape(-1)
    cfn = np.repeat(fn, 3, axis=0)
    share = cfn * w[:, None]
    ctrust = np.repeat(trusted, 3)
    out = _blend(t.reshape(-1), cfn, share, ctrust, angle)
    length = np.linalg.norm(out, axis=1)
    lost = length < 1e-12                               # nothing to go by: the triangle's own direction
    if use is not None:                                 # not ours: its own face normal
        lost |= np.repeat(~np.asarray(use, bool), 3)
    out[lost] = cfn[lost]
    out /= np.maximum(np.linalg.norm(out, axis=1), 1e-300)[:, None]
    out = out.astype(np.float32)
    return (out, cfn, share, ctrust) if parts else out


def weld(keys: np.ndarray, fn: np.ndarray, share: np.ndarray, trusted: np.ndarray, angle: float = SHARP) -> np.ndarray:
    """Corners of several tiles that lie at the same place (``keys``: one number per place) shade into each other
    like the corners of one mesh: the rule of ``corner_normals`` over all of them (its ``parts``). Returns the
    unit normals, float32; a corner with nothing to go by gets its own face normal."""
    if not len(keys):
        return np.zeros((0, 3), np.float32)
    _u, inv = np.unique(keys, return_inverse=True)
    out = _blend(inv.reshape(-1), fn, share, trusted, angle)
    lost = np.linalg.norm(out, axis=1) < 1e-12
    out[lost] = fn[lost]
    out /= np.maximum(np.linalg.norm(out, axis=1), 1e-300)[:, None]
    return out.astype(np.float32)
