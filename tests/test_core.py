import json

from fresing_render.core import materials_lib, presets, ral
from fresing_render.core import rules as R
from fresing_render.core.template import GroupLook, Scheme, Template


# ---- rules ------------------------------------------------------------------

def _facts(name, color=""):
    return R.facts_for(name, path=f"Machine#1/{name}#1", color=color, assembly="Machine")


def test_default_rules_sort_fasteners_by_finish():
    rules = R.default_rules()
    parts = [
        _facts("ISO 4017 M12 x 40 - 8.8 HDG"),
        _facts("DIN 912 M10x30 - 12.9"),
        _facts("ISO 4032 M12 A4"),
        _facts("DIN 125-A 13"),
        _facts("FRAME.WELDMENT", color="#F9A800"),
        _facts("COVER"),
    ]
    groups, counts, unmatched = R.classify(parts, rules)
    assert groups == [
        "Fasteners galvanized", "Fasteners black", "Fasteners stainless", "Fasteners default",
        "Colour #F9A800", R.FALLBACK_GROUP,
    ]
    assert unmatched == [5]
    assert sum(counts) == 5


def test_rule_order_first_match_wins():
    rules = [R.Rule("Covers", "name", "contains", "cov"), R.Rule("Everything", "name", "any")]
    g, _, _ = R.classify([_facts("BELT.COV"), _facts("FRAME")], rules)
    assert g == ["Covers", "Everything"]


def test_rule_ops():
    f = _facts("CONV.SIDE.GUIDE2")
    assert R._matches(R.Rule("x", "name", "starts", "conv"), f)
    assert R._matches(R.Rule("x", "name", "ends", "guide2"), f)
    assert R._matches(R.Rule("x", "name", "glob", "CONV.*GUIDE?"), f)
    assert R._matches(R.Rule("x", "name", "regex", r"side\.guide\d"), f)
    assert not R._matches(R.Rule("x", "name", "regex", r"[unclosed"), f)
    assert R._matches(R.Rule("x", "color", "none"), f)
    assert R._matches(R.Rule("x", "path", "contains", "machine#1"), f)
    assert not R._matches(R.Rule("x", "name", "contains", "", enabled=True), f)


def test_disabled_rule_is_skipped():
    rules = [R.Rule("A", "name", "any", enabled=False), R.Rule("B", "name", "any")]
    assert R.classify_one(_facts("X"), rules)[0] == "B"


def test_default_group_material():
    assert R.default_material_for_group("Fasteners black") == ("black_oxide", "")
    assert R.default_material_for_group("Colour #1A2B3C") == ("paint_satin", "#1A2B3C")
    assert R.default_material_for_group("Whatever")[0] == "paint_satin"


def test_rule_roundtrip():
    rules = R.default_rules()
    again = R.rules_from_list(json.loads(json.dumps(R.rules_to_list(rules))))
    assert again == rules


# ---- RAL / materials ---------------------------------------------------------

def test_ral_lookup_and_parse():
    assert ral.lookup("RAL 5010")[1] == "Gentian blue"
    assert ral.lookup("ral1003")[0] == "1003"
    assert ral.lookup("RAL 1234") is None
    label, rgb = ral.parse_colour("#f9a800")
    assert label == "#F9A800" and abs(rgb[0] - 0.976) < 0.01
    assert ral.parse_colour("nonsense") is None
    assert len(ral.RAL_CLASSIC) > 200


def test_material_library_consistency():
    for key, d in materials_lib.MATERIALS.items():
        assert d["category"] in materials_lib.CATEGORIES, key
        assert "label" in d
        if not d.get("needs_color"):
            assert "base_color" in d, key
    for group, (mat, _) in R.DEFAULT_GROUP_MATERIAL.items():
        assert mat in materials_lib.MATERIALS, group


# ---- presets -----------------------------------------------------------------

def test_screen_presets():
    assert (presets.compute("presentation", "hd").width, presets.compute("presentation", "hd").height) == (1920, 1080)
    s = presets.compute("presentation", "4k")
    assert (s.width, s.height) == (3840, 2160)
    s = presets.compute("social", "hd")
    assert (s.width, s.height) == (1080, 1920)
    s = presets.compute("square", "qhd")
    assert (s.width, s.height) == (1440, 1440)
    s = presets.compute("widescreen", "hd")
    assert s.height == 1080 and s.width == 2520
    s = presets.compute("presentation", "hd", orientation="portrait")
    assert (s.width, s.height) == (1080, 1920)


def test_paper_presets():
    s = presets.compute("brochure_a4", dpi=300)
    assert (s.width, s.height) == (2480, 3508)
    s = presets.compute("brochure_a4", dpi=300, orientation="landscape")
    assert (s.width, s.height) == (3508, 2480)
    s = presets.compute("poster_a3", dpi=300)
    assert (s.width, s.height) == (3508, 4961)
    s = presets.compute("flyer_a5", dpi=300)
    assert (s.width, s.height) == (1748, 2480)
    s = presets.compute("brochure_a4", dpi=300, bleed_mm=3)
    assert (s.width, s.height) == (2551, 3579)
    fx, fy = presets.bleed_fraction("brochure_a4", "auto", 3)
    assert 0.013 < fx < 0.015


def test_custom_preset():
    s = presets.compute("custom", custom_w=1234, custom_h=567)
    assert (s.width, s.height) == (1234, 567)


# ---- templates ----------------------------------------------------------------

def test_template_roundtrip(tmp_path):
    t = Template(name="Fresing standard")
    t.schemes.append(Scheme("Customer blue", {"Colour #F9A800": GroupLook("paint_gloss", "RAL 5010")}))
    t.output = {"format": "presentation", "resolution": "4k"}
    p = tmp_path / "t.json"
    t.save(str(p))
    again = Template.load(str(p))
    assert again.name == "Fresing standard"
    assert again.rules == t.rules
    assert again.schemes[0].looks["Colour #F9A800"].color == "RAL 5010"
    assert again.output["resolution"] == "4k"


def test_template_rejects_other_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    try:
        Template.load(str(p))
    except ValueError:
        return
    raise AssertionError("expected ValueError")
