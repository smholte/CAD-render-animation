"""Task 0199: what the app shows at its start – the welcome for a new user, What's new after an update (core/start.py,
no Blender) – and the Fresing menu, the dialogs and the tour of only the new and changed models (Blender module)."""


import json

import pytest

from fresing_render.core import functions as F
from fresing_render.core import start as S


def _starts(state, version, n):
    shown = []
    for _ in range(n):
        kind = S.decide(state, version)
        shown.append(kind)
        state = S.started(state, version, kind)
    return shown, state


def test_a_new_user_sees_the_welcome_three_starts_then_never():
    shown, state = _starts(S.fresh(), "0.2.153", 5)
    assert shown == ["welcome"] * 3 + ["", ""]
    assert state["last_run"] == "0.2.153"                   # updates bring What's new from now on
    assert S.decide(state, "0.2.154") == "whats_new"


def test_later_counts_once_per_start_and_never_or_the_tour_stop_it():
    state = S.started(S.fresh(), "0.2.153", "welcome")
    state = S.answer_welcome(state, "0.2.153", "later")
    assert state["welcome"]["later"] == 1 and S.decide(state, "0.2.153") == "welcome"
    for choice in ("never", "tour"):
        st = S.answer_welcome(S.started(S.fresh(), "0.2.153", "welcome"), "0.2.153", choice)
        assert S.decide(st, "0.2.153") == "" and st["last_run"] == "0.2.153", choice


def test_whats_new_once_after_an_update_never_after_the_same_version_or_a_downgrade(tmp_path):
    path = str(tmp_path / "Instellingen é" / S.FILE_NAME)
    state = dict(S.fresh(), last_run="0.2.150")
    S.save(path, state)
    state = S.load(path)
    assert S.decide(state, "0.2.153") == "whats_new"
    state = S.started(state, "0.2.153", "whats_new")
    assert state["whats_new"] == {"from": "0.2.150", "to": "0.2.153", "opened": False}
    assert S.whats_new_pending(state)
    assert S.decide(state, "0.2.153") == ""                  # a second start: nothing
    assert S.decide(state, "0.2.152") == ""                  # an older version: nothing
    state = S.started(state, "0.2.152", "")
    assert state["last_run"] == "0.2.153"                    # the downgrade does not lower it
    # not opened, another update: still since the first version
    state = S.started(state, "0.2.154", S.decide(state, "0.2.154"))
    assert state["whats_new"]["from"] == "0.2.150" and state["whats_new"]["to"] == "0.2.154"
    state = S.opened_whats_new(state)
    assert not S.whats_new_pending(state)
    state = S.started(state, "0.2.155", S.decide(state, "0.2.155"))
    assert state["whats_new"]["from"] == "0.2.154"


def test_a_broken_file_is_a_fresh_start(tmp_path):
    p = tmp_path / S.FILE_NAME
    p.write_text("{not json", encoding="utf-8")
    assert S.load(str(p)) == S.fresh()
    p.write_text('{"last_run": 3, "welcome": "x"}', encoding="utf-8")
    assert S.load(str(p)) == S.fresh()


def test_title_says_since_when_versions_were_skipped():
    assert S.title("0.2.152", "0.2.153") == "What's new in 0.2.153"
    assert S.title("0.2.150", "0.2.153") == "What's new since 0.2.150"
    assert S.title("0.2.152", "0.2.153", ["0.2.153", "0.2.152"]) == "What's new in 0.2.153"
    assert S.title("0.2.150", "0.2.153", ["0.2.153", "0.2.151", "0.2.150"]) == "What's new since 0.2.150"


def test_new_functions_headline_first_then_newest_at_most_eight():
    rows = S.new_functions(F.FUNCTIONS, "0.2.140", "0.2.153")
    assert 0 < len(rows) <= S.WHATS_NEW_LINES and all(k == "new" for _f, k in rows)
    assert all(S.in_range(f.since, "0.2.140", "0.2.153") for f, _k in rows)
    # the functions a user meets first lead (task 0236, row 26), each group newest first
    flags = [f.headline for f, _k in rows]
    assert flags == sorted(flags, reverse=True) and flags[0]
    for want in (True, False):
        v = [S.vtuple(f.since) for f, _k in rows if f.headline == want]
        assert v == sorted(v, reverse=True)
    ids = {f.id for f, _k in S.new_functions(F.FUNCTIONS, "0.2.154", "0.2.155", limit=100)}
    assert "help.whats_new" in ids and "panel.workspace" not in ids       # 0.2.152: before the range
    assert S.new_functions(F.FUNCTIONS, "0.2.155", "0.2.155") == []


def test_what_is_new_after_0_2_141_shows_the_headlines_and_a_better_since_list():
    rows = S.new_functions(F.FUNCTIONS, "0.2.141", "0.2.175")
    ids = [f.id for f, _k in rows]
    assert len(rows) == S.WHATS_NEW_LINES
    for must in ("panel.workspace", "panel.client_view", "panel.sections", "help.whats_new"):
        assert must in ids, ids                            # the real list: what a user sees first is not cut off
    assert S.count_new_functions(F.FUNCTIONS, "0.2.141", "0.2.175") > len(rows)
    better = S.better_functions(F.FUNCTIONS, "0.2.141", "0.2.175")
    assert 0 < len(better) <= S.BETTER_LINES and all(k == "improved" for _f, k in better)
    assert "milling.fast_map" in [f.id for f, _k in S.better_functions(F.FUNCTIONS, "0.2.141", "0.2.175", 999)]
    assert not {f.id for f, _k in better} & {f.id for f, _k in S.new_functions(F.FUNCTIONS, "0.2.141", "0.2.175", 999)}
    v = [S.vtuple(f.changed) for f, _k in better]
    assert v == sorted(v, reverse=True)


def test_a_junk_version_lists_nothing():
    for junk in ("", "0.2.x", "abc", None):
        assert S.new_functions(F.FUNCTIONS, junk, "0.2.175") == []
        assert S.better_functions(F.FUNCTIONS, junk, "0.2.175") == []


@pytest.mark.parametrize("later", ["two", None, 1e400, [], {}, True, -5, "3"])
def test_a_damaged_start_file_is_cleaned_not_a_traceback(tmp_path, later):
    p = tmp_path / "s.json"
    data = {"last_run": "0.2.150", "welcome": {"later": later, "never": "yes", "done": 1},
            "whats_new": {"from": "0.2.x", "to": 5, "opened": "no"}}
    p.write_text(json.dumps(data).replace("Infinity", "1e400") if later != 1e400 else
                 '{"last_run": "0.2.150", "welcome": {"later": 1e400}, "whats_new": {"from": "0.2.x"}}',
                 encoding="utf-8")
    st = S.load(str(p))
    assert isinstance(st["welcome"]["later"], int) and st["welcome"]["never"] is False
    assert st["whats_new"]["from"] == "" and st["whats_new"]["to"] == ""
    shows = S.decide(st, "0.2.175")                        # no traceback, whatever the file held
    assert shows == "whats_new"
    st = S.started(st, "0.2.175", shows)
    assert st["last_run"] == "0.2.175"


def test_a_junk_last_run_shows_no_whats_new_list(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"last_run": "0.2.x", "welcome": {"done": true}}', encoding="utf-8")
    st = S.load(str(p))
    assert st["last_run"] == ""
    assert S.decide(st, "0.2.175") == ""                    # welcome is done; nothing else to show
    assert S.new_functions(F.FUNCTIONS, st["whats_new"]["from"], "0.2.175") == []


def test_marks():
    assert S.mark("0.2.153", "", "0.2.150", "0.2.153") == "new"
    assert S.mark("0.2.47", "0.2.152", "0.2.150", "0.2.153") == "changed"
    assert S.mark("0.2.47", "0.2.101", "0.2.150", "0.2.153") == ""
    assert S.mark("0.2.153", "", "", "0.2.153") == ""          # no update: no marks


# ---------------------------------------------------------------------------------------------------------------
# in Blender (as a Python module)
# ---------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def test_the_fresing_menu_is_in_the_top_bar_and_help_keeps_its_lines():
    from fresing_render.blender import ui_topbar
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    assert funcs.count(ui_topbar._draw_in_editor_menus) == 1
    for idname in ui_topbar.entries():
        if idname != "fresing.user_guide":                  # the app template's
            assert ui_topbar._has(idname), idname
    names = [getattr(f, "__name__", "") for f in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()]
    assert "_draw_help" in names                           # the update check line stays in Help
    from fresing_render.blender import lock
    for idname in ("fresing.tour_take", "fresing.whats_new", "fresing.welcome", "fresing.show_panel",
                   "fresing.pc_check", "fresing.user_guide", "fresing.update_check"):
        assert lock.allowed(idname), idname                 # they only open or show: allowed in the Client view
    # lock.py's own drawing of the top bar (no workspace tabs) draws the editor menus, so the menu is there too
    import inspect
    assert "TOPBAR_MT_editor_menus.draw_collapsible" in inspect.getsource(lock._draw_left_no_tabs)


def test_no_popup_in_the_background_or_with_the_flag(monkeypatch, tmp_path):
    from fresing_render.blender import welcome
    welcome._RUN["done"] = False
    assert welcome.at_start() == ""                          # background (pytest runs bpy without a window)
    assert welcome.suppressed()
    monkeypatch.setenv(S.NO_POPUP_ENV, "1")
    assert welcome.suppressed()


def test_whats_new_lists_and_the_tour_of_only_the_new_and_changed(tmp_path):
    from fresing_render.blender import tour, welcome
    sets = welcome.sets_new("0.2.141")
    ids = [ts.id for ts, _k in sets]
    assert "gantry" in ids and "house" in ids and "decals" not in ids   # changed in 0.2.152; the decals never
    assert welcome.summary("0.2.141").count("new test model") == 1
    page = welcome.guide_link_file("whats-new-start")
    assert "#whats-new-start" in open(page, encoding="utf-8").read()
    out = tour.build_all(str(tmp_path / "Tour é"), "0.2.153", only=("faces",))
    assert list(out["files"]) == ["faces"] and not out["errors"]
    assert tour.made_sets(str(tmp_path / "Tour é"), "0.2.153") == ["faces"]
    assert tour.ready_path(str(tmp_path / "Tour é"), "0.2.153").endswith("Painted faces.blend")
    assert bpy.context.scene.get(tour.TAG) == "faces"


def test_the_runner_passes_only_to_the_build(monkeypatch):
    from fresing_render.blender import tour
    from fresing_render.pccheck import runner
    got = {}
    monkeypatch.setattr(tour, "build_main", lambda folder="", only=(): got.update(folder=folder, only=only) or 0)
    runner.run_from_argv(["blender", "--", "tourbuild", "/x", "only=faces,crane"])
    assert got == {"folder": "/x", "only": ("faces", "crane")}


def test_the_stop_marks_in_the_panel():
    from fresing_render.blender import tour, ui_tour
    st = tour.find("workspace")                              # came in 0.2.152
    assert ui_tour.stop_mark(st, "0.2.151") == "New"
    assert ui_tour.stop_mark(tour.find("finishing"), "0.2.150") == "Changed"
    assert ui_tour.stop_mark(tour.find("faces"), "0.2.150") == ""
    assert ui_tour.stop_mark(st, "") == ""


def test_a_release_without_new_functions_passes_the_checks(monkeypatch, tmp_path):
    """Task 0202 (0.2.157 brought no new function): the PC check's line and the tour's stop test that What's new can
    list functions – after a release that adds none they look further back instead of failing."""
    import types

    from fresing_render.blender import tour, welcome
    from fresing_render.core import start
    from fresing_render.pccheck import checks
    real_new, real_rows = welcome.functions_new, start.new_functions
    def first_empty(real):                    # this release brings nothing new: the first ask finds no function
        asked = []

        def fake(*a, **k):
            asked.append(a)
            return [] if len(asked) == 1 else real(*a, **k)
        return fake
    monkeypatch.setattr(welcome, "functions_new", first_empty(real_new))
    out = checks.app_start_here(types.SimpleNamespace(work=str(tmp_path)))
    assert "functions" in out and not out.endswith(" 0 functions")
    monkeypatch.setattr(welcome, "functions_new", real_new)
    monkeypatch.setattr(start, "new_functions", first_empty(real_rows))
    assert "lists 0" not in tour._check_start_here(bpy.context.scene)
