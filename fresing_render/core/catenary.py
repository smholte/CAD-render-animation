"""A cable hanging into the sea: the catenary from the hang-off down to the seabed, and the cable lying on the
seabed behind it (task 0081). No Blender; metres, radians, NumPy; every function works on F moments at once.

**The shape.** A cable that weighs w per metre in water and is pulled along the seabed with the force H hangs as
a catenary with the parameter a = H / w (metres). Its lowest point is where it touches down (TDP); from there,
at the height h above the cable's middle on the seabed::

    suspended length   s = sqrt(h² + 2 a h)              horizontal span   X = a acosh(1 + h / a)
    at arc length σ from the TDP:   x = a asinh(σ / a),   z = sqrt(a² + σ²) − a
    angle below horizontal at the top: cos θ = a / (a + h),  sin θ = s / (a + h)
    tension at the top = H + w h

(the classic results; e.g. Irvine, "Cable Structures", 1981, ch. 1). Behind the TDP the cable lies on the seabed
in a straight line along the lay direction ``aft`` to its end ``start`` (S), which lies still.

**One unknown.** Given the hang-off point T, S and the cable's length L from T to S, the laid length x and the
suspended length s add up to L. With TDP = S − x · aft the span is X(x) = |T − TDP| measured flat; x + s(X, h) grows
with x (s − X shrinks as the span grows), so there is one answer, found by bisection on a (``hang``). Three edge
cases are kept, never drawn with a wrong length without a word (``kind``):

* ``LIFTED`` – so tight that even with nothing on the seabed the touching-down catenary is longer than L: the cable
  lifts off its end. The shape is then the catenary through S and T of length L (not tangent at S):
  sqrt(L² − h²) = 2 a sinh(X / 2a) (a plain bisection on the touching shape gave a wrong length here: task 0075).
* ``PILED`` – more cable than the flat distance plus the depth: it would pile up on the seabed. It hangs straight
  down under T; on the seabed it lies straight from S along the lay line and carries the extra length in **one
  bight** next to the touch-down (task 0248, ``bight``), so the length stays L. (Before 0248 it snaked in waves of
  4 m over the whole way from S to the TDP: a let-go cable wobbled from end to end.)
* ``STRETCHED`` – L shorter than the straight line from T to S: drawn straight (the length is then wrong; the app
  warns).

**Leaving a wheel** (``hang_off``). The cable comes onto its last contact (a horn, chute or sheave: a wheel of
radius r) and leaves it where the catenary's tangent at T is the wheel's tangent – no kink. The point T lies at the
wrap ψ round the wheel from where the cable arrives; the catenary from T(ψ) with L(ψ) = L₀ − r ψ gives a direction,
that direction a ψ: a fixed point, found in a few rounds (T moves little against the span). When the catenary is
steeper than the wheel's end (``wrap_max``: a chute ends) the cable leaves at the end (``steep``); when it would
leave before it arrives, it does not touch the wheel (``short``, ψ = 0). The wrap wanted is read as the one nearest
the wheel's range (an angle a little beyond half a turn is "beyond the end", not "before the start": task 0125).

**No kink** (task 0125). Where the catenary's direction is not the wheel's tangent – beyond a chute's end, or out of
the wheel's plane (a wheel tilted out of the catenary's vertical plane) – the cable does not kink: it goes on in a
**free bend** of the wheel's radius from the wheel's tangent to the catenary's direction (in the plane of the two),
and the catenary starts where that bend ends (a fixed point: the catenary's direction depends a little on where it
starts). ``bend_points`` gives its points.

**A wheel lying flat, near the seabed** (task 0172: the D tipped flat and set down, shot 11 of the demo). Where the
cable hangs nearly straight down past a wheel lying flat, the catenary's direction direction says nothing about where round the wheel the cable goes: its sideways part flipped the
leave point from one end of the gutter to its middle and back. For a wheel whose plane holds less than ``FLAT`` of
"down" the wrap is read from the way the cable lies on the seabed (the lay direction from the touch-down towards S),
blended in as the wheel lies flatter: the cable stays in the gutter to the end that points the way it lies. A free bend that would reach into the seabed turns only as far as
fits above it (the cable comes off the bend onto the seabed: the touch-down) – before, it was left out and the cable
kinked by up to 60° at the wheel.
"""

from __future__ import annotations

import math

import numpy as np

G = 9.81                        # m/s²
NORMAL, LIFTED, PILED, STRETCHED = 0, 1, 2, 3
KINDS = ("touches down", "lifts off its end", "piles up on the seabed", "is too short")
WET_200 = 38.0                  # kg/m in water of a 200 mm power cable (task 0173: study 0152's public cables are
#                                 22–39 kg/m at Ø 200 – the heavy, lead-sheathed end; it was 51 = 0083's 500 N/m)
ROUNDS = 64                     # bisection steps (2⁻⁶⁴ of the range in log: far below a micrometre)
FIX_ROUNDS = 60                 # rounds of the fixed point on the wrap
FIX_TOL = 1e-12                 # rad
BEND_MIN = 1e-4                 # rad: a smaller kink is left as it is (no free bend)
BEND_ROUNDS = 80                # rounds of the fixed point on the free bend's turn
FLAT = 0.2                      # a wheel whose plane holds less of "down" than this lies (nearly) flat (as paths_sea.FLAT)
BED_GAP = 1e-3                  # m: a free bend ends at least this far over the cable's middle on the seabed
PILE_EASE = 1.0                 # m: a piled cable's wrap is read from straight down once this much has piled up
BED_BAND = 2.0                  # m: a free bend ending this near the seabed bends in the catenary's plane at the wheel
BIGHT_TURN = math.radians(45.0)  # a bight's feet turn this far off the lay line when no bend radius is known
BIGHT_TURN_MAX = math.radians(140.0)  # … and at most this far (beyond 150° its feet would cross: a loop)
BIGHT_EASE = 1.5                # a bight bends at this many times the cable's smallest bend radius (not at it)
BIGHT_ROUNDS = 60               # bisection steps of a bight's turn
MBR_DIAMETERS = 10.0            # no smallest bend radius given: 10 x the cable's diameter (task 0248)
_TINY = 1e-9


def wet_weight(diameter: float) -> float:
    """A power cable's weight in water (kg/m) for its diameter (m): 38 kg/m at 200 mm, as the square of Ø."""
    return WET_200 * (float(diameter) / 0.2) ** 2


def tensions(a, h, weight: float):
    """(bottom, top) tension in kN for the catenary parameter a (m), the height h (m) and the weight in water
    (kg/m): H = a w g, top = H + w g h."""
    wg = float(weight) * G
    a = np.asarray(a, dtype=float)
    return a * wg / 1000.0, (a + np.asarray(h, dtype=float)) * wg / 1000.0


# ---------------------------------------------------------------------------
# the touching-down catenary in terms of q = h / a
# ---------------------------------------------------------------------------

def _acosh1p(q):
    """acosh(1 + q), accurate for small q."""
    q = np.maximum(q, 0.0)
    return np.log1p(q + np.sqrt(q * (q + 2.0)))


def span(a, h):
    """X = a acosh(1 + h/a): how far the touching-down catenary reaches flat over the height h."""
    a, h = np.asarray(a, dtype=float), np.asarray(h, dtype=float)
    return a * _acosh1p(h / np.maximum(a, 1e-300))


def suspended(a, h):
    """s = sqrt(h² + 2 a h): its length from the touch-down to the height h."""
    a, h = np.asarray(a, dtype=float), np.asarray(h, dtype=float)
    return np.sqrt(h * h + 2.0 * a * h)


SMALL = 8                       # this many moments or fewer: the bisections run on plain numbers (task 0159: posing a
#                                 cable into the sea solved one moment with ~2,500 tiny array steps per catenary)


def _acosh1p_1(q: float) -> float:
    q = max(q, 0.0)
    return math.log1p(q + math.sqrt(q * (q + 2.0)))


def _a_for_span_1(X: float, h: float) -> float:
    """``a_for_span`` for one moment, the same bisection on plain numbers."""
    ratio = X / max(h, _TINY)
    lo, hi = -80.0, 80.0
    for _ in range(ROUNDS * 2):
        mid = 0.5 * (lo + hi)
        q = math.exp(mid)
        if _acosh1p_1(q) / q > ratio:           # reaches further than wanted: q must grow
            lo = mid
        else:
            hi = mid
    return h / math.exp(0.5 * (lo + hi))


def a_for_span(X, h):
    """The catenary parameter a whose touching-down catenary reaches X flat over the height h (bisection on
    ln(h / a); X/h falls from infinity to 0 as h/a grows)."""
    X, h = np.broadcast_arrays(np.asarray(X, dtype=float), np.asarray(h, dtype=float))
    if X.size <= SMALL:
        return np.array([_a_for_span_1(float(x), float(y)) for x, y in zip(X.reshape(-1), h.reshape(-1))]
                        ).reshape(X.shape)
    ratio = X / np.maximum(h, _TINY)
    lo, hi = np.full(ratio.shape, -80.0), np.full(ratio.shape, 80.0)     # ln q
    for _ in range(ROUNDS * 2):
        mid = 0.5 * (lo + hi)
        q = np.exp(mid)
        far = _acosh1p(q) / q > ratio           # reaches further than wanted: q must grow
        lo = np.where(far, mid, lo)
        hi = np.where(far, hi, mid)
    return h / np.exp(0.5 * (lo + hi))


# ---------------------------------------------------------------------------
# the catenary through two points (the lifted case)
# ---------------------------------------------------------------------------

def _k_for(rho):
    """k with sinh(k) / k = rho (rho >= 1)."""
    rho = np.maximum(np.asarray(rho, dtype=float), 1.0)
    lo, hi = np.zeros(rho.shape), np.full(rho.shape, 1.0)
    for _ in range(80):                         # find an upper bound
        grow = np.sinh(hi) / hi < rho
        if not grow.any():
            break
        hi = np.where(grow, hi * 2.0, hi)
    for _ in range(ROUNDS * 2):
        mid = 0.5 * (lo + hi)
        f = np.where(mid > 0.0, np.sinh(mid) / np.where(mid > 0.0, mid, 1.0), 1.0)
        below = f < rho
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    return 0.5 * (lo + hi)


def two_point(X, h, L):
    """(a, x_v): the catenary from (0, 0) to (X, h) of length L (> the straight line): z = a (cosh((x − x_v)/a) −
    cosh(x_v / a)), its lowest point at x_v (left of 0 when it rises from the start)."""
    X, h, L = (np.asarray(v, dtype=float) for v in (X, h, L))
    X = np.maximum(X, _TINY)
    rho = np.sqrt(np.maximum(L * L - h * h, 0.0)) / X
    k = np.maximum(_k_for(rho), 1e-12)
    a = X / (2.0 * k)
    xv = 0.5 * X - a * np.arcsinh(h / (2.0 * a * np.sinh(k)))
    return a, xv


# ---------------------------------------------------------------------------
# the hanging cable
# ---------------------------------------------------------------------------

def _horiz(v):
    out = np.array(v, dtype=float)
    out[..., 2] = 0.0
    return out


def _unit(v, fallback=None):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    out = v / np.maximum(n, 1e-300)
    if fallback is not None:
        out = np.where(n > 1e-12, out, np.broadcast_to(fallback, out.shape))
    return out


def _a_normal_1(lo: float, hi: float, h: float, xi_c: float, eta: float, L: float) -> float:
    """``hang``'s bisection on ln a for one moment, on plain numbers."""
    for _ in range(ROUNDS):
        mid = 0.5 * (lo + hi)
        a = math.exp(mid)
        X = a * _acosh1p_1(h / max(a, 1e-300))
        x = xi_c - math.sqrt(max(X * X - eta * eta, 0.0))
        if x + math.sqrt(h * h + 2.0 * a * h) > L:     # too long: a must grow
            lo = mid
        else:
            hi = mid
    return math.exp(0.5 * (lo + hi))


def hang(top, start, aft, bottom_z, length) -> dict:
    """The cable from the hang-off points ``top`` (F, 3) down to its end lying on the seabed at ``start`` ((3,) or
    (F, 3); its z is not used), ``aft`` (3,) the flat direction the cable is laid in (from the vessel towards its
    end), ``bottom_z`` the height of the cable's middle lying on the seabed, ``length`` (F,) from T to S.

    Returns arrays over the F moments: ``kind`` (NORMAL, LIFTED, PILED, STRETCHED), ``a`` (m), ``suspended``
    (length hanging), ``laid`` (length on the seabed), ``tdp`` (F, 3) the touch-down point (S when lifted),
    ``layback`` (flat distance from T to the TDP), ``angle`` (below horizontal at T, rad), ``direction`` (F, 3) the
    unit tangent at T pointing down the cable, ``excess`` (m of cable piled up, or missing when stretched), ``h``,
    and what ``points`` needs."""
    top = np.asarray(top, dtype=float).reshape(-1, 3)
    F = len(top)
    S = np.broadcast_to(np.asarray(start, dtype=float), (F, 3)).copy()
    S[:, 2] = bottom_z
    u = np.tile(_unit(_horiz(np.asarray(aft, dtype=float).reshape(3))), (F, 1))
    L = np.broadcast_to(np.asarray(length, dtype=float), (F,)).astype(float)
    h = np.maximum(top[:, 2] - float(bottom_z), 1e-6)
    d = _horiz(top - S)                                    # flat, from S to T
    xi = -(d * u).sum(1)                                   # T lies this far from S towards the vessel
    # the hang-off level with or behind the cable's end (the vessel went back over it): the cable lies from its end
    # towards the hang-off instead of along the lay line (it can then touch down, or pile up, as anywhere else)
    back = xi <= 1e-9
    if back.any():
        n0 = np.linalg.norm(d[back], axis=1)
        turn = n0 > 1e-9
        idx = np.flatnonzero(back)[turn]
        u[idx] = -d[idx] / n0[turn][:, None]
        xi = -(d * u).sum(1)
    lat_v = d + xi[:, None] * u
    eta = np.linalg.norm(lat_v, axis=1)
    X0 = np.linalg.norm(d, axis=1)
    line = np.sqrt(X0 * X0 + h * h)
    xi_c = np.maximum(xi, 0.0)
    # the shortest and longest the cable can be while it touches down between S and under T
    a_full = a_for_span(X0, h)                              # nothing laid: TDP at S
    s_full = suspended(a_full, h)
    a_flat = a_for_span(np.maximum(eta, 1e-9), h)          # all laid: TDP under T (beside it by eta)
    most = xi_c + suspended(a_flat, h)
    kind = np.full(F, NORMAL, dtype=np.int64)
    kind = np.where(L > most + 1e-9, PILED, kind)
    kind = np.where((L < s_full - 1e-9) & (xi > 1e-9), LIFTED, kind)
    kind = np.where(L <= line + 1e-9, STRETCHED, kind)
    # NORMAL: bisection on ln a between a_flat (all laid) and a_full (nothing laid); x + s falls as a grows
    lo, hi = np.log(np.minimum(a_flat, a_full)), np.log(np.maximum(a_full, a_flat))
    if F <= SMALL:
        a_n = np.array([_a_normal_1(*v) for v in zip(lo, hi, h, xi_c, eta, L)])
    else:
        for _ in range(ROUNDS):
            mid = 0.5 * (lo + hi)
            a = np.exp(mid)
            X = span(a, h)
            x = xi_c - np.sqrt(np.maximum(X * X - eta * eta, 0.0))
            long_ = x + suspended(a, h) > L                 # too long: a must grow
            lo = np.where(long_, mid, lo)
            hi = np.where(long_, hi, mid)
        a_n = np.exp(0.5 * (lo + hi))
    X_n = span(a_n, h)
    x_n = np.clip(xi_c - np.sqrt(np.maximum(X_n * X_n - eta * eta, 0.0)), 0.0, None)
    s_n = suspended(a_n, h)
    # the touch-down on the lay line, the flat way from it to T
    tdp = S - x_n[:, None] * u
    hdir = np.where(np.linalg.norm(_horiz(top - tdp), axis=1, keepdims=True) > 1e-12, _unit(_horiz(top - tdp)), -u)
    out = {"kind": kind, "h": h, "S": S, "T": top, "u": u, "L": L}
    a_out, s_out, x_out, X_out = a_n.copy(), s_n.copy(), x_n.copy(), X_n.copy()
    excess = np.zeros(F)
    # PILED: hangs (almost) straight down beside/under T, the rest snakes on the seabed
    pile = kind == PILED
    if pile.any():
        a_out[pile] = a_flat[pile]
        s_out[pile] = suspended(a_flat[pile], h[pile])
        x_out[pile] = L[pile] - s_out[pile]                 # the snake's length
        X_out[pile] = eta[pile]
        excess[pile] = L[pile] - most[pile]
        tdp[pile] = S[pile] - xi_c[pile, None] * u[pile]
    # LIFTED: the catenary through S and T of length L
    lift = kind == LIFTED
    xv = np.zeros(F)
    if lift.any():
        a2, xv2 = two_point(X0[lift], h[lift], L[lift])
        a_out[lift], xv[lift] = a2, xv2
        s_out[lift], x_out[lift], X_out[lift] = L[lift], 0.0, X0[lift]
        tdp[lift] = S[lift]
    # STRETCHED: straight
    st = kind == STRETCHED
    if st.any():
        s_out[st], x_out[st], X_out[st] = L[st], 0.0, X0[st]
        excess[st] = L[st] - line[st]
        tdp[st] = S[st]
    flat_ts = _horiz(top - S)
    hdir_ts = np.where(np.linalg.norm(flat_ts, axis=1, keepdims=True) > 1e-12, _unit(flat_ts), -u)
    hdir = np.where((lift | st)[:, None], hdir_ts, hdir)
    # the tangent at T, pointing down along the cable
    a_safe = np.maximum(a_out, 1e-300)
    up = (hdir * a_out[:, None] + np.array([0.0, 0.0, 1.0]) * s_out[:, None]) / (a_out + h)[:, None]
    if lift.any():
        m = np.sinh((X0[lift] - xv[lift]) / a_safe[lift])
        up[lift] = (hdir[lift] + np.array([0.0, 0.0, 1.0]) * m[:, None]) / np.sqrt(1.0 + m * m)[:, None]
    if st.any():
        up[st] = _unit(top[st] - S[st])
    direction = -_unit(up)
    angle = np.arcsin(np.clip(-direction[:, 2], -1.0, 1.0))
    out.update(kind=kind, a=a_out, suspended=s_out, laid=x_out, tdp=tdp, layback=X_out, angle=angle,
               direction=direction, excess=excess, xv=xv, hdir=hdir, X0=X0, xi=xi_c, line=line)
    return out


def points(res: dict, lam) -> np.ndarray:
    """Points of the cable at the arc lengths ``lam`` (F, k) from T (0) towards S (``res['L']``), (F, k, 3)."""
    lam = np.asarray(lam, dtype=float)
    F = len(res["kind"])
    lam = np.broadcast_to(lam, (F,) + lam.shape[-1:]).astype(float)
    kind, a, h, s = res["kind"], res["a"], res["h"], res["suspended"]
    T, S, u, hdir, tdp = res["T"], res["S"], res["u"], res["hdir"], res["tdp"]
    zb = S[:, 2]
    out = np.zeros(lam.shape + (3,))
    z_up = np.array([0.0, 0.0, 1.0])
    # touching down (NORMAL, PILED): sigma from the TDP = s - lam on the hanging part, then laid
    sig = np.clip(s[:, None] - lam, 0.0, None)
    a2 = np.maximum(a, 1e-300)[:, None]
    xh = a2 * np.arcsinh(sig / a2)
    zh = np.sqrt(a2 * a2 + sig * sig) - a2
    hang_pts = tdp[:, None, :] + hdir[:, None, :] * xh[..., None] + z_up * zh[..., None]
    hang_pts[..., 2] = zb[:, None] + zh
    beyond = np.clip(lam - s[:, None], 0.0, None)
    laid_pts = tdp[:, None, :] + u[:, None, :] * beyond[..., None]
    laid_pts[..., 2] = zb[:, None]
    normal = np.where((lam <= s[:, None])[..., None], hang_pts, laid_pts)
    out[:] = normal
    pile = kind == PILED
    if pile.any():
        # straight from S along the lay line, the extra length in one bight next to the TDP (task 0248); a bight that
        # lay there when the hang-off was let go stays where it lay further on
        b = bight(res)
        q = np.clip(beyond[pile], 0.0, None)
        along, side = _laid_at(q, *(b[k][pile][:, None] for k in ("R", "theta", "length", "span", "f_R", "f_theta",
                                                                    "f_length", "f_span", "f_at")))
        n = b["side"][pile]
        pts = tdp[pile][:, None, :] + u[pile][:, None, :] * along[..., None] + n[:, None, :] * side[..., None]
        pts[..., 2] = zb[pile][:, None]
        hp = hang_pts[pile]
        out[pile] = np.where((lam[pile] <= s[pile][:, None])[..., None], hp, pts)
    lift = kind == LIFTED
    if lift.any():
        al, xv = a[lift][:, None], res["xv"][lift][:, None]
        L = res["L"][lift][:, None]
        sigma = np.clip(L - lam[lift], 0.0, None)          # arc length from S
        x = xv + al * np.arcsinh(sigma / al + np.sinh(-xv / al))
        z = al * (np.cosh((x - xv) / al) - np.cosh(xv / al))
        hd = res["hdir"][lift]
        p = S[lift][:, None, :] + hd[:, None, :] * x[..., None]
        p[..., 2] = zb[lift][:, None] + z
        out[lift] = p
    st = kind == STRETCHED
    if st.any():
        f = np.clip(lam[st] / np.maximum(res["L"][st][:, None], 1e-300), 0.0, 1.0)
        out[st] = T[st][:, None, :] + (S[st] - T[st])[:, None, :] * f[..., None]
    return out


def _sinc(t):
    t = np.asarray(t, dtype=float)
    return np.where(np.abs(t) < 1e-8, 1.0 - t * t / 6.0, np.sin(t) / np.where(np.abs(t) < 1e-8, 1.0, t))


def _theta_for(want_sinc) -> np.ndarray:
    """θ in [0, π] with sin θ / θ = ``want_sinc`` (0 … 1; it falls monotonically over [0, π])."""
    want = np.clip(np.asarray(want_sinc, dtype=float), 0.0, 1.0)
    lo, hi = np.zeros(want.shape), np.full(want.shape, math.pi)
    for _ in range(BIGHT_ROUNDS):
        mid = 0.5 * (lo + hi)
        big = _sinc(mid) > want                          # sinc still too big: turn more
        lo, hi = np.where(big, mid, lo), np.where(big, hi, mid)
    return 0.5 * (lo + hi)


def _theta_for_radius(excess, r_min) -> np.ndarray:
    """The largest θ whose bight carrying ``excess`` has the radius ``r_min``: R = e / (4 θ (1 − sinc θ)) falls as θ
    grows."""
    e, r = np.asarray(excess, dtype=float), np.asarray(r_min, dtype=float)
    lo, hi = np.zeros(e.shape), np.full(e.shape, math.pi)
    for _ in range(BIGHT_ROUNDS):
        mid = 0.5 * (lo + hi)
        g = 4.0 * mid * (1.0 - _sinc(mid))
        wide = e >= r * g                                # R(mid) >= r_min: may turn more
        lo, hi = np.where(wide, mid, lo), np.where(wide, hi, mid)
    return lo


def bight(res: dict) -> dict:
    """The bight of a piled cable on the seabed (task 0248): from the TDP along the lay line ``u`` towards S the cable
    lies in **one smooth curve to one side** and then straight on to S. The curve is four circular arcs of one radius
    R – off the line by θ, back across by 2θ, onto the line by θ – so it leaves the TDP and meets the straight in line
    (no kink), with no point of it tighter than R. It carries the extra length e = laid − (S … TDP) over the stretch
    ``span`` next to the TDP: span = length · sin θ / θ, length = 4 R θ.

    R is ``BIGHT_EASE`` x the cable's smallest bend radius ``res['r_min']``: a small extra length lies in a long, flat
    curve (θ small), a large one in a compact, rounder bight close to the touch-down (θ up to ``BIGHT_TURN_MAX``, an Ω;
    beyond that R grows instead – the feet of the Ω would cross). Without a bend radius the turn is ``BIGHT_TURN``.
    The stretch never reaches past ``res['keep']`` metres from S (the cable that lay there when its hang-off was let
    go stays where it lay) nor past S: where it would, the bight turns more – it grows sideways, up to a loop (θ = π)
    – and may then be tighter than ``r_min`` (a warned case, or a let-go whose slide forward could not take up its
    extra length). Without ``r_min`` / ``keep`` in ``res`` (NaN or missing): none / nothing kept.

    **A bight that lay there when the hang-off was let go** (``res['frozen_span']``, ``res['frozen_extra']``: its
    span and extra length then, NaN / 0: none) lies where it lay – from ``keep`` metres from S on, towards the TDP –
    and only the extra length beyond its own goes into the bight next to the TDP (in the stretch between the two).
    Should there be less extra length than it had (nothing piles up that much), it keeps its span and lies flatter.

    Returns arrays over the moments: ``R``, ``theta``, ``length`` (of the curve), ``span`` (along the line), ``side``
    (F, 3) the flat unit it bends towards; the kept bight's ``f_R``, ``f_theta``, ``f_length``, ``f_span`` and
    ``f_at`` (from the TDP along the line to its start); zeros where the cable is not piled."""
    kind = res["kind"]
    F = len(kind)
    pile = kind == PILED
    out = {k: np.zeros(F) for k in ("R", "theta", "length", "span", "f_R", "f_theta", "f_length", "f_span", "f_at")}
    u = res["u"]
    side = np.cross(np.array([0.0, 0.0, 1.0]), u)
    out["side"] = side / np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-12)
    if not pile.any():
        return out

    def per(key, default):
        v = np.asarray(res.get(key, np.full(F, default)), dtype=float)
        return np.broadcast_to(v, (F,))[pile]

    xs = np.asarray(res["xi"], dtype=float)[pile]                          # S … TDP along the line
    e = np.clip(np.asarray(res["laid"], dtype=float)[pile] - xs, 0.0, None)
    r_min = per("r_min", 0.0)
    r_min = np.where(np.isfinite(r_min), np.maximum(r_min, 0.0), 0.0)
    keep = per("keep", np.nan)
    keep = np.clip(np.where(np.isfinite(keep), keep, 0.0), 0.0, xs)
    f_span, f_e = per("frozen_span", np.nan), per("frozen_extra", 0.0)
    frozen = np.isfinite(f_span) & np.isfinite(f_e) & (f_e > 1e-12) & (keep + np.nan_to_num(f_span) <= xs + 1e-9)
    f_span = np.where(frozen, np.nan_to_num(f_span), 0.0)
    f_e = np.where(frozen, np.minimum(np.nan_to_num(f_e), e), 0.0)          # (less extra than it had: it lies flatter)
    f_th = np.where(frozen, _theta_for(f_span / np.maximum(f_span + f_e, 1e-300)), 0.0)
    f_len = f_span + f_e
    out["f_R"][pile] = np.where(frozen, f_len / np.maximum(4.0 * f_th, 1e-300), 0.0)
    out["f_theta"][pile], out["f_length"][pile], out["f_span"][pile] = f_th, f_len, f_span
    out["f_at"][pile] = np.where(frozen, xs - keep - f_span, 0.0)
    e = e - f_e                                                             # what the bight next to the TDP carries
    room = np.clip(xs - keep - f_span, 0.0, xs)                             # the stretch it may use
    th = np.full(len(xs), BIGHT_TURN)
    tight = r_min > 0.0
    if tight.any():
        th[tight] = np.minimum(_theta_for_radius(e[tight], BIGHT_EASE * r_min[tight]), BIGHT_TURN_MAX)
    th = np.maximum(th, 1e-6)
    sc = _sinc(th)
    span = e * sc / np.maximum(1.0 - sc, 1e-300)
    cramped = span > room
    if cramped.any():                                    # no room for it: it turns more (sideways, up to a loop)
        th[cramped] = np.maximum(_theta_for(room[cramped] / np.maximum(room[cramped] + e[cramped], 1e-300)), th[cramped])
        span = np.where(cramped, room, span)
    length = span + e
    none = e <= 1e-12
    out["R"][pile] = np.where(none, 0.0, length / np.maximum(4.0 * th, 1e-300))
    out["theta"][pile] = np.where(none, 0.0, th)
    out["length"][pile] = np.where(none, 0.0, length)
    out["span"][pile] = np.where(none, 0.0, span)
    return out


def _laid_at(q, R, th, length, span, f_R, f_th, f_length, f_span, f_at):
    """(along, side) of the cable on the seabed at arc length ``q`` from the TDP (piled moments): the bight next to
    the TDP, straight, the kept bight (``f_*``, starting ``f_at`` along the line from the TDP), straight to S."""
    q = np.asarray(q, dtype=float)
    a1, s1 = _bight_at(np.minimum(q, length), R, th)
    along = np.where(q > length, span + (q - length), a1)
    side = np.where(q > length, 0.0, s1)
    q_f = length + np.maximum(f_at - span, 0.0)              # where the kept bight starts, along the cable
    has = f_length > 0.0
    t = q - q_f
    a2, s2 = _bight_at(np.clip(t, 0.0, f_length), f_R, f_th)
    in_f = has & (t > 0.0)
    along = np.where(in_f, f_at + np.where(t > f_length, f_span + (t - f_length), a2), along)
    side = np.where(in_f & (t <= f_length), s2, side)
    return along, side


def _bight_at(q, R, theta):
    """(along, side): the point at arc length ``q`` (…, k) along the bight of radius R and turn θ (…, 1), from its
    start at the TDP: along the line and off it."""
    q = np.asarray(q, dtype=float)
    R = np.broadcast_to(np.asarray(R, dtype=float), q.shape)
    th = np.broadcast_to(np.asarray(theta, dtype=float), q.shape)
    Rs = np.maximum(R, 1e-300)
    a1 = R * th                                           # end of the first arc, of the second (3 R θ), total 4 R θ
    a2 = 3.0 * R * th
    # first arc: heading 0 -> θ (turning towards the side)
    t1 = np.minimum(q, a1) / Rs
    x = R * np.sin(t1)
    y = R * (1.0 - np.cos(t1))
    # second arc: heading θ -> −θ
    t2 = np.clip(q - a1, 0.0, 2.0 * a1) / Rs
    x = x + R * (np.sin(th) - np.sin(th - t2))
    y = y + R * (np.cos(th - t2) - np.cos(th))
    # third arc: heading −θ -> 0
    t3 = np.clip(q - a2, 0.0, a1) / Rs
    x = x + R * (np.sin(t3 - th) + np.sin(th))
    y = y + R * (np.cos(th) - np.cos(t3 - th))
    flat = R <= 0.0
    return np.where(flat, q, x), np.where(flat, 0.0, y)


# ---------------------------------------------------------------------------
# leaving the last wheel
# ---------------------------------------------------------------------------

def _rot(rho, k, psi):
    """rho (F, 3) square to k (F, 3) turned by psi (F,) about k."""
    c, s = np.cos(psi)[:, None], np.sin(psi)[:, None]
    return rho * c + np.cross(k, rho) * s


def wheel_point(centre, axis, radius, side, arrive, psi):
    """(T, tangent): the point at the wrap ``psi`` round the wheel from the arrival point ``arrive`` and the
    cable's direction there. centre, axis, arrive (F, 3); radius (F,) or scalar; side ±1 (turns about ±axis)."""
    centre = np.asarray(centre, dtype=float).reshape(-1, 3)
    F = len(centre)
    k = _unit(np.asarray(axis, dtype=float).reshape(-1, 3) * np.asarray(side, dtype=float).reshape(-1, 1))
    k = np.broadcast_to(k, (F, 3))
    rho = np.asarray(arrive, dtype=float).reshape(-1, 3) - centre
    rho = rho - (rho * k).sum(1, keepdims=True) * k
    rho = _unit(rho)
    r = np.broadcast_to(np.asarray(radius, dtype=float), (F,))
    psi = np.broadcast_to(np.asarray(psi, dtype=float), (F,))
    rp = _rot(rho, k, psi)
    return centre + rp * r[:, None], np.cross(k, rp)


def _wrap_of(direction, k, t0):
    """The wrap at which the wheel's tangent points along ``direction`` (projected on the wheel's plane)."""
    e = direction - (direction * k).sum(1, keepdims=True) * k
    e = _unit(e)
    return np.arctan2((np.cross(t0, e) * k).sum(1), (t0 * e).sum(1))


def _in_range(want, wmax):
    """The wrap ``want`` (rad, -π … π) turned by a whole turn where that brings it nearer the range 0 … wmax: half a
    turn and a bit round a 180° chute is beyond its end (steep), not before its start (task 0125)."""
    want = np.asarray(want, dtype=float)
    best, gap = want.copy(), np.maximum(np.maximum(-want, want - wmax), 0.0)
    for turn in (2.0 * math.pi, -2.0 * math.pi):
        w = want + turn
        g = np.maximum(np.maximum(-w, w - wmax), 0.0)
        better = g < gap - 1e-12
        best, gap = np.where(better, w, best), np.where(better, g, gap)
    return best


def _way_want(res: dict, k, t0, wmax) -> np.ndarray:
    """(F,): the wrap the catenary wants to leave at (task 0172, 0374) – where the wheel's tangent points along the
    catenary's direction at T; for a wheel lying (nearly) flat (its plane holds less than ``FLAT`` of "down": a
    quadrant tipped flat) blended towards where it points along the lay direction ``u`` (from the touch-down towards
    S), fully that where it lies flat. A cable hanging straight down past a flat wheel has no direction in the wheel's
    plane worth the name: its sideways part moved the leave point from one end of the gutter to its middle and back.
    Task 0374: the two WRAPS are blended, not the two directions – where they point opposite ways (a gutter tipped about
    the lay line: "down" at its near end, the lay at its far end) a blend of directions passed through nothing and the
    leave point jumped from one end to the other in one step; the wraps' blend goes over the gutter from end to end."""
    # a piled cable reads its wrap from straight down (task 0172) – eased in over its first ``PILE_EASE`` m of piled
    # cable (task 0374): where it just piles up, its real direction (down and sideways to its touch-down beside T) and
    # "down" differ by up to 90°, and the leave point jumped by them in one step
    q = np.where(res["kind"] == PILED, np.clip(res["excess"] / PILE_EASE, 0.0, 1.0), 0.0)[:, None]
    d = _unit((1.0 - q) * res["direction"] + q * np.array([0.0, 0.0, -1.0]), np.array([0.0, 0.0, -1.0]))
    want_d = _in_range(_wrap_of(d, k, t0), wmax)
    u = res["u"]
    u_in = u - (u * k).sum(1, keepdims=True) * k
    down_in = np.sqrt(np.clip(1.0 - k[:, 2] ** 2, 0.0, 1.0))      # how much of "down" the wheel's plane holds
    w = np.clip(1.0 - down_in / FLAT, 0.0, 1.0)
    w = np.where(np.linalg.norm(u_in, axis=1) > 1e-9, w, 0.0)
    if not (w > 0.0).any():
        return want_d
    want_u = _in_range(_wrap_of(u, k, t0), wmax)
    # the cable's own wrap counts as much as its direction lies in the wheel's plane: a cable hanging (nearly) straight
    # down past a flat wheel has a wrap that turns round in no time (its few degrees off the vertical point anywhere)
    mag = np.linalg.norm(d - (d * k).sum(1, keepdims=True) * k, axis=1)
    # beyond both ends (the cable points out of the open side of a gutter): the turn nearer the lay's end
    x = _wrap_of(d, k, t0)
    best = want_d.copy()
    for turn in (0.0, 2.0 * math.pi, -2.0 * math.pi):
        c = x + turn
        out_c = np.maximum(np.maximum(-c, c - wmax), 0.0)
        out_b = np.maximum(np.maximum(-best, best - wmax), 0.0)
        nearer = np.abs(np.clip(c, 0.0, wmax) - want_u) < np.abs(np.clip(best, 0.0, wmax) - want_u) - 1e-12
        best = np.where((out_c > 0.0) & (out_b > 0.0) & nearer, c, best)
    # both taken into the wheel's range first: the blend of two ends is a point on the wheel between them
    lo, hi = -0.25 * math.pi, wmax + 0.25 * math.pi
    a, b = np.clip(best, lo, hi), np.clip(want_u, lo, hi)
    wd = (1.0 - w) * mag
    blend = (wd * a + w * b) / np.maximum(wd + w, 1e-300)
    return np.where(w > 0.0, blend, want_d)


def _bend(t, d):
    """(theta, m): the turn from the unit tangent t to the unit direction d, and the unit m square to t towards d."""
    c = np.clip((t * d).sum(1), -1.0, 1.0)
    m = d - c[:, None] * t
    n = np.linalg.norm(m, axis=1, keepdims=True)
    m = np.where(n > 1e-12, m / np.maximum(n, 1e-300), 0.0)
    return np.arccos(c), m


def _bend_low(T, t, m, r, theta) -> np.ndarray:
    """(F,): the lowest height a free bend (from T along t, turning towards m by theta on the radius r) reaches."""
    phi = theta[:, None] * np.linspace(0.0, 1.0, 33)[None, :]
    z = T[:, 2, None] + r[:, None] * (np.sin(phi) * t[:, 2, None] + (1.0 - np.cos(phi)) * m[:, 2, None])
    return z.min(axis=1)


def _bend_fit(T, t, m, r, theta, floor: float) -> np.ndarray:
    """(F,): how far (≤ theta) a free bend from T along t, turning towards m on the radius r, turns before it comes
    down to the height ``floor`` (task 0172: it ends there, on the seabed, instead of curling into it)."""
    T, t, m = (np.asarray(x, dtype=float).reshape(-1, 3) for x in (T, t, m))
    r = np.broadcast_to(np.asarray(r, dtype=float), (len(T),))
    theta = np.asarray(theta, dtype=float)

    def z(phi):
        return T[:, 2] + r * (np.sin(phi) * t[:, 2] + (1.0 - np.cos(phi)) * m[:, 2])

    n = 64
    grid = theta[:, None] * np.linspace(0.0, 1.0, n + 1)[None, :]
    zz = T[:, 2, None] + r[:, None] * (np.sin(grid) * t[:, 2, None] + (1.0 - np.cos(grid)) * m[:, 2, None])
    below = zz <= floor
    out = theta.copy()
    hit = below.any(axis=1)
    if hit.any():
        first = np.argmax(below, axis=1)                    # the first step at or below the floor
        lo = np.where(first > 0, grid[np.arange(len(T)), np.maximum(first - 1, 0)], 0.0)
        hi = grid[np.arange(len(T)), first]
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            over = z(mid) > floor
            lo, hi = np.where(over, mid, lo), np.where(over, hi, mid)
        out = np.where(hit, np.where(first > 0, lo, 0.0), theta)
    return out


def bend_points(res: dict, n: int):
    """(points (F, n, 3), arc lengths (F, n) from the wheel's leave point): the free bend between the wheel and the
    catenary (``hang_off``), at n steps of equal turn ending where the catenary starts (all at the leave point when
    there is no bend)."""
    t, m, theta, rb = res["bend_t"], res["bend_m"], res["bend"], res["bend_r"]
    T0 = res["T_wheel"]
    phi = theta[:, None] * (np.arange(1, n + 1) / max(n, 1))[None, :]
    pts = T0[:, None, :] + rb[:, None, None] * (np.sin(phi)[..., None] * t[:, None, :]
                                                 + (1.0 - np.cos(phi))[..., None] * m[:, None, :])
    return pts, rb[:, None] * phi


JUMP = 0.5                      # rad: the wrap of a frame this far from the frames round it is the other answer
SPIKE = 2                       # frames: at most this many frames in a row on the other answer are put back


def _rows(x, sel, F: int):
    """The rows ``sel`` of an input of ``hang_off`` that has one row per moment; shared inputs as they are."""
    a = np.asarray(x, dtype=float)
    if a.ndim == 2 and a.shape[0] == F:
        return a[sel]
    if a.ndim == 1 and a.shape[0] == F:        # (only the per-moment inputs come here: start and aft never do)
        return a[sel]
    return x


def hang_off_steady(centre, axis, radius, side, arrive, wrap_max, start, aft, bottom_z, length0,
                    frames=None) -> dict:
    """``hang_off`` along an animation, each moment kept on the answer of the moment before (task 0160, bug hunt 0147
    row 21a). Where the wheel lies nearly flat (a sheave let go, settling onto the seabed) the wrap has two answers,
    and a moment worked out on its own now and then took the other one: the cable slid 0.8 m for one frame and back.
    A run of at most ``SPIKE`` moments whose wrap is more than ``JUMP`` from the moments on both sides (which agree)
    is worked out again starting from the moment before; a moment that then lands near it takes that answer.
    ``frames`` (F,): the frame number of each moment (only moments next to each other are compared)."""
    res = hang_off(centre, axis, radius, side, arrive, wrap_max, start, aft, bottom_z, length0)
    psi = res["psi"]
    F = len(psi)
    fr = np.arange(F) if frames is None else np.asarray(frames)
    j = 1
    while j < F - 1:
        if fr[j] != fr[j - 1] + 1 or abs(psi[j] - psi[j - 1]) <= JUMP:
            j += 1
            continue
        end = None
        for e in range(j + 1, min(F, j + SPIKE + 1)):
            if fr[e] != fr[e - 1] + 1:
                break
            if abs(psi[e] - psi[j - 1]) <= JUMP:
                end = e
                break
        if end is None:
            j += 1
            continue
        sel = np.arange(j, end)
        sub = hang_off(*(_rows(x, sel, F) for x in (centre, axis, radius, side, arrive, wrap_max)), start, aft,
                       bottom_z, _rows(length0, sel, F), psi0=np.full(len(sel), psi[j - 1]))
        good = np.abs(sub["psi"] - psi[j - 1]) <= JUMP
        if good.any():
            for key, v in res.items():
                if isinstance(v, np.ndarray) and v.shape[:1] == (F,) and key in sub:
                    v[sel[good]] = sub[key][good]
        j = end
    return _slide(res, fr, (centre, axis, radius, side, arrive, wrap_max), start, aft, bottom_z, length0)


SLIDE = 0.1                     # m: the leave point moves at most this far round its wheel between neighbouring frames


def _slide(res: dict, fr, wheel, start, aft, bottom_z, length0) -> dict:
    """Task 0374 (0172's open point 1): the leave point slides round its wheel, at most ``SLIDE`` m between
    neighbouring frames, instead of jumping. A slack cable on a gutter tipping through flat has two places to lie (its
    answer folds: the one it lies at goes away and the next is at the other end), and the moment it went its leave
    point jumped 4–7 m in one frame. Now it keeps the end it was at and slides over to the other in a few frames; the
    moments on the way are worked out at the wrap they have reached."""
    psi = res["psi"]
    F = len(psi)
    if F < 2:
        return res
    r = np.broadcast_to(np.asarray(wheel[2], dtype=float), (F,))
    step = SLIDE / np.maximum(r, 1e-9)
    lim = psi.copy()
    for j in range(1, F):
        if fr[j] == fr[j - 1] + 1:
            lim[j] = min(max(psi[j], lim[j - 1] - step[j]), lim[j - 1] + step[j])
    sel = np.flatnonzero(np.abs(lim - psi) > 1e-9)
    if not len(sel):
        return res
    sub = hang_off(*(_rows(x, sel, F) for x in wheel), start, aft, bottom_z, _rows(length0, sel, F),
                   psi_fixed=lim[sel])
    for key, v in res.items():
        if isinstance(v, np.ndarray) and v.shape[:1] == (F,) and key in sub:
            v[sel] = sub[key]
    return res


def hang_off(centre, axis, radius, side, arrive, wrap_max, start, aft, bottom_z, length0, psi0=None,
             psi_fixed=None) -> dict:
    """Where the cable leaves its last wheel into the sea, and the catenary from there.

    ``length0`` (F,): the cable's length from the arrival point on the wheel to its end S (so from T(ψ) it is
    length0 − r ψ). ``wrap_max`` (F,) or scalar: the wheel's end (a chute ends; a sheave: half a turn).
    Returns ``hang``'s result for T(ψ) plus ``psi`` (F,), ``T`` (F, 3), ``steep`` (F,) the catenary wants to leave
    beyond the wheel's end (it leaves at the end with a kink of ``kink`` rad), ``short`` (F,) it leaves before
    it arrives (it does not touch the wheel; ψ = 0). ``psi_fixed`` (F,): leave at this wrap (no search; task 0374's
    slide over time)."""
    centre = np.asarray(centre, dtype=float).reshape(-1, 3)
    F = len(centre)
    k = _unit(np.asarray(axis, dtype=float).reshape(-1, 3) * np.asarray(side, dtype=float).reshape(-1, 1))
    k = np.broadcast_to(k, (F, 3)).copy()
    rho = np.asarray(arrive, dtype=float).reshape(-1, 3) - centre
    rho = _unit(rho - (rho * k).sum(1, keepdims=True) * k)
    r = np.broadcast_to(np.asarray(radius, dtype=float), (F,)).astype(float)
    wmax = np.broadcast_to(np.asarray(wrap_max, dtype=float), (F,)).astype(float)
    L0 = np.broadcast_to(np.asarray(length0, dtype=float), (F,)).astype(float)
    t0 = np.cross(k, rho)
    if psi0 is None:                            # where the wheel's tangent points down most
        psi = np.clip(_wrap_of(np.tile([0.0, 0.0, -1.0], (F, 1)), k, t0), 0.0, wmax)
    else:
        psi = np.clip(np.broadcast_to(np.asarray(psi0, dtype=float), (F,)).astype(float), 0.0, wmax)

    def at(p):
        T = centre + _rot(rho, k, p) * r[:, None]
        res = hang(T, start, aft, bottom_z, L0 - r * p)
        return T, res, _way_want(res, k, t0, wmax)

    done = np.zeros(F, dtype=bool)
    if psi_fixed is not None:
        psi = np.clip(np.broadcast_to(np.asarray(psi_fixed, dtype=float), (F,)).astype(float), 0.0, wmax)
        done[:] = True
    for _ in range(0 if psi_fixed is not None else FIX_ROUNDS):
        _T, _res, want = at(psi)
        new = np.clip(want, 0.0, wmax)
        done = np.abs(new - psi) < FIX_TOL
        psi = new
        if done.all():
            break
    if not done.all():                          # no fixed point by rounds: bisection on want(ψ) − ψ
        lo, hi = np.zeros(F), wmax.copy()
        for _ in range(ROUNDS):
            mid = 0.5 * (lo + hi)
            _T, _res, want = at(mid)
            ahead = want > mid
            lo = np.where(ahead, mid, lo)
            hi = np.where(ahead, hi, mid)
        psi = np.where(done, psi, 0.5 * (lo + hi))
    T, res, want = at(psi)
    steep, short = want > wmax + 1e-9, want < -1e-9
    tangent = np.cross(k, _rot(rho, k, psi))
    # the free bend from the wheel's tangent to the catenary's direction (task 0125): the catenary starts where it ends
    theta, m = _bend(tangent, res["direction"])
    use = (theta > BEND_MIN) & ~short
    floor = float(bottom_z) + BED_GAP
    # Task 0172: a wheel near the seabed (a quadrant set down on it): a whole free bend would curl into the seabed. It
    # turns as far as fits above it and the cable lies on the seabed from there (before: it was left out and the cable
    # kinked at the wheel by up to 60°). Where the bend's end comes within ``BED_BAND`` of the seabed its plane turns
    # from the catenary's direction at its end (which lies flat along the seabed there: no plane to bend down in) to
    # the catenary's direction at the wheel – one plane on both sides of "it reaches the seabed", no jump.
    m_T = m.copy()
    theta = np.where(use, _bend_fit(T, tangent, m, r, theta, floor), 0.0)
    if use.any():
        L1 = L0 - r * psi
        act = np.flatnonzero(use)                          # the moments still being worked out
        for _ in range(BEND_ROUNDS):
            Ta, ta, ra, th, ma = T[act], tangent[act], r[act], theta[act], m[act]
            top = Ta + ra[:, None] * (np.sin(th)[:, None] * ta + (1.0 - np.cos(th))[:, None] * ma)
            sub = hang(top, _rows(start, act, F), aft, bottom_z, (L1 - r * theta)[act])
            want, m_E = _bend(ta, sub["direction"])
            beta = np.clip(1.0 - (top[:, 2] - floor) / BED_BAND, 0.0, 1.0)[:, None]
            m_new = (1.0 - beta) * m_E + beta * m_T[act]
            m_new = m_new - (m_new * ta).sum(1, keepdims=True) * ta
            m_new = np.where(np.linalg.norm(m_new, axis=1, keepdims=True) > 1e-9, _unit(m_new), m_T[act])
            new = _bend_fit(Ta, ta, m_new, ra, want, floor)
            done = (np.abs(new - th) < 1e-10) & (np.abs(m_new - ma).max(axis=1) < 1e-10)
            # (half steps: where the bend's end hangs over the lay line the catenary's sideways pull changes side with
            # it, and full steps went back and forth for ever; half steps settle between)
            both = ma + m_new
            m_half = np.where(np.linalg.norm(both, axis=1, keepdims=True) > 1e-9, _unit(both), m_new)
            m[act] = np.where(done[:, None], m_new, m_half)
            theta[act] = np.where(done, new, _bend_fit(Ta, ta, m[act], ra, 0.5 * (th + new), floor))
            act = act[~done]
            if not len(act):
                break
        top = T + r[:, None] * (np.sin(theta)[:, None] * tangent + (1.0 - np.cos(theta))[:, None] * m)
        res = hang(top, start, aft, bottom_z, L1 - r * theta)
    res["psi"], res["T_wheel"] = psi, T
    res["steep"], res["short"] = steep, short
    res["kink"] = theta                         # the free bend's turn (rad): 0 when the cable leaves the wheel smoothly
    res["bend"], res["bend_t"], res["bend_m"], res["bend_r"] = theta, tangent, m, r.copy()
    res["tangent"] = tangent
    return res


# ---------------------------------------------------------------------------
# setting the touch-down (the anchor)
# ---------------------------------------------------------------------------

def anchor(centre, axis, radius, side, arrive, wrap_max, aft, bottom_z, a=None, layback=None,
           laid: float = 0.0) -> dict:
    """Where the cable's end on the seabed must lie for the catenary to have the parameter ``a`` (from the bottom
    tension) or the ``layback`` (flat distance from where it leaves the wheel to the touch-down), with ``laid``
    metres on the seabed behind the touch-down. One moment (arrays of length 1 work too). Returns {"psi", "T",
    "start" (S), "tdp", "length0" (from the arrival point to S), "a", "layback", "suspended", "angle"}."""
    centre = np.asarray(centre, dtype=float).reshape(-1, 3)
    F = len(centre)
    k = _unit(np.asarray(axis, dtype=float).reshape(-1, 3) * np.asarray(side, dtype=float).reshape(-1, 1))
    k = np.broadcast_to(k, (F, 3)).copy()
    rho = np.asarray(arrive, dtype=float).reshape(-1, 3) - centre
    rho = _unit(rho - (rho * k).sum(1, keepdims=True) * k)
    r = np.broadcast_to(np.asarray(radius, dtype=float), (F,)).astype(float)
    wmax = np.broadcast_to(np.asarray(wrap_max, dtype=float), (F,)).astype(float)
    u = _unit(_horiz(np.asarray(aft, dtype=float).reshape(3)))
    t0 = np.cross(k, rho)
    psi = np.clip(_wrap_of(np.tile([0.0, 0.0, -1.0], (F, 1)), k, t0), 0.0, wmax)
    z = np.array([0.0, 0.0, 1.0])
    for _ in range(FIX_ROUNDS):
        T = centre + _rot(rho, k, psi) * r[:, None]
        h = np.maximum(T[:, 2] - float(bottom_z), 1e-6)
        aa = np.full(F, float(a)) if a is not None else a_for_span(np.full(F, float(layback)), h)
        s = suspended(aa, h)
        direction = _unit(u * aa[:, None] - z * s[:, None])     # from T down and aft (cos θ = a/(a+h) …)
        new = np.clip(_wrap_of(direction, k, t0), 0.0, wmax)
        if np.all(np.abs(new - psi) < FIX_TOL):
            psi = new
            break
        psi = new
    T = centre + _rot(rho, k, psi) * r[:, None]
    h = np.maximum(T[:, 2] - float(bottom_z), 1e-6)
    aa = np.full(F, float(a)) if a is not None else a_for_span(np.full(F, float(layback)), h)
    X, s = span(aa, h), suspended(aa, h)
    tdp = _horiz(T) + u * X[:, None]
    tdp[:, 2] = bottom_z
    S = tdp + u * float(laid)
    return {"psi": psi, "T": T, "start": S, "tdp": tdp, "length0": r * psi + s + float(laid), "a": aa,
            "layback": X, "suspended": s, "angle": np.arctan2(s, aa)}
