"""Task 0117: a mesh model in the app – import (menu, drag and drop), the file's looks ("From file"), textures packed,
round faces picked like a STEP model's (joint picker, hover, decals), web 3D export, model update, save + reopen."""

import json
import math
import os
import shutil

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, decals, faces, hover, joints, logic, mesh_import, web3d  # noqa: E402
from fresing_render.core import web3d as web3d_core  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CRANE = os.path.join(DATA, "test_mesh_crane.glb")
CRANE_B = os.path.join(DATA, "test_mesh_crane_b.glb")
SINGLE = os.path.join(DATA, "test_mesh_single.glb")
OBJ = os.path.join(DATA, "test_mesh_parts.obj")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(tmp_path, path=CRANE, **kw):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_mesh(filepath=path, **kw) == {"FINISHED"}
    bpy.context.view_layer.update()
    return sc


def part(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    assert hits, name
    return hits[n]


def ray_at(point, normal, gap=0.002):
    n = Vector(normal).normalized()
    return Vector(point) + n * gap, -n


def click(sc, origin, direction):
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), origin, direction)
    assert index >= 0
    o, d, desc = joints.axis_from_hit(ob, index, loc, normal)
    return ob, index, o, d, desc


def angle(a, b):
    return math.degrees(math.acos(min(1.0, abs(Vector(a).normalized().dot(Vector(b).normalized())))))


# ---- import ----------------------------------------------------------------------

def test_menu_file_handler_and_operator_are_there():
    assert hasattr(bpy.ops.fresing, "import_mesh")
    assert hasattr(bpy.types, "FRESING_FH_mesh")
    assert bpy.types.FRESING_FH_mesh.bl_file_extensions == ".glb;.gltf;.obj;.fbx"
    from fresing_render.blender import ops_import
    funcs = bpy.types.TOPBAR_MT_file_import._dyn_ui_initialize()
    assert ops_import.menu_import in funcs


def test_crane_comes_in_like_a_step_model(tmp_path):
    sc = fresh(tmp_path)
    roots = build.model_roots(sc)
    assert len(roots) == 1 and roots[0].name == "MESH CRANE"
    root = roots[0]
    assert mesh_import.is_mesh_model(root) and root[build.PROP_SOURCE] == os.path.abspath(CRANE)
    assert "Mesh crane (test model)" in root[mesh_import.PROP_CREDIT]
    assert "Mesh crane (test model)" in bpy.data.texts[mesh_import.CREDITS_TEXT].as_string()
    wheels = [part(sc, n) for n in ("WHEEL FL", "WHEEL FR", "WHEEL RL", "WHEEL RR")]
    assert len({w.data.name for w in wheels}) == 1                          # instancing: one mesh
    assert wheels[2].matrix_world.determinant() < 0                         # mirrored wheel
    # every group starts with the look "From file": each part shows its own file material
    assert all(g.material == mesh_import.FROM_FILE for g in sc.fresing.groups)
    base = part(sc, "BASE")
    mat = base.material_slots[0].material
    assert mat.name.startswith(mesh_import.MAT_PREFIX + "Base steel") and mat.get("fr_has_texture")
    tex = [n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"]
    assert tex and tex[0].image.packed_file is not None                     # the project stays one file
    assert base.data.uv_layers.active is not None and base.data.uv_layers.active.name == "UVMap"
    boom = part(sc, "BOOM")
    rgb = boom.material_slots[0].material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    assert abs(rgb[0] - 0.85) < 1e-3 and abs(rgb[1] - 0.55) < 1e-3          # the file's linear colour
    # the model sits as drawn: Z up, metres
    mn, mx = logic.cached_bounds(sc)
    assert abs(mn[2]) < 1e-3 and mx[2] > 1.3 and abs(mn[0] + 1.0) < 1e-3


def test_another_look_replaces_the_file_look_and_back(tmp_path):
    sc = fresh(tmp_path)
    boom = part(sc, "BOOM")
    g = sc.fresing.groups[boom[build.PROP_GROUP]]
    g.material = "paint_gloss"
    assert boom.material_slots[0].material.name == "FR " + g.name
    g.material = mesh_import.FROM_FILE
    assert boom.material_slots[0].material.name.startswith(mesh_import.MAT_PREFIX)


# ---- round faces: joints, hover, decals ----------------------------------------------

def test_clicked_facetted_ring_gives_its_axis(tmp_path):
    sc = fresh(tmp_path)
    ring = part(sc, "SLEWING RING")
    # the outer wall half way up, between two corners of the 48-sided ring
    a = math.radians(360 / 48 * 0.5)
    pt = Vector((0.8 * math.cos(a) * math.cos(math.radians(3.75)), 0.8 * math.sin(a), 0.475))
    ob, index, o, d, desc = click(sc, *ray_at(pt, (math.cos(a), math.sin(a), 0)))
    assert ob == ring and desc.startswith("round face")
    assert angle(d, (0, 0, 1)) < 0.5
    r = float(desc.split("Ø")[1].split()[0]) / 2000
    assert abs(r - 0.8) / 0.8 < 0.005, desc
    foot = o - d * o.dot(d)
    assert foot.length < 0.004                                             # the axis goes through (0, 0)
    # the whole wall is one face: hover lights up all of it
    h = hover.look(sc, bpy.context.evaluated_depsgraph_get(), *ray_at(pt, (math.cos(a), math.sin(a), 0)))
    assert h.kind == "shaft" and h.tris[1] - h.tris[0] == 2 * 48 and abs(h.diameter - 1600) < 8
    # the inner wall: a hole of the same axis
    pt = Vector((0.6 * math.cos(a) * math.cos(math.radians(3.75)), 0.6 * math.sin(a), 0.475))
    h = hover.look(sc, bpy.context.evaluated_depsgraph_get(), *ray_at(pt, (-math.cos(a), -math.sin(a), 0)))
    assert h.kind == "hole" and abs(h.diameter - 1200) < 6 and angle(h.direction, (0, 0, 1)) < 0.5
    # the top: a flat face, its axis at right angles to it
    ob, index, o, d, desc = click(sc, *ray_at((0.7, 0.0, 0.55), (0, 0, 1)))
    assert desc.startswith("flat") and angle(d, (0, 0, 1)) < 1e-3
    starts = faces.face_starts(ring.data)
    f = faces.face_of_polygon(ring.data, index)
    assert starts[f + 1] - starts[f] == 2 * 48                               # the top ring: one face


def test_boom_pin_and_wheels_are_round_faces(tmp_path):
    sc = fresh(tmp_path)
    pin = part(sc, "BOOM PIN")                                               # along Y through (0.45, *, 1.05)
    ob, index, o, d, desc = click(sc, *ray_at((0.45, 0.15, 1.05 + 0.06), (0, 0, 1)))
    assert ob == pin and angle(d, (0, 1, 0)) < 0.5 and abs(o.x - 0.45) < 2e-3 and abs(o.z - 1.05) < 2e-3
    for name in ("WHEEL FL", "WHEEL RR"):
        w = part(sc, name)
        c = w.matrix_world.translation
        ob, index, o, d, desc = click(sc, *ray_at(c + Vector((0, 0, 0.25)), (0, 0, 1)))
        assert ob == w and angle(d, (0, 1, 0)) < 0.5, name
        assert abs(float(desc.split("Ø")[1].split()[0]) - 500) < 2.5, desc


def test_a_joint_made_on_the_ring_turns_the_turret(tmp_path):
    sc = fresh(tmp_path)
    a = math.radians(3.75)
    pt = Vector((0.8 * math.cos(a) * math.cos(a), 0.8 * math.sin(a), 0.475))
    _ob, _i, o, d, _desc = click(sc, *ray_at(pt, (math.cos(a), math.sin(a), 0)))
    turret = next(x for x in sc.objects if x.get(build.PROP_NAME) == "TURRET")
    j = joints.create(sc, "ROTATE", [turret], o, d, name="Slew", base=part(sc, "BASE"))
    tip0 = part(sc, "BOOM").matrix_world @ Vector((3.0, 0, 0))
    joints.set_value(joints.find(sc, "Slew"), math.radians(90.0))
    bpy.context.view_layer.update()
    tip = part(sc, "BOOM").matrix_world @ Vector((3.0, 0, 0))
    assert abs(tip.z - tip0.z) < 1e-4 and abs(Vector((tip.x, tip.y)).length - Vector((tip0.x, tip0.y)).length) < 1e-3
    assert abs(tip.y - tip0.x) < 0.01 and abs(tip.x + tip0.y) < 0.01            # a quarter turn about Z
    assert j is not None


def test_a_decal_on_a_mesh_part(tmp_path):
    sc = fresh(tmp_path)
    base = part(sc, "BASE")
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), *ray_at((0.5, -1.0, 0.2), (0, -1, 0)))
    assert ob == base
    face = faces.face_of_polygon(base.data, index)
    it = decals.add(base, face, base.matrix_world.inverted() @ loc, (0, -1, 0), "TEXT", text="MESH")
    assert it is not None and any(decals.is_decal(o) for o in bpy.data.objects)


# ---- other files -----------------------------------------------------------------------

def test_obj_units_and_split(tmp_path):
    sc = fresh(tmp_path, OBJ)
    assert "units guessed: mm" in sc.fresing.last_message
    frame = part(sc, "Frame")
    dims = sorted(frame.dimensions)
    assert abs(dims[-1] - 1.2) < 1e-3 and abs(dims[0] - 0.2) < 1e-3
    sc = fresh(tmp_path, OBJ, units="m")
    assert abs(max(part(sc, "Frame").dimensions) - 1200.0) < 0.5
    sc = fresh(tmp_path, SINGLE)
    assert sorted(o[build.PROP_NAME] for o in build.iter_parts(sc)) == [f"WELDMENT {k}" for k in range(1, 6)]
    sc = fresh(tmp_path, SINGLE, split="off")
    assert len(list(build.iter_parts(sc))) == 1


# ---- web 3D, model update, save --------------------------------------------------------

def test_web_3d_export_of_textured_parts(tmp_path):
    sc = fresh(tmp_path)
    out = web3d.export(sc, str(tmp_path / "m.glb"), size=256, page=False, hide_names=False)
    data = open(out["path"], "rb").read()
    assert web3d_core.problems(data) == []
    doc, binary = web3d_core.read_glb(data)
    steel = [m for m in doc["materials"] if "Base steel" in m["name"]]
    assert steel and "baseColorTexture" in steel[0]["pbrMetallicRoughness"]
    tinfo = steel[0]["pbrMetallicRoughness"]["baseColorTexture"]
    assert "extensions" not in tinfo                                        # the part's own UVs, not tiles
    img = doc["images"][doc["textures"][tinfo["index"]]["source"]]
    view = doc["bufferViews"][img["bufferView"]]
    assert binary[view.get("byteOffset", 0): view.get("byteOffset", 0) + 8] == b"\x89PNG\r\n\x1a\n"


def test_model_update_keeps_the_work_and_names_a_renamed_part(tmp_path):
    src = tmp_path / "crane.glb"
    shutil.copy(CRANE, src)
    sc = fresh(tmp_path, str(src))
    boom = part(sc, "BOOM")
    boom["fr_group_manual"] = "Boom look"
    a = math.radians(3.75)
    pt = Vector((0.8 * math.cos(a) * math.cos(a), 0.8 * math.sin(a), 0.475))
    _ob, _i, o, d, _desc = click(sc, *ray_at(pt, (math.cos(a), math.sin(a), 0)))
    turret = next(x for x in sc.objects if x.get(build.PROP_NAME) == "TURRET")
    joints.create(sc, "ROTATE", [turret], o, d, name="Slew", base=part(sc, "BASE"))
    root = build.model_roots(sc)[0]
    shutil.copy(CRANE_B, src)
    os.utime(src, (os.path.getmtime(src) + 5, os.path.getmtime(src) + 5))
    assert bpy.ops.fresing.import_mesh(filepath=str(src), update_root=root.name) == {"FINISHED"}
    s = sc.fresing
    assert [x.text for x in s.report_new] == ["HOOK BLOCK"] and len(s.report_missing) == 0
    assert any("BOOM is now called MAIN BOOM" in n.text for n in s.report_notes)
    main = part(sc, "MAIN BOOM")
    assert main.get("fr_group_manual") == "Boom look"
    j = joints.find(sc, "Slew")
    assert j is not None and [m.get(build.PROP_NAME) for m in joints.members(j)] == ["TURRET"]
    assert mesh_import.is_mesh_model(build.model_roots(sc)[0])


def test_save_and_reopen_keeps_textures_and_credit(tmp_path):
    sc = fresh(tmp_path)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    base = part(sc, "BASE")
    tex = [n for n in base.material_slots[0].material.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"]
    assert tex[0].image.packed_file is not None and tex[0].image.size[0] == 64
    assert "Mesh crane" in bpy.data.texts[mesh_import.CREDITS_TEXT].as_string()
    assert json.loads(build.model_roots(sc)[0][mesh_import.PROP_OPTIONS])["format"] == "glb"
