"""The usage tracker's rules (task 0181, core/usage.py; no Blender): counting, the bar sorted at start only, pins, the
declutter question's rules, the file (broken, newer, round trip), time saved as an estimate, profiles, no network."""

import ast
import json
import os

import pytest

from fresing_render.core import functions as F
from fresing_render.core import places
from fresing_render.core import usage as U
from fresing_render.core import workspaces as W

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLES = set(places.PLACES)


def _state(**kw):
    s = U.fresh()
    s.update(kw)
    return s


def _click(s, op, panel="", props=None, n=1):
    for _ in range(n):
        U.count_click(s, op, U.function_for(op, panel, props))


# ---------------------------------------------------------------------------
# counting
# ---------------------------------------------------------------------------

def test_one_click_counts_for_one_function_picked_by_kind_then_panel():
    assert U.function_for("fresing.block_add", props={"kind": "GCODE"}) == "cnc.gcode"
    assert U.function_for("fresing.block_add", props={"kind": "FADE_IN"}) == "animation.fade"
    assert U.function_for("fresing.queue_add", props={"kind": "TEST"}) == "queue.time_test"
    assert U.function_for("fresing.import_step", "FRESING_PT_import") == "import.step"
    assert U.function_for("fresing.apply_rules") == "looks.materials"           # the section's main button
    assert U.function_for("fresing.no_such_button") == ""
    s = U.fresh()
    _click(s, "fresing.block_add", props={"kind": "MOTOR"}, n=3)
    assert s["functions"] == {"animation.motor": [3, 0]} and s["buttons"] == {"fresing.block_add": 3}


def test_every_rule_names_real_functions():
    for table in U.BY_PROP.values():
        assert set(table.values()) <= set(F.FUNCTIONS)
    assert set(U.ALSO.values()) <= set(F.FUNCTIONS)
    assert set(U.STAGE_OF_FAMILY) | {"help", "panel"} == set(F.FAMILIES)


def test_panel_openings_and_the_last_session_are_kept():
    s = _state(sessions=4)
    U.count_panel(s, "FRESING_PT_waycover")
    U.count_panel(s, "FRESING_PT_waycover")
    assert s["panels"]["FRESING_PT_waycover"] == [2, 4]


def test_idle_time_is_not_counted():
    s = U.fresh()
    c = U.Clock()
    c.tick(s, now=0.0, stage="looks")
    c.tick(s, now=30.0)                       # 30 s working on looks
    c.tick(s, now=30.0 + U.IDLE + 1)          # away for over 2 min: nothing
    c.tick(s, now=200.0, stage="render")      # 49 s more on looks, then render
    c.tick(s, now=260.0)
    assert s["stages"] == {"looks": pytest.approx(79.0), "render": pytest.approx(60.0)}
    rows = U.stage_rows(s)
    assert [r[0] for r in rows] == list(U.STAGES) and max(r[3] for r in rows) == 1.0


# ---------------------------------------------------------------------------
# the favourites bar
# ---------------------------------------------------------------------------

def test_the_bar_is_sorted_only_at_a_start():
    s = U.fresh()
    _click(s, "fresing.turntable", n=5)
    _click(s, "fresing.render", n=3)
    _click(s, "fresing.clash_check", n=1)             # once: not yet earned
    U.start_session(s, "2026-11-18")
    assert s["bar"]["order"] == ["scene.turntable", "scene.still"] and s["sessions"] == 1 and s["first"] == "2026-11-18"
    _click(s, "fresing.render", n=10)                 # now used most: the bar does not move while the app runs
    assert s["bar"]["order"] == ["scene.turntable", "scene.still"]
    U.start_session(s)
    assert s["bar"]["order"][0] == "scene.still"


def test_pins_stay_first_and_a_new_pin_shows_at_once():
    s = U.fresh()
    for op in ("fresing.turntable", "fresing.render", "fresing.clash_check", "fresing.explode", "fresing.cylinder_add",
               "fresing.cable_add", "fresing.web3d_export", "fresing.decal_add", "fresing.cut_add"):
        _click(s, op, n=3)
    s["bar"]["size"] = 5
    U.start_session(s)
    assert len(s["bar"]["order"]) == 5
    U.pin(s, "help.pc_check", True)
    assert s["bar"]["order"][-1] == "help.pc_check" and len(s["bar"]["order"]) == 6     # nothing else moved
    U.start_session(s)
    assert s["bar"]["order"][0] == "help.pc_check" and len(s["bar"]["order"]) == 5
    U.pin(s, "help.pc_check", False)
    assert "help.pc_check" in s["bar"]["order"]                    # stays until the next start
    U.start_session(s)
    assert "help.pc_check" not in s["bar"]["order"]


def test_the_panels_own_switches_never_join_the_bar():
    s = U.fresh()
    _click(s, "fresing.workspace_pick", n=9)
    U.pin(s, "panel.workspace", True)
    U.start_session(s)
    assert s["bar"]["order"] == []


def test_counting_off_counts_no_session():
    s = U.fresh()
    s["track"] = False
    U.start_session(s)
    assert s["sessions"] == 0


# ---------------------------------------------------------------------------
# declutter
# ---------------------------------------------------------------------------

ALL = set(F.FUNCTIONS)


def _ask(s, used=(), shown=ALL, hidden=()):
    return U.declutter_candidate(s, set(shown), set(used), set(hidden), titles=TITLES)


def test_no_question_before_the_threshold():
    s = _state(sessions=U.THRESHOLD_DEFAULT - 1)
    assert _ask(s) == ""
    s["sessions"] = U.THRESHOLD_DEFAULT
    assert _ask(s) in TITLES


def test_a_panel_used_recently_or_by_the_project_is_never_asked_about():
    s = _state(sessions=30)
    first = _ask(s)
    assert first
    s["panels"][first] = [1, 25]                       # opened 5 starts ago: recent
    second = _ask(s)
    assert second and second != first
    used = {f for f in U.panel_functions(second)}
    assert _ask(s, used=used) != second
    s["panels"][first] = [1, 15]                       # 15 starts ago: not recent any more
    assert _ask(s) == first


def test_never_a_section_a_menu_or_the_import_and_panel_families():
    s = _state(sessions=50)
    seen = set()
    while True:
        p = _ask(s)
        if not p:
            break
        seen.add(p)
        U.answer_declutter(s, p, "later")
    assert seen and seen <= TITLES
    for p in seen:
        assert not any(F.FUNCTIONS[f].family in U.NEVER_ASK_FAMILIES for f in U.panel_functions(p))
    assert not (seen & set(places.SECTIONS))


def test_a_hidden_family_or_a_panel_hidden_already_is_not_asked_about():
    s = _state(sessions=40)
    p = _ask(s)
    shown = ALL - {U.panel_functions(p)[0]}           # one of its functions hidden by the workspace
    assert _ask(s, shown=shown) != p
    assert _ask(s, hidden={p}) != p


def test_answers_hide_later_never():
    s = _state(sessions=20)
    p = _ask(s)
    U.answer_declutter(s, p, "hide")
    assert set(U.panel_functions(p)) <= set(s["hidden"]) and p in s["declutter"]["asked"]
    assert _ask(s) != p
    hides = U.personal_hides(s, used=set())
    assert set(U.panel_functions(p)) <= set(hides)
    used = {U.panel_functions(p)[0]}
    assert used.isdisjoint(U.personal_hides(s, used=used))     # never hidden while the project uses it
    q = _ask(s)
    U.answer_declutter(s, q, "never")
    assert _ask(s) == "" and not s["declutter"]["on"]
    U.reset(s)
    assert s["hidden"] == [] and s["bar"]["pins"] == []


def test_switched_off_or_tracking_off_asks_nothing():
    s = _state(sessions=20)
    s["track"] = False
    assert _ask(s) == ""


# ---------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------

def test_file_round_trip(tmp_path):
    path = str(tmp_path / "cfg" / U.FILE_NAME)
    s = U.fresh()
    _click(s, "fresing.turntable", n=2)
    U.pin(s, "scene.still", True)
    U.save(path, s)
    back, note = U.load(path)
    assert note == "" and back == json.loads(json.dumps(s))
    assert U.load(str(tmp_path / "missing.json")) == (U.fresh(), "")


@pytest.mark.parametrize("text", ["{not json", "[]", '{"other": 1}', ""])
def test_a_broken_file_starts_empty_and_keeps_a_copy(tmp_path, text):
    path = tmp_path / U.FILE_NAME
    path.write_text(text, encoding="utf-8")
    s, note = U.load(str(path))
    assert s == U.fresh() and "copy" in note
    assert (tmp_path / (U.FILE_NAME + ".broken")).read_text(encoding="utf-8") == text


def test_a_file_of_a_newer_version_is_kept_aside(tmp_path):
    path = tmp_path / U.FILE_NAME
    path.write_text(json.dumps({U.MARKER: U.VERSION + 1, "sessions": 5}), encoding="utf-8")
    s, note = U.load(str(path))
    assert s == U.fresh() and (tmp_path / (U.FILE_NAME + ".newer")).exists()


def test_wrong_types_in_a_hand_edited_file_become_defaults():
    s = U.clean({U.MARKER: 1, "sessions": "x", "functions": {"a.b": [1], "c.d": ["2", 3]}, "stages": {"looks": "nan",
                 "junk": 3}, "bar": {"size": 99, "pins": [1, "scene.still"]}, "declutter": {"threshold": -5}})
    assert s["sessions"] == 0 and s["functions"] == {"c.d": [2, 3]} and s["stages"] == {"looks": 0.0}
    assert s["bar"]["size"] == U.BAR_MAX and s["bar"]["pins"] == ["scene.still"] and s["declutter"]["threshold"] == 1


def test_clear_keeps_the_switches_pins_and_hides():
    s = _state(sessions=12)
    _click(s, "fresing.turntable", n=4)
    s["bar"]["on"] = False
    U.pin(s, "scene.still", True)
    s["hidden"] = ["looks.cutaway"]
    s["track"] = False
    c = U.clear(s)
    assert c["functions"] == {} and c["sessions"] == 0 and c["buttons"] == {}
    assert not c["track"] and not c["bar"]["on"] and c["bar"]["pins"] == ["scene.still"] and c["hidden"] == ["looks.cutaway"]


# ---------------------------------------------------------------------------
# time saved: always an estimate, with its basis
# ---------------------------------------------------------------------------

def test_time_saved_is_an_estimate_with_a_basis():
    est = [f for f in F.FUNCTIONS.values() if f.manual_estimate]
    assert len(est) >= 10
    for f in est:
        assert U.basis(f.id).startswith("about ") and "by hand" in U.basis(f.id)
    assert U.estimate_seconds("looks.materials", parts=100) == 500
    assert U.estimate_seconds("scene.turntable", parts=100) == 900
    assert U.estimate_seconds("joints.rotate") == 0
    s = U.fresh()
    U.count_click(s, "fresing.turntable", "scene.turntable", U.estimate_seconds("scene.turntable"))
    assert U.saved_rows(s) == [("scene.turntable", 900.0, 1)]
    assert U.duration(40) == "40 s" and U.duration(900) == "15 min" and U.duration(5 * 3600) == "5.0 h"


def test_a_bad_estimate_is_refused_by_the_precheck():
    import dataclasses
    f = dataclasses.replace(F.FUNCTIONS["scene.turntable"], manual_estimate=("hour", 1, ""))
    assert any("manual_estimate" in p for p in F.problems([f]))
    assert not any("manual_estimate" in p for p in F.problems([F.FUNCTIONS["scene.turntable"]]))


def test_functions_whats_new_offers_are_not_asked_about_at_once():
    """Row 13 (task 0236): the first start after an update does not ask to hide a panel What's new advertises."""
    s = _state(sessions=U.THRESHOLD_DEFAULT)
    first = _ask(s)
    assert first
    U.note_new(s, U.panel_functions(first))                        # What's new listed its functions at this start
    assert _ask(s) != first
    s["sessions"] += U.THRESHOLD_DEFAULT - 1
    assert _ask(s) != first                                        # still too early
    s["sessions"] += 1
    assert _ask(s) == first or _ask(s) in TITLES                   # after ``threshold`` sessions it may be asked
    again = U.clean(json.loads(json.dumps(s)))
    assert again["declutter"]["new"] == s["declutter"]["new"]      # kept in the file
    assert U.clean({"declutter": {"new": {"a": "x", "b": 3}}})["declutter"]["new"] == {"a": 0, "b": 3}


def test_a_profiles_hides_are_the_users_own_and_reset_undoes_them():
    """Row 19: hides travel in the profile's own "hidden", the importer adds them to the user's, reset removes them."""
    s = U.fresh()
    s["hidden"] = ["looks.xray"]
    part = U.profile_part(s)
    assert part["hidden"] == {"ids": ["looks.xray"]}
    other = U.fresh()
    U.take_profile(other, dict(part, hidden={"ids": ["looks.xray", "nonsense.id", 5]}))
    assert other["hidden"] == ["looks.xray"]
    U.reset(other)
    assert other["hidden"] == []


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------

def test_a_profile_carries_the_bar_and_counts_only_when_ticked(tmp_path):
    s = U.fresh()
    _click(s, "fresing.turntable", n=6)
    U.pin(s, "scene.still", True)
    ws = W.make_own("Team", W.builtin("cnc"))
    ws.hide = ws.hide + ("looks.cutaway",)
    ws.extra = U.profile_part(s, with_counts=False)
    path = W.save_in(str(tmp_path), ws)
    data = json.load(open(path, encoding="utf-8"))
    assert data["favourites"]["pins"] == ["scene.still"] and "usage" not in data and "looks.cutaway" in data["hide"]
    ws.extra = U.profile_part(s, with_counts=True)
    path = W.save_in(str(tmp_path), ws)
    data = json.load(open(path, encoding="utf-8"))
    assert data["usage"]["functions"]["scene.turntable"][0] == 6
    back = W.load(path)
    assert back.extra["favourites"]["pins"] == ["scene.still"]
    assert "usage" not in json.loads(back.to_json())               # a project never keeps someone's counts
    other = U.fresh()
    U.take_profile(other, data, with_counts=False)
    assert other["bar"]["pins"] == ["scene.still"] and other["functions"] == {}
    U.take_profile(other, data, with_counts=True)
    assert other["functions"]["scene.turntable"][0] == 6 and other["bar"]["order"][0] == "scene.still"


def test_an_older_app_reads_a_profile_as_a_plain_workspace(tmp_path):
    ws = W.make_own("Team", W.builtin("product"))
    ws.extra = U.profile_part(U.fresh(), with_counts=True)
    d = ws.to_dict()
    d.pop("favourites")
    d.pop("usage")
    d.pop("hidden")
    assert W.from_dict(d).extra == {}


# ---------------------------------------------------------------------------
# privacy: nothing can be sent
# ---------------------------------------------------------------------------

NETWORK = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "ssl", "asyncio", "xmlrpc", "webbrowser",
           "telnetlib", "poplib", "imaplib", "aiohttp", "httpx"}


@pytest.mark.parametrize("rel", ["fresing_render/core/usage.py", "fresing_render/blender/usage.py",
                                 "fresing_render/blender/ops_usage.py", "fresing_render/blender/ui_usage.py"])
def test_the_tracker_imports_no_network_library(rel):
    tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
            names.add("__import__")
    assert not names & (NETWORK | {"__import__"}), names & NETWORK
