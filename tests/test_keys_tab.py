"""Settings > Keys in Blender (task 0295, ``blender/keys.py``): the list is built from the live key lists, a changed
key goes into the keymap and survives a restart (the settings file of task 0283), a clash is refused or warns, Reset,
the key sheet, the ways in. The tab clicked in a real window and a key pressed there: tools/ui_test_settings.py."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import keys as K  # noqa: E402
from fresing_render.core import settings_file as sf  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("keys tab")
    os.environ["FRESING_SETTINGS_FILE"] = str(d / "config é" / sf.FILE_NAME)
    os.environ["FRESING_USAGE_FILE"] = str(d / "fresing_usage.json")
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    from fresing_render.blender import settings_store
    settings_store.forget()
    settings_store.load()
    yield
    fresing_render.unregister()
    for k in ("FRESING_SETTINGS_FILE", "FRESING_USAGE_FILE"):
        os.environ.pop(k, None)


@pytest.fixture()
def keys():
    from fresing_render.blender import keys as mod
    mod.reset()
    yield mod
    mod.reset()


def _bound(op, props=None):
    """(key, modifiers) of every add-on key the app would add for this operator."""
    from fresing_render.blender import lock
    return [(k, K.norm(m)) for _n, _sp, k, m, o, p in lock._wanted() if o == op and (props is None or p == props)]


def test_the_list_is_built_from_the_live_key_lists(keys, monkeypatch):
    from fresing_render.blender import lock
    rows = keys.rows()
    groups = {r.group for r in rows}
    assert groups == set(K.GROUP_KEYS)
    own = [r for r in rows if r.group == "own"]
    assert len(own) == len(lock.APP_KEYS)
    assert {r.id for r in own if r.id} == set(K.OWN)
    off = [r for r in rows if r.group == "off"]
    assert {r.key for r in off} == {lock.key_label(k, m) for _n, _sp, k, m, _w in lock.BLENDER_KEYS}
    # a new key in lock.py shows by itself
    monkeypatch.setattr(lock, "APP_KEYS", lock.APP_KEYS + (("Object Mode", "EMPTY", "J", {"shift": True},
                                                            "fresing.settings", {}),))
    monkeypatch.setattr(lock, "BLENDER_KEYS", lock.BLENDER_KEYS + (("Object Mode", "EMPTY", "Q", {"ctrl": True},
                                                                    "a new Blender thing"),))
    rows = keys.rows()
    assert any(r.group == "own" and r.key == "Shift+J" and r.what == "Fresing Settings" for r in rows)
    assert any(r.group == "off" and r.key == "Ctrl+Q" and r.what == "A new Blender thing" for r in rows)


def test_a_changed_key_is_in_the_keymap_list_and_survives_a_restart(keys):
    from fresing_render.blender import prefs, settings_store
    assert bpy.ops.fresing.key_change(id="render_image", key="F9", ctrl=True) == {"FINISHED"}
    assert ("F9", {"ctrl": True}) in _bound("fresing.key_render", {"animation": False})
    assert ("F12", {}) not in _bound("fresing.key_render", {"animation": False})
    row = next(r for r in keys.rows() if r.id == "render_image")
    assert row.key == "Ctrl+F9" and row.changed and row.default == "F12"
    # a restart: Blender forgets the preference, the settings file brings it back
    with open(settings_store.path(), encoding="utf-8") as fh:
        assert "key_changes" in fh.read()
    prefs.get().key_changes = ""
    settings_store.forget()
    assert settings_store.load()
    assert K.read_changes(prefs.get().key_changes) == {"render_image": ("F9", {"ctrl": True})}
    assert ("F9", {"ctrl": True}) in _bound("fresing.key_render", {"animation": False})


def test_the_keymap_gets_the_changed_key(keys):
    """The add-on keyconfig itself (Blender as a module has one; the app adds keys only with a window)."""
    from fresing_render.blender import lock
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon is None:
        pytest.skip("no add-on key settings in this Blender")
    try:
        keys.change("measure", "K", {"shift": True})
        lock._remove_keys()
        lock._add_keys()
        items = [(kmi.idname, kmi.type, kmi.shift) for _km, kmi in lock._KEYMAPS]
        assert ("fresing.measure_key", "K", 1) in items or ("fresing.measure_key", "K", True) in items
        assert not any(i == "fresing.measure_key" and t == "M" for i, t, _s in items)
    finally:
        lock._remove_keys()


def test_a_clash_with_a_fresing_key_is_refused_and_one_with_blender_warns(keys):
    from fresing_render.blender import lock
    res = keys.change("copy", "M", {})
    assert not res.ok and "Measure" in res.refusal
    assert keys.changes() == {}
    res = K.check_new("copy", "D", {"shift": True}, keys.own_now(), [("D", {"shift": True}, "Duplicate Objects")])
    assert res.ok and res.warnings
    # a swallowed Blender key given to a Fresing key is not swallowed any more: the user's key wins
    assert keys.change("copy", "D", {"shift": True}).ok
    swallowed = [(k, K.norm(m)) for n, _sp, k, m, o, _p in lock._wanted() if o == "fresing.blender_key"
                 and n == "Object Mode"]
    assert ("D", {"shift": True}) not in swallowed and ("D", {"alt": True}) in swallowed
    row = next(r for r in keys.rows() if r.group == "off" and r.key == "Shift+D")
    assert "Fresing" in row.note


def test_reset_one_and_all(keys):
    assert keys.change("paste", "B", {"ctrl": True}).ok
    assert keys.change("measure_all", "F8", {}).ok
    assert bpy.ops.fresing.key_reset(id="paste") == {"FINISHED"}
    assert set(keys.changes()) == {"measure_all"}
    assert bpy.ops.fresing.key_reset(id="") == {"FINISHED"}
    assert keys.changes() == {}
    assert ("M", {"alt": True}) in _bound("fresing.measure")


def test_the_key_sheet_and_the_ways_in(keys, tmp_path):
    from fresing_render.blender import ui_settings, ui_topbar
    keys.change("render_animation", "F10", {})
    path = keys.write_sheet(str(tmp_path / "sheet é.html"))
    with open(path, encoding="utf-8") as fh:
        page = fh.read()
    assert "F10" in page and "yours; was Ctrl+F12" in page and "Blender keys that still work" in page
    assert bpy.ops.fresing.key_sheet() == {"FINISHED"}
    assert os.path.isfile(keys.sheet_path())
    assert "keys" in ui_settings.KEYS
    assert "keys" in ui_settings.draw_all(bpy.context)
    assert "fresing.keys" in ui_topbar.entries()
    assert keys._draw_keys_help in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()
    assert bpy.ops.fresing.keys_blender() == {"FINISHED"}
    assert bpy.context.preferences.active_section == "KEYMAP"


def test_search_in_the_tab(keys):
    wm = bpy.context.window_manager
    wm.fresing_keys_search = "render"
    try:
        found = K.search(keys.rows(), wm.fresing_keys_search)
        assert found and all("render" in (r.what + r.where + r.note).lower() for r in found)
        assert "keys" in __import__("fresing_render.blender.ui_settings", fromlist=["x"]).draw_all(bpy.context)
    finally:
        wm.fresing_keys_search = ""
