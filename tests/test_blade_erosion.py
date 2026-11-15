"""The worn leading edge of a wind turbine blade (task 0128): the library entry, the formula in plain Python, the
shader's nodes, and a render of a blade-shaped test piece compared with the formula."""

import math

import numpy as np
import pytest

from fresing_render.core import materials_lib

bpy = pytest.importorskip("bpy")

from fresing_render.blender import marine_looks as ML  # noqa: E402
from fresing_render.blender import materials  # noqa: E402

D = ML.DEFAULTS["EROSION"]


def test_library_entry():
    e = materials_lib.MATERIALS["paint_blade_eroded"]
    assert materials_lib.UIDS["paint_blade_eroded"] == 55
    assert e["category"] == "Paint" and materials_lib.needs_color("paint_blade_eroded")
    assert e["marine"]["kind"] == "EROSION" and ML.MATERIALS["EROSION"] == "paint_blade_eroded"
    assert set(e["marine"]) - {"kind"} <= set(D)
    assert 0.3 <= e["roughness"] <= 0.5 and e["coat"] <= 0.15       # a blade's satin finish, not a ship's gloss


def test_formula():
    assert ML.erosion(1.0, 117.0, 0.0) == 1.0                       # the nose, at the tip, in a worn patch
    assert ML.erosion(1.0, 117.0, 1.0) == 0.0                       # the same, in a patch that kept its paint
    assert ML.erosion(1.0, D["span_from"] - 1.0, 0.0) == 0.0        # inner blade: no wear
    assert ML.erosion(0.0, 117.0, 0.0) == 0.0                       # the flat side: no wear
    assert ML.erosion(-1.0, 117.0, 0.0) == 0.0                      # the trailing edge: no wear
    s = np.linspace(0, 117, 40)
    assert np.all(np.diff(ML.erosion(1.0, s, 0.0)) >= 0)           # more worn towards the tip, never less
    c = np.linspace(-1, 1, 40)
    assert np.all(np.diff(ML.erosion(c, 117.0, 0.0)) >= 0)         # more worn nearer the nose
    n = np.linspace(0, 1, 40)
    assert np.all(np.diff(ML.erosion(1.0, 117.0, n)) <= 0)          # patches: a low noise value is worn


def test_nodes_are_valid_and_need_no_scripts():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = materials.ensure_material("G blade", "paint_blade_eroded", "RAL 9016", 0.0)
    nt = mat.node_tree
    assert all(link.is_valid for link in nt.links)
    assert ML.NODE_EROSION in ML.nodes_of(mat)
    assert nt.animation_data is None and mat.animation_data is None
    assert not [n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage"]
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    for sock in ("Base Color", "Roughness", "Normal"):
        assert bsdf.inputs[sock].is_linked, sock
    assert materials.is_current(mat, "paint_blade_eroded", "RAL 9016", 0.0)


# ---- a blade-shaped piece, rendered ---------------------------------------------------------------------------------

LENGTH = 117.0


def _blade_piece(turn_deg=30.0):
    """An elliptical cylinder 117 m along z, chord 6 m along y (the leading edge faces -y), turned about the vertical
    like a part that sits somewhere in the model: object and world coordinates differ."""
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"
    sc.render.resolution_x, sc.render.resolution_y = 16, 128
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.view_settings.view_transform = "Standard"
    n, rings = 48, 60
    co, faces = [], []
    for j in range(rings + 1):
        for i in range(n):
            a = 2 * math.pi * i / n
            co.append((1.2 * math.cos(a), 3.0 * math.sin(a), LENGTH * j / rings))
    for j in range(rings):
        for i in range(n):
            a, b = j * n + i, j * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    me = bpy.data.meshes.new("blade")
    me.from_pydata(co, [], faces)
    me.shade_smooth()
    ob = bpy.data.objects.new("blade", me)
    sc.collection.objects.link(ob)
    ob.rotation_euler.z = math.radians(turn_deg)
    mat = materials.ensure_material("G blade", "paint_blade_eroded", "RAL 9016", 0.0)
    materials.assign(ob, mat)
    nt = mat.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(nt.nodes[ML.NODE_EROSION].outputs[0], em.inputs["Color"])
    for out in (x for x in nt.nodes if x.bl_idname == "ShaderNodeOutputMaterial"):
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.0, 0.0, 0.0)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = LENGTH
    return sc, cam


def _look(sc, cam, from_y_sign, turn_deg=30.0, path="/tmp/erosion.exr"):
    t = math.radians(turn_deg)
    d = np.array([-math.sin(t), math.cos(t)])                      # the object's +y in the world
    eye = d * from_y_sign * 200.0
    cam.location = (eye[0], eye[1], LENGTH / 2)
    cam.rotation_euler = (math.radians(90), 0.0, math.atan2(-from_y_sign * d[0], from_y_sign * d[1]) + math.pi)
    sc.render.filepath = path
    sc.cycles.samples = 4
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.empty(16 * 128 * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(128, 16, 4)[:, :, 0].astype(float)       # row 0 = the root (Blender stores a picture from the bottom)


def test_the_worn_strip_is_on_the_leading_edge_of_the_outer_blade(tmp_path):
    sc, cam = _blade_piece()
    le = _look(sc, cam, -1, path=str(tmp_path / "le.exr"))             # looking at the leading edge (-y side)
    te = _look(sc, cam, +1, path=str(tmp_path / "te.exr"))             # looking at the trailing edge
    z = (np.arange(128) + 0.5) * LENGTH / 128
    centre = slice(7, 9)                                               # the columns where the surface faces us
    assert le[z < D["span_from"] - 2][:, centre].max() == 0.0          # inner blade: paint as new
    assert le[z > D["span_full"] + 1][:, centre].mean() > 0.2          # tip: worn in patches
    assert le[z > D["span_full"] + 1][:, centre].mean() < 0.95         # but patches, not all of it
    assert te[:, centre].max() == 0.0                                             # trailing edge: never
    assert le[z > D["span_full"]].mean() > le[(z > D["span_from"]) & (z < 88)].mean()   # more worn towards the tip
