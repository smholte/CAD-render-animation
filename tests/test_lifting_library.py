"""Task 0190: the lifting equipment library (core/lifting_library.py) – files, versions, chart entry, sample mark."""

import json
import os

import pytest

from fresing_render.core import lifting
from fresing_render.core import lifting_library as L

C1_CHART = {"config": {"boom": 30.4, "counterweight": 40}, "radius": [8, 10, 12, 14],
            "capacity": [36.0, 29.5, 24.0, 20.0], "wind_max": 9.8}


def crane(name="Test crane", **extra):
    d = L.new_item("mobile_crane", "AT-100", name, charts=[json.loads(json.dumps(C1_CHART))],
                   hook_blocks=[{"name": "main", "mass": 0.85}], mass={"carrier": 30.0, "upper": 8.0},
                   cog={"carrier": [0.5, 0, 1.2], "upper": [0, 0, 2.0]}, source="invented test chart")
    d.update(extra)
    return d


def sling(name="Test sling", **extra):
    d = L.new_item("sling", "chain G8", name, wll={"straight": 8.0, "choke": 6.4})
    d.update(extra)
    return d


@pytest.fixture
def lib(tmp_path):
    return str(tmp_path / "library")


@pytest.fixture
def builtin(tmp_path):
    """A stand-in built-in folder with one sample crane (0191 ships the real ones)."""
    b = tmp_path / "builtin"
    (b / "AT-100").mkdir(parents=True)
    d = crane("AT-100", sample=True, source="invented sample – Fresing Render")
    (b / "AT-100" / "AT-100.json").write_text(json.dumps(d), encoding="utf-8")
    (b / "AT-100" / "AT-100.step").write_text("ISO-10303-21;", encoding="utf-8")
    (b / "AT-100" / "AT-100.png").write_bytes(b"\x89PNG")
    return str(b)


# --- format, read, write -------------------------------------------------------------------------------------------

def test_write_read_round_trip(lib):
    w = L.write_item(crane(), lib, builtin_folder=None)
    assert w.path == os.path.join(lib, "Test crane", "Test crane.json")
    item = L.read_item(os.path.dirname(w.path))
    assert item.ok, item.problems
    assert (item.kind, item.cls, item.name, item.sample) == ("mobile_crane", "AT-100", "Test crane", False)
    assert item.data["format"] == L.FORMAT and item.data["format_version"] == L.FORMAT_VERSION
    assert not [n for n in os.listdir(os.path.dirname(w.path)) if n.startswith(".tmp")]


def test_item_to_checks_c1_and_c4(lib):
    """lifting.crane_use / wll_use straight from a file (study 0180 C1 and C2 cases)."""
    L.write_item(crane(), lib, builtin_folder=None)
    L.write_item(sling(), lib, builtin_folder=None)
    items = {i.name: i for i in L.list_items(lib, None)}
    charts = L.charts_of(items["Test crane"])
    chart, _ = lifting.pick_chart(charts, boom=30.0)
    assert chart.config == {"boom": 30.4, "counterweight": 40000.0}
    (_, block), = L.hook_blocks_of(items["Test crane"])
    r = lifting.crane_use(lifting.kg(12.4), 11.3, chart, rigging=lifting.kg(0.35), hook_block=block)
    assert r.use == pytest.approx(13.6 / 24.0) and r.status == lifting.OK
    assert L.wll_of(items["Test sling"]) == pytest.approx(8000.0)
    assert L.wll_of(items["Test sling"], "choke") == pytest.approx(6400.0)
    r = lifting.wll_use(lifting.newton(6988.0), L.wll_of(items["Test sling"]))
    assert r.use == pytest.approx(0.8735, abs=1e-3) and r.status == lifting.OK  # rigging limit 90 %
    with pytest.raises(L.LibraryError, match="basket"):
        L.wll_of(items["Test sling"], "basket")


def test_units_feet_pounds_convert(lib):
    d = crane(units={"mass": "lb", "length": "ft"},
              charts=[{"config": {"boom": 100}, "radius": [20, 30], "capacity": [20000, 15000]}])
    c, = L.charts_of(L.from_data(d))
    assert c.radius[0] == pytest.approx(20 * 0.3048) and c.capacity[0] == pytest.approx(20000 * 0.45359237)
    assert c.config["boom"] == pytest.approx(30.48)


def test_writing_is_atomic_on_failure(lib, monkeypatch):
    w = L.write_item(crane(), lib, builtin_folder=None)
    before = open(w.path, encoding="utf-8").read()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(L.json, "dump", boom)
    with pytest.raises(OSError):
        L.write_item(crane(source="changed"), lib, builtin_folder=None)
    assert open(w.path, encoding="utf-8").read() == before
    assert os.listdir(os.path.dirname(w.path)) == ["Test crane.json"]


def test_never_writes_into_builtin(lib, builtin):
    item = L.read_item(os.path.join(builtin, "AT-100"), builtin=True)
    with pytest.raises(L.LibraryError, match="built-in"):
        L.write_item(item, lib, builtin_folder=builtin)
    with pytest.raises(L.LibraryError, match="built-in"):
        L.write_item(crane(), builtin, builtin_folder=builtin)
    with pytest.raises(L.LibraryError, match="built-in"):
        L.copy_item(item, builtin, "Mine", builtin_folder=builtin)
    with pytest.raises(L.LibraryError, match="built-in"):
        L.write_item(crane(), L.BUILTIN_DIR)


def test_unknown_fields_kept_and_named(lib):
    d = crane(colour="yellow", maker_notes={"a": 1})
    item = L.from_data(d)
    assert item.ok and any("colour" in n and "maker_notes" in n for n in item.notes)
    w = L.write_item(d, lib, builtin_folder=None)
    assert any("colour" in n for n in w.notes)
    back = json.load(open(w.path, encoding="utf-8"))
    assert back["colour"] == "yellow" and back["maker_notes"] == {"a": 1}


def test_newer_major_is_not_read(lib):
    d = crane(format_version="2.0")
    os.makedirs(os.path.join(lib, "New"))
    with open(os.path.join(lib, "New", "New.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    item = L.read_item(os.path.join(lib, "New"))
    assert item.newer and "newer Fresing Render" in item.problems[0] and "update the app" in item.problems[0]
    with pytest.raises(L.LibraryError, match="newer"):
        L.charts_of(item)
    with pytest.raises(L.LibraryError, match="newer"):
        L.write_item(item, lib, builtin_folder=None)


def test_newer_minor_is_read_with_note():
    item = L.from_data(crane(format_version="1.4", extra_1_4={"x": 1}))
    assert item.ok and not item.newer
    assert any("format 1.4" in n for n in item.notes)


def test_older_format_upgraded_in_memory_written_on_save(lib):
    d = crane(units=["t", "m"])
    del d["format_version"]
    os.makedirs(os.path.join(lib, "Old"))
    path = os.path.join(lib, "Old", "Old.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    raw = open(path, encoding="utf-8").read()
    item = L.read_item(os.path.dirname(path))
    assert item.ok and item.upgraded_from == "0" and item.data["units"] == {"mass": "t", "length": "m"}
    assert open(path, encoding="utf-8").read() == raw  # not written by reading
    w = L.write_item(item, lib, builtin_folder=None)
    back = json.load(open(w.path, encoding="utf-8"))
    assert back["format_version"] == "1.0" and back["units"] == {"mass": "t", "length": "m"}
    assert any("was 0" in n for n in w.notes)


# --- folders --------------------------------------------------------------------------------------------------------

def test_list_items_user_and_builtin_broken_never_stops(lib, builtin):
    L.write_item(crane("A crane"), lib, builtin_folder=None)
    broken = {
        "Bad json": "{not json",
        "Nan": '{"format": "fresing-lifting-equipment", "format_version": "1.0", "kind": "sling", "name": "x", '
               '"wll": NaN}',
        "Array": "[1, 2]",
        "Other format": '{"format": "something else"}',
    }
    for name, text in broken.items():
        os.makedirs(os.path.join(lib, name))
        with open(os.path.join(lib, name, name + ".json"), "w", encoding="utf-8") as fh:
            fh.write(text)
    os.makedirs(os.path.join(lib, "Empty folder"))
    os.makedirs(os.path.join(lib, ".hidden"))
    items = L.list_items(lib, builtin)
    names = [os.path.basename(i.folder) for i in items]
    assert names == ["A crane", "Array", "Bad json", "Empty folder", "Nan", "Other format", "AT-100"]
    by = dict(zip(names, items))
    assert by["A crane"].ok and not by["A crane"].builtin
    assert by["AT-100"].ok and by["AT-100"].builtin and by["AT-100"].sample
    assert by["AT-100"].model.endswith("AT-100.step") and by["AT-100"].picture.endswith("AT-100.png")
    assert "not valid JSON" in by["Bad json"].problems[0]
    assert "not valid JSON" in by["Nan"].problems[0]
    assert "not a JSON object" in by["Array"].problems[0]
    assert "Not a Fresing Render" in by["Other format"].problems[0]
    assert "No equipment file" in by["Empty folder"].problems[0]
    assert L.list_items(os.path.join(lib, "missing"), None) == []


@pytest.mark.parametrize("change, words", [
    ({"kind": ""}, "'kind' is missing"),
    ({"name": None}, "'name' is missing"),
    ({"units": {"mass": "stone", "length": "m"}}, "Unknown mass unit"),
    ({"units": {"mass": "t", "length": "yard"}}, "Unknown length unit"),
    ({"mass": -1}, "'mass'"),
    ({"cog": [1, 2]}, "'cog'"),
    ({"wll": 0}, "'wll'"),
    ({"hook_blocks": [{"name": "x"}]}, "'hook_blocks'"),
    ({"sample": "yes"}, "'sample'"),
    ({"charts": "none"}, "'charts' must be a list"),
    ({"charts": [5]}, "Chart 1: cannot be read"),
    ({"charts": [{"radius": "8", "capacity": [1]}]}, "Chart 1: 'radius' and 'capacity' must be lists"),
    ({"charts": [{"config": [1], "radius": [8], "capacity": [1]}]}, "'config'"),
    ({"charts": [{"radius": [8, 10], "capacity": [20, 25]}]}, "rises with the radius"),
    ({"charts": [{"radius": [8, 8], "capacity": [20, 15]}]}, "radii must rise"),
    ({"format_version": "one"}, "Unknown format version"),
    ({"charts": [{"config": {"boom": "twenty"}, "radius": [8], "capacity": [1]}]}, "'boom' in its configuration"),
    ({"units": 5}, "'units' must look like"),
])
def test_file_problems(change, words):
    d = crane()
    d.update(change)
    item = L.from_data(d)
    assert any(words in p for p in item.problems), item.problems
    with pytest.raises(L.LibraryError):
        L.charts_of(item)


def test_folder_names_work_on_windows():
    assert L.folder_name('AT/100: "big"?') == "AT_100_ _big__"
    assert L.folder_name("CON") == "CON_"
    assert L.folder_name("crane. ") == "crane"
    with pytest.raises(L.LibraryError):
        L.folder_name(" / ".replace("/", ""))


# --- sample mark ----------------------------------------------------------------------------------------------------

def test_sample_round_trip(lib, builtin):
    """Copy of a sample keeps the mark and the sample's hash; the mark comes off only with the user's own chart."""
    sample = L.read_item(os.path.join(builtin, "AT-100"))
    assert sample.builtin is False  # not inside BUILTIN_DIR: decided by place …
    sample = L.list_items(None, builtin)[0]  # … listed from the built-in folder it is
    with pytest.raises(L.LibraryError, match="built-in"):
        L.clear_sample(sample)
    copy = L.copy_item(sample, lib, "My AT-100", builtin_folder=builtin)
    assert copy.ok and copy.sample and copy.data["sample"] is True
    assert copy.data["derived_from"] == L.chart_hash(sample)
    assert copy.model.endswith("My AT-100.step") and copy.picture.endswith("My AT-100.png")
    with pytest.raises(L.LibraryError, match="still the sample's charts"):
        L.clear_sample(copy)
    # units changed but the same values: still the sample
    d = json.loads(json.dumps(copy.data))
    d["units"] = {"mass": "kg", "length": "m"}
    d["charts"][0]["capacity"] = [c * 1000 for c in d["charts"][0]["capacity"]]
    d["charts"][0]["config"]["counterweight"] = 40000
    assert L.chart_hash(d) == copy.data["derived_from"]
    # hand-edited "sample": false with the sample's charts: still sample, and not saved
    d["sample"] = False
    assert L.is_sample(d)
    with pytest.raises(L.LibraryError, match="still the sample's charts"):
        L.write_item(d, lib, builtin_folder=builtin)
    # the user's own chart
    entry = L.chart_csv("# boom 30.4 m; counterweight 40 t\n8;35\n10;28,5\n12;23\n14;19,5\n")
    assert entry.ok, entry.errors
    L.set_charts(copy.data, entry)
    assert copy.sample  # still marked until cleared
    assert "own" in L.clear_sample(copy)
    assert not copy.sample
    w = L.write_item(copy, lib, builtin_folder=builtin)
    again = L.read_item(os.path.dirname(w.path))
    assert again.ok and not again.sample and again.data["derived_from"] == L.chart_hash(sample)
    assert all(not c.sample for c in L.charts_of(again))
    assert all(c.sample for c in L.charts_of(sample))
    with pytest.raises(L.LibraryError, match="already in the library"):
        L.copy_item(sample, lib, "My AT-100", builtin_folder=builtin)


def test_builtin_without_mark_is_still_sample(builtin):
    p = os.path.join(builtin, "AT-100", "AT-100.json")
    d = json.load(open(p, encoding="utf-8"))
    d["sample"] = False
    json.dump(d, open(p, "w", encoding="utf-8"))
    item = L.list_items(None, builtin)[0]
    assert item.sample and any("treated as SAMPLE" in w for w in item.warnings)


def test_rigging_sample_hash_covers_wll(lib):
    d = sling(sample=True)
    item = L.from_data(d)
    os.makedirs(lib)
    copy_src = L.read_item(os.path.dirname(L.write_item(d, lib, builtin_folder=None).path))
    copy = L.copy_item(copy_src, lib, "Sling copy", builtin_folder=None)
    with pytest.raises(L.LibraryError):
        L.clear_sample(copy)
    copy.data["wll"]["straight"] = 10.0
    L.clear_sample(copy)
    assert not copy.sample and item.sample


# --- chart entry ----------------------------------------------------------------------------------------------------

B30 = {"boom": 30}


@pytest.mark.parametrize("rows, words", [
    ([(B30, 8, 30), (B30, 8, 25)], "Row 2: radii must rise"),
    ([(B30, 10, 30), (B30, 8, 35)], "Row 2: radii must rise"),
    ([(B30, 8, 30), (B30, 10, 0)], "Row 2: the capacity must be above 0"),
    ([(B30, 8, -3)], "Row 1: the capacity must be above 0"),
    ([(B30, 8, "heavy")], "Row 1: the capacity must be a number"),
    ([(B30, 0, 30)], "Row 1: the radius must be a number above 0"),
    ([(B30, "", 30)], "Row 1: the radius must be a number above 0"),
    ([(B30, 8, 30), (B30, 10, 31)], "Row 2: the capacity rises with the radius"),
    ([(B30, 8, 30), (B30, 10, None), (B30, 12, 31)], "Row 3: the capacity rises with the radius"),
    ([({"hs": 1.0}, 8, 30), ({"hs": 1.0}, 10, 25), ({"hs": 2.0}, 8, 28), ({"hs": 2.0}, 10, 26)],
     "Rows 2, 4: at 10 m the column for Hs 2 m holds more"),
    ([(B30, 8, None)], "has no capacity at all"),
    ([(B30, 8)], "Row 1: give a configuration"),
    ([("boom 30", 8, 30)], "Row 1: the configuration"),
    ([], "no rows"),
])
def test_entry_refusals(rows, words):
    e = L.chart_rows(rows)
    assert not e.ok and any(words in m for m in e.errors), e.errors
    with pytest.raises(L.LibraryError, match="not taken"):
        L.set_charts(crane(), e)


def test_entry_boom_warning_and_gaps():
    e = L.chart_rows([({"boom": 20}, 8, 30), ({"boom": 20}, 10, None), ({"boom": 20}, 12, 20),
                      ({"boom": 30}, 8, 31), ({"boom": 30}, 12, 18)])
    assert e.ok and len(e.warnings) == 1 and "Rows 1, 4" in e.warnings[0] and "30 m boom holds more" in e.warnings[0]
    c20, _ = lifting.pick_chart(e.charts, boom=20)
    assert c20.capacity == [30000.0, None, 20000.0]
    assert lifting.lookup(c20, 9.0).capacity is None and "gap" in lifting.lookup(c20, 9.0).reason
    d = L.set_charts(crane(), e)
    assert d["charts"][0]["capacity"] == [30.0, None, 20.0]
    assert L.from_data(d).ok


def test_csv_decimal_comma_header_units_and_configs():
    text = ("﻿radius (ft);capacity (lb)\n"
            "# boom 100 ft; counterweight 20000 lb\n"
            "20;40.000,5\n"
            "30;30000\n"
            "\n"
            "// a comment\n"
            "boom=120 ft;Hs 1,5\n"
            "20;35000\n"
            "30;-\n"
            "40;20000\n")
    e = L.chart_csv(text)
    assert e.ok, e.errors
    a, b = e.charts
    assert a.radius == pytest.approx([6.096, 9.144])
    assert a.capacity[0] == pytest.approx(40000.5 * 0.45359237)
    assert a.config["boom"] == pytest.approx(30.48) and a.config["counterweight"] == pytest.approx(9071.8474)
    assert b.config["hs"] == pytest.approx(1.5) and b.capacity[1] is None
    assert e.lines == [[3, 4], [8, 9, 10]]


def test_csv_comma_separated_point_decimals_and_cell_units():
    e = L.chart_csv("radius,capacity\n8,36.0\n10 m,29500 kg\n12,24\n", mass_unit="t")
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500, 24000])
    assert e.charts[0].config == {}


@pytest.mark.parametrize("text, words", [
    ("8;36\n10;38\n", "Line 2: the capacity rises with the radius (38 t after 36 t in line 1)"),
    ("radius;capacity\n8;36\n8;30\n", "Line 3: radii must rise"),
    ("8;36;5\n", "Line 1: two columns expected"),
    ("8;lots\n", "Line 1: the radius and capacity must be numbers"),
    ("radius (yd);capacity\n8;36\n", "Line 1: unknown length unit"),
    ("# boom thirty\n8;36\n", "Line 1: cannot read the configuration"),
    ("", "empty"),
])
def test_csv_refusals(text, words):
    e = L.chart_csv(text)
    assert not e.ok and any(words in m for m in e.errors), e.errors


def test_read_chart_csv_windows_file(tmp_path):
    p = tmp_path / "chart.csv"
    p.write_bytes("# boom 30,4 m\r\nradius (m);capacity (t)\r\n8;36,0\r\n10;29,5\r\n".encode("cp1252"))
    e = L.read_chart_csv(str(p))
    assert e.ok and e.charts[0].capacity == pytest.approx([36000, 29500])


# --- built-ins (0191) -----------------------------------------------------------------------------------------------

def test_every_builtin_reads_without_problems():
    items = L.list_items(None)  # none until task 0191 ships them (no skip: a pytest group allows one skip only)
    assert items or not os.path.isdir(L.BUILTIN_DIR)
    for item in items:
        assert item.ok, (item.folder, item.problems)
        assert item.builtin and item.sample and item.model, item.folder
        L.charts_of(item)
