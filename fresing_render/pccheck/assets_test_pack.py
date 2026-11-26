"""A small made-up Fresing assets pack, written at test time (task 0354) – no pack file is kept in the repository.

Shipped with the app so the PC check can make it on a user's PC later; ``tools/make_test_assets_pack.py`` is its
command line and the tests call ``make`` directly (one maker, no second copy). Needs Blender (``bpy``: Blender as a
Python module or a background Blender) to write the ``.blend`` files; everything else is plain Python.

``make(folder, version)`` writes the pack INTO ``folder`` (the folder that will hold ``pack.json``)::

    pack.json  LICENSE-ASSETS.txt (says it is a test pack, CC0)
    materials/paint_satin.blend   node group "FRP paint_satin" – procedural, on the material contract (0344 2.3)
    materials/cast_iron.blend     node group "FRP cast_iron" – reads two pictures from textures/2k/
    finishes/knurl_diamond.blend  node group "FRP knurl_diamond" – reads the finish face data and the pixel angle
    lights/PRODUCT.exr            a light look's picture (equirectangular, linear, 2048 x 1024)
    hdri/test_hall_1k|2k.exr      a 360° photo only the pack has (fallback light:OVERCAST)
    props/PALLET.blend            object "FRP PALLET": both levels in one mesh (face attribute fr_lod 1 / 2)
    environments/FACTORY.blend    collection "FRP FACTORY": a bench module and a floor tile with its own floor
                                  material "FRP FACTORY floor" (fr_env "floor")
    textures/1k|2k/test_*         small pictures made by code, versioned names (a file is never overwritten)
    pictures/<kind>.<id>.jpg      256 px picker pictures

``version`` "1.1.0" changes one look (paint_satin is rougher) and one picture (cast iron's roughness, a new file
``…_rough_v2.png``) – what "update looks" (0355) must find. Data only: no Text datablocks, no drivers, no scripts,
no handlers, no links to other files. Made up here, nothing of anyone else's (CC0).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import time

PACK_ID = "fresing-assets-test"
VERSIONS = ("1.0.0", "1.1.0")
SET = "test"
LICENCE = """Fresing assets – TEST PACK

This folder is a made-up test pack, written by Fresing Render's own code
(fresing_render/pccheck/assets_test_pack.py) for its tests and the PC check.
It holds no real looks and nothing of anyone else's. Everything in it is
dedicated to the public domain (CC0 1.0).

The real Fresing assets pack has its own licence text in this place.
"""

# the rows: id, file, datablock, picture colour (sRGB 0..1), extra fields
ROUGH = {"1.0.0": 0.36, "1.1.0": 0.42}             # paint_satin's roughness: the changed look
ROUGH_PICTURE = {"1.0.0": "v1", "1.1.0": "v2"}      # cast iron's roughness picture: the changed picture


# ---------------------------------------------------------------------------
# plain helpers
# ---------------------------------------------------------------------------

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pattern(n_y: int, n_x: int, seed: int, waves: int = 7, scale: float = 6.0):
    """A soft made-up pattern 0..1 (sums of waves), seamless in both directions."""
    import numpy as np
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n_y, 0:n_x].astype(np.float32)
    y /= n_y
    x /= n_x
    img = np.zeros((n_y, n_x), np.float32)
    for k in range(waves):
        fx, fy = (int(v) for v in rng.integers(1, int(scale * (k + 1)) + 1, 2))
        ph = rng.uniform(0, 2 * math.pi, 2)
        img += np.sin(2 * math.pi * fx * x + ph[0]) * np.cos(2 * math.pi * fy * y + ph[1]) / (k + 1)
    return (img - img.min()) / (img.max() - img.min() + 1e-9)


def _rgba(r, g, b):
    import numpy as np
    return np.stack([r, g, b, np.ones_like(r)], -1)


# ---------------------------------------------------------------------------
# Blender: making and cleaning up
# ---------------------------------------------------------------------------

class _Maker:
    """Keeps every datablock it makes, so the caller's file is left exactly as it was (``done``)."""

    def __init__(self, root: str, version: str):
        import bpy
        self.bpy = bpy
        self.root = root
        self.version = version
        self.made = []
        self.renamed = []            # (datablock, its own name): a caller's datablock that had one of our names
        self.scene = self.keep(bpy.data.scenes.new("FRP pack maker"))
        s = self.scene.render.image_settings
        s.file_format, s.color_depth, s.exr_codec = "OPEN_EXR", "16", "DWAA"

    def keep(self, idb):
        self.made.append(idb)
        return idb

    def claim(self, coll, name: str):
        """Make room for one of our names in ``bpy.data.<coll>`` (the caller's own datablock gets it back)."""
        old = getattr(self.bpy.data, coll).get(name)
        if old is not None and old not in self.made:
            self.renamed.append((old, name))
            old.name = f"{name} (kept aside {id(self)})"

    def new(self, coll: str, name: str, *args):
        self.claim(coll, name)
        idb = self.keep(getattr(self.bpy.data, coll).new(name, *args))
        if idb.name != name:
            raise RuntimeError(f"could not name {coll} {name!r}")
        return idb

    def path(self, rel: str) -> str:
        full = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        return full

    def picture(self, rel: str, rgba, colorspace: str = "sRGB"):
        """Write a picture: EXR (linear, half, DWAA) through the maker's own scene; PNG / JPEG as its bytes."""
        n_y, n_x = rgba.shape[:2]
        exr = rel.endswith(".exr")
        img = self.bpy.data.images.new("FRP pack maker picture", n_x, n_y, alpha=False, float_buffer=exr)
        try:
            if not exr:
                img.colorspace_settings.name = colorspace
            img.pixels.foreach_set(rgba.astype("float32").ravel())
            full = self.path(rel)
            if exr:
                img.save_render(full, scene=self.scene)
            else:
                img.filepath_raw = full
                img.file_format = "JPEG" if rel.endswith(".jpg") else "PNG"
                img.save()
        finally:
            self.bpy.data.images.remove(img)

    def load(self, rel: str, colorspace: str):
        img = self.keep(self.bpy.data.images.load(os.path.join(self.root, *rel.split("/"))))
        img.colorspace_settings.name = colorspace
        return img

    def write(self, rel: str, ids: set):
        """One asset per .blend: ``ids`` and what they use, picture paths relative to the .blend."""
        self.bpy.data.libraries.write(self.path(rel), ids, path_remap="RELATIVE_ALL", fake_user=True, compress=True)

    def done(self):
        bpy = self.bpy
        live = [i for i in reversed(self.made) if i is not None]
        try:
            bpy.data.batch_remove(live)
        except ReferenceError:
            for i in live:
                try:
                    getattr(bpy.data, _coll(i)).remove(i)
                except (ReferenceError, KeyError, RuntimeError):
                    pass
        for idb, name in self.renamed:
            idb.name = name


def _coll(idb) -> str:
    return {"NodeTree": "node_groups", "Material": "materials", "Image": "images", "Object": "objects",
            "Mesh": "meshes", "Collection": "collections", "Scene": "scenes"}.get(idb.bl_rna.identifier, "")


# ---------------------------------------------------------------------------
# the node groups (0344 2.3 contract: no BSDF, no Output, object coordinates in metres)
# ---------------------------------------------------------------------------

def _group(mk: _Maker, name: str, inputs: list, outputs: list):
    ng = mk.new("node_groups", name, "ShaderNodeTree")
    for sock, kind, default in inputs:
        s = ng.interface.new_socket(sock, in_out="INPUT", socket_type=kind)
        if default is not None:
            s.default_value = default
    for sock, kind in outputs:
        ng.interface.new_socket(sock, in_out="OUTPUT", socket_type=kind)
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    gi.location, go.location = (-800, 0), (600, 0)
    return ng, gi, go


COLOUR = ("Colour", "NodeSocketColor", (0.8, 0.8, 0.8, 1.0))
OUT = [("Colour", "NodeSocketColor"), ("Metallic", "NodeSocketFloat"), ("Roughness", "NodeSocketFloat"),
       ("Normal", "NodeSocketVector")]


def _value(ng, v: float):
    n = ng.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


def paint_satin(mk: _Maker):
    """Procedural: a fine orange-peel bump; roughness 0.36 (1.0.0) or 0.42 (1.1.0)."""
    ng, gi, go = _group(mk, "FRP paint_satin", [COLOUR, ("Peel size", "NodeSocketFloat", 0.002)], OUT)
    tc = ng.nodes.new("ShaderNodeTexCoord")
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 500.0          # ~2 mm on object coordinates in metres
    bump = ng.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.03
    L = ng.links.new
    L(tc.outputs["Object"], noise.inputs["Vector"])
    L(noise.outputs["Fac"], bump.inputs["Height"])
    L(gi.outputs["Colour"], go.inputs["Colour"])
    L(_value(ng, 0.0), go.inputs["Metallic"])
    L(_value(ng, ROUGH[mk.version]), go.inputs["Roughness"])
    L(bump.outputs["Normal"], go.inputs["Normal"])
    return ng


def cast_iron(mk: _Maker, colour_rel: str, rough_rel: str):
    """Two pictures, box-projected on object coordinates, 0.2 m per picture (Web 3D's tile)."""
    ng, gi, go = _group(mk, "FRP cast_iron", [COLOUR], OUT)
    tc = ng.nodes.new("ShaderNodeTexCoord")
    mp = ng.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 5.0, 5.0)
    L = ng.links.new
    L(tc.outputs["Object"], mp.inputs["Vector"])
    tex = {}
    for key, rel, cs in (("colour", colour_rel, "sRGB"), ("rough", rough_rel, "Non-Color")):
        n = ng.nodes.new("ShaderNodeTexImage")
        n.image = mk.load(rel, cs)
        n.projection, n.projection_blend = "BOX", 0.2
        L(mp.outputs["Vector"], n.inputs["Vector"])
        tex[key] = n
    mul = ng.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L(gi.outputs["Colour"], mul.inputs["A"])
    L(tex["colour"].outputs["Color"], mul.inputs["B"])
    bump = ng.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.1
    L(tex["rough"].outputs["Color"], bump.inputs["Height"])
    L(mul.outputs["Result"], go.inputs["Colour"])
    L(_value(ng, 1.0), go.inputs["Metallic"])
    L(tex["rough"].outputs["Color"], go.inputs["Roughness"])
    L(bump.outputs["Normal"], go.inputs["Normal"])
    return ng


def knurl_diamond(mk: _Maker):
    """The finish contract: colour / roughness / metallic + its numbers in; reads the face data (``fr_fx_*``, FACE
    attributes) and the pixel angle (View Layer); a stand-in pattern."""
    ng, gi, go = _group(mk, "FRP knurl_diamond",
                        [COLOUR, ("Roughness", "NodeSocketFloat", 0.3), ("Metallic", "NodeSocketFloat", 1.0),
                         ("Pitch", "NodeSocketFloat", 0.0008), ("Angle", "NodeSocketFloat", 30.0)],
                        OUT + [("Tangent", "NodeSocketVector"), ("Anisotropic", "NodeSocketFloat")])
    L = ng.links.new
    origin = ng.nodes.new("ShaderNodeAttribute")
    origin.attribute_type, origin.attribute_name = "GEOMETRY", "fr_fx_o"
    pixel = ng.nodes.new("ShaderNodeAttribute")
    pixel.attribute_type, pixel.attribute_name = "VIEW_LAYER", "fr_pixel_angle"
    geo = ng.nodes.new("ShaderNodeNewGeometry")
    rel = ng.nodes.new("ShaderNodeVectorMath")
    rel.operation = "SUBTRACT"
    L(geo.outputs["Position"], rel.inputs[0])
    L(origin.outputs["Vector"], rel.inputs[1])
    wave = ng.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 1000.0
    L(rel.outputs["Vector"], wave.inputs["Vector"])
    fade = ng.nodes.new("ShaderNodeMath")
    fade.operation = "LESS_THAN"
    L(pixel.outputs["Fac"], fade.inputs[0])
    L(gi.outputs["Pitch"], fade.inputs[1])
    height = ng.nodes.new("ShaderNodeMath")
    height.operation = "MULTIPLY"
    L(wave.outputs["Fac"], height.inputs[0])
    L(fade.outputs[0], height.inputs[1])
    bump = ng.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    L(height.outputs[0], bump.inputs["Height"])
    L(gi.outputs["Colour"], go.inputs["Colour"])
    L(gi.outputs["Metallic"], go.inputs["Metallic"])
    L(gi.outputs["Roughness"], go.inputs["Roughness"])
    L(bump.outputs["Normal"], go.inputs["Normal"])
    L(geo.outputs["Tangent"], go.inputs["Tangent"])
    L(_value(ng, 0.3), go.inputs["Anisotropic"])
    return ng


# ---------------------------------------------------------------------------
# meshes
# ---------------------------------------------------------------------------

def _boxes(boxes):
    """Vertices and quads of boxes ((x0, y0, z0), (x1, y1, z1)); faces point outwards."""
    verts, faces = [], []
    for (x0, y0, z0), (x1, y1, z1) in boxes:
        b = len(verts)
        verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                  (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces += [(b, b + 3, b + 2, b + 1), (b + 4, b + 5, b + 6, b + 7), (b, b + 1, b + 5, b + 4),
                  (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7)]
    return verts, faces


def _mesh(mk: _Maker, name: str, boxes, material, lods=None):
    me = mk.new("meshes", name)
    v, f = _boxes(boxes)
    me.from_pydata(v, [], f)
    me.materials.append(material)
    if lods is not None:
        a = me.attributes.new("fr_lod", "INT", "FACE")
        a.data.foreach_set("value", [lod for lod in lods for _ in range(6)])
    me.update()
    return me


def _plain_material(mk: _Maker, name: str, rgb, rough=0.6, image=None):
    """A whole material (props and environment modules bring their own; the contract of 2.3 is for group looks)."""
    mat = mk.new("materials", name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if image is not None:
        tc, mp, tex = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeMapping"), nt.nodes.new(
            "ShaderNodeTexImage")
        mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)       # 2 m per picture
        tex.image, tex.projection = image, "BOX"
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def pallet(mk: _Maker):
    """1.2 x 0.8 x 0.144 m, lowest point z = 0, facing -y. Level 1 = boards and blocks, level 2 = one box."""
    wood = _plain_material(mk, "FRP PALLET wood", (0.55, 0.42, 0.28))
    detailed = [((-0.6, -0.4, 0.122), (0.6, 0.4, 0.144))]                     # the top deck (as one board)
    for x in (-0.55, -0.05, 0.45):
        for y in (-0.4, -0.05, 0.3):
            detailed.append(((x, y, 0.022), (x + 0.1, y + 0.1, 0.122)))      # nine blocks
    for y in (-0.4, -0.05, 0.3):
        detailed.append(((-0.6, y, 0.0), (0.6, y + 0.1, 0.022)))             # three bottom boards
    light = [((-0.6, -0.4, 0.0), (0.6, 0.4, 0.144))]
    me = _mesh(mk, "FRP PALLET", detailed + light, wood, [1] * len(detailed) + [2] * len(light))
    ob = mk.new("objects", "FRP PALLET", me)
    ob["fr_size_m"] = [1.2, 0.8, 0.144]
    return ob


def factory(mk: _Maker, floor_picture: str):
    """An environment module set: a work bench (2 x 0.8 x 0.9 m) and a 4 x 4 m floor tile with its own floor
    material (``fr_env`` "floor": the key weather's tables and the code layout find it by)."""
    col = mk.new("collections", "FRP FACTORY")
    floor = _plain_material(mk, "FRP FACTORY floor", (0.5, 0.5, 0.48), 0.8, mk.load(floor_picture, "sRGB"))
    floor["fr_env"] = "floor"
    steel = _plain_material(mk, "FRP FACTORY bench", (0.2, 0.35, 0.55), 0.4)
    steel["fr_env"] = "bench"
    bench = [((-1.0, -0.4, 0.86), (1.0, 0.4, 0.9))] + [((x, y, 0.0), (x + 0.05, y + 0.05, 0.86))
                                                       for x in (-1.0, 0.95) for y in (-0.4, 0.35)]
    for name, boxes, mat, module in (("FRP FACTORY bench", bench, steel, "bench"),
                                     ("FRP FACTORY floor tile", [((-2, -2, -0.02), (2, 2, 0.0))], floor, "floor")):
        ob = mk.new("objects", name, _mesh(mk, name, boxes, mat))
        ob["fr_module"] = module
        col.objects.link(ob)
    col["fr_size_m"] = [4.0, 4.0, 0.9]
    return col


# ---------------------------------------------------------------------------
# the pack
# ---------------------------------------------------------------------------

def make(folder: str, version: str = "1.0.0", app_min: str = "0.0.1", app_max: str = "") -> dict:
    """Write the test pack ``version`` into ``folder`` (made if needed; an earlier test pack there is replaced, any
    other content is refused). Returns {"seconds", "bytes", "files", "folder"}. Leaves the open file as it was.
    The pack is written beside it first (``<folder>.making``) and moved in place only when it is whole."""
    if version not in VERSIONS:
        raise ValueError(f"the test pack has versions {', '.join(VERSIONS)}, not {version!r}")
    t0 = time.perf_counter()
    folder = os.path.abspath(folder)
    if os.path.isdir(folder) and os.listdir(folder):
        try:
            with open(os.path.join(folder, "pack.json"), encoding="utf-8") as f:
                ours = json.load(f).get("id") == PACK_ID
        except (OSError, ValueError, AttributeError):
            ours = False
        if not ours:
            raise ValueError(f"{folder} holds other files: the test pack is only written into an empty folder")
    work = folder + ".making"
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    try:
        got = _write(work, version, app_min, app_max)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.replace(work, folder)
    got.update(seconds=round(time.perf_counter() - t0, 2), folder=folder)
    return got


def _write(folder: str, version: str, app_min: str, app_max: str) -> dict:
    import numpy as np

    mk = _Maker(folder, version)
    rows = []
    try:
        # pictures at 1k and 2k (made by code, seamless)
        tex = {}
        for n, k in ((1024, "1k"), (2048, "2k")):
            a, b = _pattern(n, n, 7), _pattern(n, n, 11, scale=12.0)
            rough = b if version == "1.0.0" else 0.5 * b + 0.5 * _pattern(n, n, 13, scale=20.0)
            c = f"textures/{k}/test_cast_iron_colour_v1.jpg"
            r = f"textures/{k}/test_cast_iron_rough_{ROUGH_PICTURE[version]}.png"
            f = f"textures/{k}/test_concrete_colour_v1.jpg"
            mk.picture(c, _rgba(0.30 + 0.15 * a, 0.30 + 0.15 * a, 0.31 + 0.14 * a))
            mk.picture(r, _rgba(*(0.35 + 0.45 * rough,) * 3), "Non-Color")
            mk.picture(f, _rgba(0.45 + 0.2 * b, 0.45 + 0.2 * b, 0.43 + 0.18 * b))
            tex[k] = (c, r, f)
        # a light look's picture and a 360° photo (linear, equirectangular; Blender's rows start at the bottom)
        for rel, (n_y, n_x), boxes in (("lights/PRODUCT.exr", (1024, 2048), ((0.30, 8.0), (0.70, 3.0))),
                                       ("hdri/test_hall_1k.exr", (512, 1024), ((0.5, 12.0),)),
                                       ("hdri/test_hall_2k.exr", (1024, 2048), ((0.5, 12.0),))):
            v = np.linspace(0, 1, n_y, dtype=np.float32)[:, None] * np.ones((1, n_x), np.float32)
            sky = _rgba(0.3 + 0.5 * v, 0.3 + 0.5 * v, 0.32 + 0.55 * v)
            for cx, power in boxes:
                x0, x1 = int(n_x * (cx - 0.04)), int(n_x * (cx + 0.04))
                sky[int(n_y * 0.62):int(n_y * 0.80), x0:x1, :3] = power
            mk.picture(rel, sky)

        def row(full_id, file, datablock, rgb, **extra):
            kind, code = full_id.split(":")
            pic = f"pictures/{kind}.{code}.jpg"
            mk.picture(pic, _rgba(*(np.full((256, 256), c, np.float32) for c in rgb)))
            rows.append({**dict(id=full_id, kind=kind, file=file, datablock=list(datablock) if datablock else None,
                                picture=pic, set=SET, since="1.0.0", changed="", contract=1), **extra})
            return rows[-1]

        mk.write("materials/paint_satin.blend", {paint_satin(mk)})
        row("material:paint_satin", "materials/paint_satin.blend", ("node_groups", "FRP paint_satin"),
            (0.2, 0.35, 0.6), cost=1.05, size_m=0.2, changed="1.1.0" if version == "1.1.0" else "")
        c2, r2, _ = tex["2k"]
        mk.write("materials/cast_iron.blend", {cast_iron(mk, c2, r2)})
        row("material:cast_iron", "materials/cast_iron.blend", ("node_groups", "FRP cast_iron"), (0.3, 0.3, 0.31),
            cost=1.12, size_m=0.2, textures=[tex["1k"][0], tex["1k"][1], c2, r2],
            changed="1.1.0" if version == "1.1.0" else "")
        mk.write("finishes/knurl_diamond.blend", {knurl_diamond(mk)})
        row("finish:knurl_diamond", "finishes/knurl_diamond.blend", ("node_groups", "FRP knurl_diamond"),
            (0.6, 0.6, 0.62), cost=1.2, size_m=0.2)
        row("light:PRODUCT", "lights/PRODUCT.exr", None, (0.85, 0.85, 0.85), cost=1.0)
        row("hdri:test_hall", "hdri/test_hall_2k.exr", None, (0.5, 0.55, 0.62), fallback="light:OVERCAST",
            textures=["hdri/test_hall_1k.exr"])
        mk.write("props/PALLET.blend", {pallet(mk)})
        row("prop:PALLET", "props/PALLET.blend", ("objects", "FRP PALLET"), (0.55, 0.42, 0.28), cost=1.0,
            size_m=[1.2, 0.8, 0.144])
        mk.write("environments/FACTORY.blend", {factory(mk, tex["2k"][2])})
        row("environment:FACTORY", "environments/FACTORY.blend", ("collections", "FRP FACTORY"), (0.5, 0.5, 0.48),
            cost=1.0, textures=[tex["1k"][2], tex["2k"][2]], size_m=[4.0, 4.0, 0.9])
    finally:
        mk.done()

    with open(os.path.join(folder, "LICENSE-ASSETS.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(LICENCE)
    for r in rows:
        if r["datablock"] is None:
            del r["datablock"]
    files = {}
    for base, _dirs, names in os.walk(folder):
        for n in sorted(names):
            full = os.path.join(base, n)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            if rel != "pack.json":
                files[rel] = {"bytes": os.path.getsize(full), "sha256": sha256(full)}
    pack = {"format": "fresing-assets", "format_version": 1, "id": PACK_ID,
            "title": "Fresing assets – test pack (made up)", "version": version, "app_min": app_min,
            "app_max": app_max, "contract": 1, "licence": "LICENSE-ASSETS.txt", "licence_id": "test-cc0",
            "qualities": {"draft": "1k", "normal": "2k", "final": "4k"},
            "sets": {SET: {"title": "Test set (made up)", "approved": "2026-11-25", "since": "1.0.0",
                           "budget_mb": 40}},
            "files": dict(sorted(files.items())), "assets": rows}
    with open(os.path.join(folder, "pack.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(pack, f, indent=1)
        f.write("\n")
    total = sum(v["bytes"] for v in files.values()) + os.path.getsize(os.path.join(folder, "pack.json"))
    return {"bytes": total, "files": len(files) + 1}
