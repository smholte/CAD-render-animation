"""Independent tests of the three flex cores (task 0058, subagent E): ``core/flex.py`` (hoses),
``core/flex_chain.py`` (drag chains) and ``core/flex_fit.py`` (a tube mesh's centreline).

Written from the contract (tasks/0058-hoses-cables-drag-chains.md: "Design", "Scope", "Accuracy and speed") and from
what a machine designer expects of real hoses and drag chains, by an agent that wrote none of the three modules.
Everything a test compares with is worked out here, another way: the catenary's closed form, a semicircle, a heavy
cantilever from its differential equation (shooting, Runge-Kutta), a brute-force minimiser of the hose's energy
(Nelder-Mead over a few angles), chains checked pin by pin, tubes swept by this file's own mesh maker.

Tests marked ``xfail(strict=False)`` document what was found wrong or surprising, with the measured numbers in the
reason; every other assertion holds. Run with ``-s`` to see the measured values (lines starting "MEASURED").

Pure NumPy + pytest, no Blender; fixed seeds.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from fresing_render.core import flex
from fresing_render.core import flex_chain as fc
from fresing_render.core import flex_fit as ff

HAS_MOTION = hasattr(flex, "solve_motion")


def _say(name, *values):
    print("MEASURED %-58s %s" % (name, "  ".join(
        ("%.3g" % v) if isinstance(v, (float, np.floating)) else str(v) for v in values)))


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _rigid(rng, scale=1.0):
    """A random rigid transform (4 x 4): a rotation from a random quaternion, a shift of about ``scale``."""
    a, b, c, d = _unit(rng.normal(size=4))
    m = np.eye(4)
    m[:3, :3] = [[a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
                 [2 * (b * c + a * d), a * a - b * b + c * c - d * d, 2 * (c * d - a * b)],
                 [2 * (b * d - a * c), 2 * (c * d + a * b), a * a - b * b - c * c + d * d]]
    m[:3, 3] = rng.normal(size=3) * scale
    return m


def _angle_deg(a, b):
    c = np.einsum("...k,...k->...", _unit(a), _unit(b))
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


# =====================================================================================================================
# HOSES
# =====================================================================================================================

def _circumradius(points, k=1):
    """The radius of the circle through points i - k, i, i + k of one polyline, for every i (inf: in a line)."""
    a = points[k:-k] - points[:-2 * k]
    b = points[2 * k:] - points[k:-k]
    c = points[2 * k:] - points[:-2 * k]
    area2 = np.linalg.norm(np.cross(a, b), axis=-1)
    with np.errstate(divide="ignore"):
        return np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1) * np.linalg.norm(c, axis=-1) / (2 * area2)


def _hose_facts(h, p0, t0, p1, t1, length, n=33):
    """The contract's numbers for the hoses that reach: ends, segment lengths, end directions."""
    ok = ~h.short
    pts = h.points[ok]
    seg = np.diff(pts, axis=1)
    ln = np.linalg.norm(seg, axis=2)
    want = (np.broadcast_to(length, h.short.shape)[ok] / (n - 1))[:, None]
    t0, t1 = np.broadcast_to(t0, h.points[:, 0].shape)[ok], np.broadcast_to(t1, h.points[:, 0].shape)[ok]
    return dict(
        ends=max(float(np.abs(h.points[:, 0] - p0).max()), float(np.abs(h.points[:, -1] - p1).max())),
        seg=float(np.abs(ln / want - 1.0).max()) if len(pts) else 0.0,
        dir0=float(_angle_deg(seg[:, 0], t0).max()) if len(pts) else 0.0,
        dir1=float(_angle_deg(seg[:, -1], t1).max()) if len(pts) else 0.0,
        length=float(np.abs(ln.sum(axis=1) / (want[:, 0] * (n - 1)) - 1.0).max()) if len(pts) else 0.0)


def _assert_hose(h, p0, t0, p1, t1, length, n=33, label=""):
    facts = _hose_facts(h, p0, t0, p1, t1, length, n)
    assert np.isfinite(h.points).all(), label
    assert facts["ends"] < 1e-9, (label, facts)
    assert facts["seg"] < 1e-9, (label, facts)
    assert facts["length"] < 1e-9, (label, facts)
    assert facts["dir0"] < 1e-4 and facts["dir1"] < 1e-4, (label, facts)       # degrees (arccos near 1: ~1e-6)
    return facts


def _bank(seed, count, scale, offset, slack, stiff, spread=0.8):
    """Random hoses: length about ``scale``, ends ``length / slack`` apart, fittings up to ~``spread`` rad off."""
    rng = np.random.default_rng(seed)
    p0 = np.asarray(offset, dtype=float) + rng.normal(size=(count, 3)) * scale
    chord = _unit(rng.normal(size=(count, 3)))
    length = scale * rng.uniform(0.5, 2.0, count)
    p1 = p0 + chord * (length / rng.uniform(*slack, count))[:, None]
    t0 = _unit(chord + spread * rng.normal(size=(count, 3)))
    t1 = _unit(chord + spread * rng.normal(size=(count, 3)))
    return p0, t0, p1, t1, length, length * rng.uniform(*stiff, count)


BANKS = {
    "typical": (150, 1.0, 0.0, (1.02, 2.5), (0.02, 1.0)),
    "extreme slack (3-20 x the distance)": (80, 1.0, 0.0, (3.0, 20.0), (0.02, 1.0)),
    "near taut (1e-6 … 1e-3 slack)": (80, 1.0, 0.0, (1.000001, 1.001), (0.02, 1.0), 0.02),
    "long and thin (bending length 1e-3 L)": (80, 1.0, 0.0, (1.05, 2.0), (0.0005, 0.004)),
    "short and thick (bending length 5-50 L)": (80, 1.0, 0.0, (1.05, 2.0), (5.0, 50.0)),
    "50 m from the origin": (80, 1.0, (50.0, -30.0, 20.0), (1.05, 2.0), (0.05, 1.0)),
    "tiny (20 mm)": (80, 0.02, 0.0, (1.05, 2.0), (0.05, 1.0)),
    "large (20 m)": (80, 20.0, 0.0, (1.05, 2.0), (0.05, 1.0)),
    "in mm, 5 km from the origin": (80, 1000.0, (5e6, 0.0, 0.0), (1.05, 2.0), (0.05, 1.0)),
}


@pytest.mark.parametrize("name", list(BANKS))
def test_hose_ends_directions_and_segments_are_exact(name):
    p0, t0, p1, t1, length, stiff = _bank(7, *BANKS[name])
    h = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert h.points.shape == (len(p0), 33, 3)
    assert np.array_equal(h.points[:, 0], p0) and np.array_equal(h.points[:, -1], p1)       # "exactly"
    facts = _assert_hose(h, p0, t0, p1, t1, length, label=name)
    ok = ~h.short
    assert ok.sum() >= 0.9 * len(ok)
    assert (h.need[ok] <= length[ok] * (1 + 1e-9)).all() and (h.need[~ok] > length[~ok]).all()
    assert (h.min_radius > 0).all() and not h.tight.any()
    # what the module says its tightest bend is, is what the points show
    mine = np.array([_circumradius(p).min() for p in h.points[ok]])
    assert np.allclose(mine, h.min_radius[ok], rtol=1e-6)
    _say("hose %s: ends / segment / direction (deg)" % name, facts["ends"], facts["seg"],
         max(facts["dir0"], facts["dir1"]), "short %d of %d" % ((~ok).sum(), len(ok)))


def test_hose_straight_between_fittings_in_line():
    h = flex.solve_hose((0.2, 0.1, 0.3), (1, 0, 0), (1.2, 0.1, 0.3), (1, 0, 0), 1.0, 0.3)
    pts = h.points[0]
    assert not h.short[0] and h.need[0] == pytest.approx(1.0, abs=1e-12)
    assert np.abs(pts[:, 1] - 0.1).max() < 1e-12 and np.abs(pts[:, 2] - 0.3).max() < 1e-12
    assert np.allclose(np.diff(pts[:, 0]), 1.0 / 32, atol=1e-12)
    assert h.min_radius[0] > 1e6 and not h.tight[0]
    # any number of points, and a limit on the radius changes nothing on a straight hose
    for n in (5, 6, 9, 17, 64):
        pts = flex.solve_hose((0, 0, 0), (0, 1, 0), (0, 2, 0), (0, 1, 0), 2.0, 0.1, min_radius=0.5, n=n).points[0]
        assert pts.shape == (n, 3) and np.abs(pts[:, [0, 2]]).max() < 1e-12
        assert np.allclose(pts[:, 1], np.linspace(0, 2, n), atol=1e-12)


def _catenary(dist, length):
    """Parameter a of the catenary of this length between two points ``dist`` apart at one height, its sag and
    the angle of its ends below the horizontal."""
    lo, hi = 1e-4, 1e4
    for _ in range(200):
        a = math.sqrt(lo * hi)
        lo, hi = (a, hi) if 2 * a * math.sinh(dist / (2 * a)) > length else (lo, a)
    return a, a * (math.cosh(dist / (2 * a)) - 1.0), math.atan(math.sinh(dist / (2 * a)))


@pytest.mark.parametrize("dist,length", [(1.0, 1.02), (1.0, 1.2), (1.0, 2.0), (2.0, 5.0)])
def test_hose_soft_and_heavy_is_a_catenary(dist, length):
    a, sag, slope = _catenary(dist, length)
    t0, t1 = (math.cos(slope), 0, -math.sin(slope)), (math.cos(slope), 0, math.sin(slope))
    n = 33
    s = np.linspace(0, length, n) - length / 2
    want = np.stack([a * np.arcsinh(s / a) + dist / 2, 0 * s, np.sqrt(a * a + s * s) - a - sag], axis=1)
    worst = 0.0
    for stiff in (0.0, 0.001 * length, 0.01 * length):
        pts = flex.solve_hose((0, 0, 0), t0, (dist, 0, 0), t1, length, stiff, n=n).points[0]
        assert abs(-pts[:, 2].min() - sag) < 1e-3 * length                      # the lowest point
        assert np.abs(pts - want).max() < 1e-3 * length                         # every point
        assert np.abs(pts[:, 1]).max() < 1e-9
        # the free segments next to the ends point along the catenary there (the end segments are given)
        mid = np.array([-length / 2 + 2.5 * length / (n - 1), length / 2 - 2.5 * length / (n - 1)])
        ang = np.degrees(np.arctan(mid / a))
        got = np.degrees(np.arctan2(*np.diff(pts, axis=0)[[2, -3]][:, [2, 0]].T))
        assert np.abs(got - ang).max() < 0.5
        worst = max(worst, float(np.abs(pts - want).max() / length))
    _say("catenary d=%g L=%g: sag %.4f, worst point error / L" % (dist, length, sag), worst)


def test_hose_rope_between_level_fittings_sags_like_a_catenary():
    """Fittings that do not point along the catenary: a rope kinks at them and still hangs (nearly) as deep."""
    for dist, length in ((1.0, 1.2), (1.0, 2.0)):
        _a, sag, _slope = _catenary(dist, length)
        h = flex.solve_hose((0, 0, 0), (1, 0, 0), (dist, 0, 0), (1, 0, 0), length, 0.0)
        got = -h.points[0][:, 2].min()
        assert 0.93 * sag < got < 1.01 * sag
        _say("rope, level fittings d=%g L=%g: sag / catenary's" % (dist, length), got / sag)


@pytest.mark.parametrize("n,tol", [(17, 0.03), (33, 0.008), (65, 0.002)])
def test_hose_without_weight_between_fittings_pointing_down_is_a_semicircle(n, tol):
    """Two fittings ``d`` apart pointing down, a hose pi d / 2 long, no weight: half a circle (a curve of constant
    curvature needs no force, only the two fittings' moments), whatever the stiffness."""
    d = 0.4
    length = math.pi * d / 2
    first = None
    for stiff in (0.05, 0.3, 5.0):
        h = flex.solve_hose((0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), length, stiff, sag=0.0, n=n)
        pts = h.points[0]
        r = np.hypot(pts[:, 0] - d / 2, pts[:, 2])
        assert np.abs(r / (d / 2) - 1).max() < tol
        assert abs(-pts[:, 2].min() / (d / 2) - 1) < tol
        assert np.abs(pts[:, 1]).max() < 1e-12
        first = pts if first is None else first
        assert np.abs(pts - first).max() < 1e-9                                 # sag 0: stiffness has no say
    _say("semicircle n=%d: points off the circle / R" % n, float(np.abs(r / (d / 2) - 1).max()))


def _energy(points, length, stiff, sag):
    """The module's energy as its text gives it: (l^3 / 2) * sum |d_i+1 - d_i|^2 / ds + sag * h * sum of heights;
    ds = h between free segments, 1.5 h at the two joints next to the end segments. (..., n, 3) -> (...)."""
    n = points.shape[-2]
    h = length / (n - 1)
    d = np.diff(points, axis=-2) / h
    dd = np.diff(d, axis=-2)
    ds = np.full(n - 2, h)
    ds[0] = ds[-1] = 1.5 * h
    return 0.5 * stiff ** 3 * ((dd ** 2).sum(-1) / ds).sum(-1) + sag * h * points[..., 1:-1, 2].sum(-1)


def _brute_force_loop(n, length, stiff, sag, dist):
    """The planar hose between fittings pointing down (0, 0) and up (dist, 0) by brute force: the angles of the
    free segments are the unknowns, two of them (the middle pair) follow from closing the chain (a two-bar
    linkage, the elbow on the side with less energy), the rest are searched with Nelder-Mead from a start that
    knows nothing of the answer (angles evenly from -90 to +90 degrees)."""
    h = length / (n - 1)
    q = n - 3
    mid = q // 2 - 1
    rest = np.delete(np.arange(q), [mid, mid + 1])
    a0, a1 = -0.5 * math.pi, 0.5 * math.pi

    def shapes(x):
        vec = np.array([dist / h - np.cos(x).sum(), -(math.sin(a0) + math.sin(a1)) - np.sin(x).sum()])
        r = float(np.hypot(*vec))
        if r > 2.0:
            return []
        base, off = math.atan2(vec[1], vec[0]), math.acos(r / 2)
        out = []
        for sign in (1, -1):
            th = np.empty(n - 1)
            th[0], th[-1] = a0, a1
            free = np.empty(q)
            free[rest] = x
            free[mid], free[mid + 1] = base + sign * off, base - sign * off
            th[1:-1] = free
            pts = np.zeros((n, 3))
            pts[1:, 0], pts[1:, 2] = np.cumsum(h * np.cos(th)), np.cumsum(h * np.sin(th))
            out.append(pts)
        return out

    def cost(x):
        return min((float(_energy(p, length, stiff, sag)) for p in shapes(x)), default=1e30)

    x0 = np.linspace(a0, a1, n - 1)[1:-1][rest]
    for restart in range(8):
        m = len(x0)
        sim = np.vstack([x0] + [x0 + 0.2 * 0.5 ** restart * np.eye(m)[i] for i in range(m)])
        f = np.array([cost(s) for s in sim])
        for it in range(3000):
            order = np.argsort(f)
            sim, f = sim[order], f[order]
            if it > 40 and f[-1] - f[0] < 1e-15 * (abs(f[0]) + 1e-300):
                break
            c = sim[:-1].mean(axis=0)
            xr = 2 * c - sim[-1]
            fr = cost(xr)
            if fr < f[0]:
                xe = 3 * c - 2 * sim[-1]
                fe = cost(xe)
                sim[-1], f[-1] = (xe, fe) if fe < fr else (xr, fr)
            elif fr < f[-2]:
                sim[-1], f[-1] = xr, fr
            else:
                xc = 0.5 * (c + sim[-1])
                fx = cost(xc)
                if fx < f[-1]:
                    sim[-1], f[-1] = xc, fx
                else:
                    sim[1:] = sim[0] + 0.5 * (sim[1:] - sim[0])
                    f[1:] = [cost(s) for s in sim[1:]]
        x0 = sim[0]
    return min(shapes(x0), key=lambda p: float(_energy(p, length, stiff, sag)))


@pytest.mark.parametrize("dist,length,stiff,sag", [(0.3, 1.0, 0.2, 1.0), (0.3, 1.0, 0.5, 1.0), (0.5, 0.9, 0.3, 0.3)])
def test_hose_u_loop_is_the_energy_minimum_found_by_brute_force(dist, length, stiff, sag):
    n = 9                                               # few segments: the brute force has 4 unknowns
    h = flex.solve_hose((0, 0, 0), (0, 0, -1), (dist, 0, 0), (0, 0, 1), length, stiff, sag=sag, n=n)
    pts = h.points[0]
    mine = _brute_force_loop(n, length, stiff, sag, dist)
    e_solver, e_mine = float(_energy(pts, length, stiff, sag)), float(_energy(mine, length, stiff, sag))
    assert e_solver <= e_mine + 1e-9 * abs(e_mine)      # the solver's shape is at least as good …
    assert np.abs(pts - mine).max() < 1e-5 * length     # … and it is the same shape
    assert abs(pts[:, 2].min() - mine[:, 2].min()) < 1e-5 * length
    _say("U-loop d=%g L=%g l=%g sag=%g: depth %.5f, off the brute force / L" % (dist, length, stiff, sag,
                                                                               -pts[:, 2].min()),
         float(np.abs(pts - mine).max() / length))


def _cantilever(length, ell, steps=1500):
    """A heavy elastica clamped level at s = 0 and free at s = L: l^3 th'' = (L - s) cos th, th(0) = 0,
    th'(L) = 0 (th: the tangent's angle above the horizontal). Shooting on th'(0), Runge-Kutta 4.
    Returns s, x(s), z(s), th(s)."""
    h = length / steps

    def run(k0):
        y = np.array([0.0, k0, 0.0, 0.0])
        out = np.empty((steps + 1, 4))
        out[0] = y

        def f(s, y):
            return np.array([y[1], (length - s) * math.cos(y[0]) / ell ** 3, math.cos(y[0]), math.sin(y[0])])

        for i in range(steps):
            s = i * h
            k1 = f(s, y)
            k2 = f(s + h / 2, y + h / 2 * k1)
            k3 = f(s + h / 2, y + h / 2 * k2)
            k4 = f(s + h, y + h * k3)
            y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            out[i + 1] = y
        return out

    a = -length ** 2 / (2 * ell ** 3)                    # beam theory: the curvature at the clamp
    b = 0.9 * a
    fa, fb = run(a)[-1, 1], run(b)[-1, 1]
    for _ in range(30):
        a, fa, b = b, fb, b - fb * (b - a) / (fb - fa)
        fb = run(b)[-1, 1]
        if abs(fb) < 1e-13:
            break
    y = run(b)
    return np.linspace(0, length, steps + 1), y[:, 2], y[:, 3], y[:, 0]


@pytest.mark.parametrize("ell", [2.0, 0.8])
def test_hose_held_level_at_one_end_droops_like_a_heavy_cantilever(ell):
    """End 0 clamped level; end 1 put exactly where the free end of a heavy cantilever of this bending length
    would be, pointing the way it would point: the hose between is then that cantilever (it is the minimum of
    the same energy over more curves). ell = 2 L: small sag, beam theory holds (tip w L^4 / 8 EI); ell = 0.8 L:
    a quarter of the length down, far beyond beam theory."""
    length = 1.0
    s, x, z, th = _cantilever(length, ell * length)
    if ell >= 2.0:                                       # beam theory, to check the equation itself
        assert -z[-1] == pytest.approx(length ** 4 / (8 * (ell * length) ** 3), rel=0.01)
        assert -th[-1] == pytest.approx(length ** 3 / (6 * (ell * length) ** 3), rel=0.01)
    tip, tdir = np.array([x[-1], 0.0, z[-1]]), np.array([math.cos(th[-1]), 0.0, math.sin(th[-1])])
    for n, tol in ((33, 1.5e-3), (65, 4e-4)):
        h = flex.solve_hose((0, 0, 0), (1, 0, 0), tip, tdir, length, ell * length, n=n)
        at = np.linspace(0, length, n)
        want = np.stack([np.interp(at, s, x), 0 * at, np.interp(at, s, z)], axis=1)
        err = float(np.abs(h.points[0] - want).max())
        assert err < tol * length
        _say("cantilever l=%g L n=%d: tip sag %.4f L, hose off the elastica / L" % (ell, n, -z[-1]), err)
    # the part of the sag that only the weight and the stiffness explain: the middle's distance from the cubic
    # through the two ends and their slopes; beam theory: L^4 / (384 l^3)
    if ell >= 2.0:
        mid = h.points[0][(n - 1) // 2, 2] - (0.5 * tip[2] - length * math.tan(th[-1]) / 8)
        assert -mid == pytest.approx(length ** 4 / (384 * (ell * length) ** 3), rel=0.06)


def test_hose_turned_moved_mirrored_and_swapped():
    p0, t0, p1, t1, length, stiff = _bank(11, 60, 1.0, 0.0, (1.05, 1.8), (0.05, 1.0), 0.5)
    base = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert not base.short.any()
    rng = np.random.default_rng(5)
    m = _rigid(rng, 3.0)
    r, shift = m[:3, :3], m[:3, 3]
    turned = flex.solve_hoses(p0 @ r.T + shift, t0 @ r.T, p1 @ r.T + shift, t1 @ r.T, length, stiff,
                              gravity=r @ np.array([0.0, 0.0, -1.0]))
    e_turn = np.abs(turned.points - (base.points @ r.T + shift)).max(axis=(1, 2)) / length
    assert e_turn.max() < 1e-7
    mirror = np.diag([1.0, -1.0, 1.0])
    mirrored = flex.solve_hoses(p0 @ mirror, t0 @ mirror, p1 @ mirror, t1 @ mirror, length, stiff)
    e_mirror = np.abs(mirrored.points - base.points @ mirror).max(axis=(1, 2)) / length
    assert e_mirror.max() < 1e-9
    # the same hose named from its other end: the same curve, backwards
    swapped = flex.solve_hoses(p1, -t1, p0, -t0, length, stiff)
    e_swap = np.abs(swapped.points[:, ::-1] - base.points).max(axis=(1, 2)) / length
    assert e_swap.max() < 1e-9
    assert np.allclose(swapped.min_radius, base.min_radius, rtol=1e-9)
    moved = flex.solve_hoses(p0 + [50.0, -20.0, 7.0], t0, p1 + [50.0, -20.0, 7.0], t1, length, stiff)
    e_move = np.abs(moved.points - [50.0, -20.0, 7.0] - base.points).max(axis=(1, 2)) / length
    assert e_move.max() < 1e-9
    # the directions' lengths do not matter
    scaled = flex.solve_hoses(p0, 7.5 * t0, p1, 0.01 * t1, length, stiff)
    assert np.abs(scaled.points - base.points).max() < 1e-9
    _say("hose turned / mirrored / ends swapped / moved 50 m: off, per length", float(e_turn.max()),
         float(e_mirror.max()), float(e_swap.max()), float(e_move.max()))


def test_hose_in_mm_is_the_hose_in_m():
    p0, t0, p1, t1, length, stiff = _bank(12, 60, 1.0, 0.0, (1.05, 1.8), (0.05, 1.0), 0.5)
    rmin = 0.05 * length
    base = flex.solve_hoses(p0, t0, p1, t1, length, stiff, min_radius=rmin)
    mm = flex.solve_hoses(p0 * 1000, t0, p1 * 1000, t1, length * 1000, stiff * 1000, min_radius=rmin * 1000)
    err = np.abs(mm.points / 1000 - base.points).max(axis=(1, 2)) / length
    assert err.max() < 1e-9
    assert np.allclose(mm.min_radius, base.min_radius * 1000, rtol=1e-9)
    assert np.allclose(mm.need, base.need * 1000, rtol=1e-12)
    assert np.array_equal(mm.tight, base.tight) and np.array_equal(mm.short, base.short)
    _say("hose in mm against m: off, per length", float(err.max()))


def test_hose_batch_is_each_alone_in_any_order():
    p0, t0, p1, t1, length, stiff = _bank(13, 300, 1.0, 0.0, (1.02, 2.5), (0.02, 1.0))      # more than one chunk
    sag = np.where(np.arange(300) % 3 == 0, 0.0, 1.0)
    rmin = np.where(np.arange(300) % 4 == 0, 0.08 * length, 0.0)
    whole = flex.solve_hoses(p0, t0, p1, t1, length, stiff, sag=sag, min_radius=rmin)
    worst = 0.0
    for i in list(range(0, 300, 9)) + [254, 255, 256, 257, 299]:
        one = flex.solve_hose(p0[i], t0[i], p1[i], t1[i], length[i], stiff[i], sag=sag[i], min_radius=rmin[i])
        worst = max(worst, float(np.abs(one.points[0] - whole.points[i]).max() / length[i]))
        assert one.short[0] == whole.short[i] and one.tight[0] == whole.tight[i]
        assert one.need[0] == pytest.approx(whole.need[i], rel=1e-12)
    assert worst < 1e-9
    perm = np.random.default_rng(3).permutation(300)
    mixed = flex.solve_hoses(p0[perm], t0[perm], p1[perm], t1[perm], length[perm], stiff[perm], sag=sag[perm],
                             min_radius=rmin[perm])
    shuffled = float((np.abs(mixed.points - whole.points[perm]).max(axis=(1, 2)) / length[perm]).max())
    assert shuffled < 1e-9
    _say("hose alone against in a batch of 300 / the batch shuffled: off, per length", worst, shuffled)


def test_hose_is_a_pure_function():
    p0, t0, p1, t1, length, stiff = _bank(14, 40, 1.0, 0.0, (1.02, 2.5), (0.02, 1.0))
    first = flex.solve_hoses(p0, t0, p1, t1, length, stiff, min_radius=0.05)
    other = _bank(15, 70, 3.0, 5.0, (1.5, 4.0), (0.01, 0.2))
    flex.solve_hoses(*other, sag=0.3, n=17)
    flex.solve_hose((0, 0, 0), (0, 0, 1), (0.1, 0.2, 0.3), (1, 0, 0), 2.0, 0.01, n=65)
    if HAS_MOTION:
        flex.solve_motion(*_hinge(60), 0.6, 1.28)
    again = flex.solve_hoses(p0, t0, p1, t1, length, stiff, min_radius=0.05)
    for name in ("points", "short", "need", "min_radius", "tight"):
        assert np.array_equal(getattr(first, name), getattr(again, name)), name               # bit for bit
    assert not np.shares_memory(first.points, again.points)
    # the inputs are not written to
    keep = [x.copy() for x in (p0, t0, p1, t1, length, stiff)]
    flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert all(np.array_equal(a, b) for a, b in zip(keep, (p0, t0, p1, t1, length, stiff)))


def test_hose_too_short_is_a_straight_line_with_the_length_it_needs():
    # fittings along the line: the hose needs the distance
    h = flex.solve_hose((1, 2, 3), (1, 0, 0), (3, 2, 3), (1, 0, 0), 1.5, 0.3)
    assert h.short[0] and h.need[0] == pytest.approx(2.0, rel=1e-12) and not h.tight[0]
    assert np.allclose(h.points[0], np.linspace((1, 2, 3), (3, 2, 3), 33), atol=1e-12)
    assert h.min_radius[0] == np.inf
    # fittings square to the line (two glands pointing down and up): the first and last segment are lost for
    # the reach: (n - 3) segments span the distance → need = distance * (n - 1) / (n - 3)
    for n in (9, 33):
        need = 0.7 * (n - 1) / (n - 3)
        h = flex.solve_hose((0, 0, 0), (0, 0, -1), (0.7, 0, 0), (0, 0, 1), 0.6, 0.1, n=n)
        assert h.short[0] and h.need[0] == pytest.approx(need, rel=1e-12)
        # … and that is the limit: a hair longer reaches, a hair shorter does not
        longer = flex.solve_hose((0, 0, 0), (0, 0, -1), (0.7, 0, 0), (0, 0, 1), need * (1 + 1e-6), 0.1, n=n)
        shorter = flex.solve_hose((0, 0, 0), (0, 0, -1), (0.7, 0, 0), (0, 0, 1), need * (1 - 1e-6), 0.1, n=n)
        assert not longer.short[0] and shorter.short[0]
        _assert_hose(longer, (0, 0, 0), (0, 0, -1), (0.7, 0, 0), (0, 0, 1), need * (1 + 1e-6), n=n)
    # a short hose in a batch does not disturb its neighbours
    p0, t0, p1, t1, length, stiff = _bank(16, 12, 1.0, 0.0, (1.1, 1.5), (0.1, 0.5))
    base = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    length2 = length.copy()
    length2[[3, 7]] *= 0.5
    mixed = flex.solve_hoses(p0, t0, p1, t1, length2, stiff)
    assert mixed.short[[3, 7]].all() and mixed.short.sum() == 2
    rest = np.delete(np.arange(12), [3, 7])
    assert np.abs(mixed.points[rest] - base.points[rest]).max() < 1e-9
    assert (mixed.need[[3, 7]] > length2[[3, 7]]).all()


DEGENERATE = {
    "both ends at one place": dict(p1=(0, 0, 0)),
    "both ends at one place, fittings opposed": dict(p1=(0, 0, 0), t1=(-1, 0, 0)),
    "no length": dict(length=0.0),
    "negative length": dict(length=-1.0),
    "length not a number": dict(length=np.nan),
    "fittings without a direction": dict(t0=(0, 0, 0), t1=(0, 0, 0)),
    "a direction not a number": dict(t0=(np.nan, 0, 0)),
    "no stiffness": dict(stiff=0.0),
    "negative stiffness": dict(stiff=-1.0),
    "enormous stiffness": dict(stiff=1e9),
    "stiffness not a number": dict(stiff=np.nan),
    "sag not a number": dict(sag=np.nan),
    "negative sag": dict(sag=-3.0),
    "no gravity": dict(gravity=(0, 0, 0)),
    "fittings pointing backwards": dict(t0=(-1, 0, 0), t1=(-1, 0, 0), length=3.0),
    "fittings pointing backwards, hose too short": dict(t0=(-1, 0, 0), t1=(-1, 0, 0), length=1.05),
    "hanging straight down": dict(t0=(0, 0, -1), p1=(0, 0, -1), t1=(0, 0, -1), length=1.3),
    "standing straight up": dict(t0=(0, 0, 1), p1=(0, 0, 1), t1=(0, 0, 1), length=1.3),
    "five points": dict(n=5),
    "120 points": dict(n=120),
    "a nanometre": dict(p1=(1e-9, 0, 0), length=1.5e-9, stiff=0.2e-9),
    "a thousand km": dict(p1=(1e6, 0, 0), length=1.5e6, stiff=0.2e6),
    "a limit no hose can keep": dict(min_radius=100.0),
    "negative limit": dict(min_radius=-1.0),
    "limit not a number": dict(min_radius=np.nan),
    "exactly taut": dict(length=1.0),
    "taut but for rounding": dict(length=1.0 + 1e-15),
}


@pytest.mark.parametrize("name", list(DEGENERATE))
def test_hose_degenerate_inputs_give_numbers(name):
    args = dict(p0=(0, 0, 0), t0=(1, 0, 0), p1=(1, 0, 0), t1=(1, 0, 0), length=1.5, stiff=0.2)
    args.update(DEGENERATE[name])
    with np.errstate(all="raise"):                       # no warnings either
        h = flex.solve_hoses(**args)
    n = args.get("n", 33)
    assert h.points.shape == (1, n, 3)
    assert np.isfinite(h.points).all(), name
    assert np.array_equal(h.points[0, 0], np.array(args["p0"], dtype=float))
    assert np.array_equal(h.points[0, -1], np.array(args["p1"], dtype=float))
    assert not np.isnan(h.need).any() and not np.isnan(h.min_radius).any()
    if not h.short[0] and np.isfinite(args["length"]) and args["length"] > 0:
        seg = np.linalg.norm(np.diff(h.points[0], axis=0), axis=1)
        assert np.allclose(seg, args["length"] / (n - 1), rtol=1e-9)


def test_hose_bad_shapes_are_refused_in_plain_words():
    with pytest.raises(ValueError, match="at least 5 points"):
        flex.solve_hose((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), 1.5, 0.2, n=4)
    with pytest.raises(ValueError, match="3 numbers"):
        flex.solve_hoses((0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), 1.5, 0.2)
    with pytest.raises(ValueError, match="one batch"):
        flex.solve_hoses(np.zeros((2, 3)), np.ones((3, 3)), np.ones((2, 3)), np.ones((2, 3)), 1.5, 0.2)


@pytest.mark.xfail(strict=False, reason="FOUND: an end that is not a number gives points that are not numbers "
                   "(points[0] all NaN, need NaN; short is True). The Blender side writes points into a mesh: "
                   "a NaN there is worse than a straight line at the origin. Infinite length or end: "
                   "RuntimeWarning 'invalid value' from NumPy (short True, finite points for the infinite length).")
def test_hose_end_not_a_number_gives_no_nan():
    h = flex.solve_hoses((np.nan, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), 1.5, 0.2)
    assert h.short[0]
    assert np.isfinite(h.points).all() and not np.isnan(h.need).any()
    with np.errstate(all="raise"):
        g = flex.solve_hoses((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), np.inf, 0.2)
    assert g.short[0]


@pytest.mark.xfail(strict=False, reason="FOUND: a batch of no hoses raises ValueError('the inputs do not fit one "
                   "batch of 1 hoses') because the numbers (length, stiff) count as a batch of 1; an empty (0, n, 3) "
                   "result would let a caller with no hoses at a frame go on without a special case.")
def test_hose_empty_batch_is_an_empty_result():
    none = np.zeros((0, 3))
    h = flex.solve_hoses(none, none, none, none, 1.5, 0.2)
    assert h.points.shape == (0, 33, 3) and h.short.shape == (0,)


@pytest.mark.xfail(strict=False, reason="BUG: one hose with an absurd but finite number takes the whole batch down "
                   "with an exception: numpy.linalg.LinAlgError('Eigenvalues did not converge') for stiff >= ~1e60, "
                   "sag = 1e300 or inf, min_radius = 1e200 or inf (stiff = inf and NaN are caught and give a straight "
                   "line; stiff 1e20, sag 1e30, min_radius 1e30 are solved). The eigenvalue call of the coarse levels "
                   "(_settle) is not guarded as the linear solves are.")
@pytest.mark.parametrize("what,value", [("stiff", 1e60), ("stiff", 1e110), ("sag", 1e300), ("sag", np.inf),
                                        ("min_radius", 1e200), ("min_radius", np.inf)])
def test_hose_absurd_number_in_one_row_does_not_raise(what, value):
    args = dict(p0=np.zeros((2, 3)), t0=(1, 0, 0), p1=np.array([(1.0, 0, 0), (1.0, 0, 0)]), t1=(1, 0, 0),
                length=1.5, stiff=np.array([0.2, 0.2]), sag=np.array([1.0, 1.0]), min_radius=np.array([0.0, 0.0]))
    base = flex.solve_hoses(**args)
    args[what] = np.array([value, args[what][1]])
    with np.errstate(all="ignore"):
        h = flex.solve_hoses(**args)
    assert np.isfinite(h.points).all()
    assert np.abs(h.points[1] - base.points[1]).max() < 1e-9


def test_hose_not_a_number_in_one_row_leaves_the_others_alone():
    p0, t0, p1, t1, length, stiff = _bank(17, 10, 1.0, 0.0, (1.1, 1.5), (0.1, 0.5))
    base = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    bad = p1.copy()
    bad[4, 1] = np.nan
    with np.errstate(all="ignore"):
        mixed = flex.solve_hoses(p0, t0, bad, t1, length, stiff)
    rest = np.delete(np.arange(10), 4)
    assert mixed.short[4] and np.abs(mixed.points[rest] - base.points[rest]).max() < 1e-9


# ---------------------------------------------------------------------------------------------------------------------
# the minimum bend radius
# ---------------------------------------------------------------------------------------------------------------------

def test_hose_tight_is_honest_about_the_points():
    """Whatever the solver does about a limit: ``min_radius`` is the tightest circle through three neighbouring
    points and ``tight`` says truthfully whether that is under 99 % of the limit."""
    p0, t0, p1, t1, length, stiff = _bank(18, 120, 1.0, 0.0, (1.05, 3.0), (0.02, 0.5))
    limit = length * np.random.default_rng(1).uniform(0.02, 0.3, 120)
    h = flex.solve_hoses(p0, t0, p1, t1, length, stiff, min_radius=limit)
    free = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    ok = ~h.short
    _assert_hose(h, p0, t0, p1, t1, length)
    mine = np.array([_circumradius(p).min() for p in h.points])
    assert np.allclose(mine[ok], h.min_radius[ok], rtol=1e-6)
    assert np.allclose(flex.bend_radius(h.points)[ok], mine[ok], rtol=1e-6)
    assert np.array_equal(h.tight[ok], (mine < 0.99 * limit)[ok])
    # a limit never makes the tightest bend (clearly) tighter, and a hose that kept it anyway is not changed
    assert (h.min_radius[ok] >= free.min_radius[ok] * 0.98).all()
    kept = ok & (free.min_radius > 1.2 * limit)
    assert kept.sum() > 10
    assert np.abs(h.points[kept] - free.points[kept]).max() < 1e-6
    was_tight = ok & (free.min_radius < 0.99 * limit)
    cured = was_tight & ~h.tight
    _say("limit on the bend radius: hoses under it without the limit / brought to it / still tight",
         int(was_tight.sum()), int(cured.sum()), int((was_tight & h.tight).sum()))
    assert cured.sum() >= 0.3 * was_tight.sum()


def test_hose_keeps_its_minimum_radius_where_there_is_room():
    """A soft cable hanging in a narrow loop between two glands pointing down: without a limit it folds tightly at
    the bottom; with a limit that fits between the glands (limit < half their distance) it must not."""
    d, length, stiff = 0.30, 1.2, 0.03
    free = flex.solve_hose((0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), length, stiff)
    assert free.min_radius[0] < 0.08
    for limit in (0.09, 0.11, 0.13):
        h = flex.solve_hose((0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), length, stiff, min_radius=limit)
        _assert_hose(h, (0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), length)
        mine = float(_circumradius(h.points[0]).min())
        assert mine >= 0.99 * limit and not h.tight[0], (limit, mine)
        _say("soft loop, limit %.2f (free: %.3f): tightest bend measured on the points" % (limit, free.min_radius[0]),
             mine)
    # no room: the glands are closer together than twice the limit and point the same way down → it says so
    h = flex.solve_hose((0, 0, 0), (0, 0, -1), (0.1, 0, 0), (0, 0, 1), 0.5, stiff, min_radius=0.2)
    assert h.tight[0] and float(_circumradius(h.points[0]).min()) < 0.99 * 0.2


@pytest.mark.xfail(strict=False, reason="FOUND: the tightest bend is reported a third too tight when it lies at a "
                   "fitting. A hose that IS half a circle of radius 200 mm (no weight, fittings 400 mm apart) "
                   "reports min_radius 131 mm (0.656 R; n = 65: 0.664 R – it does not go away with more points): the "
                   "joint next to a fixed end segment turns 1.5 x as far as the others (it stands for 1.5 segments "
                   "of hose in the energy), but the radius there is still taken as h / |turn|. The joints between "
                   "free segments give 197.5 mm. A warning 'bends tighter than …' would name 131 mm.")
def test_hose_reported_radius_of_a_semicircle_is_its_radius():
    d = 0.4
    h = flex.solve_hose((0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), math.pi * d / 2, 0.3, sag=0.0)
    inner = float(_circumradius(h.points[0])[1:-1].min())
    assert inner == pytest.approx(d / 2, rel=0.02)       # holds: between the free segments it is the circle
    assert h.min_radius[0] == pytest.approx(d / 2, rel=0.05)


@pytest.mark.xfail(strict=False, reason="FOUND: false 'tight'. The same half circle of radius 200 mm with a limit "
                   "of 190 mm (which the half circle keeps everywhere) comes back tight=True, min_radius 179 mm, and "
                   "the shape is pulled out of round (depth 193 instead of 199 mm): the limit is enforced on the "
                   "end joints with h, the bending energy counts them with 1.5 h. Limits up to 160 mm (0.8 R) are "
                   "kept without the warning.")
def test_hose_semicircle_with_a_limit_it_keeps_is_not_tight():
    d = 0.4
    h = flex.solve_hose((0, 0, 0), (0, 0, -1), (d, 0, 0), (0, 0, 1), math.pi * d / 2, 0.3, sag=0.0, min_radius=0.19)
    assert not h.tight[0]


# ---------------------------------------------------------------------------------------------------------------------
# the small helpers
# ---------------------------------------------------------------------------------------------------------------------

def test_polyline_length_resample_bend_radius_stiff_length():
    square = np.array([(0, 0, 0), (3, 0, 0), (3, 4, 0), (0, 4, 0)], dtype=float)
    assert flex.polyline_length(square) == pytest.approx(10.0)
    assert isinstance(flex.polyline_length(square), float)
    both = flex.polyline_length(np.stack([square, 2 * square]))
    assert both.shape == (2,) and np.allclose(both, [10.0, 20.0])
    assert flex.polyline_length(square[:1]) == 0.0
    assert flex.polyline_length(np.array([(0, 0, 0), (1, 2, 2)], dtype=float)) == pytest.approx(3.0)

    out = flex.resample(square, 11)                      # every 1.0 along 10.0
    assert out.shape == (11, 3)
    assert np.allclose(out[[0, 3, 5, 7, 10]], [(0, 0, 0), (3, 0, 0), (3, 2, 0), (3, 4, 0), (0, 4, 0)])
    assert np.allclose(out[1], (1, 0, 0)) and np.allclose(out[8], (2, 4, 0))
    assert np.array_equal(out[0], square[0]) and np.array_equal(out[-1], square[-1])
    assert np.allclose(flex.resample(square, 2), square[[0, 3]])
    assert flex.resample(square, 0).shape == (0, 3)
    assert np.allclose(flex.resample(square[:1], 4), np.repeat(square[:1], 4, axis=0))
    assert np.allclose(flex.resample(np.repeat(square[:1], 5, axis=0), 3), np.repeat(square[:1], 3, axis=0))
    doubled = np.repeat(square, 2, axis=0)               # points given twice change nothing
    assert np.allclose(flex.resample(doubled, 11), out)
    line = flex.resample(np.array([(0, 0, 0), (0, 0, 9)], dtype=float), 4)
    assert np.allclose(line[:, 2], [0, 3, 6, 9])
    with pytest.raises(ValueError):
        flex.resample(np.zeros((0, 3)), 3)

    ang = np.linspace(0, 1.0, 12)
    arc = 2.5 * np.stack([np.cos(ang), np.sin(ang), 0 * ang], axis=1)
    assert flex.bend_radius(arc) == pytest.approx(2.5, rel=1e-9)
    assert flex.bend_radius(np.linspace((0, 0, 0), (1, 2, 3), 7)) == np.inf
    assert flex.bend_radius(arc[:2]) == np.inf
    assert flex.bend_radius(np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0)], dtype=float)) == pytest.approx(math.sqrt(0.5))
    assert flex.bend_radius(np.array([(0, 0, 0), (1, 0, 0), (0.5, 0, 0)], dtype=float)) == 0.0     # folded back
    several = flex.bend_radius(np.stack([arc, 2 * arc]))
    assert several.shape == (2,) and np.allclose(several, [2.5, 5.0])
    mixed = np.concatenate([np.linspace((-5, 2.5, 0), (-0.1, 2.5, 0), 6), arc[::-1]])
    assert flex.bend_radius(mixed) <= 2.5 * (1 + 1e-9)

    assert flex.stiff_length(0.02, 0.0) == pytest.approx(0.08)          # 4 diameters
    assert flex.stiff_length(0.02, 1.0) == pytest.approx(1.28)          # 64 diameters
    assert flex.stiff_length(0.02, 0.5) == pytest.approx(0.32)          # 16
    assert isinstance(flex.stiff_length(0.02, 0.5), float)
    assert np.allclose(flex.stiff_length(np.array([0.01, 0.02]), 0.5), [0.16, 0.32])
    s = np.linspace(0, 1, 9)
    assert (np.diff(flex.stiff_length(0.02, s)) > 0).all()


def test_hose_speed():
    """The contract: <= 0.25 ms per hose in batches of 20 or more, <= 5 ms for one, 5,000 in <= 3 s. Measured and
    printed; asserted with a wide margin (the machine is shared)."""
    p0, t0, p1, t1, length, stiff = _bank(19, 1000, 1.0, 0.0, (1.05, 2.5), (0.02, 1.0))
    flex.solve_hoses(p0[:20], t0[:20], p1[:20], t1[:20], length[:20], stiff[:20])          # warm up
    best = {}
    for name, count, rounds in (("one", 1, 5), ("batch of 20", 20, 5), ("batch of 1000", 1000, 1)):
        times = []
        for k in range(rounds):
            sl = slice(k * count, (k + 1) * count)
            clock = time.perf_counter()
            flex.solve_hoses(p0[sl], t0[sl], p1[sl], t1[sl], length[sl], stiff[sl])
            times.append(time.perf_counter() - clock)
        best[name] = min(times) / count * 1e3
    _say("hose speed, ms per hose: one / in a batch of 20 / in a batch of 1000 (contract: 5 / 0.25 / 0.6)",
         best["one"], best["batch of 20"], best["batch of 1000"])
    assert best["one"] < 50.0 and best["batch of 20"] < 5.0 and best["batch of 1000"] < 3.0


@pytest.mark.xfail(strict=False, reason="MEASURED (web session, 4 shared cores): one hose 4-6 ms (contract 5), a "
                   "batch of 20 unrelated hoses 0.6-0.9 ms per hose (contract 0.25), a batch of 1000 0.5-0.6 ms per "
                   "hose (5,000 in 3 s = 0.6). The batch-of-20 budget is missed by a factor 3; 20 hoses at one frame "
                   "cost about 15 ms, not 5.")
def test_hose_speed_meets_the_contract_for_batches_of_20():
    p0, t0, p1, t1, length, stiff = _bank(19, 100, 1.0, 0.0, (1.05, 2.5), (0.02, 1.0))
    flex.solve_hoses(p0[:20], t0[:20], p1[:20], t1[:20], length[:20], stiff[:20])
    times = []
    for k in range(5):
        sl = slice(k * 20, (k + 1) * 20)
        clock = time.perf_counter()
        flex.solve_hoses(p0[sl], t0[sl], p1[sl], t1[sl], length[sl], stiff[sl])
        times.append(time.perf_counter() - clock)
    assert min(times) / 20 * 1e3 <= 0.25


# =====================================================================================================================
# HOSES ALONG A MOTION
# =====================================================================================================================

FRAMES = 300


def _rot(axis, angle):
    """(F, 3, 3): turns about ``axis`` by ``angle`` (F,) radians."""
    a = _unit(axis)
    angle = np.atleast_1d(np.asarray(angle, dtype=float))
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3)[None] + np.sin(angle)[:, None, None] * k[None] + (1 - np.cos(angle))[:, None, None] * (k @ k)[None]


def _still(v, frames):
    return np.broadcast_to(np.asarray(v, dtype=float), (frames, 3)).copy()


def _hinge(frames=FRAMES, swing=40.0, axis=(0, 1, 0), a_pt=(-0.20, 0.0, 0.05), a_dir=(1, 0, 0),
           b_pt=(0.25, 0.0, 0.05), b_dir=(1, 0, 0)):
    """A hose across a hinge at the origin: end 0 on the fixed part, end 1 on an arm that swings +-``swing``
    degrees (a full cycle; the fittings are in line when the arm is in the middle)."""
    r = _rot(axis, np.radians(swing) * np.sin(np.linspace(0, 2 * np.pi, frames)))
    return _still(a_pt, frames), _still(_unit(a_dir), frames), r @ np.asarray(b_pt, dtype=float), r @ _unit(b_dir)


def _slide(frames=FRAMES, travel=0.3, along=(1, 0, 0), a_dir=(1, 0, 0), b_pt=(0.0, 0.0, 0.25), b_dir=(-1, 0, 0)):
    """End 1 slides ``travel`` along ``along`` and back; end 0 at the origin."""
    s = 0.5 * travel * (1 - np.cos(np.linspace(0, 2 * np.pi, frames)))
    return (_still((0, 0, 0), frames), _still(_unit(a_dir), frames),
            np.asarray(b_pt, dtype=float) + s[:, None] * _unit(along), _still(_unit(b_dir), frames))


def _apart(frames=FRAMES, near=0.25, far=0.85, a_dir=(0, 0, -1), b_dir=(0, 0, 1), dz=0.0, dy=0.0):
    """Two parts move apart and together along X (their distance goes near … far … near)."""
    d = near + (far - near) * 0.5 * (1 - np.cos(np.linspace(0, 2 * np.pi, frames)))
    p0, p1 = np.zeros((frames, 3)), np.zeros((frames, 3))
    p0[:, 0], p1[:, 0], p1[:, 1], p1[:, 2] = -0.5 * d, 0.5 * d, dy, dz
    return p0, _still(_unit(a_dir), frames), p1, _still(_unit(b_dir), frames)


def _swivel(frames=FRAMES, cone=90.0, axis=(1, 0, 0), b_pt=(0.4, 0, 0), b_dir=(-1, 0, 0)):
    """End 0 is an elbow fitting that turns once about its own axis: the hose leaves it ``cone`` degrees off that
    axis, so its direction goes round a cone."""
    a = _unit(axis)
    side = _unit(np.cross(a, (0.3, 0.5, 0.8)))
    base = math.cos(math.radians(cone)) * a + math.sin(math.radians(cone)) * side
    t0 = _rot(a, np.linspace(0, 2 * np.pi, frames)) @ base
    return np.zeros((frames, 3)), t0, _still(b_pt, frames), _still(_unit(b_dir), frames)


def _hinge_and_slide(frames=FRAMES, swing=35.0, travel=0.2):
    """3-D: an arm turns about Z while it is lifted along Z; the fittings point out of every plane."""
    u = np.linspace(0, 2 * np.pi, frames)
    r = _rot((0, 0, 1), np.radians(swing) * np.sin(u))
    lift = 0.5 * travel * (1 - np.cos(2 * u + 0.4))
    p1 = r @ np.array([0.30, 0.05, 0.10]) + np.stack([0 * u, 0 * u, lift], axis=1)
    return _still((-0.10, 0, 0), frames), _still(_unit((0.2, 1.0, 0.3)), frames), p1, r @ _unit((1.0, 0.3, 0.2))


def _steps(points, p0, t0, p1, t1, length):
    """Between neighbouring frames: the largest move of any point of the hose, and the ends' own move (the larger
    of the two ends' moves + the larger turn of the two fittings x the hose's length)."""
    move = np.linalg.norm(np.diff(points, axis=0), axis=2).max(axis=1)
    own = (np.maximum(np.linalg.norm(np.diff(p0, axis=0), axis=1), np.linalg.norm(np.diff(p1, axis=0), axis=1))
           + length * np.radians(np.maximum(_angle_deg(t0[1:], t0[:-1]), _angle_deg(t1[1:], t1[:-1]))))
    return move, own


def _find_jumps(h, ends, length):
    """A jump: between two neighbouring frames some point of the hose moves more than 6 x as far as the ends did
    AND more than 1 % of the hose's length. Frames next to one where the hose is too short are not counted here
    (see the test about reaching the limit). Returns [(frame, move / L, ends' move / L)], the worst ratio among
    the other steps, the largest move / L."""
    move, own = _steps(h.points, *ends, length)
    ratio = move / np.maximum(own, 1e-4 * length)
    beside_short = h.short[1:] | h.short[:-1]
    jump = (ratio > 6.0) & (move > 0.01 * length) & ~beside_short
    calm = ~jump & ~beside_short
    return ([(int(i), round(float(move[i] / length), 3), round(float(own[i] / length), 4))
             for i in np.flatnonzero(jump)],
            float(ratio[calm].max()) if calm.any() else 0.0, float(move[~beside_short].max() / length))


# (label, ends, length, diameter, stiffness slider, sag)
MOTIONS = {
    # --- a hose across a hinge that swings +-40 degrees (fittings in line at mid-swing, 10-45 % slack)
    "hinge, soft cable L=0.5": (_hinge, {}, 0.50, 0.02, 0.0, 1.0),
    "hinge, soft cable L=0.8": (_hinge, {}, 0.80, 0.02, 0.0, 1.0),
    "hinge, stiff hose L=0.5": (_hinge, {}, 0.50, 0.02, 1.0, 1.0),
    "hinge, stiff hose L=0.6": (_hinge, {}, 0.60, 0.02, 1.0, 1.0),
    "hinge, stiff hose L=0.8": (_hinge, {}, 0.80, 0.02, 1.0, 1.0),
    "hinge, medium hose L=0.6": (_hinge, {}, 0.60, 0.02, 0.5, 1.0),
    "hinge, medium hose L=0.8": (_hinge, {}, 0.80, 0.02, 0.5, 1.0),
    "hinge, stiff hose, no weight L=0.6": (_hinge, {}, 0.60, 0.02, 1.0, 0.0),
    "hinge, fittings 30 mm out of plane, stiff L=0.6": (
        _hinge, dict(a_pt=(-0.2, 0.03, 0.05), b_pt=(0.25, -0.03, 0.05), a_dir=(1, 0.2, 0.1), b_dir=(1, 0.2, -0.1)),
        0.60, 0.02, 1.0, 1.0),
    "hinge, fittings 30 mm out of plane, medium L=0.8": (
        _hinge, dict(a_pt=(-0.2, 0.03, 0.05), b_pt=(0.25, -0.03, 0.05), a_dir=(1, 0.2, 0.1), b_dir=(1, 0.2, -0.1)),
        0.80, 0.02, 0.5, 1.0),
    "hinge about a vertical axis, stiff L=0.6": (_hinge, dict(axis=(0, 0, 1)), 0.60, 0.02, 1.0, 1.0),
    "hinge about a vertical axis, soft L=0.6": (_hinge, dict(axis=(0, 0, 1)), 0.60, 0.02, 0.0, 1.0),
    # --- one end slides 300 mm
    "slide, U-loop (fittings opposed, 250 mm apart), stiff L=0.9": (_slide, {}, 0.90, 0.016, 1.0, 1.0),
    "slide, U-loop, medium L=0.75": (_slide, {}, 0.75, 0.016, 0.5, 1.0),
    "slide, U-loop, soft cable L=0.75": (_slide, {}, 0.75, 0.016, 0.0, 1.0),
    "slide across, both fittings up, stiff L=0.45": (
        _slide, dict(a_dir=(0, 0, 1), b_pt=(0, 0, 0.3), b_dir=(0, 0, 1)), 0.45, 0.016, 1.0, 1.0),
    "slide across, both fittings up, stiff L=0.6": (
        _slide, dict(a_dir=(0, 0, 1), b_pt=(0, 0, 0.3), b_dir=(0, 0, 1)), 0.60, 0.016, 1.0, 1.0),
    "slide along the hose (fittings in line), stiff L=0.7": (
        _slide, dict(b_pt=(0.25, 0, 0), b_dir=(1, 0, 0)), 0.70, 0.016, 1.0, 1.0),
    "slide along the hose (fittings in line), soft L=0.7": (
        _slide, dict(b_pt=(0.25, 0, 0), b_dir=(1, 0, 0)), 0.70, 0.016, 0.0, 1.0),
    # --- a cable between two parts that move apart and together
    "cable, glands down, parts 0.25-0.85 apart, L=1.0": (_apart, {}, 1.00, 0.01, 0.0, 1.0),
    "cable, glands down, L=1.3 medium": (_apart, {}, 1.30, 0.01, 0.5, 1.0),
    "cable, glands facing, offset 100/50 mm, L=1.0": (
        _apart, dict(a_dir=(1, 0, 0), b_dir=(1, 0, 0), dz=0.1, dy=0.05), 1.00, 0.01, 0.0, 1.0),
    "cable, glands facing, offset 100/50 mm, stiff L=1.3": (
        _apart, dict(a_dir=(1, 0, 0), b_dir=(1, 0, 0), dz=0.1, dy=0.05), 1.30, 0.01, 1.0, 1.0),
    "cable, glands facing exactly, stiff L=1.0": (_apart, dict(a_dir=(1, 0, 0), b_dir=(1, 0, 0)), 1.00, 0.01, 1.0, 1.0),
    "cable, glands facing exactly, soft L=1.0": (_apart, dict(a_dir=(1, 0, 0), b_dir=(1, 0, 0)), 1.00, 0.01, 0.0, 1.0),
    # --- an elbow fitting that turns about its own axis
    "elbow 90 turning about a level axis, stiff L=0.6": (_swivel, {}, 0.60, 0.016, 1.0, 1.0),
    "elbow 45 turning about a level axis, soft L=0.45": (_swivel, dict(cone=45.0), 0.45, 0.016, 0.0, 1.0),
    "elbow 90 turning about a vertical axis, stiff L=0.45": (
        _swivel, dict(axis=(0, 0, 1), b_pt=(0.1, 0, 0.35), b_dir=(0, 0, 1)), 0.45, 0.016, 1.0, 1.0),
    "elbow 90 turning about a vertical axis, soft L=0.45": (
        _swivel, dict(axis=(0, 0, 1), b_pt=(0.1, 0, 0.35), b_dir=(0, 0, 1)), 0.45, 0.016, 0.0, 1.0),
    # --- 3-D: hinge and slide together
    "hinge + slide in 3-D, stiff L=0.6": (_hinge_and_slide, {}, 0.60, 0.02, 1.0, 1.0),
    "hinge + slide in 3-D, soft L=0.8": (_hinge_and_slide, {}, 0.80, 0.02, 0.0, 1.0),
    "hinge + slide in 3-D, medium L=0.8": (_hinge_and_slide, {}, 0.80, 0.02, 0.5, 1.0),
}


def _motion(label):
    make, kwargs, length, dia, slider, sag = MOTIONS[label]
    return make(**kwargs), length, flex.stiff_length(dia, slider), sag


def _xf(label, reason):
    return pytest.param(label, marks=pytest.mark.xfail(strict=False, reason=reason))


PLAIN = [
    "hinge, soft cable L=0.5",
    "hinge, soft cable L=0.8",
    _xf("hinge, stiff hose L=0.5", "JUMP (kind 1: the bow flips to the other side where the fittings come in line). "
        "2 jumps, at mid-swing (frames 149->150 and 0->1 of 300): 38 % of the length in one frame while the fitting "
        "turned 0.8 degrees. The bow lies on the side the arm's fitting pushes it to; a real hose stays on its side."),
    _xf("hinge, stiff hose L=0.6", "JUMP (kind 1). 2 jumps of 58 % of the length at mid-swing."),
    _xf("hinge, stiff hose L=0.8", "JUMP (kind 1). 71 % of the length at mid-swing (3 jumps)."),
    _xf("hinge, medium hose L=0.6", "JUMP (kind 1, with weight in play: the flip comes 8 degrees after the middle, "
        "frames 10->11 and 138->139 of 300). 2 jumps of 57 % of the length."),
    _xf("hinge, medium hose L=0.8", "JUMP (kind 1 spread over several frames: the bow goes round through the "
        "side). 8 jumps of 10-33 % of the length per frame (frames 10, 23-25, 123-124 …)."),
    _xf("hinge, stiff hose, no weight L=0.6", "JUMP (kind 1). 2 jumps of 58 % of the length at mid-swing."),
    _xf("hinge, fittings 30 mm out of plane, stiff L=0.6", "JUMP (kind 1 in 3-D). 2 jumps of 52 % of the length."),
    _xf("hinge, fittings 30 mm out of plane, medium L=0.8", "JUMP (kind 1 in 3-D). 4 jumps of 60 % of the length."),
    _xf("hinge about a vertical axis, stiff L=0.6", "JUMP (kind 1, the bow lies level and flips left/right at "
        "mid-swing, and at the first and last frame where the fittings are exactly in line it hangs down instead). "
        "3 jumps: 37 %, 55 %, 37 % of the length (frames 0, 149, 298)."),
    "hinge about a vertical axis, soft L=0.6",
    "slide, U-loop (fittings opposed, 250 mm apart), stiff L=0.9",
    "slide, U-loop, medium L=0.75",
    _xf("slide, U-loop, soft cable L=0.75", "JUMP (kind 4: two shapes of a soft cable). 2 jumps of 17 % of the length "
        "with the end moving 0.07 % of it (frames 7->8 and 291->292, 300 mm stroke); the energy of the "
        "shape taken after the jump is 27 % higher than before it."),
    _xf("slide across, both fittings up, stiff L=0.45", "JUMP (kind 2: FLICKER between mirror shapes). 12 jumps "
        "in one stroke, up to 45 % of the length; in frames 103-111 of 300 the S-shaped hose alternates between its "
        "two mirror images in neighbouring frames (moves of 5-20 % of the length for an end move of 0.5 %; the two "
        "differ in energy only by the weight)."),
    _xf("slide across, both fittings up, stiff L=0.6", "JUMP (kind 2). 2 jumps of 50 % of the length."),
    _xf("slide along the hose (fittings in line), stiff L=0.7", "JUMP (kind 3: bow to loop). 2 jumps of 22 % of the "
        "length where the ends are 0.42 x the length apart: the bow kept in its plane (a balance point there) drops "
        "into a loop."),
    "slide along the hose (fittings in line), soft L=0.7",
    "cable, glands down, parts 0.25-0.85 apart, L=1.0",
    "cable, glands down, L=1.3 medium",
    "cable, glands facing, offset 100/50 mm, L=1.0",
    "cable, glands facing, offset 100/50 mm, stiff L=1.3",
    _xf("cable, glands facing exactly, stiff L=1.0", "JUMP (kind 3: bow to loop). 2 jumps of 22 % of the length at "
        "0.42 x the length between the ends."),
    "cable, glands facing exactly, soft L=1.0",
    "elbow 90 turning about a level axis, stiff L=0.6",
    "elbow 45 turning about a level axis, soft L=0.45",
    "elbow 90 turning about a vertical axis, stiff L=0.45",
    _xf("elbow 90 turning about a vertical axis, soft L=0.45", "JUMP (kind 2: FLICKER). 4 jumps of 14-19 % of the "
        "length within 7 frames (24, 26, 29, 30; the elbow turns 1.2 degrees per frame): two shapes of nearly the "
        "same energy (0.0723 against 0.0730) are taken by turns."),
    "hinge + slide in 3-D, stiff L=0.6",
    "hinge + slide in 3-D, soft L=0.8",
    _xf("hinge + slide in 3-D, medium L=0.8", "JUMP (kind 5: two shapes in 3-D). 3 jumps: 50 %, 52 % and 14 % of "
        "the length."),
]


@pytest.mark.parametrize("label", PLAIN)
def test_hose_follows_a_motion_without_a_jump(label):
    """``solve_hoses`` frame by frame (each frame knows nothing of the others)."""
    ends, length, stiff, sag = _motion(label)
    h = flex.solve_hoses(*ends, length, stiff, sag=sag)
    _assert_hose(h, *ends, length, label=label)
    jumps, ratio, largest = _find_jumps(h, ends, length)
    _say("motion, frame by frame: %s" % label, "jumps %d" % len(jumps),
         "largest move %.1f %% L" % (100 * largest), "worst calm ratio %.2f" % ratio, jumps[:6])
    assert not jumps, jumps


MOTION = [
    "hinge, soft cable L=0.5",
    "hinge, stiff hose L=0.5",
    "hinge, stiff hose L=0.6",
    "hinge, stiff hose L=0.8",
    "hinge, medium hose L=0.6",
    "hinge, medium hose L=0.8",
    "hinge, stiff hose, no weight L=0.6",
    _xf("hinge, fittings 30 mm out of plane, stiff L=0.6", "JUMP left by solve_motion: followed forwards and "
        "backwards the hose still jumps: 3 jumps (49 %, 51 % and 10 % of the length at frames 140, 241, 242) – the "
        "shape it is followed in is lost on the way."),
    _xf("hinge, fittings 30 mm out of plane, medium L=0.8", "JUMP left by solve_motion (one of 57 % of the length)."),
    _xf("hinge about a vertical axis, stiff L=0.6", "JUMP left by solve_motion: the same 3 jumps as frame by "
        "frame (37 %, 55 %, 37 % of the length) – following did not help."),
    "slide, U-loop, soft cable L=0.75",
    "slide across, both fittings up, stiff L=0.45",
    "slide across, both fittings up, stiff L=0.6",
    "slide along the hose (fittings in line), stiff L=0.7",
    _xf("cable, glands facing exactly, stiff L=1.0", "JUMP left by solve_motion: one of 20 % of the length (the "
        "loop it starts in is kept until it is lost on the way out)."),
    _xf("elbow 90 turning about a vertical axis, soft L=0.45", "JUMP left by solve_motion: the 4 jumps of 14-19 % "
        "(flicker) are all still there."),
    _xf("hinge + slide in 3-D, medium L=0.8", "JUMP left by solve_motion: 1 of the 3 (14 % of the length)."),
]


@pytest.mark.skipif(not HAS_MOTION, reason="this copy of core/flex.py has no solve_motion")
@pytest.mark.parametrize("label", MOTION)
def test_solve_motion_follows_a_motion_without_a_jump(label):
    ends, length, stiff, sag = _motion(label)
    clock = time.perf_counter()
    h = flex.solve_motion(*ends, length, stiff, sag=sag)
    spent = time.perf_counter() - clock
    _assert_hose(h, *ends, length, label=label)          # every guarantee of solve_hoses holds for a followed hose
    jumps, ratio, largest = _find_jumps(h, ends, length)
    _say("motion, solve_motion: %s" % label, "jumps %d" % len(jumps), "largest move %.1f %% L" % (100 * largest),
         "worst calm ratio %.2f" % ratio, "%.2f s" % spent, jumps[:6])
    assert not jumps, jumps


@pytest.mark.skipif(not HAS_MOTION, reason="this copy of core/flex.py has no solve_motion")
def test_solve_motion_is_solve_hoses_where_nothing_jumps_and_is_pure():
    ends, length, stiff, sag = _motion("cable, glands facing, offset 100/50 mm, stiff L=1.3")
    plain = flex.solve_hoses(*ends, length, stiff, sag=sag)
    moved = flex.solve_motion(*ends, length, stiff, sag=sag)
    assert np.array_equal(plain.points, moved.points)
    # a motion that needs following: the same frames give the same shapes again, bit for bit
    ends, length, stiff, sag = _motion("hinge, stiff hose L=0.6")
    one = flex.solve_motion(*ends, length, stiff, sag=sag)
    flex.solve_hoses(*_bank(20, 30, 1.0, 0.0, (1.1, 2.0), (0.05, 0.5)))
    two = flex.solve_motion(*ends, length, stiff, sag=sag)
    assert np.array_equal(one.points, two.points) and np.array_equal(one.min_radius, two.min_radius)
    # the shape that is kept never has less energy than the relaxed one (measured: up to 2.4 x as much here –
    # the bow held on its first side while the arm swings 40 degrees the other way)
    plain = flex.solve_hoses(*ends, length, stiff, sag=sag)
    excess = _energy(one.points, length, stiff, sag) / _energy(plain.points, length, stiff, sag) - 1
    _say("solve_motion, stiff hose across the hinge: energy above the frame-by-frame shape, worst", float(excess.max()))
    assert excess.min() > -1e-6
    # one frame, two frames
    single = flex.solve_motion(ends[0][:1], ends[1][:1], ends[2][:1], ends[3][:1], length, stiff)
    assert single.points.shape == (1, 33, 3)


def _nudge_and_let_go(points, length, stiff, sag, steps=6000, kick=1e-2, seed=0):
    """Is this a shape the hose would stay in? Every free segment's direction is nudged at random by about
    ``kick`` radians, then the hose is let go: plain gradient descent on its energy (the directions put back on
    unit length and on their sum after every step, with this file's own 3 x 3 Newton iteration). A minimum is
    come back to; a balance point that would fall over (a saddle) is left. Returns where it ends."""
    n = len(points)
    h = length / (n - 1)
    d = np.diff(points, axis=0) / h
    total = d[1:-1].sum(axis=0)
    q = n - 3

    def back(g):
        lam = np.zeros(3)
        for _ in range(8):
            w = g + lam
            size = np.linalg.norm(w, axis=1)
            unit = w / size[:, None]
            off = unit.sum(axis=0) - total
            if np.abs(off).max() < 1e-13:
                break
            lam = lam - np.linalg.solve(((np.eye(3)[None] - unit[:, :, None] * unit[:, None, :])
                                         / size[:, None, None]).sum(axis=0), off)
        return unit

    free = back(d[1:-1] + kick * np.random.default_rng(seed).normal(size=(q, 3)))
    ds = np.full(n - 2, h)
    ds[0] = ds[-1] = 1.5 * h
    k = (stiff ** 3 / ds)[:, None]
    weight = sag * h * h * (n - 3 - np.arange(q))        # d(sum of the points' heights) / d(a free direction's z)
    step = 0.45 / (2 * k.max())
    full = np.empty((n - 1, 3))
    full[0], full[-1] = d[0], d[-1]
    for _ in range(steps):
        full[1:-1] = free
        m = np.diff(full, axis=0) * k
        grad = m[:-1] - m[1:]
        grad[:, 2] += weight
        free = back(free - step * grad)
    full[1:-1] = free
    return np.concatenate([points[:1], points[0] + h * np.cumsum(full, axis=0)])


STAYS = [("hinge, stiff hose L=0.6", 75), ("hinge + slide in 3-D, stiff L=0.6", 100),
         ("slide along the hose (fittings in line), stiff L=0.7", 150)]


@pytest.mark.parametrize("label,frame", STAYS)
def test_hose_shape_is_one_the_hose_stays_in(label, frame):
    """The frame-by-frame answer is a minimum of the energy: nudged and let go, the hose comes back to it."""
    ends, length, stiff, sag = _motion(label)
    pts = flex.solve_hose(*(e[frame] for e in ends), length, stiff, sag=sag).points[0]
    after = _nudge_and_let_go(pts, length, stiff, sag)
    moved = float(np.abs(after - pts).max() / length)
    seg = np.linalg.norm(np.diff(after, axis=0), axis=1)
    assert np.abs(seg / (length / 32) - 1).max() < 1e-9 and np.abs(after[-1] - pts[-1]).max() < 1e-9
    _say("nudged and let go, frame by frame: %s, frame %d: moved / L" % (label, frame), moved)
    assert moved < 2e-3
    assert float(_energy(after, length, stiff, sag)) >= float(_energy(pts, length, stiff, sag)) * (1 - 1e-6) - 1e-12


@pytest.mark.skipif(not HAS_MOTION, reason="this copy of core/flex.py has no solve_motion")
@pytest.mark.xfail(strict=False, reason="FOUND: the shape solve_motion keeps is at many frames not one a hose would "
                   "stay in – it is a balance point that falls over. Nudged by 0.6 degrees and let go (gradient "
                   "descent on the same energy) the kept shape leaves and ends on the frame-by-frame shape: stiff "
                   "hose across the hinge at full swing (frame 75 of 300): moves 51 % of the length, energy 50.7 -> "
                   "21.0 (2.4 x the relaxed shape's); in-line fittings pushed together and pulled out again (frame "
                   "150): 20 % of the length, energy 104.8 -> 13.6 (7.7 x). The follower takes plain Newton steps on "
                   "the fine level, which follow an equilibrium also after it has become unstable; a real hose "
                   "snaps over at that moment. The frame-by-frame shapes pass the same test (they move < 0.2 %).")
@pytest.mark.parametrize("label,frame", STAYS[::2])
def test_solve_motion_shape_is_one_the_hose_stays_in(label, frame):
    ends, length, stiff, sag = _motion(label)
    pts = flex.solve_motion(*ends, length, stiff, sag=sag).points[frame]
    after = _nudge_and_let_go(pts, length, stiff, sag)
    moved = float(np.abs(after - pts).max() / length)
    _say("nudged and let go, solve_motion: %s, frame %d: moved / L, energy before -> after" % (label, frame), moved,
         float(_energy(pts, length, stiff, sag)), float(_energy(after, length, stiff, sag)))
    assert moved < 2e-3


@pytest.mark.skipif(not HAS_MOTION, reason="this copy of core/flex.py has no start=")
def test_hose_start_argument_keeps_every_guarantee():
    p0, t0, p1, t1, length, stiff = _bank(21, 80, 1.0, 0.0, (1.05, 2.5), (0.02, 1.0))
    best = flex.solve_hoses(p0, t0, p1, t1, length, stiff)
    assert best.start.shape == (80,) and np.isin(best.start, (0, 1, 2)).all()
    same = flex.solve_hoses(p0, t0, p1, t1, length, stiff, start=-1)
    assert np.array_equal(best.points, same.points)
    for k in (0, 1, 2):
        h = flex.solve_hoses(p0, t0, p1, t1, length, stiff, start=k)
        _assert_hose(h, p0, t0, p1, t1, length, label="start %d" % k)
        assert np.array_equal(h.short, best.short) and np.allclose(h.need, best.need)
        ok = ~h.short
        assert (h.start[ok] == k).all()
        mine = ok & (best.start == k)                    # asked for by name: the answer the best came from
        if mine.any():
            assert np.abs(h.points[mine] - best.points[mine]).max() < 1e-9
    again = flex.solve_hoses(p0, t0, p1, t1, length, stiff, start=best.start)       # one start per hose
    assert np.abs(again.points - best.points).max() < 1e-9
    with pytest.raises(ValueError):
        flex.solve_hoses(p0, t0, p1, t1, length, stiff, start=3)


@pytest.mark.xfail(strict=False, reason="FOUND (by design, but it shows): where a hose stops reaching, the shape "
                   "snaps from 'first and last segment in their fittings, straight between' to the plain straight "
                   "line p0 -> p1. With glands pointing down and a 0.9 m cable that is 5.1 % of the length (46 mm) in "
                   "one frame, and back when it reaches again.")
def test_hose_reaching_its_limit_does_not_snap():
    ends = _apart()
    h = flex.solve_hoses(*ends, 0.9, flex.stiff_length(0.01, 0.0))
    assert h.short.any() and not h.short.all()
    move, own = _steps(h.points, *ends, 0.9)
    edge = h.short[1:] != h.short[:-1]
    _say("cable becoming too short: move of a point at that frame / L", float(move[edge].max() / 0.9))
    assert move[edge].max() < 0.01 * 0.9


# =====================================================================================================================
# DRAG CHAINS
# =====================================================================================================================

def _turns(pins):
    """The signed turn (about +w) at every inner pin, seen in the chain's plane: (..., links - 1)."""
    x = np.diff(pins[..., :2], axis=-2)
    a = np.arctan2(x[..., 1], x[..., 0])
    return (np.diff(a, axis=-1) + np.pi) % (2 * np.pi) - np.pi


def _stroke(spec, lo, hi, frames, v=None, w=0.0):
    """The moving end travelling along u at height v (default 2 x radius); lo / hi as shares of the classic
    travel limit (chain length - half the bend's circumference)."""
    reach = spec.links * spec.pitch - math.pi * spec.radius
    u = np.linspace(lo * reach, hi * reach, frames)
    v = 2 * spec.radius if v is None else v
    return np.stack([u, np.full(frames, v), np.full(frames, w)], axis=1)


@pytest.mark.parametrize("ratio", [1.5, 2.0, 3.3, 6.0])
def test_chain_classic_stroke_is_exact(ratio):
    pitch, links = 0.04, 70
    radius = ratio * pitch
    spec = fc.ChainSpec(pitch, links, radius)
    moving = _stroke(spec, -0.9, 0.9, 721)
    c = fc.chain_pins(spec, moving)
    pins = c.pins
    assert pins.shape == (721, links + 1, 3) and not c.short.any() and np.isfinite(pins).all()
    assert np.array_equal(pins[:, 0], np.zeros((721, 3)))                                   # pin 0: the origin
    assert np.array_equal(pins[:, -1], moving)                                              # the last: the moving end
    chord = np.linalg.norm(np.diff(pins, axis=1), axis=2)
    assert np.abs(chord / pitch - 1).max() < 1e-9
    assert np.abs(chord.sum(axis=1) - links * pitch).max() < 1e-9 * links * pitch           # the length stays
    assert np.abs(pins[:, :, 2]).max() == 0.0
    # three kinds of pins, each where it belongs
    index = np.arange(links + 1)[None, :]
    on_run = index * pitch <= c.bend_u[:, None] * (1 + 1e-12)
    assert np.abs(pins[:, :, 1][on_run]).max() == 0.0                                       # the fixed run: v = 0
    assert np.abs((pins[:, :, 0] - index * pitch)[on_run]).max() < 1e-12
    upper = ~on_run & (np.abs(pins[:, :, 1] - 2 * radius) < 1e-9 * pitch)
    bend = ~on_run & ~upper
    off_circle = np.abs(np.hypot(pins[:, :, 0] - c.bend_u[:, None], pins[:, :, 1] - radius) - radius)
    assert off_circle[bend].max() < 1e-9 * pitch                                            # the bend: on the circle
    per_bend = bend.sum(axis=1)
    assert per_bend.min() >= math.floor(math.pi * radius / pitch) - 1
    assert per_bend.max() <= math.ceil(math.pi * radius / pitch) + 1
    # order along the chain: run, bend, upper run – no pin of one kind between pins of another
    kind = np.where(on_run, 0, np.where(bend, 1, 2))
    assert (np.diff(kind, axis=1) >= 0).all()
    # the upper run comes straight back
    back = np.diff(pins[:, :, 0], axis=1)[upper[:, 1:] & upper[:, :-1]]
    assert np.abs(back + pitch).max() < 1e-9 * pitch
    # no joint turns the wrong way or further than a link turns in the bend
    turn = _turns(pins)
    phi = 2 * math.asin(pitch / (2 * radius))
    assert turn.min() > -1e-9 and turn.max() < phi + 1e-9
    # the bend moves at half the moving end's speed
    rate = np.diff(c.bend_u) / np.diff(moving[:, 0])
    assert 0.48 < rate.min() and rate.max() < 0.52       # (a coarse chain, R = 1.5 pitches: 0.492 … 0.508)
    whole = (c.bend_u[-1] - c.bend_u[0]) / (moving[-1, 0] - moving[0, 0])
    assert whole == pytest.approx(0.5, abs=2e-3)
    # continuity: no pin moves further than the moving end does (a hair more where a pin goes onto the bend)
    step = np.linalg.norm(np.diff(pins, axis=0), axis=2).max(axis=1) / np.diff(moving[:, 0])
    assert step.max() < 1.06
    _say("chain R/p=%g: chord / bend pins off the circle (per pitch) / bend speed min-max / pin step per end step"
         % ratio, float(np.abs(chord / pitch - 1).max()), float(off_circle[bend].max() / pitch),
         "%.4f-%.4f" % (rate.min(), rate.max()), float(step.max()))


@pytest.mark.parametrize("mode", ["STRAIGHT", "GLIDE"])
def test_chain_moving_end_a_little_off(mode):
    """v not 2 R and w not 0: still every chord one pitch (in 3-D), still the last pin on the moving end."""
    rng = np.random.default_rng(31)
    worst_chord = worst_step = 0.0
    for trial in range(40):
        pitch = rng.uniform(0.02, 0.1)
        radius = rng.uniform(1.5, 6.0) * pitch
        links = int(rng.integers(60, 160))
        spec = fc.ChainSpec(pitch, links, radius, mode, glide_angle=math.radians(rng.uniform(5, 25)))
        v = rng.uniform(0.3, 1.0) * radius if mode == "GLIDE" else 2 * radius * (1 + rng.uniform(-0.1, 0.1))
        w = rng.uniform(-0.3, 0.3) * radius if trial % 3 else 0.0
        if mode == "GLIDE":
            moving = np.stack([np.linspace(-0.3, 0.3, 200) * links * pitch, np.full(200, v), np.full(200, w)], axis=1)
        else:
            moving = _stroke(spec, -0.4, 0.6, 200, v, w)
        c = fc.chain_pins(spec, moving)
        assert not c.short.any(), (trial, pitch, radius, links, v, w)
        pins = c.pins
        chord = np.linalg.norm(np.diff(pins, axis=1), axis=2)
        worst_chord = max(worst_chord, float(np.abs(chord / pitch - 1).max()))
        assert np.array_equal(pins[:, -1], moving) and np.array_equal(pins[:, 0], np.zeros((200, 3)))
        # sideways: nothing before the bend starts, then evenly up to the moving end
        index = np.arange(links + 1)[None, :]
        before = index * pitch <= c.bend_u[:, None]
        assert np.abs(pins[:, :, 2][before]).max() == 0.0
        dw = np.diff(pins[:, :, 2], axis=1)
        if w:
            assert (dw * np.sign(w) >= -1e-15).all()
            later = (index[:, :-1] * pitch > c.bend_u[:, None] + pitch)
            spread = np.where(later, dw, np.nan)
            assert np.nanmax(np.nanmax(spread, axis=1) - np.nanmin(spread, axis=1)) < 1e-12
        # the fixed run and the bend are where they belong
        assert np.abs(pins[:, :, 1][before]).max() == 0.0
        on_circle = np.abs(np.hypot(pins[:, :, 0] - c.bend_u[:, None], pins[:, :, 1] - radius) - radius) < 1e-9 * pitch
        first = before.sum(axis=1)
        some = max(int((math.pi - 1.2) * radius / pitch) - 1, 1)
        for k in range(some):                            # the pins right after the fixed run are on the circle
            assert on_circle[np.arange(200), first + k].all()
        turn = _turns(pins)
        phi = 2 * math.asin(pitch / (2 * radius))
        assert turn.max() < phi + 1e-9
        if mode == "STRAIGHT":
            assert turn.min() > -1e-9
        step = np.linalg.norm(np.diff(pins, axis=0), axis=2).max(axis=1) / np.diff(moving[:, 0])
        worst_step = max(worst_step, float(step.max()))
    assert worst_chord < 1e-9 and worst_step < 1.5
    _say("chain %s, end off (v, w): chord / pin step per end step" % mode, worst_chord, worst_step)


def test_chain_glide_lies_on_the_fixed_run():
    pitch, links, radius, height = 0.05, 80, 0.15, 0.06
    angle = math.radians(12.0)
    spec = fc.ChainSpec(pitch, links, radius, "GLIDE", glide_angle=angle)
    moving = np.stack([np.linspace(-1.0, 1.5, 251), np.full(251, height), np.zeros(251)], axis=1)
    c = fc.chain_pins(spec, moving)
    pins = c.pins
    assert not c.short.any()
    assert np.abs(np.linalg.norm(np.diff(pins, axis=1), axis=2) / pitch - 1).max() < 1e-9
    assert np.array_equal(pins[:, -1], moving)
    top = radius * (1 + math.cos(angle))                 # where the slope leaves the circle
    assert (pins[:, :, 1].max(axis=1) <= 2 * radius + 1e-12).all()
    assert (pins[:, :, 1].max(axis=1) >= top - pitch).all()
    assert (pins[:, :, 1] >= -1e-12).all()               # never under the fixed run
    # after the hump the run comes down at the glide angle and then lies at the moving end's height
    seg = np.diff(pins, axis=1)
    slope = np.degrees(np.arctan2(-seg[:, :, 1], -seg[:, :, 0]))             # how steeply a link comes down
    hump = pins[:, :, 1].argmax(axis=1)
    for f in (0, 100, 200):                              # (from frame 222 on the end is too near the bend)
        after = slope[f, hump[f]:]
        assert after.min() > -1e-9 and after.max() < math.degrees(angle) + 1e-6     # never up again, never steeper
        on_slope = np.abs(after - math.degrees(angle)) < 1e-6
        assert on_slope.sum() >= (top - height) / math.sin(angle) / pitch - 3
        lying = np.abs(pins[f, hump[f]:, 1] - height) < 1e-9
        assert lying.any() and lying[np.argmax(lying):].all()                  # once down it stays down
    # the foot of the slope is a kink: the chain turns back there by the glide angle, shared by two pins
    turn = np.degrees(_turns(pins))
    assert turn.min() > -math.degrees(angle) - 1e-6
    _say("chain GLIDE: the sharpest turn backwards at one pin, degrees (glide angle 12)", float(turn.min()))
    # STRAIGHT with the same low moving end has no hump: its run goes straight from the bend to the end
    plain = fc.chain_pins(fc.ChainSpec(pitch, links, radius), moving)
    assert not np.allclose(plain.pins, pins)
    # the bend still moves at half the end's speed, and nothing jumps
    rate = np.diff(c.bend_u) / np.diff(moving[:, 0])
    step = np.linalg.norm(np.diff(pins, axis=0), axis=2).max(axis=1) / np.diff(moving[:, 0])
    assert 0.49 < rate.min() and rate.max() < 0.51 and step.max() < 1.06
    # rest_v above the end: the run comes down to rest_v and goes on to the end from there
    high = fc.chain_pins(fc.ChainSpec(pitch, links, radius, "GLIDE", glide_angle=angle, rest_v=0.12), moving)
    assert not high.short.any() and np.array_equal(high.pins[:, -1], moving)
    assert np.abs(np.linalg.norm(np.diff(high.pins, axis=1), axis=2) / pitch - 1).max() < 1e-9
    # near the bend there is no room to come down: GLIDE and STRAIGHT meet without a jump
    close = np.stack([np.linspace(2.0, 3.6, 801), np.full(801, height), np.zeros(801)], axis=1)
    g = fc.chain_pins(spec, close)
    reach = ~g.short
    step = np.linalg.norm(np.diff(g.pins, axis=0), axis=2).max(axis=1) / np.diff(close[:, 0])
    both = reach[1:] & reach[:-1]
    _say("chain GLIDE: pin step per end step over the whole reach, also where the slope has no room",
         float(step[both].max()), "in reach up to u = %.3f" % close[reach, 0].max())
    assert reach.sum() > 300


def _link_boxes(pins, length, height):
    """Each link as a rectangle ``length`` x ``height`` in the chain's plane, centred between its pins: (L, 4, 2)."""
    a, b = pins[:-1, :2], pins[1:, :2]
    x = _unit(b - a)
    y = np.stack([-x[:, 1], x[:, 0]], axis=1)
    mid = 0.5 * (a + b)
    return np.stack([mid + sx * 0.5 * length * x + sy * 0.5 * height * y
                     for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))], axis=1)


def _least_gap(boxes):
    """The least gap between any two of the rectangles (separating axes; negative: they overlap by that much)."""
    edge = boxes[:, [1, 2]] - boxes[:, [0, 1]]                              # two edge directions per box
    axes = _unit(np.stack([edge[..., 1], -edge[..., 0]], axis=-1))          # (L, 2, 2)
    count = len(boxes)
    proj = np.einsum("iak,jck->ijac", axes, boxes)                          # box j's corners on box i's axes
    lo, hi = proj.min(axis=3), proj.max(axis=3)                             # (i, j, axis)
    own_lo, own_hi = lo[np.arange(count), np.arange(count)], hi[np.arange(count), np.arange(count)]
    gap = np.maximum(lo - own_hi[:, None, :], own_lo[:, None, :] - hi)      # apart along i's axis a by this
    best = np.maximum(gap.max(axis=2), gap.max(axis=2).T)                   # the best axis of either box
    best[np.arange(count), np.arange(count)] = np.inf
    return float(best.min())


@pytest.mark.parametrize("mode", ["STRAIGHT", "GLIDE"])
def test_chain_links_never_overlap(mode):
    """Each link a rectangle in the chain's plane, ``height`` thick and as long as just clears its neighbour on
    the nominal bend (pitch - height * tan(turn / 2), a real link's proportions); R / pitch 1.5 … 6, height up to
    the radius. Neighbours and the two runs against each other, over a whole stroke. (GLIDE: the links must also
    clear the kink at the foot of the slope, where the chain turns BACK by the glide angle at one pin – for
    R / pitch above 4.8 that is more than a link turns in the bend.)"""
    pitch, links = 0.05, 64
    worst = np.inf
    for ratio in (1.5, 2.0, 3.0, 4.5, 6.0):
        radius = ratio * pitch
        phi = 2 * math.asin(pitch / (2 * radius))
        for share in (0.4, 0.8, 1.0):
            height = share * radius
            clear = height * math.tan(0.5 * (phi if mode == "STRAIGHT" else max(phi, math.radians(12.0))))
            if mode == "GLIDE":                          # the upper run lies 5 % of a link's height above the lower
                spec = fc.ChainSpec(pitch, links, radius, "GLIDE")
                moving = np.stack([np.linspace(-0.25, 0.2, 21) * links * pitch, np.full(21, 1.05 * height),
                                   np.zeros(21)], axis=1)
                if 1.05 * height >= radius * (1 + math.cos(spec.glide_angle)):
                    continue
            else:
                spec = fc.ChainSpec(pitch, links, radius)
                moving = _stroke(spec, -0.8, 0.8, 21)
            c = fc.chain_pins(spec, moving)
            assert not c.short.any()
            for pins in c.pins:
                gap = _least_gap(_link_boxes(pins, pitch - clear - 1e-6 * pitch, height))
                worst = min(worst, gap / pitch)
                assert gap > 0.0, (mode, ratio, share, gap)
    _say("chain %s: least gap between any two links' rectangles, in pitches" % mode, worst)


def test_chain_out_of_reach_is_sane():
    spec = fc.ChainSpec(0.04, 40, 0.08)
    for moving in ((5.0, 0.16, 0.0), (-5.0, 0.16, 0.0), (0.5, 5.0, 0.0), (0.5, 0.16, 2.0), (1e9, 1e9, 1e9),
                   (np.nan, 0.0, 0.0), (np.inf, 0.16, 0.0), (0.5, -np.inf, 0.0)):
        c = fc.chain_pins(spec, moving)
        assert c.short[0], moving
        assert np.isfinite(c.pins).all() and np.isfinite(c.bend_u).all(), moving
        assert np.array_equal(c.pins[0, 0], np.zeros(3))
        assert np.abs(np.linalg.norm(np.diff(c.pins[0], axis=0), axis=1) / 0.04 - 1).max() < 1e-9, moving
    # pulled out ahead: the chain points at the moving end as well as it can (its last pin is the nearest it gets)
    c = fc.chain_pins(spec, (5.0, 0.16, 0.0))
    assert c.pins[0, -1, 0] > 0.99 * 1.6 * math.cos(math.atan2(0.16, 5.0)) - 0.05
    # too far back: the bend stops at pin 0
    c = fc.chain_pins(spec, (-5.0, 0.16, 0.0))
    assert c.bend_u[0] == pytest.approx(0.0, abs=1e-9) and c.pins[0, -1, 1] == pytest.approx(0.16, abs=1e-9)
    # in a batch the frames out of reach do not disturb the others
    moving = np.array([(0.3, 0.16, 0.0), (9.0, 0.16, 0.0), (0.5, 0.16, 0.0), (np.nan, 0.0, 0.0), (0.7, 0.16, 0.0)])
    c = fc.chain_pins(spec, moving)
    assert list(c.short) == [False, True, False, True, False]
    for i in (0, 2, 4):
        assert np.array_equal(c.pins[i], fc.chain_pins(spec, moving[i]).pins[0])
    # chains shorter than their own bend: short, never an error
    for links in (1, 2, 3):
        c = fc.chain_pins(fc.ChainSpec(0.04, links, 0.08), (0.02, 0.16, 0.0))
        assert c.short[0] and c.pins.shape == (1, links + 1, 3) and np.isfinite(c.pins).all()
    # what a chain cannot be is refused in plain words
    for bad in (fc.ChainSpec(0.0, 10, 0.1), fc.ChainSpec(0.04, 0, 0.1), fc.ChainSpec(0.04, 10, -1.0),
                fc.ChainSpec(0.04, 10, 0.1, "LOOP"), fc.ChainSpec(float("nan"), 10, 0.1)):
        with pytest.raises(ValueError):
            fc.chain_pins(bad, (0.1, 0.2, 0.0))
    with pytest.raises(ValueError):
        fc.chain_pins(spec, (0.1, 0.2))
    # extremes of size: a watch chain and a ship's
    for pitch in (1e-4, 40.0):
        s = fc.ChainSpec(pitch, 40, 2 * pitch)
        c = fc.chain_pins(s, (8 * pitch, 4 * pitch, 0.0))
        assert not c.short[0]
        assert np.abs(np.linalg.norm(np.diff(c.pins[0], axis=0), axis=1) / pitch - 1).max() < 1e-9


def test_chain_reach_ends_without_a_jump_at_the_back():
    """Travelling back until the fixed run is used up: the last frames in reach and the first out of reach differ
    by no more than the end moved (the bend stops at pin 0, the chain stays as it is)."""
    spec = fc.ChainSpec(0.04, 40, 0.08)
    moving = _stroke(spec, -1.05, -0.9, 601)
    c = fc.chain_pins(spec, moving)
    assert c.short[0] and not c.short[-1]
    edge = int(np.flatnonzero(~c.short)[0])
    step = np.linalg.norm(np.diff(c.pins, axis=0), axis=2).max(axis=1) / np.diff(moving[:, 0])
    assert step.max() < 1.06
    assert moving[edge, 0] == pytest.approx(-(40 * 0.04 - math.pi * 0.08), abs=0.02)        # the classic limit
    # out of reach the chain keeps its last shape (apart from its last pin's place)
    assert np.abs(c.pins[0] - c.pins[edge - 1]).max() < 1e-6


@pytest.mark.xfail(strict=False, reason="FOUND: pulled out ahead (the moving end beyond 'chain length - half the "
                   "bend', where the bend is less than half a turn) the chain whips: just before it is out of reach "
                   "(u = 1.59 m for a 1.6 m chain) a pin moves 17.8 x as far as the moving end between two steps "
                   "of 1 mm, and the bend's place runs backwards at up to 180 x the end's speed. Geometry of a "
                   "chain pulled straight, not a fault of the walk – but the frames before `short` look wrong for "
                   "a drag chain (it has no stops against straightening in this model).")
def test_chain_pulled_out_ahead_stays_calm():
    spec = fc.ChainSpec(0.04, 40, 0.08)
    u = np.linspace(1.30, 1.60, 301)
    moving = np.stack([u, np.full(301, 0.16), np.zeros(301)], axis=1)
    c = fc.chain_pins(spec, moving)
    both = ~c.short[1:] & ~c.short[:-1]
    step = np.linalg.norm(np.diff(c.pins, axis=0), axis=2).max(axis=1) / np.diff(u)
    _say("chain pulled out ahead: pin step per end step, worst", float(step[both].max()))
    assert step[both].max() < 2.0


@pytest.mark.xfail(strict=False, reason="FOUND: a moving end below the fixed run or on it (v <= 0, behind the bend) "
                   "counts as reached (short False): the chain is led round the bend and back down THROUGH its own "
                   "fixed run (moving (0.5, -0.3): bend_u 0.79, the run crosses v = 0 at u ~ 0.6 where the fixed run "
                   "lies; moving (0, 0, 0): the last pin sits on pin 0). Nothing says the pose is impossible.")
def test_chain_moving_end_under_the_fixed_run_is_not_reached():
    spec = fc.ChainSpec(0.04, 40, 0.08)
    for moving in ((0.5, -0.3, 0.0), (0.3, 0.0, 0.0), (0.0, 0.0, 0.0)):
        assert fc.chain_pins(spec, moving).short[0], moving


def test_chain_batch_is_each_alone_and_pure():
    spec = fc.ChainSpec(0.04, 50, 0.1, "GLIDE")
    rng = np.random.default_rng(8)
    moving = np.stack([rng.uniform(-1.0, 2.5, 80), rng.uniform(0.02, 0.25, 80), rng.uniform(-0.05, 0.05, 80)], axis=1)
    whole = fc.chain_pins(spec, moving)
    for i in range(80):
        one = fc.chain_pins(spec, moving[i])
        assert np.array_equal(one.pins[0], whole.pins[i]) and one.short[0] == whole.short[i]
        assert one.bend_u[0] == whole.bend_u[i]
    perm = rng.permutation(80)
    mixed = fc.chain_pins(spec, moving[perm])
    assert np.array_equal(mixed.pins, whole.pins[perm]) and np.array_equal(mixed.short, whole.short[perm])
    fc.chain_pins(fc.ChainSpec(0.03, 20, 0.2), (0.1, 0.4, 0.0))
    again = fc.chain_pins(spec, moving)
    assert np.array_equal(again.pins, whole.pins) and np.array_equal(again.bend_u, whole.bend_u)
    assert 5 < whole.short.sum() < 75                    # both kinds of frames were in it


def test_chain_link_frames_and_matrices():
    spec = fc.ChainSpec(0.04, 30, 0.07)
    pins = fc.chain_pins(spec, np.array([(0.3, 0.14, 0.0), (0.2, 0.15, 0.03)])).pins
    origin, x, z = fc.link_frames(pins)
    assert origin.shape == x.shape == z.shape == (2, 30, 3)
    assert np.array_equal(origin, pins[:, :-1])
    assert np.allclose(x, _unit(np.diff(pins, axis=1)), atol=1e-12)
    assert np.abs(np.einsum("...k,...k->...", x, z)).max() < 1e-12 and np.allclose(np.linalg.norm(z, axis=-1), 1.0)
    assert (z[..., 2] > 0.9).all()                       # near w
    assert np.allclose(z[0], (0, 0, 1))                  # in the plane: exactly w
    mats = fc.pin_matrices(pins)
    assert mats.shape == (2, 30, 4, 4)
    assert np.allclose(mats[..., :3, 0], x) and np.allclose(mats[..., :3, 2], z)
    assert np.allclose(mats[..., :3, 3], origin)
    assert np.allclose(mats[..., :3, 1], np.cross(z, x)) and np.allclose(mats[..., 3, :], (0, 0, 0, 1))
    assert np.allclose(np.linalg.det(mats[..., :3, :3]), 1.0)
    # y points from the fixed run towards the moving run (+v on the fixed run)
    assert np.allclose(mats[0, 0, :3, 1], (0, 1, 0))
    rng = np.random.default_rng(2)
    local = np.array([_rigid(rng, 0.01) for _ in range(30)])
    frame = _rigid(rng, 3.0)
    assert np.allclose(fc.link_matrices(pins, local), mats @ local)
    assert np.allclose(fc.link_matrices(pins, local, frame), frame @ mats @ local)
    # a link pointing straight across (along w) still gets a frame
    o, x, z = fc.link_frames(np.array([(0, 0, 0), (0, 0, 1.0)]))
    assert np.isfinite(z).all() and abs(float(x[0] @ z[0])) < 1e-12 and np.linalg.norm(z[0]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------------------------------------------------
# the chain read from its CAD links
# ---------------------------------------------------------------------------------------------------------------------

def _pin_frames(pins):
    """This file's own frames on the pins: x along the link, z = w made square to x, y = z x x."""
    x = _unit(np.diff(pins, axis=0))
    z = _unit(np.array([0.0, 0.0, 1.0]) - x * x[:, 2:3])
    out = np.zeros((len(x), 4, 4))
    out[:, :3, 0], out[:, :3, 1], out[:, :3, 2], out[:, :3, 3], out[:, 3, 3] = x, np.cross(z, x), z, pins[:-1], 1.0
    return out


class _Cad:
    """A chain as a CAD file has it: one matrix per link (the link mesh's own origin anywhere, turned anyhow),
    the links' mesh centres, the kind of each link; the whole chain placed somewhere in the model."""

    def __init__(self, spec, moving, kinds=1, seed=0, world=None):
        rng = np.random.default_rng(seed)
        self.spec, self.kinds = spec, kinds
        self.world = _rigid(rng, 2.0) if world is None else np.asarray(world, dtype=float)
        self.own = [_rigid(rng, 0.01) for _ in range(kinds)]                 # where each kind's mesh origin is
        self.centre = [np.append(rng.normal(size=3) * 0.004 + [0.5 * spec.pitch, 0, 0], 1.0) for _ in range(kinds)]
        self.types = np.arange(spec.links) % kinds
        self.mats, self.centres = self.at(moving)

    def at(self, moving):
        c = fc.chain_pins(self.spec, moving)
        assert not c.short[0]
        frames = _pin_frames(c.pins[0])
        mats = self.world @ frames @ np.array([self.own[t] for t in self.types])
        centres = np.array([(self.world @ frames[i] @ self.centre[t])[:3] for i, t in enumerate(self.types)])
        return mats, centres


@pytest.mark.parametrize("kinds", [1, 2])
def test_fit_links_round_trip(kinds):
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    worst = 0.0
    for case in range(5):
        pose = np.array([0.25 + 0.07 * case, 2 * radius, 0.0])
        cad = _Cad(spec, pose, kinds, seed=40 + case)
        perm = np.random.default_rng(case).permutation(links)
        fit = fc.fit_links(cad.mats[perm], cad.centres[perm], cad.types[perm] + 7)
        assert fit.ok and fit.problem == "", fit.problem
        assert fit.links == links and fit.mode == "STRAIGHT"
        assert fit.pitch == pytest.approx(pitch, rel=1e-9) and fit.radius == pytest.approx(radius, rel=1e-9)
        assert fit.residual < 1e-9 * pitch and fit.pose_error < 1e-9 * pitch
        assert np.allclose(fit.moving, pose, atol=1e-9)
        assert np.array_equal(perm[fit.order], np.arange(links))             # in order, the fixed end first
        assert fit.local.shape == (links, 4, 4) and fit.pins.shape == (links + 1, 3)
        # the frame: the chain's own axes, wherever along w the pins were put
        assert np.allclose(fit.frame[:3, :3], cad.world[:3, :3], atol=1e-9)
        assert np.allclose(np.linalg.det(fit.frame[:3, :3]), 1.0)
        off = fit.frame[:3, 3] - cad.world[:3, 3]
        assert np.linalg.norm(off - cad.world[:3, 2] * (off @ cad.world[:3, 2])) < 1e-9
        # the CAD pose again, and any other place of the moving end in the chain's plane
        for moving in (pose, (0.05, 2 * radius, 0.0), (0.62, 2 * radius, 0.0), (0.4, 2.1 * radius, 0.0),
                       (0.3, 1.9 * radius, 0.0)):
            want, _ = cad.at(moving)
            got = fc.link_matrices(fc.chain_pins(fit.spec(), moving).pins[0], fit.local, fit.frame)
            back = np.empty_like(got)
            back[perm[fit.order]] = got
            worst = max(worst, float(np.abs(back[perm] - want[perm]).max()))
            assert np.abs(back - want).max() < 1e-9
        # a moving end a little out of the plane: the links follow (their turn about the chain is a matter of
        # where the pins lie along w, which the CAD pose does not say: allow 0.5 mm on a 40 mm link)
        want, _ = cad.at((0.4, 2 * radius, 0.01))
        got = fc.link_matrices(fc.chain_pins(fit.spec(), (0.4, 2 * radius, 0.01)).pins[0], fit.local, fit.frame)
        back = np.empty_like(got)
        back[perm[fit.order]] = got
        assert np.abs(back - want).max() < 5e-4
    _say("fit_links round trip, %d kind(s) of link: matrices at another moving end, worst" % kinds, worst)


def test_fit_links_reversed_and_the_end_it_picks():
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    cad = _Cad(spec, (0.35, 2 * radius, 0.0), 2, seed=3)
    fit = fc.fit_links(cad.mats, cad.centres, cad.types)
    rev = fit.reversed()
    assert rev.ok and rev.links == links and rev.pitch == fit.pitch and rev.radius == fit.radius
    assert np.array_equal(rev.order, fit.order[::-1])
    assert np.allclose(rev.pins, fit.pins[::-1])
    assert np.allclose(rev.moving, (-0.35, 2 * radius, 0.0), atol=1e-9)      # the old pin 0 seen from the other end
    assert np.allclose(rev.frame[:3, 0], fit.frame[:3, 0]) and np.allclose(rev.frame[:3, 1], -fit.frame[:3, 1])
    assert np.allclose(np.linalg.det(rev.frame[:3, :3]), 1.0)
    # the reversed fit draws the CAD pose too
    got = fc.link_matrices(fc.chain_pins(rev.spec(), rev.moving).pins[0], rev.local, rev.frame)
    back = np.empty_like(got)
    back[rev.order] = got
    assert np.abs(back - cad.mats).max() < 1e-9
    # … and moves the other way round: its moving end is the CAD's fixed end
    twice = rev.reversed()
    assert np.allclose(twice.moving, fit.moving) and np.allclose(twice.frame, fit.frame)
    assert np.array_equal(twice.order, fit.order) and np.allclose(twice.local, fit.local)
    # the fixed end is the end of the longer straight run: drawn with the moving run the longer one, the fit
    # starts from the other end
    longer = _Cad(spec, (-0.35, 2 * radius, 0.0), 1, seed=4)
    fit2 = fc.fit_links(longer.mats, longer.centres)
    assert fit2.ok and np.array_equal(fit2.order, np.arange(links)[::-1])
    assert np.allclose(fit2.moving, (0.35, 2 * radius, 0.0), atol=1e-9)
    assert np.allclose(fit2.reversed().moving, (-0.35, 2 * radius, 0.0), atol=1e-9)
    # a fit that is not one stays what it is
    bad = fc.fit_links(cad.mats[:3])
    assert not bad.reversed().ok and bad.reversed().problem == bad.problem


def test_fit_links_planes_scale_and_modes():
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    # standing, lying on its side, hanging upside down, mirrored: the frame is always right-handed, u along the
    # fixed run, v towards the moving run
    for turn in (np.eye(4), np.array([[1.0, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]),
                 np.diag([1.0, -1.0, -1.0, 1.0]), np.diag([-1.0, 1.0, -1.0, 1.0])):
        cad = _Cad(spec, (0.4, 2 * radius, 0.0), 1, seed=5, world=turn)
        fit = fc.fit_links(cad.mats, cad.centres)
        assert fit.ok and fit.pitch == pytest.approx(pitch) and fit.radius == pytest.approx(radius)
        assert np.allclose(fit.frame[:3, :3], turn[:3, :3], atol=1e-9)
        assert np.allclose(fit.moving, (0.4, 2 * radius, 0.0), atol=1e-9)
    # link meshes in mm inside a model in m (a scale of 0.001 in every matrix)
    cad = _Cad(spec, (0.4, 2 * radius, 0.0), 1, seed=6)
    scale = np.diag([0.001, 0.001, 0.001, 1.0])
    fit = fc.fit_links(cad.mats @ scale, cad.centres)
    assert fit.ok and fit.pitch == pytest.approx(pitch) and fit.radius == pytest.approx(radius)
    want, _ = cad.at((0.2, 2 * radius, 0.0))
    got = fc.link_matrices(fc.chain_pins(fit.spec(), (0.2, 2 * radius, 0.0)).pins[0], fit.local, fit.frame)
    back = np.empty_like(got)
    back[fit.order] = got
    assert np.abs(back - want @ scale).max() < 1e-9
    # no centres given: the matrices' origins do
    assert fc.fit_links(cad.mats).radius == pytest.approx(radius)
    # a chain drawn gliding (the upper run lying low) is read as GLIDE
    glide = fc.ChainSpec(0.05, 80, 0.15, "GLIDE")
    cad = _Cad(glide, (0.5, 0.06, 0.0), 1, seed=7)
    fit = fc.fit_links(cad.mats, cad.centres)
    assert fit.ok and fit.mode == "GLIDE" and fit.radius == pytest.approx(0.15) and fit.pose_error < 1e-9
    assert np.allclose(fit.moving, (0.5, 0.06, 0.0), atol=1e-9)
    # the moving end drawn a little low or high: still the bend's own radius, not half the runs' distance
    for v in (1.8 * radius, 2.2 * radius):
        cad = _Cad(spec, (0.4, v, 0.0), 1, seed=8)
        fit = fc.fit_links(cad.mats, cad.centres)
        assert fit.ok and fit.radius == pytest.approx(radius, rel=1e-9) and fit.moving[1] == pytest.approx(v)


def test_fit_links_odd_sets_of_links():
    """Three kinds by turns; end pieces of their own; mirrored link meshes; every other link turned end for end."""
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    pose, other = (0.4, 2 * radius, 0.0), (0.15, 2 * radius, 0.0)

    def check(mats, centres, types, at_other, exact=True):
        fit = fc.fit_links(mats, centres, types)
        assert fit.ok and fit.links == links
        assert fit.pitch == pytest.approx(pitch, rel=1e-9) and fit.radius == pytest.approx(radius, rel=1e-9)
        if exact:
            assert fit.problem == "" and fit.pose_error < 1e-9
            got = fc.link_matrices(fc.chain_pins(fit.spec(), other).pins[0], fit.local, fit.frame)
            back = np.empty_like(got)
            back[fit.order] = got
            assert np.abs(back - at_other).max() < 1e-9
        return fit

    three = _Cad(spec, pose, 3, seed=3)
    check(three.mats, three.centres, three.types, three.at(other)[0])
    one = _Cad(spec, pose, 1, seed=3)
    ends = one.types.copy()
    ends[0], ends[-1] = 5, 6                             # an end piece at each end, each a mesh of its own
    check(one.mats, one.centres, ends, one.at(other)[0])
    mirror = np.diag([1.0, 1.0, -1.0, 1.0])
    two = _Cad(spec, pose, 2, seed=3)
    mats, moved = two.mats.copy(), two.at(other)[0]
    mats[1::2], moved[1::2] = mats[1::2] @ mirror, moved[1::2] @ mirror      # one kind is a mirrored mesh
    check(mats, two.centres, two.types, moved)
    # one mesh, every other link turned end for end about its own middle (as a pattern of links often is)
    own = one.own[0]
    half = np.eye(4)
    half[0, 3] = 0.5 * pitch
    about = np.linalg.inv(own) @ half @ np.diag([-1.0, -1.0, 1.0, 1.0]) @ np.linalg.inv(half) @ own
    mats, moved = one.mats.copy(), one.at(other)[0]
    mats[1::2], moved[1::2] = mats[1::2] @ about, moved[1::2] @ about
    check(mats, one.centres, None, moved)
    # one mesh, every other one a mirrored copy: the pins cannot be told, the links go by their centres (a note)
    mats = one.mats.copy()
    mats[1::2] = mats[1::2] @ mirror
    fit = check(mats, one.centres, None, None, exact=False)
    assert "centres" in fit.problem


def test_fit_links_with_noise_of_a_hundredth_of_a_mm():
    """One kind of link, positions off by 0.01 mm (random): pitch and radius good to a few 1e-4."""
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    pitch_err, radius_err, pose = [], [], []
    for seed in range(25):
        cad = _Cad(spec, (0.413, 2 * radius, 0.0), 1, seed=seed)
        rng = np.random.default_rng(100 + seed)
        mats = cad.mats.copy()
        mats[:, :3, 3] += rng.normal(size=(links, 3)) * 1e-5
        fit = fc.fit_links(mats, cad.centres + rng.normal(size=(links, 3)) * 1e-5)
        assert fit.ok and fit.links == links and fit.mode == "STRAIGHT"
        pitch_err.append(abs(fit.pitch / pitch - 1))
        radius_err.append(abs(fit.radius / radius - 1))
        pose.append(fit.pose_error)
    _say("fit_links, 0.01 mm noise, one kind: pitch / radius error (relative), pose error (mm), worst of 25",
         max(pitch_err), max(radius_err), 1e3 * max(pose))
    assert max(pitch_err) < 5e-4 and max(radius_err) < 2e-3 and max(pose) < 0.3e-3


def _fits_with_rounding(kinds, u, digits, count=40):
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    out = []
    for seed in range(count):
        cad = _Cad(spec, (u, 2 * radius, 0.0), kinds, seed=seed)
        out.append(fc.fit_links(np.round(cad.mats, digits), np.round(cad.centres, digits), cad.types))
    return out, radius


def test_fit_links_with_rounded_numbers_one_kind():
    """Matrices rounded to 1e-7 m (0.1 um), as an exported file has them: one kind of link."""
    for u in (0.40, 0.413):
        fits, radius = _fits_with_rounding(1, u, 7)
        assert all(f.ok for f in fits)
        worst = max(abs(f.radius / radius - 1) for f in fits)
        _say("fit_links, numbers rounded to 1e-7 m, one kind, u=%g: radius error, worst of 40" % u, worst)
        assert worst < 1e-4 and max(f.pose_error for f in fits) < 1e-5


@pytest.mark.xfail(strict=False, reason="BUG: fit_links reads the wrong bend radius from a chain of two kinds of "
                   "link (inner / outer by turns) drawn symmetrically (moving end a whole number of pitches from "
                   "the fixed end) as soon as its numbers are rounded at all: rounded to 1e-8 m, 5 of 40 chains "
                   "come back with radius 132 mm instead of 80 (+65 %), mode GLIDE, pose_error 105 mm, ok=True and "
                   "no note (1e-7 m: 2 of 40; 1e-6 m: 3; 1 um of random noise: 5; one kind of link rounded to "
                   "1e-5 m: 3 of 40). _bend_turn takes 'the angle two or more pins agree on' at the tightest "
                   "tolerance that gives two votes: the two pins where the chain goes onto and off the bend turn by "
                   "the same (smaller) angle and agree to 1e-6, the pins in the bend differ by 1e-4 between the two "
                   "kinds – so the two transition pins win against five bend pins.")
def test_fit_links_with_rounded_numbers_two_kinds_drawn_symmetrically():
    fits, radius = _fits_with_rounding(2, 0.40, 8)
    wrong = [round(f.radius, 4) for f in fits if abs(f.radius / radius - 1) > 0.01]
    _say("fit_links, two kinds, symmetric pose, rounded to 1e-8 m: chains with the radius more than 1 % off",
         "%d of %d" % (len(wrong), len(fits)), wrong[:5])
    assert not wrong


def test_fit_links_two_kinds_not_drawn_symmetrically_survives_rounding():
    fits, radius = _fits_with_rounding(2, 0.413, 7)
    assert all(f.ok for f in fits)
    assert max(abs(f.radius / radius - 1) for f in fits) < 1e-3


def test_fit_links_says_what_is_not_a_chain():
    pitch, links, radius = 0.04, 36, 0.08
    spec = fc.ChainSpec(pitch, links, radius)
    cad = _Cad(spec, (0.4, 2 * radius, 0.0), 1, seed=9)
    # drawn straight: it must say so, and still give the pitch and the count
    straight = np.stack([np.arange(links + 1) * pitch, np.zeros(links + 1), np.zeros(links + 1)], axis=1)
    mats = _rigid(np.random.default_rng(1), 1.0) @ _pin_frames(straight)
    fit = fc.fit_links(mats)
    assert not fit.ok and "straight" in fit.problem and "radius" in fit.problem
    assert fit.pitch == pytest.approx(pitch) and fit.links == links
    # three links only
    for k in (0, 1, 2, 3):
        fit = fc.fit_links(cad.mats[:k], cad.centres[:k])
        assert not fit.ok and "at least 4 links" in fit.problem
    # every link given twice; one link given twice
    twice = fc.fit_links(np.concatenate([cad.mats, cad.mats]), np.concatenate([cad.centres, cad.centres]))
    assert not twice.ok and twice.problem
    once = fc.fit_links(np.concatenate([cad.mats, cad.mats[5:6]]), np.concatenate([cad.centres, cad.centres[5:6]]))
    assert not once.ok and once.problem
    # a link missing in the middle; two chains picked together; places that are no numbers; all in one place
    keep = np.delete(np.arange(links), 10)
    assert not fc.fit_links(cad.mats[keep], cad.centres[keep]).ok
    other = cad.mats.copy()
    other[:, :3, 3] += cad.world[:3, 2] * 0.5
    both = fc.fit_links(np.concatenate([cad.mats, other]),
                        np.concatenate([cad.centres, cad.centres + cad.world[:3, 2] * 0.5]))
    assert not both.ok and "not one chain" in both.problem
    assert not fc.fit_links(np.full((6, 4, 4), np.nan)).ok
    assert not fc.fit_links(np.tile(np.eye(4), (8, 1, 1))).ok
    for fit in (twice, once, both):
        assert fit.problem[0].isupper() and fit.problem.endswith(".") and "Traceback" not in fit.problem
    with pytest.raises(ValueError):
        fc.fit_links(np.zeros((4, 3, 3)))
    # the fit is the same whatever order the links are given in
    perm = np.random.default_rng(4).permutation(links)
    a, b = fc.fit_links(cad.mats, cad.centres), fc.fit_links(cad.mats[perm], cad.centres[perm])
    assert np.allclose(a.frame, b.frame) and np.allclose(a.pins, b.pins) and np.array_equal(perm[b.order], a.order)


def _u_band(radius, height, width, low, high, arc=24):
    """The mesh points of a chain drawn as one solid: a band ``height`` thick and ``width`` wide, a run ``low``
    long at v = 0 and one ``high`` long at v = 2 radius, joined by half a ring round (0, radius)."""
    outer, inner = radius + 0.5 * height, radius - 0.5 * height
    th = np.linspace(-0.5 * np.pi, 0.5 * np.pi, arc + 1)
    ring = lambda r: np.stack([r * np.cos(th), radius + r * np.sin(th)], axis=1)              # noqa: E731
    outline = np.concatenate([[[-low, -0.5 * height]], ring(outer), [[-high, 2 * radius + 0.5 * height]],
                              [[-high, 2 * radius - 0.5 * height]], ring(inner)[::-1], [[-low, 0.5 * height]]])
    return np.concatenate([np.column_stack([outline, np.full(len(outline), s * 0.5 * width)]) for s in (-1, 1)])


def test_fit_solid_reads_a_u_band():
    rng = np.random.default_rng(6)
    for radius, height, width, low, high in ((0.08, 0.03, 0.06, 0.6, 0.3), (0.08, 0.03, 0.06, 0.3, 0.6),
                                             (0.15, 0.05, 0.10, 1.0, 0.2), (0.05, 0.02, 0.20, 0.3, 0.3)):
        pts = _u_band(radius, height, width, low, high)
        world = _rigid(rng, 2.0)
        placed = pts @ world[:3, :3].T + world[:3, 3]
        fit = fc.fit_solid(placed[rng.permutation(len(placed))])
        assert fit.ok and fit.problem == "", fit.problem
        assert fit.radius == pytest.approx(radius, rel=1e-6) and fit.height == pytest.approx(height, rel=1e-6)
        assert fit.width == pytest.approx(width, rel=1e-6) and fit.residual < 1e-9
        assert fit.mode == "STRAIGHT" and len(fit.local) == 0
        # the fixed end: the end of the longer run, in the middle of the band's thickness
        fixed_low = low >= high
        fixed = np.array([-max(low, high), 0.0 if fixed_low else 2 * radius, 0.0])
        assert np.allclose(fit.frame[:3, 3], world[:3, :3] @ fixed + world[:3, 3], atol=1e-9)
        assert np.allclose(fit.frame[:3, 0], world[:3, 0], atol=1e-9)                          # u: towards the bend
        assert np.allclose(fit.frame[:3, 1], world[:3, 1] * (1 if fixed_low else -1), atol=1e-9)
        assert np.linalg.det(fit.frame[:3, :3]) == pytest.approx(1.0)
        assert np.allclose(fit.moving, (abs(low - high), 2 * radius, 0.0), atol=1e-9)
        # as many links as the band is long, of a pitch that suits the bend
        assert fit.pitch == pytest.approx(min(1.6 * height, radius / 0.75), rel=1e-6)
        assert abs(fit.links * fit.pitch - (low + high + math.pi * radius)) <= 0.5 * fit.pitch + 1e-9
        assert fit.pins.shape == (fit.links + 1, 3)
        assert np.allclose(np.linalg.norm(np.diff(fit.pins, axis=0), axis=1), fit.pitch)
        assert np.allclose(fit.pins[0], fit.frame[:3, 3])
        # the drawn chain stays inside the band (its pins within half a thickness + the chords' sag of the middle)
        own = (fit.pins - world[:3, 3]) @ world[:3, :3]
        assert np.abs(own[:, 2]).max() < 1e-9
        assert own[:, 0].max() < radius + 0.5 * height and own[:, 1].min() > -0.5 * height
        chosen = fc.fit_solid(placed, pitch=0.04)
        assert chosen.ok and chosen.pitch == 0.04
        assert chosen.links == round((low + high + math.pi * radius) / 0.04)
    # what is no U band
    assert not fc.fit_solid(_u_band(0.08, 0.03, 0.06, 0.02, 0.02)).ok                          # runs too short
    assert not fc.fit_solid(pts, pitch=10.0).ok                                    # a link longer than the bend
    block = np.array([(x, y, z) for x in (0, 1.0) for y in (0, 0.2) for z in (0, 0.1)] * 2)
    for bad in (block, rng.uniform(-1, 1, (200, 3)), np.zeros((5, 3)), np.full((30, 3), np.nan), np.ones((30, 3)),
                np.outer(np.linspace(0, 1, 40), (1, 2, 3))):
        fit = fc.fit_solid(bad)
        assert not fit.ok and fit.problem.endswith(".") and len(fit.problem) > 20


# =====================================================================================================================
# A TUBE MESH'S CENTRELINE
# =====================================================================================================================

def _transport(path):
    """Tangents and a pair of normals carried along a polyline without twist."""
    tan = _unit(np.gradient(path, axis=0))
    n = _unit(np.cross(tan[0], np.eye(3)[int(np.argmin(np.abs(tan[0])))]))
    normals = np.empty_like(path)
    for i in range(len(path)):
        n = _unit(n - tan[i] * float(n @ tan[i]))
        normals[i] = n
    return tan, normals, np.cross(tan, normals)


def _sweep(path, radius, sides=16, bore=0.0, seams=False, profile=None, turned=0.1):
    """A closed tube mesh along ``path`` (m, 3): rings of ``sides`` vertices; flat end faces (a fan to the middle,
    or a ring between the walls of a tube with a ``bore``). ``profile`` (m,) or (m, sides): a radius per ring or per
    vertex (a flange, a hexagon). ``seams``: as a CAD importer leaves it – every ring's first vertex twice and the
    end faces with their own copies of the rim. All triangles face outwards. Returns verts, tris."""
    path = np.asarray(path, dtype=float)
    m = len(path)
    _tan, n1, n2 = _transport(path)
    per = sides + (1 if seams else 0)
    ang = turned + 2 * np.pi * np.arange(per) / sides
    circle = np.cos(ang)[None, :, None] * n1[:, None, :] + np.sin(ang)[None, :, None] * n2[:, None, :]
    rad = np.full((m, sides), float(radius)) if profile is None else np.broadcast_to(
        np.asarray(profile, dtype=float).reshape(m, -1), (m, sides))
    rad = rad[:, np.arange(per) % sides]
    verts = [(path[:, None, :] + rad[:, :, None] * circle).reshape(-1, 3)]
    tris = []

    def wall(base, inside):
        for i in range(m - 1):
            for j in range(sides):
                a, b = base + i * per + j, base + i * per + (j + 1) % per
                c, d = a + per, b + per
                tris.extend([(a, c, b), (b, c, d)] if inside else [(a, b, c), (b, d, c)])

    wall(0, False)
    count = m * per
    if bore > 0.0:
        verts.append((path[:, None, :] + bore * circle).reshape(-1, 3))
        wall(count, True)
    for end, ring in ((0, 0), (1, m - 1)):
        rim = ring * per + np.arange(per)
        base = sum(len(v) for v in verts)
        if seams:
            verts.append(verts[0][rim].copy())
            rim = base + np.arange(per)
            base += per
        if bore > 0.0:
            inner = count + ring * per + np.arange(per)
            if seams:
                verts.append(verts[1][ring * per + np.arange(per)].copy())
                inner = base + np.arange(per)
            for j in range(sides):
                a, b, c, d = rim[j], rim[(j + 1) % per], inner[j], inner[(j + 1) % per]
                tris.extend([(a, c, b), (b, c, d)] if end == 0 else [(a, b, c), (b, d, c)])
        else:
            verts.append(path[ring][None, :])
            for j in range(sides):
                a, b = rim[j], rim[(j + 1) % per]
                tris.append((base, b, a) if end == 0 else (base, a, b))
    return np.concatenate(verts), np.array(tris, dtype=np.int64)


def _path(pieces, per_unit=400.0):
    """A path from ("line", length) and ("arc", radius, angle, roll) pieces (roll: the bending plane is turned
    about the tangent first). Returns dense points, the exact length, the directions at the two ends."""
    pos, tan, nor = np.zeros(3), np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
    pts, total = [pos.copy()], 0.0
    for piece in pieces:
        if piece[0] == "line":
            for s in np.linspace(0, piece[1], max(int(piece[1] * per_unit), 2) + 1)[1:]:
                pts.append(pos + s * tan)
            pos = pos + piece[1] * tan
            total += piece[1]
        else:
            _name, r, angle, roll = piece
            nor = math.cos(roll) * nor + math.sin(roll) * np.cross(tan, nor)
            centre, t0, n0 = pos + r * nor, tan.copy(), nor.copy()
            for a in np.linspace(0, angle, max(int(r * angle * per_unit), 8) + 1)[1:]:
                pts.append(centre + r * (math.sin(a) * t0 - math.cos(a) * n0))
            pos = centre + r * (math.sin(angle) * t0 - math.cos(angle) * n0)
            tan, nor = math.cos(angle) * t0 + math.sin(angle) * n0, -math.sin(angle) * t0 + math.cos(angle) * n0
            total += r * angle
    return np.array(pts), total, np.array([1.0, 0.0, 0.0]), tan


def _helix(radius, rise, turns, m=320):
    a = np.linspace(0, 2 * np.pi * turns, m)
    k = math.hypot(2 * np.pi * radius, rise)
    c = 2 * np.pi * radius
    tangent = lambda x: np.array([-c * math.sin(x), c * math.cos(x), rise]) / k               # noqa: E731
    return (np.stack([radius * np.cos(a), radius * np.sin(a), rise * a / (2 * np.pi)], axis=1), turns * k,
            tangent(a[0]), tangent(a[-1]))


def _off_path(points, path):
    """The largest distance from ``points`` to the polyline ``path``."""
    a, ab = path[:-1], path[1:] - path[:-1]
    l2 = (ab * ab).sum(axis=1)
    worst = 0.0
    for p in points:
        f = np.clip(((p - a) * ab).sum(axis=1) / l2, 0.0, 1.0)
        worst = max(worst, float(np.sqrt((((a + f[:, None] * ab) - p) ** 2).sum(axis=1).min())))
    return worst


R_TUBE = 0.01
TUBES = {
    "elbow 90": lambda: _path([("line", 0.1), ("arc", 0.08, math.pi / 2, 0.0), ("line", 0.1)]),
    "U-bend 180": lambda: _path([("line", 0.15), ("arc", 0.06, math.pi, 0.0), ("line", 0.15)]),
    "two bends in two planes": lambda: _path([("line", 0.1), ("arc", 0.05, math.pi / 2, 0.0), ("line", 0.08),
                                              ("arc", 0.05, math.pi / 2, math.pi / 2), ("line", 0.1)]),
    "very short, straight (4 diameters)": lambda: _path([("line", 8 * R_TUBE)]),
    "very short, bent (4.6 diameters)": lambda: _path([("line", 0.02), ("arc", 0.05, 1.0, 0.0), ("line", 0.022)]),
    "long (150 diameters)": lambda: _path([("line", 1.0), ("arc", 0.2, math.pi / 2, 0.0), ("line", 1.0),
                                           ("arc", 0.15, math.pi / 3, 1.0), ("line", 0.529)], per_unit=150.0),
    "coiled, 1.5 turns of a helix (turns 4 radii apart)": lambda: _helix(0.05, 0.06, 1.5),
    "coiled tightly (turns 1 radius apart)": lambda: _helix(0.05, 0.03, 1.5),
    "hairpin, legs half a diameter apart": lambda: _path([("line", 0.15), ("arc", 0.0125, math.pi, 0.0),
                                                          ("line", 0.15)], per_unit=1500.0),
}
CLOSE = ("coiled tightly", "hairpin")                    # tubes that pass close to themselves: solid ones only
TUBE_CASES = [(name, sides, kind) for name in TUBES for sides, kind in
              ((8, "solid"), (16, "bore"), (32, "seams"), (12, "bore+seams"))
              if not (name.startswith("long") and sides == 32) and not (name.startswith(CLOSE) and "bore" in kind)]


def _tube_mesh(name, sides, kind, seed=0, radius=R_TUBE, **more):
    """One of the tubes, placed anywhere, its vertices and triangles shuffled. Returns verts, tris and the truth
    (path, length, end directions) in the same place."""
    path, length, d0, d1 = TUBES[name]()
    verts, tris = _sweep(path, radius, sides, bore=0.6 * radius if "bore" in kind else 0.0, seams="seams" in kind,
                         **more)
    rng = np.random.default_rng(seed)
    world = _rigid(rng, 1.0)
    verts, path = verts @ world[:3, :3].T + world[:3, 3], path @ world[:3, :3].T + world[:3, 3]
    order = rng.permutation(len(verts))
    new = np.argsort(order)
    return verts[order], new[tris][rng.permutation(len(tris))], path, length, world[:3, :3] @ d0, world[:3, :3] @ d1


def _check_tube(tube, path, length, d0, d1, radius, n=65, line=0.02, ends=0.03):
    assert tube.ok and tube.problem == "", tube.problem
    assert tube.points.shape == (n, 3) and np.isfinite(tube.points).all()
    e0, e1 = path[0], path[-1]
    if np.linalg.norm(tube.points[0] - e0) > np.linalg.norm(tube.points[0] - e1):     # the module's end 0 is my end 1
        e0, e1, d0, d1 = e1, e0, -d1, -d0
    # end 0 is the end with the smaller x (then y, then z)
    assert tuple(tube.points[0]) < tuple(tube.points[-1])
    facts = dict(line=_off_path(tube.points, path) / radius, length=tube.length / length - 1,
                 radius=tube.radius / radius - 1,
                 ends=max(np.linalg.norm(tube.points[0] - e0), np.linalg.norm(tube.points[-1] - e1)) / radius,
                 dirs=max(float(_angle_deg(tube.t0, d0)), float(_angle_deg(tube.t1, d1))))
    assert facts["line"] < line, facts                   # the centreline: within 2 % of the radius
    assert abs(facts["length"]) < 0.005, facts           # 0.5 %
    assert abs(facts["radius"]) < 0.02, facts            # 2 %
    assert facts["ends"] < ends, facts                   # 3 % of the radius (0.3 mm on a 20 mm hose)
    assert facts["dirs"] < 1.0, facts                    # 1 degree
    assert np.linalg.norm(tube.t0) == pytest.approx(1.0) and np.linalg.norm(tube.t1) == pytest.approx(1.0)
    step = np.linalg.norm(np.diff(tube.points, axis=0), axis=1)
    assert step.max() / step.min() < 1.02                # equally spaced
    assert step.sum() <= tube.length * (1 + 1e-9) and step.sum() > 0.995 * tube.length
    return facts


@pytest.mark.parametrize("name,sides,kind", TUBE_CASES)
def test_tube_centreline_is_accurate(name, sides, kind):
    verts, tris, path, length, d0, d1 = _tube_mesh(name, sides, kind, seed=sides)
    tube = ff.tube_centreline(verts, tris)
    # a coil: the centreline is 0.5-2.2 % of the radius off (more with a bore), everything else under 1 %
    facts = _check_tube(tube, path, length, d0, d1, R_TUBE, line=0.03 if name.startswith("coiled") else 0.01)
    _say("tube %s, %d sides, %s (%d triangles)" % (name, sides, kind, len(tris)),
         "line %.2f %% r" % (100 * facts["line"]), "length %+.3f %%" % (100 * facts["length"]),
         "radius %+.2f %%" % (100 * facts["radius"]), "ends %.2f %% r" % (100 * facts["ends"]),
         "directions %.2f deg" % facts["dirs"])


@pytest.mark.xfail(strict=False, reason="BUG: a hollow hose (a tube with a bore) that passes close to itself is "
                   "misread. A hairpin whose legs are 1 radius apart (bore 0.6 r): ok=True with HALF the length "
                   "(-49.4 %) – one leg is taken for the hose; legs 0.5 r apart: refused ('could not be read'). A "
                   "hollow coil with its turns up to 1.5-2 radii apart: refused, and whether it is depends on how "
                   "the part is turned in space (the same coil is read at one angle and refused at another). The "
                   "same shapes as solids are read to 0.03 %. The ends of a tube with a bore are looked for with the "
                   "vertices lumped in boxes along the X/Y/Z axes, about 1.6 radii wide: two walls of the hose that "
                   "are nearer than that fall into one box.")
@pytest.mark.parametrize("name,gap", [("hairpin", 1.0), ("hairpin", 0.5), ("coil", 1.0), ("coil", 1.5)])
def test_tube_with_a_bore_close_to_itself(name, gap):
    r = R_TUBE
    if name == "hairpin":
        path, length, d0, d1 = _path([("line", 0.15), ("arc", r + 0.5 * gap * r, math.pi, 0.0), ("line", 0.15)],
                                     per_unit=1500.0)
    else:
        path, length, d0, d1 = _helix(0.05, (2 + gap) * r, 1.5)
    rng = np.random.default_rng(16)
    for turn in range(3):                                # as drawn, and turned in space twice
        world = np.eye(4) if turn == 0 else _rigid(rng)
        verts, tris = _sweep(path @ world[:3, :3].T, r, 16, bore=0.6 * r)
        tube = ff.tube_centreline(verts, tris)
        assert tube.ok, "turn %d: %s" % (turn, tube.problem)
        assert tube.length == pytest.approx(length, rel=0.005), "turn %d: length %+.1f %%" % (
            turn, 100 * (tube.length / length - 1))


def test_tube_with_a_flange_a_hexagon_and_ferrules():
    path, length, d0, d1 = TUBES["elbow 90"]()
    path = np.array([path[0] + (path[1] - path[0]) * 0] + list(path))[1:]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    m, sides = len(path), 12
    flange = np.where(s < 0.03, 1.6 * R_TUBE, R_TUBE)                                         # a collar on end 0
    ferrules = np.where((s < 0.03) | (s > length - 0.03), 1.3 * R_TUBE, R_TUBE)               # both ends
    hexagon = np.full((m, sides), R_TUBE)                                                     # a hex nut on end 1:
    nut = s > length - 0.025                                                                  # 12 vertices, every
    hexagon[nut] = 1.5 * R_TUBE * np.where(np.arange(sides) % 2 == 0, 1.0, math.cos(math.pi / 6))   # other on a flat
    for label, profile in (("flange", flange), ("ferrules", ferrules), ("hexagon", hexagon)):
        for bore in (0.0, 0.6 * R_TUBE):
            verts, tris = _sweep(path, R_TUBE, sides, bore=bore, profile=profile)
            tube = ff.tube_centreline(verts, tris)
            facts = _check_tube(tube, path, length, d0, d1, R_TUBE)
            _say("tube with %s%s" % (label, ", bore" if bore else ""), "line %.2f %% r" % (100 * facts["line"]),
                 "length %+.3f %%" % (100 * facts["length"]), "radius %+.2f %%" % (100 * facts["radius"]))


def test_tube_is_the_same_shuffled_doubled_scaled_and_far_away():
    path, length, d0, d1 = TUBES["two bends in two planes"]()
    verts, tris = _sweep(path, R_TUBE, 16, bore=0.006)
    base = ff.tube_centreline(verts, tris)
    _check_tube(base, path, length, d0, d1, R_TUBE)
    rng = np.random.default_rng(3)
    order = rng.permutation(len(verts))
    shuffled = ff.tube_centreline(verts[order], np.argsort(order)[tris][rng.permutation(len(tris))])
    worst = float(np.abs(shuffled.points - base.points).max())
    assert worst < 1e-12 and shuffled.radius == pytest.approx(base.radius, rel=1e-12)
    assert shuffled.length == pytest.approx(base.length, rel=1e-12)
    _say("tube, vertices and triangles shuffled: centreline moved by (m)", worst)
    # the same answer again (no state), the inputs untouched
    keep_v, keep_t = verts.copy(), tris.copy()
    again = ff.tube_centreline(verts, tris)
    assert np.array_equal(again.points, base.points) and np.array_equal(verts, keep_v) and np.array_equal(tris, keep_t)
    # seams: every vertex twice, triangles given twice, corners named from another one, slivers of no area added
    seams_v, seams_t = _sweep(path, R_TUBE, 16, bore=0.006, seams=True)
    for v, t in ((seams_v, seams_t), (np.concatenate([verts, verts]), np.concatenate([tris, tris + len(verts)])),
                 (verts, np.concatenate([tris, tris])), (verts, tris[:, [1, 2, 0]]),
                 (verts, np.concatenate([tris, np.stack([tris[:30, 0], tris[:30, 0], tris[:30, 1]], axis=1)])),
                 (verts.astype(np.float32).astype(np.float64), tris.astype(np.int32)), (verts.tolist(), tris.tolist())):
        other = ff.tube_centreline(v, t)
        assert other.ok and np.abs(other.points - base.points).max() < 1e-6 * R_TUBE * 100
        assert other.radius == pytest.approx(base.radius, rel=1e-5)
    # inside out (every triangle facing in), and facing at random
    inside = ff.tube_centreline(verts, tris[:, [0, 2, 1]])
    assert inside.ok and np.abs(inside.points - base.points).max() < 1e-9
    assert inside.radius == pytest.approx(base.radius)
    flip = rng.random(len(tris)) < 0.5
    mixed = tris.copy()
    mixed[flip] = mixed[flip][:, [0, 2, 1]]
    anyhow = ff.tube_centreline(verts, mixed)
    assert anyhow.ok and anyhow.radius == pytest.approx(base.radius, rel=1e-6)
    assert np.abs(anyhow.points - base.points).max() < 0.01 * R_TUBE
    # in mm; 50 m from the origin; in mm 5 km from the origin
    mm = ff.tube_centreline(verts * 1000, tris)
    assert mm.ok and np.abs(mm.points / 1000 - base.points).max() < 1e-12
    assert mm.radius == pytest.approx(1000 * base.radius) and mm.length == pytest.approx(1000 * base.length)
    far = ff.tube_centreline(verts + [50.0, -30.0, 20.0], tris)
    assert far.ok and np.abs(far.points - [50.0, -30.0, 20.0] - base.points).max() < 1e-9
    assert np.allclose(far.t0, base.t0, atol=1e-9)
    out = ff.tube_centreline(verts * 1000 + [5e6, 0, 0], tris)
    assert out.ok and np.abs(out.points - [5e6, 0, 0] - 1000 * base.points).max() < 1e-5
    # other numbers of points
    for n in (2, 3, 17, 500):
        t = ff.tube_centreline(verts, tris, n)
        assert t.points.shape == (n, 3) and np.allclose(t.points[[0, -1]], base.points[[0, -1]])
        assert t.length == pytest.approx(base.length)
    # a crumb beside the hose (a sliver the importer left) is left out; a vertex that is no number too
    crumb_v, crumb_t = _sweep(np.linspace((0, 0.3, 0), (0.0005, 0.3, 0), 3), 0.0002, 6)
    with_crumb = ff.tube_centreline(np.concatenate([verts, crumb_v]), np.concatenate([tris, crumb_t + len(verts)]))
    assert with_crumb.ok and np.abs(with_crumb.points - base.points).max() < 1e-9
    holed = verts.copy()
    holed[7] = np.nan
    assert ff.tube_centreline(holed, tris).ok


def _box(sx, sy, sz, div=1):
    verts, tris = [], []

    def face(o, a, b):
        base = len(verts)
        for i in range(div + 1):
            for j in range(div + 1):
                verts.append(o + a * i / div + b * j / div)
        for i in range(div):
            for j in range(div):
                p = base + i * (div + 1) + j
                tris.extend([(p, p + div + 1, p + 1), (p + 1, p + div + 1, p + div + 2)])

    x, y, z, o = np.array([sx, 0, 0.0]), np.array([0, sy, 0.0]), np.array([0, 0, sz]), np.zeros(3)
    face(o, y, x), face(z, x, y), face(o, x, z), face(y, z, x), face(o, z, y), face(x, y, z)
    return np.array(verts), np.array(tris)


def _sphere(r, n=16):
    verts = [(r * math.sin(math.pi * i / n) * math.cos(math.pi * j / n),
              r * math.sin(math.pi * i / n) * math.sin(math.pi * j / n), r * math.cos(math.pi * i / n))
             for i in range(n + 1) for j in range(2 * n)]
    tris = []
    for i in range(n):
        for j in range(2 * n):
            a, b = i * 2 * n + j, i * 2 * n + (j + 1) % (2 * n)
            tris.extend([(a, a + 2 * n, b), (b, a + 2 * n, b + 2 * n)])
    return np.array(verts), np.array(tris)


def _ring(big, small, n=48, m=12):
    verts = [((big + small * math.cos(2 * math.pi * j / m)) * math.cos(2 * math.pi * i / n),
              (big + small * math.cos(2 * math.pi * j / m)) * math.sin(2 * math.pi * i / n),
              small * math.sin(2 * math.pi * j / m)) for i in range(n) for j in range(m)]
    tris = []
    for i in range(n):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            c, d = ((i + 1) % n) * m + j, ((i + 1) % n) * m + (j + 1) % m
            tris.extend([(a, c, b), (b, c, d)])
    return np.array(verts), np.array(tris)


def _two_tubes():
    path, *_ = TUBES["elbow 90"]()
    v, t = _sweep(path, R_TUBE, 12)
    return np.concatenate([v, v + [0, 0.5, 0]]), np.concatenate([t, t + len(v)])


NOT_TUBES = {
    "a cube": lambda: _box(1.0, 1.0, 1.0, 4),
    "a square bar": lambda: _box(1.0, 0.05, 0.05, 1),
    "a square bar, fine mesh": lambda: _box(1.0, 0.05, 0.05, 8),
    "a flat bar 1000 x 100 x 20, fine mesh": lambda: _box(1.0, 0.1, 0.02, 4),
    "a plate": lambda: _box(1.0, 1.0, 0.02, 4),
    "a short block": lambda: _box(0.3, 0.1, 0.05, 2),
    "a ball": lambda: _sphere(0.1),
    "a ring": lambda: _ring(0.1, 0.01),
    "a big thin ring": lambda: _ring(1.0, 0.01, n=200),
    "a fat ring": lambda: _ring(0.03, 0.01),
    "two separate tubes": _two_tubes,
    "nothing": lambda: (np.zeros((0, 3)), np.zeros((0, 3), dtype=int)),
    "a stub 2 diameters long": lambda: _sweep(np.linspace((0, 0, 0), (0.04, 0, 0), 20), R_TUBE, 16),
    "a triangle bar": lambda: _sweep(np.linspace((0, 0, 0), (0.3, 0, 0), 40), R_TUBE, 3),
}


@pytest.mark.parametrize("name", list(NOT_TUBES))
def test_tube_refuses_what_is_no_hose_in_plain_words(name):
    tube = ff.tube_centreline(*NOT_TUBES[name]())
    assert not tube.ok, (name, tube.radius, tube.length)
    assert tube.problem.startswith("The part") and tube.problem.endswith(".") and len(tube.problem) > 25
    assert not any(word in tube.problem for word in ("Error", "Traceback", "array", "nan", "index", "_"))
    assert tube.points.shape == (0, 3) and tube.radius == 0.0 and tube.length == 0.0
    _say("no hose: %s" % name, tube.problem)


@pytest.mark.xfail(strict=False, reason="BUG: a rectangular bar passes as a hose. A box 1000 x 200 x 100 mm (12 "
                   "triangles, or meshed finely) comes back ok=True, radius 111.8 mm (half its diagonal), length "
                   "1000 mm; so does every bar with sides 1.6 : 1 … 5 : 1 as a CAD file has it (12 triangles), e.g. "
                   "a flat bar 1000 x 100 x 20. Only the square (1 : 1 … 1.4 : 1) is 'not round'. The roundness "
                   "test (26 % of the outline beyond 90 % of the largest radius) is met by the two short sides of "
                   "a rectangle.")
@pytest.mark.parametrize("size,div", [((1.0, 0.2, 0.1), 1), ((1.0, 0.2, 0.1), 6), ((1.0, 0.1, 0.02), 1),
                                      ((1.0, 0.08, 0.05), 1), ((3.0, 0.1, 0.05), 2)])
def test_tube_refuses_a_rectangular_bar(size, div):
    tube = ff.tube_centreline(*_box(*size, div))
    assert not tube.ok, "taken for a hose of radius %.4f, length %.3f" % (tube.radius, tube.length)


def test_tube_never_raises():
    path, *_ = TUBES["elbow 90"]()
    verts, tris = _sweep(path, R_TUBE, 12)
    rng = np.random.default_rng(9)
    junk = [
        (None, None), ("hose", "tube"), (verts, None), (verts[:, :2], tris), (verts, tris[:, :2]),
        (verts, tris + 10 ** 6), (verts, -tris - 1), (verts, tris.astype(float)), (verts, tris * 0),
        (np.full_like(verts, np.nan), tris), (np.full_like(verts, np.inf), tris), (np.zeros_like(verts), tris),
        (verts * 0 + [1.0, 2.0, 3.0], tris), (verts[:3], tris[:3]), (verts, tris[:3]),
        (rng.normal(size=(50, 3)), rng.integers(0, 50, (200, 3))),                      # triangle soup
        (rng.normal(size=(500, 3)) * [1, 0.01, 0.01], rng.integers(0, 500, (2000, 3))),
        (verts * 1e-9, tris), (verts * 1e9, tris), (verts + 1e12, tris),
        (verts[:, [0, 1]].repeat(2, axis=1)[:, :3], tris),                             # flat: every point in a plane
        (np.linspace((0, 0, 0), (1, 0, 0), len(verts)), tris),                          # every point on a line
        (verts, np.concatenate([tris, [[0, 1, 10 ** 9]]])), (verts.reshape(-1), tris.reshape(-1)),
        (verts, tris[: (len(path) - 1) * 24]),                                         # the wall alone, ends open
        (verts, tris[::2]), (verts, tris[rng.random(len(tris)) < 0.7]),                 # holes
    ]
    for n in (65, 0, -5, 1):
        for v, t in junk:
            with np.errstate(all="ignore"):
                tube = ff.tube_centreline(v, t, n)
            assert isinstance(tube.ok, bool) and isinstance(tube.problem, str)
            assert tube.ok or tube.problem.startswith("The part")
            assert not tube.ok or (np.isfinite(tube.points).all() and tube.radius > 0 and tube.length > 0)
    # a tube whose ends are open (a surface, no end faces) is still a hose
    open_tube = ff.tube_centreline(verts, tris[: (len(path) - 1) * 24])
    assert open_tube.ok and open_tube.radius == pytest.approx(R_TUBE, rel=0.01)


def test_tube_speed_for_20k_triangles():
    path, length, d0, d1 = TUBES["long (150 diameters)"]()
    verts, tris = _sweep(path, R_TUBE, 24)
    assert 19000 < len(tris) < 23000
    ff.tube_centreline(verts[:200], tris[:10])
    times = []
    for _ in range(3):
        clock = time.perf_counter()
        tube = ff.tube_centreline(verts, tris)
        times.append(time.perf_counter() - clock)
    _check_tube(tube, path, length, d0, d1, R_TUBE)
    _say("tube of %d triangles: seconds (best of 3)" % len(tris), min(times))
    assert min(times) < 3.0                              # measured 0.15-0.25 s; the machine is shared
