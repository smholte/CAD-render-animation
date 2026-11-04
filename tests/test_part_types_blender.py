"""Part types and CAD material names inside Blender (task 0008): import, sort, group looks."""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_materials.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, logic  # noqa: E402
from fresing_render.core import rules as R  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    return sc


def _part(sc, name):
    return next(ob for ob in build.iter_parts(sc) if ob[build.PROP_NAME] == name)


def test_cad_material_on_the_part_object(scene):
    assert _part(scene, "PLATE")[build.PROP_CAD_MATERIAL] == "Aluminum - Satin"
    assert _part(scene, "SEAL RING")[build.PROP_CAD_MATERIAL] == "Rubber - Soft"
    assert _part(scene, "BODY3")[build.PROP_CAD_MATERIAL] == ""
    f = logic.facts_for_object(_part(scene, "BODY1"))
    assert f.cad_material == "Paint - Enamel Glossy (Red)"


def test_new_default_rules_sort_the_import(scene):
    s = scene.fresing
    assert [r.field for r in s.rules][-3:] == ["part_type", "cad_material", "color"]
    groups = {g.name: g for g in s.groups}
    assert _part(scene, "PLATE")[build.PROP_GROUP] == "Aluminum - Satin"
    assert groups["Aluminum - Satin"].material == "aluminium_machined"
    assert _part(scene, "SEAL RING")[build.PROP_GROUP] == "Seals & O-rings"
    assert groups["Seals & O-rings"].material == "rubber_black"
    red = _part(scene, "BODY1")[build.PROP_GROUP]
    assert red.startswith("Paint - Enamel Glossy (Red) #")
    assert groups[red].material == "paint_gloss" and groups[red].color == red.split(" ")[-1]
    assert _part(scene, "BODY3")[build.PROP_GROUP] == R.FALLBACK_GROUP
    assert s.rules[6].count == 1 and s.rules[7].count == 2       # part type: seal; CAD material: plate, body1


def test_new_materials_build_in_blender(scene):
    from fresing_render.blender import materials
    for mat_id in ("nickel_plated", "aluminium_anodized_black", "zinc_diecast", "belt_rubber", "foam", "felt",
                   "mannequin_matte", "wood"):
        mat = materials.ensure_material(f"Test {mat_id}", mat_id, "")
        assert mat["fr_material"] == mat_id and mat.node_tree.nodes
