"""Settings > Keys without Blender (task 0295, ``core/keys.py``): key names, stored changes, the clash rules, search,
the printable key sheet."""

import json

from fresing_render.core import keys as K


def test_labels_are_written_for_people():
    assert K.label("F12") == "F12"
    assert K.label("F12", {"ctrl": True}) == "Ctrl+F12"
    assert K.label("D", {"shift": True}) == "Shift+D"
    assert K.label("DEL", {"any": True}) == "Delete"
    assert K.label("NUMPAD_1") == "Numpad 1"
    assert K.label("ZERO", {"ctrl": True, "shift": True, "alt": True}) == "Ctrl+Shift+Alt+0"
    assert K.label("RIGHTMOUSE") == "Right mouse"


def test_any_modifier_answers_every_press():
    assert K.same(("X", {"any": True}), ("X", {"ctrl": True}))
    assert K.same(("X", {}), ("X", {}))
    assert not K.same(("X", {}), ("X", {"shift": True}))
    assert not K.same(("X", {}), ("Y", {}))


def test_changes_round_trip_and_defaults_are_left_out():
    ch = {"render_image": ("F9", {"ctrl": True}), "copy": ("C", {"ctrl": True})}   # copy = its default
    text = K.write_changes(ch)
    assert json.loads(text) == {"render_image": {"key": "F9", "ctrl": True}}
    assert K.read_changes(text) == {"render_image": ("F9", {"ctrl": True})}
    assert K.write_changes({}) == ""
    # the remove keys came with "any": the same key without modifiers is their default too
    assert K.write_changes({"remove_x": ("X", {})}) == ""


def test_a_bad_stored_text_never_fails():
    for text in ("", "not json", "[1, 2]", '{"nope": {"key": "K"}}', '{"copy": "K"}', '{"copy": {"key": 3}}',
                 '{"copy": {"key": "ESC"}}', '{"copy": {"key": "LEFT_CTRL"}}', "null"):
        assert K.read_changes(text) == {}, text
    assert K.read_changes('{"copy": {"key": "K", "ctrl": "yes"}}') == {"copy": ("K", {})}


def test_own_ids_match_their_defaults():
    for kid, (op, key, mods, _what) in K.OWN.items():
        assert K.own_id(op, key, mods) == kid
        assert K.own_key(kid, {}) == (key, mods)
    assert K.own_id("fresing.view_menu", "RIGHTMOUSE", {}) == ""


def _own():
    return {kid: K.own_key(kid, {}) for kid in K.OWN}


def test_a_key_another_fresing_key_has_is_refused():
    res = K.check_new("render_image", "M", {}, _own(), [])
    assert not res.ok and "Measure" in res.refusal
    # the remove keys take every modifier: Ctrl+X is theirs too
    assert not K.check_new("copy", "X", {"ctrl": True}, _own(), []).ok
    # its own key again is fine
    assert K.check_new("render_image", "F12", {}, _own(), []).ok


def test_reserved_keys_and_modifiers_alone_are_refused():
    for key in ("ESC", "RET", "LEFTMOUSE", "MIDDLEMOUSE", "WHEELUPMOUSE"):
        assert not K.check_new("copy", key, {}, _own(), []).ok, key
    res = K.check_new("copy", "LEFT_SHIFT", {}, _own(), [])
    assert not res.ok and "alone" in res.refusal
    assert not K.check_new("nope", "K", {}, _own(), []).ok


def test_a_blender_key_warns_but_is_taken():
    taken = [("D", {"shift": True}, "Duplicate Objects"), ("K", {}, "Keyframe menu")]
    res = K.check_new("copy", "D", {"shift": True}, _own(), taken)
    assert res.ok and len(res.warnings) == 1 and "Duplicate Objects" in res.warnings[0]
    assert K.check_new("copy", "D", {}, _own(), taken).warnings == []


def test_search_finds_by_words_and_key():
    rows = [K.Row("own", "Render the picture", "F12"), K.Row("kept", "Hide what is selected", "H"),
            K.Row("off", "Duplicate", "Shift+D", note="works in Full access")]
    assert [r.key for r in K.search(rows, "render")] == ["F12"]
    assert [r.key for r in K.search(rows, "f12")] == ["F12"]
    assert [r.key for r in K.search(rows, "full access")] == ["Shift+D"]
    assert K.search(rows, "") == rows
    assert K.search(rows, "nothing like it") == []


def test_the_key_sheet_has_every_group_and_marks_a_changed_key():
    rows = [K.Row(g, f"What {g} <does>", "Ctrl+K") for g in K.GROUP_KEYS]
    rows.append(K.Row("own", "Render the picture", "F9", id="render_image", default="F12"))
    page = K.sheet_html(rows, "0.2.999", "2026-11-25")
    for _g, title in K.GROUPS:
        assert K.html.escape(title) in page
    assert "&lt;does&gt;" in page and "<does>" not in page
    assert "yours; was F12" in page
    assert "@page { size: A4" in page and "0.2.999" in page
    assert page.startswith("<!doctype html>")
