"""Task 0286 proof: make a tiny Fresing test asset library (4 assets, all made here, CC0).

Run in Blender 5.2.3:  blender -b --factory-startup --python make_assets.py -- <library folder>
Then:                  blender -c asset_listing generate <library folder>

Each asset is one self-contained .blend (images packed), with a picture, author, licence, tags, a catalog and
Fresing's own custom properties (fr_source, fr_kind, fr_size_m, fr_licence_url) that the listing carries along.
Nothing here is downloaded: every shape and picture is drawn by this script, so the library is CC0 by its maker.
"""
import math
import os
import sys
import tempfile
import uuid

import bpy
import numpy as np

LIB = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
AUTHOR = "Fresing Render (test asset, task 0286)"
LICENCE = "CC0-1.0"
LIC_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
CATS = {  # name -> fixed uuid, so the listing stays the same on every run
    "Environments": "6d1f2e9a-0286-4c00-9a01-000000000001",
    "Environments/360° photos": "6d1f2e9a-0286-4c00-9a01-000000000002",
    "Materials": "6d1f2e9a-0286-4c00-9a01-000000000003",
    "Props": "6d1f2e9a-0286-4c00-9a01-000000000004",
}
TMP = tempfile.mkdtemp(prefix="fr0286_")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 256
    sc.render.film_transparent = False
    return sc


def image(name, arr, fmt="PNG"):
    """A picture from a float array (h, w, 4), saved and PACKED into the .blend."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=(fmt == "OPEN_EXR"))
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    ext = ".exr" if fmt == "OPEN_EXR" else ".png"
    img.filepath_raw = os.path.join(TMP, name + ext)
    img.file_format = fmt
    img.save()
    img.pack()
    img.filepath = "//textures/" + name + ext   # a neutral path: the packed copy is what counts
    return img


def mark(idb, kind, desc, tags, cat, size=None):
    idb.asset_mark()
    a = idb.asset_data
    a.author, a.license, a.copyright = AUTHOR, LICENCE, "No rights reserved (CC0 1.0)"
    a.description = desc
    for t in tags:
        a.tags.new(t)
    a.catalog_id = CATS[cat]
    a["fr_source"] = "fresing-standard"
    a["fr_kind"] = kind
    a["fr_licence_url"] = LIC_URL
    a["fr_pass_on"] = True     # may travel in projects, Web 3D pages and Viewer files
    if size:
        a["fr_size_m"] = list(size)


def preview(idb, setup):
    """Render a 256 px picture with Cycles and give it to the asset as its preview."""
    sc = bpy.context.scene
    setup(sc)
    path = os.path.join(TMP, idb.name + "_preview.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    pic = bpy.data.images.load(path)
    px = np.array(pic.pixels[:], dtype=np.float32)
    pv = idb.preview_ensure()
    pv.image_size = pic.size
    pv.image_pixels_float.foreach_set(px)
    bpy.data.images.remove(pic)


def camera(sc, loc, target, lens=50):
    cam = bpy.data.objects.new("_cam", bpy.data.cameras.new("_cam"))
    cam.data.lens = lens
    sc.collection.objects.link(cam)
    cam.location = loc
    d = np.array(target) - np.array(loc)
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    sc.camera = cam
    return cam


def soft_light(sc):
    w = bpy.data.worlds.new("_light")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.82, 0.85, 1)
    sc.world = w
    sun = bpy.data.objects.new("_sun", bpy.data.lights.new("_sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (0.7, 0.2, 0.6)
    sc.collection.objects.link(sun)


def save(name):
    for ob in list(bpy.data.objects):
        if ob.name.startswith("_"):
            bpy.data.objects.remove(ob)
    for w in list(bpy.data.worlds):
        if w.name.startswith("_"):
            bpy.data.worlds.remove(w)
    path = os.path.join(LIB, name + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("WROTE", path, os.path.getsize(path))


def noise(h, w, seed, scale):
    rng = np.random.default_rng(seed)
    a = rng.random((h // scale + 2, w // scale + 2))
    a = np.kron(a, np.ones((scale, scale)))[:h, :w]
    k = np.ones(scale) / scale
    a = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, a)
    a = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 0, a)
    return (a - a.min()) / (np.ptp(a) + 1e-9)


# ---------------------------------------------------------------- 1. a 360° photo (HDRI) as a World asset
def make_hdri():
    sc = reset()
    W, H = 1024, 512
    v = (np.arange(H) + 0.5) / H                    # 0 = bottom (nadir) in Blender's pixel order
    u = (np.arange(W) + 0.5) / W
    elev = (v - 0.5) * math.pi
    sky = np.zeros((H, W, 4), np.float32)
    up = np.clip(np.sin(elev), 0, 1)[:, None]
    zen, hor = np.array([0.25, 0.45, 0.95]), np.array([0.85, 0.9, 1.0])
    col = hor + (zen - hor) * up[..., None] ** 0.6
    ground = np.array([0.18, 0.17, 0.15])
    below = (elev < 0)[:, None, None]
    col = np.where(below, ground, col) * np.ones((1, W, 1))
    # the sun: 35° up, a small very bright disc
    se, sa = math.radians(35), math.radians(120)
    E, A = np.meshgrid(elev, u * 2 * math.pi - math.pi, indexing="ij")
    cosd = np.sin(E) * math.sin(se) + np.cos(E) * math.cos(se) * np.cos(A - sa)
    col = col + (cosd > math.cos(math.radians(1.2)))[..., None] * 4000.0
    col = col + np.clip(cosd, 0, 1)[..., None] ** 64 * 3.0
    sky[..., :3], sky[..., 3] = col, 1
    img = image("fr_test_sky_1k", sky, "OPEN_EXR")
    w = bpy.data.worlds.new("Fresing test sky (clear day)")
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = img
    nt.links.new(env.outputs[0], nt.nodes["Background"].inputs[0])
    w.use_fake_user = True
    mark(w, "hdri", "A clear day with the sun 35° up. 1k test picture made by Fresing, real light levels.",
         ["sky", "outdoor", "sun", "360"], "Environments/360° photos")

    def setup(sc):
        sc.world = w
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24)
        ob = bpy.context.object
        ob.name = "_ball"
        ob.data.materials.append(bpy.data.materials.new("_chrome"))
        m = ob.data.materials[0]
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value = 1.0, 0.05
        camera(sc, (0, -4.2, 0.4), (0, 0, 0), 50)
    preview(w, setup)
    for m in list(bpy.data.materials):
        if m.name.startswith("_"):
            bpy.data.materials.remove(m)
    save("hdri_test_sky")


# ---------------------------------------------------------------- 2. a material with a packed picture
def make_material():
    sc = reset()
    g = noise(256, 256, 2, 16) * 0.6 + noise(256, 256, 3, 4) * 0.4
    arr = np.ones((256, 256, 4), np.float32)
    arr[..., 0] = arr[..., 1] = arr[..., 2] = g
    img = image("fr_test_wear_256", arr)
    m = bpy.data.materials.new("Fresing test painted steel (worn)")
    m.use_nodes = True
    m.use_fake_user = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.image.colorspace_settings.name = "Non-Color"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (2, 2, 2)
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    nt.links.new(mp.outputs[0], t.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.62, 0.68
    ramp.color_ramp.elements[0].color = (0.75, 0.32, 0.05, 1)   # paint
    ramp.color_ramp.elements[1].color = (0.35, 0.35, 0.36, 1)   # bare steel
    nt.links.new(t.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    mix = nt.nodes.new("ShaderNodeMapRange")
    mix.inputs[3].default_value, mix.inputs[4].default_value = 0.0, 1.0
    mix.inputs[1].default_value, mix.inputs[2].default_value = 0.62, 0.68
    nt.links.new(t.outputs[0], mix.inputs[0])
    nt.links.new(mix.outputs[0], b.inputs["Metallic"])
    b.inputs["Roughness"].default_value = 0.45
    mark(m, "material", "Orange machine paint worn through to bare steel on the edges of use. Test material.",
         ["paint", "steel", "worn", "orange"], "Materials")

    def setup(sc):
        soft_light(sc)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32)
        ob = bpy.context.object
        ob.name = "_ball"
        bpy.ops.object.shade_smooth()
        ob.data.materials.append(m)
        camera(sc, (0, -4.2, 0.5), (0, 0, 0), 50)
    preview(m, setup)
    save("material_test_painted_steel")


# ---------------------------------------------------------------- 3. a prop at real size (euro pallet)
def box(name, x, y, z, dx, dy, dz, mat, coll):
    me = bpy.data.meshes.new(name)
    v = [(x + sx * dx / 2, y + sy * dy / 2, z + sz * dz) for sx in (-1, 1) for sy in (-1, 1) for sz in (0, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    uv = me.uv_layers.new()
    for poly in me.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            co = me.vertices[vi].co
            n = poly.normal
            a = (co.y, co.z) if abs(n.x) > 0.5 else ((co.x, co.z) if abs(n.y) > 0.5 else (co.x, co.y))
            uv.data[li].uv = (a[0] * 2, a[1] * 2)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def make_pallet():
    sc = reset()
    g = noise(128, 512, 4, 2)
    stripes = 0.5 + 0.5 * np.sin(np.linspace(0, 60, 512)[None, :] + g * 6)
    arr = np.ones((128, 512, 4), np.float32)
    base = 0.55 + 0.25 * stripes
    arr[..., 0], arr[..., 1], arr[..., 2] = base * 0.86, base * 0.68, base * 0.45
    img = image("fr_test_wood_512", arr)
    mat = bpy.data.materials.new("Pallet wood (test)")
    mat.use_nodes = True
    t = mat.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = img
    mat.node_tree.links.new(t.outputs[0], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    coll = bpy.data.collections.new("_parts")
    parts = []
    for yy in (-0.3275, 0.0, 0.3275):                       # 3 bottom boards
        parts.append(box("b", 0, yy, 0.0, 1.2, 0.145, 0.022, mat, coll))
    for xx in (-0.5, 0.0, 0.5):                             # 9 blocks
        for yy in (-0.3275, 0.0, 0.3275):
            parts.append(box("k", xx, yy, 0.022, 0.145 if xx else 0.145, 0.145 if yy else 0.1, 0.078, mat, coll))
    for xx in (-0.5, 0.0, 0.5):                             # 3 stringer boards
        parts.append(box("s", xx, 0, 0.1, 0.145, 0.8, 0.022, mat, coll))
    for i in range(5):                                      # 5 top boards
        parts.append(box("t", 0, -0.3275 + i * 0.16375, 0.122, 1.2, 0.1 if i % 4 else 0.145, 0.022, mat, coll))
    bpy.context.scene.collection.children.link(coll)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.object
    ob.name = "Euro pallet (test)"
    sc.collection.objects.link(ob)
    coll.objects.unlink(ob)
    bpy.data.collections.remove(coll)
    dims = tuple(round(d, 3) for d in ob.dimensions)
    mark(ob, "prop", "A euro pallet at real size, 1.2 × 0.8 × 0.144 m. The origin is on the floor.",
         ["pallet", "warehouse", "wood", "scale"], "Props", dims)

    def setup(sc):
        soft_light(sc)
        camera(sc, (1.6, -1.9, 1.3), (0, 0, 0.05), 50)
    preview(ob, setup)
    save("prop_test_euro_pallet")


# ---------------------------------------------------------------- 4. a small environment (a Collection asset)
def make_environment():
    sc = reset()
    g = noise(256, 256, 7, 8) * 0.5 + noise(256, 256, 8, 2) * 0.5
    arr = np.ones((256, 256, 4), np.float32)
    arr[..., 0] = arr[..., 1] = arr[..., 2] = 0.42 + 0.18 * g
    conc = image("fr_test_concrete_256", arr)
    floor_m = bpy.data.materials.new("Workshop floor (test)")
    floor_m.use_nodes = True
    t = floor_m.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = conc
    floor_m.node_tree.links.new(t.outputs[0], floor_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    wall_m = bpy.data.materials.new("Workshop wall (test)")
    wall_m.use_nodes = True
    wall_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.78, 0.8, 0.82, 1)
    bench_m = bpy.data.materials.new("Workbench blue (test)")
    bench_m.use_nodes = True
    bench_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.18, 0.45, 1)
    coll = bpy.data.collections.new("Small workshop corner (test)")
    sc.collection.children.link(coll)
    box("Floor", 0, 0, -0.02, 10, 10, 0.02, floor_m, coll)
    box("Wall back", 0, 5.1, 0, 10, 0.2, 4.0, wall_m, coll)
    box("Wall left", -5.1, 0, 0, 0.2, 10.4, 4.0, wall_m, coll)
    box("Workbench", -3.0, 4.3, 0, 2.0, 0.75, 0.9, bench_m, coll)
    lamp = bpy.data.objects.new("Ceiling light", bpy.data.lights.new("Ceiling light", "AREA"))
    lamp.data.size, lamp.data.energy = 3.0, 1500
    lamp.location = (0, 0, 3.8)
    coll.objects.link(lamp)
    mark(coll, "environment", "A corner of a workshop, 10 × 10 m, walls 4 m, a workbench and a ceiling light. "
         "Put the machine in the middle.", ["workshop", "hall", "indoor"], "Environments", (10.0, 10.0, 4.0))

    def setup(sc):
        w = bpy.data.worlds.new("_light")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.3, 0.32, 1)
        sc.world = w
        camera(sc, (6.5, -7.0, 4.2), (-1.5, 2.5, 0.8), 30)
    preview(coll, setup)
    save("environment_test_workshop_corner")


def write_catalogs():
    lines = ["# Blender asset catalog definition file (task 0286 test library)", "VERSION 1", ""]
    for path, cid in CATS.items():
        lines.append(f"{cid}:{path}:{path.replace('/', '-')}")
    with open(os.path.join(LIB, "blender_assets.cats.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


os.makedirs(LIB, exist_ok=True)
write_catalogs()
make_hdri()
make_material()
make_pallet()
make_environment()
print("DONE", LIB)
