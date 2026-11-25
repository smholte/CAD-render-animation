"""Task 0273: every built-in material has tags (kind, colour family, looks) and a one-line description."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fresing_render.core import materials_lib as ml  # noqa: E402

# Takes no colour from the group, yet its own colour is unknown (the user's Blender material).
ANY_WITHOUT_NEEDS_COLOR = {"blender_material"}


def test_every_material_has_tags_and_a_description():
    assert set(ml.TAGS) == set(ml.MATERIALS)
    assert set(ml.DESCRIPTIONS) == set(ml.MATERIALS)


def test_tag_values_are_known():
    for key, (kind, colour, looks) in ml.TAGS.items():
        assert kind in ml.KINDS, key
        assert colour in ml.COLOURS, key
        assert isinstance(looks, tuple) and looks, key
        assert len(set(looks)) == len(looks), key
        for look in looks:
            assert look in ml.LOOKS, (key, look)


def test_any_colour_follows_needs_color():
    for key, spec in ml.MATERIALS.items():
        colour = ml.TAGS[key][1]
        if spec.get("needs_color"):
            assert colour == "any", key
        elif key not in ANY_WITHOUT_NEEDS_COLOR:
            assert colour != "any", key


def test_looks_follow_the_settings():
    for key, spec in ml.MATERIALS.items():
        looks = ml.TAGS[key][2]
        if spec.get("transmission", 0) >= 0.5 or "see-through" in spec.get("label", ""):
            assert "see-through" in looks, key
        if spec.get("emission"):
            assert "glowing" in looks, key
        if "glowing" in looks:
            assert spec.get("emission"), key


def test_descriptions_are_one_plain_line():
    for key, text in ml.DESCRIPTIONS.items():
        assert text and "\n" not in text, key
        assert len(text) <= 110, (key, len(text))
        assert not text.endswith("."), key
        assert text != ml.MATERIALS[key].get("label"), key


def test_label_tables_cover_their_tuples():
    assert set(ml.COLOUR_LABELS) == set(ml.COLOURS)
    assert set(ml.LOOK_LABELS) == set(ml.LOOKS)
    assert len(set(ml.KINDS)) == len(ml.KINDS)


def test_helpers_and_fallbacks():
    assert ml.tags("steel_turned")[0] == "Steel"
    assert ml.tags("no_such") == ("Other", "any", ("matte",))
    assert ml.describe("cast_iron") == ml.DESCRIPTIONS["cast_iron"]
    assert ml.describe("no_such") == "no_such"
