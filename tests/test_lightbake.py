"""Baked light (task 0107) in Blender: the bake function another lane calls (results per object id, own UV set 1,
per-vertex light, Soft vs Everything, Cancel, the project left as it was) and the web 3D export with baked light
(per-copy light UVs on shared accessors, occlusion map, the page's settings, Blender reads the file back)."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import lightmap as lm
from fresing_render.core import web3d as core
from fresing_render.core import web3d_env as env

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, lightbake, web3d  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
FAST = {"samples": 8, "quality": "DRAFT"}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _sky_world(sc, elevation=35.0, rotation=0.0):
    w = bpy.data.worlds.new("Test sky")
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sun_elevation = math.radians(elevation)
    sky.sun_rotation = math.radians(rotation)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.08
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    sc.world = w
    return w


def block_scene():
    """A 6 m floor with a 1 m box on it (two copies of one box mesh), lit by a sky with its sun at 35°."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    _sky_world(sc)
    bpy.ops.mesh.primitive_plane_add(size=6.0)
    floor = bpy.context.object
    floor.name = "Floor"
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.2, 0.0, 0.5))
    box = bpy.context.object
    box.name = "Box A"
    box2 = box.copy()
    box2.name = "Box B"
    box2.location = (1.6, 1.6, 0.5)
    sc.collection.objects.link(box2)
    bpy.context.view_layer.update()
    return sc, floor, box, box2


def _counts():
    return (len(bpy.data.scenes), len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials),
            len(bpy.data.images), len(bpy.data.worlds))


def _sample(item, x, y, ob):
    """The baked light at the world point (x, y) on the floor: the texel under that point."""
    me = ob.data
    inv = ob.matrix_world.inverted()
    p = inv @ __import__("mathutils").Vector((x, y, 0.0))
    lt = me.loop_triangles
    for k, t in enumerate(lt):
        a, b, c = (me.vertices[i].co for i in t.vertices)
        from mathutils.geometry import barycentric_transform
        uvs = item.uv[k * 3:k * 3 + 3]
        bc = barycentric_transform(p, a, b, c, (1, 0, 0), (0, 1, 0), (0, 0, 1))
        if min(bc) >= -1e-6 and abs(sum(bc) - 1.0) < 1e-4:
            u = bc[0] * uvs[0] + bc[1] * uvs[1] + bc[2] * uvs[2]
            h, w = item.pixels.shape[:2]
            return item.pixels[int(u[1] * h), int(u[0] * w)]
    raise AssertionError("point not on the floor")


@pytest.fixture(scope="module")
def soft_and_all():
    sc, floor, box, box2 = block_scene()
    before = _counts()
    obs = [floor, box, box2]
    soft = lightbake.bake(obs, "Soft light baked, sun live", uv="AUTO", texels_per_m=24, **FAST)
    after_soft = _counts()
    every = lightbake.bake(obs, "ALL", uv="AUTO", texels_per_m=24, **FAST)
    return {"scene": sc, "floor": floor, "box": box, "box2": box2, "soft": soft, "all": every, "before": before,
            "after": after_soft, "after_all": _counts()}


def test_every_object_gets_its_own_result(soft_and_all):
    res = soft_and_all["soft"]
    assert res.light == "SOFT"
    assert set(res.items) == {"Floor", "Box A", "Box B"}
    for it in res.items.values():
        assert it.kind in ("MAP", "VERTEX")
    a, b = res.items["Box A"], res.items["Box B"]
    if a.kind == "MAP" and b.kind == "MAP":                 # one mesh, two copies: two places in the atlas
        assert not np.allclose(a.uv, b.uv)
    assert all(v > 0 for v in res.reference)


def test_the_project_is_left_as_it_was(soft_and_all):
    assert soft_and_all["after"] == soft_and_all["before"] == soft_and_all["after_all"]
    assert not any(n.startswith(lightbake.NAME) for n in bpy.data.objects.keys())
    for ob in (soft_and_all["floor"], soft_and_all["box"]):
        assert lightbake.UV_NAME not in ob.data.uv_layers


def test_light_uvs_of_all_copies_never_overlap(soft_and_all):
    res = soft_and_all["soft"]
    uvs, charts, atl = [], [], []
    for k, it in enumerate(res.items.values()):
        if it.kind != "MAP":
            continue
        uvs.append(it.uv)
        m = len(it.uv) // 3
        charts.append(np.full(m, 1000 * k, np.int64) + np.arange(m))     # every triangle its own chart: strict
        atl.append(np.full(m, it.atlas, np.int32))
    assert uvs
    uv = np.concatenate(uvs)
    assert uv.min() >= 0.0 and uv.max() <= 1.0
    # different copies never share a texel (one chart id per copy)
    copy_id = np.concatenate([np.full(len(u) // 3, k, np.int32) for k, u in enumerate(uvs)])
    assert lm.overlap_texels(uv, copy_id, np.concatenate(atl), lm.ATLAS) == 0


def test_soft_keeps_the_sun_shadow_out_everything_bakes_it(soft_and_all):
    """The floor in the box's sun shadow: Everything baked is much darker there than in the open; Soft light only
    a little (sky light blocked), because the sun's shadow stays live on the page."""
    floor = soft_and_all["floor"]
    # sun at 35° from +Y (rotation 0 points the sun along +Y in Blender's sky): the shadow falls towards -Y
    out = {}
    for key in ("soft", "all"):
        res = soft_and_all[key]
        it = res.items["Floor"]
        ref = np.asarray(res.reference)
        shadow = _sample(it, -1.2, -1.15, floor) / ref
        sunlit = _sample(it, -1.2, 1.4, floor) / ref
        open_ = _sample(it, 2.4, -2.4, floor) / ref
        out[key] = (shadow.mean(), sunlit.mean(), open_.mean())
    s_shadow, s_sunlit, s_open = out["soft"]
    a_shadow, a_sunlit, a_open = out["all"]
    assert 0.6 < s_open < 1.4 and 0.6 < a_open < 1.4        # open floor = the open probe
    assert a_shadow < 0.5 * a_open                           # the sun's shadow is baked
    assert s_shadow > 0.6 * s_open                           # ... and not in Soft
    assert a_shadow < s_shadow


def test_own_uv_set_1_is_used_as_it_is_and_ids_come_from_the_caller():
    sc, floor, box, box2 = block_scene()
    for ob in (floor, box):
        me = ob.data
        me.uv_layers.new(name="UVMap.001")              # UV set 1: a copy of set 0 (in 0 … 1)
    keep = np.empty(len(floor.data.loops) * 2, np.float32)
    floor.data.uv_layers[1].data.foreach_get("uv", keep)
    box2.data = box2.data.copy()                         # Box B: its own mesh without a 2nd UV set
    while len(box2.data.uv_layers) > 1:
        box2.data.uv_layers.remove(box2.data.uv_layers[1])
    res = lightbake.bake([floor, box, box2], "SOFT", uv="UV1", ids={floor: "house/floor", box: "house/box"},
                         texels_per_m=16, **FAST)
    assert set(res.items) == {"house/floor", "house/box", "Box B"}
    fl = res.items["house/floor"]
    assert fl.kind == "MAP" and fl.uv is None and fl.pixels.shape[2] == 3 and fl.pixels.shape[0] >= 16
    assert res.items["Box B"].kind == "VERTEX"
    assert any("Box B" in p for p in res.problems)
    after = np.empty_like(keep)
    floor.data.uv_layers[1].data.foreach_get("uv", after)
    assert np.array_equal(keep, after) and len(floor.data.uv_layers) == 2   # never unwrapped, never changed
    assert fl.pixels.mean() > 0.0


def test_vertex_light_and_cancel():
    sc, floor, box, box2 = block_scene()
    res = lightbake.bake([box, box2], "ALL", uv="VERTEX", occluders=[floor], **FAST)
    it = res.items["Box A"]
    assert it.kind == "VERTEX" and it.values.shape == (len(box.data.vertices), 3)
    assert it.corners.shape == (len(box.data.loop_triangles) * 3, 3)
    assert it.values.max() > 0.0
    before = _counts()
    calls = []

    def stop(f, text):
        calls.append(f)
        return len(calls) < 3

    with pytest.raises(core.Cancelled):
        lightbake.bake([floor, box, box2], "SOFT", progress=stop, **FAST)
    assert _counts() == before


def test_choice_names_are_the_formats():
    assert [label for _k, label in lightbake.CHOICES] == ["Live only", "Soft light baked, sun live",
                                                          "Everything baked"]
    assert lightbake.choice_id("Everything baked") == "ALL"
    with pytest.raises(ValueError):
        lightbake.choice_id("Half baked")
    sc, floor, box, box2 = block_scene()
    assert lightbake.bake([floor], "LIVE").items == {}


# ---------------------------------------------------------------------------
# the web 3D export with baked light
# ---------------------------------------------------------------------------

def fresh_mill():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture(scope="module")
def mill_lit(tmp_path_factory):
    sc = fresh_mill()
    out = tmp_path_factory.mktemp("lit") / "Mill lit.glb"
    w = sc.fresing.web3d
    w.texture_size = "512"
    w.light = "SOFT"
    w.light_quality = "DRAFT"
    counts = _counts()
    res = web3d.Job(sc, str(out), size=512, light="SOFT", light_quality="DRAFT", light_samples=8).run()
    return {"scene": sc, "out": res, "data": out.read_bytes(), "counts": counts, "path": out}


def test_export_with_baked_light_is_valid_gltf(mill_lit):
    data = mill_lit["data"]
    assert core.problems(data) == []
    doc, _bin = core.read_glb(data)
    lit = [m for m in doc["materials"] if "occlusionTexture" in m]
    assert lit and all(m["occlusionTexture"]["texCoord"] == 1 for m in lit)
    variants = [p for m in doc["meshes"] for p in m["primitives"]
                if "TEXCOORD_1" in p["attributes"] or "_FR_LIGHT" in p["attributes"]]
    assert variants
    # a copy's own light shares the part's points (one POSITION accessor, several meshes)
    pos = [p["attributes"]["POSITION"] for m in doc["meshes"] for p in m["primitives"]]
    assert len(set(pos)) < len(pos)
    out = mill_lit["out"]
    assert out["light"] == "SOFT" and out["light_bytes"] > 0 and "soft light baked" in out["text"]
    assert _counts() == mill_lit["counts"]


def test_every_shown_part_has_its_light(mill_lit):
    doc, _bin = core.read_glb(mill_lit["data"])
    nodes = doc["nodes"]
    shown = [n for n in nodes if n.get("name", "").startswith("Part ")]
    lit = 0
    for n in shown:
        mesh = n.get("mesh")
        if mesh is None:
            mesh = next(nodes[c]["mesh"] for c in n["children"] if "mesh" in nodes[c])
        attrs = doc["meshes"][mesh]["primitives"][0]["attributes"]
        lit += "TEXCOORD_1" in attrs or "_FR_LIGHT" in attrs
    assert lit == len(shown) == len([p for p in build.iter_parts(mill_lit["scene"]) if p.visible_get()])


def test_page_with_baked_light_is_the_plain_three_page(mill_lit):
    page = open(mill_lit["out"]["html"], encoding="utf-8").read()
    st = env.page_settings(page)
    assert st["light"]["light"] == "SOFT" and st["light"]["scale"] >= 1.0 and st["light"]["curve"] == 2.0
    assert st["plain"] is True and st["sea"] is None and st["vessel"] is None
    assert "FRTHREE" in page and "<model-viewer" not in page


def test_blender_reads_the_lit_file_back(mill_lit, tmp_path):
    addon_utils.enable("io_scene_gltf2", default_set=True)
    sc = bpy.data.scenes.new("read back")
    win = bpy.context.window
    with bpy.context.temp_override(scene=sc):
        bpy.ops.import_scene.gltf(filepath=str(mill_lit["path"]))
    obs = [o for o in sc.objects if o.type == "MESH"]
    assert obs
    assert any(len(o.data.uv_layers) >= 2 for o in obs)
    del win


def test_live_only_export_is_unchanged(tmp_path):
    sc = fresh_mill()
    a = web3d.Job(sc, str(tmp_path / "a.glb"), size=512).run()
    b = web3d.Job(sc, str(tmp_path / "b.glb"), size=512, light="LIVE").run()
    assert (tmp_path / "a.glb").read_bytes() == (tmp_path / "b.glb").read_bytes()
    assert "<model-viewer" in open(b["html"], encoding="utf-8").read()
    assert "light" not in b
    del a


def test_the_lit_page_opens_and_uses_the_baked_light(mill_lit):
    """The real export's page in a browser without a window: no error, every lit mesh patched (skipped without a
    browser or WebGL, as the 0106 tests)."""
    browser = env.find_browser()
    if not browser:
        pytest.skip("no browser on this machine")
    try:
        got = env.read_page(mill_lit["out"]["html"], browser, query="auto=0&frames=3", seconds=90)
    except RuntimeError as exc:
        pytest.skip(f"the browser did not run here: {exc}")
    state = got["state"]
    if state.startswith(("no-webgl", "loading")) or "webgl" in state.lower():
        pytest.skip(f"no WebGL here: {state}")
    assert state.startswith("ready"), state
    light = got["light"]
    assert light and light["light"] == "SOFT" and light["plain"] is True and light["meshes"] >= 1
