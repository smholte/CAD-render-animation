"""Cable paths: a cable over sheaves, rollers, chutes and bends, without Blender (task 0078).

A cable's centreline is a chain of **straight runs and arcs**. Every arc lies on a **wheel**: a point on its axis,
the axis, the radius to the cable's *middle*, and the side the cable goes round it: +1 when it turns about +axis
(right hand), -1 about -axis. Metres, radians, NumPy only.

**The solver** (``solve``, ``solve_frames``) draws the cable from a start over the wheels to an end, in one of
two ways (``held``):

*Held* (True): every arc lies in the plane square to its wheel's axis through the wheel's centre – a rope in a
groove, a bend as it was drawn. Each straight stands for itself: from a point it is the tangent to the circle;
between wheels with parallel axes the common tangent of the two circles seen along the axis (outer when the
cable goes round both the same way, crossing when not: a closed form, also when the circles just touch – an S
without a straight between its arcs); between wheels whose axes are not parallel the line that touches both
circles' cylinders at the circles (Newton on the line's direction). A straight that lies in both planes meets
its arcs without a kink; one that leaves a plane (a fleet angle) meets the arc there with a kink of that angle,
as a rope does on a groove's flank.

*Free* (False): the wheels are plain cylinders and the cable is a tight string: straight between the wheels,
and on a wheel a helix when it does not come and go square to the axis (the angle round the wheel and the place
along its axis rise evenly), so there is no kink anywhere and the wheel's centre may be any point on its axis.
Wheels with parallel axes that follow each other form a group: seen along the axis the tangents are the closed
forms above, and along the axis the cable rises evenly with its length seen along the axis (unrolled, a string
on a cylinder is a straight line). The straights between groups are found together by Newton on their
directions (two numbers each) until no touching point moves more than 1e-12 m.

*By itself* (None, the default): held when no straight then leaves a wheel's plane by more than 0.1° – a path as
CAD drew it stays exactly as drawn, and a misfit of a hair in one wheel does not travel down the whole cable –
and free when one does (a fleet angle, or centres that are just any point on their axes).

A path that cannot be is refused in plain words, never drawn broken: a point or a wheel inside another wheel's
circle, wheels that overlap so that no straight fits between them, a wheel the cable would have to go round by
more than 350° (it passes it on the other side), numbers that are not numbers. Circles that overlap by less than
``TOUCH`` (0.1 mm: places kept in 32-bit numbers) count as touching.

``solve_frames`` does the same for many frames at once (arrays over the frames, no Python loop over them) with the
same number of points on every frame; a frame that has no path keeps the shape of the last frame that had one.

**A wheel the cable leaves** (a sheave that sinks away under it) is **lifted off**: the cable passes it straight,
its wrap is 0 and its points lie where the straight passes nearest its axis, so the number of points stays.
Geometry alone cannot tell this from a cable that goes nearly all the way round (the tangents are the same
lines): what tells is where the wrap comes from. Along the frames a wrap never jumps by more than half a turn,
so one that shrinks to nothing and would come back as nearly a whole turn is a lifted wheel; for one frame alone
the wraps of the CAD pose say it (``wraps0``). The path is then solved again without the lifted wheels.

**Reading a CAD cable** (``read_cable``): the centreline of a cable drawn in CAD (``centreline``) is cut into
straights and arcs, each arc is matched with the round part it lies on (a WRAP: centre, axis and radius then
come from the part), the others are bends in the air (BEND, the fitted circle), and round parts the cable only
rests on or runs past are TOUCH contacts. A reading whose path does not lie on the points is refused. See
``read_cable``.

**The surface a cable rests on** (``seat``, ``surface_radius``, ``is_round``): a round part's outline (radius
against the place along its axis) is read from the triangles' edges – on a flat triangle the point furthest from
the axis at any place along it lies on an edge, so a plain roller with corners only at its ends is read exactly –
and the cable's round section is let down onto it. Whether a part is round all the way (it may turn) is read
from the triangles of its outside, so holes, keyways and flats do not make a roller a chute.

**A long cable's centreline** (``centreline``): ``flex_fit.tube_centreline`` read in overlapping pieces, because
on its own it is made for hoses and loses a cable that is hundreds of radii long.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

TOUCH = 1e-4                    # m: circles that overlap by less than this touch (a straight of length 0)
PARALLEL = 1e-6                 # rad: axes this close to parallel are parallel (one group)
SETTLED = 1e-12                 # m: the rounds stop when no touching point moves more than this …
ROUNDS = 40                     # … or after this many rounds of Newton
GOOD_ENOUGH = 1e-9              # m: a frame that still moves less than this after all rounds is taken
MAX_WRAP = math.radians(350.0)  # further round a wheel than this: refused
NO_WRAP = 1e-6                  # rad: a wrap this much less than nothing is no wrap at all (rounding)
STEP = math.radians(4.0)        # points on an arc: one every 4°
MAX_STARTS = 64                 # at most this many stripes round a cable
_SLACK = math.radians(5.0)      # wraps are counted from -5° to 355°
_NUDGE = 1e-6                   # rad: the nudge that shows how a straight's direction matters
FLEET = math.sin(math.radians(0.1))     # a straight that leaves a wheel's plane by more than 0.1°: a fleet angle

_OK, _NUMBERS, _INSIDE, _OVERLAP, _WRAP, _UNSETTLED = 0, 1, 2, 3, 4, 5


@dataclass
class Wheel:
    centre: np.ndarray          # (3,) a point on the axis: in the plane the cable lies in there (held), or any (free)
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
    lifted: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))   # the wheels the cable does
    #                             not reach (indices): it passes them straight, their wrap is 0 (see ``solve``)


# ---------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------

def _dot(a, b):
    return np.einsum("...i,...i->...", a, b)


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 0.0, n, 1.0)


def _cross(a, b):
    """a x b for (…, 3) arrays (np.cross spends most of its time moving axes about)."""
    a, b = np.asarray(a), np.asarray(b)
    return np.stack([a[..., 1] * b[..., 2] - a[..., 2] * b[..., 1], a[..., 2] * b[..., 0] - a[..., 0] * b[..., 2],
                     a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]], axis=-1)


def _square(axis):
    """Two unit directions u, v square to each axis with u x v = axis."""
    least = np.argmin(np.abs(axis), axis=-1)
    if axis.ndim == 1:
        ref = np.zeros(3)
        ref[least] = 1.0
    else:
        ref = np.zeros_like(axis)
        np.put_along_axis(ref, least[..., None], 1.0, axis=-1)
    u = _unit(_cross(axis, ref))
    return u, _cross(axis, u)


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

    def __init__(self, starts, centres, axes, radii, sides, ends, on0: bool, on1: bool, held=None, ref=None,
                 lift: bool = False):
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
        self.raw = np.zeros((F, W))
        self.held = np.ones(F, dtype=bool)               # per frame: solved with the arcs in the wheels' planes
        self.lift = np.zeros((F, W), dtype=bool)         # per frame: wheels the cable no longer reaches
        if W:
            self._solve(held)
            if lift:
                self._lift(held, ref)

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
        sin = np.linalg.norm(_cross(self.N[:, :-1], self.N[:, 1:]), axis=2)
        self.par = (sin[self.live] < PARALLEL).all(axis=0) if self.live.any() else np.ones(W - 1, dtype=bool)
        self.level = sin < PARALLEL                      # per frame: which neighbours' axes are parallel just there
        for i in np.flatnonzero(self.par):
            j = i + 1
            d = self.C[:, j] - self.C[:, i]
            dx, dy = _dot(d, self.u[:, i]), _dot(d, self.v[:, i])
            sa = float(self.sg[i])
            sb = self.sg[j] * np.where(cos[:, i] < 0.0, -1.0, 1.0)
            rho = sa * self.r[i] - sb * self.r[j]
            d2 = dx * dx + dy * dy
            dist = np.sqrt(d2)
            self._flag(self.live & ((dist < np.abs(rho) - TOUCH) | (dist < 1e-12)), _OVERLAP, j, i)
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
            wa, wb = _cross(t, na), _cross(t, nb)
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
            run = _dot(gap, _cross(nb, na)) / det
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

    def _first_guess(self, A, B):
        """Directions of the straights from wheels A to wheels B to start from: two rounds of 'the tangent from
        the other wheel's touching point' in the planes of the centres, and for wheels that touch each other the
        way the cable runs where it leaves the first."""
        zero = np.zeros((self.F, len(A)))
        t_out, _ = self._tangent(self.C[:, B], A, False)
        for _ in range(2):
            p_out = self.point(t_out, zero, A)
            t_in, _ = self._tangent(p_out, B, True)
            p_in = self.point(t_in, zero, B)
            t_out, _ = self._tangent(p_in, A, False)
        p_out = self.point(t_out, zero, A)
        e = np.cos(t_out)[..., None] * self.u[:, A] + np.sin(t_out)[..., None] * self.v[:, A]
        along = _cross(self.N[:, A], e) * self.sg[A][:, None]
        size = (self.r[A] + self.r[B])[:, None]
        return _unit(p_in - p_out + 1e-3 * size * along)

    # -- arcs held in the wheels' planes ---------------------------------------------------------------------

    def _solve(self, held) -> None:
        """``held`` True: every arc in its wheel's plane; False: the tight string; None: the first, unless a
        straight then leaves a plane by more than 0.1° (or there is no such path): then the second."""
        if held is False:
            self.held[:] = False
            self._solve_free()
            return
        self._solve_held()
        if held is None:
            loose = self.live & ((self.code != 0) | (self.fleet > FLEET))
            if loose.any():
                self._again(loose, False)
        self.ok = self.code == 0

    def _again(self, frames, held) -> None:
        """Solve these frames (a mask) as a chain of their own and take what it gives."""
        sub = _Chain(self.S[frames], self.C[frames], self.N[frames], self.r, self.sg, self.E[frames], self.on0,
                     self.on1, held=held)
        for name in ("t_in", "t_out", "h_in", "h_out", "wrap", "raw", "p_in", "p_out", "code", "bad", "other", "held"):
            getattr(self, name)[frames] = getattr(sub, name)

    # -- a wheel the cable no longer reaches -----------------------------------------------------------------

    def _lift(self, held, ref) -> None:
        """Take the wheels out that the cable no longer reaches on their side, frame by frame.

        A wheel the cable has left shows as a wrap of nearly a whole turn (it would have to come back round the
        wheel). Which it is – a wide wrap or none – is told from a wrap the wheel is known to have: ``ref``, one
        per wheel (the wrap in the CAD pose) or one per frame and wheel, and, from frame to frame, the frame
        before: a wrap never jumps by more than half a turn. Counted on like that a wrap can fall below nothing:
        the wheel is lifted off. Those frames are solved again without their lifted wheels (which can lift more),
        and each lifted wheel's points are put where the straight passes nearest its axis. A frame that has no
        path at all is tried with the wheels lifted that the last frame before it had lifted."""
        F, W = self.F, self.W
        turn = 2.0 * np.pi
        solved = self.live & ((self.code == 0) | (self.code == _WRAP))
        raw = np.mod(np.nan_to_num(self.raw), turn)
        raw = np.where(raw > turn - NO_WRAP, 0.0, raw)
        frame = np.arange(F)
        last = np.maximum.accumulate(np.where(solved, frame, -1))        # the last frame with a path, up to here
        if ref is not None and np.ndim(ref) == 2:
            turns = raw - np.where(raw - ref > np.pi, turn, 0.0)
        else:
            back = np.zeros((F, W)) if ref is None else np.where(raw - np.asarray(ref)[None, :] > np.pi, -1.0, 0.0)
            filled = raw[np.maximum(last, 0)]
            step = np.diff(filled, axis=0, prepend=filled[:1])
            jump = np.where(step > np.pi, -1.0, np.where(step < -np.pi, 1.0, 0.0))
            fresh = solved & ~np.r_[False, solved[:-1]]                  # a run of frames with a path starts here
            jump[fresh] = 0.0
            count = np.cumsum(jump, axis=0)
            run = np.maximum(np.maximum.accumulate(np.where(fresh, frame, -1)), 0)
            turns = raw + turn * (count - count[run] + back[run])
        gone = solved[:, None] & (turns < -NO_WRAP)
        hope = self.live & ~solved & (last >= 0)
        gone[hope] = gone[last[hope]]
        hope &= gone.any(axis=1)
        turns[hope] = turns[last[hope]]
        gone[~(solved | hope)] = False
        over = self.code == _WRAP                        # the wraps are judged anew, counted on
        self.code[over], self.bad[over] = 0, -1
        for i in range(W):
            self._flag(solved & ~gone.any(axis=1) & (turns[:, i] > MAX_WRAP), _WRAP, i, -3)
        rows = np.flatnonzero(gone.any(axis=1))
        if len(rows):
            kinds, which = np.unique(gone[rows], axis=0, return_inverse=True)
            for k, pattern in enumerate(kinds):
                self._without(rows[np.ravel(which) == k], pattern, held, turns, hope)
        self.ok = self.code == 0

    def _on(self, frames, i: int, theta, h):
        c, s = np.cos(theta)[:, None], np.sin(theta)[:, None]
        ring = c * self.u[frames, i] + s * self.v[frames, i]
        return self.C[frames, i] + h[:, None] * self.N[frames, i] + self.r[i] * ring

    def _without(self, frames, gone, held, turns, hope) -> None:
        """Solve ``frames`` (indices) without the wheels ``gone`` (a mask) and put the result in their places."""
        W = self.W
        act = np.flatnonzero(~gone)
        start = self._on(frames, 0, self.t_in[frames, 0], self.h_in[frames, 0]) if (self.on0 and gone[0]) else self.S[frames]
        end = self._on(frames, W - 1, self.t_out[frames, -1], self.h_out[frames, -1]) if (self.on1 and gone[-1]) \
            else self.E[frames]
        if len(act):
            sub = _Chain(start, self.C[frames][:, act], self.N[frames][:, act], self.r[act], self.sg[act], end,
                         self.on0 and not gone[0], self.on1 and not gone[-1], held,
                         ref=np.clip(turns[frames][:, act], 0.0, None), lift=True)
            good = sub.code == 0
        else:
            sub, good = None, np.ones(len(frames), dtype=bool)
        take = ~hope[frames] | good                      # a frame that had no path only takes one
        fr = frames[take]
        if not len(fr):
            return
        if sub is not None:
            for name in ("t_in", "t_out", "h_in", "h_out", "wrap", "p_in", "p_out", "lift"):
                getattr(self, name)[fr[:, None], act[None, :]] = getattr(sub, name)[take]
            far = np.concatenate([act, [-1, -2, -3]])    # the smaller chain's numbers -> this chain's
            self.code[fr], self.held[fr] = sub.code[take], sub.held[take]
            self.bad[fr] = np.where(sub.bad[take] >= 0, far[sub.bad[take]], sub.bad[take])
            self.other[fr] = np.where(sub.other[take] >= 0, far[sub.other[take]], sub.other[take])
        else:
            self.code[fr], self.bad[fr], self.other[fr] = 0, -1, -3
        before = start[take]
        for i in range(W):
            if not gone[i]:
                before = self.p_out[fr, i]
                continue
            later = act[act > i]
            after = self.p_in[fr, later[0]] if len(later) else end[take]
            if (i == 0 and self.on0) or not np.isfinite(before).all():
                spot = before
            elif i == W - 1 and self.on1:
                spot = after
            else:                                        # where the straight passes nearest the wheel's axis
                d, n, w0 = after - before, self.N[fr, i], before - self.C[fr, i]
                a, b = _dot(d, d), _dot(d, n)
                den = a - b * b
                f = np.where(den > 1e-12 * np.maximum(a, 1e-300),
                             (b * _dot(n, w0) - _dot(d, w0)) / np.where(den > 0, den, 1.0), 0.5)
                spot = before + np.clip(f, 0.0, 1.0)[:, None] * d
            self.p_in[fr, i] = self.p_out[fr, i] = spot
            self.wrap[fr, i] = self.h_in[fr, i] = self.h_out[fr, i] = 0.0
            self.lift[fr, i] = True
            before = spot

    def _ends(self):
        """The two ends: a point (the tangent from it) or a place on the wheel itself. Returns how long the first
        and the last straight are, seen along their wheel's axis."""
        F, W = self.F, self.W
        lead, tail = np.zeros(F), np.zeros(F)
        if self.on0:
            self.t_in[:, 0], _ = self._polar(self.S, 0)
        else:
            self.t_in[:, 0], inside = self._tangent(self.S, 0, True)
            self._flag(inside, _INSIDE, 0, -1)
            _, rho = self._polar(self.S, 0)
            lead = np.sqrt(np.maximum(rho * rho - self.r[0] ** 2, 0.0))
        if self.on1:
            self.t_out[:, -1], _ = self._polar(self.E, W - 1)
        else:
            self.t_out[:, -1], inside = self._tangent(self.E, W - 1, False)
            self._flag(inside, _INSIDE, W - 1, -2)
            _, rho = self._polar(self.E, W - 1)
            tail = np.sqrt(np.maximum(rho * rho - self.r[-1] ** 2, 0.0))
        return lead, tail

    def _points(self, wrap):
        """The touching points from the angles and places; True per frame where they are not numbers."""
        self.raw = np.array(wrap, dtype=np.float64)
        self.wrap = np.where((wrap < 0.0) & (wrap > -NO_WRAP), 0.0, wrap)      # rounding: no wrap at all
        every = np.arange(self.W)
        self.p_in = self.point(self.t_in, self.h_in, every)
        self.p_out = self.point(self.t_out, self.h_out, every)
        with np.errstate(invalid="ignore"):
            return ~(np.isfinite(self.p_in).all(axis=(1, 2)) & np.isfinite(self.p_out).all(axis=(1, 2)))

    def _wrap_flags(self):
        for i in range(self.W):
            with np.errstate(invalid="ignore"):
                self._flag((self.wrap[:, i] > MAX_WRAP) | (self.wrap[:, i] < 0.0), _WRAP, i, -3)
        self.wrap = np.clip(np.nan_to_num(self.wrap), 0.0, 2.0 * np.pi)
        self.ok = self.code == 0

    def _solve_held(self):
        """Every arc in the plane through its wheel's centre. Each straight stands for itself: from a point
        the tangent to a circle, between parallel wheels the common tangent seen along the axis, between
        wheels whose axes are not parallel the line that touches both circles' cylinders at the circles."""
        self._pairs()
        self._ends()
        cross = np.flatnonzero(~self.par)
        if len(cross):
            self._between(cross, cross + 1)
        wild = self._points(self._wraps(self.t_in, self.t_out))
        self._flag(wild, _NUMBERS, 0, -3)
        self._wrap_flags()
        # how far the straights leave the planes of the wheels at their ends (the sine of the widest angle)
        a = np.concatenate([(self.p_in[:, :1] if self.on0 else self.S[:, None, :]), self.p_out], axis=1)
        b = np.concatenate([self.p_in, (self.p_out[:, -1:] if self.on1 else self.E[:, None, :])], axis=1)
        d = b - a
        long = np.linalg.norm(d, axis=2)
        d = d / np.where(long > 10.0 * TOUCH, long, np.inf)[..., None]
        with np.errstate(invalid="ignore"):
            self.fleet = np.nan_to_num(np.maximum(np.abs(_dot(d[:, :-1], self.N)).max(axis=1),
                                                  np.abs(_dot(d[:, 1:], self.N)).max(axis=1)), nan=1.0)

    def _between(self, A, B):
        """Held: the straights from circles A to circles B whose axes are not parallel. A straight of direction
        t touches a circle where the circle's radius is square to t; t is right when the step from the one
        touching point to the other runs along t (Newton on t's two numbers, every straight for itself).
        Circles that come within ``TOUCH`` of each other and have no such straight (they touch, or overlap by a
        hair) get a straight of no length where they are nearest."""
        na, nb = self.N[:, A], self.N[:, B]

        def touch(t):
            ea, eb = _cross(t, na), _cross(t, nb)
            la, lb = np.linalg.norm(ea, axis=2), np.linalg.norm(eb, axis=2)
            ea = ea * (self.sg[A] / np.where(la > 1e-12, la, 1.0))[..., None]
            eb = eb * (self.sg[B] / np.where(lb > 1e-12, lb, 1.0))[..., None]
            return ea, eb, (self.C[:, B] + self.r[B][:, None] * eb) - (self.C[:, A] + self.r[A][:, None] * ea)

        def nearest(t):
            """From the direction t: the direction at which the two touching points lie nearest to each other
            (a few damped least-squares steps), and how far apart they then are."""
            for _ in range(6):
                e1, e2 = _square(t)
                gap = touch(t)[2]
                d1 = (touch(_unit(t + _NUDGE * e1))[2] - gap) / _NUDGE
                d2 = (touch(_unit(t + _NUDGE * e2))[2] - gap) / _NUDGE
                a11, a12, a22 = _dot(d1, d1), _dot(d1, d2), _dot(d2, d2)
                b1, b2 = -_dot(d1, gap), -_dot(d2, gap)
                ridge = 1e-9 * (a11 + a22) + 1e-30
                a11, a22 = a11 + ridge, a22 + ridge
                det = a11 * a22 - a12 * a12
                x1, x2 = (b1 * a22 - b2 * a12) / det, (b2 * a11 - b1 * a12) / det
                big = np.maximum(np.abs(x1), np.abs(x2))
                scale = np.minimum(1.0, 0.3 / np.where(big > 0.0, big, 1.0))
                new = _unit(t + (x1 * scale)[..., None] * e1 + (x2 * scale)[..., None] * e2)
                closer = np.linalg.norm(touch(new)[2], axis=2) < np.linalg.norm(gap, axis=2)
                t = np.where(closer[..., None], new, t)
            return t, np.linalg.norm(touch(t)[2], axis=2)

        t = self._first_guess(A, B)
        reach = np.linalg.norm(self.C[:, B] - self.C[:, A], axis=2) + (self.r[A] + self.r[B])
        far, joined_t = np.full(t.shape[:2], np.inf), t
        if (reach - 2.0 * (self.r[A] + self.r[B]) < TOUCH).any():       # (else too far apart to touch anywhere)
            shared = _unit(_cross(na, nb))
            with np.errstate(invalid="ignore", divide="ignore"):
                for way in (shared, -shared, t):
                    way, apart = nearest(way)
                    apart = np.where(np.isfinite(apart), apart, np.inf)
                    joined_t = np.where((apart < far)[..., None], way, joined_t)
                    far = np.minimum(apart, far)
        joined = far < TOUCH
        step = np.full(far.shape, np.inf)
        busy = self.live[:, None] & ~(far < 1e-9)        # (circles that touch exactly have no straight to find)
        for round_ in range(ROUNDS):
            if round_ == 12:                             # circles that nearly touch: a short straight between them
                busy = busy & ~joined                    # is found soon or not at all
            if not (busy & ~(step < SETTLED)).any():
                break
            e1, e2 = _square(t)

            def miss(tt):                                # the part of the step that is not along the straight
                gap = touch(tt)[2]
                off = gap - _dot(gap, tt)[..., None] * tt
                return _dot(off, e1), _dot(off, e2)

            g1, g2 = miss(t)
            a1, a2 = miss(_unit(t + _NUDGE * e1))
            b1, b2 = miss(_unit(t + _NUDGE * e2))
            j11, j21, j12, j22 = (a1 - g1) / _NUDGE, (a2 - g2) / _NUDGE, (b1 - g1) / _NUDGE, (b2 - g2) / _NUDGE
            det = j11 * j22 - j12 * j21
            with np.errstate(divide="ignore", invalid="ignore"):
                dx1, dx2 = (g2 * j12 - g1 * j22) / det, (g1 * j21 - g2 * j11) / det
            fine = np.isfinite(dx1) & np.isfinite(dx2)
            dx1, dx2 = np.where(fine, dx1, 0.0), np.where(fine, dx2, 0.0)
            big = np.maximum(np.abs(dx1), np.abs(dx2))
            scale = np.minimum(1.0, 0.5 / np.where(big > 0.0, big, 1.0))
            t = _unit(t + (dx1 * scale)[..., None] * e1 + (dx2 * scale)[..., None] * e2)
            step = np.where(fine, big * reach, np.inf)
        with np.errstate(invalid="ignore"):
            found = (step < GOOD_ENOUGH) & (_dot(touch(t)[2], t) >= -TOUCH)
        t = np.where((joined & ~found)[..., None], joined_t, t)
        ea, eb, gap = touch(t)
        self.t_out[:, A] = np.arctan2(_dot(ea, self.v[:, A]), _dot(ea, self.u[:, A]))
        self.t_in[:, B] = np.arctan2(_dot(eb, self.v[:, B]), _dot(eb, self.u[:, B]))
        none = ~joined & ~found
        for k in range(len(A)):
            self._flag(none[:, k], _OVERLAP, int(B[k]), int(A[k]))

    # -- the tight string -------------------------------------------------------------------------------------

    def _solve_free(self):
        F, W = self.F, self.W
        self._pairs()
        if W > 1:                                        # frames in which more axes are parallel than in the others
            odd = self.live & (self.level != self.par[None, :]).any(axis=1)      # are chains of their own
            if odd.any():
                self.live = self.live & ~odd
                if self.live.any():
                    self._free()
                else:
                    self._points(np.zeros((F, W)))
                self.live = self.live | odd
                rows = np.flatnonzero(odd)
                kinds, which = np.unique(self.level[rows], axis=0, return_inverse=True)
                for k in range(len(kinds)):
                    mask = np.zeros(F, dtype=bool)
                    mask[rows[np.ravel(which) == k]] = True
                    self._again(mask, False)
                self.ok = self.code == 0
                return
        self._free()

    def _free(self):
        F, W = self.F, self.W
        cuts = np.flatnonzero(~self.par)
        self.first = np.concatenate([[0], cuts + 1]).astype(np.int64)     # each group's first and last wheel
        self.last = np.concatenate([cuts, [W - 1]]).astype(np.int64)
        G = len(self.first)
        self.group = np.repeat(np.arange(G), self.last - self.first + 1)
        self.A, self.B = self.last[:-1], self.first[1:]                   # straight k: wheel A[k] -> wheel B[k]
        K = G - 1
        self.lead = np.zeros((F, G))                     # the straights before / after a group, seen along its axis
        self.tail = np.zeros((F, G))
        self.z_start = np.zeros((F, G))
        self.z_end = np.zeros((F, G))
        self.lead[:, 0], self.tail[:, -1] = self._ends()
        self.z_start[:, 0] = _dot(self.S, self.N[:, 0])
        self.z_end[:, -1] = _dot(self.E, self.N[:, self.first[-1]])

        t = np.zeros((F, 0, 3))
        late = np.zeros(F, dtype=bool)
        if K:                                            # step 3: Newton on the straights' directions
            t = self._first_guess(self.A, self.B)
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
        wild = self._points(wrap)
        for k in range(K):
            with np.errstate(invalid="ignore"):
                self._flag(st["run"][:, k] < -TOUCH, _OVERLAP, int(self.B[k]), int(self.A[k]))
        if K:
            self._flag(wild | late, _UNSETTLED, int(self.B[0]), -3)
        else:
            self._flag(wild, _NUMBERS, 0, -3)
        self._wrap_flags()

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
            round_ = np.cos(theta)[..., None] * self.u[:, i, None, :] + np.sin(theta)[..., None] * self.v[:, i, None, :]
            pts[:, k] = self.C[:, i, None, :] + h[..., None] * self.N[:, i, None, :] + self.r[i] * round_
            if self.lift[:, i].any():
                pts[:, k] = np.where(self.lift[:, i, None, None], self.p_in[:, i, None, :], pts[:, k])
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
    return np.maximum(np.asarray(counts, dtype=np.int64).reshape(-1), 2)


def _asked(W: int, counts, step, wraps0) -> str:
    """'' when what was asked for can be done, else what is wrong with it."""
    try:
        if not (math.isfinite(float(step)) and float(step) > 0.0):
            return "The step between an arc's points must be more than 0."
        if counts is not None and (np.size(counts) != W or not np.isfinite(np.asarray(counts, dtype=np.float64)).all()):
            return "The points per arc must be one whole number for every contact."
        if wraps0 is not None and (np.size(wraps0) != W or not np.isfinite(np.asarray(wraps0, dtype=np.float64)).all()):
            return "The known wraps must be one angle for every contact."
    except (TypeError, ValueError):
        return "The step, the points per arc or the known wraps are not numbers."
    return ""


def _arrays(wheels):
    W = len(wheels)
    c = np.array([np.asarray(w.centre, dtype=np.float64).reshape(3) for w in wheels]).reshape(W, 3)
    a = np.array([np.asarray(w.axis, dtype=np.float64).reshape(3) for w in wheels]).reshape(W, 3)
    r = np.array([float(w.radius) for w in wheels], dtype=np.float64)
    s = np.array([-1.0 if w.side < 0 else 1.0 for w in wheels], dtype=np.float64)
    return c, a, r, s


def _one(start, wheels, end, on0: bool, on1: bool, held=None, wraps0=None) -> _Chain:
    c, a, r, s = _arrays(wheels)
    W = len(wheels)
    ref = None if wraps0 is None else np.asarray(wraps0, dtype=np.float64).reshape(W)
    return _Chain(np.asarray(start, dtype=np.float64).reshape(1, 3), c[None], a[None], r, s,
                  np.asarray(end, dtype=np.float64).reshape(1, 3), bool(on0) and W > 0, bool(on1) and W > 0, held,
                  ref=ref, lift=ref is not None)


def _refusal(W: int, problem: str, bad: int = -1) -> Path:
    return Path(False, problem, bad, np.zeros((0, 3)), np.zeros(0), np.zeros(W, dtype=np.int64), np.zeros(W), 0.0,
                np.zeros(W, dtype=np.int64))


def _path(ch: _Chain, counts, step, name=_number) -> Path:
    W = ch.W
    if ch.code[0]:
        return _refusal(W, _sentence(int(ch.code[0]), int(ch.bad[0]), int(ch.other[0]), name), int(ch.bad[0]))
    cnt = _counts(counts, ch.wrap[0], step, W)
    pts, s, first = ch.polyline(cnt)
    return Path(True, "", -1, pts[0], s[0], first, ch.wrap[0].copy(), float(s[0, -1]), cnt, np.flatnonzero(ch.lift[0]))


def solve(start, wheels: list[Wheel], end, start_on_wheel: bool = False, end_on_wheel: bool = False,
          counts: list[int] | None = None, step: float = STEP, held: bool | None = None, wraps0=None) -> Path:
    """The cable from ``start`` over the wheels to ``end`` (see the module's text).

    ``start_on_wheel`` / ``end_on_wheel``: the point lies on the first / last wheel (it is put on its circle) and
    the arc starts / ends there: no straight run and no extra point on that side, so ``points[0]`` is the first
    arc's first point. ``counts``: points per arc (default: one every ``step``, at least 2). ``held``: True – the
    arcs lie in the wheels' planes; False – the wheels are plain cylinders (a helix where there is a fleet angle);
    None – the first, unless a straight then leaves a plane by more than 0.1°. No wheels: a straight line.

    ``wraps0``: the wrap (rad) each wheel is known to have – in the CAD pose. With it a wheel the cable no longer
    reaches on its side is **lifted off**: the cable passes it straight, its wrap is 0, its points all lie where
    the straight passes nearest its axis (the number of points stays) and ``lifted`` names it. A wheel counts as
    lifted when its wrap would be more than half a turn above the known one (the cable would have to come back
    round it). Without ``wraps0`` one frame alone cannot tell a wide wrap from a wheel that was left: any wrap up
    to 350° is drawn (a wheel just beside the cable's line: nearly a whole turn – refused; one further off: a
    loop round it).

    Never raises on a path that cannot be: ``ok`` is False, ``problem`` says why, ``points`` is empty."""
    wrong = _asked(len(wheels), counts, step, wraps0)
    if wrong:
        return _refusal(len(wheels), wrong)
    return _path(_one(start, wheels, end, start_on_wheel, end_on_wheel, held, wraps0), counts, step)


def solve_frames(starts, centres, axes, radii, sides, ends, start_on_wheel: bool = False,
                 end_on_wheel: bool = False, counts=None, step: float = STEP, held: bool | None = None,
                 wraps0=None) -> dict:
    """``solve`` for F frames at once: starts (F, 3), centres (F, W, 3), axes (F, W, 3), radii (W,), sides (W,),
    ends (F, 3). Returns {"points": (F, n, 3), "s": (F, n), "wrap": (F, W), "length": (F,), "first": (W,),
    "counts": (W,), "ok": (F,), "bad": (F,), "problems": {frame: text}, "held": (F,) which frames have their
    arcs in the wheels' planes, "lifted": (F, W) which wheels the cable does not reach in which frame}.

    With ``held`` None every frame chooses for itself, as ``solve`` does (the cable then jumps by millimetres
    where a fleet angle passes 0.1°: give ``held`` True for a cable whose contacts move).

    **A wheel the cable leaves** is lifted off (see ``solve``): from frame to frame a wheel's wrap never jumps by
    more than half a turn, so a wrap that shrinks to nothing and would come back as nearly a whole turn is a
    lifted wheel, for as long as it stays away; ``wraps0`` (the wraps of the CAD pose) says the same for the
    first frame and for the first frame after frames without a path. Without ``wraps0`` such a first frame is
    read as ``solve`` reads it. A frame without a path is tried with the wheels lifted that the last good frame
    had lifted.

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
    wrong = _asked(W, counts, step, wraps0)
    if wrong:
        cnt = np.full(W, 2, dtype=np.int64)
        n = 2 * W + (0 if (W and start_on_wheel) else 1) + (0 if (W and end_on_wheel) else 1)
        return {"points": np.zeros((F, n, 3)), "s": np.zeros((F, n)), "wrap": np.zeros((F, W)), "length": np.zeros(F),
                "first": np.zeros(W, dtype=np.int64), "counts": cnt, "ok": np.zeros(F, dtype=bool),
                "bad": np.full(F, -1, dtype=np.int64), "problems": {f: wrong for f in range(F)},
                "held": np.zeros(F, dtype=bool), "lifted": np.zeros((F, W), dtype=bool)}
    ref = None if wraps0 is None else np.asarray(wraps0, dtype=np.float64).reshape(W)
    ch = _Chain(starts, centres, axes, radii, sides, ends, bool(start_on_wheel) and W > 0, bool(end_on_wheel) and W > 0,
                held, ref=ref, lift=True)
    ok = ch.code == 0
    widest = ch.wrap[ok].max(axis=0) if ok.any() else np.zeros(W)
    cnt = _counts(counts, widest, step, W)
    pts, s, first = ch.polyline(cnt)
    wrap, lifted = ch.wrap.copy(), ch.lift.copy()
    if not ok.all():
        if ok.any():
            good = np.flatnonzero(ok)
            last = np.maximum.accumulate(np.where(ok, np.arange(F), -1))
            take = np.where(last >= 0, last, good[0])
            pts, s, wrap, lifted = pts[take], s[take], wrap[take], lifted[take]
        else:
            pts, s, wrap, lifted = np.zeros_like(pts), np.zeros_like(s), np.zeros_like(wrap), np.zeros_like(lifted)
    problems = {int(f): _sentence(int(ch.code[f]), int(ch.bad[f]), int(ch.other[f])) for f in np.flatnonzero(~ok)}
    return {"points": pts, "s": s, "wrap": wrap, "length": s[:, -1].copy(), "first": first, "counts": cnt,
            "ok": ok, "bad": ch.bad.copy(), "problems": problems, "held": ch.held & ok, "lifted": lifted}


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
    if not (math.isfinite(float(radius)) and float(radius) > 0.0):
        return 0.0
    sign = (1.0 if side >= 0 else -1.0) * (1.0 if float(np.dot(axis, joint_axis)) >= 0.0 else -1.0)
    if reverse:
        sign = -sign
    return sign * 360.0 / (2.0 * math.pi * float(radius) * 1000.0)


def stripes(diameter: float, pitch: float, angle: float) -> int:
    """How many stripes (strands) go round a cable: the nearest whole number to π·d / (pitch · tan(angle)), at
    most 64 either way.

    ``pitch``: from one stripe to the next along the cable; ``angle`` (rad): between a stripe and the cable's
    length – 90° gives 0 (rings round the cable), a negative angle the other hand. 0 for numbers that are none."""
    try:
        diameter, pitch, angle = float(diameter), float(pitch), float(angle)
    except (TypeError, ValueError):
        return 0
    if not (math.isfinite(diameter) and math.isfinite(pitch) and math.isfinite(angle)) or not pitch > 0.0:
        return 0
    t = math.tan(max(min(angle, 0.5 * math.pi), -0.5 * math.pi))
    if abs(t) > 1e9:
        return 0
    if abs(t) < 1e-9:
        return MAX_STARTS if angle >= 0.0 else -MAX_STARTS
    return int(max(min(round(math.pi * diameter / (pitch * t)), MAX_STARTS), -MAX_STARTS))


def stripe_angle(diameter: float, pitch: float, starts: int) -> float:
    """The angle (rad) between a stripe and the cable's length for ``starts`` stripes round it: 0 starts = 90°
    (and 90° for a pitch or a diameter that is none)."""
    try:
        diameter, pitch, starts = float(diameter), float(pitch), float(starts)
    except (TypeError, ValueError):
        return 0.5 * math.pi
    if starts == 0 or not (math.isfinite(diameter) and math.isfinite(pitch) and math.isfinite(starts)) or not pitch > 0.0:
        return 0.5 * math.pi
    return math.atan(math.pi * diameter / (starts * pitch))


# ---------------------------------------------------------------------------------------------------------
# the surface a cable rests on
# ---------------------------------------------------------------------------------------------------------

SEAT_FINE = 32.0                # the outline is read in steps of the cable's radius / this along the axis
ROUND_SLICES = 12               # is_round: the part is looked at in this many slices along the axis; in each
ROUND_TOL = 0.02                # … the corners within this share of the furthest out are its outside, and
ROUND_GAP = math.radians(65.0)  # … they leave no gap wider than this round the axis (6 flat sides: 60°)
ROUND_BAND = 0.85               # with the triangles: a facet is "outside" from this share of the slice's outer radius,
ROUND_SHARE = 0.9               # … the outside facets must cover this share of the turn,
ROUND_SLICES_SHARE = 0.9        # … in this share of the slices
WALL = 4.0                      # the outline between two of its points is a straight piece up to this slope


def _edges_of(verts, tris, centre, axis):
    """A mesh seen from an axis: every corner's place along it and its offset from it, and the edges (i, j)."""
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3).astype(np.int64)
    a = _unit(np.asarray(axis, dtype=np.float64).reshape(3))
    rel = v - np.asarray(centre, dtype=np.float64).reshape(3)
    z = rel @ a
    flat = rel - np.outer(z, a)
    if not len(v) or not len(t):
        return z, flat, np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    pair = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [0, 2]]])
    m = len(v)
    key = np.unique(pair.min(axis=1) * m + pair.max(axis=1))
    return z, flat, key // m, key % m


def _outline(mesh, lo: float, hi: float, dz: float):
    """The part's outer outline between the axial places ``lo`` and ``hi`` (m from centre along axis): arrays
    (place, radius), one point per ``dz`` of the axis where the part is, each a real point of the mesh
    (``mesh``: from ``_edges_of``).

    Only the triangles' edges are walked: on a flat triangle the point furthest from the axis at one place along
    it lies on an edge (the distance from a line is a convex function)."""
    z, flat, i, j = mesh
    empty = np.zeros(0), np.zeros(0)
    if not len(i) or not hi > lo:
        return empty
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


def _rest(zs, rs, at, rope: float, touching: bool = False):
    """How far from the axis the middle of a round section of radius ``rope`` is when it rests on the outline at
    the axial places ``at`` (array): the outline grown by the section. The outline is its points and the straight
    pieces between neighbours (not across a wall: a step in the radius), so a flat or coned surface is exact.
    ``touching``: also the radius of the outline where the section touches it."""
    at = np.atleast_1d(np.asarray(at, dtype=np.float64))
    out = np.zeros(len(at))
    where = np.zeros(len(at))
    dz, dr = np.diff(zs), np.diff(rs)
    piece = (dz > 0.0) & (np.abs(dr) <= WALL * dz)
    za, zb, ra = zs[:-1][piece], zs[1:][piece], rs[:-1][piece]
    slope = dr[piece] / dz[piece]
    lean = rope * slope / np.sqrt(1.0 + slope * slope)       # where on a sloping piece the section touches
    for k in range(0, len(at), 256):                     # in blocks: places x outline points
        z0 = at[k:k + 256, None]
        rows = np.arange(len(z0))
        d = zs[None, :] - z0
        with np.errstate(invalid="ignore"):
            up = np.where(np.abs(d) <= rope, rs[None, :] + np.sqrt(rope * rope - d * d), -np.inf)
        pick = up.argmax(axis=1)
        best, touch = up[rows, pick], rs[pick]
        if len(za):
            z = np.clip(z0 + lean[None, :], za[None, :], zb[None, :])
            d = z - z0
            on = ra[None, :] + slope[None, :] * (z - za[None, :])
            with np.errstate(invalid="ignore"):
                up = np.where(np.abs(d) <= rope, on + np.sqrt(rope * rope - d * d), -np.inf)
            pick = up.argmax(axis=1)
            higher = up[rows, pick] > best
            best, touch = np.where(higher, up[rows, pick], best), np.where(higher, on[rows, pick], touch)
        fine = np.isfinite(best)
        out[k:k + 256] = np.where(fine, best, 0.0)
        where[k:k + 256] = np.where(fine, touch, 0.0)
    return (out, where) if touching else out


def _seat(mesh, at: float, rope: float, search: float | None = None):
    """``seat`` and the radius of the surface where the cable touches it: (place, radius, touching radius)."""
    rope = float(rope)
    at = float(at)
    if not rope > 0.0 or not math.isfinite(at):
        return at, 0.0, 0.0
    search = rope if search is None else max(float(search), 0.0)
    zs, rs = _outline(mesh, at - search - rope, at + search + rope, rope / SEAT_FINE)
    if not len(zs):
        return at, 0.0, 0.0
    here = float(_rest(zs, rs, at, rope)[0])
    place = at
    if search > 0.0 and here > 0.0:
        # a groove: the lowest place in reach, if the cable can sink into it (a dip with a way up on both sides –
        # not the lower end of a slope, as on a crowned or coned roller)
        lo, hi = at - search, at + search
        for _ in range(3):
            grid = np.linspace(lo, hi, 129)
            rest = _rest(zs, rs, grid, rope)
            dips = np.flatnonzero(rest <= float(rest.min()) + 1e-12)
            k = int(dips[np.argmin(np.abs(grid[dips] - at))])
            lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, 128)]
            if not 0 < k < 128:
                break
        else:
            if 0.0 < rest[k] < here - max(1e-4 * rope, 1e-5):    # (a dip of rounding, as 32-bit corners give, is none)
                place = float(grid[k])
    radius, touch = _rest(zs, rs, place, rope, touching=True)
    if not radius[0] > 0.0:
        return at, 0.0, 0.0
    return place, float(radius[0]), float(touch[0])


def seat(verts, tris, centre, axis, at: float, rope_radius: float, search: float | None = None) -> tuple[float, float]:
    """Where a cable of ``rope_radius`` rests on a round part near the axial place ``at`` (m from ``centre`` along
    ``axis``): (place along the axis, radius from the axis to the cable's middle).

    In a groove that is the lowest place the cable can sink to within ``search`` (default: its own radius) along
    the axis: the groove's bottom + the cable's radius in a round groove, on both flanks in a V groove. On a
    plain, crowned or coned roller it is where the cable is: the surface at ``at`` + the cable's radius (the
    cable does not slide down a slope). (at, 0.0) when the part has no surface there."""
    place, radius, _ = _seat(_edges_of(verts, tris, centre, axis), at, rope_radius, search)
    return place, radius


def surface_radius(verts, tris, centre, axis, at: float, width: float) -> float:
    """The part's outer radius within ``width`` (in all) round the axial place ``at``; 0.0 when it is not there."""
    half = 0.5 * max(float(width), 1e-9)
    _, rs = _outline(_edges_of(verts, tris, centre, axis), float(at) - half, float(at) + half, 2.0 * half / 16.0)
    return float(rs.max()) if len(rs) else 0.0


def is_round(verts, centre, axis, tris=None) -> bool:
    """True when the mesh is round all the way about this axis (a roller, a sheave, a drum: it may turn); False
    for a part that is round over a part of the turn only (a chute, a quadrant's gutter) or not at all.

    With the triangles (``tris``) the outside itself is looked at: the part is cut into 12 slices along the axis,
    and in a slice the facets that lie at 85 % or more of the slice's outer radius must cover 90 % of the turn.
    At least 90 % of the slices must do so. So a cross hole, a keyway, a flat, an anchor hole in a drum's barrel
    or a lug at one end leave a roller round; a sector of 300° or less, a square bar or a roller in one piece
    with its bracket are not.

    Without them only the corners are there: in every slice the corners furthest from the axis (within 2 %) must
    go all the way round without a gap wider than 65°; a slice with a few corners that do not stand out beyond
    the round slices (the rim of a hole) does not count against the part."""
    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    if len(v) < 6:
        return False
    a = _unit(np.asarray(axis, dtype=np.float64).reshape(3))
    u, w = _square(a)
    rel = v - np.asarray(centre, dtype=np.float64).reshape(3)
    z = rel @ a
    x, y = rel @ u, rel @ w
    rho = np.hypot(x, y)
    big = float(rho.max())
    if not big > 0.0 or not np.isfinite(big) or not np.isfinite(z).all():
        return False
    phi = np.arctan2(y, x)
    z0, z1 = float(z.min()), float(z.max())
    slices = 1 if z1 - z0 < 1e-9 * big else ROUND_SLICES
    thick = (z1 - z0) / slices
    edge = 1e-6 * (z1 - z0) + 1e-9 * big                # a ring of corners on a slice's edge counts in both
    t = None if tris is None else np.asarray(tris).reshape(-1, 3).astype(np.int64)
    if t is not None and len(t):
        return _round_outside(t, np.stack([x, y], axis=1), z, rho, phi, z0, thick, slices, edge)
    far, whole = np.zeros(slices), np.zeros(slices, dtype=bool)
    for k in range(slices):
        here = (z >= z0 + k * thick - edge) & (z <= z0 + (k + 1) * thick + edge)
        if not here.any():
            continue
        far[k] = float(rho[here].max())
        if not far[k] > 1e-9 * big:
            continue
        ang = np.sort(phi[here][rho[here] >= far[k] * (1.0 - ROUND_TOL)])
        gap = max(float(np.diff(ang).max()) if len(ang) > 1 else 0.0, float(ang[0] - ang[-1]) + 2.0 * math.pi)
        whole[k] = gap <= ROUND_GAP
    if not whole.any():
        return False
    return bool((whole | (far <= far[whole].max() * (1.0 + ROUND_TOL))).all())


def _round_outside(t, flat, z, rho, phi, z0: float, thick: float, slices: int, edge: float) -> bool:
    """``is_round`` by the triangles: per slice, how much of the turn the facets at the slice's outer radius cover."""
    corners = rho[t]
    mids = np.stack([np.linalg.norm(0.5 * (flat[t[:, k]] + flat[t[:, (k + 1) % 3]]), axis=1) for k in range(3)], axis=1)
    low = np.minimum(corners.min(axis=1), mids.min(axis=1))          # a facet's own lowest radius (about)
    high = corners.max(axis=1)
    turn = 2.0 * np.pi
    d = np.mod(phi[t] - phi[t[:, :1]] + np.pi, turn) - np.pi         # the corners' angles from the first one's
    start, wide = phi[t[:, 0]] + d.min(axis=1), d.max(axis=1) - d.min(axis=1)
    bins = 72
    pad = 0.5 * turn / bins
    mid = (np.arange(bins) + 0.5) * turn / bins
    lo = z0 + thick * np.arange(slices)
    zt = z[t]
    over = (zt.min(axis=1)[:, None] <= lo[None, :] + thick + edge) & (zt.max(axis=1)[:, None] >= lo[None, :] - edge)
    outer = np.where(over, high[:, None], 0.0).max(axis=0)           # each slice's outer radius
    reach = over & (low[:, None] >= ROUND_BAND * outer[None, :]) & (wide[:, None] < np.pi)
    cover = np.zeros((slices, bins))
    for k in range(0, len(t), 20000):                    # in blocks: facets x bins
        part = slice(k, k + 20000)
        inside = np.mod(mid[None, :] - start[part, None] + pad, turn) <= wide[part, None] + 2.0 * pad
        cover += reach[part].T.astype(np.float32) @ inside.astype(np.float32)
    there = outer > 0.0
    if not there.any():
        return False
    good = (cover > 0.0).mean(axis=1) >= ROUND_SHARE
    return bool(good[there].mean() >= ROUND_SLICES_SHARE)


# ---------------------------------------------------------------------------------------------------------
# reading a CAD cable
# ---------------------------------------------------------------------------------------------------------

FIT_TOL = (5e-4, 0.01)          # a straight or an arc fits when no point is further off than 0.5 mm, or 1 % of
#                                 the cable's radius if that is more (what tube_centreline is good to; a piece
#                                 cut in two by a point a little further off is put together again) …
FINE_TOL = 2e-4                 # … and when that does not read, tighter: down to what the points' own noise allows
#                                 (at least this share of the radius): a clean thin rope's short bends need that
TOUCH_TOL = (2e-3, 0.25, 0.25)  # a part carries the cable when the cable is drawn within 2 mm of where it rests
#                                 on the part – or, if that is more, this share of its radius away from the part
#                                 (air between them) and this share into the part (two numbers: they may differ)
MAX_DEVIATION = (2e-3, 0.25)    # a reading whose path lies further from the points than 2 mm, or a quarter of the
#                                 cable's radius if that is more, is refused
SLIGHT = math.radians(1.0)      # a turn of less than this is no bend
SQUARE = math.radians(20.0)     # a roller turns when the cable crosses its axis within this of square
SAME_PLANE = math.radians(2.0)  # an arc lies on a part whose axis is this close to the arc's; arcs after each
#                                 other this close are in one plane
CORNER = math.radians(0.3)      # two straights that meet at less than this are one straight
STRONG = 3                      # an arc needs this many points of its own (that no straight fits)
LINE = 4                        # … a straight between two other pieces this many
REFITS = 6                      # at most this many steps of fitting all bends together
_STEP = 1e-6                    # m: the nudge that shows how a bend's centre and radius matter
_TIE = 30.0                     # arcs that touch: a gap between them counts this many times a point's distance


@dataclass
class Round:
    """A round face axis of a part near the cable (from the mesh's ``fr_axes``), in world coordinates. A part with
    several axes is given once per axis (the same key is fine)."""
    key: object                 # whatever the caller wants back (object name, axis index)
    centre: np.ndarray          # (3,) a point on the axis
    axis: np.ndarray            # (3,) unit
    verts: np.ndarray           # (V, 3) the part's mesh, world
    tris: np.ndarray            # (T, 3)
    full: bool | None = None    # round all the way (may turn)? None: worked out (is_round)


@dataclass
class Contact:
    kind: str                   # "WRAP" | "TOUCH" | "BEND"
    key: object                 # the Round's key (None for a BEND)
    centre: np.ndarray          # on the axis, in the plane of the cable there
    axis: np.ndarray
    radius: float               # WRAP: seat radius (from the mesh); BEND: fitted; TOUCH: axis -> centreline
    surface: float              # the part's radius where the cable touches it (BEND: 0)
    side: int
    s: float                    # where along the path (the middle of the contact)
    wrap: float                 # rad (TOUCH: 0)
    gap: float                  # the CAD cable's distance from where it would rest: + drawn apart, - drawn into the part
    full: bool                  # the part is round all the way


@dataclass
class Reading:
    ok: bool
    problem: str
    contacts: list              # of Contact, in order along the centreline
    start: np.ndarray
    end: np.ndarray
    start_on_wheel: bool
    end_on_wheel: bool
    path: Path                  # solve() of the WRAP and BEND contacts
    deviation: float            # the furthest the CAD centreline is from that path (m)


def _no_path(W: int = 0, problem: str = "") -> Path:
    return Path(False, problem, -1, np.zeros((0, 3)), np.zeros(0), np.zeros(W, dtype=np.int64), np.zeros(W), 0.0,
                np.zeros(W, dtype=np.int64))


# -- fitting -------------------------------------------------------------------------------------------------

def _fit_line(p):
    """(a point, the unit direction first -> last, each point's distance) of the straight line through points."""
    c = p.mean(axis=0)
    rel = p - c
    if len(p) == 2:
        d = _unit(p[1] - p[0])
    else:
        d = np.linalg.eigh(rel.T @ rel)[1][:, 2]
        if float(d @ (p[-1] - p[0])) < 0.0:
            d = -d
    off = rel - np.outer(rel @ d, d)
    return c, d, np.linalg.norm(off, axis=1)


def _circle_2d(x, y, rounds: int = 4):
    """The circle nearest to points in a plane: (cx, cy, r); None when they lie on a line."""
    mx, my = float(x.mean()), float(y.mean())
    x, y = x - mx, y - my
    q = x * x + y * y
    a = np.stack([x, y, np.ones_like(x)], axis=1)
    try:
        sol = np.linalg.solve(a.T @ a, a.T @ q)
    except np.linalg.LinAlgError:
        return None
    cx, cy = 0.5 * sol[0], 0.5 * sol[1]
    r2 = sol[2] + cx * cx + cy * cy
    if not (np.isfinite(r2) and r2 > 0.0):
        return None
    r = math.sqrt(r2)
    for _ in range(rounds):                              # from the algebraic fit to the true distances
        dx, dy = x - cx, y - cy
        dist = np.hypot(dx, dy)
        if not (dist > 0.0).all():
            break
        jac = np.stack([-dx / dist, -dy / dist, -np.ones_like(dist)], axis=1)
        try:
            step = np.linalg.solve(jac.T @ jac, -jac.T @ (dist - r))
        except np.linalg.LinAlgError:
            break
        if not np.isfinite(step).all() or abs(step[2]) > 0.5 * r:
            break
        cx, cy, r = cx + step[0], cy + step[1], r + step[2]
    return cx + mx, cy + my, r


def _fit_circle(p, normal=None):
    """The circle nearest to points in space: (centre, normal, radius, each point's distance), the normal turned
    so that the points go round it (right hand); None when they lie on a line. ``normal``: the plane's is given."""
    c = p.mean(axis=0)
    rel = p - c
    if normal is None:
        n = np.linalg.eigh(rel.T @ rel)[1][:, 0]
    else:
        n = _unit(np.asarray(normal, dtype=np.float64))
    u, v = _square(n)
    x, y = rel @ u, rel @ v
    got = _circle_2d(x, y)
    if got is None:
        return None
    centre = c + got[0] * u + got[1] * v
    r = got[2]
    x, y = x - got[0], y - got[1]
    if float((x[:-1] * y[1:] - y[:-1] * x[1:]).sum()) < 0.0:      # the points go round the other way
        n = -n
    return centre, n, r, np.hypot(np.hypot(x, y) - r, rel @ n)


class _Window:
    """Does a run of points fit one straight or one arc within ``tol``? Remembers the last fit, so a point that
    lies on it costs nothing."""

    def __init__(self, pts, tol: float):
        self.p, self.tol = pts, tol
        self.kind = None

    def _on(self, k: int) -> bool:
        q = self.p[k]
        if self.kind == "line":
            rel = q - self.c
            return float(np.linalg.norm(rel - (rel @ self.d) * self.d)) <= self.tol
        if self.kind == "arc":
            arm = q - self.c
            h = float(arm @ self.d)
            return math.hypot(float(np.linalg.norm(arm - h * self.d)) - self.r, h) <= self.tol
        return False

    def fits(self, i: int, j: int) -> bool:
        """Points i … j; called for j one further each time, or i one further."""
        if j - i < 2:
            self.kind = None
            return True
        if self.kind is not None and self._on(j):
            return True
        seg = self.p[i:j + 1]
        c, d, off = _fit_line(seg)
        if float(off.max()) <= self.tol:
            self.kind, self.c, self.d = "line", c, d
            return True
        got = _fit_circle(seg)
        if got is not None and float(got[3].max()) <= self.tol:
            self.kind, self.c, self.d, self.r = "arc", got[0], got[1], got[2]
            return True
        return False


def _pieces(pts, tol: float):
    """Cut the points into the fewest runs that are each one straight or one arc. Returns a list of dicts: ``lo``,
    ``hi`` (the longest run the piece fits, overlapping its neighbours where both fit), ``own`` (the points no
    neighbour fits: lo, hi) and what its own points are: ``kind`` "arc" (at least 3 that no straight fits, with
    the circle) or "line" (at least 4). The few points where two neighbours meet are in no piece."""
    n = len(pts)
    reach = np.zeros(n, dtype=np.int64)                  # the furthest point a run from point i fits
    win = _Window(pts, tol)
    j = 0
    for i in range(n):
        j = max(j, i)
        while j + 1 < n and win.fits(i, j + 1):
            j += 1
        reach[i] = j
    out = []
    i = 0
    while True:
        hi = int(reach[i])
        lo = int(np.searchsorted(reach, hi, side="left"))    # the same run, started as early as it still fits
        out.append({"lo": lo, "hi": hi})
        if hi >= n - 1:
            break
        i = hi
    def as_line(a, b):
        seg = pts[a:b + 1]
        c, d, off = _fit_line(seg)
        return dict(kind="line", c=c, d=d, long=float(np.linalg.norm(seg[-1] - seg[0])), count=b - a + 1, own=(a, b)), off

    def as_arc(a, b, bulge=None):
        seg = pts[a:b + 1]
        got = _fit_circle(seg)
        if got is None:
            return None, None
        bulge = float(_fit_line(seg)[2].max()) if bulge is None else bulge
        return dict(kind="arc", c=got[0], n=got[1], r=got[2], bulge=bulge, own=(a, b)), got[3]

    for _ in range(2):                                   # again without the runs that are no piece: their points
        for k, pc in enumerate(out):                     # go to the neighbours that fit them too
            a = max(pc["lo"], out[k - 1]["hi"] + 1) if k else pc["lo"]
            b = min(pc["hi"], out[k + 1]["lo"] - 1) if k < len(out) - 1 else pc["hi"]
            pc.update(own=(a, b), kind=None)
            if b - a < 1:
                continue
            line, off = as_line(a, b)
            if b - a + 1 >= STRONG and float(off.max()) > tol:
                # a straight that took a point or two of the bend next to it is still a straight
                for da, db in ((0, 1), (1, 0), (1, 1), (0, 2), (2, 0), (2, 2)):
                    if b - db - (a + da) + 1 >= max(LINE, 6) and float(as_line(a + da, b - db)[1].max()) <= tol:
                        a, b = a + da, b - db
                        line, off = as_line(a, b)
                        break
                else:
                    arc, _ = as_arc(a, b, float(off.max()))
                    if arc is not None:
                        pc.update(arc)
                        continue
            if b - a + 1 >= LINE or len(out) == 1:
                pc.update(line)
        if all(pc["kind"] for pc in out):
            break
        out = [pc for pc in out if pc["kind"]]
    kept = [pc for pc in out if pc["kind"]]
    # one arc (or straight) cut in two by a point that lies a little off: one piece again
    k = 0
    while k + 1 < len(kept):
        one, two = kept[k], kept[k + 1]
        a, b = one["own"][0], two["own"][1]
        new = None
        if one["kind"] == two["kind"] == "line":
            new, off = as_line(a, b)
        elif one["kind"] == two["kind"] == "arc":
            new, off = as_arc(a, b)
        if new is None or float(off.max()) > 2.0 * tol:
            k += 1
            continue
        new.update(lo=one["lo"], hi=two["hi"])
        kept[k:k + 2] = [new]
    # a short straight between two corners that turn the same way is a bend seen with a wide tolerance: one arc
    k = 1
    while k + 1 < len(kept):
        one, mid, two = kept[k - 1], kept[k], kept[k + 1]
        if (one["kind"] == mid["kind"] == two["kind"] == "line" and mid["count"] < 12
                and float(_cross(one["d"], mid["d"]) @ _cross(mid["d"], two["d"])) > 0.0):
            a, b = one["own"][1] + 1, two["own"][0] - 1
            seg = pts[a:b + 1]
            off1 = seg - one["c"]                            # the points neither straight goes through
            off1 = np.linalg.norm(off1 - np.outer(off1 @ one["d"], one["d"]), axis=1) > 0.5 * tol
            off2 = seg - two["c"]
            off2 = np.linalg.norm(off2 - np.outer(off2 @ two["d"], two["d"]), axis=1) > 0.5 * tol
            if off1.any() and off2.any():
                a, b = a + int(np.argmax(off1)), a + len(seg) - 1 - int(np.argmax(off2[::-1]))
                arc, off = as_arc(a, b) if b - a + 1 >= STRONG else (None, None)
                if arc is not None and float(off.max()) <= tol:
                    arc.update(lo=mid["lo"], hi=mid["hi"])
                    kept[k] = arc
        k += 1
    return kept


# -- the drawn path, as pieces a point's distance can be measured to --------------------------------------------

class _Drawn:
    """A solved path (one frame) as straights and arcs: the nearest place on it for any point."""

    def __init__(self, ch: _Chain):
        W = ch.W
        runs, arcs = ch.lengths()
        runs, arcs = runs[0], arcs[0]
        self.a, self.b, self.sa = [], [], []             # straights: from, to, s at from
        at = 0.0
        first = ch.S[0] if not (W and ch.on0) else ch.p_in[0, 0]
        ends = [first] + [ch.p_out[0, i] for i in range(W)]
        starts = [ch.p_in[0, i] for i in range(W)] + [ch.E[0] if not (W and ch.on1) else ch.p_out[0, -1]]
        self.arc_s = np.zeros(W)
        for k in range(W + 1):
            self.a.append(ends[k])
            self.b.append(starts[k])
            self.sa.append(at)
            at += runs[k]
            if k < W:
                self.arc_s[k] = at
                at += arcs[k]
        self.a, self.b, self.sa = np.array(self.a), np.array(self.b), np.array(self.sa)
        self.length = at
        self.ch, self.arcs = ch, arcs

    def nearest(self, pts):
        """For each point: the vector to the nearest place on the path, that place's s, and its piece (0 … W:
        straight k; W + 1 + i: arc i)."""
        ch = self.ch
        W = ch.W
        n = len(pts)
        best = np.full(n, np.inf)
        vec = np.zeros((n, 3))
        s = np.zeros(n)
        piece = np.zeros(n, dtype=np.int64)
        for k in range(W + 1):
            ab = self.b[k] - self.a[k]
            l2 = float(ab @ ab)
            f = np.clip(((pts - self.a[k]) @ ab) / l2, 0.0, 1.0) if l2 > 0.0 else np.zeros(n)
            v = self.a[k] + f[:, None] * ab - pts
            d = np.einsum("ij,ij->i", v, v)
            take = d < best
            best, vec, s, piece = np.where(take, d, best), np.where(take[:, None], v, vec), \
                np.where(take, self.sa[k] + f * math.sqrt(l2), s), np.where(take, k, piece)
        for i in range(W):
            if ch.lift[0, i]:
                continue
            c, nn, u, v_ = ch.C[0, i], ch.N[0, i], ch.u[0, i], ch.v[0, i]
            r, sg, wrap = float(ch.r[i]), float(ch.sg[i]), float(ch.wrap[0, i])
            rel = pts - c
            ang = np.mod(sg * (np.arctan2(rel @ v_, rel @ u) - ch.t_in[0, i]), 2.0 * np.pi)
            past = ang > wrap                            # beside the arc: its nearer end
            ang = np.where(past, np.where(ang - wrap < 2.0 * np.pi - ang, wrap, 0.0), ang)
            share = ang / wrap if wrap > 0.0 else np.zeros(n)
            theta = ch.t_in[0, i] + sg * ang
            h = ch.h_in[0, i] + (ch.h_out[0, i] - ch.h_in[0, i]) * share
            on = c + h[:, None] * nn + r * (np.cos(theta)[:, None] * u + np.sin(theta)[:, None] * v_)
            v = on - pts
            d = np.einsum("ij,ij->i", v, v)
            take = d < best
            best, vec, s, piece = np.where(take, d, best), np.where(take[:, None], v, vec), \
                np.where(take, self.arc_s[i] + share * self.arcs[i], s), np.where(take, W + 1 + i, piece)
        return vec, s, piece


# -- round parts -----------------------------------------------------------------------------------------------

class _Parts:
    """The round parts near the cable: where each one's axis is, and (worked out when first asked) where a cable
    rests on it."""

    def __init__(self, rounds, rope: float):
        self.rounds = list(rounds)
        self.rope = rope
        R = len(self.rounds)
        self.c = np.array([np.asarray(r.centre, dtype=np.float64).reshape(3) for r in self.rounds]).reshape(R, 3)
        self.a = _unit(np.array([np.asarray(r.axis, dtype=np.float64).reshape(3) for r in self.rounds]).reshape(R, 3))
        self._seat = {}
        self._full = {}
        self._mesh = {}
        self._far = {}

    def __len__(self):
        return len(self.rounds)

    def seat(self, k: int, at: float):
        """(place along the axis, seat radius, touching radius) of part k for a cable near the axial place at."""
        key = (k, round(at / max(0.25 * self.rope, 1e-9)))
        if key not in self._seat:
            self._seat[key] = _seat(self.mesh(k), at, self.rope)
        return self._seat[key]

    def mesh(self, k: int):
        if k not in self._mesh:
            r = self.rounds[k]
            self._mesh[k] = _edges_of(r.verts, r.tris, self.c[k], self.a[k])
        return self._mesh[k]

    def reach(self, k: int, at: float | None = None) -> float:
        """The furthest part k reaches from its axis: anywhere, or within two cable radii of the axial place at."""
        z, flat, i, j = self.mesh(k)
        if k not in self._far:
            self._far[k] = np.linalg.norm(flat, axis=1)
        far = self._far[k]
        if at is None or not len(i):
            return float(far.max()) if len(far) else 0.0
        near = (np.maximum(z[i], z[j]) >= at - 2.0 * self.rope) & (np.minimum(z[i], z[j]) <= at + 2.0 * self.rope)
        return float(np.maximum(far[i[near]], far[j[near]]).max()) if near.any() else 0.0

    def full(self, k: int) -> bool:
        if k not in self._full:
            r = self.rounds[k]
            self._full[k] = bool(r.full) if r.full is not None else is_round(r.verts, self.c[k], self.a[k], r.tris)
        return self._full[k]

    def polar(self, k, pts):
        """Points seen from part(s) k: distance from the axis, place along it."""
        rel = pts - self.c[k][..., None, :] if np.ndim(k) else pts - self.c[k]
        a = self.a[k][..., None, :] if np.ndim(k) else self.a[k]
        along = _dot(rel, a)
        return np.linalg.norm(rel - along[..., None] * a, axis=-1), along


def _side(point, centre, axis, heading) -> int:
    return 1 if float(_cross(point - centre, heading) @ axis) >= 0.0 else -1


def _rests(gap: float, touch_tol) -> bool:
    """Is a cable drawn ``gap`` from where it would rest on a part (+ apart, - into it) carried by the part?"""
    return -touch_tol[1] <= gap <= touch_tol[0]


def _arc_on_part(parts: _Parts, pts, tol: float, touch_tol):
    """The part an arc's own points lie on: they keep one distance from its axis and stay at one place along it,
    as well as they keep to their own circle (``tol``), and that distance is where the cable rests on the part
    (``touch_tol``: how far apart, how far into the part). Returns (part, place, seat, touching radius, gap) or
    None."""
    if not len(parts) or len(pts) < 2:
        return None
    every = np.arange(len(parts))
    rho, along = parts.polar(every, pts[None, :, :])
    chord = float(np.linalg.norm(pts[-1] - pts[0]))
    steady = (np.ptp(rho, axis=1) <= 4.0 * tol) & (np.ptp(along, axis=1) <= 4.0 * tol + math.sin(SAME_PLANE) * chord)
    best = None
    for k in np.flatnonzero(steady):
        mean = float(rho[k].mean())
        if mean > parts.reach(int(k), float(along[k].mean())) + parts.rope + touch_tol[0]:
            continue
        place, seat_r, touch = parts.seat(int(k), float(along[k].mean()))
        if seat_r > 0.0 and _rests(mean - seat_r, touch_tol) and (best is None or abs(mean - seat_r) < abs(best[4])):
            best = (int(k), place, seat_r, touch, mean - seat_r)
    return best


def _corner_on_part(parts: _Parts, c1, d1, c2, d2, where, tol: float, touch_tol, slack: float):
    """The part two straights that meet at a corner both lie on (the cable goes round it between points)."""
    best = None
    for k in range(len(parts)):
        a, c = parts.a[k], parts.c[k]
        if abs(float(a @ d1)) > math.sin(2.0 * SAME_PLANE) or abs(float(a @ d2)) > math.sin(2.0 * SAME_PLANE):
            continue
        feet, dist, sides = [], [], []
        for cc, dd in ((c1, d1), (c2, d2)):
            w = _unit(_cross(a, dd))                   # square to both the axis and the straight
            off = float((cc - c) @ w)
            foot = cc + dd * float(((c - cc) - off * w) @ dd) / max(1.0 - float(a @ dd) ** 2, 1e-12)
            feet.append(foot)
            dist.append(abs(off))
            sides.append(_side(foot, c + a * float((foot - c) @ a), a, dd))
        if sides[0] != sides[1] or abs(dist[0] - dist[1]) > 4.0 * tol:
            continue
        if max(np.linalg.norm(feet[0] - where), np.linalg.norm(feet[1] - where)) > slack + 2.0 * dist[0] * math.tan(
                0.5 * math.acos(float(np.clip(d1 @ d2, -1.0, 1.0)))):
            continue
        mean = 0.5 * (dist[0] + dist[1])
        place, seat_r, touch = parts.seat(k, float((where - c) @ a))
        if seat_r > 0.0 and _rests(mean - seat_r, touch_tol) and (best is None or abs(mean - seat_r) < abs(best[4])):
            best = (k, place, seat_r, touch, mean - seat_r)
    return best


# -- the reading -------------------------------------------------------------------------------------------------

def _wheel_of(parts, hit, at_point, heading):
    k, _, seat_r, touch, gap = hit
    a, c = parts.a[k], parts.c[k]
    centre = c + a * float((at_point - c) @ a)
    return {"kind": "WRAP", "part": k, "c": centre, "n": a, "r": seat_r, "side": _side(at_point, centre, a, heading),
            "surface": touch, "gap": gap}


def _touching(w1, w2):
    """How two wheels after each other stand: ("flat", gap between the circles, …) when their axes are parallel,
    ("cross", the length a straight between them has, the step between them where they are nearest, …) when
    not."""
    n1, n2 = w1["n"], w2["n"]
    cos = float(n1 @ n2)
    d = w2["c"] - w1["c"]
    if np.linalg.norm(_cross(n1, n2)) < math.sin(SAME_PLANE) * 1e-3:
        flat = d - float(d @ n1) * n1
        rho = w1["side"] * w1["r"] - w2["side"] * (1.0 if cos >= 0.0 else -1.0) * w2["r"]
        return "flat", float(np.linalg.norm(flat)) - abs(rho), flat, rho
    def step(t):                                         # from where circle 1 runs along t to where circle 2 does
        e1 = w1["side"] * _unit(_cross(t, n1))
        e2 = w2["side"] * _unit(_cross(t, n2))
        return (w2["c"] + w2["r"] * e2) - (w1["c"] + w1["r"] * e1)

    # the straight between them runs along the line both planes share (where the planes are nearly one: the way
    # the cable's points run there)
    heading = _unit(w1["t_out"] + w2["t_in"])
    shared = _cross(n1, n2)
    t = _unit(shared) * (1.0 if float(shared @ heading) >= 0.0 else -1.0) if np.linalg.norm(shared) > 0.3 else heading
    run = float(step(t) @ t)
    # … and where the two circles come nearest to each other, each at the point where it runs the same way
    gap = step(t)
    for _ in range(8):
        e1, e2 = _square(t)
        jac = np.stack([(step(_unit(t + _NUDGE * e)) - gap) / _NUDGE for e in (e1, e2)], axis=1)
        lhs = jac.T @ jac
        x = np.linalg.solve(lhs + (1e-9 * np.trace(lhs) + 1e-30) * np.eye(2), -jac.T @ gap)
        x = x * min(1.0, 0.3 / max(float(np.abs(x).max()), 1e-300))
        new = _unit(t + x[0] * e1 + x[1] * e2)
        if not float(np.linalg.norm(step(new))) < float(np.linalg.norm(gap)):
            break
        t, gap = new, step(new)
    return "cross", run, gap, t


def _joined(wheels, tol: float) -> list:
    """The pairs of wheels (index of the first) that follow each other directly: no straight piece was found
    between them, and their fits are no further apart than they can be wrong (else there is a short straight
    that has too few points to be a piece). At least one of the two is a bend (a part is never moved)."""
    def loose(w):                                        # how far a fitted circle may be off, in fit tolerances
        if w["kind"] == "WRAP" or w["corner"]:
            return 0.0
        return w["r"] / (max(w["bulge"], 1e-12) * math.sqrt(w["hi"] - w["lo"] + 1))

    out = []
    for i in range(len(wheels) - 1):
        w1, w2 = wheels[i], wheels[i + 1]
        if "BEND" not in (w1["kind"], w2["kind"]) or w1["after"] is not None or w2["before"] is not None:
            continue
        how = _touching(w1, w2)
        if how[1] < tol * (1.0 + loose(w1) + loose(w2)) and (how[0] == "cross" or abs(how[3]) > 0.0):
            out.append(i)
    return out


def _apart(w1, w2):
    """How far two wheels that should touch are from touching: the move (3,) that brings wheel 2 to wheel 1."""
    how = _touching(w1, w2)
    if how[0] == "flat":
        dist = float(np.linalg.norm(how[2]))
        return how[2] / dist * how[1] if dist > 0.0 else np.zeros(3)
    return how[2]


def _snap(wheels, joined) -> None:
    """Arcs that follow each other directly are made to touch exactly (their fits are a hair apart or into each
    other): a bend is moved, a part is not. Twice with the move shared between the two, then once forwards
    moving the later bend and once backwards moving the earlier, so that a row of arcs ends up touching all along."""
    for order, later in ((joined, 0.5), (joined, 0.5), (joined, 1.0), (joined[::-1], 0.0)):
        for i in order:
            w1, w2 = wheels[i], wheels[i + 1]
            move = _apart(w1, w2)
            share = 1.0 if w1["kind"] != "BEND" else (0.0 if w2["kind"] != "BEND" else later)
            w2["c"] = w2["c"] - share * move
            w1["c"] = w1["c"] + (1.0 - share) * move


def _refine(wheels, joined, pts, drawn) -> bool:
    """Fit all bends together: each bend's centre (in its plane) and radius are moved so that the whole path –
    arcs and the straights between them, which touch the arcs – lies as near to the points as it can
    (least squares, a few Gauss-Newton steps; arcs that follow each other directly are kept touching). A short
    bend between long straights is known far better this way than from its own few points. True when something
    was moved."""
    free = [i for i, w in enumerate(wheels) if w["kind"] == "BEND" and not w["corner"]]
    if not free:
        return False
    W = len(wheels)
    frames = {i: _square(wheels[i]["n"]) for i in free}

    def nudge(i, k, by):
        w = wheels[i]
        if k < 2:
            w["c"] = w["c"] + by * frames[i][k]
        else:
            w["r"] = w["r"] + by

    def ties():
        return np.concatenate([_apart(wheels[i], wheels[i + 1]) for i in joined]) * _TIE if joined else np.zeros(0)

    def local(ch, i):
        """The path from wheel i - 1 to wheel i + 1 on its own (its ends stay where they are)."""
        lo, hi = max(i - 1, 0), min(i + 1, W - 1)
        model = [Wheel(w["c"], w["n"], w["r"], w["side"]) for w in wheels[lo:hi + 1]]
        start = ch.p_in[0, lo] if lo else ch.S[0]
        end = ch.p_out[0, hi] if hi < W - 1 else ch.E[0]
        sub = _one(start, model, end, bool(lo) or ch.on0, hi < W - 1 or ch.on1, held=True)
        return _Drawn(sub) if sub.code[0] == 0 else None

    moved = False
    damp = 1e-3
    ch, shape = drawn()
    vec, _, piece = shape.nearest(pts)
    tie = ties()
    cost = float((vec * vec).sum() + (tie * tie).sum())
    for _ in range(REFITS):
        jac = np.zeros((3 * len(pts) + len(tie), 3 * len(free)))
        for col, i in enumerate(free):
            near = np.isin(piece, [i, i + 1, W + i, W + 1 + i, W + 2 + i])
            base = local(ch, i)
            if base is None or not near.any():
                continue
            rows = np.flatnonzero(near)
            rows = (3 * rows[:, None] + np.arange(3)[None, :]).ravel()
            was = base.nearest(pts[near])[0]
            for k in range(3):
                nudge(i, k, _STEP)
                now = local(ch, i)
                if now is not None:
                    jac[rows, 3 * col + k] = ((now.nearest(pts[near])[0] - was) / _STEP).ravel()
                    if len(tie):
                        jac[3 * len(pts):, 3 * col + k] = (ties() - tie) / _STEP
                nudge(i, k, -_STEP)
        res = np.concatenate([vec.ravel(), tie])
        lhs, rhs = jac.T @ jac, -jac.T @ res
        better = False
        for _ in range(6):
            try:
                step = np.linalg.solve(lhs + damp * np.diag(np.diag(lhs)) + 1e-12 * np.eye(len(lhs)), rhs)
            except np.linalg.LinAlgError:
                break
            keep = [(w["c"].copy(), w["r"]) for w in wheels]
            for col, i in enumerate(free):
                for k in range(3):
                    nudge(i, k, step[3 * col + k])
            _snap(wheels, joined)                        # arcs that touch stay touching
            ch2, shape2 = drawn()
            if shape2 is not None and all(wheels[i]["r"] > 0.0 for i in free):
                vec2, _, piece2 = shape2.nearest(pts)
                tie2 = ties()
                cost2 = float((vec2 * vec2).sum() + (tie2 * tie2).sum())
                if cost2 < cost:
                    gain = cost - cost2
                    ch, shape, vec, piece, tie, cost = ch2, shape2, vec2, piece2, tie2, cost2
                    damp, better, moved = max(damp / 3.0, 1e-9), True, True
                    break
            for w, (c, r) in zip(wheels, keep):          # no better: back, and a more careful step
                w["c"], w["r"] = c, r
            damp *= 10.0
        if not better or gain < 1e-6 * cost:
            break
    return moved


def read_cable(points, radius: float, rounds: list[Round], touch_tol: float | None = None,
               fit_tol: float | None = None, max_deviation: float | None = None) -> Reading:
    """Read a cable drawn in CAD: its contacts and the path over them.

    ``points`` (n, 3): the CAD centreline, about equally spaced (``centreline(...).points``: a point every cable
    radius; at least 6 on every arc). ``radius``: the cable's. ``rounds``: the round parts near it.

    1. The points are cut into the fewest straights and arcs that fit them within the fit tolerance. A stretch
       that is neither (a spline, a coil with a pitch) is refused.
    2. An arc that lies on a round part – its points keep one distance from the part's axis, and that distance
       is where the cable rests on the part (``seat``) within ``touch_tol`` – is a WRAP: centre, axis and radius
       come from the part (an arc cut in two on one part is one WRAP). Another arc is a BEND: the fitted circle.
       Two straights that meet at a corner (a tight bend with less than 3 points on it) get the part both lie
       on, else a bend that touches both. A turn of less than 1° is no bend: the cable is read straight there,
       unless that leaves the path too far from the points.
    3. The bends' planes are set (``_planes``), arcs that follow each other directly are made to touch, and all
       bends are fitted together so that the whole path – solved with ``held`` True, the arcs in their planes –
       lies as near to the points as it can.
    4. A round part the centreline passes at its seat distance, crossing its axis within 20° of square, that is
       round all the way and no WRAP there, is a TOUCH: it only turns. A part given twice is one TOUCH.

    **The fit tolerance** (``fit_tol`` None): first the usual one, 0.5 mm or 1 % of the radius – what the
    centreline of a faceted mesh is good to. When that does not read, or leaves the path further from the points
    than twice the tolerance (a thin clean rope's short straights and bends are lost in 0.5 mm), a quarter of it,
    and so on down to what the points' own roughness allows (``_noise``); last 2.5 times the usual one. The
    first that reads is taken. A number given as ``fit_tol`` is used as it is.

    ``touch_tol``: how far the cable may be drawn from where it rests on a part that carries it (default 2 mm, or
    a quarter of the radius: ``TOUCH_TOL``, which has one share for air between them and one for into the part).

    ``start`` / ``end`` are the centreline's ends (put in the first / last arc's plane when the cable starts or
    ends on an arc), ``path`` is ``solve(start, wheels of the WRAP and BEND contacts, end, start_on_wheel,
    end_on_wheel, held=True)``, ``deviation`` the furthest a point is from it. A reading with ``deviation`` above
    ``max_deviation`` (default 2 mm or a quarter of the radius; a cable drawn off its parts may be that much
    further) is refused: its contacts and path are still given, ``problem`` says where and by how much.

    Never raises on a centreline that cannot be read: ``ok`` False and ``problem`` in plain words (a stretch that
    is neither straight nor an arc, a path that cannot be solved – its contacts numbered as in ``contacts`` –, a
    path beside the cable)."""
    radius = float(radius)
    try:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    except (TypeError, ValueError):
        pts = np.zeros((0, 3))
    ends = [pts[0].copy(), pts[-1].copy()] if len(pts) else [np.zeros(3), np.zeros(3)]

    def failed(problem):
        return Reading(False, problem, [], ends[0], ends[1], False, False, _no_path(0, problem), 0.0)

    if len(pts) < 2 or not np.isfinite(pts).all() or not (radius > 0.0 and math.isfinite(radius)):
        return failed("The cable's centreline could not be read (too few points, or not numbers).")
    keep = np.r_[True, np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9]
    pts = pts[keep]
    if len(pts) < 2:
        return failed("The cable's centreline has no length.")
    step = float(np.median(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    parts = _Parts(rounds or [], radius)
    if touch_tol is None:                                # (air between the cable and the part, drawn into the part)
        reach = (max(TOUCH_TOL[0], TOUCH_TOL[1] * radius), max(TOUCH_TOL[0], TOUCH_TOL[2] * radius))
    else:
        reach = (float(touch_tol), float(touch_tol))
    limit = max(MAX_DEVIATION[0], MAX_DEVIATION[1] * radius) if max_deviation is None else float(max_deviation)
    # the fit tolerance: the usual one first (0.5 mm / 1 % of the radius: what a faceted mesh's centreline is good
    # to); when that does not read – a thin clean rope's short bends and straights are lost in it – tighter, down
    # to what the points' own noise allows; last a wider one (a Draft mesh)
    if fit_tol is not None:
        tols = [float(fit_tol)]
    else:
        fine = max(6.0 * _noise(pts), FINE_TOL * radius, 2e-6)
        usual = max(FIT_TOL[0], FIT_TOL[1] * radius, fine)
        tols = [usual]
        while tols[-1] / 4.0 >= fine:
            tols.append(tols[-1] / 4.0)
        if tols[-1] > 1.5 * fine:
            tols.append(fine)
        tols.append(2.5 * usual)
    best = None
    for tol in tols:
        got = _shaped(pts, along, parts, radius, tol, reach, limit, step)
        if best is None or got["rank"] < best["rank"]:
            best = got
        if got["rank"][0] == 0 and got["rank"][1] <= 2.0 * tol + _drawn_off(got["wheels"]):
            best = got                                   # read, and as near to the points as the fit promised
            break
    if best["ch"] is None:
        return failed(best["problem"])
    wheels, ch, shape, on0, on1 = best["wheels"], best["ch"], best["shape"], best["on0"], best["on1"]
    ends = best["ends"]

    # the contacts
    numbers = {}

    def name(i):
        return f"contact {numbers.get(i, i) + 1}"

    touches = _touches(parts, pts, along, wheels, reach)
    order = sorted([(w["s"], 0, i) for i, w in enumerate(wheels)] + [(t["s"], 1, j) for j, t in enumerate(touches)])
    for place, (_, what, i) in enumerate(order):
        if what == 0:
            numbers[i] = place
    path = _path(ch, None, STEP, name)
    contacts = []
    for _, what, i in order:
        if what == 0:
            w = wheels[i]
            k = w["part"]
            mid = float(shape.arc_s[i] + 0.5 * shape.arcs[i]) if shape is not None else w["s"]
            contacts.append(Contact(w["kind"], parts.rounds[k].key if k >= 0 else None, w["c"].copy(), w["n"].copy(),
                                    float(w["r"]), float(w["surface"]), int(w["side"]), mid,
                                    float(ch.wrap[0, i]) if path.ok else 0.0, float(w["gap"]),
                                    parts.full(k) if k >= 0 else False))
        else:
            t = touches[i]
            contacts.append(Contact("TOUCH", parts.rounds[t["part"]].key, t["c"], parts.a[t["part"]].copy(), t["dist"],
                                    t["surface"], t["side"], t["s"], 0.0, t["gap"], parts.full(t["part"])))
    if not path.ok:
        return Reading(False, path.problem, contacts, ends[0], ends[1], on0, on1, path, 0.0)
    vec, s_on, _ = shape.nearest(pts)
    for c, (_, what, i) in zip(contacts, order):         # a TOUCH's place, counted along the path like the others
        if what == 1:
            c.s = float(np.interp(c.s, along, s_on))
    contacts.sort(key=lambda c: c.s)
    off = np.linalg.norm(vec, axis=1)
    worst = int(np.argmax(off))
    if off[worst] > limit + _drawn_off(wheels):
        problem = (f"The path that can be read lies {off[worst] * 1000.0:.1f} mm beside the cable as it is drawn, "
                   f"{along[worst]:.2f} m from its start: a bend there has too few points on it to be read, or it "
                   f"is no round bend.")
        return Reading(False, problem, contacts, ends[0], ends[1], on0, on1, path, float(off[worst]))
    return Reading(True, "", contacts, ends[0], ends[1], on0, on1, path, float(off[worst]))


def _noise(pts) -> float:
    """How rough the points are (one standard deviation, m), from their third differences: those are nothing on
    a straight and next to nothing on an arc, so what is left is the points' own noise."""
    if len(pts) < 8:
        return 0.0
    d3 = pts[3:] - 3.0 * pts[2:-1] + 3.0 * pts[1:-2] - pts[:-3]
    return float(np.median(np.linalg.norm(d3, axis=1))) / 6.9


def _shaped(pts, along, parts, radius: float, tol: float, reach, limit: float, step: float) -> dict:
    """Steps 1 – 3 of ``read_cable`` with one fit tolerance: the wheels and the solved path. ``rank`` says how
    good it is: (0, deviation) read and near the points, (1, deviation) read but further off than ``limit``,
    (2, 0) not read (``problem`` says why, ``ch`` is None when there is no path at all)."""
    out = {"rank": (2, 0.0), "ch": None, "shape": None, "wheels": [], "on0": False, "on1": False,
           "ends": [pts[0].copy(), pts[-1].copy()], "problem": ""}
    kept = _pieces(pts, tol)
    every = []
    for k, pc in enumerate(kept):
        if pc["kind"] == "arc":
            lo, hi = pc["own"]
            seg = pts[lo:hi + 1]
            hit = _arc_on_part(parts, seg, tol, reach)
            mid = seg[len(seg) // 2]
            if hit is not None:
                w = _wheel_of(parts, hit, mid, _unit(_cross(pc["n"], mid - pc["c"])))
            else:
                w = {"kind": "BEND", "part": -1, "c": pc["c"], "n": pc["n"], "r": pc["r"], "side": 1, "surface": 0.0,
                     "gap": 0.0}
            beside = [kept[q] if 0 <= q < len(kept) and kept[q]["kind"] == "line" else None for q in (k - 1, k + 1)]
            w.update(lo=lo, hi=hi, s=float(along[(lo + hi) // 2]), corner=False, bulge=pc["bulge"],
                     t_in=_unit(seg[1] - seg[0]), t_out=_unit(seg[-1] - seg[-2]), before=beside[0], after=beside[1],
                     turn=float(along[hi] - along[lo]) / pc["r"])
            if every and w["part"] >= 0 and every[-1]["part"] == w["part"] and every[-1]["side"] == w["side"]:
                every[-1].update(hi=hi, t_out=w["t_out"], after=w["after"], turn=every[-1]["turn"] + w["turn"],
                                 s=float(along[(every[-1]["lo"] + hi) // 2]))      # one wrap cut in two: one again
                continue
            every.append(w)
        elif k and kept[k - 1]["kind"] == "line":
            # two straights that meet: the cable goes round something between two points
            one, two = kept[k - 1], pc
            turn = math.acos(float(np.clip(one["d"] @ two["d"], -1.0, 1.0)))
            if turn < CORNER:
                continue
            cross = _cross(one["d"], two["d"])
            gap = two["c"] - one["c"]
            den = float(cross @ cross)
            f1 = float(_cross(gap, two["d"]) @ cross) / den
            f2 = float(_cross(gap, one["d"]) @ cross) / den
            where = 0.5 * ((one["c"] + f1 * one["d"]) + (two["c"] + f2 * two["d"]))
            hit = _corner_on_part(parts, one["c"], one["d"], two["c"], two["d"], where, tol, reach, 2.0 * step + tol)
            if hit is not None:
                w = _wheel_of(parts, hit, where, _unit(one["d"] + two["d"]))
            else:
                w = _corner_bend(pts, one, two, where, turn, radius, step)
            idx = int(np.argmin(np.linalg.norm(pts - where, axis=1)))
            w.update(lo=idx, hi=idx, s=float(along[idx]), corner=True, bulge=0.0, t_in=one["d"], t_out=two["d"],
                     before=one, after=two, turn=turn)
            every.append(w)
    odd = _not_arcs(pts, kept, tol) or _gradual(every)
    if odd is not None:
        lo, hi = odd
        out["problem"] = (f"The cable's shape between {along[lo]:.1f} m and {along[hi]:.1f} m from its start is "
                          f"neither straight nor a round bend (a spline, or a coil with a pitch): its path cannot "
                          f"be read.")
        return out
    # a turn of less than a degree is no bend: the cable is read straight there (a part it lies on is then a
    # roller it rests on) – unless that leaves the path too far from the points
    slight = [w for w in every if w["turn"] < SLIGHT]
    for wheels in ([w for w in every if w["turn"] >= SLIGHT], every) if slight else (every,):
        wheels = [dict(w) for w in wheels]
        got = _fitted(wheels, pts, tol)
        if got["rank"][0] == 0 and got["rank"][1] > limit + _drawn_off(wheels):
            got["rank"] = (1, got["rank"][1])
        if got["rank"] < out["rank"] or out["ch"] is None:
            out.update(got, wheels=wheels)
        if got["rank"][0] == 0:
            break
    return out


def _drawn_off(wheels) -> float:
    """The furthest the CAD cable is drawn from where it rests on a part it goes round: the path, which lies on
    the parts, may be that much further from the points."""
    return max([abs(w["gap"]) for w in wheels if w["kind"] == "WRAP"], default=0.0)


def _fitted(wheels, pts, tol: float) -> dict:
    """The wheels' planes, arcs that touch, the path and the fit of all bends together (steps 2 – 3)."""
    ends = [pts[0].copy(), pts[-1].copy()]
    on0 = bool(wheels) and not wheels[0]["corner"] and wheels[0]["before"] is None      # it starts / ends on an arc
    on1 = bool(wheels) and not wheels[-1]["corner"] and wheels[-1]["after"] is None
    _planes(wheels, pts, tol)

    def drawn():
        model = [Wheel(w["c"], w["n"], w["r"], w["side"]) for w in wheels]
        if on0:                                          # a cable that starts on an arc starts in the arc's plane
            ends[0] = pts[0] - model[0].axis * float((pts[0] - model[0].centre) @ model[0].axis)
        if on1:
            ends[1] = pts[-1] - model[-1].axis * float((pts[-1] - model[-1].centre) @ model[-1].axis)
        ch = _one(ends[0], model, ends[1], on0, on1, held=True)
        return ch, (_Drawn(ch) if ch.code[0] == 0 else None)

    joined = _joined(wheels, tol)
    _snap(wheels, joined)
    ch, shape = drawn()
    if shape is not None:
        if _refine(wheels, joined, pts, drawn):
            _snap(wheels, joined)
            ch, shape = drawn()
    rank = (2, 0.0) if shape is None else (0, float(np.linalg.norm(shape.nearest(pts)[0], axis=1).max()))
    return {"rank": rank, "ch": ch, "shape": shape, "on0": on0, "on1": on1, "ends": ends, "problem": ""}


def _gradual(wheels):
    """Two bends in the air that follow each other directly and are nearly the same bend (the same way round, in
    nearly the same plane, radii less than half apart): a bend that changes little by little – a spline, a coil
    with a pitch, or one arc that a tolerance too tight for its points cut in two. (first point, last point) or
    None."""
    for one, two in zip(wheels, wheels[1:]):
        if one["kind"] != "BEND" or two["kind"] != "BEND" or one["corner"] or two["corner"]:
            continue
        if one["after"] is not None or two["before"] is not None:
            continue
        k1, k2 = one["n"] / one["r"], two["n"] / two["r"]
        if float(np.linalg.norm(k1 - k2)) < 0.5 * max(1.0 / one["r"], 1.0 / two["r"]):
            return one["lo"], two["hi"]
    return None


def _planes(wheels, pts, tol: float) -> None:
    """Every bend's plane. Bends that follow each other in one plane, as far as their points can tell (at most 2°
    apart), are put in one plane: a part's axis when one of them lies on a part, else their best common one. A
    straight next to a bend lies in the bend's
    plane, and a long straight is known far better than a short bend's own plane: two straights that are not
    parallel give the plane outright, one turns it so that the straight lies in it. (The solver lets the cable
    slide along a wheel's axis: a plane a hair askew would carry a long straight's end millimetres away.)"""
    def loose(w):                                        # how far (rad) a wheel's points leave its plane open
        if w["kind"] == "WRAP":
            return 0.0
        return tol / (max(w["bulge"], 1e-12) * math.sqrt(w["hi"] - w["lo"] + 1))

    i = 0
    while i < len(wheels):
        j = i
        while j + 1 < len(wheels):
            apart = float(np.linalg.norm(_cross(wheels[j]["n"], wheels[j + 1]["n"])))
            if apart >= math.sin(min(SAME_PLANE, 1e-4 + 2.0 * (loose(wheels[j]) + loose(wheels[j + 1])))):
                break
            j += 1
        group = wheels[i:j + 1]
        i = j + 1
        held = [w for w in group if w["kind"] == "WRAP"]
        free = [w for w in group if w["kind"] == "BEND"]
        if not free:
            continue
        if held:
            ref = held[0]["n"]
        else:
            ref, doubt = np.zeros(3), 0.0
            for w in free:
                trust = (w["hi"] - w["lo"] + 1) * max(w["bulge"], 1e-9) ** 2
                ref = ref + trust * w["n"] * (1.0 if float(w["n"] @ free[0]["n"]) >= 0.0 else -1.0)
                doubt += trust
            ref = _unit(ref)
            doubt = 1.0 / math.sqrt(doubt) if doubt > 0.0 else math.inf     # how far the points leave it open
            lines = {id(ln): ln for w in group for ln in (w["before"], w["after"]) if ln is not None and ln["count"] >= LINE}
            lines = sorted(lines.values(), key=lambda ln: -ln["long"] * math.sqrt(ln["count"]))
            pair = None
            for ln in lines[1:]:
                cross = _cross(lines[0]["d"], ln["d"])
                sin = float(np.linalg.norm(cross))
                open_ = math.hypot(3.5 / (lines[0]["long"] * math.sqrt(lines[0]["count"])),
                                   3.5 / (ln["long"] * math.sqrt(ln["count"]))) / max(sin, 1e-12)
                if sin > 0.02 and (pair is None or open_ < pair[0]):
                    pair = (open_, cross / sin)
            if pair is not None and pair[0] < doubt:
                ref = pair[1] if float(pair[1] @ ref) >= 0.0 else -pair[1]
            else:
                for ln in lines:
                    ref = _unit(ref - float(ref @ ln["d"]) * ln["d"])
        for w in free:
            n = ref if float(ref @ w["n"]) >= 0.0 else -ref
            if w["corner"]:
                w["n"] = n
                continue
            got = _fit_circle(pts[w["lo"]:w["hi"] + 1], n)
            if got is not None and abs(got[2] - w["r"]) < 0.2 * w["r"]:
                w["c"], w["n"], w["r"] = got[0], got[1], got[2]


def _corner_bend(pts, one, two, where, turn: float, radius: float, step: float) -> dict:
    """The bend between two straights that meet at a corner: an arc that touches both, of the radius that lies
    nearest to the points round the corner (at least the cable's own radius)."""
    n = _unit(_cross(one["d"], two["d"]))
    inward = _unit(two["d"] - one["d"])
    near = pts[np.linalg.norm(pts - where, axis=1) < 6.0 * step]
    most = max(4.0 * step / max(math.tan(0.5 * turn), 1e-6), radius)
    best, least = radius, math.inf
    for r in np.geomspace(radius, most, 48) if most > radius else [radius]:
        c = where + inward * r / math.cos(0.5 * turn)
        arm = near - c
        flat = arm - np.outer(arm @ n, n)
        cut = r * math.tan(0.5 * turn)
        t1, t2 = (near - where) @ one["d"], (near - where) @ two["d"]
        on_arc = (t1 > -cut) & (t2 < cut)
        d_arc = np.abs(np.linalg.norm(flat, axis=1) - r)
        d1 = np.linalg.norm((near - where) - np.outer(t1, one["d"]), axis=1)
        d2 = np.linalg.norm((near - where) - np.outer(t2, two["d"]), axis=1)
        err = float((np.where(on_arc, d_arc, np.where(t1 <= -cut, d1, d2)) ** 2).sum())
        if err < least - 1e-18:
            best, least = float(r), err
    return {"kind": "BEND", "part": -1, "c": where + inward * best / math.cos(0.5 * turn), "n": n, "r": best, "side": 1,
            "surface": 0.0, "gap": 0.0}


def _not_arcs(pts, pieces, tol: float):
    """A stretch that is neither straight nor an arc: (first point, last point), or None.

    Where a straight meets an arc, or an arc another arc, the shape changes at one place: a run that starts in
    the middle of the one piece cannot go far into the next. On a spline or a coil with a pitch the bend changes
    little by little: such a run goes on well into the next piece."""
    win = _Window(pts, tol)
    n = len(pts)
    for k in range(len(pieces) - 1):
        one, two = pieces[k], pieces[k + 1]
        if one["kind"] != "arc" and two["kind"] != "arc":
            continue
        size1, size2 = one["own"][1] - one["own"][0] + 1, two["own"][1] - two["own"][0] + 1
        if min(size1, size2) < 8 or min(pc.get("bulge", math.inf) for pc in (one, two)) < 4.0 * tol:
            continue
        i = (one["own"][0] + one["own"][1]) // 2
        win.kind = None
        j = i
        while j + 1 < n and win.fits(i, j + 1):
            j += 1
        over = j - one["own"][1]
        if over >= max(4, 0.3 * size2) and over >= 0.3 * (one["own"][1] - i):
            return one["own"][0], two["own"][1]
    return None


def _touches(parts: _Parts, pts, along, wheels, touch_tol) -> list:
    """The round parts the centreline passes at the distance where the cable rests on them (and that it does not
    wrap there): each a dict with part, centre, distance, surface, side, s, gap. One per pass: of the low points
    the noise makes near one pass the lowest counts; a part given twice (the same axis) counts once."""
    reach = max(touch_tol)
    out = []
    n = len(pts)
    if not len(parts) or n < 3:
        return out
    tan = _unit(np.gradient(pts, axis=0))
    step = float(np.median(np.diff(along)))

    def room(rest):                                      # how far along the cable a part of this size is "near"
        return math.sqrt(2.0 * rest * reach) + 3.0 * step

    wrapped = [(w["part"], along[w["lo"]] - room(w["r"]), along[w["hi"]] + room(w["r"])) for w in wheels if w["part"] >= 0]
    found = {}
    for k0 in range(0, len(parts), 64):                  # in blocks: parts x points
        ks = np.arange(k0, min(k0 + 64, len(parts)))
        rho, _ = parts.polar(ks, pts[None, :, :])
        d2 = rho * rho
        low = np.zeros_like(d2, dtype=bool)
        low[:, 1:-1] = (d2[:, 1:-1] <= d2[:, :-2]) & (d2[:, 1:-1] < d2[:, 2:])
        low &= rho <= rho.min(axis=1, keepdims=True) + 2.0 * (parts.rope + reach + step)   # (only the nearest passes)
        for row in np.flatnonzero(low.any(axis=1)):
            low[row] &= rho[row] <= parts.reach(int(ks[row])) + parts.rope + reach + step
        for row, i in zip(*np.nonzero(low)):
            k = int(ks[row])
            a, c = parts.a[k], parts.c[k]
            # the lowest place between the points: a parabola through three of them
            y0, y1, y2 = d2[row, i - 1], d2[row, i], d2[row, i + 1]
            x0, x2 = along[i - 1] - along[i], along[i + 1] - along[i]
            den = x0 * x2 * (x0 - x2)
            aa = (x2 * (y0 - y1) - x0 * (y2 - y1)) / den
            bb = (x0 * x0 * (y2 - y1) - x2 * x2 * (y0 - y1)) / den
            x = float(np.clip(-bb / (2.0 * aa), x0, x2)) if aa > 0.0 else 0.0
            dist = math.sqrt(max(y1 + bb * x + aa * x * x, 0.0))
            s = float(along[i] + x)
            if any(part == k and lo <= s <= hi for part, lo, hi in wrapped):
                continue
            heading = tan[i]
            if abs(float(heading @ a)) > math.sin(SQUARE):
                continue
            j = i + 1 if x >= 0.0 else i - 1
            here = pts[i] + abs(x) / abs(along[j] - along[i]) * (pts[j] - pts[i])
            if dist > parts.reach(k, float((here - c) @ a)) + parts.rope + reach:
                continue                                 # the part does not reach the cable there
            _, seat_r, touch = parts.seat(k, float((here - c) @ a))
            if not seat_r > 0.0 or not _rests(dist - seat_r, touch_tol):
                continue
            if not parts.full(k):                        # a round edge of a frame, a chain link's eye: it cannot turn
                continue
            centre = c + a * float((here - c) @ a)
            hit = {"part": k, "c": centre, "dist": dist, "surface": touch, "side": _side(here, centre, a, heading),
                   "s": s, "gap": dist - seat_r, "room": room(seat_r)}
            passes = found.setdefault(k, [])
            for q, other in enumerate(passes):           # the same pass again: keep the lower
                if abs(other["s"] - s) <= hit["room"]:
                    if dist < other["dist"]:
                        passes[q] = hit
                    break
            else:
                passes.append(hit)
    for passes in found.values():
        for hit in passes:
            a = parts.a[hit["part"]]
            twice = any(abs(o["s"] - hit["s"]) < 1e-6 + 1e-3 * hit["room"] and np.linalg.norm(o["c"] - hit["c"]) < 1e-6
                        and abs(float(parts.a[o["part"]] @ a)) > 1.0 - 1e-9 for o in out)
            if not twice:
                out.append(hit)
    return out


# ---------------------------------------------------------------------------------------------------------
# a long cable's centreline
# ---------------------------------------------------------------------------------------------------------

CHUNK = 60.0                    # a long cable is read in pieces of this many radii …
OVERLAP = 8.0                   # … that overlap by this many, of which half is thrown away at each cut end
LONG = 200.0                    # a tube up to this many radii long is read in one go


def centreline(verts, tris, spacing: float | None = None):
    """The centreline of a cable's mesh for ``read_cable``: a ``flex_fit.Tube`` (ok, problem, points equally
    spaced from end 0 to end 1, radius, length, t0, t1) with a point every ``spacing`` (default: the radius).
    End 0 is the end with the smaller x (then y, then z), as ``tube_centreline`` has it.

    ``flex_fit.tube_centreline`` is made for hoses: it cuts a tube at most 1024 times and finds its first rough
    line from 96 cuts. On a cable hundreds of radii long that is too coarse (a 300 m cable of 70 mm radius with
    bends of 2 m: up to 0.46 m beside the tube's middle; a 188 m cable with bends of 4 m: 1 mm inside every bend).
    So a cable longer than 200 radii is read in overlapping pieces of about 60 radii, each with
    ``tube_centreline``, and the pieces' lines are joined. The pieces are cut by the distance along the surface
    from one end (a cable that comes back beside itself is no problem), behind the long facets of a straight run,
    never through them. Where a piece cannot be read the whole tube is read in one go after all."""
    from . import flex_fit

    v = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(tris).reshape(-1, 3).astype(np.int64)
    rough = flex_fit.tube_centreline(v, t, 65)
    if not rough.ok:
        return rough
    radius = rough.radius
    step = radius if spacing is None else float(spacing)

    def in_one_go():
        fine = flex_fit.tube_centreline(v, t, max(int(round(rough.length / step)) + 1, 2))
        return fine if fine.ok else rough

    if rough.length <= LONG * radius:
        return in_one_go()
    welded = flex_fit._weld(v, t)
    if welded is None or isinstance(welded, str):
        return in_one_go()
    p, tri, _ = welded
    _, graph, _ = flex_fit._edges(p, tri)
    far = flex_fit._distances(graph, 0, len(p))
    far[~np.isfinite(far)] = -1.0
    along = flex_fit._distances(graph, int(np.argmax(far)), len(p))      # along the surface from one end
    if not np.isfinite(along).all():
        return in_one_go()
    total = float(along.max())
    lap = OVERLAP * radius
    low, high = along[tri].min(axis=1), along[tri].max(axis=1)
    long_ones = high - low > 0.5 * lap                   # a straight's facets run from one of its ends to the other:
    cut = [0.0]                                          # a cut goes behind them, never through them
    while cut[-1] < total:
        c = min(cut[-1] + CHUNK * radius, total)
        for _ in range(64):
            across = long_ones & (low < c) & (high > c)
            if not across.any():
                break
            c = float(high[across].max())
        if total - c < 0.5 * CHUNK * radius:
            c = total
        cut.append(c)
    count = len(cut) - 1
    line, radii = [], []
    for k in range(count):
        take = (low >= cut[k] - lap) & (high <= cut[k + 1] + lap)
        used = np.unique(tri[take])
        if len(used) < 4:
            return in_one_go()
        back = np.zeros(len(p), dtype=np.int64)
        back[used] = np.arange(len(used))
        long = (cut[k + 1] - cut[k] + 2.0 * lap) / radius
        piece = flex_fit.tube_centreline(p[used], back[tri[take]], int(min(8 * long, 100_000)) + 1)
        if not piece.ok:
            return in_one_go()
        pts = piece.points
        first = p[used][np.argmin(along[used])]          # the piece's end nearer the cable's start
        if np.linalg.norm(pts[0] - first) > np.linalg.norm(pts[-1] - first):
            pts = pts[::-1]
        gone = int(round(0.5 * lap / (piece.length / (len(pts) - 1))))   # the ragged ends where the mesh was cut
        pts = pts[(gone if k else 0):(len(pts) - gone if k < count - 1 else len(pts))]
        if line:                                         # no point twice: go on from where the line so far ends
            last, heading = line[-1][-1], line[-1][-1] - line[-1][-2]
            go = int(np.argmin(np.linalg.norm(pts - last, axis=1)))      # (only the overlap is dropped: a cable
            while go < len(pts) and float((pts[go] - last) @ heading) <= 0.0:   # that turns back later keeps its points)
                go += 1
            pts = pts[go:]
        if len(pts) < 2:
            return in_one_go()
        line.append(pts)
        radii.append(piece.radius)
    line = np.concatenate(line)
    for a, b in zip(line[0], line[-1]):                  # end 0: the smaller x, then y, then z
        if abs(a - b) > 1e-9 * max(total, 1.0):
            if a > b:
                line = line[::-1]
            break
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))])
    n = max(int(round(run[-1] / step)) + 1, 2)
    pts = np.stack([np.interp(np.linspace(0.0, run[-1], n), run, line[:, k]) for k in range(3)], axis=1)
    return flex_fit.Tube(True, "", pts, float(np.median(radii)), float(run[-1]), _unit(line[1] - line[0]),
                         _unit(line[-1] - line[-2]))
