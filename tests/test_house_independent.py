"""Task 0114, independent tests: written from FORMAT.md (house-scene-format v1.0) and the task's Design by a tester who
did not write the code, to break the House Planner reader and writer (core/house_scene.py, core/house_snow.py,
core/house_hash.py) and the Blender side (blender/house_import.py, house_bake.py).

A test whose comment starts with ``# FOUND:`` failed when it was written: it names a fault and what FORMAT.md says.
Everything else passed. The pinned checker (tests/data/house/hsf-v1.0) is the judge of every written package:
"ERROR = a reader must refuse it" (FORMAT 12)."""

import copy
import hashlib
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

from fresing_render.core import house_hash, house_snow, weather, web3d
from fresing_render.core import house_scene as hs

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
SCENE = os.path.join(PIN, "samples", "sample-house.hpscene")
BAKE = os.path.join(PIN, "samples", "sample-house.hpbake")
sys.path.insert(0, PIN)
from hsf import check as hcheck  # noqa: E402 – the pinned checker: the judge, never the code under test
from hsf import glb as hglb  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _files(path=SCENE):
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def _zip(files, method=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                  # "Duplicate name" is what some tests want
        with zipfile.ZipFile(buf, "w") as zf:
            for name, data in (files.items() if isinstance(files, dict) else files):
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = method
                zf.writestr(info, data)
    return buf.getvalue()


def _variant(change=None, glb_change=None, raw=None, extra=None) -> bytes:
    """The sample scene with scene.json (a dict function or raw bytes) and / or house.glb changed."""
    files = _files()
    doc = json.loads(files["scene.json"])
    if change:
        change(doc)
    files["scene.json"] = raw if raw is not None else json.dumps(doc).encode()
    if glb_change:
        g = hglb.Glb.parse(files["house.glb"])
        glb_change(g)
        files["house.glb"] = hglb.pack(g.json, g.bin)
        if raw is None:                 # FORMAT 5's scene_hash of the changed labels, so no stale-hash note hides a fault
            pairs = {}
            for n in g.json.get("nodes", []):
                hp = (n.get("extras") or {}).get("hp") if isinstance(n.get("extras"), dict) else None
                if isinstance(hp, dict) and isinstance(hp.get("id"), str) and isinstance(hp.get("hash"), str):
                    pairs[hp["id"]] = hp["hash"]
            text = "".join(f"{k} {pairs[k]}\n" for k in sorted(pairs))
            doc["scene_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
            files["scene.json"] = json.dumps(doc).encode()
    if extra:
        files.update(extra)
    return _zip(files)


def _node(g, sid):
    return next(i for i, n in enumerate(g.json["nodes"]) if ((n.get("extras") or {}).get("hp") or {}).get("id") == sid)


def _strict_json(data: bytes):
    def bad(name):
        raise ValueError(name)
    return json.loads(data.decode("utf-8"), parse_constant=bad)


def _control(obj):
    if isinstance(obj, str):
        return any(ord(c) < 32 or ord(c) == 127 for c in obj)
    if isinstance(obj, dict):
        return any(_control(k) or _control(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_control(v) for v in obj)
    return False


def _png_rows(data: bytes) -> np.ndarray:
    """(h, w, 3) uint8 of an 8-bit RGB PNG, any filter (written here, not taken from the code under test)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            assert (depth, ctype, inter) == (8, 2, 0)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = 3 * w
    out = np.zeros((h, stride), np.int32)
    prev = np.zeros(stride, np.int32)
    for r in range(h):
        f = raw[r * (stride + 1)]
        line = np.frombuffer(raw, np.uint8, stride, r * (stride + 1) + 1).astype(np.int32)
        cur = np.zeros(stride, np.int32)
        for i in range(stride):
            a = cur[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if f == 0:
                p = 0
            elif f == 1:
                p = a
            elif f == 2:
                p = b
            elif f == 3:
                p = (a + b) // 2
            else:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            cur[i] = (line[i] + p) & 0xFF
        out[r] = cur
        prev = cur
    return out.reshape(h, w, 3).astype(np.uint8)


def _my_encode(L, scale):
    """FORMAT 8.3 written out here: b = clamp(round(255 sqrt(max(L, 0) / scale)), 0, 255), half away from zero."""
    x = 255.0 * np.sqrt(np.maximum(np.asarray(L, np.float64), 0.0) / scale)
    return np.clip(np.floor(x + 0.5), 0, 255).astype(np.uint8), x


def _results(scene, val, rng=None, snow=None):
    """Plain results for every MAP / VERTEX surface: ``val`` everywhere (or random up to val)."""
    out = {}
    for sid, s in scene.surfaces.items():
        if s.bake == "MAP" and s.uv1_px:
            shape = (s.uv1_px[1], s.uv1_px[0], 3)
        elif s.bake == "VERTEX":
            shape = (s.verts, 3)
        else:
            continue
        out[sid] = (rng.uniform(0, val, shape) if rng is not None else np.full(shape, val)).astype(np.float32)
    for sid, n in (snow or {}).items():
        out[sid] = np.full((n, 3), val, np.float32)
    return out


def _writer(scene, **kw):
    return hs.BakeWriter(scene, light=scene.recipe.light, samples=4, app_version="0.2.90",
                         created="2026-11-13T12:00:00Z", **kw)


def _check(writer, tmp_path, scene_path=SCENE, name="b"):
    path = str(tmp_path / f"{name}.hpbake")
    writer.write(path)
    rep = hcheck.check(path, scene=scene_path)
    return path, rep.errors, rep.warnings


@pytest.fixture(scope="module")
def scene():
    return hs.read_scene(SCENE)


def _snow_layers(scene, season_id="winter"):
    season = scene.season(season_id)
    src, blockers = house_snow.sources_from_glb(scene.glb, season.foliage)
    return house_snow.build_layers(src, season.snow_cover, blockers)


@pytest.fixture(scope="module")
def winter_snow(scene):
    layers = _snow_layers(scene)
    return layers, house_snow.layers_glb(layers)


# ---------------------------------------------------------------------------
# zip rules (FORMAT 2: readers MUST refuse anything else)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["../x", "/abs", "C:\\x", "C:/x", "a//b", "./x", "x/./y", "x/../y", "x/..",
                                  "pictures\\p.png", ".."])
def test_zip_names_that_must_be_refused(name):
    files = _files()
    files[name] = b"x"
    with pytest.raises(hs.FormatError):
        hs.read_scene(_zip(files))


def test_zip_folder_entries_and_case_variants_are_read():
    files = list(_files().items()) + [("pictures/", b""), ("House.glb", b"not the house")]
    s = hs.read_scene(_zip(files))
    assert len(s.surfaces) == 52                          # "house.glb" itself, not "House.glb"


def test_zip_same_name_twice_refused():
    files = list(_files().items())
    files.append(("house.glb", dict(files)["house.glb"]))
    with pytest.raises(hs.FormatError):
        hs.read_scene(_zip(files))


def _patch_all(data: bytes, old: bytes, new: bytes) -> bytes:
    assert len(old) == len(new) and data.count(old) >= 2
    return data.replace(old, new)


# FOUND: a file name whose bytes are not UTF-8 (no UTF-8 flag, byte 0xFF) is read. FORMAT 2: "UTF-8 names … Readers
# MUST refuse anything else." (The pinned checker reads it too: a question for the leads.)
def test_zip_name_that_is_not_utf8_refused():
    files = _files()
    files["pictures/QQQQ.png"] = b"x"
    data = _patch_all(_zip(files), b"pictures/QQQQ.png", b"pictures/\xff\xfeQQ.png")
    with pytest.raises(hs.FormatError):
        hs.read_scene(data)


def _set_flag(data: bytes, name: str, *, flag=None, method=None, size=None) -> bytes:
    """Change one entry's flag bits / method / uncompressed size in its local header and the central directory."""
    b = bytearray(data)
    info = zipfile.ZipFile(io.BytesIO(data)).getinfo(name)
    lh = info.header_offset
    eocd = b.rfind(b"PK\x05\x06")
    count, _, cd = struct.unpack_from("<HII", b, eocd + 10)
    pos = cd
    for _ in range(count):
        n, e, c = struct.unpack_from("<HHH", b, pos + 28)
        if bytes(b[pos + 46:pos + 46 + n]).decode("utf-8", "replace") == name:
            for base, fo, mo, so in ((lh, 6, 8, 22), (pos, 8, 10, 24)):
                if flag is not None:
                    b[base + fo] |= flag
                if method is not None:
                    struct.pack_into("<H", b, base + mo, method)
                if size is not None:
                    struct.pack_into("<I", b, base + so, size)
        pos += 46 + n + e + c
    return bytes(b)


def test_zip_encrypted_refused():
    with pytest.raises(hs.FormatError):
        hs.read_scene(_set_flag(_zip(_files()), "house.glb", flag=1))


@pytest.mark.parametrize("method", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA, 99])
def test_zip_other_methods_refused(method):
    with pytest.raises(hs.FormatError):
        hs.read_scene(_set_flag(_zip(_files()), "house.glb", method=method))


def test_zip_a_size_that_lies_is_refused_without_unpacking_it():
    # the directory says 600 MB (above the format's 512 MB a file): refused before anything is unpacked
    with pytest.raises(hs.FormatError):
        hs.read_scene(_set_flag(_zip(_files()), "house.glb", size=600 * 2**20))
    # it says 10 bytes, the data is longer: refused (never half read)
    with pytest.raises(hs.FormatError):
        hs.read_scene(_set_flag(_zip(_files()), "house.glb", size=10))


@pytest.mark.parametrize("data", [b"", b"PK", b"PK\x05\x06" + b"\0" * 18, b"\0" * 100, b"not a zip at all"])
def test_zip_garbage_refused(data):
    with pytest.raises(hs.FormatError):
        hs.read_scene(data)


def test_zip_cut_off_or_bytes_flipped_never_crashes():
    data = _zip(_files(), zipfile.ZIP_STORED)
    rng = np.random.default_rng(3)
    for cut in (len(data) // 3, len(data) - 30, len(data) - 1):
        with pytest.raises(hs.FormatError):
            hs.read_scene(data[:cut])
    for _ in range(150):                             # stored: flips land in the payload, the zip stays readable
        b = bytearray(data)
        for _ in range(int(rng.integers(1, 5))):
            b[int(rng.integers(0, len(b)))] = int(rng.integers(0, 256))
        try:
            hs.read_scene(bytes(b))
        except hs.FormatError:
            pass


def test_missing_files_refused():
    files = _files()
    for gone in ("scene.json", "house.glb"):
        f = dict(files)
        del f[gone]
        with pytest.raises(hs.FormatError):
            hs.read_scene(_zip(f))


# ---------------------------------------------------------------------------
# scene.json: JSON rules and versions (FORMAT 2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [b"[1, 2]", b"\"text\"", b"null", b"", b"\xff\xfe{}", b"{\"a\": NaN}",
                                 b"{\"a\": Infinity}", b"{\"a\": -Infinity}", b"\xef\xbb\xbf{}"])
def test_scene_json_that_is_no_object_or_no_json_refused(raw):
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(raw=raw))


def test_nan_inside_the_sample_refused():
    raw = _files()["scene.json"].replace(b'"latitude": 53.5', b'"latitude": NaN')
    assert raw != _files()["scene.json"]
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(raw=raw))


def _set(path, value):
    def f(doc):
        d = doc
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = value
    return f


# FOUND: control characters (a line break, a tab) in scene.json's texts are read without a word, and a moment id
# with a tab goes straight into the bake's file names and ids. FORMAT 2: "no control characters (line breaks,
# tabs …) in any text or key"; the checker calls it an ERROR (a reader must refuse it).
@pytest.mark.parametrize("change", [_set(["title"], "Made-up\nhouse"),
                                    _set(["recipe", "moments", 0, "id"], "summer\tmorning"),
                                    _set(["recipe", "seasons", 0, "label"], "Sum\u0007mer")],
                         ids=["title", "moment-id", "season-label"])
def test_control_characters_in_scene_json_refused(change):
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(change))


@pytest.mark.parametrize("v,newer", [("1.10", True), ("1.9", True), ("1.1", True), ("1.0", False), ("01.0", False)])
def test_versions_read(v, newer):
    s = hs.read_scene(_variant(_set(["version"], v)))
    notes = [n for n in s.notes if "newer" in n]
    assert bool(notes) == newer, (v, s.notes)
    if newer:
        assert v.split(".")[1] in notes[0]                      # names the version it read ("1.10", not "1.1")


@pytest.mark.parametrize("v", ["2.0", "10.0", "0.9", "1", "1.", ".1", "1.0.0", "v1.0", " 1.0", "1.0 ", "+1.0",
                               "1.-1", "", None, 1.0, 1, [1, 0], "1e0.0"])
def test_versions_refused(v):
    with pytest.raises(hs.FormatError) as e:
        hs.read_scene(_variant(_set(["version"], v)))
    if v in ("2.0", "10.0"):
        assert "newer" in str(e.value) and v in str(e.value)
    if v == "0.9":
        assert "older" in str(e.value)


# FOUND: a version written in other digits ("١.٠", Arabic-Indic) reads as 1.0. FORMAT 2: "two whole numbers"; the
# schema's pattern is ^[0-9]+\.[0-9]+$ (Python's \d also matches other scripts' digits).
def test_version_in_other_digits_refused():
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(_set(["version"], "\u0661.\u0660")))


def test_version_missing_and_wrong_format_refused():
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(lambda d: d.pop("version")))
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(_set(["format"], "house-bake")))


def test_newer_minor_ignores_unknown_fields_everywhere():
    def change(doc):
        doc["version"] = "1.4"
        doc["future"] = {"x": [1, 2]}
        doc["recipe"]["future"] = 1
        doc["recipe"]["walk_paths"] = [{"id": "w"}]
        doc["recipe"]["moments"][0]["future"] = "x"
        doc["recipe"]["seasons"][0]["future"] = None
        doc["place"]["future"] = 3
        doc["storeys"][0]["future"] = 3

    def glb(g):
        g.json["nodes"][0]["extras"]["hp"]["future"] = {"a": 1}
    s = hs.read_scene(_variant(change, glb))
    assert len(s.surfaces) == 52 and len(s.recipe.moments) == 4


# ---------------------------------------------------------------------------
# closed and open lists (FORMAT 13)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change", [_set(["recipe", "light"], "HALF"), _set(["recipe", "light"], "soft"),
                                    _set(["recipe", "quality", "page_size"], 4096),
                                    _set(["recipe", "quality", "page_size"], 512)],
                         ids=["light", "light-case", "page-4096", "page-512"])
def test_closed_list_values_refused(change):
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(change))


def test_closed_list_bake_value_refused():
    def glb(g):
        g.json["nodes"][0]["extras"]["hp"]["bake"] = "LIGHTMAP"
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(glb_change=glb))


# FOUND: scene.json's "hash" and "uv1" are never looked at: a scene that says "hp-hash/2" or "hp-uv/2" is read as if
# it were hp-hash/1 / hp-uv/1. FORMAT 13: `hash`, `uv1` are closed lists – "a reader that does not know it cannot do
# the right thing" (another value = another major version).
@pytest.mark.parametrize("key,value", [("hash", "hp-hash/2"), ("uv1", "hp-uv/2")])
def test_closed_list_hash_and_uv_names_refused(key, value):
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(_set([key], value)))


# FOUND: a house.glb with extensionsRequired (meshopt, Draco …) is read; its buffers would be read as plain data.
# FORMAT 4: "extensionsRequired MUST be empty"; FORMAT 13: files are ".glb without required extensions" (closed).
def test_glb_with_required_extensions_refused():
    def glb(g):
        g.json["extensionsUsed"] = ["EXT_meshopt_compression"]
        g.json["extensionsRequired"] = ["EXT_meshopt_compression"]
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(glb_change=glb))


def test_open_list_values_read_as_format_13_says():
    def change(doc):
        doc["version"] = "1.1"
        r = doc["recipe"]
        r["quality"]["preset"] = "ULTRA"
        r["quality"]["samples"] = None
        r["seasons"][0]["foliage"] = "snowy"
        r["moments"][0]["lamps"] = "some"
        r["moments"][1]["lamps"] = {"ids": ["lamp:p_living_1"]}
        r["moments"][2]["lamps"] = ["lamp:nope"]
        r["include"]["groups"].append("pool")
        r["videos"] = [
            {"id": "walk-1", "kind": "walk", "camera": "garden-view", "moment": "summer-morning",
             "size": [64, 48], "seconds": 2, "fps": 25},
            {"id": "turn", "kind": "turntable", "camera": "garden-view", "moment": "summer-morning",
             "size": [64, 48], "seconds": 2, "fps": 120},
            {"id": "turn2", "kind": "turntable", "camera": "garden-view", "moment": "summer-morning",
             "size": [64, 48], "seconds": 2, "fps": True}]

    def glb(g):
        g.json["nodes"][_node(g, "garden:ga_terrace")]["extras"]["hp"]["kind"] = "pergola"
        g.json["nodes"][_node(g, "garden:ga_terrace")]["extras"]["hp"]["group"] = "pool"
    s = hs.read_scene(_variant(change, glb))
    r = s.recipe
    assert r.samples == 64                                   # unknown preset, samples null: NORMAL's
    assert r.seasons[0].foliage == "full"
    assert r.moments[0].lamps == "none" and r.moments[1].lamps == "none"
    assert r.moments[2].lamps == ("lamp:nope",)
    assert any("lamp" in n for n in s.notes)                 # an unknown lamp id: a note, not a crash
    assert [v["id"] for v in r.videos] == ["turn", "turn2"]  # the walk is skipped …
    assert any("walk-1" in n for n in s.notes)               # … and said so
    assert r.videos[0]["fps"] == 25 and r.videos[1]["fps"] == 25
    t = s.surfaces["garden:ga_terrace"]
    assert t.kind == "other" and t.raw_kind == "pergola" and t.group == "pool"


# ---------------------------------------------------------------------------
# the house: what the checker calls an ERROR must be refused or at least said (FORMAT 12)
# ---------------------------------------------------------------------------

def _drop_index(g):
    a = g.json["meshes"][0]["primitives"][0]["indices"]
    g.json["accessors"][a]["count"] -= 1


def _index_past_end(g):
    a = g.json["meshes"][0]["primitives"][0]["indices"]
    acc = g.json["accessors"][a]
    bv = g.json["bufferViews"][acc["bufferView"]]
    off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    size = {5121: 1, 5123: 2, 5125: 4}[acc["componentType"]]
    b = bytearray(g.bin)
    b[off:off + size] = b"\xff" * size
    g.bin = bytes(b)


# FOUND (both): a mesh whose index count is not a multiple of 3, or whose index points past the vertices, is read
# (only a "hash does not match" note); world_triangles then raises a raw ValueError (not a FormatError) or hands out
# indices past the end. FORMAT 4.2: "Indices … all below the vertex count, a multiple of 3"; checker: ERROR.
@pytest.mark.parametrize("bad", [_drop_index, _index_past_end], ids=["count-not-3n", "index-past-end"])
def test_broken_indices_refused_or_harmless(bad):
    try:
        s = hs.read_scene(_variant(glb_change=bad))
    except hs.FormatError:
        return
    sid = next(k for k, v in s.surfaces.items() if v.mesh == 0)
    pts, tris = hs.world_triangles(s, sid)
    assert tris.size == 0 or tris.max() < len(pts), "an index past the end was handed out"


def _mirror_map(g):
    g.json["nodes"][_node(g, "floor:r_living")]["scale"] = [-1.0, 1.0, 1.0]


def _storey_null(g):
    g.json["nodes"][_node(g, "floor:r_living")]["extras"]["hp"]["storey"] = None


def _storey_unknown(g):
    g.json["nodes"][_node(g, "floor:r_living")]["extras"]["hp"]["storey"] = "st_attic"


def _sparse(g):
    a = g.json["meshes"][0]["primitives"][0]["attributes"]["POSITION"]
    g.json["accessors"][a]["sparse"] = {"count": 1, "indices": {"bufferView": 0, "componentType": 5125},
                                        "values": {"bufferView": 0}}


def _id_ctrl(g):
    n = g.json["nodes"][_node(g, "garden:ga_terrace")]
    n["extras"]["hp"]["id"] = n["name"] = "garden:ga\nterrace"


def _id_long(g):
    n = g.json["nodes"][_node(g, "garden:ga_terrace")]
    n["extras"]["hp"]["id"] = n["name"] = "garden:" + "t" * 70


# FOUND (all six): each of these is an ERROR of the pinned checker that the reader takes without refusing it and
# without a note. FORMAT 6 / 4: a MAP node "may be turned and moved but not scaled or mirrored"; 4: storey is null
# only for garden / street / houses / park, and names a storey; 4.2: "No sparse accessors"; 4: ids are "letters,
# digits and _ . : -, at most 63 bytes" (a line break in an id lands in bake.json's keys).
@pytest.mark.parametrize("bad", [_mirror_map, _storey_null, _storey_unknown, _sparse, _id_ctrl, _id_long],
                         ids=["mirrored-MAP", "house-storey-null", "storey-unknown", "sparse", "id-control-char",
                              "id-70-bytes"])
def test_checker_errors_in_the_house_refused_or_noted(bad):
    try:
        s = hs.read_scene(_variant(glb_change=bad))
    except hs.FormatError:
        return
    assert s.notes, "read without refusing and without a note"


def test_house_faults_refused():
    def dup(g):
        g.json["nodes"][1]["extras"]["hp"]["id"] = g.json["nodes"][0]["extras"]["hp"]["id"]

    def cycle(g):
        g.json["nodes"][0]["children"] = [0]

    def two_parents(g):
        g.json["nodes"][0]["children"] = [1]

    def lines(g):
        g.json["meshes"][0]["primitives"][0]["mode"] = 1

    def no_mesh(g):
        g.json["nodes"][0]["mesh"] = 999

    def bad_matrix(g):
        g.json["nodes"][0]["matrix"] = [1, 0, 0]

    def no_scene(g):
        g.json["scenes"] = []

    def big_count(g):
        g.json["accessors"][g.json["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]["count"] = 10**9
    for f in (dup, cycle, two_parents, lines, no_mesh, bad_matrix, no_scene, big_count):
        with pytest.raises(hs.FormatError):
            hs.read_scene(_variant(glb_change=f))
    with pytest.raises(hs.FormatError):
        hs.read_scene(_variant(extra={"house.glb": b"glTF" + b"\0" * 40}))


def test_a_mesh_node_without_label_is_a_note():
    def glb(g):
        g.json["nodes"][_node(g, "garden:ga_terrace")].pop("extras")
    s = hs.read_scene(_variant(glb_change=glb))
    assert "garden:ga_terrace" not in s.surfaces and s.notes


# FOUND (all four): an `open_storeys` entry that is no storey (or a text, read letter by letter), and two moments or
# two seasons with one id, are read silently. The checker: ERROR ("recipe.open_storeys: … is not an included storey",
# "moment … is listed twice"; the schema wants a list). The unknown open storey reaches house_bake.steps(), which
# compares that storey's level None with `<=` (a TypeError in the middle of a bake); the second moment of a pair can
# never be written (the writer finds the first by id).
@pytest.mark.parametrize("change", [_set(["recipe", "open_storeys"], ["st_attic"]),
                                    _set(["recipe", "open_storeys"], "st_ground"),
                                    lambda d: d["recipe"]["moments"][1].update(id="summer-morning"),
                                    lambda d: d["recipe"]["seasons"].append(dict(d["recipe"]["seasons"][0]))],
                         ids=["open-storey-unknown", "open-storeys-a-text", "moment-id-twice", "season-id-twice"])
def test_recipe_faults_refused_or_noted(change):
    try:
        s = hs.read_scene(_variant(change))
    except hs.FormatError:
        return
    levels = {st.id for st in s.storeys}
    assert all(st in levels for st in s.recipe.open_storeys) and s.notes, (s.recipe.open_storeys, s.notes)
    assert len({m.id for m in s.recipe.moments}) == len(s.recipe.moments), "two moments with one id"


def test_recipe_faults_refused():
    for change in (lambda d: d["recipe"]["moments"][0].pop("season"),
                   lambda d: d["recipe"]["moments"][0].update(season="spring"),
                   lambda d: d["recipe"]["moments"][0].pop("sun"),
                   lambda d: d["recipe"]["moments"][0]["sun"].update(direction=[1, 2]),
                   lambda d: d["recipe"]["seasons"][0].update(date="2026-02-30"),
                   _set(["recipe", "seasons"], []), _set(["recipe", "moments"], []),
                   _set(["place", "north"], [0, 0]), _set(["place", "north"], [1, 1]),
                   lambda d: d.pop("place"), lambda d: d.pop("recipe"), _set(["storeys"], 3),
                   _set(["recipe", "quality", "samples"], 0), _set(["recipe", "quality", "samples"], -16),
                   _set(["recipe", "quality", "samples"], True)):
        with pytest.raises(hs.FormatError):
            hs.read_scene(_variant(change))


# FOUND: the photo's `falling` numbers are not checked: "nan" (a text) becomes float NaN and goes on to 0109's weather
# (rain = NaN). FORMAT 2: no NaN; the schema wants numbers.
def test_scene_numbers_are_finite():
    s = hs.read_scene(_variant(lambda d: d["recipe"]["photos"][0].update(falling={"rain": "nan", "wind": "inf"})))
    for p in s.recipe.photos:
        assert p["falling"] is None or all(math.isfinite(v) for v in p["falling"].values()), p["falling"]


def test_json_fuzz_never_crashes():
    """Every value of scene.json replaced by values of other types: FormatError or a scene, never another error;
    and a scene that reads gives every moment a sun."""
    doc0 = json.loads(_files()["scene.json"])
    files = _files()

    def paths(d, pre=()):
        if isinstance(d, dict):
            for k, v in d.items():
                yield pre + (k,)
                yield from paths(v, pre + (k,))
        elif isinstance(d, list):
            for j, v in enumerate(d):
                yield pre + (j,)
                yield from paths(v, pre + (j,))
    vals = [None, True, -1, 0, 1e308, "", "x", [], {}, [1, 2, 3], 10**30]
    for p in paths(doc0):
        for v in vals:
            d = copy.deepcopy(doc0)
            x = d
            for k in p[:-1]:
                x = x[k]
            x[p[-1]] = v
            f = dict(files)
            f["scene.json"] = json.dumps(d).encode()
            try:
                s = hs.read_scene(_zip(f, zipfile.ZIP_STORED))
            except hs.FormatError:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for m in s.recipe.moments:
                    hs.moment_sun(s, m)


def test_glb_fuzz_never_crashes(scene):
    """Bytes of house.glb's JSON and binary chunks changed: FormatError or a scene whose triangles can be read."""
    files = _files()
    glb = files["house.glb"]
    jlen = struct.unpack_from("<I", glb, 12)[0]
    rng = np.random.default_rng(11)
    for i in range(160):
        g = bytearray(glb)
        lo, hi = (20, 20 + jlen) if i % 2 else (28 + jlen, len(glb))
        for _ in range(int(rng.integers(1, 4))):
            g[int(rng.integers(lo, hi))] = int(rng.integers(32, 127) if i % 2 else rng.integers(0, 256))
        f = dict(files)
        f["house.glb"] = bytes(g)
        try:
            s = hs.read_scene(_zip(f, zipfile.ZIP_STORED))
        except hs.FormatError:
            continue
        for sid in s.surfaces:
            hs.world_triangles(s, sid)


# ---------------------------------------------------------------------------
# placed nodes: matrix vs translation / rotation / scale, a parent chain, a mirror (FORMAT 4.2, 8.2)
# ---------------------------------------------------------------------------

MIRROR = [-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.2, 0, -0.1, 1]      # column-major: mirrored in x, moved


def _placed(g):
    """The table under a new parent (TRS: turned 90° about +Y, moved to (3.5, 0, 3)); its own node a matrix with a
    mirror in it."""
    t = _node(g, "furniture:f_table:0")
    roots = g.json["scenes"][g.json.get("scene", 0)]["nodes"]
    roots.remove(t)
    node = g.json["nodes"][t]
    for k in ("translation", "rotation", "scale"):
        node.pop(k, None)
    node["matrix"] = list(MIRROR)
    s = math.sqrt(0.5)
    g.json["nodes"].append({"name": "group", "translation": [3.5, 0.0, 3.0], "rotation": [0.0, s, 0.0, s],
                            "children": [t]})
    roots.append(len(g.json["nodes"]) - 1)


def test_parent_chain_and_matrix_give_the_world_place(tmp_path):
    s0 = hs.read_scene(SCENE)
    data = _variant(glb_change=_placed)
    s = hs.read_scene(data)
    a, b = s0.surfaces["furniture:f_table:0"], s.surfaces["furniture:f_table:0"]
    assert b.moved and b.verts == a.verts and b.hash == a.hash
    p0, _ = hs.world_triangles(s0, "furniture:f_table:0")
    p1, _ = hs.world_triangles(s, "furniture:f_table:0")
    g = hglb.Glb.parse(_files()["house.glb"])
    m0 = np.array(g.json["nodes"][_node(g, "furniture:f_table:0")]["matrix"], float).reshape(4, 4).T
    local = (np.c_[p0, np.ones(len(p0))] @ np.linalg.inv(m0).T)[:, :3]   # the mesh's own coordinates
    c = np.stack([-local[:, 0] + 0.2, local[:, 1], local[:, 2] - 0.1], 1)  # the mirror matrix
    want = np.stack([c[:, 2] + 3.5, c[:, 1], -c[:, 0] + 3.0], 1)         # turned 90° about +Y: x' = z, z' = -x
    assert np.allclose(p1, want, atol=1e-5), np.abs(p1 - want).max()
    assert np.allclose(b.box, [*want.min(0), *want.max(0)], atol=1e-5)
    m = np.array(b.matrix).reshape(4, 4).T
    assert abs(np.linalg.det(m[:3, :3]) + 1.0) < 1e-6        # the mirror is in the world matrix


# ---------------------------------------------------------------------------
# the sun (FORMAT 3, 7.5)
# ---------------------------------------------------------------------------

def test_sun_of_format_7_5_example(scene):
    m = scene.moment("summer-morning")
    sun = hs.moment_sun(scene, m)
    assert abs(sun["elevation"] - 29.35) < 0.01
    assert abs(sun["scene_az"] + 14.6) < 0.05               # from Blender +X towards -Y
    assert abs(sun["sun_rotation"] - (90.0 + 14.6)) < 0.5   # 0109: SUN_ROTATION_ZERO_AZ - azimuth
    assert not sun["night"] and sun["mismatch"] < 0.5


@pytest.mark.parametrize("d,el,night", [((0, 1, 0), 90.0, False), ((1, 0, 0), 0.0, False), ((0, -1, 0), -90.0, True),
                                        ((2, 0, 0), 0.0, False), ((0, 3, 4), 36.87, False),
                                        ((0.0, -1e-9, 1.0), 0.0, True)])
def test_sun_overhead_horizon_below(d, el, night):
    e, az = hs.sun_angles(d)
    assert abs(e - el) < 0.01
    assert (e < 0) == night
    if abs(el) < 89:
        x, y, z = d                                           # Blender (x, -z, y): the azimuth of (x, -z)
        assert abs(hs._wrap(az - math.degrees(math.atan2(-z, x)))) < 1e-6


def _format_direction(azimuth, elevation, north):
    """FORMAT 3: east = [-north.z, north.x]; the direction towards the sun in glTF axes."""
    nx, nz = north
    ex, ez = -nz, nx
    a, e = math.radians(azimuth), math.radians(elevation)
    h = math.cos(e)
    return (h * (math.cos(a) * nx + math.sin(a) * ex), math.sin(e), h * (math.cos(a) * nz + math.sin(a) * ez))


def test_sun_mismatch_follows_format_3():
    rng = np.random.default_rng(5)
    for _ in range(200):
        n = rng.uniform(0, 360)
        north = (math.sin(math.radians(n)), -math.cos(math.radians(n)))   # House Planner's [sin n, -cos n]
        az, el = rng.uniform(0, 360), rng.uniform(-80, 80)
        m = hs.Moment(id="m", label="", season="s", time="12:00", utc_offset="+00:00", azimuth=az, elevation=el,
                      direction=_format_direction(az, el, north), clouds=0, low_clouds=0, visibility=1e4,
                      lamps="none")
        assert hs.sun_mismatch(m, north) < 1e-6
        # the compass turns clockwise seen from above: the azimuth mirrored is a different sun
        wrong = hs.Moment(**{**m.__dict__, "azimuth": 360.0 - az})
        if abs(math.sin(math.radians(az))) > 0.2 and abs(el) < 70:
            assert hs.sun_mismatch(wrong, north) > 5.0
        # east is to the right of north seen from above: azimuth 90 is north turned clockwise
    north = (0.0, -1.0)                                       # north = -Z (up on the plan): east = +X
    e = _format_direction(90.0, 0.0, north)
    assert abs(e[0] - 1.0) < 1e-9


def test_weather_sun_reaches_any_sun_also_polar():
    """0109's sun put on House Planner's: within 0.5° for any elevation, azimuth, day and latitude – also beyond
    0109's ±70° latitude and in polar day / night, where that latitude never sees the wanted elevation."""
    rng = np.random.default_rng(9)
    cases = [(el, az, day, lat) for el in (-89.9, -45, -0.5, 0.0, 0.5, 45, 89.9) for az in (-170, 0, 95)
             for day in (1, 80, 172, 355) for lat in (-89, -75, -70, 0, 53.5, 70, 78, 89)]
    cases += [(rng.uniform(-89, 89), rng.uniform(-180, 180), int(rng.integers(1, 367)), rng.uniform(-90, 90))
              for _ in range(400)]
    for el, az, day, lat in cases:
        r = hs.weather_sun(el, az, day, lat, bearing=float(rng.uniform(0, 360)))
        assert 0.0 <= r["hour"] <= 24.0 and abs(r["latitude"]) <= weather.MAX_LATITUDE
        ch = weather.derive(weather.State(**r))
        assert abs(ch["sun_el"] - el) < 0.5, (el, az, day, lat, ch["sun_el"])
        if abs(el) < 89:
            assert abs(hs._wrap(ch["sun_az"] - az)) < 0.5, (el, az, day, lat, ch["sun_az"])


# ---------------------------------------------------------------------------
# encoding and pages (FORMAT 8.3)
# ---------------------------------------------------------------------------

def test_encode_halves_go_away_from_zero():
    # exact halves: scale 255^2, L = (k + 0.5)^2 -> 255 sqrt(L / scale) = k + 0.5 exactly in float64
    scale = 255.0 ** 2
    ks = [0, 1, 2, 3, 10, 100, 253, 254]
    L = np.array([(k + 0.5) ** 2 for k in ks])
    x = 255.0 * np.sqrt(L / scale)
    exact = x == np.array(ks) + 0.5
    assert exact.sum() >= 5                                   # enough of them are exact in float64
    got = hs.encode(L, scale)
    assert list(got[exact]) == [k + 1 for k, e in zip(ks, exact) if e]
    assert list(hs.encode([0.25, 6.25], scale)) == [1, 3]    # 0.5 -> 1, 2.5 -> 3 (not 0 and 2)
    assert list(hs.encode([-1.0, 0.0, scale, 4 * scale, 1e30], scale)) == [0, 0, 255, 255, 255]


def test_encode_matches_the_format_byte_for_byte():
    rng = np.random.default_rng(2)
    L = np.concatenate([rng.uniform(-1, 3, 20000), rng.exponential(0.3, 20000)])
    for scale in (1.0, 0.0371, 2.5e-5, 1234.5):
        Ls = (L * scale).astype(np.float32)
        got = hs.encode(Ls, scale)
        want, x = _my_encode(Ls.astype(np.float64), scale)
        near_half = np.abs(x - np.floor(x) - 0.5) < 1e-9
        assert np.array_equal(got[~near_half], want[~near_half])
        assert got.dtype == np.uint8 and got.shape == L.shape


def test_moment_scale_is_always_a_positive_number():
    for arrays in ([], [np.zeros((4, 3))], [np.full((4, 3), -2.0)], [np.full((4, 3), np.nan)],
                   [np.full((4, 3), np.inf)], [np.array([[1e-300, 0, 0]])], [np.full((2, 2, 3), 1e300)]):
        s = hs.moment_scale(arrays)
        assert isinstance(s, float) and s > 0 and math.isfinite(s), (arrays, s)


def test_layout_rules_hold_for_any_sizes():
    """FORMAT 8.3: rects inside their pages, pages 256 … 2048 and at most page_size, no overlap, 2 texels between."""
    rng = np.random.default_rng(1)
    for trial in range(40):
        page_size = (1024, 2048)[trial % 2]
        n = int(rng.integers(1, 120))
        big = trial % 5 == 0
        sizes = {f"s{i}": (int(rng.integers(1, page_size - 3 if big else 200)),
                           int(rng.integers(1, page_size - 3 if big else 200))) for i in range(n)}
        pages, rects = hs.layout(sizes, page_size)
        assert set(rects) == set(sizes)
        for side in pages:
            assert side[0] == side[1] and side[0] in (256, 512, 1024, 2048) and side[0] <= page_size
        by_page = {}
        for k, (p, x, y) in rects.items():
            w, h = sizes[k]
            pw, ph = pages[p]
            assert 0 <= x and 0 <= y and x + w <= pw and y + h <= ph, (k, rects[k], sizes[k], pages[p])
            by_page.setdefault(p, []).append((x, y, x + w, y + h, k))
        for items in by_page.values():
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    apart = (b[0] >= a[2] + 2 or a[0] >= b[2] + 2 or b[1] >= a[3] + 2 or a[1] >= b[3] + 2)
                    assert apart, (a, b)


def test_page_png_rows_and_chunks():
    rgb = np.zeros((256, 256, 3), np.uint8)
    rgb[0] = 200                       # top row
    rgb[:, 0, 1] = 100
    data = hs.page_png(rgb)
    assert np.array_equal(_png_rows(data), rgb)
    assert hs.png_page_problem(data) is None
    for chunk in (b"gAMA", b"sRGB", b"iCCP", b"cHRM", b"cICP"):
        assert chunk not in data


# ---------------------------------------------------------------------------
# the writer: a whole package against the checker
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def package(tmp_path_factory, winter_snow):
    """The sample (with the table placed by a parent, a matrix and a mirror) baked with made-up light: every moment,
    the open ground floor, winter snow made by house_snow, odd values (NaN, inf, negative) in one VERTEX surface, a
    pattern in floor:r_living whose rows and bytes are checked."""
    tmp = tmp_path_factory.mktemp("indep")
    scene_path = str(tmp / "placed.hpscene")
    with open(scene_path, "wb") as fh:
        fh.write(_variant(glb_change=_placed))
    sc = hs.read_scene(scene_path)
    assert not sc.notes, sc.notes
    layers, snow_glb = winter_snow
    w = _writer(sc)
    w.add_snow("winter", snow_glb)
    rng = np.random.default_rng(8)
    given = {}
    for i, m in enumerate(sc.recipe.moments):
        sun = hs.moment_sun(sc, m)
        level = 0.02 if sun["night"] else 1.0 + i
        maps = _results(sc, level, rng, {ly.id: len(ly.positions) for ly in layers} if m.season == "winter" else None)
        H, W = maps["floor:r_living"].shape[:2]
        pat = np.zeros((H, W, 3), np.float32)
        pat[0] = level                                        # Blender row 0 = the bottom of the map
        pat[:, :, 1] = level * np.linspace(0, 1, W)[None, :]
        maps["floor:r_living"] = pat
        odd = maps["opening:o_g_win1"]
        odd[0] = [np.nan, np.inf, -np.inf]
        odd[1] = [-3.0, 0.0, 1e30]
        open_ = {"st_ground": {k: v * 0.5 for k, v in maps.items()
                               if k in sc.surfaces and sc.surfaces[k].storey == "st_ground"}}
        given[m.id] = (maps, open_)
        w.add_moment(m.id, maps, open_, reference=[level, level, level],
                     exposure=weather.exposure_for(sun["elevation"], m.clouds),
                     sun_light=None if sun["night"] else [2.0, 1.9, 1.8])
    w.add_photo("photo-1", web3d.png(np.full((240, 320, 3), 77, np.uint8)), "png")
    path = str(tmp / "placed.hpbake")
    w.write(path)
    return {"path": path, "scene_path": scene_path, "scene": sc, "writer": w, "given": given, "layers": layers}


def test_package_passes_check_py(package):
    run = subprocess.run([sys.executable, "-B", os.path.join(PIN, "check.py"), package["path"], "--scene",
                          package["scene_path"]], capture_output=True, text=True, timeout=180)
    assert run.returncode == 0 and "ERROR" not in run.stdout, run.stdout + run.stderr
    assert hs.structure_problems(package["path"], package["scene"]) == []


def test_package_json_is_strict(package):
    files = _files(package["path"])
    doc = _strict_json(files["bake.json"])
    assert not _control(doc)
    for name in files:
        assert hs._name_problem(name) is None, name
    assert all(len(p) <= 500 for p in doc["problems"])
    # the odd values (NaN, inf) were named once, in a plain sentence
    assert any("not numbers" in p for p in doc["problems"]), doc["problems"]


def test_package_places_and_rects(package):
    files = _files(package["path"])
    doc = json.loads(files["bake.json"])
    sc = package["scene"]
    table = doc["surfaces"]["furniture:f_table:0"]
    assert np.allclose(table["matrix"], sc.surfaces["furniture:f_table:0"].matrix)
    assert "matrix" not in doc["surfaces"]["floor:r_living"]
    pages = {p["id"]: tuple(p["size"]) for p in doc["pages"]}
    layouts = []
    for m in doc["moments"]:
        lay = {}
        for st, maps in [("", m["maps"])] + list(m["open"].items()):
            rects = []
            for sid, e in maps.items():
                if "page" in e:
                    x, y, w, h = e["rect"]
                    assert [w, h] == list(sc.surfaces[sid].uv1_px)
                    pw, ph = pages[e["page"]]
                    assert x >= 0 and y >= 0 and x + w <= pw and y + h <= ph
                    rects.append((e["page"], x, y, x + w, y + h))
                    lay[(st, sid)] = (x, y)
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    if a[0] == b[0]:
                        assert (b[1] >= a[3] + 2 or a[1] >= b[3] + 2 or b[2] >= a[4] + 2 or a[2] >= b[4] + 2), (a, b)
        layouts.append(lay)
    assert all(lay == layouts[0] for lay in layouts)          # one rect layout for every moment (the Design)


def test_package_bytes_are_the_format_encoding(package):
    files = _files(package["path"])
    doc = json.loads(files["bake.json"])
    for m in doc["moments"]:
        scale = m["encoding"]["scale"]
        assert scale > 0 and math.isfinite(scale)
        maps, open_ = package["given"][m["id"]]
        # a page rectangle: PNG row r = Blender row H-1-r, bytes = FORMAT 8.3's encode
        e = m["maps"]["floor:r_living"]
        page = next(p for p in doc["pages"] if p["id"] == e["page"])
        img = _png_rows(files[page["file"]])
        x, y, w, h = e["rect"]
        got = img[y:y + h, x:x + w]
        want, xs = _my_encode(maps["floor:r_living"].astype(np.float64)[::-1], scale)
        ok = np.abs(xs - np.floor(xs) - 0.5) > 1e-9
        assert np.array_equal(got[ok], want[ok]), m["id"]
        assert got[-1, :, 0].min() > got[0, :, 0].max() or maps["floor:r_living"][0, 0, 0] == 0  # bottom row lit
        # a vertex range: the .glb's vertex order, 3 bytes a vertex; NaN and -inf -> 0, +inf -> the brightest
        for sid in ("opening:o_g_win1", "furniture:f_table:0"):
            v = m["maps"][sid]
            vf = next(f for f in doc["vertex_files"] if f["id"] == v["vertex"])
            raw = np.frombuffer(files[vf["file"]], np.uint8)[3 * v["offset"]:3 * (v["offset"] + v["count"])]
            raw = raw.reshape(-1, 3)
            assert v["count"] == package["scene"].surfaces[sid].verts
            src = maps[sid].astype(np.float64)
            if sid == "opening:o_g_win1":
                assert list(raw[0]) == [0, 255, 0] and list(raw[1]) == [0, 0, 255]
                src = src[2:]
                raw = raw[2:]
            want, xs = _my_encode(src, scale)
            ok = np.abs(xs - np.floor(xs) - 0.5) > 1e-9
            assert np.array_equal(raw[ok], want[ok]), (m["id"], sid)


def test_package_snow_and_sun_light(package):
    files = _files(package["path"])
    doc = json.loads(files["bake.json"])
    sc = package["scene"]
    assert [s["season"] for s in doc["snow"]] == ["winter"]
    ids = {ly.id for ly in package["layers"]}
    for m in doc["moments"]:
        season = sc.moment(m["id"]).season
        assert (ids <= set(m["maps"])) == (season == "winter"), m["id"]
        night = sc.moment(m["id"]).elevation < 0
        assert (m.get("sun_light") is None) == night, m["id"]        # SOFT: by day only
        assert set(m["open"]) == {"st_ground"}
        assert all(sc.surfaces[k].storey == "st_ground" for k in m["open"]["st_ground"])
    assert not ids & set(doc["surfaces"])                     # snow is not a surface of the house


# ---------------------------------------------------------------------------
# the writer: wrong input is left out with a problems line, never a crash or a package the checker refuses
# ---------------------------------------------------------------------------

def test_writer_left_out_cases(scene, tmp_path):
    w = _writer(scene)
    maps = _results(scene, 1.0)
    mapid, vid = "floor:r_living", "furniture:f_table:0"
    W, H = scene.surfaces[mapid].uv1_px
    maps[mapid] = np.ones((scene.surfaces[mapid].verts, 3))        # a MAP surface given vertex values
    maps[vid] = np.ones((H, W, 3))                                 # a VERTEX surface given a map
    maps["wall:w_g_front:a"] = np.ones((W, H, 3))                  # rows and columns swapped
    maps["glass:o_g_win1"] = np.ones((4, 3))                       # bake NO
    maps["wall:nope"] = np.ones((4, 3))                            # not in the house
    maps["snow:roof:st_first:0"] = np.ones((20, 3))                # snow with no snow file
    maps["floor:r_kitchen"] = np.ones((54, 107, 3), dtype=object)  # not numbers
    maps["floor:r_bed"] = None
    w.add_moment("summer-morning", maps, {"st_attic": {}, "st_first": {}}, reference=[1, 1, 1], exposure=0.0,
                 sun_light=[1, 2])
    w.add_moment("no-such-moment", maps, reference=[1, 1, 1], exposure=0.0)
    w.add_moment("summer-evening", _results(scene, 1.0), reference=[1, 1, 1], exposure=0.0)
    w.add_moment("summer-evening", _results(scene, 3.0), reference=[3, 3, 3], exposure=0.0)   # replaces
    doc = w.bake_json()
    assert [m["id"] for m in doc["moments"]] == ["summer-morning", "summer-evening"]
    mm = doc["moments"][0]["maps"]
    for sid in (mapid, vid, "wall:w_g_front:a", "glass:o_g_win1", "wall:nope", "snow:roof:st_first:0",
                "floor:r_kitchen", "floor:r_bed"):
        assert sid not in mm, sid
    assert doc["moments"][1]["encoding"]["reference"] == [3.0, 3.0, 3.0]
    assert len(w.problems) >= 8 and not _control(w.problems)
    _, errors, _ = _check(w, tmp_path)
    assert errors == [], errors


@pytest.mark.parametrize("val", [0.0, -5.0, np.nan, np.inf, 1e30, 1e-300], ids=["zero", "neg", "nan", "inf", "huge",
                                                                                 "tiny"])
def test_writer_odd_light_values(scene, tmp_path, val):
    w = _writer(scene)
    w.add_moment("summer-morning", _results(scene, val), reference=[val] * 3, exposure=val, sun_light=[val] * 3)
    doc = _strict_json(w.files()["bake.json"])
    m = doc["moments"][0]
    assert m["encoding"]["scale"] > 0 and math.isfinite(m["encoding"]["scale"])
    assert all(math.isfinite(v) and v >= 0 for v in m["encoding"]["reference"])
    assert math.isfinite(m["encoding"]["exposure"])
    assert m["sun_light"] is None or all(math.isfinite(v) and v >= 0 for v in m["sun_light"])
    _, errors, _ = _check(w, tmp_path)
    assert errors == [], errors


def test_writer_snow_rules(scene, tmp_path, winter_snow):
    layers, glb = winter_snow
    counts = {ly.id: len(ly.positions) for ly in layers}
    w = _writer(scene)
    w.add_snow("spring", glb)                             # not in the recipe: left out
    w.add_snow("winter", b"not a glb")                    # unreadable: left out
    w.add_snow("winter", glb)
    m = _results(scene, 1.0, snow=counts)
    w.add_moment("summer-morning", m, reference=[1, 1, 1], exposure=0.0)   # winter snow in summer: left out
    w.add_moment("winter-noon", m, reference=[1, 1, 1], exposure=0.0)
    doc = w.bake_json()
    assert any("spring" in p for p in w.problems)
    noon = next(x for x in doc["moments"] if x["id"] == "winter-noon")
    assert set(counts) <= set(noon["maps"])
    _, errors, _ = _check(w, tmp_path)
    assert errors == [], errors


# FOUND: a second snow file for a season replaces the first, but light already given for the first file's layers stays
# in the moments: bake.json then lights ids no snow file has, with the old vertex counts. Checker: ERROR ("not in
# bake.json's surfaces or a snow file", "16 vertex values for 5280 vertices"). FORMAT 8.6 / 8.4: a snow id's result
# has that layer's vertex count.
def test_writer_second_snow_file_for_a_season(scene, tmp_path, winter_snow):
    layers, glb = winter_snow
    sample_snow = _files(BAKE)["snow/winter.glb"]            # the format's own: other layers, other counts
    w = _writer(scene)
    w.add_snow("winter", sample_snow)
    small = {k: v["verts"] for k, v in hs._snow_layers(sample_snow).items()}
    w.add_moment("winter-noon", _results(scene, 1.0, snow=small), reference=[1, 1, 1], exposure=0.0)
    w.add_snow("winter", glb)                                # made again: replaces it
    _, errors, _ = _check(w, tmp_path)
    assert errors == [], errors


def test_writer_live_writes_no_light(scene, tmp_path, winter_snow):
    sl = copy.copy(scene)
    sl.recipe = copy.copy(scene.recipe)
    sl.recipe.light = "LIVE"
    w = hs.BakeWriter(sl, light="LIVE", samples=4)
    w.add_snow("winter", winter_snow[1])
    w.add_moment("summer-morning", _results(scene, 1.0), reference=[1, 1, 1], exposure=0.0, sun_light=[1, 1, 1])
    doc = w.bake_json()
    assert doc["pages"] == [] and doc["vertex_files"] == []
    assert all(not m["maps"] and not m.get("open") for m in doc["moments"])
    assert not any(n.startswith("light/") for n in w.files())
    with pytest.raises(ValueError):
        hs.BakeWriter(scene, light="ALL", samples=4)          # FORMAT 8.1: the bake's light is the recipe's


# FOUND: a photo whose bytes start like a PNG but are cut off makes add_photo raise struct.error (from
# web3d.image_size) instead of leaving it out with a problems line, as the writer does for every other bad input.
def test_writer_bad_photos_left_out(scene, tmp_path):
    w = _writer(scene)
    for data, ext in ((b"", "png"), (b"\x89PNG\r\n\x1a\n" + b"\0" * 4, "png"), (b"\xff\xd8" + b"\0" * 10, "jpg"),
                      (web3d.png(np.zeros((4, 4, 3), np.uint8)), "gif"),
                      (web3d.png(np.zeros((4, 4, 3), np.uint8)), "jpg")):
        w.add_photo("photo-1", data, ext)
    w.add_photo("photo-9", web3d.png(np.zeros((4, 4, 3), np.uint8)), "png")      # not in the recipe
    assert w.bake_json()["photos"] == []
    w.add_photo("photo-1", web3d.png(np.zeros((100, 100, 3), np.uint8)), "png", size=(320, 240))   # wrong size: said
    assert any("100 x 100" in p for p in w.problems)
    _, errors, _ = _check(w, tmp_path)
    assert errors == [], errors


# FOUND: text the caller passes goes into bake.json as it is: app_version "0.2.90\nbeta" puts a line break in
# generator.version. FORMAT 2: no control characters in any text; checker: ERROR. (problems lines ARE cleaned.)
def test_writer_never_writes_control_characters(scene, tmp_path):
    w = hs.BakeWriter(scene, light="SOFT", samples=4, app_version="0.2.90\nbeta", created="2026-11-13T12:00:00Z")
    w.problem("line one\nline two\ttab\x00")
    w.add_moment("summer-morning", _results(scene, 1.0), reference=[1, 1, 1], exposure=0.0)
    doc = _strict_json(w.files()["bake.json"])
    assert not _control(doc), doc["generator"]


def test_structure_problems_never_raises(package):
    files = _files(package["path"])
    doc0 = json.loads(files["bake.json"])
    rng = np.random.default_rng(4)
    vals = [None, 1, -1, "x", [], {}, [1, 2], {"page": "zz", "rect": [0, 0, 1]}, 1e308]
    keys = ["pages", "vertex_files", "moments", "snow", "photos", "surfaces", "light"]
    for _ in range(60):
        doc = copy.deepcopy(doc0)
        k = keys[int(rng.integers(0, len(keys)))]
        if isinstance(doc[k], list) and doc[k]:
            item = doc[k][int(rng.integers(0, len(doc[k])))]
            if isinstance(item, dict):
                f = list(item)[int(rng.integers(0, len(item)))]
                item[f] = vals[int(rng.integers(0, len(vals)))]
        else:
            doc[k] = vals[int(rng.integers(0, len(vals)))]
        f = dict(files)
        f["bake.json"] = json.dumps(doc).encode()
        out = hs.structure_problems(_zip(f, zipfile.ZIP_STORED), package["scene"])
        assert isinstance(out, list)
    f = dict(files)
    f["bake.json"] = json.dumps({**doc0, "version": "2.0"}).encode()
    assert any("2.0" in p for p in hs.structure_problems(_zip(f)))


# ---------------------------------------------------------------------------
# snow layers (FORMAT 8.6)
# ---------------------------------------------------------------------------

def _quad(x0, x1, z0, z1, y, up=True):
    pts = np.array([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], float)
    tris = np.array([[0, 2, 1], [0, 3, 2]]) if up else np.array([[0, 1, 2], [0, 2, 3]])
    return pts, tris


def _src(sid, pts, tris, storey=None, group="garden"):
    return {"id": sid, "storey": storey, "group": group, "points": pts, "tris": tris}


def _merge(*pairs):
    P, T, n = [], [], 0
    for p, t in pairs:
        P.append(p)
        T.append(t + n)
        n += len(p)
    return np.concatenate(P), np.concatenate(T)


def test_snow_only_up_and_under_the_open_sky():
    ground = _quad(0, 10, 0, 10, 0.0)                       # normal +Y (counter-clockwise seen from above)
    roof = _quad(2, 5, 2, 5, 3.0)                           # 3 m above part of the ground
    canopy = _quad(6, 9, 6, 9, 30.0)                        # 30 m above: beyond SKY_DISTANCE, keeps nothing off
    ceiling = _quad(0, 2, 0, 2, 1.0, up=False)              # faces down
    a = math.radians(70)                                    # a 70° slope: steeper than any snow
    steep = (np.array([[0, 0, 12], [2, 0, 12], [2, 2 * math.tan(a), 14], [0, 2 * math.tan(a), 14]]),
             np.array([[0, 2, 1], [0, 3, 2]]))
    blockers = _merge(ground, roof, canopy, ceiling, steep)
    cover = 0.6
    layers = house_snow.build_layers([_src("ground:plot", *ground), _src("roof:x:0", *roof, "st_x", "house"),
                                      _src("ceiling:c", *ceiling, "st_x", "house"), _src("roof:x:1", *steep)],
                                     cover, blockers)
    by = {ly.on: ly for ly in layers}
    assert set(by) == {"ground:plot", "roof:x:0"}           # not the ceiling, not the steep face
    g = by["ground:plot"]
    top = g.positions[g.indices[:3 * g.top]].reshape(-1, 3)
    # the top of the ground's layer: nowhere under the roof, but under the 30 m canopy
    centre = top.reshape(-1, 3, 3).mean(1)                 # a piece is kept by its centre (pieces ~0.5 m)
    cx, cz = centre[:, 0], centre[:, 2]
    assert not np.any((cx > 2.0) & (cx < 5.0) & (cz > 2.0) & (cz < 5.0))
    assert np.any((cx > 6.5) & (cx < 8.5) & (cz > 6.5) & (cz < 8.5))
    assert not np.any((cx < 2.0) & (cz < 2.0))             # under the ceiling at 1 m
    assert np.allclose(top[:, 1], house_snow.THICKNESS_PER_COVER * cover, atol=1e-4)
    for ly in layers:
        assert ly.id == "snow:" + ly.on and len(ly.id.encode()) <= 63
        assert ly.positions.dtype == np.float32 and ly.normals.dtype == np.float32
        assert np.isfinite(ly.positions).all() and np.allclose(np.linalg.norm(ly.normals, axis=1), 1, atol=1e-3)
        idx = ly.indices.astype(np.int64)
        assert len(idx) % 3 == 0 and idx.max() < len(ly.positions)
        assert np.array_equal(np.unique(idx), np.arange(len(ly.positions)))    # every vertex used (FORMAT 4.2)
        tri = ly.positions[idx[:3 * ly.top].reshape(-1, 3)].astype(np.float64)
        edges = np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2)
        assert edges.max() <= house_snow.PIECE * 1.01                         # ~0.5 m pieces
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        assert (n[:, 1] > 0).all()                                            # the top faces up
        assert ly.hash == house_hash.hash_primitives([{"positions": ly.positions, "uv1": None,
                                                       "indices": ly.indices}])


def test_snow_ids_never_longer_than_63_bytes_and_cover_zero():
    ground = _quad(0, 1, 0, 1, 0.0)
    long_id = "ground:" + "p" * 56                          # 63 bytes: "snow:" + it would be 68
    layers = house_snow.build_layers([_src(long_id, *ground), _src("ground:ok", *ground)], 1.0, ground)
    assert all(len(ly.id.encode()) <= 63 for ly in layers) and [ly.on for ly in layers] == ["ground:ok"]
    assert house_snow.build_layers([_src("ground:ok", *ground)], 0.0, ground) == []
    assert house_snow.build_layers([_src("ground:ok", *ground)], -1.0, ground) == []


def _snow_glb(nodes):
    """A tiny house.glb: nodes = [(id, kind, points, tris, node extras such as scale / translation)]."""
    blob, views, accs, meshes, gnodes = bytearray(), [], [], [], []
    for sid, kind, pts, tris, place in nodes:
        for arr, typ, comp in ((np.asarray(pts, "<f4"), "VEC3", 5126), (np.asarray(tris, "<u4").ravel(), "SCALAR",
                                                                          5125)):
            while len(blob) % 4:
                blob.append(0)
            views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": arr.nbytes})
            blob.extend(arr.tobytes())
            acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(arr)), "type": typ}
            if typ == "VEC3":
                acc["min"] = [float(v) for v in arr.min(0)]
                acc["max"] = [float(v) for v in arr.max(0)]
            accs.append(acc)
        meshes.append({"primitives": [{"attributes": {"POSITION": len(accs) - 2}, "indices": len(accs) - 1}]})
        gnodes.append({"name": sid, "mesh": len(meshes) - 1, "extras": {"hp": {
            "id": sid, "kind": kind, "storey": None, "group": "garden", "bake": "VERTEX"}}, **place})
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(gnodes)))}],
           "nodes": gnodes, "meshes": meshes, "accessors": accs, "bufferViews": views,
           "buffers": [{"byteLength": len(blob)}]}
    return hglb.pack(doc, bytes(blob))


def test_snow_on_a_mirrored_and_turned_node():
    """A mirrored node turns its triangles round (glTF): the layer still lies on top, in world coordinates."""
    pts, tris = _quad(0, 2, 0, 2, 0.0)
    glb = _snow_glb([("ground:a", "ground", pts, tris, {"scale": [-1, 1, 1], "translation": [10, 1, 0]}),
                     ("ground:b", "ground", pts, tris, {"rotation": [0, math.sqrt(0.5), 0, math.sqrt(0.5)],
                                                        "translation": [0, 2, 20]}),
                     ("foliage:t", "foliage", *_quad(0, 2, 18, 20, 5.0), {})])
    src, blockers = house_snow.sources_from_glb(glb, "full")
    by = {ly.on: ly for ly in house_snow.build_layers(src, 1.0, blockers)}
    assert set(by) == {"ground:a", "foliage:t"}
    a = by["ground:a"]
    top = a.positions[a.indices[:3 * a.top]]
    assert np.allclose(top[:, 1], 1.0 + house_snow.THICKNESS_PER_COVER, atol=1e-4)    # above y = 1, not below
    assert top[:, 0].min() > 7.9 and top[:, 0].max() < 10.1
    # the turned ground ((0..2, 0..2) turned 90° about +Y: x 0..2, z 18..20, y 2) lies under the leaves at y 5: no
    # snow there in full foliage, snow when the tree is bare
    assert "ground:b" not in by
    src, blockers = house_snow.sources_from_glb(glb, "bare")
    by = {ly.on: ly for ly in house_snow.build_layers(src, 1.0, blockers)}
    assert "foliage:t" not in by
    b = by["ground:b"]
    top = b.positions[b.indices[:3 * b.top]]
    assert top[:, 2].min() > 17.9 and top[:, 2].max() < 20.1 and top[:, 0].min() > -0.1 and top[:, 0].max() < 2.1
    assert np.allclose(top[:, 1], 2.0 + house_snow.THICKNESS_PER_COVER, atol=1e-4)


def test_snow_glb_has_no_required_extensions_and_float32(winter_snow):
    layers, glb = winter_snow
    g = hglb.Glb.parse(glb)
    assert not g.json.get("extensionsRequired") and not g.json.get("extensionsUsed")
    ids = [n["extras"]["hp"]["id"] for n in g.json["nodes"]]
    assert ids == [ly.id for ly in layers] and len(set(ids)) == len(ids)
    for n in g.json["nodes"]:
        hp = n["extras"]["hp"]
        assert hp["kind"] == "snow" and hp["bake"] == "VERTEX" and hp["id"] == "snow:" + hp["on"] == n["name"]
        assert "matrix" not in n and "translation" not in n
        for p in g.json["meshes"][n["mesh"]]["primitives"]:
            for key in ("POSITION", "NORMAL"):
                acc = g.json["accessors"][p["attributes"][key]]
                assert acc["componentType"] == 5126 and not acc.get("normalized")


# ---------------------------------------------------------------------------
# Blender (two short bakes and one cancelled one)
# ---------------------------------------------------------------------------

def _bpy():
    return pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def blender():
    bpy = _bpy()
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def _fresh(bpy, tmp, data: bytes, name="house.hpscene"):
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    src = os.path.join(str(tmp), name)
    with open(src, "wb") as fh:
        fh.write(data)
    return bpy.context.scene, src


def _project(bpy, scene):
    from fresing_render.blender import weather as bw
    return (bw.state(scene), scene.fresing.weather.enabled, scene.fresing.background, scene.render.engine,
            scene.render.resolution_x, scene.frame_current, scene.camera,
            len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images),
            len(bpy.data.scenes), len(bpy.data.worlds), len(bpy.data.cameras), len(bpy.data.collections),
            sorted((ob.name, ob.hide_render, ob.hide_viewport, ob.visible_shadow) for ob in scene.objects))


def test_blender_cancel_leaves_the_project_as_it_was(blender, tmp_path):
    from fresing_render.blender import house_bake, house_import
    scene, src = _fresh(blender, tmp_path, open(SCENE, "rb").read())
    house_import.import_scene(scene, src)
    before = _project(blender, scene)
    files_before = sorted(os.listdir(tmp_path))
    out = str(tmp_path / "cancelled.hpbake")
    gen = house_bake.HouseBake(scene, out, moments=["summer-morning"], samples=1, photos=False).steps()
    seen = []
    for f in gen:
        seen.append(f)
        if len(seen) >= 6:
            break
    gen.close()                                              # Cancel
    assert len(seen) >= 6, seen
    assert not os.path.exists(out)
    assert sorted(os.listdir(tmp_path)) == files_before      # no half-written or temporary file
    assert _project(blender, scene) == before


@pytest.fixture(scope="module")
def live_bake(blender, tmp_path_factory):
    """LIVE (nothing baked) with a winter moment (snow) and a video of a kind 1.0 does not know."""
    from fresing_render.blender import house_bake, house_import
    tmp = tmp_path_factory.mktemp("live")

    def change(doc):
        doc["version"] = "1.2"
        doc["recipe"]["light"] = "LIVE"
        doc["recipe"]["videos"] = [{"id": "walk-1", "kind": "walk", "camera": "garden-view",
                                    "moment": "winter-noon", "size": [64, 48], "seconds": 1, "fps": 25}]
    data = _variant(change)
    scene, src = _fresh(blender, tmp, data)
    house_import.import_scene(scene, src)
    path = str(tmp / "live.hpbake")
    res = house_bake.HouseBake(scene, path, moments=["winter-noon"], samples=1, photos=False).run()
    return {"path": path, "src": src, "result": res}


def test_blender_live_package_holds_no_light(live_bake):
    rep = hcheck.check(live_bake["path"], scene=live_bake["src"])
    assert rep.errors == [], rep.errors
    doc = json.loads(_files(live_bake["path"])["bake.json"])
    assert doc["light"] == "LIVE" and doc["pages"] == [] and doc["vertex_files"] == []
    assert all(not m["maps"] and not m.get("open") for m in doc["moments"])
    assert doc["videos"] == []                                # the walk is skipped (FORMAT 13)


# FOUND: with light LIVE the bake writes no snow layers (house_bake.steps skips the snow when the light is LIVE).
# FORMAT 7.1: LIVE bakes "nothing (only snow, photos, videos)" – the season's snow layers (8.6) belong in the package.
def test_blender_live_still_brings_the_snow(live_bake):
    doc = json.loads(_files(live_bake["path"])["bake.json"])
    assert [s["season"] for s in doc["snow"]] == ["winter"], doc["snow"]


def test_blender_one_moment_after_importing_twice(blender, tmp_path):
    """Import twice (the second replaces the first), then bake a list of one moment – the night, lamps on, snow."""
    from fresing_render.blender import house_bake, house_import
    scene, src = _fresh(blender, tmp_path, open(SCENE, "rb").read())
    house_import.import_scene(scene, src)
    n1 = len(blender.data.objects)
    house_import.import_scene(scene, src)
    assert len(blender.data.objects) == n1
    path = str(tmp_path / "night.hpbake")
    res = house_bake.HouseBake(scene, path, moments=["winter-night"], samples=1, photos=False).run()
    assert res["moments"] == 1
    rep = hcheck.check(path, scene=src)
    assert rep.errors == [], rep.errors
    doc = json.loads(_files(path)["bake.json"])
    assert [m["id"] for m in doc["moments"]] == ["winter-night"]
    m = doc["moments"][0]
    assert m.get("sun_light") is None and m["encoding"]["scale"] > 0
    assert any(k.startswith("snow:") for k in m["maps"])
    assert "lamp:p_living_1" in m["maps"]                     # the lit fitting has its own light
    assert not _control(doc) and all(len(p) <= 500 for p in doc["problems"])
