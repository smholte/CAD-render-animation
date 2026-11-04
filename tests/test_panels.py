"""2 Structure (tree) and 3 Looks (find, group, rules, suggestions, show only) – task 0009."""

import os
import re

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, finder, logic  # noqa: E402
from fresing_render.blender import tree as tree_mod  # noqa: E402
from fresing_render.core import rules as R  # noqa: E402

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")
CRANE_A = os.path.join(HERE, "data", "test_crane_inv_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _load(path):
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def scene():
    return _load(STEP)


def _row(s, label):
    return next(i for i, it in enumerate(s.tree) if it.label == label)


def _part(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


# ---- tree ------------------------------------------------------------------------------


def test_tree_rows_parts_and_identical_parts(scene):
    s = scene.fresing
    labels = [(it.label, it.is_part, it.same) for it in s.tree]
    assert labels[0] == ("TEST.MACHINE", False, 1)
    assert ("COVER.ASM", False, 1) in labels and ("FRAME", True, 1) in labels
    assert ("ISO 4017 M12 x 40 - 8.8 HDG", True, 4) in labels       # four bolts: one row
    assert s.tree[0].expanded and not s.tree[_row(s, "COVER.ASM")].expanded
    shown = [s.tree[i].label for i, v in enumerate(tree_mod.visible_rows(s)) if v]
    assert "COVER.ASM" in shown and "COVER.PLATE" not in shown       # closed assembly hides its parts
    tree_mod.set_open(s, _row(s, "COVER.ASM"), True)
    shown = [s.tree[i].label for i, v in enumerate(tree_mod.visible_rows(s)) if v]
    assert "COVER.PLATE" in shown
    logic.rebuild_tree(scene)                                         # open state is kept
    assert s.tree[_row(s, "COVER.ASM")].expanded
    tree_mod.open_all(s, False)
    assert s.tree[0].expanded and not s.tree[_row(s, "COVER.ASM")].expanded


def test_tree_search_shows_matches_with_their_assemblies(scene):
    s = scene.fresing
    shown = [s.tree[i].label for i, v in enumerate(tree_mod.visible_rows(s, "plate")) if v]
    assert shown == ["TEST.MACHINE", "COVER.ASM", "COVER.PLATE"]


def test_identical_subassemblies_get_occurrence_numbers():
    class Ob(dict):
        def __init__(self, name, inst=""):
            super().__init__({build.PROP_NAME: name, build.PROP_INSTANCE: inst})
            self.name = name
    kids = [Ob("LEAK.TEST"), Ob("LEAK.TEST"), Ob("PUMP"), Ob("LEAK.TEST", "LEAK.TEST:7")]
    assert [lab for _o, lab in tree_mod._labelled(kids)] == ["LEAK.TEST :1", "LEAK.TEST :2", "PUMP", "LEAK.TEST:7"]


def test_row_click_highlights_and_view_click_opens_the_tree(scene):
    s = scene.fresing
    s.tree_index = _row(s, "COVER.ASM")                     # a click on the row
    sel = {o.get(build.PROP_NAME) for o in bpy.context.selected_objects}
    assert {"COVER.ASM", "COVER.PLATE", "ISO 7380 M6x12"} <= sel and "FRAME" not in sel
    s.tree_index = _row(s, "ISO 4017 M12 x 40 - 8.8 HDG")   # one row, all four bolts
    assert sum(1 for o in bpy.context.selected_objects if o.get(build.PROP_NAME, "").startswith("ISO 4017")) == 4
    # a click in the view on a part inside the closed cover opens the tree down to it
    tree_mod.open_all(s, False)
    s.pick_mode = "PART"
    plate = _part(scene, "COVER.PLATE")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    from fresing_render.blender import handlers
    handlers._on_active_changed()
    assert s.tree[s.tree_index].label == "COVER.PLATE"
    assert s.tree[_row(s, "COVER.ASM")].expanded


def test_show_only_and_back(scene):
    s = scene.fresing
    frame = _part(scene, "FRAME")
    bolts = [o for o in scene.objects if o.get(build.PROP_NAME, "").startswith("ISO 4017")]
    logic.set_hidden(bolts[0], True)                         # the user's own hidden part
    tree_mod.show_only(scene, [frame], "FRAME")
    assert s.isolated == "FRAME" and not frame.hide_get() and _part(scene, "COVER.PLATE").hide_get()
    tree_mod.end_show_only(scene)
    assert not _part(scene, "COVER.PLATE").hide_get() and s.isolated == ""
    assert bolts[0].hide_get(), "a part hidden by the user stays hidden"


# ---- find & group ---------------------------------------------------------------------


def test_search_words_and_wildcards():
    assert finder.name_matches("O-RING 20x2 NBR", finder.terms_of("ring nbr"))
    assert not finder.name_matches("O-RING 20x2 NBR", finder.terms_of("ring epdm"))
    assert finder.name_matches("ISO 4762 M6x20", finder.terms_of("M6*20"))
    assert not finder.name_matches("ISO 4762 M8x20", finder.terms_of("M6*20"))


@pytest.mark.parametrize("text", ["iso", "ISO m12", "M*12 hdg", "plate", "DIN 912"])
def test_a_search_and_its_rule_find_the_same_names(text):
    names = ["ISO 4017 M12 x 40 - 8.8 HDG", "ISO 7380 M6x12", "DIN 912 M10x30 - 12.9", "COVER.PLATE",
             "FRAME", "SIGNAL.LAMP", "Iso plate M12 hdg"]
    field, op, value = finder.rule_for_search(text)
    rule = R.Rule("X", field, op, value)
    for n in names:
        assert finder.name_matches(n, finder.terms_of(text)) == R._matches(rule, R.facts_for(n)), (text, n)


def test_find_put_in_group_and_make_rule(scene):
    s = scene.fresing
    s.find_text = "iso"                                      # runs the search
    names = {it.part_name: it.count for it in s.found}
    assert names == {"ISO 4017 M12 x 40 - 8.8 HDG": 4, "ISO 7380 M6x12": 2}
    s.found[1].use = False                                   # untick the M6 screws
    assert bpy.ops.fresing.find_assign(group="__new__") == {"FINISHED"}
    assert s.groups.get("Iso") is not None
    assert {o.get(build.PROP_GROUP) for o in scene.objects if o.get(build.PROP_NAME, "").startswith("ISO 4017")} \
        == {"Iso"}
    assert _part(scene, "ISO 7380 M6x12").get(build.PROP_GROUP) != "Iso"
    s.groups_index = next(i for i, g in enumerate(s.groups) if g.name == "Iso")
    assert bpy.ops.fresing.find_rule() == {"FINISHED"}
    assert (s.rules[0].target, s.rules[0].field, s.rules[0].op, s.rules[0].value) == ("Iso", "name", "contains", "ISO")
    # the rule sorts a new revision by itself: drop the hand assignments, sort again
    for o in scene.objects:
        o.pop("fr_group_manual", None)
    logic.apply_rules(scene)
    assert _part(scene, "ISO 7380 M6x12").get(build.PROP_GROUP) == "Iso"


def test_find_only_in_selected_subassembly(scene):
    s = scene.fresing
    s.tree_index = _row(s, "COVER.ASM")
    s.find_in_selected = True
    s.find_text = "iso"
    assert [it.part_name for it in s.found] == ["ISO 7380 M6x12"]


def test_rule_for_a_whole_subassembly(scene):
    s = scene.fresing
    s.tree_index = _row(s, "COVER.ASM")
    logic.ensure_group(s, "Cover")
    s.groups_index = next(i for i, g in enumerate(s.groups) if g.name == "Cover")
    assert bpy.ops.fresing.rule_from_subassembly() == {"FINISHED"}
    assert {_part(scene, n).get(build.PROP_GROUP) for n in ("COVER.PLATE", "ISO 7380 M6x12")} == {"Cover"}
    assert _part(scene, "FRAME").get(build.PROP_GROUP) != "Cover"


def test_suggestions_for_unsorted_parts(scene):
    s = scene.fresing
    for name in ("FRAME", "SIGNAL.LAMP", "COVER.PLATE"):
        ob = _part(scene, name)
        ob[build.PROP_NAME] = "SEAL RING " + name
        ob[build.PROP_COLOR] = ""
    logic.apply_rules(scene)
    words = dict(finder.suggestions(scene))
    assert words.get("SEAL") == 3 and words.get("RING") == 3
    assert "ASM" not in words


def test_show_only_unsorted_and_group(scene):
    s = scene.fresing
    assert bpy.ops.fresing.show_only_group(group="") == {"FINISHED"}
    unsorted = finder.unsorted_parts(scene)
    assert unsorted and all(not o.hide_get() for o in unsorted)
    assert _part(scene, "FRAME").hide_get() or _part(scene, "FRAME").get(build.PROP_GROUP) == R.FALLBACK_GROUP
    assert bpy.ops.fresing.show_all() == {"FINISHED"}
    assert s.isolated == "" and not _part(scene, "FRAME").hide_get()


def test_ready_made_material_and_move_to_group(scene):
    s = scene.fresing
    s.groups_index = 0
    assert bpy.ops.fresing.group_preset(preset="rubber") == {"FINISHED"}
    assert s.groups[0].material == "rubber_black"
    for o in bpy.context.selected_objects:
        o.select_set(False)
    lamp = _part(scene, "SIGNAL.LAMP")
    lamp.select_set(True)
    bpy.context.view_layer.objects.active = lamp
    assert bpy.ops.fresing.part_move_group(group="Fasteners black") == {"FINISHED"}
    assert lamp.get(build.PROP_GROUP) == "Fasteners black"
    assert bpy.ops.fresing.part_move_group(group="__new__") == {"FINISHED"}
    assert lamp.get(build.PROP_GROUP).startswith("SIGNAL.LAMP")


def test_tree_row_buttons(scene):
    s = scene.fresing
    row = _row(s, "COVER.ASM")
    for action in ("SELECT", "FRAME", "HIDE", "HIDE", "ONLY"):
        assert bpy.ops.fresing.tree_row(index=row, action=action) == {"FINISHED"}, action
    assert s.isolated
    assert bpy.ops.fresing.show_only_end() == {"FINISHED"} and not s.isolated
    assert bpy.ops.fresing.tree_toggle(index=row) == {"FINISHED"}
    assert bpy.ops.fresing.tree_open_all(open=True) == {"FINISHED"}
    assert all(it.expanded for it in s.tree if it.has_kids)
    bpy.ops.fresing.tree_row(index=row, action="SELECT")
    assert bpy.ops.fresing.show_only_selected() == {"FINISHED"} and s.isolated == "the selection"


def test_crane_tree_after_model_update():
    """The tree survives a model update (new part, one less bolt) and keeps open rows."""
    sc = _load(CRANE_A)
    s = sc.fresing
    boom = _row(s, "BOOM.ASM")
    tree_mod.set_open(s, boom, True)
    root = build.model_roots(sc)[0]
    res = bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_crane_inv_c.step"),
                                      quality="draft", update_root=root.name)
    assert res == {"FINISHED"}
    labels = [it.label for it in s.tree]
    assert "BOOM.LAMP" in labels and s.tree[_row(s, "BOOM.ASM")].expanded
    assert re.match(r"ISO 4017 M12 x 40 - 8\.8 HDG", next(lab for lab in labels if lab.startswith("ISO 4017")))


def test_find_inside_uses_the_subassembly_of_a_selected_part(scene):
    s = scene.fresing
    s.tree_index = _row(s, "COVER.PLATE")
    assert finder.scope_row(s).label == "COVER.ASM"
    s.find_in_selected = True
    s.find_text = "iso"
    assert [it.part_name for it in s.found] == ["ISO 7380 M6x12"]


def test_tree_rebuild_walks_the_scene_a_few_times_only(scene, monkeypatch):
    """Was one scene walk per 'x N' row: 4.6 s on a 2,800-part model (now 0.07 s)."""
    made = []
    orig = logic.Tree.__init__

    def counting(self, *a, **k):
        made.append(1)
        orig(self, *a, **k)
    monkeypatch.setattr(logic.Tree, "__init__", counting)
    logic.rebuild_tree(scene)
    tree_mod.row_of(scene, _part(scene, "FRAME"))
    assert len(made) <= 2, len(made)
