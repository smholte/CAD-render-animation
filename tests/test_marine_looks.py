"""Marine weathering looks and concrete (task 0116): the library entries, the band's formula (plain Python in
``marine_looks``) and the shader nodes that draw it.

The Blender tests use a **vertical plate** 1 m wide from world z −4 m to +4 m, seen square on by an orthographic
camera; renders are tiny (16 x 128 px, Cycles on the processor). A named node of the look is shown as light
("probe"), so a row of the picture is compared with the formula at the height it shows."""

import math

import numpy as np
import pytest

from fresing_render.core import materials_lib

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

from fresing_render.blender import marine_looks as ML  # noqa: E402
from fresing_render.blender import materials  # noqa: E402

NEW = ("concrete", "paint_marine_growth", "paint_marine_streaks")


# ---- the library and the formula (nothing rendered) -------------------------------------------------------------

def test_library_entries():
    m, uids = materials_lib.MATERIALS, materials_lib.UIDS
    assert uids["wire_rope"] == 50                                    # the last number before this task
    assert [uids[k] for k in NEW] == [51, 52, 53]
    assert set(uids) == set(m) and len(set(uids.values())) == len(uids)
    assert m["concrete"]["label"] == "Concrete" and m["concrete"]["category"] == "Other"
    assert not materials_lib.needs_color("concrete") and m["concrete"]["roughness"] >= 0.8
    r, g, b = m["concrete"]["base_color"]
    assert 0.5 < b < g < r < 0.7                                      # light, warm grey
    for key, kind in (("paint_marine_growth", "GROWTH"), ("paint_marine_streaks", "STREAKS")):
        e = m[key]
        assert e["category"] == "Paint" and materials_lib.needs_color(key), key
        assert e["label"].startswith("Marine paint, "), key
        assert e["marine"]["kind"] == kind and ML.MATERIALS[kind] == key
        assert set(e["marine"]) - {"kind"} <= set(ML.DEFAULTS[kind]), key
        for k in ("roughness", "coat", "coat_roughness", "peel", "variation"):    # the marine paint underneath
            assert e[k] == m["paint_marine"][k], (key, k)
    labels = [v["label"] for v in m.values()]
    assert len(labels) == len(set(labels))
    assert ("concrete", "Concrete") in dict(materials_lib.items_by_category())["Other"]


def test_splash_zone_formula():
    d = ML.DEFAULTS["GROWTH"]
    assert ML.splash(0.0) == 1.0 and ML.splash(-3.0) == 1.0 and ML.splash(d["splash"]) == 0.0
    assert ML.splash(10.0) == 0.0
    assert ML.splash(d["splash"] / 2) == pytest.approx(0.25)
    h = np.linspace(-1, 4, 51)
    assert np.all(np.diff(ML.splash(h)) <= 0)                         # fades upwards, never back
    assert 1.0 <= d["splash"] <= 3.0                                  # the brief: about 1 – 3 m


def test_growth_formula():
    lo, hi = ML.growth_band()
    assert lo < -0.5 and -0.2 < hi < 0.6                              # below the waterline, edge reaching up to it
    for n in (0.0, 0.3, 0.45, 0.5, 0.62, 0.7, 1.0):
        assert ML.growth(lo - 0.01, n) == 1.0 and ML.growth(hi + 0.01, n) == 0.0, n
    assert ML.edge_shift(0.5) == pytest.approx(0.0)
    assert ML.edge_shift(0.0) == -ML.DEFAULTS["GROWTH"]["edge_jitter"] == -ML.edge_shift(1.0)
    h = np.linspace(-3, 1, 81)
    assert np.all(np.diff(ML.growth(h, 0.55)) <= 0)
    # the edge wanders: higher noise, higher edge
    assert ML.growth(ML.DEFAULTS["GROWTH"]["edge"], 0.6) > ML.growth(ML.DEFAULTS["GROWTH"]["edge"], 0.4)
    with pytest.raises(ValueError):
        ML.kind_name("barnacles")


# ---- Blender ------------------------------------------------------------------------------------------------------

W, H = 16, 128
Z0, Z1 = -4.0, 4.0


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"
    sc.render.resolution_percentage = 100
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("plate")
    sc.world.use_nodes = True
    nt = sc.world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(bg.outputs[0], nt.nodes.new("ShaderNodeOutputWorld").inputs[0])
    return sc


@pytest.fixture
def scene():
    return fresh()


def plate(material, colour="RAL 1023", wear=0.0, facing_up=False):
    """A plate 1 m x 8 m, upright (or lying, ``facing_up``), the material the app's own way. Its object is moved and
    turned about z, so world and object coordinates differ."""
    me = bpy.data.meshes.new("plate")
    if facing_up:
        co = [(-0.5, Z0, 0.0), (0.5, Z0, 0.0), (0.5, Z1, 0.0), (-0.5, Z1, 0.0)]
    else:
        co = [(-0.5, 0.0, Z0), (0.5, 0.0, Z0), (0.5, 0.0, Z1), (-0.5, 0.0, Z1)]
    me.from_pydata(co, [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("plate", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler.z = math.radians(30)        # turned about the vertical...
    ob.location = (0.0, 0.0, 0.0)
    mat = materials.ensure_material(f"Group {material}", material, colour, wear)
    materials.assign(ob, mat)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = Z1 - Z0
    if facing_up:
        cam.location = (0.0, 0.0, 5.0)
        cam.rotation_euler = (0.0, 0.0, math.radians(30))
    else:   # square on to the turned plate, picture up = world up
        cam.rotation_euler = (math.radians(90), 0.0, math.radians(30))
        cam.location = (5.0 * math.sin(math.radians(30)), -5.0 * math.cos(math.radians(30)), 0.0)
    return ob, mat


def zoom(size, z):
    """Show only ``size`` metres of the plate round world height ``z`` (a square picture of ``ZW`` px)."""
    sc = bpy.context.scene
    sc.camera.data.ortho_scale = size
    sc.camera.location.z = z
    sc.render.resolution_x = sc.render.resolution_y = ZW


ZW = 64


def probe(mat, name):
    nt = mat.node_tree
    em = nt.nodes.get("probe") or nt.nodes.new("ShaderNodeEmission")
    em.name = "probe"
    nt.links.new(nt.nodes[name].outputs[0], em.inputs["Color"])
    for out in (n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"):
        nt.links.new(em.outputs[0], out.inputs["Surface"])


def render(path, samples=4):
    sc = bpy.context.scene
    w, h = sc.render.resolution_x, sc.render.resolution_y
    sc.cycles.samples = samples
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[:, :, :3].astype(float)


def heights():
    """World z of every row's middle (row 0 at the bottom)."""
    return Z0 + (np.arange(H) + 0.5) * (Z1 - Z0) / H


def _image_nodes(nt):
    out = []
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeTexImage":
            out.append(n)
        if getattr(n, "node_tree", None) is not None:
            out += _image_nodes(n.node_tree)
    return out


@pytest.mark.parametrize("mid", NEW)
@pytest.mark.parametrize("wear", [0.0, 0.5])
def test_build_nodes_makes_a_valid_tree(scene, mid, wear):
    mat = materials.ensure_material(f"G {mid}", mid, "RAL 7035", wear)
    nt = mat.node_tree
    assert all(link.is_valid for link in nt.links)
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    assert out.inputs["Surface"].links[0].from_node == bsdf
    assert not _image_nodes(nt)                                       # no picture files
    assert nt.animation_data is None and mat.animation_data is None   # no drivers: works with scripts off
    assert (mat["fr_material"], float(mat["fr_wear"])) == (mid, wear)
    assert materials.is_current(mat, mid, "RAL 7035", wear)
    names = set(ML.nodes_of(mat))
    if mid == "paint_marine_growth":
        assert names == {ML.NODE_WATERLINE, ML.NODE_HEIGHT, ML.NODE_GROWTH, ML.NODE_SPLASH, ML.NODE_STREAKS}
        wl = nt.nodes[ML.NODE_WATERLINE]
        assert (wl.attribute_type, wl.attribute_name) == ("VIEW_LAYER", ML.WATERLINE)
        assert bsdf.inputs["Coat Weight"].is_linked                  # the growth takes the clear coat off
        assert bsdf.inputs["Normal"].is_linked                       # its relief
    elif mid == "paint_marine_streaks":
        assert names == {ML.NODE_STREAKS}
    else:
        assert not names and bsdf.inputs["Normal"].is_linked         # concrete: pores
    for sock in ("Base Color", "Roughness"):
        assert bsdf.inputs[sock].is_linked, sock
    if wear:
        assert any(n.bl_idname == "ShaderNodeAmbientOcclusion" for n in nt.nodes)   # the wear's dirt is there


def test_weather_wrap_keeps_the_marine_look(scene):
    from fresing_render.blender import weather_look
    mat = materials.ensure_material("G growth", "paint_marine_growth", "RAL 1023", 0.3)
    assert weather_look.wrap(mat)
    assert weather_look.NODE in mat.node_tree.nodes and ML.NODE_GROWTH in mat.node_tree.nodes
    materials.build_nodes(mat, "paint_marine_growth", "RAL 1023", 0.6)     # a rebuild (the wear slider)
    assert weather_look.NODE in mat.node_tree.nodes and ML.NODE_GROWTH in mat.node_tree.nodes
    assert all(link.is_valid for link in mat.node_tree.links)


def test_sync_follows_the_sea(scene):
    from fresing_render.blender import surroundings
    assert ML.waterline(scene) == 0.0 and ML.sync(scene) == 0.0 and ML.WATERLINE not in scene   # no sea: z 0
    root = bpy.data.objects.new("root", None)
    root.location = (3.0, 1.0, -30.0)
    sea = bpy.data.objects.new("sea", bpy.data.meshes.new("sea"))
    sea.parent = root
    sea.location.z = 30.4
    sea[surroundings.TAG] = "sea"
    for ob in (root, sea):
        scene.collection.objects.link(ob)
    assert ML.sea_z(scene) == pytest.approx(0.4)
    assert ML.sync(scene) == pytest.approx(0.4) and scene[ML.WATERLINE] == pytest.approx(0.4)
    bpy.data.objects.remove(sea)
    assert ML.sync(scene) == pytest.approx(0.4)          # the sea taken away: the growth stays where it was
    # building a growth look picks the sea up by itself
    sea = bpy.data.objects.new("sea", bpy.data.meshes.new("sea2"))
    sea[surroundings.TAG] = "sea"
    sea.location.z = -1.25
    scene.collection.objects.link(sea)
    materials.ensure_material("G growth", "paint_marine_growth", "RAL 1023")
    assert scene[ML.WATERLINE] == pytest.approx(-1.25)


def test_the_band_sits_at_the_waterline_in_world_space(scene, tmp_path):
    """Splash zone: exactly the formula at each row's height; growth: covered below its band, clean above it.
    Then the scene's waterline moves up 1.5 m and the band with it."""
    ob, mat = plate("paint_marine_growth")
    h = heights()
    lo, hi = ML.growth_band()
    for wl in (0.0, 1.5):
        scene[ML.WATERLINE] = wl
        probe(mat, ML.NODE_SPLASH)
        got = render(tmp_path / "splash.exr")[:, :, 0]
        want = ML.splash(h - wl)
        assert np.abs(got - want[:, None]).max() < 0.02, (wl, got.mean(1), want)
        probe(mat, ML.NODE_GROWTH)
        got = render(tmp_path / "growth.exr")[:, :, 0]
        below, above = h - wl < lo - 0.1, h - wl > hi + 0.1
        assert below.sum() > 10 and above.sum() > 10
        assert got[below].min() > 0.98 and got[above].max() < 0.02, wl
        # the edge is patchy: within the band the rows are not all the same
        band = (h - wl > lo + 0.1) & (h - wl < hi - 0.1)
        assert got[band].std() > 0.05, wl


def test_rust_streaks_are_vertical_and_fade_upwards(scene, tmp_path):
    ob, mat = plate("paint_marine_growth")
    probe(mat, ML.NODE_STREAKS)
    got = render(tmp_path / "streaks.exr")[:, :, 0]
    assert got[heights() > ML.DEFAULTS["GROWTH"]["rust_height"]].max() < 1e-3    # none high up
    zoom(1.0, 0.8)                                                    # 1 m just above the waterline, 16 mm a pixel
    a = render(tmp_path / "near.exr", samples=8)[:, :, 0]
    assert a.max() > 0.2                                              # there are streaks
    down = np.abs(np.diff(a, axis=0)).mean()                          # row to row: along a streak
    across = np.abs(np.diff(a, axis=1)).mean()                        # column to column: across them
    assert down < 0.5 * across, (down, across)
    zoom(1.0, 2.6)                                                    # higher up: fainter
    assert render(tmp_path / "up.exr", samples=8)[:, :, 0].mean() < 0.6 * a.mean()


def test_weathering_streaks_run_down_walls_only(scene, tmp_path):
    ob, mat = plate("paint_marine_streaks")
    probe(mat, ML.NODE_STREAKS)
    whole = render(tmp_path / "s.exr", samples=8)[:, :, 0]
    assert whole.mean() < 0.15                                         # light: thin lines, not a coat of dirt
    zoom(1.0, 0.0)
    upright = render(tmp_path / "near.exr", samples=8)[:, :, 0]
    assert upright.max() > 0.1
    down = np.abs(np.diff(upright, axis=0)).mean()
    across = np.abs(np.diff(upright, axis=1)).mean()
    assert down < 0.5 * across, (down, across)
    fresh()
    ob, mat = plate("paint_marine_streaks", facing_up=True)
    probe(mat, ML.NODE_STREAKS)
    assert render(tmp_path / "flat.exr")[:, :, 0].max() < 1e-3         # a deck: no streaks


def test_the_real_material_below_and_above(scene, tmp_path):
    """The whole look in Cycles: yellow paint high up, dark growth deep down."""
    plate("paint_marine_growth", "RAL 1023")
    px = render(tmp_path / "look.exr", samples=8)
    h = heights()
    lo, _hi = ML.growth_band()
    deep, high = px[h < lo - 0.3].mean((0, 1)), px[h > 3.2].mean((0, 1))
    assert high[0] > 0.3 and high[2] < 0.5 * high[0]                   # traffic yellow
    assert deep.sum() < 0.4 * high.sum()                               # dark growth
    assert deep[1] >= deep[2]                                          # green-brown, not blue
