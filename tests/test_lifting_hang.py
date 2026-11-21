"""Task 0232: the hang solver (core/lifting_hang.py) on study 0180's hand cases and on odd CoGs."""

import math

import numpy as np
import pytest

from fresing_render.core import lifting as L
from fresing_render.core import lifting_hang as H


def t(force_n):
    return force_n / L.G / 1000.0


def test_c2_hand_case_comes_out_of_the_solver():
    """10 t, A and B 4.0 m apart, CoG 1.5 m from A (below the line), hook 3.0 m above: T_A 6.988 t, T_B 4.881 t."""
    la, lb = math.hypot(1.5, 3.0), math.hypot(2.5, 3.0)
    h = H.single(10000.0, (1.5, 0.0, -0.5), [(0, 0, 0), (4, 0, 0)], [la, lb], (1.5, 0.0, 3.0))
    assert h.ok and h.stable and not h.notes
    assert h.tilts[0] < 0.01
    assert t(h.leg("A").force) == pytest.approx(6.988, rel=5e-4)
    assert t(h.leg("B").force) == pytest.approx(4.881, rel=5e-4)
    assert h.leg("A").angle == pytest.approx(26.57, abs=0.01) and h.leg("B").angle == pytest.approx(39.81, abs=0.01)
    r = H.checks(h, 10000.0, leg_wll=8000.0, shackle_wll=8500.0)
    c2 = r[0]
    assert c2.check == "C2" and c2.parts[0].use == pytest.approx(0.873, abs=5e-4)
    shackles = [x for x in r if x.title.startswith("Shackle")]
    assert max(x.use for x in shackles) == pytest.approx(0.822, abs=5e-4)


def test_equal_legs_tilt_and_match_the_two_leg_formula():
    h = H.single(10000.0, (1.5, 0.0, -0.5), [(0, 0, 0), (4, 0, 0)], [4.0, 4.0], (0.0, 0.0, 8.0))
    assert h.ok and 5.0 < h.tilts[0] < 10.0
    assert np.allclose(h.cogs[0][:2], h.hook[:2], atol=1e-6)            # CoG under the hook
    ref = L.two_leg(10000.0, h.leg("A").bottom, h.leg("B").bottom, h.hook)
    assert h.leg("A").force == pytest.approx(ref.details["force"][0], rel=1e-4)
    assert h.leg("B").force == pytest.approx(ref.details["force"][1], rel=1e-4)


def test_c3_symmetric_four_legs_no_tilt_and_the_rules():
    pts = [(2, 1.5, 0), (-2, 1.5, 0), (-2, -1.5, 0), (2, -1.5, 0)]
    h = H.single(20000.0, (0, 0, -0.3), pts, 4.3012, (0, 0, 9))
    assert h.ok and h.tilts[0] < 1e-3
    assert all(t(lg.force) == pytest.approx(6.145, rel=5e-4) for lg in h.legs)      # equal share
    assert h.hook[2] - h.legs[0].bottom[2] == pytest.approx(3.5, abs=1e-3)
    c3 = H.checks(h, 20000.0, leg_wll=12500.0, mode="rigid")[0]
    assert c3.check == "C3" and t(c3.value) == pytest.approx(12.289, rel=5e-4)
    assert c3.parts[0].use == pytest.approx(0.983, abs=1e-3)
    assert c3.parts[1].use == pytest.approx(0.762, abs=1e-3)
    dnv = H.checks(h, 20000.0, leg_wll=12500.0, mode="dnv")[0]
    assert t(dnv.value) == pytest.approx(7.681, rel=5e-4)


def test_off_centre_four_legs_tilt_and_the_near_legs_carry_most():
    pts = [(2, 1.5, 0), (-2, 1.5, 0), (-2, -1.5, 0), (2, -1.5, 0)]
    h = H.single(20000.0, (0.8, 0.3, -0.3), pts, 4.3012, (0, 0, 9))
    assert h.ok and h.tilts[0] > 5.0
    f = [lg.force for lg in h.legs]
    assert max(f) == f[0]                     # A (+x, +y) is nearest the CoG
    # equilibrium: the legs' pulls add up to the weight, straight up
    s = sum(lg.force * (lg.top - lg.bottom) / np.linalg.norm(lg.top - lg.bottom) for lg in h.legs)
    assert np.allclose(s, [0, 0, 20000.0 * L.G], rtol=0, atol=20000.0 * L.G * 1e-4)


def test_a_shorter_leg_leaves_another_slack():
    pts = [(2, 1.5, 0), (-2, 1.5, 0), (-2, -1.5, 0), (2, -1.5, 0)]
    h = H.single(20000.0, (0, 0, -0.3), pts, [4.3, 4.3, 4.25, 4.3], (0, 0, 9))
    assert any(not lg.taut for lg in h.legs) and any("slack" in n for n in h.notes)


def test_cog_above_the_lift_points_rolls_over():
    h = H.single(10000.0, (2, 0.0, 0.5), [(0, 0, 0), (4, 0, 0)], 3.0, (2, 0, 5))
    assert not h.ok and "roll over" in h.problems[0]
    h = H.single(10000.0, (2, 0.02, 0.5), [(0, 0, 0), (4, 0, 0)], 3.0, (2, 0, 5))
    assert not h.ok and "roll over" in h.problems[0]


def test_cog_on_the_line_turns_freely():
    h = H.single(10000.0, (2, 0.0, 0.0), [(0, 0, 0), (4, 0, 0)], 3.0, (2, 0, 5))
    assert h.ok and h.neutral and "turns freely" in h.notes[0]


def test_a_leg_that_cannot_reach():
    h = H.single(10000.0, (2, 0, -0.5), [(0, 0, 0), (40, 0, 0)], 3.0, (20, 0, 5))
    assert not h.ok and "too short" in h.problems[0]


def test_spreader_two_stages():
    h = H.with_spreader(10000.0, (0, 0, -0.5), [(-2, 0, 0), (2, 0, 0)], 3.7, 500.0, (0, 0, 4),
                        [(-1.5, 0, 4.3), (1.5, 0, 4.3)], [(-2, 0, 3.7), (2, 0, 3.7)], 2.5, (0, 0, 10))
    assert h.ok and len(h.poses) == 2
    assert t(h.leg("top 1").force) == pytest.approx(10.5 / 2 * 2.5 / 2.0, rel=5e-4)
    assert t(h.leg("A").force) == pytest.approx(5.0, rel=5e-4)
    r = H.checks(h, 10000.0, leg_wll=8000.0, spreader_wll=25000.0, spreader_mass=500.0)
    assert r[0].check == "C2" and r[1].title == "Spreader WLL" and r[1].use == pytest.approx(0.4, abs=1e-4)


def test_spreader_off_centre_is_in_equilibrium():
    h = H.with_spreader(10000.0, (0.6, 0, -0.5), [(-2, 0, 0), (2, 0, 0)], 3.7, 500.0, (0, 0, 4),
                        [(-1.5, 0, 4.3), (1.5, 0, 4.3)], [(-2, 0, 3.7), (2, 0, 3.7)], 2.5, (0, 0, 10))
    assert h.ok
    tops = [lg for lg in h.legs if lg.at_hook]
    up = sum(lg.force * (lg.top - lg.bottom)[2] / np.linalg.norm(lg.top - lg.bottom) for lg in tops)
    assert up == pytest.approx(10500.0 * L.G, rel=1e-4)
    assert h.leg("B").force > h.leg("A").force            # the CoG is nearer B


def test_poses_move_rest_points_onto_the_answer():
    pts = [(2, 1.5, 0), (-2, 1.5, 0), (-2, -1.5, 0), (2, -1.5, 0)]
    h = H.single(20000.0, (0.5, 0.2, -0.3), pts, 4.3012, (10, 5, 20))
    M = h.poses[0]
    for p, lg in zip(pts, h.legs):
        assert np.allclose((M @ np.r_[p, 1.0])[:3], lg.bottom, atol=1e-9)
    assert np.allclose((M @ np.r_[0.5, 0.2, -0.3, 1.0])[:3], h.cogs[0], atol=1e-9)
