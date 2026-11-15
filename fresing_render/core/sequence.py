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

Distance: a set length, or "by size": far enough to clear the whole subassembly (its length along the part's way,
or its radius from the centre). Parts that would end up in each other's way are stacked: a part ends beyond every part
that leaves *after* it going nearly the same way (``NEAR``) and whose way lies across its own (``GAP`` apart). So the
last part goes the set distance and the first one furthest: no part ever flies through the place where an earlier one
waits. Task 0129: "Away from the centre" stacks too (parts nested in each other went the same way, the same distance).

Parts outside the subassembly (task 0129, ``obstacle``): a part whose way runs into one goes another way – the
subassembly's other axes, most like the wanted way first, the opposite last – that is clear of them and of the parts
still in place when it leaves; the order is then worked out again (at most ``ROUNDS`` times).

Riders (task 0129, ``carried``): a part a joint carries on another part of the subassembly leaves before its carrier
(any order); Blender keeps it where it flew while the carrier flies out under it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import math

import numpy as np

ORDERS = ("OUTSIDE_IN", "TREE", "REVERSE")
DIRECTIONS = ("CENTRE", "AXIS", "UP")
GAP = 0.05                  # stacked parts: this share of the distance between them (at least MIN_GAP)
MIN_GAP = 0.002             # m
SAME_WAY = 0.999            # two directions closer than this (cos) count as one
NEAR = math.cos(math.radians(25.0))   # parts going closer to one way than this (cos) are stacked (task 0129)
ROUNDS = 4                  # other ways tried round a part outside the subassembly: plans worked out at most
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
    frame: tuple | None = None          # the subassembly's X, Y, Z axes (world): the other ways a blocked part tries


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


def order(parts: list[Part], st: Settings, centre: np.ndarray, dirs: list[np.ndarray], blocked=None,
          carried: dict | None = None) -> list[int]:
    """Indices of ``parts`` in the order they leave when taken apart. ``blocked(i, j)``: True when part i, leaving
    along its direction, runs into part j standing in its place (asked only for parts that lie across i's way).
    ``carried[i]``: the parts that ride on part i; i never leaves before them (task 0129)."""
    by_tree = sorted(range(len(parts)), key=lambda i: parts[i].index)
    if st.order == "TREE":
        return _carriers_last(by_tree, carried)
    if st.order == "REVERSE":
        return _carriers_last(by_tree[::-1], carried)

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
        return _carriers_last(wish, carried)
    boxes = _corner_array(parts)
    pos = np.empty(len(parts), dtype=int)
    pos[wish] = np.arange(len(wish))
    ahead = {}
    for i in wish:
        hit = np.flatnonzero(_in_way_all(boxes, i, dirs[i]))
        ahead[i] = [int(j) for j in hit[np.argsort(pos[hit], kind="stable")] if j != i]
    seen: dict = {}

    def stopped(i, j):
        if (i, j) not in seen:
            seen[(i, j)] = bool(blocked(i, j))
        return seen[(i, j)]
    carried = carried or {}
    left = list(wish)
    out = []
    while left:
        here = set(left)
        free = [i for i in left if not any(r in here for r in carried.get(i, ()))]
        pick = next((i for i in free if not any(j in here and stopped(i, j) for j in ahead[i])), free[0])
        out.append(pick)
        left.remove(pick)
    return out


def _carriers_last(seq: list[int], carried: dict | None) -> list[int]:
    """``seq`` with every carrier moved behind the parts it carries (otherwise the same order)."""
    if not carried:
        return seq
    left = list(seq)
    out = []
    while left:
        here = set(left)
        pick = next(i for i in left if not any(r in here for r in carried.get(i, ())))
        out.append(pick)
        left.remove(pick)
    return out


def _in_way(a, b, u) -> bool:
    """Could box ``b`` stand in the way of box ``a`` moving along ``u``? (across it, and reaching beyond a's near
    end)"""
    lo_a, _hi_a = _span(a, u)
    _lo_b, hi_b = _span(b, u)
    return hi_b > lo_a + 1e-6 and _across(a, b, u)


def _corner_array(parts: list[Part]) -> np.ndarray:
    """(n, 8, 3): every part's box corners."""
    return np.stack([np.asarray(p.corners, dtype=float).reshape(-1, 3) for p in parts])


def _frame(u) -> tuple[np.ndarray, np.ndarray]:
    """Two directions square to ``u`` (and to each other): "across" ``u``."""
    e1 = _unit(np.cross(u, (1.0, 0.0, 0.0)) if abs(u[0]) < 0.9 else np.cross(u, (0.0, 1.0, 0.0)))
    return e1, np.cross(u, e1)


def _spans_all(boxes: np.ndarray, u) -> tuple[np.ndarray, np.ndarray]:
    d = boxes @ np.asarray(u, dtype=float)
    return d.min(axis=1), d.max(axis=1)


def _across_all(boxes: np.ndarray, i: int, u) -> np.ndarray:
    """``_across`` of part i against every part at once (n booleans; part i itself included)."""
    ok = np.ones(len(boxes), dtype=bool)
    for e in _frame(u):
        lo, hi = _spans_all(boxes, e)
        ok &= ~((hi[i] <= lo + 1e-6) | (hi <= lo[i] + 1e-6))
    return ok


def _in_way_all(boxes: np.ndarray, i: int, u) -> np.ndarray:
    """``_in_way`` of part i against every part at once (task 0121: the pairs one by one cost seconds for 260
    parts)."""
    lo, hi = _spans_all(boxes, u)
    return (hi > lo[i] + 1e-6) & _across_all(boxes, i, u)


def _across(a, b, u) -> bool:
    """Do the boxes of corners ``a`` and ``b`` overlap seen along ``u`` (side by side across it)?"""
    for e in _frame(u):
        lo_a, hi_a = _span(a, e)
        lo_b, hi_b = _span(b, e)
        if hi_a <= lo_b + 1e-6 or hi_b <= lo_a + 1e-6:
            return False
    return True


def base_distance(parts: list[Part], st: Settings, centre: np.ndarray, u=None) -> float:
    """How far a part flies: the set distance, or by size the subassembly's length along ``u`` (default: the step's
    way) or its radius from the centre."""
    if not st.by_size:
        return max(0.0, float(st.distance))
    pts = np.concatenate([np.asarray(p.corners, dtype=float) for p in parts]) if parts else np.zeros((1, 3))
    if st.direction == "CENTRE":
        return float(np.max(np.linalg.norm(pts - centre, axis=1)))
    if u is None:
        u = _unit(st.up) if st.direction == "UP" else _unit(st.axis)
    lo, hi = _span(pts, u)
    return hi - lo


def other_ways(want, st: Settings) -> list[np.ndarray]:
    """The ways a part may take instead of ``want``: the subassembly's ±X, ±Y, ±Z and world up, the most like
    ``want`` first (the opposite last); ``want`` itself is not in the list."""
    want = _unit(want)
    axes = [np.asarray(a, dtype=float) for a in (st.frame or ((1, 0, 0), (0, 1, 0), (0, 0, 1)))]
    cands = []
    for a in axes + [np.asarray(st.up, dtype=float)]:
        for sgn in (1.0, -1.0):
            v = _unit(sgn * a)
            if float(v @ want) >= SAME_WAY or any(float(v @ c) >= SAME_WAY for c in cands):
                continue
            cands.append(v)
    order_ = sorted(range(len(cands)), key=lambda k: (-round(float(cands[k] @ want), 6), k))
    return [cands[k] for k in order_]


def _across_rows(box: np.ndarray, others: np.ndarray, u) -> np.ndarray:
    """For each row of ``others`` (m, k, 3): do its points and ``box`` (8, 3) overlap seen along ``u``?"""
    ok = np.ones(len(others), dtype=bool)
    for e in _frame(u):
        lo_a, hi_a = _span(box, e)
        d = others @ e
        ok &= ~((hi_a <= d.min(axis=1) + 1e-6) | (d.max(axis=1) <= lo_a + 1e-6))
    return ok


def _travels(boxes: np.ndarray, seq: list[int], dirs: list[np.ndarray], bases: np.ndarray, gap: float) -> np.ndarray:
    """How far each part flies: its base distance, or further to end beyond every part that leaves after it going
    nearly the same way (``NEAR``) and whose way – start box to end box – lies across its own way (``gap`` beyond the
    furthest such end). The last to leave is worked out first."""
    n = len(boxes)
    dir_arr = np.asarray(dirs, dtype=float)
    went = np.zeros(n)
    later = np.zeros(n, dtype=bool)
    for rank in range(len(seq) - 1, -1, -1):
        i = seq[rank]
        u = dir_arr[i]
        t = float(bases[i])
        if later.any():
            m = later & (dir_arr @ u >= NEAR)
            if m.any():
                idx = np.flatnonzero(m)
                ends = boxes[idx] + (dir_arr[idx] * went[idx, None])[:, None, :]
                way = np.concatenate([boxes[idx], ends], axis=1)
                hit = _across_rows(boxes[i], way, u)
                if hit.any():
                    hi_end = (ends[hit] @ u).max(axis=1)
                    lo_i = float((boxes[i] @ u).min())
                    t = max(t, float(hi_end.max()) + gap - lo_i)
        went[i] = t
        later[i] = True
    return went


def plan(parts: list[Part], st: Settings, blocked=None, obstacle=None, carried: dict | None = None) -> list[Move]:
    """One Move per part, in the order they leave (take apart) – or come in (put together).

    ``blocked``: see ``order``; it gets the indices into ``parts`` and the directions as ``blocked.dirs`` (set before
    it is asked, changed in place when a part takes another way). Its optional ``hit(i, j, u, dist)`` tells whether
    part i, flying ``dist`` along ``u``, runs into part j in its place (to choose another way that is clear).
    ``obstacle(i, u, dist)``: True when part i, flying ``dist`` m along ``u``, runs into a part outside the
    subassembly: it then takes another way (``other_ways``). ``carried[i]``: the parts that ride on part i."""
    if not parts:
        return []
    centre = centre_of(parts)
    dirs = directions(parts, st, centre)
    if blocked is not None:
        blocked.dirs = dirs
    boxes = _corner_array(parts)
    base0 = base_distance(parts, st, centre)
    gap = max(MIN_GAP, GAP * base0)
    hit = getattr(blocked, "hit", None) if blocked is not None else None
    want = [d.copy() for d in dirs]
    failed: dict[int, list] = {}
    stuck: set = set()

    def base_for(i):
        if st.direction == "CENTRE" or not st.by_size or float(dirs[i] @ want[i]) >= SAME_WAY:
            return base0
        return base_distance(parts, st, centre, dirs[i])

    def way_blocked(i, u, dist, later):
        if obstacle is not None and obstacle(i, u, dist):
            return True
        if hit is None or not len(later):
            return False
        near = np.flatnonzero(_in_way_all(boxes, i, u))
        return any(hit(i, int(j), u, dist) for j in near if int(j) in later)

    for _round in range(ROUNDS):
        seq = order(parts, st, centre, dirs, blocked, carried)
        bases = np.array([base_for(i) for i in range(len(parts))])
        travel = _travels(boxes, seq, dirs, bases, gap)
        if obstacle is None:
            break
        changed = False
        for r, i in enumerate(seq):
            if i in stuck or not obstacle(i, dirs[i], float(travel[i])):
                continue
            later = set(seq[r + 1:])
            failed.setdefault(i, []).append(dirs[i])
            pick = fallback = None
            for u in [want[i]] + other_ways(want[i], st):
                if any(float(u @ f) >= SAME_WAY for f in failed[i]):
                    continue
                d = base0 if not st.by_size or st.direction == "CENTRE" else base_distance(parts, st, centre, u)
                if obstacle(i, u, d):
                    continue
                if fallback is None:
                    fallback = u
                if not way_blocked(i, u, d, later):
                    pick = u
                    break
            pick = pick if pick is not None else fallback
            if pick is None:                                # every way runs into something: keep the wanted one
                pick = want[i]
                stuck.add(i)
            if float(pick @ dirs[i]) < SAME_WAY:
                dirs[i] = np.asarray(pick, dtype=float)
                changed = True
        if not changed:
            break

    step = interval(len(parts), st.part_time, st.overlap)
    total = duration(len(parts), st.part_time, st.overlap)
    moves = []
    for rank, i in enumerate(seq):
        u = dirs[i]
        t = float(travel[i])
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
