"""Learn as you go (task 0208): the learning list and the quiet 'next to learn' (no Blender)."""

import ast
import json
import os

import pytest

from fresing_render.core import functions as F
from fresing_render.core import learning as L
from fresing_render.core import usage as U

ALL = set(F.FUNCTIONS)


def _state(sessions=10):
    s = U.fresh()
    s["sessions"] = sessions
    return s


def _use(s, fid, days):
    for d in days:
        U.count_click(s, "x", fid, today=d)


def test_every_unused_panel_the_question_asks_about_can_be_taught_or_just_hidden():
    s = _state()
    n = 0
    for f in F.FUNCTIONS.values():
        t = L.target_of_panel(f.panel)
        if t:
            n += 1
            assert F.FUNCTIONS[t].panel == f.panel and L.teachable(t)
    assert n > 30


def test_menu_lines_and_panel_switches_are_never_taught():
    assert not L.teachable("usage.favourites")
    assert not L.teachable("no.such.function")
    assert L.target_of_panel("FRESING_PT_does_not_exist") == ""


def test_options_name_the_guide_and_the_tour_and_say_why_a_tour_button_is_grey():
    with_tour = next(f for f in F.FUNCTIONS.values() if f.tour and f.guide and L.teachable(f.id))
    o = L.options(with_tour.id)
    assert o["guide"] == with_tour.guide and o["tour"] == with_tour.tour[0] and not o["why_no_tour"]
    no_tour = next(f for f in F.FUNCTIONS.values() if not f.tour and f.guide and L.teachable(f.id))
    o = L.options(no_tour.id)
    assert o["tour"] == "" and "Learning hub" in o["why_no_tour"]


def test_the_question_choices_learn_hide_later_never():
    s = _state()
    panel = F.FUNCTIONS["scene.turntable"].panel
    fid = L.target_of_panel(panel)
    U.answer_declutter(s, panel, "learn")
    assert L.find(s, fid) is not None and s["hidden"] == [] and panel in s["declutter"]["asked"]
    s2 = _state()
    U.answer_declutter(s2, panel, "hide")
    assert s2["hidden"] and L.find(s2, fid) is None
    s3 = _state()
    U.answer_declutter(s3, panel, "never")
    assert not s3["declutter"]["on"] and not s3["learning"]["teach"]


def test_the_question_still_comes_when_only_teaching_is_on_and_not_when_both_are_off():
    s = _state()
    s["declutter"]["on"] = False
    assert U.declutter_candidate(s, ALL, set())            # teaching alone is enough
    s["learning"]["teach"] = False
    assert U.declutter_candidate(s, ALL, set()) == ""


def test_a_function_on_the_list_is_ticked_by_itself_after_n_different_days_and_told_once():
    s = _state()
    fid = "scene.turntable"
    assert L.add(s, fid) and not L.add(s, fid)
    assert _use(s, fid, ["2026-11-01", "2026-11-01", "2026-11-01"]) is None
    assert not L.find(s, fid)["done"]                      # three clicks, one day
    got = []
    for d in ("2026-11-02", "2026-11-03"):
        got += U.count_click(s, "x", fid, today=d)
    assert got == [fid] and L.find(s, fid)["done"] and L.find(s, fid)["auto"]
    assert L.take_told(s) == [fid] and L.take_told(s) == []
    assert "hang of" in L.say_learned(fid)


def test_days_needed_is_a_setting_and_a_used_function_added_later_counts_its_days():
    s = _state()
    s["learning"]["need_days"] = 2
    _use(s, "scene.turntable", ["2026-11-01", "2026-11-02"])
    assert L.add(s, "scene.turntable")
    assert L.find(s, "scene.turntable")["done"]            # already used on 2 days


def test_done_by_hand_and_remove():
    s = _state()
    L.add(s, "scene.turntable")
    L.set_done(s, "scene.turntable")
    assert L.open_items(s) == []
    L.set_done(s, "scene.turntable", False)
    assert L.open_items(s) == ["scene.turntable"]
    assert L.remove(s, "scene.turntable") and not L.remove(s, "scene.turntable")


def test_new_since_lists_only_teachable_functions_that_came_after():
    ids = L.new_since("0.2.100")
    assert ids and all(L.teachable(i) for i in ids)
    assert all(F.FUNCTIONS[i].since != "0.1.0" for i in ids)
    assert L.new_since("99.0.0") == []


def _worker(s):
    for _ in range(3):
        U.count_click(s, "fresing.turntable", "scene.turntable", today="2026-11-01")
    return s


def test_next_to_learn_picks_in_a_family_the_user_works_in_in_the_list_order():
    s = _worker(_state())
    got = L.candidates(s, ALL, set())
    assert got and all(fam == "scene" for _f, fam in got[:1])
    fid = got[0][0]
    f = F.FUNCTIONS[fid]
    assert f.family == "scene" and not s["functions"].get(fid)


def test_next_to_learn_never_offers_hidden_turned_down_listed_used_or_not_shown_things():
    s = _worker(_state())
    first = L.candidates(s, ALL, set())[0][0]
    # not shown in the workspace (Full access only)
    assert first not in [c[0] for c in L.candidates(s, ALL - {first}, set())]
    # used by the open project
    assert first not in [c[0] for c in L.candidates(s, ALL, {first})]
    # hidden by the user
    s["hidden"].append(first)
    assert first not in [c[0] for c in L.candidates(s, ALL, set())]
    s["hidden"].clear()
    # on the list already
    L.add(s, first)
    assert first not in [c[0] for c in L.candidates(s, ALL, set())]
    L.remove(s, first)
    # turned down
    L.decline(s, first)
    assert first not in [c[0] for c in L.candidates(s, ALL, set())]
    # a hidden panel
    second = L.candidates(s, ALL, set())[0][0]
    assert second not in [c[0] for c in L.candidates(s, ALL, set(), hidden_panels={F.FUNCTIONS[second].panel})]


def test_a_user_with_no_use_gets_no_suggestion():
    s = _state()
    assert L.candidates(s, ALL, set()) == []
    assert L.choose_next(s, ALL, set()) == ""


def test_one_suggestion_a_session_and_it_stays_until_answered():
    s = _worker(_state(sessions=4))
    a = L.choose_next(s, ALL, set())
    assert a and L.choose_next(s, ALL, set()) == a          # the same one again in this session
    L.answer_next(s, a, "no")
    assert L.choose_next(s, ALL, set()) == ""               # answered: no second one in this session
    s["sessions"] = 5
    b = L.choose_next(s, ALL, set())
    assert b and b != a                                     # next session: another one, never the turned-down


def test_learn_answer_puts_it_on_the_list_and_off_the_card():
    s = _worker(_state())
    a = L.choose_next(s, ALL, set())
    L.answer_next(s, a, "learn")
    assert L.find(s, a) is not None and s["learning"]["next"]["id"] == ""


def test_the_suggestion_can_be_switched_off_and_tracking_off_gives_none():
    s = _worker(_state())
    s["learning"]["next_on"] = False
    assert L.choose_next(s, ALL, set()) == ""
    s["learning"]["next_on"] = True
    s["track"] = False
    assert L.choose_next(s, ALL, set()) == ""


def test_the_file_round_trip_and_an_older_file_without_learning(tmp_path):
    p = str(tmp_path / "Ünï" / U.FILE_NAME)
    s = _worker(_state())
    L.add(s, "scene.turntable")
    U.save(p, s)
    back, note = U.load(p)
    assert not note and back["learning"]["list"][0]["id"] == "scene.turntable"
    assert back["learning"]["days"]["scene.turntable"] == ["2026-11-01"]
    old = {k: v for k, v in U.fresh().items() if k != "learning"}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(old, fh)
    back, note = U.load(p)
    assert not note and back["learning"] == L.fresh()


def test_wrong_types_in_a_hand_edited_learning_part_become_defaults():
    got = L.clean({"list": [1, {"id": 5}, {"id": "a.b", "added": "x"}, {"id": "a.b"}], "days": {"a.b": "no", "c": [1, "2026-11-02"]},
                   "declined": "x", "need_days": 0, "next": [], "teach": 0})
    assert [i["id"] for i in got["list"]] == ["a.b"] and got["need_days"] == 1 and got["days"] == {"c": ["2026-11-02"]}
    assert got["teach"] is False and got["next"] == {"session": 0, "id": ""}
    assert L.clean("junk") == L.fresh() and L.clean(None) == L.fresh()


def test_days_are_dates_only_and_capped():
    s = _state()
    _use(s, "scene.turntable", [f"2026-10-{d:02d}" for d in range(1, 29)] + [f"2026-11-{d:02d}" for d in range(1, 10)])
    days = s["learning"]["days"]["scene.turntable"]
    assert len(days) == L.DAYS_KEPT and all(len(d) == 10 for d in days) and days == sorted(days)


def test_clear_keeps_the_list_unless_asked():
    s = _worker(_state())
    L.add(s, "scene.still")
    s["learning"]["need_days"] = 5
    kept = U.clear(s)
    assert L.find(kept, "scene.still") is not None and kept["learning"]["days"] == {} and kept["learning"]["need_days"] == 5
    gone = U.clear(s, with_list=True)
    assert gone["learning"]["list"] == [] and gone["learning"]["need_days"] == 5


def test_a_profile_has_the_list_only_with_the_counts(tmp_path):
    s = _worker(_state())
    L.add(s, "scene.still")
    assert "usage" not in U.profile_part(s)
    full = U.profile_part(s, with_counts=True)
    assert full["usage"]["learning"]["list"][0]["id"] == "scene.still"
    mine = _state()
    U.take_profile(mine, json.loads(json.dumps(full)), with_counts=True)
    assert L.find(mine, "scene.still") is not None
    other = _state()
    U.take_profile(other, json.loads(json.dumps(full)), with_counts=False)
    assert L.find(other, "scene.still") is None


@pytest.mark.parametrize("rel", ["fresing_render/core/learning.py", "fresing_render/blender/learning.py",
                                 "fresing_render/blender/ops_learning.py"])
def test_learning_imports_no_network_library(rel):
    here = os.path.dirname(os.path.dirname(__file__))
    tree = ast.parse(open(os.path.join(here, rel), encoding="utf-8").read())
    banned = {"urllib", "http", "socket", "requests", "ftplib", "smtplib", "ssl", "webbrowser"}
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
        for n in names:
            assert n.split(".")[0] not in banned, f"{rel} imports {n}"
