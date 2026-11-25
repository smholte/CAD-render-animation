"""Task 0352: the compatibility kit's plain rules (core/compat.py) – no Blender."""

import os

import pytest

from fresing_render.core import compat as C
from fresing_render.core import functions


def steps(*pairs):
    return tuple(C.Step(a, b, f"s{a}", f"mod:step{a}") for a, b in pairs)


def test_the_shipped_chain_is_sound():
    assert isinstance(C.FORMAT, int) and C.FORMAT >= 1
    assert C.BASELINE_FORMAT is None or 1 <= C.BASELINE_FORMAT <= C.FORMAT
    assert C.chain_problems() == []
    assert C.STEPS == ()                         # empty until the first change after the baseline


def test_chain_problems_find_every_fault():
    assert C.chain_problems(steps((1, 2), (2, 3)), 3, 1) == []
    assert any("one step raises" in p for p in C.chain_problems(steps((1, 3)), 3, None, check_baseline=False))
    assert any("two steps start" in p for p in C.chain_problems(steps((1, 2), (1, 2)), 3, None, check_baseline=False))
    assert any("out of order" in p for p in C.chain_problems(steps((2, 3), (1, 2)), 3, None, check_baseline=False))
    assert any("above FORMAT" in p for p in C.chain_problems(steps((3, 4)), 3, None, check_baseline=False))
    gap = C.chain_problems(steps((1, 2)), 3, 1)
    assert any("no upgrade step from format 2" in p for p in gap)
    raised = C.chain_problems((), 2, 1)          # FORMAT raised from the baseline without its step
    assert raised and "from format 1 to 2" in raised[0]
    assert C.chain_problems((), 0, None, check_baseline=False)
    assert C.chain_problems((), 3, 4)            # a baseline above FORMAT
    bad = (C.Step(1, 2, "x", "nofunction"),)
    assert any("module:function" in p for p in C.chain_problems(bad, 2, 1))


def test_plan_runs_nothing_before_the_baseline_or_without_a_stamp():
    chain = steps((2, 3), (3, 4), (4, 5))
    assert C.plan(None, chain, 5, 2) == []                  # no stamp: made before the kit
    assert C.plan(3, chain, 5, None, use_baseline=False) == []   # no baseline yet
    assert C.plan(1, chain, 5, 2) == []                     # below the baseline: the per-lane code still runs
    assert C.plan(5, chain, 5, 2) == []                     # current
    assert C.plan(6, chain, 5, 2) == []                     # newer: never touched
    assert C.plan(True, chain, 5, 2) == []                  # a bool is no format number
    assert [s.name for s in C.plan(3, chain, 5, 2)] == ["s3", "s4"]
    assert [s.name for s in C.plan(2, tuple(reversed(chain)), 5, 2)] == ["s2", "s3", "s4"]   # always in order
    assert C.plan(3) == []                                  # the shipped chain: nothing


def test_run_keeps_the_order_and_stops_at_a_failing_step():
    calls, said = [], []

    def call(step):
        calls.append(step.name)
        if step.name == "s3":
            raise ValueError("broken")
    done, failed = C.run(steps((2, 3), (3, 4), (4, 5)), call, said.append)
    assert calls == ["s2", "s3"]                     # s4 builds on s3: it waits for a fixed version
    assert done == ["s2"] and failed == ["s3"]
    assert len(said) == 1 and "'s3'" in said[0] and "broken" in said[0] and "3 → 4" in said[0]
    assert "1 step(s) after it wait" in said[0]


def test_reading_stamps():
    assert C.as_format(3) == 3 and C.as_format(3.0) == 3 and C.as_format("4") == 4
    for bad in (None, True, 0, -1, 2.5, "x", "", [], {}):
        assert C.as_format(bad) is None
    assert C.file_format([None, 2, "x", 5, 3]) == 5
    assert C.file_format([None, "nope"]) is None
    assert C.is_newer(C.FORMAT + 1) and not C.is_newer(C.FORMAT) and not C.is_newer(None)


def test_the_newer_note_is_plain():
    text = C.newer_note("0.3.4", "0.2.261")
    assert text == ("Saved by Fresing Render 0.3.4, newer than this one (0.2.261). Update the app to work on it – "
                    "Fresing > Check for updates. Saving is off so nothing in it is lost.")
    assert "newer version" in C.newer_note("", "0.2.261")


def test_aside_name_never_takes_a_name_in_use(tmp_path):
    p = str(tmp_path / "Crane é.blend")
    first = C.aside_name(p, "0.3.4")
    assert first.endswith("Crane é (Fresing Render 0.3.4).blend")
    taken = {first}
    second = C.aside_name(p, "0.3.4", exists=lambda q: q in taken)
    assert second.endswith("Crane é (Fresing Render 0.3.4) (2).blend")
    odd = C.aside_name(p, 'a/b:"c')
    assert os.path.dirname(odd) == str(tmp_path) and os.path.basename(odd) == "Crane é (Fresing Render abc).blend"


def test_same_path(tmp_path):
    a = tmp_path / "a.blend"
    a.write_bytes(b"x")
    assert C.same_path(str(a), str(tmp_path / "." / "a.blend"))
    assert not C.same_path(str(a), str(tmp_path / "b.blend"))
    assert not C.same_path("", str(a))


def test_compare():
    old = {"a": 1, "b": [1.0, {"c": "x"}], "d": {"e": 0.1}}
    assert C.compare(old, {"a": 1, "b": [1.0000001, {"c": "x"}], "d": {"e": 0.1, "new": 5}, "more": 1}) == []
    diff = C.compare(old, {"a": 2, "b": [1.0], "d": {}})
    assert "a: 1 -> 2" in diff and "b: 2 items, now 1" in diff and "d.e: gone" in diff
    assert C.compare(old, {"a": 1, "b": [1.0, {"c": "y"}], "d": {"e": 0.1}}) == ["b[1].c: 'x' -> 'y'"]
    assert C.compare(old, {"a": 1, "b": [1.0, {"c": "y"}], "d": {}}, allowed=("b", "d.e")) == []
    assert C.compare({"x": 1.0}, {"x": 1.1}) == ["x: 1.0 -> 1.1"]
    assert C.compare({"x": {"y": 1}}, {"x": 3})


def test_round_value():
    assert C.round_value(0.1 + 0.2) == 0.3
    assert C.round_value([1.23456789, {"a": 2}]) == [1.23457, {"a": 2}]
    assert C.round_value(float("nan")) == "nan"


def test_picture_difference():
    import numpy as np
    a = np.zeros((4, 4, 3))
    assert C.picture_difference(a, a) == 0.0
    assert C.picture_difference(a, a + 0.5) == pytest.approx(0.5)
    assert C.picture_difference(a, np.zeros((2, 2, 3))) == 1.0


def test_every_family_is_sorted_into_stores_data_or_not():
    assert C.family_problems(functions.FAMILIES, functions.FAMILIES) == []
    more = dict(functions.FAMILIES, newfam="New family")
    assert any("'newfam' is not in core/compat.py FAMILY_DATA" in p for p in C.family_problems(more, more))
    missing = C.family_problems(functions.FAMILIES, set(functions.FAMILIES) - {"cnc"})
    assert len(missing) == 1 and "'cnc'" in missing[0]
    assert C.family_problems(functions.FAMILIES, set(functions.FAMILIES) - {"help"}) == []   # stores nothing


def test_the_precheck_wants_the_test_project_and_the_step_from_the_baseline_on(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import ci_precheck
    assert ci_precheck.check_compat() == []                     # as shipped
    monkeypatch.setattr(C, "BASELINE_FORMAT", 1)
    monkeypatch.setattr(C, "FORMAT", 2)
    found = ci_precheck.check_compat(str(tmp_path))
    assert any("no upgrade step from format 1 to 2" in p for p in found)
    assert any("format_1/summary.json is missing" in p for p in found)
    assert any("format_2/summary.json is missing" in p for p in found)
    for n in (1, 2):
        d = tmp_path / "tests" / "data" / "compat" / f"format_{n}"
        d.mkdir(parents=True)
        (d / "summary.json").write_text('{"format": %d, "projects": {"crane": {}}}' % n)
        (d / "crane.blend").write_bytes(b"BLENDER")
    monkeypatch.setattr(C, "STEPS", (C.Step(1, 2, "one", "m:f"),))
    assert ci_precheck.check_compat(str(tmp_path)) == []
