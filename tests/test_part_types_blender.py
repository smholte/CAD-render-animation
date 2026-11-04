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


def test_untouched_old_rules_become_the_new_defaults_on_open(scene, tmp_path):
    s = scene.fresing
    logic.load_rules_into_scene(s, R.old_default_rules())
    s.rule_set, s.rule_set_data = "", ""          # a project of before 0.2.10 has no rule set
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    s = bpy.context.scene.fresing
    assert logic.rules_from_scene(s) == R.default_rules()
    assert "new defaults" in s.last_message
    assert s.rule_set == "Standard"               # the new defaults are the built-in rule set (0.2.10)
    # rules the user changed are left alone
    rules = R.old_default_rules()
    rules[0].target = "My stainless bolts"
    logic.load_rules_into_scene(s, rules)
    s.rule_set = ""
    assert not logic.ensure_default_rules(s) and logic.rules_from_scene(s)[0].target == "My stainless bolts"


def test_ready_made_black_anodised_uses_the_black_anodised_material():
    from fresing_render.blender import finder
    preset = next(p for p in finder.PRESETS if p[0] == "alu_black")
    assert preset[2:] == ("aluminium_anodized_black", "")
    assert R.default_material_for_group("Wire mesh & fences") == ("wire_mesh", "RAL 9005")


def test_wire_mesh_material_cuts_holes(tmp_path):
    """A guard panel drawn as a plate: the material lets the background through between the wires."""
    import numpy as np
    from fresing_render.blender import materials
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=0.2)                    # 200 x 200 mm, facing up
    plate = bpy.context.active_object
    plate.data.materials.append(materials.ensure_material("Mesh", "wire_mesh", "RAL 9005"))
    assert plate.active_material.node_tree.nodes["Principled BSDF"].inputs["Alpha"].is_linked
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    cam.location = (0, 0, 1)
    cam.data.type, cam.data.ortho_scale = "ORTHO", 0.1
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 100
    sc.render.filepath = str(tmp_path / "mesh.png")
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    alpha = np.array(img.pixels[:]).reshape(100, 100, 4)[..., 3]
    holes, wires = (alpha < 0.1).mean(), (alpha > 0.9).mean()
    assert 0.5 < holes < 0.9 and wires > 0.1, (holes, wires)          # 25 mm mesh, 3 mm wire: ~77 % open
