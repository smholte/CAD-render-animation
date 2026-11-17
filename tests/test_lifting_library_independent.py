"""Independent tests of ``fresing_render/core/lifting_library.py`` (task 0190).

Written from the brief of task 0190, study 0180 section 4 and the public API list only, by an agent that did not read
the module first. They try to break it: refusals, CSV variants, broken files, versions, the sample mark, and the
checks of ``core/lifting.py`` run straight from a file. Invented charts only.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re

import pytest

from fresing_render.core import lifting as L
from fresing_render.core import lifting_library as LL

G = 9.80665

# The study's C1 chart (invented): 8 m 36.0 t, 10 m 29.5 t, 12 m 24.0 t, 14 m 20.0 t.
RADII = [8.0, 10.0, 12.0, 14.0]
CAPS_T = [36.0, 29.5, 24.0, 20.0]


def chart_dict(boom=20.0, counterweight=10.0, radius=None, capacity=None, **kw):
    d = {"config": {"boom": boom, "counterweight": counterweight}, "radius": list(radius or RADII),
         "capacity": list(capacity or CAPS_T), "wind_max": 9.0, "includes_hook_block": False, "interpolate": False}
    d.update(kw)
    return d


def crane(name="Test crane", charts=None, **kw):
    return LL.new_item("mobile_crane", "AT-40", name, charts=charts if charts is not None else [chart_dict()],
                       hook_blocks=[{"name": "Block 40 t", "mass": 0.85}], **kw)


def sling(name="Test sling", wll=8.0, **kw):
    return LL.new_item("sling", "chain sling", name, wll=wll, **kw)


def write_json(path, data, raw=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw if raw is not None else json.dumps(data))
    return path


def builtin_lib(tmp_path, name="Sample crane"):
    """A built-in folder as 0191 would ship it: sample true, a model and a picture."""
    folder = tmp_path / "builtin"
    d = crane(name)
    d["sample"] = True
    write_json(str(folder / name / f"{name}.json"), d)
    (folder / name / f"{name}.step").write_text("ISO-10303-21; invented")
    (folder / name / f"{name}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return folder


def text(msgs):
    return " | ".join(str(m) for m in msgs)


# ---------------------------------------------------------------------------------------------------------------------
# Constants and new items

def test_constants():
    assert LL.FORMAT == "fresing-lifting-equipment"
    assert LL.FORMAT_VERSION == "1.0"
    assert issubclass(LL.LibraryError, ValueError)
    for ext in (".step", ".glb", ".obj", ".fbx"):
        assert ext in [e.lower() for e in LL.MODEL_EXTS]
    assert any(e.lower() in (".png", ".jpg", ".jpeg") for e in LL.PICTURE_EXTS)


def test_new_item_fields_and_valid():
    d = crane()
    assert d["format"] == LL.FORMAT and d["format_version"] == "1.0"
    assert d["kind"] == "mobile_crane" and d["class"] == "AT-40" and d["name"] == "Test crane"
    assert d["units"] == {"mass": "t", "length": "m"}
    json.dumps(d, allow_nan=False)  # plain JSON
    it = LL.from_data(d)
    assert it.ok, it.problems
    assert (it.kind, it.cls, it.name) == ("mobile_crane", "AT-40", "Test crane")
    assert not it.sample and not LL.is_sample(it)


def test_new_item_other_units():
    d = LL.new_item("mobile_crane", "AT-40", "Imperial", mass_unit="lb", length_unit="ft",
                    charts=[chart_dict(boom=65.0, counterweight=20000.0, radius=[26.0, 33.0],
                                       capacity=[80000.0, 65000.0])])
    assert d["units"] == {"mass": "lb", "length": "ft"}
    ch = LL.charts_of(d)[0]
    assert ch.radius == pytest.approx([26.0 * 0.3048, 33.0 * 0.3048])
    assert ch.capacity == pytest.approx([80000.0 * 0.45359237, 65000.0 * 0.45359237])
    assert ch.config["boom"] == pytest.approx(65.0 * 0.3048)
    assert ch.config["counterweight"] == pytest.approx(20000.0 * 0.45359237)


# ---------------------------------------------------------------------------------------------------------------------
# Item -> checks (SI), C1 and C2 straight from a file

def test_charts_of_si_and_hs_stays_metres():
    d = LL.new_item("offshore_crane", "OP-50", "Sea crane", mass_unit="kg", length_unit="ft",
                    charts=[{"config": {"hs": 1.5}, "radius": [30.0, 40.0], "capacity": [20000.0, 15000.0]},
                            {"config": {"hs": 2.5}, "radius": [30.0, 40.0], "capacity": [16000.0, 12000.0]}])
    it = LL.from_data(d)
    assert it.ok, it.problems
    chs = LL.charts_of(it)
    assert all(isinstance(c, L.Chart) for c in chs)
    assert sorted(c.config["hs"] for c in chs) == pytest.approx([1.5, 2.5])  # hs is metres in any length unit
    assert chs[0].radius == pytest.approx([30 * 0.3048, 40 * 0.3048])
    assert chs[0].capacity == pytest.approx([20000.0, 15000.0])


def test_c1_crane_use_from_file(tmp_path):
    w = LL.write_item(crane(), str(tmp_path / "lib"))
    it = LL.read_item(w.path)
    assert it.ok, it.problems
    chart = LL.charts_of(it)[0]
    blocks = LL.hook_blocks_of(it)
    assert blocks[0][0] == "Block 40 t" and blocks[0][1] == pytest.approx(850.0)
    r = L.crane_use(12400, 11.3, chart, rigging=350, hook_block=blocks[0][1])
    assert r.use * 100 == pytest.approx(56.7, abs=0.05)
    assert r.limit == pytest.approx(24000.0)


def test_c1_same_from_lb_ft_file(tmp_path):
    lb, ft = 0.45359237, 0.3048
    d = LL.new_item("mobile_crane", "AT-40", "Imperial crane", mass_unit="lb", length_unit="ft",
                    charts=[chart_dict(boom=20 / ft, counterweight=10000 / lb, radius=[r / ft for r in RADII],
                                       capacity=[c * 1000 / lb for c in CAPS_T])],
                    hook_blocks=[{"name": "Block", "mass": 850 / lb}])
    w = LL.write_item(d, str(tmp_path / "lib"))
    it = LL.read_item(w.path)
    assert it.ok, it.problems
    chart = LL.charts_of(it)[0]
    r = L.crane_use(12400, 11.3, chart, rigging=350, hook_block=LL.hook_blocks_of(it)[0][1])
    assert r.use * 100 == pytest.approx(56.7, abs=0.05)
    # radius 12 m exactly must still be the 12 m row after the ft round trip (no float noise pushing it to 14 m)
    assert L.lookup(chart, 12.0).capacity == pytest.approx(24000.0, rel=1e-6)


def test_c1_includes_hook_block_from_file():
    d = crane(charts=[chart_dict(includes_hook_block=True)])
    chart = LL.charts_of(d)[0]
    assert chart.includes_hook_block
    r = L.crane_use(12400, 11.3, chart, rigging=350, hook_block=850)
    assert r.use * 100 == pytest.approx(12750 / 24000 * 100, abs=0.05)


def test_c2_wll_use_from_file(tmp_path):
    w = LL.write_item(sling(), str(tmp_path / "lib"))
    it = LL.read_item(w.path)
    assert it.ok, it.problems
    wll = LL.wll_of(it)
    assert wll == pytest.approx(8000.0)
    leg = L.two_leg(10000, (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (1.5, 0.0, 3.0)).details["force"][0]
    r = L.wll_use(leg, wll)
    assert r.use * 100 == pytest.approx(87.3, abs=0.05)


def test_wll_by_use_and_units():
    d = sling(wll={"straight": 8.0, "choke": 6.4})
    assert LL.wll_of(d, "straight") == pytest.approx(8000.0)
    assert LL.wll_of(d, "choke") == pytest.approx(6400.0)
    assert LL.wll_of(d) == pytest.approx(8000.0)  # no use given: the straight pull
    d2 = LL.new_item("shackle", "bow shackle", "Shackle", mass_unit="lb", wll=18740.0)
    assert LL.wll_of(d2) == pytest.approx(18740.0 * 0.45359237)
    assert LL.wll_of(crane()) is None


def test_hook_blocks_in_lb():
    d = LL.new_item("mobile_crane", "AT-40", "Imperial", mass_unit="lb", length_unit="ft",
                    charts=[chart_dict(radius=[30.0, 40.0], capacity=[50000.0, 40000.0])],
                    hook_blocks=[{"name": "B", "mass": 2000.0}])
    assert LL.hook_blocks_of(LL.from_data(d)) == [("B", pytest.approx(2000.0 * 0.45359237))]


def test_gap_in_file_is_not_allowed_there():
    d = crane(charts=[chart_dict(capacity=[36.0, 29.5, None, 20.0])])
    it = LL.from_data(d)
    assert it.ok, it.problems
    chart = LL.charts_of(it)[0]
    assert chart.capacity[2] is None
    lk = L.lookup(chart, 11.3)
    assert lk.capacity is None and "not allowed" in lk.reason


# ---------------------------------------------------------------------------------------------------------------------
# Chart entry – table rows

A = {"boom": 20.0}
B = {"boom": 30.0}

REFUSED = [
    # name, rows, row number the message must name
    ("radii equal", [(A, 8, 30), (A, 10, 25), (B, 8, 28), (B, 8, 20)], 4),
    ("radii falling", [(A, 10, 30), (A, 8, 35)], 2),
    ("capacity zero", [(A, 8, 30), (A, 10, 0)], 2),
    ("capacity negative", [(A, 8, 30), (A, 10, -5)], 2),
    ("capacity text", [(A, 8, 30), (A, 10, "abc")], 2),
    ("capacity NaN", [(A, 8, 30), (A, 10, float("nan"))], 2),
    ("capacity infinite", [(A, 8, 30), (A, 10, float("inf"))], 2),
    ("radius negative", [(A, -2, 30), (A, 10, 25)], 1),
    ("radius text", [(A, 8, 30), (A, "far", 25)], 2),
    ("capacity rising with radius", [(A, 8, 30), (A, 10, 25), (A, 12, 27)], 3),
    ("rising after a gap", [(A, 8, 30), (A, 10, None), (A, 12, 31)], 3),
    ("sea column above calmer", [({"hs": 1.0}, 10, 20), ({"hs": 1.0}, 12, 18),
                                 ({"hs": 2.0}, 10, 22), ({"hs": 2.0}, 12, 17)], 3),
]


@pytest.mark.parametrize("name,rows,row", REFUSED, ids=[r[0] for r in REFUSED])
def test_chart_rows_refused(name, rows, row):
    e = LL.chart_rows(rows)
    assert not e.ok
    assert e.errors
    # "row 4" or "rows 1, 4": the offending row's number must be named in a row phrase
    assert re.search(rf"\brows? (\d+, )*{row}\b", text(e.errors).lower()), e.errors


def test_chart_rows_warns_longer_boom_holding_more():
    e = LL.chart_rows([(A, 10, 20), (A, 12, 18), (B, 10, 22), (B, 12, 17)])
    assert e.ok, e.errors
    assert e.warnings
    assert len(e.charts) == 2


def test_chart_rows_good_and_gap():
    e = LL.chart_rows([(A, 8, 36), (A, 10, 29.5), (A, 12, None), (A, 14, ""), (A, 16, 18)])
    assert e.ok, e.errors
    ch = e.charts[0]
    assert ch.radius == pytest.approx([8, 10, 12, 14, 16])
    assert ch.capacity[:2] == pytest.approx([36000, 29500])
    assert ch.capacity[2] is None and ch.capacity[3] is None
    assert ch.config["boom"] == pytest.approx(20.0)


def test_chart_rows_units():
    e = LL.chart_rows([({"boom": 100.0, "counterweight": 20000.0, "hs": 1.5}, 30, 50000),
                       ({"boom": 100.0, "counterweight": 20000.0, "hs": 1.5}, 40, 40000)],
                      mass_unit="lb", length_unit="ft")
    assert e.ok, e.errors
    ch = e.charts[0]
    assert ch.radius == pytest.approx([30 * 0.3048, 40 * 0.3048])
    assert ch.capacity == pytest.approx([50000 * 0.45359237, 40000 * 0.45359237])
    assert ch.config["boom"] == pytest.approx(100 * 0.3048)
    assert ch.config["counterweight"] == pytest.approx(20000 * 0.45359237)
    assert ch.config["hs"] == pytest.approx(1.5)
    back = e.dicts("lb", "ft")
    assert back[0]["radius"] == pytest.approx([30, 40])
    assert back[0]["capacity"] == pytest.approx([50000, 40000])
    assert back[0]["config"]["boom"] == pytest.approx(100.0)


def test_chart_rows_rows_unordered_by_config_kept_apart():
    # rows of two configurations mixed: each configuration is its own chart
    e = LL.chart_rows([(A, 8, 36), (B, 8, 30), (A, 10, 29), (B, 10, 25)])
    assert e.ok, e.errors
    assert sorted(c.config["boom"] for c in e.charts) == [20.0, 30.0]


# ---------------------------------------------------------------------------------------------------------------------
# Chart entry – CSV

def test_csv_semicolon_decimal_comma():
    e = LL.chart_csv("boom 20 m; counterweight 10 t\nradius;capacity\n8;36,0\n10;29,5\n12,5;24\n")
    assert e.ok, e.errors
    ch = e.charts[0]
    assert ch.radius == pytest.approx([8, 10, 12.5])
    assert ch.capacity == pytest.approx([36000, 29500, 24000])
    assert ch.config["boom"] == pytest.approx(20.0)
    assert ch.config["counterweight"] == pytest.approx(10000.0)


def test_csv_comma_decimal_point():
    e = LL.chart_csv("radius,capacity\n8,36.0\n10,29.5\n")
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_csv_tab():
    e = LL.chart_csv("8\t36,0\n10\t29.5\n")
    assert e.ok, e.errors
    assert e.charts[0].radius == pytest.approx([8, 10])
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_csv_header_sets_units_ft_lb():
    e = LL.chart_csv("radius (ft);capacity (lb)\n10;2000\n20;1500\n")
    assert e.ok, e.errors
    assert e.charts[0].radius == pytest.approx([3.048, 6.096])
    assert e.charts[0].capacity == pytest.approx([2000 * 0.45359237, 1500 * 0.45359237])


def test_csv_kg_argument():
    e = LL.chart_csv("8;36000\n10;29500\n", mass_unit="kg")
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_csv_header_kg():
    e = LL.chart_csv("radius (m);capacity (kg)\n8;36000\n10;29500\n")
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_csv_several_configurations_and_gap():
    csv = ("boom 20 m; counterweight 10 t\n"
           "radius;capacity\n"
           "8;36\n10;29,5\n12;\n14;20\n"
           "\n"
           "boom 30.4 m; counterweight 10 t\n"
           "radius;capacity\n"
           "8;30\n10;25\n12;21\n14;18\n")
    e = LL.chart_csv(csv)
    assert e.ok, e.errors
    assert len(e.charts) == 2
    by_boom = {round(c.config["boom"], 3): c for c in e.charts}
    assert set(by_boom) == {20.0, 30.4}
    assert by_boom[20.0].capacity[2] is None
    assert by_boom[30.4].capacity == pytest.approx([30000, 25000, 21000, 18000])
    lk = L.lookup(by_boom[20.0], 11.0)
    assert lk.capacity is None and "not allowed" in lk.reason


def test_csv_crlf_bom_and_blank_lines():
    e = LL.chart_csv("﻿radius;capacity\r\n\r\n8;36\r\n10;29,5\r\n")
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_csv_errors_name_the_line():
    e = LL.chart_csv("boom 20 m\nradius;capacity\n8;30\n10;35\n")
    assert not e.ok
    assert "line 4" in text(e.errors).lower(), e.errors
    e2 = LL.chart_csv("8;30\n10;0\n")
    assert not e2.ok and "line 2" in text(e2.errors).lower(), e2.errors
    e3 = LL.chart_csv("8;30\n8;25\n")
    assert not e3.ok and "line 2" in text(e3.errors).lower(), e3.errors


def test_csv_sea_column_refused():
    csv = "hs 1.0 m\n10;20\n12;18\nhs 2.0 m\n10;22\n12;17\n"
    e = LL.chart_csv(csv)
    assert not e.ok, e.charts
    assert "line" in text(e.errors).lower()


def test_csv_boom_warning_only():
    csv = "boom 20 m\n10;20\n12;18\nboom 30 m\n10;22\n12;17\n"
    e = LL.chart_csv(csv)
    assert e.ok, e.errors
    assert e.warnings


def test_csv_extra_column_or_garbage_number():
    e = LL.chart_csv("8;30\n10;2x5\n")
    assert not e.ok
    assert "line 2" in text(e.errors).lower(), e.errors


def test_csv_empty_text():
    e = LL.chart_csv("")
    assert not e.ok and e.errors


def test_read_chart_csv_file(tmp_path):
    p = tmp_path / "chart.csv"
    p.write_text("boom 20 m; counterweight 10 t\nradius;capacity\n8;36,0\n10;29,5\n", encoding="utf-8")
    e = LL.read_chart_csv(str(p))
    assert e.ok, e.errors
    assert e.charts[0].capacity == pytest.approx([36000, 29500])


def test_set_charts_into_item_in_other_units():
    d = LL.new_item("mobile_crane", "AT-40", "Kilo crane", mass_unit="kg", length_unit="mm")
    e = LL.chart_csv("boom 20 m; counterweight 10 t\n8;36\n10;29,5\n12;24\n14;20\n")
    assert e.ok, e.errors
    LL.set_charts(d, e)
    it = LL.from_data(d)
    assert it.ok, it.problems
    ch = LL.charts_of(it)[0]
    assert ch.radius == pytest.approx(RADII)
    assert ch.capacity == pytest.approx([c * 1000 for c in CAPS_T])
    assert ch.config["boom"] == pytest.approx(20.0)
    # stored in the file's own units
    assert d["charts"][0]["radius"][0] == pytest.approx(8000.0)
    assert d["charts"][0]["capacity"][0] == pytest.approx(36000.0)


def test_set_charts_refuses_entry_with_errors():
    d = crane()
    e = LL.chart_csv("8;30\n10;35\n")
    with pytest.raises(LL.LibraryError):
        LL.set_charts(d, e)


# ---------------------------------------------------------------------------------------------------------------------
# Writing

def test_write_layout_and_atomic(tmp_path):
    lib = tmp_path / "lib"
    w = LL.write_item(crane("Test crane"), str(lib))
    assert os.path.normpath(w.path) == os.path.normpath(str(lib / "Test crane" / "Test crane.json"))
    assert sorted(os.listdir(lib / "Test crane")) == ["Test crane.json"]  # no temp file left
    data = json.loads((lib / "Test crane" / "Test crane.json").read_text(encoding="utf-8"))
    assert data["format"] == LL.FORMAT and data["format_version"] == "1.0"
    # writing again replaces
    d = crane("Test crane", charts=[chart_dict(capacity=[35.0, 29.5, 24.0, 20.0])])
    LL.write_item(d, str(lib))
    assert sorted(os.listdir(lib / "Test crane")) == ["Test crane.json"]
    assert LL.charts_of(LL.read_item(str(lib / "Test crane")))[0].capacity[0] == pytest.approx(35000)


def test_write_refuses_builtin_folder(tmp_path):
    bf = builtin_lib(tmp_path)
    before = sorted(os.listdir(bf))
    with pytest.raises(LL.LibraryError):
        LL.write_item(crane("New one"), str(bf), builtin_folder=str(bf))
    with pytest.raises(LL.LibraryError):
        LL.write_item(crane("New one"), str(bf / "Sample crane"), builtin_folder=str(bf))
    assert sorted(os.listdir(bf)) == before


def test_write_refuses_builtin_item(tmp_path):
    bf = builtin_lib(tmp_path)
    items = LL.list_items(None, builtin_folder=str(bf))
    assert len(items) == 1 and items[0].builtin
    with pytest.raises(LL.LibraryError):
        LL.write_item(items[0], str(tmp_path / "lib"), builtin_folder=str(bf))


def test_write_refuses_problems(tmp_path):
    d = crane(charts=[chart_dict(capacity=[36.0, 37.0, 24.0, 20.0])])
    with pytest.raises(LL.LibraryError):
        LL.write_item(d, str(tmp_path / "lib"))
    assert not (tmp_path / "lib" / "Test crane" / "Test crane.json").exists()


def test_write_refuses_newer_major(tmp_path):
    d = crane()
    d["format_version"] = "2.0"
    with pytest.raises(LL.LibraryError):
        LL.write_item(d, str(tmp_path / "lib"))


def test_write_name_cannot_escape_library(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    for bad in ("../evil", "a/b", "..", "", "   "):
        try:
            LL.write_item(crane(bad), str(lib))
        except LL.LibraryError:
            pass
    assert sorted(os.listdir(tmp_path)) == ["lib"]
    for root, _dirs, files in os.walk(lib):
        for f in files:
            assert os.path.commonpath([os.path.realpath(os.path.join(root, f)), os.path.realpath(lib)]) \
                == os.path.realpath(lib)


def test_unknown_fields_kept_and_noted(tmp_path):
    d = crane()
    d["my_note"] = {"who": "tester"}
    d["charts"][0]["my_chart_note"] = "from page 3"
    w = LL.write_item(d, str(tmp_path / "lib"))
    assert "my_note" in text(w.notes)
    data = json.loads(open(w.path, encoding="utf-8").read())
    assert data["my_note"] == {"who": "tester"}
    assert data["charts"][0].get("my_chart_note") == "from page 3"
    it = LL.read_item(w.path)
    assert it.ok, it.problems
    assert "my_note" in text(it.notes)


def test_write_is_strict_json(tmp_path):
    w = LL.write_item(crane(charts=[chart_dict(capacity=[36.0, None, 24.0, 20.0])]), str(tmp_path / "lib"))
    raw = open(w.path, encoding="utf-8").read()
    assert "NaN" not in raw and "Infinity" not in raw
    assert json.loads(raw)["charts"][0]["capacity"][1] is None


# ---------------------------------------------------------------------------------------------------------------------
# Reading broken items, listing

BROKEN = {
    "bad json": "{ not json",
    "nan": json.dumps(crane("nan")).replace('"wind_max": 9.0', '"wind_max": NaN'),
    "not an object": "[1, 2, 3]",
    "wrong format": json.dumps(dict(crane("wrong format"), format="something-else")),
    "no kind": json.dumps({k: v for k, v in crane("no kind").items() if k != "kind"}),
    "no name": json.dumps({k: v for k, v in crane("no name").items() if k != "name"}),
    "bad units": json.dumps(dict(crane("bad units"), units={"mass": "stone", "length": "m"})),
    "units not a dict": json.dumps(dict(crane("units text"), units=5)),
    "broken chart": json.dumps(crane("broken chart", charts=[chart_dict(capacity=[36.0, 40.0, 24.0, 20.0])])),
    "chart lengths differ": json.dumps(crane("lengths", charts=[chart_dict(capacity=[36.0, 29.5])])),
    "charts not a list": json.dumps(dict(crane("charts dict"), charts={"a": 1})),
    "radius strings": json.dumps(crane("strings", charts=[chart_dict(radius=["8", "10", "12", "14"])])),
    "empty file": "",
}


@pytest.mark.parametrize("name", list(BROKEN))
def test_read_broken_item_never_raises(tmp_path, name):
    p = write_json(str(tmp_path / "lib" / name / f"{name}.json"), None, raw=BROKEN[name])
    it = LL.read_item(p)
    assert it.problems, f"{name}: no problem reported"
    assert not it.ok
    assert all(isinstance(m, str) and m.strip() for m in it.problems)


def test_read_non_utf8_and_missing(tmp_path):
    p = tmp_path / "lib" / "x" / "x.json"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"\xff\xfe\x00{garbage")
    assert LL.read_item(str(p)).problems
    assert LL.read_item(str(tmp_path / "nowhere" / "nothing.json")).problems
    empty = tmp_path / "lib" / "empty"
    empty.mkdir()
    assert LL.read_item(str(empty)).problems


def test_read_folder_or_json_same(tmp_path):
    w = LL.write_item(crane(), str(tmp_path / "lib"))
    a, b = LL.read_item(w.path), LL.read_item(os.path.dirname(w.path))
    assert a.ok and b.ok
    assert a.name == b.name == "Test crane"
    assert os.path.normpath(a.folder) == os.path.normpath(b.folder)


def test_model_and_picture_found(tmp_path):
    w = LL.write_item(crane(), str(tmp_path / "lib"))
    folder = os.path.dirname(w.path)
    open(os.path.join(folder, "Test crane.glb"), "wb").close()
    open(os.path.join(folder, "Test crane.jpg"), "wb").close()
    it = LL.read_item(folder)
    assert it.model and it.model.lower().endswith(".glb")
    assert it.picture and it.picture.lower().endswith(".jpg")


def test_list_items_user_then_builtin_and_broken(tmp_path):
    bf = builtin_lib(tmp_path)
    lib = tmp_path / "lib"
    LL.write_item(crane("Mine"), str(lib))
    LL.write_item(sling("My sling"), str(lib))
    for name, raw in (("bad json", BROKEN["bad json"]), ("not an object", BROKEN["not an object"]),
                      ("nan", BROKEN["nan"])):
        write_json(str(lib / name / f"{name}.json"), None, raw=raw)
    (lib / "stray.txt").write_text("not an item")
    items = LL.list_items(str(lib), builtin_folder=str(bf))
    assert len(items) == 6
    assert [it.builtin for it in items] == [False] * 5 + [True]
    assert items[-1].sample and LL.is_sample(items[-1])
    good = [it for it in items if it.ok]
    assert sorted(it.name for it in good) == ["Mine", "My sling", "Sample crane"]
    assert sum(1 for it in items if it.problems) == 3


def test_list_items_missing_folders(tmp_path):
    assert LL.list_items(str(tmp_path / "nope"), builtin_folder=str(tmp_path / "nope2")) == []
    assert LL.list_items(None, builtin_folder=str(tmp_path / "nope2")) == []


def test_list_items_default_builtin_does_not_raise():
    LL.list_items(None)  # BUILTIN_DIR may not exist yet


def test_validate_duplicate_configuration():
    it = LL.validate(crane(charts=[chart_dict(), chart_dict()]))
    assert not it.ok and it.problems


def test_validate_boom_warning_is_not_a_problem():
    it = LL.validate(crane(charts=[chart_dict(boom=20.0, capacity=[36.0, 29.5, 24.0, 20.0]),
                                   chart_dict(boom=30.0, capacity=[36.0, 30.0, 24.0, 20.0])]))
    assert it.ok, it.problems
    assert it.warnings


# ---------------------------------------------------------------------------------------------------------------------
# Versions

def test_same_major_newer_minor_reads(tmp_path):
    d = crane()
    d["format_version"] = "1.7"
    d["future_field"] = [1, 2]
    p = write_json(str(tmp_path / "lib" / "Test crane" / "Test crane.json"), d)
    it = LL.read_item(p)
    assert it.ok, it.problems
    assert not it.newer
    assert "future_field" in text(it.notes)
    assert LL.charts_of(it)[0].capacity[0] == pytest.approx(36000)


def test_newer_major_no_checks(tmp_path):
    d = crane(charts=[chart_dict(capacity=[36.0, 40.0, 24.0, 20.0])])  # broken chart: must not be checked
    d["format_version"] = "2.0"
    d["units"] = "whatever 2.0 does"
    p = write_json(str(tmp_path / "lib" / "Test crane" / "Test crane.json"), d)
    it = LL.read_item(p)
    assert it.newer
    assert not it.ok
    assert len(it.problems) == 1, it.problems
    msg = it.problems[0].lower()
    assert "newer" in msg and "update" in msg
    with pytest.raises(LL.LibraryError):
        LL.charts_of(it)
    items = LL.list_items(str(tmp_path / "lib"), builtin_folder=str(tmp_path / "none"))
    assert len(items) == 1 and items[0].newer


def test_garbage_version_is_a_problem():
    d = crane()
    d["format_version"] = "one point oh"
    assert LL.from_data(d).problems


def test_older_format_upgraded_in_memory_only(tmp_path):
    d = crane("Old crane")
    del d["format_version"]
    d["units"] = ["t", "m"]
    p = write_json(str(tmp_path / "lib" / "Old crane" / "Old crane.json"), d)
    raw = open(p, "rb").read()
    it = LL.read_item(p)
    assert it.ok, it.problems
    assert it.upgraded_from is not None
    assert it.data["units"] == {"mass": "t", "length": "m"}
    assert LL.charts_of(it)[0].capacity == pytest.approx([c * 1000 for c in CAPS_T])
    assert open(p, "rb").read() == raw  # untouched until saved
    LL.write_item(it, str(tmp_path / "lib"))
    data = json.loads(open(p, encoding="utf-8").read())
    assert data["format_version"] == "1.0"
    assert data["units"] == {"mass": "t", "length": "m"}
    again = LL.read_item(p)
    assert again.ok and not again.upgraded_from


def test_older_format_kg_ft_list_units():
    d = LL.new_item("mobile_crane", "AT-40", "Old imperial",
                    charts=[chart_dict(radius=[30.0, 40.0], capacity=[30000.0, 20000.0], boom=100.0,
                                       counterweight=5000.0)])
    del d["format_version"]
    d["units"] = ["kg", "ft"]
    it = LL.from_data(d)
    assert it.ok, it.problems
    ch = LL.charts_of(it)[0]
    assert ch.radius == pytest.approx([30 * 0.3048, 40 * 0.3048])
    assert ch.capacity == pytest.approx([30000.0, 20000.0])


# ---------------------------------------------------------------------------------------------------------------------
# Sample mark, hash, copy

def test_chart_hash_units_and_values():
    a = crane()
    h = LL.chart_hash(a)
    assert isinstance(h, str) and h.startswith("sha256:")
    assert LL.chart_hash(LL.from_data(a)) == h
    # the same charts in kg / mm
    b = copy.deepcopy(a)
    b["units"] = {"mass": "kg", "length": "mm"}
    for c in b["charts"]:
        c["radius"] = [r * 1000 for r in c["radius"]]
        c["capacity"] = [None if x is None else x * 1000 for x in c["capacity"]]
        c["config"] = {"boom": c["config"]["boom"] * 1000, "counterweight": c["config"]["counterweight"] * 1000}
    b["hook_blocks"] = [{"name": "Block 40 t", "mass": 850.0}]
    assert LL.chart_hash(b) == h
    # the same charts in lb / ft (float noise from the conversion)
    lb, ft = 0.45359237, 0.3048
    c = copy.deepcopy(a)
    c["units"] = {"mass": "lb", "length": "ft"}
    for ch in c["charts"]:
        ch["radius"] = [r / ft for r in ch["radius"]]
        ch["capacity"] = [None if x is None else x * 1000 / lb for x in ch["capacity"]]
        ch["config"] = {"boom": ch["config"]["boom"] / ft, "counterweight": ch["config"]["counterweight"] * 1000 / lb}
    assert LL.chart_hash(c) == h
    # a changed value changes it
    d = copy.deepcopy(a)
    d["charts"][0]["capacity"][3] = 19.0
    assert LL.chart_hash(d) != h
    e = copy.deepcopy(a)
    e["charts"][0]["capacity"][2] = None
    assert LL.chart_hash(e) != h
    f = copy.deepcopy(a)
    f["charts"][0]["config"]["boom"] = 21.0
    assert LL.chart_hash(f) != h


def test_chart_hash_wll():
    assert LL.chart_hash(sling(wll=8.0)) != LL.chart_hash(sling(wll=8.5))
    assert LL.chart_hash(sling(wll=8.0)) == LL.chart_hash(LL.new_item("sling", "chain sling", "X", mass_unit="kg",
                                                                      wll=8000.0))


def test_round_trip_copy_change_clear(tmp_path):
    bf = builtin_lib(tmp_path)
    lib = tmp_path / "lib"
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    assert sample.builtin and LL.is_sample(sample)
    assert all(c.sample for c in LL.charts_of(sample))
    # a built-in never loses its mark
    with pytest.raises(LL.LibraryError):
        LL.clear_sample(sample)
    cp = LL.copy_item(sample, str(lib), "My crane", builtin_folder=str(bf))
    assert not cp.builtin
    assert cp.name == "My crane"
    assert LL.is_sample(cp) and cp.sample
    assert cp.data.get("derived_from") == LL.chart_hash(sample)
    files = os.listdir(lib / "My crane")
    assert "My crane.json" in files
    assert any(f.lower().endswith(".step") for f in files)
    assert any(f.lower().endswith(".png") for f in files)
    assert json.loads((lib / "My crane" / "My crane.json").read_text(encoding="utf-8"))["name"] == "My crane"
    # the built-in folder is untouched
    assert sorted(os.listdir(bf / "Sample crane")) == ["Sample crane.json", "Sample crane.png", "Sample crane.step"]
    # unchanged: clearing refused with words
    with pytest.raises(LL.LibraryError) as ex:
        LL.clear_sample(cp)
    assert "sample" in str(ex.value).lower()
    assert LL.is_sample(cp)
    # hand-set sample false and write: refused
    forged = copy.deepcopy(cp.data)
    forged["sample"] = False
    with pytest.raises(LL.LibraryError):
        LL.write_item(forged, str(lib))
    # his own chart now
    cp.data["charts"][0]["capacity"][3] = 19.0
    msg = LL.clear_sample(cp)
    assert isinstance(msg, str) and msg.strip()
    assert not LL.is_sample(cp)
    LL.write_item(cp, str(lib))
    back = LL.read_item(str(lib / "My crane"))
    assert back.ok, back.problems
    assert not back.sample and not LL.is_sample(back)
    assert not any(c.sample for c in LL.charts_of(back))
    assert LL.charts_of(back)[0].capacity[3] == pytest.approx(19000)


def test_copy_units_only_stays_sample(tmp_path):
    bf = builtin_lib(tmp_path)
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    cp = LL.copy_item(sample, str(tmp_path / "lib"), "Kilo copy", builtin_folder=str(bf))
    d = cp.data
    d["units"] = {"mass": "kg", "length": "m"}
    for c in d["charts"]:
        c["capacity"] = [None if x is None else x * 1000 for x in c["capacity"]]
        c["config"]["counterweight"] = c["config"]["counterweight"] * 1000
    for b in d.get("hook_blocks", []):
        b["mass"] = b["mass"] * 1000
    with pytest.raises(LL.LibraryError):
        LL.clear_sample(d)
    assert LL.is_sample(d)


def test_copy_refuses_existing_name(tmp_path):
    bf = builtin_lib(tmp_path)
    lib = tmp_path / "lib"
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    LL.copy_item(sample, str(lib), "Mine", builtin_folder=str(bf))
    with pytest.raises(LL.LibraryError):
        LL.copy_item(sample, str(lib), "Mine", builtin_folder=str(bf))


def test_copy_into_builtin_refused(tmp_path):
    bf = builtin_lib(tmp_path)
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    with pytest.raises(LL.LibraryError):
        LL.copy_item(sample, str(bf), "Another", builtin_folder=str(bf))
    assert sorted(os.listdir(bf)) == ["Sample crane"]


def test_copy_of_copy_keeps_derived_from(tmp_path):
    bf = builtin_lib(tmp_path)
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    a = LL.copy_item(sample, str(tmp_path / "lib"), "A", builtin_folder=str(bf))
    b = LL.copy_item(a, str(tmp_path / "lib"), "B", builtin_folder=str(bf))
    assert LL.is_sample(b)
    assert b.data.get("derived_from") == LL.chart_hash(sample)
    with pytest.raises(LL.LibraryError):
        LL.clear_sample(b)


def test_copy_of_own_item_is_not_sample(tmp_path):
    w = LL.write_item(crane("Own"), str(tmp_path / "lib"))
    own = LL.read_item(w.path)
    cp = LL.copy_item(own, str(tmp_path / "lib"), "Own 2")
    assert not LL.is_sample(cp)
    assert cp.ok, cp.problems


def test_builtin_without_sample_flag_still_sample(tmp_path):
    bf = tmp_path / "builtin"
    d = crane("Unmarked")
    d["sample"] = False
    write_json(str(bf / "Unmarked" / "Unmarked.json"), d)
    (it,) = LL.list_items(None, builtin_folder=str(bf))
    assert it.builtin
    assert LL.is_sample(it) or it.problems


def test_hand_edited_copy_cannot_drop_mark(tmp_path):
    bf = builtin_lib(tmp_path)
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    cp = LL.copy_item(sample, str(tmp_path / "lib"), "Edited", builtin_folder=str(bf))
    p = os.path.join(cp.folder, "Edited.json")
    data = json.loads(open(p, encoding="utf-8").read())
    data["sample"] = False  # by hand in a text editor, charts untouched
    write_json(p, data)
    it = LL.read_item(p)
    assert LL.is_sample(it) or it.problems


def test_clear_sample_on_plain_data_with_derived_from():
    d = crane()
    d["sample"] = True
    h = LL.chart_hash(d)
    d["derived_from"] = h
    with pytest.raises(LL.LibraryError):
        LL.clear_sample(d)
    d["charts"][0]["capacity"][0] = 35.0
    LL.clear_sample(d)
    assert d["sample"] is False or not LL.is_sample(d)


# ---------------------------------------------------------------------------------------------------------------------
# More ways to break it

def test_known_kinds_give_no_note():
    it = LL.from_data(crane())
    assert not any("kind" in n.lower() for n in it.notes), it.notes


BAD_VALUES = {
    "capacity true": lambda d: d["charts"][0]["capacity"].__setitem__(0, True),
    "radius true": lambda d: d["charts"][0]["radius"].__setitem__(0, True),
    "capacity string": lambda d: d["charts"][0]["capacity"].__setitem__(0, "36"),
    "boom string": lambda d: d["charts"][0]["config"].__setitem__("boom", "twenty"),
    "hook block negative": lambda d: d.__setitem__("hook_blocks", [{"name": "B", "mass": -1.0}]),
    "hook block no mass": lambda d: d.__setitem__("hook_blocks", [{"name": "B"}]),
    "sample not bool": lambda d: d.__setitem__("sample", "no"),
    "name not text": lambda d: d.__setitem__("name", 42),
}


@pytest.mark.parametrize("name", list(BAD_VALUES))
def test_bad_values_in_file_are_problems(name):
    d = crane()
    BAD_VALUES[name](d)
    it = LL.from_data(d)
    assert it.problems, f"{name}: accepted"


@pytest.mark.parametrize("wll", [-8.0, 0.0, "8", {"straight": 0.0}, {"choke": -1.0}, True])
def test_bad_wll_is_a_problem(wll):
    assert LL.from_data(sling(wll=wll)).problems


def test_chart_rows_capacity_true_refused():
    e = LL.chart_rows([(A, 8, 30), (A, 10, True)])
    assert not e.ok


def test_csv_same_configuration_twice_refused():
    e = LL.chart_csv("boom 20 m\n8;30\n10;25\nboom 20 m\n8;29\n10;24\n")
    assert not e.ok


def test_copy_name_cannot_escape(tmp_path):
    bf = builtin_lib(tmp_path)
    lib = tmp_path / "lib"
    lib.mkdir()
    (sample,) = LL.list_items(None, builtin_folder=str(bf))
    # settled with the author: a name with path characters is turned into a safe folder name inside the library
    # (the item keeps its name); a name with nothing usable is refused
    for bad in ("../evil", "a/b"):
        copy = LL.copy_item(sample, str(lib), bad, builtin_folder=str(bf))
        assert os.path.dirname(os.path.realpath(copy.folder)) == os.path.realpath(lib)
        assert copy.name == bad
    with pytest.raises(LL.LibraryError):
        LL.copy_item(sample, str(lib), "..", builtin_folder=str(bf))
    assert sorted(os.listdir(tmp_path)) == ["builtin", "lib"]
