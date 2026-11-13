"""A house from House Planner in Blender (task 0114): File > Import > House Planner scene (the made-up sample of
house-scene-format v1.0), Preview a moment (0109's sun where House Planner's stands), Bake and export at 4 samples,
and the pinned checker (`check.py <bake> --scene <hpscene>`) on the package: no ERROR. Then what the light must look
like: the table darkens the floor under the ceiling lamp, open storeys hold only their own surfaces, snow only on the
roof and the plot, sun_light by day and not at night; and the project is as it was after the bake."""

import io
import json
import os
import shutil
import subprocess
import sys
import zipfile

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import house_bake, house_import  # noqa: E402
from fresing_render.core import house_scene as hs  # noqa: E402
from fresing_render.core import weather as wcore  # noqa: E402

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
SAMPLE = os.path.join(PIN, "samples", "sample-house.hpscene")
SAMPLES = 4


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _fresh(tmp):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    src = os.path.join(str(tmp), "sample-house.hpscene")
    shutil.copyfile(SAMPLE, src)
    return bpy.context.scene, src


@pytest.fixture(scope="module")
def baked(tmp_path_factory):
    """The sample imported and baked once (every moment, open ground floor, winter snow, the photo)."""
    tmp = tmp_path_factory.mktemp("house")
    scene, src = _fresh(tmp)
    out = house_import.import_scene(scene, src)
    before = _state(scene)
    path = os.path.join(str(tmp), "sample-house.hpbake")
    res = house_bake.HouseBake(scene, path, samples=SAMPLES, photo_samples=4).run()
    return {"scene": scene, "house": out["house"], "path": path, "result": res, "before": before,
            "after": _state(scene), "src": src}


def _state(scene):
    from fresing_render.blender import weather
    return (weather.state(scene), scene.fresing.weather.enabled, scene.fresing.background, scene.camera,
            len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials),
            len([i for i in bpy.data.images if i.type != "RENDER_RESULT"]),
            len(bpy.data.scenes), len(bpy.data.worlds),
            sorted((ob.name, ob.hide_render) for ob in scene.objects))


def _package(path):
    z = zipfile.ZipFile(path)
    return z, json.loads(z.read("bake.json"))


def _page(z, doc, page_id):
    from PIL import Image
    f = next(p["file"] for p in doc["pages"] if p["id"] == page_id)
    return np.asarray(Image.open(io.BytesIO(z.read(f))).convert("RGB"))


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

def test_import_makes_the_house_a_model(tmp_path):
    scene, src = _fresh(tmp_path)
    out = house_import.import_scene(scene, src)
    house = out["house"]
    parts = house_import.by_id(scene)
    assert set(parts) == {sid for sid, s in house.surfaces.items() if s.mesh is not None}
    assert scene.fresing.model_count == 1 and house_import.root(scene) is not None
    assert all(ob.users_collection[0].name == house_import.COLLECTION for ob in parts.values())
    # vertex order kept (merge vertices off): the table's 88 vertices, as in the glb
    assert len(parts["furniture:f_table:0"].data.vertices) == house.surfaces["furniture:f_table:0"].verts
    # UV set 1 came in as the second UV layer
    assert len(parts["floor:r_living"].data.uv_layers) == 2
    lamps = house_import.lights(scene)
    assert len(lamps) == 1 and lamps[0].get(house_import.LAMP) == "lamp:p_living_1"
    assert lamps[0].parent is parts["lamp:p_living_1"]
    assert lamps[0].data.energy > 0.1                     # Lighting Mode Standard: candela -> watts
    # importing again replaces it: still one house, same ids
    house_import.import_scene(scene, src)
    assert len(house_import.parts(scene)) == len(parts)
    assert len([o for o in scene.objects if o.get(house_import.TAG) == "root"]) == 1


def test_another_major_version_is_refused_before_anything_changes(tmp_path):
    scene, src = _fresh(tmp_path)
    z = zipfile.ZipFile(SAMPLE)
    doc = json.loads(z.read("scene.json"))
    doc["version"] = "2.0"
    bad = os.path.join(str(tmp_path), "newer.hpscene")
    with zipfile.ZipFile(bad, "w") as out:
        for n in z.namelist():
            out.writestr(n, json.dumps(doc) if n == "scene.json" else z.read(n))
    n0 = len(bpy.data.objects)
    with pytest.raises(hs.FormatError) as e:
        house_import.import_scene(scene, bad)
    assert "2.0" in str(e.value) and "newer" in str(e.value)
    assert len(bpy.data.objects) == n0 and not house_import.has_house(scene)


def test_preview_puts_0109s_sun_where_house_planner_has_it(tmp_path):
    scene, src = _fresh(tmp_path)
    house = house_import.import_scene(scene, src)["house"]
    for m in house.recipe.moments:
        assert house_import.preview(scene, m.id)
        el, az = hs.sun_angles(m.direction)
        got_el = float(scene[wcore.prop("sun_el")])
        got_az = float(scene[wcore.prop("sun_az")])
        assert house_import._angle(el, az, got_el, got_az) < 0.5, m.id
        on = [ob for ob in house_import.lights(scene) if not ob.hide_render]
        assert len(on) == (1 if m.lamps == "all" else 0), m.id
    # the sky texture turns its sun by 0109's rule (its driver): sun_rotation = radians(90 - sun_az), and
    # House Planner's sun gives the same turn (house_scene.sun_rotation_deg)
    sky = next(n for n in scene.world.node_tree.nodes if n.type == "TEX_SKY")
    drv = next(fc.driver for fc in scene.world.node_tree.animation_data.drivers
               if fc.data_path == f'nodes["{sky.name}"].sun_rotation')
    assert drv.expression.replace(" ", "") == "radians(90-sun_az)"
    for m in house.recipe.moments:
        el, az = hs.sun_angles(m.direction)
        assert abs(((hs.sun_rotation_deg(az) - (90.0 - az)) + 180.0) % 360.0 - 180.0) < 1e-6


def test_bare_season_hides_the_leaves(tmp_path):
    scene, src = _fresh(tmp_path)
    house = house_import.import_scene(scene, src)["house"]
    # the sample has no tree: call the terrace a tree's leaves for this test
    house.surfaces["garden:ga_terrace"].kind = "foliage"
    winter = next(s for s in house.recipe.seasons if s.foliage == "bare")
    summer = next(s for s in house.recipe.seasons if s.foliage != "bare")
    assert house_import.hidden_in(house, winter) == {"garden:ga_terrace"}
    assert house_import.hidden_in(house, summer) == set()
    night = next(m for m in house.recipe.moments if m.season == winter.id)
    house_import.preview(scene, night.id)
    assert house_import.by_id(scene)["garden:ga_terrace"].hide_render


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

def test_checker_passes_with_no_error(baked):
    r = subprocess.run([sys.executable, os.path.join(PIN, "check.py"), baked["path"], "--scene", baked["src"]],
                       capture_output=True, text=True, cwd=PIN)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ERROR" not in r.stdout
    assert not hs.structure_problems(baked["path"], baked["house"])


def test_the_project_is_as_it_was(baked):
    assert baked["after"] == baked["before"]


def test_every_moment_has_its_results(baked):
    z, doc = _package(baked["path"])
    house = baked["house"]
    assert [m["id"] for m in doc["moments"]] == [m.id for m in house.recipe.moments]
    want = {sid for sid, s in house.surfaces.items() if s.bake in ("MAP", "VERTEX")}
    for m in doc["moments"]:
        assert want <= set(m["maps"]), m["id"]
        assert m["encoding"]["scale"] > 0 and m["encoding"]["curve"] == 2.0
        # open: the ground floor's surfaces only
        assert set(m["open"]) == {"st_ground"}
        assert m["open"]["st_ground"]
        assert all(house.surfaces[s].storey == "st_ground" for s in m["open"]["st_ground"])
    assert doc["light"] == "SOFT" and doc["quality"]["samples"] == SAMPLES
    assert len(doc["photos"]) == 1 and doc["photos"][0]["size"] == [320, 240]


def test_sun_light_by_day_and_none_at_night(baked):
    _z, doc = _package(baked["path"])
    house = baked["house"]
    for m in doc["moments"]:
        el = next(x for x in house.recipe.moments if x.id == m["id"]).elevation
        if el < 0:
            assert m.get("sun_light") is None, m["id"]
            assert m["encoding"]["exposure"] > 3.0          # 0109: +4 EV in the dark
        else:
            assert m["sun_light"] is not None and min(m["sun_light"]) >= 0.0, m["id"]
            clouds = next(x for x in house.recipe.moments if x.id == m["id"]).clouds
            if clouds < 0.5:                                # a clear sky: the sun is strong (overcast hides it)
                assert min(m["sun_light"]) > 0.5 * max(m["encoding"]["reference"]), m["id"]


def test_snow_only_on_the_roof_and_the_plot(baked):
    z, doc = _package(baked["path"])
    assert [s["season"] for s in doc["snow"]] == ["winter"]
    from fresing_render.core import web3d
    g, _bin = web3d.read_glb(z.read(doc["snow"][0]["file"]))
    on = {n["extras"]["hp"]["on"] for n in g["nodes"]}
    assert "roof:st_first:0" in on and "ground:plot" in on
    inside = {sid for sid, s in baked["house"].surfaces.items() if s.kind in ("floor", "ceiling", "stair",
                                                                              "furniture")}
    assert not on & inside
    winter = [m for m in doc["moments"] if m["id"].startswith("winter")]
    summer = [m for m in doc["moments"] if m["id"].startswith("summer")]
    assert all(any(k.startswith("snow:") for k in m["maps"]) for m in winter)
    assert not any(k.startswith("snow:") for m in summer for k in m["maps"])


def test_the_table_darkens_the_floor_under_the_lamp(baked):
    """At night the ceiling lamp hangs over the table: the floor under the table is darker than the floor beside it
    (also proves the page's rows run top-down: the table's place found through the glb's own light-map UVs)."""
    z, doc = _package(baked["path"])
    house = baked["house"]
    night = next(m for m in doc["moments"] if m["id"] == "winter-night")
    e = night["maps"]["floor:r_living"]
    page = _page(z, doc, e["page"]).astype(np.float64)
    x, y, w, h = e["rect"]
    pts, tris = hs.world_triangles(house, "floor:r_living")
    doc_g, binary = hs.glb_meshes(house.glb)
    prims = hs.mesh_arrays(doc_g, binary, house.surfaces["floor:r_living"].mesh)
    uv = np.concatenate([p["uv1"] for p in prims])

    def texel_at(px, pz):
        # the floor is flat: interpolate the UV of the world point (px, pz) from the nearest triangle
        for t in tris:
            a, b, c = pts[t][:, [0, 2]]
            m = np.array([b - a, c - a]).T
            try:
                s, r = np.linalg.solve(m, np.array([px, pz]) - a)
            except np.linalg.LinAlgError:
                continue
            if s >= -1e-6 and r >= -1e-6 and s + r <= 1 + 1e-6:
                u = uv[t[0]] + s * (uv[t[1]] - uv[t[0]]) + r * (uv[t[2]] - uv[t[0]])
                return int(x + u[0] * w), int(y + u[1] * h)
        raise AssertionError(f"({px}, {pz}) is not on the floor")

    def light(px, pz):
        cx, cy = texel_at(px, pz)
        return page[cy - 1:cy + 2, cx - 1:cx + 2].mean()

    under = light(3.5, 3.0)                       # the table's middle (glTF x, z)
    beside = light(3.5, 4.6)                      # 1.6 m further, still under the lamp's light
    assert under < 0.8 * beside, (under, beside)


def test_pages_have_no_colour_chunks_and_are_8_bit_rgb(baked):
    z, doc = _package(baked["path"])
    for p in doc["pages"]:
        data = z.read(p["file"])
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        i, kinds = 8, []
        while i < len(data):
            n = int.from_bytes(data[i:i + 4], "big")
            kinds.append(data[i + 4:i + 8])
            if kinds[-1] == b"IHDR":
                assert data[i + 16] == 8 and data[i + 17] == 2 and data[i + 20] == 0     # 8 bit, RGB, not interlaced
            i += 12 + n
        assert not set(kinds) & {b"gAMA", b"iCCP", b"sRGB", b"cHRM", b"cICP"}
        assert max(p["size"]) <= 1024
