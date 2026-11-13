"""Task 0080: the spooling maths (fresing_render/core/spool.py) – no Blender.

The wound path of a spiral-groove drum, a Lebus drum and a carousel; the spool's turn against the payout (table at
the breaks against the exact formula and against a brute-force helix integrated here); the leave point; drawing
(chords equal to the length, within the sag); the tangent where a rope leaves; the arm that follows the leave
radius; fleet angles; the stack (rope on top, a solid below) and its volume.
"""

import math
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from fresing_render.core import spool as S  # noqa: E402

DEG = math.pi / 180.0
TOL_ANGLE = 0.01 * DEG          # the task: drum angle within 0.01°


def drum(**kw):
    numbers = dict(d=0.020, r1=0.160, a_lo=0.0, a_hi=0.400, pitch=0.0212, r_max=0.30)
    numbers.update(kw)
    return S.Spool(S.DRUM, **numbers)


def carousel(**kw):
    numbers = dict(d=0.040, r_in=0.340, r_out=0.840, a_bot=0.0, layers=4)
    numbers.update(kw)
    return S.Spool(S.CAROUSEL, **numbers)


@pytest.fixture(scope="module")
def drum_path():
    return S.wind(drum())


@pytest.fixture(scope="module")
def lebus_path():
    return S.wind(drum(groove=S.LEBUS, layers=3, r_max=math.inf))


@pytest.fixture(scope="module")
def carousel_path():
    return S.wind(carousel())


def dense_xyz(path, L):
    phi, a, r, _ = S.at(path, L)
    return S.xyz(phi, a, r)


# ---------------------------------------------------------------------------------------------------------
# the wound path
# ---------------------------------------------------------------------------------------------------------

def test_drum_layers_and_pieces(drum_path):
    s = drum_path.spool
    # r_max 0.30: layers at 0.160 + k * 0.02 * cos30 while <= 0.30 -> k = 0 … 8
    assert drum_path.layer_count == 9
    helix = drum_path.kind == S.HELIX
    assert helix.sum() == 9
    climbs = drum_path.kind == S.CLIMB
    assert sorted(set(drum_path.layer[climbs])) == list(range(8))           # a climb out of every layer but the top
    turns = (s.a_hi - s.a_lo - s.d) / s.pitch
    for i in np.nonzero(helix)[0]:
        k = drum_path.layer[i]
        assert drum_path.r0[i] == pytest.approx(0.160 + k * 0.020 * math.cos(30 * DEG), abs=1e-12)
        assert drum_path.phi1[i] - drum_path.phi0[i] == pytest.approx(2 * math.pi * turns, rel=1e-12)
        # a true helix length
        r = drum_path.r0[i]
        expect = math.hypot(r * 2 * math.pi * turns, s.a_hi - s.a_lo - s.d)
        assert drum_path.L1[i] - drum_path.L0[i] == pytest.approx(expect, rel=1e-12)
        # layer 0 from a_lo; the direction alternates
        lo, hi = s.a_lo + s.d / 2, s.a_hi - s.d / 2
        assert (drum_path.a0[i], drum_path.a1[i]) == ((lo, hi) if k % 2 == 0 else (hi, lo))


def test_drum_start_and_hand():
    p = S.wind(drum(start=-1, hand=-1, layers=2, r_max=math.inf))
    assert p.a0[0] == pytest.approx(0.390) and p.a1[0] == pytest.approx(0.010)
    assert np.all(np.diff(np.concatenate([p.phi0, p.phi1[-1:]])) < 0.0)


def test_path_is_continuous(drum_path, lebus_path, carousel_path):
    """No jumps anywhere along L: piece ends meet the next piece's start, and dense samples are never further apart
    than their difference in L."""
    for path in (drum_path, lebus_path, carousel_path):
        for x0, x1 in ((path.phi0, path.phi1), (path.a0, path.a1), (path.r0, path.r1)):
            assert np.max(np.abs(x0[1:] - x1[:-1])) < 1e-12
        assert np.all(path.L0[1:] == path.L1[:-1])
        L = np.linspace(0.0, path.total, 200001)
        pts = dense_xyz(path, L)
        step = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        assert np.all(step <= np.diff(L) * (1 + 1e-6) + 1e-12)


def test_climb_pieces(drum_path, carousel_path):
    s = drum_path.spool
    climb = drum_path.kind == S.CLIMB
    for k in range(drum_path.layer_count - 1):
        sel = np.nonzero(climb & (drum_path.layer == k))[0]      # the layer it climbs from
        assert np.all(drum_path.a0[sel] == drum_path.a1[sel])
        assert np.all(drum_path.a0[sel] == drum_path.a0[sel[0]])
        assert drum_path.a0[sel[0]] in (pytest.approx(s.a_lo + s.d / 2), pytest.approx(s.a_hi - s.d / 2))
        assert drum_path.r0[sel[0]] == pytest.approx(float(S.layer_radius(drum_path, k)))
        assert drum_path.r1[sel[-1]] == pytest.approx(float(S.layer_radius(drum_path, k + 1)))
        assert abs(drum_path.phi1[sel[-1]] - drum_path.phi0[sel[0]]) == pytest.approx(s.climb)
        # cut small: the radius changes by at most SHARE in a piece
        assert np.all((drum_path.r1[sel] - drum_path.r0[sel]) <= S.SHARE * drum_path.r0[sel] + 1e-12)
    climb = carousel_path.kind == S.CLIMB
    rise = carousel_path.a1[climb] - carousel_path.a0[climb]
    assert np.all(rise > 0.0)
    for k in range(carousel_path.layer_count - 1):
        sel = climb & (carousel_path.layer == k)
        assert carousel_path.a0[sel][0] == pytest.approx(float(S.layer_place(carousel_path, k)))
        assert carousel_path.a1[sel][-1] == pytest.approx(float(S.layer_place(carousel_path, k + 1)))


def test_lebus_layers(lebus_path):
    p, s = lebus_path, lebus_path.spool
    par = p.kind == S.PARALLEL
    cross = p.kind == S.CROSSOVER
    assert np.all(p.a0[par] == p.a1[par])                       # parallel: a stays
    full = cross & np.isclose(np.abs(p.phi1 - p.phi0), s.crossover)
    # a full crossover moves a by half a pitch, a partial one by its share of it
    assert np.allclose(np.abs(p.a1[full] - p.a0[full]), s.pitch / 2, atol=1e-12)
    share = np.abs(p.phi1[cross] - p.phi0[cross]) / s.crossover
    assert np.allclose(np.abs(p.a1[cross] - p.a0[cross]), share * s.pitch / 2, atol=1e-12)
    # crossovers lie in the two zones fixed on the drum, half a turn apart, at every layer
    mid = 0.5 * (p.phi0[cross] + p.phi1[cross])
    x = (mid - s.crossover_at) % math.pi
    assert np.all(x < s.crossover + 1e-9)
    # two crossovers per turn
    for k in range(3):
        sel = cross & (p.layer == k)
        turn = np.abs(p.phi1[(p.layer == k) & (p.kind != S.CLIMB)] - p.phi0[(p.layer == k) & (p.kind != S.CLIMB)]).sum()
        assert np.abs(p.phi1[sel] - p.phi0[sel]).sum() / s.crossover == pytest.approx(2 * turn / (2 * math.pi), abs=1.0)
        # each layer moves over by the whole width, back and forth
        travel = s.a_hi - s.a_lo - s.d
        assert np.abs(p.a1[sel] - p.a0[sel]).sum() == pytest.approx(travel, abs=1e-9)
        # about the turns of a helix of the same pitch (where the zones lie decides the last half turn)
        assert abs(turn - 2 * math.pi * travel / s.pitch) <= math.pi + 1e-9


def test_lebus_angle_table(lebus_path):
    W0 = lebus_path.total - 0.5
    p_hi = W0 - 0.01
    keys = S.breaks(lebus_path, W0, 0.0, p_hi)
    table = S.angle_table(lebus_path, W0, None, keys)
    rng = np.random.default_rng(3)
    p = rng.uniform(0.0, p_hi, 2000)
    exact = S.exact_angle(lebus_path, W0, p)
    assert np.max(np.abs(np.interp(p, keys, table) - exact)) < TOL_ANGLE / 5
    # and against plain geometry: the turn equals the turn of rope paid out (phi from the anchor)
    assert np.allclose(exact, S.at(lebus_path, W0)[0] - S.at(lebus_path, W0 - p)[0])


def test_refuses_impossible_numbers():
    with pytest.raises(ValueError, match="narrower"):
        S.wind(drum(a_hi=0.015))
    with pytest.raises(ValueError, match="largest radius or a number of layers"):
        S.wind(drum(r_max=math.inf))
    with pytest.raises(ValueError, match="top or a number of layers"):
        S.wind(carousel(layers=None))
    with pytest.raises(ValueError, match="diameter"):
        S.wind(drum(d=0.0))
    assert S.wind(carousel(layers=None, a_top=0.125)).layer_count == 3     # 3 layers of 40 mm fit under 125 mm


# ---------------------------------------------------------------------------------------------------------
# the drum's turn against the payout
# ---------------------------------------------------------------------------------------------------------

def brute_force_phi(spool, L_query):
    """phi at rope length L, built here independently: the drum's helix layers and the climbs stepped through in
    tiny steps of turn, their chords summed (no pieces, no Gauss-Legendre)."""
    d, pitch = spool.d, spool.pitch
    lo, hi = spool.a_lo + d / 2, spool.a_hi - d / 2
    turns = (hi - lo) / pitch
    phis, Ls = [0.0], [0.0]
    phi, L = 0.0, 0.0
    a = lo
    k = 0
    while Ls[-1] < max(L_query) + 1.0:
        r = spool.r1 + k * d * math.cos(math.radians(30))
        r_next = spool.r1 + (k + 1) * d * math.cos(math.radians(30))
        going = 1 if k % 2 == 0 else -1
        # the layer
        t = np.linspace(0.0, 2 * math.pi * turns, 200001)
        x, y, z = r * np.cos(phi + t), r * np.sin(phi + t), a + going * (hi - lo) * t / t[-1]
        s = np.concatenate([[0.0], np.cumsum(np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2 + np.diff(z) ** 2))])
        phis.extend(phi + t[1:])
        Ls.extend(L + s[1:])
        phi, L, a = phi + t[-1], L + s[-1], z[-1]
        # the climb
        t = np.linspace(0.0, spool.climb, 20001)
        rr = r + (r_next - r) * t / t[-1]
        x, y = rr * np.cos(phi + t), rr * np.sin(phi + t)
        s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
        phis.extend(phi + t[1:])
        Ls.extend(L + s[1:])
        phi, L = phi + t[-1], L + s[-1]
        k += 1
    return np.interp(L_query, np.array(Ls), np.array(phis))


def test_drum_angle_table_over_100_m(drum_path):
    W0 = 120.0
    p_hi = 100.0
    _, _, _, layer_full = S.at(drum_path, W0)
    _, _, _, layer_left = S.at(drum_path, W0 - p_hi)
    assert layer_full - layer_left >= 3                         # at least 3 layers paid out
    keys = S.breaks(drum_path, W0, 0.0, p_hi)
    assert keys[0] == 0.0 and keys[-1] == p_hi and np.all(np.diff(keys) > 0)
    table = S.angle_table(drum_path, W0, None, keys)
    rng = np.random.default_rng(1)
    p = rng.uniform(0.0, p_hi, 2000)
    exact = S.exact_angle(drum_path, W0, p)
    assert np.max(np.abs(np.interp(p, keys, table) - exact)) < TOL_ANGLE
    assert np.max(np.abs(np.interp(p, keys, table) - exact)) < 3e-5     # exact on the helices, ~1e-5 rad on climbs
    # against a brute-force helix
    ref = brute_force_phi(drum_path.spool, np.array([W0]))[0] - brute_force_phi(drum_path.spool, W0 - p)
    assert np.max(np.abs(exact - ref)) < TOL_ANGLE
    assert np.max(np.abs(np.interp(p, keys, table) - ref)) < TOL_ANGLE
    # paying out turns the drum about +z for hand +1, ever more
    assert np.all(np.diff(table) > 0.0)


def test_angle_table_with_moving_psi(drum_path):
    W0 = 50.0
    p = np.linspace(0.0, 20.0, 41)
    psi = 0.1 * np.sin(p)
    plain = S.angle_table(drum_path, W0, None, p)
    moved = S.angle_table(drum_path, W0, psi, p)
    assert np.allclose(moved - plain, psi - psi[0])
    assert np.allclose(S.exact_angle(drum_path, W0, p, lambda x: 0.1 * np.sin(x)), moved)


def test_angle_stands_still_when_empty_or_full(drum_path):
    W0 = 10.0
    theta = S.exact_angle(drum_path, W0, np.array([10.0, 11.0, 30.0]))
    assert theta[0] == theta[1] == theta[2]
    W0 = drum_path.total + 5.0
    theta = S.exact_angle(drum_path, W0, np.array([0.0, 2.0, 5.0]))
    assert np.allclose(theta, 0.0)


def test_leave_point_and_length(drum_path):
    W0 = 120.0
    rng = np.random.default_rng(2)
    s = drum_path.spool
    for p in np.concatenate([[0.0, 100.0], rng.uniform(0.0, 100.0, 40)]):
        phi, a, r, k = S.at(drum_path, W0 - p)
        pt = S.xyz(phi, a, r)
        i = S._index(drum_path, W0 - p)[0]
        if drum_path.kind[i] == S.HELIX:            # on its layer's rope circle
            assert abs(math.hypot(pt[0], pt[1]) - float(S.layer_radius(drum_path, k))) < 0.0005
            assert s.a_lo + s.d / 2 - 1e-12 <= a <= s.a_hi - s.d / 2 + 1e-12
        # length on the spool (the drawn rope) + paid out = wound at the start
        pts, L = S.polyline(drum_path, 0.0, W0 - p, 0.0005)
        on_spool = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()
        assert abs(on_spool + p - W0) < 0.001
        assert np.allclose(pts[-1], pt, atol=1e-12)


def test_breaks_are_piece_ends(drum_path):
    W0 = 120.0
    keys = S.breaks(drum_path, W0, 3.0, 90.0)
    assert keys[0] == 3.0 and keys[-1] == 90.0
    inner = keys[1:-1]
    assert len(inner) >= 3
    assert np.all(np.min(np.abs((W0 - inner)[:, None] - drum_path.L1[None, :]), axis=1) < 1e-9)


# ---------------------------------------------------------------------------------------------------------
# the carousel
# ---------------------------------------------------------------------------------------------------------

def test_carousel_layers(carousel_path):
    p, s = carousel_path, carousel_path.spool
    assert p.layer_count == 4
    flat = p.kind == S.FLAT
    assert np.all(p.a0[flat] == p.a1[flat])
    for k in range(4):
        sel = flat & (p.layer == k)
        assert np.allclose(p.a0[sel], s.a_bot + s.d / 2 + k * s.d)
        rs = np.concatenate([p.r0[sel], p.r1[sel]])
        # every layer covers the whole width: inside out, then outside in
        lo, hi = s.r_in + s.d / 2, s.r_out - s.d / 2
        if k == 0:
            assert p.r0[sel][0] == pytest.approx(lo) and p.r1[sel][-1] == pytest.approx(hi)
        else:
            assert rs.max() <= hi + 1e-12 and rs.min() >= lo - 1e-12
            assert p.r1[sel][-1] == pytest.approx(lo if k % 2 else hi)
    # Archimedean: the radius changes by d per turn
    dr = (p.r1 - p.r0) / (p.phi1 - p.phi0)
    assert np.allclose(np.abs(dr), s.d / (2 * math.pi), rtol=1e-9)
    # pieces small enough
    turn = np.abs(p.phi1 - p.phi0)
    assert np.all(turn <= S.SPIRAL_MAX + 1e-12)
    assert np.all(turn <= S.SPIRAL_SHARE * math.pi * np.minimum(p.r0, p.r1) / s.d + 1e-9)


def test_carousel_turn_per_metre(carousel_path):
    p = carousel_path
    flat_L = np.concatenate([np.linspace(p.L0[i], p.L1[i], 7)[1:-1] for i in np.nonzero(p.kind == S.FLAT)[0]])
    L = np.concatenate([flat_L, np.linspace(0.0, p.total, 50001)])
    i = S._index(p, L)[0]
    L = L[p.kind[i] == S.FLAT]
    r = S.at(p, L)[2]
    tpm = S.turn_per_metre(p, L)
    assert np.max(np.abs(np.abs(tpm) * r - 1.0)) < 0.001       # 1/r at every radius, within 0.1 %
    # the table's slope between neighbouring keys: right at both keys and between them
    W0 = p.total
    keys = S.breaks(p, W0, 0.0, W0)
    table = S.angle_table(p, W0, None, keys)
    slope = np.diff(table) / np.diff(keys)
    mid = keys[:-1] + 0.5 * np.diff(keys)
    flat = p.kind[S._index(p, W0 - mid)[0]] == S.FLAT       # the stretches on a layer's spiral (not a climb)
    for f in (0.0, 0.5, 1.0):
        r_here = S.at(p, W0 - (keys[:-1] + f * np.diff(keys)))[2]
        assert np.max(np.abs(np.abs(slope[flat]) * r_here[flat] - 1.0)) < 0.001
    # and the slope is the exact one (the derivative of exact_angle)
    h = 1e-4 * np.diff(keys)
    numeric = (S.exact_angle(p, W0, mid + h) - S.exact_angle(p, W0, mid - h)) / (2 * h)
    assert np.allclose(slope, numeric, rtol=1e-6)
    assert np.allclose(slope, S.turn_per_metre(p, W0 - mid), rtol=1e-3)


def test_carousel_volume(carousel_path):
    p, s = carousel_path, carousel_path.spool
    for k in range(1, 5):
        L = S.layer_start(p, k)             # the rope of k full layers
        ratio = S.rope_volume(L, s.d) / (S.ring_volume(s, k) * math.pi / 4)
        assert abs(ratio - 1.0) < 0.01
    # top layer partly paid out + the solid below: drawn rope + solid keep the volume
    W0 = p.total
    for pay in (5.0, 30.0, 60.0, 100.0):
        L_low, solid = S.stack(p, W0, pay, 1)
        full = round(float(solid) / s.d)
        rope = S.rope_volume(W0 - pay - L_low, s.d)
        total = S.rope_volume(W0 - pay, s.d)
        assert abs((S.ring_volume(s, full) * math.pi / 4 + rope) / total - 1.0) < 0.01


# ---------------------------------------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------------------------------------

def _gap_to_polyline(pts, Lp, path, n=20001, lo=None, hi=None):
    """The largest distance of the true path (sampled densely) from the polyline: each sample against the
    segments round the one its L falls in."""
    L = np.linspace(Lp[0] if lo is None else lo, Lp[-1] if hi is None else hi, n)
    true = dense_xyz(path, L)
    seg = np.clip(np.searchsorted(Lp, L, side="right") - 1, 0, len(Lp) - 2)
    worst = np.full(len(L), np.inf)
    for shift in (-1, 0, 1):
        k = np.clip(seg + shift, 0, len(Lp) - 2)
        A, B = pts[k], pts[k + 1]
        ab = B - A
        t = np.clip(np.einsum("ij,ij->i", true - A, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-300), 0, 1)
        worst = np.minimum(worst, np.linalg.norm(true - (A + t[:, None] * ab), axis=1))
    return worst.max()


@pytest.mark.parametrize("which", ["drum", "lebus", "carousel"])
@pytest.mark.parametrize("sag", [0.002, 0.0005])
def test_polyline(which, sag, drum_path, lebus_path, carousel_path):
    path = {"drum": drum_path, "lebus": lebus_path, "carousel": carousel_path}[which]
    lo, hi = 0.37 * path.total, 0.37 * path.total + 30.0
    pts, L = S.polyline(path, lo, hi, sag)
    assert L[0] == lo and L[-1] == hi
    assert np.all(np.diff(L) > 0)
    assert np.allclose(pts[0], dense_xyz(path, lo), atol=1e-15)
    assert np.allclose(pts[-1], dense_xyz(path, hi), atol=1e-15)
    chord = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert np.max(np.abs(chord / np.diff(L) - 1.0)) < 1e-9
    assert _gap_to_polyline(pts, L, path) <= sag
    # cheap enough: about one point per sqrt(8 sag r) of rope, not thousands per turn
    assert len(L) < 4 * 30.0 / math.sqrt(8 * sag * 0.15) + 200


def test_polyline_whole_and_tiny_ranges(drum_path):
    pts, L = S.polyline(drum_path, 0.0, drum_path.total, 0.001)
    assert L[0] == 0.0 and L[-1] == drum_path.total
    chord = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert np.max(np.abs(chord / np.diff(L) - 1.0)) < 1e-9
    # a range that ends a hair after a piece's end
    edge = drum_path.L1[2]
    pts, L = S.polyline(drum_path, edge - 3.0, edge + 1e-7, 0.001)
    chord = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert np.max(np.abs(chord / np.diff(L) - 1.0)) < 1e-9
    pts, L = S.polyline(drum_path, 5.0, 5.0, 0.001)
    assert len(L) == 2 and np.allclose(pts[0], pts[1])


# ---------------------------------------------------------------------------------------------------------
# where the rope leaves, followers, fleet angles
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hand", [1, -1])
def test_tangency_sign(hand):
    """The rope from the leave point to the point it goes to must run on along the wound rope's own direction (the
    way L grows: the free rope is the part beyond the leave point) and square to the radius."""
    path = S.wind(drum(hand=hand, layers=2, r_max=math.inf))
    rng = np.random.default_rng(4)
    for L in rng.uniform(1.0, path.total - 1.0, 20):
        phi, a, r, _ = S.at(path, L)
        for alpha in (0.3, 2.0, -2.5):
            rho = 3.0 * r
            psi = float(S.tangency(rho, alpha, r, hand))
            P = np.array([r * math.cos(psi), r * math.sin(psi)])
            T = np.array([rho * math.cos(alpha), rho * math.sin(alpha)])
            go = (T - P) / np.linalg.norm(T - P)
            assert abs(go @ P) < 1e-9                               # square to the radius
            # the wound rope's direction at the same place round the drum (turn the path's point there)
            t = S.tangent(path, L)
            c, s = math.cos(psi - float(phi)), math.sin(psi - float(phi))
            t2 = np.array([c * t[0] - s * t[1], s * t[0] + c * t[1]])
            assert go @ (t2 / np.linalg.norm(t2)) > 0.99
    # vectorised, and a point inside the circle leaves where it lies
    assert S.tangency(np.array([1.0, 2.0]), 0.0, 1.0, 1).shape == (2,)
    assert float(S.tangency(0.5, 0.7, 1.0, 1)) == pytest.approx(0.7)


def test_arm_angle():
    c_s = np.array([0.0, 0.0])
    c_a = np.array([1.5, 0.2])
    a0 = np.array([0.9, 0.5])
    targets = np.linspace(0.85, 2.15, 30)      # the arm reaches 0.843 … 2.18 from c_s
    for prefer in (0.0, 0.8, -0.8):
        t = S.arm_angle(c_s, c_a, a0, targets, prefer)
        assert np.all(np.isfinite(t))
        for ti, rt in zip(t, targets):
            c, s = math.cos(ti), math.sin(ti)
            v = a0 - c_a
            pt = c_a + np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])
            assert abs(np.linalg.norm(pt - c_s) - rt) < 1e-9
            # the other answer is not nearer to prefer
            others = [x for x in _both(c_s, c_a, a0, rt) if abs(x - ti) > 1e-3]     # the brute-force grid
            for o in others:
                o = o + 2 * math.pi * round((prefer - o) / (2 * math.pi))
                assert abs(ti - prefer) <= abs(o - prefer) + 1e-4
    # unreachable: nan
    assert np.isnan(S.arm_angle(c_s, c_a, a0, 5.0))
    assert np.isnan(S.arm_angle(c_s, c_a, a0, 0.6))
    # the answer stays near prefer over whole turns
    assert abs(float(S.arm_angle(c_s, c_a, a0, 1.5, prefer=4 * math.pi)) - 4 * math.pi) < math.pi


def _both(c_s, c_a, a0, rt):
    """Both turns, by brute force: scan the circle and refine."""
    v = a0 - c_a
    t = np.linspace(-math.pi, math.pi, 100001)
    pts = c_a[None, :] + np.stack([np.cos(t) * v[0] - np.sin(t) * v[1], np.sin(t) * v[0] + np.cos(t) * v[1]], 1)
    f = np.linalg.norm(pts - c_s, axis=1) - rt
    i = np.nonzero(np.sign(f[:-1]) != np.sign(f[1:]))[0]
    return [float(t[k]) for k in i]


def test_fleet_angles():
    path = S.wind(drum(layers=3, r_max=math.inf))
    s = path.spool
    middle = 0.5 * (s.a_lo + s.a_hi)
    q = np.array([0.0, -0.8, middle])                   # 800 mm in front of the drum's middle
    lo, hi = S.fleet_angles(path, q)
    r_top = float(S.layer_radius(path, 2))
    half = 0.5 * (s.a_hi - s.a_lo - s.d)
    expect = math.atan2(half, math.sqrt(0.8 ** 2 - r_top ** 2))
    assert lo == pytest.approx(expect, rel=1e-12) and hi == pytest.approx(expect, rel=1e-12)
    assert expect == pytest.approx(math.atan(half / 0.8), rel=0.05)        # atan(half span / 800)-ish
    assert lo > 0 and hi > 0
    lo, hi = S.fleet_angles(path, q + np.array([0.0, 0.0, 0.05]))          # off the middle: one end steeper
    assert hi < lo
    with pytest.raises(ValueError):
        S.fleet_angles(S.wind(carousel()), q)


# ---------------------------------------------------------------------------------------------------------
# reading a CAD leave point, the stack, status
# ---------------------------------------------------------------------------------------------------------

def test_wound_at_round_trip(drum_path, carousel_path):
    rng = np.random.default_rng(5)
    for path in (drum_path, carousel_path):
        main = np.nonzero(np.isin(path.kind, [S.HELIX, S.FLAT]))[0]
        i = rng.choice(main, 300)
        L = path.L0[i] + rng.uniform(0.02, 0.98, 300) * (path.L1[i] - path.L0[i])
        _, a, r, _ = S.at(path, L)
        assert np.max(np.abs(S.wound_at(path, a, r) - L)) < 1e-9
        # a CAD point a little off still finds its place
        L1 = float(L[0])
        _, a1, r1, _ = S.at(path, L1)
        assert abs(S.wound_at(path, float(a1) + 1e-4, float(r1)) - L1) < 0.02


def test_stack(drum_path, carousel_path):
    for path, drawn in ((drum_path, 2), (carousel_path, 1)):
        s = path.spool
        W0 = path.total
        steps = S.stack_breaks(path, W0, 0.0, W0, drawn)
        # the steps lie where a layer's own pieces begin, for every layer from `drawn` up
        firsts = [W0 - S._first_of_layer(path, k) for k in range(drawn, path.layer_count)]
        assert np.allclose(np.sort(steps), np.sort(firsts))
        p = np.linspace(0.0, W0, 4001)
        L_low, solid = S.stack(path, W0, p, drawn)
        # L_low and solid only change at the steps
        changed = np.nonzero(np.diff(L_low) != 0)[0]
        for c in changed:
            assert np.any((steps > p[c]) & (steps <= p[c + 1]))
        assert np.all(L_low <= np.maximum(W0 - p, 0.0) + 1e-9)
        for pi, lo, so in zip(p[::97], L_low[::97], solid[::97]):
            k = int(S.at(path, W0 - pi)[3])
            low = max(k - drawn + 1, 0)
            assert lo == pytest.approx(S.layer_start(path, low))
            if s.kind == S.DRUM:
                expect = 0.0 if low == 0 else float(S.layer_radius(path, low - 1)) + s.d / 2
            else:
                expect = low * s.d
            assert so == pytest.approx(expect)
        # full: the solid is there; empty: nothing
        assert solid[0] > 0.0 and solid[-1] == 0.0 and L_low[-1] == 0.0
    # at a step the value is the one after it
    path, W0 = drum_path, drum_path.total
    steps = S.stack_breaks(path, W0, 0.0, W0, 2)
    for st in steps:
        here = S.stack(path, W0, st, 2)
        after = S.stack(path, W0, st + 1e-6, 2)
        assert here[0] == after[0] and here[1] == after[1]


def test_status(drum_path):
    W0 = 50.0
    assert S.status(drum_path, W0, 10.0) == ""
    assert S.status(drum_path, W0, 50.0) == ""
    assert S.status(drum_path, W0, 50.1) == "empty"
    assert S.status(drum_path, drum_path.total + 1.0, 0.5) == "full"
    out = S.status(drum_path, W0, np.array([0.0, 60.0]))
    assert list(out) == ["", "empty"]
    assert S.capacity(drum_path) == drum_path.total
