"""core/house_scene.py (task 0114): reading a House Planner scene and writing the bake package, checked against the
pinned house-scene-format v1.0 (its checker, schemas and samples in tests/data/house/hsf-v1.0). Pure Python."""

import io
import json
import math
import os
import struct
import subprocess
import sys
import warnings
import zipfile
import zlib

import numpy as np
import pytest

from fresing_render.core import house_hash, weather, web3d
from fresing_render.core import house_scene as hs

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
SCENE = os.path.join(PIN, "samples", "sample-house.hpscene")
BAKE = os.path.join(PIN, "samples", "sample-house.hpbake")
sys.path.insert(0, PIN)
from hsf import check as hcheck  # noqa: E402 – the pinned checker, for the comparisons only
from hsf import glb as hglb  # noqa: E402
from hsf import surface as hsurface  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _files(path):
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _scene_with(change=None, glb_change=None) -> bytes:
    """The sample scene with its scene.json (and house.glb's JSON) changed by the given functions."""
    files = _files(SCENE)
    doc = json.loads(files["scene.json"])
    if change:
        change(doc)
    files["scene.json"] = json.dumps(doc).encode()
    if glb_change:
        g = hglb.Glb.parse(files["house.glb"])
        glb_change(g.json)
        files["house.glb"] = hglb.pack(g.json, g.bin)
    return _zip(files)


def _set_encrypted(data: bytes, name: str) -> bytes:
    """Set the 'encrypted' flag of one entry in the local header and in the central directory."""
    b = bytearray(data)
    zf = zipfile.ZipFile(io.BytesIO(data))
    info = zf.getinfo(name)
    b[info.header_offset + 6] |= 1
    eocd = b.rfind(b"PK\x05\x06")
    count, _, cd_off = struct.unpack_from("<HII", b, eocd + 10)
    pos = cd_off
    for _ in range(count):
        n, e, c = struct.unpack_from("<HHH", b, pos + 28)
        if bytes(b[pos + 46:pos + 46 + n]).decode() == name:
            b[pos + 8] |= 1
        pos += 46 + n + e + c
    return bytes(b)


def _png_pixels(data: bytes) -> np.ndarray:
    """(h, w, 3) of a page PNG as core/web3d.png writes it (filter 0 on every row)."""
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + 3 * w)
    assert (raw[:, 0] == 0).all()
    return raw[:, 1:].reshape(h, w, 3)


def _chunks(data: bytes) -> list:
    pos, out = 8, []
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        out.append(data[pos + 4:pos + 8])
        pos += 12 + n
    return out


def test_no_blender_and_no_checker_in_the_module():
    with open(hs.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "import bpy" not in src and "from hsf" not in src and "import hsf" not in src


@pytest.fixture(scope="module")
def scene():
    return hs.read_scene(SCENE)


# ---------------------------------------------------------------------------
# reading the sample
# ---------------------------------------------------------------------------

def test_read_sample(scene):
    assert len(scene.surfaces) == 52
    assert scene.notes == []
    assert scene.id == "sample-house-a" and scene.title == "Made-up sample house"
    assert [(s.id, s.level) for s in scene.storeys] == [("st_ground", 0), ("st_first", 1)]
    assert hs.storey_level(scene, "st_first") == 1 and hs.storey_level(scene, None) is None
    r = scene.recipe
    assert (r.light, r.preset, r.samples, r.page_size, r.texels_per_m) == ("SOFT", "DRAFT", 16, 1024, 16.0)
    assert r.texels_per_m_by_group == {"garden": 6.0}
    assert r.open_storeys == ["st_ground"]
    assert [m.id for m in r.moments] == ["summer-morning", "summer-evening", "winter-noon", "winter-night"]
    assert [(s.id, s.day, s.foliage) for s in r.seasons] == [("summer", 172, "full"), ("winter", 15, "bare")]
    assert r.moments[3].lamps == "all" and r.moments[0].lamps == "none"
    cam = r.cameras["garden-view"]
    assert cam.position == (3.5, 1.7, 22.0) and cam.target == (3.5, 2.5, 4.5) and cam.fov == 50.0
    assert [(p["id"], p["size"], p["moment"]) for p in r.photos] == [("photo-1", (320, 240), "summer-morning")]
    assert r.videos == []
    assert hs.surface_density(r, scene.surfaces["ground:plot"]) == 6.0
    assert hs.surface_density(r, scene.surfaces["garden:ga_terrace"]) == 10.0
    assert hs.surface_density(r, scene.surfaces["floor:r_living"]) == 16.0


def test_surfaces_match_the_checker(scene):
    files = _files(SCENE)
    quality = json.loads(files["scene.json"])["recipe"]["quality"]
    g = hglb.Glb.parse(files["house.glb"])
    rep = hcheck.Report("t")
    ref = hcheck.read_surfaces(g, rep, "house.glb", False, snow=False, quality=quality).by_id
    assert rep.ok and set(ref) == set(scene.surfaces)
    doc, binary = scene.gltf
    for sid, s in scene.surfaces.items():
        info = ref[sid]
        assert np.allclose(s.matrix, info["matrix"], atol=1e-12), sid
        assert np.allclose(s.box, info["box"], atol=1e-9), sid
        assert s.verts == info["verts"]
        assert s.hash == info["hp"]["hash"]
        prims = hs.mesh_arrays(doc, binary, s.mesh)
        mine = house_hash.hash_primitives(prims, s.uv1_px)
        assert mine == s.hash == hsurface.surface_hash(g, s.mesh, s.uv1_px), sid
    assert house_hash.scene_hash({k: s.hash for k, s in scene.surfaces.items()}) == scene.scene_hash
    moved = sorted(k for k, s in scene.surfaces.items() if s.moved)
    assert moved == ["furniture:f_table:0", "lamp:p_living_1"]
    table = scene.surfaces["furniture:f_table:0"]
    assert table.kind == "furniture" and table.bake == "VERTEX" and table.storey == "st_ground"
    lamp = scene.surfaces["lamp:p_living_1"]
    assert lamp.light == 0 and lamp.group == "ceilItems"
    assert scene.surfaces["glass:o_g_win1"].bake == "NO"


def test_world_triangles_are_the_table_in_place(scene):
    pts, tris = hs.world_triangles(scene, "furniture:f_table:0")
    assert len(pts) == scene.surfaces["furniture:f_table:0"].verts and tris.max() < len(pts)
    box = scene.surfaces["furniture:f_table:0"].box
    assert np.allclose(np.concatenate([pts.min(0), pts.max(0)]), box)
    # placed at glTF (3.5, 0, 3.0): the table stands round that point
    assert abs((box[0] + box[3]) / 2 - 3.5) < 0.5 and abs((box[2] + box[5]) / 2 - 3.0) < 0.5


# ---------------------------------------------------------------------------
# zip rules (FORMAT 2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["../escape.txt", "/abs.txt", "dir\\file.txt", "a/./b.txt", "a//b.txt", "C:/x.txt"])
def test_zip_names_refused(bad):
    files = _files(SCENE)
    files[bad] = b"x"
    with pytest.raises(hs.FormatError, match="relative path|empty parts"):
        hs.read_scene(_zip(files))


def test_zip_duplicate_refused():
    files = _files(SCENE)
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buf, "w") as zf:
            for name, data in files.items():
                zf.writestr(name, data)
            zf.writestr("house.glb", files["house.glb"])
    with pytest.raises(hs.FormatError, match="twice"):
        hs.read_zip(buf.getvalue())


def test_zip_encrypted_refused():
    files = _files(SCENE)
    files["extra.txt"] = b"secret"
    data = _set_encrypted(_zip(files), "extra.txt")
    with pytest.raises(hs.FormatError, match="encrypted"):
        hs.read_zip(data)


def test_zip_method_and_garbage_refused():
    files = _files(SCENE)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("extra.txt", b"x" * 100, compress_type=zipfile.ZIP_BZIP2)
    with pytest.raises(hs.FormatError, match="stored or deflated"):
        hs.read_zip(buf.getvalue())
    with pytest.raises(hs.FormatError, match="not a zip"):
        hs.read_zip(b"not a zip at all")


def test_zip_good_sample_reads():
    files = hs.read_zip(SCENE)
    assert set(files) == {"scene.json", "house.glb", "pictures/preview.png"}


# ---------------------------------------------------------------------------
# versions and open lists (FORMAT 2, 13)
# ---------------------------------------------------------------------------

def test_another_major_refused():
    with pytest.raises(hs.FormatError) as e:
        hs.read_scene(_scene_with(lambda d: d.update(version="2.0")))
    assert str(e.value) == ("This house scene was made by a newer House Planner (format 2.0). Update Fresing Render "
                            "to read it.")
    with pytest.raises(hs.FormatError, match=r"older House Planner \(format 0\.9\)"):
        hs.read_scene(_scene_with(lambda d: d.update(version="0.9")))
    with pytest.raises(hs.FormatError, match="not a house scene package"):
        hs.read_scene(_scene_with(lambda d: d.update(format="house-bake")))
    with pytest.raises(hs.FormatError, match="newer Fresing Render"):
        hs.check_version({"format": "house-bake", "version": "3.1"}, "house-bake")
    assert hs.parse_version("1.10") > hs.parse_version("1.9")


def test_newer_minor_read_with_unknown_values_and_fields():
    def change(d):
        d["version"] = "1.3"
        d["new_top"] = {"x": 1}
        r = d["recipe"]
        r["walk_paths"] = []
        r["quality"]["preset"] = "ULTRA"
        r["quality"]["samples"] = None
        r["quality"]["new_q"] = 1
        r["seasons"][1]["foliage"] = "leafless"
        r["moments"][0]["lamps"] = "half"
        r["moments"][0]["sun"]["new_s"] = 1
        r["videos"] = [{"id": "walk1", "kind": "walk", "camera": "garden-view", "moment": "summer-morning",
                        "size": [64, 48], "seconds": 4, "fps": 25},
                       {"id": "turn", "kind": "turntable", "camera": "garden-view", "moment": "summer-morning",
                        "size": [64, 48], "seconds": 4, "fps": 29}]

    def glb_change(g):
        g["nodes"][50]["extras"]["hp"]["kind"] = "pond"            # not in the hash
        g["nodes"][50]["extras"]["hp"]["new_field"] = "x"
    sc = hs.read_scene(_scene_with(change, glb_change))
    assert sc.notes[0] == "Made by a newer House Planner (format 1.3): some extras are not used."
    assert any("walk1" in n for n in sc.notes)
    assert (sc.surfaces["ground:plot"].kind, sc.surfaces["ground:plot"].raw_kind) == ("other", "pond")
    assert sc.recipe.samples == 64 and sc.recipe.preset == "ULTRA"
    assert sc.recipe.seasons[1].foliage == "full"
    assert sc.recipe.moments[0].lamps == "none"
    assert [(v["id"], v["fps"]) for v in sc.recipe.videos] == [("turn", 25)]
    # a known preset with samples null: 0107's samples for it
    sc = hs.read_scene(_scene_with(lambda d: d["recipe"]["quality"].update(samples=None)))
    assert sc.recipe.samples == 16


def test_closed_list_value_refused():
    with pytest.raises(hs.FormatError, match="light choice"):
        hs.read_scene(_scene_with(lambda d: d["recipe"].update(light="HALF")))
    with pytest.raises(hs.FormatError, match="bake"):
        hs.read_scene(_scene_with(glb_change=lambda g: g["nodes"][0]["extras"]["hp"].update(bake="SOME")))
    with pytest.raises(hs.FormatError, match="used by two nodes"):
        hs.read_scene(_scene_with(glb_change=lambda g: g["nodes"][1]["extras"]["hp"].update(id="wall:w_g_front:a")))


def test_a_changed_wall_is_a_note():
    def glb_change(g):
        g["nodes"][0]["extras"]["hp"]["hash"] = "0" * 32
    sc = hs.read_scene(_scene_with(glb_change=glb_change))
    assert any("wall:w_g_front:a" in n and "hash" in n for n in sc.notes)


# ---------------------------------------------------------------------------
# the sun (FORMAT 7.5)
# ---------------------------------------------------------------------------

def test_sun_of_the_format_example():
    d = (0.843629, 0.490152, 0.219185)
    assert hs.gltf_to_blender(d) == (0.843629, -0.219185, 0.490152)
    el, az = hs.sun_angles(d)
    assert abs(el - 29.35) < 0.01
    assert abs(az - (-14.6)) < 0.05                   # 14.6° from Blender's +X towards -Y
    assert abs(hs.sun_rotation_deg(az) - 104.6) < 0.5
    assert abs(hs.sun_rotation_deg(az, 90.0) - (90.0 - az)) < 1e-9
    assert hs.sun_rotation_deg(-120.0) == -150.0 and hs.sun_rotation_deg(-90.0) == 180.0


def test_north_and_mismatch(scene):
    # place.north [sin 15°, -cos 15°] in glTF = scene azimuth 75°
    assert abs(hs.north_scene_az(scene.place["north"]) - 75.0) < 1e-4
    for m in scene.recipe.moments:
        assert hs.sun_mismatch(m, scene.place["north"]) < 0.5
    # the compass azimuth turned into a scene azimuth agrees with the direction's
    for m in scene.recipe.moments:
        _, az = hs.sun_angles(m.direction)
        assert abs(hs._wrap(weather.to_scene_az(m.azimuth, 75.0) - az)) < 0.05
    wrong = hs.Moment(**{**scene.recipe.moments[0].__dict__, "azimuth": 100.0})
    assert hs.sun_mismatch(wrong, scene.place["north"]) > 5


def _check_weather(el, az, day, lat, bearing=None):
    r = hs.weather_sun(el, az, day, lat, bearing=bearing)
    assert set(r) == {"hour", "use_date", "day", "latitude", "north"}
    assert 0.0 <= r["hour"] <= 24.0 and abs(r["latitude"]) <= weather.MAX_LATITUDE
    ch = weather.derive(weather.State(**r))
    assert abs(ch["sun_el"] - el) < 0.5, (ch["sun_el"], el)
    assert abs(hs._wrap(ch["sun_az"] - az)) < 0.5, (ch["sun_az"], az)
    return r


def test_weather_sun_lands_on_house_planners_sun(scene):
    for m in scene.recipe.moments:
        sun = hs.moment_sun(scene, m)
        r = _check_weather(sun["elevation"], sun["scene_az"], scene.season(m.season).day,
                           scene.place["latitude"], bearing=m.azimuth)
        assert r == sun["weather"]
        assert abs(hs._wrap(r["north"] - 75.0)) < 2.0          # north lands near the real north
        assert sun["night"] == (m.id == "winter-night")
    # morning and evening on their own side of noon
    ms = {m.id: hs.moment_sun(scene, m)["weather"]["hour"] for m in scene.recipe.moments}
    assert ms["summer-morning"] < 12 < ms["summer-evening"]
    # the night sun at -43.8°
    night = scene.moment("winter-night")
    el, _ = hs.sun_angles(night.direction)
    assert abs(el - (-43.77)) < 0.01
    # a noon sun at its highest and above what 0109's sun reaches at that latitude: the latitude moves
    top = 90.0 - abs(53.5 - weather.declination(172))
    r = _check_weather(top + 2.0, -105.0, 172, 53.5)
    assert r["latitude"] < 53.5 - 1.9
    r = _check_weather(top, 30.0, 172, 53.5)
    assert abs(r["hour"] - 12.0) < 0.2
    _check_weather(-60.0, 10.0, 15, 53.5)          # deeper than midnight there
    _check_weather(89.0, 0.0, 172, 53.5)


# ---------------------------------------------------------------------------
# encoding (FORMAT 8.3)
# ---------------------------------------------------------------------------

def test_round_half_away_from_zero():
    assert [house_hash.round_half_away(x) for x in (0.5, 1.5, 2.5, -0.5, -2.5, 0.49)] == [1, 2, 3, -1, -3, 0]
    # 255 x sqrt(L / scale) exactly 0.5 and 2.5 (0107's encode rounds these to 0 and 2)
    assert 255 * math.sqrt(0.25 / 65025) == 0.5 and 255 * math.sqrt(6.25 / 65025) == 2.5
    assert hs.encode([0.25, 6.25], 65025.0).tolist() == [1, 3]


def test_encode_known_values():
    s = 2.0
    assert hs.encode([s, s / 4, 0.0, -1.0, 5 * s, np.nan, np.inf, -np.inf], s).tolist() == \
        [255, 128, 0, 0, 255, 0, 255, 0]          # s / 4: 127.5 rounds up
    assert hs.encode(np.ones((4, 5, 3)), 1.0).shape == (4, 5, 3)
    assert hs.encode(np.ones(3), 1.0).dtype == np.uint8


def test_decode_encode_within_one_step():
    rng = np.random.default_rng(1)
    s = 3.7
    L = rng.uniform(0, s, 5000)
    b = hs.encode(L, s).astype(int)
    lo = hs.decode(np.clip(b - 1, 0, 255), s)
    hi = hs.decode(np.clip(b + 1, 0, 255), s)
    assert (lo <= L + 1e-6).all() and (L <= hi + 1e-6).all()
    assert (hs.encode(hs.decode(np.arange(256), s), s) == np.arange(256)).all()


def test_moment_scale():
    rng = np.random.default_rng(2)
    a, b = rng.uniform(0, 2, (30, 40, 3)), rng.uniform(0, 5, (100, 3))
    want = np.percentile(np.concatenate([a.ravel(), b.ravel()]), 99.9)
    assert abs(hs.moment_scale([a, b]) - want) < 1e-12
    assert hs.moment_scale([np.zeros((10, 3))]) > 0
    assert hs.moment_scale([]) > 0
    few = np.zeros(10000)
    few[0] = 0.3                                     # the percentile is 0, the brightest value is not
    assert hs.moment_scale([few]) == 0.3


# ---------------------------------------------------------------------------
# pages (FORMAT 8.3)
# ---------------------------------------------------------------------------

def _check_layout(sizes, pages, rects, gap=2):
    for k, (p, x, y) in rects.items():
        w, h = sizes[k]
        pw, ph = pages[p]
        assert pw in hs.SIDES and pw == ph
        assert 0 <= x and 0 <= y and x + w <= pw and y + h <= ph
    items = list(rects.items())
    for i, (ka, (pa, xa, ya)) in enumerate(items):
        wa, ha = sizes[ka]
        for kb, (pb, xb, yb) in items[i + 1:]:
            if pa != pb:
                continue
            wb, hb = sizes[kb]
            apart = xb >= xa + wa + gap or xa >= xb + wb + gap or yb >= ya + ha + gap or ya >= yb + hb + gap
            assert apart, (ka, kb)


def test_layout_rules():
    rng = np.random.default_rng(3)
    sizes = {f"s{i}": (int(rng.integers(5, 300)), int(rng.integers(5, 300))) for i in range(120)}
    sizes["huge"] = (1500, 20)
    pages, rects = hs.layout(sizes, 1024)
    assert "huge" not in rects and len(rects) == 120
    assert all(p == (1024, 1024) for p in pages)
    _check_layout(sizes, pages, rects)
    # the smallest page side that holds it in one page
    pages, rects = hs.layout({"a": (100, 100), "b": (100, 100)}, 2048)
    assert pages == [(256, 256)]
    _check_layout({"a": (100, 100), "b": (100, 100)}, pages, rects)
    assert hs.layout({}, 1024) == ([], {})
    pages, rects = hs.layout(sizes, 2048)
    assert len(pages) == 1 and pages[0][0] == 2048
    _check_layout(sizes, pages, rects)


def test_sample_fits_one_page_per_moment(scene):
    sizes = {("", k): s.uv1_px for k, s in scene.surfaces.items() if s.uv1_px}
    sizes.update({("st_ground", k): s.uv1_px for k, s in scene.surfaces.items()
                  if s.uv1_px and s.storey == "st_ground"})
    pages, rects = hs.layout(sizes, scene.recipe.page_size)
    assert pages == [(1024, 1024)] and len(rects) == len(sizes) == 48 + 20
    _check_layout(sizes, pages, rects)
    fill = sum(w * h for w, h in sizes.values()) / 1024 ** 2
    assert abs(fill - 0.43) < 0.01                   # FORMAT section 11: about 43 %


def test_page_png_has_no_colour_chunks():
    data = hs.page_png(np.zeros((256, 256, 3), np.uint8))
    assert _chunks(data) == [b"IHDR", b"IDAT", b"IEND"]
    assert hs.png_page_problem(data) is None
    assert hs.png_page_problem(web3d.png(np.zeros((4, 4, 4), np.uint8))).startswith("is 8-bit colour type 6")


# ---------------------------------------------------------------------------
# a whole package from made-up results
# ---------------------------------------------------------------------------

SNOW = ("snow:roof:st_first:0", "snow:ground:plot")


def _fake(scene, sid, rng, level):
    s = scene.surfaces[sid]
    if s.bake == "MAP":
        W, H = s.uv1_px
        a = np.empty((H, W, 3), np.float32)
        a[:, :, 0] = level * np.linspace(0.05, 1.0, W)[None, :]       # brighter to the right
        a[:, :, 1] = level * np.linspace(0.05, 1.0, H)[:, None]       # brighter up (Blender row 0 = the bottom)
        a[:, :, 2] = 0.5 * level
        return a
    return rng.uniform(0, level, (s.verts, 3)).astype(np.float32)


def _results(scene, moment, rng, level):
    maps = {sid: _fake(scene, sid, rng, level) for sid, s in scene.surfaces.items() if s.bake != "NO"}
    if moment.season == "winter":
        maps.update({SNOW[0]: rng.uniform(0, level, (20, 3)), SNOW[1]: rng.uniform(0, level, (16, 3))})
    open_ = {"st_ground": {sid: _fake(scene, sid, rng, 0.8 * level) for sid, s in scene.surfaces.items()
                           if s.bake != "NO" and s.storey == "st_ground"}}
    return maps, open_


@pytest.fixture(scope="module")
def package(scene, tmp_path_factory):
    rng = np.random.default_rng(4)
    w = hs.BakeWriter(scene, light="SOFT", samples=4, app_version="0.2.90", created="2026-11-13T12:00:00Z")
    w.add_snow("winter", _files(BAKE)["snow/winter.glb"])
    kept = {}
    for i, m in enumerate(scene.recipe.moments):
        sun = hs.moment_sun(scene, m)
        level = 0.01 if sun["night"] else 1.0 + i
        maps, open_ = _results(scene, m, rng, level)
        kept[m.id] = (maps, open_)
        w.add_moment(m.id, maps, open_, reference=[level, 0.97 * level, 0.92 * level],
                     exposure=weather.exposure_for(sun["elevation"], m.clouds),
                     sun_light=None if sun["night"] else [2.5, 2.4, 2.3])
    w.add_photo("photo-1", web3d.png(np.full((240, 320, 3), 90, np.uint8)), "png")
    path = str(tmp_path_factory.mktemp("bake") / "sample.hpbake")
    w.write(path)
    return path, w, kept


def test_package_passes_the_checker(package):
    path, w, _ = package
    assert w.problems == []
    run = subprocess.run([sys.executable, "-B", os.path.join(PIN, "check.py"), path, "--scene", SCENE],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "ERROR" not in run.stdout and "WARNING" not in run.stdout, run.stdout
    assert run.stdout.strip().endswith("OK"), run.stdout


def test_package_contents(package, scene):
    path, _, kept = package
    files = hs.read_zip(path)
    doc = json.loads(files["bake.json"])
    assert doc["light"] == "SOFT" and doc["scene"] == {"id": scene.id, "scene_hash": scene.scene_hash}
    assert doc["quality"] == {"texels_per_m": 16.0, "samples": 4, "denoised": True}
    assert len(doc["surfaces"]) == 51                 # every surface but the glass
    assert "matrix" in doc["surfaces"]["furniture:f_table:0"] and "matrix" not in doc["surfaces"]["floor:r_bed"]
    assert not any(k.startswith("snow:") for k in doc["surfaces"])
    by_id = {m["id"]: m for m in doc["moments"]}
    assert by_id["winter-night"]["sun_light"] is None
    assert by_id["summer-morning"]["sun_light"] == [2.5, 2.4, 2.3]
    assert by_id["winter-night"]["encoding"]["exposure"] > 3
    assert len(doc["pages"]) == 4 and all(p["size"] == [1024, 1024] for p in doc["pages"])  # one page per moment
    assert set(by_id["winter-noon"]["maps"]) >= set(SNOW) and not set(SNOW) & set(by_id["summer-morning"]["maps"])
    assert set(by_id["winter-noon"]["open"]["st_ground"]) == {k for k, s in scene.surfaces.items()
                                                              if s.storey == "st_ground" and s.bake != "NO"}
    # one rect layout for every moment
    rects = [{k: v["rect"] for k, v in m["maps"].items() if "rect" in v} for m in doc["moments"]]
    assert all(r == rects[0] for r in rects)
    # pages: no colour chunks; rows top-down (Blender row 0 = the last PNG row of the rect)
    pages = {p["id"]: p["file"] for p in doc["pages"]}
    for f in pages.values():
        assert _chunks(files[f]) == [b"IHDR", b"IDAT", b"IEND"]
    m = by_id["summer-evening"]
    scale = m["encoding"]["scale"]
    e = m["maps"]["floor:r_living"]
    x, y, W, H = e["rect"]
    page = _png_pixels(files[pages[e["page"]]])
    got = page[y:y + H, x:x + W]
    src = kept["summer-evening"][0]["floor:r_living"]
    assert (got == hs.encode(src, scale)[::-1]).all()
    assert (got[-1] == hs.encode(src[0], scale)).all()          # the bottom row of the map is the last PNG row
    assert got[0, 0, 1] > got[-1, 0, 1]                         # brighter up: brighter in the top PNG rows
    assert got[0, -1, 0] > got[0, 0, 0]                         # brighter to the right, not mirrored
    # open results on their own rects, the same page
    eo = m["open"]["st_ground"]["floor:r_living"]
    assert eo["page"] == e["page"] and eo["rect"] != e["rect"] and eo["rect"][2:] == e["rect"][2:]
    # light per vertex in the .glb's order, in its own range
    v = m["maps"]["furniture:f_table:0"]
    vfile = {x["id"]: x["file"] for x in doc["vertex_files"]}[v["vertex"]]
    raw = np.frombuffer(files[vfile], np.uint8).reshape(-1, 3)[v["offset"]:v["offset"] + v["count"]]
    assert (raw == hs.encode(kept["summer-evening"][0]["furniture:f_table:0"], scale)).all()
    # the scale: the 99.9th percentile of the moment's results
    maps, open_ = kept["summer-evening"]
    want = hs.moment_scale(list(maps.values()) + list(open_["st_ground"].values()))
    assert abs(scale - want) < 1e-12
    # stored and deflated as FORMAT 2 recommends
    with zipfile.ZipFile(path) as zf:
        kinds = {i.filename: i.compress_type for i in zf.infolist()}
    assert kinds["bake.json"] == zipfile.ZIP_DEFLATED and kinds["snow/winter.glb"] == zipfile.ZIP_STORED
    assert all(kinds[f] == zipfile.ZIP_STORED for f in pages.values())


def test_structure_problems(package, scene):
    path, _, _ = package
    assert hs.structure_problems(path) == []
    assert hs.structure_problems(path, scene) == []
    files = hs.read_zip(path)
    doc = json.loads(files["bake.json"])
    # a rect of the wrong size
    e = doc["moments"][0]["maps"]["floor:r_living"]
    e["rect"][2] -= 1
    broken = dict(files, **{"bake.json": json.dumps(doc).encode()})
    probs = hs.structure_problems(_zip(broken), scene)
    assert any("floor:r_living" in p and "rect" in p for p in probs), probs
    # a missing page file
    missing = {k: v for k, v in files.items() if k != doc["pages"][1]["file"]}
    probs = hs.structure_problems(_zip(missing))
    assert any("is not in the package" in p for p in probs), probs
    # sun_light at night, a page with a colour chunk, another major
    doc = json.loads(files["bake.json"])
    doc["moments"][3]["sun_light"] = [1, 1, 1]
    probs = hs.structure_problems(_zip(dict(files, **{"bake.json": json.dumps(doc).encode()})), scene)
    assert any("sun_light" in p for p in probs)
    f = doc["pages"][0]["file"]
    png = files[f]
    srgb = struct.pack(">I", 1) + b"sRGB" + b"\0" + struct.pack(">I", zlib.crc32(b"sRGB\0"))
    coloured = png[:33] + srgb + png[33:]
    probs = hs.structure_problems(_zip(dict(files, **{f: coloured})))
    assert any("sRGB" in p for p in probs)
    doc = json.loads(files["bake.json"])
    doc["version"] = "2.0"
    assert hs.structure_problems(_zip(dict(files, **{"bake.json": json.dumps(doc).encode()}))) == \
        ["This bake was made by a newer Fresing Render (format 2.0). Update Fresing Render to read it."]


def test_wrong_results_are_left_out(scene):
    w = hs.BakeWriter(scene, light="SOFT", samples=4, created="2026-11-13T12:00:00Z")
    rng = np.random.default_rng(5)
    m = scene.recipe.moments[0]
    maps, open_ = _results(scene, m, rng, 1.0)
    W, H = scene.surfaces["floor:r_bed"].uv1_px
    maps["floor:r_bed"] = np.ones((H + 1, W, 3))                                  # wrong shape
    maps["floor:r_bath"] = np.ones((scene.surfaces["floor:r_bath"].verts, 3))      # per vertex for a MAP surface
    maps["furniture:f_table:0"] = np.ones((5, 3))                                  # wrong vertex count
    maps["glass:o_g_win1"] = np.ones((scene.surfaces["glass:o_g_win1"].verts, 3))  # bake NO
    maps["floor:nowhere"] = np.ones((3, 3))                                        # not in the house
    maps[SNOW[0]] = np.ones((20, 3))                                               # no snow added
    open_["st_ground"]["floor:r_bed"] = maps["floor:r_bath"]                       # another storey
    w.add_moment(m.id, maps, open_, reference=[1, 1, 1], exposure=0.0, sun_light=[1, 1, 1])
    entry = w.bake_json()["moments"][0]
    for sid in ("floor:r_bed", "floor:r_bath", "furniture:f_table:0", "glass:o_g_win1", "floor:nowhere", SNOW[0]):
        assert sid not in entry["maps"], sid
        assert any(sid in p for p in w.problems), sid
    assert "floor:r_bed" not in entry["open"]["st_ground"]
    assert "floor:r_living" in entry["maps"] and "floor:r_bed" not in w.bake_json()["surfaces"]
    assert all("\n" not in p and len(p) <= 500 for p in w.problems)
    # an unknown moment, a photo not in the recipe, a light other than the recipe's
    w.add_moment("no-such-moment", {}, reference=[1, 1, 1], exposure=0.0)
    w.add_photo("photo-9", web3d.png(np.zeros((2, 2, 3), np.uint8)), "png")
    assert any("no-such-moment" in p for p in w.problems) and any("photo-9" in p for p in w.problems)
    with pytest.raises(ValueError):
        hs.BakeWriter(scene, light="ALL", samples=4)


def test_night_and_all_have_no_sun_light(scene):
    sc = hs.read_scene(_scene_with(lambda d: d["recipe"].update(light="ALL")))
    w = hs.BakeWriter(sc, light="ALL", samples=4, created="2026-11-13T12:00:00Z")
    m = sc.recipe.moments[0]
    w.add_moment(m.id, {"floor:r_living": _fake(sc, "floor:r_living", None, 1.0)}, reference=[1, 1, 1],
                 exposure=0.0, sun_light=[1, 1, 1])
    assert w.bake_json()["moments"][0]["sun_light"] is None
    w = hs.BakeWriter(scene, light="SOFT", samples=4)
    w.add_moment("winter-night", {"floor:r_living": _fake(scene, "floor:r_living", None, 0.01)},
                 reference=[0.01] * 3, exposure=4.0, sun_light=[1, 1, 1])
    assert w.bake_json()["moments"][0]["sun_light"] is None
    assert w.bake_json()["created"].endswith("Z") and hs.ID_RE.match(w.bake_id)


# ---------------------------------------------------------------------------
# what the format's checker calls an ERROR is refused with a plain sentence (the independent tester's findings)
# ---------------------------------------------------------------------------

def _node_of(g, sid):
    return next(n for n in g["nodes"] if ((n.get("extras") or {}).get("hp") or {}).get("id") == sid)


@pytest.mark.parametrize("change,words", [
    (lambda d: d.update(hash="hp-hash/2"), "hp-hash/1"),
    (lambda d: d.update(uv1="hp-uv/2"), "hp-uv/1"),
    (lambda d: d.update(title="two\nlines"), "control character"),
    (lambda d: d.update(version="١.٠"), "version"),
    (lambda d: d["recipe"].update(open_storeys=["st_attic"]), "not an included storey"),
    (lambda d: d["recipe"].update(open_storeys="st_ground"), "not a list"),
    (lambda d: d["recipe"]["moments"][1].update(id="summer-morning"), "listed twice"),
    (lambda d: d["recipe"]["seasons"].append(dict(d["recipe"]["seasons"][0])), "listed twice"),
    (lambda d: d["recipe"]["moments"][0].update(id="a/../b"), "not an id"),
    (lambda d: d["recipe"]["photos"][0].update(camera="nowhere"), "camera"),
    (lambda d: d["recipe"]["photos"][0].update(moment="nowhen"), "moment"),
    (lambda d: d["recipe"]["photos"][0].update(falling={"rain": "nan"}), "falling.rain"),
], ids=["hash", "uv1", "control", "digits", "open-unknown", "open-text", "moment-twice", "season-twice", "moment-id",
        "photo-camera", "photo-moment", "falling"])
def test_scene_errors_refused(change, words):
    with pytest.raises(hs.FormatError) as e:
        hs.read_scene(_scene_with(change))
    assert words in str(e.value) and "\n" not in str(e.value), str(e.value)


def _sparse(g):
    a = g["meshes"][0]["primitives"][0]["attributes"]["POSITION"]
    g["accessors"][a]["sparse"] = {"count": 1}


@pytest.mark.parametrize("glb_change,words", [
    (lambda g: g.update(extensionsRequired=["EXT_meshopt_compression"]), "extensions"),
    (lambda g: _node_of(g, "floor:r_living").update(scale=[-1.0, 1.0, 1.0]), "scaled or mirrored"),
    (lambda g: _node_of(g, "floor:r_living")["extras"]["hp"].update(storey=None), "no storey"),
    (lambda g: _node_of(g, "floor:r_living")["extras"]["hp"].update(storey="st_attic"), "not an included"),
    (lambda g: _node_of(g, "garden:ga_terrace")["extras"]["hp"].update(storey="st_ground"), "no storey"),
    (lambda g: _node_of(g, "garden:ga_terrace")["extras"]["hp"].update(id="garden:" + "t" * 60), "63 bytes"),
    (lambda g: _node_of(g, "garden:ga_terrace")["extras"]["hp"].update(id="Garden terrace"), "<kind>:<name>"),
    (lambda g: _node_of(g, "garden:ga_terrace")["extras"]["hp"].update(source="a\tb"), "control character"),
    (_sparse, "sparse"),
], ids=["required", "mirrored-map", "storey-null", "storey-unknown", "site-with-storey", "id-long", "id-form",
        "extras-control", "sparse"])
def test_house_errors_refused(glb_change, words):
    with pytest.raises(hs.FormatError) as e:
        hs.read_scene(_scene_with(glb_change=glb_change))
    assert words in str(e.value), str(e.value)


def test_broken_indices_refused():
    files = _files(SCENE)
    g = hglb.Glb.parse(files["house.glb"])
    k = g.json["meshes"][0]["primitives"][0]["indices"]
    acc = g.json["accessors"][k]
    size = {5121: 1, 5123: 2, 5125: 4}[acc["componentType"]]
    at = g.json["bufferViews"][acc["bufferView"]].get("byteOffset", 0) + acc.get("byteOffset", 0)

    def fewer(n):
        return lambda j, b: j["accessors"][k].update(count=acc["count"] - n)

    def past(j, b):
        b[at:at + size] = b"\xff" * size
    for change, words in ((fewer(3), "not used"), (fewer(1), "whole number of triangles"), (past, "past")):
        j, b = json.loads(json.dumps(g.json)), bytearray(g.bin)
        change(j, b)
        f = dict(files)
        f["house.glb"] = hglb.pack(j, bytes(b))
        with pytest.raises(hs.FormatError) as e:
            hs.read_scene(_zip(f))
        assert words in str(e.value), str(e.value)


def test_zip_name_not_utf8_refused():
    files = _files(SCENE)
    files["pictures/QQ.png"] = b"x"
    data = _zip(files).replace(b"pictures/QQ.png", b"pictures/\xe9Q.png")      # Latin-1, no UTF-8 flag
    with pytest.raises(hs.FormatError) as e:
        hs.read_scene(data)
    assert "UTF-8" in str(e.value)
    files = _files(SCENE)
    files["pictures/café.png"] = b"x"                                      # zipfile sets the UTF-8 flag
    assert len(hs.read_scene(_zip(files)).surfaces) == 52


def test_writer_second_snow_file_drops_the_old_light(scene, tmp_path):
    from fresing_render.core import house_snow
    w = hs.BakeWriter(scene, light="SOFT", samples=4, created="2026-11-13T12:00:00Z")
    w.add_snow("winter", _files(BAKE)["snow/winter.glb"])
    m = scene.moment("winter-noon")
    maps, open_ = _results(scene, m, np.random.default_rng(6), 1.0)
    w.add_moment(m.id, maps, open_, reference=[1, 1, 1], exposure=0.0)
    vertex_before = {k for k, v in w.bake_json()["moments"][0]["maps"].items() if "vertex" in v}
    season = scene.season("winter")
    src, blockers = house_snow.sources_from_glb(scene.glb, season.foliage)
    layers = house_snow.build_layers(src, season.snow_cover, blockers)
    w.add_snow("winter", house_snow.layers_glb(layers), sources=src)
    entry = w.bake_json()["moments"][0]
    assert not set(SNOW) & set(entry["maps"])                       # the old layers' light is gone …
    assert vertex_before - set(SNOW) <= set(entry["maps"])          # … the rest stays, packed again
    assert any("made again" in p and "winter-noon" in p for p in w.problems)
    path = str(tmp_path / "again.hpbake")
    w.write(path)
    rep = hcheck.check(path, scene=SCENE)
    assert rep.errors == [], rep.errors
    assert hs.structure_problems(path, scene) == []


def test_writer_snow_id_too_long_is_named(scene):
    w = hs.BakeWriter(scene, light="SOFT", samples=4)
    long_id = "ground:" + "p" * 56                                  # 63 bytes; "snow:" + it is 68
    assert hs.snow_id_too_long(long_id) and not hs.snow_id_too_long("ground:ok")
    w.add_snow("winter", _files(BAKE)["snow/winter.glb"], sources=[{"id": long_id}, {"id": "ground:ok"}])
    assert any("1 surface(s) get no snow" in p and long_id in p for p in w.problems)


def test_writer_cleans_its_own_texts_and_bad_pictures(scene):
    w = hs.BakeWriter(scene, light="SOFT", samples=4, app_version="0.2.90\nbeta", created="2026-11-13\n")
    doc = w.bake_json()
    assert doc["generator"]["version"] == "0.2.90 beta"
    assert hs.CREATED_RE.fullmatch(doc["created"])
    assert hs.BakeWriter(scene, light="SOFT", samples=4, created="2026-11-13T12:00Z").created == "2026-11-13T12:00Z"
    assert hs.BakeWriter(scene, light="SOFT", samples=4, created="2026-13-40T12:00:00Z").created != \
        "2026-13-40T12:00:00Z"
    for data in (b"\x89PNG\r\n\x1a\n" + b"\0" * 4, b"\xff\xd8\xff\xc0\0", b"", None):
        w.add_photo("photo-1", data, "png")
    w.add_video("turn", b"\0" * 10, "mp4", size=None)
    assert w.bake_json()["photos"] == [] and w.bake_json()["videos"] == []
    assert hs.picture_info(web3d.png(np.zeros((3, 5, 3), np.uint8))) == ("png", 5, 3)


def test_writer_infinite_light_is_the_brightest(scene):
    w = hs.BakeWriter(scene, light="SOFT", samples=4)
    sid = "furniture:f_table:0"
    a = np.full((scene.surfaces[sid].verts, 3), 0.5, np.float32)
    a[0] = [np.inf, np.nan, -np.inf]
    w.add_moment("summer-morning", {sid: a}, reference=[1, 1, 1], exposure=0.0)
    assert w.bake_json()["moments"][0]["encoding"]["scale"] == pytest.approx(0.5)   # inf does not set the scale
    raw = w.files()[w.bake_json()["vertex_files"][0]["file"]]
    assert list(raw[:3]) == [255, 0, 0] and raw[3] == 255
    assert any("+inf as 255" in p for p in w.problems)
