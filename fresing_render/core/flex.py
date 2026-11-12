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
* min_radius – the tightest bend allowed (centreline radius), 0 = no limit.

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
  energy is taken if it is clearly better than the plain one.
* It stops when the Newton step is below 1e-4 rad (the error is about its square), not after a fixed number of
  steps. (The design suggested a fixed number of smoothing steps with a constant matrix. That does not reach the
  equilibrium of a stiff hose in an affordable number of steps – it needs about n² of them – and an unfinished
  iteration is not the shape of any hose.)

What that gives, and what it cannot
-----------------------------------
* Exact ends, end directions and segment lengths.
* A pure function: the same inputs give bit for bit the same points, whatever was solved before; a hose solved in
  a batch (in any order, with any others) gets what it gets alone, to rounding.
* The shape follows the ends smoothly as long as it is the same shape. **Where a hose has two shapes, a function
  of the present position alone has to choose**, and along a motion from where the one is the relaxed shape to
  where the other is, the choice changes: the hose jumps there, once, where the two have the same energy (on the
  coarsest level). A real hose stays in the shape it is in until that shape is lost; that needs the frame before,
  which this function does not have by design (frames are rendered in any order). Hoses with little slack and
  fittings that roughly face each other have one shape; the more slack and the more the fittings point out of
  one plane, the more often there are two. Measured on random motions (fittings up to ~45° off the line between
  the ends, in any direction; the end moves 30 % of the distance and the fitting turns 40° in 40 frames): one
  jump in 3 of 235 motions of hoses a little longer than the distance, in 20 of 299 for up to twice the distance;
  never more than one. Known exception: a hose without weight (sag 0) that passes close to a symmetric set-up
  can show a third, in-between shape for a frame or two.
* Turning or moving the whole scene (gravity with it) turns and moves the answer; mirroring it mirrors the answer.
* A set-up that is exactly symmetric keeps its symmetric shape, also where that is a balance point (two fittings
  exactly in line, pushed together so far that the bow would rather wind out of its plane): the solver only
  leaves a balance point to the side the hose leans to. The model has no twist stiffness, which a real hose has
  and which holds a bow in its plane for longer, so that errs on the right side. Pushed together to under about
  0.4 × its length, a hose between fittings in line goes from a bow to a loop, with a jump.

Not reaching, and tight bends
-----------------------------
* ``short``: the ends are further apart than the hose can reach with its first and last segment in their fittings.
  The points are then the straight line p0 → p1 (stretched, ends exact); ``need`` is the length that would just
  reach. Within 1e-7 of that limit (``TAUT``) the answer is the one shape that still fits: first and last segment
  in their fittings and a straight line between.
* ``min_radius`` of the result is measured on the points: the circle through three neighbouring points, which for
  equal segments is h / |d_i+1 − d_i|. With a limit > 0 a bend tighter than the limit costs extra energy, steeply
  (the hose stiffens where it would be too tight), so the bend spreads out along the hose as far as the length and
  the ends allow. ``tight`` is True when the result still bends tighter than 0.99 × the limit: the ends force it
  (too close together for a loop of that radius, or a fitting pointing so that the hose must turn sharply right at
  it), or – rarely – a wider shape exists that the solver did not find from its start. A limit that the hose keeps
  anyway costs nothing; one that it has to be held to makes the solve 2 … 6 times slower.

Speed
-----
n = 33, measured in tests/test_flex_core.py (Claude Code web session, 4 cores, 12 Nov 2026): one hose 5 ms; a
batch of 20: 11 ms (20 poses of a U-loop) … 19 ms (20 unrelated hoses, a quarter of them with fittings pointing
sideways or backwards); 5,000 in one call 3.0 s (0.6 ms each). Small batches are slow per hose because every
NumPy call has a fixed cost: solve all hoses of a frame, or all frames of a hose, in one call. From n = 65 on
the linear systems are large enough for the BLAS library to start its threads (1.3 ms per hose in a batch).

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
_TOL_COARSE = 1e-2         # … and the coarse levels (they only give the start)
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
_TINY = 1e-300


@dataclass
class Hoses:
    """The shapes of a batch of B hoses."""
    points: np.ndarray       # (B, n, 3) centreline; points[:, 0] == p0 and points[:, -1] == p1 exactly
    short: np.ndarray        # (B,) bool: the ends are further apart than the hose can reach
    need: np.ndarray         # (B,) the shortest length that reaches (>= length when short)
    min_radius: np.ndarray   # (B,) the tightest bend along the hose (np.inf when straight)
    tight: np.ndarray        # (B,) bool: a limit was asked (> 0) and min_radius is under it (beyond 1 %)


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


def bend_radius(points):
    """The tightest bend of each polyline (..., n, 3) → (...): the smallest circle through three neighbouring
    points; np.inf for a straight line (or fewer than three points)."""
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

    __slots__ = ("q", "t0", "t1", "s", "kj", "bg", "ism", "rho", "pen", "emax", "shift")

    def take(self, keep) -> "_Level":
        out = _Level()
        out.q, out.pen = self.q, self.pen
        for name in ("t0", "t1", "s", "kj", "bg", "emax", "shift"):
            setattr(out, name, getattr(self, name)[keep])
        out.ism = self.ism[keep] if self.pen else None
        out.rho = self.rho[keep] if self.pen else None
        return out


def _make_level(q, a, free, t0, t1, rel, ell3, sagv, rmin, pen) -> _Level:
    """q free segments sharing the length ``free`` between the two fixed end segments of length ``a``;
    rel = p1 − p0 − a·(t0 + t1): what the free segments have to span; sagv = sag × unit gravity (b, 3)."""
    lv = _Level()
    b = len(free)
    hc = free / q                                         # the free segments
    lv.q, lv.t0, lv.t1, lv.pen = q, t0, t1, pen
    lv.s = rel / hc[:, None]
    k = ell3 / hc ** 3                                    # joint between two free segments
    ks = ell3 / ((a + 0.5 * hc) * hc * hc)                # joint between an end segment and a free one
    lv.kj = np.empty((b, q + 1))
    lv.kj[:] = k[:, None]
    lv.kj[:, 0] = lv.kj[:, -1] = ks
    c = 0.5 * (q + 1) - np.arange(1, q + 1)               # points hanging on each segment, centred
    lv.bg = c[None, :, None] * sagv[:, None, :]
    lv.emax = 2.0 * lv.kj.sum(axis=1) + _norm(lv.bg).sum(axis=1) + _TINY
    lv.shift = _SHIFT * lv.emax
    lv.ism = lv.rho = None
    if pen:
        hbar = np.empty((b, q + 1))                       # the length a joint stands for
        hbar[:] = hc[:, None]
        hbar[:, 0] = hbar[:, -1] = 0.5 * (a + hc)
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


def _dual_step(d, inv, r):
    """Newton step of the closing problem: d = unit(g + lam), r = sum(d) − s; returns the change of lam."""
    h = -np.matmul((d * inv[..., None]).transpose(0, 2, 1), d)
    tr = inv.sum(axis=1)
    h += (tr * (1.0 + 1e-13))[:, None, None] * _EYE3
    return -np.linalg.solve(h, r[..., None])[..., 0]


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
            try:
                sol = np.linalg.solve(mat, rhs[..., None])[..., 0]
            except np.linalg.LinAlgError:
                break
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
            try:
                sol = np.linalg.solve(mat, rhs[..., None])[..., 0]
            except np.linalg.LinAlgError:                                 # exactly singular: a damped step for all
                sol = np.full((b, nq + 3), np.nan)
            xi = np.einsum("bqka,bqa->bqk", tn, sol[:, :nq].reshape(b, q, 2))
            size = np.sqrt(np.einsum("bqk,bqk->bq", xi, xi).max(axis=1))
            far = size > _CAP                                             # too long a step: damp it, do not cut it
            trial, res = _close(d + xi, lv.s)
            e1 = _energy(trial, _joints(trial, lv)[1], lv)
            good = ~far & (res <= 1e-10) & (e1 <= e0 + 1e-13 * lv.emax)   # NaN anywhere: not good
            small = size < tol
        d = np.where(good[:, None, None], trial, d)
        lam = np.where(good[:, None], -sol[:, nq:], lam)
        done = (good & small & (gamma == 0.0)) | (size < 1e-3 * tol) | (gamma > 1e12 * scale)
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
            z = np.linalg.qr(jt, mode="complete")[0][:, :, 3:]            # the directions that keep it closed
            zt = z.transpose(0, 2, 1)
            w, vec = np.linalg.eigh(np.matmul(zt, np.matmul(hm, z)))
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
            new_lam = np.linalg.solve(np.matmul(jt.transpose(0, 2, 1), jt) + 1e-12 * _EYE3, rest)[..., 0]
        d = new_d
        lam = np.where(good[:, None], new_lam, lam)
        # done: a small step that was (nearly) a full Newton step, and not on a saddle
        done = (good & (took < tol) & (gamma <= 0.05 * aw[:, 0]) & ~saddle) | (good & (took < 1e-3 * tol)) \
            | (gamma > 1e12 * scale)
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
    along = np.einsum("bqk,bqk->bq", d, grad)
    rhs = (grad - d * along[..., None]).sum(axis=1)
    mat = lv.q * (1.0 + 1e-9) * _EYE3 - np.matmul(d.transpose(0, 2, 1), d)
    return np.linalg.solve(mat, rhs[..., None])[..., 0]


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


def _solve(n, t0, t1, rel, length, ell3, sagv, rmin):
    """Directions of the n − 3 free segments for a chunk of hoses that reach and are not taut: (b, n − 3, 3)."""
    pen = bool((rmin > 0.0).any())
    qs = _levels(n - 3)
    seg = length / (n - 1)
    free = length - 2.0 * seg
    tol = _TOL if len(qs) == 1 else _TOL_COARSE
    lv = _make_level(qs[0], seg, free, t0, t1, rel, ell3, sagv, rmin, pen)
    if qs[0] == 4 and _TWIST:
        # a hose with slack between fittings that do not lie in one plane often has two shapes, one winding like
        # a right-handed screw and one like a left-handed: both are looked for (the fold wound each way), and the
        # one with less energy is taken. The plain fold is the third start: its answer stays unless a wound one
        # is clearly better, so a set-up that is symmetric gets nothing unsymmetric from the winding.
        b = len(seg)
        three = lv.take(np.arange(3 * b) % b)
        d = np.concatenate((_fold(lv, sagv), _fold(lv, sagv, _TWIST), _fold(lv, sagv, -_TWIST)), axis=0)
        d, lam = _settle(d, _force(d, three), three, tol)
        e = _energy(d, _joints(d, three)[1], three).reshape(3, b)
        wound = 1 + (e[2] < e[1] - 1e-9 * lv.emax)
        pick = np.arange(b) + b * np.where(e[wound, np.arange(b)] < e[0] - _CLEARLY * lv.emax, wound, 0)
        d, lam = d[pick], lam[pick]
    else:
        d = _fold(lv, sagv)
        d, lam = _settle(d, _force(d, lv), lv, tol)
    for qc, qf in zip(qs[:-1], qs[1:]):
        full = np.concatenate((t0[:, None, :], d, t1[:, None, :]), axis=1)
        lv = _make_level(qf, seg, free, t0, t1, rel, ell3, sagv, rmin, pen)
        g = np.matmul(_spread(n, qc, qf), full)
        g *= 1.0 / (_norm(g) + 1e-30)[..., None]
        d, res = _close_safe(g, lv.s)
        bad = ~(res <= 1e-10)
        if bad.any():                                     # never seen; the fold always closes
            d[bad] = _fold(lv.take(bad), sagv[bad])
        tol = _TOL if qf == qs[-1] else _TOL_COARSE
        if qf <= _SETTLE:                                 # still coarse: a shape that stays (plain Newton would
            d, lam = _settle(d, lam * (qf / qc), lv, tol)   # also stop on a saddle, and hide that it is one)
        else:
            d, lam = _refine(d, lam * (qf / qc), lv, tol)
    d, _res = _close(d, lv.s, iters=3, tol=1e-15)
    return d


# ---------------------------------------------------------------------------
# the public solver
# ---------------------------------------------------------------------------

def solve_hoses(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33) -> Hoses:
    """The shapes of B hoses at once.

    p0, p1 (B, 3) the ends; t0, t1 (B, 3) the directions along the hose at end 0 and end 1 (both from end 0
    towards end 1; any length, a direction without length takes the line p0 → p1); length, stiff (the bending
    length, see ``stiff_length``), sag, min_radius: one number or (B,); gravity: the direction things fall in,
    (3,) or (B, 3), any length; n: points per hose (at least 5). One hose may be given as plain (3,) vectors.

    Result (``Hoses``): n points per hose with exact ends; unless ``short``, all n − 1 segments are length/(n − 1)
    long, the first along t0, the last along t1. Nothing is remembered between calls.
    """
    n = int(n)
    if n < MIN_POINTS:
        raise ValueError("a hose needs at least %d points (n=%d)" % (MIN_POINTS, n))
    p0, t0, p1, t1 = _rows(p0), _rows(t0), _rows(p1), _rows(t1)
    grav = _rows(gravity)
    length, stiff, sag, rmin = _col(length), _col(stiff), _col(sag), _col(min_radius)
    b = max(len(x) for x in (p0, t0, p1, t1, grav, length, stiff, sag, rmin))
    try:
        p0, t0, p1, t1, grav = (np.broadcast_to(x, (b, 3)) for x in (p0, t0, p1, t1, grav))
        length, stiff, sag, rmin = (np.broadcast_to(x, (b,)) for x in (length, stiff, sag, rmin))
    except ValueError:
        raise ValueError("the inputs do not fit one batch of %d hoses" % b) from None

    chord = p1 - p0
    dist = _norm(chord)
    line = _unit_or(chord, np.broadcast_to(np.array([1.0, 0.0, 0.0]), (b, 3)))
    t0 = _unit_or(t0, line)
    t1 = _unit_or(t1, line)
    grav = _unit_or(grav, np.zeros((b, 3)))               # no direction: no weight
    sag = np.maximum(np.nan_to_num(sag), 0.0)
    rmin = np.maximum(np.nan_to_num(rmin), 0.0)

    # the length that just reaches: |chord − x·(t0 + t1)| = (n − 3)·x with x the segment
    q = n - 3
    u = t0 + t1
    du = np.einsum("bk,bk->b", chord, u)
    den = du + np.sqrt(du * du + np.maximum(q * q - np.einsum("bk,bk->b", u, u), 0.0) * dist * dist)
    with np.errstate(divide="ignore", invalid="ignore"):
        need = np.where(dist > 0.0, np.where(den > 0.0, (n - 1) * dist * dist / den, np.inf), 0.0)
        need = np.maximum(need, dist)

    seg = length / (n - 1)
    free = length - 2.0 * seg
    rel = chord - seg[:, None] * u
    with np.errstate(divide="ignore", invalid="ignore"):
        slack = 1.0 - _norm(rel) / free
    fine = np.isfinite(slack) & (length > 0.0) & np.isfinite(stiff) & np.isfinite(t0 + t1 + grav).all(axis=1)
    short = ~(fine & (slack >= -SHORT))
    taut = ~short & (slack <= TAUT)
    work = ~short & ~taut

    points = np.empty((b, n, 3))
    w = np.linspace(0.0, 1.0, n)[None, :, None]
    points[:] = p0[:, None, :] + w * chord[:, None, :]    # short: the straight line (kept for the others' ends)

    dirs = np.empty((b, n - 1, 3))
    dirs[:, 0], dirs[:, -1] = t0, t1
    if taut.any():
        dirs[taut, 1:-1] = (rel[taut] / (q * seg[taut])[:, None])[:, None, :]
    if work.any():
        idx = np.flatnonzero(work)
        ell = np.maximum(np.nan_to_num(stiff[idx]), 0.0)
        ell3 = ell ** 3 + (_FLOOR * length[idx]) ** 3
        # the weight, plus the trace of weight every hose keeps, a little to one side of straight down
        gw = grav[idx]
        side = np.zeros_like(gw)
        side[np.arange(len(idx)), np.abs(gw).argmin(axis=1)] = _TILT
        across = _norm(np.cross(gw, line[idx])) / 0.03    # … only where the hose's line is within ~2° of gravity
        side /= (1.0 + np.where(dist[idx] > 0.0, across * across, 0.0))[:, None]
        ghost = _GHOST * ell3 / length[idx] ** 3
        sagv = (sag[idx] + ghost)[:, None] * gw + (ghost * _norm(gw))[:, None] * side
        for lo in range(0, len(idx), CHUNK):
            c = idx[lo:lo + CHUNK]
            k = slice(lo, lo + CHUNK)
            dirs[c, 1:-1] = _solve(n, t0[c], t1[c], rel[c], length[c], ell3[k], sagv[k], rmin[c])
    bent = ~short
    if bent.any():
        points[bent] = p0[bent, None, :] + seg[bent, None, None] * np.concatenate(
            (np.zeros((int(bent.sum()), 1, 3)), np.cumsum(dirs[bent], axis=1)), axis=1)
    points[:, 0], points[:, -1] = p0, p1

    radius = np.full(b, np.inf)
    if bent.any():
        turn = _norm(dirs[bent, 1:] - dirs[bent, :-1]).max(axis=1)
        with np.errstate(divide="ignore"):
            radius[bent] = np.where(turn > 1e-12, seg[bent] / np.where(turn > 1e-12, turn, 1.0), np.inf)
    tight = (rmin > 0.0) & (radius < TIGHT * rmin)
    return Hoses(points=points, short=short, need=need, min_radius=radius, tight=tight)


def solve_hose(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33) -> Hoses:
    """One hose: as ``solve_hoses`` with B = 1 (``points`` is (1, n, 3))."""
    one = [np.array(x, dtype=float).reshape(3) for x in (p0, t0, p1, t1, gravity)]
    return solve_hoses(one[0], one[1], one[2], one[3], float(length), float(stiff), float(sag), float(min_radius),
                       one[4], n)
