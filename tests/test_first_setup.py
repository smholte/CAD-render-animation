"""Task 0276: the first-start set-up – its rules (core/first_setup.py, core/start.py, a set-up file's skip; no Blender)
and its Blender side (the window's steps draw, the work ticks set the workspace, the menu entry, the app template)."""

import os

import pytest

from fresing_render.core import first_setup as C
from fresing_render.core import locations as L
from fresing_render.core import start as S

from fresing_render.core import workspaces as W  # noqa: E402

CNC = W.NAMES["cnc"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# who sees it
# ---------------------------------------------------------------------------

def test_a_new_user_gets_the_set_up_at_most_three_starts():
    state, shown = S.fresh(), []
    for _ in range(4):
        kind = S.decide(state, "0.2.233")
        shown.append(kind)
        state = S.started(state, "0.2.233", kind)
    assert shown == ["setup", "setup", "setup", ""]
    assert S.decide(state, "0.2.234") == "whats_new"        # from then on: What's new after an update


@pytest.mark.parametrize("how", ["done", "skipped"])
def test_done_or_skipped_never_again_and_updates_bring_whats_new(how):
    state = S.setup_finished(S.started(S.fresh(), "0.2.233", "setup"), "0.2.233", how, step="pc", work=["cnc"])
    assert state["setup"]["state"] == how and state["setup"]["work"] == ["cnc"] and state["last_run"] == "0.2.233"
    assert S.decide(state, "0.2.233") == ""
    assert S.decide(state, "0.2.234") == "whats_new"


def test_closed_on_the_way_is_asked_again_and_keeps_its_step():
    state = S.setup_finished(S.started(S.fresh(), "0.2.233", "setup"), "0.2.233", "", step="company", work=["sales"])
    assert S.decide(state, "0.2.233") == "setup"
    assert state["setup"]["step"] == "company" and state["setup"]["work"] == ["sales"] and state["last_run"] == ""


def test_an_update_from_before_the_set_up_shows_whats_new_not_the_set_up():
    state = dict(S.fresh(), last_run="0.2.195")
    assert S.decide(state, "0.2.233") == "whats_new"


def test_an_old_start_file_without_the_set_up_part_reads(tmp_path):
    p = tmp_path / "Instellingen é" / S.FILE_NAME
    p.parent.mkdir()
    p.write_text('{"last_run": "", "welcome": {"later": 1}}', encoding="utf-8")
    st = S.load(str(p))
    assert st["setup"] == S.fresh_setup() and S.decide(st, "0.2.233") == "setup"


@pytest.mark.parametrize("junk", ['{"setup": "x"}', '{"setup": {"state": "maybe", "work": "cnc", "step": 3}}',
                                  '{"setup": {"state": "done", "work": [1, "cnc", null], "by": "me"}}'])
def test_a_damaged_set_up_part_is_cleaned(tmp_path, junk):
    p = tmp_path / S.FILE_NAME
    p.write_text(junk, encoding="utf-8")
    su = S.load(str(p))["setup"]
    assert su["state"] in S.SETUP_STATES and isinstance(su["work"], list) and isinstance(su["step"], str)
    assert all(isinstance(w, str) for w in su["work"]) and su["by"] in ("", "it")


def test_a_round_trip_keeps_it(tmp_path):
    p = str(tmp_path / S.FILE_NAME)
    st = S.setup_finished(S.fresh(), "0.2.233", "skipped", by="it")
    S.save(p, st)
    assert S.load(p)["setup"] == st["setup"] and st["setup"]["by"] == "it"


# ---------------------------------------------------------------------------
# the work ticks, the hub's chapter, the languages
# ---------------------------------------------------------------------------

def test_the_ticks_give_the_workspace_by_the_rule():
    from fresing_render.core import workspaces as W
    assert C.workspace_for([])[0] == ""                                  # not chosen = Essentials
    for key, _title, ws, _ch in C.WORK:
        assert C.workspace_for([key])[0] == W.NAMES[ws]
        assert C.ticks_for(W.NAMES[ws]) == [key]
    assert C.workspace_for(["cnc", "sales"])[0] == W.DEFAULT == "All functions"
    assert C.workspace_for(["nonsense"])[0] == ""
    assert "Essentials" in C.RULE and "All functions" in C.RULE


def test_every_tick_names_a_real_workspace_and_hub_chapter():
    from fresing_render.core import workspaces as W
    from fresing_render.blender import tour
    for _k, _t, ws, ch in C.WORK:
        assert ws in W.BUILTIN and ch in tour.GROUPS
    assert C.chapter_for(["cnc"]) == "Machining" and C.chapter_for([]) == ""


def test_the_languages_english_first():
    assert C.LANGUAGES[0][0] == "en_US" and C.language_ok("nl_NL") and not C.language_ok("fr_FR")


# ---------------------------------------------------------------------------
# step 3: the PC in plain words
# ---------------------------------------------------------------------------

FAST = {"pc": {"cpu": "Test CPU", "cores": 24, "ram_gb": 64},
        "results": [{"id": "app.start", "status": "OK"},
                    {"id": "gpu.device", "status": "OK", "note": "GPU (OPTIX): Test RTX"},
                    {"id": "pc.gpu", "status": "OK", "note": "The graphics card draws the window"},
                    {"id": "render.gpu", "status": "OK", "metrics": {"render": [6.2, "s"]}}]}


def test_a_pc_with_a_card_gets_live_preview_on():
    s = C.pc_summary(FAST)
    assert s["gpu"] and s["live_preview"] and not s["slow"]
    texts = " ".join(t for _i, t in s["lines"])
    assert "Test RTX" in texts and "graphics card" in texts and "6 s" in texts and "24 cores" in texts


def test_a_pc_without_a_card_is_called_slow_and_live_preview_off():
    probe = {"pc": {"cores": 4, "ram_gb": 8},
             "results": [{"id": "app.start", "status": "OK"}, {"id": "gpu.device", "status": "SKIPPED"}]}
    s = C.pc_summary(probe)
    assert not s["gpu"] and not s["live_preview"]
    assert s["slow"].startswith("Big models will be slow on this PC") and "4 processor cores" in s["slow"]
    assert "8 GB" in s["slow"] and "processor" in " ".join(t for _i, t in s["lines"])


def test_a_slow_card():
    probe = {"pc": FAST["pc"], "results": FAST["results"][:3] + [
        {"id": "render.gpu", "status": "OK", "metrics": {"render": [C.SLOW_HD_S + 5, "s"]}}]}
    assert "slow" in C.pc_summary(probe)["slow"] and not C.pc_summary(probe)["live_preview"]


@pytest.mark.parametrize("note, want", [
    ("draws: llvmpipe (LLVM 15.0.7, 256 bits) (built-in graphics); renders: CPU", "without a graphics card"),
    ("draws: NVIDIA GeForce RTX 3090 (graphics card); renders: OPTIX: RTX 3090", "by the graphics card NVIDIA GeForce RTX 3090"),
    ("draws: not known yet (start the app once); renders: CPU", ""),
    ("renders: CPU", ""),
    ("The graphics card draws the window", "The graphics card draws the window"),
    ("", "")])
def test_your_pc_says_who_draws_the_window_in_plain_words(note, want):
    """0328 row 32: "draws: llvmpipe …; renders: CPU" was shown as it is; the render device has its own line."""
    got = C.window_words(note)
    assert (want in got) if want else got == ""
    assert "draws:" not in got and "renders:" not in got and "llvmpipe" not in got
    probe = {"pc": {}, "results": [{"id": "pc.gpu", "status": "OK", "note": note}]}
    texts = [t for _i, t in C.pc_summary(probe)["lines"]]
    assert not any("draws:" in t or "renders:" in t for t in texts)


@pytest.mark.parametrize("probe", [{}, {"error": "boom"}, {"results": []},
                                   {"results": [{"id": "app.start", "status": "FAILED", "reason": "models missing"}]}])
def test_a_probe_that_did_not_run_says_why(probe):
    assert C.probe_failed_text(probe)


@pytest.mark.parametrize("probe", [{"pc": "x", "results": [{"id": "render.gpu", "status": "OK", "metrics": {}}]},
                                   {"pc": {"cores": "many"}, "results": [{"id": "gpu.device", "status": "OK"}]},
                                   {"results": [{"id": "render.gpu", "status": "OK", "metrics": {"render": ["x"]}}]}])
def test_a_strange_probe_never_breaks_the_summary(probe):
    try:
        C.pc_summary(dict(probe, pc=probe.get("pc") if isinstance(probe.get("pc"), dict) else {}))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"pc_summary raised {exc!r}")


def test_the_probe_lines_are_quick_lines_of_the_pc_check():
    from fresing_render.pccheck import checks
    from fresing_render.pccheck import core as pcore
    quick = {ln.id for ln in pcore.lines_for(checks.LINES, "quick", False)}
    assert set(C.PROBE_LINES) <= quick
    assert "queue.eevee" not in C.PROBE_LINES                 # no video in the set-up


# ---------------------------------------------------------------------------
# a company's set-up file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("data", [{"first_setup": "skip"}, {"first_start": {"first_setup": "skip"}},
                                  {"first_start": {"skip": True}}, {"first_setup": " SKIP "}])
def test_a_set_up_file_can_skip_the_first_start(tmp_path, data):
    path = str(tmp_path / ("Beheer é" + L.SETUP_EXT))
    L.write_setup(path, L.from_data(dict({"id": "managed", "name": "Managed"}, **data)))
    s = L.read_setup(path)
    assert not s.notes                                      # "first_setup" is a key this app knows
    assert C.from_setups([s.first_start])["skip"]


def test_a_set_up_file_pre_fills_the_work_and_language():
    got = C.from_setups([{"workspace": CNC, "language": "de_DE", "work": ["cnc", "x"]},
                         {"workspace": "Sales", "language": "xx"}])
    assert got == {"skip": False, "workspace": CNC, "work": ["cnc"], "language": "de_DE"}
    assert C.from_setups(["junk", None, 3]) == {"skip": False, "workspace": "", "work": [], "language": ""}


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def addon(tmp_path_factory):
    pytest.importorskip("bpy")
    import fresing_render
    d = tmp_path_factory.mktemp("first_setup")
    os.environ["FRESING_LOCATIONS_FILE"] = str(d / "fresing_locations.json")
    os.environ["FRESING_SETTINGS_FILE"] = str(d / "fresing_settings.json")
    fresing_render.register()
    import bpy
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()
    os.environ.pop("FRESING_LOCATIONS_FILE", None)
    os.environ.pop("FRESING_SETTINGS_FILE", None)


def test_the_window_draws_every_step_and_the_ticks_set_the_workspace(addon):
    import bpy
    from fresing_render.blender import first_setup, prefs, ui_settings
    v = first_setup.values()
    assert v is not None
    for key in C.STEP_KEYS:
        v.step = key
        first_setup.DRAW[key](ui_settings._Any(), bpy.context, v)
    p = prefs.get()
    was = p.default_workspace
    try:
        v.work_cnc = True
        assert p.default_workspace == CNC
        v.work_animator = True
        assert p.default_workspace == "All functions"
        v.work_cnc = v.work_animator = False
        assert p.default_workspace == ""
    finally:
        p.default_workspace = was


def test_next_and_back_walk_the_steps_and_keep_where_it_stands(addon, monkeypatch, tmp_path):
    import bpy
    from fresing_render.blender import first_setup, welcome
    monkeypatch.setattr(welcome, "state_path", lambda: str(tmp_path / S.FILE_NAME))
    monkeypatch.setattr(first_setup, "start_probe", lambda: "")
    v = first_setup.values()
    v.step = "welcome"
    assert bpy.ops.fresing.first_setup_step(go="NEXT") == {"FINISHED"} and v.step == "work"
    assert welcome.load()["setup"]["step"] == "work"
    bpy.ops.fresing.first_setup_step(go="TO", to="done")
    assert v.step == "done"
    bpy.ops.fresing.first_setup_step(go="NEXT")
    assert v.step == "done"                                 # not past the last
    bpy.ops.fresing.first_setup_step(go="BACK")
    assert v.step == "hub"
    assert bpy.ops.fresing.first_setup_skip() == {"FINISHED"}
    assert welcome.load()["setup"]["state"] == "skipped"


def test_nothing_opens_in_the_background_and_the_menu_has_set_up_again(addon):
    from fresing_render.blender import first_setup, ui_topbar, welcome
    assert first_setup.open_window()                      # a reason: no window in the background
    welcome._RUN["done"] = False
    assert welcome.at_start() == ""
    first_setup.at_load()                                 # background: does nothing (no preferences saved)
    assert not first_setup._S["splash_hidden"]
    assert "fresing.first_setup" in ui_topbar.entries() and ui_topbar._has("fresing.first_setup")


def test_the_app_template_hands_the_first_start_to_the_extension():
    with open(os.path.join(ROOT, "app_template", "fresing_render", "__init__.py"), encoding="utf-8") as fh:
        text = fh.read()
    assert "_no_blender_quick_setup(name)" in text and '".blender.first_setup").at_load(name)' in text
    assert "save_userpref" in text                       # without the extension: Blender's preferences still saved


def test_the_page_window_is_a_page_window_everywhere(addon):
    from fresing_render.blender import ops_settings, ops_setup, panels
    assert ops_setup.FIRST_SETUP_MARK in ops_setup.PAGE_MARKS and ops_setup.FIRST_SETUP_MARK in panels.SIDE_MARKS
    assert "FRESING_PT_first_setup" in ops_settings.PAGES


def test_opening_the_set_up_keeps_a_workspace_the_user_chose(addon, monkeypatch, tmp_path):
    from fresing_render.blender import first_setup, prefs, welcome
    monkeypatch.setattr(welcome, "state_path", lambda: str(tmp_path / S.FILE_NAME))
    v, p = first_setup.values(), prefs.get()
    was = p.default_workspace
    try:
        v.work_cnc = True                                   # ticks left from before …
        p.default_workspace = "My own workspace"            # … and a workspace of the user's own since
        first_setup.prefill(v)                              # (no ticks kept, no set-up file)
        assert not v.work_cnc and p.default_workspace == "My own workspace"
        v.work_sales = True                                 # a click writes
        assert p.default_workspace == "Sales"
    finally:
        v.work_sales = False
        p.default_workspace = was
