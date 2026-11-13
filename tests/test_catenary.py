"""Task 0081: the catenary into the sea (fresing_render/core/catenary.py). No Blender.

Lengths exact as the cable pays out and the vessel moves, the two edge cases (too much cable, so tight it lifts off
its end) and the stretched case, the tangent at the hang-off continuous where the horn allows it, the steep case,
the laid length = vessel advance + what was there.
"""

import math

import numpy as np
import pytest

from fresing_render.core import catenary as C

U = np.array([-1.0, 0.0, 0.0])          # laid aft (−x)
ZB = -30.0                              # the cable's middle on the seabed


def poly_length(p):
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def dense(res, k=0, n=200001):
    lam = np.linspace(0.0, float(res["L"][k]), n)
    sub = {key: (v[k:k + 1] if isinstance(v, np.ndarray) and v.shape[:1] == res["kind"].shape else v)
           for key, v in res.items()}
    return C.points(sub, lam[None])[0]


def test_formulas():
    h, a = 33.0, 20.0
    X, s = C.span(a, h), C.suspended(a, h)
    assert s == pytest.approx(math.sqrt(h * h + 2 * a * h))
    assert X == pytest.approx(a * math.acosh(1 + h / a))
    assert float(C.a_for_span(X, h)) == pytest.approx(a, rel=1e-12)
    for X_ in (0.01, 1.0, 50.0, 5000.0):
        assert float(C.span(C.a_for_span(X_, h), h)) == pytest.approx(X_, rel=1e-10)
    bottom, top = C.tensions(a, h, 51.0)
    assert float(top - bottom) == pytest.approx(51.0 * C.G * h / 1000.0)        # T_top = T_bottom + w h
    assert C.wet_weight(0.2) == pytest.approx(51.0) and C.wet_weight(0.05) == pytest.approx(51.0 / 16)
    # 0083's numbers: 10 kN at the bottom, 500 N/m, 20–50 m deep: layback 26–39 m, 60–75° below horizontal
    for depth in (20.0, 50.0):
        aa = 10000.0 / 500.0
        X_ = float(C.span(aa, depth))
        ang = math.degrees(math.atan2(float(C.suspended(aa, depth)), aa))
        assert 20.0 < X_ < 45.0 and 55.0 < ang < 80.0


def test_length_exact_over_payout_and_vessel_motion():
    """laid + suspended = L to the last digit; the drawn line (dense) ≤ 0.1 mm per 100 m off it."""
    rng = np.random.default_rng(3)
    F = 40
    T = np.zeros((F, 3))
    T[:, 0] = rng.uniform(-1.0, 1.0, F)                  # surge / sway / heave of the hang-off
    T[:, 1] = rng.uniform(-0.5, 0.5, F)
    T[:, 2] = 3.0 + rng.uniform(-1.0, 1.0, F)
    S = np.array([-150.0, 0.0, ZB])
    L = np.linspace(165.0, 178.0, F)
    res = C.hang(T, S, U, ZB, L)
    assert (res["kind"] == C.NORMAL).all()
    assert np.abs(res["laid"] + res["suspended"] - L).max() < 1e-9
    for k in (0, F // 2, F - 1):
        p = dense(res, k)
        assert abs(poly_length(p) - L[k]) < 1e-4 * L[k] / 100.0 + 1e-6
        assert np.linalg.norm(p[0] - T[k]) < 1e-9 and np.linalg.norm(p[-1] - S) < 1e-9
        assert p[:, 2].min() >= ZB - 1e-9                                   # never below the seabed
        # the catenary's own equation from the touch-down
        tdp, a = res["tdp"][k], res["a"][k]
        hang_ = p[p[:, 2] > ZB + 1e-6]
        x = np.linalg.norm((hang_ - tdp)[:, :2], axis=1)
        assert np.abs(hang_[:, 2] - ZB - (a * np.cosh(x / a) - a)).max() < 1e-6


def test_lifts_off_its_end_keeps_the_length():
    T = np.array([[0.0, 0.0, 3.0]])
    S = np.array([-80.0, 0.0, ZB])
    h, X0 = 33.0, 80.0
    s_full = float(C.suspended(C.a_for_span(X0, h), h))
    line = math.hypot(X0, h)
    for L in (line + 0.3, 0.5 * (line + s_full), s_full - 1e-3):
        res = C.hang(T, S, U, ZB, [L])
        assert res["kind"][0] == C.LIFTED and res["laid"][0] == 0.0
        p = dense(res)
        assert poly_length(p) == pytest.approx(L, abs=1e-5)
        assert np.linalg.norm(p[-1] - S) < 1e-9 and np.linalg.norm(p[0] - T[0]) < 1e-9
    # it goes over into touching down without a jump of the departure angle
    a1 = C.hang(T, S, U, ZB, [s_full - 1e-6])["angle"][0]
    a2 = C.hang(T, S, U, ZB, [s_full + 1e-6])["angle"][0]
    assert C.hang(T, S, U, ZB, [s_full + 1e-6])["kind"][0] == C.NORMAL
    assert abs(a1 - a2) < 1e-5


def test_too_much_cable_piles_up_but_keeps_its_length():
    T = np.array([[0.0, 0.0, 3.0]])
    S = np.array([-60.0, 0.0, ZB])
    L = 60.0 + 33.0 + 25.0
    res = C.hang(T, S, U, ZB, [L])
    assert res["kind"][0] == C.PILED and res["excess"][0] == pytest.approx(25.0, abs=1e-3)
    p = dense(res)
    assert poly_length(p) == pytest.approx(L, rel=1e-5)
    assert np.linalg.norm(p[-1] - S) < 1e-9
    assert math.degrees(res["angle"][0]) > 89.0                         # hangs straight down


def test_too_short_is_said():
    T = np.array([[0.0, 0.0, 3.0]])
    S = np.array([-60.0, 0.0, ZB])
    res = C.hang(T, S, U, ZB, [50.0])
    assert res["kind"][0] == C.STRETCHED and res["excess"][0] < 0.0


def _horn(F=1):
    """A horn: radius 3.5 about −y through (0, 0, −3.5); the cable arrives on top going aft (−x)."""
    c = np.tile([0.0, 0.0, -3.5], (F, 1))
    ax = np.tile([0.0, 1.0, 0.0], (F, 1))
    arrive = np.tile([0.0, 0.0, 0.0], (F, 1))
    return c, ax, 3.5, -1.0, arrive


def test_leaves_the_horn_at_its_tangent():
    c, ax, r, side, arrive = _horn()
    an = C.anchor(c, ax, r, side, arrive, math.radians(90.0), U, ZB, a=20.0, laid=60.0)
    res = C.hang_off(c, ax, r, side, arrive, math.radians(90.0), an["start"][0], U, ZB, an["length0"])
    assert res["kink"][0] < 1e-9 and not res["steep"][0] and not res["short"][0]
    assert res["psi"][0] == pytest.approx(an["psi"][0], abs=1e-9)
    assert res["a"][0] == pytest.approx(20.0, rel=1e-9) and res["laid"][0] == pytest.approx(60.0, abs=1e-6)
    # the wheel's tangent at T is the catenary's direction there
    assert float(np.dot(res["tangent"][0], res["direction"][0])) == pytest.approx(1.0, abs=1e-12)
    # the layback anchor gives the same
    an2 = C.anchor(c, ax, r, side, arrive, math.radians(90.0), U, ZB, layback=float(an["layback"][0]), laid=60.0)
    assert an2["a"][0] == pytest.approx(20.0, rel=1e-8)


def test_steep_catenary_bends_over_the_end():
    c, ax, r, side, arrive = _horn()
    an = C.anchor(c, ax, r, side, arrive, math.radians(90.0), U, ZB, a=5.0, laid=20.0)      # steep: 80° or so
    end = math.radians(40.0)                                                                 # a short chute
    res = C.hang_off(c, ax, r, side, arrive, end, an["start"][0], U, ZB, an["length0"])
    assert res["steep"][0] and res["psi"][0] == pytest.approx(end) and res["kink"][0] > math.radians(10.0)


def test_laid_length_is_the_advance_plus_what_was_there():
    """The vessel moves forward as fast as it pays out: the touch-down stays behind it and the cable on the seabed
    grows by the advance; slower: the layback shrinks."""
    c, ax, r, side, arrive = _horn(1)
    an = C.anchor(c, ax, r, side, arrive, math.radians(90.0), U, ZB, a=20.0, laid=60.0)
    S = an["start"][0]
    adv = np.linspace(0.0, 25.0, 6)
    F = len(adv)
    shift = -U[None, :] * 0.0 + np.outer(adv, -U)        # the vessel moves forward (+x) by adv over the seabed
    cF, axF, _r, _s, arrF = _horn(F)
    res = C.hang_off(cF + shift, axF, r, side, arrF + shift, math.radians(90.0), S, U, ZB, an["length0"] + adv)
    assert np.abs(res["laid"] - (60.0 + adv)).max() < 1e-6
    assert np.abs(res["layback"] - an["layback"][0]).max() < 1e-6
    half = C.hang_off(cF + shift, axF, r, side, arrF + shift, math.radians(90.0), S, U, ZB,
                      an["length0"] + 0.5 * adv)
    assert np.all(np.diff(half["layback"]) > 0.0)        # paid out slower than it moves: pulled flatter
