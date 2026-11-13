"""Tracks and belts (task 0079): a closed chain of rigid links running round wheels – plain Python, no Blender.

A **track** is a chain of N rigid links, each hinging on two pins one pitch p apart, closed into a loop round two or
more wheels whose axes are parallel (a tensioner's track round its sprockets and support rollers, a crawler track, a
conveyor belt of separate slats). Parts that ride on a link (pads, back plates) move rigidly with it.

* ``chain_of`` reads the chain from the links' hinge points as the CAD file draws them: the pins (neighbour links
  share one), their order round the loop, the pitch. One closed cycle of one pitch, or a plain reason why not.
* ``fit`` lays the **loop** round the wheels: in the plane square to their axes, each wheel a circle of radius R (where
  the pins lie when the chain wraps it, the distance to the run when the chain only touches it – a support roller)
  on the side the chain passes it; straight runs are the tangents between neighbour wheels (closed form), with arcs
  between them. Every CAD pin must lie on that loop.
* **The chain parameter c** (metres of chain): on a straight run it is the length along the run; on a wheel one tooth
  step (θt = 2·asin(p / 2R), the angle between two pins one pitch apart on the circle) counts p. So two pins one pitch
  apart in c are exactly one pitch apart in space on a run and on a wheel, and a part placed at c and moved on by the
  chain's travel keeps its place in the chain – the polygon effect of a real chain on its sprockets. The loop's length
  in c is ``length``; for a chain that fits its wheels it is N·p.
* **A link at c** hinges at A = ``point(c)`` and B = the point ahead on the loop exactly p away (``ahead``: the chord,
  solved). Its frame: X along A→B, Y = the loop's normal n, Z = X × Y (outwards, away from the loop's inside).
* **Wheels turn** one tooth per pitch of chain: θt/p radians per metre (anticlockwise about n for a wheel inside the
  loop, clockwise for one the chain goes round the other way). A wheel the chain only touches turns at 1/r, r = its
  radius to the chain's surface.

The loop runs anticlockwise about ``n`` (``fit`` turns n round when the pins go the other way). Units: metres,
radians; points in any one set of coordinates (the Blender side uses the carrier's, see ``blender/tracks.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

PIN_TOL = 0.001                 # m: two links' hinge points this close are one pin
PITCH_TOL = 0.005               # share: the links of one chain have one pitch
ON_LOOP = 0.001                 # m: every CAD pin lies this close to the loop
FLAT = 0.002                    # share of p: the chain's pins lie this close to one plane
AXIS_TOL = math.radians(1.0)    # the wheels' axes are parallel to this
STRAIGHT = 0.0002               # m: a pin this close to the line through its neighbours lies on a straight run
TABLE_STEP = 0.002              # m of chain between two points of the loop table
MIN_TEETH = 4                   # a wheel smaller than this many links round is refused
LENGTH_NOTE = 0.02              # share of p: the loop's length and N x p differ this much -> reported


class TrackError(ValueError):
    """The parts are not a track the app can run: the message says why, in plain words."""


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 0.0 else v


def _mm(m: float) -> str:
    return f"{m * 1000.0:.1f}"


def _left(v) -> np.ndarray:
    """A 2-D vector turned a quarter anticlockwise (works on (..., 2) arrays)."""
    v = np.asarray(v, dtype=float)
    return np.stack([-v[..., 1], v[..., 0]], axis=-1)


def _cross2(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


# ---------------------------------------------------------------------------
# the chain: pins and links
# ---------------------------------------------------------------------------

@dataclass
class Chain:
    """``pins`` (N, 3) in loop order; ``link_pins`` (K, 2): each link's two pins (indices into ``pins``), the first
    one first along that order; ``pitch`` (m)."""
    pins: np.ndarray
    link_pins: np.ndarray
    pitch: float

    def reversed(self) -> "Chain":
        n = len(self.pins)
        lp = (n - 1 - self.link_pins)[:, ::-1]
        return Chain(self.pins[::-1].copy(), lp.copy(), self.pitch)


def loop_of(hinges, keep: int, tol: float = PIN_TOL) -> np.ndarray:
    """The indices of the links that hang together with link ``keep`` (through shared pins): the other track's
    links of the same name are left out."""
    h = np.asarray(hinges, dtype=float).reshape(-1, 2, 3)
    k = len(h)
    parent = list(range(k))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    pts = h.reshape(-1, 3)
    for i in range(len(pts)):
        d = np.linalg.norm(pts - pts[i], axis=1)
        for j in np.flatnonzero(d <= tol):
            a, b = root(i // 2), root(int(j) // 2)
            if a != b:
                parent[a] = b
    r = root(keep)
    return np.array([i for i in range(k) if root(i) == r], dtype=int)


def chain_of(hinges, tol: float = PIN_TOL) -> Chain:
    """The chain the links make. ``hinges`` (K, 2, 3): each link's two hinge points (any order of links and ends).
    Raises TrackError: fewer than 3 links, two pitches, an open chain (a link missing), a pin with three links, or
    more than one loop."""
    h = np.asarray(hinges, dtype=float).reshape(-1, 2, 3)
    k = len(h)
    if k < 3:
        raise TrackError(f"A track needs at least 3 links; {k} {'was' if k == 1 else 'were'} found.")
    if not np.isfinite(h).all():
        raise TrackError("The links' places could not be read.")
    d = np.linalg.norm(h[:, 1] - h[:, 0], axis=1)
    pitch = float(np.median(d))
    if pitch <= 0.0:
        raise TrackError("The links' two hinges lie on one point: they are no chain links.")
    off = np.abs(d - pitch) > PITCH_TOL * pitch
    if off.any():
        bad = int(np.flatnonzero(off)[0])
        raise TrackError(f"The links do not all have one pitch: most hinge {_mm(pitch)} mm apart, link {bad + 1} "
                         f"{_mm(float(d[bad]))} mm. A track is one chain of one pitch.")
    pts = h.reshape(-1, 3)
    pin_of = -np.ones(len(pts), dtype=int)
    centres: list = []
    for i, p in enumerate(pts):                       # merge the hinge points that are one pin
        if centres:
            dist = np.linalg.norm(np.asarray(centres) - p, axis=1)
            j = int(np.argmin(dist))
            if dist[j] <= tol:
                pin_of[i] = j
                continue
        pin_of[i] = len(centres)
        centres.append(p)
    lp = pin_of.reshape(-1, 2)
    if (lp[:, 0] == lp[:, 1]).any():
        raise TrackError("A link's two hinges fall on one pin: the pitch is too small to read.")
    n = len(centres)
    # each pin's place: the mean of the hinge points that make it
    pins = np.zeros((n, 3))
    np.add.at(pins, pin_of, pts)
    pins /= np.bincount(pin_of, minlength=n)[:, None]
    deg = np.bincount(lp.ravel(), minlength=n)
    if (deg == 1).any():
        at = pins[int(np.flatnonzero(deg == 1)[0])]
        raise TrackError(f"The chain is open: a link is missing next to the pin at ({_mm(at[0])}, {_mm(at[1])}, "
                         f"{_mm(at[2])}) mm. A track is a closed loop of links.")
    if (deg > 2).any():
        raise TrackError("More than two links hinge on one pin: the parts are not one chain.")
    nb: list = [[] for _ in range(n)]
    for li, (a, b) in enumerate(lp):
        nb[a].append((b, li))
        nb[b].append((a, li))
    order, links, used = [0], [], set()
    cur = 0
    while True:
        nxt = next(((p, li) for p, li in nb[cur] if li not in used), None)
        if nxt is None:
            break
        p, li = nxt
        used.add(li)
        links.append(li)
        if p == 0:
            break
        order.append(p)
        cur = p
    if len(order) != n or len(links) != k:
        raise TrackError(f"The links make more than one loop ({len(links)} of {k} links go round together): a "
                         "track is one closed chain.")
    out = np.zeros((k, 2), dtype=int)
    for step, li in enumerate(links):
        out[li] = (step, (step + 1) % n)
    return Chain(pins[np.asarray(order)], out, pitch)


# ---------------------------------------------------------------------------
# the loop round the wheels
# ---------------------------------------------------------------------------

@dataclass
class WheelFit:
    """One wheel as the loop has it: ``centre`` (2-D), ``radius`` R (pitch line), ``side`` (+1: the chain goes round
    it anticlockwise about n, the wheel is inside the loop; -1 the other way), ``wrapped`` (the chain bends round it;
    False: it only touches the chain – a support roller), ``wrap`` (angle the chain lies on it), ``index`` (the
    wheel's place in the list given to ``fit``)."""
    centre: np.ndarray
    radius: float
    side: int
    wrapped: bool
    index: int
    wrap: float = 0.0
    tooth: float = 0.0


@dataclass
class Loop:
    """The loop of a chain round its wheels; see the module's docstring."""
    origin: np.ndarray                 # 3-D: the plane's origin (the loop's points are origin + x e1 + y e2)
    e1: np.ndarray
    e2: np.ndarray
    n: np.ndarray                      # the loop's normal: the chain runs anticlockwise about it
    pitch: float
    wheels: list                       # WheelFit, in loop order
    kinds: list = field(default_factory=list)       # per piece: "LINE" / "ARC"
    data: list = field(default_factory=list)        # per piece: (p0, p1) for a line, (wheel index, a0) for an arc
    lengths: np.ndarray = field(default_factory=lambda: np.zeros(0))   # per piece, in c
    starts: np.ndarray = field(default_factory=lambda: np.zeros(0))

    # ---- geometry ------------------------------------------------------------------------------------------------
    @property
    def length(self) -> float:
        return float(self.lengths.sum())

    def to3(self, xy) -> np.ndarray:
        xy = np.asarray(xy, dtype=float)
        return self.origin + xy[..., :1] * self.e1 + xy[..., 1:2] * self.e2

    def to2(self, p) -> np.ndarray:
        rel = np.asarray(p, dtype=float) - self.origin
        return np.stack([rel @ self.e1, rel @ self.e2], axis=-1)

    def point2(self, c) -> np.ndarray:
        """The loop's 2-D point at chain parameter(s) c (any real numbers: taken round the loop)."""
        c = np.mod(np.asarray(c, dtype=float), self.length)
        flat = np.atleast_1d(c)
        piece = np.clip(np.searchsorted(self.starts, flat, side="right") - 1, 0, len(self.kinds) - 1)
        out = np.zeros((len(flat), 2))
        for i, kind in enumerate(self.kinds):
            sel = piece == i
            if not sel.any():
                continue
            u = flat[sel] - self.starts[i]
            if kind == "LINE":
                p0, p1 = self.data[i]
                L = self.lengths[i]
                t = u / L if L > 0 else np.zeros_like(u)
                out[sel] = p0 + np.outer(t, p1 - p0)
            else:
                w, a0 = self.data[i]
                wh = self.wheels[w]
                a = a0 + wh.side * u * (wh.tooth / self.pitch)
                out[sel] = wh.centre + wh.radius * np.stack([np.cos(a), np.sin(a)], axis=1)
        return out.reshape(np.shape(c) + (2,))

    def point(self, c) -> np.ndarray:
        return self.to3(self.point2(c))

    def ahead(self, c, iterations: int = 60) -> np.ndarray:
        """The chain parameter of the point ahead of c on the loop exactly one pitch away (a link's second hinge)."""
        c = np.atleast_1d(np.asarray(c, dtype=float))
        a = self.point2(c)
        p = self.pitch
        lo, hi = c + 0.5 * p, c + 2.0 * p
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            far = np.linalg.norm(self.point2(mid) - a, axis=1) > p
            hi = np.where(far, mid, hi)
            lo = np.where(far, lo, mid)
        return 0.5 * (lo + hi)

    def frames(self, c):
        """(A, X, Z) at chain parameter(s) c: hinge A (3-D), the unit direction to hinge B, the outward unit Z."""
        c = np.atleast_1d(np.asarray(c, dtype=float))
        a = self.point2(c)
        b = self.point2(self.ahead(c))
        x2 = (b - a) / np.linalg.norm(b - a, axis=1, keepdims=True)
        X = x2[:, :1] * self.e1 + x2[:, 1:2] * self.e2
        Z = np.cross(X, self.n)
        return self.to3(a), X, Z

    def matrices(self, c) -> np.ndarray:
        """(len(c), 4, 4): the frame of a link whose first hinge is at c (columns X, Y = n, Z, A)."""
        A, X, Z = self.frames(c)
        m = np.zeros((len(A), 4, 4))
        m[:, :3, 0], m[:, :3, 1], m[:, :3, 2], m[:, :3, 3] = X, np.broadcast_to(self.n, X.shape), Z, A
        m[:, 3, 3] = 1.0
        return m

    def table(self, step: float = TABLE_STEP):
        """The loop as samples: (A (M, 3), X (M, 3), Z (M, 3)) at c = j * length / M, and M."""
        m = max(16, int(math.ceil(self.length / step)))
        c = np.arange(m) * (self.length / m)
        A, X, Z = self.frames(c)
        return A, X, Z, m

    def locate(self, points):
        """(c, distance): each 3-D point's chain parameter on the loop and its distance from the loop (in the plane
        and out of it)."""
        P = np.atleast_2d(np.asarray(points, dtype=float))
        xy = self.to2(P)
        depth = np.abs((P - self.origin) @ self.n)
        best_d = np.full(len(P), np.inf)
        best_c = np.zeros(len(P))
        for i, kind in enumerate(self.kinds):
            s0, L = self.starts[i], self.lengths[i]
            if kind == "LINE":
                p0, p1 = self.data[i]
                seg = p1 - p0
                g = float(seg @ seg)
                t = np.clip(((xy - p0) @ seg) / g, 0.0, 1.0) if g > 0 else np.zeros(len(P))
                d = np.linalg.norm(xy - (p0 + np.outer(t, seg)), axis=1)
                c = s0 + t * L
            else:
                w, a0 = self.data[i]
                wh = self.wheels[w]
                rel = xy - wh.centre
                ang = np.arctan2(rel[:, 1], rel[:, 0])
                along = np.mod(wh.side * (ang - a0), 2.0 * math.pi)      # angle along the wrap from its start
                span = wh.wrap
                inside = along <= span
                back = 2.0 * math.pi - along                              # before the start
                along = np.where(inside, along, np.where(back < along - span, 0.0, span))
                a = a0 + wh.side * along
                q = wh.centre + wh.radius * np.stack([np.cos(a), np.sin(a)], axis=1)
                d = np.linalg.norm(xy - q, axis=1)
                c = s0 + along * (self.pitch / wh.tooth) if wh.tooth > 0 else np.full(len(P), s0)
            better = d < best_d
            best_d = np.where(better, d, best_d)
            best_c = np.where(better, c, best_c)
        return np.mod(best_c, self.length), np.hypot(best_d, depth)

    def runs(self) -> list:
        """The straight runs as (start 3-D, end 3-D, c at the start)."""
        return [(self.to3(self.data[i][0]), self.to3(self.data[i][1]), float(self.starts[i]))
                for i, k in enumerate(self.kinds) if k == "LINE" and self.lengths[i] > 0.0]

    def direction(self, c) -> np.ndarray:
        """The chain's unit direction of travel (3-D) at c, for a positive travel."""
        A, X, _Z = self.frames(c)
        del A
        return X

    def rate(self, w: int, touch_radius: float = 0.0) -> float:
        """Radians wheel ``w`` (its place in ``wheels``) turns about n per metre of chain: one tooth per pitch when
        the chain wraps it, else 1 / its radius to the chain (``touch_radius``, default R)."""
        wh = self.wheels[w]
        if wh.wrapped:
            return wh.side * wh.tooth / self.pitch
        r = touch_radius if touch_radius > 0.0 else wh.radius
        return wh.side / r


def _plane(axes, pins):
    n = _unit(axes[0])
    for k, a in enumerate(axes):
        a = _unit(a)
        if abs(float(a @ n)) < math.cos(AXIS_TOL):
            ang = math.degrees(math.acos(min(1.0, abs(float(a @ n)))))
            raise TrackError(f"The wheels' axes are not parallel: wheel {k + 1} is {ang:.1f}° off the first one. "
                             "A track runs round wheels whose axes are parallel.")
    ref = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = _unit(ref - n * (ref @ n))
    e2 = np.cross(n, e1)
    depth = float(np.mean(pins @ n))
    return n, e1, e2, n * depth


def _area(xy) -> float:
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def fit(chain: Chain, centres, axes, names=None):
    """The loop of ``chain`` round its wheels. ``centres`` / ``axes``: a point on each wheel's axis and its
    direction (any order of wheels: they are sorted round the loop). Returns the loop; its normal n is chosen so the
    chain's pin order runs anticlockwise about it (c grows along that order). Raises TrackError in plain words."""
    names = list(names) if names is not None else [f"wheel {k + 1}" for k in range(len(centres))]
    if len(centres) < 2:
        raise TrackError("A track runs round at least 2 wheels: click the wheels round the loop.")
    pins = np.asarray(chain.pins, dtype=float)
    p = chain.pitch
    n, e1, e2, origin = _plane([np.asarray(a, dtype=float) for a in axes], pins)
    flat = np.abs((pins - origin) @ n)
    if flat.max() > max(0.002, FLAT * p):
        raise TrackError(f"The chain's pins do not lie in one plane square to the wheels' axes ({_mm(flat.max())} mm "
                         "off): are these the wheels this chain runs round?")
    rel = pins - origin
    xy = np.stack([rel @ e1, rel @ e2], axis=1)
    if _area(xy) < 0.0:                               # run anticlockwise about n
        n, e2 = -n, -e2
        xy[:, 1] *= -1.0
        origin = n * float(np.mean(pins @ n))
    N = len(xy)
    wheels = []
    for k, (c3, name) in enumerate(zip(centres, names)):
        c = np.array([(np.asarray(c3, dtype=float) - origin) @ e1, (np.asarray(c3, dtype=float) - origin) @ e2])
        d = np.linalg.norm(xy - c, axis=1)
        i = int(np.argmin(d))
        a, b = xy[(i - 1) % N], xy[(i + 1) % N]
        u = _unit(b - a)
        off_line = abs(float(_cross2(u, xy[i] - a)))
        side = 1 if _cross2(b - a, c - xy[i]) > 0.0 else -1
        if off_line <= STRAIGHT:                      # the chain runs straight past it: it only touches
            r = abs(float(_cross2(u, c - a)))
            wrapped = False
        else:
            r = float(d[i])
            wrapped = True
        if r < p / (2.0 * math.sin(math.pi / MIN_TEETH)) - 1e-9 and wrapped:
            raise TrackError(f"'{name}' is too small for this chain: it is {_mm(2 * r)} mm across at the pins, "
                             f"less than {MIN_TEETH} links of {_mm(p)} mm round.")
        # its place round the loop: the nearest pin, then how far along the chain from it
        t = float((c - xy[i]) @ u)
        wheels.append((i + max(-0.49, min(0.49, t / p)), WheelFit(c, r, side, wrapped, k)))
    wheels.sort(key=lambda kw: kw[0])
    order = [w for _key, w in wheels]
    m = len(order)
    for w in order:
        w.tooth = 2.0 * math.asin(min(1.0, p / (2.0 * w.radius))) if w.radius > p / 2.0 else math.pi
    # tangents between neighbours (signed radii), arcs between them
    outs, ins = [None] * m, [None] * m
    for j in range(m):
        w0, w1 = order[j], order[(j + 1) % m]
        r0, r1 = w0.side * w0.radius, w1.side * w1.radius
        D = w1.centre - w0.centre
        L2 = float(D @ D)
        delta = r1 - r0
        t2 = L2 - delta * delta
        if t2 <= 1e-12:
            raise TrackError(f"'{names[w0.index]}' and '{names[w1.index]}' overlap: the chain has no straight run "
                             "between them.")
        t = math.sqrt(t2)
        d = (t * D - delta * _left(D)) / L2
        nl = _left(d)
        outs[j] = w0.centre - r0 * nl
        ins[(j + 1) % m] = w1.centre - r1 * nl
    loop = Loop(origin, e1, e2, n, p, order)
    kinds, data, lengths = [], [], []
    for j in range(m):
        w = order[j]
        a_in = math.atan2(*(ins[j] - w.centre)[::-1])
        a_out = math.atan2(*(outs[j] - w.centre)[::-1])
        wrap = (w.side * (a_out - a_in)) % (2.0 * math.pi)
        if wrap > 2.0 * math.pi - 1e-6:
            wrap = 0.0
        if not w.wrapped and wrap > 0.1:
            raise TrackError(f"The chain only touches '{names[w.index]}' in the CAD file but would have to go round "
                             "it: click the wheels in the order the chain passes them, and only wheels it touches.")
        w.wrap = wrap
        kinds.append("ARC")
        data.append((j, a_in))
        lengths.append(wrap * p / w.tooth if w.tooth > 0 else 0.0)
        kinds.append("LINE")
        data.append((outs[j], ins[(j + 1) % m]))
        lengths.append(float(np.linalg.norm(ins[(j + 1) % m] - outs[j])))
    loop.kinds, loop.data = kinds, data
    loop.lengths = np.asarray(lengths)
    loop.starts = np.concatenate([[0.0], np.cumsum(loop.lengths)[:-1]])
    if loop.length <= 0.0:
        raise TrackError("The loop round these wheels has no length.")
    # every CAD pin on it
    _c, dist = loop.locate(pins)
    worst = int(np.argmax(dist))
    if dist[worst] > ON_LOOP:
        at = pins[worst]
        raise TrackError(f"The chain's CAD places do not lie on one loop round these wheels: the pin at "
                         f"({_mm(at[0])}, {_mm(at[1])}, {_mm(at[2])}) mm is {_mm(float(dist[worst]))} mm off it. Is "
                         "a wheel missing, or one clicked that the chain does not go round?")
    return loop


def length_note(loop: Loop, links: int) -> str:
    """'' or a sentence when the loop round the wheels and the CAD chain (links x pitch) differ by more than 2 % of
    a pitch."""
    want = links * loop.pitch
    diff = loop.length - want
    if abs(diff) <= LENGTH_NOTE * loop.pitch:
        return ""
    return (f"The loop round the wheels is {_mm(loop.length)} mm, the chain {links} x {_mm(loop.pitch)} = "
            f"{_mm(want)} mm ({'+' if diff > 0 else '-'}{_mm(abs(diff))} mm): it shows a gap or an overlap where "
            "the CAD file has one.")


def drive_expression(k: float, c: float, length: float, bias: float) -> str:
    """The driver of a part's Travel: u = a * k + c metres of chain, kept to 0 … length, + bias – plain arithmetic,
    so Blender evaluates it without Python (``floor`` is one of its simple-expression functions)."""
    u = f"(a * {float(k)!r}"
    if c > 0:
        u += f" + {float(c)!r}"
    elif c < 0:
        u += f" - {-float(c)!r}"
    u += ")"
    return f"{u} - {float(length)!r} * floor({u} / {float(length)!r}) + {float(bias)!r}"
