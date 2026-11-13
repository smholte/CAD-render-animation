"""Cable paths: a cable over sheaves, rollers, chutes and bends, without Blender (task 0078).

A cable's centreline is a chain of **straight runs and arcs** that meet without a kink. Every arc lies on a
**wheel**: a cylinder (any point on its axis, the axis, the radius to the cable's *middle*) and the side the cable
goes round it: +1 when it turns about +axis (right hand), -1 about -axis. Metres, radians, NumPy only.

**The solver** (``solve``, ``solve_frames``). A cable under tension takes the shortest way: straight between the
wheels, and on a wheel the line a string takes on a cylinder – a circle arc when it comes and goes square to the
axis, else a helix (the angle round the wheel and the place along its axis rise evenly). Where the cable touches a
wheel depends only on what the wheel sees along its own axis, so:

1. *Wheels with parallel axes that follow each other* form a group. Seen along the axis the cable between two of
   them is the common tangent of two circles – outer when it goes round both the same way, crossing when not –
   and has a closed form, also when the circles just touch (an S-bend without a straight between: a straight of
   length 0). From a point (the start, the end) to a wheel it is the tangent from a point to a circle.
2. *Along the axis* the cable rises evenly with the length it has when the group is seen along its axis
   (unrolled, a string on a cylinder is a straight line). That gives every touching point's place on its wheel,
   between the last point before the group and the first after it.
3. *Wheels whose axes are not parallel* depend on each other: the tangent from the one's touching point to the
   other is taken in turn (0075's alternating), with step 2 after each round, until no touching point moves
   more than 1e-12 m. A path in one plane needs no rounds at all.

So a wheel is a cylinder, not a groove: with a fleet angle the cable is drawn where a tight string would lie on
the wheel, without a kink, and not held in the wheel's middle plane. A path that lies in the planes its CAD
drawing gave it (every straight square to the axes of the wheels at its ends) stays exactly there.

A path that cannot be is refused in plain words, never drawn broken: a point or a wheel inside another wheel's
circle, wheels that overlap so that no straight fits between them, a wheel the cable would have to go round by
more than 350° (it passes it on the other side), numbers that are not numbers. Circles that overlap by less than
``TOUCH`` (0.1 mm: places kept in 32-bit numbers) count as touching.

``solve_frames`` does the same for many frames at once (arrays over the frames, no Python loop over them) with the
same number of points on every frame; a frame that has no path keeps the shape of the last frame that had one.

**Reading a CAD cable** (``read_cable``): the centreline of a cable drawn in CAD (``flex_fit.tube_centreline``) is
cut into straights and arcs, each arc is matched with the round part it lies on (a WRAP: centre, axis and radius
then come from the part), the others are bends in the air (BEND, the fitted circle), and round parts the cable
only rests on or runs past are TOUCH contacts. See ``read_cable``.

**The surface a cable rests on** (``seat``, ``surface_radius``, ``is_round``): a round part's outline (radius
against the place along its axis) is read from the triangles' edges – on a flat triangle the point furthest from
the axis at any place along it lies on an edge, so a plain roller with corners only at its ends is read exactly –
and the cable's round section is let down onto it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

TOUCH = 1e-4                    # m: circles that overlap by less than this touch (a straight of length 0)
PARALLEL = 1e-6                 # rad: axes this close to parallel are parallel (one group)
SETTLED = 1e-12                 # m: the rounds stop when no touching point moves more than this …
ROUNDS = 40                     # … or after this many
GOOD_ENOUGH = 1e-9              # m: a frame that still moves less than this after all rounds is taken
MAX_WRAP = math.radians(350.0)  # further round a wheel than this: refused
NO_WRAP = 1e-6                  # rad: a wrap this much less than nothing is no wrap at all (rounding)
STEP = math.radians(4.0)        # points on an arc: one every 4°
_SLACK = math.radians(5.0)      # wraps are counted from -5° to 355°
_NUDGE = 1e-6                   # rad: the nudge that shows how a straight's direction matters

_OK, _NUMBERS, _INSIDE, _OVERLAP, _WRAP, _UNSETTLED = 0, 1, 2, 3, 4, 5


@dataclass
class Wheel:
    centre: np.ndarray          # (3,) a point on the axis (any; best in the plane the cable lies in there)
    axis: np.ndarray            # (3,) unit
    radius: float               # axis -> the cable's middle
    side: int                   # +1: the cable turns about +axis (right hand), -1: about -axis


@dataclass
class Path:
    ok: bool
    problem: str                # '' or a plain reason that names the contact by its number (from 1)
    bad: int                    # index of the wheel the problem is about (-1: none)
    points: np.ndarray          # (n, 3) start, per wheel its arc (tangent-in … tangent-out), end
    s: np.ndarray               # (n,) length along the path from the start (arcs exact, not chords)
    first: np.ndarray           # (W,) index in points of each wheel's tangent-in point
    wrap: np.ndarray            # (W,) rad >= 0
    length: float
    counts: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))   # (W,) points per arc


# ---------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------

def _dot(a, b):
    return np.einsum("...i,...i->...", a, b)


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 0.0, n, 1.0)


def _square(axis):
    """Two unit directions u, v square to each axis with u x v = axis."""
    least = np.argmin(np.abs(axis), axis=-1)
    ref = np.zeros_like(axis)
    np.put_along_axis(ref, least[..., None], 1.0, axis=-1)
    u = _unit(np.cross(axis, ref))
    return u, np.cross(axis, u)


def _number(i: int) -> str:
    return f"contact {i + 1}"


def _sentence(code: int, i: int, j: int, name=_number) -> str:
    """The plain reason for a refusal; ``i`` the wheel it is about, ``j`` its neighbour (-1: the start, -2: the
    end, -3: none)."""
    if code == _NUMBERS:
        if i < 0:
            return "The cable's start or end is not a place (not a number)."
        return f"The place, axis or radius of {name(i)} is not valid."
    if code == _INSIDE:
        other = {-1: "the cable's start", -2: "the cable's end"}.get(j) or name(j)
        return f"{other[0].upper()}{other[1:]} lies inside the circle of {name(i)}: the cable cannot go round it."
    if code == _OVERLAP:
        return (f"{name(j)[0].upper()}{name(j)[1:]} and {name(i)} overlap: no straight run fits between them on "
                f"these sides.")
    if code == _WRAP:
        return (f"The cable would go more than 350° round {name(i)}: it passes it on the other side "
                f"(flip its side, or take it out).")
    if code == _UNSETTLED:
        return f"The straight run to {name(i)} could not be worked out: the contacts there lie too close together."
    return ""


# ---------------------------------------------------------------------------------------------------------
# the solver, all frames at once
# ---------------------------------------------------------------------------------------------------------

class _Chain:
    """The touching points of F frames x W wheels: angles ``t_in``/``t_out`` round each wheel (in its own u, v),
    places ``h_in``/``h_out`` along its axis from its centre, ``wrap``, and per frame ``code``/``bad``/``other``."""

    def __init__(self, starts, centres, axes, radii, sides, ends, on0: bool, on1: bool):
        self.S, self.E = starts, ends
        self.C, self.N = centres, axes
        self.r, self.sg = radii, sides
        self.F, self.W = centres.shape[0], centres.shape[1]
        self.on0, self.on1 = on0, on1
        F, W = self.F, self.W
        self.code = np.zeros(F, dtype=np.int64)
        self.bad = np.full(F, -1, dtype=np.int64)
        self.other = np.full(F, -3, dtype=np.int64)
        fine = np.isfinite(starts).all(axis=1) & np.isfinite(ends).all(axis=1)
        self._flag(~fine, _NUMBERS, -1, -3)
        with np.errstate(invalid="ignore"):
            long = np.linalg.norm(axes, axis=2)
            good = (np.isfinite(centres).all(axis=2) & np.isfinite(long) & (long > 1e-9)
                    & (np.isfinite(radii) & (radii > 0.0))[None, :])
        for i in range(W):
            self._flag(~good[:, i], _NUMBERS, i, -3)
        self.live = self.code == 0                       # frames that are worked on (the others: numbers kept tame)
        dead = ~self.live
        if dead.any():
            self.S = np.where(dead[:, None], 0.0, starts)
            self.E = np.where(dead[:, None], 1.0, ends)
            self.C = np.where(dead[:, None, None], np.arange(W, dtype=np.float64)[None, :, None] * 10.0, centres)
            self.N = np.where(dead[:, None, None], np.array([0.0, 0.0, 1.0]), axes)
            self.r = np.where(np.isfinite(radii) & (radii > 0.0), radii, 1.0)
        self.N = _unit(self.N)
        self.u, self.v = _square(self.N)
        self.t_in = np.zeros((F, W))
        self.t_out = np.zeros((F, W))
        self.h_in = np.zeros((F, W))
        self.h_out = np.zeros((F, W))
        self.wrap = np.zeros((F, W))
        if W:
            self._solve()

    # -- bookkeeping ----------------------------------------------------------------------------------

    def _flag(self, mask, code: int, i: int, j: int) -> None:
        """Frames in ``mask`` that have no problem yet get this one."""
        new = mask & (self.code == 0)
        if new.any():
            self.code[new], self.bad[new], self.other[new] = code, i, j

    def point(self, theta, h, i=slice(None)):
        """The point at angle ``theta`` round and ``h`` along wheel(s) ``i``."""
        c, s = np.cos(theta)[..., None], np.sin(theta)[..., None]
        return self.C[:, i] + h[..., None] * self.N[:, i] + self.r[i][..., None] * (c * self.u[:, i] + s * self.v[:, i])

    def _polar(self, q, i):
        """A point seen along the axis of wheel(s) ``i``: its angle and how far it is from the axis."""
        rel = q - self.C[:, i]
        x, y = _dot(rel, self.u[:, i]), _dot(rel, self.v[:, i])
        return np.arctan2(y, x), np.hypot(x, y)

    def _tangent(self, q, i, coming: bool):
        """The angle on wheel(s) ``i`` where the straight from the point q arrives (``coming``) or the straight
        to q leaves, and whether q lies inside the wheel's circle."""
        alpha, rho = self._polar(q, i)
        r = self.r[i]
        with np.errstate(divide="ignore", invalid="ignore"):
            beta = np.arccos(np.clip(r / rho, -1.0, 1.0))
        beta = np.where(rho > 0.0, beta, 0.0)
        turn = self.sg[i] * beta
        return (alpha + turn if coming else alpha - turn), rho < r - TOUCH

    # -- step 1: parallel neighbours ---------------------------------------------------------------------

    def _pairs(self):
        """Wheels with parallel axes next to each other: the common tangent of two circles (closed form)."""
        W = self.W
        self.run = np.zeros((self.F, max(W - 1, 0)))     # each such straight's length seen along the axis
        if W < 2:
            self.par = np.zeros(0, dtype=bool)
            return
        cos = _dot(self.N[:, :-1], self.N[:, 1:])
        sin = np.linalg.norm(np.cross(self.N[:, :-1], self.N[:, 1:]), axis=2)
        self.par = (sin[self.live] < PARALLEL).all(axis=0) if self.live.any() else np.ones(W - 1, dtype=bool)
        for i in np.flatnonzero(self.par):
            j = i + 1
            d = self.C[:, j] - self.C[:, i]
            dx, dy = _dot(d, self.u[:, i]), _dot(d, self.v[:, i])
            sa = float(self.sg[i])
            sb = self.sg[j] * np.where(cos[:, i] < 0.0, -1.0, 1.0)
            rho = sa * self.r[i] - sb * self.r[j]
            d2 = dx * dx + dy * dy
            dist = np.sqrt(d2)
            self._flag((dist < np.abs(rho) - TOUCH) | (dist < 1e-12), _OVERLAP, j, i)
            run = np.sqrt(np.maximum(d2 - rho * rho, 0.0))
            safe = np.where(d2 > 0.0, d2, 1.0)
            tx, ty = (run * dx - rho * dy) / safe, (run * dy + rho * dx) / safe
            long = np.hypot(tx, ty)
            long = np.where(long > 0.0, long, 1.0)
            tx, ty = tx / long, ty / long
            self.run[:, i] = run
            self.t_out[:, i] = np.arctan2(-sa * tx, sa * ty)
            e = (sb * ty)[:, None] * self.u[:, i] - (sb * tx)[:, None] * self.v[:, i]
            self.t_in[:, j] = np.arctan2(_dot(e, self.v[:, j]), _dot(e, self.u[:, j]))

    def _wraps(self, t_in, t_out):
        """How far round each wheel, counted so that a wheel the cable just misses gives a little less than
        nothing (and not nearly a whole turn): the steps below stay smooth there."""
        return np.mod(self.sg[None, :] * (t_out - t_in) + _SLACK, 2.0 * np.pi) - _SLACK

    # -- steps 2 and 3 ------------------------------------------------------------------------------------

    def _state(self, t):
        """Everything that follows from the directions ``t`` (F, K, 3) of the straights between the groups:
        the angles and places where those straights touch, every wheel's wrap, each group's two fixed points
        (length seen along its axis, place along it) and how far the straights are from fitting (F, 2K)."""
        F, W, K = self.F, self.W, len(self.A)
        t_in, t_out = self.t_in.copy(), self.t_out.copy()
        slope_in = slope_out = run = None
        z_a, z_b = self.z_start.copy(), self.z_end.copy()        # (F, G): the fixed point before / after
        if K:
            A, B = self.A, self.B
            na, nb = self.N[:, A], self.N[:, B]
            wa, wb = np.cross(t, na), np.cross(t, nb)
            la, lb = np.linalg.norm(wa, axis=2), np.linalg.norm(wb, axis=2)
            la, lb = np.where(la > 1e-12, la, 1.0), np.where(lb > 1e-12, lb, 1.0)
            ea = wa * (self.sg[A] / la)[..., None]
            eb = wb * (self.sg[B] / lb)[..., None]
            t_out[:, A] = np.arctan2(_dot(ea, self.v[:, A]), _dot(ea, self.u[:, A]))
            t_in[:, B] = np.arctan2(_dot(eb, self.v[:, B]), _dot(eb, self.u[:, B]))
            # where along the two axes the straight touches, and its length: three numbers, three equations
            gap = (self.C[:, B] + self.r[B][:, None] * eb) - (self.C[:, A] + self.r[A][:, None] * ea)
            det = _dot(na, wb)                           # na . (t x nb): Cramer's rule for [na, -nb, t]
            flat = ~(np.abs(det) > 1e-12)
            det = np.where(flat, np.nan, det)
            ha = _dot(gap, wb) / det
            hb = _dot(gap, wa) / det
            run = _dot(gap, np.cross(nb, na)) / det
            ng_out, ng_in = self.N[:, self.first[:-1]], nb     # the axes of the groups the straight leaves / enters
            slope_out = _dot(t, ng_out) / np.where(la > 0.0, la, 1.0)
            slope_in = _dot(t, ng_in) / lb
            z_b[:, :-1] = _dot(self.C[:, A], ng_out) + ha * _dot(na, ng_out)
            z_a[:, 1:] = _dot(self.C[:, B], ng_in) + hb
        wrap = self._wraps(t_in, t_out)
        arcs = self.r[None, :] * wrap
        upto = np.cumsum(arcs, axis=1)
        if W > 1:
            upto[:, 1:] += np.cumsum(self.run, axis=1)
        u_out = upto - (upto - arcs)[:, self.first][:, self.group]      # from the group's first touching point
        u_in = u_out - arcs
        span = u_out[:, self.last] + self.tail + self.lead               # (F, G) between the two fixed points
        res = np.zeros((F, 2 * K))
        if K:
            rise = z_b - z_a
            res[:, 0] = slope_out[:, 0] * span[:, 0] - rise[:, 0]
            res[:, -1] = slope_in[:, -1] * span[:, -1] - rise[:, -1]
            if K > 1:
                res[:, 1:-1:2] = slope_in[:, :-1] - slope_out[:, 1:]
                res[:, 2:-1:2] = 0.5 * (slope_in[:, :-1] + slope_out[:, 1:]) * span[:, 1:-1] - rise[:, 1:-1]
        return {"t_in": t_in, "t_out": t_out, "wrap": wrap, "u_in": u_in, "u_out": u_out, "span": span,
                "z_a": z_a, "z_b": z_b, "run": run, "res": res}

    def _first_guess(self):
        """Directions of the straights between the groups to start from: two rounds of 'the tangent from the
        other wheel's touching point' in the planes of the centres, and for wheels that touch each other the
        way the cable runs where it leaves the first."""
        A, B = self.A, self.B
        zero = np.zeros((self.F, len(A)))
        t_out, _ = self._tangent(self.C[:, B], A, False)
        for _ in range(2):
            p_out = self.point(t_out, zero, A)
            t_in, _ = self._tangent(p_out, B, True)
            p_in = self.point(t_in, zero, B)
            t_out, _ = self._tangent(p_in, A, False)
        p_out = self.point(t_out, zero, A)
        e = np.cos(t_out)[..., None] * self.u[:, A] + np.sin(t_out)[..., None] * self.v[:, A]
        along = np.cross(self.N[:, A], e) * self.sg[A][:, None]
        size = (self.r[A] + self.r[B])[:, None]
        return _unit(p_in - p_out + 1e-3 * size * along)

    def _solve(self):
        F, W = self.F, self.W
        self._pairs()
        cuts = np.flatnonzero(~self.par)
        self.first = np.concatenate([[0], cuts + 1]).astype(np.int64)     # each group's first and last wheel
        self.last = np.concatenate([cuts, [W - 1]]).astype(np.int64)
        G = len(self.first)
        self.group = np.repeat(np.arange(G), self.last - self.first + 1)
        self.A, self.B = self.last[:-1], self.first[1:]                   # straight k: wheel A[k] -> wheel B[k]
        K = G - 1
        # the two ends: a point (the tangent from it) or a place on the wheel itself
        inside0 = inside1 = np.zeros(F, dtype=bool)
        self.lead = np.zeros((F, G))                     # the straights before / after a group, seen along its axis
        self.tail = np.zeros((F, G))
        self.z_start = np.zeros((F, G))
        self.z_end = np.zeros((F, G))
        if self.on0:
            self.t_in[:, 0], _ = self._polar(self.S, 0)
        else:
            self.t_in[:, 0], inside0 = self._tangent(self.S, 0, True)
            _, rho = self._polar(self.S, 0)
            self.lead[:, 0] = np.sqrt(np.maximum(rho * rho - self.r[0] ** 2, 0.0))
        if self.on1:
            self.t_out[:, -1], _ = self._polar(self.E, W - 1)
        else:
            self.t_out[:, -1], inside1 = self._tangent(self.E, W - 1, False)
            _, rho = self._polar(self.E, W - 1)
            self.tail[:, -1] = np.sqrt(np.maximum(rho * rho - self.r[-1] ** 2, 0.0))
        self.z_start[:, 0] = _dot(self.S, self.N[:, 0])
        self.z_end[:, -1] = _dot(self.E, self.N[:, self.first[-1]])
        self._flag(inside0, _INSIDE, 0, -1)
        self._flag(inside1, _INSIDE, W - 1, -2)

        t = np.zeros((F, 0, 3))
        late = np.zeros(F, dtype=bool)
        if K:                                            # step 3: Newton on the straights' directions
            t = self._first_guess()
            rows = np.concatenate([[0], np.repeat(np.arange(1, K), 2), [K]]) if K > 1 else np.array([0, 1])
            feels = (rows[:, None] == np.arange(K)[None, :]) | (rows[:, None] == np.arange(K)[None, :] + 1)
            reach = np.linalg.norm(self.C[:, self.B] - self.C[:, self.A], axis=2) + (self.r[self.A] + self.r[self.B])
            step = np.full(F, np.inf)
            for _ in range(ROUNDS):
                st = self._state(t)
                e1, e2 = _square(t)
                jac = np.zeros((F, 2 * K, 2 * K))
                for parity in (0, 1):                    # straights two apart share no group: nudged together
                    cols = np.arange(parity, K, 2)
                    if not len(cols):
                        continue
                    for k, e in enumerate((e1, e2)):
                        tt = t.copy()
                        tt[:, cols] = _unit(t[:, cols] + _NUDGE * e[:, cols])
                        diff = (self._state(tt)["res"] - st["res"]) / _NUDGE
                        jac[:, :, 2 * cols + k] = diff[:, :, None] * feels[None, :, cols]
                res = st["res"]
                wild = ~(np.isfinite(jac).all(axis=(1, 2)) & np.isfinite(res).all(axis=1))
                jac[wild] = np.eye(2 * K)
                res = np.where(wild[:, None], 0.0, res)
                try:
                    dx = np.linalg.solve(jac, -res[:, :, None])[:, :, 0]
                except np.linalg.LinAlgError:
                    dx = np.stack([np.linalg.lstsq(j, -r, rcond=None)[0] for j, r in zip(jac, res)])
                dx = dx.reshape(F, K, 2)
                big = np.abs(dx).max(axis=(1, 2))
                dx = dx * np.minimum(1.0, 0.5 / np.where(big > 0.0, big, 1.0))[:, None, None]
                t = _unit(t + dx[..., :1] * e1 + dx[..., 1:] * e2)
                step = np.where(wild, np.inf, (np.abs(dx).max(axis=2) * reach).max(axis=1))
                if not (step[self.live] > SETTLED).any():
                    break
            late = ~(step < GOOD_ENOUGH)
        st = self._state(t)
        self.t_in, self.t_out = st["t_in"], st["t_out"]
        wrap = st["wrap"]
        # step 2: along each group's axis the cable rises evenly between the group's two fixed points
        span = np.where(st["span"] > 0.0, st["span"], 1.0)
        rate = ((st["z_b"] - st["z_a"]) / span)[:, self.group]
        z0, lead = st["z_a"][:, self.group], self.lead[:, self.group]
        ng = self.N[:, self.first][:, self.group]
        turned = np.where(_dot(self.N, ng) < 0.0, -1.0, 1.0)
        base = _dot(self.C, ng)
        self.h_in = (z0 + rate * (lead + st["u_in"]) - base) * turned
        self.h_out = (z0 + rate * (lead + st["u_out"]) - base) * turned
        if self.on0:                                     # a start on the wheel stays where it was put
            self.h_in[:, 0] = _dot(self.S - self.C[:, 0], self.N[:, 0])
        if self.on1:
            self.h_out[:, -1] = _dot(self.E - self.C[:, -1], self.N[:, -1])
        self.wrap = np.where((wrap < 0.0) & (wrap > -NO_WRAP), 0.0, wrap)      # rounding: no wrap at all
        every = np.arange(W)
        self.p_in = self.point(self.t_in, self.h_in, every)
        self.p_out = self.point(self.t_out, self.h_out, every)
        with np.errstate(invalid="ignore"):
            wild = ~(np.isfinite(self.p_in).all(axis=(1, 2)) & np.isfinite(self.p_out).all(axis=(1, 2)))
        for k in range(K):
            with np.errstate(invalid="ignore"):
                self._flag(st["run"][:, k] < -TOUCH, _OVERLAP, int(self.B[k]), int(self.A[k]))
        if K:
            worst = int(self.B[0])
            self._flag(wild | late, _UNSETTLED, worst, -3)
        else:
            self._flag(wild, _NUMBERS, 0, -3)
        for i in range(W):
            with np.errstate(invalid="ignore"):
                self._flag((self.wrap[:, i] > MAX_WRAP) | (self.wrap[:, i] < 0.0), _WRAP, i, -3)
        self.wrap = np.clip(np.nan_to_num(self.wrap), 0.0, 2.0 * np.pi)
        self.ok = self.code == 0

    # -- the drawn line ---------------------------------------------------------------------------------

    def lengths(self):
        """Per frame the pieces' lengths: W + 1 straights (0 for an end on a wheel) and W arcs."""
        F, W = self.F, self.W
        runs = np.zeros((F, W + 1))
        if W == 0:
            runs[:, 0] = np.linalg.norm(self.E - self.S, axis=1)
            return runs, np.zeros((F, 0))
        if not self.on0:
            runs[:, 0] = np.linalg.norm(self.p_in[:, 0] - self.S, axis=1)
        runs[:, 1:W] = np.linalg.norm(self.p_in[:, 1:] - self.p_out[:, :-1], axis=2)
        if not self.on1:
            runs[:, W] = np.linalg.norm(self.E - self.p_out[:, -1], axis=1)
        arcs = np.hypot(self.r[None, :] * self.wrap, self.h_out - self.h_in)
        return runs, arcs

    def polyline(self, counts):
        """Points (F, n, 3), lengths along them (F, n) and each wheel's first index, ``counts[i]`` points on arc i."""
        F, W = self.F, self.W
        runs, arcs = self.lengths()
        lead = 0 if (W and self.on0) else 1
        tail = 0 if (W and self.on1) else 1
        first = lead + np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int64) if W else np.zeros(0, np.int64)
        n = lead + int(np.sum(counts)) + tail
        pts = np.zeros((F, n, 3))
        s = np.zeros((F, n))
        at = np.zeros(F)
        if lead:
            pts[:, 0] = self.S
        for i in range(W):
            at = at + runs[:, i]
            tau = np.linspace(0.0, 1.0, int(counts[i]))[None, :]
            theta = self.t_in[:, i, None] + self.sg[i] * self.wrap[:, i, None] * tau
            h = self.h_in[:, i, None] + (self.h_out[:, i] - self.h_in[:, i])[:, None] * tau
            k = slice(int(first[i]), int(first[i]) + int(counts[i]))
            pts[:, k] = (self.C[:, i, None, :] + h[..., None] * self.N[:, i, None, :] + self.r[i]
                         * (np.cos(theta)[..., None] * self.u[:, i, None, :] + np.sin(theta)[..., None] * self.v[:, i, None, :]))
            s[:, k] = at[:, None] + arcs[:, i, None] * tau
            at = at + arcs[:, i]
        if tail:
            pts[:, -1] = self.E
            s[:, -1] = at + runs[:, W]
        return pts, s, first


def point_counts(wrap_max, step: float = STEP, least: int = 2) -> list[int]:
    """Points per arc for wraps up to ``wrap_max`` (rad, one per wheel): one every ``step``, at least ``least``."""
    w = np.atleast_1d(np.asarray(wrap_max, dtype=np.float64))
    w = np.where(np.isfinite(w), np.clip(w, 0.0, 2.0 * np.pi), 0.0)
    return [int(max(least, 2, math.ceil(float(x) / step - 1e-9) + 1)) for x in w]


def _counts(counts, wrap, step, W: int) -> np.ndarray:
    if counts is None:
        return np.array(point_counts(wrap, step), dtype=np.int64).reshape(W)
    c = np.asarray(counts, dtype=np.int64).reshape(-1)
    if len(c) != W:
        raise ValueError("counts: one number per wheel")
    return np.maximum(c, 2)


def _arrays(wheels):
    W = len(wheels)
    c = np.array([np.asarray(w.centre, dtype=np.float64).reshape(3) for w in wheels]).reshape(W, 3)
    a = np.array([np.asarray(w.axis, dtype=np.float64).reshape(3) for w in wheels]).reshape(W, 3)
    r = np.array([float(w.radius) for w in wheels], dtype=np.float64)
    s = np.array([-1.0 if w.side < 0 else 1.0 for w in wheels], dtype=np.float64)
    return c, a, r, s


def _one(start, wheels, end, on0: bool, on1: bool) -> _Chain:
    c, a, r, s = _arrays(wheels)
    W = len(wheels)
    return _Chain(np.asarray(start, dtype=np.float64).reshape(1, 3), c[None], a[None], r, s,
                  np.asarray(end, dtype=np.float64).reshape(1, 3), bool(on0) and W > 0, bool(on1) and W > 0)


def _path(ch: _Chain, counts, step, name=_number) -> Path:
    W = ch.W
    if ch.code[0]:
        return Path(False, _sentence(int(ch.code[0]), int(ch.bad[0]), int(ch.other[0]), name), int(ch.bad[0]),
                    np.zeros((0, 3)), np.zeros(0), np.zeros(W, dtype=np.int64), np.zeros(W), 0.0,
                    np.zeros(W, dtype=np.int64))
    cnt = _counts(counts, ch.wrap[0], step, W)
    pts, s, first = ch.polyline(cnt)
    return Path(True, "", -1, pts[0], s[0], first, ch.wrap[0].copy(), float(s[0, -1]), cnt)


def solve(start, wheels: list[Wheel], end, start_on_wheel: bool = False, end_on_wheel: bool = False,
          counts: list[int] | None = None, step: float = STEP) -> Path:
    """The cable from ``start`` over the wheels to ``end`` (see the module's text).

    ``start_on_wheel`` / ``end_on_wheel``: the point lies on the first / last wheel (it is put on its circle) and
    the arc starts / ends there: no straight run and no extra point on that side, so ``points[0]`` is the first
    arc's first point. ``counts``: points per arc (default: one every ``step``, at least 2). No wheels: a straight
    line. Never raises on a path that cannot be: ``ok`` is False, ``problem`` says why, ``points`` is empty."""
    return _path(_one(start, wheels, end, start_on_wheel, end_on_wheel), counts, step)


def solve_frames(starts, centres, axes, radii, sides, ends, start_on_wheel: bool = False,
                 end_on_wheel: bool = False, counts=None, step: float = STEP) -> dict:
    """``solve`` for F frames at once: starts (F, 3), centres (F, W, 3), axes (F, W, 3), radii (W,), sides (W,),
    ends (F, 3). Returns {"points": (F, n, 3), "s": (F, n), "wrap": (F, W), "length": (F,), "first": (W,),
    "counts": (W,), "ok": (F,), "bad": (F,), "problems": {frame: text}}.

    Every frame has the same number of points: ``counts`` per arc, by default enough for the widest wrap any
    frame has. A frame without a path (``ok`` False) keeps the shape of the last frame before it that has one (the
    first ones: of the first that has); with no good frame at all the points are 0."""
    starts = np.asarray(starts, dtype=np.float64).reshape(-1, 3)
    F = len(starts)
    radii = np.asarray(radii, dtype=np.float64).reshape(-1)
    W = len(radii)
    centres = np.asarray(centres, dtype=np.float64).reshape(F, W, 3)
    axes = np.asarray(axes, dtype=np.float64).reshape(F, W, 3)
    sides = np.where(np.asarray(sides, dtype=np.float64).reshape(W) < 0.0, -1.0, 1.0)
    ends = np.asarray(ends, dtype=np.float64).reshape(F, 3)
    ch = _Chain(starts, centres, axes, radii, sides, ends, bool(start_on_wheel) and W > 0, bool(end_on_wheel) and W > 0)
    ok = ch.code == 0
    widest = ch.wrap[ok].max(axis=0) if ok.any() else np.zeros(W)
    cnt = _counts(counts, widest, step, W)
    pts, s, first = ch.polyline(cnt)
    wrap = ch.wrap.copy()
    if not ok.all():
        if ok.any():
            good = np.flatnonzero(ok)
            last = np.maximum.accumulate(np.where(ok, np.arange(F), -1))
            take = np.where(last >= 0, last, good[0])
            pts, s, wrap = pts[take], s[take], wrap[take]
        else:
            pts, s, wrap = np.zeros_like(pts), np.zeros_like(s), np.zeros_like(wrap)
    problems = {int(f): _sentence(int(ch.code[f]), int(ch.bad[f]), int(ch.other[f])) for f in np.flatnonzero(~ok)}
    return {"points": pts, "s": s, "wrap": wrap, "length": s[:, -1].copy(), "first": first, "counts": cnt,
            "ok": ok, "bad": ch.bad.copy(), "problems": problems}


def tightest(wheels, wrap, least_wrap: float = math.radians(1.0)) -> tuple[int, float]:
    """(index, radius) of the tightest bend among the wheels the cable really goes round (a wrap of at least
    ``least_wrap``); (-1, inf) when there is none."""
    best, radius = -1, math.inf
    for i, (w, a) in enumerate(zip(wheels, np.atleast_1d(wrap))):
        if a >= least_wrap and float(w.radius) < radius:
            best, radius = i, float(w.radius)
    return best, radius


# ---------------------------------------------------------------------------------------------------------
# what turns, and the look's numbers
# ---------------------------------------------------------------------------------------------------------

def wheel_ratio(radius: float, side: int, axis, joint_axis, reverse: bool = False) -> float:
    """Degrees a wheel's joint turns per **mm** of cable that runs over it (start -> end), signed.

    ``radius`` (m): where the cable's speed is the wheel's rim speed – the cable's middle on a sheave, the
    surface of a roller. The wheel turns about +axis when ``side`` is +1; the joint counts about ``joint_axis``;
    ``reverse``: the cable's joint counts the other way (end -> start)."""
    sign = (1.0 if side >= 0 else -1.0) * (1.0 if float(np.dot(axis, joint_axis)) >= 0.0 else -1.0)
    if reverse:
        sign = -sign
    return sign * 360.0 / (2.0 * math.pi * float(radius) * 1000.0)


def stripes(diameter: float, pitch: float, angle: float) -> int:
    """How many stripes (strands) go round a cable: the nearest whole number to π·d / (pitch · tan(angle)).

    ``pitch``: from one stripe to the next along the cable; ``angle`` (rad): between a stripe and the cable's
    length – 90° gives 0 (rings round the cable), a negative angle the other hand."""
    t = math.tan(max(min(float(angle), 0.5 * math.pi), -0.5 * math.pi))
    if abs(t) > 1e9 or not pitch > 0.0:
        return 0
    if abs(t) < 1e-6:
        t = math.copysign(1e-6, t if t else 1.0)
    return int(round(math.pi * float(diameter) / (float(pitch) * t)))


def stripe_angle(diameter: float, pitch: float, starts: int) -> float:
    """The angle (rad) between a stripe and the cable's length for ``starts`` stripes round it: 0 starts = 90°."""
    if starts == 0:
        return 0.5 * math.pi
    return math.atan(math.pi * float(diameter) / (float(starts) * float(pitch)))


# ---------------------------------------------------------------------------------------------------------
# the surface a cable rests on
# ---------------------------------------------------------------------------------------------------------

SEAT_FINE = 64.0                # the outline is read in steps of the cable's radius / this along the axis
ROUND_SECTORS = 6               # is_round: the part is looked at in this many sectors round the axis …
ROUND_SLICES = 12               # … and this many slices along it
ROUND_TOL = 0.02                # … whose outer radii agree within this share of the part's radius


def _outline(verts, tris, centre, axis, lo: float, hi: float, dz: float):
    """The part's outer outline between the axial places ``lo`` and ``hi`` (m from centre along axis): arrays
    (place, radius), one point per ``dz`` of the axis where the part is, each a real point of the mesh.

    Only the triangles' edges are walked: on a flat triangle the point furthest from the axis at one place along
    it lies on an edge (the distance from a line is a convex function)."""
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3).astype(np.int64)
    empty = np.zeros(0), np.zeros(0)
    if not len(v) or not len(t) or not hi > lo:
        return empty
    a = _unit(np.asarray(axis, dtype=np.float64).reshape(3))
    rel = v - np.asarray(centre, dtype=np.float64).reshape(3)
    z = rel @ a
    flat = rel - np.outer(z, a)
    pair = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [0, 2]]])
    m = len(v)
    key = np.unique(pair.min(axis=1) * m + pair.max(axis=1))
    i, j = key // m, key % m
    near = (np.maximum(z[i], z[j]) >= lo) & (np.minimum(z[i], z[j]) <= hi)
    i, j = i[near], j[near]
    if not len(i):
        return empty
    dzz = z[j] - z[i]
    with np.errstate(divide="ignore", invalid="ignore"):   # the part of each edge between lo and hi
        f0 = np.where(dzz != 0.0, (lo - z[i]) / dzz, 0.0)
        f1 = np.where(dzz != 0.0, (hi - z[i]) / dzz, 1.0)
    fa = np.clip(np.minimum(f0, f1), 0.0, 1.0)
    fb = np.clip(np.maximum(f0, f1), 0.0, 1.0)
    level = dzz == 0.0
    fa, fb = np.where(level, 0.0, fa), np.where(level, 1.0, fb)
    count = np.minimum(np.ceil(np.abs(dzz) * (fb - fa) / dz).astype(np.int64) + 1, 100_000)
    count = np.maximum(count, 2)
    total = int(count.sum())
    if total > 20_000_000:
        return empty
    edge = np.repeat(np.arange(len(i)), count)
    step = np.arange(total) - np.repeat(np.cumsum(count) - count, count)
    f = fa[edge] + (fb - fa)[edge] * step / (count[edge] - 1)
    zs = z[i][edge] + f * dzz[edge]
    rs = np.linalg.norm(flat[i][edge] + f[:, None] * (flat[j] - flat[i])[edge], axis=1)
    # the outermost point of every step along the axis
    box = np.clip(np.floor((zs - lo) / dz).astype(np.int64), 0, int(math.ceil((hi - lo) / dz)))
    order = np.lexsort((rs, box))
    top = np.r_[box[order][1:] != box[order][:-1], True]
    keep = order[top]
    return zs[keep], rs[keep]


def _rest(zs, rs, at, rope: float):
    """How far from the axis the middle of a round section of radius ``rope`` is when it rests on the outline at
    the axial places ``at`` (array): the outline grown by the section."""
    at = np.atleast_1d(np.asarray(at, dtype=np.float64))
    out = np.zeros(len(at))
    for k in range(0, len(at), 256):                     # in blocks: places x outline points
        d = zs[None, :] - at[k:k + 256, None]
        with np.errstate(invalid="ignore"):
            up = rs[None, :] + np.sqrt(rope * rope - d * d)
        up = np.where(np.abs(d) <= rope, up, -np.inf)
        best = up.max(axis=1)
        out[k:k + 256] = np.where(np.isfinite(best), best, 0.0)
    return out


def _seat(verts, tris, centre, axis, at: float, rope: float, search: float | None = None):
    """``seat`` and the radius of the surface where the cable touches it: (place, radius, touching radius)."""
    rope = float(rope)
    at = float(at)
    if not rope > 0.0 or not math.isfinite(at):
        return at, 0.0, 0.0
    search = rope if search is None else max(float(search), 0.0)
    zs, rs = _outline(verts, tris, centre, axis, at - search - rope, at + search + rope, rope / SEAT_FINE)
    if not len(zs):
        return at, 0.0, 0.0
    here = float(_rest(zs, rs, at, rope)[0])
    place, radius = at, here
    if search > 0.0:
        # a groove: the lowest place in reach, if the cable can sink into it (a dip with a way up on both sides –
        # not the lower end of a slope, as on a crowned or coned roller)
        lo, hi = at - search, at + search
        for _ in range(3):
            grid = np.linspace(lo, hi, 129)
            rest = _rest(zs, rs, grid, rope)
            low = float(rest.min())
            dips = np.flatnonzero(rest <= low + 1e-12)
            k = int(dips[np.argmin(np.abs(grid[dips] - at))])
            lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, 128)]
            if not 0 < k < 128:
                break
        else:
            if rest[k] < here - 1e-9 and rest[k] > 0.0:
                place, radius = float(grid[k]), float(rest[k])
    if not radius > 0.0:
        return at, 0.0, 0.0
    d = zs - place
    with np.errstate(invalid="ignore"):
        up = np.where(np.abs(d) <= rope, rs + np.sqrt(rope * rope - d * d), -np.inf)
    return place, radius, float(rs[up >= radius - 1e-6].mean())


def seat(verts, tris, centre, axis, at: float, rope_radius: float, search: float | None = None) -> tuple[float, float]:
    """Where a cable of ``rope_radius`` rests on a round part near the axial place ``at`` (m from ``centre`` along
    ``axis``): (place along the axis, radius from the axis to the cable's middle).

    In a groove that is the lowest place the cable can sink to within ``search`` (default: its own radius) along
    the axis: the groove's bottom + the cable's radius in a round groove, on both flanks in a V groove. On a
    plain, crowned or coned roller it is where the cable is: the surface at ``at`` + the cable's radius (the
    cable does not slide down a slope). (at, 0.0) when the part has no surface there."""
    place, radius, _ = _seat(verts, tris, centre, axis, at, rope_radius, search)
    return place, radius


def surface_radius(verts, tris, centre, axis, at: float, width: float) -> float:
    """The part's outer radius within ``width`` (in all) round the axial place ``at``; 0.0 when it is not there."""
    half = 0.5 * max(float(width), 1e-9)
    zs, rs = _outline(verts, tris, centre, axis, float(at) - half, float(at) + half, 2.0 * half / 16.0)
    return float(rs.max()) if len(rs) else 0.0


def is_round(verts, centre, axis) -> bool:
    """True when the mesh is round all the way about this axis (a roller, a sheave, a drum: it may turn); False
    for a part that is round over a part of the turn only (a chute, a quadrant's gutter) or not at all.

    The corners are sorted into 6 sectors round the axis and 12 slices along it; in every slice all sectors
    must reach as far out (within 2 % of the part's radius). Holes, spokes and keyways inside do not matter."""
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    if len(v) < 2 * ROUND_SECTORS:
        return False
    a = _unit(np.asarray(axis, dtype=np.float64).reshape(3))
    u, w = _square(a)
    rel = v - np.asarray(centre, dtype=np.float64).reshape(3)
    z = rel @ a
    x, y = rel @ u, rel @ w
    rho = np.hypot(x, y)
    big = float(rho.max())
    if not big > 0.0 or not np.isfinite(big):
        return False
    outer = rho > 0.5 * big
    start = float(np.arctan2(y[outer], x[outer]).min())  # a sector starts just before a corner
    sector = np.floor(np.mod(np.arctan2(y, x) - start + 1e-6, 2.0 * np.pi) / (2.0 * np.pi / ROUND_SECTORS))
    sector = np.clip(sector.astype(np.int64), 0, ROUND_SECTORS - 1)
    z0, z1 = float(z.min()), float(z.max())
    slices = 1 if z1 - z0 < 1e-9 * big else ROUND_SLICES
    k = np.clip(np.floor((z - z0) / max(z1 - z0, 1e-300) * slices).astype(np.int64), 0, slices - 1)
    reach = np.zeros((slices, ROUND_SECTORS))
    np.maximum.at(reach, (k, sector), rho)
    used = reach.max(axis=1) > 0.0
    even = reach.max(axis=1) - reach.min(axis=1) <= ROUND_TOL * big
    return bool(used.any() and even[used].all())
