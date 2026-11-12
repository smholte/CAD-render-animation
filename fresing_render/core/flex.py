"""Hoses and cables: the shape between two ends, without Blender (task 0058).

A hose hangs between two fittings. Each fitting holds its end in place and gives it a direction. The hose has a
fixed length, it resists bending, and its own weight pulls it down. Given where the two ends are *now*, this module
works out the centreline: ``n`` points from end 0 to end 1.

Words and units (metres, any right-handed axes; Blender's are Z up):
* p0, p1   – the two ends;
* t0, t1   – unit directions, both pointing along the hose from end 0 to end 1: t0 is the direction the hose
             leaves end 0 in, t1 the direction it arrives at end 1 in;
* length   – along the centreline;
* stiff    – the **bending length** ℓ in metres: ℓ³ = bending stiffness EI / weight per metre. A piece of hose
             about ℓ long, held level at one end, droops clearly under its own weight; a piece much shorter stands
             out like a stick, a piece much longer hangs like a rope. ``stiff_length(diameter, slider)`` turns the
             panel's slider 0 … 1 into ℓ = diameter · 4 · 16**slider: 4 diameters (a rope, a chain, a thin soft
             cable) up to 64 diameters (a stiff hydraulic hose). Roughly, for real ones: a 1" two-wire hydraulic
             hose 40 … 60 diameters (slider 0.85 … 1), a rubber air or water hose 20 … 30 (0.6 … 0.7), an electric
             cable 15 … 30 (0.5 … 0.7), a rope or chain 4 … 8 (0 … 0.25);
* sag      – scales the weight: 1 = real gravity, 0 = no weight (the shape is then set by bending alone and does
             not depend on ``stiff``), in between a hose that is lighter than its stiffness says;
* min_radius – the tightest bend allowed (centreline radius), 0 = no limit;
* guide    – optional: a line of points from end 0 to end 1 that shows how the hose lies (which side it bows to).

The model
---------
An elastic rod that cannot stretch and has no twist stiffness. Per unit of weight its energy is

    (ℓ³ / 2) · ∫ curvature² ds  +  sag · ∫ height ds

and the shape is a minimum of it among all curves of the given length with the given ends and end directions.

The hose is ``n - 1`` straight segments, all exactly h = ``length / (n - 1)`` long. The unknowns are the unit
directions d_i of the segments; the first is t0 and the last is t1 (so the end directions are exact), and
h · Σ d_i = p1 − p0 (so the ends are exact). The curvature at a joint is |d_i+1 − d_i| / Δs, with Δs = h between
two free segments and 1.5 h at the two joints next to the fixed end segments: an end segment stands for the
fitting's clamp *at the end point*, half a segment before its own middle. (With Δs = h there the curve closed
in only in proportion to h when n was raised; with 1.5 h it closes in with h²: the points for n = 33 and n = 65
are 0.4 % of the length apart, for 65 and 129 0.1 %.) The weight is h · Σ height of the points (half for the two
ends). A hose much softer than a segment is long (ℓ under about 3 h) kinks at its fittings inside one segment;
where exactly then depends on n.

Two things are added that no picture shows. The bending length is at least 1/1000 of the length (a rope without
weight would have no shape at all). And every hose keeps a trace of weight, 1/1000 × (ℓ / length)³ of the real
one (it moves a hose by 2.6 µm per metre), which says where "down" is when sag is 0 or the weight has no say: a
hose pushed together between two fittings in line bows downwards, not anywhere. Where the line p0 → p1 is within
~2° of gravity itself, that trace also pulls a little (1/1000 of it) to one side, along the world axis gravity
has least of: only there does turning the whole scene not simply turn the answer.

How it is solved
----------------
Newton's method on the directions: each direction moves in its own tangent plane; the turn of every segment and
the force in the hose come out of one linear system (2 · free segments + 3 unknowns) per step.

* **Coarse to fine.** The hose is first solved with 4 free segments between the two end segments, then with 8,
  15 and 30 (for n = 33: n − 3 halved down to 4), each level starting from the one before. The end segments keep
  their final short length on every level, so a hose that reaches on the fine level reaches on all of them. The
  coarse levels are small and decide *which* shape it is; the fine levels need two or three steps each.
* **A shape that stays.** On the coarse levels (up to 8 free segments, ``_settle``) the step is worked out from
  the eigenvalues of the energy's second derivative: where the energy curves down – a saddle, a shape in balance
  that would fall over – the step goes down the hill instead of to the balance point, and the level is not done
  while it is on a saddle. A step that is too long, or raises the energy, is damped and tried again; every trial
  is first put back exactly on the constraints (unit directions with the right sum: a 3 × 3 Newton iteration on a
  convex problem, ``_close``), so that energies are compared fairly. The finer levels take plain Newton steps
  (``_newton_fast``; and the damped way, ``_newton``, only for a hose whose steps do not shrink).
* **Two shapes.** A hose with slack between fittings that do not lie in one plane very often has two shapes it can
  stay in: one winding like a right-handed screw, one like a left-handed. The coarsest level therefore starts
  three times: from a fold (the first half of the hose in one direction, the second half in another, on the side
  the fittings and the weight push it to) and from that fold wound a little each way. The wound start with less
  energy is taken if it is clearly better than the plain one (``start`` asks for one of the three by name; it
  rarely matters: which of two shapes a hose takes is mostly decided a level later, by the side it leans to).
  A hose with a guide starts once, from the guide, on the 8-segment level.
* It stops when the Newton step is below 1e-4 rad (the error is about its square), not after a fixed number of
  steps. (The design suggested a fixed number of smoothing steps with a constant matrix. That does not reach the
  equilibrium of a stiff hose in an affordable number of steps – it needs about n² of them – and an unfinished
  iteration is not the shape of any hose.)

What that gives, and what it cannot
-----------------------------------
* Exact ends, end directions and segment lengths.
* A pure function: the same inputs give bit for bit the same points, whatever was solved before; a hose solved in
  a batch (in any order, with any others) gets what it gets alone, to rounding.
* Turning or moving the whole scene (gravity with it) turns and moves the answer; mirroring it mirrors the answer.
* The shape follows the ends smoothly as long as it is the same shape. **But very often a hose has two shapes, and
  a function of the present position alone has to choose.** The commonest case: a hose with some slack between
  two fittings that come in line somewhere in the motion (a hose across a hinge). Its bow can lie on either
  side; this function puts it on the side the fittings push it to and the weight pulls it to, and when the arm
  swings through the line the bow flips to the other side in one frame. A real hose stays on the side it was
  installed on. An independent review found a jump in 16 of 32 everyday motions solved frame by frame (hinges,
  slides, turning elbows; 10 … 70 % of the length in one frame, some of them several times, to and fro).
  So a caller that shows a motion should not rely on the frame-by-frame answer, but say how the hose lies:
* **A guide** (``guide=``: a line of points from end 0 to end 1, for instance the hose as it is drawn in the CAD
  pose, carried along by the two parts it is fitted to and blended between them). With a guide the solver starts
  from the guide's shape instead of its own three starts, and it holds the hose's belly – where its middle lies
  beside the line between the ends – in the plane of the guide's belly. That hold stands in for the twist
  stiffness the model lacks: without it a bow is free to swing round the line of its fittings to the other side;
  a real hose would have to twist for that. In its plane the hose is free. The answer is still a pure function
  of the inputs, the guide among them. In the review's 16 jumping motions, with the first frame's shape carried
  along as the guide, 11 no longer jump (all 9 across a hinge); the 5 left are a bow that turns into a loop when
  fittings in line are pushed together to 0.4 × the length (2), soft cables with two hanging shapes (2), and an
  S between two fittings that changes over (1). The caller carries the drawn shape along with ``carried``
  (a share of the turn between the two end parts: the bow is kept across a hinge up to ±90° and more). An elbow
  fitting that spins about its own axis by more than about a third of a turn still makes a jump of its own with
  a guide (one of 28–35 % of the length in the review's cases; such hoses are calm without a guide).
* ``solve_motion`` takes all frames of one hose at once. Where the frame-by-frame answer jumps it follows the
  hose from frame to frame for as long as the shape it is in is one a hose stays in, and lets it snap over –
  once, to the frame's own answer – where it is not. Without a guide that does not save the hose across a hinge
  (in this model the bow on the "wrong" side is a balance point that falls over as soon as the fittings tilt:
  followed honestly it snaps where they come in line); with a guide it follows the held shape.
* A set-up that is exactly symmetric keeps its symmetric shape, also where that is a balance point (two fittings
  exactly in line, pushed together so far that the bow would rather wind out of its plane): the solver only
  leaves a balance point to the side the hose leans to. A motion that passes exactly through such a set-up can
  show the symmetric shape for that one frame.

Not reaching, tight bends, bad numbers
--------------------------------------
* ``short``: the ends are further apart than the hose can reach with its first and last segment in their fittings.
  The points are then the straight line p0 → p1 (stretched, ends exact); ``need`` is the length that would just
  reach. Within 1e-7 of that limit (``TAUT``) the answer is the one shape that still fits: first and last segment
  in their fittings and a straight line between (so at the frame a hose stops reaching it moves by up to a
  segment or two at once).
* ``min_radius`` of the result is the tightest bend along the hose: at a joint between two free segments the
  circle through the three points, h / |d_i+1 − d_i|; at the two joints next to the fittings 1.5 h / |d_i+1 − d_i|,
  because the bend there is spread over 1.5 segments (see The model; a hose that is half a circle reports that
  circle's radius). ``bend_radius(points, hose=True)`` measures the same on any solved points.
* With a limit > 0 the hose is first solved without it. If it bends tighter than the limit somewhere, a bend under
  the limit is made to cost extra energy, steeply (the hose stiffens where it is too tight), and it settles again
  from there: the bend spreads out along the hose as far as the length and the ends allow. ``tight`` is True when
  the result still bends tighter than 0.99 × the limit: the ends force it (too close together for a loop of that
  radius, or a fitting pointing so that the hose must turn sharply right at it), or – rarely – a wider shape
  exists that was not found. A limit the hose keeps anyway changes nothing and costs nothing; one it has to be
  held to makes the solve 1.5 … 4 times slower.
* Any numbers give a result, never an error and never a warning: an end or a length that is not a number or not
  finite gives a straight line between the ends (0 for what was no number), flagged ``short`` with ``need`` inf;
  a direction that is no number takes the line between the ends; gravity that is no number is left out;
  stiffness, sag and limit are brought into the range the arithmetic can carry (stiffness and limit at most 1000
  hose lengths, sag at most a million; no number: 0). No hoses (B = 0) give an empty result. Only shapes that
  make no sense are refused (ValueError): points that are not triples, inputs of different batch sizes, n < 5.

Speed
-----
n = 33, measured in tests/test_flex_core.py (Claude Code web session, 4 cores shared with other work, 13 Nov
2026): one hose 4.5 ms; a batch of 20: 11 ms (20 poses of a U-loop) … 18 ms (20 unrelated hoses, a quarter of
them with fittings pointing sideways or backwards), 10 ms with guides (a guided hose skips the three starts);
5,000 in one call 2.8 s (0.56 ms each). Small batches are slow per hose because every NumPy call has a fixed
cost: solve all hoses of a frame, or all frames of a hose, in one call. From n = 65 on the linear systems are
large enough for the BLAS library to start its threads (1.3 ms per hose in a batch). ``solve_motion`` for 250
frames of one hose: 70 … 80 ms where nothing jumps (with or without a guide); 0.9 s when the hose jumps and is
followed (both ways, with the check that it stays).

NumPy only (Blender's Python has no SciPy). Everything is vectorised over the batch: 20 hoses at one frame, or one
hose at 250 frames, are one call.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

SOFT, STIFF = 4.0, 64.0    # stiff_length: bending length in diameters at slider 0 and 1
MIN_POINTS = 5             # first + last segment are fixed: at least two free ones between
TAUT = 1e-7                # slack (as a share of the free length) under which the hose is simply straight
SHORT = 1e-9               # … and how far past the limit before it counts as too short
TIGHT = 0.99               # ``tight``: the result bends tighter than this share of the limit
CHUNK = 256                # hoses solved together (keeps the matrices in the processor's cache)
END_JOINT = 1.5            # the joint next to a fitting bends over this many segments of hose
JUMP = 6.0                 # solve_motion: a point moving this many times as far as the ends did is a jump

# the model's small additions
_FLOOR = 1e-3              # smallest bending length, as a share of the length (keeps a weightless rope defined)
_GHOST = 1e-3              # the trace of weight every hose keeps, × (bending length / length)³ …
_TILT = 1e-3               # … and its pull to one side, where the hose's line is along gravity
_PENALTY = 1.2e4           # how steeply a bend under the minimum radius costs energy (× the cube of how far)
# the levels
_FIRST = 4                 # free segments on the coarsest level
_SETTLE = 8                # up to this many free segments the shape is made sure to be one that stays
_TWIST = 0.5               # the wound starts on the coarsest level: the fold wound this much (radians) each way
_CLEARLY = 1e-4            # … a wound start wins when its energy is lower by this share of the energy's size
# the steps
_TOL = 1e-4                # Newton step (radians) at which the fine level is done (the error is its square)
_TOL_COARSE = 0.05         # … and the coarse levels (they only give the start)
_MAX_IT = 60               # steps per level at most
_CAP = 0.6                 # largest turn of one segment in one damped step, radians
_TRIES = 4                 # damped tries of one step before the eigenvalues are worked out anew
_KICK = 0.15               # the least step off a saddle, radians …
_ON_IT = 1e-7              # … unless the hose sits on the balance point this exactly (radians): it stays
_CAP_FAST = 1.5            # plain Newton: a larger first step than this goes the damped way
_GROW = 0.7                # … and so does a step that is not clearly smaller than the one before
_FAST_IT = 8               # … or more steps than this
_SHIFT = 1e-12             # added to the second derivative (× the energy's size): a direction in which nothing
                           # changes (a bow free to turn about the line of its ends) stays put
_MOST = 1e3                # stiffness and limit at most this many hose lengths, sag at most _MOST_SAG:
_MOST_SAG = 1e6            # beyond these nothing changes any more but the arithmetic
_SIDE = 3000.0             # how firmly a guide holds the hose's belly in its plane (× bending stiffness / length
                           # for a belly of length² off the plane)
_TINY = 1e-300


@dataclass
class Hoses:
    """The shapes of a batch of B hoses."""
    points: np.ndarray       # (B, n, 3) centreline; points[:, 0] == p0 and points[:, -1] == p1 exactly
    short: np.ndarray        # (B,) bool: the ends are further apart than the hose can reach
    need: np.ndarray         # (B,) the shortest length that reaches (>= length when short)
    min_radius: np.ndarray   # (B,) the tightest bend along the hose (np.inf when straight); see the module's text
    tight: np.ndarray        # (B,) bool: a limit was asked (> 0) and min_radius is under it (beyond 1 %)
    start: np.ndarray        # (B,) int: the start whose answer this is: 0 the plain fold, 1 / 2 the fold wound
    #                          right- / left-handed, 3 the hose's guide (0 where there was nothing to choose:
    #                          short, taut, and without a guide for n = 5, 6, 8, 9, whose coarsest level has no
    #                          room for the wound starts)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def stiff_length(diameter, stiffness):
    """The bending length ℓ (metres) for a hose of this outer diameter and the slider 0 (soft cable) … 1 (stiff
    hydraulic hose): diameter · 4 · 16**stiffness. Works on arrays too."""
    out = np.asarray(diameter, dtype=float) * SOFT * (STIFF / SOFT) ** np.asarray(stiffness, dtype=float)
    return float(out) if out.ndim == 0 else out


def polyline_length(points):
    """Length along a polyline: (..., n, 3) → (...) (a float for one polyline)."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[-2] < 2:
        out = np.zeros(pts.shape[:-2])
    else:
        seg = pts[..., 1:, :] - pts[..., :-1, :]
        out = np.sqrt(np.einsum("...k,...k->...", seg, seg)).sum(axis=-1)
    return float(out) if out.ndim == 0 else out


def resample(points, n):
    """``n`` points equally spaced along the polyline ``points`` (m, 3), first and last kept. (Equal along the
    polyline: the straight distance between neighbours is a little shorter where it bends.)"""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    n = int(n)
    if n < 1:
        return np.zeros((0, 3))
    if len(pts) == 0:
        raise ValueError("no points to resample")
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1))
    s = np.concatenate(([0.0], np.cumsum(seg)))
    if len(pts) == 1 or s[-1] <= 0.0 or n == 1:
        return np.repeat(pts[:1], n, axis=0)
    at = np.linspace(0.0, s[-1], n)
    out = np.stack([np.interp(at, s, pts[:, k]) for k in range(3)], axis=1)
    out[0], out[-1] = pts[0], pts[-1]
    return out


def bend_radius(points, hose=False):
    """The tightest bend of each polyline (..., n, 3) → (...): the smallest circle through three neighbouring
    points; np.inf for a straight line (or fewer than three points). ``hose``: the points are a hose of this
    solver, whose first and last segment lie in the fittings: the bend at the two end joints is spread over 1.5
    segments (see the module's text), so the circle there counts 1.5 times its radius (meant for 5 points or more, as every solved hose has) – this is what
    ``Hoses.min_radius`` reports."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[-2] < 3:
        return np.full(pts.shape[:-2], np.inf)
    a = pts[..., 1:-1, :] - pts[..., :-2, :]
    b = pts[..., 2:, :] - pts[..., 1:-1, :]
    c = pts[..., 2:, :] - pts[..., :-2, :]
    cr = np.cross(a, b)
    area2 = np.sqrt(np.einsum("...k,...k->...", cr, cr))                 # twice the triangle's area
    prod = np.sqrt(np.einsum("...k,...k->...", a, a) * np.einsum("...k,...k->...", b, b)
                   * np.einsum("...k,...k->...", c, c))
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(area2 > 1e-14 * prod, prod / (2.0 * area2), np.inf)
    # two neighbouring segments folded back on each other: three points in a line, but no straight hose
    back = np.einsum("...k,...k->...", a, b) < 0.0
    r = np.where(back & ~np.isfinite(r), 0.0, r)
    if hose:
        r[..., 0] *= END_JOINT
        r[..., -1] *= END_JOINT
    return r.min(axis=-1)


def _rows(x) -> np.ndarray:
    """(3,) or (k, 3) → float (k, 3)."""
    a = np.array(x, dtype=float)
    if a.ndim == 0 or a.shape[-1] != 3:
        raise ValueError("a point or direction needs 3 numbers (x, y, z), got shape %s" % (a.shape,))
    return a.reshape(-1, 3)


def _col(x) -> np.ndarray:
    return np.array(x, dtype=float).reshape(-1)


def _norm(v) -> np.ndarray:
    return np.sqrt(np.einsum("...k,...k->...", v, v))


def _unit_or(v, other) -> np.ndarray:
    """Rows of ``v`` made unit; a row that has no length takes the row of ``other`` (already unit)."""
    ln = _norm(v)
    ok = ln > 1e-12
    out = np.where(ok[:, None], v / np.where(ok, ln, 1.0)[:, None], other)
    return out


# ---------------------------------------------------------------------------
# one level: n - 3 … 2 free segments between the two fixed end segments
# ---------------------------------------------------------------------------

class _Level:
    """What the solver knows about a batch of hoses on one level (q free segments). Lengths are in units of
    the free segment, the energy in units of weight per length × segment²."""

    __slots__ = ("q", "t0", "t1", "s", "kj", "bg", "ism", "rho", "pen", "emax", "shift", "side")

    def take(self, keep) -> "_Level":
        out = _Level()
        out.q, out.pen = self.q, self.pen
        for name in ("t0", "t1", "s", "kj", "bg", "emax", "shift"):
            setattr(out, name, getattr(self, name)[keep])
        out.ism = self.ism[keep] if self.pen else None
        out.rho = self.rho[keep] if self.pen else None
        out.side = None if self.side is None else self.side[keep]
        return out


def _make_level(q, a, free, t0, t1, rel, ell3, sagv, rmin, pen, guide=None) -> _Level:
    """q free segments sharing the length ``free`` between the two fixed end segments of length ``a``;
    rel = p1 − p0 − a·(t0 + t1): what the free segments have to span; sagv = sag × unit gravity (b, 3).

    ``guide`` (b, q, 3): the directions of a guide's free segments. The hose's *belly* – where its middle lies
    beside the line between its ends: Σ c_i · d_i with c_i the points hanging on segment i – is then held in the
    plane of the guide's belly and that line: energy ``_SIDE``/2 · ℓ³/length · (belly out of that plane, as an
    area / length²)². That stands in for the twist stiffness the model lacks: a real hose cannot swing its bow
    round the line of its fittings without twisting. It leaves the hose free in the guide's plane (to either
    side), costs nothing there, and weighs nothing against the weight of a soft cable (ℓ small)."""
    lv = _Level()
    b = len(free)
    hc = free / q                                         # the free segments
    lv.q, lv.t0, lv.t1, lv.pen = q, t0, t1, pen
    lv.s = rel / hc[:, None]
    k = ell3 / hc ** 3                                    # joint between two free segments
    ks = ell3 / ((a + (END_JOINT - 1.0) * hc) * hc * hc)  # joint between an end segment and a free one
    lv.kj = np.empty((b, q + 1))
    lv.kj[:] = k[:, None]
    lv.kj[:, 0] = lv.kj[:, -1] = ks
    c = 0.5 * (q + 1) - np.arange(1, q + 1)               # points hanging on each segment, centred
    lv.bg = c[None, :, None] * sagv[:, None, :]
    lv.emax = 2.0 * lv.kj.sum(axis=1) + _norm(lv.bg).sum(axis=1) + _TINY
    lv.shift = _SHIFT * lv.emax
    lv.ism = lv.rho = lv.side = None
    if guide is not None:
        line = lv.s / (_norm(lv.s) + _TINY)[:, None]
        belly = np.einsum("q,bqk->bk", c, guide)
        belly = belly - line * np.einsum("bk,bk->b", belly, line)[:, None]
        size = _norm(belly)
        there = (size > 1e-6 * q * q) & (_norm(lv.s) > 1e-9 * q)          # a guide with a belly, ends apart
        across = np.cross(line, belly / np.where(there, size, 1.0)[:, None])
        strength = np.sqrt(_SIDE * k * (hc / (2.0 * a + free)) ** 5) * there
        # (b, q, 3); the energy is (Σ d_i · side_i)² / 2
        lv.side = strength[:, None, None] * c[None, :, None] * across[:, None, :]
    if pen:
        hbar = np.empty((b, q + 1))                       # the length a joint stands for
        hbar[:] = hc[:, None]
        hbar[:, 0] = hbar[:, -1] = a + 0.5 * hc               # (as in the bending energy)
        ratio = rmin[:, None] / hbar                      # 1 / the largest |d_i+1 − d_i| allowed
        lv.ism = ratio * ratio
        load = 2.0 * lv.kj + (_norm(sagv) * (q * q / 8.0))[:, None]
        with np.errstate(divide="ignore"):
            lv.rho = np.where(ratio > 0.0, _PENALTY * load / np.where(ratio > 0.0, ratio, 1.0), 0.0)
    return lv


def _joints(d, lv):
    full = np.concatenate((lv.t0[:, None, :], d, lv.t1[:, None, :]), axis=1)
    dl = full[:, 1:] - full[:, :-1]
    return dl, np.einsum("bjk,bjk->bj", dl, dl)


def _energy(d, s, lv):
    e = 0.5 * np.einsum("bj,bj->b", lv.kj, s) - np.einsum("bqk,bqk->b", d, lv.bg)
    if lv.side is not None:
        off = np.einsum("bqk,bqk->b", d, lv.side)
        e = e + 0.5 * off * off
    if lv.pen:
        v = np.maximum(s * lv.ism - 1.0, 0.0)
        e = e + np.einsum("bj,bj->b", lv.rho, v * v * v) * (1.0 / 3.0)
    return e


def _tangents(d) -> np.ndarray:
    """Two unit vectors square to each unit vector of d (b, q, 3) → (b, q, 3, 2): the first two columns of the
    mirror that turns the Z axis into ±d (no branch, no trigonometry)."""
    v = d.copy()
    z = d[..., 2]
    v[..., 2] += np.copysign(1.0, z)
    t = v[..., :, None] * (v[..., None, :2] / (-1.0 - np.abs(z))[..., None, None])
    t[..., 0, 0] += 1.0
    t[..., 1, 1] += 1.0
    return t


_EYE3 = np.eye(3)


def _rowwise(call, a, *more):
    """``call`` for every matrix of the stack on its own, after it raised for the stack: the one that cannot be
    done gets NaN, the others their answer (so one absurd hose does not take its batch down)."""
    out = None
    for i in range(len(a)):
        try:
            got = call(a[i:i + 1], *(m[i:i + 1] for m in more))
        except np.linalg.LinAlgError:
            continue
        got = got if isinstance(got, tuple) else (got,)
        if out is None:
            out = tuple(np.full((len(a),) + g.shape[1:], np.nan) for g in got)
        for o, g in zip(out, got):
            o[i] = g[0]
    return out


def _lsolve(a, r):
    """Solutions of a stack of linear systems (b, k, k), (b, k, 1); NaN where a matrix is singular."""
    try:
        return np.linalg.solve(a, r)
    except np.linalg.LinAlgError:
        out = _rowwise(np.linalg.solve, a, r)
        return np.full(r.shape, np.nan) if out is None else out[0]


def _leigh(a):
    """Eigenvalues and eigenvectors of a stack of symmetric matrices; NaN where it does not come out."""
    try:
        return np.linalg.eigh(a)
    except np.linalg.LinAlgError:
        out = _rowwise(lambda x: tuple(np.linalg.eigh(x)), a)
        return (np.full(a.shape[:-1], np.nan), np.full(a.shape, np.nan)) if out is None else out


def _lqr(a):
    """The complete Q of a stack of tall matrices; NaN where it does not come out."""
    try:
        return np.linalg.qr(a, mode="complete")[0]
    except np.linalg.LinAlgError:
        out = _rowwise(lambda x: np.linalg.qr(x, mode="complete")[0], a)
        return np.full(a.shape[:-1] + a.shape[-2:-1], np.nan) if out is None else out[0]


def _dual_step(d, inv, r):
    """Newton step of the closing problem: d = unit(g + lam), r = sum(d) − s; returns the change of lam."""
    h = -np.matmul((d * inv[..., None]).transpose(0, 2, 1), d)
    tr = inv.sum(axis=1)
    h += (tr * (1.0 + 1e-13))[:, None, None] * _EYE3
    return -_lsolve(h, r[..., None])[..., 0]


def _close(g, s, iters=6, tol=1e-11):
    """The unit directions nearest to g (b, q, 3) whose sum is s (b, 3): d_i = unit(g_i + lam) with one lam per
    hose. For a g that is already nearly right (a Newton step from a closed shape). Returns d and how far the sum
    is off. (A hose that is closed is left alone while the others go on: its answer does not depend on who else
    is in the batch.)"""
    lam = np.zeros_like(s)
    for it in range(iters + 1):
        w = g + lam[:, None, :]
        inv = 1.0 / np.sqrt(np.einsum("bqk,bqk->bq", w, w) + _TINY)
        d = w * inv[..., None]
        r = d.sum(axis=1) - s
        res = np.abs(r).max(axis=1)
        open_ = res > tol
        if it == iters or not open_.any():
            break
        step = _dual_step(d, inv, r)
        lam = lam + step if open_.all() else np.where(open_[:, None], lam + step, lam)
    return d, res


def _close_safe(g, s, iters=60, tol=1e-11):
    """As ``_close`` for any g: the Newton steps are shortened until the sum comes nearer (the problem is convex,
    so that always ends at the one answer)."""
    b = len(g)
    lam = np.zeros_like(s)
    step = np.zeros_like(s)
    t = np.ones(b)
    best = np.full(b, np.inf)
    for it in range(iters):
        cur = lam + t[:, None] * step
        w = g + cur[:, None, :]
        inv = 1.0 / np.sqrt(np.einsum("bqk,bqk->bq", w, w) + _TINY)
        d = w * inv[..., None]
        r = d.sum(axis=1) - s
        res = np.abs(r).max(axis=1)
        ok = (res < best) & (best > tol)                  # (closed already: left alone)
        if ok.all():
            lam, best = cur, res
        else:
            lam = np.where(ok[:, None], cur, lam)
            best = np.where(ok, res, best)
        if not best.max() > tol:
            if ok.all():
                return d, res
            break
        new = _dual_step(d, inv, r)
        step = np.where(ok[:, None], new, step)
        t = np.where(ok, 1.0, t * 0.25)
    w = g + lam[:, None, :]
    d = w / np.sqrt(np.einsum("bqk,bqk->bq", w, w) + _TINY)[..., None]
    return d, np.abs(d.sum(axis=1) - s).max(axis=1)


@lru_cache(maxsize=64)
def _index(q):
    i = 2 * np.arange(q)
    a = np.arange(2)
    rd = i[:, None, None] + a[None, :, None] + np.zeros((1, 1, 2), dtype=int)
    cd = i[:, None, None] + a[None, None, :] + np.zeros((1, 2, 1), dtype=int)
    return i, i + 1, rd, cd, rd[:-1], cd[1:]


def _system(d, lam, lv, gamma=None):
    """The pieces of one Newton step at d: the joints' s = |d_i+1 − d_i|², the tangent frames tn (b, q, 3, 2),
    the energy's slope gt (b, 2q), mu (b, q): the pull along each segment, ke: the joints' stiffness as it is
    now, and mat (b, 2q + 3, 2q + 3): the energy's second derivative in the tangent frames (plus ``gamma`` on its
    diagonal), bordered by the three closing conditions."""
    q = lv.q
    nq = 2 * q
    b = len(d)
    i0, i1, rd, cd, ru, cu = _index(q)
    dl, s = _joints(d, lv)
    ke = lv.kj
    if lv.pen:
        v = np.maximum(s * lv.ism - 1.0, 0.0)             # how far each joint is over the limit
        slope = lv.rho * v * lv.ism                       # the extra energy is rho · v³ / 3
        ke = ke + 2.0 * slope * v
        beta = 8.0 * slope * lv.ism
    m = ke[..., None] * dl
    grad = m[:, :-1] - m[:, 1:] - lv.bg                                   # dE/dd_i, (b, q, 3)
    if lv.side is not None:
        grad += np.einsum("bqk,bqk->b", d, lv.side)[:, None, None] * lv.side
    tn = _tangents(d)
    gt = np.einsum("bqka,bqk->bqa", tn, grad).reshape(b, nq)
    mu = np.einsum("bqk,bk->bq", d, lam) - np.einsum("bqk,bqk->bq", d, grad)
    dia = ke[:, :-1] + ke[:, 1:] + mu
    dia += (lv.shift if gamma is None else lv.shift + gamma)[:, None]
    up = np.matmul(tn[:, :-1].transpose(0, 1, 3, 2), tn[:, 1:])           # T_i' T_i+1, (b, q - 1, 2, 2)
    up *= -ke[:, 1:-1, None, None]
    mat = np.zeros((b, nq + 3, nq + 3))
    if lv.pen:
        al = np.einsum("bqka,bqk->bqa", tn, dl[:, 1:])                    # the joint on the right of each segment
        ar = np.einsum("bqka,bqk->bqa", tn, dl[:, :-1])                   # … and on its left
        blk = (beta[:, 1:, None, None] * al[..., :, None] * al[..., None, :]
               + beta[:, :-1, None, None] * ar[..., :, None] * ar[..., None, :])
        blk[..., 0, 0] += dia
        blk[..., 1, 1] += dia
        mat[:, rd, cd] = blk
        up -= beta[:, 1:-1, None, None] * al[:, :-1, :, None] * ar[:, 1:, None, :]
    else:
        mat[:, i0, i0] = dia
        mat[:, i1, i1] = dia
    mat[:, ru, cu] = up
    mat[:, cu, ru] = up
    if lv.side is not None:                                               # the belly's term couples all segments
        v = np.einsum("bqka,bqk->bqa", tn, lv.side).reshape(b, nq)
        mat[:, :nq, :nq] += v[:, :, None] * v[:, None, :]
    jac = tn.transpose(0, 2, 1, 3).reshape(b, 3, nq)
    mat[:, nq:, :nq] = jac
    mat[:, :nq, nq:] = jac.transpose(0, 2, 1)
    return s, tn, gt, mu, ke, mat


def _newton_fast(d, lam, lv, tol, max_it):
    """Plain Newton steps for hoses that start near their answer (a finer level from a coarser one): one linear
    system per step gives the turn of every segment and the force; no energy is compared. A hose whose steps do
    not shrink is handed back (``ok`` False) for the careful way. Returns d (not yet closed exactly), lam, ok."""
    q = lv.q
    nq = 2 * q
    out_d, out_lam = d.copy(), lam.copy()
    ok = np.zeros(len(d), dtype=bool)
    ids = None
    last = np.inf
    for it in range(max_it):
        b = len(d)
        _s, tn, gt, _mu, _ke, mat = _system(d, lam, lv)
        rhs = np.empty((b, nq + 3))
        rhs[:, :nq] = -gt
        rhs[:, nq:] = lv.s - d.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            sol = _lsolve(mat, rhs[..., None])[..., 0]
            xi = np.einsum("bqka,bqa->bqk", tn, sol[:, :nq].reshape(b, q, 2))
            size = np.sqrt(np.einsum("bqk,bqk->bq", xi, xi).max(axis=1))
            fine = size < np.minimum(_CAP_FAST, _GROW * last)             # NaN: not fine
            new = d + xi
            new *= 1.0 / np.sqrt(np.einsum("bqk,bqk->bq", new, new))[..., None]
        if fine.all():
            d, lam = new, -sol[:, nq:]
        else:
            d = np.where(fine[:, None, None], new, d)
            lam = np.where(fine[:, None], -sol[:, nq:], lam)
        out = ~(size >= tol) | ~fine
        if out.any():
            if ids is None:
                ids = np.arange(b)
            if out.all():
                out_d[ids], out_lam[ids], ok[ids] = d, lam, fine
                return out_d, out_lam, ok
            hit = ids[out]
            out_d[hit], out_lam[hit], ok[hit] = d[out], lam[out], fine[out]
            keep = ~out
            d, lam, ids, lv, size = d[keep], lam[keep], ids[keep], lv.take(keep), size[keep]
        last = size
    return out_d, out_lam, ok


def _newton(d, lam, lv, tol, max_it=_MAX_IT):
    """Minimise the energy of one level from the closed start d (b, q, 3), the careful way: every step is closed
    exactly and only taken when it does not raise the energy; a step that would is taken again, damped (shorter
    and more downhill). lam (b, 3) is the force in the hose (it only steers the first step). Returns d and lam."""
    q = lv.q
    nq = 2 * q
    out_d, out_lam = d.copy(), lam.copy()
    ids = np.arange(len(d))
    gamma = np.zeros(len(d))
    for it in range(max_it):
        b = len(d)
        s, tn, gt, mu, ke, mat = _system(d, lam, lv, gamma)
        e0 = _energy(d, s, lv)
        scale = ke.max(axis=1) + np.abs(mu).max(axis=1) + _TINY
        rhs = np.empty((b, nq + 3))
        rhs[:, :nq] = -gt
        rhs[:, nq:] = lv.s - d.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            sol = _lsolve(mat, rhs[..., None])[..., 0]                    # (NaN where singular: a damped step)
            xi = np.einsum("bqka,bqa->bqk", tn, sol[:, :nq].reshape(b, q, 2))
            size = np.sqrt(np.einsum("bqk,bqk->bq", xi, xi).max(axis=1))
            far = size > _CAP                                             # too long a step: damp it, do not cut it
            trial, res = _close(d + xi, lv.s)
            e1 = _energy(trial, _joints(trial, lv)[1], lv)
            good = ~far & (res <= 1e-10) & (e1 <= e0 + 1e-13 * lv.emax)   # NaN anywhere: not good
            small = size < tol
        d = np.where(good[:, None, None], trial, d)
        lam = np.where(good[:, None], -sol[:, nq:], lam)
        done = (good & small & (gamma == 0.0)) | (size < 1e-3 * tol) | (gamma > 1e12 * scale) \
            | ~np.isfinite(scale + gamma)
        floor = 1.02 * np.maximum(-mu.min(axis=1), 0.0) + 1e-3 * scale
        calm = 0.1 * gamma
        more = np.maximum(gamma, floor)
        more = np.where(far, more * np.minimum(1.5 * size / _CAP, 100.0), np.maximum(4.0 * gamma, floor))
        gamma = np.where(good, np.where(calm > 1e-6 * scale, calm, 0.0), more)
        if done.any():
            out_d[ids[done]] = d[done]
            out_lam[ids[done]] = lam[done]
            keep = ~done
            if not keep.any():
                return out_d, out_lam
            d, lam, gamma, ids, lv = d[keep], lam[keep], gamma[keep], ids[keep], lv.take(keep)
    out_d[ids] = d
    out_lam[ids] = lam
    return out_d, out_lam


def _settle(d, lam, lv, tol, max_it=_MAX_IT):
    """As ``_newton``, for the coarse levels, and the result is a shape the hose would stay in: the step is worked
    out in the directions that keep the hose closed, from the eigenvalues of the energy's second derivative there.
    Where the energy curves down (a saddle: a shape in balance that would fall over) the step goes down the hill
    instead of to the balance point, and it is not done before the hose has left the saddle. Only a hose that
    sits exactly on the balance point stays there: a set-up that is exactly symmetric keeps its symmetric shape.
    (A step that is too long or raises the energy is damped and tried again from the same eigenvalues, up to
    ``_TRIES`` times, before they are worked out anew.)"""
    q = lv.q
    nq = 2 * q
    out_d, out_lam = d.copy(), lam.copy()
    ids = np.arange(len(d))
    gamma = np.zeros(len(d))
    for it in range(max_it):
        b = len(d)
        s, tn, gt, mu, ke, mat = _system(d, lam, lv)
        e0 = _energy(d, s, lv)
        scale = ke.max(axis=1) + np.abs(mu).max(axis=1) + _TINY
        hm, jt = mat[:, :nq, :nq], mat[:, :nq, nq:]
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            z = _lqr(jt)[:, :, 3:]                                        # the directions that keep it closed
            zt = z.transpose(0, 2, 1)
            w, vec = _leigh(np.matmul(zt, np.matmul(hm, z)))
            zv = np.matmul(z, vec)
            coef = np.matmul(zv.transpose(0, 2, 1), gt[..., None])[..., 0]
            aw = np.maximum(np.abs(w), 1e-10 * scale[:, None])
            # a saddle: the energy curves down one way, and the hose is not sitting exactly on the balance point
            saddle = (w[:, 0] < -1e-6 * scale) & (np.abs(coef[:, 0]) > _ON_IT * aw[:, 0])
            steep = None
            good = np.zeros(b, dtype=bool)
            took = np.zeros(b)                                            # the size of the step that was taken
            new_d, y = d, np.zeros((b, nq, 1))
            for attempt in range(_TRIES):
                go = -coef / (aw + gamma[:, None])
                # off a saddle with a real step, to the side it already leans to
                kick = _KICK * aw[:, 0] / (aw[:, 0] + gamma)
                go[:, 0] = np.where(saddle & (np.abs(go[:, 0]) < kick), -np.sign(coef[:, 0]) * kick, go[:, 0])
                yy = np.matmul(zv, go[..., None])
                xi = np.einsum("bqka,bqa->bqk", tn, yy.reshape(b, q, 2))
                size = np.sqrt(np.einsum("bqk,bqk->bq", xi, xi).max(axis=1))
                far = size > _CAP                                         # too long a step: damp it, do not cut it
                ok = np.zeros(b, dtype=bool)
                if not far.all():
                    trial, res = _close(d + xi, lv.s)
                    e1 = _energy(trial, _joints(trial, lv)[1], lv)
                    ok = ~far & ~good & (res <= 1e-10) & (e1 <= e0 + 1e-13 * lv.emax)     # NaN anywhere: not ok
                    if ok.all():
                        new_d, y, took, good = trial, yy, size, ok
                        break
                    new_d = np.where(ok[:, None, None], trial, new_d)
                    y = np.where(ok[:, None, None], yy, y)
                    took = np.where(ok, size, took)
                    good = good | ok
                    if good.all():
                        break
                if steep is None:                                         # the damping that surely shortens it
                    down = np.einsum("bqka,bqa->bqk", tn, np.matmul(zv, coef[..., None]).reshape(b, q, 2))
                    steep = np.sqrt(np.einsum("bqk,bqk->bq", down, down).max(axis=1)) / _CAP
                more = np.where(far, np.maximum(steep, 2.0 * gamma), 4.0 * np.maximum(gamma, 1e-3 * scale))
                gamma = np.where(good, gamma, more)
            rest = np.matmul(jt.transpose(0, 2, 1), np.matmul(hm, y) + gt[..., None])
            new_lam = _lsolve(np.matmul(jt.transpose(0, 2, 1), jt) + 1e-12 * _EYE3, rest)[..., 0]
        d = new_d
        lam = np.where(good[:, None], new_lam, lam)
        # done: a small step that was (nearly) a full Newton step, and not on a saddle
        done = (good & (took < tol) & (gamma <= 0.05 * aw[:, 0]) & ~saddle) | (good & (took < 1e-3 * tol)) \
            | (gamma > 1e12 * scale) | ~np.isfinite(scale + gamma)
        calm = 0.1 * gamma
        gamma = np.where(good, np.where(calm > 1e-6 * scale, calm, 0.0), gamma)
        if done.any():
            out_d[ids[done]] = d[done]
            out_lam[ids[done]] = lam[done]
            keep = ~done
            if not keep.any():
                return out_d, out_lam
            d, lam, gamma, ids, lv = d[keep], lam[keep], gamma[keep], ids[keep], lv.take(keep)
    out_d[ids] = d
    out_lam[ids] = lam
    return out_d, out_lam


def _along(lines, x):
    """Points on the polylines ``lines`` (b, m, 3) at the shares x (k,) of each one's own length: (b, k, 3), and
    for each line whether it is one (finite, with a length)."""
    step = lines[:, 1:] - lines[:, :-1]
    ln = _norm(step)
    s = np.concatenate((np.zeros((len(lines), 1)), np.cumsum(ln, axis=1)), axis=1)
    fine = np.isfinite(s[:, -1]) & (s[:, -1] > 0.0)
    at = x[None, :] * s[:, -1:]
    i = np.clip((s[:, None, :] <= at[:, :, None]).sum(axis=2) - 1, 0, lines.shape[1] - 2)
    part = np.take_along_axis(ln, i, axis=1)
    f = (at - np.take_along_axis(s, i, axis=1)) / np.where(part > 0.0, part, 1.0)
    rows = np.arange(len(lines))[:, None]
    return lines[rows, i] + np.clip(f, 0.0, 1.0)[..., None] * step[rows, i], fine


def _fold(lv, sagv, twist=0.0):
    """The start: the free segments as one fold (the first half one direction, the second half another; with an
    odd number the middle one along the chord). For 2 free segments this *is* the minimum of the energy: the fold
    lies on the side that the end directions and the weight push it to. ``twist`` (radians, 4 free segments
    only) turns the fold into one turn of a screw, right-handed or left-handed by its sign."""
    q = lv.q
    half = q // 2
    s = lv.s
    if q % 2:
        mid = _unit_or(s, np.broadcast_to(np.array([1.0, 0.0, 0.0]), s.shape))
        z = (s - mid) / half
    else:
        z = s / half
    zz = np.einsum("bk,bk->b", z, z)
    zu = z / np.sqrt(zz + 1e-200)[:, None]
    push = lv.kj[:, :1] * (lv.t0 - lv.t1) + sagv
    size = (lv.kj[:, 0] + _norm(sagv) + _TINY)[:, None]
    # nothing at all pushes it sideways (no gravity direction given): two fixed axes
    push = push + size * (1e-12 * np.array([0.6, 0.0, 0.8]) + 1e-13 * np.array([0.0, 1.0, 0.0]))
    push = push - zu * np.einsum("bk,bk->b", push, zu)[:, None]
    e = push / (_norm(push) + _TINY)[:, None]
    e = e - zu * np.einsum("bk,bk->b", e, zu)[:, None]
    e = e / (_norm(e) + _TINY)[:, None]
    r = np.sqrt(np.maximum(1.0 - 0.25 * zz, 0.0))[:, None]
    d = np.empty((len(s), q, 3))
    if twist and q == 4:
        side = np.cross(zu, e)                            # (unit where the chord has a direction, else 0)
        ce, sn = r * np.cos(twist) * e, r * np.sin(twist) * side
        d[:, 0], d[:, 1], d[:, 2], d[:, 3] = 0.5 * z + ce + sn, 0.5 * z + ce - sn, 0.5 * z - ce - sn, 0.5 * z - ce + sn
        d /= _norm(d)[..., None]
        return d
    d[:, :half] = (0.5 * z + r * e)[:, None, :]
    d[:, q - half:] = (0.5 * z - r * e)[:, None, :]
    if q % 2:
        d[:, half] = mid
    return d


def _force(d, lv):
    """A first guess of the force in the hose (least squares on the equilibrium of the segments)."""
    dl, _s = _joints(d, lv)
    m = lv.kj[..., None] * dl
    grad = m[:, :-1] - m[:, 1:] - lv.bg
    if lv.side is not None:
        grad += np.einsum("bqk,bqk->b", d, lv.side)[:, None, None] * lv.side
    along = np.einsum("bqk,bqk->bq", d, grad)
    rhs = (grad - d * along[..., None]).sum(axis=1)
    mat = lv.q * (1.0 + 1e-9) * _EYE3 - np.matmul(d.transpose(0, 2, 1), d)
    return _lsolve(mat, rhs[..., None])[..., 0]


@lru_cache(maxsize=64)
def _spread(n, qc, qf):
    """The matrix that reads the directions of a finer level off a coarser one: straight-line interpolation
    between the segments' middles along the hose ((qf, qc + 2); the end segments are columns 0 and qc + 1)."""
    a = 1.0 / (n - 1)
    xc = np.concatenate(([0.5 * a], a + (np.arange(qc) + 0.5) * (1.0 - 2.0 * a) / qc, [1.0 - 0.5 * a]))
    xf = a + (np.arange(qf) + 0.5) * (1.0 - 2.0 * a) / qf
    w = np.zeros((qf, qc + 2))
    hi = np.clip(np.searchsorted(xc, xf), 1, qc + 1)
    f = (xf - xc[hi - 1]) / (xc[hi] - xc[hi - 1])
    w[np.arange(qf), hi - 1] = 1.0 - f
    w[np.arange(qf), hi] = f
    return w


@lru_cache(maxsize=64)
def _levels(q):
    out = [q]
    while out[-1] > _FIRST:
        out.append((out[-1] + 1) // 2)
    return tuple(out[::-1])


def _refine(d, lam, lv, tol):
    """One level from a start near its answer: plain Newton, and the careful way for those it does not work for."""
    new, new_lam, ok = _newton_fast(d, lam, lv, tol, _FAST_IT)
    if ok.all():
        return new, new_lam
    d, lam = d.copy(), lam.copy()
    d[ok], lam[ok] = new[ok], new_lam[ok]
    no = ~ok
    d[no], lam[no] = _newton(d[no], lam[no], lv.take(no), tol)
    return d, lam


def _solve(n, t0, t1, rel, length, ell3, sagv, rmin, start, guide):
    """Directions of the n − 3 free segments for a chunk of hoses that reach and are not taut: (b, n − 3, 3), and
    the start each answer came from (b,). ``start`` (b,) int: −1 = the best of the three, 0 / 1 / 2 = that one.
    ``guide``: None or (b, m, 3), rows of NaN for hoses without one; a hose with a guide starts from it (start 3),
    and only if that leads nowhere is it solved as if it had none."""
    b = len(length)
    d = np.empty((b, n - 3, 3))
    which = np.zeros(b, dtype=int)
    plain = np.ones(b, dtype=bool)
    if guide is not None:
        led = np.flatnonzero(np.isfinite(guide).all(axis=(1, 2)))
        if len(led):
            got, ok = _solve_guided(n, t0[led], t1[led], rel[led], length[led], ell3[led], sagv[led], rmin[led],
                                    guide[led])
            led = led[ok]
            d[led], which[led], plain[led] = got[ok], 3, False
    if plain.all():
        d, which = _solve_plain(n, t0, t1, rel, length, ell3, sagv, rmin, start)
    elif plain.any():
        i = np.flatnonzero(plain)
        d[i], which[i] = _solve_plain(n, t0[i], t1[i], rel[i], length[i], ell3[i], sagv[i], rmin[i], start[i])
    # the minimum radius comes last, on the fine level, and only for the hoses that bend tighter than it: from
    # the shape without a limit the hose stiffens where it is too tight and settles again. (A hose that keeps its
    # limit anyway is not touched by it.)
    seg = length / (n - 1)
    full = np.concatenate((t0[:, None, :], d, t1[:, None, :]), axis=1)
    turn = _norm(full[:, 1:] - full[:, :-1])
    turn[:, 0] /= END_JOINT
    turn[:, -1] /= END_JOINT
    over = np.flatnonzero((rmin > 0.0) & (turn.max(axis=1) * rmin > seg))
    if len(over):
        g = None
        if guide is not None and (which[over] == 3).any():
            g = _guide_dirs(np.where((which[over] == 3)[:, None, None], guide[over], 0.0), n, n - 3)[0]
        lv = _make_level(n - 3, seg[over], length[over] - 2.0 * seg[over], t0[over], t1[over], rel[over], ell3[over],
                         sagv[over], rmin[over], True, g)
        new, _lam = _newton(d[over], _force(d[over], lv), lv, _TOL)
        new, res = _close(new, lv.s, iters=3, tol=1e-15)
        fine = (res <= 1e-10) & np.isfinite(new).all(axis=(1, 2))
        d[over[fine]] = new[fine]
    return d, which


def _finer(n, qc, qf, d, t0, t1, lv, sagv):
    """The closed directions of level qf read off the answer d of level qc."""
    full = np.concatenate((t0[:, None, :], d, t1[:, None, :]), axis=1)
    g = np.matmul(_spread(n, qc, qf), full)
    g *= 1.0 / (_norm(g) + 1e-30)[..., None]
    d, res = _close_safe(g, lv.s)
    bad = ~(res <= 1e-10)
    if bad.any():                                         # never seen; the fold always closes
        d[bad] = _fold(lv.take(bad), sagv[bad])
    return d


def _guide_dirs(guide, n, q):
    """The unit directions of the guide's own q free segments (b, q, 3), and whether each guide is a line."""
    a = 1.0 / (n - 1)
    pts, fine = _along(guide, a + (1.0 - 2.0 * a) * np.arange(q + 1) / q)
    g = pts[:, 1:] - pts[:, :-1]
    g = g / (_norm(g) + 1e-30)[..., None]
    fine &= np.isfinite(g).all(axis=(1, 2))
    return np.where(fine[:, None, None], g, 0.0), fine


def _solve_guided(n, t0, t1, rel, length, ell3, sagv, rmin, guide):
    """Hoses with a guide: every level's energy holds the hose's belly in the plane of the guide's (see
    ``_make_level``), and the coarsest level starts from the guide's own shape, closed onto the ends, instead of
    the three folds. Otherwise as ``_solve_plain``. Returns the directions and ok (b,): False where the guide is
    no line or cannot be closed onto the ends (the hose is then solved as if it had no guide)."""
    pen = False                                           # (the minimum radius: see ``_solve``)
    qs = _levels(n - 3)
    qs = qs[max(0, sum(q <= _SETTLE for q in qs) - 1):]   # from the finest of the coarse levels on: the guide is
    seg = length / (n - 1)                                # a shape, not a guess, and has the detail for it
    free = length - 2.0 * seg
    for i, q in enumerate(qs):
        g, line = _guide_dirs(guide, n, q)
        lv = _make_level(q, seg, free, t0, t1, rel, ell3, sagv, rmin, pen, g)
        tol = _TOL if q == qs[-1] else _TOL_COARSE
        if i == 0:
            d, res = _close_safe(g, lv.s)
            ok = line & (res <= 1e-10) & np.isfinite(d).all(axis=(1, 2))
            if not ok.all():                              # (something closed to go on with; not used)
                d[~ok] = _fold(lv.take(~ok), sagv[~ok])
            lam = _force(d, lv)
        else:
            d = _finer(n, qs[i - 1], q, d, t0, t1, lv, sagv)
            lam = lam * (q / qs[i - 1])
        if q <= _SETTLE or i == 0:
            d, lam = _settle(d, lam, lv, tol)
        else:
            d, lam = _refine(d, lam, lv, tol)
    d, res = _close(d, lv.s, iters=3, tol=1e-15)
    return d, ok & (res <= 1e-10) & np.isfinite(d).all(axis=(1, 2))


def _solve_plain(n, t0, t1, rel, length, ell3, sagv, rmin, start):
    """Hoses without a guide: see ``_solve``."""
    pen = False                                           # (the minimum radius: see ``_solve``)
    qs = _levels(n - 3)
    seg = length / (n - 1)
    free = length - 2.0 * seg
    tol = _TOL if len(qs) == 1 else _TOL_COARSE
    lv = _make_level(qs[0], seg, free, t0, t1, rel, ell3, sagv, rmin, pen)
    b = len(seg)
    which = np.zeros(b, dtype=int)
    if qs[0] == 4 and _TWIST:
        # a hose with slack between fittings that do not lie in one plane often has two shapes, one winding like
        # a right-handed screw and one like a left-handed: both are looked for (the fold wound each way), and the
        # one with less energy is taken. The plain fold is the third start: its answer stays unless a wound one
        # is clearly better, so a set-up that is symmetric gets nothing unsymmetric from the winding.
        # (A hose whose start is given is settled from that start alone.)
        ar = np.arange(b)
        free_choice = start < 0
        hose = np.concatenate([ar[free_choice | (start == k)] for k in range(3)])
        kind = np.concatenate([np.full(int((free_choice | (start == k)).sum()), k) for k in range(3)])
        folds = np.stack((_fold(lv, sagv), _fold(lv, sagv, _TWIST), _fold(lv, sagv, -_TWIST)))
        d = folds[kind, hose]
        many = lv.take(hose)
        d, lam = _settle(d, _force(d, many), many, tol)
        e = np.full((3, b), np.inf)
        e[kind, hose] = _energy(d, _joints(d, many)[1], many)
        where = np.zeros((3, b), dtype=int)
        where[kind, hose] = np.arange(len(hose))
        with np.errstate(invalid="ignore"):
            wound = 1 + (e[2] < e[1] - 1e-9 * lv.emax)
            best = np.where(e[wound, ar] < e[0] - _CLEARLY * lv.emax, wound, 0)
        which = np.where(free_choice, best, np.clip(start, 0, 2))
        pick = where[which, ar]
        d, lam = d[pick], lam[pick]
    else:
        d = _fold(lv, sagv)
        d, lam = _settle(d, _force(d, lv), lv, tol)
    for qc, qf in zip(qs[:-1], qs[1:]):
        lv = _make_level(qf, seg, free, t0, t1, rel, ell3, sagv, rmin, pen)
        d = _finer(n, qc, qf, d, t0, t1, lv, sagv)
        tol = _TOL if qf == qs[-1] else _TOL_COARSE
        if qf <= _SETTLE:                                 # still coarse: a shape that stays (plain Newton would
            d, lam = _settle(d, lam * (qf / qc), lv, tol)   # also stop on a saddle, and hide that it is one)
        else:
            d, lam = _refine(d, lam * (qf / qc), lv, tol)
    d, _res = _close(d, lv.s, iters=3, tol=1e-15)
    return d, which


# ---------------------------------------------------------------------------
# the public solver
# ---------------------------------------------------------------------------

def solve_hoses(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33,
                start=None, guide=None) -> Hoses:
    """The shapes of B hoses at once.

    p0, p1 (B, 3) the ends; t0, t1 (B, 3) the directions along the hose at end 0 and end 1 (both from end 0
    towards end 1; any length, a direction without length takes the line p0 → p1); length, stiff (the bending
    length, see ``stiff_length``), sag, min_radius: one number or (B,); gravity: the direction things fall in,
    (3,) or (B, 3), any length; n: points per hose (at least 5). One hose may be given as plain (3,) vectors.

    start: None (or −1) = of the three starts on the coarsest level the one with the least energy, as the module's
    text says. 0, 1 or 2 (one number or (B,), −1 for "the best" in between): that start alone – the plain fold,
    the fold wound right-handed, the fold wound left-handed; every guarantee holds for a given start as well.
    (It rarely changes the answer: the three mostly settle on one coarse shape, and which of two shapes a hose
    takes is then decided a level later, by the side it leans to. To keep a hose on its side give a guide.)

    guide: None, or a line of m >= 2 points from end 0 to end 1 that shows how the hose lies: (m, 3) for one
    hose, (B, m, 3) for a batch (the same m for all; resample them); a row of NaN is a hose without a guide. Only
    its shape counts – which way it bows beside the line between the ends – not its length or where exactly it is.
    The hose starts from the guide's shape and keeps its belly in the plane of the guide's (see the module's
    text); ``start`` is ignored for it and ``Hoses.start`` is 3. A guide that is no line (all its points in one
    place, or not finite) is no guide; fewer than 2 points are refused (ValueError). What the caller gives: the hose's centreline in the pose it was drawn in, each point carried
    along by the part of end 0 and by the part of end 1 and the two blended along the hose (all of end 0's at
    the start, all of end 1's at the end, a smooth step between).

    Result (``Hoses``): n points per hose with exact ends; unless ``short``, all n − 1 segments are length/(n − 1)
    long, the first along t0, the last along t1; ``start`` says which start each answer came from. Nothing is
    remembered between calls.
    """
    return _run(p0, t0, p1, t1, length, stiff, sag, min_radius, gravity, n, start, guide)[0]


class _Batch:
    """What ``_run`` worked out about a batch on the way (for ``solve_motion``, which goes on from there)."""


def _run(p0, t0, p1, t1, length, stiff, sag, min_radius, gravity, n, start, guide=None):
    """``solve_hoses``, and the batch as it was prepared and solved."""
    with np.errstate(all="ignore"):                       # (numbers that are not numbers are dealt with below)
        return _run_quietly(p0, t0, p1, t1, length, stiff, sag, min_radius, gravity, n, start, guide)


def _run_quietly(p0, t0, p1, t1, length, stiff, sag, min_radius, gravity, n, start, guide):
    n = int(n)
    if n < MIN_POINTS:
        raise ValueError("a hose needs at least %d points (n=%d)" % (MIN_POINTS, n))
    p0, t0, p1, t1 = _rows(p0), _rows(t0), _rows(p1), _rows(t1)
    grav = _rows(gravity)
    length, stiff, sag, rmin = _col(length), _col(stiff), _col(sag), _col(min_radius)
    want = np.array(-1 if start is None else start).reshape(-1)
    if not np.isin(want, (-1, 0, 1, 2)).all():
        raise ValueError("start is None, -1 (the best), 0, 1 or 2, got %r" % (start,))
    want = want.astype(int)
    sizes = [len(x) for x in (p0, t0, p1, t1, grav, length, stiff, sag, rmin, want)]
    if guide is not None:
        guide = np.array(guide, dtype=float)
        if guide.ndim == 2:
            guide = guide[None]
        if guide.ndim != 3 or guide.shape[2] != 3 or guide.shape[1] < 2:
            raise ValueError("a guide is a line of at least 2 points: (m, 3) for one hose or (B, m, 3), got shape %s"
                             % (guide.shape,))
        sizes.append(len(guide))
    b = 0 if 0 in sizes else max(sizes)                   # (no hoses: an empty result)
    try:
        p0, t0, p1, t1, grav = (np.broadcast_to(x, (b, 3)) for x in (p0, t0, p1, t1, grav))
        length, stiff, sag, rmin, want = (np.broadcast_to(x, (b,)) for x in (length, stiff, sag, rmin, want))
        if guide is not None:
            guide = np.broadcast_to(guide, (b,) + guide.shape[1:])
    except ValueError:
        raise ValueError("the inputs do not fit one batch of %d hoses" % b) from None

    # numbers that are not numbers, and absurd ones: an end or a length that is not finite gives a straight line
    # (flagged short) between the ends with 0 for what was not a number; a direction takes the line between the
    # ends, gravity is left out; stiffness, sag and limit are brought into a range the arithmetic can carry
    real = np.isfinite(p0).all(axis=1) & np.isfinite(p1).all(axis=1) & np.isfinite(length)
    p0 = np.where(np.isfinite(p0), p0, 0.0)
    p1 = np.where(np.isfinite(p1), p1, 0.0)
    length = np.where(np.isfinite(length), length, 0.0)
    t0, t1, grav = (np.where(np.isfinite(x).all(axis=1)[:, None], x, 0.0) for x in (t0, t1, grav))
    reach = np.maximum(length, 0.0)
    stiff = np.clip(np.nan_to_num(stiff, nan=0.0, posinf=np.inf), 0.0, _MOST * reach)
    sag = np.clip(np.nan_to_num(sag, nan=0.0, posinf=np.inf), 0.0, _MOST_SAG)
    rmin = np.clip(np.nan_to_num(rmin, nan=0.0, posinf=np.inf), 0.0, _MOST * reach)

    chord = p1 - p0
    dist = _norm(chord)
    line = _unit_or(chord, np.broadcast_to(np.array([1.0, 0.0, 0.0]), (b, 3)))
    t0 = _unit_or(t0, line)
    t1 = _unit_or(t1, line)
    grav = _unit_or(grav, np.zeros((b, 3)))               # no direction: no weight

    # the length that just reaches: |chord − x·(t0 + t1)| = (n − 3)·x with x the segment
    q = n - 3
    u = t0 + t1
    du = np.einsum("bk,bk->b", chord, u)
    den = du + np.sqrt(du * du + np.maximum(q * q - np.einsum("bk,bk->b", u, u), 0.0) * dist * dist)
    need = np.where(dist > 0.0, np.where(den > 0.0, (n - 1) * dist * dist / np.where(den > 0.0, den, 1.0), np.inf), 0.0)
    need = np.where(real, np.maximum(need, dist), np.inf)

    seg = length / (n - 1)
    free = length - 2.0 * seg
    rel = chord - seg[:, None] * u
    slack = 1.0 - _norm(rel) / np.where(free > 0.0, free, 1.0)
    fine = real & (length > 0.0) & np.isfinite(slack)
    short = ~(fine & (slack >= -SHORT))
    taut = ~short & (slack <= TAUT)
    work = ~short & ~taut

    dirs = np.empty((b, n - 1, 3))
    dirs[:, 0], dirs[:, -1] = t0, t1
    came = np.zeros(b, dtype=int)
    if taut.any():
        dirs[taut, 1:-1] = (rel[taut] / (q * seg[taut])[:, None])[:, None, :]
    pr = _Batch()
    pr.n, pr.p0, pr.p1, pr.t0, pr.t1, pr.length, pr.seg, pr.free, pr.rel = n, p0, p1, t0, t1, length, seg, free, rel
    pr.rmin, pr.short, pr.work, pr.need = rmin, short, work, need
    pr.led = np.zeros(b, dtype=bool)
    pr.ell3, pr.sagv = np.zeros(b), np.zeros((b, 3))
    if work.any():
        idx = np.flatnonzero(work)
        ell3 = stiff[idx] ** 3 + (_FLOOR * length[idx]) ** 3
        # the weight, plus the trace of weight every hose keeps, a little to one side of straight down
        gw = grav[idx]
        side = np.zeros_like(gw)
        side[np.arange(len(idx)), np.abs(gw).argmin(axis=1)] = _TILT
        across = _norm(np.cross(gw, line[idx])) / 0.03    # … only where the hose's line is within ~2° of gravity
        side /= (1.0 + np.where(dist[idx] > 0.0, across * across, 0.0))[:, None]
        ghost = _GHOST * ell3 / length[idx] ** 3
        sagv = (sag[idx] + ghost)[:, None] * gw + (ghost * _norm(gw))[:, None] * side
        pr.ell3[idx], pr.sagv[idx] = ell3, sagv
        for lo in range(0, len(idx), CHUNK):
            c = idx[lo:lo + CHUNK]
            k = slice(lo, lo + CHUNK)
            dirs[c, 1:-1], came[c] = _solve(n, t0[c], t1[c], rel[c], length[c], ell3[k], sagv[k], rmin[c], want[c],
                                            None if guide is None else guide[c])
    pr.dirs, pr.came, pr.led, pr.guide = dirs, came, came == 3, guide
    return _finish(pr, dirs, came), pr


def _finish(pr, dirs, came) -> Hoses:
    """The points and the tightest bend from the segments' directions."""
    n, p0, p1, seg, short = pr.n, pr.p0, pr.p1, pr.seg, pr.short
    b = len(seg)
    w = np.linspace(0.0, 1.0, n)[None, :, None]
    points = p0[:, None, :] + w * (p1 - p0)[:, None, :]   # short: the straight line (kept for the others' ends)
    bent = ~short
    if bent.any():
        points[bent] = p0[bent, None, :] + seg[bent, None, None] * np.concatenate(
            (np.zeros((int(bent.sum()), 1, 3)), np.cumsum(dirs[bent], axis=1)), axis=1)
    points[:, 0], points[:, -1] = p0, p1

    radius = np.full(b, np.inf)
    if bent.any():
        turn = _norm(dirs[bent, 1:] - dirs[bent, :-1])    # (b, n − 2): the joints
        turn[:, 0] /= END_JOINT                           # the two end joints turn over 1.5 segments of hose
        turn[:, -1] /= END_JOINT
        turn = turn.max(axis=1)
        radius[bent] = np.where(turn > 1e-12, seg[bent] / np.where(turn > 1e-12, turn, 1.0), np.inf)
    tight = (pr.rmin > 0.0) & (radius < TIGHT * pr.rmin)
    return Hoses(points=points, short=short, need=pr.need, min_radius=radius, tight=tight, start=came)


def solve_hose(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33,
               start=None, guide=None) -> Hoses:
    """One hose: as ``solve_hoses`` with B = 1 (``points`` is (1, n, 3)); ``guide`` (m, 3)."""
    one = [np.array(x, dtype=float).reshape(3) for x in (p0, t0, p1, t1, gravity)]
    if guide is not None:
        guide = np.array(guide, dtype=float)
        if guide.ndim != 2:
            raise ValueError("the guide of one hose is a line of points (m, 3), got shape %s" % (guide.shape,))
    return solve_hoses(one[0], one[1], one[2], one[3], float(length), float(stiff), float(sag), float(min_radius),
                       one[4], n, None if start is None else int(start), guide)


def largest_move(points) -> float:
    """The largest distance any point of a hose moves between two neighbouring frames: (F, n, 3) → metres."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    step = pts[1:] - pts[:-1]
    return float(np.sqrt(np.einsum("fnk,fnk->fn", step, step).max()))


def solve_motion(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33,
                 guide=None) -> Hoses:
    """ONE hose at the F frames of a motion, in their order (inputs (F, 3), numbers or (F,); ``guide`` (F, m, 3),
    one line per frame): as ``solve_hoses``, but the hose keeps the shape it has over the motion where it can.

    All frames are solved as ``solve_hoses`` does. If the hose jumps somewhere (a point moves more than ``JUMP``
    times as far between two frames as the ends and fittings did), the hose is *followed*: from the first frame's
    shape each frame is solved starting from the shape of the frame before, which keeps it in that shape for as
    long as a hose would stay in it. Where the shape it is in stops being one that stays (the energy starts to
    curve down some way: it would fall over), the hose takes that frame's own answer – it snaps over there, once,
    as a real hose does – and is followed on from the new shape. If the followed hose still jumps, the same is done
    from the last frame backwards, and of the three (as solved, followed forwards, followed backwards) the one
    with the fewest jumps is returned, then the one whose largest move of a point between two frames is smallest
    (on a tie in that order). ``Hoses.start`` of a followed frame is the start of the frame it was followed from.

    A hose with a ``guide`` is held by it frame by frame already; if it jumps all the same it is followed in the
    same way, with the guide's hold on its belly in every frame.

    Still a pure function – of the whole motion: the same frames in the same order give the same shapes, whatever
    was solved before. What it cannot do, and what the caller must know:
    * a shape that is lost along the motion jumps where it is lost;
    * the shape kept is not at every frame the one with the least energy, and a frame solved alone
      (``solve_hoses``) can differ from the same frame in the motion: store these shapes, do not mix the two;
    * other frames (a longer animation, another first frame) can keep another shape;
    * frames that are short are the straight line in every case, and a shape is not followed across them.
    Costs one solve of the F frames; following is one frame after the other (about 1 ms each) and only happens
    when there was a jump."""
    first, pr = _run(p0, t0, p1, t1, length, stiff, sag, min_radius, gravity, n, None, guide)
    f = len(first.points)
    with np.errstate(all="ignore"):
        if f < 2 or not _jumps(first.points, pr):
            return first
        best, least = first, (_jumps(first.points, pr), largest_move(first.points))
        for order in (range(f), range(f - 1, -1, -1)):
            cand = _finish(pr, *_follow(pr, order))
            score = (_jumps(cand.points, pr), largest_move(cand.points))
            if score < least:
                best, least = cand, score
            if not score[0]:
                break
    return best


def _follow(pr, order):
    """The directions of every frame, each solved (on the fine level only) from the frame before it in ``order``;
    the first frame, and every frame after one that was not solved (short, taut), as ``_run`` left it. A frame
    whose followed shape is not one the hose would stay in is left as ``_run`` solved it."""
    q = pr.n - 3
    dirs, came = pr.dirs.copy(), pr.came.copy()
    before = lam = None
    for f in order:
        if not pr.work[f]:
            before = lam = None
            continue
        if before is not None:
            k = slice(f, f + 1)
            lv = _make_level(q, pr.seg[k], pr.free[k], pr.t0[k], pr.t1[k], pr.rel[k], pr.ell3[k], pr.sagv[k],
                             pr.rmin[k], bool(pr.rmin[f] > 0.0),
                             _guide_dirs(pr.guide[k], pr.n, q)[0] if pr.led[f] else None)
            d, res = _close_safe(dirs[before:before + 1, 1:-1], lv.s)
            fine = res[0] <= 1e-10
            if fine:
                d, lam = _refine(d, _force(d, lv) if lam is None else lam, lv, _TOL)
                fine = bool(_stays(d, lam, lv)[0])
            if fine:
                d, res = _close(d, lv.s, iters=3, tol=1e-15)
                fine = res[0] <= 1e-10 and bool(np.isfinite(d).all())
            if fine:
                dirs[f, 1:-1], came[f] = d[0], came[before]
            else:                                         # this frame stays as it was solved alone
                lam = None
        before = f
    return dirs, came


def _stays(d, lam, lv):
    """Is d (an equilibrium of level lv, with the force lam) a shape the hose stays in? (b,) bool: no direction
    that keeps the hose closed in which the energy curves down."""
    nq = 2 * lv.q
    _s, _tn, _gt, mu, ke, mat = _system(d, lam, lv)
    hm, jt = mat[:, :nq, :nq], mat[:, :nq, nq:]
    z = _lqr(jt)[:, :, 3:]
    try:
        w = np.linalg.eigvalsh(np.matmul(z.transpose(0, 2, 1), np.matmul(hm, z)))
    except np.linalg.LinAlgError:
        return np.zeros(len(d), dtype=bool)
    return w[:, 0] >= -1e-6 * (ke.max(axis=1) + np.abs(mu).max(axis=1))


def _jumps(points, pr) -> int:
    """How often does a point move more than JUMP times as far between two frames as the two ends moved and the
    two fittings turned (as a length: angle × hose length) and the length changed?"""
    step = points[1:] - points[:-1]
    moved = np.sqrt(np.einsum("fnk,fnk->fn", step, step).max(axis=1))
    reach = np.abs(pr.length)
    drive = _norm(pr.p0[1:] - pr.p0[:-1]) + _norm(pr.p1[1:] - pr.p1[:-1]) + np.abs(reach[1:] - reach[:-1]) \
        + (_norm(pr.t0[1:] - pr.t0[:-1]) + _norm(pr.t1[1:] - pr.t1[:-1])) * reach[1:]
    return int((moved > JUMP * drive + 1e-9 * reach[1:]).sum())


# ---------------------------------------------------------------------------
# the guide of a hose between two parts that move against each other
# ---------------------------------------------------------------------------

def carried(points_a, points_b) -> np.ndarray:
    """The guide of a hose whose ends sit on two parts: the hose's drawn shape carried along by both.

    ``points_a`` and ``points_b`` (F, m, 3) or (m, 3): the same m points of the drawn centreline (end 0 … end 1) as
    the part at end 0 has carried them, and as the part at end 1 has – two rigid copies of one line. The result
    goes over from the first copy to the second along the hose: point k is moved by the share w_k (a smooth step
    of its place along the line) of the *screw* that takes copy A onto copy B – a turn about one axis and a slide
    along it. Across a hinge that is a turn of w_k × the hinge angle about the hinge's own axis, so the line keeps
    its bow however far the parts turn (blending the two copies point by point makes the middle collapse onto the
    axis from about a quarter turn on). Copies that are not rigid copies of each other, or lie on one straight
    line, are blended point by point."""
    a = np.asarray(points_a, dtype=float)
    b = np.asarray(points_b, dtype=float)
    one = a.ndim == 2
    if one:
        a, b = a[None], b[None]
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(a[0], axis=0), axis=1))])
    t = run / (run[-1] or 1.0)
    w = t * t * (3.0 - 2.0 * t)                           # (m,)
    plain = (1.0 - w)[None, :, None] * a + w[None, :, None] * b
    out = plain.copy()
    with np.errstate(all="ignore"):
        ca, cb = a.mean(axis=1), b.mean(axis=1)
        pa, pb = a - ca[:, None], b - cb[:, None]
        h = np.einsum("fki,fkj->fij", pa, pb)             # Kabsch: the turn that takes copy A onto copy B
        fine = np.isfinite(h).all(axis=(1, 2))
        h = np.where(fine[:, None, None], h, np.eye(3))
        u, s, vt = np.linalg.svd(h)
        d = np.sign(np.linalg.det(np.einsum("fij,fjk->fik", u, vt)))
        d = np.where(d == 0.0, 1.0, d)
        flip = np.broadcast_to(np.eye(3), h.shape).copy()
        flip[:, 2, 2] = d
        rot = np.einsum("fji,fjk,flk->fil", vt, flip, u)  # R = V D Uᵀ, b - cb = R (a - ca)
        fit = np.linalg.norm(np.einsum("fij,fkj->fki", rot, pa) - pb, axis=2).max(axis=1)
        size = np.linalg.norm(pa, axis=2).max(axis=1)
        rigid = fine & (fit <= 1e-6 * np.maximum(size, 1e-12)) & (s[:, 1] > 1e-9 * np.maximum(s[:, 0], 1e-300))
        cos = np.clip((np.trace(rot, axis1=1, axis2=2) - 1.0) * 0.5, -1.0, 1.0)
        angle = np.arccos(cos)
        axis = np.stack([rot[:, 2, 1] - rot[:, 1, 2], rot[:, 0, 2] - rot[:, 2, 0], rot[:, 1, 0] - rot[:, 0, 1]], axis=1)
        norm = np.linalg.norm(axis, axis=1)
        near_pi = norm < 1e-6
        if (near_pi & (angle > 1.0)).any():               # half a turn: the axis from the symmetric part
            _vals, vecs = np.linalg.eigh(0.5 * (rot + rot.transpose(0, 2, 1)))
            axis = np.where((near_pi & (angle > 1.0))[:, None], vecs[:, :, 2], axis)
            norm = np.linalg.norm(axis, axis=1)
        turn = rigid & (angle > 1e-9) & (norm > 0.0)
        n = axis / np.where(norm > 0.0, norm, 1.0)[:, None]
        move = cb - np.einsum("fij,fj->fi", rot, ca)      # b = R a + move
        along = np.einsum("fi,fi->f", n, move)
        # a point on the screw's axis: (I - R) p = move - along n, solved in the plane square to the axis
        rest = move - along[:, None] * n
        half = 0.5 * angle
        cot = np.where(np.abs(np.sin(half)) > 1e-12, np.cos(half) / np.where(np.sin(half) == 0.0, 1.0, np.sin(half)), 0.0)
        p0 = 0.5 * (rest + cot[:, None] * np.cross(n, rest))
        ang = w[None, :] * angle[:, None]                 # (F, m)
        x = a - p0[:, None]
        nx = np.cross(np.broadcast_to(n[:, None], x.shape), x)
        nd = np.einsum("fi,fki->fk", n, x)[..., None] * n[:, None]
        spun = (x * np.cos(ang)[..., None] + nx * np.sin(ang)[..., None] + nd * (1.0 - np.cos(ang))[..., None]
                + p0[:, None] + (w[None, :] * along[:, None])[..., None] * n[:, None])
        good = turn & np.isfinite(spun).all(axis=(1, 2))
        out[good] = spun[good]
    return out[0] if one else out
