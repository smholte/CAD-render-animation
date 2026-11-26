"""Task 0354: the Fresing assets pack's pack.json (core/assets_pack.py) and the registry (core/assets_registry.py).

Plain Python, no Blender: every rule of study 0344 1.5 (missing, damaged, not ours, newer format, outside the app
window, a bad row, a path outside the pack, a newer contract per kind, size / sha256 in ``verify``), the ids (every
code id of every kind resolves; a pack-only id without a twin or fallback is refused), the resolve order, read-once.
"""

import builtins
import hashlib
import json
import os

import pytest

from fresing_render.core import assets_pack as ap
from fresing_render.core import assets_registry as reg

APP = "0.2.300"


def _file(root, rel, data=b"x"):
    full = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _row(full_id, file, **extra):
    kind = full_id.split(":")[0]
    row = {"id": full_id, "kind": kind, "file": file}
    if kind in ap.BLEND_KINDS:
        row["datablock"] = [ap.BLEND_KINDS[kind][0], "FRP " + full_id.split(":")[1]]
    row.update(extra)
    return row


def make_pack(root, rows=None, files=None, **head):
    """A small pack.json with real (tiny) files; ``rows`` default: one good row per kind with a contract."""
    if rows is None:
        rows = [_row("material:paint_satin", "materials/paint_satin.blend", picture="pictures/m.jpg", set="paints",
                     cost=1.1),
                _row("finish:knurl_diamond", "finishes/knurl_diamond.blend"),
                _row("light:PRODUCT", "lights/PRODUCT.exr"),
                _row("hdri:test_hall", "hdri/test_hall_2k.exr", fallback="light:OVERCAST",
                     textures=["hdri/test_hall_1k.exr"]),
                _row("environment:FACTORY", "environments/FACTORY.blend", textures=["textures/2k/floor.jpg"]),
                _row("prop:PALLET", "props/PALLET.blend")]
    if files is None:
        files = {}
        for r in rows:
            for rel in [r.get("file"), r.get("picture"), *r.get("textures", [])]:
                if isinstance(rel, str) and ap.path_ok(rel):
                    files[rel] = _file(root, rel, rel.encode() * 3)
        files["LICENSE-ASSETS.txt"] = _file(root, "LICENSE-ASSETS.txt", b"test")
    data = {"format": "fresing-assets", "format_version": 1, "id": "fresing-assets-test", "title": "Test",
            "version": "1.0.0", "app_min": "0.2.200", "app_max": "", "contract": 1,
            "licence": "LICENSE-ASSETS.txt", "licence_id": "test",
            "qualities": {"draft": "1k", "normal": "2k", "final": "4k"},
            "sets": {"paints": {"title": "Paints", "approved": "2026-11-25", "since": "1.0.0", "budget_mb": 40}},
            "files": files, "assets": rows}
    data.update(head)
    with open(os.path.join(root, "pack.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv(ap.ENV, raising=False)
    reg.forget()
    yield
    reg.forget()


# ---------------------------------------------------------------------------
# 1.5: a broken or missing pack never stops the app
# ---------------------------------------------------------------------------

def test_no_pack_json_is_no_pack_and_nothing_said(tmp_path):
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "none" and f.note == ""
    f = ap.read(str(tmp_path / "missing"), APP)
    assert f.pack is None and f.note == ""


@pytest.mark.parametrize("text", ["{", "", "[1,", '{"format": "fresing-assets", "x": NaN}',
                                  '{"format": "fresing-assets", "x": Infinity}', "\x00\x01", "\ufeff{"])
def test_damaged_pack_json_is_no_pack_and_one_note(tmp_path, text):
    (tmp_path / "pack.json").write_text(text, encoding="utf-8")
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "damaged" and f.note == ap.NOTE_DAMAGED and f.detail


def test_not_utf8_and_too_large_are_damaged(tmp_path):
    (tmp_path / "pack.json").write_bytes(b'{"id": "\xff\xfe"}')
    assert ap.read(str(tmp_path), APP).state == "damaged"
    (tmp_path / "pack.json").write_bytes(b" " * (ap.MAX_PACK_JSON + 1))
    f = ap.read(str(tmp_path), APP)
    assert f.state == "damaged" and "larger" in f.detail


def test_pack_json_that_is_a_folder_is_not_a_crash(tmp_path):
    (tmp_path / "pack.json").mkdir()
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.note == ""            # not a file: nothing there


@pytest.mark.parametrize("data", [[], "text", 3, {"format": "other"}, {"x": 1}, {"format": None}])
def test_not_ours(tmp_path, data):
    (tmp_path / "pack.json").write_text(json.dumps(data), encoding="utf-8")
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "not_ours" and f.note == ap.NOTE_NOT_OURS


@pytest.mark.parametrize("head", [dict(format_version="1"), dict(format_version=None), dict(format_version=0),
                                  dict(format_version=True), dict(version=""), dict(version="new"),
                                  dict(app_min="later"), dict(app_max="soon"), dict(id=7),
                                  dict(qualities={"draft": "8k", "normal": "2k", "final": "4k"}),
                                  dict(qualities={"normal": "2k"}), dict(contract="1"), dict(contract={"material": "x"}),
                                  dict(sets=[1]), dict(sets={"a": {"budget_mb": "big"}}), dict(files=[]),
                                  dict(files={"../x.blend": {"bytes": 1, "sha256": "0" * 64}}),
                                  dict(files={"a.blend": {"bytes": -1, "sha256": "0" * 64}}),
                                  dict(files={"a.blend": {"bytes": 1, "sha256": "short"}}), dict(assets={}),
                                  dict(licence="../LICENCE.txt"), dict(title="a\nb")])
def test_damaged_head_is_no_pack_and_one_note(tmp_path, head):
    make_pack(str(tmp_path), **head)
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "damaged" and f.note == ap.NOTE_DAMAGED, f.detail


def test_newer_format_is_no_pack_and_says_update(tmp_path):
    make_pack(str(tmp_path), format_version=ap.FORMAT_VERSION + 1)
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "newer" and f.note == ap.NOTE_NEWER


def test_app_outside_the_window(tmp_path):
    make_pack(str(tmp_path), app_min="0.3.0")
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "app_old" and "0.3.0 or newer" in f.note and "1.0.0" in f.note
    make_pack(str(tmp_path), app_min="0.2.100", app_max="0.2.250")
    f = ap.read(str(tmp_path), APP)
    assert f.pack is None and f.state == "app_new" and "up to 0.2.250" in f.note
    make_pack(str(tmp_path), app_min="0.2.300", app_max="0.2.300")      # the edges are inside
    assert ap.read(str(tmp_path), APP).state == "ok"
    assert ap.read(str(tmp_path), "0.2.300-rc.1").state == "app_old"   # a pre-release sorts before its release


def test_a_good_pack_reads_with_no_note(tmp_path):
    make_pack(str(tmp_path))
    f = ap.read(str(tmp_path), APP)
    assert f.state == "ok" and f.note == "" and f.pack.left_out == []
    p = f.pack
    assert set(p.assets) == {"material:paint_satin", "finish:knurl_diamond", "light:PRODUCT", "hdri:test_hall",
                             "environment:FACTORY", "prop:PALLET"}
    a = p.assets["material:paint_satin"]
    assert a.kind == "material" and a.code_id == "paint_satin" and a.datablock == ("node_groups", "FRP paint_satin")
    assert a.sha256 == p.files[a.file][1] and a.bytes == p.files[a.file][0] and a.cost == 1.1 and a.set == "paints"
    assert p.assets["light:PRODUCT"].datablock == () and p.qualities == ap.DEFAULT_QUALITIES
    assert p.path(a.file) == os.path.join(str(tmp_path), "materials", "paint_satin.blend")
    assert p.contracts["material"] == 1 and "1.0.0" in ap.describe(f)


def test_bom_is_read(tmp_path):
    make_pack(str(tmp_path))
    raw = (tmp_path / "pack.json").read_bytes()
    (tmp_path / "pack.json").write_bytes(b"\xef\xbb\xbf" + raw)
    assert ap.read(str(tmp_path), APP).state == "ok"


BAD_ROWS = [
    ("not a table", "row"),
    (_row("material:../evil", "materials/x.blend"), "bad id"),
    (_row("Material:paint_satin", "materials/x.blend"), "bad id"),
    (_row("material:", "materials/x.blend"), "bad id"),
    ({"id": 5, "file": "materials/x.blend"}, "bad id"),
    (_row("material:paint_gloss", "../outside.blend"), "outside the pack"),
    (_row("material:paint_gloss", "/etc/passwd"), "outside the pack"),
    (_row("material:paint_gloss", "C:/Windows/x.blend"), "outside the pack"),
    (_row("material:paint_gloss", "materials\\x.blend"), "outside the pack"),
    (_row("material:paint_gloss", "materials/./x.blend"), "outside the pack"),
    (_row("material:paint_gloss", "materials/.hidden.blend"), "outside the pack"),
    (_row("material:paint_gloss", "materials/unlisted.blend"), "not in the pack's 'files'"),
    (_row("material:paint_gloss", "materials/x.blend", kind="finish"), "differs"),
    (_row("material:paint_gloss", "materials/x.blend", datablock=["objects", "x"]), "datablock"),
    (_row("material:paint_gloss", "materials/x.blend", datablock="FRP x"), "datablock"),
    (_row("material:paint_gloss", "lights/x.exr"), "must be a .blend"),
    (_row("light:SUN", "materials/x.blend"), "must be a"),
    (_row("light:SUN", "lights/x.exr", datablock=["images", "x"]), "no datablock"),
    (_row("material:paint_gloss", "materials/x.blend", contract="2"), "whole number"),
    (_row("material:paint_gloss", "materials/x.blend", picture="../p.jpg"), "picture"),
    (_row("material:paint_gloss", "materials/x.blend", picture="materials/x.blend"), "picture"),
    (_row("material:paint_gloss", "materials/x.blend", textures=["../t.png"]), "textures"),
    (_row("material:paint_gloss", "materials/x.blend", textures="lights/x.exr"), "textures"),
    (_row("material:paint_gloss", "materials/x.blend", fallback="paint_satin"), "fallback"),
    (_row("material:paint_gloss", "materials/x.blend", cost="slow"), "cost"),
    (_row("material:paint_gloss", "materials/x.blend", cost=1.31), "without the owner's OK"),
    (_row("material:paint_gloss", "materials/x.blend", set="nope"), "set"),
    (_row("material:paint_gloss", "materials/x.blend", since=3), "version"),
    (_row("future_kind:x", "materials/x.blend"), "not known"),
    (_row("weather:STORM", "materials/x.blend"), "newer than this app's 0"),   # weather stays code
]


@pytest.mark.parametrize("row,why", BAD_ROWS, ids=[str(i) for i in range(len(BAD_ROWS))])
def test_a_bad_row_is_left_out_with_one_note(tmp_path, row, why):
    files = {"materials/x.blend": _file(str(tmp_path), "materials/x.blend"),
             "lights/x.exr": _file(str(tmp_path), "lights/x.exr")}
    good = _row("material:paint_satin", "materials/x.blend")
    make_pack(str(tmp_path), rows=[good, row], files=files)
    f = ap.read(str(tmp_path), APP)
    assert f.state == "ok" and list(f.pack.assets) == ["material:paint_satin"]
    assert len(f.pack.left_out) == 1 and why in f.pack.left_out[0][1], f.pack.left_out
    assert f.note == ap.rows_note(1) and "1 item of the Fresing assets pack is left out" in f.note


def test_slower_look_with_the_owners_ok_is_kept(tmp_path):
    files = {"materials/x.blend": _file(str(tmp_path), "materials/x.blend")}
    make_pack(str(tmp_path), files=files, rows=[_row("material:paint_satin", "materials/x.blend", cost=1.6,
                                                     approved_slower="2026-12-01 pick page")])
    assert "material:paint_satin" in ap.read(str(tmp_path), APP).pack.assets


def test_a_duplicate_id_keeps_the_first(tmp_path):
    files = {"materials/x.blend": _file(str(tmp_path), "materials/x.blend")}
    rows = [_row("material:paint_satin", "materials/x.blend", cost=1.0),
            _row("material:paint_satin", "materials/x.blend", cost=1.2)]
    f = ap.read(str(make_pack(str(tmp_path), rows=rows, files=files) and tmp_path), APP)
    assert f.pack.assets["material:paint_satin"].cost == 1.0 and "twice" in f.pack.left_out[0][1]
    assert "1 item" in f.note


@pytest.mark.parametrize("kind", [k for k, n in ap.CONTRACTS.items()])
def test_a_newer_contract_per_kind_uses_the_code_look(tmp_path, kind):
    blend = kind in ap.BLEND_KINDS
    rel = f"{kind}/x" + (".blend" if blend else ap.PICTURE_KINDS.get(kind, (".exr",))[0])
    files = {rel: _file(str(tmp_path), rel)}
    newer = _row(f"{kind}:newer", rel, contract=ap.CONTRACTS[kind] + 1)
    make_pack(str(tmp_path), rows=[newer], files=files)
    f = ap.read(str(tmp_path), APP)
    assert f.pack.assets == {} and "newer than this app" in f.pack.left_out[0][1] and f.note == ap.rows_note(1)
    # the pack's own contract per kind counts the same way
    make_pack(str(tmp_path), rows=[_row(f"{kind}:newer", rel)], files=files,
              contract={kind: ap.CONTRACTS[kind] + 1})
    assert ap.read(str(tmp_path), APP).pack.assets == {}


def test_two_bad_rows_one_note(tmp_path):
    files = {"materials/x.blend": _file(str(tmp_path), "materials/x.blend")}
    make_pack(str(tmp_path), files=files, rows=[_row("material:a", "../x.blend"), _row("x:y", "materials/x.blend"),
                                                _row("material:paint_satin", "materials/x.blend")])
    f = ap.read(str(tmp_path), APP)
    assert f.note.startswith("2 items of the Fresing assets pack are left out") and len(f.pack.assets) == 1


def test_a_link_out_of_the_pack_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.blend").write_bytes(b"x")
    pack = tmp_path / "pack"
    pack.mkdir()
    try:
        os.symlink(str(outside), str(pack / "materials"))
    except (OSError, NotImplementedError):
        pytest.skip("no symbolic links here")
    info = {"bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
    make_pack(str(pack), rows=[_row("material:paint_satin", "materials/x.blend")],
              files={"materials/x.blend": info})
    p = ap.read(str(pack), APP).pack
    assert p.path("materials/x.blend") == ""
    v = ap.verify(p)
    assert not v.ok and "outside the pack" in v.problems[0]


def test_read_never_raises_whatever_the_row(tmp_path):
    files = {"materials/x.blend": _file(str(tmp_path), "materials/x.blend")}
    weird = [None, [], {"id": None}, {"id": "material:a", "file": None}, {"id": "material:a" * 50},
             {"id": "material:a", "file": "materials/x.blend", "datablock": [None, None]},
             {"id": "material:a", "file": "materials/x.blend", "datablock": ["node_groups", "x"], "size_m": True},
             {"id": "material:a", "file": "materials/x.blend", "datablock": ["node_groups", "x"], "cost": True}]
    make_pack(str(tmp_path), files=files, rows=weird)
    f = ap.read(str(tmp_path), APP)
    assert f.state == "ok" and f.pack.assets == {} and len(f.pack.left_out) == len(weird)


# ---------------------------------------------------------------------------
# verify: size and sha256 of every listed file
# ---------------------------------------------------------------------------

def test_verify_finds_a_changed_size_a_changed_content_and_a_missing_file(tmp_path):
    make_pack(str(tmp_path))
    p = ap.read(str(tmp_path), APP).pack
    seen = []
    v = ap.verify(p, progress=lambda done, total: seen.append((done, total)))
    assert v.ok and v.problems == [] and v.files == len(p.files) and v.bytes == p.bytes and seen[-1][0] == p.bytes
    (tmp_path / "materials" / "paint_satin.blend").write_bytes(b"different size")
    rel = "lights/PRODUCT.exr"
    data = (tmp_path / "lights" / "PRODUCT.exr").read_bytes()
    (tmp_path / "lights" / "PRODUCT.exr").write_bytes(bytes([data[0] ^ 1]) + data[1:])       # same size
    (tmp_path / "props" / "PALLET.blend").unlink()
    v = ap.verify(p)
    text = "\n".join(v.problems)
    assert not v.ok and len(v.problems) == 3
    assert "materials/paint_satin.blend is " in text and "bytes, the list says" in text
    assert f"{rel} has another content" in text and "props/PALLET.blend is missing" in text


def test_reading_does_not_hash_the_files(tmp_path, monkeypatch):
    make_pack(str(tmp_path))
    (tmp_path / "materials" / "paint_satin.blend").write_bytes(b"changed after the install")
    calls = []
    monkeypatch.setattr(ap.hashlib, "sha256", lambda *a: calls.append(a) or hashlib.sha256(*a))
    assert ap.read(str(tmp_path), APP).state == "ok" and calls == []      # only verify() reads the files


def test_sizes_above_budget_are_warnings(tmp_path):
    big = b"x" * 1_100_000
    rows = [_row("material:paint_satin", "materials/paint_satin.blend", set="paints")]
    files = {"materials/paint_satin.blend": _file(str(tmp_path), "materials/paint_satin.blend", big)}
    make_pack(str(tmp_path), rows=rows, files=files,
              sets={"paints": {"title": "Paints", "budget_mb": 1}})
    f = ap.read(str(tmp_path), APP)
    assert f.state == "ok" and "material:paint_satin" in f.pack.assets   # a warning, not a stop
    assert ap.size_problems(f.pack) == ["Set 'paints' is 1.1 MB, above its budget of 1 MB"]
    files["materials/paint_satin.blend"]["bytes"] = 301_000_000          # pick 11: ~300 MB
    make_pack(str(tmp_path), rows=rows, files=files, sets={"paints": {"title": "Paints"}})
    assert ap.size_problems(ap.read(str(tmp_path), APP).pack) == ["The pack is 301 MB, above the planned 300 MB"]


# ---------------------------------------------------------------------------
# where the app looks (1.2)
# ---------------------------------------------------------------------------

def _install(tmp_path):
    inst = tmp_path / "FresingRender"
    (inst / "blender-5.2.3-windows-x64").mkdir(parents=True)
    (inst / "installed.txt").write_text("0.2.300")
    return inst, str(inst / "blender-5.2.3-windows-x64" / "blender.exe")


def test_where_the_app_looks(tmp_path, monkeypatch):
    inst, binary = _install(tmp_path)
    company = tmp_path / "share" / "Fresing Assets"
    company.mkdir(parents=True)
    assert ap.places(str(company), binary) == [str(company), str(inst / "Fresing Assets")]
    assert ap.places("", str(tmp_path / "elsewhere" / "blender" / "blender")) == []      # not an installed Blender
    assert ap.find(APP, str(company), binary).state == "none"                          # nothing anywhere
    make_pack(str(inst / "Fresing Assets"), version="1.0.0")
    assert ap.find(APP, str(company), binary).where == str(inst / "Fresing Assets")    # the share is empty
    make_pack(str(company), version="1.2.0")
    f = ap.find(APP, str(company), binary)
    assert f.where == str(company) and f.pack.version == "1.2.0"                       # the company's comes first
    env = tmp_path / "env pack"
    monkeypatch.setenv(ap.ENV, str(env))
    assert ap.places(str(company), binary) == [str(env)]
    assert ap.find(APP, str(company), binary).state == "none"                          # only FRESING_ASSETS
    make_pack(str(env), version="1.1.0")
    assert ap.find(APP, str(company), binary).pack.version == "1.1.0"


def test_a_damaged_first_place_says_so(tmp_path):
    inst, binary = _install(tmp_path)
    make_pack(str(inst / "Fresing Assets"))
    company = tmp_path / "share"
    company.mkdir()
    (company / "pack.json").write_text("{", encoding="utf-8")
    f = ap.find(APP, str(company), binary)
    assert f.pack is None and f.state == "damaged" and f.where == str(company)


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------

def test_code_ids_are_read_from_the_code():
    from fresing_render.core import decal_art, finishes, materials_lib, props_detail, studio, surroundings, weather
    from fresing_render.lifting_model import classes
    from fresing_render.blender import cable_looks
    c = reg.code_ids()
    assert set(c) == set(ap.KINDS)
    assert c["material"] == set(materials_lib.UIDS) and len(c["material"]) >= 87
    assert c["finish"] == set(finishes.FINISHES) and c["finish"] <= c["material"]      # finish ids are material ids
    assert c["light"] == set(studio.LOOKS) and "PRODUCT" in c["light"]
    assert c["environment"] == {k.id for k in surroundings.KINDS} and "FACTORY" in c["environment"]
    assert c["prop"] == set(surroundings.PROPS) and c["person"] == set(props_detail.OUTFITS)
    assert c["decal"] == set(decal_art.STICKER_KEYS) and c["cable_look"] == set(cable_looks.KINDS)
    assert c["crane"] == set(classes.CLASSES) and c["weather"] == set(weather.PRESETS) and c["hdri"] == set()
    assert {"crane", "mill", "weather", "looks"} <= c["project"]                      # tour sets + lessons


def test_tour_sets_are_read_without_blender(tmp_path):
    src = tmp_path / "tour.py"
    src.write_text('HUB = "hub"\n@tour_set(HUB, "Hub")\ndef a(): pass\n@tour_set("b", "B")\ndef b(): pass\n'
                   '@other("c")\ndef c(): pass\n', encoding="utf-8")
    assert reg.tour_sets(str(src)) == ["hub", "b"]


def _registry(tmp_path, rows=None, files=None, code=None):
    make_pack(str(tmp_path), rows=rows, files=files)
    return reg.Registry.build(ap.read(str(tmp_path), APP), code)


def test_every_code_id_of_every_kind_resolves_without_a_pack():
    r = reg.Registry.build(ap.Found())
    for kind, ids in reg.code_ids().items():
        for i in ids:
            c = r.resolve(f"{kind}:{i}")
            assert c.source == "code" and c.id == f"{kind}:{i}" and c.asset is None
    assert r.note == "" and r.problems() == [] and r.pack is None and r.version == ""


def test_every_code_id_resolves_with_the_pack_too(tmp_path):
    r = _registry(tmp_path)
    for full in reg.code_full_ids():
        c = r.resolve(full)
        assert c.id == full and c.source == ("pack" if full in r.usable else "code")


def test_resolve_order(tmp_path):
    r = _registry(tmp_path)
    c = r.resolve("material:paint_satin")
    assert c.source == "pack" and c.id == "material:paint_satin" and c.asset.file == "materials/paint_satin.blend"
    assert c.pack_version == "1.0.0" and c.code_id == "paint_satin"
    assert r.stamp(c) == {"id": "material:paint_satin", "pack": "fresing-assets-test", "version": "1.0.0",
                          "contract": 1, "sha": c.asset.sha256}
    # a project made before the pack (source "") or set to code keeps today's look
    for source in ("", "code"):
        assert r.resolve("material:paint_satin", source=source) == reg.Choice("code", "material:paint_satin")
    # the user's switch off: code
    assert r.resolve("material:paint_satin", use_pack=False).source == "code"
    assert r.stamp(r.resolve("material:paint_satin", use_pack=False)) == {}
    # a code id the pack does not have: code
    assert r.resolve("material:steel_machined") == reg.Choice("code", "material:steel_machined")
    # a pack-only id: the pack when allowed, else its fallback
    assert r.resolve("hdri:test_hall").source == "pack"
    assert r.resolve("hdri:test_hall", source="code") == reg.Choice("code", "light:OVERCAST")
    assert r.resolve("hdri:test_hall", use_pack=False) == reg.Choice("code", "light:OVERCAST")
    # nobody knows it: the caller's default
    for unknown in ("hdri:test_hall_gone", "material:nope", "nonsense", None, 3):
        assert r.resolve(unknown) == reg.Choice("code", "")


def test_a_pack_only_id_needs_a_twin_or_a_fallback(tmp_path):
    rel = "materials/x.blend"
    files = {rel: _file(str(tmp_path), rel), "hdri/h.exr": _file(str(tmp_path), "hdri/h.exr"),
             "props/p.blend": _file(str(tmp_path), "props/p.blend")}
    rows = [_row("material:paint_satin", rel),                                           # a twin: fine
            _row("material:concrete_new", rel, fallback="material:paint_satin"),        # materials need a twin
            _row("hdri:no_fallback", "hdri/h.exr"),
            _row("hdri:bad_fallback", "hdri/h.exr", fallback="light:NOPE"),
            _row("hdri:fine", "hdri/h.exr", fallback="light:OVERCAST"),
            _row("prop:FORKLIFT", "props/p.blend", fallback="prop:PALLET")]
    r = _registry(tmp_path, rows, files)
    assert set(r.usable) == {"material:paint_satin", "hdri:fine", "prop:FORKLIFT"}
    assert [i for i, _ in r.refused] == ["material:concrete_new", "hdri:no_fallback", "hdri:bad_fallback"]
    assert r.note == ap.rows_note(3) and r.note.startswith("3 items")
    probs = r.problems()
    assert any(p.startswith("material:concrete_new: left out – a material needs a built-in look") for p in probs)
    assert any(p.startswith("hdri:no_fallback: left out – no built-in look") for p in probs)
    assert any("light:NOPE is not a built-in look" in p for p in probs)
    # a refused id never answers from the pack
    assert r.resolve("material:concrete_new") == reg.Choice("code", "")
    assert r.resolve("hdri:no_fallback") == reg.Choice("code", "")
    assert r.resolve("prop:FORKLIFT", source="code") == reg.Choice("code", "prop:PALLET")
    assert [a.id for a in r.items("hdri")] == ["hdri:fine"] and r.has("prop:FORKLIFT")


def test_problems_count_rows_left_out_and_refused_together(tmp_path):
    rel = "materials/x.blend"
    files = {rel: _file(str(tmp_path), rel)}
    r = _registry(tmp_path, [_row("material:x", "../y.blend"), _row("material:new_only", rel)], files)
    assert r.note.startswith("2 items") and len(r.problems()) == 2
    r = reg.Registry.build(ap.read(str(tmp_path / "none"), APP))
    assert r.problems() == [] and r.note == ""
    (tmp_path / "pack.json").write_text("{", encoding="utf-8")
    r = reg.Registry.build(ap.read(str(tmp_path), APP))
    assert r.note == ap.NOTE_DAMAGED and r.problems() == [ap.NOTE_DAMAGED]


def test_the_pack_is_read_once(tmp_path, monkeypatch):
    make_pack(str(tmp_path))
    monkeypatch.setenv(ap.ENV, str(tmp_path))
    reg.code_ids()                                                   # the code modules are loaded once too
    first = reg.current(APP)
    assert first.resolve("material:paint_satin").source == "pack"
    opened = []
    real_open = builtins.open

    def counting(*a, **k):
        opened.append(a[0] if a else k.get("file"))
        return real_open(*a, **k)

    monkeypatch.setattr(builtins, "open", counting)
    monkeypatch.setattr(os.path, "isfile", lambda p: opened.append(p) or False)
    again = reg.current(APP, "/some/company/folder", "/any/blender")
    for _ in range(100):
        again.resolve("material:paint_satin")
        again.resolve("hdri:test_hall", source="code")
    assert again is first and opened == []                           # no file opened, nothing looked at
    monkeypatch.undo()
    reg.forget()
    monkeypatch.setenv(ap.ENV, str(tmp_path / "none"))
    assert reg.current(APP).pack is None                              # forget(): read again


def test_the_shipped_kinds_match_the_report():
    # 0344 2.1: today's kinds; weather stays code; every kind with contract 0 takes no pack items yet
    assert set(ap.KINDS) == {"material", "finish", "light", "hdri", "environment", "prop", "person", "decal",
                             "cable_look", "crane", "project", "weather"}
    assert ap.CONTRACTS["weather"] == 0
    assert set(ap.BLEND_KINDS) | set(ap.PICTURE_KINDS) == set(ap.KINDS) - {"weather"}
    assert ap.split_id("material:paint_satin") == ("material", "paint_satin") and ap.split_id("x") == ("", "")
