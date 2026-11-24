"""Task 0310, no Blender: the numbers of the lead motions' sliders on the web 3D page (core/web3d_lead.py) – which of two
joints carries the other, the order the page applies them in, the joints' values from several sliders (0309's rule:
the lead motion moved last wins a joint) and the page's sum of the joints' moves (exact for a trolley on a boom)."""

import math

import numpy as np
import pytest

from fresing_render.core import lead_motions as lm
from fresing_render.core import web3d_lead as core


def rot_z(a, about=(0.0, 0.0, 0.0)):
    m = np.eye(4)
    c, s = math.cos(a), math.sin(a)
    m[:2, :2] = [[c, -s], [s, c]]
    p = np.array(about)
    m[:3, 3] = p - m[:3, :3] @ p
    return m


def move(x, y=0.0, z=0.0):
    m = np.eye(4)
    m[:3, 3] = [x, y, z]
    return m


# a boom turning about z at (0, 0, 2) and a trolley sliding along the boom's x: two parts, the boom and the trolley
M0 = np.stack([move(1.0, 0.0, 2.0), move(3.0, 0.0, 2.2)])


def boom(a):            # boom alone at angle a: both parts turn
    return np.stack([rot_z(a, (0, 0, 2)) @ m for m in M0])


def trolley(x):         # trolley alone: only the trolley slides along x (the boom at rest)
    return np.stack([M0[0], move(x) @ M0[1]])


def both(a, x):         # Blender: the trolley rides on the boom
    return np.stack([rot_z(a, (0, 0, 2)) @ M0[0], rot_z(a, (0, 0, 2)) @ move(x) @ M0[1]])


def test_the_carrier_is_found_and_applied_last():
    a, x = math.radians(40), 1.5
    assert core.outer(M0, boom(a), trolley(x), both(a, x)) == 1               # A (the boom) carries B
    assert core.outer(M0, trolley(x), boom(a), both(a, x)) == -1
    order = core.apply_order(2, {(0, 1): 1}, sizes=[2, 1])
    assert order == [1, 0]                                                     # the trolley first, the boom last
    assert core.apply_order(2, {(0, 1): -1}, sizes=[2, 1]) == [0, 1]
    assert core.apply_order(3, {}, sizes=[5, 1, 3]) == [2, 0, 1]               # no rule: fewer parts first
    assert sorted(core.apply_order(3, {(0, 1): 1, (1, 2): 1, (2, 0): 1})) == [0, 1, 2]   # a loop still orders


def test_two_independent_joints_need_no_rule():
    other = np.stack([M0[0], rot_z(0.3, (3, 0, 0)) @ M0[1]])                  # turns the trolley in place
    still = np.stack([move(0, 0, 0.5) @ M0[0], M0[1]])                         # lifts only the boom part
    assert core.outer(M0, still, other, np.stack([still[0], other[1]])) == 0


def test_the_page_sum_is_exact_for_a_carried_joint():
    a, x = math.radians(25), 0.8
    got = core.mixed(M0, {0: boom(a), 1: np.stack([np.full((4, 4), np.nan), trolley(x)[1]])}, {0: 1, 1: 0})
    assert np.allclose(got, both(a, x), atol=1e-12)
    wrong = core.mixed(M0, {0: boom(a), 1: np.stack([np.full((4, 4), np.nan), trolley(x)[1]])}, {0: 0, 1: 1})
    assert not np.allclose(wrong, both(a, x), atol=1e-3)                       # the other order is not


def rows(*rs):
    return [{"j": j, "v0": v0, "v1": v1, "start": s, "end": e, "easing": ez} for j, v0, v1, s, e, ez in rs]


def test_joint_values_the_last_moved_wins_and_windows_ease_as_the_app():
    up_out = {"rows": rows((0, 0.0, 0.5, 0, 60, "SMOOTH"), (1, 0.0, 1.5, 40, 100, "LINEAR"))}
    up = {"rows": rows((0, 0.0, 0.6, 0, 100, "SMOOTH"))}
    out = {"rows": rows((1, 0.0, 1.0, 0, 100, "LINEAR"))}
    ms = [up_out, up, out]
    v = core.joint_values(ms, [100.0, 50.0, 0.0], [1, 2, 0])                  # up-and-out, then up at 50 %
    assert v[0] == pytest.approx(0.3) and v[1] == pytest.approx(1.5)          # the trolley stays where up-and-out put it
    v = core.joint_values(ms, [100.0, 50.0, 0.0], [2, 1, 0])                  # up first, then up-and-out: it wins both
    assert v[0] == pytest.approx(0.5) and v[1] == pytest.approx(1.5)
    assert core.joint_values(ms, [30.0, 0.0, 0.0], [0, 0, 0]) == {}           # nothing moved: nothing set
    want = lm.values([lm.Row(0, 0.0, 0.5, 0, 60), lm.Row(1, 0.0, 1.5, 40, 100, "LINEAR")], 50.0)
    assert core.joint_values(ms, [50.0, 0, 0], [1, 0, 0]) == pytest.approx(want)


def test_two_rows_on_one_joint_out_and_back():
    there_and_back = {"rows": rows((0, 0.0, 1.0, 0, 50, "LINEAR"), (0, 1.0, 0.0, 50, 100, "LINEAR"))}
    for p, want in ((25, 0.5), (50, 1.0), (75, 0.5), (100, 0.0)):
        assert core.joint_values([there_and_back], [p], [1])[0] == pytest.approx(want)


def test_ranges_values_and_entries():
    a = lm.LeadMotion("Boom up", [lm.Row("Boom", 0.0, 0.6)], 3.0, "Lifts the boom")
    b = lm.LeadMotion("Down", [lm.Row("Boom", 0.2, -0.1), lm.Row("Trolley", 0.0, 1.5, 40, 100, "LINEAR")])
    r = core.joint_ranges([a, b])
    assert r == {"Boom": (-0.1, 0.6), "Trolley": (0.0, 1.5)}
    vs = core.values(*r["Boom"])
    assert vs[0] == -0.1 and vs[-1] == 0.6 and len(vs) == core.STEPS + 1
    assert core.clip_time(0.25, -0.1, 0.6) == pytest.approx(0.5)
    e = core.motion_entry(b, {"Boom": 0, "Trolley": 1}, 12.3456, ["0 %", "100 %"])
    assert e["rows"][1] == {"j": 1, "v0": 0.0, "v1": 1.5, "start": 40.0, "end": 100.0, "easing": "LINEAR"}
    assert e["at"] == 12.346 and e["about"] == "" and e["seconds"] == 4.0
    assert core.motion_entry(a, {"Boom": 0}, None, ["0°", "34°"])["at"] is None
    assert core.joint_entry(3, 0.0, 1.5, 1, "SLIDE", 2) == {"clip": 3, "lo": 0.0, "hi": 1.5, "apply": 1,
                                                          "kind": "SLIDE", "parts": 2}
