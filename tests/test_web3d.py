"""Web 3D model (task 0099) in Blender: export of the test mill, what goes in, names, looks, decals, animation,
cancel, the project left as it was, and Blender reading the file back."""

import os

import numpy as np
import pytest

from fresing_render.core import web3d as core

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, decals, logic, web3d  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
DECALS_A = os.path.join(HERE, "data", "test_decals_a.step")
TOP = 5                                   # +Z face of a box (OpenCascade's order)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(path=MILL):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture(scope="module")
def mill_export(tmp_path_factory):
    """The test mill exported once at 512 px with the panel's operator (as the Export button does without the file
    window)."""
    sc = fresh()
    out = tmp_path_factory.mktemp("web") / "Mill ä web.glb"
    sc.fresing.web3d.texture_size = "512"
    meshes = {me.name: (len(me.uv_layers), [m.name if m else "" for m in me.materials]) for me in bpy.data.meshes}
    counts = (len(bpy.data.scenes), len(bpy.data.materials), len(bpy.data.images), len(bpy.data.objects))
    assert bpy.ops.fresing.web3d_export(filepath=str(out)) == {"FINISHED"}
    data = out.read_bytes()
    return {"scene": sc, "path": out, "data": data, "meshes": meshes, "counts": counts,
            "parts": list(build.iter_parts(sc))}


def _doc(data):
    return core.read_glb(data)


def mesh_of(doc, node):
    """The mesh a part's node shows: its own, or its unnamed child's (16-bit points)."""
    if "mesh" in node:
        return node["mesh"]
    return next(doc["nodes"][c]["mesh"] for c in node["children"] if "mesh" in doc["nodes"][c])


def test_export_writes_a_valid_glb_and_one_file_page(mill_export):
    data, path = mill_export["data"], mill_export["path"]
    assert core.problems(data) == []
    s = core.summary(data)
    parts = mill_export["parts"]
    assert s["parts"] == len(parts) == 9
    assert s["triangles"] == sum(len(p.data.polygons) for p in parts)
    assert s["size"] < 5_000_000                             # the target for the test mill
    page = path.with_suffix(".html")
    assert page.exists()
    text = page.read_text(encoding="utf-8")
    assert "<model-viewer" in text and "customElements" in text      # the viewer is inside the page
    import base64
    import re
    assert base64.b64decode(re.search(r'id="glb">([^<]+)</script>', text).group(1)) == data
    w = mill_export["scene"].fresing.web3d
    assert w.last_path == str(path) and w.last_size == len(data)
    assert w.last_text.startswith(core.mb(len(data))) and "triangles" in w.last_text
    assert "Web 3D model saved" in mill_export["scene"].fresing.last_message


def test_the_project_is_left_as_it_was(mill_export):
    assert (len(bpy.data.scenes), len(bpy.data.materials), len(bpy.data.images),
            len(bpy.data.objects)) == mill_export["counts"]
    for me in bpy.data.meshes:
        if me.name in mill_export["meshes"]:
            assert (len(me.uv_layers), [m.name if m else "" for m in me.materials]) == mill_export["meshes"][me.name]
    assert not [i for i in bpy.data.images if i.name.startswith(web3d.BAKE_NAME)]
    assert not os.path.exists(str(mill_export["path"]) + ".part")


def test_hidden_names_and_y_up(mill_export):
    doc, _ = _doc(mill_export["data"])
    names = [n["name"] for n in doc["nodes"] if "name" in n]
    assert names[0] == "Model" and doc["nodes"][0]["rotation"] == pytest.approx(list(core.Z_UP_TO_Y_UP))
    assert names[1:] == [f"Part {k}" for k in range(1, 10)]
    assert all(m["name"].startswith("Mesh ") for m in doc["meshes"])
    assert all(m["name"].startswith("Look ") for m in doc["materials"])
    for p in mill_export["parts"]:
        assert p[build.PROP_NAME].encode() not in mill_export["data"]


def test_base_colours_are_the_materials_colours(mill_export):
    """Every part's glTF base colour is its Blender material's (flat looks: a factor; within 1/255 in sRGB)."""
    doc, _ = _doc(mill_export["data"])
    nodes = [n for n in doc["nodes"] if "mesh" in n]
    for ob, node in zip(mill_export["parts"], nodes):
        mat = ob.material_slots[0].material
        want = np.array(web3d.principled(mat).inputs["Base Color"].default_value[:3])
        gm = doc["materials"][doc["meshes"][node["mesh"]]["primitives"][0]["material"]]
        got = np.array(gm["pbrMetallicRoughness"]["baseColorFactor"][:3])
        assert core.linear_to_srgb(got) == pytest.approx(core.linear_to_srgb(want), abs=1.0 / 255), ob.name


def test_looks_are_baked_to_seamless_textures(mill_export):
    doc, binary = _doc(mill_export["data"])
    assert doc["images"], "no look was baked"
    for img in doc["images"]:
        view = doc["bufferViews"][img["bufferView"]]
        raw = binary[view["byteOffset"]:view["byteOffset"] + view["byteLength"]]
        assert core.image_size(raw) == (512, 512)
    for s in doc["samplers"]:
        assert s["wrapS"] == core.REPEAT
    paint = [m for m in doc["materials"] if "KHR_materials_clearcoat" in m.get("extensions", {})]
    assert paint                                        # the satin paint's coat
    # the orange peel tilts the surface by 0.3°: less than an 8-bit normal map holds, so no picture for it
    assert not any("normalTexture" in m for m in paint)
    steel = [m for m in doc["materials"] if m["pbrMetallicRoughness"].get("metallicFactor") == 1.0]
    assert steel and all("metallicRoughnessTexture" in m["pbrMetallicRoughness"] for m in steel)
    # one picture per look source: the two ground-steel groups share theirs
    assert len(doc["images"]) < len(steel) + 1
    # UVs only on meshes whose looks have a picture (half the file of a painted machine is UVs otherwise)
    for mesh in doc["meshes"]:
        textured = any(web3d._textured(doc["materials"][p["material"]]) for p in mesh["primitives"])
        assert ("TEXCOORD_0" in mesh["primitives"][0]["attributes"]) == textured


def test_blender_reads_the_file_back(mill_export, tmp_path):
    """The file opens in another glTF reader (Blender's): same parts and triangles, the pictures on the looks."""
    addon_utils.enable("io_scene_gltf2", default_set=True)
    sc = bpy.data.scenes.new("Read back")
    win_scene = bpy.context.window.scene if bpy.context.window else None
    with bpy.context.temp_override(scene=sc):
        if bpy.context.window:
            bpy.context.window.scene = sc
        bpy.ops.import_scene.gltf(filepath=str(mill_export["path"]))
    obs = [o for o in sc.objects if o.type == "MESH"]
    assert len(obs) == 9
    assert sum(len(o.data.polygons) for o in obs) == core.summary(mill_export["data"])["triangles"]
    imgs = {n.image.name for o in obs for s in o.material_slots if s.material
            for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
    assert imgs
    if win_scene is not None:
        bpy.context.window.scene = win_scene
    for o in list(sc.objects):
        bpy.data.objects.remove(o)
    bpy.data.scenes.remove(sc)


def test_hidden_parts_are_left_out_and_names_can_stay(tmp_path):
    sc = fresh()
    parts = list(build.iter_parts(sc))
    parts[0].hide_set(True)
    out = web3d.export(sc, str(tmp_path / "m.glb"), size=512, hide_names=False, page=False)
    s = core.summary(open(out["path"], "rb").read())
    assert s["parts"] == len(parts) - 1 == out["parts"]
    assert parts[1][build.PROP_NAME] in s["names"]
    assert parts[0][build.PROP_NAME] not in s["names"]
    assert not (tmp_path / "m.html").exists()
    assert out["text"] == core.result_line(out["size"], out["triangles"], out["textures"], out["seconds"])


def test_the_active_paint_scheme_is_exported(tmp_path):
    sc = fresh()
    s = sc.fresing
    group = next(g for g in s.groups if g.color)
    logic.save_scheme(s, "Own")
    s.groups[group.name].color = "#E00000"
    logic.save_scheme(s, "Red")
    logic.apply_scheme(sc, "Red")

    def colours():
        out = web3d.export(sc, str(tmp_path / "s.glb"), size=512, page=False)
        doc, _ = core.read_glb(open(out["path"], "rb").read())
        return [tuple(round(c, 3) for c in m["pbrMetallicRoughness"]["baseColorFactor"][:3]) for m in doc["materials"]]

    red = colours()
    assert any(c[0] > 0.6 and c[1] < 0.05 and c[2] < 0.05 for c in red)
    logic.apply_scheme(sc, "Own")
    assert colours() != red


def test_decals_go_in_as_transparent_baked_pictures(tmp_path):
    sc = fresh(DECALS_A)
    panel = next(o for o in build.iter_parts(sc) if o[build.PROP_NAME] == "PANEL")
    decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="WARN_HOT")
    out = web3d.export(sc, str(tmp_path / "d.glb"), size=512, page=False)
    assert out["decals"] == 1
    data = open(out["path"], "rb").read()
    assert core.problems(data) == []
    doc, binary = core.read_glb(data)
    node = next(n for n in doc["nodes"] if n.get("name") == "Decal " + str(out["parts"] + 1))
    prim = doc["meshes"][mesh_of(doc, node)]["primitives"][0]
    mat = doc["materials"][prim["material"]]
    assert mat["alphaMode"] == "BLEND"
    tex = doc["textures"][mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]]
    assert doc["samplers"][tex["sampler"]]["wrapS"] == core.CLAMP
    view = doc["bufferViews"][doc["images"][tex["source"]]["bufferView"]]
    raw = binary[view["byteOffset"]:view["byteOffset"] + view["byteLength"]]
    assert raw[:4] == b"\x89PNG"                        # with see-through parts
    uv = core.accessor_array(doc, binary, prim["attributes"]["TEXCOORD_0"])
    assert uv.min() >= -1e-4 and uv.max() <= 1 + 1e-4   # the decal's own picture, not tiles


def test_animation_of_moving_parts(tmp_path):
    sc = fresh()
    parts = list(build.iter_parts(sc))
    ob = parts[-1]
    start = ob.location.copy()
    ob.keyframe_insert("location", frame=1)
    ob.location.x += 0.1
    ob.keyframe_insert("location", frame=11)
    sc.frame_start, sc.frame_end = 1, 11
    sc.frame_set(1)
    sc.fresing.anim_baked = "Slide"                     # as Build animation leaves it
    out = web3d.export(sc, str(tmp_path / "a.glb"), size=512, animation=True)
    assert out["animated"]
    data = open(out["path"], "rb").read()
    assert core.problems(data) == []
    doc, binary = core.read_glb(data)
    anim = doc["animations"][0]
    assert anim["name"] == "Slide"
    moved = {c["target"]["node"] for c in anim["channels"]}
    assert len(moved) == 1
    node = doc["nodes"][moved.pop()]
    assert "matrix" not in node and "translation" in node
    t = core.accessor_array(doc, binary, anim["samplers"][0]["output"])
    times = core.accessor_array(doc, binary, anim["samplers"][0]["input"])
    assert times[-1, 0] == pytest.approx(10 / sc.render.fps)
    assert np.ptp(t[:, 0]) == pytest.approx(0.1, abs=1e-4)
    assert sc.frame_current == 1 and ob.location.x == pytest.approx(start.x)
    assert "autoplay" in open(out["html"], encoding="utf-8").read()
    # without a built animation the tick does nothing
    sc.fresing.anim_baked = ""
    out = web3d.export(sc, str(tmp_path / "b.glb"), size=512, animation=True, page=False)
    assert not out["animated"] and core.summary(open(out["path"], "rb").read())["animations"] == 0


def _key_hidden(ob, rows):
    for frame, hidden in rows:
        ob.hide_render = ob.hide_viewport = hidden
        ob.keyframe_insert("hide_render", frame=frame)
        ob.keyframe_insert("hide_viewport", frame=frame)


def test_animation_shows_and_hides_parts(tmp_path):
    """Task 0111: parts the animation shows and hides – the tool copies of a tool change, Show/Hide steps – come along:
    one hidden at the first frame is in the file too, and both are scaled to 0 while hidden, switched without
    in-between (STEP). Before, the hidden one was left out and the other stayed on the page all the time."""
    sc = fresh()
    parts = list(build.iter_parts(sc))
    later, gone = parts[-1], parts[-2]
    _key_hidden(later, [(1, True), (6, False)])          # comes in at frame 6
    _key_hidden(gone, [(1, False), (8, True)])           # goes at frame 8
    sc.frame_start, sc.frame_end = 1, 11
    sc.frame_set(1)
    assert not web3d._visible(later)
    sc.fresing.anim_baked = "Show and hide"
    out = web3d.export(sc, str(tmp_path / "v.glb"), size=512, animation=True, page=False)
    assert out["animated"] and out["parts"] == len(parts)
    doc, binary = core.read_glb(open(out["path"], "rb").read())
    anim = doc["animations"][0]
    scales = {c["target"]["node"]: anim["samplers"][c["sampler"]] for c in anim["channels"]
              if c["target"]["path"] == "scale"}
    assert len(scales) == 2 and all(s["interpolation"] == "STEP" for s in scales.values())
    seen = {}
    for node, smp in scales.items():
        s = core.accessor_array(doc, binary, smp["output"])[:, 0]
        seen[tuple(np.round(s).astype(int))] = doc["nodes"][node]
    assert set(seen) == {(0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1), (1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0)}
    assert seen[(0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1)]["scale"] == [0.0, 0.0, 0.0]   # hidden on the first frame


def test_cancel_writes_nothing_and_cleans_up(tmp_path):
    sc = fresh()
    job = web3d.Job(sc, str(tmp_path / "c.glb"), size=512)
    gen = job.steps()
    for _ in range(3):                                   # into the baking
        next(gen)
    gen.close()
    assert not os.listdir(tmp_path)
    assert BAKE_LEFT() == []
    assert len(bpy.data.scenes) == 1


def BAKE_LEFT():
    return [i.name for coll in (bpy.data.images, bpy.data.materials, bpy.data.meshes, bpy.data.objects)
            for i in coll if i.name.startswith(web3d.BAKE_NAME)]


def test_panel_and_nothing_to_export(tmp_path):
    sc = fresh()
    assert web3d.can_export(sc) == ""
    assert web3d.default_path(sc).endswith(" web 3D.glb")
    for p in build.iter_parts(sc):
        p.hide_set(True)
    assert "No part is shown" in web3d.can_export(sc)
    assert bpy.ops.fresing.web3d_export(filepath=str(tmp_path / "x.glb")) == {"CANCELLED"}
    from fresing_render.blender import ui_web3d
    assert ui_web3d.FRESING_PT_web3d.bl_parent_id == "FRESING_PT_scene"


def test_bake_scene_is_a_copy_and_empty():
    """Switching a new scene's engine to Cycles froze the real app (Blender waits for a running material preview,
    which needs Python): the bake scene is a copy of a scene that already renders with Cycles, emptied."""
    sc = fresh()
    assert sc.render.engine == "CYCLES"
    sc["fr_test_mark"] = 1
    b = web3d.Baker(sc)
    try:
        assert b.scene is not sc and b.scene.get("fr_test_mark") == 1          # copied, never switched
        assert len(b.scene.objects) == 0 and b.scene.world is None
        assert len(sc.objects) > 0                                            # the project keeps its own
    finally:
        b.close()
    assert len(bpy.data.scenes) == 1


def test_compressed_export_and_the_panels_default(mill_export, tmp_path):
    """Task 0105: Smaller file is on by default but packs only a big model; forced on, the test mill is packed with
    meshopt, reads back to the same parts and triangles, and its page switches the viewer's decoder on."""
    sc = fresh()
    assert sc.fresing.web3d.compress is True
    assert not core.summary(mill_export["data"])["compressed"]          # 2,693 triangles: below COMPRESS_FROM
    out = web3d.export(sc, str(tmp_path / "packed.glb"), size=512, compress=True)
    data = open(out["path"], "rb").read()
    assert core.problems(data) == []
    s0, s1 = core.summary(mill_export["data"]), core.summary(data)
    assert s1["compressed"] and out["compressed"] and " compressed · " in out["text"]
    assert (s1["parts"], s1["triangles"], s1["textures"]) == (s0["parts"], s0["triangles"], s0["textures"])
    doc, _ = core.read_glb(data)
    modes = {v["extensions"][core.MESHOPT]["mode"] for v in doc["bufferViews"] if "extensions" in v}
    from fresing_render.core import meshopt
    assert modes == {"ATTRIBUTES", "TRIANGLES" if meshopt.native() is not None else "INDICES"}
    assert web3d.meshopt_native() is not None                         # Blender as a module ships libmeshoptimizer
    page = open(out["html"], encoding="utf-8").read()
    assert "meshoptDecoderLocation" in page
    off = web3d.export(sc, str(tmp_path / "plain.glb"), size=512, compress=False)
    assert not off["compressed"] and off["size"] > out["size"]
