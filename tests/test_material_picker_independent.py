"""Independent tests of the material picker (task 0273), written from the brief by an agent that did not write the
code: hostile material files, every finish and material through the checks, colour families at the edges, odd
filter text, merge, and in Blender: every built-in applied in turn, own materials whose base or folder is gone,
renamed / deleted groups, paint schemes, templates with junk, Blender materials with odd names, node groups and
outside images, a deleted "FRM" material, duplicate ids, the folder read racing a save, and the Web 3D export."""

import json
import math
import ntpath
import os
import shutil

import pytest

from fresing_render.core import finishes as fin_core
from fresing_render.core import material_files as F
from fresing_render.core import materials_lib as ML

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")

GOOD = {"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "Blue", "base": "paint_satin",
        "changes": {"color": "RAL 5010"}}


def _write(folder, content):
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, F.JSON_NAME)
    with open(p, "wb") as fh:
        fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))
    return folder


def _with(**kw):
    d = json.loads(json.dumps(GOOD))
    d.update(kw)
    return json.dumps(d)


def _storable(text: str) -> bool:
    """A text Blender can keep in a string property and draw: valid UTF-8, no NUL (Blender cuts it there)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return "\x00" not in text


# ---------------------------------------------------------------------------------------------------------------------
# core: hostile material.json files – never an exception, a broken file is an entry with its problem

HOSTILE = {
    "nan": '{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "X", "base": "chrome",'
           ' "changes": {"wear": NaN}}',
    "infinity": '{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "X", '
                '"base": "chrome", "changes": {"wear": Infinity}}',
    "huge_float": _with(changes={"wear": 1e308, "rust": -1e308, "color": "RAL 5010"}).replace("1e+308", "1e400"),
    "huge_int": _with().replace('"Blue"', '"Blue", "big": ' + "9" * 5000),
    "deep": "[" * 100000 + "]" * 100000,
    "deep_in_field": _with()[:-1] + ', "extra": ' + "[" * 50000 + "]" * 50000 + "}",
    "not_utf8": b'{"format": "fresing-material", "name": "Bl\xe4u"}',
    "utf16": _with().encode("utf-16"),
    "bom": b"\xef\xbb\xbf" + _with().encode("utf-8"),
    "empty": "",
    "null": "null",
    "string": '"fresing-material"',
    "list_of_dicts": "[" + _with() + "]",
    "id_path": _with(id="../../etc"),
    "id_backslash": _with(id="..\\..\\x"),
    "id_number": _with(id=12345678),
    "id_long": _with(id="a" * 65),
    "name_list": _with(name=["a", "b"]),
    "name_dict": _with(name={"a": 1}),
    "name_bool": _with(name=True),
    "name_huge": _with(name="N" * 10000),
    "name_blank": _with(name=" \t\n "),
    "name_reserved": _with(name="CON"),
    "base_list": _with(base=["chrome"]),
    "base_blender": _with(base="blender_material"),
    "base_none": _with(base=None),
    "changes_list": _with(changes=["color", "RAL 5010"]),
    "changes_str": _with(changes="RAL 5010"),
    "changes_wrong_types": _with(changes={"color": 5010, "wear": "0.5", "rust": [1], "finish": "fine"}),
    "changes_bool": _with(changes={"wear": True, "rust": False}),
    "finish_junk": _with(base="knurl_diamond", changes={"finish": {"size": "big", "angle": [], "amount": {},
                                                                    "base": 5, "kind": None, "extra": 1}}),
    "tags_junk": _with(tags={"material": ["Paint"], "colour": {"x": 1}, "looks": "gloss"}),
    "tags_list": _with(tags=["Paint", "blue"]),
    "tags_looks_unhashable": _with(tags={"looks": [["gloss"], {"a": 1}, "gloss", "gloss"]}),
    "version_number": _with(format_version=1.0),
    "version_text": _with(format_version="one"),
    "version_huge": _with(format_version="99999999999999999999.0"),
    "version_newer_minor": _with(format_version="1.99"),
    "version_older": _with(format_version="0.1"),
    "blend_str": _with(blend="material.blend"),
    "blend_no_material": _with(blend={"file": "material.blend"}),
    "blend_up": _with(blend={"file": "../x.blend", "material": "M"}),
    "blend_abs": _with(blend={"file": "/etc/passwd", "material": "M"}),
    "blend_backslash": _with(blend={"file": "..\\..\\x.blend", "material": "M"}),
    "blend_nul": _with(blend={"file": "material.blend\u0000x", "material": "M"}),
    "blend_images_junk": _with(blend={"material": "M", "images_outside": "C:/x.png"}),
    "description_dict": _with(description={"a": "b"}, author=["x"]),
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile_material_files_never_raise(tmp_path, name):
    folder = _write(str(tmp_path / "Materials" / name), HOSTILE[name])
    found = F.list_folder(str(tmp_path / "Materials"))
    assert len(found) == 1
    e = found[0]
    assert isinstance(e, F.Entry)
    assert e.key.startswith("own:")
    # whatever came in, what is shown and kept is clean
    assert isinstance(e.name, str) and 0 < len(e.name) <= 200
    assert e.kind in ML.KINDS and e.colour in ML.COLOURS and all(x in ML.LOOKS for x in e.looks)
    assert e.base in ML.MATERIALS and e.base != "blender_material"
    if e.ok:
        assert set(e.changes) <= set(F.CHANGE_KEYS)
        for k in ("wear", "rust"):
            if k in e.changes:
                assert isinstance(e.changes[k], float) and 0.0 <= e.changes[k] <= 1.0
        v = F.values_of(e)
        assert math.isfinite(v["wear"]) and math.isfinite(v["rust"])
        if e.blend:
            # the Blender file is always inside the folder
            assert os.path.dirname(os.path.abspath(e.blend)) == os.path.abspath(folder)
    if e.blend:
        assert os.path.dirname(os.path.abspath(e.blend)) == os.path.abspath(folder)


def test_hostile_files_get_the_expected_verdict(tmp_path):
    def entry(n):
        root = tmp_path / n
        _write(str(root / "m"), HOSTILE[n])
        return F.list_folder(str(root))[0]

    for n in ("nan", "infinity", "deep", "not_utf8", "utf16", "empty", "null", "string", "list_of_dicts", "id_path",
              "id_backslash", "id_number", "id_long", "name_list", "name_blank", "base_list", "base_blender",
              "version_number", "version_text", "blend_str", "blend_no_material", "blend_up"):
        assert not entry(n).ok, n
    for n in ("bom", "huge_float", "changes_wrong_types", "finish_junk", "tags_junk", "version_newer_minor",
              "version_older", "description_dict", "name_huge", "name_reserved"):
        assert entry(n).ok, (n, entry(n).problems)
    assert entry("huge_float").changes in ({"wear": 1.0, "color": "RAL 5010"}, {"color": "RAL 5010"})
    assert not entry("version_huge").ok


def test_a_name_with_a_lone_surrogate_is_kept_storable(tmp_path):
    """JSON may escape a lone surrogate (\\ud800): Python keeps it, Blender cannot store it (a TypeError on every
    string property, a failed draw). Such a file must still be an entry whose texts Blender can show (or a broken
    entry), never one that breaks the window or the project."""
    for i, raw in enumerate(('"Blau \\ud800 x"', '"\\udfff"')):
        folder = _write(str(tmp_path / f"m{i}"), _with().replace('"Blue"', raw))
        e = F.read_folder(folder)
        assert _storable(e.name) or not e.ok, repr(e.name)
        if e.ok:
            json.dumps(e.data, ensure_ascii=False).encode("utf-8")      # the project copy (remember) can be stored


def test_a_name_with_a_nul_is_not_cut_short(tmp_path):
    """A NUL in a name: Blender cuts a string property there ("Grün\\x00hidden" shows as "Grün")."""
    folder = _write(str(tmp_path / "m"), _with().replace('"Blue"', '"Gr\\u00fcn\\u0000hidden"'))
    e = F.read_folder(folder)
    assert "\x00" not in e.name, repr(e.name)


def test_description_and_author_are_storable(tmp_path):
    folder = _write(str(tmp_path / "m"), _with(description="a\ud800b", author="c\udfffd"))
    e = F.read_folder(folder)
    assert _storable(e.description) and _storable(e.author)


def test_the_blend_file_cannot_point_outside_on_windows_either(monkeypatch, tmp_path):
    """On Windows a backslash separates folders: a file name like '..\\x.blend' must not leave the folder."""
    monkeypatch.setattr(F.os, "path", ntpath)
    folder = "C:\\Materials\\m"
    for f in ("..\\x.blend", "C:x.blend", "\\\\server\\share\\x.blend", "D:\\x.blend", "sub\\material.blend"):
        e = F.entry_from_data(json.loads(_with(blend={"file": f, "material": "M"})), folder=folder)
        assert ntpath.dirname(e.blend) == folder, (f, e.blend)


def test_material_json_that_is_a_folder_and_odd_roots(tmp_path):
    (tmp_path / "M" / "a" / F.JSON_NAME).mkdir(parents=True)
    found = F.list_folder(str(tmp_path / "M"))
    assert len(found) == 1 and not found[0].ok
    assert F.list_folder(str(tmp_path / "does not exist")) == []
    (tmp_path / "file.txt").write_text("x")
    assert F.list_folder(str(tmp_path / "file.txt")) == []
    assert F.list_folder("") == []


def test_a_folder_that_disappears_between_listing_and_reading(tmp_path, monkeypatch):
    root = tmp_path / "M"
    for n in ("a", "b", "c"):
        _write(str(root / n), _with(id=f"id_{n}xx", name=n))
    real = F.read_folder

    def vanish(folder, *a, **k):
        if folder.endswith("b"):
            shutil.rmtree(folder)
        return real(folder, *a, **k)

    monkeypatch.setattr(F, "read_folder", vanish)
    found = F.list_folder(str(root))
    assert [e.ok for e in found] == [True, False, True]

    real_listdir = os.listdir

    def gone(p):                                    # the whole Materials folder goes while it is listed
        if str(p).endswith(os.sep + "a"):
            raise FileNotFoundError(p)
        return real_listdir(p)

    monkeypatch.setattr(F, "read_folder", real)
    monkeypatch.setattr(F.os, "listdir", gone)
    found = F.list_folder(str(root))
    assert all(isinstance(e, F.Entry) for e in found)


def test_a_too_big_file_is_a_problem_not_a_read(tmp_path):
    folder = _write(str(tmp_path / "m"), _with(description="x" * (F.MAX_JSON + 10)))
    e = F.read_folder(folder)
    assert not e.ok


# ---------------------------------------------------------------------------------------------------------------------
# core: changes, values, finishes

JUNK = [None, True, False, "1", [], {}, float("nan"), float("inf"), -float("inf"), 1e308, -1e308, 0, -0.0, 1e-30, 7]


@pytest.mark.parametrize("mid", sorted(fin_core.FINISHES))
def test_every_finish_keeps_its_settings_inside_the_limits(mid):
    material = next(m for m, s in ML.MATERIALS.items() if s.get("finish") == mid)
    f = fin_core.FINISHES[mid]
    used = set(fin_core.settings_of(material))
    for junk in JUNK:
        for base in [junk, "STEEL", "STAINLESS", "nope", *(f.get("bases") or ())]:
            for kind in [junk, "nope", *(f.get("kinds") or ())]:
                ch = F.clean_changes(material, {"finish": {"size": junk, "angle": junk, "amount": junk,
                                                           "base": base, "kind": kind}})
                fin = ch.get("finish", {})
                assert set(fin) <= used, (material, fin)
                e = F.Entry(key="own:abcd1234", name="x", base=material, changes=ch)
                v = F.values_of(e)["finish"]
                assert v is not None
                if f.get("size"):
                    assert f["size"][3] <= v["size"] <= f["size"][4]
                if f.get("angle"):
                    assert f["angle"][2] <= v["angle"] <= f["angle"][3]
                if f.get("amount"):
                    assert 0.0 <= v["amount"] <= 1.0
                assert all(math.isfinite(v[k]) for k in ("size", "angle", "amount"))
                assert v["base"] in (f.get("bases") or ("",))
                assert v["kind"] in (f.get("kinds") or ("",))
                # what goes into the group's enum fields exists there
                assert (v["base"] in fin_core.BASES) == bool(f.get("bases"))
                assert (v["kind"] in fin_core.KINDS) == bool(f.get("kinds"))


@pytest.mark.parametrize("material", sorted(ML.MATERIALS))
def test_colour_wear_and_rust_only_where_the_material_has_them(material):
    for junk in JUNK + ["RAL 5010", "#13447C", " ral 3020 ", "#zzz", "RAL", ""]:
        ch = F.clean_changes(material, {"color": junk, "wear": junk, "rust": junk})
        if "color" in ch:
            assert ML.needs_color(material) and F.rgb_of(ch["color"]) is not None
        if "rust" in ch:
            assert ML.rust_kind(material) or fin_core.get(material) is not None
            assert 0.0 <= ch["rust"] <= 1.0
        if "wear" in ch:
            assert 0.0 <= ch["wear"] <= 1.0
        e = F.Entry(key="own:abcd1234", name="x", base=material, changes=ch)
        v = F.values_of(e)
        assert v["material"] == (material if material in ML.MATERIALS else "paint_satin")
        assert 0.0 <= v["wear"] <= 1.0 and 0.0 <= v["rust"] <= 1.0


def _rusting_finishes():
    out = []
    for m in ML.MATERIALS:
        f = fin_core.get(m)
        if not f:
            continue
        for b in (f.get("bases") or ("",)):
            for k in (f.get("kinds") or ("",)):
                if ML.rust_kind(m, b, k):
                    out.append((m, b, k))
    return out


@pytest.mark.parametrize("material, base, kind", _rusting_finishes())
def test_rust_of_a_finish_whose_metal_rusts_is_kept(material, base, kind):
    """A steel knurl, a honed cast-iron bore, galvanized tread plate … rust (ML.rust_kind with the finish's Metal /
    Kind says so, and 3 Looks shows the Rust slider): saving such a group as an own material must keep its rust."""
    ch = F.changes_of(material, "", 0.0, 0.5, {"base": base, "kind": kind})
    assert ch.get("rust") == pytest.approx(0.5), (material, base, kind, ch)


def test_no_rust_where_the_finish_metal_cannot_rust():
    for m in ML.MATERIALS:
        f = fin_core.get(m)
        for b in ((f.get("bases") if f else None) or ("",)):
            for k in ((f.get("kinds") if f else None) or ("",)):
                if not ML.rust_kind(m, b, k):
                    ch = F.changes_of(m, "", 0.0, 0.5, {"base": b, "kind": k} if f else None)
                    assert "rust" not in ch, (m, b, k)


# ---------------------------------------------------------------------------------------------------------------------
# core: colour families, filters, merge, folder names

def test_colour_family_never_raises_and_is_a_filter_value():
    steps = [i / 20 for i in range(21)]
    for r in steps:
        for g in steps:
            for b in steps:
                assert F.colour_family((r, g, b)) in ML.COLOURS
    for odd in [(float("nan"),) * 3, (float("inf"), 0, 0), (-5, 2, 0.5), (1, 1, 1), (0, 0, 0), (255, 255, 255),
                (True, False, 0), [0.5, 0.5, 0.5]]:
        assert F.colour_family(odd) in ML.COLOURS
    assert F.colour_family((0, 0, 0)) == "black" and F.colour_family((1, 1, 1)) == "white"
    for v in (0.3, 0.5, 0.7):
        assert F.colour_family((v, v, v)) == "grey"
    import colorsys
    for deg in range(0, 360, 5):                   # a full-strength hue is never white, grey or black
        rgb = colorsys.hsv_to_rgb(deg / 360, 1.0, 1.0)
        assert F.colour_family(rgb) not in ("white", "grey", "black", "any", "metal"), deg


def test_every_ral_colour_has_a_family():
    from fresing_render.core import ral
    table = getattr(ral, "RAL", None) or getattr(ral, "COLOURS", None) or {}
    codes = list(table)[:400] if isinstance(table, dict) else []
    for code in codes:
        rgb = F.rgb_of(code if str(code).upper().startswith("RAL") else f"RAL {code}")
        if rgb:
            assert F.colour_family(rgb) in ML.COLOURS


@pytest.mark.parametrize("text", ["", " ", "\t\n", "*", ".*", "(", "[a-", "\\", "ß", "STRASSE", "ÄÖÜ", "\x00",
                                  "\ud800", "x" * 100000, "blue  satin", "RAL 5010", "🙂", None, 5, "Built-in"])
def test_filters_with_odd_text(text):
    b = F.builtin_entries()
    own = [F.Entry(key="own:x", name="Straße blau", source="mine", badge="Mine", base="unknown_base",
                   changes={"color": "RAL 5010"}),
           F.entry_from_data(None)]
    for kind in ("", "Paint", "nope"):
        for colour in ("", "any", "blue", "nope"):
            for look in ("", "gloss", "nope"):
                out = F.filter_entries(b + own, text, "", kind, colour, look)
                assert isinstance(out, list)
    if text in ("", " ", "\t\n", None):
        assert len(F.filter_entries(b, text)) == len(b)


def test_search_casefolds_both_ways():
    own = [F.Entry(key="own:x", name="Straße", source="mine", badge="Mine")]
    assert F.filter_entries(own, "STRASSE") and F.filter_entries(own, "straße")


def test_merge_keeps_every_builtin_and_the_folders_copy():
    b = F.builtin_entries()
    own = [F.Entry(key="own:a1b2", name="A", source="company", badge="ACME"),
           F.Entry(key="own:a1b2", name="A (dept)", source="department", badge="Dept"),
           F.Entry(key="own:c3d4", name="C", source="mine", badge="Mine", problems=["broken"])]
    proj = [F.Entry(key="own:a1b2", name="A", source="project", badge="This project"),
            F.Entry(key="own:c3d4", name="C copy", source="project", badge="This project"),
            F.Entry(key="own:e5f6", name="E", source="project", badge="This project")]
    m = F.merge(b, own, proj)
    assert [e.key for e in m[:len(b)]] == [e.key for e in b]
    rest = m[len(b):]
    assert sum(1 for e in rest if e.source == "project" and e.key == "own:a1b2") == 0
    # a broken folder does not hide the project's working copy
    assert any(e.key == "own:c3d4" and e.ok for e in rest)
    assert any(e.key == "own:e5f6" for e in rest)
    assert len(m) == len(b) + len(own) + 2
    assert F.merge([], [], []) == []


def test_builtin_keys_unique_and_every_builtin_has_tags_and_a_picture():
    b = F.builtin_entries()
    assert len({e.key for e in b}) == len(b)
    for e in b:
        assert e.kind in ML.KINDS and e.colour in ML.COLOURS and e.looks and all(x in ML.LOOKS for x in e.looks)
        assert e.picture and os.path.isfile(e.picture), e.key
        assert e.base in ML.UIDS


@pytest.mark.parametrize("name, ok", [
    ("CON", "CON_"), ("con .txt", None), ("COM¹", "COM¹_"), ("LPT³.x", "LPT³.x_"), ("CONIN$", "CONIN$_"),
    ("COM1 ", "COM1_"), ("nul.tar.gz", "nul.tar.gz_"), ("Clock$", "Clock$_"), ("N" * 10000, None),
    ("a/b\\c:d*e?f\"g<h>i|j", "a_b_c_d_e_f_g_h_i_j"), ("tab\there", "tab_here"), ("ends with dots...", "ends with dots"),
    ("  spaces  ", "spaces"), ("x" * 79 + " .", None),
])
def test_folder_names_for_windows(name, ok):
    s = F.folder_name(name)
    assert 0 < len(s) <= 80
    assert not s.endswith((" ", ".")) and not F._BAD_CHARS.search(s)
    assert s.split(".")[0].strip().upper() not in F._RESERVED
    if ok:
        assert s == ok


@pytest.mark.parametrize("name", ["", "   ", "...", " . . "])
def test_folder_names_that_are_nothing(name):
    try:
        s = F.folder_name(name)
    except F.MaterialError:
        return
    assert s and s.strip(" ._")


def test_save_new_never_overwrites_and_handles_long_names(tmp_path):
    d = F.new_material("x" * 10000, "chrome")
    a = F.save_new(str(tmp_path), d)
    b = F.save_new(str(tmp_path), d)
    assert a != b and os.path.isfile(os.path.join(a, F.JSON_NAME)) and os.path.isfile(os.path.join(b, F.JSON_NAME))
    assert len(os.path.basename(a)) <= 80
    e = F.read_folder(a)
    assert e.ok and len(e.name) <= 120
    assert not [n for n in os.listdir(a) if n.endswith(".tmp")]


def test_new_material_refuses_and_cleans():
    with pytest.raises(F.MaterialError):
        F.new_material("", "chrome")
    with pytest.raises(F.MaterialError):
        F.new_material("x", "unobtainium")
    d = F.new_material("  a \n b  ", "steel_machined", {"color": "RAL 5010", "wear": 2, "rust": float("nan")})
    assert d["name"] == "a b" and d["changes"] == {"wear": 1.0}
    json.dumps(d, allow_nan=False)


# ---------------------------------------------------------------------------------------------------------------------
# Blender

bpy = None


@pytest.fixture(scope="module")
def app():
    global bpy
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture()
def loc(app, tmp_path, monkeypatch):
    from fresing_render.blender import locations, material_picker, prefs
    from fresing_render.core import locations as L
    monkeypatch.setenv(locations.ENV, str(tmp_path / "config" / L.STATE_FILE))
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs"))
    prefs.get().library_path = ""
    locations.forget()
    locations.load()
    locations.wait_reach()
    material_picker._S.update(own=[], own_time=-1e9, own_gen=None, own_busy=False, own_result=None)
    material_picker.forget()
    yield locations
    locations.forget()


@pytest.fixture()
def no_pictures(monkeypatch, app):
    """The pictures of own materials are not made (a background Blender each: the CPU is shared)."""
    from fresing_render.blender import material_picker as MP
    monkeypatch.setattr(MP, "make_picture", lambda e: False)


@pytest.fixture()
def scene(loc, no_pictures):
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.groups_index = 0
    return sc


def _mine(loc):
    return loc.save_folder("materials")


def _parts(sc, name):
    from fresing_render.blender import logic
    return list(logic.parts_in_group(sc, name))


def _shop_material(name="Shop red", rgb=(0.8, 0.05, 0.03)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
    return mat


def _outcome(op, **kw) -> str:
    """'done', 'refused' (CANCELLED, or an error report in plain words) or 'crash' (a Python error in the operator)."""
    try:
        r = op(**kw)
    except RuntimeError as exc:
        return "crash: " + str(exc)[-300:] if "Traceback" in str(exc) else "refused"
    return "done" if r == {"FINISHED"} else "refused"


class Strict:
    """A layout that refuses what Blender's would: a text or a property value Blender cannot store."""

    def __getattr__(self, name):
        def call(*a, **k):
            for v in list(a) + list(k.values()):
                if isinstance(v, str):
                    v.encode("utf-8")
            return Strict()
        return call

    def __setattr__(self, name, value):
        if isinstance(value, str):
            value.encode("utf-8")

    def __iter__(self):
        return iter((Strict(), Strict()))


def test_every_builtin_applied_in_turn(scene):
    from fresing_render.blender import material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    parts = _parts(scene, g.name)
    assert parts
    for e in F.builtin_entries():
        assert bpy.ops.fresing.mat_use(key=e.key) == {"FINISHED"}, e.key
        assert g.mat_key == e.key and g.material == e.base, e.key
        mat = bpy.data.materials["FR " + g.name]
        assert mat.get("fr_material") == e.base, e.key
        assert all(ob.material_slots[0].material == mat for ob in parts), e.key
        if e.changes.get("color"):
            assert g.color == e.changes["color"]
        assert MP.group_key(g) == e.key
    UIs = __import__("fresing_render.blender.ui_material_picker", fromlist=["x"])
    UIs.draw_window(Strict(), bpy.context)


def test_an_own_material_whose_base_is_unknown_later(scene, loc):
    """A project copy made by a newer app (an unknown base): listed with its problem, using it is refused politely,
    and the group keeps working."""
    from fresing_render.blender import logic, material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    data = json.loads(_with(id="newer0001", name="From the future", base="unobtainium"))
    pm = s.project_materials.add()
    pm.name, pm.title, pm.data, pm.listed = "own:newer0001", "From the future", json.dumps(data), True
    g.mat_key = "own:newer0001"
    e = MP.find(scene, "own:newer0001")
    assert e is not None and not e.ok
    assert _outcome(bpy.ops.fresing.mat_use, key="own:newer0001") == "refused"
    assert bpy.ops.fresing.mat_star(key="own:newer0001") == {"FINISHED"}         # off the list again
    logic.refresh_group_materials(scene)
    MP.short_list(scene)
    from fresing_render.blender import ui_material_picker as UI
    UI.draw_short_list(Strict(), bpy.context, g)
    UI.draw_window(Strict(), bpy.context)


def test_group_renamed_after_an_own_blender_material(scene, loc):
    from fresing_render.blender import logic, material_picker as MP
    g = scene.fresing.groups[0]
    e = MP.save_from_blender(bpy.context, _shop_material(), "Shop red", "", _mine(loc), group=g)
    assert e.ok and g.material == "blender_material"
    old = g.name
    g.name = old + " renamed"
    logic.refresh_group_materials(scene)
    gm = bpy.data.materials["FR " + g.name]
    assert gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[0] == pytest.approx(0.8)
    assert all(ob.material_slots[0].material == gm for ob in _parts(scene, g.name))
    assert bpy.data.materials.get("FR " + old) is None or bpy.data.materials["FR " + old].users == 0


def test_removing_a_project_material_a_group_uses(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    g.material, g.color = "paint_satin", "RAL 6018"
    e = MP.save_from_group(bpy.context, g, "Green", "", _mine(loc))
    MP.add_to_project(scene, e)
    assert bpy.ops.fresing.mat_unlist(key=e.key) == {"FINISHED"}
    assert s.project_materials.get(e.key) is not None and s.project_materials[e.key].data   # the group uses it
    shutil.rmtree(e.folder)
    MP.refresh_own(force=True, wait=True)
    found = MP.find(scene, e.key)
    assert found is not None and found.source == "project"
    assert [x.key for x, listed, used in MP.short_list(scene) if used and not listed] == [e.key] + \
        [k for k in MP.used_keys(scene) if k != e.key]


def test_paint_scheme_brings_back_an_own_blender_material_after_it_left_the_list(scene, loc):
    """Scheme A: a group with an own Blender material; scheme B: a built-in. While B is shown the material is taken
    off the project's list (no group uses it at that moment) – switching back to A must bring the material back,
    not a grey stand-in (the scheme still names it)."""
    from fresing_render.blender import logic, material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    e = MP.save_from_blender(bpy.context, _shop_material(), "Shop red", "", _mine(loc), group=g)
    MP.add_to_project(scene, e)
    logic.save_scheme(s, "A")
    assert bpy.ops.fresing.mat_use(key="builtin:chrome") == {"FINISHED"}
    logic.save_scheme(s, "B")
    assert bpy.ops.fresing.mat_unlist(key=e.key) == {"FINISHED"}
    shutil.rmtree(e.folder)                                    # … and on a PC without the folder
    MP.refresh_own(force=True, wait=True)
    logic.apply_scheme(scene, "A")
    assert g.material == "blender_material" and g.mat_key == e.key
    gm = bpy.data.materials["FR " + g.name]
    assert gm.node_tree.nodes.get("Principled BSDF") is not None and \
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[0] == pytest.approx(0.8), \
        "scheme A shows a stand-in: the own material's copy was removed with the list entry"


def test_paint_scheme_with_an_own_settings_material_keeps_its_wear(scene, loc):
    from fresing_render.blender import logic, material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    g.material, g.color, g.wear = "paint_satin", "RAL 5015", 0.6
    e = MP.save_from_group(bpy.context, g, "Worn blue", "", _mine(loc))
    logic.save_scheme(s, "Worn")
    assert bpy.ops.fresing.mat_use(key="builtin:paint_gloss") == {"FINISHED"}
    g.wear = 0.0
    logic.save_scheme(s, "Clean")
    logic.apply_scheme(scene, "Worn")
    assert g.mat_key == e.key
    # the group says it has the own material "Worn blue": then it must look like it
    assert g.wear == pytest.approx(0.6), "the scheme restores the own material's key but not its wear"


def test_short_list_with_a_deleted_group(scene):
    from fresing_render.blender import material_picker as MP, ui_material_picker as UI
    s = scene.fresing
    assert bpy.ops.fresing.mat_use(key="builtin:chrome") == {"FINISHED"}
    assert bpy.ops.fresing.mat_star(key="builtin:brass") == {"FINISHED"}
    s.groups.remove(0)
    s.groups_index = 0 if len(s.groups) else -1
    MP.short_list(scene)
    g = MP.current_group(bpy.context)
    if g is not None:
        UI.draw_short_list(Strict(), bpy.context, g)
    UI.draw_window(Strict(), bpy.context)
    s.groups_index = 99
    UI.draw_window(Strict(), bpy.context)
    assert bpy.ops.fresing.mat_use(key="builtin:chrome") == {"CANCELLED"}


def test_template_without_materials_and_with_junk(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP, ops_main
    from fresing_render.core.template import Template
    d = ops_main._template_from_scene(scene).to_dict()
    d.pop("materials", None)
    ops_main.apply_template(scene, Template.from_dict(d))                       # an older template
    for junk in ("x", 5, None, {"a": 1}):
        d["materials"] = junk
        ops_main.apply_template(scene, Template.from_dict(d))
    good = json.loads(_with(id="tmpl0001", name="From template"))
    d["materials"] = [1, None, "own:x", [], {"key": 5}, {"key": "builtin:nope"}, {"key": "preset:nope"},
                      {"key": "x:y"}, {"key": ""}, {"key": "own:"}, {"key": "own:junk0001", "data": "{"},
                      {"key": "own:junk0002", "data": {"not": "text"}}, {"key": "own:junk0003", "data": 5},
                      {"key": "own:junk0004", "data": "[1, 2]"}, {"key": "own:tmpl0001", "data": json.dumps(good),
                                                                  "title": None},
                      {"key": "own:mism0001", "data": json.dumps(good)},          # data of another id
                      {"key": "builtin:chrome", "title": "x" * 10000}]
    ops_main.apply_template(scene, Template.from_dict(d))
    keys = [e.key for e, listed, _u in MP.short_list(scene) if listed]
    assert "own:tmpl0001" in keys and "builtin:chrome" in keys
    own_keys = [e.key for e in MP.all_entries(scene) if e.source == "project" and e.ok]
    assert len(own_keys) == len(set(own_keys)), f"one material listed twice: {own_keys}"
    from fresing_render.blender import ui_material_picker as UI
    UI.draw_short_list(Strict(), bpy.context, scene.fresing.groups[0])
    UI.draw_window(Strict(), bpy.context)


def test_template_with_deeply_nested_data(scene, loc):
    """A company template whose material data is nested very deep (a broken or hostile file): the template still
    applies and the window still draws."""
    from fresing_render.blender import material_picker as MP, ops_main
    from fresing_render.core.template import Template
    d = ops_main._template_from_scene(scene).to_dict()
    d["materials"] = [{"key": "own:deep0001", "data": "[" * 200000 + "]" * 200000}]
    ops_main.apply_template(scene, Template.from_dict(d))
    MP.short_list(scene)
    from fresing_render.blender import ui_material_picker as UI
    UI.draw_window(Strict(), bpy.context)


def test_template_whose_own_blender_material_file_is_damaged(scene, loc):
    from fresing_render.blender import material_picker as MP, ops_main
    g = scene.fresing.groups[0]
    e = MP.save_from_blender(bpy.context, _shop_material(), "Shop red", "", _mine(loc), group=None)
    MP.add_to_project(scene, e)
    t = ops_main._template_from_scene(scene)
    with open(e.blend, "wb") as fh:
        fh.write(b"BLENDER-v999 this is not a blend file" * 10)
    MP.refresh_own(force=True, wait=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    ops_main.apply_template(sc, t)                       # must not raise
    sc.fresing.groups_index = 0
    assert "crash" not in _outcome(bpy.ops.fresing.mat_use, key=e.key)
    assert g is not None


def test_saving_a_blender_material_with_an_odd_name_node_group_and_outside_image(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP
    img_path = str(tmp_path / "outside textures" / "rust é.png")
    os.makedirs(os.path.dirname(img_path))
    img = bpy.data.images.new("rust", 8, 8)
    img.filepath_raw = img_path
    img.file_format = "PNG"
    img.save()
    name = 'Rot/Grün: "x" <a>|b?*c ' + "z" * 20
    mat = _shop_material(name)
    ng = bpy.data.node_groups.new("My group", "ShaderNodeTree")
    ng.interface.new_socket("Colour", in_out="OUTPUT", socket_type="NodeSocketColor")
    out = ng.nodes.new("NodeGroupOutput")
    tex = ng.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(img_path)
    ng.links.new(tex.outputs["Color"], out.inputs[0])
    grp = mat.node_tree.nodes.new("ShaderNodeGroup")
    grp.node_tree = ng
    mat.node_tree.links.new(grp.outputs[0], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    assert mat.name in [m.name for m in MP.blender_materials()]
    outside = MP.images_outside(mat, str(tmp_path / "nowhere"))
    assert any(os.path.normcase(p) == os.path.normcase(img_path) for p in outside), outside
    g = scene.fresing.groups[1]
    e = MP.save_from_blender(bpy.context, mat, "", "", _mine(loc), group=g)
    assert e.ok, e.problems
    assert os.path.dirname(e.folder) == _mine(loc)
    assert any(os.path.normcase(p) == os.path.normcase(img_path) for p in e.images_outside)
    assert e.name == " ".join(name.split())
    # used in a fresh project (the source material and node group are not there): the node group comes along
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.groups_index = 0
    MP.refresh_own(force=True, wait=True)
    assert bpy.ops.fresing.mat_use(key=e.key) == {"FINISHED"}
    gm = bpy.data.materials["FR " + sc.fresing.groups[0].name]
    groups = [n for n in gm.node_tree.nodes if n.type == "GROUP"]
    assert groups and groups[0].node_tree is not None and groups[0].node_tree.name.startswith("My group")


def test_project_opened_after_its_frm_material_was_deleted(scene, loc, tmp_path):
    from fresing_render.blender import logic, material_picker as MP, ui_material_picker as UI
    s = scene.fresing
    g = s.groups[0]
    e = MP.save_from_blender(bpy.context, _shop_material(), "Shop red", "", _mine(loc), group=g)
    src = bpy.data.materials[s.project_materials[e.key].blend_mat]
    bpy.data.materials.remove(src)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    shutil.rmtree(e.folder)
    MP.refresh_own(force=True, wait=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    g = sc.fresing.groups[0]
    assert g.material == "blender_material"
    logic.refresh_group_materials(sc)
    logic.upgrade_looks(sc)
    gm = bpy.data.materials["FR " + g.name]
    assert gm.node_tree is not None
    assert all(ob.material_slots[0].material == gm for ob in _parts(sc, g.name))
    UI.draw_window(Strict(), bpy.context)
    UI.draw_short_list(Strict(), bpy.context, g)
    assert _outcome(bpy.ops.fresing.mat_use, key=e.key) == "refused"      # refused in plain words, no crash
    assert bpy.ops.fresing.mat_use(key="builtin:chrome") == {"FINISHED"}


def test_a_hostile_name_does_not_break_the_star_the_use_or_the_window(scene, loc):
    from fresing_render.blender import material_picker as MP, ui_material_picker as UI
    root = _mine(loc)
    _write(os.path.join(root, "evil"), _with(id="evil0001").replace('"Blue"', '"Blau \\ud800"'))
    _write(os.path.join(root, "fine"), _with(id="fine0001", name="Fine"))
    MP.refresh_own(force=True, wait=True)
    assert any(e.key == "own:fine0001" for e in MP.all_entries(scene))
    r1 = _outcome(bpy.ops.fresing.mat_star, key="own:evil0001")     # a refusal or a success, never a Python error
    r2 = _outcome(bpy.ops.fresing.mat_use, key="own:evil0001")
    try:
        UI.draw_window(Strict(), bpy.context)                 # the rest of the window still draws
        drawn = "drawn"
    except (UnicodeEncodeError, TypeError) as exc:
        drawn = f"window draw fails: {exc}"
    assert (r1, r2, drawn) == ("done", "done", "drawn") or ("crash" not in r1 + r2 and drawn == "drawn"), \
        (r1, r2, drawn)


def test_the_same_material_in_two_folders_can_each_be_used(scene, loc, tmp_path):
    """Brief/Design: the same id in two folders lists twice, each with its badge. The user must be able to pick and
    use either: the company's copy and the edited copy in Mine (same id, another colour)."""
    from fresing_render.blender import material_picker as MP
    from fresing_render.core import locations as L
    shared = tmp_path / "Server" / "Materials"
    d = F.new_material("House blue", "paint_satin", {"color": "RAL 5010"}, ident="same0001")
    F.save_new(str(shared), d)
    s = L.Setup(id="acme", name="ACME", level="company", label="ACME", locations={"materials": [str(shared)]})
    p = str(tmp_path / "acme.frsetup")
    L.write_setup(p, s)
    loc.install(p, "copy")
    loc.wait_reach()
    d2 = dict(d, changes={"color": "RAL 5015"})
    F.save_new(_mine(loc), d2)
    MP.refresh_own(force=True, wait=True)
    both = [e for e in MP.all_entries(scene) if e.key == "own:same0001"]
    assert len(both) == 2 and {e.badge for e in both} == {"ACME", "Mine"}
    keys = [e.key for e in MP.all_entries(scene)]
    colours = set()
    for e in both:
        assert bpy.ops.fresing.mat_use(key=e.key) == {"FINISHED"}
        colours.add(scene.fresing.groups[0].color)
    assert colours == {"RAL 5010", "RAL 5015"} or len(keys) == len(set(keys)), \
        "both copies have one key: picking or using either always gives the first folder's copy"


def test_a_material_saved_while_the_folders_are_read_stays_listed(scene, loc):
    """The folders are read in a helper thread. A material saved while such a read is under way (it started before
    the save) must not vanish from the window when that older read arrives."""
    from fresing_render.blender import material_picker as MP
    g = scene.fresing.groups[0]
    g.material, g.color = "paint_satin", "RAL 1021"
    MP.refresh_own(force=True, wait=True)
    stale = list(MP._S["own"])                       # what the read that is under way will bring
    MP._S["own_busy"] = True
    try:
        e = MP.save_from_group(bpy.context, g, "Yellow", "", _mine(loc))
    finally:
        MP._S["own_result"] = stale
        MP._S["own_busy"] = False
    MP._take_own()
    assert e.key in [x.key for x in MP._S["own"] if x.source != "project"], \
        "the older read wrote over the list: the new material is gone until the next read (30 s)"


def test_save_from_a_rusty_steel_knurl_keeps_the_group_as_it_was(scene, loc):
    """Save as my material: 'what the group shows now becomes a material' – the group must not change."""
    from fresing_render.blender import material_picker as MP
    g = scene.fresing.groups[0]
    g.material = "knurl_diamond"
    g.fin_base = "STEEL"
    g.rust = 0.5
    g.wear = 0.2
    before = (g.material, round(g.rust, 3), round(g.wear, 3), g.fin_base)
    e = MP.save_from_group(bpy.context, g, "Rusty knurl", "", _mine(loc))
    assert (g.material, round(g.rust, 3), round(g.wear, 3), g.fin_base) == before, e.changes


def test_web3d_export_with_own_materials(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP, web3d
    from fresing_render.core import web3d as core
    s = scene.fresing
    assert len(s.groups) >= 2
    g0, g1 = s.groups[0], s.groups[1]
    g0.material, g0.color, g0.wear = "paint_satin", "RAL 5015", 0.3
    e0 = MP.save_from_group(bpy.context, g0, "Our blue", "", _mine(loc))
    mat = _shop_material()
    noise = mat.node_tree.nodes.new("ShaderNodeTexNoise")
    mat.node_tree.links.new(noise.outputs["Fac"], mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"])
    e1 = MP.save_from_blender(bpy.context, mat, "Shop red", "", _mine(loc), group=g1)
    assert g0.mat_key == e0.key and g1.mat_key == e1.key and g1.material == "blender_material"
    out = web3d.export(scene, str(tmp_path / "own.glb"), size=256, page=False)
    path = out.get("path") if isinstance(out, dict) else None
    path = path or str(tmp_path / "own.glb")
    data = open(path, "rb").read()
    assert core.problems(data) == []
    # the project is left as it was
    assert g1.material == "blender_material" and g1.mat_key == e1.key
    assert bpy.data.materials["FR " + g1.name].get("fr_material") == "blender_material"


def test_runner_command_and_picture_job(app, tmp_path, monkeypatch):
    from fresing_render.blender import material_picker as MP
    cmd, env = MP.runner_command(str(tmp_path / "job.json"))
    assert os.path.isfile(cmd[1] if cmd[0] != bpy.app.binary_path else MP.RUNNER)
    assert MP.RUNNER in cmd
    e = F.Entry(key="own:abcd1234", name="x", base="knurl_diamond", folder=str(tmp_path),
                changes=F.changes_of("knurl_diamond", finish={"size": 0.002}))
    item = MP.picture_item(e)
    assert item["out"].startswith(str(tmp_path)) and item["base"] == "knurl_diamond"
    json.dumps(item)
    e2 = F.Entry(key="own:abcd1234", name="x", base="paint_gloss", folder=str(tmp_path))
    assert F.rgb_of(MP.picture_item(e2)["changes"]["color"]) is not None


def test_chip_pixels_lower_right(app):
    """The colour chip goes into the lower right corner (Blender's rows run from the bottom)."""
    import numpy as np

    from fresing_render.blender import material_picker as MP
    pc = MP.previews()
    w, h = 40, 30
    src = pc.new("indep|src")
    src.image_size = (w, h)
    src.image_pixels_float.foreach_set(np.zeros(w * h * 4, np.float32))
    e = F.Entry(key="builtin:paint_satin", name="x", base="paint_satin", picture="/indep.png")
    MP._S["icons"][e.picture] = "indep|src"
    MP._S["chip_todo"][:] = [("indep|chip", e, (1.0, 0.0, 0.0))]
    try:
        MP._make_chips()
        assert "indep|chip" in pc
        px = np.empty(w * h * 4, np.float32)
        pc["indep|chip"].image_pixels_float.foreach_get(px)
        px = px.reshape(h, w, 4)
        n = max(8, int(min(w, h) * MP.CHIP))
        mid = n // 2
        assert tuple(px[mid, w - mid, :3]) == (1.0, 0.0, 0.0)            # lower right: the chip
        assert tuple(px[h - mid, mid, :3]) == (0.0, 0.0, 0.0)            # upper left: untouched
        assert tuple(px[h - mid, w - mid, :3]) == (0.0, 0.0, 0.0)        # upper right: untouched
    finally:
        MP._S["icons"].pop(e.picture, None)
        for k in ("indep|chip", "indep|src"):
            if k in pc:
                del pc[k]
