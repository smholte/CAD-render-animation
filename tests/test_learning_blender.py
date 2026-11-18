"""Learn as you go in Blender (task 0208): the question's buttons, the list, the right-click, the card, the file."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import functions as F  # noqa: E402
from fresing_render.core import learning as L  # noqa: E402
from fresing_render.core import usage as U  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


class Layout:                                       # a stand-in that takes every call (no window in a test)
    def __getattr__(self, name):
        return lambda *a, **k: self

    def __setattr__(self, name, value):
        pass


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("learn")
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_USAGE_FILE"] = str(d / U.FILE_NAME)
    os.environ[U.TEST_ENV] = "1"
    fresing_render.register()
    yield
    fresing_render.unregister()
    for k in ("FRESING_WORKSPACES_DIR", "FRESING_USAGE_FILE", U.TEST_ENV):
        os.environ.pop(k, None)


@pytest.fixture()
def usage():
    from fresing_render.blender import usage as mod
    path = os.environ["FRESING_USAGE_FILE"]
    if os.path.exists(path):
        os.remove(path)
    mod.forget()
    bpy.ops.wm.read_homefile(use_empty=True)
    yield mod
    mod.forget()
    from fresing_render.blender import workspaces
    workspaces.PERSONAL["hide"] = ()


def _ask(usage, panel="FRESING_PT_xray"):
    usage.state()["sessions"] = 30
    usage._S["prompt"] = panel


def test_the_question_offers_the_teaching_buttons_and_hide(usage):
    from fresing_render.blender import learning
    _ask(usage)
    q = learning.question("FRESING_PT_xray")
    assert q["fid"] == "looks.xray" and q["guide"] and q["can_hide"] and q["line"]
    usage.state()["declutter"]["on"] = False
    assert not learning.question("FRESING_PT_xray")["can_hide"]
    usage.state()["learning"]["teach"] = False
    assert learning.question("FRESING_PT_xray")["fid"] == ""
    from fresing_render.blender import ui_usage
    assert ui_usage.FRESING_PT_favourites is not None


def test_add_to_my_learning_list_answers_the_question_and_hides_nothing(usage):
    _ask(usage)
    bpy.ops.fresing.usage_declutter(choice="learn")
    s = usage.state()
    assert L.find(s, "looks.xray") is not None and s["hidden"] == [] and usage.prompt() == ""
    assert "FRESING_PT_xray" in s["declutter"]["asked"]


def test_show_me_in_the_guide_lists_it_and_answers(usage, monkeypatch):
    from fresing_render.blender import learning
    opened = []
    monkeypatch.setattr(learning, "open_guide", lambda a: opened.append(a) or "file")
    _ask(usage)
    assert bpy.ops.fresing.learn_show(fid="looks.xray", how="GUIDE") == {"FINISHED"}
    assert opened == [F.FUNCTIONS["looks.xray"].guide]
    assert L.find(usage.state(), "looks.xray") is not None and usage.prompt() == ""


def test_the_guide_opens_the_installed_copy_or_else_the_web_page(usage, monkeypatch, tmp_path):
    from fresing_render.blender import files, learning, welcome
    seen = {"files": [], "url": []}
    monkeypatch.setattr(files, "open_path", lambda p: seen["files"].append(p))
    monkeypatch.setattr(welcome, "guide_file", lambda: str(tmp_path / "missing.html"))
    monkeypatch.setattr(bpy.ops.wm, "url_open", lambda url: seen["url"].append(url), raising=False)
    assert learning.open_guide("looks") in ("web", "")
    guide = tmp_path / "g.html"
    guide.write_text("x")
    monkeypatch.setattr(welcome, "guide_file", lambda: str(guide))
    monkeypatch.setattr(welcome, "guide_link_file", lambda a: str(tmp_path / f"{a}.html"))
    assert learning.open_guide("looks") == "file" and seen["files"]
    assert learning.open_guide("") == ""


def test_show_me_in_the_test_tour_is_refused_with_a_reason_when_there_is_no_tour_or_no_stop(usage, monkeypatch):
    from fresing_render.blender import learning
    nostop = next(f.id for f in F.FUNCTIONS.values() if not f.tour and L.teachable(f.id))
    assert "test tour" in learning.show_in_tour(bpy.context, nostop)
    withstop = next(f.id for f in F.FUNCTIONS.values() if f.tour and L.teachable(f.id))
    monkeypatch.setattr(learning, "tour_state", lambda scene: "none")
    assert "Take the test tour" in learning.show_in_tour(bpy.context, withstop)
    assert bpy.ops.fresing.learn_show(fid=nostop, how="TOUR") == {"CANCELLED"}


def test_the_tour_stop_of_a_function_is_set_up_and_pointed_at_when_a_tour_is_open(usage, monkeypatch):
    from fresing_render.blender import highlight, learning, tour
    went, pointed = [], []
    monkeypatch.setattr(learning, "tour_state", lambda scene: "here")
    monkeypatch.setattr(learning, "_go", lambda stop: went.append(stop))
    monkeypatch.setattr(highlight, "point_function", lambda fid, open_panels=False: pointed.append(fid) or True)
    fid = next(f.id for f in F.FUNCTIONS.values() if f.tour and L.teachable(f.id) and tour.find(f.tour[0]))
    assert learning.show_in_tour(bpy.context, fid) == ""
    assert went == [F.FUNCTIONS[fid].tour[0]] and pointed == [fid]


def test_a_right_clicked_button_finds_its_function(usage):
    from fresing_render.blender import learning, ops_learning
    assert learning.idname_of("FRESING_OT_sort_parts") == "fresing.sort_parts" and learning.idname_of("X") == ""
    assert learning.function_of_button("fresing.turntable") == "scene.turntable"
    prop_fn = next(f for f in F.FUNCTIONS.values() if f.prop and L.teachable(f.id))
    assert learning.function_of_button("", prop_fn.prop)

    class Ctx:
        button_operator = type("P", (), {"bl_rna": type("R", (), {"identifier": "FRESING_OT_turntable"})})()
        button_prop = None
    assert ops_learning.button_function(Ctx()) == "scene.turntable"

    class Other:
        button_operator = type("P", (), {"bl_rna": type("R", (), {"identifier": "MESH_OT_x"})})()
        button_prop = None
    assert ops_learning.button_function(Other()) == ""
    bpy.ops.fresing.learn_add(fid="scene.turntable")
    assert L.find(usage.state(), "scene.turntable") is not None
    assert hasattr(bpy.types.UI_MT_button_context_menu, "draw")


def test_the_list_window_draws_ticks_by_itself_and_says_so_once(usage):
    from fresing_render.blender import ops_learning
    s = usage.state()
    bpy.ops.fresing.learn_add(fid="scene.turntable")
    for _ in range(3):
        pass
    for day in ("2026-11-01", "2026-11-02", "2026-11-03"):
        L.note_use(s, "scene.turntable", day)
    assert L.find(s, "scene.turntable")["done"]
    ops_learning.draw_list(Layout(), L.take_told(s))
    assert L.take_told(s) == []
    ops_learning.draw_list(Layout())
    bpy.ops.fresing.learn_done(fid="scene.turntable")                # click again: the tick goes
    assert not L.find(s, "scene.turntable")["done"]
    bpy.ops.fresing.learn_remove(fid="scene.turntable")
    assert L.find(s, "scene.turntable") is None
    ops_learning.draw_list(Layout())                                 # the empty list draws too


def test_a_use_counts_a_day_and_the_file_keeps_the_list(usage):
    s = usage.state()
    bpy.ops.fresing.learn_add(fid="scene.turntable")
    usage.record("fresing.turntable")
    assert len(s["learning"]["days"]["scene.turntable"]) == 1
    assert usage.save(force=True)
    usage.forget()
    assert L.find(usage.state(), "scene.turntable") is not None


def test_the_card_has_one_suggestion_and_learn_and_not_interested_answer_it(usage):
    from fresing_render.blender import learning, ui_top
    sc = bpy.context.scene
    s = usage.state()
    s["sessions"] = 5
    for _ in range(3):
        usage.record("fresing.turntable")
    fid = learning.suggestion(sc)
    assert fid and learning.suggestion(sc) == fid
    assert bpy.types.FRESING_PT_next.poll(bpy.context)
    ui_top._draw_learn(Layout(), bpy.context)
    assert bpy.ops.fresing.learn_next(fid=fid, choice="no") == {"FINISHED"}
    assert fid in s["learning"]["declined"] and learning.suggestion(sc) == ""


def test_whats_new_adds_the_new_functions(usage):
    since = "0.2.100"
    expect = L.new_since(since)
    assert expect
    bpy.ops.fresing.learn_add_new(since=since)
    assert all(L.find(usage.state(), f) is not None for f in expect)


def test_the_my_usage_window_and_the_clear_question_draw(usage):
    from fresing_render.blender import ops_usage
    ops_usage.draw_window(Layout(), bpy.context)
    wm = bpy.context.window_manager
    wm.fresing_learn_days = 5
    assert usage.state()["learning"]["need_days"] == 5
    wm.fresing_learn_teach = False
    assert not usage.state()["learning"]["teach"]
    bpy.ops.fresing.learn_add(fid="scene.still")
    bpy.ops.fresing.usage_clear(also_list=False)
    assert L.find(usage.state(), "scene.still") is not None
    bpy.ops.fresing.usage_clear(also_list=True)
    assert usage.state()["learning"]["list"] == []


def test_the_menu_line_and_the_tooltips(usage):
    from fresing_render.blender import ui_topbar
    assert "fresing.learn_window" in ui_topbar.entries()
    for name in ("learn_show", "learn_add", "learn_add_new", "learn_done", "learn_remove", "learn_next", "learn_window"):
        assert getattr(bpy.ops.fresing, name).get_rna_type().description
