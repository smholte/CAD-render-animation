"""Task 0278: Live preview and Build & play only on the left panel; Favourites folds like the other left sections and
every left section keeps its fold over a restart (a small file in Blender's settings folder – Blender does not keep an
extension's own preferences over a restart while the app template is on)."""

import inspect
import json
import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import functions as F  # noqa: E402
from fresing_render.core import places  # noqa: E402
from fresing_render.core import usage as U  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("left")
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_USAGE_FILE"] = str(d / U.FILE_NAME)
    os.environ["FRESING_LEFT_STORE"] = str(d / "fresing_left.json")
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield d / "fresing_left.json"
    fresing_render.unregister()
    for k in ("FRESING_WORKSPACES_DIR", "FRESING_USAGE_FILE", "FRESING_LEFT_STORE"):
        os.environ.pop(k, None)


def _restart(panels, ui_left):
    """What a new start of the app has: nothing in memory, only the file."""
    panels.OPEN.clear()
    panels.OPEN.update(panels.DEFAULT_OPEN)
    panels._LEFT_DONE.clear()
    ui_left._SYNCED.clear()


def test_favourites_has_the_apps_title_row_with_the_fold_arrow():
    from fresing_render.blender import panels
    assert "FRESING_PT_favourites" in panels.LEFT
    assert "FRESING_PT_favourites" not in panels._PLAIN            # the app draws its title row (fold arrow)
    assert "FRESING_PT_favourites" in panels.DEFAULT_OPEN          # open for a new user
    cls = bpy.types.FRESING_PT_favourites
    assert hasattr(cls, "draw_header") and hasattr(cls, "draw_header_preset")


def test_a_left_sections_fold_is_kept_over_a_restart(addon):
    from fresing_render.blender import panels, ui_left
    _restart(panels, ui_left)
    names = ("FRESING_PT_favourites", "FRESING_PT_hub", "FRESING_PT_lesson", "FRESING_PT_workspace")
    before = {n: panels.is_open(n) for n in names}
    for n in names:
        assert bpy.ops.fresing.panel_toggle(name=n) == {"FINISHED"}
    want = {n: not before[n] for n in names}
    assert json.loads(addon.read_text(encoding="utf-8"))["open"] == want
    _restart(panels, ui_left)
    assert {n: panels.is_open(n) for n in names} == want            # the first look puts them back
    panels.on_load(bpy.context.scene)                                # and so does every project that opens
    assert {n: panels.is_open(n) for n in names} == want
    for n in names:                                                  # back as they were
        bpy.ops.fresing.panel_toggle(name=n)


def test_only_the_users_click_is_remembered(addon):
    from fresing_render.blender import panels, ui_left
    ui_left.store_set(open={})
    panels.open_to("FRESING_PT_lesson")                              # a lesson or a test opens it: not kept
    panels.set_open("FRESING_PT_hub", False)
    assert ui_left.store().get("open") == {}


def test_the_left_panels_own_fold_and_whats_next_are_kept_too(addon):
    from fresing_render.blender import prefs, ui_left
    p = prefs.get()
    folded = p.next_folded
    assert bpy.ops.fresing.next_fold() == {"FINISHED"}
    assert ui_left.store()["next_folded"] == (not folded)
    p.next_folded, p.left_folded = folded, False                    # what a fresh start reads from Blender …
    ui_left.store_set(folded=True, width=300)
    ui_left._SYNCED.clear()
    assert ui_left.folded() and ui_left.next_folded() == (not folded) and p.left_width == 300   # … the file wins
    ui_left.store_set(folded=False, next_folded=folded, width=240)
    ui_left._SYNCED.clear()
    assert not ui_left.folded()


def test_a_broken_file_gives_the_defaults(addon):
    from fresing_render.blender import ui_left
    addon.write_text("{not json", encoding="utf-8")
    assert ui_left.store() == {}
    addon.write_text(json.dumps({"open": {"FRESING_PT_hub": "yes", "FRESING_PT_lesson": False}, "folded": 1,
                                 "width": True}), encoding="utf-8")
    assert ui_left.store() == {"open": {"FRESING_PT_lesson": False}}
    ui_left.store_set(open={})


def test_the_folded_favourites_header_says_a_question_waits(monkeypatch):
    from fresing_render.blender import panels, ui_usage, usage

    class Row:
        def __init__(self, log):
            self.log, self.alignment = log, ""

        def row(self, **_k):
            return self

        def label(self, text="", icon="NONE"):
            self.log.append(("label", text))

        def operator(self, idname, **_k):
            self.log.append(("op", idname))

    class Stand:
        def __init__(self):
            self.log = []
            self.layout = Row(self.log)

    monkeypatch.setattr(usage, "prompt", lambda: "FRESING_PT_cutaway")
    for opened in (True, False):
        panels.set_open("FRESING_PT_favourites", opened)
        st = Stand()
        ui_usage.FRESING_PT_favourites.draw_header_preset(st, bpy.context)
        assert (("label", ui_usage.QUESTION) in st.log) == (not opened)
        assert ("op", "fresing.usage_window") in st.log                # the gear stays on the right of the header
    panels.set_open("FRESING_PT_favourites", True)


def test_live_preview_and_build_and_play_are_only_on_the_left():
    from fresing_render.blender import panels, ui, ui_left, ui_motion
    out = inspect.getsource(panels.body_of(ui.FRESING_PT_output))
    anim = inspect.getsource(panels.body_of(ui_motion.FRESING_PT_animation))
    assert "fresing.preview" not in out and "fresing.anim_build" not in anim
    assert "fresing.anim_clear" in anim                              # the X stays, beside the Built line
    quick = inspect.getsource(ui_left.FRESING_PT_left_quick.draw)
    assert quick.count("fresing.preview") == 2 and quick.count("fresing.anim_build") == 2      # open and the strip
    assert F.FUNCTIONS["animation.build"].panel == "FRESING_PT_left_quick"


def test_the_section_count_is_written_from_the_list():
    from fresing_render.blender import prefs
    n = len(places.SECTIONS)
    assert n == 8
    desc = prefs.get().bl_rna.properties["keep_sections"].description
    assert f"sections 1 to {n} start folded" in desc
    tab = bpy.types.WindowManager.bl_rna.properties["fresing_tab"].description
    assert f"all {n}" in tab
