"""Task 0182: core/lifting.py – the worked cases of study 0180 section 3, to the study's digits, and the rules."""

from __future__ import annotations

import json
import math
import re

import pytest

from fresing_render.core import lifting as L

t = L.kg


def ft(force_n):
    return L.force_t(force_n)


def chart_c1(**kw):
    return L.Chart(radius=[8.0, 10.0, 12.0, 14.0], capacity=[t(36.0), t(29.5), t(24.0), t(20.0)], **kw)


# --- C1 ---------------------------------------------------------------------------------------------------------------

def test_c1_next_longer_radius():
    r = L.crane_use(t(12.4), 11.3, chart_c1(), rigging=t(0.35), hook_block=t(0.85))
    assert r.value == pytest.approx(t(13.6))
    assert r.limit == pytest.approx(t(24.0))
    assert r.details["row_radius"] == 12.0
    assert round(r.use * 100, 1) == 56.7
    assert r.status == L.OK and r.words == "Within entered limits"
    assert r.check == "C1" and "next longer radius" in r.formula


def test_c1_interpolated_number_is_only_information():
    assert L.capacity_interpolated(chart_c1(), 11.3) == pytest.approx(t(25.925))
    assert round(t(13.6) / L.capacity_interpolated(chart_c1(), 11.3) * 100, 1) == 52.5
    # A chart that says it allows interpolation still gets the next longer radius (owner, 17 Nov 2026).
    r = L.crane_use(t(13.6), 11.3, chart_c1(interpolate=True))
    assert r.limit == pytest.approx(t(24.0))
    assert any("not offered" in w for w in L.validate_chart(chart_c1(interpolate=True))[1])


def test_c1_outside_the_chart_is_red():
    r = L.crane_use(t(13.6), 14.5, chart_c1())
    assert r.status == L.RED and r.limit is None
    assert "outside the chart" in r.message
    assert L.crane_use(t(1.0), 7.0, chart_c1()).status == L.RED


def test_c1_hook_block_in_chart_and_daf():
    r = L.crane_use(t(12.4), 12.0, chart_c1(includes_hook_block=True), rigging=t(0.35), hook_block=t(0.85))
    assert r.value == pytest.approx(t(12.75))
    r = L.crane_use(t(10.0), 12.0, chart_c1(), daf=1.2)
    assert r.value == pytest.approx(t(12.0))
    hs = chart_c1(config={"hs": 1.5})
    r = L.crane_use(t(10.0), 12.0, hs, daf=1.2)
    assert r.value == pytest.approx(t(10.0)) and r.details["daf_applied"] == 1.0
    assert any("double count" in n for n in r.notes)


def test_c1_amber_and_red_bounds():
    c = chart_c1()
    assert L.crane_use(t(18.0), 12.0, c).status == L.AMBER  # exactly 75 %
    assert L.crane_use(t(24.0), 12.0, c).status == L.AMBER  # exactly 100 %
    assert L.crane_use(t(24.01), 12.0, c).status == L.RED
    assert L.crane_use(t(17.9), 12.0, c).status == L.OK


def test_c1_wind_area_note():
    r = L.crane_use(t(10.0), 12.0, chart_c1(), wind_area=13.0)
    assert r.status == L.OK and any("1.2 m²/t" in n for n in r.notes)
    assert not L.crane_use(t(10.0), 12.0, chart_c1(), wind_area=11.0).notes


# --- C2 / C4 ---------------------------------------------------------------------------------------------------------

def test_c2_two_legs_off_centre():
    r = L.two_leg(t(10.0), (0, 0, 0), (4, 0, 0), (1.5, 0, 3.0), leg_wll=t(8.0), shackle_wll=t(8.5),
                  limits=L.Limits(rigging=0.75))
    d = r.details
    assert [round(ft(v), 3) for v in d["vertical"]] == [6.25, 3.75]
    assert [round(v, 4) for v in d["length"]] == [3.3541, 3.9051]
    assert [round(ft(v), 3) for v in d["force"]] == [6.988, 4.881]
    assert [round(v, 2) for v in d["angle"]] == [26.57, 39.81]
    assert round(ft(d["horizontal"][0]), 3) == 3.125 and round(ft(-d["horizontal"][1]), 3) == 3.125
    uses = {p.inputs["item"]: round(p.use * 100, 1) for p in r.parts}
    assert uses["sling leg A"] == 87.3 and uses["shackle A"] == 82.2
    assert r.status == L.AMBER  # amber at 75 % (the study's case)
    # With the owner's default 90 % for rigging the same legs are within the limits.
    assert L.two_leg(t(10.0), (0, 0, 0), (4, 0, 0), (1.5, 0, 3.0), leg_wll=t(8.0)).status == L.OK


def test_c2_without_wll_is_not_checked_and_off_line_hook_noted():
    r = L.two_leg(t(10.0), (0, 0, 0), (4, 0, 0), (2.0, 0.5, 3.0))
    assert r.status == L.NOT_CHECKED and any("beside the line" in n for n in r.notes)
    r = L.two_leg(t(10.0), (0, 0, 0), (4, 0, 0), (5.0, 0, 3.0), leg_wll=t(20))
    assert r.status == L.RED


def test_c4_angle_and_side_load():
    assert L.wll_use(L.newton(t(5)), t(10), angle=70).status == L.RED
    r = L.wll_use(L.newton(t(5)), t(10), item="shackle", side_angle=8)
    assert r.status == L.OK and any("Side load" in n for n in r.notes)
    assert L.wll_use(L.newton(t(4)), t(5), mode_factor=0.8).use == pytest.approx(1.0)


# --- C3 ---------------------------------------------------------------------------------------------------------------

POINTS = [(2, 1.5, 0), (2, -1.5, 0), (-2, 1.5, 0), (-2, -1.5, 0)]


def test_c3_rigid_load_two_legs_carry():
    r = L.multi_leg(t(20.0), POINTS, (0, 0, 3.5), leg_wll=t(12.5))
    d = r.details
    assert round(d["length"][0], 4) == 4.3012 and round(d["angle"][0], 2) == 35.54
    assert round(ft(r.value), 3) == 12.289
    assert round(ft(d["equal_share"][0]), 3) == 6.145
    assert round(ft(d["dnv_share"][0]), 3) == 7.681
    leg, assembly = r.parts
    assert round(assembly.use * 100, 1) == 76.2 and assembly.limit == pytest.approx(t(26.25))
    assert round(leg.use * 100, 1) == 98.3 and leg.status == L.AMBER
    assert r.status == L.AMBER


def test_c3_modes_and_steep_leg():
    assert ft(L.multi_leg(t(20), POINTS, (0, 0, 3.5), mode="dnv").value) == pytest.approx(7.681, abs=5e-4)
    h = 2.5 / math.tan(math.radians(70))
    r = L.multi_leg(t(20), POINTS, (0, 0, h), leg_wll=t(12.5))
    assert round(r.details["angle"][0]) == 70 and r.status == L.RED
    assert L.assembly_factor(45) == 2.1 and L.assembly_factor(50) == 1.5 and L.assembly_factor(61) is None
    with pytest.raises(ValueError):
        L.multi_leg(t(20), POINTS[:2], (0, 0, 3))


# --- C5 ---------------------------------------------------------------------------------------------------------------

CARRIER = [(t(30.0), 0.5, 0.0)]
UPPER = [(t(8.0), 0.0, 0.0), (t(12.0), -4.5, 0.0)]


def test_c5_four_outriggers():
    items = L.crane_items(CARRIER, UPPER, t(13.6), 12.0, 30.0)
    re = L.outrigger_reactions(items, 3.5, 3.3)
    assert round(L.tonnes(re.P), 1) == 63.6
    assert round(re.x, 4) == 1.7228 and round(re.y, 4) == 0.8585
    assert [round(ft(v), 3) for v in re.reactions] == [27.863, 19.590, 12.210, 3.937]
    assert sum(re.reactions) == pytest.approx(L.newton(t(63.6)))
    r = L.outriggers(items, 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3)
    assert round(L.kN(r.details["r_max"]), 1) == 273.2
    assert round(L.kPa(r.value), 1) == 121.4
    assert round(r.use * 100, 1) == 60.7 and r.status == L.OK


def test_c5_one_corner_lifts():
    items = L.crane_items(CARRIER, UPPER, t(26.0), 12.0, 45.0)
    re = L.outrigger_reactions(items, 3.5, 3.3)
    assert round(re.x, 4) == 2.5978 and round(re.y, 4) == 2.4004
    four = [L.newton(re.P) / 4 * (1 + sx * re.x / 3.5 + sy * re.y / 3.3) for sx, sy in ((-1, -1),)]
    assert round(ft(four[0]), 3) == -8.923
    assert re.lifted == 3
    assert [round(ft(v), 3) for v in re.reactions[:3]] == [55.846, 10.359, 9.795]
    r = L.outriggers(items, 3.5, 3.3, mat=(1.5, 1.5), allowable=10e6)
    assert r.status == L.AMBER and any("One outrigger unloaded" in n for n in r.notes)
    assert L.outriggers(L.crane_items(CARRIER, UPPER, t(80.0), 12.0, 45.0), 3.5, 3.3).status == L.RED


def test_c5_sweep_and_missing_data():
    r = L.outriggers(L.crane_items(CARRIER, UPPER, t(13.6), 12.0, 30.0), 3.5, 3.3)
    assert r.status == L.NOT_CHECKED and r.details["reactions"]
    s = L.outriggers_sweep(CARRIER, UPPER, t(13.6), 12.0, 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3, step=5)
    assert s.value >= r.details["r_max"] / 2.25 - 1e-6 and "slew" in s.details


# --- C6 ---------------------------------------------------------------------------------------------------------------

def test_c6_trapezoid_and_triangle():
    r = L.tracks(t(300.0), 1.2, 0.9, 6.0, 8.0, 1.2, allowable=500e3)
    assert [round(ft(v), 1) for v in r.details["share"]] == [195.0, 105.0]
    assert round(ft(r.value), 3) == 38.594 and round(L.kPa(r.value), 1) == 378.5
    assert round(ft(r.details["p_min"][0]), 3) == 2.031
    r = L.tracks(t(300.0), 1.6, 0.9, 6.0, 8.0, 1.2)
    assert round(ft(r.value), 3) == 45.139 and round(L.kPa(r.value), 1) == 442.7
    assert round(r.details["contact"][0], 2) == 7.20 and r.status == L.NOT_CHECKED
    assert L.tracks(t(300.0), 4.0, 0.0, 6.0, 8.0, 1.2).status == L.RED


# --- C7 ---------------------------------------------------------------------------------------------------------------

def test_c7_forklift():
    r = L.forklift(1900.0, 2500.0, 0.5, 0.7, 0.42)
    assert round(r.limit, 1) == 1785.7 and round(r.details["moment_rule"], 1) == 2053.6
    assert round(r.use * 100, 1) == 106.4 and r.status == L.RED
    assert round(r.details["moment_use"] * 100, 1) == 92.5
    table = [(0.5, 3.0, 2500.0), (0.6, 3.0, 2100.0), (0.8, 3.0, 1600.0), (0.8, 5.0, 1400.0)]
    r = L.forklift(1500.0, 2500.0, 0.5, 0.7, 0.42, table=table, lift_height=4.0)
    assert r.limit == 1400.0
    assert L.forklift(1500.0, 2500.0, 0.5, 0.9, 0.42, table=table).status == L.RED


# --- C8 ---------------------------------------------------------------------------------------------------------------

def test_c8_daf():
    shl = L.static_hook_load(t(370.0), rigging=t(5.0), tool=t(25.0))
    assert shl == pytest.approx(t(400.0))
    r = L.dynamic_load(shl, "offshore", chart_capacity=t(600.0))
    assert r.details["daf"] == 1.20 and r.value == pytest.approx(t(480.0))
    assert round(r.use * 100, 1) == 80.0 and r.status == L.AMBER and L.DAF_NOTE in r.notes
    bands = [(t(50), (1.10, 1.15, 1.30)), (t(200), (1.05, 1.12, 1.25)), (t(700), (1.05, 1.10, 1.20)),
             (t(2000), (1.03, 1.08, 1.15)), (t(3000), (1.03, 1.05, 1.10))]
    for shl_, f in bands:
        assert tuple(L.daf_for(shl_, s) for s in L.SITES) == f
    assert L.daf_for(t(100), "offshore") == 1.30 and L.daf_for(t(100.001), "offshore") == 1.25
    assert L.dynamic_load(shl, "offshore", hs_rated=True).status == L.NOT_CHECKED
    with pytest.raises(ValueError):
        L.daf_for(shl, "harbour")


# --- C9 ---------------------------------------------------------------------------------------------------------------

def test_c9_upending():
    pile = [(t(2000.0), 45.0)]
    for angle in (0, 20, 45, 70, 89.9):
        r = L.upending(pile, 100.0, angle)
        assert round(ft(r.value), 3) == 900.0
        assert round(ft(r.details["hinge"]), 3) == 1100.0
    assert round(ft(L.upending(pile + [(t(60.0), 100.0)], 100.0, 30).value), 3) == 960.0
    assert round(ft(L.upending(pile + [(t(60.0), 100.0)], 100.0, 90).value), 3) == 2060.0
    assert round(ft(L.upending(pile, 100.0, 30, off_hinge=True).value), 3) == 2000.0
    r = L.upending(pile, 100.0, 30, capacity=t(1200.0))
    assert r.use == pytest.approx(0.75) and r.status == L.AMBER


def test_c9_rope_not_vertical_balances_moments():
    pile = [(t(100.0), 40.0)]
    r = L.upending(pile, 90.0, 30.0, rope=(-0.2, 1.0))
    f = r.value
    th = math.radians(30.0)
    n = math.hypot(-0.2, 1.0)
    rh, ru = -0.2 / n, 1.0 / n
    moment_rope = f * 90.0 * (math.cos(th) * ru - math.sin(th) * rh)
    assert moment_rope == pytest.approx(L.newton(t(100.0)) * 40.0 * math.cos(th))


# --- charts ---------------------------------------------------------------------------------------------------------

def test_lookup_rules():
    c = L.Chart(radius=[8, 10, 12], capacity=[t(30), None, t(20)])
    assert L.lookup(c, 10.0).capacity is None and "gap" in L.lookup(c, 9.0).reason
    assert L.lookup(c, 12.0).capacity == t(20) and L.lookup(c, 12.0).row_radius == 12
    assert L.lookup(c, 8.0).capacity == t(30)
    assert "outside the chart" in L.lookup(c, 12.5).reason


def test_chart_validation():
    good = chart_c1()
    assert L.validate_chart(good) == ([], [])
    bad = [L.Chart(radius=[], capacity=[]), L.Chart(radius=[8, 8], capacity=[1, 1]),
           L.Chart(radius=[8, 10], capacity=[t(10), t(12)]), L.Chart(radius=[8, 10], capacity=[0, 1]),
           L.Chart(radius=[8, 10], capacity=[1]), L.Chart(radius=[-1, 10], capacity=[2, 1]),
           L.Chart(radius=[8, 10], capacity=[float("nan"), 1])]
    for c in bad:
        assert L.validate_chart(c)[0], c
        assert L.lookup(c, 9.0).capacity is None
    calm = chart_c1(config={"boom": 30.0, "hs": 1.0})
    rough = L.Chart(radius=[8.0, 12.0], capacity=[t(37.0), t(20.0)], config={"boom": 30.0, "hs": 2.0})
    errs, _ = L.validate_charts([calm, rough])
    assert any("calmer" in e for e in errs)
    longer = L.Chart(radius=[8.0, 12.0], capacity=[t(37.0), t(20.0)], config={"boom": 40.0, "hs": 1.0})
    errs, warns = L.validate_charts([calm, longer])
    assert not errs and any("boom" in w for w in warns)
    assert L.validate_charts([calm, chart_c1(config={"boom": 30.0, "hs": 1.0})])[0]


def test_pick_chart_and_units():
    charts = [chart_c1(config={"boom": b, "counterweight": t(12.0)}) for b in (20.0, 30.0, 40.0)]
    c, note = L.pick_chart(charts, boom=25.0, counterweight=t(12.0))
    assert c.config["boom"] == 30.0 and "next longer boom" in note
    assert L.pick_chart(charts, boom=45.0)[0] is None
    assert L.pick_chart(charts, counterweight=t(10.0))[0] is None
    d = {"config": {"boom": 100.0, "counterweight": 26.4554, "hs": 1.5}, "radius": [26.247, 32.808],
         "capacity": [79366.4, None]}
    c = L.chart_from_dict(d, mass_unit="lb", length_unit="ft")
    assert c.radius[0] == pytest.approx(8.0, abs=1e-4) and c.capacity[0] == pytest.approx(36000.0, rel=1e-6)
    assert c.config["boom"] == pytest.approx(30.48) and c.config["hs"] == 1.5 and c.capacity[1] is None
    back = L.chart_to_dict(c, mass_unit="lb", length_unit="ft")
    assert back["radius"] == pytest.approx(d["radius"]) and back["config"]["counterweight"] == pytest.approx(26.4554)
    with pytest.raises(ValueError):
        L.chart_from_dict(d, mass_unit="stone")


# --- status, words, categories -------------------------------------------------------------------------------------

def test_status_and_worst():
    assert L.status_of(None, 0.75) == L.NOT_CHECKED
    assert L.status_of(0.7499, 0.75) == L.OK and L.status_of(0.75, 0.75) == L.AMBER
    assert L.status_of(1.0, 0.75) == L.AMBER and L.status_of(1.0001, 0.75) == L.RED
    assert L.worst_status([L.OK, L.NOT_CHECKED]) == L.NOT_CHECKED
    assert L.worst_status([L.AMBER, L.NOT_CHECKED, L.RED]) == L.RED
    rs = [L.crane_use(t(10), 12, chart_c1()), L.crane_use(t(20), 12, chart_c1()), L.crane_use(t(15), 12, chart_c1())]
    assert L.worst(rs) == 1 and L.worst([]) is None


def _all_results():
    yield L.crane_use(t(12.4), 11.3, chart_c1(), rigging=t(0.35), hook_block=t(0.85), wind_area=50)
    yield L.crane_use(t(13.6), 14.5, chart_c1())
    yield L.two_leg(t(10.0), (0, 0, 0), (4, 0, 0), (1.5, 0.1, 3.0), leg_wll=t(8.0), shackle_wll=t(8.5))
    yield L.multi_leg(t(20.0), POINTS, (0, 0, 0.9), leg_wll=t(12.5))
    yield L.wll_use(L.newton(t(5)), t(10), item="shackle", side_angle=8, angle=70)
    yield L.outriggers(L.crane_items(CARRIER, UPPER, t(26.0), 12.0, 45.0), 3.5, 3.3)
    yield L.outriggers(L.crane_items(CARRIER, UPPER, t(80.0), 12.0, 45.0), 3.5, 3.3)
    yield L.tracks(t(300.0), 1.6, 0.9, 6.0, 8.0, 1.2, allowable=400e3)
    yield L.forklift(1900.0, 2500.0, 0.5, 0.7, 0.42)
    yield L.dynamic_load(t(400.0), "offshore", chart_capacity=t(600.0))
    yield L.upending([(t(2000.0), 45.0)], 100.0, 90)


def _texts(r):
    yield r.message
    yield r.words
    yield r.formula
    yield r.leaves_out
    yield from r.notes
    for p in r.parts:
        yield from _texts(p)


def test_words_never_say_safe():
    texts = [x for r in _all_results() for x in _texts(r)]
    texts += [L.SAMPLE_MARK, L.SAMPLE_PAGE_MARK, L.NOT_CHECKED_BY_APP, L.DAF_NOTE, *L.NOT_DONE,
              *L.STATUS_WORDS.values(), *L.LEAVES_OUT.values()]
    for system in L.CATEGORY_SYSTEMS:
        texts += L.suggest_category(system, cranes=2, crane_use=0.9, offshore=True)[1]
    for text in texts:
        for w in L.FORBIDDEN_WORDS:
            assert not re.search(rf"\b{re.escape(w)}\b", text, re.I), (w, text)
    assert L.PLANNING_AID.startswith("Planning aid only.") and "competent person" in L.PLANNING_AID


def test_results_are_json():
    for r in _all_results():
        d = r.to_dict()
        json.dumps(d, allow_nan=False)
        assert d["status"] in L.STATUS_WORDS and d["inputs"] is not None


def test_categories():
    assert L.suggest_category()[0] == "basic"
    assert L.suggest_category(crane_use=0.8)[0] == "intermediate"
    assert L.suggest_category(pick_and_carry=True)[0] == "intermediate"
    assert L.suggest_category(cranes=2)[0] == "complex"
    assert L.suggest_category("ASME P30.1")[0] == "standard"
    assert L.suggest_category("ASME P30.1", offshore=True)[0] == "critical"
    with pytest.raises(ValueError):
        L.suggest_category("ISO")


def test_no_blender_import():
    import fresing_render.core.lifting as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert "import bpy" not in src and "numpy" not in src
