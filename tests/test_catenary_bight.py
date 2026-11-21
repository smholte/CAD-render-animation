"""Task 0248: a cable piled up on the seabed lies straight from its end S along the lay line and carries its extra
length in ONE bight next to the touch-down (``core.catenary.bight``), not in waves of 4 m over the whole way from S
to the touch-down. No Blender.

What is checked on the drawn line (sampled densely): its length, both ends, it lies on the seabed, no kink where the
bight meets the touch-down or the straight (≤ 1°), one curve to one side, never tighter than its bend radius (when it
has room), the cable from S up to the bight exactly on the lay line, nothing of it beyond ``keep`` metres from S moved.
"""

import math

import numpy as np
import pytest

from fresing_render.core import catenary as C

U = np.array([-1.0, 0.0, 0.0])          # laid aft (−x)
ZB = -30.0                              # the cable's middle on the seabed


def piled(T, S, L, **extra):
    res = C.hang(np.array([T], dtype=float), np.array(S, dtype=float), U, ZB, np.array([L], dtype=float))
    for key, v in extra.items():
        res[key] = np.array([v], dtype=float)
    assert int(res["kind"][0]) == C.PILED
    return res


def dense(res, n=400001):
    lam = np.linspace(0.0, float(res["L"][0]), n)
    return lam, C.points(res, lam[None])[0]


def poly_length(p):
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def bed_part(res, lam, p):
    """The points on the seabed (arc length beyond the hanging part)."""
    on = lam >= float(res["suspended"][0]) + 1e-9
    return p[on]


def turning(p):
    """Signed turn (rad) between successive pieces of a flat polyline and the pieces' lengths."""
    d = np.diff(p[:, :2], axis=0)
    ln = np.linalg.norm(d, axis=1)
    keep = ln > 1e-9
    d, ln = d[keep], ln[keep]
    ang = np.arctan2(d[:, 1], d[:, 0])
    return np.angle(np.exp(1j * np.diff(ang))), ln


def tightest(p):
    """The smallest radius of a flat polyline (from the turn over each pair of pieces)."""
    turn, ln = turning(p)
    k = np.abs(turn) / np.maximum(0.5 * (ln[:-1] + ln[1:]), 1e-300)
    return 1.0 / max(float(k.max()), 1e-300)


CASES = [
    # T, S, L, r_min: a little extra; a lot of extra with a tight bend radius; the extra in shallow water
    ((0.0, 0.0, ZB + 0.001), (-80.0, 0.0, ZB), 80.5, 1.2),
    ((0.0, 0.0, ZB + 0.001), (-400.0, 0.0, ZB), 428.0, 3.5),
    ((0.0, 0.0, ZB + 3.0), (-60.0, 0.0, ZB), 70.0, 2.0),
    ((0.0, 0.0, ZB + 0.001), (-80.0, 0.0, ZB), 80.02, 1.2),           # just piled: a long flat curve
]


@pytest.mark.parametrize("T, S, L, r_min", CASES)
def test_one_bight_next_to_the_touch_down(T, S, L, r_min):
    res = piled(T, S, L, r_min=r_min)
    lam, p = dense(res)
    b = C.bight(res)
    # length, ends, on the seabed
    assert poly_length(p) == pytest.approx(L, abs=1e-3)
    assert np.linalg.norm(p[0] - res["T"][0]) < 1e-6 and np.linalg.norm(p[-1] - res["S"][0]) < 1e-9
    assert p[:, 2].min() >= ZB - 1e-9
    bed = bed_part(res, lam, p)
    assert np.allclose(bed[:, 2], ZB)
    # from S to the bight: exactly on the lay line (y = 0), in the order of the line
    span = float(b["span"][0])
    tdp_x = float(res["tdp"][0][0])
    straight = bed[bed[:, 0] < tdp_x - span - 1e-6]
    assert len(straight) and np.abs(straight[:, 1]).max() < 1e-9
    # one curve to one side: the bight's points all on one side, back on the line at its two ends
    curve = bed[bed[:, 0] >= tdp_x - span - 1e-6]
    sign = np.sign(curve[np.abs(curve[:, 1]) > 1e-6, 1])
    assert len(set(sign)) == 1
    # no kink: the first and the last piece of the bight along the line (≤ 1°)
    turn, ln = turning(bed)
    assert np.abs(turn).max() < math.radians(1.0)
    # never tighter than the bend radius (it had room)
    assert float(b["R"][0]) >= r_min - 1e-9
    assert tightest(curve) >= r_min * 0.999


def test_the_bight_stays_close_to_the_touch_down():
    """The extra cable lies next to the touch-down, not spread over the whole way from S: 400 m on the seabed with 2 m
    extra – the bight spans a few dozen metres, the rest is straight (before: 100 waves over the whole 400 m)."""
    res = piled((0.0, 0.0, ZB + 0.001), (-400.0, 0.0, ZB), 402.0, r_min=2.0)
    b = C.bight(res)
    assert 2.0 < float(b["span"][0]) < 40.0


def test_cable_kept_from_s_is_never_bent():
    """``keep``: the metres from S that lay on the seabed when the hang-off was let go. The bight never reaches into
    them, even when it must turn more (grow sideways) to do so – then it may be tighter than the bend radius."""
    for keep in (0.0, 30.0, 70.0, 79.0):
        res = piled((0.0, 0.0, ZB + 0.001), (-80.0, 0.0, ZB), 84.0, r_min=1.2, keep=keep)
        lam, p = dense(res)
        bed = bed_part(res, lam, p)
        kept = bed[bed[:, 0] <= -80.0 + keep + 1e-9]
        assert len(kept) and np.abs(kept[:, 1]).max() < 1e-9, keep
        assert poly_length(p) == pytest.approx(84.0, abs=1e-3)
    # no room at all (kept up to under the hang-off): a loop on the spot, still the right length
    res = piled((0.0, 0.0, ZB + 0.001), (-80.0, 0.0, ZB), 84.0, r_min=1.2, keep=80.0)
    lam, p = dense(res)
    assert poly_length(p) == pytest.approx(84.0, abs=1e-3)
    assert float(C.bight(res)["theta"][0]) == pytest.approx(math.pi, abs=1e-6)


def test_no_bend_radius_given_a_45_degree_bight():
    res = piled((0.0, 0.0, ZB + 0.001), (-80.0, 0.0, ZB), 81.0)
    assert float(C.bight(res)["theta"][0]) == pytest.approx(C.BIGHT_TURN)


def test_the_bight_grows_smoothly_from_nothing():
    """As the extra length grows from 0 (a let-go cable that has just come to pile up), the bight grows from nothing:
    no point jumps."""
    prev = None
    for extra in np.linspace(0.0, 1.0, 101):
        res = C.hang(np.array([[0.0, 0.0, ZB + 0.001]]), np.array([-80.0, 0.0, ZB]), U, ZB,
                     np.array([80.0 + 1e-6 + extra]))
        res["r_min"] = np.array([1.2])
        lam = np.linspace(0.0, float(res["L"][0]), 2001)
        p = C.points(res, lam[None])[0]
        if prev is not None:
            assert np.abs(p - prev).max() < 0.25, extra
        prev = p


def test_many_moments_are_the_one_moment_answers():
    rng = np.random.default_rng(11)
    F = 40
    T = np.column_stack([rng.uniform(-5, 5, F), rng.uniform(-3, 3, F), ZB + rng.uniform(0.001, 8.0, F)])
    L = 100.0 + rng.uniform(5.0, 40.0, F)
    res = C.hang(T, np.array([-100.0, 0.0, ZB]), U, ZB, L)
    res["r_min"] = rng.uniform(0.0, 4.0, F)
    res["keep"] = np.where(rng.uniform(size=F) < 0.5, np.nan, rng.uniform(0.0, 90.0, F))
    lam = L[:, None] * np.linspace(0.0, 1.0, 301)[None]
    many = C.points(res, lam)
    for k in range(F):
        one = {key: (v[k:k + 1] if isinstance(v, np.ndarray) and v.shape[:1] == (F,) else v) for key, v in res.items()}
        assert np.allclose(C.points(one, lam[k:k + 1])[0], many[k], atol=1e-9)
