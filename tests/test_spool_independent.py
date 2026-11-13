"""Task 0080, independent tests: drums and carousels, written from the brief (tasks/0080-spooling.md: Goal, Scope,
"Accuracy and speed (tests)", Design) by an agent that did not write the code.

The expected values are worked out here on their own – a helix, a climb and an Archimedean spiral integrated in this
file, the tangent from a point to a circle chosen by the rope's own direction, the fleet angle from the right
triangle – never with the module's functions. The module is only asked for what it promises to give.

A test marked ``# FAULT:`` fails because of a fault found in the code (see the comment); it is kept failing on
purpose, not loosened.

Part 1 needs no Blender (``core/spool.py``). Part 2 runs Blender as a Python module on the test model
(tests/data/test_spool.step, tools/make_test_spool.py) as ``spool.set_up_test_model`` sets it up. Part 3 starts the
real Blender once with Python scripts in the file disabled (``-Y``).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from fresing_render.core import spool as S  # noqa: E402

DEG = math.pi / 180.0
COS30 = math.cos(math.radians(30.0))
ANGLE_TOL = 0.01 * DEG          # brief: drum angle within 0.01° of the exact helix
LEAVE_TOL = 0.0005              # brief: leave point on its layer's circle within 0.5 mm
LENGTH_TOL = 0.001              # brief: on the spool + paid out = wound within 1 mm
TURN_TOL = 0.001                # brief: carousel turn per metre within 0.1 %
VOLUME_TOL = 0.01               # brief: carousel volume within 1 %


# =====================================================================================================================
# my own wound path (from the brief and the Design, not from the module)
# =====================================================================================================================

class Ref:
    """A wound path built here: pieces in which phi, a and r change linearly with one parameter u; the length along
    each piece integrated on a fine grid (exact for a helix). ``at(L)`` -> (phi, a, r, layer)."""

    def __init__(self):
        self.pieces = []        # (phi0, phi1, a0, a1, r0, r1, layer, kind)

    def add(self, dphi, a0, a1, r0, r1, layer, kind):
        phi0 = self.pieces[-1][1] if self.pieces else 0.0
        self.pieces.append((phi0, phi0 + dphi, a0, a1, r0, r1, layer, kind))

    def finish(self, n=4001):
        Ls, us, idx = [], [], []
        L = 0.0
        self.L0 = []
        for i, (p0, p1, a0, a1, r0, r1, _k, _kind) in enumerate(self.pieces):
            self.L0.append(L)
            u = np.linspace(0.0, 1.0, n if (r1 != r0) else 2)
            r = r0 + (r1 - r0) * u
            speed = np.sqrt((r * (p1 - p0)) ** 2 + (r1 - r0) ** 2 + (a1 - a0) ** 2)
            if len(u) == 2:
                cum = np.array([0.0, speed[0]])
            else:   # Simpson on pairs of intervals, then the half-steps by the trapezoid between them
                h = u[1] - u[0]
                cum = np.concatenate([[0.0], np.cumsum(0.5 * h * (speed[1:] + speed[:-1]))])
                simpson = h / 3.0 * (speed[0] + speed[-1] + 4 * speed[1:-1:2].sum() + 2 * speed[2:-1:2].sum())
                cum *= simpson / cum[-1]
            Ls.append(L + cum)
            us.append(u)
            idx.append(np.full(len(u), i))
            L += cum[-1]
        self.total = L
        self.L0 = np.array(self.L0 + [L])
        self._L = Ls
        self._u = us
        return self

    def at(self, L):
        L = np.clip(np.atleast_1d(np.asarray(L, dtype=float)), 0.0, self.total)
        out = np.zeros((len(L), 4))
        i = np.clip(np.searchsorted(self.L0, L, side="right") - 1, 0, len(self.pieces) - 1)
        for k in np.unique(i):
            m = i == k
            p0, p1, a0, a1, r0, r1, layer, _kind = self.pieces[k]
            u = np.interp(L[m], self._L[k], self._u[k])
            out[m, 0] = p0 + (p1 - p0) * u
            out[m, 1] = a0 + (a1 - a0) * u
            out[m, 2] = r0 + (r1 - r0) * u
            out[m, 3] = layer
        return out[:, 0], out[:, 1], out[:, 2], out[:, 3].astype(int)


def ref_drum(d, r1, a_lo, a_hi, pitch, layers, start=1, hand=1, climb=math.pi / 2):
    """Brief + Design: layer k at r1 + k * d * cos 30°, rope middles from a_lo + d/2 to a_hi - d/2, one helix per
    layer (the hand reversing each layer), a climb of ``climb`` of turn at the flange between layers (a stays)."""
    ref = Ref()
    lo, hi = a_lo + d / 2, a_hi - d / 2
    for k in range(layers):
        r = r1 + k * d * COS30
        going = start if k % 2 == 0 else -start
        a_from, a_to = (lo, hi) if going > 0 else (hi, lo)
        ref.add(hand * 2 * math.pi * (hi - lo) / pitch, a_from, a_to, r, r, k, "HELIX")
        if k < layers - 1:
            ref.add(hand * climb, a_to, a_to, r, r + d * COS30, k, "CLIMB")
    return ref.finish()


def ref_carousel(d, r_a, r_b, a_bot, layers, start=1, hand=1, climb=math.pi / 2):
    """Brief + Design (and the module's doc: the climb takes the first ``climb`` of the next layer's spiral, rising
    by d): layer k's rope middles at a_bot + d/2 + k d; an Archimedean spiral between the rope middles r_a and r_b,
    the radius changing by d per turn."""
    ref = Ref()
    turn_all = 2 * math.pi * (r_b - r_a) / d
    for k in range(layers):
        out = start if k % 2 == 0 else -start
        r_from = r_a if out > 0 else r_b
        a = a_bot + d / 2 + k * d
        c = 0.0 if k == 0 else min(climb, turn_all)
        r_c = r_from + out * d * c / (2 * math.pi)
        if c > 0:
            ref.add(hand * c, a - d, a, r_from, r_c, k - 1, "CLIMB")
        ref.add(hand * (turn_all - c), a, a, r_c, r_from + out * (r_b - r_a), k, "FLAT")
    return ref.finish()


def my_tangent_angle(q_xy, r, hand):
    """Where a rope wound with ``hand`` on the circle r leaves towards the point q (seen along the axis): of the two
    tangent points the one where the rope's own direction (the way it is paid out) points at q."""
    rho, alpha = math.hypot(*q_xy), math.atan2(q_xy[1], q_xy[0])
    spread = math.acos(min(1.0, r / rho))
    for psi in (alpha + spread, alpha - spread):
        t = hand * np.array([-math.sin(psi), math.cos(psi)])
        if float(t @ (np.asarray(q_xy) - r * np.array([math.cos(psi), math.sin(psi)]))) > 0.0:
            return psi
    raise AssertionError("no tangent")


# =====================================================================================================================
# Part 1: core/spool.py, no Blender
# =====================================================================================================================

DRUM = dict(d=0.020, r1=0.160, a_lo=-0.200, a_hi=0.200, pitch=0.0212)


@pytest.mark.parametrize("start,hand", [(1, 1), (-1, -1), (1, -1)])
def test_core_drum_path_is_my_helix(start, hand):
    """Every point of the wound path (angle, place along the axis, radius) against the helix + climbs built here."""
    sp = S.Spool(S.DRUM, layers=6, start=start, hand=hand, **DRUM)
    path = S.wind(sp)
    ref = ref_drum(layers=6, start=start, hand=hand, **DRUM)
    assert path.total == pytest.approx(ref.total, abs=LENGTH_TOL)
    L = np.linspace(0.0, ref.total, 6007)
    phi, a, r, k = S.at(path, L)
    phi_r, a_r, r_r, k_r = ref.at(L)
    assert np.abs(phi - phi_r).max() < ANGLE_TOL
    assert np.abs(a - a_r).max() < LEAVE_TOL and np.abs(r - r_r).max() < LEAVE_TOL
    helix = np.array([ref.pieces[i][7] == "HELIX" for i in
                      np.clip(np.searchsorted(ref.L0, L, side="right") - 1, 0, len(ref.pieces) - 1)])
    assert np.array_equal(np.asarray(k)[helix], k_r[helix])         # the layer number on every helix


def test_core_drum_angle_table_over_100_m_across_layers():
    """The spool's turn as a table (keys at the breaks, straight between: what the driver does) against my exact
    drum angle at 4,000 payouts over 100 m that cross at least three layers."""
    sp = S.Spool(S.DRUM, layers=7, **DRUM)
    path = S.wind(sp)
    ref = ref_drum(layers=7, **DRUM)
    W0 = ref.total - 1.0
    keys = S.breaks(path, W0, 0.0, 100.0)
    table = S.angle_table(path, W0, None, keys)
    p = np.random.default_rng(1).uniform(0.0, 100.0, 4000)
    phi_p = ref.at(W0 - p)[0]
    phi_0 = ref.at(W0)[0]
    want = -(phi_p - phi_0)                                         # theta = -(phi(W0 - p) - phi(W0)) for psi = 0
    got = np.interp(p, keys, table)
    assert len(set(ref.at(W0 - p)[3])) >= 3
    assert np.abs(got - want).max() < ANGLE_TOL, math.degrees(np.abs(got - want).max())


def test_core_lebus_wraps_cross_over_only_in_the_two_zones():
    """Lebus: in a layer the rope runs square to the axis and moves over by half a pitch in two crossover zones per
    turn, each 35° of turn, fixed on the drum (the same drum angles in every layer); the layer still fills flange to
    flange; in the parallel runs the drum turns 1 / r per metre."""
    w, at0 = math.radians(35.0), 0.3
    sp = S.Spool(S.DRUM, layers=3, groove=S.LEBUS, crossover=w, crossover_at=at0, **DRUM)
    path = S.wind(sp)
    L = np.linspace(0.0, path.total, 200001)
    phi, a, r, k = S.at(path, L)
    da = np.diff(a)
    mid_phi = 0.5 * (phi[1:] + phi[:-1])
    moving = np.abs(da) > 1e-12
    same_layer = np.diff(k) == 0
    flat_r = np.abs(np.diff(r)) < 1e-12                               # not on a climb
    x = np.mod(mid_phi - at0, math.pi)
    sel = moving & same_layer & flat_r
    assert sel.any()
    step = float(np.abs(np.diff(phi)).max())                       # (a sample may straddle a zone's edge)
    assert np.all((x[sel] < w + step) | (x[sel] > math.pi - step)), "the rope moved over outside a crossover zone"
    # half a pitch per zone: the rope's place along the axis while it crosses one whole zone
    pitch = DRUM["pitch"]
    shift_per_rad = np.abs(da[sel]) / np.abs(np.diff(phi)[sel])
    assert np.median(shift_per_rad) == pytest.approx(0.5 * pitch / w, rel=1e-3)
    # every layer fills from flange to flange
    for layer in range(3):
        m = k == layer
        assert np.ptp(a[m]) == pytest.approx(DRUM["a_hi"] - DRUM["a_lo"] - DRUM["d"], abs=1e-6)
        assert np.median(r[m]) == pytest.approx(DRUM["r1"] + layer * DRUM["d"] * COS30, abs=1e-9)
    # parallel runs: 1 / r per metre
    par = (~moving) & same_layer & flat_r
    rate = np.abs(np.diff(phi)[par] / np.diff(L)[par])
    assert np.allclose(rate, 1.0 / 0.5 / (r[1:][par] + r[:-1][par]), rtol=1e-6)


def test_core_carousel_radius_is_my_archimedean_spiral():
    """Layer 0 of a carousel: the radius after L metres of an Archimedean spiral from the core, worked out from my own
    arc-length formula (r = r_a + b theta, s(theta) by the closed form)."""
    d, r_a, r_b = 0.04, 0.34, 0.84
    sp = S.Spool(S.CAROUSEL, d=d, r_in=r_a - d / 2, r_out=r_b + d / 2, a_bot=0.0, layers=3)
    path = S.wind(sp)
    b = d / (2 * math.pi)

    def s_of(r):    # arc length of r = b * t from r = 0 to r, closed form
        t = r / b
        return 0.5 * b * (t * math.sqrt(1 + t * t) + math.asinh(t))
    s0 = s_of(r_a)
    layer0 = s_of(r_b) - s0
    rs = np.linspace(r_a + 0.001, r_b - 0.001, 300)
    Ls = np.array([s_of(r) - s0 for r in rs])
    phi, a, r, k = S.at(path, Ls)
    assert np.abs(r - rs).max() < 1e-5
    assert np.all(k == 0)
    assert np.abs(np.abs(phi) - (rs - r_a) / b).max() < ANGLE_TOL
    assert a.max() - a.min() < 1e-12 and a[0] == pytest.approx(d / 2)
    # the whole carousel against mine (climbs included)
    ref = ref_carousel(d, r_a, r_b, 0.0, 3)
    assert ref.at(np.array([layer0]))[2][0] == pytest.approx(r_b, abs=1e-6)
    assert path.total == pytest.approx(ref.total, abs=LENGTH_TOL)


def test_core_carousel_turn_per_metre_within_a_tenth_percent_everywhere():
    """The carousel's turn as a table (straight between keys): its slope in every piece against the exact turn per
    metre at both ends of the piece, 1 / sqrt(r^2 + b^2 + (da/dphi)^2), at every radius of every layer."""
    d = 0.04
    sp = S.Spool(S.CAROUSEL, d=d, r_in=0.32, r_out=0.86, a_bot=0.0, layers=4, hand=-1)
    path = S.wind(sp)
    W0 = path.total
    p = S.breaks(path, W0, 0.0, W0)
    theta = S.angle_table(path, W0, None, p)
    slope = np.abs(np.diff(theta) / np.diff(p))
    b = d / (2 * math.pi)
    # the rise along the axis per radian in each interval (a climb rises by d over its turn; elsewhere 0)
    phi_lo, a_lo, _r, _k = S.at(path, W0 - p[:-1] - 1e-7)
    phi_hi, a_hi, _r, _k = S.at(path, W0 - p[1:] + 1e-7)
    rise = np.abs(a_hi - a_lo) / np.maximum(np.abs(phi_hi - phi_lo), 1e-12)
    for end in (p[:-1] + 1e-7, p[1:] - 1e-7):
        _phi, a, r, _k = S.at(path, W0 - end)
        exact = 1.0 / np.sqrt(r * r + b * b + rise * rise)
        err = np.abs(slope / exact - 1.0)
        assert err.max() < TURN_TOL, (err.max(), r[np.argmax(err)])


def test_core_carousel_solid_holds_the_cable_it_stands_for():
    """The full layers drawn as one solid ring hold the same cable as the rope they stand for: the rope of k full
    layers (length x section) against the ring (``stack``'s height, between the rope middles) x pi/4 (square
    packing of round cable), within 1 %; checked from my own spiral lengths."""
    d, r_a, r_b = 0.04, 0.34, 0.84
    sp = S.Spool(S.CAROUSEL, d=d, r_in=r_a - d / 2, r_out=r_b + d / 2, a_bot=0.0, layers=5)
    path = S.wind(sp)
    ref = ref_carousel(d, r_a, r_b, 0.0, 5)
    W0 = path.total
    section = math.pi * d * d / 4
    for p in np.linspace(1.0, W0 - 1.0, 23):
        L_low, solid = S.stack(path, W0, np.array([p]), 1)
        L_low, solid = float(np.asarray(L_low).reshape(-1)[0]), float(np.asarray(solid).reshape(-1)[0])
        left = W0 - p
        layer_now = int(ref.at(left)[3][0])
        # the solid is as high as the full layers under the one paid out from
        assert solid == pytest.approx(layer_now * d, abs=1e-9), p
        if solid <= 0:
            continue
        ring = math.pi * (r_b ** 2 - r_a ** 2) * solid
        assert L_low * section == pytest.approx(ring * math.pi / 4, rel=VOLUME_TOL), p


def test_core_drawn_points_lie_on_the_path_and_chords_add_up_to_the_length():
    """Drawing: between the points the straight line stays within the sag of the true path; the leave point read off
    the drawn line (as the trimmed tube ends) lies on its layer's circle within 0.5 mm; the chords add up to the
    length along the path (so a trim by length cuts at the true L) within 1 mm over a whole spool."""
    sp = S.Spool(S.DRUM, layers=4, **DRUM)
    path = S.wind(sp)
    ref = ref_drum(layers=4, **DRUM)
    pts, Ls = S.polyline(path, 0.0, path.total, 0.0005)
    chords = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert abs(chords.sum() - (Ls[-1] - Ls[0])) < LENGTH_TOL
    assert np.allclose(chords, np.diff(Ls), rtol=1e-6, atol=1e-9)
    L = np.random.default_rng(2).uniform(0.0, path.total, 3000)
    drawn = np.stack([np.interp(L, Ls, pts[:, i]) for i in range(3)], axis=-1)
    phi, a, r, k = ref.at(L)
    radius = np.hypot(drawn[:, 0], drawn[:, 1])
    helix = np.isclose(r, DRUM["r1"] + k * DRUM["d"] * COS30, atol=1e-9)
    assert np.abs(radius - r)[helix].max() < LEAVE_TOL
    assert np.abs(drawn[:, 2] - a).max() < LEAVE_TOL
    true = np.stack([r * np.cos(phi), r * np.sin(phi), a], axis=-1)
    assert np.linalg.norm(drawn - true, axis=1).max() < 0.0005 + 1e-6


@pytest.mark.parametrize("hand", [1, -1])
def test_core_tangency_is_the_tangent_the_rope_runs_along(hand):
    rng = np.random.default_rng(3)
    for _ in range(50):
        r = rng.uniform(0.1, 0.5)
        q = rng.uniform(-3, 3, 2)
        if np.hypot(*q) < r * 1.2:
            continue
        psi = float(S.tangency(math.hypot(*q), math.atan2(q[1], q[0]), r, hand))
        want = my_tangent_angle(q, r, hand)
        assert math.remainder(psi - want, 2 * math.pi) == pytest.approx(0.0, abs=1e-9)


def test_core_arm_angle_brings_the_guide_over_the_radius():
    rng = np.random.default_rng(4)
    n = 0
    for _ in range(200):
        c_a, a0 = rng.uniform(-2, 2, 2), rng.uniform(-2, 2, 2)
        target = rng.uniform(0.1, 2.5)
        prefer = rng.uniform(-1, 1)
        t = float(S.arm_angle(np.zeros(2), c_a, a0, target, prefer=prefer))
        v = a0 - c_a
        reach = (abs(np.hypot(*c_a) - np.hypot(*v)), np.hypot(*c_a) + np.hypot(*v))
        if not (reach[0] + 1e-9 < target < reach[1] - 1e-9):
            assert not math.isfinite(t)
            continue
        n += 1
        moved = c_a + np.array([math.cos(t) * v[0] - math.sin(t) * v[1], math.sin(t) * v[0] + math.cos(t) * v[1]])
        assert np.hypot(*moved) == pytest.approx(target, abs=1e-9)
        # of the two turns that reach it (mirror images about the line through both centres), the one nearer prefer
        beta = math.atan2(v[1], v[0])
        gamma = math.atan2(c_a[1], c_a[0])                  # the direction from the spool's axis to the pivot
        mirror = 2 * (gamma - beta) - t                     # the other answer: the guide mirrored about that line
        mirror += 2 * math.pi * round((prefer - mirror) / (2 * math.pi))
        assert abs(t - prefer) <= abs(mirror - prefer) + 1e-9
    assert n > 50


def test_core_fleet_angles_from_the_right_triangle():
    """The rope from the top layer at each flange to the sheave: the angle against the plane square to the axis."""
    sp = S.Spool(S.DRUM, layers=3, **DRUM)
    path = S.wind(sp)
    q = np.array([0.8, 0.3, 0.05])
    r_top = DRUM["r1"] + 2 * DRUM["d"] * COS30
    run = math.sqrt(q[0] ** 2 + q[1] ** 2 - r_top ** 2)
    lo = math.atan2(abs(q[2] - (DRUM["a_lo"] + DRUM["d"] / 2)), run)
    hi = math.atan2(abs(q[2] - (DRUM["a_hi"] - DRUM["d"] / 2)), run)
    got = S.fleet_angles(path, q)
    assert got[0] == pytest.approx(lo, abs=1e-9) and got[1] == pytest.approx(hi, abs=1e-9)
    assert got[0] > got[1]                      # the flange further from the sheave has the larger angle


def test_core_wound_at_finds_the_length_back():
    """The wound length read from where the CAD rope leaves: a point of the path -> its L, within 1 mm."""
    sp = S.Spool(S.DRUM, layers=4, **DRUM)
    path = S.wind(sp)
    ref = ref_drum(layers=4, **DRUM)
    rng = np.random.default_rng(5)
    for L in rng.uniform(0.5, ref.total - 0.5, 40):
        i = int(np.searchsorted(ref.L0, L, side="right") - 1)
        if ref.pieces[i][7] != "HELIX":
            continue
        _phi, a, r, _k = ref.at(L)
        assert S.wound_at(path, float(a[0]), float(r[0])) == pytest.approx(L, abs=LENGTH_TOL)


def test_core_empty_and_full_and_refusals_in_plain_words():
    sp = S.Spool(S.DRUM, layers=2, **DRUM)
    path = S.wind(sp)
    assert S.status(path, 10.0, 11.0) == "empty"
    assert S.status(path, path.total + 1.0, 0.0) == "full"
    assert S.status(path, 10.0, 3.0) == ""
    for bad in (dict(d=0.0), dict(a_hi=-0.19)):
        numbers = dict(DRUM, **bad)
        with pytest.raises(ValueError) as e:
            S.wind(S.Spool(S.DRUM, layers=2, **numbers))
        assert "Traceback" not in str(e.value) and len(str(e.value)) > 10


# =====================================================================================================================
# Part 2: Blender as a Python module, the test model
# =====================================================================================================================

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, spool  # noqa: E402

MODEL = os.path.join(HERE, "data", "test_spool.step")
_DIRTY = [True]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spool_independent"))


def _build_scene(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    spool.set_up_test_model(sc)
    update()
    return bpy.context.scene


@pytest.fixture()
def made(folder):
    """The set-up test model, shared by the tests that put everything back (payouts at 0)."""
    if _DIRTY[0] or spool.find(bpy.context.scene, "Drum") is None:
        _build_scene(folder)
        _DIRTY[0] = False
    sc = bpy.context.scene
    yield sc
    sc = bpy.context.scene
    try:
        for name in ("Wire", "Power cable"):
            if paths.find(sc, name) is not None:
                pay(sc, name, 0.0)
    except Exception:
        _DIRTY[0] = True


@pytest.fixture()
def fresh(folder):
    """A test model of its own (the test changes it for good)."""
    sc = _build_scene(folder)
    _DIRTY[0] = True
    yield sc
    _DIRTY[0] = True


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def pay(sc, cable, metres):
    it = paths.find(sc, cable)
    joints.set_value(joints.find(sc, it.joint), -metres if it.reverse else metres, use_limits=False)
    update()
    paths.refresh(sc)
    update()


def leave_world(sc, cable):
    return np.asarray(paths.shape_now(sc, paths.find(sc, cable))[0], dtype=float)


def to_spool(sc, sp, x):
    fr = spool.frame_cad(sc, sp, {})
    return (np.linalg.inv(fr) @ np.r_[x, 1.0])[:3]


def spool_value(sc, sp):
    """The spool's turn about the spool frame's +z: what the motion empty really has."""
    return joints.find(sc, sp.joint).motion.rotation_euler[2] * sp.zsign


def my_drum(sc, sp):
    d = float(paths.find(sc, sp.cable).diameter)
    pitch = float(sp.pitch) if sp.pitch > 0 else 1.06 * d
    n = int(math.floor((sp.r_max - sp.r1) / (d * COS30) + 1e-9)) + 1
    return ref_drum(d, float(sp.r1), float(sp.a_lo), float(sp.a_hi), pitch, n, start=-1 if sp.other_side else 1,
                    hand=int(sp.hand))


def rope_curve(sc, sp):
    """The drawn rope on the spool, as Blender evaluates it: (centres of its rings, world, ordered along it; their
    fr_s)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ob = sp.owner
    ev = ob.evaluated_get(dg)
    me = ev.data
    n = len(me.vertices)
    if n == 0:
        return np.zeros((0, 3)), np.zeros(0)
    co = np.empty(3 * n, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(float)
    s = np.empty(n, np.float32)
    me.attributes[spool.S_ATTR].data.foreach_get("value", s)
    keys, inv = np.unique(s, return_inverse=True)
    centres = np.zeros((len(keys), 3))
    np.add.at(centres, inv, co)
    centres /= np.bincount(inv)[:, None]
    m = np.array(ob.matrix_world)
    centres = centres @ m[:3, :3].T + m[:3, 3]
    return centres, keys.astype(float)


# ---------------------------------------------------------------------------------------------------------------------
# accuracy
# ---------------------------------------------------------------------------------------------------------------------

def test_drum_turn_against_my_helix_and_tangent_over_100_m(made):
    """The drum's turn (as Blender drives it) from 50 m wound on to 50 m paid out against my own: the leave point
    stays where the rope runs off tangent towards the fairlead (my tangent from the rope's own direction), the rope
    on the drum follows my helix and climbs. Within 0.01°, over at least three layers."""
    sc = made
    sp = spool.find(sc, "Drum")
    ref = my_drum(sc, sp)
    W0 = float(sp.wound)
    q = np.array(sp.q, dtype=float)
    hand = int(sp.hand)

    def theta(p):
        phi, _a, r, _k = ref.at(np.array([W0 - p, W0]))
        psi = my_tangent_angle(q[:2], r[0], hand)
        psi0 = my_tangent_angle(q[:2], r[1], hand)
        return math.remainder(psi - psi0, 2 * math.pi) - (phi[0] - phi[1])

    layers, worst = set(), 0.0
    pay(sc, "Wire", 0.0)
    assert abs(spool_value(sc, sp)) < 1e-6                                # the CAD pose at 0 paid out
    for p in np.linspace(-50.0, 50.0, 41):
        if W0 - p < 0:
            continue
        pay(sc, "Wire", float(p))
        worst = max(worst, abs(spool_value(sc, sp) - theta(p)))
        layers.add(int(ref.at(W0 - p)[3][0]))
    assert len(layers) >= 3, layers
    assert math.degrees(worst) < 0.01, math.degrees(worst)


@pytest.mark.parametrize("name,cable", [("Drum", "Wire"), ("Carousel", "Power cable")])
def test_leave_point_on_its_layers_circle_at_random_payouts(made, name, cable):
    """Where the free cable starts: on the circle of the layer it comes off (radius and, on a drum, the place along
    the axis of my helix), within 0.5 mm, at 25 payouts picked at random."""
    sc = made
    sp = spool.find(sc, name)
    W0 = float(sp.wound)
    path = spool.path_of(sc, sp)
    ref = my_drum(sc, sp) if name == "Drum" else None
    worst = 0.0
    for p in np.random.default_rng(6).uniform(-30.0, min(W0 - 0.5, 45.0), 25):
        pay(sc, cable, float(p))
        loc = to_spool(sc, sp, leave_world(sc, cable))
        if ref is not None:
            _phi, a, r, _k = ref.at(W0 - p)
            err = max(abs(math.hypot(loc[0], loc[1]) - r[0]), abs(loc[2] - a[0]))
        else:   # carousel: the layer's height and the turn's radius (the radius from the module's own path)
            _phi, a, r, _k = S.at(path, np.array([W0 - p]))
            err = max(abs(math.hypot(loc[0], loc[1]) - float(r[0])), abs(loc[2] - float(a[0])))
        worst = max(worst, err)
    assert worst < LEAVE_TOL, worst * 1000


def _kink_deg(sc, sp, cable):
    """How far (degrees) the free span leaving the spool turns away from the rope's own direction there (square to
    the radius, the way the rope is wound): 0 = no kink."""
    line = np.asarray(paths.shape_now(sc, paths.find(sc, cable)), dtype=float)
    start = to_spool(sc, sp, line[0])
    far = next(x for x in line[1:] if np.linalg.norm(x - line[0]) > 0.05)
    ahead = to_spool(sc, sp, far) - start
    radial = start[:2] / np.linalg.norm(start[:2])
    flat = ahead[:2] / np.linalg.norm(ahead[:2])
    wound_way = int(sp.hand) * np.array([-radial[1], radial[0]])
    return math.degrees(math.acos(max(-1.0, min(1.0, float(wound_way @ flat)))))


def test_free_span_leaves_the_drum_along_the_tangent(made):
    """No kink where the rope leaves the drum: the free span runs square to the radius, the way the rope is wound
    (not back over the drum)."""
    sc = made
    sp = spool.find(sc, "Drum")
    for p in (-30.0, -5.0, 0.0, 2.5, 11.0, 30.0):
        pay(sc, "Wire", p)
        assert _kink_deg(sc, sp, "Wire") < 0.5, p


@pytest.mark.parametrize("name,cable", [("Drum", "Wire"), ("Carousel", "Power cable")])
def test_drawn_rope_plus_paid_out_is_what_was_wound(made, name, cable):
    """Read off the evaluated rope on the spool: it ends at W0 - p (on the spool + paid out = wound, within 1 mm);
    its drawn length is that length; the free cable starts where it ends (within 1 mm)."""
    sc = made
    sp = spool.find(sc, name)
    W0 = float(sp.wound)
    for p in (-12.0, 0.0, 3.3, 20.0):
        pay(sc, cable, p)
        centres, s = rope_curve(sc, sp)
        assert len(s) > 2, p
        on_spool = W0 + s.max()
        # FAULT (Drum): the trimmed rope ends up to 1.7 mm past W0 - p (and past the free cable's start), growing
        # with the length trimmed: the "End" input is right (W0 - p), the polyline's chords add up to L, but Blender's
        # Trim Curve measures the length along ~2,000 segments in 32-bit floats. On the test drum: p = -12 m (End
        # 61.6 m) 1.70 mm, p = 0 1.10 mm, p = 20 m 0.24 mm; a longer rope on a bigger spool is worse (blender/spool.py
        # _draw / _build_tree: one curve from the anchor, trimmed by its whole length).
        assert on_spool + p == pytest.approx(W0, abs=LENGTH_TOL), p
        drawn = np.linalg.norm(np.diff(centres, axis=0), axis=1).sum()
        assert drawn == pytest.approx(s.max() - s.min(), abs=LENGTH_TOL), p
        gap = float(np.linalg.norm(centres[-1] - leave_world(sc, cable)))
        assert gap < LENGTH_TOL, (p, gap * 1000)


def test_carousel_solid_and_top_layer_keep_the_cable(made):
    """The carousel's solid below the drawn layer and the rope drawn on top: (the solid's evaluated volume x pi/4 for
    the packing) + drawn length x section = (wound - paid out) x section, within 1 %."""
    sc = made
    sp = spool.find(sc, "Carousel")
    W0 = float(sp.wound)
    d = float(paths.find(sc, sp.cable).diameter)
    section = math.pi * d * d / 4
    solid = spool._made(sc, sp, "solid")
    for p in (-60.0, 0.0, 30.0, 80.0):
        pay(sc, "Power cable", p)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = solid.evaluated_get(dg)
        me = ev.data
        m = np.array(ev.matrix_world)
        co = np.array([m[:3, :3] @ np.array(v.co) + m[:3, 3] for v in me.vertices])
        vol = 0.0
        for poly in me.polygons:
            idx = list(poly.vertices)
            for i in range(1, len(idx) - 1):
                vol += np.dot(co[idx[0]], np.cross(co[idx[i]], co[idx[i + 1]])) / 6.0
        vol = abs(vol)
        _c, s = rope_curve(sc, sp)
        drawn = s.max() - s.min()
        assert vol * math.pi / 4 + drawn * section == pytest.approx((W0 - p) * section, rel=VOLUME_TOL), p


def test_carousel_solid_is_as_wide_as_the_layers_on_it(made):
    """The solid under the drawn layer looks like the layers it stands for: its outer and inner radius are those of
    the coil (the outer and inner edge of the cable, as the CAD coil and the drawn layer on top show), not half a
    cable narrower on each side."""
    sc = made
    sp = spool.find(sc, "Carousel")
    d = float(paths.find(sc, sp.cable).diameter)
    pay(sc, "Power cable", 0.0)
    solid = spool._made(sc, sp, "solid")
    dg = bpy.context.evaluated_depsgraph_get()
    ev = solid.evaluated_get(dg)
    m = np.array(ev.matrix_world)
    co = np.array([m[:3, :3] @ np.array(v.co) + m[:3, 3] for v in ev.data.vertices])
    rho = np.array([math.hypot(*to_spool(sc, sp, x)[:2]) for x in co])
    # FAULT: the solid runs between the rope MIDDLES (r 0.34 .. 0.84 on the test model), while the cable on top and
    # the CAD coil run from r 0.32 to 0.86: the stack looks 20 mm narrower on each side than the layer lying on it
    # (blender/spool.py _solid_mesh uses core ring_radii = the rope middles).
    assert rho.max() == pytest.approx(float(sp.r_out) + d / 2, abs=0.002)
    assert rho.min() == pytest.approx(float(sp.r_in) - d / 2, abs=0.002)


def test_level_wind_rides_with_the_wrap_and_back(made):
    """The level wind follows the place along the drum of my helix (zig-zag: back at each layer)."""
    sc = made
    sp = spool.find(sc, "Drum")
    ref = my_drum(sc, sp)
    W0 = float(sp.wound)
    a0 = float(ref.at(W0)[1][0])
    lw = joints.find(sc, "Level wind")
    sign = None
    for p in np.linspace(-20.0, 30.0, 26):
        pay(sc, "Wire", float(p))
        want = float(ref.at(W0 - p)[1][0]) - a0
        got = joints.get_value(lw)
        if sign is None and abs(want) > 0.01:
            sign = math.copysign(1.0, got / want)
        if sign is not None:
            assert got == pytest.approx(sign * want, abs=LEAVE_TOL), p


# ---------------------------------------------------------------------------------------------------------------------
# what the owner reads
# ---------------------------------------------------------------------------------------------------------------------

def test_empty_and_overfull_said_in_plain_words(made):
    sc = made
    sp = spool.find(sc, "Drum")
    W0 = float(sp.wound)
    try:
        pay(sc, "Wire", W0 + 2.0)
        text, icon = spool.status(sc, spool.find(sc, "Drum"))
        assert icon == "ERROR" and "empty" in text.lower() and re.search(r"\b2\.00? m\b", text), text
        pay(sc, "Wire", -(spool.find(sc, "Drum").capacity - W0) - 3.0)
        text, icon = spool.status(sc, spool.find(sc, "Drum"))
        assert icon == "ERROR" and ("full" in text.lower() or "overfill" in text.lower()), text
        assert re.search(r"\b3\.00? m\b", text), text
    finally:
        pay(sc, "Wire", 0.0)
    assert spool.status(sc, spool.find(sc, "Drum"))[1] != "ERROR"


def test_build_warns_when_the_animation_empties_the_spool(made):
    """An animation that pays out more than is wound: Build says so, by name."""
    sc = made
    sp = spool.find(sc, "Drum")
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    b = next(b for b in a.blocks if b.joint == paths.find(sc, "Wire").joint)
    was = b.to_dist
    try:
        b.to_dist = float(sp.wound) + 5.0
        res = animation.bake(sc, a)
        warns = res["warnings"] if isinstance(res, dict) else res
        assert any("Drum" in w and "empty" in w for w in warns), warns
    finally:
        b.to_dist = was
        animation.clear_keys(sc)
        sc.frame_set(1)


def test_fleet_angle_warning_names_the_flange_and_the_angle(made):
    """Without the level wind the rope runs from the flanges to a fixed sheave: the panel and Build warn, with the
    angle and which end of the drum."""
    sc = made
    sp = spool.find(sc, "Drum")
    spool.remove_follower(sc, sp, 0)
    try:
        sp = spool.find(sc, "Drum")
        text, icon = spool.status(sc, sp)
        lo, hi = sp.fleet_lo, sp.fleet_hi
        assert icon == "ERROR" and f"{math.degrees(max(lo, hi)):.1f}°" in text, text
        assert "flange" in text, text
        a = sc.fresing.animations[spool.TEST_ANIMATION]
        warns = spool.bake(sc, a)
        w = next((w for w in warns if "fleet" in w.lower()), "")
        assert f"{math.degrees(max(lo, hi)):.1f}°" in w, warns
        # FAULT: Build's warning says only "at a flange" – the brief: the warning names the drum end
        # (blender/spool.py bake()).
        assert "at a flange" not in w and "flange" in w, w
    finally:
        spool.add_follower(sc, spool.find(sc, "Drum"), "Level wind")
    assert not spool.find(sc, "Drum").problem


def test_fleet_angle_names_the_right_flange_when_the_first_layer_starts_at_the_other(made):
    """The warning's "the flange it starts from" must follow which flange the first layer starts from."""
    sc = made
    sp = spool.find(sc, "Drum")
    spool.remove_follower(sc, sp, 0)
    sp = spool.find(sc, "Drum")
    try:
        texts = {}
        for other in (False, True):
            sp = spool.find(sc, "Drum")
            sp.other_side = other
            sp = spool.find(sc, "Drum")
            q = list(sp.q)
            q[2] = float(sp.a_hi) + 0.3            # the sheave beyond the a_hi flange: the a_lo end is the worse
            sp.q = q
            texts[other] = spool.status(sc, sp)[0]
            assert sp.fleet_lo > sp.fleet_hi
        # FAULT: the text says "at the flange it starts from" whenever the a_lo end is worse, also when the first
        # layer starts at the other (a_hi) flange (blender/spool.py status(): `lo >= hi` ignores other_side).
        assert texts[False] != texts[True], texts
    finally:
        sp = spool.find(sc, "Drum")
        sp.other_side = False
        spool.add_follower(sc, spool.find(sc, "Drum"), "Level wind")


# ---------------------------------------------------------------------------------------------------------------------
# behaviour
# ---------------------------------------------------------------------------------------------------------------------

def test_every_driver_is_plain_arithmetic(made):
    """Scripts off: every driver the spools made, and every coupling, is MAX / AVERAGE or a simple expression."""
    sc = made
    assert joints.couplings_simple(sc)
    seen = 0
    for ob in bpy.data.objects:
        ad = ob.animation_data
        if ad is None:
            continue
        for fc in ad.drivers:
            drv = fc.driver
            ok = drv.type in ("MAX", "MIN", "AVERAGE", "SUM") or (drv.type == "SCRIPTED" and drv.is_simple_expression)
            assert ok, (ob.name, fc.data_path, drv.expression)
            assert drv.is_valid, (ob.name, fc.data_path)
            seen += 1
    assert seen > 10


def test_built_animation_frames_in_any_order_are_the_same(made):
    """Build, then frames forwards, backwards and jumbled: the same cable shapes, the same drawn rope, the same
    turns."""
    sc = made
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    animation.bake(sc, a)
    try:
        frames = [1, 25, 50, 75, 100, 125, 150, 175, 200]

        def snap():
            out = []
            for cable, name in (("Wire", "Drum"), ("Power cable", "Carousel")):
                sp = spool.find(sc, name)
                out.append(np.asarray(paths.shape_now(sc, paths.find(sc, cable)), dtype=float).copy())
                out.append(rope_curve(sc, sp)[0].copy())
                out.append(np.array([spool_value(sc, sp)]))
            out.append(np.array([joints.get_value(joints.find(sc, "Level wind")),
                                 joints.get_value(joints.find(sc, "Arm slew"))]))
            return out

        seen = {}
        for order in (frames, frames[::-1], [100, 1, 200, 50, 175, 25, 150, 75, 125]):
            for f in order:
                sc.frame_set(f)
                update()
                got = snap()
                if f not in seen:
                    seen[f] = got
                    continue
                for x, y in zip(seen[f], got):
                    assert x.shape == y.shape and np.allclose(x, y, atol=1e-6), f
        # and it really moves
        assert not np.allclose(seen[1][2], seen[200][2])
    finally:
        animation.clear_keys(sc)
        sc.frame_set(1)


def test_off_shows_the_cad_coil_and_on_again_is_as_before(made):
    sc = made
    pay(sc, "Wire", 4.0)
    sp = spool.find(sc, "Drum")
    before = (float(sp.wound), spool_value(sc, sp), leave_world(sc, "Wire").copy(),
              np.array(joints.table_of(joints.find(sc, sp.joint))).copy())
    coil = sp.coil
    sp.enabled = False
    update()
    sp = spool.find(sc, "Drum")
    dg = bpy.context.evaluated_depsgraph_get()
    assert len(coil.evaluated_get(dg).data.vertices) > 100            # the CAD wire on the drum shows again
    assert not [o for o in bpy.data.objects if o.get(spool.TAG) == "Drum"]
    assert paths.find(sc, "Wire").a_kind != "SPOOL"
    assert not joints.find(sc, "Drum turn").couple_table and not joints.find(sc, "Level wind").couple_table
    text, icon = spool.status(sc, sp)
    assert icon != "ERROR" and "off" in text.lower()
    sp.enabled = True
    update()
    pay(sc, "Wire", 4.0)
    sp = spool.find(sc, "Drum")
    assert not sp.problem and paths.find(sc, "Wire").a_kind == "SPOOL"
    assert float(sp.wound) == pytest.approx(before[0], abs=1e-6)
    assert spool_value(sc, sp) == pytest.approx(before[1], abs=1e-6)
    assert np.linalg.norm(leave_world(sc, "Wire") - before[2]) < 1e-5
    assert np.allclose(np.array(joints.table_of(joints.find(sc, sp.joint))), before[3], atol=1e-9)
    dg = bpy.context.evaluated_depsgraph_get()
    assert len(coil.evaluated_get(dg).data.vertices) == 0             # the CAD coil hidden again


def test_reading_the_cable_again_keeps_its_spool_and_a_typed_length(made):
    sc = made
    sp = spool.find(sc, "Drum")
    W_cad = float(sp.wound)
    pay(sc, "Wire", 5.0)
    angle = spool_value(sc, sp)
    it = paths.find(sc, "Wire")
    paths.read_cad(sc, it, it.part)
    update()
    pay(sc, "Wire", 5.0)
    sp = spool.find(sc, "Drum")
    assert paths.find(sc, "Wire").a_kind == "SPOOL" and sp.enabled and not sp.problem
    assert float(sp.wound) == pytest.approx(W_cad, abs=1e-6)
    assert spool_value(sc, sp) == pytest.approx(angle, abs=1e-6)
    assert [f.joint for f in sp.followers] == ["Level wind"]
    # a typed length stays when the cable is read again
    try:
        sp.wound = 30.0
        it = paths.find(sc, "Wire")
        paths.read_cad(sc, it, it.part)
        sp = spool.find(sc, "Drum")
        assert float(sp.wound) == pytest.approx(30.0, abs=1e-6)
        pay(sc, "Wire", 1.0)
        spool.status(sc, spool.find(sc, "Drum"))
        assert float(spool.find(sc, "Drum").on_spool) == pytest.approx(29.0, abs=1e-3)
    finally:
        _DIRTY[0] = True


def test_a_typed_wound_length_on_the_drum(made):
    """The owner types another "Wound at the start" for the drum: the cable then leaves from another wrap; it must
    still leave the drum along its tangent (no kink), and the level wind must stand in line with THAT wrap (both
    hold with the length read from the CAD)."""
    sc = made
    try:
        pay(sc, "Wire", 0.0)
        sp = spool.find(sc, "Drum")
        lw = joints.find(sc, "Level wind")
        axis = np.array(spool.frame_cad(sc, sp, {}))[:3, 2]

        def offset():   # where the carriage stands along the drum against where the cable leaves it
            return float(axis @ (np.array(lw.motion.matrix_world.translation) - leave_world(sc, "Wire")))
        cad = offset()
        sp.wound = 30.0
        worst_lw, kink = 0.0, 0.0
        for p in (0.0, 2.0, 5.0):
            pay(sc, "Wire", p)
            worst_lw = max(worst_lw, abs(offset() - cad))
            kink = max(kink, _kink_deg(sc, spool.find(sc, "Drum"), "Wire"))
        # FAULT 1: the cable no longer leaves the drum along its tangent: the leave point moves to phi(W0 typed) +
        # phase, but `phase` (and so the drum's start angle) was fitted to the length read from CAD – changed() sets
        # the spool up again without reading – so the free span leaves the drum at a kink (139.6° here: it runs back
        # over the drum) for the whole animation (blender/spool.py changed() / _setup(read=False)).
        # FAULT 2: the level wind's table is a(W0 - p) - a(W0) of the TYPED length, added to where the carriage stands
        # in CAD (in line with the CAD wrap): typing 30 m instead of 49.6 m leaves the carriage 31.7 mm off the wrap
        # for the whole animation, and the panel then shows a fleet angle of 2.3° (tables(), ACROSS: `a - a0`).
        assert kink < 0.5 and worst_lw < 0.002, f"kink {kink:.1f}°, level wind off the wrap {worst_lw * 1000:.1f} mm"
    finally:
        _DIRTY[0] = True


def test_a_typed_wound_length_on_the_carousel_keeps_the_arm_over_the_turn(made):
    sc = made
    try:
        sp = spool.find(sc, "Carousel")
        sp.wound = 120.0
        sp = spool.find(sc, "Carousel")
        gs = next(o for o in sc.objects if o.get(build.PROP_NAME) == "GUIDE SHEAVE")
        for p in (0.0, 3.0):
            pay(sc, "Power cable", p)
            g = to_spool(sc, sp, np.array(gs.matrix_world.translation))
            lv = to_spool(sc, sp, leave_world(sc, "Power cable"))
            assert math.hypot(g[0], g[1]) == pytest.approx(math.hypot(lv[0], lv[1]), abs=0.005), p
            _phi, _a, r, _k = S.at(spool.path_of(sc, sp), np.array([120.0 - p]))
            assert math.hypot(lv[0], lv[1]) == pytest.approx(float(r[0]), abs=LEAVE_TOL), p
    finally:
        _DIRTY[0] = True


def test_lookups_survive_undo_and_load(made):
    """What undo and load call leaves the module holding nothing of the old data (no Blender objects in its caches),
    and everything is found again afterwards."""
    sc = made
    pay(sc, "Wire", 3.0)

    def holds_bpy(x, depth=0):
        if depth > 6:
            return False
        if isinstance(x, bpy.types.bpy_struct):
            return True
        if isinstance(x, dict):
            return any(holds_bpy(v, depth + 1) or holds_bpy(k, depth + 1) for k, v in x.items())
        if isinstance(x, (list, tuple, set)):
            return any(holds_bpy(v, depth + 1) for v in x)
        return False
    assert not holds_bpy(spool._STATE)
    for h in (bpy.app.handlers.undo_post, bpy.app.handlers.load_post):
        assert any(getattr(fn, "__module__", "").endswith("blender.spool") for fn in h), h
    spool._on_load()
    paths._on_undo()
    pay(sc, "Wire", 3.5)
    sp = spool.find(sc, "Drum")
    loc = to_spool(sc, sp, leave_world(sc, "Wire"))
    _phi, a, r, _k = my_drum(sc, sp).at(float(sp.wound) - 3.5)
    assert math.hypot(loc[0], loc[1]) == pytest.approx(r[0], abs=LEAVE_TOL)


def test_a_table_and_a_ratio_in_one_chain(made):
    """'Follows by table' in a chain: a motor drives the cable joint by a ratio, the drum follows the cable by its
    table, a joint follows the drum by a ratio – all move together, without Python."""
    sc = made
    weight = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WEIGHT")
    clamp = next(o for o in sc.objects if o.get(build.PROP_NAME) == "CABLE CLAMP")
    from mathutils import Vector
    joints.create(sc, "ROTATE", [weight], weight.matrix_world.translation.copy(), Vector((0, 0, 1)),
                  name="Test after drum")
    joints.create(sc, "ROTATE", [clamp], clamp.matrix_world.translation.copy(), Vector((0, 0, 1)),
                  name="Test motor")
    cable_joint = paths.find(sc, "Wire").joint
    try:
        joints.set_follows(sc, joints.find(sc, "Test after drum"), "Drum turn", ratio=2.0)
        update()
        pay(sc, "Wire", 7.0)
        drum = spool_value(sc, spool.find(sc, "Drum")) * spool.find(sc, "Drum").zsign
        assert joints.find(sc, "Test after drum").motion.rotation_euler[2] == pytest.approx(2.0 * drum, abs=1e-5)
        # a motor above the cable joint: 1 turn of it pays out ... whatever its ratio says; the drum still agrees
        joints.set_follows(sc, joints.find(sc, cable_joint), "Test motor")
        update()
        joints.set_value(joints.find(sc, "Test motor"), 1.3)
        update()
        paths.refresh(sc)
        update()
        sp = spool.find(sc, "Drum")
        p = spool.payout(sc, sp)
        want = joints.interp(*joints.table_of(joints.find(sc, "Drum turn")), p)
        assert joints.find(sc, "Drum turn").motion.rotation_euler[2] == pytest.approx(want, abs=1e-5)
        loc = to_spool(sc, sp, leave_world(sc, "Wire"))
        _phi, _a, r, _k = my_drum(sc, sp).at(float(sp.wound) - p)
        assert math.hypot(loc[0], loc[1]) == pytest.approx(r[0], abs=LEAVE_TOL)
        assert joints.couplings_simple(sc)
    finally:
        _DIRTY[0] = True


def test_lebus_on_the_test_drum(made):
    """The test drum switched to Lebus: the level wind stands still in the parallel runs (about 290° of every turn)
    and moves on by about one pitch per turn; the leave point stays on its layer's circle."""
    sc = made
    sp = spool.find(sc, "Drum")
    try:
        sp.groove = "LEBUS"
        sp = spool.find(sc, "Drum")
        assert not sp.problem, sp.problem
        d = float(paths.find(sc, "Wire").diameter)
        pitch = float(sp.pitch) if sp.pitch > 0 else 1.06 * d
        lw = joints.find(sc, "Level wind")
        vals, ps = [], np.arange(0.0, 2.4, 0.01)
        for p in ps:
            pay(sc, "Wire", float(p))
            vals.append(joints.get_value(lw))
        step = np.abs(np.diff(vals))
        still = (step < 1e-6).mean()
        assert still == pytest.approx(1.0 - 35.0 / 180.0, abs=0.08), still
        loc = to_spool(sc, sp, leave_world(sc, "Wire"))
        layer_r = float(sp.r1) + int(sp.layer - 1) * d * COS30
        assert math.hypot(loc[0], loc[1]) == pytest.approx(layer_r, abs=LEAVE_TOL)
        turns = 2.4 / (2 * math.pi * layer_r)
        assert abs(vals[-1] - vals[0]) == pytest.approx(turns * pitch, abs=0.5 * pitch)
    finally:
        _DIRTY[0] = True


def test_zero_wound(made):
    """Nothing on the drum at the start: no error at 0, paying out says it runs empty, nothing drawn on it."""
    sc = made
    sp = spool.find(sc, "Drum")
    try:
        sp.wound = 0.0
        sp = spool.find(sc, "Drum")
        pay(sc, "Wire", 0.0)
        text, icon = spool.status(sc, sp)
        assert "Traceback" not in text
        pay(sc, "Wire", 1.0)
        text, icon = spool.status(sc, spool.find(sc, "Drum"))
        assert icon == "ERROR" and "empty" in text.lower(), text
        _c, s = rope_curve(sc, spool.find(sc, "Drum"))
        assert len(s) == 0 or s.max() - s.min() < 1e-3
    finally:
        _DIRTY[0] = True


def test_refusals_two_spools_and_wrong_joints(made):
    sc = made
    n = len(sc.fresing.spools)
    barrel = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WINCH DRUM")
    with pytest.raises(spool.SpoolError) as e:
        spool.add(sc, "DRUM", barrel, "Wire", name="Second")
    assert "already" in str(e.value) and "Drum" in str(e.value)
    assert len(sc.fresing.spools) == n
    with pytest.raises(spool.SpoolError) as e:
        spool.add_follower(sc, spool.find(sc, "Drum"), "Level wind", mode="ARM")
    with pytest.raises(spool.SpoolError) as e:
        spool.add_follower(sc, spool.find(sc, "Drum"), "Drum turn")
    with pytest.raises(spool.SpoolError) as e:
        spool.add_follower(sc, spool.find(sc, "Carousel"), "Drum turn", mode="ARM")
    assert "parallel" in str(e.value)
    assert [f.joint for f in spool.find(sc, "Drum").followers] == ["Level wind"]


def test_a_slide_joint_switched_to_arm_in_the_panel(made):
    """The panel's "Follows" list lets the owner switch the level wind (a slide) to "Arm over the coil": that must be
    refused in plain words, not give the slide a table of angles."""
    sc = made
    sp = spool.find(sc, "Drum")
    lw = joints.find(sc, "Level wind")
    before = np.array(joints.table_of(lw)).copy()
    try:
        sp.followers[0].mode = "ARM"
        sp = spool.find(sc, "Drum")
        after = joints.table_of(joints.find(sc, "Level wind"))
        # FAULT: tables() only checks that an ARM joint's axis is parallel to the drum's, not that it is a rotate
        # joint; the level wind slides along the drum axis, so it passes, gets arm angles (radians) as metres, and
        # no problem is shown (blender/spool.py tables(), the ARM loop; add_follower checks the kind, the panel's
        # mode list does not).
        refused = bool(sp.problem) or (after is not None and np.allclose(np.array(after), before))
        assert refused, (sp.problem, None if after is None else np.ptp(np.array(after)[1]))
    finally:
        sp = spool.find(sc, "Drum")
        sp.followers[0].mode = "ACROSS"
        _DIRTY[0] = True


# ---------------------------------------------------------------------------------------------------------------------
# changes for good (a model of their own)
# ---------------------------------------------------------------------------------------------------------------------

def _cad_line(which):
    import make_test_spool as M
    return np.asarray(M.centreline(which, 2.0), dtype=float) / 1000.0


def _off_line(points, line):
    """The largest distance from ``points`` to the polyline ``line``."""
    worst = 0.0
    a, b = line[:-1], line[1:]
    ab = b - a
    ll = np.maximum((ab * ab).sum(1), 1e-30)
    for x in points:
        t = np.clip(((x - a) * ab).sum(1) / ll, 0, 1)
        worst = max(worst, float(np.linalg.norm(a + t[:, None] * ab - x, axis=1).min()))
    return worst


def test_removing_the_spool_puts_the_cable_back(fresh):
    sc = fresh
    i = next(k for k, s in enumerate(sc.fresing.spools) if s.name == "Drum")
    coil = spool.find(sc, "Drum").coil
    spool.remove(sc, i)
    update()
    assert spool.find(sc, "Drum") is None
    it = paths.find(sc, "Wire")
    assert it.a_kind != "SPOOL" and not it.problem
    assert not [o for o in bpy.data.objects if o.get(spool.TAG) == "Drum"]
    assert not [m for m in bpy.data.meshes if m.name.startswith("FR spool") and "Drum" in m.name]
    assert spool.HIDE not in coil.modifiers
    dg = bpy.context.evaluated_depsgraph_get()
    assert len(coil.evaluated_get(dg).data.vertices) > 100
    for name in ("Drum turn", "Level wind"):
        j = joints.find(sc, name)
        assert j is not None and not j.couple_table and not j.follows, name
        joints.set_value(j, 0.1)                                        # it moves by itself again
        update()
        assert joints.get_value(j) == pytest.approx(0.1, abs=1e-6)
        joints.set_value(j, 0.0)
    update()
    pay(sc, "Wire", 0.0)
    shape = np.asarray(paths.shape_now(sc, paths.find(sc, "Wire")), dtype=float)
    assert _off_line(shape, _cad_line("wire")) < 0.001                # the cable as drawn in CAD again
    # the carousel did not notice
    assert not spool.find(sc, "Carousel").problem and paths.find(sc, "Power cable").a_kind == "SPOOL"


def test_model_update_of_the_same_file_keeps_the_spools(fresh):
    sc = fresh
    sp = spool.find(sc, "Drum")
    sp.wound = 40.0
    pay(sc, "Wire", 5.0)
    pay(sc, "Power cable", 5.0)
    before = {n: (spool_value(sc, spool.find(sc, n)), leave_world(sc, c).copy())
              for n, c in (("Drum", "Wire"), ("Carousel", "Power cable"))}
    old_parts = {n: spool.find(sc, n).part.name for n in ("Drum", "Carousel")}
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal", update_root=root.name) == {"FINISHED"}
    update()
    sc = bpy.context.scene
    notes = [n.text for n in sc.fresing.report_notes]
    assert not [n for n in notes if "Drum or carousel" in n], notes
    # FAULT: after updating to the same file both spools are broken: the cables are read again with the CAD coil
    # ('WIRE ON DRUM', 'CABLE COIL') as their first contact and the sheave three times; the drum's q lands on the coil
    # (fleet angle 90°), the power cable "cannot go round 'CABLE COIL'" (spool.after_model_update /
    # paths.after_model_update -> read_cad -> spool.after_read: the cable is read while its start is SPOOL and the
    # coil's contacts were taken off – _setup(read=True) re-reads, but the coil is visible to the reading).
    pay(sc, "Wire", 5.0)
    pay(sc, "Power cable", 5.0)
    for n, c in (("Drum", "Wire"), ("Carousel", "Power cable")):
        sp = spool.find(sc, n)
        assert sp is not None and sp.enabled and not sp.problem, (n, sp and sp.problem)
        assert sp.part is not None and sp.part.name in sc.objects
        assert sp.owner is not None and sp.owner.name in sc.objects
        assert paths.find(sc, c).a_kind == "SPOOL"
        assert joints.find(sc, sp.joint).couple_table == f"spool:{n}"
        assert spool_value(sc, sp) == pytest.approx(before[n][0], abs=1e-5), n
        assert np.linalg.norm(leave_world(sc, c) - before[n][1]) < LEAVE_TOL, n
        _c, s = rope_curve(sc, sp)
        assert float(sp.wound) + s.max() == pytest.approx(float(sp.wound) - 5.0, abs=LENGTH_TOL)
    assert float(spool.find(sc, "Drum").wound) == pytest.approx(40.0, abs=1e-6)   # typed: kept
    assert [f.joint for f in spool.find(sc, "Drum").followers] == ["Level wind"]
    assert [f.joint for f in spool.find(sc, "Carousel").followers] == ["Arm slew"]
    print("\nparts before / after:", old_parts, {n: spool.find(sc, n).part.name for n in ("Drum", "Carousel")})


def test_save_and_open_again(fresh, tmp_path):
    sc = fresh
    pay(sc, "Wire", 6.0)
    pay(sc, "Power cable", 2.0)
    before = {n: (spool_value(sc, spool.find(sc, n)), leave_world(sc, c).copy())
              for n, c in (("Drum", "Wire"), ("Carousel", "Power cable"))}
    path = str(tmp_path / "spool.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    update()
    for n, c in (("Drum", "Wire"), ("Carousel", "Power cable")):
        sp = spool.find(sc, n)
        assert sp is not None and sp.enabled and not sp.problem
        assert spool_value(sc, sp) == pytest.approx(before[n][0], abs=1e-6)
    paths.refresh(sc, force=True)
    update()
    for n, c in (("Drum", "Wire"), ("Carousel", "Power cable")):
        assert np.linalg.norm(leave_world(sc, c) - before[n][1]) < 1e-4, n
    # live again
    pay(sc, "Wire", 9.0)
    sp = spool.find(sc, "Drum")
    loc = to_spool(sc, sp, leave_world(sc, "Wire"))
    _phi, a, r, _k = my_drum(sc, sp).at(float(sp.wound) - 9.0)
    assert math.hypot(loc[0], loc[1]) == pytest.approx(r[0], abs=LEAVE_TOL)
    _c, s = rope_curve(sc, sp)
    assert s.max() == pytest.approx(-9.0, abs=LENGTH_TOL)
    # Build in the opened file
    pay(sc, "Wire", 0.0)
    pay(sc, "Power cable", 0.0)
    a = sc.fresing.animations[spool.TEST_ANIMATION]
    animation.bake(sc, a)
    sc.frame_set(150)
    update()
    sp = spool.find(sc, "Drum")
    p = spool.payout(sc, sp)
    assert 0.0 < p < 6.0
    loc = to_spool(sc, sp, leave_world(sc, "Wire"))
    _phi, a_, r, _k = my_drum(sc, sp).at(float(sp.wound) - p)
    assert math.hypot(loc[0], loc[1]) == pytest.approx(r[0], abs=LEAVE_TOL)
    animation.clear_keys(sc)


def test_a_cable_drawn_from_the_weight_to_the_drum(fresh, monkeypatch):
    """A cable whose CAD reading ends on the drum (read from its other end): the spool still takes its start, and the
    cable comes off the drum as before."""
    sc = fresh
    i = next(k for k, s in enumerate(sc.fresing.spools) if s.name == "Drum")
    spool.remove(sc, i)
    real = paths._direction

    def backwards(scene, item, geo):
        real(scene, item, geo)
        paths._flip_rows(geo)
    monkeypatch.setattr(paths, "_direction", backwards)
    it = paths.find(sc, "Wire")
    paths.read_cad(sc, it, it.part)
    it = paths.find(sc, "Wire")
    weight = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WEIGHT")
    first = np.asarray(paths.shape_now(sc, it)[0], dtype=float)
    assert first[2] < 0.3 and abs(first[0] - 0.9) < 0.05, first        # it starts on the weight now
    barrel = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WINCH DRUM")
    coil = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WIRE ON DRUM")
    sp = spool.add(sc, "DRUM", barrel, "Wire", name="Drum", coil=coil)
    spool.add_follower(sc, spool.find(sc, "Drum"), "Level wind")
    sp = spool.find(sc, "Drum")
    assert not sp.problem, sp.problem
    assert paths.find(sc, "Wire").a_kind == "SPOOL"
    assert float(sp.wound) == pytest.approx(49.5, abs=0.3)
    pay(sc, "Wire", 2.0)
    sp = spool.find(sc, "Drum")
    loc = to_spool(sc, sp, leave_world(sc, "Wire"))
    _phi, a, r, _k = my_drum(sc, sp).at(float(sp.wound) - 2.0)
    assert math.hypot(loc[0], loc[1]) == pytest.approx(r[0], abs=LEAVE_TOL)
    assert weight is not None


def test_a_drum_without_flanges(fresh):
    """A barrel without flanges: refused in plain words, nothing half made (no joint, no list entry, the cable as
    it was); or taken, with a sensible width and no problem."""
    import bmesh
    sc = fresh
    i = next(k for k, s in enumerate(sc.fresing.spools) if s.name == "Drum")
    spool.remove(sc, i)
    barrel = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WINCH DRUM")
    # cut the flanges off the barrel's mesh: keep what lies within 0.2 m of the drum axis (+Y through z 0.45)
    me = barrel.data.copy()
    barrel.data = me
    bm = bmesh.new()
    bm.from_mesh(me)
    m = barrel.matrix_world
    gone = [v for v in bm.verts if math.hypot((m @ v.co).x, (m @ v.co).z - 0.45) > 0.2]
    bmesh.ops.delete(bm, geom=gone, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    update()
    n_spools, n_joints = len(sc.fresing.spools), len(sc.fresing.joints)
    contacts = [c.name for c in paths.find(sc, "Wire").contacts]
    coil = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WIRE ON DRUM")
    try:
        sp = spool.add(sc, "DRUM", barrel, "Wire", name="Drum", coil=coil)
    except spool.SpoolError as e:
        text = str(e)
        assert "flange" in text.lower() and "Traceback" not in text, text
        assert len(sc.fresing.spools) == n_spools and len(sc.fresing.joints) == n_joints
        assert [c.name for c in paths.find(sc, "Wire").contacts] == contacts
        assert paths.find(sc, "Wire").a_kind != "SPOOL"
        return
    assert not sp.problem and sp.a_hi - sp.a_lo > 0.05


# =====================================================================================================================
# Part 3: the real Blender, Python scripts in the file disabled
# =====================================================================================================================

BLENDER = os.path.expanduser("~/blender-5.2.3/blender-5.2.3-linux-x64/blender")

_CHECK = r"""
import bpy, sys, json
ob = bpy.data.objects
out = {"autoexec": bpy.app.driver_namespace is not None and bool(bpy.context.preferences.filepaths.use_scripts_auto_execute)}
cable = ob[sys.argv[sys.argv.index("--") + 1]]
drum = ob[sys.argv[sys.argv.index("--") + 2]]
lw = ob[sys.argv[sys.argv.index("--") + 3]]
res = []
for v in (0.0, 4.0, 13.0):
    cable["fr_value"] = v
    cable.update_tag()
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    res.append((v, drum.rotation_euler[2], lw.location[2]))
out["res"] = res
print("RESULT" + json.dumps(out))
"""


@pytest.mark.skipif(not os.path.exists(BLENDER), reason="no real Blender here")
def test_real_blender_with_scripts_off_turns_the_drum(fresh, tmp_path):
    """The saved project opened in the real Blender with "Auto Run Python Scripts" off (-Y): the drum turns and the
    level wind moves by their tables when the cable's joint changes."""
    sc = fresh
    it = paths.find(sc, "Wire")
    cj = joints.find(sc, it.joint)
    dj = joints.find(sc, spool.find(sc, "Drum").joint)
    lw = joints.find(sc, "Level wind")
    want = []
    for v in (0.0, 4.0, 13.0):
        joints.set_value(cj, v, use_limits=False)
        update()
        want.append((dj.motion.rotation_euler[2], lw.motion.location[2]))
    joints.set_value(cj, 0.0)
    update()
    path = str(tmp_path / "scripts_off.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    script = tmp_path / "check.py"
    script.write_text(_CHECK.replace('"fr_value"', repr(joints.VALUE)))
    r = subprocess.run([BLENDER, "-b", "-Y", "--factory-startup", path, "--python", str(script), "--",
                        cj.motion.name, dj.motion.name, lw.motion.name],
                       capture_output=True, text=True, timeout=180)
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT")), None)
    assert line is not None, r.stdout[-2000:] + r.stderr[-2000:]
    import json
    got = json.loads(line[len("RESULT"):])["res"]
    for (v, rot, loc), (w_rot, w_loc) in zip(got, want):
        assert rot == pytest.approx(w_rot, abs=1e-5), v
        assert loc == pytest.approx(w_loc, abs=1e-6), v
    assert abs(got[2][1] - got[0][1]) > 1.0                            # it really turned
