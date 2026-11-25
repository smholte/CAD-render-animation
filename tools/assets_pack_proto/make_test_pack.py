"""Task 0344 proof (study files only): write a tiny made-up "Fresing assets" test pack.

Not part of the app. Runs inside Blender 5.2.3 (background, factory settings):

    blender -b --factory-startup --python tools/assets_pack_proto/make_test_pack.py -- <out folder> [1.0.0|1.1.0]

Writes ``<out>/fresing_assets/`` – the layout the study proposes (pack.json, LICENSE-ASSETS.txt, one .blend per
asset, shared textures and HDRIs as files with their own sizes):

    pack.json                       id, version, app window, contract, one row per asset (id, kind, file, datablock,
                                    sha256 of the file, size)
    materials/paint_satin.blend     a shader node group "FRP paint_satin" – procedural (no image), the contract inputs
    materials/concrete_floor.blend  a node group + a Material using 3 image textures from textures/
    worlds/studio_soft.blend        a World using hdri/studio_soft_2k.exr
    environments/workshop_small.blend  a Collection (floor with the concrete material, two walls, a lamp)
    props/euro_pallet.blend         an Object at real size (1.2 x 0.8 x 0.144 m)
    textures/<n>k/*.jpg|png         colour / roughness / normal at 1k, 2k, 4k (made-up patterns)
    hdri/studio_soft_<n>k.exr       2k and 4k half-float

Version 1.1.0 changes ``paint_satin`` (rougher, a new input default) and the concrete colour picture, so the
"update looks" step has something to find. Everything here is drawn by this script: CC0, nothing of anyone else's.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time

import bpy
import numpy as np

PACK_ID = "fresing-assets-test"
PACKED_PICTURES = False
CONTRACT = 1                      # the interface version of the node groups (inputs / outputs the app wires)


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else "/tmp/fr0344_pack"
    version = argv[1] if len(argv) > 1 else "1.0.0"
    global PACKED_PICTURES
    PACKED_PICTURES = len(argv) > 2 and argv[2] == "packed"       # variant: pictures packed inside each .blend
    return os.path.abspath(out), version


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _tag(idb, asset_id: str, kind: str, version: str):
    """What the app would store on every pack datablock: enough to find its source again ("update looks")."""
    idb["fr_asset"] = json.dumps({"id": asset_id, "kind": kind, "pack": PACK_ID, "version": version,
                                  "contract": CONTRACT}, separators=(",", ":"))


# ---- pictures -----------------------------------------------------------------------------------------------------

def _pattern(n: int, seed: int, smooth: float = 6.0) -> np.ndarray:
    """A soft made-up pattern (sum of waves + a little noise) – compresses like a photo, not like white noise."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n
    img = np.zeros((n, n), np.float32)
    for k in range(9):
        fx, fy = rng.uniform(1, smooth * (k + 1), 2)
        ph = rng.uniform(0, 2 * math.pi, 2)
        img += np.sin(2 * math.pi * fx * x + ph[0]) * np.cos(2 * math.pi * fy * y + ph[1]) / (k + 1)
    img = (img - img.min()) / (img.max() - img.min() + 1e-9)
    img = 0.85 * img + 0.15 * rng.random((n, n), dtype=np.float32)
    return img


def _save_image(path: str, rgba: np.ndarray, fmt: str, colorspace: str = "sRGB", depth: str = "8"):
    n_y, n_x = rgba.shape[:2]
    name = os.path.basename(path)
    img = bpy.data.images.new(name, n_x, n_y, alpha=False, float_buffer=(fmt == "OPEN_EXR"))
    img.colorspace_settings.name = colorspace if fmt != "OPEN_EXR" else "Linear Rec.709"
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = fmt
    sc = bpy.context.scene
    s = sc.render.image_settings
    s.file_format = fmt
    if fmt == "JPEG":
        s.quality = 90
    if fmt == "PNG":
        s.color_depth = depth
        s.compression = 90
    if fmt == "OPEN_EXR":
        s.color_depth = "16"
        s.exr_codec = "DWAA"
    img.save_render(path, scene=sc)
    bpy.data.images.remove(img)


def make_textures(root: str, version: str) -> dict:
    """colour (JPEG, sRGB), roughness (PNG 8-bit, non-colour), normal (PNG 8-bit, non-colour) at 1k / 2k / 4k."""
    sizes = {}
    for n in (1024, 2048, 4096):
        k = f"{n // 1024}k"
        a = _pattern(n, 7)
        b = _pattern(n, 11, 18.0)
        tint = 0.05 if version == "1.0.0" else 0.12          # 1.1.0: a warmer concrete
        col = np.stack([0.42 + 0.25 * a + tint, 0.42 + 0.25 * a, 0.40 + 0.22 * a, np.ones_like(a)], -1)
        rough = np.stack([0.55 + 0.35 * b] * 3 + [np.ones_like(b)], -1)
        gy, gx = np.gradient(b)
        nrm = np.stack([0.5 - 4 * gx, 0.5 - 4 * gy, np.ones_like(b) * 0.95, np.ones_like(b)], -1)
        d = os.path.join(root, "textures", k)
        _save_image(os.path.join(d, "concrete_color.jpg"), np.clip(col, 0, 1)[::-1], "JPEG")
        _save_image(os.path.join(d, "concrete_rough.png"), np.clip(rough, 0, 1)[::-1], "PNG", "Non-Color")
        _save_image(os.path.join(d, "concrete_normal.png"), np.clip(nrm, 0, 1)[::-1], "PNG", "Non-Color")
        sizes[k] = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
    for n in (2048, 4096):
        h, w = n // 2, n
        # Blender's rows start at the bottom: row 0 = straight down, the last row = straight up
        v = np.linspace(0, 1, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
        sky = np.stack([0.25 + 0.5 * v, 0.27 + 0.5 * v, 0.30 + 0.55 * v, np.ones_like(v)], -1)
        for cx in (0.25, 0.7):                                  # two soft boxes above the horizon
            x0, x1 = int(w * (cx - 0.04)), int(w * (cx + 0.04))
            y0, y1 = int(h * 0.62), int(h * 0.80)
            sky[y0:y1, x0:x1, :3] = 30.0
        _save_image(os.path.join(root, "hdri", f"studio_soft_{n // 1024}k.exr"), sky, "OPEN_EXR")
    return sizes


# ---- node groups and datablocks --------------------------------------------------------------------------------------

def paint_satin_group(version: str):
    """The contract: inputs Colour, Wear, Rust (0 … 1), output Shader. Procedural only."""
    ng = bpy.data.node_groups.new("FRP paint_satin", "ShaderNodeTree")
    iface = ng.interface
    iface.new_socket("Colour", in_out="INPUT", socket_type="NodeSocketColor").default_value = (0.8, 0.8, 0.8, 1.0)
    iface.new_socket("Wear", in_out="INPUT", socket_type="NodeSocketFloat")
    iface.new_socket("Rust", in_out="INPUT", socket_type="NodeSocketFloat")
    iface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    nt = ng.nodes
    gi, go = nt.new("NodeGroupInput"), nt.new("NodeGroupOutput")
    bsdf = nt.new("ShaderNodeBsdfPrincipled")
    noise = nt.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 650.0
    bump = nt.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    ng.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    ng.links.new(bump.outputs["Normal"], bsdf.inputs["Coat Normal"])
    ng.links.new(gi.outputs["Colour"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.36 if version == "1.0.0" else 0.42
    bsdf.inputs["Coat Weight"].default_value = 0.15
    ng.links.new(bsdf.outputs["BSDF"], go.inputs["Shader"])
    _tag(ng, "material:paint_satin", "material", version)
    return ng


def _image(root: str, rel: str, colorspace: str):
    img = bpy.data.images.load(os.path.join(root, rel), check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def concrete_material(root: str, version: str, k: str = "2k"):
    """A whole Material (floors take a whole material) with 3 pictures from textures/<k>/ – paths relative to the
    .blend so the pack can move."""
    mat = bpy.data.materials.new("FRP concrete_floor")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)          # 2 m per picture
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    imgs = {}
    for key, cs in (("color", "sRGB"), ("rough", "Non-Color"), ("normal", "Non-Color")):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = imgs[key] = _image(root, f"textures/{k}/concrete_{key}." + ("jpg" if key == "color" else "png"), cs)
        nt.links.new(mp.outputs["Vector"], node.inputs["Vector"])
        if key == "color":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        elif key == "rough":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nt.links.new(node.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    _tag(mat, "material:concrete_floor", "material", version)
    return mat


def studio_world(root: str, version: str, k: str = "2k"):
    w = bpy.data.worlds.new("FRP studio_soft")
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = _image(root, f"hdri/studio_soft_{k}.exr", "Linear Rec.709")
    nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    _tag(w, "world:studio_soft", "world", version)
    return w


def _box(name, size, loc, mat=None):
    me = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    return ob


def workshop_collection(root: str, version: str):
    col = bpy.data.collections.new("FRP workshop_small")
    floor_mat = concrete_material(root, version)                  # its own copy: every pack .blend stands alone
    col.objects.link(_box("FRP workshop floor", (10, 10, 0.02), (0, 0, -0.01), floor_mat))
    wall = bpy.data.materials.new("FRP workshop wall")
    wall.diffuse_color = (0.8, 0.8, 0.78, 1)
    col.objects.link(_box("FRP workshop wall back", (10, 0.2, 4), (0, 5, 2), wall))
    col.objects.link(_box("FRP workshop wall left", (0.2, 10, 4), (-5, 0, 2), wall))
    lamp = bpy.data.lights.new("FRP workshop lamp", "AREA")
    lamp.energy, lamp.size = 800.0, 2.0
    lob = bpy.data.objects.new("FRP workshop lamp", lamp)
    lob.location = (0, 0, 3.9)
    col.objects.link(lob)
    col["fr_size_m"] = [10.0, 10.0, 4.0]
    _tag(col, "environment:workshop_small", "environment", version)
    return col


def pallet_object(root: str, version: str):
    wood = bpy.data.materials.new("FRP pallet wood")
    wood.use_nodes = True
    tex = wood.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = _image(root, "textures/1k/concrete_color.jpg", "sRGB")    # stands in for a wood picture
    wood.node_tree.links.new(tex.outputs["Color"], wood.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    ob = _box("FRP euro_pallet", (1.2, 0.8, 0.144), (0, 0, 0.072), wood)
    ob["fr_size_m"] = [1.2, 0.8, 0.144]
    _tag(ob, "prop:euro_pallet", "prop", version)
    return ob


def _save(root: str, rel: str, keep):
    """Save only what ``keep`` needs (fake users on the roots), with paths relative to the .blend itself."""
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0      # no .blend1 copies in the pack
    for idb in keep:
        idb.use_fake_user = True
    if PACKED_PICTURES:
        for img in bpy.data.images:
            if img.source == "FILE" and img.packed_file is None:
                img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    return path


def main():
    out, version = _args()
    root = os.path.join(out, "fresing_assets")
    t0 = time.time()
    _clean()
    tex_sizes = make_textures(root, version)
    rows = []

    def add(asset_id, kind, rel, datablock, coll):
        path = os.path.join(root, rel)
        rows.append({"id": asset_id, "kind": kind, "file": rel, "datablock": [coll, datablock],
                     "sha256": _sha256(path), "bytes": os.path.getsize(path)})

    _clean()
    ng = paint_satin_group(version)
    add("material:paint_satin", "material", _save(root, "materials/paint_satin.blend", [ng]).replace(root + "/", ""),
        ng.name, "node_groups")
    _clean()
    mat = concrete_material(root, version)
    add("material:concrete_floor", "material",
        _save(root, "materials/concrete_floor.blend", [mat]).replace(root + "/", ""), mat.name, "materials")
    _clean()
    w = studio_world(root, version)
    add("world:studio_soft", "world", _save(root, "worlds/studio_soft.blend", [w]).replace(root + "/", ""),
        w.name, "worlds")
    _clean()
    col = workshop_collection(root, version)
    add("environment:workshop_small", "environment",
        _save(root, "environments/workshop_small.blend", [col]).replace(root + "/", ""), col.name, "collections")
    _clean()
    ob = pallet_object(root, version)
    add("prop:euro_pallet", "prop", _save(root, "props/euro_pallet.blend", [ob]).replace(root + "/", ""),
        ob.name, "objects")

    with open(os.path.join(root, "LICENSE-ASSETS.txt"), "w", encoding="utf-8") as f:
        f.write("Made-up test pack of task 0344 (made by tools/assets_pack_proto/make_test_pack.py). CC0.\n")
    pack = {"format": "fresing-assets", "format_version": 1, "id": PACK_ID, "title": "Fresing assets (test pack)",
            "version": version, "contract": CONTRACT, "app_min": "0.2.258", "app_max": "",
            "licence": "LICENSE-ASSETS.txt", "made": time.strftime("%Y-%m-%d"),
            "qualities": {"draft": "1k", "normal": "2k", "final": "4k"}, "assets": rows,
            "texture_bytes": tex_sizes}
    with open(os.path.join(root, "pack.json"), "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=1)
    total = sum(os.path.getsize(os.path.join(d, n)) for d, _, ns in os.walk(root) for n in ns)
    print(f"FR0344 PACK {version} at {root}: {len(rows)} assets, {total / 1e6:.1f} MB, {time.time() - t0:.1f} s")


main()
