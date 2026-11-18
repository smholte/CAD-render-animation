"""About Fresing Render in Blender (task 0206): the operators, the menus, the copy that opens in a text program, and
Blender's own extension sync switched off once (and only once)."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("about")
    os.environ["FRESING_EXT_SYNC_FILE"] = str(d / "fresing_ext_sync.json")
    fresing_render.register()
    yield
    fresing_render.unregister()
    os.environ.pop("FRESING_EXT_SYNC_FILE", None)


def test_operators_and_menus():
    from fresing_render.blender import about, lock, ui_topbar
    assert ui_topbar._has("fresing.about") and ui_topbar._has("fresing.about_open")
    assert "fresing.about" in ui_topbar.entries()
    assert about._draw_help in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
    assert {"fresing.about", "fresing.about_open"} <= lock.ALLOWED          # works in the Client view too


def test_tooltips():
    for name in ("about", "about_open"):
        assert getattr(bpy.ops.fresing, name).get_rna_type().description
    from fresing_render.blender import about
    tip = about.FRESING_OT_about_open.description(None, type("P", (), {"which": "NOTICES"})())
    assert "offline" in tip and "Third-party" not in tip.lower() or "others made" in tip


def test_each_button_opens_a_copy_as_text(monkeypatch):
    from fresing_render.blender import about, files
    opened = []
    monkeypatch.setattr(files, "open_path", lambda p: opened.append(p))
    for which in ("LICENCE", "NOTICES", "COMPANY", "TEXTS"):
        assert bpy.ops.fresing.about_open("EXEC_DEFAULT", which=which) == {"FINISHED"}
    assert len(opened) == 4
    assert all(p.endswith(".txt") for p in opened[:3]) and os.path.isdir(opened[3])
    assert "GNU GENERAL PUBLIC LICENSE" in open(opened[0], encoding="utf-8").read()


def test_a_missing_file_is_reported_not_a_crash(monkeypatch, tmp_path):
    from fresing_render.blender import about, files
    monkeypatch.setattr(about, "package_dir", lambda: str(tmp_path))
    monkeypatch.setattr(files, "open_path", lambda p: pytest.fail("opened something"))
    with pytest.raises(RuntimeError, match="missing from this install"):      # an operator's error report
        bpy.ops.fresing.about_open("EXEC_DEFAULT", which="LICENCE")


def test_the_dialog_draws():
    from fresing_render.blender import about
    class L:                                  # a layout that accepts everything
        def __getattr__(self, name):
            return lambda *a, **k: L()
    about.FRESING_OT_about.draw(type("O", (), {"layout": L()})(), bpy.context)


def test_extension_sync_is_switched_off_once(tmp_path, monkeypatch):
    from fresing_render.blender import ext_sync
    monkeypatch.setenv(ext_sync.FILE_ENV, str(tmp_path / "once.json"))
    bpy.ops.wm.read_factory_settings()
    remote = [r for r in bpy.context.preferences.extensions.repos if r.use_remote_url]
    assert remote and all(r.use_sync_on_startup for r in remote), "Blender's default changed: the test needs a start state"
    assert ext_sync.synced()
    changed = ext_sync.switch_off_once()
    assert changed and not ext_sync.synced()
    remote[0].use_sync_on_startup = True                  # the user turns it back on
    assert ext_sync.switch_off_once() == []               # … and the app does not switch it off again
    assert ext_sync.synced()
