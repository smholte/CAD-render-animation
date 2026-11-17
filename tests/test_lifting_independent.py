"""Independent tests of ``fresing_render/core/lifting.py`` (task 0182).

Written from study 0180 section 3 + 8 and the Design of task 0182 only, by an agent that did not read the module or
its author's tests. The worked cases C1-C9 are checked to the study's printed digits; the other tests check the
contract of the Design (units, status rules, words) and physics the author could get wrong.
"""

from __future__ import annotations

import json
import math
import re

import pytest

from fresing_render.core import lifting as L

G = 9.80665


def t_of(newtons):
    """A force in N as tonnes-force (the study's unit)."""
    return newtons / G / 1000.0


def kpa(pa):
    return pa / 1000.0


def walk(result):
    yield result
    for part in result.parts or []:
        yield from walk(part)


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


# A study chart: 8 m 36.0 t, 10 m 29.5 t, 12 m 24.0 t, 14 m 20.0 t.
def study_chart(**kw):
    return L.Chart(radius=[8.0, 10.0, 12.0, 14.0], capacity=[36000.0, 29500.0, 24000.0, 20000.0], **kw)


# ---------------------------------------------------------------------------------------------------------------
# Constants, units, status
# ---------------------------------------------------------------------------------------------------------------

def test_g_is_standard_gravity():
    assert L.G == pytest.approx(9.80665, abs=1e-12)


def test_edge_helpers():
    assert L.kg(1.0) == pytest.approx(1000.0)
    assert L.tonnes(2500.0) == pytest.approx(2.5)
    assert L.newton(1.0) == pytest.approx(G)
    assert L.force_t(G * 1000.0) == pytest.approx(1.0)
    assert L.kN(12345.0) == pytest.approx(12.345)
    assert L.kPa(121400.0) == pytest.approx(121.4)


def test_unit_tables():
    assert L.MASS_UNITS == {"kg": 1, "t": 1000, "lb": 0.45359237}
    assert L.LENGTH_UNITS == {"m": 1, "mm": 0.001, "ft": 0.3048}


def test_status_constants_and_words():
    assert (L.OK, L.AMBER, L.RED, L.NOT_CHECKED) == ("ok", "amber", "red", "not_checked")
    assert L.STATUS_WORDS == {
        "ok": "Within entered limits",
        "amber": "Near entered limit",
        "red": "Over entered limit",
        "not_checked": "Not checked",
    }


@pytest.mark.parametrize("use, amber_at, status", [
    (None, 0.75, "not_checked"),
    (0.0, 0.75, "ok"),
    (0.5, 0.75, "ok"),
    (0.7499, 0.75, "ok"),
    (0.75, 0.75, "amber"),            # exactly at the limit = amber
    (0.75 - 1e-12, 0.75, "amber"),    # compared after rounding to 1e-9
    (0.9, 0.9, "amber"),
    (0.95, 0.9, "amber"),
    (1.0, 0.75, "amber"),             # exactly 100 % = amber
    (1.0 + 1e-12, 0.75, "amber"),     # rounding noise above 100 % is still 100 %
    (1.000001, 0.75, "red"),
    (1.5, 0.75, "red"),
])
def test_status_of(use, amber_at, status):
    assert L.status_of(use, amber_at) == status


@pytest.mark.parametrize("statuses, worst", [
    ([], "ok"),
    (["ok"], "ok"),
    (["ok", "not_checked"], "not_checked"),
    (["not_checked", "amber", "ok"], "amber"),
    (["amber", "red", "ok", "not_checked"], "red"),
    (["red", "red"], "red"),
])
def test_worst_status(statuses, worst):
    assert L.worst_status(statuses) == worst


def test_limits_defaults():
    lim = L.Limits()
    assert (lim.crane, lim.rigging, lim.ground) == (0.75, 0.90, 0.90)
    d = L.DEFAULT_LIMITS
    assert (d.crane, d.rigging, d.ground) == (0.75, 0.90, 0.90)


def test_worst_picks_status_then_use():
    rs = [L.wll_use(u * 1000 * G, 1000.0) for u in (0.5, 0.95, 0.92, 0.2)]
    assert [r.status for r in rs] == ["ok", "amber", "amber", "ok"]
    assert L.worst(rs) == 1
    rs2 = [L.wll_use(0.99 * 1000 * G, 1000.0), L.wll_use(1.01 * 1000 * G, 1000.0)]
    assert L.worst(rs2) == 1
    rs3 = [L.wll_use(0.3 * 1000 * G, 1000.0), L.wll_use(0.4 * 1000 * G, None)]
    assert rs3[1].status == "not_checked"
    assert L.worst(rs3) == 1   # not_checked ranks above ok


# ---------------------------------------------------------------------------------------------------------------
# Words (section 8)
# ---------------------------------------------------------------------------------------------------------------

STUDY_PLANNING_AID = (
    "Planning aid only. Fresing Render checks this plan against the data entered in it, not against the real "
    "equipment, ground or load. The plan must be checked and approved by a competent person (for example the "
    "appointed person or lift director) before any lift."
)
STUDY_SAMPLE_MARK = ("SAMPLE – not for real lifts. Invented values to show how the app works. Enter the chart of "
                     "your real crane.")


def test_planning_aid_is_the_studys_line():
    assert L.PLANNING_AID == STUDY_PLANNING_AID


def test_sample_mark():
    assert L.SAMPLE_MARK.startswith("SAMPLE – not for real lifts.")
    assert L.SAMPLE_MARK == STUDY_SAMPLE_MARK


def test_not_checked_by_app_and_not_done():
    assert L.NOT_CHECKED_BY_APP == "not checked by Fresing Render – competent person"
    assert isinstance(L.NOT_DONE, (list, tuple)) and len(L.NOT_DONE) >= 5
    assert all(isinstance(x, str) and x.strip() for x in L.NOT_DONE)
    joined = " ".join(L.NOT_DONE).lower()
    for topic in ("soil", "people", "certificat"):
        assert topic in joined


def test_forbidden_words_list():
    assert tuple(L.FORBIDDEN_WORDS) == ("safe", "approved", "certified", "compliant", "OK to lift", "passed")


_FORBIDDEN = re.compile(r"\b(" + "|".join(re.escape(w) for w in
                                          ("safe", "approved", "certified", "compliant", "OK to lift", "passed"))
                        + r")\b", re.IGNORECASE)


def _texts(result):
    for r in walk(result):
        yield r.message or ""
        yield r.words or ""
        yield r.title or ""
        yield r.formula or ""
        for n in r.notes or []:
            yield n
        lo = r.leaves_out
        if isinstance(lo, str):
            yield lo
        elif lo:
            yield from lo


def _many_results():
    ch = study_chart()
    out = [
        L.crane_use(12400, 11.3, ch, rigging=350, hook_block=850),
        L.crane_use(12400, 14.5, ch, rigging=350, hook_block=850),
        L.crane_use(12400, 7.0, ch),
        L.crane_use(12400, 11.0, L.Chart(radius=[10, 12, 14], capacity=[29500, None, 20000])),
        L.crane_use(12400, 11.0, ch, wind_area=40.0),
        L.crane_use(12400, 11.0, L.Chart(radius=[10, 12], capacity=[29500, 24000], config={"hs": 1.5}), daf=1.2),
        L.two_leg(10000, (0, 0, 0), (4, 0, 0), (1.5, 0, 3), leg_wll=8000, shackle_wll=8500),
        L.two_leg(10000, (0, 0, 0), (4, 0, 0), (1.5, 0.5, 3)),
        L.multi_leg(20000, _rect(), (0, 0, 3.5), leg_wll=12500),
        L.multi_leg(20000, _rect(), (0, 0, 0.5), leg_wll=12500),
        L.multi_leg(20000, _rect(), (0, 0, 3.5), mode="dnv"),
        L.wll_use(50000.0, 4000, angle=65, side_angle=10),
        L.outriggers(_c5_items(13600, 30), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3),
        L.outriggers(_c5_items(26000, 45), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3),
        L.outriggers([(10000, 0, 0), (50000, 10, 0)], 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3),
        L.outriggers(_c5_items(13600, 30), 3.5, 3.3),
        L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2, allowable=500e3),
        L.tracks(300000, 1.2, 4.0, 6.0, 8.0, 1.2, allowable=500e3),
        L.forklift(1900, 2500, 0.5, 0.7, 0.42),
        L.forklift(1900, 2500, 0.5, 1.5, 0.42, table=[(0.5, 3.0, 2500)]),
        L.dynamic_load(400000, "offshore", chart_capacity=600000),
        L.dynamic_load(400000, "offshore", hs_rated=True),
        L.upending([(2000000, 45)], 100, 90),
        L.upending([(2000000, 45)], 100, 30, capacity=1000000),
    ]
    return out


def test_no_forbidden_word_in_any_result_text():
    for r in _many_results():
        for text in _texts(r):
            assert not _FORBIDDEN.search(text), (r.check, text)


def test_no_forbidden_word_in_module_words():
    texts = list(L.STATUS_WORDS.values()) + list(L.NOT_DONE) + [L.SAMPLE_MARK, L.NOT_CHECKED_BY_APP, L.DAF_NOTE]
    for text in texts:
        assert not _FORBIDDEN.search(text), text


def test_no_forbidden_word_in_lookup_and_validation_texts():
    bad = L.Chart(radius=[10, 8], capacity=[1000, 2000], interpolate=True)
    errors, warnings = L.validate_chart(bad)
    texts = errors + warnings
    for r in (5.0, 9.0, 20.0):
        texts.append(L.lookup(study_chart(), r).reason or "")
    for text in texts:
        assert not _FORBIDDEN.search(text), text


def test_words_match_status_everywhere():
    for r in _many_results():
        for x in walk(r):
            assert x.status in ("ok", "amber", "red", "not_checked")
            assert x.words == L.STATUS_WORDS[x.status]


def test_parent_status_is_worst_of_parts():
    for r in _many_results():
        for x in walk(r):
            if x.parts:
                rank = {"ok": 0, "not_checked": 1, "amber": 2, "red": 3}
                assert rank[x.status] >= max(rank[p.status] for p in x.parts)


def test_to_dict_is_json():
    for r in _many_results():
        d = r.to_dict()
        assert isinstance(d, dict)
        s = json.dumps(d)
        back = json.loads(s)
        assert back["status"] == r.status
        assert back["check"] == r.check


def test_leaves_out_present():
    for r in _many_results():
        assert r.leaves_out, r.check


# ---------------------------------------------------------------------------------------------------------------
# Lift categories
# ---------------------------------------------------------------------------------------------------------------

def test_category_systems():
    assert L.CATEGORY_SYSTEMS == {"BS 7121": ("basic", "intermediate", "complex"),
                                  "ASME P30.1": ("standard", "critical")}
    assert L.DEFAULT_CATEGORY_SYSTEM == "BS 7121"


@pytest.mark.parametrize("kw, cat", [
    ({}, "basic"),
    ({"cranes": 2}, "complex"),
    ({"people": True}, "complex"),
    ({"cranes": 2, "offshore": True}, "complex"),
    ({"crane_use": 0.8}, "intermediate"),
    ({"crane_use": 0.75}, "basic"),
    ({"crane_use": 0.5}, "basic"),
    ({"crane_use": 0.8, "crane_limit": 0.85}, "basic"),
    ({"offshore": True}, "intermediate"),
    ({"pick_and_carry": True}, "intermediate"),
])
def test_suggest_category_bs7121(kw, cat):
    got, reasons = L.suggest_category(**kw)
    assert got == cat
    assert isinstance(reasons, (list, tuple))
    if cat != "basic":
        assert reasons and all(isinstance(x, str) for x in reasons)
    got2, _ = L.suggest_category(system="BS 7121", **kw)
    assert got2 == cat


@pytest.mark.parametrize("kw, cat", [
    ({}, "standard"),
    ({"cranes": 3}, "critical"),
    ({"people": True}, "critical"),
    ({"crane_use": 0.9}, "critical"),
    ({"crane_use": 0.7}, "standard"),
    ({"offshore": True}, "critical"),
    ({"pick_and_carry": True}, "standard"),
])
def test_suggest_category_asme(kw, cat):
    got, reasons = L.suggest_category(system="ASME P30.1", **kw)
    assert got == cat
    assert got in L.CATEGORY_SYSTEMS["ASME P30.1"]


def test_suggest_category_unknown_system():
    with pytest.raises(ValueError):
        L.suggest_category(system="EN 13001")


# ---------------------------------------------------------------------------------------------------------------
# Charts: validation
# ---------------------------------------------------------------------------------------------------------------

def test_chart_defaults():
    ch = L.Chart(radius=[8.0], capacity=[1000.0])
    assert ch.config == {} and ch.name == ""
    assert ch.includes_hook_block is False and ch.interpolate is False
    assert ch.wind_max is None and ch.sample is False


def test_valid_chart_has_no_errors():
    assert L.validate_chart(study_chart()) == ([], [])


def test_equal_capacity_and_gaps_allowed():
    errors, warnings = L.validate_chart(L.Chart(radius=[8, 10, 12, 14], capacity=[30000, 30000, None, 20000]))
    assert errors == [] and warnings == []


@pytest.mark.parametrize("radius, capacity", [
    ([], []),                                         # no rows
    ([8, 10], [36000]),                               # different lengths
    ([0.0, 10], [36000, 29500]),                      # radius not > 0
    ([-8, 10], [36000, 29500]),
    ([float("nan"), 10], [36000, 29500]),
    ([8, float("inf")], [36000, 29500]),
    ([8, 8, 10], [36000, 30000, 29500]),              # not strictly rising
    ([10, 8], [29500, 36000]),
    ([8, 10], [36000, 0.0]),                          # capacity not > 0
    ([8, 10], [36000, -1.0]),
    ([8, 10], [36000, float("nan")]),
    ([8, 10], [float("inf"), 29500]),
    ([8, 10], [29500, 36000]),                        # rising capacity
    ([8, 10, 12], [30000, None, 31000]),              # rising over a gap
])
def test_invalid_charts(radius, capacity):
    errors, _ = L.validate_chart(L.Chart(radius=radius, capacity=capacity))
    assert errors and all(isinstance(e, str) and e for e in errors)


def test_interpolate_is_only_a_warning():
    errors, warnings = L.validate_chart(study_chart(interpolate=True))
    assert errors == []
    assert len(warnings) == 1
    assert "next longer radius" in warnings[0]


def test_validate_charts_duplicate_config():
    a = study_chart(config={"boom": 30.0, "counterweight": 12000.0})
    b = study_chart(config={"boom": 30.0, "counterweight": 12000.0})
    errors, _ = L.validate_charts([a, b])
    assert errors


def test_validate_charts_includes_each_charts_errors():
    good = study_chart(config={"boom": 30.0})
    bad = L.Chart(radius=[10, 8], capacity=[1, 2], config={"boom": 40.0})
    errors, _ = L.validate_charts([good, bad])
    assert errors
    errors2, warnings2 = L.validate_charts([good, study_chart(config={"boom": 40.0}, interpolate=True)])
    assert warnings2   # each chart's warnings come through


def test_validate_charts_hs_columns():
    calm = L.Chart(radius=[8, 10], capacity=[30000, 25000], config={"boom": 30.0, "hs": 1.0})
    rough_ok = L.Chart(radius=[8, 10], capacity=[25000, 20000], config={"boom": 30.0, "hs": 2.0})
    rough_bad = L.Chart(radius=[8, 10], capacity=[25000, 26000], config={"boom": 30.0, "hs": 2.0})
    assert L.validate_charts([calm, rough_ok])[0] == []
    assert L.validate_charts([calm, rough_bad])[0]
    # order in the list must not matter
    assert L.validate_charts([rough_bad, calm])[0]


def test_validate_charts_boom_is_warning_only():
    short = L.Chart(radius=[8, 10], capacity=[30000, 25000], config={"boom": 30.0})
    long_ok = L.Chart(radius=[8, 10], capacity=[28000, 24000], config={"boom": 40.0})
    long_more = L.Chart(radius=[8, 10], capacity=[32000, 25000], config={"boom": 40.0})
    assert L.validate_charts([short, long_ok]) == ([], [])
    errors, warnings = L.validate_charts([short, long_more])
    assert errors == []
    assert warnings


def test_validate_charts_different_configs_not_compared():
    # different counterweight: more capacity is fine, no warning, no error
    a = L.Chart(radius=[8, 10], capacity=[30000, 25000], config={"boom": 30.0, "counterweight": 10000.0})
    b = L.Chart(radius=[8, 10], capacity=[40000, 35000], config={"boom": 30.0, "counterweight": 20000.0})
    assert L.validate_charts([a, b]) == ([], [])


# ---------------------------------------------------------------------------------------------------------------
# Charts: lookup
# ---------------------------------------------------------------------------------------------------------------

def test_lookup_next_longer_radius_c1():
    lk = L.lookup(study_chart(), 11.3)
    assert lk.capacity == pytest.approx(24000.0)
    assert lk.row_radius == pytest.approx(12.0)


@pytest.mark.parametrize("radius, cap, row", [
    (8.0, 36000, 8.0),
    (8.0001, 29500, 10.0),
    (10.0, 29500, 10.0),             # exact hit takes that row
    (10.0 + 1e-10, 29500, 10.0),     # within 1e-9 m
    (10.0 - 1e-10, 29500, 10.0),
    (10.001, 24000, 12.0),
    (14.0, 20000, 14.0),
])
def test_lookup_rows(radius, cap, row):
    lk = L.lookup(study_chart(), radius)
    assert lk.capacity == pytest.approx(cap)
    assert lk.row_radius == pytest.approx(row)


def test_lookup_past_the_end():
    lk = L.lookup(study_chart(), 14.5)
    assert lk.capacity is None
    assert "outside the chart" in lk.reason


def test_lookup_before_first_row():
    lk = L.lookup(study_chart(), 7.0)
    assert lk.capacity is None
    assert "closer than the chart's shortest radius" in lk.reason


def test_lookup_gap_is_not_allowed_not_look_further():
    ch = L.Chart(radius=[8, 10, 12, 14], capacity=[36000, 29500, None, 20000])
    lk = L.lookup(ch, 11.0)
    assert lk.capacity is None
    assert "not allowed here" in lk.reason
    lk2 = L.lookup(ch, 12.0)
    assert lk2.capacity is None
    # beyond the gap the chart works again
    assert L.lookup(ch, 13.0).capacity == pytest.approx(20000)
    assert L.lookup(ch, 9.0).capacity == pytest.approx(29500)


def test_lookup_invalid_chart_reason_is_first_error():
    ch = L.Chart(radius=[10, 8], capacity=[29500, 36000])
    errors, _ = L.validate_chart(ch)
    lk = L.lookup(ch, 9.0)
    assert lk.capacity is None
    assert lk.reason == errors[0]


def test_lookup_never_interpolates_even_when_flag_set():
    lk = L.lookup(study_chart(interpolate=True), 11.3)
    assert lk.capacity == pytest.approx(24000.0)


def test_capacity_interpolated_c1():
    assert L.capacity_interpolated(study_chart(), 11.3) == pytest.approx(25925.0, abs=0.5)
    assert L.capacity_interpolated(study_chart(), 10.0) == pytest.approx(29500.0)
    assert L.capacity_interpolated(study_chart(), 9.0) == pytest.approx(32750.0)


def test_capacity_interpolated_outside_is_none():
    assert L.capacity_interpolated(study_chart(), 15.0) is None
    assert L.capacity_interpolated(study_chart(), 7.0) is None


# ---------------------------------------------------------------------------------------------------------------
# Charts: pick_chart, dict round trip
# ---------------------------------------------------------------------------------------------------------------

def _boom_charts():
    return [L.Chart(radius=[8, 10], capacity=[30000 - b * 100, 25000 - b * 100],
                    config={"boom": float(b), "counterweight": 12000.0}, name=f"boom {b}")
            for b in (30, 40, 50)] + [
        L.Chart(radius=[8, 10], capacity=[20000, 15000], config={"boom": 40.0, "counterweight": 6000.0},
                name="light cw")]


def test_pick_chart_next_longer_boom():
    ch, note = L.pick_chart(_boom_charts(), boom=35.0, counterweight=12000.0)
    assert ch is not None and ch.config["boom"] == pytest.approx(40.0)
    assert ch.config["counterweight"] == pytest.approx(12000.0)
    ch, _ = L.pick_chart(_boom_charts(), boom=40.0, counterweight=12000.0)
    assert ch.config["boom"] == pytest.approx(40.0)


def test_pick_chart_config_filter():
    ch, _ = L.pick_chart(_boom_charts(), boom=40.0, counterweight=6000.0)
    assert ch.name == "light cw"


def test_pick_chart_none():
    ch, note = L.pick_chart(_boom_charts(), boom=55.0, counterweight=12000.0)
    assert ch is None and isinstance(note, str) and note
    ch, note = L.pick_chart(_boom_charts(), boom=30.0, counterweight=99000.0)
    assert ch is None and note


def test_pick_chart_hs():
    charts = [L.Chart(radius=[8, 10], capacity=[30000 - h * 1000, 25000 - h * 1000], config={"hs": h})
              for h in (1.0, 1.5, 2.5)]
    assert L.pick_chart(charts, hs=1.2)[0].config["hs"] == pytest.approx(1.5)
    assert L.pick_chart(charts, hs=1.5)[0].config["hs"] == pytest.approx(1.5)
    assert L.pick_chart(charts, hs=0.5)[0].config["hs"] == pytest.approx(1.0)
    assert L.pick_chart(charts, hs=3.0)[0] is None


def test_chart_from_dict_tonnes_metres():
    d = {"name": "test", "config": {"boom": 30.0, "jib": 8.0, "counterweight": 12.0, "outriggers": 7.0, "hs": 1.5},
         "radius": [8.0, 10.0, 12.0], "capacity": [36.0, None, 24.0], "wind_max": 9.8,
         "includes_hook_block": True, "interpolate": False, "sample": True}
    ch = L.chart_from_dict(d)
    assert ch.radius == pytest.approx([8.0, 10.0, 12.0])
    assert ch.capacity[0] == pytest.approx(36000.0) and ch.capacity[1] is None
    assert ch.capacity[2] == pytest.approx(24000.0)
    assert ch.config["counterweight"] == pytest.approx(12000.0)
    assert ch.config["boom"] == pytest.approx(30.0)
    assert ch.config["hs"] == pytest.approx(1.5)
    assert ch.wind_max == pytest.approx(9.8)
    assert ch.includes_hook_block is True and ch.sample is True and ch.name == "test"


def test_chart_from_dict_lb_ft():
    d = {"config": {"boom": 100.0, "jib": 20.0, "outriggers": 20.0, "counterweight": 20000.0, "hs": 2.0},
         "radius": [10.0, 20.0], "capacity": [10000.0, 5000.0], "wind_max": 9.0}
    ch = L.chart_from_dict(d, mass_unit="lb", length_unit="ft")
    assert ch.radius == pytest.approx([3.048, 6.096])
    assert ch.capacity == pytest.approx([4535.9237, 2267.96185])
    assert ch.config["boom"] == pytest.approx(30.48)
    assert ch.config["jib"] == pytest.approx(6.096)
    assert ch.config["outriggers"] == pytest.approx(6.096)
    assert ch.config["counterweight"] == pytest.approx(9071.8474)
    assert ch.config["hs"] == pytest.approx(2.0)      # Hs stays in m
    assert ch.wind_max == pytest.approx(9.0)          # m/s, never converted


def test_chart_from_dict_kg_mm():
    d = {"config": {"boom": 30000.0}, "radius": [8000.0, 10000.0], "capacity": [36000.0, 29500.0]}
    ch = L.chart_from_dict(d, mass_unit="kg", length_unit="mm")
    assert ch.radius == pytest.approx([8.0, 10.0])
    assert ch.capacity == pytest.approx([36000.0, 29500.0])
    assert ch.config["boom"] == pytest.approx(30.0)


@pytest.mark.parametrize("mu, lu", [("t", "m"), ("kg", "mm"), ("lb", "ft"), ("t", "ft"), ("lb", "mm")])
def test_chart_dict_round_trip(mu, lu):
    d = {"name": "rt", "config": {"boom": 33.0, "counterweight": 7.5, "hs": 1.25},
         "radius": [5.0, 7.5, 11.0], "capacity": [40.0, None, 12.5], "wind_max": 12.0,
         "includes_hook_block": False, "interpolate": True, "sample": False}
    back = L.chart_to_dict(L.chart_from_dict(d, mass_unit=mu, length_unit=lu), mass_unit=mu, length_unit=lu)
    assert back["radius"] == pytest.approx(d["radius"])
    assert back["capacity"][0] == pytest.approx(40.0) and back["capacity"][1] is None
    assert back["capacity"][2] == pytest.approx(12.5)
    assert back["config"]["boom"] == pytest.approx(33.0)
    assert back["config"]["counterweight"] == pytest.approx(7.5)
    assert back["config"]["hs"] == pytest.approx(1.25)
    assert back["wind_max"] == pytest.approx(12.0)
    assert back["interpolate"] is True and back["name"] == "rt"
    json.dumps(back)


def test_chart_to_dict_converts_out():
    ch = study_chart(config={"boom": 30.48})
    d = L.chart_to_dict(ch, mass_unit="t", length_unit="ft")
    assert d["capacity"] == pytest.approx([36.0, 29.5, 24.0, 20.0])
    assert d["radius"][0] == pytest.approx(8.0 / 0.3048)
    assert d["config"]["boom"] == pytest.approx(100.0)


@pytest.mark.parametrize("mu, lu", [("stone", "m"), ("t", "yard"), ("tonne", "m"), ("kg", "inch")])
def test_chart_unknown_unit(mu, lu):
    d = {"config": {}, "radius": [8.0], "capacity": [1.0]}
    with pytest.raises(ValueError):
        L.chart_from_dict(d, mass_unit=mu, length_unit=lu)
    with pytest.raises(ValueError):
        L.chart_to_dict(study_chart(), mass_unit=mu, length_unit=lu)


# ---------------------------------------------------------------------------------------------------------------
# C1 crane use
# ---------------------------------------------------------------------------------------------------------------

def test_c1_worked_case():
    r = L.crane_use(12400, 11.3, study_chart(), rigging=350, hook_block=850)
    assert r.check == "C1"
    assert r.value == pytest.approx(13600.0)
    assert r.limit == pytest.approx(24000.0)
    assert r.use * 100 == pytest.approx(56.7, abs=0.05)
    assert r.status == "ok" and r.amber_at == pytest.approx(0.75)
    assert r.details["gross"] == pytest.approx(13600.0)
    assert r.details["capacity"] == pytest.approx(24000.0)
    assert r.details["row_radius"] == pytest.approx(12.0)
    assert isinstance(r.inputs, dict)


def test_c1_interpolated_number_only():
    # the worked case's 52.5 % with interpolation is a number only; the check stays on the next longer radius
    cap = L.capacity_interpolated(study_chart(), 11.3)
    assert 13600.0 / cap * 100 == pytest.approx(52.5, abs=0.05)
    r = L.crane_use(12400, 11.3, study_chart(interpolate=True), rigging=350, hook_block=850)
    assert r.limit == pytest.approx(24000.0)


def test_c1_past_the_chart_is_red():
    r = L.crane_use(12400, 14.5, study_chart(), rigging=350, hook_block=850)
    assert r.status == "red"
    assert "outside the chart" in r.message


def test_c1_gap_is_red_with_reason():
    ch = L.Chart(radius=[8, 10, 12, 14], capacity=[36000, 29500, None, 20000])
    r = L.crane_use(5000, 11.0, ch)
    assert r.status == "red"
    assert "not allowed here" in r.message


def test_c1_too_close_is_red():
    r = L.crane_use(5000, 6.0, study_chart())
    assert r.status == "red"
    assert "closer than" in r.message


def test_c1_hook_block_in_chart_not_added():
    r = L.crane_use(12400, 11.3, study_chart(includes_hook_block=True), rigging=350, hook_block=850)
    assert r.value == pytest.approx(12750.0)
    assert r.use == pytest.approx(12750.0 / 24000.0, rel=1e-6)


def test_c1_daf_on_static_chart():
    r = L.crane_use(12400, 11.3, study_chart(), rigging=350, hook_block=850, daf=1.1)
    assert r.value == pytest.approx(14960.0)
    assert r.use == pytest.approx(14960.0 / 24000.0, rel=1e-6)
    assert r.details["daf_applied"] is True or r.details["daf_applied"] == pytest.approx(1.1)


def test_c1_daf_not_applied_on_hs_chart():
    ch = study_chart(config={"hs": 1.5})
    r = L.crane_use(12400, 11.3, ch, rigging=350, hook_block=850, daf=1.2)
    assert r.value == pytest.approx(13600.0)
    assert r.details["daf_applied"] is False or r.details["daf_applied"] == pytest.approx(1.0)
    assert any("double count" in n.lower() for n in r.notes)


@pytest.mark.parametrize("load, status", [
    (14999.0, "ok"),
    (15000.0, "amber"),   # exactly 75 %
    (20000.0, "amber"),   # exactly 100 %
    (20001.0, "red"),
])
def test_c1_status_boundaries(load, status):
    ch = L.Chart(radius=[10.0], capacity=[20000.0])
    assert L.crane_use(load, 10.0, ch).status == status


def test_c1_own_limit():
    ch = L.Chart(radius=[10.0], capacity=[20000.0])
    r = L.crane_use(15000, 10.0, ch, limits=L.Limits(crane=0.8))
    assert r.status == "ok" and r.amber_at == pytest.approx(0.8)


def test_c1_wind_area_note_status_unchanged():
    ch = study_chart()
    plain = L.crane_use(12400, 11.3, ch, rigging=350, hook_block=850)
    windy = L.crane_use(12400, 11.3, ch, rigging=350, hook_block=850, wind_area=20.0)   # 1.6 m2/t
    calm = L.crane_use(12400, 11.3, ch, rigging=350, hook_block=850, wind_area=10.0)    # 0.8 m2/t
    assert windy.status == plain.status
    assert any("1.2" in n for n in windy.notes)
    assert not any("1.2" in n for n in calm.notes)
    assert len(windy.notes) > len(calm.notes)


# ---------------------------------------------------------------------------------------------------------------
# C2 two-leg
# ---------------------------------------------------------------------------------------------------------------

def _c2(**kw):
    return L.two_leg(10000, (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (1.5, 0.0, 3.0), **kw)


def test_c2_worked_case_forces():
    r = _c2()
    d = r.details
    assert r.check == "C2"
    assert t_of(d["vertical"][0]) == pytest.approx(6.250, abs=5e-4)
    assert t_of(d["vertical"][1]) == pytest.approx(3.750, abs=5e-4)
    assert d["length"][0] == pytest.approx(3.3541, abs=5e-5)
    assert d["length"][1] == pytest.approx(3.9051, abs=5e-5)
    assert t_of(d["force"][0]) == pytest.approx(6.988, abs=5e-4)
    assert t_of(d["force"][1]) == pytest.approx(4.881, abs=5e-4)
    assert d["angle"][0] == pytest.approx(26.57, abs=5e-3)
    assert d["angle"][1] == pytest.approx(39.81, abs=5e-3)
    assert t_of(abs(d["horizontal"][0])) == pytest.approx(3.125, abs=5e-4)
    assert t_of(abs(d["horizontal"][1])) == pytest.approx(3.125, abs=5e-4)
    assert t_of(r.value) == pytest.approx(6.988, abs=5e-4)


def test_c2_no_wll_is_not_checked():
    r = _c2()
    assert r.status == "not_checked"
    assert r.details["force"][0] > 0


def test_c2_invariants():
    d = _c2().details
    assert d["vertical"][0] + d["vertical"][1] == pytest.approx(10000 * G, rel=1e-9)
    assert abs(d["horizontal"][0]) == pytest.approx(abs(d["horizontal"][1]), rel=1e-9)
    for i in (0, 1):
        f, v, h = d["force"][i], d["vertical"][i], abs(d["horizontal"][i])
        assert math.hypot(v, h) == pytest.approx(f, rel=1e-9)
        assert math.degrees(math.atan2(h, v)) == pytest.approx(d["angle"][i], abs=1e-6)


def test_c2_against_wlls_amber_at_75():
    r = _c2(leg_wll=8000, shackle_wll=8500, limits=L.Limits(rigging=0.75))
    uses = sorted(p.use for p in r.parts)
    assert len(r.parts) == 4
    expected = sorted([6.988 / 8.0, 4.881 / 8.0, 6.988 / 8.5, 4.881 / 8.5])
    assert uses == pytest.approx(expected, abs=1e-3)
    assert max(uses) * 100 == pytest.approx(87.3, abs=0.05)
    assert any(p.use * 100 == pytest.approx(82.2, abs=0.05) for p in r.parts)
    assert r.status == "amber"


def test_c2_against_wlls_default_limits():
    r = _c2(leg_wll=8000, shackle_wll=8500)
    # 87.3 % and 82.2 % are below the owner's 90 % rigging limit
    assert r.status == "ok"
    assert all(p.amber_at == pytest.approx(0.90) for p in r.parts)


def test_c2_leg_wll_only_two_parts():
    r = _c2(leg_wll=8000)
    assert len(r.parts) == 2


def test_c2_red_part_lifts_check():
    r = _c2(leg_wll=6000, shackle_wll=8500)
    assert r.status == "red"


def test_c2_symmetric_equal_legs():
    d = L.two_leg(8000, (0, 0, 0), (4, 0, 0), (2, 0, 3)).details
    assert d["force"][0] == pytest.approx(d["force"][1], rel=1e-9)
    leg = math.hypot(2, 3)
    assert t_of(d["force"][0]) == pytest.approx(4.0 * leg / 3.0, rel=1e-9)


def test_c2_orientation_independent():
    a = _c2().details
    b = L.two_leg(10000, (5.0, 2.0, 1.0), (5.0, -2.0, 1.0), (5.0, 0.5, 4.0)).details
    assert b["force"][0] == pytest.approx(a["force"][0], rel=1e-9)
    assert b["force"][1] == pytest.approx(a["force"][1], rel=1e-9)


def test_c2_points_at_different_heights():
    # A (0,0,0), B (4,0,1), hook (1.5,0,3): solve the 2x2 statics by hand
    ax, az, bx, bz, hx, hz = 0.0, 0.0, 4.0, 1.0, 1.5, 3.0
    la, lb = math.hypot(hx - ax, hz - az), math.hypot(hx - bx, hz - bz)
    ua, ub = ((hx - ax) / la, (hz - az) / la), ((hx - bx) / lb, (hz - bz) / lb)
    det = ua[0] * ub[1] - ub[0] * ua[1]
    w = 10000 * G
    ta = (0 * ub[1] - ub[0] * w) / det
    tb = (ua[0] * w - 0 * ua[1]) / det
    d = L.two_leg(10000, (ax, 0, az), (bx, 0, bz), (hx, 0, hz)).details
    assert d["force"][0] == pytest.approx(ta, rel=1e-6)
    assert d["force"][1] == pytest.approx(tb, rel=1e-6)
    assert t_of(ta) == pytest.approx(7.986, abs=1e-3)


def test_c2_hook_off_plane_gives_note():
    inplane = _c2()
    off = L.two_leg(10000, (0, 0, 0), (4, 0, 0), (1.5, 0.3, 3.0))
    assert len(off.notes) > len(inplane.notes)
    tiny = L.two_leg(10000, (0, 0, 0), (4, 0, 0), (1.5, 0.0005, 3.0))   # 0.5 mm: no note
    assert len(tiny.notes) == len(inplane.notes)


# ---------------------------------------------------------------------------------------------------------------
# C3 multi-leg
# ---------------------------------------------------------------------------------------------------------------

def _rect():
    return [(2.0, 1.5, 0.0), (2.0, -1.5, 0.0), (-2.0, -1.5, 0.0), (-2.0, 1.5, 0.0)]


def test_c3_worked_case():
    r = L.multi_leg(20000, _rect(), (0.0, 0.0, 3.5))
    d = r.details
    assert r.check == "C3"
    assert all(x == pytest.approx(4.3012, abs=5e-5) for x in d["length"])
    assert all(x == pytest.approx(35.54, abs=5e-3) for x in d["angle"])
    assert t_of(r.value) == pytest.approx(12.289, abs=5e-4)
    assert all(t_of(x) == pytest.approx(12.289, abs=5e-4) for x in d["force"])
    assert all(t_of(x) == pytest.approx(6.145, abs=5e-4) for x in d["equal_share"])
    assert all(t_of(x) == pytest.approx(7.681, abs=5e-4) for x in d["dnv_share"])
    assert r.status == "not_checked"


def test_c3_skew_factor():
    assert L.SKEW_FACTOR_DNV == pytest.approx(1.25)


def test_c3_modes_value():
    eq = L.multi_leg(20000, _rect(), (0, 0, 3.5), mode="equalised")
    dnv = L.multi_leg(20000, _rect(), (0, 0, 3.5), mode="dnv")
    assert t_of(eq.value) == pytest.approx(6.145, abs=5e-4)
    assert t_of(dnv.value) == pytest.approx(7.681, abs=5e-4)


def test_c3_with_chain_wll():
    r = L.multi_leg(20000, _rect(), (0, 0, 3.5), leg_wll=12500)
    assert len(r.parts) == 2
    asm = [p for p in r.parts if p.value == pytest.approx(20000.0)]
    assert len(asm) == 1
    asm = asm[0]
    assert asm.limit == pytest.approx(26250.0)
    assert asm.use * 100 == pytest.approx(76.2, abs=0.05)
    leg = [p for p in r.parts if p is not asm][0]
    assert leg.use * 100 == pytest.approx(98.3, abs=0.05)
    assert leg.status == "amber"
    assert asm.status == "ok"            # 76.2 % < 90 %
    assert r.status == "amber"


def test_c3_assembly_amber_at_75():
    r = L.multi_leg(20000, _rect(), (0, 0, 3.5), leg_wll=12500, limits=L.Limits(rigging=0.75))
    asm = [p for p in r.parts if p.value == pytest.approx(20000.0)][0]
    assert asm.status == "amber"


def test_c3_assembly_factor_45_to_60():
    d = 2.5
    h = d / math.tan(math.radians(50.0))
    r = L.multi_leg(20000, _rect(), (0, 0, h), leg_wll=100000)
    asm = [p for p in r.parts if p.value == pytest.approx(20000.0)][0]
    assert asm.limit == pytest.approx(150000.0)
    assert r.status != "red"


def test_c3_assembly_factor_below_45():
    h = 2.5 / math.tan(math.radians(40.0))
    r = L.multi_leg(20000, _rect(), (0, 0, h), leg_wll=100000)
    asm = [p for p in r.parts if p.value == pytest.approx(20000.0)][0]
    assert asm.limit == pytest.approx(210000.0)


def test_c3_leg_above_60_is_red_even_with_big_wll():
    h = 2.5 / math.tan(math.radians(70.0))
    r = L.multi_leg(20000, _rect(), (0, 0, h), leg_wll=1_000_000)
    assert max(r.details["angle"]) == pytest.approx(70.0, abs=1e-6)
    assert r.status == "red"
    asm = [p for p in r.parts if p.value == pytest.approx(20000.0)][0]
    assert asm.status == "red"


def test_c3_59_degrees_not_red_by_angle():
    h = 2.5 / math.tan(math.radians(59.0))
    r = L.multi_leg(20000, _rect(), (0, 0, h), leg_wll=1_000_000)
    assert r.status != "red"


def test_c3_three_legs():
    pts = [(0.0, 2.0, 0.0), (math.sqrt(3), -1.0, 0.0), (-math.sqrt(3), -1.0, 0.0)]
    r = L.multi_leg(9000, pts, (0, 0, 3.0))
    leg = math.hypot(2.0, 3.0)
    assert t_of(r.value) == pytest.approx(4.5 * leg / 3.0, rel=1e-6)   # two legs carry
    assert t_of(r.details["equal_share"][0]) == pytest.approx(3.0 * leg / 3.0, rel=1e-6)


@pytest.mark.parametrize("n", [1, 2, 5])
def test_c3_wrong_number_of_points(n):
    pts = [(math.cos(k), math.sin(k), 0.0) for k in range(n)]
    with pytest.raises(ValueError):
        L.multi_leg(1000, pts, (0, 0, 3))


def test_c3_uneven_hook_per_leg_formula():
    hook = (0.5, 0.2, 3.5)
    pts = _rect()
    r = L.multi_leg(20000, pts, hook)
    for (x, y, z), f in zip(pts, r.details["force"]):
        li = math.dist((x, y, z), hook)
        hi = hook[2] - z
        assert f == pytest.approx(20000 * G / 2 * li / hi, rel=1e-9)
    assert r.value == pytest.approx(max(r.details["force"]), rel=1e-12)


# ---------------------------------------------------------------------------------------------------------------
# C4 WLL use
# ---------------------------------------------------------------------------------------------------------------

def test_c4_basic():
    r = L.wll_use(6.988 * 1000 * G, 8000)
    assert r.check == "C4"
    assert r.limit == pytest.approx(8000.0)
    assert r.use == pytest.approx(6.988 / 8.0, rel=1e-9)
    assert r.amber_at == pytest.approx(0.90)
    assert r.status == "ok"


def test_c4_mode_factor():
    r = L.wll_use(5000 * G, 8000, mode_factor=0.8)
    assert r.limit == pytest.approx(6400.0)
    assert r.use == pytest.approx(5000 / 6400, rel=1e-9)
    assert r.status == "ok"
    assert L.wll_use(6000 * G, 8000, mode_factor=0.8).status == "amber"


@pytest.mark.parametrize("force_kg, status", [(899.0, "ok"), (900.0, "amber"), (1000.0, "amber"), (1000.5, "red")])
def test_c4_boundaries(force_kg, status):
    assert L.wll_use(force_kg * G, 1000).status == status


def test_c4_angle_above_60_red():
    assert L.wll_use(100 * G, 1000, angle=61).status == "red"
    assert L.wll_use(100 * G, 1000, angle=59).status == "ok"


def test_c4_side_angle_note_only():
    plain = L.wll_use(100 * G, 1000)
    side = L.wll_use(100 * G, 1000, side_angle=8)
    small = L.wll_use(100 * G, 1000, side_angle=3)
    assert side.status == plain.status == "ok"
    assert len(side.notes) > len(plain.notes)
    assert len(small.notes) == len(plain.notes)


def test_c4_no_wll_not_checked():
    assert L.wll_use(100 * G, None).status == "not_checked"


# ---------------------------------------------------------------------------------------------------------------
# C5 outriggers
# ---------------------------------------------------------------------------------------------------------------

CARRIER = [(30000.0, 0.5, 0.0)]
UPPER = [(8000.0, 0.0, 0.0), (12000.0, -4.5, 0.0)]


def _c5_items(load, slew):
    return L.crane_items(CARRIER, UPPER, load, 12.0, slew)


def _mass_of(items):
    return sum(m for m, _, _ in items)


def test_c5_crane_items_resultant():
    items = _c5_items(13600, 30)
    p = _mass_of(items)
    assert p == pytest.approx(63600.0)
    x = sum(m * xi for m, xi, _ in items) / p
    y = sum(m * yi for m, _, yi in items) / p
    assert x == pytest.approx(1.7228, abs=5e-5)
    assert y == pytest.approx(0.8585, abs=5e-5)


def test_c5_slew_direction_and_side():
    items = L.crane_items([], [(1000.0, 0.0, 1.0)], 500.0, 10.0, 90.0)
    load = [it for it in items if it[0] == pytest.approx(500.0)][0]
    assert load[1] == pytest.approx(0.0, abs=1e-9) and load[2] == pytest.approx(10.0)
    side = [it for it in items if it[0] == pytest.approx(1000.0)][0]
    assert side[1] == pytest.approx(-1.0) and side[2] == pytest.approx(0.0, abs=1e-9)
    items0 = L.crane_items([], [(1000.0, 0.0, 1.0)], 500.0, 10.0, 0.0)
    side0 = [it for it in items0 if it[0] == pytest.approx(1000.0)][0]
    assert side0[1] == pytest.approx(0.0, abs=1e-9) and side0[2] == pytest.approx(1.0)


def test_c5_carrier_does_not_turn():
    a = L.crane_items([(30000.0, 0.5, 0.2)], [], 1000.0, 10.0, 0.0)
    b = L.crane_items([(30000.0, 0.5, 0.2)], [], 1000.0, 10.0, 137.0)
    ca = [it for it in a if it[0] == pytest.approx(30000.0)][0]
    cb = [it for it in b if it[0] == pytest.approx(30000.0)][0]
    assert ca[1:] == pytest.approx(cb[1:])


def test_c5_worked_reactions():
    rx = L.outrigger_reactions(_c5_items(13600, 30), 3.5, 3.3)
    assert rx.lifted is None
    assert [tuple(c) for c in rx.corners] == [pytest.approx((3.5, 3.3)), pytest.approx((3.5, -3.3)),
                                             pytest.approx((-3.5, 3.3)), pytest.approx((-3.5, -3.3))]
    got = [t_of(r) for r in rx.reactions]
    assert got == pytest.approx([27.863, 19.590, 12.210, 3.937], abs=5e-4)
    assert sum(got) == pytest.approx(63.6, abs=1e-6)
    assert rx.x == pytest.approx(1.7228, abs=5e-5)
    assert rx.y == pytest.approx(0.8585, abs=5e-5)
    assert rx.P == pytest.approx(63600.0) or rx.P == pytest.approx(63600.0 * G)


def test_c5_moments_balance():
    items = _c5_items(13600, 30)
    rx = L.outrigger_reactions(items, 3.5, 3.3)
    pg = _mass_of(items) * G
    mx = sum(m * x for m, x, _ in items) * G
    my = sum(m * y for m, _, y in items) * G
    assert sum(rx.reactions) == pytest.approx(pg, rel=1e-9)
    assert sum(r * c[0] for r, c in zip(rx.reactions, rx.corners)) == pytest.approx(mx, rel=1e-9)
    assert sum(r * c[1] for r, c in zip(rx.reactions, rx.corners)) == pytest.approx(my, rel=1e-9)


def test_c5_lift_off_branch():
    items = _c5_items(26000, 45)
    rx = L.outrigger_reactions(items, 3.5, 3.3)
    assert rx.x == pytest.approx(2.5978, abs=5e-5)
    assert rx.y == pytest.approx(2.4004, abs=5e-5)
    assert rx.lifted == 3
    got = [t_of(r or 0.0) for r in rx.reactions]
    assert got[:3] == pytest.approx([55.846, 10.359, 9.795], abs=5e-4)
    assert got[3] == pytest.approx(0.0, abs=1e-9)
    pg = 76000.0 * G
    assert sum(r or 0.0 for r in rx.reactions) == pytest.approx(pg, rel=1e-9)
    mx = sum(m * x for m, x, _ in items) * G
    my = sum(m * y for m, _, y in items) * G
    assert sum((r or 0.0) * c[0] for r, c in zip(rx.reactions, rx.corners)) == pytest.approx(mx, rel=1e-9)
    assert sum((r or 0.0) * c[1] for r, c in zip(rx.reactions, rx.corners)) == pytest.approx(my, rel=1e-9)


@pytest.mark.parametrize("x, y, lifted", [(-3.0, -3.0, 0), (3.0, -3.0, 2), (-3.0, 3.0, 1), (3.0, 3.0, 3)])
def test_c5_which_corner_lifts(x, y, lifted):
    rx = L.outrigger_reactions([(10000.0, x, y)], 3.5, 3.3)
    assert rx.lifted == lifted
    assert all((r or 0.0) >= -1e-6 for r in rx.reactions)


def test_c5_tips():
    rx = L.outrigger_reactions([(10000.0, 0.0, 0.0), (50000.0, 10.0, 0.0)], 3.5, 3.3)
    assert rx.lifted == "tips"
    assert rx.reactions is None


def test_c5_centre_offset():
    a = L.outrigger_reactions(_c5_items(13600, 30), 3.5, 3.3)
    shifted = [(m, x + 2.0, y - 1.0) for m, x, y in _c5_items(13600, 30)]
    b = L.outrigger_reactions(shifted, 3.5, 3.3, centre=(2.0, -1.0))
    assert b.reactions == pytest.approx(a.reactions, rel=1e-9)
    assert tuple(b.corners[0]) == pytest.approx((5.5, 2.3))


def test_c5_mat_pressure_worked():
    r = L.outriggers(_c5_items(13600, 30), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3)
    assert r.check == "C5"
    assert kpa(r.value) == pytest.approx(121.4, abs=0.05)
    assert r.limit == pytest.approx(200e3)
    assert r.use * 100 == pytest.approx(60.7, abs=0.05)
    assert r.status == "ok" and r.amber_at == pytest.approx(0.90)
    assert t_of(max(r.details["reactions"])) == pytest.approx(27.863, abs=5e-4)
    assert max(r.details["reactions"]) / 1000 == pytest.approx(273.2, abs=0.05)   # kN


def test_c5_ground_limit():
    r = L.outriggers(_c5_items(13600, 30), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3, limits=L.Limits(ground=0.6))
    assert r.status == "amber"


def test_c5_lift_off_is_at_least_amber():
    r = L.outriggers(_c5_items(26000, 45), 3.5, 3.3, mat=(1.5, 1.5), allowable=10e6)
    assert r.use < 0.5
    assert r.status == "amber"
    assert r.details["lifted"] == 3
    assert any("unloaded" in n.lower() for n in r.notes)


def test_c5_tips_red():
    r = L.outriggers([(10000.0, 0.0, 0.0), (50000.0, 10.0, 0.0)], 3.5, 3.3, mat=(1.5, 1.5), allowable=10e6)
    assert r.status == "red"


def test_c5_no_mat_or_allowable_not_checked():
    for kw in ({}, {"mat": (1.5, 1.5)}, {"allowable": 200e3}):
        r = L.outriggers(_c5_items(13600, 30), 3.5, 3.3, **kw)
        assert r.status == "not_checked"
        assert t_of(max(r.details["reactions"])) == pytest.approx(27.863, abs=5e-4)


def test_c5_sweep_is_worst():
    one = L.outriggers(_c5_items(13600, 30), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3)
    sw = L.outriggers_sweep(CARRIER, UPPER, 13600, 12.0, 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3)
    assert sw.value >= one.value - 1e-6
    assert 0.0 <= sw.details["slew"] <= 360.0
    for slew in range(0, 360, 15):
        r = L.outriggers(_c5_items(13600, slew), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3)
        assert sw.value >= r.value - 1e-6 or r.status == "red"


def test_c5_sweep_unloaded_crane_worst():
    carrier = [(30000.0, 0.0, 0.0)]
    upper = [(8000.0, 0.0, 0.0), (40000.0, -4.0, 0.0)]
    sw = L.outriggers_sweep(carrier, upper, 5000.0, 30.0, 3.5, 3.3, mat=(1.5, 1.5), allowable=1e7)
    assert sw.details["loaded"] is False


def test_c5_sweep_unloaded_at_every_slew():
    # the unloaded crane, slewed so the counterweight points at a corner, is the worst case here
    carrier = [(30000.0, 0.0, 0.0)]
    upper = [(8000.0, 0.0, 0.0), (40000.0, -4.0, 0.0)]
    sw = L.outriggers_sweep(carrier, upper, 5000.0, 30.0, 3.5, 3.3, mat=(1.5, 1.5), allowable=1e7)
    best = 0.0
    for slew in range(0, 360):
        items = L.crane_items(carrier, upper, 0.0, 30.0, float(slew))
        r = L.outriggers(items, 3.5, 3.3, mat=(1.5, 1.5), allowable=1e7)
        best = max(best, r.value)
    assert sw.value == pytest.approx(best, rel=1e-9)


# ---------------------------------------------------------------------------------------------------------------
# C6 crawler tracks
# ---------------------------------------------------------------------------------------------------------------

def _t_per_m2(pa):
    return pa / G / 1000.0


def test_c6_trapezoid_worked():
    r = L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2)
    d = r.details
    assert r.check == "C6"
    assert t_of(d["share"][0]) == pytest.approx(195.0, abs=5e-4)
    assert t_of(d["share"][1]) == pytest.approx(105.0, abs=5e-4)
    assert _t_per_m2(d["p_max"][0]) == pytest.approx(38.594, abs=5e-4)
    assert kpa(d["p_max"][0]) == pytest.approx(378.5, abs=0.05)
    assert _t_per_m2(d["p_min"][0]) == pytest.approx(2.031, abs=5e-4)
    assert d["contact"][0] == pytest.approx(8.0)
    assert kpa(r.value) == pytest.approx(378.5, abs=0.05)
    assert r.status == "not_checked"


def test_c6_triangle_worked():
    r = L.tracks(300000, 1.6, 0.9, 6.0, 8.0, 1.2)
    d = r.details
    assert _t_per_m2(d["p_max"][0]) == pytest.approx(45.139, abs=5e-4)
    assert kpa(d["p_max"][0]) == pytest.approx(442.7, abs=0.05)
    assert d["contact"][0] == pytest.approx(7.20, abs=5e-3)
    assert d["p_min"][0] == pytest.approx(0.0, abs=1e-6)


def test_c6_second_track_and_sign():
    d = L.tracks(300000, -1.2, -0.9, 6.0, 8.0, 1.2).details
    assert t_of(d["share"][0]) == pytest.approx(105.0, abs=5e-4)
    assert t_of(d["share"][1]) == pytest.approx(195.0, abs=5e-4)
    assert _t_per_m2(d["p_max"][1]) == pytest.approx(38.594, abs=5e-4)
    assert sum(d["share"]) == pytest.approx(300000 * G, rel=1e-9)


def test_c6_pressure_integral_equals_share():
    for x in (0.0, 0.7, 1.2, 1.6, 3.0):
        d = L.tracks(300000, x, 0.9, 6.0, 8.0, 1.2).details
        for i in (0, 1):
            area = 0.5 * (d["p_max"][i] + d["p_min"][i]) * d["contact"][i] * 1.2
            assert area == pytest.approx(d["share"][i], rel=1e-9)


def test_c6_continuous_at_l_over_6():
    e = 8.0 / 6.0
    a = L.tracks(300000, e - 1e-9, 0.0, 6.0, 8.0, 1.2).details
    b = L.tracks(300000, e + 1e-9, 0.0, 6.0, 8.0, 1.2).details
    assert a["p_max"][0] == pytest.approx(b["p_max"][0], rel=1e-6)
    assert a["p_max"][0] == pytest.approx(2 * 150000 * G / (1.2 * 8.0), rel=1e-6)


def test_c6_centred_is_uniform():
    d = L.tracks(300000, 0.0, 0.0, 6.0, 8.0, 1.2).details
    p = 150000 * G / (1.2 * 8.0)
    assert d["p_max"][0] == pytest.approx(p) and d["p_min"][0] == pytest.approx(p)


def test_c6_status_with_allowable():
    r = L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2, allowable=500e3)
    assert r.use == pytest.approx(r.value / 500e3)
    assert r.status == "ok" and r.amber_at == pytest.approx(0.90)
    assert L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2, allowable=400e3).status == "amber"
    assert L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2, allowable=370e3).status == "red"


@pytest.mark.parametrize("x, y", [(0.0, 3.1), (0.0, -3.5), (4.0, 0.0), (-4.5, 0.0)])
def test_c6_outside_tracks_red(x, y):
    assert L.tracks(300000, x, y, 6.0, 8.0, 1.2, allowable=10e6).status == "red"
    assert L.tracks(300000, x, y, 6.0, 8.0, 1.2).status == "red"


# ---------------------------------------------------------------------------------------------------------------
# C7 forklift
# ---------------------------------------------------------------------------------------------------------------

def _info_numbers(details):
    out = []
    for v in details.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
    return out


def test_c7_worked_fork_rule():
    r = L.forklift(1900, 2500, 0.5, 0.7, 0.42)
    assert r.check == "C7"
    assert r.limit == pytest.approx(1785.7, abs=0.05)
    assert r.value == pytest.approx(1900.0)
    assert r.use * 100 == pytest.approx(106.4, abs=0.05)
    assert r.status == "red"
    assert r.amber_at == pytest.approx(0.75)


def test_c7_moment_rule_for_information():
    r = L.forklift(1900, 2500, 0.5, 0.7, 0.42)
    nums = _info_numbers(r.details)
    assert any(abs(n - 2053.6) < 0.05 for n in nums)
    assert r.limit != pytest.approx(2053.6, abs=1.0)


def test_c7_shorter_centre_no_rise():
    r = L.forklift(1000, 2500, 0.5, 0.4, 0.42)
    assert r.limit == pytest.approx(2500.0)


@pytest.mark.parametrize("load, status", [(1300.0, "ok"), (1400.0, "amber"), (1785.0, "amber")])
def test_c7_statuses(load, status):
    assert L.forklift(load, 2500, 0.5, 0.7, 0.42).status == status


TABLE = [(0.5, 3.0, 2500.0), (0.6, 3.0, 2200.0), (0.7, 3.0, 1900.0), (0.7, 5.0, 1600.0), (0.9, 3.0, 1500.0)]


@pytest.mark.parametrize("centre, height, cap", [
    (0.65, 2.5, 1900.0),
    (0.65, 4.0, 1600.0),
    (0.65, None, 1900.0),
    (0.5, 3.0, 2500.0),
    (0.55, 3.0, 2200.0),
    (0.8, 1.0, 1500.0),
])
def test_c7_table(centre, height, cap):
    r = L.forklift(1000, 2500, 0.5, centre, 0.42, table=TABLE, lift_height=height)
    assert r.limit == pytest.approx(cap)


@pytest.mark.parametrize("centre, height", [(1.0, None), (0.75, 4.0), (0.5, 6.0)])
def test_c7_table_no_row_red(centre, height):
    r = L.forklift(1000, 2500, 0.5, centre, 0.42, table=TABLE, lift_height=height)
    assert r.status == "red"


# ---------------------------------------------------------------------------------------------------------------
# C8 offshore DAF
# ---------------------------------------------------------------------------------------------------------------

def test_c8_table():
    t = L.DAF_DNV_OS_H205_2014
    assert len(t) == 5
    want = [(100000, 1.10, 1.15, 1.30), (300000, 1.05, 1.12, 1.25), (1000000, 1.05, 1.10, 1.20),
            (2500000, 1.03, 1.08, 1.15), (None, 1.03, 1.05, 1.10)]
    for got, w in zip(t, want):
        if w[0] is None:
            assert got[0] is None
        else:
            assert got[0] == pytest.approx(w[0])
        assert tuple(got[1:]) == pytest.approx(w[1:])


def test_c8_note():
    assert L.DAF_NOTE == "Preset from DNV-OS-H205 (2014) – check against the current DNV-ST-N001"


def test_c8_static_hook_load():
    assert L.static_hook_load(370000, rigging=5000, tool=25000) == pytest.approx(400000.0)
    assert L.static_hook_load(100000, rigging=1000, tool=0, contingency=1.1) == pytest.approx(111000.0)
    assert L.static_hook_load(500) == pytest.approx(500.0)


@pytest.mark.parametrize("shl, site, daf", [
    (50000, "onshore", 1.10), (50000, "inshore", 1.15), (50000, "offshore", 1.30),
    (100000, "onshore", 1.10), (100000, "offshore", 1.30),     # 100 t inclusive in the first band
    (100001, "offshore", 1.25),
    (300000, "inshore", 1.12), (300001, "inshore", 1.10),
    (400000, "offshore", 1.20),
    (1000000, "offshore", 1.20), (1000001, "offshore", 1.15),
    (2500000, "inshore", 1.08), (2500001, "inshore", 1.05),
    (9000000, "onshore", 1.03), (9000000, "offshore", 1.10),
])
def test_c8_daf_for(shl, site, daf):
    assert L.daf_for(shl, site) == pytest.approx(daf)


def test_c8_daf_for_bad_site():
    with pytest.raises(ValueError):
        L.daf_for(100000, "subsea")
    with pytest.raises(ValueError):
        L.dynamic_load(100000, "Offshore ")


def test_c8_daf_for_own_table():
    table = [(1000.0, 2.0, 3.0, 4.0), (None, 1.5, 1.6, 1.7)]
    assert L.daf_for(500, "inshore", table=table) == pytest.approx(3.0)
    assert L.daf_for(5000, "offshore", table=table) == pytest.approx(1.7)


def test_c8_worked_case():
    shl = L.static_hook_load(370000, rigging=5000, tool=25000)
    r = L.dynamic_load(shl, "offshore", chart_capacity=600000)
    assert r.check == "C8"
    assert r.details["shl"] == pytest.approx(400000.0)
    assert r.details["daf"] == pytest.approx(1.20)
    assert r.details["dhl"] == pytest.approx(480000.0)
    assert r.use * 100 == pytest.approx(80.0, abs=0.05)
    assert r.status == "amber" and r.amber_at == pytest.approx(0.75)


def test_c8_daf_override():
    r = L.dynamic_load(400000, "offshore", chart_capacity=600000, daf=1.4)
    assert r.details["dhl"] == pytest.approx(560000.0)


def test_c8_hs_rated():
    r = L.dynamic_load(400000, "offshore", chart_capacity=600000, hs_rated=True)
    assert r.use is None
    assert r.status == "not_checked"
    assert r.notes
    assert r.details["dhl"] == pytest.approx(480000.0)


def test_c8_no_chart():
    r = L.dynamic_load(400000, "offshore")
    assert r.use is None and r.status == "not_checked"
    assert r.details["dhl"] == pytest.approx(480000.0)


# ---------------------------------------------------------------------------------------------------------------
# C9 upending
# ---------------------------------------------------------------------------------------------------------------

PILE = [(2000000.0, 45.0)]


@pytest.mark.parametrize("angle", [0.0, 15.0, 30.0, 60.0, 85.0, 89.9])
def test_c9_vertical_rope_900t_every_angle(angle):
    r = L.upending(PILE, 100.0, angle)
    assert r.check == "C9"
    assert t_of(r.details["hook"]) == pytest.approx(900.0, abs=0.05)
    assert t_of(r.details["hinge"]) == pytest.approx(1100.0, abs=0.05)
    assert t_of(r.value) == pytest.approx(900.0, abs=0.05)
    assert r.status == "not_checked"


def test_c9_with_tool():
    r = L.upending(PILE + [(60000.0, 100.0)], 100.0, 40.0)
    assert t_of(r.details["hook"]) == pytest.approx(960.0, abs=0.05)
    assert t_of(r.details["hinge"]) == pytest.approx(1100.0, abs=0.05)


def test_c9_at_vertical_hook_takes_all():
    r = L.upending(PILE + [(60000.0, 100.0)], 100.0, 90.0)
    assert t_of(r.details["hook"]) == pytest.approx(2060.0, abs=0.05)
    assert r.notes


def test_c9_off_hinge():
    r = L.upending(PILE + [(60000.0, 100.0)], 100.0, 30.0, off_hinge=True)
    assert t_of(r.details["hook"]) == pytest.approx(2060.0, abs=0.05)
    assert t_of(r.details["hinge"]) == pytest.approx(0.0, abs=0.05)


def test_c9_hinge_vector_vertical_rope():
    r = L.upending(PILE, 100.0, 30.0)
    h, up = r.details["hinge_vector"]
    assert t_of(h) == pytest.approx(0.0, abs=1e-6)
    assert t_of(up) == pytest.approx(1100.0, abs=0.05)


def test_c9_tilted_rope_uses_degrees():
    # rope leaning back towards the hinge: (horizontal, up) = (-0.6, 0.8)
    th = math.radians(30.0)
    f = 2000000 * G * 45 * math.cos(th) / (100 * (math.cos(th) * 0.8 + math.sin(th) * 0.6))
    r = L.upending(PILE, 100.0, 30.0, rope=(-0.6, 0.8))
    assert r.details["hook"] == pytest.approx(f, rel=1e-6)
    assert t_of(f) == pytest.approx(785.06, abs=0.01)
    hx, hu = -f * -0.6, 2000000 * G - f * 0.8
    assert r.details["hinge"] == pytest.approx(math.hypot(hx, hu), rel=1e-6)
    vec = r.details["hinge_vector"]
    assert abs(vec[0]) == pytest.approx(abs(hx), rel=1e-6)
    assert abs(vec[1]) == pytest.approx(abs(hu), rel=1e-6)


def test_c9_force_balance_general():
    items = [(500000.0, 20.0), (80000.0, 60.0)]
    r = L.upending(items, 60.0, 50.0, rope=(0.28, 0.96))
    w = sum(m for m, _ in items) * G
    f = r.details["hook"]
    hv = r.details["hinge_vector"]
    # hinge + rope pull balance the weight (allow either sign convention of the hinge vector)
    plus = (hv[0] + f * 0.28, hv[1] + f * 0.96 - w)
    minus = (-hv[0] + f * 0.28, -hv[1] + f * 0.96 - w)
    assert min(math.hypot(*plus), math.hypot(*minus)) == pytest.approx(0.0, abs=w * 1e-9)
    th = math.radians(50.0)
    moment = sum(m * G * s * math.cos(th) for m, s in items)
    assert f * 60.0 * (math.cos(th) * 0.96 - math.sin(th) * 0.28) == pytest.approx(moment, rel=1e-9)


def test_c9_capacity():
    r = L.upending(PILE, 100.0, 30.0, capacity=1000000)
    assert r.use * 100 == pytest.approx(90.0, abs=0.05)
    assert r.status == "amber" and r.amber_at == pytest.approx(0.75)
    assert L.upending(PILE, 100.0, 30.0, capacity=2000000).status == "ok"
    assert L.upending(PILE, 100.0, 30.0, capacity=800000).status == "red"


# ---------------------------------------------------------------------------------------------------------------
# Limits go to the right check
# ---------------------------------------------------------------------------------------------------------------

def test_amber_at_follows_the_right_limit():
    lim = L.Limits(crane=0.61, rigging=0.62, ground=0.63)
    ch = L.Chart(radius=[10.0], capacity=[20000.0])
    assert L.crane_use(5000, 10.0, ch, limits=lim).amber_at == pytest.approx(0.61)
    assert L.forklift(1000, 2500, 0.5, 0.5, 0.42, limits=lim).amber_at == pytest.approx(0.61)
    assert L.dynamic_load(1000, "onshore", chart_capacity=5000, limits=lim).amber_at == pytest.approx(0.61)
    assert L.upending(PILE, 100.0, 30.0, capacity=2000000, limits=lim).amber_at == pytest.approx(0.61)
    assert L.wll_use(1000.0, 1000, limits=lim).amber_at == pytest.approx(0.62)
    c2 = L.two_leg(10000, (0, 0, 0), (4, 0, 0), (1.5, 0, 3), leg_wll=8000, limits=lim)
    assert all(p.amber_at == pytest.approx(0.62) for p in c2.parts)
    assert L.outriggers(_c5_items(13600, 30), 3.5, 3.3, mat=(1.5, 1.5), allowable=200e3,
                        limits=lim).amber_at == pytest.approx(0.63)
    assert L.tracks(300000, 1.2, 0.9, 6.0, 8.0, 1.2, allowable=500e3, limits=lim).amber_at == pytest.approx(0.63)
