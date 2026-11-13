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
  down under T and the rest lies snaking on the seabed between S and the TDP, so the length stays L.
* ``STRETCHED`` – L shorter than the straight line from T to S: drawn straight (the length is then wrong; the app
  warns).

**Leaving a wheel** (``hang_off``). The cable comes onto its last contact (a horn, chute or sheave: a wheel of
radius r) and leaves it where the catenary's tangent at T is the wheel's tangent – no kink. The point T lies at the
wrap ψ round the wheel from where the cable arrives; the catenary from T(ψ) with L(ψ) = L₀ − r ψ gives a direction,
that direction a ψ: a fixed point, found in a few rounds (T moves little against the span). When the catenary is
steeper than the wheel's end (``wrap_max``: a chute ends) the cable leaves at the end with a kink (``steep``); when
it would leave before it arrives, it does not touch the wheel (``short``, ψ = 0).
"""

from __future__ import annotations

import math

import numpy as np

G = 9.81                        # m/s²
NORMAL, LIFTED, PILED, STRETCHED = 0, 1, 2, 3
KINDS = ("touches down", "lifts off its end", "piles up on the seabed", "is too short")
WET_200 = 51.0                  # kg/m in water of a 200 mm power cable (500 N/m; task 0083's numbers)
ROUNDS = 64                     # bisection steps (2⁻⁶⁴ of the range in log: far below a micrometre)
FIX_ROUNDS = 60                 # rounds of the fixed point on the wrap
FIX_TOL = 1e-12                 # rad
SNAKE = 4.0                     # m: wavelength of cable piled on the seabed (only drawn in the warned case)
_TINY = 1e-9


def wet_weight(diameter: float) -> float:
    """A power cable's weight in water (kg/m) for its diameter (m): 51 kg/m at 200 mm, as the square of Ø."""
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


def a_for_span(X, h):
    """The catenary parameter a whose touching-down catenary reaches X flat over the height h (bisection on
    ln(h / a); X/h falls from infinity to 0 as h/a grows)."""
    X, h = np.broadcast_arrays(np.asarray(X, dtype=float), np.asarray(h, dtype=float))
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
    for _ in range(ROUNDS):
        mid = 0.5 * (lo + hi)
        a = np.exp(mid)
        X = span(a, h)
        x = xi_c - np.sqrt(np.maximum(X * X - eta * eta, 0.0))
        long_ = x + suspended(a, h) > L                     # too long: a must grow
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
        # snaking: the laid part between TDP and S has length laid > the distance between them
        xs = res["xi"][pile]                               # the flat distance S..TDP
        total = res["laid"][pile]
        bb = beyond[pile]
        pts = np.zeros(bb.shape + (3,))
        side_all = np.cross(z_up, u[pile])
        for i, (dist, ln) in enumerate(zip(xs, total)):
            waves = max(1, int(round(max(dist, SNAKE) / SNAKE)))
            amp = _snake_amplitude(max(dist, 1e-6), ln, waves)
            t = np.linspace(0.0, 1.0, 2049)
            x = t * dist
            y = amp * np.sin(2.0 * math.pi * waves * t)
            seg = np.hypot(np.diff(x), np.diff(y))
            arc = np.concatenate([[0.0], np.cumsum(seg)])
            arc *= ln / max(arc[-1], 1e-300)
            q = np.clip(bb[i], 0.0, ln)
            xi_ = np.interp(q, arc, x)
            yi_ = np.interp(q, arc, y)
            pts[i] = tdp[pile][i] + u[pile][i] * xi_[:, None] + side_all[i] * yi_[:, None]
            pts[i, :, 2] = zb[pile][i]
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


def _snake_amplitude(dist: float, length: float, waves: int) -> float:
    """The amplitude of a flat sine with ``waves`` waves over ``dist`` whose length is ``length``."""
    if length <= dist * (1.0 + 1e-12):
        return 0.0
    t = np.linspace(0.0, 1.0, 2049)

    def arc(amp):
        x, y = t * dist, amp * np.sin(2.0 * math.pi * waves * t)
        return float(np.hypot(np.diff(x), np.diff(y)).sum())
    lo, hi = 0.0, max(length, dist)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if arc(mid) < length:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


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


def hang_off(centre, axis, radius, side, arrive, wrap_max, start, aft, bottom_z, length0, psi0=None) -> dict:
    """Where the cable leaves its last wheel into the sea, and the catenary from there.

    ``length0`` (F,): the cable's length from the arrival point on the wheel to its end S (so from T(ψ) it is
    length0 − r ψ). ``wrap_max`` (F,) or scalar: the wheel's end (a chute ends; a sheave: half a turn).
    Returns ``hang``'s result for T(ψ) plus ``psi`` (F,), ``T`` (F, 3), ``steep`` (F,) the catenary wants to leave
    beyond the wheel's end (it leaves at the end with a kink of ``kink`` rad), ``short`` (F,) it leaves before
    it arrives (it does not touch the wheel; ψ = 0)."""
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
        return T, res, _wrap_of(res["direction"], k, t0)

    done = np.zeros(F, dtype=bool)
    for _ in range(FIX_ROUNDS):
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
    res["psi"], res["T"] = psi, T
    res["steep"] = want > wmax + 1e-9
    res["short"] = want < -1e-9
    tangent = np.cross(k, _rot(rho, k, psi))
    res["kink"] = np.arccos(np.clip((tangent * res["direction"]).sum(1), -1.0, 1.0))
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
