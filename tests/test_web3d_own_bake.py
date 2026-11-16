"""Task 0161 (bug hunt 0147, row 10): marine looks follow world height, up and the part's own axes, so a flat 0.2 m
tile cannot carry them – the page showed plain paint. Parts with a marine look are baked on their own UVs where they
stand: the page's colour below the waterline is the growth, above it the paint."""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, materials, web3d  # noqa: E402
from fresing_render.blender import marine_looks as ML  # noqa: E402
from fresing_render.core import web3d as core  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _plate(sc, name, z0=-2.0, z1=5.0, nx=4, nz=28, turn=30.0):
    """An upright plate 1 m wide from world z ``z0`` to ``z1``, turned about z (object and world axes differ)."""
    co, faces = [], []
    for j in range(nz + 1):
        for i in range(nx + 1):
            co.append((-0.5 + i / nx, 0.0, z0 + (z1 - z0) * j / nz))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(co, [], faces)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob[build.PROP_KIND] = "part"
    ob.rotation_euler.z = math.radians(turn)
    return ob


def _picture(doc, binary, tex, tmp_path):
    """A texture of the file as (h, w, 3) floats, row 0 at the top (glTF's v = 0)."""
    img = doc["images"][doc["textures"][tex]["source"]]
    raw = core.view_bytes(doc, binary, img["bufferView"])
    p = tmp_path / f"t{tex}.{'png' if raw[:4] == b'\x89PNG' else 'jpg'}"
    p.write_bytes(raw)
    im = bpy.data.images.load(str(p))
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1, :, :3]


def test_growth_band_reaches_the_page(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    ob = _plate(sc, "plate")
    plain = _plate(sc, "plain", z0=0.0, z1=1.0, nz=2)
    plain.location.x = 3.0
    materials.assign(ob, materials.ensure_material("G growth", "paint_marine_growth", "RAL 1023", 0.0))
    materials.assign(plain, materials.ensure_material("G plain", "paint", "RAL 1023", 0.0))
    sc[ML.WATERLINE] = 0.0
    bpy.context.view_layer.update()
    assert web3d.needs_own_bake(ob) and not web3d.needs_own_bake(plain) and web3d.has_marine_looks()
    out = web3d.export(sc, str(tmp_path / "plate.glb"), size=256, compress=False, page=False)
    assert out["own"]["parts"] == 1 and "marine looks baked on 1 part" in out["text"]
    doc, binary = core.read_glb((tmp_path / "plate.glb").read_bytes())
    part = next(n for n in doc["nodes"] if n.get("name") == "Part 1")
    child = doc["nodes"][part["children"][0]] if "children" in part else part
    prim = doc["meshes"][child["mesh"]]["primitives"][0]
    mat = doc["materials"][prim["material"]]
    info = mat["pbrMetallicRoughness"]["baseColorTexture"]
    assert "extensions" not in info                           # its own UVs, not the tiles' repeat
    assert "normalTexture" in mat                             # the growth's relief, a tangent-space map
    pos = core.accessor_array(doc, binary, prim["attributes"]["POSITION"]).astype(np.float64)
    pos = pos * np.array(child.get("scale", [1, 1, 1])) + np.array(child.get("translation", [0, 0, 0]))
    uv = core.accessor_array(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float64)
    pic = _picture(doc, binary, info["index"], tmp_path)
    h, w = pic.shape[:2]
    col = pic[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)]
    lum = col.mean(1)
    z = pos[:, 2]                                             # the plate turns about z only: local z = world z
    lo, _hi = ML.growth_band()
    below, above = z < lo - 0.6, z > 3.4                      # deep in the growth; above the splash zone's rust
    assert below.sum() > 5 and above.sum() > 5
    assert lum[below].mean() < 0.6 * lum[above].mean(), (lum[below].mean(), lum[above].mean())
    # above the splash zone the paint is RAL 1023 as on the plain plate (yellow: red and green over blue)
    assert (col[above][:, 0] > col[above][:, 2] + 0.2).all()
