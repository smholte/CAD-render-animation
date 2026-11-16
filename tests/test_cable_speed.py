"""Task 0159: cables, paths and spools faster – the same results as before, in less time.

- ``flex.read_places`` (the pass through the frames a Build makes for hoses and cables) lets Blender work out only the
  objects it reads and what their places depend on: the places are exactly those of a pass with everything shown, and
  every object's visibility and visibility keys are as they were afterwards.
- ``core/spool.polyline`` works out all pieces of the wound path at once: the same points as the piece-by-piece loop
  it replaced (kept below as the reference), to the last bit.
- ``core/catenary``: one moment (posing a cable into the sea) is solved on plain numbers; the same answer as the array
  form (the path many moments take, at Build).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fresing_render.core import catenary as C
from fresing_render.core import spool as S


# ---------------------------------------------------------------------------------------------------------- polyline

def _curvature_ref(path, i: int) -> float:
    dphi = path.phi1[i] - path.phi0[i]
    da = path.a1[i] - path.a0[i]
    dr = path.r1[i] - path.r0[i]
    worst = 0.0
    for u in (0.0, 0.5, 1.0):
        r = path.r0[i] + (path.r1[i] - path.r0[i]) * u
        d1 = np.array([dr, r * dphi, da])
        d2 = np.array([-r * dphi * dphi, 2.0 * dr * dphi, 0.0])
        worst = max(worst, float(np.linalg.norm(np.cross(d1, d2)) / np.linalg.norm(d1) ** 3))
    return worst


def _grid_ref(path, L_lo, L_hi, sag):
    """The piece-by-piece grid of polyline before task 0159: (L, piece)."""
    L_lo = float(np.clip(L_lo, 0.0, path.total))
    L_hi = float(np.clip(L_hi, 0.0, path.total))
    first = int(S._index(path, L_lo)[0])
    last = int(S._index(path, L_hi, upper=True)[0])
    grids = []
    for i in range(first, last + 1):
        lo, hi = max(path.L0[i], L_lo), min(path.L1[i], L_hi)
        if hi - lo <= S._TINY:
            continue
        kappa = _curvature_ref(path, i)
        h = math.sqrt(8.0 * sag / kappa) if kappa > 0.0 else hi - lo
        m = max(1, int(math.ceil((hi - lo) / (2.0 * h))))
        Ls = lo + (hi - lo) * np.arange(2 * m + 1) / (2 * m)
        Ls[-1] = hi
        grids.append((i, Ls if not grids else Ls[1:]))
    L = np.concatenate([g for _, g in grids])
    L[0], L[-1] = L_lo, L_hi
    return L, np.concatenate([np.full(len(g), i) for i, g in grids])


SPOOLS = {
    "carousel": S.Spool(kind="CAROUSEL", d=0.2, r_in=4.16, r_out=11.6, a_bot=0.4, a_top=5.4, hand=1),
    "lebus": S.Spool(kind="DRUM", d=0.048, r1=0.5, a_lo=-0.6, a_hi=0.6, groove="LEBUS", r_max=0.9, hand=-1),
    "spiral": S.Spool(kind="DRUM", d=0.036, r1=0.3, a_lo=-0.4, a_hi=0.4, r_max=0.6, hand=1),
}


@pytest.mark.parametrize("name", sorted(SPOOLS))
def test_polyline_is_the_piece_by_piece_grid(name):
    path = S.wind(SPOOLS[name])
    T = float(path.total)
    for lo, hi, sag in ((0.0, T, 3e-4), (0.3 * T, 0.55 * T, 1e-3), (T - 50.0, T, 2e-4), (5.0, 5.3, 1e-4),
                        (0.5 * T, 0.5 * T + 1e-6, 1e-3)):
        L_ref, piece = _grid_ref(path, lo, hi, sag)
        pts, L = S.polyline(path, lo, hi, sag)
        assert np.array_equal(L, L_ref), (name, lo, hi)
        phi, a, r = S._eval(path, piece, L_ref)
        ref = S.xyz(phi, a, r)
        # the ends and every even point lie on the path; the odd ones were moved onto the chord circles (as before)
        assert np.array_equal(pts[0::2][:-1], ref[0::2][:-1])
        assert np.array_equal(pts[-1], ref[-1])


def test_curvature_of_many_pieces_at_once():
    path = S.wind(SPOOLS["lebus"])
    idx = np.arange(len(path.L0))
    got = S._curvature(path, idx)
    assert got.shape == idx.shape
    for i in idx[:: max(1, len(idx) // 50)]:
        assert got[i] == pytest.approx(_curvature_ref(path, int(i)), rel=1e-12, abs=1e-15)
    assert isinstance(S._curvature(path, 3), float)


# ---------------------------------------------------------------------------------------------------------- catenary

def _cases(seed=1, n=200):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        top = np.array([rng.uniform(-50, 50), rng.uniform(-5, 5), rng.uniform(1, 40)])
        start = np.array([rng.uniform(80, 400), rng.uniform(-10, 10), 0.0])
        aft = np.array([1.0, rng.uniform(-0.2, 0.2), 0.0])
        yield top, start, aft, float(rng.uniform(5, 600))


def test_one_moment_on_plain_numbers_is_the_array_answer():
    """The same moment once alone (plain numbers) and among more than SMALL moments (arrays): the same catenary."""
    cases = list(_cases())
    kinds = set()
    for top, start, aft, L in cases:
        one = C.hang(top[None], start, aft, -0.1, np.array([L]))
        many = C.hang(np.tile(top, (C.SMALL + 1, 1)), start, aft, -0.1, np.full(C.SMALL + 1, L))
        kinds.add(int(one["kind"][0]))
        assert one["kind"][0] == many["kind"][0]
        for key in ("a", "suspended", "laid", "layback", "angle", "excess"):
            assert one[key][0] == pytest.approx(many[key][0], rel=1e-12, abs=1e-9), key
        assert np.allclose(one["tdp"][0], many["tdp"][0], rtol=0, atol=1e-9)
        assert np.allclose(one["direction"][0], many["direction"][0], rtol=0, atol=1e-6)
    assert {C.NORMAL, C.PILED} <= kinds                     # (the cases reach both the touching and the piled shape)


def test_a_for_span_small_and_large_agree():
    rng = np.random.default_rng(7)
    X, h = rng.uniform(0.01, 300.0, 50), rng.uniform(0.01, 60.0, 50)
    big = C.a_for_span(X, h)
    small = np.array([C.a_for_span(X[i:i + 1], h[i:i + 1])[0] for i in range(len(X))])
    assert np.allclose(small, big, rtol=1e-12, atol=0)
    assert np.allclose(C.span(big, h), X, rtol=1e-9)
    assert C.a_for_span(5.0, 2.0).shape == ()


def test_hang_off_one_moment_is_faster():
    """Posing a cable into the sea solves one moment many times: well below the array form's time (measured on the
    4-core web machine: 7 x)."""
    import time
    rng = np.random.default_rng(3)
    args = []
    for _ in range(10):
        c = np.array([[rng.uniform(-3, 0), 0.0, rng.uniform(3, 8)]])
        args.append((c, [0, 1, 0], 3.5, 1.0, c + [[3.5, 0, 0]], np.pi, [rng.uniform(80, 300), 0, 0], [1, 0, 0], -30.0,
                     rng.uniform(40, 400)))
    t0 = time.perf_counter()
    for a in args:
        C.hang_off(*a)
    one = time.perf_counter() - t0
    small, C.SMALL = C.SMALL, 0                             # every moment through the arrays, as before
    try:
        t0 = time.perf_counter()
        for a in args:
            C.hang_off(*a)
        arrays = time.perf_counter() - t0
    finally:
        C.SMALL = small
    assert one < 0.5 * arrays, (one, arrays)


def _snake_ref(dist: float, length: float, waves: int) -> float:
    """The one-moment bisection the piled-up snake used before task 0159."""
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


def test_snake_amplitudes_of_many_moments_are_the_one_moment_answers():
    rng = np.random.default_rng(5)
    n = 300                                             # (more than one block of 256)
    d = rng.uniform(0.5, 60.0, n)
    ln = d * rng.uniform(1.0, 1.6, n)
    ln[:5] = d[:5]                                      # (lying straight: no snake)
    w = np.maximum(1, np.round(np.maximum(d, C.SNAKE) / C.SNAKE)).astype(int)
    got = C._snake_amplitudes(d, ln, w)
    ref = np.array([_snake_ref(float(a), float(b), int(c)) for a, b, c in zip(d, ln, w)])
    assert np.array_equal(got, ref)
    assert (got[:5] == 0.0).all() and (got[5:] > 0.0).all()
