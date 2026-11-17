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
    img = doc["images"][core.texture_image(doc, tex)]
    raw = core.view_bytes(doc, binary, img["bufferView"])
    p = tmp_path / f"t{tex}.{'png' if raw[:4] == b'\x89PNG' else 'webp' if core.is_webp(raw) else 'jpg'}"
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


def _tower(sc, name, height=90.0, radius=3.0, z0=-5.0, nz=60, n=48):
    """An upright round tower (a turbine's) from world z ``z0``: its marine looks need the part's own bake."""
    co, faces = [], []
    for j in range(nz + 1):
        for i in range(n):
            a = 2 * math.pi * i / n
            co.append((radius * math.cos(a), radius * math.sin(a), z0 + height * j / nz))
    for j in range(nz):
        for i in range(n):
            a, b = j * n + i, j * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    me = bpy.data.meshes.new(name)
    me.from_pydata(co, [], faces)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob[build.PROP_KIND] = "part"
    return ob


def _tower_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    ob = _tower(sc, "tower")
    materials.assign(ob, materials.ensure_material("T growth", "paint_marine_growth", "RAL 1023", 0.0))
    sc[ML.WATERLINE] = 0.0
    bpy.context.view_layer.update()
    return sc


def test_fine_marine_detail_on_a_tower(tmp_path):
    """Task 0165: Normal is today's file; Fine gives the tower pixels at least 3 x finer than Normal (<= 14 mm of a
    90 m tower, 4096 px pictures), the page still shows growth below the waterline and paint above it, and the
    estimate the panel shows says Fine costs more."""
    sc = _tower_scene()
    a = web3d.export(sc, str(tmp_path / "n.glb"), size=256, compress=False, page=False)
    b = web3d.export(sc, str(tmp_path / "f.glb"), size=256, compress=False, page=False, marine_detail="FINE")
    c = web3d.export(sc, str(tmp_path / "n2.glb"), size=256, compress=False, page=False, marine_detail="NORMAL")
    assert (tmp_path / "n.glb").read_bytes() == (tmp_path / "n2.glb").read_bytes()      # Normal: the same file
    mm_n, mm_f = a["own"]["coarsest_mm"], b["own"]["coarsest_mm"]
    print(f"MEASURED tower: Normal {mm_n:.1f} mm {a['size'] / 1e6:.2f} MB {a['own']['seconds']:.1f} s; "
          f"Fine {mm_f:.1f} mm {b['size'] / 1e6:.2f} MB {b['own']['seconds']:.1f} s")
    assert mm_f <= 14.0 and mm_f < mm_n / 2.5, (mm_n, mm_f)
    assert "Marine detail Fine" in a["text"] and "Marine detail Fine" not in b["text"]
    assert b["size"] > a["size"]
    doc, binary = core.read_glb((tmp_path / "f.glb").read_bytes())
    prim = doc["meshes"][0]["primitives"][0]
    node = next(n for n in doc["nodes"] if "mesh" in n)
    mat = doc["materials"][prim["material"]]
    info = mat["pbrMetallicRoughness"]["baseColorTexture"]
    pos = core.accessor_array(doc, binary, prim["attributes"]["POSITION"]).astype(np.float64)
    pos = pos * np.array(node.get("scale", [1, 1, 1])) + np.array(node.get("translation", [0, 0, 0]))
    uv = core.accessor_array(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float64)
    pic = _picture(doc, binary, info["index"], tmp_path)
    assert pic.shape[0] > 2048                                 # a picture of 4096 px, for this bake only
    h, w = pic.shape[:2]
    col = pic[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)]
    z = pos[:, 2]                                              # the tower stands upright: local z = world z
    lum = col.mean(1)
    below, above = z < -2.0, z > 30.0
    assert below.sum() > 5 and above.sum() > 5
    assert lum[below].mean() < 0.6 * lum[above].mean()
    est = web3d.marine_estimate(sc)
    assert est["FINE"]["mm"] < est["NORMAL"]["mm"] / 2 and est["FINE"]["bytes"] > est["NORMAL"]["bytes"]


def test_marine_detail_core_numbers():
    assert core.own_tpm(1024, 1e4, "NORMAL") == pytest.approx(math.sqrt(core.OWN_BUDGET / 1e4))
    assert core.own_tpm(1024, 1e4, "FINE") == pytest.approx(2 * core.own_tpm(1024, 1e4, "NORMAL"))
    n, f = core.own_estimate(1700.0, 1024), core.own_estimate(1700.0, 1024, "FINE")
    assert f["mm"] < n["mm"] and f["bytes"] > n["bytes"] and f["seconds"] > n["seconds"]
    assert "Fine makes them finer" in core.own_line(1, 20.0, 40.0)
    assert "Fine" not in core.own_line(1, 20.0, 40.0, "FINE") and "Fine" not in core.own_line(1, 2.0, 5.0)


def _base_picture(doc, binary, node_name, tmp_path):
    """(the node's mesh index, (local z, colour) of each of its points read from its base colour picture)."""
    part = next(n for n in doc["nodes"] if n.get("name") == node_name)
    child = doc["nodes"][part["children"][0]] if "children" in part else part
    prim = doc["meshes"][child["mesh"]]["primitives"][0]
    tex = doc["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    pic = _picture(doc, binary, tex, tmp_path)
    pos = core.accessor_array(doc, binary, prim["attributes"]["POSITION"]).astype(np.float64)
    pos = pos * np.array(child.get("scale", [1, 1, 1])) + np.array(child.get("translation", [0, 0, 0]))
    uv = core.accessor_array(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float64)
    h, w = pic.shape[:2]
    col = pic[np.clip((uv[:, 1] * h).astype(int), 0, h - 1), np.clip((uv[:, 0] * w).astype(int), 0, w - 1)]
    return child["mesh"], pos[:, 2], col


def _bands(z, col):
    """The mean colour in 0.5 m bands of height (the growth band, the splash zone, the paint)."""
    k = np.floor(z / 0.5).astype(int)
    return {int(b): col[k == b].mean(axis=0) for b in np.unique(k)}


def test_copies_share_one_marine_bake(tmp_path):
    """Task 0189 (0183 row 9): the demo's wind park baked every clamp of every turbine on its own (264 bakes, ~7 s each,
    36 min). Copies with the same mesh and looks at the same height and tilt share one bake – also turned about the
    vertical and moved across – and give the same picture as their own bake; a copy at another height bakes its own."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    first = _plate(sc, "first", nz=14)
    materials.assign(first, materials.ensure_material("G growth", "paint_marine_growth", "RAL 1023", 0.0))
    copies = []
    for k, (dx, turn, dz) in enumerate(((4.0, 75.0, 0.0), (8.0, -40.0, 0.0), (12.0, 30.0, 1.0))):
        c = first.copy()                                     # the same mesh and material, as the importer's copies
        c.name = f"copy {k}"
        sc.collection.objects.link(c)
        c.location = (dx, 2.0 * k, dz)
        c.rotation_euler.z = math.radians(turn)
        copies.append(c)
    sc[ML.WATERLINE] = 0.0
    bpy.context.view_layer.update()
    out = web3d.export(sc, str(tmp_path / "copies.glb"), size=256, compress=False, page=False, hide_names=False)
    assert out["own"]["parts"] == 4 and out["own"]["bakes"] == 2, out["own"]      # the raised copy bakes its own
    assert "marine looks baked on 4 parts" in out["text"] and "copies share: 2 bakes" in out["text"], out["text"]
    doc, binary = core.read_glb((tmp_path / "copies.glb").read_bytes())
    m0, z0, c0 = _base_picture(doc, binary, "first", tmp_path)
    m1, z1, c1 = _base_picture(doc, binary, "copy 1", tmp_path)
    m2, z2, c2 = _base_picture(doc, binary, "copy 2", tmp_path)
    assert m0 == m1 and m2 != m0                              # one mesh in the file for the shared ones
    b0, b2 = _bands(z0, c0), _bands(z2, c2)                   # (copy 2 stands 1 m higher: its own band)
    assert max(float(np.abs(b0[k] - b2[k]).max()) for k in b0) > 0.1
    # the same look as its own bake: copy 1 exported alone
    for ob in [first] + copies:
        ob.hide_set(ob.name != "copy 1")
    bpy.context.view_layer.update()
    alone = web3d.export(sc, str(tmp_path / "alone.glb"), size=256, compress=False, page=False, hide_names=False)
    assert alone["own"]["bakes"] == 1
    doc_a, bin_a = core.read_glb((tmp_path / "alone.glb").read_bytes())
    _m, za, ca = _base_picture(doc_a, bin_a, "copy 1", tmp_path)
    ba, b1 = _bands(za, ca), _bands(z1, c1)
    assert set(ba) == set(b1)
    worst = max(float(np.abs(ba[k] - b1[k]).max()) for k in ba)
    assert worst < 0.03, worst


def test_panel_estimates_are_kept_until_something_changes(monkeypatch):
    """Task 0189 (0183 row 17): every draw of the Web 3D panel walked every part (45–60 ms on the small demo). The
    estimates are kept until the scene changes (a depsgraph update, undo, a file load); the marine estimate
    counts the bakes copies share."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    first = _plate(sc, "first", nz=14)
    materials.assign(first, materials.ensure_material("G growth", "paint_marine_growth", "RAL 1023", 0.0))
    for k in range(3):
        c = first.copy()
        sc.collection.objects.link(c)
        c.location.x = 4.0 * (k + 1)
    bpy.context.view_layer.update()
    w = web3d.settings(sc)
    w.light = "SOFT"
    bpy.context.view_layer.update()
    calls = []
    real = web3d.objects
    monkeypatch.setattr(web3d, "objects", lambda scene: calls.append(1) or real(scene))

    def draw():                                              # what the panel draws (the button's check stays exact)
        return None, web3d.marine_estimate(sc), web3d.light_estimate(sc)

    a = draw()
    n = len(calls)
    assert n > 0 and a[1]["NORMAL"]["bakes"] == 1            # four copies, one bake
    for _ in range(5):
        assert draw() == a
    assert len(calls) == n                                   # nothing changed: no part walked again
    first.location.z += 1.0                                  # a change: one copy now stands higher
    bpy.context.view_layer.update()
    b = draw()
    assert len(calls) > n and b[1]["NORMAL"]["bakes"] == 2
    one = core.own_estimate(10.0, 1024, bakes=1, unique_area=10.0)
    many = core.own_estimate(10.0, 1024, bakes=40, unique_area=10.0)
    assert many["seconds"] - one["seconds"] == pytest.approx(39 * core.OWN_SECONDS_PER_BAKE)


def test_the_bake_scene_does_not_pull_in_the_project():
    """Task 0189 (0183 row 9): the bake scene is a copy of the project's scene. It kept the compositor's tree (whose
    Render Layers node reads the project's scene) and the project's settings (labels pointing at parts …), so every bake
    built the depsgraph of the whole project: 0.6 s per bake on the small demo, 0.07 s without."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    ob = _plate(sc, "project part", nz=2)
    from fresing_render.blender import callouts
    callouts.add(sc, ob, ob.matrix_world.translation, text="A label on the part")
    tree = bpy.data.node_groups.new("comp", "CompositorNodeTree")
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.scene = sc
    if hasattr(sc, "compositing_node_group"):
        sc.compositing_node_group = tree
    sc["fr_some_object"] = ob
    bpy.context.view_layer.update()
    b = web3d.Baker(sc)
    try:
        bake_vl = b.scene.view_layers[0]
        with bpy.context.temp_override(scene=b.scene, view_layer=bake_vl):
            dg = bpy.context.evaluated_depsgraph_get()
            names = {i.original.name for i in dg.ids}
        assert ob.name not in names and sc.name not in names, sorted(names)
        assert sc.fresing.callouts and sc.get("fr_some_object") is ob          # the project keeps its own
    finally:
        b.close()
