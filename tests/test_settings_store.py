"""Every Fresing setting kept over a restart (task 0283, ``blender/settings_store.py``): the preferences read from the
app's own file at the start, written when they change, the old values moved, a damaged file."""

import json
import os

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import settings_file as sf  # noqa: E402

# one setting of each tab of the Settings window, changed from its default
CHANGES = {
    "default_rule_set": "Offshore",            # General
    "hover_highlight": False,                  # General
    "new_project_name": "empty",               # General (task 0291)
    "default_workspace": "CNC milling",        # General
    "library_path": "C:/Läbrary folder/",      # General
    "keep_sections": True,                     # Side panel
    "keep_howto": True,                        # Side panel
    "lesson_button": "D",                      # Lessons
    "lesson_colour": (0.9, 0.1, 0.4),          # Lessons
    "lesson_play_on": True,                    # Lessons
    "backups_on": False,                       # Backups
    "backup_minutes": 12,                      # Backups
    "backup_days": 0,                          # Backups
    "check_updates": False,                    # Updates
    "live_preview": True,                      # a button's remembered choice
    "settings_tab": "backups",                 # the Settings window's last tab
}


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("settings store")
    os.environ["FRESING_SETTINGS_FILE"] = str(d / "config é" / sf.FILE_NAME)
    os.environ["FRESING_USAGE_FILE"] = str(d / "fresing_usage.json")
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()
    for k in ("FRESING_SETTINGS_FILE", "FRESING_USAGE_FILE"):
        os.environ.pop(k, None)


@pytest.fixture()
def store():
    from fresing_render.blender import prefs, settings_store
    path = settings_store.path()
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))
    _defaults(prefs.get())
    settings_store.forget()
    yield settings_store
    _defaults(prefs.get())
    settings_store.forget()


def _defaults(p):
    from fresing_render.blender import settings_store
    for name, kind in settings_store.spec().items():
        setattr(p, name, kind.default)


def _restart(store):
    """As a new start with the app template: Blender gives the defaults, only the file remembers."""
    from fresing_render.blender import prefs
    _defaults(prefs.get())
    store.forget()
    assert store.load()


def _get(p, name):
    v = getattr(p, name)
    return tuple(round(float(x), 6) for x in v) if name == "lesson_colour" else v


def test_every_preference_is_in_the_file_but_the_left_panels_own():
    from fresing_render.blender import prefs, settings_store
    names = {p.identifier for p in prefs.FRESING_AP_prefs.bl_rna.properties} - {"rna_type", "bl_idname"}
    spec = settings_store.spec()
    assert set(spec) == names - set(settings_store.ELSEWHERE)
    assert set(settings_store.ELSEWHERE) <= names                      # kept in fresing_left.json (task 0278)
    assert set(CHANGES) <= set(spec)
    assert spec["lesson_button"].items == ("C", "D") and spec["backup_minutes"].min == 1
    assert spec["lesson_colour"].type == "colour" and spec["lesson_colour"].size == 3


def test_a_change_of_each_tab_survives_a_restart(store):
    from fresing_render.blender import prefs
    assert store.load()
    p = prefs.get()
    for name, value in CHANGES.items():
        setattr(p, name, value)
    assert store.save()
    assert not store.save()                                           # nothing new: nothing written
    _restart(store)
    p = prefs.get()
    for name, value in CHANGES.items():
        assert sf.same(_get(p, name), value), name
    data = json.load(open(store.path(), encoding="utf-8"))
    assert set(data["settings"]) == set(CHANGES)                       # only what the user changed


def test_a_setting_put_back_to_its_default_is_kept_as_default(store):
    from fresing_render.blender import prefs
    store.load()
    p = prefs.get()
    p.keep_sections = True
    store.save()
    p.keep_sections = False
    store.save()
    _restart(store)
    assert prefs.get().keep_sections is False
    assert json.load(open(store.path(), encoding="utf-8"))["settings"] == {}


def test_the_timer_loads_first_then_saves_a_change(store):
    from fresing_render.blender import prefs
    with open(store.path(), "w", encoding="utf-8") as fh:
        json.dump({"format": sf.FORMAT, "version": 1, "settings": {"backup_keep": 9}}, fh)
    assert store.sync() == store.TICK
    p = prefs.get()
    assert p.backup_keep == 9
    p.lesson_part = "1"
    store.sync()
    got = json.load(open(store.path(), encoding="utf-8"))["settings"]
    assert got == {"backup_keep": 9, "lesson_part": "1"}


def test_the_old_values_are_moved_at_the_first_start(store):
    """No file yet (the first start of this version): what Blender still has is written, so nothing is lost."""
    from fresing_render.blender import prefs
    p = prefs.get()
    p.backup_minutes = 20
    p.lesson_section = "4"
    assert not os.path.exists(store.path())
    assert store.load()
    assert json.load(open(store.path(), encoding="utf-8"))["settings"] == {"backup_minutes": 20, "lesson_section": "4"}
    _restart(store)
    assert prefs.get().backup_minutes == 20 and prefs.get().lesson_section == "4"


def test_a_damaged_file_gives_the_defaults_and_a_note_and_the_app_goes_on(store):
    from fresing_render.blender import prefs, ui_settings
    with open(store.path(), "w", encoding="utf-8") as fh:
        fh.write('{"format": "fresing-settings", "version": 1, "settings": {"keep_sections": tru')
    prefs.get().keep_sections = True                     # whatever was in memory: the defaults are used
    store.forget()
    assert store.load()
    assert len(store.notes()) == 1 and "damaged" in store.notes()[0]
    folder = os.listdir(os.path.dirname(store.path()))
    assert len([f for f in folder if ".broken-" in f]) == 1
    assert sf.read(store.path(), store.spec()).notes == []           # written again, readable
    # the note shows on Settings > General
    shown = []

    class Layout:
        alert = False
        active = True

        def __getattr__(self, name):
            return lambda *a, **k: (shown.append(k.get("text", "")) if name == "label" else None) or Layout()
    ui_settings.draw_general(Layout(), bpy.context)
    assert any("damaged" in t for t in shown)
    assert any("kept for you" in t for t in shown)


def test_a_wrong_value_is_left_at_its_default(store):
    from fresing_render.blender import prefs
    with open(store.path(), "w", encoding="utf-8") as fh:
        json.dump({"format": sf.FORMAT, "version": 1, "settings": {"backup_minutes": 999, "keep_howto": True}}, fh)
    store.load()
    p = prefs.get()
    assert p.backup_minutes == 5 and p.keep_howto is True
    assert len(store.notes()) == 1 and "backup_minutes" in store.notes()[0]


def test_nothing_is_read_or_written_in_a_background_blender_without_the_test_file(store, monkeypatch):
    from fresing_render.blender import prefs
    monkeypatch.delenv("FRESING_SETTINGS_FILE")
    assert bpy.app.background
    assert not store.usable()
    assert not store.load()
    prefs.get().keep_sections = True
    assert not store.save()
    assert store.sync() is None
