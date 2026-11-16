"""The operator who changes the tool (task 0156): a whole person (the 0155 figure with 0157's rig) walks up to the
machine, opens its door, takes the old tool out of the spindle, lays it on a tool trolley, takes the new one, puts it
in, closes the door and, after the last change, walks away again. No Blender.

What comes in (from ``blender/tc_person.py``), all in world coordinates, metres and seconds from the animation's first
frame:

* a ``Floor`` – an occupancy grid of the floor round the machine (what stands between knee and head height), used to
  find a stand spot in front of the spindle, a spot for the trolley and a clear way from the start spot;
* one ``Station`` per tool change: the pause (start, length), the holder in the spindle (``spindle``: 4x4, origin on
  the tool's axis at the grip, z along the axis into the spindle), the tools' world matrices in the spindle, the
  drawbar button (a point on the head with the way it faces), the door's seconds;
* the trolley's top (``Trolley``): where each tool lies (its world matrix, worked out here);
* a ``Door`` (optional): a slide or turn joint's axis, its closed and open value and the handle.

``Operator.plan()`` works out the walk with ``core/people.py`` (planted feet, the gait's speed), and ``sample(times)``
gives every frame: the root (x, y, z, heading), the ``person_rig.Pose`` (arms by ``Figure.arm_ik`` on the holder, the
button, the trolley and the door's handle), the door's value and the world matrix of every tool the hand carries.

The moves inside a pause are ``core/toolchange.person_keys`` (the same times the tool copies' visibility uses): the old
tool leaves the spindle at the end of "release", the new one is in at the end of "clamp".

Hands (props_detail frames, figure space): a hand bone runs along its frame's -z (fingers), x = into the palm for the
right hand and out of its back for the left. The right hand holds a holder like a handshake: palm beside the holder,
facing it, fingers wrapped round, thumb along the tool's axis towards the spindle. On the trolley the tool lies across
(its axis to the person's left) with the hand turned palm down – the forearm's natural turn.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np

from . import people as PL
from . import person_rig as R
from . import toolchange as TC

BODY = 0.27                  # m: the person's half width / depth (shoulders, toes) – kept off the machine
WORK_ROOM = 0.25             # m: round the stand spot (toes and belly in front, the arms close by when it turns)
WALK_MARGIN = 0.06           # m: the way is planned this much further from things (corners are rounded)
BAND = (0.08, 1.95)          # m above the floor: what is in the way of a walking person
SLAB = 0.1                   # m: the floor map also keeps what stands in each 10 cm slice of height (head, chest)
SLABS = 24                   # … up to 2.4 m
HEAD_R, CHEST_R = 0.11, 0.15  # m: the head and the upper chest kept off things when the person leans in
TROLLEY_SIZE = (0.68, 0.46, 0.96)     # length, width, height (core/props_detail tool trolley)
TROLLEY_BODY = 0.43          # m: the trolley's half diagonal, kept off the machine
GRIP_GAP = 0.004             # m: the hand's fist is this much wider than the holder (no skin in the steel)
PRESS = 0.003                # m: the drawbar button goes in this far
PULL = 0.05                  # m: the tool comes down this far out of the spindle (its taper out), then out
ARRIVE = 0.4                 # s: the person stands at the machine this long before a pause starts
DEPART = 0.3                 # s: after the last pause the person waits this long before walking away
WALK_GAIT = "WALK"
REACH = 0.985                # of the arm's length: what a hand can reach without straining
HOLDER_R = 0.025             # m: the holder's radius where the hand grips it (BT30/BT40 flange ~ 23–32 mm)
GRIP_BELOW = 0.085           # m: the fist's middle below the spindle's gauge line (its thumb points up along the holder)
ELBOW = {"l": np.array((0.35, 0.25, -1.0)), "r": np.array((-0.5, 0.3, -1.0))}   # elbows down, a little out and back
THUMB_TILT = 25.0            # degrees: the gripping thumb leans back from the tool's axis (it stays off the spindle)
ENTRY = 0.3                  # m: a hand goes in and out of the machine through a point this far in front of the
                             # holder, at the holder's height (no straight line from the hip through the table)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def unit(v) -> np.ndarray:
    return R.unit(v)


def m4(Rm, p) -> np.ndarray:
    return PL.m4(Rm, p)


def root4(root) -> np.ndarray:
    """The person object's world matrix of a root (x, y, z, heading)."""
    x, y, z, h = root
    return m4(R.rz(h), (x, y, z))


def to_fig(root, M) -> np.ndarray:
    """A world 4x4 into figure space."""
    return PL.inv4(root4(root)) @ np.asarray(M, float)


def to_world(root, M) -> np.ndarray:
    return root4(root) @ np.asarray(M, float)


def frame_of(z, y) -> np.ndarray:
    """A 3x3 frame with z along ``z`` and y as near ``y`` as can be (columns x, y, z)."""
    z = unit(z)
    y = np.asarray(y, float) - z * float(np.dot(y, z))
    if np.linalg.norm(y) < 1e-6:
        y = np.array((0.0, 0.0, 1.0)) - z * z[2]
        if np.linalg.norm(y) < 1e-6:
            y = np.array((0.0, 1.0, 0.0))
    y = unit(y)
    return np.column_stack((np.cross(y, z), y, z))


# ---------------------------------------------------------------------------
# the floor: what is in the way, a stand spot, a clear way
# ---------------------------------------------------------------------------

class Floor:
    """An occupancy grid of the floor (x, y) between ``lo`` and ``hi``: a cell is taken when something stands in it
    between ``BAND`` above the floor. ``free(r)`` = the cells a body of radius ``r`` can stand on."""

    def __init__(self, lo, hi, z: float = 0.0, cell: float = 0.05, max_cells: int = 320):
        lo = np.asarray(lo[:2], float)
        hi = np.asarray(hi[:2], float)
        span = float(max(hi - lo))
        self.cell = max(float(cell), span / max_cells)
        self.lo = lo
        self.shape = (int(math.ceil((hi[0] - lo[0]) / self.cell)) + 1, int(math.ceil((hi[1] - lo[1]) / self.cell)) + 1)
        self.occ = np.zeros(self.shape, bool)
        self.slab = np.zeros((SLABS,) + self.shape, bool)
        self.z = float(z)
        self._free: dict = {}

    # -- filling ------------------------------------------------------------------------------------------------
    def _mark(self, pts) -> None:
        p = np.asarray(pts, float).reshape(-1, 3)
        if not len(p):
            return
        ij = np.floor((p[:, :2] - self.lo) / self.cell + 0.5).astype(int)
        h = p[:, 2] - self.z
        ok = (ij[:, 0] >= 0) & (ij[:, 1] >= 0) & (ij[:, 0] < self.shape[0]) & (ij[:, 1] < self.shape[1])
        band = ok & (h >= BAND[0]) & (h <= BAND[1])
        self.occ[ij[band, 0], ij[band, 1]] = True
        k = np.floor(h / SLAB).astype(int)
        sl = ok & (k >= 0) & (k < SLABS)
        self.slab[k[sl], ij[sl, 0], ij[sl, 1]] = True
        self._free.clear()

    def add_points(self, pts) -> None:
        """Points (n, 3) of something solid: those in the band take their cell (and their slice of height)."""
        self._mark(pts)

    def add_box(self, lo, hi) -> None:
        """A solid box (world, axis-aligned)."""
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        xs = np.arange(lo[0], hi[0] + self.cell, self.cell * 0.5)
        ys = np.arange(lo[1], hi[1] + self.cell, self.cell * 0.5)
        zs = np.arange(lo[2], hi[2] + SLAB, SLAB * 0.5)
        X, Y, Z = np.meshgrid(np.clip(xs, lo[0], hi[0]), np.clip(ys, lo[1], hi[1]), np.clip(zs, lo[2], hi[2]))
        self._mark(np.column_stack((X.ravel(), Y.ravel(), Z.ravel())))

    def add_triangles(self, tris) -> None:
        """Triangles (n, 3, 3) of a surface: their points in the band take their cells (sampled finer than a cell)."""
        t = np.asarray(tris, float).reshape(-1, 3, 3)
        if not len(t):
            return
        zlo, zhi = self.z, self.z + SLAB * SLABS
        tz = t[:, :, 2]
        t = t[(tz.max(axis=1) >= zlo) & (tz.min(axis=1) <= zhi)]
        if not len(t):
            return
        edge = np.max(np.linalg.norm(t - np.roll(t, 1, axis=1), axis=2), axis=1)
        n = np.clip(np.ceil(edge / (self.cell * 0.5)).astype(int), 1, 400)
        for k in np.unique(n):
            sel = t[n == k]
            ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
            keep = ii + jj <= k
            a = (ii[keep] / k)[None, :, None]
            b = (jj[keep] / k)[None, :, None]
            pts = sel[:, 0:1] * (1 - a - b) + sel[:, 1:2] * a + sel[:, 2:3] * b
            self._mark(pts.reshape(-1, 3))

    # -- reading -----------------------------------------------------------------------------------------------
    def ij(self, xy) -> tuple:
        v = np.floor((np.asarray(xy[:2], float) - self.lo) / self.cell + 0.5).astype(int)
        return int(v[0]), int(v[1])

    def xy(self, i: int, j: int) -> np.ndarray:
        return self.lo + np.array((i, j), float) * self.cell

    def free(self, radius: float) -> np.ndarray:
        """Cells whose centre is at least ``radius`` from every taken cell (outside the grid counts as free)."""
        key = round(radius, 4)
        if key in self._free:
            return self._free[key]
        r = int(math.ceil(radius / self.cell))
        blocked = self.occ.copy()
        nx, ny = self.shape
        if self.occ.any():
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if (di == 0 and dj == 0) or (di * di + dj * dj) * self.cell ** 2 > radius ** 2:
                        continue
                    a0, a1 = max(0, di), min(nx, nx + di)
                    b0, b1 = max(0, dj), min(ny, ny + dj)
                    blocked[a0:a1, b0:b1] |= self.occ[a0 - di:a1 - di, b0 - dj:b1 - dj]
        out = ~blocked
        self._free[key] = out
        return out

    def is_free(self, xy, radius: float) -> bool:
        i, j = self.ij(xy)
        if not (0 <= i < self.shape[0] and 0 <= j < self.shape[1]):
            return True
        return bool(self.free(radius)[i, j])

    def clear_at(self, p, radius: float, half_h: float) -> bool:
        """Nothing within ``radius`` (across) and ``half_h`` (up and down) of the world point ``p``."""
        h0, h1 = p[2] - half_h - self.z, p[2] + half_h - self.z
        k0, k1 = max(0, int(math.floor(h0 / SLAB))), min(SLABS - 1, int(math.floor(h1 / SLAB)))
        if k1 < 0 or k0 > SLABS - 1 or k0 > k1:
            return True
        i0, j0 = self.ij(p)
        r = int(math.ceil(radius / self.cell))
        a0, a1 = max(0, i0 - r), min(self.shape[0], i0 + r + 1)
        b0, b1 = max(0, j0 - r), min(self.shape[1], j0 + r + 1)
        if a0 >= a1 or b0 >= b1:
            return True
        sub = self.slab[k0:k1 + 1, a0:a1, b0:b1].any(axis=0)
        if not sub.any():
            return True
        ii, jj = np.nonzero(sub)
        d2 = ((ii + a0 - i0) ** 2 + (jj + b0 - j0) ** 2) * self.cell ** 2
        return bool(d2.min() > radius * radius)

    def clearance(self, xy) -> float:
        """How far ``xy`` is from the nearest taken cell (m; inf on an empty floor)."""
        if not self.occ.any():
            return math.inf
        ii, jj = np.nonzero(self.occ)
        d = np.hypot(self.lo[0] + ii * self.cell - xy[0], self.lo[1] + jj * self.cell - xy[1])
        return float(d.min())

    def nearest_free(self, xy, radius: float, reach: float = 2.0):
        """The free spot nearest ``xy`` (within ``reach``), or None."""
        if self.is_free(xy, radius):
            return np.asarray(xy[:2], float)
        f = self.free(radius)
        i0, j0 = self.ij(xy)
        r = int(math.ceil(reach / self.cell))
        a0, a1 = max(0, i0 - r), min(self.shape[0], i0 + r + 1)
        b0, b1 = max(0, j0 - r), min(self.shape[1], j0 + r + 1)
        sub = f[a0:a1, b0:b1]
        if not sub.any():
            return None
        ii, jj = np.nonzero(sub)
        ii, jj = ii + a0, jj + b0
        d = (ii - i0) ** 2 + (jj - j0) ** 2
        k = int(d.argmin())
        return self.xy(int(ii[k]), int(jj[k]))

    def line_free(self, a, b, radius: float) -> bool:
        a, b = np.asarray(a[:2], float), np.asarray(b[:2], float)
        n = max(2, int(math.ceil(np.linalg.norm(b - a) / (self.cell * 0.5))) + 1)
        for u in np.linspace(0.0, 1.0, n):
            if not self.is_free(a + (b - a) * u, radius):
                return False
        return True

    def way(self, a, b, radius: float) -> list | None:
        """A clear way from ``a`` to ``b`` (x, y) for a body of ``radius``: [a, corners …, b], or None. A* over the
        grid (8 neighbours), then pulled tight (a corner is dropped when the line past it is clear)."""
        f = self.free(radius)
        a, b = np.asarray(a[:2], float), np.asarray(b[:2], float)
        if self.line_free(a, b, radius):
            return [a, b]
        sa, sb = self.ij(a), self.ij(b)
        nx, ny = self.shape

        def ok(c):
            return 0 <= c[0] < nx and 0 <= c[1] < ny and f[c]

        if not ok(sa) or not ok(sb):
            return None
        steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142),
                 (-1, 1, 1.4142), (-1, -1, 1.4142)]

        def h(c):
            dx, dy = abs(c[0] - sb[0]), abs(c[1] - sb[1])
            return max(dx, dy) + 0.4142 * min(dx, dy)

        came = {sa: None}
        g = {sa: 0.0}
        todo = [(h(sa), sa)]
        while todo:
            _f, c = heapq.heappop(todo)
            if c == sb:
                break
            for di, dj, w in steps:
                n = (c[0] + di, c[1] + dj)
                if not ok(n):
                    continue
                gn = g[c] + w
                if gn < g.get(n, math.inf) - 1e-9:
                    g[n] = gn
                    came[n] = c
                    heapq.heappush(todo, (gn + h(n), n))
        if sb not in came:
            return None
        cells = []
        c = sb
        while c is not None:
            cells.append(c)
            c = came[c]
        cells.reverse()
        pts = [a] + [self.xy(*c) for c in cells[1:-1]] + [b]
        out = [pts[0]]                                    # pull tight
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.line_free(pts[i], pts[j], radius):
                j -= 1
            out.append(pts[j])
            i = j
        return out


def way_to(floor: Floor, start, goal, radius: float = BODY, margin: float = WALK_MARGIN) -> list | None:
    """A clear way from ``start`` to ``goal`` kept ``margin`` further off things than ``radius`` where it can be;
    the last stretch to a goal close to the machine is planned with ``radius`` alone."""
    a, b = np.asarray(start[:2], float), np.asarray(goal[:2], float)
    w = floor.way(a, b, radius + margin)
    if w is not None:
        return w
    near = floor.nearest_free(b, radius + margin, 0.6)
    last = min(radius, WORK_ROOM)                 # the stand spot itself may be closer to things than a walk
    if near is not None and floor.line_free(near, b, last):
        a = floor.nearest_free(a, radius + margin, 1.0)
        if a is not None:
            w = floor.way(a, near, radius + margin)
            if w is not None:
                return ([np.asarray(start[:2], float)] if np.linalg.norm(a - start[:2]) > 1e-6 else []) + w + [b]
    return floor.way(np.asarray(start[:2], float), b, last)


def walkable(points, corner: float = 0.22) -> list:
    """The way with two points near each corner, so the walk's rounding (``people.Path``) stays tight round it."""
    pts = [np.asarray(p[:2], float) for p in points]
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        la, lc = float(np.linalg.norm(b - a)), float(np.linalg.norm(c - b))
        da, dc = min(corner, 0.4 * la), min(corner, 0.4 * lc)
        if da > 1e-3:
            out.append(b + (a - b) / la * da)
        out.append(b)
        if dc > 1e-3:
            out.append(b + (c - b) / lc * dc)
    out.append(pts[-1])
    return out


def stand_spot(floor: Floor, holder_xy, front, radius: float = WORK_ROOM, near: float = 0.32, far: float = 2.0):
    """Where the person stands in front of the holder: the nearest free spot along ``front`` (the way from the machine
    to the person), tried a little to either side when straight in front is taken. None when nothing is free."""
    hx = np.asarray(holder_xy[:2], float)
    f = unit(np.asarray(front[:2], float))
    side = np.array((-f[1], f[0]))
    for d in np.arange(near, far + 1e-9, floor.cell * 0.5):
        for s in (0.0, 0.08, -0.08, 0.16, -0.16):
            p = hx + f * d + side * s
            if floor.is_free(p, radius):
                return p
    return None


def trolley_spot(floor: Floor, stand_xy, heading: float, right: bool = True):
    """Where the trolley stands beside the person (its centre, and its turn about z): on the right hand side (or the
    left), its long side along the way the person faces, a little behind the person. None when it does not fit."""
    f = PL.facing(heading)
    left = PL.left_of(heading)
    s = -1.0 if right else 1.0
    stand = np.asarray(stand_xy[:2], float)
    for lat in (0.55, 0.62, 0.7):
        for back in (0.08, 0.2, -0.04, 0.32):
            c = stand + left * s * lat - f * back
            if floor.is_free(c, TROLLEY_BODY) and floor.clearance(c) >= TROLLEY_BODY:
                return c, heading
    return None


# ---------------------------------------------------------------------------
# what the operator works with
# ---------------------------------------------------------------------------

@dataclass
class Door:
    """A machine door moved by one joint. ``kind`` SLIDE (``open``/``closed`` in metres along ``direction``) or
    ROTATE (radians about ``direction`` through ``origin``). ``handle``: the handle's world point with the door
    closed; ``out``: the way the door's face looks (towards the person)."""
    kind: str
    origin: np.ndarray
    direction: np.ndarray
    closed: float
    open: float
    handle: np.ndarray
    out: np.ndarray
    speed: float = 0.0           # m/s (slide) or rad/s (turn); 0: the default

    def travel_time(self) -> float:
        d = abs(self.open - self.closed)
        sp = self.speed or (0.7 if self.kind == "SLIDE" else math.radians(110))
        return max(TC.DOOR_MIN, d / sp)

    def move(self, v: float) -> np.ndarray:
        """The 4x4 that takes the closed door to the door at value ``v``."""
        dv = float(v) - self.closed
        d = unit(self.direction)
        if self.kind == "SLIDE":
            return m4(np.eye(3), d * dv)
        Rm = _axis_angle(d, dv)
        o = np.asarray(self.origin, float)
        return m4(Rm, o - Rm @ o)

    def at(self, v: float, point) -> np.ndarray:
        M = self.move(v)
        return (M[:3, :3] @ np.asarray(point, float)) + M[:3, 3]


def _axis_angle(d, a) -> np.ndarray:
    x, y, z = unit(d)
    c, s = math.cos(a), math.sin(a)
    C = 1 - c
    return np.array(((c + x * x * C, x * y * C - z * s, x * z * C + y * s),
                     (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
                     (z * x * C - y * s, z * y * C + x * s, c + z * z * C)))


@dataclass
class Station:
    """One tool change as the operator does it. ``spindle``: the holder frame at the spindle (4x4, origin on the
    tool's axis at the grip, z along the axis into the spindle). ``tools``: {T: the tool copy's world matrix in the
    spindle}. ``grip``: {T: (the grip frame in the copy's own space, the tool's largest radius)}. ``button``: (point,
    the way the head's face looks there) or None."""
    old: int
    new: int
    t0: float
    length: float
    spindle: np.ndarray
    tools: dict
    grip: dict
    button: tuple | None = None
    door: float = 0.0
    holder_r: float = HOLDER_R


@dataclass
class Trolley:
    """The tool trolley: its centre on the floor, its turn about z, its top's height; ``slots``: {T: world matrix of
    the tool lying there} (``place_tools``)."""
    centre: np.ndarray
    heading: float
    top: float
    slots: dict = field(default_factory=dict)


def place_tools(trolley: Trolley, numbers: list, grips: dict, person_heading: float) -> None:
    """Lay the tools on the trolley's top in a row along its length (the way the person faces), each across it with
    its taper to the person's left, the grip towards the near edge."""
    f3 = np.array((*PL.facing(person_heading), 0.0))
    left3 = np.array((*PL.left_of(person_heading), 0.0))
    L = TROLLEY_SIZE[0]
    gap = max([2 * grips[n][1] + 0.025 for n in numbers if n in grips] + [0.07])
    count = max(1, len(numbers))
    span = min(L - 0.12, gap * (count - 1))
    for k, n in enumerate(numbers):
        if n not in grips:
            continue
        L_grip, r = grips[n]
        along = (span / 2 - k * (span / max(1, count - 1))) if count > 1 else 0.0
        p = np.asarray(trolley.centre[:2], float)
        point = np.array((p[0], p[1], trolley.top + r + 0.002)) + f3 * along + left3 * 0.06
        H = m4(np.column_stack((np.cross((0.0, 0.0, 1.0), left3), (0.0, 0.0, 1.0), left3)), point)
        trolley.slots[n] = H @ PL.inv4(L_grip)


# ---------------------------------------------------------------------------
# hands
# ---------------------------------------------------------------------------

def grip_hand(H: np.ndarray, k: float, holder_r: float, right_way: np.ndarray, side: str = "r",
              open_by: float = 0.0) -> np.ndarray:
    """The right hand's frame (4x4, its head = the wrist) holding a holder whose grip frame is ``H`` (z along the axis
    into the spindle): the palm beside the holder on the ``right_way`` side, facing it, the thumb along z, the
    fingers round it. ``open_by``: the palm that much further off (reaching, letting go)."""
    z = unit(H[:3, 2])
    y_h = np.asarray(right_way, float) - z * float(np.dot(right_way, z))
    y_h = unit(y_h)
    x_palm = -y_h                                     # into the palm: towards the holder
    z0 = np.cross(x_palm, -z)
    a = math.radians(THUMB_TILT)                      # the thumb up along the holder, tilted back off the spindle
    thumb = z * math.cos(a) + z0 * math.sin(a)
    y_hand = -thumb                                   # the thumb is -y of the hand
    z_hand = np.cross(x_palm, y_hand)
    Rh = np.column_stack((x_palm, y_hand, z_hand))
    grip = PL._grip_local(side, k) + np.array((-(holder_r + GRIP_GAP - 0.016), 0.0, 0.0)) * (1.0 if side == "r" else -1.0)
    centre = H[:3, 3] + y_h * open_by
    return m4(Rh, centre - Rh @ grip)


#: the index finger's tip in its hand bone's frame (props_detail._hand: the palm 0.095 long, the index finger 0.074,
#: 0.03 to the thumb's side), metres of a 1.75 m person
INDEX_TIP = (0.0, -0.03, -(0.095 + 0.074))


def press_hand(point, face, k: float, side: str = "l", press: float = 0.0) -> np.ndarray:
    """A hand pressing a button at ``point`` with the tip of its straight index finger (``face``: the way the face
    there looks): the finger points into the face, the back of the hand up."""
    n = unit(face)
    Z = -n                                            # along the fingers: into the face
    up = np.array((0.0, 0.0, 1.0)) - n * float(n[2])
    up = unit(up) if np.linalg.norm(up) > 1e-6 else unit(np.cross(n, (1.0, 0.0, 0.0)))
    sd = 1.0 if side == "l" else -1.0
    X = up * sd                                       # left: x out of the back of the hand; right: into the palm
    R2 = -Z
    Y = np.cross(R2, X)
    Rh = np.column_stack((X, Y, R2))
    tip = np.asarray(point, float) + n * (0.004 - press)
    return m4(Rh, tip - Rh @ (np.asarray(INDEX_TIP, float) * k))


def _rest_arms(fig: R.Figure, pose: R.Pose) -> dict:
    fk = fig.fk(pose)
    return {s: m4(fk[f"{s}_hand"][1], fk[f"{s}_hand"][0]) for s in R.SIDES}


def _blend4(A, B, w: float) -> np.ndarray:
    if w <= 0:
        return np.array(A, float)
    if w >= 1:
        return np.array(B, float)
    return m4(R.slerp(A[:3, :3], B[:3, :3], w), A[:3, 3] + (B[:3, 3] - A[:3, 3]) * w)


# ---------------------------------------------------------------------------
# the operator
# ---------------------------------------------------------------------------

@dataclass
class Target:
    """A hand's aim at the end of a move (world): its frame (4x4) or None (hanging as the body has it), its fingers
    (0 open … 1 fist), and a lift for the way there (an arc, m)."""
    M: np.ndarray | None
    fingers: float = R.FINGERS_REST
    arc: float = 0.0
    via: np.ndarray | None = None     # a world point the hand passes half way (in or out of the machine)
    point: float = 0.0                # the index finger straight (pressing a button)


class Operator:
    """The operator's plan: where it walks, what each hand does at each change, the door, the carried tools."""

    def __init__(self, height: float, start_xy, stand_xy, way_in: list, stations: list, trolley: Trolley | None,
                 floor_z: float, door: Door | None = None, name: str = "Operator", t_end: float | None = None,
                 floor: Floor | None = None):
        self.fig = R.Figure(height)
        self.k = self.fig.k
        self.start = np.asarray(start_xy[:2], float)
        self.stand = np.asarray(stand_xy[:2], float)
        self.way_in = [np.asarray(p[:2], float) for p in way_in]
        self.stations = sorted(stations, key=lambda s: s.t0)
        self.trolley = trolley
        self.z = float(floor_z)
        self.door = door
        self.floor = floor
        self.name = name
        self.t_end = t_end
        self.notes: list = []
        self.misses: list = []                  # (t, side, metres the hand stayed off its aim)
        self.plan_people = None
        self.person = None
        self.at_start = False
        self._moves = [TC.person_keys(s.t0, s.length, s.door) for s in self.stations]
        self.heading = 0.0
        self._door_memo: dict = {}

    # -- the walk ---------------------------------------------------------------------------------------------
    def facing_target(self) -> np.ndarray:
        if self.stations:
            return self.stations[0].spindle[:3, 3]
        return np.array((self.stand[0], self.stand[1] + 1.0, self.z + 1.0))

    def plan(self) -> None:
        """The walk in (to be at the stand spot ``ARRIVE`` s before the first pause), standing there through every
        change and the walk out after the last one."""
        if not self.stations:
            raise ValueError("no tool changes to do")
        first = self.stations[0].t0
        last = self.stations[-1].t0 + self.stations[-1].length
        tgt = tuple(float(x) for x in self.facing_target())
        pts = walkable(self.way_in)
        path = tuple((float(p[0]), float(p[1]), self.z) for p in pts[1:])
        h0 = PL.heading_of(pts[1] - pts[0]) if len(pts) > 1 else 0.0

        def spec(start, stop, walk_in=True):
            acts = []
            if walk_in:
                acts.append(PL.Action("WALK", place="POINT", point=len(path), gait=WALK_GAIT))
            acts += [PL.Action("TURN", target=tgt), PL.Action("STOP", duration=max(0.05, stop)),
                     PL.Action("WALK", place="POINT", point=0, gait=WALK_GAIT)]
            if walk_in:
                return PL.PersonSpec(self.name, self.fig.height, (float(pts[0][0]), float(pts[0][1]), self.z), h0,
                                     path, tuple(acts), start=start)
            hs = PL.heading_of(np.asarray(tgt[:2]) - self.stand)
            return PL.PersonSpec(self.name, self.fig.height, (float(self.stand[0]), float(self.stand[1]), self.z), hs,
                                 tuple((float(p[0]), float(p[1]), self.z) for p in reversed(pts[:-1])),
                                 (PL.Action("STOP", duration=max(0.05, stop)),
                                  PL.Action("WALK", place="END", gait=WALK_GAIT)) if len(pts) > 1 else
                                 (PL.Action("STOP", duration=max(0.05, stop)),), start=0.0)

        ground = PL.flat_ground(self.z)
        trial = PL.plan([spec(0.0, 1.0)], (), ground)
        p = trial.people[self.name]
        ready = p.step_times[1][1]                       # walked in and turned to the machine
        start = first - ARRIVE - ready
        if len(pts) < 2 or start < 0.0:
            self.at_start = True
            if len(pts) >= 2:
                self.notes.append("The program changes the tool too early for the operator to walk in: the operator "
                                  "stands at the machine from the start")
            pl = PL.plan([spec(0.0, last + DEPART, walk_in=False)], (), ground)
        else:
            stop = (last + DEPART) - (start + ready)
            pl = PL.plan([spec(start, stop)], (), ground)
        self.plan_people = pl
        self.person = pl.people[self.name]
        self.heading = PL.heading_of(np.asarray(tgt[:2]) - self.stand)
        self.notes += [w for w in pl.warnings if "path" not in w.lower()]

    # -- one moment ---------------------------------------------------------------------------------------------
    def _station_at(self, t: float):
        for s, moves in zip(self.stations, self._moves):
            if moves[0][0] - 0.05 <= t <= moves[-1][1] + 0.05:
                return s, moves
        return None, None

    def door_value(self, t: float) -> float | None:
        if self.door is None:
            return None
        v = self.door.closed
        for _s, moves in zip(self.stations, self._moves):
            for a, b, name in moves:
                if name == "open" and t >= a:
                    v = self.door.closed + (self.door.open - self.door.closed) * smooth((t - a) / max(1e-6, b - a))
                if name == "close" and t >= a:
                    v = self.door.open + (self.door.closed - self.door.open) * smooth((t - a) / max(1e-6, b - a))
        return v

    def _right_way(self, root) -> np.ndarray:
        """From a holder towards where the right palm is: the person's right, a little towards the person."""
        h = root[3]
        right = -np.array((*PL.left_of(h), 0.0))
        back = -np.array((*PL.facing(h), 0.0))
        return unit(right + back * 0.35)

    def _aims(self, s: Station, root) -> dict:
        """The hands' aims (world) at the end of each move of a change."""
        k = self.k
        rw = self._right_way(root)
        H = s.spindle
        down = m4(np.eye(3), -unit(H[:3, 2]) * PULL)
        r = s.holder_r
        at = grip_hand(H, k, r, rw)
        near = grip_hand(H, k, r, rw, open_by=0.035)
        pulled = down @ at
        aims: dict = {}
        rest = Target(None)
        towards = np.array((*(-PL.facing(root[3])), 0.0))      # from the machine to the person
        e_in = at[:3, 3] + towards * ENTRY
        e_out = pulled[:3, 3] + towards * ENTRY
        btn = btn_in = None
        e_btn = None
        if s.button is not None:
            btn = Target(press_hand(s.button[0], s.button[1], k), 0.85, point=1.0)
            btn_in = Target(press_hand(s.button[0], s.button[1], k, press=PRESS), 0.85, point=1.0)
            e_btn = btn.M[:3, 3] + towards * ENTRY
        L_rest = rest
        L_out = Target(None, via=e_btn)
        btn_reach = Target(btn.M, 0.85, via=e_btn, point=1.0) if btn is not None else None
        aims["reach"] = (Target(near, 0.05, via=e_in), btn_reach or L_rest)
        aims["grip"] = (Target(at, 0.8), btn or L_rest)
        aims["release"] = (Target(at, 0.8), btn_in or L_rest)
        aims["pull"] = (Target(pulled, 0.8), Target(btn.M, 0.85, point=1.0) if btn is not None else L_rest)
        slot_old = self._slot_hand(s, s.old, H, at)
        slot_new = self._slot_hand(s, s.new, H, at)
        if slot_old is not None:
            above = m4(slot_old[:3, :3], slot_old[:3, 3] + np.array((0.0, 0.0, 0.07)))
            aims["away"] = (Target(above, 0.8, via=e_out), L_out)
            aims["set"] = (Target(slot_old, 0.8), L_rest)
            lift = m4(slot_old[:3, :3], slot_old[:3, 3] + np.array((0.0, 0.0, 0.05)))
            aims["wait"] = (Target(lift, 0.1), L_rest)
        else:
            aims["away"] = (Target(None, 0.8, via=e_out), L_out)
            aims["set"] = aims["wait"] = (Target(None, 0.8), L_rest)
        if slot_new is not None:
            aims["take"] = (Target(slot_new, 0.8), L_rest)
        else:
            aims["take"] = (Target(None, 0.8), L_rest)
        fetch_l = Target(btn_in.M, 0.85, via=e_btn, point=1.0) if btn_in is not None else L_rest
        aims["fetch"] = (Target(pulled, 0.8, via=e_out), fetch_l)
        aims["insert"] = (Target(at, 0.8), btn_in or L_rest)
        aims["clamp"] = (Target(at, 0.8), Target(btn.M, 0.85, point=1.0) if btn is not None else L_rest)
        aims["leave"] = (Target(None, via=e_in), L_out)
        return aims

    def _slot_hand(self, s: Station, n: int, H, at) -> np.ndarray | None:
        """The hand on tool ``n`` lying on the trolley: the same hold as at the spindle (hand in the tool's frame)."""
        if self.trolley is None or n not in self.trolley.slots or n not in s.tools:
            return None
        hold = PL.inv4(s.tools[n]) @ at                   # the hand in the tool's own frame
        return self.trolley.slots[n] @ hold

    def _door_hand(self, v: float, root, contact) -> np.ndarray:
        d = self.door
        p = d.at(v, contact)
        out = unit(d.move(v)[:3, :3] @ d.out)
        H = m4(frame_of((0.0, 0.0, 1.0), -out), p)
        right = -np.array((*PL.left_of(root[3]), 0.0))
        return grip_hand(H, self.k, 0.012, out * 0.7 + right * 0.3)

    def _reachable(self, root, pose, M) -> bool:
        """Whether the right hand reaches ``M`` (world), leaning as far as its head and chest stay clear."""
        fig = self.fig
        lean, yaw, f, lft = self._lean_for(pose, root, M)
        p = pose.copy()
        _apply_bend(p, lean, yaw, f, lft)
        w = to_fig(root, M)[:3, 3]
        return float(np.linalg.norm(w - fig.shoulder(p, "r"))) <= (fig.ARM + fig.FOREARM) * self.k * REACH

    def _bend(self, pose: R.Pose, root, M, amount: float) -> None:
        """Lean the upper body ``amount`` (0 … 1 of the way) towards the aim ``M`` (world): the chest turns towards it
        and the spine bends forward / sideways as far as the right hand needs to reach it."""
        if M is None or amount <= 1e-4:
            return
        lean, yaw, f, lft = self._lean_for(pose, root, M)
        _apply_bend(pose, lean * amount, yaw * amount, f, lft)

    def _lean_for(self, pose: R.Pose, root, M) -> tuple:
        """(lean in degrees, chest turn in radians, forward share, left share) that bring the right shoulder within
        reach of the hand's aim ``M`` (bisection; 0 when it reaches standing)."""
        fig = self.fig
        k = self.k
        w = to_fig(root, M)[:3, 3]
        sh = (fig.shoulder(pose, "l") + fig.shoulder(pose, "r")) / 2
        d = (w - sh)[:2]
        n = float(np.linalg.norm(d))
        f, lft = (-d[1] / n, d[0] / n) if n > 1e-6 else (1.0, 0.0)
        yaw = max(-math.radians(40), min(math.radians(40), math.atan2(d[0], -d[1]))) * 0.7
        yaw *= smooth((n - 0.25 * k) / (0.2 * k))         # only for an aim away from the body (none at the side)
        reach = (fig.ARM + fig.FOREARM) * k * 0.97

        def bent(a):
            p = pose.copy()
            _apply_bend(p, a, yaw, f, lft)
            return p

        def reaches(p):
            return float(np.linalg.norm(w - fig.shoulder(p, "r"))) <= reach

        def clear(p):
            if self.floor is None:
                return True
            fk = fig.fk(p)
            hh, _Rh, ht = fk["head"]
            head = to_world(root, m4(np.eye(3), hh + (ht - hh) * 0.45))[:3, 3]
            chest = to_world(root, m4(np.eye(3), fk["neck"][0]))[:3, 3]
            return (self.floor.clear_at(head, HEAD_R * k, 0.12 * k) and
                    self.floor.clear_at(chest, CHEST_R * k, 0.08 * k))

        p0 = bent(0.0)
        if reaches(p0):
            return 0.0, yaw, f, lft
        lo, hi = 0.0, 55.0
        if not (reaches(bent(hi)) and clear(bent(hi))):
            # it cannot reach without its head or chest in something: lean only as far as stays clear
            a_ok = 0.0
            for a in np.arange(2.0, 55.01, 2.0):
                p = bent(a)
                if not clear(p):
                    break
                a_ok = float(a)
                if reaches(p):
                    break
            return a_ok, yaw, f, lft
        for _ in range(14):
            mid = (lo + hi) / 2
            if reaches(bent(mid)):
                hi = mid
            else:
                lo = mid
        return hi, yaw, f, lft

    def pose(self, t: float, root, base: R.Pose) -> tuple:
        """(pose, {T: carried tool world matrix}, door value) at ``t`` from the walk's pose ``base``."""
        pose = base
        s, moves = self._station_at(t)
        door_v = self.door_value(t)
        if s is None:
            return pose, {}, door_v
        fig = self.fig
        k = self.k
        aims = self._aims(s, root)
        cur, prev_name = moves[-1], moves[-2][2] if len(moves) > 1 else None
        for i, mv in enumerate(moves):
            if t <= mv[1]:
                cur = mv
                prev_name = moves[i - 1][2] if i > 0 else None
                break
        a, b, name = cur
        u = smooth((t - a) / max(1e-6, b - a))
        whole = (moves[0][0], moves[-1][1])
        ease = smooth((t - whole[0]) / 0.5) * smooth((whole[1] - t) / 0.5)
        door_move = name in DOOR_MOVES
        base_pose = pose.copy()

        def aim_of(nm, side):
            if nm is None or nm in DOOR_MOVES or nm not in aims:
                return Target(None)
            return aims[nm][0 if side == "r" else 1]

        # the hands' aims (world) at the start and the end of this move
        if door_move:
            M_r, f_r = self._door_aim(t, root, base_pose, moves, name, a, b, u)
            plan = {"r": (M_r, f_r)}
            # the lean goes from the one of the move's start to the one of its end (not the least each moment
            # needs: that came and went within a few frames)
            bend_from = self._door_aim(a + 1e-6, root, base_pose, moves, name, a, b, 0.0)[0]
            bend_to = self._door_aim(b - 1e-6, root, base_pose, moves, name, a, b, 1.0)[0]
            w_bend = u
        else:
            plan = {}
            t_from = {sd: aim_of(prev_name, sd) for sd in ("r", "l")}
            t_to = {sd: aim_of(name, sd) for sd in ("r", "l")}
            bend_from, bend_to = t_from["r"].M, t_to["r"].M
            w_bend = u
        # lean towards the right hand's aim (blended over the move), then look, then the arms
        lean_a = self._lean_for(base_pose, root, bend_from) if bend_from is not None else (0.0, 0.0, 1.0, 0.0)
        lean_b = self._lean_for(base_pose, root, bend_to) if bend_to is not None else (0.0, 0.0, 1.0, 0.0)
        mix = tuple(x + (y - x) * w_bend for x, y in zip(lean_a, lean_b))
        _apply_bend(pose, mix[0], mix[1], mix[2], mix[3])

        def look_of(nm):
            if nm in ("away", "set", "wait", "take") and self.trolley is not None:
                slot = self.trolley.slots.get(s.old if nm in ("away", "set") else s.new)
                if slot is not None:
                    return slot[:3, 3]
            if nm in DOOR_MOVES and self.door is not None:
                return self.door.at(door_v, self.door.handle)
            return s.spindle[:3, 3]

        look_at = look_of(name)
        if prev_name is not None:                  # the eyes go over to the next thing in the first part of a move
            w_look = smooth((t - a) / max(1e-6, min(0.4, 0.6 * (b - a))))
            look_at = look_of(prev_name) + (look_at - look_of(prev_name)) * w_look
        head = fig.fk(pose)["head"][0]
        fig.look(pose, to_fig(root, m4(np.eye(3), look_at))[:3, 3] - head, 0.8 * ease, chest_share=0.0)
        rest = _rest_arms(fig, pose)
        for side in ("r", "l"):
            if door_move:
                M, fingers = plan.get(side, (None, R.FINGERS_REST))
                if side == "r" and M is not None:
                    M = M
            else:
                A, B = t_from[side].M, t_to[side].M
                if A is None and B is None:
                    M = None
                else:
                    Ah = to_fig(root, A) if A is not None else rest[side]
                    Bh = to_fig(root, B) if B is not None else rest[side]
                    Mf = _blend4(Ah, Bh, u)
                    if t_to[side].via is not None:                # through the entry point half way
                        E = to_fig(root, m4(np.eye(3), t_to[side].via))[:3, 3]
                        Cp = 2.0 * E - 0.5 * (Ah[:3, 3] + Bh[:3, 3])
                        Mf[:3, 3] = (1 - u) ** 2 * Ah[:3, 3] + 2 * u * (1 - u) * Cp + u * u * Bh[:3, 3]
                    elif t_to[side].arc > 0:
                        Mf[:3, 3] += np.array((0.0, 0.0, t_to[side].arc * math.sin(math.pi * u)))
                    M = to_world(root, Mf)
                fingers = t_from[side].fingers + (t_to[side].fingers - t_from[side].fingers) * u
                pose.point[side] = t_from[side].point + (t_to[side].point - t_from[side].point) * u
            if M is not None:
                Mf = to_fig(root, M)
                miss = fig.arm_ik(pose, side, Mf[:3, 3], hand_R=Mf[:3, :3], elbow=ELBOW[side])
                if miss > 0.004:
                    self.misses.append((t, side, miss, name))
            pose.fingers[side] = fingers
        # the tools the right hand carries
        out_tools = {}
        fk = fig.fk(pose)
        hand = to_world(root, m4(fk["r_hand"][1], fk["r_hand"][0]))
        out_t, in_t = TC.person_events(s.t0, s.length, s.door)
        set_end = next(bb for _aa, bb, nm in moves if nm == "set")
        take_end = next(bb for _aa, bb, nm in moves if nm == "take")
        at = grip_hand(s.spindle, k, s.holder_r, self._right_way(root))
        if s.old in s.tools and out_t <= t <= set_end:
            out_tools[s.old] = hand @ PL.inv4(at) @ s.tools[s.old]
        if s.new in s.tools and take_end <= t <= in_t:
            out_tools[s.new] = hand @ PL.inv4(at) @ s.tools[s.new]
        return pose, out_tools, door_v

    def _door_aim(self, t, root, pose, moves, name, a, b, u):
        """The right hand at the door: to the handle, along with it while it can reach, then (or after the door's
        move) back to the side. Returns (hand world 4x4 or None = hanging, fingers)."""
        d = self.door
        span = {nm: (aa, bb) for aa, bb, nm in moves}
        opening = name in ("to_door", "open", "let_go")
        contact = d.handle if opening else self._close_contact(root, pose)
        key = "open" if opening else "close"
        ka, kb = span[key]

        def at(tt):
            return self._door_hand(self.door_value(tt), root, contact)

        # how long into the door's move the hand can follow (sampled once per change and move: the person stands)
        memo = self._door_memo.get((id(moves), key))
        if memo is None:
            last = ka
            for i in range(1, 21):
                tt = ka + (kb - ka) * i / 20
                if not self._reachable(root, pose, at(tt)):
                    break
                last = tt
            memo = (last, self._reachable(root, pose, at(ka)))
            self._door_memo[(id(moves), key)] = memo
        last, start_ok = memo
        if name in ("to_door", "to_close"):
            if not start_ok:
                return None, R.FINGERS_REST
            return _blend_world(root, self.fig, pose, None, at(ka), u), 0.35 + 0.45 * u
        if name in ("open", "close"):
            if not start_ok:
                return None, R.FINGERS_REST
            if t <= last:
                return at(t), 0.8
            w = smooth((t - last) / 0.3)                  # out of reach: it lets go and the door runs on
            return _blend_world(root, self.fig, pose, at(last), None, w), 0.8 - 0.45 * w
        # let_go / let_go2: from where the hand let go (if it still held the door at the end)
        if not start_ok:
            return None, R.FINGERS_REST
        if last < kb - 1e-6:                              # it let go during the door's move: that ends now
            w = smooth((t - last) / 0.3)
            if w >= 1.0:
                return None, R.FINGERS_REST
            return _blend_world(root, self.fig, pose, at(last), None, w), 0.8 - 0.45 * w
        return _blend_world(root, self.fig, pose, at(kb), None, u), 0.8 - 0.45 * u

    def _close_contact(self, root, pose):
        """A point of the door to pull it closed by: the handle, or – when the open door took it out of reach – a
        point of the door's face as far back along its travel as the hand reaches."""
        d = self.door
        if d.kind != "SLIDE":
            return d.handle
        M = self._door_hand(d.open, root, d.handle)
        if self._reachable(root, pose, M):
            return d.handle
        dirn = unit(d.direction)
        lo, hi = 0.0, abs(d.open - d.closed)
        sgn = 1.0 if d.open >= d.closed else -1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            c = d.handle - dirn * sgn * mid
            if self._reachable(root, pose, self._door_hand(d.open, root, c)):
                hi = mid
            else:
                lo = mid
        return d.handle - dirn * sgn * hi

    # -- every frame -------------------------------------------------------------------------------------------
    def sample(self, times: list) -> list:
        """[(root, pose, {T: carried tool world}, door value)] for every time."""
        if self.person is None:
            self.plan()
        rows = PL._sample_person(self.plan_people, self.person, list(times))
        out = []
        for t, (root, base) in zip(times, rows):
            pose, tools, dv = self.pose(t, root, base)
            out.append((root, pose, tools, dv))
        return out

    def change_times(self) -> list:
        """Per change: (pause start, pause length, the person's whole time at it from the first to the last move)."""
        return [(s.t0, s.length, m[-1][1] - m[0][0]) for s, m in zip(self.stations, self._moves)]


DOOR_MOVES = ("to_door", "open", "let_go", "to_close", "close", "let_go2")


def _apply_bend(pose: R.Pose, lean_deg: float, yaw: float, f: float, lft: float) -> None:
    """Bend spine and chest by ``lean_deg`` towards the horizontal way (forward share ``f``, left share ``lft``) and
    turn the chest by ``yaw`` (radians, + = to the left)."""
    if abs(lean_deg) < 1e-6 and abs(yaw) < 1e-6:
        return
    a = math.radians(lean_deg)
    for bone, share in (("spine", 0.45), ("chest", 0.55)):
        pose.local[bone] = pose.local[bone] @ R.rx(a * share * f) @ R.ry(a * share * lft)
    pose.local["chest"] = pose.local["chest"] @ R.rz(yaw)


def _blend_world(root, fig, pose, A, B, u):
    rest = _rest_arms(fig, pose)["r"]
    Ah = to_fig(root, A) if A is not None else rest
    Bh = to_fig(root, B) if B is not None else rest
    return to_world(root, _blend4(Ah, Bh, u))


def front_of(spindle_frame: np.ndarray, machine_front=(0.0, -1.0)) -> np.ndarray:
    """The way from the machine towards the operator (x, y): the machine's front (−y of the world, as the hand of
    task 0041), unless the holder's frame says otherwise."""
    f = np.asarray(machine_front, float)
    return f / max(1e-9, float(np.linalg.norm(f)))
