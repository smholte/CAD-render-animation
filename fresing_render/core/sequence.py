"""Assembly sequence (task 0100): which part goes when, which way and how far. No Blender.

A subassembly is taken apart part by part: each part flies out along its own straight line, one after the other with
an overlap (staggered). Putting it together is the exact reverse: the same lines and times played backwards, ending at
the parts' real places.

Everything here works in world metres, on each part's box corners at the moment the step starts (``Part.corners``).

Order
    OUTSIDE_IN  fasteners first, then the other parts; within each, the part whose near end lies furthest out along
                its own direction leaves first (for "Away from the centre": the part furthest from the centre).
                With a ``blocked(i, j)`` test (Blender casts rays) a part waits while a part still in place lies in
                its way: a ring in a cup leaves before the cup when they go up, after it when they go down
    TREE        the order of the model tree
    REVERSE     the model tree from the bottom up

Direction
    CENTRE      away from the subassembly's centre (a part right in the middle goes up)
    AXIS        along one axis of the subassembly (+ or -), every part the same way
    UP          straight up in the world

Distance: a set length, or "by size": far enough to clear the whole subassembly (its length along the axis, or its
radius from the centre). Along an axis or up, parts that would end up in each other's way are stacked: a part ends
beyond every part that leaves *after* it in the same direction and lies across it (``GAP`` apart). So the last part
goes the set distance and the first one furthest: no part ever flies through the place where an earlier one waits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

ORDERS = ("OUTSIDE_IN", "TREE", "REVERSE")
DIRECTIONS = ("CENTRE", "AXIS", "UP")
GAP = 0.05                  # stacked parts: this share of the distance between them (at least MIN_GAP)
MIN_GAP = 0.002             # m
SAME_WAY = 0.999            # two directions closer than this (cos) count as one for stacking
UP = np.array((0.0, 0.0, 1.0))


@dataclass
class Part:
    name: str
    corners: np.ndarray                 # 8 x 3, world metres, at the step's start
    fastener: bool = False
    index: int = 0                      # place in the model tree

    @property
    def centre(self) -> np.ndarray:
        c = np.asarray(self.corners, dtype=float)
        return (c.min(axis=0) + c.max(axis=0)) / 2.0


@dataclass
class Settings:
    direction: str = "AXIS"
    axis: tuple = (0.0, 0.0, 1.0)       # world direction of the chosen axis of the subassembly, + or - (AXIS)
    up: tuple = (0.0, 0.0, 1.0)         # world up (UP; also for a part right in the centre)
    distance: float = 0.2               # m
    by_size: bool = True
    order: str = "OUTSIDE_IN"
    part_time: float = 1.0              # s each part takes
    overlap: float = 0.5                # 0 … 0.9: share of a part's time the next one starts early
    put_together: bool = False


@dataclass
class Move:
    name: str
    rank: int                           # 0 = first to leave when taken apart
    t0: float                           # s from the step's start
    t1: float
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))   # world m: out place - real place
    direction: np.ndarray = field(default_factory=lambda: np.array(UP))

    @property
    def distance(self) -> float:
        return float(np.linalg.norm(self.offset))


def _unit(v, fallback=UP) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else np.asarray(fallback, dtype=float)


def interval(n: int, part_time: float, overlap: float) -> float:
    """Seconds between the starts of two parts."""
    return max(0.0, float(part_time)) * (1.0 - min(max(float(overlap), 0.0), 0.9))


def duration(n: int, part_time: float, overlap: float) -> float:
    """The whole step: the last part starts (n - 1) intervals after the first and takes part_time."""
    if n <= 0:
        return 0.0
    return max(0.0, float(part_time)) + (n - 1) * interval(n, part_time, overlap)


def centre_of(parts: list[Part]) -> np.ndarray:
    pts = np.concatenate([np.asarray(p.corners, dtype=float) for p in parts]) if parts else np.zeros((1, 3))
    return (pts.min(axis=0) + pts.max(axis=0)) / 2.0


def directions(parts: list[Part], st: Settings, centre: np.ndarray) -> list[np.ndarray]:
    up = _unit(st.up)
    out = []
    for p in parts:
        if st.direction == "UP":
            out.append(up)
        elif st.direction == "AXIS":
            out.append(_unit(st.axis))
        else:
            v = p.centre - centre
            out.append(_unit(v, up) if np.linalg.norm(v) > 1e-6 else up)
    return out


def _span(corners, u) -> tuple[float, float]:
    d = np.asarray(corners, dtype=float) @ u
    return float(d.min()), float(d.max())


def order(parts: list[Part], st: Settings, centre: np.ndarray, dirs: list[np.ndarray], blocked=None) -> list[int]:
    """Indices of ``parts`` in the order they leave when taken apart. ``blocked(i, j)``: True when part i, leaving
    along its direction, runs into part j standing in its place (asked only for parts that lie across i's way)."""
    by_tree = sorted(range(len(parts)), key=lambda i: parts[i].index)
    if st.order == "TREE":
        return by_tree
    if st.order == "REVERSE":
        return by_tree[::-1]

    def out_key(i):
        if st.direction == "CENTRE":
            return float(np.linalg.norm(parts[i].centre - centre))
        lo, _hi = _span(np.asarray(parts[i].corners) - centre, dirs[i])
        return lo                                          # the part's near end, measured along its own way out
    key = {i: out_key(i) for i in by_tree}
    rank = {i: n for n, i in enumerate(by_tree)}
    fast = sorted((i for i in by_tree if parts[i].fastener), key=lambda i: (-key[i], rank[i]))
    rest = sorted((i for i in by_tree if not parts[i].fastener), key=lambda i: (-key[i], rank[i]))
    wish = fast + rest
    if blocked is None or len(wish) < 2:
        return wish
    ahead = {i: [j for j in wish if j != i and _in_way(parts[i].corners, parts[j].corners, dirs[i])] for i in wish}
    seen: dict = {}

    def stopped(i, j):
        if (i, j) not in seen:
            seen[(i, j)] = bool(blocked(i, j))
        return seen[(i, j)]
    left = list(wish)
    out = []
    while left:
        here = set(left)
        pick = next((i for i in left if not any(j in here and stopped(i, j) for j in ahead[i])), left[0])
        out.append(pick)
        left.remove(pick)
    return out


def _in_way(a, b, u) -> bool:
    """Could box ``b`` stand in the way of box ``a`` moving along ``u``? (across it, and reaching beyond a's near
    end)"""
    lo_a, _hi_a = _span(a, u)
    _lo_b, hi_b = _span(b, u)
    return hi_b > lo_a + 1e-6 and _across(a, b, u)


def _across(a, b, u) -> bool:
    """Do the boxes of corners ``a`` and ``b`` overlap seen along ``u`` (side by side across it)?"""
    e1 = _unit(np.cross(u, (1.0, 0.0, 0.0)) if abs(u[0]) < 0.9 else np.cross(u, (0.0, 1.0, 0.0)))
    e2 = np.cross(u, e1)
    for e in (e1, e2):
        lo_a, hi_a = _span(a, e)
        lo_b, hi_b = _span(b, e)
        if hi_a <= lo_b + 1e-6 or hi_b <= lo_a + 1e-6:
            return False
    return True


def base_distance(parts: list[Part], st: Settings, centre: np.ndarray) -> float:
    if not st.by_size:
        return max(0.0, float(st.distance))
    pts = np.concatenate([np.asarray(p.corners, dtype=float) for p in parts]) if parts else np.zeros((1, 3))
    if st.direction == "CENTRE":
        return float(np.max(np.linalg.norm(pts - centre, axis=1)))
    u = _unit(st.up) if st.direction == "UP" else _unit(st.axis)
    lo, hi = _span(pts, u)
    return hi - lo


def plan(parts: list[Part], st: Settings, blocked=None) -> list[Move]:
    """One Move per part, in the order they leave (take apart) – or come in (put together). ``blocked``: see
    ``order``; it gets the indices into ``parts`` and the directions as ``plan.dirs`` (set before it is asked)."""
    if not parts:
        return []
    centre = centre_of(parts)
    dirs = directions(parts, st, centre)
    if blocked is not None:
        blocked.dirs = dirs
    seq = order(parts, st, centre, dirs, blocked)
    base = base_distance(parts, st, centre)
    gap = max(MIN_GAP, GAP * base)
    step = interval(len(parts), st.part_time, st.overlap)
    total = duration(len(parts), st.part_time, st.overlap)
    travel: dict[int, float] = {}
    for rank in range(len(seq) - 1, -1, -1):                # the last to leave first: it goes the base distance
        i = seq[rank]
        u = dirs[i]
        t = base
        if st.direction != "CENTRE":                        # stack: end beyond the parts that leave after it
            lo_i, _ = _span(parts[i].corners, u)
            for k in seq[rank + 1:]:
                if float(np.dot(dirs[k], u)) < SAME_WAY or not _across(parts[i].corners, parts[k].corners, u):
                    continue
                _lo_k, hi_k = _span(parts[k].corners, u)
                t = max(t, hi_k + travel[k] + gap - lo_i)
        travel[i] = t
    moves = []
    for rank, i in enumerate(seq):
        u = dirs[i]
        t = travel[i]
        t0 = rank * step
        t1 = t0 + max(0.0, float(st.part_time))
        if st.put_together:
            t0, t1 = total - t1, total - t0
        moves.append(Move(parts[i].name, rank, t0, t1, u * t, u))
    if st.put_together:
        moves.sort(key=lambda m: (m.t0, -m.rank))
    return moves


def fasteners_first(moves: list[Move], parts: list[Part]) -> bool:
    """True when every fastener leaves before every other part (take apart)."""
    fast = {p.name for p in parts if p.fastener}
    ranks = sorted(moves, key=lambda m: m.rank)
    seen_other = False
    for m in ranks:
        if m.name in fast and seen_other:
            return False
        seen_other = seen_other or m.name not in fast
    return True
