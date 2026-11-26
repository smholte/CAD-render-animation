"""Task 0348 (Lifting L6a): the lift path's checks in plain Python – hand-worked cases.

* C5 along a slew (study 0180's C5 numbers): the corner reaction R(+a, +b) = P/4 + (15 + M cos s)/(4a) + M sin s/(4b)
  with M = 13.6 × 12 − 12 × 4.5 = 109.2 t·m, peaks at tan s = a / b (46.685°) with 28.341 t – between the keys 0° and
  90° (24.771 t, 25.244 t). The search finds it; at an allowable pressure of 27.0 t on a 1.5 × 1.5 m mat the ends are
  amber and the middle red.
* Jacks up (AT-100 'Working' with the jacks at 0): "Set up" red. Counterweight above the chart (AT-100 with 40 t, its
  charts go to 30 t): C1 says so and Backward stability is worked out; with the chart's 30 t it is grey.
"""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_path as P, lifting_reach as LR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "fresing_render", "data", "lifting")

A, B = 3.5, 3.3
CARRIER = [(30000.0, 0.5, 0.0)]
UPPER = [(8000.0, 0.0, 0.0), (12000.0, -4.5, 0.0)]
MAT = (1.5, 1.5)
S_PEAK = math.degrees(math.atan2(A, B))
R_PEAK = 63.6 / 4 + 15 / (4 * A) + 109.2 / 4 * math.sqrt(1 / A ** 2 + 1 / B ** 2)


def _r_pp(s_deg: float) -> float:
    s = math.radians(s_deg)
    return 63.6 / 4 + (15 + 109.2 * math.cos(s)) / (4 * A) + 109.2 * math.sin(s) / (4 * B)


def _slew_at(allowable_t: float | None):
    allow = None if allowable_t is None else allowable_t * 1000 * lifting.G / (MAT[0] * MAT[1])

    def at(t):
        items = lifting.crane_items(CARRIER, UPPER, 13600.0, 12.0, t)
        return [P.outrigger_row(items, A, B, (0.0, 0.0), MAT, allow, lifting.DEFAULT_LIMITS, "its mat")]
    return at


def test_hand_case_numbers():
    assert _r_pp(30.0) == pytest.approx(27.863, abs=5e-4)          # the study's worked case at 30°
    assert _r_pp(0.0) == pytest.approx(24.771, abs=5e-4)
    assert _r_pp(90.0) == pytest.approx(25.244, abs=5e-4)
    assert S_PEAK == pytest.approx(46.685, abs=1e-3) and R_PEAK == pytest.approx(28.341, abs=5e-4)


def test_worst_moment_between_the_keys():
    f = P.search(_slew_at(None), 0.0, 90.0, keys=(0.0, 90.0))
    w = f.worst["C5"]
    assert w.t == pytest.approx(S_PEAK, abs=0.05)
    assert float(w.value.split()[0]) == pytest.approx(R_PEAK, abs=0.05)
    assert f.evaluations < 60                                       # not every moment


def test_red_mid_slew_green_or_amber_at_the_keys():
    at = _slew_at(27.0)
    k0, k1 = at(0.0)[0], at(90.0)[0]
    assert k0.status == k1.status == lifting.AMBER                  # 91.7 % and 93.5 % of 27.0 t
    f = P.search(at, 0.0, 90.0, keys=(0.0, 90.0))
    w = f.worst["C5"]
    assert w.status == lifting.RED and w.use == pytest.approx(R_PEAK / 27.0, rel=1e-4)
    assert w.t == pytest.approx(S_PEAK, abs=0.05)
    assert "red" in w.words and "Outrigger" in w.words
    # the moments the data box reads: red only from the moment it turns red
    assert P.worst_so_far(f.moments, 1.0) == lifting.AMBER
    assert P.worst_so_far(f.moments, 89.9) == lifting.RED


def test_search_agrees_with_every_frame():
    at = _slew_at(27.0)
    ref = P.every(at, np.linspace(0.0, 90.0, 901))
    f = P.search(at, 0.0, 90.0, keys=(0.0, 45.0, 90.0))
    assert f.worst["C5"].use >= ref.worst["C5"].use - 1e-6
    assert f.evaluations < ref.evaluations / 10


def test_search_skips_constant_checks():
    calls = []

    def at(t):
        calls.append(t)
        return [P.Row("C2", "Sling legs", lifting.OK, 0.5)]
    f = P.search(at, 0.0, 100.0, keys=(0.0, 50.0, 100.0))
    assert f.worst["C2"].use == 0.5 and len(set(calls)) == 9       # the grid only


def _crane(name):
    it = LL.read_item(os.path.join(LIB, name))
    charts = LL.charts_of(it)
    poses = {p["name"]: dict(p["values"]) for p in it.data["rig"]["poses"]}
    return it, charts, poses


def _rows(checks, vals):
    return {r.id: r for r in checks.at(vals)}


def test_jacks_up_is_red():
    it, charts, poses = _crane("AT-100")
    plan = P.Plan(load_kg=5000, hook_block_kg=1000, counterweight_kg=30000)
    c = P.Checks(it.data, charts, plan)
    rows = _rows(c, poses["Working"])
    assert rows["SETUP"].status == lifting.OK and "jacks down" in rows["SETUP"].words
    up = dict(poses["Working"], Jacks=0.0)
    rows = _rows(c, up)
    assert rows["SETUP"].status == lifting.RED and "jacks are up" in rows["SETUP"].words


def test_beams_in_against_a_typed_spread_is_red():
    it, charts, poses = _crane("AT-100")
    plan = P.Plan(load_kg=5000, hook_block_kg=1000, counterweight_kg=30000, spread=7.6)
    vals = dict(poses["Working"], Outriggers=0.0)                   # beams in: 3.1 m, chart picked for 7.6 m
    rows = _rows(P.Checks(it.data, charts, plan), vals)
    assert rows["SETUP"].status == lifting.RED and "the chart is for 7.6 m" in rows["SETUP"].words


def test_counterweight_above_the_chart():
    it, charts, poses = _crane("AT-100")
    vals = dict(poses["Working"])
    same = _rows(P.Checks(it.data, charts, P.Plan(load_kg=5000, hook_block_kg=1000, counterweight_kg=30000)), vals)
    assert same["BACK"].status == lifting.NOT_CHECKED and "chart covers" in same["BACK"].words
    more = _rows(P.Checks(it.data, charts, P.Plan(load_kg=5000, hook_block_kg=1000, counterweight_kg=40000)), vals)
    assert "the chart is for 30.00 t" in more["C1"].words
    b = more["BACK"]
    assert b.status != lifting.NOT_CHECKED and b.use is not None
    assert "more than the chart's 30.00 t" in b.words
    # hand check of the margin: the unloaded crane's resultant from the same items
    rig = LR.Rig(it.data)
    items = P.Supports(rig, it.data).items(vals, 40000, 0.0)
    _p, x, y = lifting.resultant(items)
    o = it.data["outriggers"]
    sp = LR.outrigger_spread(it.data, vals)
    m = min(1 - abs(x - o["centre"][0]) / o["a"], 1 - abs(y - o["centre"][1]) / (sp / 2))
    assert b.use == pytest.approx((1 - m) / (1 - P.BACK_RESERVE), rel=1e-9)


def test_rigging_rows_from_the_hang_and_grey_when_not_hung():
    it, charts, poses = _crane("AT-40")
    vals = poses["Working"]
    rows = _rows(P.Checks(it.data, charts, P.Plan(load_kg=2000)), vals)
    assert rows["C2"].status == lifting.NOT_CHECKED and "not hung" in rows["C2"].words
    chk = [{"check": "C3", "title": "Sling legs", "status": "amber", "use": 0.93, "parts": []},
           {"check": "C4", "title": "WLL", "status": "ok", "use": 0.4,
            "parts": [{"title": "Shackle A", "status": "ok", "use": 0.4}, {"title": "Shackle B", "status": "ok",
                                                                            "use": 0.6}]}]
    rows = _rows(P.Checks(it.data, charts, P.Plan(load_kg=2000, hung=True, rig_checks=chk)), vals)
    assert rows["C3"].status == lifting.AMBER and rows["C3"].use == 0.93
    assert rows["C4"].use == 0.6 and "Shackle B" in rows["C4"].words


def test_crawler_tracks_and_no_outriggers_row():
    it, charts, poses = _crane("CC-300")
    plan = P.Plan(load_kg=10000, hook_block_kg=3200, counterweight_kg=100000, allowable_pa=300e3)
    rows = _rows(P.Checks(it.data, charts, plan), poses["Working"])
    assert "C6" in rows and "C5" not in rows and "SETUP" not in rows
    assert rows["C6"].use is not None and "kPa" in rows["C6"].words
    # travel does not change the ground pressure (everything rides on the tracks)
    moved = _rows(P.Checks(it.data, charts, plan), dict(poses["Working"], Travel=5000.0))
    assert moved["C6"].use == pytest.approx(rows["C6"].use, rel=1e-9)


def test_c1_words():
    it, charts, poses = _crane("AT-100")
    rows = _rows(P.Checks(it.data, charts, P.Plan(load_kg=5000, hook_block_kg=1000, counterweight_kg=30000)),
                 poses["Working"])
    r = rows["C1"]
    assert r.words.startswith(f"Crane at {r.use * 100:.0f} % of its chart at ")
    assert f"your limit is {lifting.DEFAULT_LIMITS.crane * 100:.0f} %" in r.words or r.status == lifting.NOT_CHECKED


def test_words_never_forbidden():
    it, charts, poses = _crane("AT-100")
    for cw in (30000, 40000):
        for vals in poses.values():
            for r in P.Checks(it.data, charts, P.Plan(load_kg=8000, hook_block_kg=1000, counterweight_kg=cw,
                                                      allowable_pa=250e3)).at(vals):
                low = r.words.lower()
                assert not any(w.lower() in low for w in lifting.FORBIDDEN_WORDS), r.words


@pytest.mark.parametrize("name,target", [("AT-100", (12000.0, 8000.0, 0.0)), ("CC-300", (-25000.0, 10000.0, 0.0)),
                                         ("KB-50", (5000.0, -6000.0, 0.0))])
def test_propose_reaches_the_set_down_point(name, target):
    it, charts, poses = _crane(name)
    rig = LR.Rig(it.data)
    vals = poses["Working"]
    pr = P.propose(rig, it.data, vals, np.array(target), 2000.0, charts, {}, load_kg=2000.0)
    assert pr.ok, pr.reason
    assert np.linalg.norm(rig.hook(pr.end) - np.array(target)) < 5.0
    kinds = [s.kind for s in pr.steps]
    assert kinds[-1] == "lower" and kinds.index("slew") < kinds.index("lower")
    assert all(P.MIN_S <= s.seconds <= P.MAX_S for s in pr.steps if s.kind != "luff")
    luff = [s for s in pr.steps if s.kind == "luff"]
    assert len(luff) in (0, 1, P.SUB) and P.MIN_S - 0.05 <= sum(s.seconds for s in luff) <= P.MAX_S + 0.05
    # the hook stays at least the clearance above the pick and the set-down while the crane slews and luffs
    now = dict(vals)
    up = rig.up
    floor = max(float(rig.hook(vals) @ up), target[2]) + 2000.0 - 1.0
    for s in pr.steps[:-1]:
        now.update(s.values)
        if s.kind != "hoist":
            assert float(rig.hook(now) @ up) >= floor - 50.0


def test_propose_a_crawler_travels_when_out_of_reach():
    it, charts, poses = _crane("CC-300")
    rig = LR.Rig(it.data)
    pr = P.propose(rig, it.data, poses["Working"], np.array((60000.0, 0.0, 2000.0)), 2000.0, charts, {})
    assert pr.ok and [s.kind for s in pr.steps].count("travel") == 1
    assert any("travels" in n for n in pr.notes)


def test_propose_out_of_reach_says_why():
    it, charts, poses = _crane("AT-40")
    rig = LR.Rig(it.data)
    pr = P.propose(rig, it.data, poses["Working"], np.array((200000.0, 0.0, 0.0)), 2000.0, charts, {})
    assert not pr.ok and pr.reason
