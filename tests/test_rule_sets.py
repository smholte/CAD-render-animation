"""Rule sets (task 0015): one naming scheme per company, chosen per project, switchable.

Core file format and library functions without Blender; then the project side in Blender:
copy Standard, edit, save, load in a new project; start empty; switch with hand assignments kept;
preview counts; library missing; old projects and old templates open unchanged; templates refer
to a rule set by name; renames; painted faces; operators and panels.
"""

import json
import os

import pytest

from fresing_render.core import rule_sets as RS
from fresing_render.core import rules as R

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")
FACES_A = os.path.join(HERE, "data", "test_faces_a.step")


# =============================================================================
# core: no Blender
# =============================================================================


def test_standard_is_the_default_rules_and_builtin_looks():
    std = RS.standard()
    assert std.builtin and std.name == "Standard"
    assert R.rules_to_list(std.rules) == R.rules_to_list(R.default_rules())
    assert std.looks == {} and std.renames == {}
    assert std.content() == {"rules": R.rules_to_list(R.default_rules()), "looks": {}, "renames": {}}


def test_file_roundtrip_keeps_everything(tmp_path):
    rs = RS.RuleSet("Fresing", [R.Rule("Plates RVS", "name", "contains", "RVS", note="mine")],
                    {"Plates RVS": ("stainless_brushed", ""), "Frame": ("paint_satin", "RAL 5010")},
                    {"Fasteners black": "Bolts black"}, "Our scheme")
    path = tmp_path / "x.json"
    rs.save(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[RS.MARKER] == 1 and data["name"] == "Fresing"
    assert data["groups"]["Frame"] == {"material": "paint_satin", "color": "RAL 5010"}
    again = RS.RuleSet.load(str(path))
    assert again.to_dict() == rs.to_dict()
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]           # no temporary file left behind
    with pytest.raises(ValueError):
        RS.RuleSet.from_dict({"fresing_render_template": 1})


def test_built_in_looks_do_not_count_as_own_looks():
    rs = RS.RuleSet("A", [], {"Fasteners stainless": ("stainless_brushed", "RAL 1000"),   # default; colour unused
                              "Seals & O-rings": ("rubber_black", ""),                    # default
                              "Colour #F9A800": ("paint_satin", "#F9A800"),              # default from the name
                              "Frame": ("paint_satin", "RAL 5010")})                      # own
    assert rs.own_looks() == {"Frame": ("paint_satin", "RAL 5010")}
    assert RS.RuleSet("B", [], {}).same_content(RS.RuleSet("C", [], {"Seals & O-rings": ("rubber_black", "")}))


def test_differences_are_counted_per_kind():
    a = RS.RuleSet("A", R.default_rules(), {"Frame": ("paint_satin", "RAL 5010")}, {"x": "y"})
    b = a.copy()
    assert RS.differences(a, b) == {"rules": 0, "looks": 0, "renames": 0}
    b.rules.insert(0, R.Rule("Seals", "name", "contains", "SEAL"))
    b.rules[3].enabled = False
    b.looks["Frame"] = ("paint_gloss", "RAL 5010")
    b.looks["Covers"] = ("paint_satin", "RAL 3000")
    b.renames = {}
    d = RS.differences(a, b)
    assert d == {"rules": 2, "looks": 2, "renames": 1}
    assert RS.describe_differences(d) == "2 rules, 2 group looks, 1 group name"
    c = a.copy()
    c.rules.reverse()                                       # same rules, other order
    assert RS.differences(a, c)["rules"] == 1


def test_names_and_file_names():
    assert RS.name_problem("") and RS.name_problem("   ")
    assert "built-in" in RS.name_problem("standard")
    assert "already" in RS.name_problem("Fresing", ["fresing"])
    assert RS.name_problem("Client B: Damen/Offshore") == ""
    assert RS.file_name("Client B: Damen/Offshore") == "Client B_ Damen_Offshore.json"
    assert RS.file_name("CON") == "_CON.json" and RS.file_name("x. ") == "x.json"
    assert len(RS.clean_name("x" * 100)) == RS.MAX_NAME


def test_library_folder_scan_save_rename_delete(tmp_path):
    lib = str(tmp_path / "Rule sets")
    assert RS.scan(lib) == {}
    RS.save_in(lib, RS.RuleSet("Fresing", [R.Rule("A", "name", "contains", "A")]))
    RS.save_in(lib, RS.RuleSet("Client B", []))
    (tmp_path / "Rule sets" / "notes.json").write_text('{"other": 1}', encoding="utf-8")   # not a rule set
    (tmp_path / "Rule sets" / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "Rule sets" / "fake.json").write_text(json.dumps(RS.standard().to_dict()), encoding="utf-8")
    assert list(RS.scan(lib)) == ["Client B", "Fresing"]          # 'Standard' is always the built-in one
    with pytest.raises(ValueError):
        RS.save_in(lib, RS.standard())
    # saving again overwrites the same file, also when the file was renamed by hand
    os.rename(os.path.join(lib, "Fresing.json"), os.path.join(lib, "fresing-old.json"))
    RS.save_in(lib, RS.RuleSet("Fresing", []))
    assert RS.scan(lib)["Fresing"][0].endswith("fresing-old.json")
    assert RS.scan(lib)["Fresing"][1].rules == []
    RS.rename_in(lib, "Fresing", "Fresing BV")
    assert set(RS.scan(lib)) == {"Client B", "Fresing BV"}
    with pytest.raises(ValueError):
        RS.rename_in(lib, "Client B", "fresing bv")
    RS.delete_in(lib, "Client B")
    assert list(RS.scan(lib)) == ["Fresing BV"]
    with pytest.raises(FileNotFoundError):
        RS.delete_in(lib, "Client B")


def test_damaged_files_are_skipped_and_never_break_the_list(tmp_path):
    """Review 0015: a hand-edited file with lists where the format has tables broke 3 Looks."""
    lib = tmp_path / "Rule sets"
    RS.save_in(str(lib), RS.RuleSet("Good", [R.Rule("A", "name", "contains", "A")]))
    bad = {"groups": [["Frame", "RAL 5010"]], "renames": ["x"], "rules": ["not a rule"], "rules2": [{"field": "name"}]}
    for i, (key, value) in enumerate(bad.items()):
        d = {RS.MARKER: 1, "name": f"Bad {i}", key.rstrip("2"): value}
        (lib / f"bad{i}.json").write_text(json.dumps(d), encoding="utf-8")
    (lib / "list.json").write_text("[1, 2]", encoding="utf-8")
    (lib / "binary.json").write_bytes(b"\xff\xfe\x00garbage")
    # Notepad's "UTF-8 with BOM", and values of the wrong type that still make sense
    d = {RS.MARKER: 1, "name": "Notepad", "rules": [{"target": 5, "value": 12, "enabled": 0}]}
    (lib / "notepad.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(d).encode("utf-8"))
    found = RS.scan(str(lib))
    assert sorted(found) == ["Good", "Notepad"]
    r = found["Notepad"][1].rules[0]
    assert (r.target, r.value, r.enabled) == ("5", "12", False)
    for value in ([], {"groups": {}}, {RS.MARKER: 1, "groups": [1]}, {RS.MARKER: 1, "renames": "x"}, {RS.MARKER: 1, "rules": [None]}):
        with pytest.raises(ValueError):
            RS.RuleSet.from_dict(value)


def test_saving_never_overwrites_another_rule_sets_file(tmp_path):
    """Review 0015: names that differ can give the same file name ('A/B' and 'A_B')."""
    lib = str(tmp_path / "Rule sets")
    pairs = [("Fresing", "Fresing."), ("Client A_B", "Client A/B"), ("CON", "_CON")]
    for first, second in pairs:
        RS.save_in(lib, RS.RuleSet(first, [R.Rule(first, "name", "contains", "1")]))
        RS.save_in(lib, RS.RuleSet(second, [R.Rule(second, "name", "contains", "2")]))
    found = RS.scan(lib)
    for first, second in pairs:
        assert found[first][1].rules[0].target == first and found[second][1].rules[0].target == second
        assert found[first][0] != found[second][0]
    assert os.path.basename(found["Fresing."][0]) == "Fresing (2).json"
    # a file that is no rule set is never overwritten either
    (tmp_path / "Rule sets" / "Notes.json").write_text('{"mine": 1}', encoding="utf-8")
    RS.save_in(lib, RS.RuleSet("Notes", []))
    assert json.loads((tmp_path / "Rule sets" / "Notes.json").read_text(encoding="utf-8")) == {"mine": 1}
    # renaming onto a file name in use takes the next free one
    RS.rename_in(lib, "Notes", "Client A/B 2")
    RS.rename_in(lib, "Client A/B 2", "Fresing.. ")
    found = RS.scan(lib)
    assert {"Fresing", "Fresing.", "Fresing..", "Client A_B", "Client A/B"} <= set(found)
    assert len({p for p, _rs in found.values()}) == len(found)
    assert json.loads((tmp_path / "Rule sets" / "Notes.json").read_text(encoding="utf-8")) == {"mine": 1}


def test_a_copy_made_in_explorer_does_not_take_over(tmp_path):
    """Review 0015: 'Fresing - Copy.json' sorts before 'Fresing.json'; saves must still go to the original."""
    import shutil
    lib = tmp_path / "Rule sets"
    RS.save_in(str(lib), RS.RuleSet("Fresing", []))
    shutil.copy(lib / "Fresing.json", lib / "Fresing - Copy.json")
    assert RS.scan(str(lib))["Fresing"][0].endswith(os.sep + "Fresing.json")
    RS.save_in(str(lib), RS.RuleSet("Fresing", [R.Rule("A", "name", "contains", "A")]))
    assert RS.RuleSet.load(str(lib / "Fresing.json")).rules and not RS.RuleSet.load(str(lib / "Fresing - Copy.json")).rules


def test_a_rule_without_group_survives_saving():
    """Review 0015: it was dropped when read back, so the project showed 'changed: 1 rule' for ever."""
    rs = RS.RuleSet("A", [R.Rule("", "name", "contains", "X"), R.Rule("B", "name", "contains", "B")])
    again = RS.RuleSet.from_json(rs.to_json())
    assert len(again.rules) == 2 and not any(RS.differences(again, rs).values())


def test_names_need_a_letter_or_digit():
    assert "letters or digits" in RS.name_problem("...")
    assert "letters or digits" in RS.name_problem("/?*")
    assert RS.name_problem("Ü") == "" and RS.name_problem("7") == ""


def test_template_keeps_its_rule_set_and_old_templates_have_none(tmp_path):
    from fresing_render.core.template import Template
    t = Template(name="T", rule_set=RS.RuleSet("Fresing", []).to_dict())
    p = tmp_path / "t.json"
    t.save(str(p))
    again = Template.load(str(p))
    assert again.rule_set["name"] == "Fresing" and again.rules == R.default_rules()
    old = json.loads(p.read_text(encoding="utf-8"))
    del old["rule_set"]
    p.write_text(json.dumps(old), encoding="utf-8")
    assert Template.load(str(p)).rule_set is None


# =============================================================================
# Blender
# =============================================================================

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, faces, logic, rule_sets  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    path = tmp_path / "library" / "Rule sets"
    monkeypatch.setenv(rule_sets.ENV_FOLDER, str(path))
    rule_sets.forget_scan()
    yield path
    rule_sets.forget_scan()


def _new_project(step=STEP):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def scene(lib):
    return _new_project()


def _part(sc, name, n=0):
    return sorted((o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name), key=lambda o: o[build.PROP_UID])[n]


def _groups_of(sc):
    return {o.name: o[build.PROP_GROUP] for o in build.iter_parts(sc)}


def test_new_project_uses_standard_unchanged(scene):
    s = scene.fresing
    assert s.rule_set == "Standard" and rule_sets.kind(s) == "builtin"
    assert not rule_sets.is_changed(s)
    assert logic.rules_from_scene(s) == R.default_rules()
    assert all(g.by_rules for g in s.groups)


def test_copy_standard_edit_save_and_use_in_a_new_project(scene, lib, monkeypatch):
    s = scene.fresing
    # copy Standard: the project now uses the copy, nothing else changes
    before = _groups_of(scene)
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    assert s.rule_set == "Fresing" and rule_sets.kind(s) == "library" and not rule_sets.is_changed(s)
    assert (lib / "Fresing.json").is_file() and _groups_of(scene) == before
    # edit in the project: a rule from Find & sort parts and a group material
    s.find_text = "lamp"
    s.groups_index = next(i for i, g in enumerate(s.groups) if g.name == "Fasteners black")
    assert bpy.ops.fresing.find_rule() == {"FINISHED"}
    s.groups["Fasteners galvanized"].material = "zinc_flake"
    d = rule_sets.differences(s)
    assert d == {"rules": 1, "looks": 1, "renames": 0} and rule_sets.is_changed(s)
    assert RS.RuleSet.load(str(lib / "Fresing.json")).same_content(RS.standard())     # not saved yet
    assert bpy.ops.fresing.rule_set_save() == {"FINISHED"}
    assert not rule_sets.is_changed(s)
    saved = RS.RuleSet.load(str(lib / "Fresing.json"))
    assert saved.rules[0].value.upper() == "LAMP" and saved.rules[0].target == "Fasteners black"
    assert saved.looks["Fasteners galvanized"] == ("zinc_flake", "")
    # a new project started with 'Fresing' sorts and paints the same way
    monkeypatch.setattr(rule_sets, "default_name", lambda: "Fresing")
    sc2 = _new_project()
    s2 = sc2.fresing
    assert s2.rule_set == "Fresing" and not rule_sets.is_changed(s2)
    assert _part(sc2, "SIGNAL.LAMP")[build.PROP_GROUP] == "Fasteners black"
    assert s2.groups["Fasteners galvanized"].material == "zinc_flake"


def test_default_rule_set_missing_from_the_library_falls_back_to_standard(lib, monkeypatch):
    monkeypatch.setattr(rule_sets, "default_name", lambda: "Gone")
    sc = _new_project()
    assert sc.fresing.rule_set == "Standard" and "Gone" in sc.fresing.last_message


def test_new_empty_rule_set_puts_everything_in_unsorted_but_keeps_hand_picks(scene, lib):
    s = scene.fresing
    lamp = _part(scene, "SIGNAL.LAMP")
    lamp["fr_group_manual"] = "Lamps by hand"
    logic.apply_rules(scene)
    assert bpy.ops.fresing.rule_set_new_empty(name="Client B") == {"FINISHED"}
    assert s.rule_set == "Client B" and len(s.rules) == 0 and not rule_sets.is_changed(s)
    assert RS.RuleSet.load(str(lib / "Client B.json")).rules == []
    for ob in build.iter_parts(scene):
        assert ob[build.PROP_GROUP] == ("Lamps by hand" if ob == lamp else R.FALLBACK_GROUP), ob.name
    assert sorted(g.name for g in s.groups) == ["Lamps by hand", R.FALLBACK_GROUP]
    # sorting again keeps the empty rule set empty (no defaults sneak back in)
    logic.apply_rules(scene)
    assert len(s.rules) == 0 and s.unmatched == len(list(build.iter_parts(scene)))


def test_switch_keeps_hand_assignments_and_preview_counts_match(scene, lib):
    s = scene.fresing
    frame = _part(scene, "FRAME")
    bolt = _part(scene, "ISO 4017 M12 x 40 - 8.8 HDG", 1)
    assert bpy.ops.fresing.group_add(name="Special") == {"FINISHED"}
    s.groups["Special"].material = "paint_gloss"
    s.groups["Special"].color = "RAL 3000"
    frame["fr_group_manual"] = "Special"
    bolt["fr_group_manual"] = "Special"
    logic.apply_rules(scene)
    other = RS.RuleSet("Client B", [R.Rule("Bolts", "is_standard", "any", ""),
                                    R.Rule("Covers {color}", "name", "contains", "COVER")],
                       {"Bolts": ("stainless_brushed", "")}, {"Covers #13447C": "Covers blue"})
    RS.save_in(str(lib), other)
    rule_sets.forget_scan()
    before = _groups_of(scene)
    groups_before = {g.name for g in s.groups}
    p = rule_sets.preview(scene, rule_sets.find("Client B"))
    assert _groups_of(scene) == before                          # the preview changes nothing
    assert bpy.ops.fresing.rule_set_switch(name="Client B") == {"FINISHED"}
    after = _groups_of(scene)
    assert p["moved"] == sum(1 for k in before if before[k] != after[k]) > 0
    assert p["by_hand"] == 2
    groups_after = {g.name for g in s.groups}
    assert set(p["added"]) == groups_after - groups_before and set(p["gone"]) == groups_before - groups_after
    assert p["unsorted"] == s.unmatched
    # hand picks stay, with their group and its look
    assert frame[build.PROP_GROUP] == "Special" and bolt[build.PROP_GROUP] == "Special"
    assert (s.groups["Special"].material, s.groups["Special"].color) == ("paint_gloss", "RAL 3000")
    # the new rule set's rules, renames and looks
    assert _part(scene, "ISO 7380 M6x12")[build.PROP_GROUP] == "Bolts"
    assert s.groups["Bolts"].material == "stainless_brushed"
    assert _part(scene, "COVER.PLATE")[build.PROP_GROUP] == "Covers blue"
    assert _part(scene, "SIGNAL.LAMP")[build.PROP_GROUP] == R.FALLBACK_GROUP
    assert "Fasteners black" not in s.groups                    # left without parts: gone
    assert not rule_sets.is_changed(s)
    # and back to Standard: the built-in looks come back, hand picks still stay
    s.groups["Bolts"].material = "galvanized"
    assert rule_sets.is_changed(s)
    assert bpy.ops.fresing.rule_set_switch(name="Standard") == {"FINISHED"}
    assert s.rule_set == "Standard" and not rule_sets.is_changed(s)
    assert frame[build.PROP_GROUP] == "Special" and s.groups["Fasteners black"].material == "black_oxide"


def test_switching_restores_looks_the_new_rule_set_does_not_list(scene, lib):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Red covers") == {"FINISHED"}
    cover = _part(scene, "COVER.PLATE")[build.PROP_GROUP]
    s.groups[cover].color = "RAL 3000"
    assert bpy.ops.fresing.rule_set_save() == {"FINISHED"}
    assert bpy.ops.fresing.rule_set_switch(name="Standard") == {"FINISHED"}
    assert s.groups[cover].color == "#13447C"                   # Standard: the look from the CAD colour
    p = rule_sets.preview(scene, rule_sets.find("Red covers"))
    assert p["looks"] == 1 and p["moved"] == 0
    assert bpy.ops.fresing.rule_set_switch(name="Red covers") == {"FINISHED"}
    assert s.groups[cover].color == "RAL 3000"


def test_group_renames_belong_to_the_rule_set(scene, lib, monkeypatch):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    s.groups["Fasteners black"].name = "Bolts black"            # rename in the list
    assert rule_sets.differences(s)["renames"] == 1
    assert bpy.ops.fresing.rule_set_save() == {"FINISHED"}
    monkeypatch.setattr(rule_sets, "default_name", lambda: "Fresing")
    sc2 = _new_project()
    g = sc2.fresing.groups["Bolts black"]
    assert g.material == "black_oxide" and _part(sc2, "ISO 7380 M6x12")[build.PROP_GROUP] == "Bolts black"
    assert "Fasteners black" not in sc2.fresing.groups and not rule_sets.is_changed(sc2.fresing)


def test_groups_with_only_hand_picked_parts_belong_to_the_project(scene, lib):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    _part(scene, "FRAME")["fr_group_manual"] = "Frame by hand"
    logic.apply_rules(scene)
    s.groups["Frame by hand"].material = "paint_gloss"
    assert not s.groups["Frame by hand"].by_rules and not rule_sets.is_changed(s)


def test_library_missing_the_project_uses_its_own_copy(scene, lib, tmp_path):
    import shutil
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    s.groups_index = 0
    assert bpy.ops.fresing.rule_add() == {"FINISHED"}
    s.rules[0].value = "LAMP"
    assert bpy.ops.fresing.rule_set_save() == {"FINISHED"}
    logic.apply_rules(scene)
    before = _groups_of(scene)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    shutil.rmtree(lib)
    rule_sets.forget_scan()
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = sc.fresing
    assert s.rule_set == "Fresing" and rule_sets.kind(s) == "project" and not rule_sets.is_changed(s)
    logic.apply_rules(sc)
    assert _groups_of(sc) == before and s.rules[0].value == "LAMP"
    # it can be put back into the library under its own name
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    assert rule_sets.kind(s) == "library" and RS.RuleSet.load(str(lib / "Fresing.json")).rules[0].value == "LAMP"


def test_unreachable_shared_library(scene, lib, monkeypatch, tmp_path):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    monkeypatch.delenv(rule_sets.ENV_FOLDER)

    class Prefs:
        library_path = str(tmp_path / "offline share")
        default_rule_set = "Fresing"
        default_template = ""
    from fresing_render.blender import prefs
    monkeypatch.setattr(prefs, "get", lambda: Prefs)
    rule_sets.forget_scan()
    path, shared, problem = rule_sets.folder()
    assert shared and "cannot be reached" in problem and path.endswith("Rule sets")
    assert rule_sets.kind(s) == "project" and rule_sets.library() == {}
    s.groups[0].material = "paint_gloss"
    with pytest.raises(OSError):
        rule_sets.save_to_library(scene)
    sc2 = _new_project()                                        # default set not reachable: Standard
    assert sc2.fresing.rule_set == "Standard"


def test_old_project_opens_unchanged_as_a_rule_set_of_its_own(scene, lib, tmp_path):
    s = scene.fresing
    rules = logic.rules_from_scene(s)
    rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    logic.load_rules_into_scene(s, rules)
    logic.apply_rules(scene)
    s.groups["Lamps"].material = "plastic_gloss"
    s.groups["Lamps"].color = "RAL 2004"
    before = _groups_of(scene)
    looks = {g.name: (g.material, g.color) for g in s.groups}
    s.rule_set, s.rule_set_data = "", ""                       # as saved by 0.2.9
    for g in s.groups:
        g.by_rules = False
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = sc.fresing
    assert s.rule_set == RS.FROM_PROJECT and rule_sets.kind(s) == "project"
    assert not rule_sets.is_changed(s)
    assert rule_sets.saved(s).looks["Lamps"] == ("plastic_gloss", "RAL 2004")
    logic.apply_rules(sc)
    assert _groups_of(sc) == before and {g.name: (g.material, g.color) for g in s.groups} == looks
    # an old project with the untouched default rules uses Standard
    sc = _new_project()
    sc.fresing.rule_set, sc.fresing.rule_set_data = "", ""
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert bpy.context.scene.fresing.rule_set == "Standard"


def test_old_template_loads_as_before(scene, lib, tmp_path):
    from fresing_render.blender.ops_main import _template_from_scene, apply_template
    from fresing_render.core.template import Template
    s = scene.fresing
    rules = logic.rules_from_scene(s)
    rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    logic.load_rules_into_scene(s, rules)
    logic.apply_rules(scene)
    s.groups["Lamps"].material = "plastic_gloss"
    s.groups["Lamps"].color = "RAL 2004"
    t = _template_from_scene(scene)
    t.rule_set = None                                           # as written by 0.2.9
    path = str(tmp_path / "old template.json")
    t.save(path)
    assert "rule_set" not in json.loads(open(path, encoding="utf-8").read())
    sc = _new_project()
    apply_template(sc, Template.load(path))
    s = sc.fresing
    assert logic.rules_from_scene(s) == rules
    assert _part(sc, "SIGNAL.LAMP")[build.PROP_GROUP] == "Lamps"
    assert (s.groups["Lamps"].material, s.groups["Lamps"].color) == ("plastic_gloss", "RAL 2004")
    assert s.rule_set == "From template 'Template'" and not rule_sets.is_changed(s)


def test_template_refers_to_its_rule_set_by_name(scene, lib, tmp_path):
    from fresing_render.blender.ops_main import _template_from_scene, apply_template
    from fresing_render.core.template import Template
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    path = str(tmp_path / "t.json")
    _template_from_scene(scene).save(path)
    # the library version moves on: the template uses it
    newer = RS.RuleSet.load(str(lib / "Fresing.json"))
    newer.rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    RS.save_in(str(lib), newer)
    rule_sets.forget_scan()
    sc = _new_project()
    apply_template(sc, Template.load(path))
    assert sc.fresing.rule_set == "Fresing" and not rule_sets.is_changed(sc.fresing)
    assert _part(sc, "SIGNAL.LAMP")[build.PROP_GROUP] == "Lamps"
    # the library does not have it (another PC): the template's own copy
    os.remove(str(lib / "Fresing.json"))
    rule_sets.forget_scan()
    sc = _new_project()
    apply_template(sc, Template.load(path))
    s = sc.fresing
    assert s.rule_set == "Fresing" and rule_sets.kind(s) == "project"
    assert logic.rules_from_scene(s) == R.default_rules()


def test_template_keeps_changes_not_saved_to_the_library(scene, lib, tmp_path):
    from fresing_render.blender.ops_main import _template_from_scene, apply_template
    from fresing_render.core.template import Template
    s = scene.fresing
    s.groups["Fasteners black"].material = "chrome"             # Standard, changed in this project
    path = str(tmp_path / "t.json")
    _template_from_scene(scene).save(path)
    sc = _new_project()
    apply_template(sc, Template.load(path))
    s = sc.fresing
    assert s.rule_set == "Standard" and s.groups["Fasteners black"].material == "chrome"
    assert rule_sets.differences(s) == {"rules": 0, "looks": 1, "renames": 0}
    # a library rule set with changes, and the library moves on afterwards: the library version wins
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    s.groups["Fasteners galvanized"].material = "zinc_flake"
    _template_from_scene(sc).save(path)
    newer = RS.RuleSet.load(str(lib / "Fresing.json"))
    newer.rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    RS.save_in(str(lib), newer)
    rule_sets.forget_scan()
    sc = _new_project()
    apply_template(sc, Template.load(path))
    s = sc.fresing
    assert s.rule_set == "Fresing" and not rule_sets.is_changed(s) and s.rules[0].target == "Lamps"
    assert s.groups["Fasteners galvanized"].material == "galvanized" and "newer in the library" in s.last_message


def test_library_has_a_newer_version(scene, lib):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    assert not rule_sets.library_differs(s)
    newer = RS.RuleSet.load(str(lib / "Fresing.json"))
    newer.rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    RS.save_in(str(lib), newer)
    rule_sets.forget_scan()
    assert rule_sets.library_differs(s) and not rule_sets.is_changed(s)
    assert bpy.ops.fresing.rule_set_switch(name="Fresing") == {"FINISHED"}      # load it again
    assert not rule_sets.library_differs(s) and s.rules[0].target == "Lamps"


def test_rename_and_delete(scene, lib):
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    assert bpy.ops.fresing.rule_set_rename(name="Fresing", new_name="Fresing BV") == {"FINISHED"}
    assert s.rule_set == "Fresing BV" and rule_sets.kind(s) == "library" and not rule_sets.is_changed(s)
    assert list(rule_sets.library(force=True)) == ["Fresing BV"]
    assert bpy.ops.fresing.rule_set_delete(name="Fresing BV") == {"FINISHED"}
    assert rule_sets.library(force=True) == {}
    assert s.rule_set == "Fresing BV" and rule_sets.kind(s) == "project"     # the project keeps its copy
    # a project-only rule set can be renamed too
    assert bpy.ops.fresing.rule_set_rename(name="Fresing BV", new_name="Mine") == {"FINISHED"}
    assert s.rule_set == "Mine"
    # names that cannot be used
    with pytest.raises(RuntimeError):
        bpy.ops.fresing.rule_set_save_as(name="Standard")
    with pytest.raises(RuntimeError):
        bpy.ops.fresing.rule_set_save_as(name="")


def test_standard_cannot_be_saved_over(scene):
    s = scene.fresing
    s.groups[0].material = "paint_gloss"
    assert rule_sets.is_changed(s)
    assert not bpy.ops.fresing.rule_set_save.poll()
    with pytest.raises(ValueError):
        rule_sets.save_to_library(scene)


def test_switch_sorts_painted_faces_again(lib):
    sc = _new_project(FACES_A)
    s = sc.fresing
    housing = _part(sc, "HOUSING")
    assert faces.groups_on(housing)[1] == "Colour #CC1A1A"
    red = RS.standard().copy("Red anodised")
    red.rules.insert(0, R.Rule("Anodised red", "color", "equals", "#CC1A1A"))
    red.looks["Anodised red"] = ("aluminium_anodized_color", "#CC1A1A")
    RS.save_in(str(lib), red)
    rule_sets.forget_scan()
    p = rule_sets.preview(sc, rule_sets.find("Red anodised"))
    assert p["faces_moved"] == 1 and "Anodised red" in p["added"]
    assert bpy.ops.fresing.rule_set_switch(name="Red anodised") == {"FINISHED"}
    assert faces.groups_on(housing)[1] == "Anodised red"
    assert housing.material_slots[2].material["fr_material"] == "aluminium_anodized_color"
    assert "Colour #CC1A1A" not in s.groups


def test_panels_draw_in_every_state(scene, lib):
    from test_blender import FakeLayout
    from fresing_render.blender import ui
    s = scene.fresing

    def draw_all():
        errors = []
        for cls in (ui.FRESING_PT_looks, ui.FRESING_PT_rules):
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            cls.draw(fake, bpy.context)
            for extra in ("draw_header_preset",):
                if hasattr(cls, extra):
                    getattr(cls, extra)(fake, bpy.context)
        assert not errors, errors

    draw_all()                                                  # Standard
    s.groups[0].material = "paint_gloss"
    draw_all()                                                  # Standard, changed
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    s.groups[0].material = "paint_satin"
    draw_all()                                                  # library, changed
    newer = RS.RuleSet.load(str(lib / "Fresing.json"))
    newer.rules = []
    RS.save_in(str(lib), newer)
    rule_sets.forget_scan()
    draw_all()                                                  # library has a newer version
    os.remove(str(lib / "Fresing.json"))
    rule_sets.forget_scan()
    draw_all()                                                  # only in this project
    # every item list of the menus has the rule sets
    from fresing_render.blender import ops_rule_sets
    items = ops_rule_sets._all_items(None, bpy.context)
    assert [it[0] for it in items] == ["Standard", "Fresing"]
    assert "only in this project" in items[1][1]


def test_tooltips_on_every_rule_set_button_and_setting():
    from fresing_render.blender import ops_rule_sets
    for cls in ops_rule_sets.CLASSES:
        assert (cls.__doc__ or "").strip(), cls.__name__
        mod, op = cls.bl_idname.split(".")
        for name, prop in getattr(getattr(bpy.ops, mod), op).get_rna_type().properties.items():
            if name != "rna_type" and not prop.is_hidden:
                assert prop.description, f"{cls.__name__}.{name}"


def test_sorting_cost_of_the_changed_check(scene):
    """The panel compares the project's rule set with its saved copy on every redraw: keep it cheap."""
    import time
    s = scene.fresing
    t = time.perf_counter()
    for _ in range(200):
        rule_sets.is_changed(s)
    assert (time.perf_counter() - t) / 200 < 0.005


def test_menu_numbers_stay_with_their_rule_set(lib):
    """Review 0015: Blender keeps the number of the picked menu item. Numbered by position, a rule set a
    colleague adds while a dialog is open made Delete remove another rule set."""
    from fresing_render.blender import ops_rule_sets
    for name in ("Beta", "Gamma"):
        RS.save_in(str(lib), RS.RuleSet(name, []))
    rule_sets.forget_scan()

    class Holder(bpy.types.PropertyGroup):
        pick: bpy.props.EnumProperty(items=ops_rule_sets._library_items)
    bpy.utils.register_class(Holder)
    bpy.types.WindowManager.fr_test_pick = bpy.props.PointerProperty(type=Holder)
    try:
        holder = bpy.context.window_manager.fr_test_pick
        holder.pick = "Beta"
        RS.save_in(str(lib), RS.RuleSet("Alpha", []))          # a colleague adds one; the list is read again
        rule_sets.forget_scan()
        assert [it[0] for it in ops_rule_sets._library_items(None, bpy.context)] == ["Alpha", "Beta", "Gamma"]
        assert holder.pick == "Beta"
    finally:
        del bpy.types.WindowManager.fr_test_pick
        bpy.utils.unregister_class(Holder)
    numbers = [it[4] for it in ops_rule_sets._all_items(None, bpy.context)]
    assert numbers[0] == 0 and len(set(numbers)) == len(numbers)


def test_save_warns_before_replacing_a_newer_library_version(scene, lib):
    """Review 0015: 'Save changes' replaced a colleague's newer version without a word."""
    s = scene.fresing
    assert bpy.ops.fresing.rule_set_save_as(name="Fresing") == {"FINISHED"}
    s.groups[0].material = "paint_gloss"
    text, careful = rule_sets.save_question(s)
    assert not careful and "1 group look" in text
    newer = RS.RuleSet.load(str(lib / "Fresing.json"))
    newer.rules.insert(0, R.Rule("Lamps", "name", "contains", "LAMP"))
    RS.save_in(str(lib), newer)                                 # no forget_scan: the dialog reads the folder itself
    text, careful = rule_sets.save_question(s)
    assert careful and "lost" in text and "Save as new" in text


def test_shared_folder_is_checked_at_most_every_few_seconds(monkeypatch, tmp_path):
    """Review 0015: the panel asked the (network) folder at every redraw; an unreachable server froze it."""
    from fresing_render.blender import prefs
    share = tmp_path / "share"
    share.mkdir()

    class Prefs:
        library_path = str(share)
        default_rule_set = "Standard"
        default_template = ""
    monkeypatch.delenv(rule_sets.ENV_FOLDER, raising=False)
    monkeypatch.setattr(prefs, "get", lambda: Prefs)
    rule_sets.forget_scan()
    asked = []
    real = os.path.isdir
    monkeypatch.setattr(os.path, "isdir", lambda p: (asked.append(p), real(p))[1])
    for _ in range(50):
        assert rule_sets.folder()[2] == ""
    assert asked.count(str(share)) == 1
    share.rmdir()                                               # the server goes away
    assert rule_sets.folder()[2] == ""                          # not asked again yet
    assert "cannot be reached" in rule_sets.folder(fresh=True)[2]
    with pytest.raises(OSError):
        rule_sets.new_empty("X")                                # saving always asks the folder itself
    rule_sets.forget_scan()
    assert hasattr(rule_sets.documents_dir, "cache_info")      # Documents: asked from Windows once


def test_damaged_files_never_stop_the_panel_drawing(scene, lib):
    from test_blender import FakeLayout
    from fresing_render.blender import ui
    s = scene.fresing
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "bad.json").write_text(json.dumps({RS.MARKER: 1, "name": "Bad", "groups": [1]}), encoding="utf-8")
    rule_sets.forget_scan()
    s.rule_set_data = json.dumps({RS.MARKER: 1, "name": "Mine", "renames": ["x"]})     # a damaged own copy
    errors = []
    fake = type("P", (), {"layout": FakeLayout(errors)})()
    ui.FRESING_PT_looks.draw(fake, bpy.context)
    assert not errors and "Bad" not in rule_sets.library()
