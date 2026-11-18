"""The usage tracker in Blender (task 0181): every Fresing button counts once, a panel opening counts, the personal
hides go on top of the workspace (never what the project uses), one question per session, profiles, the cost."""

import json
import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import functions as F  # noqa: E402
from fresing_render.core import usage as U  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("usage")
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


def _polls(name):
    from fresing_render.blender import panels
    cls = getattr(bpy.types, name)
    return bool(cls.poll(bpy.context)) and panels.visible(name, bpy.context, folds=False)


def test_every_fresing_button_counts_except_the_trackers_own():
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        idname = getattr(cls, "bl_idname", "")
        if not (isinstance(cls, type) and issubclass(cls, bpy.types.Operator) and idname.startswith("fresing.")):
            continue
        wrapped = any(getattr(getattr(cls, a, None), "_fr_usage", False) for a in ("invoke", "execute"))
        assert wrapped == (idname not in U.NOT_COUNTED), idname


def test_a_click_counts_once_for_its_function(usage):
    assert bpy.ops.fresing.workspace_refresh() == {"FINISHED"}         # a button no function names: only the button
    s = usage.state()
    assert s["buttons"] == {"fresing.workspace_refresh": 1} and s["functions"] == {}
    bpy.ops.fresing.next_hide()
    assert s["functions"] == {"panel.next": [1, 0]}
    bpy.ops.fresing.block_add(kind="MOTOR")
    assert s["functions"].get("animation.motor", [0])[0] == 1
    assert usage.record("fresing.panel_toggle") == ""                 # an opening is counted as one, not as a click


def test_a_button_inside_a_button_counts_once(usage):
    from fresing_render.blender import usage as mod

    def outer(self, context):
        bpy.ops.fresing.next_hide()
        return {"FINISHED"}

    call = mod._wrap_call(outer, "fresing.turntable", False)
    call(None, bpy.context)
    s = usage.state()
    assert s["buttons"] == {"fresing.turntable": 1} and s["functions"]["scene.turntable"][0] == 1
    assert s["saved"]["scene.turntable"] == pytest.approx(900.0)


def test_nothing_is_counted_with_tracking_off_or_in_a_tool_run(usage, monkeypatch):
    usage.state()["track"] = False
    bpy.ops.fresing.next_hide()
    assert usage.state()["buttons"] == {}
    usage.state()["track"] = True
    monkeypatch.setenv(U.OFF_ENV, "1")
    bpy.ops.fresing.next_hide()
    assert usage.state()["buttons"] == {}
    monkeypatch.delenv(U.OFF_ENV)
    monkeypatch.delenv(U.TEST_ENV)
    bpy.ops.fresing.next_hide()                                          # a background run: not counted
    assert usage.state()["buttons"] == {}


def test_opening_a_panel_counts_for_it(usage):
    from fresing_render.blender import panels
    panels.OPEN.discard("FRESING_PT_looks")
    bpy.ops.fresing.panel_toggle(name="FRESING_PT_looks")                # opens
    bpy.ops.fresing.panel_toggle(name="FRESING_PT_looks")                # folds: not a use
    assert usage.state()["panels"]["FRESING_PT_looks"][0] == 1


def test_the_file_is_written_and_a_broken_one_never_stops_the_app(usage):
    bpy.ops.fresing.next_hide()
    assert usage.save()
    data = json.load(open(usage.path(), encoding="utf-8"))
    assert data["buttons"] == {"fresing.next_hide": 1}
    with open(usage.path(), "w", encoding="utf-8") as fh:
        fh.write("{broken")
    usage.forget()
    assert usage.state() == U.fresh() and os.path.exists(usage.path() + ".broken")


def test_hide_goes_on_top_of_the_workspace_and_never_hides_what_the_project_uses(usage, monkeypatch):
    from fresing_render.blender import workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    assert _polls("FRESING_PT_xray")
    s = usage.state()
    s["sessions"] = 20
    usage.project_changed(sc)
    first = usage.prompt()
    assert first in F.FUNCTIONS[next(iter(U.panel_functions(first)))].panel
    usage._S["prompt"] = "FRESING_PT_xray"                               # ask about X-ray look
    bpy.ops.fresing.usage_declutter(choice="hide")
    assert not _polls("FRESING_PT_xray") and usage.prompt() == ""
    assert "looks.xray" in workspaces.PERSONAL["hide"]
    monkeypatch.setattr(workspaces, "used_functions", lambda scene: {"looks.xray": ("looks", "an X-ray part")})
    usage.apply_personal(sc)                                             # a project that uses it shows it
    assert _polls("FRESING_PT_xray")
    monkeypatch.undo()
    usage.apply_personal(sc)
    assert not _polls("FRESING_PT_xray")
    workspaces.switch(sc, "Full access")                                 # Full access shows everything
    assert _polls("FRESING_PT_xray")
    workspaces.switch(sc, "All functions")
    bpy.ops.fresing.usage_reset()
    assert _polls("FRESING_PT_xray") and usage.state()["hidden"] == []


def test_one_question_per_session(usage):
    s = usage.state()
    s["sessions"] = 30
    usage.project_changed(bpy.context.scene)
    p = usage.prompt()
    assert p
    bpy.ops.fresing.usage_declutter(choice="later")
    usage.project_changed(bpy.context.scene)                             # another project, same session: no new one
    assert usage.prompt() == "" and p in s["declutter"]["asked"]


def test_the_bar_draws_and_a_favourite_opens_its_place(usage):
    from fresing_render.blender import panels
    s = usage.state()
    s["functions"] = {"looks.decals": [4, 1], "help.pc_check": [3, 1]}
    usage.start()
    assert usage.bar(bpy.context.scene) == ["looks.decals", "help.pc_check"]
    assert usage.label("looks.decals") == "Logos & stickers"
    assert bpy.types.FRESING_PT_favourites.poll(bpy.context)
    panels.OPEN.discard("FRESING_PT_decals")
    assert usage.go(bpy.context, "looks.decals") == "shown"
    assert panels.is_open("FRESING_PT_decals") and bpy.context.window_manager.fresing_tab == "3"
    usage._end_go()
    bpy.context.window_manager.fresing_tab = "ALL"


def test_profile_export_and_import(usage, tmp_path):
    from fresing_render.blender import ops_usage, workspaces
    sc = bpy.context.scene
    s = usage.state()
    s["functions"] = {"scene.turntable": [5, 1]}
    usage.pin("scene.still", True)
    s["hidden"] = list(U.panel_functions("FRESING_PT_xray"))
    usage.apply_personal(sc)
    path = ops_usage.export_profile(sc, "Team profile", with_counts=False)
    data = json.load(open(path, encoding="utf-8"))
    assert data["favourites"]["pins"] == ["scene.still"] and "usage" not in data and "looks.xray" in data["hide"]
    assert workspaces.name_of(sc) == "Team profile"
    outside = tmp_path / "from a colleague.json"
    d = dict(data, name="Colleague", favourites={"on": True, "size": 7, "pins": ["help.pc_check"]},
             usage={"functions": {"looks.decals": [9, 3]}, "sessions": 3})
    outside.write_text(json.dumps(d), encoding="utf-8")
    assert ops_usage.import_profile(sc, str(outside), with_counts=False) == "Colleague"
    assert workspaces.name_of(sc) == "Colleague" and s["bar"]["pins"] == ["help.pc_check"] and s["bar"]["size"] == 7
    assert "looks.decals" not in s["functions"]
    lib = json.load(open(workspaces.library(force=True)["Colleague"][0], encoding="utf-8"))
    assert "usage" not in lib                                            # the library copy carries no counts
    assert "usage" not in sc.fresing.ws_data
    ops_usage.import_profile(sc, str(outside), with_counts=True)
    assert s["functions"]["looks.decals"][0] == 9
    workspaces.switch(sc, "All functions")


def test_my_usage_window_draws(usage):
    from fresing_render.blender import ops_usage
    s = usage.state()
    s["functions"] = {"scene.turntable": [5, 1]}
    s["saved"] = {"scene.turntable": 4500.0}
    s["stages"] = {"looks": 600.0, "render": 120.0}

    class Layout:                                   # a stand-in that takes every call (no window in a test)
        def __getattr__(self, name):
            return lambda *a, **k: self

        def __setattr__(self, name, value):
            pass

    ops_usage.draw_window(Layout(), bpy.context)
    wm = bpy.context.window_manager
    wm.fresing_usage_bar_size = 7
    assert s["bar"]["size"] == 7 and wm.fresing_usage_track


def test_counting_costs_next_to_nothing_per_click(usage):
    """The hook's cost per click (printed for the report): the same button with and without counting."""
    n = 2000

    def per_click():
        t0 = time.perf_counter()
        for _ in range(n):
            bpy.ops.fresing.next_hide()                                  # the same flag each time: no growing work
        return (time.perf_counter() - t0) / n

    per_click()
    os.environ[U.OFF_ENV] = "1"
    off = per_click()
    os.environ.pop(U.OFF_ENV)
    on = per_click()
    t0 = time.perf_counter()
    for _ in range(n):
        usage.record("fresing.block_add")
    rec = (time.perf_counter() - t0) / n
    print(f"\nusage cost per click: button {off * 1000:.3f} ms without counting, {on * 1000:.3f} ms with; "
          f"record() alone {rec * 1000:.4f} ms")
    assert rec < 0.002                                                   # well under 2 ms (it is ~0.02 ms)
