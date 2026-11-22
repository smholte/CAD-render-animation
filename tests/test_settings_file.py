"""The app's own settings file (task 0283, ``core/settings_file.py``): read, write, defaults, versions, damage."""

import json
import os

import pytest

from fresing_render.core import settings_file as sf

SPEC = {
    "keep_sections": sf.Kind("bool", False),
    "backup_minutes": sf.Kind("int", 5, 1, 60),
    "default_rule_set": sf.Kind("str", "Standard"),
    "lesson_button": sf.Kind("enum", "C", items=("C", "D")),
    "lesson_colour": sf.Kind("colour", (0.278, 0.608, 0.161), 0.0, 1.0, size=3),
    "scale": sf.Kind("float", 1.0, 0.5, 2.0),
}
DEFAULTS = {n: k.default for n, k in SPEC.items()}


def _file(path, settings, version=1, fmt=sf.FORMAT):
    path.write_text(json.dumps({"format": fmt, "version": version, "settings": settings}), encoding="utf-8")


def test_a_missing_file_gives_nothing_and_no_note(tmp_path):
    res = sf.read(str(tmp_path / sf.FILE_NAME), SPEC)
    assert (res.found, res.values, res.notes) == (False, {}, [])


def test_written_and_read_back(tmp_path):
    path = str(tmp_path / "a folder é" / sf.FILE_NAME)
    values = dict(DEFAULTS, keep_sections=True, backup_minutes=12, default_rule_set="Offshore – grün",
                  lesson_button="D", lesson_colour=(1.0, 0.5, 0.0), scale=1.25)
    sf.write(path, values, SPEC)
    res = sf.read(path, SPEC)
    assert res.found and not res.notes and res.version == sf.VERSION
    assert res.values == {k: v for k, v in values.items()}
    assert not [f for f in os.listdir(os.path.dirname(path)) if f.endswith(".tmp")]


def test_only_changed_values_are_written(tmp_path):
    path = tmp_path / sf.FILE_NAME
    sf.write(str(path), dict(DEFAULTS, backup_minutes=10, lesson_colour=(0.2780001, 0.608, 0.161)), SPEC)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"format": sf.FORMAT, "version": sf.VERSION, "settings": {"backup_minutes": 10}}


@pytest.mark.parametrize("body", [b"", b"{", b"\xff\xfe nonsense", b"[]", b'{"format": "other", "version": 1}',
                                  b'{"format": "fresing-settings", "settings": {}}',
                                  b'{"format": "fresing-settings", "version": true, "settings": {}}',
                                  b'{"format": "fresing-settings", "version": 1, "settings": []}',
                                  b'{"format": "fresing-settings", "version": 1, "settings": {"scale": NaN}}'])
def test_a_damaged_file_gives_the_defaults_a_copy_and_one_note(tmp_path, body):
    path = tmp_path / sf.FILE_NAME
    path.write_bytes(body)
    res = sf.read(str(path), SPEC)
    assert res.found and res.values == {} and len(res.notes) == 1
    assert "damaged" in res.notes[0] and "defaults" in res.notes[0]
    copies = [f for f in os.listdir(tmp_path) if f.startswith("fresing_settings.broken-")]
    assert len(copies) == 1 and (tmp_path / copies[0]).read_bytes() == body
    assert copies[0] in res.notes[0]


def test_two_damaged_reads_keep_two_copies(tmp_path):
    path = tmp_path / sf.FILE_NAME
    path.write_bytes(b"{")
    sf.read(str(path), SPEC)
    sf.read(str(path), SPEC)
    assert len([f for f in os.listdir(tmp_path) if ".broken-" in f]) == 2


@pytest.mark.parametrize("name, value", [("keep_sections", 1), ("backup_minutes", 0), ("backup_minutes", 61),
                                         ("backup_minutes", "5"), ("backup_minutes", True), ("default_rule_set", 3),
                                         ("default_rule_set", "a\nb"), ("lesson_button", "X"),
                                         ("lesson_colour", [1, 2, 3]), ("lesson_colour", [0.1, 0.2]),
                                         ("scale", 3.0)])
def test_a_wrong_value_is_left_out_with_a_note_the_rest_is_read(tmp_path, name, value):
    path = tmp_path / sf.FILE_NAME
    good = ("scale", 1.5) if name == "keep_sections" else ("keep_sections", True)
    _file(path, {name: value, good[0]: good[1], "a_later_setting": 1})
    res = sf.read(str(path), SPEC)
    assert name not in res.values
    assert res.values == {good[0]: good[1]} and res.extra == {"a_later_setting": 1}
    assert len(res.notes) == 1 and name in res.notes[0]
    assert not [f for f in os.listdir(tmp_path) if ".broken-" in f]      # not damaged: no copy


def test_a_whole_float_is_a_whole_number(tmp_path):
    path = tmp_path / sf.FILE_NAME
    _file(path, {"backup_minutes": 10.0})
    assert sf.read(str(path), SPEC).values == {"backup_minutes": 10}


def test_a_newer_file_keeps_what_this_version_does_not_know(tmp_path):
    path = tmp_path / sf.FILE_NAME
    _file(path, {"keep_sections": True, "locations": {"Company": "X:/lib"}}, version=sf.VERSION + 1)
    res = sf.read(str(path), SPEC)
    assert res.values == {"keep_sections": True} and res.extra == {"locations": {"Company": "X:/lib"}}
    assert not res.notes
    sf.write(str(path), dict(DEFAULTS, keep_sections=False), SPEC, res.extra)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["settings"] == {"locations": {"Company": "X:/lib"}}


def test_a_file_with_a_byte_order_mark_is_read(tmp_path):
    path = tmp_path / sf.FILE_NAME
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"format": sf.FORMAT, "version": 1,
                                                    "settings": {"lesson_button": "D"}}).encode())
    assert sf.read(str(path), SPEC).values == {"lesson_button": "D"}


def test_a_failed_write_leaves_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / sf.FILE_NAME
    sf.write(str(path), dict(DEFAULTS, keep_sections=True), SPEC)
    before = path.read_bytes()

    def boom(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        sf.write(str(path), dict(DEFAULTS, backup_minutes=9), SPEC)
    assert path.read_bytes() == before
    assert os.listdir(tmp_path) == [sf.FILE_NAME]


def test_same_compares_like_blender_stores():
    assert sf.same((0.1, 0.2, 0.3), (0.1000000015, 0.2, 0.3))
    assert sf.same(5, 5) and not sf.same(5, True) and not sf.same("a", "b")
    assert not sf.same(1.0, 1.1)
