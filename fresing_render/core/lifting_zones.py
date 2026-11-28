"""Clearances, reach envelope, exclusion zone and ground footprint of a lift (task 0349, Lifting lane L6b) – plain
Python with NumPy, no Blender.

* **Clearance** (``Clearance``): the smallest distance between what moves in the lift – the crane's parts that turn
  with the slew (boom, superstructure, counterweight, hook block), the load and its rigging – and every obstacle (the
  project's other parts and props), at any joint values. Each moving part is points on its surface (5 cm apart) in its
  joint's frame at zero, the obstacles one set of triangles (``Triangles``; the app: Blender's BVH tree): the distance
  is from those points to the nearest triangle (the true gap, or up to ~3 cm more), looked for only where a part's
  box comes near an obstacle's box. What the load or its rigging touch where the lift starts and ends (what it stands
  on) does not count for them; what they are nearer to than the clearance needed there counts again once they have
  moved that far. The row joins ``lifting_path.Checks.at`` (id
  ``CLR``): use = the clearance needed / the distance, colours like C1 (amber from the crane limit, red under the
  clearance needed).
* **Reach envelope** (``reach``, ``range_curve``): the radius out to which the chart that applies carries the gross
  load (100 %) and out to the amber limit – drawn as rings round the slew axis – and the range diagram: the hook's
  highest point over the radius as the boom luffs, with the chart's rows.
* **Exclusion zone** (``exclusion_zone``): the convex outline on the ground round the crane's tail swing (OSHA 29 CFR
  1926.1424(a): mark the swing radius of the rotating superstructure), its outriggers or tracks and the load's path,
  widened by a margin.
* **Ground footprint** (``footprint``): every outrigger pad / mat with its reaction and pressure, every crawler track
  in pieces with the pressure under each, coloured by the ground limit (C5 / C6), at one moment.
* **Plan sheet** (``plan_svg``, ``range_svg``, ``sheet_html``): the plan view, the range diagram and the checks table
  as one page to print.

Units: metres and kg (Pa for pressures, N for reactions); the crane's own frame in mm only inside ``Supports``.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

import numpy as np

from . import clash
from . import lifting
from . import lifting_path as P
from . import lifting_reach as LR

REQUIRED_DEFAULT = 3.05            # m – OSHA 29 CFR 1926.1408 Table A: 10 ft to power lines up to 50 kV
REQUIRED_SOURCE = "OSHA 29 CFR 1926.1408, Table A: 10 ft (3.05 m) from power lines up to 50 kV"
MARGIN_DEFAULT = 1.0               # m round the exclusion zone (the user's choice, no guideline)
NEED = 1.1                         # distances are searched out to this share past the amber border
SPACING = 0.05                     # m between a moving part's surface points
MOST_POINTS = 20000                # about this many surface points of one part at most (more: wider apart)
FACING = 0.999                     # a point straight below an obstacle's face, behind it: inside the obstacle
GROUP = 0.15                       # m: a moving part's points are looked at in cubes this big first …
TOP_GROUP = 1.0                    # … and those cubes in cubes this big before
FAR = 1e9
TOUCH = 0.05                       # m: the load "stands on" what is this close at the lift's start or end


# ---------------------------------------------------------------------------------------------------------------------
# clearance

def _moved_box(M, lo, hi):
    c = clash.transform(M, clash.corners(lo[None], hi[None])[0])
    return c.min(axis=0), c.max(axis=0)


@dataclass
class Body:
    """A part that moves in the lift: points on its surface (``SPACING`` apart, its corners too) in its joint's frame
    at zero (m), sorted into groups of a ``GROUP`` m cube – each group a point of its own (``reps``), the furthest of
    its points ``radius`` from it, its points ``points[start[g]:start[g + 1]]`` – the joint (rig name; None: it
    stands) and its kind: "crane", "load" or "rigging"."""

    name: str
    kind: str
    joint: str | None
    points: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    reps: np.ndarray = None
    radius: np.ndarray = None
    start: np.ndarray = None
    spacing: float = 0.05              # m between its points (wider on a very large part: ``sample``)
    top: tuple = None                  # the groups grouped again in ``TOP_GROUP`` cubes: (reps, radius, members, start)

    def __post_init__(self):
        if self.reps is None:
            self.points, self.reps, self.radius, self.start = grouped(self.points)
        if self.top is None:
            self.top = regrouped(self.reps, self.radius)


def regrouped(reps, radius, size: float = None) -> tuple:
    """Groups of groups: (one group point of each, how far its groups' points reach from it, the groups' numbers
    sorted by bigger group, where each bigger group starts)."""
    size = TOP_GROUP if size is None else size
    r = np.asarray(reps, float)
    if not len(r):
        return np.zeros((0, 3)), np.zeros(0), np.zeros(0, np.int64), np.zeros(1, np.int64)
    key = np.floor(r / size).astype(np.int64)
    order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
    k = key[order]
    new = np.ones(len(order), bool)
    new[1:] = np.any(k[1:] != k[:-1], axis=1)
    start = np.r_[np.flatnonzero(new), len(order)]
    top_reps, top_rad = [], []
    for a, b in zip(start[:-1], start[1:]):
        mem = order[a:b]
        mid = r[mem].mean(axis=0)
        rep = r[mem[int(np.argmin(np.linalg.norm(r[mem] - mid, axis=1)))]]
        top_reps.append(rep)
        top_rad.append(float(np.max(np.linalg.norm(r[mem] - rep, axis=1) + np.asarray(radius)[mem])))
    return np.array(top_reps), np.array(top_rad), order, start


def grouped(points, size: float = None):
    """(points sorted by group, one of each group's points (the nearest to its middle), how far its furthest point
    lies from it, where each group starts): groups = cubes of ``size`` m."""
    size = GROUP if size is None else size
    p = np.asarray(points, float)
    if not len(p):
        return p, np.zeros((0, 3)), np.zeros(0), np.zeros(1, np.int64)
    key = np.floor(p / size).astype(np.int64)
    order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
    p, key = p[order], key[order]
    new = np.ones(len(p), bool)
    new[1:] = np.any(key[1:] != key[:-1], axis=1)
    start = np.r_[np.flatnonzero(new), len(p)]
    g = np.repeat(np.arange(len(start) - 1), np.diff(start))
    n = np.diff(start).astype(float)
    mid = np.zeros((len(n), 3))
    np.add.at(mid, g, p)
    mid /= n[:, None]
    d = np.linalg.norm(p - mid[g], axis=1)
    best = np.full(len(n), np.inf)
    np.minimum.at(best, g, d)
    pick = np.flatnonzero(d <= best[g] + 1e-12)
    first = np.full(len(n), -1, np.int64)
    for i in pick[::-1]:
        first[g[i]] = i
    reps = p[first]
    r = np.linalg.norm(p - reps[g], axis=1)
    radius = np.zeros(len(n))
    np.maximum.at(radius, g, r)
    return p, reps, radius, start


def _subdivide(tri: np.ndarray, longest: float, rounds: int = 12) -> np.ndarray:
    """Triangles (N, 3, 3) cut in four (at their edges' middles) until no edge is longer than ``longest``."""
    for _k in range(rounds):
        e = np.linalg.norm(tri - np.roll(tri, -1, axis=1), axis=2).max(axis=1)
        big = e > longest
        if not big.any():
            break
        t = tri[big]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        four = np.concatenate([np.stack(x, axis=1) for x in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
        tri = np.concatenate([tri[~big], four])
    return tri


def sample(verts, tris, spacing: float = None, most: int = None) -> tuple:
    """(points on a mesh's surface, the spacing used): its corners and points spread over its faces ``spacing`` apart
    – every face, a long or a wide one, cut first so that its points really lie that close (task 0349's tester: a
    30 m boom's faces got points 0.47 m apart). A part so large that it would need more than ``most`` points gets them
    wider apart (``spacing`` grows with the square root of its area). Faces with a corner that is not a number are
    left out."""
    spacing = SPACING if spacing is None else spacing
    most = MOST_POINTS if most is None else most
    v = np.asarray(verts, float)
    t = np.asarray(tris, np.int64).reshape(-1, 3)
    if not len(v):
        return np.zeros((0, 3)), spacing
    if not len(t):                                   # points only: the corners themselves
        return v[np.all(np.isfinite(v), axis=1)], spacing
    tri = v[t]
    tri = tri[np.all(np.isfinite(tri), axis=(1, 2))]
    if not len(tri):
        return np.zeros((0, 3)), spacing
    area = 0.5 * float(np.sum(np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)))
    s = max(spacing, math.sqrt(2.5 * area / max(most, 1)))
    tri = _subdivide(tri, 16.0 * s)
    pts, _w = clash.triangle_points(tri, s, max_split=16)
    return pts, s


def surface_points(verts, tris, spacing: float = None, most: int = None) -> np.ndarray:
    """The points of ``sample``."""
    return sample(verts, tris, spacing, most)[0]


def body(name: str, kind: str, joint, verts, tris) -> Body:
    pts, sp = sample(verts, tris)
    if not len(pts):
        raise ValueError("a part without triangles")
    return Body(name, kind, joint, pts, pts.min(axis=0), pts.max(axis=0), spacing=sp)


class Triangles:
    """The obstacles as triangles (world, m) with their names: ``nearest(points, need)`` -> (distance, obstacle index;
    -1 when none is within ``need``), worked out exactly (closest point on every triangle near the point) in plain
    NumPy – for tests and small sets. The app hands its own (Blender's BVH tree) with the same methods."""

    def __init__(self, parts):
        """``parts`` [(name, verts (N, 3) world m, tris (T, 3))]."""
        self.parts = list(parts)
        self.names, tri, owner = [], [], []
        for k, (name, v, t) in enumerate(parts):
            v, t = np.asarray(v, float), np.asarray(t, np.int64).reshape(-1, 3)
            self.names.append(name)
            tri.append(v[t])
            owner.append(np.full(len(t), k))
        self.tri = np.concatenate(tri) if tri else np.zeros((0, 3, 3))
        self.owner = np.concatenate(owner) if owner else np.zeros(0, np.int64)
        self.lo = np.array([x.min(axis=(0, 1)) for x in tri]) if tri else np.zeros((0, 3))
        self.hi = np.array([x.max(axis=(0, 1)) for x in tri]) if tri else np.zeros((0, 3))
        self.tlo, self.thi = self.tri.min(axis=1), self.tri.max(axis=1)

    def nearest(self, points, need: float):
        pts = np.asarray(points, float)
        d = np.full(len(pts), np.inf)
        who = np.full(len(pts), -1, np.int64)
        for i, p in enumerate(pts):
            g = np.maximum(0.0, np.maximum(self.tlo - p, p - self.thi))
            near = np.flatnonzero(np.einsum("ij,ij->i", g, g) <= need * need)
            if not len(near):
                continue
            q = clash.closest_on_triangles(p, self.tri[near])
            dd = np.linalg.norm(q - p, axis=1)
            k = int(np.argmin(dd))
            if dd[k] <= need:
                t = self.tri[near[k]]
                n = np.cross(t[1] - t[0], t[2] - t[0])
                d[i], who[i] = (0.0 if behind(p - q[k], n) else dd[k]), self.owner[near[k]]
        return d, who

    def without(self, drop):
        """The same obstacles less those with the indices ``drop``: (``Triangles``, their indices here)."""
        keep = [k for k in range(len(self.parts)) if k not in drop]
        return Triangles([self.parts[k] for k in keep]), np.array(keep, np.int64)


def behind(gap, normal) -> bool:
    """A point ``gap`` from the nearest point of a face (``normal``: its outward side) lies inside the obstacle: straight
    below the face, behind it (the clash check's rule – beside a sharp edge the nearest face can point away)."""
    g, n = float(np.linalg.norm(gap)), float(np.linalg.norm(normal))
    return g > 1e-9 and n > 1e-12 and float(np.dot(gap, normal)) < -FACING * g * n


@dataclass
class Nearest:
    distance: float                    # m (FAR: nothing within the search)
    body: str = ""
    obstacle: str = ""
    kind: str = ""
    points: tuple = ()                 # (the body's point, world) – where the gap is
    spacing: float = 0.05              # m between that body's points


class Clearance:
    """The lift's clearance at any joint values. ``motion(joint, values)`` -> 4 x 4: the joint's frame now relative to
    its frame at zero, in the world (m). ``obstacles``: ``Triangles`` or the app's own with its methods and its
    ``names``, ``lo``, ``hi``. A distance is the nearest obstacle triangle to the body's surface points – they lie
    ``SPACING`` apart, so it is the true gap or up to about half that more."""

    def __init__(self, bodies, obstacles, motion, required: float = REQUIRED_DEFAULT,
                 limits: lifting.Limits = lifting.DEFAULT_LIMITS):
        self.bodies = list(bodies)
        self.obstacles = obstacles
        self.motion = motion
        self.required = max(float(required), 1e-3)
        self.limits = limits
        self.ignore: dict = {}             # body index -> {obstacle indices} (what the load stands on: always)
        self.ends: dict = {}               # body index -> [(where it was, {obstacle indices})] (near the pick, set-down)
        self._subs: dict = {}              # frozenset of left-out obstacle indices -> (obstacles without them, indices)
        self.need = NEED * self.required / max(limits.crane, 1e-3)

    def _mats(self, values) -> dict:
        out = {}
        for b in self.bodies:
            if b.joint not in out:
                out[b.joint] = np.eye(4) if b.joint is None else np.asarray(self.motion(b.joint, values), float)
        return out

    @staticmethod
    def _boxes_near(ob, pts, reach, near):
        """Which of ``pts`` come within ``reach`` (a number or one per point) of an obstacle box in ``near``."""
        olo, ohi = ob.lo[near], ob.hi[near]
        r2 = np.asarray(reach, float) ** 2
        keep = np.zeros(len(pts), bool)
        for k in range(len(olo)):
            gp = np.maximum(0.0, np.maximum(olo[k] - pts, pts - ohi[k]))
            keep |= np.einsum("ij,ij->i", gp, gp) <= r2
        return keep

    def _without(self, skip):
        """(the obstacles less ``skip`` – a nearer left-out one must not hide the rest –, their original indices)."""
        if not skip:
            return self.obstacles, None
        key = frozenset(skip)
        got = self._subs.get(key)
        if got is None:
            got = self.obstacles.without(key)
            if len(self._subs) > 64:
                self._subs.clear()
            self._subs[key] = got
        return got

    def distances(self, values, need: float | None = None) -> list:
        """[(distance m, body, obstacle index, the body's point)] of the bodies that can be the nearest one within
        ``need`` (default: the amber border, a little wider) – each with its own nearest; ``nearest`` takes the
        smallest. First every body's group points (each a surface point); then only the groups that can hold a nearer
        point – a group's points lie within its radius – point by point. The answer is the same as looking at every
        point."""
        need = self.need if need is None else need
        if self.obstacles is None or not len(self.obstacles.names):
            return []
        mats = self._mats(values)
        import heapq
        heap: list = []                                  # (lower bound, level, body number, group)
        bodies: list = []
        top = need                                       # the nearest found so far (group points are surface points)
        for i, b in enumerate(self.bodies):
            M = mats[b.joint]
            ob, back = self._without(self._skip(i, M))
            if not len(ob.names):
                continue
            blo, bhi = _moved_box(M, b.lo, b.hi)
            g = np.maximum(0.0, np.maximum(ob.lo - bhi, blo - ob.hi))
            near = np.einsum("ij,ij->i", g, g) <= need * need
            if not near.any():
                continue
            treps, trad, _members, _st = b.top
            tw = treps @ M[:3, :3].T + M[:3, 3]
            keep = np.flatnonzero(self._boxes_near(ob, tw, need + trad, near))
            if not len(keep):
                continue
            d, _who = ob.nearest(tw[keep], need + float(trad[keep].max()))
            n = len(bodies)
            bodies.append((b, M, ob, back))
            if len(d) and np.isfinite(d).any():
                top = min(top, float(np.nanmin(np.where(np.isfinite(d), d, np.inf))))
            for k, lb in zip(keep, d - trad[keep]):
                if lb <= top:
                    heapq.heappush(heap, (float(lb), 1, n, int(k)))
        found: dict = {}                                 # body number -> (distance, obstacle index, point)
        while heap:
            lb, level, n, k = heapq.heappop(heap)
            if lb > top:
                break
            b, M, ob, back = bodies[n]
            if level == 1:                               # a bigger group: its groups
                _tr, _trad, members, st = b.top
                grp = members[st[k]:st[k + 1]]
                gw = b.reps[grp] @ M[:3, :3].T + M[:3, 3]
                d, _w = ob.nearest(gw, top + float(b.radius[grp].max()) + 1e-3)
                if np.isfinite(d).any():
                    top = min(top, float(np.min(d)))
                for gk, g_lb in zip(grp, d - b.radius[grp]):
                    if g_lb <= top:
                        heapq.heappush(heap, (float(g_lb), 0, n, int(gk)))
                continue
            pts = b.points[b.start[k]:b.start[k + 1]] @ M[:3, :3].T + M[:3, 3]
            dd, ww = ob.nearest(pts, top + 1e-3)
            i = int(np.argmin(dd))
            if math.isfinite(dd[i]) and dd[i] <= need:
                w = int(ww[i]) if back is None else int(back[ww[i]])
                if n not in found or dd[i] < found[n][0]:
                    found[n] = (float(dd[i]), w, pts[i])
                top = min(top, float(dd[i]))
        return [(dist, bodies[n][0], w, p) for n, (dist, w, p) in found.items()]

    def nearest(self, values) -> Nearest:
        got = self.distances(values)
        if not got:
            return Nearest(FAR)
        d, b, k, p = min(got, key=lambda x: x[0])
        return Nearest(d, b.name, self.obstacles.names[k], b.kind, (tuple(map(float, p)),), b.spacing)

    def _skip(self, i: int, M) -> set:
        """The obstacles (indices) that do not count for body ``i`` where ``M`` puts it: what it stands on, and what it
        was nearer than the clearance needed at the pick or the set-down while it is still within that distance of
        where it was there."""
        out = set(self.ignore.get(i, ()))
        for where, ks in self.ends.get(i, ()):
            if float(np.linalg.norm(M[:3, 3] - where)) < self.required:
                out |= ks
        return out

    def leave_out_touching(self, moments, kinds=("load", "rigging")) -> None:
        """The ends of the lift (``moments``: joint values at the pick and the set-down): what the load and its
        rigging touch there does not count for them; what they are nearer to than the clearance needed (the wall
        beside the pick) counts again once they have moved that far from there. By obstacle, not by name (names
        repeat: two pallets)."""
        ob = self.obstacles
        if ob is None or not len(ob.names):
            return
        for values in moments:
            mats = self._mats(values)
            for i, b in enumerate(self.bodies):
                if b.kind not in kinds:
                    continue
                M = mats[b.joint]
                reps = b.reps @ M[:3, :3].T + M[:3, 3]           # only the groups that can come that near
                dr, _w = ob.nearest(reps, self.required + float(b.radius.max(initial=0.0)))
                grp = np.flatnonzero(dr - b.radius < self.required)
                if not len(grp):
                    continue
                idx = np.concatenate([np.arange(b.start[k], b.start[k + 1]) for k in grp])
                pts = b.points[idx] @ M[:3, :3].T + M[:3, 3]
                near: set = set()
                touch: set = set()
                left = set()
                for _round in range(len(ob.names)):          # every obstacle near it, not only the nearest one
                    sub, back = self._without(left)
                    if not len(sub.names):
                        break
                    d, who = sub.nearest(pts, self.required)
                    hit = who[d < self.required]
                    if not len(hit):
                        break
                    ks = {int(w) if back is None else int(back[w]) for w in hit}
                    near |= ks
                    touch |= {int(w) if back is None else int(back[w]) for w in who[d <= TOUCH]}
                    left |= ks
                if touch:
                    self.ignore.setdefault(i, set()).update(touch)
                if near - touch:
                    self.ends.setdefault(i, []).append((M[:3, 3].copy(), near - touch))

    def row(self, values) -> P.Row:
        n = self.nearest(values)
        req = self.required
        row = P.Row("CLR", P.TITLES["CLR"], amber_at=self.limits.crane)
        row.limit = f"{req:.2f} m needed"
        if n.distance >= FAR / 2:
            row.status, row.use, row.measure = lifting.OK, req / self.need, -self.need
            row.value = f"more than {self.need:.2f} m"
            row.words = (f"Nothing comes within {self.need:.2f} m of the boom, the load or the rigging ({req:.2f} m "
                         f"needed) – {P._limit_words(lifting.OK, self.limits.crane)}.")
            return row
        d = n.distance
        row.use = req / max(d, 1e-6)
        row.measure = -d
        row.status = lifting.status_of(row.use, self.limits.crane)
        row.value = f"{d:.2f} m"
        who = {"load": "the load", "rigging": "the rigging"}.get(n.kind, n.body)
        row.words = (f"Clearance {d:.2f} m: {who} ({n.body}) to {n.obstacle}, {req:.2f} m needed – "
                     f"{P._limit_words(row.status, self.limits.crane)}.")
        if n.spacing > SPACING * 1.01:
            row.words += f" (A large part: measured to about {0.6 * n.spacing * 100:.0f} cm.)"
        return row


# ---------------------------------------------------------------------------------------------------------------------
# reach envelope

@dataclass
class Reach:
    chart: object = None
    gross: float = 0.0                 # kg
    full: float | None = None          # m: the chart carries the gross load out to here (100 %)
    amber: float | None = None         # m: … within the amber limit
    longest: float | None = None       # m: the chart's longest row
    words: str = ""


def reach(chart, gross_kg: float, limits: lifting.Limits = lifting.DEFAULT_LIMITS) -> Reach:
    """How far out the chart carries ``gross_kg``: the longest row whose capacity is at least the gross load (the
    chart's next-longer-radius rule: every radius up to that row), and the same within the amber limit."""
    out = Reach(chart, float(gross_kg))
    if chart is None:
        out.words = "No chart applies to the crane's set-up: no reach ring."
        return out
    rows = [(float(r), c) for r, c in zip(chart.radius, chart.capacity)]
    out.longest = rows[-1][0] if rows else None

    def furthest(share):
        best = None
        for r, c in rows:
            if c is None or float(c) * share < gross_kg - 1e-9:
                break
            best = r
        return best
    out.full, out.amber = furthest(1.0), furthest(limits.crane)
    t = lifting.tonnes(gross_kg)
    lim = f"{limits.crane * 100:.0f} %"
    if out.full is None:
        out.words = f"The chart does not carry {t:.2f} t even at its shortest radius."
    else:
        out.words = (f"The chart carries {t:.2f} t out to {out.full:g} m; within your {lim} limit "
                     + (f"out to {out.amber:g} m." if out.amber is not None else "nowhere."))
    return out


def range_curve(rig: LR.Rig, values: dict, steps: int = 41) -> list:
    """The range diagram's curve: [(radius m, height m)] of the hook at the top of the hoist as the main boom luffs
    through its range, the other joints as given (telescope, jib, knuckle as they stand)."""
    luff = rig.role.get("luff")
    hoist = rig.role.get("hoist")
    if not luff:
        return []
    lo, hi = rig.limits(luff)
    lo, hi = max(lo, -90.0), min(hi, 90.0)
    v = dict(values)
    if hoist:
        v[hoist] = rig.solve_range(hoist)[0]
    out = []
    for a in np.linspace(lo, hi, steps):
        v[luff] = float(a)
        r, z = rig.radius_height(v)
        out.append((round(r, 3), round(z, 3)))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# exclusion zone

def hull(points) -> list:
    """The convex hull of 2-D points, counter-clockwise (Andrew's monotone chain)."""
    pts = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in points})
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def circle(c, r: float, n: int = 48, outside: bool = False) -> list:
    """``n`` points round a circle; ``outside``: the polygon round it (its edges touch the circle: it holds the whole
    circle – the exclusion zone never falls short of a radius)."""
    if outside:
        r = r / math.cos(math.pi / n)
    return [(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def exclusion_zone(slew_centre, tail: float, supports, path, load_r: float, margin: float = MARGIN_DEFAULT,
                   n: int = 32) -> list:
    """The ground outline round the lift (m, the plan's x-y): the tail swing circle round ``slew_centre`` (``tail``:
    the furthest point of what slews from its axis), the corners of the outriggers / tracks (``supports``), the
    hook's path widened by the load's radius, all widened by ``margin``; convex, counter-clockwise."""
    pts = list(circle(slew_centre, max(tail, 0.0), n, outside=True)) if tail > 0 else [tuple(slew_centre)]
    pts += [tuple(p) for p in supports]
    for p in path:
        pts += circle(p, max(load_r, 0.0), 12, outside=True) if load_r > 0 else [tuple(p)]
    h = hull(pts)
    if margin <= 0:
        return h
    grown = []
    for p in h:
        grown += circle(p, margin, n, outside=True)
    return hull(grown)


def polygon_area(poly) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2.0


def inside(poly, p) -> bool:
    """A point in a convex counter-clockwise polygon (on the edge counts)."""
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (x1 - x0) * (p[1] - y0) - (y1 - y0) * (p[0] - x0) < -1e-9:
            return False
    return True


# ---------------------------------------------------------------------------------------------------------------------
# ground footprint

@dataclass
class Patch:
    """One coloured piece of the ground footprint: a rectangle (corners, the crane's ground plane, m) with what it
    carries."""

    kind: str                          # "pad" | "track"
    name: str
    corners: list
    force: float = 0.0                 # N
    pressure: float | None = None      # Pa
    use: float | None = None
    status: str = lifting.NOT_CHECKED
    lifted: bool = False

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "corners": [list(map(float, c)) for c in self.corners],
                "force": self.force, "pressure": self.pressure, "use": self.use, "status": self.status,
                "lifted": self.lifted}


PAD_NAMES = ("front left", "front right", "rear left", "rear right")


def _rect(cx, cy, w, l):
    return [(cx - w / 2, cy - l / 2), (cx + w / 2, cy - l / 2), (cx + w / 2, cy + l / 2), (cx - w / 2, cy + l / 2)]


def footprint(checks: P.Checks, values: dict, pieces: int = 8) -> list:
    """[Patch] of the crane's ground support at ``values`` (in the crane's level frame, m – with a crawler's travel):
    the four outrigger pads (the plan's mat, else the file's pad) or the two tracks in ``pieces`` each. Each with its
    share of the load and the ground pressure against the allowable entered (grey when none is)."""
    sup, plan = checks.sup, checks.plan
    lim = plan.limits
    if sup.problem:
        return []
    items = sup.items(values, checks.cw, checks.hanging_kg())
    allow = plan.allowable_pa
    shift = np.zeros(2)
    if sup.travel:
        v0 = sup.carrier_values(values)
        p0 = checks.rig.moved(sup.travel, np.zeros(3), values) - checks.rig.moved(sup.travel, np.zeros(3), v0)
        shift = P._flat(sup.up, p0) * sup.rig_m
    out = []
    if sup.outr is not None:
        o = sup.outr
        sp = LR.outrigger_spread(checks.data, values)
        if not LR._number(o.get("a")) or sp is None:
            return []
        a, b = float(o["a"]) * sup.f_m, sp / 2.0
        c = [float(x) * sup.f_m for x in (o.get("centre") or (0.0, 0.0))]
        mat = plan.mat
        if mat is None:
            pad = o.get("pad")
            mat = (float(pad[0]) * sup.f_m, float(pad[1]) * sup.f_m) if isinstance(pad, (list, tuple)) else (0.6, 0.6)
        try:
            re = lifting.outrigger_reactions(items, a, b, c)
        except ValueError:
            return []
        area = mat[0] * mat[1]
        for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
            px, py = c[0] + sx * a, c[1] + sy * b
            pt = Patch("pad", PAD_NAMES[i], _rect(px, py, mat[0], mat[1]))
            if re.reactions is None:
                pt.status = lifting.RED
                pt.lifted = True
            else:
                r = float(re.reactions[i])
                pt.force, pt.pressure = r, r / area
                pt.lifted = r <= 1e-6
                if allow:
                    pt.use = pt.pressure / allow
                    pt.status = lifting.status_of(pt.use, lim.ground)
                if re.lifted is not None and i == re.lifted and pt.status == lifting.OK:
                    pt.status = lifting.AMBER
            out.append(pt)
    elif sup.trk is not None:
        t = sup.trk
        g, L, w = (float(t[k]) * sup.f_m for k in ("gauge", "length", "width"))
        c = [float(x) * sup.f_m for x in (t.get("centre") or (0.0, 0.0))]
        try:
            pm, x, y = lifting.resultant(items)
            res = lifting.tracks(pm, x - c[0], y - c[1], g, L, w, allowable=allow, limits=lim)
        except ValueError:
            return []
        d = res.details
        e = x - c[0]
        for k, side in enumerate((1, -1)):
            ty = c[1] + side * g / 2
            for j in range(pieces):
                x0 = -L / 2 + L * j / pieces
                x1 = x0 + L / pieces
                xm = (x0 + x1) / 2
                name = f"{'left' if side > 0 else 'right'} track {j + 1}"
                pt = Patch("track", name, [(c[0] + x0, ty - w / 2), (c[0] + x1, ty - w / 2), (c[0] + x1, ty + w / 2),
                                           (c[0] + x0, ty + w / 2)])
                if not d:
                    pt.status, pt.lifted = lifting.RED, True
                    out.append(pt)
                    continue
                pmax, pmin, contact = d["p_max"][k], d["p_min"][k], d["contact"][k]
                s = 1.0 if e >= 0 else -1.0
                u = (s * xm + L / 2) / L                  # 0 at the light end, 1 at the heavy end
                if d["shape"] == "trapezoid":
                    p = pmin + (pmax - pmin) * u
                else:
                    reach_ = (s * xm + L / 2) - (L - contact)
                    p = max(0.0, pmax * reach_ / contact) if contact > 0 else 0.0
                pt.pressure = p
                pt.force = p * w * L / pieces
                pt.lifted = p <= 1e-6
                if allow:
                    pt.use = p / allow
                    pt.status = lifting.status_of(pt.use, lim.ground)
                out.append(pt)
    if np.any(shift):
        for pt in out:
            pt.corners = [(cx + shift[0], cy + shift[1]) for cx, cy in pt.corners]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# the plan sheet (SVG + HTML)

RGB = {lifting.OK: "#4caf50", lifting.AMBER: "#f9a825", lifting.RED: "#e53935", lifting.NOT_CHECKED: "#9e9e9e"}


def _fit(points, w: float, h: float, pad: float = 24.0):
    pts = np.asarray([p for p in points], float).reshape(-1, 2)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = np.maximum(hi - lo, 1e-6)
    s = min((w - 2 * pad) / span[0], (h - 2 * pad) / span[1])
    off = np.array([pad + (w - 2 * pad - s * span[0]) / 2, pad + (h - 2 * pad - s * span[1]) / 2])

    def to(p):
        q = (np.asarray(p, float) - lo) * s + off
        return float(q[0]), float(h - q[1])
    return to, s


def _poly(to, pts, **attr) -> str:
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attr.items())
    return '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in (to(p) for p in pts)) + f'" {a}/>'


def _line(to, pts, **attr) -> str:
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attr.items())
    return '<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in (to(p) for p in pts)) + f'" {a}/>'


def nice(x: float) -> float:
    """The largest 1, 2 or 5 × 10^k not over ``x`` (a scale bar, a tick step)."""
    if x <= 0 or not math.isfinite(x):
        return 1.0
    k = 10 ** math.floor(math.log10(x))
    return max(m * k for m in (1, 2, 5) if m * k <= x * (1 + 1e-9))


def plan_svg(view: dict, w: float = 720.0, h: float = 520.0) -> str:
    """The plan view (top, to scale): the exclusion zone, the reach rings, the crane's footprint coloured by the
    ground check, the hook's path, the pick and the set-down, a scale bar and north-up axes. ``view``: world x-y (m)
    of ``zone``, ``slew``, ``rings`` [(radius, status)], ``patches`` [Patch dicts], ``path``, ``obstacles`` [(name,
    [corners])], ``nearest`` (two points or None)."""
    pts = list(view.get("zone") or []) + [tuple(view["slew"])]
    for r, _st in view.get("rings") or []:
        pts += circle(view["slew"], r, 8)
    for pt in view.get("patches") or []:
        pts += [tuple(c) for c in pt["corners"]]
    pts += [tuple(p) for p in view.get("path") or []]
    to, s = _fit(pts, w, h)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
           'font-family="sans-serif" font-size="11">', f'<rect width="{w:.0f}" height="{h:.0f}" fill="#fff"/>']
    for name, corners in view.get("obstacles") or []:
        if len(corners) >= 3:
            out.append(_poly(to, corners, fill="#cfd8dc", stroke="#90a4ae", stroke_width="0.8"))
    zone = view.get("zone") or []
    if len(zone) >= 3:
        out.append(_poly(to, zone, fill="#ffebee", fill_opacity="0.6", stroke="#c62828", stroke_width="2",
                         stroke_dasharray="8 4"))
        x, y = to(max(zone, key=lambda p: p[1]))
        out.append(f'<text x="{x:.1f}" y="{y - 6:.1f}" fill="#c62828" text-anchor="middle">Exclusion zone</text>')
    for r, st in view.get("rings") or []:
        out.append(_line(to, circle(view["slew"], r, 96) + [circle(view["slew"], r, 96)[0]], fill="none",
                         stroke=RGB.get(st, "#555"), stroke_width="1.6"))
        x, y = to((view["slew"][0] + r, view["slew"][1]))
        out.append(f'<text x="{x + 3:.1f}" y="{y - 3:.1f}" fill="{RGB.get(st, "#555")}">{r:g} m</text>')
    for pt in view.get("patches") or []:
        out.append(_poly(to, pt["corners"], fill=RGB.get(pt["status"], "#999"), stroke="#333", stroke_width="0.6"))
    path = [tuple(p) for p in view.get("path") or []]
    if len(path) >= 2:
        out.append(_line(to, path, fill="none", stroke="#1565c0", stroke_width="2"))
        for p, lab in ((path[0], "pick"), (path[-1], "set-down")):
            x, y = to(p)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1565c0"/>'
                       f'<text x="{x + 6:.1f}" y="{y + 4:.1f}" fill="#1565c0">{lab}</text>')
    x, y = to(view["slew"])
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#000"/>')
    near = view.get("nearest")
    if near:
        out.append(_line(to, near, fill="none", stroke="#6a1b9a", stroke_width="1.5", stroke_dasharray="3 2"))
    bar = nice(100.0 / s)
    out.append(f'<line x1="20" y1="{h - 14:.0f}" x2="{20 + bar * s:.1f}" y2="{h - 14:.0f}" stroke="#000" '
               f'stroke-width="2"/><text x="20" y="{h - 20:.0f}">{bar:g} m</text>')
    out.append(f'<text x="{w - 20:.0f}" y="30" text-anchor="middle">N</text><line x1="{w - 20:.0f}" y1="36" '
               f'x2="{w - 20:.0f}" y2="60" stroke="#000"/>')
    out.append("</svg>")
    return "\n".join(out)


def range_svg(curve, chart_rows, full: float | None, amber: float | None, hook=None, path=(), w: float = 520.0,
              h: float = 360.0) -> str:
    """The range diagram: the hook's highest point over the radius as the boom luffs (``curve`` [(r, z)]), the chart's
    rows (radius, capacity t) as ticks, the reach of the gross load (100 % red line, amber limit), the hook now and
    along the path [(r, z)]."""
    pts = [tuple(p) for p in curve] + [(0.0, 0.0)] + [tuple(p) for p in path] + ([tuple(hook)] if hook else [])
    pts += [(float(r), 0.0) for r, _c in chart_rows]
    to, _s = _fit(pts, w, h, pad=36.0)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
           'font-family="sans-serif" font-size="10">', f'<rect width="{w:.0f}" height="{h:.0f}" fill="#fff"/>']
    x0, y0 = to((0.0, 0.0))
    xm = max([p[0] for p in pts] + [1.0])
    zm = max([p[1] for p in pts] + [1.0])
    x1, _ = to((xm, 0.0))
    _, y1 = to((0.0, zm))
    out.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y0:.1f}" stroke="#000"/>'
               f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{y1:.1f}" stroke="#000"/>'
               f'<text x="{x1:.1f}" y="{y0 + 24:.1f}" text-anchor="end">radius (m)</text>'
               f'<text x="{x0 + 4:.1f}" y="{y1 + 4:.1f}">hook height (m)</text>')
    for lim, col in ((amber, RGB[lifting.AMBER]), (full, RGB[lifting.RED])):
        if lim is not None:
            xa, _ = to((lim, 0.0))
            out.append(f'<line x1="{xa:.1f}" y1="{y0:.1f}" x2="{xa:.1f}" y2="{y1:.1f}" stroke="{col}" '
                       f'stroke-width="1.5" stroke-dasharray="5 3"/>')
    if len(curve) >= 2:
        out.append(_line(to, curve, fill="none", stroke="#37474f", stroke_width="2"))
    last = -1e9
    for r, c in chart_rows:
        xr, _ = to((float(r), 0.0))
        out.append(f'<line x1="{xr:.1f}" y1="{y0:.1f}" x2="{xr:.1f}" y2="{y0 + 5:.1f}" stroke="#000"/>')
        if xr - last < 24.0:                    # rows close together: a tick only, their numbers would overlap
            continue
        last = xr
        out.append(f'<text x="{xr:.1f}" y="{y0 + 14:.1f}" text-anchor="middle" font-size="8">{float(r):g}</text>'
                   + (f'<text x="{xr:.1f}" y="{y0 - 4:.1f}" text-anchor="middle" font-size="8" fill="#555">'
                      f'{lifting.tonnes(c):.3g}</text>' if c is not None else ""))
    step = nice(zm / 5.0)
    z = step
    while z <= zm + 1e-9:
        _, yz = to((0.0, z))
        out.append(f'<line x1="{x0 - 4:.1f}" y1="{yz:.1f}" x2="{x0:.1f}" y2="{yz:.1f}" stroke="#000"/>'
                   f'<text x="{x0 - 6:.1f}" y="{yz + 3:.1f}" text-anchor="end" font-size="8">{z:g}</text>')
        z += step
    if path:
        out.append(_line(to, path, fill="none", stroke="#1565c0", stroke_width="1.5"))
    if hook:
        xh, yh = to(hook)
        out.append(f'<circle cx="{xh:.1f}" cy="{yh:.1f}" r="4" fill="#1565c0"/>')
    out.append(f'<text x="{w - 8:.0f}" y="14" text-anchor="end" fill="#555">chart capacity (t) over each row</text>')
    out.append("</svg>")
    return "\n".join(out)


def sheet_html(title: str, lines: list, plan: str, rng: str, rows: list, notes: list) -> str:
    """The plan sheet: a header (``lines`` of "label: value"), the plan view, the range diagram, the checks table
    (``rows``: P.Row) and notes – one page to print (A4 landscape)."""
    e = html.escape
    head = "".join(f"<div><b>{e(k)}</b> {e(v)}</div>" for k, v in lines)
    trs = "".join(
        f'<tr><td><span class="dot" style="background:{RGB.get(r.status, "#999")}"></span>{e(r.title)}</td>'
        f"<td>{e(P.COLOUR[r.status])}</td><td>{'' if r.use is None or r.id == 'CLR' else f'{r.use * 100:.0f} %'}</td>"
        f"<td>{e(r.value)}</td><td>{e(r.limit)}</td><td>{'' if r.t is None else f'{r.t:.1f}'}</td>"
        f"<td>{e(r.words)}</td></tr>" for r in rows)
    ns = "".join(f"<li>{e(n)}</li>" for n in notes)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>
<style>
@page {{ size: A4 landscape; margin: 12mm; }}
body {{ font-family: sans-serif; font-size: 11px; color: #222; margin: 16px; }}
h1 {{ font-size: 18px; margin: 0 0 6px; }}
.head {{ display: grid; grid-template-columns: repeat(3, auto); gap: 2px 18px; margin-bottom: 8px; }}
.views {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; }}
.views figure {{ margin: 0; }} figcaption {{ font-weight: bold; margin-bottom: 2px; }}
svg {{ max-width: 100%; height: auto; border: 1px solid #ccc; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
td, th {{ border: 1px solid #ccc; padding: 3px 5px; text-align: left; vertical-align: top; }}
.dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; }}
.note {{ color: #555; }}
</style></head><body>
<h1>{e(title)}</h1>
<div class="head">{head}</div>
<div class="views"><figure><figcaption>Plan view</figcaption>{plan}</figure>
<figure><figcaption>Range diagram</figcaption>{rng}</figure></div>
<table><tr><th>Check</th><th>Status</th><th>Use</th><th>Worst value</th><th>Limit</th><th>Frame</th><th>In words</th></tr>
{trs}</table>
<ul class="note">{ns}</ul>
</body></html>
"""
