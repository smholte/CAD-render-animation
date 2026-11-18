"""The function list (task 0124): fresing_render/core/functions.py and the precheck's check of it."""

from __future__ import annotations

import dataclasses
import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from fresing_render.core import functions as F  # noqa: E402


@pytest.fixture(scope="module")
def repo():
    return F.read_repo(ROOT)


def test_the_real_list_has_no_problems(repo):
    assert F.problems(**repo) == []


def test_the_list_is_read_from_the_repository(repo):
    assert len(F.FUNCTIONS) >= 90
    assert len(repo["stops"]) >= 60 and "joint" in repo["stops"]
    assert len(repo["lines"]) >= 80 and "joints.rotate" in repo["lines"]
    assert "own.import" not in repo["lines"]                      # a Quick-only line is not Full
    assert "FRESING_PT_motion" in repo["panels"] and "fr_product_video" in repo["folds"]
    assert "fresing.joint_pick_axis" in repo["operators"] and "background" in repo["props"]


def test_every_family_is_used_and_every_entry_is_complete():
    used = {f.family for f in F.FUNCTIONS.values()}
    assert used == set(F.FAMILIES)
    for f in F.FUNCTIONS.values():
        assert f.title and f.guide and f.since and (f.button or f.prop), f.id


def _with(**kw):
    """The real list with one made-up entry (or one entry changed)."""
    base = F.Function(id="test.thing", title="A thing", family="motion", panel="FRESING_PT_motion",
                      button="fresing.joint_add", guide="motion", since="0.2.99")
    funcs = dict(F.FUNCTIONS)
    f = dataclasses.replace(base, **kw)
    funcs[f.id] = f
    return funcs


@pytest.mark.parametrize("kw, words", [
    (dict(guide=""), "no guide anchor"),
    (dict(guide="nowhere"), "the guide has no anchor 'nowhere'"),
    (dict(family="boats"), "family 'boats' is not one of"),
    (dict(panel="FRESING_PT_nope"), "unknown panel 'FRESING_PT_nope'"),
    (dict(fold="fr_nope"), "unknown fold 'fr_nope'"),
    (dict(button="fresing.nope"), "unknown button 'fresing.nope'"),
    (dict(button="", prop=""), "no button or setting"),
    (dict(button="", prop="nope_prop"), "unknown setting 'nope_prop'"),
    (dict(text="No such button text"), "button text 'No such button text' is not in the app's code"),
    (dict(tour=("nope",)), "no tour stop 'nope'"),
    (dict(pccheck=("nope.line",)), "no PC-check Full line 'nope.line'"),
    (dict(pccheck=("own.import",)), "no PC-check Full line 'own.import'"),
    (dict(id="Test.Thing"), "an id is area.name"),
    (dict(since="soon"), "since 'soon' is not a version"),
    (dict(since=""), "no since= version"),                          # task 0199: a new entry without since= fails
    (dict(changed="later"), "changed 'later' is not a version"),
])
def test_a_broken_entry_is_caught(repo, kw, words):
    found = F.problems(_with(**kw), **repo)
    assert len(found) >= 1 and any(words in p for p in found), found


def test_a_lesson_step_that_does_not_exist_is_caught(repo):
    assert F.problems(_with(lesson="crane:3"), **repo, lessons={"crane": 11}) == []
    found = F.problems(_with(lesson="crane:12"), **repo, lessons={"crane": 11})
    assert any("lesson step 'crane:12' does not exist" in p for p in found)


def test_a_stop_line_or_section_nobody_names_is_caught(repo):
    funcs = {k: v for k, v in F.FUNCTIONS.items() if k != "machines.tracks"}
    found = F.problems(funcs, **repo)
    assert any("tour stop 'tracks' is named by no entry" in p for p in found)
    assert any("PC-check line 'motion.tracks' is named by no entry" in p for p in found)
    assert any("guide section 'tracks' is named by no entry" in p for p in found)
    repo2 = dict(repo, anchors=repo["anchors"] + ["new-section"])
    assert any("guide section 'new-section'" in p for p in F.problems(**repo2))


def test_a_duplicate_id_or_anchor_is_caught(repo):
    one = F.FUNCTIONS["joints.rotate"]
    found = F.problems(list(F.FUNCTIONS.values()) + [one], **repo)
    assert any("joints.rotate: two entries have this id" in p for p in found)
    assert any("two entries" in p for p in F.problems(**repo, duplicates=["x.y"]))
    found = F.problems(**dict(repo, anchors=repo["anchors"] + ["motion"]))
    assert any("the anchor 'motion' twice" in p for p in found)


def test_the_precheck_fails_with_the_sentences(monkeypatch):
    import ci_precheck
    assert ci_precheck.check_functions() == []
    broken = dict(F.FUNCTIONS)
    broken["test.thing"] = dataclasses.replace(F.FUNCTIONS["joints.rotate"], id="test.thing", guide="nowhere")
    monkeypatch.setattr(F, "FUNCTIONS", broken)
    found = ci_precheck.check_functions()
    assert found and all(p.startswith("function list: ") for p in found)
    assert any("test.thing: the guide has no anchor 'nowhere'" in p for p in found)


def test_guide_link():
    assert F.guide_link("joints.rotate") == "guide/#motion"
    assert F.guide_link("looks.xray", base="../../guide/") == "../../guide/#xray"


def test_every_guide_heading_has_an_anchor():
    text = open(os.path.join(ROOT, "docs", "USER-GUIDE.md"), encoding="utf-8").read()
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"#{2,4} ", line):
            assert re.match(r'<a id="[a-z0-9-]+"></a>$', lines[i - 1]), f"no anchor above '{line}'"
    anchors = F.guide_anchors(text)
    assert len(anchors) == len(set(anchors))


def test_anchors_in_the_notes_for_the_chats_do_not_count():
    assert F.guide_anchors('<!-- <a id="x"></a> -->\n<a id="y"></a>\n## Y') == ["y"]
