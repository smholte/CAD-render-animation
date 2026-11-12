"""Better materials (task 0046): library entries, CAD names, node trees, wear, old projects get the new looks."""

import os

import pytest

from fresing_render.core import cad_materials, materials_lib

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_materials.step")

KNOWN_KEYS = {"label", "category", "needs_color", "base_color", "metallic", "roughness", "coat", "coat_roughness",
              "transmission", "ior", "emission", "emission_strength", "specular", "anisotropic", "sheen",
              "sheen_roughness", "variation", "bump", "peel", "marks", "grid"}


# ---- library (no Blender) -------------------------------------------------------------------

def test_new_materials_have_new_numbers_and_old_numbers_stay():
    assert materials_lib.UIDS["wire_mesh"] == 42            # the last number before 0046
    new = {"steel_ground": 43, "steel_turned": 44, "cast_iron_painted": 45, "chrome_rod": 46}
    for key, uid in new.items():
        assert materials_lib.UIDS[key] == uid
        assert key in materials_lib.MATERIALS
    assert set(materials_lib.UIDS) == set(materials_lib.MATERIALS)
    assert len(set(materials_lib.UIDS.values())) == len(materials_lib.UIDS)


def test_every_definition_uses_known_keys():
    for key, d in materials_lib.MATERIALS.items():
        assert set(d) <= KNOWN_KEYS, (key, set(d) - KNOWN_KEYS)
        assert 0.0 <= d.get("roughness", 0.4) <= 1.0, key
        m = d.get("marks")
        if m:
            assert m["kind"] in ("ground", "brushed", "turned", "milled"), key
            assert m["scale"] >= 1000, key                       # sub-millimetre marks only
            assert 0 < m["rough"] <= 0.1, key                     # subtle
        if d.get("anisotropic"):
            assert m and m["kind"] != "milled", f"{key}: anisotropy needs marks that give it a direction"


def test_the_brief_materials_are_there():
    m = materials_lib.MATERIALS
    assert m["stainless_brushed"]["anisotropic"] > 0 and m["stainless_brushed"]["marks"]["kind"] == "brushed"
    assert m["steel_ground"]["marks"]["kind"] == "ground"
    assert m["steel_turned"]["marks"]["kind"] == "turned"
    assert m["aluminium_machined"]["marks"]["kind"] == "milled"
    assert m["chrome_rod"]["roughness"] < 0.1 and m["chrome_rod"]["metallic"] == 1.0
    assert m["cast_iron_painted"]["needs_color"] and m["cast_iron_painted"]["bump"]
    for key in ("aluminium_anodized", "aluminium_anodized_black", "aluminium_anodized_color"):
        assert m[key]["coat"] > 0 and m[key]["coat_roughness"] >= 0.2, key       # soft satin sheen
    for key in ("paint_gloss", "paint_satin", "paint_marine"):
        assert m[key]["peel"]["strength"] > 0, key                                 # orange peel
    assert sum(m["rubber_black"]["base_color"]) / 3 > 0.03 and m["rubber_black"]["sheen"] > 0   # not pure black


@pytest.mark.parametrize("name, material", [
    ("Aluminum - Anodized", "aluminium_anodized"),
    ("Aluminum - Anodized Rough (Blue)", "aluminium_anodized_color"),
    ("Steel - Polished", "steel_ground"),
    ("Steel, ground", "steel_ground"),
    ("Stahl geschliffen", "steel_ground"),
    ("Steel - Turned", "steel_turned"),
    ("Gedreht", "steel_turned"),
    ("Cast Iron", "cast_iron"),
    ("Gray Iron", "cast_iron"),
    ("Rubber", "rubber_black"),
    ("Hard Chrome", "chrome_rod"),
    ("Hartverchromt", "chrome_rod"),
    ("Piston rod", "chrome_rod"),
    ("Chrome - Polished", "chrome"),
    ("Stainless Steel - Polished", "stainless_polished"),
    ("Aluminum - Turned", "aluminium_machined"),               # the metal wins over the finish
])
def test_cad_names_map_to_the_new_materials(name, material):
    assert cad_materials.lookup(name)[0] == material


def test_ground_alone_is_not_a_finish():
    assert cad_materials.lookup("Ground plane") is None
    assert cad_materials.takes_cad_colour("cast_iron_painted")


# ---- Blender -------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, logic, materials  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _kinds(mat):
    return {n.bl_idname for n in mat.node_tree.nodes}


def _new_mat(name="FR test"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat


def test_every_material_builds_and_is_stamped():
    for key in materials_lib.MATERIALS:
        for wear in (0.0, 0.6):
            mat = _new_mat()
            materials.build_nodes(mat, key, "RAL 5010", wear)
            assert mat[materials.PROP_LOOK] == materials.LOOK_VERSION
            assert abs(mat["fr_wear"] - wear) < 1e-6
            assert materials.is_current(mat, key, "RAL 5010", wear)
            out = [n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
            assert out and all(n.inputs["Surface"].is_linked for n in out), key
            bpy.data.materials.remove(mat)


def test_marks_read_the_parts_own_axes():
    mat = _new_mat()
    materials.build_nodes(mat, "stainless_brushed")
    names = {n.attribute_name for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeAttribute"}
    assert materials.AX_LONG in names
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    assert bsdf.inputs["Tangent"].is_linked                       # the brushing direction
    materials.build_nodes(mat, "steel_turned")
    names = {n.attribute_name for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeAttribute"}
    assert {materials.AX_ROUND, materials.AX_CENTRE} <= names
    bpy.data.materials.remove(mat)


def test_wear_costs_nothing_at_zero():
    mat = _new_mat()
    materials.build_nodes(mat, "paint_satin", "RAL 7035", 0.0)
    assert "ShaderNodeBevel" not in _kinds(mat) and "ShaderNodeAmbientOcclusion" not in _kinds(mat)
    materials.build_nodes(mat, "paint_satin", "RAL 7035", 0.5)
    assert {"ShaderNodeBevel", "ShaderNodeAmbientOcclusion"} <= _kinds(mat)
    bpy.data.materials.remove(mat)


def test_glass_has_its_own_eevee_output():
    mat = _new_mat()
    materials.build_nodes(mat, "polycarbonate_clear")
    targets = sorted(n.target for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    assert targets == ["CYCLES", "EEVEE"]
    bpy.data.materials.remove(mat)


def test_part_axes_of_a_shaft_and_a_disc():
    import bmesh
    for size, long_k, round_k in (((0.2, 0.02, 0.02), 0, 0), ((0.06, 0.06, 0.02), None, 2),
                                  ((0.08, 0.05, 0.04), 0, 0)):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = (v.co.x * size[0] + 1.0, v.co.y * size[1], v.co.z * size[2])
        me = bpy.data.meshes.new("axes")
        bm.to_mesh(me)
        bm.free()
        materials.part_axes(me)
        if long_k is not None:
            assert list(me[materials.AX_LONG]) == [float(k == long_k) for k in range(3)]
        assert list(me[materials.AX_ROUND]) == [float(k == round_k) for k in range(3)], size
        assert abs(me[materials.AX_CENTRE][0] - 1.0) < 1e-6
        assert me[materials.AX_COUNT] == len(me.vertices)
        bpy.data.meshes.remove(me)


def _make_old(mat):
    """What a 0.2.34 project holds: one plain Principled BSDF, no look version, no wear."""
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    for key in (materials.PROP_LOOK, "fr_wear"):
        if key in mat:
            del mat[key]


def test_ensure_material_rebuilds_an_old_look():
    mat = materials.ensure_material("Old group", "steel_ground", "")
    _make_old(mat)
    assert not materials.is_current(mat, "steel_ground", "")
    again = materials.ensure_material("Old group", "steel_ground", "")
    assert again is mat and "ShaderNodeAttribute" in _kinds(mat)
    assert mat[materials.PROP_LOOK] == materials.LOOK_VERSION


def test_old_project_opens_with_new_looks(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    s = sc.fresing
    before = {g.name: (g.material, g.color) for g in s.groups}
    assert before
    for g in s.groups:                                    # as saved by 0.2.34
        mat = bpy.data.materials.get(materials.material_name(g.name))
        _make_old(mat)
    for me in bpy.data.meshes:
        for key in (materials.AX_LONG, materials.AX_ROUND, materials.AX_CENTRE, materials.AX_COUNT):
            if key in me:
                del me[key]
    path = str(tmp_path / "old project.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)               # the load handler upgrades the looks
    s = bpy.context.scene.fresing
    assert {g.name: (g.material, g.color) for g in s.groups} == before
    for g in s.groups:
        mat = bpy.data.materials[materials.material_name(g.name)]
        assert mat[materials.PROP_LOOK] == materials.LOOK_VERSION, g.name
        assert mat["fr_material"] == g.material and mat["fr_color"] == g.color
        assert len(mat.node_tree.nodes) >= 2
    parts = list(build.iter_parts(bpy.context.scene))
    assert parts and all(materials.AX_LONG in ob.data for ob in parts)
    assert logic.upgrade_looks(bpy.context.scene) == 0     # nothing left to do


def test_wear_slider_rebuilds_the_group_material(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    plain = [g for g in sc.fresing.groups if not {"transmission", "emission"} & set(materials_lib.get(g.material))]
    g = plain[0]
    assert g.wear == 0.0
    mat = bpy.data.materials[materials.material_name(g.name)]
    assert "ShaderNodeBevel" not in _kinds(mat)
    g.wear = 0.4
    assert "ShaderNodeBevel" in _kinds(mat) and abs(mat["fr_wear"] - 0.4) < 1e-6
    assert g.material == mat["fr_material"]


def test_tangent_runs_across_the_marks():
    """Task 0098: the anisotropy's tangent is the marks' direction crossed with the face normal."""
    for key in ("stainless_brushed", "steel_ground", "steel_turned"):
        mat = _new_mat()
        materials.build_nodes(mat, key)
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        norm = bsdf.inputs["Tangent"].links[0].from_node
        cross = norm.inputs[0].links[0].from_node
        assert norm.operation == "NORMALIZE" and cross.operation == "CROSS_PRODUCT", key
        assert any(l.from_node.bl_idname == "ShaderNodeNewGeometry" and l.from_socket.name == "Normal"
                   for i in cross.inputs for l in i.links), key
        bpy.data.materials.remove(mat)


def test_highlight_is_longer_across_the_marks():
    """Task 0098, rendered (Cycles CPU, 160 px): ground plate across the lines, turned shaft along its axis."""
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import measure_shine
    r = measure_shine.main()
    assert r[("steel_ground", 0)] < 0.85 * r[("steel_ground", 1)]        # along X (the lines) shorter than across
    assert r[("steel_turned", 0)] > 1.5 * r[("steel_turned", 1)]         # along the axis longer than round it
