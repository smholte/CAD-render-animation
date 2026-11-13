"""Web 3D model (task 0099), no Blender: the glTF writer and reader, UVs, welding, seamless tiles, the viewer page."""

import base64
import json
import math
import re

import numpy as np
import pytest

from fresing_render.core import web3d as core


def _cube():
    pos = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], np.float32) * 0.5
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tri = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))], np.int64)
    return pos, tri


def _glb(n_nodes=2, uv=True):
    pos, tri = _cube()
    g = core.Gltf()
    vert = tri.ravel()
    p = pos[tri]
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    nrm = np.repeat(fn / np.linalg.norm(fn, axis=1, keepdims=True), 3, axis=0)
    cuv = core.box_uv(pos, tri).reshape(-1, 2) if uv else None
    vidx, qn, uvw, inverse = core.weld(vert, nrm, cuv)
    tex = g.texture(core.png(np.full((4, 4, 3), 200, np.uint8)))
    m = g.material({"name": "Look 1", "pbrMetallicRoughness": {"baseColorTexture": {"index": tex,
                                                                                    "extensions": core.UV_TRANSFORM}}})
    mesh = g.mesh("Mesh 1", pos[vidx], qn, uvw, [(m, inverse.reshape(-1, 3))], tiled_uv=True)
    root = g.node({"name": "Model", "rotation": list(core.Z_UP_TO_Y_UP)})
    for k in range(n_nodes):
        g.place_mesh({"name": f"Part {k + 1}", "translation": [k * 1.0, 0, 0]}, mesh, root)
    return g


def test_glb_round_trip_and_rules():
    data = _glb().glb()
    assert core.problems(data) == []
    doc, binary = core.read_glb(data)
    assert doc["asset"]["version"] == "2.0"
    assert "KHR_mesh_quantization" in doc["extensionsRequired"]
    s = core.summary(data)
    assert s["parts"] == 2 and s["meshes"] == 1 and s["triangles"] == 24 and s["unique_triangles"] == 12
    assert s["textures"] == 1 and s["names"] == ["Model", "Part 1", "Part 2"]
    prim = doc["meshes"][0]["primitives"][0]
    acc = doc["accessors"][prim["attributes"]["POSITION"]]
    assert acc["componentType"] == core.SHORT                    # 16-bit points ...
    child = doc["nodes"][doc["nodes"][1]["children"][0]]          # ... turned back into metres by a child node
    assert child["mesh"] == 0 and "name" not in child
    pos = core.accessor_array(doc, binary, prim["attributes"]["POSITION"]) * child["scale"][0] + child["translation"]
    assert pos.min() == pytest.approx(0.0, abs=core.POS_STEP) and pos.max() == pytest.approx(0.5, abs=core.POS_STEP)
    assert acc["max"] == [int(v) for v in core.accessor_array(doc, binary, prim["attributes"]["POSITION"]).max(0)]
    nrm = core.accessor_array(doc, binary, prim["attributes"]["NORMAL"])
    assert np.allclose(np.linalg.norm(nrm, axis=1), 1.0, atol=0.02)
    # flat sides: 4 corners each, 24 vertices for a box with sharp edges
    assert len(pos) == 24
    for v in doc["bufferViews"]:
        assert v["byteOffset"] % 4 == 0
        assert v.get("byteStride", 4) % 4 == 0


def test_tiled_uvs_are_16_bit_and_scaled_back():
    data = _glb().glb()
    doc, binary = core.read_glb(data)
    assert {"KHR_texture_transform", "KHR_mesh_quantization"} <= set(doc["extensionsRequired"])
    prim = doc["meshes"][0]["primitives"][0]
    acc = doc["accessors"][prim["attributes"]["TEXCOORD_0"]]
    assert acc["componentType"] == core.SHORT and "normalized" not in acc
    uv = core.accessor_array(doc, binary, prim["attributes"]["TEXCOORD_0"]) / core.UV_Q
    pos, tri = _cube()
    want = core.box_uv(pos, tri).reshape(-1, 2)
    want[:, 1] = 1 - want[:, 1]
    shift = uv.min(0) - want.min(0)                               # whole tiles may be taken off (the look repeats)
    assert shift == pytest.approx(np.round(shift))
    assert {tuple(np.round(r - shift, 3)) for r in uv} <= {tuple(np.round(r, 3)) for r in want}


def test_big_parts_keep_32_bit_points():
    g = core.Gltf()
    pos = np.array([[0, 0, 0], [10.0, 0, 0], [0, 1, 0]])          # 10 m: steps would be 0.15 mm
    nrm = core.quantize_normals(np.tile([0, 0, 1.0], (3, 1)))
    m = g.mesh("Big", pos, nrm, None, [(None, np.array([[0, 1, 2]]))])
    assert g.dequantize[m] is None
    big = g.mesh("Big, no decal", pos, nrm, None, [(None, np.array([[0, 1, 2]]))], max_step=core.POS_STEP_BIG)
    assert g.dequantize[big][1] == pytest.approx(10.0 / 65000)
    g.place_mesh({"name": "Part 1"}, m)
    data = g.glb()
    assert core.problems(data) == []
    doc, _ = core.read_glb(data)
    assert doc["nodes"][0]["mesh"] == 0 and doc["accessors"][0]["componentType"] == core.FLOAT
    assert core.summary(data)["parts"] == 1


def test_problems_finds_broken_files():
    assert core.problems(b"nonsense" * 4)
    data = bytearray(_glb().glb())
    doc, binary = core.read_glb(bytes(data))
    doc["meshes"][0]["primitives"][0]["material"] = 7
    js = json.dumps(doc).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    import struct
    bad = (struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)) + struct.pack("<II", len(js), 0x4E4F534A)
           + js + struct.pack("<II", len(binary), 0x004E4942) + binary)
    assert any("no such material" in p for p in core.problems(bad))


def test_box_uv_scale_and_handedness():
    pos, tri = _cube()
    uv = core.box_uv(pos, tri)
    assert uv.shape == (12, 3, 2)
    # a 0.5 m side is 2.5 tiles of 0.2 m
    span = uv.max(axis=1) - uv.min(axis=1)                        # per triangle, per direction
    assert span.max() == pytest.approx(0.5 / core.TILE_M)
    p = pos[tri].astype(np.float64)
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    for t in range(len(tri)):          # U x V of each triangle's mapping agrees with its outward normal
        e1, e2 = p[t, 1] - p[t, 0], p[t, 2] - p[t, 0]
        d1, d2 = uv[t, 1] - uv[t, 0], uv[t, 2] - uv[t, 0]
        det = d1[0] * d2[1] - d1[1] * d2[0]
        assert det > 0, f"triangle {t} is mirrored in its texture"
        dpdu = (e1 * d2[1] - e2 * d1[1]) / det
        dpdv = (e2 * d1[0] - e1 * d2[0]) / det
        assert np.dot(np.cross(dpdu, dpdv), fn[t]) > 0


def test_weld_shares_corners_but_keeps_sharp_edges():
    vert = np.array([0, 1, 2, 0, 2, 3])
    n_up = np.tile([0.0, 0.0, 1.0], (6, 1))
    vidx, qn, uv, inv = core.weld(vert, n_up, None)
    assert len(vidx) == 4 and uv is None
    assert np.array_equal(vidx[inv], vert)
    n_mix = n_up.copy()
    n_mix[3:] = [1.0, 0.0, 0.0]                      # the second triangle faces another way: corners split
    vidx, qn, uv, inv = core.weld(vert, n_mix, None)
    assert len(vidx) == 6
    uvs = np.zeros((6, 2))
    uvs[3:] = 0.5
    vidx, qn, uv, inv = core.weld(vert, n_up, uvs)
    assert len(vidx) == 6 and uv.shape == (6, 2)


def test_quantized_normals():
    q = core.quantize_normals(np.array([[0, 0, 2.0], [1, 1, 0], [0, 0, 0]]))
    assert q.dtype == np.int8
    assert q[0].tolist() == [0, 0, 127]
    assert q[1].tolist() == [90, 90, 0]
    assert q[2].tolist() == [0, 0, 127]               # no direction: up, never NaN


def test_seamless_tiles_repeat_without_a_seam():
    rng = np.random.default_rng(1)
    t = rng.random((64, 64, 1)).astype(np.float32)
    t = (t + np.roll(t, 1, 0) + np.roll(t, 1, 1)) / 3            # some smooth noise
    s = core.seamless(t)
    assert s.shape == t.shape
    inner = np.abs(np.diff(s, axis=1)).mean()
    across = np.abs(s[:, 0] - s[:, -1]).mean()                    # the step where the tile meets its copy
    assert across < 1.6 * inner
    across_v = np.abs(s[0] - s[-1]).mean()
    assert across_v < 1.6 * np.abs(np.diff(s, axis=0)).mean()
    assert np.std(s) == pytest.approx(np.std(t), rel=0.25)        # the noise keeps its strength
    assert abs(np.mean(s) - np.mean(t)) < 0.01


def test_flat_tiles_become_numbers():
    t = np.full((32, 32, 3), 0.4, np.float32)
    assert core.is_flat(t)
    t[0, 0] = 0.9                                     # one stray pixel does not make a texture
    assert core.is_flat(t)
    t[:, :16] = 0.6
    assert not core.is_flat(t)


def test_flat_normal_maps():
    n = np.zeros((16, 16, 3), np.float32)
    n[..., 2] = 1.0
    assert core.normal_flat(n)
    n[..., 0] = 0.006                                 # 0.3°: the orange peel of satin paint, too fine for 8 bits
    assert core.normal_flat(n)
    n[::2, :, 0] = 0.05                               # 3°: a cast surface
    assert not core.normal_flat(n)


def test_colours_and_pictures():
    assert core.linear_to_srgb(np.array([0.0, 1.0]))[1] == pytest.approx(1.0)
    assert core.linear_to_srgb(np.array([0.2140]))[0] == pytest.approx(0.5, abs=0.002)
    png = core.png(np.zeros((3, 5, 4), np.uint8))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert core.image_size(png) == (5, 3)


def test_decompose_matrices():
    a = math.radians(30)
    m = np.eye(4)[None].repeat(3, 0)
    for k, ang in enumerate((0.0, a, 2 * a)):
        c, s = math.cos(ang), math.sin(ang)
        m[k, :3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
        m[k, :3, 3] = [k, 2 * k, 0]
    t, q, s = core.decompose(m)
    assert t[2] == pytest.approx([2, 4, 0])
    assert s == pytest.approx(np.ones((3, 3)))
    assert q[1] == pytest.approx([0, 0, math.sin(a / 2), math.cos(a / 2)])
    assert np.allclose(core.quat_to_matrix(q[2]), m[2, :3, :3])
    # no sign flip between frames
    assert all(np.dot(q[i], q[i + 1]) > 0 for i in range(2))


def test_animation_channels():
    g = _glb(1)
    t = np.array([[0, 0, 0], [1, 0, 0]], np.float32)
    g.animation("Move", np.array([0.0, 1.0]), [(1, "translation", t)])
    data = g.glb()
    assert core.problems(data) == []
    doc, _ = core.read_glb(data)
    assert doc["animations"][0]["channels"][0]["target"] == {"node": 1, "path": "translation"}
    assert core.summary(data)["animations"] == 1


def test_words():
    assert core.mb(312_492) == "0.3 MB"
    assert core.mb(23_400_000) == "23 MB"
    assert core.result_line(312_492, 2693, 3, 5.51) == "0.3 MB · 2,693 triangles · 3 textures · 5.5 s"
    assert core.result_line(1, 1, 1, 0.0).count("1 triangle ") == 1
    assert core.header(0) == ""
    assert core.safe_name('Mill: "A"/B') == "Mill_ _A__B"
    assert core.safe_name("  ") == "Model"


def test_viewer_page_is_one_file():
    data = _glb().glb()
    page = core.viewer_html("Test <mill>", glb=data, script_text="console.log('x</script>')")
    assert "Test &lt;mill&gt;" in page
    assert "x<\\/script>" in page                    # the inlined script cannot end its own tag
    b64 = re.search(r'id="glb">([^<]+)</script>', page).group(1)
    assert base64.b64decode(b64) == data
    # nothing comes from the internet
    assert not re.search(r'(src|href)="https?://', page)


def test_viewer_page_with_the_real_viewer():
    js = core.viewer_script()
    assert len(js) > 400_000 and "model-viewer" in js
    page = core.viewer_html("Site", src="../media/x.glb", script_src="../vendor/" + core.MV_FILE)
    assert 'src="../media/x.glb"' in page and f'<script src="../vendor/{core.MV_FILE}">' in page
    assert len(page) < 10_000                          # the script is not inlined here
    import os
    assert os.path.isfile(os.path.join(core.WEB_DIR, "LICENSE-model-viewer.txt"))
