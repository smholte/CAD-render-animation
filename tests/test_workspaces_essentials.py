"""Workspaces round 2 (task 0294): Essentials as the start of anyone who has not chosen, the task workspaces Sales,
Quick render, Animator and Reviewer (each exactly its list of functions), favourite workspaces on top of the
drop-down, kept over a restart."""

import json
import os

import pytest

from fresing_render.core import functions as F
from fresing_render.core import workspaces as W

TASK = ("essentials", "sales", "quick", "animator", "reviewer", "welding", "builder", "video", "houses")  # 0321: +4

# ---------------------------------------------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------------------------------------------


def test_essentials_is_first_and_the_task_workspaces_are_built_in():
    assert list(W.BUILTIN)[0] == "essentials" and W.NAMES["essentials"] == W.START == "Essentials"
    assert list(W.BUILTIN)[-1] == "full"
    for key, name in (("sales", "Sales"), ("quick", "Quick render"), ("animator", "Animator"),
                      ("reviewer", "Reviewer")):
        assert W.NAMES[key] == name and W.key_of(name) == key
        assert len(W.BUILTIN[key][1]) > 40                    # a tooltip that says what it is for
    assert set(F.TASK_WORKSPACES) == set(TASK) and set(TASK) <= set(F.WORKSPACE_KEYS)


@pytest.mark.parametrize("key", TASK)
def test_a_task_workspace_shows_exactly_its_functions(key):
    ws = W.builtin(key)
    assert W.shown_functions(ws) == frozenset(F.TASK_WORKSPACES[key])
    assert not ws.lock and not ws.blender_ui
    assert len(set(F.TASK_WORKSPACES[key])) == len(F.TASK_WORKSPACES[key]), "a function named twice"
    for fid in F.TASK_WORKSPACES[key]:
        assert fid in F.FUNCTIONS, fid
    hidden = W.hidden_panels(ws)
    assert "FRESING_PT_workspace" not in hidden and "FRESING_PT_tabs" not in hidden   # the switcher stays


def test_a_task_workspace_list_naming_a_function_that_is_gone_is_refused(monkeypatch):
    monkeypatch.setitem(F.TASK_WORKSPACES, "sales", F.TASK_WORKSPACES["sales"] + ("scene.gone",))
    assert any("'scene.gone' is not a function id" in p for p in F.problems())


def test_a_function_built_later_adds_itself_to_a_task_workspace():
    f = F.Function(id="scene.later", title="Later", family="scene", panel="FRESING_PT_scene", button="x.y",
                   workspaces=("sales",))
    assert f.shown_in("sales") and not f.shown_in("reviewer") and f.shown_in("all")
    assert not [p for p in F.problems([f], duplicates=[]) if "workspace" in p]


def test_essentials_holds_a_first_picture_and_a_simple_motion():
    shown = W.shown_functions(W.builtin("essentials"))
    for fid in ("import.step", "looks.materials", "scene.surroundings", "looks.light_look", "scene.camera",
                "joints.rotate", "poses.pose", "animation.build", "scene.still", "scene.turntable"):
        assert fid in shown, fid
    for fid in ("cnc.machine", "milling.cut", "offshore.cables", "web.export", "lifting.place", "queue.still"):
        assert fid not in shown, fid
    hidden = W.hidden_panels(W.builtin("essentials"))
    for panel in ("import", "looks", "motion", "poses", "scene", "camera", "output", "turntable", "animation"):
        assert "FRESING_PT_" + panel not in hidden, panel
    for panel in ("cnc", "milling", "cables", "web3d", "queue", "cylinders"):
        assert "FRESING_PT_" + panel in hidden, panel


def test_sales_shows_outputs_and_hides_structure_and_motion_without_the_lock():
    ws = W.builtin("sales")
    hidden = W.hidden_panels(ws)
    for gone in ("import", "structure", "place", "cylinders", "mechanisms", "cnc"):
        assert "FRESING_PT_" + gone in hidden, gone
    # task 0321 (owner 24 Nov): Sales may move joints – 4 Motion, its Joints and Poses show
    for shown in ("looks", "schemes", "shots", "scene", "turntable", "output", "web3d", "queue", "motion", "joints",
                  "poses"):
        assert "FRESING_PT_" + shown not in hidden, shown
    assert not ws.lock and W.builtin("client").lock        # unlike the Client view, looks can still be changed


def test_reviewer_and_animator_and_quick_render():
    rev = W.shown_functions(W.builtin("reviewer"))
    assert {"scene.save", "looks.cutaway", "poses.explode", "animation.labels", "animation.clash"} <= rev
    assert "joints.rotate" not in rev and "import.step" not in rev
    ani = W.shown_functions(W.builtin("animator"))
    assert {"joints.rotate", "machines.cylinder", "machines.mechanism", "poses.pose", "animation.camera_path",
            "animation.labels", "queue.video", "animation.finishing"} <= ani
    assert "milling.cut" not in ani and "web.export" not in ani
    q = W.shown_functions(W.builtin("quick"))
    assert {"import.step", "looks.materials", "scene.surroundings", "scene.still", "scene.turntable"} <= q
    assert "joints.rotate" not in q and "animation.add" not in q


def test_the_area_workspaces_are_unchanged_by_the_task_lists():
    for key in ("cnc", "offshore", "product", "client", "education", "lifting"):
        for f in F.FUNCTIONS.values():
            if key == "client" and f.id.startswith(F.NO_CLIENT):       # task 0333: the Client view imports nothing
                assert not f.shown_in(key), f.id
                continue
            assert f.shown_in(key) == (key in (f.workspaces or F.FAMILY_WORKSPACES.get(f.family, ()))), (key, f.id)


def test_stars_are_kept_in_order_and_survive_damage():
    s = W.toggle_star([], "Sales")
    s = W.toggle_star(s, "CNC & machining")
    assert s == ["Sales", "CNC & machining"]
    assert W.parse_stars(W.stars_json(s)) == s
    assert W.toggle_star(s, "sales") == ["CNC & machining"]                 # a second press takes it away
    assert W.parse_stars("not json") == [] and W.parse_stars('{"a": 1}') == [] and W.parse_stars("") == []
    assert W.parse_stars('["A", 3, "a", "  B  "]') == ["A", "B"]
    assert W.rename_star(["X", "Old"], "old", "New") == ["X", "New"]
    assert W.stars_json([]) == ""


def test_the_menu_puts_new_projects_and_starred_on_top():
    names = [W.NAMES[k] for k in W.BUILTIN] + ["My offshore"]
    top, rest = W.menu_order(names, ["Reviewer", "My offshore", "Gone"], "Essentials")
    assert top == ["Essentials", "Reviewer", "My offshore"]
    assert rest == [n for n in names if n not in top] and rest[0] == "All functions"
    top, rest = W.menu_order(names, [], "")
    assert top == [] and rest == names
    top, _ = W.menu_order(names, ["essentials"], "Essentials")            # the same one twice: once
    assert top == ["Essentials"]


def test_a_new_user_starts_in_essentials_an_existing_one_keeps_all_functions():
    assert W.start_choice("", "") == ""                                     # a new user: not chosen -> Essentials
    assert W.start_choice("", "0.2.100", since="0.2.220") == W.DEFAULT       # ran a version before Essentials
    assert W.start_choice("", "0.2.220", since="0.2.220") == ""             # started in Essentials already
    assert W.start_choice("", "0.2.230", since="0.2.220") == ""
    assert W.start_choice("CNC & machining", "0.2.100", since="0.2.220") == "CNC & machining"
    assert W.start_choice("", "junk", since="0.2.220") == ""
    assert W.START_SINCE and W._vt(W.START_SINCE)


# ---------------------------------------------------------------------------------------------------------------
# in Blender (as a Python module)
# ---------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import fresing_render
    d = tmp_path_factory.mktemp("ws2")
    keep = {k: os.environ.get(k) for k in ("FRESING_WORKSPACES_DIR", "FRESING_SETTINGS_FILE", "FRESING_WORKSPACE_START")}
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_SETTINGS_FILE"] = str(d / "fresing_settings.json")
    os.environ.pop("FRESING_WORKSPACE_START", None)           # a real user: not chosen means Essentials
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    from fresing_render.blender import settings_store
    settings_store.forget()
    settings_store.load()
    yield d
    fresing_render.unregister()
    for k, v in keep.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _fresh(app):
    from fresing_render.blender import prefs, settings_store, workspaces
    p = prefs.get()
    p.default_workspace, p.workspace_stars = "", ""
    settings_store.save(p)
    bpy.ops.wm.read_homefile(use_empty=True)
    workspaces.forget_scan()
    return p, workspaces


def test_a_new_project_of_a_new_user_is_in_essentials(app):
    p, workspaces = _fresh(app)
    sc = bpy.context.scene
    sc.fresing.ws_name = ""
    assert workspaces.default_name() == "Essentials"
    assert workspaces.ensure(sc) and sc.fresing.ws_name == "Essentials"
    assert not workspaces.panel_hidden(sc, "FRESING_PT_import") and workspaces.panel_hidden(sc, "FRESING_PT_cnc")


def test_a_user_who_chose_keeps_it_and_a_project_keeps_its_own(app):
    p, workspaces = _fresh(app)
    p.default_workspace = "CNC & machining"
    sc = bpy.context.scene
    sc.fresing.ws_name = ""
    workspaces.ensure(sc)
    assert sc.fresing.ws_name == "CNC & machining"
    workspaces.switch(sc, "Offshore & cable laying")              # a project already in a workspace keeps it
    assert not workspaces.ensure(sc) and sc.fresing.ws_name == "Offshore & cable laying"


def test_an_existing_user_is_moved_to_all_functions_once(app, monkeypatch):
    from fresing_render.blender import settings_store, welcome
    from fresing_render.core import settings_file as sf
    p, workspaces = _fresh(app)
    monkeypatch.setattr(welcome, "load", lambda: {"last_run": "0.1.0"})
    assert workspaces.keep_for_existing_user() == "All functions"
    assert p.default_workspace == "All functions"
    res = sf.read(settings_store.path(), settings_store.spec())        # written down: his choice from now on
    assert res.values.get("default_workspace") == "All functions"
    assert workspaces.keep_for_existing_user() == ""                  # once: a choice is never changed
    p.default_workspace = ""
    monkeypatch.setattr(welcome, "load", lambda: {"last_run": ""})    # a new user
    assert workspaces.keep_for_existing_user() == "" and p.default_workspace == ""


def test_stars_are_kept_over_a_restart_and_follow_a_rename(app):
    from fresing_render.blender import settings_store
    p, workspaces = _fresh(app)
    assert bpy.ops.fresing.workspace_star(name="Reviewer") == {"FINISHED"}
    assert bpy.ops.fresing.workspace_star(name="Sales") == {"FINISHED"}
    assert workspaces.stars() == ["Reviewer", "Sales"]
    top, rest = workspaces.menu()
    assert [r[0] for r in top] == ["Essentials", "Reviewer", "Sales"]
    assert "Sales" not in [r[0] for r in rest]
    # a restart: the preferences come back empty, the settings file gives them back
    p.workspace_stars = ""
    settings_store.forget()
    settings_store.load()
    assert workspaces.stars() == ["Reviewer", "Sales"]
    with open(settings_store.path(), encoding="utf-8") as fh:
        assert json.loads(json.load(fh)["settings"]["workspace_stars"]) == ["Reviewer", "Sales"]
    assert bpy.ops.fresing.workspace_star(name="Reviewer") == {"FINISHED"}
    assert workspaces.stars() == ["Sales"]
    # an own workspace still loads, can be starred and its star follows a rename
    sc = bpy.context.scene
    workspaces.switch(sc, "Quick render")
    workspaces.save_own(sc, "My quick one")
    assert "My quick one" in workspaces.library(force=True)
    workspaces.toggle_star("My quick one")
    workspaces.rename_own(sc, "My quick one", "Our quick one")
    assert workspaces.stars() == ["Sales", "Our quick one"]
    assert W.shown_functions(workspaces.current(sc)) == W.shown_functions(W.builtin("quick"))
    top, _rest = workspaces.menu()
    assert [r[0] for r in top][-1] == "Our quick one"


def test_the_drop_down_draws_with_a_star_on_every_row(app):
    from fresing_render.blender import ops_workspace
    p, workspaces = _fresh(app)
    workspaces.toggle_star("Animator")
    calls = []

    class Rec:
        def __getattr__(self, name):
            if name == "operator":
                def op(idname, **k):
                    calls.append((idname, k.get("icon")))
                    return type("O", (), {})()
                return op
            return lambda *a, **k: self

    menu = type("M", (), {"layout": Rec()})()
    ops_workspace.FRESING_MT_workspaces.draw(menu, bpy.context)
    picks = [c for c in calls if c[0] == "fresing.workspace_pick"]
    stars = [c for c in calls if c[0] == "fresing.workspace_star"]
    assert len(picks) == len(stars) == len(workspaces.names())
    assert stars.count(("fresing.workspace_star", "SOLO_ON")) == 1
