"""Adjust a look (task 0314): the sliders' ranges and formulas (core), the node "FR adjust" in a group's material,
live changes without a rebuild, Reset, Save as my material keeping the changed values, the shader editor's poll, and
the cost table with its "slower" badge."""

import json
import os

import pytest

from fresing_render.core import look_adjust as LA
from fresing_render.core import material_files as F
from fresing_render.core import materials_lib as ML

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")


# ---------------------------------------------------------------------------------------------------------------------
# core

def test_ranges_and_keys():
    assert LA.clean({"shine": 5, "dirt": -1, "relief": float("nan"), "coat": "x"}) == \
        {"shine": 1.0, "metal": 0.0, "dirt": 0.0, "relief": 1.0, "coat": 0.0}
    assert LA.is_default({}) and LA.key({}) == ""
    k = LA.key({"shine": 0.25, "relief": 1.0, "dirt": 0.5})
    assert k == "shine=0.2500;dirt=0.5000"
    assert LA.parse(k) == LA.clean({"shine": 0.25, "dirt": 0.5})
    assert LA.changed({"shine": 0.25, "relief": 1.0}) == {"shine": 0.25}


def test_safe_ranges_never_black_or_glowing():
    for r in (0.0, 0.2, 0.5, 1.0):
        for s in (-1.0, -0.4, 0.0, 0.4, 1.0):
            for d in (0.0, 0.5, 1.0):
                assert LA.ROUGH_SHINY <= LA.roughness(r, s, d) <= 1.0
    assert LA.roughness(0.4, 1.0) == pytest.approx(LA.ROUGH_SHINY)
    assert LA.roughness(0.4, -1.0) == pytest.approx(LA.ROUGH_DULL)
    assert LA.roughness(0.4, 0.0) == pytest.approx(0.4)
    assert LA.metallic(0.0, 1.0) == 1.0 and LA.metallic(1.0, -1.0) == 0.0 and LA.metallic(0.3, 0.0) == 0.3
    dirty = LA.colour((1.0, 1.0, 1.0), 1.0)
    assert all(0.1 < c < 0.2 for c in dirty)                 # a dark brown, never black
    assert LA.colour((0.5, 0.2, 0.1), 0.0) == (0.5, 0.2, 0.1)


def test_which_sliders_a_look_has():
    assert LA.applies("paint_satin") == ("shine", "metal", "dirt", "relief", "coat")      # orange peel: relief
    assert "relief" not in LA.applies("paint_gloss") or ML.get("paint_gloss").get("peel")
    assert LA.applies("emission_light") == ()
    assert LA.applies("glass_clear") == ("shine",) if "glass_clear" in ML.MATERIALS else True
    assert "relief" in LA.applies("knurl_diamond")
    assert LA.effective("emission_light", {"shine": 1.0}) == LA.DEFAULTS


def test_an_own_material_keeps_the_changed_values(tmp_path):
    d = F.new_material("Dusty blue", "paint_satin", {"color": "RAL 5015", "adjust": {"shine": 0.4, "dirt": 0.3,
                                                                                    "relief": 1.0, "bogus": 2}})
    assert d["format_version"] == "1.1"
    assert d["changes"]["adjust"] == {"shine": 0.4, "dirt": 0.3}              # only what moved
    e = F.read_folder(F.save_new(str(tmp_path), d), "mine", "Mine")
    assert e.ok and e.changes["adjust"] == {"shine": 0.4, "dirt": 0.3}
    assert F.values_of(e)["adjust"] == LA.clean({"shine": 0.4, "dirt": 0.3})
    notes = []
    assert F.clean_changes("emission_light", {"adjust": {"shine": 0.5}}, notes) == {}     # a lamp has no sliders
    assert F.clean_changes("paint_satin", {"adjust": "x"}, notes) == {} and notes
    assert F.values_of(F.builtin("builtin:chrome"))["adjust"] == LA.DEFAULTS


def test_an_older_file_and_a_built_in_have_no_adjust():
    d = F.new_material("Plain", "paint_satin")
    assert "adjust" not in d["changes"]
    d["format_version"] = "1.0"
    e = F.entry_from_data(d, "mine", "Mine", "/x/Plain")
    assert e.ok and F.values_of(e)["adjust"] == LA.DEFAULTS


def test_cost_table_and_badge(tmp_path):
    data = LA.costs()
    looks = data.get("looks", {})
    assert set(looks) == set(ML.MATERIALS) - {"blender_material"}, "tools/look_costs.py: every look measured"
    assert all(isinstance(v, (int, float)) and v > 0 for v in looks.values())
    assert looks["paint_satin"] == pytest.approx(1.0)
    assert data.get("samples") and data.get("machine")
    slow = [k for k in looks if LA.slower(k)]
    for k in slow:
        assert LA.cost_text(k).startswith("Slower to render")
    assert LA.cost_text("paint_satin") == ""


# ---------------------------------------------------------------------------------------------------------------------
# Blender

@pytest.fixture(scope="module")
def app():
    global bpy
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture()
def loc(app, tmp_path, monkeypatch):
    from fresing_render.blender import locations, prefs
    from fresing_render.core import locations as L
    monkeypatch.setenv(locations.ENV, str(tmp_path / "config" / L.STATE_FILE))
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs"))
    prefs.get().library_path = ""
    locations.forget()
    locations.load()
    return locations


@pytest.fixture()
def scene(loc):
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.groups_index = 0
    return sc


def _mat(g):
    from fresing_render.blender import materials
    return bpy.data.materials.get(materials.material_name(g.name))


def test_an_untouched_look_has_no_adjust_node(scene):
    from fresing_render.blender import look_adjust
    g = scene.fresing.groups[0]
    g.material, g.color = "paint_satin", "RAL 5010"
    mat = _mat(g)
    assert look_adjust.node_of(mat) is None and "fr_adjust" not in mat


def test_a_slider_puts_the_node_in_then_moves_it_live(scene):
    from fresing_render.blender import look_adjust, materials
    g = scene.fresing.groups[0]
    g.material, g.color = "paint_satin", "RAL 5010"
    g.adj_shine = 0.5
    mat = _mat(g)
    n = look_adjust.node_of(mat)
    assert n is not None and n.inputs["Shine"].default_value == pytest.approx(0.5)
    assert mat["fr_adjust"] == "shine=0.5000"
    bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
    for name, out in (("Base Color", "Colour"), ("Roughness", "Roughness"), ("Metallic", "Metallic"),
                      ("Normal", "Normal"), ("Coat Weight", "Coat")):
        assert bsdf.inputs[name].links[0].from_node == n and bsdf.inputs[name].links[0].from_socket.name == out
    assert n.inputs["Roughness"].default_value == pytest.approx(ML.get("paint_satin")["roughness"])
    assert n.inputs["Coat"].default_value == pytest.approx(ML.get("paint_satin")["coat"])
    assert mat.roughness == pytest.approx(LA.roughness(ML.get("paint_satin")["roughness"], 0.5))
    # live: the next slider changes the node, the tree is not built again
    names = {x.name for x in mat.node_tree.nodes}
    g.adj_dirt, g.adj_coat, g.adj_metal, g.adj_relief = 0.6, 0.4, -0.3, 1.5
    assert look_adjust.node_of(mat) == n and {x.name for x in mat.node_tree.nodes} == names
    assert n.inputs["Dirt"].default_value == pytest.approx(0.6) and n.inputs["Relief"].default_value == pytest.approx(1.5)
    assert n.inputs["Clear coat"].default_value == pytest.approx(0.4)
    assert n.inputs["Metal ↔ paint"].default_value == pytest.approx(-0.3)
    assert materials.is_current(mat, g.material, g.color, g.wear, "", g.rust, look_adjust.group_key(g))
    # a rebuild (Wear) keeps the values in the node
    g.wear = 0.3
    n = look_adjust.node_of(_mat(g))
    assert n.inputs["Dirt"].default_value == pytest.approx(0.6) and n.inputs["Shine"].default_value == pytest.approx(0.5)


def test_the_node_group_matches_the_formulas(app):
    """The group's wiring, read back: Shine's targets and Dirt's colour are the core's numbers."""
    from fresing_render.blender import look_adjust
    ng = look_adjust.node_group()
    ins = [s.name for s in ng.interface.items_tree if s.in_out == "INPUT"]
    assert ins[-5:] == [LA.SLIDERS[k][0] for k in LA.NAMES]
    for k in LA.NAMES:
        s = next(x for x in ng.interface.items_tree if x.in_out == "INPUT" and x.name == LA.SLIDERS[k][0])
        assert (s.min_value, s.max_value, s.default_value) == pytest.approx(LA.SLIDERS[k][1:4])
    consts = {round(n.inputs[1].default_value, 4) for n in ng.nodes if n.bl_idname == "ShaderNodeMath"
              and n.operation == "MULTIPLY_ADD"}
    assert {LA.ROUGH_SHINY, LA.ROUGH_DULL} <= consts
    mix = next(n for n in ng.nodes if n.bl_idname == "ShaderNodeMix" and n.data_type == "RGBA")
    assert tuple(mix.inputs[7].default_value)[:3] == pytest.approx(LA.DIRT_RGB)


def test_sliders_that_do_not_apply_are_left_out(scene):
    from fresing_render.blender import look_adjust
    g = scene.fresing.groups[0]
    g.material = "emission_light"
    g.adj_shine = 0.8
    assert look_adjust.node_of(_mat(g)) is None


def test_pick_reset_and_save(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP
    g = scene.fresing.groups[0]
    assert bpy.ops.fresing.mat_use(key="builtin:knurl_diamond", group=g.name) == {"FINISHED"}
    g.adj_shine, g.adj_relief, g.wear = -0.4, 1.8, 0.5
    root = loc.save_folder("materials")
    e = MP.save_from_group(bpy.context, g, "Deep knurl", "", root)
    with open(os.path.join(e.folder, F.JSON_NAME), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["changes"]["adjust"] == {"shine": -0.4, "relief": 1.8}
    assert data["changes"]["wear"] == 0.5
    # another group gets the same values from the file
    g2 = scene.fresing.groups[1]
    assert bpy.ops.fresing.mat_use(key=e.key, group=g2.name) == {"FINISHED"}
    assert (g2.adj_shine, g2.adj_relief) == pytest.approx((-0.4, 1.8))
    # Reset: the own material's values again
    g2.adj_shine, g2.adj_dirt = 0.9, 0.7
    assert bpy.ops.fresing.look_reset(group=g2.name) == {"FINISHED"}
    assert (g2.adj_shine, g2.adj_dirt, g2.adj_relief, g2.wear) == pytest.approx((-0.4, 0.0, 1.8, 0.5))
    # a built-in: picked again, the sliders start at their defaults; Reset takes Wear and the finish back too
    assert bpy.ops.fresing.mat_use(key="builtin:knurl_diamond", group=g.name) == {"FINISHED"}
    assert (g.adj_shine, g.adj_relief) == pytest.approx((0.0, 1.0))
    g.adj_coat, g.fin_amount = 0.5, 0.2
    assert bpy.ops.fresing.look_reset(group=g.name) == {"FINISHED"}
    from fresing_render.core import finishes as fin_core
    assert g.adj_coat == 0.0 and g.wear == 0.0
    assert g.fin_amount == pytest.approx(fin_core.defaults("knurl_diamond")["amount"])
    MP.wait_pictures(300)


def test_shader_editor_only_in_full_access(scene):
    from fresing_render.blender import look_adjust, workspaces
    g = scene.fresing.groups[0]
    g.material = "paint_satin"
    full = workspaces.blender_ui(scene)
    assert bpy.ops.fresing.look_nodes.poll() == full
    mat = look_adjust.keep_node(g)                        # what the button does before it opens the window
    assert look_adjust.node_of(mat) is not None and mat.get(look_adjust.KEEP)
    g.color = "RAL 3020"                                  # a rebuild keeps it
    assert look_adjust.node_of(_mat(g)) is not None


def test_adjusted_picture_job(scene, tmp_path):
    """The job the window's large picture is made from holds the group's sliders."""
    from fresing_render.blender import material_picker as MP
    g = scene.fresing.groups[0]
    g.material, g.color = "paint_satin", ""
    g.adj_dirt = 0.5
    it = MP.group_item(g, str(tmp_path / "x.png"))
    assert it["base"] == "paint_satin" and it["changes"]["adjust"] == {"dirt": 0.5}
    assert it["changes"]["color"] == F.PICTURE_COLOURS["paint_satin"]
